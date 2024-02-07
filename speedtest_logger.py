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
        utils.run_cmd("sudo nmcli connection down \"{}\"".format(conn),
                      "Set connection {} down".format(conn))
    utils.run_cmd("sudo ip link set {} down".format(iface),
                  "Set interface {} link down".format(iface))


def set_interface_up(iface, conn=False):
    logging.info("Setting interface %s up.", iface)
    utils.run_cmd("sudo ip link set {} up".format(iface),
                  "Set interface {} link up".format(iface))
    if (conn):
        retry_count = 0
        retry_max = 10
        while retry_count < retry_max:
            output = utils.run_cmd("sudo nmcli connection up \"{}\"".format(conn),
                                   "Set connection {} up".format(conn))
            if (output.find("successfully") >= 0):
                retry_count += retry_max
            else:
                retry_count += 1
                time.sleep(1)
                logging.debug("Error setting conn up, retry count: %s",
                              retry_count)


def enable_monitor(iface):
    logging.info("Enabling interface %s as monitor.", iface)
    is_monitor = "monitor" in (
        utils.run_cmd("sudo iw dev {} info".format(iface),
                      "Checking iface {} info".format(iface)))
    logging.info("{} is monitor? {}".format(iface, is_monitor))
    if (not is_monitor):
        set_interface_down(iface)
        utils.run_cmd("sudo iw dev {} set type monitor".format(iface),
                      "Set interface {} as monitor".format(iface))
    set_interface_up(iface)


def disable_monitor(iface):
    logging.info("Disabling interface %s as monitor.", iface)
    is_monitor = "monitor" in (
        utils.run_cmd("sudo iw dev {} info".format(iface),
                      "Checking iface {} info".format(iface)))
    logging.info("{} is monitor? {}".format(iface, is_monitor))
    if (is_monitor):
        set_interface_down(iface)
        utils.run_cmd("sudo iw dev {} set type managed".format(iface),
                      "Set interface {} as managed".format(iface))
    set_interface_up(iface)


def setup_network(wifi_conn, wireless_iface, monitor_iface):
    logging.info("Setting up network.")

    # Set all interface link up, just in case
    set_interface_up("eth0")
    set_interface_up(wireless_iface)
    disable_monitor(wireless_iface)
    if (monitor_iface and wireless_iface != monitor_iface):
        enable_monitor(monitor_iface)

    # Check available eth and wlan connection in nmcli
    conn_found = False
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
                               "delete \"{}\"").format(split[0]),
                              "Deleting wlan connection {}".format(split[0]))
            else:
                # Otherwise the connection is found
                conn_found = True
        elif (split[2] == "802-3-ethernet"):
            # If the connection is ethernet, try to connect
            utils.run_cmd("sudo nmcli connection up \"{}\"".format(split[0]),
                          "Connecting to ethernet {}".format(split[0]))

    # Try connect Wi-Fi using info from Firebase
    if (not conn_found and wifi_conn):
        result = utils.run_cmd(
            "sudo nmcli device wifi connect {} password {}".format(
                wifi_conn["ssid"], wifi_conn["pass"]),
            "Adding SSID {}".format(wifi_conn["ssid"]))
        conn_found = (result.find("successfully") >= 0)

    if (conn_found):
        # Check if connection need editing.
        conn_iface = utils.run_cmd(
            ("sudo nmcli --fields connection.interface-name connection "
             "show \"{}\"").format(wifi_conn["ssid"]),
            "Check connection {} interface".format(wifi_conn["ssid"]))
        edit_iface = wireless_iface not in conn_iface
        logging.debug("Edit connection %s interface? %s",
                      wifi_conn["ssid"], edit_iface)
        edit_bssid = False
        if ("bssid" in wifi_conn and wifi_conn["bssid"]):
            conn_iface = utils.run_cmd(
                ("sudo nmcli --fields 802-11-wireless.bssid connection "
                 "show \"{}\"").format(wifi_conn["ssid"]),
                "Check connection {} interface".format(wifi_conn["ssid"]))
            edit_bssid = wifi_conn["bssid"] not in conn_iface
            logging.debug("Edit connection %s BSSID? %s",
                          wifi_conn["ssid"], edit_bssid)

        if (edit_bssid or edit_iface):
            # Put new connection down temporarily for editing
            utils.run_cmd(("sudo nmcli connection "
                           "down \"{}\"").format(wifi_conn["ssid"]),
                          ("Setting connection {} "
                           "down temporarily").format(wifi_conn["ssid"]))
            # Ensure that the connection is active on selected iface
            if (edit_iface):
                utils.run_cmd(
                    ("sudo nmcli connection modify \"{}\" "
                     "connection.interface-name {}").format(
                        wifi_conn["ssid"], wireless_iface),
                    "Setting connection {} to {}".format(
                        wifi_conn["ssid"], wireless_iface))
            # If BSSID is in connection info, add it
            if (edit_bssid):
                utils.run_cmd(
                    ("sudo nmcli connection modify \"{}\" "
                     "802-11-wireless.bssid {}").format(
                        wifi_conn["ssid"], wifi_conn["bssid"]),
                    "Setting connection {} BSSID to {}".format(
                        wifi_conn["ssid"], wifi_conn["bssid"]))

        # Activate connection, should run whether the connection is up or down
        utils.run_cmd(("sudo nmcli connection "
                       "up \"{}\"").format(wifi_conn["ssid"]),
                      ("Setting connection {} "
                       "up").format(wifi_conn["ssid"]))

    # Check all interfaces status
    result = utils.run_cmd("sudo nmcli --terse device status",
                           "Checking network interfaces status")
    eth_connection = False
    wifi_connection = False
    for line in result.splitlines():
        split = line.split(":")
        if (split[0] == "eth0"):
            eth_connection = split[3]
        elif (split[0] == wireless_iface):
            wifi_connection = split[3]
    logging.debug("eth0 connection: %s.", eth_connection)
    logging.debug("%s connection: %s.", wireless_iface, wifi_connection)

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


def scan_wifi(iface, extra):
    # Run Wi-Fi scan
    logging.info("Starting Wi-Fi scan.")
    results = wifi_scan.scan(iface)
    timestamp = datetime.now(timezone.utc).astimezone().isoformat()

    # Log this data
    with open("logs/wifi-scan/{}.json".format(timestamp), "w") as log_file:
        log_file.write(
            json.dumps({
                "timestamp": timestamp,
                "interface": iface,
                "extra": extra,
                "beacons": results}))


def scan_wifi_async(iface, link_wait=1):
    # Run Wi-Fi scan
    logging.info("Starting Wi-Fi scan.")
    return {
        "proc_obj": wifi_scan.scan_async(iface, link_wait),
        "proc_link": wifi_scan.link_async(iface),
        "timestamp": datetime.now(timezone.utc).astimezone().isoformat(),
        "iface": iface
    }


def resolve_scan_wifi_async(resolve_obj, extra):
    logging.info("Resolving Wi-Fi scan.")
    results = wifi_scan.resolve_scan_async(resolve_obj["proc_obj"])
    results_link = wifi_scan.resolve_link_async(resolve_obj["proc_link"])

    # Log this data
    with open("logs/wifi-scan/{}.json".format(
              resolve_obj["timestamp"]), "w") as log_file:
        log_file.write(
            json.dumps({
                "timestamp": resolve_obj["timestamp"],
                "interface": resolve_obj["iface"],
                "extra": extra,
                "beacons": results,
                "links": results_link}))


def main():
    logging.info("Upload previously recorded logs on startup.")
    firebase.upload_directory_with_transfer_manager(
        source_dir=logdir,
        mac=mac)

    while True:
        logging.info("Starting tests.")

        # Update config
        config = firebase.read_config(mac)
        # Random UUID to correlate WiFi scans and tests
        config["test_uuid"] = str(uuid4())
        logging.info("Config: %s", config)
        # WiFi connection
        config["wifi_conn"] = firebase.get_wifi_conn(mac)

        # Ensure Ethernet and Wi-Fi are connected
        conn_status = setup_network(
            config["wifi_conn"],
            config["wireless_interface"],
            config["monitor_interface"])
        logging.info("Connection status: %s", conn_status)

        # Send heartbeat to indicate up status
        firebase.push_heartbeat(mac)

        # Start tests over ethernet
        if (conn_status["eth"]):
            logging.info("Starting tests over eth0.")
            if (conn_status["wifi"]):
                set_interface_down(config["wireless_interface"],
                                   conn_status["wifi"])

            # Disabled while FMNC is down
            # run_fmnc()

            # iperf downlink
            run_iperf(test_uuid=config["test_uuid"],
                      server=config["iperf_server"],
                      port=randint(config["iperf_minport"],
                                   config["iperf_maxport"]),
                      direction="dl", duration=config["iperf_duration"],
                      dev="eth0", timeout_s=config["timeout_s"])

            # iperf uplink
            run_iperf(test_uuid=config["test_uuid"],
                      server=config["iperf_server"],
                      port=randint(config["iperf_minport"],
                                   config["iperf_maxport"]),
                      direction="ul", duration=config["iperf_duration"],
                      dev="eth0", timeout_s=config["timeout_s"])

            # Ookla Speedtest
            run_speedtest(test_uuid=config["test_uuid"],
                          timeout_s=config["timeout_s"])

            if (conn_status["wifi"]):
                set_interface_up(config["wireless_interface"],
                                 conn_status["wifi"])

        # Start tests over Wi-Fi
        if (conn_status["wifi"]):
            logging.info("Starting tests over Wi-Fi.")
            if (conn_status["eth"]):
                set_interface_down("eth0", conn_status["eth"])

            # Disabled while FMNC is down
            # run_fmnc()

            # iperf downlink
            resolve_obj = scan_wifi_async(config["wireless_interface"])
            run_iperf(test_uuid=config["test_uuid"],
                      server=config["iperf_server"],
                      port=randint(config["iperf_minport"],
                                   config["iperf_maxport"]),
                      direction="dl", duration=config["iperf_duration"],
                      dev=config["wireless_interface"],
                      timeout_s=config["timeout_s"])
            resolve_scan_wifi_async(
                resolve_obj,
                extra={
                    "test_uuid": config["test_uuid"],
                    "corr_test": "iperf-dl"})

            # iperf uplink
            resolve_obj = scan_wifi_async(config["wireless_interface"])
            run_iperf(test_uuid=config["test_uuid"],
                      server=config["iperf_server"],
                      port=randint(config["iperf_minport"],
                                   config["iperf_maxport"]),
                      direction="ul", duration=config["iperf_duration"],
                      dev=config["wireless_interface"],
                      timeout_s=config["timeout_s"])
            resolve_scan_wifi_async(
                resolve_obj,
                extra={
                    "test_uuid": config["test_uuid"],
                    "corr_test": "iperf-ul"})

            # Ookla Speedtest
            resolve_obj = scan_wifi_async(config["wireless_interface"])
            run_speedtest(test_uuid=config["test_uuid"],
                          timeout_s=config["timeout_s"])
            resolve_scan_wifi_async(
                resolve_obj,
                extra={
                    "test_uuid": config["test_uuid"],
                    "corr_test": "speedtest"})

            if (conn_status["eth"]):
                set_interface_up("eth0", conn_status["eth"])
        else:
            scan_wifi(
                config["wireless_interface"],
                extra={
                    "test_uuid": config["test_uuid"],
                    "corr_test": "none"})

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
            firebase.push_heartbeat(mac)

        # Avoid ValueError
        if (interval > 0):
            logging.info("Sleeping for {}s, waking up at {}".format(
                interval,
                (datetime.now(timezone.utc).astimezone() + timedelta(
                    0, interval)).isoformat()))
            time.sleep(interval)


if __name__ == "__main__":
    main()
