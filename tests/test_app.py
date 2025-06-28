import pytest
import unittest.mock as mock
from pathlib import Path
import sqlite3
import apcaccess

import app

import apcaccess

# Mock the logger to prevent actual logging during tests
@pytest.fixture(autouse=True)
def mock_logger():
    with mock.patch('app.logger') as _mock_logger:
        yield _mock_logger

@pytest.fixture(autouse=True)
def setup_config_file(tmp_path):
    # Create a dummy config.ini for testing
    config_content = """
[apcmagic]
shutdown_threshold = 20
monitor_interval_seconds = 1

[ubiquiti]
hosts = 
username = testuser
password = testpass
ssh_key_path = 
"""
    config_file = tmp_path / "config.ini"
    config_file.write_text(config_content)

    # Temporarily change the CONFIG_FILE path in app.py
    original_config_file = app.CONFIG_FILE
    app.CONFIG_FILE = config_file
    yield
    app.CONFIG_FILE = original_config_file # Restore original path

@pytest.fixture
def mock_config():
    with mock.patch('app.configparser.ConfigParser') as MockConfigParser:
        mock_config_instance = MockConfigParser.return_value
        mock_config_instance.getint.side_effect = lambda section, option: {
            ('apcmagic', 'shutdown_threshold'): 20,
            ('apcmagic', 'monitor_interval_seconds'): 1,
        }[(section, option)]
        mock_config_instance.get.side_effect = lambda section, option, fallback=None: {
            ('ubiquiti', 'hosts'): '192.168.1.1',
            ('ubiquiti', 'username'): 'testuser',
            ('ubiquiti', 'password'): 'testpass',
            ('ubiquiti', 'ssh_key_path'): fallback,
        }.get((section, option), fallback)
        yield

@pytest.fixture
def mock_apcaccess_get_parse():
    with mock.patch('apcaccess.status.get') as _mock_get,          mock.patch('apcaccess.status.parse') as _mock_parse:
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













@pytest.fixture
def mock_subprocess_run():
    with mock.patch('app.subprocess.run') as _mock_run:
        yield _mock_run

@pytest.fixture
def mock_paramiko_sshclient():
    with mock.patch('app.paramiko.SSHClient') as MockSSHClient:
        mock_ssh_instance = MockSSHClient.return_value
        mock_ssh_instance.set_missing_host_key_policy = mock.Mock()
        mock_ssh_instance.connect = mock.Mock()
        mock_ssh_instance.exec_command = mock.Mock()
        mock_ssh_instance.close = mock.Mock()
        yield mock_ssh_instance

@pytest.fixture
def mock_sqlite3_connect():
    with mock.patch('app.sqlite3.connect') as _mock_connect:
        mock_conn = mock.Mock()
        mock_cursor = mock.Mock()
        mock_conn.cursor.return_value = mock_cursor
        _mock_connect.return_value = mock_conn
        yield _mock_connect


def test_setup_database(mock_sqlite3_connect, mock_config):
    app._load_configuration()
    app.setup_database()
    mock_sqlite3_connect.assert_called_once_with(app.DATABASE_FILE)
    mock_sqlite3_connect.return_value.cursor.assert_called_once()
    mock_sqlite3_connect.return_value.cursor.return_value.execute.assert_called_once()
    mock_sqlite3_connect.return_value.commit.assert_called_once()
    mock_sqlite3_connect.return_value.close.assert_called_once()

def test_shutdown_ubiquiti_devices_no_devices(mock_paramiko_sshclient, mock_logger, mock_config):
    app._load_configuration()
    app.UBIQUITI_DEVICES.clear() # Ensure it's empty for this test
    app.shutdown_ubiquiti_devices()
    mock_paramiko_sshclient.assert_not_called()
    mock_logger.info.assert_called_with("No Ubiquiti devices configured for shutdown.")

def test_shutdown_ubiquiti_devices_success_password(mock_paramiko_sshclient, mock_logger, mock_config):
    app._load_configuration()
    app.UBIQUITI_DEVICES.clear()
    app.UBIQUITI_DEVICES.append({'host': '192.168.1.1', 'username': 'testuser', 'password': 'testpass'})
    app.shutdown_ubiquiti_devices()
    mock_paramiko_sshclient.connect.assert_called_once_with(
        '192.168.1.1', username='testuser', password='testpass', key_filename=None, timeout=10
    )
    mock_paramiko_sshclient.exec_command.assert_called_once_with("poweroff")
    mock_paramiko_sshclient.close.assert_called_once()
    mock_logger.info.assert_any_call("Successfully shut down 192.168.1.1")

def test_shutdown_ubiquiti_devices_success_ssh_key(mock_paramiko_sshclient, mock_logger, tmp_path, mock_config):
    app._load_configuration()
    # Create a dummy SSH key file
    ssh_key_file = tmp_path / "id_rsa"
    ssh_key_file.write_text("-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----\n")

    app.UBIQUITI_DEVICES.clear()
    app.UBIQUITI_DEVICES.append({'host': '192.168.1.2', 'username': 'testuser', 'key_filename': str(ssh_key_file)})
    app.shutdown_ubiquiti_devices()
    mock_paramiko_sshclient.connect.assert_called_once_with(
        '192.168.1.2', username='testuser', password=None, key_filename=str(ssh_key_file), timeout=10
    )
    mock_paramiko_sshclient.exec_command.assert_called_once_with("poweroff")
    mock_paramiko_sshclient.close.assert_called_once()
    mock_logger.info.assert_any_call("Successfully shut down 192.168.1.2")

def test_shutdown_ubiquiti_devices_auth_failure_password(mock_paramiko_sshclient, mock_logger, mock_config):
    app._load_configuration()
    app.UBIQUITI_DEVICES.clear()
    app.UBIQUITI_DEVICES.append({'host': '192.168.1.1', 'username': 'baduser', 'password': 'badpass'})
    mock_paramiko_sshclient.return_value.connect.side_effect = app.paramiko.AuthenticationException
    with mock.patch('app.sys.exit'):
        app.shutdown_ubiquiti_devices()
    mock_logger.error.assert_any_call(
        "Authentication failed for 192.168.1.1. Please check your credentials in config.ini."
    )

def test_shutdown_ubiquiti_devices_auth_failure_ssh_key(mock_paramiko_sshclient, mock_logger, tmp_path, mock_config):
    app._load_configuration()
    ssh_key_file = tmp_path / "id_rsa"
    ssh_key_file.write_text("-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----\n")

    app.UBIQUITI_DEVICES.clear()
    app.UBIQUITI_DEVICES.append({'host': '192.168.1.2', 'username': 'baduser', 'key_filename': str(ssh_key_file)})
    mock_paramiko_sshclient.return_value.connect.side_effect = app.paramiko.AuthenticationException
    with mock.patch('app.sys.exit'):
        app.shutdown_ubiquiti_devices()
    mock_logger.error.assert_any_call(
        "Authentication failed for 192.168.1.2. Please check your credentials in config.ini."
    )

def test_shutdown_ubiquiti_devices_no_auth_method(mock_paramiko_sshclient, mock_logger, mock_config):
    app._load_configuration()
    app.UBIQUITI_DEVICES.clear()
    app.UBIQUITI_DEVICES.append({'host': '192.168.1.3', 'username': 'testuser'}) # No password or key_filename
    with mock.patch('app.sys.exit'):
        app.shutdown_ubiquiti_devices()
    mock_paramiko_sshclient.assert_not_called()
    mock_logger.warning.assert_any_call(
        "No SSH key or password provided for 192.168.1.3. Skipping."
    )


def test_monitor_ups_normal_operation(mock_apcaccess_get_parse, mock_sqlite3_connect, mock_logger, mock_config):
    app._load_configuration()
    mock_apcaccess_get_parse[0].return_value = "raw_status_string"
    mock_apcaccess_get_parse[1].return_value = {
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

    mock_apcaccess_get_parse[0].assert_called_once()
    mock_sqlite3_connect.return_value.cursor.return_value.execute.assert_called_once()
    mock_sqlite3_connect.return_value.commit.assert_called_once()
    mock_logger.debug.assert_called_with(f"UPS Status: {mock_apcaccess_get_parse[1].return_value}")
    mock_logger.warning.assert_not_called()
    mock_logger.info.assert_not_called()

def test_monitor_ups_shutdown_triggered(mock_apcaccess_get_parse, mock_sqlite3_connect, mock_subprocess_run, mock_logger, mock_config):
    app._load_configuration()
    mock_apcaccess_get_parse[0].return_value = "raw_status_string"
    mock_apcaccess_get_parse[1].return_value = {
        'STATUS': 'ONBATT',
        'BCHARGE': '15.0',
        'LOADPCT': '10.0',
        'TIMELEFT': '5.0',
        'LINEV': '0.0',
        'BATTV': '11.0',
    }
    app.UBIQUITI_DEVICES.clear()
    app.UBIQUITI_DEVICES.append({'host': '192.168.1.1', 'username': 'testuser', 'password': 'testpass'})

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

def test_monitor_ups_apcaccess_failure(mock_apcaccess_get_parse, mock_logger, mock_config):
    app._load_configuration()
    mock_apcaccess_get_parse[0].side_effect = Exception("Connection refused")

    with mock.patch('app.time.sleep', side_effect=InterruptedError):
        with pytest.raises(InterruptedError):
            app.monitor_ups()

    mock_logger.error.assert_called_with("Failed to get status from apcupsd. Is it running? Error: Connection refused")

def test_monitor_ups_sqlite_error(mock_apcaccess_get_parse, mock_sqlite3_connect, mock_logger, mock_config):
    app._load_configuration()
    mock_apcaccess_get_parse[0].return_value = "raw_status_string"
    mock_apcaccess_get_parse[1].return_value = {
        'STATUS': 'ONLINE',
        'BCHARGE': '100.0',
        'LOADPCT': '10.0',
        'TIMELEFT': '60.0',
        'LINEV': '120.0',
        'BATTV': '13.0',
    }
    mock_sqlite3_connect.return_value.cursor.return_value.execute.side_effect = sqlite3.Error("DB Error")

    with mock.patch('app.time.sleep', side_effect=InterruptedError):
        with mock.patch('app.sys.exit') as mock_sys_exit:
            with pytest.raises(InterruptedError):
                app.monitor_ups()
    mock_sys_exit.assert_called_once_with(1)

    mock_logger.error.assert_called_with("Database error in monitoring loop: DB Error")
