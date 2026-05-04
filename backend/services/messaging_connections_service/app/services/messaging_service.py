import asyncio
from services.shared.cache import get_int, set_int
from services.shared.common import body_hash, build_event, check_idempotency, fail, record_idempotency, require_auth, success
from services.shared.outbox import DocumentOutboxRepository, dispatch_outbox_forever

from services.shared.repositories import MemberRepository, RecruiterRepository

class MessagingConnectionsService:
    def __init__(self, repo):
        self.repo = repo
        self.member_repo = MemberRepository()
        self.recruiter_repo = RecruiterRepository()
        self.outbox = DocumentOutboxRepository()
        self.stop_event = asyncio.Event()
        self.tasks: list[asyncio.Task] = []

    async def startup(self):
        if not self.tasks:
            self.tasks.append(asyncio.create_task(dispatch_outbox_forever(self.outbox, self.stop_event)))

    async def shutdown(self):
        self.stop_event.set()
        for task in self.tasks:
            task.cancel()
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks.clear()
        self.stop_event = asyncio.Event()

    def _resolve_identity(self, user_id: str) -> dict:
        if not user_id:
            return {'display_name': 'Unknown', 'headline': '', 'profile_photo_url': ''}

        recruiter = self.recruiter_repo.get_recruiter(user_id) or {}
        member = self.member_repo.get(user_id) or {}
        company = self.recruiter_repo.get_company(recruiter.get('company_id')) if recruiter and recruiter.get('company_id') else {}

        member_name = f"{(member.get('first_name') or '').strip()} {(member.get('last_name') or '').strip()}".strip() if member else ''
        member_has_identity = bool(member_name or member.get('headline') or member.get('profile_photo_url')) if member else False

        def recruiter_identity() -> dict:
            company_name = recruiter.get('company_name') or (company or {}).get('company_name') or ''
            role_name = recruiter.get('headline') or recruiter.get('access_level') or 'Recruiter'
            headline = f"{role_name} · {company_name}" if company_name else role_name
            return {
                'display_name': recruiter.get('name') or user_id,
                'headline': headline,
                'profile_photo_url': recruiter.get('profile_photo_url') or '',
            }

        if recruiter and (str(user_id).startswith('rec_') or not member_has_identity):
            return recruiter_identity()

        if member:
            return {
                'display_name': member_name or user_id,
                'headline': member.get('headline') or '',
                'profile_photo_url': member.get('profile_photo_url') or '',
            }

        if recruiter:
            return recruiter_identity()

        return {'display_name': user_id, 'headline': '', 'profile_photo_url': ''}


    def unread_key(self, thread_id: str, user_id: str) -> str:
        return f'unread:thread:{thread_id}:{user_id}'

    def get_unread(self, thread_id: str, user_id: str) -> int:
        return int(get_int(self.unread_key(thread_id, user_id)) or 0)

    def set_unread(self, thread_id: str, user_id: str, value: int) -> None:
        set_int(self.unread_key(thread_id, user_id), max(0, int(value)), 3600)

    async def open_thread(self, payload, authorization, trc):
        try:
            actor = require_auth(authorization)
        except Exception:
            return fail('auth_required', 'Missing, expired, or invalid bearer token.', trc, status_code=401)
        participants = payload.get('participant_ids') or []
        if len(participants) != 2 or len(set(participants)) != 2:
            return fail('validation_error', 'participant_ids must contain exactly 2 distinct users.', trc, status_code=400)
        if actor['role'] != 'admin' and actor['sub'] not in participants:
            return fail('forbidden', 'You may only open threads you participate in.', trc, status_code=403)
        thread, created = self.repo.get_or_create_thread(participants)
        if created:
            self.outbox.enqueue(topic='thread.opened', event=build_event(event_type='thread.opened', actor_id=actor['sub'], entity_type='thread', entity_id=thread['thread_id'], payload={'participant_ids': participants}, trace=trc), aggregate_type='thread', aggregate_id=thread['thread_id'])
        return success({'thread_id': thread['thread_id'], 'created': created}, trc)

    def get_thread(self, payload, authorization, trc):
        try:
            actor = require_auth(authorization)
        except Exception:
            return fail('auth_required', 'Missing, expired, or invalid bearer token.', trc, status_code=401)
        body = self.repo.get_thread(payload.get('thread_id'))
        if not body:
            return fail('not_found', 'Thread not found.', trc, status_code=404)
        if actor['sub'] not in body['participant_ids'] and actor['role'] != 'admin':
            return fail('forbidden', 'Only thread participants can access this thread.', trc, status_code=403)
        body = {**body, 'unread_count': self.get_unread(body['thread_id'], actor['sub'])}
        return success({'thread': body}, trc)

    def threads_by_user(self, payload, authorization, trc):
        try:
            actor = require_auth(authorization)
        except Exception:
            return fail('auth_required', 'Missing, expired, or invalid bearer token.', trc, status_code=401)
        user_id = payload.get('user_id')
        if actor['role'] != 'admin' and actor['sub'] != user_id:
            return fail('forbidden', 'You may only list your own threads.', trc, status_code=403)
        items = []
        for thread in self.repo.list_threads_for_user(user_id):
            others = [p for p in thread.get('participant_ids', []) if p != user_id]
            other = others[0] if others else None
            ident = self._resolve_identity(other) if other else {'display_name': 'Unknown', 'headline': '', 'profile_photo_url': ''}
            items.append({'thread_id': thread['thread_id'], 'other_participant': other, 'other_display_name': ident.get('display_name'), 'other_headline': ident.get('headline'), 'other_profile_photo_url': ident.get('profile_photo_url'), 'latest_message_at': thread.get('latest_message_at'), 'unread_count': self.get_unread(thread['thread_id'], user_id)})
        return success({'items': items}, trc, {'page': payload.get('page', 1), 'page_size': payload.get('page_size', 20), 'total': len(items)})

    def list_messages(self, payload, authorization, trc):
        try:
            actor = require_auth(authorization)
        except Exception:
            return fail('auth_required', 'Missing, expired, or invalid bearer token.', trc, status_code=401)
        thread = self.repo.get_thread(payload.get('thread_id'))
        if not thread:
            return fail('not_found', 'Thread not found.', trc, status_code=404)
        if actor['sub'] not in thread['participant_ids'] and actor['role'] != 'admin':
            return fail('forbidden', 'Only thread participants can access this thread.', trc, status_code=403)
        items = sorted(self.repo.list_messages(payload.get('thread_id')), key=lambda m: m.get('sent_at') or '')
        self.set_unread(thread['thread_id'], actor['sub'], 0)
        page_size = payload.get('page_size', 20)
        return success({'items': items[:page_size]}, trc, {'next_cursor': None})

    async def send_message(self, payload, authorization, trc, idempotency_key=None):
        try:
            actor = require_auth(authorization)
        except Exception:
            return fail('auth_required', 'Missing, expired, or invalid bearer token.', trc, status_code=401)
        thread = self.repo.get_thread(payload.get('thread_id'))
        if not thread:
            return fail('not_found', 'Thread not found.', trc, status_code=404)
        if actor['sub'] not in thread['participant_ids']:
            return fail('forbidden', 'Only thread participants can send messages.', trc, status_code=403)
        route = '/messages/send'
        dedupe_key = idempotency_key or payload.get('client_message_id') or payload.get('idempotency_key')
        h = body_hash(payload)
        existing, conflict = check_idempotency(route, dedupe_key, h)
        if conflict:
            return fail('idempotency_conflict', 'Same key reused with a different payload.', trc, status_code=409)
        if existing:
            return success(existing['data'], existing['trace_id'], existing.get('meta'))
        receiver_id = [p for p in thread['participant_ids'] if p != actor['sub']][0]
        existing_msg = self.repo.get_message_by_client_id(payload['thread_id'], payload.get('client_message_id', dedupe_key))
        if existing_msg:
            return success(existing_msg, trc, {'event_dispatch': 'published'})
        try:
            row = self.repo.create_message({'thread_id': payload['thread_id'], 'sender_id': actor['sub'], 'receiver_id': receiver_id, 'text': payload.get('text', ''), 'client_message_id': payload.get('client_message_id', dedupe_key), 'delivery_state': 'sent'})
        except Exception as exc:
            return fail('message_send_failed', f'Failed to store message: {exc}', trc, retryable=True, status_code=503)
        thread['latest_message_at'] = row['sent_at']
        thread['latest_message_id'] = row['message_id']
        self.repo.save_thread(thread)
        self.set_unread(payload['thread_id'], receiver_id, self.get_unread(payload['thread_id'], receiver_id) + 1)
        self.outbox.enqueue(topic='message.sent', event=build_event(event_type='message.sent', actor_id=actor['sub'], entity_type='thread', entity_id=payload['thread_id'], payload={'message_id': row['message_id'], 'thread_id': payload['thread_id'], 'sender_id': actor['sub'], 'receiver_id': receiver_id, 'text': row['text']}, trace=trc, idempotency_key=dedupe_key), aggregate_type='thread', aggregate_id=payload['thread_id'])
        meta = {'event_dispatch': 'queued'}
        response = {'trace_id': trc, 'data': row, 'meta': meta}
        record_idempotency(route, dedupe_key, h, response)
        return success(row, trc, meta)

    async def request_connection(self, payload, authorization, trc):
        try:
            actor = require_auth(authorization)
        except Exception:
            return fail('auth_required', 'Missing, expired, or invalid bearer token.', trc, status_code=401)
        requester_id, receiver_id = payload.get('requester_id'), payload.get('receiver_id')
        if not requester_id or not receiver_id or requester_id == receiver_id:
            return fail('validation_error', 'requester_id and receiver_id are required and must be different.', trc, status_code=400)
        if actor['role'] != 'admin' and actor['sub'] != requester_id:
            return fail('forbidden', 'You can only request a connection as yourself.', trc, status_code=403)
        if self.repo.connection_exists(requester_id, receiver_id) or self.repo.pending_request_exists(requester_id, receiver_id):
            return fail('connection_conflict', 'Users are already connected or already have a pending request.', trc, status_code=409)
        req = self.repo.create_connection_request(payload)
        self.outbox.enqueue(topic='connection.requested', event=build_event(event_type='connection.requested', actor_id=actor['sub'], entity_type='connection', entity_id=req['request_id'], payload={'requester_id': requester_id, 'receiver_id': receiver_id}, trace=trc), aggregate_type='connection', aggregate_id=req['request_id'])
        return success({'request_id': req['request_id'], 'status': 'pending'}, trc, {'event_dispatch': 'queued'})

    async def accept_connection(self, payload, authorization, trc):
        try:
            actor = require_auth(authorization)
        except Exception:
            return fail('auth_required', 'Missing, expired, or invalid bearer token.', trc, status_code=401)
        req = self.repo.get_connection_request(payload.get('request_id'))
        if not req:
            return fail('not_found', 'Connection request not found.', trc, status_code=404)
        if actor['sub'] != req.get('receiver_id') and actor['role'] != 'admin':
            return fail('invalid_connection_state', 'Only the pending receiver can accept this request.', trc, status_code=403)
        req['status'] = 'accepted'
        self.repo.save_connection_request(req)
        connection = self.repo.create_connection(req['requester_id'], req['receiver_id'], req['request_id'])
        self.outbox.enqueue(topic='connection.accepted', event=build_event(event_type='connection.accepted', actor_id=actor['sub'], entity_type='connection', entity_id=connection['connection_id'], payload={'request_id': req['request_id'], 'requester_id': req['requester_id'], 'receiver_id': req['receiver_id']}, trace=trc), aggregate_type='connection', aggregate_id=connection['connection_id'])
        return success({'request_id': req['request_id'], 'status': 'accepted', 'connected': True}, trc, {'event_dispatch': 'queued'})

    async def reject_connection(self, payload, authorization, trc):
        try:
            actor = require_auth(authorization)
        except Exception:
            return fail('auth_required', 'Missing, expired, or invalid bearer token.', trc, status_code=401)
        req = self.repo.get_connection_request(payload.get('request_id'))
        if not req:
            return fail('not_found', 'Connection request not found.', trc, status_code=404)
        if actor['sub'] != req.get('receiver_id') and actor['role'] != 'admin':
            return fail('invalid_connection_state', 'Only the pending receiver can reject this request.', trc, status_code=403)
        req['status'] = 'rejected'
        self.repo.save_connection_request(req)
        self.outbox.enqueue(topic='connection.rejected', event=build_event(event_type='connection.rejected', actor_id=actor['sub'], entity_type='connection', entity_id=req['request_id'], payload={'requester_id': req['requester_id'], 'receiver_id': req['receiver_id']}, trace=trc), aggregate_type='connection', aggregate_id=req['request_id'])
        return success({'request_id': req['request_id'], 'status': 'rejected'}, trc, {'event_dispatch': 'queued'})


    async def withdraw_connection(self, payload, authorization, trc):
        try:
            actor = require_auth(authorization)
        except Exception:
            return fail('auth_required', 'Missing, expired, or invalid bearer token.', trc, status_code=401)
        req = self.repo.get_connection_request(payload.get('request_id'))
        if not req:
            return fail('not_found', 'Connection request not found.', trc, status_code=404)
        if actor['sub'] != req.get('requester_id') and actor['role'] != 'admin':
            return fail('forbidden', 'Only the requester can withdraw this request.', trc, status_code=403)
        if req.get('status') != 'pending':
            return fail('invalid_connection_state', 'Only pending requests can be withdrawn.', trc, status_code=409)
        req['status'] = 'withdrawn'
        self.repo.save_connection_request(req)
        self.outbox.enqueue(topic='connection.withdrawn', event=build_event(event_type='connection.withdrawn', actor_id=actor['sub'], entity_type='connection', entity_id=req['request_id'], payload={'requester_id': req['requester_id'], 'receiver_id': req['receiver_id']}, trace=trc), aggregate_type='connection', aggregate_id=req['request_id'])
        return success({'request_id': req['request_id'], 'status': 'withdrawn'}, trc, {'event_dispatch': 'queued'})

    async def remove_connection(self, payload, authorization, trc):
        """Either participant may remove an accepted connection (disconnect)."""
        try:
            actor = require_auth(authorization)
        except Exception:
            return fail('auth_required', 'Missing, expired, or invalid bearer token.', trc, status_code=401)
        other_id = (payload.get('other_user_id') or '').strip()
        if not other_id:
            return fail('validation_error', 'other_user_id is required.', trc, status_code=400)
        mine = actor['sub']
        if mine == other_id:
            return fail('validation_error', 'Cannot remove connection with yourself.', trc, status_code=400)
        if actor['role'] == 'admin':
            user_a = (payload.get('user_id') or mine).strip()
            deleted = self.repo.delete_connection_between(user_a, other_id)
            if not deleted:
                return fail('not_found', 'No connection with that user.', trc, status_code=404)
            return success({'other_user_id': other_id, 'removed': True}, trc, {})
        conns = [c for c in self.repo.list_connections(mine) if other_id in {c.get('user_a'), c.get('user_b')}]
        if not conns:
            return fail('not_found', 'No connection with that user.', trc, status_code=404)
        deleted = self.repo.delete_connection_between(mine, other_id)
        if not deleted:
            return fail('not_found', 'Connection could not be removed.', trc, status_code=404)
        return success({'other_user_id': other_id, 'removed': True}, trc, {})

    def sent_connections(self, payload, authorization, trc):
        try:
            actor = require_auth(authorization)
        except Exception:
            return fail('auth_required', 'Missing, expired, or invalid bearer token.', trc, status_code=401)
        user_id = payload.get('user_id') or actor.get('sub')
        if actor['role'] != 'admin' and actor['sub'] != user_id:
            return fail('forbidden', 'You may only list your own sent requests.', trc, status_code=403)
        items = []
        for req in self.repo.list_pending_requests_for_requester(user_id):
            ident = self._resolve_identity(req.get('receiver_id'))
            name = (ident.get('display_name') or '').strip()
            first_name, last_name = '', ''
            if ' ' in name:
                first_name, last_name = name.split(' ', 1)
            else:
                first_name = name
            items.append({
                'request_id': req.get('request_id'),
                'requester_id': req.get('requester_id'),
                'receiver_id': req.get('receiver_id'),
                'message': req.get('message', ''),
                'created_at': req.get('created_at'),
                'first_name': first_name,
                'last_name': last_name,
                'headline': ident.get('headline'),
                'profile_photo_url': ident.get('profile_photo_url'),
            })
        return success({'items': items}, trc, {'total': len(items)})

    def pending_connections(self, payload, authorization, trc):
        try:
            actor = require_auth(authorization)
        except Exception:
            return fail('auth_required', 'Missing, expired, or invalid bearer token.', trc, status_code=401)
        user_id = payload.get('user_id') or actor.get('sub')
        if actor['role'] != 'admin' and actor['sub'] != user_id:
            return fail('forbidden', 'You may only list your own pending requests.', trc, status_code=403)
        items = []
        for req in self.repo.list_pending_requests_for_receiver(user_id):
            ident = self._resolve_identity(req.get('requester_id'))
            name = (ident.get('display_name') or '').strip()
            first_name, last_name = '', ''
            if ' ' in name:
                first_name, last_name = name.split(' ', 1)
            else:
                first_name = name
            items.append({
                'request_id': req.get('request_id'),
                'requester_id': req.get('requester_id'),
                'receiver_id': req.get('receiver_id'),
                'message': req.get('message', ''),
                'created_at': req.get('created_at'),
                'first_name': first_name,
                'last_name': last_name,
                'headline': ident.get('headline'),
                'profile_photo_url': ident.get('profile_photo_url'),
            })
        return success({'items': items}, trc, {'total': len(items)})

    def list_connections(self, payload, authorization, trc):
        try:
            actor = require_auth(authorization)
        except Exception:
            return fail('auth_required', 'Missing, expired, or invalid bearer token.', trc, status_code=401)
        user_id = payload.get('user_id')
        if actor['role'] != 'admin' and actor['sub'] != user_id:
            return fail('forbidden', 'You may only list your own connections.', trc, status_code=403)
        items = []
        for c in self.repo.list_connections(user_id):
            other_user_id = c['user_b'] if c['user_a'] == user_id else c['user_a']
            ident = self._resolve_identity(other_user_id)
            first_name, last_name = '', ''
            if ' ' in ident.get('display_name', ''):
                first_name, last_name = ident['display_name'].split(' ', 1)
            else:
                first_name = ident.get('display_name', '')
            items.append({'connection_id': c['connection_id'], 'other_user_id': other_user_id, 'first_name': first_name, 'last_name': last_name, 'headline': ident.get('headline'), 'profile_photo_url': ident.get('profile_photo_url'), 'connected_at': c.get('connected_at')})
        return success({'items': items}, trc, {'total': len(items)})

    def mutual_connections(self, payload, authorization, trc):
        try:
            require_auth(authorization)
        except Exception:
            return fail('auth_required', 'Missing, expired, or invalid bearer token.', trc, status_code=401)
        def neighbors(user_id: str) -> set[str]:
            vals = set()
            for c in self.repo.list_connections(user_id):
                vals.add(c['user_b'] if c['user_a'] == user_id else c['user_a'])
            return vals
        mutual = sorted(neighbors(payload.get('user_id')) & neighbors(payload.get('other_id')))
        items = []
        for user_id in mutual:
            ident = self._resolve_identity(user_id)
            items.append({'user_id': user_id, 'display_name': ident.get('display_name'), 'headline': ident.get('headline'), 'profile_photo_url': ident.get('profile_photo_url')})
        return success({'items': items}, trc, {'total': len(items)})
