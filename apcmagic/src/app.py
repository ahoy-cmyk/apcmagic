#!/usr/bin/env python3

import configparser
import logging
import sqlite3
import subprocess
import sys
import time
import threading
from pathlib import Path

from apcaccess.status import get, parse
import paramiko
import apcaccess

from rumps_app import APCApp
from web_app import app as flask_app

# Constants
BASE_DIR = Path(__file__).parent.parent
DATABASE_FILE = BASE_DIR / "data" / "apc_data.db"
CONFIG_FILE = BASE_DIR / "config.ini"
LOG_FILE = BASE_DIR / "logs" / "apcmagic.log"

# Create logs directory if it doesn't exist
LOG_FILE.parent.mkdir(exist_ok=True)

# --- Logging Setup ---
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# File Handler
file_handler = logging.FileHandler(LOG_FILE)
file_handler.setLevel(logging.INFO)

# Console Handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# Formatter
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Add Handlers to Logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)
# --- End Logging Setup ---

# Global variables (will be set by _load_configuration)
SHUTDOWN_THRESHOLD: int = 0
MONITOR_INTERVAL: int = 0
UBIQUITI_DEVICES: list[dict] = []

def _load_configuration() -> None:
    """Loads configuration from config.ini and populates global variables."""
    global SHUTDOWN_THRESHOLD, MONITOR_INTERVAL, UBIQUITI_DEVICES

    config = configparser.ConfigParser()
    if not CONFIG_FILE.is_file():
        logger.error(f"Configuration file not found at {CONFIG_FILE}")
        logger.error("Please copy config.ini.example to config.ini and fill in your details.")
        sys.exit(1) # Keep sys.exit for direct execution, tests will mock this.

    config.read(CONFIG_FILE)

    try:
        SHUTDOWN_THRESHOLD = config.getint("apcmagic", "shutdown_threshold")
        MONITOR_INTERVAL = config.getint("apcmagic", "monitor_interval_seconds")
        ubiquiti_hosts_str = config.get("ubiquiti", "hosts")
        ubiquiti_username = config.get("ubiquiti", "username")
        ubiquiti_password = config.get("ubiquiti", "password", fallback=None)
        ubiquiti_ssh_key_path = config.get("ubiquiti", "ssh_key_path", fallback=None)
    except (configparser.NoSectionError, configparser.NoOptionError) as e:
        logger.error(f"Error in configuration file: {e}")
        sys.exit(1) # Keep sys.exit for direct execution, tests will mock this.

    # Create UBIQUITI_DEVICES list from config
    UBIQUITI_DEVICES.clear() # Clear existing list for re-runs in tests
    if ubiquiti_hosts_str:
        ubiquiti_hosts = [h.strip() for h in ubiquiti_hosts_str.split(',')]
        for host in ubiquiti_hosts:
            if host:
                # Determine authentication method
                auth_method = {}
                if ubiquiti_ssh_key_path and Path(ubiquiti_ssh_key_path).expanduser().is_file():
                    auth_method["key_filename"] = str(Path(ubiquiti_ssh_key_path).expanduser())
                    logger.info(f"Using SSH key for {host}")
                elif ubiquiti_password:
                    auth_method["password"] = ubiquiti_password
                    logger.info(f"Using password for {host}")
                else:
                    logger.warning(f"No SSH key or password provided for {host}. Skipping.")
                    continue

                UBIQUITI_DEVICES.append({
                    "host": host,
                    "username": ubiquiti_username,
                    **auth_method,
                })

# Database setup
def setup_database() -> None:
    """Sets up the SQLite database for storing UPS data. Creates the table if it doesn't exist."""
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS ups_data (
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                status TEXT,
                bcharge REAL,
                loadpct REAL,
                timeleft REAL,
                linev REAL,
                battv REAL
            )
            """
        )
        conn.commit()
        conn.close()
        logger.info("Database setup complete.")
    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")
        sys.exit(1)


# Ubiquiti shutdown
def shutdown_ubiquiti_devices() -> None:
    """Shuts down configured Ubiquiti devices via SSH."""
    if not UBIQUITI_DEVICES:
        logger.info("No Ubiquiti devices configured for shutdown.")
        return

    for device in UBIQUITI_DEVICES:
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            logger.info(f"Connecting to {device['host']} for shutdown...")
            ssh.connect(
                device["host"],
                username=device["username"],
                password=device.get("password"),
                key_filename=device.get("key_filename"),
                timeout=10,
            )
            logger.info(f"Sending shutdown command to {device['host']}")
            ssh.exec_command("poweroff")
            ssh.close()
            logger.info(f"Successfully shut down {device['host']}")
        except paramiko.AuthenticationException:
            logger.error(f"Authentication failed for {device['host']}. Please check your credentials in config.ini.")
        except Exception as e:
            logger.error(f"Error shutting down {device['host']}: {e}")


# Monitoring loop
def monitor_ups() -> None:
    """Monitors the UPS status, logs data, and initiates shutdown if necessary."""
    setup_database()
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()

    while True:
        try:
            raw_status = get()
            status = parse(raw_status)
            logger.debug(f"UPS Status: {status}")
            cursor.execute(
                "INSERT INTO ups_data (status, bcharge, loadpct, timeleft, linev, battv) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    status["STATUS"],
                    status["BCHARGE"],
                    status["LOADPCT"],
                    status["TIMELEFT"],
                    status["LINEV"],
                    status["BATTV"],
                ),
            )
            conn.commit()

            # Check for power loss and battery threshold
            if status["STATUS"] == "ONBATT" and float(status["BCHARGE"]) < SHUTDOWN_THRESHOLD:
                logger.warning("UPS power lost and battery threshold reached. Initiating shutdown sequence...")
                shutdown_ubiquiti_devices()
                logger.info("Shutting down local machine...")
                # Uncomment the following line to enable shutdown
                # subprocess.run(["shutdown", "-h", "now"])
                logger.info("Shutdown sequence complete. Exiting.")
                sys.exit(0)

        except Exception as e:
            logger.error("Failed to get status from apcupsd. Is it running? Error: %s" % e)
        except sqlite3.Error as e:
            logger.error(f"Database error in monitoring loop: {e}")
        except Exception as e:
            logger.error(f"An unexpected error occurred in the monitoring loop: {e}")

        time.sleep(MONITOR_INTERVAL)

def main() -> None:
    """Main function to start the monitoring, web, and rumps applications."""
    _load_configuration()

    # Start the monitoring loop in a separate thread
    monitor_thread = threading.Thread(target=monitor_ups)
    monitor_thread.daemon = True
    monitor_thread.start()

    # Start the Flask app in a separate thread
    flask_thread = threading.Thread(target=lambda: flask_app.run(debug=True, use_reloader=False))
    flask_thread.daemon = True
    flask_thread.start()

    # Start the rumps app
    APCApp().run()

if __name__ == "__main__":
    main()
