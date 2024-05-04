from datetime import datetime
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db
from firebase_admin import storage
from getpass import getuser
from google.cloud.storage import transfer_manager
import json
import logging
from pathlib import Path

# Firebase setup
cred = credentials.Certificate(
    "/home/{}/sigcap-buddy/{}".format(
        getuser(), "nd-schmidt-firebase-adminsdk-d1gei-43db929d8a.json")
)
firebase_admin.initialize_app(cred, {
    "databaseURL": "https://nd-schmidt-default-rtdb.firebaseio.com",
    "storageBucket": "nd-schmidt.appspot.com"
})


def read_config(mac):
    logging.info("Reading config.json.")
    config = dict()
    with open("config.json", "r") as config_file:
        config = json.load(config_file)

    try:
        query = db.reference("config").order_by_child(
            "mac").equal_to(mac.replace("-", ":")).get()
        values = list(query.values())
        if (len(values) > 0):
            val = values[0]
            for key in val:
                if (key != "mac" and val[key]):
                    config[key] = val[key]
    except Exception as e:
        logging.error("Cannot connect db config: %s", e, exc_info=1)

    return config


def push_heartbeat(mac):
    hb_append_ref = db.reference("hb_append").child(mac)
    timestamp = datetime.timestamp(datetime.now()) * 1000
    logging.info("Pushing heartbeat with timestamp %f", timestamp)

    try:
        found = hb_append_ref.order_by_child(
            "last_timestamp").limit_to_last(1).get()
        updated = False

        if (found and len(found) > 0):
            key = list(found.keys())[0]
            last_timestamp = found[key]["last_timestamp"]
            span = (timestamp - last_timestamp)
            if (span < 5400000):  # 90 minutes
                logging.debug(("Updating key %s mac %s last_timestamp from "
                               "%f to %f (span %.3f hour)"),
                              key, mac, found[key]['last_timestamp'],
                              timestamp, span / 3600000)
                ref = hb_append_ref.child(key)
                ref.update({
                    "last_timestamp": timestamp
                })
                updated = True

        if (not updated):
            entry = {
                "start_timestamp": timestamp,
                "last_timestamp": timestamp
            }
            print("new entry:", entry)
            hb_append_ref.push().set(entry)
    except Exception as e:
        logging.error("Cannot connect db hb_append: %s", e, exc_info=1)


def get_wifi_conn(mac):
    logging.info("Getting Wi-Fi connection from Firebase.")
    wifi_ref = None
    try:
        wifi_ref = db.reference("wifi").order_by_child("mac").equal_to(
            mac.replace("-", ":")).get()
    except Exception as e:
        logging.error("Cannot connect db wifi: %s", e, exc_info=1)

    if not wifi_ref:
        logging.warning("Cannot find Wi-Fi info for %s", mac)
        return False
    else:
        wifi_ref_key = list(wifi_ref.keys())[0]
        logging.info("Got SSID: %s", wifi_ref[wifi_ref_key]["ssid"])
        return wifi_ref[wifi_ref_key]


def get_mqtt_conn():
    logging.info("Getting MQTT connection from Firebase.")

    auth_path = Path(".mqtt-config.json")
    if auth_path.is_file():
        logging.info("MQTT connection is already stored.")
        return True

    mqtt_ref = None
    try:
        mqtt_ref = db.reference("mqtt_temp").get()
    except Exception as e:
        logging.error("Cannot connect db wifi: %s", e, exc_info=1)

    if not mqtt_ref:
        logging.warning("Cannot find MQTT info.")
        return False
    else:
        logging.info("Writing MQTT connection to %s.", auth_path)
        with open(auth_path, "w") as file:
            json.dump(mqtt_ref, file)
        return True


def upload_directory_with_transfer_manager(
    source_dir,
    mac,
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
            if name != "speedtest_logger.log":
                local_copy = Path("{}/{}".format(source_dir, name))
                local_copy.unlink()
                logging.info("Deleted local copy: %s.", local_copy)
