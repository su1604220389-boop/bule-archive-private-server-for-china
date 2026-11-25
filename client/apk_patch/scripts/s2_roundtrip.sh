#!/bin/bash
set -u
# 1) string_ids of the STEP1 *empty* roundtrip dex, to separate roundtrip drift from our edits
echo "########## STEP1 empty-roundtrip dex (slim_rebuild.apk) ##########"
unzip -p /root/ba_work/slim_rebuild.apk classes.dex > /root/ba_work/verify/classes_rt0.dex
python3 - <<'PY'
import struct
for tag,p in [('orig      ','/root/ba_work/verify/classes_orig.dex'),
              ('empty-rt   ','/root/ba_work/verify/classes_rt0.dex'),
              ('patched    ','/root/ba_work/out/classes.dex')]:
    d=open(p,'rb').read()
    print('%s size=%-9d string_ids=%-6d type_ids=%-5d proto=%-6d field=%-6d method=%-6d class=%-5d'
          % (tag,len(d),
             struct.unpack('<I',d[56:60])[0], struct.unpack('<I',d[64:68])[0],
             struct.unpack('<I',d[72:76])[0], struct.unpack('<I',d[80:84])[0],
             struct.unpack('<I',d[88:92])[0], struct.unpack('<I',d[96:100])[0]))
PY

echo
echo "########## full baksmali round-trip fidelity check ##########"
rm -rf /root/ba_work/rt
java -jar /opt/ba-tools/apktool.jar d -f -o /root/ba_work/rt /root/ba_work/exp_final.apk > /root/ba_work/rt.log 2>&1
echo "apktool d rc=$?"
tail -4 /root/ba_work/rt.log
echo
echo "--- diff: dec2/smali (what we assembled)  vs  rt/smali (baksmali of the new dex) ---"
diff -r /root/ba_work/dec2/smali /root/ba_work/rt/smali > /root/ba_work/verify/rt_diff.txt 2>&1
echo "diff rc=$?   diff lines=$(wc -l < /root/ba_work/verify/rt_diff.txt)"
head -60 /root/ba_work/verify/rt_diff.txt
echo
echo "--- diff: dec2/smali_classes2 vs rt/smali_classes2 (untouched, must be identical) ---"
diff -r /root/ba_work/dec2/smali_classes2 /root/ba_work/rt/smali_classes2 > /root/ba_work/verify/rt_diff2.txt 2>&1
echo "diff rc=$?   diff lines=$(wc -l < /root/ba_work/verify/rt_diff2.txt)"
head -20 /root/ba_work/verify/rt_diff2.txt
