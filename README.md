# apcmagic

A Python application for monitoring an APC Back-UPS Pro BR1500MS2 via USB, with statistics, visualization, and automated shutdown capabilities for macOS and Ubiquiti devices.

## Features

*   **UPS Monitoring:** Real-time monitoring of UPS status, battery charge, load, input voltage, battery voltage, and estimated runtime.
*   **Web Dashboard:** A web-based interface to visualize current and historical UPS data with selectable time ranges.
*   **Data Logging:** Historical UPS data is stored in a local SQLite database.
*   **Automated Shutdown:**
    *   Initiates a graceful shutdown of the host macOS machine when the UPS is on battery and reaches a critical charge threshold.
    *   Sends shutdown commands to configured Ubiquiti network devices using either password or SSH key authentication.
*   **Menu Bar App:** A simple macOS menu bar application to quickly check the UPS status.
*   **Robust Logging:** Detailed logging to console and file for monitoring application behavior and troubleshooting.

## Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/ahoy-cmyk/apcmagic.git
    ```

2.  **Install `apcupsd`:**
    This application relies on `apcupsd` to communicate with the UPS. You can install it using Homebrew:
    ```bash
    brew install apcupsd
    ```
    You will need to configure `apcupsd` to work with your specific UPS model. The primary configuration file is typically located at `/usr/local/etc/apcupsd/apcupsd.conf`.

3.  **Install Python dependencies:**
    It is highly recommended to use a virtual environment.
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -e .
    ```

## Configuration

Before running the application, you need to set up your configuration.

1.  **Copy the example configuration file:**
    ```bash
    cp config.ini.example config.ini
    ```

2.  **Edit `config.ini`:**
    Open `config.ini` in your preferred text editor and update the following sections:

    *   **`[apcmagic]` section:**
        *   `shutdown_threshold`: The battery charge percentage (e.g., `20`) at which the shutdown sequence will be initiated.
        *   `monitor_interval_seconds`: The time in seconds (e.g., `60`) between each check of the UPS status.

    *   **`[ubiquiti]` section:**
        *   `hosts`: A comma-separated list of hostnames or IP addresses for your Ubiquiti devices (e.g., `192.168.1.1,192.168.1.2`).
        *   `username`: The SSH username for your Ubiquiti devices.
        *   `password`: (Optional) The SSH password for your Ubiquiti devices. **It is highly recommended to use SSH keys instead of passwords for security.**
        *   `ssh_key_path`: (Optional) The absolute path to your SSH private key file (e.g., `~/.ssh/id_rsa`). If both `password` and `ssh_key_path` are provided, `ssh_key_path` will be prioritized.

## Usage

Once configured, run the application from the project root directory:

```bash
apcmagic
```

This will:
*   Start a background thread that continuously monitors the UPS status.
*   Launch a simple macOS menu bar application for quick status checks.
*   Start a Flask web server for the dashboard.

### Accessing the Web Dashboard

Open your web browser and navigate to `http://127.0.0.1:5000` to view the UPS status and historical data. You can select different time ranges to view the data.

## How It Works

The `apcmagic` application is structured into several modular components:

*   **`app.py` (Main Application Logic):**
    *   Handles configuration loading from `config.ini`.
    *   Initializes logging to both console and a log file (`logs/apcmagic.log`).
    *   Manages the main monitoring loop, which periodically fetches UPS data using `apcaccess`.
    *   Stores UPS data in an SQLite database (`data/apc_data.db`).
    *   Triggers the shutdown sequence for Ubiquiti devices and the local machine when the UPS is on battery and the charge falls below the configured `shutdown_threshold`.

*   **`rumps_app.py` (macOS Menu Bar Application):**
    *   Provides a `rumps`-based application for displaying current UPS status in the macOS menu bar.
    *   Allows users to quickly check key UPS metrics via a simple alert window.

*   **`web_app.py` (Flask Web Server):**
    *   Implements a Flask web application that serves the interactive dashboard.
    *   Provides API endpoints (`/api/status` and `/api/history`) to fetch real-time and historical UPS data.
    *   The `/api/history` endpoint supports `timerange` parameters to filter historical data (e.g., `1h`, `24h`, `7d`).

*   **`setup_database()` function:** Ensures the SQLite database and its schema are correctly set up on application start.

*   **`shutdown_ubiquiti_devices()` function:** Connects to configured Ubiquiti devices via SSH (prioritizing SSH key authentication if available) and executes the `poweroff` command.

## Development

### Running Tests

To run the unit tests, ensure you have `pytest` installed (it's included in `requirements.txt` and installed via `pip install -e .`). From the project root directory, run:

```bash
pytest
```

### Code Structure

```
.apcmagic/
├── src/
│   ├── app.py
│   ├── rumps_app.py
│   └── web_app.py
├── data/
│   └── apc_data.db  (SQLite database - created on first run)
├── logs/
│   └── apcmagic.log (Application logs - created on first run)
├── templates/
│   └── index.html
├── tests/
│   ├── test_app.py
│   └── test_web_app.py
├── .gitignore
├── config.ini.example
├── README.md
├── requirements.txt
└── setup.py
```