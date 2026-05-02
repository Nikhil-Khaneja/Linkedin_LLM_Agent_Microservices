import time


def test_outbox_dispatch_and_rollups(clients):
    o3,o4,o5,o7 = clients['owner3'],clients['owner4'],clients['owner5'],clients['owner7']
    recruiter = clients['headers']['recruiter']
    member = clients['headers']['member']

    o3.post('/recruiters/create', headers=recruiter, json={
        'recruiter_id': 'rec_120', 'name': 'Morgan Lee', 'email': 'recruiter@example.com',
        'company_name': 'Northstar Labs', 'company_industry': 'Software', 'company_size': 'medium', 'access_level': 'admin',
    })

    create = o4.post('/jobs/create', headers=recruiter, json={
        'company_id':'cmp_44','recruiter_id':'rec_120','title':'Outbox Job','description':'Outbox and rollups validation path for analytics.','seniority_level':'mid','employment_type':'full_time','location':'San Jose, CA','work_mode':'hybrid','skills_required':['Python']
    })
    assert create.status_code == 200
    job_id = create.json()['data']['job_id']

    submit = o5.post('/applications/submit', headers=member, json={
        'job_id': job_id, 'member_id': 'mem_501', 'resume_ref': 'resume.pdf', 'idempotency_key': f'mem501-{job_id}-outbox', 'city': 'San Jose'
    })
    assert submit.status_code == 202

    time.sleep(0.5)
    top = o7.post('/analytics/jobs/top', headers=recruiter, json={'metric':'applications','limit':10})
    assert top.status_code == 200
    assert any(item['job_id'] == job_id for item in top.json()['data']['items'])
