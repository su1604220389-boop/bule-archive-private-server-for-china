#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verify the exact AXML landing points inside the ORIGINAL res/Q9.xml."""
import sys, zipfile, struct, hashlib, os

BASE = r'C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\noroot\BA_noroot_prod_20261118_v1.apk'
zf = zipfile.ZipFile(BASE, 'r')
d = zf.read('res/Q9.xml')
print('res/Q9.xml size =', len(d), 'sha256 =', hashlib.sha256(d).hexdigest())

for off in (0xc88, 0xc9c, 0xef0, 0xf04, 0xc60, 0xc10):
    if off + 4 <= len(d):
        v = struct.unpack_from('<I', d, off)[0]
        print('offset 0x%04x  u32 = 0x%08x (%d)' % (off, v, v))

print('\n--- raw bytes 0xc70..0xcd0 (attribute records around et_phone) ---')
for row in range(0xc70, 0xcd0, 16):
    chunk = d[row:row + 16]
    print('0x%04x  %s  %s' % (row, ' '.join('%02x' % b for b in chunk),
                              ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)))

print('\n--- AXML header ---')
t, hsz, sz = struct.unpack_from('<HHI', d, 0)
print('type=0x%04x hdrSize=%d size=%d  (file len %d)' % (t, hsz, sz, len(d)))

# count attributes whose dataType is TYPE_STRING(0x03) in the whole file
nstr = 0
for i in range(8, len(d) - 4):
    pass
print('\n--- keystore ---')
ks = r'C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\noroot\ba_private.keystore'
print('path:', ks, 'size:', os.path.getsize(ks))
h = hashlib.sha256(open(ks, 'rb').read()).hexdigest()
print('sha256:', h)
