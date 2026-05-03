"""Tests for AI evaluation metrics: approval_action and /ai/analytics/* endpoints.

Uses the `clients` fixture from conftest.py, which sets EVENT_BUS_MODE=memory,
CACHE_MODE=memory, DOC_STORE_MODE=memory. Tasks are seeded directly via the
AIRepository (memory doc store) so these tests do not require MySQL/Kafka.
"""


def _seed_task(task_id: str, created_by: str, draft_message: str, status: str = 'awaiting_approval'):
    from services.ai_orchestrator_service.app.core.deps import get_ai_service
    svc = get_ai_service()
    svc.repo.create_task({
        'task_id': task_id,
        'status': status,
        'current_step': 'waiting_approval',
        'approval_state': 'pending',
        'input': {'job_id': 'job_test_1', 'task_type': 'full_pipeline'},
        'output': {
            'draft_message': draft_message,
            'outreach_drafts': [{'candidate_id': 'mem_cand_1', 'message': draft_message, 'draft': draft_message}],
            'shortlist': [],
        },
        'created_by': created_by,
        'created_by_role': 'recruiter',
    })


def test_approve_with_no_edits_sets_approved_as_is(clients):
    RECRUITER = clients['headers']['recruiter']
    o8 = clients['owner8']
    _seed_task('ait_no_edits', 'rec_120', 'Hi Ava, interested?')

    r = o8.post('/ai/tasks/ait_no_edits/approve', headers=RECRUITER, json={'send_outreach': False})
    assert r.status_code == 200, r.text
    body = r.json()['data']
    assert body['approval_state'] == 'approved'
    assert body['approval_action'] == 'approved_as_is'

    task = o8.get('/ai/tasks/ait_no_edits', headers=RECRUITER).json()['data']
    assert task['approval_action'] == 'approved_as_is'
    assert task['approval_state'] == 'approved'


def test_approve_with_same_edits_still_approved_as_is(clients):
    """Edits that are whitespace-equivalent to the draft are not real edits."""
    RECRUITER = clients['headers']['recruiter']
    o8 = clients['owner8']
    _seed_task('ait_same_edits', 'rec_120', 'Hi Ava, interested?')

    r = o8.post('/ai/tasks/ait_same_edits/approve', headers=RECRUITER, json={
        'send_outreach': False,
        'edits': {'mem_cand_1': '  Hi Ava, interested?  '},
    })
    assert r.status_code == 200, r.text
    assert r.json()['data']['approval_action'] == 'approved_as_is'


def test_approve_with_real_edits_sets_edited(clients):
    RECRUITER = clients['headers']['recruiter']
    o8 = clients['owner8']
    _seed_task('ait_edited', 'rec_120', 'Hi Ava, interested?')

    edited_text = 'Hi Ava, I reviewed your SQL background and would love to chat.'
    r = o8.post('/ai/tasks/ait_edited/approve', headers=RECRUITER, json={
        'send_outreach': False,
        'edits': {'mem_cand_1': edited_text},
    })
    assert r.status_code == 200, r.text
    body = r.json()['data']
    assert body['approval_state'] == 'approved'
    assert body['approval_action'] == 'edited'

    task = o8.get('/ai/tasks/ait_edited', headers=RECRUITER).json()['data']
    assert task['approval_action'] == 'edited'
    assert task['output']['draft_message'] == edited_text


def test_reject_sets_rejected(clients):
    RECRUITER = clients['headers']['recruiter']
    o8 = clients['owner8']
    _seed_task('ait_rejected', 'rec_120', 'Hi Ava, interested?')

    r = o8.post('/ai/tasks/ait_rejected/reject', headers=RECRUITER, json={'reason': 'Not a fit'})
    assert r.status_code == 200, r.text
    body = r.json()['data']
    assert body['approval_state'] == 'rejected'
    assert body['approval_action'] == 'rejected'

    task = o8.get('/ai/tasks/ait_rejected', headers=RECRUITER).json()['data']
    assert task['approval_action'] == 'rejected'
    assert task['status'] == 'rejected'


def _seed_task_with_shortlist(task_id: str, created_by: str, status: str, shortlist: list, approval_action: str | None = None):
    from services.ai_orchestrator_service.app.core.deps import get_ai_service
    from services.shared.repositories import now_iso
    svc = get_ai_service()
    payload = {
        'task_id': task_id,
        'status': status,
        'current_step': status,
        'approval_state': 'approved' if approval_action in {'approved_as_is', 'edited'} else ('rejected' if approval_action == 'rejected' else 'pending'),
        'input': {'job_id': 'job_test_1', 'task_type': 'full_pipeline'},
        'output': {'shortlist': shortlist, 'outreach_drafts': [], 'draft_message': ''},
        'steps': [],
        'created_by': created_by,
        'created_by_role': 'recruiter',
        'created_at': now_iso(),
        'updated_at': now_iso(),
    }
    if approval_action is not None:
        payload['approval_action'] = approval_action
    # save_task preserves all fields (replace_one), unlike create_task which whitelists.
    svc.repo.save_task(payload)


def test_approval_rate_aggregates_three_actions(clients):
    RECRUITER = clients['headers']['recruiter']
    o8 = clients['owner8']
    # Seed 2 approved_as_is, 1 edited, 1 rejected, 1 running (no approval_action — should be excluded)
    _seed_task_with_shortlist('ar_1', 'rec_120', 'completed', [], 'approved_as_is')
    _seed_task_with_shortlist('ar_2', 'rec_120', 'completed', [], 'approved_as_is')
    _seed_task_with_shortlist('ar_3', 'rec_120', 'completed', [], 'edited')
    _seed_task_with_shortlist('ar_4', 'rec_120', 'rejected', [], 'rejected')
    _seed_task_with_shortlist('ar_5', 'rec_120', 'running', [], None)

    r = o8.get('/ai/analytics/approval-rate', headers=RECRUITER)
    assert r.status_code == 200, r.text
    data = r.json()['data']
    assert data['total_tasks'] == 4, data
    assert data['approved_as_is'] == 2
    assert data['edited'] == 1
    assert data['rejected'] == 1
    assert data['approval_rate_pct'] == 50.0
    assert data['edit_rate_pct'] == 25.0
    assert data['rejection_rate_pct'] == 25.0
    assert data['scope'] == 'recruiter'


def test_approval_rate_forbidden_for_member(clients):
    MEMBER = clients['headers']['member']
    o8 = clients['owner8']
    r = o8.get('/ai/analytics/approval-rate', headers=MEMBER)
    assert r.status_code == 403


def test_approval_rate_requires_auth(clients):
    o8 = clients['owner8']
    r = o8.get('/ai/analytics/approval-rate')
    assert r.status_code == 401


def test_approval_rate_admin_sees_all_recruiters(clients):
    RECRUITER = clients['headers']['recruiter']
    ADMIN = clients['headers']['admin']
    o8 = clients['owner8']
    _seed_task_with_shortlist('adm_1', 'rec_120', 'completed', [], 'approved_as_is')
    _seed_task_with_shortlist('adm_2', 'rec_OTHER', 'completed', [], 'edited')
    _seed_task_with_shortlist('adm_3', 'rec_OTHER', 'rejected', [], 'rejected')

    admin_view = o8.get('/ai/analytics/approval-rate', headers=ADMIN).json()['data']
    assert admin_view['total_tasks'] == 3
    assert admin_view['scope'] == 'all'

    recruiter_view = o8.get('/ai/analytics/approval-rate', headers=RECRUITER).json()['data']
    assert recruiter_view['total_tasks'] == 1  # only adm_1 belongs to rec_120
    assert recruiter_view['scope'] == 'recruiter'


def test_match_quality_averages_top_5(clients):
    RECRUITER = clients['headers']['recruiter']
    o8 = clients['owner8']
    # Task 1: 3 candidates (all counted)
    _seed_task_with_shortlist('mq_1', 'rec_120', 'awaiting_approval', [
        {'candidate_id': 'c1', 'match_score': 80, 'skill_overlap': ['python', 'sql'], 'missing_skills': ['aws']},
        {'candidate_id': 'c2', 'match_score': 60, 'skill_overlap': ['python'],        'missing_skills': ['aws', 'sql']},
        {'candidate_id': 'c3', 'match_score': 40, 'skill_overlap': [],                'missing_skills': ['aws', 'sql', 'python']},
    ])
    # Task 2: 1 candidate, completed
    _seed_task_with_shortlist('mq_2', 'rec_120', 'completed', [
        {'candidate_id': 'c4', 'match_score': 90, 'skill_overlap': ['java', 'kubernetes'], 'missing_skills': []},
    ])
    # Task 3: running — excluded
    _seed_task_with_shortlist('mq_3', 'rec_120', 'running', [
        {'candidate_id': 'c5', 'match_score': 10, 'skill_overlap': [], 'missing_skills': ['x']},
    ])

    r = o8.get('/ai/analytics/match-quality', headers=RECRUITER)
    assert r.status_code == 200, r.text
    data = r.json()['data']
    assert data['sample_size'] == 4, data  # c5 excluded because task running
    # Avg of 80, 60, 40, 90 = 67.5
    assert data['avg_match_score'] == 67.5
    # Skill overlap pcts: c1=2/3*100=66.67, c2=1/3*100=33.33, c3=0/3=0, c4=2/2*100=100 → avg=50.0
    assert abs(data['avg_skill_overlap_pct'] - 50.0) < 0.1
    assert data['top_k'] == 5


def test_match_quality_top_5_slice(clients):
    RECRUITER = clients['headers']['recruiter']
    o8 = clients['owner8']
    candidates = [
        {'candidate_id': f'c{i}', 'match_score': 100 - i * 10, 'skill_overlap': ['x'], 'missing_skills': []}
        for i in range(10)
    ]
    _seed_task_with_shortlist('mq_top5', 'rec_120', 'completed', candidates)
    data = o8.get('/ai/analytics/match-quality', headers=RECRUITER).json()['data']
    assert data['sample_size'] == 5  # only top 5 counted
    # Top 5 scores: 100, 90, 80, 70, 60 → avg 80
    assert data['avg_match_score'] == 80.0


def test_match_quality_forbidden_for_member(clients):
    MEMBER = clients['headers']['member']
    o8 = clients['owner8']
    r = o8.get('/ai/analytics/match-quality', headers=MEMBER)
    assert r.status_code == 403
