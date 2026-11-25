#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import base64, json, hashlib
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

def ecb_dec_block(key, block):
    d = Cipher(algorithms.AES(key), modes.ECB()).decryptor()
    return d.update(block) + d.finalize()

def cbc_dec(key, iv, ct):
    d = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    return d.update(ct) + d.finalize()

def unpad(b):
    n = b[-1] if b else 0
    if 1 <= n <= 16 and b.endswith(bytes([n]) * n):
        return b[:-n], n, True
    return b, n, False

for tag in ('resp_1', 'resp_4'):
    raw = base64.b64decode(open('/www/wwwroot/_ba_state/cn_real_capture/%s.body' % tag).read().strip())
    ct, key = raw[:176], raw[176:]
    print('=' * 78)
    print(tag, 'raw =', len(raw), ' ct =', len(ct), ' key =', len(key))

    C1 = ct[:16]
    D1 = ecb_dec_block(key, C1)
    KNOWN = b'{"protocol":"Err'
    derived_iv = bytes(a ^ b for a, b in zip(D1, KNOWN))
    print('  C1 =', C1.hex())
    print('  D_key(C1) =', D1.hex())
    print('  KNOWN P1  = %r' % KNOWN)
    print('  >>> DERIVED IV =', derived_iv.hex())
    print('  IV all-zero?', derived_iv == bytes(16))

    # now decrypt full ct with derived iv
    pt = cbc_dec(key, derived_iv, ct)
    body, n, ok = unpad(pt)
    print('  full decrypt: len=%d pkcs7=%s pad=%d' % (len(pt), ok, n))
    print('  plaintext len =', len(body))
    print('  plaintext = %r' % body)
    print()
    print(body.decode('utf-8', 'replace'))
    print()
    try:
        j = json.loads(body.decode('utf-8'))
        print('  *** JSON OK, keys =', list(j.keys()))
        for k, v in j.items():
            print('     %-12s = %r' % (k, v if not isinstance(v, str) or len(v) < 200 else v[:200]))
        if isinstance(j.get('packet'), str):
            inner = json.loads(j['packet'])
            print('     inner(packet) JSON =', json.dumps(inner, ensure_ascii=False))
    except Exception as e:
        print('  JSON FAIL:', e)

    # candidate IV list from lead
    print()
    print('  --- candidate IVs from the given list ---')
    cands = [('zero', bytes(16)), ('key[:16]', key[:16]), ('key[16:32]', key[16:]),
             ('md5(key)', hashlib.md5(key).digest())]
    for name, iv in cands:
        p = cbc_dec(key, iv, ct)
        b2, _, ok2 = unpad(p)
        head = b2[:16]
        print('    %-10s iv=%-32s head=%r  starts_with_{=%s' % (name, iv.hex()[:32], head, head[:1] == b'{'))
    print()
