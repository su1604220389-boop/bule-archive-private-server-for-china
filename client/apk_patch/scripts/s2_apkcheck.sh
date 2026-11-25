#!/bin/bash
set -u
OLD=/mnt/c/Users/su/Desktop/大肥鱼项目/BAServer/work/ba/apk_patch/backup/BA_noroot_prod_20261118_v1.apk
NEW=/mnt/c/Users/su/Desktop/大肥鱼项目/BAServer/work/ba/apk_patch/out/BlueArchive_cardlogin_v1.apk
O=/root/ba_work/outcheck; rm -rf $O; mkdir -p $O

echo "######################## aapt dump badging : BASELINE ########################"
aapt dump badging "$OLD" 2>&1 > $O/badging_old.txt
head -6 $O/badging_old.txt
echo "   ... (full: $(wc -l < $O/badging_old.txt) lines)"
grep -E "^sdkVersion|^targetSdkVersion|^uses-permission: name='android.permission.INTERNET'|^native-code|^launchable-activity" $O/badging_old.txt | head -12

echo
echo "######################## aapt dump badging : NEW ########################"
aapt dump badging "$NEW" 2>&1 > $O/badging_new.txt
head -6 $O/badging_new.txt
echo "   ... (full: $(wc -l < $O/badging_new.txt) lines)"
grep -E "^sdkVersion|^targetSdkVersion|^native-code|^launchable-activity" $O/badging_new.txt | head -12

echo
echo "######################## badging diff (old vs new) ########################"
diff $O/badging_old.txt $O/badging_new.txt > $O/badging_diff.txt
echo "diff rc=$?  lines=$(wc -l < $O/badging_diff.txt)"
head -20 $O/badging_diff.txt

echo
echo "######################## apksigner verify : NEW ########################"
apksigner verify --print-certs -v "$NEW" 2>&1 | tee $O/sig_new.txt | head -30
echo "rc=$?"

echo
echo "######################## apksigner verify : BASELINE ########################"
apksigner verify --print-certs "$OLD" 2>&1 | tee $O/sig_old.txt | head -10

echo
echo "######################## certificate comparison ########################"
echo "--- baseline ---"
grep -iE "Signer #1 certificate SHA-256|Signer #1 certificate DN|Verified using" $O/sig_old.txt
echo "--- new ---"
grep -iE "Signer #1 certificate SHA-256|Signer #1 certificate DN|Verified using" $O/sig_new.txt
