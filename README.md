# **sigcap-buddy**

A tool to automatically log speedtest results on a Raspberry Pi.

## **Setup**

**Prerequisites**:
- A Raspberry Pi with a working network connection.

Simply run the following command on the Pi:
```
wget -q -O - https://raw.githubusercontent.com/adstriegel/sigcap-buddy/main/pi-setup.sh | bash
```
This will automatically install prerequisites apps, fetch scripts, setup systemd service, and set an update cronjob.

**Configuration**

The program reads a config.json file to determine various test configurations. The format is:

```
{
    "speedtest_interval": 60,            // Test interval in minutes.
    "upload_interval": 0,                // Upload interval in minutes, set 0 to upload right after the test.
    "iperf_server": "ns-mn1.cse.nd.edu", // Target iperf server.
    "iperf_maxport": 5206,               // iperf port will be randomized between 5201 and this variable.
    "iperf_duration": 10                 // Duration of iperf test.
}
```

## **Measurement Process**

The following steps described the measurement process at each interval:
1. A heartbeat message containing Pi's MAC and timestamp is pushed to our Firebase DB.
2. eth0 and wlan0 connection states are ensured. Particularly for wlan0, the script pulls Wi-Fi connection info from Firebase DB (identified by Pi's MAC address).
3. A suite of tests consists of iperf (DL and UL throughput), Ookla speedtest (DL, UL, and latency), and Wi-Fi beacon scanning are executed. Additionally, the iperf and Ookla speedtest runs on eth0 by disabling wlan0, and on wlan0 by disabling eth0.
4. All files are uploaded as defined by `upload_interval` in the config. All successfully uploaded files are deleted from storage.
5. If the Pi has just booted up (1 hour from the boot time), the script will transmit a heartbeat message every minute to ensure that the up state is pronounced.

## **Log Format**

For debugging purpose, the program logs is stored in `speedtest_logger.log`. Each test also stores its result logs in the `logs` folder with the following subfolder structure:
- `iperf-log` contains iperf logs in JSON format.
- `speedtest-log` contains Ookla speedtest logs in JSON format.
- `wifi-scan` contains the results of Wi-Fi scanning in JSON format.
