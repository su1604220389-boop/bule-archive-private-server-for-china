#!/bin/bash
set -u
D=/root/ba_work/dec0
F="$D/smali/com/airi/official/core/ui/fragment/DefaultMobileLoginFragment.smali"
echo "########## initView tail 1095-1145 ##########"
sed -n '1095,1145p' "$F" | cat -n | awk '{printf "%d| %s\n", $1+1094, substr($0, index($0,$2))}'
echo
echo "########## onClick head 1143-1215 ##########"
sed -n '1143,1215p' "$F" | cat -n | awk '{printf "%d| %s\n", $1+1142, substr($0, index($0,$2))}'
echo
echo "########## DisplayUtils.dp2px ##########"
DU="$D/smali/com/airi/official/core/utils/DisplayUtils.smali"
grep -n "^\.method" "$DU"
echo "--- body ---"
awk '/^\.method public static dp2px\(Landroid\/content\/Context;F\)I/,/^\.end method/' "$DU"
