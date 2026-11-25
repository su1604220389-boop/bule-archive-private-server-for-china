#!/bin/bash
set -u
V=/root/ba_work/verify
rm -rf $V; mkdir -p $V
SLIM=/mnt/c/Users/su/Desktop/大肥鱼项目/BAServer/work/ba/apk_patch/slim/slim.apk
NEW=/root/ba_work/exp_final.apk
LONG=res/layout/fragment_default_mobile_code_login.xml

cd $V
# the file that will be installed as res/Q9.xml :
unzip -p "$NEW" "$LONG" > Q9_new.axml
unzip -p "$SLIM" res/Q9.xml > Q9_orig.axml
echo "orig res/Q9.xml            = $(stat -c%s Q9_orig.axml) B"
echo "new $LONG = $(stat -c%s Q9_new.axml) B   <-- this becomes res/Q9.xml"

echo
echo "########## aapt dump xmltree : ORIGINAL res/Q9.xml ##########"
aapt dump xmltree "$SLIM" res/Q9.xml 2>/dev/null | sed -E 's/\(line=[0-9]+\)//g' | sed -E 's/[[:space:]]+$//' > t_orig.txt
wc -l t_orig.txt

echo "########## aapt dump xmltree : NEW $LONG ##########"
aapt dump xmltree "$NEW" "$LONG" 2>/dev/null | sed -E 's/\(line=[0-9]+\)//g' | sed -E 's/[[:space:]]+$//' > t_new.txt
wc -l t_new.txt

echo
echo "########## DIFF (orig -> new) ##########"
diff -u t_orig.txt t_new.txt > d.txt; rc=$?
echo "diff rc=$rc  changed-lines=$(grep -cE '^[+-][^+-]' d.txt || true)"
cat d.txt

echo
echo "########## referenced resource-id sets ##########"
grep -oE '=@0x[0-9a-f]+' t_orig.txt | sed 's/=//' | sort -u > ids_orig.txt
grep -oE '=@0x[0-9a-f]+' t_new.txt  | sed 's/=//' | sort -u > ids_new.txt
echo "counts: orig=$(wc -l < ids_orig.txt)  new=$(wc -l < ids_new.txt)"
echo "--- ids ONLY in NEW (must be empty) ---"
comm -13 ids_orig.txt ids_new.txt
echo "--- ids ONLY in ORIG (must be empty) ---"
comm -23 ids_orig.txt ids_new.txt

echo
echo "########## attribute name-ids used (android:*) ##########"
grep -oE 'android:[a-zA-Z_]+\(0x[0-9a-f]+\)' t_orig.txt | sort -u > a_orig.txt
grep -oE 'android:[a-zA-Z_]+\(0x[0-9a-f]+\)' t_new.txt  | sort -u > a_new.txt
echo "--- attr-name/attr-id pairs ONLY in NEW ---"
comm -13 a_orig.txt a_new.txt
echo "--- attr-name/attr-id pairs ONLY in ORIG ---"
comm -23 a_orig.txt a_new.txt
