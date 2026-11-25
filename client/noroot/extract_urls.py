#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract_urls.py — 从二进制里抽出所有"包含 :// 的可打印串"，并给出偏移/长度/是否完整URL

判定规则：
  full_url  : 以 http:// 或 https:// 开头、有 host、可含端口与 path    → 完整 URL
  scheme_ok : 有 scheme:// 但 host 明显是文档/注释里的示例
  fragment  : 只有 host 或 path 片段，没有 scheme                    → 域名片段

用法: python extract_urls.py <file> [--min 8] [--out prefix]
"""
import argparse
import os
import re
import sys

# 可打印 ASCII 连续段
RUN = re.compile(rb"[\x20-\x7e]{6,}")
URL_IN_RUN = re.compile(rb"[A-Za-z][A-Za-z0-9+.\-]*://[^\s\"'<>]{2,}")
HOSTLIKE = re.compile(rb"\b(?:[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?\.){1,4}(?:com|cn|net|org|io|cc|tv|me|xyz|top|dev|app|jp|kr)\b", re.I)


def scan(path, minlen=8):
    size = os.path.getsize(path)
    out = []
    with open(path, "rb") as f:
        base = 0
        carry = b""
        while True:
            blk = f.read(8 * 1024 * 1024)
            if not blk:
                break
            buf = carry + blk
            bufbase = base - len(carry)
            for m in RUN.finditer(buf):
                s = m.group(0)
                if len(s) < minlen:
                    continue
                if b"://" in s:
                    off = bufbase + m.start()
                    for u in URL_IN_RUN.finditer(s):
                        us = u.group(0).decode("latin-1")
                        out.append(("full_url", off + u.start(), len(us), us))
                else:
                    for hh in HOSTLIKE.finditer(s):
                        hs = hh.group(0).decode("latin-1")
                        out.append(("host_fragment", bufbase + m.start() + hh.start(), len(hs), hs))
            carry = buf[-4096:]
            base += len(blk)
    return out, size


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--min", type=int, default=8)
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    lines = []
    for p in a.files:
        if not os.path.exists(p):
            print("MISSING " + p, file=sys.stderr)
            continue
        rows, size = scan(p, a.min)
        lines.append("=" * 110)
        lines.append("FILE %s  (%d bytes)  urls=%d" % (p, size, sum(1 for r in rows if r[0] == "full_url")))
        seen = {}
        for (kind, off, ln, s) in rows:
            seen.setdefault((kind, s), []).append(off)
        for (kind, s) in sorted(seen, key=lambda k: (k[0], k[1])):
            offs = seen[(kind, s)]
            lines.append("  [%s] n=%d first_off=0x%08X dec=%d len=%d  %s"
                         % (kind, len(offs), offs[0], offs[0], len(s), s))
    txt = "\n".join(lines)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(txt + "\n")
    print(txt)


if __name__ == "__main__":
    main()
