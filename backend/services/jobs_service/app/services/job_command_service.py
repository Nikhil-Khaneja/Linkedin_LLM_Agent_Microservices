from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from services.shared.cache import delete_key, delete_pattern, get_json, set_json
from services.shared.common import build_event
from services.shared.document_store import find_one, insert_one
from services.shared.kafka_bus import consume_forever, publish_event
from services.shared.observability import get_logger, log_event
from services.shared.relational import fetch_one
from services.shared.repositories import JobRepository

_PROCESSED_COLLECTION = 'job_write_commands'
_TOPIC_CREATE = 'job.create.requested'
_TOPIC_UPDATE = 'job.update.requested'
_TOPIC_CLOSE = 'job.close.requested'
_TOPIC_SAVE = 'job.save.requested'
_TOPIC_UNSAVE = 'job.unsave.requested'
_PENDING_TTL_SECONDS = 300


def _detail_key(job_id: str) -> str:
    return f'job:detail:{job_id}'


def _pending_detail_key(job_id: str) -> str:
    return f'job:pending:detail:{job_id}'


def _pending_recruiter_key(recruiter_id: str) -> str:
    return f'jobs:pending:recruiter:{recruiter_id}'


def _pending_saved_key(member_id: str) -> str:
    return f'jobs:pending:saved:{member_id}'


class JobCommandService:
    def __init__(self) -> None:
        self.stop_event = asyncio.Event()
        self.tasks: list[asyncio.Task] = []
        self.repo = JobRepository()
        self.logger = get_logger('jobs_service')

    async def startup(self) -> None:
        if self.tasks:
            return
        topics = [_TOPIC_CREATE, _TOPIC_UPDATE, _TOPIC_CLOSE, _TOPIC_SAVE, _TOPIC_UNSAVE]
        self.tasks.append(asyncio.create_task(consume_forever(topics, 'jobs-write-processor', self.process_event, self.stop_event)))
        log_event(self.logger, 'job_command_service_started', topics=topics, consumer_group='jobs-write-processor')

    async def shutdown(self) -> None:
        self.stop_event.set()
        for task in self.tasks:
            task.cancel()
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks.clear()
        self.stop_event = asyncio.Event()

    def _mark_processed(self, idempotency_key: str, topic: str, entity_id: str) -> None:
        insert_one(_PROCESSED_COLLECTION, {
            'idempotency_key': idempotency_key,
            'topic': topic,
            'entity_id': entity_id,
            'processed_at': datetime.now(timezone.utc).isoformat(),
        })

    def _processed(self, idempotency_key: str) -> bool:
        return bool(find_one(_PROCESSED_COLLECTION, {'idempotency_key': idempotency_key}))

    def _upsert_pending_recruiter(self, recruiter_id: str, job: dict[str, Any], operation: str) -> None:
        existing = get_json(_pending_recruiter_key(recruiter_id)) or {}
        existing[job['job_id']] = {'job': job, 'operation': operation, 'updated_at': datetime.now(timezone.utc).isoformat()}
        set_json(_pending_recruiter_key(recruiter_id), existing, _PENDING_TTL_SECONDS)

    async def process_event(self, topic: str, event: dict[str, Any]) -> None:
        payload = event.get('payload') or {}
        entity_id = (event.get('entity') or {}).get('entity_id') or payload.get('job_id') or ''
        idempotency_key = event.get('idempotency_key') or f'{topic}:{entity_id}'
        if self._processed(idempotency_key):
            log_event(self.logger, 'job_command_duplicate_skipped', topic=topic, idempotency_key=idempotency_key, entity_id=entity_id)
            return
        if topic == _TOPIC_CREATE:
            job = payload.get('job') or {}
            job_id = job.get('job_id')
            if not fetch_one("SELECT job_id FROM jobs WHERE job_id=:job_id", {"job_id": job_id}):
                self.repo.create(job)
            delete_key(_pending_detail_key(job_id))
            delete_pattern('jobs:search:*')
            delete_pattern(f'jobs:recruiter:{job.get("recruiter_id")}:*')
            set_json(_detail_key(job_id), job, _PENDING_TTL_SECONDS)
            await publish_event('job.created', build_event(event_type='job.created', actor_id=event.get('actor_id') or job.get('recruiter_id') or '', entity_type='job', entity_id=job_id, payload={'job_id': job_id, 'recruiter_id': job.get('recruiter_id')}, trace=event.get('trace_id') or 'job-create', idempotency_key=f'job.created:{idempotency_key}'))
            self._mark_processed(idempotency_key, topic, job_id)
            log_event(self.logger, 'job_create_applied', job_id=job_id, recruiter_id=job.get('recruiter_id'), idempotency_key=idempotency_key)
            return
        if topic == _TOPIC_UPDATE:
            job = payload.get('job') or {}
            job_id = job.get('job_id')
            try:
                db_row = fetch_one("SELECT payload_json FROM jobs WHERE job_id=:job_id", {"job_id": job_id})
                if not db_row:
                    self.repo.create(job)
                else:
                    current = self.repo.get(job_id) or {}
                    expected = payload.get('expected_version') or current.get('version')
                    self.repo.update(job_id, {k: v for k, v in job.items() if k != 'job_id'}, expected)
            except ValueError:
                log_event(self.logger, 'job_update_version_conflict', job_id=job_id, idempotency_key=idempotency_key)
            delete_key(_pending_detail_key(job_id))
            delete_pattern('jobs:search:*')
            delete_pattern(f'jobs:recruiter:{job.get("recruiter_id")}:*')
            set_json(_detail_key(job_id), job, _PENDING_TTL_SECONDS)
            await publish_event('job.updated', build_event(event_type='job.updated', actor_id=event.get('actor_id') or job.get('recruiter_id') or '', entity_type='job', entity_id=job_id, payload={'job_id': job_id, 'recruiter_id': job.get('recruiter_id')}, trace=event.get('trace_id') or 'job-update', idempotency_key=f'job.updated:{idempotency_key}'))
            self._mark_processed(idempotency_key, topic, job_id)
            log_event(self.logger, 'job_update_applied', job_id=job_id, recruiter_id=job.get('recruiter_id'), idempotency_key=idempotency_key)
            return
        if topic == _TOPIC_CLOSE:
            job_id = payload.get('job_id')
            current = self.repo.get(job_id) or {}
            recruiter_id = payload.get('recruiter_id') or current.get('recruiter_id')
            if not fetch_one("SELECT job_id FROM jobs WHERE job_id=:job_id", {"job_id": job_id}):
                self.repo.create({**current, 'job_id': job_id})
            if current:
                try:
                    self.repo.update(job_id, {'status': 'closed'}, current.get('version'))
                except Exception:
                    pass
            final_job = self.repo.get(job_id) or {**current, 'job_id': job_id, 'recruiter_id': recruiter_id, 'status': 'closed'}
            delete_key(_pending_detail_key(job_id))
            delete_pattern('jobs:search:*')
            delete_pattern(f'jobs:recruiter:{recruiter_id}:*')
            set_json(_detail_key(job_id), final_job, _PENDING_TTL_SECONDS)
            await publish_event('job.closed', build_event(event_type='job.closed', actor_id=event.get('actor_id') or recruiter_id or '', entity_type='job', entity_id=job_id, payload={'job_id': job_id, 'recruiter_id': recruiter_id}, trace=event.get('trace_id') or 'job-close', idempotency_key=f'job.closed:{idempotency_key}'))
            self._mark_processed(idempotency_key, topic, job_id)
            log_event(self.logger, 'job_close_applied', job_id=job_id, recruiter_id=recruiter_id, idempotency_key=idempotency_key)
            return
        if topic == _TOPIC_SAVE:
            job_id = payload.get('job_id')
            member_id = payload.get('member_id')
            created = self.repo.save_job_for_member(job_id, member_id)
            delete_pattern(f'jobs:saved:{member_id}:*')
            await publish_event('job.saved', build_event(event_type='job.saved', actor_id=member_id, entity_type='job', entity_id=job_id, payload={'job_id': job_id, 'member_id': member_id}, trace=event.get('trace_id') or 'job-save', idempotency_key=f'job.saved:{idempotency_key}'))
            self._mark_processed(idempotency_key, topic, job_id)
            log_event(self.logger, 'job_save_applied', job_id=job_id, member_id=member_id, created=bool(created), idempotency_key=idempotency_key)
            return
        if topic == _TOPIC_UNSAVE:
            job_id = payload.get('job_id')
            member_id = payload.get('member_id')
            removed = self.repo.unsave_job_for_member(job_id, member_id)
            delete_pattern(f'jobs:saved:{member_id}:*')
            self._mark_processed(idempotency_key, topic, job_id)
            log_event(self.logger, 'job_unsave_applied', job_id=job_id, member_id=member_id, removed=bool(removed), idempotency_key=idempotency_key)
            return


_service: JobCommandService | None = None


def get_job_command_service() -> JobCommandService:
    global _service
    if _service is None:
        _service = JobCommandService()
    return _service
