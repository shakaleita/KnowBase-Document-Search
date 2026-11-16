import importlib,os,sys,tempfile
from pathlib import Path
from fastapi.testclient import TestClient

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
temp = tempfile.mkdtemp(prefix='portfolio-test-')
os.environ['APP_DB']=str(Path(temp)/'test.db')
os.environ['OWNER_SETUP_TOKEN']='test-only-setup-token-1234567890123'
if 'main' in sys.modules: del sys.modules['main']
from main import app
client=TestClient(app)
assert client.post('/api/auth/register',json={'username':'qaowner','password':'DemoPassword123!','setup_token':'test-only-setup-token-1234567890123'}).status_code==201
assert client.post('/api/auth/login',json={'username':'qaowner','password':'DemoPassword123!'}).status_code==200

def test_health():
    r=client.get('/api/health')
    assert r.status_code==200 and r.json()['ok']

def test_initial_list():
    r=client.get('/api/items')
    assert r.status_code==200 and isinstance(r.json(),list)

def test_summary():
    r=client.get('/api/summary')
    assert r.status_code==200 and isinstance(r.json(),list)


# v0.3 regression tests
def test_search_edit_and_delete_index_consistency():
    d=client.post('/api/items',json={'title':'Apollo','body':'Red cosmos rocket','source':'Demo'}).json()
    assert any(x['id']==d['id'] for x in client.get('/api/search',params={'q':'cosmos'}).json())
    assert client.put(f"/api/items/{d['id']}",json={'title':'Apollo','body':'Ocean observation','source':'Demo'}).status_code==200
    assert not any(x['id']==d['id'] for x in client.get('/api/search',params={'q':'cosmos'}).json())
    assert any(x['id']==d['id'] for x in client.get('/api/search',params={'q':'ocean'}).json())
    assert client.delete(f"/api/items/{d['id']}").status_code==204
    assert not any(x['id']==d['id'] for x in client.get('/api/search',params={'q':'ocean'}).json())



def test_v05_document_revision():
    doc=client.post('/api/items',json={'title':'Original research','body':'First draft'}).json()
    assert client.put(f"/api/items/{doc['id']}",json={'title':'Revised research','body':'Second draft'}).status_code==200
    revisions=client.get(f"/api/documents/{doc['id']}/history").json()
    assert any(x['body']=='First draft' for x in revisions)

def test_v05_authentication():
    with TestClient(app) as anonymous:
        assert anonymous.get('/api/items').status_code==401
        assert anonymous.post('/api/auth/register',json={'username':'intruder','password':'DemoPassword123!','setup_token':'bad'}).status_code==403

# v0.6 request-origin and owner audit regression
def test_v06_audit_record_and_cross_site_guard():
    attempted=client.post('/api/__audit_probe_404')
    assert attempted.status_code==404
    audit=client.get('/api/auth/audit')
    assert audit.status_code==200
    assert any(row['method']=='POST' and row['path']=='/api/__audit_probe_404'
               and row['status_code']==404 for row in audit.json())
    assert client.get('/api/auth/audit',params={'limit':201}).status_code==422
    blocked=client.post('/api/__audit_probe_404',headers={'sec-fetch-site':'cross-site'})
    assert blocked.status_code==403

def test_restore_revision_preserves_history_and_updates_full_text_index():
    document=client.post('/api/items',json={'title':'Demo doc','body':'Original spaceship'}).json()
    ident=document['id']
    assert client.put(f'/api/items/{ident}',json={'title':'Demo doc','body':'Replacement ocean'}).status_code==200
    history=client.get(f'/api/documents/{ident}/history').json()
    snapshot=next(r for r in history if r['body']=='Original spaceship')
    restored=client.post(f"/api/documents/{ident}/restore/{snapshot['id']}")
    assert restored.status_code==200
    assert restored.json()['body']=='Original spaceship'
    assert any(x['id']==ident for x in client.get('/api/search',params={'q':'spaceship'}).json())
    assert not any(x['id']==ident for x in client.get('/api/search',params={'q':'ocean'}).json())
    after=client.get(f'/api/documents/{ident}/history').json()
    assert any(row['body']=='Replacement ocean' for row in after)
    assert client.post(f'/api/documents/{ident}/restore/999999').status_code==404
