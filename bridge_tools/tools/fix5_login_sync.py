#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FIX-5：让 1017 (Account_LoginSync) 走 relay2 → Shittim 真实现。

两处同变量改动（同一个目的：放 1017 过去）：
  1) RL2_HANDLED 去掉 1017
  2) RL2_SKIP_NAMES 去掉 'Account_LoginSync'
不动其它元素、不动开关、不动任何函数体。
"""
import hashlib, io, sys

SRC = '/www/wwwroot/bapatch/tools/account_auth_probe.py'
BASE_SHA = '128c6ba9bec71590a6443610a3814cfb8d56f0a03b973241e54dabf1bde405d4'

OLD_HANDLED = ("RL2_HANDLED = frozenset((1002, 1014, 1000, 1009, 1012, 1019, 2001, 3, 1017,   # FIX-2: 1005 已移出，改走转发\n"
               "                         24000, 26000, 4000, 90004))")
NEW_HANDLED = ("RL2_HANDLED = frozenset((1002, 1014, 1000, 1009, 1012, 1019, 2001, 3,   # FIX-2: 1005 移出; FIX-5: 1017 移出\n"
               "                         24000, 26000, 4000, 90004))")

OLD_SKIP = ("RL2_SKIP_NAMES = frozenset(('Account_CheckNexon', 'Account_Auth', 'Account_Auth2',\n"
            "                            'Account_LoginSync', 'Account_Nickname', 'Account_CallName'))")
NEW_SKIP = ("RL2_SKIP_NAMES = frozenset(('Account_CheckNexon', 'Account_Auth', 'Account_Auth2',   # FIX-5: LoginSync 移出\n"
            "                            'Account_Nickname', 'Account_CallName'))")


def main():
    src = io.open(SRC, encoding='utf-8').read()
    cur = hashlib.sha256(src.encode('utf-8')).hexdigest()
    print('  baseline sha256 =', cur)
    if cur != BASE_SHA:
        print('  !! ABORT baseline mismatch')
        return 2
    if 'FIX-5: LoginSync 移出' in src:
        print('  already applied')
        return 0
    for nm, old in (('RL2_HANDLED', OLD_HANDLED), ('RL2_SKIP_NAMES', OLD_SKIP)):
        n = src.count(old)
        print('  anchor %-14s occurrences = %d' % (nm, n))
        if n != 1:
            print('  !! ABORT anchor not unique')
            return 3
    src = src.replace(OLD_HANDLED, NEW_HANDLED, 1).replace(OLD_SKIP, NEW_SKIP, 1)
    import ast
    try:
        ast.parse(src)
    except SyntaxError as e:
        print('  !! ABORT syntax:', e)
        return 4
    io.open(SRC, 'w', encoding='utf-8').write(src)
    out = src.encode('utf-8')
    print('  patched bytes  =', len(out))
    print('  patched sha256 =', hashlib.sha256(out).hexdigest())
    return 0


if __name__ == '__main__':
    sys.exit(main())
