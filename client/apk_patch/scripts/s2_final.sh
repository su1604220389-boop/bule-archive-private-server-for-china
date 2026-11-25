#!/bin/bash
set -u
NEW=/mnt/c/Users/su/Desktop/大肥鱼项目/BAServer/work/ba/apk_patch/out/BlueArchive_cardlogin_v1.apk
OLD=/mnt/c/Users/su/Desktop/大肥鱼项目/BAServer/work/ba/apk_patch/backup/BA_noroot_prod_20261118_v1.apk

echo "########## artifacts ##########"
for f in "$OLD" "$NEW"; do
  echo "$f"
  echo "   size   = $(stat -c%s "$f")"
  echo "   sha256 = $(sha256sum "$f" | cut -d' ' -f1)"
done

echo
echo "########## shipped entry digests (from the new APK) ##########"
cd /tmp && rm -rf sh && mkdir sh && cd sh
unzip -o -q "$NEW" res/Q9.xml classes.dex
echo "res/Q9.xml  size=$(stat -c%s res/Q9.xml)  sha256=$(sha256sum res/Q9.xml | cut -d' ' -f1)"
echo "classes.dex size=$(stat -c%s classes.dex)   sha256=$(sha256sum classes.dex | cut -d' ' -f1)"
echo "--- compare with staging ---"
S=/mnt/c/Users/su/Desktop/大肥鱼项目/BAServer/work/ba/apk_patch/out/staging
echo "Q9.xml     staging sha256=$(sha256sum $S/Q9.xml | cut -d' ' -f1)"
echo "classes.dex staging sha256=$(sha256sum $S/classes.dex | cut -d' ' -f1)"

echo
echo "########## apksigner with min-sdk forced low (proves v1 JAR signature too) ##########"
apksigner verify --min-sdk-version 21 --print-certs "$NEW" 2>&1 | head -8
echo "rc=$?"

echo
echo "########## exact patch locations in the build tree (dec2) ##########"
D=/root/ba_work/dec2
F=$D/smali/com/airi/official/core/ui/fragment/DefaultMobileLoginFragment.smali
H=$D/smali/com/airi/official/core/http/net/HttpCallBack.smali
C=$D/smali/com/airi/common/utils/CommonUtil.smali
L=$D/res/layout/fragment_default_mobile_code_login.xml
echo "--- DefaultMobileLoginFragment.smali (total $(wc -l < $F) lines) ---"
grep -n "BPK-A :\|BPK-A END\|BPK-B :\|BPK-B END\|BPK-C :\|BPK-C END\|getChildAt(I)Landroid/view/View\|indexOfChild\|:bpk_sel_done\|:bpk_not_sel\|:bpk_sel_apply" "$F"
echo "--- HttpCallBack.smali (total $(wc -l < $H) lines) ---"
grep -n "BPK-D :\|BPK-D END\|bpk_keep_local" "$H"
echo "--- CommonUtil.smali ---"
grep -n 'const-string v0, "\^' "$C"
echo "--- layout xml (total $(wc -l < $L) lines) ---"
grep -n "RadioGroup\|RadioButton\|android:id=\"@id/et_phone\"\|android:id=\"@id/et_phone_code\"\|android:id=\"@id/layout_phone_code\"\|android:text=\"@string/login\"\|<LinearLayout android:gravity=\"center_horizontal\"" "$L" | cut -c1-150

echo
echo "########## root LinearLayout child indentation proof ##########"
awk 'NR>=1 && /^<LinearLayout/ {inroot=1; next} inroot && /^<\/LinearLayout>$/ {exit} inroot {print NR": "substr($0,1,80)}' "$L" | grep -E "^[0-9]+: {4}<" | head -10
