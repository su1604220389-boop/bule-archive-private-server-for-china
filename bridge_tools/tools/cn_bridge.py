#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cn_bridge.py —— 国服信封(protocol/encode/packet) -> Shittim .mx 的桥（骨架）

职责：
  接收 POST /api/account/auth（multipart: protocol / encode / packet）
  → unwrap_outer(packet)   外层容器：[u32 LE 明文长度][gzip(净载荷)]   ← 已完全掌握
  → to_json(净载荷)        净载荷 -> JSON                            ← 唯一未实现的一块
  → build_mx(json)         按 Shittim 格式重封装                      ← 已完全掌握
  → 转发 http://127.0.0.1:5000/api/gateway
  → 把 Shittim 的响应原样回给客户端

用法：
  python3 cn_bridge.py            # 起服务（127.0.0.1:9096）
  python3 cn_bridge.py --selftest # 用真实 HTTP 走一遍完整链路（to_json 用桩）
"""
import sys, os, io, gzip, json, struct, base64, http.server, socketserver
import urllib.request, urllib.error, time

LISTEN = ('127.0.0.1', 9096)
TARGET = 'http://127.0.0.1:5000/api/gateway'
LOG    = '/www/wwwroot/bapatch/logs/cn_bridge.log'

XOR_KEY = 0xD9   # Shittim RequestXorKey

# --------------------------------------------------------------------------
# 1) 外层容器（已掌握）：packet = base64( [u32 LE 明文长度][gzip(净载荷)] )
# --------------------------------------------------------------------------
def unwrap_outer(packet_b64: str) -> bytes:
    raw = base64.b64decode(packet_b64)
    if len(raw) < 4:
        raise ValueError('packet too short: %d' % len(raw))
    declared = struct.unpack('<I', raw[:4])[0]
    body = gzip.decompress(raw[4:])
    if len(body) != declared:
        raise ValueError('length mismatch: declared=%d actual=%d' % (declared, len(body)))
    return body

# --------------------------------------------------------------------------
# 2) 净载荷 -> JSON（★ 唯一未实现：等混淆/序列化格式确定后填这一个函数）
# --------------------------------------------------------------------------
def to_json(raw_payload: bytes) -> dict:
    """
    已观测事实（432 字节样本）：
      - 首 4 字节 29 4e d0 c9  -> 不是合法 flatbuffers root offset
      - 末尾 36 字符是明文 base64: MjRlMmQ1MmNiZDg0Mzc2MjBjZTgwOTI3
        -> base64("24e2d52cbd8437620ce80927")，一直延伸到最后一个字节
      - 与 0xD9 单字节 XOR 后不是 '{'，故非 Shittim 那套纯 XOR+gzip JSON
    待定：是 flatbuffers / protobuf / 自定义结构，还是固定密钥加密。
    """
    raise NotImplementedError(
        'to_json not implemented yet (raw=%d bytes, head=%s)' % (len(raw_payload), raw_payload[:8].hex())
    )

# --------------------------------------------------------------------------
# 3) Shittim .mx 重封装（已掌握并实测通过）
#    [crc u32][typeConversion i32][keyLen u8][ivLen u8][ XOR(0xD9)( [u32 明文长度][gzip(JSON)] ) ]
# --------------------------------------------------------------------------
def build_mx(json_obj_or_bytes, crc=0, type_conversion=0, key=b'', iv=b'') -> bytes:
    if isinstance(json_obj_or_bytes, (dict, list)):
        payload = json.dumps(json_obj_or_bytes, ensure_ascii=False, separators=(',', ':')).encode()
    else:
        payload = json_obj_or_bytes
    gz  = gzip.compress(payload)
    raw = struct.pack('<I', len(payload)) + gz
    enc = bytes(b ^ XOR_KEY for b in raw)
    return struct.pack('<I', crc) + struct.pack('<i', type_conversion) + bytes([len(key), len(iv)]) + key + iv + enc

# --------------------------------------------------------------------------
# 4) 转发到 Shittim，multipart 字段名必须是 mx（实测：字段名不对就 400 "Expecting an mx file"）
# --------------------------------------------------------------------------
def post_mx(mx_bytes: bytes, timeout=30):
    boundary = '----cnbridge%d' % int(time.time() * 1000)
    body = []
    body.append(('--%s\r\n' % boundary).encode())
    body.append(b'Content-Disposition: form-data; name="mx"; filename="packet.mx"\r\n')
    body.append(b'Content-Type: application/octet-stream\r\n\r\n')
    body.append(mx_bytes)
    body.append(('\r\n--%s--\r\n' % boundary).encode())
    data = b''.join(body)
    req = urllib.request.Request(TARGET, data=data, method='POST')
    req.add_header('Content-Type', 'multipart/form-data; boundary=%s' % boundary)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()

# --------------------------------------------------------------------------
# 5) multipart 解析（只取 protocol / encode / packet 三个文本字段）
# --------------------------------------------------------------------------
def parse_cn_multipart(raw: bytes):
    out = {}
    for name in ('protocol', 'encode', 'packet'):
        key = ('name="%s"' % name).encode()
        i = raw.find(key)
        if i < 0:
            continue
        j = raw.find(b'\r\n\r\n', i)
        if j < 0:
            continue
        k = raw.find(b'\r\n--', j + 4)
        if k < 0:
            continue
        out[name] = raw[j + 4:k].decode('latin1').strip()
    return out

# --------------------------------------------------------------------------
def log(obj):
    try:
        with open(LOG, 'a') as f:
            f.write(json.dumps(obj, ensure_ascii=False) + '\n')
    except Exception:
        pass

class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def do_POST(self):
        n = int(self.headers.get('Content-Length') or 0)
        raw = self.rfile.read(n) if n else b''
        rec = {'t': time.strftime('%Y-%m-%d %H:%M:%S'), 'path': self.path,
               'method': 'POST', 'body_len': len(raw), 'stage': 'start'}
        try:
            fields = parse_cn_multipart(raw)
            rec['protocol'] = fields.get('protocol')
            rec['encode'] = fields.get('encode')
            rec['packet_len'] = len(fields.get('packet') or '')
            payload = unwrap_outer(fields['packet'])
            rec['stage'] = 'outer-unwrapped'
            rec['payload_len'] = len(payload)
            rec['payload_head'] = payload[:32].hex()
            rec['payload_tail'] = payload[-32:].hex()
            obj = to_json(payload)                 # ← 唯一未实现
            rec['stage'] = 'json-built'
            mx = build_mx(obj)
            rec['mx_len'] = len(mx)
            code, resp = post_mx(mx)
            rec['stage'] = 'forwarded'
            rec['fwd_code'] = code
            rec['fwd_resp_printable'] = ''.join(chr(c) if 32 <= c < 127 else '.' for c in resp[:512])
        except NotImplementedError as e:
            rec['stage'] = 'to_json-TODO'
            rec['err'] = str(e)
            code, resp = 501, json.dumps({'error': 'to_json not implemented', 'detail': str(e)}).encode()
        except Exception as e:
            rec['stage'] = 'error'
            rec['err'] = repr(e)
            code, resp = 502, json.dumps({'error': repr(e)}).encode()
        log(rec)
        try:
            self.send_response(code)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(resp)))
            self.end_headers()
            self.wfile.write(resp)
        except Exception:
            pass

    def do_GET(self):
        body = b'{"ok":true}'
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass

# --------------------------------------------------------------------------
def selftest():
    print('== build_mx smoke ==')
    for obj in ({"Protocol": 0}, {"Protocol": "NetworkTime_Sync"},
                {"Protocol": "Account_Auth", "YostarUID": 314816420}):
        mx = build_mx(obj)
        print('  %-46s -> mx=%3d B' % (json.dumps(obj, ensure_ascii=False)[:46], len(mx)))
    print('== forward each to Shittim ==')
    for obj in ({"Protocol": 0}, {"Protocol": "NetworkTime_Sync"},
                {"Protocol": "Account_Auth", "YostarUID": 314816420,
                 "YostarToken": "61de1d1b7519ab1231866f74c11fcfdd1f80b210"}):
        code, resp = post_mx(build_mx(obj))
        print('  %-40s -> %s %s' % (json.dumps(obj, ensure_ascii=False)[:40], code, resp[:160].decode('latin1')))

    print('== full bridge path with a stubbed to_json (real HTTP, real Shittim) ==')
    global to_json
    to_json = lambda raw: {"Protocol": "Account_Auth", "YostarUID": 314816420,
                           "YostarToken": "61de1d1b7519ab1231866f74c11fcfdd1f80b210"}
    # 造一个国服形状的请求：packet = base64([u32 len][gzip(随便什么)])
    payload = b'\x00' * 432
    pkt = struct.pack('<I', len(payload)) + gzip.compress(payload)
    pkt_b64 = base64.b64encode(pkt).decode()
    boundary = 'X'
    body = ('--X\r\nContent-Disposition: form-data; name="protocol"\r\n\r\nAHTQLQI65FWJGGGK4KL5AEF57A\r\n'
            '--X\r\nContent-Disposition: form-data; name="encode"\r\n\r\nTrue\r\n'
            '--X\r\nContent-Disposition: form-data; name="packet"\r\n\r\n%s\r\n--X--\r\n' % pkt_b64).encode()
    import threading
    t = threading.Thread(target=lambda: socketserver.ThreadingTCPServer(
        LISTEN, Handler, bind_and_activate=True).serve_forever(), daemon=True)
    t.start()
    time.sleep(0.5)
    req = urllib.request.Request('http://127.0.0.1:9096/api/account/auth', data=body, method='POST')
    req.add_header('Content-Type', 'multipart/form-data; boundary=X')
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            print('  bridge -> %s %s' % (r.status, r.read()[:300].decode('latin1')))
    except urllib.error.HTTPError as e:
        print('  bridge -> %s %s' % (e.code, e.read()[:300].decode('latin1')))
    print('  (see /www/wwwroot/bapatch/logs/cn_bridge.log)')

if __name__ == '__main__':
    if '--selftest' in sys.argv:
        selftest()
    else:
        socketserver.ThreadingTCPServer.allow_reuse_address = True
        with socketserver.ThreadingTCPServer(LISTEN, Handler) as s:
            print('cn_bridge listening on %s:%d -> %s' % (LISTEN[0], LISTEN[1], TARGET))
            s.serve_forever()
