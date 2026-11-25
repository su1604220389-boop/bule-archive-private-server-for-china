#!/bin/bash
set -u
D=/root/ba_work/dec0
echo "===== radius/bt colors (raw grep across all values) ====="
for n in radius_common_dialog radius_common_bg bt_normal bt_pressed width_stroke_onekey color_primary res_theme_color; do
  echo "--- $n ---"
  grep -rh -B0 -A0 -P "name=\"$n\"" "$D"/res/values*/*.xml 2>/dev/null | sed 's/^[[:space:]]*//' | head -6
done
echo
echo "===== what tag holds radius_common_bg ====="
grep -rlP 'name="radius_common_bg"' "$D"/res/values*/*.xml 2>/dev/null
grep -rhP 'radius_common_bg' "$D"/res/values/*.xml 2>/dev/null | head -5
