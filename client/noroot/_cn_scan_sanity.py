#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_cn_scan_sanity.py -- 验证 _cn_scan_lib.py 的「0 命中」是真阴性而不是扫描器坏了。

对照组：本该一定存在的串（il2cpp/Unity 运行时符号）。若对照组命中而目标串不命中，
则「native 库不含 state 域名明文」这个结论成立。
"""
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
APK = ROOT / 'report' / '_tmp' / 'cn_base.apk'

CONTROL = ['il2cpp', 'UnityMain', 'JNI_OnLoad', 'UnityEngine', 'MonoBehaviour',
           'System.String', 'AndroidRuntime', 'libunity']
TARGET = ['state-api', 'stateqc', 'bluearchive-cn', '/api/state', 'yostar', 'bluearchive',
          'ServerInfoData', 'GameMainConfig', 'dispatcher', 'prod', 'ChannelID']

z = zipfile.ZipFile(APK)
for member in ['lib/arm64-v8a/libil2cpp.so', 'lib/arm64-v8a/libsigner.so', 'lib/arm64-v8a/libn.so']:
    d = z.read(member)
    print('\n=== %s (%d B) ===' % (member, len(d)))
    # 熵/可打印率快检：判断是否被加密或加壳
    sample = d[:: max(1, len(d) // 200000)][:200000]
    printable = sum(1 for b in sample if 32 <= b < 127)
    zero = sum(1 for b in sample if b == 0)
    print('  抽样 %d B：可打印 %.1f%%  零字节 %.1f%%' %
          (len(sample), 100.0 * printable / len(sample), 100.0 * zero / len(sample)))
    for grp, name in ((CONTROL, '对照(应命中)'), (TARGET, '目标')):
        tot = 0
        detail = []
        for s in grp:
            c = d.count(s.encode()) + d.count(s.encode('utf-16-le'))
            tot += c
            if c:
                detail.append('%s=%d' % (s, c))
        print('  %s 合计 %d  %s' % (name, tot, ' '.join(detail[:8])))
