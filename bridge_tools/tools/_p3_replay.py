#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_p3_replay.py -- 协议 3 补丁的**本地重放验收**（不连网、不起服务、不写 --target）。

做的事：把打完补丁的 bridge 副本放进临时装置（cn_* 用长度等价的替身模块），
构造一条合成的 /api/networktime/sync 请求，直接调 Handler._bridge()，
然后对回来的字节做逐项断言：

  A1  外层 protocol 字段 == 'NetworkTime_Sync'
  A2  cn_wire.wrap_response 出来的字节数 **恰好 620**（官方 resp_bytes）
  A3  内层 7 键，键序 == official_spec.json 的 top_key_order
  A4  ReceiveTick == EchoSendTick 且 != 0（红线：客户端靠它算时钟偏移）
  A5  0 <= ServerTimeTicks - ReceiveTick < 10 ms（官方 12 ticks）
  A6  内层 RequestId == 外层 requestid（uuid4 形态）
  A7  ReceiveTick 解回墙钟 ≈ 现在（±180 s，tick 口径自证）
  A8  请求里的 SessionKey(AccountServerId/MxToken) 原样回显
  A9  生成器抛异常 -> 仍 200，长度 == 打补丁前，rec['p3_err'] 留痕（不 500 / 不断连）
  A10 开关缺失 / =0 -> 行为完全回到打补丁前
  A11 不抢别的协议（4000 / 1017 / 24000 / 8000 / 90004 -> None）
  A12 连发 5 次，长度恒为 620（不随时间抖动）

用法：
    python deploy/_p3_replay.py --target deploy/_sandbox/p3/account_auth_probe.py
    python deploy/_p3_replay.py --target /www/wwwroot/bapatch/tools/account_auth_probe.py
退出码：全 PASS -> 0，否则 1。
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import uuid

sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
PATCH3_PATH = os.path.join(HERE, 'patch_3.py')
OFFICIAL3 = os.path.join(HERE, '..', '..', '..', '..',
                         'report', '_tmp', 'official_decoded_201',
                         '04_3_api_networktime_sync.response.json')

EXPECT_WIRE = 620
EXPECT_NAME = 'NetworkTime_Sync'
EXPECT_ORDER = ['Protocol', 'SessionKey', 'ServerTimeTicks', 'ServerNotification',
                'RequestId', 'ReceiveTick', 'EchoSendTick']


def load_patch3(path):
    spec = importlib.util.spec_from_file_location('p3patch_lib', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


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


def decode_ticks(ticks):
    return dt.datetime(1, 1, 1) + dt.timedelta(microseconds=int(ticks) // 10)


def main(argv=None):
    ap = argparse.ArgumentParser(description='协议 3 补丁本地重放验收')
    ap.add_argument('--target', required=True, help='打完补丁的 account_auth_probe.py')
    ap.add_argument('--patch3', default=PATCH3_PATH, help='patch_3.py 路径（默认同级）')
    ap.add_argument('--keep-rig', action='store_true', help='保留临时装置目录（排查用）')
    args = ap.parse_args(argv)

    if not os.path.isfile(args.target):
        raise SystemExit('!! --target 不存在: %s' % args.target)
    if not os.path.isfile(args.patch3):
        raise SystemExit('!! --patch3 不存在: %s' % args.patch3)

    P = load_patch3(args.patch3)
    src_text = P.read_text(args.target)
    print('target : %s' % args.target)
    print('         %d 字节 / sha256 %s'
          % (len(src_text.encode('utf-8')), P.sha256_text(src_text)[:16]))
    print('patched: %s' % ('是' if P.is_patched(src_text) else '否'))
    if not P.is_patched(src_text):
        raise SystemExit('!! 这个文件还没打补丁，先 --apply')

    R = Report()
    legacy_text, _ = P.build_removed(src_text)
    frag = P.rig_fragment()
    pkt = P._packet_of(frag)
    body = (None, pkt)

    tmp = tempfile.mkdtemp(prefix='p3replay_')
    tmp_legacy = tempfile.mkdtemp(prefix='p3replay_legacy_')
    try:
        # ---------------- 装置：补丁后
        rig = P.build_rig(src_text, tmp)
        mod = P.load_rig(rig, tmp)
        mod.load_names()
        P.write_text(os.path.join(tmp, P.SWITCH_FILE), '1\n')

        code, resp, ctype, rec = P._rig_call(mod, pkt)
        wire = resp if isinstance(resp, (bytes, bytearray)) else resp.encode()

        # 响应体是 cn_wire 的**密文容器**（base64(密文+key)，与官方一致），
        # 外层 JSON 在 plaintext 里；替身 cn_wire 把 plaintext 原样吐在 CALLS 里。
        calls = list(getattr(mod.cn_wire, 'CALLS', []))
        plain = calls[-1][1] if calls else ''
        try:
            outer = json.loads(plain) if plain else {}
        except Exception as e:
            outer = {}
            R.add(False, 'A1', '外层明文不是 JSON: %r' % (e,))
        R.info('A0', '响应体 = base64(密文+key)（%d B），外层明文 %d B' % (len(wire), len(plain)))
        R.add(outer.get('protocol') == EXPECT_NAME, 'A1',
              "外层 protocol == %r（实测 %r）" % (EXPECT_NAME, outer.get('protocol')))
        R.add(code == 200 and ctype.startswith('text/plain'), 'A1',
              'HTTP %r / Content-Type %r（官方同款 text/plain）' % (code, ctype))
        R.add(len(wire) == EXPECT_WIRE, 'A2',
              'wire 字节数 == %d（实测 %d）' % (EXPECT_WIRE, len(wire)))
        try:
            raw = base64.b64decode(wire, validate=True)
            b64_ok = len(raw) > 32 and (len(raw) - 32) % 16 == 0
        except Exception as e:
            raw, b64_ok = b'', False
            R.info('A2', 'base64 解码出错: %r' % (e,))
        R.add(b64_ok, 'A2', 'base64(密文+key32) 形态成立：raw %d B = ct %d B + key 32 B'
              % (len(raw), len(raw) - 32))

        inner = json.loads(outer['packet']) if outer.get('packet') else {}

        # A3 —— 键序
        R.add(list(inner.keys()) == EXPECT_ORDER, 'A3',
              '内层键序 == 官方 top_key_order（%d 键）' % len(inner))
        spec = P.spec_order3()
        if spec:
            R.add(list(inner.keys()) == list(spec), 'A3',
                  '内层键序 == official_spec.json protocols["3"].top_key_order')

        # A4 —— 两个 tick
        rt, et = inner.get('ReceiveTick'), inner.get('EchoSendTick')
        R.add(isinstance(rt, int) and rt > 0, 'A4', 'ReceiveTick 是真时间戳（%r，非 0）' % (rt,))
        R.add(rt == et, 'A4', 'ReceiveTick == EchoSendTick（红线）：%r == %r' % (rt, et))

        # A5 —— ServerTimeTicks 与它们的关系
        stt = inner.get('ServerTimeTicks')
        d = (stt - rt) if isinstance(stt, int) and isinstance(rt, int) else -1
        R.add(0 <= d < 100000, 'A5',
              'ServerTimeTicks - ReceiveTick = %d ticks（0..100000 即 0..10 ms）' % d)

        # A6 —— RequestId
        rid, orid = inner.get('RequestId'), outer.get('requestid')
        try:
            uuid.UUID(rid)
            uuid_ok = True
        except Exception:
            uuid_ok = False
        R.add(rid == orid and uuid_ok, 'A6',
              '内层 RequestId == 外层 requestid 且是 uuid 形态（%s）' % str(rid)[:8])

        # A7 —— tick 口径自证：解回墙钟应 ≈ 现在
        now = dt.datetime.now()
        try:
            back = decode_ticks(rt)
            delta = abs((now - back).total_seconds())
        except Exception:
            back, delta = None, 1e9
        R.add(delta < 180, 'A7',
              'ReceiveTick 解回 %s，与现在 %s 差 %.1f s（<180 s）'
              % (back, now.strftime('%Y-%m-%d %H:%M:%S'), delta))

        # A8 —— SessionKey 回显
        sk = inner.get('SessionKey') or {}
        R.add(sk.get('AccountServerId') == 10015354380
              and sk.get('MxToken') == 'Vji5A/Cy6X2enQZKeYgrjxAC8MoRDOCT2Tb1SW13PcZTq2cnyCPPdd81pGbzYBKA',
              'A8', '请求 SessionKey 原样回显（AccountServerId=%r / MxToken %d 字符）'
              % (sk.get('AccountServerId'), len(sk.get('MxToken') or '')))
        R.add(rec.get('gen_kind') == 'networktime-3' and rec.get('p3_hook'),
              'A8', 'rec.gen_kind=%r / p3_hook=%r / ticks_mode=%r'
              % (rec.get('gen_kind'), rec.get('p3_hook'), rec.get('p3_ticks_mode')))

        # A9 —— 生成器异常 -> 降级不断连
        legacy_len = P._legacy_len(legacy_text, tmp_legacy, pkt)
        orig_build = mod.p3_build

        def boom(*a, **kw):
            raise RuntimeError('replay-injected failure')
        mod.p3_build = boom
        try:
            code9, resp9, ctype9, rec9 = P._rig_call(mod, pkt)
        finally:
            mod.p3_build = orig_build
        R.add(code9 == 200 and len(resp9) == legacy_len, 'A9',
              '生成器抛异常 -> %r / %d B（== 打补丁前 %d B），没有 500/断连'
              % (code9, len(resp9), legacy_len))
        R.add('p3_err' in rec9 and 'replay-injected' in str(rec9.get('p3_err')), 'A9',
              '异常留痕 rec.p3_err=%r' % (rec9.get('p3_err'),))

        # A10 —— 开关
        sw = os.path.join(tmp, P.SWITCH_FILE)
        os.remove(sw)
        code10, resp10, ctype10, rec10 = P._rig_call(mod, pkt)
        R.add(code10 == 200 and len(resp10) == legacy_len, 'A10',
              'cn_3.txt 缺失 -> %r / %d B == 打补丁前（行为完全回退）'
              % (code10, len(resp10)))
        P.write_text(sw, '0\n')
        code10b, resp10b, ctype10b, rec10b = P._rig_call(mod, pkt)
        R.add(code10b == 200 and len(resp10b) == legacy_len, 'A10',
              'cn_3.txt=0 -> %r / %d B == 打补丁前' % (code10b, len(resp10b)))
        P.write_text(sw, '1\n')

        # A11 —— 不抢别的协议
        quiet = []
        for num in (4000, 1017, 24000, 8000, 90004, 1005, 26000):
            r = mod.p3_route({'req_Hash': num << 32}, None, num, '', None, None, hook='X')
            if r is not None:
                quiet.append(num)
        R.add(not quiet, 'A11', 'p3_route 对别的协议返回 None（%r）'
              % (quiet or '4000/1017/24000/8000/90004/1005/26000 全部 None',))

        # A12 —— 稳定性
        lens = []
        for _ in range(5):
            c, r, ct, rr = P._rig_call(mod, pkt)
            lens.append(len(r))
        R.add(set(lens) == {EXPECT_WIRE}, 'A12',
              '连发 5 次长度 %r（恒为 %d）' % (lens, EXPECT_WIRE))

        # A13 —— 请求里 packet 解不出来（空包 / 换了密钥）也不能崩
        code13, resp13, ctype13, rec13 = P._rig_call(mod, '')
        calls13 = list(getattr(mod.cn_wire, 'CALLS', []))
        try:
            inner13 = json.loads(json.loads(calls13[-1][1])['packet']) if calls13 else {}
        except Exception:
            inner13 = {}
        sk13 = inner13.get('SessionKey') or {}
        R.add(code13 == 200 and len(resp13) == EXPECT_WIRE, 'A13',
              'packet 解不出来时仍回 %r / %d B（不 500、不断连）'
              % (code13, len(resp13)))
        R.add(len(sk13.get('MxToken') or '') == 64 and bool(inner13.get('ReceiveTick')), 'A13',
              '兜底 SessionKey 由账号派生（MxToken %d 字符）且两个 tick 仍是真值'
              % len(sk13.get('MxToken') or ''))

        # 官方抓包对照（本机有就比，没有就只报 INFO）
        if os.path.isfile(OFFICIAL3):
            with open(OFFICIAL3, 'r', encoding='utf-8') as fh:
                off = json.load(fh)
            R.add(len(off['plain'].encode('utf-8')) == 430, 'REF',
                  '官方明文 %d B -> pkcs7 432 + key 32 -> base64 = 620（容器算式自证）'
                  % len(off['plain'].encode('utf-8')))
    finally:
        if args.keep_rig:
            print('（临时装置保留：%s / %s）' % (tmp, tmp_legacy))
        else:
            shutil.rmtree(tmp, ignore_errors=True)
            shutil.rmtree(tmp_legacy, ignore_errors=True)

    print('\n== 重放断言 ==')
    R.dump()
    n_fail = sum(1 for g, _t, _x in R.rows if g is False)
    print('\n%d 项断言 / %d FAIL / %s'
          % (sum(1 for g, _t, _x in R.rows if g is not None), n_fail,
             'ALL PASS' if R.ok else 'SOME FAILED'))
    return 0 if R.ok else 1


if __name__ == '__main__':
    sys.exit(main())
