from datetime import datetime, timezone
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
import re
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

# Regexes
re_nmcli_wifi = re.compile(r"wlan0 +wifi +disconnected")
re_nmcli_eth = re.compile(r"eth0 +ethernet +disconnected")


def read_config():
    logging.debug("Reading config.json.")
    with open("config.json", "r") as config_file:
        return json.load(config_file)


config = read_config()
# Random UUID to correlate WiFi scans and tests
config["test_uuid"] = str(uuid4())


def update_config():
    temp_config = read_config()
    for key in config:
        if (key == "test_uuid"):
            config[key] = str(uuid4())
        elif key in temp_config:
            config[key] = temp_config[key]


def push_heartbeat(test_uuid):
    logging.debug("Pushing heartbeat.")
    heartbeat_ref = db.reference("heartbeat")
    heartbeat_ref.push().set({
        "mac": mac,
        "test_uuid": test_uuid,
        "last_timestamp": datetime.timestamp(datetime.now()) * 1000
    })


def setup_network():
    check_nmcli_cmd = ["sudo", "nmcli", "device", "status"]
    logging.debug("Checking network device status: {}".format(
        " ".join(check_nmcli_cmd)))
    result = subprocess.check_output(check_nmcli_cmd).decode("utf-8")
    eth_connected = (len(re_nmcli_eth.findall(result)) == 0)
    wifi_connected = (len(re_nmcli_wifi.findall(result)) == 0)
    logging.debug("Ethernet connected: {}".format(eth_connected))
    logging.debug("Wi-Fi connected: {}".format(wifi_connected))

    if (eth_connected is False):
        # Try to connect eth
        try:
            eth_result = subprocess.check_output(
                ["sudo", "nmcli", "device", "up", "eth0"]).decode("utf-8")
            eth_connected = (eth_result.find("successfully") >= 0)
            logging.debug("Eth connect success? {}".format(eth_connected))
        except Exception as e:
            logging.warning("Cannot bring eth0 up: %s", e, exc_info=1)

    if (wifi_connected is False):
        # Wi-Fi disconnected, try to get connection info and authenticate
        wifi_ref = db.reference("wifi").order_by_child("mac").equal_to(
            mac.replace("-", ":")).get()
        if not wifi_ref:
            logging.warning("Cannot find wifi info for {}".format(mac))
        else:
            wifi_ref_key = list(wifi_ref.keys())[0]
            wifi_conn = wifi_ref[wifi_ref_key]
            logging.debug("Got SSID: {}".format(wifi_conn["ssid"]))
            try:
                wifi_result = subprocess.check_output(
                    ["sudo", "nmcli", "device", "wifi", "connect",
                     wifi_conn["ssid"], "password",
                     wifi_conn["pass"]]).decode("utf-8")
                wifi_connected = (wifi_result.find("successfully") >= 0)
                logging.debug("Wi-Fi connect success? {}".format(
                    wifi_connected))
            except Exception as e:
                logging.warning("Cannot connect wlan0: %s", e, exc_info=1)

    return {"eth": eth_connected, "wifi": wifi_connected}


def run_iperf(test_uuid, server, port, direction, duration, dev, timeout_s):
    # Run iperf command
    iperf_cmd = ["iperf3", "-c", server, "-p", str(port), "-t", str(duration),
                 "-P", "8", "-b", "2000M", "-J"]
    if (direction == "dl"):
        iperf_cmd.append("-R")
    logging.debug("Start iperf: {}".format(" ".join(iperf_cmd)))

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
    logging.debug("Start speedtest: {}".format(" ".join(speedtest_cmd)))

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
    logging.debug("Starting Wi-Fi scan.")
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
    logging.debug("Uploading files.")

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

    logging.debug("Found {} files.".format(len(string_paths)))

    # Start the upload.
    results = transfer_manager.upload_many_from_filenames(
        bucket, string_paths, source_directory=source_dir,
        max_workers=workers, blob_name_prefix="{}/".format(mac)
    )

    for name, result in zip(string_paths, results):
        # The results list is either `None` or an exception for each filename
        # in the input list, in order.

        if isinstance(result, Exception):
            logging.warning("Failed to upload {} due to exception: {}".format(
                name, result))
        else:
            logging.debug("Uploaded {} to {}.".format(name, bucket.name))
            if not (name.startswith("speedtest_logger.log")):
                Path("{}/{}".format(source_dir, name)).unlink()


def set_interface(iface, state):
    try:
        logging.debug(subprocess.check_output(
            ["sudo", "nmcli", "device", state,
             iface]).decode("utf-8"))
    except Exception as e:
        logging.warning(
            "Error while setting interface %s %s: %s",
            iface, state, e, exc_info=1)


def main():
    while True:
        # Update config
        update_config()

        # Send heartbeat to indicate up status
        push_heartbeat(test_uuid=config["test_uuid"])
        # Ensure Ethernet and Wi-Fi are connected
        conn_status = setup_network()

        # Start tests over ethernet
        if (conn_status["eth"]):
            logging.debug("Starting tests over ethernet")
            if (conn_status["wifi"]):
                set_interface("wlan0", "down")

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
                set_interface("wlan0", "up")

        # Start tests over Wi-Fi
        if (conn_status["wifi"]):
            logging.debug("Starting tests over Wi-Fi")
            if (conn_status["eth"]):
                set_interface("eth0", "down")

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
                set_interface("eth0", "up")
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
            logging.debug("Sleeping for 60s")
            interval -= 60
            time.sleep(60)
            push_heartbeat(test_uuid="startup")

        # Avoid ValueError
        if (interval > 0):
            logging.debug("Sleeping for {}s".format(interval))
            time.sleep(interval)


if __name__ == "__main__":
    main()
