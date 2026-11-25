#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scan_needles.py — 二进制安全的多记号扫描器（只读，不修改任何输入文件）

用途：在 APK 解包产物里定位硬编码域名字符串，输出
  文件 + 偏移(hex/dec) + 所在 ELF section(.rodata/.data/.text/...) + 前后 100 字节上下文

特性：
  * 分块读取（默认 16 MiB/块 + 重叠），内存占用与文件大小无关 —— 271 MB 的 so 不会整读
  * 同时搜 ASCII 与 UTF-16LE 两种编码
  * ELF64/ELF32 section header 解析：把文件偏移映射到 section 名与 vaddr
  * 输出 TSV（供机器读）+ TXT（供人读）

用法：
  python scan_needles.py --out work\\ba\\noroot\\_scan <file1> <file2> ...
  python scan_needles.py --needles bluearchive-cn,state-api --out x f1
"""
import argparse
import json
import os
import struct
import sys

CHUNK = 16 * 1024 * 1024

DEFAULT_NEEDLES = [
    # —— 任务指定的 7 条 ——
    "bluearchive-cn",
    "state-api",
    "gsqc-api",
    "gs-api",
    "yostar.cn",
    "xuliehaochaxu",
    "https://",
    # —— 扩展：同族/上位/下位形态，用于确认"没有别的硬编码域名" ——
    "bluearchive",
    "bluearchive-com",
    "bluearchive.com",
    "yostar.net",
    "yostar.com",
    "yostar",
    "test-ba",
    "api/state",
    "/api/",
    "http://",
    "bluearchive-cn.com",
    "gs-api.bluearchive",
    "gsqc-api.bluearchive",
    "state-api.bluearchive",
]


# ---------------------------------------------------------------- ELF sections
def elf_sections(path):
    """返回 [(name, offset, size, vaddr, flags_letter)]；非 ELF 返回 []"""
    try:
        with open(path, "rb") as f:
            hdr = f.read(64)
            if len(hdr) < 52 or hdr[:4] != b"\x7fELF":
                return []
            is64 = hdr[4] == 2
            le = hdr[5] == 1
            e = "<" if le else ">"
            if is64:
                (e_shoff,) = struct.unpack_from(e + "Q", hdr, 0x28)
                (e_shentsize, e_shnum, e_shstrndx) = struct.unpack_from(e + "HHH", hdr, 0x3A)
            else:
                (e_shoff,) = struct.unpack_from(e + "I", hdr, 0x20)
                (e_shentsize, e_shnum, e_shstrndx) = struct.unpack_from(e + "HHH", hdr, 0x2E)
            if e_shoff == 0 or e_shnum == 0 or e_shnum > 4096:
                return []
            f.seek(e_shoff)
            raw = f.read(e_shentsize * e_shnum)
            secs = []
            for i in range(e_shnum):
                b = raw[i * e_shentsize:(i + 1) * e_shentsize]
                if is64:
                    sh_name, sh_type, sh_flags, sh_addr, sh_offset, sh_size = struct.unpack_from(e + "IIQQQQ", b, 0)
                else:
                    sh_name, sh_type, sh_flags, sh_addr, sh_offset, sh_size = struct.unpack_from(e + "IIIIII", b, 0)
                secs.append((sh_name, sh_type, sh_flags, sh_addr, sh_offset, sh_size))
            strsec = secs[e_shstrndx]
            f.seek(strsec[4])
            strtab = f.read(strsec[5])
            out = []
            for (sh_name, sh_type, sh_flags, sh_addr, sh_offset, sh_size) in secs:
                if sh_type == 8:  # SHT_NOBITS (.bss) — 磁盘上无字节
                    continue
                if sh_size == 0:
                    continue
                end = strtab.find(b"\0", sh_name)
                nm = strtab[sh_name:end].decode("latin-1") if end > 0 else ""
                fl = ""
                if sh_flags & 0x2:
                    fl += "A"
                if sh_flags & 0x1:
                    fl += "W"
                if sh_flags & 0x4:
                    fl += "X"
                out.append((nm, sh_offset, sh_size, sh_addr, fl))
            return out
    except Exception as ex:  # noqa: BLE001
        return [("__elf_parse_error__:" + repr(ex), 0, 0, 0, "")]


def section_of(secs, off):
    for (nm, sh_off, sh_size, addr, fl) in secs:
        if sh_off <= off < sh_off + sh_size:
            return "%s (%s, vaddr=0x%x)" % (nm, fl or "-", addr + (off - sh_off))
    return "-"


# ---------------------------------------------------------------- context dump
def ctx(path, off, before=100, after=100, total=None):
    size = total if total is not None else os.path.getsize(path)
    s = max(0, off - before)
    e = min(size, off + after)
    with open(path, "rb") as f:
        f.seek(s)
        b = f.read(e - s)
    txt = "".join(chr(c) if 32 <= c < 127 else ("." if c else ".") for c in b)
    # 每 48 字符折行，便于阅读
    lines = [txt[i:i + 96] for i in range(0, len(txt), 96)]
    return {
        "ctx_off": s,
        "ctx_len": len(b),
        "hex": b.hex(),
        "ascii": txt,
        "ascii_wrapped": " | ".join(lines),
    }


# ---------------------------------------------------------------- search
def find_all(path, needle, limit=2000):
    """分块查找，返回所有文件偏移"""
    n = len(needle)
    hits = []
    overlap = n - 1
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        base = 0
        carry = b""
        while True:
            blk = f.read(CHUNK)
            if not blk:
                break
            buf = carry + blk
            buf_base = base - len(carry)
            i = 0
            while True:
                j = buf.find(needle, i)
                if j < 0:
                    break
                hits.append(buf_base + j)
                if len(hits) >= limit:
                    return hits, size
                i = j + 1
            carry = buf[-overlap:] if overlap > 0 else b""
            base += len(blk)
    return hits, size


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--out", default="work\\ba\\noroot\\_scan")
    ap.add_argument("--needles", default="")
    ap.add_argument("--limit", type=int, default=2000)
    ap.add_argument("--ctx", type=int, default=100)
    args = ap.parse_args()

    needles = [s for s in args.needles.split(",") if s] or DEFAULT_NEEDLES

    rows = []
    summary = []
    for path in args.files:
        if not os.path.exists(path):
            print("MISSING " + path, file=sys.stderr)
            continue
        size = os.path.getsize(path)
        secs = elf_sections(path)
        per_file = []
        for nd in needles:
            for enc, raw in (("ascii", nd.encode("latin-1")), ("utf16le", nd.encode("utf-16-le"))):
                try:
                    hits, _ = find_all(path, raw, args.limit)
                except Exception as ex:  # noqa: BLE001
                    print("ERR %s %s: %r" % (path, nd, ex), file=sys.stderr)
                    continue
                for h in hits:
                    c = ctx(path, h, args.ctx, args.ctx, size)
                    row = {
                        "file": path,
                        "file_size": size,
                        "needle": nd,
                        "enc": enc,
                        "offset": h,
                        "offset_hex": "0x%08X" % h,
                        "section": section_of(secs, h),
                        "ctx_ascii": c["ascii_wrapped"],
                        "ctx_hex": c["hex"],
                    }
                    rows.append(row)
                    per_file.append(row)
        summary.append((path, size, per_file))

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out + ".tsv", "w", encoding="utf-8") as f:
        f.write("file\tneedle\tenc\toffset_dec\toffset_hex\tsection\tctx_ascii\n")
        for r in rows:
            f.write("%s\t%s\t%s\t%d\t%s\t%s\t%s\n" % (
                r["file"], r["needle"], r["enc"], r["offset"], r["offset_hex"], r["section"],
                r["ctx_ascii"].replace("\t", " ")))
    with open(args.out + ".json", "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)

    # 人类可读
    with open(args.out + ".txt", "w", encoding="utf-8") as f:
        f.write("needles = %s\n\n" % ", ".join(needles))
        for (path, size, per) in summary:
            f.write("=" * 100 + "\n")
            f.write("FILE %s  (%d bytes = %.1f MB)   hits=%d\n" % (path, size, size / 1048576.0, len(per)))
            # 每个 needle 计数
            cnt = {}
            for r in per:
                cnt[(r["needle"], r["enc"])] = cnt.get((r["needle"], r["enc"]), 0) + 1
            for k in sorted(cnt):
                f.write("    %-20s %-8s %d\n" % (k[0], k[1], cnt[k]))
            for r in per:
                f.write("-" * 100 + "\n")
                f.write("  needle=%r enc=%s  offset=%d (%s)  section=%s\n"
                        % (r["needle"], r["enc"], r["offset"], r["offset_hex"], r["section"]))
                f.write("  ctx@%d: %s\n" % (r["offset"] - args.ctx, r["ctx_ascii"]))
        f.write("\nTOTAL ROWS = %d\n" % len(rows))
    print("wrote %s.tsv / .json / .txt   rows=%d" % (args.out, len(rows)))


if __name__ == "__main__":
    main()
