#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""official_probe2.py -- 4 requests only (2 accounts x 2 header sets). New file, touches nothing.
Interval >= 2s between requests. Records everything, never retries.
"""
import base64, gzip, hashlib, json, os, socket, ssl, time
from datetime import datetime
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

HOST = "gsqc-api.bluearchive-cn.com"
PATH = "/api/account/auth"
OUT = "/www/wwwroot/_ba_state/captures_official"
UA = "BestHTTP/2 v2.4.0"

ACCOUNTS = [
    ("A", "1013178778", "076b037e8ff4226c972cd8ab18d914f0db517852"),
    ("B", "314816420",  "61de1d1b7519ab1231866f74c11fcfdd1f80b210"),
]
HEADERSETS = [
    ("h1", {"APP-VER": "3.0.2", "PLATFORM-ID": "1", "CHANNEL-ID": "1", "SERVER-NAME": "prod"}),
    ("h2", {"APP-VER": "3.0.2", "PLATFORM-ID": "1", "CHANNEL-ID": "1",
            "RESOURCE-VER": "202611051844", "TABLE-VER": "202611051826"}),
]


def b32(name):
    return base64.b32encode(hashlib.md5(name.encode("utf-16-le")).digest()).decode().rstrip("=")


def build_body(dev_id, token, counter=1):
    H = (1002 << 32) | counter
    frag = (',"DevId":"%s","OSVersion":"Android OS 17 / API-37",'
            '"DeviceUniqueId":"<REDACTED_DEVID>","DeviceModel":"OnePlus PLR110",'
            '"DeviceSystemMemorySize":15104,"Token":"%s","SdkPid":"CN-BA","SubChannel":"",'
            '"ResUrl":"https://static.bluearchive-cn.com/prodm39","Hash":%d}' % (dev_id, token, H))
    plain = frag.encode()
    key = base64.b16encode(os.urandom(16)).lower()[:32]
    iv = os.urandom(16)
    pad = 16 - len(plain) % 16
    plain += bytes([pad]) * pad
    e = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    ct = e.update(plain) + e.finalize()
    inner = iv + ct + key
    pkt = base64.b64encode(len(inner).to_bytes(4, "little") + gzip.compress(inner)).decode()
    boundary = "BestHTTP_HTTPMultiPartForm_%08X" % (int(time.time() * 1000) & 0xFFFFFFFF)
    def part(n, v):
        return ('--%s\r\nContent-Disposition: form-data; name="%s"\r\n'
                'Content-Type: text/plain; charset=utf-8\r\nContent-Length: %d\r\n\r\n%s\r\n'
                % (boundary, n, len(v), v)).encode()
    body = (part("protocol", b32("Account_Auth")) + part("encode", "True") +
            part("packet", pkt) + ("--%s--\r\n" % boundary).encode())
    return body, boundary


def decrypt(raw):
    txt = raw.decode("utf-8", "replace").strip()
    if txt.startswith("{"):
        return txt, "plaintext-json"
    try:
        blob = base64.b64decode(txt + "=" * ((4 - len(txt) % 4) % 4))
    except Exception as e:
        return None, "b64-fail:%r" % e
    cands = [("iv+ct+key32", blob)]
    try:
        cands.append(("u32+gzip", gzip.decompress(blob[4:])))
    except Exception:
        pass
    try:
        cands.append(("gzip", gzip.decompress(blob)))
    except Exception:
        pass
    for name, buf in cands:
        if len(buf) <= 48:
            continue
        iv, ct, key = buf[:16], buf[16:-32], buf[-32:]
        try:
            d = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
            pt = d.update(ct) + d.finalize()
            pad = pt[-1]
            if 1 <= pad <= 16 and pt.endswith(bytes([pad]) * pad):
                pt = pt[:-pad]
            s = pt.decode("utf-8", "replace")
            if s.strip():
                return s, name
        except Exception:
            continue
    return None, "all-layouts-failed(blob=%d)" % len(blob)


def one(acct_tag, dev_id, token, hs_tag, extra):
    body, boundary = build_body(dev_id, token)
    base_h = {"Host": HOST, "User-Agent": UA, "Accept": "*/*", "Accept-Encoding": "gzip",
              "Content-Type": "multipart/form-data; boundary=%s" % boundary,
              "Content-Length": str(len(body))}
    base_h.update(extra)
    req = ("POST %s HTTP/1.1\r\n" % PATH) + "".join("%s: %s\r\n" % kv for kv in base_h.items()) + \
          "Connection: close\r\n\r\n"
    raw_req = req.encode() + body
    ips = sorted({r[4][0] for r in socket.getaddrinfo(HOST, 443, socket.AF_INET, socket.SOCK_STREAM)})
    res = {"acct": acct_tag, "hset": hs_tag, "dev_id": dev_id, "token": token[:12] + "...",
           "req_bytes": len(raw_req), "ts": datetime.now().strftime("%H:%M:%S")}
    for ip in ips:
        try:
            ctx = ssl.create_default_context()
            ss = ctx.wrap_socket(socket.create_connection((ip, 443), timeout=30), server_hostname=HOST)
            ss.sendall(raw_req)
            buf = b""
            while True:
                c = ss.recv(65536)
                if not c:
                    break
                buf += c
            ss.close()
            sep = buf.find(b"\r\n\r\n")
            head, rb = buf[:sep], buf[sep + 4:]
            res["status"] = head.split(b"\r\n")[0].decode("latin1")
            h = {}
            for line in head.split(b"\r\n")[1:]:
                if b":" in line:
                    k, v = line.split(b":", 1)
                    h[k.decode("latin1").strip().lower()] = v.decode("latin1").strip()
            res["headers"] = h
            res["ip"] = ip
            if h.get("content-encoding", "").lower() == "gzip" and rb[:2] == b"\x1f\x8b":
                rb = gzip.decompress(rb)
            res["resp_bytes"] = len(rb)
            res["body_text"] = rb.decode("utf-8", "replace")[:400]
            if h.get("transfer-encoding", "").lower() == "chunked":
                out, p = b"", 0
                while p < len(rb):
                    e2 = rb.find(b"\r\n", p)
                    if e2 < 0:
                        break
                    n = int(rb[p:e2].split(b";")[0], 16)
                    if n == 0:
                        break
                    out += rb[e2 + 2:e2 + 2 + n]
                    p = e2 + 2 + n + 2
                rb = out
                res["resp_bytes"] = len(rb)
            pt, how = decrypt(rb) if rb else (None, "empty-body")
            res["decrypt"] = how
            res["plain"] = pt
            break
        except Exception as e:
            res["error"] = repr(e)
    print(json.dumps(res, ensure_ascii=False)[:900])
    return res


out = []
for acct_tag, dev_id, token in ACCOUNTS:
    for hs_tag, extra in HEADERSETS:
        acc = one(acct_tag, dev_id, token, hs_tag, extra)
        out.append(acc)
        time.sleep(2)

os.makedirs(OUT, exist_ok=True)
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
p = os.path.join(OUT, "probe2_%s.json" % ts)
with open(p, "w") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
    f.flush(); os.fsync(f.fileno())
print("saved =", p)
