#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_cn_parity.py -- 字典无关：用 UTF-16LE 高字节恒 0 的奇偶分解硬破第二层字段名。

    key_ct[奇] = k[奇]                       (名字是 ASCII => 高字节 0)
    key_ct[偶] = N[i] XOR k[(2i) mod 8]
    => 逐相位枚举 k[0],k[2],k[4],k[6]，拼出 N，用 create_key(N) == k 判定。

对 idx2(L=10)/idx3(L=11) 我们会同时看到已知答案 ServerName / VersionCode，
这即是方法的自验证；同一轮里的新命中即为 idx4/idx5 的真名。
"""
import base64
import itertools
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from CRYPTO_MT import create_key  # noqa: E402

OUTER = '_extract_cn/GameMainConfig_assets_bin_Data_e37c46fea17834108a4756797197d05a.json'
IDENT = set('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_')
REF = '1b232806ad72c257'


def b64d(s):
    return base64.b64decode(s + '=' * (-len(s) % 4))


def cyc8(k, n):
    return (k * (n // 8 + 2))[:n]


def crack(key_ct, label, strict=True):
    L = len(key_ct) // 2
    k = [0] * 8
    for odd in (1, 3, 5, 7):
        if odd < len(key_ct):
            k[odd] = key_ct[odd]
    allowed = []
    for p in range(4):
        idx = list(range(p, L, 4))
        opts = [v for v in range(256) if all(chr(key_ct[2 * i] ^ v) in IDENT for i in idx)]
        allowed.append(opts)
    total = 1
    for a in allowed:
        total *= len(a)
    print('\n[%s] L=%d phases=%s combos=%d' % (label, L, [len(a) for a in allowed], total), flush=True)

    hits = []
    t0 = time.time()
    start = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    end = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] != '-' else total
    n = 0
    for c0, c2, c4, c6 in itertools.product(*allowed):
        if n < start:
            n += 1
            continue
        if n >= end:
            break
        n += 1
        kb = bytes((c0, k[1], c2, k[3], c4, k[5], c6, k[7]))
        name = ''.join(chr(key_ct[2 * i] ^ kb[(2 * i) % 8]) for i in range(L))
        if not name[:1].isalpha():
            continue
        if strict and not (name.isalpha() or name.isalnum()):
            continue
        if create_key(name) == kb:
            hits.append(name)
            print('  >>> HIT %r  k=%s  (%.0fs)' % (name, kb.hex(), time.time() - t0), flush=True)
    print('  [%s] range=[%d,%d) done %.1fs hits=%s' % (label, start, end, time.time() - t0, hits), flush=True)
    return hits


def main():
    if create_key('GameMainConfig').hex() != REF:
        print('selfcheck FAIL')
        return
    js = json.loads(Path(OUTER).read_text(encoding='utf-8'))
    pairs = [(b64d(k), b64d(v)) for k, v in js.items()]
    want = [int(x) for x in sys.argv[1:]] or [5, 11, 3, 4]
    cfg = {}
    for i in want:
        kct, vct = pairs[i]
        for n in crack(kct, 'idx%d' % i, strict=False):
            k = create_key(n)
            val = bytes(a ^ b for a, b in zip(vct, cyc8(k, len(vct)))).decode('utf-16-le') if vct else ''
            cfg[n] = val
            print('     NAME=%r VALUE=%r' % (n, val), flush=True)
    print('\n=== 本轮还原 ===')
    for k, v in cfg.items():
        print('  %-24s = %r' % (k, v))


if __name__ == '__main__':
    main()
