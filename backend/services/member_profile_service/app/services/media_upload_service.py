from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from services.shared.common import build_event, trace_id
from services.shared.document_store import find_one, replace_one, update_one
from services.shared.kafka_bus import consume_forever, publish_event
from services.shared.observability import get_logger, log_event
from services.shared.relational import execute, fetch_one
from services.shared.resume_parser import extract_text_from_bytes
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
        if upload.get('media_type') == 'profile_photo':
            profile_photo_url = upload.get('file_url') or profile_photo_url
            payload['profile_photo_url'] = profile_photo_url
        elif upload.get('media_type') == 'resume':
            resume_url = upload.get('file_url') or resume_url
            resume_text_db = resume_text or resume_text_db
            payload['resume_url'] = resume_url
            if resume_text_db:
                payload['resume_text'] = resume_text_db
        try:
            execute(
                'UPDATE members SET payload_json=:payload_json, profile_photo_url=:profile_photo_url, resume_url=:resume_url, resume_text=:resume_text WHERE member_id=:member_id',
                {
                    'member_id': member_id,
                    'payload_json': json.dumps(payload),
                    'profile_photo_url': profile_photo_url,
                    'resume_url': resume_url,
                    'resume_text': resume_text_db,
                },
            )
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
