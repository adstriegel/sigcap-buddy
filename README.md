# **sigcap-buddy**

A tool to automatically log speedtest results on a Raspberry Pi.

## **Setup**
**Prerequisites**:

- A Raspberry Pi with a working network connection.
- Python 3 installed.

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


