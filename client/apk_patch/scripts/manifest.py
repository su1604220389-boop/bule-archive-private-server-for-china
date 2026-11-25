#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Emit the baseline manifest (sha256 + sizes) for the apk_patch workspace."""
import zipfile, hashlib, os, json

BASE = r'C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\noroot\BA_noroot_prod_20261118_v1.apk'
OUT = r'C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\apk_patch\BASELINE_MANIFEST.json'


def sha(b):
    return hashlib.sha256(b).hexdigest()


def sha_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()


zf = zipfile.ZipFile(BASE, 'r')
by = {i.filename: i for i in zf.infolist()}

entries = {}
for name in ('AndroidManifest.xml', 'resources.arsc', 'classes.dex', 'classes2.dex',
             'res/Q9.xml', 'res/nW.xml', 'res/EQ.xml', 'res/o4.xml', 'res/Dk.xml',
             'assets/SDKConfigSettings.json'):
    data = zf.read(name)
    i = by[name]
    entries[name] = {
        'size': len(data),
        'sha256': sha(data),
        'crc32': '%08x' % (i.CRC & 0xffffffff),
        'zip_method': i.compress_type,
        'zip_csize': i.compress_size,
    }

ks = r'C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\noroot\ba_private.keystore'
man = {
    'generated_at': '2026-11-18T18:58+08:00',
    'base_apk': {
        'path': BASE,
        'size': os.path.getsize(BASE),
        'sha256': sha_file(BASE),
        'entries': len(zf.infolist()),
    },
    'backup_apk': {
        'path': r'C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\apk_patch\backup\BA_noroot_prod_20261118_v1.apk',
        'size': os.path.getsize(r'C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\apk_patch\backup\BA_noroot_prod_20261118_v1.apk'),
        'sha256': sha_file(r'C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\apk_patch\backup\BA_noroot_prod_20261118_v1.apk'),
    },
    'keystore': {
        'path': ks,
        'size': os.path.getsize(ks),
        'sha256': sha_file(ks),
        'alias': 'ba',
        'storepass': 'baserver',
    },
    'slim_apk': {
        'path': r'C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\apk_patch\slim\slim.apk',
        'size': os.path.getsize(r'C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\apk_patch\slim\slim.apk'),
        'sha256': sha_file(r'C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\apk_patch\slim\slim.apk'),
    },
    'entries': entries,
}
with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(man, f, ensure_ascii=False, indent=2)
print(open(OUT, encoding='utf-8').read())
