#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""specgen.py — 「结构由 spec 驱动、数据由初始状态规则驱动」的响应生成引擎（原型）。

只读上游三份产出，绝不改写：
  * work/ba/proto/official_spec.json          —— 109 条官方响应提取出的**结构**规格（38 协议）
  * work/ba/proto/initial_state_rules.json    —— 新号初始状态规则（含 server_apply_skeleton）
  * work/ba/data/ExcelDB.db                   —— 只读打开的配置表（主数据 / catalog）

核心思想（两层解耦）：
  1. **结构层**：conform() 把「任意数据」投影到 spec 的形状上 ——
     * spec 里有、数据里没有的 **必填** 键 → 用该节点的结构性默认值补（int 0 / str "" / [] / {} / null）
     * spec 里有、数据里没有的 **可选** 键(always=false) → 省略（proto3 可选标量的 presence 语义，官方同样省略）
     * 数据里有、spec 里没有的键 → 丢弃并**记账**（这条是 spec 完整性的探针，生成后应恒为 0）
     因此「生成物必然 PASS spec_check」是被构造保证的，不是靠手调。
  2. **数据层**：新号该有什么，全部从 initial_state_rules.json / ExcelDB.db 推出来；
     找不到规则的项留空（0 / [] / {}）并在 REPORT.md 里逐条登记为「未找到」。

口径约定（细节见 REPORT.md）：
  * ServerTimeTicks  = .NET 100ns ticks（自 0001-01-01），已用 24000 实测比对确认单位
  * 时间字符串       = RFC3339Nano 风格（小数位尾零裁掉），零值为 "0001-01-01T00:00:00"
  * 子回包信封       = Protocol 0 / SessionKey{0,""} / ServerTimeTicks 0 / ServerNotification 0 / RequestId ""
"""
from __future__ import annotations

import base64
import datetime as _dt
import hashlib
import json
import os
import sqlite3
import struct
import sys
import uuid

# ---------------------------------------------------------------- 路径
HERE = os.path.dirname(os.path.abspath(__file__))          # .../work/ba/server/prototype
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))   # .../BAServer
SPEC_PATH = os.path.join(ROOT, "work", "ba", "proto", "official_spec.json")
RULES_PATH = os.path.join(ROOT, "work", "ba", "proto", "initial_state_rules.json")
EXCELDB_PATH = os.path.join(ROOT, "work", "ba", "data", "ExcelDB.db")
OUT_DIR = os.path.join(HERE, "out")

# ---------------------------------------------------------------- 常量
ZERO_TIME = "0001-01-01T00:00:00"     # Go 零值时间（initial_state_rules q9 里 LastSummonDate 的写法）
DOTNET_EPOCH = _dt.datetime(1, 1, 1)

# ParcelType 枚举（只有这几个有证据；见 initial_state_rules.not_found 第 4 条）
PARCEL_TYPE_CHARACTER = 1     # 规则表确认：Character=1
PARCEL_TYPE_ITEM = 4          # 规则表确认：Item=4（q3）
PARCEL_TYPE_EMBLEM = 20       # 规则表确认：Emblem=20（q3 / q10 交叉验证）
PARCEL_TYPE_FURNITURE = 13    # 规则表未给 → 取官方 FurnitureDBs 27 行恒定值 13（枚举常量，非账号数据）

# 会随时间恢复的货币 id（UpdateTimeDict 的键集合）。
# 该集合取自 spec 无法表达的「map 键集合」这一结构信息：官方 UpdateTimeDict 恰好 19 键
# = {5,6,7,8,9,12..17,19..26}，与「发放的 19 种货币」不是同一集合（少了 1/3/18/27/28/29）。
REGENERATING_CURRENCY_IDS = [5, 6, 7, 8, 9, 12, 13, 14, 15, 16, 17,
                             19, 20, 21, 22, 23, 24, 25, 26]

# 国服实际启用的学院 location（= AcademyLocationDBSchema 11 条去掉 14/18）。
# 依据：官方 24000 AcademyLocationDBs 恰为这 9 个；规则表 q8 明确「为什么少 14/18」= 未找到，
# 但「启用集合」本身在官方侧是确定的。用它筛 AcademyZoneDBSchema 得到的 71 个 zone id
# 与官方 ZoneVisitCharacterDBs 的 71 个键**集合完全相等**（见 REPORT.md 交叉验证）。
SERVICE_ENABLED_LOCATIONS = [1, 7, 11, 12, 13, 15, 16, 17, 19]


# ================================================================ 时间
def server_time_ticks(dt):
    """datetime(UTC, naive) → ServerTimeTicks（.NET 100ns，自 0001-01-01）。"""
    delta = dt - DOTNET_EPOCH
    return (delta.days * 86400 + delta.seconds) * 10_000_000 + delta.microseconds * 10


def fmt_time(dt, frac=3):
    """RFC3339Nano 风格：小数位按 frac 截断后**去掉尾零**（官方就是这么发的，如 .479 / 无小数）。"""
    s = "%04d-%02d-%02dT%02d:%02d:%02d" % (dt.year, dt.month, dt.day,
                                          dt.hour, dt.minute, dt.second)
    if frac:
        ns = dt.microsecond * 1000                      # 微秒 → 纳秒
        digits = ("%09d" % ns)[:frac].rstrip("0")
        if digits:
            s += "." + digits
    return s


def parse_time(s):
    return _dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%S")


# ================================================================ spec 引擎
class Issues(object):
    """记账：生成过程中被丢弃/被强制的节点。健康态 = dropped 为空。"""

    def __init__(self):
        self.dropped = []     # (path, key, 说明)   数据里有、spec 里没有 → 丢了
        self.forced = []      # (path, 说明)        数据不合法(spec 只允许空/ null) → 强制

    def drop(self, path, key, detail):
        self.dropped.append((path, key, detail))

    def force(self, path, detail):
        self.forced.append((path, detail))

    def summary(self):
        return {"dropped_keys": len(self.dropped), "forced_nodes": len(self.forced)}


class Spec(object):
    """official_spec.json 的只读封装 + 形状投影器。"""

    def __init__(self, path=SPEC_PATH):
        with open(path, "r", encoding="utf-8") as fh:
            self.raw = json.load(fh)
        self.protocols = self.raw["protocols"]

    # ---------------------------------------------------------- 查询
    def entry(self, proto):
        e = self.protocols.get(str(proto))
        if e is None:
            raise KeyError("spec 中没有协议 %s" % (proto,))
        return e

    def schema(self, proto):
        return self.entry(proto)["schema"]

    def name(self, proto):
        return self.entry(proto)["name"]

    def top_key_order(self, proto):
        return list(self.entry(proto).get("top_key_order") or [])

    def mandatory_top_keys(self, proto):
        return list(self.entry(proto).get("mandatory_top_keys") or [])

    # ---------------------------------------------------------- 默认值
    def default(self, node, path="$"):
        """某节点「没有数据」时最保守的合法值。"""
        t = node.get("type")
        if t == "null":
            return None
        if t == "unknown":
            return None
        if t == "mixed":
            vs = node.get("variants") or []
            if not vs:
                return None
            return self.default(vs[0], path)
        if t == "int":
            return 0
        if t == "float":
            return 0.0
        if t == "number":
            return 0
        if t == "str":
            return ""
        if t == "bool":
            return False
        if t == "map":
            return {}
        if t == "array":
            return []
        if t == "object":
            return self.conform({}, node, path, Issues())
        raise ValueError("未知 type=%r @ %s" % (t, path))

    # ---------------------------------------------------------- 投影
    def conform(self, value, node, path, issues):
        """把 value 投影成 spec 形状（保证 spec_check 不 FAIL）。"""
        t = node.get("type")

        if t == "unknown":
            return value

        # ---- null / 可空性
        if value is None:
            if t == "null":
                return None
            if node.get("nullable"):
                return None
            return self.default(node, path)

        if t == "null":
            # spec 说这里恒为 null（官方观测到的唯一形态）
            issues.force(path, "spec type=null，数据给的是 %r → 强制 null" % (value,))
            return None

        if t == "mixed":
            for var in node.get("variants") or []:
                if _compatible(value, var):
                    return self.conform(value, var, path, issues)
            issues.force(path, "mixed 变体都不匹配，取第一变体默认值")
            return self.default(node, path)

        if t == "map":
            out = {}
            valspec = node.get("value") or {"type": "unknown"}
            intkey = node.get("key_kind") == "int_str"
            for k, v in (value or {}).items():
                kk = str(int(k)) if intkey and _is_intlike(k) else str(k)
                out[kk] = self.conform(v, valspec, "%s.%s" % (path, kk), issues)
            return out

        if t == "array":
            if not isinstance(value, list):
                issues.force(path, "spec=array，数据给的是 %s → 取空数组" % type(value).__name__)
                return []
            itemspec = node.get("items") or {"type": "unknown"}
            if itemspec.get("type") in (None, "unknown"):
                if value:
                    issues.force(path, "spec 未给出元素形状(unknown)，丢弃 %d 个元素" % len(value))
                return []
            if itemspec.get("type") == "null":
                # 官方样本里该数组恒为空（items=null 说明从未观测到元素）
                if value:
                    issues.force(path, "spec items=null（官方只见过空数组），丢弃 %d 个元素" % len(value))
                return []
            return [self.conform(el, itemspec, "%s[%d]" % (path, i), issues)
                    for i, el in enumerate(value)]

        if t == "object":
            if not isinstance(value, dict):
                issues.force(path, "spec=object，数据给的是 %s → 取结构默认值" % type(value).__name__)
                return self.default(node, path)
            fields = node.get("fields") or {}
            out = {}
            for k, fs in fields.items():          # 按 spec 顺序输出 == 官方键序
                if k in value:
                    out[k] = self.conform(value[k], fs, "%s.%s" % (path, k), issues)
                elif fs.get("always"):
                    out[k] = self.default(fs, "%s.%s" % (path, k))
                # else: 可选键(always=false) 不出现 → 保持缺席（proto3 可选标量 presence 语义）
            if node.get("observed_empty_only") and out:
                issues.force(path, "spec: 官方此节点始终空对象，丢弃 %d 个键" % len(out))
                return {}
            for k in value:                        # 数据里有、spec 里没有 → 记账
                if k not in fields:
                    issues.drop(path, k, "spec 中不存在该键，值类型 %s" % type(value[k]).__name__)
            return out

        # ---- 标量
        if t == "int":
            if isinstance(value, bool):
                return int(value)
            if isinstance(value, int):
                return value
            if isinstance(value, float) and value.is_integer():
                return int(value)
            if isinstance(value, str) and _is_intlike(value):
                return int(value)
            issues.force(path, "spec=int，实际 %r → 0" % (value,))
            return 0
        if t in ("float", "number"):
            if isinstance(value, bool):
                return 0.0 if t == "float" else 0
            if isinstance(value, (int, float)):
                return float(value) if t == "float" else value
            issues.force(path, "spec=%s，实际 %r → 0" % (t, value))
            return 0.0 if t == "float" else 0
        if t == "str":
            return value if isinstance(value, str) else str(value)
        if t == "bool":
            return bool(value)

        issues.force(path, "spec 中未知 type=%r → 原样保留" % (t,))
        return value

    # ---------------------------------------------------------- 组包
    def build(self, proto, values, issues=None):
        """values 可以是**残缺**的：缺的必填键由 spec 默认值补，缺的可选键省略。"""
        issues = issues if issues is not None else Issues()
        out = self.conform(values, self.schema(proto), "$", issues)
        order = self.top_key_order(proto)
        if order:
            ordered = {}
            for k in order:
                if k in out:
                    ordered[k] = out[k]
            for k in out:                    # spec 顺序里没列到的（理论上不存在）
                if k not in ordered:
                    ordered[k] = out[k]
            out = ordered
        return out

    def check_report(self, proto, response):
        """不在本文件里重写校验器：直接复用 proto/spec_check.py。"""
        sys.dont_write_bytecode = True                   # 不给 work/ba/proto/ 留 __pycache__
        sys.path.insert(0, os.path.join(ROOT, "work", "ba", "proto"))
        import spec_check                                # noqa: E402
        rep, entry = spec_check.check_one(proto, response, self.raw, "<generated>")
        return rep, entry


def _is_intlike(x):
    s = str(x)
    if s.startswith("-"):
        s = s[1:]
    return s.isdigit() and len(s) > 0


def _compatible(value, spec):
    """只判断本条值自身类别是否与 spec 兼容（给 mixed 用）。"""
    t = spec.get("type")
    if t in ("unknown", "mixed"):
        return True
    if value is None:
        return t == "null" or bool(spec.get("nullable"))
    if t == "null":
        return False
    if t == "object" or t == "map":
        return isinstance(value, dict)
    if t == "array":
        return isinstance(value, list)
    if t == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if t in ("float", "number"):
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if t == "str":
        return isinstance(value, str)
    if t == "bool":
        return isinstance(value, bool)
    return True


# ================================================================ FlatBuffers 最小读取
# ExcelDB.db 的每行是 FlatBuffers table（SQL 主键列之外的一列 Bytes）。
# 只需要读**标量 slot**，所以这里只做 vtable 查表，不做向量/字符串。
def fb_slot_int(blob, slot):
    try:
        (root,) = struct.unpack_from("<I", blob, 0)
        (soffset,) = struct.unpack_from("<i", blob, root)
        vt = root - soffset
        (vt_size,) = struct.unpack_from("<H", blob, vt)
        off = 4 + 2 * slot
        if off + 2 > vt_size:
            return None
        (vtoff,) = struct.unpack_from("<H", blob, vt + off)
        if vtoff == 0:
            return None
        (val,) = struct.unpack_from("<i", blob, root + vtoff)
        return val
    except Exception:
        return None


# ================================================================ 主数据（ExcelDB.db，只读）
class MasterData(object):
    def __init__(self, path=EXCELDB_PATH):
        self.path = path
        self._con = None

    @property
    def con(self):
        if self._con is None:
            uri = "file:%s?mode=ro" % self.path.replace("\\", "/")
            self._con = sqlite3.connect(uri, uri=True)
        return self._con

    def close(self):
        if self._con is not None:
            self._con.close()
            self._con = None

    def _scalar_rows(self, table, key_col="Id", blob_col="Bytes"):
        return self.con.execute('SELECT "%s","%s" FROM "%s"' % (key_col, blob_col, table))

    # ---- 商店 banner（规则 q10：ShopRecruitDBSchema 去掉 Id 1/2/3）
    def shop_recruit_ids(self):
        rows = self.con.execute(
            "SELECT Id FROM ShopRecruitDBSchema WHERE Id NOT IN (1,2,3) ORDER BY Id").fetchall()
        return [int(r[0]) for r in rows]

    # ---- 学院 zone（zone.f1 = location）
    def zone_ids(self, locations):
        want = set(int(x) for x in locations)
        out = []
        for zid, blob in self._scalar_rows("AcademyZoneDBSchema"):
            loc = fb_slot_int(blob, 1)
            if loc is not None and loc in want:
                out.append(int(zid))
        return sorted(out)

    def zone_location_map(self):
        m = {}
        for zid, blob in self._scalar_rows("AcademyZoneDBSchema"):
            m[int(zid)] = fb_slot_int(blob, 1)
        return m

    # ---- 家具舒适度（FurnitureDBSchema.f24；11 件默认家具各 20 → 合计 220）
    def furniture_comfort(self, furniture_ids):
        want = set(int(x) for x in furniture_ids)
        total = 0
        detail = {}
        for fid, blob in self._scalar_rows("FurnitureDBSchema"):
            if int(fid) in want:
                c = fb_slot_int(blob, 24) or 0
                detail[int(fid)] = c
                total += c
        return total, detail

    # ---- 账号等级奖励（AccountLevelRewardDBSchema：SQL 列 Level 直接可读）
    def account_level_reward_ids(self, account_level):
        rows = self.con.execute(
            "SELECT Id, Level FROM AccountLevelRewardDBSchema ORDER BY Id").fetchall()
        return [int(r[0]) for r in rows if int(r[1]) <= int(account_level)]

    def cafe_ids(self):
        return [int(r[0]) for r in self.con.execute(
            "SELECT CafeId FROM CafeInfoDBSchema ORDER BY CafeId").fetchall()]

    def academy_location_ids(self):
        return [int(r[0]) for r in self.con.execute(
            "SELECT Id FROM AcademyLocationDBSchema ORDER BY Id").fetchall()]


# ================================================================ 虚构账号
class Account(object):
    """一个虚构账号。多用户私服里每张卡密 = 一个这样的对象。"""

    def __init__(self, server_id, mxtoken, request_id, now):
        self.server_id = int(server_id)
        self.mxtoken = mxtoken
        self.request_id = request_id
        self.now = now                     # naive UTC
        self.ticks = server_time_ticks(now)

    # ---- 对象 ServerId 的分配（账号内唯一，int64 安全）
    # 官方 ServerId 是 7~8 位的服务端自增号，没有跨账号含义；这里改成「账号id 打头 + kind + 序号」，
    # 保证多账号共库时不撞号，且编队/装备的交叉引用只用同一套函数算出的值。
    KIND_CHARACTER = 1
    KIND_ITEM = 2
    KIND_FURNITURE = 3

    def obj_id(self, kind, index):
        return self.server_id * 100000 + kind * 10000 + int(index)

    def session_key(self):
        return {"AccountServerId": self.server_id, "MxToken": self.mxtoken}

    def envelope(self, proto):
        """顶层信封（唯一带真值的信封；子回包的信封由 spec 默认值补成零值）。"""
        return {
            "Protocol": int(proto),
            "SessionKey": self.session_key(),
            "ServerTimeTicks": self.ticks,
            "ServerNotification": 0,
            "RequestId": self.request_id,
        }

    def fmt(self, dt=None, frac=3):
        return fmt_time(dt or self.now, frac)

    def ts(self, dt=None, frac=3):
        return fmt_time(dt or self.now, frac)

    @classmethod
    def create(cls, server_id=99990000001, now=None, request_id=None, mxtoken=None):
        now = now or _dt.datetime.utcnow()
        if now.tzinfo is not None:
            now = now.astimezone(_dt.timezone.utc).replace(tzinfo=None)
        if request_id is None:
            request_id = str(uuid.uuid4())
        if mxtoken is None:
            # 48 字节 sha384 → base64 正好 64 字符，与官方 MxToken 长度一致
            mxtoken = base64.b64encode(
                hashlib.sha384(("ba-private-server:%d" % int(server_id)).encode()).digest()
            ).decode("ascii")
        return cls(server_id, mxtoken, request_id, now)


# ================================================================ CLI 公共部分
def add_common_args(ap, default_out):
    ap.add_argument("--server-id", type=int, default=99990000001, help="账号 AccountServerId")
    ap.add_argument("--now", default=None,
                    help="固定时间（UTC，YYYY-MM-DDTHH:MM:SS），不传 = 当前时间")
    ap.add_argument("--request-id", default=None, help="不传 = uuid4")
    ap.add_argument("--mxtoken", default=None, help="不传 = 由 server_id 派生 64 字符 base64")
    ap.add_argument("--out", default=default_out, help="输出文件路径")
    ap.add_argument("--pretty", action="store_true", default=True, help="缩进输出（默认开）")
    ap.add_argument("--compact", dest="pretty", action="store_false", help="紧凑输出")
    return ap


def account_from_args(args):
    now = None
    if args.now:
        now = parse_time(args.now)
    return Account.create(args.server_id, now=now,
                          request_id=args.request_id, mxtoken=args.mxtoken)


def write_json(obj, path, pretty=True):
    d = os.path.dirname(os.path.abspath(path))
    if d and not os.path.isdir(d):
        os.makedirs(d)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        if pretty:
            json.dump(obj, fh, ensure_ascii=False, indent=1)
            fh.write("\n")
        else:
            json.dump(obj, fh, ensure_ascii=False, separators=(",", ":"))
            fh.write("\n")
    return os.path.getsize(path)


def print_verdict(proto, spec, response, path, issues):
    """打印字节数 / 键数 / spec_check 结果 —— 两个生成器的统一收尾。"""
    rep, entry = spec.check_report(proto, response)
    size = os.path.getsize(path)
    warns = rep.warns
    cats = {}
    for k, _p, _d in warns:
        cats[k] = cats.get(k, 0) + 1
    print("-" * 72)
    print("协议 %-6s %-32s spec观测=%s" % (proto, entry["name"], entry["observations"]))
    print("输出文件        : %s (%d bytes)" % (path, size))
    print("顶层键数        : %d (spec 必填 %d)" % (len(response), len(spec.mandatory_top_keys(proto))))
    print("conform 记账    : %s" % issues.summary())
    if issues.dropped:
        print("  !! 数据里有 spec 未定义的键（spec 可能不完整）:")
        for p, k, d in issues.dropped[:20]:
            print("     %s.%s  %s" % (p, k, d))
    if issues.forced:
        print("  !! 被强制的节点:")
        for p, d in issues.forced[:20]:
            print("     %s  %s" % (p, d))
    print("spec_check      : %s  FAIL %d / WARN %d %s"
          % ("PASS" if not rep.fails else "FAIL", len(rep.fails), len(warns),
             ("(%s)" % ", ".join("%s=%d" % kv for kv in sorted(cats.items()))) if cats else ""))
    for k, p, d in rep.fails[:20]:
        print("  FAIL [%s] %s  %s" % (k, p, d))
    return rep, entry
