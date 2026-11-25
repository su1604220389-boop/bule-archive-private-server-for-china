#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patch_3.py -- 协议 3 / api/networktime/sync / NetworkTime_Sync 的服务端补丁。

背景（都是已确认的事实，证据见 PROGRESS_3_NETWORKTIME.md）：
  * 线上 bridge 现在把协议 3 回成「通用空构造」：只有 Protocol / ServerTimeTicks /
    ServerNotification 等键，**没有 ReceiveTick / EchoSendTick**（或为 0）。
    客户端拿不到有效的两个 tick → 算不出时钟偏移 → 静默不再发下一个请求。
  * 官方 04_3 抓包：内层 314 B / 外层 wire **620 B**，7 个键，
    ReceiveTick == EchoSendTick（服务端收到请求那一刻），ServerTimeTicks 比它们大 12 ticks
    （1.2 µs，同一次取时的抖动），内层 RequestId == 外层 requestid。
  * 生成器 work/ba/server/deploy/gen3.py 的 build_3() 已能逐字节复现官方 314 B
    （--verify-official PASS / spec_check FAIL 0 WARN 0）。

本补丁做三件事：
  1. 把「协议 3 载荷生成器」作为一个**自包含模块**（P3_PAYLOAD_SRC，只用标准库）
     原样内嵌进 bridge 的 `if __name__ == '__main__':` 之前 —— 和 patch_simple.py
     内嵌 simple_payload.py 是同一套路。它是运行时唯一真源；--verify 会拿
     gen3.build_3() 跟它逐字节比对，两边一旦不一致立刻报 FAIL。
  2. 挂三个钩子（每个都有独立标记，--rollback 逐个摘）：
       HOOK-E  _bridge() 里 name 解析之后、exp 分支之前 —— 按协议名最早接管；
       HOOK-D  path D 的 `if proto_int:` 之前 —— 兜住 {"Protocol":3} 单键回包；
       HOOK-G  _generic_protocol_response() 里 `if num == 90004:` 之前 —— 泛接口兜底。
     三层都包 try/except：本补丁自己出任何异常只写 rec['p3_err'] 然后原路返回，
     绝不会 500 / 断连（客户端断线比返回错数据更难查）。
  3. 运行时开关 /www/wwwroot/bapatch/cn_3.txt（1=开 0=关，**缺失=关**）。
     可选 /www/wwwroot/bapatch/cn_3_ticks.txt：'local'（默认，= 官方墙钟口径）
     或 'utc'。缺文件不报错。

红线：协议 3 绝不能继续走通用空构造。ReceiveTick / EchoSendTick 必须是真时间戳，
      否则客户端算错时钟偏移，所有倒计时/活动时间错乱。

不碰的东西：cn_preempt / cn_bridge_exp / cn_bridge_mode / 1017 / 24000 / 8000 /
            90004 / patch_simple 的任何逻辑。本基线里根本没有 cn_preempt 相关代码。

用法（--src 必须显式给，脚本不会猜路径 —— 猜错会静默打在沙箱副本上）：
    # 1) 自检（不写文件）
    python deploy/patch_3.py --src /www/wwwroot/bapatch/tools/account_auth_probe.py --verify
    # 2) 只看插入位置和 diff
    python deploy/patch_3.py --src /www/wwwroot/bapatch/tools/account_auth_probe.py --dry-run
    # 3) 打补丁（先备份 .p3.bak.<ts>，再写，再自检）
    python deploy/patch_3.py --src ... --apply
    # 4) 证明新分支真的会被走到（不走网络，纯本地仿真）
    python deploy/patch_3.py --src ... --prove-dispatch
    # 5) 回滚（优先用 .p3.bak.* 还原；没有备份就摘块）
    python deploy/patch_3.py --src ... --rollback

本地演练（不碰线上）：
    python deploy/patch_3.py --src deploy/_sandbox/p3/account_auth_probe.py --apply
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import importlib.util
import io
import json
import os
import re
import shutil
import sys
import tempfile
import time

sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
PROTO_DIR = os.path.join(ROOT, 'work', 'ba', 'proto')
SPEC_PATH = os.path.join(PROTO_DIR, 'official_spec.json')
DECODED_DIR = os.path.join(ROOT, 'report', '_tmp', 'official_decoded_201')
OFFICIAL3 = os.path.join(DECODED_DIR, '04_3_api_networktime_sync.response.json')
GEN3_PATH = os.path.join(HERE, 'gen3.py')
GEN_COMMON_PATH = os.path.join(HERE, 'gen_common.py')

LIVE_SRC = '/www/wwwroot/bapatch/tools/account_auth_probe.py'
DEFAULT_SWITCH_DIR = '/www/wwwroot/bapatch'

# 基线指纹：线上 account_auth_probe.py（2026-11-16 抓到的那一份）
BASELINE_SIZE = 90585
BASELINE_SHA256 = '368aa5e70941c3f08c59a9ede1b662331e5800dc0a714bc0a30dfbf252dd073a'

VER = 'v1'
PROTO = 3
PROTO_NAME = 'NetworkTime_Sync'
SWITCH_FILE = 'cn_3.txt'
TICKS_FILE = 'cn_3_ticks.txt'

# ---------------------------------------------------------------- 锚点
# 三个锚点都必须**在 bridge 里唯一**；不唯一就拒绝动文件（见 anchor_pos）。
# 值 = (锚点文本, 'before' | 'after')：after = 插到这段文本**之后**。
ANCHOR_E = ("        name = NAME_TABLE.get(proto_str) or EXTRA_TOKENS.get(proto_str)\n"
            "        rec['protocol_name'] = name\n")
ANCHOR_D = ("        if proto_int:\n"
            "            obj = cn_nick.build_min_response(proto_int)\n")
ANCHOR_G = "        if num == 90004:\n"
ANCHOR_PAYLOAD = "if __name__ == '__main__':\n"

UNIT_PAYLOAD = 'PAYLOAD'
UNIT_HOOK_E = 'HOOK-E'
UNIT_HOOK_D = 'HOOK-D'
UNIT_HOOK_G = 'HOOK-G'
UNITS = (UNIT_PAYLOAD, UNIT_HOOK_E, UNIT_HOOK_D, UNIT_HOOK_G)

ANCHORS = {UNIT_PAYLOAD: (ANCHOR_PAYLOAD, 'before'),
           UNIT_HOOK_E: (ANCHOR_E, 'after'),      # 插在「协议名解析完」之后
           UNIT_HOOK_D: (ANCHOR_D, 'before'),
           UNIT_HOOK_G: (ANCHOR_G, 'before')}

ANCHOR_DESC = {
    UNIT_PAYLOAD: "bridge 顶层，`if __name__ == '__main__':` 之前",
    UNIT_HOOK_E: "_bridge() 里协议名解析完、`if exp == 'experror':` 之前",
    UNIT_HOOK_D: "_bridge() 的 path D，`if proto_int:` 之前",
    UNIT_HOOK_G: "_generic_protocol_response() 里，`if num == 90004:` 之前",
}

# ================================================================ 内嵌载荷（唯一真源）
# 语义 == gen3.build_3(Account(...))；只用标准库；公共名字 p3_* / P3_* 前缀。
P3_PAYLOAD_SRC = r'''# -*- coding: utf-8 -*-
"""NetworkTime_Sync (protocol 3) 载荷生成器 —— 内嵌进 bridge 的运行时真源。

与 deploy/gen3.py 的 build_3() 逐字节等价（patch_3.py --verify 用真生成器比对）：
    acct = Account(server_id, mxtoken, request_id, now)      # now 必须是 datetime
    obj  = build_3(acct)                                     # ReceiveTick == EchoSendTick
    顶层键序 = official_spec.json protocols["3"].top_key_order

官方 04_3 抓包（report/_tmp/official_decoded_201/04_3_api_networktime_sync.response.json）：
    inner 314 B / wire 620 B，7 键；
    ReceiveTick == EchoSendTick == 639304002554622693；
    ServerTimeTicks = ...705（比前两者大 12 ticks = 1.2 µs，同一次取时的抖动）；
    inner.RequestId == outer.requestid（同一个 uuid）。
请求 DTO 没有业务字段（只有 HttpMessage 外壳），所以服务端**没有**可回显的客户端 tick，
两个 tick 都填「收到请求那一刻」就是官方行为。

tick 口径 = 服务器本地墙钟（不是 UTC）：
    官方 ServerTimeTicks=639304002554622705 解出来是 2026-11-16T04:30:55.462，
    HAR 里同一条请求的 startedDateTime=2026-11-15T20:30:55.625Z（Unix 口径），
    _timeline.txt 的 Beijing 列写 04:30:55.625 —— 即官方发的是北京墙钟。
    客户端是北京设备，只有同口径才能算出 ≈0 的偏移；发 UTC 会整体差 8 小时。
    需要时可用 cn_3_ticks.txt 写 'utc' 覆盖。

约定（原样贴进 bridge 的模块命名空间，所以）：
  * 不写 from __future__ / 不写 if __name__ == '__main__'；
  * 只用标准库，且全部用 _p3* 别名 import，不污染 bridge 现有全局名；
  * import 期不碰文件系统、不碰网络。
"""
import base64 as _p3base64
import datetime as _p3dt
import hashlib as _p3hashlib
import os as _p3os
import re as _p3re
import uuid as _p3uuid

P3_PROTOCOL = 3
P3_NAME = 'NetworkTime_Sync'

# official_spec.json -> protocols["3"].top_key_order
# （patch_3.py --verify 会重新读 spec 并断言这张表没过期）
P3_ORDER = ('Protocol', 'SessionKey', 'ServerTimeTicks', 'ServerNotification',
            'RequestId', 'ReceiveTick', 'EchoSendTick')

P3_SWITCH_FILE = 'cn_3.txt'
P3_TICKS_FILE = 'cn_3_ticks.txt'
# 开关查找顺序：bridge 所在目录 -> 线上 tools/ -> 线上 bapatch/
P3_FALLBACK_DIRS = ('/www/wwwroot/bapatch/tools', '/www/wwwroot/bapatch')
P3_DEFAULT_ACCOUNT = 10015354380
P3_EPOCH = _p3dt.datetime(1, 1, 1)


# ---------------------------------------------------------------- 开关 / 小工具
def p3_dirs():
    """开关文件的候选目录（有序）。"""
    out = []
    try:
        out.append(_p3os.path.dirname(_p3os.path.abspath(__file__)))
    except Exception:
        pass
    for d in P3_FALLBACK_DIRS:
        if d not in out:
            out.append(d)
    return out


def p3_read_file(fn, base=None):
    """读一个小开关文件 -> (路径, 内容)。找不到 -> (None, None)。"""
    dirs = ([base] if base else []) + p3_dirs()
    for d in dirs:
        if not d:
            continue
        p = _p3os.path.join(d, fn)
        try:
            with open(p, 'r') as fh:
                return p, fh.read().strip()
        except Exception:
            continue
    return None, None


def p3_switch_on(base=None):
    """协议 3 是否启用。缺失 / 读不到 / 内容不是真值 -> False（fail-safe）。"""
    _p, v = p3_read_file(P3_SWITCH_FILE, base)
    if v is None:
        return False
    return v.strip().lower() in ('1', 'on', 'true', 'yes')


def p3_wants(num, base=None):
    """协议号是 3 且开关打开 —— 给 bridge 的分发处做前置判断（不解密、不构包）。"""
    try:
        n = int(num)
    except Exception:
        return False
    return n == P3_PROTOCOL and p3_switch_on(base)


def p3_num(num=None, name=None):
    """协议号判定：Hash>>32 命中 3，或者外层 protocol 就是 NetworkTime_Sync。"""
    try:
        n = int(num)
    except Exception:
        n = None
    if n == P3_PROTOCOL:
        return P3_PROTOCOL
    if isinstance(name, str) and name == P3_NAME:
        return P3_PROTOCOL
    return None


def p3_name_hit(name):
    """廉价预判（不碰文件系统）：外层协议名就是 NetworkTime_Sync？

    HOOK-E 在**每个**请求上都会经过，所以先用一次字符串比较挡住其它协议，
    连开关文件都不读；只有命中协议 3 才去碰盘。
    """
    return isinstance(name, str) and name == P3_NAME


def p3_ticks_mode(base=None):
    _p, v = p3_read_file(P3_TICKS_FILE, base)
    if v and v.strip().lower() == 'utc':
        return 'utc'
    return 'local'


def p3_ticks(dt=None, mode='local'):
    """.NET ticks（100ns，自 0001-01-01）。整数运算，不经 float。"""
    if dt is None:
        if str(mode).lower() == 'utc':
            dt = _p3dt.datetime.now(_p3dt.timezone.utc).replace(tzinfo=None)
        else:
            dt = _p3dt.datetime.now()
    elif getattr(dt, 'tzinfo', None) is not None:
        if str(mode).lower() == 'utc':
            dt = dt.astimezone(_p3dt.timezone.utc).replace(tzinfo=None)
        else:
            dt = dt.astimezone().replace(tzinfo=None)
    delta = dt - P3_EPOCH
    return (delta.days * 86400 + delta.seconds) * 10000000 + delta.microseconds * 10


def p3_now(mode='local'):
    if str(mode).lower() == 'utc':
        return _p3dt.datetime.now(_p3dt.timezone.utc).replace(tzinfo=None)
    return _p3dt.datetime.now()


# ---------------------------------------------------------------- 账号 / 令牌
def p3_session_from_frag(frag):
    """从客户端请求片段里取 SessionKey（官方就是原样回显它）。"""
    sid = mx = None
    if isinstance(frag, str) and frag:
        m = _p3re.search(r'"AccountServerId"\s*:\s*(\d+)', frag)
        if m:
            sid = int(m.group(1))
        m = _p3re.search(r'"MxToken"\s*:\s*"([^"]{8,200})"', frag)
        if m:
            mx = m.group(1)
    return sid, mx


def p3_account_id(rec=None, frag=None):
    sid, _mx = p3_session_from_frag(frag)
    if sid:
        return int(sid)
    try:
        sess = globals().get('SESSION')
        sk = getattr(sess, 'session_key', None) or {}
        if isinstance(sk, dict) and sk.get('AccountServerId'):
            return int(sk['AccountServerId'])
        aid = getattr(sess, 'account_id', None)
        if aid:
            return int(aid)
    except Exception:
        pass
    if isinstance(rec, dict):
        for k in ('acct_server_id', 'req_AccountServerId'):
            v = rec.get(k)
            if v:
                try:
                    return int(v)
                except Exception:
                    pass
    return P3_DEFAULT_ACCOUNT


def p3_mxtoken(account_id):
    """由账号派生 64 字符 base64 MxToken（sha384 48 字节，与 gen_common.Account 同一公式）。"""
    raw = _p3hashlib.sha384(
        ('ba-private-server:%d' % int(account_id)).encode('utf-8')).digest()
    return _p3base64.b64encode(raw).decode('ascii')


def p3_requestid(rec=None):
    """外层 requestid / 内层 RequestId 用同一个值（官方逐字节相同）。"""
    rid = None
    fn = globals().get('pick_requestid')
    if callable(fn):
        try:
            rid = fn(rec if isinstance(rec, dict) else {})
        except Exception:
            rid = None
    if not rid:
        rid = str(_p3uuid.uuid4())
    return rid


# ---------------------------------------------------------------- 载荷
def p3_build(account_id, mxtoken, request_id, ticks, server_ticks=None):
    """7 键官方结构。

    ReceiveTick == EchoSendTick == ticks  —— 红线：绝不能是 0（客户端靠它算时钟偏移）。
    ServerTimeTicks = server_ticks（不给就同 ticks）。官方 ServerTimeTicks 比两个 tick 大
    12 ticks（1.2 µs）：那是「收到请求」和「组包发出」两次取时之差，运行时按两次采样给。
    """
    ticks = int(ticks)
    stt = ticks if server_ticks is None else int(server_ticks)
    if stt < ticks:
        stt = ticks
    obj = {
        'Protocol': P3_PROTOCOL,
        'SessionKey': {'AccountServerId': int(account_id), 'MxToken': mxtoken},
        'ServerTimeTicks': stt,
        'ServerNotification': 0,
        'RequestId': request_id,
        'ReceiveTick': ticks,
        'EchoSendTick': ticks,
    }
    return dict((k, obj[k]) for k in P3_ORDER if k in obj)


def p3_inner_len(obj):
    return len(json_dumps_compact(obj))


def json_dumps_compact(obj):
    import json as _j
    return _j.dumps(obj, ensure_ascii=False, separators=(',', ':'))


def p3_route(rec, name=None, num=None, frag=None, send=None, base=None, hook=None):
    """协议 3 的接管线。返回 (200, wire, ctype)；不管 -> None（交回原有兜底）。

    send 必须注入（bridge 传 cn_wire.wrap_response，测试可传替身）：
        send(protocol_name, inner_obj, requestid) -> (wire, plain, key)
    任何异常都往上抛，由 hook 的 try/except 兜住并记 rec['p3_err']。
    """
    proto = p3_num(num, name)
    if proto is None:
        return None
    if not p3_switch_on(base):
        if isinstance(rec, dict):
            rec['p3_off'] = proto
        return None
    if send is None:
        return None

    if isinstance(rec, dict) and isinstance(frag, str) and frag:
        rec['p3_frag_head'] = frag[:200]

    sid_frag, mx_frag = p3_session_from_frag(frag)
    account_id = p3_account_id(rec, frag)
    mxtoken = mx_frag or p3_mxtoken(account_id)
    mode = p3_ticks_mode(base)
    ticks = p3_ticks(p3_now(mode), mode)                 # 收到请求那一刻 -> 两个 tick
    server_ticks = p3_ticks(p3_now(mode), mode)          # 组包那一刻 -> ServerTimeTicks
    rid = p3_requestid(rec)

    obj = p3_build(account_id, mxtoken, rid, ticks, server_ticks=server_ticks)
    wire, plain, key = send(P3_NAME, obj, rid)

    if isinstance(rec, dict):
        rec['gen_kind'] = 'networktime-3'
        rec['p3_hook'] = hook or '?'
        rec['p3_proto'] = proto
        rec['p3_name'] = P3_NAME
        rec['p3_account_id'] = account_id
        rec['p3_session_from_request'] = bool(sid_frag or mx_frag)
        rec['p3_ticks_mode'] = mode
        rec['p3_ticks'] = int(ticks)
        rec['p3_server_ticks'] = obj['ServerTimeTicks']
        rec['p3_server_tick_delta'] = obj['ServerTimeTicks'] - obj['ReceiveTick']
        rec['p3_receive_tick'] = obj['ReceiveTick']
        rec['p3_echo_tick'] = obj['EchoSendTick']
        rec['p3_tick_delta'] = obj['EchoSendTick'] - obj['ReceiveTick']
        rec['p3_requestid_echo'] = (obj.get('RequestId') == rid)
        rec['p3_keys'] = len(obj)
        rec['enc_requestid'] = rid
        rec['enc_inner_keys'] = len(obj)
        rec['enc_plain_len'] = len(plain)
        rec['enc_body_len'] = len(wire)
        rec['_send_opts'] = {'ctype': 'text/plain; charset=utf-8', 'close': True}
    return 200, wire, 'text/plain; charset=utf-8'
'''

# ---------------------------------------------------------------- 三个 hook 的代码
HOOK_E_BODY = """        # >>> BAPATCH-P3-HOOK-E %(ver)s BEGIN >>>
        # protocol 3 (NetworkTime_Sync)：在 exp / path A 之前按协议名最早接管，
        # 保证 ReceiveTick / EchoSendTick 一定是真时间戳（红线：不能是通用空构造里的 0）。
        # 先 p3_name_hit（一次字符串比较）挡住别的协议，命中才读开关文件。
        # 开关关 / 生成器异常 -> 原路返回，后面的 path D / generic 兜底完全不变。
        try:
            if p3_name_hit(name) and p3_wants(%(proto)d):
                _p3e = p3_route(rec, name, %(proto)d,
                                self._cn_decode_any(packet_b64, proto_str),
                                cn_wire.wrap_response, hook='HOOK-E')
                if _p3e is not None:
                    return _p3e
        except Exception as _p3e_err:
            rec['p3_err'] = 'HOOK-E ' + repr(_p3e_err)
        # <<< BAPATCH-P3-HOOK-E %(ver)s END <<<
"""

HOOK_D_BODY = """        # >>> BAPATCH-P3-HOOK-D %(ver)s BEGIN >>>
        # protocol 3：path D 会把它回成 {"Protocol":3} 单键（无 tick），先在这里接管。
        try:
            if p3_wants(proto_int):
                _p3d = p3_route(rec, name, proto_int,
                                self._cn_decode_any(packet_b64, proto_str),
                                cn_wire.wrap_response, hook='HOOK-D')
                if _p3d is not None:
                    return _p3d
        except Exception as _p3d_err:
            rec['p3_err'] = 'HOOK-D ' + repr(_p3d_err)
        # <<< BAPATCH-P3-HOOK-D %(ver)s END <<<
"""

HOOK_G_BODY = """        # >>> BAPATCH-P3-HOOK-G %(ver)s BEGIN >>>
        # protocol 3：泛接口兜底（min+base 假键）之前接管，回官方 7 键 / 620 B。
        # frag 用 locals().get()：万一别的版本里这个局部变量改名也不至于 NameError。
        try:
            _p3g = p3_route(rec, name, num, locals().get('frag'),
                            cn_wire.wrap_response, hook='HOOK-G')
            if _p3g is not None:
                return _p3g
        except Exception as _p3g_err:
            rec['p3_err'] = 'HOOK-G ' + repr(_p3g_err)
        # <<< BAPATCH-P3-HOOK-G %(ver)s END <<<
"""

HOOK_BODIES = {UNIT_HOOK_E: HOOK_E_BODY, UNIT_HOOK_D: HOOK_D_BODY, UNIT_HOOK_G: HOOK_G_BODY}


# ================================================================ 文本工具
def sha256_text(s):
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def read_text(path):
    with io.open(path, 'r', encoding='utf-8', newline='') as fh:
        return fh.read()


def write_text(path, text):
    with io.open(path, 'w', encoding='utf-8', newline='') as fh:
        fh.write(text)


def mark_begin(unit):
    return '# >>> BAPATCH-P3-%s %s BEGIN' % (unit, VER)


def mark_end(unit):
    return '# <<< BAPATCH-P3-%s %s END <<<' % (unit, VER)


def payload_body():
    """内嵌载荷正文（唯一真源 = 本文件里的 P3_PAYLOAD_SRC）。"""
    return P3_PAYLOAD_SRC.replace('\r\n', '\n').rstrip('\n') + '\n'


def unit_block(unit, body=None):
    """整块文本（含 BEGIN/END 标记）。PAYLOAD 顶格，三个 hook 按函数体缩进。"""
    if unit == UNIT_PAYLOAD:
        src = payload_body() if body is None else body
        head = ('%s >>> (deploy/patch_3.py 内嵌 P3_PAYLOAD_SRC，sha256=%s) >>>'
                % (mark_begin(UNIT_PAYLOAD), sha256_text(src)))
        return head + '\n' + src + mark_end(UNIT_PAYLOAD) + '\n'
    return HOOK_BODIES[unit] % {'ver': VER, 'proto': PROTO}


def find_block(text, unit):
    """-> (start_line, end_line) 含 END 行；未找到 -> None。忽略缩进。"""
    lines = text.split('\n')
    b = e = None
    for i, ln in enumerate(lines):
        s = ln.lstrip()
        if b is None:
            if s.startswith(mark_begin(unit)):
                b = i
        elif s.startswith(mark_end(unit)):
            e = i
            break
    if b is None or e is None or e < b:
        return None
    return b, e


def count_marks(text, unit):
    lines = text.split('\n')
    b = sum(1 for ln in lines if ln.lstrip().startswith(mark_begin(unit)))
    e = sum(1 for ln in lines if ln.lstrip().startswith(mark_end(unit)))
    return b, e


def extract_block_body(text, unit):
    rng = find_block(text, unit)
    if not rng:
        return None
    lines = text.split('\n')
    return '\n'.join(lines[rng[0] + 1:rng[1]]) + '\n'


def is_patched(text):
    return count_marks(text, UNIT_PAYLOAD)[0] == 1


def anchor_hits(text, anchor):
    """anchor 在 text 里的出现次数与首次行号（1-based）。"""
    n = text.count(anchor)
    if n == 0:
        return 0, None
    return n, text[:text.index(anchor)].count('\n') + 1


def anchor_text(unit):
    a = ANCHORS[unit]
    return a[0] if isinstance(a, tuple) else a


def anchor_pos(text, anchor, unit):
    """返回插入点。anchor 可以是 (文本, 'before'|'after')。锚点不唯一直接退出。"""
    mode = 'before'
    if isinstance(anchor, tuple):
        anchor, mode = anchor
    n = text.count(anchor)
    if n != 1:
        raise SystemExit('锚点不唯一：[%s] 出现 %d 次（%r）—— 拒绝动这个文件'
                         % (unit, n, anchor.strip().split('\n')[0][:70]))
    i = text.index(anchor)
    return i + len(anchor) if mode == 'after' else i


def compile_ok(text, path):
    try:
        compile(text, path, 'exec')
        return True, ''
    except SyntaxError as e:
        return False, '%s line %s: %s' % (type(e).__name__, e.lineno, e.msg)


def mask_payload(text):
    """给 diff 用：把 PAYLOAD 正文压成一行占位，避免 200+ 行噪声。"""
    rng = find_block(text, UNIT_PAYLOAD)
    if not rng:
        return text
    lines = text.split('\n')
    n = rng[1] - rng[0] - 1
    ph = '# ...[%d 行载荷生成器原样内嵌自 patch_3.py 的 P3_PAYLOAD_SRC，--full-diff 查看]...' % n
    return '\n'.join(lines[:rng[0] + 1] + [ph] + lines[rng[1]:])


# ================================================================ 打 / 摘
def build_patched(orig, only=None):
    text = orig
    acts = []
    for unit in UNITS:
        if only and unit not in only:
            continue
        blk = unit_block(unit)
        nlines = len(blk.rstrip('\n').split('\n'))
        rng = find_block(text, unit)
        if rng:
            lines = text.split('\n')
            text = '\n'.join(lines[:rng[0]] + blk.rstrip('\n').split('\n') + lines[rng[1] + 1:])
            acts.append('%s: 替换已有块（旧 %d 行 -> 新 %d 行，幂等）'
                        % (unit, rng[1] - rng[0] + 1, nlines))
            continue
        anchor_pos(text, ANCHORS[unit], unit)          # 唯一性检查（不唯一直接退出）
        at = anchor_text(unit)
        line_no = orig[:orig.index(at)].count('\n') + 1   # 报原文件行号，便于 ops 对照
        i = text.index(at)
        if isinstance(ANCHORS[unit], tuple) and ANCHORS[unit][1] == 'after':
            i += len(at)
        text = text[:i] + blk + text[i:]
        acts.append('%s: 在原文件第 %d 行%s插入 %d 行（锚点 %r）'
                    % (unit, line_no,
                       '之后' if (isinstance(ANCHORS[unit], tuple)
                                  and ANCHORS[unit][1] == 'after') else '之前',
                       nlines, at.strip().split('\n')[0][:56]))
    return text, acts


def build_removed(orig, only=None):
    text = orig
    acts = []
    for unit in UNITS:
        if only and unit not in only:
            continue
        rng = find_block(text, unit)
        if not rng:
            acts.append('%s: 本来就没有' % unit)
            continue
        lines = text.split('\n')
        text = '\n'.join(lines[:rng[0]] + lines[rng[1] + 1:])
        acts.append('%s: 摘掉第 %d-%d 行（%d 行）'
                    % (unit, rng[0] + 1, rng[1] + 1, rng[1] - rng[0] + 1))
    return text, acts


def backup(src):
    bak = '%s.p3.bak.%s' % (src, time.strftime('%Y%m%d-%H%M%S'))
    shutil.copy2(src, bak)
    return bak


def find_backups(src):
    d = os.path.dirname(os.path.abspath(src))
    base = os.path.basename(src) + '.p3.bak.'
    out = []
    try:
        for fn in os.listdir(d):
            if fn.startswith(base):
                out.append(os.path.join(d, fn))
    except Exception:
        pass
    return sorted(out)


# ================================================================ 开关文件
def switch_dir_for(src, override=None):
    if override:
        return override
    if os.path.abspath(src) == os.path.abspath(LIVE_SRC):
        return DEFAULT_SWITCH_DIR
    return os.path.dirname(os.path.abspath(src))


def apply_switches(src, val, override=None):
    d = switch_dir_for(src, override)
    p = os.path.join(d, SWITCH_FILE)
    exists = os.path.exists(p)
    if val == 'keep' and exists:
        with io.open(p, 'r') as fh:
            return '%s=%r（保留，未改动）' % (p, fh.read().strip())
    want = '1' if val == 'keep' else val
    if not os.path.isdir(d):
        return '%s（目录不存在，未创建 —— 开关按「关」处理）' % p
    with io.open(p, 'w', newline='\n') as fh:
        fh.write(want + '\n')
    return '%s=%s（%s）' % (p, want, '保留文件' if exists else '新建')


# ================================================================ 生成器口径比对（gen3）
def _load_py(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_embedded_ns(src_text):
    body = extract_block_body(src_text, UNIT_PAYLOAD)
    if body is None:
        return None, '内嵌 PAYLOAD 块不存在'
    ns = {'__name__': 'embedded_p3_payload',
          '__file__': os.path.join(HERE, 'patch_3.py')}
    try:
        exec(compile(body, '<embedded p3 payload>', 'exec'), ns)
    except Exception as e:
        return None, '内嵌 PAYLOAD 无法 exec: %r' % (e,)
    return ns, ''


def spec_order3():
    if not os.path.isfile(SPEC_PATH):
        return None
    try:
        with io.open(SPEC_PATH, 'r', encoding='utf-8') as fh:
            raw = json.load(fh)
        return list(raw['protocols']['3'].get('top_key_order') or [])
    except Exception:
        return None


def official_inner3():
    if not os.path.isfile(OFFICIAL3):
        return None
    try:
        with io.open(OFFICIAL3, 'r', encoding='utf-8') as fh:
            return json.load(fh)
    except Exception:
        return None


def compact(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(',', ':'))


def pkcs7_len(plain):
    """cn_wire 容器长度：base64( pkcs7(plain) + key(32) )。密文长度只由 pkcs7 决定。"""
    b = len(plain.encode('utf-8'))
    padded = b + (16 - b % 16)
    raw = padded + 32
    return 4 * ((raw + 2) // 3)


def wrap_len_of(inner_obj, rid, name=PROTO_NAME):
    plain = compact({'protocol': name, 'packet': compact(inner_obj), 'requestid': rid})
    return pkcs7_len(plain), plain


# ================================================================ 自检
def verify(src, want_sha=None, verbose=True):
    rep = []
    state = {'ok': True}

    def add(good, text):
        state['ok'] = state['ok'] and bool(good)
        rep.append(('PASS  ' if good else 'FAIL  ') + text)

    def info(text):
        rep.append('INFO  ' + text)

    if not os.path.isfile(src):
        return False, ['FAIL  src 不存在: %s' % src], state

    raw = open(src, 'rb').read()
    sha = hashlib.sha256(raw).hexdigest()
    text = read_text(src)
    patched = is_patched(text)
    info('src = %s  (%d 字节 / %d 行 / sha256 %s)'
         % (src, len(raw), text.count('\n'), sha[:16]))
    info('状态 = %s' % ('已打补丁（校验补丁后不变量）' if patched else '未打补丁（校验基线+锚点）'))

    # ---- 1. 语法
    ok, err = compile_ok(text, src)
    add(ok, 'python 语法检查 compile() %s' % ('' if ok else '-> ' + err))

    # ---- 2. 基线指纹 / 锚点
    if not patched:
        add(len(raw) == BASELINE_SIZE, '基线大小 == %d（实测 %d）' % (BASELINE_SIZE, len(raw)))
        add(sha == (want_sha or BASELINE_SHA256),
            '基线 sha256 == %s（实测 %s）'
            % ((want_sha or BASELINE_SHA256)[:16], sha[:16]))
        for unit in (UNIT_HOOK_E, UNIT_HOOK_D, UNIT_HOOK_G, UNIT_PAYLOAD):
            n, line = anchor_hits(text, anchor_text(unit))
            add(n == 1, '锚点 %s 唯一命中 %d 次（第 %s 行，%s）'
                % (unit, n, line, ANCHOR_DESC[unit]))
        add('BAPATCH-P3' not in text, '基线里没有 BAPATCH-P3 残留标记')
    else:
        for unit in UNITS:
            b, e = count_marks(text, unit)
            add(b == 1 and e == 1 and find_block(text, unit) is not None,
                '%s 标记成对、各 1 处（BEGIN %d / END %d）' % (unit, b, e))
        # 内嵌载荷 == 本文件里的真源（逐字节）
        body = extract_block_body(text, UNIT_PAYLOAD)
        add(body == payload_body(),
            '内嵌 PAYLOAD 逐字节 == patch_3.py 的 P3_PAYLOAD_SRC（sha256 %s / %s）'
            % ((sha256_text(body)[:16] if body else '-'), sha256_text(payload_body())[:16]))
        head_line = ''
        for ln in text.split('\n'):
            if ln.lstrip().startswith(mark_begin(UNIT_PAYLOAD)):
                head_line = ln
                break
        m = re.search(r'sha256=([0-9a-f]{64})', head_line)
        add(bool(m) and m.group(1) == sha256_text(payload_body()),
            'PAYLOAD 标记里记的 sha256 与真源一致（%s）' % (m.group(1)[:16] if m else '缺'))
        for unit in (UNIT_HOOK_E, UNIT_HOOK_D, UNIT_HOOK_G):
            blk = extract_block_body(text, unit)
            want = '\n'.join(unit_block(unit).rstrip('\n').split('\n')[1:-1]) + '\n'
            add(blk == want, '%s 代码块逐字节 == patch_3.py 里生成的那份' % unit)
        # 位置关系
        gi = text.find(mark_begin(UNIT_HOOK_G))
        g_def = text.find('def _generic_protocol_response')
        g_next = text.find('def _cn_send_envelope')
        add(g_def >= 0 and g_next > g_def and g_def < gi < g_next,
            'HOOK-G 落在 _generic_protocol_response() 内（def@%d < hook@%d < 下一函数@%d）'
            % (g_def, gi, g_next))
        g_anchor = text.find('        if num == 90004:')
        add(0 < gi < g_anchor, 'HOOK-G 在 `if num == 90004:` 之前（hook@%d < anchor@%d）'
            % (gi, g_anchor))
        di = text.find(mark_begin(UNIT_HOOK_D))
        d_anchor = text.find('        if proto_int:')
        add(0 <= di < d_anchor, 'HOOK-D 在 path D 的 `if proto_int:` 之前（hook@%d < anchor@%d）'
            % (di, d_anchor))
        ei = text.find(mark_begin(UNIT_HOOK_E))
        e_anchor = text.find('        if exp == \'experror\':')
        name_anchor = text.find("        rec['protocol_name'] = name")
        add(0 <= name_anchor < ei < e_anchor,
            'HOOK-E 在协议名解析之后、exp 分支之前（name@%d < hook@%d < exp@%d）'
            % (name_anchor, ei, e_anchor))
        pi = text.find(mark_begin(UNIT_PAYLOAD))
        p_anchor = text.find(ANCHOR_PAYLOAD)
        add(0 < pi < p_anchor, "PAYLOAD 在 `if __name__ == '__main__':` 之前（payload@%d < anchor@%d）"
            % (pi, p_anchor))
        # 老补丁没被破坏
        for other in ('BAPATCH-SIMPLE-HOOK-G', 'BAPATCH-SIMPLE-HOOK-D', 'BAPATCH-SIMPLE-PAYLOAD'):
            add(text.count(other + ' %s BEGIN' % ('v1',)) == 1,
                '既有补丁 %s 仍在（未被动过）' % other)

    # ---- 3. 内嵌载荷行为
    ns, nerr = load_embedded_ns(text) if patched else (None, '未打补丁')
    if patched:
        add(ns is not None, '内嵌载荷可 exec%s' % ('' if ns else ' -> ' + nerr))
    if ns:
        tmp = tempfile.mkdtemp(prefix='p3sw_')
        try:
            add(ns['p3_switch_on'](tmp) is False, '开关文件缺失 -> 判定「关」（fail-safe）')
            with io.open(os.path.join(tmp, SWITCH_FILE), 'w', newline='\n') as fh:
                fh.write('1\n')
            add(ns['p3_switch_on'](tmp) is True and ns['p3_wants'](3, tmp) is True,
                'cn_3.txt=1 -> 协议 3「开」')
            add(ns['p3_wants'](4000, tmp) is False and ns['p3_wants'](1017, tmp) is False,
                '开关打开也不会接管别的协议（4000 / 1017 -> False）')
            add(ns['p3_wants'](None, tmp) is False, 'p3_wants(None) -> False（不会 TypeError）')
            add(ns['p3_name_hit'](PROTO_NAME) is True
                and ns['p3_name_hit']('Item_List') is False
                and ns['p3_name_hit'](None) is False,
                'p3_name_hit 只认 NetworkTime_Sync（HOOK-E 每个请求都过，必须先挡一下）')
            with io.open(os.path.join(tmp, SWITCH_FILE), 'w', newline='\n') as fh:
                fh.write('0\n')
            add(ns['p3_switch_on'](tmp) is False, 'cn_3.txt=0 -> 「关」')
            with io.open(os.path.join(tmp, SWITCH_FILE), 'w', newline='\n') as fh:
                fh.write('1\n')

            # 7 键 / tick 相等 / RequestId 回显
            tk = 639304002554622693
            obj = ns['p3_build'](10015354380, 'M' * 64, 'R' * 36, tk)
            add(list(obj.keys()) == list(ns['P3_ORDER']),
                '内层键序 == P3_ORDER（%d 键）' % len(obj))
            add(obj['ReceiveTick'] == obj['EchoSendTick'] == tk,
                'ReceiveTick == EchoSendTick == %d（红线：非 0 且相等）' % tk)
            add(obj['ServerTimeTicks'] == tk,
                'ServerTimeTicks 缺省 == 两个 tick（同一时刻只采一次时不自相矛盾）')
            add(obj['RequestId'] == 'R' * 36, '内层 RequestId 用注入值（== 外层 requestid）')
            obj2 = ns['p3_build'](10015354380, 'M' * 64, 'R' * 36, tk, server_ticks=tk + 12)
            add(obj2['ServerTimeTicks'] == tk + 12 and obj2['ReceiveTick'] == obj2['EchoSendTick'] == tk,
                'ServerTimeTicks 可单独给（+12 ticks，复现官方两次取时）且不动两个 tick')

            # 请求 SessionKey 回显 / 缺省派生
            frag = ('{"Protocol":3,"Resendable":true,"Hash":12884901893,"IsTest":false,'
                    '"SessionKey":{"AccountServerId":10015354380,"MxToken":"%s"},'
                    '"AccountId":10015354380,"OSType":2}' % ('Vji5A/Cy6X2enQZKeYgrjxAC8MoRDO'
                                                             'CT2Tb1SW13PcZTq2cnyCPPdd81pGbzYBKA'))
            sid, mx = ns['p3_session_from_frag'](frag)
            add(sid == 10015354380 and mx == 'Vji5A/Cy6X2enQZKeYgrjxAC8MoRDOCT2Tb1SW13PcZTq2cnyCPPdd81pGbzYBKA',
                '从请求片段取到 SessionKey（AccountServerId / MxToken 各 %s / %d 字符）'
                % (sid, len(mx or '')))
            mt = ns['p3_mxtoken'](10015354380)
            add(isinstance(mt, str) and len(mt) == 64 and mt == ns['p3_mxtoken'](10015354380),
                '无请求 SessionKey 时 MxToken 由账号派生（%d 字符 base64，可复现）' % len(mt))

            # 620 B 断言（官方内层 314 B）
            off = official_inner3()
            o_inner = (off or {}).get('inner') or {}
            if off is not None:
                rid = o_inner.get('RequestId') or 'd1d5579c-9c2b-44e6-a496-c66d4ccca10c'
                rebuilt = ns['p3_build'](o_inner['SessionKey']['AccountServerId'],
                                         o_inner['SessionKey']['MxToken'], rid,
                                         o_inner['ReceiveTick'],
                                         server_ticks=o_inner['ServerTimeTicks'])
                add(compact(rebuilt) == compact(o_inner),
                    '用官方 SessionKey/tick 重建内层 == 官方 inner（逐字节，%d B）'
                    % len(compact(rebuilt)))
                add(o_inner['ReceiveTick'] == o_inner['EchoSendTick'],
                    '官方 inner 的 ReceiveTick == EchoSendTick（%d）' % o_inner['ReceiveTick'])
                add(o_inner['ServerTimeTicks'] - o_inner['ReceiveTick'] == 12,
                    '官方 ServerTimeTicks 比两个 tick 大 %d ticks'
                    % (o_inner['ServerTimeTicks'] - o_inner['ReceiveTick']))
                n, plain = wrap_len_of(rebuilt, rid)
                add(n == 620, 'cn_wire 容器长度 == %d（官方 resp_bytes=%s，plain %d B）'
                    % (n, off.get('meta', {}).get('resp_bytes'), len(plain)))
                add(off.get('meta', {}).get('resp_bytes') == 620,
                    '抓包原文 resp_bytes == 620（对照值）')
                add(json.loads(plain)['protocol'] == PROTO_NAME,
                    '外层 protocol == %r' % json.loads(plain)['protocol'])
            else:
                info('官方 04_3 抓包不存在，跳过逐字节比对: %s' % OFFICIAL3)

            # 真生成器 gen3.build_3 逐字节比对
            if os.path.isfile(GEN3_PATH) and os.path.isfile(GEN_COMMON_PATH):
                try:
                    G = _load_py(GEN_COMMON_PATH, 'p3gen_common')
                    G3 = _load_py(GEN3_PATH, 'p3gen3')
                    rid2 = 'd1d5579c-9c2b-44e6-a496-c66d4ccca10c'
                    bad = []
                    cases = [
                        (10015354380, 'M' * 64, 639304002554622693, None),
                        (99990000001, ns['p3_mxtoken'](99990000001), 1, None),
                        (10015354380, ns['p3_mxtoken'](10015354380), 639304002559071160, None),
                        (1, 'x' * 64, 639304002554622705, 639304002554622717),
                        (10015354380, 'M' * 64, 639304002554622693, 639304002554622693),
                    ]
                    for aid, mx2, rt2, st2 in cases:
                        stt2 = rt2 if st2 is None else st2
                        # gen3 口径：Account.ticks = ServerTimeTicks，recv/echo 单独给
                        acct = G.Account(aid, mx2, rid2, G.dt_from_ticks(stt2), ticks=stt2)
                        want = G3.build_3(acct, recv_tick=rt2, echo_tick=rt2)
                        got = ns['p3_build'](aid, mx2, rid2, rt2, server_ticks=stt2)
                        if compact(want) != compact(got):
                            bad.append((aid, rt2, stt2))
                    add(not bad, '内嵌生成器 == 真生成器 gen3.build_3()（%d 组输入逐字节相同）%s'
                        % (len(cases), '' if not bad else ' -> 不一致 %r' % (bad,)))

                    if off is not None:
                        # 官方输入回灌真生成器（== gen3 --verify-official 的口径）
                        acct_o = G.Account(o_inner['SessionKey']['AccountServerId'],
                                           o_inner['SessionKey']['MxToken'],
                                           o_inner.get('RequestId'),
                                           G.dt_from_ticks(o_inner['ServerTimeTicks']),
                                           ticks=o_inner['ServerTimeTicks'])
                        want_o = G3.build_3(acct_o, recv_tick=o_inner['ReceiveTick'],
                                            echo_tick=o_inner['EchoSendTick'])
                        add(compact(want_o) == compact(o_inner),
                            'gen3.build_3 用官方输入回灌 == 官方 inner（--verify-official 口径）')
                        add(compact(want_o) == compact(rebuilt),
                            '内嵌生成器 == gen3.build_3（官方输入，含独立 ServerTimeTicks）')
                    info('gen3.build_3 内层 %d B（官方 %d B）'
                         % (len(compact(rebuilt)) if off is not None else -1,
                            len(compact(o_inner)) if off is not None else -1))
                except Exception as e:
                    add(False, 'gen3 比对失败: %r' % (e,))
            else:
                info('gen3.py / gen_common.py 不在本机 %s，跳过真生成器比对' % HERE)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # ---- 4. spec 键序
    so = spec_order3()
    if so is None:
        info('official_spec.json 不可读，跳过键序比对')
    elif ns is None:
        info('未打补丁，跳过 P3_ORDER 比对（spec 键序 = %r）' % (list(so),))
    else:
        add(list(ns['P3_ORDER']) == list(so),
            'P3_ORDER == official_spec.json protocols["3"].top_key_order (%r)' % (list(so),))

    if verbose:
        for line in rep:
            print('  ' + line)
    return state['ok'], rep, state


# ================================================================ 分发证明（本地仿真）
RIG_STUBS = {}

RIG_STUBS['cn_wire.py'] = r'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cn_wire 仿真替身：容器/编码/长度与真 cn_wire 完全一致，只有分组加密本体换成 0 字节桩
（本机没有 cryptography）。密文长度只由 pkcs7 决定 -> len(wire) 与真机等长；
plaintext 原样返回，测试直接断言外层 protocol / 内层 ticks，不需要解密。"""
import base64
import json
import os
import uuid

IV_FIXED = b'JOSYdf8ys97uhFYS'
KEY_LEN = 32
BLOCK = 16
CALLS = []


def pkcs7_pad(data, bs=BLOCK):
    n = bs - (len(data) % bs)
    return data + bytes([n]) * n


def build_plaintext(protocol_name, inner_obj, requestid=None):
    requestid = requestid or str(uuid.uuid4())
    plain = json.dumps({"protocol": protocol_name,
                        "packet": json.dumps(inner_obj, ensure_ascii=False, separators=(',', ':')),
                        "requestid": requestid},
                       ensure_ascii=False, separators=(',', ':'))
    return plain, requestid


def wrap_response(protocol_name, inner_obj, requestid=None, key=None):
    key = key or os.urandom(KEY_LEN)
    if len(key) != KEY_LEN:
        raise ValueError('bad key length %d' % len(key))
    plain, requestid = build_plaintext(protocol_name, inner_obj, requestid)
    ct = bytes(len(pkcs7_pad(plain.encode('utf-8'))))
    wire = base64.b64encode(ct + key)
    CALLS.append((wire, plain, key))
    return wire, plain, key


def unwrap_response(body):
    raise NotImplementedError('stub cannot decrypt (no cryptography locally)')
'''

RIG_STUBS['cn_cipher.py'] = r'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cn_cipher 仿真替身：容器与真机一致 base64([u32 len][gzip(fragment)])，AES 层换成明文直存。"""
import base64
import gzip
import struct

CALLS = []


def wrap_fragment(fragment_text):
    raw = fragment_text.encode('utf-8')
    return base64.b64encode(struct.pack('<I', len(raw)) + gzip.compress(raw)).decode()


def decode_packet(packet_b64, protocol_field=None):
    raw = base64.b64decode(packet_b64 + '=' * ((4 - len(packet_b64) % 4) % 4))
    if len(raw) < 6:
        raise ValueError('packet too short')
    declared = struct.unpack('<I', raw[:4])[0]
    inner = gzip.decompress(raw[4:])
    if declared != len(inner):
        raise ValueError('declared %d != actual %d' % (declared, len(inner)))
    text = inner.decode('utf-8', 'replace')
    CALLS.append((protocol_field, text))
    return {"fragment": text, "json": None, "iv": '00' * 16, "key": 'K' * 32,
            "inner_len": len(inner), "frag_len": len(inner)}


def build_inner(fragment_text, key=None, iv=None):
    return fragment_text.encode('utf-8')


def wrap_packet(inner):
    return base64.b64encode(struct.pack('<I', len(inner)) + gzip.compress(inner)).decode()
'''

RIG_STUBS['cn_inner.py'] = r'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cn_inner 仿真替身（只需 90004 分支用到的表）。"""
STATIC_OPEN_CONDITIONS = {}


def build(protocol=None):
    return {"Protocol": protocol}
'''

RIG_STUBS['cn_inner27.py'] = r'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cn_inner27 仿真替身。"""


def build(protocol=None):
    return {"Protocol": protocol}
'''

RIG_STUBS['cn_nick.py'] = r'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cn_nick 仿真替身：真机同签名（build_min_response 是 path D 的兜底）。"""


def build_min_response(protocol):
    return {"Protocol": int(protocol)}


def build_accountdb(nickname, **kw):
    return {"ServerId": 2, "Nickname": nickname}
'''


def b32md5(name):
    import base64
    import hashlib
    return base64.b32encode(hashlib.md5(name.encode('utf-16-le')).digest()).decode().rstrip('=')


def make_body(token, packet_b64):
    b = '----p3BOUNDARY'
    return ('--%s\r\nContent-Disposition: form-data; name="protocol"\r\n\r\n%s\r\n'
            '--%s\r\nContent-Disposition: form-data; name="packet"\r\n\r\n%s\r\n'
            '--%s--\r\n' % (b, token, b, packet_b64, b)).encode('utf-8')


def rig_fragment(account_id=10015354380,
                 mxtoken='<REDACTED_TOKEN>',
                 hash_val=(PROTO << 32) | 5, with_hash=True):
    frag = ('{"Protocol":3,"Resendable":true,')
    if with_hash:
        frag += '"Hash":%d,' % hash_val
    frag += ('"IsTest":false,"SessionKey":{"AccountServerId":%d,"MxToken":"%s"},'
             '"AccountId":%d,"OSType":2}' % (account_id, mxtoken, account_id))
    return frag


def build_rig(src_text, tmp):
    """把 bridge 副本 + 替身模块写进 tmp，返回副本路径。"""
    for fn, body in RIG_STUBS.items():
        write_text(os.path.join(tmp, fn), body)
    path = os.path.join(tmp, 'account_auth_probe.py')
    write_text(path, src_text)
    return path


def load_rig(path, tmp):
    if tmp not in sys.path:
        sys.path.insert(0, tmp)
    spec = importlib.util.spec_from_file_location('p3_rig_bridge', path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules['p3_rig_bridge'] = mod
    spec.loader.exec_module(mod)
    return mod


def _rig_call(mod, packet_b64, rec_extra=None, exp=''):
    """直接调 Handler._bridge()（HTTP 层不参与，只走分发）。"""
    mod.exp_flag = lambda: exp
    b = make_body(b32md5(PROTO_NAME), packet_b64)
    rec = {'t': '2026-11-17 00:00:00', 'from': '127.0.0.1', 'method': 'POST',
           'path': '/api/networktime/sync', 'mode': 'bridge', 'headers': {},
           'body_len': len(b)}
    if rec_extra:
        rec.update(rec_extra)
    try:
        mod.cn_wire.CALLS[:] = []
    except Exception:
        pass
    inst = object.__new__(mod.Handler)
    code, resp, ctype = mod.Handler._bridge(inst, b, rec)
    return code, resp, ctype, rec


def _packet_of(frag):
    import base64
    import gzip
    import struct
    raw = frag.encode('utf-8')
    return base64.b64encode(struct.pack('<I', len(raw)) + gzip.compress(raw)).decode()


def prove_dispatch(src_text, verbose=True):
    """在临时装置里跑四条场景，证明三层钩子都真的会被走到、且异常只降级不断连。"""
    rep = []
    state = {'ok': True}

    def add(good, text):
        state['ok'] = state['ok'] and bool(good)
        rep.append(('PASS  ' if good else 'FAIL  ') + text)

    def info(text):
        rep.append('INFO  ' + text)

    patched = is_patched(src_text)
    if not patched:
        return False, ['FAIL  这个 src 还没打补丁，--prove-dispatch 需要在 --apply 之后跑'], state
    legacy_text, _acts = build_removed(src_text)

    tmp = tempfile.mkdtemp(prefix='p3rig_')
    tmp2 = tempfile.mkdtemp(prefix='p3rig_legacy_')
    try:
        frag = rig_fragment()
        pkt = _packet_of(frag)

        # ---------- 场景 1：正常启动 -> HOOK-E（最早一层，按协议名接管）
        p1 = build_rig(src_text, tmp)
        m1 = load_rig(p1, tmp)
        write_text(os.path.join(tmp, SWITCH_FILE), '1\n')
        n = m1.load_names()
        code, resp, ctype, rec = _rig_call(m1, pkt)
        add(code == 200 and len(resp) == 620 and rec.get('p3_hook') == 'HOOK-E',
            'HOOK-E：exp 分支之前接管 -> %s B（%r）hook=%r，名字表 %d 项'
            % (len(resp), code, rec.get('p3_hook'), n))
        add(rec.get('protocol_name') == PROTO_NAME and rec.get('gen_kind') == 'networktime-3',
            'HOOK-E：protocol_name=%r / gen_kind=%r'
            % (rec.get('protocol_name'), rec.get('gen_kind')))
        _check_plain(m1, add, rec)

        # ---------- 场景 2：把 HOOK-E 摘掉（模拟更早的部署 / --only 回滚了 E）-> HOOK-D
        orig_route = m1.p3_route

        def route_no_e(rec=None, name=None, num=None, frag=None, send=None, base=None, hook=None):
            if hook == 'HOOK-E':
                return None                      # 假装 HOOK-E 不在
            return orig_route(rec, name, num, frag, send, base, hook)

        m1.p3_route = route_no_e
        try:
            code, resp, ctype, rec = _rig_call(m1, pkt,
                                               rec_extra={'req_Hash': (PROTO << 32) | 5})
            add(code == 200 and len(resp) == 620 and rec.get('p3_hook') == 'HOOK-D',
                'HOOK-D：path D 的 `if proto_int:` 之前接管 -> %s B（%r）hook=%r（HOOK-E 摘掉后）'
                % (len(resp), code, rec.get('p3_hook')))
            add(rec.get('gen_kind') == 'networktime-3',
                'HOOK-D：rec.gen_kind=%r（不再是 min-envelope 的 {"Protocol":3}）'
                % rec.get('gen_kind'))
            _check_plain(m1, add, rec)

            # ---------- 场景 2b：HOOK-E 摘掉 + req_Hash 也没有 -> 走泛接口 HOOK-G
            code, resp, ctype, rec = _rig_call(m1, pkt)
            add(code == 200 and len(resp) == 620 and rec.get('p3_hook') == 'HOOK-G',
                'HOOK-G：正常分发（无 req_Hash，HOOK-E 摘掉）-> %s B，hook=%r'
                % (len(resp), rec.get('p3_hook')))
        finally:
            m1.p3_route = orig_route

        # ---------- 场景 3：泛接口直调 -> HOOK-G（path D 之后的兜底）
        inst = object.__new__(m1.Handler)
        rec3 = {'t': 'x', 'from': '127.0.0.1', 'headers': {}}
        got = m1.Handler._generic_protocol_response(inst, b32md5(PROTO_NAME), pkt, rec3,
                                                    name=PROTO_NAME)
        add(got is not None and len(got[1]) == 620 and rec3.get('p3_hook') == 'HOOK-G',
            'HOOK-G：_generic_protocol_response() 里接管 -> %s B，hook=%r'
            % (len(got[1]) if got else -1, rec3.get('p3_hook')))
        add(rec3.get('gen_kind') == 'networktime-3' and rec3.get('p3_tick_delta') == 0,
            'HOOK-G：gen_kind=%r / tick_delta=%r' % (rec3.get('gen_kind'),
                                                     rec3.get('p3_tick_delta')))

        # ---------- 场景 4：生成器抛异常 -> 降级回原来的通用构造（不 500、不断连）
        orig_build = m1.p3_build

        def boom(*a, **kw):
            raise RuntimeError('injected generator failure')

        m1.p3_build = boom
        try:
            code4, resp4, ctype4, rec4 = _rig_call(m1, pkt)
        finally:
            m1.p3_build = orig_build
        legacy_len = _legacy_len(legacy_text, tmp2, pkt)
        add(code4 == 200 and len(resp4) == legacy_len,
            '异常隔离：生成器抛错 -> 仍是 %r / %d B（== 打补丁前的 %d B），没有 500'
            % (code4, len(resp4), legacy_len))
        add('p3_err' in rec4 and 'injected generator failure' in rec4.get('p3_err', ''),
            '异常隔离：rec.p3_err=%r（留痕，不会静默）' % rec4.get('p3_err'))

        # ---------- 场景 5：开关关掉 -> 与打补丁前逐字节一致
        sw = os.path.join(tmp, SWITCH_FILE)
        if os.path.exists(sw):
            os.remove(sw)
        code5, resp5, ctype5, rec5 = _rig_call(m1, pkt)
        add(code5 == 200 and len(resp5) == legacy_len,
            '开关缺失(=关)：回 %r / %d B == 打补丁前 %d B（行为完全回退）'
            % (code5, len(resp5), legacy_len))
        add(rec5.get('p3_off') == PROTO or rec5.get('p3_hook') is None,
            '开关缺失(=关)：rec.p3_off=%r（判定为关并留痕）' % rec5.get('p3_off'))
        if not os.path.exists(sw):
            write_text(sw, '1\n')

        # ---------- 场景 6：请求里没有 Hash（协议号只能靠协议名认）
        code6, resp6, ctype6, rec6 = _rig_call(m1, _packet_of(rig_fragment(with_hash=False)))
        add(code6 == 200 and len(resp6) == 620,
            '协议名兜底：请求片段没有 Hash 时仍回 %d B（p3_num 认 NetworkTime_Sync）' % len(resp6))
    finally:
        for d in (tmp, tmp2):
            shutil.rmtree(d, ignore_errors=True)

    if verbose:
        for line in rep:
            print('  ' + line)
    return state['ok'], rep, state


def _legacy_len(legacy_text, tmp2, packet_b64):
    """打补丁前的 bridge 对同一请求回多少字节（A/B 对照基线）。"""
    if not os.path.isdir(tmp2):
        os.makedirs(tmp2)
    p2 = build_rig(legacy_text, tmp2)
    m2 = load_rig(p2, tmp2)
    m2.load_names()
    code, resp, ctype, rec = _rig_call(m2, packet_b64)
    return len(resp)


def _check_plain(mod, add, rec):
    """校验最后一次 wrap_response 的 plaintext：外层 protocol + 内层两个 tick。"""
    calls = list(getattr(getattr(mod, 'cn_wire', None), 'CALLS', []))
    if not calls:
        add(False, 'cn_wire.wrap_response 没被调用')
        return
    _wire, plain, _key = calls[-1]
    outer = json.loads(plain)
    inner = json.loads(outer['packet'])
    add(outer['protocol'] == PROTO_NAME,
        '外层 protocol == %r' % outer['protocol'])
    add(inner.get('ReceiveTick') == inner.get('EchoSendTick') and inner.get('ReceiveTick'),
        '内层 ReceiveTick == EchoSendTick == %r（非 0）' % (inner.get('ReceiveTick'),))
    add(inner.get('RequestId') == outer.get('requestid') and inner.get('RequestId'),
        '内层 RequestId == 外层 requestid（%s）' % str(inner.get('RequestId'))[:8])
    add(len(inner) == 7, '内层 7 键（官方结构）：%d' % len(inner))
    d = inner.get('ServerTimeTicks', 0) - (inner.get('ReceiveTick') or 0)
    add(0 <= d < 100000,
        'ServerTimeTicks - ReceiveTick = %d ticks（0..100000 = 0..10 ms，官方 12）' % d)


# ================================================================ CLI
def main(argv=None):
    ap = argparse.ArgumentParser(
        description='协议 3 (NetworkTime_Sync) 服务端补丁 —— 必须显式给 --src')
    ap.add_argument('--src', required=True,
                    help='要打补丁的 account_auth_probe.py（线上：%s）' % LIVE_SRC)
    ap.add_argument('--apply', action='store_true', help='打补丁（先备份再写）')
    ap.add_argument('--verify', action='store_true', help='自检（不写文件）')
    ap.add_argument('--dry-run', action='store_true', help='打印插入位置与 diff，不写文件')
    ap.add_argument('--rollback', action='store_true', help='回滚（优先用 .p3.bak.* 还原）')
    ap.add_argument('--prove-dispatch', action='store_true',
                    help='本地仿真证明新分支真的会被走到（不连网）')
    ap.add_argument('--restore', default=None, help='配合 --rollback：直接用这个备份覆盖')
    ap.add_argument('--from-block-removal', action='store_true',
                    help='配合 --rollback：不用备份，直接摘块')
    ap.add_argument('--force', action='store_true', help='--rollback 时容忍备份指纹不符')
    ap.add_argument('--switches', choices=('keep', '1', '0'), default='keep',
                    help='cn_3.txt：keep（默认：已有不动，缺失建 1）/ 1 / 0')
    ap.add_argument('--switch-dir', default=None,
                    help='cn_3.txt 所在目录（默认：线上路径 -> %s，其它 -> src 所在目录）'
                         % DEFAULT_SWITCH_DIR)
    ap.add_argument('--full-diff', action='store_true', help='--dry-run 连载荷正文一起 diff')
    ap.add_argument('--expect-sha', default=None, help='覆盖基线 sha256 期望值')
    args = ap.parse_args(argv)

    if not (args.apply or args.verify or args.dry_run or args.rollback or args.prove_dispatch):
        ap.error('要指定 --verify / --dry-run / --apply / --prove-dispatch / --rollback 之一')
    if not os.path.isfile(args.src):
        raise SystemExit('!! --src 不存在: %s\n'
                         '   （本脚本不会去猜沙箱副本；线上路径 = %s）' % (args.src, LIVE_SRC))

    raw = open(args.src, 'rb').read()
    orig = read_text(args.src)
    print('src     : %s' % args.src)
    print('          %d 字节 / %d 行 / sha256 %s'
          % (len(raw), orig.count('\n'), hashlib.sha256(raw).hexdigest()))
    print('patched : %s' % ('是' if is_patched(orig) else '否'))

    # ---------------- rollback
    if args.rollback:
        if args.restore:
            cand = args.restore
            if not os.path.isfile(cand):
                raise SystemExit('备份不存在: %s' % cand)
        else:
            cand = None
            if not args.from_block_removal:
                for p in reversed(find_backups(args.src)):
                    s = sha256_file(p)
                    if s == (args.expect_sha or BASELINE_SHA256) or args.force:
                        cand = p
                        break
                    print('  跳过备份 %s（sha256 %s 不是基线）' % (os.path.basename(p), s[:16]))
        if cand:
            text_b = read_text(cand)
            ok, err = compile_ok(text_b, cand)
            if not ok:
                raise SystemExit('备份本身语法不过，拒绝覆盖: %s' % err)
            write_text(args.src, text_b)
            now_raw = open(args.src, 'rb').read()
            print('已用备份还原: %s' % cand)
            print('  还原后 %d 字节 / sha256 %s'
                  % (len(now_raw), hashlib.sha256(now_raw).hexdigest()))
            print('  残留 BAPATCH-P3 标记: %s'
                  % ('无（干净）' if 'BAPATCH-P3' not in text_b else '有残留!!'))
            return 0
        new_text, acts = build_removed(orig)
        for a in acts:
            print('  ' + a)
        if new_text == orig:
            print('  什么都没改（三块本来就不在）')
            return 0
        ok, err = compile_ok(new_text, args.src)
        if not ok:
            raise SystemExit('摘块后语法不过，拒绝写: %s' % err)
        bak = backup(args.src)
        write_text(args.src, new_text)
        print('  摘块回滚完成。备份=%s' % bak)
        print('  残留 BAPATCH-P3 标记: %s'
              % ('无（干净）' if 'BAPATCH-P3' not in new_text else '有残留!!'))
        return 0

    # ---------------- prove-dispatch
    if args.prove_dispatch:
        print('\n== --prove-dispatch：本地仿真（临时目录 + 替身模块，不连网、不写 src）==')
        ok, _rep, _st = prove_dispatch(orig)
        print('\n结论: %s' % ('全绿：三层钩子都会被走到、异常只降级' if ok else '有 FAIL（见上）'))
        return 0 if ok else 1

    # ---------------- apply / dry-run
    if args.apply or args.dry_run:
        before = (os.stat(args.src).st_mtime_ns, os.path.getsize(args.src))
        new_text, acts = build_patched(orig)
        print('\n== 插入动作 ==')
        for a in acts:
            print('  ' + a)
        if args.dry_run:
            print('\n== 将要插入的代码 ==')
            for unit in UNITS:
                rng = find_block(orig, unit)
                if rng:
                    print('  [%s] 已存在（第 %d-%d 行），--apply 会整块替换' % (unit, rng[0] + 1, rng[1] + 1))
                    continue
                i = orig.index(anchor_text(unit))
                line_no = orig[:i].count('\n') + 1
                print('  [%s] 插到第 %d 行之前（%s）' % (unit, line_no, ANCHOR_DESC[unit]))
            for unit in (UNIT_HOOK_E, UNIT_HOOK_D, UNIT_HOOK_G):
                print('\n  ---- %s ----' % unit)
                for ln in unit_block(unit).rstrip('\n').split('\n'):
                    print('  ' + ln)
            print('\n  ---- PAYLOAD 摘要 ----')
            body = unit_block(UNIT_PAYLOAD)
            blines = body.rstrip('\n').split('\n')
            print('  %d 行 / sha256 %s' % (len(blines), sha256_text(
                '\n'.join(blines[1:-1]) + '\n')[:16]))
            print('  头: %s' % blines[0][:110])
            print('  尾: %s' % blines[-1][:110])
        if args.full_diff:
            a_txt, b_txt = orig, new_text
        else:
            a_txt, b_txt = mask_payload(orig), mask_payload(new_text)
        diff = list(difflib.unified_diff(a_txt.split('\n'), b_txt.split('\n'),
                                         fromfile=args.src,
                                         tofile=args.src + '.patched', lineterm='', n=3))
        print('\n== diff（%d 行）==' % len(diff))
        for ln in diff:
            print('  ' + ln)
        ok, err = compile_ok(new_text, args.src)
        print('\n语法检查: %s' % ('PASS' if ok else 'FAIL ' + err))
        if not ok:
            raise SystemExit('打出来的文件语法不过，已中止（没写任何东西）')
        if args.dry_run:
            after = (os.stat(args.src).st_mtime_ns, os.path.getsize(args.src))
            print('--dry-run：没有写文件。mtime/size 未变: %s（%r）' % (before == after, after))
            print('           开关文件也没动（正式执行时 --switches %s -> %s）'
                  % (args.switches, os.path.join(
                      switch_dir_for(args.src, args.switch_dir), SWITCH_FILE)))
            return 0
        bak = backup(args.src)
        write_text(args.src, new_text)
        now_raw = open(args.src, 'rb').read()
        print('\n已写入。备份: %s' % bak)
        print('  写入后 %d 字节 / sha256 %s'
              % (len(now_raw), hashlib.sha256(now_raw).hexdigest()))
        print('  还原命令: cp -a %s %s' % (bak, args.src))
        print('  （或 python patch_3.py --src %s --rollback）' % args.src)
        print('开关: %s' % apply_switches(args.src, args.switches, args.switch_dir))
        print('\n== 打完补丁后的自检 ==')
        vok, _rep, _st = verify(args.src, args.expect_sha)
        print('自检: %s' % ('全绿' if vok else '有 FAIL（见上）'))
        return 0 if vok else 1

    # ---------------- verify
    vok, _rep, _st = verify(args.src, args.expect_sha)
    if args.switches != 'keep' and is_patched(orig):
        print('开关: %s' % apply_switches(args.src, args.switches, args.switch_dir))
    print('结论: %s' % ('PASS' if vok else 'FAIL'))
    return 0 if vok else 1


if __name__ == '__main__':
    sys.exit(main())
