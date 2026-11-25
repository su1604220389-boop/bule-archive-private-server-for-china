#!/bin/bash
# Persist the decode tree into the project, and dump the smali we need.
W=/root/ba_work
DST=/mnt/c/Users/su/Desktop/大肥鱼项目/BAServer/work/ba/apk_patch
rm -rf "$DST/decode"
cp -a $W/dec0 "$DST/decode"
echo "copied decode -> $DST/decode"
du -sh "$DST/decode"
ls "$DST/decode"

echo ""
echo "############ DefaultMobileLoginFragment class decl ############"
head -30 "$DST/decode/smali/com/airi/official/core/ui/fragment/DefaultMobileLoginFragment.smali"
echo ""
echo "############ method signatures ############"
grep -n "^.method\|^.field" "$DST/decode/smali/com/airi/official/core/ui/fragment/DefaultMobileLoginFragment.smali" | head -60

echo ""
echo "############ HttpCallBack handleErrorCode ############"
F=$DST/decode/smali/com/airi/official/core/http/net/HttpCallBack.smali
ls -l $F
sed -n '1,20p' $F
echo "--- handleErrorCode method ---"
awk '/^\.method.*handleErrorCode/,/^\.end method/' $F

echo ""
echo "############ ExtendEditText class + init ############"
EX=$DST/decode/smali/com/airi/official/core/widget/ExtendEditText.smali
head -25 $EX
echo "--- filter-related lines ---"
grep -n "Filter\|filters\|InputType\|inputType" $EX | head -30

echo "############ DONE ############"
