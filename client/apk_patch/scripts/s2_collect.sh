#!/bin/bash
set -u
DST=/mnt/c/Users/su/Desktop/大肥鱼项目/BAServer/work/ba/apk_patch
mkdir -p "$DST/patched" "$DST/out/verify"
D=/root/ba_work/dec2
cp -f "$D/smali/com/airi/official/core/ui/fragment/DefaultMobileLoginFragment.smali" "$DST/patched/"
cp -f "$D/smali/com/airi/official/core/http/net/HttpCallBack.smali"                    "$DST/patched/"
cp -f "$D/smali/com/airi/common/utils/CommonUtil.smali"                               "$DST/patched/"
cp -f "$D/res/layout/fragment_default_mobile_code_login.xml"                           "$DST/patched/extend_edit_login_layout.xml"
cp -f /root/ba_work/verify/t_orig.txt /root/ba_work/verify/t_new.txt /root/ba_work/verify/d.txt "$DST/out/verify/" 2>/dev/null
cp -f /root/ba_work/verify/rt_diff.txt "$DST/out/verify/" 2>/dev/null
cp -f /root/ba_work/outcheck/sig_new.txt /root/ba_work/outcheck/badging_old.txt /root/ba_work/outcheck/badging_new.txt "$DST/out/verify/" 2>/dev/null
echo "=== patched/ ==="
ls -la "$DST/patched/"
echo "=== out/ ==="
ls -la "$DST/out/" | head -20
echo "=== out/verify/ ==="
ls "$DST/out/verify/"
