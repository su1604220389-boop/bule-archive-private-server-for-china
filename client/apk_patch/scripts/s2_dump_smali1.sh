#!/bin/bash
set -u
D=/root/ba_work/dec0
echo "########## dp2px / dip2px helpers in smali ##########"
grep -rl -E "dip2px|dp2px|dpToPx|dipToPx|getDimensionPixelSize" "$D/smali" "$D/smali_classes2" 2>/dev/null | head -20
echo "--- method sigs ---"
grep -rh -E "\.method.*(dip2px|dp2px|dpToPx|dipToPx)" "$D/smali" "$D/smali_classes2" 2>/dev/null | sort -u | head -20
echo
echo "########## DefaultMobileLoginFragment ##########"
F="$D/smali/com/airi/official/core/ui/fragment/DefaultMobileLoginFragment.smali"
ls -la "$F"
echo "--- fields ---"
grep -n "^\.field" "$F"
echo "--- class decl ---"
sed -n '1,12p' "$F"
echo
echo "########## initView: first 40 lines ##########"
awk 'NR>=1 && /^\.method/ && tolower($0) ~ /initview/ {print NR": "$0; f=1; next} f&&/^\.end method/{print NR": "$0; exit} f{print NR": "$0}' "$F" | head -50
