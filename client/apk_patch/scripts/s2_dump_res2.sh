#!/bin/bash
set -u
D=/root/ba_work/dec0
for f in login_btn_normal login_btn_pressed disagree; do
  echo "----- drawable/$f -----"
  if [ -f "$D/res/drawable/$f.xml" ]; then cat "$D/res/drawable/$f.xml"; else echo "(no xml; listing variants)"; ls -la "$D/res"/*/"$f".* 2>/dev/null; fi
done
echo
echo "===== colors of interest ====="
for c in et_stroke c_ffe656 onekey_solid onekey_stroke c_b9b9b9 c_eaeaea radius_common_dialog radius_common_bg width_stroke_onekey; do
  e=$(grep -hoP "(?<=<color name=\"$c\">)[^<]*" "$D/res/values/"*.xml 2>/dev/null | head -1)
  dd=$(grep -hoP "(?<=<dimen name=\"$c\">)[^<]*" "$D/res/values/"*.xml 2>/dev/null | head -1)
  echo "$c : color=[${e:-none}] dimen=[${dd:-none}]"
done
echo
echo "===== et_stroke / etc follow-ups ====="
for c in c_f2f2f2 c_ededed c_ffffff c_1e88e5; do
  e=$(grep -hoP "(?<=<color name=\"$c\">)[^<]*" "$D/res/values/"*.xml 2>/dev/null | head -1)
  echo "$c = [${e:-none}]"
done
echo
echo "===== does values/colors.xml have many entries? ====="
ls -la "$D/res/values/" | head
echo "--- names containing 'login' or 'blue' ---"
grep -ohP '(?<=<color name=")[^"]*' "$D/res/values/colors.xml" | grep -iE "blue|main|primary|btn|login|theme" | head -40
