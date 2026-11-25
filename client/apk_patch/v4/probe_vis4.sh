#!/bin/bash
F=/root/ba_work/dec0/smali/com/airi/official/core/ui/fragment/DefaultMobileLoginFragment.smali
echo "== lines 552-600 =="
sed -n '552,600p' "$F"
echo
echo "== who owns loginHelper field / init =="
grep -n "loginHelper" "$F" || true
