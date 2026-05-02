import time


def test_full_system_flow(clients):
    o1, o2, o3, o4, o5, o6, o7, o8 = [clients[k] for k in ['owner1','owner2','owner3','owner4','owner5','owner6','owner7','owner8']]
    MEMBER = clients['headers']['member']
    RECRUITER = clients['headers']['recruiter']
    ADMIN = clients['headers']['admin']

    r = o1.post('/auth/register', json={
        'email': 'ava@example.com', 'password': 'StrongPass#1', 'user_type': 'member', 'first_name': 'Ava', 'last_name': 'Shah'
    })
    assert r.status_code == 200
    assert r.json()['data']['bootstrap_state'] == 'pending_profile'

    r = o1.post('/auth/login', json={'email': 'ava@example.com', 'password': 'StrongPass#1'})
    assert r.status_code == 200
    refresh = r.json()['data']['refresh_token']
    member_runtime_headers = {'Authorization': f"Bearer {r.json()['data']['access_token']}"}
    assert o1.post('/auth/refresh', json={'refresh_token': refresh}).status_code == 200
    assert o1.get('/.well-known/jwks.json').status_code == 200

    r = o3.post('/recruiters/create', headers=RECRUITER, json={
        'recruiter_id': 'rec_120', 'name': 'Morgan Lee', 'email': 'recruiter@example.com',
        'company_name': 'Northstar Labs', 'company_industry': 'Software', 'company_size': 'medium', 'access_level': 'admin'
    })
    assert r.status_code == 200
    assert o3.post('/recruiters/get', headers=RECRUITER, json={'recruiter_id': 'rec_120'}).status_code == 200

    r = o2.post('/members/create', headers=member_runtime_headers, json={
        'member_id': 'mem_501', 'first_name': 'Ava', 'last_name': 'Shah', 'email': 'ava@example.com',
        'headline': 'Data Analyst', 'about': 'Analyst with SQL and Python experience', 'skills': ['SQL', 'Python', 'FastAPI'],
        'location': 'San Jose, CA'
    })
    assert r.status_code == 200
    assert o2.post('/members/get', headers=member_runtime_headers, json={'member_id': 'mem_501'}).status_code == 200
    assert o2.post('/members/search', headers=RECRUITER, json={'skill': 'Python', 'page': 1, 'page_size': 10}).status_code == 200

    r = o4.post('/jobs/create', headers=RECRUITER, json={
        'company_id': 'cmp_44', 'recruiter_id': 'rec_120', 'title': 'Backend Engineer',
        'description': 'Build Kafka-backed services and optimize data access patterns in a LinkedIn-style product.',
        'seniority_level': 'mid', 'employment_type': 'full_time', 'location': 'San Jose, CA', 'work_mode': 'hybrid',
        'skills_required': ['Python', 'Kafka', 'MySQL']
    })
    assert r.status_code == 200
    job_id = r.json()['data']['job_id']
    assert o4.post('/jobs/get', headers=member_runtime_headers, json={'job_id': job_id}).status_code == 200
    assert o4.post('/jobs/search', headers=member_runtime_headers, json={'keyword': 'Backend', 'page': 1, 'page_size': 10}).status_code == 200

    r = o5.post('/applications/submit', headers=member_runtime_headers, json={
        'job_id': job_id, 'member_id': 'mem_501', 'resume_ref': 'resume-501.pdf', 'cover_letter': 'Excited to apply.',
        'idempotency_key': f'mem501-{job_id}-v1', 'city': 'San Jose'
    })
    assert r.status_code == 200
    app_id = r.json()['data']['application_id']
    assert o5.post('/applications/get', headers=member_runtime_headers, json={'application_id': app_id}).status_code == 200
    assert o5.post('/applications/byMember', headers=member_runtime_headers, json={'member_id': 'mem_501'}).status_code == 200
    assert o5.post('/applications/byJob', headers=RECRUITER, json={'job_id': job_id}).status_code == 200
    assert o5.post('/applications/updateStatus', headers=RECRUITER, json={'application_id': app_id, 'recruiter_id': 'rec_120', 'new_status': 'reviewing'}).status_code == 200

    r = o6.post('/threads/open', headers=member_runtime_headers, json={'participant_ids': ['mem_501', 'rec_120']})
    assert r.status_code == 200
    thread_id = r.json()['data']['thread_id']
    assert o6.post('/threads/get', headers=member_runtime_headers, json={'thread_id': thread_id}).status_code == 200
    assert o6.post('/messages/send', headers=member_runtime_headers, json={'thread_id': thread_id, 'text': 'Hello recruiter', 'client_message_id': 'msg-1'}).status_code == 200
    assert o6.post('/messages/list', headers=member_runtime_headers, json={'thread_id': thread_id, 'page_size': 20}).status_code == 200
    r = o6.post('/connections/request', headers=member_runtime_headers, json={'requester_id': 'mem_501', 'receiver_id': 'rec_120', 'message': 'Would love to connect.'})
    assert r.status_code == 200
    request_id = r.json()['data']['request_id']
    assert o6.post('/connections/accept', headers=RECRUITER, json={'request_id': request_id}).status_code == 200
    assert o6.post('/connections/list', headers=member_runtime_headers, json={'user_id': 'mem_501'}).status_code == 200

    time.sleep(0.5)
    top_jobs = o7.post('/analytics/jobs/top', headers=RECRUITER, json={'metric': 'applications', 'limit': 10})
    assert top_jobs.status_code == 200
    funnel = o7.post('/analytics/funnel', headers=RECRUITER, json={'job_id': job_id})
    assert funnel.status_code == 200
    member_dash = o7.post('/analytics/member/dashboard', headers=member_runtime_headers, json={'member_id': 'mem_501'})
    assert member_dash.status_code == 200
    bench = o7.post('/benchmarks/report', headers=ADMIN, json={'scenario': 'B', 'throughput': 100, 'latency_ms_p95': 180})
    assert bench.status_code == 200

    ai_create = o8.post('/ai/tasks/create', headers=RECRUITER, json={'task_type': 'shortlist_for_job', 'job_id': job_id})
    assert ai_create.status_code == 200
    task_id = ai_create.json()['data']['task_id']

    status = None
    for _ in range(80):
        res = o8.get(f'/ai/tasks/{task_id}', headers=RECRUITER)
        assert res.status_code == 200
        status = res.json()['data']['status']
        if status == 'waiting_for_approval':
            break
        time.sleep(0.25)
    assert status == 'waiting_for_approval'
    approve = o8.post(f'/ai/tasks/{task_id}/approve', headers=RECRUITER, json={'edits': 'Hi Ava, your profile looks strong for this role.'})
    assert approve.status_code == 200
    final_task = o8.get(f'/ai/tasks/{task_id}', headers=RECRUITER)
    assert final_task.json()['data']['approval_state'] == 'approved'
