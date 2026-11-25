# -*- coding: utf-8 -*-
import sys
import zipfile

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
NEW = r'work\ba\apk_patch\out\BlueArchive_cardlogin_v1.apk'
z = zipfile.ZipFile(NEW)
print('%-22s %-6s %-12s %-10s %s' % ('entry', 'method', 'hdr_offset', 'data_off', 'data_off%4'))
for n in ('resources.arsc', 'classes.dex', 'res/Q9.xml', 'AndroidManifest.xml',
          'classes2.dex', 'lib/arm64-v8a/libunity.so'):
    i = z.getinfo(n)
    data_off = i.header_offset + 30 + len(i.filename.encode()) + len(i.extra)
    print('%-22s %-6d %-12d %-10d %d' % (n, i.compress_type, i.header_offset, data_off, data_off % 4))
print()
# scan ALL STORED entries for 4-byte alignment
bad = []
for i in z.infolist():
    if i.compress_type == 0:
        data_off = i.header_offset + 30 + len(i.filename.encode()) + len(i.extra)
        if data_off % 4:
            bad.append((i.filename, data_off % 4))
print('STORED entries: %d   misaligned: %d' % (sum(1 for i in z.infolist() if i.compress_type == 0), len(bad)))
for b in bad[:10]:
    print('   ', b)
