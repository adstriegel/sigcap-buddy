import subprocess
import json
import datetime
import time
import logging

logging.basicConfig(filename='/home/netscale/Desktop/sigcap-buddy/speedtest_logger.log', level=logging.DEBUG)

def read_config():
    with open("config.json", "r") as config_file:
        config = json.load(config_file)
        return config["speedtest_interval"] * 60  # Convert to seconds

def run_speedtest():
    # Record start time
    start_time = datetime.datetime.now().isoformat()
    
    # Run the speedtest command
    result = subprocess.check_output(["./speedtest", "--progress=no", "--format=json"]).decode('utf-8')
    data = json.loads(result)

    # Record end time
    end_time = datetime.datetime.now().isoformat()
    
    # Extracting relevant data
    log = {
        'start_time': start_time,
        'end_time': end_time,
        'server': data['server']['name'],
        'isp': data['isp'],
        'idle_latency': data['ping']['latency'],
        'download_speed': data['download']['bandwidth'],
        'upload_speed': data['upload']['bandwidth'],
        'download_data_used': data['download']['bytes'],
        'upload_data_used': data['upload']['bytes']
    }

    # Log this data
    with open('speedtest_log.json', 'a') as log_file:
        log_file.write(json.dumps(log) + "\n")

def main():
    while True:
        run_speedtest()
        interval = read_config()
        time.sleep(interval)

if __name__ == "__main__":
    main()
