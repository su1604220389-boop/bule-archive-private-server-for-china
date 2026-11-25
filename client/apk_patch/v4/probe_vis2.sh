#!/bin/bash
# probe: read the visibility block of initView (read-only)
F=/root/ba_work/dec0/smali/com/airi/official/core/ui/fragment/DefaultMobileLoginFragment.smali
echo "== lines 600-700 =="
sed -n '600,700p' "$F"
