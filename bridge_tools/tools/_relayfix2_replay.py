#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_relayfix2_replay.py -- patch_relay_fix2.py 的本地重放验收（纯本地，不连网、不起服务）。

被测对象：
    deploy/patch_relay_fix2.py 打到 _sandbox/p3/account_auth_probe.py 之后的 bridge 副本
    （即 60f34664… → 本补丁后的产物）。
装置：
    复用 _relay2_replay.py 的 cn_cipher / cn_wire / cn_nick 替身与 rig 加载器，
    再用本文件自己的假 Shittim（127.0.0.1 随机端口，支持 normal / auth_once）。

修的是什么（线上实测）：桥账号服务把 SessionKey.AccountServerId 改成 10000000001
（桥账号服务号），客户端原样回传；relay 原来是「缺了才注入」，于是把 10000000001
转给 Shittim，Shittim 回 `Session expired or invalid`（SessionKeyService.cs:153），
补丁窗口里共 12 次。

断言分组：
  G0  结构：target 已打 BAPATCH-RLFIX2；摘块后逐字节 == 136,894 B / 60f34664…；
      前四层（P3/SIMPLE/RELAY/RELAY2）+ 第五层 RLFIX 的块全在
  G1  客户端带着**错的** SessionKey（{"AccountServerId":10000000001,"MxToken":"<REDACTED_TOKEN>"}）
      -> relay v1 转发给假 Shittim 的 AccountServerId 必须是 2（桥铸的那把），
      且 rl_session_overwrote=True / rl_session_old_sid=10000000001
  G1b 反证：同一请求打在**摘掉本补丁**的基线上 -> Shittim 真会收到 10000000001
      （这就是线上 12 次被拒的根因；本补丁前后对照）
  G2  relay v2 路径同样无条件覆盖（relay2_session_* / rl2_session_*）
  G3  请求里**没有** SessionKey -> 照常注入，rl_session_overwrote=False / old_sid=None
  G4  请求里的 SessionKey **本来就等于** sk -> 覆盖但 overwrote=False（不误报）
  G5  ensure_session 返回 None -> **不覆盖**、落回、不 500、零 Shittim 请求
  G6  鉴权失败重试路径也走无条件覆盖：首包 Protocol:-1，第二次转发收到的仍是 sk
      （relay v1 与 relay v2 各一遍；每次都用重新铸的 key）
  G7  两个 relay 开关都关 -> 响应与「摘掉本补丁的基线」逐字节一致 + 零新字段 + 零 Shittim
  G8  访问日志字段齐备（rl_session_overwrote / rl_session_old_sid /
      relay_session_injected / relay_session_overwrote / relay_session_old_sid）
  G9  全程只连 127.0.0.1 的假 Shittim

用法：
    python deploy/_relayfix2_replay.py --target deploy/_sandbox/p3/account_auth_probe.py
退出码：全 PASS -> 0，否则 1。
"""
from __future__ import annotations

import argparse
import base64
import contextlib
import hashlib
import importlib.util
import json
import os
import sys
import tempfile
import threading
import time
import datetime as _dtmod
import uuid as _uuidmod

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
L = __import__('_relay2_replay')          # 复用替身模块 / rig / 工具（import 期无副作用）
PATCH_PATH = os.path.join(HERE, 'patch_relay_fix2.py')
DEFAULT_TARGET = os.path.join(HERE, '_sandbox', 'p3', 'account_auth_probe.py')

UNKNOWN_NAME = 'RelayFix2_Unknown_Protocol'
KNOWN_8006 = 'Mission_GuideMissionSeasonList'
SW_RELAY1 = 'cn_relay_unknown.txt'
SW_RELAY2 = 'cn_relay_known.txt'

# 线上实测的那个错值：桥账号服务号
BOGUS_SID = 10000000001
BOGUS = {'AccountServerId': BOGUS_SID, 'MxToken': '<REDACTED_TOKEN>'}

LAYER_MARKS = (('BAPATCH-P3-PAYLOAD', 'BAPATCH-P3-HOOK-E', 'BAPATCH-P3-HOOK-D',
                'BAPATCH-P3-HOOK-G'),
               ('BAPATCH-SIMPLE-PAYLOAD', 'BAPATCH-SIMPLE-HOOK-D',
                'BAPATCH-SIMPLE-HOOK-G'),
               ('BAPATCH-RELAY-PAYLOAD', 'BAPATCH-RELAY-HOOK-A'),
               ('BAPATCH-RELAY2-PAYLOAD', 'BAPATCH-RELAY2-HOOK'))


# ================================================================ 工具
def b32md5(name):
    return L.b32md5(name)


def token_for_mint(n):
    """假 Shittim 第 n 次 CheckNexon 铸的 MxToken（64 字符 base64）。"""
    return base64.b64encode(bytes([n % 250 + 1]) * 48).decode('ascii')


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def frag_with_sk(num, sk):
    """客户端明文片段里带上它自己的 SessionKey（线上就是这个形态）。"""
    return L.frag_for(num, ',"SessionKey":%s'
                      % json.dumps(sk, separators=(',', ':'), sort_keys=True))


@contextlib.contextmanager
def frozen_time():
    """冻结 time.time / datetime.datetime.now / uuid.uuid4，让两次响应可逐字节比对。"""
    real_time = time.time
    real_dt = _dtmod.datetime
    real_uuid4 = _uuidmod.uuid4

    class _FrozenDT(real_dt):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 11, 17, 0, 0, 0, 123456)

    time.time = lambda: 1794854400.0
    _dtmod.datetime = _FrozenDT
    _uuidmod.uuid4 = lambda: _uuidmod.UUID('11111111-1111-4111-8111-111111111111')
    try:
        yield
    finally:
        time.time = real_time
        _dtmod.datetime = real_dt
        _uuidmod.uuid4 = real_uuid4


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


# ================================================================ 假 Shittim
class FakeShittim(object):
    """本地假 Shittim：/api/gateway；normal / auth_once（首包 Protocol=-1）两种剧本。"""

    def __init__(self):
        self.lock = threading.Lock()
        self.calls = []
        self.mode = 'normal'
        self.mint = 0           # CheckNexon 次数
        self.proto = 0          # 非 CheckNexon 转发次数
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
                    req = L._decode_gateway_body(body, self.headers.get('Content-Type') or '')
                except Exception as e:
                    req = {'_decode_err': repr(e)}
                with outer.lock:
                    outer.calls.append({'path': self.path, 'req': req})
                proto = req.get('Protocol') if isinstance(req, dict) else None
                if proto == 'Account_CheckNexon' or proto == 1014:
                    with outer.lock:
                        outer.mint += 1
                        mint_no = outer.mint
                    pkt = {'Protocol': 1014, 'ResultState': 1,
                           'SessionKey': {'AccountServerId': 2,
                                          'MxToken': token_for_mint(mint_no)},
                           'AccountId': 2}
                else:
                    with outer.lock:
                        outer.proto += 1
                        idx = outer.proto
                    num = proto if isinstance(proto, int) else -1
                    if outer.mode == 'auth_once' and idx == 1:
                        pkt = {'Protocol': -1, 'ErrorCode': 3,
                               'Msg': 'Session expired or invalid',
                               'ServerTimeTicks': 0}
                    else:
                        pkt = {'Protocol': num,
                               'Echo': sorted(k for k in (req or {}) if k != 'SessionKey')}
                out = json.dumps({'protocol': str(proto),
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

    def reset(self, mode='normal'):
        with self.lock:
            self.calls[:] = []
            self.mint = 0
            self.proto = 0
        self.mode = mode

    def snapshot(self):
        with self.lock:
            return list(self.calls)

    def forwarded(self, num=None):
        out = [c for c in self.snapshot()
               if isinstance(c['req'], dict)
               and c['req'].get('Protocol') not in ('Account_CheckNexon', 1014)]
        if num is not None:
            out = [c for c in out if c['req'].get('Protocol') == num]
        return out

    def checknexon(self):
        return [c for c in self.snapshot()
                if isinstance(c['req'], dict)
                and c['req'].get('Protocol') in ('Account_CheckNexon', 1014)]


# ================================================================ rig
def call(mod, token, frag, path='/api/unknown', rec_extra=None):
    return L.call_bridge(mod, token, L.packet_of(frag), path=path, rec_extra=rec_extra)


def sk_of(call_row):
    """假 Shittim 收到的那条请求里的 SessionKey。"""
    if not call_row:
        return {}
    sk = (call_row['req'] or {}).get('SessionKey')
    return sk if isinstance(sk, dict) else {}


def main(argv=None):
    ap = argparse.ArgumentParser(description='patch_relay_fix2.py 的本地重放验收')
    ap.add_argument('--target', default=DEFAULT_TARGET,
                    help='打完 patch_relay_fix2 的 account_auth_probe.py（默认沙箱）')
    ap.add_argument('--patch', default=PATCH_PATH, help='patch_relay_fix2.py 路径（默认同级）')
    ap.add_argument('--keep-rig', action='store_true', help='保留临时装置目录（排查用）')
    args = ap.parse_args(argv)

    if not os.path.isfile(args.target):
        raise SystemExit('!! --target 不存在: %s' % args.target)
    if not os.path.isfile(args.patch):
        raise SystemExit('!! --patch 不存在: %s' % args.patch)

    P = load_module(args.patch, 'relayfix2_patch_lib')
    src_text = P.read_text(args.target)
    target_sha = hashlib.sha256(src_text.encode('utf-8')).hexdigest()
    print('target : %s' % args.target)
    print('         %d 字节 / sha256 %s' % (len(src_text.encode('utf-8')), target_sha))
    print('patched: %s' % ('是' if P.is_patched(src_text) else '否'))
    if not P.is_patched(src_text):
        raise SystemExit('!! 这个文件还没打 patch_relay_fix2，先 --apply')

    R = Report()

    # ---------------- G0：结构 + 前五层
    removed_text, _acts = P.build_removed(src_text)
    removed_sha = hashlib.sha256(removed_text.encode('utf-8')).hexdigest()
    R.add(len(removed_text.encode('utf-8')) == P.BASE_SIZE and removed_sha == P.BASE_SHA256,
          'G0', '摘掉 RLFIX2 后 == 基线 %d B / %s（实测 %d B / %s）'
          % (P.BASE_SIZE, P.BASE_SHA256[:16],
             len(removed_text.encode('utf-8')), removed_sha[:16]))
    R.add(P.count_marker_lines(src_text) == (1, 1), 'G0',
          'BAPATCH-RLFIX2 标记行 BEGIN/END 各 1（实测 %r）'
          % (P.count_marker_lines(src_text),))
    miss = []
    for layer in LAYER_MARKS:
        for m in layer:
            if not (src_text.count(m + ' v1 BEGIN') == 1 and src_text.count(m + ' v1 END') == 1):
                miss.append(m)
    R.add(not miss, 'G0', '前四层 11 个块全在（P3×4 / SIMPLE×3 / RELAY×2 / RELAY2×2）%s'
          % ('' if not miss else '（缺 %r）' % (miss,)))
    rlf_ok = (src_text.count('# >>> BAPATCH-RLFIX v1 BEGIN') == 1
              and src_text.count('# <<< BAPATCH-RLFIX v1 END <<<') == 1
              and src_text.count('if _rl_is_auth_fail(obj):') == 2)
    R.add(rlf_ok, 'G0', '第五层 RLFIX 块在（BEGIN/END 各 1 + 两处鉴权失败重试）')
    R.add(src_text.find('# >>> BAPATCH-RLFIX v1 BEGIN')
          < src_text.find('# >>> BAPATCH-RLFIX2 v1 BEGIN')
          < src_text.find('# <<< BAPATCH-RLFIX v1 END <<<'),
          'G0', 'RLFIX2 块嵌在 RLFIX 块尾部（LIFO 层序：rlf 摘块会连它一起摘）')

    fake = FakeShittim().start()
    tmp_on = tempfile.mkdtemp(prefix='relayfix2_on_')
    tmp_off = tempfile.mkdtemp(prefix='relayfix2_off_')
    tmp_base = tempfile.mkdtemp(prefix='relayfix2_base_')
    tmp_bug = tempfile.mkdtemp(prefix='relayfix2_bug_')
    try:
        both_on = {SW_RELAY1: '1\n', SW_RELAY2: '1\n'}
        p_on = L.build_rig(src_text, tmp_on, both_on)
        p_off = L.build_rig(src_text, tmp_off, {})
        p_base = L.build_rig(removed_text, tmp_base, {})
        p_bug = L.build_rig(removed_text, tmp_bug, both_on)
        mod_on = L.load_rig(p_on, tmp_on)
        mod_off = L.load_rig(p_off, tmp_off)
        mod_base = L.load_rig(p_base, tmp_base)
        mod_bug = L.load_rig(p_bug, tmp_bug)
        for m in (mod_on, mod_off, mod_base, mod_bug):
            m.GATEWAY = fake.url
        # 四份装置的名字表必须**完全一致**，否则「开关关 -> 与基线逐字节一致」会因为
        # 装置差异（而不是补丁差异）误报。
        PROTOS = ((19004, 'Scenario_Select'), (90011, 'Shop_ListTutorialGacha'),
                  (35003, 'MiniGame_MissionList'), (16000, 'Toast_List'),
                  (8006, KNOWN_8006), (8000, 'Mission_List'))
        for m in (mod_on, mod_off, mod_base, mod_bug):
            L.inject_names(m, [(n, nm, False) for n, nm in PROTOS])

        tok_unknown = b32md5(UNKNOWN_NAME)
        tok_8006 = b32md5(KNOWN_8006)
        R.add(mod_on.NAME_TABLE.get(tok_unknown) is None, 'G0',
              '未知协议 token = b32md5(%r) 不在名字表（走 relay v1 / HOOK-A）' % UNKNOWN_NAME)
        R.info('G0', '假 Shittim 监听 127.0.0.1:%d' % fake.port)
        R.info('G0', '两份装置：修后 %s / 摘掉本补丁的基线 %s'
               % (os.path.basename(p_on), os.path.basename(p_base)))

        # ---------------- G1：relay v1 —— 客户端带着错的 SessionKey
        fake.reset('normal')
        L.reset_session(mod_on)
        frag1 = frag_with_sk(8006, BOGUS)
        code, resp, ctype, rec1 = call(mod_on, tok_unknown, frag1, path='/api/unknown')
        fwd = fake.forwarded(8006)
        got = sk_of(fwd[0] if fwd else None)
        inner = L.inner_of(L.body_of(resp))
        R.add(code == 200 and rec1.get('relay_used') is True
              and got.get('AccountServerId') == 2
              and got.get('MxToken') == token_for_mint(1)
              and len(fwd) == 1,
              'G1', 'relay1 转发前把错 SessionKey 覆盖掉：Shittim 收到 AccountServerId=%r'
                    ' / MxToken=%r…（客户端带的是 %r）'
              % (got.get('AccountServerId'), (got.get('MxToken') or '')[:8], BOGUS_SID))
        R.add(rec1.get('rl_session_overwrote') is True
              and rec1.get('rl_session_old_sid') == BOGUS_SID,
              'G1', 'rl_session_overwrote=%r / rl_session_old_sid=%r（期望 True / %d）'
              % (rec1.get('rl_session_overwrote'), rec1.get('rl_session_old_sid'), BOGUS_SID))
        R.add(rec1.get('relay_session_injected') is True
              and rec1.get('relay_session_overwrote') is True
              and rec1.get('relay_session_old_sid') == BOGUS_SID,
              'G1', '既有字段同步更新：relay_session_injected/overwrote/old_sid = %r / %r / %r'
              % (rec1.get('relay_session_injected'), rec1.get('relay_session_overwrote'),
                 rec1.get('relay_session_old_sid')))
        R.add(isinstance(inner, dict) and inner.get('Protocol') == 8006,
              'G1', 'bridge 仍回 200 + 内层协议 %r（没有因为覆盖而 500）'
              % ((inner or {}).get('Protocol'),))

        # ---------------- G1b：反证 —— 摘掉本补丁的基线会把这个错值转出去
        fake.reset('normal')
        L.reset_session(mod_bug)
        code_b, resp_b, ctype_b, rec_b = call(mod_bug, tok_unknown, frag1, path='/api/unknown')
        fwd_b = fake.forwarded(8006)
        got_b = sk_of(fwd_b[0] if fwd_b else None)
        R.add(code_b == 200 and got_b.get('AccountServerId') == BOGUS_SID
              and len(fwd_b) == 1,
              'G1b', '反证（摘掉本补丁）：同一请求把 AccountServerId=%r 原样转给 Shittim'
                     '（线上 12 次 Session expired/invalid 的根因）'
              % (got_b.get('AccountServerId'),))

        # ---------------- G2：relay v2 —— 同样无条件覆盖
        fake.reset('normal')
        L.reset_session(mod_on)
        code, resp, ctype, rec2 = call(mod_on, tok_8006, frag_with_sk(8006, BOGUS),
                                       path='/api/mission/list')
        fwd2 = fake.forwarded(8006)
        got2 = sk_of(fwd2[0] if fwd2 else None)
        R.add(code == 200 and rec2.get('relay2_used') is True
              and got2.get('AccountServerId') == 2
              and got2.get('MxToken') == token_for_mint(1),
              'G2', 'relay2 转发前同样覆盖：Shittim 收到 AccountServerId=%r / MxToken=%r…'
              % (got2.get('AccountServerId'), (got2.get('MxToken') or '')[:8]))
        R.add(rec2.get('rl2_session_overwrote') is True
              and rec2.get('rl2_session_old_sid') == BOGUS_SID
              and rec2.get('relay2_session_old_sid') == BOGUS_SID,
              'G2', 'rl2_session_overwrote=%r / rl2_session_old_sid=%r / '
                    'relay2_session_old_sid=%r'
              % (rec2.get('rl2_session_overwrote'), rec2.get('rl2_session_old_sid'),
                 rec2.get('relay2_session_old_sid')))
        R.add('rl_session_overwrote' not in rec2,
              'G2', 'relay2 路径不会误写 relay v1 的前缀字段（rl_session_* 不存在）')

        # ---------------- G3：请求里没有 SessionKey -> 照常注入
        fake.reset('normal')
        L.reset_session(mod_on)
        frag3 = L.frag_for(90011)
        code, resp, ctype, rec3 = call(mod_on, tok_unknown, frag3, path='/api/unknown')
        fwd3 = fake.forwarded(90011)
        got3 = sk_of(fwd3[0] if fwd3 else None)
        R.add(code == 200 and got3.get('AccountServerId') == 2
              and rec3.get('rl_session_overwrote') is False
              and rec3.get('rl_session_old_sid') is None
              and rec3.get('relay_session_injected') is True,
              'G3', '没有 SessionKey -> 注入（overwrote=%r / old_sid=%r），Shittim 收到 %r'
              % (rec3.get('rl_session_overwrote'), rec3.get('rl_session_old_sid'),
                 got3.get('AccountServerId')))

        # ---------------- G4：请求里的 SessionKey 本来就等于 sk
        fake.reset('normal')
        L.reset_session(mod_on)
        sk_cached = {'AccountServerId': 2, 'MxToken': token_for_mint(7)}
        mod_on.SESSION.session_key = dict(sk_cached)
        mod_on.SESSION.account_id = 2
        code, resp, ctype, rec4 = call(mod_on, tok_unknown, frag_with_sk(16000, sk_cached),
                                       path='/api/unknown')
        fwd4 = fake.forwarded(16000)
        got4 = sk_of(fwd4[0] if fwd4 else None)
        R.add(code == 200 and got4.get('AccountServerId') == 2
              and got4.get('MxToken') == token_for_mint(7)
              and rec4.get('rl_session_overwrote') is False
              and rec4.get('relay_session_injected') is True
              and len(fake.checknexon()) == 0,
              'G4', 'SessionKey 本来就 == sk -> 覆盖（injected=%r）但 overwrote=%r / '
                    'old_sid=%r；CheckNexon %d 次（走缓存）'
              % (rec4.get('relay_session_injected'), rec4.get('rl_session_overwrote'),
                 rec4.get('rl_session_old_sid'), len(fake.checknexon())))

        # ---------------- G5：ensure_session 返回 None -> 不覆盖、落回
        fake.reset('normal')
        L.reset_session(mod_on)
        real_ensure = mod_on.ensure_session
        mod_on.ensure_session = lambda rec: (None, None)
        try:
            code, resp, ctype, rec5 = call(mod_on, tok_unknown, frag_with_sk(8006, BOGUS),
                                           path='/api/unknown')
        finally:
            mod_on.ensure_session = real_ensure
        inner5 = L.inner_of(L.body_of(resp))
        R.add(code == 200 and not fake.snapshot()
              and rec5.get('relay_fallthrough') == 'ensure-session'
              and 'rl_session_overwrote' not in rec5
              and 'relay_session_overwrote' not in rec5,
              'G5', 'ensure_session 回 None -> 不覆盖、不算 overwrote、'
                    '落回 fallthrough=%r、Shittim %d 次、bridge %r'
              % (rec5.get('relay_fallthrough'), len(fake.snapshot()), code))
        R.add(isinstance(inner5, dict) and inner5.get('Protocol') == 8006,
              'G5', '落回后仍是正常响应（内层 Protocol=%r），没有 500'
              % ((inner5 or {}).get('Protocol'),))

        # ---------------- G6：鉴权失败重试路径也走无条件覆盖
        fake.reset('auth_once')
        L.reset_session(mod_on)
        code, resp, ctype, rec6 = call(mod_on, tok_unknown, frag_with_sk(8006, BOGUS),
                                       path='/api/unknown')
        fwd6 = fake.forwarded(8006)
        sk_a = sk_of(fwd6[0] if fwd6 else None)
        sk_b = sk_of(fwd6[1] if len(fwd6) > 1 else None)
        inner6 = L.inner_of(L.body_of(resp))
        R.add(code == 200 and len(fwd6) == 2
              and rec6.get('rl_session_retry') is True
              and rec6.get('rl_session_retry_ok') is True
              and isinstance(inner6, dict) and inner6.get('Protocol') == 8006,
              'G6', 'relay1 重试：转发 %d 次 / retry=%r / ok=%r / 内层 %r'
              % (len(fwd6), rec6.get('rl_session_retry'), rec6.get('rl_session_retry_ok'),
                 (inner6 or {}).get('Protocol')))
        R.add(sk_a.get('AccountServerId') == 2 and sk_b.get('AccountServerId') == 2
              and sk_a.get('MxToken') == token_for_mint(1)
              and sk_b.get('MxToken') == token_for_mint(2),
              'G6', '两次转发收到的都是桥铸的 sk（%r/%r… -> %r/%r…）'
              % (sk_a.get('AccountServerId'), (sk_a.get('MxToken') or '')[:8],
                 sk_b.get('AccountServerId'), (sk_b.get('MxToken') or '')[:8]))
        R.add(rec6.get('rl_session_overwrote') is True
              and rec6.get('rl_session_old_sid') == 2,
              'G6', '重试那次也走无条件覆盖：overwrote=%r / old_sid=%r（= 上一把桥铸的）'
              % (rec6.get('rl_session_overwrote'), rec6.get('rl_session_old_sid')))

        fake.reset('auth_once')
        L.reset_session(mod_on)
        code, resp, ctype, rec7 = call(mod_on, tok_8006, frag_with_sk(8006, BOGUS),
                                       path='/api/mission/list')
        fwd7 = fake.forwarded(8006)
        R.add(code == 200 and len(fwd7) == 2
              and rec7.get('rl_session_retry_ok') is True
              and rec7.get('rl2_session_overwrote') is True
              and rec7.get('rl2_session_old_sid') == 2
              and all(sk_of(c).get('AccountServerId') == 2 for c in fwd7),
              'G6', 'relay2 重试同样覆盖：转发 %d 次 / ok=%r / rl2_overwrote=%r / '
                    'old_sid=%r / 两次 AccountServerId=%r'
              % (len(fwd7), rec7.get('rl_session_retry_ok'),
                 rec7.get('rl2_session_overwrote'), rec7.get('rl2_session_old_sid'),
                 [sk_of(c).get('AccountServerId') for c in fwd7]))

        # ---------------- G7：两个开关都关 == 摘掉本补丁的基线（逐字节）
        off_cases = ((tok_unknown, frag_with_sk(8006, BOGUS), '/api/unknown', '未知 8006 + 错 Key'),
                     (b32md5('Mission_List'), L.frag_for(8000), '/api/mission/list',
                      '已知 8000'),
                     (b32md5('Scenario_Select'), L.frag_for(19004), '/api/scenario/select',
                      '已知 19004'))
        for token, frag, path, label in off_cases:
            fake.reset('normal')
            with frozen_time():
                L.reset_session(mod_off)
                c1, r1, t1, rec1 = call(mod_off, token, frag, path=path)
                L.reset_session(mod_base)
                c2, r2, t2, rec2 = call(mod_base, token, frag, path=path)
            same = (c1 == c2 and bytes(r1) == bytes(r2) and t1 == t2)
            R.add(same and not fake.snapshot()
                  and not [k for k in rec1 if k.startswith(('rl_session_', 'rl2_session_',
                                                            'relay_session_', 'relay2_session_'))],
                  'G7', '%s 开关关：响应 %d B 与基线逐字节%s / Shittim %d 次 / 新字段=%r'
                  % (label, len(bytes(r1)), '一致' if same else '不一致!!',
                     len(fake.snapshot()),
                     [k for k in rec1 if k.startswith('rl_session_') or
                      k.startswith('rl2_session_')]))

        # ---------------- G8：访问日志字段齐备
        fake.reset('normal')
        L.reset_session(mod_on)
        code, resp, ctype, rec8 = call(mod_on, tok_unknown, frag_with_sk(35003, BOGUS),
                                       path='/api/unknown')
        need = ('rl_session_overwrote', 'rl_session_old_sid',
                'relay_session_injected', 'relay_session_overwrote',
                'relay_session_old_sid')
        miss = [k for k in need if k not in rec8]
        R.add(not miss and rec8.get('rl_session_old_sid') == BOGUS_SID,
              'G8', '访问日志字段齐备 %r（缺 %r）/ old_sid=%r'
              % (list(need), miss, rec8.get('rl_session_old_sid')))

        # ---------------- G9：纯本地
        R.add(fake.url.startswith('http://127.0.0.1:'), 'G9',
              '全程只连假 Shittim %s（未连任何远端）' % fake.url)
    finally:
        fake.stop()
        if args.keep_rig:
            print('rig: %s | %s | %s | %s' % (tmp_on, tmp_off, tmp_base, tmp_bug))
        else:
            for d in (tmp_on, tmp_off, tmp_base, tmp_bug):
                L.shutil.rmtree(d, ignore_errors=True)

    print('\n== 重放断言 ==')
    R.dump()
    n_fail = sum(1 for good, _t, _x in R.rows if good is False)
    print('\n%d 项断言 / %d FAIL' % (len([r for r in R.rows if r[0] is not None]), n_fail))
    return 0 if R.ok else 1


if __name__ == '__main__':
    sys.exit(main())
