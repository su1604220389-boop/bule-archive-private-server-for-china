#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compare original res/Q9.xml with the freshly built one, using two independent
AXML readers: this project's own parser (axml_dump.py) and aapt's `dump xmltree`.
Run inside WSL:  python3 /mnt/c/.../v2v3/cmp_axml.py
"""
import os
import re
import subprocess
import zipfile
import hashlib
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.abspath(os.path.join(HERE, '..', 'backup', 'BA_noroot_prod_20261118_v1.apk'))
ORIG = os.path.join(HERE, 'res_Q9_orig.axml')
NEW = os.path.join(HERE, 'res_Q9_new.axml')
WRAP_O = os.path.join(HERE, 'wrap_orig.apk')
WRAP_N = os.path.join(HERE, 'wrap_new.apk')


def sh(cmd):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


with zipfile.ZipFile(BASE) as z:
    orig = z.read('res/Q9.xml')
    info = z.getinfo('res/Q9.xml')
open(ORIG, 'wb').write(orig)
new = open(NEW, 'rb').read()
print('orig res/Q9.xml  %d B  crc=%08x  sha256=%s'
      % (len(orig), info.CRC, hashlib.sha256(orig).hexdigest()))
print('new  res/Q9.xml  %d B  crc=%08x  sha256=%s'
      % (len(new), zlib.crc32(new) & 0xffffffff, hashlib.sha256(new).hexdigest()))

for p, blob in ((WRAP_O, orig), (WRAP_N, new)):
    with zipfile.ZipFile(p, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('res/Q9.xml', blob)

# ---------- reader 1: our own parser ----------
dumps = {}
for tag, f in (('orig', ORIG), ('new', NEW)):
    rc, out = sh('python3 %s dump %s' % (os.path.join(HERE, 'axml_dump.py'), f))
    if rc != 0:
        raise SystemExit('own parser failed on %s:\n%s' % (f, out))
    dumps[tag] = out
    open(os.path.join(HERE, 'own_dump_%s.txt' % tag), 'w').write(out)
print('\n=== own parser header lines ===')
for tag in ('orig', 'new'):
    print(' [%s] %s' % (tag, dumps[tag].splitlines()[1]))
rc, d = sh('diff -u %s %s' % (os.path.join(HERE, 'own_dump_orig.txt'),
                             os.path.join(HERE, 'own_dump_new.txt')))
open(os.path.join(HERE, 'own_diff.txt'), 'w').write(d)
print('=== own-parser diff: %d lines ===' % len(d.splitlines()))

# ---------- reader 2: aapt dump xmltree ----------
norm = lambda t: re.sub(r'\(line=\d+\)', '(line=?)', t)
res = {}
for tag, p in (('orig', WRAP_O), ('new', WRAP_N)):
    rc, o = sh('aapt dump xmltree "%s" res/Q9.xml' % p)
    if rc != 0:
        raise SystemExit('aapt failed on %s:\n%s' % (tag, o))
    res[tag] = o
    open(os.path.join(HERE, 'aapt_dump_%s.txt' % tag), 'w').write(o)
    open(os.path.join(HERE, 'aapt_dump_%s_norm.txt' % tag), 'w').write(norm(o))
    print(' [aapt %s] rc=%d  %d lines' % (tag, rc, len(o.splitlines())))
rc, d2 = sh('diff -u %s %s' % (os.path.join(HERE, 'aapt_dump_orig_norm.txt'),
                              os.path.join(HERE, 'aapt_dump_new_norm.txt')))
open(os.path.join(HERE, 'aapt_diff.txt'), 'w').write(d2)
print('=== aapt normalized (line= stripped) diff: %d lines ===' % len(d2.splitlines()))
print(d2)
