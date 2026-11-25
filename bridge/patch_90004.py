#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patch_90004.py — 修 bridge 里 90004 Management_Data 的 Data 外壳（P0）。

    python work\\ba\\server\\deploy\\patch_90004.py --seed           # 把 _bridge_ref 的快照复制到 _sandbox
    python work\\ba\\server\\deploy\\patch_90004.py --dry-run        # 看 diff，不写
    python work\\ba\\server\\deploy\\patch_90004.py --apply          # 备份 + 写入 + 自动 verify
    python work\\ba\\server\\deploy\\patch_90004.py --verify         # 只校验
    python work\\ba\\server\\deploy\\patch_90004.py --rollback       # 回到最近的备份

线上用法（先按 102 方案 §0 把线上文件拉回本地基线，再对本文件打补丁）：
    python patch_90004.py --src /tmp/live_account_auth_probe.py --apply

改的是什么
----------
1) 往 bridge 里**内联** dto90004.py 的正文（同一份代码，不是抄一遍），
   marker 包起来：`# ==== BEGIN 90004-PATCH v1 ====` … `# ==== END 90004-PATCH v1 ====`
2) 把 `if num == 90004:` 分支从「16 键平铺」换成「6 键 + Data(9 键)」：
   旧：{"Protocol":90004, "ServerTimeTicks":…, "ServerNotification":0,
        "MissionProgressDBs":[], "EventMissionProgressDBDict":{},
        "BattlePassMissionProgressDBDict":{}, "StaticOpenConditions":{…},
        "Notices":[], "Events":[], "Issues":[], "Banners":[],
        "GachaProbabilityDisplay":False, "ContentLock":False,
        "GachaPeriodDisplay":False, "RaidPeriodDisplay":False, "GuidePopup":{}}
   新：{"Protocol":90004, "SessionKey":{…}, "ServerTimeTicks":…,
        "ServerNotification":0, "RequestId":"<uuid4>",
        "Data":{"Notices":[],"Events":[],"Issues":[],"Banners":[],
                "GachaProbabilityDisplay":[],"GuidePopup":[],
                "GachaPeriodDisplay":null,"RaidPeriodDisplay":null,"Survey":null}}
3) （默认，可用 --no-sync-outer-requestid 关掉）把 `_cn_send_envelope` 里的
   `rid = str(_uuid.uuid4())` 改成优先复用 obj['RequestId'] —— 官方 outer requestid
   与 inner RequestId 逐字节相同（102 方案 §3.6）。这条对所有走 _cn_send_envelope 的
   协议都生效，但只有**带了 RequestId 的 obj** 才会变，没有 RequestId 的协议行为不变。

幂等性：marker 已在 → --apply 什么都不改（也不会再备份一份）。
安全性：写入前一定先备份；--verify 会把内联块单独 exec 出来，用官方 spec 校验输出。
"""
from __future__ import annotations

import argparse
import ast
import datetime as _dt
import difflib
import hashlib
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_common as G                                   # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REF_SRC = os.path.join(G.ROOT, "work", "ba", "server", "_bridge_ref", "account_auth_probe.py")
# 独占子目录：deploy/_sandbox 下可能同时有别条线的补丁在工作，90004 只碰自己的副本
SANDBOX = os.path.join(HERE, "_sandbox", "90004", "account_auth_probe.py")
DTO_SRC = os.path.join(HERE, "dto90004.py")

PATCH_ID = "90004-PATCH v1"
BEGIN = "# ==== BEGIN %s (from work/ba/server/deploy/dto90004.py)" % PATCH_ID
END = "# ==== END %s ====" % PATCH_ID
RID_TAG = "# 90004-PATCH: outer requestid = inner RequestId"

RE_BRANCH = re.compile(r"^([ \t]*)if num == 90004:[ \t]*$", re.M)
RE_RID = re.compile(r"^([ \t]*)rid = str\(_uuid\.uuid4\(\)\)[ \t]*$", re.M)


# ================================================================ 内联块
def inline_block():
    """把 dto90004.py 的顶层语句（去掉 docstring 与 __main__）原样取出来。"""
    src = open(DTO_SRC, "r", encoding="utf-8").read()
    tree = ast.parse(src)
    parts = []
    prev_import = False
    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) \
                and isinstance(node.value.value, str):
            continue                                   # 模块 docstring
        if isinstance(node, ast.If):
            t = node.test
            if isinstance(t, ast.Compare) and isinstance(t.left, ast.Name) \
                    and t.left.id == "__name__":
                continue                               # if __name__ == "__main__"
        seg = ast.get_source_segment(src, node)
        if not seg:
            continue
        is_import = isinstance(node, (ast.Import, ast.ImportFrom))
        if parts:
            parts.append("\n" if (prev_import and is_import) else "\n\n")
        parts.append(seg)
        prev_import = is_import
    return "".join(parts).rstrip("\n") + "\n"


def block_text(nl="\n"):
    body = inline_block().replace("\r\n", "\n")
    lines = [BEGIN,
             "# 本块由 work/ba/server/deploy/patch_90004.py --apply 生成，不要手改。",
             "# 改逻辑请改 work/ba/server/deploy/dto90004.py，然后重新 --apply（幂等）。",
             ""]
    lines += body.rstrip("\n").split("\n")
    lines += ["", END]
    return nl.join(lines) + nl


# ================================================================ 定位
def find_branch(text):
    """→ (start, end, indent, block_text)  字符偏移，end 指向 return 行末尾（不含换行）。"""
    m = RE_BRANCH.search(text)
    if not m:
        raise PatchError("找不到 `if num == 90004:` 分支（线上版本可能不同）")
    ind = m.group(1)
    start = m.start()
    # 从下一行开始找属于这个分支的 return self._cn_send_envelope(...)
    pos = text.find("\n", m.end())
    if pos < 0:
        raise PatchError("90004 分支在文件末尾，异常")
    pos += 1
    cur = pos
    n = len(text)
    while cur < n:
        eol = text.find("\n", cur)
        if eol < 0:
            eol = n
        line = text[cur:eol]
        stripped = line.strip()
        if stripped and not line.startswith(ind + " ") and not line.startswith(ind + "\t") \
                and line[:len(ind)] == ind and len(line) > len(ind) and line[len(ind)] != " ":
            raise PatchError("90004 分支在第 %d 行意外结束（没有 return self._cn_send_envelope）"
                             % (text[:cur].count("\n") + 1))
        if stripped.startswith("return self._cn_send_envelope("):
            block = text[start:eol]
            if "90004" not in block:
                raise PatchError("90004 分支里没出现 90004 字面量，anchor 不可信")
            return start, eol, ind, block
        if stripped and stripped[0] not in ")]}" and not line.startswith(ind):
            raise PatchError("90004 分支在第 %d 行意外结束" % (text[:cur].count("\n") + 1))
        cur = eol + 1
    raise PatchError("90004 分支没有以 return self._cn_send_envelope(...) 结尾")


def branch_code(ind):
    """新的 90004 分支（缩进跟随原分支）。"""
    pad = ind
    body = [
        "if num == 90004:",
        "    from datetime import datetime as _d9",
        "    import uuid as _uuid9",
        "    _n9 = _d9.now()",
        "    _t9 = int((_n9 - _d9(1, 1, 1)).total_seconds()) * 10_000_000 + _n9.microsecond * 10",
        "    _sk9 = getattr(SESSION, 'session_key', None)",
        "    if not isinstance(_sk9, dict):",
        "        _sk9 = {}",
        "    _sk9 = {'AccountServerId': _sk9.get('AccountServerId')",
        "                          or getattr(SESSION, 'account_id', 0) or 0,",
        "            'MxToken': _sk9.get('MxToken') or ''}",
        "    _rid9 = pick_requestid(rec) or str(_uuid9.uuid4())",
        "    if not rec.get('requestid_source'):",
        "        rec['requestid_source'] = 'random'",
        "    obj = build_90004_management_data(_sk9, _t9, _rid9, load_90004_ops())",
        "    rec['gen_kind'] = 'management-90004-official'",
        "    rec['fallback'] = 'generic-envelope'",
        "    rec['gen_90004_data_keys'] = len(obj.get('Data') or {})",
        "    rec['gen_90004_bytes'] = len(json.dumps(obj, ensure_ascii=False,",
        "                                                separators=(',', ':')))",
        "    _r9 = data_key_report(obj)",
        "    rec['gen_90004_lists'] = dict((k, _r9[k]) for k in (",
        "        'Notices', 'Events', 'Issues', 'Banners',",
        "        'GachaProbabilityDisplay', 'GuidePopup'))",
        "    return self._cn_send_envelope(name or 'Management_Data', obj, rec)",
    ]
    return "\n".join(pad + ln if ln else ln for ln in body)


class PatchError(Exception):
    pass


# ================================================================ 打补丁 / 拆补丁
def detect_nl(text):
    return "\r\n" if "\r\n" in text else "\n"


def apply_patch(text, with_outer_rid=True):
    """→ (new_text, report)。幂等：marker 已在就不再动。"""
    nl = detect_nl(text)
    rep = {"inlined": False, "branch": False, "outer_rid": False, "already": False}

    if BEGIN in text:
        rep["already"] = True
        if not (END in text):
            raise PatchError("有 BEGIN 标记但没有 END，文件可能被手工改坏")
    else:
        start, end, ind, old = find_branch(text)
        rep["legacy_branch_len"] = len(old.split("\n"))
        rep["legacy_keys"] = len(re.findall(r'"[A-Za-z0-9_]+"\s*:', old))
        new_text = text[:start] + branch_code(ind) + text[end:]
        rep["branch"] = True
        # 内联块插到第一个顶层 def 之前
        m = re.search(r"^def ", new_text, re.M)
        if not m:
            raise PatchError("找不到顶层 def 作为内联块的插入锚点")
        blk = block_text(nl)
        new_text = new_text[:m.start()] + blk + nl + new_text[m.start():]
        rep["inlined"] = True
        text = new_text

    if with_outer_rid:
        if RID_TAG in text:
            rep["outer_rid"] = "already"
        else:
            m = re.search(r"^([ \t]*)def _cn_send_envelope\(", text, re.M)
            if not m:
                rep["outer_rid"] = "skip(no function)"
            else:
                find = len(m.group(1))
                # 函数体结束 = 下一个缩进 <= 该函数、且非空的行
                cur = text.find("\n", m.end()) + 1
                seg_end = len(text)
                while cur < len(text):
                    eol = text.find("\n", cur)
                    eol = len(text) if eol < 0 else eol
                    line = text[cur:eol]
                    if line.strip() and (len(line) - len(line.lstrip())) <= find:
                        seg_end = cur
                        break
                    cur = eol + 1
                seg = text[m.start():seg_end]
                mr = RE_RID.search(seg)
                if not mr:
                    rep["outer_rid"] = "skip(no rid line)"
                else:
                    new_line = (mr.group(1)
                                + "rid = (obj.get('RequestId') if isinstance(obj, dict) else '')"
                                  " or str(_uuid.uuid4())  " + RID_TAG)
                    text = text[:m.start()] + seg[:mr.start()] + new_line + seg[mr.end():] \
                        + text[seg_end:]
                    rep["outer_rid"] = True
    return text, rep


# ================================================================ 校验
def verify_text(text, verbose=True):
    """→ (ok, details)。四件事：能编译 / marker 唯一 / 旧 16 键没了 / 内联块真能过 spec。"""
    ok = True
    det = {}

    def fail(msg):
        nonlocal ok
        ok = False
        det.setdefault("errors", []).append(msg)

    # 1 编译
    try:
        compile(text, "<patched>", "exec")
        det["compile"] = "PASS"
    except SyntaxError as e:
        fail("语法错误: %s (line %s)" % (e.msg, e.lineno))
        det["compile"] = "FAIL"
        return ok, det

    # 2 marker
    nb, ne = text.count(BEGIN), text.count(END)
    det["markers"] = "%d/%d" % (nb, ne)
    if nb != 1 or ne != 1:
        fail("marker 数量不对 BEGIN=%d END=%d（应各 1）" % (nb, ne))

    # 3 分支内容
    try:
        start, end, ind, block = find_branch(text)
        det["branch_calls_helper"] = "build_90004_management_data(" in block
        det["branch_has_data"] = "'Data'" in block or '"Data"' in block
        if not det["branch_calls_helper"]:
            fail("90004 分支没有调用 build_90004_management_data")
        if "GuidePopup\": {}" in block or '"GachaProbabilityDisplay": False' in block \
                or '"GachaProbabilityDisplay":False' in block:
            fail("90004 分支里还有旧的错类型键（False / {}）")
        if "return self._cn_send_envelope(name or 'Management_Data', obj, rec)" not in block:
            fail("90004 分支没有用 obj 调用 _cn_send_envelope")
        det["legacy_16key"] = "gone" if not re.search(r'"StaticOpenConditions"', block) else "STILL THERE"
        if re.search(r'"StaticOpenConditions"', block):
            fail("90004 分支里还有 StaticOpenConditions（旧 16 键平铺的残留）")
    except PatchError as e:
        fail(str(e))

    # 4.b 静态名字检查：分支里引用的名字必须能在模块层找到（防「线上版本不同 → NameError」）
    try:
        start, end, ind, block = find_branch(text)
        tree = ast.parse(text)
        mod_names = set(dir(__builtins__)) | {"True", "False", "None"}
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                mod_names.add(node.name)
            elif isinstance(node, ast.Assign):
                for t in node.targets:
                    for n in ast.walk(t):
                        if isinstance(n, ast.Name):
                            mod_names.add(n.id)
            elif isinstance(node, ast.Import):
                for a in node.names:
                    mod_names.add((a.asname or a.name).split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                for a in node.names:
                    mod_names.add(a.asname or a.name)
        btree = ast.parse("\n".join(l[len(ind):] for l in block.split("\n")))
        local = set()
        for n in ast.walk(btree):
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
                local.add(n.id)
            if isinstance(n, (ast.FunctionDef, ast.ClassDef)):
                local.add(n.name)
            if isinstance(n, ast.Import):
                for a in n.names:
                    local.add((a.asname or a.name).split(".")[0])
            if isinstance(n, ast.ImportFrom):
                for a in n.names:
                    local.add(a.asname or a.name)
        used = set()
        for n in ast.walk(btree):
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
                used.add(n.id)
        unknown = sorted(used - mod_names - local - {"self", "num", "name", "rec"})
        det["branch_names_resolved"] = "PASS" if not unknown else ("FAIL: %r" % (unknown,))
        if unknown:
            fail("90004 分支引用了模块层不存在/未导入的名字: %r" % (unknown,))
    except PatchError as e:
        fail(str(e))
    except SyntaxError as e:
        fail("分支静态分析失败: %s" % e)

    # 4 内联块单独 exec → 过 official_spec
    if nb == 1 and ne == 1:
        i = text.find(BEGIN)
        j = text.find(END)
        blk = text[text.find("\n", i) + 1:j]
        ns = {"__name__": "inlined_90004_check"}
        try:
            exec(compile(blk, "<inline>", "exec"), ns)
            fn = ns.get("build_90004_management_data")
            if not fn:
                fail("内联块里没有 build_90004_management_data")
            else:
                obj = fn({"AccountServerId": 99990000001, "MxToken": "A" * 64},
                         639304002554622705, "00000000-0000-4000-8000-000000000000")
                fails, warns, entry = G.check(90004, obj)
                det["inline_spec_check"] = "PASS" if not fails else "FAIL"
                det["inline_data_keys"] = len(obj.get("Data") or {})
                det["inline_inner_bytes"] = G.inner_bytes(obj)
                if fails:
                    fail("内联块的输出过不了 spec_check: %s"
                         % [(k, p) for k, p, _ in fails[:5]])
                # 脏运营数据不能打坏结构
                dirty = {"Notices": [{"NoticeId": "12", "Title": 99, "Extra": 1}],
                         "Banners": [{"BannerId": 1}],
                         "GachaProbabilityDisplay": "not-a-list"}
                obj2 = fn({"AccountServerId": 1, "MxToken": "B" * 64}, 1, "r", dirty)
                fails2, _, _ = G.check(90004, obj2)
                det["inline_dirty_input"] = "PASS" if not fails2 else "FAIL"
                if fails2:
                    fail("脏运营数据打坏了结构: %s" % [(k, p) for k, p, _ in fails2[:5]])
        except Exception as e:
            fail("内联块 exec 失败: %r" % (e,))
            det["inline_exec"] = "FAIL"

    # 5 outer requestid 联动
    det["outer_requestid"] = "synced" if RID_TAG in text else "未同步(可选)"

    if verbose:
        for k in ("compile", "markers", "legacy_16key", "branch_calls_helper",
                  "branch_has_data", "branch_names_resolved", "inline_spec_check",
                  "inline_data_keys", "inline_inner_bytes", "inline_dirty_input",
                  "outer_requestid"):
            if k in det:
                print("  %-22s: %s" % (k, det[k]))
        for e in det.get("errors", []):
            print("  !! %s" % e)
    return ok, det


# ================================================================ 文件操作
def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def read(path):
    with open(path, "r", encoding="utf-8", errors="strict", newline="") as fh:
        return fh.read()


def write(path, text):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def backup(path):
    ts = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    dst = "%s.bak.90004.%s" % (path, ts)
    shutil.copy2(path, dst)
    return dst


def list_backups(path):
    d = os.path.dirname(os.path.abspath(path))
    base = os.path.basename(path) + ".bak.90004."
    out = []
    for f in os.listdir(d):
        if f.startswith(base):
            p = os.path.join(d, f)
            out.append((os.path.getmtime(p), p))
    return [p for _m, p in sorted(out)]


def show_diff(a, b, label="diff"):
    la = a.splitlines(True)
    lb = b.splitlines(True)
    diff = list(difflib.unified_diff(la, lb, fromfile="before", tofile="after", n=3))
    if not diff:
        print("（无差异）")
        return
    print("".join(diff[:400]))
    if len(diff) > 400:
        print("... diff 还有 %d 行" % (len(diff) - 400))


# ================================================================ 端到端（stub 掉加密层）
class _SelfTestError(Exception):
    pass


def _install_stub_modules():
    """bridge 顶部会 import cn_cipher / cn_wire / cn_inner / cn_inner27 / cn_nick。

    本地没有这几个线上模块，用最小 stub 顶替：只覆盖 90004 分支 + _cn_send_envelope 用到的东西。
    stub 只是让代码能跑起来，不参与任何判断。
    """
    import types
    made = []
    if "cn_wire" not in sys.modules:
        m = types.ModuleType("cn_wire")

        def wrap_response(proto_name, obj, requestid=None, **kw):
            plain = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
            return (b"WIRE:" + plain.encode("utf-8")), plain, b"0" * 32
        m.wrap_response = wrap_response
        m.wrap_raw = lambda plaintext: (b"WIRE:", plaintext, b"0" * 32)
        m.unwrap_response = lambda raw: ({}, {}, b"", "")
        sys.modules["cn_wire"] = m
        made.append("cn_wire")
    for name in ("cn_cipher", "cn_inner", "cn_inner27", "cn_nick"):
        if name not in sys.modules:
            m = types.ModuleType(name)
            m.STATIC_OPEN_CONDITIONS = {}
            sys.modules[name] = m
            made.append(name)
    return made


def e2e_patched(path):
    """真跑一遍打补丁后的 bridge 文件里的 90004 分支（不联网、不发 HTTP）。

    做法：把 patched 源码 exec 到独立命名空间（stub 掉 cn_* 模块），
    然后用一个假 self 调 Handler._generic_protocol_response，
    截获传给 _cn_send_envelope 的 obj，用官方 spec 校验。
    """
    _install_stub_modules()
    text = read(path)
    ns = {"__name__": "patched_bridge_e2e", "__file__": path}
    try:
        exec(compile(text, path, "exec"), ns)
    except Exception as e:
        print("  !! exec patched 源码失败: %r" % (e,))
        return False
    H = ns.get("Handler")
    if H is None:
        print("  !! 找不到 class Handler")
        return False
    gen = getattr(H, "_generic_protocol_response", None)
    if gen is None:
        print("  !! Handler 没有 _generic_protocol_response")
        return False

    captured = {}

    class Fake(object):
        """只提供 90004 分支用到的两个方法。"""
        def _cn_decode_any(self, packet_b64, proto_str):
            return '{"Hash": %d}' % (90004 << 32)     # num = Hash>>32 = 90004

        def _cn_send_envelope(self, proto_name, obj, rec):
            rec['proto_name'] = proto_name
            captured['obj'] = obj
            captured['rec'] = rec
            return 200, b"<stub-wire>", "text/plain"

    fake = Fake()
    rec = {"req_Hash": 90004 << 32}
    # 分支会读 SESSION.session_key，先塞一个真值
    sess = ns.get("SESSION")
    if sess is not None and not getattr(sess, "session_key", None):
        sess.session_key = {"AccountServerId": 10015354380, "MxToken": "T" * 64}
        sess.account_id = 10015354380
    try:
        gen(fake, "Management_Data", "stub-packet", rec, "Management_Data")
    except Exception as e:
        import traceback
        print("  !! 跑 90004 分支抛异常: %r" % (e,))
        traceback.print_exc()
        return False

    obj = captured.get("obj")
    if not isinstance(obj, dict):
        print("  !! 分支没有产出 obj")
        return False
    fails, warns, _ = G.check(90004, obj)
    ib = G.inner_bytes(obj)
    print("  e2e gen_kind          : %s" % rec.get("gen_kind"))
    print("  e2e rec keys          : data_keys=%s bytes=%s lists=%s"
          % (rec.get("gen_90004_data_keys"), rec.get("gen_90004_bytes"),
             json.dumps(rec.get("gen_90004_lists"), ensure_ascii=False)))
    print("  e2e 顶层键            : %s" % list(obj.keys()))
    print("  e2e Data 键           : %s" % list((obj.get("Data") or {}).keys()))
    print("  e2e 紧凑包体          : %d bytes" % ib)
    print("  e2e spec_check        : %s (FAIL %d / WARN %d)"
          % ("PASS" if not fails else "FAIL", len(fails), len(warns)))
    ok = not fails
    # Data 外壳必须真的在，且三个 null 是 null、两个 list 是 list
    d = obj.get("Data")
    checks = {
        "Data 是 dict": isinstance(d, dict),
        "Data 9 键": isinstance(d, dict) and len(d) == 9,
        "GachaProbabilityDisplay 是 list": isinstance((d or {}).get("GachaProbabilityDisplay"), list),
        "GuidePopup 是 list": isinstance((d or {}).get("GuidePopup"), list),
        "GachaPeriodDisplay is null": (d or {}).get("GachaPeriodDisplay", "x") is None,
        "RaidPeriodDisplay is null": (d or {}).get("RaidPeriodDisplay", "x") is None,
        "Survey is null": (d or {}).get("Survey", "x") is None,
        "SessionKey 有值": isinstance(obj.get("SessionKey"), dict)
                            and obj["SessionKey"].get("AccountServerId") == 10015354380,
        "RequestId 非空": isinstance(obj.get("RequestId"), str) and len(obj["RequestId"]) >= 32,
        # 官方有、我们旧实现多出来的 11 个键，一个都不能出现在顶层或 Data 里
        "无 Maintenance 等 11 个多余额外键": not (set(obj) | set(d or {})) & {
            "Maintenance", "ServerStatus", "LatestClientVersion", "LatestAndroidClientVersion",
            "LatestIosClientVersion", "LatestPCClientVersion", "MarketAppleId",
            "NotificationBeforeMaintenance", "ContentLock", "DownloadLimitTime", "EnableSQLite"},
    }
    for k, v in checks.items():
        print("  e2e %-30s: %s" % (k, "OK" if v else "FAIL"))
        ok = ok and v

    # outer requestid 联动：真跑一次 _cn_send_envelope，看它传出去的 requestid 是不是 obj['RequestId']
    import types
    seen = {}

    def _capture_wrap(proto_name, obj_, requestid=None, **kw):
        seen["rid"] = requestid
        return b"WIRE", json.dumps(obj_, ensure_ascii=False), b"0" * 32
    sys.modules["cn_wire"].wrap_response = _capture_wrap
    real_send = getattr(H, "_cn_send_envelope", None)
    if real_send is not None:
        try:
            real_send(Fake(), "Management_Data", obj, {})
            rid_ok = seen.get("rid") == obj.get("RequestId")
            print("  e2e %-30s: %s (rid=%s… / RequestId=%s…)"
                  % ("outer requestid == inner", "OK" if rid_ok else "FAIL",
                     str(seen.get("rid"))[:8], str(obj.get("RequestId"))[:8]))
            ok = ok and rid_ok
        except Exception as e:
            print("  e2e %-30s: FAIL (%r)" % ("outer requestid == inner", e))
            ok = False
    return ok


# ================================================================ main
def main(argv=None):
    ap = argparse.ArgumentParser(description="修 90004 Management_Data 的 Data 外壳")
    ap.add_argument("--src", default=SANDBOX,
                    help="要打补丁的 account_auth_probe.py（默认沙箱副本 %s）" % SANDBOX)
    ap.add_argument("--seed", action="store_true",
                    help="把 _bridge_ref/account_auth_probe.py 复制到沙箱（不覆盖已存在文件，除非 --force）")
    ap.add_argument("--force", action="store_true", help="--seed 时覆盖")
    ap.add_argument("--apply", action="store_true", help="备份 + 写入 + 自动 verify")
    ap.add_argument("--dry-run", action="store_true", help="只打印 diff，不写")
    ap.add_argument("--verify", action="store_true", help="校验（可单独跑）")
    ap.add_argument("--e2e", action="store_true",
                    help="把打补丁后的 bridge 真的跑一遍 90004 分支（stub 掉加密层，不联网）")
    ap.add_argument("--rollback", action="store_true", help="回到最近的 .bak.90004.* 备份")
    ap.add_argument("--list-backups", action="store_true", help="列出备份")
    ap.add_argument("--no-sync-outer-requestid", action="store_true",
                    help="不联动 _cn_send_envelope 的 outer requestid（默认联动）")
    args = ap.parse_args(argv)

    if args.seed:
        if not os.path.isfile(REF_SRC):
            print("找不到参考实现: %s" % REF_SRC)
            return 2
        os.makedirs(os.path.dirname(SANDBOX), exist_ok=True)
        if os.path.exists(SANDBOX) and not args.force:
            print("沙箱已有副本，未覆盖: %s（要覆盖加 --force）" % SANDBOX)
        else:
            shutil.copy2(REF_SRC, SANDBOX)
            print("已复制: %s → %s" % (REF_SRC, SANDBOX))
        print("sha256[:16] = %s" % sha(read(SANDBOX)))
        return 0

    src = args.src
    if not os.path.isfile(src):
        print("找不到目标文件: %s" % src)
        print("先 --seed（从 _bridge_ref 复制沙箱副本），或用 --src 指定线上拉回的基线")
        return 2

    if args.list_backups:
        bs = list_backups(src)
        print("备份（%d）:" % len(bs))
        for b in bs:
            print("  %s  %d bytes" % (b, os.path.getsize(b)))
        return 0

    if args.rollback:
        bs = list_backups(src)
        if not bs:
            print("没有备份可回滚: %s.bak.90004.*" % src)
            return 2
        newest = bs[-1]
        cur = read(src)
        shutil.copy2(newest, src) if False else write(src, read(newest))
        print("已回滚: %s ← %s" % (src, newest))
        print("sha256[:16]  %s → %s" % (sha(cur), sha(read(src))))
        ok, _ = verify_text(read(src), verbose=False)
        print("回滚后校验（期望失败，因为补丁已被撤掉）: %s" % ("PASS" if ok else "未打补丁"))
        return 0

    text = read(src)
    print("目标文件: %s" % src)
    print("sha256[:16] = %s  %d bytes" % (sha(text), len(text.encode("utf-8"))))

    if args.verify and not (args.apply or args.dry_run):
        print("=" * 72)
        print("校验（%s）" % ("已打补丁" if BEGIN in text else "未打补丁"))
        ok, _ = verify_text(text)
        print("结果: %s" % ("PASS" if ok else "FAIL"))
        return 0 if ok else 1

    if args.e2e:
        print("=" * 72)
        print("端到端：跑 patched bridge 的 90004 分支（stub 掉 cn_* 加密层，不联网）")
        if BEGIN not in text:
            print("  !! 文件还没打补丁，先 --apply")
            return 1
        ok = e2e_patched(src)
        print("结果: %s" % ("PASS" if ok else "FAIL"))
        return 0 if ok else 1

    try:
        new_text, rep = apply_patch(text, with_outer_rid=not args.no_sync_outer_requestid)
    except PatchError as e:
        print("打补丁失败: %s" % e)
        return 3

    print("=" * 72)
    print("补丁动作: %s" % json.dumps(rep, ensure_ascii=False))
    if rep.get("already") and not (rep["outer_rid"] is True):
        print("已经是打过补丁的版本（幂等，无改动）")
        ok, _ = verify_text(text)
        return 0 if ok else 1

    if args.dry_run:
        print("=" * 72)
        show_diff(text, new_text)
        print("（--dry-run：未写盘）")
        return 0

    if not args.apply:
        print("没有指定动作。用 --apply / --dry-run / --verify / --rollback 之一。")
        return 2

    # 先校验候选内容，验证不过不落盘
    print("候选内容预校验:")
    ok, det = verify_text(new_text)
    if not ok:
        print("候选内容校验 FAIL，拒绝写入（原文件未改）")
        return 4

    bak = backup(src)
    write(src, new_text)
    print("=" * 72)
    print("已备份: %s" % bak)
    print("已写入: %s" % src)
    print("sha256[:16]  %s → %s" % (sha(text), sha(read(src))))
    print("写入后复校验:")
    ok2, _ = verify_text(read(src))
    print("结果: %s" % ("PASS" if ok2 else "FAIL"))
    if ok2:
        print("-" * 72)
        print("上线前只剩三件事：")
        print("  1) 把本文件 scp 到 /www/wwwroot/bapatch/tools/account_auth_probe.py")
        print("  2) 重启 bridge 进程")
        print("  3) 让客户端再发 90004，日志里看 gen_kind=management-90004-official / gen_90004_data_keys=9")
        print("回滚：python %s --src <线上路径> --rollback" % os.path.basename(__file__))
    return 0 if ok2 else 1


if __name__ == "__main__":
    sys.exit(main())
