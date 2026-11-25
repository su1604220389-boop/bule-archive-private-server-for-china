#!/bin/bash
set -u
D=/root/ba_work/verify/rt_diff.txt
echo "########## total diff hunks / changed lines ##########"
grep -c '^diff -r' $D || true
echo "--- changed lines ('<' or '>') ---"
grep -cE '^[<>]' $D || true
echo
echo "########## classify every changed line ##########"
grep -E '^[<>]' $D | sed -E 's/^[<>] *//' | sed -E 's/= (false|true|null|0x[0-9a-f]+|-?[0-9]+).*$/= <VAL>/' | cut -c1-40 | sort | uniq -c | sort -rn | head -20
echo
echo "########## any changed line that is NOT a '.field' line? ##########"
grep -E '^[<>]' $D | grep -vE '^[<>][[:space:]]*\.field' > /root/ba_work/verify/rt_nonfield.txt || true
echo "non-.field changed lines = $(wc -l < /root/ba_work/verify/rt_nonfield.txt)"
cat /root/ba_work/verify/rt_nonfield.txt | head -40
echo
echo "########## our 4 patched files: any diff at all? ##########"
for f in com/airi/official/core/ui/fragment/DefaultMobileLoginFragment.smali \
         com/airi/official/core/http/net/HttpCallBack.smali \
         com/airi/common/utils/CommonUtil.smali \
         com/airi/official/core/utils/DisplayUtils.smali; do
  echo "--- $f ---"
  if diff -q /root/ba_work/dec2/smali/$f /root/ba_work/rt/smali/$f >/dev/null 2>&1; then
    echo "IDENTICAL after dex round-trip"
  else
    diff /root/ba_work/dec2/smali/$f /root/ba_work/rt/smali/$f | head -10
  fi
done
echo
echo "########## the patched methods as baksmali read them back ##########"
echo "--- initView head (BPK-A) ---"
awk '/^\.method protected initView/,/\.line 96/' /root/ba_work/rt/smali/com/airi/official/core/ui/fragment/DefaultMobileLoginFragment.smali | head -20
echo "--- onClick head (BPK-B) ---"
awk '/^\.method public onClick/,/\.line 331/' /root/ba_work/rt/smali/com/airi/official/core/ui/fragment/DefaultMobileLoginFragment.smali | head -30
echo "--- handleErrorCode (BPK-D) ---"
awk '/^\.method private handleErrorCode/,/\.line 72/' /root/ba_work/rt/smali/com/airi/official/core/http/net/HttpCallBack.smali | tail -30
echo "--- isChinaPhoneLegal regex ---"
grep -A1 -B1 'const-string v0, "' /root/ba_work/rt/smali/com/airi/common/utils/CommonUtil.smali | head -6
