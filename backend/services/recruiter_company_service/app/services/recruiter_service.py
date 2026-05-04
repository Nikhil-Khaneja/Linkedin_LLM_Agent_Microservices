from services.shared.common import fail, require_auth, success

class RecruiterCompanyService:
    def __init__(self, repo):
        self.repo = repo

    def create_recruiter(self, payload, authorization, trc):
        try:
            actor = require_auth(authorization)
        except Exception:
            return fail('auth_required', 'Missing, expired, or invalid bearer token.', trc, status_code=401)
        if actor['role'] not in {'recruiter', 'admin'}:
            return fail('forbidden', 'Authenticated user lacks permission or role for the target action.', trc, status_code=403)
        recruiter_id = payload.get('recruiter_id') or actor['sub']
        if actor['role'] != 'admin' and actor['sub'] != recruiter_id:
            return fail('forbidden', 'You can only create your own recruiter profile.', trc, status_code=403)
        if payload.get('email') and self.repo.email_exists(payload['email']):
            existing = self.repo.get_recruiter(recruiter_id)
            if existing:
                return success({'recruiter_id': recruiter_id, 'company_id': existing.get('company_id'), 'status': 'active'}, trc)
            return fail('duplicate_recruiter_email', 'A recruiter with this email already exists.', trc, status_code=409)
        company_id = payload.get('company_id') or f"cmp_{recruiter_id.split('_')[-1]}"
        recruiter = {
            **payload,
            'recruiter_id': recruiter_id,
            'company_id': company_id,
            'name': payload.get('name') or actor.get('email', 'Recruiter').split('@')[0],
            'email': payload.get('email') or actor.get('email'),
            'access_level': payload.get('access_level') or 'admin',
        }
        company = {
            'company_id': company_id,
            'company_name': payload.get('company_name') or 'Your Company',
            'company_industry': payload.get('company_industry') or 'General',
            'company_size': payload.get('company_size') or 'medium',
        }
        try:
            self.repo.create(recruiter, company)
        except Exception:
            existing = self.repo.get_recruiter(recruiter_id)
            if existing:
                return success({'recruiter_id': recruiter_id, 'company_id': existing.get('company_id'), 'status': 'active'}, trc)
            return fail('duplicate_recruiter_email', 'A recruiter with this email already exists.', trc, status_code=409)
        return success({'recruiter_id': recruiter_id, 'company_id': company_id, 'status': 'active'}, trc)

    def get_recruiter(self, payload, authorization, trc):
        try:
            actor = require_auth(authorization)
        except Exception:
            return fail('auth_required', 'Missing, expired, or invalid bearer token.', trc, status_code=401)
        recruiter_id = payload.get('recruiter_id') or actor.get('sub')
        recruiter = self.repo.get_recruiter(recruiter_id)
        if not recruiter:
            return fail('not_found', 'Recruiter record not found.', trc, status_code=404)
        company = self.repo.get_company(recruiter.get('company_id')) or {}
        return success({'recruiter': {**recruiter, 'company_name': company.get('company_name'), 'company_industry': company.get('company_industry'), 'company_size': company.get('company_size')}}, trc)

    def update_recruiter(self, payload, authorization, trc):
        try:
            actor = require_auth(authorization)
        except Exception:
            return fail('auth_required', 'Missing, expired, or invalid bearer token.', trc, status_code=401)
        recruiter_id = payload.get('recruiter_id') or actor.get('sub')
        recruiter = self.repo.get_recruiter(recruiter_id)
        if not recruiter:
            return fail('not_found', 'Requested entity does not exist.', trc, status_code=404)
        if actor['role'] != 'admin' and actor['sub'] != recruiter_id:
            return fail('forbidden', 'Authenticated user lacks permission or role for the target action.', trc, status_code=403)
        updated = self.repo.update_recruiter(recruiter_id, payload)
        return success({'recruiter_id': recruiter_id, 'updated': True, 'recruiter': updated}, trc)

    def create_company(self, payload, authorization, trc):
        try:
            actor = require_auth(authorization)
        except Exception:
            return fail('auth_required', 'Missing, expired, or invalid bearer token.', trc, status_code=401)
        if actor['role'] not in {'recruiter', 'admin'}:
            return fail('forbidden', 'Recruiter/admin only.', trc, status_code=403)
        recruiter_id = payload.get('recruiter_id') or actor.get('sub')
        if actor['role'] != 'admin' and actor['sub'] != recruiter_id:
            return fail('forbidden', 'You can only manage your own company.', trc, status_code=403)
        recruiter = self.repo.get_recruiter(recruiter_id)
        if recruiter and recruiter.get('company_id'):
            updated = self.repo.update_company(recruiter['company_id'], payload)
            self.repo.update_recruiter(recruiter_id, {'company_name': updated.get('company_name'), 'company_industry': updated.get('company_industry'), 'company_size': updated.get('company_size')})
            return success({'company': updated, 'updated': True}, trc)
        company_id = payload.get('company_id') or f"cmp_{recruiter_id.split('_')[-1]}"
        company = self.repo.create_company({
            'company_id': company_id,
            'company_name': payload.get('company_name') or 'Your Company',
            'company_industry': payload.get('company_industry') or 'General',
            'company_size': payload.get('company_size') or 'medium',
        })
        if recruiter:
            self.repo.update_recruiter(recruiter_id, {'company_id': company_id, 'company_name': company.get('company_name'), 'company_industry': company.get('company_industry'), 'company_size': company.get('company_size')})
        return success({'company': company, 'updated': False}, trc)

    def update_company(self, payload, authorization, trc):
        try:
            actor = require_auth(authorization)
        except Exception:
            return fail('auth_required', 'Missing, expired, or invalid bearer token.', trc, status_code=401)
        if actor['role'] not in {'recruiter', 'admin'}:
            return fail('forbidden', 'Recruiter/admin only.', trc, status_code=403)
        recruiter_id = payload.get('recruiter_id') or actor.get('sub')
        if actor['role'] != 'admin' and actor['sub'] != recruiter_id:
            return fail('forbidden', 'You can only manage your own company.', trc, status_code=403)
        recruiter = self.repo.get_recruiter(recruiter_id)
        company_id = payload.get('company_id') or (recruiter or {}).get('company_id')
        if not company_id:
            return fail('not_found', 'Company not found.', trc, status_code=404)
        company = self.repo.update_company(company_id, payload)
        if not company:
            return fail('not_found', 'Company not found.', trc, status_code=404)
        if recruiter:
            self.repo.update_recruiter(recruiter_id, {'company_name': company.get('company_name'), 'company_industry': company.get('company_industry'), 'company_size': company.get('company_size')})
        return success({'company': company}, trc)

    def get_company(self, payload, authorization, trc):
        try:
            actor = require_auth(authorization)
        except Exception:
            return fail('auth_required', 'Missing, expired, or invalid bearer token.', trc, status_code=401)
        company_id = payload.get('company_id')
        if not company_id and actor['role'] == 'recruiter':
            recruiter = self.repo.get_recruiter(payload.get('recruiter_id') or actor.get('sub'))
            company_id = (recruiter or {}).get('company_id')
        company = self.repo.get_company(company_id) if company_id else None
        if not company:
            return fail('not_found', 'Company not found.', trc, status_code=404)
        return success({'company': company}, trc)


    def public_get_recruiter(self, payload, authorization, trc):
        try:
            require_auth(authorization)
        except Exception:
            return fail('auth_required', 'Missing, expired, or invalid bearer token.', trc, status_code=401)
        recruiter_id = payload.get('recruiter_id')
        if not recruiter_id:
            return fail('validation_error', 'recruiter_id is required.', trc, status_code=400)
        recruiter = self.repo.get_recruiter(recruiter_id)
        if not recruiter:
            return fail('not_found', 'Recruiter record not found.', trc, status_code=404)
        company = self.repo.get_company(recruiter.get('company_id')) or {}
        public_profile = {
            'recruiter_id': recruiter.get('recruiter_id'),
            'name': recruiter.get('name'),
            'headline': recruiter.get('access_level') or 'Recruiter',
            'access_level': recruiter.get('access_level'),
            'company_id': recruiter.get('company_id'),
            'company_name': company.get('company_name'),
            'company_industry': company.get('company_industry'),
            'company_size': company.get('company_size'),
            'profile_photo_url': recruiter.get('profile_photo_url'),
        }
        return success({'recruiter': public_profile}, trc)

    def search_recruiters(self, payload, authorization, trc):
        try:
            actor = require_auth(authorization)
        except Exception:
            return fail('auth_required', 'Missing, expired, or invalid bearer token.', trc, status_code=401)
        if actor['role'] not in {'member', 'recruiter', 'admin'}:
            return fail('forbidden', 'You are not allowed to search recruiters.', trc, status_code=403)
        keyword = (payload.get('keyword') or '').strip()
        if not keyword:
            return success({'items': []}, trc, {'total': 0})
        try:
            page_size = int(payload.get('page_size') or 50)
        except (TypeError, ValueError):
            page_size = 50
        page_size = max(1, min(page_size, 500))
        try:
            page = int(payload.get('page') or 1)
        except (TypeError, ValueError):
            page = 1
        page = max(1, page)
        offset = (page - 1) * page_size
        items = self.repo.search_recruiters(keyword, limit=page_size, offset=offset)
        if actor['role'] == 'recruiter':
            items = [r for r in items if r.get('recruiter_id') != actor.get('sub')]
        return success({'items': items}, trc, {'total': len(items), 'page': page, 'page_size': page_size})
