#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate jar_line() wrapping against the official MANIFEST.MF byte-for-byte."""
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_noroot_apk as B  # noqa: E402

APK = Path(r'C:\Users\su\Desktop\大肥鱼项目\BAServer\report\_tmp\cn_base.apk')
zf = zipfile.ZipFile(APK)
raw = zf.read('META-INF/MANIFEST.MF')
zf.close()

lines = raw.split(b'\r\n')
# collect official "Name:" attribute raw lines (with continuations)
official = {}
i = 0
while i < len(lines):
    if lines[i].startswith(b'Name: '):
        blk = [lines[i]]
        j = i + 1
        while j < len(lines) and lines[j].startswith(b' '):
            blk.append(lines[j])
            j += 1
        official[b''.join(x if k == 0 else x[1:] for k, x in enumerate(blk))[6:]] = blk
        i = j
    else:
        i += 1

bad = 0
maxlen = 0
for name, want in official.items():
    got = B.jar_line('Name: ', name.decode('utf-8')).split(b'\r\n')[:-1]
    maxlen = max(maxlen, max(len(x) for x in got))
    if got != want:
        bad += 1
        if bad <= 3:
            print('MISMATCH name=%r' % name)
            print('  official:', want)
            print('  jar_line:', got)
print('names checked      :', len(official))
print('mismatch           :', bad)
print('max line len mine  :', maxlen, '(official max =',
      max(len(x) for x in lines), ')')
print('RESULT:', 'PASS' if bad == 0 else 'FAIL')
