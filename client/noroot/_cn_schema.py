#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_cn_schema.py -- 国服 3.0.2 第二层字段名反搜（自密钥判定）。

判定式（充要）:  dec(cand, key_ct) == UTF16LE(cand)
候选来源: 国服 global-metadata.dat 的 null 分隔可打印串（内存读，不落盘）。
"""
import base64
import json
import re
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from CRYPTO_MT import create_key  # noqa: E402

APK = str(Path(__file__).resolve().parents[3] / 'report' / '_tmp' / 'cn_base.apk')
MET = 'assets/bin/Data/Managed/Metadata/global-metadata.dat'
OUTER = '_extract_cn/GameMainConfig_assets_bin_Data_e37c46fea17834108a4756797197d05a.json'


def cyc8(name, n):
    k = create_key(name)
    return (k * (n // 8 + 2))[:n]


def dec(name, ct):
    return bytes(a ^ b for a, b in zip(ct, cyc8(name, len(ct))))


def u16(s):
    return s.encode('utf-16-le')


def b64d(s):
    return base64.b64decode(s + '=' * (-len(s) % 4))


def main():
    js = json.loads(Path(OUTER).read_text(encoding='utf-8'))
    targets = defaultdict(list)          # char_len -> [(idx, key_ct, val_ct)]
    for i, (k, v) in enumerate(js.items()):
        kct = b64d(k)
        targets[len(kct) // 2].append((i, kct, b64d(v)))
    print('[*] 待反搜目标: ', {L: [t[0] for t in ts] for L, ts in sorted(targets.items())})
    for L, ts in sorted(targets.items()):
        for i, kct, vct in ts:
            print('    idx=%d  name_len=%d  key_ct=%d B  val_ct=%d B' % (i, L, len(kct), len(vct)))

    print('\n[*] 读取 metadata (内存) ...')
    m = zipfile.ZipFile(APK).read(MET)
    print('[*] metadata = %d B' % len(m))

    cands = set()
    for chunk in m.split(b'\x00'):
        if 8 <= len(chunk) <= 32:
            try:
                s = chunk.decode('ascii')
            except UnicodeDecodeError:
                continue
            if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', s):
                cands.add(s)
    print('[*] 候选标识符 =', len(cands), ' (len 8..32)')

    bylen = defaultdict(int)
    for c in cands:
        bylen[len(c)] += 1
    print('[*] 按长度分布:', dict(sorted(bylen.items())))

    print('\n[*] 自密钥反搜 ...')
    found = {}
    for c in cands:
        ts = targets.get(len(c))
        if not ts:
            continue
        u = u16(c)
        ks = cyc8(c, len(u))
        # 只解前 len(u) 字节即可判定
        for i, kct, vct in ts:
            if len(kct) != len(u):
                continue
            if bytes(a ^ b for a, b in zip(kct, ks)) == u:
                val = dec(c, vct) if vct else b''
                try:
                    vs = val.decode('utf-16-le')
                except Exception:
                    vs = '<BAD>' + val.hex()
                found[i] = (c, vs)
                print('  HIT idx=%d  name=%r  value=%r' % (i, c, vs))

    print('\n=== 汇总 ===')
    for i in sorted(found):
        print('  [%d] %-20s = %r' % (i, found[i][0], found[i][1]))
    miss = [i for L, ts in targets.items() for i, _, _ in ts if i not in found]
    print('  未破:', miss)


if __name__ == '__main__':
    main()
