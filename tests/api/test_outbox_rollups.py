import time
import uuid


def test_outbox_dispatch_and_rollups(clients):
    o3, o4, o5, o7 = clients['owner3'], clients['owner4'], clients['owner5'], clients['owner7']
    recruiter = clients['headers']['recruiter']
    member = clients['headers']['member']
    o3.post('/recruiters/create', headers=recruiter, json={
        'recruiter_id': 'rec_120', 'name': 'Morgan Lee', 'email': 'recruiter@example.com',
        'company_name': 'Northstar Labs', 'company_industry': 'Software', 'company_size': 'medium', 'access_level': 'admin',
    })
    o2.post('/members/create', headers=member, json={
        'member_id': 'mem_501', 'first_name': 'Ava', 'last_name': 'Shah', 'email': 'ava@example.com',
        'headline': 'Data Analyst', 'skills': ['SQL', 'Python', 'FastAPI'], 'location': 'San Jose, CA',
    })

    o3.post('/recruiters/create', headers=recruiter, json={
        'recruiter_id': 'rec_120', 'name': 'Morgan Lee', 'email': 'recruiter@example.com',
        'company_name': 'Northstar Labs', 'company_industry': 'Software', 'company_size': 'medium', 'access_level': 'admin',
    })

    create = o4.post('/jobs/create', headers=recruiter, json={
        'company_id':'cmp_44','recruiter_id':'rec_120','title':f'Outbox Job {uuid.uuid4().hex[:8]}','description':'Outbox and rollups validation path for analytics.','seniority_level':'mid','employment_type':'full_time','location':'San Jose, CA','work_mode':'hybrid','skills_required':['Python']
    })
    assert create.status_code == 200
    job_id = create.json()['data']['job_id']

    committed = False
    for _ in range(120):
        g = o4.post('/jobs/get', headers=recruiter, json={'job_id': job_id})
        if g.status_code == 200 and (g.json().get('meta') or {}).get('write_state') == 'committed':
            committed = True
            break
        time.sleep(0.1)
    assert committed

    submit = o5.post('/applications/submit', headers=member, json={
        'job_id': job_id, 'member_id': 'mem_501', 'resume_ref': 'resume.pdf', 'idempotency_key': f'mem501-{job_id}-outbox', 'city': 'San Jose'
    })
    assert submit.status_code == 202

    ok = False
    for _ in range(200):
        o5.post('/applications/get', headers=member, json={'application_id': app_id})
        funnel = o7.post('/analytics/funnel', headers=recruiter, json={'job_id': job_id})
        if funnel.status_code == 200:
            sub = int((funnel.json().get('data') or {}).get('funnel', {}).get('submitted', 0))
            if sub >= 1:
                ok = True
                break
        time.sleep(0.05)
    assert ok
