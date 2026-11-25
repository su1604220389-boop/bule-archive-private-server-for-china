#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""meta_band2.py — 在"混淆字面量带"里用**严格域名/URL 正则**枚举，排除随机噪声。
只读。区间 0x000B0000..0x00120000（320 KB）。
"""
import re
import sys

MD = r"work\ba\audit\ba-work\x\assets\bin\Data\Managed\Metadata\global-metadata.dat"
data = open(MD, "rb").read()
lo, hi = 0x000B0000, 0x00120000
band = data[lo:hi]

DOM = re.compile(rb"(?:https?|wss?)://[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]{4,200}"
                 rb"|(?<![A-Za-z0-9\-])[a-z0-9][a-z0-9\-]{0,62}"
                 rb"(?:\.[a-z0-9][a-z0-9\-]{0,62}){1,5}"
                 rb"\.(?:com|cn|net|org|jp|io|tv|cc|me|xyz|top|dev|app)\b")

hits = {}
for k in range(256):
    tbl = bytes((b ^ k) for b in range(256))
    dec = band.translate(tbl)
    for m in DOM.finditer(dec):
        s = m.group(0)
        off = lo + m.start()
        hits.setdefault(s, []).append((k, off))

print("区间 0x%08X..0x%08X  (%d B)" % (lo, hi, hi - lo))
print("distinct =", len(hits))
for s in sorted(hits):
    occ = hits[s]
    print("  %-52s keys=%s  first=0x%08X n=%d"
          % (s.decode("latin-1"), ",".join("%02X" % k for k, _ in occ), occ[0][1], len(occ)))
