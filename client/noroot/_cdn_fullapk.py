# -*- coding: utf-8 -*-
"""全 APK 穷举：任意条目里是否存在资源 CDN 关键串（明文，流式，低内存）
这是"CDN 是否硬编码在 APK 里"的终局判据。
"""
import zipfile, sys, time

APK = r'C:\Users\su\Desktop\大肥鱼项目\BAServer\report\_tmp\cn_base.apk'
NEEDLES = [
    b'prodm39',
    b'static.bluearchive-cn.com',
    b'static-qc.bluearchive-cn.com',
    b'static-hs.bluearchive-cn.com',
    b'AddressablesCatalogUrlRoots',
    b'PlatformUtils.AddressableLoadPath',
]

def main():
    z = zipfile.ZipFile(APK)
    infos = z.infolist()
    print("条目总数 %d" % len(infos), flush=True)
    hits = {n: [] for n in NEEDLES}
    scanned = 0
    t0 = time.time()
    for idx, i in enumerate(infos):
        if i.is_dir():
            continue
        try:
            with z.open(i) as f:
                while True:
                    chunk = f.read(4 << 20)
                    if not chunk:
                        break
                    for n in NEEDLES:
                        if n in chunk:
                            hits[n].append((i.filename, i.file_size, chunk.count(n)))
            scanned += i.file_size
        except Exception as e:
            print("  [ERR] %s %s" % (i.filename, e), flush=True)
        if idx % 4000 == 0:
            print("  ... %d/%d entries, %.1f MB, %.1fs" % (idx, len(infos), scanned / 1e6, time.time() - t0), flush=True)

    print("\n扫描字节数 %.1f MB  用时 %.1fs" % (scanned / 1e6, time.time() - t0))
    print("=" * 70)
    for n in NEEDLES:
        print("\n### %r" % n.decode())
        if not hits[n]:
            print("  0 命中 —— 全 APK 任何条目都不含此串")
        else:
            for fn, sz, c in hits[n]:
                print("  %-70s  size=%-12d count=%d" % (fn, sz, c))

if __name__ == '__main__':
    main()
