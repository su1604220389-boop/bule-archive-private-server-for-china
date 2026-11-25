# -*- coding: utf-8 -*-
"""STEP2: inspect how build_noroot_apk.py handles --asset-replace"""
import sys, io
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
p = r'work\ba\noroot\build_noroot_apk.py'
src = open(p, encoding='utf-8').read()
lines = src.split('\n')
hits = [i for i, l in enumerate(lines, 1)
        if 'asset_replace' in l or 'asset-replace' in l or 'assetrepl' in l.lower()]
print('HIT LINES:', hits)
for i in hits:
    lo = max(1, i - 3)
    hi = min(len(lines), i + 12)
    print('=' * 70)
    for n in range(lo, hi + 1):
        print('%5d| %s' % (n, lines[n - 1]))
