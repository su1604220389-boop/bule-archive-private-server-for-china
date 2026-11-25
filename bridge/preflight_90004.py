#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""preflight_90004.py — 打补丁**之前**对线上 bridge 做锚点体检（只读，不改文件）。

    python3 preflight_90004.py --file /www/wwwroot/bapatch/tools/account_auth_probe.py

为什么要它：本地快照与线上真身可能不是同一版（本次就差了 ~61 KB：快照 161,194 B，
线上按 ITEMLIST_RELAY_V2.md 是 222,539 B）。patch_90004.py 只在「候选内容校验通过」时
才写盘，但它的 --dry-run 不看锚点；这个脚本先把「能不能打」说清楚，避免 srv-ops 在
线上文件上试错。

判定：
  READY    = 还没打补丁，且 5 个锚点齐全 → 可以跑 patch_90004.py --apply
  PATCHED  = 已经有 90004-PATCH marker（幂等，无需再打）
  BLOCKED  = 锚点缺失 / 分支形状不认识 → **不要打**，把输出发回来

退出码：0 READY / 10 PATCHED / 2 BLOCKED
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys

BEGIN = "# ==== BEGIN 90004-PATCH v1"
END = "# ==== END 90004-PATCH v1"
RE_BRANCH = re.compile(r"^([ \t]*)if num == 90004:[ \t]*$", re.M)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    a = ap.parse_args(argv)
    p = os.path.abspath(a.file)
    raw = open(p, "rb").read()
    text = raw.decode("utf-8")

    print("file   : %s" % p)
    print("size   : %d bytes" % len(raw))
    print("sha256 : %s" % hashlib.sha256(raw).hexdigest())
    print("md5    : %s" % hashlib.md5(raw).hexdigest())

    checks = []

    def chk(name, cond, detail=""):
        checks.append((name, bool(cond), detail))
        print("  %-42s %s %s" % (name, "OK  " if cond else "MISS", detail))
        return cond

    print("\nanchors:")
    m = RE_BRANCH.search(text)
    chk("90004 branch  `if num == 90004:`", bool(m),
        "line %d" % (text[:m.start()].count("\n") + 1) if m else "")

    branch = ""
    if m:
        e = text.find("return self._cn_send_envelope(name or 'Management_Data', obj, rec)",
                      m.start())
        e = text.find("\n", e) if e >= 0 else m.start() + 4000
        branch = text[m.start():e if e > 0 else m.start() + 4000]
        n_keys = len(re.findall(r'"[A-Za-z0-9_]+"\s*:', branch))
        print("      branch: %d lines / %d quoted keys / has Data=%s" % (
            branch.count("\n") + 1, n_keys, '"Data"' in branch))
        chk("branch 以 _cn_send_envelope 收尾",
            "return self._cn_send_envelope(name or 'Management_Data', obj, rec)" in branch)

    chk("def _cn_send_envelope(", "def _cn_send_envelope(" in text)
    rid_in_send = False
    ms = re.search(r"^([ \t]*)def _cn_send_envelope\(", text, re.M)
    if ms:
        ind = len(ms.group(1))
        cur = text.find("\n", ms.end()) + 1
        seg_end = len(text)
        while cur < len(text):
            eol = text.find("\n", cur)
            eol = len(text) if eol < 0 else eol
            line = text[cur:eol]
            if line.strip() and (len(line) - len(line.lstrip())) <= ind:
                seg_end = cur
                break
            cur = eol + 1
        rid_in_send = bool(re.search(r"^[ \t]*rid = str\(_uuid\.uuid4\(\)\)[ \t]*$",
                                     text[ms.start():seg_end], re.M))
    chk("`rid = str(_uuid.uuid4())` 在 _cn_send_envelope 内", rid_in_send)
    chk("pick_requestid(rec)", "def pick_requestid(rec)" in text)
    chk("SESSION = Session()", bool(re.search(r"^SESSION = Session\(\)", text, re.M)))
    chk("import json", bool(re.search(r"^import json", text, re.M)))

    nb, ne = text.count(BEGIN), text.count(END)
    print("\nmarkers: BEGIN=%d END=%d" % (nb, ne))

    if nb == 1 and ne == 1:
        print("\nVERDICT: PATCHED —— 已打过 90004-PATCH v1（幂等），不需要再打")
        return 10
    if nb or ne:
        print("\nVERDICT: BLOCKED —— marker 只有一半（BEGIN=%d/END=%d），文件可能被手工改坏" % (nb, ne))
        return 2
    if all(ok for _n, ok, _d in checks):
        if m and branch:
            print("\nVERDICT: READY —— 5 个锚点齐全，可以 `patch_90004.py --src <本文件副本> --apply`")
            return 0
    print("\nVERDICT: BLOCKED —— 有锚点缺失，**不要打**；把上面输出发回来，"
          "让本地按这一版重做补丁（dto90004.py 里没有跟版本相关的逻辑，通常只是插入点变了）")
    return 2


if __name__ == "__main__":
    sys.exit(main())
