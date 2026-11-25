#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SELF-TEST for out/v5_login.apk  (Windows python, shells out to WSL for aapt/apksigner).

Baseline for THIS version is v4_login.apk (v5 = v4 + the re-added
游客登录 / 卡密登录 strip).  The original repack baseline
BA_noroot_prod_20261118_v1.apk is carried along so the "nothing but the layout
ever changed" chain is still visible.

Checks
  1 resources.arsc sha256 == cd8943ae...              (spec constant)
  2 classes.dex sha256 == 56b3a73b...                 (v4 constant, 1 byte untouched)
  3 classes2.dex / AndroidManifest.xml sha256 == v4   (and == v1)
  4 aapt dump badging  v5 vs v4 : diff == 0 lines
  5 zip entry diff (size/crc32/method) v5 vs v4 : only res/Q9.xml + META-INF/*
  6 apksigner verify --verbose --print-certs : pass, same cert as v4
  7 full-file sha256 + byte size of v5
"""
import difflib
import hashlib
import json
import os
import subprocess
import sys
import zipfile

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
ROOT = os.path.abspath(ROOT)
V1 = os.path.join(ROOT, 'backup', 'BA_noroot_prod_20261118_v1.apk')
V4 = os.path.join(ROOT, 'out', 'v4_login.apk')
V5 = os.path.join(ROOT, 'out', 'v5_login.apk')
AXML = os.path.join(ROOT, 'v5', 'res_Q9_v5.axml')
HERE = os.path.dirname(os.path.abspath(__file__))

ARSC_SHA = 'cd8943ae979fd434a6c1fee67e8129bba1bc4a452e1937d7d7e6052079eecb86'
DEX_SHA = '56b3a73b3039db99ade67faf42e471c8de4dcd7127ce9bef49d9f4d473c27651'
DEX2_SHA = 'dca6f88a614fd7666842eed9d11d3f6bf9c842e381b80a63a330cbb78c93a7b4'
MAN_SHA = '9a07ec83802b9b6fc08582b9429d9649775fe8627c35be419a3b851f1ffaca11'
CERT_SHA = '94fa997be0debb69f1c62d766664fa8a879839dc9f710f6eebd0c413dee99ebc'

WATCH = ('resources.arsc', 'classes.dex', 'classes2.dex', 'AndroidManifest.xml',
         'res/Q9.xml')

OUT = []
FAIL = []


def p(s=''):
    print(s)
    OUT.append(s)


def sha_file(path):
    h = hashlib.sha256()
    n = 0
    with open(path, 'rb') as f:
        while True:
            b = f.read(1 << 22)
            if not b:
                break
            n += len(b)
            h.update(b)
    return h.hexdigest(), n


def sha_entry(apk, name):
    with zipfile.ZipFile(apk) as z:
        b = z.read(name)
    return hashlib.sha256(b).hexdigest(), len(b)


def wsl(cmd, timeout=1200):
    r = subprocess.run(['wsl', '-e', 'bash', '-lc', cmd], capture_output=True,
                       text=True, encoding='utf-8', errors='replace',
                       timeout=timeout)
    return r.returncode, (r.stdout or '') + (r.stderr or '')


def main():
    p('# SELF-TEST v5_login.apk')
    p('')
    p('* v5 (本次) : `%s`' % V5)
    p('* v4 (基线) : `%s`' % V4)
    p('* v1 (原包) : `%s`' % V1)
    p('* 布局源   : `%s`' % AXML)
    p('')

    # ---------------------------------------------------- 0 full file hash ---
    p('## 0) 包体 SHA-256 / 字节数')
    p('')
    sizes = {}
    hashes = {}
    for tag, path in (('v1', V1), ('v4', V4), ('v5', V5)):
        h, n = sha_file(path)
        sizes[tag] = n
        hashes[tag] = h
        p('* %-3s %16s B  sha256 = `%s`' % (tag, format(n, ','), h))
    p('')
    p('* v5 体积 = v4 %s B -> v5 %s B  (Δ %+d B)'
      % (format(sizes['v4'], ','), format(sizes['v5'], ','),
         sizes['v5'] - sizes['v4']))
    p('')

    # ------------------------------------- 1/2/3 arsc + dex + manifest -----
    p('## 1) `resources.arsc` / `classes.dex` / `classes2.dex` / `AndroidManifest.xml`')
    p('')
    p('| entry | v1 sha256 | v4 sha256 | v5 sha256 | v1==v4==v5 |')
    p('|---|---|---|---|---|')
    table = {}
    for name in WATCH:
        row = {}
        for tag, apk in (('v1', V1), ('v4', V4), ('v5', V5)):
            row[tag] = sha_entry(apk, name)
        table[name] = row
        same = row['v1'][0] == row['v4'][0] == row['v5'][0]
        p('| `%s` | `%s…` (%d B) | `%s…` (%d B) | `%s…` (%d B) | %s |'
          % (name, row['v1'][0][:16], row['v1'][1], row['v4'][0][:16], row['v4'][1],
             row['v5'][0][:16], row['v5'][1], '✅' if same else '❌'))
    p('')
    arsc = table['resources.arsc']['v5'][0]
    p('* v5 `resources.arsc` sha256 = `%s`' % arsc)
    p('* 规范常量                  = `%s`' % ARSC_SHA)
    p('* => %s' % ('**一致 ✅**' if arsc == ARSC_SHA else '**不一致 ❌**'))
    if arsc != ARSC_SHA:
        FAIL.append('resources.arsc sha256 mismatch')
    p('')
    for name, const in (('classes.dex', DEX_SHA), ('classes2.dex', DEX2_SHA),
                        ('AndroidManifest.xml', MAN_SHA)):
        got = table[name]['v5'][0]
        p('* `%s` sha256 = `%s`' % (name, got))
        p('  * 与常量 `%s` : %s' % (const[:16] + '…',
                                    '一致 ✅' if got == const else '不一致 ❌'))
        if got != const:
            FAIL.append('%s sha256 mismatch' % name)
        if table[name]['v4'][0] != got:
            FAIL.append('%s differs from v4' % name)
    p('')

    # ------------------------------------------- 4 aapt dump badging --------
    p('## 2) `aapt dump badging` —— v5 vs v4，diff 行数')
    p('')
    bd = {}
    for tag, apk in (('v4', V4), ('v5', V5)):
        rc, o = wsl('aapt dump badging "%s" 2>&1' % apk.replace('\\', '/')
                    .replace('C:', '/mnt/c'))
        bd[tag] = o
        fn = os.path.join(HERE, 'badging_%s.txt' % tag)
        open(fn, 'w', encoding='utf-8', newline='\n').write(o)
        p('* aapt dump badging %s -> exit %d, %d 行, 存 `%s`'
          % (tag, rc, o.count('\n'), os.path.basename(fn)))
        if rc != 0:
            FAIL.append('aapt dump badging %s rc=%d' % (tag, rc))
    diff = list(difflib.unified_diff(bd['v4'].splitlines(), bd['v5'].splitlines(),
                                     'v4', 'v5', lineterm=''))
    p('* diff 行数 = **%d**  %s' % (len(diff), '✅' if len(diff) == 0 else '❌'))
    if diff:
        FAIL.append('badging diff %d lines' % len(diff))
        for l in diff[:60]:
            p('    ' + l)
    p('')

    # ------------------------------------------------- 5 zip entry diff -----
    p('## 3) zip 条目 diff（v5 vs v4）')
    p('')
    with zipfile.ZipFile(V4) as z4, zipfile.ZipFile(V5) as z5:
        i4 = {i.filename: i for i in z4.infolist()}
        i5 = {i.filename: i for i in z5.infolist()}
    only4 = sorted(set(i4) - set(i5))
    only5 = sorted(set(i5) - set(i4))
    changed = []
    for n in sorted(set(i4) & set(i5)):
        a, b = i4[n], i5[n]
        if (a.CRC, a.file_size, a.compress_size, a.compress_type) != \
           (b.CRC, b.file_size, b.compress_size, b.compress_type):
            changed.append(n)
    p('* v4 条目数 = %d, v5 条目数 = %d' % (len(i4), len(i5)))
    p('* only in v4 : %s' % (only4 or '[]'))
    p('* only in v5 : %s' % (only5 or '[]'))
    p('* 内容有差异的条目 (%d) :' % len(changed))
    for n in changed:
        a, b = i4[n], i5[n]
        p('    * `%s`: %d B (csize %d, crc %08X) -> %d B (csize %d, crc %08X)'
          % (n, a.file_size, a.compress_size, a.CRC,
             b.file_size, b.compress_size, b.CRC))
    expected_extra = {'res/Q9.xml'}
    bad_changed = [n for n in changed
                   if n not in expected_extra and not n.startswith('META-INF/')]
    p('* 只允许 `res/Q9.xml` + `META-INF/*` 变化 -> %s'
      % ('✅' if (not bad_changed and not only4 and not only5) else '❌ %s' % bad_changed))
    if bad_changed or only4 or only5:
        FAIL.append('zip diff unexpected entries')
    p('* v5 内 `res/Q9.xml` : %d B, sha256 = `%s`（磁盘上的 res_Q9_v5.axml sha256 = `%s`）'
      % (table['res/Q9.xml']['v5'][1], table['res/Q9.xml']['v5'][0],
         hashlib.sha256(open(AXML, 'rb').read()).hexdigest()))
    p('')
    json.dump({'changed': changed, 'only_v4': only4, 'only_v5': only5,
               'badging_diff_lines': len(diff),
               'ok': not FAIL},
              open(os.path.join(HERE, 'zipdiff_v5.json'), 'w', encoding='utf-8'),
              indent=2)

    # ------------------------------------------- 6 apksigner / certificate --
    p('## 4) `apksigner verify --verbose --print-certs`')
    p('')
    sigs = {}
    for tag, apk in (('v4', V4), ('v5', V5)):
        rc, o = wsl('apksigner verify --verbose --print-certs "%s"' %
                    apk.replace('\\', '/').replace('C:', '/mnt/c'))
        sigs[tag] = o
        open(os.path.join(HERE, 'sig_%s.txt' % tag), 'w', encoding='utf-8',
             newline='\n').write(o)
        p('### %s  -> exit %d' % (os.path.basename(apk), rc))
        p('')
        p('```')
        p('\n'.join(l for l in o.strip().splitlines()
                    if l.startswith(('Verifies', 'Verified using', 'Number of',
                                     'Signer #1 certificate', 'WARNING', 'ERROR'))))
        p('```')
        if rc != 0:
            FAIL.append('apksigner verify %s rc=%d' % (tag, rc))
        p('')
    cert5 = [l for l in sigs['v5'].splitlines() if 'certificate SHA-256' in l]
    cert4 = [l for l in sigs['v4'].splitlines() if 'certificate SHA-256' in l]
    p('* v5 证书 SHA-256 行 : `%s`' % (cert5[0].strip() if cert5 else '(none)'))
    p('* v4 证书 SHA-256 行 : `%s`' % (cert4[0].strip() if cert4 else '(none)'))
    ok_cert = bool(cert5) and bool(cert4) and cert5 == cert4 and \
        CERT_SHA in cert5[0].lower()
    p('* 与 v4 同一张证书 + 等于常量 94FA…EBC : %s' % ('✅' if ok_cert else '❌'))
    if not ok_cert:
        FAIL.append('certificate mismatch')

    p('')
    p('---')
    p('')
    p('**%s**' % ('ALL CHECKS PASSED ✅' if not FAIL else 'FAILED ❌ %s' % FAIL))
    open(os.path.join(HERE, 'selftest_v5_out.txt'), 'w', encoding='utf-8',
         newline='\n').write('\n'.join(OUT) + '\n')
    print('\n[written] %s' % os.path.join(HERE, 'selftest_v5_out.txt'))
    return 0 if not FAIL else 1


if __name__ == '__main__':
    sys.exit(main())
