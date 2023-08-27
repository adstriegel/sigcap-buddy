#!/bin/bash

while inotifywait -e modify /home/netscale/Desktop/sigcap-buddy/speedtest_logger.py /home/netscale/Desktop/sigcap-buddy/config.json; do
    sudo systemctl restart speedtest_logger.service
done
