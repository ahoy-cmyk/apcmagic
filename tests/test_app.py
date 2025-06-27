import pytest
import unittest.mock as mock
import sys
from pathlib import Path
import sqlite3

# Adjust the path to import modules from src
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import app

# Mock the logger to prevent actual logging during tests
@pytest.fixture(autouse=True)
def mock_logger():
    with mock.patch('app.logger') as _mock_logger:
        yield _mock_logger

@pytest.fixture
def mock_config():
    with mock.patch('app.configparser.ConfigParser') as MockConfigParser:
        mock_config_instance = MockConfigParser.return_value
        mock_config_instance.getint.side_effect = lambda section, option: {
            ('apcmagic', 'shutdown_threshold'): 20,
            ('apcmagic', 'monitor_interval_seconds'): 1,
        }[(section, option)]
        mock_config_instance.get.side_effect = lambda section, option: {
            ('ubiquiti', 'hosts'): '',
            ('ubiquiti', 'username'): 'testuser',
            ('ubiquiti', 'password'): 'testpass',
        }[(section, option)]
        yield

@pytest.fixture
def mock_apcaccess_status():
    with mock.patch('app.apcaccess.get_status') as _mock_get_status:
        yield _mock_get_status

@pytest.fixture
def mock_subprocess_run():
    with mock.patch('app.subprocess.run') as _mock_run:
        yield _mock_run

@pytest.fixture
def mock_paramiko_sshclient():
    with mock.patch('app.paramiko.SSHClient') as MockSSHClient:
        mock_ssh_instance = MockSSHClient.return_value
        yield mock_ssh_instance

@pytest.fixture
def mock_sqlite3_connect():
    with mock.patch('app.sqlite3.connect') as _mock_connect:
        mock_conn = mock.Mock()
        mock_cursor = mock.Mock()
        mock_conn.cursor.return_value = mock_cursor
        _mock_connect.return_value = mock_conn
        yield _mock_connect


def test_setup_database(mock_sqlite3_connect):
    app.setup_database()
    mock_sqlite3_connect.assert_called_once_with(app.DATABASE_FILE)
    mock_sqlite3_connect.return_value.cursor.assert_called_once()
    mock_sqlite3_connect.return_value.cursor.return_value.execute.assert_called_once()
    mock_sqlite3_connect.return_value.commit.assert_called_once()
    mock_sqlite3_connect.return_value.close.assert_called_once()

def test_shutdown_ubiquiti_devices_no_devices(mock_paramiko_sshclient, mock_logger):
    app.UBIQUITI_DEVICES = []
    app.shutdown_ubiquiti_devices()
    mock_paramiko_sshclient.assert_not_called()
    mock_logger.info.assert_called_with("No Ubiquiti devices configured for shutdown.")

def test_shutdown_ubiquiti_devices_success(mock_paramiko_sshclient, mock_logger):
    app.UBIQUITI_DEVICES = [{'host': '192.168.1.1', 'username': 'testuser', 'password': 'testpass'}]
    app.shutdown_ubiquiti_devices()
    mock_paramiko_sshclient.assert_called_once()
    mock_paramiko_sshclient.return_value.connect.assert_called_once_with(
        '192.168.1.1', username='testuser', password='testpass', timeout=10
    )
    mock_paramiko_sshclient.return_value.exec_command.assert_called_once_with("poweroff")
    mock_paramiko_sshclient.return_value.close.assert_called_once()
    mock_logger.info.assert_any_call("Successfully shut down 192.168.1.1")

def test_shutdown_ubiquiti_devices_auth_failure(mock_paramiko_sshclient, mock_logger):
    app.UBIQUITI_DEVICES = [{'host': '192.168.1.1', 'username': 'baduser', 'password': 'badpass'}]
    mock_paramiko_sshclient.return_value.connect.side_effect = app.paramiko.AuthenticationException
    app.shutdown_ubiquiti_devices()
    mock_logger.error.assert_called_with(
        "Authentication failed for 192.168.1.1. Please check your credentials in config.ini."
    )

def test_monitor_ups_normal_operation(mock_apcaccess_status, mock_sqlite3_connect, mock_logger, mock_config):
    mock_apcaccess_status.return_value = {
        'STATUS': 'ONLINE',
        'BCHARGE': '100.0',
        'LOADPCT': '10.0',
        'TIMELEFT': '60.0',
        'LINEV': '120.0',
        'BATTV': '13.0',
    }
    # Simulate running the loop once and then exiting
    with mock.patch('app.time.sleep', side_effect=InterruptedError):
        with pytest.raises(InterruptedError):
            app.monitor_ups()

    mock_apcaccess_status.assert_called_once()
    mock_sqlite3_connect.return_value.cursor.return_value.execute.assert_called_once()
    mock_sqlite3_connect.return_value.commit.assert_called_once()
    mock_logger.debug.assert_called_with(f"UPS Status: {mock_apcaccess_status.return_value}")
    mock_logger.warning.assert_not_called()
    mock_logger.info.assert_not_called()

def test_monitor_ups_shutdown_triggered(mock_apcaccess_status, mock_sqlite3_connect, mock_subprocess_run, mock_logger, mock_config):
    mock_apcaccess_status.return_value = {
        'STATUS': 'ONBATT',
        'BCHARGE': '15.0',
        'LOADPCT': '10.0',
        'TIMELEFT': '5.0',
        'LINEV': '0.0',
        'BATTV': '11.0',
    }
    app.UBIQUITI_DEVICES = [{'host': '192.168.1.1', 'username': 'testuser', 'password': 'testpass'}]

    with mock.patch('app.sys.exit') as mock_sys_exit:
        with mock.patch('app.shutdown_ubiquiti_devices') as mock_shutdown_ubiquiti_devices:
            app.monitor_ups()

            mock_logger.warning.assert_called_with("UPS power lost and battery threshold reached. Initiating shutdown sequence...")
            mock_shutdown_ubiquiti_devices.assert_called_once()
            mock_logger.info.assert_called_with("Shutting down local machine...")
            # subprocess.run is commented out in app.py for safety, so we assert it's not called
            mock_subprocess_run.assert_not_called()
            mock_logger.info.assert_called_with("Shutdown sequence complete. Exiting.")
            mock_sys_exit.assert_called_once_with(0)

def test_monitor_ups_apcaccess_failure(mock_apcaccess_status, mock_logger, mock_config):
    mock_apcaccess_status.side_effect = app.apcaccess.APCACCESS_GET_STATUS_FAILED

    with mock.patch('app.time.sleep', side_effect=InterruptedError):
        with pytest.raises(InterruptedError):
            app.monitor_ups()

    mock_logger.error.assert_called_with("Failed to get status from apcupsd. Is it running?")

def test_monitor_ups_sqlite_error(mock_apcaccess_status, mock_sqlite3_connect, mock_logger, mock_config):
    mock_apcaccess_status.return_value = {
        'STATUS': 'ONLINE',
        'BCHARGE': '100.0',
        'LOADPCT': '10.0',
        'TIMELEFT': '60.0',
        'LINEV': '120.0',
        'BATTV': '13.0',
    }
    mock_sqlite3_connect.return_value.cursor.return_value.execute.side_effect = sqlite3.Error("DB Error")

    with mock.patch('app.time.sleep', side_effect=InterruptedError):
        with pytest.raises(InterruptedError):
            app.monitor_ups()

    mock_logger.error.assert_called_with("Database error in monitoring loop: DB Error")
