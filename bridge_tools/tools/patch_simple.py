#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patch_simple.py -- 把 1005 / 4000 / 26000 三个分支挂进 bridge 的协议分发处。

三个补丁单元，各有独立标记，--rollback 逐个摘掉，互不影响：

  PAYLOAD  把 deploy/simple_payload.py **逐字节原样**插到 bridge 的 `if __name__ == '__main__':`
           之前。它是三件套的唯一真源，bridge 里不再抄第二份；--verify 会比对 sha256，
           一旦有人只改了 deploy 那一份、没重新 apply，立刻报「内嵌副本 != 真源」。

  HOOK-D   bridge 的 path D（`if proto_int:` 之前）。这条路在 exp=decrypt+* 且拿到
           req_Hash 时会把 1005/4000/26000 回成 `{"Protocol":N}` 单键
           （cn_nick.build_min_response），必须在这儿先接管。

  HOOK-G   _generic_protocol_response() 里，`if num == 90004:` 之前。
           这就是现在的 `min+base` 兜底（7 个假键：MissionProgressDBs / StaticOpenConditions ...）。

两个 hook 都包在 try/except 里：本补丁自身出任何异常都只写 rec['simple_err']，然后原路返回，
不可能把别的协议带崩。

三个协议的运行时开关（bridge 目录下，内容 1=开 0=关，缺失=关）：
    cn_1005.txt  cn_4000.txt  cn_26000.txt
另有两个可选文件（不建就走默认）：
    cn_simple_account.txt   账号号（SESSION.account_id 拿不到时的兜底，1 行数字）
    cn_simple_ticks.txt     'utc'（默认，与官方实测一致）或 'local'

用法（默认 --bridge /www/wwwroot/bapatch/tools/account_auth_probe.py）：
    python deploy/patch_simple.py --dry-run                 只看 diff，不写
    python deploy/patch_simple.py --apply                   打补丁（自动备份 + 语法检查）
    python deploy/patch_simple.py --apply --switches 1      打补丁并把三个开关写成 1
    python deploy/patch_simple.py --verify                  自检（结构 + 真源一致 + 行为等价）
    python deploy/patch_simple.py --rollback                摘掉三块（幂等）
    python deploy/patch_simple.py --rollback --restore F    直接用备份 F 覆盖
本地演练（不碰 _bridge_ref）：
    mkdir deploy\\_sandbox & copy work\\ba\\server\\_bridge_ref\\account_auth_probe.py deploy\\_sandbox\\
    python deploy/patch_simple.py --apply --bridge deploy\\_sandbox\\account_auth_probe.py --switches 1
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
import sys
import tempfile
import time

sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
PROTO_DIR = os.path.join(ROOT, 'work', 'ba', 'proto')
PAYLOAD_PATH = os.path.join(HERE, 'simple_payload.py')
SPEC_PATH = os.path.join(PROTO_DIR, 'official_spec.json')
SPECGEN_PATH = os.path.join(ROOT, 'work', 'ba', 'server', 'prototype', 'specgen.py')

DEFAULT_BRIDGE = '/www/wwwroot/bapatch/tools/account_auth_probe.py'

VER = 'v1'

# ---- 三个插入锚点（在 bridge 里各自唯一；不唯一就拒绝动文件）
ANCHOR_PAYLOAD = "if __name__ == '__main__':\n"
ANCHOR_HOOK_D = "        if proto_int:\n            obj = cn_nick.build_min_response(proto_int)\n"
ANCHOR_HOOK_G = "        if num == 90004:\n"
ANCHORS = {'PAYLOAD': ANCHOR_PAYLOAD, 'HOOK-D': ANCHOR_HOOK_D, 'HOOK-G': ANCHOR_HOOK_G}

UNIT_PAYLOAD = 'PAYLOAD'
UNIT_HOOK_D = 'HOOK-D'
UNIT_HOOK_G = 'HOOK-G'
UNITS = (UNIT_PAYLOAD, UNIT_HOOK_D, UNIT_HOOK_G)

SWITCH_FILES = {1005: 'cn_1005.txt', 4000: 'cn_4000.txt', 26000: 'cn_26000.txt'}

HOOK_D_BODY = """        # >>> BAPATCH-SIMPLE-HOOK-D %(ver)s BEGIN >>>
        # 1005 / 4000 / 26000: path D 会把它们回成 {"Protocol":N} 单键，先在这里接管
        try:
            if simple_wants(proto_int):
                _sg = self._generic_protocol_response(proto_str, packet_b64, rec, name=name)
                if _sg is not None:
                    return _sg
        except Exception as _sg_err:
            rec['simple_err'] = 'HOOK-D ' + repr(_sg_err)
        # <<< BAPATCH-SIMPLE-HOOK-D %(ver)s END <<<
"""

HOOK_G_BODY = """        # >>> BAPATCH-SIMPLE-HOOK-G %(ver)s BEGIN >>>
        # 1005 / 4000 / 26000: 官方结构（spec 驱动），替代下面 min+base 的 7 个假键
        # frag 用 locals().get() 取：线上 bridge 与本仓库副本不是同一版（45,470 vs 46,568 B），
        # 万一那版里这个局部变量不叫 frag，也不至于 NameError（最坏只是不回显 MxToken）。
        try:
            _sg = simple_route(rec, name, num, locals().get('frag'), cn_wire.wrap_response)
            if _sg is not None:
                return _sg
        except Exception as _sg_err:
            rec['simple_err'] = 'HOOK-G ' + repr(_sg_err)
        # <<< BAPATCH-SIMPLE-HOOK-G %(ver)s END <<<
"""


# ================================================================ 文本工具
def sha256_text(s):
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


def read_text(path):
    with io.open(path, 'r', encoding='utf-8', newline='') as fh:
        return fh.read()


def write_text(path, text):
    with io.open(path, 'w', encoding='utf-8', newline='') as fh:
        fh.write(text)


def mark_begin(unit):
    return '# >>> BAPATCH-SIMPLE-%s %s BEGIN' % (unit, VER)


def mark_end(unit):
    return '# <<< BAPATCH-SIMPLE-%s %s END <<<' % (unit, VER)


def payload_body():
    src = read_text(PAYLOAD_PATH).replace('\r\n', '\n').rstrip('\n')
    return src + '\n'


def unit_block(unit, body=None):
    """整块文本。PAYLOAD 的标记顶格；两个 HOOK 的标记按函数体缩进（lstrip 匹配）。"""
    if unit == UNIT_PAYLOAD:
        body = payload_body() if body is None else body
        head = ('%s >>> (deploy/simple_payload.py verbatim, sha256=%s) >>>'
                % (mark_begin(UNIT_PAYLOAD), sha256_text(body)))
        return head + '\n' + body + mark_end(UNIT_PAYLOAD) + '\n'
    # HOOK_*_BODY 的第一行就是 BEGIN，最后一行就是 END，不再额外加
    body = (HOOK_D_BODY if unit == UNIT_HOOK_D else HOOK_G_BODY) % {'ver': VER}
    return body


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


def anchor_pos(text, anchor, unit):
    n = text.count(anchor)
    if n != 1:
        raise SystemExit('补丁锚点不唯一：[%s] 出现 %d 次（%r）—— 拒绝动这个文件'
                         % (unit, n, anchor.strip().split('\n')[0][:70]))
    return text.index(anchor)


def compile_ok(text, path):
    try:
        compile(text, path, 'exec')
        return True, ''
    except SyntaxError as e:
        return False, '%s line %s: %s' % (type(e).__name__, e.lineno, e.msg)


def mask_payload(text):
    """给 diff 用：把 PAYLOAD 正文压成一行占位，避免 400 行噪声。"""
    rng = find_block(text, UNIT_PAYLOAD)
    if not rng:
        return text
    lines = text.split('\n')
    n = rng[1] - rng[0] - 1
    placeholder = '# ...[%d 行 payload 原样内嵌自 deploy/simple_payload.py，--full-diff 查看]...' % n
    return '\n'.join(lines[:rng[0] + 1] + [placeholder] + lines[rng[1]:])


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
        i = anchor_pos(text, ANCHORS[unit], unit)
        text = text[:i] + blk + text[i:]
        acts.append('%s: 在 %r 之前插入 %d 行' % (unit, ANCHORS[unit].strip().split('\n')[0][:56], nlines))
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
        acts.append('%s: 摘掉 %d 行' % (unit, rng[1] - rng[0] + 1))
    return text, acts


def backup(bridge):
    bak = '%s.simple.bak.%s' % (bridge, time.strftime('%Y%m%d-%H%M%S'))
    shutil.copy2(bridge, bak)
    return bak


# ================================================================ 开关文件
def bridge_dir(bridge):
    return os.path.dirname(os.path.abspath(bridge))


def switch_path(bridge, proto):
    return os.path.join(bridge_dir(bridge), SWITCH_FILES[proto])


def apply_switches(bridge, val):
    out = []
    for proto in sorted(SWITCH_FILES):
        p = switch_path(bridge, proto)
        exists = os.path.exists(p)
        if val == 'keep':
            if exists:
                with io.open(p, 'r') as fh:
                    out.append('%s=%r(保留)' % (SWITCH_FILES[proto], fh.read().strip()))
                continue
            want = '1'
        else:
            want = val
        with io.open(p, 'w', newline='\n') as fh:
            fh.write(want + '\n')
        out.append('%s=%s(%s)' % (SWITCH_FILES[proto], want, '保留文件' if exists else '新建'))
    return out


def report_switches(bridge, ns):
    out = []
    for proto in sorted(SWITCH_FILES):
        p = switch_path(bridge, proto)
        state = 'MISSING'
        if os.path.exists(p):
            with io.open(p, 'r') as fh:
                state = repr(fh.read().strip())
        on = ns['simple_switch_on'](proto, bridge_dir(bridge))
        out.append((proto, os.path.basename(p), state, on))
    return out


# ================================================================ 自检
class _FakeSession(object):
    account_id = 10015354380


def fake_send(name, obj, rid):
    """替身 cn_wire.wrap_response：同样的 plaintext 组装，但不加密。"""
    packet = json.dumps(obj, ensure_ascii=False, separators=(',', ':'))
    plain = json.dumps({'protocol': name, 'packet': packet, 'requestid': rid},
                       ensure_ascii=False, separators=(',', ':'))
    return ('WIRE<' + plain + '>', plain, b'K' * 32)


def load_embedded_ns(bridge_text):
    body = extract_block_body(bridge_text, UNIT_PAYLOAD)
    if body is None:
        return None, '内嵌 PAYLOAD 块不存在'
    ns = {'__name__': 'embedded_simple_payload',
          '__file__': os.path.join(HERE, 'simple_payload.py')}
    try:
        exec(compile(body, '<embedded simple_payload>', 'exec'), ns)
    except Exception as e:
        return None, '内嵌 PAYLOAD 无法 exec: %r' % (e,)
    return ns, ''


def verify(bridge, want_sha=None, verbose=True):
    rep = []
    state = {'ok': True}

    def add(good, text):
        state['ok'] = state['ok'] and bool(good)
        rep.append(('PASS  ' if good else 'FAIL  ') + text)

    if not os.path.isfile(bridge):
        return False, ['FAIL  bridge 不存在: %s' % bridge]
    text = read_text(bridge)

    ok, err = compile_ok(text, bridge)
    add(ok, 'python 语法检查 compile() %s' % ('' if ok else '-> ' + err))

    # ---- 1. 三个标记成对
    for unit in UNITS:
        b, e = count_marks(text, unit)
        add(b == 1 and e == 1 and find_block(text, unit) is not None,
            '%s 标记成对、各 1 处（BEGIN %d / END %d）' % (unit, b, e))

    # ---- 2. PAYLOAD == 真源（逐字节）
    body = extract_block_body(text, UNIT_PAYLOAD)
    src_body = payload_body()
    add(body == src_body,
        'PAYLOAD 内嵌副本 == deploy/simple_payload.py 逐字节（sha256 %s / %s）'
        % ((sha256_text(body)[:16] if body else '-'), sha256_text(src_body)[:16]))
    head_line = ''
    for ln in text.split('\n'):
        if ln.lstrip().startswith(mark_begin(UNIT_PAYLOAD)):
            head_line = ln
            break
    m = re.search(r'sha256=([0-9a-f]{64})', head_line)
    add(bool(m) and (want_sha is None or m.group(1) == want_sha),
        'PAYLOAD 标记里记的 sha256 与真源一致（%s）' % (m.group(1)[:16] if m else '缺'))

    # ---- 3. 位置
    g_def = text.find('def _generic_protocol_response')
    g_next = text.find('def _cn_send_envelope')
    gi = text.find(mark_begin(UNIT_HOOK_G))
    add(g_def >= 0 and g_next > g_def and g_def < gi < g_next,
        'HOOK-G 落在 _generic_protocol_response() 内（def@%d < hook@%d < 下一函数@%d）'
        % (g_def, gi, g_next))
    di = text.find(mark_begin(UNIT_HOOK_D))
    d_anchor = text.find('        if proto_int:')
    g_anchor = text.find('        if num == 90004:')
    add(0 <= di < d_anchor, 'HOOK-D 落在 path D 的 `if proto_int:` 之前（hook@%d < anchor@%d）'
        % (di, d_anchor))
    add(0 < g_anchor and gi < g_anchor, 'HOOK-G 落在 `if num == 90004:` 之前')
    payload_anchor = text.find(ANCHOR_PAYLOAD)
    pi = text.find(mark_begin(UNIT_PAYLOAD))
    add(0 < pi < payload_anchor, 'PAYLOAD 落在 `if __name__ == \'__main__\':` 之前')

    # ---- 4. 行为：exec 内嵌块
    ns, nerr = load_embedded_ns(text)
    add(ns is not None, '内嵌 PAYLOAD 可 exec%s' % ('' if ns else ' -> ' + nerr))

    if ns:
        tmp = tempfile.mkdtemp(prefix='bapatch_sw_')
        try:
            add(ns['simple_switch_on'](1005, tmp) is False,
                '开关文件缺失 -> 判定「关」（fail-safe，不会意外接管）')
            for fn in SWITCH_FILES.values():
                with io.open(os.path.join(tmp, fn), 'w', newline='\n') as fh:
                    fh.write('1\n')
            add(all(ns['simple_switch_on'](p, tmp) for p in SWITCH_FILES), '三个开关=1 -> 全部「开」')
            with io.open(os.path.join(tmp, SWITCH_FILES[4000]), 'w', newline='\n') as fh:
                fh.write('0\n')
            add(ns['simple_switch_on'](4000, tmp) is False and ns['simple_switch_on'](1005, tmp) is True,
                '只关 cn_4000.txt -> 1005 仍开、4000 关（三个开关互相独立）')
            for fn in SWITCH_FILES.values():
                with io.open(os.path.join(tmp, fn), 'w', newline='\n') as fh:
                    fh.write('1\n')

            for proto in (1005, 4000, 26000):
                rec = {'req_Hash': (proto << 32) | 7}
                got = ns['simple_route'](rec, None, proto, '', fake_send, tmp)
                if got is None:
                    add(False, 'simple_route(%d) 返回 None（应接管）' % proto)
                    continue
                code, wire, ctype = got
                outer = json.loads(wire[5:-1])
                inner = json.loads(outer['packet'])
                name_ok = outer['protocol'] == ns['SIMPLE_NAMES'][proto]
                rid_ok = bool(inner.get('RequestId')) and inner['RequestId'] == outer['requestid']
                keys_ok = len(inner) == {1005: 6, 4000: 7, 26000: 8}[proto]
                add(code == 200 and name_ok and rid_ok and keys_ok,
                    'simple_route(%d): 200 / 外层 protocol=%s / inner.RequestId==外层 requestid=%s / 顶层 %d 键'
                    % (proto, outer['protocol'], rid_ok, len(inner)))
                if proto == 1005:
                    add(inner.get('TutorialIds') == [], '1005 TutorialIds == []（新号进度为空）')
                elif proto == 4000:
                    rows = inner.get('ItemDBs') or []
                    row = rows[0] if rows else {}
                    add(len(rows) == 1 and row.get('Type') == 4 and row.get('UniqueId') == 2
                        and row.get('StackCount') == 5 and len(row) == 5,
                        '4000 ItemDBs = 1 行加速券（Type=4 / UniqueId=2 / StackCount=5 / 5 键，非空）')
                else:
                    add(inner.get('HasValidData') is False and inner.get('ContentSaveDB') is None
                        and inner.get('EventContentChangeDB') is None,
                        '26000 HasValidData=false + ContentSaveDB/EventContentChangeDB 均为 null')

            for fn in SWITCH_FILES.values():
                with io.open(os.path.join(tmp, fn), 'w', newline='\n') as fh:
                    fh.write('0\n')
            add(all(ns['simple_route']({'req_Hash': (p << 32)}, None, p, '', fake_send, tmp) is None
                    for p in (1005, 4000, 26000)),
                '三个开关全关 -> 全部返回 None（交回原有兜底，行为完全回到打补丁前）')

            # ---- 不抢别的协议（8000 / 90004 / 24000 即使开关全开也必须返回 None）
            for fn in SWITCH_FILES.values():
                with io.open(os.path.join(tmp, fn), 'w', newline='\n') as fh:
                    fh.write('1\n')
            add(all(ns['simple_route']({'req_Hash': (p << 32)}, None, p, '', fake_send, tmp) is None
                    for p in (3, 8000, 90004, 24000, 1017)),
                '开关全开也不会接管别的协议（3 / 8000 / 90004 / 24000 / 1017 -> None）')

            # ---- 请求片段回显：AccountServerId / MxToken 取自客户端请求
            tok = 'Vji5A/Cy2X2enQZKeYgrjxAC8MoRDOCT2Tb1SW13PcZTq2cnyCPPdd81pGbzYBKA'
            frag = (',"SessionKey":{"AccountServerId":10015354380,"MxToken":"%s"},'
                    '"Hash":4316446606771,"IsTest":false}' % tok)
            rec = {'req_frag_head': frag[:600]}
            got = ns['simple_route'](rec, 'Account_GetTutorial', 1005, frag, fake_send, tmp)
            inner = json.loads(json.loads(got[1][5:-1])['packet']) if got else {}
            add(inner.get('SessionKey', {}).get('MxToken') == tok
                and inner.get('SessionKey', {}).get('AccountServerId') == 10015354380,
                '1005 回显客户端 MxToken/AccountServerId（官方行为），且 gen_kind=%r' % rec.get('gen_kind'))

            # ---- 无请求片段时：MxToken 由账号派生（64 字符 base64）
            rec2 = {}
            got2 = ns['simple_route'](rec2, None, 26000, '', fake_send, tmp)
            inner2 = json.loads(json.loads(got2[1][5:-1])['packet']) if got2 else {}
            mt = inner2.get('SessionKey', {}).get('MxToken') or ''
            add(len(mt) == 64 and inner2.get('SessionKey', {}).get('AccountServerId') == ns['SIMPLE_DEFAULT_ACCOUNT'],
                '无请求片段时 MxToken 由账号派生（%d 字符 base64）、账号回落到 %d'
                % (len(mt), ns['SIMPLE_DEFAULT_ACCOUNT']))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

        # ---- 5. 生成器口径一致：bridge 的 dict == gen_simple 经 specgen.conform 后的 dict
        try:
            import importlib.util
            sp = importlib.util.spec_from_file_location('v_specgen', SPECGEN_PATH)
            sg = importlib.util.module_from_spec(sp)
            sp.loader.exec_module(sg)
            S = sg.Spec(SPEC_PATH)
            fixed = dict(account_id=10015354380,
                         mxtoken='<REDACTED_TOKEN>',
                         rid='00000000-0000-4000-8000-000000000000',
                         ticks=639304002553346915)
            bad = []
            for proto in (1005, 4000, 26000):
                raw = ns['simple_build'](proto, **fixed)
                shaped = S.build(proto, json.loads(json.dumps(raw)), sg.Issues())
                if json.dumps(shaped, ensure_ascii=False, separators=(',', ':')) != \
                   json.dumps(raw, ensure_ascii=False, separators=(',', ':')):
                    bad.append(proto)
            add(not bad, 'bridge 载荷 == gen_simple 的 spec_conform 结果（键序/键数/类型全等）%s'
                % ('' if not bad else ' -> 不一致 %r' % (bad,)))
        except Exception as e:
            add(False, '生成器口径比对失败: %r' % (e,))

        for proto, fn, st, on in report_switches(bridge, ns):
            rep.append('INFO  %-6d %s %-14s -> %s' % (proto, fn, st, 'ON' if on else 'OFF'))

    if verbose:
        for line in rep:
            print('  ' + line)
    return state['ok'], rep


# ================================================================ CLI
def main(argv=None):
    ap = argparse.ArgumentParser(description='1005/4000/26000 三协议补丁（挂进 bridge 分发处）')
    ap.add_argument('--bridge', default=DEFAULT_BRIDGE, help='bridge 文件（默认线上路径）')
    ap.add_argument('--apply', action='store_true', help='打补丁')
    ap.add_argument('--verify', action='store_true', help='自检')
    ap.add_argument('--rollback', action='store_true', help='摘掉三块（幂等）')
    ap.add_argument('--dry-run', action='store_true', help='只看 diff，不写文件')
    ap.add_argument('--restore', default=None, help='配合 --rollback：直接用这个备份覆盖')
    ap.add_argument('--switches', choices=('keep', '1', '0'), default='keep',
                    help='开关文件：keep（默认：已有不动，缺失建 1）/ 1 / 0')
    ap.add_argument('--full-diff', action='store_true', help='--dry-run 时连 PAYLOAD 也逐行 diff')
    ap.add_argument('--only', default=None, help='只处理这些单元，如 HOOK-G,PAYLOAD')
    args = ap.parse_args(argv)

    only = None
    if args.only:
        only = tuple(x.strip().upper() for x in args.only.split(',') if x.strip())
        bad = [u for u in only if u not in UNITS]
        if bad:
            ap.error('未知单元 %s，可选 %s' % (bad, list(UNITS)))
        if UNIT_PAYLOAD not in only and args.apply and not args.rollback:
            print('!! 警告：选了 %s 但没有 PAYLOAD，hook 会在运行时 NameError（被 try/except 兜住，'
                  '但等于没接管）' % (list(only),))

    if not (args.apply or args.verify or args.rollback or args.dry_run):
        ap.error('要指定 --apply / --verify / --rollback / --dry-run 之一')
    if not os.path.isfile(args.bridge):
        raise SystemExit('bridge 不存在: %s' % args.bridge)

    orig = read_text(args.bridge)
    print('bridge  : %s  (%d 行 / %d 字节)' % (args.bridge, orig.count('\n'), len(orig.encode('utf-8'))))
    print('payload : %s  (sha256 %s)' % (PAYLOAD_PATH, sha256_text(payload_body())[:16]))

    # ---------------- rollback --restore
    if args.rollback and args.restore:
        if not os.path.isfile(args.restore):
            raise SystemExit('备份不存在: %s' % args.restore)
        bak = read_text(args.restore)
        ok, err = compile_ok(bak, args.restore)
        if not ok:
            raise SystemExit('备份本身语法不过，拒绝覆盖: %s' % err)
        shutil.copy2(args.restore, args.bridge)
        print('已用备份覆盖: %s -> %s' % (args.restore, args.bridge))
        print('残留标记检查: %s' % ('无（干净）' if 'BAPATCH-SIMPLE' not in read_text(args.bridge)
                                  else '仍有 BAPATCH-SIMPLE 标记'))
        return 0

    # ---------------- rollback
    if args.rollback:
        new_text, acts = build_removed(orig, only)
        for a in acts:
            print('  ' + a)
        if new_text == orig:
            print('  什么都没改（三块本来就不在）')
            return 0
        ok, err = compile_ok(new_text, args.bridge)
        if not ok:
            raise SystemExit('摘除后语法不过，拒绝写: %s' % err)
        bak = backup(args.bridge)
        write_text(args.bridge, new_text)
        print('  回滚完成。备份=%s' % bak)
        print('  残留标记: %s' % ('无（干净）' if 'BAPATCH-SIMPLE' not in new_text else '有残留'))
        return 0

    # ---------------- apply / dry-run
    if args.apply or args.dry_run:
        new_text, acts = build_patched(orig, only)
        for a in acts:
            print('  ' + a)
        if args.full_diff:
            diff = list(difflib.unified_diff(orig.split('\n'), new_text.split('\n'),
                                             fromfile=args.bridge,
                                             tofile=args.bridge + '.patched', lineterm='', n=3))
        elif args.dry_run:
            diff = list(difflib.unified_diff(mask_payload(orig).split('\n'),
                                             mask_payload(new_text).split('\n'),
                                             fromfile=args.bridge,
                                             tofile=args.bridge + '.patched', lineterm='', n=3))
        else:
            diff = []
        for ln in diff:
            print('  ' + ln)
        ok, err = compile_ok(new_text, args.bridge)
        print('语法检查: %s' % ('PASS' if ok else 'FAIL ' + err))
        if not ok:
            raise SystemExit('打出来的文件语法不过，已中止（没写任何东西）')
        if args.dry_run:
            print('--dry-run：没有写 bridge；开关文件也没动（正式执行时 --switches %s）' % args.switches)
            return 0
        bak = backup(args.bridge)
        write_text(args.bridge, new_text)
        print('已写入。备份: %s' % bak)
        print('还原命令: cp -a %s %s' % (bak, args.bridge))
        print('开关: %s' % ', '.join(apply_switches(args.bridge, args.switches)))
        vok, _ = verify(args.bridge, sha256_text(payload_body()))
        print('自检: %s' % ('全绿' if vok else '有 FAIL（见上）'))
        return 0 if vok else 1

    # ---------------- verify
    vok, _ = verify(args.bridge, sha256_text(payload_body()))
    if args.switches != 'keep':
        print('开关: %s' % ', '.join(apply_switches(args.bridge, args.switches)))
    return 0 if vok else 1


if __name__ == '__main__':
    sys.exit(main())
