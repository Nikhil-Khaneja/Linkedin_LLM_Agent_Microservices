import asyncio
from services.shared.cache import delete_pattern, get_json, set_json
from services.shared.common import body_hash, build_event, fail, require_auth, success
from services.shared.kafka_bus import consume_forever, publish_event
from services.shared.repositories import ApplicationRepository, JobRepository


class AnalyticsService:
    ANALYTICS_TTL = 120

    def __init__(self, repo, rollups):
        self.repo = repo
        self.rollups = rollups
        self.jobs = JobRepository()
        self.applications = ApplicationRepository()
        self.stop_event = asyncio.Event()
        self.tasks: list[asyncio.Task] = []

    def invalidate_rollup_cache(self) -> None:
        delete_pattern('analytics:*')

    async def ingest_event_payload(self, payload: dict) -> None:
        dedupe_key = payload.get('idempotency_key') or body_hash(payload)
        if self.repo.event_exists(dedupe_key):
            return
        payload['idempotency_key'] = dedupe_key
        self.repo.insert_event(payload)
        self.rollups.apply_event(payload)
        self.invalidate_rollup_cache()

    async def analytics_consumer(self, topic: str, payload: dict) -> None:
        await self.ingest_event_payload(payload)

    async def startup(self) -> None:
        if self.tasks:
            return
        topics = [
            'application.submitted', 'application.status.updated', 'application.started', 'application.note.added',
            'message.sent', 'connection.requested', 'connection.accepted', 'connection.rejected',
            'job.viewed', 'job.created', 'job.updated', 'job.closed', 'job.saved',
            'profile.viewed', 'ai.results', 'benchmark.completed'
        ]
        self.tasks.append(asyncio.create_task(consume_forever(topics, 'analytics-service', self.analytics_consumer, self.stop_event)))

    async def shutdown(self) -> None:
        self.stop_event.set()
        for task in self.tasks:
            task.cancel()
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks.clear()
        self.stop_event = asyncio.Event()

    async def ingest(self, payload, authorization, trc):
        try:
            require_auth(authorization)
        except Exception:
            return fail('auth_required', 'Missing, expired, or invalid bearer token.', trc, status_code=401)
        dedupe_key = payload.get('idempotency_key') or body_hash(payload)
        if self.repo.event_exists(dedupe_key):
            return fail('duplicate_event', 'Event already ingested for this idempotency key.', trc, {'idempotency_key': dedupe_key}, False, 409)
        payload['idempotency_key'] = dedupe_key
        event = self.repo.insert_event(payload)
        self.rollups.apply_event(payload)
        self.invalidate_rollup_cache()
        entity = payload.get('entity') or {}
        inner = payload.get('payload') or {}
        job_id = inner.get('job_id') or entity.get('entity_id')
        if payload.get('event_type') == 'job.viewed' and job_id:
            await publish_event(
                'job.viewed',
                build_event(
                    event_type='job.viewed',
                    actor_id=str(payload.get('actor_id') or 'anonymous'),
                    entity_type=str(entity.get('entity_type') or 'job'),
                    entity_id=str(entity.get('entity_id') or job_id),
                    payload=inner if inner else {'job_id': job_id},
                    trace=trc,
                    idempotency_key=dedupe_key,
                ),
            )
        await publish_event('analytics.normalized', build_event(
            event_type='analytics.normalized',
            actor_id=payload.get('actor_id') or 'analytics_service',
            entity_type=entity.get('entity_type') or payload.get('event_type', 'event'),
            entity_id=entity.get('entity_id') or event.get('event_id', ''),
            payload=payload,
            trace=trc,
            idempotency_key=f'analytics.normalized:{dedupe_key}',
        ))
        return success({'accepted': True, 'event_id': event['event_id']}, trc)

    def top_jobs(self, payload, authorization, trc):
        try:
            actor = require_auth(authorization)
        except Exception:
            return fail('auth_required', 'Missing, expired, or invalid bearer token.', trc, status_code=401)
        if actor['role'] not in {'recruiter', 'admin'}:
            return fail('forbidden', 'Recruiter/admin only.', trc, status_code=403)
        requested_recruiter_id = payload.get('recruiter_id')
        actor_sub = actor.get('sub')
        recruiter_id = requested_recruiter_id or actor_sub
        if actor.get('role') != 'admin' and recruiter_id != actor_sub:
            return fail('forbidden', 'Recruiters may only view analytics for their own jobs.', trc, status_code=403)
        cache_key = f"analytics:jobs_top:{actor_sub}:{body_hash({'metric': payload.get('metric', 'applications'), 'limit': payload.get('limit', 10), 'sort': payload.get('sort', 'desc'), 'recruiter_id': recruiter_id})}"
        cached = get_json(cache_key)
        if cached:
            return success(cached, trc, {'cache': 'hit'})
        metric = payload.get('metric', 'applications')
        sort = (payload.get('sort') or 'desc').lower()
        if sort not in {'asc', 'desc'}:
            sort = 'desc'
        rows = self.rollups.top_jobs(metric, 200, sort)
        items = []
        for row in rows:
            if not row.get('job_id'):
                continue
            job = self.jobs.get(row.get('job_id')) or {}
            if recruiter_id and job.get('recruiter_id') != recruiter_id:
                continue
            items.append({'job_id': row.get('job_id'), 'count': int(row.get('count', 0)), 'metric_value': int(row.get('count', 0)), 'title': job.get('title') or row.get('job_id'), 'company_name': job.get('company_name', '')})
        limit = max(1, int(payload.get('limit', 10)))
        items = items[:limit]
        body = {'items': items}
        set_json(cache_key, body, self.ANALYTICS_TTL)
        return success(body, trc, {'cache': 'miss'})

    def funnel(self, payload, authorization, trc):
        try:
            actor = require_auth(authorization)
        except Exception:
            return fail('auth_required', 'Missing, expired, or invalid bearer token.', trc, status_code=401)
        if actor['role'] not in {'recruiter', 'admin'}:
            return fail('forbidden', 'Recruiter/admin only.', trc, status_code=403)
        cache_key = f"analytics:funnel:{body_hash(payload)}"
        cached = get_json(cache_key)
        if cached:
            return success(cached, trc, {'cache': 'hit'})
        roll = self.rollups.funnel(payload.get('job_id'))
        body = {'funnel': {'viewed': int(roll.get('viewed', 0)), 'saved': int(roll.get('saved', 0)), 'apply_started': int(roll.get('apply_started', 0)), 'submitted': int(roll.get('submitted', 0)), 'applications': int(roll.get('submitted', 0))}}
        set_json(cache_key, body, self.ANALYTICS_TTL)
        return success(body, trc, {'cache': 'miss'})

    def geo(self, payload, authorization, trc):
        try:
            actor = require_auth(authorization)
        except Exception:
            return fail('auth_required', 'Missing, expired, or invalid bearer token.', trc, status_code=401)
        if actor['role'] not in {'recruiter', 'admin'}:
            return fail('forbidden', 'Recruiter/admin only.', trc, status_code=403)
        cache_key = f"analytics:geo:{body_hash(payload)}"
        cached = get_json(cache_key)
        if cached:
            return success(cached, trc, {'cache': 'hit'})
        key_name = 'state' if payload.get('granularity') == 'state' else 'city'
        rows = self.rollups.geo(payload.get('job_id'), key_name)
        items = [{'key': row.get('key', 'Unknown'), 'application_count': int(row.get('count', 0)), 'count': int(row.get('count', 0)), 'city': row.get('key') if key_name == 'city' else None, 'state': row.get('key') if key_name == 'state' else None} for row in rows]
        body = {'items': items, 'geo_distribution': items}
        set_json(cache_key, body, self.ANALYTICS_TTL)
        return success(body, trc, {'cache': 'miss'})

    def member_dashboard(self, payload, authorization, trc):
        try:
            actor = require_auth(authorization)
        except Exception:
            return fail('auth_required', 'Missing, expired, or invalid bearer token.', trc, status_code=401)
        member_id = payload.get('member_id')
        if actor.get('role') != 'admin' and actor.get('sub') != member_id:
            return fail('forbidden', 'You may only view your own member dashboard.', trc, status_code=403)
        cache_key = f"analytics:member_dashboard:{body_hash(payload)}"
        cached = get_json(cache_key)
        if cached:
            return success(cached, trc, {'cache': 'hit'})
        member_id = payload.get('member_id')
        body = self.rollups.member_dashboard(member_id)
        # Use current application rows so each application contributes only one (latest) status.
        latest_statuses: dict[str, int] = {}
        for app in self.applications.list_by_member(member_id):
            status = str(app.get('status') or 'submitted')
            latest_statuses[status] = int(latest_statuses.get(status, 0)) + 1
        body['application_status_breakdown'] = latest_statuses
        body['profile_views'] = [
            {'view_date': item.get('date'), 'view_count': int(item.get('count', 0))}
            for item in body.get('profile_views', [])
        ]
        body['application_status_breakdown'] = {k: int(v) for k, v in (body.get('application_status_breakdown') or {}).items()}
        body['total_profile_views'] = int(sum(int(v.get('view_count', 0)) for v in body.get('profile_views', [])))
        body['status_total'] = int(sum(int(v) for v in body.get('application_status_breakdown', {}).values()))
        set_json(cache_key, body, self.ANALYTICS_TTL)
        return success(body, trc, {'cache': 'miss'})

    async def benchmarks(self, payload, authorization, trc):
        try:
            actor = require_auth(authorization)
        except Exception:
            return fail('auth_required', 'Missing, expired, or invalid bearer token.', trc, status_code=401)
        if actor['role'] not in {'recruiter', 'admin'}:
            return fail('forbidden', 'Recruiter/admin only.', trc, status_code=403)
        benchmark = self.repo.insert_benchmark(payload)
        await publish_event('benchmark.completed', build_event(
            event_type='benchmark.completed',
            actor_id=actor['sub'],
            entity_type='benchmark',
            entity_id=benchmark['benchmark_id'],
            payload=benchmark,
            trace=trc,
            idempotency_key=f'benchmark.completed:{benchmark["benchmark_id"]}',
        ))
        self.invalidate_rollup_cache()
        return success({'benchmark_id': benchmark['benchmark_id'], 'accepted': True}, trc)

    def list_benchmarks(self, payload, authorization, trc):
        try:
            actor = require_auth(authorization)
        except Exception:
            return fail('auth_required', 'Missing, expired, or invalid bearer token.', trc, status_code=401)
        if actor['role'] not in {'recruiter', 'admin'}:
            return fail('forbidden', 'Recruiter/admin only.', trc, status_code=403)
        cache_key = f"analytics:benchmarks:{body_hash(payload)}"
        cached = get_json(cache_key)
        if cached:
            return success(cached, trc, {'cache': 'hit'})
        items = self.repo.list_benchmarks(payload.get('limit', 20))
        body = {'items': items}
        set_json(cache_key, body, self.ANALYTICS_TTL)
        return success(body, trc, {'cache': 'miss'})
