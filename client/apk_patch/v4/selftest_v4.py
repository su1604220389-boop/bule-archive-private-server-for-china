#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SELF-TEST for out/v4_login.apk  (run inside WSL: python3 selftest_v4.py)

Compares v4_login.apk against
  * v2_layoutonly.apk            <- the declared v4 baseline (must only differ in
                                    res/Q9.xml + META-INF/*)
  * BA_noroot_prod_20261118_v1.apk <- original repack baseline (for the arsc/dex
                                    "unchanged since the very beginning" proof)

Checks
  1 resources.arsc sha256 == cd8943ae...  (spec constant)
  2 classes.dex / classes2.dex / AndroidManifest.xml bytes == v2 == v1
  3 aapt dump badging : full-output diff v4 vs v2 == 0 lines
  4 zip entry diff (size/crc32/method) v4 vs v2 : only res/Q9.xml + META-INF/*
  5 apksigner verify --print-certs : v1, v2, v4 same signer certificate
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import zipfile

ROOT = '/mnt/c/Users/su/Desktop/大肥鱼项目/BAServer/work/ba/apk_patch'
V1 = os.path.join(ROOT, 'backup', 'BA_noroot_prod_20261118_v1.apk')
V2 = os.path.join(ROOT, 'out', 'v2_layoutonly.apk')
V4 = os.path.join(ROOT, 'out', 'v4_login.apk')
AXML_SRC = os.path.join(ROOT, 'v4', 'res_Q9_v4.axml')

ARSC_SHA = 'cd8943ae979fd434a6c1fee67e8129bba1bc4a452e1937d7d7e6052079eecb86'
V2_SHA = '562d528a951eaeb15ae3165ece4a7ceb91849bb21ef54c895c6f217f9a676d64'
V1_SHA = '5f8b79dd930b8d1420b5b686cbc978142b751eea47c4b090ba308482a0f2f5c6'
DEX_SHA = '56b3a73b3039db99'   # prefix printed in the v2 report (original classes.dex)
CERT_SHA = '94FA997BE0DEBB69F1C62D766664FA8A879839DC9F710F6EEBD0C413DEE99EBC'

OUT = []


def p(s=''):
    print(s)
    OUT.append(s)


def sh(cmd):
    r = subprocess.run(cmd, shell=True, capture_output=True)
    return r.returncode, (r.stdout.decode('utf-8', 'replace') +
                          r.stderr.decode('utf-8', 'replace'))


def sha_file(path, chunk=1 << 22):
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


def sha_entries(path, names):
    d = {}
    with zipfile.ZipFile(path) as z:
        have = set(z.namelist())
        for n in names:
            if n in have:
                b = z.read(n)
                d[n] = {'sha256': hashlib.sha256(b).hexdigest(), 'size': len(b)}
    return d


def main():
    ok = True
    p('# SELF-TEST v4_login.apk')
    p('')
    p('run at      : %s' % subprocess.run('date -Is', shell=True, capture_output=True)
      .stdout.decode().strip())
    p('v1 (原包重签) : %s' % V1)
    p('v2 (v4 基线)  : %s' % V2)
    p('v4 (本次)     : %s' % V4)
    p('')

    # ---------------- 0. digests / sizes ---------------------------------
    p('## 0) 包体 SHA-256 / 字节数')
    p('')
    p('| 包 | 字节 | sha256 |')
    p('|---|---|---|')
    info = {}
    for tag, path, want in (('v1', V1, V1_SHA), ('v2', V2, V2_SHA), ('v4', V4, None)):
        h = sha_file(path)
        sz = os.path.getsize(path)
        info[tag] = {'sha256': h, 'size': sz}
        mark = ''
        if want:
            mark = ' ✅' if h == want else ' ❌(spec %s)' % want
        p('| %s | %s | `%s`%s |' % (os.path.basename(path), '{:,}'.format(sz), h, mark))
        if want and h != want:
            ok = False
    p('')

    # ---------------- 1/2. arsc + dex + manifest --------------------------
    names = ['resources.arsc', 'classes.dex', 'classes2.dex',
             'AndroidManifest.xml', 'res/Q9.xml']
    per = {t: sha_entries(pt, names) for t, pt in (('v1', V1), ('v2', V2), ('v4', V4))}
    p('## 1) resources.arsc —— 必须与原始包逐字节相同')
    p('')
    p('| entry | v1 | v2 | v4 |')
    p('|---|---|---|---|')
    for n in names:
        cells = []
        for t in ('v1', 'v2', 'v4'):
            d = per[t].get(n)
            cells.append('`%s…` (%d B)' % (d['sha256'][:16], d['size']) if d else '-')
        p('| `%s` | %s | %s | %s |' % (n, cells[0], cells[1], cells[2]))
    p('')
    arsc_ok = per['v4']['resources.arsc']['sha256'] == ARSC_SHA
    p('* v4 `resources.arsc` sha256 = `%s`' % per['v4']['resources.arsc']['sha256'])
    p('* 规范常量                    = `%s`' % ARSC_SHA)
    p('* => **%s**' % ('一致 ✅' if arsc_ok else '不一致 ❌'))
    ok = ok and arsc_ok
    p('')

    p('## 2) classes.dex / classes2.dex / AndroidManifest.xml —— 逐字节不变')
    p('')
    for n in ('classes.dex', 'classes2.dex', 'AndroidManifest.xml'):
        v1h, v2h, v4h = (per[t][n]['sha256'] for t in ('v1', 'v2', 'v4'))
        same = (v1h == v2h == v4h)
        ok = ok and same
        p('* `%s`  sha256 = `%s`  (%d B)' % (n, v4h, per['v4'][n]['size']))
        p('  * v1 == v2 == v4 : **%s**%s' % (same, '' if same else
                                              '  v1=%s v2=%s' % (v1h, v2h)))
    p('')
    p('* （对照）原始 `classes.dex` 前 16 位应为 `%s`：%s'
      % (DEX_SHA, '一致 ✅' if per['v4']['classes.dex']['sha256'].startswith(DEX_SHA)
         else '不一致 ❌'))
    p('')

    # ---------------- 3. aapt dump badging --------------------------------
    p('## 3) `aapt dump badging` —— 与 v2 基线 diff')
    p('')
    _, b2 = sh('aapt dump badging "%s"' % V2)
    _, b4 = sh('aapt dump badging "%s"' % V4)
    l2 = [re.sub(r'\s+', ' ', l.strip()) for l in b2.splitlines() if l.strip()]
    l4 = [re.sub(r'\s+', ' ', l.strip()) for l in b4.splitlines() if l.strip()]
    import difflib
    diff = list(difflib.unified_diff(l2, l4, 'v2', 'v4', lineterm='', n=1))
    p('* v2 行数 = %d, v4 行数 = %d' % (len(l2), len(l4)))
    p('* **diff 行数 = %d**' % len(diff))
    if diff:
        p('')
        p('```diff')
        for l in diff[:80]:
            p(l)
        p('```')
        ok = False
    p('')
    p('* v4 badging 前 6 行：')
    p('')
    p('```')
    for l in l4[:6]:
        p(l)
    p('```')
    p('')

    # ---------------- 4. zip entry diff -----------------------------------
    p('## 4) zip 条目 diff（v4 vs v2，按 name + size + crc32 + method）')
    p('')
    e2 = entry_map(V2)
    e4 = entry_map(V4)
    changed = [n for n in sorted(set(e2) & set(e4))
               if (e2[n]['usize'], e2[n]['crc'], e2[n]['method']) !=
                  (e4[n]['usize'], e4[n]['crc'], e4[n]['method'])]
    only_v2 = sorted(set(e2) - set(e4))
    only_v4 = sorted(set(e4) - set(e2))
    p('* 条目数：v2 = %d, v4 = %d' % (len(e2), len(e4)))
    p('* **变化条目 (%d)**：' % len(changed))
    p('')
    p('| entry | v2 size | v4 size | v2 crc32 | v4 crc32 | v2 method | v4 method |')
    p('|---|---|---|---|---|---|---|')
    for n in changed:
        p('| `%s` | %d | %d | %s | %s | %d | %d |'
          % (n, e2[n]['usize'], e4[n]['usize'], e2[n]['crc'], e4[n]['crc'],
             e2[n]['method'], e4[n]['method']))
    p('')
    p('* 只在 v2：%s' % (only_v2 or '无'))
    p('* 只在 v4：%s' % (only_v4 or '无'))
    bad = [n for n in changed if not (n == 'res/Q9.xml' or n.startswith('META-INF/'))]
    p('')
    p('* 允许集合 = {`res/Q9.xml`} ∪ `META-INF/*`')
    p('* 超出允许集合的条目：**%s**' % (bad or '无')
      if not bad else '* 超出允许集合的条目：**%s** ❌' % bad)
    ok = ok and not bad and not only_v2 and not only_v4
    p('')
    p('* META-INF 变化条目明细：')
    p('')
    for n in changed:
        if n.startswith('META-INF/'):
            p('  * `%s`  %d B -> %d B' % (n, e2[n]['usize'], e4[n]['usize']))
    p('')

    # Q9.xml content sha vs the source AXML we fed the builder
    with zipfile.ZipFile(V4) as z:
        q9 = z.read('res/Q9.xml')
    h_q9 = hashlib.sha256(q9).hexdigest()
    h_src = sha_file(AXML_SRC)
    p('* `res/Q9.xml` in package : %d B  sha256=`%s`' % (len(q9), h_q9))
    p('* fed AXML file           : %d B  sha256=`%s`' % (os.path.getsize(AXML_SRC), h_src))
    p('* 一致：**%s**' % (h_q9 == h_src))
    ok = ok and h_q9 == h_src
    p('')

    # ---------------- 5. apksigner ----------------------------------------
    p('## 5) `apksigner verify --print-certs`')
    p('')
    for tag, path in (('v1', V1), ('v2', V2), ('v4', V4)):
        rc, o = sh('apksigner verify --verbose --print-certs "%s"' % path)
        p('### %s  -> exit %d' % (os.path.basename(path), rc))
        p('')
        p('```')
        for l in o.strip().splitlines():
            if any(k in l for k in ('Verifies', 'Verified using', 'Number of signers',
                                    'Signer #1 certificate DN',
                                    'Signer #1 certificate SHA-256',
                                    'Signer #1 certificate SHA-1',
                                    'Signer #1 certificate MD5', 'WARNING')):
                p(l)
        p('```')
        p('')
        if rc != 0:
            ok = False
        if tag == 'v4':
            ok = ok and (CERT_SHA in o.upper() or CERT_SHA.lower() in o.lower())
            p('* v4 签名证书 == 原签名证书 `%s` : **%s**'
              % (CERT_SHA, 'yes' if CERT_SHA.lower() in o.lower() else 'NO'))
            p('')

    # ---------------- verdict ---------------------------------------------
    p('## 结论')
    p('')
    p('**ALL CHECKS %s**' % ('PASSED ✅' if ok else 'FAILED ❌'))
    p('')

    txt = '\n'.join(OUT) + '\n'
    open(os.path.join(ROOT, 'v4', 'selftest_v4_out.txt'), 'w',
         encoding='utf-8', newline='\n').write(txt)
    json.dump({'changed': changed, 'only_v2': only_v2, 'only_v4': only_v4,
               'badging_diff_lines': len(diff), 'ok': ok},
              open(os.path.join(ROOT, 'v4', 'zipdiff_v4.json'), 'w'), indent=2)
    print('\n--- written to v4/selftest_v4_out.txt ; ALL=%s' % ok)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
