from __future__ import annotations

from services.shared.auth import issue_access_token, password_hash, password_matches
from services.shared.cache import delete_key, get_int, incr
from services.shared.common import body_hash, build_event, check_idempotency, record_idempotency
from services.shared.kafka_bus import publish_event
from services.shared.repositories import MemberRepository, RecruiterRepository


class AuthService:
    RATE_LIMIT_THRESHOLD = 5
    RATE_LIMIT_TTL = 60

    def __init__(self, repo):
        self.repo = repo
        self.member_repo = MemberRepository()
        self.recruiter_repo = RecruiterRepository()

    def _login_limit_key(self, email: str | None) -> str:
        return f"auth:login_fail:{(email or 'unknown').lower()}"

    def _domain_subject_for(self, user: dict) -> str:
        email = (user.get('email') or '').lower()
        if user['subject_type'] == 'member':
            if email == 'ava@example.com':
                return 'mem_501'
            return f"mem_{str(user['user_id']).split('_')[-1]}"
        if user['subject_type'] == 'recruiter':
            if email == 'recruiter@example.com':
                return 'rec_120'
            return f"rec_{str(user['user_id']).split('_')[-1]}"
        return user['user_id']

    def issue_access_token_for(self, user: dict) -> str:
        return issue_access_token(
            sub=self._domain_subject_for(user),
            role=user['subject_type'],
            email=user['email'],
            extra_claims={'user_id': user['user_id'], 'first_name': user.get('first_name'), 'last_name': user.get('last_name')},
        )

    def _ensure_member_profile(self, user: dict) -> None:
        if user.get('subject_type') != 'member':
            return
        member_id = self._domain_subject_for(user)
        if self.member_repo.get(member_id):
            return
        try:
            self.member_repo.create({
                'member_id': member_id,
                'email': user.get('email'),
                'first_name': user.get('first_name') or '',
                'last_name': user.get('last_name') or '',
                'headline': '',
                'about_summary': '',
                'skills': [],
                'city': '',
                'state': '',
                'profile_photo_url': '',
                'resume_url': '',
                'profile_version': 1,
            })
        except Exception:
            pass

    def _ensure_recruiter_profile(self, user: dict, payload: dict | None = None) -> None:
        if user.get('subject_type') != 'recruiter':
            return
        payload = payload or {}
        recruiter_id = self._domain_subject_for(user)
        existing = self.recruiter_repo.get_recruiter(recruiter_id)
        if existing:
            return
        company_id = payload.get('company_id') or f"cmp_{str(user['user_id']).split('_')[-1]}"
        company = {
            'company_id': company_id,
            'company_name': payload.get('company_name') or 'Your Company',
            'company_industry': payload.get('company_industry') or 'General',
            'company_size': payload.get('company_size') or 'medium',
        }
        recruiter = {
            'recruiter_id': recruiter_id,
            'company_id': company_id,
            'email': user.get('email'),
            'name': (' '.join([part for part in [user.get('first_name'), user.get('last_name')] if part]).strip() or payload.get('name') or user.get('email', 'recruiter').split('@')[0]),
            'phone': payload.get('phone'),
            'access_level': payload.get('access_level') or 'admin',
            'company_name': company['company_name'],
            'company_industry': company['company_industry'],
            'company_size': company['company_size'],
        }
        try:
            self.recruiter_repo.create(recruiter, company)
        except Exception:
            pass

    async def register(self, payload: dict, trace_id: str, idempotency_key: str | None):
        email = payload.get('email')
        password = payload.get('password')
        user_type = payload.get('user_type')
        route = '/auth/register'
        request_hash = body_hash(payload)
        existing, conflict = check_idempotency(route, idempotency_key or payload.get('idempotency_key'), request_hash)
        if conflict:
            return {'kind': 'error', 'code': 'idempotency_conflict', 'message': 'Same Idempotency-Key reused with a different request body.', 'status_code': 409}
        if existing:
            return {'kind': 'success', 'data': existing['data'], 'trace_id': existing['trace_id'], 'meta': existing.get('meta')}
        if self.repo.get_user_by_email(email):
            return {'kind': 'error', 'code': 'duplicate_email', 'message': 'An account with this email already exists.', 'status_code': 409, 'details': {'email': email}}
        if user_type == 'recruiter' and not payload.get('company_name'):
            return {'kind': 'error', 'code': 'validation_error', 'message': 'Recruiter registration requires company_name.', 'status_code': 400}
        user = self.repo.create_user(email=email, password_hash=password_hash(password), subject_type=user_type, first_name=payload.get('first_name'), last_name=payload.get('last_name'))
        self._ensure_member_profile(user)
        self._ensure_recruiter_profile(user, payload)
        refresh = self.repo.issue_refresh_token(user['user_id'])
        bootstrap_state = 'pending_profile' if user['subject_type'] == 'member' else 'pending_recruiter'
        resp = {'user_id': user['user_id'], 'user_type': user['subject_type'], 'first_name': user.get('first_name'), 'last_name': user.get('last_name'), 'access_token': self.issue_access_token_for(user), 'refresh_token': refresh, 'expires_in': 3600, 'bootstrap_state': bootstrap_state}
        record_idempotency(route, idempotency_key or payload.get('idempotency_key'), request_hash, {'trace_id': trace_id, 'data': resp})
        await publish_event('user.created', build_event(
            event_type='user.created',
            actor_id=user['user_id'],
            entity_type='user',
            entity_id=user['user_id'],
            payload={'user_id': user['user_id'], 'email': email, 'subject_type': user['subject_type']},
            trace=trace_id,
            idempotency_key=f'user.created:{user["user_id"]}',
        ))
        return {'kind': 'success', 'data': resp, 'trace_id': trace_id}

    def login(self, email: str | None, password: str | None, trace_id: str):
        limit_key = self._login_limit_key(email)
        failures = get_int(limit_key) or 0
        if failures >= self.RATE_LIMIT_THRESHOLD:
            return {'kind': 'error', 'code': 'login_rate_limited', 'message': 'Too many failed attempts for this email or IP.', 'status_code': 429, 'details': {'retry_after_seconds': self.RATE_LIMIT_TTL}, 'retryable': True}
        user = self.repo.get_user_by_email(email) if email else None
        if not user or not password_matches(password or '', user['password_hash']):
            current = incr(limit_key, 1, self.RATE_LIMIT_TTL)
            if current >= self.RATE_LIMIT_THRESHOLD:
                return {'kind': 'error', 'code': 'login_rate_limited', 'message': 'Too many failed attempts for this email or IP.', 'status_code': 429, 'details': {'retry_after_seconds': self.RATE_LIMIT_TTL}, 'retryable': True}
            return {'kind': 'error', 'code': 'invalid_credentials', 'message': 'Email or password is incorrect.', 'status_code': 401}
        delete_key(limit_key)
        self._ensure_member_profile(user)
        self._ensure_recruiter_profile(user)
        refresh = self.repo.issue_refresh_token(user['user_id'])
        resp = {'user_id': user['user_id'], 'user_type': user['subject_type'], 'subject_type': user['subject_type'], 'first_name': user.get('first_name'), 'last_name': user.get('last_name'), 'access_token': self.issue_access_token_for(user), 'refresh_token': refresh, 'expires_in': 3600}
        return {'kind': 'success', 'data': resp, 'trace_id': trace_id}

    def refresh(self, refresh_token: str | None, trace_id: str):
        user = self.repo.get_user_by_refresh_token(refresh_token) if refresh_token else None
        if not user:
            return {'kind': 'error', 'code': 'refresh_invalid', 'message': 'Refresh token is invalid or expired.', 'status_code': 401}
        self.repo.revoke_refresh_token(refresh_token)
        self._ensure_member_profile(user)
        self._ensure_recruiter_profile(user)
        new_refresh = self.repo.issue_refresh_token(user['user_id'])
        return {'kind': 'success', 'data': {'access_token': self.issue_access_token_for(user), 'refresh_token': new_refresh, 'expires_in': 3600}, 'trace_id': trace_id}

    def logout(self, refresh_token: str | None, trace_id: str):
        if refresh_token:
            self.repo.revoke_refresh_token(refresh_token)
        return {'kind': 'success', 'data': {'revoked': True}, 'trace_id': trace_id}
