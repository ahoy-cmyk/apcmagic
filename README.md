# apcmagic

A Python application for monitoring an APC Back-UPS Pro BR1500MS2 via USB, with statistics, visualization, and automated shutdown capabilities for macOS and Ubiquiti devices.

## Features

*   **UPS Monitoring:** Real-time monitoring of UPS status, battery charge, load, and estimated runtime.
*   **Web Dashboard:** A web-based interface to visualize current and historical UPS data.
*   **Data Logging:** Historical UPS data is stored in a local SQLite database.
*   **Automated Shutdown:**
    *   Initiates a graceful shutdown of the host macOS machine when the UPS is on battery and reaches a critical charge threshold.
    *   Sends shutdown commands to configured Ubiquiti network devices.
*   **Menu Bar App:** A simple macOS menu bar application to quickly check the UPS status.

## Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/ahoy-cmyk/apcmagic.git
    cd apcmagic
    ```

2.  **Install `apcupsd`:**
    This application relies on `apcupsd` to communicate with the UPS. You can install it using Homebrew:
    ```bash
    brew install apcupsd
    ```
    You will need to configure `apcupsd` to work with your specific UPS model. The primary configuration file is typically located at `/usr/local/etc/apcupsd/apcupsd.conf`.

3.  **Install Python dependencies:**
    It is recommended to use a virtual environment.
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```

## Usage

1.  **Configure Ubiquiti Devices:**
    Open `src/app.py` and edit the `UBIQUITI_DEVICES` list to include the IP address and SSH credentials for your Ubiquiti devices.

    ```python
    # src/app.py

    # ...

    # Ubiquiti Configuration
    UBIQUITI_DEVICES = [
        {
            "host": "YOUR_DEVICE_IP",
            "username": "YOUR_SSH_USERNAME",
            "password": "YOUR_SSH_PASSWORD",
        },
        # Add more devices here
    ]

    # ...
    ```

2.  **Run the application:**
    ```bash
    python src/app.py
    ```

    This will:
    *   Start the background monitoring process.
    *   Launch the macOS menu bar icon.
    *   Start the Flask web server for the dashboard.

3.  **Access the Dashboard:**
    Open your web browser and navigate to `http://127.0.0.1:5000` to view the UPS status and historical data.

## How It Works

The application consists of three main components:

1.  **Monitoring Loop:** A background thread that runs continuously to fetch the UPS status using the `apcaccess` command. It stores this data in an SQLite database and checks for shutdown conditions.
2.  **Flask Web Server:** Provides a web interface with API endpoints to retrieve current and historical UPS data, which is then displayed on a chart.
3.  **rumps Menu Bar App:** Creates a simple icon in the macOS menu bar that allows you to quickly see the UPS status.

If the UPS is on battery power and the battery charge drops below 20%, the application will first attempt to shut down the configured Ubiquiti devices via SSH and then initiate a shutdown of the local machine.
