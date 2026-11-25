#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""deploy_all.py —— 把 6+1 条并行线产出的补丁整合成一个可执行、可回滚的部署流程。

六个补丁全都落在同一个 account_auth_probe.py（patch_requestid 落 cn_wire.py），
而且互相之间**没有任何文本重叠**（已实测，见 deploy/DEPLOY_PLAN.md §1）。
真正的问题不是冲突，是两件架构性的事：

  A. path A 抢跑：线上 cn_bridge_exp.txt = decrypt+plain+http200 时，
     _bridge() 的 path A 会把「协议名能解析」的请求代理给 Shittim 并直接 return，
     于是 _generic_protocol_response() 里我们写的 1005/4000/26000/8000 分支成了死代码。
     -> 由 patch_preempt.py（本流程第 7 步）加白名单拦截解决。

  B. 信封不变量：官方 109/109 响应满足 outer.requestid == inner packet.RequestId，
     而客户端下一条请求的 REQUEST-ID 头取自 **inner** 那个。
     -> 由 patch_requestid.py（第 1 步，改 cn_wire.build_plaintext 这个唯一 choke point）
        保证；patch_90004.py 顺带把 _cn_send_envelope 的 outer rid 改成 obj['RequestId']。

应用顺序（经论证，见 DEPLOY_PLAN.md §2）
────────────────────────────────────────
    1  patch_requestid.py    cn_wire.py          信封层唯一 choke point（另一个文件，先立不变量）
    2  patch_90004.py        bridge              90004 分支体 + 内联 DTO 块 + _cn_send_envelope 的 rid
    3  patch_1017.py         bridge              block_a（class Handler 之前）+ block_b（1019 分支之前）
    4  patch_24000_v2.py     bridge              managed block + 24000 分支体
    5  patch_8000.py         bridge              managed block + 8000 分支（插入点用 24000 分支做锚）
    6  patch_simple.py       bridge              PAYLOAD + HOOK-D + HOOK-G（1005/4000/26000）
    7  patch_preempt.py      bridge              路由器白名单（必须最后，它要看到全部已实现分支）

为什么是这个顺序：文本上七步是可交换的（已实测 4 种排列，最终都是 105,725 B / 六个补丁的
marker 各就各位）；但语义上有两条硬依赖，所以顺序仍然固定：

  · patch_requestid 先于 patch_90004：前者在 cn_wire.build_plaintext 里建立
    「outer rid 会写进 inner RequestId」这条通道，后者才谈得上「把 obj['RequestId']
    提到 outer」。反过来的话 90004 的 outer_rid 改动在 cn_wire 未打补丁时无从验证。
  · patch_24000 先于 patch_8000：patch_8000 的 find_insert_point() 用
    `if num == 24000:` 分支的**结束位置**当插入锚；先让 24000 定型，8000 插进去的位置
    就是终态位置，而不是插在一个马上要被整段重写的旧分支后面。
  · patch_preempt 最后：它的 --verify 要枚举「已实现协议」，且它插在 class Handler
    之前（紧挨 patch_1017 的 block_a 之后），最后插保证 diff 最小、位置确定。

每步之后的验证（--apply 每步都会自动做，做不过就立刻停）
──────────────────────────────────────────────────────
    1. 该补丁自己的 marker 数量正确
    2. 之前所有补丁的 marker **仍然**数量正确（互不覆盖）
    3. python -m py_compile 通过
    4. 任何一步失败 => 立刻停在那一步，打印已完成的步骤 + 单步回滚命令。

用法
────
    # 只看：每一步会改什么（在 _scratch 的副本上真跑一遍并给出 diff，正式文件一个字节不动）
    python deploy/deploy_all.py --dry-run

    # 正式打（自动：备份 <target>.bapatch_orig.<ts> + 写 manifest + 逐步自检 + 收尾全量 verify）
    python deploy/deploy_all.py --apply

    # 全量验证（见 --verify 一节）
    python deploy/deploy_all.py --verify

    # 一次性回滚全部（按逆序调用每个补丁自己的 --rollback；最后比 sha256，不符就用原件覆盖）
    python deploy/deploy_all.py --rollback

    # 当前每个补丁的状态
    python deploy/deploy_all.py --status

路径
────
    --target     默认 /www/wwwroot/bapatch/tools/account_auth_probe.py
    --cn-wire    默认 /www/wwwroot/bapatch/tools/cn_wire.py
    --base       默认 <deploy>/_baseline/account_auth_probe.py（54,026 B 基线）
    --sandbox    强制在 <deploy>/_sandbox/deploy_all/ 里演练（默认：--target 不存在时自动进沙箱）
    --seed       先把 _baseline 复制进沙箱（覆盖沙箱里现有的）
本地演练（不碰线上、不碰 _baseline）：
    python deploy/deploy_all.py --seed --apply
    python deploy/deploy_all.py --verify
    python deploy/deploy_all.py --rollback
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
import types

sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))

LIVE_TARGET = '/www/wwwroot/bapatch/tools/account_auth_probe.py'
LIVE_CN_WIRE = '/www/wwwroot/bapatch/tools/cn_wire.py'
LIVE_PREEMPT_SWITCH = '/www/wwwroot/bapatch/cn_preempt.txt'

BASE_PATH = os.path.join(HERE, '_baseline', 'account_auth_probe.py')
BASE_SHA = 'f94b4fa05d95d4c8719f5623322b75629b81eed59442370dd552db721437dbc9'
BASE_BYTES = 54026
BASE_LINES = 1245

SANDBOX_DIR = os.path.join(HERE, '_sandbox', 'deploy_all')
SCRATCH_DIR = os.path.join(HERE, '_scratch', 'deploy_all')
RIG_DIR = os.path.join(HERE, '_verify_rig')
REPORT_DIR = os.path.join(HERE, '_report')

SPEC_CHECK = os.path.abspath(os.path.join(ROOT, 'work', 'ba', 'proto', 'spec_check.py'))
SPEC_JSON = os.path.abspath(os.path.join(ROOT, 'work', 'ba', 'proto', 'official_spec.json'))

ACCT_ID = 10015354380
MXTOKEN = 'M' * 64
RIG_BRIDGE = os.path.join(RIG_DIR, 'account_auth_probe.py')

# ================================================================ 步骤表
# 顺序即执行顺序。24000 排在最前（除 cn_wire 外），因为 patch_24000_v3 有**基线守卫**：
# 目标 sha256 必须等于 54,026 B 基线（f94b4fa0…），否则 exit 2 拒绝改文件。
# 所以它必须先碰到还没被别的补丁改过的 bridge。真要在一个非原始目标上打，
# step_args() 会自动补 --allow-other-baseline 并打印原因。
STEPS = [
    dict(
        key='requestid', script='patch_requestid.py', arg_key='cn_wire',
        arg_flag='--target', verify_flag='--verify',
        markers=[('# >>> BA_PATCH_REQUESTID v1', 1),
                 ('# <<< BA_PATCH_REQUESTID v1 <<<', 1),
                 ('# BA_PATCH_REQUESTID v1: outer requestid == inner RequestId', 1)],
        optional=True,
        why='信封层唯一 choke point：outer.requestid 会写进 inner RequestId（109/109 官方证据）',
    ),
    dict(
        key='24000', script='patch_24000_v2.py', arg_key='bridge',
        arg_flag='--target', verify_flag='--verify',
        markers=[('# ==== BEGIN 24000_v2 (managed block) ====', 1),
                 ('# ==== END 24000_v2 (managed block) ====', 1)],
        baseline_guard=True,
        why='24000 Academy_GetInfo 规则驱动渲染（v3 有基线守卫，所以它第一个碰 bridge）',
    ),
    dict(
        key='90004', script='patch_90004.py', arg_key='bridge',
        arg_flag='--src', verify_flag='--verify',
        markers=[('# ==== BEGIN 90004-PATCH v1', 1),
                 ('# ==== END 90004-PATCH v1 ====', 1),
                 ('# 90004-PATCH: outer requestid = inner RequestId', 1)],
        why='90004 Management_Data 官方 6 键外壳 + 内联 dto90004 + _cn_send_envelope 的 outer rid',
    ),
    dict(
        key='1017', script='patch_1017.py', arg_key='bridge',
        arg_flag='--target', verify_flag='--verify',
        markers=[('# >>> BA-1017-DYNAMIC-PATCH v1', 2),
                 ('# <<< BA-1017-DYNAMIC-PATCH v1 <<<', 2)],
        why='1017 动态生成（35 键）；旧 7 行 1019/1017 分支逐字保留做 fallback',
    ),
    dict(
        key='8000', script='patch_8000.py', arg_key='bridge',
        arg_flag='--target', verify_flag='--verify',
        markers=[('# ==== BEGIN 8000_mission_list (managed block) ====', 1),
                 ('# ==== END 8000_mission_list (managed block) ====', 1)],
        why='8000 Mission_List 目录驱动（7153 条 catalog）+ 独立开关 8000_switch.json',
    ),
    dict(
        key='simple', script='patch_simple.py', arg_key='bridge',
        arg_flag='--bridge', verify_flag='--verify',
        markers=[('# >>> BAPATCH-SIMPLE-PAYLOAD v1 BEGIN', 1),
                 ('# >>> BAPATCH-SIMPLE-HOOK-D v1 BEGIN', 1),
                 ('# >>> BAPATCH-SIMPLE-HOOK-G v1 BEGIN', 1)],
        why='1005 / 4000 / 26000 官方结构（simple_payload.py 唯一真源，逐字节内嵌）',
    ),
    dict(
        key='preempt', script='patch_preempt.py', arg_key='bridge',
        arg_flag='--target', verify_flag='--verify',
        markers=[('# >>> BAPATCH-ROUTER-PREEMPT v1 BEGIN (B1-module) >>>', 1),
                 ('# >>> BAPATCH-ROUTER-PREEMPT v1 BEGIN (B2-method) >>>', 1),
                 ('# >>> BAPATCH-ROUTER-PREEMPT v1 BEGIN (B3-callsite) >>>', 1)],
        why='path A 之前插协议白名单拦截 —— 否则 1005/4000/26000/8000 的分支是死代码',
    ),
]

# 已实现协议清单（渲染验证用）。
#   branch : 在 _generic_protocol_response() 里有专属分支
#   hook   : 由 patch_simple 的 HOOK-G 接管
#   none   : 只有生成器（deploy/gen*.py），bridge 里没有分支，现在会被 path A 代理给 Shittim
PROTOCOLS = [
    dict(num=24000, name='Academy_GetInfo', via='branch', gen=None),
    dict(num=1017, name='Account_LoginSync', via='branch', gen='gen1017.py'),
    dict(num=1005, name='Account_GetTutorial', via='hook', gen=None),
    dict(num=4000, name='Item_List', via='hook', gen=None),
    dict(num=26000, name='ContentSave_Get', via='hook', gen=None),
    dict(num=8000, name='Mission_List', via='branch', gen=None),
    dict(num=90004, name='Management_Data', via='branch', gen=None),
    dict(num=8006, name='Mission_GuideMissionSeasonList', via='none', gen='gen8006.py'),
    dict(num=3, name='NetworkTime_Sync', via='none', gen='gen3.py'),
    dict(num=36001, name='Notification_EventContentReddotCheck', via='none', gen='gen36001.py'),
]


# ================================================================ 小工具
class DeployError(Exception):
    pass


def die(msg, code=2):
    sys.stderr.write('[deploy] !! %s\n' % msg)
    raise SystemExit(code)


def read_text(path):
    with io.open(path, 'r', encoding='utf-8', newline='') as fh:
        return fh.read()


def write_text(path, text):
    d = os.path.dirname(os.path.abspath(path)) or '.'
    if d and not os.path.isdir(d):
        os.makedirs(d)
    with io.open(path, 'w', encoding='utf-8', newline='') as fh:
        fh.write(text)


def count_lines(text):
    """行数（与 wc -l / Get-Content 一致的「行」定义：末尾换行不算新行）。"""
    if not text:
        return 0
    return text.count('\n') + (0 if text.endswith('\n') else 1)


# patch_24000 有两个版本共存：v2（43,213 B）与 v3（60,504 B，会顺手拆掉 v2 的托管块）。
# 默认优先 v3；两个的托管块标记不同，所以 marker 必须跟着选中的脚本走，不能写死。
_R24000_DONE = False


def resolve_24000(explicit=None):
    """→ (script_name, block_begin, block_end)。"""
    global _R24000_DONE
    _R24000_DONE = True
    if explicit:
        name = os.path.basename(explicit)
    elif os.path.exists(os.path.join(HERE, 'patch_24000_v3.py')):
        name = 'patch_24000_v3.py'
    else:
        name = 'patch_24000_v2.py'
    path = os.path.join(HERE, name)
    text = read_text(path) if os.path.exists(path) else ''
    m = re.search(r"^BLOCK_BEGIN = '# ==== BEGIN (.*?) \(managed block\) ===='", text, re.M)
    e = re.search(r"^BLOCK_END = '# ==== END (.*?) \(managed block\) ===='", text, re.M)
    tag_b = m.group(1) if m else ('24000_v3' if 'v3' in name else '24000_v2')
    tag_e = e.group(1) if e else tag_b
    begin = '# ==== BEGIN %s (managed block) ====' % tag_b
    end = '# ==== END %s (managed block) ====' % tag_e
    for st in STEPS:
        if st['key'] == '24000':
            st['script'] = name
            st['markers'] = [(begin, 1), (end, 1)]
            st['why'] = ('24000 Academy_GetInfo 规则驱动渲染（%s）' % name)
    return name, begin, end


def sha256_file(path):
    with open(path, 'rb') as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def sha256_text(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def stamp():
    return time.strftime('%Y%m%d-%H%M%S')


def norm_live_path(p):
    """线上路径是 POSIX 的 `/www/wwwroot/...`。

    在 Windows 上 os.path.abspath() 会把它变成 `C:\\www\\wwwroot\\...`（凭空造个盘符），
    那是个不存在的路径，后面读开关就会一直读到「缺失」。所以：
      * 已经是 POSIX 绝对路径的（以 / 开头且没有盘符）原样保留；
      * 其它才走 abspath。
    """
    if not p:
        return p
    if p.startswith('/') and not re.match(r'^/[A-Za-z]:', p):
        return p
    return os.path.abspath(p)


def path_under(p, d):
    try:
        return os.path.commonpath([os.path.abspath(p), os.path.abspath(d)]) == \
               os.path.abspath(d)
    except Exception:
        return False


def rule(ch='-', n=78):
    return ch * n


def run_py(script, args, timeout=300):
    """跑 deploy/ 下的补丁脚本。-> (rc, stdout+stderr)"""
    script_path = os.path.join(HERE, script)
    if not os.path.exists(script_path):
        return 127, '脚本不存在: %s' % script_path
    cmd = [sys.executable, script_path] + list(args)
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    try:
        p = subprocess.run(cmd, cwd=HERE, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        return 124, '超时 %ds: %s' % (timeout, ' '.join(cmd))
    except Exception as e:
        return 125, '起不来: %r' % (e,)
    return p.returncode, p.stdout.decode('utf-8', 'replace')


def py_compile_ok(path):
    """子进程跑 python -m py_compile（和线上重启前的检查一致）。"""
    env = dict(os.environ)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    try:
        p = subprocess.run([sys.executable, '-m', 'py_compile', path],
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           timeout=120, env=env)
    except Exception as e:
        return False, repr(e)
    if p.returncode == 0:
        return True, ''
    return False, p.stdout.decode('utf-8', 'replace').strip()[:400]


def tail(text, n=14):
    lines = [ln for ln in text.replace('\r', '').split('\n') if ln.strip()]
    return '\n'.join(lines[-n:])


def marker_report(text, markers):
    rows = []
    ok = True
    for needle, want in markers:
        got = text.count(needle)
        good = (got == want)
        ok = ok and good
        rows.append((needle, want, got, good))
    return ok, rows


# ================================================================ 上下文 / 预检
class Ctx(object):
    pass


def resolve_ctx(a):
    """决定 target / cn_wire / sandbox，并做预检。"""
    if not _R24000_DONE:
        resolve_24000()
    c = Ctx()
    c.base = os.path.abspath(a.base)
    c.base_ok = os.path.exists(c.base)
    c.base_sha = sha256_file(c.base) if c.base_ok else None
    c.base_bytes = os.path.getsize(c.base) if c.base_ok else 0
    c.base_lines = count_lines(read_text(c.base)) if c.base_ok else 0

    target = os.path.abspath(a.target)
    if a.sandbox:
        c.sandbox = True
        c.target = os.path.join(SANDBOX_DIR, 'account_auth_probe.py')
    elif not os.path.exists(target):
        c.sandbox = True
        c.target = os.path.join(SANDBOX_DIR, 'account_auth_probe.py')
        print('[deploy] 目标 %s 不存在 -> 自动进沙箱：%s' % (target, c.target))
    else:
        c.sandbox = False
        c.target = target

    c.dir = os.path.dirname(c.target)
    c.cn_wire = norm_live_path(a.cn_wire)
    c.cn_wire_mode = 'live' if (a.cn_wire and os.path.exists(c.cn_wire)) else 'missing'
    if a.no_cn_wire:
        c.cn_wire_mode = 'off'
    # 开关文件：沙箱里就放在沙箱目录，免得把本地演练的开关写到线上路径上去
    if a.switch_file:
        c.preempt_switch = norm_live_path(a.switch_file)
    elif c.sandbox:
        c.preempt_switch = os.path.join(c.dir, 'cn_preempt.txt')
    else:
        c.preempt_switch = LIVE_PREEMPT_SWITCH

    # 沙箱里没有 _baseline 之外的「现成文件」；--seed 时从 base 复制
    if c.sandbox:
        if a.seed or not os.path.exists(c.target):
            if not c.base_ok:
                die('基线不存在，无法 seed: %s' % c.base)
            if not os.path.isdir(SANDBOX_DIR):
                os.makedirs(SANDBOX_DIR)
            shutil.copy2(c.base, c.target)
            print('[deploy] 已 seed 沙箱: %s -> %s' % (c.base, c.target))
    return c


def preflight(c, quiet=False):
    """→ ok, rows。基线 / 目标 的身份核对。"""
    rows = []
    ok = True

    def add(good, name, detail=''):
        nonlocal ok
        ok = ok and bool(good)
        rows.append((name, bool(good), detail))

    add(c.base_ok, '基线文件存在', c.base if c.base_ok else '缺失')
    if c.base_ok:
        add(c.base_sha == BASE_SHA, '基线 sha256 == 官方记录',
            '%s (期望 %s)' % (c.base_sha[:16], BASE_SHA[:16]))
        add(c.base_bytes == BASE_BYTES, '基线大小 == 54,026 B', '%d B' % c.base_bytes)
        add(c.base_lines == BASE_LINES, '基线行数 == 1,245', '%d 行' % c.base_lines)
    add(os.path.exists(c.target), '目标文件存在', c.target)
    if os.path.exists(c.target):
        t = read_text(c.target)
        add('class Handler(http.server.BaseHTTPRequestHandler):' in t,
            '目标看起来是 account_auth_probe.py', '%d B' % os.path.getsize(c.target))
        # 关键锚点唯一性（后面每个补丁都指望它们唯一）
        for label, anchor in (('want_decrypt 锚点', "        want_decrypt = exp.startswith('decrypt+')"),
                              ('_generic_protocol_response 锚点',
                               '    def _generic_protocol_response(self, proto_str, packet_b64, rec, name=None):'),
                              ('class Handler 锚点',
                               'class Handler(http.server.BaseHTTPRequestHandler):')):
            n = t.count(anchor)
            add(n == 1, label + ' 唯一', '%d 处' % n)
    if not quiet:
        for name, good, detail in rows:
            print('  %-46s %s  %s' % (name, 'PASS' if good else 'FAIL', detail))
    return ok, rows


# ================================================================ 步骤执行
def step_args(step, c, mode):
    """→ [script, args]。mode: apply/dry/verify/rollback"""
    flag = {'apply': '--apply', 'dry': '--dry-run',
            'verify': '--verify', 'rollback': '--rollback'}[mode]
    target = c.cn_wire if step['arg_key'] == 'cn_wire' else c.target
    args = [step['arg_flag'], target, flag]
    if step['key'] == 'preempt':
        args += ['--switch-file', c.preempt_switch]
    if step['key'] == 'requestid' and step['arg_key'] == 'cn_wire':
        args = ['--target', target, flag]
    # 24000 的 v3 有基线守卫：目标 sha256 必须等于 54,026 B 基线。
    # 它按设计是第一个碰 bridge 的补丁，所以正常情况下守卫成立；
    # 如果目标已经不是原始件（例如在别人的半成品上续跑），显式放行并在调用方打印原因。
    if step.get('baseline_guard') and os.path.exists(c.target):
        if sha256_file(c.target) != BASE_SHA and script_has_flag(step['script'],
                                                                 '--allow-other-baseline'):
            args.append('--allow-other-baseline')
    return step['script'], args


_FLAG_CACHE = {}


def script_has_flag(script, flag):
    """补丁脚本是否支持某个 CLI 开关（v3 有 --allow-other-baseline，v2 没有）。"""
    key = (script, flag)
    if key not in _FLAG_CACHE:
        p = os.path.join(HERE, script)
        try:
            _FLAG_CACHE[key] = flag in read_text(p)
        except Exception:
            _FLAG_CACHE[key] = False
    return _FLAG_CACHE[key]


def baseline_guard_override(step, c):
    """→ 需要打印的说明（不需要则为 None）。"""
    if not step.get('baseline_guard') or not os.path.exists(c.target):
        return None
    if sha256_file(c.target) == BASE_SHA:
        return None
    return ('目标 sha256 != 基线，%s 的基线守卫被 --allow-other-baseline 放行；'
            '锚点仍要求 `if num == 24000:` 唯一存在' % step['key'])


def step_skip_reason(step, c):
    """→ None 表示要跑；否则返回跳过原因。"""
    if step['arg_key'] == 'cn_wire':
        if c.cn_wire_mode == 'off':
            return '--no-cn-wire'
        if not os.path.exists(c.cn_wire):
            return 'cn_wire.py 不存在：%s（用 --cn-wire 指定，或先让第 0 步的 fixture 顶上）' \
                   % c.cn_wire
    return None


def verify_markers(step, path):
    if not os.path.exists(path):
        return False, [(n, w, 0, False) for n, w in step['markers']]
    return marker_report(read_text(path), step['markers'])


def check_previous(c, upto_idx, quiet=True):
    """之前已应用的步骤，marker 是否仍然完整。-> (ok, [failed_keys])"""
    bad = []
    for st in STEPS[:upto_idx]:
        if step_skip_reason(st, c):
            continue
        path = c.cn_wire if st['arg_key'] == 'cn_wire' else c.target
        ok, _ = verify_markers(st, path)
        if not ok:
            bad.append(st['key'])
    return (not bad), bad


def compile_target(c):
    bad = []
    if os.path.exists(c.target):
        ok, why = py_compile_ok(c.target)
        if not ok:
            bad.append(('account_auth_probe.py', why))
    if c.cn_wire_mode == 'live' and os.path.exists(c.cn_wire):
        ok, why = py_compile_ok(c.cn_wire)
        if not ok:
            bad.append(('cn_wire.py', why))
    return (not bad), bad


# ================================================================ cn_wire 替身
# patch_requestid 的目标是 cn_wire.py，本地没有那份文件。为了能在离线环境里
# **真的**验证它的锚点与变换（而不是只打印一句 SKIP），这里生成一个只复刻
# patch_requestid 依赖形状的最小替身。它不参与任何线上行为，也不会进 _baseline。
CN_WIRE_FIXTURE = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cn_wire.py 最小替身 —— 由 deploy/deploy_all.py 生成，仅用于验证 patch_requestid。

不是线上文件，不参与线上行为。只复刻 patch_requestid.py 依赖的两个锚点：
    requestid = requestid or str(uuid.uuid4())
    plain = json.dumps({
"""
import base64
import hashlib
import json
import os
import uuid


def build_plaintext(proto_name, inner_obj, requestid=None):
    requestid = requestid or str(uuid.uuid4())
    packet = json.dumps(inner_obj, ensure_ascii=False, separators=(',', ':'))
    plain = json.dumps({
        'protocol': proto_name,
        'packet': packet,
        'requestid': requestid,
    }, ensure_ascii=False, separators=(',', ':'))
    return b'WIRE:' + plain.encode('utf-8'), plain, b'0' * 32


def wrap_response(proto_name, inner_obj, requestid=None):
    return build_plaintext(proto_name, inner_obj, requestid)


def wrap_raw(plaintext):
    return b'WIRE:' + plaintext, plaintext, b'0' * 32
'''


def make_cn_wire_fixture(path):
    write_text(path, CN_WIRE_FIXTURE)


def test_cn_wire_fixture(dirpath=None):
    """在替身上真跑一次 patch_requestid，并功能性验证「inner RequestId 被同步成 outer」。"""
    d = dirpath or os.path.join(SCRATCH_DIR, 'cn_wire_fixture')
    if os.path.isdir(d):
        shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    fx = os.path.join(d, 'cn_wire.py')
    make_cn_wire_fixture(fx)
    before = sha256_file(fx)
    rc, out = run_py('patch_requestid.py', ['--target', fx, '--apply'])
    rows = []
    ok = (rc == 0)
    rows.append(('patch_requestid 在 cn_wire 形状文件上 --apply', rc == 0, 'exit=%d' % rc))
    if not ok:
        rows.append(('输出尾巴', False, tail(out, 6)))
        return False, rows, {}
    text = read_text(fx)
    rows.append(('helper 块存在', '# >>> BA_PATCH_REQUESTID v1' in text,
                 '%d 处' % text.count('# >>> BA_PATCH_REQUESTID v1')))
    rows.append(('调用语句存在', 'inner_requestid_apply(inner_obj, requestid)' in text, ''))
    okc, why = py_compile_ok(fx)
    rows.append(('替身 py_compile', okc, why))
    # 功能性验证：请求进去，inner packet 的 RequestId 必须等于传进去的 requestid
    functional = False
    detail = ''
    rid = '11111111-2222-3333-4444-555555555555'
    for case in ({'Protocol': 8000, 'SessionKey': {'AccountServerId': ACCT_ID}},
                 {'Protocol': 8000, 'RequestId': 'stale-should-be-overwritten'},
                 {'Protocol': 90004}):
        try:
            ns = {'__name__': 'fixture_probe'}
            exec(compile(read_text(fx), fx, 'exec'), ns)
            _body, plain, _key = ns['build_plaintext']('Mission_List', dict(case), rid)
            obj = json.loads(json.loads(plain)['packet'])
            got = obj.get('RequestId')
            good = (got == rid) and (json.loads(plain).get('requestid') == rid)
            if not good:
                detail = 'case=%r -> inner RequestId=%r' % (case, got)
                break
            functional = True
        except Exception as e:
            detail = repr(e)
            functional = False
            break
    rows.append(('替身功能：inner RequestId == outer requestid（插入/覆盖/缺省三种）',
                 functional, detail))
    return (ok and functional), rows, {'sha_before': before, 'sha_after': sha256_file(fx)}


# ================================================================ 渲染台（rig）
def install_stub_modules(captured):
    """bridge 顶部 import cn_cipher / cn_wire / cn_inner / cn_inner27 / cn_nick。

    cn_wire.wrap_response 这里**复刻 patch_requestid 打完补丁后的行为**：
    先 inner_requestid_apply(inner_obj, requestid)，再拼 plaintext。
    注意：这是 cn_wire 的**模型**；cn_wire.py 本身是否真的这样，由
    test_cn_wire_fixture() 在替身上单独证明。
    """
    try:
        import patch_requestid as PR
        apply_fn = PR.inner_requestid_apply
    except Exception:
        apply_fn = None

    if 'cn_wire' not in sys.modules:
        m = types.ModuleType('cn_wire')

        def wrap_response(proto_name, inner_obj, requestid=None, **kw):
            if requestid is None and isinstance(inner_obj, dict):
                requestid = inner_obj.get('RequestId')
            if apply_fn is not None:
                apply_fn(inner_obj, requestid)
            packet = json.dumps(inner_obj, ensure_ascii=False, separators=(',', ':'))
            plain = json.dumps({'protocol': proto_name, 'packet': packet,
                                'requestid': requestid},
                               ensure_ascii=False, separators=(',', ':'))
            captured.clear()
            captured.update({'proto_name': proto_name, 'obj': inner_obj,
                             'requestid': requestid, 'packet': packet, 'plain': plain})
            return b'WIRE:' + plain.encode('utf-8'), plain, b'0' * 32

        m.wrap_response = wrap_response
        m.wrap_raw = lambda plaintext: (b'WIRE', plaintext, b'0' * 32)
        m.unwrap_response = lambda raw: ({}, {}, b'', '')
        sys.modules['cn_wire'] = m
    else:
        sys.modules['cn_wire'].wrap_response = wrap_response
    for name in ('cn_cipher', 'cn_inner', 'cn_inner27', 'cn_nick'):
        if name not in sys.modules:
            m = types.ModuleType(name)
            m.STATIC_OPEN_CONDITIONS = {}
            sys.modules[name] = m
        elif not hasattr(sys.modules[name], 'STATIC_OPEN_CONDITIONS'):
            sys.modules[name].STATIC_OPEN_CONDITIONS = {}


def prepare_rig(bridge_text):
    """把打补丁后的 bridge 拷进一个自洽的目录，并补齐它运行时会读的数据文件。"""
    if os.path.isdir(RIG_DIR):
        shutil.rmtree(RIG_DIR, ignore_errors=True)
    os.makedirs(RIG_DIR)
    write_text(RIG_BRIDGE, bridge_text)
    # gen1017：block_b 用 BA_GEN1017_DIR 或 bridge 同目录 import gen1017
    src = os.path.join(HERE, 'gen1017.py')
    if os.path.exists(src):
        shutil.copy2(src, os.path.join(RIG_DIR, 'gen1017.py'))
    # 1005 / 4000 / 26000 的运行时开关（缺失=关，会让 HOOK-G 不接管）
    for n, fn in ((1005, 'cn_1005.txt'), (4000, 'cn_4000.txt'), (26000, 'cn_26000.txt')):
        write_text(os.path.join(RIG_DIR, fn), '1\n')
    # 8000 的开关（缺省 enabled=true，但显式写一份免得读到线上文件）
    write_text(os.path.join(RIG_DIR, '8000_switch.json'), json.dumps({
        '_comment': 'deploy_all.py 渲染台专用，enabled=true',
        'enabled': True, 'profile': 'seed', 'reset_hour': 4,
        'daily_sudden_id': 1606, 'max_progress': 5000,
    }, ensure_ascii=False, indent=1) + '\n')
    # 拦截开关（渲染时用 $CN_PREEMPT 覆盖，这里放 off 做兜底）
    write_text(os.path.join(RIG_DIR, 'cn_preempt.txt'), 'off\n')
    return RIG_DIR


def _frag_for(num, extra=None):
    """合成一份「解出来的请求明文」：够各个分支解析出账号与协议号即可。"""
    obj = {
        'Protocol': num,
        'Hash': num << 32,
        'IsTest': False,
        'SessionKey': {'AccountServerId': ACCT_ID, 'MxToken': MXTOKEN},
        'AccountId': ACCT_ID,
        'OSType': 2,
    }
    if extra:
        obj.update(extra)
    return json.dumps(obj, ensure_ascii=False, separators=(',', ':'))


class FakeHandler(object):
    """只提供 _cn_decode_any；_generic_protocol_response / _cn_send_envelope 绑真的。

    绑真的（而不是另写一份）是关键：这样 outer requestid 到底取自哪里
    （patch_90004 改的 _cn_send_envelope）也是真跑出来的，不是我在测试里重写一遍。
    """

    _last_decode_err = ''

    def __init__(self, frag):
        self._frag = frag

    def _cn_decode_any(self, packet_b64, proto_str):
        return self._frag


def load_rig_ns(bridge_text, captured):
    install_stub_modules(captured)
    prepare_rig(bridge_text)
    os.environ['BA_GEN1017_DIR'] = HERE          # 让 block_b 找到 gen1017.py
    ns = {'__name__': 'ba_deploy_rig', '__file__': RIG_BRIDGE}
    exec(compile(bridge_text, RIG_BRIDGE, 'exec'), ns)
    sess = ns.get('SESSION')
    if sess is not None:
        try:
            sess.session_key = {'AccountServerId': ACCT_ID, 'MxToken': MXTOKEN}
            sess.account_id = ACCT_ID
        except Exception:
            pass
    return ns


def reachability(ns):
    """→ {proto_num: 'L1088'|'path-A'}。

    线上 _bridge() 里，协议名能解析（NAME_TABLE 命中）的请求会被 path A 抢跑去代理
    Shittim；解析不到的才走 L1088 直达 _generic_protocol_response。
    => 24000 / 1017 / 90004 这类「名字不在表里」的协议**根本不需要 preempt**；
       8000 / 1005（名字在 BUILTIN_NAMES 里）没有 preempt 就是死代码。
    本地只有 BUILTIN_NAMES 可用（线上还会读 protocol_names.txt，所以只会更多）。
    """
    out = {}
    try:
        if callable(ns.get('load_names')):
            ns['load_names']()
        table = ns.get('NAME_TABLE') or {}
        b32 = ns.get('b32md5')
        for p in PROTOCOLS:
            got = None
            if callable(b32):
                try:
                    got = table.get(b32(p['name']))
                except Exception:
                    got = None
            out[p['num']] = 'path-A' if got else 'L1088'
    except Exception:
        pass
    return out


def render_one(ns, captured, num, name):
    """用打补丁后的 bridge 渲染一次该协议。-> dict(result)"""
    H = ns.get('Handler')
    out = {'num': num, 'name': name, 'ok': False, 'via': None,
           'gen_kind': None, 'inner_bytes': 0, 'top_keys': 0,
           'inner_rid': None, 'outer_rid': None, 'rid_match': False,
           'note': '', 'obj': None}
    if H is None:
        out['note'] = '没有 class Handler'
        return out

    frag = _frag_for(num)
    h = FakeHandler(frag)
    for meth in ('_generic_protocol_response', '_cn_send_envelope', '_preempt_response'):
        fn = getattr(H, meth, None)
        if fn is not None:
            setattr(h, meth, types.MethodType(fn, h))

    rec = {}
    got = None
    # 先走路由器（把白名单也一并验证了）
    if hasattr(h, '_preempt_response'):
        old = os.environ.get('CN_PREEMPT')
        try:
            os.environ['CN_PREEMPT'] = str(num)
            got = h._preempt_response(name, 'tok', 'stub-packet-b64', rec)
            out['via'] = 'preempt(%s)' % rec.get('preempt')
        finally:
            if old is None:
                os.environ.pop('CN_PREEMPT', None)
            else:
                os.environ['CN_PREEMPT'] = old
    if got is None:
        try:
            got = h._generic_protocol_response('tok', 'stub-packet-b64', rec, name=name)
            out['via'] = out['via'] or 'direct'
        except Exception as e:
            out['note'] = '分支抛异常: %r' % (e,)
            return out

    out['gen_kind'] = rec.get('gen_kind')
    if got is None:
        out['note'] = '没有分支产出响应（会被 path A 代理给 Shittim）'
        return out
    cap = dict(captured)
    obj = cap.get('obj')
    out['obj'] = obj
    if not isinstance(obj, dict):
        out['note'] = 'wrap_response 没拿到 dict'
        return out
    out['inner_bytes'] = len(cap.get('packet', '').encode('utf-8'))
    out['top_keys'] = len(obj)
    out['inner_rid'] = obj.get('RequestId')
    out['outer_rid'] = cap.get('requestid')
    out['rid_match'] = bool(out['inner_rid']) and out['inner_rid'] == out['outer_rid']
    out['ok'] = True
    return out


def spec_check_proto(num, obj):
    """→ (verdict, fails, warns, detail)。优先走 spec_check.py（子进程，逐条按官方 spec）。"""
    tmpdir = os.path.join(RIG_DIR, '_responses')
    if not os.path.isdir(tmpdir):
        os.makedirs(tmpdir)
    path = os.path.join(tmpdir, 'p%d.json' % num)
    with io.open(path, 'w', encoding='utf-8', newline='') as fh:
        fh.write(json.dumps(obj, ensure_ascii=False, indent=1))
    if not os.path.exists(SPEC_CHECK):
        return 'SKIP', -1, -1, 'spec_check.py 不存在: %s' % SPEC_CHECK
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    try:
        p = subprocess.run([sys.executable, SPEC_CHECK, '--protocol', str(num),
                            '--file', path],
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           timeout=120, env=env)
    except Exception as e:
        return 'ERROR', -1, -1, repr(e)
    text = p.stdout.decode('utf-8', 'replace')
    fails = warns = -1
    m = re.search(r'FAIL\s+(\d+)\s*/\s*WARN\s+(\d+)', text)
    if m:
        fails, warns = int(m.group(1)), int(m.group(2))
    verdict = 'PASS' if (p.returncode == 0 and fails == 0) else 'FAIL'
    if fails < 0:
        verdict = 'PASS' if p.returncode == 0 else 'FAIL'
        detail = tail(text, 4)
    else:
        detail = 'FAIL=%d WARN=%d' % (fails, warns)
    return verdict, fails, warns, detail


def gen_check(step_script, num):
    """对 bridge 还没接的协议，用 deploy/gen*.py 单独渲染一次并跑 spec_check。"""
    path = os.path.join(HERE, step_script)
    if not os.path.exists(path):
        return 'SKIP', '生成器不存在'
    out = os.path.join(RIG_DIR, '_responses', 'gen_%d.json' % num)
    rc, txt = run_py(step_script, ['--out', out], timeout=300)
    if rc != 0:
        return 'FAIL', 'exit=%d' % rc
    verdict = 'PASS' if 'spec_check      : PASS' in txt else 'FAIL'
    m = re.search(r'spec_check\s*:\s*(\w+)\s+FAIL\s+(\d+)\s*/\s*WARN\s+(\d+)', txt)
    detail = ('FAIL=%s WARN=%s' % (m.group(2), m.group(3))) if m else ''
    return verdict, detail


# ================================================================ --verify
def cmd_verify(a, ctx=None):
    c = ctx or resolve_ctx(a)
    print(rule('='))
    print('全量验证  target=%s' % c.target)
    print(rule('='))
    t0 = time.time()
    all_ok = True
    report = {'ts': stamp(), 'target': c.target, 'sandbox': c.sandbox,
              'target_sha256': sha256_file(c.target) if os.path.exists(c.target) else None,
              'steps': [], 'protocols': [], 'checks': []}

    def chk(good, name, detail=''):
        nonlocal all_ok
        all_ok = all_ok and bool(good)
        report['checks'].append({'name': name, 'pass': bool(good), 'detail': detail})
        print('  %-56s %s %s' % (name, 'PASS' if good else 'FAIL', detail))
        return good

    # ---------- 1. marker 全在，且没有互相覆盖
    print('\n[1] 所有补丁的 marker')
    if not os.path.exists(c.target):
        die('目标不存在: %s' % c.target)
    bridge_text = read_text(c.target)
    applied = []
    for st in STEPS:
        path = c.cn_wire if st['arg_key'] == 'cn_wire' else c.target
        skip = step_skip_reason(st, c)
        if skip:
            print('  %-56s SKIP %s' % ('[%s] marker' % st['key'], skip))
            report['steps'].append({'key': st['key'], 'status': 'skip', 'why': skip})
            continue
        if not os.path.exists(path):
            chk(False, '[%s] marker' % st['key'], '文件不存在 %s' % path)
            report['steps'].append({'key': st['key'], 'status': 'missing'})
            continue
        ok, rows = verify_markers(st, path)
        detail = ' '.join('%s=%d/%d' % (n.split('(')[0][:26], g, w) for n, w, g, _ in rows)
        chk(ok, '[%s] marker' % st['key'], detail)
        report['steps'].append({'key': st['key'], 'status': 'applied' if ok else 'broken',
                                'markers': [{'needle': n, 'want': w, 'got': g}
                                            for n, w, g, _ in rows]})
        if ok:
            applied.append(st['key'])

    # ---------- 2. py_compile
    print('\n[2] py_compile')
    okc, bad = compile_target(c)
    chk(okc, 'python -m py_compile', '' if okc else repr(bad))

    # ---------- 3. cn_wire 侧（有真文件就测真的，没有就在替身上测变换）
    print('\n[3] cn_wire（outer requestid 的闸门）')
    if c.cn_wire_mode == 'live':
        okf, rows, _ = test_cn_wire_fixture()
        for name, good, detail in rows:
            chk(good, 'cn_wire 变换: ' + name, detail)
        rc, out = run_py('patch_requestid.py', ['--target', c.cn_wire, '--verify'], timeout=600)
        chk(rc == 0, 'patch_requestid --verify（线上 cn_wire）', 'exit=%d' % rc)
        report['cn_wire'] = {'mode': 'live', 'path': c.cn_wire, 'verify_rc': rc}
    else:
        print('  线上 cn_wire.py 不可用（%s）-> 在替身上验证 patch_requestid 的变换'
              % c.cn_wire_mode)
        okf, rows, meta = test_cn_wire_fixture()
        for name, good, detail in rows:
            chk(good, 'cn_wire 替身: ' + name, detail)
        report['cn_wire'] = {'mode': c.cn_wire_mode, 'fixture': meta}

    # ---------- 4. 逐个协议渲染
    print('\n[4] 逐协议渲染（打补丁后的 bridge，stub 掉加密层，不联网）')
    print('  %-7s %-36s %-13s %-7s %-7s %-9s %-8s %s'
          % ('proto', 'name', 'via', 'innerB', 'keys', 'spec', 'rid', '线上入口'))
    captured = {}
    ns = None
    try:
        ns = load_rig_ns(bridge_text, captured)
    except Exception as e:
        chk(False, '渲染台 exec 打补丁后的 bridge', repr(e))
    reach = reachability(ns) if ns is not None else {}
    for p in PROTOCOLS:
        r = {'num': p['num'], 'name': p['name'], 'via': p['via'],
             'reach': reach.get(p['num'])}
        if ns is None:
            r.update({'status': 'FAIL', 'reason': '渲染台起不来'})
            report['protocols'].append(r)
            continue
        res = render_one(ns, captured, p['num'], p['name'])
        r.update({'gen_kind': res['gen_kind'], 'inner_bytes': res['inner_bytes'],
                  'top_keys': res['top_keys'], 'route': res['via'],
                  'inner_rid': res['inner_rid'], 'outer_rid': res['outer_rid'],
                  'rid_match': res['rid_match'], 'note': res['note']})
        if not res['ok'] or res['gen_kind'] == 'min+base':
            # bridge 里没有这个协议的分支
            expected = (p['via'] != 'none')
            r.update({'status': 'NO-BRIDGE-BRANCH', 'expected_branch': expected,
                      'spec': 'NONE',
                      'spec_detail': '该协议在 bridge 里没有分支，会被 path A 代理给 Shittim',
                      'route': res['via'], 'why': res['note'] or res['gen_kind']})
            gv, gd = ('-', '')
            if p['gen']:
                gv, gd = gen_check(p['gen'], p['num'])
            r['generator'] = {'script': p['gen'], 'spec': gv, 'detail': gd}
            if expected:
                # 我们**以为**它已经有分支了 —— 那就是补丁没生效，算硬失败
                all_ok = False
                r['pass'] = False
                print('  %-7d %-36s %-13s %-7s %-7s %-9s %-8s %s'
                      % (p['num'], p['name'], (res['via'] or '-')[:13], '-', '-',
                         'GEN:' + gv if p['gen'] else '-', 'X',
                         '!! 期望有分支但没有：%s' % (res['note'] or res['gen_kind'])))
            else:
                print('  %-7d %-36s %-13s %-7s %-7s %-9s %-8s %s'
                      % (p['num'], p['name'], (res['via'] or '-')[:13], '-', '-',
                         'GEN:' + gv if p['gen'] else '-', 'X',
                         'no-branch（已知：只有生成器）'))
            report['protocols'].append(r)
            continue
        verdict, fails, warns, sdetail = spec_check_proto(p['num'], res['obj'])
        r.update({'status': 'OK', 'spec': verdict, 'spec_fails': fails,
                  'spec_warns': warns, 'spec_detail': sdetail})
        good = (verdict == 'PASS') and res['rid_match']
        r['pass'] = good
        all_ok = all_ok and good
        reach_txt = {'L1088': 'L1088直通', 'path-A': 'path-A拦截'}.get(r.get('reach'), '?')
        print('  %-7d %-36s %-13s %-7d %-7d %-9s %-8s %s'
              % (p['num'], p['name'], res['via'] or '-', res['inner_bytes'],
                 res['top_keys'], verdict, 'OK' if res['rid_match'] else 'MISMATCH',
                 reach_txt))
        report['protocols'].append(r)

    # ---------- 5. 汇总
    ok_protos = [r for r in report['protocols'] if r.get('status') == 'OK']
    expect = [r for r in report['protocols'] if r.get('via') != 'none']
    nob = [r['num'] for r in report['protocols'] if r.get('status') == 'NO-BRIDGE-BRANCH'
           and not r.get('expected_branch')]
    missing_branch = [r['num'] for r in report['protocols']
                      if r.get('status') == 'NO-BRIDGE-BRANCH' and r.get('expected_branch')]
    bad_rid = [r['num'] for r in ok_protos if not r.get('rid_match')]
    bad_spec = [r['num'] for r in ok_protos if r.get('spec') != 'PASS']

    print('\n[5] 汇总')
    chk(len(ok_protos) == len(expect),
        '应该有分支的 %d 个协议全部渲染出响应' % len(expect),
        '只有 %d 个；缺 %r' % (len(ok_protos), missing_branch) if missing_branch else '')
    chk(not bad_spec, '已接分支的协议 spec_check 全 PASS',
        'FAIL: %r' % bad_spec if bad_spec else '%d 个' % len(ok_protos))
    chk(not bad_rid, '已接分支的协议 outer requestid == inner RequestId',
        'MISMATCH: %r' % bad_rid if bad_rid else '%d 个' % len(ok_protos))
    if nob:
        print('  %-56s %s %r' % ('bridge 里**没有**分支（只有生成器，需另写补丁）', 'KNOWN', nob))
    patha = [r['num'] for r in ok_protos if r.get('reach') == 'path-A']
    if patha:
        print('  %-56s %s %r' % ('这些协议线上必须靠 cn_preempt 放行，否则分支是死代码', 'INFO', patha))
    direct = [r['num'] for r in ok_protos if r.get('reach') == 'L1088']
    if direct:
        print('  %-56s %s %r' % ('这些协议 name 解析不到，天然走 L1088，与 cn_preempt 无关',
                                 'INFO', direct))
    print('\n  应用状态: %s' % (', '.join(applied) if applied else '（未应用任何补丁）'))
    print('  开关 cn_preempt: %s'
          % _switch_value(c.preempt_switch))
    if not c.sandbox:
        print('  !! 这是线上文件。改完记得重启 bridge，并看 logs/api_all_requests.log 里'
              " rec['preempt'] / rec['gen_kind']")

    # ---------- report
    report['ok'] = all_ok
    report['elapsed_s'] = round(time.time() - t0, 2)
    try:
        if not os.path.isdir(REPORT_DIR):
            os.makedirs(REPORT_DIR)
        write_text(os.path.join(REPORT_DIR, 'deploy_verify_%s.json' % report['ts']),
                   json.dumps(report, ensure_ascii=False, indent=1))
        write_text(os.path.join(REPORT_DIR, 'deploy_verify.json'),
                   json.dumps(report, ensure_ascii=False, indent=1))
        print('\n  report: %s' % os.path.join(REPORT_DIR, 'deploy_verify.json'))
    except Exception as e:
        print('\n  !! report 写不出去: %r' % (e,))

    print(rule('='))
    print('结果: %s   （%.2fs）' % ('PASS' if all_ok else 'FAIL', report['elapsed_s']))
    return 0 if all_ok else 1


def _switch_value(path):
    try:
        v = open(path).read().strip()
        return '%r (%s)' % (v, path)
    except Exception:
        return '(缺失) = off  %s' % path


# ================================================================ --dry-run
def cmd_dry_run(a, ctx=None):
    c = ctx or resolve_ctx(a)
    print(rule('='))
    print('DRY-RUN：在副本上真跑一遍，正式文件一个字节都不动')
    print('  source : %s' % c.target)
    if os.path.isdir(SCRATCH_DIR):
        shutil.rmtree(SCRATCH_DIR, ignore_errors=True)
    os.makedirs(SCRATCH_DIR)
    tmp = os.path.join(SCRATCH_DIR, 'account_auth_probe.py')
    shutil.copy2(c.target, tmp)
    c_tmp = Ctx()
    c_tmp.__dict__.update(c.__dict__)
    c_tmp.target = tmp
    c_tmp.dir = SCRATCH_DIR
    c_tmp.preempt_switch = os.path.join(SCRATCH_DIR, 'cn_preempt.txt')

    # cn_wire 侧也一起演练（真文件就复制一份，没有就用替身）
    cn_dry = None
    if c.cn_wire_mode == 'live':
        cn_dry = os.path.join(SCRATCH_DIR, 'cn_wire.py')
        shutil.copy2(c.cn_wire, cn_dry)
        c_tmp.cn_wire = cn_dry
        c_tmp.cn_wire_mode = 'live'
    else:
        cn_dry = os.path.join(SCRATCH_DIR, 'cn_wire.py')
        make_cn_wire_fixture(cn_dry)
        c_tmp.cn_wire = cn_dry
        c_tmp.cn_wire_mode = 'fixture'
    print('  scratch: %s' % SCRATCH_DIR)
    print(rule('='))

    print('\n[预检] 目标身份')
    ok, _ = preflight(c, quiet=False)
    if not ok:
        print('预检没过 —— 后面每一步都不可信，先修预检。')

    prev = read_text(tmp)
    ok_all = True
    for i, st in enumerate(STEPS, 1):
        path = c_tmp.cn_wire if st['arg_key'] == 'cn_wire' else c_tmp.target
        print('\n[第 %d 步] %s' % (i, st['key']))
        print('  脚本 : %s' % st['script'])
        print('  改   : %s  %s' % (os.path.basename(path), st['why']))
        if c_tmp.cn_wire_mode != 'live' and st['arg_key'] == 'cn_wire':
            print('  说明 : 用的是 cn_wire 替身（线上文件不可用），只证明锚点与变换成立')
        before = read_text(path)
        note = baseline_guard_override(st, c_tmp)
        if note:
            print('  守卫 : %s' % note)
        script, args = step_args(st, c_tmp, 'apply')
        rc, out = run_py(script, args)
        after = read_text(path)
        print('  exit : %d   %+d bytes' % (rc, len(after.encode()) - len(before.encode())))
        if rc != 0:
            ok_all = False
            print('  !! 这一步失败，后面的步骤不可信。输出尾巴：')
            print('  ' + tail(out, 10).replace('\n', '\n  '))
            break
        # marker
        okm, rows = verify_markers(st, path)
        print('  marker: %s' % ('PASS' if okm else 'FAIL'))
        if not okm:
            ok_all = False
        # 之前的 marker 没被破坏
        okp, bad = check_previous(c_tmp, i)
        print('  之前补丁完好: %s %s' % ('PASS' if okp else 'FAIL', bad or ''))
        ok_all = ok_all and okp
        # diff 预览
        d = list(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                      fromfile='before', tofile='after', n=2))
        addn = sum(1 for x in d if x.startswith('+') and not x.startswith('+++'))
        deln = sum(1 for x in d if x.startswith('-') and not x.startswith('---'))
        print('  diff : +%d / -%d 行（下面只显示前 16 行）' % (addn, deln))
        for x in d[:16]:
            print('    ' + x.rstrip('\n'))
        if len(d) > 16:
            print('    ... 还有 %d 行' % (len(d) - 16))
        # py_compile
        okc, why = py_compile_ok(c_tmp.target)
        print('  py_compile: %s %s' % ('PASS' if okc else 'FAIL', why))
        ok_all = ok_all and okc
        if not okc:
            break

    print('\n' + rule('='))
    if os.path.exists(c_tmp.target):
        print('抄完一遍: %d B -> %d B   sha256=%s'
              % (os.path.getsize(c.target), os.path.getsize(c_tmp.target),
                 sha256_file(c_tmp.target)[:16]))
    print('DRY-RUN 结果: %s' % ('全步骤可应用' if ok_all else '有步骤失败（见上）'))
    print('副本保留在 %s（要清理就删这个目录）' % SCRATCH_DIR)
    print('确认无误后用 --apply 正式打。')
    return 0 if ok_all else 1


# ================================================================ --apply
def manifest_path(c):
    return os.path.join(c.dir, 'account_auth_probe.py.bapatch_deploy.json')


def cmd_apply(a, ctx=None):
    c = ctx or resolve_ctx(a)
    print(rule('='))
    print('APPLY  target=%s' % c.target)
    print('  sandbox=%s  cn_wire=%s(%s)' % (c.sandbox, c.cn_wire, c.cn_wire_mode))
    print(rule('='))
    print('\n[预检]')
    ok, _ = preflight(c, quiet=False)
    if not ok:
        print('\n[apply] !! 预检没过，拒绝改文件。')
        return 3

    # 现状：已经打过哪些
    before_text = read_text(c.target)
    before_sha = sha256_text(before_text)
    done = []
    for st in STEPS:
        path = c.cn_wire if st['arg_key'] == 'cn_wire' else c.target
        if step_skip_reason(st, c):
            continue
        okm, _ = verify_markers(st, path)
        if okm:
            done.append(st['key'])
    if done:
        print('\n[apply] 这些补丁已经在目标上了: %s' % done)
        print('        幂等：会跳过；要重来请先 --rollback。')

    # 原始件（一次性回滚的兜底）+ manifest
    ts = stamp()
    orig = os.path.join(c.dir, 'account_auth_probe.py.bapatch_orig.%s' % ts)
    man = {
        'ts': ts, 'target': c.target, 'cn_wire': c.cn_wire,
        'cn_wire_mode': c.cn_wire_mode, 'sandbox': c.sandbox,
        'sha256_original': before_sha, 'original_copy': orig,
        'base_sha': c.base_sha, 'steps': [], 'order': [s['key'] for s in STEPS],
    }
    if not os.path.exists(orig):
        shutil.copy2(c.target, orig)
        print('[apply] 原始件备份: %s' % orig)

    print('\n[执行]')
    failed_at = None
    for i, st in enumerate(STEPS, 1):
        path = c.cn_wire if st['arg_key'] == 'cn_wire' else c.target
        skip = step_skip_reason(st, c)
        if skip:
            print('\n[%d/%d] %-8s SKIP  %s' % (i, len(STEPS), st['key'], skip))
            man['steps'].append({'key': st['key'], 'status': 'skip', 'why': skip})
            continue
        okm, _ = verify_markers(st, path)
        if okm:
            print('\n[%d/%d] %-8s 已应用，跳过（幂等）' % (i, len(STEPS), st['key']))
            man['steps'].append({'key': st['key'], 'status': 'already'})
            continue
        print('\n[%d/%d] %-8s %s' % (i, len(STEPS), st['key'], st['why']))
        note = baseline_guard_override(st, c)
        if note:
            print('    !! 基线守卫: %s' % note)
        h_before = sha256_file(path)
        script, args = step_args(st, c, 'apply')
        rc, out = run_py(script, args)
        print('    exit=%d  %s' % (rc, tail(out, 3).replace('\n', ' | ')))
        if rc != 0:
            print('[apply] !! 第 %d 步（%s）失败。完整输出：\n%s' % (i, st['key'], out))
            man['steps'].append({'key': st['key'], 'status': 'failed', 'rc': rc})
            failed_at = st['key']
            break
        okm2, rows = verify_markers(st, path)
        if not okm2:
            print('[apply] !! %s 的 marker 不对: %r' % (st['key'], rows))
            man['steps'].append({'key': st['key'], 'status': 'marker-fail'})
            failed_at = st['key']
            break
        okp, bad = check_previous(c, i)
        print('    marker PASS   之前补丁完好: %s %s' % ('PASS' if okp else 'FAIL', bad or ''))
        if not okp:
            print('[apply] !! %s 覆盖了之前的补丁: %r' % (st['key'], bad))
            man['steps'].append({'key': st['key'], 'status': 'clobbered', 'broke': bad})
            failed_at = st['key']
            break
        okc, why = py_compile_ok(path)
        print('    py_compile: %s %s' % ('PASS' if okc else 'FAIL', why))
        if not okc:
            man['steps'].append({'key': st['key'], 'status': 'compile-fail', 'why': why})
            failed_at = st['key']
            break
        man['steps'].append({'key': st['key'], 'status': 'applied',
                             'sha_before': h_before, 'sha_after': sha256_file(path)})

    man['sha256_after'] = sha256_file(c.target)
    write_text(manifest_path(c), json.dumps(man, ensure_ascii=False, indent=1))

    # 拦截开关：默认不动（off）。要开必须显式 --switch。
    if a.switch is not None:
        rc, out = run_py('patch_preempt.py',
                         ['--target', c.target, '--switch-file', c.preempt_switch,
                          '--switch', a.switch])
        print('\n[apply] 拦截开关 -> %r  %s' % (a.switch, tail(out, 2).replace('\n', ' ')))
    else:
        print('\n[apply] 拦截开关保持现状（%s）。'
              '默认 off = 今天的线上行为；等其它补丁验证完再 --switch all 或 --switch 协议号。'
              % _switch_value(c.preempt_switch))

    if failed_at:
        print('\n' + rule('='))
        print('[apply] 失败于: %s' % failed_at)
        print('        已完成的步骤见 %s' % manifest_path(c))
        print('        立刻回退： python %s --rollback' % os.path.relpath(__file__, os.getcwd())
              if os.path.exists(__file__) else '        立刻回退： --rollback')
        print(rule('='))
        return 4

    print('\n[收尾] 全量验证')
    rc = cmd_verify(a, ctx=c)
    print(rule('='))
    print('[apply] 完成。target=%s  sha256=%s' % (c.target, man['sha256_after']))
    if c.sandbox:
        print('[apply] 这是沙箱。上机时用 --target /www/wwwroot/bapatch/tools/account_auth_probe.py '
              '--cn-wire /www/wwwroot/bapatch/tools/cn_wire.py --apply')
    else:
        print('[apply] 线上文件已改。**需要重启 bridge 才生效**：')
        print('        pkill -f account_auth_probe.py ; '
              'nohup python3 /www/wwwroot/bapatch/tools/account_auth_probe.py >> '
              '/www/wwwroot/bapatch/logs/bridge.out 2>&1 &')
    print(rule('='))
    return 0 if rc == 0 else 5


# ================================================================ --rollback
def cmd_rollback(a, ctx=None):
    c = ctx or resolve_ctx(a)
    print(rule('='))
    print('ROLLBACK  target=%s' % c.target)
    print(rule('='))
    if not os.path.exists(c.target):
        die('目标不存在: %s' % c.target)
    man = None
    try:
        man = json.loads(read_text(manifest_path(c)))
    except Exception:
        man = None
    orig_sha = (man or {}).get('sha256_original')
    orig_copy = (man or {}).get('original_copy')

    cur_sha = sha256_file(c.target)
    print('当前 sha256 : %s' % cur_sha)
    if orig_sha:
        print('原始 sha256 : %s' % orig_sha)
        print('原始件副本  : %s%s' % (orig_copy, '' if os.path.exists(orig_copy or '') else '  (缺失)'))

    # 逆序逐个摘
    for st in reversed(STEPS):
        path = c.cn_wire if st['arg_key'] == 'cn_wire' else c.target
        if c.cn_wire_mode == 'off' or (st['arg_key'] == 'cn_wire'
                                       and not os.path.exists(c.cn_wire)):
            print('\n[rollback] %-8s SKIP（cn_wire 不可用）' % st['key'])
            continue
        okm, _ = verify_markers(st, path)
        if not okm:
            print('\n[rollback] %-8s 不在（跳过）' % st['key'])
            continue
        print('\n[rollback] %-8s %s' % (st['key'], st['script']))
        script, args = step_args(st, c, 'rollback')
        rc, out = run_py(script, args)
        print('    exit=%d  %s' % (rc, tail(out, 3).replace('\n', ' | ')))
        if rc != 0:
            print('[rollback] !! %s 的 --rollback 失败，后面交给兜底。输出：\n%s'
                  % (st['key'], tail(out, 20)))

    now_sha = sha256_file(c.target)
    print('\n' + rule('-'))
    print('回滚后 sha256 : %s' % now_sha)
    if orig_sha and now_sha == orig_sha:
        print('结果: PASS  —— 逐字节回到 --apply 之前的状态。')
        return 0
    # 兜底：直接用原始件覆盖
    if orig_copy and os.path.exists(orig_copy):
        shutil.copy2(orig_copy, c.target)
        fixed = sha256_file(c.target)
        print('兜底: 用原始件覆盖 %s' % orig_copy)
        print('回滚后 sha256 : %s' % fixed)
        if orig_sha and fixed == orig_sha:
            print('结果: PASS（兜底还原，逐字节一致）')
            return 0
        print('结果: FAIL —— 兜底后 sha256 仍不等于原始值，请人工介入。')
        return 1
    print('结果: %s —— 没有原始件可比对；请 --status 人工确认。'
          % ('PASS（无 manifest，无法比 sha）' if not orig_sha else 'FAIL'))
    return 0


# ================================================================ --status
def cmd_status(a, ctx=None):
    c = ctx or resolve_ctx(a)
    print(rule('='))
    print('STATUS  target=%s%s' % (c.target, '' if os.path.exists(c.target) else '   (不存在)'))
    print('        sandbox=%s   cn_wire=%s(%s)' % (c.sandbox, c.cn_wire, c.cn_wire_mode))
    print(rule('='))
    if not os.path.exists(c.target):
        print('目标文件不存在，无从判断。')
        return 2
    text = read_text(c.target)
    print('size   : %d B / %d 行' % (os.path.getsize(c.target), count_lines(text)))
    print('sha256 : %s' % sha256_file(c.target))
    print('\n各补丁状态:')
    print('  %-9s %-26s %-9s %s' % ('step', 'script', 'status', 'marker'))
    applied = 0
    for st in STEPS:
        path = c.cn_wire if st['arg_key'] == 'cn_wire' else c.target
        skip = step_skip_reason(st, c)
        if skip:
            print('  %-9s %-26s %-9s %s' % (st['key'], st['script'], 'SKIP', skip[:60]))
            continue
        ok, rows = verify_markers(st, path)
        if ok:
            applied += 1
        det = ' '.join('%d/%d' % (g, w) for _, w, g, _ in rows)
        print('  %-9s %-26s %-9s %s' % (st['key'], st['script'],
                                        'APPLIED' if ok else 'not-applied', det))
    print('\n已应用 %d/%d 步' % (applied, len([s for s in STEPS if not step_skip_reason(s, c)])))
    print('拦截开关 cn_preempt: %s' % _switch_value(c.preempt_switch))

    # 24000 v3 探测
    v3 = os.path.join(HERE, 'patch_24000_v3.py')
    cur, _b, _e = resolve_24000()
    print('\npatch_24000_v3.py: %s' % ('存在' if os.path.exists(v3) else '不存在'))
    print('当前 24000 补丁  : %s（--24000-script 可显式指定）' % cur)

    man = None
    try:
        man = json.loads(read_text(manifest_path(c)))
    except Exception:
        pass
    if man:
        print('\nmanifest: %s' % manifest_path(c))
        print('  原始 sha256: %s' % man.get('sha256_original'))
        print('  当前 sha256: %s' % sha256_file(c.target))
        for s in man.get('steps', []):
            print('  %-9s %s' % (s.get('key'), s.get('status')))
        if man.get('sha256_original') == sha256_file(c.target):
            print('  => 目标处于「未部署」状态（与原始 sha 一致）')
    else:
        print('\n没有 manifest（%s）—— 可能是手工部署或还没 --apply。' % manifest_path(c))
    print(rule('='))
    return 0


# ================================================================ main
def main(argv=None):
    ap = argparse.ArgumentParser(
        description='BA 国服私服 bridge 补丁统一部署器（6+1 步）',
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--target', default=LIVE_TARGET, help='account_auth_probe.py')
    ap.add_argument('--cn-wire', default=LIVE_CN_WIRE, help='cn_wire.py（patch_requestid 的目标）')
    ap.add_argument('--base', default=BASE_PATH, help='54,026 B 基线（只读）')
    ap.add_argument('--switch-file', default=None,
                    help='cn_preempt.txt 路径（默认线上 /www/wwwroot/bapatch/cn_preempt.txt；'
                         '沙箱默认 <沙箱目录>/cn_preempt.txt）')
    ap.add_argument('--sandbox', action='store_true', help='强制在 deploy/_sandbox/deploy_all 里演练')
    ap.add_argument('--seed', action='store_true', help='先把 _baseline 复制进沙箱（覆盖）')
    ap.add_argument('--no-cn-wire', action='store_true', help='完全跳过 cn_wire 那一步')
    ap.add_argument('--24000-script', dest='s24000_script', default=None,
                    help='24000 补丁脚本（默认 patch_24000_v3.py；不存在则 patch_24000_v2.py）')
    ap.add_argument('--switch', default=None,
                    help="apply 完之后把 cn_preempt.txt 写成这个值（off/all/all+/协议号表）；"
                         "不写就保持现状")
    g = ap.add_mutually_exclusive_group()
    g.add_argument('--apply', action='store_true', help='按顺序应用全部补丁（含逐步自检 + 收尾 verify）')
    g.add_argument('--verify', action='store_true', help='全量验证')
    g.add_argument('--rollback', action='store_true', help='逆序一次性回滚全部')
    g.add_argument('--status', action='store_true', help='显示每个补丁的应用状态')
    ap.add_argument('--dry-run', action='store_true', help='在副本上真跑一遍并给每步 diff 预览')
    ap.add_argument('--pristine', action='store_true', help='允许写 _baseline/（默认拒绝）')
    a = ap.parse_args(argv)

    if not a.pristine and '_baseline' in os.path.abspath(a.target).replace('\\', '/'):
        die('拒绝把 _baseline/ 当目标（那是只读基线）：%s' % a.target)

    # 24000 补丁版本 + 它的托管块标记（v2/v3 不同）在这里定下来
    resolve_24000(a.s24000_script)

    if a.dry_run:
        return cmd_dry_run(a)
    if a.verify:
        return cmd_verify(a)
    if a.rollback:
        return cmd_rollback(a)
    if a.status:
        return cmd_status(a)
    if a.apply:
        return cmd_apply(a)
    return cmd_status(a)


if __name__ == '__main__':
    sys.exit(main())
