#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_cn_crack.py -- 不依赖字段名词表，直接破译 GameMainConfig 第二层的字段名。

原理（周期 8 keystream 的奇偶分解）:
    key_ct = UTF16LE(N) XOR cycle8(create_key(N))
    UTF16LE(N) 的**奇数字节恒为 0x00** (ASCII 名)
    => key_ct[奇数] == cycle8(k)[奇数] == k[奇数 mod 8]     （完全已知！）
       key_ct[1], [3], [5], [7] 直接给出 k[1], k[3], k[5], k[7]
    => key_ct[偶数] == N[i] XOR k[(2i) mod 8]               （只剩 k[0],k[2],k[4],k[6] 未知）
    用「N 的字符必须是 [A-Za-z0-9_]」逐相位筛出 k 的偶数位候选，
    笛卡尔积后以 create_key(N) == k 作唯一判定（因此无需任何候选词表）。
"""
import base64
import itertools
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from CRYPTO_MT import create_key  # noqa: E402

OUTER = '_extract_cn/GameMainConfig_assets_bin_Data_e37c46fea17834108a4756797197d05a.json'
IDENT = set(b'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_')
PRINT = set(range(0x20, 0x7F))


def b64d(s):
    return base64.b64decode(s + '=' * (-len(s) % 4))


def cyc8(name, n):
    k = create_key(name)
    return (k * (n // 8 + 2))[:n]


def dec(name, ct):
    return bytes(a ^ b for a, b in zip(ct, cyc8(name, len(ct))))


def crack(key_ct):
    """返回候选字段名列表（通常恰好 1 个）。"""
    L = len(key_ct) // 2                      # UTF-16 字符数
    k = [None] * 8
    for odd in (1, 3, 5, 7):                  # 奇数字节 => 直接读 key
        if odd < len(key_ct):
            k[odd] = key_ct[odd]
    print('    已知 key 奇数位: ' + ' '.join('k[%d]=%02x' % (o, k[o]) for o in (1, 3, 5, 7)))

    # 相位 p: 字符 N[i], i≡p (mod 4)  <->  k[(2p) mod 8]
    allowed = []
    for p in range(4):
        idx = list(range(p, L, 4))
        kpos = (2 * p) % 8
        opts = []
        for v in range(256):
            if all((key_ct[2 * i] ^ v) in IDENT for i in idx):
                opts.append(v)
        allowed.append(opts)
        print('    phase %d -> k[%d]: %d 个候选字节 (字符 %s)'
              % (p, kpos, len(opts), idx))

    out = []
    for c0, c2, c4, c6 in itertools.product(*allowed):
        kk = list(k)
        kk[0], kk[2], kk[4], kk[6] = c0, c2, c4, c6
        # 用猜出的 k 反推名字
        name = bytes(key_ct[2 * i] ^ kk[(2 * i) % 8] for i in range(L)).decode('ascii')
        if create_key(name).hex() == bytes(kk).hex():
            out.append(name)
    return out


def main():
    js = json.loads(Path(OUTER).read_text(encoding='utf-8'))
    print('[*] outer pairs =', len(js))
    rows = []
    for i, (k, v) in enumerate(js.items()):
        key_ct, val_ct = b64d(k), b64d(v)
        print('\n=== idx %d  name_len=%d  key_ct=%s' % (i, len(key_ct) // 2, key_ct.hex()))
        names = crack(key_ct)
        if not names:
            print('    !! 无解')
            rows.append((i, None, None))
            continue
        for n in names:
            assert dec(n, key_ct) == n.encode('utf-16-le'), 'self-key mismatch'
            val = dec(n, val_ct).decode('utf-16-le') if val_ct else ''
            print('    -> NAME = %r   VALUE = %r' % (n, val))
            rows.append((i, n, val))

    print('\n=== 还原后的国服 GameMainConfig ===')
    cfg = {}
    for i, n, v in rows:
        if n is not None:
            cfg[n] = v
            print('  %-20s = %r' % (n, v))
    Path('_extract_cn/CN_GameMainConfig_plain.json').write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2), encoding='utf-8')
    print('\n[write] _extract_cn/CN_GameMainConfig_plain.json')


if __name__ == '__main__':
    main()
