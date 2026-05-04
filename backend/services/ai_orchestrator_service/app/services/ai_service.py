from __future__ import annotations

import asyncio
import json
import os
from uuid import uuid4

import httpx
from fastapi import WebSocket

from services.ai_orchestrator_service.app.services.ai_matching import CandidateMatchingService
from services.ai_orchestrator_service.app.services.ai_openrouter_client import OpenRouterClient
from services.ai_orchestrator_service.app.services.ai_resume_intelligence import collect_resume_text, parse_resume
from services.shared.cache import delete_key, get_json, set_json
from services.shared.common import body_hash, build_event, check_idempotency, fail, record_idempotency, require_auth, success, trace_id
from services.shared.kafka_bus import consume_forever, publish_event
from services.shared.notifications import create_notification
from services.shared.observability import get_logger, log_event
from services.shared.outbox import DocumentOutboxRepository, dispatch_outbox_forever
from services.shared.document_store import find_many, insert_one
from services.shared.repositories import ApplicationRepository, JobRepository, MemberRepository, RecruiterRepository
from services.shared.resume_parser import extract_text_from_response


class AIOrchestratorService:
    TASK_CACHE_TTL = 900

    def __init__(self, repo):
        self.repo = repo
        self.outbox = DocumentOutboxRepository()
        self.applications = ApplicationRepository()
        self.jobs = JobRepository()
        self.members = MemberRepository()
        self.recruiters = RecruiterRepository()
        self.matcher = CandidateMatchingService()
        self.openrouter = OpenRouterClient()
        self.logger = get_logger('ai_orchestrator')
        self.sockets: dict[str, WebSocket] = {}
        self.stop_event = asyncio.Event()
        self.tasks: list[asyncio.Task] = []
        self.results_seen: set[str] = set()
        self.public_base_url = os.environ.get('PUBLIC_BASE_URL', '')
        self.messaging_service_url = os.environ.get('MESSAGING_SERVICE_URL', 'http://messaging_connections_service:8006').rstrip('/')
        self.kafka_consumers_enabled = str(os.environ.get('AI_KAFKA_CONSUMERS_ENABLED', 'true')).lower() not in {'0', 'false', 'no'}

    def cache_task(self, task_id: str, task: dict) -> None:
        set_json(f'ai:task:{task_id}', task, self.TASK_CACHE_TTL)

    async def push_update(self, task_id: str, payload: dict) -> None:
        websocket = self.sockets.get(task_id)
        if websocket:
            try:
                await websocket.send_json(payload)
            except Exception:
                self.sockets.pop(task_id, None)

    def _provider_name(self) -> str:
        self.openrouter.refresh()
        return self.openrouter.provider_name

    def _normalize_task(self, task: dict | None) -> dict | None:
        if not task:
            return None
        item = dict(task)
        if not isinstance(item.get('input'), dict):
            item['input'] = {}
        if not isinstance(item.get('output'), dict):
            item['output'] = {}
        if not isinstance(item.get('steps'), list):
            item['steps'] = []
        return item

    def _ensure_output(self, task: dict) -> dict:
        if not isinstance(task.get('output'), dict):
            task['output'] = {}
        return task['output']

    def _build_resume_fetch_url(self, url: str | None) -> str | None:
        if not url:
            return url
        rewritten = str(url)
        rewritten = rewritten.replace('http://localhost:8002', (os.environ.get('MEMBER_SERVICE_INTERNAL_URL') or 'http://member_profile_service:8002').rstrip('/'))
        rewritten = rewritten.replace('http://127.0.0.1:8002', (os.environ.get('MEMBER_SERVICE_INTERNAL_URL') or 'http://member_profile_service:8002').rstrip('/'))
        rewritten = rewritten.replace('http://localhost:9000', 'http://minio:9000')
        rewritten = rewritten.replace('http://127.0.0.1:9000', 'http://minio:9000')
        return rewritten

    async def _fetch_resume_text_from_ref(self, resume_ref: str | None) -> str:
        if not resume_ref:
            return ''
        ref = self._build_resume_fetch_url(resume_ref)
        lower = str(ref).lower()
        if lower.startswith('uploaded:'):
            return ''
        if not (lower.startswith('http://') or lower.startswith('https://')):
            return ''
        try:
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                response = await client.get(ref)
                response.raise_for_status()
                return extract_text_from_response(ref, response.content, response.headers.get('content-type'))
        except Exception as exc:
            log_event(self.logger, 'resume_fetch_failed', level=30, resume_ref=resume_ref, error=str(exc))
            return ''

    async def _build_candidate(self, application: dict, source_rank: int, job: dict) -> dict:
        application = dict(application or {})
        member = self.members.get(application.get('member_id')) or {}
        if not application.get('resume_text'):
            parsed_text = await self._fetch_resume_text_from_ref(application.get('resume_ref') or application.get('resume_url') or member.get('resume_url'))
            if parsed_text:
                application['resume_text'] = parsed_text
        artifacts = self.matcher.build_candidate(application, member, job, source_rank)
        return artifacts.candidate

    def _recruiter_signature(self, actor_id: str | None) -> tuple[str, str, str]:
        recruiter = self.recruiters.get_recruiter(actor_id) if actor_id else None
        if not recruiter:
            return ('Recruiting Team', 'Recruiter', '')
        company = self.recruiters.get_company(recruiter.get('company_id')) if recruiter.get('company_id') else None
        name = recruiter.get('name') or actor_id or 'Recruiting Team'
        title = recruiter.get('headline') or recruiter.get('access_level') or 'Recruiter'
        company_name = recruiter.get('company_name') or (company or {}).get('company_name') or ''
        return (name, title, company_name)

    def _personalize_draft_text(self, text: str | None, actor_id: str | None) -> str:
        if not text:
            return text or ''
        name, title, company_name = self._recruiter_signature(actor_id)
        result = str(text)
        replacements = {
            '[Your Name]': name,
            '[Recruiter Name]': name,
            '[Your Title]': f'{title}{(" · " + company_name) if company_name else ""}',
            '[Recruiter Title]': f'{title}{(" · " + company_name) if company_name else ""}',
            '[Company Name]': company_name or 'our company',
            'Recruiting Team': name,
        }
        for src, dst in replacements.items():
            if src in result and dst:
                result = result.replace(src, dst)
        if company_name and name in result and ('[Your Title]' not in text and '[Recruiter Title]' not in text):
            # Ensure a company-aware signature when the model leaves only the recruiter name.
            result = result.replace(f'\n{name}', f'\n{name}\n{title} · {company_name}')
        return result

    def _personalize_drafts(self, drafts: list[dict] | None, actor_id: str | None) -> list[dict]:
        output = []
        for draft in list(drafts or []):
            item = dict(draft)
            item['message'] = self._personalize_draft_text(item.get('message'), actor_id)
            item['draft'] = self._personalize_draft_text(item.get('draft') or item.get('message'), actor_id)
            name, title, company_name = self._recruiter_signature(actor_id)
            item['sender_name'] = name
            item['sender_title'] = title
            item['sender_company'] = company_name
            output.append(item)
        return output

    def _heuristic_drafts(self, shortlist: list[dict], job: dict, actor_id: str | None) -> list[dict]:
        drafts = []
        for candidate in shortlist[:3]:
            first_name = candidate.get('first_name') or candidate.get('name') or candidate.get('candidate_id')
            role = job.get('title') or 'this role'
            message = f"Hi {first_name}, your background looks like a strong fit for {role}. Would you be open to a quick chat?"
            drafts.append({
                'candidate_id': candidate.get('candidate_id'),
                'name': candidate.get('name'),
                'message': message,
                'draft': f"Hi {first_name},\n\nI reviewed your application and your background looks like a strong fit for {role}. I would love to connect and share more about the opportunity.\n\nBest,\nRecruiting Team",
            })
        return self._personalize_drafts(drafts, actor_id)

    def _merge_ai_output(self, shortlist: list[dict], ai_output: dict | None) -> tuple[list[dict], list[dict]]:
        if not ai_output:
            return shortlist, []
        ai_items = ai_output.get('shortlist') or []
        outreach = ai_output.get('outreach_drafts') or []
        if not ai_items:
            return shortlist, outreach
        by_id = {item.get('candidate_id'): dict(item) for item in shortlist}
        merged: list[dict] = []
        for item in ai_items:
            candidate_id = item.get('candidate_id')
            base = dict(by_id.get(candidate_id) or {})
            if not base:
                continue
            base.update({key: value for key, value in item.items() if value not in (None, '')})
            base['skill_overlap'] = list(item.get('skill_overlap') or base.get('skill_overlap') or [])
            base['missing_skills'] = list(item.get('missing_skills') or base.get('missing_skills') or [])
            base['keyword_overlap'] = list(base.get('keyword_overlap') or [])
            try:
                base['match_score'] = int(item.get('match_score', base.get('match_score', 0)))
            except Exception:
                pass
            merged.append(base)
            by_id.pop(candidate_id, None)
        merged.extend(sorted(by_id.values(), key=lambda candidate: int(candidate.get('match_score') or 0), reverse=True))
        return merged, outreach

    def _parsed_candidates(self, shortlist: list[dict]) -> list[dict]:
        parsed: list[dict] = []
        for candidate in shortlist:
            parsed.append({
                'candidate_id': candidate.get('candidate_id'),
                'name': candidate.get('name'),
                'match_score': candidate.get('match_score'),
                'embedding_similarity': candidate.get('embedding_similarity'),
                'resume_parsed': candidate.get('resume_parsed', {}),
                'skill_overlap': list(candidate.get('skill_overlap') or []),
                'missing_skills': list(candidate.get('missing_skills') or []),
                'rationale': candidate.get('rationale'),
            })
        return parsed

    def _build_result_event(self, actor_id: str, task_id: str, job_id: str | None, step: str, payload: dict, trc: str) -> dict:
        return build_event(
            event_type='ai.result',
            actor_id=actor_id,
            entity_type='ai_task',
            entity_id=task_id,
            payload={'task_id': task_id, 'job_id': job_id, 'step': step, **payload},
            trace=trc,
            idempotency_key=f'{task_id}:{step}',
        )

    async def _emit_result(self, event: dict) -> None:
        task_id = event.get('entity', {}).get('entity_id')
        if task_id:
            self.outbox.enqueue(topic='ai.results', event=event, aggregate_type='ai_task', aggregate_id=task_id)
        published = await publish_event('ai.results', event)
        log_event(self.logger, 'ai_result_emitted', task_id=task_id, step=event.get('payload', {}).get('step'), kafka_published=published)
        await self.process_ai_result('ai.results', event)

    async def _run_pipeline(self, task: dict, event: dict) -> None:
        task_id = task['task_id']
        actor_id = event.get('actor_id', task.get('created_by') or 'rec_120')
        trc = event.get('trace_id', trace_id())
        job_id = task.get('input', {}).get('job_id')
        task_type = task.get('input', {}).get('task_type', 'full_pipeline')
        log_event(self.logger, 'ai_task_runner_started', task_id=task_id, job_id=job_id, task_type=task_type, provider=self._provider_name(), trace_id=trc)

        job = self.jobs.get(job_id) if job_id else None
        if not job:
            raise RuntimeError('job_not_found')
        applicants = self.applications.list_by_job(job_id) if job_id else []
        shortlisted: list[dict] = []
        for index, application in enumerate(applicants, start=1):
            shortlisted.append(await self._build_candidate(application, index, job))
        shortlisted.sort(key=lambda candidate: int(candidate.get('match_score') or 0), reverse=True)
        parsed_candidates = self._parsed_candidates(shortlisted)

        await self._emit_result(self._build_result_event(actor_id, task_id, job_id, 'fetching_job', {
            'job_id': job_id,
            'job_title': job.get('title'),
            'progress_pct': 15,
        }, trc))
        await asyncio.sleep(0.05)

        await self._emit_result(self._build_result_event(actor_id, task_id, job_id, 'fetching_candidates', {
            'candidates_found': len(shortlisted),
            'progress_pct': 30,
        }, trc))
        await asyncio.sleep(0.05)

        await self._emit_result(self._build_result_event(actor_id, task_id, job_id, 'parsing_resumes', {
            'parsed_candidates': parsed_candidates,
            'progress_pct': 55,
        }, trc))
        await asyncio.sleep(0.05)

        drafts = self._heuristic_drafts(shortlisted, job, actor_id)
        ai_output = None
        try:
            ai_output = await self.openrouter.generate(job, shortlisted, task_type, trace_id=trc)
        except Exception as exc:
            log_event(self.logger, 'openrouter_request_failed', level=30, trace_id=trc, task_id=task_id, error=str(exc))
        if ai_output:
            shortlisted, ai_drafts = self._merge_ai_output(shortlisted, ai_output)
            if ai_drafts:
                drafts = self._personalize_drafts(ai_drafts, actor_id)
            parsed_candidates = self._parsed_candidates(shortlisted)

        await self._emit_result(self._build_result_event(actor_id, task_id, job_id, 'matching_candidates', {
            'matches': shortlisted,
            'parsed_candidates': parsed_candidates,
            'provider': self._provider_name(),
            'progress_pct': 75,
        }, trc))
        await asyncio.sleep(0.05)

        if task_type in {'resume_parse', 'shortlist'}:
            await self._emit_result(self._build_result_event(actor_id, task_id, job_id, 'waiting_approval', {
                'approval_required': False,
                'shortlist': shortlisted,
                'parsed_candidates': parsed_candidates,
                'outreach_drafts': [],
                'provider': self._provider_name(),
                'progress_pct': 100,
            }, trc))
            return

        drafts = self._personalize_drafts(drafts, actor_id)
        await self._emit_result(self._build_result_event(actor_id, task_id, job_id, 'drafting_outreach', {
            'outreach_drafts': drafts,
            'provider': self._provider_name(),
            'progress_pct': 90,
        }, trc))
        await asyncio.sleep(0.05)
        await self._emit_result(self._build_result_event(actor_id, task_id, job_id, 'waiting_approval', {
            'approval_required': True,
            'shortlist': shortlisted,
            'parsed_candidates': parsed_candidates,
            'outreach_drafts': drafts,
            'provider': self._provider_name(),
            'progress_pct': 100,
        }, trc))

    async def process_ai_request(self, topic: str, event: dict) -> None:
        if event.get('event_type') not in {'ai.requested', 'ai.tasks.create'}:
            return
        task_id = event.get('entity', {}).get('entity_id')
        task = self._normalize_task(self.repo.get_task(task_id))
        if not task:
            return
        status = str(task.get('status') or 'queued')
        current_step = str(task.get('current_step') or 'queued')
        if status not in {'queued', 'running'} and current_step not in {'queued', 'starting'}:
            return
        marker = event.get('idempotency_key') or f'{task_id}:request'
        if task.get('_processing_marker') == marker and current_step not in {'queued', 'starting'}:
            return
        task['_processing_marker'] = marker
        task['status'] = 'running'
        task['current_step'] = 'starting'
        self.repo.save_task(task)
        self.cache_task(task_id, task)
        await self.push_update(task_id, {'task_id': task_id, 'status': task['status'], 'current_step': task['current_step'], 'payload': {}, 'type': 'task_state', 'data': task})
        try:
            await self._run_pipeline(task, event)
        except Exception as exc:
            trc = event.get('trace_id', trace_id())
            log_event(self.logger, 'ai_task_runner_failed', level=30, trace_id=trc, task_id=task_id, error=str(exc))
            await self._emit_result(self._build_result_event(
                event.get('actor_id', task.get('created_by') or 'rec_120'),
                task_id,
                task.get('input', {}).get('job_id'),
                'failed',
                {'error': str(exc), 'progress_pct': 100},
                trc,
            ))

    async def process_ai_result(self, topic: str, event: dict) -> None:
        if event.get('event_type') not in {'ai.result', 'ai.rejected'}:
            return
        event_key = str(event.get('idempotency_key') or '')
        task_id = event.get('entity', {}).get('entity_id')
        if not task_id or (event_key and event_key in self.results_seen):
            return
        if event_key:
            self.results_seen.add(event_key)
        task = self._normalize_task(self.repo.get_task(task_id))
        if not task:
            return
        payload = event.get('payload', {}) or {}
        step = payload.get('step', event.get('event_type', 'unknown'))
        output = self._ensure_output(task)
        task.setdefault('steps', []).append({'step': step, 'payload': payload, 'trace_id': event.get('trace_id')})
        task['current_step'] = step

        if step == 'waiting_approval':
            approval_required = bool(payload.get('approval_required'))
            task['status'] = 'awaiting_approval' if approval_required else 'completed'
            output.update({
                'shortlist': payload.get('shortlist', output.get('shortlist', [])),
                'parsed_candidates': payload.get('parsed_candidates', output.get('parsed_candidates', [])),
                'outreach_drafts': payload.get('outreach_drafts', output.get('outreach_drafts', [])),
                'draft_message': ((payload.get('outreach_drafts') or output.get('outreach_drafts') or [{}])[0].get('message') if (payload.get('outreach_drafts') or output.get('outreach_drafts')) else output.get('draft_message')),
                'provider': payload.get('provider', output.get('provider', self._provider_name())),
            })
        elif step == 'approved':
            task['status'] = 'completed'
            task['approval_state'] = 'approved'
            if payload.get('approval_action') in {'approved_as_is', 'edited'}:
                task['approval_action'] = payload['approval_action']
            output['sent_messages'] = payload.get('sent_messages', output.get('sent_messages', []))
            output['outreach_sent_count'] = payload.get('sent_count', output.get('outreach_sent_count', 0))
            output['outreach_send_failures'] = payload.get('failed', output.get('outreach_send_failures', []))
        elif step == 'rejected':
            task['status'] = 'rejected'
            task['approval_state'] = 'rejected'
            task['approval_action'] = 'rejected'
        elif step == 'failed':
            task['status'] = 'failed'
            output['error'] = payload.get('error')
        else:
            task['status'] = 'running'
            if step == 'parsing_resumes':
                output['parsed_candidates'] = payload.get('parsed_candidates', [])
            elif step == 'matching_candidates':
                output['shortlist'] = payload.get('matches', [])
                output['parsed_candidates'] = payload.get('parsed_candidates', [])
                output['provider'] = payload.get('provider', output.get('provider', self._provider_name()))
            elif step == 'drafting_outreach':
                output['outreach_drafts'] = payload.get('outreach_drafts', [])
                drafts = output.get('outreach_drafts') or []
                output['draft_message'] = drafts[0].get('message') if drafts else output.get('draft_message')
        self.repo.save_task(task)
        self.cache_task(task_id, task)
        await self.push_update(task_id, {'task_id': task_id, 'status': task['status'], 'current_step': task['current_step'], 'payload': payload, 'type': 'task_state', 'data': task})

    async def _run_local_fallback(self, event: dict, delay_seconds: float, reason: str) -> None:
        try:
            await asyncio.sleep(delay_seconds)
            task_id = event.get('entity', {}).get('entity_id')
            task = self._normalize_task(self.repo.get_task(task_id)) if task_id else None
            if not task:
                return
            if str(task.get('status') or '') in {'completed', 'failed', 'rejected', 'awaiting_approval'}:
                return
            log_event(self.logger, 'ai_task_fallback_triggered', task_id=task_id, reason=reason)
            await self.process_ai_request('ai.requests.local_fallback', event)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log_event(self.logger, 'ai_task_fallback_failed', level=30, error=str(exc), reason=reason)

    def _build_existing_task_event(self, task: dict, trc: str) -> dict:
        return build_event(
            event_type='ai.requested',
            actor_id=task.get('created_by') or 'rec_120',
            entity_type='ai_task',
            entity_id=task['task_id'],
            payload={
                'job_id': task.get('input', {}).get('job_id'),
                'task_type': task.get('input', {}).get('task_type', 'full_pipeline'),
            },
            trace=trc,
            idempotency_key=f"{task['task_id']}:rehydrate",
        )

    def _schedule_processing_if_needed(self, task: dict | None, reason: str, trc: str) -> None:
        task = self._normalize_task(task)
        if not task:
            return
        if str(task.get('status') or '') in {'completed', 'failed', 'rejected', 'awaiting_approval'}:
            return
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._run_local_fallback(self._build_existing_task_event(task, trc), 0.1, reason))
        except RuntimeError:
            pass

    async def startup(self) -> None:
        if self.tasks:
            return
        log_event(self.logger, 'ai_startup_config', kafka_consumers_enabled=self.kafka_consumers_enabled, provider=self._provider_name(), openrouter_key_present=self.openrouter.enabled, model=self.openrouter.model)
        self.tasks.append(asyncio.create_task(dispatch_outbox_forever(self.outbox, self.stop_event)))
        if self.kafka_consumers_enabled:
            self.tasks.append(asyncio.create_task(consume_forever(['ai.requests'], 'ai-orchestrator-processor', self.process_ai_request, self.stop_event)))
            self.tasks.append(asyncio.create_task(consume_forever(['ai.results'], 'ai-orchestrator-results', self.process_ai_result, self.stop_event)))

    async def shutdown(self) -> None:
        self.stop_event.set()
        for task in self.tasks:
            task.cancel()
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks.clear()
        self.stop_event = asyncio.Event()

    async def create_task(self, payload, authorization, trc, idempotency_key=None):
        try:
            actor = require_auth(authorization)
        except Exception:
            return fail('auth_required', 'Missing, expired, or invalid bearer token.', trc, status_code=401)
        if actor['role'] not in {'recruiter', 'admin'}:
            return fail('forbidden', 'Recruiter/admin only.', trc, status_code=403)
        route = '/ai/tasks/create'
        explicit_key = idempotency_key or payload.get('idempotency_key')
        key = explicit_key or f"{actor['sub']}:{payload.get('job_id', 'unknown')}:{payload.get('task_type', 'full_pipeline')}:{uuid4().hex}"
        request_hash = body_hash(payload)
        existing, conflict = check_idempotency(route, key, request_hash)
        if conflict:
            return fail('idempotency_conflict', 'Same Idempotency-Key reused with a different request body.', trc, status_code=409)
        if existing:
            return success(existing['data'], existing['trace_id'], existing.get('meta'))

        self.openrouter.refresh()
        task = self.repo.create_task({
            'input': payload,
            'output': {},
            'created_by': actor['sub'],
            'created_by_role': actor['role'],
            'status': 'queued',
            'current_step': 'queued',
        })
        task = self._normalize_task(task) or task
        self.cache_task(task['task_id'], task)
        event = build_event(
            event_type='ai.requested',
            actor_id=actor['sub'],
            entity_type='ai_task',
            entity_id=task['task_id'],
            payload={'job_id': payload.get('job_id'), 'task_type': payload.get('task_type', 'shortlist')},
            trace=trc,
            idempotency_key=key,
        )
        published = await publish_event('ai.requests', event)
        self.outbox.enqueue(topic='ai.requests', event=event, aggregate_type='ai_task', aggregate_id=task['task_id'])
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._run_local_fallback(event, 2.0 if self.kafka_consumers_enabled else 0.05, 'create_task'))
        except RuntimeError:
            pass
        meta = {
            'event_dispatch': 'published' if published else 'queued',
            'provider': self._provider_name(),
            'execution_mode': 'kafka_first_hybrid_async',
        }
        response = {'task_id': task['task_id'], 'status': 'queued'}
        record_idempotency(route, key, request_hash, {'trace_id': trc, 'data': response, 'meta': meta})
        log_event(self.logger, 'ai_request_received', trace_id=trc, task_id=task['task_id'], job_id=payload.get('job_id'), task_type=payload.get('task_type', 'shortlist'), kafka_published=published, provider=self._provider_name())
        return success(response, trc, meta)

    def list_tasks(self, authorization, trc):
        try:
            actor = require_auth(authorization)
        except Exception:
            return fail('auth_required', 'Missing, expired, or invalid bearer token.', trc, status_code=401)
        if actor['role'] not in {'recruiter', 'admin'}:
            return fail('forbidden', 'Recruiter/admin only.', trc, status_code=403)
        tasks = [self._normalize_task(task) for task in self.repo.list_tasks_for_user(actor['sub'])]
        for task in tasks:
            self._schedule_processing_if_needed(task, 'list_tasks', trc)
            self.cache_task(task['task_id'], task)
        return success({'items': tasks}, trc, {'total': len(tasks)})

    def _scoped_tasks(self, actor: dict) -> list[dict]:
        if actor.get('role') == 'admin':
            raw = self.repo.list_all_tasks()
        else:
            raw = self.repo.list_tasks_for_user(actor['sub'])
        return [self._normalize_task(task) for task in raw if task]

    def approval_rate(self, authorization, trc):
        try:
            actor = require_auth(authorization)
        except Exception:
            return fail('auth_required', 'Missing, expired, or invalid bearer token.', trc, status_code=401)
        if actor['role'] not in {'recruiter', 'admin'}:
            return fail('forbidden', 'Recruiter/admin only.', trc, status_code=403)
        counts = {'approved_as_is': 0, 'edited': 0, 'rejected': 0}
        for task in self._scoped_tasks(actor):
            action = task.get('approval_action')
            if action in counts:
                counts[action] += 1
        total = counts['approved_as_is'] + counts['edited'] + counts['rejected']
        def pct(n: int) -> float:
            return round((n / total) * 100, 1) if total else 0.0
        payload = {
            'total_tasks': total,
            'approved_as_is': counts['approved_as_is'],
            'edited': counts['edited'],
            'rejected': counts['rejected'],
            'approval_rate_pct': pct(counts['approved_as_is']),
            'edit_rate_pct': pct(counts['edited']),
            'rejection_rate_pct': pct(counts['rejected']),
            'scope': 'all' if actor.get('role') == 'admin' else 'recruiter',
        }
        return success(payload, trc)

    def match_quality(self, authorization, trc):
        try:
            actor = require_auth(authorization)
        except Exception:
            return fail('auth_required', 'Missing, expired, or invalid bearer token.', trc, status_code=401)
        if actor['role'] not in {'recruiter', 'admin'}:
            return fail('forbidden', 'Recruiter/admin only.', trc, status_code=403)
        TOP_K = 5
        eligible_statuses = {'awaiting_approval', 'completed', 'rejected'}
        match_scores: list[float] = []
        skill_overlap_pcts: list[float] = []
        for task in self._scoped_tasks(actor):
            if str(task.get('status') or '') not in eligible_statuses:
                continue
            shortlist = list((task.get('output') or {}).get('shortlist') or [])
            shortlist = sorted(shortlist, key=lambda c: float(c.get('match_score') or 0), reverse=True)[:TOP_K]
            for candidate in shortlist:
                score = candidate.get('match_score')
                if score is None:
                    continue
                try:
                    match_scores.append(float(score))
                except (TypeError, ValueError):
                    continue
                matched = len(candidate.get('skill_overlap') or [])
                missing = len(candidate.get('missing_skills') or [])
                required = matched + missing
                skill_overlap_pcts.append((matched / required) * 100 if required else 0.0)
        sample_size = len(match_scores)
        avg_match = round(sum(match_scores) / sample_size, 1) if sample_size else 0.0
        avg_overlap = round(sum(skill_overlap_pcts) / sample_size, 1) if sample_size else 0.0
        return success({
            'avg_match_score': avg_match,
            'avg_skill_overlap_pct': avg_overlap,
            'top_k': TOP_K,
            'sample_size': sample_size,
            'scope': 'all' if actor.get('role') == 'admin' else 'recruiter',
        }, trc)

    def _save_coach_history(self, member_id: str, job: dict, result: dict) -> None:
        try:
            from datetime import datetime, timezone
            record = {
                'history_id': f'ch_{uuid4().hex[:10]}',
                'member_id': member_id,
                'target_job_id': result.get('target_job_id'),
                'job_title': job.get('title') or '',
                'company_name': job.get('company_name') or job.get('company_id') or '',
                'current_match_score': result.get('current_match_score'),
                'match_score_if_improved': result.get('match_score_if_improved'),
                'score_delta': result.get('score_delta'),
                'skills_to_add': list(result.get('skills_to_add') or []),
                'suggested_headline': result.get('suggested_headline'),
                'resume_tips': list(result.get('resume_tips') or []),
                'rationale': result.get('rationale'),
                'provider': result.get('provider'),
                'searched_at': datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
            }
            insert_one('coach_history', record)
            delete_key(f'coach_hist:{member_id}')
        except Exception as exc:
            log_event(self.logger, 'coach_history_save_failed', level=30, error=str(exc))

    def _heuristic_coach_text(self, member: dict, job: dict, missing: list[str]) -> tuple[str, list[str]]:
        title = job.get('title') or 'your target role'
        top_skills = (missing or [])[:3]
        if top_skills:
            headline = f"{member.get('current_title') or 'Aspiring ' + title} | {' · '.join(top_skills)}"
        else:
            headline = member.get('headline') or f"Candidate for {title}"
        tips: list[str] = []
        if missing:
            tips.append(f"Highlight projects or coursework involving {', '.join(missing[:3])}.")
        tips.append('Quantify impact in your experience bullets (users, latency, revenue, accuracy).')
        if not member.get('about_text') and not member.get('about'):
            tips.append('Add a 2-3 sentence summary that names your specialization and target role.')
        if job.get('seniority_level'):
            tips.append(f"Mirror language used in {job.get('seniority_level')}-level job descriptions, e.g. 'led', 'owned', 'architected'.")
        return headline[:100], tips[:4]

    async def coach_suggest(self, payload, authorization, trc):
        try:
            actor = require_auth(authorization)
        except Exception:
            return fail('auth_required', 'Missing, expired, or invalid bearer token.', trc, status_code=401)
        member_id = payload.get('member_id') or actor.get('sub')
        target_job_id = payload.get('target_job_id') or payload.get('job_id')
        if not member_id:
            return fail('invalid_request', 'member_id is required', trc, status_code=400)
        if not target_job_id:
            return fail('invalid_request', 'target_job_id is required', trc, status_code=400)
        # Members can only coach themselves; recruiters/admins can coach any member.
        if actor.get('role') == 'member' and member_id != actor.get('sub'):
            return fail('forbidden', 'Members can only request coaching for their own profile.', trc, status_code=403)

        member = self.members.get(member_id)
        if not member:
            return fail('not_found', f'Member {member_id} not found', trc, status_code=404)
        job = self.jobs.get(target_job_id)
        if not job:
            return fail('not_found', f'Job {target_job_id} not found', trc, status_code=404)

        resume_text = collect_resume_text({}, member)
        parsed = parse_resume(resume_text, member, {}).as_dict()
        current_score, matched, missing, keyword_overlap, rationale, embedding_sim = self.matcher.score_candidate(job, member, parsed, resume_text)

        improved_parsed = dict(parsed)
        improved_parsed['skills'] = list(parsed.get('skills') or []) + list(missing or [])
        improved_score, _, _, _, _, _ = self.matcher.score_candidate(job, member, improved_parsed, resume_text)

        coach_output = None
        try:
            self.openrouter.refresh()
            coach_output = await self.openrouter.coach_generate(member=member, job=job, missing_skills=missing, trace_id=trc)
        except Exception as exc:
            log_event(self.logger, 'coach_llm_failed', level=30, trace_id=trc, error=str(exc))

        if coach_output and isinstance(coach_output.get('resume_tips'), list) and coach_output.get('suggested_headline'):
            suggested_headline = str(coach_output['suggested_headline'])[:100]
            resume_tips = [str(tip) for tip in coach_output['resume_tips'] if tip][:4]
            served_by = self._provider_name()
        else:
            suggested_headline, resume_tips = self._heuristic_coach_text(member, job, missing)
            served_by = 'heuristic'

        log_event(self.logger, 'career_coach_generated', trace_id=trc, member_id=member_id, job_id=target_job_id, current_score=current_score, improved_score=improved_score, provider=served_by)
        result_payload = {
            'member_id': member_id,
            'target_job_id': target_job_id,
            'suggested_headline': suggested_headline,
            'skills_to_add': list(missing),
            'resume_tips': resume_tips,
            'current_match_score': current_score,
            'match_score_if_improved': improved_score,
            'score_delta': improved_score - current_score,
            'rationale': rationale,
            'provider': served_by,
        }
        self._save_coach_history(member_id, job, result_payload)
        return success(result_payload, trc)

    def coach_history(self, authorization, trc):
        try:
            actor = require_auth(authorization)
        except Exception:
            return fail('auth_required', 'Missing, expired, or invalid bearer token.', trc, status_code=401)
        member_id = actor.get('sub')
        if not member_id:
            return fail('invalid_request', 'Could not determine member identity from token.', trc, status_code=400)
        cache_key = f'coach_hist:{member_id}'
        cached = get_json(cache_key)
        if cached is not None:
            return success({'items': cached}, trc, {'cache': 'hit', 'total': len(cached)})
        items = find_many('coach_history', {'member_id': member_id}, sort=[('searched_at', -1)])
        items = items[:20]
        set_json(cache_key, items, 300)
        return success({'items': items}, trc, {'cache': 'miss', 'total': len(items)})

    def _heuristic_redraft(self, current_draft: str, instructions: str, candidate_name: str) -> str:
        instr = instructions.lower()
        lines = [l for l in current_draft.strip().split('\n') if l.strip()]
        if not lines:
            return current_draft
        if any(w in instr for w in ('shorter', 'brief', 'concise', 'short')):
            lines = lines[:2] + ([lines[-1]] if len(lines) > 2 else [])
        if any(w in instr for w in ('casual', 'friendly', 'informal', 'warm')):
            if lines[0].lower().startswith('dear'):
                lines[0] = f'Hi {candidate_name},'
        elif any(w in instr for w in ('formal', 'professional')):
            if lines[0].lower().startswith(('hi ', 'hey ')):
                lines[0] = f'Dear {candidate_name},'
        return '\n'.join(lines)

    async def redraft_draft(self, task_id: str, payload: dict, authorization, trc):
        try:
            actor = require_auth(authorization)
        except Exception:
            return fail('auth_required', 'Missing, expired, or invalid bearer token.', trc, status_code=401)
        if actor['role'] not in {'recruiter', 'admin'}:
            return fail('forbidden', 'Recruiter/admin only.', trc, status_code=403)
        candidate_id = payload.get('candidate_id', '').strip()
        instructions = payload.get('instructions', '').strip()
        current_draft = payload.get('current_draft', '').strip()
        if not candidate_id or not instructions:
            return fail('bad_request', 'candidate_id and instructions are required.', trc, status_code=400)
        task = self._normalize_task(self.repo.get_task(task_id))
        if not task:
            return fail('not_found', 'Task not found.', trc, status_code=404)
        job_id = task.get('input', {}).get('job_id')
        job = self.jobs.get(job_id) if job_id else {}
        shortlist = task.get('output', {}).get('shortlist') or []
        if isinstance(shortlist, str):
            try:
                import json as _json
                shortlist = _json.loads(shortlist)
            except Exception:
                shortlist = []
        candidate = next((c for c in shortlist if c.get('candidate_id') == candidate_id), {'candidate_id': candidate_id, 'name': candidate_id})
        new_message = None
        try:
            self.openrouter.refresh()
            new_message = await self.openrouter.redraft_message(
                job=job or {},
                candidate=candidate,
                current_draft=current_draft,
                instructions=instructions,
                trace_id=trc,
            )
        except Exception as exc:
            log_event(self.logger, 'redraft_openrouter_failed', level=30, trace_id=trc, task_id=task_id, error=str(exc))
        if not new_message:
            new_message = self._heuristic_redraft(current_draft, instructions, candidate.get('name') or candidate_id)
        return success({'message': new_message, 'candidate_id': candidate_id, 'provider': self._provider_name()}, trc)

    def get_task(self, task_id, authorization, trc):
        try:
            require_auth(authorization)
        except Exception:
            return fail('auth_required', 'Missing, expired, or invalid bearer token.', trc, status_code=401)
        task = get_json(f'ai:task:{task_id}')
        cache_status = 'hit' if task else 'miss'
        if not task:
            task = self.repo.get_task(task_id)
            if task:
                self.cache_task(task_id, task)
        task = self._normalize_task(task)
        if not task:
            return fail('not_found', 'Task not found.', trc, status_code=404)
        self._schedule_processing_if_needed(task, 'get_task', trc)
        return success(task, trc, {'cache': cache_status})

    async def _send_outreach_messages(self, task: dict, actor_id: str, authorization: str | None, trc: str) -> dict:
        drafts = list(self._ensure_output(task).get('outreach_drafts') or [])
        if not drafts:
            return {'sent': [], 'failed': [], 'sent_count': 0}
        headers = {'Authorization': authorization or '', 'X-Trace-Id': trc}
        sent: list[dict] = []
        failed: list[dict] = []
        async with httpx.AsyncClient(timeout=15.0) as client:
            for draft in drafts:
                candidate_id = draft.get('candidate_id')
                if not candidate_id:
                    failed.append({'candidate_id': None, 'error': 'missing_candidate_id'})
                    continue
                try:
                    thread_response = await client.post(
                        f'{self.messaging_service_url}/threads/open',
                        json={'participant_ids': [actor_id, candidate_id]},
                        headers=headers,
                    )
                    thread_response.raise_for_status()
                    thread_payload = thread_response.json().get('data') or {}
                    thread_id = thread_payload.get('thread_id')
                    message_text = draft.get('draft') or draft.get('message') or ''
                    message_response = await client.post(
                        f'{self.messaging_service_url}/messages/send',
                        json={'thread_id': thread_id, 'text': message_text, 'client_message_id': f"ai-{task['task_id']}-{candidate_id}"},
                        headers=headers,
                    )
                    message_response.raise_for_status()
                    sent.append({'candidate_id': candidate_id, 'thread_id': thread_id, 'message': message_text})
                    create_notification(
                        candidate_id,
                        'recruiter_outreach',
                        'Recruiter reached out',
                        'A recruiter sent you a message about a shortlisted role.',
                        actor_id=actor_id,
                        target_url=f'/messages?thread={thread_id}',
                        data={'task_id': task['task_id'], 'thread_id': thread_id},
                    )
                except Exception as exc:
                    failed.append({'candidate_id': candidate_id, 'error': str(exc)})
        output = self._ensure_output(task)
        output['sent_messages'] = sent
        output['outreach_send_failures'] = failed
        output['outreach_sent_count'] = len(sent)
        return {'sent': sent, 'failed': failed, 'sent_count': len(sent)}

    def _notify_selected_candidates(self, task: dict, actor_id: str) -> None:
        shortlist = list(self._ensure_output(task).get('shortlist') or [])
        for candidate in shortlist[:3]:
            candidate_id = candidate.get('candidate_id')
            if not candidate_id:
                continue
            create_notification(
                candidate_id,
                'ai_shortlisted',
                'You were shortlisted',
                'A recruiter shortlisted your application for further review.',
                actor_id=actor_id,
                target_url='/jobs',
                data={'task_id': task['task_id'], 'job_id': task.get('input', {}).get('job_id')},
            )

    async def approve_task(self, task_id, payload, authorization, trc):
        try:
            actor = require_auth(authorization)
        except Exception:
            return fail('auth_required', 'Missing, expired, or invalid bearer token.', trc, status_code=401)
        if actor['role'] not in {'recruiter', 'admin'}:
            return fail('forbidden', 'Recruiter/admin only.', trc, status_code=403)
        task = self._normalize_task(self.repo.get_task(task_id))
        if not task:
            return fail('not_found', 'Task not found.', trc, status_code=404)
        task['approval_state'] = 'approved'
        task['status'] = 'completed'
        task['current_step'] = 'approved'
        output = self._ensure_output(task)
        edits_raw = payload.get('edits')
        drafts = list(output.get('outreach_drafts') or [])
        any_edited = False

        if isinstance(edits_raw, dict):
            for draft in drafts:
                cid = draft.get('candidate_id')
                if cid is None or cid not in edits_raw:
                    continue
                new_text = edits_raw.get(cid)
                if new_text is None:
                    continue
                original = str(draft.get('message') or draft.get('draft') or '').strip()
                if str(new_text).strip() != original:
                    any_edited = True
                    draft['draft'] = new_text
                    draft['message'] = new_text
            if any_edited:
                output['outreach_drafts'] = drafts
                if drafts:
                    output['draft_message'] = drafts[0].get('message', output.get('draft_message'))

        task['approval_action'] = 'edited' if any_edited else 'approved_as_is'
        send_result = {'sent': [], 'failed': [], 'sent_count': 0}
        if payload.get('send_outreach', True) and bool(output.get('outreach_drafts')):
            send_result = await self._send_outreach_messages(task, actor['sub'], authorization, trc)
        self._notify_selected_candidates(task, actor['sub'])
        self.repo.save_task(task)
        self.cache_task(task_id, task)
        await self._emit_result(self._build_result_event(actor['sub'], task_id, task.get('input', {}).get('job_id'), 'approved', {
            'approval_state': 'approved',
            'approval_action': task['approval_action'],
            'sent_messages': send_result.get('sent', []),
            'failed': send_result.get('failed', []),
            'sent_count': send_result.get('sent_count', 0),
        }, trc))
        return success({'task_id': task_id, 'approval_state': 'approved', 'approval_action': task['approval_action'], 'status': 'approved', 'sent_count': send_result.get('sent_count', 0), 'failed': send_result.get('failed', [])}, trc, {'event_dispatch': 'queued'})

    async def send_outreach(self, task_id, payload, authorization, trc):
        try:
            actor = require_auth(authorization)
        except Exception:
            return fail('auth_required', 'Missing, expired, or invalid bearer token.', trc, status_code=401)
        if actor['role'] not in {'recruiter', 'admin'}:
            return fail('forbidden', 'Recruiter/admin only.', trc, status_code=403)
        task = self._normalize_task(self.repo.get_task(task_id))
        if not task:
            return fail('not_found', 'Task not found.', trc, status_code=404)
        result = await self._send_outreach_messages(task, actor['sub'], authorization, trc)
        self.repo.save_task(task)
        self.cache_task(task_id, task)
        return success({'task_id': task_id, 'sent_count': result.get('sent_count', 0), 'sent_messages': result.get('sent', []), 'failed': result.get('failed', [])}, trc)

    async def reject_task(self, task_id, payload, authorization, trc):
        try:
            actor = require_auth(authorization)
        except Exception:
            return fail('auth_required', 'Missing, expired, or invalid bearer token.', trc, status_code=401)
        if actor['role'] not in {'recruiter', 'admin'}:
            return fail('forbidden', 'Recruiter/admin only.', trc, status_code=403)
        task = self._normalize_task(self.repo.get_task(task_id))
        if not task:
            return fail('not_found', 'Task not found.', trc, status_code=404)
        task['approval_state'] = 'rejected'
        task['approval_action'] = 'rejected'
        task['status'] = 'rejected'
        task['current_step'] = 'rejected'
        task['rejection_reason'] = payload.get('reason', 'No reason provided')
        self.repo.save_task(task)
        self.cache_task(task_id, task)
        await self._emit_result(self._build_result_event(actor['sub'], task_id, task.get('input', {}).get('job_id'), 'rejected', {'reason': task['rejection_reason'], 'approval_action': 'rejected'}, trc))
        return success({'task_id': task_id, 'approval_state': 'rejected', 'approval_action': 'rejected', 'status': 'rejected'}, trc, {'event_dispatch': 'queued'})

    async def task_socket(self, websocket: WebSocket, task_id: str):
        await websocket.accept()
        self.sockets[task_id] = websocket
        cached = get_json(f'ai:task:{task_id}')
        if cached:
            await websocket.send_json({'task_id': task_id, 'status': cached.get('status'), 'current_step': cached.get('current_step'), 'payload': cached.get('output') or {}, 'type': 'task_state', 'data': cached})
        try:
            while True:
                await websocket.receive_text()
        except Exception:
            self.sockets.pop(task_id, None)
