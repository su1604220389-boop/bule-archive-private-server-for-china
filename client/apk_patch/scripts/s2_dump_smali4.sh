#!/bin/bash
set -u
D=/root/ba_work/dec0
F="$D/smali/com/airi/official/core/ui/fragment/DefaultMobileLoginFragment.smali"
echo "########## any setHint on et_phone anywhere in fragment? ##########"
grep -n "setHint" "$F" || echo "(none)"
echo "--- setHint across com/airi that mention et_phone (context) ---"
grep -rn "setHint" "$D/smali/com/airi/official/core/" 2>/dev/null | head -20
echo
echo "########## R\$id has layout_phone_code / et_phone? ##########"
R="$D/smali/com/airi/official/core/R\$id.smali"
ls -la "$R"
grep -nE "layout_phone_code|(= et_phone:|et_phone:I|\"et_phone\")" "$R" | head
echo
echo "########## HttpCallBack.handleErrorCode ##########"
H="$D/smali/com/airi/official/core/http/net/HttpCallBack.smali"
grep -n "^\.method" "$H"
echo "--- body ---"
awk '/^\.method private handleErrorCode\(ILjava\/lang\/String;\)V/,/^\.end method/' "$H" | nl -ba | head -80
echo
echo "########## ErrorCodeInfo ctor ##########"
E="$D/smali/com/airi/official/core/http/net/ErrorCodeInfo.smali"
grep -n "^\.method\|^\.field" "$E"
echo
echo "########## CommonUtil.isChinaPhoneLegal ##########"
C="$D/smali/com/airi/common/utils/CommonUtil.smali"
awk '/^\.method.*isChinaPhoneLegal/,/^\.end method/' "$C" | nl -ba
echo "--- grep the regex line ---"
grep -n '1\\\\d{10}\|\^1' "$C" | head
