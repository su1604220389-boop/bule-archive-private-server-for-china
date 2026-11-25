# -*- coding: utf-8 -*-
"""Lead 用的 v2/v3 负向测试夹具生成器（不依赖 build_noroot_apk.py 的任何代码）。

目的：证明 build_noroot_apk.py 的校验器不是「永远说 OK」。

生成两个被篡改的变体，其余字节完全不动：
  A) _neg_content.apk  —— 改一个普通条目的内容字节。zip 结构合法，但 v2/v3 内容摘要必须变 → 必须 FAIL
  B) _neg_sigblock.apk —— 只改 APK Signing Block 内的一个字节。zip 与内容全不变，只有签名坏 → 必须 FAIL

用法: python _lead_negtest.py <source.apk>
"""
import os
import shutil
import struct
import sys

MAGIC = b'APK Sig Block 42'


def eocd_offset(buf):
    i = buf.rfind(b'PK\x05\x06')
    if i < 0:
        raise SystemExit('找不到 EOCD')
    if i + 22 > len(buf):
        raise SystemExit('EOCD 越界（有 zip 注释时不支持）')
    return i


def cd_offset(buf):
    e = eocd_offset(buf)
    return struct.unpack('<I', buf[e + 16:e + 20])[0]


def sig_block_range(buf):
    """返回 (start, size_total)。size_total 含首尾两个 8 字节 size 字段。"""
    cd = cd_offset(buf)
    if buf[cd - 16:cd] != MAGIC:
        raise SystemExit('CD 前 16 字节不是 %r（无 APK Signing Block）' % MAGIC)
    size_at_end = struct.unpack('<Q', buf[cd - 24:cd - 16])[0]
    start = cd - size_at_end - 8
    if start < 0:
        raise SystemExit('签名块起点为负')
    size_at_head = struct.unpack('<Q', buf[start:start + 8])[0]
    if size_at_head != size_at_end:
        raise SystemExit('签名块首尾 size 不一致 %d != %d' % (size_at_head, size_at_end))
    return start, size_at_end + 8


def flip(buf, off, what):
    old = buf[off]
    buf[off] ^= 0xFF
    print('  %s: 翻字节 @%d  %02X -> %02X' % (what, off, old, buf[off]))


def main():
    if len(sys.argv) < 2:
        raise SystemExit('用法: python _lead_negtest.py <source.apk>')
    src = sys.argv[1]
    if not os.path.exists(src):
        raise SystemExit('源 APK 不存在: %s' % src)
    here = os.path.dirname(os.path.abspath(__file__))
    raw = open(src, 'rb').read()
    print('源 %s  %d B' % (src, len(raw)))

    start, size = sig_block_range(raw)
    print('  APK Signing Block: start=%d size_total=%d（CD 在 %d）' % (start, size, cd_offset(raw)))

    # ---- B) 只改签名块 ----
    b = bytearray(raw)
    # 块布局: [size(8)][id-value pairs ...][size(8)][magic(16)]
    # 在 pairs 区里挑偏中间的一个字节，避开 id/size 字段的可能性尽量小
    off = start + 8 + (size - 8 - 8 - 16) // 2
    flip(b, off, 'sigblock')
    out_b = os.path.join(here, '_neg_sigblock.apk')
    open(out_b, 'wb').write(bytes(b))

    # ---- A) 改普通条目内容 ----
    import zipfile
    a = bytearray(raw)
    with zipfile.ZipFile(src) as z:
        infos = z.infolist()
        print('  条目 %d 个' % len(infos))
        pick = None
        for i in infos:
            print('    - %-60s method=%d size=%d' % (i.filename, i.compress_type, i.file_size))
            if i.compress_type != 0:
                continue                      # 只挑 STORED 的，改明文才有意义
            if i.filename in ('AndroidManifest.xml', 'res/Dk.xml'):
                continue                      # 这两个会被解析/替换，篡改会变成解析错误而非摘要不符
            # 注意：resources.arsc 允许篡改——校验器只查它的位置/压缩方法，不解析内容
            #      （Probe13.apk 里它就是唯一的 STORED 条目）
            if i.filename.startswith('assets/bin/Data/'):
                continue                      # GameMainConfig，会被解密自检
            if i.file_size >= 8:
                pick = i
                break
        if pick is None:
            raise SystemExit('找不到可篡改的 STORED 普通条目')
    with open(src, 'rb') as fp:
        fp.seek(pick.header_offset)
        lh = fp.read(30)
        if lh[:4] != b'PK\x03\x04':
            raise SystemExit('本地文件头签名不对')
        nlen, elen = struct.unpack('<HH', lh[26:30])
    data_off = pick.header_offset + 30 + nlen + elen
    flip(a, data_off + 1, 'content(%s)' % pick.filename)
    out_a = os.path.join(here, '_neg_content.apk')
    open(out_a, 'wb').write(bytes(a))

    print('产出:')
    for p in (out_a, out_b):
        print('  %-40s %d B  sha256=%s'
              % (os.path.basename(p), os.path.getsize(p),
                 __import__('hashlib').sha256(open(p, 'rb').read()).hexdigest()[:16]))


if __name__ == '__main__':
    main()
