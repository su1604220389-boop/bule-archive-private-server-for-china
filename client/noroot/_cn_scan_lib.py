#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_cn_scan_lib.py -- 在国服 APK 的 native 库里找 state 域名 / dispatcher 线索（只读 zip）。

目的：回答「除 GameMainConfig 之外，客户端还能从哪拿到 state 域名」。
同时枚举 lib/ 与 assets/ 里体积可接受的条目，做 ASCII + UTF-16LE 双形态命中。
"""
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
APK = ROOT / 'report' / '_tmp' / 'cn_base.apk'

NEEDLES = ['state-api', 'stateqc', 'bluearchive-cn', '/api/state', 'api/state',
           'yostar', 'bluearchive', 'ServerInfoData', 'GameMainConfig',
           'DefaultConnectionGroup', 'dispatcher']


def variants(s):
    out = [s.encode('ascii'), s.encode('utf-16-le'), s.upper().encode('ascii')]
    return out


def main():
    z = zipfile.ZipFile(APK)
    infos = z.infolist()
    libs = [i for i in infos if i.filename.startswith('lib/')]
    print('[lib/] %d 个条目' % len(libs))
    for i in sorted(libs, key=lambda x: -x.file_size):
        print('   %12d  %s' % (i.file_size, i.filename))

    # 只扫 native 库（不做整包 2 GB 解压）
    targets = [i for i in libs if i.filename.endswith('.so')]
    for i in targets:
        d = z.read(i.filename)
        print('\n=== %s  (%d B) ===' % (i.filename, len(d)))
        for n in NEEDLES:
            hits = []
            for v in variants(n):
                start = 0
                while True:
                    p = d.find(v, start)
                    if p < 0:
                        break
                    hits.append((p, v))
                    start = p + 1
                    if len(hits) > 40:
                        break
            if hits:
                print('  %-24s %d hit(s)  @ %s' % (n, len(hits),
                      ', '.join(hex(p) for p, _ in hits[:8])))
                for p, v in hits[:3]:
                    lo, hi = max(0, p - 40), p + 90
                    ctx = d[lo:hi]
                    txt = re.sub(rb'[^\x20-\x7e]', b'.', ctx).decode('ascii')
                    print('      %s  |%s|' % (hex(p), txt))


if __name__ == '__main__':
    main()
