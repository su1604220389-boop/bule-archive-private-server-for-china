#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify rebuilt classes.dex integrity + presence of patched strings, then stage files"""
import hashlib
import os
import shutil
import struct
import sys
import zlib

NEW = '/root/ba_work/out/classes.dex'
ORIG = '/root/ba_work/verify/classes_orig.dex'
STAGE = '/mnt/c/Users/su/Desktop/大肥鱼项目/BAServer/work/ba/apk_patch/out/staging'


def dex_check(path, tag):
    d = open(path, 'rb').read()
    magic = d[:8]
    ok_magic = magic.startswith(b'dex\n') and magic.endswith(b'\x00')
    ver = magic[4:7].decode('ascii', 'replace')
    csum = struct.unpack('<I', d[8:12])[0]
    calc = zlib.adler32(d[12:]) & 0xFFFFFFFF
    sig = d[12:32]
    calc_sig = hashlib.sha1(d[32:]).digest()
    fsize = struct.unpack('<I', d[32:36])[0]
    print('[%s] %s' % (tag, path))
    print('   size=%d  header.file_size=%d  match=%s' % (len(d), fsize, len(d) == fsize))
    print('   magic=%r version=%s' % (magic, ver))
    print('   checksum(stored)=0x%08x  adler32(bytes[12:])=0x%08x  MATCH=%s'
          % (csum, calc, csum == calc))
    print('   signature(stored)=%s  sha1(bytes[32:])=%s  MATCH=%s'
          % (sig.hex(), calc_sig.hex(), sig == calc_sig))
    print('   sha256=%s' % hashlib.sha256(d).hexdigest())
    return d, (ok_magic and csum == calc and sig == calc_sig and len(d) == fsize)


o = open(ORIG, 'rb').read() if os.path.exists(ORIG) else b''
d, ok = dex_check(NEW, 'NEW classes.dex')
if o:
    dex_check(ORIG, 'ORIG classes.dex')

# ---- strings ----
NEED = {
    'guest_label': '游客登录',
    'card_label': '卡密登录',
    'hint_free': '请输入公益卡密',
    'hint_paid': '请输入付费卡密',
    'regex_new': '^.{1,64}$',
}
print('\n[strings]')
for k, s in NEED.items():
    b = s.encode('utf-8')
    print('   %-12s %-16r present_in_new=%s  present_in_orig=%s'
          % (k, s, d.find(b) >= 0, (o.find(b) >= 0) if o else 'n/a'))

OLD_RE = b'^1\\d{10}$'
print('   %-12s %-16r present_in_new=%s  present_in_orig=%s'
      % ('regex_old', '^1\\d{10}$', d.find(OLD_RE) >= 0, (o.find(OLD_RE) >= 0) if o else 'n/a'))

# ---- structural counts from header ----
print('\n[dex header counts]')
for name, off in [('string_ids_size', 56), ('type_ids_size', 64), ('proto_ids_size', 72),
                  ('field_ids_size', 80), ('method_ids_size', 88), ('class_defs_size', 96)]:
    print('   %-16s new=%-8d orig=%s' % (name, struct.unpack('<I', d[off:off + 4])[0],
                                         struct.unpack('<I', o[off:off + 4])[0] if o else 'n/a'))

if not ok:
    print('\n!! dex integrity check FAILED')
    sys.exit(1)

os.makedirs(STAGE, exist_ok=True)
shutil.copyfile('/root/ba_work/out/Q9.xml', os.path.join(STAGE, 'Q9.xml'))
shutil.copyfile(NEW, os.path.join(STAGE, 'classes.dex'))
for f in ('Q9.xml', 'classes.dex'):
    p = os.path.join(STAGE, f)
    b = open(p, 'rb').read()
    print('[stage] %s  size=%d  sha256=%s' % (p, len(b), hashlib.sha256(b).hexdigest()))
print('[OK] dex integrity verified, staged')
