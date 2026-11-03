import json
import pytest
from fastapi.testclient import TestClient
from vt import paths
from vt.server.app import app
from vt.social import core


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, 'PROJECTS', tmp_path / 'projects')
    monkeypatch.setattr(core, 'DB', tmp_path / 'social.db')
    monkeypatch.setattr(core, 'start_worker', lambda: None)
    project = paths.PROJECTS / 'demo'
    (project / 'exports').mkdir(parents=True)
    (project / 'project.json').write_text(json.dumps({'id':'demo','title':'Demo','language':'en','aspect':'9:16','theme':'paper','pace':'normal','created_at':'2026-01-01T00:00:00Z'}))
    (project / 'exports/demo.mp4').write_bytes(b'test-only')
    return TestClient(app)


def account(client, name='Practice'):
    response = client.post('/api/social/accounts/connect/mock', json={'platform':'mock','name':name,'credentials':{}})
    assert response.status_code == 200
    return response.json()['id']


def send(client, ids, **extra):
    return client.post('/api/projects/demo/social/dispatch', json={'account_ids':ids,'video_filename':'demo.mp4','title':'A test',**extra})


def test_direct_accounts_need_no_group_and_are_deduplicated(client):
    a, b = account(client), account(client, 'Second')
    response = send(client, [a, a, b], platform_overrides={'mock':{'title':'Custom'}})
    assert response.status_code == 200, response.text
    assert response.json()['total_tasks'] == 2
    tasks = client.get('/api/social/tasks').json()
    assert {t['account_id'] for t in tasks} == {a,b}
    assert all(t['title'] == 'Custom' for t in tasks)
    assert core.one('SELECT group_id FROM batch')['group_id'] is None


@pytest.mark.parametrize('kind', ['unknown','disconnected','empty','mixed'])
def test_bad_selection_never_queues_partial_post(client, kind):
    a = account(client)
    ids = [a, 'missing'] if kind == 'unknown' else [a]
    extra = {}
    if kind == 'disconnected': client.delete(f'/api/social/accounts/{a}')
    if kind == 'empty': ids = []
    if kind == 'mixed': extra['group_id'] = 'some-group'
    assert send(client, ids, **extra).status_code == 400
    assert not core.rows('SELECT * FROM task')
    assert not core.rows('SELECT * FROM batch')


@pytest.mark.parametrize('platform,key', [('facebook','page_id'),('instagram','ig_user_id')])
def test_platform_destination_is_required(client, platform, key):
    payload = {'platform':platform,'name':'Test','credentials':{'access_token':'fake-not-used'}}
    assert client.post(f'/api/social/accounts/connect/{platform}', json=payload).status_code == 400
    payload['credentials'][key] = '123'
    assert client.post(f'/api/social/accounts/connect/{platform}', json=payload).status_code == 200
    assert 'fake-not-used' not in client.get('/api/social/accounts').text
