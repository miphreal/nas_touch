#!/bin/bash

LOG_DIR=/mnt/data/.daemons/dropbox/Dropbox/sys/nas/logs


if [ "$(ifconfig | grep -o ppp0)" != "ppp0" ]; then
	pppd call vpn.itechart
fi

date > "$LOG_DIR/last_update"
ifconfig > "$LOG_DIR/ifconfig.log"
top -bn1 > "$LOG_DIR/top.log"
df -h > "$LOG_DIR/df.log"
free -m > "$LOG_DIR/free.log"
route > "$LOG_DIR/route.log"
sensors > "$LOG_DIR/sensors.log"