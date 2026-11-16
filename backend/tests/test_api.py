import importlib,os,sys,tempfile
from pathlib import Path
from fastapi.testclient import TestClient

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
temp = tempfile.mkdtemp(prefix='portfolio-test-')
os.environ['APP_DB']=str(Path(temp)/'test.db')
if 'main' in sys.modules: del sys.modules['main']
from main import app
client=TestClient(app)

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

