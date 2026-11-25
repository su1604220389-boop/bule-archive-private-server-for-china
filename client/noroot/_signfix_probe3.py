#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""只读测量 3：apksig ManifestWriter 的常量 + 用官方 41,310 个 section 反证换行规则。"""
import os
import struct
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '..', '..', '..', 'report', '_tmp', 'cn_base.apk')
JAR = os.path.join(os.environ['USERPROFILE'], r'.gradle\caches\modules-2\files-2.1'
                   r'\com.android.tools.build\apksig\8.6.1')


def find_jar():
    for root, _d, files in os.walk(JAR):
        for f in files:
            if f.endswith('.jar'):
                return os.path.join(root, f)
    return None


def cp_ints(data):
    """解析 class 文件常量池里的 Integer 常量与字符串常量。"""
    assert data[:4] == b'\xca\xfe\xba\xbe'
    cnt = struct.unpack('>H', data[8:10])[0]
    off = 10
    ints, strs = [], []
    i = 1
    while i < cnt:
        tag = data[off]
        off += 1
        if tag == 1:
            ln = struct.unpack('>H', data[off:off + 2])[0]
            strs.append(data[off + 2:off + 2 + ln].decode('utf-8', 'replace'))
            off += 2 + ln
        elif tag == 3:
            ints.append(struct.unpack('>i', data[off:off + 4])[0])
            off += 4
        elif tag == 4:
            off += 4
        elif tag == 5:
            off += 8
            i += 1
        elif tag == 6:
            off += 8
            i += 1
        elif tag in (7, 8, 16, 19, 20):
            off += 2
        elif tag in (9, 10, 11, 12, 17, 18):
            off += 4
        elif tag == 15:
            off += 3
        else:
            raise ValueError('bad cp tag %d @%d' % (tag, off))
        i += 1
    return ints, strs


def jar_probe():
    jar = find_jar()
    print('== apksig jar: %s' % jar)
    with zipfile.ZipFile(jar) as z:
        for n in z.namelist():
            if n.endswith(('ManifestWriter.class', 'ManifestParser.class')):
                ints, strs = cp_ints(z.read(n))
                keep = [s for s in strs if s in ('\r\n ', ' ', 'Name: ', ': ',
                                                 'Manifest-Version: 1.0')
                        or 'line' in s.lower()]
                print('  %-52s ints=%s' % (n, sorted(set(ints))))
                print('       strings: %s' % keep)


# ---- 原型：按 70 B 贪心换行 ------------------------------------------------
def jar_wrap(text, limit=70):
    chunks = [ch.encode('utf-8') for ch in text]
    segs, i, n, first = [], 0, len(chunks), True
    while True:
        cap = limit if first else limit - 1
        cur = bytearray()
        while i < n:
            cb = chunks[i]
            if cur and len(cur) + len(cb) > cap:
                break
            cur += cb
            i += 1
        segs.append(bytes(cur) if first else b' ' + bytes(cur))
        first = False
        if i >= n:
            return segs


def manifest_sections(data):
    """极简 section 切分（官方文件用 CRLF，续行以空格开头）。"""
    lines = data.split(b'\r\n')
    if lines and lines[-1] == b'':
        lines = lines[:-1]
    out = []
    for ln in lines:
        if ln.startswith(b' ') and out and out[-1]:
            out[-1][-1] += ln[1:]
        elif ln == b'':
            if out and out[-1]:
                out.append([])
        else:
            if not out:
                out.append([])
            if not out[-1]:
                out.append([]) if False else None
            if not out[-1]:
                out[-1] = [ln]
            else:
                out[-1].append(ln)
    return out


def section_test():
    with zipfile.ZipFile(SRC) as z:
        mf = z.read('META-INF/MANIFEST.MF')
    # 直接按 b'\r\n\r\n' 切会更稳（每个 section 以空行结束）
    raw = mf.split(b'\r\n\r\n')
    if raw and raw[-1] == b'':
        raw = raw[:-1]
    print('== section 反证: 官方 MANIFEST.MF 共 %d 段' % len(raw))
    bad = 0
    wrapped = 0
    for sec in raw:
        blk = sec
        # 续行拼回：物理行 -> 逻辑行
        if b'\r\n ' in blk:
            wrapped += 1
        logical = []
        for ln in blk.split(b'\r\n'):
            if ln.startswith(b' ') and logical:
                logical[-1] += ln[1:]
            else:
                logical.append(ln)
        # 用 70 B 规则重新写一遍，比对字节
        rebuilt = []
        for ln in logical:
            rebuilt.extend(jar_wrap(ln.decode('utf-8'), 70))
        if b'\r\n'.join(rebuilt) != blk:
            bad += 1
            if bad <= 3:
                print('  不匹配:\n    orig=%r\n    new =%r'
                      % (blk[:200], b'\r\n'.join(rebuilt)[:200]))
    print('  含续行的 section: %d ；重新换行后字节不匹配: %d' % (wrapped, bad))


if __name__ == '__main__':
    jar_probe()
    section_test()
