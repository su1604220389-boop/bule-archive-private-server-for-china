# -*- coding: utf-8 -*-
"""在项目全部 HAR 里找 ResUrl / AddressablesCatalogUrlRoots / api/state 的实例"""
import os, re, json, glob

ROOT = r'C:\Users\su\Desktop\大肥鱼项目\BAServer'
hars = []
for pat in ('**/*.har', '**/*.HAR'):
    hars += glob.glob(os.path.join(ROOT, pat), recursive=True)
hars = sorted(set(hars))
print("HAR 文件 %d 个：\n" % len(hars))
for h in hars:
    print("  %10d  %s" % (os.path.getsize(h), os.path.relpath(h, ROOT)))

def iter_text(h):
    try:
        with open(h, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()
    except Exception as e:
        return ''

print("\n" + "=" * 78)
for h in hars:
    t = iter_text(h)
    if not t:
        continue
    res = {}
    for needle in ('ResUrl', 'AddressablesCatalogUrlRoots', 'prodm39',
                   'static-qc.bluearchive', 'static-hs.bluearchive'):
        c = t.count(needle)
        if c:
            res[needle] = c
    if not res:
        continue
    print("\n### %s" % os.path.relpath(h, ROOT))
    for k, v in res.items():
        print("    %-28s x%d" % (k, v))
    # 抓所有 ResUrl 的值
    for m in re.finditer(r'ResUrl(?:\\?"|\\?\')\s*:\s*\\?"([^"\\]{0,200})', t):
        print("    ResUrl = %s" % m.group(1))
    # 抓所有 AddressablesCatalogUrlRoots 数组内容
    for m in re.finditer(r'AddressablesCatalogUrlRoots\\?"\s*:\s*\[(.{0,600}?)\]', t, re.S):
        print("    Roots  = [%s]" % m.group(1)[:500].replace('\\"', '"'))
