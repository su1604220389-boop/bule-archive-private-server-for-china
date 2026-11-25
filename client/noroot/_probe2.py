#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_probe2.py -- confirm the 2nd-layer scheme: stored = S ^ K(S), K=MT keystream seeded by S."""
import base64
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from CRYPTO_MT import create_key, MT, xxhash32

ENTRIES = [
    ('8AOaQvLC5wj3A4RC78L4CNEDmEL6wvsI', 'xQOQQvfC5AjGAw=='),
    ('YZMqL8DWxWpakyIv0Nbnag==', 'QZM3L8zW7Go='),
    ('wL4EWsDv8QX5vgRaye/zBQ==', ''),
    ('X04YXBFqd3ZpTg9cKmpvdmpOElwnamB2eE4cXDZqc3ZgTg==', ''),
    ('tSrfb7xhQRKEKtZvrmFjEp4q1G+0YUUSkirOb7NhTxKfKv1vqGFPEoQqym8=', ''),
]


def keystream_for(s: str, n: int) -> bytes:
    """MT(xxhash32(s)) continuous keystream, n bytes -- == create_key(s) for n<=8."""
    return MT(xxhash32(s.encode())).NextBytes(n)


def enc_str(s: str) -> bytes:
    """stored = UTF16LE(s) XOR K(s).  Returns base64 of stored."""
    p = s.encode('utf-16-le')
    k = keystream_for(s, len(p))
    return base64.b64encode(bytes(a ^ b for a, b in zip(p, k))).decode()


def main():
    # 1) tautology check on entry 3 (= ServerInfoDataUrl, value empty)
    print('[1] enc_str("ServerInfoDataUrl") =', enc_str('ServerInfoDataUrl'))
    print('    entry[3].key                 =', ENTRIES[3][0])
    print('    MATCH' if enc_str('ServerInfoDataUrl') == ENTRIES[3][0] else '    NO MATCH')
    print()

    # 2) hypothesis: values are booleans "true"/"false"
    print('[2] value hypotheses (stored = V ^ K(V)):')
    for v in ('true', 'false', 'True', 'False', '1', '0', 'null'):
        print(f'    {v!r:8} -> {enc_str(v)}')
    print()
    for i, (k, v) in enumerate(ENTRIES):
        if v:
            print(f'    entry[{i}].val stored = {v}')
    print()

    # 3) name hypotheses for the other 4 keys (byte lengths 24,16,16,44)
    print('[3] candidate names by encoded length:')
    for i, (k, v) in enumerate(ENTRIES):
        raw = base64.b64decode(k)
        nchars = len(raw) // 2
        print(f'    entry[{i}] = {len(raw):2d} B = {nchars:2d} UTF-16 chars, value={"<empty>" if not v else v!r}')


if __name__ == '__main__':
    main()
