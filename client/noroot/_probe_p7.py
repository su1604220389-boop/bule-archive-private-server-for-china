#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Probe the official BACN.RSA SignerInfo structure (signedAttrs or not)."""
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_noroot_apk as B  # noqa: E402

APK = Path(r'C:\Users\su\Desktop\大肥鱼项目\BAServer\report\_tmp\cn_base.apk')
zf = zipfile.ZipFile(APK)
der = zf.read('META-INF/BACN.RSA')
zf.close()

_, vo, vl, _ = B.der_read_tlv(der, 0)
ci = B.der_children(der, vo, vo + vl)
sd0 = B.der_children(der, ci[1][1], ci[1][1] + ci[1][2])
sd = B.der_children(der, sd0[0][1], sd0[0][1] + sd0[0][2])
print('SignedData children:')
for t, a, l, s0, s1 in sd:
    print('  tag=0x%02X len=%d' % (t, l))
sig = None
for t, a, l, s0, s1 in sd:
    if t == 0x31:
        kids = B.der_children(der, a, a + l)
        sig = der[kids[-1][3]:kids[-1][4]]
_, svo, svl, _ = B.der_read_tlv(sig, 0)
si = B.der_children(sig, svo, svo + svl)
print('SignerInfo children:')
for t, a, l, s0, s1 in si:
    print('  tag=0x%02X len=%d  %s' % (t, l, der[s0:s0 + 4].hex()))
print('has signedAttrs [0]:', any(x[0] == 0xA0 for x in si))
