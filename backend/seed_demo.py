"""Insert optional synthetic demonstration records (safe to rerun)."""
from fastapi.testclient import TestClient
from main import app

SEEDS = [{'title': 'Remote work policy', 'body': 'Team members may work remotely three days per week after approval.', 'source': 'demo://handbook', 'category': 'HR'}, {'title': 'Security practices', 'body': 'Use multi-factor authentication and review access quarterly.', 'source': 'demo://security', 'category': 'Security'}]
client=TestClient(app)
if client.get('/api/items').json():
    print('Existing records found; skipping seed.')
else:
    for record in SEEDS:
        result=client.post('/api/items',json=record)
        result.raise_for_status()
    print('Added',len(SEEDS),'synthetic sample records.')
