#!/bin/bash
W=/root/ba_work
SLIM=/mnt/c/Users/su/Desktop/大肥鱼项目/BAServer/work/ba/apk_patch/slim/slim.apk
REB=$W/slim_rebuild.apk
OUT=$W/cmp2
rm -rf $OUT; mkdir -p $OUT

echo "############ TEST 1: is apktool-rebuilt Q9 AXML a drop-in replacement? ############"
echo "--- attribute-by-attribute diff of the SAME layout ---"
aapt dump xmltree "$SLIM" res/Q9.xml                        > $OUT/a.txt 2>&1
aapt dump xmltree "$REB"  res/layout/fragment_default_mobile_code_login.xml > $OUT/b.txt 2>&1
echo "orig lines: $(wc -l < $OUT/a.txt)   reb lines: $(wc -l < $OUT/b.txt)"
sed -e 's/(line=[0-9]*)//' $OUT/a.txt > $OUT/a2.txt
sed -e 's/(line=[0-9]*)//' $OUT/b.txt > $OUT/b2.txt
diff $OUT/a2.txt $OUT/b2.txt > $OUT/q9_norm.diff 2>&1
echo "normalized diff lines: $(wc -l < $OUT/q9_norm.diff)"
head -40 $OUT/q9_norm.diff

echo ""
echo "############ TEST 2: do any original res XMLs carry TYPE_STRING values? ############"
for f in Q9.xml nW.xml EQ.xml o4.xml; do
  echo "--- $f TYPE_STRING(type 0x03) count:"
  aapt dump xmltree "$SLIM" res/$f 2>/dev/null | grep -c "type 0x03" || true
done
echo "--- any Raw: literals anywhere in res/ ? (scan a sample) ---"
git -C / root 2>/dev/null; true
aapt dump xmltree "$SLIM" res/RT.xml 2>/dev/null | head -20

echo ""
echo "############ TEST 3: rebuilt APK arsc - did aapt2 add a string resource for literals? ############"
aapt dump --values resources "$REB" 2>/dev/null | grep -c "spec resource" || true

echo ""
echo "############ TEST 4: ExtendEditText - does it add its own LengthFilter? ############"
ls $W/dec0/smali/com/airi/official/core/widget/ 2>/dev/null | head -40
echo "--- ExtendEditText.smali grep ---"
grep -n "LengthFilter\|setFilters\|maxLength\|InputFilter" $W/dec0/smali/com/airi/official/core/widget/ExtendEditText*.smali 2>/dev/null | head -40

echo ""
echo "############ TEST 5: isPhoneLegal / isChinaPhoneLegal smali ############"
grep -rn "isChinaPhoneLegal\|isPhoneLegal" $W/dec0/smali/com/airi/common/utils/CommonUtil.smali 2>/dev/null | head -20
echo "--- regex const-string in CommonUtil ---"
grep -n "const-string" $W/dec0/smali/com/airi/common/utils/CommonUtil.smali 2>/dev/null | grep -n '\^1\|\\\\d' | head -10

echo ""
echo "############ TEST 6: DefaultMobileLoginFragment - class decl + initView + onClick ############"
find $W/dec0/smali* -name 'DefaultMobileLoginFragment.smali' 2>/dev/null
echo "=== DONE ==="
