#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patch_relay.py -- 未知协议「转发给本地 Shittim」补丁（不打空壳，拿真数据）。

背景（已确证）：
  * 线上 bridge = /www/wwwroot/bapatch/tools/account_auth_probe.py，
    基线 90,585 B / sha256 368aa5e7… 打上 patch_3(v1) 之后 = **103,900 B /
    sha256 563c1942289968e3f402c52eb89982cba75f9753ba85d13f6cca0be244ffc5c8**。
    本补丁只认这后一份（--expect-sha 可覆盖），不认 90,585 B 的原始基线。
  * `_bridge()` 的 `if name is None:` 分支先调 `_generic_protocol_response()`：
    它只回 {"Protocol":<num>, "ServerTimeTicks":…, "ServerNotification":0, …}
    的 min+base 空壳（536 / 512 B），**永远走不到下面那条正确的转发路径**
    （path A 在 `want_decrypt = exp.startswith('decrypt+')` 之后）。
    8000 / 8006 / 90011 / 35003 / 16000 全卡在这里（见 FALLBACK_QUEUE_20261117.md）。
    例子：/api/mission/list(8000) 一次登录被连发 3 次，官方同接口回 268,396 B。

本补丁做的事（只加两块，全部可整块摘掉）：
  1. PAYLOAD：一段自包含运行时模块（只用标准库，RL_* / rl_* 前缀），插在
     `if __name__ == '__main__':` 之前。它是运行时唯一真源，--verify 会把它
     重跑一遍单测（开关判定 / 请求重建 / 协议号排除 / 转发管线 / 重入保护）。
  2. HOOK-A：插在 `_bridge()` 的 `if name is None:` 分支里、
     `rec['unknown_protocol'] = True` **之后**、`got = self._generic_protocol_response(...)`
     **之前**。开关打开时：
       cn_cipher.decode_packet -> 请求 dict -> ensure_session(rec)（打 1014 拿真
       SessionKey 并注入）-> post_gateway（本地 Shittim /api/gateway）->
       unwrap_gateway_response -> self._cn_envelope(proto_str, obj, rec) 原样回。
     任何一步不成就 return None，原逻辑（min+base / forward）完全照旧，绝不 500。

红线（三条，都由 --verify 断言）：
  * 只接管名字表里没有的协议；RL_HANDLED 里的协议号（3 / 1005 / 1017 / 1019 /
    24000 / 26000 / 4000 / 90004）**显式排除**。这条不是多余的：本机
    /www/wwwroot/bapatch/tools/protocol_names.txt 不存在时 NAME_TABLE 只有 43 个
    BUILTIN_NAMES，24000 与 90004 的 name 也是 None —— 没有这个排除表，开关一开
    就会把 academy-24000 / management-90004 抢去转发，直接违反「已知协议逐字节不变」。
  * Account_CheckNexon(1014) 由 ensure_session 内部调用、走 post_gateway 直连
    Shittim，不经过 bridge；它在名字表里，结构上到不了本分支。RL_LOCAL.busy
    再加一道重入保护（同一线程嵌套调用直接落回原逻辑）。
  * 开关 `cn_relay_unknown.txt`：内容 1/on/true/yes = 开；0 / 缺失 / 读不到 = 关。
    **默认缺失 = 关**（打了补丁但行为与打补丁前完全一致）。
    CLI 的 `--switches keep` 也遵守这条：**文件缺失时不创建**（这点与 patch_3 的 keep 不同，
    那边的 keep 是「缺失建 1」；本补丁的红线是默认不改行为，所以只有显式 `--switches 1` 才开）。

开关查找顺序（照 patch_3 里 p3_read_file 的做法）：
    bridge 所在目录 -> /www/wwwroot/bapatch/tools -> /www/wwwroot/bapatch

日志字段（写进 rec，全部可 grep）：
    relay_on / relay_used / relay_code / relay_resp_len / relay_protocol /
    relay_err / relay_fallthrough
  另有辅助字段：relay_protocol_num / relay_shittim_keys / relay_session_injected /
    relay_gateway_protocol / relay_frag_len / relay_num / relay_account_id。

刻意不动的东西：path A（decrypt+*）、path B/C/D、_generic_protocol_response() 本体、
任何生成器、cn_* 开关。已知协议的代码路径一个字节都没变。

用法（--src 必须显式给，脚本不猜路径）：
    # 1) 自检（不写文件）：基线指纹 + 锚点唯一 + 载荷单测
    python deploy/patch_relay.py --src <file> --verify
    # 2) 只看插入位置和 diff（mtime 不变）
    python deploy/patch_relay.py --src <file> --dry-run
    # 3) 打补丁（先备份 .relay.bak.<ts>，再写，再自检）+ 开关
    python deploy/patch_relay.py --src <file> --apply --switches 1
    # 4) 回滚（优先用 .relay.bak.* 还原，零残留标记）
    python deploy/patch_relay.py --src <file> --rollback
    # 5) 换一个基线指纹
    python deploy/patch_relay.py --src <file> --verify --expect-sha <sha256>

本地演练（不碰线上）：
    python deploy/patch_relay.py --src deploy/_sandbox/p3/account_auth_probe.py --apply
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import io
import os
import shutil
import sys
import tempfile
import time

sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))

LIVE_SRC = '/www/wwwroot/bapatch/tools/account_auth_probe.py'
DEFAULT_SWITCH_DIR = '/www/wwwroot/bapatch'

# 基线指纹 = 线上现状（patch_3 已打）。--expect-sha 可覆盖。
BASE_SIZE = 103900
BASE_SHA256 = '563c1942289968e3f402c52eb89982cba75f9753ba85d13f6cca0be244ffc5c8'
# 上一层的原始基线（只用于文档/报错提示，不作为本补丁的基线）
P3_BASE_SHA256 = '368aa5e70941c3f08c59a9ede1b662331e5800dc0a714bc0a30dfbf252dd073a'

VER = 'v1'
SWITCH_FILE = 'cn_relay_unknown.txt'

# ---------------------------------------------------------------- 锚点
# 两个锚点都必须在目标文件里唯一；不唯一就拒绝动文件（见 anchor_pos）。
ANCHOR_A = ("        if name is None:\n"
            "            rec['unknown_protocol'] = True\n")
# 插完以后必须仍然在它前面（结构完好性断言）
ANCHOR_NEXT = "            got = self._generic_protocol_response(proto_str, packet_b64, rec)\n"
ANCHOR_PAYLOAD = "if __name__ == '__main__':\n"

UNIT_PAYLOAD = 'PAYLOAD'
UNIT_HOOK_A = 'HOOK-A'
UNITS = (UNIT_PAYLOAD, UNIT_HOOK_A)

ANCHORS = {UNIT_PAYLOAD: (ANCHOR_PAYLOAD, 'before'),
           UNIT_HOOK_A: (ANCHOR_A, 'after')}

ANCHOR_DESC = {
    UNIT_PAYLOAD: "bridge 顶层，`if __name__ == '__main__':` 之前",
    UNIT_HOOK_A: "_bridge() 的 name is None 分支里，`rec['unknown_protocol'] = True` 之后、"
                 "`got = self._generic_protocol_response(...)` 之前",
}

# ================================================================ 内嵌运行时（唯一真源）
RL_PAYLOAD_SRC = r'''# -*- coding: utf-8 -*-
"""未知协议 -> 本地 Shittim 转发（bridge 运行时真源，patch_relay.py --verify 逐字节比对）。

问题：_bridge() 的 `if name is None:` 分支先调 _generic_protocol_response()，它只回
     {"Protocol":<num>, "ServerTimeTicks":…, "ServerNotification":0, …} 的 min+base
     空壳，不会把客户端真实请求送去 Shittim。8000 / 8006 / 90011 / 35003 / 16000 卡在这里。

做法（开关打开时）：
     ① cn_cipher.decode_packet(packet_b64, proto_str) 解出客户端真实请求；
     ② ensure_session(rec) 打 Account_CheckNexon(1014) 拿真 SessionKey 并注入；
     ③ post_gateway(req) POST 到本地 Shittim 的 /api/gateway；
     ④ unwrap_gateway_response(raw) 拿 dict；
     ⑤ bridge 自己的 _cn_envelope(proto_str, obj, rec) 包成 CN 信封返回。
     任何一步不成就 return None，原逻辑（min+base / forward）照旧，绝不 500。

红线：
  * RL_HANDLED 里的协议号（3/1005/1017/1019/24000/26000/4000/90004）**显式排除**。
    本机 protocol_names.txt 缺失时 24000 / 90004 的 name 也是 None，没有这张表，
    开关一开就会把它们从真生成器手里抢走。
  * Account_CheckNexon(1014) 在名字表里，结构上到不了本分支；RL_LOCAL.busy 再挡
    一层同线程重入（嵌套调用直接落回原逻辑，不死循环）。
  * 开关缺失/0 => 完全不改行为（fail-safe）。

开关查找顺序（与 p3_read_file / simple_read_switch 一致）：
    bridge 所在目录 -> /www/wwwroot/bapatch/tools -> /www/wwwroot/bapatch

日志字段（写进 rec）：relay_on / relay_used / relay_code / relay_resp_len /
    relay_protocol / relay_err / relay_fallthrough
  辅助：relay_protocol_num / relay_num / relay_frag_len / relay_shittim_keys /
    relay_session_injected / relay_gateway_protocol / relay_account_id

约定（原样贴进 bridge 模块命名空间）：
  * 不写 from __future__，不写 __main__ 块；
  * 只用标准库，全部用 _rl* 别名 import，不污染 bridge 现有全局名；
  * import 期不碰文件系统、不碰网络；bridge 依赖一律 globals().get() 运行时取。
"""
import json as _rljson
import os as _rlos
import re as _rlre
import threading as _rlthreading

RL_SWITCH_FILE = 'cn_relay_unknown.txt'
RL_FALLBACK_DIRS = ('/www/wwwroot/bapatch/tools', '/www/wwwroot/bapatch')
# 有真生成器 / 别的 hook 负责的协议号：本 hook 一律不碰（名字表缺名字时尤其重要）
RL_HANDLED = frozenset((3, 1005, 1017, 1019, 24000, 26000, 4000, 90004))
RL_SKIP_NAMES = frozenset(('Account_CheckNexon',))
RL_LOCAL = _rlthreading.local()


# ---------------------------------------------------------------- 开关
def rl_dirs():
    """开关文件的候选目录（有序）。"""
    out = []
    try:
        out.append(_rlos.path.dirname(_rlos.path.abspath(__file__)))
    except Exception:
        pass
    for d in RL_FALLBACK_DIRS:
        if d not in out:
            out.append(d)
    return out


def rl_read_file(fn, base=None):
    """读一个小开关文件 -> (路径, 内容)。找不到 -> (None, None)。"""
    dirs = ([base] if base else []) + rl_dirs()
    for d in dirs:
        if not d:
            continue
        p = _rlos.path.join(d, fn)
        try:
            with open(p, 'r') as fh:
                return p, fh.read().strip()
        except Exception:
            continue
    return None, None


def rl_switch_on(base=None):
    """未知协议转发是否启用。缺失 / 读不到 / 内容不是真值 -> False（fail-safe）。"""
    _p, v = rl_read_file(RL_SWITCH_FILE, base)
    if v is None:
        return False
    return v.strip().lower() in ('1', 'on', 'true', 'yes')


# ---------------------------------------------------------------- 请求重建
def rl_num_from_frag(frag):
    """协议号 = 请求里 Hash 的高 32 位（客户端每个请求都自带 Hash）。"""
    if not isinstance(frag, str) or not frag:
        return None
    m = _rlre.search(r'"Hash"\s*:\s*(\d+)', frag)
    if not m:
        return None
    try:
        return int(m.group(1)) >> 32
    except Exception:
        return None


def rl_request_json(decoded, rec=None):
    """cn_cipher.decode_packet() 的结果 -> 可发给 Shittim 的请求 dict；失败 -> None。

    decode_packet 的 'json' 只在它认识 protocol token 时才填（参照实现
    report/_tmp/mx_crypto/cn_cipher.py 的 PROTOCOL_MAP 只有 Account_Auth 一条）；
    而本 hook 面对的正是「名字表里没有」的 token，所以 'json' 常常是 None。
    这时用 'fragment'（客户端明文片段，形如 ',"Hash":…,"IsTest":false}'）拼回
    完整请求：'{"Protocol":<num>' + fragment。Protocol 用数字，交给 Shittim 的
    enum 反序列化（它本来就接受数字与名字两种写法）。
    """
    if not isinstance(decoded, dict):
        return None
    js = decoded.get('json')
    if isinstance(js, dict) and js:
        return js
    frag = decoded.get('fragment')
    if not isinstance(frag, str):
        return None
    text = frag.strip()
    if not text:
        return None
    if text[0] == '{':
        try:
            obj = _rljson.loads(text)
        except Exception:
            return None
        return obj if isinstance(obj, dict) else None
    num = rl_num_from_frag(text)
    if num is None and isinstance(rec, dict):
        h = rec.get('req_Hash')
        if isinstance(h, int) and h > 0:
            num = h >> 32
    if num is None:
        return None
    try:
        obj = _rljson.loads('{"Protocol":%d' % int(num) + text)
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def rl_num_from_request(decoded, req=None):
    """协议号：片段 Hash>>32 -> 请求 JSON 的 Hash >>32 -> 请求 JSON 的 Protocol(int)。"""
    num = None
    if isinstance(decoded, dict):
        num = rl_num_from_frag(decoded.get('fragment'))
    if num is None and isinstance(req, dict):
        h = req.get('Hash')
        if isinstance(h, int) and h > 0:
            num = h >> 32
        elif isinstance(h, str) and h.strip().isdigit():
            num = int(h.strip()) >> 32
    if num is None and isinstance(req, dict):
        p = req.get('Protocol')
        if isinstance(p, int) and p > 0:
            num = p
    return num


# ---------------------------------------------------------------- 转发管线
def rl_route(rec, proto_str, packet_b64, name=None, envelope=None, base=None):
    """未知协议的接管线。已接管 -> (code, body, ctype)；不管 -> None（交回原兜底）。

    envelope 必须注入（bridge 传 self._cn_envelope）：
        envelope(proto_str, inner_obj, rec) -> (code, body, ctype)
    任何异常都不在这里吞：由 HOOK-A 的 try/except 兜住并记 rec['relay_err']。
    """
    if not isinstance(rec, dict):
        rec = {}
    on = bool(rl_switch_on(base))
    rec['relay_on'] = on
    rec['relay_err'] = ''
    if not on:
        rec['relay_fallthrough'] = 'switch-off'
        return None
    if isinstance(name, str) and name and name != 'Unknown':
        rec['relay_fallthrough'] = 'known-name'
        return None
    if isinstance(name, str) and name in RL_SKIP_NAMES:
        rec['relay_fallthrough'] = 'skip-name'
        return None
    if getattr(RL_LOCAL, 'busy', False):
        rec['relay_fallthrough'] = 'reentrant'
        return None
    RL_LOCAL.busy = True
    try:
        return _rl_relay_once(rec, proto_str, packet_b64, envelope)
    finally:
        RL_LOCAL.busy = False


def _rl_relay_once(rec, proto_str, packet_b64, envelope):
    """真正干活的只有这一段；异常往上抛（HOOK-A 负责留痕 + 落回）。"""
    dec = globals().get('cn_cipher')
    if dec is None or not hasattr(dec, 'decode_packet'):
        rec['relay_err'] = 'cn_cipher.decode_packet unavailable'
        rec['relay_fallthrough'] = 'no-cn_cipher'
        return None
    try:
        decoded = dec.decode_packet(packet_b64, proto_str)
    except Exception as e:
        rec['relay_err'] = repr(e)
        rec['relay_fallthrough'] = 'decode'
        return None
    req = rl_request_json(decoded, rec)
    if not isinstance(req, dict):
        rec['relay_fallthrough'] = 'decode-json'
        return None
    rec['relay_frag_len'] = len(decoded.get('fragment') or '') if isinstance(decoded, dict) else 0
    num = rl_num_from_request(decoded, req)
    rec['relay_num'] = num
    if num is None:
        rec['relay_fallthrough'] = 'no-protocol-num'
        return None
    if num in RL_HANDLED:
        # 3/1005/1017/1019/24000/26000/4000/90004 有真生成器：绝不抢
        rec['relay_fallthrough'] = 'handled-%d' % num
        return None
    ensure = globals().get('ensure_session')
    post = globals().get('post_gateway')
    unwrap = globals().get('unwrap_gateway_response')
    if not (callable(ensure) and callable(post) and callable(unwrap)):
        rec['relay_err'] = ('bridge deps missing: ensure_session=%r post_gateway=%r '
                            'unwrap_gateway_response=%r'
                            % (callable(ensure), callable(post), callable(unwrap)))
        rec['relay_fallthrough'] = 'no-deps'
        return None
    sk, aid = ensure(rec)
    if sk is None:
        rec['relay_fallthrough'] = 'ensure-session'
        return None
    injected = not req.get('SessionKey')
    if injected:
        req['SessionKey'] = sk
    rec['relay_session_injected'] = bool(injected)
    rec['relay_account_id'] = aid
    code, raw = post(req)
    raw = raw or b''
    rec['relay_code'] = code
    rec['relay_resp_len'] = len(raw)
    if code == 0:
        rec['relay_err'] = 'gateway unreachable/timeout: %r' % (raw[:160],)
        rec['relay_fallthrough'] = 'gateway-code-0'
        return None
    gp, obj = unwrap(raw)
    if isinstance(gp, (str, int)) or gp is None:
        rec['relay_gateway_protocol'] = gp
    else:
        rec['relay_gateway_protocol'] = repr(gp)
    if not isinstance(obj, dict):
        rec['relay_err'] = ('shittim response not dict (code=%r len=%d body=%r)'
                            % (code, len(raw), raw[:160]))
        rec['relay_fallthrough'] = 'shittim-non-dict'
        return None
    rec['relay_protocol'] = req.get('Protocol') if req.get('Protocol') is not None else num
    rec['relay_protocol_num'] = num
    if isinstance(obj.get('Protocol'), int):
        rec['relay_shittim_protocol'] = obj.get('Protocol')
    rec['relay_shittim_keys'] = len(obj)
    out = None
    if callable(envelope):
        out = envelope(proto_str, obj, rec)
    if out is None:
        rec['relay_fallthrough'] = 'envelope'
        return None
    rec['relay_used'] = True
    rec['relay_fallthrough'] = ''
    return out
'''

# ---------------------------------------------------------------- hook 的代码
# 注意缩进：`rec['unknown_protocol'] = True` 在 `if name is None:` 的**函数体里**（12 空格），
# 所以整块必须 12 空格缩进。缩进错了不会报语法错，但会跑到分支外面对所有协议生效 ——
# --verify 有专门的缩进断言，_relay_replay 的 R5 会从行为上再抓一次。
HOOK_A_BODY = """            # >>> BAPATCH-RELAY-HOOK-A %(ver)s BEGIN >>>
            # 未知协议：开关打开时把解出来的客户端真实请求转发给本地 Shittim
            # (/api/gateway)，拿到 dict 回包就用 _cn_envelope 包成 CN 信封返回。
            # 任何一步不成就原路落回（下面的 min+base / forward 完全不变，绝不 500）。
            # 已知协议（含 3/1005/1017/1019/24000/26000/4000/90004）在 relay_route
            # 里由 RL_HANDLED 显式排除；Account_CheckNexon(1014) 只由 ensure_session
            # 内部调用，不会经过这里。开关 cn_relay_unknown.txt 缺失 = 关。
            try:
                _rl_a = rl_route(rec, proto_str, packet_b64, name, self._cn_envelope)
                if _rl_a is not None:
                    return _rl_a
            except Exception as _rl_a_err:
                rec['relay_err'] = repr(_rl_a_err)
                rec['relay_fallthrough'] = 'exception'
            # <<< BAPATCH-RELAY-HOOK-A %(ver)s END <<<
"""


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
    return '# >>> BAPATCH-RELAY-%s %s BEGIN' % (unit, VER)


def mark_end(unit):
    return '# <<< BAPATCH-RELAY-%s %s END <<<' % (unit, VER)


def payload_body():
    """内嵌运行时正文（唯一真源 = 本文件里的 RL_PAYLOAD_SRC）。"""
    return RL_PAYLOAD_SRC.replace('\r\n', '\n').rstrip('\n') + '\n'


def unit_block(unit, body=None):
    """整块文本（含 BEGIN/END 标记）。PAYLOAD 顶格，hook 按函数体缩进。"""
    if unit == UNIT_PAYLOAD:
        src = payload_body() if body is None else body
        head = ('%s >>> (deploy/patch_relay.py 内嵌 RL_PAYLOAD_SRC，sha256=%s) >>>'
                % (mark_begin(UNIT_PAYLOAD), sha256_text(src)))
        return head + '\n' + src + mark_end(UNIT_PAYLOAD) + '\n'
    return HOOK_A_BODY % {'ver': VER}


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
    ph = '# ...[%d 行运行时模块原样内嵌自 patch_relay.py 的 RL_PAYLOAD_SRC，--full-diff 查看]...' % n
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
        end_line = line_no + at.count('\n') - 1
        i = text.index(at)
        after = isinstance(ANCHORS[unit], tuple) and ANCHORS[unit][1] == 'after'
        if after:
            i += len(at)
        text = text[:i] + blk + text[i:]
        acts.append('%s: 在原文件第 %d%s 行%s插入 %d 行（锚点 %r）'
                    % (unit, line_no,
                       ('-%d' % end_line) if end_line > line_no else '',
                       '之后' if after else '之前',
                       nlines, at.strip().split('\n')[0][:56]))
        if unit == UNIT_HOOK_A:
            acts.append('       -> 插入后 HOOK-A 落在第 %d 行之前（即 anchor 之后）'
                        % (text[:text.index(mark_begin(UNIT_HOOK_A))].count('\n') + 1))
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
    bak = '%s.relay.bak.%s' % (src, time.strftime('%Y%m%d-%H%M%S'))
    shutil.copy2(src, bak)
    return bak


def find_backups(src):
    d = os.path.dirname(os.path.abspath(src))
    base = os.path.basename(src) + '.relay.bak.'
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
    """写开关。与 patch_3 的差异（有意为之）：keep 在文件**缺失时不创建**。

    patch_3 的 keep 是「缺失建 1」——对它合适（协议 3 的目标就是打开）。但本补丁的红线是
    「默认必须是不存在 = 关，打了补丁但不改行为」，所以这里 keep 只保留已有内容，
    缺失就保持缺失（= 关）。要开必须显式 --switches 1。
    """
    d = switch_dir_for(src, override)
    p = os.path.join(d, SWITCH_FILE)
    exists = os.path.exists(p)
    if val == 'keep':
        if exists:
            with io.open(p, 'r') as fh:
                return '%s=%r（保留，未改动）' % (p, fh.read().strip())
        return ('%s（缺失，未创建 —— 缺失=关；要开启用 --switches 1，'
                '要显式写 0 用 --switches 0）' % p)
    if not os.path.isdir(d):
        return '%s（目录不存在，未创建 —— 开关按「关」处理）' % p
    with io.open(p, 'w', newline='\n') as fh:
        fh.write(val + '\n')
    return '%s=%s（%s）' % (p, val, '改写' if exists else '新建')


# ================================================================ 内嵌运行时装载 / 单测
def load_embedded_ns(src_text):
    body = extract_block_body(src_text, UNIT_PAYLOAD)
    if body is None:
        return None, '内嵌 PAYLOAD 块不存在'
    ns = {'__name__': 'embedded_relay_payload',
          '__file__': os.path.join(HERE, 'patch_relay.py')}
    try:
        exec(compile(body, '<embedded relay payload>', 'exec'), ns)
    except Exception as e:
        return None, '内嵌 PAYLOAD 无法 exec: %r' % (e,)
    return ns, ''


class _FakeCnCipher(object):
    """verify 单测用的 cn_cipher 替身：decode_packet 返回预设结果（或抛错）。"""

    def __init__(self, decoded=None, error=None):
        self.decoded = decoded
        self.error = error
        self.calls = []

    def decode_packet(self, packet_b64, protocol_field=None):
        self.calls.append((packet_b64, protocol_field))
        if self.error is not None:
            raise self.error
        return self.decoded


def _payload_selftest(ns, tmp, add, info):
    """把内嵌运行时当成独立模块跑一遍单测（不碰网络、不碰 bridge）。"""
    NS = ns

    def put(name, val):
        NS[name] = val

    def drop(*names):
        for n in names:
            NS.pop(n, None)

    # ---- 开关
    _dirs = NS['rl_dirs']()
    add(_dirs and _dirs[0] == os.path.dirname(os.path.abspath(NS['__file__']))
        and '/www/wwwroot/bapatch/tools' in _dirs and '/www/wwwroot/bapatch' in _dirs
        and _dirs.index('/www/wwwroot/bapatch/tools') < _dirs.index('/www/wwwroot/bapatch'),
        '开关查找顺序 == bridge 目录 -> /www/wwwroot/bapatch/tools -> /www/wwwroot/bapatch（%r）'
        % (_dirs,))
    add(NS['rl_switch_on'](tmp) is False, '开关文件缺失 -> 判定「关」（fail-safe）')
    sw = os.path.join(tmp, SWITCH_FILE)
    for text, want, label in (('1\n', True, '1'), ('0\n', False, '0'),
                              ('on\n', True, 'on'), ('  yes  \n', True, 'yes'),
                              ('\n', False, '空')):
        write_text(sw, text)
        add(NS['rl_switch_on'](tmp) is want, 'cn_relay_unknown.txt=%s -> %s' % (label, want))
    os.remove(sw)
    add(NS['rl_switch_on'](tmp) is False, '删除开关文件 -> 又变回「关」')

    # ---- 请求重建
    frag = ',"Hash":34359738368005,"IsTest":false,"AccountId":10015354380}'
    add(NS['rl_num_from_frag'](frag) == 8000, 'Hash>>32 -> 协议号 8000')
    add(NS['rl_num_from_frag']('') is None and NS['rl_num_from_frag'](None) is None,
        '空片段 / None -> 协议号 None（不抛）')
    req0 = {'Protocol': 8000, 'Hash': 34359738368005, 'IsTest': False}
    add(NS['rl_request_json']({'json': req0, 'fragment': ''}) is req0,
        "decode_packet 给了 'json' -> 直接用它（与 path A 同源）")
    got = NS['rl_request_json']({'json': None, 'fragment': frag})
    add(isinstance(got, dict) and got.get('Protocol') == 8000
        and got.get('Hash') == 34359738368005,
        "cn_cipher 不认识 token（json=None）-> 用 fragment 拼回 {\"Protocol\":8000,…}"
        '（%r）' % (sorted(got.keys()) if isinstance(got, dict) else got,))
    add(NS['rl_request_json']({'json': None, 'fragment': ''}) is None,
        '片段为空 -> None（落回原逻辑）')
    got2 = NS['rl_request_json']({'json': None, 'fragment': ',"IsTest":false}'},
                                 {'req_Hash': 90004 << 32})
    add(isinstance(got2, dict) and got2.get('Protocol') == 90004,
        '片段没有 Hash 时用 rec[req_Hash] 补协议号（%r）' % (got2,))
    add(NS['rl_request_json']({'json': None, 'fragment': '}}garbage'}) is None
        or isinstance(NS['rl_request_json']({'json': None, 'fragment': '}}garbage'}), dict),
        '坏片段不抛异常（返回 None 或 dict）')
    add(NS['rl_num_from_request']({'fragment': frag}, {'Hash': 34359738368005}) == 8000,
        'rl_num_from_request 优先级：片段 Hash 优先')

    # ---- 开关关 == 完全不接管
    rec = {}
    out = NS['rl_route'](rec, 'TOKEN', '<REDACTED_TOKEN>', None, lambda *a: (200, b'X', 't'), tmp)
    add(out is None and rec.get('relay_on') is False
        and rec.get('relay_fallthrough') == 'switch-off',
        '开关关：rl_route -> None（relay_on=False / fallthrough=switch-off）')

    write_text(sw, '1\n')
    rec = {'req_Hash': 90004 << 32}
    out = NS['rl_route'](rec, 'TOKEN', '<REDACTED_TOKEN>', None, lambda *a: (200, b'X', 't'), tmp)
    add(out is None and rec.get('relay_err') and 'cn_cipher' in rec['relay_err'],
        '开关开但没有 cn_cipher -> None + relay_err 留痕（%r）' % (rec.get('relay_err'),))

    # ---- 已知协议号显式排除（本机 24000/90004 的 name 就是 None）
    for num in (3, 1005, 1017, 1019, 24000, 26000, 4000, 90004):
        put('cn_cipher', _FakeCnCipher({'json': None,
                                        'fragment': ',"Hash":%d}' % (num << 32 | 5)}))
        rec = {}
        out = NS['rl_route'](rec, 'TOKEN', '<REDACTED_TOKEN>', None, lambda *a: (200, b'X', 't'), tmp)
        add(out is None and rec.get('relay_fallthrough') == 'handled-%d' % num,
            '协议号 %d 有真生成器 -> 本 hook 不碰（fallthrough=%r）'
            % (num, rec.get('relay_fallthrough')))
    add(3 in NS['RL_HANDLED'] and 24000 in NS['RL_HANDLED'] and 90004 in NS['RL_HANDLED'],
        'RL_HANDLED 覆盖 3 / 24000 / 90004（名字表缺名字时也不会被抢）')

    # ---- 名字已知 / 重入
    rec = {}
    out = NS['rl_route'](rec, 'TOKEN', '<REDACTED_TOKEN>', 'Item_List', lambda *a: (200, b'X', 't'), tmp)
    add(out is None and rec.get('relay_fallthrough') == 'known-name',
        'name 已知 -> 不接管（fallthrough=known-name）')
    rec = {}
    NS['RL_LOCAL'].busy = True
    try:
        out = NS['rl_route'](rec, 'TOKEN', '<REDACTED_TOKEN>', None, lambda *a: (200, b'X', 't'), tmp)
    finally:
        NS['RL_LOCAL'].busy = False
    add(out is None and rec.get('relay_fallthrough') == 'reentrant',
        '同线程重入保护：busy=True -> 不接管（fallthrough=reentrant）')

    # ---- 完整转发管线（全替身）
    put('cn_cipher', _FakeCnCipher({'json': None, 'fragment': frag}))
    put('ensure_session', lambda rec: ({'AccountServerId': 2, 'MxToken': 'M' * 64}, 2))
    sent = []

    def fake_post(obj, timeout=40):
        sent.append(obj)
        return 200, b'{"protocol":"Mission_List","packet":"{\\"Protocol\\":8000,\\"Echo\\":[\\"Hash\\"]}"}'

    put('post_gateway', fake_post)
    put('unwrap_gateway_response', lambda raw: ('Mission_List',
                                                {'Protocol': 8000, 'Echo': ['Hash']}))
    enveloped = []

    def fake_env(proto_str, obj, rec):
        enveloped.append((proto_str, obj))
        return 200, b'RELAY-OK', 'text/plain; charset=utf-8'

    rec = {}
    out = NS['rl_route'](rec, 'TOKEN_8000', 'B64', None, fake_env, tmp)
    add(out == (200, b'RELAY-OK', 'text/plain; charset=utf-8'),
        '开关开 + 全链路替身 -> 返回 _cn_envelope 的 (200, body, ctype)')
    add(rec.get('relay_used') is True and rec.get('relay_on') is True,
        'relay_used=True / relay_on=True')
    add(rec.get('relay_protocol') == 8000 and rec.get('relay_protocol_num') == 8000,
        'relay_protocol=%r / relay_protocol_num=%r（协议号取自 Hash>>32）'
        % (rec.get('relay_protocol'), rec.get('relay_protocol_num')))
    add(rec.get('relay_code') == 200 and rec.get('relay_resp_len') == len(
        b'{"protocol":"Mission_List","packet":"{\\"Protocol\\":8000,\\"Echo\\":[\\"Hash\\"]}"}'),
        'relay_code=%r / relay_resp_len=%r' % (rec.get('relay_code'), rec.get('relay_resp_len')))
    add(rec.get('relay_session_injected') is True and sent
        and isinstance(sent[-1].get('SessionKey'), dict),
        'SessionKey 缺省时注入（relay_session_injected=%r）' % (rec.get('relay_session_injected'),))
    add(sent and sent[-1].get('Protocol') == 8000,
        '发给 Shittim 的请求带 Protocol=8000（%r）' % (sent[-1].get('Protocol') if sent else None,))
    add(enveloped and enveloped[-1][0] == 'TOKEN_8000'
        and enveloped[-1][1].get('Protocol') == 8000,
        '响应经 self._cn_envelope(proto_str, obj, rec) 出口（proto_str=%r, keys=%r）'
        % (enveloped[-1][0] if enveloped else None,
           sorted(enveloped[-1][1]) if enveloped else None))

    # 请求已带 SessionKey 就不覆盖（与 path A 同一语义）
    sent[:] = []
    rec = {}
    put('cn_cipher', _FakeCnCipher({'json': {'Protocol': 8000, 'SessionKey': {'AccountServerId': 7}},
                                    'fragment': frag}))
    out = NS['rl_route'](rec, 'TOKEN_8000', 'B64', None, fake_env, tmp)
    add(out is not None and rec.get('relay_session_injected') is False
        and sent and sent[-1]['SessionKey'] == {'AccountServerId': 7},
        '请求里已有 SessionKey -> 不覆盖（relay_session_injected=False）')

    # ---- ensure_session 拿不到会话 -> 落回（不 500、不死循环）
    put('cn_cipher', _FakeCnCipher({'json': None, 'fragment': frag}))
    put('ensure_session', lambda rec: (None, None))
    rec = {}
    out = NS['rl_route'](rec, 'TOKEN_8000', 'B64', None, fake_env, tmp)
    add(out is None and rec.get('relay_fallthrough') == 'ensure-session'
        and rec.get('relay_used') is None,
        'ensure_session 回 None（1014 失败）-> 落回原逻辑（fallthrough=ensure-session）')

    # ---- Shittim 报错 / 超时 -> 一律落回
    sent[:] = []
    put('cn_cipher', _FakeCnCipher({'json': None, 'fragment': frag}))
    put('ensure_session', lambda rec: ({'AccountServerId': 2, 'MxToken': 'M' * 64}, 2))
    put('post_gateway', lambda obj, timeout=40: (500, b'{"error":"boom"}'))
    put('unwrap_gateway_response', lambda raw: (None, None))
    rec = {}
    out = NS['rl_route'](rec, 'TOKEN_8000', 'B64', None, fake_env, tmp)
    add(out is None and rec.get('relay_used') is None and bool(rec.get('relay_err')),
        'Shittim 回 500 -> None + relay_err=%r（落回 min+base，不 500）'
        % (rec.get('relay_err'),))

    put('post_gateway', lambda obj, timeout=40: (0, b'{"error":"timed out"}'))
    rec = {}
    out = NS['rl_route'](rec, 'TOKEN_8000', 'B64', None, fake_env, tmp)
    add(out is None and rec.get('relay_fallthrough') == 'gateway-code-0'
        and bool(rec.get('relay_err')),
        'Shittim 超时（post_gateway 回 code 0）-> None + relay_err=%r'
        % (rec.get('relay_err'),))

    # ---- 解码失败 -> 落回
    put('cn_cipher', _FakeCnCipher(error=ValueError('bad packet')))
    rec = {}
    out = NS['rl_route'](rec, 'TOKEN_8000', 'B64', None, fake_env, tmp)
    add(out is None and rec.get('relay_fallthrough') == 'decode'
        and 'bad packet' in str(rec.get('relay_err')),
        'cn_cipher.decode_packet 抛错 -> None + relay_err=%r' % (rec.get('relay_err'),))

    # ---- 清理注入的替身，避免污染后续
    drop('cn_cipher', 'ensure_session', 'post_gateway', 'unwrap_gateway_response')
    if os.path.exists(sw):
        os.remove(sw)


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

    want = want_sha or BASE_SHA256
    raw = open(src, 'rb').read()
    sha = hashlib.sha256(raw).hexdigest()
    text = read_text(src)
    patched = is_patched(text)
    info('src = %s  (%d 字节 / %d 行 / sha256 %s)'
         % (src, len(raw), text.count('\n'), sha))
    info('状态 = %s' % ('已打补丁（校验补丁后不变量）' if patched else '未打补丁（校验基线+锚点）'))

    # ---- 1. 语法
    ok, err = compile_ok(text, src)
    add(ok, 'python 语法检查 compile() %s' % ('' if ok else '-> ' + err))

    if not patched:
        # ---- 2. 基线指纹
        add(len(raw) == BASE_SIZE, '基线大小 == %d（实测 %d）' % (BASE_SIZE, len(raw)))
        add(sha == want, '基线 sha256 == %s（实测 %s）' % (want, sha))
        add('BAPATCH-RELAY' not in text, '基线里没有 BAPATCH-RELAY 残留标记')
        add(text.count('BAPATCH-P3-PAYLOAD %s BEGIN' % VER) == 1,
            '基线确实是打过 patch_3 的 103900 B 版本（P3 载荷块在）')
        # ---- 3. 锚点
        for unit in UNITS:
            n, line = anchor_hits(text, anchor_text(unit))
            add(n == 1, '锚点 %s 唯一命中 %d 次（第 %s 行，%s）'
                % (unit, n, line, ANCHOR_DESC[unit]))
        i_a = text.find(ANCHOR_A)
        i_n = text.find(ANCHOR_NEXT)
        add(0 <= i_a < i_n, 'name is None 分支结构完好（anchor@%d < got@%d）' % (i_a, i_n))
        i_m = text.find(ANCHOR_PAYLOAD)
        add(i_m > i_n, "PAYLOAD 锚点在 name is None 分支之后（main@%d）" % (i_m,))
    else:
        # ---- 2. 标记成对
        for unit in UNITS:
            b, e = count_marks(text, unit)
            add(b == 1 and e == 1 and find_block(text, unit) is not None,
                '%s 标记成对、各 1 处（BEGIN %d / END %d）' % (unit, b, e))
        # ---- 3. 载荷逐字节 == 真源
        body = extract_block_body(text, UNIT_PAYLOAD)
        add(body == payload_body(),
            '内嵌 PAYLOAD 逐字节 == patch_relay.py 的 RL_PAYLOAD_SRC（sha256 %s / %s）'
            % ((sha256_text(body)[:16] if body else '-'), sha256_text(payload_body())[:16]))
        head_line = ''
        for ln in text.split('\n'):
            if ln.lstrip().startswith(mark_begin(UNIT_PAYLOAD)):
                head_line = ln
                break
        import re as _re
        m = _re.search(r'sha256=([0-9a-f]{64})', head_line)
        add(bool(m) and m.group(1) == sha256_text(payload_body()),
            'PAYLOAD 标记里记的 sha256 与真源一致（%s）' % (m.group(1)[:16] if m else '缺'))
        # ---- 4. hook 逐字节
        blk = extract_block_body(text, UNIT_HOOK_A)
        want_hook = '\n'.join(unit_block(UNIT_HOOK_A).rstrip('\n').split('\n')[1:-1]) + '\n'
        add(blk == want_hook, 'HOOK-A 代码块逐字节 == patch_relay.py 里生成的那份')
        # ---- 5. 位置
        i_none = text.find("        if name is None:")
        i_flag = text.find("            rec['unknown_protocol'] = True")
        i_hook = text.find(mark_begin(UNIT_HOOK_A))
        i_got = text.find(ANCHOR_NEXT)
        add(0 <= i_none < i_flag < i_hook < i_got,
            'HOOK-A 落在 `if name is None:` 之内：none@%d < flag@%d < hook@%d < got@%d'
            % (i_none, i_flag, i_hook, i_got))
        hook_lines = text.split('\n')
        hook_first = ''
        prev_line = ''
        for _i, _ln in enumerate(hook_lines):
            if _ln.lstrip().startswith(mark_begin(UNIT_HOOK_A)):
                hook_first = _ln
                prev_line = hook_lines[_i - 1] if _i else ''
                break
        add(hook_first.startswith('            #') and not hook_first.startswith('             '),
            'HOOK-A 起始行缩进 12 空格（在 name is None 的分支体内，不是函数体层）')
        add(prev_line == "            rec['unknown_protocol'] = True",
            'HOOK-A 紧跟在 `rec[unknown_protocol] = True` 之后（上一行 = %r）' % (prev_line,))
        try:
            import ast as _ast
            _tree = _ast.parse(text)
            _hook_ok = False
            for _node in _ast.walk(_tree):
                if isinstance(_node, _ast.If) and isinstance(_node.test, _ast.Compare):
                    try:
                        if (_node.test.left.id == 'name'
                                and isinstance(_node.test.comparators[0], _ast.Constant)
                                and _node.test.comparators[0].value is None):
                            _seg = _ast.get_source_segment(text, _node) or ''
                            _hook_ok = 'BAPATCH-RELAY-HOOK-A' in _seg
                    except Exception:
                        pass
            add(_hook_ok, 'AST：HOOK-A 确实在 `if name is None:` 的语法块里（不只是文本位置对）')
        except Exception as _e:
            add(False, 'AST 检查失败: %r' % (_e,))
        add('rl_route' in text[i_hook:i_got] and 'self._cn_envelope' in text[i_hook:i_got],
            'HOOK-A 调用了 rl_route(...) 且注入 self._cn_envelope')
        i_payload = text.find(mark_begin(UNIT_PAYLOAD))
        i_main = text.find(ANCHOR_PAYLOAD)
        add(0 < i_payload < i_main,
            "PAYLOAD 在 `if __name__ == '__main__':` 之前（payload@%d < main@%d）"
            % (i_payload, i_main))
        # ---- 6. 既有补丁没被动过
        for other in ('BAPATCH-P3-PAYLOAD', 'BAPATCH-P3-HOOK-E', 'BAPATCH-P3-HOOK-D',
                      'BAPATCH-P3-HOOK-G', 'BAPATCH-SIMPLE-PAYLOAD',
                      'BAPATCH-SIMPLE-HOOK-D', 'BAPATCH-SIMPLE-HOOK-G'):
            add(text.count(other + ' %s BEGIN' % VER) == 1,
                '既有补丁 %s 仍在（未被动过）' % other)
        # ---- 7. 摘掉本补丁 == 基线（逐字节）
        removed, _acts = build_removed(text)
        add(len(removed.encode('utf-8')) == BASE_SIZE
            and sha256_text(removed) == want,
            '摘掉 PAYLOAD+HOOK-A 后逐字节 == 基线 %d B / sha256 %s（实测 %d B / %s）'
            % (BASE_SIZE, want[:16], len(removed.encode('utf-8')),
               sha256_text(removed)[:16]))
        add('BAPATCH-RELAY' not in removed, '摘块后零 BAPATCH-RELAY 残留')

    # ---- 8. 内嵌运行时单测
    ns, nerr = load_embedded_ns(text) if patched else (None, '未打补丁')
    if patched:
        add(ns is not None, '内嵌载荷可 exec%s' % ('' if ns else ' -> ' + nerr))
    if ns:
        tmp = tempfile.mkdtemp(prefix='relaysw_')
        try:
            _payload_selftest(ns, tmp, add, info)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    if verbose:
        for line in rep:
            print('  ' + line)
    return state['ok'], rep, state


# ================================================================ CLI
def main(argv=None):
    ap = argparse.ArgumentParser(
        description='未知协议转发给本地 Shittim 的补丁 —— 必须显式给 --src')
    ap.add_argument('--src', required=True,
                    help='要打补丁的 account_auth_probe.py（线上：%s）' % LIVE_SRC)
    ap.add_argument('--apply', action='store_true', help='打补丁（先备份再写）')
    ap.add_argument('--verify', action='store_true', help='自检（不写文件）')
    ap.add_argument('--dry-run', action='store_true', help='打印插入位置与 diff，不写文件')
    ap.add_argument('--rollback', action='store_true', help='回滚（优先用 .relay.bak.* 还原）')
    ap.add_argument('--restore', default=None, help='配合 --rollback：直接用这个备份覆盖')
    ap.add_argument('--from-block-removal', action='store_true',
                    help='配合 --rollback：不用备份，直接摘块')
    ap.add_argument('--force', action='store_true',
                    help='--rollback / --apply 时容忍指纹不符')
    ap.add_argument('--switches', choices=('keep', '1', '0'), default='keep',
                    help='cn_relay_unknown.txt：keep（默认：已有不动，缺失**不创建** = 关）/ 1 / 0')
    ap.add_argument('--switch-dir', default=None,
                    help='cn_relay_unknown.txt 所在目录（默认：线上路径 -> %s，其它 -> src 所在目录）'
                         % DEFAULT_SWITCH_DIR)
    ap.add_argument('--full-diff', action='store_true', help='--dry-run 连载荷正文一起 diff')
    ap.add_argument('--expect-sha', default=None, help='覆盖基线 sha256 期望值')
    ap.add_argument('--show-sha', action='store_true', help='只打印指纹（便于脚本取值）')
    args = ap.parse_args(argv)

    if not (args.apply or args.verify or args.dry_run or args.rollback or args.show_sha):
        ap.error('要指定 --verify / --dry-run / --apply / --rollback / --show-sha 之一')
    if not os.path.isfile(args.src):
        raise SystemExit('!! --src 不存在: %s\n'
                         '   （本脚本不会去猜沙箱副本；线上路径 = %s）' % (args.src, LIVE_SRC))
    want = args.expect_sha or BASE_SHA256

    raw = open(args.src, 'rb').read()
    orig = read_text(args.src)
    sha_now = hashlib.sha256(raw).hexdigest()
    print('src     : %s' % args.src)
    print('          %d 字节 / %d 行 / sha256 %s'
          % (len(raw), orig.count('\n'), sha_now))
    print('patched : %s' % ('是' if is_patched(orig) else '否'))

    if args.show_sha:
        print('size=%d sha256=%s patched=%s'
              % (len(raw), sha_now, '1' if is_patched(orig) else '0'))
        return 0

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
                    if s == want or args.force:
                        cand = p
                        break
                    print('  跳过备份 %s（sha256 %s 不是基线 %s）'
                          % (os.path.basename(p), s[:16], want[:16]))
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
            print('  残留 BAPATCH-RELAY 标记: %s'
                  % ('无（干净）' if 'BAPATCH-RELAY' not in text_b else '有残留!!'))
            return 0
        new_text, acts = build_removed(orig)
        for a in acts:
            print('  ' + a)
        if new_text == orig:
            print('  什么都没改（两块本来就不在）')
            return 0
        ok, err = compile_ok(new_text, args.src)
        if not ok:
            raise SystemExit('摘块后语法不过，拒绝写: %s' % err)
        bak = backup(args.src)
        write_text(args.src, new_text)
        now_raw = open(args.src, 'rb').read()
        print('  摘块回滚完成。备份=%s' % bak)
        print('  还原后 %d 字节 / sha256 %s'
              % (len(now_raw), hashlib.sha256(now_raw).hexdigest()))
        print('  残留 BAPATCH-RELAY 标记: %s'
              % ('无（干净）' if 'BAPATCH-RELAY' not in new_text else '有残留!!'))
        return 0

    # ---------------- apply / dry-run
    if args.apply or args.dry_run:
        if not is_patched(orig) and sha_now != want and not args.force:
            raise SystemExit(
                '!! 基线指纹不符，拒绝打补丁\n'
                '   实测 %d 字节 / sha256 %s\n'
                '   期望 %d 字节 / sha256 %s（= 基线 %s + patch_3 v1）\n'
                '   本补丁必须以打过 patch_3 的 103,900 B 文件为基线。\n'
                '   确认无误可加 --expect-sha <实测sha> 或 --force。'
                % (len(raw), sha_now, BASE_SIZE, want, P3_BASE_SHA256))
        before = (os.stat(args.src).st_mtime_ns, os.path.getsize(args.src))
        new_text, acts = build_patched(orig)
        print('\n== 插入动作 ==')
        for a in acts:
            print('  ' + a)
        if args.dry_run:
            print('\n== 将要插入的位置 ==')
            for unit in UNITS:
                rng = find_block(orig, unit)
                if rng:
                    print('  [%s] 已存在（第 %d-%d 行），--apply 会整块替换'
                          % (unit, rng[0] + 1, rng[1] + 1))
                    continue
                at = anchor_text(unit)
                i = orig.index(at)
                line_no = orig[:i].count('\n') + 1
                end_line = line_no + at.count('\n') - 1
                if isinstance(ANCHORS[unit], tuple) and ANCHORS[unit][1] == 'after':
                    print('  [%s] 插到第 %d-%d 行之后、第 %d 行之前（%s）'
                          % (unit, line_no, end_line, end_line + 1, ANCHOR_DESC[unit]))
                else:
                    print('  [%s] 插到第 %d 行之前（%s）' % (unit, line_no, ANCHOR_DESC[unit]))
            print('\n  ---- HOOK-A ----')
            for ln in unit_block(UNIT_HOOK_A).rstrip('\n').split('\n'):
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
        print('  （或 python patch_relay.py --src %s --rollback）' % args.src)
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
