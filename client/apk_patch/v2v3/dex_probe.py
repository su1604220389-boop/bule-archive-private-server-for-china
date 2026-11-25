#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Probe classes.dex: locate string index 32792 and its MUTF-8 payload bytes."""
import sys, struct, hashlib, zipfile

APK = sys.argv[1] if len(sys.argv) > 1 else 'work/ba/apk_patch/backup/BA_noroot_prod_20261118_v1.apk'
IDX = int(sys.argv[2]) if len(sys.argv) > 2 else 32792

with zipfile.ZipFile(APK) as z:
    data = z.read('classes.dex')

print('dex size      =', len(data))
print('sha256        =', hashlib.sha256(data).hexdigest())
print('magic         =', data[:8].hex())
print('checksum(@08) =', data[8:12].hex(), 'stored adler32 =', hex(struct.unpack_from('<I', data, 8)[0]))
print('signature(@0c)=', data[12:32].hex())
print('file_size(@20)=', struct.unpack_from('<I', data, 0x20)[0])
print('header_size   =', struct.unpack_from('<I', data, 0x24)[0])
print('endian_tag    =', data[0x28:0x2c].hex())
string_ids_size, string_ids_off = struct.unpack_from('<II', data, 0x38)
print('string_ids    = size %d off 0x%x' % (string_ids_size, string_ids_off))
type_ids_size, type_ids_off = struct.unpack_from('<II', data, 0x40)
print('type_ids      = size %d off 0x%x' % (type_ids_size, type_ids_off))

sid_off = string_ids_off + 4 * IDX
sdata_off = struct.unpack_from('<I', data, sid_off)[0]
print('string_ids[%d] @0x%x -> data_off 0x%x' % (IDX, sid_off, sdata_off))
# uleb128 utf16_size
p = sdata_off
u = 0
shift = 0
while True:
    b = data[p]
    u |= (b & 0x7f) << shift
    shift += 7
    p += 1
    if not (b & 0x80):
        break
print('  uleb128 utf16_size = %d, prefix bytes = %s' % (u, data[sdata_off:p].hex()))
payload = data[p:p + u]
print('  payload @0x%x len %d = %r' % (p, len(payload), payload))
print('  payload hex =', payload.hex(' '))

# recompute header fields for sanity on the ORIGINAL file
print('  adler32(12:) =', hex(__import__('zlib').adler32(data[12:]) & 0xffffffff))
print('  sha1(32:)    =', hashlib.sha1(data[32:]).hexdigest())

# neighbours, for uniqueness check
for k in range(IDX - 2, IDX + 3):
    off = struct.unpack_from('<I', data, string_ids_off + 4 * k)[0]
    q = off
    sz = 0
    sh = 0
    while True:
        b = data[q]
        sz |= (b & 0x7f) << sh
        sh += 7
        q += 1
        if not (b & 0x80):
            break
    print('  [%d] %r' % (k, data[q:q + sz]))
