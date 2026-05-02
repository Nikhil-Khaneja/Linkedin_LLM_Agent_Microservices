
def test_message_send_is_idempotent(clients):
    owner6 = clients['owner6']
    MEMBER = clients['headers']['member']
    RECRUITER = clients['headers']['recruiter']
    thread = owner6.post('/threads/open', headers=MEMBER, json={'participant_ids': ['mem_501', 'rec_120']})
    assert thread.status_code == 200
    thread_id = thread.json()['data']['thread_id']

    payload = {'thread_id': thread_id, 'text': 'hello', 'client_message_id': 'pytest-1'}
    first = owner6.post('/messages/send', headers=MEMBER, json=payload)
    second = owner6.post('/messages/send', headers=MEMBER, json=payload)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()['data']['message_id'] == second.json()['data']['message_id']

    listed = owner6.post('/messages/list', headers=RECRUITER, json={'thread_id': thread_id, 'page_size': 10})
    assert listed.status_code == 200
    assert len(listed.json()['data']['items']) == 1


def test_connection_accept_creates_mutual_graph(clients):
    owner6 = clients['owner6']
    MEMBER = clients['headers']['member']
    RECRUITER = clients['headers']['recruiter']
    r1 = owner6.post('/connections/request', headers=MEMBER, json={'requester_id': 'mem_501', 'receiver_id': 'rec_120', 'message': 'connect'})
    assert r1.status_code == 200
    request_id = r1.json()['data']['request_id']
    r2 = owner6.post('/connections/accept', headers=RECRUITER, json={'request_id': request_id})
    assert r2.status_code == 200
    r3 = owner6.post('/connections/list', headers=MEMBER, json={'user_id': 'mem_501'})
    assert r3.status_code == 200
    assert r3.json()['meta']['total'] == 1
