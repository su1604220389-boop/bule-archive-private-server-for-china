#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patch_requestid.py -- move `RequestId` INTO the inner packet so it always equals the
outer envelope `requestid`, for every protocol the bridge renders.

WHY (three independently verified facts, see deploy/TEST_REQUESTID.md):

  1. Official 109/109 captured responses satisfy   outer.requestid == inner.packet.RequestId
     (same UUIDv4 string, 0 exceptions, 0 missing -- scan_requestid_positions.py).
  2. Client chain: HTTP header REQUEST-ID of request n  ==  RequestId of response n-1
     (108/108, report/102).  The field the client reads is the INNER one.
  3. Our cn_wire.build_plaintext() only ever wrote the outer field, so after 24000 the
     client had no value to put in the next REQUEST-ID header and simply stopped.

WHAT THIS PATCH DOES (plan A, cf. TEST_REQUESTID.md section 1):

  * cn_wire.py: inserts a small helper block + ONE statement inside build_plaintext():
        inner_requestid_apply(inner_obj, requestid)
    -> "sync if present, insert if absent", at the exact official key index
       (immediately after the last present base-packet field).
  * Everything else in cn_wire.py is untouched: the AES/IV/pkcs7 container, the fact that
    `packet` is a JSON *string*, base64 layout, return value, function signature.
  * One choke point => every protocol covered, including the 1002 path that never touches
    _cn_send_envelope (the gateway passthrough object goes straight to wrap_response).

KILL SWITCH (instant rollback without touching code):
    echo 0 > /www/wwwroot/bapatch/cn_inner_requestid.txt     # off  (pre-patch behaviour)
    echo 1 > /www/wwwroot/bapatch/cn_inner_requestid.txt     # on
  No file at all = ON (default).  Paths checked, in order:
    $CN_INNER_REQUESTID_FILE, /www/wwwroot/bapatch/cn_inner_requestid.txt,
    <dir of cn_wire.py>/cn_inner_requestid.txt

USAGE
    python patch_requestid.py --dry-run                  # show diff, write nothing
    python patch_requestid.py --apply                    # backup + patch live cn_wire.py
    python patch_requestid.py --verify                   # prove outer == inner (gates + 109)
    python patch_requestid.py --rollback                 # restore newest clean backup
    python patch_requestid.py --target <dir-or-file> ... # work on a copy (used by TEST)

    extra: --write-switch {0,1}  --switch-file PATH  --captures DIR  --bridge-src PATH
           --selftest-aes  --force  --diff-only

  --target accepts either the cn_wire.py file or the directory that contains it.
  All actions are idempotent: re-applying a patched file is a no-op, re-rolling-back with
  no backup present is a no-op, and --verify never writes to the target.

ASCII-only output on purpose (this is run over ssh on a cp936/utf-8 console).
"""
import argparse
import ast
import base64
import binascii
import copy
import difflib
import hashlib
import io
import json
import os
import re
import shutil
import sys
import tempfile
import time

LIVE_TARGET = '/www/wwwroot/bapatch/tools/cn_wire.py'
DEFAULT_SWITCH = '/www/wwwroot/bapatch/cn_inner_requestid.txt'
SWITCH_ENV = 'CN_INNER_REQUESTID_FILE'
TS_FMT = '%Y%m%d_%H%M%S'

MARK_BEGIN = '# >>> BA_PATCH_REQUESTID v1 (work/ba/server/deploy/patch_requestid.py) >>>'
MARK_END = '# <<< BA_PATCH_REQUESTID v1 <<<'
MARK_STMT = '# BA_PATCH_REQUESTID v1: outer requestid == inner RequestId'

# anchor -> insert the call right after it (inside build_plaintext, before packet is built)
ANCHOR_REQUESTID = 'requestid = requestid or str(uuid.uuid4())'
ANCHOR_PLAIN = 'plain = json.dumps({'
SIG = 'def build_plaintext('
_HAS_CONSTANT = hasattr(ast, 'Constant')   # py >= 3.8

HELPER_BLOCK = '''\
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

'''


# =============================================================================
# 0. tiny colourless report helpers
# =============================================================================
class Fail(Exception):
    pass


def die(msg, code=2):
    print('FATAL: %s' % msg)
    raise SystemExit(code)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 16), b''):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def read_text(path):
    with io.open(path, encoding='utf-8', newline='') as f:
        return f.read()


def write_text_atomic(path, text):
    d = os.path.dirname(os.path.abspath(path)) or '.'
    fd, tmp = tempfile.mkstemp(prefix='.rid_patch_', suffix='.tmp', dir=d)
    try:
        with io.open(fd, 'w', encoding='utf-8', newline='') as f:
            f.write(text)
        if os.path.exists(path):
            try:
                shutil.copymode(path, tmp)
            except Exception:
                pass
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except Exception:
                pass


# =============================================================================
# 1. crypto: use `cryptography` when present, else a self-checked pure-python AES
# =============================================================================
def _install_crypto():
    """-> name of the provider actually installed ('cryptography' or 'pure-aes-shim')."""
    try:  # real thing (server has it)
        import cryptography                                  # noqa: F401
        from cryptography.hazmat.primitives.ciphers import (  # noqa: F401
            Cipher, algorithms, modes)
        return 'cryptography'
    except Exception:
        pass
    import types
    mod = _build_embedded_aes()
    Cipher, algorithms, modes = mod.Cipher, mod.algorithms, mod.modes
    pkg = types.ModuleType('cryptography')
    pkg.__path__ = []
    haz = types.ModuleType('cryptography.hazmat')
    haz.__path__ = []
    prim = types.ModuleType('cryptography.hazmat.primitives')
    prim.__path__ = []
    ciph = types.ModuleType('cryptography.hazmat.primitives.ciphers')
    ciph.Cipher, ciph.algorithms, ciph.modes = Cipher, algorithms, modes
    pkg.hazmat = haz
    haz.primitives = prim
    prim.ciphers = ciph
    sys.modules['cryptography'] = pkg
    sys.modules['cryptography.hazmat'] = haz
    sys.modules['cryptography.hazmat.primitives'] = prim
    sys.modules['cryptography.hazmat.primitives.ciphers'] = ciph
    return 'pure-aes-shim'


def _build_embedded_aes():
    """Pure-python AES-128/192/256 + CBC exposing the tiny `cryptography` surface cn_wire
    uses.  Validated at import against the FIPS-197 and NIST SP 800-38A vectors, so it can
    never silently pass a verification it did not actually perform."""
    import types

    def _rotl8(x, s):
        return ((x << s) | (x >> (8 - s))) & 0xFF

    def _xtime(a):
        a <<= 1
        return ((a ^ 0x1B) if (a & 0x100) else a) & 0xFF

    def _mul(a, b):
        r = 0
        for _ in range(8):
            if b & 1:
                r ^= a
            a = _xtime(a)
            b >>= 1
        return r

    def _tables():
        sbox = [0] * 256
        p = q = 1
        while True:
            p = p ^ ((p << 1) & 0xFF) ^ (0x1B if p & 0x80 else 0)
            q ^= q << 1
            q ^= q << 2
            q ^= q << 4
            q &= 0xFF
            if q & 0x80:
                q ^= 0x09
            x = q ^ _rotl8(q, 1) ^ _rotl8(q, 2) ^ _rotl8(q, 3) ^ _rotl8(q, 4)
            sbox[p] = (x ^ 0x63) & 0xFF
            if p == 1:
                break
        sbox[0] = 0x63
        inv = [0] * 256
        for i, v in enumerate(sbox):
            inv[v] = i
        rcon = [0x01]
        for _ in range(13):
            rcon.append(_xtime(rcon[-1]))
        return sbox, inv, rcon

    SBOX, INV, RCON = _tables()

    class AES(object):
        def __init__(self, key):
            key = bytes(key)
            if len(key) not in (16, 24, 32):
                raise ValueError('bad key length %d' % len(key))
            self.nk = len(key) // 4
            self.nr = self.nk + 6
            w = [list(key[4 * i:4 * i + 4]) for i in range(self.nk)]
            for i in range(self.nk, 4 * (self.nr + 1)):
                t = list(w[i - 1])
                if i % self.nk == 0:
                    t = t[1:] + t[:1]
                    t = [SBOX[b] for b in t]
                    t[0] ^= RCON[i // self.nk - 1]
                elif self.nk > 6 and i % self.nk == 4:
                    t = [SBOX[b] for b in t]
                w.append([w[i - self.nk][j] ^ t[j] for j in range(4)])
            self.rk = w

        def _ark(self, s, rnd):
            for c in range(4):
                word = self.rk[4 * rnd + c]
                for r in range(4):
                    s[r][c] ^= word[r]

        @staticmethod
        def _to_state(b):
            return [[b[r + 4 * c] for c in range(4)] for r in range(4)]

        @staticmethod
        def _from_state(s):
            return bytes(s[r][c] for c in range(4) for r in range(4))

        def encrypt_block(self, block):
            s = self._to_state(block)
            self._ark(s, 0)
            for rnd in range(1, self.nr):
                for r in range(4):
                    for c in range(4):
                        s[r][c] = SBOX[s[r][c]]
                for r in range(1, 4):
                    s[r] = s[r][r:] + s[r][:r]
                m = [[0] * 4 for _ in range(4)]
                for c in range(4):
                    a = [s[r][c] for r in range(4)]
                    m[0][c] = _xtime(a[0]) ^ (_xtime(a[1]) ^ a[1]) ^ a[2] ^ a[3]
                    m[1][c] = a[0] ^ _xtime(a[1]) ^ (_xtime(a[2]) ^ a[2]) ^ a[3]
                    m[2][c] = a[0] ^ a[1] ^ _xtime(a[2]) ^ (_xtime(a[3]) ^ a[3])
                    m[3][c] = (_xtime(a[0]) ^ a[0]) ^ a[1] ^ a[2] ^ _xtime(a[3])
                s = m
                self._ark(s, rnd)
            for r in range(4):
                for c in range(4):
                    s[r][c] = SBOX[s[r][c]]
            for r in range(1, 4):
                s[r] = s[r][r:] + s[r][:r]
            self._ark(s, self.nr)
            return self._from_state(s)

        def decrypt_block(self, block):
            s = self._to_state(block)
            self._ark(s, self.nr)
            for rnd in range(self.nr - 1, 0, -1):
                for r in range(1, 4):
                    s[r] = s[r][-r:] + s[r][:-r]
                for r in range(4):
                    for c in range(4):
                        s[r][c] = INV[s[r][c]]
                self._ark(s, rnd)
                m = [[0] * 4 for _ in range(4)]
                for c in range(4):
                    a = [s[r][c] for r in range(4)]
                    m[0][c] = (_mul(a[0], 14) ^ _mul(a[1], 11) ^ _mul(a[2], 13)
                               ^ _mul(a[3], 9))
                    m[1][c] = (_mul(a[0], 9) ^ _mul(a[1], 14) ^ _mul(a[2], 11)
                               ^ _mul(a[3], 13))
                    m[2][c] = (_mul(a[0], 13) ^ _mul(a[1], 9) ^ _mul(a[2], 14)
                               ^ _mul(a[3], 11))
                    m[3][c] = (_mul(a[0], 11) ^ _mul(a[1], 13) ^ _mul(a[2], 9)
                               ^ _mul(a[3], 14))
                s = m
            for r in range(1, 4):
                s[r] = s[r][-r:] + s[r][:-r]
            for r in range(4):
                for c in range(4):
                    s[r][c] = INV[s[r][c]]
            self._ark(s, 0)
            return self._from_state(s)

    class _CBC(object):
        def __init__(self, key, iv, encrypting):
            if len(iv) != 16:
                raise ValueError('iv must be 16 bytes')
            self.aes = AES(key)
            self.iv = bytes(iv)
            self.enc = encrypting
            self.buf = b''
            self.prev = self.iv

        def update(self, data):
            if not isinstance(data, (bytes, bytearray)):
                raise TypeError('data must be bytes')
            self.buf += bytes(data)
            out = b''
            while len(self.buf) >= 16:
                blk, self.buf = self.buf[:16], self.buf[16:]
                if self.enc:
                    c = self.aes.encrypt_block(bytes(a ^ b for a, b in zip(blk, self.prev)))
                    self.prev = c
                    out += c
                else:
                    p = self.aes.decrypt_block(blk)
                    out += bytes(a ^ b for a, b in zip(p, self.prev))
                    self.prev = blk
            return out

        def finalize(self):
            if self.buf:
                raise ValueError('not a multiple of 16 (%d trailing)' % len(self.buf))
            return b''

    class algorithms(object):
        AES = staticmethod(lambda key: ('AES', bytes(key)))

    class modes(object):
        @staticmethod
        def CBC(iv):
            return ('CBC', bytes(iv))

    class Cipher(object):
        def __init__(self, algorithm, mode):
            if algorithm[0] != 'AES' or mode[0] != 'CBC':
                raise ValueError('shim supports AES-CBC only')
            self.key, self.iv = algorithm[1], mode[1]

        def encryptor(self):
            return _CBC(self.key, self.iv, True)

        def decryptor(self):
            return _CBC(self.key, self.iv, False)

    mod = types.ModuleType('_rid_aes_shim')
    mod.Cipher, mod.algorithms, mod.modes = Cipher, algorithms, modes
    mod.AES = AES

    # ---- mandatory self-check before this shim is allowed to verify anything
    for k, p, c in (
            ('000102030405060708090a0b0c0d0e0f', '00112233445566778899aabbccddeeff',
             '69c4e0d86a7b0430d8cdb78070b4c55a'),
            ('000102030405060708090a0b0c0d0e0f1011121314151617',
             '00112233445566778899aabbccddeeff', 'dda97ca4864cdfe06eaf70a0ec0d7191'),
            ('000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f',
             '00112233445566778899aabbccddeeff', '8ea2b7ca516745bfeafc49904b496089')):
        a = AES(binascii.unhexlify(k))
        got = a.encrypt_block(binascii.unhexlify(p))
        if got != binascii.unhexlify(c) or a.decrypt_block(got) != binascii.unhexlify(p):
            raise RuntimeError('pure-AES FIPS-197 self-test failed -- refusing to verify')
    key = binascii.unhexlify('2b7e151628aed2a6abf7158809cf4f3c')
    iv = binascii.unhexlify('000102030405060708090a0b0c0d0e0f')
    pt = binascii.unhexlify('6bc1bee22e409f96e93d7e117393172a')
    cb = _CBC(key, iv, True)
    ct = cb.update(pt) + cb.finalize()
    if ct != binascii.unhexlify('7649abac8119b246cee98e9b12e9197d'):
        raise RuntimeError('pure-AES SP800-38A CBC self-test failed -- refusing to verify')
    return mod


def load_codec(target_file, switch_file=None):
    """Import the (possibly patched) cn_wire module from the target directory.
    Any other module sitting next to it (cn_inner27 / cn_nick) is importable too, so the
    verification uses the real builders."""
    import importlib.util
    d = os.path.dirname(os.path.abspath(target_file))
    if d not in sys.path:
        sys.path.insert(0, d)
    if switch_file:
        os.environ[SWITCH_ENV] = os.path.abspath(switch_file)
    name = 'cn_wire_under_test_%d' % int(time.time() * 1000 % 1000000)
    spec = importlib.util.spec_from_file_location(name, target_file)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# =============================================================================
# 2. text transforms
# =============================================================================
def find_function_block(text, sig):
    """-> (start_index, end_index) of a top-level `def <sig>` block (0..end exclusive)."""
    lines = text.split('\n')
    start = None
    for i, ln in enumerate(lines):
        if ln.startswith(sig):
            start = i
            break
    if start is None:
        return None
    end = len(lines)
    for j in range(start + 1, len(lines)):
        ln = lines[j]
        if ln.strip() == '':
            continue
        if not ln[:1].isspace():
            end = j
            break
    return start, end, lines


def analyze(text):
    """-> dict describing the target text."""
    info = {'patched': MARK_BEGIN in text and MARK_STMT in text,
            'helper': MARK_BEGIN in text,
            'stmt': MARK_STMT in text,
            'has_build_plaintext': SIG in text,
            'has_anchor': False,
            'anchor_line': None,
            'has_anchor_plain': False}
    block = find_function_block(text, SIG)
    if block:
        start, end, lines = block
        for i in range(start, end):
            ln = lines[i]
            if ln.strip() == ANCHOR_REQUESTID:
                info['has_anchor'] = True
                info['anchor_line'] = i + 1
                break
            if ln.strip() == ANCHOR_PLAIN:
                info['has_anchor_plain'] = True
                if info['anchor_line'] is None:
                    info['anchor_line'] = i + 1
    return info


def patch_text(text):
    """-> (new_text, notes[list]).  Raises Fail when the shape is not recognised."""
    info = analyze(text)
    if info['patched']:
        return text, ['already patched (helper block + statement both present)']
    if info['helper'] or info['stmt']:
        raise Fail('PARTIAL patch state: helper block=%s statement=%s -- fix by hand '
                   '(or --rollback / --force) before re-applying'
                   % (info['helper'], info['stmt']))
    if not info['has_build_plaintext']:
        raise Fail('no top-level `def build_plaintext(` found -- not a cn_wire.py we know')
    if not (info['has_anchor'] or info['has_anchor_plain']):
        raise Fail('build_plaintext found but neither anchor line is present '
                   '(%r / %r) -- refusing to guess inside a wire codec'
                   % (ANCHOR_REQUESTID, ANCHOR_PLAIN))

    lines = text.split('\n')
    notes = []
    # --- 1) helper block, immediately above `def build_plaintext(`
    start, _end, _lines = find_function_block(text, SIG)
    if MARK_BEGIN not in text:
        helper = HELPER_BLOCK.split('\n')
        lines[start:start] = helper
        notes.append('inserted %d-line helper block above build_plaintext (line %d)'
                     % (len(helper), start + 1))
    # --- 2) the single call statement inside build_plaintext
    text2 = '\n'.join(lines)
    start2, end2, lines2 = find_function_block(text2, SIG)
    ins = None
    for i in range(start2, end2):
        if lines2[i].strip() == ANCHOR_REQUESTID:
            ins = i + 1
            notes.append('statement inserted after line %d: `%s`'
                         % (i + 1, ANCHOR_REQUESTID))
            break
    if ins is None:
        for i in range(start2, end2):
            if lines2[i].strip() == ANCHOR_PLAIN:
                ins = i
                notes.append('anchor line 1 missing; statement inserted BEFORE line %d: `%s`'
                             % (i + 1, ANCHOR_PLAIN))
                break
    if ins is None:
        raise Fail('internal: anchors vanished after helper insertion')
    # keep the original indentation of the anchor line
    indent = re.match(r'[ \t]*', lines2[ins - 1]).group(0) if ins > 0 else '    '
    lines2.insert(ins, indent + 'inner_requestid_apply(inner_obj, requestid)  ' + MARK_STMT)
    notes.append('build_plaintext now syncs/inserts RequestId before serialising `packet`')
    return '\n'.join(lines2), notes


def revert_text(text):
    """Remove the patch (used by --rollback --force).  Surgical: deletes the helper block,
    the call statement, and exactly the two blank lines the helper block contributed -- so a
    reverted file is byte-identical to the pre-patch original (verified by sha256 in tests)."""
    if MARK_BEGIN not in text and MARK_STMT not in text:
        return text
    lines = text.split('\n')
    out = []
    i, n = 0, len(lines)
    while i < n:
        ln = lines[i]
        if ln.strip() == MARK_BEGIN:
            j = i
            while j < n and lines[j].strip() != MARK_END:
                j += 1
            i = j + 1
            dropped = 0
            while i < n and dropped < 2 and lines[i].strip() == '':
                i += 1
                dropped += 1
            continue
        if MARK_STMT in ln:
            i += 1
            continue
        out.append(ln)
        i += 1
    return '\n'.join(out)


# =============================================================================
# 3. target resolution + apply / rollback
# =============================================================================
def resolve_target(target):
    """Accept a cn_wire.py file or the directory containing it."""
    if target is None:
        return LIVE_TARGET
    t = os.path.abspath(target)
    if os.path.isdir(t):
        cand = os.path.join(t, 'cn_wire.py')
        return cand
    return t


def backup_of(target_file):
    d = os.path.dirname(os.path.abspath(target_file))
    base = os.path.basename(target_file)
    pat = re.compile(r'^%s\.bak\.(\d{8}_\d{6})$' % re.escape(base))
    out = []
    if os.path.isdir(d):
        for n in os.listdir(d):
            m = pat.match(n)
            if m:
                out.append((m.group(1), os.path.join(d, n)))
    out.sort()
    return out


def do_apply(args):
    path = resolve_target(args.target)
    if not os.path.exists(path) and args.dry_run:
        # A dry-run must be runnable off-server (that is what it is for).  Fall back to the
        # read-only baseline copy so the diff can be reviewed before touching anything.
        for cand in (os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 '_baseline', 'cn_wire.py'),):
            if os.path.exists(cand):
                print('NOTE: target absent (%s)' % path)
                print('      previewing against the read-only baseline copy instead: %s'
                      % cand)
                path = cand
                break
    if not os.path.exists(path):
        die('target not found: %s\n'
            '  (run this on the server, or pass --target <dir-with-cn_wire.py>)' % path)
    before_sha = sha256_file(path)
    text = read_text(path)
    info = analyze(text)
    print('target   : %s' % path)
    print('sha256   : %s' % before_sha)
    print('state    : %s' % ('PATCHED (v1)' if info['patched'] else 'pristine'))

    if args.dry_run:
        new_text, notes = patch_text(text)
        print()
        print('-- plan (%d step(s)) --' % len(notes))
        for n in notes:
            print('   * %s' % n)
        print()
        if info['patched']:
            print('-- nothing to diff: already patched --')
        else:
            diff = list(difflib.unified_diff(
                text.split('\n'), new_text.split('\n'),
                fromfile='a/' + os.path.basename(path),
                tofile='b/' + os.path.basename(path), lineterm='', n=3))
            for ln in diff:
                print(ln)
            print()
            added = sum(1 for x in diff if x.startswith('+') and not x.startswith('+++'))
            removed = sum(1 for x in diff if x.startswith('-') and not x.startswith('---'))
            print('-- dry-run: %d line(s) added, %d removed, 0 modified --'
                  % (added, removed))
        print()
        print('-- after applying --')
        print('   backup  : %s.bak.<TS>' % path)
        print('   rollback: python patch_requestid.py --rollback --target %s' % path)
        print('   kill-sw : echo 0 > %s' % DEFAULT_SWITCH)
        return 0

    if info['patched'] and not args.force:
        print()
        print('already patched -- nothing to do (idempotent).')
        return 0

    # compute + compile the patched source BEFORE any filesystem side effect
    new_text, notes = patch_text(text)
    try:
        compile(new_text, path, 'exec')
    except SyntaxError as e:
        die('patched source does not compile (%r) -- original left untouched' % (e,))

    ts = time.strftime(TS_FMT)
    url = path
    bak = '%s.bak.%s' % (url, ts)
    if os.path.exists(bak):
        # never overwrite an existing backup (idempotency safety)
        bak = '%s.bak.%s_%d' % (url, ts, os.getpid() % 1000)
    shutil.copy2(url, bak)
    if sha256_file(bak) != before_sha:
        die('backup verification failed: %s' % bak)
    print('backup   : %s  (sha256 verified)' % bak)

    write_text_atomic(url, new_text)
    after_sha = sha256_file(url)
    if after_sha == before_sha:
        die('write produced identical bytes -- refusing to report success')
    meta = {'version': 'BA_PATCH_REQUESTID v1',
            'target': url, 'backup': bak,
            'sha256_before': before_sha, 'sha256_after': after_sha,
            'switch_file': args.switch_file or DEFAULT_SWITCH,
            'switch_env': SWITCH_ENV,
            'applied_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'notes': notes}
    write_text_atomic(bak + '.meta.json',
                      json.dumps(meta, ensure_ascii=False, indent=2))
    print('applied  : %s' % url)
    print('sha256   : %s -> %s' % (before_sha, after_sha))
    for n in notes:
        print('   * %s' % n)

    if args.write_switch is not None:
        sp = args.switch_file or DEFAULT_SWITCH
        try:
            write_text_atomic(sp, str(int(args.write_switch)) + '\n')
            print('switch   : %s = %d' % (sp, args.write_switch))
        except Exception as e:
            print('switch   : could NOT write %s (%r) -- default ON applies' % (sp, e))
    print()
    print('next     : python %s --verify%s' % (
        os.path.basename(__file__),
        (' --target "%s"' % path) if path != LIVE_TARGET else ''))
    return 0


def do_rollback(args):
    path = resolve_target(args.target)
    if not os.path.exists(path):
        die('target not found: %s' % path)
    text = read_text(path)
    info = analyze(text)
    cands = backup_of(path)
    if not cands:
        if not args.force:
            print('no backup found next to %s -- nothing to roll back (idempotent).' % path)
            return 0
        print('no backup found; --force: reverting the patch by text edit')
        if not info['patched']:
            print('target is pristine already -- nothing to do')
            return 0
        write_text_atomic(path, revert_text(text))
        print('reverted by text edit: %s' % path)
        print('sha256   : %s' % sha256_file(path))
        return 0

    pick = None
    for ts, p in reversed(cands):
        if not analyze(read_text(p))['patched']:
            pick = p
            break
    if pick is None:
        if not args.rollback_force:
            die('every backup already contains the patch; pass --rollback-force to use the '
                'newest one anyway (or --force to revert by text edit)')
        pick = cands[-1][1]
    print('rollback : %s' % pick)
    if args.dry_run:
        print('(dry-run: nothing written)')
        return 0
    ts = time.strftime(TS_FMT)
    keep = '%s.pre_rollback.%s' % (path, ts)
    shutil.copy2(path, keep)
    print('preserved: %s' % keep)
    tmp = path + '.restore.tmp'
    shutil.copy2(pick, tmp)
    os.replace(tmp, path)
    print('restored : %s' % path)
    print('sha256   : %s' % sha256_file(path))
    print('state    : %s' % ('PATCHED' if analyze(read_text(path))['patched'] else 'pristine'))
    print()
    print('extra kill switch (no file edit):  echo 0 > %s' % DEFAULT_SWITCH)
    return 0


# =============================================================================
# 4. inner-object builders for the six gated protocols (real ones when available)
# =============================================================================
def _eval_literal(node, notes):
    """ast literal evaluator that tolerates `dict(cn_inner.X)` style calls."""
    if isinstance(node, ast.Dict):
        return {_eval_literal(k, notes): _eval_literal(v, notes)
                for k, v in zip(node.keys, node.values)}
    if isinstance(node, ast.List):
        return [_eval_literal(e, notes) for e in node.elts]
    if isinstance(node, ast.Tuple):
        return [_eval_literal(e, notes) for e in node.elts]
    if isinstance(node, ast.Constant):
        return node.value
    if not _HAS_CONSTANT:
        # python < 3.8 only: numbers/strings are Num/Str/Bytes/NameConstant nodes
        for legacy in ('Num', 'Str', 'Bytes', 'NameConstant'):
            cls = getattr(ast, legacy, None)
            if cls is not None and isinstance(node, cls):
                return getattr(node, 'n', getattr(node, 's', getattr(node, 'value', None)))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_eval_literal(node.operand, notes)
    if isinstance(node, ast.Call):
        notes.append('call replaced with {} (%s)' % _src(node))
        return {}
    if isinstance(node, ast.Attribute):
        notes.append('attribute replaced with None (%s)' % _src(node))
        return None
    if isinstance(node, ast.Name):
        notes.append('name replaced with None (%s)' % node.id)
        return None
    raise Fail('unsupported literal node %s' % type(node).__name__)


def _src(node):
    try:
        return ast.unparse(node)
    except Exception:
        return '<expr>'


def _branch_protocols(test):
    """`if num == 90004` -> [90004];  `if num in (1019, 1017)` -> [1019, 1017]"""
    if not isinstance(test, ast.Compare) or len(test.ops) != 1:
        return []
    left = test.left
    if not (isinstance(left, ast.Name) and left.id == 'num'):
        return []
    right = test.comparators[0]
    try:
        if isinstance(test.ops[0], ast.Eq) and isinstance(right, ast.Constant):
            return [int(right.value)]
        if isinstance(test.ops[0], ast.In) and isinstance(right, (ast.Tuple, ast.List)):
            return [int(e.value) for e in right.elts if isinstance(e, ast.Constant)]
    except Exception:
        return []
    return []


def extract_live_objects(bridge_src):
    """-> {protocol:int -> (dict, [notes])} taken verbatim (via ast) from the live bridge."""
    out = {}
    if not bridge_src or not os.path.exists(bridge_src):
        return out
    tree = ast.parse(read_text(bridge_src))

    class V(ast.NodeVisitor):
        def visit_If(self, node):
            for proto in _branch_protocols(node.test):
                for st in node.body:
                    if (isinstance(st, ast.Assign)
                            and isinstance(st.targets[0], ast.Name)
                            and st.targets[0].id == 'obj'
                            and isinstance(st.value, ast.Dict)):
                        notes = []
                        try:
                            out[proto] = (_eval_literal(st.value, notes), notes)
                        except Exception:
                            out.pop(proto, None)
                        break
            self.generic_visit(node)

    V().visit(tree)
    return out


GATE_NAMES = ((1002, 'Account_Auth'), (1001, 'Account_Nickname'),
              (1010, 'Account_CallName'), (24000, 'Academy_GetInfo'),
              (90004, 'Management_Data'), (1017, 'Account_LoginSync'))


def captures_by_protocol(caps_dir):
    """-> {protocol name -> official inner dict (RequestId already stripped)}"""
    out = {}
    if not caps_dir or not os.path.isdir(caps_dir):
        return out
    for fp in sorted(glob_glob(caps_dir, '*response.json')):
        try:
            doc = json.load(io.open(fp, encoding='utf-8'))
            outer = json.loads(doc['plain'])
            inner = json.loads(outer['packet'])
        except Exception:
            continue
        if not isinstance(inner, dict):
            continue
        name = outer.get('protocol')
        if name and name not in out:
            out[name] = {k: v for k, v in inner.items() if k != 'RequestId'}
    return out


def build_gate_cases(codec_dir, bridge_src, caps_dir=None):
    """-> list of dicts: {proto,name,obj,builder,notes}. Real builders win; every gate always
    renders something, and the `builder` column says exactly what was used."""
    cases = []

    def load_sibling(name):
        p = os.path.join(codec_dir, name + '.py')
        if not os.path.exists(p):
            return None
        try:
            return load_codec(p)
        except Exception:
            return None

    live = extract_live_objects(bridge_src)

    # ---- 1002 Account_Auth
    m27 = load_sibling('cn_inner27')
    if m27 is not None and hasattr(m27, 'build'):
        cases.append({'proto': 1002, 'name': 'Account_Auth', 'obj': m27.build(1002),
                      'builder': 'cn_inner27.build(1002)@%s' % codec_dir, 'notes': []})
    elif 1002 in live:
        cases.append({'proto': 1002, 'name': 'Account_Auth', 'obj': live[1002][0],
                      'builder': 'live-literal(ast)@%s' % os.path.basename(bridge_src),
                      'notes': list(live[1002][1])})

    # ---- 1001 / 1010 via cn_nick
    mn = load_sibling('cn_nick')
    if mn is not None:
        cases.append({'proto': 1001, 'name': 'Account_Nickname',
                      'obj': mn.build_nickname_response('111', protocol=1001),
                      'builder': 'cn_nick.build_nickname_response@%s' % codec_dir,
                      'notes': []})
        cases.append({'proto': 1010, 'name': 'Account_CallName',
                      'obj': mn.build_callname_response('111', nickname='111', protocol=1010),
                      'builder': 'cn_nick.build_callname_response@%s' % codec_dir,
                      'notes': []})

    # ---- 24000 / 90004 / 1017 from the live bridge source (ast, verbatim)
    for proto, name in ((24000, 'Academy_GetInfo'), (90004, 'Management_Data'),
                        (1017, 'Account_LoginSync')):
        if proto in live:
            cases.append({'proto': proto, 'name': name, 'obj': live[proto][0],
                          'builder': 'live-literal(ast)@%s' % os.path.basename(bridge_src),
                          'notes': list(live[proto][1])})

    # ---- never leave a hole: any gate without a builder gets the official capture shape
    #      (or a clearly-labelled minimal replica) so the invariant is still exercised.
    have = {c['proto'] for c in cases}
    caps = captures_by_protocol(caps_dir)
    for proto, name in GATE_NAMES:
        if proto in have:
            continue
        if name in caps:
            cases.append({'proto': proto, 'name': name, 'obj': copy.deepcopy(caps[name]),
                          'builder': 'official-shape@captures',
                          'notes': ['real builder absent; official capture inner used '
                                    '(RequestId stripped)']})
        else:
            cases.append({'proto': proto, 'name': name,
                          'obj': {'Protocol': proto, 'ServerTimeTicks': 0,
                                  'ServerNotification': 0},
                          'builder': 'replica-min',
                          'notes': ['no builder and no capture for this protocol; '
                                    'minimal replica -- the invariant does not depend on '
                                    'the payload']})
    cases.sort(key=lambda c: [p for p, _n in GATE_NAMES].index(c['proto'])
               if c['proto'] in [p for p, _n in GATE_NAMES] else 99)
    return cases


# =============================================================================
# 5. verification
# =============================================================================
def render(mod, name, obj, rid):
    """Drive the real codec: build_plaintext -> AES-CBC(pkcs7) -> base64(ct+key) and back."""
    wire, plain, key = mod.wrap_response(name, obj, rid)
    outer, inner, k2, plain2 = mod.unwrap_response(wire)
    ok_key = (k2 == key)
    ok_plain = (plain == plain2)
    ok_len = (len(key) == mod.KEY_LEN == 32)
    return {'wire': wire, 'plain': plain, 'outer': outer, 'inner': inner,
            'key_ok': ok_key, 'plain_roundtrip': ok_plain, 'key_len_ok': ok_len}


def inner_json_text(mod, obj):
    return json.dumps(obj, ensure_ascii=False, separators=(',', ':'))


def verify(args):
    path = resolve_target(args.target)
    if not os.path.exists(path):
        die('target not found: %s' % path)
    text = read_text(path)
    info = analyze(text)
    provider = _install_crypto()
    codec_dir = os.path.dirname(os.path.abspath(path))

    # --------------------------------------- captures (used by [2] fallback and by [3])
    caps = args.captures
    if not caps:
        here = os.path.dirname(os.path.abspath(__file__))
        for cand in (os.path.join(here, '..', '..', '..', '..', 'report', '_tmp',
                                  'official_decoded_201'),
                     os.path.join(os.getcwd(), 'report', '_tmp',
                                  'official_decoded_201')):
            cand = os.path.abspath(cand)
            if os.path.isdir(cand):
                caps = cand
                break

    print('=' * 78)
    print('patch_requestid.py --verify')
    print('=' * 78)
    print('target        : %s' % path)
    print('sha256        : %s' % sha256_file(path))
    print('state         : %s' % ('PATCHED (BA_PATCH_REQUESTID v1)' if info['patched']
                                   else 'PRISTINE (no patch)'))
    print('aes provider  : %s' % provider)
    print('codec dir     : %s' % codec_dir)

    # ---- switch file: force a private one so a stray server file cannot skew the run
    tmpdir = tempfile.mkdtemp(prefix='rid_verify_')
    switch = os.path.join(tmpdir, 'cn_inner_requestid.txt')
    with io.open(switch, 'w', encoding='utf-8') as f:
        f.write('1\n')
    mod = load_codec(path, switch_file=switch)
    missing = [n for n in ('wrap_response', 'unwrap_response', 'KEY_LEN', 'IV_FIXED')
               if not hasattr(mod, n)]
    if missing:
        die('the module at %s has no %s -- that is not a full cn_wire.py (a reduced test '
            'stub?), so there is nothing to verify. Point --target at the real codec.'
            % (path, ', '.join(missing)))
    print('switch file   : %s (=1)' % switch)
    print('captures      : %s' % (caps or 'NOT FOUND (gate fallback disabled)'))
    print()

    failures = []
    rid = 'a1b2c3d4-e5f6-4a7b-8c9d-0a1b2c3d4e5f'

    # ------------------------------------------------------------------ [2] gates
    bridge_src = args.bridge_src
    if not bridge_src:
        for cand in (os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  '_baseline', 'account_auth_probe.py'),
                     '/www/wwwroot/bapatch/tools/account_auth_probe.py'):
            if os.path.exists(cand):
                bridge_src = cand
                break
    cases = build_gate_cases(codec_dir, bridge_src, caps)
    if not cases:
        die('no gate builders available (need cn_inner27.py / cn_nick.py next to cn_wire.py '
            'or --bridge-src <account_auth_probe.py>)')
    print('-- [2] the 6 gated protocols, rendered through the real codec --')
    print('   %-7s %-20s %5s %5s %8s %8s %6s %-6s %s' % (
        'proto', 'protocol name', 'keys', 'keys', 'inner', 'inner', 'delta', 'outer', 'case'))
    print('   %-7s %-20s %5s %5s %8s %8s %6s %-6s %s' % (
        '', '', 'pre', 'post', 'bytes', 'bytes', 'bytes', '', ''))
    print('   ' + '-' * 94)
    gate_rows = []
    for case in cases:
        proto, name = case['proto'], case['name']
        obj_off = copy.deepcopy(case['obj'])
        obj_on = copy.deepcopy(case['obj'])
        # OFF render == pre-patch behaviour (monkeypatch the switch predicate, no file I/O)
        had = getattr(mod, 'inner_requestid_enabled', None)
        if had is not None:
            mod.inner_requestid_enabled = lambda: False
        try:
            pre = render(mod, name, obj_off, rid)
            pre_j = inner_json_text(mod, obj_off)
        finally:
            if had is not None:
                mod.inner_requestid_enabled = had
        post = render(mod, name, obj_on, rid)
        post_j = inner_json_text(mod, obj_on)
        k_post = list(post['inner'].keys())
        pos = k_post.index('RequestId') if 'RequestId' in k_post else None
        eq = (post['outer'].get('requestid') == post['inner'].get('RequestId'))
        same_keys = (sorted(pre['inner'].keys()) ==
                     sorted(k for k in post['inner'].keys() if k != 'RequestId'))
        delta = len(post_j.encode('utf-8')) - len(pre_j.encode('utf-8'))
        print('   %-7d %-20s %5d %5d %8d %8d %+6d %-6s %s' % (
            proto, name, len(pre['inner']), len(post['inner']),
            len(pre_j.encode('utf-8')), len(post_j.encode('utf-8')), delta,
            'OK' if eq else 'MISMATCH', case['builder']))
        row = {'proto': proto, 'name': name, 'keys_pre': len(pre['inner']),
               'keys_post': len(post['inner']),
               'bytes_pre': len(pre_j.encode('utf-8')),
               'bytes_post': len(post_j.encode('utf-8')), 'delta': delta,
               'rid_index': pos, 'equal': eq, 'no_key_lost': same_keys,
               'prefix': k_post[:pos] if pos is not None else None,
               'wire_ok': post['key_ok'] and post['plain_roundtrip'] and post['key_len_ok'],
               'wire_chars_pre': len(pre['wire']), 'wire_chars_post': len(post['wire']),
               'builder': case['builder'],
               'pre_has_rid': 'RequestId' in pre['inner']}
        gate_rows.append(row)
        if not eq:
            failures.append('%s/%d: outer.requestid != inner.RequestId' % (name, proto))
        if not same_keys:
            failures.append('%s/%d: key set changed by the patch' % (name, proto))
        if pos is None:
            failures.append('%s/%d: inner RequestId absent after the patch' % (name, proto))
        if not row['wire_ok']:
            failures.append('%s/%d: AES/pkcs7/base64 round-trip broken' % (name, proto))
        if delta <= 0 and not row['pre_has_rid']:
            failures.append('%s/%d: no byte increase although RequestId was inserted'
                            % (name, proto))
        for n in case['notes']:
            print('        note: %s' % n)
    print()

    # ------------------------------------------------- [3] official shape replay
    print('-- [3] official shape replay: strip RequestId from every capture, re-render --')
    replay = {'files': 0, 'ok': 0, 'order_exact': 0, 'bad': []}
    if not caps or not os.path.isdir(caps):
        print('   SKIP: captures not found (pass --captures <dir>)')
    else:
        files = sorted(glob_glob(caps, '*response.json'))
        print('   captures: %s (%d files)' % (caps, len(files)))
        for fp in files:
            try:
                doc = json.load(io.open(fp, encoding='utf-8'))
                outer0 = json.loads(doc['plain'])
                offi = json.loads(outer0['packet'])
            except Exception as e:
                replay['bad'].append((os.path.basename(fp), 'unparsable: %r' % (e,)))
                continue
            if not isinstance(offi, dict) or 'RequestId' not in offi:
                replay['bad'].append((os.path.basename(fp), 'no official RequestId'))
                continue
            offi_keys = list(offi.keys())
            offi_rid_index = offi_keys.index('RequestId')
            stripped = {k: v for k, v in offi.items() if k != 'RequestId'}
            case_rid = 'a1b2c3d4-e5f6-4a7b-8c9d-0a1b2c3d4e5f'
            obj = copy.deepcopy(stripped)
            r = render(mod, outer0.get('protocol') or 'Unknown', obj, case_rid)
            replay['files'] += 1
            keys_now = list(r['inner'].keys())
            eqv = (r['outer'].get('requestid') == r['inner'].get('RequestId') == case_rid)
            order = (keys_now == offi_keys)
            if eqv:
                replay['ok'] += 1
            if order:
                replay['order_exact'] += 1
            if not eqv:
                replay['bad'].append((os.path.basename(fp), 'outer != inner'))
            elif not order:
                replay['bad'].append((os.path.basename(fp),
                                      'key order differs: got %r want %r'
                                      % (keys_now[:6], offi_keys[:6])))
        print('   rendered              : %d/%d' % (replay['files'], len(files)))
        print('   outer.requestid==inner: %d/%d' % (replay['ok'], replay['files']))
        print('   key order == official : %d/%d  (position of RequestId reproduced exactly)'
              % (replay['order_exact'], replay['files']))
        for b in replay['bad'][:10]:
            print('   BAD %s: %s' % b)
        if replay['bad']:
            failures.append('official replay: %d failure(s)' % len(replay['bad']))
        if replay['files'] == 0:
            failures.append('official replay: no capture could be rendered')
    print()

    # --------------------------------------------------- [4] "already has RequestId"
    print('-- [4] inner already carries a DIFFERENT RequestId -> must be synced, not duplicated --')
    probe = {'Protocol': 90004, 'ServerTimeTicks': 0, 'ServerNotification': 0,
             'SessionKey': {'AccountServerId': 0, 'MxToken': ''},
             'RequestId': '00000000-0000-4000-8000-000000000000', 'Notices': []}
    before_keys = list(probe.keys())
    r = render(mod, 'Management_Data', probe, rid)
    kept_pos = list(r['inner'].keys()).index('RequestId') if 'RequestId' in r['inner'] else -1
    sync_ok = (r['inner'].get('RequestId') == rid and r['outer'].get('requestid') == rid
               and list(r['inner'].keys()) == before_keys)
    print('   RequestId: %s -> %s' % ('00000000-...', r['inner'].get('RequestId')))
    print('   key order unchanged    : %s' % (list(r['inner'].keys()) == before_keys))
    print('   still exactly one key  : %s' % (list(r['inner'].keys()).count('RequestId') == 1))
    print('   index kept             : %d' % kept_pos)
    print('   %s' % ('PASS' if sync_ok else 'FAIL'))
    if not sync_ok:
        failures.append('sync branch broken')
    print()

    # ----------------------------------------------------------- [5] kill switch
    print('-- [5] kill switch (no code edit, instant rollback) --')
    sw_ok = True
    with io.open(switch, 'w', encoding='utf-8') as f:
        f.write('0\n')
    mod_off = load_codec(path, switch_file=switch)
    r_off = render(mod_off, 'Management_Data',
                   {'Protocol': 90004, 'ServerTimeTicks': 0, 'ServerNotification': 0,
                    'Notices': []}, rid)
    off_ok = ('RequestId' not in r_off['inner'])
    print('   switch=0 -> inner RequestId present: %s  (expected False)'
          % ('RequestId' in r_off['inner']))
    with io.open(switch, 'w', encoding='utf-8') as f:
        f.write('1\n')
    mod_on = load_codec(path, switch_file=switch)
    r_on = render(mod_on, 'Management_Data',
                  {'Protocol': 90004, 'ServerTimeTicks': 0, 'ServerNotification': 0,
                   'Notices': []}, rid)
    on_ok = (r_on['inner'].get('RequestId') == r_on['outer'].get('requestid'))
    print('   switch=1 -> outer == inner          : %s  (expected True)' % on_ok)
    # no switch file at all => ON
    os.remove(switch)
    mod_def = load_codec(path, switch_file=switch)
    r_def = render(mod_def, 'Management_Data',
                   {'Protocol': 90004, 'ServerTimeTicks': 0, 'ServerNotification': 0,
                    'Notices': []}, rid)
    def_ok = (r_def['inner'].get('RequestId') == r_def['outer'].get('requestid'))
    print('   no switch file -> default ON        : %s  (expected True)' % def_ok)
    sw_ok = off_ok and on_ok and def_ok
    print('   %s' % ('PASS' if sw_ok else 'FAIL'))
    if not sw_ok:
        failures.append('kill switch does not behave as documented')
    print()

    # -------------------------------------------------------- [6] non-dict safety
    print('-- [6] non-dict inner (bare list/str payloads must still work) --')
    ok_nd = True
    for bad in ([], 'x', 42, None):
        try:
            w, p, k = mod.wrap_response('Whatever', bad, rid)
            o, i, k2, pl = mod.unwrap_response(w)
            ok_nd &= (i == bad and o.get('requestid') == rid)
        except Exception as e:
            ok_nd = False
            print('   FAIL on %r: %r' % (bad, e))
    print('   list/str/int/None payloads          : %s' % ('PASS' if ok_nd else 'FAIL'))
    if not ok_nd:
        failures.append('non-dict inner broke wrap_response')
    print()

    # ---------------------------------------------------------------- verdict
    print('=' * 78)
    if not info['patched']:
        print('RESULT: FAIL -- target is PRISTINE (patch not applied).')
        print('        That is the expected "before" state: the codec writes the outer')
        print('        requestid only, the generated inner packets above have no RequestId.')
    if failures:
        print('RESULT: FAIL (%d)' % len(failures))
        for f in failures:
            print('   - %s' % f)
    else:
        print('RESULT: PASS -- outer.requestid == inner.RequestId on every rendered packet,')
        print('        key position matches the official capture, AES/pkcs7/base64 intact,')
        print('        kill switch works, non-dict payloads unaffected.')
    print('=' * 78)
    # machine-readable dump for the report
    dump = {'target': path, 'sha256': sha256_file(path), 'patched': info['patched'],
            'aes_provider': provider, 'gates': gate_rows,
            'replay': {k: replay[k] for k in ('files', 'ok', 'order_exact')},
            'replay_bad': replay['bad'][:20],
            'failures': failures, 'verdict': 'PASS' if (not failures and info['patched'])
            else 'FAIL'}
    out_json = getattr(args, 'json_out', None)
    if out_json:
        write_text_atomic(out_json, json.dumps(dump, ensure_ascii=False, indent=2))
        print('json     : %s' % out_json)
    shutil.rmtree(tmpdir, ignore_errors=True)
    return 0 if (not failures and info['patched']) else 1


def glob_glob(dirpath, pattern):
    import fnmatch
    out = []
    for n in os.listdir(dirpath):
        if fnmatch.fnmatch(n, pattern):
            out.append(os.path.join(dirpath, n))
    return out


# =============================================================================
# 6. CLI
# =============================================================================
def do_switch(args):
    path = args.switch_file or DEFAULT_SWITCH
    if args.dry_run:
        print('would write %r to %s (dry-run)' % (str(int(args.switch)), path))
        return 0
    try:
        write_text_atomic(path, str(int(args.switch)) + '\n')
    except Exception as e:
        die('cannot write switch file %s: %r\n'
            '  (the switch lives on the server; run it there, or pass --switch-file)'
            % (path, e))
    print('switch   : %s = %d' % (path, args.switch))
    return 0


def do_aes_selftest():
    provider = _install_crypto()
    print('aes provider: %s' % provider)
    if provider == 'pure-aes-shim':
        print('FIPS-197 (3 key sizes) + NIST SP800-38A CBC vectors: PASS')
    else:
        import binascii as _b
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        key = _b.unhexlify('000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f')
        pt = _b.unhexlify('00112233445566778899aabbccddeeff')
        e = Cipher(algorithms.AES(key), modes.ECB()).encryptor()
        got = e.update(pt) + e.finalize()
        print('FIPS-197 AES-256 vector: %s'
              % ('PASS' if got.hex() == '8ea2b7ca516745bfeafc49904b496089' else 'FAIL'))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(add_help=True,
                                 description=__doc__.splitlines()[0])
    ap.add_argument('--target', default=None,
                    help='cn_wire.py file OR the directory containing it '
                         '(default: %s)' % LIVE_TARGET)
    ap.add_argument('--apply', action='store_true', help='backup + write the patch')
    ap.add_argument('--verify', action='store_true', help='render and prove outer == inner')
    ap.add_argument('--rollback', action='store_true', help='restore the newest clean backup')
    ap.add_argument('--dry-run', action='store_true',
                    help='show the diff / plan, write nothing')
    ap.add_argument('--write-switch', type=int, default=None, choices=(0, 1),
                    help='after --apply: also write the kill-switch file')
    ap.add_argument('--switch-file', default=None,
                    help='kill-switch path (default %s)' % DEFAULT_SWITCH)
    ap.add_argument('--switch', type=int, default=None, choices=(0, 1),
                    help='write the kill-switch file and exit (0=off, 1=on)')
    ap.add_argument('--captures', default=None,
                    help='official_decoded_201 directory for the 109-response replay')
    ap.add_argument('--bridge-src', default=None,
                    help='live account_auth_probe.py (ast source of the 24000/90004/1017 '
                         'inner objects)')
    ap.add_argument('--json-out', default=None, help='write the verify result as JSON')
    ap.add_argument('--selftest-aes', action='store_true', help='test the AES provider')
    ap.add_argument('--force', action='store_true',
                    help='apply even if already patched / revert by text edit on rollback')
    ap.add_argument('--rollback-force', action='store_true',
                    help='with --rollback: take the newest backup even if it is patched')
    args = ap.parse_args(argv)

    if args.selftest_aes:
        return do_aes_selftest()
    if args.switch is not None:
        return do_switch(args)
    if args.rollback:
        return do_rollback(args)
    if args.apply or args.dry_run:
        return do_apply(args)
    if args.verify:
        return verify(args)
    print(__doc__)
    return 2


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Fail as e:
        print('FATAL: %s' % e)
        sys.exit(2)
