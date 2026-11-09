#!/bin/bash
# PrinterCam watchdog: restart service if stream sends no frames
up=$(cut -d. -f1 /proc/uptime)
[ "$up" -lt 90 ] && exit 0
systemctl is-active --quiet PrinterCam || exit 0
since=$(systemctl show PrinterCam -p ActiveEnterTimestampMonotonic --value)
now=$(( up * 1000000 ))
[ $(( (now - since) / 1000000 )) -lt 45 ] && exit 0
bytes=$(timeout 4 curl -s http://localhost:7123/stream.mjpg | wc -c)
if [ "$bytes" -lt 20000 ]; then
  logger -t printercam-watchdog "No frames ($bytes bytes); restarting PrinterCam"
  systemctl restart PrinterCam
fi
