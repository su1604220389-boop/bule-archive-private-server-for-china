#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import socket, ssl, json, os, time

HOST = 'gsqc-api.bluearchive-cn.com'
OUT = '/www/wwwroot/_ba_state/cn_real_capture'
os.makedirs(OUT, exist_ok=True)

import socket as _s
ips = sorted({r[4][0] for r in _s.getaddrinfo(HOST, 443, _s.AF_INET, _s.SOCK_STREAM)})
print('IPs =', ips)

def fetch(ip):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    s = ctx.wrap_socket(socket.create_connection((ip, 443), timeout=12), server_hostname=HOST)
    req = ("GET /api/state HTTP/1.1\r\n"
           "Host: %s\r\n"
           "APP-VER: 3.0.2\r\nPLATFORM-ID: 1\r\nCHANNEL-ID: 1\r\n"
           "RESOURCE-VER: 202611051844\r\nTABLE-VER: 202611051826\r\n"
           "User-Agent: BestHTTP/2 v2.4.0\r\nAccept: */*\r\n"
           "Accept-Encoding: gzip\r\nConnection: close\r\n\r\n" % HOST).encode()
    s.sendall(req)
    buf = b''
    while True:
        c = s.recv(65536)
        if not c: break
        buf += c
    s.close()
    sep = buf.find(b'\r\n\r\n')
    head, body = buf[:sep], buf[sep+4:]
    return head, body

best = None
for ip in ips:
    try:
        head, body = fetch(ip)
        print('--- %s ---' % ip)
        print(head.decode('latin1').replace('\r\n',' | ')[:300])
        print('body bytes =', len(body))
        if body[:2] == b'\x1f\x8b':
            import gzip
            body = gzip.decompress(body)
            print('(gzip) ->', len(body))
        if not best or len(body) > len(best[1]):
            best = (ip, body)
    except Exception as e:
        print('--- %s ERR %r' % (ip, e))

if not best:
    print('ALL FAILED'); raise SystemExit(1)

ip, body = best
open(os.path.join(OUT,'state_real.json'),'wb').write(body)
print()
print('=== saved state_real.json from %s, %d bytes ===' % (ip, len(body)))
d = json.loads(body)
print('top-level keys =', len(d))
print()
print('%-40s %-10s %s' % ('key','type','value'))
for k in sorted(d.keys()):
    v = d[k]
    t = type(v).__name__
    sval = json.dumps(v, ensure_ascii=False)
    print('%-40s %-10s %s' % (k, t, sval[:300]))
print()
print('=== fields of interest ===')
for k in sorted(d.keys()):
    kl = k.lower()
    if any(x in kl for x in ('url','version','catalog','resource','static','cdn','patch','prodm')):
        print('  %-40s = %s' % (k, json.dumps(d[k], ensure_ascii=False)[:300]))
print()
blob = json.dumps(d, ensure_ascii=False)
import re
print('=== any string containing "prodm" ===')
for m in set(re.findall(r'[^"]*prodm[^"]*', blob)):
    print('  ', m)
