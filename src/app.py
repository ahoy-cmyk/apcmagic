#!/usr/bin/env python3

import configparser
import logging
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import apcaccess
import paramiko
import rumps
from flask import Flask, jsonify, render_template, request

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

# Configuration
config = configparser.ConfigParser()
if not CONFIG_FILE.is_file():
    logger.error(f"Configuration file not found at {CONFIG_FILE}")
    logger.error("Please copy config.ini.example to config.ini and fill in your details.")
    sys.exit(1)

config.read(CONFIG_FILE)

try:
    SHUTDOWN_THRESHOLD = config.getint("apcmagic", "shutdown_threshold")
    MONITOR_INTERVAL = config.getint("apcmagic", "monitor_interval_seconds")
    ubiquiti_hosts_str = config.get("ubiquiti", "hosts")
    ubiquiti_username = config.get("ubiquiti", "username")
    ubiquiti_password = config.get("ubiquiti", "password")
except (configparser.NoSectionError, configparser.NoOptionError) as e:
    logger.error(f"Error in configuration file: {e}")
    sys.exit(1)

# Create UBIQUITI_DEVICES list from config
UBIQUITI_DEVICES = []
if ubiquiti_hosts_str:
    ubiquiti_hosts = [h.strip() for h in ubiquiti_hosts_str.split(',')]
    for host in ubiquiti_hosts:
        if host:
            UBIQUITI_DEVICES.append({
                "host": host,
                "username": ubiquiti_username,
                "password": ubiquiti_password,
            })


# rumps app
class APCApp(rumps.App):
    def __init__(self):
        super(APCApp, self).__init__("APC UPS Status")
        self.menu = ["Status", "Quit"]

    @rumps.clicked("Status")
    def status(self, _):
        try:
            status = apcaccess.get_status()
            rumps.alert(
                title="APC UPS Status",
                message=f"Status: {status['STATUS']}\n" \
                        f"Battery: {status['BCHARGE']}%\n" \
                        f"Load: {status['LOADPCT']}%\n" \
                        f"Time Left: {status['TIMELEFT']}",
            )
        except Exception as e:
            rumps.alert(title="Error", message=str(e))
            logger.error(f"Error in rumps app status: {e}")

# Flask app
app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/status")
def api_status():
    try:
        status = apcaccess.get_status()
        return jsonify(status)
    except Exception as e:
        logger.error(f"Error in /api/status: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/history")
def api_history():
    timerange = request.args.get("timerange", "1h")

    time_deltas = {
        "1h": "-1 hour",
        "24h": "-1 day",
        "7d": "-7 days",
    }

    if timerange not in time_deltas:
        return jsonify({"error": "Invalid timerange"}), 400

    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM ups_data WHERE timestamp > datetime('now', ?) ORDER BY timestamp DESC",
            (time_deltas[timerange],),
        )
        data = cursor.fetchall()
        conn.close()
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error in /api/history: {e}")
        return jsonify({"error": str(e)}), 500

# Database setup
def setup_database():
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
                timeleft REAL
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
def shutdown_ubiquiti_devices():
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
                password=device["password"],
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
def monitor_ups():
    setup_database()
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()

    while True:
        try:
            status = apcaccess.get_status()
            logger.debug(f"UPS Status: {status}")
            cursor.execute(
                "INSERT INTO ups_data (status, bcharge, loadpct, timeleft) VALUES (?, ?, ?, ?)",
                (
                    status["STATUS"],
                    status["BCHARGE"],
                    status["LOADPCT"],
                    status["TIMELEFT"],
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

        except apcaccess.APCACCESS_GET_STATUS_FAILED:
            logger.error("Failed to get status from apcupsd. Is it running?")
        except sqlite3.Error as e:
            logger.error(f"Database error in monitoring loop: {e}")
        except Exception as e:
            logger.error(f"An unexpected error occurred in the monitoring loop: {e}")

        time.sleep(MONITOR_INTERVAL)

if __name__ == "__main__":
    # Start the monitoring loop in a separate thread
    import threading

    monitor_thread = threading.Thread(target=monitor_ups)
    monitor_thread.daemon = True
    monitor_thread.start()

    # Start the Flask app
    # app.run(debug=True, use_reloader=False)

    # Start the rumps app
    APCApp().run()
