# -*- coding: utf-8 -*-
"""按给定偏移打印 zip 条目/文件 附近的上下文（可打印化），并列出周围的可打印字符串"""
import sys, re, zipfile, os

APK = r'C:\Users\su\Desktop\大肥鱼项目\BAServer\report\_tmp\cn_base.apk'

def read_range(target, start, end):
    if os.path.exists(target):
        with open(target, 'rb') as f:
            f.seek(start)
            return f.read(end - start)
    z = zipfile.ZipFile(APK)
    with z.open(target) as f:
        f.seek(start)
        return f.read(end - start)

def walk(target, offsets, back=120, fwd=200):
    lo = max(0, min(offsets) - back)
    hi = max(offsets) + fwd
    data = read_range(target, lo, hi)
    print("=" * 78)
    print("TARGET %s  window [0x%x, 0x%x)" % (target, lo, hi))
    print("=" * 78)
    for o in offsets:
        rel = o - lo
        print("\n--- offset 0x%08x ---" % o)
        ctx = data[max(0, rel - 120): rel + 200]
        s = ''.join(chr(c) if 32 <= c < 127 else '.' for c in ctx)
        print("  %s" % s)
        # 该窗口内的所有 >=4 可打印串
        print("  含 %d 字符以上可打印串:" % 4)
        for m in re.finditer(rb'[\x20-\x7e]{4,}', ctx):
            print("     +%4d  %s" % (max(0, rel - 120) + m.start(), m.group().decode()))

if __name__ == '__main__':
    target = sys.argv[1]
    offs = [int(x, 0) for x in sys.argv[2].split(',')]
    walk(target, offs)
