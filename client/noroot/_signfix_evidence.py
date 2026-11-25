#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把"改前 / 改后"的 .SF 与 MANIFEST 原始字节并排打印出来（写 SIGNER_FIXES.md 用）。

只调用两个版本的 build_v1()，不构建 APK、不写产物。
"""
import base64
import hashlib
import importlib.util
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))


def load(path, name):
    tmp = tempfile.mkdtemp(prefix='evid')
    dst = os.path.join(tmp, name + '.py')
    shutil.copyfile(path, dst)
    spec = importlib.util.spec_from_file_location(name, dst)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


LONG = ('assets/audio/voc_jp/jp_shirokoridingsuit/'
        'shirokoridingsuit_battle_tacticalaction_1.ogg')
ITEMS = [('res/Dk.xml', hashlib.sha256(b'nsc').digest()),
         (LONG, hashlib.sha256(b'ogg').digest())]


def show(title, blob, limit=1400):
    print('---- %s (%d B) ----' % (title, len(blob)))
    txt = blob.decode('utf-8', 'replace')
    for ln in txt.split('\r\n'):
        print('  |%s|' % ln)
        limit -= len(ln) + 3
        if limit <= 0:
            print('  |...（截断）')
            break
    print()


def main():
    old = load(os.path.join(HERE, 'build_noroot_apk.py.orig'), 'mod_old')
    new = load(os.path.join(HERE, 'build_noroot_apk.py'), 'mod_new')

    for tag, mod in (('改前 (build_noroot_apk.py.orig)', old),
                     ('改后 (build_noroot_apk.py)', new)):
        mf, sf = mod.build_v1(ITEMS)
        lens = [len(x) for x in mf.split(b'\r\n')]
        print('==== %s ====' % tag)
        print('  MANIFEST.MF %d B, 最长行 %d B, >72 B 的行 %d 个, 续行 %d 条'
              % (len(mf), max(lens), sum(1 for n in lens if n > 72),
                 sum(1 for x in mf.split(b'\r\n') if x.startswith(b' '))))
        print('  CERT.SF     %d B' % len(sf))
        show(tag + ' CERT.SF', sf)
        show(tag + ' MANIFEST.MF', mf)


if __name__ == '__main__':
    main()
