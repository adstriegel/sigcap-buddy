from argparse import ArgumentParser
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db
from getpass import getpass
from uuid import getnode as get_mac

cred = credentials.Certificate(
    "nd-schmidt-firebase-adminsdk-d1gei-43db929d8a.json")
firebase_admin.initialize_app(cred, {
    "databaseURL": "https://nd-schmidt-default-rtdb.firebaseio.com"
})


def main():
    def_mac = ":".join(("%012X" % get_mac())[i:i + 2] for i in range(0, 12, 2))
    parser = ArgumentParser(prog="store_wifi.py",
                            description="Store Wi-Fi info to Firebase DB")
    parser.add_argument("--mac", type=str, help="Input MAC")
    parser.add_argument("--ssid", type=str, help="Input SSID")
    args = parser.parse_args()

    mac = args.mac
    if (mac is None):
        mac = input("Input MAC [{}]: ".format(def_mac))
        if (mac == ""):
            mac = def_mac

    ssid = args.ssid
    if (ssid is None):
        ssid = input("Input SSID: ")

    passwd = getpass()

    db.reference("wifi").push().set({"mac": mac, "ssid": ssid, "pass": passwd})
    print("MAC {} SSID {} successfully added!".format(mac, ssid))


if __name__ == "__main__":
    main()
