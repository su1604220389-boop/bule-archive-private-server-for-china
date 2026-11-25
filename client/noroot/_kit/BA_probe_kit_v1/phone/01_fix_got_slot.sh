#!/system/bin/sh
# 01_fix_got_slot.sh -- fix ONE 4-byte constant in the already-installed patched libil2cpp.so
#
#   broken  : f2c2540 = 09 9a 92 d2   movz x9, #0x94d0  -> hooks gettimeofday  (WRONG)
#   fixed   : f2c2540 = 09 9b 92 d2   movz x9, #0x94d8  -> hooks getaddrinfo  (RIGHT)
#
# Why: libunity's import GOT slot 0x13d94d0 is gettimeofday, 0x13d94d8 is getaddrinfo.
#      The current on-device build writes its stub into the gettimeofday slot, which
#      breaks the game's time base (that is very likely the "timeout" in E64).
#
# Usage:
#     sh 01_fix_got_slot.sh            # verify + patch
#     sh 01_fix_got_slot.sh --check    # only print current state
#     sh 01_fix_got_slot.sh --rollback # restore the 4 bytes saved by the last patch
#
# ASCII only. Needs root. Game must be force-stopped.

PKG=com.RoamingStar.BlueArchive
CAVE_OFF=254551056      # 0xf2c2410
SLOT_OFF=254551360      # 0xf2c2540
BAK=/sdcard/ba_slot_backup.bin
MODE=patch
[ "$1" = "--check" ]    && MODE=check
[ "$1" = "--rollback" ] && MODE=rollback

if [ "$(id -u)" != "0" ]; then
    command -v su >/dev/null 2>&1 && exec su -c "sh $0 $*"
    echo "[!] need root"; exit 1
fi

SO=$(ls /data/app/*/$PKG-*/lib/arm64/libil2cpp.so 2>/dev/null | head -1)
[ -z "$SO" ] && SO=$(pm path $PKG | sed -n 's/^package://p' | head -1 | sed 's#/base.apk#/lib/arm64/libil2cpp.so#')
[ -f "$SO" ] || { echo "[!] libil2cpp.so not found"; exit 1; }
echo "[*] target: $SO"

hexat() { dd if="$SO" bs=1 skip=$1 count=$2 2>/dev/null | od -An -tx1 -v | tr -d ' \n'; }

CAVE=$(hexat $CAVE_OFF 4)
SLOT=$(hexat $SLOT_OFF 4)
echo "[*] cave head : $CAVE   (expect f353b6a9 = the patched g20 build)"
echo "[*] slot word : $SLOT"

case "$SLOT" in
    099a92d2) STATE=broken ;;
    099b92d2) STATE=fixed  ;;
    *)        STATE=other  ;;
esac
echo "[*] state     : $STATE"

if [ "$CAVE" != "f353b6a9" ]; then
    echo
    echo "[!] this file does NOT look like the patched (g20) build."
    echo "    cave head at offset $CAVE_OFF should be f3 53 b6 a9."
    echo "    The installed so is probably the ORIGINAL one -- nothing to fix here."
    echo "    Install the patched build first, or use the PC-side proxy track instead."
    exit 2
fi

[ "$MODE" = "check" ] && exit 0

if [ "$MODE" = "rollback" ]; then
    [ -f "$BAK" ] || { echo "[!] no backup at $BAK"; exit 1; }
    echo "[*] restoring 4 bytes from $BAK"
    dd if="$BAK" of="$SO" bs=1 seek=$SLOT_OFF conv=notrunc 2>/dev/null
    echo "[*] now: $(hexat $SLOT_OFF 4)"
    exit 0
fi

if [ "$STATE" = "fixed" ]; then
    echo "[*] already fixed, nothing to do"; exit 0
fi

# --- stop the game, patch, verify -----------------------------------------
echo "[*] force-stopping $PKG"
am force-stop $PKG 2>/dev/null
sleep 2

dd if="$SO" of="$BAK" bs=1 skip=$SLOT_OFF count=4 2>/dev/null
echo "[*] backup of old 4 bytes -> $BAK ($(od -An -tx1 -v "$BAK" | tr -d '\n'))"

echo "[*] writing 09 9b 92 d2 (movz x9,#0x94d8)"
printf '\011\233\222\322' | dd of="$SO" bs=1 seek=$SLOT_OFF conv=notrunc 2>/dev/null

NOW=$(hexat $SLOT_OFF 4)
echo "[*] readback  : $NOW"
if [ "$NOW" = "099b92d2" ]; then
    echo
    echo "OK   patched. getaddrinfo slot is now correct."
    echo "     next: start the game, play until the gateway error, then run"
    echo "           sh 00_collect.sh    (to grab bainj.txt = resolution log)"
    echo "           sh 02_net_watch.sh  (to see where it connects)"
else
    echo "[!] readback mismatch -- file may be on a protected mount."
    echo "    try: mount -o remount,rw /data   (unlikely needed) or use the PC track."
    exit 3
fi
