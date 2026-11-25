#!/bin/bash
# Raw evidence for the "does anyone index the root children?" question.
# Runs on the ORIGINAL apktool tree (dec0) -> same smali as v4/v5.
cd /root/ba_work/dec0 || exit 1
F=smali/com/airi/official/core/ui/fragment/DefaultMobileLoginFragment.smali

echo '### 1) which classes reference R.layout.fragment_default_mobile_code_login'
echo '$ grep -rn fragment_default_mobile_code_login smali smali_classes2'
grep -rn 'fragment_default_mobile_code_login' smali smali_classes2
echo

echo '### 2) the consumer class itself'
echo "\$ grep -n '^\.class\|^\.super' $F"
grep -n '^\.class' "$F"
grep -n '^\.super' "$F"
echo "\$ wc -l $F"
wc -l "$F"
echo

echo '### 3) getChildAt / getChildCount in the consumer  (0 hits = no index dependency)'
echo "\$ grep -c getChildAt $F"
grep -c 'getChildAt' "$F"
echo "\$ grep -c getChildCount $F"
grep -c 'getChildCount' "$F"
echo "\$ grep -n 'getChildAt\|getChildCount' $F   # empty output = 0 hits"
grep -n 'getChildAt\|getChildCount' "$F"
echo

echo '### 4) every view id the consumer touches (all id-based, no indices)'
echo "\$ grep -o 'R\$id;->[a-z_0-9]*' $F | sort -u"
grep -o 'R\$id;->[a-z_0-9]*' "$F" | sort -u
echo

echo '### 5) who instantiates the fragment (no subclass exists)'
echo '$ grep -rn "new-instance.*DefaultMobileLoginFragment;" smali smali_classes2'
grep -rn 'new-instance.*DefaultMobileLoginFragment;' smali smali_classes2
echo '$ grep -rn "extends.*DefaultMobileLoginFragment" smali smali_classes2   # empty = no subclass'
grep -rn 'extends.*DefaultMobileLoginFragment' smali smali_classes2
echo

echo '### 6) every getChildAt caller inside the app packages (none of them touch this layout)'
echo '$ grep -rn getChildAt smali/com/airi smali/com/RoamingStar smali_classes2/com | grep -v "okhttp\|unity3d\|androidx"'
grep -rn 'getChildAt' smali/com/airi smali/com/RoamingStar smali_classes2/com 2>/dev/null \
  | grep -v 'okhttp\|unity3d\|androidx'
