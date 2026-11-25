#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_patch_90004.py — 对 _p90004/account_auth_probe.py 做三项静态检查并打印结果。

    python work/ba/server/deploy/_p90004/check_patch_90004.py [--file <path>] [--pre <打补丁前备份>]

检查：
  A 语法（ast.parse + py_compile）
  B 幂等（marker 各 1 份；patch_90004.py 靠 marker 判断「已打」，--apply 复跑不改字节）
  C 无残留（**90004 分支内**旧 16 键平铺 stub 的 12 个特征串全为 0；
     全文件 `"Protocol": 90004` 字面量只有 1 处；90004 响应生成点只有 1 处）

注意：`StaticOpenConditions` / `MissionProgressDBs` 这几个键在 **1019 legacy 分支**和
几个 helper 里本来就有（历史代码，见行号），它们不是 90004 的残留 —— 所以检查按
「90004 分支块内」定性，而不是全文件清零。
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import os
import py_compile
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT = os.path.join(HERE, "account_auth_probe.py")

BEGIN = "# ==== BEGIN 90004-PATCH v1"
END = "# ==== END 90004-PATCH v1"

# 旧 16 键平铺 stub 的特征（90004 分支内任一残留 = FAIL）
LEGACY_MARKERS = (
    '"ContentLock"',
    '"StaticOpenConditions"',
    '"MissionProgressDBs"',
    '"EventMissionProgressDBDict"',
    '"BattlePassMissionProgressDBDict"',
    '"GachaProbabilityDisplay": False',
    '"GachaPeriodDisplay": False',
    '"RaidPeriodDisplay": False',
    '"GuidePopup": {}',
    "cn_inner.STATIC_OPEN_CONDITIONS",
    "rec['gen_kind'] = 'management-90004'",
    "build_min_response(90004",
)


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def branch_block(text):
    """→ (start, end, block)；块 = `if num == 90004:` 到其 return 行（含）。"""
    m = re.search(r"^[ \t]*if num == 90004:[ \t]*$", text, re.M)
    if not m:
        return None, None, None
    e = text.find("return self._cn_send_envelope(name or 'Management_Data', obj, rec)",
                  m.start())
    if e < 0:
        e = min(len(text), m.start() + 4000)
    e = text.find("\n", e)
    e = len(text) if e < 0 else e
    return m.start(), e, text[m.start():e]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=DEFAULT)
    ap.add_argument("--pre", default=None, help="打补丁前的备份（对比旧分支 16 键）")
    a = ap.parse_args(argv)
    p = os.path.abspath(a.file)
    text = open(p, "r", encoding="utf-8", errors="strict").read()
    ok = True

    print("file : %s" % p)
    print("size : %d bytes / %d lines / sha256=%s" % (
        len(text.encode("utf-8")), text.count("\n") + 1, sha(text)))

    # ---- A 语法
    print("\n[A] syntax")
    try:
        ast.parse(text, filename=p)
        print("  ast.parse   : PASS")
    except SyntaxError as e:
        ok = False
        print("  ast.parse   : FAIL %s (line %s)" % (e.msg, e.lineno))
    try:
        py_compile.compile(p, cfile=os.path.join(HERE, "_pyc_check.pyc"),
                           doraise=True, quiet=2)
        print("  py_compile  : PASS")
    except Exception as e:
        ok = False
        print("  py_compile  : FAIL %r" % (e,))

    # ---- B 幂等的前置：marker 恰好各 1 份（patch 靠 marker 判断已打）
    print("\n[B] idempotency markers")
    nb, ne = text.count(BEGIN), text.count(END)
    print("  BEGIN marker: %d (expect 1)" % nb)
    print("  END   marker: %d (expect 1)" % ne)
    if nb != 1 or ne != 1:
        ok = False

    # ---- C 无残留（只看 90004 分支块）
    s, e, blk = branch_block(text)
    print("\n[C] 90004 branch block: chars [%s,%s) = %s" % (
        s, e, "FOUND" if blk else "NOT FOUND"))
    if not blk:
        print("  !! 找不到 90004 分支")
        return 1
    for m in LEGACY_MARKERS:
        c = blk.count(m)
        glob = text.count(m)
        flag = "OK" if c == 0 else "FAIL"
        if c:
            ok = False
        note = "" if glob == c else "  (全文件 %d 处，均在其它协议分支/helper)" % glob
        print("  %-4s in-branch=%d  %s%s" % (flag, c, m, note))

    # 90004 响应生成点：只允许 1 处 `if num == 90004:` + 1 处 Protocol 字面量
    print("\n[C2] 90004 dispatch sites (whole file)")
    n_branch = len(re.findall(r"^[ \t]*if num == 90004:[ \t]*$", text, re.M))
    n_build = len(re.findall(r"build_90004_management_data\(", text))
    n_proto = len(re.findall(r'"Protocol":\s*90004', text))
    print("  `if num == 90004:`             : %d (expect 1)" % n_branch)
    print("  `build_90004_management_data(` : %d (expect 2 = def + call)" % n_build)
    print('  `"Protocol": 90004` literal    : %d (expect 1)' % n_proto)
    if n_branch != 1 or n_proto != 1 or n_build != 2:
        ok = False

    has_call = "build_90004_management_data(" in blk
    has_ret = "return self._cn_send_envelope(name or 'Management_Data', obj, rec)" in blk
    has_data = '"Data"' in blk
    print("  branch calls helper            : %s" % has_call)
    print("  branch returns obj             : %s" % has_ret)
    print("  branch mentions Data key       : %s (helper 负责构造)" % has_data)
    ok = ok and has_call and has_ret

    # 旧分支对照（如果给了打补丁前备份）
    if a.pre:
        pre = open(os.path.abspath(a.pre), "r", encoding="utf-8").read()
        _ps, _pe, pblk = branch_block(pre)
        print("\n[C3] before/after 分支对照")
        print("  before: %d 行 / 顶层键 %d 个 / Protocol 字面量 %d 处" % (
            pblk.count("\n") + 1 if pblk else -1,
            len(re.findall(r'"[A-Za-z0-9_]+"\s*:', pblk)) if pblk else -1,
            pblk.count('"Protocol": 90004') if pblk else -1))
        print("  after : %d 行 / Protocol 字面量 %d 处 / 调 helper %s" % (
            blk.count("\n") + 1, blk.count('"Protocol": 90004'), has_call))

    # 所有 90004 相关行（人工复核用：确认剩下的都不是第二套生成逻辑）
    print("\n[C4] all lines mentioning 90004")
    for i, ln in enumerate(text.split("\n"), 1):
        if "90004" in ln:
            print("  %5d| %s" % (i, ln.strip()[:150]))

    print("\nRESULT: %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
