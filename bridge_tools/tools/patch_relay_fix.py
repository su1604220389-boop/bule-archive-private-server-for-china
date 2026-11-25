#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patch_relay_fix.py -- relay 上线后暴露的三个真问题的本地补丁（v1）。

基线（硬闸）：
    128,309 B / sha256 e5fb03b87433741ed61ad6f7cc010707193fbd46d7c2086608fb0c11d66f5581
    = patch_3 v1 + patch_relay.py v1 + patch_relay2.py v1 之后的沙箱现状。
    --verify / --apply 都会先校验这个指纹；不符就拒绝动文件（--expect-sha 可覆盖）。

修的是什么（线上实测，详见 PROGRESS_RELAYFIX.md）：

  ① 协议号被拼错（最要紧）
     Shittim 收到 Protocol 190044 / 900111 / 350033 / 160000（应为 19004 / 90011 /
     35003 / 16000），全部回 "doesn't have corresponding type registered"。
     根因：rl_request_json() 里 `_rljson.loads('{"Protocol":%d' % int(num) + text)`
     假设 fragment 一定以 ',' 开头；实测有些协议 decode 出来的 fragment 开头残留了
     协议号的最后一位数字（19004 -> "4,..."），拼出来就是 190044。
     修法：新增 _rl_build_request(num, text, rec)，按候选顺序逐个试，只接受
     json.loads 成功 + Protocol == num + 非空 dict 的结果；全部不成立 -> None（落回，
     不猜）。两条 relay 路径都记 req_frag_head（上层已写则不覆盖）。

  ② Session expired or invalid 被拒后一直不重试
     桥缓存的 SESSION.session_key 与 Shittim 内存表 _activeSessions 不一致
     （实测 sessions.json = a25071d4…，桥缓存 = 0793ebba…），Shittim 一直拒，
     桥一直用死缓存。
     修法：两条转发路径拿到响应后先用 _rl_is_auth_fail(obj) 判断；命中则拿同一把
     SESSION.lock 清空 session_key / account_id -> 重新 ensure_session -> 重新
     post_gateway，只重试一次。仍失败 -> 落回原逻辑（return None，绝不 500）。

  ③ EncryptedUID 是写死的假值（本轮只登记，不修）
     线上 1002 响应里 "EncryptedUID":"FUQPRE2OHCSXGOQRNGJQOAOCD4" 硬编码在
     cn_inner27.py:98，客户端因此弹 InvalidProtocol。它不在本补丁范围（另一个文件），
     需要按真实 UID 派生，属独立任务。

开关：
    本补丁**不新增开关**。修的是既有 relay 行为，cn_relay_unknown.txt /
    cn_relay_known.txt 打开时自动生效；两个都关时与打补丁前行为一致
    （_relayfix_replay.py 用「冻结时间 + 冻结 uuid」对响应做了逐字节比对）。

改动形态（全部可整段撤销）：
    1. 在 relay v1 的 RL_PAYLOAD 里、`def rl_request_json(...)` 之前插入一块
       BAPATCH-RLFIX（_rl_build_request / _rl_is_auth_fail / _rl_clear_session /
       _rl_retry_on_auth_fail）。
    2. rl_request_json 尾部改调 _rl_build_request，并补 req_frag_head 日志。
    3. _rl_relay_once：补 req_frag_head；鉴权失败 -> 清缓存 + 只重试一次。
    4. _rl2_relay_once：同上（复用 relay v1 的同一个 _rl_build_request / 重试函数）。
    注意：本补丁改的是两条 relay 载荷内部的代码。打完本补丁以后**不要**再跑
    patch_relay.py --apply 或 patch_relay2.py --apply —— 它们会把各自的载荷整块换回
    未修的版本，rlf 的改动会被覆盖。

日志字段（新增）：
    rl_req_build（用了第几个候选；0 = 全部失败）
    rl_req_frag_head（fragment.strip()[:200]）
    rl_req_build_err（失败原因摘要）
    rl_session_retry（命中鉴权失败、发起过重试）
    rl_session_retry_ok（重试后拿到正常响应）
    req_frag_head（fragment.strip()[:300]；两条 relay 路径都写，上层已写不覆盖）
    辅助：rl_session_clear_err / rl_session_retry_err

CLI：
    python deploy/patch_relay_fix.py --src <file> --verify
    python deploy/patch_relay_fix.py --src <file> --dry-run
    python deploy/patch_relay_fix.py --src <file> --apply
    python deploy/patch_relay_fix.py --src <file> --rollback
    python deploy/patch_relay_fix.py --src <file> --verify --expect-sha <sha256>

红线：
  * 纯本地；脚本 import 期不碰网络、不碰开关文件。
  * 锚点不唯一 / 基线指纹不符 / 打出来语法不过 -> 拒绝写文件（先备份再写）。
  * --rollback 后必须逐字节回到基线（脚本自己校验并向调用方返回退出码）。
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
import time

sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))

LIVE_SRC = '/www/wwwroot/bapatch/tools/account_auth_probe.py'
DEFAULT_SWITCH_DIR = '/www/wwwroot/bapatch'

# ---------------------------------------------------------------- 基线指纹
# 线上现状 = patch_3 v1 + patch_relay v1 + patch_relay2 v1
BASE_SIZE = 128309
BASE_SHA256 = 'e5fb03b87433741ed61ad6f7cc010707193fbd46d7c2086608fb0c11d66f5581'
# 上一层（只用于报错提示，不作为本补丁的基线）
RELAY2_SIZE = 115911
RELAY2_SHA256 = '377176809ff25949a45e54224a274ad2b701e02c2d6d8a787a4a6eb16e815a07'
RELAY1_SIZE = 103900
RELAY1_SHA256 = '563c1942289968e3f402c52eb89982cba75f9753ba85d13f6cca0be244ffc5c8'

VER = 'v1'
BACKUP_TAG = '.rlf.bak.'
MARK = 'BAPATCH-RLFIX'
BEGIN_PREFIX = '# >>> BAPATCH-RLFIX %s BEGIN' % VER
END_LINE = '# <<< BAPATCH-RLFIX %s END <<<' % VER

# 插入位置：RL_PAYLOAD 里 rl_request_json 的定义之前（这个 def 全文件唯一）
ANCHOR_HELPER = 'def rl_request_json(decoded, rec=None):\n'

# 上一版补丁的块必须原样在（relay2 复用 relay v1 的 rl_request_json）
RELAY1_MARKS = ('BAPATCH-RELAY-PAYLOAD v1', 'BAPATCH-RELAY-HOOK-A v1')
RELAY2_MARKS = ('BAPATCH-RELAY2-PAYLOAD v1', 'BAPATCH-RELAY2-HOOK v1')
REQUIRED_RELAY1_FUNCS = ('rl_request_json', 'rl_num_from_request', 'rl_read_file')
REQUIRED_RELAY2_FUNCS = ('rl2_route', '_rl2_relay_once')

# 既有补丁（一个字节都不许动）
OTHER_MARKS = ('BAPATCH-P3-PAYLOAD', 'BAPATCH-P3-HOOK-E', 'BAPATCH-P3-HOOK-D',
               'BAPATCH-P3-HOOK-G', 'BAPATCH-SIMPLE-PAYLOAD',
               'BAPATCH-SIMPLE-HOOK-D', 'BAPATCH-SIMPLE-HOOK-G',
               'BAPATCH-RELAY-PAYLOAD', 'BAPATCH-RELAY-HOOK-A',
               'BAPATCH-RELAY2-PAYLOAD', 'BAPATCH-RELAY2-HOOK')


# ================================================================ 内嵌运行时（唯一真源）
RLFIX_HELPER_SRC = r'''# -*- coding: utf-8 -*-
"""BAPATCH-RLFIX v1：relay 运行时修正（协议号拼接 / 会话失效重试）。

被 patch_relay_fix.py 插在 patch_relay.py 的 RL_PAYLOAD 里（rl_request_json 之前），
relay v1（cn_relay_unknown.txt）与 relay2（cn_relay_known.txt）两条转发路径共用。

* _rl_build_request(num, text, rec)：
  decode_packet 解出的 fragment 偶尔以协议号最后一位数字开头（19004 -> "4,…"），
  原逻辑 '{"Protocol":19004' + "4,…" 会拼成 190044。这里按候选顺序试，只有
  json.loads 成功、Protocol == num、且不是空 dict 才接受；全部不成立 -> None。
* _rl_is_auth_fail(obj)：识别 Shittim 的鉴权失败信封。
* _rl_retry_on_auth_fail(...)：清桥会话缓存（同一把 SESSION.lock）-> 重新
  ensure_session -> 重新 post_gateway，只重试一次。

日志字段：rl_req_build / rl_req_frag_head / rl_req_build_err /
          rl_session_retry / rl_session_retry_ok。
"""
RLFIX_FRAG_DROP_MAX = 8


def _rl_frag_candidates(num, text):
    """按候选顺序给出 (候选号, 要丢给 json.loads 的文本)。

    1     原逻辑：'{"Protocol":<num>' + text
    2     text[0] 是数字：从第一个逗号处截断后再拼
    3-10  依次去掉开头 1..8 个字符，再从第一个逗号处截断后拼
    11    text 以 } / , 之外的可疑字符开头：同样从第一个逗号处截断

    没有逗号可截的候选直接跳过（拼不出合法 JSON）。重复文本不剔除：先命中的
    候选号就是 rec['rl_req_build']，顺序本身就是可核对的事实。
    """
    n = int(num)
    cands = [(1, '{"Protocol":%d' % n + text)]
    comma = text.find(',')
    if text[:1].isdigit() and comma >= 0:
        cands.append((2, '{"Protocol":%d' % n + text[comma:]))
    for k in range(1, RLFIX_FRAG_DROP_MAX + 1):
        rest = text[k:]
        c = rest.find(',')
        if c >= 0:
            cands.append((2 + k, '{"Protocol":%d' % n + rest[c:]))
    if text[:1] and text[0] not in ('}', ',') and comma >= 0:
        cands.append((3 + RLFIX_FRAG_DROP_MAX, '{"Protocol":%d' % n + text[comma:]))
    return cands


def _rl_build_request(num, text, rec=None):
    """fragment -> 可发给 Shittim 的请求 dict；所有候选都不成立 -> None（不猜）。"""
    if isinstance(rec, dict):
        rec['rl_req_frag_head'] = text[:200]
        rec['rl_req_build'] = 0
        rec['rl_req_build_err'] = ''
    try:
        n = int(num)
    except Exception as e:
        if isinstance(rec, dict):
            rec['rl_req_build_err'] = 'bad num: %r' % (e,)
        return None
    errs = []
    for cid, body in _rl_frag_candidates(n, text):
        try:
            obj = _rljson.loads(body)
        except Exception as e:
            if len(errs) < 4:
                errs.append('c%d:%s' % (cid, type(e).__name__))
            continue
        if not isinstance(obj, dict) or not obj:
            if len(errs) < 4:
                errs.append('c%d:not-dict-or-empty' % cid)
            continue
        if obj.get('Protocol') != n:
            if len(errs) < 4:
                errs.append('c%d:Protocol=%r' % (cid, obj.get('Protocol')))
            continue
        if isinstance(rec, dict):
            rec['rl_req_build'] = cid
            rec['rl_req_build_err'] = ''
        return obj
    if isinstance(rec, dict):
        rec['rl_req_build_err'] = ('all candidates failed (%d tries): %s'
                                   % (len(errs), '; '.join(errs)))[:300]
    return None


def _rl_is_auth_fail(obj):
    """Shittim 的「Session expired or invalid」是否打回来了。"""
    if not isinstance(obj, dict):
        return False
    if obj.get('Protocol') == -1:
        return True
    ec = obj.get('ErrorCode')
    if isinstance(ec, int) and ec != 0:
        return True
    msg = str(obj.get('Msg') or obj.get('Message') or '')
    return 'Session' in msg and ('expired' in msg.lower() or 'invalid' in msg.lower())


def _rl_clear_session(rec=None):
    """清桥缓存的 session_key / account_id（同一把 SESSION.lock）；失败不抛。"""
    sess = globals().get('SESSION')
    if sess is None:
        return False
    try:
        lock = getattr(sess, 'lock', None)
        if lock is not None:
            with lock:
                sess.session_key = None
                sess.account_id = None
        else:
            sess.session_key = None
            sess.account_id = None
    except Exception as e:
        if isinstance(rec, dict):
            rec['rl_session_clear_err'] = repr(e)
        return False
    return True


def _rl_retry_on_auth_fail(rec, req, post, unwrap, ensure, timeout=None):
    """鉴权失败后的唯一一次重试：清缓存 -> ensure_session -> post_gateway。

    成功 -> (code, raw, gp, obj)；失败 / 异常 -> None（调用方落回原逻辑，不 500）。
    日志：rl_session_retry=True / rl_session_retry_ok=True|False。
    """
    if not isinstance(rec, dict):
        return None
    if rec.get('rl_session_retry'):
        # 只重试一次：同一个 rec 已经重试过就直接放弃
        return None
    rec['rl_session_retry'] = True
    rec['rl_session_retry_ok'] = False
    try:
        _rl_clear_session(rec)
        sk, _aid = ensure(rec)
        if sk is None:
            rec['rl_session_retry_err'] = 'ensure_session returned None'
            return None
        req['SessionKey'] = sk
        if timeout is None:
            code, raw = post(req)
        else:
            try:
                code, raw = post(req, timeout=timeout)
            except TypeError:
                # 变体 bridge 的 post_gateway 可能没有 timeout 形参
                code, raw = post(req)
        raw = raw or b''
        if code == 0:
            rec['rl_session_retry_err'] = 'gateway unreachable/timeout'
            return None
        gp, obj = unwrap(raw)
        if not isinstance(obj, dict) or _rl_is_auth_fail(obj):
            rec['rl_session_retry_err'] = 'still auth-failed'
            return None
        rec['rl_session_retry_ok'] = True
        return code, raw, gp, obj
    except Exception as e:
        rec['rl_session_retry_err'] = repr(e)
        return None
'''


# ================================================================ 外科手术式替换
# 每条 = (名字, 原文, 新文)。原文/新文都必须全文件唯一；--verify 会断言。
EDIT_REQ_TAIL_OLD = """    try:
        obj = _rljson.loads('{"Protocol":%d' % int(num) + text)
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None
"""
EDIT_REQ_TAIL_NEW = """    # BAPATCH-RLFIX: 统一走 _rl_build_request（候选顺序 + Protocol 硬校验；全失败 -> None）
    return _rl_build_request(num, text, rec)
"""

EDIT_REQ_HEAD_OLD = """    text = frag.strip()
    if not text:
        return None
"""
EDIT_REQ_HEAD_NEW = """    text = frag.strip()
    if not text:
        return None
    # BAPATCH-RLFIX: 请求片段头落进访问日志（上层已写则不覆盖）
    if isinstance(rec, dict) and not rec.get('req_frag_head'):
        rec['req_frag_head'] = text[:300]
"""

EDIT_R1_HEAD_OLD = """    req = rl_request_json(decoded, rec)
"""
EDIT_R1_HEAD_NEW = """    # BAPATCH-RLFIX: decode 结果里的 fragment 头部落日志（上层已写则不覆盖）
    if isinstance(rec, dict) and not rec.get('req_frag_head'):
        _frag = decoded.get('fragment') if isinstance(decoded, dict) else None
        if isinstance(_frag, str):
            rec['req_frag_head'] = _frag[:300]
    req = rl_request_json(decoded, rec)
"""

EDIT_R1_RETRY_OLD = """    if not isinstance(obj, dict):
        rec['relay_err'] = ('shittim response not dict (code=%r len=%d body=%r)'
                            % (code, len(raw), raw[:160]))
        rec['relay_fallthrough'] = 'shittim-non-dict'
        return None
    rec['relay_protocol'] = req.get('Protocol') if req.get('Protocol') is not None else num
"""
EDIT_R1_RETRY_NEW = """    if not isinstance(obj, dict):
        rec['relay_err'] = ('shittim response not dict (code=%r len=%d body=%r)'
                            % (code, len(raw), raw[:160]))
        rec['relay_fallthrough'] = 'shittim-non-dict'
        return None
    # BAPATCH-RLFIX: Shittim 判定 Session expired/invalid -> 清桥缓存后只重试一次
    if _rl_is_auth_fail(obj):
        _rlfix_got = _rl_retry_on_auth_fail(rec, req, post, unwrap, ensure)
        if _rlfix_got is None:
            rec['relay_fallthrough'] = 'session-retry-failed'
            return None
        code, raw, gp, obj = _rlfix_got
        rec['relay_code'] = code
        rec['relay_resp_len'] = len(raw)
        rec['relay_session_injected'] = True
        if isinstance(gp, (str, int)) or gp is None:
            rec['relay_gateway_protocol'] = gp
        else:
            rec['relay_gateway_protocol'] = repr(gp)
    rec['relay_protocol'] = req.get('Protocol') if req.get('Protocol') is not None else num
"""

EDIT_R2_HEAD_OLD = """    req = req_builder(decoded, rec)
"""
EDIT_R2_HEAD_NEW = """    # BAPATCH-RLFIX: decode 结果里的 fragment 头部落日志（上层已写则不覆盖）
    if isinstance(rec, dict) and not rec.get('req_frag_head'):
        _frag = decoded.get('fragment') if isinstance(decoded, dict) else None
        if isinstance(_frag, str):
            rec['req_frag_head'] = _frag[:300]
    req = req_builder(decoded, rec)
"""

EDIT_R2_RETRY_OLD = """    if not isinstance(obj, dict):
        rec['relay2_err'] = ('shittim response not dict (code=%r len=%d body=%r)'
                             % (code, len(raw), raw[:160]))
        rec['relay2_fallthrough'] = 'shittim-non-dict'
        return None
    rec['relay2_protocol'] = req.get('Protocol') if req.get('Protocol') is not None else num
"""
EDIT_R2_RETRY_NEW = """    if not isinstance(obj, dict):
        rec['relay2_err'] = ('shittim response not dict (code=%r len=%d body=%r)'
                             % (code, len(raw), raw[:160]))
        rec['relay2_fallthrough'] = 'shittim-non-dict'
        return None
    # BAPATCH-RLFIX: Shittim 判定 Session expired/invalid -> 清桥缓存后只重试一次
    if _rl_is_auth_fail(obj):
        _rlfix_got = _rl_retry_on_auth_fail(rec, req, post, unwrap, ensure,
                                           timeout=RL2_TIMEOUT)
        if _rlfix_got is None:
            rec['relay2_fallthrough'] = 'session-retry-failed'
            return None
        code, raw, gp, obj = _rlfix_got
        rec['relay2_code'] = code
        rec['relay2_resp_len'] = len(raw)
        rec['relay2_session_injected'] = True
        if gp is None or isinstance(gp, (str, int)):
            rec['relay2_gateway_protocol'] = gp
        else:
            rec['relay2_gateway_protocol'] = repr(gp)
    rec['relay2_protocol'] = req.get('Protocol') if req.get('Protocol') is not None else num
"""

EDITS = (
    ('req-tail', EDIT_REQ_TAIL_OLD, EDIT_REQ_TAIL_NEW),
    ('req-frag-head', EDIT_REQ_HEAD_OLD, EDIT_REQ_HEAD_NEW),
    ('relay1-frag-head', EDIT_R1_HEAD_OLD, EDIT_R1_HEAD_NEW),
    ('relay1-session-retry', EDIT_R1_RETRY_OLD, EDIT_R1_RETRY_NEW),
    ('relay2-frag-head', EDIT_R2_HEAD_OLD, EDIT_R2_HEAD_NEW),
    ('relay2-session-retry', EDIT_R2_RETRY_OLD, EDIT_R2_RETRY_NEW),
)


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


def helper_body():
    """内嵌运行时正文（唯一真源 = 本文件里的 RLFIX_HELPER_SRC）。"""
    return RLFIX_HELPER_SRC.replace('\r\n', '\n').rstrip('\n') + '\n'


def helper_block():
    """整块文本（含 BEGIN/END 标记 + 正文 sha256）。"""
    head = ('%s >>> (deploy/patch_relay_fix.py 内嵌 RLFIX_HELPER_SRC，sha256=%s) >>>'
            % (BEGIN_PREFIX, sha256_text(helper_body())))
    return head + '\n' + helper_body() + END_LINE + '\n'


def find_helper_block(text):
    """-> (start, end) 字符下标（含 END 行）；不存在 / 不成对 -> None。"""
    i = text.find(BEGIN_PREFIX)
    if i < 0:
        return None
    j = text.find(END_LINE, i)
    if j < 0:
        return None
    return i, j + len(END_LINE)


def extract_helper_body(text):
    rng = find_helper_block(text)
    if not rng:
        return None
    seg = text[rng[0]:rng[1]]
    lines = seg.split('\n')
    return '\n'.join(lines[1:-1]) + '\n'


def count_marks(text):
    """全文 BAPATCH-RLFIX 出现次数（含行内注释，用于「零残留」）。"""
    return text.count(MARK)


def count_marker_lines(text):
    """BEGIN/END 标记行数 -> (begin, end)。"""
    b = sum(1 for ln in text.split('\n') if ln.lstrip().startswith(BEGIN_PREFIX))
    e = sum(1 for ln in text.split('\n') if ln.lstrip().startswith(END_LINE))
    return b, e


def is_patched(text):
    b, e = count_marker_lines(text)
    return b == 1 and e == 1 and find_helper_block(text) is not None


def anchor_hits(text, anchor):
    n = text.count(anchor)
    if n == 0:
        return 0, None
    return n, text[:text.index(anchor)].count('\n') + 1


def compile_ok(text, path):
    try:
        compile(text, path, 'exec')
        return True, ''
    except SyntaxError as e:
        return False, '%s line %s: %s' % (type(e).__name__, e.lineno, e.msg)


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


# ================================================================ 打 / 摘
def build_patched(orig):
    """返回 (新文本, 动作列表)。幂等：已打过的块/替换原样跳过。"""
    text = orig
    acts = []

    # 1) 先插 helper 块（必须在 rl_request_json 之前）
    if find_helper_block(text):
        rng = find_helper_block(text)
        old = text[rng[0]:rng[1] + 1]
        blk = helper_block()
        if old == blk:
            acts.append('RLFIX: helper 块已存在且逐字节一致（幂等，跳过）')
        else:
            lines = text.split('\n')
            # 按字符替换，保留行结构
            text = text[:rng[0]] + blk + text[rng[1] + 1:]
            acts.append('RLFIX: helper 块已存在但内容不同 -> 整块替换（%d B -> %d B）'
                        % (len(old), len(blk)))
    else:
        n, line = anchor_hits(text, ANCHOR_HELPER)
        if n != 1:
            raise SystemExit('锚点不唯一：helper 插入点 %r 命中 %d 次 —— 拒绝动这个文件'
                             % (ANCHOR_HELPER.strip(), n))
        blk = helper_block()
        text = text[:text.index(ANCHOR_HELPER)] + blk + text[text.index(ANCHOR_HELPER):]
        acts.append('RLFIX: 在原文件第 %d 行之前插入 helper 块（%d 行 / %d B）'
                    % (line, blk.rstrip('\n').count('\n') + 1, len(blk)))

    # 2) 六处外科手术式替换
    for name, old, new in EDITS:
        if new in text:
            n_old = text.count(old)
            acts.append('%s: 已是补丁后形态（跳过%s）'
                        % (name, '' if n_old == 0 else '；仍发现 %d 处原文' % n_old))
            continue
        n = text.count(old)
        if n != 1:
            raise SystemExit('锚点不唯一：%s 原文命中 %d 次（要求恰好 1）—— 拒绝动这个文件'
                             % (name, n))
        text = text.replace(old, new, 1)
        acts.append('%s: 替换 1 处（%d B -> %d B）' % (name, len(old), len(new)))
    return text, acts


def build_removed(orig):
    """返回 (还原文本, 动作列表)；按 EDITS 的逆序还原，再摘 helper 块。"""
    text = orig
    acts = []
    for name, old, new in reversed(EDITS):
        n_new = text.count(new)
        n_old = text.count(old)
        if n_new == 0:
            if n_old == 1:
                acts.append('%s: 本来就没打（跳过）' % name)
                continue
            acts.append('%s: 原文/新文都找不到（跳过）' % name)
            continue
        if n_new != 1:
            raise SystemExit('%s 的新文命中 %d 次，无法安全还原' % (name, n_new))
        text = text.replace(new, old, 1)
        acts.append('%s: 还原 1 处（%d B -> %d B）' % (name, len(new), len(old)))

    rng = find_helper_block(text)
    if rng:
        seg = text[rng[0]:rng[1] + 1]
        text = text[:rng[0]] + text[rng[1] + 1:]
        acts.append('RLFIX: 摘掉 helper 块（%d B）' % len(seg))
    else:
        acts.append('RLFIX: helper 块本来就不在（跳过）')
    return text, acts


# ================================================================ 内嵌运行时单测
class _FakeLock(object):
    def __init__(self):
        self.enter = 0

    def __enter__(self):
        self.enter += 1
        return self

    def __exit__(self, *a):
        return False


class _FakeSession(object):
    def __init__(self):
        self.lock = _FakeLock()
        self.session_key = {'AccountServerId': 1, 'MxToken': '<REDACTED_TOKEN>'}
        self.account_id = 1


def _load_helper_ns():
    ns = {'__name__': 'embedded_rlfix_helper',
          '__file__': os.path.join(HERE, 'patch_relay_fix.py'),
          '_rljson': json}
    exec(compile(helper_body(), '<embedded rlfix helper>', 'exec'), ns)
    return ns


def _selftest(add, info):
    ns = _load_helper_ns()

    # ---- 候选顺序 / Protocol 硬校验
    rec = {}
    frag = ',"Hash":%d,"IsTest":false}' % (19004 << 32 | 5)
    obj = ns['_rl_build_request'](19004, frag, rec)
    add(isinstance(obj, dict) and obj.get('Protocol') == 19004 and rec.get('rl_req_build') == 1,
        '正常 fragment（以逗号开头）-> 候选 1 / Protocol=19004（实测 %r / %r）'
        % (rec.get('rl_req_build'), (obj or {}).get('Protocol')))

    rec = {}
    bad = '4' + frag
    obj = ns['_rl_build_request'](19004, bad, rec)
    add(isinstance(obj, dict) and obj.get('Protocol') == 19004 and rec.get('rl_req_build') == 2,
        '畸形 fragment（开头残留末位数字 "4"）-> 候选 2 / Protocol=19004（实测 %r / %r）'
        % (rec.get('rl_req_build'), (obj or {}).get('Protocol')))
    add(rec.get('rl_req_frag_head') == bad[:200],
        'rl_req_frag_head == fragment[:200]')

    rec = {}
    obj = ns['_rl_build_request'](19004, 'xx' + frag, rec)
    add(isinstance(obj, dict) and obj.get('Protocol') == 19004 and rec.get('rl_req_build') == 3,
        '两字符可疑前缀 -> 候选 3（实测 %r）' % (rec.get('rl_req_build'),))

    rec = {}
    obj = ns['_rl_build_request'](90011, 'garbage"Hash":%d}' % (90011 << 32), rec)
    add(obj is None and rec.get('rl_req_build') == 0 and bool(rec.get('rl_req_build_err')),
        '全部候选失败 -> None / rl_req_build=0 / rl_req_build_err=%r'
        % (rec.get('rl_req_build_err'),))

    rec = {}
    obj = ns['_rl_build_request'](16000, ',"Protocol":16001}', rec)
    add(obj is None and rec.get('rl_req_build') == 0,
        '拼出来的 Protocol 不等于 num（16001 != 16000）-> 拒绝，不猜')

    # ---- 5 位协议号逐个验证（用户点名的 4 个 + 通用性）
    five = (19004, 90011, 35003, 16000)
    bads = []
    for n in five:
        f = ',"Hash":%d,"IsTest":false}' % (n << 32 | 7)
        r1 = {}
        o1 = ns['_rl_build_request'](n, f, r1)
        r2 = {}
        o2 = ns['_rl_build_request'](n, str(n)[-1] + f, r2)
        if not (isinstance(o1, dict) and o1.get('Protocol') == n and r1.get('rl_req_build') == 1
                and isinstance(o2, dict) and o2.get('Protocol') == n and r2.get('rl_req_build') == 2):
            bads.append((n, (o1 or {}).get('Protocol'), r1.get('rl_req_build'),
                         (o2 or {}).get('Protocol'), r2.get('rl_req_build')))
    add(not bads, '19004/90011/35003/16000 正常与畸形 fragment 都重建出正确 Protocol%s'
        % ('' if not bads else '（例外 %r）' % (bads,)))

    # ---- _rl_is_auth_fail 正负样本
    pos = ({'Protocol': -1},
           {'ErrorCode': 3},
           {'ErrorCode': -7},
           {'Msg': 'Session expired or invalid'},
           {'Message': 'Session invalid'})
    neg = ({}, {'Protocol': 8000}, {'ErrorCode': 0},
           {'Msg': 'OK'}, {'Msg': 'Session limit exceeded'}, None, 'Session expired')
    add(all(ns['_rl_is_auth_fail'](x) is True for x in pos),
        '_rl_is_auth_fail 5 个正样本全部命中')
    add(all(ns['_rl_is_auth_fail'](x) is False for x in neg),
        '_rl_is_auth_fail 7 个负样本全部不命中')

    # ---- _rl_clear_session 用同一把锁
    sess = _FakeSession()
    ns['SESSION'] = sess
    ok = ns['_rl_clear_session']({})
    add(ok and sess.lock.enter == 1 and sess.session_key is None and sess.account_id is None,
        '_rl_clear_session 拿 SESSION.lock 清 session_key / account_id（lock 进入 %d 次）'
        % sess.lock.enter)

    # ---- 重试：成功 / 二次拒绝 / 不再重试
    sess = _FakeSession()
    ns['SESSION'] = sess
    calls = {'post': 0}
    good = {'Protocol': 8006, 'Echo': ['Hash']}

    def ensure(rec):
        return {'AccountServerId': 2, 'MxToken': '<REDACTED_TOKEN>'}, 2

    def post(req):
        calls['post'] += 1
        return 200, b'second'

    def unwrap(raw):
        return 8006, dict(good)

    req = {'Protocol': 8006, 'Hash': 8006 << 32}
    rec = {}
    got = ns['_rl_retry_on_auth_fail'](rec, req, post, unwrap, ensure)
    add(got is not None and got[3] == good and calls['post'] == 1
        and req.get('SessionKey') == {'AccountServerId': 2, 'MxToken': '<REDACTED_TOKEN>'},
        '鉴权失败 -> 清缓存 + 重新 ensure + 只补发 1 次 post（post %d 次；'
        'req.SessionKey=%r）' % (calls['post'], req.get('SessionKey')))
    add(rec.get('rl_session_retry') is True and rec.get('rl_session_retry_ok') is True,
        'rl_session_retry=True / rl_session_retry_ok=True')

    before = calls['post']
    got2 = ns['_rl_retry_on_auth_fail'](rec, req, post, unwrap, ensure)
    add(got2 is None and calls['post'] == before,
        '同一个 rec 不会二次重试（只重试一次，post 次数不变）')

    rec = {}
    calls2 = {'post': 0}

    def post_bad(req):
        calls2['post'] += 1
        return 200, b'bad'

    def unwrap_bad(raw):
        return -1, {'Protocol': -1, 'ErrorCode': 3}

    got3 = ns['_rl_retry_on_auth_fail'](rec, {'Protocol': 8006}, post_bad, unwrap_bad, ensure)
    add(got3 is None and calls2['post'] == 1
        and rec.get('rl_session_retry_ok') is False and bool(rec.get('rl_session_retry_err')),
        '重试仍鉴权失败 -> None / rl_session_retry_ok=False（不循环，post %d 次）'
        % calls2['post'])

    rec = {}
    calls3 = {'post': 0}

    def post_err(req):
        calls3['post'] += 1
        return 0, b'timeout'

    got4 = ns['_rl_retry_on_auth_fail'](rec, {'Protocol': 8006}, post_err,
                                        lambda raw: (None, None), ensure)
    add(got4 is None and calls3['post'] == 1 and rec.get('rl_session_retry_ok') is False,
        '重试时网关不可达 -> None / rl_session_retry_ok=False（不 500）')


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
    info('状态 = %s' % ('已打补丁（校验补丁后不变量）' if patched else '校验基线 + 锚点'))

    ok, err = compile_ok(text, src)
    add(ok, 'python 语法检查 compile() %s' % ('' if ok else '-> ' + err))

    if not patched:
        add(len(raw) == BASE_SIZE, '基线大小 == %d（实测 %d）' % (BASE_SIZE, len(raw)))
        add(sha == want, '基线 sha256 == %s（实测 %s）' % (want, sha))
        add(count_marks(text) == 0, '基线里零 BAPATCH-RLFIX 残留（实测 %d 处）'
            % count_marks(text))
        for m in RELAY1_MARKS + RELAY2_MARKS:
            add(text.count(m + ' BEGIN') == 1 and text.count(m + ' END') == 1,
                '上一版补丁 %s 块在（BEGIN/END 各 1）' % m)
        i_r1 = text.find('# >>> BAPATCH-RELAY-PAYLOAD')
        i_r2 = text.find('# >>> BAPATCH-RELAY2-PAYLOAD')
        add(0 < i_r1 < i_r2, 'relay2 载荷排在 relay1 载荷之后（relay1@%d < relay2@%d）'
            % (i_r1, i_r2))
        n, line = anchor_hits(text, ANCHOR_HELPER)
        add(n == 1, 'helper 插入锚点唯一 %d 次（第 %s 行）' % (n, line))
        for name, old, new in EDITS:
            add(text.count(old) == 1 and text.count(new) == 0,
                '%s: 原文恰好 1 处、新文 0 处（可安全替换）' % name)
        for fn in REQUIRED_RELAY1_FUNCS + REQUIRED_RELAY2_FUNCS:
            add(fn in text, '上一版补丁的 %s() 在（本补丁挂在它旁边）' % fn)
        for other in OTHER_MARKS:
            add(text.count(other + ' %s BEGIN' % VER) >= 1
                or text.count(other) >= 2,
                '既有补丁 %s 仍在（未被动过）' % other)
    else:
        b_n, e_n = count_marker_lines(text)
        add(b_n == 1 and e_n == 1, 'BAPATCH-RLFIX 标记行 BEGIN/END 各 1（实测 %d / %d）'
            % (b_n, e_n))
        body = extract_helper_body(text)
        add(body == helper_body(),
            'helper 块正文逐字节 == patch_relay_fix.py 的 RLFIX_HELPER_SRC（sha256 %s / %s）'
            % ((sha256_text(body)[:16] if body else '-'), sha256_text(helper_body())[:16]))
        i0 = text.find(BEGIN_PREFIX)
        head_line = text[i0:text.find('\n', i0)] if i0 >= 0 else ''
        m = __import__('re').search(r'sha256=([0-9a-f]{64})', head_line)
        add(bool(m) and m.group(1) == sha256_text(helper_body()),
            'helper 标记里记的 sha256 与真源一致（%s）' % (m.group(1)[:16] if m else '缺'))
        for name, old, new in EDITS:
            add(text.count(new) == 1, '%s: 新文恰好 1 处（已应用）' % name)
        # 位置：helper 必须在 rl_request_json 之前
        i_h = text.find(BEGIN_PREFIX)
        i_def = text.find(ANCHOR_HELPER)
        add(0 < i_h < i_def, 'helper 块在 rl_request_json 之前（helper@%d < def@%d）'
            % (i_h, i_def))
        add('return _rl_build_request(num, text, rec)' in text,
            'rl_request_json 尾部已改走 _rl_build_request')
        add('session-retry-failed' in text
            and text.count('if _rl_is_auth_fail(obj):') == 2,
            '两条 relay 路径都接了鉴权失败重试（if _rl_is_auth_fail(obj) 2 处）')
        add('rec["req_frag_head"]' in text or "rec['req_frag_head']" in text,
            'req_frag_head 已写进 relay 路径')
        # 摘块 == 基线（逐字节）
        removed, _acts = build_removed(text)
        add(len(removed.encode('utf-8')) == BASE_SIZE and sha256_text(removed) == want,
            '摘掉本补丁后逐字节 == 基线 %d B / sha256 %s（实测 %d B / %s）'
            % (BASE_SIZE, want[:16], len(removed.encode('utf-8')),
               sha256_text(removed)[:16]))
        add(count_marks(removed) == 0, '还原后零 BAPATCH-RLFIX 残留')

    if patched:
        tmp = tempfile.mkdtemp(prefix='rlfix_')
        try:
            _selftest(add, info)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    if verbose:
        for line in rep:
            print('  ' + line)
    return state['ok'], rep, state


# ================================================================ CLI
def main(argv=None):
    ap = argparse.ArgumentParser(
        description='relay 上线三问题修复（协议号拼接 / Session 失效重试）'
                    '（必须显式给 --src）')
    ap.add_argument('--src', required=True,
                    help='要打补丁的 account_auth_probe.py（线上：%s）' % LIVE_SRC)
    ap.add_argument('--apply', action='store_true', help='打补丁（先备份再写）')
    ap.add_argument('--verify', action='store_true', help='自检（不写文件；基线做 sha 硬校验）')
    ap.add_argument('--dry-run', action='store_true', help='打印插入位置与 diff，不写文件')
    ap.add_argument('--rollback', action='store_true', help='回滚（优先用 .rlf.bak.* 还原）')
    ap.add_argument('--restore', default=None, help='配合 --rollback：直接用这个备份覆盖')
    ap.add_argument('--force', action='store_true', help='--apply / --rollback 时容忍指纹不符')
    ap.add_argument('--full-diff', action='store_true', help='--dry-run 连 helper 正文一起 diff')
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
            if not args.force and count_marks(text_b) != 0:
                raise SystemExit('备份里还有 BAPATCH-RLFIX 残留，拒绝覆盖')
            write_text(args.src, text_b)
            now_raw = open(args.src, 'rb').read()
            now_sha = hashlib.sha256(now_raw).hexdigest()
            print('已用备份还原: %s' % cand)
            print('  还原后 %d 字节 / sha256 %s' % (len(now_raw), now_sha))
            print('  与基线 %d B / %s %s'
                  % (BASE_SIZE, want[:16],
                     '逐字节一致' if (len(now_raw) == BASE_SIZE and now_sha == want)
                     else '不一致!!'))
            print('  残留 BAPATCH-RLFIX 标记: %s'
                  % ('无（干净）' if count_marks(text_b) == 0 else '有残留!!'))
            return 0 if (now_sha == want and len(now_raw) == BASE_SIZE) else 1
        new_text, acts = build_removed(orig)
        for a in acts:
            print('  ' + a)
        if new_text == orig:
            print('  什么都没改（本补丁本来就不在）')
            return 0 if len(raw) == BASE_SIZE and sha_now == want else 1
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
              % (BASE_SIZE, want[:16],
                 '逐字节一致' if (len(now_raw) == BASE_SIZE and now_sha == want)
                 else '不一致!!'))
        print('  残留 BAPATCH-RLFIX 标记: %s'
              % ('无（干净）' if count_marks(new_text) == 0 else '有残留!!'))
        return 0 if (now_sha == want and len(now_raw) == BASE_SIZE) else 1

    # ---------------- apply / dry-run
    if args.apply or args.dry_run:
        if not is_patched(orig) and (len(raw) != BASE_SIZE or sha_now != want) \
                and not args.force:
            raise SystemExit(
                '!! 基线指纹不符，拒绝打补丁\n'
                '   实测 %d 字节 / sha256 %s\n'
                '   期望 %d 字节 / sha256 %s（= patch_3 v1 + patch_relay v1 + patch_relay2 v1）\n'
                '   本补丁必须以 128,309 B 的文件为基线；如果你的文件是 %d B / %s，\n'
                '   先按顺序打上上一版：patch_relay.py --apply -> patch_relay2.py --apply。\n'
                '   确认无误可加 --expect-sha <实测sha> 或 --force。'
                % (len(raw), sha_now, BASE_SIZE, want, RELAY2_SIZE, RELAY2_SHA256))
        before = (os.stat(args.src).st_mtime_ns, os.path.getsize(args.src))
        new_text, acts = build_patched(orig)
        print('\n== 改动动作 ==')
        for a in acts:
            print('  ' + a)
        if args.dry_run:
            print('\n== 将要改动的位置 ==')
            rng = find_helper_block(orig)
            if rng:
                print('  [helper] 已存在（第 %d-%d 行）'
                      % (orig[:rng[0]].count('\n') + 1, orig[:rng[1]].count('\n') + 1))
            else:
                i = orig.index(ANCHOR_HELPER)
                print('  [helper] 插到第 %d 行之前（rl_request_json 定义前）'
                      % (orig[:i].count('\n') + 1))
            for name, old, new in EDITS:
                i = orig.find(old)
                print('  [%s] 第 %d 行起（%d B -> %d B）'
                      % (name, orig[:i].count('\n') + 1 if i >= 0 else -1,
                         len(old), len(new)))
            print('\n  ---- helper 摘要 ----')
            blines = helper_block().rstrip('\n').split('\n')
            print('  %d 行 / sha256 %s'
                  % (len(blines), sha256_text(helper_body())[:16]))
            print('  头: %s' % blines[0][:110])
            print('  尾: %s' % blines[-1][:110])
        a_txt, b_txt = orig, new_text
        if not args.full_diff:
            rng = find_helper_block(b_txt)
            if rng:
                b_txt = b_txt[:rng[0]] + '# ...[helper 正文见 patch_relay_fix.py]...\n' \
                    + b_txt[rng[1] + 1:]
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
            return 0
        bak = backup(args.src)
        write_text(args.src, new_text)
        now_raw = open(args.src, 'rb').read()
        print('\n已写入。备份: %s' % bak)
        print('  写入后 %d 字节 / sha256 %s'
              % (len(now_raw), hashlib.sha256(now_raw).hexdigest()))
        print('  还原命令: cp -a %s %s' % (bak, args.src))
        print('  （或 python patch_relay_fix.py --src %s --rollback）' % args.src)
        print('\n== 打完补丁后的自检 ==')
        vok, _rep, _st = verify(args.src, args.expect_sha)
        print('自检: %s' % ('全绿' if vok else '有 FAIL（见上）'))
        return 0 if vok else 1

    # ---------------- verify
    vok, _rep, _st = verify(args.src, args.expect_sha)
    print('结论: %s' % ('PASS' if vok else 'FAIL'))
    return 0 if vok else 1


if __name__ == '__main__':
    sys.exit(main())
