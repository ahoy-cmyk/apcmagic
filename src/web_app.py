import logging
import sqlite3
from pathlib import Path

import apcaccess
from flask import Flask, jsonify, render_template, request

logger = logging.getLogger("apcmagic")

# Constants
BASE_DIR = Path(__file__).parent.parent
DATABASE_FILE = BASE_DIR / "data" / "apc_data.db"

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
