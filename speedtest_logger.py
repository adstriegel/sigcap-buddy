from datetime import datetime, timedelta, timezone
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db
from firebase_admin import storage
from getpass import getuser
from google.cloud.storage import transfer_manager
import json
import logging
from logging.handlers import TimedRotatingFileHandler
from logging import Formatter
from pathlib import Path
from random import randint
import shlex
import subprocess
import time
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

# Firebase setup
cred = credentials.Certificate(
    "/home/{}/sigcap-buddy/{}".format(
        getuser(), "nd-schmidt-firebase-adminsdk-d1gei-43db929d8a.json")
)
firebase_admin.initialize_app(cred, {
    "databaseURL": "https://nd-schmidt-default-rtdb.firebaseio.com",
    "storageBucket": "nd-schmidt.appspot.com"
})


def read_config():
    logging.info("Reading config.json.")
    with open("config.json", "r") as config_file:
        return json.load(config_file)


def push_heartbeat(test_uuid):
    logging.info("Pushing heartbeat with test_uuid=%s.", test_uuid)
    heartbeat_ref = db.reference("heartbeat")
    heartbeat_ref.push().set({
        "mac": mac,
        "test_uuid": test_uuid,
        "last_timestamp": datetime.timestamp(datetime.now()) * 1000
    })


def get_wifi_conn():
    logging.info("Getting Wi-Fi connection from Firebase.")
    wifi_ref = db.reference("wifi").order_by_child("mac").equal_to(
        mac.replace("-", ":")).get()
    if not wifi_ref:
        logging.warning("Cannot find Wi-Fi info for %s", mac)
        return False
    else:
        wifi_ref_key = list(wifi_ref.keys())[0]
        logging.info("Got SSID: %s", wifi_ref[wifi_ref_key]["ssid"])
        return wifi_ref[wifi_ref_key]


def run_cmd(cmd, logging_prefix="Running command"):
    logging.info("%s: %s.", logging_prefix, cmd)
    args = shlex.split(cmd)
    try:
        result = subprocess.check_output(args).decode("utf-8")
        logging.debug(result)
        return result
    except subprocess.CalledProcessError as e:
        logging.warning("%s error: %s\n%s", logging_prefix, e,
                        e.output, exc_info=1)
        return ""


def set_interface_down(iface, conn=False):
    logging.debug("Setting interface %s down.", iface)
    if (conn):
        run_cmd("sudo nmcli connection down {}".format(conn),
                "Set connection {} down".format(conn))
    run_cmd("sudo ip link set {} down".format(iface),
            "Set interface {} link down".format(iface))


def set_interface_up(iface, conn=False):
    logging.debug("Setting interface %s up.", iface)
    run_cmd("sudo ip link set {} up".format(iface),
            "Set interface {} link up".format(iface))
    if (conn):
        time.sleep(3)
        run_cmd("sudo nmcli connection up {}".format(conn),
                "Set connection {} up".format(conn))


def setup_network(wifi_conn):
    logging.info("Setting up network.")
    # Set all interface link up, just in case
    set_interface_up("eth0")
    set_interface_up("wlan0")

    # Check available eth and wlan connection in nmcli
    wifi_connected = False
    result = run_cmd("sudo nmcli --terse connection show",
                     "Checking available connections")
    for line in result.splitlines():
        split = line.split(":")
        if (split[2] == "802-11-wireless" and wifi_conn):
            # Delete the connection if wifi_conn available from Firebase
            # and the current connection is not wifi_conn
            if (wifi_conn["ssid"] != split[0]):
                # Delete the possibly unused connection
                run_cmd("sudo nmcli connection delete {}".format(split[0]),
                        "Deleting wlan connection {}".format(split[0]))
            else:
                # Otherwise the current connection is the correct one
                result = run_cmd(
                    "sudo nmcli connection up {}".format(split[0]),
                    "Connecting wlan0 to SSID {}".format(split[0]))
                wifi_connected = (result.find("successfully") >= 0)
        elif (split[2] == "802-3-ethernet"):
            # If the connection is ethernet, try to connect
            run_cmd("sudo nmcli connection up {}".format(split[0]),
                    "Connecting to ethernet {}".format(split[0]))

    # Try connect Wi-Fi using info from Firebase
    if (not wifi_connected and wifi_conn):
        result = run_cmd(
            "sudo nmcli device wifi connect {} password {}".format(
                wifi_conn["ssid"], wifi_conn["pass"]),
            "Adding SSID {}".format(wifi_conn["ssid"]))
        wifi_connected = (result.find("successfully") >= 0)
        if (wifi_connected):
            # Put new connection down temporarily
            run_cmd("sudo nmcli connection down {}".format(wifi_conn["ssid"]),
                    "Setting connection {} down temp".format(
                        wifi_conn["ssid"]))
            # Ensure that the connection is active on wlan0
            run_cmd(
                ("nmcli connection modify {} "
                 "connection.interface-name wlan0").format(
                    wifi_conn["ssid"]),
                "Setting connection {} to wlan0")
            # If BSSID is in connection info, add it
            if (wifi_conn["bssid"]):
                run_cmd(
                    ("nmcli connection modify {} "
                     "802-11-wireless.bssid {}").format(
                        wifi_conn["ssid"], wifi_conn["bssid"]),
                    "Setting connection {} BSSID to {}".format(
                        wifi_conn["ssid"], wifi_conn["bssid"]))
            # Put new connection up
            run_cmd("sudo nmcli connection up {}".format(wifi_conn["ssid"]),
                    "Setting connection {} up".format(wifi_conn["ssid"]))

    # Check all interfaces status
    result = run_cmd("sudo nmcli --terse device status",
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
    iperf_cmd = ["iperf3", "-c", server, "-p", str(port), "-t", str(duration),
                 "-P", "8", "-b", "2000M", "-J"]
    if (direction == "dl"):
        iperf_cmd.append("-R")
    logging.info("Start iperf: %s", " ".join(iperf_cmd))

    try:
        result = subprocess.check_output(
            iperf_cmd,
            timeout=timeout_s).decode("utf-8")
        result_json = json.loads(result)
        result_json["start"]["interface"] = dev
        result_json["start"]["test_uuid"] = test_uuid

        # Log this data
        with open("logs/iperf-log/{}.json".format(
            datetime.now(timezone.utc).astimezone().isoformat()
        ), "w") as log_file:
            log_file.write(json.dumps(result_json))
    except Exception as e:
        logging.warning("Error while running iperf: %s", e, exc_info=1)


def run_speedtest(test_uuid, timeout_s):
    # Run the speedtest command
    speedtest_cmd = ["./speedtest", "--accept-license", "--format=json"]
    logging.info("Start speedtest: %s", " ".join(speedtest_cmd))

    try:
        result = subprocess.check_output(
            speedtest_cmd,
            timeout=timeout_s).decode("utf-8")
        result_json = json.loads(result)
        result_json["test_uuid"] = test_uuid

        # Log this data
        with open("logs/speedtest-log/{}.json".format(
            datetime.now(timezone.utc).astimezone().isoformat()
        ), "w") as log_file:
            log_file.write(json.dumps(result_json))
    except Exception as e:
        logging.warning("Error while running speedtest: %s", e, exc_info=1)


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


def upload_directory_with_transfer_manager(
    source_dir,
    workers=8
):
    """Upload every file in a directory, including all files in subdirectories.

    Each blob name is derived from the filename, not including the `directory`
    parameter itself. For complete control of the blob name for each file (and
    other aspects of individual blob metadata), use
    transfer_manager.upload_many() instead.
    """
    logging.info("Uploading files.")

    # The directory on your computer to upload. Files in the directory and its
    # subdirectories will be uploaded. An empty string means "the current
    # working directory".
    # source_dir=

    # The maximum number of processes to use for the operation. The performance
    # impact of this value depends on the use case, but smaller files usually
    # benefit from a higher number of processes. Each additional process
    # occupies some CPU and memory resources until finished. Threads can be
    # used instead of processes by passing `worker_type=transfer_manager.
    # THREAD`.
    # workers=8

    bucket = storage.bucket()

    # Generate a list of paths (in string form) relative to the `directory`.
    # This can be done in a single list comprehension, but is expanded into
    # multiple lines here for clarity.

    # First, recursively get all files in `directory` as Path objects.
    directory_as_path_obj = Path(source_dir)
    paths = directory_as_path_obj.rglob("*")

    # Filter so the list only includes files, not directories themselves.
    file_paths = [path for path in paths if path.is_file()]

    # These paths are relative to the current working directory. Next, make
    # them relative to `directory`
    relative_paths = [path.relative_to(source_dir) for path in file_paths]

    # Finally, convert them all to strings.
    string_paths = [str(path) for path in relative_paths]

    logging.info("Found %d files.", len(string_paths))

    # Start the upload.
    results = transfer_manager.upload_many_from_filenames(
        bucket, string_paths, source_directory=source_dir,
        max_workers=workers, blob_name_prefix="{}/".format(mac)
    )

    for name, result in zip(string_paths, results):
        # The results list is either `None` or an exception for each filename
        # in the input list, in order.

        if isinstance(result, Exception):
            logging.warning("Failed to upload %s due to exception: %s.",
                            name, result)
        else:
            logging.info("Uploaded %s.", name)
            if not (name.startswith("speedtest_logger.log")):
                local_copy = Path("{}/{}".format(source_dir, name))
                local_copy.unlink()
                logging.info("Deleted local copy: %s.", local_copy)


def main():
    while True:
        logging.info("Starting tests.")

        # Update config
        config = read_config()
        # Random UUID to correlate WiFi scans and tests
        config["test_uuid"] = str(uuid4())
        logging.info("Config: %s", config)
        # WiFi connection
        config["wifi_conn"] = get_wifi_conn()

        # Ensure Ethernet and Wi-Fi are connected
        conn_status = setup_network(config["wifi_conn"])
        logging.info("Connection status: %s", conn_status)

        # Send heartbeat to indicate up status
        push_heartbeat(test_uuid=config["test_uuid"])

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
        upload_directory_with_transfer_manager(source_dir=logdir)

        # Sleep for interval + random backoff
        interval = config["speedtest_interval"] * 60 + randint(0, 60)
        # Run heartbeat every minute if uptime is < 60 minutes
        while (time.clock_gettime(time.CLOCK_BOOTTIME) < 3600):
            logging.info("Sleeping for 60s")
            interval -= 60
            time.sleep(60)
            push_heartbeat(test_uuid="startup")

        # Avoid ValueError
        if (interval > 0):
            logging.info("Sleeping for {}s, waking up at {}".format(
                interval,
                (datetime.now(timezone.utc).astimezone() + timedelta(
                    0, interval)).isoformat()))
            time.sleep(interval)


if __name__ == "__main__":
    main()
