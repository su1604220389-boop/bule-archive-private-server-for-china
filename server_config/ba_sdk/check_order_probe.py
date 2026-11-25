#!/usr/bin/env python3
# -*- coding: ascii -*-
"""check_order_probe.py -- decide in one command whether the client really
called the SDK's order endpoints.

This is the gate for the whole fake-payment plan (see CHAIN_AUDIT SDK-12.1):
  ORDER_CREATE_SEEN=YES -> the client does use /order/create -> continue.
  ORDER_CREATE_SEEN=NO  -> it does not -> the SDK route is dead for this
                           build, switch to "grant inside 29000" instead.

Usage (on the server):
    python3 check_order_probe.py --minutes 5
    python3 check_order_probe.py --since 1794918000
    python3 check_order_probe.py --log /root/bapatch/order_probe.log --minutes 5

Exit codes: 0 = seen, 3 = not seen, 2 = log missing/unreadable.
"""
import argparse
import json
import os
import sys
import time


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default="/www/wwwroot/ba_sdk/order_probe.log")
    ap.add_argument("--minutes", type=float, default=5.0)
    ap.add_argument("--since", type=float, default=0.0)
    ap.add_argument("--show", type=int, default=3, help="max sample lines per path")
    a = ap.parse_args()

    if not os.path.isfile(a.log):
        print("LOG_MISSING=%s" % a.log)
        print("VERDICT=UNKNOWN")
        return 2

    now = time.time()
    since = a.since if a.since else now - a.minutes * 60.0

    counts = {}
    samples = {}
    total = 0
    bad = 0
    try:
        with open(a.log) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except Exception:
                    bad += 1
                    continue
                try:
                    ep = float(d.get("epoch") or 0)
                except Exception:
                    ep = 0.0
                if ep and ep < since:
                    continue
                path = str(d.get("path") or "")
                if not path:
                    continue
                total += 1
                counts[path] = counts.get(path, 0) + 1
                if path not in samples:
                    samples[path] = []
                if len(samples[path]) < a.show:
                    body = d.get("body_text")
                    if body is None:
                        body = "<base64:%s>" % (d.get("body_b64") or "")[:40]
                    samples[path].append({
                        "ts": d.get("ts"),
                        "client": d.get("client"),
                        "dev": (d.get("headers", {}) or {}).get("Authorization", "")[:80],
                        "body": str(body)[:200],
                    })
    except Exception as e:
        print("LOG_READ_ERROR=%r" % (e,))
        print("VERDICT=UNKNOWN")
        return 2

    lo = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(since))
    hi = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now))
    print("WINDOW=%s .. %s" % (lo, hi))
    print("LINES_IN_WINDOW=%d  BAD_JSON=%d" % (total, bad))
    if not counts:
        print("NO_ORDER_REQUESTS_IN_WINDOW")
    for path in sorted(counts, key=lambda p: -counts[p]):
        print("  %-28s %d" % (path, counts[path]))
        for s in samples[path]:
            print("      %s client=%s" % (s["ts"], s["client"]))
            print("        auth=%s" % (s["dev"] or "-"))
            print("        body=%s" % s["body"])

    seen = any(p.startswith("/order/create") for p in counts)
    print("ORDER_CREATE_SEEN=%s" % ("YES" if seen else "NO"))
    if seen:
        print("VERDICT=SDK_ORDER_ROUTE_ALIVE")
        return 0
    print("VERDICT=SDK_ORDER_ROUTE_NOT_CALLED")
    print("NEXT=switch to Shittim 29000 direct-grant; stop tuning PayState")
    return 3


if __name__ == "__main__":
    sys.exit(main())
