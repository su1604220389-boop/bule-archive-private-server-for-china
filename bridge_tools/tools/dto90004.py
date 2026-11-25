#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dto90004.py — 90004 Management_Data 的**唯一构造器**（生成器与 bridge 补丁共用）。

两个消费者：
  * work/ba/server/deploy/gen90004.py   本地生成 + spec_check 验收
  * work/ba/server/deploy/patch_90004.py 把本文件正文（本 docstring 之后）**原样内联**进
    account_auth_probe.py 的 90004 分支 —— 所以本文件必须零依赖（只用 json / os），
    且不能引用 gen_common.py。这样「本地验收过的代码」与「线上跑的代码」是同一份字节。

【为什么必须是 Data 外壳】
dto_schema_full_v2.json 里 `ManagementData` 是 **20 个字段**的 DTO，
`ManagementDataResponse.Data` 的类型就是它。官方 201 抓包（06_90004）的 Data 只发出 9 个键：
    Notices / Events / Issues / Banners / GachaProbabilityDisplay / GuidePopup /
    GachaPeriodDisplay(null) / RaidPeriodDisplay(null) / Survey(null)
另外 11 个（Maintenance / ServerStatus / LatestClientVersion / LatestAndroidClientVersion /
LatestIosClientVersion / LatestPCClientVersion / MarketAppleId / NotificationBeforeMaintenance /
ContentLock / DownloadLimitTime / EnableSQLite）在官方包里 **一次都没出现** ——
它们是 null / 0 / 默认值，被序列化层丢掉（Issues / GuidePopup 这类空 list 反而会保留）。

我们 bridge 现在的 16 键平铺 = 3 个信封键 + 4 个 ResponsePacket 继承字段 +
**上面那 9 个 Data 内层键被抬到了信封层**，而且 4 个键类型还写错了
（GachaProbabilityDisplay:false 该是 list、GuidePopup:{} 该是 list、
GachaPeriodDisplay/RaidPeriodDisplay:false 该是 null）。
⇒ 客户端 `ManagementDataResponse.Data = null` → NRE。

【数据来源】Notices / Events / Banners / GachaProbabilityDisplay 是运营数据，
ExcelDB 398 表全扫 0 命中（H 线已确认），新号阶段给空数组，结构/类型仍然正确。
运营数据可后补：把一个 JSON 丢到 OPS_PATHS 里任一位置即可，本模块会做字段白名单 +
类型强转，所以**脏数据也打不坏结构**。
"""

import json
import os

# 官方 Data 的 9 个键，顺序即官方键序（10/10 稳定）
P90004_DATA_KEYS = (
    "Notices", "Events", "Issues", "Banners", "GachaProbabilityDisplay",
    "GuidePopup", "GachaPeriodDisplay", "RaidPeriodDisplay", "Survey",
)

# 三个恒为 null 的对象字段（官方 10/10 显式发 null，不是缺省）
P90004_NULL_KEYS = ("GachaPeriodDisplay", "RaidPeriodDisplay", "Survey")

# 列表型 Data 字段（新号 = 空数组；运营数据后补）
P90004_LIST_KEYS = ("Notices", "Events", "Issues", "Banners",
                    "GachaProbabilityDisplay", "GuidePopup")

# (字段名, 类型, 是否必发)  —— 顺序 = 官方键序（Issues/GuidePopup 官方恒空，元素形状未知）
P90004_NOTICE_FIELDS = (
    ("NoticeId", "int", True),
    ("StartDate", "str", True),
    ("EndDate", "str", True),
    ("Url", "str", True),
    ("Title", "str", True),
    ("DisplayOrder", "int", True),
)
# Notices 与 Events 的元素形状**完全相同**（官方 6 条 + 14 条，键集合一致）
P90004_EVENT_FIELDS = P90004_NOTICE_FIELDS

# Banners：7 条里 5 条 10 键、2 条 9 键；缺的正是这两个可选键
P90004_BANNER_FIELDS = (
    ("BannerId", "int", True),
    ("StartDate", "str", True),
    ("EndDate", "str", True),
    ("CdnUrl", "str", True),
    ("LinkedLobbyBannerId", "int", False),
    ("BannerType", "int", False),
    ("LinkUrl", "str", True),
    ("SurveyId", "int", True),
    ("BannerDisplayType", "int", True),
    ("CreateTime", "str", True),
)

P90004_GACHA_FIELDS = (
    ("GachaProbabilityDisplayId", "int", True),
    ("Url", "str", True),
    ("LinkedLobbyBannerId", "int", True),
    ("GachaDisplayTag", "int", True),
)

# 运营数据覆盖文件（按顺序取第一个存在的；都没有 → 全空数组，这是合法的新号状态）
P90004_OPS_PATHS = (
    "/www/wwwroot/bapatch/_ba_state/90004_ops.json",
    "/www/wwwroot/bapatch/90004_ops.json",
)


# ---------------------------------------------------------------- 归一化
def _p90004_int(v):
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, int):
        return v
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if isinstance(v, str):
        s = v.strip()
        try:
            return int(s)
        except Exception:
            return 0
    return 0


def _p90004_str(v):
    if isinstance(v, str):
        return v
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


def _p90004_items(raw, fields):
    """把任意脏数据投影成「字段白名单 + 类型强转 + 官方键序」的列表。

    白名单的意义：运营数据里多写的键不会漏到客户端（多键 = 结构错）；
    可选字段缺省时**整个键不出现**（官方 2/7 条 banner 就是这样）。
    """
    if not isinstance(raw, list):
        return []
    out = []
    for it in raw:
        if not isinstance(it, dict):
            continue
        row = {}
        for name, kind, need in fields:
            if name in it and it[name] is not None:
                row[name] = _p90004_int(it[name]) if kind == "int" else _p90004_str(it[name])
            elif need:
                row[name] = 0 if kind == "int" else ""
            # 可选且缺 → 不出现（proto3 presence 语义）
        out.append(row)
    return out


def build_90004_management_data(session_key, ticks, request_id, ops=None):
    """返回官方形状的 90004 响应（6 个顶层键，Data 是 9 键 dict）。

    session_key : {"AccountServerId": int, "MxToken": str}   取不到时传 {} 或 None
    ticks       : ServerTimeTicks（.NET 100ns）
    request_id  : 必须与 HTTP 响应头 requestid 同值（官方逐字节相同）
    ops         : 运营数据 dict，可残缺；None = 新号（4 个列表全空 + 3 个 null）
    """
    sk = session_key if isinstance(session_key, dict) else {}
    ops = ops if isinstance(ops, dict) else {}

    data = {}
    data["Notices"] = _p90004_items(ops.get("Notices"), P90004_NOTICE_FIELDS)
    data["Events"] = _p90004_items(ops.get("Events"), P90004_EVENT_FIELDS)
    data["Issues"] = _p90004_items(ops.get("Issues"), ())
    data["Banners"] = _p90004_items(ops.get("Banners"), P90004_BANNER_FIELDS)
    data["GachaProbabilityDisplay"] = _p90004_items(
        ops.get("GachaProbabilityDisplay"), P90004_GACHA_FIELDS)
    data["GuidePopup"] = _p90004_items(ops.get("GuidePopup"), ())
    # 三个恒 null（不是 False、不是 {}）
    data["GachaPeriodDisplay"] = None
    data["RaidPeriodDisplay"] = None
    data["Survey"] = None

    return {
        "Protocol": 90004,
        "SessionKey": {"AccountServerId": _p90004_int(sk.get("AccountServerId")),
                       "MxToken": _p90004_str(sk.get("MxToken"))},
        "ServerTimeTicks": _p90004_int(ticks),
        "ServerNotification": 0,
        "RequestId": _p90004_str(request_id),
        "Data": data,
    }


def load_90004_ops(path=None):
    """读运营数据：显式 path 优先；否则扫 P90004_OPS_PATHS。失败一律返回 None。"""
    cands = [path] if path else list(P90004_OPS_PATHS)
    for p in cands:
        if not p or not os.path.isfile(p):
            continue
        try:
            with open(p, "r", encoding="utf-8") as fh:
                obj = json.load(fh)
        except Exception:
            continue
        if isinstance(obj, dict) and isinstance(obj.get("Data"), dict):
            obj = obj["Data"]          # 容忍直接把整个响应存进去
        if isinstance(obj, dict):
            return obj
    return None


def data_key_report(obj):
    """给日志/验收用：Data 的键数 + 各列表长度。"""
    d = obj.get("Data") or {}
    return {"data_keys": len(d),
            "Notices": len(d.get("Notices") or []),
            "Events": len(d.get("Events") or []),
            "Issues": len(d.get("Issues") or []),
            "Banners": len(d.get("Banners") or []),
            "GachaProbabilityDisplay": len(d.get("GachaProbabilityDisplay") or []),
            "GuidePopup": len(d.get("GuidePopup") or []),
            "nulls": [k for k in P90004_NULL_KEYS if d.get(k, "missing") is None]}


# ---------------------------------------------------------------- 自检
if __name__ == "__main__":
    o = build_90004_management_data(
        {"AccountServerId": 99990000001, "MxToken": "A" * 64},
        639304002554622705, "00000000-0000-4000-8000-000000000000")
    print(json.dumps(o, ensure_ascii=False, indent=1))
    print("data_key_report =", data_key_report(o))
    print("inner_bytes     =", len(json.dumps(o, ensure_ascii=False,
                                              separators=(",", ":")).encode("utf-8")))
