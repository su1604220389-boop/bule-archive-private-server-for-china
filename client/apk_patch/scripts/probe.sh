#!/bin/bash
# WSL toolchain probe for BA apk_patch
echo "=== id ==="
id
echo "=== sudo ==="
if sudo -n true 2>/dev/null; then echo "SUDO_NOPASS_OK"; else echo "SUDO_NEEDS_PASS_OR_ABSENT"; fi
echo "=== os ==="
. /etc/os-release 2>/dev/null
echo "$PRETTY_NAME"
echo "=== java ==="
if command -v java >/dev/null 2>&1; then java -version 2>&1; else echo "NO_JAVA"; fi
echo "=== javac ==="
if command -v javac >/dev/null 2>&1; then javac -version 2>&1; else echo "NO_JAVAC"; fi
echo "=== tool paths ==="
for t in java javac apktool jadx baksmali smali apksigner zipalign python3 pip3 aapt aapt2 unzip zip keytool d8 dx procyon jd-cli; do
  printf "%-12s %s\n" "$t" "$(command -v "$t" 2>/dev/null || echo MISSING)"
done
echo "=== apt-cache apktool ==="
apt-cache policy apktool 2>&1 | head -6
echo "=== apt-cache default-jre-headless ==="
apt-cache policy default-jre-headless 2>&1 | head -6
echo "=== python3 ==="
python3 --version 2>&1
python3 -c "import zipfile,sys; print('zipfile ok', sys.version)" 2>&1
echo "=== pip modules ==="
python3 -m pip list 2>/dev/null | head -40
echo "=== disk ==="
df -h / /mnt/c 2>&1
echo "=== nproc / mem ==="
nproc
free -h 2>&1 | head -3
echo "=== androiddir candidates ==="
ls -d /opt/* 2>/dev/null
ls -d /usr/share/apktool* 2>/dev/null
ls -d ~/Android 2>/dev/null
ls ~/.local/bin 2>/dev/null
echo "=== DONE ==="
