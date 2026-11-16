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
