#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
find_gamemainconfig.py -- locate + decrypt the encrypted Unity TextAsset
`GameMainConfig` (field `ServerInfoDataUrl`) inside a BA APK / extracted dir.

Three independent passes, each reported separately:

  P1  NAME PASS      -- m_Name is stored PLAINTEXT (only m_Script is encrypted).
                        Find ASCII "<name>", verify the u32 length prefix, then
                        read the u32 m_Script length that follows and take the blob.
  P2  PERIOD-8 PASS  -- no format knowledge needed. UTF-16LE plaintext has zero
                        high bytes, so with an 8-byte XOR key cycled, the
                        ciphertext's odd-offset bytes equal the key's odd-offset
                        bytes: 23 06 72 57 23 06 72 57 ...  (report/56:985).
                        We search a strided byte view (stride 2) for that 8-byte
                        cycle in all 4 rotations -> exact file offsets.
  P3  TEXTASSET PASS -- best-effort Unity SerializedFile walk: header
                        (metadata_size, file_size, version, data_offset, endian),
                        objects table, class_id 49 => list every TextAsset name.

Decryption hypotheses tested for every candidate:
  H1  key8 cycled, phase 0        (=> create_key(name) reused, period 8)
  H2  key8 cycled, phase 1..7     (in case the blob starts mid-cycle)
  H3  continuous MT keystream     (xor_bytes(); == H1 for the first 8 bytes only)
Winner is the one that parses as JSON / decodes to sane text.

Usage:
    python find_gamemainconfig.py <apk-or-dir> [--name GameMainConfig] [--dump DIR]
                                  [--all] [--quiet]
Examples:
    python find_gamemainconfig.py "C:\\...\\base.apk" --dump _extract
    python find_gamemainconfig.py assets/bin/Data --all
"""
import argparse
import io
import json
import os
import struct
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from CRYPTO_MT import MT, create_key, keystream, xor_bytes, xxhash32  # noqa: E402

# ------------------------------------------------------------------ helpers


def u32(b, o):
    return struct.unpack_from('<I', b, o)[0]


def align4(n):
    return (n + 3) & ~3


def score_plain(raw: bytes):
    """Return (score, text, encoding). Score = how much this looks like the JSON."""
    best = (-1, None, None)
    for enc in ('utf-16-le', 'utf-8', 'latin-1'):
        try:
            t = raw.decode(enc)
        except UnicodeDecodeError:
            continue
        s = 0
        st = t.lstrip('\ufeff \t\r\n')
        if st[:1] == '{':
            s += 40
        if '"ServerInfoDataUrl"' in t:
            s += 60
        if '"ConnectionGroups"' in t or '"OverrideConnectionGroups"' in t:
            s += 20
        try:
            json.loads(st.split('\x00')[0])
            s += 40
        except Exception:
            pass
        printable = sum(1 for c in t if c.isprintable() or c in '\r\n\t')
        s += (printable * 10) // max(1, len(t))
        if s > best[0]:
            best = (s, t, enc)
    return best


def try_decrypt(blob: bytes, name: str):
    """Yield (hypothesis, plaintext_bytes) candidates, best-effort dedup."""
    k8 = create_key(name)
    seen = set()

    def emit(tag, out):
        h = hash(out)
        if h in seen:
            return
        seen.add(h)
        return (tag, out)

    # H1: key8 cycled, phase 0
    ks = (k8 * ((len(blob) // 8) + 2))[:len(blob)]
    yield emit('H1 key8-cycled phase0', bytes(a ^ b for a, b in zip(blob, ks)))
    # H2: other phases
    for ph in range(1, 8):
        ks2 = (k8 * ((len(blob) // 8) + 3))[ph:ph + len(blob)]
        yield emit(f'H2 key8-cycled phase{ph}', bytes(a ^ b for a, b in zip(blob, ks2)))
    # H3: continuous keystream
    yield emit('H3 MT continuous stream', xor_bytes(name, blob))


# ------------------------------------------------------- pass 1: name search


def pass_name(data: bytes, name: str, fname: str, out):
    """Find TextAsset objects by their plaintext m_Name + length prefix."""
    nb = name.encode('ascii')
    ln = len(nb)
    pref = struct.pack('<I', ln)
    hits = []
    pos = data.find(nb)
    while pos >= 0:
        pfx = pos - 4
        if pfx >= 0 and data[pfx:pfx + 4] == pref:
            script_len_off = align4(pos + ln)
            if script_len_off + 4 <= len(data):
                slen = u32(data, script_len_off)
                data_off = script_len_off + 4
                if 0 < slen <= len(data) - data_off:
                    hits.append({
                        'name_prefix_off': pfx,
                        'name_off': pos,
                        'script_len_off': script_len_off,
                        'data_off': data_off,
                        'declared_len': slen,
                    })
        pos = data.find(nb, pos + 1)

    for h in hits:
        blob = data[h['data_off']:h['data_off'] + h['declared_len']]
        best = None
        for tag, out_b in try_decrypt(blob, name):
            if out_b is None:
                continue
            sc, txt, enc = score_plain(out_b)
            if best is None or sc > best[0]:
                best = (sc, tag, out_b, txt, enc)
        h.update(dict(file=fname, blob=blob, best=best))
        out.append(h)
    return hits


# -------------------------------------------------- pass 2: period-8 signature


def pass_signature(data: bytes, key8: bytes, fname: str, out, min_run: int = 10):
    """Find regions whose odd-offset bytes repeat the key's odd bytes with period 8.

    Strided trick: with plaintext UTF-16LE, positions at stride 2 inside one
    parity hold the key's bytes in a 4-cycle. Search both parities x 4 rotations.
    """
    # key bytes that land on the 'high byte' lane: k[1],k[3],k[5],k[7]
    lane = bytes((key8[1], key8[3], key8[5], key8[7]))
    cyc = lane * 2                      # 8 bytes
    needles = [cyc[r:] + cyc[:r] for r in range(4)]
    hits = []
    for parity in (0, 1):
        view = data[parity::2]
        found = []
        for rot, nd in enumerate(needles):
            p = view.find(nd)
            while p >= 0:
                found.append((p * 2 + parity, rot))
                p = view.find(nd, p + 1)
    # verify + merge adjacent
    found.sort()
    verified = []
    for off, rot in found:
        # off = offset of the 1st lane byte; require min_run more lane bytes
        span = 2 * min_run
        if off + span >= len(data):
            continue
        ok = True
        for j in range(min_run):
            exp = lane[(rot + j) % 4]
            if data[off + 2 * j] != exp:
                ok = False
                break
        if ok:
            verified.append(off)
    # merge into runs
    merged = []
    for o in verified:
        if merged and o - merged[-1][1] <= 16:
            merged[-1][1] = max(merged[-1][1], o + 2 * min_run)
        else:
            merged.append([o, o + 2 * min_run])
    for a, b in merged:
        hits.append({'file': fname, 'lane_start': a, 'lane_end': min(b, len(data))})
    out.extend(hits)
    return hits


# --------------------------------------- pass 3: TextAsset enumeration + header


def container_probe(data: bytes):
    """Report the Unity container header numbers we can recognise, LE or BE.

    NOTE: the file that actually holds GameMainConfig in the 1.93 build is a
    big-endian SerializedFile whose field order does not match the AssetStudio
    layout (metadata 0x0..0xFFF, data from 0x1000, version 22, file_size 4616).
    We therefore report numbers instead of pretending a strict walk succeeded.
    """
    if len(data) < 64:
        return None
    ver_le = struct.unpack_from('<I', data, 8)[0]
    ver_be = struct.unpack_from('>I', data, 8)[0]
    if ver_le in (15, 16, 17, 21, 22, 23, 24):
        return {'version': ver_le, 'endian': 'LE'}
    if ver_be in (15, 16, 17, 21, 22, 23, 24):
        return {'version': ver_be, 'endian': 'BE'}
    # UnityFS bundle?
    if data[:7] == b'UnityFS':
        return {'version': None, 'endian': 'bundle(UnityFS)'}
    return None


def pass_textassets(data: bytes, fname: str, out, maxlen: int = 128):
    """Enumerate every (u32 len)(printable name)(align4)(u32 script_len)(blob).

    This is the class_id=49 TextAsset layout *without* needing the object table,
    so it works on LE/BE and on the odd 1.93 container alike.
    """
    n = len(data)
    hits = []
    for p in range(4, n - 8):
        ln = u32(data, p - 4)
        if not (1 <= ln <= maxlen) or p + ln + 4 > n:
            continue
        nb = data[p:p + ln]
        if not all(32 <= c < 127 for c in nb):
            continue
        sl_off = align4(p + ln)
        if sl_off + 4 > n:
            continue
        slen = u32(data, sl_off)
        doff = sl_off + 4
        if not (0 < slen <= n - doff) or slen > 4 * 1024 * 1024:
            continue
        hits.append({'file': fname, 'name': nb.decode('ascii'),
                     'name_off': p, 'script_len_off': sl_off,
                     'data_off': doff, 'script_len': slen})
    out.extend(hits)
    return hits


# ---------------------------------------------------------------- drivers


def iter_sources(path):
    """Yield (member_name, bytes). APK/zip -> members under assets/bin/Data."""
    if os.path.isdir(path):
        for root, _dirs, files in os.walk(path):
            for f in files:
                fp = os.path.join(root, f)
                try:
                    with open(fp, 'rb') as fh:
                        yield os.path.relpath(fp, path), fh.read()
                except OSError:
                    continue
    else:
        with zipfile.ZipFile(path) as z:
            for i in z.infolist():
                if i.is_dir():
                    continue
                if 'assets/bin/Data' not in i.filename and not i.filename.endswith('.assets'):
                    continue
                yield i.filename, z.read(i)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('source')
    ap.add_argument('--name', default='GameMainConfig')
    ap.add_argument('--dump', default=None, help='dir to copy the hit file + plaintext into')
    ap.add_argument('--all', action='store_true', help='scan every member, not just assets/bin/Data')
    ap.add_argument('--quiet', action='store_true')
    a = ap.parse_args(argv)

    key8 = create_key(a.name)
    print(f'[*] target name = {a.name!r}  ({len(a.name)} bytes)')
    print(f'[*] create_key({a.name!r}) = {key8.hex(" ")}')
    print(f'[*]   lane bytes (k[1],k[3],k[5],k[7]) = {key8[1]:02x} {key8[3]:02x} {key8[5]:02x} {key8[7]:02x}')
    print(f'[*] source = {a.source}')

    name_hits, sig_hits, ta_hits = [], [], []
    nfiles = nbytes = 0
    for fname, data in iter_sources(a.source):
        nfiles += 1
        nbytes += len(data)
        if b'GameMainConfig' in data:
            pass_name(data, a.name, fname, name_hits)
        pass_signature(data, key8, fname, sig_hits)
        if not a.quiet:
            pass_textassets(data, fname, ta_hits)

    print(f'[P0] scanned {nfiles} members / {nbytes} bytes')
    print(f'[P1] name hits      : {len(name_hits)}')
    print(f'[P2] period-8 hits  : {len(sig_hits)}')
    if not a.quiet:
        print(f'[P3] TextAsset-shaped objects (name+len+bold): {len(ta_hits)}'
              f' across {len({h["file"] for h in ta_hits})} files')
        if ta_hits:
            for h in ta_hits[:6]:
                print(f'       {h["file"]}  name={h["name"]!r} '
                      f'script_len={h["script_len"]} data@0x{h["data_off"]:X}')

    if sig_hits:
        print('[P2] signature hits (file, lane_start, lane_end):')
        for h in sig_hits[:20]:
            print(f'       {h["file"]}  0x{h["lane_start"]:X} .. 0x{h["lane_end"]:X}')

    winner = None
    for h in name_hits:
        sc, tag, blob, txt, enc = h['best']
        print(f"\n  file         : {h['file']}")
        print(f"  name @       : 0x{h['name_off']:X} (prefix 0x{h['name_prefix_off']:X})")
        print(f"  script len @ : 0x{h['script_len_off']:X}  value {h['declared_len']}")
        print(f"  data @       : 0x{h['data_off']:X} .. 0x{h['data_off']+h['declared_len']:X}"
              f"  ({h['declared_len']} B)")
        print(f"  decrypt      : {tag}   score={sc} enc={enc}")
        print(f"  first 32 ct  : {h['blob'][:32].hex(' ')}")
        print(f"  first 32 pt  : {blob[:32].hex(' ')}")
        print(f"  key          : {(k8 := create_key(a.name)).hex(' ')}  (cycled, period 8)")
        if txt:
            body = txt.split('\x00')[0].strip()
            try:
                j = json.loads(body)
                print('  JSON         : OK')
                print(json.dumps(j, ensure_ascii=False, indent=2)[:4000])
                if winner is None:
                    winner = (h, j, body)
            except Exception as e:
                print(f'  JSON         : not parseable ({e}); head={body[:200]!r}')

    if a.dump and winner:
        os.makedirs(a.dump, exist_ok=True)
        h, j, body = winner
        base = f"GameMainConfig_{h['file'].replace('/', '_').replace(':', '_')}"
        src_path = os.path.join(a.dump, base + '.bin')
        dst_path = os.path.join(a.dump, base + '.json')
        for fname, data in iter_sources(a.source):
            if fname == h['file']:
                with open(src_path, 'wb') as fh:
                    fh.write(data)
                break
        with open(dst_path, 'w', encoding='utf-8') as fh:
            fh.write(body)
        print(f'\n[dump] {src_path}')
        print(f'[dump] {dst_path}')
    return 0 if winner else 1


if __name__ == '__main__':
    sys.exit(main())
