#!/usr/bin/env python3

import configparser
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import apcaccess
import paramiko
import rumps
from flask import Flask, jsonify, render_template

# Constants
BASE_DIR = Path(__file__).parent.parent
DATABASE_FILE = BASE_DIR / "data" / "apc_data.db"
CONFIG_FILE = BASE_DIR / "config.ini"

# Configuration
config = configparser.ConfigParser()
if not CONFIG_FILE.is_file():
    print(f"Error: Configuration file not found at {CONFIG_FILE}")
    print("Please copy config.ini.example to config.ini and fill in your details.")
    sys.exit(1)

config.read(CONFIG_FILE)

try:
    SHUTDOWN_THRESHOLD = config.getint("apcmagic", "shutdown_threshold")
    MONITOR_INTERVAL = config.getint("apcmagic", "monitor_interval_seconds")
    ubiquiti_hosts_str = config.get("ubiquiti", "hosts")
    ubiquiti_username = config.get("ubiquiti", "username")
    ubiquiti_password = config.get("ubiquiti", "password")
except (configparser.NoSectionError, configparser.NoOptionError) as e:
    print(f"Error in configuration file: {e}")
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
        return jsonify({"error": str(e)}), 500

@app.route("/api/history")
def api_history():
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ups_data ORDER BY timestamp DESC LIMIT 100")
    data = cursor.fetchall()
    conn.close()
    return jsonify(data)

# Database setup
def setup_database():
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


# Ubiquiti shutdown
def shutdown_ubiquiti_devices():
    for device in UBIQUITI_DEVICES:
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(
                device["host"],
                username=device["username"],
                password=device["password"],
                timeout=10,
            )
            print(f"Shutting down {device['host']}")
            ssh.exec_command("poweroff")
            ssh.close()
        except Exception as e:
            print(f"Error shutting down {device['host']}: {e}")


# Monitoring loop
def monitor_ups():
    setup_database()
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()

    while True:
        try:
            status = apcaccess.get_status()
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
                # Initiate shutdown
                print("UPS power lost and battery threshold reached. Shutting down...")
                shutdown_ubiquiti_devices()
                subprocess.run(["shutdown", "-h", "now"])

        except Exception as e:
            print(f"Error: {e}")

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
