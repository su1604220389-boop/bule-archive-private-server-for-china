#!/bin/bash
set -u
D=/root/ba_work/dec0
H="$D/smali/com/airi/official/core/http/net/HttpCallBack.smali"
echo "########## handleErrorCode tail (body lines 76-128) ##########"
awk '/^\.method private handleErrorCode\(ILjava\/lang\/String;\)V/,/^\.end method/' "$H" | sed -n '76,130p' | nl -ba -v76
echo
echo "########## exact file line numbers of .line 70..72 region ##########"
sed -n '28,45p' "$H" | nl -ba -v28
