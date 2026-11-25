#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Final acceptance: read everything BACK OUT of the two delivered APKs.

This is deliberately not re-using the local staging files -- it proves what is
actually inside the shipped packages.
"""
import hashlib
import os
import struct
import sys
import zlib
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import axml_dump as A

OUT = os.path.abspath(os.path.join(HERE, '..', 'out'))
V2 = os.path.join(OUT, 'v2_layoutonly.apk')
V3 = os.path.join(OUT, 'v3_dexpatch.apk')
BASE = os.path.abspath(os.path.join(HERE, '..', 'backup', 'BA_noroot_prod_20261118_v1.apk'))
ARSC = 'cd8943ae979fd434a6c1fee67e8129bba1bc4a452e1937d7d7e6052079eecb86'
TMP = os.path.join(HERE, 'tmp_q9.axml')


def sha(b):
    return hashlib.sha256(b).hexdigest()


def dump_axml(blob, tag):
    open(TMP, 'wb').write(blob)
    d = A.parse(TMP)
    names = [n['name'] for n in d['nodes'] if n['k'] == 'E_START']
    txt = A.dump(TMP)
    return d, names, txt


print('=== delivered package acceptance (values read back from the .apk) ===')
for tag, p in (('v2_layoutonly', V2), ('v3_dexpatch', V3)):
    print('\n--- %s = %s' % (tag, os.path.basename(p)))
    print('    bytes  = %d' % os.path.getsize(p))
    with open(p, 'rb') as f:
        h = hashlib.sha256()
        for chunk in iter(lambda: f.read(1 << 22), b''):
            h.update(chunk)
    print('    sha256 = %s' % h.hexdigest())
    with zipfile.ZipFile(p) as z:
        names = z.namelist()
        arsc = z.read('resources.arsc')
        q9 = z.read('res/Q9.xml')
        dex = z.read('classes.dex')
        print('    entries = %d' % len(names))
        print('    resources.arsc sha256 = %s -> %s'
              % (sha(arsc), 'OK == baseline' if sha(arsc) == ARSC else 'FAIL'))
        print('    res/Q9.xml  %d B sha256=%s' % (len(q9), sha(q9)))
        d, els, txt = dump_axml(q9, tag)
        print('    res/Q9.xml  elements = %d, RadioGroup=%d RadioButton=%d'
              % (len(els), els.count('RadioGroup'), els.count('RadioButton')))
        has_guest = '游客登录' in txt
        has_card = '卡密登录' in txt
        mx = [l.strip() for l in txt.splitlines() if 'maxLength' in l]
        it = [l.strip() for l in txt.splitlines() if 'inputType' in l]
        print('    literal text "游客登录" = %s, "卡密登录" = %s' % (has_guest, has_card))
        print('    maxLength attrs: %s' % '; '.join(mx))
        print('    inputType attrs: %s' % '; '.join(it))
        ck = [l.strip() for l in txt.splitlines() if 'checked(' in l]
        print('    checked attrs  : %s' % ('; '.join(ck) or 'none'))
        # ---- dex -----
        sz = struct.unpack_from('<I', dex, 0x20)[0]
        ok_len = (sz == len(dex))
        ok_cks = (struct.unpack_from('<I', dex, 0x08)[0] == zlib.adler32(dex[12:]) & 0xffffffff)
        ok_sig = (hashlib.sha1(dex[32:]).digest() == dex[12:32])
        sids, soff = struct.unpack_from('<II', dex, 0x38)
        off = struct.unpack_from('<I', dex, soff + 4 * 32792)[0]
        q = off
        n = 0
        sh = 0
        while True:
            b = dex[q]
            n |= (b & 0x7f) << sh
            sh += 7
            q += 1
            if not (b & 0x80):
                break
        s = dex[q:q + n]
        print('    classes.dex %d B sha256=%s' % (len(dex), sha(dex)))
        print('      file_size(0x20)==len : %s' % ok_len)
        print('      adler32(0x08)       : %s (0x%08x)' % (ok_cks, struct.unpack_from('<I', dex, 0x08)[0]))
        print('      sha1(0x0c)          : %s (%s)' % (ok_sig, dex[12:32].hex()))
        print('      string_ids[32792]   : %r   (data_off 0x%x, uleb128 %d)' % (s, off, n))
        print('      string count        : %d' % sids)
