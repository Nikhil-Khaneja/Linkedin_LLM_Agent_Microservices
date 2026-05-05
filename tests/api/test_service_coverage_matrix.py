import time

def _seed_recruiter_member_job(clients):
    o2, o3, o4 = clients['owner2'], clients['owner3'], clients['owner4']
    member_headers = clients['headers']['member']
    recruiter_headers = clients['headers']['recruiter']

    o3.post(
        '/recruiters/create',
        headers=recruiter_headers,
        json={
            'recruiter_id': 'rec_120',
            'name': 'Morgan Lee',
            'email': 'recruiter@example.com',
            'company_name': 'Northstar Labs',
            'company_industry': 'Software',
            'company_size': 'medium',
            'access_level': 'admin',
        },
    )
    o2.post(
        '/members/create',
        headers=member_headers,
        json={
            'member_id': 'mem_501',
            'first_name': 'Ava',
            'last_name': 'Shah',
            'email': 'ava@example.com',
            'headline': 'Data Analyst',
            'skills': ['SQL', 'Python'],
            'location': 'San Jose, CA',
        },
    )
    created = o4.post(
        '/jobs/create',
        headers=recruiter_headers,
        json={
            'company_id': 'cmp_44',
            'recruiter_id': 'rec_120',
            'title': 'Backend Engineer',
            'description': 'Build Kafka-backed services',
            'seniority_level': 'mid',
            'employment_type': 'full_time',
            'location': 'San Jose, CA',
            'work_mode': 'hybrid',
            'skills_required': ['Python', 'Kafka', 'MySQL'],
        },
    )
    assert created.status_code == 200
    return created.json()['data']['job_id']


def test_healthz_for_all_services(clients):
    service_clients = [
        clients['owner1'],
        clients['owner2'],
        clients['owner3'],
        clients['owner4'],
        clients['owner5'],
        clients['owner6'],
        clients['owner7'],
        clients['owner8'],
    ]
    for c in service_clients:
        res = c.get('/ops/healthz')
        assert res.status_code == 200
        assert res.json().get('status') == 'ok'


def test_auth_service_register_login_refresh(clients):
    auth = clients['owner1']
    reg = auth.post(
        '/auth/register',
        json={
            'email': 'matrix-user@example.com',
            'password': 'StrongPass#1',
            'user_type': 'member',
            'first_name': 'Matrix',
            'last_name': 'User',
        },
    )
    assert reg.status_code == 200
    login = auth.post('/auth/login', json={'email': 'matrix-user@example.com', 'password': 'StrongPass#1'})
    assert login.status_code == 200
    refresh = auth.post('/auth/refresh', json={'refresh_token': login.json()['data']['refresh_token']})
    assert refresh.status_code == 200


def test_member_and_recruiter_services_get_paths(clients):
    member = clients['owner2']
    recruiter = clients['owner3']
    member_headers = clients['headers']['member']
    recruiter_headers = clients['headers']['recruiter']

    r = recruiter.post(
        '/recruiters/create',
        headers=recruiter_headers,
        json={
            'recruiter_id': 'rec_120',
            'name': 'Morgan Lee',
            'email': 'recruiter@example.com',
            'company_name': 'Northstar Labs',
        },
    )
    assert r.status_code == 200
    assert recruiter.post('/recruiters/get', headers=recruiter_headers, json={'recruiter_id': 'rec_120'}).status_code == 200

    c = member.post(
        '/members/create',
        headers=member_headers,
        json={
            'member_id': 'mem_501',
            'first_name': 'Ava',
            'last_name': 'Shah',
            'email': 'ava@example.com',
            'headline': 'Data Analyst',
            'skills': ['Python'],
            'location': 'San Jose, CA',
        },
    )
    assert c.status_code == 200
    assert member.post('/members/get', headers=member_headers, json={'member_id': 'mem_501'}).status_code == 200


def test_jobs_and_applications_services_core_flows(clients):
    jobs = clients['owner4']
    apps = clients['owner5']
    member_headers = clients['headers']['member']
    recruiter_headers = clients['headers']['recruiter']

    job_id = _seed_recruiter_member_job(clients)
    assert jobs.post('/jobs/get', headers=member_headers, json={'job_id': job_id}).status_code == 200
    submitted = apps.post(
        '/applications/submit',
        headers=member_headers,
        json={
            'job_id': job_id,
            'member_id': 'mem_501',
            'resume_ref': 'resume-501.pdf',
            'idempotency_key': f'matrix-{job_id}',
        },
    )
    assert submitted.status_code == 202
    app_id = submitted.json()['data']['application_id']
    get_status = None
    for _ in range(20):
        get_status = apps.post('/applications/get', headers=member_headers, json={'application_id': app_id})
        if get_status.status_code == 200:
            break
        time.sleep(0.1)
    assert get_status is not None and get_status.status_code == 200
    assert apps.post('/applications/updateStatus', headers=recruiter_headers, json={'application_id': app_id, 'new_status': 'reviewing'}).status_code == 200


def test_messaging_service_threads_messages_and_connections(clients):
    msg = clients['owner6']
    member_headers = clients['headers']['member']
    recruiter_headers = clients['headers']['recruiter']

    opened = msg.post('/threads/open', headers=member_headers, json={'participant_ids': ['mem_501', 'rec_120']})
    assert opened.status_code == 200
    thread_id = opened.json()['data']['thread_id']
    assert msg.post('/messages/send', headers=member_headers, json={'thread_id': thread_id, 'text': 'hello', 'client_message_id': 'matrix-msg'}).status_code == 200

    req = msg.post(
        '/connections/request',
        headers=member_headers,
        json={'requester_id': 'mem_501', 'receiver_id': 'rec_120', 'message': 'Connect?'},
    )
    assert req.status_code == 200
    request_id = req.json()['data']['request_id']
    assert msg.post('/connections/accept', headers=recruiter_headers, json={'request_id': request_id}).status_code == 200


def test_analytics_and_ai_service_entrypoints(clients):
    analytics = clients['owner7']
    ai = clients['owner8']
    member_headers = clients['headers']['member']
    recruiter_headers = clients['headers']['recruiter']

    job_id = _seed_recruiter_member_job(clients)
    analytics_top = analytics.post('/analytics/jobs/top', headers=recruiter_headers, json={'metric': 'applications', 'limit': 5})
    assert analytics_top.status_code == 200
    member_dash = analytics.post('/analytics/member/dashboard', headers=member_headers, json={'member_id': 'mem_501'})
    assert member_dash.status_code == 200

    ai_task = ai.post('/ai/tasks/create', headers=recruiter_headers, json={'task_type': 'shortlist_for_job', 'job_id': job_id})
    assert ai_task.status_code == 200
