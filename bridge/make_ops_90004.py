#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_ops_90004.py — 从官方 201 抓包里抽出 90004 的 9 键运营数据。

    python work/ba/server/deploy/_p90004/make_ops_90004.py
    python work/ba/server/deploy/_p90004/make_ops_90004.py --src <官方 response.json> --out <输出>

做什么
------
把 `06_90004_api_management_data.response.json` 的 `inner.Data` 里那 9 个键
（Notices / Events / Issues / Banners / GachaProbabilityDisplay / GuidePopup /
GachaPeriodDisplay / RaidPeriodDisplay / Survey）**原样**抽出来写成 `90004_ops.json`，
给 bridge 的 `load_90004_ops()` 读（P90004_OPS_PATHS 第一位）。

保真口径
--------
* 不改写、不翻译、不裁剪，只做 `json.loads` → `json.dumps` 的等价搬运；
* 抽出后立刻做一次「紧凑 JSON 逐字节相等」校验：
  `compact(ours) == compact(official_data)`；只要有一个字符不同就报 FAIL 并不写盘。
* 输出 UTF-8 无 BOM、`\\n` 换行、`ensure_ascii=False`（中文原样）、indent=1。

退出码：0 = 写出且校验全过；1 = 校验失败（不写盘）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
DEFAULT_SRC = os.path.join(ROOT, "report", "_tmp", "official_decoded_201",
                           "06_90004_api_management_data.response.json")
DEFAULT_OUT = os.path.join(HERE, "90004_ops.json")

DATA_KEYS = ("Notices", "Events", "Issues", "Banners", "GachaProbabilityDisplay",
             "GuidePopup", "GachaPeriodDisplay", "RaidPeriodDisplay", "Survey")
EXPECT_LEN = {"Notices": 6, "Events": 14, "Issues": 0, "Banners": 7,
              "GachaProbabilityDisplay": 12, "GuidePopup": 0}
EXPECT_NULL = ("GachaPeriodDisplay", "RaidPeriodDisplay", "Survey")


def compact(o):
    return json.dumps(o, ensure_ascii=False, separators=(",", ":"))


def sha_file(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=DEFAULT_SRC)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--expected", default=os.path.join(HERE, "expected_90004.json"),
                    help="同时写「预期响应」（6 层键；3 个易变字段留占位）")
    ap.add_argument("--no-expected", action="store_true")
    a = ap.parse_args(argv)

    with open(a.src, "r", encoding="utf-8") as fh:
        whole = json.load(fh)
    inner = whole.get("inner") or whole
    src_data = inner.get("Data")
    if not isinstance(src_data, dict):
        print("FAIL: %s 里没有 inner.Data" % a.src)
        return 1

    ok = True
    print("src : %s" % a.src)
    print("      inner keys = %s" % list(inner))
    print("      Data keys  = %s (%d)" % (list(src_data), len(src_data)))
    if tuple(src_data) != DATA_KEYS:
        ok = False
        print("FAIL: Data 键序/键名与官方 9 键模板不一致")

    # 只抽 9 键，保持官方顺序（dict 保序）
    ops = {k: src_data[k] for k in DATA_KEYS if k in src_data}

    print("\n[1] 逐字节保真（紧凑 JSON 对比）")
    same = compact(ops) == compact(src_data)
    print("  compact(extracted) == compact(official inner.Data) : %s" % same)
    ok = ok and same

    print("\n[2] 条数 / 类型")
    for k in DATA_KEYS:
        v = ops.get(k, "<missing>")
        if isinstance(v, list):
            want = EXPECT_LEN.get(k)
            flag = "OK" if (want is None or len(v) == want) else "FAIL"
            if flag == "FAIL":
                ok = False
            print("  %-4s %-24s list  n=%-3d %s" % (
                flag, k, len(v), "" if want is None else "(expect %d)" % want))
        elif v is None:
            flag = "OK" if k in EXPECT_NULL else "FAIL"
            if flag == "FAIL":
                ok = False
            print("  %-4s %-24s null" % (flag, k))
        else:
            ok = False
            print("  FAIL %-24s %r (应为 list/null)" % (k, type(v).__name__))

    if not ok:
        print("\nRESULT: FAIL —— 校验没过，**不写盘**")
        return 1

    # 写出：UTF-8 无 BOM
    out = os.path.abspath(a.out)
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(ops, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    raw = open(out, "rb").read()
    print("\n[3] 写出")
    print("  path   : %s" % out)
    print("  size   : %d bytes" % len(raw))
    print("  bom    : %s" % ("YES(FAIL)" if raw[:3] == b"\xef\xbb\xbf" else "no"))
    print("  sha256 : %s" % hashlib.sha256(raw).hexdigest())

    # 回读校验（落盘后再比一次，防写出时被改写）
    back = json.load(open(out, "r", encoding="utf-8"))
    rt = compact(back) == compact(src_data)
    print("  reread == official : %s" % rt)
    if not rt:
        print("\nRESULT: FAIL")
        return 1

    print("\n条数汇总: " + " ".join(
        "%s=%s" % (k, len(ops[k]) if isinstance(ops[k], list) else "null") for k in DATA_KEYS))

    # ---- 预期响应：官方 6 层键，易变字段留占位
    if not a.no_expected:
        expected = {
            "Protocol": 90004,
            # 占位：真实值是 bridge 的 SESSION.session_key；新号/未登录时就是 {"AccountServerId":0,"MxToken":""}
            "SessionKey": {"AccountServerId": 0, "MxToken": ""},
            "ServerTimeTicks": 0,          # 占位：真实值 = 当前 .NET 100ns ticks
            "ServerNotification": 0,
            "RequestId": "00000000-0000-4000-8000-000000000000",  # 占位：每次请求新 uuid4
            "Data": ops,
        }
        ep = os.path.abspath(a.expected)
        with open(ep, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(expected, fh, ensure_ascii=False, indent=1)
            fh.write("\n")
        eraw = open(ep, "rb").read()
        print("\n[4] 预期响应")
        print("  path   : %s" % ep)
        print("  size   : %d bytes" % len(eraw))
        print("  sha256 : %s" % hashlib.sha256(eraw).hexdigest())
        print("  top    : %s" % list(expected))
        print("  note   : SessionKey/ServerTimeTicks/RequestId 是占位，verify_90004.py 只查类型/合理性")

    print("\nRESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
