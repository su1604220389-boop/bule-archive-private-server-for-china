#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""official_auth_probe.py -- send ONE real Account_Auth request to the OFFICIAL server.

Read-only with respect to existing assets: it only imports cn_wire (for nothing but
constants) and does everything else itself. No modification of any existing file.

Safety: exactly ONE request, 30 s timeout, no retries, no loops.
"""
import base64
import gzip
import hashlib
import json
import os
import socket
import ssl
import sys
import time
import uuid
from datetime import datetime

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

HOST = "gsqc-api.bluearchive-cn.com"
PATH = "/api/account/auth"
UA = "BestHTTP/2 v2.4.0"
OUTDIR = "/www/wwwroot/_ba_state/captures_official"

# ---- credentials (from the phone, read-only extraction by phone-ops) ----
USER_ID = "314816420"
TOKEN = "<REDACTED_TOKEN>"
DEVICE_UNIQUE_ID = "<REDACTED_DEVID>"
DEVICE_MODEL = "OnePlus PLR110"
OS_VERSION = "Android OS 17 / API-37"
MEMORY = 15104
SDK_PID = "CN-BA"
SUB_CHANNEL = ""
RES_URL = "https://static.bluearchive-cn.com/prodm39"

PROTOCOL_ID = 1002
COUNTER = 1


def b32(name: str) -> str:
    return base64.b32encode(hashlib.md5(name.encode("utf-16-le")).digest()).decode().rstrip("=")


def build_request_packet() -> str:
    """CN request container: base64( u32le(len) + gzip( iv16 + AES-CBC ct + key32 ) )"""
    hash_val = (PROTOCOL_ID << 32) | COUNTER
    # fragment: starts with ',' and ends with '}'  (matches the real client)
    frag = (',"DevId":"%s","OSVersion":"%s","DeviceUniqueId":"%s","DeviceModel":"%s",'
            '"DeviceSystemMemorySize":%d,"Token":"%s","SdkPid":"%s","SubChannel":"%s",'
            '"ResUrl":"%s","Hash":%d}' % (
                USER_ID, OS_VERSION, DEVICE_UNIQUE_ID, DEVICE_MODEL, MEMORY,
                TOKEN, SDK_PID, SUB_CHANNEL, RES_URL, hash_val))
    # the client's plaintext inside the cipher begins after the {'s protocol part,
    # which travels outside the ciphertext; our captured sample used exactly this shape
    plain = frag.encode("utf-8")

    key = base64.b16encode(os.urandom(16)).lower()[:32]          # 32 ASCII chars
    iv = os.urandom(16)
    pad = 16 - len(plain) % 16
    padded = plain + bytes([pad]) * pad
    enc = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    ct = enc.update(padded) + enc.finalize()
    inner = iv + ct + key
    wire = base64.b64encode(len(inner).to_bytes(4, "little") + gzip.compress(inner))
    return wire.decode()


def build_multipart(protocol_token: str, packet_b64: str) -> (bytes, str):
    boundary = "BestHTTP_HTTPMultiPartForm_%08X" % (uuid.uuid4().int & 0xFFFFFFFF)
    parts = []

    def add(name, value):
        parts.append(("--%s\r\n" % boundary).encode())
        parts.append(('Content-Disposition: form-data; name="%s"\r\n' % name).encode())
        parts.append(b"Content-Type: text/plain; charset=utf-8\r\n")
        parts.append(("Content-Length: %d\r\n\r\n" % len(value.encode())).encode())
        parts.append(value.encode())
        parts.append(b"\r\n")

    add("protocol", protocol_token)
    add("encode", "True")
    add("packet", packet_b64)
    parts.append(("--%s--\r\n" % boundary).encode())
    return b"".join(parts), boundary


def decrypt_response(raw: bytes):
    """Try several layouts; return (plaintext_str, layout_name) or (None, reason)."""
    txt = raw.decode("utf-8", "replace").strip()
    # maybe JSON already (plaintext error)
    if txt.startswith("{"):
        return txt, "plaintext-json"
    try:
        blob = base64.b64decode(txt + "=" * ((4 - len(txt) % 4) % 4))
    except Exception as e:
        return None, "b64-fail:%r" % e

    attempts = []
    # layout A: iv16 + ct + key32  (no length/gzip)  <- what the real error response used
    attempts.append(("iv+ct+key32", blob))
    # layout B: u32 + gzip(iv+ct+key32)
    if len(blob) > 4:
        try:
            attempts.append(("u32+gzip(iv+ct+key32)", gzip.decompress(blob[4:])))
        except Exception:
            pass
    # layout C: gzip(iv+ct+key32)
    try:
        attempts.append(("gzip(iv+ct+key32)", gzip.decompress(blob)))
    except Exception:
        pass

    for name, buf in attempts:
        if len(buf) <= 48:
            continue
        iv, ct, key = buf[:16], buf[16:-32], buf[-32:]
        for kname, k in (("key32-as-is", key), ("key32-b64dec", None)):
            if k is None:
                continue
            try:
                dec = Cipher(algorithms.AES(k), modes.CBC(iv)).decryptor()
                pt = dec.update(ct) + dec.finalize()
                pad = pt[-1]
                if 1 <= pad <= 16 and pt.endswith(bytes([pad]) * pad):
                    pt = pt[:-pad]
                s = pt.decode("utf-8", "replace")
                if s.strip():
                    return s, "%s/%s/pad=%d" % (name, kname, pad)
            except Exception:
                continue
    return None, "all layouts failed (blob=%d bytes)" % len(blob)


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    token = b32("Account_Auth")
    pkt = build_request_packet()
    body, boundary = build_multipart(token, pkt)

    print("=== official_auth_probe ===")
    print("ts            =", ts)
    print("host          =", HOST)
    print("protocol token=", token)
    print("request bytes =", len(body))
    print("UA            =", UA)
    print("Credentials: DevId=%s Token=%s..." % (USER_ID, TOKEN[:12]))

    ips = sorted({r[4][0] for r in socket.getaddrinfo(HOST, 443, socket.AF_INET, socket.SOCK_STREAM)})
    print("resolved IPs  =", ips)

    last_err = None
    raw = b""
    status = None
    hdrs = {}
    ip_used = None
    t0 = time.time()
    for ip in ips:                      # one attempt per IP, still a single logical request set
        try:
            ctx = ssl.create_default_context()      # real CA verification
            sock = socket.create_connection((ip, 443), timeout=30)
            ss = ctx.wrap_socket(sock, server_hostname=HOST)
            req = ("POST %s HTTP/1.1\r\nHost: %s\r\nUser-Agent: %s\r\n"
                   "Content-Type: multipart/form-data; boundary=%s\r\nContent-Length: %d\r\n"
                   "Accept: */*\r\nAccept-Encoding: gzip\r\nConnection: close\r\n\r\n"
                   % (PATH, HOST, UA, boundary, len(body))).encode() + body
            ss.sendall(req)
            buf = b""
            while True:
                chunk = ss.recv(65536)
                if not chunk:
                    break
                buf += chunk
            ss.close()
            sep = buf.find(b"\r\n\r\n")
            head, resp_body = buf[:sep], buf[sep + 4:]
            status = head.split(b"\r\n")[0].decode("latin1")
            for line in head.split(b"\r\n")[1:]:
                if b":" in line:
                    k, v = line.split(b":", 1)
                    hdrs[k.decode("latin1").strip().lower()] = v.decode("latin1").strip()
            if hdrs.get("transfer-encoding", "").lower() == "chunked":
                out, p = b"", 0
                while p < len(resp_body):
                    e = resp_body.find(b"\r\n", p)
                    if e < 0:
                        break
                    n = int(resp_body[p:e].split(b";")[0], 16)
                    if n == 0:
                        break
                    out += resp_body[e + 2:e + 2 + n]
                    p = e + 2 + n + 2
                resp_body = out
            if hdrs.get("content-encoding", "").lower() == "gzip" and resp_body[:2] == b"\x1f\x8b":
                resp_body = gzip.decompress(resp_body)
            raw = resp_body
            ip_used = ip
            break
        except Exception as e:
            last_err = repr(e)
            continue

    elapsed = int((time.time() - t0) * 1000)
    print()
    if status is None:
        print("!!! CONNECTION FAILED:", last_err)
        print("no request completed; nothing written")
        return 1

    print("HTTP status   =", status)
    print("ip used       =", ip_used)
    print("resp bytes    =", len(raw))
    print("elapsed ms    =", elapsed)
    print("resp headers  =", json.dumps(hdrs, ensure_ascii=False))
    print()

    pt, how = decrypt_response(raw)
    print("decrypt       =", "OK via " + how if pt else "FAILED: " + how)
    if pt:
        print()
        print("=== DECRYPTED PLAINTEXT ===")
        print(pt)
        # pretty-print inner JSON if it is the envelope
        try:
            outer = json.loads(pt)
            if isinstance(outer, dict) and "packet" in outer:
                inner = json.loads(outer["packet"])
                print()
                print("=== INNER (packet) DECODED ===")
                print(json.dumps(inner, ensure_ascii=False, indent=2))
        except Exception:
            pass

    rec = {
        "ts": ts, "host": HOST, "path": PATH, "status": status, "ip": ip_used,
        "elapsed_ms": elapsed, "req_bytes": len(body), "resp_bytes": len(raw),
        "resp_b64": raw.decode("latin1"),
        "decrypt": how, "resp_plain": pt,
        "headers": hdrs,
    }
    out = os.path.join(OUTDIR, "auth_%s.json" % ts)
    with open(out, "w") as f:
        json.dump(rec, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    print()
    print("saved         =", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
