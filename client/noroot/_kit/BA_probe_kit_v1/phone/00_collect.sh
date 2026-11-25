#!/system/bin/sh
# 00_collect.sh -- BA prober / stage 0: collect ground truth from the phone.
# Usage (on device, or via adb shell):
#     sh 00_collect.sh
# Everything lands in /sdcard/ba_collect_<timestamp>/  -- send that folder back.
# ASCII only. Safe: reads only, never writes to the game.

PKG=com.RoamingStar.BlueArchive
TS=$(date +%Y%m%d_%H%M%S)
OUT=/sdcard/ba_collect_$TS

if [ "$(id -u)" != "0" ]; then
    if command -v su >/dev/null 2>&1; then
        echo "[*] not root, re-exec through su"
        exec su -c "sh $0 $*"
    else
        echo "[!] not root and no su; results will be partial"
    fi
fi

mkdir -p "$OUT" || { echo "cannot mkdir $OUT"; exit 1; }
echo "[*] output: $OUT"
echo "$TS" > "$OUT/timestamp.txt"

run() {  # run <outfile> <cmd...>
    _f="$OUT/$1"; shift
    echo "### $*" > "$_f"
    "$@" >> "$_f" 2>&1
}

# ---------------------------------------------------------------- 1. device
{
    echo "model=$(getprop ro.product.model)"
    echo "brand=$(getprop ro.product.brand)"
    echo "android=$(getprop ro.build.version.release)"
    echo "sdk=$(getprop ro.build.version.sdk)"
    echo "abi=$(getprop ro.product.cpu.abi)"
    echo "selinux=$(getenforce)"
    echo "uid=$(id)"
} > "$OUT/device.txt"

# ---------------------------------------------------------------- 2. package
{
    echo "== pm path =="
    pm path $PKG
    echo
    echo "== package info =="
    dumpsys package $PKG | grep -E 'versionName|versionCode|codePath|resourcePath|primaryCpuAbi|legacyNativeLibraryDir|dataDir|firstInstallTime|lastUpdateTime' | head -30
    echo
    echo "== extracted native lib dir =="
    ls -l /data/app/*/$PKG-*/lib/arm64/ 2>/dev/null
} > "$OUT/package.txt" 2>&1

# ---------------------------------------------------------------- 3. so hashes
{
    for so in /data/app/*/$PKG-*/lib/arm64/libil2cpp.so \
              /data/app/*/$PKG-*/lib/arm64/libunity.so \
              /data/app/*/$PKG-*/lib/arm64/libmain.so ; do
        [ -f "$so" ] || continue
        ls -l "$so"
        if command -v sha256sum >/dev/null 2>&1; then
            echo "sha256=$(sha256sum "$so" | cut -d' ' -f1)"
        fi
        echo
    done
} > "$OUT/so_hashes.txt" 2>&1

# ---------------------------------------------------------------- 4. cave marker
# patched libil2cpp (g20 build) has a code cave at 0xf2c2410 and the slot const at 0xf2c2540
SO=$(ls /data/app/*/$PKG-*/lib/arm64/libil2cpp.so 2>/dev/null | head -1)
if [ -n "$SO" ]; then
    {
        echo "so=$SO"
        echo
        echo "== cave head @ 254551056 (0xf2c2410), expect: f3 53 b6 a9 = patched build =="
        dd if="$SO" bs=1 skip=254551056 count=16 2>/dev/null | od -An -tx1 -v
        echo
        echo "== slot const @ 254551360 (0xf2c2540) =="
        echo "   patched-broken : 09 9a 92 d2  (movz x9,#0x94d0 -> gettimeofday)"
        echo "   patched-fixed  : 09 9b 92 d2  (movz x9,#0x94d8 -> getaddrinfo)"
        echo "   original build : (not this one)"
        dd if="$SO" bs=1 skip=254551360 count=16 2>/dev/null | od -An -tx1 -v
    } > "$OUT/cave.txt" 2>&1
fi

# ---------------------------------------------------------------- 5. runtime files (hex)
FD=/sdcard/Android/data/$PKG/files
DD=/data/data/$PKG/files
dumpf() {  # dumpf <label> <path>
    _lab="$1"; _p="$2"
    [ -f "$_p" ] || { echo "### $_lab : MISSING $_p"; return; }
    echo "### $_lab  ($(wc -c < "$_p") bytes)  $_p"
    echo "--- as text ---"
    cat "$_p" 2>/dev/null
    echo
    echo "--- as hex ---"
    od -An -tx1 -v "$_p" | head -40
    echo
}
{
    echo "== external files =="
    ls -la "$FD" 2>/dev/null
    echo
    echo "== internal files =="
    ls -la "$DD" 2>/dev/null
    echo
    dumpf Hosts          "$FD/Hosts"
    dumpf LocalConfig    "$FD/LocalConfig.json"
    dumpf LocalizeConfig "$FD/LocalizeConfig.txt"
    dumpf GlobalConfig   "$FD/GlobalConfig.json"
    dumpf bainj          "$DD/bainj.txt"
} > "$OUT/runtime_files.txt" 2>&1

# ---------------------------------------------------------------- 6. ACE / exits
{
    echo "== exit-info =="
    dumpsys activity exit-info $PKG 2>/dev/null | head -60
    echo
    echo "== ace bookkeeping files =="
    ls -la "$DD"/ace_shell_di.dat "$DD"/shell_cache "$DD"/ano_tmp "$DD"/data/app 2>&1
} > "$OUT/ace.txt" 2>&1

# ---------------------------------------------------------------- 7. live state
{
    echo "== ps =="
    ps -A 2>/dev/null | grep -i -E 'BlueArchive|RoamingStar' 
    echo
    echo "== ss -tnp =="
    ss -tnp 2>/dev/null | head -60
} > "$OUT/live.txt" 2>&1

PID=$(ps -A 2>/dev/null | grep "$PKG" | grep -v grep | head -1 | awk '{print $2}')
if [ -n "$PID" ]; then
    {
        echo "pid=$PID"
        echo "== maps (libunity / libil2cpp) =="
        grep -E 'libunity\.so|libil2cpp\.so|libtprt\.so' /proc/$PID/maps
    } > "$OUT/maps.txt" 2>&1
fi

# ---------------------------------------------------------------- 8. logcat
logcat -d -t 4000 -v threadtime 2>/dev/null | grep -i -E 'AiriSDK|Xposed|ACRA|BlueArchive|RoamingStar|tprt|ACE|il2cpp' > "$OUT/logcat.txt"

# ---------------------------------------------------------------- 9. done
echo
echo "[*] done. files:"
ls -l "$OUT"
echo
echo "Send this folder back:  $OUT"
echo "(from PC:  adb pull $OUT  )"
