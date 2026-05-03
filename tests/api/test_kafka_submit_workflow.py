import time
import uuid


def _bootstrap_job(clients):
    o2, o3, o4 = clients['owner2'], clients['owner3'], clients['owner4']
    member = clients['headers']['member']
    recruiter = clients['headers']['recruiter']
    o3.post('/recruiters/create', headers=recruiter, json={
        'recruiter_id': 'rec_120', 'name': 'Morgan Lee', 'email': 'recruiter@example.com',
        'company_name': 'Northstar Labs', 'company_industry': 'Software', 'company_size': 'medium', 'access_level': 'admin',
    })
    o2.post('/members/create', headers=member, json={
        'member_id': 'mem_501', 'first_name': 'Ava', 'last_name': 'Shah', 'email': 'ava@example.com',
        'headline': 'Data Analyst', 'skills': ['SQL', 'Python', 'FastAPI'], 'location': 'San Jose, CA',
    })
    created = o4.post('/jobs/create', headers=recruiter, json={
        'company_id': 'cmp_44', 'recruiter_id': 'rec_120', 'title': f'Kafka submit job {uuid.uuid4().hex[:8]}',
        'description': 'Kafka-first apply test', 'seniority_level': 'mid', 'employment_type': 'full_time',
        'location': 'San Jose, CA', 'work_mode': 'hybrid', 'skills_required': ['Python', 'Kafka', 'MySQL'],
    })
    assert created.status_code == 200
    job_id = created.json()['data']['job_id']
    for _ in range(120):
        g = o4.post('/jobs/get', headers=recruiter, json={'job_id': job_id})
        if g.status_code == 200 and (g.json().get('meta') or {}).get('write_state') == 'committed':
            return job_id
        time.sleep(0.1)
    raise AssertionError('job did not reach committed after create')


def test_submit_kafka_first_then_row_exists(monkeypatch, clients):
    monkeypatch.setenv('APPLICATION_SUBMIT_KAFKA_FIRST', 'true')
    job_id = _bootstrap_job(clients)
    o5 = clients['owner5']
    MEMBER = clients['headers']['member']
    key = f'kafka-first-{job_id}'
    r = o5.post(
        '/applications/submit',
        headers=MEMBER,
        json={'job_id': job_id, 'resume_ref': 'resume-kf.pdf', 'idempotency_key': key},
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get('success') is True
    assert body.get('meta', {}).get('async') is True
    assert body['data']['status'] == 'accepted'
    app_id = body['data']['application_id']

    last = None
    o7 = clients['owner7']
    RECRUITER = clients['headers']['recruiter']
    for _ in range(200):
        o5.post('/applications/get', headers=MEMBER, json={'application_id': app_id})
        o7.post('/analytics/funnel', headers=RECRUITER, json={'job_id': job_id})
        last = o5.post('/applications/get', headers=MEMBER, json={'application_id': app_id})
        if last.status_code == 200:
            break
        time.sleep(0.05)
    assert last.status_code == 200, getattr(last, 'text', last)
    assert last.json()['data']['application']['application_id'] == app_id
