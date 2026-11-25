#!/bin/bash
# apktool rebuild round-trip test (empty change) + fidelity comparison
APKTOOL="java -Xmx8g -jar /opt/ba-tools/apktool.jar"
W=/root/ba_work
cd $W || exit 1

echo "=== decode tree ==="
ls -la $W/dec0
echo "--- res subdir sample ---"
ls $W/dec0/res | head -20
echo "--- locate layout/tips/act_background ---"
ls -l $W/dec0/res/layout/fragment_default_mobile_code_login.xml 2>&1
ls -l $W/dec0/res/layout/act_background.xml 2>&1
ls -l $W/dec0/res/layout/activity_tips.xml 2>&1
ls -l $W/dec0/res/layout/fragment_quick_login.xml 2>&1
echo "--- public.xml present? ---"
ls -l $W/dec0/res/values/public.xml 2>&1
wc -l $W/dec0/res/values/public.xml 2>/dev/null
echo "--- values dirs ---"
ls $W/dec0/res | grep -i value | head -20
echo "--- original/ ---"
find $W/dec0/original -maxdepth 2 | head -20

echo ""
echo "=== rebuild (no edits) ==="
rm -f $W/slim_rebuild.apk
time $APKTOOL b -f -o $W/slim_rebuild.apk $W/dec0 2>&1 | tail -60
echo "rc=$?"
ls -l $W/slim_rebuild.apk 2>&1
echo "=== DONE ==="
