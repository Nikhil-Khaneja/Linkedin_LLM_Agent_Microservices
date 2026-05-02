import asyncio
import uuid
from datetime import datetime, timezone

from services.shared.common import body_hash, build_event, check_idempotency, fail, record_idempotency, require_auth, success
from services.shared.outbox import RelationalOutboxRepository, dispatch_outbox_forever
from services.shared.repositories import JobRepository
from services.shared.notifications import create_notification
from services.shared.observability import get_logger, log_event


class ApplicationsService:
    def __init__(self, repo):
        self.repo = repo
        self.jobs_repo = JobRepository()
        self.outbox = RelationalOutboxRepository()
        self.stop_event = asyncio.Event()
        self.tasks: list[asyncio.Task] = []
        self.logger = get_logger('applications_service')

    async def startup(self):
        if not self.tasks:
            log_event(self.logger, 'applications_outbox_dispatcher_starting', action='startup')
            self.tasks.append(asyncio.create_task(dispatch_outbox_forever(self.outbox, self.stop_event)))

    async def shutdown(self):
        self.stop_event.set()
        for task in self.tasks:
            task.cancel()
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks.clear()
        self.stop_event = asyncio.Event()
        log_event(self.logger, 'applications_outbox_dispatcher_stopped', action='shutdown')

    async def submit(self, payload, authorization, trc, idempotency_key=None):
        log_event(
            self.logger,
            'application_submit_received',
            trace_id=trc,
            action='submit',
            route='/applications/submit',
            job_id=payload.get('job_id'),
            requested_member_id=payload.get('member_id'),
            resume_ref=payload.get('resume_ref'),
            idempotency_key=idempotency_key or payload.get('idempotency_key'),
        )
        try:
            actor = require_auth(authorization)
        except Exception:
            log_event(self.logger, 'application_submit_auth_failed', trace_id=trc, action='submit', route='/applications/submit', error_code='auth_required')
            return fail('auth_required', 'Missing, expired, or invalid bearer token.', trc, status_code=401)
        if actor['role'] != 'member':
            log_event(self.logger, 'application_submit_forbidden', trace_id=trc, action='submit', route='/applications/submit', actor_id=actor.get('sub'), actor_role=actor.get('role'), error_code='forbidden')
            return fail('forbidden', 'Member role only.', trc, status_code=403)

        member_id = actor['sub']
        job_id = payload.get('job_id')
        route = '/applications/submit'
        key = idempotency_key or payload.get('idempotency_key')
        h = body_hash(payload)
        existing, conflict = check_idempotency(route, key, h)
        if conflict:
            log_event(self.logger, 'application_submit_idempotency_conflict', trace_id=trc, action='submit', route=route, member_id=member_id, job_id=job_id, idempotency_key=key, error_code='idempotency_conflict')
            return fail('idempotency_conflict', 'Same Idempotency-Key reused with different apply payload.', trc, status_code=409)
        if existing:
            log_event(self.logger, 'application_submit_idempotency_replay', trace_id=trc, action='submit', route=route, member_id=member_id, job_id=job_id, idempotency_key=key, application_id=((existing or {}).get('data') or {}).get('application_id'))
            return success(existing['data'], existing['trace_id'], existing.get('meta'))

        if not job_id:
            log_event(self.logger, 'application_submit_validation_failed', trace_id=trc, action='submit', route=route, member_id=member_id, error_code='validation_error', validation_field='job_id')
            return fail('validation_error', 'job_id is required.', trc, status_code=400)

        job = self.jobs_repo.get(job_id)
        if not job:
            log_event(self.logger, 'application_submit_job_not_found', trace_id=trc, action='submit', route=route, member_id=member_id, job_id=job_id, error_code='job_not_found')
            return fail('job_not_found', 'Job not found.', trc, status_code=404)
        if str(job.get('status') or 'open').lower() != 'open':
            log_event(self.logger, 'application_submit_job_closed', trace_id=trc, action='submit', route=route, member_id=member_id, job_id=job_id, recruiter_id=job.get('recruiter_id'), error_code='job_closed')
            return fail('job_closed', 'Cannot apply to a closed job.', trc, status_code=409)

        if self.repo.find_duplicate(job_id, member_id):
            log_event(self.logger, 'application_submit_duplicate', trace_id=trc, action='submit', route=route, member_id=member_id, job_id=job_id, recruiter_id=job.get('recruiter_id'), error_code='duplicate_application')
            return fail('duplicate_application', 'Already applied to this job.', trc, status_code=409)

        application_id = f"app_{uuid.uuid4().hex[:10]}"
        applied_at = datetime.now(timezone.utc).replace(microsecond=0).strftime('%Y-%m-%d %H:%M:%S')
        payload_with_member = {
            **payload,
            'application_id': application_id,
            'member_id': member_id,
            'status': 'submitted',
            'application_datetime': applied_at,
        }

        event = build_event(
            event_type='application.submitted',
            actor_id=actor['sub'],
            entity_type='application',
            entity_id=application_id,
            payload={
                'job_id': job_id,
                'member_id': member_id,
                'resume_ref': payload.get('resume_ref'),
                'status': 'submitted',
                'city': payload.get('city') or job.get('city') or 'San Jose',
            },
            trace=trc,
            idempotency_key=key,
        )
        try:
            row = self.repo.create_with_outbox(payload_with_member, 'application.submitted', event)
            log_event(self.logger, 'application_submit_persisted', trace_id=trc, action='submit', route=route, application_id=application_id, member_id=member_id, job_id=job_id, recruiter_id=job.get('recruiter_id'), outbox_topic='application.submitted', idempotency_key=event.get('idempotency_key'))
        except Exception as exc:
            log_event(self.logger, 'application_submit_failed', trace_id=trc, action='submit', route=route, application_id=application_id, member_id=member_id, job_id=job_id, recruiter_id=job.get('recruiter_id'), error_code='application_submit_failed', error_message=str(exc))
            return fail('application_submit_failed', f'Failed to submit application: {str(exc)}', trc, status_code=500)
        meta = {'event_dispatch': 'queued'}
        response = {'trace_id': trc, 'data': {'application_id': row['application_id'], 'job_id': row.get('job_id'), 'member_id': row.get('member_id'), 'status': 'submitted', 'application_datetime': row.get('application_datetime') or applied_at}, 'meta': meta}
        record_idempotency(route, key, h, response)
        log_event(self.logger, 'application_submit_succeeded', trace_id=trc, action='submit', route=route, application_id=row['application_id'], member_id=row.get('member_id'), job_id=row.get('job_id'), status='submitted', idempotency_key=key)
        return success(response['data'], trc, response['meta'])

    def start_application(self, payload, authorization, trc):
        try:
            actor = require_auth(authorization)
        except Exception:
            log_event(self.logger, 'application_start_auth_failed', trace_id=trc, action='start', route='/applications/start', job_id=payload.get('job_id'), error_code='auth_required')
            return fail('auth_required', 'Missing, expired, or invalid bearer token.', trc, status_code=401)
        if actor['role'] != 'member':
            log_event(self.logger, 'application_start_forbidden', trace_id=trc, action='start', route='/applications/start', actor_id=actor.get('sub'), actor_role=actor.get('role'), job_id=payload.get('job_id'), error_code='forbidden')
            return fail('forbidden', 'Member role only.', trc, status_code=403)
        job_id = payload.get('job_id')
        if not job_id:
            return fail('validation_error', 'job_id is required.', trc, status_code=400)
        job = self.jobs_repo.get(job_id)
        if not job:
            return fail('job_not_found', 'Job not found.', trc, status_code=404)
        event = build_event(
            event_type='application.started',
            actor_id=actor['sub'],
            entity_type='job',
            entity_id=job_id,
            payload={'job_id': job_id, 'member_id': actor['sub']},
            trace=trc,
            idempotency_key=f"application.started:{job_id}:{actor['sub']}:{payload.get('session_id') or trc}",
        )
        self.outbox.enqueue(topic='application.started', event=event, aggregate_type='job', aggregate_id=job_id)
        log_event(self.logger, 'application_start_recorded', trace_id=trc, action='start', route='/applications/start', member_id=actor.get('sub'), job_id=job_id, outbox_topic='application.started')
        return success({'job_id': job_id, 'started': True}, trc, {'event_dispatch': 'queued'})

    def get_application(self, payload, authorization, trc):
        try:
            actor = require_auth(authorization)
        except Exception:
            log_event(self.logger, 'application_get_auth_failed', trace_id=trc, action='get', route='/applications/get', application_id=payload.get('application_id'), error_code='auth_required')
            return fail('auth_required', 'Missing, expired, or invalid bearer token.', trc, status_code=401)
        app_row = self.repo.get(payload.get('application_id'))
        if not app_row:
            log_event(self.logger, 'application_get_not_found', trace_id=trc, action='get', route='/applications/get', actor_id=actor.get('sub'), application_id=payload.get('application_id'), error_code='not_found')
            return fail('not_found', 'Application not found.', trc, status_code=404)
        full = dict(app_row)
        full['notes'] = self.repo.notes_for_application(app_row['application_id'])
        log_event(self.logger, 'application_get_succeeded', trace_id=trc, action='get', route='/applications/get', actor_id=actor.get('sub'), actor_role=actor.get('role'), application_id=app_row.get('application_id'), member_id=app_row.get('member_id'), job_id=app_row.get('job_id'), status=app_row.get('status'))
        return success({'application': full}, trc)

    def by_job(self, payload, authorization, trc):
        try:
            actor = require_auth(authorization)
        except Exception:
            log_event(self.logger, 'applications_by_job_auth_failed', trace_id=trc, action='by_job', route='/applications/byJob', job_id=payload.get('job_id'), error_code='auth_required')
            return fail('auth_required', 'Missing, expired, or invalid bearer token.', trc, status_code=401)
        if actor['role'] not in {'recruiter', 'admin'}:
            log_event(self.logger, 'applications_by_job_forbidden', trace_id=trc, action='by_job', route='/applications/byJob', actor_id=actor.get('sub'), actor_role=actor.get('role'), job_id=payload.get('job_id'), error_code='forbidden')
            return fail('forbidden', 'Only recruiters who can access this job may list its applications.', trc, status_code=403)
        items = [{'application_id': a['application_id'], 'member_id': a.get('member_id'), 'first_name': a.get('first_name'), 'last_name': a.get('last_name'), 'headline': a.get('headline'), 'profile_photo_url': a.get('profile_photo_url'), 'resume_url': a.get('resume_url'), 'status': a.get('status') or 'submitted', 'applied_at': a.get('application_datetime')} for a in self.repo.list_by_job(payload.get('job_id'))]
        log_event(self.logger, 'applications_by_job_succeeded', trace_id=trc, action='by_job', route='/applications/byJob', actor_id=actor.get('sub'), job_id=payload.get('job_id'), results=len(items))
        return success({'items': items}, trc, {'total': len(items)})

    def by_member(self, payload, authorization, trc):
        try:
            actor = require_auth(authorization)
        except Exception:
            log_event(self.logger, 'applications_by_member_auth_failed', trace_id=trc, action='by_member', route='/applications/byMember', error_code='auth_required')
            return fail('auth_required', 'Missing, expired, or invalid bearer token.', trc, status_code=401)
        member_id = actor['sub']
        items = [{'application_id': a['application_id'], 'job_id': a.get('job_id'), 'title': a.get('title') or a.get('job_id'), 'company_name': a.get('company_name'), 'status': a.get('status') or 'submitted', 'applied_at': a.get('application_datetime')} for a in self.repo.list_by_member(member_id)]
        log_event(self.logger, 'applications_by_member_succeeded', trace_id=trc, action='by_member', route='/applications/byMember', member_id=member_id, results=len(items))
        return success({'items': items}, trc, {'total': len(items)})

    async def update_status(self, payload, authorization, trc, idempotency_key=None):
        log_event(self.logger, 'application_status_update_received', trace_id=trc, action='update_status', route='/applications/updateStatus', application_id=payload.get('application_id'), requested_status=payload.get('new_status') or payload.get('status'), idempotency_key=idempotency_key)
        try:
            actor = require_auth(authorization)
        except Exception:
            log_event(self.logger, 'application_status_update_auth_failed', trace_id=trc, action='update_status', route='/applications/updateStatus', application_id=payload.get('application_id'), error_code='auth_required')
            return fail('auth_required', 'Missing, expired, or invalid bearer token.', trc, status_code=401)
        if actor['role'] not in {'recruiter', 'admin'}:
            log_event(self.logger, 'application_status_update_forbidden', trace_id=trc, action='update_status', route='/applications/updateStatus', actor_id=actor.get('sub'), actor_role=actor.get('role'), application_id=payload.get('application_id'), error_code='forbidden')
            return fail('forbidden', 'Recruiter/admin only.', trc, status_code=403)
        current = self.repo.get(payload.get('application_id'))
        if not current:
            log_event(self.logger, 'application_status_update_not_found', trace_id=trc, action='update_status', route='/applications/updateStatus', actor_id=actor.get('sub'), application_id=payload.get('application_id'), error_code='not_found')
            return fail('not_found', 'Requested entity does not exist.', trc, status_code=404)
        old = current.get('status', 'submitted')
        new = payload.get('new_status') or payload.get('status')
        if old == 'submitted' and new == 'offer':
            log_event(self.logger, 'application_status_update_invalid_transition', trace_id=trc, action='update_status', route='/applications/updateStatus', actor_id=actor.get('sub'), application_id=payload.get('application_id'), member_id=current.get('member_id'), job_id=current.get('job_id'), previous_status=old, requested_status=new, error_code='invalid_status_transition')
            return fail('invalid_status_transition', 'Cannot move application directly from submitted to offer.', trc, {'current_status': old, 'requested_status': new}, False, 422)
        event = build_event(event_type='application.status.updated', actor_id=actor['sub'], entity_type='application', entity_id=payload.get('application_id'), payload={'member_id': current.get('member_id'), 'job_id': current.get('job_id'), 'status': new, 'previous_status': old}, trace=trc, idempotency_key=idempotency_key or f'{payload.get("application_id")}:{new}')
        try:
            app_row, _ = self.repo.update_status_with_outbox(payload.get('application_id'), new, 'application.status.updated', event)
            log_event(self.logger, 'application_status_update_persisted', trace_id=trc, action='update_status', route='/applications/updateStatus', actor_id=actor.get('sub'), application_id=payload.get('application_id'), member_id=current.get('member_id'), job_id=current.get('job_id'), previous_status=old, current_status=new, outbox_topic='application.status.updated', idempotency_key=event.get('idempotency_key'))
        except Exception as exc:
            log_event(self.logger, 'application_status_update_failed', trace_id=trc, action='update_status', route='/applications/updateStatus', actor_id=actor.get('sub'), application_id=payload.get('application_id'), member_id=current.get('member_id'), job_id=current.get('job_id'), previous_status=old, requested_status=new, error_code='application_update_failed', error_message=str(exc))
            return fail('application_update_failed', f'Failed to update application status: {str(exc)}', trc, status_code=500)
        try:
            job = self.jobs_repo.get(current.get('job_id')) or {}
            pretty_status = str(new or '').replace('_', ' ')
            create_notification(
                current.get('member_id'),
                'application.status.updated',
                'Application status updated',
                f"Your application for {job.get('title') or current.get('job_id') or 'this role'} is now {pretty_status}.",
                actor_id=actor['sub'],
                actor_name=actor['sub'],
                target_url='/applications',
                data={'application_id': payload.get('application_id'), 'job_id': current.get('job_id'), 'status': new, 'previous_status': old},
            )
            log_event(self.logger, 'application_status_update_notification_created', trace_id=trc, action='update_status', route='/applications/updateStatus', application_id=payload.get('application_id'), member_id=current.get('member_id'), current_status=new)
        except Exception as exc:
            log_event(self.logger, 'application_status_update_notification_failed', trace_id=trc, action='update_status', route='/applications/updateStatus', application_id=payload.get('application_id'), member_id=current.get('member_id'), current_status=new, error_message=str(exc))
        return success({'application_id': app_row['application_id'], 'previous_status': old, 'current_status': new}, trc, {'event_dispatch': 'queued'})

    def add_note(self, payload, authorization, trc):
        log_event(self.logger, 'application_note_add_received', trace_id=trc, action='add_note', route='/applications/addNote', application_id=payload.get('application_id'))
        try:
            actor = require_auth(authorization)
        except Exception:
            log_event(self.logger, 'application_note_add_auth_failed', trace_id=trc, action='add_note', route='/applications/addNote', application_id=payload.get('application_id'), error_code='auth_required')
            return fail('auth_required', 'Missing, expired, or invalid bearer token.', trc, status_code=401)
        if actor['role'] not in {'recruiter', 'admin'}:
            log_event(self.logger, 'application_note_add_forbidden', trace_id=trc, action='add_note', route='/applications/addNote', actor_id=actor.get('sub'), actor_role=actor.get('role'), application_id=payload.get('application_id'), error_code='forbidden')
            return fail('forbidden', 'Recruiter/admin only.', trc, status_code=403)
        note = self.repo.add_note({**payload, 'recruiter_id': payload.get('recruiter_id') or actor['sub']})
        event = build_event(
            event_type='application.note.added',
            actor_id=actor['sub'],
            entity_type='application',
            entity_id=payload.get('application_id'),
            payload={'application_id': payload.get('application_id'), 'note_id': note.get('note_id'), 'recruiter_id': note.get('recruiter_id'), 'visibility': note.get('visibility', 'internal')},
            trace=trc,
            idempotency_key=f"application.note.added:{note.get('note_id')}",
        )
        self.outbox.enqueue(topic='application.note.added', event=event, aggregate_type='application', aggregate_id=payload.get('application_id') or note.get('note_id'))
        log_event(self.logger, 'application_note_add_succeeded', trace_id=trc, action='add_note', route='/applications/addNote', actor_id=actor.get('sub'), recruiter_id=note.get('recruiter_id'), application_id=payload.get('application_id'), note_id=note.get('note_id'), outbox_topic='application.note.added')
        return success({'note_id': note['note_id'], 'application_id': payload.get('application_id')}, trc, {'event_dispatch': 'queued'})
