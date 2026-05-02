import requests
import time

BASE = {
    'auth': 'http://localhost:8001',
    'member': 'http://localhost:8002',
    'recruiter': 'http://localhost:8003',
    'jobs': 'http://localhost:8004',
    'applications': 'http://localhost:8005',
    'messaging': 'http://localhost:8006',
    'analytics': 'http://localhost:8007',
}


def post(base, path, body=None, headers=None, allow_conflict=False):
    r = requests.post(f"{BASE[base]}{path}", json=body or {}, headers=headers or {}, timeout=15)
    try:
        data = r.json()
    except Exception:
        raise RuntimeError(f"{base}{path} returned non-JSON: {r.status_code} {r.text}")
    if r.status_code >= 400 and not (allow_conflict and r.status_code == 409):
        raise RuntimeError(f"{base}{path} failed: {r.status_code} {data}")
    return data


def auth_headers(token: str):
    return {"Authorization": f"Bearer {token}"}


def get_data(resp):
    return resp.get("data", resp)


def main():
    print('Registering demo users...')
    post('auth', '/auth/register', {
        'email': 'ava@example.com', 'password': 'StrongPass#1', 'user_type': 'member', 'first_name': 'Ava', 'last_name': 'Shah'
    }, allow_conflict=True)
    post('auth', '/auth/register', {
        'email': 'recruiter@example.com', 'password': 'RecruiterPass#1', 'user_type': 'recruiter', 'first_name': 'Morgan', 'last_name': 'Lee'
    }, allow_conflict=True)

    print('Logging in...')
    member_login = post('auth', '/auth/login', {'email': 'ava@example.com', 'password': 'StrongPass#1'})
    recruiter_login = post('auth', '/auth/login', {'email': 'recruiter@example.com', 'password': 'RecruiterPass#1'})
    member_token = get_data(member_login)['access_token']
    recruiter_token = get_data(recruiter_login)['access_token']
    HEADERS_MEMBER = auth_headers(member_token)
    HEADERS_RECRUITER = auth_headers(recruiter_token)

    print('Creating recruiter/company...')
    recruiter_resp = post('recruiter', '/recruiters/create', {
        'recruiter_id': 'rec_120',
        'name': 'Morgan Lee',
        'email': 'recruiter@example.com',
        'company_name': 'Northstar Labs',
        'company_industry': 'Software',
        'company_size': 'medium',
        'access_level': 'admin'
    }, HEADERS_RECRUITER, allow_conflict=True)
    recruiter_data = get_data(recruiter_resp) if isinstance(recruiter_resp, dict) else {}
    recruiter_id = recruiter_data.get('recruiter_id', 'rec_120')
    company_id = recruiter_data.get('company_id', 'cmp_44')

    print('Creating member profile...')
    post('member', '/members/create', {
        'member_id': 'mem_501',
        'first_name': 'Ava',
        'last_name': 'Shah',
        'email': 'ava@example.com',
        'headline': 'Applied Data Science Student',
        'skills': ['SQL', 'Python', 'FastAPI'],
        'city': 'San Jose',
        'state': 'CA',
        'location': 'San Jose, CA'
    }, HEADERS_MEMBER, allow_conflict=True)

    print('Creating jobs...')
    created_job_ids = []
    for i in range(1, 11):
        resp = post('jobs', '/jobs/create', {
            'company_id': company_id,
            'recruiter_id': recruiter_id,
            'title': f'Backend Engineer {i}',
            'description': f'Build software and distributed services in San Jose for class project #{i}.',
            'seniority_level': 'mid',
            'employment_type': 'full_time',
            'location': 'San Jose, CA',
            'work_mode': 'hybrid',
            'skills_required': ['Python', 'Kafka', 'MySQL']
        }, HEADERS_RECRUITER, allow_conflict=True)
        job_id = get_data(resp).get('job_id') if isinstance(resp, dict) else None
        if job_id:
            created_job_ids.append(job_id)
    first_job_id = created_job_ids[0] if created_job_ids else 'job_3301'

    print('Submitting application...')
    post('applications', '/applications/submit', {
        'job_id': first_job_id,
        'member_id': 'mem_501',
        'resume_ref': 'resume-501.pdf',
        'cover_letter': 'Excited to apply.',
        'idempotency_key': f'mem501-{first_job_id}-v1'
    }, HEADERS_MEMBER, allow_conflict=True)

    print('Opening thread and sending message...')
    thread = post('messaging', '/threads/open', {'participant_ids': ['mem_501', 'rec_120']}, HEADERS_MEMBER)
    thread_id = get_data(thread).get('thread_id', 'thr_901')
    post('messaging', '/messages/send', {'thread_id': thread_id, 'text': 'Hi recruiter, I applied for the role.', 'client_message_id': f'seed-{int(time.time())}'}, HEADERS_MEMBER)
    post('messaging', '/connections/request', {'requester_id': 'mem_501', 'receiver_id': 'rec_120', 'message': 'Would love to connect.'}, HEADERS_MEMBER, allow_conflict=True)

    print('Sending analytics event...')
    post('analytics', '/events/ingest', {
        'event_type': 'application.submitted',
        'timestamp': '2026-04-25T21:00:00Z',
        'actor_id': 'mem_501',
        'entity': {'entity_type': 'job', 'entity_id': first_job_id},
        'payload': {'city': 'San Jose', 'member_id': 'mem_501', 'status': 'submitted', 'job_id': first_job_id}
    }, HEADERS_MEMBER, allow_conflict=True)

    print('Demo seed complete.')


if __name__ == '__main__':
    main()
