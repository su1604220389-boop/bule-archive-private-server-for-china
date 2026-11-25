#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""official_replay.py -- replay the EXACT captured client multipart body to the official server.
Control experiment for official_auth_probe.py (which returned HTTP 500 with a self-built body).
Sends exactly ONE request.
"""
import socket, ssl, gzip, base64, json, os, time
from datetime import datetime

HOST = "gsqc-api.bluearchive-cn.com"
PATH = "/api/account/auth"
BODY_FILE = "/www/wwwroot/bapatch/cnpacket/cn_multipart_1138.bin"
BOUNDARY = "BestHTTP_HTTPMultiPartForm_2AEF4E90"
OUT = "/www/wwwroot/_ba_state/captures_official"

body = open(BODY_FILE, "rb").read()
print("captured body bytes =", len(body))
print("boundary guess      =", BOUNDARY)
print("boundary in body?   =", BOUNDARY.encode() in body)

ips = sorted({r[4][0] for r in socket.getaddrinfo(HOST, 443, socket.AF_INET, socket.SOCK_STREAM)})
print("IPs =", ips)

req = ("POST %s HTTP/1.1\r\nHost: %s\r\nUser-Agent: BestHTTP/2 v2.4.0\r\n"
       "Content-Type: multipart/form-data; boundary=%s\r\nContent-Length: %d\r\n"
       "Accept: */*\r\nAccept-Encoding: gzip\r\nConnection: close\r\n\r\n"
       % (PATH, HOST, BOUNDARY, len(body))).encode() + body

status = None; hdrs = {}; raw = b""; ip_used = None; t0 = time.time()
for ip in ips:
    try:
        ctx = ssl.create_default_context()
        ss = ctx.wrap_socket(socket.create_connection((ip, 443), timeout=30), server_hostname=HOST)
        ss.sendall(req)
        buf = b""
        while True:
            c = ss.recv(65536)
            if not c: break
            buf += c
        ss.close()
        sep = buf.find(b"\r\n\r\n")
        head, raw = buf[:sep], buf[sep+4:]
        status = head.split(b"\r\n")[0].decode("latin1")
        for line in head.split(b"\r\n")[1:]:
            if b":" in line:
                k, v = line.split(b":", 1); hdrs[k.decode("latin1").strip().lower()] = v.decode("latin1").strip()
        ip_used = ip
        break
    except Exception as e:
        print("ip %s failed: %r" % (ip, e))

el = int((time.time()-t0)*1000)
print()
print("HTTP status =", status, " ip =", ip_used, " elapsed =", el, "ms")
print("headers =", json.dumps(hdrs, ensure_ascii=False))
print("resp bytes =", len(raw))
if raw[:2] == b"\x1f\x8b":
    raw = gzip.decompress(raw); print("(gzip decompressed) ->", len(raw))
print()
txt = raw.decode("utf-8", "replace").strip()
print("resp text head =", txt[:300])
pt = None
if txt.startswith("{"):
    pt = txt
else:
    try:
        blob = base64.b64decode(txt + "="*((4-len(txt)%4)%4))
        iv, ct, key = blob[:16], blob[16:-32], blob[-32:]
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        d = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
        p = d.update(ct)+d.finalize()
        pad = p[-1]
        if 1 <= pad <= 16 and p.endswith(bytes([pad])*pad): p = p[:-pad]
        pt = p.decode("utf-8", "replace")
        print()
        print("=== DECRYPTED ===")
        print(pt)
    except Exception as e:
        print("decrypt failed:", repr(e))

os.makedirs(OUT, exist_ok=True)
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
out = os.path.join(OUT, "replay_%s.json" % ts)
with open(out, "w") as f:
    json.dump({"ts": ts, "status": status, "ip": ip_used, "resp_bytes": len(raw),
               "headers": hdrs, "resp_text": txt, "decrypted": pt}, f, ensure_ascii=False, indent=2)
    f.flush(); os.fsync(f.fileno())
print("saved =", out)
