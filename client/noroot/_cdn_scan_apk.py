# -*- coding: utf-8 -*-
"""APK 静态配置扫描：找资源 CDN 地址是否硬编码。
只读 zip，不修改 APK。
用法: python _cdn_scan_apk.py <apk> [--list] [--scan]
"""
import sys, os, json, re, zipfile, collections

apk = sys.argv[1]
CONF_EXT = ('.json', '.txt', '.bytes', '.cfg', '.ini', '.dat', '.xml', '.yaml', '.yml', '.csv')
URLRE = re.compile(rb'(?i)https?://[A-Za-z0-9._~:/?#\[\]@!$&\'()*+,;=%-]{4,200}')
HOSTRE = re.compile(rb'(?i)[A-Za-z0-9][A-Za-z0-9.-]{2,80}\.(?:com|cn|net|org|io|cc|xyz|top|xyz)\b')

NEEDLES = [b'prodm39', b'AddressablesCatalogUrlRoots', b'AddressablesCatalog', b'ResUrl',
           b'ResUrls', b'bluearchive-cn', b'static.bluearchive', b'cdn.bluearchive',
           b'ResourceVersion', b'TableVersion', b'MediaVersion', b'PatchVersion',
           b'TableCatalog', b'MediaCatalog', b'VersionInfo', b'AssetBundle',
           b'cdn', b'CDN', b'Patch', b'bundle', b'Bundle']

def main():
    z = zipfile.ZipFile(apk)
    infos = z.infolist()
    print("== APK 条目总数: %d ==" % len(infos))

    # ---- 1. assets/ 下的配置型条目
    assets = [i for i in infos if i.filename.startswith('assets/')]
    print("== assets/ 条目数: %d ==" % len(assets))
    conf = [i for i in assets if i.filename.lower().endswith(CONF_EXT)]
    print("== assets/ 配置型条目(json/txt/bytes/cfg/ini/dat/xml/...): %d ==" % len(conf))
    tot = 0
    for i in sorted(conf, key=lambda x: -x.file_size):
        tot += i.file_size
        print("  %12d  %s" % (i.file_size, i.filename))
    print("== 配置型条目合计 %d B ==" % tot)

    # ---- 2. assets/ 根目录直接子项
    print("\n== assets/ 根目录直接子项 ==")
    roots = collections.OrderedDict()
    for i in assets:
        rest = i.filename[len('assets/'):]
        if '/' in rest:
            roots.setdefault(rest.split('/')[0] + '/', 0)
            roots[rest.split('/')[0] + '/'] += i.file_size
        else:
            roots.setdefault(rest, 0)
            roots[rest] += i.file_size
    for k, v in sorted(roots.items()):
        print("  %14s  %s" % (v, k))

    # ---- 3. 扫描配置型条目里的 URL / 命中词
    print("\n== 扫描配置型条目: URL 与关键字 ==")
    for i in conf:
        if i.file_size > 8 * 1024 * 1024:
            print("  [SKIP>8MB] %s" % i.filename)
            continue
        try:
            data = z.read(i)
        except Exception as e:
            print("  [ERR] %s %s" % (i.filename, e))
            continue
        urls = set(URLRE.findall(data))
        hits = [n for n in NEEDLES if n in data]
        if urls or hits:
            print("\n  --- %s (%d B) ---" % (i.filename, i.file_size))
            for u in sorted(urls):
                print("      URL %s" % u.decode('latin1'))
            if hits:
                print("      NEEDLES %s" % [h.decode('latin1') for h in hits])

if __name__ == '__main__':
    main()
