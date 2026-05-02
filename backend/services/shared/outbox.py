from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from services.shared.common import utc_now
from services.shared.relational import fetch_all, fetch_one, execute
from services.shared.document_store import find_many, insert_one, update_one
from services.shared.kafka_bus import publish_event


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime('%Y-%m-%d %H:%M:%S')


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


class RelationalOutboxRepository:
    def enqueue(self, *, topic: str, event: dict[str, Any], aggregate_type: str, aggregate_id: str) -> dict[str, Any]:
        row = {
            'outbox_id': f'out_{uuid4().hex[:12]}',
            'topic': topic,
            'event_type': event.get('event_type', topic),
            'aggregate_type': aggregate_type,
            'aggregate_id': aggregate_id,
            'payload_json': __import__('json').dumps(event, sort_keys=True, default=str),
            'trace_id': event.get('trace_id'),
            'idempotency_key': event.get('idempotency_key') or f'{topic}:{aggregate_id}',
            'status': 'pending',
            'attempts': 0,
            'error_message': None,
            'available_at': _now(),
        }
        execute(
            """
            INSERT IGNORE INTO outbox_events (outbox_id, topic, event_type, aggregate_type, aggregate_id, payload_json, trace_id, idempotency_key, status, attempts, error_message, available_at)
            VALUES (:outbox_id, :topic, :event_type, :aggregate_type, :aggregate_id, :payload_json, :trace_id, :idempotency_key, :status, :attempts, :error_message, :available_at)
            """,
            row,
        )
        existing = fetch_one('SELECT * FROM outbox_events WHERE idempotency_key = :idempotency_key', {'idempotency_key': row['idempotency_key']})
        return existing or row

    def pending(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = fetch_all(
            'SELECT * FROM outbox_events WHERE status IN (\'pending\', \'failed\') ORDER BY created_at ASC LIMIT :limit',
            {'limit': limit},
        )
        import json
        for row in rows:
            row['payload'] = json.loads(row.get('payload_json') or '{}')
        return rows

    def mark_published(self, outbox_id: str) -> None:
        execute('UPDATE outbox_events SET status = :status, published_at = :published_at, error_message = :error_message WHERE outbox_id = :outbox_id', {'status': 'published', 'published_at': _now(), 'error_message': None, 'outbox_id': outbox_id})

    def mark_failed(self, outbox_id: str, error_message: str) -> None:
        execute('UPDATE outbox_events SET status = :status, attempts = attempts + 1, error_message = :error_message WHERE outbox_id = :outbox_id', {'status': 'failed', 'error_message': error_message[:500], 'outbox_id': outbox_id})


class DocumentOutboxRepository:
    collection = 'outbox_events'

    def enqueue(self, *, topic: str, event: dict[str, Any], aggregate_type: str, aggregate_id: str) -> dict[str, Any]:
        idempotency_key = event.get('idempotency_key') or f'{topic}:{aggregate_id}'
        existing = find_many(self.collection, {'idempotency_key': idempotency_key})
        if existing:
            return existing[0]
        row = {
            'outbox_id': f'out_{uuid4().hex[:12]}',
            'topic': topic,
            'event_type': event.get('event_type', topic),
            'aggregate_type': aggregate_type,
            'aggregate_id': aggregate_id,
            'payload': event,
            'trace_id': event.get('trace_id'),
            'idempotency_key': idempotency_key,
            'status': 'pending',
            'attempts': 0,
            'error_message': None,
            'created_at': _iso_now(),
        }
        insert_one(self.collection, row)
        return row

    def pending(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = [r for r in find_many(self.collection, sort=[('created_at', 1)]) if r.get('status') in {'pending', 'failed'}]
        return rows[:limit]

    def mark_published(self, outbox_id: str) -> None:
        update_one(self.collection, {'outbox_id': outbox_id}, {'status': 'published', 'published_at': _iso_now(), 'error_message': None})

    def mark_failed(self, outbox_id: str, error_message: str) -> None:
        rows = find_many(self.collection, {'outbox_id': outbox_id})
        attempts = (rows[0].get('attempts', 0) if rows else 0) + 1
        update_one(self.collection, {'outbox_id': outbox_id}, {'status': 'failed', 'attempts': attempts, 'error_message': error_message[:500]})


async def dispatch_outbox_forever(repo: Any, stop_event: asyncio.Event, poll_seconds: float = 0.2) -> None:
    while not stop_event.is_set():
        rows = []
        try:
            rows = repo.pending(50)
            for row in rows:
                ok = await publish_event(row['topic'], row.get('payload') or row.get('payload_json') or {})
                if ok:
                    repo.mark_published(row['outbox_id'])
                else:
                    repo.mark_failed(row['outbox_id'], 'publish_failed')
        except Exception as exc:
            for row in rows:
                try:
                    repo.mark_failed(row['outbox_id'], str(exc))
                except Exception:
                    pass
        await asyncio.sleep(poll_seconds)

