#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FIX-2：从 RL2_HANDLED 里去掉 1005（唯一改动）。"""
import hashlib, io, sys

SRC = '/www/wwwroot/bapatch/tools/account_auth_probe.py'
BASE_SHA = '5dd609a0abe35479451868b56ac00bc283d74e334b047f8f5c673b5acf47f358'

OLD = ("RL2_HANDLED = frozenset((1002, 1014, 1000, 1009, 1012, 1019, 2001, 3, 1005, 1017,\n"
       "                         24000, 26000, 4000, 90004))")
NEW = ("RL2_HANDLED = frozenset((1002, 1014, 1000, 1009, 1012, 1019, 2001, 3, 1017,   # FIX-2: 1005 已移出，改走转发\n"
       "                         24000, 26000, 4000, 90004))")


def main():
    src = io.open(SRC, encoding='utf-8').read()
    cur = hashlib.sha256(src.encode('utf-8')).hexdigest()
    print('  baseline sha256 =', cur)
    if cur != BASE_SHA:
        print('  !! ABORT: baseline mismatch')
        return 2
    n = src.count(OLD)
    print('  OLD block occurrences =', n)
    if n != 1:
        print('  !! ABORT: expected exactly 1')
        return 3
    if 'FIX-2: 1005' in src:
        print('  already applied')
        return 0
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
