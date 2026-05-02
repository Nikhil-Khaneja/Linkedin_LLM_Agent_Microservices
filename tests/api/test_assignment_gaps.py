import time


def bootstrap_member_recruiter_job(clients):
    o2, o3, o4 = clients['owner2'], clients['owner3'], clients['owner4']
    MEMBER = clients['headers']['member']
    RECRUITER = clients['headers']['recruiter']

    o3.post('/recruiters/create', headers=RECRUITER, json={
        'recruiter_id': 'rec_120', 'name': 'Morgan Lee', 'email': 'recruiter@example.com',
        'company_name': 'Northstar Labs', 'company_industry': 'Software', 'company_size': 'medium', 'access_level': 'admin'
    })
    o2.post('/members/create', headers=MEMBER, json={
        'member_id': 'mem_501', 'first_name': 'Ava', 'last_name': 'Shah', 'email': 'ava@example.com',
        'headline': 'Data Analyst', 'skills': ['SQL', 'Python', 'FastAPI'], 'location': 'San Jose, CA'
    })
    created = o4.post('/jobs/create', headers=RECRUITER, json={
        'company_id': 'cmp_44', 'recruiter_id': 'rec_120', 'title': 'Backend Engineer',
        'description': 'Build Kafka-backed services', 'seniority_level': 'mid', 'employment_type': 'full_time',
        'location': 'San Jose, CA', 'work_mode': 'hybrid', 'skills_required': ['Python', 'Kafka', 'MySQL']
    })
    assert created.status_code == 200
    return created.json()['data']['job_id']


def test_save_jobs_flow_and_rollup(clients):
    o4, o7 = clients['owner4'], clients['owner7']
    MEMBER = clients['headers']['member']
    RECRUITER = clients['headers']['recruiter']
    job_id = bootstrap_member_recruiter_job(clients)

    saved = o4.post('/jobs/save', headers=MEMBER, json={'job_id': job_id})
    assert saved.status_code == 200
    saved_list = o4.post('/jobs/savedByMember', headers=MEMBER, json={})
    assert saved_list.status_code == 200
    assert any(item['job_id'] == job_id for item in saved_list.json()['data']['items'])

    time.sleep(0.2)
    top_saved = o7.post('/analytics/jobs/top', headers=RECRUITER, json={'metric': 'saves', 'limit': 10})
    assert top_saved.status_code == 200


def test_apply_to_closed_job_is_rejected(clients):
    o4, o5 = clients['owner4'], clients['owner5']
    MEMBER = clients['headers']['member']
    RECRUITER = clients['headers']['recruiter']
    job_id = bootstrap_member_recruiter_job(clients)

    closed = o4.post('/jobs/close', headers=RECRUITER, json={'job_id': job_id})
    assert closed.status_code == 200
    blocked = o5.post('/applications/submit', headers=MEMBER, json={
        'job_id': job_id, 'resume_ref': 'resume-501.pdf', 'idempotency_key': f'closed-{job_id}'
    })
    assert blocked.status_code == 409
    assert blocked.json()['error']['code'] == 'job_closed'


def test_application_started_and_note_events_exist(clients):
    o5, o7 = clients['owner5'], clients['owner7']
    MEMBER = clients['headers']['member']
    RECRUITER = clients['headers']['recruiter']
    job_id = bootstrap_member_recruiter_job(clients)

    started = o5.post('/applications/start', headers=MEMBER, json={'job_id': job_id, 'session_id': 'sess-1'})
    assert started.status_code == 200
    submitted = o5.post('/applications/submit', headers=MEMBER, json={
        'job_id': job_id, 'resume_ref': 'resume-501.pdf', 'idempotency_key': f'mem501-{job_id}-note'
    })
    assert submitted.status_code == 200
    app_id = submitted.json()['data']['application_id']
    noted = o5.post('/applications/addNote', headers=RECRUITER, json={'application_id': app_id, 'note_text': 'Strong candidate'})
    assert noted.status_code == 200

    time.sleep(0.2)
    funnel = o7.post('/analytics/funnel', headers=RECRUITER, json={'job_id': job_id})
    assert funnel.status_code == 200
    data = funnel.json()['data']['funnel']
    assert data['apply_started'] >= 1
    assert data['submitted'] >= 1


def test_benchmark_report_and_list(clients):
    o7 = clients['owner7']
    ADMIN = clients['headers']['admin']
    report = o7.post('/benchmarks/report', headers=ADMIN, json={
        'scenario': 'B+S+K', 'variant': 'B+S+K', 'description': 'Measured run',
        'latency_ms_avg': 55, 'latency_ms_p95': 140, 'throughput': 120, 'error_rate_pct': 0.5,
    })
    assert report.status_code == 200
    listed = o7.post('/benchmarks/list', headers=ADMIN, json={'limit': 5})
    assert listed.status_code == 200
    assert len(listed.json()['data']['items']) >= 1
