from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from services.shared.cache import delete_key, delete_pattern, get_json, set_json
from services.shared.common import body_hash, build_event, fail, require_auth, success
from services.shared.kafka_bus import publish_event
from services.shared.outbox import RelationalOutboxRepository, dispatch_outbox_forever
from services.shared.repositories import RecruiterRepository


class JobsService:
    TTL_JOB_DETAIL = 120
    TTL_JOB_SEARCH = 90
    TTL_RECRUITER_LIST = 90
    TTL_MEMBER_SAVED = 60
    TTL_PENDING = 300

    def __init__(self, repo):
        self.repo = repo
        self.recruiters = RecruiterRepository()
        self.outbox = RelationalOutboxRepository()
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

    def _detail_key(self, job_id: str) -> str:
        return f'job:detail:{job_id}'

    def _pending_detail_key(self, job_id: str) -> str:
        return f'job:pending:detail:{job_id}'

    def _pending_recruiter_key(self, recruiter_id: str) -> str:
        return f'jobs:pending:recruiter:{recruiter_id}'

    def _pending_saved_key(self, member_id: str) -> str:
        return f'jobs:pending:saved:{member_id}'

    def _invalidate_job_cache(self, job_id=None, recruiter_id=None, member_id=None):
        if job_id:
            delete_pattern(self._detail_key(job_id))
            delete_pattern(self._pending_detail_key(job_id))
        delete_pattern('jobs:search:*')
        if recruiter_id:
            delete_pattern(f'jobs:recruiter:{recruiter_id}:*')
        if member_id:
            delete_pattern(f'jobs:saved:{member_id}:*')

    def _set_pending_recruiter_job(self, recruiter_id: str, job: dict, operation: str) -> None:
        state = get_json(self._pending_recruiter_key(recruiter_id)) or {}
        state[job['job_id']] = {'job': job, 'operation': operation, 'updated_at': datetime.now(timezone.utc).isoformat()}
        set_json(self._pending_recruiter_key(recruiter_id), state, self.TTL_PENDING)

    def _set_pending_saved_state(self, member_id: str, job_id: str, is_saved: bool, job_snapshot: dict | None = None) -> None:
        state = get_json(self._pending_saved_key(member_id)) or {}
        entry = {'is_saved': bool(is_saved), 'updated_at': datetime.now(timezone.utc).isoformat()}
        if job_snapshot:
            entry['job_snapshot'] = job_snapshot
        elif state.get(job_id, {}).get('job_snapshot'):
            entry['job_snapshot'] = state[job_id]['job_snapshot']
        state[job_id] = entry
        set_json(self._pending_saved_key(member_id), state, self.TTL_PENDING)

    def _apply_saved_overlay(self, items: list[dict], member_id: str | None) -> list[dict]:
        if not member_id:
            return items
        pending = get_json(self._pending_saved_key(member_id)) or {}
        saved_ids = set(self.repo.saved_job_ids_for_member(member_id))
        for job_id, marker in pending.items():
            if bool(marker.get('is_saved')):
                saved_ids.add(job_id)
            else:
                saved_ids.discard(job_id)
        shaped = []
        for item in items:
            updated = dict(item)
            updated['is_saved'] = updated.get('job_id') in saved_ids
            shaped.append(updated)
        return shaped

    def _merge_pending_recruiter_jobs(self, recruiter_id: str, items: list[dict]) -> list[dict]:
        pending = get_json(self._pending_recruiter_key(recruiter_id)) or {}
        merged = {item['job_id']: dict(item) for item in items if item.get('job_id')}
        for job_id, entry in pending.items():
            job = dict(entry.get('job') or {})
            operation = entry.get('operation')
            if operation == 'close':
                job['status'] = 'closed'
            merged[job_id] = {**merged.get(job_id, {}), **job}
        return list(merged.values())

    async def create_job(self, payload, authorization, trc):
        try:
            actor = require_auth(authorization)
        except Exception:
            return fail('auth_required', 'Missing, expired, or invalid bearer token.', trc, status_code=401)
        if actor['role'] not in {'recruiter', 'admin'}:
            return fail('forbidden', 'Recruiter role required.', trc, status_code=403)

        recruiter_id = actor['sub'] if actor['role'] != 'admin' else (payload.get('recruiter_id') or actor['sub'])
        recruiter = self.recruiters.get_recruiter(recruiter_id)
        if not recruiter:
            return fail('recruiter_not_found', 'Recruiter profile not found for the signed-in user.', trc, status_code=404)

        normalized = dict(payload)
        normalized['recruiter_id'] = recruiter_id
        normalized['company_id'] = recruiter.get('company_id')
        normalized['company_name'] = recruiter.get('company_name') or payload.get('company_name') or ''
        if payload.get('city') or payload.get('state'):
            normalized['location'] = ', '.join([v for v in [payload.get('city'), payload.get('state')] if v])
        if normalized.get('title'):
            existing = self.repo.find_duplicate_open(recruiter_id, normalized.get('title'))
            if existing:
                return fail('duplicate_job', 'A matching open job already exists for this recruiter.', trc, status_code=409)
        job_id = normalized.get('job_id') or f'job_{uuid4().hex[:8]}'
        pending_job = {
            **normalized,
            'job_id': job_id,
            'status': normalized.get('status', 'open'),
            'version': 1,
            'created_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        }
        set_json(self._pending_detail_key(job_id), pending_job, self.TTL_PENDING)
        set_json(self._detail_key(job_id), pending_job, self.TTL_PENDING)
        self._set_pending_recruiter_job(recruiter_id, pending_job, 'create')
        self._invalidate_job_cache(None, recruiter_id)
        published = await publish_event('job.create.requested', build_event(event_type='job.create.requested', actor_id=actor['sub'], entity_type='job', entity_id=job_id, payload={'job': pending_job}, trace=trc, idempotency_key=f'job.create.requested:{job_id}'))
        if not published:
            return fail('kafka_publish_failed', 'Failed to queue job posting command.', trc, status_code=503)
        return success({'job_id': job_id, 'status': pending_job['status'], 'recruiter_id': recruiter_id}, trc, {'write_state': 'pending', 'dispatch': 'kafka'})

    def get_job(self, payload, authorization, trc):
        try:
            actor = require_auth(authorization)
        except Exception:
            return fail('auth_required', 'Missing, expired, or invalid bearer token.', trc, status_code=401)
        job_id = payload.get('job_id')
        pending = get_json(self._pending_detail_key(job_id))
        cache_key = self._detail_key(job_id)
        cached = get_json(cache_key)
        cache_status = 'hit' if (pending or cached) else 'miss'
        job = pending or cached or self.repo.get(job_id)
        if job and not (pending or cached):
            set_json(cache_key, job, self.TTL_JOB_DETAIL)
        if not job:
            return fail('not_found', 'Job posting does not exist.', trc, status_code=404)
        viewer_id = payload.get('viewer_id') or actor['sub']
        event = build_event(event_type='job.viewed', actor_id=viewer_id, entity_type='job', entity_id=job['job_id'], payload={'job_id': job['job_id']}, trace=trc, idempotency_key=f'view:{viewer_id}:{job["job_id"]}:{trc}')
        self.outbox.enqueue(topic='job.viewed', event=event, aggregate_type='job', aggregate_id=job['job_id'])
        if actor.get('role') == 'member':
            pending_saved = get_json(self._pending_saved_key(actor['sub'])) or {}
            is_saved = self.repo.is_saved_by_member(job['job_id'], actor['sub'])
            if job['job_id'] in pending_saved:
                is_saved = bool((pending_saved.get(job['job_id']) or {}).get('is_saved'))
            job = {**job, 'is_saved': is_saved}
        return success({'job': job}, trc, {'cache': cache_status, 'write_state': 'pending' if pending else 'committed'})

    async def update_job(self, payload, authorization, trc):
        try:
            actor = require_auth(authorization)
        except Exception:
            return fail('auth_required', 'Missing, expired, or invalid bearer token.', trc, status_code=401)
        current = self.repo.get(payload.get('job_id')) or get_json(self._pending_detail_key(payload.get('job_id')))
        if not current:
            return fail('not_found', 'Requested entity does not exist.', trc, status_code=404)
        if actor['role'] != 'admin' and actor['sub'] != current.get('recruiter_id'):
            return fail('forbidden', 'Only the owning recruiter or admin can update this job.', trc, status_code=403)
        if current.get('status') == 'closed':
            return fail('job_closed', 'Attempted update is incompatible with current closed status.', trc, status_code=409)
        next_job = {**current, **{k: v for k, v in payload.items() if k not in {'job_id', 'expected_version'}}, 'job_id': current['job_id'], 'version': int(current.get('version') or 1) + 1}
        set_json(self._pending_detail_key(next_job['job_id']), next_job, self.TTL_PENDING)
        set_json(self._detail_key(next_job['job_id']), next_job, self.TTL_PENDING)
        self._set_pending_recruiter_job(next_job.get('recruiter_id'), next_job, 'update')
        self._invalidate_job_cache(None, next_job.get('recruiter_id'))
        published = await publish_event('job.update.requested', build_event(event_type='job.update.requested', actor_id=actor['sub'], entity_type='job', entity_id=next_job['job_id'], payload={'job': next_job, 'expected_version': current.get('version')}, trace=trc, idempotency_key=f'job.update.requested:{next_job["job_id"]}:{next_job.get("version")}'))
        if not published:
            return fail('kafka_publish_failed', 'Failed to queue job update command.', trc, status_code=503)
        return success({'job_id': next_job['job_id'], 'updated': True, 'version': next_job['version']}, trc, {'write_state': 'pending', 'dispatch': 'kafka'})

    def search_jobs(self, payload, authorization, trc):
        try:
            actor = require_auth(authorization)
        except Exception:
            return fail('auth_required', 'Missing, expired, or invalid bearer token.', trc, status_code=401)
        cache_key = f"jobs:search:{actor.get('sub')}:{body_hash(payload)}"
        cached = get_json(cache_key)
        if cached:
            body = dict(cached['data'])
            if actor.get('role') == 'member':
                body['items'] = self._apply_saved_overlay(body.get('items', []), actor.get('sub'))
            return success(body, trc, {**cached['meta'], 'cache': 'hit'})
        keyword = (payload.get('keyword') or '').lower()
        location = (payload.get('location') or '').lower()
        employment_type = payload.get('employment_type')
        work_mode = payload.get('work_mode')
        remote = payload.get('remote')
        items = []
        for job in self.repo.search():
            text = " ".join([
                str(job.get('title', '')),
                str(job.get('description', '')),
                str(job.get('description_text', '')),
                str(job.get('company_name', '')),
                str(job.get('location', '')),
                str(job.get('city', '')),
                str(job.get('state', '')),
            ]).lower()
            if keyword and keyword not in text:
                continue
            if location and location not in text:
                continue
            if employment_type and employment_type != job.get('employment_type'):
                continue
            if work_mode and work_mode != job.get('work_mode'):
                continue
            if remote is True and job.get('work_mode') != 'remote':
                continue
            display_location = job.get('location') or ', '.join([v for v in [job.get('city'), job.get('state')] if v])
            items.append({
                'job_id': job['job_id'],
                'title': job.get('title', ''),
                'company_name': job.get('company_name', 'Northstar Labs'),
                'location': display_location,
                'city': job.get('city'),
                'state': job.get('state'),
                'status': job.get('status', 'open'),
                'work_mode': job.get('work_mode'),
                'employment_type': job.get('employment_type'),
                'applicants_count': job.get('applicants_count', 0),
                'posted_at': job.get('posted_at') or job.get('created_at'),
            })
        if actor.get('role') == 'member':
            items = self._apply_saved_overlay(items, actor.get('sub'))
        items.sort(key=lambda j: (j.get('status') != 'open', j.get('title') or ''))
        page = int(payload.get('page', 1))
        page_size = int(payload.get('page_size', 10))
        start = (page - 1) * page_size
        body = {'items': items[start:start + page_size]}
        meta = {'page': page, 'page_size': page_size, 'total': len(items), 'cache': 'miss'}
        set_json(cache_key, {'data': body, 'meta': meta}, self.TTL_JOB_SEARCH)
        return success(body, trc, meta)

    async def close_job(self, payload, authorization, trc):
        try:
            actor = require_auth(authorization)
        except Exception:
            return fail('auth_required', 'Missing, expired, or invalid bearer token.', trc, status_code=401)
        current = self.repo.get(payload.get('job_id')) or get_json(self._pending_detail_key(payload.get('job_id')))
        if not current:
            return fail('not_found', 'Requested entity does not exist.', trc, status_code=404)
        if actor['role'] != 'admin' and actor['sub'] != current.get('recruiter_id'):
            return fail('forbidden', 'Only the owning recruiter or admin can close this job.', trc, status_code=403)
        next_job = {**current, 'status': 'closed', 'version': int(current.get('version') or 1) + 1}
        set_json(self._pending_detail_key(next_job['job_id']), next_job, self.TTL_PENDING)
        set_json(self._detail_key(next_job['job_id']), next_job, self.TTL_PENDING)
        self._set_pending_recruiter_job(next_job.get('recruiter_id'), next_job, 'close')
        self._invalidate_job_cache(None, next_job.get('recruiter_id'))
        published = await publish_event('job.close.requested', build_event(event_type='job.close.requested', actor_id=actor['sub'], entity_type='job', entity_id=next_job['job_id'], payload={'job_id': next_job['job_id'], 'recruiter_id': next_job.get('recruiter_id'), 'reason': payload.get('reason')}, trace=trc, idempotency_key=f'job.close.requested:{next_job["job_id"]}:{next_job.get("version")}'))
        if not published:
            return fail('kafka_publish_failed', 'Failed to queue job close command.', trc, status_code=503)
        return success({'job_id': payload['job_id'], 'status': 'closed'}, trc, {'write_state': 'pending', 'dispatch': 'kafka'})

    def jobs_by_recruiter(self, payload, authorization, trc):
        try:
            actor = require_auth(authorization)
        except Exception:
            return fail('auth_required', 'Missing, expired, or invalid bearer token.', trc, status_code=401)
        recruiter_id = payload.get('recruiter_id') or actor['sub']
        if actor['role'] != 'admin' and actor['sub'] != recruiter_id:
            return fail('forbidden', 'You cannot list jobs for another recruiter.', trc, status_code=403)
        status_filter = payload.get('status', 'all')
        page = int(payload.get('page', 1))
        page_size = int(payload.get('page_size', 50))
        cache_key = f'jobs:recruiter:{recruiter_id}:{status_filter}:{page}:{page_size}'
        cached = get_json(cache_key)
        if cached:
            body = dict(cached['data'])
            body['items'] = self._merge_pending_recruiter_jobs(recruiter_id, body.get('items', []))
            body['items'].sort(key=lambda j: (j.get('status') != 'open', j.get('title') or ''))
            return success(body, trc, {**cached['meta'], 'cache': 'hit'})
        items = []
        for job in self.repo.list_by_recruiter(recruiter_id, status_filter):
            items.append({
                'job_id': job['job_id'],
                'title': job.get('title', ''),
                'company_name': job.get('company_name', ''),
                'city': job.get('city'),
                'state': job.get('state'),
                'work_mode': job.get('work_mode'),
                'employment_type': job.get('employment_type'),
                'seniority_level': job.get('seniority_level'),
                'status': job.get('status', 'open'),
                'applicants_count': job.get('applicants_count', 0),
                'version': job.get('version'),
            })
        items = self._merge_pending_recruiter_jobs(recruiter_id, items)
        items.sort(key=lambda j: (j.get('status') != 'open', j.get('title') or ''))
        body = {'items': items[(page - 1) * page_size: page * page_size]}
        meta = {'total': len(items), 'page': page, 'page_size': page_size, 'cache': 'miss'}
        set_json(cache_key, {'data': body, 'meta': meta}, self.TTL_RECRUITER_LIST)
        return success(body, trc, meta)

    async def save_job(self, payload, authorization, trc):
        try:
            actor = require_auth(authorization)
        except Exception:
            return fail('auth_required', 'Missing, expired, or invalid bearer token.', trc, status_code=401)
        if actor.get('role') != 'member':
            return fail('forbidden', 'Member role only.', trc, status_code=403)
        job_id = payload.get('job_id')
        job = self.repo.get(job_id) or get_json(self._pending_detail_key(job_id))
        if not job:
            return fail('job_not_found', 'Job not found.', trc, status_code=404)
        self._set_pending_saved_state(actor['sub'], job_id, True, job_snapshot=job)
        self._invalidate_job_cache(job_id=job_id, member_id=actor['sub'])
        published = await publish_event('job.save.requested', build_event(event_type='job.save.requested', actor_id=actor['sub'], entity_type='job', entity_id=job_id, payload={'job_id': job_id, 'member_id': actor['sub']}, trace=trc, idempotency_key=f'job.save.requested:{job_id}:{actor["sub"]}'))
        if not published:
            return fail('kafka_publish_failed', 'Failed to queue save-job command.', trc, status_code=503)
        return success({'job_id': job_id, 'saved': True, 'created': True}, trc, {'write_state': 'pending', 'dispatch': 'kafka'})

    async def unsave_job(self, payload, authorization, trc):
        try:
            actor = require_auth(authorization)
        except Exception:
            return fail('auth_required', 'Missing, expired, or invalid bearer token.', trc, status_code=401)
        if actor.get('role') != 'member':
            return fail('forbidden', 'Member role only.', trc, status_code=403)
        job_id = payload.get('job_id')
        self._set_pending_saved_state(actor['sub'], job_id, False)
        self._invalidate_job_cache(job_id=job_id, member_id=actor['sub'])
        published = await publish_event('job.unsave.requested', build_event(event_type='job.unsave.requested', actor_id=actor['sub'], entity_type='job', entity_id=job_id, payload={'job_id': job_id, 'member_id': actor['sub']}, trace=trc, idempotency_key=f'job.unsave.requested:{job_id}:{actor["sub"]}'))
        if not published:
            return fail('kafka_publish_failed', 'Failed to queue unsave-job command.', trc, status_code=503)
        return success({'job_id': job_id, 'saved': False, 'removed': True}, trc, {'write_state': 'pending', 'dispatch': 'kafka'})

    def saved_jobs(self, payload, authorization, trc):
        try:
            actor = require_auth(authorization)
        except Exception:
            return fail('auth_required', 'Missing, expired, or invalid bearer token.', trc, status_code=401)
        member_id = payload.get('member_id') or actor['sub']
        if actor.get('role') != 'admin' and actor.get('sub') != member_id:
            return fail('forbidden', 'You may only view your own saved jobs.', trc, status_code=403)
        cache_key = f'jobs:saved:{member_id}:{body_hash(payload)}'
        cached = get_json(cache_key)
        if cached:
            items = cached['data'].get('items', [])
            items = self._apply_saved_overlay(items, member_id)
            items = [item for item in items if item.get('is_saved')]
            return success({'items': items}, trc, {**cached['meta'], 'cache': 'hit'})
        items = self.repo.list_saved_jobs_for_member(member_id)
        # merge pending saves that haven't been written to DB yet
        pending_saves = get_json(self._pending_saved_key(member_id)) or {}
        db_job_ids = {item.get('job_id') for item in items}
        for job_id, marker in pending_saves.items():
            if bool(marker.get('is_saved')) and job_id not in db_job_ids:
                job_detail = (marker.get('job_snapshot')
                              or get_json(self._pending_detail_key(job_id))
                              or get_json(self._detail_key(job_id)))
                if job_detail:
                    items.append({**job_detail, 'is_saved': True})
        items = self._apply_saved_overlay(items, member_id)
        items = [item for item in items if item.get('is_saved')]
        body = {'items': items}
        meta = {'total': len(items), 'cache': 'miss'}
        set_json(cache_key, {'data': body, 'meta': meta}, self.TTL_MEMBER_SAVED)
        return success(body, trc, meta)
