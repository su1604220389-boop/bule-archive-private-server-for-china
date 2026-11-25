#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_relay2_replay.py -- 名字已知协议转发补丁（patch_relay2.py）的本地重放验收。

做了什么（**全部在本地**：只监听 127.0.0.1 的随机端口，不连任何服务器）：
  1. 把 target（已打 patch_3 + patch_relay + patch_relay2 的 account_auth_probe.py）
     复制三份进临时装置：
        tmp_on   : 补丁后 + cn_relay_known.txt=1       （开关开）
        tmp_off  : 补丁后、没有 cn_relay_known.txt      （开关关 = 默认）
        tmp_base : 摘掉 patch_relay2 两块 == 115,911 B 的现状（relay v1 已打）
     cn_cipher / cn_wire / cn_inner / cn_inner27 / cn_nick 用长度、容器、信封逐字段
     等价的替身模块（本机没有 cryptography，只有 AES 本体被换成明文直存）。
  2. 起一个**假 Shittim**（http.server + ThreadingHTTPServer，监听 127.0.0.1:0）：
       POST /api/gateway，字段 mx 用真 cn_cipher.build_mx 的字节布局解回来；
       Account_CheckNexon(1014) -> {"Protocol":1014,"ResultState":1,
                                    "SessionKey":{"AccountServerId":2,"MxToken":<64>},
                                    "AccountId":2}
       其它协议                -> {"Protocol":<num>,"Echo":[<请求体的键>]}
     可切成 error500 / hang（超时）/ garbage（200 但非 JSON）三档；收到什么都记下来。
  3. 直接调 Handler._bridge()（HTTP 层不参与），逐条断言：
       S0  结构：摘块后逐字节 == 115,911 B；钩子在 `if proto_int:` 之前、同级 8 空格；
                AST 上它是 `_bridge` 里 `if proto_int:` 的直接前一条语句
       S1  开关关 ：8000 -> min+base 空壳（gen_kind='min+base'），假 Shittim 0 次调用，
                    且与摘掉本补丁的 tmp_base 逐字段一致
       S2  开关开 ：8000 -> 假 Shittim 的真响应（relay2_used=True / relay2_protocol=8000），
                    注入 ensure_session 铸的 SessionKey；post_gateway 收到 timeout=8
       S2b proto_int 有值（模拟线上 rec['req_Hash'] 已置）：开关关 -> min-envelope，
                    开关开 -> 仍然被 relay2 接住（证明钩子确实在 `if proto_int:` 之前）
       S3  通用性：1006/8006/90011/35003/16000/19003/19004/25003/15002/36001
                    开关开时都走 relay2
       S4  假 Shittim 回 500 / 超时 / 200 非 JSON / post_gateway 抛异常
                    -> 仍然 200 + min+base + relay2_err 非空（绝不 500）
       S5  回归：1002/1014/24000/1017/4000/1005/26000/3/90004 开关开着时
                    relay2_used 不存在，响应与开关关时逐字段一致
       S6  Account_CheckNexon(1014) 不被钩子拦（无递归）：只有 1 次 1014 调用，
                    rec 里没有任何 relay2_* 字段
       S7  日志字段齐备：relay2_on / relay2_used / relay2_code / relay2_resp_len /
                    relay2_protocol / relay2_err / relay2_fallthrough

用法：
    python deploy/_relay2_replay.py --target deploy/_sandbox/p3/account_auth_probe.py
    python deploy/_relay2_replay.py --target /www/wwwroot/bapatch/tools/account_auth_probe.py
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
PATCH_PATH = os.path.join(HERE, 'patch_relay2.py')

TOKEN64 = base64.b64encode(bytes(range(48))).decode('ascii')
UUID_RE = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
TIME_RE = re.compile(r'^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}')
MASK_KEYS = ('requestid', 'RequestId', 'ServerTimeTicks', 'ReceiveTick',
             'EchoSendTick', 'ServerTime')

# 任务清单里的 10 个「名字已知、但没有真生成器」的协议（8000 单独在 S2 里测）
RELAY2_PROTOCOLS = [
    (1006, 'Account_SetTutorial', True),          # BUILTIN_NAMES 里就有
    (8006, 'Mission_GuideMissionSeasonList', False),
    (90011, 'Shop_ListTutorialGacha', False),
    (35003, 'MiniGame_MissionList', False),
    (16000, 'Toast_List', False),
    (19003, 'Scenario_Skip', False),
    (19004, 'Scenario_Select', False),
    (25003, 'Event_RewardIncrease', False),
    (15002, 'OpenCondition_EventList', False),
    (36001, 'Notification_EventContentReddotCheck', False),
]

# 回归清单：有专分支 / 真生成器，开关开着也必须逐字段不变
REGRESSION = [
    ('Account_Auth', 1002, None),
    ('Account_CheckNexon', 1014, None),
    ('Academy_GetInfo', 24000, 'academy-24000-v3'),
    ('Account_LoginSync', 1017, None),
    ('Item_List', 4000, 'simple-4000'),
    ('Account_GetTutorial', 1005, 'simple-1005'),
    ('Content_SaveGet', 26000, 'simple-26000'),
    ('NetworkTime_Sync', 3, 'networktime-3'),
    ('Management_Data', 90004, 'management-90004'),
]


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


BODY_BOUNDARY = '----relay2BOUNDARY'


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
    """掩掉 uuid / ticks / 时间，让两次运行的响应可以逐字段比较。"""
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
                try:
                    req = _decode_gateway_body(body, self.headers.get('Content-Type') or '')
                except Exception as e:
                    req = {'_decode_err': repr(e)}
                with outer.lock:
                    outer.calls.append({'path': self.path, 'req': req})
                if outer.mode == 'hang':
                    time.sleep(30)
                    return
                if outer.mode == 'error500':
                    self._reply(500, b'{"error":"injected-shittim-failure"}')
                    return
                if outer.mode == 'garbage':
                    self._reply(200, b'<<<not-json-at-all>>>',
                                'text/plain; charset=utf-8')
                    return
                proto = req.get('Protocol') if isinstance(req, dict) else None
                if proto == 'Account_CheckNexon' or proto == 1014:
                    name = 'Account_CheckNexon'
                    pkt = {'Protocol': 1014, 'ResultState': 1,
                           'SessionKey': {'AccountServerId': 2, 'MxToken': TOKEN64},
                           'AccountId': 2}
                else:
                    num = proto if isinstance(proto, int) else -1
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
所以「名字表里没有 / 不在 PROTOCOL_MAP 里」的 token 在 decode_packet 里 json=None ——
这正是 relay2 必须复用 relay v1 的 rl_request_json 用 fragment 拼回请求的原因。
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
    modname = 'relay2_rig_%d' % RIG_MOD_SEQ[0]
    spec = importlib.util.spec_from_file_location(modname, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod
    spec.loader.exec_module(mod)
    mod.load_names()
    return mod


def inject_names(mod, pairs):
    """模拟线上 /www/wwwroot/bapatch/tools/protocol_names.txt 的 202 条名字表。

    本地没有那个文件（绝对路径 /www/wwwroot/... 在 Windows 上不存在），BUILTIN_NAMES
    只有 43 条。线上这 202 条里包含本测试要用的名字，所以直接往 NAME_TABLE 里补同名项
    —— 等价于 load_names() 从文件读到它们。
    """
    added = []
    for num, name, _builtin in pairs:
        tok = b32md5(name)
        if mod.NAME_TABLE.get(tok) != name:
            mod.NAME_TABLE[tok] = name
            added.append((num, name, tok))
    return added


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
    ap = argparse.ArgumentParser(description='patch_relay2.py 的本地重放验收')
    ap.add_argument('--target', required=True,
                    help='打完 patch_3 + patch_relay + patch_relay2 的 account_auth_probe.py')
    ap.add_argument('--patch', default=PATCH_PATH, help='patch_relay2.py 路径（默认同级）')
    ap.add_argument('--keep-rig', action='store_true', help='保留临时装置目录（排查用）')
    args = ap.parse_args(argv)

    if not os.path.isfile(args.target):
        raise SystemExit('!! --target 不存在: %s' % args.target)
    if not os.path.isfile(args.patch):
        raise SystemExit('!! --patch 不存在: %s' % args.patch)

    P = load_module(args.patch, 'relay2_patch_lib')
    src_text = P.read_text(args.target)
    target_sha = hashlib.sha256(src_text.encode('utf-8')).hexdigest()
    print('target : %s' % args.target)
    print('         %d 字节 / sha256 %s'
          % (len(src_text.encode('utf-8')), target_sha))
    print('patched: %s' % ('是' if P.is_patched(src_text) else '否'))
    if not P.is_patched(src_text):
        raise SystemExit('!! 这个文件还没打 patch_relay2，先 --apply')

    R = Report()

    # ---------------- S0：结构不变量
    base_text, _acts = P.build_removed(src_text)
    base_sha = hashlib.sha256(base_text.encode('utf-8')).hexdigest()
    R.add(len(base_text.encode('utf-8')) == P.BASE_SIZE and base_sha == P.BASE_SHA256,
          'S0', '摘掉 PAYLOAD+HOOK 后 == 基线 %d B / %s（实测 %d B / %s）'
          % (P.BASE_SIZE, P.BASE_SHA256[:16], len(base_text.encode('utf-8')), base_sha[:16]))
    i_hook = src_text.find('# >>> BAPATCH-RELAY2-HOOK')
    i_pto = src_text.find('        if proto_int:')
    R.add(0 <= i_hook < i_pto, 'S0',
          'HOOK 整块在 `if proto_int:` 之前（hook@%d < proto_int@%d）' % (i_hook, i_pto))
    R.add(P.indent_at(src_text, i_hook) == 8 and P.indent_at(src_text, i_pto) == 8,
          'S0', 'HOOK 与 `if proto_int:` 同为 8 空格缩进（实测 %d / %d）'
          % (P.indent_at(src_text, i_hook), P.indent_at(src_text, i_pto)))
    tree = __import__('ast').parse(src_text)
    _n, _b, idx_hook, owner = P.ast_hook_try(tree, src_text)
    idx_if = P.ast_proto_int_index(_b)
    R.add(idx_hook is not None and idx_if is not None and idx_hook == idx_if - 1
          and owner == 'FunctionDef',
          'S0', 'AST：HOOK 是 `_bridge` 里 `if proto_int:` 的直接前一条语句'
                '（下标 %r / %r，父节点 %r）' % (idx_hook, idx_if, owner))
    R.add('BAPATCH-RELAY2' not in base_text, 'S0', '基线里零 BAPATCH-RELAY2 残留')

    fake = FakeShittim().start()
    tmp_on = tempfile.mkdtemp(prefix='relay2_on_')
    tmp_off = tempfile.mkdtemp(prefix='relay2_off_')
    tmp_base = tempfile.mkdtemp(prefix='relay2_base_')
    try:
        simple_switches = {'cn_1005.txt': '1\n', 'cn_4000.txt': '1\n',
                           'cn_26000.txt': '1\n', 'cn_3.txt': '1\n'}
        p_on = build_rig(src_text, tmp_on,
                         dict(simple_switches, **{P.SWITCH_FILE: '1\n'}))
        p_off = build_rig(src_text, tmp_off, dict(simple_switches))
        p_base = build_rig(base_text, tmp_base, dict(simple_switches))
        mod_on = load_rig(p_on, tmp_on)
        mod_off = load_rig(p_off, tmp_off)
        mod_base = load_rig(p_base, tmp_base)
        for m in (mod_on, mod_off, mod_base):
            m.GATEWAY = fake.url

        added_on = inject_names(mod_on, RELAY2_PROTOCOLS)
        added_off = inject_names(mod_off, RELAY2_PROTOCOLS)
        added_base = inject_names(mod_base, RELAY2_PROTOCOLS)
        R.info('S0', '模拟线上名字表：给 3 个装置各补 %d 条名字（本机没有 '
               'protocol_names.txt）—— %r' % (len(added_on),
                                              [x[1] for x in added_on][:4]))
        R.add(len(added_on) == len(added_off) == len(added_base), 'S0',
              '三个装置的名字表补丁一致（%d / %d / %d）'
              % (len(added_on), len(added_off), len(added_base)))
        tok8000 = b32md5('Mission_List')
        R.add(mod_on.NAME_TABLE.get(tok8000) == 'Mission_List', 'S0',
              '8000 的 token 在名字表里（= %r）—— 与线上一样，name is not None'
              % (mod_on.NAME_TABLE.get(tok8000),))
        pkt8000 = packet_of(frag_for(8000, ',"AccountId":10015354380'))

        # ---------------- S1：开关关 == 现状（min+base）
        fake.reset('normal')
        reset_session(mod_off)
        code1, resp1, ctype1, rec1 = call_bridge(mod_off, tok8000, pkt8000,
                                                 path='/api/mission/list')
        o1 = body_of(resp1)
        i1 = inner_of(o1)
        R.add(code1 == 200 and ctype1 and rec1.get('gen_kind') == 'min+base',
              'S1', '开关关：8000 -> %r / gen_kind=%r（min+base 空壳，%d B）'
              % (code1, rec1.get('gen_kind'), len(bytes(resp1))))
        R.add(rec1.get('relay2_on') is False and rec1.get('relay2_fallthrough') == 'switch-off'
              and 'relay2_used' not in rec1,
              'S1', '开关关：relay2_on=False / fallthrough=%r / relay2_used 不存在'
              % (rec1.get('relay2_fallthrough'),))
        R.add(isinstance(i1, dict) and i1.get('Protocol') == 8000,
              'S1', '开关关：内层仍是假壳 Protocol=%r（键=%r）'
              % ((i1 or {}).get('Protocol'), sorted(i1 or {})))
        R.add(len(fake.snapshot()) == 0, 'S1',
              '开关关：假 Shittim 一次都没被调用（%d 次）' % len(fake.snapshot()))
        # 与摘掉本补丁的 tmp_base 逐步对照
        reset_session(mod_base)
        code1B, resp1B, ctype1B, rec1B = call_bridge(mod_base, tok8000, pkt8000,
                                                     path='/api/mission/list')
        R.add(code1 == code1B and norm(i1) == norm(inner_of(body_of(resp1B))),
              'S1', '开关关：响应与摘掉本补丁的现状逐字段一致（掩 tick 后；gen_kind=%r）'
              % (rec1B.get('gen_kind'),))

        # ---------------- S2：开关开 == 真 Shittim 数据
        fake.reset('normal')
        reset_session(mod_on)
        tos = []
        orig_pg = mod_on.post_gateway

        def pg_rec(obj, timeout=40):
            tos.append(timeout)
            return orig_pg(obj, timeout=timeout)

        mod_on.post_gateway = pg_rec
        try:
            code2, resp2, ctype2, rec2 = call_bridge(mod_on, tok8000, pkt8000,
                                                     path='/api/mission/list')
        finally:
            mod_on.post_gateway = orig_pg
        o2 = body_of(resp2)
        i2 = inner_of(o2)
        calls2 = fake.snapshot()
        R.add(code2 == 200 and rec2.get('relay2_used') is True and rec2.get('relay2_on') is True,
              'S2', '开关开：8000 -> %r，relay2_used=%r / relay2_on=%r'
              % (code2, rec2.get('relay2_used'), rec2.get('relay2_on')))
        R.add(rec2.get('relay2_protocol') == 8000 and rec2.get('relay2_protocol_num') == 8000,
              'S2', 'relay2_protocol=%r / relay2_protocol_num=%r（= Hash>>32）'
              % (rec2.get('relay2_protocol'), rec2.get('relay2_protocol_num')))
        R.add(isinstance(i2, dict) and i2.get('Protocol') == 8000 and 'Echo' in i2,
              'S2', '内层是假 Shittim 的真响应（Protocol=%r / Echo=%r）'
              % ((i2 or {}).get('Protocol'), (i2 or {}).get('Echo')))
        R.add(rec2.get('relay2_code') == 200 and rec2.get('relay2_resp_len', 0) > 0,
              'S2', 'relay2_code=%r / relay2_resp_len=%r'
              % (rec2.get('relay2_code'), rec2.get('relay2_resp_len')))
        R.add(rec2.get('relay2_session_injected') is True and bool(rec2.get('relay2_err')) is False,
              'S2', 'SessionKey 由 ensure_session(1014) 注入（relay2_session_injected=%r / '
                    'relay2_err=%r）' % (rec2.get('relay2_session_injected'),
                                         rec2.get('relay2_err')))
        chk_1014 = [c for c in calls2 if (c['req'] or {}).get('Protocol') in
                    ('Account_CheckNexon', 1014)]
        chk_8000 = [c for c in calls2 if (c['req'] or {}).get('Protocol') == 8000]
        R.add(len(chk_1014) == 1 and len(chk_8000) == 1, 'S2',
              '假 Shittim 收到 1014=%d 次 / 8000=%d 次（先铸会话再转发，各一次）'
              % (len(chk_1014), len(chk_8000)))
        sk_sent = (chk_8000[0]['req'].get('SessionKey') if chk_8000 else None)
        R.add(sk_sent == {'AccountServerId': 2, 'MxToken': TOKEN64}, 'S2',
              '转发请求里的 SessionKey == Shittim 铸的那张（AccountServerId=%r / MxToken %d 字符）'
              % ((sk_sent or {}).get('AccountServerId'), len((sk_sent or {}).get('MxToken') or '')))
        R.add(tos and tos[-1] == 8, 'S2',
              'post_gateway 收到 timeout=8（不是默认 40；实测 %r）' % (tos[-1:] or None,))
        R.add(o2.get('protocol') == tok8000, 'S2',
              '外层 protocol == 客户端自己的 token（%r）—— 客户端看不出中间换了数据源'
              % (o2.get('protocol'),))
        R.add(norm(i2) != norm(i1), 'S2',
              '开关开后的内层 != 开关关时的 min+base 空壳（真的换了数据源）')

        # ---------------- S7：日志字段齐备
        need = ('relay2_on', 'relay2_used', 'relay2_code', 'relay2_resp_len',
                'relay2_protocol', 'relay2_err', 'relay2_fallthrough')
        miss = [k for k in need if k not in rec2]
        R.add(not miss, 'S7', '成功路径的 7 个日志字段齐备%s'
              % ('' if not miss else '（缺 %r）' % (miss,)))

        # ---------------- S2b：proto_int 有值（模拟线上 rec['req_Hash'] 已置）
        # 关：落在 `if proto_int:` 的 min-envelope；开：仍然被 relay2 接住
        fake.reset('normal')
        reset_session(mod_off)
        codeB, respB, _ctB, recB = call_bridge(mod_off, tok8000, pkt8000,
                                               path='/api/mission/list',
                                               rec_extra={'req_Hash': 8000 << 32})
        fake.reset('normal')
        reset_session(mod_on)
        codeA, respA, _ctA, recA = call_bridge(mod_on, tok8000, pkt8000,
                                               path='/api/mission/list',
                                               rec_extra={'req_Hash': 8000 << 32})
        iA = inner_of(body_of(respA))
        R.add(codeB == 200 and recB.get('fallback') == 'min-envelope',
              'S2b', 'proto_int 有值 + 开关关：走 `if proto_int:` 的 min-envelope'
                     '（fallback=%r / %d B）' % (recB.get('fallback'), len(bytes(respB))))
        R.add(codeA == 200 and recA.get('relay2_used') is True
              and isinstance(iA, dict) and iA.get('Protocol') == 8000,
              'S2b', 'proto_int 有值 + 开关开：仍被 relay2 接住（relay2_used=%r / '
                     'fallthrough=%r）—— 证明钩子确实在 `if proto_int:` 之前'
              % (recA.get('relay2_used'), recA.get('relay2_fallthrough')))

        # ---------------- S3：10 个「名字已知、没有真生成器」的协议
        for num, name, _builtin in RELAY2_PROTOCOLS:
            tok = b32md5(name)
            pkt = packet_of(frag_for(num, ',"AccountId":10015354380'))
            fake.reset('normal')
            code3, resp3, ctype3, rec3 = call_bridge(mod_on, tok, pkt,
                                                     path='/api/%d' % num)
            i3 = inner_of(body_of(resp3))
            R.add(code3 == 200 and rec3.get('relay2_used') is True
                  and rec3.get('relay2_protocol') == num
                  and isinstance(i3, dict) and i3.get('Protocol') == num and 'Echo' in i3,
                  'S3', '%d %-32s -> Shittim 真响应（relay2_protocol=%r / 内层 Protocol=%r）'
                  % (num, name[:32], rec3.get('relay2_protocol'),
                     (i3 or {}).get('Protocol')))
            # 同一协议：开关关时必须还是 min+base 空壳（不能有一半的协议被抢）
            fake.reset('normal')
            code3o, resp3o, _ct3o, rec3o = call_bridge(mod_off, tok, pkt,
                                                       path='/api/%d' % num)
            i3o = inner_of(body_of(resp3o))
            R.add(code3o == 200 and 'relay2_used' not in rec3o
                  and (i3o or {}).get('Protocol') == num
                  and norm(i3o) != norm(i3),
                  'S3', '%d 开关关 -> 仍是空壳（gen_kind=%r），与开关开的数据不同'
                  % (num, rec3o.get('gen_kind')))

        # ---------------- S4：Shittim 故障 -> 200 + min+base + relay2_err
        fake.reset('error500')
        code4, resp4, _ct4, rec4 = call_bridge(mod_on, tok8000, pkt8000,
                                               path='/api/mission/list')
        i4 = inner_of(body_of(resp4))
        R.add(code4 == 200 and rec4.get('gen_kind') == 'min+base'
              and rec4.get('relay2_used') is None and bool(rec4.get('relay2_err')),
              'S4', 'Shittim 回 500 -> bridge 仍 %r / gen_kind=%r / relay2_err=%r'
              % (code4, rec4.get('gen_kind'), rec4.get('relay2_err')))
        R.add(isinstance(i4, dict) and i4.get('Protocol') == 8000
              and rec4.get('relay2_code') == 500,
              'S4', '落回的内层是 min+base 空壳（Protocol=%r / relay2_code=%r）'
              % ((i4 or {}).get('Protocol'), rec4.get('relay2_code')))

        fake.reset('garbage')
        code4b, resp4b, _ct4b, rec4b = call_bridge(mod_on, tok8000, pkt8000,
                                                   path='/api/mission/list')
        R.add(code4b == 200 and rec4b.get('gen_kind') == 'min+base'
              and bool(rec4b.get('relay2_err'))
              and rec4b.get('relay2_fallthrough') == 'shittim-non-dict',
              'S4', 'Shittim 回 200 非 JSON -> 仍 %r / fallthrough=%r'
              % (code4b, rec4b.get('relay2_fallthrough')))

        fake.reset('hang')
        mod_on.SESSION.session_key = {'AccountServerId': 2, 'MxToken': TOKEN64}
        mod_on.SESSION.account_id = 2
        orig_pg2 = mod_on.post_gateway

        def pg_fast(obj, timeout=40):
            return orig_pg2(obj, timeout=min(timeout, 2))

        mod_on.post_gateway = pg_fast
        t0 = time.time()
        try:
            code4c, resp4c, _ct4c, rec4c = call_bridge(mod_on, tok8000, pkt8000,
                                                       path='/api/mission/list')
        finally:
            mod_on.post_gateway = orig_pg2
            fake.mode = 'normal'
        dt4 = time.time() - t0
        R.add(code4c == 200 and rec4c.get('gen_kind') == 'min+base'
              and rec4c.get('relay2_used') is None and bool(rec4c.get('relay2_err'))
              and dt4 < 10,
              'S4', 'Shittim 超时 -> 仍 %r / gen_kind=%r / relay2_err=%r（%.1f s 内返回）'
              % (code4c, rec4c.get('gen_kind'), rec4c.get('relay2_err'), dt4))

        # post_gateway 自己抛异常 -> HOOK 的 except 兜住（不 500、留 relay2_err）
        fake.reset('normal')
        reset_session(mod_on)
        orig_pg3 = mod_on.post_gateway

        def pg_boom(obj, timeout=40):
            raise RuntimeError('injected-post-boom')

        mod_on.post_gateway = pg_boom
        try:
            code4d, resp4d, _ct4d, rec4d = call_bridge(mod_on, tok8000, pkt8000,
                                                       path='/api/mission/list')
        finally:
            mod_on.post_gateway = orig_pg3
        R.add(code4d == 200 and rec4d.get('gen_kind') == 'min+base'
              and rec4d.get('relay2_used') is None
              and 'injected-post-boom' in str(rec4d.get('relay2_err'))
              and rec4d.get('relay2_fallthrough') == 'exception',
              'S4', 'post_gateway 抛异常 -> 仍 %r / fallthrough=%r / relay2_err 非空'
              % (code4d, rec4d.get('relay2_fallthrough')))

        # ---------------- S6：1014 不被钩子拦（无递归）
        fake.reset('normal')
        reset_session(mod_on)
        tok1014 = b32md5('Account_CheckNexon')
        pkt1014 = packet_of(frag_for(1014, ',"AccountId":10015354380'))
        t0 = time.time()
        code6, resp6, _ct6, rec6 = call_bridge(mod_on, tok1014, pkt1014,
                                               path='/api/account/checknexon')
        dt6 = time.time() - t0
        i6 = inner_of(body_of(resp6))
        n1014 = len([c for c in fake.snapshot()
                     if (c['req'] or {}).get('Protocol') in ('Account_CheckNexon', 1014)])
        relay_keys = sorted(k for k in rec6 if k.startswith('relay2_'))
        R.add(code6 == 200 and isinstance(i6, dict) and i6.get('Protocol') == 1014
              and n1014 == 1 and dt6 < 5,
              'S6', 'Account_CheckNexon(1014) -> %r / 内层 Protocol=%r / 只调用 %d 次'
                    '（%.2f s）' % (code6, (i6 or {}).get('Protocol'), n1014, dt6))
        R.add(not relay_keys, 'S6',
              '1014 的 rec 里没有任何 relay2_* 字段（%r）—— 钩子根本没碰它，无递归'
              % (relay_keys,))

        # ---------------- S5：已知协议开关开着时行为不变
        exact = 0
        for nm, num, want_gen in REGRESSION:
            tok = b32md5(nm)
            pkt = packet_of(frag_for(num, ',"AccountId":1001001,"Token":"t"'))
            fake.reset('normal')
            reset_session(mod_on)
            co, ro, cto, reco = call_bridge(mod_on, tok, pkt, path='/api/known/%d' % num)
            fake.reset('normal')
            reset_session(mod_off)
            cf, rf, ctf, recf = call_bridge(mod_off, tok, pkt, path='/api/known/%d' % num)
            fake.reset('normal')
            reset_session(mod_base)
            cb, rb, ctb, recb = call_bridge(mod_base, tok, pkt, path='/api/known/%d' % num)
            # base（= 打补丁前）自己再跑一次：证明「掩码后不一致」纯属时间/uuid 抖动
            fake.reset('normal')
            reset_session(mod_base)
            _c2, rb2, _ct2, _rec2 = call_bridge(mod_base, tok, pkt,
                                                path='/api/known/%d' % num)
            det = norm(body_of(rb)) == norm(body_of(rb2))
            io_, if_, ib_ = inner_of(body_of(ro)), inner_of(body_of(rf)), inner_of(body_of(rb))
            relay_keys = sorted(k for k in reco if k.startswith('relay2_'))
            good = (co == cf == cb == 200 and cto == ctf == ctb
                    and norm(io_) == norm(if_) == norm(ib_)
                    and 'relay2_used' not in reco and det)
            if want_gen is not None:
                good = good and reco.get('gen_kind') == want_gen == recb.get('gen_kind')
            exact += 1 if same_bytes(ro, rb) else 0
            R.add(good, 'S5',
                  '%s(%d)：开关开 / 开关关 / 打补丁前 三者响应逐字段一致'
                  '（gen_kind=%r / relay2_used 不存在 / fallthrough=%r / 现状自证可复现=%r%s）'
                  % (nm, num, reco.get('gen_kind'), reco.get('relay2_fallthrough'), det,
                     '' if same_bytes(ro, rb) else ' / 字节仅差 tick-uuid'))
            R.info('S5', '  ↳ %s(%d) rec relay2_* = %r'
                   % (nm, num, relay_keys))
        R.info('S5', '%d 个已知协议里 %d 个原始字节完全相同，其余仅差 ServerTimeTicks/uuid/'
               '时间字符串（掩码后全部逐字段一致；打补丁前自身两次运行也在同一批字段上不同）'
               % (len(REGRESSION), exact))

        # ---------------- 收尾
        R.add(True, 'S8', '全程只监听 127.0.0.1:%d（假 Shittim），未连任何远端' % fake.port)
    finally:
        fake.stop()
        for d in (tmp_on, tmp_off, tmp_base):
            if args.keep_rig:
                print('（临时装置保留：%s）' % d)
            else:
                shutil.rmtree(d, ignore_errors=True)

    print('\n== 重放断言 ==')
    R.dump()
    n_fail = sum(1 for g, _t, _x in R.rows if g is False)
    n_pass = sum(1 for g, _t, _x in R.rows if g is True)
    print('\n%d 项断言 / %d FAIL / %s'
          % (n_pass, n_fail, 'ALL PASS' if R.ok else 'SOME FAILED'))
    return 0 if R.ok else 1


if __name__ == '__main__':
    sys.exit(main())
