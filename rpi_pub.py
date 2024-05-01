from datetime import datetime, timezone
import firebase
from getpass import getuser
import jc
import json
import logging
from logging import Formatter
from logging.handlers import TimedRotatingFileHandler
from paho.mqtt import client as mqtt
from pathlib import Path
import re
import time
import utils


logdir = "/home/{}/sigcap-buddy/logs".format(getuser())

# Logging setup
handler = TimedRotatingFileHandler(
    filename="{}/rpi_pub.log".format(logdir),
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


# Update config
config = firebase.read_config(mac)
logging.info("Config: %s", config)


# Publish topics
topic_report = f"Schmidt/{mac}/report/status"
# topic_report_ip = f"Schmidt/{mac}/report/status/ip"
# topic_report_mac = f"Schmidt/{mac}/report/status/mac"
topic_report_conf = f"Schmidt/{mac}/report/config"
# Subscribed topics
topic_config_all = f"Schmidt/all/config/#"
topic_config_specific = f"Schmidt/{mac}/config/#"


def create_msg(msg_type, out, err=""):
    return {
        "mac": mac,
        "timestamp": datetime.now(timezone.utc).astimezone().isoformat(),
        "type": msg_type,
        "result": "failed" if err else "success",
        "out": out,
        "err": err,
    }


def get_ssid():
    output = utils.run_cmd("iwconfig")

    # Process output to extract SSID using regular expression
    pattern = r'ESSID:"([^"]*)"'
    match = re.search(pattern, output)
    if match:
        essid = match.group(1)
        ssid = f'{essid}'
    else:
        ssid = 'NONE'
    return ssid


def get_ifaces(specific=None):
    parsed = jc.parse("ifconfig", utils.run_cmd("ifconfig"))
    # Remove loopback
    parsed = [item for item in parsed if item["name"] != "lo"]
    # Remove unneeded parameters
    match specific:
        case "up":
            parsed = {item["name"]: "UP" in item["state"] for item in parsed}
        case "ip":
            parsed = {item["name"]: item["ipv4_addr"] for item in parsed}
        case "mac":
            parsed = {item["name"]: item["mac_addr"] for item in parsed}
        case _:
            parsed = list(map(lambda x: {
                "name": x["name"],
                "up": "UP" in x["state"],
                "ip_address": x["ipv4_addr"],
                "mac_address": x["mac_addr"]
            }, parsed))

    return parsed


def create_status(command, specific=None):
    match specific:
        case "ssid":
            out = get_ssid()
        case "iface":
            out = get_ifaces()
        case "up":
            out = get_ifaces("up")
        case "ip":
            out = get_ifaces("ip")
        case "mac":
            out = get_ifaces("mac")
        case _:
            out = {
                "ssid": get_ssid(),
                "ifaces": get_ifaces()
            }

    msg_type = "status"
    if specific:
        msg_type += f"/{specific}"

    return create_msg(msg_type, out)


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logging.info("Connected to MQTT broker")
        # Subscribe to "Schmidt/config" for commands
        client.subscribe(topic_config_all)
        client.subscribe(topic_config_specific)
    else:
        logging.error(f"Connection failed with code {rc}")


def on_message(client, userdata, msg):
    # We only receive message from "Schmidt/config" topic
    topic = msg.topic
    logging.info("Message received: %s", topic)
    splits = topic.split("/")
    [_, target, _, command] = splits[:4]
    extras = splits[4:]

    # Skip if the command is not intended for this mac
    if target != "all" and target != mac:
        logging.info("Skipping command intended for %s.", target)
        return

    match command:
        case "ping":
            # Ping the Pi
            logging.info("Got ping command")
            msg = create_msg("ping", msg.payload.decode("utf-8"))
            logging.info("Sending reply: %s", msg)
            client.publish(topic_report_conf, json.dumps(msg), qos=1)

        case "update":
            # Run the update script
            logging.info("Got update command")
            # TODO this message is sent later with the update results
            # msg = create_msg("update", "starting update...")
            # client.publish(topic_report_conf, json.dumps(msg), qos=1)
            # TODO if the update script restarts this script, it will stop here
            output = utils.run_cmd(
                ("wget -q -O - https://raw.githubusercontent.com/adstriegel/"
                 "sigcap-buddy/main/pi-setup.sh | /bin/bash"),
                raw_out=True)
            logging.debug(output)
            msg = create_msg("update", {"returncode": output["returncode"]},
                             ("" if output["returncode"] == 0
                              else output["stderr"]))
            logging.info("Sending reply: %s", msg)
            client.publish(topic_report_conf, json.dumps(msg), qos=1)

        case "status":
            # TODO query status
            # Extra options: "/(ssid|iface|up|ip|mac)"
            pass

        case "logs":
            # TODO send program logs and error logs
            # Extra options: "/(mqtt|speedtest)/n"
            # n: read last n lines, default 20
            pass

        case "restart-srv":
            # TODO restart services
            # Extra options: "/(mqtt|speedtest)"
            pass

        case "reboot":
            # TODO reboot Pi
            pass

        case _:
            logging.warning("Unknown command: %s", command)


def publish_msg(client):
    report = create_status("report")
    logging.info("Publishing report: %s", report)
    client.publish(topic_report, json.dumps(report), qos=1, retain=True)


def load_mqtt_auth():
    auth_path = Path(".mqtt-config.json")
    timeout_s = 60
    while not auth_path.is_file():
        logging.warning(("mqtt-config not found! waiting to be downloaded by "
                         "speedtest_logger, sleeping for %d s"), timeout_s)
        time.sleep(timeout_s)

    with open(auth_path, "r") as file:
        return json.load(file)


def main():
    client = mqtt.Client(
        client_id=mac,
        callback_api_version=mqtt.CallbackAPIVersion.VERSION1)
    client.on_connect = on_connect
    client.on_message = on_message

    auth = load_mqtt_auth()
    client.username_pw_set(auth['username'], auth['password'])
    client.connect(config['broker_addr'], int(config['broker_port']), 60)

    client.loop_start()

    try:
        while True:
            publish_msg(client)
            time.sleep(config["publish_interval"])
    except KeyboardInterrupt:
        logging.info("Disconnecting from the broker...")
        client.disconnect()


if __name__ == '__main__':
    main()
