#!/bin/bash
# Collect the AXML-level evidence used by SELFTEST_v5.md.
OUT=/root/ba_work/xmltree_evidence.txt
{
  echo '### v4 (throw-away build apk) -- root children, aapt dump xmltree'
  echo '$ aapt dump xmltree v4_layout_build.apk res/layout/fragment_default_mobile_code_login.xml | grep "^      E: "'
  grep -n '^      E: ' /root/ba_work/xmltree_v4.txt
  echo
  echo '### v5 (throw-away build apk) -- root children'
  echo '$ aapt dump xmltree v5_layout_build.apk res/layout/fragment_default_mobile_code_login.xml | grep "^      E: "'
  grep -n '^      E: ' /root/ba_work/xmltree_v5.txt
  echo
  echo '### v5 -- the new RadioGroup block, raw attributes as compiled into the AXML'
  echo '$ aapt dump xmltree v5_layout_build.apk res/layout/fragment_default_mobile_code_login.xml | sed -n "47,78p"'
  sed -n '47,78p' /root/ba_work/xmltree_v5.txt
} > "$OUT" 2>&1
cp "$OUT" '/mnt/c/Users/su/Desktop/大肥鱼项目/BAServer/work/ba/apk_patch/v5/ev_xmltree.txt'
cp /root/ba_work/v5_make_layout.log '/mnt/c/Users/su/Desktop/大肥鱼项目/BAServer/work/ba/apk_patch/v5/make_layout_v5.log'
echo OK
