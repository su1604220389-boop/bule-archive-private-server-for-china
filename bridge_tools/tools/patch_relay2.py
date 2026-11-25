#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patch_relay2.py -- 「名字已知、但没有真生成器」的协议也转发给本地 Shittim。

背景（已实测，见 PROGRESS_RELAY2.md §1）：
  * 上一版 `patch_relay.py`（产物 115,911 B /
    sha256 377176809ff25949a45e54224a274ad2b701e02c2d6d8a787a4a6eb16e815a07）
    把 HOOK-A 挂在 `_bridge()` 的 `if name is None:` 分支里 —— 只对「名字表里查不到」的
    协议生效。
  * 线上 `/www/wwwroot/bapatch/tools/protocol_names.txt` 存在（2434 B / 202 条名字），
    `Mission_List`(8000) / `Account_SetTutorial`(1006) 的名字**都在表里**，
    于是 `name is not None`，永远进不了 `if name is None:`，HOOK-A 一次都不执行。
  * 它们实际落在 path D：`if proto_int:` 的 min-envelope（proto_int 有值时），或者
    紧接着 `_generic_protocol_response()` 的 min+base 空壳（proto_int 为 None 时）。
    线上实测 8000 = 536 B、其它 512 B；官方同一个 /api/mission/list 回 268,396 B。
  * Shittim 侧有全部 handler（8000 实测回 804 B 真数据），所以这条路本来就是通的，
    只差把钩子挂到 `if proto_int:` **之前**。

本补丁做的事（只加两块，全部可整块摘掉）：
  1. PAYLOAD：一段自包含运行时模块（RL2_* / rl2_* 前缀，只用标准库），插在
     `if __name__ == '__main__':` 之前。它是运行时唯一真源，--verify 会把它重跑一遍单测。
  2. HOOK：插在 `if proto_int:` **之前**、且与它**同级**（8 空格，`_bridge` 的语句序列里）。
     开关 `cn_relay_known.txt` 打开时：
       cn_cipher.decode_packet -> 复用 relay v1 的 rl_request_json / rl_num_from_request
       拼请求取协议号 -> ensure_session(rec)（1014 铸 SessionKey，缺才注入）->
       post_gateway(req, timeout=8)（**8 秒**，不是默认 40 秒）->
       unwrap_gateway_response -> self._cn_envelope(协议名, obj, rec) 原样回。
     任何一步不成就 return None，原来的 `if proto_int:` / min+base / forward 完全照旧，
     绝不 500。

红线（都由 --verify 断言）：
  * RL2_HANDLED 里的 14 个协议号
    (1002, 1014, 1000, 1009, 1012, 1019, 2001, 3, 1005, 1017, 24000, 26000, 4000, 90004)
    **显式排除**：它们要么在更前面的分支就 return 了（结构上到不了这里），要么有真生成器
    （24000 / 1017 / 90004 在 `_generic_protocol_response()` 里）。排除表是双保险。
  * Account_CheckNexon(1014) 另有名字级排除（RL2_SKIP_NAMES）+ RL2_LOCAL.busy
    同线程重入保护：`ensure_session()` 内部那次 1014 直接走 post_gateway，不经过
    bridge，嵌套调用也被挡住 —— 不会递归。
  * 开关 `cn_relay_known.txt`：内容 1/on/true/yes = 开；0 / 缺失 / 读不到 = 关。
    **默认缺失 = 关**（打了补丁但行为与打补丁前完全一致）。
    `--switches keep`（默认）同样**不创建**缺失的开关文件。

开关查找顺序（直接用 relay v1 的 `rl_read_file`，与 patch_3 / patch_relay 一致）：
    bridge 所在目录 -> /www/wwwroot/bapatch/tools -> /www/wwwroot/bapatch

日志字段（写进 rec，全部可 grep）：
    relay2_on / relay2_used / relay2_code / relay2_resp_len / relay2_protocol /
    relay2_err / relay2_fallthrough
  辅助字段：relay2_num / relay2_name / relay2_session_injected / relay2_account_id /
    relay2_gateway_protocol / relay2_shittim_protocol / relay2_shittim_keys

缩进的坑（上一版踩过，这一版用断言钉死）：
  `if proto_int:` 在 `_bridge` 的**方法体**里（8 空格），不是某个分支体内。所以钩子的
  `try:` 必须也是 8 空格 —— 与 `if proto_int:` 同级、紧挨在它前面。写成 12 空格不会报
  语法错，但会掉进上面 P3-HOOK-D 那个 `except` 的**处理体**里（只有 p3_wants 抛异常时才
  执行），等于永远不生效。--verify 因此断言：
    * 钩子标记行缩进 == 8 == `if proto_int:` 的缩进（同级）
    * 钩子体缩进 == 12 == 锚点缩进 + 1 层
    * AST：`rl2_route` 所在的 Try 节点是 `_bridge` 函数体里 `if proto_int` 的**直接前一条**
      语句（parent 就是 FunctionDef，不是 ExceptHandler）
    * 反证：把这块整体右移 4 空格后，AST 上它确实掉进 ExceptHandler —— 说明这条断言真能
      抓住那个坑。

用法（--src 必须显式给，脚本不猜路径）：
    # 1) 自检（不写文件）：基线 sha 硬校验 + 锚点唯一 + 缩进/AST + 载荷单测
    python deploy/patch_relay2.py --src <file> --verify
    # 2) 只看插入位置和 diff（mtime 不变）
    python deploy/patch_relay2.py --src <file> --dry-run
    # 3) 打补丁（先备份 .relay2.bak.<ts>，再写，再自检）+ 开关
    python deploy/patch_relay2.py --src <file> --apply --switches 1
    # 4) 回滚（优先用 .relay2.bak.* 还原，零残留标记）
    python deploy/patch_relay2.py --src <file> --rollback
    # 5) 换一个基线指纹
    python deploy/patch_relay2.py --src <file> --verify --expect-sha <sha256>

本地演练（不碰线上）：
    python deploy/patch_relay2.py --src deploy/_sandbox/p3/account_auth_probe.py --apply --switches 1
"""
from __future__ import annotations

import argparse
import ast
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

# 基线指纹 = 线上现状（patch_3 v1 + patch_relay v1 已打）。--expect-sha 可覆盖。
BASE_SIZE = 115911
BASE_SHA256 = '377176809ff25949a45e54224a274ad2b701e02c2d6d8a787a4a6eb16e815a07'
# 上一层的基线（只用于文档 / 报错提示，不作为本补丁的基线）
RELAY1_SIZE = 103900
RELAY1_UPSTREAM_SHA256 = '563c1942289968e3f402c52eb89982cba75f9753ba85d13f6cca0be244ffc5c8'

VER = 'v1'
SWITCH_FILE = 'cn_relay_known.txt'
BACKUP_TAG = '.relay2.bak.'

# ---------------------------------------------------------------- 锚点
# 两个锚点都必须在目标文件里唯一；不唯一就拒绝动文件（见 anchor_pos）。
# HOOK 锚点 = `if proto_int:` 那一行 + 它的第一行函数体（两行一起，钉死是 path D 的那个
# 分支，不会被别处的同形代码骗到）。整块钩子插在它**之前**（mode='before'）。
ANCHOR_HOOK = ("        if proto_int:\n"
               "            obj = cn_nick.build_min_response(proto_int)\n")
# 插完以后必须仍然完整地在钩子后面（结构完好性断言）
HOOK_TAIL = ("        if proto_int:\n"
             "            obj = cn_nick.build_min_response(proto_int)\n"
             "            rec['fallback'] = 'min-envelope'\n"
             "            rec['fallback_protocol'] = proto_int\n"
             "            proto_name = name if (name and name != 'Unknown') else 'Account_Nickname'\n"
             "            return self._cn_send_envelope(proto_name, obj, rec)\n"
             "        got = self._generic_protocol_response(proto_str, packet_b64, rec, name=name)\n")
ANCHOR_PAYLOAD = "if __name__ == '__main__':\n"

# 上一版补丁的块（必须原样还在；relay2 复用它的 RL_PAYLOAD 函数）
RELAY1_MARKS = ('BAPATCH-RELAY-PAYLOAD v1', 'BAPATCH-RELAY-HOOK-A v1')
RELAY1_REUSED = ('rl_read_file', 'rl_request_json', 'rl_num_from_request')

# 既有补丁的块（一个字节都不许被我们动到）
OTHER_MARKS = ('BAPATCH-P3-PAYLOAD', 'BAPATCH-P3-HOOK-E', 'BAPATCH-P3-HOOK-D',
               'BAPATCH-P3-HOOK-G', 'BAPATCH-SIMPLE-PAYLOAD',
               'BAPATCH-SIMPLE-HOOK-D', 'BAPATCH-SIMPLE-HOOK-G',
               'BAPATCH-RELAY-PAYLOAD', 'BAPATCH-RELAY-HOOK-A')

UNIT_PAYLOAD = 'PAYLOAD'
UNIT_HOOK = 'HOOK'
UNITS = (UNIT_PAYLOAD, UNIT_HOOK)

ANCHORS = {UNIT_PAYLOAD: (ANCHOR_PAYLOAD, 'before'),
           UNIT_HOOK: (ANCHOR_HOOK, 'before')}

ANCHOR_DESC = {
    UNIT_PAYLOAD: "bridge 顶层，`if __name__ == '__main__':` 之前",
    UNIT_HOOK: "_bridge() 里 path D 的 `if proto_int:` **之前、同级**（8 空格），"
               "在 P3-HOOK-D 之后",
}

# 期望的钩子缩进（`_bridge` 方法体 = 8 空格；`if proto_int:` 也是 8）
HOOK_INDENT = 8

# ================================================================ 内嵌运行时（唯一真源）
RL2_PAYLOAD_SRC = r'''# -*- coding: utf-8 -*-
"""名字已知但没有真生成器的协议 -> 本地 Shittim 转发（bridge 运行时真源）。

为什么要这一版：patch_relay.py 的 HOOK-A 挂在 `if name is None:` 分支里，只对「名字表里
查不到」的协议生效。但 protocol_names.txt 里 Mission_List(8000) / Account_SetTutorial(1006)
这些名字都在，所以它们进不了那个分支，只能拿到 min+base 空壳。本模块的钩子挂在
`if proto_int:` **之前**（与它同级、都在 `_bridge` 的语句序列里），名字已知也照样接管。

做法（开关 cn_relay_known.txt 打开时）：
  ① cn_cipher.decode_packet(packet_b64, proto_str) 解出客户端真实请求（与 HOOK-A 同一个解码器）；
  ② 复用 relay v1 的 RL_PAYLOAD 里已经验证过的 rl_request_json / rl_num_from_request
     拼回发给 Shittim 的请求、取出协议号 —— 不另写一套；
  ③ ensure_session(rec) 打 Account_CheckNexon(1014) 拿真 SessionKey（缺才注入）；
  ④ post_gateway(req, timeout=8) POST 到本地 Shittim 的 /api/gateway。
     8 秒而不是默认 40 秒：这条路径每个请求都要走，40 秒会把客户端拖到超时；
  ⑤ unwrap_gateway_response(raw) -> dict 就用 self._cn_envelope(协议名, obj, rec) 返回。
     （传协议名不是 token：_cn_envelope 内部会算 base32(md5(名字))，那正好等于客户端
      请求里带的 token；传 token 会二次哈希，外层 protocol 就对不上了。）
  任何一步不成就 return None，原逻辑（if proto_int 的 min-envelope / min+base / forward）
  照旧，绝不 500。

红线：
  * RL2_HANDLED（1002/1014/1000/1009/1012/1019/2001/3/1005/1017/24000/26000/4000/90004）
    一律不碰：要么在更前面的分支已经 return（结构上到不了这里），要么有真生成器
    （24000 / 1017 / 90004 在 _generic_protocol_response 里）。排除表是双保险。
  * Account_CheckNexon 名字级排除 + RL2_LOCAL.busy 同线程重入保护：ensure_session 内部
    那次 1014 直接走 post_gateway、不经过 bridge，嵌套调用也被挡住，不会递归。
  * 开关缺失 / 不是真值 => 完全不改行为（fail-safe）。

依赖（运行时从 bridge 全局取，取不到就落回，不抛）：
    cn_cipher.decode_packet / ensure_session / post_gateway / unwrap_gateway_response
    rl_request_json / rl_num_from_request / rl_read_file（= patch_relay.py 的 RL_PAYLOAD）

开关查找顺序（委托 rl_read_file，与 patch_3 / patch_relay 一致）：
    bridge 所在目录 -> /www/wwwroot/bapatch/tools -> /www/wwwroot/bapatch

日志字段（写进 rec）：
    relay2_on / relay2_used / relay2_code / relay2_resp_len / relay2_protocol /
    relay2_err / relay2_fallthrough
  辅助：relay2_num / relay2_name / relay2_session_injected / relay2_account_id /
    relay2_gateway_protocol / relay2_shittim_protocol / relay2_shittim_keys

约定（原样贴进 bridge 模块命名空间）：
  * 不写 from __future__，不写 __main__ 块；
  * 只用标准库，全部 _rl2* 别名 import，不污染 bridge 现有全局名；
  * import 期不碰文件系统、不碰网络；bridge 依赖一律 globals().get() 运行时取。
"""
import os as _rl2os
import threading as _rl2threading

RL2_VER = 'v1'
RL2_SWITCH_FILE = 'cn_relay_known.txt'
RL2_FALLBACK_DIRS = ('/www/wwwroot/bapatch/tools', '/www/wwwroot/bapatch')
# 转发超时：这条路径每个请求都走，必须短（默认 40 秒会让客户端超时）
RL2_TIMEOUT = 8
# 有真生成器 / 更前面的专分支负责的协议号：本 hook 一律不碰（双保险）
RL2_HANDLED = frozenset((1002, 1014, 1000, 1009, 1012, 1019, 2001, 3, 1005, 1017,
                         24000, 26000, 4000, 90004))
RL2_SKIP_NAMES = frozenset(('Account_CheckNexon', 'Account_Auth', 'Account_Auth2',
                            'Account_LoginSync', 'Account_Nickname', 'Account_CallName'))
RL2_LOCAL = _rl2threading.local()


# ---------------------------------------------------------------- 开关
def rl2_dirs():
    """开关文件的候选目录（有序）：bridge 目录 -> bapatch/tools -> bapatch。"""
    out = []
    try:
        out.append(_rl2os.path.dirname(_rl2os.path.abspath(__file__)))
    except Exception:
        pass
    for d in RL2_FALLBACK_DIRS:
        if d not in out:
            out.append(d)
    return out


def rl2_read_file(fn, base=None):
    """读一个小开关文件 -> (路径, 内容)。优先复用 relay v1 的 rl_read_file。"""
    rd = globals().get('rl_read_file')
    if callable(rd):
        try:
            return rd(fn, base)
        except Exception:
            pass
    dirs = ([base] if base else []) + rl2_dirs()
    for d in dirs:
        if not d:
            continue
        p = _rl2os.path.join(d, fn)
        try:
            with open(p, 'r') as fh:
                return p, fh.read().strip()
        except Exception:
            continue
    return None, None


def rl2_switch_on(base=None):
    """cn_relay_known.txt 是否打开。缺失 / 读不到 / 内容不是真值 -> False（fail-safe）。"""
    _p, v = rl2_read_file(RL2_SWITCH_FILE, base)
    if v is None:
        return False
    return v.strip().lower() in ('1', 'on', 'true', 'yes')


# ---------------------------------------------------------------- 转发管线
def rl2_route(rec, proto_str, packet_b64, name=None, envelope=None, base=None):
    """名字已知（但没有真生成器）的协议接管线。接管 -> (code, body, ctype)；不管 -> None。

    envelope 必须注入（bridge 传 self._cn_envelope）：
        envelope(协议名, inner_obj, rec) -> (code, body, ctype)
      （传**协议名**不是客户端 token：_cn_envelope 内部算 base32(md5(名字))，那才等于
        客户端请求里带的 token；传 token 会二次哈希。）
    任何异常都不在这里吞：由 HOOK 的 try/except 兜住并记 rec['relay2_err']。
    """
    if not isinstance(rec, dict):
        rec = {}
    on = bool(rl2_switch_on(base))
    rec['relay2_on'] = on
    rec['relay2_err'] = ''
    if not on:
        rec['relay2_fallthrough'] = 'switch-off'
        return None
    if isinstance(name, str) and name in RL2_SKIP_NAMES:
        rec['relay2_fallthrough'] = 'skip-name'
        return None
    if getattr(RL2_LOCAL, 'busy', False):
        rec['relay2_fallthrough'] = 'reentrant'
        return None
    RL2_LOCAL.busy = True
    try:
        return _rl2_relay_once(rec, proto_str, packet_b64, name, envelope)
    finally:
        RL2_LOCAL.busy = False


def _rl2_relay_once(rec, proto_str, packet_b64, name, envelope):
    """真正干活的只有这一段；异常往上抛（HOOK 负责留痕 + 落回）。"""
    dec = globals().get('cn_cipher')
    if dec is None or not hasattr(dec, 'decode_packet'):
        rec['relay2_err'] = 'cn_cipher.decode_packet unavailable'
        rec['relay2_fallthrough'] = 'no-cn_cipher'
        return None
    # 复用 patch_relay.py 的 RL_PAYLOAD：请求重建 / 协议号提取只信这一份实现
    req_builder = globals().get('rl_request_json')
    num_reader = globals().get('rl_num_from_request')
    if not (callable(req_builder) and callable(num_reader)):
        rec['relay2_err'] = ('relay v1 payload missing: rl_request_json=%r '
                             'rl_num_from_request=%r'
                             % (callable(req_builder), callable(num_reader)))
        rec['relay2_fallthrough'] = 'no-relay1'
        return None
    try:
        decoded = dec.decode_packet(packet_b64, proto_str)
    except Exception as e:
        rec['relay2_err'] = repr(e)
        rec['relay2_fallthrough'] = 'decode'
        return None
    req = req_builder(decoded, rec)
    if not isinstance(req, dict):
        rec['relay2_fallthrough'] = 'decode-json'
        return None
    num = num_reader(decoded, req)
    rec['relay2_num'] = num
    rec['relay2_name'] = name if isinstance(name, str) else None
    if num is None:
        rec['relay2_fallthrough'] = 'no-protocol-num'
        return None
    if num in RL2_HANDLED:
        # 1002/1014/3/1005/1017/24000/26000/4000/90004 … 有真生成器或专分支：绝不抢
        rec['relay2_fallthrough'] = 'handled-%d' % num
        return None
    ensure = globals().get('ensure_session')
    post = globals().get('post_gateway')
    unwrap = globals().get('unwrap_gateway_response')
    if not (callable(ensure) and callable(post) and callable(unwrap)):
        rec['relay2_err'] = ('bridge deps missing: ensure_session=%r post_gateway=%r '
                             'unwrap_gateway_response=%r'
                             % (callable(ensure), callable(post), callable(unwrap)))
        rec['relay2_fallthrough'] = 'no-deps'
        return None
    sk, aid = ensure(rec)
    if sk is None:
        rec['relay2_fallthrough'] = 'ensure-session'
        return None
    injected = not req.get('SessionKey')
    if injected:
        req['SessionKey'] = sk
    rec['relay2_session_injected'] = bool(injected)
    rec['relay2_account_id'] = aid
    try:
        code, raw = post(req, timeout=RL2_TIMEOUT)
    except TypeError:
        # 变体 bridge 的 post_gateway 可能没有 timeout 形参：退回默认总比 500 好
        code, raw = post(req)
    raw = raw or b''
    rec['relay2_code'] = code
    rec['relay2_resp_len'] = len(raw)
    if code == 0:
        rec['relay2_err'] = 'gateway unreachable/timeout: %r' % (raw[:160],)
        rec['relay2_fallthrough'] = 'gateway-code-0'
        return None
    gp, obj = unwrap(raw)
    if gp is None or isinstance(gp, (str, int)):
        rec['relay2_gateway_protocol'] = gp
    else:
        rec['relay2_gateway_protocol'] = repr(gp)
    if not isinstance(obj, dict):
        rec['relay2_err'] = ('shittim response not dict (code=%r len=%d body=%r)'
                             % (code, len(raw), raw[:160]))
        rec['relay2_fallthrough'] = 'shittim-non-dict'
        return None
    rec['relay2_protocol'] = req.get('Protocol') if req.get('Protocol') is not None else num
    rec['relay2_protocol_num'] = num
    if isinstance(obj.get('Protocol'), int):
        rec['relay2_shittim_protocol'] = obj.get('Protocol')
    rec['relay2_shittim_keys'] = len(obj)
    out = None
    # 注意：bridge 的 _cn_envelope(proto_name, ...) 会自己算 base32(md5(proto_name))，
    # 客户端请求里带的正是 base32(md5(协议名))。所以这里必须传**协议名**，不能传客户端
    # 的 token —— 传 token 会变成 b32md5(b32md5(name))，外层 protocol 就和客户端对不上了。
    proto_name = name if (isinstance(name, str) and name and name != 'Unknown') else proto_str
    rec['relay2_envelope_name'] = proto_name
    if callable(envelope):
        out = envelope(proto_name, obj, rec)
    if out is None:
        rec['relay2_fallthrough'] = 'envelope'
        return None
    rec['relay2_used'] = True
    rec['relay2_fallthrough'] = ''
    return out
'''

# ---------------------------------------------------------------- hook 的代码
# 缩进：`if proto_int:` 在 `_bridge` 的方法体里（8 空格），所以 `try:` 也是 8 空格 ——
# 与它同级、紧挨在它前面。写成 12 空格不会报语法错，但会掉进上面 P3-HOOK-D 的 except
# 处理体里（只有 p3_wants 抛异常时才执行）—— --verify 有缩进 + AST 断言专门抓这个。
HOOK_BODY = """        # >>> BAPATCH-RELAY2-HOOK %(ver)s BEGIN >>>
        # 名字已知、但没有真生成器的协议（8000 / 1006 / 8006 / 90011 / 35003 / 16000 …）：
        # 开关 cn_relay_known.txt 打开时，把客户端真实请求转发给本地 Shittim
        # (/api/gateway)，拿到 dict 回包就用 _cn_envelope 包成 CN 信封返回。
        # 挂在这里（`if proto_int:` 之前、同级）等于同时接住两条空壳出口：
        #   proto_int 有值 -> 原本走下面的 min-envelope；为 None -> 走 _generic_protocol_response 的 min+base。
        # 任何一步不成就原路落回（下面的代码完全不变，绝不 500）。
        # 有真生成器的协议号由 RL2_HANDLED 显式排除；Account_CheckNexon(1014) 只由
        # ensure_session 内部调用，另有名字级排除 + 同线程重入保护。开关缺失 = 关。
        try:
            _rl2_a = rl2_route(rec, proto_str, packet_b64, name, self._cn_envelope)
            if _rl2_a is not None:
                return _rl2_a
        except Exception as _rl2_a_err:
            rec['relay2_err'] = repr(_rl2_a_err)
            rec['relay2_fallthrough'] = 'exception'
        # <<< BAPATCH-RELAY2-HOOK %(ver)s END <<<
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
    return '# >>> BAPATCH-RELAY2-%s %s BEGIN' % (unit, VER)


def mark_end(unit):
    return '# <<< BAPATCH-RELAY2-%s %s END <<<' % (unit, VER)


def payload_body():
    """内嵌运行时正文（唯一真源 = 本文件里的 RL2_PAYLOAD_SRC）。"""
    return RL2_PAYLOAD_SRC.replace('\r\n', '\n').rstrip('\n') + '\n'


def unit_block(unit, body=None):
    """整块文本（含 BEGIN/END 标记）。PAYLOAD 顶格，HOOK 按函数体缩进。"""
    if unit == UNIT_PAYLOAD:
        src = payload_body() if body is None else body
        head = ('%s >>> (deploy/patch_relay2.py 内嵌 RL2_PAYLOAD_SRC，sha256=%s) >>>'
                % (mark_begin(UNIT_PAYLOAD), sha256_text(src)))
        return head + '\n' + src + mark_end(UNIT_PAYLOAD) + '\n'
    return HOOK_BODY % {'ver': VER}


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


def count_any_marks(text):
    """所有 BAPATCH-RELAY2 标记的总数（BEGIN+END = 4 块时 = 4）。"""
    return text.count('BAPATCH-RELAY2')


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


def line_indent(ln):
    return len(ln) - len(ln.lstrip(' '))


def indent_at(text, pos):
    """pos 所在行的缩进空格数。"""
    start = text.rfind('\n', 0, pos) + 1
    end = text.find('\n', pos)
    if end < 0:
        end = len(text)
    return line_indent(text[start:end])


def mask_payload(text):
    """给 diff 用：把 PAYLOAD 正文压成一行占位，避免 260+ 行噪声。"""
    rng = find_block(text, UNIT_PAYLOAD)
    if not rng:
        return text
    lines = text.split('\n')
    n = rng[1] - rng[0] - 1
    ph = '# ...[%d 行运行时模块原样内嵌自 patch_relay2.py 的 RL2_PAYLOAD_SRC，--full-diff 查看]...' % n
    return '\n'.join(lines[:rng[0] + 1] + [ph] + lines[rng[1]:])


# ================================================================ AST 工具（缩进坑的硬断言）
def ast_find_bridge(tree):
    """-> _bridge 的 FunctionDef 节点（全文件唯一）。"""
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == '_bridge':
            found.append(node)
    if len(found) != 1:
        raise ValueError('_bridge 定义数量 = %d（要求恰好 1 个）' % len(found))
    return found[0]


def ast_parent_map(tree):
    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    return parents


def ast_proto_int_index(bridge):
    """_bridge 函数体里 `if proto_int:` 语句的下标（必须是直接语句）。"""
    for i, stmt in enumerate(bridge.body):
        if isinstance(stmt, ast.If) and isinstance(stmt.test, ast.Name) \
                and stmt.test.id == 'proto_int':
            return i
    return None


def ast_find_rl2_call(tree):
    """-> `rl2_route(...)` 的 Call 节点（全树唯一）。"""
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == 'rl2_route':
            return node
    return None


def ast_enclosing_try(tree, parents=None):
    """-> 包含 rl2_route(...) 调用的**最近的那个** Try 节点（沿 parent 链向上找）。"""
    parents = parents if parents is not None else ast_parent_map(tree)
    node = ast_find_rl2_call(tree)
    while node is not None and not isinstance(node, ast.Try):
        node = parents.get(node)
    return node


def ast_hook_try(tree, text):
    """-> (Try 节点, _bridge, 它在 _bridge.body 里的下标或 None, 父节点类型名)。

    下标 == None 就说明这块**不在 `_bridge` 的语句序列里**（缩进错一层时就是这样）。
    """
    parents = ast_parent_map(tree)
    bridge = ast_find_bridge(tree)
    node = ast_enclosing_try(tree, parents)
    if node is None:
        return None, bridge, None, None
    owner = type(parents.get(node)).__name__
    idx = None
    for i, stmt in enumerate(bridge.body):
        if stmt is node:
            idx = i
            break
    return node, bridge, idx, owner


def ast_try_owner(tree, text):
    """-> (含 rl2_route 的 Try 的父节点类型名, 父节点)。"""
    parents = ast_parent_map(tree)
    node = ast_enclosing_try(tree, parents)
    if node is None:
        return None, None
    return type(parents.get(node)).__name__, parents.get(node)


def indent_variant(text, unit, extra=4):
    """把某块整体右移 extra 空格（模拟「缩进错一层」的坑），返回新文本。"""
    rng = find_block(text, unit)
    if not rng:
        return None
    lines = text.split('\n')
    pad = ' ' * extra
    for i in range(rng[0], rng[1] + 1):
        if lines[i].strip():
            lines[i] = pad + lines[i]
    return '\n'.join(lines)


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
        if unit == UNIT_HOOK:
            acts.append('       -> 插入后 HOOK 落在第 %d 行，紧挨在 `if proto_int:`（第 %d 行）'
                        '之前，两者同为 %d 空格缩进'
                        % (text[:text.index(mark_begin(UNIT_HOOK))].count('\n') + 1,
                           line_no + nlines, HOOK_INDENT))
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
    bak = '%s%s%s' % (src, BACKUP_TAG, time.strftime('%Y%m%d-%H%M%S'))
    shutil.copy2(src, bak)
    return bak


def find_backups(src):
    d = os.path.dirname(os.path.abspath(src))
    base = os.path.basename(src) + BACKUP_TAG
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
    """写开关。keep 在文件**缺失时不创建**（红线：默认必须是不存在 = 关）。"""
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


# ================================================================ 载入内嵌运行时 / 单测
def load_embedded_ns(src_text):
    body = extract_block_body(src_text, UNIT_PAYLOAD)
    if body is None:
        return None, '内嵌 PAYLOAD 块不存在'
    ns = {'__name__': 'embedded_relay2_payload',
          '__file__': os.path.join(HERE, 'patch_relay2.py')}
    try:
        exec(compile(body, '<embedded relay2 payload>', 'exec'), ns)
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
    """把内嵌运行时当成独立模块跑一遍单测（不碰网络、不碰 bridge）。

    这里给 rl_request_json / rl_num_from_request 用极简替身 —— relay2 只负责「调用」它们，
    真实拼接逻辑由 relay v1 的 --verify 和 _relay2_replay.py 的整链测试覆盖。
    """
    NS = ns

    def put(name, val):
        NS[name] = val

    def drop(*names):
        for n in names:
            NS.pop(n, None)

    # ---- 常量 / 开关
    add(NS['RL2_TIMEOUT'] == 8,
        '转发超时 RL2_TIMEOUT == 8 秒（不是 post_gateway 默认的 40 秒）')
    want_handled = set((1002, 1014, 1000, 1009, 1012, 1019, 2001, 3, 1005, 1017,
                        24000, 26000, 4000, 90004))
    add(set(NS['RL2_HANDLED']) == want_handled,
        'RL2_HANDLED == 14 个「绝不能被抢」的协议号（实测 %d 个：%r）'
        % (len(NS['RL2_HANDLED']), sorted(NS['RL2_HANDLED'])))
    add('Account_CheckNexon' in NS['RL2_SKIP_NAMES'],
        'RL2_SKIP_NAMES 覆盖 Account_CheckNexon（名字级双保险）')
    add(NS['RL2_SWITCH_FILE'] == 'cn_relay_known.txt',
        '开关文件 == cn_relay_known.txt（与 relay v1 的 cn_relay_unknown.txt 独立）')
    _dirs = NS['rl2_dirs']()
    add(_dirs and _dirs[0] == os.path.dirname(os.path.abspath(NS['__file__']))
        and '/www/wwwroot/bapatch/tools' in _dirs and '/www/wwwroot/bapatch' in _dirs
        and _dirs.index('/www/wwwroot/bapatch/tools') < _dirs.index('/www/wwwroot/bapatch'),
        '开关查找顺序 == bridge 目录 -> /www/wwwroot/bapatch/tools -> /www/wwwroot/bapatch（%r）'
        % (_dirs,))
    add(NS['rl2_switch_on'](tmp) is False, 'cn_relay_known.txt 缺失 -> 判定「关」（fail-safe）')
    sw = os.path.join(tmp, NS['RL2_SWITCH_FILE'])
    for text, want, label in (('1\n', True, '1'), ('on\n', True, 'on'),
                              (' yes \n', True, 'yes'), ('TRUE\n', True, 'TRUE'),
                              ('0\n', False, '0'), ('\n', False, '空'),
                              ('off\n', False, 'off')):
        write_text(sw, text)
        add(NS['rl2_switch_on'](tmp) is want,
            'cn_relay_known.txt=%s -> %r' % (label, want))
    os.remove(sw)
    add(NS['rl2_switch_on'](tmp) is False, '删除开关文件 -> 又变回「关」')

    # ---- 开关读取委托给 relay v1 的 rl_read_file
    calls = []
    put('rl_read_file', lambda fn, base=None: (calls.append((fn, base)) or ('/x/' + fn, '1')))
    add(NS['rl2_switch_on'](tmp) is True,
        'rl_read_file 存在时委托给它（复用 relay v1 的查找顺序，不另写一套）')
    add(bool(calls) and calls[-1][0] == 'cn_relay_known.txt',
        '委托时文件名 == cn_relay_known.txt（%r）' % (calls[-1],))
    drop('rl_read_file')

    # ---- 替身：relay v1 的两个函数 + bridge 的四件套
    def fake_req_json(decoded, rec=None):
        # 返回浅拷贝（真实现每次都新建 dict，替身也别把 SessionKey 写回共享样本）；
        # 空 / 缺失 -> None（与 rl_request_json 一致：它只在真拿到 dict 时才返回）
        d = decoded.get('req') if isinstance(decoded, dict) else None
        if not isinstance(d, dict) or not d:
            return None
        return dict(d)

    def fake_num(decoded, req=None):
        return decoded.get('num') if isinstance(decoded, dict) else None

    good = {'req': {'Protocol': 8000, 'Hash': 8000 << 32}, 'num': 8000}
    enveloped = []

    def fake_env(proto_str, obj, rec):
        enveloped.append((proto_str, obj))
        return 200, b'RELAY2-OK', 'text/plain; charset=utf-8'

    write_text(sw, '1\n')

    # ---- 缺 relay v1
    put('cn_cipher', _FakeCnCipher(good))
    rec = {}
    out = NS['rl2_route'](rec, 'TOKEN', '<REDACTED_TOKEN>', 'Mission_List', fake_env, tmp)
    add(out is None and rec.get('relay2_fallthrough') == 'no-relay1'
        and 'relay v1' in str(rec.get('relay2_err')),
        '没有 relay v1 的 rl_request_json/rl_num_from_request -> 落回（fallthrough=no-relay1）')
    put('rl_request_json', fake_req_json)
    put('rl_num_from_request', fake_num)

    # ---- 关 == 完全不接管（即便名字已知）
    write_text(sw, '0\n')
    rec = {}
    out = NS['rl2_route'](rec, 'TOKEN', '<REDACTED_TOKEN>', 'Mission_List', fake_env, tmp)
    add(out is None and rec.get('relay2_on') is False
        and rec.get('relay2_fallthrough') == 'switch-off',
        '开关关：名字已知也照样返回 None（relay2_on=False / fallthrough=switch-off）')
    write_text(sw, '1\n')

    # ---- 名字层排除
    rec = {}
    out = NS['rl2_route'](rec, 'TOKEN', '<REDACTED_TOKEN>', 'Account_CheckNexon', fake_env, tmp)
    add(out is None and rec.get('relay2_fallthrough') == 'skip-name',
        '名字 = Account_CheckNexon -> 不碰（fallthrough=skip-name，双保险）')

    # ---- 14 个协议号排除
    bad = []
    for num in sorted(want_handled):
        put('cn_cipher', _FakeCnCipher({'req': {'Protocol': num, 'Hash': num << 32},
                                        'num': num}))
        rec = {}
        out = NS['rl2_route'](rec, 'TOKEN', '<REDACTED_TOKEN>', 'Item_List', fake_env, tmp)
        if not (out is None and rec.get('relay2_fallthrough') == 'handled-%d' % num):
            bad.append((num, rec.get('relay2_fallthrough')))
    add(not bad, '14 个专分支/真生成器协议号一律不抢（fallthrough=handled-N）%s'
        % ('' if not bad else '  例外=%r' % (bad,)))

    # ---- 重入
    rec = {}
    NS['RL2_LOCAL'].busy = True
    try:
        out = NS['rl2_route'](rec, 'TOKEN', '<REDACTED_TOKEN>', 'Mission_List', fake_env, tmp)
    finally:
        NS['RL2_LOCAL'].busy = False
    add(out is None and rec.get('relay2_fallthrough') == 'reentrant',
        '同线程重入保护：busy=True -> 不接管（fallthrough=reentrant）')

    # ---- 依赖缺失 / 解码失败
    put('cn_cipher', _FakeCnCipher(good))
    drop('ensure_session', 'post_gateway', 'unwrap_gateway_response')
    rec = {}
    out = NS['rl2_route'](rec, 'TOKEN', '<REDACTED_TOKEN>', 'Mission_List', fake_env, tmp)
    add(out is None and rec.get('relay2_fallthrough') == 'no-deps',
        'bridge 四件套缺失 -> 落回（fallthrough=no-deps）')
    put('ensure_session', lambda rec: ({'AccountServerId': 2, 'MxToken': 'M' * 64}, 2))
    put('unwrap_gateway_response', lambda raw: (None, None))
    put('post_gateway', lambda obj, timeout=40: (200, b'{}'))
    drop('cn_cipher')
    rec = {}
    out = NS['rl2_route'](rec, 'TOKEN', '<REDACTED_TOKEN>', 'Mission_List', fake_env, tmp)
    add(out is None and rec.get('relay2_fallthrough') == 'no-cn_cipher',
        '没有 cn_cipher.decode_packet -> 落回（fallthrough=no-cn_cipher）')
    put('cn_cipher', _FakeCnCipher(error=ValueError('bad packet')))
    rec = {}
    out = NS['rl2_route'](rec, 'TOKEN', '<REDACTED_TOKEN>', 'Mission_List', fake_env, tmp)
    add(out is None and rec.get('relay2_fallthrough') == 'decode'
        and 'bad packet' in str(rec.get('relay2_err')),
        'decode_packet 抛错 -> 落回 + relay2_err=%r' % (rec.get('relay2_err'),))
    put('cn_cipher', _FakeCnCipher({'req': None, 'num': 8000}))
    rec = {}
    out = NS['rl2_route'](rec, 'TOKEN', '<REDACTED_TOKEN>', 'Mission_List', fake_env, tmp)
    add(out is None and rec.get('relay2_fallthrough') == 'decode-json',
        '拼不出请求 dict -> 落回（fallthrough=decode-json）')
    put('cn_cipher', _FakeCnCipher({'req': {'Protocol': 8000}, 'num': None}))
    rec = {}
    out = NS['rl2_route'](rec, 'TOKEN', '<REDACTED_TOKEN>', 'Mission_List', fake_env, tmp)
    add(out is None and rec.get('relay2_fallthrough') == 'no-protocol-num',
        '取不到协议号 -> 落回（fallthrough=no-protocol-num）')

    # ---- 完整转发管线
    put('cn_cipher', _FakeCnCipher(good))
    sent = []

    def fake_post(obj, timeout=40):
        sent.append((obj, timeout))
        return 200, (b'{"protocol":"Mission_List","packet":"{\\"Protocol\\":8000,'
                     b'\\"Echo\\":[\\"Hash\\"]}"}')

    put('post_gateway', fake_post)
    put('unwrap_gateway_response',
        lambda raw: ('Mission_List', {'Protocol': 8000, 'Echo': ['Hash']}))
    rec = {}
    out = NS['rl2_route'](rec, 'TOKEN_8000', 'B64', 'Mission_List', fake_env, tmp)
    add(out == (200, b'RELAY2-OK', 'text/plain; charset=utf-8'),
        '开关开 + 全链路替身 -> 返回 _cn_envelope 的 (200, body, ctype)')
    add(rec.get('relay2_used') is True and rec.get('relay2_on') is True,
        'relay2_used=True / relay2_on=True')
    add(sent and sent[-1][1] == 8,
        'post_gateway 收到 timeout=8（实测 %r）'
        % (sent[-1][1] if sent else None,))
    add(sent and sent[-1][0].get('Protocol') == 8000,
        '发给 Shittim 的请求带 Protocol=8000（%r）'
        % (sent[-1][0].get('Protocol') if sent else None,))
    add(rec.get('relay2_session_injected') is True and sent
        and isinstance(sent[-1][0].get('SessionKey'), dict),
        'SessionKey 缺省时注入（relay2_session_injected=%r）'
        % (rec.get('relay2_session_injected'),))
    add(rec.get('relay2_protocol') == 8000 and rec.get('relay2_protocol_num') == 8000,
        'relay2_protocol=%r / relay2_protocol_num=%r'
        % (rec.get('relay2_protocol'), rec.get('relay2_protocol_num')))
    add(rec.get('relay2_code') == 200 and rec.get('relay2_resp_len', 0) > 0,
        'relay2_code=%r / relay2_resp_len=%r'
        % (rec.get('relay2_code'), rec.get('relay2_resp_len')))
    add(enveloped and enveloped[-1][0] == 'Mission_List'
        and enveloped[-1][1].get('Protocol') == 8000,
        '响应经 envelope(协议名, obj, rec) 出口（proto_name=%r, keys=%r）—— 传名字不传 token'
        % (enveloped[-1][0] if enveloped else None,
           sorted(enveloped[-1][1]) if enveloped else None))
    need = ('relay2_on', 'relay2_used', 'relay2_code', 'relay2_resp_len',
            'relay2_protocol', 'relay2_err', 'relay2_fallthrough')
    miss = [k for k in need if k not in rec]
    add(not miss, '成功路径的 7 个日志字段齐备%s'
        % ('' if not miss else '（缺 %r）' % (miss,)))

    # 已有 SessionKey -> 不覆盖
    sent[:] = []
    put('cn_cipher', _FakeCnCipher({'req': {'Protocol': 8000, 'Hash': 8000 << 32,
                                            'SessionKey': {'AccountServerId': 7}},
                                    'num': 8000}))
    rec = {}
    out = NS['rl2_route'](rec, 'TOKEN_8000', 'B64', 'Mission_List', fake_env, tmp)
    add(out is not None and rec.get('relay2_session_injected') is False
        and sent and sent[-1][0]['SessionKey'] == {'AccountServerId': 7},
        '请求里已有 SessionKey -> 不覆盖（relay2_session_injected=False）')

    # post_gateway 没有 timeout 形参 -> 退回无参调用（只发一次）
    put('cn_cipher', _FakeCnCipher(good))
    sent2 = []

    def post_no_timeout(obj):
        sent2.append(obj)
        return 200, b'{"protocol":"Mission_List","packet":"{\\"Protocol\\":8000}"}'

    put('post_gateway', post_no_timeout)
    rec = {}
    out = NS['rl2_route'](rec, 'TOKEN_8000', 'B64', 'Mission_List', fake_env, tmp)
    add(out is not None and rec.get('relay2_used') is True and len(sent2) == 1,
        'post_gateway 没有 timeout 形参（TypeError）-> 退回无参调用且只发一次（%d 次）'
        % len(sent2))

    # ---- ensure_session 失败
    sent[:] = []
    put('post_gateway', fake_post)
    put('cn_cipher', _FakeCnCipher(good))
    put('ensure_session', lambda rec: (None, None))
    rec = {}
    out = NS['rl2_route'](rec, 'TOKEN_8000', 'B64', 'Mission_List', fake_env, tmp)
    add(out is None and rec.get('relay2_fallthrough') == 'ensure-session'
        and rec.get('relay2_used') is None and len(sent) == 0,
        'ensure_session 回 None（1014 失败）-> 落回，且没有向 Shittim 发请求（%d 次）'
        % len(sent))
    put('ensure_session', lambda rec: ({'AccountServerId': 2, 'MxToken': 'M' * 64}, 2))

    # ---- Shittim 500 / 超时 / 非 dict
    put('post_gateway', lambda obj, timeout=40: (500, b'{"error":"boom"}'))
    put('unwrap_gateway_response', lambda raw: (None, None))
    rec = {}
    out = NS['rl2_route'](rec, 'TOKEN_8000', 'B64', 'Mission_List', fake_env, tmp)
    add(out is None and rec.get('relay2_used') is None and bool(rec.get('relay2_err'))
        and rec.get('relay2_fallthrough') == 'shittim-non-dict',
        'Shittim 回 500 -> 落回 + relay2_err=%r' % (rec.get('relay2_err'),))
    put('post_gateway', lambda obj, timeout=40: (0, b'{"error":"timed out"}'))
    rec = {}
    out = NS['rl2_route'](rec, 'TOKEN_8000', 'B64', 'Mission_List', fake_env, tmp)
    add(out is None and rec.get('relay2_fallthrough') == 'gateway-code-0'
        and bool(rec.get('relay2_err')),
        'Shittim 超时（post_gateway 回 code 0）-> 落回 + relay2_err=%r'
        % (rec.get('relay2_err'),))

    # ---- 信封返回 None
    put('post_gateway', fake_post)
    put('unwrap_gateway_response',
        lambda raw: ('Mission_List', {'Protocol': 8000, 'Echo': ['Hash']}))
    rec = {}
    out = NS['rl2_route'](rec, 'TOKEN_8000', 'B64', 'Mission_List', None, tmp)
    add(out is None and rec.get('relay2_fallthrough') == 'envelope'
        and rec.get('relay2_used') is None,
        'envelope 没注入 / 返回 None -> 落回（fallthrough=envelope）')

    # ---- 清理注入的替身，避免污染后续
    drop('cn_cipher', 'ensure_session', 'post_gateway', 'unwrap_gateway_response',
         'rl_request_json', 'rl_num_from_request')
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
    info('状态 = %s' % ('已打补丁（校验补丁后不变量）' if patched else '校验基线+锚点'))

    # ---- 1. 语法
    ok, err = compile_ok(text, src)
    add(ok, 'python 语法检查 compile() %s' % ('' if ok else '-> ' + err))

    if not patched:
        # ---- 2. 基线指纹（硬闸：不符就不许 --apply）
        add(len(raw) == BASE_SIZE, '基线大小 == %d（实测 %d）' % (BASE_SIZE, len(raw)))
        add(sha == want, '基线 sha256 == %s（实测 %s）' % (want, sha))
        add(count_any_marks(text) == 0, '基线里没有 BAPATCH-RELAY2 残留（实测 %d 处）'
            % count_any_marks(text))
        # relay v1 必须已经打上（relay2 复用它的 RL_PAYLOAD 函数）
        for m in RELAY1_MARKS:
            add(text.count(m + ' BEGIN') == 1 and text.count(m + ' END') == 1,
                'relay v1 的 %s 块在（BEGIN/END 各 1）' % m)
        _b1 = text.find('# >>> BAPATCH-RELAY-PAYLOAD')
        _e1 = text.find('# <<< BAPATCH-RELAY-PAYLOAD')
        _relay1_body = text[_b1:_e1 + 60] if 0 <= _b1 < _e1 else ''
        for fn in RELAY1_REUSED:
            add(fn in _relay1_body,
                'relay v1 的 RL_PAYLOAD 里确实有 %s()（relay2 复用的就是它）' % fn)
        # ---- 3. 锚点唯一
        for unit in UNITS:
            n, line = anchor_hits(text, anchor_text(unit))
            add(n == 1, '锚点 %s 唯一命中 %d 次（第 %s 行，%s）'
                % (unit, n, line, ANCHOR_DESC[unit]))
        add(text.count(HOOK_TAIL) == 1,
            'path D 的 `if proto_int:` 分支 7 行原样在（唯一命中，结构性完好）')
        # ---- 4. 缩进 / AST：确认真实锚点就在 _bridge 的方法体里
        _i_anchor = text.find(ANCHOR_HOOK)
        _ind = indent_at(text, _i_anchor)
        add(_ind == HOOK_INDENT,
            '锚点 `if proto_int:` 缩进 == %d 空格（实测 %d）—— 钩子也必须 %d 空格'
            % (HOOK_INDENT, _ind, HOOK_INDENT))
        try:
            _tree = ast.parse(text)
            _bridge = ast_find_bridge(_tree)
            _idx = ast_proto_int_index(_bridge)
            add(_idx is not None,
                'AST：`if proto_int:` 是 `_bridge` 函数体的一条**直接语句**（下标 %r）'
                % (_idx,))
            if _idx is not None:
                _prev = _bridge.body[_idx - 1] if _idx else None
                add(isinstance(_prev, ast.Try),
                    'AST：`if proto_int:` 的前一条语句是 Try（P3-HOOK-D，line %r）—— '
                    '钩子就插在这一对之间' % (getattr(_prev, 'lineno', None),))
        except Exception as _e:
            add(False, 'AST 检查失败: %r' % (_e,))
        i_main = text.find(ANCHOR_PAYLOAD)
        add(i_main > _i_anchor, 'PAYLOAD 锚点在 path D 之后（main@%d）' % (i_main,))
    else:
        # ---- 2. 标记成对
        for unit in UNITS:
            b, e = count_marks(text, unit)
            add(b == 1 and e == 1 and find_block(text, unit) is not None,
                '%s 标记成对、各 1 处（BEGIN %d / END %d）' % (unit, b, e))
        # ---- 3. 载荷逐字节 == 真源
        body = extract_block_body(text, UNIT_PAYLOAD)
        add(body == payload_body(),
            '内嵌 PAYLOAD 逐字节 == patch_relay2.py 的 RL2_PAYLOAD_SRC（sha256 %s / %s）'
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
        # ---- 4. HOOK 逐字节
        blk = extract_block_body(text, UNIT_HOOK)
        want_hook = '\n'.join(unit_block(UNIT_HOOK).rstrip('\n').split('\n')[1:-1]) + '\n'
        add(blk == want_hook, 'HOOK 代码块逐字节 == patch_relay2.py 里生成的那份')
        # ---- 5. 位置
        i_hook = text.find(mark_begin(UNIT_HOOK))
        i_anchor = text.find(ANCHOR_HOOK)
        i_pto = text.find("        if proto_int:")
        add(0 <= i_hook < i_anchor == i_pto,
            'HOOK 整块在 `if proto_int:` 之前（hook@%d < anchor@%d == proto_int@%d）'
            % (i_hook, i_anchor, i_pto))
        add(text[i_hook:i_anchor].rstrip().endswith(mark_end(UNIT_HOOK)),
            'HOOK 与 `if proto_int:` 之间没有别的代码（END 标记后面就是锚点）')
        # ---- 6. 缩进（两个方向都断言：与目标同级 + 体内深一层）
        hook_lines = text.split('\n')
        hook_mark_line = ''
        hook_try_line = ''
        hook_stmt_line = ''
        prev_line = ''
        for _i, _ln in enumerate(hook_lines):
            if _ln.lstrip().startswith(mark_begin(UNIT_HOOK)):
                hook_mark_line = _ln
                prev_line = hook_lines[_i - 1] if _i else ''
                for _j in range(_i, min(_i + 60, len(hook_lines))):
                    if hook_lines[_j].strip() == 'try:':
                        hook_try_line = hook_lines[_j]
                        hook_stmt_line = hook_lines[_j + 1] if _j + 1 < len(hook_lines) else ''
                        break
                break
        add(line_indent(hook_mark_line) == HOOK_INDENT,
            'HOOK 起始行缩进 == %d 空格（实测 %d）—— 与 `if proto_int:` **同级**'
            % (HOOK_INDENT, line_indent(hook_mark_line)))
        add(hook_try_line.strip() == 'try:'
            and line_indent(hook_try_line) == HOOK_INDENT,
            'HOOK 的 `try:` 缩进 == %d 空格（实测 %d）'
            % (HOOK_INDENT, line_indent(hook_try_line)))
        add(line_indent(hook_stmt_line) == HOOK_INDENT + 4,
            'HOOK 体内语句缩进 == %d 空格 == 锚点缩进 + 1 层（实测 %d）'
            % (HOOK_INDENT + 4, line_indent(hook_stmt_line)))
        add(prev_line.strip().startswith('# <<< BAPATCH-P3-HOOK-D'),
            'HOOK 紧跟在 P3-HOOK-D 的 END 标记之后（上一行 = %r）' % (prev_line.strip()[:48],))
        # ---- 7. AST：必须真的在 _bridge 的语句序列里、紧邻 proto_int 之前
        try:
            _tree = ast.parse(text)
            _bridge = ast_find_bridge(_tree)
            _idx_if = ast_proto_int_index(_bridge)
            _node, _bridge2, _idx_hook, _owner = ast_hook_try(_tree, text)
            add(_idx_hook is not None,
                'AST：含 rl2_route(...) 的 Try 是 `_bridge` 函数体的一条直接语句（下标 %r）'
                % (_idx_hook,))
            add(_idx_hook is not None and _idx_if is not None and _idx_hook == _idx_if - 1,
                'AST：它就是 `if proto_int:` 的**直接前一条**语句（hook 下标 %r / '
                'proto_int 下标 %r）' % (_idx_hook, _idx_if))
            add(_owner == 'FunctionDef',
                'AST：rl2_route 所在 Try 的父节点 == %r（不是 ExceptHandler/If）' % (_owner,))
            # 反证：整体右移 4 空格后，AST 上确实掉进 ExceptHandler（说明这条断言抓得住坑）
            _var = indent_variant(text, UNIT_HOOK, 4)
            _ok_v, _err_v = compile_ok(_var, '<indent-variant>')
            _owner2 = None
            if _ok_v:
                _owner2, _p2 = ast_try_owner(ast.parse(_var), _var)
            add((not _ok_v) or _owner2 == 'ExceptHandler',
                '反证：把 HOOK 写成 12 空格会掉进 P3-HOOK-D 的 except 处理体'
                '（语法=%r / 父节点=%r）—— 这正是上一版踩过的坑'
                % (_ok_v, _owner2))
        except Exception as _e:
            add(False, 'AST 检查失败: %r' % (_e,))
        add('rl2_route' in text[i_hook:i_anchor]
            and 'self._cn_envelope' in text[i_hook:i_anchor],
            'HOOK 调用了 rl2_route(...) 且注入 self._cn_envelope')
        # ---- 8. path D 结构完好
        add(text.count(HOOK_TAIL) == 1,
            '`if proto_int:` 分支 7 行原样未被改动（min-envelope / _generic_protocol_response）')
        i_payload = text.find(mark_begin(UNIT_PAYLOAD))
        i_main = text.find(ANCHOR_PAYLOAD)
        add(0 < i_payload < i_main,
            "PAYLOAD 在 `if __name__ == '__main__':` 之前（payload@%d < main@%d）"
            % (i_payload, i_main))
        _i_r1 = text.find('# >>> BAPATCH-RELAY-PAYLOAD')
        add(0 < _i_r1 < i_payload,
            'PAYLOAD 排在 relay v1 的 PAYLOAD 之后（relay1@%d < relay2@%d），'
            'rl2_* 运行时才能看到 rl_* 函数' % (_i_r1, i_payload))
        # ---- 9. 既有补丁没被动过
        for other in OTHER_MARKS:
            add(text.count(other + ' %s BEGIN' % VER) == 1,
                '既有补丁 %s 仍在（BEGIN 各 1 处，未被动过）' % other)
        # ---- 10. 摘掉本补丁 == 基线（逐字节）
        removed, _acts = build_removed(text)
        add(len(removed.encode('utf-8')) == BASE_SIZE
            and sha256_text(removed) == want,
            '摘掉 PAYLOAD+HOOK 后逐字节 == 基线 %d B / sha256 %s（实测 %d B / %s）'
            % (BASE_SIZE, want[:16], len(removed.encode('utf-8')),
               sha256_text(removed)[:16]))
        add(count_any_marks(removed) == 0, '摘块后零 BAPATCH-RELAY2 残留')

    # ---- 11. 内嵌运行时单测
    ns, nerr = load_embedded_ns(text) if patched else (None, '未打补丁')
    if patched:
        add(ns is not None, '内嵌载荷可 exec%s' % ('' if ns else ' -> ' + nerr))
    if ns:
        tmp = tempfile.mkdtemp(prefix='relay2sw_')
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
        description='名字已知但没有真生成器的协议 -> 本地 Shittim 的转发补丁'
                    '（必须显式给 --src）')
    ap.add_argument('--src', required=True,
                    help='要打补丁的 account_auth_probe.py（线上：%s）' % LIVE_SRC)
    ap.add_argument('--apply', action='store_true', help='打补丁（先备份再写）')
    ap.add_argument('--verify', action='store_true', help='自检（不写文件）')
    ap.add_argument('--dry-run', action='store_true', help='打印插入位置与 diff，不写文件')
    ap.add_argument('--rollback', action='store_true', help='回滚（优先用 .relay2.bak.* 还原）')
    ap.add_argument('--restore', default=None, help='配合 --rollback：直接用这个备份覆盖')
    ap.add_argument('--from-block-removal', action='store_true',
                    help='配合 --rollback：不用备份，直接摘块')
    ap.add_argument('--force', action='store_true',
                    help='--rollback / --apply 时容忍指纹不符')
    ap.add_argument('--switches', choices=('keep', '1', '0'), default='keep',
                    help='cn_relay_known.txt：keep（默认：已有不动，缺失**不创建** = 关）/ 1 / 0')
    ap.add_argument('--switch-dir', default=None,
                    help='cn_relay_known.txt 所在目录（默认：线上路径 -> %s，其它 -> src 所在目录）'
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
            print('  残留 BAPATCH-RELAY2 标记: %s'
                  % ('无（干净）' if count_any_marks(text_b) == 0 else '有残留!!'))
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
        now_sha = hashlib.sha256(now_raw).hexdigest()
        print('  摘块回滚完成。备份=%s' % bak)
        print('  还原后 %d 字节 / sha256 %s' % (len(now_raw), now_sha))
        print('  与基线 %d B / %s %s'
              % (BASE_SIZE, want[:16], '逐字节一致' if now_sha == want else '不一致!!'))
        print('  残留 BAPATCH-RELAY2 标记: %s'
              % ('无（干净）' if count_any_marks(new_text) == 0 else '有残留!!'))
        return 0 if now_sha == want else 1

    # ---------------- apply / dry-run
    if args.apply or args.dry_run:
        if not is_patched(orig) and (len(raw) != BASE_SIZE or sha_now != want) \
                and not args.force:
            raise SystemExit(
                '!! 基线指纹不符，拒绝打补丁\n'
                '   实测 %d 字节 / sha256 %s\n'
                '   期望 %d 字节 / sha256 %s（= patch_3 v1 + patch_relay v1）\n'
                '   本补丁必须以 115,911 B 的文件为基线；如果你的文件是 %d B / %s，\n'
                '   先把上一版补丁打上：patch_relay.py --src <file> --apply\n'
                '   确认无误可加 --expect-sha <实测sha> 或 --force。'
                % (len(raw), sha_now, BASE_SIZE, want, RELAY1_SIZE,
                   RELAY1_UPSTREAM_SHA256))
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
                    print('  [%s] 插到第 %d 行之前（%s）'
                          % (unit, line_no, ANCHOR_DESC[unit]))
                if unit == UNIT_HOOK:
                    print('        缩进 = %d 空格（与 `if proto_int:` 同级；体内 %d 空格）'
                          % (indent_at(orig, i), indent_at(orig, i) + 4))
            print('\n  ---- HOOK ----')
            for ln in unit_block(UNIT_HOOK).rstrip('\n').split('\n'):
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
        print('  （或 python patch_relay2.py --src %s --rollback）' % args.src)
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
