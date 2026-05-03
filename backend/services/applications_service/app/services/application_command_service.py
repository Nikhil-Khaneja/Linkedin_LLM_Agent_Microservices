from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from services.shared.cache import delete_key
from services.shared.common import build_event
from services.shared.document_store import find_one, insert_one
from services.shared.kafka_bus import consume_forever, publish_event
from services.shared.observability import get_logger, log_event
from services.shared.repositories import ApplicationRepository

_TOPIC = 'application.submit.requested'
_PROCESSED_COLLECTION = 'application_write_commands'


def _pending_key(job_id: str, member_id: str) -> str:
    return f'application:pending:{job_id}:{member_id}'


class ApplicationCommandService:
    """Consumes application.submit.requested events and writes the application row to DB.

    This completes the Kafka-first submit flow:
      POST /applications/submit → Kafka → this consumer → DB write → application.submitted
    """

    def __init__(self) -> None:
        self.repo = ApplicationRepository()
        self.stop_event = asyncio.Event()
        self.tasks: list[asyncio.Task] = []
        self.logger = get_logger('applications_service')

    async def startup(self) -> None:
        if self.tasks:
            return
        self.tasks.append(asyncio.create_task(
            consume_forever([_TOPIC], 'applications-writer', self.process_event, self.stop_event)
        ))
        log_event(self.logger, 'application_command_service_started', topics=[_TOPIC], consumer_group='applications-writer')

    async def shutdown(self) -> None:
        self.stop_event.set()
        for task in self.tasks:
            task.cancel()
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks.clear()
        self.stop_event = asyncio.Event()
        log_event(self.logger, 'application_command_service_stopped')

    async def process_event(self, topic: str, event: dict[str, Any]) -> None:
        if topic != _TOPIC:
            return

        idempotency_key = event.get('idempotency_key') or ''
        if not idempotency_key:
            return

        if find_one(_PROCESSED_COLLECTION, {'idempotency_key': idempotency_key}):
            log_event(self.logger, 'application_command_duplicate_skipped', idempotency_key=idempotency_key)
            return

        payload = event.get('payload') or {}
        application_id = payload.get('application_id') or (event.get('entity') or {}).get('entity_id')
        job_id = payload.get('job_id')
        member_id = payload.get('member_id')
        trc = event.get('trace_id') or 'unknown'

        if not application_id or not job_id or not member_id:
            log_event(self.logger, 'application_command_invalid', idempotency_key=idempotency_key,
                      reason='missing_required_fields')
            return

        applied_at = datetime.now(timezone.utc).replace(microsecond=0).strftime('%Y-%m-%d %H:%M:%S')
        try:
            self.repo.create({
                'application_id': application_id,
                'job_id': job_id,
                'member_id': member_id,
                'resume_ref': payload.get('resume_ref'),
                'cover_letter': payload.get('cover_letter'),
                'status': 'submitted',
                'application_datetime': applied_at,
            })
        except Exception as exc:
            msg = str(exc)
            if 'Duplicate entry' in msg or '1062' in msg:
                log_event(self.logger, 'application_command_already_exists',
                          application_id=application_id, member_id=member_id, job_id=job_id)
            else:
                log_event(self.logger, 'application_command_db_error',
                          application_id=application_id, error=msg)
                raise

        insert_one(_PROCESSED_COLLECTION, {
            'idempotency_key': idempotency_key,
            'application_id': application_id,
            'processed_at': datetime.now(timezone.utc).isoformat(),
        })
        delete_key(_pending_key(job_id, member_id))

        submitted_event = build_event(
            event_type='application.submitted',
            actor_id=member_id,
            entity_type='application',
            entity_id=application_id,
            payload={
                'job_id': job_id,
                'member_id': member_id,
                'resume_ref': payload.get('resume_ref'),
                'status': 'submitted',
                'city': payload.get('city', ''),
            },
            trace=trc,
            idempotency_key=f'application.submitted:{application_id}',
        )
        await publish_event('application.submitted', submitted_event)
        log_event(self.logger, 'application_command_applied',
                  application_id=application_id, member_id=member_id, job_id=job_id)


_service: ApplicationCommandService | None = None


def get_application_command_service() -> ApplicationCommandService:
    global _service
    if _service is None:
        _service = ApplicationCommandService()
    return _service
