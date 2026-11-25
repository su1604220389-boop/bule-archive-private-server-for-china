#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cross-check: synthetic GameMainConfig vs the real extracted asset, and the
new builder's output vs the hand-made PATCHED_*.bin from _cn_patch.py."""
import hashlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_noroot_apk as B  # noqa: E402

REAL = HERE / '_extract_cn' / 'GameMainConfig_assets_bin_Data_e37c46fea17834108a4756797197d05a.bin'
PATCHED_A = HERE / '_extract_cn' / 'PATCHED_e37c46fea17834108a4756797197d05a.bin'
MINE_HTTP = HERE / 'GameMainConfig_http_example.com.bin'

real = REAL.read_bytes()
synth = B.gmconfig_synth()


def sha(b):
    return hashlib.sha256(b).hexdigest()[:16]


print('[1] synth vs real')
print('    real   %d B sha %s' % (len(real), sha(real)))
print('    synth  %d B sha %s' % (len(synth), sha(synth)))
print('    0x1018..0x145A (m_Script) equal:', real[0x1018:0x145A] == synth[0x1018:0x145A])
print('    whole-file equal:', real == synth)
print('    header 0x0..0x1018 equal:', real[:0x1018] == synth[:0x1018])
print('    tail equal:', real[0x145A:] == synth[0x145A:])
print('    real tail hex:', real[0x145A:].hex(), ' synth tail hex:', synth[0x145A:].hex())

print('[2] builder output vs _cn_patch.py PATCHED (scheme A, https 18)')
mine_a, st = B.gmconfig_rewrite(real, B.gmconfig_value_from_spec('bapsvr-prod-cn.com', 'https'))
patched = PATCHED_A.read_bytes()
print('    mine   %d B  diff-bytes %d' % (len(mine_a), st['diff']))
print('    patched %d B  sha %s   mine sha %s' % (len(patched), sha(patched), sha(mine_a)))
print('    byte-identical to _cn_patch.py output:', mine_a == patched)
if mine_a != patched:
    d = [i for i in range(len(mine_a)) if mine_a[i] != patched[i]]
    print('    first diffs:', [(hex(i), hex(mine_a[i]), hex(patched[i])) for i in d[:5]],
          'total', len(d))

print('[3] builder http output vs hand-written doc snippet')
http_dom = 'bapsvr-prods-cn.com'
v = B.gmconfig_value_from_spec(http_dom)
mine = MINE_HTTP.read_bytes()
print('    value %r (%d chars)' % (v, len(v)))
print('    %d B  sha %s' % (len(mine), sha(mine)))
i = B.gmconfig_read(mine)
print('    round-trip ServerInfoDataUrl == value:', i['fields'][B.GMC_URL_FIELD] == v)
o = B.gmconfig_read(real)
print('    other 5 fields unchanged:',
      all(i['fields'][f] == o['fields'][f] for f in B.GMC_FIELDS if f != B.GMC_URL_FIELD))
print('    ciphertext diff bytes:', sum(1 for k in range(1090)
                                       if mine[0x1018 + k] != real[0x1018 + k]))
