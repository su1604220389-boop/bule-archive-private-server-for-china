#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_schema_bruteforce.py -- recover the field names of GameMainConfig.

Scheme (proved): stored = UTF16LE(S) XOR cycle8(create_key(S)).
So a candidate name S can be tested by re-encrypting it and comparing with a
stored dict key. Candidate names come from global-metadata.dat ASCII strings,
filtered by the exact UTF-16 character length implied by the stored blob.
"""
import base64
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from CRYPTO_MT import create_key

ENTRIES = [
    '8AOaQvLC5wj3A4RC78L4CNEDmEL6wvsI',
    'YZMqL8DWxWpakyIv0Nbnag==',
    'wL4EWsDv8QX5vgRaye/zBQ==',
    'X04YXBFqd3ZpTg9cKmpvdmpOElwnamB2eE4cXDZqc3ZgTg==',
    'tSrfb7xhQRKEKtZvrmFjEp4q1G+0YUUSkirOb7NhTxKfKv1vqGFPEoQqym8=',
]


def enc_cycle(s: str) -> bytes:
    p = s.encode('utf-16-le')
    k8 = create_key(s)
    ks = (k8 * (len(p) // 8 + 2))[:len(p)]
    return bytes(a ^ b for a, b in zip(p, ks))


def main(meta_path):
    want = {}
    for e in ENTRIES:
        raw = base64.b64decode(e)
        want.setdefault(len(raw) // 2, set()).add(raw)
    print('[want] char-lengths -> blobs:', {k: len(v) for k, v in sorted(want.items())})

    data = open(meta_path, 'rb').read()
    import re
    strs = set()
    for m in re.finditer(rb'[A-Za-z_][A-Za-z0-9_]{5,40}', data):
        try:
            s = m.group().decode('ascii')
        except UnicodeDecodeError:
            continue
        if len(s) in want:
            strs.add(s)
    print(f'[meta] candidate strings: {len(strs)} (lengths {sorted(want)})')

    found = {}
    for s in strs:
        e = enc_cycle(s)
        for ln, blobs in want.items():
            if ln == len(s) and e in blobs:
                found[e] = s
                print(f'  MATCH  len={ln:2d}  name={s!r}')
    print(f'[result] recovered {len(found)}/{len(ENTRIES)} field names')
    unknown = [e for e in ENTRIES if base64.b64decode(e) not in found]
    for e in unknown:
        print(f'  UNRESOLVED {len(base64.b64decode(e))//2:2d} chars  {e}')


if __name__ == '__main__':
    main(sys.argv[1])
