#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patch_relay_fix2.py -- relay 转发时 **SessionKey 没被覆盖** 的本地补丁（v1）。

基线（硬闸）：
    136,894 B / sha256 60f34664933656f460e5c4e74e4cacb19273bac213302b184f8ce12070e785ee
    = patch_3 v1 + patch_simple v1 + patch_relay.py v1 + patch_relay2.py v1
      + patch_relay_fix.py v1 之后的线上现状。
    --verify / --apply / --dry-run 都会先校验这个指纹；不符就拒绝动文件
    （--expect-sha 可覆盖）。--rollback 之后必须逐字节回到这个指纹。

修的是什么（线上实测，根因已确证）：

  现象：补丁后的窗口里仍有 12 次
        `Rejected request with invalid session: Session expired or invalid`
        （Shittim SessionKeyService.cs:153）。

  根因：桥自己的账号服务把 SessionKey.AccountServerId 改成了 10000000001
        （= 桥账号服务号），客户端把这个 SessionKey 原样回传。relay 转发用的是
        「缺了才注入」：

            injected = 'SessionKey' not in req_json      # patch_relay v1
            if injected:
                req_json['SessionKey'] = sk

        客户端带了 SessionKey（值 = 10000000001）-> 注入被跳过 -> Shittim 拿到一个
        不存在的账号 id -> 拒（Invalid session）。

  修法：两条转发路径（`_rl_relay_once` / `_rl2_relay_once`）里**无条件**用
        `ensure_session()` 返回的 `sk` 覆盖 `req['SessionKey']`：

            old = req.get('SessionKey')
            req['SessionKey'] = sk
            rec['relay_session_injected'] = True
            rec['relay_session_overwrote'] = (old is not None and old != sk)
            rec['relay_session_old_sid'] = (old or {}).get('AccountServerId') if isinstance(old, dict) else old

        同时 patch_relay_fix 的 session-retry 里「重新铸 Key 覆盖请求」也改成走
        同一个覆盖函数（原来只在走到重试分支时补发；现在两条路径 + 重试三条入口
        全部是同一份实现、同一套日志）。
        `sk is None` 时**不覆盖**，直接落回（保持打补丁前行为，绝不 500）。

开关：
    本补丁**不新增开关**。修的是既有 relay 行为，cn_relay_unknown.txt（relay v1）/
    cn_relay_known.txt（relay v2）打开时生效；两个都关时走不到这两段代码，
    响应与打补丁前逐字节一致（_relayfix2_replay.py 用「冻结时间 + 冻结 uuid」+
    摘掉本补丁的基线做了逐字节比对）。

改动形态（全部可整段撤销）：
    1. 在 patch_relay_fix v1 的 RLFIX 块 **尾部**（`# <<< BAPATCH-RLFIX v1 END <<<` 之前）
       插入一块 BAPATCH-RLFIX2（_rlfix2_session_family / _rlfix2_force_session）。
       为什么嵌在里面：① 它修的就是 RLFIX 块里 `_rl_retry_on_auth_fail` 的那一行，
       同层相邻才看得懂；② 层序天然 LIFO —— patch_relay_fix 摘块 = 把本补丁一起摘掉
       （_relayfix_replay.py 的 F0「摘掉 RLFIX 后逐字节 == 128,309 B 基线」因此仍然成立），
       不会留下半个补丁。
    2. `_rl_relay_once`：「缺了才注入」-> 无条件覆盖（relay 前缀）。
    3. `_rl2_relay_once`：同上（relay2 前缀）。
    4. `_rl_retry_on_auth_fail`：签名补 family/log；内部的 `req['SessionKey'] = sk`
       改走同一个覆盖函数（重试不再有「特定条件」）。
    注意：本补丁改的是 relay 载荷内部的代码（含 RLFIX 块里的 2 行）。
    **打完本补丁以后不要**再单独跑 patch_relay.py / patch_relay2.py /
    patch_relay_fix.py 的 --apply —— 它们会把各自载荷整块换回旧版本。
    回滚顺序必须是先本补丁（patch_relay_fix2.py --rollback），再往前一层。

日志字段（新增）：
    rl_session_overwrote / rl_session_old_sid      （relay v1 路径 + 它触发的重试）
    rl2_session_overwrote / rl2_session_old_sid    （relay v2 路径 + 它触发的重试）
  语义更新（字段名不变，两个都写）：
    relay_session_injected / relay_session_overwrote / relay_session_old_sid
    relay2_session_injected / relay2_session_overwrote / relay2_session_old_sid
  说明：`*_session_injected` 现在的含义是「已经用桥铸的 sk 填进去了」，客户端自带
  错误 SessionKey 的请求也会置 True —— 这正是本补丁要表达的事实。

CLI：
    python deploy/patch_relay_fix2.py --src <file> --verify
    python deploy/patch_relay_fix2.py --src <file> --dry-run
    python deploy/patch_relay_fix2.py --src <file> --apply
    python deploy/patch_relay_fix2.py --src <file> --rollback
    python deploy/patch_relay_fix2.py --src <file> --show-sha
    python deploy/patch_relay_fix2.py --src <file> --verify --expect-sha <sha256>

--verify 的硬要求：**前四层补丁块必须全在**
    P3×4（PAYLOAD / HOOK-E / HOOK-D / HOOK-G）
    SIMPLE×3（PAYLOAD / HOOK-D / HOOK-G）
    RELAY×2（PAYLOAD / HOOK-A）
    RELAY2×2（PAYLOAD / HOOK）
    RLFIX×N（BEGIN/END + 块正文 sha256 与头行记录一致 + 5 个函数 + 6 处行内标记 …）

红线：
  * 纯本地；脚本 import 期不碰网络、不碰开关文件。
  * 锚点不唯一（原文 ≠ 1 处、新文 ≠ 0 处）/ 基线指纹不符 / 打出来语法不过
    -> 拒绝写文件（先备份再写）。
  * --rollback 后必须逐字节回到 136,894 B / 60f34664…（脚本自己校验并决定退出码）。
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import io
import os
import re
import shutil
import sys
import tempfile
import time

sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))

LIVE_SRC = '/www/wwwroot/bapatch/tools/account_auth_probe.py'

# ---------------------------------------------------------------- 基线指纹
# 线上现状 = patch_3 + patch_simple + patch_relay + patch_relay2 + patch_relay_fix
BASE_SIZE = 136894
BASE_SHA256 = '60f34664933656f460e5c4e74e4cacb19273bac213302b184f8ce12070e785ee'
# 上一层（只用于报错提示，不作为本补丁的基线）
RLFIXED_SIZE = 128309
RLFIXED_SHA256 = 'e5fb03b87433741ed61ad6f7cc010707193fbd46d7c2086608fb0c11d66f5581'

VER = 'v1'
BACKUP_TAG = '.rlf2.bak.'
MARK = 'BAPATCH-RLFIX2'
BEGIN_PREFIX = '# >>> BAPATCH-RLFIX2 %s BEGIN' % VER
END_LINE = '# <<< BAPATCH-RLFIX2 %s END <<<' % VER

# patch_relay_fix v1 的块（本补丁插在它的 END 行之后）
RLFIX_BEGIN_PREFIX = '# >>> BAPATCH-RLFIX v1 BEGIN'
RLFIX_END_LINE = '# <<< BAPATCH-RLFIX v1 END <<<'

# 插入点：RLFIX 块末尾（END 行之前）—— 本补丁嵌在 patch_relay_fix 的块里（LIFO 层序）
ANCHOR_INSERT = RLFIX_END_LINE + '\n'

# ---------------------------------------------------------------- 前四层块
# 每层 = (层名, (标记前缀…))；--verify 断言每个前缀的 BEGIN/END 各 1 次。
LAYERS = (
    ('P3', ('BAPATCH-P3-PAYLOAD', 'BAPATCH-P3-HOOK-E',
            'BAPATCH-P3-HOOK-D', 'BAPATCH-P3-HOOK-G')),
    ('SIMPLE', ('BAPATCH-SIMPLE-PAYLOAD', 'BAPATCH-SIMPLE-HOOK-D',
                'BAPATCH-SIMPLE-HOOK-G')),
    ('RELAY', ('BAPATCH-RELAY-PAYLOAD', 'BAPATCH-RELAY-HOOK-A')),
    ('RELAY2', ('BAPATCH-RELAY2-PAYLOAD', 'BAPATCH-RELAY2-HOOK')),
)

# RLFIX 层（第五层，patch_relay_fix v1）必须成立的不变量。
RLFIX_FUNCS = ('_rl_frag_candidates', '_rl_build_request', '_rl_is_auth_fail',
               '_rl_clear_session', '_rl_retry_on_auth_fail')
# RLFIX 的 6 处行内标记（= patch_relay_fix 的 6 处替换各一条注释）
RLFIX_INLINE_MARKS = 6


# ================================================================ 内嵌运行时（唯一真源）
RLFIX2_HELPER_SRC = r'''# -*- coding: utf-8 -*-
"""BAPATCH-RLFIX2 v1：relay 转发时**无条件**用桥铸的 SessionKey 覆盖请求。

被 patch_relay_fix2.py 插在 patch_relay_fix v1 的 RLFIX 块之后（rl_request_json 之前），
relay v1（cn_relay_unknown.txt）与 relay2（cn_relay_known.txt）两条转发路径
以及 relayfix 的 session-retry 三处入口共用这一份实现。

问题：桥账号服务把 SessionKey.AccountServerId 改成 10000000001，客户端回传它；
relay 原来的「缺了才注入」因此跳过注入 -> Shittim 收到不存在的账号 id -> 拒。

* _rlfix2_session_family(rec, timeout)：判当前属于哪条 relay（relay1 / relay2）。
* _rlfix2_force_session(rec, req, sk, family, log)：无条件覆盖 req['SessionKey']。
  sk is None -> 不覆盖、返回 False（调用方落回，保持打补丁前行为，不 500）。

日志：<family>_session_injected / <family>_session_overwrote / <family>_session_old_sid
      以及本补丁新增的 <log>_session_overwrote / <log>_session_old_sid。
"""


def _rlfix2_session_family(rec=None, timeout=None):
    """当前转发/重试属于哪条 relay -> (字段家族, 日志前缀)。

    判定顺序（先看最确定的信号）：
      1. timeout 非 None —— 只有 relay2 会带 RL2_TIMEOUT 调 post，最可靠；
      2. rec['relay2_on'] / rec['relay2_num'] 有、且没有 relay v1 的对应标记；
      3. 其余一律当 relay v1（rl_route 之前的默认路径）。
    """
    if timeout is not None:
        return 'relay2', 'rl2'
    if isinstance(rec, dict):
        is2 = rec.get('relay2_on') is True or rec.get('relay2_num') is not None
        is1 = rec.get('relay_on') is True or rec.get('relay_num') is not None
        if is2 and not is1:
            return 'relay2', 'rl2'
    return 'relay', 'rl'


def _rlfix2_force_session(rec, req, sk, family=None, log=None):
    """无条件用桥铸的 sk 覆盖 req['SessionKey']；返回 True 表示已覆盖。

    * 不看请求里原来有没有 SessionKey：客户端带来的（错的）一律覆盖。
    * sk is None -> 不动请求、返回 False（调用方落回原逻辑，不 500）。
    * 日志：
        <family>_session_injected  是否已用桥的 sk 填进去（True）
        <family>_session_overwrote 是否真的改了（原来有值且不相等）
        <family>_session_old_sid   被覆盖掉的那个 AccountServerId（没有则 None）
        <log>_session_overwrote / <log>_session_old_sid  同一份事实的短名
    """
    if not isinstance(req, dict):
        return False
    if family is None or log is None:
        _fam, _log = _rlfix2_session_family(rec)
        family = family or _fam
        log = log or _log
    if sk is None:
        if isinstance(rec, dict):
            rec[family + '_session_injected'] = False
        return False
    try:
        old = req.get('SessionKey')
    except Exception:
        old = None
    try:
        same = (old == sk)
    except Exception:
        same = False
    req['SessionKey'] = sk
    if isinstance(rec, dict):
        over = (old is not None and not same)
        try:
            old_sid = old.get('AccountServerId') if isinstance(old, dict) else old
        except Exception:
            old_sid = None
        rec[family + '_session_injected'] = True
        rec[family + '_session_overwrote'] = over
        rec[family + '_session_old_sid'] = old_sid
        rec[log + '_session_overwrote'] = over
        rec[log + '_session_old_sid'] = old_sid
    return True
'''


# ================================================================ 外科手术式替换
# 每条 = (名字, 原文, 新文)。原文必须全文件唯一（恰好 1 处），新文必须 0 处。
EDIT_R1_INJECT_OLD = """    sk, aid = ensure(rec)
    if sk is None:
        rec['relay_fallthrough'] = 'ensure-session'
        return None
    injected = not req.get('SessionKey')
    if injected:
        req['SessionKey'] = sk
    rec['relay_session_injected'] = bool(injected)
"""
EDIT_R1_INJECT_NEW = """    sk, aid = ensure(rec)
    # BAPATCH-RLFIX2: sk 为 None -> 不覆盖、直接落回（保持打补丁前行为，不 500）
    if sk is None:
        rec['relay_fallthrough'] = 'ensure-session'
        return None
    # BAPATCH-RLFIX2: 无条件用桥铸的 sk 覆盖（客户端回传的是桥账号服务的 SessionKey）
    _rlfix2_force_session(rec, req, sk, 'relay', 'rl')
"""

EDIT_R2_INJECT_OLD = """    sk, aid = ensure(rec)
    if sk is None:
        rec['relay2_fallthrough'] = 'ensure-session'
        return None
    injected = not req.get('SessionKey')
    if injected:
        req['SessionKey'] = sk
    rec['relay2_session_injected'] = bool(injected)
"""
EDIT_R2_INJECT_NEW = """    sk, aid = ensure(rec)
    # BAPATCH-RLFIX2: sk 为 None -> 不覆盖、直接落回（保持打补丁前行为，不 500）
    if sk is None:
        rec['relay2_fallthrough'] = 'ensure-session'
        return None
    # BAPATCH-RLFIX2: 无条件用桥铸的 sk 覆盖（同上；本路径用 relay2_ / rl2_ 前缀留痕）
    _rlfix2_force_session(rec, req, sk, 'relay2', 'rl2')
"""

EDIT_RETRY_DEF_OLD = """def _rl_retry_on_auth_fail(rec, req, post, unwrap, ensure, timeout=None):
"""
EDIT_RETRY_DEF_NEW = """def _rl_retry_on_auth_fail(rec, req, post, unwrap, ensure, timeout=None,
                           family=None, log=None):
"""

EDIT_RETRY_SET_OLD = """        req['SessionKey'] = sk
        if timeout is None:
"""
EDIT_RETRY_SET_NEW = """        # BAPATCH-RLFIX2: 重试也走无条件覆盖（不是「缺了才补」），并留 overwrote/old_sid
        _rlfix2_force_session(rec, req, sk, family, log)
        if timeout is None:
"""

EDITS = (
    ('relay1-session-overwrite', EDIT_R1_INJECT_OLD, EDIT_R1_INJECT_NEW),
    ('relay2-session-overwrite', EDIT_R2_INJECT_OLD, EDIT_R2_INJECT_NEW),
    ('retry-session-overwrite', EDIT_RETRY_DEF_OLD, EDIT_RETRY_DEF_NEW),
    ('retry-session-assign', EDIT_RETRY_SET_OLD, EDIT_RETRY_SET_NEW),
)

# 打完补丁后必须成立的事实（verify 用于定位，不是锚点）
NEED_R1_FORCE = "    _rlfix2_force_session(rec, req, sk, 'relay', 'rl')\n"
NEED_R2_FORCE = "    _rlfix2_force_session(rec, req, sk, 'relay2', 'rl2')\n"
NEED_RETRY_FORCE = "        _rlfix2_force_session(rec, req, sk, family, log)\n"


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
    """内嵌运行时正文（唯一真源 = 本文件里的 RLFIX2_HELPER_SRC）。"""
    return RLFIX2_HELPER_SRC.replace('\r\n', '\n').rstrip('\n') + '\n'


def helper_block():
    """整块文本（含 BEGIN/END 标记 + 正文 sha256）。"""
    head = ('%s >>> (deploy/patch_relay_fix2.py 内嵌 RLFIX2_HELPER_SRC，sha256=%s) >>>'
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
    """全文 BAPATCH-RLFIX2 出现次数（含行内注释，用于「零残留」）。"""
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


# ---------------------------------------------------------------- RLFIX 层取证
def rlf_block_range(text):
    i = text.find(RLFIX_BEGIN_PREFIX)
    if i < 0:
        return None
    j = text.find(RLFIX_END_LINE, i)
    if j < 0:
        return None
    return i, j + len(RLFIX_END_LINE)


def rlf_body(text):
    rng = rlf_block_range(text)
    if not rng:
        return None
    seg = text[rng[0]:rng[1]]
    lines = seg.split('\n')
    return '\n'.join(lines[1:-1]) + '\n'


def rlf_recorded_sha(text):
    rng = rlf_block_range(text)
    if not rng:
        return None
    head = text[rng[0]:text.find('\n', rng[0])]
    m = re.search(r'sha256=([0-9a-f]{64})', head)
    return m.group(1) if m else None


def unfix2(text):
    """把本补丁的改动反向还原（用于证明 RLFIX 块其余部分一个字都没动）。

    两步：① 摘掉嵌在 RLFIX 块尾部的 BAPATCH-RLFIX2 块；② 逆序还原 4 处替换。
    """
    out = text
    rng = find_helper_block(out)
    if rng:
        out = out[:rng[0]] + out[rng[1] + 1:]
    for _name, old, new in reversed(EDITS):
        if out.count(new) == 1 and out.count(old) == 0:
            out = out.replace(new, old, 1)
    return out


# ================================================================ 打 / 摘
def build_patched(orig):
    """返回 (新文本, 动作列表)。幂等：已打过的块/替换原样跳过。"""
    text = orig
    acts = []

    # 1) 先插 helper 块（RLFIX 块尾部、rl_request_json 之前）
    rng = find_helper_block(text)
    if rng:
        old = text[rng[0]:rng[1] + 1]
        blk = helper_block()
        if old == blk:
            acts.append('RLFIX2: helper 块已存在且逐字节一致（幂等，跳过）')
        else:
            text = text[:rng[0]] + blk + text[rng[1] + 1:]
            acts.append('RLFIX2: helper 块已存在但内容不同 -> 整块替换（%d B -> %d B）'
                        % (len(old), len(blk)))
    else:
        n, line = anchor_hits(text, ANCHOR_INSERT)
        if n != 1:
            raise SystemExit('锚点不唯一：helper 插入点（RLFIX END 行）命中 %d 次 '
                             '—— 拒绝动这个文件' % n)
        blk = helper_block()
        i = text.index(ANCHOR_INSERT)
        text = text[:i] + blk + text[i:]
        acts.append('RLFIX2: 在原文件第 %d 行之前插入 helper 块（%d 行 / %d B；'
                    '即 RLFIX 块尾部）'
                    % (line, blk.rstrip('\n').count('\n') + 1, len(blk)))

    # 2) 四处外科手术式替换
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
        acts.append('RLFIX2: 摘掉 helper 块（%d B）' % len(seg))
    else:
        acts.append('RLFIX2: helper 块本来就不在（跳过）')
    return text, acts


# ================================================================ 内嵌运行时单测
def _load_helper_ns():
    ns = {'__name__': 'embedded_rlfix2_helper',
          '__file__': os.path.join(HERE, 'patch_relay_fix2.py')}
    exec(compile(helper_body(), '<embedded rlfix2 helper>', 'exec'), ns)
    return ns


def _selftest(add, info):
    ns = _load_helper_ns()
    force = ns['_rlfix2_force_session']
    fam = ns['_rlfix2_session_family']

    BOGUS = {'AccountServerId': 10000000001, 'MxToken': '<REDACTED_TOKEN>'}
    SK = {'AccountServerId': 2, 'MxToken': '<REDACTED_TOKEN>'}

    # ---- 客户端带着错的 SessionKey -> 无条件覆盖
    rec = {}
    req = {'Protocol': 8006, 'SessionKey': dict(BOGUS)}
    ok = force(rec, req, SK, 'relay', 'rl')
    add(ok is True and req['SessionKey'] == SK,
        '带着错的 SessionKey（AccountServerId=10000000001）-> 覆盖成桥铸的 sk（%r）'
        % (req.get('SessionKey'),))
    add(rec.get('relay_session_injected') is True
        and rec.get('relay_session_overwrote') is True
        and rec.get('relay_session_old_sid') == 10000000001,
        '日志 relay_session_injected=True / overwrote=True / old_sid=10000000001（实测 %r / %r / %r）'
        % (rec.get('relay_session_injected'), rec.get('relay_session_overwrote'),
           rec.get('relay_session_old_sid')))
    add(rec.get('rl_session_overwrote') is True and rec.get('rl_session_old_sid') == 10000000001,
        '短名前缀字段 rl_session_overwrote=True / rl_session_old_sid=10000000001')

    # ---- 请求里没有 SessionKey -> 照常注入，overwrote=False
    rec = {}
    req = {'Protocol': 8006}
    force(rec, req, SK, 'relay', 'rl')
    add(req.get('SessionKey') == SK and rec.get('relay_session_injected') is True
        and rec.get('relay_session_overwrote') is False
        and rec.get('relay_session_old_sid') is None,
        '没有 SessionKey -> 注入、overwrote=False、old_sid=None（实测 %r / %r）'
        % (rec.get('relay_session_overwrote'), rec.get('relay_session_old_sid')))

    # ---- 请求里的 SessionKey 本来就等于 sk -> 覆盖但 overwrote=False
    rec = {}
    req = {'Protocol': 8006, 'SessionKey': dict(SK)}
    force(rec, req, SK, 'relay', 'rl')
    add(req.get('SessionKey') == SK and rec.get('relay_session_injected') is True
        and rec.get('relay_session_overwrote') is False,
        'SessionKey 本来就 == sk -> 仍走覆盖、overwrote=False')

    # ---- sk is None -> 不覆盖、落回
    rec = {}
    req = {'Protocol': 8006, 'SessionKey': dict(BOGUS)}
    ok = force(rec, req, None, 'relay', 'rl')
    add(ok is False and req.get('SessionKey') == BOGUS
        and rec.get('relay_session_injected') is False
        and 'relay_session_overwrote' not in rec,
        'sk is None -> 不覆盖（请求原样保留 bogus）、injected=False、不写 overwrote')
    rec = {}
    force(rec, {'Protocol': 1}, None)
    add(rec.get('relay_session_injected') is False,
        'sk is None + 家族靠 rec 推断 -> 也不炸（injected=False）')

    # ---- 家族推断：relay2
    rec = {'relay2_on': True, 'relay2_num': 8006}
    req = {'Protocol': 8006, 'SessionKey': dict(BOGUS)}
    force(rec, req, SK)
    add(rec.get('rl2_session_overwrote') is True and rec.get('rl2_session_old_sid') == 10000000001
        and rec.get('relay2_session_injected') is True
        and 'rl_session_overwrote' not in rec,
        'rec.relay2_on=True -> 家族推断成 relay2（rl2_session_* / relay2_session_*）')
    rec = {'relay_on': True, 'relay_num': 8006}
    force(rec, {'Protocol': 8006}, SK)
    add(rec.get('rl_session_overwrote') is False and rec.get('relay_session_injected') is True
        and 'rl2_session_overwrote' not in rec,
        'rec.relay_on=True -> 家族推断成 relay（rl_session_*）')
    add(fam({}, 8) == ('relay2', 'rl2') and fam({}, None) == ('relay', 'rl'),
        '兜底：timeout 非 None -> relay2；否则 relay')

    # ---- 非 dict 请求不炸
    add(force({}, 'not-a-dict', SK) is False, 'req 不是 dict -> 返回 False，不抛')


# ================================================================ 自检
def _check_layers(text, add):
    """前四层补丁块必须全在：P3×4 / SIMPLE×3 / RELAY×2 / RELAY2×2。"""
    total = 0
    for layer, marks in LAYERS:
        bad = []
        for m in marks:
            b = text.count(m + ' %s BEGIN' % VER)
            e = text.count(m + ' %s END' % VER)
            if not (b == 1 and e == 1):
                bad.append((m, b, e))
        total += len(marks)
        add(not bad, '%s 层 %d 个块全在（BEGIN/END 各 1）%s'
            % (layer, len(marks), '' if not bad else '（缺失/重复：%r）' % (bad,)))
    return total


def _check_rlf(self_text, add, info, patched):
    """第五层（RLFIX）不变量。返回检查项数 N。"""
    n = 0
    b = self_text.count(RLFIX_BEGIN_PREFIX)
    e = self_text.count(RLFIX_END_LINE)
    add(b == 1 and e == 1, 'RLFIX 块 BEGIN/END 各 1（实测 %d / %d）' % (b, e))
    n += 1

    rec_sha = rlf_recorded_sha(self_text)
    body = rlf_body(self_text)
    body_now = sha256_text(body) if body else '-'
    # 摘掉本补丁的 4 处替换后，RLFIX 块正文必须逐字节 == 头行记录的 sha256
    body_un = sha256_text(unfix2(body)) if body else '-'
    add(rec_sha is not None and body_un == rec_sha,
        'RLFIX 块正文（摘掉本补丁替换后）sha256 == 头行记录（%s / %s）'
        % ((rec_sha or '-')[:16], body_un[:16]))
    n += 1
    if patched:
        info('RLFIX 块正文当前 sha256 = %s（本补丁在块内改了 2 行，属设计内）'
             % body_now[:16])

    miss = [f for f in RLFIX_FUNCS if self_text.count('def %s(' % f) != 1]
    add(not miss, 'RLFIX 的 5 个函数各 1 处定义%s' % ('' if not miss else '（缺 %r）' % (miss,)))
    n += 1

    add(self_text.count('return _rl_build_request(num, text, rec)') == 1,
        'rl_request_json 尾部仍走 _rl_build_request（1 处）')
    n += 1
    add(self_text.count('if _rl_is_auth_fail(obj):') == 2,
        '两条 relay 路径的鉴权失败重试都在（2 处，实测 %d）'
        % self_text.count('if _rl_is_auth_fail(obj):'))
    n += 1
    add(self_text.count("'session-retry-failed'") == 2,
        "session-retry-failed 落回分支 2 处（实测 %d）"
        % self_text.count("'session-retry-failed'"))
    n += 1
    add(self_text.count('# BAPATCH-RLFIX:') == RLFIX_INLINE_MARKS,
        'RLFIX 的 6 处行内标记齐备（实测 %d）' % self_text.count('# BAPATCH-RLFIX:'))
    n += 1
    return n


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
        add(count_marks(text) == 0,
            '基线里零 BAPATCH-RLFIX2 残留（实测 %d 处）' % count_marks(text))

        # ---- 前四层 + 第五层 RLFIX
        _check_layers(text, add)
        n_rlf = _check_rlf(text, add, info, patched=False)
        info('前五层取证合计：P3×4 / SIMPLE×3 / RELAY×2 / RELAY2×2 / RLFIX×%d' % n_rlf)

        # ---- 本补丁的替换点
        n, line = anchor_hits(text, ANCHOR_INSERT)
        add(n == 1, 'helper 插入锚点（RLFIX END 行）唯一 %d 次（第 %s 行）' % (n, line))
        for name, old, new in EDITS:
            add(text.count(old) == 1 and text.count(new) == 0,
                '%s: 原文恰好 1 处、新文 0 处（可安全替换）' % name)

        # ---- 反证：现在的「缺了才注入」确实在
        add('    injected = not req.get(\'SessionKey\')\n' in text
            and text.count('relay_session_injected\'] = bool(injected)') == 1
            and text.count('relay2_session_injected\'] = bool(injected)') == 1,
            '基线确实是「缺了才注入」（两条路径各 1 处 bool(injected)）')
        add(('def _rl_retry_on_auth_fail(rec, req, post, unwrap, ensure, '
             'timeout=None):\n') in text,
            '基线里 _rl_retry_on_auth_fail 还没有 family/log 形参')
    else:
        b_n, e_n = count_marker_lines(text)
        add(b_n == 1 and e_n == 1,
            'BAPATCH-RLFIX2 标记行 BEGIN/END 各 1（实测 %d / %d）' % (b_n, e_n))
        body = extract_helper_body(text)
        add(body == helper_body(),
            'helper 块正文逐字节 == patch_relay_fix2.py 的 RLFIX2_HELPER_SRC'
            '（sha256 %s / %s）'
            % ((sha256_text(body)[:16] if body else '-'), sha256_text(helper_body())[:16]))
        i0 = text.find(BEGIN_PREFIX)
        head_line = text[i0:text.find('\n', i0)] if i0 >= 0 else ''
        m = re.search(r'sha256=([0-9a-f]{64})', head_line)
        add(bool(m) and m.group(1) == sha256_text(helper_body()),
            'helper 标记里记的 sha256 与真源一致（%s）' % (m.group(1)[:16] if m else '缺'))

        # 位置：嵌在 RLFIX 块尾部（RLFIX BEGIN 之后、RLFIX END / rl_request_json 之前）
        i_h = text.find(BEGIN_PREFIX)
        i_rb = text.find(RLFIX_BEGIN_PREFIX)
        i_re = text.find(RLFIX_END_LINE)
        i_def = text.find('def rl_request_json(decoded, rec=None):')
        add(0 <= i_rb < i_h < i_re < i_def,
            'helper 块嵌在 RLFIX 块尾部、rl_request_json 之前'
            '（%d <= %d < %d < %d）' % (i_rb, i_h, i_re, i_def))
        _rng = rlf_block_range(text)
        _stripped = (text[:_rng[0]] + text[_rng[1] + 1:]) if _rng else text
        add(find_helper_block(_stripped) is None
            and _stripped.count(BEGIN_PREFIX) == 0
            and _stripped.count(END_LINE) == 0,
            'RLFIX 层整层摘掉时本补丁块随之消失（LIFO；摘后 BEGIN/END 残留 %d / %d）'
            % (_stripped.count(BEGIN_PREFIX), _stripped.count(END_LINE)))

        for name, old, new in EDITS:
            add(text.count(new) == 1, '%s: 新文恰好 1 处（已应用）' % name)
        add(text.count(NEED_R1_FORCE) == 1 and text.count(NEED_R2_FORCE) == 1,
            '两条转发路径都调 _rlfix2_force_session（relay 1 处 / relay2 1 处）')
        add(text.count(NEED_RETRY_FORCE) == 1,
            'session-retry 也调 _rlfix2_force_session（1 处）')
        _call_lines = [ln for ln in text.split('\n')
                       if '_rlfix2_force_session(' in ln
                       and not ln.lstrip().startswith('def ')
                       and not ln.lstrip().startswith('*')]
        add(len(_call_lines) == 3,
            '_rlfix2_force_session 调用点 == 3（两条转发 + 重试；实测 %d）'
            % len(_call_lines))
        add(text.count("'_session_overwrote'") >= 1
            and text.count("'_session_old_sid'") >= 1
            and text.count("family + '_session_overwrote'") == 1,
            "新增日志字段骨架在（_session_overwrote / _session_old_sid；"
            "具体名由 log 前缀拼出 = rl_ / rl2_）")
        add('injected = not req.get(\'SessionKey\')' not in text,
            '「缺了才注入」的旧逻辑已彻底消失（0 处）')

        # ---- 前四层 + 第五层 RLFIX（打完后仍然全在）
        _check_layers(text, add)
        n_rlf = _check_rlf(text, add, info, patched=True)
        info('前五层取证合计：P3×4 / SIMPLE×3 / RELAY×2 / RELAY2×2 / RLFIX×%d' % n_rlf)

        # ---- 摘块 == 基线（逐字节）
        removed, _acts = build_removed(text)
        add(len(removed.encode('utf-8')) == BASE_SIZE and sha256_text(removed) == want,
            '摘掉本补丁后逐字节 == 基线 %d B / sha256 %s（实测 %d B / %s）'
            % (BASE_SIZE, want[:16], len(removed.encode('utf-8')),
               sha256_text(removed)[:16]))
        add(count_marks(removed) == 0, '还原后零 BAPATCH-RLFIX2 残留')

        _selftest(add, info)

    if verbose:
        for line in rep:
            print('  ' + line)
    return state['ok'], rep, state


# ================================================================ CLI
def main(argv=None):
    ap = argparse.ArgumentParser(
        description='relay 转发时 SessionKey 没被覆盖（无条件覆盖）'
                    '（必须显式给 --src）')
    ap.add_argument('--src', required=True,
                    help='要打补丁的 account_auth_probe.py（线上：%s）' % LIVE_SRC)
    ap.add_argument('--apply', action='store_true', help='打补丁（先备份再写）')
    ap.add_argument('--verify', action='store_true', help='自检（不写文件；基线做 sha 硬校验）')
    ap.add_argument('--dry-run', action='store_true', help='打印插入位置与 diff，不写文件')
    ap.add_argument('--rollback', action='store_true', help='回滚（优先用 .rlf2.bak.* 还原）')
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
                raise SystemExit('备份里还有 BAPATCH-RLFIX2 残留，拒绝覆盖')
            write_text(args.src, text_b)
            now_raw = open(args.src, 'rb').read()
            now_sha = hashlib.sha256(now_raw).hexdigest()
            print('已用备份还原: %s' % cand)
            print('  还原后 %d 字节 / sha256 %s' % (len(now_raw), now_sha))
            print('  与基线 %d B / %s %s'
                  % (BASE_SIZE, want[:16],
                     '逐字节一致' if (len(now_raw) == BASE_SIZE and now_sha == want)
                     else '不一致!!'))
            print('  残留 BAPATCH-RLFIX2 标记: %s'
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
        print('  残留 BAPATCH-RLFIX2 标记: %s'
              % ('无（干净）' if count_marks(new_text) == 0 else '有残留!!'))
        return 0 if (now_sha == want and len(now_raw) == BASE_SIZE) else 1

    # ---------------- apply / dry-run
    if args.apply or args.dry_run:
        if not is_patched(orig) and (len(raw) != BASE_SIZE or sha_now != want) \
                and not args.force:
            raise SystemExit(
                '!! 基线指纹不符，拒绝打补丁\n'
                '   实测 %d 字节 / sha256 %s\n'
                '   期望 %d 字节 / sha256 %s\n'
                '   （= patch_3 + patch_simple + patch_relay + patch_relay2 '
                '+ patch_relay_fix）\n'
                '   本补丁必须以 %d B 的文件为基线；如果你的文件是 %d B / %s，\n'
                '   先把前四层按顺序打上：patch_relay.py --apply -> '
                'patch_relay2.py --apply -> patch_relay_fix.py --apply。\n'
                '   确认无误可加 --expect-sha <实测sha> 或 --force。'
                % (len(raw), sha_now, BASE_SIZE, want, BASE_SIZE,
                   RLFIXED_SIZE, RLFIXED_SHA256))
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
                i = orig.index(ANCHOR_INSERT)
                print('  [helper] 插到第 %d 行之前（RLFIX 块尾部，END 行之前）'
                      % (orig[:i].count('\n') + 1,))
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
                b_txt = b_txt[:rng[0]] + '# ...[helper 正文见 patch_relay_fix2.py]...\n' \
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
        print('补丁后大小: %d B（基线 %d B，净增 %+d B）'
              % (len(new_text.encode('utf-8')), BASE_SIZE,
                 len(new_text.encode('utf-8')) - BASE_SIZE))
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
        print('  （或 python patch_relay_fix2.py --src %s --rollback）' % args.src)
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
