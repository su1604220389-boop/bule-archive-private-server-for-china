#!/system/bin/sh
# 02_net_watch.sh -- passive: log every TCP connection the game makes (no hooks, no patching)
#
#   sh 02_net_watch.sh            # watch for 180s
#   sh 02_net_watch.sh 600        # watch for 600s
#
# Output: /sdcard/ba_net_<timestamp>.log
#         each line: time  pid  remote-ip:port  state
# This alone answers "which hosts does the client talk to, and in what order",
# without touching the APK or the .so files.

PKG=com.RoamingStar.BlueArchive
DUR=${1:-180}
TS=$(date +%Y%m%d_%H%M%S)
OUT=/sdcard/ba_net_$TS.log

if [ "$(id -u)" != "0" ]; then
    command -v su >/dev/null 2>&1 && exec su -c "sh $0 $*"
    echo "[!] need root for ss -p"; exit 1
fi

echo "# ba_net_watch start $TS  dur=${DUR}s" | tee "$OUT"
echo "# remote ip / port  ->  you can look up the hostname on the PC side" | tee -a "$OUT"

END=$(( $(date +%s) + DUR ))
SEEN=""
while [ "$(date +%s)" -lt "$END" ]; do
    PID=$(ps -A 2>/dev/null | grep "$PKG" | grep -v grep | head -1 | awk '{print $2}')
    if [ -n "$PID" ]; then
        ss -tnp 2>/dev/null | grep "pid=$PID" | while read -r line; do
            REM=$(echo "$line" | awk '{print $5}')
            ST=$(echo "$line" | awk '{print $1}')
            echo "$(date +%H:%M:%S)  pid=$PID  $REM  $ST"
        done
    fi
    sleep 1
done | awk '!seen[$0]++' | tee -a "$OUT"

echo
echo "# done -> $OUT"
echo "# (from PC:  adb pull $OUT )"
