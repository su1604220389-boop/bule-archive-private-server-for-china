#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Capture a REAL response from the genuine CN gsqc-api server.
Read-only w.r.t. our own services: opens its own TLS connection to the public IP.
"""
import socket, ssl, json, os, time, base64, zlib, gzip, io, sys

HOST = 'gsqc-api.bluearchive-cn.com'
PATH = '/api/account/auth'
OUTDIR = '/www/wwwroot/_ba_state/cn_real_capture'
os.makedirs(OUTDIR, exist_ok=True)

REAL_IPS = sys.argv[1:] or []
if not REAL_IPS:
    print('ERROR: pass real IPs as argv'); sys.exit(2)

# real client's captured multipart body (1138 B, from 02:42:51)
BODY_PATH = '/www/wwwroot/bapatch/cnpacket/cn_multipart_1138.bin'
BOUNDARY = 'BestHTTP_HTTPMultiPartForm_2AEF4E90'

def build_request(mode, body):
    hdrs = [
        ('Host', HOST),
        ('APP-VER', '3.0.2'),
        ('PLATFORM-ID', '1'),
        ('CHANNEL-ID', '1'),
        ('RESOURCE-VER', '202611051844'),
        ('TABLE-VER', '202611051826'),
        ('User-Agent', 'BestHTTP/2 v2.4.0'),
        ('Accept', '*/*'),
        ('Accept-Encoding', 'gzip'),
    ]
    if mode == 'full':
        hdrs.append(('Content-Type', 'multipart/form-data; boundary=%s' % BOUNDARY))
        hdrs.append(('Content-Length', str(len(body))))
    elif mode == 'headers_only':
        hdrs.append(('Content-Length', '0'))
    else:
        hdrs.append(('Content-Length', '0'))
    lines = ['POST %s HTTP/1.1' % PATH]
    for k, v in hdrs:
        lines.append('%s: %s' % (k, v))
    lines.append('Connection: close')
    lines.append('')
    lines.append('')
    head = '\r\n'.join(lines).encode()
    return head + (body if mode == 'full' else b'')

def one(ip, mode, body, idx):
    rec = {'ip': ip, 'mode': mode, 't': time.strftime('%Y-%m-%d %H:%M:%S'), 'idx': idx}
    raw = build_request(mode, body)
    open(os.path.join(OUTDIR, 'req_%d.http' % idx), 'wb').write(raw)
    rec['req_bytes'] = len(raw)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    t0 = time.time()
    try:
        sock = socket.create_connection((ip, 443), timeout=12)
        ss = ctx.wrap_socket(sock, server_hostname=HOST)
        rec['tls_version'] = ss.version()
        try:
            cert = ss.getpeercert()
            rec['cert_subject'] = str(cert.get('subject'))
            rec['cert_issuer'] = str(cert.get('issuer'))
        except Exception as e:
            rec['cert_err'] = repr(e)
        ss.sendall(raw)
        chunks = []
        while True:
            b = ss.recv(65536)
            if not b: break
            chunks.append(b)
            if sum(len(c) for c in chunks) > 4_000_000: break
        resp = b''.join(chunks)
        ss.close()
        rec['resp_bytes'] = len(resp)
        open(os.path.join(OUTDIR, 'resp_%d.http' % idx), 'wb').write(resp)
        # split head/body
        sep = resp.find(b'\r\n\r\n')
        head, rbody = (resp[:sep], resp[sep+4:]) if sep >= 0 else (resp, b'')
        open(os.path.join(OUTDIR, 'resp_%d.head' % idx), 'wb').write(head)
        open(os.path.join(OUTDIR, 'resp_%d.body' % idx), 'wb').write(rbody)
        rec['status_line'] = head.split(b'\r\n')[0].decode('latin1') if head else ''
        hdrs = {}
        for line in head.split(b'\r\n')[1:]:
            if b':' in line:
                k, v = line.split(b':', 1)
                hdrs[k.decode('latin1').strip().lower()] = v.decode('latin1').strip()
        rec['headers'] = hdrs
        rec['body_bytes'] = len(rbody)
        # gzip?
        if rbody[:2] == b'\x1f\x8b':
            try:
                rbody = gzip.decompress(rbody)
                rec['body_was_gzip'] = True
                rec['body_after_gunzip'] = len(rbody)
            except Exception as e:
                rec['gunzip_err'] = repr(e)
        # chunked?
        if hdrs.get('transfer-encoding', '').lower() == 'chunked':
            try:
                out = b''
                p = 0
                while p < len(rbody):
                    e = rbody.find(b'\r\n', p)
                    if e < 0: break
                    n = int(rbody[p:e].split(b';')[0], 16)
                    if n == 0: break
                    out += rbody[e+2:e+2+n]
                    p = e+2+n+2
                rbody = out
                rec['body_after_dechunk'] = len(rbody)
            except Exception as e:
                rec['dechunk_err'] = repr(e)
        rec['body_final'] = len(rbody)
        txt = rbody.decode('utf-8', 'replace')
        rec['body_head_text'] = txt[:600]
        try:
            j = json.loads(txt)
            rec['json_ok'] = True
            rec['json_type'] = type(j).__name__
            if isinstance(j, dict):
                rec['json_keys'] = list(j.keys())
                for k in ('protocol', 'Protocol', 'packet', 'Packet'):
                    if k in j:
                        v = j[k]
                        rec['has_%s' % k] = True
                        rec['%s_type' % k] = type(v).__name__
                        if isinstance(v, str):
                            rec['%s_value_head' % k] = v[:80]
                            try:
                                b = base64.b64decode(v + '=' * ((4 - len(v) % 4) % 4))
                                rec['%s_b64_decoded_len' % k] = len(b)
                                rec['%s_b64_first4_hex' % k] = b[:4].hex()
                                rec['%s_b64_first4_uint_le' % k] = int.from_bytes(b[:4], 'little')
                                rec['%s_b64_is_gzip_at4' % k] = b[4:6] == b'\x1f\x8b'
                            except Exception as e:
                                rec['%s_b64_err' % k] = repr(e)
        except Exception as e:
            rec['json_ok'] = False
            rec['json_err'] = repr(e)
    except Exception as e:
        rec['error'] = repr(e)
    rec['elapsed_ms'] = int((time.time() - t0) * 1000)
    open(os.path.join(OUTDIR, 'meta_%d.json' % idx), 'w').write(json.dumps(rec, ensure_ascii=False, indent=2))
    print(json.dumps({k: v for k, v in rec.items() if k not in ('body_head_text',)}, ensure_ascii=False)[:1200])
    print()
    return rec

body = open(BODY_PATH, 'rb').read() if os.path.exists(BODY_PATH) else b''
print('captured client body bytes =', len(body))
idx = 0
for ip in REAL_IPS:
    for mode in ('full', 'headers_only', 'empty'):
        idx += 1
        print('=== #%d  ip=%s  mode=%s ===' % (idx, ip, mode))
        one(ip, mode, body, idx)
print('done. files in', OUTDIR)
