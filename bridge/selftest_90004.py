#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""selftest_90004.py — 证明「ops 文件 + dto90004」复现官方 Data 逐字节一致。

    python work/ba/server/deploy/_p90004/selftest_90004.py

三件事：
  1 dto90004.build_90004_management_data(ops=90004_ops.json) 的 Data
    与官方 06_90004 `inner.Data` 的紧凑 JSON **逐字节相等**；
  2 打补丁后 bridge 里**内联的那份** helper 输出与 dto90004.py 的输出完全一致
    （证明「本地验收的代码 == 线上跑的代码」）；
  3 两个输出都过 work/ba/proto/spec_check.py（FAIL=0）。

只读；找不到文件就报错退出，不伪造结果。
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEPLOY = os.path.dirname(HERE)
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))

sys.path.insert(0, DEPLOY)
import dto90004 as D  # noqa: E402

BRIDGE = os.path.join(HERE, "account_auth_probe.py")
OPS = os.path.join(HERE, "90004_ops.json")
OFFICIAL = os.path.join(ROOT, "report", "_tmp", "official_decoded_201",
                        "06_90004_api_management_data.response.json")
BEGIN = "# ==== BEGIN 90004-PATCH v1"
END = "# ==== END 90004-PATCH v1"


def compact(o):
    return json.dumps(o, ensure_ascii=False, separators=(",", ":"))


def sha(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def load_inlined_helper():
    """把 patched bridge 里 marker 之间的内联块单独 exec 出来。"""
    text = open(BRIDGE, "r", encoding="utf-8").read()
    i, j = text.find(BEGIN), text.find(END)
    if i < 0 or j < 0:
        raise RuntimeError("bridge 里找不到 90004-PATCH marker")
    blk = text[text.find("\n", i) + 1:j]
    ns = {"__name__": "inlined_90004"}
    exec(compile(blk, "<inlined>", "exec"), ns)
    return ns


def main():
    ok = True
    official = json.load(open(OFFICIAL, "r", encoding="utf-8"))["inner"]
    off_data = official["Data"]
    ops = json.load(open(OPS, "r", encoding="utf-8"))

    a = D.build_90004_management_data(
        {"AccountServerId": 10015354380, "MxToken": "A" * 64},
        official["ServerTimeTicks"], official["RequestId"], ops)
    ns = load_inlined_helper()
    b = ns["build_90004_management_data"](
        {"AccountServerId": 10015354380, "MxToken": "A" * 64},
        official["ServerTimeTicks"], official["RequestId"], ops)

    print("== 1) dto + ops  vs  官方 inner.Data（紧凑 JSON 逐字节）")
    eq = compact(a["Data"]) == compact(off_data)
    print("   equal            : %s" % eq)
    print("   official bytes   : %d" % len(compact(off_data).encode("utf-8")))
    print("   ours bytes       : %d" % len(compact(a["Data"]).encode("utf-8")))
    print("   official sha256  : %s" % sha(compact(off_data)))
    print("   ours sha256      : %s" % sha(compact(a["Data"])))
    if not eq:
        ok = False
        # 找第一处差异
        x, y = compact(off_data), compact(a["Data"])
        for k in range(min(len(x), len(y))):
            if x[k] != y[k]:
                print("   first diff @%d: official=%r ours=%r" % (k, x[k:k + 60], y[k:k + 60]))
                break
        else:
            print("   first diff: length (%d vs %d)" % (len(x), len(y)))

    print("\n== 2) 内联副本  vs  dto90004.py（同一份字节？）")
    same = compact(a) == compact(b)
    print("   identical        : %s" % same)
    if not same:
        ok = False
    print("   inlined data_keys: %d / lists=%s" % (
        len(b["Data"]), {k: len(b["Data"][k]) for k in
                         ("Notices", "Events", "Issues", "Banners",
                          "GachaProbabilityDisplay", "GuidePopup")}))

    print("\n== 3) spec_check（work/ba/proto/spec_check.py）")
    try:
        import gen_common as G
        fails, warns, _ = G.check(90004, a)
        print("   dto     : FAIL=%d WARN=%d %s" % (len(fails), len(warns),
                                                    "PASS" if not fails else "FAIL"))
        if fails:
            ok = False
            for k, p, d in fails[:5]:
                print("     !! %s %s %s" % (k, p, d))
        fails2, warns2, _ = G.check(90004, b)
        print("   inlined : FAIL=%d WARN=%d %s" % (len(fails2), len(warns2),
                                                    "PASS" if not fails2 else "FAIL"))
        if fails2:
            ok = False
        print("   官方样本: FAIL=%d WARN=%d" % (len(G.check(90004, official)[0]),
                                               len(G.check(90004, official)[1])))
    except Exception as e:
        ok = False
        print("   !! spec_check 跑不起来: %r" % (e,))

    print("\n== 4) 顶层 6 键 / Data 9 键")
    print("   top keys : %s" % list(a))
    print("   data keys: %s" % list(a["Data"]))
    if list(a) != ["Protocol", "SessionKey", "ServerTimeTicks", "ServerNotification",
                   "RequestId", "Data"]:
        ok = False
    if list(a["Data"]) != list(D.P90004_DATA_KEYS):
        ok = False

    print("\nRESULT: %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
