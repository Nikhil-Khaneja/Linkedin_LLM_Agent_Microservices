"""trace_id propagation audit for the AI pipeline.

Verifies that X-Trace-Id on /ai/tasks/create flows through:
  request → ai.requests Kafka event → _run_pipeline → ai.results events → task.steps

Monkey-patches job/application/member repos so the pipeline runs without MySQL.
"""

import asyncio
import time


def _install_pipeline_fixtures(monkeypatch):
    from services.ai_orchestrator_service.app.core.deps import get_ai_service
    svc = get_ai_service()

    class _FakeJobs:
        def get(self, jid):
            return {'job_id': jid, 'title': 'Backend Engineer',
                    'description': 'Python Kafka MySQL microservices.',
                    'description_text': 'Python Kafka MySQL microservices.',
                    'seniority_level': 'mid', 'location_text': 'San Jose, CA',
                    'work_mode': 'hybrid', 'skills_required': ['python', 'kafka', 'mysql'],
                    'status': 'open'}

    class _FakeApplications:
        def list_by_job(self, jid):
            return []  # empty shortlist keeps the test lightweight

    class _FakeMembers:
        def get(self, mid):
            return {}

    monkeypatch.setattr(svc, 'jobs', _FakeJobs())
    monkeypatch.setattr(svc, 'applications', _FakeApplications())
    monkeypatch.setattr(svc, 'members', _FakeMembers())
    return svc


def test_trace_id_flows_into_task_steps(clients, monkeypatch):
    RECRUITER = clients['headers']['recruiter']
    o8 = clients['owner8']
    _install_pipeline_fixtures(monkeypatch)

    expected = 'trc_pipeline_audit_abc'
    create = o8.post('/ai/tasks/create',
                     headers={**RECRUITER, 'X-Trace-Id': expected},
                     json={'task_type': 'shortlist', 'job_id': 'job_pipeline_1'})
    assert create.status_code == 200, create.text
    assert create.json()['trace_id'] == expected
    task_id = create.json()['data']['task_id']

    # The pipeline runs async via the memory Kafka bus + local fallback. Poll until the
    # task reaches a terminal or awaiting_approval state, then inspect its step log.
    final_task = None
    for _ in range(80):
        res = o8.get(f'/ai/tasks/{task_id}', headers=RECRUITER)
        assert res.status_code == 200
        payload = res.json()['data']
        if payload.get('status') in {'awaiting_approval', 'completed', 'rejected', 'failed'}:
            final_task = payload
            break
        time.sleep(0.15)
    assert final_task is not None, 'pipeline did not reach terminal state in time'

    # Every step log entry should carry the same trace_id that was sent on the request.
    steps = final_task.get('steps') or []
    assert steps, 'expected at least one step recorded'
    trace_ids = {step.get('trace_id') for step in steps if step.get('trace_id')}
    assert trace_ids == {expected}, f'expected all steps to carry {expected!r}, got {trace_ids!r}'
