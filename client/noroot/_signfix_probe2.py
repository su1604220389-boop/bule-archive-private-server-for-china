#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""只读测量 2：推导 signapk 的换行规则 + 看真 apksigner 的 SF/MANIFEST 结构。"""
import collections
import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '..', '..', '..', 'report', '_tmp', 'cn_base.apk')
PROBE13 = os.path.join(HERE, '..', 'bapatch', 'lsp', 'build13', 'Probe13.apk')


def splitlines(data):
    lines = data.split(b'\r\n')
    if lines and lines[-1] == b'':
        lines = lines[:-1]
    return lines


def analyze(data, label):
    lines = splitlines(data)
    print('== %s  lines=%d' % (label, len(lines)))
    hist = collections.Counter(len(x) for x in lines)
    print('   长度分布 (>=60): %s' % {k: hist[k] for k in sorted(hist) if k >= 60})
    cont = [x for x in lines if x.startswith(b' ')]
    noncont = [x for x in lines if not x.startswith(b' ')]
    print('   续行 %d 条: max=%d  长度分布(>=60)=%s'
          % (len(cont), max(len(x) for x in cont) if cont else 0,
             {k: v for k, v in sorted(collections.Counter(
                 len(x) for x in cont).items()) if k >= 60}))
    print('   非续行 %d 条: max=%d' % (len(noncont), max(len(x) for x in noncont)))
    # 续行内容长度（去掉前导空格）
    print('   续行去空格后 max=%d' % (max((len(x) - 1) for x in cont) if cont else 0))
    # 打印 3 组 70 字节行 + 下一行，看断点位置
    shown = 0
    for i, x in enumerate(lines):
        if len(x) == 70 and i + 1 < len(lines) and lines[i + 1].startswith(b' '):
            print('   [70] %r' % x)
            print('   [nxt] %r' % lines[i + 1])
            shown += 1
            if shown >= 3:
                break
    # 找最长的非续行（前 3 条）
    for x in sorted(noncont, key=len, reverse=True)[:3]:
        print('   最长非续行 %d: %r' % (len(x), x))


def main():
    with zipfile.ZipFile(SRC) as z:
        analyze(z.read('META-INF/MANIFEST.MF'), 'cn_base MANIFEST.MF')
        analyze(z.read('META-INF/BACN.SF'), 'cn_base BACN.SF')
    with zipfile.ZipFile(PROBE13) as z:
        print('\n===== Probe13 MANIFEST.MF =====')
        print(z.read('META-INF/MANIFEST.MF').decode('utf-8', 'replace'))
        print('===== Probe13 BA.SF =====')
        print(z.read('META-INF/BA.SF').decode('utf-8', 'replace'))
        analyze(z.read('META-INF/BA.SF'), 'Probe13 BA.SF')


if __name__ == '__main__':
    main()
