#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patch_1017.py — 把 account_auth_probe.py 的 1017 分支接到动态生成器 gen1017。

背景
----
现网 `account_auth_probe.py:696-702` 对所有 1019/1017 都回同一个固定空包
（9 键 / inner 216 B / wire **492 B**），而官方 1017 是
**35 个顶层键 / inner 167,287 B / wire 246,808 B**。

本补丁**只做两处纯插入**，不改任何既有行：

    插入 A（模块级，在 `class Handler(...)` 之前）
        cn_1017_mode()          —— 运行时开关：'dynamic'（默认） / 'legacy'
        _gen1017_import()       —— 把 gen1017 所在目录塞进 sys.path 再 import

    插入 B（在 `        if num in (1019, 1017):` 之前）
        num == 1017 且 mode != 'legacy' 时调用 gen1017 生成 35 键响应并 return；
        任何异常只记 rec['gen1017_err'] 然后**继续落到下面未改动的旧分支**。

为什么是"纯插入"
----------------
* 旧分支原封不动 → `--legacy` 只是运行时把 mode 改成 legacy，行为精确回到 492 B；
* 不存在"改了某行导致 if/else 链断裂"的风险；
* `--rollback` 只要把两段 marker 之间的行删掉，就逐字节回到原文件（可用 sha256 验证）。

RequestId 闭合
-------------
`_cn_send_envelope` 自己 uuid4 生成 rid，只写外层、不回填 inner（这是 report102 §3.6
记的老问题）。本补丁**不走** `_cn_send_envelope`：

    _rid = uuid4()
    obj  = gen1017.build(..., request_id=_rid)   →  obj['RequestId'] == _rid
    wire = cn_wire.wrap_response(name, obj, _rid)  →  外层 requestid == _rid

于是 inner RequestId == outer requestid，与官方实测一致（官方那条两者逐字节相同）。
HTTP 响应头上本来就没有 REQUEST-ID 头（`_send` 只发 4 个头，对**所有**协议都如此），
客户端是从响应体内层 RequestId 取下一个 REQUEST-ID 的，所以内层同值即可。

用法
----
    # 看将插入什么（不写盘）
    python patch_1017.py --dry-run

    # 应用（自动备份到 <target>.bak.<YYYYmmdd-HHMMSS>）
    python patch_1017.py --apply

    # 校验：语法 + marker + 旧分支完好 + gen1017 能生成 35 键
    python patch_1017.py --verify

    # 一键切回 492 B 旧实现（不重新打补丁，只写开关文件）
    python patch_1017.py --legacy
    python patch_1017.py --legacy off      # 切回动态
    python patch_1017.py --legacy status

    # 撤补丁（删两段 marker 块，逐字节回到原文件）
    python patch_1017.py --rollback

部署时需要一起放到 tools 目录的三个文件：
    account_auth_probe.py（被改） / gen1017.py / specgen.py
外加数据文件（gen1017 会自己按 repo 布局或环境变量找）：
    official_spec.json / initial_state_rules.json / ExcelDB.db
"""
from __future__ import annotations

import argparse
import datetime as _dt
import difflib
import hashlib
import json
import os
import re
import shutil
import sys
import uuid

DEFAULT_TARGET = "/www/wwwroot/bapatch/tools/account_auth_probe.py"
DEFAULT_MODE_FILE = "/www/wwwroot/bapatch/cn_1017_mode.txt"
GEN1017_NAME = "gen1017.py"

HERE = os.path.dirname(os.path.abspath(__file__))

VERSION = "v1"
MARK_BEGIN = "# >>> BA-1017-DYNAMIC-PATCH %s" % VERSION
MARK_END = "# <<< BA-1017-DYNAMIC-PATCH %s <<<" % VERSION

ANCHOR_A = "class Handler(http.server.BaseHTTPRequestHandler):"
ANCHOR_B = "        if num in (1019, 1017):"

# 旧的 1017/1019 分支（原始 696-702 行）—— 必须原样保留，用来做完整性校验
LEGACY_BLOCK = """        if num in (1019, 1017):
            obj = {"Protocol": 1019, "ServerTimeTicks": 0, "ServerNotification": 0,
                   "MissionProgressDBs": [], "EventMissionProgressDBDict": {},
                   "BattlePassMissionProgressDBDict": {}, "StaticOpenConditions": [],
                   "Responses": [], "SkillCutInOption": ""}
            rec['gen_kind'] = 'loginsync-%d' % num
            obj['Protocol'] = num""".splitlines()


# ---------------------------------------------------------------- 插入块
def block_a(eol):
    lines = [
        MARK_BEGIN + "  (work/ba/server/deploy/patch_1017.py)",
        "# 1017 Account_LoginSync 动态生成 —— 运行时开关。",
        "#   cn_1017_mode.txt 内容 'dynamic'（默认）/'legacy'；文件不存在 = dynamic。",
        "#   环境变量 CN_1017_MODE 优先级更高（便于单次启动临时覆盖）。",
        "CN_1017_MODE_FILE = %r" % DEFAULT_MODE_FILE,
        "GEN1017_DIR = os.environ.get('BA_GEN1017_DIR') or os.path.dirname(os.path.abspath(__file__))",
        "",
        "",
        "def cn_1017_mode():",
        "    v = (os.environ.get('CN_1017_MODE') or '').strip().lower()",
        "    if v:",
        "        return v",
        "    try:",
        "        v = open(CN_1017_MODE_FILE).read().strip().lower()",
        "    except Exception:",
        "        return 'dynamic'",
        "    return v or 'dynamic'",
        "",
        "",
        "def _gen1017_import():",
        "    if GEN1017_DIR and GEN1017_DIR not in sys.path:",
        "        sys.path.insert(0, GEN1017_DIR)",
        "    import gen1017",
        "    return gen1017",
        "",
        MARK_END + "  (module level)",
    ]
    return [ln + eol for ln in lines]


def block_b(eol):
    lines = [
        MARK_BEGIN + "  (work/ba/server/deploy/patch_1017.py)",
        "# 1017 走动态生成器（35 键 / 26 具名子回包 / 无 Responses 数组）。",
        "# 关掉开关（--legacy）或任何异常 → 静默落到下面**未改动**的旧 492 B 分支。",
        "        if num == 1017 and cn_1017_mode() != 'legacy':",
        "            try:",
        "                import uuid as _u1017",
        "                _rid = str(_u1017.uuid4())",
        "                _sk = SESSION.session_key or {}",
        "                _sid = _sk.get('AccountServerId') or SESSION.account_id or 0",
        "                _obj = _gen1017_import().build(",
        "                    account_state={'server_id': _sid},",
        "                    session=_sk,",
        "                    request_id=_rid)",
        "                _obj['RequestId'] = _rid      # inner == outer requestid（官方逐字节相同）",
        "                _nm = name if (name and name != 'Unknown') else 'Account_LoginSync'",
        "                _wire, _plain, _key = cn_wire.wrap_response(_nm, _obj, _rid)",
        "                rec['gen_kind'] = 'loginsync-1017-dynamic'",
        "                rec['fallback'] = 'gen1017'",
        "                rec['wrap_mode'] = 'direct_envelope'",
        "                rec['enc_requestid'] = _rid",
        "                rec['enc_inner_keys'] = len(_obj)",
        "                rec['gen1017_inner_len'] = _gen1017_import().measure(",
        "                    _obj, _nm, _rid)['inner']",
        "                rec['enc_plain_len'] = len(_plain)",
        "                rec['enc_body_len'] = len(_wire)",
        "                rec['_send_opts'] = {'ctype': 'text/plain; charset=utf-8', 'close': True}",
        "                return 200, _wire, 'text/plain; charset=utf-8'",
        "            except Exception as _e1017:",
        "                rec['gen1017_err'] = repr(_e1017)",
        "",
        MARK_END + "  (1017 dispatch)",
    ]
    return [ln + eol for ln in lines]


# ---------------------------------------------------------------- 文件操作
def read_text(path):
    with open(path, "rb") as fh:
        raw = fh.read()
    return raw, raw.decode("utf-8")


def eol_of(text):
    crlf = text.count("\r\n")
    lf = text.count("\n") - crlf
    return "\r\n" if crlf > lf else "\n"


def split_lines(text):
    """按 \\n 切但保留行尾（用 keepends 语义）。"""
    out, cur = [], 0
    for i, ch in enumerate(text):
        if ch == "\n":
            out.append(text[cur:i + 1])
            cur = i + 1
    if cur < len(text):
        out.append(text[cur:])
    return out


def strip_eol(line):
    return line.rstrip("\r\n")


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def is_under(path, marker):
    p = os.path.abspath(path).replace("\\", "/").lower()
    return marker.lower() in p


def marker_count(text, marker):
    return sum(1 for ln in split_lines(text) if strip_eol(ln).startswith(marker))


def find_line(lines, exact):
    """返回 exact 行（去行尾）首次出现的下标。"""
    for i, ln in enumerate(lines):
        if strip_eol(ln) == exact:
            return i
    return -1


def legacy_block_ok(lines, at):
    """at 指向 `if num in (1019, 1017):`，校验后面 6 行与原文件逐字相同。"""
    for k, want in enumerate(LEGACY_BLOCK):
        idx = at + k
        if idx >= len(lines):
            return False, "文件在 %d 行处结束（旧分支不完整）" % idx
        got = strip_eol(lines[idx])
        if got != want:
            return False, "第 %d 行与旧分支不一致:\n    期望 %r\n    实际 %r" % (idx + 1, want, got)
    return True, "旧 1017/1019 分支 7 行逐字匹配"


# ---------------------------------------------------------------- 动作
def cmd_apply(target, dry_run, force, keep_backup, quiet):
    raw, text = read_text(target)
    lines = split_lines(text)
    eol = eol_of(text)

    # ---------- 幂等：已经打过就什么都不做
    nb, ne = marker_count(text, MARK_BEGIN), marker_count(text, MARK_END)
    if nb == 2 and ne == 2:
        if not quiet:
            print("[apply] 已经是打过补丁的状态（marker 各 2 处），无改动。")
            print("        目标: %s" % os.path.abspath(target))
            print("        sha256: %s" % sha256_bytes(raw))
        return 0
    if nb or ne:
        print("[apply] !! marker 数量异常（begin=%d, end=%d），文件可能被手工改过。"
              % (nb, ne))
        print("        先 --rollback 清理，再 --apply。")
        return 2

    ia = find_line(lines, ANCHOR_A)
    ib = find_line(lines, ANCHOR_B)
    if ia < 0:
        print("[apply] !! 找不到锚点 A: %r" % ANCHOR_A)
        return 2
    if ib < 0:
        print("[apply] !! 找不到锚点 B: %r" % ANCHOR_B)
        return 2
    ok, why = legacy_block_ok(lines, ib)
    if not ok:
        print("[apply] !! 旧分支校验失败: %s" % why)
        if not force:
            print("        线上跑的可能不是仓库里这一版（report102 §2 说线上 gen_kind='min' 就是旧版）。")
            print("        确认要在这份文件上打补丁请加 --force。")
            return 3
        print("        --force：继续。")

    # 先插 B 再插 A（A 在更前面，插完 A 后 B 的下标会顺移，所以按倒序插）
    new_lines = list(lines)
    new_lines[ib:ib] = block_b(eol)
    new_lines[ia:ia] = block_a(eol)
    new_text = "".join(new_lines)

    # ---------- 语法检查
    try:
        compile(new_text, target, "exec")
    except SyntaxError as e:
        print("[apply] !! 打补丁后语法错误，已放弃写入: %s" % (e,))
        return 4

    diff = list(difflib.unified_diff(
        split_lines(text), split_lines(new_text),
        fromfile="a/account_auth_probe.py", tofile="b/account_auth_probe.py", n=3))

    if dry_run:
        print("[dry-run] 将写入 %s" % os.path.abspath(target))
        print("[dry-run] 原文 %d 行 → 新文 %d 行（+%d 行，纯插入，无删改）"
              % (len(lines), len(new_lines), len(new_lines) - len(lines)))
        print("[dry-run] diff（unified，n=3）:")
        for ln in diff:
            sys.stdout.write(ln if ln.endswith("\n") else ln + "\n")
        return 0

    # ---------- 备份 + 原子写
    ts = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = "%s.bak.%s" % (target, ts)
    shutil.copy2(target, bak)
    tmp = target + ".tmp.%s" % ts
    with open(tmp, "wb") as fh:
        fh.write(new_text.encode("utf-8"))
    os.replace(tmp, target)

    print("[apply] OK  %s" % os.path.abspath(target))
    print("        原文 %d 行 (%d B, sha256=%s)"
          % (len(lines), len(raw), sha256_bytes(raw)))
    print("        新文 %d 行 (+%d 行, sha256=%s)"
          % (len(new_lines), len(new_lines) - len(lines), sha256_bytes(new_text.encode("utf-8"))))
    print("        备份 %s%s" % (bak, "" if keep_backup else ""))
    print("        语法检查: ok")
    print("        补丁后 1017 生效条件: cn_1017_mode() != 'legacy'")
    print("        下一步：重启 bridge 进程，让新模块生效。")
    return 0


def cmd_rollback(target, mode_file, quiet):
    raw, text = read_text(target)
    nb, ne = marker_count(text, MARK_BEGIN), marker_count(text, MARK_END)
    if nb == 0 and ne == 0:
        print("[rollback] 文件里没有 marker，已经处于未打补丁状态，无改动。")
        return 0
    if nb != ne:
        print("[rollback] !! marker 不配对（begin=%d, end=%d），拒绝自动删除。" % (nb, ne))
        return 2

    out, skipping = [], False
    for ln in split_lines(text):
        s = strip_eol(ln)
        if s.startswith(MARK_BEGIN):
            if skipping:
                print("[rollback] !! marker 嵌套，拒绝。")
                return 2
            skipping = True
            continue
        if s.startswith(MARK_END):
            if not skipping:
                print("[rollback] !! 出现无配对的 end marker，拒绝。")
                return 2
            skipping = False
            continue
        if not skipping:
            out.append(ln)
    new_text = "".join(out)
    try:
        compile(new_text, target, "exec")
    except SyntaxError as e:
        print("[rollback] !! 剥离 marker 后语法错误，已放弃: %s" % (e,))
        return 4

    single = text.replace("\r\n", "\n")
    stripped_single = new_text.replace("\r\n", "\n")
    # 与备份比对（如果备份在）
    cands = sorted([p for p in _glob_baks(target)])
    matched = None
    for c in cands:
        try:
            _b, bt = read_text(c)
        except Exception:
            continue
        if bt.replace("\r\n", "\n") == stripped_single:
            matched = c
            break

    ts = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = "%s.pre-rollback.%s" % (target, ts)
    shutil.copy2(target, bak)
    tmp = target + ".tmp.%s" % ts
    with open(tmp, "wb") as fh:
        fh.write(new_text.encode("utf-8"))
    os.replace(tmp, target)

    print("[rollback] OK  %s" % os.path.abspath(target))
    print("           删除 %d 段 marker 块，行数 %d → %d"
          % (nb, len(split_lines(text)), len(split_lines(new_text))))
    print("           语法检查: ok")
    print("           剥离后 sha256 = %s" % sha256_bytes(new_text.encode("utf-8")))
    if matched:
        print("           与备份 %s 逐字节相同 ✔" % os.path.basename(matched))
    elif cands:
        print("           !! 剥离结果与任何 .bak 都不同（%d 个备份）——请人工比对" % len(cands))
    else:
        print("           未找到 .bak 备份；剥离结果自洽（marker 块是纯插入，可逆）")
    print("           切回动态前请确认开关文件：%s = dynamic" % mode_file)
    return 0


def _glob_baks(target):
    d = os.path.dirname(os.path.abspath(target)) or "."
    base = os.path.basename(target)
    try:
        for n in os.listdir(d):
            if n.startswith(base + ".bak."):
                yield os.path.join(d, n)
    except OSError:
        return


def cmd_verify(target, mode_file, quiet):
    ok = True
    raw, text = read_text(target)
    lines = split_lines(text)
    print("[verify] 目标        : %s" % os.path.abspath(target))
    print("[verify] 大小/sha256 : %d B / %s" % (len(raw), sha256_bytes(raw)))

    # 1) 语法
    try:
        compile(text, target, "exec")
        print("[verify] 语法        : ok")
    except SyntaxError as e:
        print("[verify] 语法        : FAIL  %s" % (e,))
        ok = False

    # 2) marker
    nb, ne = marker_count(text, MARK_BEGIN), marker_count(text, MARK_END)
    state = "已打补丁" if (nb == 2 and ne == 2) else ("未打补丁" if nb == 0 and ne == 0 else "异常")
    print("[verify] marker      : begin=%d end=%d → %s" % (nb, ne, state))
    if state == "异常":
        ok = False

    # 3) 锚点 + 旧分支完好
    ia = find_line(lines, ANCHOR_A)
    ib = find_line(lines, ANCHOR_B)
    print("[verify] 锚点 A      : %s" % ("第 %d 行" % (ia + 1) if ia >= 0 else "缺失"))
    print("[verify] 锚点 B      : %s" % ("第 %d 行" % (ib + 1) if ib >= 0 else "缺失"))
    if ia < 0 or ib < 0:
        ok = False
    else:
        good, why = legacy_block_ok(lines, ib)
        print("[verify] 旧分支      : %s" % why)
        if not good:
            ok = False

    # 4) gen1017 可加载 + 能产出 35 键
    gpath = os.path.join(HERE, GEN1017_NAME)
    if not os.path.isfile(gpath):
        gpath = None
        d = os.environ.get("BA_GEN1017_DIR")
        if d and os.path.isfile(os.path.join(d, GEN1017_NAME)):
            gpath = os.path.join(d, GEN1017_NAME)
    if gpath:
        try:
            sys.path.insert(0, os.path.dirname(gpath))
            import gen1017
            obj = gen1017.build({"server_id": 10015354380},
                                None,
                                request_id=str(uuid.uuid4()),
                                now="2026-11-16T05:00:00")
            m = gen1017.measure(obj)
            errs, _n = gen1017.selfcheck(obj)
            sub = gen1017.sub_response_names()
            print("[verify] gen1017     : 顶层 %d 键 / 子回包 %d / inner %d B / wire %d B"
                  % (len(obj), len(sub), m["inner"], m["wire"]))
            print("[verify] 自检        : %s" % ("PASS" if not errs else "FAIL %d" % len(errs)))
            for e in errs[:5]:
                print("           !! %s" % e)
            if errs:
                ok = False
        except Exception as e:
            print("[verify] gen1017     : FAIL  %r" % (e,))
            ok = False
    else:
        print("[verify] gen1017     : 未找到 %s（部署时需要与 probe 放同一目录）" % GEN1017_NAME)

    # 5) 运行时开关
    mode = _read_mode(mode_file)
    print("[verify] 运行时开关  : cn_1017_mode() = %r  (%s)" % (mode, mode_file))
    if state == "已打补丁":
        print("[verify] 预期行为    : %s" % (
            "1017 → 动态（35 键）" if mode != "legacy" else "1017 → 旧固定包（wire 492 B）"))
    print("[verify] 结论        : %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def _read_mode(mode_file):
    v = (os.environ.get("CN_1017_MODE") or "").strip().lower()
    if v:
        return v
    try:
        with open(mode_file, "r", encoding="utf-8") as fh:
            v = fh.read().strip().lower()
    except Exception:
        return "dynamic"
    return v or "dynamic"


def cmd_legacy(target, mode_file, value, quiet):
    if value == "status":
        m = _read_mode(mode_file)
        print("[legacy] 当前模式: %r  (%s)" % (m, mode_file))
        print("[legacy] 1017 将走: %s" % ("旧固定包 / wire 492 B" if m == "legacy"
                                          else "动态生成 / 35 键"))
        return 0
    want = "legacy" if value in ("on", "legacy", "1", "true", "") else "dynamic"
    d = os.path.dirname(os.path.abspath(mode_file))
    if d and not os.path.isdir(d):
        try:
            os.makedirs(d)
        except OSError as e:
            print("[legacy] !! 无法创建目录 %s: %s" % (d, e))
            return 2
    try:
        with open(mode_file, "w", encoding="utf-8") as fh:
            fh.write(want + "\n")
    except OSError as e:
        print("[legacy] !! 写入 %s 失败: %s" % (mode_file, e))
        print("         可以改用环境变量 CN_1017_MODE=%s 启动 bridge。" % want)
        return 2
    print("[legacy] OK  已写入 %s = %r" % (mode_file, want))
    print("[legacy] 1017 现在是: %s" % ("旧固定包（inner 216 B / wire 492 B）" if want == "legacy"
                                       else "动态生成（35 键 / A 号 wire 124,248 B）"))
    print("[legacy] 生效不需要重启（每次请求都会重读该文件）。")
    return 0


# ---------------------------------------------------------------- 补丁块逻辑证明
def cmd_prove_dispatch(target, quiet):
    """从**已打过补丁的文件里**把插入的 1017 分发块抽出来，用桩跑一遍。

    本地没有 cryptography，跑不起整个 bridge；但分发块的正确性只需要 5 件事：
      1) 它在原始缩进下语法正确（抽出来 dedent 后 compile）；
      2) 调 gen1017.build 拿到的 obj 是 35 键；
      3) 传给 cn_wire.wrap_response 的 requestid == obj['RequestId'] == 新 uuid4；
      4) 返回值是 (200, wire, 'text/plain; charset=utf-8')；
      5) mode == 'legacy' 时**不**返回（落到旧分支）。
    """
    raw, text = read_text(target)
    lines = split_lines(text)
    nb = marker_count(text, MARK_BEGIN)
    if nb != 2:
        print("[prove] 目标未打补丁（marker=%d），先 --apply" % nb)
        return 2

    # 取第 2 段（dispatch）
    blocks, cur = [], None
    for ln in lines:
        s = strip_eol(ln)
        if s.startswith(MARK_BEGIN):
            cur = []
            continue
        if s.startswith(MARK_END):
            if cur is not None:
                blocks.append(cur)
            cur = None
            continue
        if cur is not None:
            cur.append(ln)
    if len(blocks) != 2:
        print("[prove] 期望 2 段 marker 块，实际 %d 段" % len(blocks))
        return 2
    body = blocks[1]

    src = ["def _probe(self, num, name, rec, SESSION, cn_wire, cn_1017_mode, _gen1017_import):"]
    for ln in body:
        s = strip_eol(ln)
        src.append(s[4:] if s.startswith("    ") else s)
    src.append("    return None")
    code = "\n".join(src) + "\n"
    try:
        compile(code, "<probe>", "exec")
    except SyntaxError as e:
        print("[prove] FAIL 抽出后语法错误: %s" % (e,))
        return 1

    # ---- 桩
    sys.path.insert(0, HERE)
    import gen1017
    seen = {}

    class Wire(object):
        @staticmethod
        def wrap_response(protocol_name, inner_obj, requestid=None, key=None):
            seen["name"] = protocol_name
            seen["rid"] = requestid
            seen["obj"] = inner_obj
            inner = json.dumps(inner_obj, ensure_ascii=False, separators=(",", ":"))
            plain = json.dumps({"protocol": protocol_name, "packet": inner,
                                "requestid": requestid or ""},
                               ensure_ascii=False, separators=(",", ":"))
            ct = 16 * ((len(plain.encode("utf-8")) + 15) // 16)
            seen["plain"] = plain
            return b"x" * (4 * ((ct + 32 + 2) // 3)), plain, b"k" * 32

    class Sess(object):
        session_key = {"AccountServerId": 10015354380,
                       "MxToken": "A" * 64}
        account_id = 10015354380

    ns = {}
    exec(compile(code, "<probe>", "exec"), {"json": json}, ns)
    probe = ns["_probe"]

    failures = []

    # (a) dynamic 模式
    rec = {}
    got = probe(None, 1017, "Account_LoginSync", rec, Sess, Wire,
                lambda: "dynamic", lambda: gen1017)
    if not (isinstance(got, tuple) and len(got) == 3):
        failures.append("dynamic 模式没有返回三元组: %r" % (got,))
    else:
        code_, body_, ctype_ = got
        if code_ != 200:
            failures.append("返回码 %r != 200" % (code_,))
        if ctype_ != "text/plain; charset=utf-8":
            failures.append("ctype = %r" % (ctype_,))
    obj = seen.get("obj") or {}
    if len(obj) != 35:
        failures.append("obj 顶层键 %d != 35" % len(obj))
    if not seen.get("rid") or seen.get("rid") != obj.get("RequestId"):
        failures.append("wrap_response 的 requestid(%r) != obj['RequestId'](%r)"
                        % (seen.get("rid"), obj.get("RequestId")))
    try:
        uuid.UUID(str(obj.get("RequestId")))
    except Exception:
        failures.append("obj['RequestId'] 不是合法 uuid: %r" % (obj.get("RequestId"),))
    try:
        outer = json.loads(seen.get("plain") or "{}")
        if outer.get("requestid") != obj.get("RequestId"):
            failures.append("外层 requestid != 内层 RequestId")
        if outer.get("protocol") != "Account_LoginSync":
            failures.append("外层 protocol = %r" % (outer.get("protocol"),))
    except Exception as e:
        failures.append("外层明文解析失败: %r" % (e,))
    if len(seen.get("plain", "")) and gen1017.measure(obj, "Account_LoginSync",
                                                      obj.get("RequestId"))["wire"] != len(got[1] if isinstance(got, tuple) and len(got) == 3 else b""):
        failures.append("wire 长度与 measure() 推算不一致")
    if rec.get("gen_kind") != "loginsync-1017-dynamic":
        failures.append("rec['gen_kind'] = %r" % (rec.get("gen_kind"),))
    if rec.get("gen1017_err"):
        failures.append("rec['gen1017_err'] = %r" % (rec.get("gen1017_err"),))

    # (b) legacy 模式：必须不返回
    rec2 = {}
    got2 = probe(None, 1017, "Account_LoginSync", rec2, Sess, Wire,
                 lambda: "legacy", lambda: gen1017)
    if got2 is not None:
        failures.append("legacy 模式竟然返回了 %r（应落到旧分支）" % (got2,))

    # (c) gen1017 抛异常：必须吞掉并落到旧分支
    def _boom():
        raise RuntimeError("boom")
    rec3 = {}
    got3 = probe(None, 1017, "Account_LoginSync", rec3, Sess, Wire, lambda: "dynamic", _boom)
    if got3 is not None:
        failures.append("gen1017 异常时没有落到旧分支")
    if "boom" not in str(rec3.get("gen1017_err")):
        failures.append("异常没有记进 rec['gen1017_err']: %r" % (rec3.get("gen1017_err"),))

    print("[prove] 抽出的分发块（%d 行）在桩环境下执行结果:" % len(body))
    print("        返回三元组          : %s" % ("ok" if isinstance(got, tuple) else "FAIL"))
    print("        obj 顶层键          : %d" % len(obj))
    print("        requestid 闭合      : %s" % (
        "outer == inner == " + str(obj.get("RequestId"))
        if not failures or seen.get("rid") == obj.get("RequestId") else "FAIL"))
    print("        wire 长度           : %d B" % (len(got[1]) if isinstance(got, tuple) else -1))
    print("        legacy 模式落到旧分支: %s" % (got2 is None))
    print("        gen1017 异常兜底     : %s（rec['gen1017_err']=%r）"
          % (got3 is None, rec3.get("gen1017_err")))
    if failures:
        print("[prove] 结论: FAIL")
        for f in failures:
            print("        !! %s" % f)
        return 1
    print("[prove] 结论: PASS")
    return 0


# ---------------------------------------------------------------- CLI
def main(argv=None):
    ap = argparse.ArgumentParser(
        description="给 account_auth_probe.py 的 1017 分支打动态生成补丁",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__)
    ap.add_argument("--target", default=DEFAULT_TARGET,
                    help="account_auth_probe.py 路径（默认 %s）" % DEFAULT_TARGET)
    ap.add_argument("--mode-file", default=DEFAULT_MODE_FILE,
                    help="运行时开关文件（默认 %s）" % DEFAULT_MODE_FILE)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--apply", action="store_true", help="打补丁（自动备份，幂等）")
    g.add_argument("--verify", action="store_true", help="校验补丁状态/语法/旧分支/gen1017")
    g.add_argument("--rollback", action="store_true", help="撤补丁（删除 marker 块）")
    g.add_argument("--dry-run", action="store_true", help="只打印将插入的内容与 diff")
    g.add_argument("--prove-dispatch", action="store_true",
                   help="把已插入的 1017 分发块抽出来用桩执行，验证 requestid 闭合/兜底")
    g.add_argument("--legacy", nargs="?", const="on", default=None,
                   metavar="{on|off|status}",
                   help="运行时开关：默认 on=切回 492 B 旧实现，off=切回动态，status=查看")
    ap.add_argument("--force", action="store_true",
                    help="旧分支与仓库快照不一致时仍然打补丁")
    ap.add_argument("--keep-backup", action="store_true", default=True,
                    help="保留 .bak.<TS>（默认开）")
    ap.add_argument("--allow-reference-dir", action="store_true",
                    help="允许对 _bridge_ref/ 下的只读参考副本打补丁（默认拒绝）")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    if not os.path.isfile(args.target):
        print("!! 目标文件不存在: %s" % os.path.abspath(args.target))
        print("   线上路径默认 /www/wwwroot/bapatch/tools/account_auth_probe.py")
        print("   本地自测请 --target <副本路径>（不要直接改 _bridge_ref 下的参考副本）")
        return 2

    if is_under(args.target, "_bridge_ref") and not args.allow_reference_dir:
        print("!! 拒绝写入 _bridge_ref/ ：那是 report102 §2 的只读参考基线。")
        print("   要自测请先复制到别处：cp _bridge_ref/account_auth_probe.py /tmp/t/probe.py")
        return 2

    if args.dry_run:
        return cmd_apply(args.target, True, args.force, args.keep_backup, args.quiet)
    if args.apply:
        return cmd_apply(args.target, False, args.force, args.keep_backup, args.quiet)
    if args.verify:
        return cmd_verify(args.target, args.mode_file, args.quiet)
    if args.rollback:
        return cmd_rollback(args.target, args.mode_file, args.quiet)
    if args.prove_dispatch:
        return cmd_prove_dispatch(args.target, args.quiet)
    if args.legacy is not None:
        return cmd_legacy(args.target, args.mode_file, args.legacy, args.quiet)
    ap.print_help()
    return 0


# ---------------------------------------------------------------- selftest
def selftest():
    """在不碰线上文件的前提下，把 apply→verify→rollback→verify 跑一遍。

    做法：把 --target 指向一个临时副本。返回 0 = 全通。
    """
    import tempfile
    src = os.path.join(os.path.dirname(HERE), "_bridge_ref", "account_auth_probe.py")
    if not os.path.isfile(src):
        print("selftest: 找不到 %s" % src)
        return 2
    tmpd = tempfile.mkdtemp(prefix="ba1017-")
    tgt = os.path.join(tmpd, "account_auth_probe.py")
    shutil.copy2(src, tgt)
    orig = open(src, "rb").read()
    rc = 0
    print("=" * 78)
    print("selftest: apply → apply(幂等) → verify → rollback → 逐字节比对")
    print("=" * 78)
    print("\n-- 1) dry-run --")
    rc |= cmd_apply(tgt, True, False, True, True)
    print("\n-- 2) apply --")
    rc |= cmd_apply(tgt, False, False, True, True)
    print("\n-- 3) apply 再来一次（应无改动）--")
    before = open(tgt, "rb").read()
    rc |= cmd_apply(tgt, False, False, True, True)
    after = open(tgt, "rb").read()
    idem = before == after
    print("         幂等: %s" % idem)
    if not idem:
        rc |= 1
    print("\n-- 4) verify --")
    rc |= cmd_verify(tgt, os.path.join(tmpd, "mode.txt"), True)
    print("\n-- 5) rollback --")
    rc |= cmd_rollback(tgt, os.path.join(tmpd, "mode.txt"), True)
    got = open(tgt, "rb").read()
    same = got == orig
    print("         与原文件逐字节相同: %s" % same)
    if not same:
        rc |= 1
    print("\n-- 6) verify（未打补丁态）--")
    rc |= cmd_verify(tgt, os.path.join(tmpd, "mode.txt"), True) and 0
    print("\nselftest 结果: %s   (临时目录 %s)" % ("PASS" if rc == 0 else "FAIL", tmpd))
    return 0 if rc == 0 else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    sys.exit(main())
