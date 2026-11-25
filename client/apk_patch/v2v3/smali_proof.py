#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Third-party structural proof for the patched dex.

apktool.jar ships dexlib2.  We build a 3-entry mini apk (AndroidManifest.xml +
resources.arsc + the dex under test) and let `apktool d` disassemble it: dexlib2
refuses a structurally damaged dex, so a clean smali tree proves the dex still
parses.  Both dex files are processed and the smali trees are diffed -- the only
difference must be the single const-string in CommonUtil.isChinaPhoneLegal.

Read-only disassembly.  Nothing is ever reassembled.
"""
import os
import subprocess
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.abspath(os.path.join(HERE, '..', 'backup', 'BA_noroot_prod_20261118_v1.apk'))
JAR = '/opt/ba-tools/apktool.jar'
WORK = '/root/ba_work/mini'


def sh(cmd):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip()


os.makedirs(WORK, exist_ok=True)
patched = os.path.join(HERE, 'classes_patched.dex')
orig_dex = os.path.join(WORK, 'classes_orig.dex')
with zipfile.ZipFile(BASE) as z:
    orig_dex_bytes = z.read('classes.dex')
    man = z.read('AndroidManifest.xml')
    arsc = z.read('resources.arsc')
open(orig_dex, 'wb').write(orig_dex_bytes)
for tag, dex in (('orig', orig_dex), ('new', patched)):
    mini = os.path.join(WORK, 'mini_%s.apk' % tag)
    with zipfile.ZipFile(mini, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('AndroidManifest.xml', man)
        z.writestr('resources.arsc', arsc)
        z.writestr('classes.dex', open(dex, 'rb').read())
    d = os.path.join(WORK, 'dec_' + tag)
    rc, o = sh('java -jar %s d -f "%s" -o "%s"' % (JAR, mini, d))
    n = sum(len(f) for _, _, f in os.walk(d))
    print('[apktool d %s] rc=%d  files=%d' % (tag, rc, n))
    print('   ', o.replace('\n', ' | ')[:400])
    if rc != 0:
        raise SystemExit('apktool d FAILED on the %s dex' % tag)

rc, o = sh('diff -r %s/dec_orig %s/dec_new' % (WORK, WORK))
open(os.path.join(HERE, 'smali_diff.txt'), 'w').write(o)
print('\n=== smali tree diff (orig dex vs patched dex) ===')
print(o if o.strip() else '(no difference!)')
lines = [l for l in o.splitlines() if l.startswith(('<', '>'))]
print('\nchanged smali lines: %d' % len(lines))

p = os.path.join(WORK, 'dec_new', 'smali', 'com', 'airi', 'common', 'utils', 'CommonUtil.smali')
if os.path.exists(p):
    txt = open(p, encoding='utf-8').read()
    i = txt.find('.method public static isChinaPhoneLegal')
    print('\n=== patched CommonUtil.smali :: isChinaPhoneLegal ===')
    print(txt[i:i + 640])
