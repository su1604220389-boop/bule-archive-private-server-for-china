#!/bin/bash
# apktool decode/rebuild round-trip test on the slim APK
set -e
APKTOOL="java -Xmx6g -jar /opt/ba-tools/apktool.jar"
W=/root/ba_work
mkdir -p $W
cd $W
SLIM=/mnt/c/Users/su/Desktop/大肥鱼项目/BAServer/work/ba/apk_patch/slim/slim.apk

echo "=== clean ==="
rm -rf $W/dec0 $W/slim_rebuild.apk
echo "=== decode (empty change baseline) ==="
time $APKTOOL d -f -o $W/dec0 "$SLIM" 2>&1 | tail -40
echo "=== decode tree top ==="
ls -la $W/dec0 | head -30
echo "=== decoded resources.arsc present? ==="
ls -l $W/dec0/resources.arsc $W/dec0/apktool.yml 2>&1
echo "=== res dir count ==="
find $W/dec0/res -type f | wc -l
echo "=== locate Q9 / act_background / tips layout ==="
grep -n "fragment_default_mobile_code_login\|act_background\|activity_tips" $W/dec0/res/values/public.xml 2>/dev/null | head -10
ls -l $W/dec0/res/layout/fragment_default_mobile_code_login.xml 2>&1 | head -3
echo "=== rebuild (no edits) ==="
time $APKTOOL b -f -o $W/slim_rebuild.apk $W/dec0 2>&1 | tail -40
ls -l $W/slim_rebuild.apk
echo "=== DONE ==="
