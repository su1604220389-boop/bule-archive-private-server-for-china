#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_relayfix_replay.py -- patch_relay_fix.py 的本地重放验收（纯本地，不连网、不起服务）。

被测对象：
    deploy/patch_relay_fix.py 打到 _sandbox/p3/account_auth_probe.py 之后的 bridge 副本。
装置：
    复用 _relay2_replay.py 的 cn_cipher / cn_wire / cn_nick 替身与 rig 加载器，
    再用本文件自己的假 Shittim（127.0.0.1 随机端口，支持 auth_once / auth_always）。

断言分组：
  F0  结构：target 已打 BAPATCH-RLFIX，基线可还原
  F1  协议号修复：19004 / 90011 / 35003 / 16000，relay v1 与 relay2 两条路径，
      每条各两种 fragment（正常 ,… / 畸形 末位数字+…）—— 重建 Protocol 正确，
      假 Shittim 收到的就是 19004 而不是 190044
  F2  候选顺序：rl_req_build == 1 / 2 / 3（正常 / 前导数字 / 两字符可疑前缀）
  F3  全部候选失败：rl_request_json 返回 None、零 Shittim 请求、落回 min+base、不 500
  F4  Session 重试（成功）：首包 Protocol=-1 / ErrorCode=3，第二包正常 ->
      只重试一次、rl_session_retry=True、rl_session_retry_ok=True、拿到正常数据、
      第二次转发用的是重新铸的 SessionKey
  F5  Session 重试（仍失败）：两次都鉴权失败 -> 落回、不 500、转发计数恰好 2
  F6  _rl_is_auth_fail 正负样本各 5 个
  F7  开关都关：与「摘掉本补丁的基线」响应逐字节一致（冻结 time.time / datetime / uuid）
  F8  访问日志字段：req_frag_head / rl_req_build / rl_req_frag_head 落进 rec
  F9  全程只连 127.0.0.1 的假 Shittim

用法：
    python deploy/_relayfix_replay.py --target deploy/_sandbox/p3/account_auth_probe.py
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
PATCH_PATH = os.path.join(HERE, 'patch_relay_fix.py')
DEFAULT_TARGET = os.path.join(HERE, '_sandbox', 'p3', 'account_auth_probe.py')

UNKNOWN_NAME = 'RelayFix_Unknown_Protocol'
PROTOS = ((19004, 'Scenario_Select'),
          (90011, 'Shop_ListTutorialGacha'),
          (35003, 'MiniGame_MissionList'),
          (16000, 'Toast_List'))
SW_RELAY1 = 'cn_relay_unknown.txt'
SW_RELAY2 = 'cn_relay_known.txt'


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
    """本地假 Shittim：/api/gateway；支持 normal / auth_once / auth_always 三种剧本。"""

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
                if outer.mode == 'hang':
                    time.sleep(30)
                    return
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
                    elif outer.mode == 'auth_always':
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


def main(argv=None):
    ap = argparse.ArgumentParser(description='patch_relay_fix.py 的本地重放验收')
    ap.add_argument('--target', default=DEFAULT_TARGET,
                    help='打完 patch_relay_fix 的 account_auth_probe.py（默认沙箱）')
    ap.add_argument('--patch', default=PATCH_PATH, help='patch_relay_fix.py 路径（默认同级）')
    ap.add_argument('--keep-rig', action='store_true', help='保留临时装置目录（排查用）')
    args = ap.parse_args(argv)

    if not os.path.isfile(args.target):
        raise SystemExit('!! --target 不存在: %s' % args.target)
    if not os.path.isfile(args.patch):
        raise SystemExit('!! --patch 不存在: %s' % args.patch)

    P = load_module(args.patch, 'relayfix_patch_lib')
    src_text = P.read_text(args.target)
    target_sha = hashlib.sha256(src_text.encode('utf-8')).hexdigest()
    print('target : %s' % args.target)
    print('         %d 字节 / sha256 %s' % (len(src_text.encode('utf-8')), target_sha))
    print('patched: %s' % ('是' if P.is_patched(src_text) else '否'))
    if not P.is_patched(src_text):
        raise SystemExit('!! 这个文件还没打 patch_relay_fix，先 --apply')

    R = Report()

    # ---------------- F0：结构
    removed_text, _acts = P.build_removed(src_text)
    removed_sha = hashlib.sha256(removed_text.encode('utf-8')).hexdigest()
    R.add(len(removed_text.encode('utf-8')) == P.BASE_SIZE and removed_sha == P.BASE_SHA256,
          'F0', '摘掉 RLFIX 后 == 基线 %d B / %s（实测 %d B / %s）'
          % (P.BASE_SIZE, P.BASE_SHA256[:16],
             len(removed_text.encode('utf-8')), removed_sha[:16]))
    R.add(P.count_marker_lines(src_text) == (1, 1), 'F0',
          'BAPATCH-RLFIX 标记行 BEGIN/END 各 1（实测 %r）'
          % (P.count_marker_lines(src_text),))

    fake = FakeShittim().start()
    tmp_on = tempfile.mkdtemp(prefix='relayfix_on_')
    tmp_off = tempfile.mkdtemp(prefix='relayfix_off_')
    tmp_base = tempfile.mkdtemp(prefix='relayfix_base_')
    try:
        both_on = {SW_RELAY1: '1\n', SW_RELAY2: '1\n'}
        p_on = L.build_rig(src_text, tmp_on, both_on)
        p_off = L.build_rig(src_text, tmp_off, {})
        p_base = L.build_rig(removed_text, tmp_base, {})
        mod_on = L.load_rig(p_on, tmp_on)
        mod_off = L.load_rig(p_off, tmp_off)
        mod_base = L.load_rig(p_base, tmp_base)
        for m in (mod_on, mod_off, mod_base):
            m.GATEWAY = fake.url
            L.inject_names(m, [(n, name, False) for n, name in PROTOS])
        if 'Mission_List' not in [v for v in mod_on.NAME_TABLE.values()]:
            L.inject_names(mod_on, [(8000, 'Mission_List', True)])
            L.inject_names(mod_off, [(8000, 'Mission_List', True)])
        tok_unknown = b32md5(UNKNOWN_NAME)
        R.add(mod_on.NAME_TABLE.get(tok_unknown) is None, 'F0',
              '未知协议 token = b32md5(%r) 不在名字表（走 relay v1 / HOOK-A）' % UNKNOWN_NAME)
        R.info('F0', '假 Shittim 监听 127.0.0.1:%d' % fake.port)

        # ---------------- F1：协议号修复（两条路径 × 4 协议 × 正常/畸形）
        for path_tag in ('relay1', 'relay2'):
            for num, name in PROTOS:
                token = tok_unknown if path_tag == 'relay1' else b32md5(name)
                for form in ('normal', 'malformed'):
                    frag = L.frag_for(num)
                    if form == 'malformed':
                        frag = str(num)[-1] + frag
                    fake.reset('normal')
                    L.reset_session(mod_on)
                    code, resp, ctype, rec = call(mod_on, token, frag,
                                                  path='/api/unknown')
                    inner = L.inner_of(L.body_of(resp))
                    fwd = fake.forwarded(num)
                    bug_num = int(str(num) + str(num)[-1])
                    bug_calls = fake.forwarded(bug_num)
                    used_key = 'relay_used' if path_tag == 'relay1' else 'relay2_used'
                    proto_key = 'relay_protocol' if path_tag == 'relay1' else 'relay2_protocol'
                    good = (code == 200 and rec.get(used_key) is True
                            and isinstance(inner, dict) and inner.get('Protocol') == num
                            and len(fwd) == 1 and fwd[0]['req'].get('Protocol') == num
                            and not bug_calls
                            and rec.get(proto_key) == num
                            and rec.get('rl_req_build') == (1 if form == 'normal' else 2)
                            and rec.get('req_frag_head') == frag[:300])
                    R.add(good, 'F1',
                          '%s %s/%-5s %-9s -> Protocol=%r / rl_req_build=%r / '
                          'Shittim 收到 %r（错误号 %r 出现 %d 次）'
                          % (path_tag, num, name[:15], form,
                             (inner or {}).get('Protocol'), rec.get('rl_req_build'),
                             fwd[0]['req'].get('Protocol') if fwd else None,
                             bug_num, len(bug_calls)))

        # ---------------- F2：候选顺序（直接调共享实现）
        for frag, want, label in (
                (L.frag_for(19004), 1, '正常 fragment（逗号开头）'),
                ('4' + L.frag_for(19004), 2, '开头残留末位数字 "4"'),
                ('xx' + L.frag_for(19004), 3, '两字符可疑前缀')):
            rec = {}
            obj = mod_on.rl_request_json({'fragment': frag}, rec)
            R.add(isinstance(obj, dict) and obj.get('Protocol') == 19004
                  and rec.get('rl_req_build') == want,
                  'F2', '%s -> rl_req_build=%r / Protocol=%r（期望 %d / 19004）'
                  % (label, rec.get('rl_req_build'), (obj or {}).get('Protocol'), want))

        # ---------------- F3：全部候选失败
        bad_frag = 'garbage"Hash":%d}' % (19004 << 32)
        rec_direct = {}
        obj_direct = mod_on.rl_request_json({'fragment': bad_frag}, rec_direct)
        R.add(obj_direct is None and rec_direct.get('rl_req_build') == 0
              and bool(rec_direct.get('rl_req_build_err')),
              'F3', 'rl_request_json 直接调用 -> None / rl_req_build=0 / err=%r'
              % (rec_direct.get('rl_req_build_err'),))
        fake.reset('normal')
        L.reset_session(mod_on)
        code, resp, ctype, rec = call(mod_on, tok_unknown, bad_frag, path='/api/unknown')
        inner = L.inner_of(L.body_of(resp))
        R.add(code == 200 and not fake.snapshot()
              and rec.get('relay_fallthrough') == 'decode-json'
              and isinstance(inner, dict) and inner.get('Protocol') == 19004,
              'F3', '全候选失败 -> bridge %r / Shittim 请求 %d 次 / fallthrough=%r / '
                    '内层 Protocol=%r（落回 min+base，不 500）'
              % (code, len(fake.snapshot()), rec.get('relay_fallthrough'),
                 (inner or {}).get('Protocol')))
        R.add(rec.get('rl_req_build') == 0 and bool(rec.get('rl_req_build_err'))
              and rec.get('req_frag_head') == bad_frag[:300],
              'F3', '失败也留痕：rl_req_build=%r / rl_req_build_err 非空 / req_frag_head 已写'
              % (rec.get('rl_req_build'),))

        # ---------------- F4：Session 重试成功（relay v1）
        fake.reset('auth_once')
        L.reset_session(mod_on)
        frag = L.frag_for(8006)
        code, resp, ctype, rec = call(mod_on, tok_unknown, frag, path='/api/unknown')
        inner = L.inner_of(L.body_of(resp))
        fwd = fake.forwarded(8006)
        chk = fake.checknexon()
        R.add(code == 200 and rec.get('relay_used') is True
              and rec.get('rl_session_retry') is True
              and rec.get('rl_session_retry_ok') is True
              and isinstance(inner, dict) and inner.get('Protocol') == 8006
              and 'Echo' in (inner or {}),
              'F4', '首包鉴权失败 -> 重试成功：bridge %r / retry=%r / ok=%r / 内层=%r'
              % (code, rec.get('rl_session_retry'), rec.get('rl_session_retry_ok'),
                 (inner or {}).get('Protocol')))
        R.add(len(fwd) == 2 and len(chk) == 2,
              'F4', '只重试 1 次：转发 8006=%d 次 / CheckNexon=%d 次（期望 2 / 2）'
              % (len(fwd), len(chk)))
        sk1 = (fwd[0]['req'].get('SessionKey') or {}) if fwd else {}
        sk2 = (fwd[1]['req'].get('SessionKey') or {}) if len(fwd) > 1 else {}
        R.add(sk1.get('MxToken') == token_for_mint(1)
              and sk2.get('MxToken') == token_for_mint(2),
              'F4', '第二次转发用的是重新铸的 SessionKey（%s… -> %s…）'
              % ((sk1.get('MxToken') or '')[:8], (sk2.get('MxToken') or '')[:8]))

        # ---------------- F5：Session 重试仍失败（relay2）
        fake.reset('auth_always')
        L.reset_session(mod_on)
        tok8006 = b32md5('Mission_GuideMissionSeasonList')
        L.inject_names(mod_on, [(8006, 'Mission_GuideMissionSeasonList', False)])
        frag = L.frag_for(8006)
        code, resp, ctype, rec = call(mod_on, tok8006, frag, path='/api/mission/list')
        inner = L.inner_of(L.body_of(resp))
        fwd = fake.forwarded(8006)
        chk = fake.checknexon()
        R.add(code == 200 and 'relay2_used' not in rec
              and rec.get('relay2_fallthrough') == 'session-retry-failed'
              and rec.get('rl_session_retry') is True
              and rec.get('rl_session_retry_ok') is False
              and isinstance(inner, dict) and inner.get('Protocol') == 8006,
              'F5', '两次都鉴权失败 -> bridge %r / relay2_used=%r / fallthrough=%r / '
                    'retry_ok=%r / 内层 Protocol=%r（落回、不 500）'
              % (code, 'relay2_used' in rec, rec.get('relay2_fallthrough'),
                 rec.get('rl_session_retry_ok'), (inner or {}).get('Protocol')))
        R.add(len(fwd) == 2 and len(chk) == 2,
              'F5', '不循环：转发 8006=%d 次 / CheckNexon=%d 次（恰好 2 / 2）'
              % (len(fwd), len(chk)))

        # ---------------- F6：_rl_is_auth_fail 正负样本各 5
        pos = ({'Protocol': -1},
               {'ErrorCode': 3},
               {'ErrorCode': -7},
               {'Msg': 'Session expired or invalid'},
               {'Message': 'Session invalid'})
        neg = ({}, {'Protocol': 8000}, {'ErrorCode': 0},
               {'Msg': 'OK'}, {'Msg': 'Session limit exceeded'})
        R.add([mod_on._rl_is_auth_fail(x) for x in pos] == [True] * 5,
              'F6', '_rl_is_auth_fail 5 个正样本全部命中（%r）'
              % ([mod_on._rl_is_auth_fail(x) for x in pos],))
        R.add([mod_on._rl_is_auth_fail(x) for x in neg] == [False] * 5,
              'F6', '_rl_is_auth_fail 5 个负样本全部不命中（%r）'
              % ([mod_on._rl_is_auth_fail(x) for x in neg],))

        # ---------------- F7：两个开关都关 == 摘掉补丁的基线（逐字节）
        off_cases = ((tok_unknown, L.frag_for(8006), '/api/unknown', '未知 8006'),
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
                  and 'rl_req_build' not in rec1 and 'req_frag_head' not in rec1
                  and 'rl_session_retry' not in rec1,
                  'F7', '%s 开关关：响应 %d B 与基线逐字节%s / Shittim %d 次 / '
                        'RLFIX 字段=%r'
                  % (label, len(bytes(r1)), '一致' if same else '不一致!!',
                     len(fake.snapshot()),
                     [k for k in ('rl_req_build', 'req_frag_head', 'rl_session_retry')
                      if k in rec1]))

        # ---------------- F8：访问日志字段
        fake.reset('normal')
        L.reset_session(mod_on)
        frag = L.frag_for(90011)
        code, resp, ctype, rec = call(mod_on, tok_unknown, frag, path='/api/unknown')
        need = ('req_frag_head', 'rl_req_build', 'rl_req_frag_head')
        miss = [k for k in need if not rec.get(k) and rec.get(k) != 0]
        R.add(not miss and rec.get('rl_req_build') == 1,
              'F8', '访问日志字段齐备：req_frag_head=%r… / rl_req_build=%r / '
                    'rl_req_frag_head=%r…'
              % ((rec.get('req_frag_head') or '')[:12], rec.get('rl_req_build'),
                 (rec.get('rl_req_frag_head') or '')[:12]))
        R.add(rec.get('req_frag_head') == frag[:300],
              'F8', 'req_frag_head == fragment[:300]（%d 字符）'
              % len(rec.get('req_frag_head') or ''))

        # 上层已经写过 req_frag_head 时不许覆盖（relay2 路径）
        fake.reset('normal')
        L.reset_session(mod_on)
        code, resp, ctype, rec = call(mod_on, b32md5('Scenario_Select'), L.frag_for(19004),
                                      path='/api/scenario/select',
                                      rec_extra={'req_frag_head': 'UPSTREAM-SENTINEL'})
        R.add(code == 200 and rec.get('req_frag_head') == 'UPSTREAM-SENTINEL'
              and rec.get('rl_req_build') == 1,
              'F8', 'relay2：上层已有 req_frag_head -> 不覆盖（%r）/ rl_req_build=%r'
              % (rec.get('req_frag_head'), rec.get('rl_req_build')))

        # ---------------- F9：纯本地
        R.add(fake.url.startswith('http://127.0.0.1:'), 'F9',
              '全程只连假 Shittim %s（未连任何远端）' % fake.url)
    finally:
        fake.stop()
        if args.keep_rig:
            print('rig: %s | %s | %s' % (tmp_on, tmp_off, tmp_base))
        else:
            for d in (tmp_on, tmp_off, tmp_base):
                L.shutil.rmtree(d, ignore_errors=True)

    print('\n== 重放断言 ==')
    R.dump()
    n_fail = sum(1 for good, _t, _x in R.rows if good is False)
    print('\n%d 项断言 / %d FAIL' % (len([r for r in R.rows if r[0] is not None]), n_fail))
    return 0 if R.ok else 1


if __name__ == '__main__':
    sys.exit(main())
