#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import base64, itertools, json, zlib, gzip, io, sys
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

FILES = [('resp_1','/www/wwwroot/_ba_state/cn_real_capture/resp_1.body'),
         ('resp_4','/www/wwwroot/_ba_state/cn_real_capture/resp_4.body')]

# request-side key/iv observed in bridge log for the round that used this body
REQ_KEYS = [
    ('round6 req_key', b'MTA5OGQyMTk2YmI5YjA2N2U3ZGM3YWQ1'),
    ('sampleB req_key', b'MjRlMmQ1MmNiZDg0Mzc2MjBjZTgwOTI3'),
    ('sampleA req_key', b'Y2M4YjI2YzNmY2YzZjFiNThkZWYwMTM0'),
]

def pkcs7_ok(b):
    if not b: return False, 0
    n = b[-1]
    return (1 <= n <= 16 and b[-n:] == bytes([n])*n), n

def printable_ratio(b, n=64):
    s = b[:n]
    if not s: return 0.0
    ok = sum(1 for c in s if 32 <= c < 127 or c in (9,10,13))
    return ok / len(s)

def try_dec(key, iv, ct, tag, out):
    if len(key) not in (16,24,32) or len(iv) != 16 or len(ct) == 0 or len(ct)%16:
        return
    try:
        d = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
        pt = d.update(ct) + d.finalize()
    except Exception as e:
        return
    ok, n = pkcs7_ok(pt)
    body = pt[:-n] if ok else pt
    pr = printable_ratio(body)
    out.append((tag, len(pt), ok, n, pr, body))

for name, path in FILES:
    raw = base64.b64decode(open(path).read().strip())
    print('='*78)
    print('%s raw = %d bytes' % (name, len(raw)))
    print('  full hex =', raw.hex())
    print('  ascii-ish =', ''.join(chr(c) if 32<=c<127 else '.' for c in raw))
    out = []
    # A. structured splits: iv | ct | key   and   key | iv | ct
    for keylen in (16,24,32):
        for ivlen in (12,16):
            # tail key
            k = raw[-keylen:]; iv = raw[:ivlen]; ct = raw[ivlen:len(raw)-keylen]
            try_dec(k, iv.ljust(16,b'\0') if ivlen==16 else iv, ct, 'tailkey kl=%d iv=%d'%(keylen,ivlen), out)
            # head key
            k2 = raw[:keylen]; iv2 = raw[keylen:keylen+ivlen]; ct2 = raw[keylen+ivlen:]
            try_dec(k2, iv2, ct2, 'headkey kl=%d iv=%d'%(keylen,ivlen), out)
    # B. key = request key (ASCII), iv = first16 / last16 / zero
    for kn, kv in REQ_KEYS:
        for ivname, ivv in (('head16', raw[:16]), ('tail16', raw[-16:]), ('zero', b'\0'*16)):
            for off in (0,16):
                ct = raw[off:]
                if len(ct)%16: continue
                try_dec(kv, ivv, ct, '%s + iv=%s off=%d'%(kn, ivname, off), out)
    # C. ECB with various keys
    for kname, k in [('tail32', raw[-32:]), ('head32', raw[:32])] + REQ_KEYS:
        if len(k) not in (16,24,32): continue
        try:
            d = Cipher(algorithms.AES(k), modes.ECB()).decryptor()
            ct = raw[:len(raw)//16*16]
            pt = d.update(ct)+d.finalize()
            ok,n = pkcs7_ok(pt)
            body = pt[:-n] if ok else pt
            out.append(('ECB %s'%kname, len(pt), ok, n, printable_ratio(body), body))
        except Exception:
            pass
    # report sorted by printable ratio then pkcs7
    out.sort(key=lambda t: (-(t[2]), -t[4]))
    print('  --- attempts: %d, showing top 12 ---' % len(out))
    for tag, ln, ok, n, pr, body in out[:12]:
        print('   %-42s len=%-3d pkcs7=%-5s pad=%-2d printable=%.2f' % (tag, ln, ok, n, pr))
        print('        head =', body[:80].hex())
        print('        text =', repr(body[:80]))
    # any that look like json?
    for tag, ln, ok, n, pr, body in out:
        try:
            j = json.loads(body.decode('utf-8'))
            print('   *** JSON HIT: %s -> %s' % (tag, list(j.keys()) if isinstance(j,dict) else type(j)))
            print('       ', json.dumps(j, ensure_ascii=False)[:800])
        except Exception:
            pass
        for nm, fn in (('gzip', gzip.decompress), ('zlib', zlib.decompress)):
            try:
                o = fn(body)
                print('   *** %s HIT: %s -> %d bytes %r' % (nm, tag, len(o), o[:200]))
            except Exception:
                pass
    print()
