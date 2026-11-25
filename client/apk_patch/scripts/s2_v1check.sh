#!/bin/bash
set -u
NEW=/mnt/c/Users/su/Desktop/大肥鱼项目/BAServer/work/ba/apk_patch/out/BlueArchive_cardlogin_v1.apk
OLD=/mnt/c/Users/su/Desktop/大肥鱼项目/BAServer/work/ba/apk_patch/backup/BA_noroot_prod_20261118_v1.apk

echo "################ BASELINE: apksigner verify --min-sdk-version 21 ################"
apksigner verify --min-sdk-version 21 "$OLD" 2>&1 | head -12
echo "---- (count of errors) ----"
apksigner verify --min-sdk-version 21 "$OLD" 2>&1 | grep -c "^ERROR" || true

echo
echo "################ NEW: apksigner verify --min-sdk-version 21 ################"
apksigner verify --min-sdk-version 21 "$NEW" 2>&1 | head -12
echo "---- (count of errors) ----"
apksigner verify --min-sdk-version 21 "$NEW" 2>&1 | grep -c "^ERROR" || true

echo
echo "################ NEW: apksigner verify (default = minSdk from APK = 24) ################"
apksigner verify "$NEW" 2>&1 | head -6
echo "rc=$?"
echo "################ BASELINE: apksigner verify (default) ################"
apksigner verify "$OLD" 2>&1 | head -6
echo "rc=$?"

echo
echo "################ MANIFEST.MF: is resources.arsc / classes.dex listed? ################"
unzip -p "$NEW" META-INF/MANIFEST.MF | tr -d '\r' > /tmp/mf.txt
echo "Name sections = $(grep -c '^Name:' /tmp/mf.txt)"
for n in "resources.arsc" "classes.dex" "res/Q9.xml" "AndroidManifest.xml" "lib/arm64-v8a/libVorbisPlugin.so"; do
  printf '  %-40s listed=%s\n' "$n" "$(grep -cxF "Name: $n" /tmp/mf.txt)"
done
echo "--- first 8 lines of MANIFEST.MF ---"
head -8 /tmp/mf.txt
echo "--- the res/Q9.xml section ---"
grep -A2 -xF "Name: res/Q9.xml" /tmp/mf.txt
