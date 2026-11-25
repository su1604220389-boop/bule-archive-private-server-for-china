#!/bin/bash
set -u
D=/root/ba_work/dec0
echo "########## which classes own dp helpers (com/airi preferred) ##########"
for pat in 'dp2px(Landroid/content/Context;F)I' 'dip2px(Landroid/content/Context;F)I' 'dpToPx(I)F' 'dpToPx(F)F'; do
  echo "--- $pat ---"
  grep -rl --include='*.smali' -F ".method public static $pat" "$D/smali" "$D/smali_classes2" 2>/dev/null | head -10
  grep -rl --include='*.smali' -F ".method public static final $pat" "$D/smali" "$D/smali_classes2" 2>/dev/null | head -10
done
echo
echo "########## com/airi utility classes ##########"
ls "$D/smali/com/airi/common/utils/" 2>/dev/null
echo
echo "########## initView tail (last 60 lines) ##########"
F="$D/smali/com/airi/official/core/ui/fragment/DefaultMobileLoginFragment.smali"
awk 'NR>=495 && NR<=1240' "$F" | grep -n "" | awk -F: '$1>0' | sed -n '680,760p'
echo
echo "########## exact line numbers around initView end / onClick start ##########"
grep -n -E "^\.method|^\.end method" "$F" | sed -n '1,40p'
