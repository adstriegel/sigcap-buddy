#!/bin/bash

sudo sed -i "s/#deb-src/deb-src/g" /etc/apt/sources.list
sudo apt update && sudo apt source wireless-tools
cd wireless-tools-*
sudo sed -i "s/timeout = 15000000/timeout = 30000000/" iwlist.c
sudo make && sudo make install
