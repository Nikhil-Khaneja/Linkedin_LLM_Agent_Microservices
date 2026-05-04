from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import mimetypes

from fastapi import APIRouter, Body, File, Form, Header, Query, UploadFile
from fastapi.responses import Response, StreamingResponse
from pymongo import MongoClient

from services.shared.common import success, fail, trace_id, require_auth, build_event
from services.shared.kafka_bus import publish_event
from services.shared.cache import get_json, set_json
from services.shared.relational import fetch_one, fetch_all, execute
from services.shared.media_signed_url import (
    default_member_public_url,
    member_media_proxy_url,
    sanitize_media_public_base,
    verify_media_params,
)
from services.shared.storage import MINIO_BUCKET_PROFILE, MINIO_BUCKET_RESUME, client as minio_client
from services.member_profile_service.app.services.media_upload_service import get_media_upload_service
from services.shared.notifications import create_notification
from services.shared.resume_parser import extract_text_from_bytes

router = APIRouter()

UPLOAD_DIR = Path(os.environ.get("APP_DATA_DIR", "/app/data")) / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

_MONGO_CLIENT = None


def _mongo():
    global _MONGO_CLIENT
    if _MONGO_CLIENT is None:
        uri = os.environ.get("MONGO_URI") or os.environ.get("MONGO_URL") or "mongodb://mongo:27017"
        _MONGO_CLIENT = MongoClient(uri)
    db_name = os.environ.get("MONGO_DATABASE", "linkedin_sim")
    return _MONGO_CLIENT[db_name]


def _notifications():
    return _mongo()["notifications"]


def _actor(authorization: str | None):
    claims = require_auth(authorization)
    actor_id = claims.get("sub") or claims.get("user_id")
    role = claims.get("role") or claims.get("subject_type")
    email = claims.get("email")
    return {"actor_id": actor_id, "role": role, "email": email}


def _parse_payload(raw):
    try:
        return json.loads(raw or "{}")
    except Exception:
        return {}


def _safe_list(value):
    return value if isinstance(value, list) else []


def _json_list(value):
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value:
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []
    return []


def _derive_current_experience(experience: list[dict] | list[str] | None) -> tuple[str | None, str | None]:
    entries = [e for e in (experience or []) if isinstance(e, dict)]
    if not entries:
        return None, None

    def sort_key(entry: dict):
        current = 1 if entry.get('is_current') or str(entry.get('end_year') or '').lower() in {'present', 'current'} else 0
        try:
            year = int(str(entry.get('start_year') or 0)[:4])
        except Exception:
            year = 0
        try:
            month = int(entry.get('start_month') or 0)
        except Exception:
            month = 0
        return (current, year, month)

    top = sorted(entries, key=sort_key, reverse=True)[0]
    return (top.get('company') or top.get('company_name') or None, top.get('title') or top.get('role') or None)




def _pending_member_update_key(member_id: str) -> str:
    return f"member:pending:update:{member_id}"


def _shape_profile_preview(member_id: str, row, merged_payload: dict, location_text: str, profile_version: int):
    profile = {
        "member_id": member_id,
        "email": merged_payload.get("email") or (row.get("email") if row else ''),
        "first_name": merged_payload.get("first_name") or (row.get("first_name") if row else ''),
        "last_name": merged_payload.get("last_name") or (row.get("last_name") if row else ''),
        "headline": merged_payload.get("headline") or (row.get("headline") if row else ''),
        "about_summary": merged_payload.get("about_summary") or merged_payload.get("about") or (row.get("about_text") if row else ''),
        "location": location_text or (row.get("location_text") if row else ''),
        "city": merged_payload.get("city") or '',
        "state": merged_payload.get("state") or '',
        "skills": _safe_list(merged_payload.get("skills") or []),
        "experience": _safe_list(merged_payload.get("experience") or []),
        "education": _safe_list(merged_payload.get("education") or []),
        "profile_photo_url": merged_payload.get("profile_photo_url") or (row.get("profile_photo_url") if row else ''),
        "resume_url": merged_payload.get("resume_url") or (row.get("resume_url") if row else ''),
        "resume_text": merged_payload.get("resume_text") or (row.get("resume_text") if row else ''),
        "current_company": merged_payload.get("current_company") or '',
        "current_title": merged_payload.get("current_title") or '',
        "connections_count": (row.get("connections_count") if row else 0) or 0,
        "profile_views": (row.get("profile_views") if row else 0) or 0,
        "profile_version": profile_version,
    }
    return profile

def _resolve_media_public_base(payload: dict | None) -> str:
    if not payload:
        return default_member_public_url()
    raw = sanitize_media_public_base(payload.get("media_public_base"))
    return raw or default_member_public_url()


def _member_to_profile(row, media_public_base: str | None = None):
    if not row:
        return None
    payload = _parse_payload(row.get("payload_json"))
    location_text = row.get("location_text") or ""
    city = payload.get("city")
    state = payload.get("state")
    if not city and location_text:
        parts = [p.strip() for p in location_text.split(",")]
        if parts:
            city = parts[0]
            state = parts[1] if len(parts) > 1 else state
    experience = _json_list(row.get('experience_json')) or _safe_list(payload.get("experience", []))
    current_company, current_title = _derive_current_experience(experience)
    photo_url = row.get("profile_photo_url") or payload.get("profile_photo_url") or ""
    photo_obj = (payload.get("profile_photo_object") or "").strip()
    photo_bucket = (payload.get("profile_photo_bucket") or MINIO_BUCKET_PROFILE).strip()
    base = (media_public_base or default_member_public_url()).strip().rstrip("/") or default_member_public_url()
    mid = row.get("member_id") or ""
    if photo_obj:
        try:
            photo_url = member_media_proxy_url(base, mid, photo_bucket, photo_obj, ttl_seconds=3600)
        except Exception:
            photo_url = row.get("profile_photo_url") or payload.get("profile_photo_url") or ""
    resume_url = row.get("resume_url") or payload.get("resume_url") or ""
    resume_obj = (payload.get("resume_object") or "").strip()
    resume_bucket = (payload.get("resume_bucket") or MINIO_BUCKET_RESUME).strip()
    if resume_obj:
        try:
            resume_url = member_media_proxy_url(base, mid, resume_bucket, resume_obj, ttl_seconds=3600)
        except Exception:
            resume_url = row.get("resume_url") or payload.get("resume_url") or ""
    return {
        "member_id": row.get("member_id"),
        "email": row.get("email"),
        "first_name": row.get("first_name"),
        "last_name": row.get("last_name"),
        "headline": row.get("headline"),
        "about_summary": row.get("about_text"),
        "location": row.get("location_text"),
        "city": city,
        "state": state,
        "skills": _json_list(row.get('skills_json')) or _safe_list(payload.get("skills", [])),
        "experience": experience,
        "education": _json_list(row.get('education_json')) or _safe_list(payload.get("education", [])),
        "profile_photo_url": photo_url,
        "resume_url": resume_url,
        "resume_text": row.get("resume_text") or payload.get("resume_text") or "",
        "current_company": row.get("current_company") or payload.get("current_company") or current_company,
        "current_title": row.get("current_title") or payload.get("current_title") or current_title,
        "connections_count": row.get("connections_count") or 0,
        "profile_views": row.get("profile_views") or 0,
    }


def _ensure_member(member_id: str, email: str | None = None):
    row = fetch_one("SELECT * FROM members WHERE member_id=:member_id", {"member_id": member_id})
    if row:
        return row
    execute(
        """
        INSERT INTO members (member_id, email, first_name, last_name, headline, about_text, location_text, profile_version, is_deleted, payload_json, skills_json, experience_json, education_json, profile_photo_url, resume_url, resume_text, current_company, current_title)
        VALUES (:member_id, :email, '', '', '', '', '', 1, 0, :payload_json, :skills_json, :experience_json, :education_json, '', '', '', '', '')
        """,
        {"member_id": member_id, "email": email or "", "payload_json": json.dumps({}), "skills_json": json.dumps([]), "experience_json": json.dumps([]), "education_json": json.dumps([])},
    )
    return fetch_one("SELECT * FROM members WHERE member_id=:member_id", {"member_id": member_id})


def _create_notification(member_id: str, actor_id: str):
    actor_row = fetch_one(
        "SELECT member_id, first_name, last_name, email FROM members WHERE member_id=:member_id",
        {"member_id": actor_id},
    )
    display_name = actor_id
    target_url = f'/profile/{actor_id}'
    if actor_row:
        full_name = f"{actor_row.get('first_name') or ''} {actor_row.get('last_name') or ''}".strip()
        display_name = full_name or actor_row.get("email") or actor_id
    else:
        recruiter_row = fetch_one(
            "SELECT recruiter_id, name, email FROM recruiters WHERE recruiter_id=:recruiter_id",
            {"recruiter_id": actor_id},
        )
        if recruiter_row:
            display_name = recruiter_row.get('name') or recruiter_row.get('email') or actor_id
            target_url = f'/profile/{actor_id}'
    create_notification(
        member_id,
        'profile.viewed',
        'Profile viewed',
        f'{display_name} viewed your profile',
        actor_id=actor_id,
        actor_name=display_name,
        target_url=target_url,
        data={'member_id': member_id, 'viewer_id': actor_id},
    )


@router.get("/members/media")
async def stream_member_media(
    member_id: str = Query(...),
    bucket: str = Query(...),
    object_name: str = Query(..., alias="object"),
    e: int = Query(...),
    s: str = Query(...),
):
    """Stream profile (or other member) media from MinIO using a signed URL (browser-safe, no presigned host mismatch)."""
    if not verify_media_params(member_id, bucket, object_name, e, s):
        return Response(status_code=403, content="Invalid or expired media link.")
    try:
        obj = minio_client().get_object(bucket, object_name)
    except Exception:
        return Response(status_code=404, content="Object not found.")

    media_type = mimetypes.guess_type(object_name)[0] or "application/octet-stream"

    def body():
        try:
            while True:
                chunk = obj.read(65536)
                if not chunk:
                    break
                yield chunk
        finally:
            try:
                obj.close()
            except Exception:
                pass
            try:
                obj.release_conn()
            except Exception:
                pass

    return StreamingResponse(body(), media_type=media_type)


def _merge_profile_payload(existing_payload: dict, incoming: dict) -> tuple[dict, str, str]:
    payload = dict(existing_payload)
    for key in ("skills", "experience", "education"):
        if key in incoming:
            payload[key] = incoming.get(key) or []
    for key in ("profile_photo_url", "resume_url", "resume_text"):
        if incoming.get(key) is not None:
            payload[key] = incoming.get(key)
    city = incoming.get("city") or payload.get("city") or ''
    state = incoming.get("state") or payload.get("state") or ''
    payload["city"] = city
    payload["state"] = state
    current_company, current_title = _derive_current_experience(payload.get('experience'))
    payload['current_company'] = current_company or incoming.get('current_company') or payload.get('current_company') or ''
    payload['current_title'] = current_title or incoming.get('current_title') or payload.get('current_title') or ''
    return payload, payload.get('current_company') or '', payload.get('current_title') or ''


@router.post("/members/create")
async def create_member(payload: dict = Body(...), authorization: str | None = Header(None), x_trace_id: str | None = Header(None)):
    trc = trace_id(x_trace_id)
    try:
        actor = _actor(authorization)
    except Exception:
        return fail("auth_required", "Bearer token is missing or invalid.", trc, status_code=401)

    member_id = payload.get("member_id") or actor["actor_id"]
    if member_id != actor["actor_id"] and actor["role"] != "admin":
        return fail("forbidden", "You can only create your own member profile.", trc, status_code=403)
    row = _ensure_member(member_id, payload.get("email") or actor.get("email"))
    current_payload, current_company, current_title = _merge_profile_payload(_parse_payload(row.get("payload_json")), payload)
    location_text = payload.get("location") or ", ".join([p for p in [current_payload.get('city'), current_payload.get('state')] if p])

    execute(
        """
        UPDATE members
        SET email=:email,
            first_name=:first_name,
            last_name=:last_name,
            headline=:headline,
            about_text=:about_text,
            location_text=:location_text,
            payload_json=:payload_json,
            skills_json=:skills_json,
            experience_json=:experience_json,
            education_json=:education_json,
            profile_photo_url=:profile_photo_url,
            resume_url=:resume_url,
            resume_text=:resume_text,
            current_company=:current_company,
            current_title=:current_title,
            is_deleted=0,
            profile_version=COALESCE(profile_version, 1) + 1
        WHERE member_id=:member_id
        """,
        {
            "member_id": member_id,
            "email": payload.get("email", row.get("email") or actor.get("email") or ""),
            "first_name": payload.get("first_name", row.get("first_name") or ""),
            "last_name": payload.get("last_name", row.get("last_name") or ""),
            "headline": payload.get("headline", row.get("headline") or ""),
            "about_text": payload.get("about_summary", row.get("about_text") or ""),
            "location_text": location_text or row.get("location_text") or "",
            "payload_json": json.dumps(current_payload),
            "skills_json": json.dumps(current_payload.get('skills') or []),
            "experience_json": json.dumps(current_payload.get('experience') or []),
            "education_json": json.dumps(current_payload.get('education') or []),
            "profile_photo_url": current_payload.get('profile_photo_url') or row.get('profile_photo_url') or '',
            "resume_url": current_payload.get('resume_url') or row.get('resume_url') or '',
            "resume_text": current_payload.get('resume_text') or row.get('resume_text') or '',
            "current_company": current_company,
            "current_title": current_title,
        },
    )
    row = fetch_one("SELECT * FROM members WHERE member_id=:member_id", {"member_id": member_id})
    profile = _member_to_profile(row, _resolve_media_public_base(payload))
    if actor.get("role") != "admin" and actor.get("actor_id") != member_id and profile:
        profile.pop("profile_views", None)
    return success({"profile": profile}, trc)


@router.post("/members/get")
async def get_member(payload: dict = Body(...), authorization: str | None = Header(None), x_trace_id: str | None = Header(None)):
    trc = trace_id(x_trace_id)
    try:
        actor = _actor(authorization)
    except Exception:
        return fail("auth_required", "Bearer token is missing or invalid.", trc, status_code=401)

    member_id = payload.get("member_id") or actor["actor_id"]
    media_base = _resolve_media_public_base(payload)
    pending = get_json(_pending_member_update_key(member_id)) if actor.get("actor_id") == member_id or actor.get("role") == 'admin' else None
    if pending and isinstance(pending, dict) and pending.get('profile'):
        profile = dict(pending.get('profile') or {})
        if actor.get("role") != "admin" and actor.get("actor_id") != member_id and profile:
            profile.pop("profile_views", None)
        return success({"profile": profile}, trc, {'write_state': 'pending'})

    row = fetch_one("SELECT * FROM members WHERE member_id=:member_id", {"member_id": member_id})
    if not row and member_id == actor["actor_id"]:
        row = _ensure_member(member_id, actor.get("email"))
    if not row:
        return fail("member_not_found", "Member profile not found.", trc, status_code=404)

    if actor["actor_id"] and actor["actor_id"] != member_id:
        try:
            execute("UPDATE members SET profile_views = COALESCE(profile_views, 0) + 1 WHERE member_id=:member_id", {"member_id": member_id})
        except Exception:
            pass
        try:
            _create_notification(member_id, actor["actor_id"])
        except Exception:
            pass
        try:
            await publish_event('profile.viewed', build_event(event_type='profile.viewed', actor_id=actor['actor_id'], entity_type='member', entity_id=member_id, payload={'member_id': member_id, 'viewer_role': actor.get('role')}, trace=trc, idempotency_key=f"profile:{member_id}:{actor['actor_id']}:{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"))
        except Exception:
            pass
        row = fetch_one("SELECT * FROM members WHERE member_id=:member_id", {"member_id": member_id})

    profile = _member_to_profile(row, media_base)
    if actor.get("role") != "admin" and actor.get("actor_id") != member_id and profile:
        profile.pop("profile_views", None)
    return success({"profile": profile}, trc)


@router.post("/members/update")
async def update_member(payload: dict = Body(...), authorization: str | None = Header(None), x_trace_id: str | None = Header(None)):
    trc = trace_id(x_trace_id)
    try:
        actor = _actor(authorization)
    except Exception:
        return fail("auth_required", "Bearer token is missing or invalid.", trc, status_code=401)

    member_id = payload.get("member_id") or actor["actor_id"]
    if member_id != actor["actor_id"] and actor["role"] != "admin":
        return fail("forbidden", "You can only update your own member profile.", trc, status_code=403)

    row = _ensure_member(member_id, actor.get("email"))
    current_payload, current_company, current_title = _merge_profile_payload(_parse_payload(row.get("payload_json")), payload)
    location_text = payload.get("location") or ", ".join([p for p in [current_payload.get('city'), current_payload.get('state')] if p])
    next_version = int(row.get('profile_version') or 1) + 1
    current_payload['email'] = current_payload.get('email') or row.get('email') or actor.get('email') or ''
    current_payload['first_name'] = payload.get('first_name', row.get('first_name') or current_payload.get('first_name') or '')
    current_payload['last_name'] = payload.get('last_name', row.get('last_name') or current_payload.get('last_name') or '')
    current_payload['headline'] = payload.get('headline', row.get('headline') or current_payload.get('headline') or '')
    current_payload['about_summary'] = payload.get('about_summary', row.get('about_text') or current_payload.get('about_summary') or current_payload.get('about') or '')
    current_payload['location'] = location_text or row.get('location_text') or ''
    current_payload['current_company'] = current_company or current_payload.get('current_company') or ''
    current_payload['current_title'] = current_title or current_payload.get('current_title') or ''
    current_payload['profile_version'] = next_version
    profile = _shape_profile_preview(member_id, row, current_payload, location_text, next_version)
    command = {
        'member_id': member_id,
        'profile': profile,
    }
    idempotency_key = f'member.update.requested:{member_id}:{next_version}'
    set_json(_pending_member_update_key(member_id), {'profile': profile, 'queued_at': datetime.now(timezone.utc).isoformat()}, 300)
    published = await publish_event('member.update.requested', build_event(event_type='member.update.requested', actor_id=actor['actor_id'], entity_type='member', entity_id=member_id, payload=command, trace=trc, idempotency_key=idempotency_key))
    if not published:
        return fail('kafka_publish_failed', 'Profile update could not be queued.', trc, status_code=503)
    return success({'profile': profile}, trc, {'write_state': 'pending', 'dispatch': 'kafka'})


@router.post("/members/search")
async def search_members(payload: dict = Body(...), authorization: str | None = Header(None), x_trace_id: str | None = Header(None)):
    trc = trace_id(x_trace_id)
    try:
        actor = _actor(authorization)
    except Exception:
        return fail("auth_required", "Bearer token is missing or invalid.", trc, status_code=401)

    if actor["role"] not in {"member", "recruiter", "admin"}:
        return fail("forbidden", "You are not allowed to search members.", trc, status_code=403)

    media_base = _resolve_media_public_base(payload)
    keyword = (payload.get("keyword") or "").strip().lower()
    try:
        limit = int(payload.get("page_size") or 12)
    except (TypeError, ValueError):
        limit = 12
    limit = max(1, min(limit, 5000))
    try:
        page = int(payload.get("page") or 1)
    except (TypeError, ValueError):
        page = 1
    page = max(1, page)
    offset = (page - 1) * limit

    if keyword:
        like = f"%{keyword}%"
        rows = fetch_all(
            """
            SELECT * FROM members
            WHERE is_deleted = 0
              AND member_id LIKE 'mem_%'
              AND member_id <> :self_id
              AND (
                lower(first_name) LIKE :like OR
                lower(last_name) LIKE :like OR
                lower(email) LIKE :like OR
                lower(headline) LIKE :like OR
                lower(about_text) LIKE :like OR
                lower(location_text) LIKE :like OR
                lower(COALESCE(current_company, '')) LIKE :like OR
                lower(COALESCE(current_title, '')) LIKE :like OR
                lower(COALESCE(payload_json, '')) LIKE :like
              )
            ORDER BY first_name ASC, last_name ASC
            LIMIT :limit OFFSET :offset
            """,
            {"self_id": actor["actor_id"], "like": like, "limit": limit, "offset": offset},
        )
    else:
        rows = fetch_all(
            """
            SELECT * FROM members
            WHERE is_deleted = 0
              AND member_id LIKE 'mem_%'
              AND member_id <> :self_id
            ORDER BY first_name ASC, last_name ASC
            LIMIT :limit OFFSET :offset
            """,
            {"self_id": actor["actor_id"], "limit": limit, "offset": offset},
        )

    return success(
        {"items": [_member_to_profile(r, media_base) for r in rows]},
        trc,
        {"page": page, "page_size": limit, "offset": offset},
    )


@router.post("/members/upload-media")
async def upload_media(
    member_id: str = Form(...),
    media_type: str = Form(...),
    file: UploadFile = File(...),
    authorization: str | None = Header(None),
    x_trace_id: str | None = Header(None),
):
    trc = trace_id(x_trace_id)
    try:
        actor = _actor(authorization)
    except Exception:
        return fail("auth_required", "Bearer token is missing or invalid.", trc, status_code=401)

    target_member_id = member_id or actor["actor_id"]
    if target_member_id != actor["actor_id"] and actor["role"] != "admin":
        return fail("forbidden", "You can only upload media for your own profile.", trc, status_code=403)
    if media_type not in {"profile_photo", "resume"}:
        return fail("invalid_media_type", "media_type must be profile_photo or resume.", trc, status_code=400)

    _ensure_member(target_member_id, actor.get("email"))
    content = await file.read()
    upload = await get_media_upload_service().queue_upload(
        member_id=target_member_id,
        media_type=media_type,
        filename=file.filename or f"{media_type}.bin",
        content_type=file.content_type or "application/octet-stream",
        content=content,
        trc=trc,
    )
    return success({
        "upload_id": upload["upload_id"],
        "status": upload.get("status", "queued"),
        "file_url": upload.get("file_url"),
        "message": "Upload accepted and queued for asynchronous processing via Kafka.",
    }, trc, {"event_dispatch": "queued", "execution_mode": "kafka_async"})


@router.get("/members/upload-status/{upload_id}")
async def get_upload_status(
    upload_id: str,
    authorization: str | None = Header(None),
    x_trace_id: str | None = Header(None),
    media_public_base: str | None = Query(None),
):
    trc = trace_id(x_trace_id)
    try:
        actor = _actor(authorization)
    except Exception:
        return fail("auth_required", "Bearer token is missing or invalid.", trc, status_code=401)

    upload = get_media_upload_service().get_upload(upload_id)
    if not upload:
        return fail("upload_not_found", "Upload not found.", trc, status_code=404)
    if actor.get("role") != "admin" and actor.get("actor_id") != upload.get("member_id"):
        return fail("forbidden", "You can only view uploads for your own profile.", trc, status_code=403)

    row = fetch_one("SELECT * FROM members WHERE member_id=:member_id", {"member_id": upload.get("member_id")})
    base = sanitize_media_public_base(media_public_base) or default_member_public_url()
    profile = _member_to_profile(row, base) if row else None
    if actor.get("role") != "admin" and actor.get("actor_id") != upload.get("member_id") and profile:
        profile.pop("profile_views", None)
    return success({
        "upload_id": upload_id,
        "status": upload.get("status"),
        "media_type": upload.get("media_type"),
        "file_url": upload.get("file_url"),
        "extracted_text": upload.get("resume_text", "") if upload.get("media_type") == "resume" else None,
        "error": upload.get("error"),
        "profile": profile,
    }, trc)


@router.post("/members/notifications/list")
async def list_notifications(payload: dict = Body(...), authorization: str | None = Header(None), x_trace_id: str | None = Header(None)):
    trc = trace_id(x_trace_id)
    try:
        actor = _actor(authorization)
    except Exception:
        return fail("auth_required", "Bearer token is missing or invalid.", trc, status_code=401)

    member_id = actor["actor_id"]
    docs = list(_notifications().find({"member_id": member_id}).sort("created_at", -1).limit(int(payload.get("page_size") or 30)))
    for d in docs:
        d["notification_id"] = d.pop("_id")
    return success({"items": docs}, trc)


@router.post("/members/notifications/markRead")
async def mark_read(payload: dict = Body(...), authorization: str | None = Header(None), x_trace_id: str | None = Header(None)):
    trc = trace_id(x_trace_id)
    try:
        actor = _actor(authorization)
    except Exception:
        return fail("auth_required", "Bearer token is missing or invalid.", trc, status_code=401)

    notification_id = payload.get("notification_id")
    if not notification_id:
        return fail("validation_error", "notification_id is required.", trc, status_code=400)
    _notifications().update_one({"_id": notification_id, "member_id": actor["actor_id"]}, {"$set": {"is_read": True}})
    return success({"marked": True}, trc)


@router.post("/members/delete")
async def delete_member(payload: dict = Body(...), authorization: str | None = Header(None), x_trace_id: str | None = Header(None)):
    trc = trace_id(x_trace_id)
    try:
        actor = _actor(authorization)
    except Exception:
        return fail("auth_required", "Bearer token is missing or invalid.", trc, status_code=401)

    member_id = payload.get("member_id") or actor["actor_id"]
    if member_id != actor["actor_id"] and actor["role"] != "admin":
        return fail("forbidden", "You can only delete your own member profile.", trc, status_code=403)
    execute("UPDATE members SET is_deleted=1 WHERE member_id=:member_id", {"member_id": member_id})
    return success({"member_id": member_id, "deleted": True}, trc)
