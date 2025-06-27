#!/usr/bin/env python3

import sqlite3
import subprocess
import time
from pathlib import Path

import apcaccess
import rumps
from flask import Flask, jsonify, render_template

# Constants
DATABASE_FILE = Path(__file__).parent.parent / "data" / "apc_data.db"

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
            if status["STATUS"] == "ONBATT" and float(status["BCHARGE"]) < 20:
                # Initiate shutdown
                subprocess.run(["shutdown", "-h", "now"])

        except Exception as e:
            print(f"Error: {e}")

        time.sleep(60)

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
