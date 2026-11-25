#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen90004.py — 生成 90004 Management_Data 响应并跑 spec_check。

    python work\\ba\\server\\deploy\\gen90004.py --out report\\_tmp\\t90004.json
    python work\\ba\\proto\\spec_check.py --protocol 90004 --file report\\_tmp\\t90004.json

三种数据口径：
  默认（新号）        4 个运营列表 = []、3 个对象 = null，结构与类型完全按官方
  --ops FILE          用外部运营数据（字段白名单 + 类型强转，脏数据打不坏结构）
  --verify-official   用官方抓包里的输入参数回灌构造器，与官方包体**逐字节**比对
                      （证明键序/键集合/类型/省略规则与官方一致，不是"看着像"）

默认没有 Data 里的运营内容，是**故意**的：ExcelDB 398 表里没有公告/Banner/扭蛋概率公示
（H 线已确认 0 命中）。客户端拿到空列表只是没内容，不会 NRE；NRE 的唯一来源是
`ManagementDataResponse.Data` 为 null。
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dto90004                                          # noqa: E402
import gen_common as G                                   # noqa: E402

# 仓库布局下落在 <repo>/report/_tmp；扁平部署（线上 tools/）没有 report/ 时落到本文件旁 out/
if os.path.isdir(os.path.join(G.ROOT, "report")):
    DEFAULT_OUT = os.path.join(G.ROOT, "report", "_tmp", "t90004.json")
else:
    DEFAULT_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "t90004.json")


def build(args):
    if args.official:
        # 直接回放官方包体（结构基准，不含任何本地推导）
        return G.official_inner(90004)

    acct = G.account_from_args(args)
    ops = dto90004.load_90004_ops(args.ops) if (args.ops or not args.no_ops_file) else None
    obj = dto90004.build_90004_management_data(
        acct.session_key(), acct.ticks, acct.request_id, ops)
    obj = G.order_like_spec(obj, 90004)
    if not args.no_dto_check:
        G.check_against_dto(90004, obj, G.load_dto_extra("proto90004_management.json"))
    return obj


def verify_official(args):
    """用官方输入 → 我们的构造器 → 与官方包体逐字节比。"""
    o = G.official_inner(90004)
    ops = o.get("Data") or {}
    rebuilt = dto90004.build_90004_management_data(
        o["SessionKey"], o["ServerTimeTicks"], o["RequestId"], ops)
    rebuilt = G.order_like_spec(rebuilt, 90004)
    print("=" * 72)
    print("官方回灌验证（输入取 06_90004 抓包的 SessionKey/ServerTimeTicks/RequestId + Data）")
    ok = G.verify_official_bytes(90004, rebuilt)
    fails, warns, _ = G.check(90004, rebuilt)
    print("官方回灌物 spec_check : %s (FAIL %d / WARN %d)"
          % ("PASS" if not fails else "FAIL", len(fails), len(warns)))
    return ok and not fails


def main(argv=None):
    ap = argparse.ArgumentParser(description="生成并验收 90004 Management_Data")
    G.add_common_args(ap, DEFAULT_OUT)
    ap.add_argument("--ops", default=None, help="运营数据 JSON（Notices/Events/Banners/…）")
    ap.add_argument("--no-ops-file", action="store_true",
                    help="不读默认运营数据文件（%s）" % (dto90004.P90004_OPS_PATHS[0],))
    ap.add_argument("--official", action="store_true", help="直接输出官方抓包包体（结构基准）")
    ap.add_argument("--verify-official", action="store_true", help="官方输入回灌 + 逐字节比对")
    args = ap.parse_args(argv)

    if args.verify_official:
        ok = verify_official(args)
        return 0 if ok else 1

    obj = build(args)
    size = G.write_json(obj, args.out, pretty=not args.compact, wrap=args.wrap)
    rep = dto90004.data_key_report(obj)
    extra = {
        "Data 键数": "%d (官方 9)" % rep["data_keys"],
        "列表长度": "Notices=%d Events=%d Issues=%d Banners=%d GachaProb=%d GuidePopup=%d"
                    % (rep["Notices"], rep["Events"], rep["Issues"],
                       rep["Banners"], rep["GachaProbabilityDisplay"], rep["GuidePopup"]),
        "null 三键": ",".join(rep["nulls"]) or "(缺)",
        "落盘": "%d bytes" % size,
    }
    ok = G.print_verdict(90004, obj, args.out, extra=extra)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
