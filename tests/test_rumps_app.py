import pytest
import unittest.mock as mock
import rumps
from rumps_app import APCApp

@pytest.fixture
def mock_rumps_app():
    with mock.patch('rumps.App.__init__', return_value=None) as mock_init,         mock.patch('rumps.App.menu', new_callable=mock.PropertyMock) as mock_menu:
        yield mock_init, mock_menu


@pytest.fixture
def mock_rumps_alert():
    with mock.patch('rumps.alert') as mock_alert:
        yield mock_alert

@pytest.fixture
def mock_apcaccess_get_parse():
    with mock.patch('apcaccess.status.get') as mock_get, \
         mock.patch('apcaccess.status.parse') as mock_parse:
        mock_get.return_value = "raw_status_string"
        mock_parse.return_value = {
            'STATUS': 'ONLINE',
            'BCHARGE': '100.0',
            'LOADPCT': '10.0',
            'TIMELEFT': '60.0',
        }
        yield mock_get, mock_parse

def test_apcapp_init(mock_rumps_app):
    mock_init, mock_menu = mock_rumps_app
    app = APCApp()
    mock_init.assert_called_once_with("APC UPS Status")
    mock_menu.assert_called_once_with(["Status", "Quit"])

def test_apcapp_status_success(mock_rumps_app, mock_rumps_alert, mock_apcaccess_get_parse):
    mock_init, mock_menu = mock_rumps_app
    app = APCApp()
    app.status(None)
    mock_apcaccess_get_parse[0].assert_called_once()
    mock_apcaccess_get_parse[1].assert_called_once_with("raw_status_string")
    mock_rumps_alert.assert_called_once_with(
        title="APC UPS Status",
        message="Status: ONLINE\nBattery: 100.0%\nLoad: 10.0%\nTime Left: 60.0",
    )


def test_apcapp_status_failure(mock_rumps_app, mock_rumps_alert, mock_apcaccess_get_parse):
    mock_init, mock_menu = mock_rumps_app
    mock_apcaccess_get_parse[0].side_effect = Exception("Test Error")
    app = APCApp()
    app.status(None)
    mock_rumps_alert.assert_called_once_with(title="Error", message="Test Error")
