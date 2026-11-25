#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Inventory the BA APK: entry prefixes, sizes, and key entries of interest."""
import sys, zipfile, collections, os

APK = sys.argv[1] if len(sys.argv) > 1 else \
    r'C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\noroot\BA_noroot_prod_20261118_v1.apk'

zf = zipfile.ZipFile(APK, 'r')
infos = zf.infolist()
print('entries:', len(infos))
print('file size:', os.path.getsize(APK))

agg = collections.Counter()
cnt = collections.Counter()
for i in infos:
    k = i.filename.split('/')[0] if '/' in i.filename else '(root)'
    agg[k] += i.compress_size
    cnt[k] += 1
print('\n--- top-level prefix sizes ---')
for k, v in agg.most_common():
    print('%-14s %5d entries  %14d B (%.1f MB)' % (k, cnt[k], v, v / 1048576.0))

# second level for assets
agg2 = collections.Counter()
cnt2 = collections.Counter()
for i in infos:
    parts = i.filename.split('/')
    if parts[0] == 'assets' and len(parts) > 1:
        k = 'assets/' + parts[1]
        agg2[k] += i.compress_size
        cnt2[k] += 1
print('\n--- assets/ second level ---')
for k, v in agg2.most_common(20):
    print('%-28s %5d entries  %14d B (%.1f MB)' % (k, cnt2[k], v, v / 1048576.0))

KEY = ['AndroidManifest.xml', 'resources.arsc', 'classes.dex', 'classes2.dex',
       'res/Q9.xml', 'res/nW.xml', 'res/EQ.xml', 'res/o4.xml', 'res/Dk.xml',
       'assets/SDKConfigSettings.json']
print('\n--- key entries ---')
by_name = {i.filename: i for i in infos}
for k in KEY:
    i = by_name.get(k)
    if not i:
        print('%-34s MISSING' % k)
        continue
    print('%-34s size=%9d csize=%9d crc=%08x method=%d' %
          (k, i.file_size, i.compress_size, i.CRC, i.compress_type))

print('\n--- res/ count ---')
res = [i for i in infos if i.filename.startswith('res/')]
print('res entries:', len(res), 'total', sum(i.compress_size for i in res))
dex = [i for i in infos if i.filename.startswith('classes')]
print('dex entries:', [(i.filename, i.file_size) for i in dex])
print('lib/ compress size:', agg['lib'])
print('arsc_first? first 3 entries:', [i.filename for i in infos[:3]])
