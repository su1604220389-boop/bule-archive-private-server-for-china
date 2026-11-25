#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
xor_scan.py — 键无关的 XOR 混淆扫描器（只读，不写任何输入）

两段：
 A) url_only(<file>)  —— 找"任意单字节 XOR 键"下的所有 URL
      锚点用 b":://"（3 字节）。取相邻字节 XOR 差 delta = d[i]^d[i-1]：
      plain = data ^ K  =>  delta 里 K 被消掉，故 delta 与键无关。
      一次遍历即可覆盖全部 256 个键，命中处反推键并解码窗口。

 B) needle_period(<file>, needle, maxp) —— 找 needle 在"周期 ≤ maxp 的重复 keystream"下
      把 needle 按相位 φ 拆成 needle[φ::P]，data 按同样相位拆成 data[φ::P]，
      在跨步序列上用 delta 指纹（同样与键无关）定位，再反推每个相位的键并整串校验。

用法:
  python xor_scan.py url   <file> [--out prefix]
  python xor_scan.py needle <file> --needle bluearchive-cn [--maxp 8]
"""
import argparse
import os
import re
import sys

import numpy as np

CHUNK = 64 * 1024 * 1024
OVER = 1024

URL_RE = re.compile(rb"[A-Za-z][A-Za-z0-9+.\-]{1,10}://[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]{3,220}")
# 严格版：scheme://host.tld[:port][/path]，host 必须有至少一个点
STRICT_URL = re.compile(rb"^(?:https?|wss?|ftp)://[A-Za-z0-9](?:[A-Za-z0-9\-]{0,50}[A-Za-z0-9])?"
                        rb"(?:\.[A-Za-z0-9](?:[A-Za-z0-9\-]{0,50}[A-Za-z0-9])?)+"
                        rb"(?::\d{1,5})?(?:[/?#][A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]*)?$", re.I)
# 可疑记号：任何解码窗口里出现即报告（不看 URL 形态）
SUSPECT = [b"bluearchive", b"yostar", b"state-api", b"gs-api", b"xuliehaochaxu", b"gsqc",
           b"/api/state", b"noroot"]


def chunks(path, chunk=CHUNK, over=OVER):
    """生成 (buf, buf_base)，buf 含 over 字节重叠"""
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        base = 0
        carry = b""
        while True:
            f.seek(base)
            blk = f.read(chunk)
            if not blk:
                break
            buf = carry + blk
            yield buf, base - len(carry)
            carry = buf[-over:]
            base += len(blk)
            if len(blk) < chunk:
                break


# ------------------------------------------------------------------ A) URL under any 1-byte key
def url_only(path):
    """返回 (strict_urls, suspect_hits, anchor_total)，覆盖全部 256 个单字节键"""
    res = []
    susp = []
    total = 0
    k1 = ord(":") ^ ord("/")     # 0x3a ^ 0x2f
    k2 = ord("/") ^ ord("/")     # 0x00
    for buf, off0 in chunks(path):
        a = np.frombuffer(buf, dtype=np.uint8)
        if a.size < 4:
            continue
        d = a[1:] ^ a[:-1]
        mask = (d[:-1] == k1) & (d[1:] == k2)   # i 指向 ':'
        idx = np.flatnonzero(mask)
        for i in idx.tolist():
            total += 1
            key = int(a[i]) ^ ord(":")
            s = max(0, i - 90)
            e = min(a.size, i + 250)
            dec = bytes((a[s:e] ^ key).tolist())
            for m in URL_RE.finditer(dec):
                u = m.group(0).decode("latin-1")
                if STRICT_URL.match(m.group(0)):
                    res.append((off0 + s + m.start(), key, u))
            for tok in SUSPECT:
                p = dec.find(tok)
                if p >= 0:
                    susp.append((off0 + s + p, key, tok.decode(), dec.decode("latin-1", "replace")))
        # 另外：key=0 之外也要覆盖"整段被同一键加密的 JSON 数组"，上面已覆盖
    return res, susp, total


# ------------------------------------------------------------------ B) needle under periodic keystream
def needle_period(path, needle, maxp=8):
    n = needle if isinstance(needle, bytes) else needle.encode("latin-1")
    L = len(n)
    found = []
    for P in range(1, maxp + 1):
        for phi in range(P):
            # 若 needle 起点 abs_off ≡ phi (mod P)，则参与的 data 偏移都 ≡ phi (mod P)，
            # 对应的 needle 下标 t 都满足 t ≡ 0 (mod P) —— 所以 seg 恒为 n[0::P]
            seg = n[0::P]
            m = len(seg)
            if m < 2:
                continue
            deltas = [(seg[j] ^ seg[j - 1]) for j in range(1, m)]
            # 在 data[phi::P] 上找 deltas
            for buf, off0 in chunks(path):
                a = np.frombuffer(buf, dtype=np.uint8)
                # 需要绝对偏移 ≡ phi (mod P)；buf_base 已知
                start = (phi - off0) % P
                strided = a[start::P]
                if strided.size < m:
                    continue
                mask = None
                for j, dv in enumerate(deltas):
                    sl = strided[j: strided.size - (m - 1) + j]
                    cur = (sl == dv)
                    mask = cur if mask is None else (mask & cur)
                if mask is None:
                    continue
                for pos in np.flatnonzero(mask).tolist():
                    abs_off = off0 + start + pos * P
                    # 反推整串并校验
                    if abs_off + L > off0 + a.size:
                        continue
                    ok = True
                    for t in range(L):
                        q = abs_off + t
                        if q < off0 or q >= off0 + a.size:
                            ok = False
                            break
                        # 键 = data[q] ^ n[t]，但只在前 P 个位置定键
                        pass
                    # 用前 P 个字符定 key 槽
                    keys = []
                    for t in range(min(P, L)):
                        q = abs_off + t
                        keys.append(int(a[q - off0]) ^ n[t])
                    # 周期 P 的键必须是同一个 pattern 重复
                    good = True
                    for t in range(L):
                        q = abs_off + t
                        if q - off0 >= a.size:
                            good = False
                            break
                        if (int(a[q - off0]) ^ n[t]) != keys[t % P]:
                            good = False
                            break
                    if good:
                        found.append((abs_off, P, bytes(keys).hex()))
    # 去重
    uniq = {}
    for (off, P, kb) in found:
        uniq.setdefault(off, (P, kb))
    return sorted(uniq.items()), L


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["url", "needle"])
    ap.add_argument("files", nargs="+")
    ap.add_argument("--needle", default="bluearchive-cn")
    ap.add_argument("--maxp", type=int, default=8)
    ap.add_argument("--out", default="")
    a = ap.parse_args()

    lines = []
    for p in a.files:
        if not os.path.exists(p):
            print("MISSING " + p, file=sys.stderr)
            continue
        if a.mode == "url":
            res, susp, total = url_only(p)
            seen = {}
            for (off, key, u) in res:
                seen.setdefault((u, key), []).append(off)
            lines.append("=" * 110)
            lines.append("FILE %s (%d B)  anchor_hits=%d  strict_urls=%d  suspect=%d"
                         % (p, os.path.getsize(p), total, len(seen), len(susp)))
            for (u, key) in sorted(seen, key=lambda k: k[0]):
                offs = seen[(u, key)]
                lines.append("  key=0x%02X n=%-3d first=0x%08X  %s" % (key, len(offs), offs[0], u))
            if susp:
                lines.append("  --- SUSPECT tokens ----")
                for (off, key, tok, win) in susp[:60]:
                    lines.append("  key=0x%02X off=0x%08X tok=%-14s win=%s" % (key, off, tok, win[:160]))
        else:
            hits, L = needle_period(p, a.needle, a.maxp)
            lines.append("=" * 110)
            lines.append("FILE %s  needle=%r L=%d  hits=%d" % (p, a.needle, L, len(hits)))
            for (off, (P, kb)) in hits:
                lines.append("  off=0x%08X P=%d keystream_pattern=%s" % (off, P, kb))
    txt = "\n".join(lines)
    print(txt)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(txt + "\n")


if __name__ == "__main__":
    main()
