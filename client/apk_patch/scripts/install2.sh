#!/bin/bash
# install2: upgrade apktool to latest jar, add jadx, apksigner, zipalign, aapt/aapt2
set -x
export DEBIAN_FRONTEND=noninteractive
TOOLS=/opt/ba-tools
mkdir -p $TOOLS
cd $TOOLS

echo "=== apt: apksigner zipalign aapt ==="
apt-get install -y -qq --no-install-recommends apksigner zipalign aapt 2>&1 | tail -10
which apksigner zipalign aapt
apksigner version 2>&1 | head -2
aapt version 2>&1 | head -2
zipalign 2>&1 | head -3

echo "=== apktool latest ==="
curl -sL --max-time 120 -o $TOOLS/apktool.jar https://github.com/iBotPeaches/Apktool/releases/download/v2.11.1/apktool_2.11.1.jar
ls -l $TOOLS/apktool.jar
java -jar $TOOLS/apktool.jar --version 2>&1 | head -3

echo "=== jadx latest ==="
curl -sL --max-time 240 -o $TOOLS/jadx.zip https://github.com/skylot/jadx/releases/download/v1.5.3/jadx-1.5.3.zip
ls -l $TOOLS/jadx.zip
unzip -q -o $TOOLS/jadx.zip -d $TOOLS/jadx
chmod +x $TOOLS/jadx/bin/jadx $TOOLS/jadx/bin/jadx-gui 2>/dev/null
ls $TOOLS/jadx/bin/
$TOOLS/jadx/bin/jadx --version 2>&1 | head -3

echo "=== aapt2 from google maven ==="
curl -s --max-time 60 -o /tmp/maven_aapt2.xml https://dl.google.com/dl/android/maven2/com/android/tools/build/aapt2/maven-metadata.xml
tail -20 /tmp/maven_aapt2.xml 2>/dev/null

echo "=== DONE INSTALL2 ==="
