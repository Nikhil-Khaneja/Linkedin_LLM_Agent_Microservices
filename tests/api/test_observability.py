
def test_ops_endpoints_and_cache_stats(clients):
    o4 = clients['owner4']
    o6 = clients['owner6']
    MEMBER = clients['headers']['member']
    RECRUITER = clients['headers']['recruiter']

    create = o4.post('/jobs/create', headers=RECRUITER, json={
        'company_id': 'cmp_44',
        'recruiter_id': 'rec_120',
        'title': 'Observability Engineer',
        'description': 'Build tracing, metrics, and event driven systems for recruiter workflows.',
        'seniority_level': 'mid',
        'employment_type': 'full_time',
        'location': 'San Jose, CA',
        'work_mode': 'hybrid',
        'skills_required': ['Python', 'Prometheus', 'Kafka'],
    })
    assert create.status_code == 200
    job_id = create.json()['data']['job_id']

    first = o4.post('/jobs/get', headers=MEMBER, json={'job_id': job_id})
    second = o4.post('/jobs/get', headers=MEMBER, json={'job_id': job_id})
    assert first.status_code == 200
    assert second.status_code == 200

    cache_stats = o4.get('/ops/cache-stats')
    assert cache_stats.status_code == 200
    payload = cache_stats.json()
    assert payload['service'] == 'jobs_service'
    assert payload['lookups'] >= 2
    assert payload['hits'] >= 1
    assert 'job' in payload['namespaces']

    metrics = o4.get('/ops/metrics')
    assert metrics.status_code == 200
    assert 'linkedin_service_http_requests_total' in metrics.text
    assert 'linkedin_service_cache_hit_rate_percent' in metrics.text

    thread = o6.post('/threads/open', headers=MEMBER, json={'participant_ids': ['mem_501', 'rec_120']})
    assert thread.status_code == 200
    thread_id = thread.json()['data']['thread_id']
    send = o6.post('/messages/send', headers=MEMBER, json={'thread_id': thread_id, 'text': 'hello', 'client_message_id': 'obs-1'})
    assert send.status_code == 200
    get_thread = o6.post('/threads/get', headers=RECRUITER, json={'thread_id': thread_id})
    assert get_thread.status_code == 200
    unread_stats = o6.get('/ops/cache-stats')
    assert unread_stats.status_code == 200
    assert unread_stats.json()['service'] == 'messaging_connections_service'
