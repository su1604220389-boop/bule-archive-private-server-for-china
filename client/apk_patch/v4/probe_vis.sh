#!/bin/bash
# probe: visibility toggles inside the login fragment (read-only)
F=/root/ba_work/dec0/smali/com/airi/official/core/ui/fragment/DefaultMobileLoginFragment.smali
echo "== setVisibility count =="
grep -c setVisibility "$F"
echo "== setVisibility lines =="
grep -n setVisibility "$F" || true
echo "== isHideAllBottomTap call sites =="
grep -n isHideAllBottomTap "$F" || true
echo "== context of those call sites =="
for N in $(grep -n isHideAllBottomTap "$F" | cut -d: -f1); do
  echo "--- around line $N ---"
  sed -n "$((N-6)),$((N+22))p" "$F"
done
