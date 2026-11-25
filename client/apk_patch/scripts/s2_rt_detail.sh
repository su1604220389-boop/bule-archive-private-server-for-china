#!/bin/bash
set -u
R=/root/ba_work/rt/smali
echo "########## handleErrorCode: where does the skip-label land? ##########"
awk '/^\.method private handleErrorCode/,/^\.end method/' "$R/com/airi/official/core/http/net/HttpCallBack.smali" | sed -n '20,50p'
echo
echo "########## isChinaPhoneLegal after round-trip ##########"
awk '/^\.method public static isChinaPhoneLegal/,/^\.end method/' "$R/com/airi/common/utils/CommonUtil.smali" | head -12
echo
echo "########## initView tail (BPK-C) after round-trip ##########"
awk '/^\.method protected initView/,/^\.end method/' "$R/com/airi/official/core/ui/fragment/DefaultMobileLoginFragment.smali" | tail -22
echo
echo "########## A3 radio wiring after round-trip ##########"
awk '/^\.method protected initView/,/^\.line 96/' "$R/com/airi/official/core/ui/fragment/DefaultMobileLoginFragment.smali" | sed -n '55,120p'
