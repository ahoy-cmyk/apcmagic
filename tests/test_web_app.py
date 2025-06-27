import pytest
from src.web_app import app
import json

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_api_status(client):
    # Mock apcaccess.get_status() if needed, but for a basic test, assume it works
    # or handle the case where apcupsd is not running gracefully in the app.
    response = client.get('/api/status')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert "STATUS" in data

def test_api_history_default(client):
    response = client.get('/api/history')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert isinstance(data, list)

def test_api_history_invalid_timerange(client):
    response = client.get('/api/history?timerange=invalid')
    assert response.status_code == 400
    data = json.loads(response.data)
    assert "error" in data
    assert data["error"] == "Invalid timerange"
