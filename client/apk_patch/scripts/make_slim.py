#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a 'slim' APK containing everything except assets/ and lib/.

Purpose: give apktool a small (≈16 MB) but resource-complete input so we can
decode / edit / rebuild without dragging 1.9 GB of Unity audio through it.
The rebuilt slim is then harvested for resources.arsc + res/*.xml (+ dex),
which get injected into the real 2.1 GB APK by build_noroot_apk.py --asset-replace.
"""
import sys, os, zipfile, hashlib

BASE = r'C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\noroot\BA_noroot_prod_20261118_v1.apk'
OUTDIR = r'C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\apk_patch\slim'
OUT = os.path.join(OUTDIR, 'slim.apk')
SKIP = ('assets/', 'lib/')

os.makedirs(OUTDIR, exist_ok=True)
zin = zipfile.ZipFile(BASE, 'r')
kept = [i for i in zin.infolist() if not i.filename.startswith(SKIP)]
print('keeping %d / %d entries' % (len(kept), len(zin.infolist())))

tmp = OUT + '.tmp'
with zipfile.ZipFile(tmp, 'w', allowZip64=True) as zout:
    for i in kept:
        data = zin.read(i.filename)
        zi = zipfile.ZipInfo(i.filename, date_time=i.date_time)
        zi.compress_type = i.compress_type
        zi.external_attr = i.external_attr
        zi.internal_attr = i.internal_attr
        zi.create_system = i.create_system
        zout.writestr(zi, data)
        if i.filename in ('resources.arsc', 'res/Q9.xml', 'classes.dex'):
            print('  wrote %-20s %d B method=%d' % (i.filename, len(data), i.compress_type))
os.replace(tmp, OUT)
print('slim:', OUT, os.path.getsize(OUT), 'B')

h = hashlib.sha256()
with open(OUT, 'rb') as f:
    for chunk in iter(lambda: f.read(1 << 20), b''):
        h.update(chunk)
print('slim sha256:', h.hexdigest())
