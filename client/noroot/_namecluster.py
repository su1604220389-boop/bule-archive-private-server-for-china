# -*- coding: utf-8 -*-
"""名字簇提取：在 metadata 的某个区段里，对每个偏移自动找"能让其后若干字节成为标识符"的单字节 key。
用于判读 IL2CPP 字符串堆中 ResUrls / LocalizeConfig 这类名字的邻接关系。
"""
import re, sys, zipfile

APK = r'C:\Users\su\Desktop\大肥鱼项目\BAServer\report\_tmp\cn_base.apk'
IDENT = re.compile(rb'[A-Za-z_][A-Za-z0-9_]{2,60}')
IDENT2 = re.compile(rb'[A-Za-z_<`][A-Za-z0-9_<>`.]{2,80}')
VALID = re.compile(r'^[A-Za-z_<][A-Za-z0-9_<>`.@/$-]*$')

def load():
    z = zipfile.ZipFile(APK)
    return z.read('assets/bin/Data/Managed/Metadata/global-metadata.dat')

def extract(buf, lo, hi, minlen=4, maxlen=64):
    """在 [lo,hi) 内找出所有 (offset,key,string)，要求 string 是合法标识符且 key 唯一确定"""
    out = {}
    seg = buf[lo:hi]
    n = len(seg)
    for p in range(max(0, n - 2)):
        for key in range(256):
            # 快速试探：前 3 字节必须都以该 key 落在标识符字符集
            b0, b1, b2 = seg[p] ^ key, seg[p + 1] ^ key, seg[p + 2] ^ key
            if not (65 <= b0 <= 90 or 97 <= b0 <= 122 or b0 in (95, 60)):
                continue
            if not (65 <= b1 <= 90 or 97 <= b1 <= 122 or 48 <= b1 <= 57 or b1 in (95,)):
                continue
            if not (65 <= b2 <= 90 or 97 <= b2 <= 122 or 48 <= b2 <= 57 or b2 in (95,)):
                continue
            s = bytearray()
            q = p
            while q < n and len(s) < maxlen:
                c = seg[q] ^ key
                ch = chr(c)
                if VALID.match(ch):
                    s.append(c)
                    q += 1
                else:
                    break
            if len(s) >= minlen:
                out.setdefault((lo + p, key), bytes(s).decode())
    return out

def main():
    lo = int(sys.argv[1], 0)
    hi = int(sys.argv[2], 0)
    buf = load()
    hits = extract(buf, lo, hi)
    # 按偏移排序；同一偏移只保留最长的
    byoff = {}
    for (off, key), s in hits.items():
        if off not in byoff or len(s) > len(byoff[off][1]):
            byoff[off] = (key, s)
    print("区段 0x%x..0x%x ，提取到 %d 个候选名字\n" % (lo, hi, len(byoff)))
    for off in sorted(byoff):
        key, s = byoff[off]
        mark = ""
        if any(k in s for k in ('ResUrl', 'Localize', 'IsLocalize')):
            mark = "   <<<<"
        print("  0x%08x key=0x%02x  %s%s" % (off, key, s, mark))

if __name__ == '__main__':
    main()
