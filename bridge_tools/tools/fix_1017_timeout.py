#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BAPATCH-1017RELAY v1c：LoginSync 转发超时放宽（Shittim 实测 ~9.7s）。"""
import hashlib, io, sys

SRC = '/www/wwwroot/bapatch/tools/account_auth_probe.py'
BASE_SHA = '9079436f4aabb8dacfe446040ebc05f543159ad396a9358391e6136a10d9a47c'

OLD = """    rec['relay2_account_id'] = aid
    try:
        code, raw = post(req, timeout=RL2_TIMEOUT)"""
NEW = """    rec['relay2_account_id'] = aid
    # BAPATCH-1017RELAY v1c: LoginSync 在 Shittim 侧实测 ~9.7s，8s 会超时 -> 单独放宽到 45s
    _to = 45 if (relay1017_on() and name == RELAY1017_NAME) else RL2_TIMEOUT
    rec['relay2_timeout'] = _to
    try:
        code, raw = post(req, timeout=_to)"""


def main():
    src = io.open(SRC, encoding='utf-8').read()
    cur = hashlib.sha256(src.encode('utf-8')).hexdigest()
    print('  baseline sha256 =', cur)
    if cur != BASE_SHA:
        print('  !! ABORT baseline mismatch')
        return 2
    if 'relay2_timeout' in src:
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
