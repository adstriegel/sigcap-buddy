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


def byte_uint_to_int(byte_uint):
    out = byte_uint
    # check sign bit
    if (out & 0x8000) == 0x8000:
        # if set, invert and add one to get the negative value,
        # then add the negative sign
        out = -((out ^ 0xffff) + 1)
    return out


def read_beacon_ie(ie_hex_string):
    output = {
        "id": 0,
        "raw": ie_hex_string,
        "type": "",
        "elements": {}
    }
    # Convert hex string to bytes
    byte_data = bytes.fromhex(ie_hex_string)
    output["id"] = byte_data[0]

    match output["id"]:
        case 11:
            # BSS Load
            output["type"] = "BSS Load"
            output["elements"]["sta_count"] = int.from_bytes(
                byte_data[2:4], byteorder='little')
            output["elements"]["ch_utilization"] = byte_data[4] / 255
            output["elements"]["available_admission_cap"] = int.from_bytes(
                byte_data[5:7], byteorder='little')
        case 35:
            # TPC Report
            output["type"] = "TPC Report"
            output["elements"]["tx_power"] = byte_uint_to_int(byte_data[2])
            output["elements"]["link_margin"] = byte_uint_to_int(byte_data[3])
        case 61:
            # HT Operation
            output["type"] = "HT Operation"
            output["elements"]["primary_channel"] = byte_data[2]

            ht_operation_info = byte_data[3:8]
            output["elements"]["secondary_channel_offset"] = (
                ht_operation_info[0] & 0x03)
            output["elements"]["sta_channel_width"] = (
                (ht_operation_info[0] >> 2) & 0x01)
            output["elements"]["rifs_mode"] = (
                (ht_operation_info[0] >> 3) & 0x01)
            output["elements"]["ht_protection"] = (
                ht_operation_info[1] & 0x02)
            output["elements"]["nongf_ht_sta_present"] = (
                (ht_operation_info[1] >> 2) & 0x01)
            output["elements"]["obss_nonht_sta_present"] = (
                (ht_operation_info[1] >> 4) & 0x01)
            output["elements"]["channel_center_freq_segment_2"] = (
                ((ht_operation_info[1] >> 5) & 0x03)
                + (ht_operation_info[2] << 8))
            output["elements"]["dual_beacon"] = (
                (ht_operation_info[3] >> 6) & 0x01)
            output["elements"]["dual_cts_protection"] = (
                (ht_operation_info[3] >> 7) & 0x01)
            output["elements"]["stbc_beacon"] = (
                ht_operation_info[4] & 0x01)
            output["elements"]["lsig_txop_protection"] = (
                (ht_operation_info[4] >> 1) & 0x01)
            output["elements"]["pco_active"] = (
                (ht_operation_info[4] >> 2) & 0x01)
            output["elements"]["pco_phase"] = (
                (ht_operation_info[4] >> 3) & 0x01)

            output["elements"]["basic_mcs_set"] = int.from_bytes(
                byte_data[8:24], byteorder='little')
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
                        cell[key].append(ie)
                elif key == "rates":
                    cell[key] = matches
                else:
                    cell[key] = matches[0]

        if cell["bssid"] != "":
            cells.append(cell)

    return cells


if __name__ == '__main__':
    print(scan())
