#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen8000.py —— Mission_List (8000) 响应生成器。

只读上游，绝不改写：
  * work/ba/proto/official_spec.json          结构权威（3 次观测合并）
  * work/ba/data/ExcelDB.db                    4 张任务表（只读，mode=ro）
  * work/ba/server/prototype/specgen.py        已验证的 conform 引擎（复用，不重写）
  * report/_tmp/official_decoded_201/0[8]/*.    官方 3 份抓包（用于对比/校验）

────────────────────────────────────────────────────────────────────────
一、8000 有三个变体，差异不在 id 段，在请求里的 EventContentId
────────────────────────────────────────────────────────────────────────
实测（三份 request/response 逐字节对比，见 TEST_8000.md §1）：

  抓包   EventContentId   顶层键       ProgressDBs  官方 resp_bytes  inner 明文
  08     null            10 键(相同)   1240         268,396 B        201,253 B
  10     849             10 键(相同)      39           8,768 B          6,540 B
  11     10838           10 键(相同)      35           8,216 B          6,115 B

  · 三份响应的顶层键 **完全相同**（10 个），键序也相同；
  · 唯一变化的量是 `ProgressDBs` 的长度，以及连带 `MissionHistoryUniqueIds` /
    `ClearedOriginalMissionIds`（08 各 372 条，10/11 都是 `[]`）；
  · `HistoryDBs` 三份都是 `null`；`DailySuddenMissionInfo` 三份都是 `{"Id":1606}`。

  ⇒ 触发差异的原因是**客户端请求参数不同**：`EventContentId:null` 拉全量，
    `EventContentId:N` 只拉该活动。过滤规则经 100% 验证：

        EventContentId=N  ⇒  ProgressDBs = { m | m.EventContentId == N }

    849   → EventContentMissionDBSchema WHERE EventContentId=849          = 39 条（官方 39，集合相等）
    10838 → EventContentMissionDBSchema WHERE EventContentId=10838 (17)
          + MiniGameMissionDBSchema  WHERE Id//10000    = 10838 (18)      = 35 条（官方 35，集合相等）

  ⇒ **事件变体是纯表驱动、与账号进度无关**，可以逐条复现官方。

────────────────────────────────────────────────────────────────────────
二、全量变体（EventContentId=null）的 1240 条是「账号进度」，不是「表全量」
────────────────────────────────────────────────────────────────────────
按 Category 路由（H 线结论，本文件用行内槽位再次验证）：

    Category          → 表                            该表行数   官方 08 选中
    0,1,2,3,9,10      → MissionDBSchema (f1)              3444        476
    4                 → GuideMissionDBSchema (f2)           923        690
    7                 → MiniGameMissionDBSchema (f4)        402         18
    8                 → EventContentMissionDBSchema (f4)   2384         56
                                                         ─────      ─────
                                                           7153       1240

  1240/1240 全部有归属（与 H 线一致），但**只是表的一小部分**：
  MissionDB 3084 条 Category=3 只出 379、cat9 22 条只出 1 条、cat10 3 条只出 1 条。
  被选中的 id 离散分布在 40 个万位段（见 TEST_8000.md §3），
  且为同一张表内同一 Category 的**子集** ⇒ 选择由账号进度决定，静态表无法反推。
  这与 B 线 `initial_state_rules.json` 的 `not_found`（"首日任务进度"）结论一致。

  ⇒ 新号的 ProgressDBs 取什么，见本文件 PROFILE 说明。

────────────────────────────────────────────────────────────────────────
三、Category 的静态来源（行内槽位，不是按 id 位数猜）
────────────────────────────────────────────────────────────────────────
    MissionDBSchema.f1              406/406 行 == Category（0 不落盘，槽位缺席即 0）
    GuideMissionDBSchema.f2        1429/1429
    EventContentMissionDBSchema.f4  112/112
    MiniGameMissionDBSchema.f4       36/36

  本文件 `--selfcheck` 会把这条重算一遍（全表，不只样本行）。

────────────────────────────────────────────────────────────────────────
四、协议里**没有** Progress 字段
────────────────────────────────────────────────────────────────────────
  ProgressDBs[] 实际字段只有 5~6 个：
    AccountServerId / MissionUniqueId / Category / StartDate / ProgressParameters
    (+ 可选的 Complete，official 357/1314 有)
  `Progress` 在 3 份响应里出现 0 次（H 线结论）。本文件不产生该字段。

────────────────────────────────────────────────────────────────────────
五、ProgressParameters 的 key —— 判别槽位是 f16（任务进度类型）
────────────────────────────────────────────────────────────────────────
  cat 8（EventContentMissionDBSchema）：交叉表实测（官方 56 条 cat8 全量）得到

      f16 == 83        → key = str(f15)     （关卡型；30/30 条 f15 都在）
      f16 == 121 / 122 → key = str(EventContentId)   （计数型）
      f16 == 3  / 131  → 省略 PP（{}）      （无进度参数型）
      其余（未观测）    → f15 有则用 f15，否则用 EventContentId

      这条规则 **56/56 与官方逐条一致**（含 849 里 22 条 {"849":0}、
      15 条 {"8492301":999}、2 条 {}），见 `--selfcheck` ⑤。

      对照表（uid / kind / f15 / f16）：
        849001..849022  eci    None   121|122   → {"849":0}
        849023          empty  None   131       → {}
        849024..849038  f15    8492xxx 83       → {"8492301":999} …
        849039          empty  None   3         → {}
        10838001        empty  None   131       → {}
        10838002..16    f15    10838xxx 83      → {"108382301":999} …
        10838017        empty  None   3         → {}

  cat 7（MiniGame）：官方 key 形如 110838101，实测命中 `MiniGameDefenseStageDBSchema.Id`，
      但「哪个任务对应哪个迷你关卡」映射**未找到**（该 key 不在任何表槽位里）⇒
      退回 EventContentId，6/18 与官方一致，其余 12 条 key 合法但不同（仍 PASS）。
  cat 1/2/9/10：key 基本都是 "0"（官方 25 条里 23 条是 {"0":...}；
      例外 1514 / 2399 官方是 {}，本文件给 {"0":0}，如实登记为未解释）。

  值：新号一律 0。

────────────────────────────────────────────────────────────────────────
六、幂等与速度
────────────────────────────────────────────────────────────────────────
  8000 在大厅会被反复调用（本次抓包里 3 次）。因此：
  · 同一账号同一天、同一参数 ⇒ **字节完全相同**（不用 now()，不用随机数）；
  · StartDate 钉在「当日 04:00 日重置点 + 账号派生常数毫秒」，与官方
    `2026-11-16T04:00:06.215` 同一形态（官方抓包 bj=04:30:56 ⇒ 日重置 04:00）；
  · 目录（7000+ 行）只在进程启动时读一次，之后纯内存过滤。

用法
────
    # 全量变体（新号默认 profile=seed）
    python gen8000.py --account-id 10015354380 --out out.json

    # 事件变体
    python gen8000.py --account-id 10015354380 --event-content-id 849 --out out.json
    python gen8000.py --account-id 10015354380 --event-content-id 10838 --out out.json

    # 纯空进度（最小响应）
    python gen8000.py --account-id 10015354380 --profile empty --out out.json

    # 三份官方抓包逐键对比（TEST_8000.md §1 的可复现命令）
    python gen8000.py --explain-variants

    # 表路由自检（Category 槽位一致性 + 官方 1240 归属）
    python gen8000.py --selfcheck

    # 导出部署用目录（供 patch_8000.py 的服务端运行时读取）
    python gen8000.py --emit-catalog 8000_catalog.json
"""
from __future__ import annotations

import argparse
import base64
import datetime as _dt
import hashlib
import importlib.util
import json
import os
import sqlite3
import struct
import sys

# ---------------------------------------------------------------- 路径

HERE = os.path.dirname(os.path.abspath(__file__))                      # work/ba/server/deploy
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))     # BAServer

# 数据/引擎文件定位（与 gen1017.py 同一套顺序）：
#   环境变量 > 从本文件/cwd 向上找 repo 布局(work/ba/…) > 同一批目录下找裸文件名。
# 最后一条覆盖扁平部署：specgen.py / official_spec.json / spec_check.py / ExcelDB.db
# 与本文件平铺在同一目录（线上 /www/wwwroot/bapatch/tools/）时裸名命中。
SPEC_ENV = "BA_SPEC_PATH"
SPECGEN_ENV = "BA_SPECGEN_DIR"
EXCELDB_ENV = "BA_EXCELDB_PATH"


def _ancestors(start, depth=8):
    out, cur = [], os.path.abspath(start)
    for _ in range(depth):
        out.append(cur)
        nxt = os.path.abspath(os.path.join(cur, os.pardir))
        if nxt == cur:
            break
        cur = nxt
    return out


def _find_path(fname, rel=(), env=None, want_dir=False, env_is_dir=False):
    """按 gen1017 的顺序找文件/目录（找不到返回 None）。env_is_dir: 环境变量给的是目录。"""
    probe = os.path.isdir if want_dir else os.path.isfile
    val = os.environ.get(env) if env else None
    if val:
        cand = os.path.join(val, fname) if env_is_dir else val
        if probe(cand):
            return os.path.abspath(cand)
    roots = _ancestors(HERE) + _ancestors(os.getcwd(), 4)
    for d in roots:
        p = os.path.join(d, *(rel + (fname,))) if rel else os.path.join(d, fname)
        if probe(p):
            return os.path.abspath(p)
    for d in roots:
        p = os.path.join(d, fname)
        if probe(p):
            return os.path.abspath(p)
    return None


_P_SPEC = _find_path("official_spec.json", ("work", "ba", "proto"), SPEC_ENV)
_P_SPEC_CHECK = _find_path("spec_check.py", ("work", "ba", "proto"))
P_PROTO = (os.path.dirname(_P_SPEC) if _P_SPEC else
           (os.path.dirname(_P_SPEC_CHECK) if _P_SPEC_CHECK else
            os.path.join(ROOT, "work", "ba", "proto")))
P_SPEC = _P_SPEC or os.path.join(P_PROTO, "official_spec.json")
P_SPECGEN = (_find_path("specgen.py", ("work", "ba", "server", "prototype"),
                        SPECGEN_ENV, env_is_dir=True) or
             os.path.join(ROOT, "work", "ba", "server", "prototype", "specgen.py"))
P_EXCELDB = (_find_path("ExcelDB.db", ("work", "ba", "data"), EXCELDB_ENV) or
             os.path.join(ROOT, "work", "ba", "data", "ExcelDB.db"))
P_CAPTURE = (_find_path("official_decoded_201", ("report", "_tmp"), want_dir=True) or
             os.path.join(ROOT, "report", "_tmp", "official_decoded_201"))

sys.dont_write_bytecode = True          # 不给 work/ba/proto、prototype 留 __pycache__

# ---------------------------------------------------------------- 常量

PROTOCOL = 8000
PROTOCOL_NAME = "Mission_List"
DEFAULT_ACCOUNT = 10015354380

# 日重置时刻（本地 04:00）。证据：官方 StartDate=2026-11-16T04:00:06.215，
# 而同一次抓包 meta.bj=04:30:56，两者同一时钟且相差 30 分钟 ⇒ 日重置在 04:00。
RESET_HOUR = 4

# 官方三份抓包的实测尺寸（用于对比，不是目标值）
#   wire  = meta.resp_bytes，抓包里的 HTTP body 大小（含加密/外层包裹）
#   inner = outer.packet 的长度，即解密后的紧凑 inner JSON —— **这才是结构口径**
#   （注意：报告 102 里引用的 268,396 是 wire，不是 inner；inner 是 183,441）
OFFICIAL = {
    None:  {"file": "08", "wire": 268396, "inner": 183441, "progress": 1240,
            "history": 372, "complete": 357, "startdate_distinct": 23},
    849:   {"file": "10", "wire": 8768,   "inner": 5878,   "progress": 39,
            "history": 0,   "complete": 0,   "startdate_distinct": 1},
    10838: {"file": "11", "wire": 8216,   "inner": 5511,   "progress": 35,
            "history": 0,   "complete": 0,   "startdate_distinct": 1},
}

# 4 张任务表 → Category 槽位（H 线 + 本文件 --selfcheck 复验）
TABLES = {
    "MissionDBSchema":            {"cat_slot": 1, "event": "none"},
    "GuideMissionDBSchema":       {"cat_slot": 2, "event": "none"},
    "EventContentMissionDBSchema": {"cat_slot": 4, "event": "sql:EventContentId"},
    "MiniGameMissionDBSchema":    {"cat_slot": 4, "event": "id//10000"},
}

# Category → 表（路由权威表）。0/1/2/3/9/10 都属于 MissionDBSchema。
# cat6 / cat11 是表里存在、但官方 8000 的 1240 条里**未观测**的组合，也按所在表路由，
# 以免 7153 条目录里有条目落不到表（本文件 --selfcheck ②会检查「未路由」）。
CATEGORY_TO_TABLE = {
    0: "MissionDBSchema",
    1: "MissionDBSchema",
    2: "MissionDBSchema",
    3: "MissionDBSchema",
    4: "GuideMissionDBSchema",
    6: "MiniGameMissionDBSchema",
    7: "MiniGameMissionDBSchema",
    8: "EventContentMissionDBSchema",
    9: "MissionDBSchema",
    10: "MissionDBSchema",
    11: "EventContentMissionDBSchema",
}

# seed profile 用到的「时间驱动」区间（证据见 TEST_8000.md §4）
SEED_CAT1_RANGE = (1500, 1514)     # 日常系列：Cat1 的 60 条里官方只选中这一段
SEED_CAT2_RANGE = (2300, 2400)     # 周常系列
SEED_SUDDEN_ID = 1606              # DailySuddenMissionInfo.Id，3 份抓包恒为 1606
SEED_CAT10_ID = 1701               # Cat10 3 条里官方只选中 1701


def out(s=""):
    """Windows 控制台默认 GBK，中文会炸；强制 utf-8 输出。"""
    sys.stdout.write(str(s) + "\n")


# ================================================================ FlatBuffers 标量槽
def fb_slot_int(blob, slot):
    """读 ExcelDB 行 BLOB 的第 slot 个标量槽（缺席 → None）。"""
    try:
        (root,) = struct.unpack_from("<I", blob, 0)
        (soff,) = struct.unpack_from("<i", blob, root)
        vt = root - soff
        (vt_size,) = struct.unpack_from("<H", blob, vt)
        off = 4 + 2 * slot
        if off + 2 > vt_size:
            return None
        (voff,) = struct.unpack_from("<H", blob, vt + off)
        if voff == 0:
            return None
        return struct.unpack_from("<i", blob, root + voff)[0]
    except Exception:
        return None


# ================================================================ specgen 复用
def load_specgen():
    """按路径加载已验证的引擎（不复制它的 conform 逻辑）。"""
    if not os.path.exists(P_SPECGEN):
        raise SystemExit("找不到生成引擎: %s" % P_SPECGEN)
    spec = importlib.util.spec_from_file_location("_ba_specgen", P_SPECGEN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ================================================================ 任务目录
class Mission(object):
    __slots__ = ("uid", "category", "table", "event_id", "f15", "f16")

    def __init__(self, uid, category, table, event_id, f15, f16=None):
        self.uid = int(uid)
        self.category = int(category)
        self.table = table
        self.event_id = event_id          # None = 无活动归属
        self.f15 = f15                    # None = 槽位缺席
        self.f16 = f16                    # None = 槽位缺席（cat8 的进度类型判别位）

    def __repr__(self):
        return "Mission(%d, cat=%d, %s, ev=%s)" % (
            self.uid, self.category, self.table, self.event_id)


class Catalog(object):
    """4 张任务表的只读目录。一次构建，之后纯内存查询。

    构建成本：7153 行 × 一次 vtable 查表，实测 < 0.2 s。
    """

    def __init__(self, db_path=P_EXCELDB):
        if not os.path.exists(db_path):
            raise SystemExit("找不到 ExcelDB: %s" % db_path)
        uri = "file:%s?mode=ro" % db_path.replace("\\", "/")
        self._con = sqlite3.connect(uri, uri=True)
        self._by_uid = {}
        self._by_event = {}
        self._by_cat = {}
        self._load()

    # ---------------------------------------------------------- 构建
    def _load(self):
        con = self._con

        # 1) MissionDBSchema：Category 在 f1（缺席=0）
        for uid, blob in con.execute('SELECT Id, Bytes FROM "MissionDBSchema"'):
            cat = fb_slot_int(blob, 1)
            self._add(Mission(uid, 0 if cat is None else cat,
                              "MissionDBSchema", None, None))

        # 2) GuideMissionDBSchema：Category 在 f2（恒 4）
        for uid, blob in con.execute('SELECT Id, Bytes FROM "GuideMissionDBSchema"'):
            cat = fb_slot_int(blob, 2)
            self._add(Mission(uid, 4 if cat is None else cat,
                              "GuideMissionDBSchema", None, None))

        # 3) EventContentMissionDBSchema：Category 在 f4；EventContentId 用 SQL 列（权威）
        for uid, eci, blob in con.execute(
                'SELECT Id, EventContentId, Bytes FROM "EventContentMissionDBSchema"'):
            self._add(Mission(uid, fb_slot_int(blob, 4) or 0,
                              "EventContentMissionDBSchema",
                              int(eci) if eci is not None else None,
                              fb_slot_int(blob, 15),
                              fb_slot_int(blob, 16)))

        # 4) MiniGameMissionDBSchema：Category 在 f4；EventContentId = Id // 10000
        #    （该表没有 EventContentId 列。Id = EventContentId*10000 + 4 位序号，
        #      实测 13 个活动号：804/807/825/833/836/838/843/848/10804/10825/10833/10836/10838）
        for uid, blob in con.execute('SELECT Id, Bytes FROM "MiniGameMissionDBSchema"'):
            self._add(Mission(uid, fb_slot_int(blob, 4) or 0,
                              "MiniGameMissionDBSchema", int(uid) // 10000,
                              fb_slot_int(blob, 15),
                              fb_slot_int(blob, 16)))

        # 同一活动内是否存在 f15（cat8 的 PP key 回退判定要用）
        self._event_has_f15 = {}
        for m in self._by_uid.values():
            if m.event_id is not None and m.f15 is not None:
                self._event_has_f15[m.event_id] = True

    def _add(self, m):
        self._by_uid[m.uid] = m
        self._by_cat.setdefault(m.category, []).append(m)
        if m.event_id is not None:
            self._by_event.setdefault(m.event_id, []).append(m)

    # ---------------------------------------------------------- 查询
    def __len__(self):
        return len(self._by_uid)

    def get(self, uid):
        return self._by_uid.get(int(uid))

    def by_event(self, event_id):
        """某活动的全部任务定义，按 MissionUniqueId 升序（官方就是这个序）。"""
        return sorted(self._by_event.get(int(event_id), []), key=lambda m: m.uid)

    def by_category(self, cat):
        return sorted(self._by_cat.get(int(cat), []), key=lambda m: m.uid)

    def category_counts(self):
        return {c: len(v) for c, v in sorted(self._by_cat.items())}

    def event_has_f15(self, event_id):
        return bool(self._event_has_f15.get(int(event_id)))

    def close(self):
        try:
            self._con.close()
        except Exception:
            pass


# ================================================================ 时间
def daily_reset(now, hour=RESET_HOUR):
    """当日日重置时刻（同一时钟口径，不做时区转换）。"""
    r = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if now < r:
        r -= _dt.timedelta(days=1)
    return r


def account_jitter_ms(account_id, span=20000):
    """账号派生常数：让 StartDate 落在重置后 1~21 秒，且同账号恒定。

    官方是 04:00:06.215（重置后 6.215 s），量级一致。
    """
    h = hashlib.sha256(b"ba8000:startdate:%d" % int(account_id)).digest()
    return 1000 + struct.unpack_from(">I", h, 0)[0] % span


def start_date_text(account_id, now, hour=RESET_HOUR):
    r = daily_reset(now, hour) + _dt.timedelta(milliseconds=account_jitter_ms(account_id))
    return "%04d-%02d-%02dT%02d:%02d:%02d.%03d" % (
        r.year, r.month, r.day, r.hour, r.minute, r.second, r.microsecond // 1000)


# ================================================================ PP key
def pp_for(mission, catalog):
    """按 Category 给出 ProgressParameters（新号：值一律 0）。

    规则与证据见文件头 §五。返回 {} 表示官方形态就是空 map。
    """
    if mission.category == 8:
        # f16 = 任务进度类型（56/56 复现官方）
        t = mission.f16
        if t in (3, 131):
            return {}                                  # 无进度参数型
        if t in (121, 122):
            return {str(mission.event_id): 0} if mission.event_id is not None else {}
        # 83（关卡型）或未观测值：f15 优先，退化到 EventContentId
        if mission.f15 is not None:
            return {str(mission.f15): 0}
        if mission.event_id is not None:
            return {str(mission.event_id): 0}
        return {}

    if mission.category == 7:
        # 官方 key 形如 "110838101"，实测命中 MiniGameDefenseStageDBSchema.Id，
        # 但「任务→迷你关卡」映射未找到（该 key 不在本表任何槽位里）
        # ⇒ 退回 EventContentId（官方 18 条里 6 条一致）。
        if mission.event_id is not None:
            return {str(mission.event_id): 0}
        return {}

    # cat 0/1/2/3/9/10：官方 key 基本是 "0"
    # （cat0 的 key 来自 MissionDBSchema.f19，新号不出 cat0 条目，故不特殊处理；
    #   官方例外 1514 / 2399 是 {}，此处给 {"0":0}，如实登记为未解释）
    return {"0": 0}


# ================================================================ 生成
def build_progress(profile, catalog, account_id, now, event_content_id=None,
                   reset_hour=RESET_HOUR, daily_sudden_id=SEED_SUDDEN_ID):
    """返回 ProgressDBs 列表（已按 MissionUniqueId 升序）。

    三个变体：
      event_content_id 非 None          → 事件变体（纯表驱动）
      profile == "empty"                → 全量变体，进度全空
      profile == "seed"                 → 全量变体，日/周常一批「已开启未完成」
    """
    sd = start_date_text(account_id, now, reset_hour)

    def item(m, complete=None):
        obj = {
            "AccountServerId": int(account_id),
            "MissionUniqueId": int(m.uid),
            "Category": int(m.category),
            "StartDate": sd,
            "ProgressParameters": pp_for(m, catalog),
        }
        if complete:
            obj["Complete"] = True
        return obj

    # ---------------- 事件变体
    if event_content_id is not None:
        ms = catalog.by_event(event_content_id)
        return [item(m) for m in ms]

    # ---------------- 全量变体 + empty
    if profile == "empty":
        return []

    # ---------------- 全量变体 + seed（时间驱动的日/周常）
    picked = []

    lo, hi = SEED_CAT1_RANGE
    for m in catalog.by_category(1):
        if lo <= m.uid <= hi:
            picked.append(m)

    lo, hi = SEED_CAT2_RANGE
    for m in catalog.by_category(2):
        if lo <= m.uid <= hi:
            picked.append(m)

    for cat, want in ((9, daily_sudden_id), (10, SEED_CAT10_ID)):
        if want:
            m = catalog.get(want)
            if m is not None:
                picked.append(m)

    seen = set()
    uniq = []
    for m in picked:
        if m.uid in seen:
            continue
        seen.add(m.uid)
        uniq.append(m)
    return [item(m) for m in sorted(uniq, key=lambda x: x.uid)]


def build_response(account_id, profile="seed", event_content_id=None, now=None,
                   request_id=None, mxtoken=None, reset_hour=RESET_HOUR,
                   daily_sudden_id=SEED_SUDDEN_ID, catalog=None):
    """组包。返回 (inner_dict, issues, meta)。

    结构正确性由 specgen.Spec.conform 构造性保证：进 conform 之前我们只提供
    数据，缺的必填键由 spec 默认值补，spec 没有的键会被记账丢弃。
    """
    sg = load_specgen()
    spec = sg.Spec(P_SPEC)
    acc = sg.Account.create(int(account_id), now=now,
                            request_id=request_id, mxtoken=mxtoken)
    own = catalog is None
    cat = catalog or Catalog()
    try:
        progress = build_progress(profile, cat, int(account_id), acc.now,
                                  event_content_id=event_content_id,
                                  reset_hour=reset_hour,
                                  daily_sudden_id=daily_sudden_id)
        values = {
            "Protocol": PROTOCOL,
            "SessionKey": acc.session_key(),
            "ServerTimeTicks": acc.ticks,
            "ServerNotification": 0,
            "RequestId": acc.request_id,
            # 官方 3/3 都是 null；spec 里 type=null，别填数组
            "HistoryDBs": None,
            "ProgressDBs": progress,
            "DailySuddenMissionInfo": {"Id": int(daily_sudden_id) if daily_sudden_id else 0},
            # 玩家通关历史：新号为空（官方 08 有 372 条，是进度不是初始值）
            "MissionHistoryUniqueIds": [],
            "ClearedOriginalMissionIds": [],
        }
        issues = sg.Issues()
        inner = spec.build(PROTOCOL, values, issues)
    finally:
        if own:
            cat.close()
    meta = {
        "protocol": PROTOCOL,
        "protocol_name": PROTOCOL_NAME,
        "account_id": int(account_id),
        "variant": "event" if event_content_id is not None else "full",
        "event_content_id": event_content_id,
        "profile": profile,
        "progress_count": len(inner.get("ProgressDBs") or []),
        "inner_bytes": len(compact(inner).encode("utf-8")),
        "request_id": acc.request_id,
        "start_date": (inner.get("ProgressDBs") or [{}])[0].get("StartDate"),
    }
    return inner, issues, meta


def compact(obj):
    """官方 inner 就是这个序列化口径（紧凑、不转义、无空格）。"""
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def b64_bytes(inner):
    """base64(inner) 的字节数 —— 只是 wire 的**下界**，不是真实 wire。

    真实 wire 还含加密块与 `{"protocol","packet","requestid"}` 外层包裹，
    官方实测：inner 5,878 → wire 8,768（+49%）、inner 183,441 → wire 268,396（+46%）。
    """
    raw = compact(inner).encode("utf-8")
    return 4 * ((len(raw) + 2) // 3)


def write_output(inner, path, meta=None):
    """落盘为官方解密格式 {meta, plain, inner} —— spec_check 和 diff 工具都认。"""
    d = os.path.dirname(os.path.abspath(path))
    if d and not os.path.isdir(d):
        os.makedirs(d)
    payload = {"meta": meta or {}, "plain": compact(inner), "inner": inner}
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    return os.path.getsize(path)


# ================================================================ 校验
def check_inline(inner):
    """复用 proto/spec_check.py（不重写校验器）。"""
    sys.path.insert(0, P_PROTO)
    import spec_check                                    # noqa: E402
    with open(os.path.join(P_PROTO, "official_spec.json"), "r", encoding="utf-8") as fh:
        spec = json.load(fh)
    rep, entry = spec_check.check_one(PROTOCOL, inner, spec, "<generated>")
    return rep, entry


def print_check(inner, label=""):
    rep, entry = check_inline(inner)
    kinds = {}
    for k, _p, _d in rep.warns:
        kinds[k] = kinds.get(k, 0) + 1
    out("spec_check      : %s  FAIL %d / WARN %d %s" % (
        "PASS" if not rep.fails else "FAIL", len(rep.fails), len(rep.warns),
        ("(" + ", ".join("%s=%d" % kv for kv in sorted(kinds.items())) + ")") if kinds else ""))
    for k, p, d in rep.fails[:20]:
        out("  FAIL [%s] %s  %s" % (k, p, d))
    return rep


# ================================================================ 模式：explain-variants
def cmd_explain_variants(_a):
    """三份官方抓包逐键对比（TEST_8000.md §1 的可复现命令）。"""
    out("=" * 78)
    out("8000 三个变体：官方抓包逐键对比")
    out("=" * 78)
    rows = {}
    tops = {}
    for ev, info in sorted(OFFICIAL.items(), key=lambda kv: (kv[0] is not None, kv[0] or 0)):
        p = os.path.join(P_CAPTURE, "%s_%s_api_mission_list.response.json"
                         % (info["file"], PROTOCOL))
        if not os.path.exists(p):
            out("!! 找不到抓包: %s" % p)
            return 3
        with open(p, "r", encoding="utf-8") as fh:
            d = json.load(fh)
        inner = d["inner"]
        tops[ev] = list(inner.keys())
        per = {}
        for k, v in inner.items():
            s = json.dumps({k: v}, ensure_ascii=False, separators=(",", ":"))
            per[k] = len(s.encode("utf-8")) - (len(k) + 3)
        rows[ev] = {"meta": d.get("meta") or {}, "per": per,
                    "inner": len(d["plain"].encode("utf-8")),
                    "counts": {k: (len(v) if isinstance(v, (list, dict)) else None)
                               for k, v in inner.items()}}

    out("")
    out("① 顶层键")
    for ev in tops:
        out("   EventContentId=%-7s %d 键: %s" % (ev, len(tops[ev]), ", ".join(tops[ev])))
    same = all(tops[e] == tops[None] for e in tops)
    out("   → 三份顶层键%s" % ("完全相同（含键序）" if same else "不同 !!"))

    out("")
    out("② 逐键字节数")
    keys = tops[None]
    evs = sorted(rows, key=lambda e: (e is not None, e or 0))
    out("   %-28s %10s %10s %10s  %12s" % ("键", *["%s" % (e if e else "null") for e in evs],
                                           "变化量(849-全量)"))
    for k in keys:
        vals = [rows[e]["per"][k] for e in evs]
        out("   %-28s %10d %10d %10d  %+12d" % (k, vals[0], vals[1], vals[2], vals[1] - vals[0]))

    out("")
    out("③ 数组/对象元素数")
    for e in evs:
        c = rows[e]["counts"]
        out("   EventContentId=%-7s HistoryDBs=%-5s ProgressDBs=%-5s MHU=%-4s COMI=%-4s" % (
            e, c.get("HistoryDBs"), c.get("ProgressDBs"),
            c.get("MissionHistoryUniqueIds"), c.get("ClearedOriginalMissionIds")))
    out("   （DailySuddenMissionInfo 三份都是 {\"Id\":1606}，1 键）")

    out("")
    out("④ 尺寸（resp_bytes=wire；inner=outer.packet 才是结构口径）")
    for e in evs:
        info = OFFICIAL[e]
        out("   EventContentId=%-7s wire=%-7d inner=%-7d  wire/inner=%.3f" % (
            e, info["wire"], info["inner"], info["wire"] / float(info["inner"])))
    out("   注：报告 102 引用的 268,396 B 是 wire；解密后的 inner 只有 183,441 B。")
    out("")
    out("⑤ 结论：差异只在 ProgressDBs(+连带两个 id 列表)，由请求的 EventContentId 触发")
    out("   全量 1240 → 849 只给 39 → 10838 只给 35；三份 HistoryDBs 都是 null。")
    return 0


# ================================================================ 模式：selfcheck
def cmd_selfcheck(_a):
    """复验：Category 槽位一致性 + 官方 1240 归属 + 事件过滤集合相等。"""
    cat = Catalog()
    ok = True
    out("=" * 78)
    out("① Category 槽位 == SQL 行内 Category（全表，不是样本）")
    out("=" * 78)
    for tname, info in TABLES.items():
        total = same = 0
        expected = {"MissionDBSchema": None, "GuideMissionDBSchema": 4,
                    "EventContentMissionDBSchema": None, "MiniGameMissionDBSchema": None}[tname]
        for m in cat._by_uid.values():
            if m.table != tname:
                continue
            total += 1
            if expected is not None:
                same += 1 if m.category == expected else 0
        if expected is not None:
            out("   %-30s f%-2d == Category : %d/%d" % (tname, info["cat_slot"], same, total))
            ok = ok and same == total
        else:
            cnt = {}
            for m in cat._by_uid.values():
                if m.table == tname:
                    cnt[m.category] = cnt.get(m.category, 0) + 1
            out("   %-30s f%-2d 分布        : %s（和=%d）" % (
                tname, info["cat_slot"],
                ", ".join("cat%d=%d" % kv for kv in sorted(cnt.items())), sum(cnt.values())))
            ok = ok and sum(cnt.values()) == total

    out("")
    out("② 目录规模与 Category 分布")
    out("=" * 78)
    out("   任务总数 %d" % len(cat))
    for c, n in cat.category_counts().items():
        out("   cat%-3d n=%-5d → %s" % (c, n, CATEGORY_TO_TABLE.get(c, "未路由!!")))

    out("")
    out("③ 官方 08 的 1240 条任务，是否全部能按 Category 找到表")
    out("=" * 78)
    p = os.path.join(P_CAPTURE, "08_%s_api_mission_list.response.json" % PROTOCOL)
    if not os.path.exists(p):
        out("   !! 找不到抓包: %s" % p)
        return 3
    with open(p, "r", encoding="utf-8") as fh:
        official = json.load(fh)["inner"]["ProgressDBs"]
    hit = miss = wrong_tbl = 0
    per_tbl = {}
    for it in official:
        m = cat.get(it["MissionUniqueId"])
        if m is None:
            miss += 1
            continue
        hit += 1
        per_tbl[m.table] = per_tbl.get(m.table, 0) + 1
        if m.category != it["Category"]:
            wrong_tbl += 1
    out("   有归属 %d/%d，缺 %d；行内 Category 与表槽位不符 %d" % (
        hit, len(official), miss, wrong_tbl))
    for t, n in sorted(per_tbl.items()):
        out("     %-30s %d" % (t, n))
    ok = ok and hit == len(official) and wrong_tbl == 0

    out("")
    out("④ 事件过滤：官方 39 / 35 是否与表集合完全相等")
    out("=" * 78)
    for ev, fname in ((849, "10"), (10838, "11")):
        q = os.path.join(P_CAPTURE, "%s_%s_api_mission_list.response.json" % (fname, PROTOCOL))
        with open(q, "r", encoding="utf-8") as fh:
            off_uids = {x["MissionUniqueId"] for x in json.load(fh)["inner"]["ProgressDBs"]}
        tab_uids = {m.uid for m in cat.by_event(ev)}
        eq = off_uids == tab_uids
        ok = ok and eq
        out("   EventContentId=%-6d 官方 %-3d  表 %-3d  集合相等=%s%s" % (
            ev, len(off_uids), len(tab_uids), eq,
            "" if eq else "  差集 官-表=%s 表-官=%s" % (
                sorted(off_uids - tab_uids)[:6], sorted(tab_uids - off_uids)[:6])))

    out("")
    out("⑤ ProgressParameters key 规则复验（cat8，官方 56 条）")
    out("=" * 78)
    bad = 0
    tot = 0
    for ev, fname in ((849, "10"), (10838, "11")):
        q = os.path.join(P_CAPTURE, "%s_%s_api_mission_list.response.json" % (fname, PROTOCOL))
        with open(q, "r", encoding="utf-8") as fh:
            off = json.load(fh)["inner"]["ProgressDBs"]
        for it in off:
            m = cat.get(it["MissionUniqueId"])
            if m is None or m.category != 8:
                continue
            tot += 1
            mine = set(pp_for(m, cat).keys())
            theirs = set(it["ProgressParameters"].keys())
            if mine != theirs:
                bad += 1
                out("     不符 uid=%d 我们=%s 官方=%s" % (m.uid, sorted(mine), sorted(theirs)))
    out("   cat8 PP key：%d/%d 与官方一致" % (tot - bad, tot))
    ok = ok and bad == 0

    cat.close()
    out("")
    out("=" * 78)
    out("selfcheck: %s" % ("PASS" if ok else "FAIL"))
    out("=" * 78)
    return 0 if ok else 1


# ================================================================ 模式：emit-catalog
def cmd_emit_catalog(args):
    """导出服务端运行时用的目录（供 patch_8000.py 注入的代码读取）。

    每行 = [uid, category, event_content_id, f15, f16]
      event_content_id = 0 表示无活动归属
      f15 / f16        = 0 表示槽位缺席（f16 是 cat8 的进度类型判别位，见文件头 §五）
    """
    cat = Catalog()
    rows = []
    for m in sorted(cat._by_uid.values(), key=lambda x: x.uid):
        rows.append([m.uid, m.category,
                     m.event_id if m.event_id is not None else 0,
                     m.f15 if m.f15 is not None else 0,
                     m.f16 if m.f16 is not None else 0])
    doc = {
        "_meta": {
            "protocol": PROTOCOL,
            "protocol_name": PROTOCOL_NAME,
            "purpose": "Mission_List(8000) 目录：[uid, category, event_content_id, f15, f16]",
            "tables": sorted(TABLES.keys()),
            "count": len(rows),
            "category_to_table": {str(k): v for k, v in sorted(CATEGORY_TO_TABLE.items())},
            "note": "event_content_id=0 无活动归属；f15/f16=0 表示槽位缺席",
        },
        "rows": rows,
    }
    text = json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
    with open(args.emit_catalog, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    cat.close()
    out("写出目录: %s (%d 字节, %d 条任务)" % (
        args.emit_catalog, os.path.getsize(args.emit_catalog), len(rows)))
    return 0


# ================================================================ 主流程
def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Mission_List(8000) 生成器：按账号状态 + Category 路由，区分三种请求变体",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("用法\n────", 1)[-1])
    ap.add_argument("--account-id", "--server-id", dest="account_id", type=int,
                    default=DEFAULT_ACCOUNT, help="AccountServerId（默认 %d）" % DEFAULT_ACCOUNT)
    ap.add_argument("--event-content-id", type=int, default=None,
                    help="请求里的 EventContentId；给了就走**事件变体**（纯表驱动）")
    ap.add_argument("--profile", choices=("seed", "empty"), default="seed",
                    help="全量变体的新号策略：seed=日/周常一批未完成(默认) / empty=进度全空")
    ap.add_argument("--out", default=None, help="输出文件（官方解密格式 {meta,plain,inner}）")
    ap.add_argument("--now", default=None,
                    help="固定时间 UTC YYYY-MM-DDTHH:MM:SS，不传=当前；同一天内结果不变")
    ap.add_argument("--request-id", default=None, help="不传=uuid4")
    ap.add_argument("--mxtoken", default=None, help="不传=由 account_id 派生 64 字符 base64")
    ap.add_argument("--reset-hour", type=int, default=RESET_HOUR,
                    help="日重置小时（默认 %d，证据见文件头 §六）" % RESET_HOUR)
    ap.add_argument("--daily-sudden-id", type=int, default=SEED_SUDDEN_ID,
                    help="DailySuddenMissionInfo.Id（默认 %d，3 份抓包恒为此值）" % SEED_SUDDEN_ID)
    ap.add_argument("--explain-variants", action="store_true",
                    help="对比三份官方抓包并打印逐键差异")
    ap.add_argument("--selfcheck", action="store_true",
                    help="复验 Category 槽位 / 1240 归属 / 事件集合 / PP key")
    ap.add_argument("--emit-catalog", metavar="PATH", default=None,
                    help="导出服务端运行时目录 JSON")
    ap.add_argument("--quiet", action="store_true", help="只输出结果行")
    args = ap.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    if args.explain_variants:
        return cmd_explain_variants(args)
    if args.selfcheck:
        return cmd_selfcheck(args)
    if args.emit_catalog:
        return cmd_emit_catalog(args)

    now = None
    if args.now:
        now = _dt.datetime.strptime(args.now, "%Y-%m-%dT%H:%M:%S")

    inner, issues, meta = build_response(
        args.account_id, profile=args.profile,
        event_content_id=args.event_content_id, now=now,
        request_id=args.request_id, mxtoken=args.mxtoken,
        reset_hour=args.reset_hour, daily_sudden_id=args.daily_sudden_id)

    if args.out:
        size = write_output(inner, args.out, meta)
    else:
        size = None

    if not args.quiet:
        out("-" * 78)
        out("协议 %d (%s)" % (PROTOCOL, PROTOCOL_NAME))
        out("账号            : %d" % args.account_id)
        out("变体            : %s%s" % (
            meta["variant"],
            "" if args.event_content_id is None else "  EventContentId=%d" % args.event_content_id))
        out("profile         : %s" % args.profile)
        out("ProgressDBs     : %d 条" % meta["progress_count"])
        out("StartDate       : %s" % meta["start_date"])
        out("inner 明文      : %d bytes" % meta["inner_bytes"])
        out("wire 下界(b64)  : %d bytes（真实 wire ≈ ×1.46~1.49，见 b64_bytes 注释）"
            % b64_bytes(inner))
        if size:
            out("输出文件        : %s (%d bytes, 缩进格式)" % (args.out, size))
        out("conform 记账    : %s" % issues.summary())
        if issues.dropped:
            out("  !! spec 未定义的键被丢弃（说明 spec 不完整）:")
            for p, k, d in issues.dropped[:20]:
                out("     %s.%s  %s" % (p, k, d))
        if issues.forced:
            out("  !! 被强制的节点:")
            for p, d in issues.forced[:20]:
                out("     %s  %s" % (p, d))
        print_check(inner)
        ref = OFFICIAL.get(args.event_content_id)
        if ref:
            out("官方对照        : %s_ inner=%d 条数=%d  我们 inner=%d 条数=%d  差 %+d B" % (
                ref["file"], ref["inner"], ref["progress"],
                meta["inner_bytes"], meta["progress_count"],
                meta["inner_bytes"] - ref["inner"]))
    else:
        out("%s %d %d %d" % (meta["variant"], args.event_content_id or 0,
                             meta["progress_count"], meta["inner_bytes"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
