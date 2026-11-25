#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""In-place 9-byte patch of classes.dex string 32792 + DEX header re-checksum.

NO dex rebuild: exactly one 9-byte payload is overwritten with an *equal length*
9-byte payload, then the two header integrity fields are recomputed:
    +0x08 uint32  adler32(bytes[12:])
    +0x0c [20]    SHA-1(bytes[32:])
Everything else must stay bit-identical; this script proves it byte by byte.
"""
import hashlib
import os
import struct
import sys
import zipfile
import zlib

IDX = 32792
OLD = b'^1\\d{10}$'        # ^ 1 \ d { 1 0 } $
NEW = b'^.{1,64}$'         # ^ . { 1 , 6 4 } $
assert len(OLD) == 9 and len(NEW) == 9, (len(OLD), len(NEW))

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.abspath(os.path.join(HERE, '..', 'backup', 'BA_noroot_prod_20261118_v1.apk'))
OUT = os.path.join(HERE, 'classes_patched.dex')


def locate(data, idx):
    sids, soff = struct.unpack_from('<II', data, 0x38)
    assert idx < sids, (idx, sids)
    off = struct.unpack_from('<I', data, soff + 4 * idx)[0]
    p = off
    n = 0
    shift = 0
    while True:
        b = data[p]
        n |= (b & 0x7f) << shift
        shift += 7
        p += 1
        if not (b & 0x80):
            break
    return off, p, n


def main():
    with zipfile.ZipFile(BASE) as z:
        data = bytearray(z.read('classes.dex'))
    print('=== input classes.dex ===')
    print('  size          = %d' % len(data))
    print('  sha256        = %s' % hashlib.sha256(bytes(data)).hexdigest())
    sz = struct.unpack_from('<I', data, 0x20)[0]
    assert sz == len(data), (sz, len(data))

    off, p, n = locate(data, IDX)
    payload = bytes(data[p:p + n])
    print('  string_ids[%d] data_off = 0x%x  uleb128 len = %d  payload = %r'
          % (IDX, off, n, payload))
    assert payload == OLD, 'unexpected payload %r' % payload
    assert n == 9

    # ---- the ONLY content change -------------------------------------------
    old_cks = struct.unpack_from('<I', data, 0x08)[0]
    old_sig = bytes(data[0x0c:0x20])
    # order matters: adler32 covers bytes[12:], i.e. it covers the signature.
    data[p:p + 9] = NEW
    new_sig = hashlib.sha1(bytes(data[32:])).digest()
    data[0x0c:0x20] = new_sig
    new_cks = zlib.adler32(bytes(data[12:])) & 0xffffffff
    struct.pack_into('<I', data, 0x08, new_cks)

    # ---- header sanity -----------------------------------------------------
    blob = bytes(data)
    assert len(blob) == sz
    assert struct.unpack_from('<I', blob, 0x08)[0] == zlib.adler32(blob[12:]) & 0xffffffff
    assert hashlib.sha1(blob[32:]).digest() == blob[12:32]
    _, p2, n2 = locate(blob, IDX)
    print('\n=== after patch ===')
    print('  string_ids[%d] payload = %r' % (IDX, blob[p2:p2 + n2]))
    print('  +0x08 checksum  0x%08x -> 0x%08x' % (old_cks, new_cks))
    print('  +0x0c signature %s -> %s' % (old_sig.hex(), new_sig.hex()))
    print('  adler32(bytes[12:])  = 0x%08x (matches header)' % (zlib.adler32(blob[12:]) & 0xffffffff))
    print('  sha1(bytes[32:])     = %s (matches header)' % hashlib.sha1(blob[32:]).hexdigest())
    print('  size unchanged       = %s (%d)' % (len(blob) == sz, len(blob)))
    print('  sha256(new)      = %s' % hashlib.sha256(blob).hexdigest())

    # ---- byte level diff proof --------------------------------------------
    with zipfile.ZipFile(BASE) as z:
        orig = z.read('classes.dex')
    assert len(orig) == len(blob)
    diffs = [i for i in range(len(orig)) if orig[i] != blob[i]]
    print('\n=== byte diff vs original ===')
    print('  total bytes        = %d' % len(orig))
    print('  differing bytes    = %d' % len(diffs))
    print('  identical bytes    = %d' % (len(orig) - len(diffs)))
    print('  differing offsets  = %s' % (' '.join('0x%x' % i for i in diffs)))
    ranges = []
    start = prev = diffs[0]
    for i in diffs[1:]:
        if i == prev + 1:
            prev = i
            continue
        ranges.append((start, prev))
        start = prev = i
    ranges.append((start, prev))
    print('  contiguous ranges  = %s' % ', '.join('0x%x..0x%x(%d)'
                                                 % (a, b, b - a + 1) for a, b in ranges))
    payload_hits = [i for i in diffs if p <= i < p + 9]
    hdr_hits = [i for i in diffs if 8 <= i < 32]
    # the 9-byte payload window is fully overwritten; only the bytes whose value
    # actually changes show up in the diff (^ at +0, } at +7, $ at +8 are equal)
    assert blob[p:p + 9] == NEW, 'payload region wrong'
    assert orig[p:p + 9] == OLD, 'original payload region wrong'
    assert all(i in range(8, 32) or i in range(p, p + 9) for i in diffs), 'stray diff!'
    print('  payload window 0x%x..0x%x  old %s' % (p, p + 8, OLD.hex(' ')))
    print('                             new %s' % NEW.hex(' '))
    print('  bytes inside the payload window that changed value: %d/9  (offsets %s)'
          % (len(payload_hits), ' '.join('0x%x' % i for i in payload_hits)))
    print('  bytes outside payload window in 0x%x..0x%x: %d'
          % (p, p + 8, 9 - len(payload_hits)))
    print('  header region 0x08..0x1f differs in %d/24 bytes' % len(hdr_hits))
    print('  bytes outside those two regions untouched: %d'
          % (len(orig) - len(diffs)))

    open(OUT, 'wb').write(blob)
    print('\n  wrote %s (%d B)' % (OUT, len(blob)))


if __name__ == '__main__':
    main()
