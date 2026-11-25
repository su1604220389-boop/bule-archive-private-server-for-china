#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Independent AXML (binary Android XML) parser + canonical dumper.

Used as a structural cross-check on res/Q9.xml before/after the layout edit.
Deliberately implements the chunk format directly (no aapt, no apktool) so it is
an independent opinion about whether the file is well-formed.
"""
import sys, struct, hashlib

RES_XML_TYPE = 0x0003
RES_STRING_POOL_TYPE = 0x0001
RES_XML_RESOURCE_MAP_TYPE = 0x0180
RES_XML_START_NAMESPACE = 0x0100
RES_XML_END_NAMESPACE = 0x0101
RES_XML_START_ELEMENT = 0x0102
RES_XML_END_ELEMENT = 0x0103
RES_XML_CDATA = 0x0104

TYPE_NAMES = {
    0x00: 'NULL', 0x01: 'REFERENCE', 0x02: 'ATTRIBUTE', 0x03: 'STRING',
    0x04: 'FLOAT', 0x05: 'DIMENSION', 0x06: 'FRACTION',
    0x07: 'DYNAMIC_REFERENCE', 0x08: 'DYNAMIC_ATTRIBUTE', 0x10: 'INT_DEC',
    0x11: 'INT_HEX', 0x12: 'INT_BOOLEAN', 0x1c: 'INT_COLOR_ARGB8',
    0x1d: 'INT_COLOR_RGB8', 0x1e: 'INT_COLOR_ARGB4', 0x1f: 'INT_COLOR_RGB4',
}


class Pool(object):
    def __init__(self, data, off):
        (t, hsz, sz) = struct.unpack_from('<HHI', data, off)
        assert t == RES_STRING_POOL_TYPE, hex(t)
        self.count, self.style_count, self.flags, self.strings_start, self.styles_start = \
            struct.unpack_from('<IIIII', data, off + 8)
        self.utf8 = bool(self.flags & 0x100)
        self.offsets = list(struct.unpack_from('<%dI' % self.count, data, off + hsz))
        self.base = off + self.strings_start
        self.raw = data
        self._cache = {}
        self.end = off + sz

    def get(self, i):
        if i in self._cache:
            return self._cache[i]
        if i == 0xffffffff:
            v = None
        else:
            p = self.base + self.offsets[i]
            d = self.raw
            if self.utf8:
                # UTF-8 pool strings carry TWO variable-length prefixes:
                #   length in UTF-16 code units, then length in bytes
                n16 = d[p]
                if n16 & 0x80:
                    n16 = ((n16 & 0x7f) << 8) | d[p + 1]
                    p += 2
                else:
                    p += 1
                n = d[p]
                if n & 0x80:
                    n = ((n & 0x7f) << 8) | d[p + 1]
                    p += 2
                else:
                    p += 1
                v = d[p:p + n].decode('utf-8', 'replace')
            else:
                n = struct.unpack_from('<H', d, p)[0]
                if n & 0x8000:
                    n = ((n & 0x7fff) << 16) | struct.unpack_from('<H', d, p + 2)[0]
                    p += 4
                else:
                    p += 2
                v = d[p:p + n * 2].decode('utf-16-le', 'replace')
        self._cache[i] = v
        return v


def dimen_str(complex_val):
    """Decode aapt Res_value complex dimension float (radix/shift) to text."""
    RADIX = [1.0 / (1 << 8), 1.0 / (1 << 15), 1.0 / (1 << 23), 1.0 / (1 << 31)]
    UNIT = {0: 'px', 1: 'dip', 2: 'sp', 3: 'pt', 4: 'in', 5: 'mm'}
    mantissa = complex_val & 0xFFFFFF00
    radix = (complex_val >> 4) & 0x3
    unit = complex_val & 0xf
    m = struct.unpack('<i', struct.pack('<I', mantissa))[0]
    return '%g%s' % (m * RADIX[radix], UNIT.get(unit, '?%d' % unit))


def val_str(dt, d, raw):
    if dt == 0x03:
        return '%d' % d  # substituted by caller with pool string
    if dt == 0x01:
        return '@0x%08x' % d
    if dt == 0x02:
        return '?0x%08x' % d
    if dt == 0x04:
        return repr(struct.unpack('<f', struct.pack('<I', d))[0])
    if dt == 0x05:
        return dimen_str(d)
    if dt == 0x06:
        return '%d%%' % d
    if dt in (0x10,):
        return '%d' % d
    if dt == 0x11:
        return '0x%08x' % d
    if dt == 0x12:
        return 'true' if d else 'false'
    if dt in (0x1c, 0x1d, 0x1e, 0x1f):
        return '#%08x' % d
    return '%s(0x%08x)' % (TYPE_NAMES.get(dt, '?'), d)


def parse(path):
    data = open(path, 'rb').read()
    t, hsz, sz = struct.unpack_from('<HHI', data, 0)
    assert t == RES_XML_TYPE, 'not AXML: type=0x%04x' % t
    assert sz == len(data), 'declared size %d != file size %d' % (sz, len(data))
    pool = None
    resmap = None
    nodes = []
    off = hsz
    while off < sz:
        ct, chsz, csz = struct.unpack_from('<HHI', data, off)
        assert csz >= chsz >= 8, 'bad chunk at 0x%x' % off
        assert off + csz <= sz, 'chunk overrun at 0x%x' % off
        if ct == RES_STRING_POOL_TYPE:
            pool = Pool(data, off)
        elif ct == RES_XML_RESOURCE_MAP_TYPE:
            n = (csz - chsz) // 4
            resmap = list(struct.unpack_from('<%dI' % n, data, off + chsz))
        elif ct in (RES_XML_START_NAMESPACE, RES_XML_END_NAMESPACE):
            line, comment, prefix, uri = struct.unpack_from('<IIII', data, off + 8)
            nodes.append({'k': 'NS_START' if ct == RES_XML_START_NAMESPACE else 'NS_END',
                          'line': line, 'prefix': pool.get(prefix), 'uri': pool.get(uri)})
        elif ct == RES_XML_START_ELEMENT:
            line, comment = struct.unpack_from('<II', data, off + 8)
            ns, name = struct.unpack_from('<II', data, off + 16)
            attr_start, attr_size, attr_count = struct.unpack_from('<HHH', data, off + 24)
            attrs = []
            # attributeStart is relative to the end of the chunk header (i.e. to
            # the first byte of ResXMLTree_attrExt at off+chsz), NOT to off.
            for i in range(attr_count):
                p = off + chsz + attr_start + i * attr_size
                ans, aname, araw = struct.unpack_from('<III', data, p)
                vsize, res0, dt, d = struct.unpack_from('<HBBI', data, p + 12)
                attrs.append({
                    'ns': pool.get(ans), 'name': pool.get(aname), 'araw': pool.get(araw),
                    'dt': dt, 'data': d, 'name_idx': aname,
                    'resid': (resmap[aname] if (resmap and aname < len(resmap)) else 0),
                })
            nodes.append({'k': 'E_START', 'line': line, 'ns': pool.get(ns),
                          'name': pool.get(name), 'attrs': attrs})
        elif ct == RES_XML_END_ELEMENT:
            line, comment = struct.unpack_from('<II', data, off + 8)
            ns, name = struct.unpack_from('<II', data, off + 16)
            nodes.append({'k': 'E_END', 'line': line, 'name': pool.get(name)})
        elif ct == RES_XML_CDATA:
            line, comment = struct.unpack_from('<II', data, off + 8)
            d = struct.unpack_from('<I', data, off + 16)[0]
            nodes.append({'k': 'CDATA', 'line': line, 'text': pool.get(d)})
        else:
            nodes.append({'k': 'UNKNOWN_0x%04x' % ct, 'off': off})
        off += csz
    return {'data': data, 'pool': pool, 'resmap': resmap, 'nodes': nodes, 'size': sz}


def dump(path, sort_attrs=False):
    p = parse(path)
    pool = p['pool']
    out = []
    out.append('# AXML %s' % path)
    out.append('# size=%d strings=%d utf8=%s resmap=%d chunks=%d sha256=%s'
               % (p['size'], pool.count, pool.utf8, len(p['resmap'] or []),
                  len(p['nodes']), hashlib.sha256(p['data']).hexdigest()))
    for n in p['nodes']:
        if n['k'] == 'NS_START':
            out.append('NS %s -> %s' % (n['prefix'], n['uri']))
        elif n['k'] == 'E_START':
            out.append('E: %s' % n['name'])
            attrs = n['attrs']
            if sort_attrs:
                attrs = sorted(attrs, key=lambda a: (a['name'] or '', a['ns'] or ''))
            for a in attrs:
                v = val_str(a['dt'], a['data'], a['araw'])
                if a['dt'] == 0x03:
                    v = repr(pool.get(a['data']))
                if a['araw'] is not None and a['dt'] != 0x03:
                    v += ' (raw=%r)' % a['araw']
                out.append('  A: %s%s(0x%08x) %s [%s]'
                           % ((a['ns'] + ':') if a['ns'] else '', a['name'],
                              a['resid'], v, TYPE_NAMES.get(a['dt'], hex(a['dt']))))
        elif n['k'] == 'E_END':
            out.append('/E: %s' % n['name'])
        elif n['k'] == 'CDATA':
            out.append('C: %r' % n['text'])
        else:
            out.append('# %s' % n['k'])
    return '\n'.join(out)


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'dump'
    if mode == 'dump':
        print(dump(sys.argv[2], sort_attrs=('--sort' in sys.argv)))
    elif mode == 'stats':
        p = parse(sys.argv[2])
        print('nodes', len(p['nodes']), 'strings', p['pool'].count,
              'resmap', len(p['resmap'] or []), 'size', p['size'])
        # every attribute name that has a resource id must be inside resmap range
        bad = 0
        for n in p['nodes']:
            if n['k'] != 'E_START':
                continue
            for a in n['attrs']:
                if a['ns'] and a['resid'] == 0:
                    bad += 1
                    print('NO-RESID', a['ns'], a['name'], a['name_idx'])
        print('attrs-with-ns-but-no-resid:', bad)
