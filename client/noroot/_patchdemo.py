#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_patchdemo.py -- prove the in-place 494-byte rewrite works, then read it back."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from CRYPTO_MT import create_key

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_extract',
                   'GameMainConfig_assets_bin_Data_61376b4dc1d7943a1a6556439d2df761.bin')
DATA_OFF, SCRIPT_LEN = 0x1018, 494


def main():
    raw = open(SRC, 'rb').read()
    assert len(raw) == 4616, len(raw)
    ct = raw[DATA_OFF:DATA_OFF + SCRIPT_LEN]
    k8 = create_key('GameMainConfig')
    ks = (k8 * (SCRIPT_LEN // 8 + 2))[:SCRIPT_LEN]
    pt = bytes(a ^ b for a, b in zip(ct, ks))
    print('[1] round-trip (re-encrypt == original):',
          bytes(a ^ b for a, b in zip(pt, ks)) == ct)

    url = 'https://ba.example.com/si.json'
    new = '{"ServerInfoDataUrl":"%s"}' % url
    body = new.ljust(247)                      # 247 UTF-16 chars = 494 B
    nb = body.encode('utf-16-le')
    assert len(nb) == SCRIPT_LEN, len(nb)
    print(f'[2] new json {len(new)} chars, padded to {len(body)}, {len(nb)} B')

    nct = bytes(a ^ b for a, b in zip(nb, ks))
    out = bytearray(raw)
    out[DATA_OFF:DATA_OFF + SCRIPT_LEN] = nct
    dst = SRC.replace('.bin', '.PATCHDEMO.bin')
    open(dst, 'wb').write(bytes(out))
    print(f'[3] wrote {os.path.basename(dst)} ({len(out)} B, same size as original)')

    d = open(dst, 'rb').read()
    back = bytes(a ^ b for a, b in zip(d[DATA_OFF:DATA_OFF + SCRIPT_LEN], ks)).decode('utf-16-le')
    j = json.loads(back)
    print(f'[4] read back: ServerInfoDataUrl = {j["ServerInfoDataUrl"]!r}  match={j["ServerInfoDataUrl"] == url}')
    print('[5] name/length bytes untouched:',
          d[0x1000:0x1018] == raw[0x1000:0x1018],
          '| file size equal:', len(d) == len(raw))


if __name__ == '__main__':
    main()
