#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_cn_crack3.py -- 自包含版：奇偶分解硬破第二层字段名（不 import 其它模块）。

已知（已由词表+自密钥双重验证）:
  idx0 = SkipTutorial(12)   idx1 = ServerInfoDataUrl(17)
  idx2 = ServerName(10)     idx3 = VersionCode(11)
本脚本对全部 6 个目标重跑奇偶分解以作独立复核，并硬破 idx4(10) / idx5(9)。
"""
import base64
import itertools
import json
from pathlib import Path

M = 0xFFFFFFFF
OUTER = '_extract_cn/GameMainConfig_assets_bin_Data_e37c46fea17834108a4756797197d05a.json'
IDENT = set('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_')

P1, P2, P3, P4, P5 = 2654435761, 2246822519, 3266489917, 668265263, 374761393


def _rotl(x, r):
    x &= M
    return ((x << r) | (x >> (32 - r))) & M


def xxh32(data, seed=0):
    n = len(data)
    i = 0
    if n >= 16:
        v1 = (seed + P1 + P2) & M
        v2 = (seed + P2) & M
        v3 = seed & M
        v4 = (seed - P1) & M

        def _round(v, kk):
            return (_rotl((v + (kk * P2)) & M, 13) * P1) & M

        while i <= n - 16:
            v1 = _round(v1, int.from_bytes(data[i:i + 4], 'little')); i += 4
            v2 = _round(v2, int.from_bytes(data[i:i + 4], 'little')); i += 4
            v3 = _round(v3, int.from_bytes(data[i:i + 4], 'little')); i += 4
            v4 = _round(v4, int.from_bytes(data[i:i + 4], 'little')); i += 4
        h = (_rotl(v1, 1) + _rotl(v2, 7) + _rotl(v3, 12) + _rotl(v4, 18)) & M
    else:
        h = (seed + P5) & M
    h = (h + n) & M
    while i + 4 <= n:
        k = int.from_bytes(data[i:i + 4], 'little')
        i += 4
        h = (_rotl((h + k * P3) & M, 17) * P4) & M
    while i < n:
        h = (_rotl((h + data[i] * P5) & M, 11) * P1) & M
        i += 1
    h ^= h >> 15
    h = (h * P2) & M
    h ^= h >> 13
    h = (h * P3) & M
    h ^= h >> 16
    return h & M


def create_key(name):
    seed = xxh32(name.encode())
    mt = [0] * 624
    mt[0] = seed
    for i in range(1, 624):
        mt[i] = (1812433253 * (mt[i - 1] ^ (mt[i - 1] >> 30)) + i) & M
    for i in range(624):
        y = (mt[i] & 0x80000000) | (mt[(i + 1) % 624] & 0x7FFFFFFF)
        v = mt[(i + 397) % 624] ^ (y >> 1)
        if y & 1:
            v ^= 2567483615
        mt[i] = v & M
    out = bytearray()
    for j in range(2):
        y = mt[j]
        y ^= y >> 11
        y ^= (y << 7) & 2636928640
        y ^= (y << 15) & 4022730752
        y ^= y >> 18
        n = (y & M) >> 1
        out += bytes(((n >> (8 * k)) & 0xFF) for k in range(4))
    return bytes(out)


def cyc8(k, n):
    return (k * (n // 8 + 2))[:n]


def crack(key_ct, label):
    L = len(key_ct) // 2
    k = [None] * 8
    for odd in (1, 3, 5, 7):
        if odd < len(key_ct):
            k[odd] = key_ct[odd]
    allowed, sizes = [], []
    for p in range(4):
        idx = list(range(p, L, 4))
        opts = [v for v in range(256) if all(chr(key_ct[2 * i] ^ v) in IDENT for i in idx)]
        allowed.append(opts)
        sizes.append(len(opts))
    total = 1
    for s in sizes:
        total *= s
    print('  %s L=%d  phases=%s combos=%d' % (label, L, sizes, total))
    hits = []
    for c0, c2, c4, c6 in itertools.product(*allowed):
        kk = list(k)
        kk[0], kk[2], kk[4], kk[6] = c0, c2, c4, c6
        name = ''.join(chr(key_ct[2 * i] ^ kk[(2 * i) % 8]) for i in range(L))
        if not name[:1].isalpha():
            continue
        if create_key(name) == bytes(kk):
            hits.append(name)
    return hits


def main():
    # 先自检：create_key 必须复现 1b232806ad72c257
    ck = create_key('GameMainConfig')
    print('[selftest] create_key("GameMainConfig") =', ck.hex(), 'OK' if ck.hex() == '1b232806ad72c257' else 'FAIL')
    if ck.hex() != '1b232806ad72c257':
        return

    js = json.loads(Path(OUTER).read_text(encoding='utf-8'))
    pairs = [(base64.b64decode(k + '=' * (-len(k) % 4)),
              base64.b64decode(v + '=' * (-len(v) % 4))) for k, v in js.items()]

    cfg = {}
    KNOWN = {0: 'SkipTutorial', 1: 'ServerInfoDataUrl'}   # 已由词表+自密钥验证，跳过 2.7M 枚举
    for i, (key_ct, val_ct) in enumerate(pairs):
        print('\n=== idx %d' % i)
        if i in KNOWN:
            n = KNOWN[i]
            k = create_key(n)
            ok = bytes(a ^ b for a, b in zip(key_ct, cyc8(k, len(key_ct)))) == n.encode('utf-16-le')
            v = bytes(a ^ b for a, b in zip(val_ct, cyc8(k, len(val_ct)))).decode('utf-16-le') if val_ct else ''
            print('    [known] NAME = %-22r self-key=%s VALUE = %r' % (n, ok, v))
            cfg[n] = v
            continue
        names = crack(key_ct, 'idx%d' % i)
        for n in names:
            v = bytes(a ^ b for a, b in zip(val_ct, cyc8(create_key(n), len(val_ct)))).decode('utf-16-le') if val_ct else ''
            print('    NAME = %-22r VALUE = %r' % (n, v))
            cfg[n] = v
        if not names:
            print('    (无解)')

    print('\n=== 国服 3.0.2 GameMainConfig ===')
    for k, v in cfg.items():
        print('  %-22s = %r' % (k, v))


if __name__ == '__main__':
    main()
