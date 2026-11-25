#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""meta_band.py — 两件事（只读）：
 1) 精确定位被单字节 XOR 的 test-ba JSON 字符串的全部副本
 2) 枚举 metadata 里"混淆字面量带"中所有可被某个单字节键解出的可打印串（≥10），
    用来证明除已知 5 条外没有别的游戏域名
"""
import re
import sys

MD = r"work\ba\audit\ba-work\x\assets\bin\Data\Managed\Metadata\global-metadata.dat"
NEEDLE = b'["http://test-ba.yostar.net:5210/api/state","http://test-ba.yostar.net:5210/api/state","http://test-ba.yostar.net:5210/api/state"]'

data = open(MD, "rb").read()

print("== 1) test-ba JSON 副本（键 0xB5）==")
enc = bytes(b ^ 0xB5 for b in NEEDLE)
i = 0
n = 0
while True:
    j = data.find(enc, i)
    if j < 0:
        break
    n += 1
    print("  copy #%d  offset=0x%08X dec=%d  len=%d" % (n, j, j, len(NEEDLE)))
    i = j + 1
print("  total copies =", n)

# 也报告只含单条 URL 的副本
one = bytes(b ^ 0xB5 for b in b"http://test-ba.yostar.net:5210/api/state")
i = 0
offs = []
while True:
    j = data.find(one, i)
    if j < 0:
        break
    offs.append(j)
    i = j + 1
print("  single-URL occurrences (key 0xB5) =", len(offs), [hex(o) for o in offs])

print()
print("== 2) 混淆字面量带 0x000B0000..0x00100000 里所有可疑字面量 ==")
lo, hi = 0x000B0000, 0x00100000
band = data[lo:hi]
RUN = re.compile(rb"[\x20-\x7e]{10,}")
seen = {}
for k in range(256):
    tbl = bytes((b ^ k) for b in range(256))
    dec = band.translate(tbl)
    for m in RUN.finditer(dec):
        s = m.group(0)
        # 只留"像 URL/域名/JSON"的
        if not (b"://" in s or b"." in s and (b"/" in s or b":" in s) or s.startswith(b"[")):
            continue
        if s.count(b" ") > len(s) // 3:
            continue
        seen.setdefault((s, k), 0)
        seen[(s, k)] += 1
for (s, k) in sorted(seen, key=lambda x: (x[0])):
    print("  key=0x%02X n=%d  %r" % (k, seen[(s, k)], s.decode("latin-1")))
print("  distinct =", len(seen))
