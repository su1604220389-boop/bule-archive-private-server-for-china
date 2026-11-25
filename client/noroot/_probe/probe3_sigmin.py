# -*- coding: utf-8 -*-
"""Probe 3: minSdk, META-INF, compression stats, alignment of key entries."""
import struct
import sys
import zipfile
from collections import Counter

sys.path.insert(0, r'work\ba\noroot\_probe')
from axml_arsc_probe import parse_axml  # noqa

APK = sys.argv[1] if len(sys.argv) > 1 else r'report\_tmp\cn_base.apk'
z = zipfile.ZipFile(APK)

# --- minSdk / targetSdk from binary manifest ---
pool, resmap, events = parse_axml(z.read('AndroidManifest.xml'))
print('=== uses-sdk / package ===')
for e in events:
    if e['name'] in ('manifest', 'uses-sdk'):
        for a in e['attrs']:
            val = a['data']
            if a['dtype'] == 0x03:
                val = pool.get(a['data'])
            print('  <%s> %-22s rid=0x%08x dt=0x%02x -> %s' %
                  (e['name'], a['name'], a['res_id'], a['dtype'], val))

# --- META-INF ---
print('\n=== META-INF (%d) ===' % len([n for n in z.namelist() if n.startswith('META-INF/')]))
for n in z.namelist():
    if n.startswith('META-INF/'):
        print('  ', n)

# --- compression stats ---
infos = z.infolist()
c = Counter(i.compress_type for i in infos)
print('\n=== compression types ===', dict(c))
stored = [i for i in infos if i.compress_type == zipfile.ZIP_STORED]
print('STORED count:', len(stored), ' total bytes:', sum(i.file_size for i in stored))
big = sorted(stored, key=lambda i: -i.file_size)[:12]
for i in big:
    print('   %-60s %10d' % (i.filename, i.file_size))

print('\n=== prefixes of STORED entries ===')
pref = Counter('/'.join(i.filename.split('/')[:2]) for i in stored)
for k, v in pref.most_common(15):
    print('   %-40s %d' % (k, v))


def local_data_offset(apk_path, info):
    with open(apk_path, 'rb') as f:
        f.seek(info.header_offset)
        hdr = f.read(30)
        sig, ver, flags, method, mt, md, crc, csz, usz, nlen, elen = struct.unpack('<IHHHHHIIIHH', hdr)
        if sig != 0x04034b50:
            return None, None
        return info.header_offset + 30 + nlen + elen, (elen, nlen)


print('\n=== alignment of STORED entries (data offset %% 4 / %% 4096) ===')
for name in ('resources.arsc', 'AndroidManifest.xml', 'res/Dk.xml', 'res/E5.ogg'):
    info = z.getinfo(name)
    off, extra = local_data_offset(APK, info)
    print('  %-22s stored=%s data_off=%-12d %%4=%d  %%4096=%-4d nlen/elen=%s' %
          (name, info.compress_type == 0, off, off % 4, off % 4096, extra))

print('\n=== EOCD / zip comment tail ===')
with open(APK, 'rb') as f:
    f.seek(-64, 2)
    tail = f.read()
print('  tail hex:', tail.hex())
print('  has APK Sig Block:', b'APK Sig Block 42' in tail)
