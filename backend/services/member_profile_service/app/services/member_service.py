from services.shared.cache import delete_pattern, get_json, set_json
from services.shared.common import build_event, ensure_same_user_or_admin, fail, require_auth, success, body_hash
from services.shared.kafka_bus import publish_event
import time

def payload_ts():
    return int(time.time()*1000)

class MemberProfileService:
    def __init__(self, repo):
        self.repo = repo

    async def create_member(self, payload, authorization, trc):
        try:
            actor = require_auth(authorization)
        except Exception:
            return fail("auth_required", "Missing, expired, or invalid bearer token.", trc, status_code=401)
        member_id = payload.get("member_id") or actor['sub']
        if actor['role'] not in {'member', 'admin'}:
            return fail('forbidden', 'Member or admin role required.', trc, status_code=403)
        if actor['role'] != 'admin' and actor['sub'] != member_id:
            return fail('forbidden', 'You can only create your own member profile.', trc, status_code=403)
        existing = self.repo.get(member_id)
        if payload.get('email') and actor['role'] != 'admin' and payload.get('email') != actor.get('email'):
            return fail('email_mismatch', 'Profile email does not match authenticated subject email.', trc, status_code=409)
        full = {**payload, "member_id": member_id, 'email': payload.get('email') or actor.get('email')}
        if existing:
            updated = self.repo.update(member_id, full)
            await publish_event('member.updated', build_event(event_type='member.updated', actor_id=actor['sub'], entity_type='member', entity_id=member_id, payload={'email': full.get('email')}, trace=trc))
            return success({"member_id": member_id, "status": "updated", "profile_version": updated.get('profile_version', 1)}, trc)
        full['profile_version'] = 1
        try:
            self.repo.create(full)
        except Exception:
            return fail("duplicate_member", "Member profile already exists for this account.", trc, status_code=409)
        await publish_event('member.created', build_event(event_type='member.created', actor_id=actor['sub'], entity_type='member', entity_id=member_id, payload={'email': full.get('email')}, trace=trc))
        return success({"member_id": member_id, "status": "created", "profile_version": 1}, trc)

    def get_member(self, payload, authorization, trc):
        try:
            actor = require_auth(authorization)
        except Exception:
            return fail("auth_required", "Missing, expired, or invalid bearer token.", trc, status_code=401)
        member_id = payload.get("member_id") or actor.get('sub')
        cache_key = f"member:get:{member_id}"
        cached = get_json(cache_key)
        if cached:
            return success(cached, trc, {"cache": "hit"})
        member = self.repo.get(member_id)
        if not member:
            return fail("not_found", "Requested member profile does not exist.", trc, status_code=404)
        profile = {k: v for k, v in member.items() if k != "profile_version"}
        body = {"member_id": member["member_id"], "profile": profile}
        set_json(cache_key, body, 120)
        return success(body, trc, {"cache": "miss"})

    async def update_member(self, payload, authorization, trc):
        try:
            actor = require_auth(authorization)
            ensure_same_user_or_admin(actor, payload.get("member_id"))
        except Exception:
            return fail("forbidden", "Authenticated user lacks permission or role for the target action.", trc, status_code=403)
        try:
            member = self.repo.update(payload.get("member_id"), payload, payload.get("expected_version"))
        except ValueError:
            existing = self.repo.get(payload.get("member_id"))
            return fail("version_conflict", "Profile was modified by another request. Refresh and try again.", trc, {"expected_version": payload.get("expected_version"), "current_version": existing.get("profile_version") if existing else None}, False, 409)
        if not member:
            return fail("not_found", "Requested entity does not exist.", trc, status_code=404)
        delete_pattern(f'member:get:{payload.get("member_id")}')
        delete_pattern('members:search:*')
        await publish_event('member.updated', build_event(event_type='member.updated', actor_id=actor['sub'], entity_type='member', entity_id=payload['member_id'], payload={'profile_version': member['profile_version']}, trace=trc))
        return success({"member_id": payload["member_id"], "updated": True, "profile_version": member["profile_version"]}, trc)

    async def delete_member(self, payload, authorization, trc):
        try:
            actor = require_auth(authorization)
            ensure_same_user_or_admin(actor, payload.get("member_id"))
        except Exception:
            return fail("forbidden", "You are not allowed to delete this member profile.", trc, status_code=403)
        if not self.repo.delete(payload.get("member_id")):
            return fail("not_found", "Requested entity does not exist.", trc, status_code=404)
        await publish_event('member.deleted', build_event(event_type='member.deleted', actor_id=actor['sub'], entity_type='member', entity_id=payload['member_id'], payload={'reason': payload.get('reason')}, trace=trc))
        return success({"member_id": payload["member_id"], "status": "deleted"}, trc)

    def search_members(self, payload, authorization, trc):
        try:
            actor = require_auth(authorization)
        except Exception:
            return fail("auth_required", "Missing, expired, or invalid bearer token.", trc, status_code=401)
        if actor["role"] not in {"member", "recruiter", "admin"}:
            return fail("forbidden", "Authenticated user required.", trc, status_code=403)
        cache_key = f"members:search:{body_hash(payload)}"
        cached = get_json(cache_key)
        if cached:
            return success(cached['body'], trc, {**cached['meta'], 'cache': 'hit'})
        items = self.repo.search(skill=payload.get("skill") or "", location=payload.get("location") or "", keyword=payload.get("keyword") or "")
        items = [m for m in items if m.get('member_id') != actor.get('sub')]
        try:
            page = int(payload.get("page", 1))
        except (TypeError, ValueError):
            page = 1
        page = max(1, page)
        try:
            page_size = int(payload.get("page_size", 10))
        except (TypeError, ValueError):
            page_size = 10
        page_size = max(1, min(page_size, 5000))
        start = (page - 1) * page_size
        shaped = [{"member_id": m["member_id"], "first_name": m.get("first_name", ""), "last_name": m.get("last_name", ""), "headline": m.get("headline", ""), "city": m.get("city") or m.get("location") or '', "location": m.get("location", ''), "skills": m.get("skills", [])[:5], "profile_photo_url": m.get("profile_photo_url", '')} for m in items]
        body = {"items": shaped[start:start+page_size]}
        meta = {"page": page, "page_size": page_size, "total": len(shaped), 'cache': 'miss'}
        set_json(cache_key, {'body': body, 'meta': meta}, 120)
        return success(body, trc, meta)



    async def member_upload_file(self, member_id, kind, file, authorization, trc):
        try:
            actor = require_auth(authorization)
        except Exception:
            return fail('auth_required', 'Missing, expired, or invalid bearer token.', trc, status_code=401)
        if actor['role'] != 'admin' and actor['sub'] != member_id:
            return fail('forbidden', 'You may only upload assets for your own profile.', trc, status_code=403)
        from services.shared.storage import MINIO_BUCKET_PROFILE, MINIO_BUCKET_RESUME, upload_bytes
        ext = (file.filename or 'bin').split('.')[-1]
        bucket = MINIO_BUCKET_PROFILE if kind == 'profile_photo' else MINIO_BUCKET_RESUME
        object_name = f"{member_id}/{kind}-{payload_ts()}.{ext}"
        blob = await file.read()
        download_url = upload_bytes(bucket, object_name, blob, file.content_type or 'application/octet-stream')
        member = self.repo.get(member_id)
        if member:
            field = 'profile_photo_url' if kind == 'profile_photo' else 'resume_url'
            self.repo.update(member_id, {field: download_url})
            delete_pattern(f'member:get:{member_id}')
            delete_pattern('members:search:*')
        return success({'bucket': bucket, 'object_name': object_name, 'download_url': download_url}, trc)

    def member_upload_url(self, payload, authorization, trc):
        try:
            actor = require_auth(authorization)
        except Exception:
            return fail('auth_required', 'Missing, expired, or invalid bearer token.', trc, status_code=401)
        member_id = payload.get('member_id') or actor.get('sub')
        if actor['role'] != 'admin' and actor['sub'] != member_id:
            return fail('forbidden', 'You may only upload assets for your own profile.', trc, status_code=403)
        from services.shared.storage import MINIO_BUCKET_PROFILE, MINIO_BUCKET_RESUME, presigned_put, presigned_get
        kind = payload.get('kind', 'profile_photo')
        ext = payload.get('ext', 'bin').lstrip('.')
        bucket = MINIO_BUCKET_PROFILE if kind == 'profile_photo' else MINIO_BUCKET_RESUME
        object_name = f"{member_id}/{kind}-{payload.get('ts') or 'latest'}.{ext}"
        upload_url = presigned_put(bucket, object_name)
        download_url = presigned_get(bucket, object_name)
        return success({'bucket': bucket, 'object_name': object_name, 'upload_url': upload_url, 'download_url': download_url}, trc)
