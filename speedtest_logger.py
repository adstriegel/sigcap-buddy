from datetime import datetime, timedelta, timezone
import firebase
from getpass import getuser
import json
import logging
from logging.handlers import TimedRotatingFileHandler
from logging import Formatter
from random import randint
import time
import utils
from uuid import uuid4
import wifi_scan

logdir = "/home/{}/sigcap-buddy/logs".format(getuser())

# Logging setup
handler = TimedRotatingFileHandler(
    filename="{}/speedtest_logger.log".format(logdir),
    when="D", interval=1, backupCount=90, encoding="utf-8",
    delay=False)
formatter = Formatter(
    fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logging.basicConfig(
    handlers=[handler],
    level=logging.DEBUG
)

logging.info("Script started.")

# Get eth0 MAC address
mac = "00-00-00-00-00-00"
try:
    mac = open("/sys/class/net/eth0/address").readline()[0:17].upper().replace(
        ":", "-")
except Exception as e:
    logging.error("Cannot retrieve eth0 MAC address: %s", e, exc_info=1)

logging.info("eth0 MAC address: %s", mac)


def set_interface_down(iface, conn=False):
    logging.info("Setting interface %s down.", iface)
    if (conn):
        utils.run_cmd("sudo nmcli connection down {}".format(conn),
                      "Set connection {} down".format(conn))
    utils.run_cmd("sudo ip link set {} down".format(iface),
                  "Set interface {} link down".format(iface))


def set_interface_up(iface, conn=False):
    logging.info("Setting interface %s up.", iface)
    utils.run_cmd("sudo ip link set {} up".format(iface),
                  "Set interface {} link up".format(iface))
    if (conn):
        time.sleep(3)
        utils.run_cmd("sudo nmcli connection up {}".format(conn),
                      "Set connection {} up".format(conn))


def setup_network(wifi_conn):
    logging.info("Setting up network.")

    # Set all interface link up, just in case
    set_interface_up("eth0")
    set_interface_up("wlan0")

    # Check available eth and wlan connection in nmcli
    wifi_connected = False
    result = utils.run_cmd("sudo nmcli --terse connection show",
                           "Checking available connections")
    for line in result.splitlines():
        split = line.split(":")
        if (split[2] == "802-11-wireless" and wifi_conn):
            # Delete the connection if wifi_conn available from Firebase
            # and the current connection is not wifi_conn
            if (wifi_conn["ssid"] != split[0]):
                # Delete the possibly unused connection
                utils.run_cmd(("sudo nmcli connection "
                               "delete {}").format(split[0]),
                              "Deleting wlan connection {}".format(split[0]))
            else:
                # Otherwise the current connection is the correct one
                result = utils.run_cmd(
                    "sudo nmcli connection up {}".format(split[0]),
                    "Connecting wlan0 to SSID {}".format(split[0]))
                wifi_connected = (result.find("successfully") >= 0)
        elif (split[2] == "802-3-ethernet"):
            # If the connection is ethernet, try to connect
            utils.run_cmd("sudo nmcli connection up {}".format(split[0]),
                          "Connecting to ethernet {}".format(split[0]))

    # Try connect Wi-Fi using info from Firebase
    if (not wifi_connected and wifi_conn):
        result = utils.run_cmd(
            "sudo nmcli device wifi connect {} password {}".format(
                wifi_conn["ssid"], wifi_conn["pass"]),
            "Adding SSID {}".format(wifi_conn["ssid"]))
        wifi_connected = (result.find("successfully") >= 0)
        if (wifi_connected):
            # Put new connection down temporarily
            utils.run_cmd(("sudo nmcli connection "
                           "down {}").format(wifi_conn["ssid"]),
                          ("Setting connection {} "
                           "down temporarily").format(wifi_conn["ssid"]))
            # Ensure that the connection is active on wlan0
            utils.run_cmd(
                ("nmcli connection modify {} "
                 "connection.interface-name wlan0").format(
                    wifi_conn["ssid"]),
                "Setting connection {} to wlan0")
            # If BSSID is in connection info, add it
            if (wifi_conn["bssid"]):
                utils.run_cmd(
                    ("nmcli connection modify {} "
                     "802-11-wireless.bssid {}").format(
                        wifi_conn["ssid"], wifi_conn["bssid"]),
                    "Setting connection {} BSSID to {}".format(
                        wifi_conn["ssid"], wifi_conn["bssid"]))
            # Put new connection up
            utils.run_cmd(("sudo nmcli connection "
                           "up {}").format(wifi_conn["ssid"]),
                          "Setting connection {} up".format(wifi_conn["ssid"]))

    # Check all interfaces status
    result = utils.run_cmd("sudo nmcli --terse device status",
                           "Checking network interfaces status")
    eth_connection = False
    wifi_connection = False
    for line in result.splitlines():
        split = line.split(":")
        if (split[0] == "eth0"):
            eth_connection = split[3]
        elif (split[0] == "wlan0"):
            wifi_connection = split[3]
    logging.debug("eth0 connection: %s.", eth_connection)
    logging.debug("wlan0 connection: %s.", wifi_connection)

    return {"eth": eth_connection, "wifi": wifi_connection}


def run_iperf(test_uuid, server, port, direction, duration, dev, timeout_s):
    # Run iperf command
    iperf_cmd = ("iperf3 -c {} -p {} -t {} -P 8 -b 2000M -J").format(
        server, port, duration)
    if (direction == "dl"):
        iperf_cmd += " -R"
    result = utils.run_cmd(
        iperf_cmd,
        "Running iperf command",
        log_result=False,
        timeout_s=timeout_s)

    if (result):
        result_json = json.loads(result)
        result_json["start"]["interface"] = dev
        result_json["start"]["test_uuid"] = test_uuid

        # Log this data
        with open("logs/iperf-log/{}.json".format(
            datetime.now(timezone.utc).astimezone().isoformat()
        ), "w") as log_file:
            log_file.write(json.dumps(result_json))


def run_speedtest(test_uuid, timeout_s):
    # Run the speedtest command
    result = utils.run_cmd(
        "./speedtest --accept-license --format=json",
        "Running speedtest command",
        log_result=False,
        timeout_s=timeout_s)

    if (result):
        result_json = json.loads(result)
        result_json["test_uuid"] = test_uuid

        # Log this data
        with open("logs/speedtest-log/{}.json".format(
            datetime.now(timezone.utc).astimezone().isoformat()
        ), "w") as log_file:
            log_file.write(json.dumps(result_json))


def scan_wifi(extra):
    # Run Wi-Fi scan
    logging.info("Starting Wi-Fi scan.")
    results = wifi_scan.scan()
    timestamp = datetime.now(timezone.utc).astimezone().isoformat()

    # Log this data
    with open("logs/wifi-scan/{}.json".format(timestamp), "w") as log_file:
        log_file.write(
            json.dumps({
                "timestamp": timestamp,
                "extra": extra,
                "beacons": results}))


def main():
    while True:
        logging.info("Starting tests.")

        # Update config
        config = firebase.read_config()
        # Random UUID to correlate WiFi scans and tests
        config["test_uuid"] = str(uuid4())
        logging.info("Config: %s", config)
        # WiFi connection
        config["wifi_conn"] = firebase.get_wifi_conn(mac)

        # Ensure Ethernet and Wi-Fi are connected
        conn_status = setup_network(config["wifi_conn"])
        logging.info("Connection status: %s", conn_status)

        # Send heartbeat to indicate up status
        firebase.push_heartbeat(mac, config["test_uuid"])

        # Start tests over ethernet
        if (conn_status["eth"]):
            logging.info("Starting tests over eth0.")
            if (conn_status["wifi"]):
                set_interface_down("wlan0", conn_status["wifi"])

            # run_fmnc()        # Disabled while FMNC is down
            run_iperf(test_uuid=config["test_uuid"],
                      server=config["iperf_server"],
                      port=randint(config["iperf_minport"],
                                   config["iperf_maxport"]),
                      direction="dl", duration=config["iperf_duration"],
                      dev="eth0", timeout_s=config["timeout_s"])
            run_iperf(test_uuid=config["test_uuid"],
                      server=config["iperf_server"],
                      port=randint(config["iperf_minport"],
                                   config["iperf_maxport"]),
                      direction="ul", duration=config["iperf_duration"],
                      dev="eth0", timeout_s=config["timeout_s"])
            run_speedtest(test_uuid=config["test_uuid"],
                          timeout_s=config["timeout_s"])

            if (conn_status["wifi"]):
                set_interface_up("wlan0", conn_status["wifi"])

        # Start tests over Wi-Fi
        if (conn_status["wifi"]):
            logging.info("Starting tests over Wi-Fi.")
            if (conn_status["eth"]):
                set_interface_down("eth0", conn_status["eth"])

            # run_fmnc()        # Disabled while FMNC is down
            scan_wifi(extra={
                "test_uuid": config["test_uuid"],
                "corr_test": "iperf-dl"
            })
            run_iperf(test_uuid=config["test_uuid"],
                      server=config["iperf_server"],
                      port=randint(config["iperf_minport"],
                                   config["iperf_maxport"]),
                      direction="dl", duration=config["iperf_duration"],
                      dev="wlan0", timeout_s=config["timeout_s"])
            scan_wifi(extra={
                "test_uuid": config["test_uuid"],
                "corr_test": "iperf-ul"
            })
            run_iperf(test_uuid=config["test_uuid"],
                      server=config["iperf_server"],
                      port=randint(config["iperf_minport"],
                                   config["iperf_maxport"]),
                      direction="ul", duration=config["iperf_duration"],
                      dev="wlan0", timeout_s=config["timeout_s"])
            scan_wifi(extra={
                "test_uuid": config["test_uuid"],
                "corr_test": "speedtest"
            })
            run_speedtest(test_uuid=config["test_uuid"],
                          timeout_s=config["timeout_s"])

            if (conn_status["eth"]):
                set_interface_up("eth0", conn_status["eth"])
        else:
            scan_wifi(extra={
                "test_uuid": config["test_uuid"],
                "corr_test": "none"
            })

        # Upload
        # TODO: Might run on a different interval in the future.
        firebase.upload_directory_with_transfer_manager(
            source_dir=logdir,
            mac=mac)

        # Sleep for interval + random backoff
        interval = config["speedtest_interval"] * 60 + randint(0, 60)
        # Run heartbeat every minute if uptime is < 60 minutes
        while (time.clock_gettime(time.CLOCK_BOOTTIME) < 3600):
            logging.info("Sleeping for 60s")
            interval -= 60
            time.sleep(60)
            firebase.push_heartbeat(mac, test_uuid="startup")

        # Avoid ValueError
        if (interval > 0):
            logging.info("Sleeping for {}s, waking up at {}".format(
                interval,
                (datetime.now(timezone.utc).astimezone() + timedelta(
                    0, interval)).isoformat()))
            time.sleep(interval)


if __name__ == "__main__":
    main()
