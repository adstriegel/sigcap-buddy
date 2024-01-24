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


def read_config():
    logging.info("Reading config.json.")
    # TODO: implement querying config from Firebase
    with open("config.json", "r") as config_file:
        return json.load(config_file)


def push_heartbeat(mac, test_uuid):
    logging.info("Pushing heartbeat with test_uuid=%s.", test_uuid)
    heartbeat_ref = db.reference("heartbeat")
    heartbeat_ref.push().set({
        "mac": mac,
        "test_uuid": test_uuid,
        "last_timestamp": datetime.timestamp(datetime.now()) * 1000
    })


def get_wifi_conn(mac):
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
