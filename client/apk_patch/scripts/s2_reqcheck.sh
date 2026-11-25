#!/bin/bash
set -u
A=/root/ba_work/dec0/smali/com/airi/official/core/ui/fragment/DefaultMobileLoginFragment.smali
B=/root/ba_work/rt/smali/com/airi/official/core/ui/fragment/DefaultMobileLoginFragment.smali
echo "########## handleLoginLink(Z)V : original (dec0) vs shipped (rt/baksmali of new dex) ##########"
awk '/^\.method public handleLoginLink\(Z\)V/,/^\.end method/' "$A" > /tmp/h1.txt
awk '/^\.method public handleLoginLink\(Z\)V/,/^\.end method/' "$B" > /tmp/h2.txt
echo "orig lines=$(wc -l < /tmp/h1.txt)  shipped lines=$(wc -l < /tmp/h2.txt)"
diff /tmp/h1.txt /tmp/h2.txt > /tmp/hd.txt; echo "diff rc=$?  lines=$(wc -l < /tmp/hd.txt)"
cat /tmp/hd.txt
echo
echo "--- does it still build LoginReq{type=mobile, openid=card, token=code} ? ---"
grep -nE "LoginReq|const-string .*(mobile|openid|OpenID)|->setType|->setOpenId|->setToken" /tmp/h2.txt | head -20
echo
echo "########## whole-file line count check on the shipped fragment ##########"
echo "dec0(orig)  = $(wc -l < $A)"
echo "dec2(patch) = $(wc -l < /root/ba_work/dec2/smali/com/airi/official/core/ui/fragment/DefaultMobileLoginFragment.smali)"
echo "rt(shipped) = $(wc -l < $B)"
echo "expected    = $(wc -l < $A) + blockA(156) + blockB(33) + blockC(8) + 3 separators = $(( $(wc -l < $A) + 156 + 33 + 8 ))"
