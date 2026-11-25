# -*- coding: utf-8 -*-
"""Probe: parse AndroidManifest.xml (AXML) + resources.arsc from cn_base.apk.

Read-only. Writes nothing except stdout / optional JSON.
Goal: resolve android:networkSecurityConfig -> res path, and dump that XML.
"""
import json
import struct
import sys
import zipfile

RES_XML_TYPE = 0x0003
RES_STRING_POOL_TYPE = 0x0001
RES_XML_START_ELEMENT_TYPE = 0x0100 + 2
RES_XML_START_NS = 0x0100
RES_XML_END_NS = 0x0101
RES_XML_START_ELEM = 0x0102
RES_XML_END_ELEM = 0x0103
RES_XML_CDATA = 0x0104
RES_XML_RESOURCE_MAP = 0x0180

ATTR_NETWORK_SECURITY_CONFIG = 0x01010527


class StringPool:
    def __init__(self, buf, off):
        (typ, hsz, size) = struct.unpack_from('<HHI', buf, off)
        assert typ == RES_STRING_POOL_TYPE, hex(typ)
        self.hsz, self.size, self.off = hsz, size, off
        self.count, self.style_count, self.flags, self.strings_start, self.styles_start = \
            struct.unpack_from('<IIIII', buf, off + 8)
        self.utf8 = bool(self.flags & 0x100)
        self.offsets = list(struct.unpack_from('<%dI' % self.count, buf, off + hsz))
        self.buf = buf

    def get(self, idx):
        if idx < 0 or idx >= self.count:
            return None
        p = self.off + self.strings_start + self.offsets[idx]
        if self.utf8:
            # utf16 length then utf8 length (each 1 or 2 bytes)
            n = self.buf[p]
            p += 1
            if n & 0x80:
                p += 1
            n = self.buf[p]
            p += 1
            if n & 0x80:
                n = ((n & 0x7F) << 8) | self.buf[p]
                p += 1
            return self.buf[p:p + n].decode('utf-8', 'replace')
        else:
            n = struct.unpack_from('<H', self.buf, p)[0]
            p += 2
            if n & 0x8000:
                n2 = struct.unpack_from('<H', self.buf, p)[0]
                p += 2
                n = ((n & 0x7FFF) << 16) | n2
            return self.buf[p:p + n * 2].decode('utf-16-le', 'replace')


def parse_axml(buf):
    typ, hsz, size = struct.unpack_from('<HHI', buf, 0)
    if typ != RES_XML_TYPE:
        raise SystemExit('not axml: %04x' % typ)
    off = hsz
    pool = None
    resmap = []
    events = []
    while off < len(buf) and off < size:
        ctyp, chsz, csize = struct.unpack_from('<HHI', buf, off)
        if csize == 0:
            break
        if ctyp == RES_STRING_POOL_TYPE:
            pool = StringPool(buf, off)
        elif ctyp == RES_XML_RESOURCE_MAP:
            n = (csize - chsz) // 4
            resmap = list(struct.unpack_from('<%dI' % n, buf, off + chsz))
        elif ctyp == RES_XML_START_ELEM:
            line, comment, ns, name = struct.unpack_from('<IIII', buf, off + 8)
            astart, asize, acount, aidx, aclass, astyle = struct.unpack_from('<HHHHHH', buf, off + 8 + 16)
            attrs = []
            p = off + 16 + astart
            for i in range(acount):
                ans, anm, araw = struct.unpack_from('<III', buf, p)
                vsz, res0, dtype, data = struct.unpack_from('<HBBI', buf, p + 12)
                res_id = resmap[anm] if anm < len(resmap) else 0
                attrs.append({
                    'ns': ans, 'name_idx': anm, 'raw': araw,
                    'dtype': dtype, 'data': data, 'res_id': res_id,
                    'name': pool.get(anm) if pool else None,
                })
                p += asize
            events.append({'line': line, 'name_idx': name,
                           'name': pool.get(name) if pool else None,
                           'attrs': attrs, 'off': off})
        off += csize
    return pool, resmap, events


def dump_manifest(apk, out_json=None):
    z = zipfile.ZipFile(apk)
    man = z.read('AndroidManifest.xml')
    pool, resmap, events = parse_axml(man)
    print('== manifest: %d bytes, stringpool %d strings, resmap %d ids ==' %
          (len(man), pool.count, len(resmap)))
    print('   utf8 pool:', pool.utf8, ' hsz', pool.hsz, ' chunk size', pool.size)
    print('   resmap head:', ' '.join('%08x' % x for x in resmap[:24]))

    app_attrs = []
    for e in events:
        if e['name'] == 'application':
            print('\n== <application> at off 0x%x, line %d, %d attrs ==' %
                  (e['off'], e['line'], len(e['attrs'])))
            for a in e['attrs']:
                nm = a['name']
                val = ''
                if a['dtype'] == 0x03 and pool:
                    val = pool.get(a['data'])
                elif a['dtype'] == 0x01:
                    val = '@0x%08x' % a['data']
                elif a['dtype'] == 0x10:
                    val = 'int 0x%x' % a['data']
                elif a['dtype'] == 0x12:
                    val = 'bool %s' % bool(a['data'])
                print('   %-28s res_id=0x%08x dtype=0x%02x data=0x%08x  -> %s' %
                      (nm, a['res_id'], a['dtype'], a['data'], val))
                app_attrs.append({'name': nm, 'res_id': a['res_id'],
                                  'dtype': a['dtype'], 'data': a['data']})
    return pool, events, app_attrs, man


class Arsc:
    def __init__(self, buf):
        self.buf = buf
        typ, hsz, size, pkgcount = struct.unpack_from('<HHII', buf, 0)
        assert typ == 2, hex(typ)
        self.hsz, self.size, self.pkgcount = hsz, size, pkgcount
        self.global_pool = None
        self.packages = []
        off = hsz
        while off < size:
            ctyp, chsz, csize = struct.unpack_from('<HHI', buf, off)
            if csize < 8:
                break
            if ctyp == RES_STRING_POOL_TYPE and self.global_pool is None:
                self.global_pool = StringPool(buf, off)
            elif ctyp == 0x0200:
                self.packages.append(self._pkg(off))
            off += csize

    def _pkg(self, off):
        buf = self.buf
        ctyp, chsz, csize = struct.unpack_from('<HHI', buf, off)
        pkg_id = struct.unpack_from('<I', buf, off + 8)[0]
        name = buf[off + 12:off + 12 + 256].decode('utf-16-le', 'replace').rstrip('\x00')
        type_strings, last_pub_type, key_strings, last_pub_key = struct.unpack_from('<IIII', buf, off + 268)
        p = {'id': pkg_id, 'name': name, 'off': off, 'size': csize,
             'type_pool': None, 'key_pool': None, 'types': {}, 'keys': []}
        o = off + chsz
        end = off + csize
        while o < end:
            t2, h2, s2 = struct.unpack_from('<HHI', buf, o)
            if t2 == RES_STRING_POOL_TYPE:
                if p['type_pool'] is None:
                    p['type_pool'] = StringPool(buf, o)
                else:
                    p['key_pool'] = StringPool(buf, o)
            elif t2 == 0x0201:  # TYPE
                tid = buf[o + 8]
                flags = buf[o + 9]
                entry_count, entries_start = struct.unpack_from('<II', buf, o + 12)
                cfg_size = struct.unpack_from('<I', buf, o + 20)[0]
                p['types'].setdefault(tid, []).append({
                    'flags': flags, 'count': entry_count, 'start': entries_start,
                    'chunk_off': o, 'cfg_size': cfg_size,
                    'hsz': h2, 'size': s2,
                })
            o += s2 if s2 >= 8 else 8
        return p

    def type_name(self, pkg, tid):
        tp = pkg['type_pool']
        if tp and 0 < tid <= tp.count:
            return tp.get(tid - 1)
        return None

    def key_name(self, pkg, kidx):
        kp = pkg['key_pool']
        if kp and 0 <= kidx < kp.count:
            return kp.get(kidx)
        return None

    def resolve(self, resid):
        pkg_id = (resid >> 24) & 0xFF
        tid = (resid >> 16) & 0xFF
        eidx = resid & 0xFFFF
        for pkg in self.packages:
            if pkg['id'] != pkg_id:
                continue
            for tinfo in pkg['types'].get(tid, []):
                if tinfo['flags'] & 0x01:  # FLAG_SPARSE
                    continue
                base = tinfo['chunk_off'] + tinfo['hsz']
                eo = struct.unpack_from('<I', self.buf, base + eidx * 4)[0]
                if eo == 0xFFFFFFFF:
                    return None
                ent = tinfo['chunk_off'] + tinfo['start'] + eo
                esize, eflags, ekey = struct.unpack_from('<HHI', self.buf, ent)
                out = {'type': self.type_name(pkg, tid), 'key': self.key_name(pkg, ekey),
                       'flags': eflags, 'entry_off': ent, 'tinfo': tinfo}
                if eflags & 0x0001:  # COMPLEX
                    out['kind'] = 'complex'
                else:
                    vsz, res0, dtype, data = struct.unpack_from('<HBBI', self.buf, ent + esize)
                    out['dtype'] = dtype
                    out['data'] = data
                    if dtype == 0x03 and self.global_pool:
                        out['str'] = self.global_pool.get(data)
                    out['kind'] = 'value'
                return out
        return None

    def dump_types(self):
        for pkg in self.packages:
            print('pkg 0x%02x %r types:' % (pkg['id'], pkg['name']))
            for tid in sorted(pkg['types']):
                print('   type 0x%02x %-22s configs=%d count=%s' %
                      (tid, self.type_name(pkg, tid), len(pkg['types'][tid]),
                       [t['count'] for t in pkg['types'][tid]]))


def main():
    apk = sys.argv[1] if len(sys.argv) > 1 else r'report\_tmp\cn_base.apk'
    pool, events, app_attrs, man = dump_manifest(apk)
    nsc = [a for a in app_attrs if a['res_id'] == ATTR_NETWORK_SECURITY_CONFIG]
    print('\n== networkSecurityConfig attr ==')
    print(nsc)
    z = zipfile.ZipFile(apk)
    arsc = Arsc(z.read('resources.arsc'))
    print('\n== resources.arsc: %d bytes, %d packages ==' %
          (len(arsc.buf), len(arsc.packages)))
    arsc.dump_types()
    if nsc:
        a = nsc[0]
        if a['dtype'] == 0x01:
            r = arsc.resolve(a['data'])
            print('\n== resolve 0x%08x ==' % a['data'])
            if r:
                print({k: v for k, v in r.items() if k != 'tinfo'})
                if r.get('str'):
                    name = r['str']
                    info = z.getinfo(name)
                    print('  zip entry %r comp=%d size=%d csize=%d' %
                          (name, info.compress_type, info.file_size, info.compress_size))
                    data = z.read(name)
                    print('  bytes:', data.hex())
                    open(r'work\ba\noroot\_probe\_nsc_orig.bin', 'wb').write(data)
                    print('  saved _nsc_orig.bin')
            else:
                print('  resolve FAILED')


if __name__ == '__main__':
    main()
