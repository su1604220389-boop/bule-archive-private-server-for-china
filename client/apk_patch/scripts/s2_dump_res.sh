#!/bin/bash
# STEP2: dump the drawables/colors the login layout actually uses, before designing
set -u
D=/root/ba_work/dec0
echo "===== drawables ====="
for f in login_bg_fragment login_edit_bg_fragment login_btn_selector login_one_btn_selector shape_bg_taptap_login back close ic_login_logo disagree; do
  echo "----- $f -----"
  for ext in xml png webp jpg 9.png; do
    if [ -f "$D/res/drawable/$f.$ext" ]; then
      echo "[found drawable/$f.$ext $(stat -c%s "$D/res/drawable/$f.$ext") B]"
      case "$ext" in
        xml) cat "$D/res/drawable/$f.$ext" ;;
        *) echo "(binary)" ;;
      esac
    fi
  done
done
echo
echo "===== which res/ dir types exist ====="
ls "$D/res" | tr '\n' ' '; echo
echo
echo "===== colors referenced by layout ====="
for c in c_6a6a6a c_000000 disable_text divider_common bt_text c_a3a3a3; do
  echo "--- $c ---"
  grep -rhoP "(?<=<color name=\"$c\">)[^<]*" "$D/res/values/colors.xml" 2>/dev/null || echo "(not in colors.xml)"
done
echo
echo "===== dimens used by layout ====="
for d in dp328 dp24 dp12 dp7 dp4 dp1 dp2 dp5 dp6 dp8 dp14 dp16 dp18 dp20 dp26 dp28 dp32 dp40 dp60 dp66 dp120 dp140; do
  v=$(grep -hoP "(?<=<dimen name=\"$d\">)[^<]*" "$D/res/values/"*.xml 2>/dev/null | head -1)
  echo "$d = ${v:-MISSING}"
done
echo
echo "===== sp used ====="
for d in sp12 sp14 sp16; do
  v=$(grep -hoP "(?<=<dimen name=\"$d\">)[^<]*" "$D/res/values/"*.xml 2>/dev/null | head -1)
  echo "$d = ${v:-MISSING}"
done
echo
echo "===== PNG/9-patch? ====="
ls -la "$D/res" | grep -E "drawable" | head
