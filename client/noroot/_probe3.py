#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_probe3.py -- 2nd layer = UTF16LE(S) XOR cycle8(create_key(S))  (same primitive as m_Script)."""
import base64
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from CRYPTO_MT import create_key


def enc_cycle(s: str) -> str:
    p = s.encode('utf-16-le')
    k8 = create_key(s)
    ks = (k8 * (len(p) // 8 + 2))[:len(p)]
    return base64.b64encode(bytes(a ^ b for a, b in zip(p, ks))).decode()


def dec_cycle(b64: str) -> bytes:
    return base64.b64decode(b64)


ENTRIES = [
    ('8AOaQvLC5wj3A4RC78L4CNEDmEL6wvsI', 'xQOQQvfC5AjGAw=='),
    ('YZMqL8DWxWpakyIv0Nbnag==', 'QZM3L8zW7Go='),
    ('wL4EWsDv8QX5vgRaye/zBQ==', ''),
    ('X04YXBFqd3ZpTg9cKmpvdmpOElwnamB2eE4cXDZqc3ZgTg==', ''),
    ('tSrfb7xhQRKEKtZvrmFjEp4q1G+0YUUSkirOb7NhTxKfKv1vqGFPEoQqym8=', ''),
]


def try_value(blob_b64: str, wlen: int):
    """Given 2*wlen bytes, brute the plaintext over a small dictionary."""
    blob = dec_cycle(blob_b64)
    cands = ['true', 'false', 'True', 'False', 'null', 'yes', 'no', 'on', 'off',
             '1', '0', '-1', '100', '1000', 'http://', 'https://']
    for c in cands:
        if enc_cycle(c) == blob_b64:
            return c, 'self-keyed'
    # keyed by another entry name?
    for nm in ['ServerInfoDataUrl', 'GameMainConfig']:
        k8 = create_key(nm)
        ks = (k8 * (len(blob) // 8 + 2))[:len(blob)]
        pt = bytes(a ^ b for a, b in zip(blob, ks))
        try:
            t = pt.decode('utf-16-le')
            if all(31 < ord(ch) < 127 for ch in t):
                return t, f'keyed-by {nm}'
        except UnicodeDecodeError:
            pass
    return None, None


def main():
    print('[A] enc_cycle("ServerInfoDataUrl") =', enc_cycle('ServerInfoDataUrl'))
    print('    entry[3]                        =', ENTRIES[3][0])
    print('    =>', 'MATCH (scheme confirmed)' if enc_cycle('ServerInfoDataUrl') == ENTRIES[3][0] else 'NO MATCH')
    print()
    print('[B] value decoding:')
    for i, (k, v) in enumerate(ENTRIES):
        if not v:
            print(f'    entry[{i}] val = <empty>')
            continue
        raw = base64.b64decode(v)
        got = try_value(v, len(raw) // 2)
        print(f'    entry[{i}] stored={v} ({len(raw)} B = {len(raw)//2} chars) -> {got}')
    print()
    print('[C] does enc_cycle reproduce the other keys? (needs the name, so try a list)')
    guesses = ['UseSomeThing', 'ServerInfoData', 'AddressablesCatalogUrlRoot',
               'ServerInfoDataUrlRoot', 'UseCDN', 'CdnUrl', 'ApiUrl', 'ServerUrl',
               'GameMainConfig', 'UseSocialServer', 'SocialServerUrl']
    for g in guesses:
        e = enc_cycle(g)
        for i, (k, _v) in enumerate(ENTRIES):
            if e == k:
                print(f'    entry[{i}] name = {g!r}')


if __name__ == '__main__':
    main()
