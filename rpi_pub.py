from datetime import datetime, timezone
import firebase
from getpass import getuser
import jc
import json
import logging
from logging import Formatter
from logging.handlers import TimedRotatingFileHandler
from paho.mqtt import client as mqtt
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


# Define topics
topic_report = f"Schmidt/{mac}/report/status"
topic_config = "Schmidt/config"
topic_config_res = f"Schmidt/{mac}/config/result"


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


def get_ifaces():
    parsed = jc.parse("ifconfig", utils.run_cmd("ifconfig"))
    # Remove unneeded parameters
    parsed = list(map(lambda x: {
        "name": x["name"],
        "up": "UP" in x["state"],
        "ip_address": x["ipv4_addr"],
        "mac_address": x["mac_addr"]
    }, parsed))
    # Remove loopback
    parsed = [item for item in parsed if item["name"] != "lo"]

    return parsed


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logging.info("Connected to MQTT broker")
        # Subscribe to "Schmidt/config" for commands
        client.subscribe(topic_config)
    else:
        logging.error(f"Connection failed with code {rc}")


def on_message(client, userdata, msg):
    # We only receive message from "Schmidt/config" topic
    payload = msg.payload.decode()
    logging.info("Message received: %s", payload)
    # Expected payload:
    # {
    #     "cmd": command,
    #     "mac": mac recipient (wildcard if ""),
    # }
    commands = json.loads(payload)

    # Skip if the command is not intended for this mac
    if "mac" in commands and commands["mac"] != "" and commands["mac"] != mac:
        logging.info("Skipping command intended for %s.", mac)
        return

    match commands["cmd"]:
        case "ping":
            # Ping the Pi
            logging.info("Got ping command")
            client.publish(
                topic_config_res,
                json.dumps({"mac": mac,
                            "cmd": commands["cmd"],
                            "res": "success",
                            "err": ""}),
                qos=1, retain=True)

        case "update":
            # Run the update script
            logging.info("Got update command")
            output = utils.run_cmd(
                ("wget -q -O - https://raw.githubusercontent.com/adstriegel/"
                 "sigcap-buddy/main/pi-setup.sh | /bin/bash"),
                raw_out=True)
            logging.debug(output)
            if (output["result"] == 0):
                client.publish(
                    topic_config_res,
                    json.dumps({"mac": mac,
                                "cmd": commands["cmd"],
                                "res": "success",
                                "err": ""}),
                    qos=1, retain=True)
            else:
                client.publish(
                    topic_config_res,
                    json.dumps({"mac": mac,
                                "cmd": commands["cmd"],
                                "res": "failed",
                                "err": output["stderr"]}),
                    qos=1, retain=True)

        case "publish":
            # TODO immediately publish report
            pass

        case "logs":
            # TODO send program logs and error logs
            # Extra option "tgt": "mqtt" or "speedtest"
            # Extra option "n": read last n lines, default 20
            pass

        case "restart-srv":
            # TODO restart services
            # Extra option "tgt": "mqtt" or "speedtest"
            pass

        case "reboot":
            # TODO reboot Pi
            pass

        case _:
            logging.warning("Unknown command: %s", commands[0])


def publish_msg(client):
    report = {
        "mac": mac,
        "ssid": get_ssid(),
        "ifaces": get_ifaces(),
        "timestamp": datetime.now(timezone.utc).astimezone().isoformat()
    }
    logging.info("Publishing report: %s", report)
    client.publish(topic_report, json.dumps(report), qos=1, retain=True)


def load_mqtt_auth():
    with open('.mqtt-config.json', 'r') as file:
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
