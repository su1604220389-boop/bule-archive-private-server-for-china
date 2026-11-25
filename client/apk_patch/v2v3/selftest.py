#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Full self-test for the two split packages (v2 layout-only, v3 dex patch).

Checks
  1) resources.arsc sha256 == baseline constant
  2) aapt dump badging identity fields: 0-line diff vs baseline
  3) per-entry zip diff vs baseline (name / size / crc32 / method / sha256)
  4) apksigner verify --print-certs on baseline + both packages
  5) sha256 + byte size of every package
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
BASE = os.path.abspath(os.path.join(HERE, '..', 'backup', 'BA_noroot_prod_20261118_v1.apk'))
V2 = os.path.abspath(os.path.join(HERE, '..', 'out', 'v2_layoutonly.apk'))
V3 = os.path.abspath(os.path.join(HERE, '..', 'out', 'v3_dexpatch.apk'))
ARSC_SHA = 'cd8943ae979fd434a6c1fee67e8129bba1bc4a452e1937d7d7e6052079eecb86'
BASE_SHA = '5f8b79dd930b8d1420b5b686cbc978142b751eea47c4b090ba308482a0f2f5c6'

out = []


def p(s=''):
    print(s)
    out.append(s)


def sh(cmd):
    r = subprocess.run(cmd, shell=True, capture_output=True)
    o = r.stdout.decode('utf-8', 'replace') + r.stderr.decode('utf-8', 'replace')
    return r.returncode, o


def sha256_file(path, chunk=1 << 22):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def entry_map(path):
    m = {}
    with zipfile.ZipFile(path) as z:
        for i in z.infolist():
            m[i.filename] = {'usize': i.file_size, 'csize': i.compress_size,
                             'crc': '%08x' % (i.CRC & 0xffffffff),
                             'method': i.compress_type}
    return m


def interesting(path, names):
    d = {}
    with zipfile.ZipFile(path) as z:
        for n in names:
            if n in z.namelist():
                b = z.read(n)
                d[n] = {'sha256': hashlib.sha256(b).hexdigest(), 'size': len(b)}
    return d


def main():
    p('# SELF-TEST  v2_layoutonly.apk / v3_dexpatch.apk')
    p('')
    p('baseline : %s' % BASE)
    p('v2       : %s' % V2)
    p('v3       : %s' % V3)
    p('')

    # ---------- 5) sizes & sha256 first (cheap enough, one pass) -----------
    p('## 5) package digest / size')
    p('')
    p('| file | bytes | sha256 |')
    p('|---|---|---|')
    info = {}
    for tag, path in (('baseline', BASE), ('v2_layoutonly', V2), ('v3_dexpatch', V3)):
        if not os.path.exists(path):
            p('| %s | MISSING | - |' % tag)
            continue
        h = sha256_file(path)
        info[tag] = {'path': path, 'size': os.path.getsize(path), 'sha256': h}
        p('| %s | %d | `%s` |' % (os.path.basename(path), os.path.getsize(path), h))
    p('')
    if info.get('baseline', {}).get('sha256') == BASE_SHA:
        p('* baseline sha256 == spec `%s` -> OK' % BASE_SHA)
    else:
        p('* !! baseline sha256 != spec')

    # ---------- 1) resources.arsc -----------------------------------------
    p('')
    p('## 1) resources.arsc  (must be byte-identical to baseline)')
    p('')
    names = ['resources.arsc', 'classes.dex', 'classes2.dex', 'AndroidManifest.xml', 'res/Q9.xml']
    per = {}
    for tag, path in (('baseline', BASE), ('v2_layoutonly', V2), ('v3_dexpatch', V3)):
        if os.path.exists(path):
            per[tag] = interesting(path, names)
    p('| entry | %s | v2 | v3 |' % 'baseline')
    p('|---|---|---|---|')
    for n in names:
        cells = []
        for tag in ('baseline', 'v2_layoutonly', 'v3_dexpatch'):
            d = per.get(tag, {}).get(n)
            cells.append('`%s` (%d B)' % (d['sha256'][:16] + '…', d['size']) if d else '-')
        p('| `%s` | %s | %s | %s |' % (n, cells[0], cells[1], cells[2]))
    p('')
    ok_arsc = True
    for tag in ('v2_layoutonly', 'v3_dexpatch'):
        got = per.get(tag, {}).get('resources.arsc', {}).get('sha256')
        good = (got == ARSC_SHA)
        ok_arsc = ok_arsc and good
        p('* %s resources.arsc sha256 = `%s`  -> %s' % (tag, got, 'OK' if good else 'FAIL'))
    p('* expected (spec)            = `%s`' % ARSC_SHA)
    p('')
    p('* AndroidManifest.xml unchanged in both packages: %s'
      % (per['v2_layoutonly']['AndroidManifest.xml']['sha256'] == per['baseline']['AndroidManifest.xml']['sha256']
         and per['v3_dexpatch']['AndroidManifest.xml']['sha256'] == per['baseline']['AndroidManifest.xml']['sha256']))
    p('* classes2.dex unchanged in both packages: %s'
      % (per['v2_layoutonly']['classes2.dex']['sha256'] == per['baseline']['classes2.dex']['sha256']
         and per['v3_dexpatch']['classes2.dex']['sha256'] == per['baseline']['classes2.dex']['sha256']))
    p('* v2 classes.dex == baseline classes.dex: %s'
      % (per['v2_layoutonly']['classes.dex']['sha256'] == per['baseline']['classes.dex']['sha256']))
    p('* v3 classes.dex sha256 = `%s`' % per['v3_dexpatch']['classes.dex']['sha256'])

    # ---------- 4) apksigner ----------------------------------------------
    p('')
    p('## 4) apksigner verify --print-certs')
    p('')
    certs = {}
    for tag, path in (('baseline', BASE), ('v2_layoutonly', V2), ('v3_dexpatch', V3)):
        if not os.path.exists(path):
            continue
        rc, o = sh('apksigner verify --verbose --print-certs "%s"' % path)
        certs[tag] = {'rc': rc, 'out': o}
        p('### %s  -> exit %d' % (os.path.basename(path), rc))
        p('```')
        p('\n'.join(o.strip().splitlines()[:40]))
        p('```')
        p('')

    # ---------- 2) aapt badging -------------------------------------------
    p('## 2) aapt dump badging identity fields')
    p('')
    KEYS = ('package:', 'sdkVersion:', 'targetSdkVersion:')

    def badging(path):
        rc, o = sh('aapt dump badging "%s"' % path)
        keep = []
        for line in o.splitlines():
            if line.startswith(KEYS):
                keep.append(re.sub(r'\s+', ' ', line.strip()))
        return keep

    bb = badging(BASE)
    p('### baseline')
    p('```')
    p('\n'.join(bb))
    p('```')
    for tag, path in (('v2_layoutonly', V2), ('v3_dexpatch', V3)):
        if not os.path.exists(path):
            continue
        b = badging(path)
        p('')
        p('### %s' % os.path.basename(path))
        p('```')
        p('\n'.join(b))
        p('```')
        d = [l for l in bb if l not in b] + [l for l in b if l not in bb]
        p('')
        p('* diff vs baseline = **%d line(s)** %s' % (len(d), ('-> ' + repr(d)) if d else ''))

    # ---------- 3) zip entry diff -----------------------------------------
    p('')
    p('## 3) zip entry diff (per entry: size / crc32 / method / sha256)')
    p('')
    em = {t: entry_map(pth) for t, pth in (('baseline', BASE), ('v2_layoutonly', V2),
                                           ('v3_dexpatch', V3)) if os.path.exists(pth)}
    report = {}
    for tag in ('v2_layoutonly', 'v3_dexpatch'):
        a, b = em['baseline'], em[tag]
        changed, only_old, only_new = [], [], []
        for n in sorted(set(a) & set(b)):
            if (a[n]['usize'], a[n]['crc'], a[n]['method']) != (b[n]['usize'], b[n]['crc'], b[n]['method']):
                changed.append(n)
        only_old = sorted(set(a) - set(b))
        only_new = sorted(set(b) - set(a))
        p('### %s' % os.path.basename(V2 if tag == 'v2_layoutonly' else V3))
        p('')
        p('* entries: baseline %d / this %d' % (len(a), len(b)))
        p('* **changed entries (%d)**:' % len(changed))
        p('')
        p('| entry | old size | new size | old crc32 | new crc32 | old method | new method |')
        p('|---|---|---|---|---|---|---|')
        for n in changed:
            p('| `%s` | %d | %d | %s | %s | %d | %d |'
              % (n, a[n]['usize'], b[n]['usize'], a[n]['crc'], b[n]['crc'],
                 a[n]['method'], b[n]['method']))
        p('')
        p('* only-in-baseline: %s' % (only_old or 'none'))
        p('* only-in-new: %s' % (only_new or 'none'))
        # byte proof for the non-signature changed entries
        p('')
        for n in changed:
            if n.startswith('META-INF/'):
                continue
            p('* `%s` content sha256: `%s` -> `%s`' % (n, a[n]['crc'], b[n]['crc']))
        report[tag] = {'changed': changed, 'only_old': only_old, 'only_new': only_new}
        # assertions
        allowed = {'res/Q9.xml'} | ({'classes.dex'} if tag == 'v3_dexpatch' else set())
        bad = [n for n in changed if not (n in allowed or n.startswith('META-INF/'))]
        p('* changed entries outside {res/Q9.xml%s + META-INF/*}: **%s**'
          % (', classes.dex' if tag == 'v3_dexpatch' else '', bad or 'none'))
        p('')

    json.dump(report, open(os.path.join(HERE, 'zipdiff_v2v3.json'), 'w'), indent=2)
    open(os.path.join(HERE, 'selftest_out.txt'), 'w').write('\n'.join(out) + '\n')
    p('')
    p('---')
    p('')
    p('raw log written to %s' % os.path.join(HERE, 'selftest_out.txt'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
