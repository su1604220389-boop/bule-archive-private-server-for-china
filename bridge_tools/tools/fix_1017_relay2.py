#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BAPATCH-1017RELAY v1b：让开关打开时**绕过 RL2_HANDLED**（1019 在排除表里）。"""
import hashlib, io, sys

SRC = '/www/wwwroot/bapatch/tools/account_auth_probe.py'
BASE_SHA = 'bbbed26f5b4f8827a988f90f0fd462cc3e910cd469ed22d669171c6dc4703c47'

OLD = """    if num in RL2_HANDLED:
        # 1002/1014/3/1005/1017/24000/26000/4000/90004 … 有真生成器或专分支：绝不抢
        rec['relay2_fallthrough'] = 'handled-%d' % num
        return None"""
NEW = """    if num in RL2_HANDLED:
        # BAPATCH-1017RELAY v1b: LoginSync 开关打开时绕过排除表（1019 在 RL2_HANDLED 里）
        if relay1017_on() and name == RELAY1017_NAME:
            rec['relay1017_handled_bypass'] = True
        else:
            # 1002/1014/3/1005/1017/24000/26000/4000/90004 … 有真生成器或专分支：绝不抢
            rec['relay2_fallthrough'] = 'handled-%d' % num
            return None"""


def main():
    src = io.open(SRC, encoding='utf-8').read()
    cur = hashlib.sha256(src.encode('utf-8')).hexdigest()
    print('  baseline sha256 =', cur)
    if cur != BASE_SHA:
        print('  !! ABORT baseline mismatch')
        return 2
    if 'relay1017_handled_bypass' in src:
        print('  already applied')
        return 0
    print('  anchor occurrences =', src.count(OLD))
    if src.count(OLD) != 1:
        print('  !! ABORT')
        return 3
    src = src.replace(OLD, NEW, 1)
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
