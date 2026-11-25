# -*- coding: utf-8 -*-
"""find which entries actually differ in compress_size, top deltas"""
import sys
import zipfile

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
OLD = r'work\ba\apk_patch\backup\BA_noroot_prod_20261118_v1.apk'
NEW = r'work\ba\apk_patch\out\BlueArchive_cardlogin_v1.apk'

zo = zipfile.ZipFile(OLD)
zn = zipfile.ZipFile(NEW)

# list-based (keep duplicates)
lo = zo.infolist()
ln = zn.infolist()
print('list lengths %d / %d' % (len(lo), len(ln)))

mo = {}
for i in lo:
    mo.setdefault(i.filename, []).append(i)
mn = {}
for i in ln:
    mn.setdefault(i.filename, []).append(i)
print('unique names %d / %d' % (len(mo), len(mn)))
print('names with >1 entry old=%d new=%d'
      % (sum(1 for v in mo.values() if len(v) > 1), sum(1 for v in mn.values() if len(v) > 1)))

deltas = []
for n in sorted(set(mo) & set(mn)):
    a = mo[n][0]
    b = mn[n][0]
    d = b.compress_size - a.compress_size
    if d != 0 or a.compress_type != b.compress_type:
        deltas.append((d, n, a, b))
deltas.sort(reverse=True)
print('\nentries whose compress_size differs: %d' % len(deltas))
tot = 0
for d, n, a, b in deltas[:25]:
    tot += d
    print('  %+9d  %-46s method %d->%d  usize %d->%d  csize %d->%d'
          % (d, n, a.compress_type, b.compress_type, a.file_size, b.file_size,
             a.compress_size, b.compress_size))
print('  sum of ALL differing compress_size deltas = %d'
      % sum(d for d, _, _, _ in deltas))
