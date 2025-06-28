# APCMagic

APCMagic is a Python application designed to monitor APC UPS devices, log their status, and gracefully shut down connected Ubiquiti devices and the local machine when power is lost and the UPS battery reaches a critical threshold. It also provides a web interface and a macOS menu bar application for monitoring.

## Features

*   **UPS Monitoring:** Continuously monitors APC UPS devices for status, battery charge, load, and time remaining.
*   **Configurable Shutdown Threshold:** Shuts down connected devices and the local machine when the UPS battery level drops below a user-defined threshold.
*   **Ubiquiti Device Shutdown:** Integrates with Ubiquiti devices (e.g., UniFi switches, access points) to initiate a graceful shutdown via SSH.
*   **Data Logging:** Stores historical UPS data in an SQLite database.
*   **Web Interface:** Provides a simple web interface to view current UPS status and historical data.
*   **macOS Menu Bar Application:** Offers a native macOS application for quick status checks from the menu bar.

## Installation

1.  **Clone the repository:**

    ```bash
    git clone https://github.com/your-repo/apcmagic.git
    cd apcmagic
    ```

2.  **Create and activate a virtual environment:**

    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install dependencies:**

    ```bash
    pip install -e .
    ```

4.  **Configure the application:**

    Copy the example configuration file and edit it with your settings:

    ```bash
    cp config.ini.example config.ini
    nano config.ini
    ```

    *   **`[apcmagic]` section:**
        *   `shutdown_threshold`: The battery percentage at which to initiate shutdown (e.g., `20`).
        *   `monitor_interval_seconds`: The interval (in seconds) between UPS status checks (e.g., `60`).
    *   **`[ubiquiti]` section:**
        *   `hosts`: Comma-separated list of Ubiquiti device IP addresses or hostnames (e.g., `192.168.1.10,192.168.1.11`).
        *   `username`: SSH username for your Ubiquiti devices.
        *   `password`: SSH password for your Ubiquiti devices (use `ssh_key_path` instead for key-based authentication).
        *   `ssh_key_path`: Absolute path to your SSH private key (e.g., `/home/user/.ssh/id_rsa`).

5.  **Ensure `apcupsd` is running:**

    This application relies on `apcupsd` to communicate with your UPS. Make sure `apcupsd` is installed and configured correctly on your system, and its Network Information Server (NIS) is enabled (usually on port 3551).

## Usage

To start the APCMagic application (which includes the monitoring loop, web server, and macOS menu bar app):

```bash
python3 src/app.py
```

*   **Web Interface:** Access the web interface by opening your browser to `http://127.0.0.1:5000` (or the port Flask is running on).
*   **macOS Menu Bar App:** The menu bar application will appear in your macOS menu bar, providing quick access to UPS status.

## Project Structure

```
apcmagic/
├── config.ini.example
├── pytest.ini
├── README.md
├── requirements.txt
├── setup.py
├── data/
│   └── apc_data.db
├── docs/
│   └── README.md
├── logs/
│   └── apcmagic.log
├── src/
│   ├── __init__.py
│   ├── app.py
│   ├── rumps_app.py
│   ├── web_app.py
├── static/
├── templates/
│   └── index.html
└── venv/
```

## Testing

To run the tests for this project:

```bash
pytest tests/
```

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## License

This project is licensed under the MIT License - see the `LICENSE` file for details. (Note: A `LICENSE` file is not included in the provided structure, but it's good practice to mention it.)
