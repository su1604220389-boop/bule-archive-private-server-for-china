#!/usr/bin/env python3
"""DD2: decode Android binary XML (AXML) res/xml/http.xml from res.apk.

Read-only on inputs; writes only under work/ba/noroot/.
Purpose: determine the effective cleartextTrafficPermitted value.
"""
import io
import struct
import sys
import zipfile

RES_STRING_POOL_TYPE = 0x0001
RES_XML_TYPE = 0x0003
RES_XML_START_ELEMENT_TYPE = 0x0102
RES_XML_END_ELEMENT_TYPE = 0x0103
RES_XML_RESOURCE_MAP_TYPE = 0x0180

TYPE_REFERENCE = 0x01
TYPE_STRING = 0x03
TYPE_INT_DEC = 0x10
TYPE_INT_HEX = 0x11
TYPE_INT_BOOLEAN = 0x12


def parse_string_pool(buf, off):
    (typ, hsize, size, count, style_count, flags,
     strings_start, styles_start) = struct.unpack_from('<HHIIIIII', buf, off)
    utf8 = bool(flags & (1 << 8))
    offs = struct.unpack_from('<%dI' % count, buf, off + hsize)
    base = off + strings_start
    out = []
    for o in offs:
        p = base + o
        if utf8:
            # u16len, u8len, bytes, 0
            n = buf[p]
            p += 2 if n & 0x80 else 1
            n = buf[p]
            if n & 0x80:
                n = ((n & 0x7F) << 8) | buf[p + 1]
                p += 2
            else:
                p += 1
            out.append(buf[p:p + n].decode('utf-8', 'replace'))
        else:
            n = struct.unpack_from('<H', buf, p)[0]
            p += 2
            if n & 0x8000:
                n = ((n & 0x7FFF) << 16) | struct.unpack_from('<H', buf, p)[0]
                p += 2
            out.append(buf[p:p + n * 2].decode('utf-16-le', 'replace'))
    return out


def value_to_str(t, d, strings):
    if t == TYPE_STRING:
        return repr(strings[d]) if d < len(strings) else '?str%d' % d
    if t == TYPE_INT_BOOLEAN:
        return 'true' if d else 'false'
    if t == TYPE_REFERENCE:
        return '@0x%08x' % d
    if t == TYPE_INT_DEC:
        return str(d)
    if t == TYPE_INT_HEX:
        return hex(d)
    return 'type=0x%02x data=0x%x' % (t, d)


def decode(buf):
    (typ, hsize, size) = struct.unpack_from('<HHI', buf, 0)
    assert typ == RES_XML_TYPE, 'not AXML: 0x%04x' % typ
    off = hsize
    strings = []
    resmap = []
    depth = 0
    lines = []
    while off < min(size, len(buf)):
        ctype, chsize, csize = struct.unpack_from('<HHI', buf, off)
        if csize == 0:
            break
        if ctype == RES_STRING_POOL_TYPE:
            strings = parse_string_pool(buf, off)
        elif ctype == RES_XML_RESOURCE_MAP_TYPE:
            n = (csize - chsize) // 4
            resmap = list(struct.unpack_from('<%dI' % n, buf, off + chsize))
        elif ctype == RES_XML_START_ELEMENT_TYPE:
            ns, name, attr_start, attr_size, attr_count = struct.unpack_from(
                '<IIHHH', buf, off + chsize)
            attrs = []
            p = off + chsize + attr_start
            for _ in range(attr_count):
                a_ns, a_name, a_raw, a_tsize, a_res0, a_type, a_data = \
                    struct.unpack_from('<IIIHBBI', buf, p)
                p += attr_size
                aname = strings[a_name] if a_name < len(strings) else '?'
                res_id = resmap[a_name] if a_name < len(resmap) else 0
                raw = strings[a_raw] if (a_raw != 0xFFFFFFFF and a_raw < len(strings)) else None
                val = value_to_str(a_type, a_data, strings)
                attrs.append((aname, res_id, raw, val, a_type, a_data))
            elname = strings[name] if name < len(strings) else '?'
            lines.append('%s<%s' % ('  ' * depth, elname))
            for (aname, res_id, raw, val, a_type, a_data) in attrs:
                lines.append('%s  @%s (resid=0x%08x) raw=%r -> %s  [type=0x%02x data=0x%x]'
                             % ('  ' * depth, aname, res_id, raw, val, a_type, a_data))
            lines.append('%s  >' % ('  ' * depth))
            depth += 1
        elif ctype == RES_XML_END_ELEMENT_TYPE:
            depth -= 1
        off += csize
    return strings, lines


def main():
    apk = sys.argv[1] if len(sys.argv) > 1 else r'work\ba\bapatch\res.apk'
    entry = 'res/xml/http.xml'
    with zipfile.ZipFile(apk) as z:
        buf = z.read(entry)
    print('# file: %s!%s  (%d bytes)' % (apk, entry, len(buf)))
    print('# magic: %s' % buf[:8].hex())
    strings, lines = decode(buf)
    print('# string pool (%d):' % len(strings))
    for i, s in enumerate(strings):
        print('#   [%d] %r' % (i, s))
    print('--- decoded ---')
    for ln in lines:
        print(ln)


if __name__ == '__main__':
    main()
