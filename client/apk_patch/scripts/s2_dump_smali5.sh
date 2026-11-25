#!/bin/bash
set -u
D=/root/ba_work/dec0
echo "########## ExtendEditText: getBackground / setBackground usages ##########"
for f in "$D"/smali/com/airi/official/core/widget/ExtendEditText*.smali; do
  echo "===== $f ====="
  grep -n -E "getBackground|setBackground|GradientDrawable|Drawable;->" "$f" | head -40
done
echo
echo "########## ExtendEditText methods ##########"
grep -n "^\.method" "$D/smali/com/airi/official/core/widget/ExtendEditText.smali" 2>/dev/null | head -40
echo
echo "########## ErrorCodeInfo <init> body ##########"
awk '/^\.method public constructor <init>\(ILjava\/lang\/String;ZZ\)V/,/^\.end method/' "$D/smali/com/airi/official/core/http/net/ErrorCodeInfo.smali" | nl -ba | head -40
echo
echo "########## component3/component4 bodies ##########"
awk '/^\.method public final component3\(\)Z/,/^\.end method/' "$D/smali/com/airi/official/core/http/net/ErrorCodeInfo.smali" | nl -ba
awk '/^\.method public final component4\(\)Z/,/^\.end method/' "$D/smali/com/airi/official/core/http/net/ErrorCodeInfo.smali" | nl -ba
