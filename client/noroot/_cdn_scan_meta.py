# -*- coding: utf-8 -*-
"""多编码关键词扫描：明文 / XOR 0x20 / UTF-16LE / UTF-16BE / UTF-16LE^0x20
用法: python _cdn_scan_meta.py <zip条目名或文件路径> <needle1,needle2,...>
输出每个命中：偏移 + 三种解码后的上下文（各 80 字符）
"""
import sys, re, zipfile, os

APK = r'C:\Users\su\Desktop\大肥鱼项目\BAServer\report\_tmp\cn_base.apk'
CH = 8 << 20
CTX = 80

def xor20(b):
    return bytes(c ^ 0x20 for c in b)

def variants(n):
    nb = n.encode('ascii')
    out = {
        'plain':      nb,
        'xor20':      xor20(nb),
        'utf16le':    n.encode('utf-16-le'),
        'utf16be':    n.encode('utf-16-be'),
        'utf16le^20': xor20(n.encode('utf-16-le')),
    }
    return out

def decode_ctx(buf, pos, length, mode):
    lo = max(0, pos - CTX)
    hi = min(len(buf), pos + length + CTX)
    raw = buf[lo:hi]
    if mode in ('plain', 'xor20'):
        s = xor20(raw) if mode == 'xor20' else raw
        s = s.decode('latin1')
        s = ''.join(ch if 32 <= ord(ch) < 127 else '.' for ch in s)
        return s
    else:
        if mode == 'utf16be':
            raw = bytes(b for pair in zip(raw[1::2], raw[0::2]) for b in pair)
        if mode.endswith('^20'):
            raw = xor20(raw)
        try:
            s = raw.decode('utf-16-le', 'replace')
        except Exception:
            s = repr(raw)
        s = ''.join(ch if 32 <= ord(ch) < 127 else '.' for ch in s)
        return s

def open_stream(target):
    if os.path.exists(target):
        return open(target, 'rb'), os.path.getsize(target)
    z = zipfile.ZipFile(APK)
    i = z.getinfo(target)
    return z.open(target), i.file_size

def scan(target, needles):
    f, size = open_stream(target)
    print("=" * 78)
    print("TARGET: %s  (%d B)" % (target, size))
    print("=" * 78)
    # 每个 needle 每种编码：(count, first_offsets[])
    results = {n: {m: [0, []] for m in variants(n)} for n in needles}
    maxlen = max(len(m) for n in needles for m in variants(n).values())
    off = 0
    carry_b = b''
    while True:
        chunk = f.read(CH)
        if not chunk:
            break
        buf = carry_b + chunk
        base = off - len(carry_b)
        for n in needles:
            for mode, mb in variants(n).items():
                c = buf.count(mb)
                if c:
                    st = results[n][mode]
                    st[0] += c
                    if len(st[1]) < 4:
                        p = buf.find(mb)
                        while p != -1 and len(st[1]) < 4:
                            st[1].append(base + p)
                            p = buf.find(mb, p + 1)
        carry_b = buf[-maxlen:]
        off += len(chunk)
    f.close()

    for n in needles:
        print("\n### NEEDLE %r" % n)
        any_hit = False
        for mode in ('plain', 'xor20', 'utf16le', 'utf16be', 'utf16le^20'):
            cnt, offs = results[n][mode]
            if not cnt:
                continue
            any_hit = True
            print("  [%-10s] count=%d  first=%s" % (mode, cnt, [hex(o) for o in offs]))
        if not any_hit:
            print("  (0 命中：5 种编码全试过)")
    print()

if __name__ == '__main__':
    target = sys.argv[1]
    needles = [x for x in sys.argv[2].split(',') if x]
    scan(target, needles)
