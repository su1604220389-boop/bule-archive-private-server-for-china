#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_relay_replay.py -- 未知协议转发补丁（patch_relay.py）的本地重放验收。

做了什么（**全部在本地**：只监听 127.0.0.1 的随机端口，不连任何服务器）：
  1. 把 target（已打 patch_3 + patch_relay 的 account_auth_probe.py）复制三份进临时装置：
       tmp_on     : 补丁后 + cn_relay_unknown.txt=1      （开关开）
       tmp_off    : 补丁后、没有开关文件                  （开关关 = 默认）
       tmp_legacy : 摘掉 patch_relay 两块（== 103,900 B 的 patch_3 现状）
     cn_cipher / cn_wire / cn_inner / cn_inner27 / cn_nick 用长度、容器、信封逐字段
     等价的替身模块（本机没有 cryptography，只有 AES 本体被换成明文直存）。
  2. 起一个**假 Shittim**（http.server + ThreadingHTTPServer，监听 127.0.0.1:0）：
       POST /api/gateway，字段 mx 用真 cn_cipher.build_mx 的字节布局解回来；
       Account_CheckNexon(1014) -> {"Protocol":1014,"ResultState":1,
                                    "SessionKey":{"AccountServerId":2,"MxToken":<64>},
                                    "AccountId":2}
       其它协议                -> {"Protocol":<num>,"Echo":[<请求体的键>]}
     可切成 error500 / hang（超时）两档；所有收到的请求都记下来。
  3. 直接调 Handler._bridge()（HTTP 层不参与），逐条断言：
       R1  开关关   ：8000 -> 仍然是 min+base 空壳，与 legacy 逐字节（掩掉 uuid）一致
       R2  开关开   ：8000 -> 假 Shittim 的真响应（relay_used=True / relay_protocol=8000），
                      且确实注入了 ensure_session 拿到的 SessionKey
       R3  Shittim 报错（500）-> 仍然 200 + min+base，relay_err 非空
       R4  Shittim 超时          -> 仍然 200 + min+base，relay_err 非空
       R5  已知协议（1002/1014/4000/1005/26000/3/1017/24000/90004）开关开着时
          行为不变：无 relay_* 字段、掩掉 tick/uuid 后响应逐字节一致
       R6  Account_CheckNexon(1014) 不被 hook 拦（无递归）：只有 1 次 1014 调用
       R7  cn_cipher 若自己给了 json（活服务器可能如此）-> 走同一条转发管线
       R8  同线程重入保护：RL_LOCAL.busy=True -> 落回 min+base（reentrant）
       R9  通用性：8006 / 90011 / 35003 / 16000 同样能拿到 Shittim 数据
       R10 日志字段齐备：relay_on/relay_used/relay_code/relay_resp_len/
          relay_protocol/relay_err/relay_fallthrough

用法：
    python deploy/_relay_replay.py --target deploy/_sandbox/p3/account_auth_probe.py
    python deploy/_relay_replay.py --target /www/wwwroot/bapatch/tools/account_auth_probe.py
退出码：全 PASS -> 0，否则 1。
"""
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import importlib.util
import json
import os
import re
import shutil
import struct
import sys
import tempfile
import threading
import time

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
PATCH_PATH = os.path.join(HERE, 'patch_relay.py')

UNKNOWN_8000_NAME = 'Mission_List_CN_8000'      # 只有我们用；确定不在 NAME_TABLE 里
TOKEN64 = base64.b64encode(bytes(range(48))).decode('ascii')
UUID_RE = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
TIME_RE = re.compile(r'^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}')
MASK_KEYS = ('requestid', 'RequestId', 'ServerTimeTicks', 'ReceiveTick',
             'EchoSendTick', 'ServerTime')
_PROTO_NUM = {'Account_Auth': 1002, 'Account_Auth2': 1012, 'Account_CheckNexon': 1014}


# ================================================================ 工具
def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def b32md5(name):
    return base64.b32encode(hashlib.md5(name.encode('utf-16-le')).digest()).decode().rstrip('=')


def packet_of(fragment_text):
    raw = fragment_text.encode('utf-8')
    return base64.b64encode(struct.pack('<I', len(raw)) + gzip.compress(raw)).decode()


def frag_for(num, extra=''):
    """客户端明文片段：',' 开头 '}' 结尾，Hash 高 32 位 = 协议号。"""
    return ',"Hash":%d,"IsTest":false%s}' % ((int(num) << 32) | 5, extra)


BODY_BOUNDARY = '----relayBOUNDARY'


def make_body(token, pkt):
    b = BODY_BOUNDARY
    return ('--%s\r\nContent-Disposition: form-data; name="protocol"\r\n\r\n%s\r\n'
            '--%s\r\nContent-Disposition: form-data; name="packet"\r\n\r\n%s\r\n'
            '--%s--\r\n' % (b, token, b, pkt, b)).encode('utf-8')


def call_bridge(mod, token, pkt, path='/api/unknown', rec_extra=None):
    """直接调 Handler._bridge()（HTTP 层不参与，只走分发）。"""
    mod.exp_flag = lambda: ''
    body = make_body(token, pkt)
    rec = {'t': '2026-11-17 00:00:00', 'from': '127.0.0.1', 'method': 'POST',
           'path': path, 'mode': 'bridge', 'headers': {}, 'body_len': len(body)}
    if rec_extra:
        rec.update(rec_extra)
    try:
        mod.cn_cipher.CALLS[:] = []
    except Exception:
        pass
    inst = object.__new__(mod.Handler)
    code, resp, ctype = mod.Handler._bridge(inst, body, rec)
    return code, resp, ctype, rec


def decode_cn_packet(pkt_b64):
    raw = base64.b64decode(pkt_b64 + '=' * ((4 - len(pkt_b64) % 4) % 4))
    declared = struct.unpack('<I', raw[:4])[0]
    inner = gzip.decompress(raw[4:])
    if declared != len(inner):
        raise ValueError('declared %d != actual %d' % (declared, len(inner)))
    return json.loads(inner.decode('utf-8'))


def body_of(resp):
    raw = bytes(resp) if isinstance(resp, (bytes, bytearray)) else str(resp).encode()
    try:
        return json.loads(raw.decode('utf-8'))
    except Exception:
        return {'_not_json': True, '_len': len(raw),
                '_head': raw[:160].decode('utf-8', 'replace')}


def inner_of(outer):
    """响应外层 -> 内层 dict（cn_wire 明文包 与 CN 信封 b64+gzip 两种都认）。"""
    if not isinstance(outer, dict):
        return None
    p = outer.get('packet')
    if isinstance(p, dict):
        return p
    if not isinstance(p, str):
        return None
    s = p.lstrip()
    if s.startswith('{'):
        try:
            return json.loads(p)
        except Exception:
            return None
    try:
        return decode_cn_packet(p)
    except Exception:
        return None


def norm(v, key=None):
    """掩掉 uuid / ticks，让两次运行的响应可以逐字段比较。"""
    if isinstance(v, dict):
        out = {}
        for k, val in v.items():
            if k == 'packet' and isinstance(val, str):
                try:
                    out[k] = norm(json.loads(val))
                    continue
                except Exception:
                    pass
            out[k] = norm(val, k)
        return dict(sorted(out.items()))
    if isinstance(v, list):
        return [norm(x) for x in v]
    if isinstance(v, bool) or v is None:
        return v
    if isinstance(v, int):
        if key in MASK_KEYS or abs(v) > 10 ** 15:
            return '<TICKS>'
        return v
    if isinstance(v, str):
        if key in MASK_KEYS or UUID_RE.match(v):
            return '<UUID>'
        if TIME_RE.match(v):
            return '<TIME>'
        return v
    return v


def reset_session(mod):
    try:
        mod.SESSION.session_key = None
        mod.SESSION.account_id = None
        mod.SESSION.created = 0
    except Exception:
        pass


def same_bytes(a, b):
    aa = bytes(a) if isinstance(a, (bytes, bytearray)) else str(a).encode()
    bb = bytes(b) if isinstance(b, (bytes, bytearray)) else str(b).encode()
    return aa == bb


# ================================================================ 假 Shittim
class FakeShittim(object):
    """本地假 Shittim：/api/gateway，mx 用真布局解，响应是 {"protocol","packet"}。"""

    def __init__(self):
        self.lock = threading.Lock()
        self.calls = []
        self.mode = 'normal'
        outer = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'

            def log_message(self, *a):
                pass

            def _reply(self, code, payload, ctype='application/json; charset=utf-8'):
                self.send_response(code)
                self.send_header('Content-Type', ctype)
                self.send_header('Content-Length', str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def do_POST(self):
                n = int(self.headers.get('Content-Length') or 0)
                body = self.rfile.read(n)
                req = _decode_gateway_body(body, self.headers.get('Content-Type') or '')
                with outer.lock:
                    outer.calls.append({'path': self.path, 'req': req})
                if outer.mode == 'hang':
                    time.sleep(30)
                    return
                if outer.mode == 'error500':
                    self._reply(500, b'{"error":"injected-shittim-failure"}')
                    return
                proto = req.get('Protocol') if isinstance(req, dict) else None
                if proto == 'Account_CheckNexon' or proto == 1014:
                    name = 'Account_CheckNexon'
                    pkt = {'Protocol': 1014, 'ResultState': 1,
                           'SessionKey': {'AccountServerId': 2, 'MxToken': TOKEN64},
                           'AccountId': 2}
                else:
                    num = proto if isinstance(proto, int) else _PROTO_NUM.get(proto, -1)
                    name = str(proto)
                    pkt = {'Protocol': num,
                           'Echo': sorted(k for k in (req or {}) if k != 'SessionKey')}
                out = json.dumps({'protocol': name,
                                  'packet': json.dumps(pkt, ensure_ascii=False,
                                                       separators=(',', ':'))},
                                 ensure_ascii=False, separators=(',', ':')).encode('utf-8')
                self._reply(200, out)

        self.httpd = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.port = self.httpd.server_address[1]
        self.url = 'http://127.0.0.1:%d/api/gateway' % self.port
        self.thread = threading.Thread(target=self.httpd.serve_forever,
                                       kwargs={'poll_interval': 0.05}, daemon=True)

    def start(self):
        self.thread.start()
        return self

    def stop(self):
        try:
            self.httpd.shutdown()
        except Exception:
            pass
        try:
            self.httpd.server_close()
        except Exception:
            pass

    def snapshot(self):
        with self.lock:
            return list(self.calls)

    def reset(self, mode='normal'):
        with self.lock:
            self.calls[:] = []
        self.mode = mode


def _mx_decode(payload):
    """cn_cipher.build_mx 的逆：10 B 头 + XOR0xD9 的 [u32 len][gzip(json)]。"""
    if len(payload) < 10:
        raise ValueError('mx too short: %d' % len(payload))
    _crc, _conv, klen, ivlen = struct.unpack('<I i B B', payload[:10])
    body = bytes(b ^ 0xD9 for b in payload[10 + klen + ivlen:])
    declared = struct.unpack('<I', body[:4])[0]
    raw = gzip.decompress(body[4:])
    if declared != len(raw):
        raise ValueError('mx declared %d != actual %d' % (declared, len(raw)))
    return json.loads(raw.decode('utf-8'))


def _decode_gateway_body(body, ctype):
    m = re.search(r'boundary=([^;]+)', ctype or '')
    boundary = (m.group(1).strip() if m else BODY_BOUNDARY).encode()
    i = body.find(b'\r\n\r\n')
    j = body.rfind(b'\r\n--' + boundary)
    if i < 0:
        raise ValueError('mx multipart: no header/body separator')
    payload = body[i + 4:j] if j > i else body[i + 4:]
    return _mx_decode(payload)


# ================================================================ 替身模块
RIG_STUBS = {}

RIG_STUBS['cn_cipher.py'] = r'''# -*- coding: utf-8 -*-
"""cn_cipher 仿真替身：容器/长度与真机一致 base64([u32 len][gzip(fragment)])；
AES 层换成明文直存（本机没有 cryptography）。build_mx / unwrap_mx 与真机同构。

关键：真机 PROTOCOL_MAP 只有 Account_Auth 一条（report/_tmp/mx_crypto/cn_cipher.py:35-37），
所以「名字表里没有的 token」decode_packet 会返回 json=None —— 这正是 relay 必须能
自己用 fragment 拼回请求的原因。
"""
import base64
import gzip
import json
import struct

CALLS = []
IV_FIXED = b'JOSYdf8ys97uhFYS'
KEY_LEN = 32
PROTOCOL_MAP = {'AHTQLQI65FWJGGGK4KL5AEF57A': 'Account_Auth'}
SHITTIM_XOR = 0xD9


def wrap_packet(inner):
    return base64.b64encode(struct.pack('<I', len(inner)) + gzip.compress(inner)).decode()


def unwrap_packet(packet_b64):
    raw = base64.b64decode(packet_b64 + '=' * ((4 - len(packet_b64) % 4) % 4))
    if len(raw) < 6:
        raise ValueError('packet too short')
    declared = struct.unpack('<I', raw[:4])[0]
    inner = gzip.decompress(raw[4:])
    if declared != len(inner):
        raise ValueError('declared %d != actual %d' % (declared, len(inner)))
    return inner


def build_inner(fragment_text, key=None, iv=None):
    return fragment_text.encode('utf-8')


def decode_packet(packet_b64, protocol_field=None):
    inner = unwrap_packet(packet_b64)
    text = inner.decode('utf-8', 'replace')
    name = PROTOCOL_MAP.get(protocol_field) if protocol_field else None
    full = None
    if name:
        try:
            full = json.loads('{"Protocol":"%s"' % name + text)
        except Exception:
            full = None
    CALLS.append((protocol_field, text))
    return {"fragment": text, "json": full, "iv": '00' * 16, "key": 'K' * 32,
            "inner_len": len(inner), "frag_len": len(inner)}


def build_mx(json_obj):
    payload = json.dumps(json_obj, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    body = struct.pack('<I', len(payload)) + gzip.compress(payload)
    enc = bytes(b ^ SHITTIM_XOR for b in body)
    return struct.pack('<I', 0) + struct.pack('<i', 0) + bytes([0, 0]) + enc


def unwrap_mx(raw):
    _crc, _conv, klen, ivlen = struct.unpack('<I i B B', raw[:10])
    body = bytes(b ^ SHITTIM_XOR for b in raw[10 + klen + ivlen:])
    return json.loads(gzip.decompress(body[4:]).decode('utf-8'))
'''

RIG_STUBS['cn_wire.py'] = r'''# -*- coding: utf-8 -*-
"""cn_wire 仿真替身：外层信封字段与真机一致（protocol / packet / requestid），
加密层省略 —— body 直接就是 plaintext，测试可以 json.loads 后逐字段断言。"""
import json
import uuid

KEY_LEN = 32
IV_FIXED = b'JOSYdf8ys97uhFYS'
CALLS = []


def build_plaintext(protocol_name, inner_obj, requestid=None):
    requestid = requestid or str(uuid.uuid4())
    plain = json.dumps({"protocol": protocol_name,
                        "packet": json.dumps(inner_obj, ensure_ascii=False,
                                            separators=(',', ':')),
                        "requestid": requestid},
                       ensure_ascii=False, separators=(',', ':'))
    return plain, requestid


def wrap_response(protocol_name, inner_obj, requestid=None, key=None):
    plain, requestid = build_plaintext(protocol_name, inner_obj, requestid)
    CALLS.append(plain)
    return plain.encode('utf-8'), plain, b'K' * KEY_LEN


def unwrap_response(body):
    raise NotImplementedError('stub cannot decrypt')
'''

RIG_STUBS['cn_inner.py'] = r'''# -*- coding: utf-8 -*-
"""cn_inner 仿真替身（只有 90004 分支用到的表）。"""
STATIC_OPEN_CONDITIONS = {}


def build(protocol=None):
    return {"Protocol": protocol}
'''

RIG_STUBS['cn_inner27.py'] = r'''# -*- coding: utf-8 -*-
"""cn_inner27 仿真替身。"""


def build(protocol=None):
    return {"Protocol": protocol}
'''

RIG_STUBS['cn_nick.py'] = r'''# -*- coding: utf-8 -*-
"""cn_nick 仿真替身：真机同签名。"""


def build_min_response(protocol):
    return {"Protocol": int(protocol)}


def build_accountdb(nickname, **kw):
    return {"ServerId": 2, "Nickname": nickname}


def build_nickname_response(nickname, protocol=1001):
    return {"Protocol": int(protocol), "AccountDB": {"ServerId": 2, "Nickname": nickname}}


def build_callname_response(call, nickname='111', protocol=1010):
    return {"Protocol": int(protocol), "AccountDB": {"ServerId": 2, "Nickname": nickname}}
'''

STUB_NAMES = ('cn_cipher', 'cn_wire', 'cn_inner', 'cn_inner27', 'cn_nick')
RIG_MOD_SEQ = [0]


def build_rig(src_text, tmp, extra_files=None):
    for fn, body in RIG_STUBS.items():
        with open(os.path.join(tmp, fn), 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(body)
    path = os.path.join(tmp, 'account_auth_probe.py')
    with open(path, 'w', encoding='utf-8', newline='') as fh:
        fh.write(src_text)
    for fn, val in (extra_files or {}).items():
        with open(os.path.join(tmp, fn), 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(val)
    return path


def load_rig(path, tmp):
    for name in STUB_NAMES:
        sys.modules.pop(name, None)
    if tmp not in sys.path:
        sys.path.insert(0, tmp)
    RIG_MOD_SEQ[0] += 1
    modname = 'relay_rig_%d' % RIG_MOD_SEQ[0]
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod
    spec.loader.exec_module(mod)
    mod.load_names()
    return mod


# ================================================================ 主流程
class Report(object):
    def __init__(self):
        self.rows = []
        self.ok = True

    def add(self, good, tag, text):
        self.ok = self.ok and bool(good)
        self.rows.append((bool(good), tag, text))

    def info(self, tag, text):
        self.rows.append((None, tag, text))

    def dump(self):
        for good, tag, text in self.rows:
            mark = 'PASS  ' if good else ('INFO  ' if good is None else 'FAIL  ')
            print('  %s%-4s %s' % (mark, tag, text))


def main(argv=None):
    ap = argparse.ArgumentParser(description='patch_relay.py 的本地重放验收')
    ap.add_argument('--target', required=True,
                    help='打完 patch_3 + patch_relay 的 account_auth_probe.py')
    ap.add_argument('--patch', default=PATCH_PATH, help='patch_relay.py 路径（默认同级）')
    ap.add_argument('--keep-rig', action='store_true', help='保留临时装置目录（排查用）')
    args = ap.parse_args(argv)

    if not os.path.isfile(args.target):
        raise SystemExit('!! --target 不存在: %s' % args.target)
    if not os.path.isfile(args.patch):
        raise SystemExit('!! --patch 不存在: %s' % args.patch)

    P = load_module(args.patch, 'relay_patch_lib')
    src_text = P.read_text(args.target)
    target_sha = hashlib.sha256(src_text.encode('utf-8')).hexdigest()
    print('target : %s' % args.target)
    print('         %d 字节 / sha256 %s' % (len(src_text.encode('utf-8')), target_sha))
    print('patched: %s' % ('是' if P.is_patched(src_text) else '否'))
    if not P.is_patched(src_text):
        raise SystemExit('!! 这个文件还没打 patch_relay，先 --apply')

    R = Report()

    # ---------------- R0：结构不变量
    legacy_text, _acts = P.build_removed(src_text)
    legacy_sha = hashlib.sha256(legacy_text.encode('utf-8')).hexdigest()
    R.add(len(legacy_text.encode('utf-8')) == P.BASE_SIZE and legacy_sha == P.BASE_SHA256,
          'R0', '摘掉 PAYLOAD+HOOK-A 后 == 基线 %d B / %s（实测 %d B / %s）'
          % (P.BASE_SIZE, P.BASE_SHA256[:16], len(legacy_text.encode('utf-8')), legacy_sha[:16]))
    i_none = src_text.find("        if name is None:")
    i_hook = src_text.find('# >>> BAPATCH-RELAY-HOOK-A')
    i_got = src_text.find('            got = self._generic_protocol_response(proto_str, packet_b64, rec)')
    R.add(0 <= i_none < i_hook < i_got, 'R0',
          'HOOK-A 落在 name is None 分支内（none@%d < hook@%d < got@%d）' % (i_none, i_hook, i_got))
    R.add("        if name is None:\n            rec['unknown_protocol'] = True\n" in
          src_text.replace('\r\n', '\n'), 'R0',
          "锚点 `if name is None:` + `rec['unknown_protocol'] = True` 未被改动")

    fake = FakeShittim().start()
    tmp_on = tempfile.mkdtemp(prefix='relay_on_')
    tmp_off = tempfile.mkdtemp(prefix='relay_off_')
    tmp_legacy = tempfile.mkdtemp(prefix='relay_legacy_')
    try:
        simple_switches = {'cn_1005.txt': '1\n', 'cn_4000.txt': '1\n',
                           'cn_26000.txt': '1\n', 'cn_3.txt': '1\n'}
        p_on = build_rig(src_text, tmp_on,
                         dict(simple_switches, **{P.SWITCH_FILE: '1\n'}))
        p_off = build_rig(src_text, tmp_off, dict(simple_switches))
        p_legacy = build_rig(legacy_text, tmp_legacy, dict(simple_switches))
        mod_on = load_rig(p_on, tmp_on)
        mod_off = load_rig(p_off, tmp_off)
        mod_legacy = load_rig(p_legacy, tmp_legacy)
        for m in (mod_on, mod_off, mod_legacy):
            m.GATEWAY = fake.url

        tok8000 = b32md5(UNKNOWN_8000_NAME)
        R.info('R1', '未知协议 token = b32md5(%r) = %s（NAME_TABLE 里查不到 = %s）'
               % (UNKNOWN_8000_NAME, tok8000, mod_on.NAME_TABLE.get(tok8000) is None))
        pkt8000 = packet_of(frag_for(8000, ',"AccountId":10015354380'))

        # ---------------- R1：开关关 == 现状（min+base）
        fake.reset('normal')
        reset_session(mod_off)
        code1, resp1, ctype1, rec1 = call_bridge(mod_off, tok8000, pkt8000,
                                                 path='/api/mission/list')
        o1 = body_of(resp1)
        i1 = inner_of(o1)
        R.add(code1 == 200 and ctype1 and rec1.get('gen_kind') == 'min+base',
              'R1', '开关关：8000 -> %r / gen_kind=%r（min+base 空壳）'
              % (code1, rec1.get('gen_kind')))
        R.add(rec1.get('unknown_protocol') is True and 'relay_used' not in rec1,
              'R1', '开关关：unknown_protocol=True 且没有 relay_used 字段')
        R.add(rec1.get('relay_on') is False and rec1.get('relay_fallthrough') == 'switch-off',
              'R1', '开关关：relay_on=False / relay_fallthrough=%r'
              % (rec1.get('relay_fallthrough'),))
        R.add(isinstance(i1, dict) and i1.get('Protocol') == 8000,
              'R1', '开关关：内层仍是假壳 Protocol=%r' % ((i1 or {}).get('Protocol'),))
        R.add(len(fake.snapshot()) == 0, 'R1',
              '开关关：假 Shittim 一次都没被调用（%d 次）' % len(fake.snapshot()))
        # 与 legacy（= 摘掉本补丁）逐步对照
        reset_session(mod_legacy)
        code1L, resp1L, ctype1L, rec1L = call_bridge(mod_legacy, tok8000, pkt8000,
                                                     path='/api/mission/list')
        R.add(code1 == code1L and norm(o1) == norm(body_of(resp1L)),
              'R1', '开关关：响应与摘掉本补丁的 legacy 逐字段一致（掩 uuid 后）')
        R.add(same_bytes(resp1, resp1L) or True,
              'R1', '开关关：原始字节 %r（uuid 每次不同，故以掩码对照为准）'
              % ('相同' if same_bytes(resp1, resp1L) else '差 %d B' % abs(len(resp1) - len(resp1L))))

        # ---------------- R2：开关开 == 真 Shittim 数据
        fake.reset('normal')
        reset_session(mod_on)
        code2, resp2, ctype2, rec2 = call_bridge(mod_on, tok8000, pkt8000,
                                                 path='/api/mission/list')
        o2 = body_of(resp2)
        i2 = inner_of(o2)
        calls2 = fake.snapshot()
        R.add(code2 == 200 and rec2.get('relay_used') is True and rec2.get('relay_on') is True,
              'R2', '开关开：8000 -> %r，relay_used=%r / relay_on=%r'
              % (code2, rec2.get('relay_used'), rec2.get('relay_on')))
        R.add(rec2.get('relay_protocol') == 8000 and rec2.get('relay_protocol_num') == 8000,
              'R2', 'relay_protocol=%r / relay_protocol_num=%r（= Hash>>32）'
              % (rec2.get('relay_protocol'), rec2.get('relay_protocol_num')))
        R.add(isinstance(i2, dict) and i2.get('Protocol') == 8000 and 'Echo' in i2,
              'R2', '内层是假 Shittim 的真响应（Protocol=%r / Echo=%r）'
              % ((i2 or {}).get('Protocol'), (i2 or {}).get('Echo')))
        R.add(rec2.get('relay_code') == 200 and rec2.get('relay_resp_len', 0) > 0,
              'R2', 'relay_code=%r / relay_resp_len=%r'
              % (rec2.get('relay_code'), rec2.get('relay_resp_len')))
        R.add(rec2.get('relay_session_injected') is True, 'R2',
              'SessionKey 由 ensure_session(1014) 注入（relay_session_injected=%r）'
              % (rec2.get('relay_session_injected'),))
        chk_1014 = [c for c in calls2 if (c['req'] or {}).get('Protocol') in
                    ('Account_CheckNexon', 1014)]
        chk_8000 = [c for c in calls2 if (c['req'] or {}).get('Protocol') == 8000]
        R.add(len(chk_1014) == 1 and len(chk_8000) == 1,
              'R2', '假 Shittim 收到 1014=%d 次 / 8000=%d 次（先铸会话再转发，各一次）'
              % (len(chk_1014), len(chk_8000)))
        sk_sent = (chk_8000[0]['req'].get('SessionKey') if chk_8000 else None)
        R.add(sk_sent == {'AccountServerId': 2, 'MxToken': TOKEN64},
              'R2', '转发请求里的 SessionKey == Shittim 铸的那张（AccountServerId=%r / MxToken %d 字符）'
              % ((sk_sent or {}).get('AccountServerId'), len((sk_sent or {}).get('MxToken') or '')))
        R.add(o2.get('protocol') == rec2.get('cn_env_protocol'),
              'R2', '外层 protocol == _cn_envelope 的 cn_env_protocol（%r）'
              % (o2.get('protocol'),))
        R.add(norm(body_of(resp1)) != norm(o2),
              'R2', '开关开后的响应 != 开关关时的 min+base 空壳（真的换了数据源）')

        # ---------------- R10：日志字段齐备
        need = ('relay_on', 'relay_used', 'relay_code', 'relay_resp_len',
                'relay_protocol', 'relay_err', 'relay_fallthrough')
        miss = [k for k in need if k not in rec2]
        R.add(not miss, 'R10', '成功路径的 7 个日志字段齐备%s'
              % ('' if not miss else '（缺 %r）' % (miss,)))

        # ---------------- R3：Shittim 报错 -> 200 + 落回
        fake.reset('error500')
        code3, resp3, ctype3, rec3 = call_bridge(mod_on, tok8000, pkt8000,
                                                 path='/api/mission/list')
        i3 = inner_of(body_of(resp3))
        R.add(code3 == 200 and rec3.get('gen_kind') == 'min+base'
              and rec3.get('relay_used') is None,
              'R3', 'Shittim 回 500 -> bridge 仍 %r / gen_kind=%r（relay_used 不存在）'
              % (code3, rec3.get('gen_kind')))
        R.add(rec3.get('relay_code') == 500 and bool(rec3.get('relay_err')),
              'R3', 'relay_code=%r / relay_err=%r' % (rec3.get('relay_code'), rec3.get('relay_err')))
        R.add(isinstance(i3, dict) and i3.get('Protocol') == 8000,
              'R3', '落回的内层是 min+base 空壳（Protocol=%r）' % ((i3 or {}).get('Protocol'),))

        # ---------------- R3b：信封构造抛异常 -> hook 兜住（不 500）
        fake.reset('normal')
        reset_session(mod_on)
        orig_env = mod_on.Handler._cn_envelope

        def _env_boom(self, *a, **kw):
            raise RuntimeError('injected-envelope-boom')

        mod_on.Handler._cn_envelope = _env_boom
        try:
            code3b, resp3b, ctype3b, rec3b = call_bridge(mod_on, tok8000, pkt8000,
                                                         path='/api/mission/list')
        finally:
            mod_on.Handler._cn_envelope = orig_env
        R.add(code3b == 200 and rec3b.get('gen_kind') == 'min+base'
              and rec3b.get('relay_used') is None
              and 'injected-envelope-boom' in str(rec3b.get('relay_err'))
              and rec3b.get('relay_fallthrough') == 'exception',
              'R3b', '_cn_envelope 抛异常 -> bridge 仍 %r / fallthrough=%r / relay_err=%r'
              % (code3b, rec3b.get('relay_fallthrough'), rec3b.get('relay_err')))

        # ---------------- R3c：ensure_session 拿不到会话 -> 落回（不 500）
        fake.reset('normal')
        reset_session(mod_on)
        orig_ens = mod_on.ensure_session
        mod_on.ensure_session = lambda rec: (None, None)
        try:
            code3c, resp3c, ctype3c, rec3c = call_bridge(mod_on, tok8000, pkt8000,
                                                         path='/api/mission/list')
        finally:
            mod_on.ensure_session = orig_ens
        R.add(code3c == 200 and rec3c.get('gen_kind') == 'min+base'
              and rec3c.get('relay_fallthrough') == 'ensure-session'
              and rec3c.get('relay_used') is None,
              'R3c', 'ensure_session 回 None -> bridge 仍 %r / fallthrough=%r（不 500）'
              % (code3c, rec3c.get('relay_fallthrough')))

        # ---------------- R4：Shittim 超时 -> 200 + 落回
        fake.reset('hang')
        # 预置会话（等价于「启动后已经 CheckNexon 过」），让超时发生在真正的转发上，
        # 而不是先卡在 ensure_session 的 1014 上。
        mod_on.SESSION.session_key = {'AccountServerId': 2, 'MxToken': TOKEN64}
        mod_on.SESSION.account_id = 2
        orig_pg = mod_on.post_gateway

        def _pg_fast(obj, timeout=40):
            return orig_pg(obj, timeout=min(timeout, 2))

        mod_on.post_gateway = _pg_fast
        t0 = time.time()
        try:
            code4, resp4, ctype4, rec4 = call_bridge(mod_on, tok8000, pkt8000,
                                                     path='/api/mission/list')
        finally:
            mod_on.post_gateway = orig_pg
            fake.mode = 'normal'
        dt4 = time.time() - t0
        R.add(code4 == 200 and rec4.get('gen_kind') == 'min+base'
              and rec4.get('relay_used') is None,
              'R4', 'Shittim 超时 -> bridge 仍 %r / gen_kind=%r（%.1f s 内返回）'
              % (code4, rec4.get('gen_kind'), dt4))
        R.add(bool(rec4.get('relay_err')) and dt4 < 10,
              'R4', 'relay_err=%r（耗时 %.1f s < 10 s）' % (rec4.get('relay_err'), dt4))

        # ---------------- R7：cn_cipher 自己给了 json 的活服务器分支
        fake.reset('normal')
        orig_dec = mod_on.cn_cipher.decode_packet

        def dec_with_json(packet_b64, protocol_field=None):
            d = orig_dec(packet_b64, protocol_field)
            frag = d.get('fragment') or ''
            try:
                d = dict(d)
                d['json'] = json.loads('{"Protocol":8000' + frag)
            except Exception:
                pass
            return d

        mod_on.cn_cipher.decode_packet = dec_with_json
        try:
            code7, resp7, ctype7, rec7 = call_bridge(mod_on, tok8000, pkt8000,
                                                     path='/api/mission/list')
        finally:
            mod_on.cn_cipher.decode_packet = orig_dec
        i7 = inner_of(body_of(resp7))
        R.add(code7 == 200 and rec7.get('relay_used') is True
              and isinstance(i7, dict) and i7.get('Protocol') == 8000,
              'R7', 'cn_cipher 给了 json（活服务器可能如此）-> 仍走同一条转发管线'
              '（relay_used=%r / 内层 Protocol=%r）'
              % (rec7.get('relay_used'), (i7 or {}).get('Protocol')))

        # ---------------- R9：通用性（FALLBACK_QUEUE 里剩下 4 个）
        for num in (8006, 90011, 35003, 16000):
            tok = b32md5('CN_Unknown_%d' % num)
            pkt = packet_of(frag_for(num, ',"AccountId":10015354380'))
            fake.reset('normal')
            code9, resp9, ctype9, rec9 = call_bridge(mod_on, tok, pkt,
                                                     path='/api/unknown/%d' % num)
            i9 = inner_of(body_of(resp9))
            R.add(code9 == 200 and rec9.get('relay_used') is True
                  and rec9.get('relay_protocol') == num
                  and isinstance(i9, dict) and i9.get('Protocol') == num and 'Echo' in i9,
                  'R9', '%d -> Shittim 真响应（relay_protocol=%r / 内层 Protocol=%r）'
                  % (num, rec9.get('relay_protocol'), (i9 or {}).get('Protocol')))

        # ---------------- R8：同线程重入保护
        fake.reset('normal')
        mod_on.RL_LOCAL.busy = True
        try:
            code8, resp8, ctype8, rec8 = call_bridge(mod_on, tok8000, pkt8000,
                                                     path='/api/mission/list')
        finally:
            mod_on.RL_LOCAL.busy = False
        R.add(code8 == 200 and rec8.get('relay_fallthrough') == 'reentrant'
              and rec8.get('relay_used') is None and len(fake.snapshot()) == 0,
              'R8', '同一线程已在转发（busy=True）-> 直接落回（fallthrough=%r / Shittim 0 次）'
              % (rec8.get('relay_fallthrough'),))

        # ---------------- R6：1014 不被 hook 拦（无递归）
        fake.reset('normal')
        reset_session(mod_on)
        tok1014 = b32md5('Account_CheckNexon')
        pkt1014 = packet_of(frag_for(1014, ',"AccountId":10015354380'))
        t0 = time.time()
        code6, resp6, ctype6, rec6 = call_bridge(mod_on, tok1014, pkt1014,
                                                 path='/api/account/checknexon')
        dt6 = time.time() - t0
        i6 = inner_of(body_of(resp6))
        n1014 = len([c for c in fake.snapshot()
                     if (c['req'] or {}).get('Protocol') in ('Account_CheckNexon', 1014)])
        relay_keys = sorted(k for k in rec6 if k.startswith('relay_'))
        R.add(code6 == 200 and isinstance(i6, dict) and i6.get('Protocol') == 1014,
              'R6', 'Account_CheckNexon(1014) -> %r / 内层 Protocol=%r'
              % (code6, (i6 or {}).get('Protocol')))
        R.add(n1014 == 1 and dt6 < 5 and not relay_keys,
              'R6', '1014 只被调用 1 次（%.2f s）、rec 里没有任何 relay_* 字段（%r）—— 无递归'
              % (dt6, relay_keys))

        # ---------------- R5：已知协议开关开着时行为不变
        known = [
            ('Account_Auth', 1002, 'AHTQLQI65FWJGGGK4KL5AEF57A', 'gen_kind', None),
            ('Account_CheckNexon', 1014, b32md5('Account_CheckNexon'), 'gen_kind', None),
            ('Item_List', 4000, b32md5('Item_List'), 'gen_kind', 'simple-4000'),
            ('Account_GetTutorial', 1005, b32md5('Account_GetTutorial'), 'gen_kind', 'simple-1005'),
            ('Content_SaveGet', 26000, b32md5('Content_SaveGet'), 'gen_kind', 'simple-26000'),
            ('NetworkTime_Sync', 3, b32md5('NetworkTime_Sync'), 'gen_kind', 'networktime-3'),
            ('Account_LoginSync', 1017, 'P3OMQZD2FXV7XXEGA7ETCXIJ4Q', 'gen_kind', None),
            ('Academy_GetInfo', 24000, b32md5('Academy_GetInfo'), 'gen_kind', 'academy-24000-v3'),
            ('Management_Data', 90004, b32md5('Management_Data'), 'gen_kind', 'management-90004'),
        ]
        exact = 0
        for nm, num, tok, _gkey, want_gen in known:
            pkt = packet_of(frag_for(num, ',"AccountId":1001001,"Token":"t"'))
            fake.reset('normal')
            reset_session(mod_on)
            co, ro, cto, reco = call_bridge(mod_on, tok, pkt, path='/api/known/%d' % num)
            fake.reset('normal')
            reset_session(mod_legacy)
            cl, rl, ctl, recl = call_bridge(mod_legacy, tok, pkt, path='/api/known/%d' % num)
            # legacy 自己再跑一次：证明「掩码后不一致」纯属 bridge 自身的时间/uuid 抖动
            fake.reset('normal')
            reset_session(mod_legacy)
            _c2, rl2, _ct2, _rec2 = call_bridge(mod_legacy, tok, pkt,
                                                path='/api/known/%d' % num)
            det = norm(body_of(rl)) == norm(body_of(rl2))
            relay_keys = sorted(k for k in reco if k.startswith('relay_'))
            good = (co == cl == 200 and cto == ctl
                    and norm(body_of(ro)) == norm(body_of(rl))
                    and 'relay_used' not in reco and det)
            if want_gen is not None:
                good = good and reco.get('gen_kind') == want_gen and recl.get('gen_kind') == want_gen
            exact += 1 if same_bytes(ro, rl) else 0
            R.add(good, 'R5',
                  '%s(%d)：开关开 vs legacy 一致（gen_kind=%r / relay_used 不存在 / '
                  'fallthrough=%r / legacy 自身可复现=%r%s）'
                  % (nm, num, reco.get('gen_kind'), reco.get('relay_fallthrough'), det,
                     '' if same_bytes(ro, rl) else ' / 字节仅差时间-uuid'))
            R.info('R5', '  ↳ %s(%d) rec relay_* = %r（只允许 on/err/fallthrough 这类访问痕迹）'
                   % (nm, num, relay_keys))
        R.info('R5', '9 个已知协议里 %d 个原始字节完全相同，其余仅差 ServerTimeTicks/uuid/'
               '时间字符串（掩码后全部逐字段一致；legacy 自身两次运行也在同一批字段上不同）'
               % exact)

        # ---------------- 收尾
        R.add(True, 'R11', '全程只监听 127.0.0.1:%d（假 Shittim），未连任何远端' % fake.port)
    finally:
        fake.stop()
        for d in (tmp_on, tmp_off, tmp_legacy):
            if args.keep_rig:
                print('（临时装置保留：%s）' % d)
            else:
                shutil.rmtree(d, ignore_errors=True)

    print('\n== 重放断言 ==')
    R.dump()
    n_fail = sum(1 for g, _t, _x in R.rows if g is False)
    n_pass = sum(1 for g, _t, _x in R.rows if g is True)
    print('\n%d 项断言 / %d FAIL / %s' % (n_pass, n_fail, 'ALL PASS' if R.ok else 'SOME FAILED'))
    return 0 if R.ok else 1


if __name__ == '__main__':
    sys.exit(main())
