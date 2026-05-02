from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from services.shared.cache import delete_key, delete_pattern, set_json
from services.shared.common import build_event
from services.shared.document_store import find_one, insert_one
from services.shared.kafka_bus import consume_forever, publish_event
from services.shared.observability import get_logger, log_event
from services.shared.relational import execute, fetch_one

_TOPIC = 'member.update.requested'
_PROCESSED_COLLECTION = 'member_write_commands'
_PENDING_TTL_SECONDS = 300


def _pending_key(member_id: str) -> str:
    return f'member:pending:update:{member_id}'


def _parse_payload(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)
    try:
        return json.loads(raw or '{}')
    except Exception:
        return {}


class MemberCommandService:
    def __init__(self) -> None:
        self.stop_event = asyncio.Event()
        self.tasks: list[asyncio.Task] = []
        self.logger = get_logger('member_profile_service')

    async def startup(self) -> None:
        if self.tasks:
            return
        self.tasks.append(asyncio.create_task(consume_forever([_TOPIC], 'member-write-processor', self.process_event, self.stop_event)))
        log_event(self.logger, 'member_command_service_started', topics=[_TOPIC], consumer_group='member-write-processor')

    async def shutdown(self) -> None:
        self.stop_event.set()
        for task in self.tasks:
            task.cancel()
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks.clear()
        self.stop_event = asyncio.Event()

    async def process_event(self, topic: str, event: dict[str, Any]) -> None:
        if topic != _TOPIC:
            return
        idempotency_key = event.get('idempotency_key') or f'{topic}:{(event.get("entity") or {}).get("entity_id") or "unknown"}'
        if find_one(_PROCESSED_COLLECTION, {'idempotency_key': idempotency_key}):
            log_event(self.logger, 'member_command_duplicate_skipped', idempotency_key=idempotency_key)
            return
        payload = event.get('payload') or {}
        member_id = payload.get('member_id') or (event.get('entity') or {}).get('entity_id')
        if not member_id:
            log_event(self.logger, 'member_command_invalid', idempotency_key=idempotency_key, reason='missing_member_id')
            return
        profile = payload.get('profile') or {}
        row = fetch_one('SELECT * FROM members WHERE member_id=:member_id', {'member_id': member_id})
        if row:
            existing_payload = _parse_payload(row.get('payload_json'))
            merged = {**existing_payload, **profile}
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
                    profile_version=:profile_version,
                    is_deleted=0
                WHERE member_id=:member_id
                """,
                {
                    'member_id': member_id,
                    'email': profile.get('email') or row.get('email') or '',
                    'first_name': profile.get('first_name') or '',
                    'last_name': profile.get('last_name') or '',
                    'headline': profile.get('headline') or '',
                    'about_text': profile.get('about_summary') or profile.get('about') or '',
                    'location_text': profile.get('location') or '',
                    'payload_json': json.dumps(merged),
                    'skills_json': json.dumps(profile.get('skills') or []),
                    'experience_json': json.dumps(profile.get('experience') or []),
                    'education_json': json.dumps(profile.get('education') or []),
                    'profile_photo_url': profile.get('profile_photo_url') or '',
                    'resume_url': profile.get('resume_url') or '',
                    'resume_text': profile.get('resume_text') or '',
                    'current_company': profile.get('current_company') or '',
                    'current_title': profile.get('current_title') or '',
                    'profile_version': profile.get('profile_version') or ((row.get('profile_version') or 1) + 1),
                },
            )
        else:
            execute(
                """
                INSERT INTO members (member_id, email, first_name, last_name, headline, about_text, location_text, profile_version, is_deleted, payload_json, skills_json, experience_json, education_json, profile_photo_url, resume_url, resume_text, current_company, current_title)
                VALUES (:member_id, :email, :first_name, :last_name, :headline, :about_text, :location_text, :profile_version, 0, :payload_json, :skills_json, :experience_json, :education_json, :profile_photo_url, :resume_url, :resume_text, :current_company, :current_title)
                """,
                {
                    'member_id': member_id,
                    'email': profile.get('email') or '',
                    'first_name': profile.get('first_name') or '',
                    'last_name': profile.get('last_name') or '',
                    'headline': profile.get('headline') or '',
                    'about_text': profile.get('about_summary') or profile.get('about') or '',
                    'location_text': profile.get('location') or '',
                    'profile_version': profile.get('profile_version') or 1,
                    'payload_json': json.dumps(profile),
                    'skills_json': json.dumps(profile.get('skills') or []),
                    'experience_json': json.dumps(profile.get('experience') or []),
                    'education_json': json.dumps(profile.get('education') or []),
                    'profile_photo_url': profile.get('profile_photo_url') or '',
                    'resume_url': profile.get('resume_url') or '',
                    'resume_text': profile.get('resume_text') or '',
                    'current_company': profile.get('current_company') or '',
                    'current_title': profile.get('current_title') or '',
                },
            )
        insert_one(_PROCESSED_COLLECTION, {
            'idempotency_key': idempotency_key,
            'member_id': member_id,
            'processed_at': datetime.now(timezone.utc).isoformat(),
        })
        delete_key(_pending_key(member_id))
        delete_pattern(f'member:get:{member_id}')
        delete_pattern('members:search:*')
        set_json(f'member:get:{member_id}', {'profile': profile}, _PENDING_TTL_SECONDS)
        await publish_event('member.updated', build_event(event_type='member.updated', actor_id=event.get('actor_id') or member_id, entity_type='member', entity_id=member_id, payload={'member_id': member_id, 'profile_version': profile.get('profile_version')}, trace=event.get('trace_id') or 'member-update', idempotency_key=f'member.updated:{idempotency_key}'))
        log_event(self.logger, 'member_command_applied', member_id=member_id, idempotency_key=idempotency_key)


_service: MemberCommandService | None = None


def get_member_command_service() -> MemberCommandService:
    global _service
    if _service is None:
        _service = MemberCommandService()
    return _service
