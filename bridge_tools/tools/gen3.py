#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen3.py — 生成 protocol 3 NetworkTime_Sync 响应并跑 spec_check。

    python work\\ba\\server\\deploy\\gen3.py --out report\\_tmp\t3.json
    python work\\ba\\proto\\spec_check.py --protocol 3 --file report\\_tmp\t3.json

DTO 是反推的（dto_schema_full_v2.json 里没有 NetworkTimeSyncResponse）：
    work\\ba\\proto\\dto_extra\\proto3_networktime.json

取值规则（有抓包证据）：官方 ReceiveTick == EchoSendTick == 收到请求那一刻的 .NET ticks，
且请求 DTO (`NetworkTimeSyncRequest`) **没有任何字段** ⇒ 服务端无可回显的客户端 tick，
两个字段都填接收时刻即可逐字节复现官方行为（--verify-official 会验证这一点）。
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_common as G                                   # noqa: E402

DEFAULT_OUT = os.path.join(G.ROOT, "report", "_tmp", "t3.json")


def build_3(account, recv_tick=None, echo_tick=None, recv_offset_us=0):
    ticks = recv_tick if recv_tick is not None else account.ticks + int(recv_offset_us) * 10
    obj = account.envelope(3)
    obj["ReceiveTick"] = int(ticks)
    obj["EchoSendTick"] = int(echo_tick if echo_tick is not None else ticks)
    return G.order_like_spec(obj, 3)


def build(args):
    if args.official:
        return G.official_inner(3)
    acct = G.account_from_args(args)
    obj = build_3(acct, recv_tick=args.recv_tick, echo_tick=args.echo_tick,
                  recv_offset_us=args.recv_offset_us)
    if not args.no_dto_check:
        G.check_against_dto(3, obj, G.load_dto_extra("proto3_networktime.json"))
    return obj


def verify_official(args):
    o = G.official_inner(3)
    acct = G.Account(o["SessionKey"]["AccountServerId"], o["SessionKey"]["MxToken"],
                     o["RequestId"], G.dt_from_ticks(o["ServerTimeTicks"]),
                     ticks=o["ServerTimeTicks"])
    rebuilt = build_3(acct, recv_tick=o["ReceiveTick"], echo_tick=o["EchoSendTick"])
    print("=" * 72)
    print("官方回灌验证（SessionKey/RequestId/两个 tick 全部取自 04_3 抓包）")
    ok = G.verify_official_bytes(3, rebuilt)
    fails, warns, _ = G.check(3, rebuilt)
    print("官方回灌物 spec_check : %s (FAIL %d / WARN %d)"
          % ("PASS" if not fails else "FAIL", len(fails), len(warns)))
    # 语义断言：官方两个 tick 必须相等（这是 gen3 默认行为的前提）
    print("语义断言        : ReceiveTick == EchoSendTick ? %s"
          % ("YES" if o["ReceiveTick"] == o["EchoSendTick"] else "NO"))
    return ok and not fails and o["ReceiveTick"] == o["EchoSendTick"]


def main(argv=None):
    ap = argparse.ArgumentParser(description="生成并验收 protocol 3 NetworkTime_Sync")
    G.add_common_args(ap, DEFAULT_OUT)
    ap.add_argument("--recv-tick", type=int, default=None,
                    help="ReceiveTick（.NET ticks），不传 = 现在的 ticks")
    ap.add_argument("--echo-tick", type=int, default=None,
                    help="EchoSendTick，不传 = 与 ReceiveTick 相同")
    ap.add_argument("--recv-offset-us", type=int, default=0,
                    help="ReceiveTick 相对 ServerTimeTicks 的微秒偏移（默认 0）")
    ap.add_argument("--official", action="store_true", help="直接输出官方抓包包体（结构基准）")
    ap.add_argument("--verify-official", action="store_true", help="官方输入回灌 + 逐字节比对")
    args = ap.parse_args(argv)

    if args.verify_official:
        return 0 if verify_official(args) else 1

    obj = build(args)
    size = G.write_json(obj, args.out, pretty=not args.compact, wrap=args.wrap)
    extra = {
        "ReceiveTick": obj["ReceiveTick"],
        "EchoSendTick": obj["EchoSendTick"],
        "tick 差(ticks)": obj["ReceiveTick"] - obj["ServerTimeTicks"],
        "落盘": "%d bytes" % size,
    }
    ok = G.print_verdict(3, obj, args.out, extra=extra)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
