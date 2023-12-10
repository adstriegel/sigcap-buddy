from datetime import datetime, timezone
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db
from firebase_admin import storage
from getpass import getuser
from google.cloud.storage import transfer_manager
import json
import logging
from pathlib import Path
from random import randint
import re
import subprocess
import time
from uuid import getnode as get_mac
import wifi_scan

# Setup
logging.basicConfig(
    filename="/home/{}/sigcap-buddy/speedtest_logger.log".format(getuser()),
    level=logging.DEBUG
)
mac = "-".join(("%012X" % get_mac())[i:i + 2] for i in range(0, 12, 2))
logdir = "/home/{}/sigcap-buddy/logs".format(getuser())
cred = credentials.Certificate(
    "/home/{}/sigcap-buddy/{}".format(
        getuser(), "nd-schmidt-firebase-adminsdk-d1gei-43db929d8a.json")
)
firebase_admin.initialize_app(cred, {
    "databaseURL": "https://nd-schmidt-default-rtdb.firebaseio.com",
    "storageBucket": "nd-schmidt.appspot.com"
})
re_nmcli_wifi = re.compile(r"wlan0 +wifi +disconnected")


def read_config():
    logging.debug("Reading config.json.")
    with open("config.json", "r") as config_file:
        return json.load(config_file)


def push_heartbeat():
    logging.debug("Pushing heartbeat.")
    heartbeat_ref = db.reference("heartbeat")
    heartbeat_ref.push().set({
        "mac": mac,
        "last_timestamp": datetime.timestamp(datetime.now()) * 1000
    })


def setup_wifi():
    check_wifi_cmd = ["sudo", "nmcli", "device", "status"]
    logging.debug("Checking Wi-Fi status: {}".format(" ".join(check_wifi_cmd)))
    result = subprocess.check_output(check_wifi_cmd).decode("utf-8")
    result = re_nmcli_wifi.findall(result)
    logging.debug("Is Wi-Fi disconnected? {}".format(
        (len(result) > 0)))

    if (len(result) > 0):
        # Wi-Fi disconnected, try to get connection info and authenticate
        wifi_conn = db.reference("wifi").child(mac.replace("-", ":")).get()
        result = False
        if (wifi_conn is not None):
            logging.debug("Got SSID: {}".format(wifi_conn["ssid"]))
            result = subprocess.check_output(
                ["sudo", "nmcli", "device", "wifi", "connect",
                 wifi_conn["ssid"], "password",
                 wifi_conn["pass"]]).decode("utf-8")
            result = (result.find("successfully") >= 0)
            logging.debug("Connect success? {}".format(result))
        return result
    else:
        return True


def run_iperf(server, port, direction, duration, dev):
    # Run iperf command
    iperf_cmd = ["iperf3", "-c", server, "-p", str(port), "-t", str(duration),
                 "-P", "8", "-b", "2000M", "-J", "--bind-dev", dev]
    if (direction == "dl"):
        iperf_cmd.append("-R")
    logging.debug("Start iperf: {}".format(" ".join(iperf_cmd)))
    result = subprocess.check_output(iperf_cmd).decode("utf-8")

    # Log this data
    with open("logs/iperf-log/{}.json".format(
        datetime.now(timezone.utc).astimezone().isoformat()
    ), "w") as log_file:
        log_file.write(json.dumps(result))


def run_speedtest(dev):
    # Run the speedtest command
    speedtest_cmd = ["./speedtest", "--accept-license", "--format=json",
                     "-I", dev]
    logging.debug("Start speedtest: {}".format(" ".join(speedtest_cmd)))
    result = subprocess.check_output(speedtest_cmd).decode("utf-8")

    # Log this data
    with open("logs/speedtest-log/{}.json".format(
        datetime.now(timezone.utc).astimezone().isoformat()
    ), "w") as log_file:
        log_file.write(json.dumps(result))


def scan_wifi():
    # Run Wi-Fi scan
    logging.debug("Starting Wi-Fi scan.")
    results = wifi_scan.scan()

    # Log this data
    with open("logs/wifi-scan/{}.json".format(
        datetime.now(timezone.utc).astimezone().isoformat()
    ), "w") as log_file:
        log_file.write(json.dumps(results))


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
            Path("{}/{}".format(source_dir, name)).unlink()


def main():
    while True:
        # Update config
        config = read_config()

        # Send heartbeat to indicate up status
        push_heartbeat()

        # Start tests over ethernet
        # run_fmnc()        # Disabled while FMNC is down
        run_iperf(server=config["iperf_server"],
                  port=randint(5201, config["iperf_maxport"]),
                  direction="dl", duration=config["iperf_duration"],
                  dev="eth0")
        run_iperf(server=config["iperf_server"],
                  port=randint(5201, config["iperf_maxport"]),
                  direction="ul", duration=config["iperf_duration"],
                  dev="eth0")
        run_speedtest(dev="eth0")

        # Start tests over Wi-Fi
        scan_wifi()
        # Ensure Wi-Fi is connected
        wifi_connected = setup_wifi()
        if wifi_connected:
            # run_fmnc()        # Disabled while FMNC is down
            run_iperf(server=config["iperf_server"],
                      port=randint(5201, config["iperf_maxport"]),
                      direction="dl", duration=config["iperf_duration"],
                      dev="wlan0")
            run_iperf(server=config["iperf_server"],
                      port=randint(5201, config["iperf_maxport"]),
                      direction="ul", duration=config["iperf_duration"],
                      dev="wlan0")
            run_speedtest(dev="wlan0")

        # Upload
        # TODO: Might run on a different interval in the future.
        upload_directory_with_transfer_manager(source_dir=logdir)

        # Sleep for interval + random backoff
        interval = config["speedtest_interval"] * 60 + randint(0, 60)
        # Run heartbeat every minute if uptime is < 60 minutes
        while (time.clock_gettime(time.CLOCK_BOOTTIME) < 360):
            logging.debug("Sleeping for 60s")
            interval -= 60
            time.sleep(60)
            push_heartbeat()

        logging.debug("Sleeping for {}s".format(interval))
        time.sleep(interval)


if __name__ == "__main__":
    main()
