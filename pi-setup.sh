#!/bin/bash

USER=`whoami`

# 1. Install required apps, setup firebase venv
echo "wireshark-common wireshark-common/install-setuid boolean true" | sudo debconf-set-selections
echo "iperf3 iperf3/start_daemon boolean false" | sudo debconf-set-selections
sudo apt update && DEBIAN_FRONTEND=noninteractive sudo apt install git iperf3 python3 python3-pip python3-venv wireshark -y
if [ ! -d /home/$USER/venv_firebase ]; then
	python -m venv /home/$USER/venv_firebase
fi
/home/$USER/venv_firebase/bin/python -m pip install firebase-admin

# 2. git clone/pull sigcap-buddy
if [ ! -d /home/$USER/sigcap-buddy ]; then
	git clone https://github.com/adstriegel/sigcap-buddy
else
	cd /home/$USER/sigcap-buddy
	git pull
	cd ~
fi

# 2.1. checkout to testing branch if a .testing file is detected
if [ -f /home/$USER/.testing ]; then
	cd /home/$USER/sigcap-buddy
	git checkout testing
	git pull
	cd ~
fi

# 3. Setup dir
mkdir -p /home/$USER/sigcap-buddy/logs/fmnc-log
mkdir -p /home/$USER/sigcap-buddy/logs/iperf-log
mkdir -p /home/$USER/sigcap-buddy/logs/pcap-log
mkdir -p /home/$USER/sigcap-buddy/logs/speedtest-log
mkdir -p /home/$USER/sigcap-buddy/logs/wifi-scan

# 4. Fetch speedtest-cli and extract
rm /tmp/ookla-speedtest*
wget -P /tmp https://install.speedtest.net/app/cli/ookla-speedtest-1.2.0-linux-$(arch).tgz
tar -xf /tmp/ookla-speedtest-1.2.0-linux-$(arch).tgz -C /home/$USER/sigcap-buddy
# First run to accept license
/home/$USER/sigcap-buddy/speedtest --accept-license --progress=no

# 5. Fetch firebase auth
if [ ! -f /home/$USER/sigcap-buddy/nd-schmidt-firebase-*.json ]; then
	wget --user nsadmin --ask-password -P /home/$USER/sigcap-buddy http://ns-mn1.cse.nd.edu/firebase/nd-schmidt-firebase-adminsdk-d1gei-43db929d8a.json
fi

# 6. Enable/restart service
if [ -f /etc/systemd/system/speedtest_logger.service ]; then
	sed -e "s/\$USER/$USER/g" /home/$USER/sigcap-buddy/speedtest_logger.service.template > speedtest_logger.service
	sudo mv speedtest_logger.service /etc/systemd/system/
	sudo systemctl reenable speedtest_logger.service
	sudo systemctl restart speedtest_logger.service
else
	sed -e "s/\$USER/$USER/g" /home/$USER/sigcap-buddy/speedtest_logger.service.template > speedtest_logger.service
	sudo mv speedtest_logger.service /etc/systemd/system/
	sudo systemctl enable speedtest_logger.service
	sudo systemctl start speedtest_logger.service
fi

# 7. Set update cron
cron_list=`crontab -l 2>&1`
if [[ ! $cron_list == *"pi-setup.sh"* ]] ; then
	(crontab -l ; echo "$((RANDOM % 60)) 0 * * * wget -q -O - https://raw.githubusercontent.com/adstriegel/sigcap-buddy/main/pi-setup.sh | /bin/bash") 2>&1 | grep -v "no crontab" | sort | uniq | crontab -
fi

# 8. Reset Wi-Fi connection
# nmcli --terse connection show | awk -F ":" '{if ($3 == "802-11-wireless") print $1}' | while read name; do sudo nmcli connection delete "$name"; done
