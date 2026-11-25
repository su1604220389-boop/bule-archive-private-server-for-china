#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SIGNER_FIXES 用的一次性只读测量脚本（不修改任何产物，不生成 APK）。

用法: python _signfix_probe.py
"""
import hashlib
import io
import os
import struct
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_noroot_apk as B  # noqa: E402

SRC = os.path.join(HERE, '..', '..', '..', 'report', '_tmp', 'cn_base.apk')
OUT = os.path.join(HERE, 'BA_noroot_v1.apk')
PROBE13 = os.path.join(HERE, '..', 'bapatch', 'lsp', 'build13', 'Probe13.apk')


def line_stats(data, label):
    """按 CRLF 切行（不拼续行），统计行长分布。"""
    lines = data.split(b'\r\n')
    if lines and lines[-1] == b'':
        lines = lines[:-1]
    lens = [len(x) for x in lines]
    over = [(i, n) for i, n in enumerate(lens) if n > 72]
    cont = sum(1 for x in lines if x.startswith(b' '))
    print('  %-28s lines=%-7d max=%-4d >72=%-5d cont=%d'
          % (label, len(lines), max(lens) if lens else 0, len(over), cont))
    return lens, over, cont


def sf_head(data, label):
    print('  ---- %s (%d B) ----' % (label, len(data)))
    txt = data.split(b'\r\n\r\n')[0]
    for ln in txt.split(b'\r\n')[:12]:
        print('    | %s' % ln.decode('utf-8', 'replace'))
    print('    sections=%d' % (data.count(b'\r\nName: ') + data.startswith(b'Name: ')))


def p7_sig_scan(data, label):
    """在 PKCS#7 里找 sha256 / rsa OID 命中情况（只看字节模式）。"""
    oid_sha256 = bytes.fromhex('0609608648016503040201')
    oid_sha256rsa = bytes.fromhex('06092a864886f70d01010b')
    oid_rsa = bytes.fromhex('06092a864886f70d010101')
    print('  %s: sha256-OID=%d sha256WithRSA-OID=%d rsaEncryption-OID=%d'
          % (label, data.count(oid_sha256), data.count(oid_sha256rsa),
             data.count(oid_rsa)))


def main():
    print('== A. 官方源包 %s' % os.path.basename(SRC))
    with zipfile.ZipFile(SRC) as z:
        names = z.namelist()
        print('  entries=%d' % len(names))
        sf = z.read('META-INF/BACN.SF')
        mf = z.read('META-INF/MANIFEST.MF')
        p7 = z.read('META-INF/BACN.RSA')
        man = z.read('AndroidManifest.xml')
        sf_head(sf, 'META-INF/BACN.SF')
        p7_sig_scan(p7, 'META-INF/BACN.RSA')
        line_stats(sf, 'BACN.SF 原始行')
        line_stats(mf, 'MANIFEST.MF 原始行')
        # 续行拼回后 section 数
        secs = [s for s in mf.split(b'\r\n\r\n') if s.strip()]
        print('  MANIFEST.MF sections=%d' % len(secs))
        # 官方 SF 里 X-Android-APK-Signed 的确切字节
        i = sf.find(b'X-Android-APK-Signed')
        print('  SF X-Android-APK-Signed @%d: %r' % (i, sf[i:i + 40]))
        _, _, _, cdoff, _ = (None,) * 5
        # 用模块自己的 AXML 解析实测包身份
        info = B.read_manifest_identity(man) if hasattr(B, 'read_manifest_identity') else None
        print('  manifest identity: %r' % (info,))

    print('== B. 本工具产物 %s' % os.path.basename(OUT))
    with zipfile.ZipFile(OUT) as z:
        names = z.namelist()
        print('  entries=%d  first=%s' % (len(names), names[0]))
        ai = z.getinfo('resources.arsc')
        print('  resources.arsc method=%d size=%d' % (ai.compress_type, ai.file_size))
        mf = z.read('META-INF/MANIFEST.MF')
        sf = z.read('META-INF/CERT.SF')
        p7 = z.read('META-INF/CERT.RSA')
        line_stats(mf, 'MANIFEST.MF 原始行')
        line_stats(sf, 'CERT.SF 原始行')
        sf_head(sf, 'META-INF/CERT.SF')
        p7_sig_scan(p7, 'META-INF/CERT.RSA')
        secs = [s for s in mf.split(b'\r\n\r\n') if s.strip()]
        print('  MANIFEST.MF sections=%d' % len(secs))
        # 现有产物 MANIFEST 里最长的 Name 行
        longest = max((ln for ln in mf.split(b'\r\n') if ln.startswith(b'Name: ')),
                      key=len)
        print('  最长 Name 行 %d B: %r' % (len(longest), longest[:100]))

    print('== C. 真 apksigner 样本 %s' % os.path.basename(PROBE13))
    with zipfile.ZipFile(PROBE13) as z:
        for n in z.namelist():
            if n.startswith('META-INF/'):
                print('  %-28s %d B' % (n, z.getinfo(n).file_size))
        sf = [n for n in z.namelist() if n.upper().endswith('.SF')]
        if sf:
            d = z.read(sf[0])
            sf_head(d, sf[0])
            line_stats(d, sf[0] + ' 原始行')


if __name__ == '__main__':
    main()
