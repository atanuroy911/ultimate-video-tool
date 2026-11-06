"""The two distributions must remain independent after future feature work."""
import importlib.util
import json
from pathlib import Path
from fastapi.testclient import TestClient

ROOT=Path(__file__).resolve().parents[1]

def test_server_never_serves_the_client_workspace():
    from vt.server.app import app
    client=TestClient(app)
    response=client.get('/')
    assert response.status_code==200
    assert 'Ultimate Video Tool Server' in response.text
    assert 'id="root"' not in response.text
    for route in ['/new','/settings','/p/example','/assets/index.js']:
        assert client.get(route).status_code==404

def test_product_manifests_do_not_cross_bundle():
    client=json.loads((ROOT/'client/desktop/package.json').read_text())
    server=json.loads((ROOT/'server/desktop/package.json').read_text())
    assert client['dependencies']=={'ws':'^8.18.0'}
    assert not any('bootstrap' in file or 'server-manager' in file for file in client['build']['files'])
    assert {'from':'../studio/dist','to':'studio','filter':['**/*']} in client['build']['extraResources']
    assert all((ROOT/'client/desktop'/item['from']).resolve().is_relative_to(ROOT/'client') for item in client['build']['extraResources'])
    assert not any('studio' in name or 'client' in name for item in server['build']['extraResources'] for name in item['filter'])
    assert (ROOT/'server/desktop'/server['build']['extraResources'][0]['from']).resolve()==ROOT/'server'
    assert not (ROOT/'server/studio').exists() and not (ROOT/'client/vt').exists()

def test_full_processing_archive_still_excludes_the_editor():
    spec=importlib.util.spec_from_file_location('package_split',ROOT/'scripts/make_engine_package.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    files=module.collect('1.0.0',full=True)
    assert any('/renderer/runtime/' in name for name in files)
    assert not any('/studio/' in name or '/client/' in name for name in files)
