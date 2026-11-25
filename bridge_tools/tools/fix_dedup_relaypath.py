#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BAPATCH-DEDUP v1 RELAYPATH: place the dedupe inside _rl2_relay_once (real request dict)."""
import hashlib
import io
import sys

SRC = '/www/wwwroot/bapatch/tools/account_auth_probe.py'
BASE_SHA = '3f51611c934f74e0e59d9a91443197b43836393a0980b3b24d8eef4dca788975'

HELPERS = '''
# >>> BAPATCH-DEDUP v1 RELAYPATH BEGIN >>>
def dedup_key_obj(name, req):
    if not isinstance(req, dict):
        return None
    for k in ('PurchaseOrderId', 'OrderNo', 'OrderId', 'ShopCashId'):
        v = req.get(k)
        if isinstance(v, (int, str)) and str(v) not in ('', '0'):
            return '%s|%s=%s' % (name, k, v)
    sk = req.get('SessionKey')
    if isinstance(sk, dict) and sk.get('AccountServerId'):
        return '%s|acct=%s' % (name, sk.get('AccountServerId'))
    return None


def dedup_fetch(key, name, rec):
    try:
        if not dedup_on() or name not in DEDUP_NAMES or not key:
            return None
        hit = dedup_lookup(key)
        if isinstance(rec, dict):
            rec['dedup_key'] = key
            rec['dedup_hit'] = hit is not None
        return hit
    except Exception:
        return None


def dedup_put(key, name, payload, rec):
    try:
        if not dedup_on() or name not in DEDUP_NAMES or not key or payload is None:
            return
        dedup_store(key, payload)
        if isinstance(rec, dict):
            rec['dedup_stored'] = True
    except Exception:
        pass
# <<< BAPATCH-DEDUP v1 RELAYPATH END <<<
'''

STORE_OLD = """    rec['relay2_account_id'] = aid
    # BAPATCH-1017RELAY v1c"""
STORE_NEW = """    rec['relay2_account_id'] = aid
    # BAPATCH-DEDUP v1 RELAYPATH: dup order -> replay cached response, never hit Shittim twice
    _dd_k = dedup_key_obj(name, req)
    _dd_hit = dedup_fetch(_dd_k, name, rec)
    if _dd_hit is not None:
        return _dd_hit
    # BAPATCH-1017RELAY v1c"""

PUT_OLD = """    rec['relay2_used'] = True
    rec['relay2_fallthrough'] = ''
    return out"""
PUT_NEW = """    rec['relay2_used'] = True
    rec['relay2_fallthrough'] = ''
    # BAPATCH-DEDUP v1 RELAYPATH: cache this response for the dedupe window
    dedup_put(_dd_k, name, out, rec)
    return out"""


def main():
    src = io.open(SRC, encoding='utf-8').read()
    cur = hashlib.sha256(src.encode('utf-8')).hexdigest()
    print('  baseline sha256 =', cur)
    if cur != BASE_SHA:
        print('  !! ABORT baseline mismatch')
        return 2
    if 'BAPATCH-DEDUP v1 RELAYPATH' in src:
        print('  already applied')
        return 0
    for nm, old in (('STORE', STORE_OLD), ('PUT', PUT_OLD)):
        c = src.count(old)
        print('  anchor %-6s occurrences = %d' % (nm, c))
        if c != 1:
            print('  !! ABORT')
            return 3
    mark = "# <<< BAPATCH-DEDUP v1 END <<<\n"
    if src.count(mark) != 1:
        print('  !! ABORT dedup end marker =', src.count(mark))
        return 4
    src = src.replace(mark, mark + HELPERS, 1)
    src = src.replace(STORE_OLD, STORE_NEW, 1)
    src = src.replace(PUT_OLD, PUT_NEW, 1)

    import ast
    try:
        ast.parse(src)
    except SyntaxError as e:
        print('  !! ABORT syntax:', e)
        return 5
    io.open(SRC, 'w', encoding='utf-8').write(src)
    out = src.encode('utf-8')
    print('  patched bytes  =', len(out))
    print('  patched sha256 =', hashlib.sha256(out).hexdigest())
    return 0


if __name__ == '__main__':
    sys.exit(main())
