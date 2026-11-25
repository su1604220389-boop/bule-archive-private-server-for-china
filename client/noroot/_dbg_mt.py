#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_dbg_mt.py -- 定位 CRYPTO_MT.MT 的 IndexError 触发条件。"""
import itertools
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from CRYPTO_MT import MT, create_key  # noqa: E402

print('MT(12345).mt len =', len(MT(12345).mt))

key_ct = bytes.fromhex('f0039a42f2c2e708f7038442efc2f808d1039842fac2fb08')
k = [None] * 8
for o in (1, 3, 5, 7):
    k[o] = key_ct[o]
IDENT = set('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_')

allowed = []
for p in range(4):
    idx = list(range(p, 12, 4))
    opts = [v for v in range(256) if all(chr(key_ct[2 * i] ^ v) in IDENT for i in idx)]
    allowed.append(opts)
print('cand sizes', [len(a) for a in allowed])

ok = bad = 0
first_bad = None
names_hit = []
for c0, c2, c4, c6 in itertools.product(*allowed):
    kk = list(k)
    kk[0], kk[2], kk[4], kk[6] = c0, c2, c4, c6
    name = bytes(key_ct[2 * i] ^ kk[(2 * i) % 8] for i in range(12)).decode('ascii')
    try:
        if create_key(name).hex() == bytes(kk).hex():
            names_hit.append((name, kk))
        ok += 1
    except Exception as e:
        bad += 1
        if first_bad is None:
            first_bad = (name, repr(e))
print('ok', ok, 'bad', bad)
if first_bad:
    print('first bad:', first_bad)
print('HITS:', [(n, bytes(kk).hex()) for n, kk in names_hit])
