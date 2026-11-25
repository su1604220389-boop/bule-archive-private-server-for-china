# -*- coding: utf-8 -*-
"""Probe 2: dump every res xml resource + the single raw resource, and decode Dk.xml tree."""
import struct
import sys
import zipfile

sys.path.insert(0, r'work\ba\noroot\_probe')
from axml_arsc_probe import Arsc, parse_axml, RES_XML_START_ELEM, RES_XML_END_ELEM  # noqa


def dump_tree(buf, label):
    pool, resmap, events = parse_axml(buf)
    print('\n===== %s : %d bytes, %d strings, resmap=%d =====' %
          (label, len(buf), pool.count, len(resmap)))
    print('  strings:', [pool.get(i) for i in range(pool.count)])
    depth = 0
    for e in events:
        nm = e['name']
        print('  <%s> line=%d off=0x%x' % (nm, e['line'], e['off']))
        for a in e['attrs']:
            v = ''
            if a['dtype'] == 0x03:
                v = repr(pool.get(a['data']))
            elif a['dtype'] == 0x12:
                v = 'bool %s' % bool(a['data'])
            elif a['dtype'] == 0x01:
                v = '@0x%08x' % a['data']
            elif a['dtype'] == 0x10:
                v = 'int %d' % a['data']
            print('      %-34s rid=0x%08x dt=0x%02x raw=%d -> %s' %
                  (a['name'], a['res_id'], a['dtype'], a['raw'], v))


def main():
    apk = sys.argv[1] if len(sys.argv) > 1 else r'report\_tmp\cn_base.apk'
    z = zipfile.ZipFile(apk)
    arsc = Arsc(z.read('resources.arsc'))
    pkg = arsc.packages[0]

    print('=== all res/xml resources (type 0x12) ===')
    for tid in sorted(pkg['types']):
        if arsc.type_name(pkg, tid) != 'xml':
            continue
        for tinfo in pkg['types'][tid]:
            if tinfo['flags'] & 0x01:
                print('  sparse type - skipped')
                continue
            base = tinfo['chunk_off'] + tinfo['hsz']
            for eidx in range(tinfo['count']):
                eo = struct.unpack_from('<I', arsc.buf, base + eidx * 4)[0]
                if eo == 0xFFFFFFFF:
                    continue
                ent = tinfo['chunk_off'] + tinfo['start'] + eo
                esize, eflags, ekey = struct.unpack_from('<HHI', arsc.buf, ent)
                vsz, r0, dtype, data = struct.unpack_from('<HBBI', arsc.buf, ent + esize)
                path = arsc.global_pool.get(data) if dtype == 3 else None
                print('  0x%08x %-14s %s' % (0x7f000000 | (tid << 16) | eidx,
                                             arsc.key_name(pkg, ekey), path))

    print('\n=== res/raw resources (type 0x0e) ===')
    for tid in sorted(pkg['types']):
        if arsc.type_name(pkg, tid) != 'raw':
            continue
        for tinfo in pkg['types'][tid]:
            base = tinfo['chunk_off'] + tinfo['hsz']
            for eidx in range(tinfo['count']):
                eo = struct.unpack_from('<I', arsc.buf, base + eidx * 4)[0]
                if eo == 0xFFFFFFFF:
                    continue
                ent = tinfo['chunk_off'] + tinfo['start'] + eo
                esize, eflags, ekey = struct.unpack_from('<HHI', arsc.buf, ent)
                vsz, r0, dtype, data = struct.unpack_from('<HBBI', arsc.buf, ent + esize)
                path = arsc.global_pool.get(data) if dtype == 3 else None
                print('  0x%08x %-14s %s' % (0x7f000000 | (tid << 16) | eidx,
                                             arsc.key_name(pkg, ekey), path))

    # decode the live network security config
    data = z.read('res/Dk.xml')
    dump_tree(data, 'res/Dk.xml (live network security config)')


if __name__ == '__main__':
    main()
