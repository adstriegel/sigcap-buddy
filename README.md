# **sigcap-buddy**

A tool to automatically log speedtest results on a Raspberry Pi.

## **Setup**

**Prerequisites**:
- A Raspberry Pi with a working network connection.
- Python 3 installed.
- Ookla Speedtest CLI (Automatically downloaded and set up by the script if not present.)
- `inotify-tools` package installed. 

**Configuration**

The program reads a config.json file to determine the interval between speed tests. The format is:

{
    "speedtest_interval": 5  // The interval, in minutes, between tests.
}


## **Execution**

This script runs as a service on the Raspberry Pi, logging speedtest results at intervals defined in the config file.

1. Move the provided speedtest_logger.service to the /etc/systemd/system/ directory:
sudo cp speedtest_logger.service /etc/systemd/system/

2. Reload the systemd manager configuration
sudo systemctl daemon-reload

3. Start the service:
sudo systemctl start speedtest_logger.service

4. To ensure the serve starts authomatically on boot: 
sudo systemctl enable speedtest_logger.service


## **Code Monitoring and Auto-Updates**

The script `monitor_changes.sh` can be set up to monitor the codebase for any changes and auto-update the service upon any changes.

1. Ensure the `monitor_changes.sh` script is executable:

chmod +x monitor_changes.sh


2. Run the script as a cronjob so it always starts at boot time

## **Log Format**

The program logs the results of each test in speedtest_log.json. Each entry is a separate line and is structured as:

{
    "start_time": "ISO timestamp when test started",
    "end_time": "ISO timestamp when test ended",
    "server": "Name of the test server",
    "isp": "Name of your ISP",
    "idle_latency": "Ping latency in ms",
    "download_speed": "Download speed in bps",
    "upload_speed": "Upload speed in bps",
    "download_data_used": "Data used for the download test in bytes",
    "upload_data_used": "Data used for the upload test in bytes"
}


