"""
Tests for all 6 required failure cases from the spec:
  1. Duplicate email on register → 409
  2. Duplicate application to same job → 409
  3. Apply to a closed job → 409 (job_closed)
  4. Message send idempotency (same key, same body → replay; same key, different body → conflict)
  5. Kafka consumer idempotency via idempotency_key header (submit replay)
  6. Multi-step partial failure: update non-existent application → 404
"""
import uuid


def _uid():
    return uuid.uuid4().hex[:8]


def _ensure_recruiter(o3, recruiter_hdr):
    """Create recruiter rec_120 if not already present (idempotent)."""
    o3.post('/recruiters/create', headers=recruiter_hdr, json={
        'recruiter_id': 'rec_120', 'name': 'Morgan Lee', 'email': 'recruiter@example.com',
        'company_name': 'Northstar Labs', 'company_industry': 'Software',
        'company_size': 'medium', 'access_level': 'admin',
    })


def test_duplicate_email_register(clients):
    o1 = clients['owner1']
    email = f"dup_{_uid()}@example.com"
    body = {'email': email, 'password': 'StrongPass#1', 'user_type': 'member', 'first_name': 'A', 'last_name': 'B'}
    r1 = o1.post('/auth/register', json=body)
    assert r1.status_code == 200

    r2 = o1.post('/auth/register', json=body | {'idempotency_key': _uid()})
    assert r2.status_code == 409
    assert r2.json()['error']['code'] == 'duplicate_email'


def test_duplicate_application(clients):
    o1, o3, o4, o5 = clients['owner1'], clients['owner3'], clients['owner4'], clients['owner5']
    RECRUITER = clients['headers']['recruiter']
    _ensure_recruiter(o3, RECRUITER)

    email = f"mem_{_uid()}@example.com"
    r = o1.post('/auth/register', json={'email': email, 'password': 'StrongPass#1', 'user_type': 'member', 'first_name': 'T', 'last_name': 'U'})
    assert r.status_code == 200
    member_token = r.json()['data']['access_token']
    member_hdr = {'Authorization': f'Bearer {member_token}'}

    r = o4.post('/jobs/create', headers=RECRUITER, json={
        'company_id': f'cmp_{_uid()}', 'recruiter_id': 'rec_120',
        'title': 'Dup Test Job', 'description': 'test', 'seniority_level': 'mid',
        'employment_type': 'full_time', 'location': 'Remote', 'work_mode': 'remote',
        'skills_required': ['Python'],
    })
    assert r.status_code == 200
    job_id = r.json()['data']['job_id']
    ikey = f'dup-app-{_uid()}'

    r1 = o5.post('/applications/submit', headers=member_hdr, json={'job_id': job_id, 'resume_ref': 'r.pdf', 'idempotency_key': ikey})
    assert r1.status_code == 202

    r2 = o5.post('/applications/submit', headers=member_hdr, json={'job_id': job_id, 'resume_ref': 'r.pdf', 'idempotency_key': f'dup-app-{_uid()}'})
    assert r2.status_code == 409
    assert r2.json()['error']['code'] == 'duplicate_application'


def test_apply_to_closed_job(clients):
    o3, o4, o5 = clients['owner3'], clients['owner4'], clients['owner5']
    RECRUITER = clients['headers']['recruiter']
    MEMBER = clients['headers']['member']
    _ensure_recruiter(o3, RECRUITER)

    r = o4.post('/jobs/create', headers=RECRUITER, json={
        'company_id': f'cmp_{_uid()}', 'recruiter_id': 'rec_120',
        'title': 'Closed Job', 'description': 'will be closed', 'seniority_level': 'entry',
        'employment_type': 'full_time', 'location': 'Remote', 'work_mode': 'remote',
        'skills_required': [],
    })
    assert r.status_code == 200
    job_id = r.json()['data']['job_id']

    close = o4.post('/jobs/close', headers=RECRUITER, json={'job_id': job_id})
    assert close.status_code == 200

    r_apply = o5.post('/applications/submit', headers=MEMBER, json={
        'job_id': job_id, 'resume_ref': 'r.pdf', 'idempotency_key': f'closed-{_uid()}',
    })
    assert r_apply.status_code == 409
    assert r_apply.json()['error']['code'] == 'job_closed'


def test_application_submit_idempotency_replay(clients):
    o1, o3, o4, o5 = clients['owner1'], clients['owner3'], clients['owner4'], clients['owner5']
    RECRUITER = clients['headers']['recruiter']
    _ensure_recruiter(o3, RECRUITER)

    email = f"mem_{_uid()}@example.com"
    r = o1.post('/auth/register', json={'email': email, 'password': 'StrongPass#1', 'user_type': 'member', 'first_name': 'T', 'last_name': 'V'})
    member_token = r.json()['data']['access_token']
    member_hdr = {'Authorization': f'Bearer {member_token}'}

    r = o4.post('/jobs/create', headers=RECRUITER, json={
        'company_id': f'cmp_{_uid()}', 'recruiter_id': 'rec_120',
        'title': 'Idem Job', 'description': 'test', 'seniority_level': 'mid',
        'employment_type': 'full_time', 'location': 'Remote', 'work_mode': 'remote',
        'skills_required': [],
    })
    job_id = r.json()['data']['job_id']
    ikey = f'idem-{_uid()}'
    body = {'job_id': job_id, 'resume_ref': 'r.pdf', 'idempotency_key': ikey}

    r1 = o5.post('/applications/submit', headers=member_hdr, json=body)
    assert r1.status_code == 202
    app_id = r1.json()['data']['application_id']

    r2 = o5.post('/applications/submit', headers=member_hdr, json=body)
    assert r2.status_code == 202
    assert r2.json()['data']['application_id'] == app_id


def test_message_send_idempotency_conflict(clients):
    o6 = clients['owner6']
    MEMBER = clients['headers']['member']
    RECRUITER = clients['headers']['recruiter']

    r = o6.post('/threads/open', headers=MEMBER, json={'participant_ids': ['mem_501', 'rec_120']})
    assert r.status_code == 200
    thread_id = r.json()['data']['thread_id']
    ikey = f'msg-idem-{_uid()}'

    r1 = o6.post('/messages/send', headers=MEMBER, json={'thread_id': thread_id, 'text': 'Hello', 'client_message_id': ikey})
    assert r1.status_code == 200

    r2 = o6.post('/messages/send', headers=MEMBER, json={'thread_id': thread_id, 'text': 'Hello', 'client_message_id': ikey})
    assert r2.status_code == 200
    assert r2.json()['data']['message_id'] == r1.json()['data']['message_id']

    r3 = o6.post('/messages/send', headers=MEMBER, json={'thread_id': thread_id, 'text': 'DIFFERENT TEXT', 'client_message_id': ikey})
    assert r3.status_code == 409
    assert r3.json()['error']['code'] == 'idempotency_conflict'


def test_update_nonexistent_application(clients):
    o5 = clients['owner5']
    RECRUITER = clients['headers']['recruiter']

    r = o5.post('/applications/updateStatus', headers=RECRUITER, json={
        'application_id': f'app_nonexistent_{_uid()}',
        'new_status': 'reviewing',
    })
    assert r.status_code == 404
    assert r.json()['error']['code'] == 'not_found'
