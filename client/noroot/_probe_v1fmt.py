#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Probe official META-INF/MANIFEST.MF + .SF formatting (read-only, ASCII output)."""
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
APK = ROOT / 'report' / '_tmp' / 'cn_base.apk'

zf = zipfile.ZipFile(APK)
meta = [n for n in zf.namelist() if n.startswith('META-INF/')]
print('[META-INF]', meta)

mf = zf.read('META-INF/MANIFEST.MF')
print('MANIFEST.MF bytes =', len(mf))
lines = mf.split(b'\r\n')
print('lines(split CRLF) =', len(lines))
lens = [len(x) for x in lines]
print('max line len =', max(lens), ' count>72 =', sum(1 for x in lens if x > 72),
      ' count>70 =', sum(1 for x in lens if x > 70))
cont = [x for x in lines if x.startswith(b' ')]
print('continuation lines =', len(cont))
print('max continuation len =', max((len(x) for x in cont), default=0))
print('max non-continuation len =', max((len(x) for x in lines if not x.startswith(b' ')), default=0))
print('--- first 12 lines ---')
for x in lines[:12]:
    print('  %3d  %r' % (len(x), x))
print('--- a wrapped name example ---')
idx = [i for i, x in enumerate(lines) if x.startswith(b'Name: ') and len(x) == 70]
print('Name: lines of exactly 70 B =', len(idx))
if idx:
    i = idx[0]
    for x in lines[i:i + 3]:
        print('  %3d  %r' % (len(x), x))
    # reconstruct
    j = i
    nm = lines[j][6:]
    j += 1
    while j < len(lines) and lines[j].startswith(b' '):
        nm += lines[j][1:]
        j += 1
    print('  joined =', nm.decode())

for sfname in [n for n in meta if n.endswith('.SF')]:
    sf = zf.read(sfname)
    print('\n=== %s (%d B) ===' % (sfname, len(sf)))
    print(repr(sf[:400]))
    print('lines:')
    for x in sf.split(b'\r\n')[:10]:
        print('  %3d  %r' % (len(x), x))
for rname in [n for n in meta if n.endswith(('.RSA', '.DSA', '.EC'))]:
    b = zf.read(rname)
    print('\n=== %s (%d B) first 64 hex ===' % (rname, len(b)))
    print(b[:64].hex())
zf.close()
