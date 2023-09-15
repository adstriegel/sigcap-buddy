import subprocess
import json
import datetime
import time
import logging
import os

logging.basicConfig(filename='/home/netscale/Desktop/sigcap-buddy/speedtest_logger.log', level=logging.DEBUG)

def download_speedtest():
    """Download and extract the speedtest executable if not present."""
    DOWNLOAD_ATTEMPTS = 3
    SPEEDTEST_LINK = 'https://install.speedtest.net/app/cli/ookla-speedtest-1.2.0-linux-x86_64.tgz'
    
    if not os.path.exists('./speedtest'):
        for _ in range(DOWNLOAD_ATTEMPTS):
            try:
                # Download the tar file
                subprocess.check_output(['wget', SPEEDTEST_LINK])
                # Extract the tar file
                subprocess.check_output(['tar', '-xvf', 'ookla-speedtest-1.2.0-linux-x86_64.tgz'])
                # Check if speedtest exists in the current directory after extraction
                if os.path.exists('speedtest/ookla-speedtest-1.2.0-linux-x86_64/speedtest'):
                    # Copy the executable to the current directory
                    subprocess.check_output(['cp', 'speedtest/ookla-speedtest-1.2.0-linux-x86_64/speedtest', '.'])
                # Cleanup
                #subprocess.check_output(['rm', '-r', 'speedtest'])
                subprocess.check_output(['rm', 'ookla-speedtest-1.2.0-linux-x86_64.tgz'])
                break
            except subprocess.CalledProcessError:
                logging.error(f"Attempt {_ + 1} to download speedtest failed.")
        else:
            logging.error("All attempts to download speedtest failed. Please ensure you have an active internet connection.")
            logging.error(f"If the issue persists, locate the latest link for Ookla Speedtest CLI and update the link in {__file__}.")
            raise SystemExit("Exiting due to failed speedtest download.")


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
    download_speedtest()  # Ensure speedtest executable is present
    while True:
        run_speedtest()
        interval = read_config()
        time.sleep(interval)

if __name__ == "__main__":
    main()
