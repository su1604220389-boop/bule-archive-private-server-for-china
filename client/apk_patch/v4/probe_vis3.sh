#!/bin/bash
F=/root/ba_work/dec0/smali/com/airi/official/core/ui/fragment/DefaultMobileLoginFragment.smali
echo "== lines 700-850 =="
sed -n '700,850p' "$F"
echo
echo "== any mention of layout_phone_code / get_phone_code fields =="
grep -n "layout_phone_code\|get_phone_code\|etCode" "$F" || true
