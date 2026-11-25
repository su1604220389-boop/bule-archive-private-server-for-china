#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DD3 / P4 : 二进制 AndroidManifest.xml (AXML) 解析器 —— 逐元素打印属性。

目的：把 `report\\06-手机基线恢复.md:628` 那句
      「AndroidManifest.xml 里 grep 'networkSecurityConfig|cleartext|network' → 全空」
变成一个**可复算**的结论。
      （该文件是 AXML 二进制，直接 grep 连 `targetSdkVersion` 都搜不到，
        所以 0 命中不能证明属性不存在。）

用法：python _dump_axml.py <AndroidManifest.xml> [--all]
输出：manifest / uses-sdk / application / activity / service / provider /
      meta-data / uses-permission 的属性名=值；以及关键字扫描表。
只读，不修改任何被解析的文件。
"""
import struct
import sys

RES_STRING_POOL_TYPE = 0x0001
RES_XML_TYPE = 0x0003
RES_XML_RESOURCE_MAP_TYPE = 0x0180
RES_XML_START_ELEMENT_TYPE = 0x0102

MAXCHUNK = 0x0102

ATTR_TYPES = {0x00: "NULL", 0x01: "REF", 0x02: "ATTR", 0x03: "STR", 0x04: "FLOAT",
              0x05: "DIM", 0x06: "FRAC", 0x10: "INT_DEC", 0x11: "INT_HEX",
              0x12: "BOOL", 0x1c: "INT_COLOR"}


def read_string_pool(d, off):
    t, hs, sz = struct.unpack_from("<HHI", d, off)
    assert t == RES_STRING_POOL_TYPE, hex(t)
    cnt, stc, flags, sst, sts = struct.unpack_from("<IIIII", d, off + 8)
    utf8 = bool(flags & 0x100)
    ob = off + hs
    db = off + sst
    out = []
    for i in range(cnt):
        o = struct.unpack_from("<I", d, ob + 4 * i)[0]
        p = db + o
        try:
            if utf8:
                n1 = d[p]; p += 1
                if n1 & 0x80:
                    n1 = ((n1 & 0x7F) << 8) | d[p]; p += 1
                n2 = d[p]; p += 1
                if n2 & 0x80:
                    n2 = ((n2 & 0x7F) << 8) | d[p]; p += 1
                s = d[p:p + n2].decode("utf-8", "replace")
            else:
                n = struct.unpack_from("<H", d, p)[0]; p += 2
                s = d[p:p + n * 2].decode("utf-16-le", "replace")
        except Exception:
            s = "<decode-error>"
        out.append(s)
    return out, utf8, cnt


def fmt_value(strings, atype, adata):
    if atype == 0x03:
        return strings[adata] if adata < len(strings) else "<str%d?>" % adata
    if atype == 0x01:
        return "@ref/0x%08x" % adata
    if atype == 0x10:
        return str(adata)
    if atype == 0x11:
        return "0x%x" % adata
    if atype == 0x12:
        return "true" if adata else "false"
    if atype == 0x00:
        return "(null)"
    return "(%s:0x%x)" % (ATTR_TYPES.get(atype, "?"), adata)


def main(argv):
    path = argv[1]
    show_all = "--all" in argv
    d = open(path, "rb").read()
    t, hs, total = struct.unpack_from("<HHI", d, 0)
    print("[hdr] type=0x%04x headerSize=%d totalSize=%d filesize=%d isAXML=%s"
          % (t, hs, total, len(d), t == RES_XML_TYPE))

    strings, resmap = [], []
    pos = hs
    elems = 0
    watch = ("manifest", "uses-sdk", "application", "uses-permission",
             "uses-permission-sdk-23", "permission", "queries", "provider")
    while pos + 8 <= len(d):
        ct, chs, csz = struct.unpack_from("<HHI", d, pos)
        if csz < 8:
            break
        if ct == RES_STRING_POOL_TYPE:
            strings, utf8, cnt = read_string_pool(d, pos)
            print("[pool] strings=%d utf8=%s" % (cnt, utf8))
        elif ct == RES_XML_RESOURCE_MAP_TYPE:
            n = (csz - chs) // 4
            resmap = list(struct.unpack_from("<%dI" % n, d, pos + chs))
            print("[resmap] %d entries" % n)
        elif ct == RES_XML_START_ELEMENT_TYPE:
            elems += 1
            line, cmt = struct.unpack_from("<II", d, pos + 8)
            ext = pos + chs
            ns, name, a_start, a_size, a_count, a_idx, c_idx, s_idx = \
                struct.unpack_from("<IIHHHHHH", d, ext)
            tag = strings[name] if name < len(strings) else "?<%d>" % name
            # attributeStart 相对 attrExt 起点（AOSP 习惯）；用"属性名非空"做一致性判定
            base = ext + a_start
            def looks_ok(bs):
                if a_count == 0:
                    return True
                nm = struct.unpack_from("<I", d, bs + 4)[0]
                return nm < len(strings) and strings[nm] != ""
            if not looks_ok(base) and looks_ok(pos + a_start):
                base = pos + a_start
            rows = []
            for i in range(a_count):
                a = base + i * a_size
                ans, anm, araw = struct.unpack_from("<III", d, a)
                asz2, res0, atype, adata = struct.unpack_from("<HBBI", d, a + 12)
                aname = strings[anm] if anm < len(strings) else ""
                if not aname and anm < len(resmap):
                    aname = "android:0x%08x" % resmap[anm]
                rows.append((aname, fmt_value(strings, atype, adata), atype))
            if show_all or tag in watch:
                print("[%5d] <%s>  attrs=%d" % (line, tag, a_count))
                for an, av, at in rows:
                    print("          %-34s = %s" % (an, av))
        pos += csz

    print("\n[elements] total start-elements = %d" % elems)

    print("\n[keyword scan over %d pooled strings]" % len(strings))
    kws = ["networkSecurityConfig", "network_security_config", "usesCleartextTraffic",
           "cleartext", "cleartextTrafficPermitted", "trust-anchors", "certificates",
           "debuggable", "targetSdkVersion", "minSdkVersion", "extractNativeLibs",
           "profileable", "src=\"user\"", "res/xml"]
    for k in kws:
        hits = [s for s in strings if k in s]
        print("  %-26s hits=%d %s" % (k, len(hits), hits[:5] if hits else ""))


if __name__ == "__main__":
    main(sys.argv)
