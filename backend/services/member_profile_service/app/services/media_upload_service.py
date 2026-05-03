from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from services.shared.cache import delete_key
from services.shared.common import build_event, trace_id
from services.shared.document_store import find_one, replace_one, update_one
from services.shared.kafka_bus import consume_forever, publish_event
from services.shared.observability import get_logger, log_event
from services.shared.relational import execute, fetch_one
from services.shared.resume_parser import extract_text_from_bytes
from services.shared.media_signed_url import default_member_public_url, member_media_proxy_url
from services.shared.resume_structure import merge_skills_from_resume, structured_profile_from_resume_text
from services.shared.storage import (
    MINIO_BUCKET_PROFILE,
    MINIO_BUCKET_RESUME,
    download_bytes,
    upload_bytes,
)

UPLOAD_COLLECTION = 'media_uploads'
UPLOAD_DIR = Path(os.environ.get('APP_DATA_DIR', '/app/data')) / 'uploads'
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


class MediaUploadService:
    def __init__(self) -> None:
        self.stop_event = asyncio.Event()
        self.tasks: list[asyncio.Task] = []
        self.logger = get_logger('member_profile_service')

    async def startup(self) -> None:
        if self.tasks:
            return
        self.tasks.append(asyncio.create_task(consume_forever(['member.media.uploaded'], 'member-media-upload-processor', self.process_upload_event, self.stop_event)))
        log_event(self.logger, 'member_media_upload_startup', topic='member.media.uploaded')

    async def shutdown(self) -> None:
        self.stop_event.set()
        for task in self.tasks:
            task.cancel()
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks.clear()

    async def queue_upload(self, *, member_id: str, media_type: str, filename: str, content_type: str, content: bytes, trc: str | None = None) -> dict:
        trc = trc or trace_id()
        ext = Path(filename or '').suffix or '.bin'
        upload_id = f'upl_{uuid4().hex[:10]}'
        object_name = f'{member_id}_{media_type}_{upload_id}{ext}'
        bucket = MINIO_BUCKET_PROFILE if media_type == 'profile_photo' else MINIO_BUCKET_RESUME
        file_url = upload_bytes(bucket, object_name, content, content_type or 'application/octet-stream')
        now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        record = {
            'upload_id': upload_id,
            'member_id': member_id,
            'media_type': media_type,
            'status': 'queued',
            'bucket': bucket,
            'object_name': object_name,
            'filename': filename,
            'content_type': content_type or 'application/octet-stream',
            'file_url': file_url,
            'file_url_length': len(file_url or ''),
            'resume_text': '',
            'error': None,
            'created_at': now,
            'updated_at': now,
        }
        replace_one(UPLOAD_COLLECTION, {'upload_id': upload_id}, record, upsert=True)
        event = build_event(
            event_type='member.media.uploaded',
            actor_id=member_id,
            entity_type='media_upload',
            entity_id=upload_id,
            payload={'upload_id': upload_id, 'member_id': member_id, 'media_type': media_type},
            trace=trc,
            idempotency_key=f'media:{upload_id}',
        )
        published = await publish_event('member.media.uploaded', event)
        log_event(self.logger, 'member_media_upload_queued', upload_id=upload_id, member_id=member_id, media_type=media_type, published=published, file_url_length=len(file_url or ''))
        if not published:
            loop = asyncio.get_running_loop()
            loop.create_task(self.process_upload_event('member.media.uploaded', event))
        return record

    def get_upload(self, upload_id: str) -> dict | None:
        return find_one(UPLOAD_COLLECTION, {'upload_id': upload_id})

    async def process_upload_event(self, topic: str, event: dict) -> None:
        upload_id = (event.get('payload') or {}).get('upload_id') or event.get('entity', {}).get('entity_id')
        if not upload_id:
            return
        upload = self.get_upload(upload_id)
        if not upload:
            log_event(self.logger, 'member_media_upload_missing', upload_id=upload_id)
            return
        if upload.get('status') == 'completed':
            return
        update_one(UPLOAD_COLLECTION, {'upload_id': upload_id}, {'status': 'processing', 'updated_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')})
        log_event(self.logger, 'member_media_upload_processing', upload_id=upload_id, media_type=upload.get('media_type'), member_id=upload.get('member_id'), object_name=upload.get('object_name'), bucket=upload.get('bucket'))
        try:
            content = download_bytes(upload['bucket'], upload['object_name'])
            resume_text = ''
            if upload.get('media_type') == 'resume':
                resume_text = extract_text_from_bytes(upload.get('filename'), content, upload.get('content_type')) or ''
            self._apply_member_media(upload, resume_text)
            update_one(
                UPLOAD_COLLECTION,
                {'upload_id': upload_id},
                {
                    'status': 'completed',
                    'resume_text': resume_text,
                    'updated_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                    'error': None,
                },
            )
            log_event(self.logger, 'member_media_upload_completed', upload_id=upload_id, media_type=upload.get('media_type'), member_id=upload.get('member_id'), parsed_resume=bool(resume_text), stored_profile_photo_url_length=len(profile_photo_url) if 'profile_photo_url' in locals() else None, stored_resume_url_length=len(resume_url) if 'resume_url' in locals() else None)
        except Exception as exc:
            update_one(
                UPLOAD_COLLECTION,
                {'upload_id': upload_id},
                {
                    'status': 'failed',
                    'error': str(exc)[:500],
                    'updated_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                },
            )
            log_event(self.logger, 'member_media_upload_failed', upload_id=upload_id, media_type=upload.get('media_type'), member_id=upload.get('member_id'), error=str(exc))

    def _apply_member_media(self, upload: dict, resume_text: str) -> None:
        member_id = upload['member_id']
        row = fetch_one('SELECT * FROM members WHERE member_id=:member_id', {'member_id': member_id})
        if not row:
            log_event(self.logger, 'member_media_upload_member_missing', upload_id=upload.get('upload_id'), member_id=member_id)
            return
        try:
            payload = json.loads(row.get('payload_json') or '{}')
        except Exception:
            payload = {}
        profile_photo_url = row.get('profile_photo_url') or ''
        resume_url = row.get('resume_url') or ''
        resume_text_db = row.get('resume_text') or ''
        about_text = row.get('about_text') or ''
        experience_json = row.get('experience_json') or '[]'
        skills_json = row.get('skills_json') or '[]'
        if upload.get('media_type') == 'profile_photo':
            bucket = upload.get('bucket') or MINIO_BUCKET_PROFILE
            obj = (upload.get('object_name') or '').strip()
            profile_photo_url = (
                member_media_proxy_url(default_member_public_url(), member_id, bucket, obj, ttl_seconds=86400 * 7)
                or (upload.get('file_url') or profile_photo_url)
            )
            payload['profile_photo_url'] = profile_photo_url
            # Stable keys so /members/get can mint a fresh proxy URL (stored URLs expire).
            payload['profile_photo_bucket'] = bucket
            payload['profile_photo_object'] = obj
        elif upload.get('media_type') == 'resume':
            rbucket = upload.get('bucket') or MINIO_BUCKET_RESUME
            robj = (upload.get('object_name') or '').strip()
            resume_url = (
                member_media_proxy_url(default_member_public_url(), member_id, rbucket, robj, ttl_seconds=86400 * 7)
                or (upload.get('file_url') or resume_url)
            )
            resume_text_db = resume_text or resume_text_db
            payload['resume_url'] = resume_url
            payload['resume_bucket'] = rbucket
            payload['resume_object'] = robj
            if resume_text_db:
                payload['resume_text'] = resume_text_db
        if upload.get('media_type') == 'resume' and (resume_text_db or '').strip():
            rt = (resume_text_db or '').strip()
            struct = structured_profile_from_resume_text(rt)

            def _exp_blank(e):
                if not isinstance(e, dict):
                    return True
                return not any(str(e.get(k) or '').strip() for k in ('title', 'company', 'description', 'start_year', 'end_year'))

            try:
                exp_list = json.loads(experience_json) if experience_json else []
            except Exception:
                exp_list = []
            try:
                skills_list = json.loads(skills_json) if skills_json else []
            except Exception:
                skills_list = []

            if not str(about_text).strip() and (struct.get('about_summary') or '').strip():
                about_text = struct['about_summary'].strip()[:8000]
                payload['about_summary'] = about_text

            inferred_exp = struct.get('experience') or []
            if inferred_exp and (not exp_list or all(_exp_blank(e) for e in exp_list)):
                experience_json = json.dumps(inferred_exp)
                payload['experience'] = inferred_exp
            elif not exp_list or all(_exp_blank(e) for e in exp_list):
                experience_json = json.dumps(
                    [
                        {
                            'title': '',
                            'company': '',
                            'location': '',
                            'employment_type': '',
                            'start_month': '',
                            'start_year': '',
                            'end_month': '',
                            'end_year': '',
                            'is_current': False,
                            'description': rt[:12000],
                        }
                    ]
                )
                payload['experience'] = json.loads(experience_json)

            if not skills_list:
                merged_skills = merge_skills_from_resume(rt, [], limit=24)
                if merged_skills:
                    skills_json = json.dumps(merged_skills)
                    payload['skills'] = merged_skills
        try:
            execute(
                """
                UPDATE members SET payload_json=:payload_json, profile_photo_url=:profile_photo_url, resume_url=:resume_url,
                resume_text=:resume_text, about_text=:about_text, experience_json=:experience_json, skills_json=:skills_json
                WHERE member_id=:member_id
                """,
                {
                    'member_id': member_id,
                    'payload_json': json.dumps(payload),
                    'profile_photo_url': profile_photo_url,
                    'resume_url': resume_url,
                    'resume_text': resume_text_db,
                    'about_text': about_text,
                    'experience_json': experience_json if isinstance(experience_json, str) else json.dumps(experience_json),
                    'skills_json': skills_json if isinstance(skills_json, str) else json.dumps(skills_json),
                },
            )
            delete_key(f'member:pending:update:{member_id}')
            log_event(self.logger, 'member_media_upload_member_updated', upload_id=upload.get('upload_id'), member_id=member_id, media_type=upload.get('media_type'), profile_photo_url_length=len(profile_photo_url), resume_url_length=len(resume_url), resume_text_length=len(resume_text_db or ''))
        except Exception as exc:
            log_event(self.logger, 'member_media_upload_member_update_failed', upload_id=upload.get('upload_id'), member_id=member_id, media_type=upload.get('media_type'), profile_photo_url_length=len(profile_photo_url), resume_url_length=len(resume_url), error=str(exc))
            raise


_service: MediaUploadService | None = None


def get_media_upload_service() -> MediaUploadService:
    global _service
    if _service is None:
        _service = MediaUploadService()
    return _service
