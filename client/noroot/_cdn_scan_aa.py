# -*- coding: utf-8 -*-
"""深挖 assets/aa/ 下的 Addressables 配置：settings.json 字符串 + catalog.json 流式扫 URL/占位符"""
import re, zipfile, sys

apk = r'C:\Users\su\Desktop\大肥鱼项目\BAServer\report\_tmp\cn_base.apk'
z = zipfile.ZipFile(apk)

print("=" * 70)
print("A) assets/aa/settings.json 全部可打印字符串")
print("=" * 70)
b = z.read('assets/aa/settings.json')
for m in re.finditer(rb'[\x20-\x7e]{4,}', b):
    s = m.group().decode()
    if len(set(s)) <= 2:   # 跳过 000000 / IIII 之类
        continue
    print("  %5d  %s" % (m.start(), s))

print()
print("=" * 70)
print("B) assets/aa/catalog.json 流式扫描")
print("=" * 70)
info = z.getinfo('assets/aa/catalog.json')
print("  条目大小:", info.file_size)
CH = 8 << 20
pat_http = re.compile(rb'https?://[^\x00"\'\\ ]{4,300}')
pat_ph = re.compile(rb'\{[A-Za-z][A-Za-z0-9_.]{2,80}\}')
pat_needle = re.compile(rb'(?i)(prodm39|bluearchive-cn|RemoteLoadPath|RemoteLoadPathRoot|AddressablesCatalogUrlRoots|static\.)')

found_url = {}
found_ph = {}
found_needle = {}
off = 0
with z.open('assets/aa/catalog.json') as f:
    carry = b''
    while True:
        chunk = f.read(CH)
        if not chunk:
            break
        buf = carry + chunk
        base = off - len(carry)
        for m in pat_http.finditer(buf):
            s = m.group()
            if s not in found_url:
                found_url[s] = base + m.start()
        for m in pat_ph.finditer(buf):
            s = m.group()
            if s not in found_ph:
                found_ph[s] = base + m.start()
        for m in pat_needle.finditer(buf):
            s = m.group()
            if s not in found_needle:
                found_needle[s] = base + m.start()
        carry = buf[-512:]
        off += len(chunk)
        if off > 200 << 20:
            break

print("\n  [URL 字面量] %d 个" % len(found_url))
for s, o in sorted(found_url.items(), key=lambda x: x[1])[:60]:
    print("    0x%08x  %s" % (o, s.decode('latin1')))
print("\n  [{占位符}] %d 个" % len(found_ph))
for s, o in sorted(found_ph.items(), key=lambda x: x[1])[:60]:
    print("    0x%08x  %s" % (o, s.decode('latin1')))
print("\n  [关键字] %d 个" % len(found_needle))
for s, o in sorted(found_needle.items(), key=lambda x: x[1])[:60]:
    print("    0x%08x  %s" % (o, s.decode('latin1')))
