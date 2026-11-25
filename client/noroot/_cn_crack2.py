#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_cn_crack2.py -- 奇偶分解硬破第二层剩余字段名（不依赖词表）。

    key_ct[奇数] = k[奇数]                       (UTF-16LE 名的高字节恒 0)
    key_ct[偶数] = N[i] XOR k[(2i) mod 8]
逐相位筛 [A-Za-z0-9_] 得 k 的 4 个偶数字节候选，笛卡尔积后用
create_key(N) == k 判定。名字短（9~11 字符）时组合数很小，瞬时完成。
"""
import base64
import itertools
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _cn_guess import mt19937_key  # noqa: E402

OUTER = '_extract_cn/GameMainConfig_assets_bin_Data_e37c46fea17834108a4756797197d05a.json'
IDENT = set('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_')


def b64d(s):
    return base64.b64decode(s + '=' * (-len(s) % 4))


def cyc8_k(k, n):
    return (k * (n // 8 + 2))[:n]


def crack(key_ct, verbose=True):
    L = len(key_ct) // 2
    k = [None] * 8
    for odd in (1, 3, 5, 7):
        if odd < len(key_ct):
            k[odd] = key_ct[odd]
    allowed = []
    for p in range(4):
        idx = list(range(p, L, 4))
        opts = []
        for v in range(256):
            if all(chr(key_ct[2 * i] ^ v) in IDENT for i in idx):
                opts.append(v)
        allowed.append(opts)
    total = 1
    for a in allowed:
        total *= len(a)
    if verbose:
        print('    phases: %s  total combos = %d'
              % ([len(a) for a in allowed], total))
    hits = []
    for c0, c2, c4, c6 in itertools.product(*allowed):
        kk = list(k)
        kk[0], kk[2], kk[4], kk[6] = c0, c2, c4, c6
        name = bytes(key_ct[2 * i] ^ kk[(2 * i) % 8] for i in range(L)).decode('ascii')
        if not name[:1].isalpha():
            continue
        if mt19937_key(name) == bytes(kk):
            hits.append(name)
    return hits


def main():
    js = json.loads(Path(OUTER).read_text(encoding='utf-8'))
    cfg = {}
    for i, (kb, vb) in enumerate(js.items()):
        key_ct, val_ct = b64d(kb), b64d(vb)
        print('=== idx %d  name_len=%d' % (i, len(key_ct) // 2))
        names = crack(key_ct)
        for n in names:
            k = mt19937_key(n)
            val = bytes(a ^ b for a, b in zip(val_ct, cyc8_k(k, len(val_ct)))).decode('utf-16-le') if val_ct else ''
            print('    NAME = %-20r VALUE = %r' % (n, val))
            cfg[n] = val
        if not names:
            print('    (无解)')
    print('\n=== 国服 3.0.2 GameMainConfig 还原 ===')
    for k, v in cfg.items():
        print('  %-22s = %r' % (k, v))
    Path('_extract_cn/CN_GameMainConfig_plain.json').write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2), encoding='utf-8')
    print('\n[write] _extract_cn/CN_GameMainConfig_plain.json')


if __name__ == '__main__':
    main()
