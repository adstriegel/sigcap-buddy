from datetime import datetime, timezone
import logging
from pathlib import Path
import time
import utils

# List of channel targets:
# 6 GHz channels BW 80 MHz and 5 GHz channels BW 40 MHz
channel_list = [
    { 'freq_label': '6ghz', 'primary_ch': 5,    'primary_center_freq': 5975, 'center_freq': 5985, 'width': 80 },
    { 'freq_label': '6ghz', 'primary_ch': 21,   'primary_center_freq': 6055, 'center_freq': 6065, 'width': 80 },
    { 'freq_label': '6ghz', 'primary_ch': 37,   'primary_center_freq': 6135, 'center_freq': 6145, 'width': 80 },
    { 'freq_label': '6ghz', 'primary_ch': 53,   'primary_center_freq': 6215, 'center_freq': 6225, 'width': 80 },
    { 'freq_label': '6ghz', 'primary_ch': 69,   'primary_center_freq': 6295, 'center_freq': 6305, 'width': 80 },
    { 'freq_label': '6ghz', 'primary_ch': 85,   'primary_center_freq': 6375, 'center_freq': 6385, 'width': 80 },
    { 'freq_label': '6ghz', 'primary_ch': 101,  'primary_center_freq': 6455, 'center_freq': 6465, 'width': 80 },
    { 'freq_label': '6ghz', 'primary_ch': 117,  'primary_center_freq': 6535, 'center_freq': 6545, 'width': 80 },
    { 'freq_label': '6ghz', 'primary_ch': 133,  'primary_center_freq': 6615, 'center_freq': 6625, 'width': 80 },
    { 'freq_label': '6ghz', 'primary_ch': 149,  'primary_center_freq': 6695, 'center_freq': 6705, 'width': 80 },
    { 'freq_label': '6ghz', 'primary_ch': 165,  'primary_center_freq': 6775, 'center_freq': 6785, 'width': 80 },
    { 'freq_label': '6ghz', 'primary_ch': 181,  'primary_center_freq': 6855, 'center_freq': 6865, 'width': 80 },
    { 'freq_label': '6ghz', 'primary_ch': 197,  'primary_center_freq': 6935, 'center_freq': 6945, 'width': 80 },
    { 'freq_label': '6ghz', 'primary_ch': 213,  'primary_center_freq': 7015, 'center_freq': 7025, 'width': 80 },
    { 'freq_label': '5ghz', 'primary_ch': 36,   'primary_center_freq': 5180, 'center_freq': 5190, 'width': 40 },
    { 'freq_label': '5ghz', 'primary_ch': 40,   'primary_center_freq': 5200, 'center_freq': 5190, 'width': 40 },
    { 'freq_label': '5ghz', 'primary_ch': 44,   'primary_center_freq': 5220, 'center_freq': 5230, 'width': 40 },
    { 'freq_label': '5ghz', 'primary_ch': 48,   'primary_center_freq': 5240, 'center_freq': 5230, 'width': 40 },
    { 'freq_label': '5ghz', 'primary_ch': 52,   'primary_center_freq': 5260, 'center_freq': 5270, 'width': 40 },
    { 'freq_label': '5ghz', 'primary_ch': 56,   'primary_center_freq': 5280, 'center_freq': 5270, 'width': 40 },
    { 'freq_label': '5ghz', 'primary_ch': 60,   'primary_center_freq': 5300, 'center_freq': 5310, 'width': 40 },
    { 'freq_label': '5ghz', 'primary_ch': 64,   'primary_center_freq': 5320, 'center_freq': 5310, 'width': 40 },
    { 'freq_label': '5ghz', 'primary_ch': 100,  'primary_center_freq': 5500, 'center_freq': 5510, 'width': 40 },
    { 'freq_label': '5ghz', 'primary_ch': 104,  'primary_center_freq': 5520, 'center_freq': 5510, 'width': 40 },
    { 'freq_label': '5ghz', 'primary_ch': 108,  'primary_center_freq': 5540, 'center_freq': 5550, 'width': 40 },
    { 'freq_label': '5ghz', 'primary_ch': 112,  'primary_center_freq': 5560, 'center_freq': 5550, 'width': 40 },
    { 'freq_label': '5ghz', 'primary_ch': 116,  'primary_center_freq': 5580, 'center_freq': 5590, 'width': 40 },
    { 'freq_label': '5ghz', 'primary_ch': 120,  'primary_center_freq': 5600, 'center_freq': 5590, 'width': 40 },
    { 'freq_label': '5ghz', 'primary_ch': 124,  'primary_center_freq': 5620, 'center_freq': 5630, 'width': 40 },
    { 'freq_label': '5ghz', 'primary_ch': 128,  'primary_center_freq': 5640, 'center_freq': 5630, 'width': 40 },
    { 'freq_label': '5ghz', 'primary_ch': 132,  'primary_center_freq': 5660, 'center_freq': 5670, 'width': 40 },
    { 'freq_label': '5ghz', 'primary_ch': 136,  'primary_center_freq': 5680, 'center_freq': 5670, 'width': 40 },
    { 'freq_label': '5ghz', 'primary_ch': 140,  'primary_center_freq': 5700, 'center_freq': 5710, 'width': 40 },
    { 'freq_label': '5ghz', 'primary_ch': 149,  'primary_center_freq': 5745, 'center_freq': 5755, 'width': 40 },
    { 'freq_label': '5ghz', 'primary_ch': 153,  'primary_center_freq': 5765, 'center_freq': 5755, 'width': 40 },
    { 'freq_label': '5ghz', 'primary_ch': 157,  'primary_center_freq': 5785, 'center_freq': 5795, 'width': 40 },
    { 'freq_label': '5ghz', 'primary_ch': 161,  'primary_center_freq': 5805, 'center_freq': 5795, 'width': 40 }
]


def monitor(monitor_iface, duration, packet_size=765, mode='all'):
    # Determine target channels
    target_chs = list()
    if (mode == 'all'):
        target_chs = channel_list
    elif (mode == '5ghz' or mode == '6ghz'):
        target_chs = [ch for ch in channel_list if ch['freq_label'] == mode]
    elif (mode == 'target'):
        # TODO
        pass
    else:
        logging.error('Monitor mode %s not allowed !')
    
    if (len(target_chs) > 0):
        capture_files = list()
        for ch in target_chs:
            result = utils.run_cmd(
                (f"sudo iw dev {monitor_iface} set freq "
                 f"{ch['primary_center_freq']} {ch['width']} "
                 f"{ch['center_freq']}"),
                (f"Set iface {monitor_iface} freq "
                 f"{ch['primary_center_freq']} {ch['width']} "
                 f"{ch['center_freq']}"),
                raw_out=True)
            if (result['returncode'] != 0):
                logging.warning(f"Cannot set {monitor_iface} freq ! "
                                f"{result['stderr']}")
                continue

            file_name = Path(f"capture_{ch['freq_label']}_{ch['primary_ch']}_"
                             f"{ch['width']}.pcap")
            proc = utils.run_cmd_async(
                (f"sudo tcpdump -i {monitor_iface} -s {packet_size} "
                 f"-w {file_name}"),
                (f"Capture Wi-Fi packets on {monitor_iface}, size {packet_size}"
                 f" to {file_name}"))
            time.sleep(duration)
            utils.resolve_cmd_async(
                proc,
                'Resolving Wi-Fi packet capture',
                timeout_s=duration + 1,
                kill=True)
            logging.info('Capture finished !')
            capture_files.append(file_name)

        completed_capture_files = [fn for fn in capture_files if fn.is_file()]
        if (len(completed_capture_files) > 0):
            logging.info(f"Zipping {len(completed_capture_files)} pcap files.")
            curr_datetime = datetime.now(timezone.utc).astimezone().isoformat()
            files_str = " ".join([str(fn) for fn in completed_capture_files])
            utils.run_cmd(
                f"zip logs/pcap-log/{curr_datetime}.zip {files_str}",
                'Zipping all capture files.')
            # Delete capture files afterwards
            for fn in completed_capture_files:
                fn.unlink()
        else:
            logging.info("No completed captures, skip zipping...")

