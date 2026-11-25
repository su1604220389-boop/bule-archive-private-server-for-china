#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_probe_payload.py -- analyse the decrypted GameMainConfig payload shape."""
import base64
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from CRYPTO_MT import create_key, xor_bytes, MT, xxhash32

PAYLOAD = (
    '{"8AOaQvLC5wj3A4RC78L4CNEDmEL6wvsI":"xQOQQvfC5AjGAw==",'
    '"YZMqL8DWxWpakyIv0Nbnag==":"QZM3L8zW7Go=",'
    '"wL4EWsDv8QX5vgRaye/zBQ==":"",'
    '"X04YXBFqd3ZpTg9cKmpvdmpOElwnamB2eE4cXDZqc3ZgTg==":"",'
    '"tSrfb7xhQRKEKtZvrmFjEp4q1G+0YUUSkirOb7NhTxKfKv1vqGFPEoQqym8=":""}'
)


def main():
    j = json.loads(PAYLOAD)
    print(f'entries: {len(j)}\n')
    names = ['GameMainConfig', 'ServerInfoDataUrl', 'ServerInfoData',
             'ServerInfoDataUrlRoot', 'AddressablesCatalogUrlRoot']
    for i, (k, v) in enumerate(j.items()):
        kb = base64.b64decode(k)
        vb = base64.b64decode(v) if v else b''
        print(f'[{i}] key b64={k!r} ({len(k)} chars)')
        print(f'    key raw {len(kb):2d} B: {kb.hex(" ")}')
        print(f'    val b64={v!r} ({len(v)} chars)')
        print(f'    val raw {len(vb):2d} B: {vb.hex(" ")}')
        # maybe the blob is UTF-16LE plaintext XOR'd, or plain ascii escaped
        for label, blob in (('key', kb), ('val', vb)):
            if not blob:
                continue
            for x in range(256):
                d = bytes(c ^ x for c in blob)
                if len(d) >= 4 and all(32 <= c < 127 for c in d):
                    print(f'    {label}: xor({x:#04x}) -> {d.decode()!r}')
            # utf16le after xor?
            for x in range(256):
                d = bytes(c ^ x for c in blob)
                try:
                    t = d.decode('utf-16-le')
                except UnicodeDecodeError:
                    continue
                if all(31 < ord(c) < 127 for c in t):
                    print(f'    {label}: xor({x:#04x}) utf16 -> {t!r}')
        print()

    print('--- try per-entry XOR with create_key(name) ---')
    for nm in names:
        k8 = create_key(nm)
        ks = (k8 * 40)
        for i, (k, v) in enumerate(j.items()):
            kb = base64.b64decode(k)
            d = bytes(a ^ b for a, b in zip(kb, ks))
            try:
                t = d.decode('utf-16-le')
                ok = all(31 < ord(c) < 127 for c in t)
            except Exception:
                continue
            if ok:
                print(f'  [{nm}] entry{i} key -> utf16 {t!r}')


if __name__ == '__main__':
    main()
