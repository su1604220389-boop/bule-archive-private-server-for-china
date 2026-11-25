#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cn_wire.py -- CN /api/account/auth response wire codec (PROVEN against the real server).

Verified facts (captured from the genuine TencentEdgeOne origin, 2026-11-14):
  body_on_wire = base64( AES-256-CBC ciphertext + key(32) )
  cipher key   = the trailing 32 bytes, random per response
  IV           = FIXED CONSTANT b"JOSYdf8ys97uhFYS"  (derived independently from two
                 different responses with different random keys -> same IV)
  plaintext    = {"protocol":"<name>","packet":"<inner json string>","requestid":"<guid>"}
  (no gzip, no [u32] length prefix, IV is NOT transmitted)

Real sample used by --selftest:
  /www/wwwroot/_ba_state/cn_real_capture/resp_1.body
"""
import base64
import binascii
import json
import os
import sys
import uuid

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

IV_FIXED = b'JOSYdf8ys97uhFYS'
KEY_LEN = 32
BLOCK = 16


def pkcs7_pad(data, bs=BLOCK):
    n = bs - (len(data) % bs)
    return data + bytes([n]) * n


def pkcs7_unpad(data, bs=BLOCK):
    if not data:
        raise ValueError('empty')
    n = data[-1]
    if not (1 <= n <= bs) or data[-n:] != bytes([n]) * n:
        raise ValueError('bad pkcs7 padding (last byte %d)' % n)
    return data[:-n]


def _cbc(key, iv, data, encrypt):
    if len(key) not in (16, 24, 32):
        raise ValueError('bad key length %d' % len(key))
    c = Cipher(algorithms.AES(key), modes.CBC(iv))
    op = c.encryptor() if encrypt else c.decryptor()
    return op.update(data) + op.finalize()


# >>> BA_PATCH_REQUESTID v1 (work/ba/server/deploy/patch_requestid.py) >>>
# OFFICIAL INVARIANT, verified on 109/109 captured responses:
#     outer.requestid  ==  inner packet "RequestId"      (same UUIDv4 string)
# and the client feeds the NEXT request's HTTP header REQUEST-ID from that INNER field
# (108/108: hdr(request n) == RequestId(resp n-1)).  Without it the login chain stops.
BA_PATCH_REQUESTID_VERSION = 'v1'
INNER_REQUESTID_ENV = 'CN_INNER_REQUESTID_FILE'
INNER_REQUESTID_ANCHORS = ('ServerNotification', 'ServerTimeTicks', 'SessionKey', 'Protocol')
LAST_INNER_REQUESTID = {'action': 'init', 'index': None, 'requestid': None}


def inner_requestid_switch_paths():
    """Candidate switch files, highest priority first.  Absent everywhere => enabled."""
    out = []
    try:
        v = os.environ.get(INNER_REQUESTID_ENV)
        if v:
            out.append(v)
    except Exception:
        pass
    out.append('/www/wwwroot/bapatch/cn_inner_requestid.txt')
    try:
        out.append(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                'cn_inner_requestid.txt'))
    except Exception:
        pass
    return out


def inner_requestid_enabled():
    """'1'/'on'/'true' => on; '0'/'off'/'false' => off; no switch file at all => ON."""
    for p in inner_requestid_switch_paths():
        try:
            v = open(p).read().strip().lower()
        except Exception:
            continue
        return v not in ('0', 'off', 'false', 'no', 'disabled')
    return True


def inner_requestid_index(keys):
    """Where the official server puts RequestId: right AFTER the last present base-packet
    field -- 108/109 responses put it at index 4 after
    (Protocol,SessionKey,ServerTimeTicks,ServerNotification); 1002 (the one protocol whose
    SessionKey comes last) puts it at index 3, right before SessionKey."""
    for anchor in INNER_REQUESTID_ANCHORS:
        try:
            return keys.index(anchor) + 1
        except ValueError:
            continue
    return 0


def inner_requestid_apply(inner_obj, requestid):
    """Sync if present, insert at the official index if absent.  Mutates in place."""
    if not isinstance(inner_obj, dict) or not requestid:
        LAST_INNER_REQUESTID.update(action='skip-not-a-dict', index=None,
                                    requestid=requestid)
        return inner_obj
    if not inner_requestid_enabled():
        LAST_INNER_REQUESTID.update(action='skip-switch-off', index=None,
                                    requestid=requestid)
        return inner_obj
    if 'RequestId' in inner_obj:
        idx = list(inner_obj).index('RequestId')
        if inner_obj.get('RequestId') == requestid:
            LAST_INNER_REQUESTID.update(action='kept', index=idx, requestid=requestid)
            return inner_obj
        inner_obj['RequestId'] = requestid
        LAST_INNER_REQUESTID.update(action='synced', index=idx, requestid=requestid)
        return inner_obj
    items = list(inner_obj.items())
    idx = inner_requestid_index([k for k, _ in items])
    items.insert(idx, ('RequestId', requestid))
    inner_obj.clear()
    inner_obj.update(items)
    LAST_INNER_REQUESTID.update(action='inserted', index=idx, requestid=requestid)
    return inner_obj
# <<< BA_PATCH_REQUESTID v1 <<<


def build_plaintext(protocol_name, inner_obj, requestid=None):
    """Outer envelope. packet is the INNER JSON SERIALISED AS A STRING (so it gets \\\" escaped)."""
    requestid = requestid or str(uuid.uuid4())
    inner_requestid_apply(inner_obj, requestid)  # BA_PATCH_REQUESTID v1: outer requestid == inner RequestId
    plain = json.dumps({
        "protocol": protocol_name,
        "packet": json.dumps(inner_obj, ensure_ascii=False, separators=(',', ':')),
        "requestid": requestid,
    }, ensure_ascii=False, separators=(',', ':'))
    return plain, requestid


def wrap_response(protocol_name, inner_obj, requestid=None, key=None):
    """-> (body_bytes_b64, plaintext_str, key_bytes)"""
    key = key or os.urandom(KEY_LEN)
    plain, requestid = build_plaintext(protocol_name, inner_obj, requestid)
    ct = _cbc(key, IV_FIXED, pkcs7_pad(plain.encode('utf-8')), True)
    wire = base64.b64encode(ct + key)
    return wire, plain, key


def unwrap_response(body):
    """body: bytes from the wire (base64 text) -> (outer dict, inner dict, key bytes, plaintext str)"""
    if isinstance(body, str):
        body = body.encode()
    raw = base64.b64decode(body.strip())
    if len(raw) <= KEY_LEN or (len(raw) - KEY_LEN) % BLOCK:
        raise ValueError('bad wire length %d' % len(raw))
    ct, key = raw[:-KEY_LEN], raw[-KEY_LEN:]
    plain = pkcs7_unpad(_cbc(key, IV_FIXED, ct, False)).decode('utf-8')
    outer = json.loads(plain)
    inner = json.loads(outer['packet'])
    return outer, inner, key, plain



def wrap_raw(plaintext, key=None):
    """Encrypt an arbitrary plaintext string WITHOUT the protocol envelope.
    Same container as wrap_response: base64( AES-CBC(key, IV_FIXED) + key )."""
    key = key or os.urandom(KEY_LEN)
    if isinstance(plaintext, str):
        plaintext = plaintext.encode('utf-8')
    ct = _cbc(key, IV_FIXED, pkcs7_pad(plaintext), True)
    return base64.b64encode(ct + key), plaintext.decode('utf-8'), key


def unwrap_raw(body):
    """Inverse of wrap_raw -> (plaintext_str, key). No JSON assumed."""
    if isinstance(body, str):
        body = body.encode()
    raw = base64.b64decode(body.strip())
    if len(raw) <= KEY_LEN or (len(raw) - KEY_LEN) % BLOCK:
        raise ValueError('bad wire length %d' % len(raw))
    ct, key = raw[:-KEY_LEN], raw[-KEY_LEN:]
    return pkcs7_unpad(_cbc(key, IV_FIXED, ct, False)).decode('utf-8'), key


# ---------------------------------------------------------------- selftest
def _selftest():
    ok = True
    print('== 1) round-trip: our own wrapper ==')
    inner = {"Protocol": 1002, "AccountId": 2, "_probe": "ZZCANARY7391QKVB"}
    wire, plain, key = wrap_response('Account_Auth', inner, '11111111-2222-3333-4444-555555555555')
    o, i, k, p = unwrap_response(wire)
    print('   wire len   =', len(wire))
    print('   key match  =', k == key)
    print('   outer keys =', list(o.keys()))
    print('   protocol   =', repr(o['protocol']))
    print('   requestid  =', repr(o['requestid']))
    print('   inner      =', json.dumps(i, ensure_ascii=False))
    ok &= (k == key and o['protocol'] == 'Account_Auth' and i == inner)
    print('   PASS' if ok else '   FAIL')

    print()
    print('== 2) decode the REAL captured response ==')
    real = '/www/wwwroot/_ba_state/cn_real_capture/resp_1.body'
    if not os.path.exists(real):
        print('   SKIP (not found):', real)
        return ok
    body = open(real, 'rb').read()
    print('   raw body chars =', len(body.strip()))
    o2, i2, k2, p2 = unwrap_response(body)
    print('   plaintext len  =', len(p2))
    print('   plaintext      =', repr(p2))
    print('   outer keys     =', list(o2.keys()))
    print('   protocol       =', repr(o2['protocol']))
    print('   packet         =', repr(o2['packet']))
    print('   requestid      =', repr(o2['requestid']))
    print('   inner          =', json.dumps(i2, ensure_ascii=False))
    ok &= (o2['protocol'] == 'Error' and 'packet' in o2 and 'requestid' in o2)
    print('   PASS' if ok else '   FAIL')

    print()
    print('== 3) re-encode the real plaintext and compare byte-for-byte ==')
    raw = base64.b64decode(body.strip())
    ct, key = raw[:-KEY_LEN], raw[-KEY_LEN:]
    rebuilt_ct = _cbc(key, IV_FIXED, pkcs7_pad(p2.encode('utf-8')), True)
    print('   ciphertext identical =', rebuilt_ct == ct)
    ok &= (rebuilt_ct == ct)
    print('   PASS' if rebuilt_ct == ct else '   FAIL')

    print()
    print('ALL PASS' if ok else 'SOME FAILED')
    return ok


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        sys.exit(0 if _selftest() else 1)
    if len(sys.argv) > 1 and sys.argv[1] == '--unwrap':
        d, i, k, p = unwrap_response(open(sys.argv[2], 'rb').read())
        print(json.dumps(d, ensure_ascii=False, indent=2))
        print('--- inner ---')
        print(json.dumps(i, ensure_ascii=False, indent=2))
        sys.exit(0)
    print(__doc__)
