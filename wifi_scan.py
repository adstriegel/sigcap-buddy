import logging
import re
import subprocess

re_sub = re.compile(r"\s+")

re_patterns = {
    "bssid": re.compile(r"Address: *([0-9A-F:]+)"),
    "channel": re.compile(r"Channel: *(\d+)"),
    "freq": re.compile(r"Frequency: *([\d\.]+ ?.Hz)"),
    "rssi": re.compile(r"Signal level= *([-\d\.]+ ?dBm)"),
    "ssid": re.compile(r"ESSID: *\"(.+)\""),
    "rates": re.compile(r"\d+ Mb/s"),
    "extras": re.compile(r"IE: +Unknown: +([0-9A-F]+)")
}


def hex_to_uint(hex_string):
    return int(hex_string, 16)


def hex_to_int(hex_string):
    out = hex_to_uint(hex_string)
    # check sign bit
    if (out & 0x8000) == 0x8000:
        # if set, invert and add one to get the negative value,
        # then add the negative sign
        out = -((out ^ 0xffff) + 1)
    return out


def read_beacon_ie(ie_hex_string):
    output = {
        "id": 0,
        "type": "",
        "elements": {}
    }
    octets = [ie_hex_string[i:i + 2] for i in range(0, len(ie_hex_string), 2)]
    output["id"] = int(octets[0], 16)

    match output["id"]:
        case 11:
            # BSS Load
            output["type"] = "BSS Load"
            output["elements"]["sta_count"] = hex_to_uint(
                octets[3] + octets[2])
            output["elements"]["ch_utilization"] = hex_to_uint(octets[4]) / 255
        case 35:
            # TPC Report
            output["type"] = "TPC Report"
            output["elements"]["tx_power"] = hex_to_int(octets[2])
            output["elements"]["link_margin"] = hex_to_int(octets[3])
        case _:
            output["type"] = "Unknown"

    return output


def scan(iface="wlan0"):
    results = ""
    try:
        results = subprocess.check_output(
            ["sudo", "iwlist", iface, "scanning"]).decode('utf-8')
    except Exception as e:
        logging.warning("wifi scan failed: %s", e, exc_info=1)
        return []

    results = re_sub.sub(" ", results).split("Cell")
    cells = []

    for entry in results:
        cell = {
            "bssid": "",
            "channel": "",
            "freq": "",
            "rssi": "",
            "ssid": "",
            "rates": [],
            "extras": []
        }

        for key in re_patterns:
            matches = re_patterns[key].findall(entry)
            if (len(matches) > 0):
                if key == "extras":
                    for ie_hex in matches:
                        # Convert hex string to information element dict
                        ie = read_beacon_ie(ie_hex)
                        if ie["type"] != "Unknown":
                            cell[key].append(ie)
                elif key == "rates":
                    cell[key] = matches
                else:
                    cell[key] = matches[0]

        if cell["bssid"] != "":
            cells.append(cell)

    return cells
