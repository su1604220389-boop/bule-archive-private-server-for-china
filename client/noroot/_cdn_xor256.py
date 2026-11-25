# -*- coding: utf-8 -*-
"""×256 单字节 XOR 全扫：判定某字符串是否以任意单字节 key 存在于 metadata 字面量区
依据 report\\52-客户端补丁方案-metadata绕过登录.md §6.3 的方法
"""
import sys, re, zipfile, os

APK = r'C:\Users\su\Desktop\大肥鱼项目\BAServer\report\_tmp\cn_base.apk'

def load(target):
    if os.path.exists(target):
        with open(target, 'rb') as f:
            return f.read()
    z = zipfile.ZipFile(APK)
    return z.read(target)

def sweep(buf, needle, max_report=6):
    nb = needle.encode('ascii')
    hits = []
    total = 0
    for key in range(256):
        pat = bytes(c ^ key for c in nb)
        start = 0
        while True:
            p = buf.find(pat, start)
            if p < 0:
                break
            total += 1
            if len(hits) < max_report:
                hits.append((p, key))
            start = p + 1
            if total > 500:
                break
        if total > 500:
            break
    return total, hits

def ctx(buf, pos, n, key):
    lo = max(0, pos - 90)
    hi = min(len(buf), pos + n + 90)
    raw = bytes(c ^ key for c in buf[lo:hi])
    return ''.join(chr(c) if 32 <= c < 127 else '.' for c in raw)

def main():
    target = sys.argv[1]
    needles = sys.argv[2].split(',')
    buf = load(target)
    print("TARGET %s  %d B" % (target, len(buf)))
    print("方法: ×256 单字节 XOR（key=0 即明文）\n")
    for n in needles:
        total, hits = sweep(buf, n)
        if total == 0:
            print("### %-28s : 0 命中（×256 全 key 扫过，ASCII 形态）" % n)
        else:
            print("### %-28s : %d 命中" % (n, total))
            for pos, key in hits:
                print("      0x%08x key=0x%02x" % (pos, key))
                print("        %s" % ctx(buf, pos, len(n), key))
        print()

if __name__ == '__main__':
    main()
