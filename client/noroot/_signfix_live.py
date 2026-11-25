#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""只读复核：用新加的 read_manifest_identity / check_source_identity 读官方源包。

不构建、不写任何文件；只从 cn_base.apk 读 50 KB 的 AndroidManifest.xml。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_noroot_apk as B  # noqa: E402

SRC = os.path.join(HERE, '..', '..', '..', 'report', '_tmp', 'cn_base.apk')
OUT = os.path.join(HERE, 'BA_noroot_v1.apk')


def main():
    print('== 官方源包: %s' % os.path.basename(SRC))
    src = B.SrcZip(SRC)
    man = src.read('AndroidManifest.xml')
    print('  AndroidManifest.xml %d B' % len(man))
    info = B.read_manifest_identity(man)
    for k in ('package', 'versionCode', 'versionName', 'minSdk', 'targetSdk',
              'nscResId'):
        v = info.get(k)
        print('  %-12s = %r%s' % (k, v, ('  (0x%08X)' % v) if k == 'nscResId' else ''))
    exp = (B.PKG_NAME, B.APK_VERSION_CODE, B.TARGET_SDK, B.NSC_RES_ID)
    got = (info.get('package'), info.get('versionCode'), info.get('targetSdk'),
           info.get('nscResId'))
    print('  与常量一致: %s' % ('OK' if exp == got else 'MISMATCH %r != %r' % (got, exp)))
    print('\n== check_source_identity（不 --force，官方包应当直接过）')
    min_sdk = B.check_source_identity(src)
    print('  返回 minSdk = %r（旧实现硬编码 24）' % (min_sdk,))

    print('\n== 旧产物 %s 的签名相关字段（只读）' % os.path.basename(OUT))
    import zipfile
    with zipfile.ZipFile(OUT) as z:
        sf = z.read('META-INF/CERT.SF')
        mf = z.read('META-INF/MANIFEST.MF')
        ai = z.getinfo('resources.arsc')
        print('  CERT.SF: %d B, X-Android-APK-Signed=%r'
              % (len(sf), B.jar_parse(sf)[0].get('X-Android-APK-Signed')))
        lens = [len(x) for x in mf.split(b'\r\n')]
        print('  MANIFEST.MF: %d B, max 行 %d B, >72 B 的行 %d 个'
              % (len(mf), max(lens), sum(1 for n in lens if n > 72)))
        print('  resources.arsc: method=%d（0=STORED）' % ai.compress_type)
    src.close()


if __name__ == '__main__':
    main()
