from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from services.shared.document_store import find_one, insert_one, replace_one
from services.shared.kafka_bus import consume_forever
from services.shared.notifications import create_notification
from services.shared.observability import get_logger, log_event
from services.shared.relational import execute, fetch_one

_PROCESSED_COLLECTION = 'member_event_consumed'
_CONNECTION_EVENTS_COLLECTION = 'member_connection_events'
_MESSAGE_INBOX_COLLECTION = 'member_message_inbox'


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


class MemberEventProjectionService:
    """Owns member-facing projections derived from Kafka events.

    Transactional sources of truth stay with producing services:
    - messages / threads / connection requests / connection edges in messaging_connections_service (Mongo)
    - member master data in member_profile_service (MySQL)

    This service builds member-facing read models and notifications:
    - notifications (Mongo)
    - member_connection_events projection (Mongo)
    - member_message_inbox projection (Mongo)
    - connections_count on members (MySQL) for accepted connections
    """

    def __init__(self) -> None:
        self.stop_event = asyncio.Event()
        self.tasks: list[asyncio.Task] = []
        self.logger = get_logger('member_profile_service')

    async def startup(self) -> None:
        if self.tasks:
            return
        topics = [
            'connection.requested', 'connection.accepted', 'connection.rejected', 'connection.withdrawn',
            'message.sent',
            'application.submitted', 'application.status.updated',
        ]
        self.tasks.append(asyncio.create_task(consume_forever(topics, 'member-profile-projections', self.process_event, self.stop_event)))
        log_event(self.logger, 'member_event_projection_startup', topics=topics, consumer_group='member-profile-projections')

    async def shutdown(self) -> None:
        self.stop_event.set()
        for task in self.tasks:
            task.cancel()
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks.clear()
        self.stop_event = asyncio.Event()
        log_event(self.logger, 'member_event_projection_stopped')

    def _processed(self, idempotency_key: str) -> bool:
        return bool(find_one(_PROCESSED_COLLECTION, {'idempotency_key': idempotency_key}))

    def _mark_processed(self, idempotency_key: str, topic: str, entity_id: str) -> None:
        insert_one(_PROCESSED_COLLECTION, {
            'idempotency_key': idempotency_key,
            'topic': topic,
            'entity_id': entity_id,
            'processed_at': _now_iso(),
        })

    def _resolve_identity(self, user_id: str) -> dict[str, Any]:
        member_row = fetch_one(
            'SELECT member_id, first_name, last_name, headline, profile_photo_url, email FROM members WHERE member_id=:member_id',
            {'member_id': user_id},
        )
        if member_row:
            full_name = f"{member_row.get('first_name') or ''} {member_row.get('last_name') or ''}".strip()
            return {
                'display_name': full_name or member_row.get('email') or user_id,
                'headline': member_row.get('headline') or '',
                'profile_photo_url': member_row.get('profile_photo_url') or '',
                'profile_url': f'/profile/{user_id}',
            }
        recruiter_row = fetch_one(
            'SELECT recruiter_id, name, email, access_level FROM recruiters WHERE recruiter_id=:recruiter_id',
            {'recruiter_id': user_id},
        )
        if recruiter_row:
            return {
                'display_name': recruiter_row.get('name') or recruiter_row.get('email') or user_id,
                'headline': recruiter_row.get('access_level') or 'Recruiter',
                'profile_photo_url': '',
                'profile_url': f'/profile/{user_id}',
            }
        return {'display_name': user_id, 'headline': '', 'profile_photo_url': '', 'profile_url': f'/profile/{user_id}'}

    def _upsert_connection_projection(self, event_type: str, payload: dict[str, Any], actor_id: str) -> None:
        request_id = payload.get('request_id') or payload.get('connection_id') or payload.get('entity_id')
        requester_id = payload.get('requester_id')
        receiver_id = payload.get('receiver_id')
        doc = {
            'request_id': request_id,
            'requester_id': requester_id,
            'receiver_id': receiver_id,
            'status': event_type.split('.')[-1],
            'actor_id': actor_id,
            'updated_at': _now_iso(),
        }
        existing = find_one(_CONNECTION_EVENTS_COLLECTION, {'request_id': request_id}) or {}
        replace_one(_CONNECTION_EVENTS_COLLECTION, {'request_id': request_id}, {**existing, **doc}, upsert=True)

    def _increment_connection_counts(self, requester_id: str | None, receiver_id: str | None) -> None:
        if requester_id:
            execute('UPDATE members SET connections_count = COALESCE(connections_count, 0) + 1 WHERE member_id=:member_id', {'member_id': requester_id})
        if receiver_id:
            execute('UPDATE members SET connections_count = COALESCE(connections_count, 0) + 1 WHERE member_id=:member_id', {'member_id': receiver_id})

    def _upsert_message_inbox(self, payload: dict[str, Any]) -> None:
        thread_id = payload.get('thread_id')
        receiver_id = payload.get('receiver_id')
        sender_id = payload.get('sender_id')
        if not thread_id or not receiver_id:
            return
        existing = find_one(_MESSAGE_INBOX_COLLECTION, {'member_id': receiver_id, 'thread_id': thread_id}) or {
            'member_id': receiver_id,
            'thread_id': thread_id,
            'unread_count': 0,
            'created_at': _now_iso(),
        }
        sender_ident = self._resolve_identity(sender_id or '') if sender_id else {'display_name': sender_id or ''}
        unread_count = int(existing.get('unread_count') or 0) + 1
        updated = {
            **existing,
            'member_id': receiver_id,
            'thread_id': thread_id,
            'latest_message_id': payload.get('message_id'),
            'latest_message_text': payload.get('text') or '',
            'latest_sender_id': sender_id,
            'latest_sender_name': sender_ident.get('display_name') or sender_id,
            'unread_count': unread_count,
            'updated_at': _now_iso(),
        }
        replace_one(_MESSAGE_INBOX_COLLECTION, {'member_id': receiver_id, 'thread_id': thread_id}, updated, upsert=True)

    async def process_event(self, topic: str, event: dict[str, Any]) -> None:
        payload = event.get('payload') or {}
        actor_id = event.get('actor_id') or ''
        entity_id = (event.get('entity') or {}).get('entity_id') or payload.get('request_id') or payload.get('message_id') or ''
        idempotency_key = event.get('idempotency_key') or f'{topic}:{entity_id}'
        if self._processed(idempotency_key):
            log_event(self.logger, 'member_event_projection_skip_duplicate', topic=topic, idempotency_key=idempotency_key, entity_id=entity_id)
            return

        log_event(self.logger, 'member_event_projection_received', topic=topic, idempotency_key=idempotency_key, entity_id=entity_id)

        if topic == 'connection.requested':
            self._upsert_connection_projection(topic, payload, actor_id)
            receiver_id = payload.get('receiver_id')
            requester_id = payload.get('requester_id')
            requester_ident = self._resolve_identity(requester_id or '')
            if receiver_id:
                create_notification(
                    receiver_id,
                    'connection.requested',
                    'New connection request',
                    f"{requester_ident.get('display_name') or requester_id} sent you a connection request.",
                    actor_id=requester_id,
                    actor_name=requester_ident.get('display_name') or requester_id,
                    target_url='/connections',
                    data={'request_id': payload.get('request_id'), 'requester_id': requester_id, 'receiver_id': receiver_id},
                )
        elif topic == 'connection.accepted':
            self._upsert_connection_projection(topic, payload, actor_id)
            requester_id = payload.get('requester_id')
            receiver_id = payload.get('receiver_id')
            self._increment_connection_counts(requester_id, receiver_id)
            receiver_ident = self._resolve_identity(receiver_id or '')
            if requester_id:
                create_notification(
                    requester_id,
                    'connection.accepted',
                    'Connection request accepted',
                    f"{receiver_ident.get('display_name') or receiver_id} accepted your connection request.",
                    actor_id=receiver_id,
                    actor_name=receiver_ident.get('display_name') or receiver_id,
                    target_url=receiver_ident.get('profile_url') or f'/profile/{receiver_id}',
                    data={'request_id': payload.get('request_id'), 'requester_id': requester_id, 'receiver_id': receiver_id},
                )
        elif topic == 'connection.rejected':
            self._upsert_connection_projection(topic, payload, actor_id)
            requester_id = payload.get('requester_id')
            receiver_id = payload.get('receiver_id')
            receiver_ident = self._resolve_identity(receiver_id or '')
            if requester_id:
                create_notification(
                    requester_id,
                    'connection.rejected',
                    'Connection request declined',
                    f"{receiver_ident.get('display_name') or receiver_id} declined your connection request.",
                    actor_id=receiver_id,
                    actor_name=receiver_ident.get('display_name') or receiver_id,
                    target_url='/connections',
                    data={'request_id': payload.get('request_id')},
                )
        elif topic == 'connection.withdrawn':
            self._upsert_connection_projection(topic, payload, actor_id)
        elif topic == 'application.submitted':
            member_id = payload.get('member_id')
            job_id = payload.get('job_id')
            if member_id:
                job_row = fetch_one(
                    'SELECT title, recruiter_id FROM jobs WHERE job_id=:job_id',
                    {'job_id': job_id},
                ) if job_id else None
                job_title = (job_row.get('title') if job_row else None) or job_id or 'the role'
                create_notification(
                    member_id,
                    'application.submitted',
                    'Application submitted',
                    f"Your application for {job_title} was successfully submitted.",
                    actor_id=member_id,
                    actor_name='',
                    target_url='/applications',
                    data={'job_id': job_id, 'application_id': entity_id},
                )
        elif topic == 'application.status.updated':
            member_id = payload.get('member_id')
            job_id = payload.get('job_id')
            new_status = payload.get('status') or ''
            if member_id and new_status:
                job_row = fetch_one(
                    'SELECT title FROM jobs WHERE job_id=:job_id',
                    {'job_id': job_id},
                ) if job_id else None
                job_title = (job_row.get('title') if job_row else None) or job_id or 'your application'
                create_notification(
                    member_id,
                    'application.status.updated',
                    'Application status updated',
                    f"Your application for {job_title} is now {new_status.replace('_', ' ')}.",
                    actor_id=actor_id,
                    actor_name='',
                    target_url='/applications',
                    data={'job_id': job_id, 'application_id': entity_id, 'status': new_status},
                )
        elif topic == 'message.sent':
            receiver_id = payload.get('receiver_id')
            sender_id = payload.get('sender_id')
            thread_id = payload.get('thread_id')
            self._upsert_message_inbox(payload)
            sender_ident = self._resolve_identity(sender_id or '')
            if receiver_id and sender_id and receiver_id != sender_id:
                create_notification(
                    receiver_id,
                    'message.sent',
                    'New message',
                    f"{sender_ident.get('display_name') or sender_id} sent you a message.",
                    actor_id=sender_id,
                    actor_name=sender_ident.get('display_name') or sender_id,
                    target_url=f'/messages?thread={thread_id}' if thread_id else '/messages',
                    data={'thread_id': thread_id, 'message_id': payload.get('message_id'), 'sender_id': sender_id},
                )

        self._mark_processed(idempotency_key, topic, entity_id)
        log_event(self.logger, 'member_event_projection_applied', topic=topic, idempotency_key=idempotency_key, entity_id=entity_id)


_service: MemberEventProjectionService | None = None


def get_member_event_projection_service() -> MemberEventProjectionService:
    global _service
    if _service is None:
        _service = MemberEventProjectionService()
    return _service
