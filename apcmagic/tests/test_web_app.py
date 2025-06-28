import pytest
import unittest.mock as mock
import json

from web_app import app, DATABASE_FILE

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

@pytest.fixture(autouse=True)
def mock_apcaccess_get_status():
    with mock.patch('web_app.get') as _mock_get, mock.patch('web_app.parse') as _mock_parse:
        _mock_get.return_value = "raw_status_string"
        _mock_parse.return_value = {
            'STATUS': 'ONLINE',
            'BCHARGE': '100.0',
            'LOADPCT': '10.0',
            'TIMELEFT': '60.0',
            'LINEV': '120.0',
            'BATTV': '13.0',
        }
        yield _mock_get, _mock_parse

@pytest.fixture(autouse=True)
def mock_sqlite3_connect():
    with mock.patch('web_app.sqlite3.connect') as _mock_connect:
        mock_conn = mock.Mock()
        mock_cursor = mock.Mock()
        mock_conn.cursor.return_value = mock_cursor
        _mock_connect.return_value = mock_conn

        # Mock execute for history data
        mock_cursor.fetchall.return_value = [
            ("2025-06-27 10:00:00", "ONLINE", 100.0, 10.0, 60.0, 120.0, 13.0),
            ("2025-06-27 09:00:00", "ONLINE", 90.0, 12.0, 55.0, 119.0, 12.5),
        ]
        yield _mock_connect

def test_api_status(client):
    response = client.get('/api/status')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert "STATUS" in data

def test_api_history_default(client):
    response = client.get('/api/history')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert isinstance(data, list)
    assert len(data) > 0

def test_api_history_invalid_timerange(client):
    response = client.get('/api/history?timerange=invalid')
    assert response.status_code == 400
    data = json.loads(response.data)
    assert "error" in data
    assert data["error"] == "Invalid timerange"
