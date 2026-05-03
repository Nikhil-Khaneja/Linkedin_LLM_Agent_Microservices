"""Career Coach endpoint tests.

Monkey-patches the AI service's member and job repositories with in-memory
fixtures so these tests do not require MySQL. OpenRouter is absent in the
test env (no OPENROUTER_API_KEY), so the handler falls back to the heuristic
coach path — which is what we want to verify here.
"""


def _install_fixture_repos(monkeypatch, member: dict, job: dict):
    from services.ai_orchestrator_service.app.core.deps import get_ai_service
    svc = get_ai_service()

    class _FakeMembers:
        def get(self, mid):
            return member if mid == member.get('member_id') else None

    class _FakeJobs:
        def get(self, jid):
            return job if jid == job.get('job_id') else None

    monkeypatch.setattr(svc, 'members', _FakeMembers())
    monkeypatch.setattr(svc, 'jobs', _FakeJobs())
    return svc


SAMPLE_MEMBER = {
    'member_id': 'mem_coach_1',
    'first_name': 'Ava',
    'last_name': 'Shah',
    'email': 'ava@example.com',
    'headline': 'Data Analyst',
    'about_text': 'Analyst with SQL and Python experience at a startup.',
    'location_text': 'San Jose, CA',
    'current_title': 'Data Analyst',
    'current_company': 'Northstar',
    'skills_json': ['python', 'sql'],
    'resume_text': 'Python SQL data analysis. 3 years experience. BS Computer Science.',
}

SAMPLE_JOB = {
    'job_id': 'job_coach_1',
    'title': 'Senior Data Engineer',
    'description': 'Build pipelines with Python, SQL, Kafka, AWS and Kubernetes. Mentor juniors.',
    'description_text': 'Build pipelines with Python, SQL, Kafka, AWS and Kubernetes. Mentor juniors.',
    'seniority_level': 'senior',
    'employment_type': 'full_time',
    'location_text': 'San Jose, CA',
    'work_mode': 'hybrid',
    'skills_required': ['python', 'sql', 'kafka', 'aws', 'kubernetes'],
    'status': 'open',
}


def test_coach_requires_auth(clients):
    o8 = clients['owner8']
    r = o8.post('/ai/coach/suggest', json={'member_id': 'mem_coach_1', 'target_job_id': 'job_coach_1'})
    assert r.status_code == 401


def test_coach_requires_target_job_id(clients, monkeypatch):
    MEMBER = clients['headers']['member']
    o8 = clients['owner8']
    _install_fixture_repos(monkeypatch, SAMPLE_MEMBER, SAMPLE_JOB)
    r = o8.post('/ai/coach/suggest', headers=MEMBER, json={'member_id': 'mem_501'})
    assert r.status_code == 400
    assert 'target_job_id' in r.json()['error']['message']


def test_coach_member_cannot_coach_other_member(clients, monkeypatch):
    """Member JWT has sub='mem_501'; coaching mem_coach_1 should be forbidden."""
    MEMBER = clients['headers']['member']
    o8 = clients['owner8']
    _install_fixture_repos(monkeypatch, SAMPLE_MEMBER, SAMPLE_JOB)
    r = o8.post('/ai/coach/suggest', headers=MEMBER, json={
        'member_id': 'mem_coach_1',  # different from JWT sub mem_501
        'target_job_id': 'job_coach_1',
    })
    assert r.status_code == 403


def test_coach_recruiter_can_coach_any_member(clients, monkeypatch):
    RECRUITER = clients['headers']['recruiter']
    o8 = clients['owner8']
    _install_fixture_repos(monkeypatch, SAMPLE_MEMBER, SAMPLE_JOB)
    r = o8.post('/ai/coach/suggest', headers=RECRUITER, json={
        'member_id': 'mem_coach_1',
        'target_job_id': 'job_coach_1',
    })
    assert r.status_code == 200, r.text


def test_coach_returns_expected_shape_and_fields(clients, monkeypatch):
    RECRUITER = clients['headers']['recruiter']
    o8 = clients['owner8']
    _install_fixture_repos(monkeypatch, SAMPLE_MEMBER, SAMPLE_JOB)

    r = o8.post('/ai/coach/suggest', headers=RECRUITER, json={
        'member_id': 'mem_coach_1',
        'target_job_id': 'job_coach_1',
    })
    assert r.status_code == 200, r.text
    data = r.json()['data']
    # Required response fields
    for key in ('member_id', 'target_job_id', 'suggested_headline', 'skills_to_add',
                'resume_tips', 'current_match_score', 'match_score_if_improved', 'provider'):
        assert key in data, f'missing {key} in {data}'
    # Member has python+sql, job needs python+sql+kafka+aws+kubernetes → missing 3
    assert set(data['skills_to_add']) == {'kafka', 'aws', 'kubernetes'}
    # Scores are 0-100
    assert 0 <= data['current_match_score'] <= 100
    assert 0 <= data['match_score_if_improved'] <= 100
    # Improved must not be worse than current (adding skills can only raise skill_ratio + keyword_overlap)
    assert data['match_score_if_improved'] >= data['current_match_score']


def test_coach_404_on_missing_member(clients, monkeypatch):
    RECRUITER = clients['headers']['recruiter']
    o8 = clients['owner8']
    _install_fixture_repos(monkeypatch, SAMPLE_MEMBER, SAMPLE_JOB)
    r = o8.post('/ai/coach/suggest', headers=RECRUITER, json={
        'member_id': 'mem_does_not_exist',
        'target_job_id': 'job_coach_1',
    })
    assert r.status_code == 404


def test_coach_404_on_missing_job(clients, monkeypatch):
    RECRUITER = clients['headers']['recruiter']
    o8 = clients['owner8']
    _install_fixture_repos(monkeypatch, SAMPLE_MEMBER, SAMPLE_JOB)
    r = o8.post('/ai/coach/suggest', headers=RECRUITER, json={
        'member_id': 'mem_coach_1',
        'target_job_id': 'job_does_not_exist',
    })
    assert r.status_code == 404


def test_coach_tips_are_populated(clients, monkeypatch):
    RECRUITER = clients['headers']['recruiter']
    o8 = clients['owner8']
    _install_fixture_repos(monkeypatch, SAMPLE_MEMBER, SAMPLE_JOB)
    r = o8.post('/ai/coach/suggest', headers=RECRUITER, json={
        'member_id': 'mem_coach_1',
        'target_job_id': 'job_coach_1',
    })
    data = r.json()['data']
    assert isinstance(data['resume_tips'], list)
    assert len(data['resume_tips']) >= 1
    # Headline should be non-empty and ≤100 chars
    assert 0 < len(data['suggested_headline']) <= 100


def test_coach_propagates_trace_id(clients, monkeypatch):
    """The X-Trace-Id header sent by the caller must appear unchanged on the response envelope."""
    RECRUITER = clients['headers']['recruiter']
    o8 = clients['owner8']
    _install_fixture_repos(monkeypatch, SAMPLE_MEMBER, SAMPLE_JOB)

    expected = 'trc_test_coach_propagation_123'
    r = o8.post('/ai/coach/suggest',
                headers={**RECRUITER, 'X-Trace-Id': expected},
                json={'member_id': 'mem_coach_1', 'target_job_id': 'job_coach_1'})
    assert r.status_code == 200, r.text
    assert r.json()['trace_id'] == expected
