#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen1017.py — 1017 Account_LoginSync 动态生成器（可部署版）。

输入：`(account_state, session)`          输出：完整 1017 dict（35 个顶层键）

    入参形态
    --------
    account_state : dict | None
        账号状态。**只认白名单键**（见 KNOWN_STATE_KEYS），出现就覆盖，
        不出现就回落到 `initial_state_rules.json` 的 server_apply_skeleton（新号初始态）。
        任一键都不给 == 全新号。这是"动态"的唯一来源：库里有什么就发什么。
    session : dict | None
        真实的 SessionKey，形如 {"AccountServerId": <int>, "MxToken": "<64 字符 base64>"}。
        它是 5 个信封字段里 SessionKey 的唯一来源；同时决定 ServerId 的取值域
        （ServerKey.AccountServerId 优先于 account_state["server_id"]）。
    request_id : str | None
        不传 = uuid4。**部署时必须由调用方传进来**，
        因为外层 requestid（cn_wire 明文里的 requestid）必须与 inner RequestId 逐字节相同。

    骨架来源
    --------
    顶层键集合、键序、每个子回包的字段形状，**全部**从 official_spec.json 的 1017 条目投影出来：

        for key, field_spec in spec.schema(1017)["fields"]:
            if key in 信封字段:            continue        # 由 envelope() 填
            if field_spec["type"] == "null": 值 = None      # 官方只见过 null
            elif key 有注册的 body 构造器:     值 = 构造器(state)
            else:                            值 = {}        # spec 允许的空结构

    ⇒ spec 里多出一个子回包、或少一个，这里**不用改一行代码**；
      数据填多了/填错了会被 specgen.conform 丢弃或记账（issues.dropped / issues.forced），
      所以「生成物必然 PASS spec_check」是被构造保证的，不是手调出来的。

    三条硬口径（与 report/102 §4 一致）
    ----------------------------------
    1. 25/26 个具名子回包**自带信封，但全是零值**：
       Protocol 0 / SessionKey{0,""} / ServerTimeTicks 0 / ServerNotification 0 / RequestId ""。
       本文件只给子回包的 body，信封由 spec 的默认值自动补成零值。
    2. **绝不发 Responses 数组**。1017 是 25 条被打包成"具名兄弟字段"，不是列表。
    3. `ItemListResponse` / `CafeGetInfoResponse.CafeDB` / `TimeAttackDungeonLoginResponse.PreviousRoomDB`
       / `MultiFloorRaidSyncResponse.MultiFloorRaidDBs` —— spec 里 type=null（官方从未见过非空），
       **只能发 null**。发 {} 会 FAIL。

    4 个"双身份" DTO（5000 / 6000 / 29002 / 30041）
    -----------------------------------------------
    它们既是 1017 的子回包，又是独立 RPC。本文件里 **同一个函数对象** 两处复用：
        BODY_BY_PROTO[5000] is BODY_BY_NAME["EchelonListResponse"]  → True
    `build_standalone(proto)` 用同一个 body 构造器拼独立 RPC 的响应，可独立 spec_check。

    用法
    ----
        # 渲染一个全新号（验收命令）
        python work/ba/server/deploy/gen1017.py --account-id 10015354380 --out report/_tmp/t1017.json

        # 带真实 session + 固定 requestid
        python work/ba/server/deploy/gen1017.py --account-id 10015354380 \
            --session-json '{"AccountServerId":10015354380,"MxToken":"<REDACTED_TOKEN>"}' \
            --request-id 11111111-2222-3333-4444-555555555555 --out /tmp/t1017.json

        # 从库里的账号状态文件渲染
        python work/ba/server/deploy/gen1017.py --state-json account.json --out /tmp/t1017.json

        # 顺带把 4 个独立 RPC 也渲染出来（证明构造器复用）
        python work/ba/server/deploy/gen1017.py --account-id 1 --out /tmp/t1017.json --standalones
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import sys
import uuid

PROTO = 1017
DTO_NAME = "Account_LoginSync"

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- 依赖定位
# 本生成器只 import 一个外部模块：D 线已验证的 spec 引擎 specgen.py。
# 部署到 /www/wwwroot/bapatch/tools/ 时把 specgen.py 一起放进去即可（见 TEST_1017.md）。
SPECGEN_ENV = "BA_SPECGEN_DIR"
SPEC_ENV = "BA_SPEC_PATH"
RULES_ENV = "BA_RULES_PATH"
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


def _bootstrap_specgen():
    """把 specgen.py 所在目录放进 sys.path，返回该目录（找不到返回 None）。"""
    cands = []
    env = os.environ.get(SPECGEN_ENV)
    if env:
        cands.append(env)
    for d in _ancestors(HERE) + _ancestors(os.getcwd(), 4):
        cands.extend([
            d,
            os.path.join(d, "work", "ba", "server", "prototype"),
            os.path.join(d, "prototype"),
            os.path.join(d, "tools"),
        ])
    seen = set()
    for c in cands:
        c = os.path.abspath(c)
        if c in seen:
            continue
        seen.add(c)
        if os.path.isfile(os.path.join(c, "specgen.py")):
            if c not in sys.path:
                sys.path.insert(0, c)
            sys.dont_write_bytecode = True
            return c
    return None


_SPECGEN_DIR = _bootstrap_specgen()
if _SPECGEN_DIR is None:
    sys.stderr.write(
        "[gen1017] 找不到 specgen.py。把它放到本文件同目录，或设 %s=<dir>。\n" % SPECGEN_ENV)
    raise SystemExit(2)

import specgen as G  # noqa: E402  （spec 驱动引擎：Spec / Issues / MasterData / 时间工具）


def _find_data_files():
    """定位 official_spec.json / initial_state_rules.json / ExcelDB.db。

    优先级：环境变量 > 从本文件向上找 repo 布局 > 从 cwd 向上找 > 与 specgen 同级。
    """
    want = {
        "spec": (SPEC_ENV, "official_spec.json", ("work", "ba", "proto")),
        "rules": (RULES_ENV, "initial_state_rules.json", ("work", "ba", "proto")),
        "exceldb": (EXCELDB_ENV, "ExcelDB.db", ("work", "ba", "data")),
    }
    roots = _ancestors(HERE) + _ancestors(os.getcwd(), 4)
    if _SPECGEN_DIR:
        roots += _ancestors(_SPECGEN_DIR, 6)
    out = {}
    for slot, (env, fname, rel) in want.items():
        val = os.environ.get(env)
        if val and os.path.isfile(val):
            out[slot] = os.path.abspath(val)
            continue
        found = None
        for d in roots:
            p = os.path.join(d, *rel, fname)
            if os.path.isfile(p):
                found = os.path.abspath(p)
                break
        if found is None:
            for d in roots:
                p = os.path.join(d, fname)
                if os.path.isfile(p):
                    found = os.path.abspath(p)
                    break
        out[slot] = found
    return out


DATA = _find_data_files()

# ---------------------------------------------------------------- 常量
ZERO_TIME = G.ZERO_TIME                       # "0001-01-01T00:00:00"
DOTNET_EPOCH = _dt.datetime(1, 1, 1)
DEFAULT_SERVER_ID = 10015354380               # 官方那个号；CLI 不给 --account-id 时用它

# ParcelType 枚举（只有这几个有证据，见 initial_state_rules.not_found 第 4 条）
PARCEL_TYPE_CHARACTER = 1     # 规则表确认 Character=1
PARCEL_TYPE_FURNITURE = 13    # 规则表未给 → 官方 FurnitureDBs 27 行恒定值 13（枚举常量）
PARCEL_TYPE_EMBLEM = 20       # 规则表确认 Emblem=20

# 商店 banner 售卖区间（合成）。ShopRecruitDBSchema 的日期是 int 日期码，解码规则未找到
# → 给「长期开放」区间，保证客户端任何时刻都视为在售。见 rules q10 / report102 §9。
SHOP_SALES_START = "2000-01-01T00:00:00"
SHOP_SALES_END = "2099-12-31T23:59:59"

ENVELOPE_FIELDS = ("Protocol", "SessionKey", "ServerTimeTicks", "ServerNotification", "RequestId")
ZERO_ENVELOPE = {
    "Protocol": 0,
    "SessionKey": {"AccountServerId": 0, "MxToken": ""},
    "ServerTimeTicks": 0,
    "ServerNotification": 0,
    "RequestId": "",
}

# 4 个「双身份」DTO：既是 1017 的子回包，又是独立 RPC（report/102 §4.3）
DUAL_RPC_PROTOS = (5000, 6000, 29002, 30041)

# account_state 认得的键（白名单）。多出来的键会被记进 ignored_state_keys，
# 方便部署时发现拼错的字段名 —— 而不是静默发一个空响应。
KNOWN_STATE_KEYS = frozenset([
    # 身份 / 信封
    "server_id", "account_id", "AccountServerId", "account_level", "mxtoken", "<REDACTED_TOKEN>", "now",
    # 角色 / 装备 / 道具
    "characters", "equipments", "gears", "weapons", "tss_characters",
    # 编队
    "echelons",
    # 咖啡厅
    "cafes", "furnitures", "cafe_rank",
    # 货币
    "currency", "currency_dict", "currency_update_times", "academy_location_rank_sum",
    # 附件 / 徽章 / 贴纸
    "emblems", "attached_emblem_unique_id", "stickers_unused_ids", "stickers_used_ids",
    # 商店
    "shop_recruits", "shop_schedule",
    # 剧情 / 关卡进度
    "scenario_history_dbs", "scenario_group_history_dbs", "scenario_collection_dbs",
    "campaign_chapter_clear_reward_history_dbs", "stage_history_dbs", "current_scenario_id",
    # 其它进度
    "momotalk_outlines", "favor_schedule_records",
    "permanent_event_ids", "permanent_event_dbs",
    "content_sweep_presets",
    "account_level_reward_ids",
    "friend_count", "friend_code",
    "arena_player_info", "raid_login", "eliminate_raid_login",
    "last_cleared_difficulty", "purchase_counts",
    "clan", "memory_lobby_dbs",
    "pickup_first_get_history_dbs",
])


# ================================================================ 小工具
def server_time_ticks(dt):
    """.NET 100ns ticks（自 0001-01-01）。单位已用官方 24000 实测比对确认。"""
    return G.server_time_ticks(dt)


def fmt_time(dt, frac=3):
    """RFC3339Nano 风格，小数位尾零裁掉（官方就这么发，如 .479 / 无小数）。"""
    return G.fmt_time(dt, frac)


def parse_time(s):
    if isinstance(s, _dt.datetime):
        return s
    s = str(s).strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return _dt.datetime.strptime(s, fmt)
        except ValueError:
            continue
    raise ValueError("无法解析时间: %r（要 YYYY-MM-DDTHH:MM:SS）" % (s,))


def _sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ================================================================ 三层体积
# 官方 meta.resp_bytes 是**最外层**（HTTP body）口径，不是 inner JSON 的字数：
#   inner  JSON          = json.dumps(obj, separators=(',',':'))
#   outer  明文          = {"protocol","packet":"<inner 作为字符串，引号被转义>","requestid"}
#   wire   HTTP body     = base64( AES-256-CBC(outer) + 32B key )
# 校验：旧 1017 固定包 → inner 216 / outer 331 / wire **492**（= 任务里说的 492 B）；
#       回放官方状态 → inner 167,287 / outer 185,068 / wire **246,808**（= 官方 meta.resp_bytes）。
def measure(obj, protocol_name=DTO_NAME, request_id=None):
    """返回 {inner, outer, wire} 三层字节数。只算长度，不做加密。"""
    rid = request_id or obj.get("RequestId") or ("0" * 8 + "-0000-4000-8000-" + "0" * 12)
    inner = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    outer = json.dumps({"protocol": protocol_name, "packet": inner, "requestid": rid},
                       ensure_ascii=False, separators=(",", ":"))
    ct = 16 * ((len(outer.encode("utf-8")) + 15) // 16)          # PKCS7 补齐到 16
    wire = 4 * ((ct + 32 + 2) // 3)                              # base64(ct + 32B key)
    return {"inner": len(inner.encode("utf-8")),
            "outer": len(outer.encode("utf-8")),
            "wire": wire}



# ================================================================ 账号状态
class AccountState(object):
    """一个账号的 1017 视图。每个 getter 都是「account_state 覆盖 > 规则回落」的纯函数。

    设计约束：所有 getter 必须是**纯函数**（同一 state → 同一输出），
    因为 ServerId 的分配要跨请求稳定（编队引用角色时靠的就是这个稳定性）。
    """

    KIND_CHARACTER = 1
    KIND_ITEM = 2
    KIND_FURNITURE = 3
    KIND_EQUIPMENT = 4

    def __init__(self, account_state, session, rules, master,
                 request_id=None, now=None):
        data = dict(account_state or {})
        sess = dict(session or {})

        self.notes = []          # 未找到 / 推断 / 冲突，逐条记下来给 --stats 打
        self.ignored_state_keys = sorted(k for k in data if k not in KNOWN_STATE_KEYS)

        # ---- server_id：SessionKey.AccountServerId 权威（CafeDBId / AccountId 全靠它算）
        sid_data = data.get("server_id") or data.get("account_id") or data.get("AccountServerId") or 0
        sid_sess = sess.get("AccountServerId") or 0
        if sid_sess and sid_data and int(sid_sess) != int(sid_data):
            self.notes.append("session.AccountServerId=%s 与 account_state.server_id=%s 冲突，取 session"
                              % (sid_sess, sid_data))
        self.server_id = int(sid_sess or sid_data or DEFAULT_SERVER_ID)

        # ---- 时间
        n = now or data.get("now")
        if isinstance(n, str):
            n = parse_time(n)
        if n is None:
            n = _dt.datetime.now(_dt.timezone.utc).replace(tzinfo=None)   # 3.12 无 DeprecationWarning
        if n.tzinfo is not None:
            n = n.astimezone(_dt.timezone.utc).replace(tzinfo=None)
        self.now = n
        self.ticks = server_time_ticks(n)          # 动态字段 #1

        # ---- request id（动态字段 #2）
        self.request_id = str(request_id or uuid.uuid4())

        # ---- MxToken（NxToken 不参与 1017 的业务语义，但要与 1002 一致）
        self.mxtoken = (data.get("mxtoken") or data.get("MxToken")
                        or sess.get("MxToken")
                        or self._derive_mxtoken(self.server_id))

        # ---- 数据
        self.rules = rules
        self.master = master
        self.skeleton = rules["server_apply_skeleton"]
        self.data = data
        self._char_server = {}                      # CharacterUniqueId -> ServerId
        self.comfort_value = 0

        # ---- 账号等级（官方那个号 AccountLevel=1，见 TEST_1017.md）
        self.account_level = int(data.get("account_level")
                                 or self.skeleton["AccountCurrencyDB"]["AccountLevel"])

    # ------------------------------------------------------------ 派生
    @staticmethod
    def _derive_mxtoken(server_id):
        """48 字节 sha384 → base64 正好 64 字符，与官方 MxToken 长度一致。"""
        import base64
        return base64.b64encode(
            hashlib.sha384(("ba-private-server:%d" % int(server_id)).encode()).digest()
        ).decode("ascii")

    def obj_id(self, kind, index):
        """账号内唯一的对象 ServerId。

        官方 ServerId 是 7~8 位服务端自增号，没有跨账号含义；这里用
        「账号id 打头 + kind + 序号」，保证多账号共库不撞号、int64 不溢出，
        并且**同一个账号每次调用都得到同一个值**（编队/装备交叉引用靠它）。
        """
        return self.server_id * 100000 + kind * 10000 + int(index)

    def session_key(self, session):
        """信封里的 SessionKey。给了真 session 就原样用（spec 会滤掉多余键）。"""
        sess = dict(session or {})
        if sess.get("AccountServerId") and "MxToken" in sess:
            return sess
        return {"AccountServerId": self.server_id, "MxToken": self.mxtoken}

    def envelope(self, session):
        """顶层 5 个信封字段。子回包的信封由 spec 默认值补成零值。"""
        return {
            "Protocol": PROTO,
            "SessionKey": self.session_key(session),
            "ServerTimeTicks": self.ticks,          # 动态
            "ServerNotification": 0,
            "RequestId": self.request_id,           # 动态（必须 == 外层 requestid）
        }

    def ts(self, dt=None, frac=3):
        return fmt_time(dt or self.now, frac)

    # ------------------------------------------------------------ 角色
    def characters(self):
        """CharacterListResponse.CharacterDBs。

        默认 = server_apply_skeleton.CharacterDBs 的 4 个初始角色
        （13010 优香 / 16003 铃美 / 13003 莲见 / 26000 千夏）。
        ServerId 用 obj_id 派生；EquipmentServerIds 默认空（新号没装备）。
        """
        rows = self.data.get("characters")
        if rows is None:
            rows = self.skeleton["CharacterDBs"]
        out = []
        for i, c in enumerate(rows, start=1):
            sid = c.get("ServerId") or self.obj_id(self.KIND_CHARACTER, i)
            c = dict(c)
            c.setdefault("Type", PARCEL_TYPE_CHARACTER)     # ParcelType.Character = 1
            c["ServerId"] = sid
            self._char_server[int(c["UniqueId"])] = int(sid)
            out.append(c)
        return out

    def char_sid(self, unique_id):
        """CharacterUniqueId → ServerId。必须先跑过 characters()。"""
        uid = int(unique_id)
        if uid not in self._char_server:
            raise KeyError("引用了一个不存在的角色 UniqueId=%d（现有 %s）"
                           % (uid, sorted(self._char_server)))
        return self._char_server[uid]

    # ------------------------------------------------------------ 编队
    def echelons(self):
        """EchelonListResponse.EchelonDBs（== 独立 RPC 5000 Echelon_List 的 body）。

        默认 = rules q5：1 条编队，主槽 4 + 支援槽 2 + 3 个 SkillCardMulligan + 6 个 CombatStyleIndex。
        规则表写的是 CharacterUniqueId，落库要换成 ServerId；空槽补 0，**不缩短数组**
        （官方 8 条编队形状完全一致，支援槽就是 [x,0] / [0,0]）。
        """
        if self.data.get("echelons") is not None:
            rows = []
            for e in self.data["echelons"]:
                e = dict(e)
                e.setdefault("AccountServerId", self.server_id)
                if e.get("LeaderServerId") is None and e.get("LeaderCharacterUniqueId"):
                    e["LeaderServerId"] = self.char_sid(e["LeaderCharacterUniqueId"])
                if e.get("MainSlotServerIds") is None and e.get("MainSlotCharacterUniqueIds"):
                    ids = [self.char_sid(u) for u in e["MainSlotCharacterUniqueIds"]]
                    e["MainSlotServerIds"] = ids + [0] * (4 - len(ids))
                if e.get("SupportSlotServerIds") is None and e.get("SupportSlotCharacterUniqueIds"):
                    ids = [self.char_sid(u) for u in e["SupportSlotCharacterUniqueIds"]]
                    e["SupportSlotServerIds"] = ids + [0] * (2 - len(ids))
                # 这三个是「输入侧的便利键」，不是 spec 里的字段 → 用完就摘掉，
                # 否则 conform 会把它们记成 dropped_keys（噪音，且会被误当成 spec 不完整）。
                for helper in ("LeaderCharacterUniqueId", "MainSlotCharacterUniqueIds",
                               "SupportSlotCharacterUniqueIds"):
                    e.pop(helper, None)
                rows.append(e)
            return rows

        e = self.rules["q5_initial_echelons"]["initial"]["echelon"]
        main_ids = list(e["MainSlotCharacterUniqueIds"])
        sup_ids = list(e["SupportSlotCharacterUniqueIds"])
        main = [self.char_sid(u) for u in main_ids] + [0] * (4 - len(main_ids))
        sup = [self.char_sid(u) for u in sup_ids] + [0] * (2 - len(sup_ids))
        return [{
            "AccountServerId": self.server_id,
            "EchelonType": int(e["EchelonType"]),
            "EchelonNumber": int(e["EchelonNumber"]),
            "ExtensionType": int(e["ExtensionType"]),
            "LeaderServerId": self.char_sid(e["LeaderCharacterUniqueId"]),
            "MainSlotServerIds": main,
            "SupportSlotServerIds": sup,
            "TSSInteractionServerId": int(e["TSSInteractionServerId"]),
            "UsingFlag": int(e["UsingFlag"]),
            "SkillCardMulliganCharacterIds": list(e["SkillCardMulliganCharacterIds"]),
            "CombatStyleIndex": list(e["CombatStyleIndex"]),
        }]

    # ------------------------------------------------------------ 咖啡厅
    def _furniture_rows(self, cafe_db_id, start_seq):
        """11 件默认家具（rules q9.initial.FurnitureDBs）。

        Type=13 取自官方 FurnitureDBs 27 行的恒定枚举值（规则表未给家具 ParcelType）。
        Rotation 只在该行表里有值时才发（proto3 可选标量 presence；官方 2/27 次有）。
        """
        rows, comfort_ids = [], []
        for i, f in enumerate(self.rules["q9_cafe"]["initial"]["FurnitureDBs"]):
            fid = int(f["FurnitureId"])
            comfort_ids.append(fid)
            row = {
                "Type": PARCEL_TYPE_FURNITURE,
                "ServerId": self.obj_id(self.KIND_FURNITURE, start_seq + i),
                "UniqueId": fid,
                "StackCount": 1,
                "Location": int(f["Location"]),
                "PositionX": float(f.get("PositionX") or 0.0),
                "PositionY": float(f.get("PositionY") or 0.0),
                "ItemDeploySequence": i,
                "CafeDBId": cafe_db_id,
            }
            if f.get("Rotation") is not None:
                row["Rotation"] = int(float(f["Rotation"]))
            rows.append(row)
        return rows, comfort_ids

    def cafes(self):
        """CafeGetInfoResponse 的 (CafeDBs, 顶层 FurnitureDBs)。

        默认 = rules q9：2 个咖啡厅，各带同一套 11 件默认家具。
        CafeDBId = AccountServerId * 10 + CafeId（官方实测 100153543801 / 100153543802）。
        ComfortValue = Σ FurnitureDBSchema.f24（11 件各 20 → 220），已用官方 cafe2（Rank1）
        交叉验证闭合。顶层 FurnitureDBs 是「账号拥有的全部家具」：新号 22 件
        （官方 27 = cafe1 的 14 + cafe2 的 11 + 2 件未摆放，那 2 件新号没有）。
        """
        if self.data.get("cafes") is not None:
            cafes = [dict(c) for c in self.data["cafes"]]
            furniture = [dict(f) for f in (self.data.get("furnitures") or [])]
            for c in cafes:
                c.setdefault("AccountId", self.server_id)
                c.setdefault("CafeDBId", self.server_id * 10 + int(c.get("CafeId", 1)))
            return cafes, furniture

        cafes, all_furniture, comfort_ids = [], [], []
        seq = 1
        for c in self.rules["q9_cafe"]["initial"]["CafeDBs"]:
            cafe_id = int(c["CafeId"])
            cafe_db_id = self.server_id * 10 + cafe_id
            furn, ids = self._furniture_rows(cafe_db_id, seq)
            seq += len(furn)
            all_furniture.extend(furn)
            comfort_ids.extend(ids)
            cafes.append({
                "CafeDBId": cafe_db_id,                       # 动态（随 server_id）
                "CafeId": cafe_id,
                "AccountId": self.server_id,                  # 动态
                "CafeRank": int(self.data.get("cafe_rank") or c["CafeRank"]),
                "LastUpdate": self.ts(),                      # 动态（时间）
                "LastSummonDate": c["LastSummonDate"],        # 零值 = 从未召唤
                "IsNew": True,                                # 新号首次登录：内容全部未读
                "CafeVisitCharacterDBs": {},                  # 未找到访客调度规则 → 空 map
                "FurnitureDBs": furn,
                "ProductionAppliedTime": ZERO_TIME,
                "ProductionDB": {
                    "CafeDBId": cafe_db_id,
                    "ComfortValue": 0,                        # 下面用主数据覆盖
                    "AppliedDate": ZERO_TIME,
                    "ProductionParcelInfos": [],
                },
            })
        self.comfort_value, _detail = self.master.furniture_comfort(sorted(set(comfort_ids)))
        for c in cafes:
            c["ProductionDB"]["ComfortValue"] = self.comfort_value
        return cafes, all_furniture

    # ------------------------------------------------------------ 货币
    def account_currency(self):
        """AccountCurrencySyncResponse.AccountCurrencyDB。

        * CurrencyDict 必须 1..29 **全部 29 个键**（值为 0 的也在），rules q4 有反证。
        * UpdateTimeDict = 19 个「会随时间恢复」的货币的更新时间（REGENERATING_CURRENCY_IDS），
          该 19 键集合已与官方实测逐键相等。
        * AcademyLocationRankSum 与 24000 的 AcademyLocationDBs 同源（q8.suggested_minimum）。
        """
        override = self.data.get("currency") or self.data.get("currency_dict")
        if override is not None:
            cur = {str(k): int(v) for k, v in dict(override).items()}
        else:
            cur = dict(self.skeleton["AccountCurrencyDB"]["CurrencyDict"])
        for i in range(1, 30):
            cur.setdefault(str(i), 0)

        upd = self.data.get("currency_update_times")
        if upd is not None:
            upd = {str(k): str(v) for k, v in dict(upd).items()}
        else:
            upd = {str(k): self.ts(frac=9) for k in G.REGENERATING_CURRENCY_IDS}

        rank_sum = self.data.get("academy_location_rank_sum")
        if rank_sum is None:
            rank_sum = _academy_location_rank_sum(self.rules)
        return {
            "AccountLevel": self.account_level,
            "AcademyLocationRankSum": int(rank_sum),
            "CurrencyDict": cur,
            "UpdateTimeDict": upd,
        }

    # ------------------------------------------------------------ 商店
    def shop_recruits(self):
        """ShopGachaRecruitListResponse.ShopRecruits = ShopRecruitDBSchema 全部行去掉 Id 1/2/3。

        三种来源，优先级从高到低：
          1. account_state["shop_recruits"] —— 完整 529 条（每条 4 个字段），原样投影。
          2. account_state["shop_schedule"] —— {Id: {SalesStartDate, SalesEndDate, UpdateDate}}
             或 [{Id, ...}] 的排期覆盖，缺失的 Id 用下面的默认区间补。
          3. 默认：长期开放区间 2000-01-01 → 2099-12-31。
             **为什么默认不是官方排期**：ShopRecruitDBSchema 里的日期是 int 日期码，解码规则
             未找到（report102 §9），而私服的目标是让 529 个 banner **任何时刻都可售**；
             官方那套逐 banner 的上/下架窗口会让绝大多数 banner 过期不可见。
             （官方抓包里其实有全部 529 条的 4 个字段，需要时可以照 TEST_1017.md §5 抽成
              shop_schedule 传进来 —— 那样本子回包与官方逐字节相同。）
        """
        as_is = self.data.get("shop_recruits")
        if as_is is not None:
            return [dict(r) for r in as_is]

        sched = self.data.get("shop_schedule")
        if isinstance(sched, list):
            sched = {str(r.get("Id")): r for r in sched}

        out = []
        for rid in self.master.shop_recruit_ids():
            row = {"Id": rid,
                   "SalesStartDate": SHOP_SALES_START,
                   "SalesEndDate": SHOP_SALES_END,
                   "UpdateDate": ZERO_TIME}
            if sched and str(rid) in sched:
                row.update({k: v for k, v in dict(sched[str(rid)]).items() if k != "Id"})
            out.append(row)
        return out

    # ------------------------------------------------------------ 徽章
    def emblems(self):
        """AttachmentEmblemListResponse.EmblemDBs = 5 个初始徽章（q3.EmblemDBs，Type=20）。"""
        rows = self.data.get("emblems")
        if rows is None:
            rows = self.skeleton["EmblemDBs"]
        out = []
        for e in rows:
            out.append({
                "Type": int(e.get("Type", PARCEL_TYPE_EMBLEM)),
                "UniqueId": int(e["UniqueId"]),
                "ReceiveDate": e.get("ReceiveDate") or self.ts(),   # 初始发放 = 建号时间
            })
        return out

    def attached_emblem_unique_id(self):
        return int(self.data.get("attached_emblem_unique_id")
                   or self.skeleton["AccountAttachmentDB"]["EmblemUniqueId"])

    def account_level_reward_ids(self):
        """AccountLevelRewardIds = 已达到的等级奖励档位（AccountLevelRewardDBSchema，6 行）。

        表里只有 Level 30/40/45/50/55/60 六个里程碑 → 新号(1 级) 得 []。
        **未找到**：官方样本 AccountLevel=1 却给了 [1]，与「已达阈值」不自洽，语义待定；
        这里仍按唯一可从表推出的规则实现（动态：account_level 变化时该数组会变）。
        """
        if self.data.get("account_level_reward_ids") is not None:
            return [int(x) for x in self.data["account_level_reward_ids"]]
        return self.master.account_level_reward_ids(self.account_level)

    # ------------------------------------------------------------ 好友
    def friend_code(self):
        """FriendCode：官方 7 位大小写字母+数字混合（样本 slmv4wc）。

        规则未找到 → 由账号 id 确定性派生（同账号每次相同，不同账号不同）。
        """
        if self.data.get("friend_code"):
            return str(self.data["friend_code"])
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
        h = hashlib.sha256(("friend-code:%d" % self.server_id).encode()).digest()
        return "".join(alphabet[b % len(alphabet)] for b in h[:7])

    # ------------------------------------------------------------ 战队
    def clan(self):
        """ClanLoginResponse：新号未加入战队 = 全零。

        **未找到**：官方那个号在战队里，没有「不在战队」的样本可对照。
        只有「指代本账号」的字段写真值（AccountId / AttachmentDB.AccountId），
        代表角色 = 初始 Leader，徽章 = ConstCommonExcel.EmblemDefaultId。
        """
        if self.data.get("clan") is not None:
            return dict(self.data["clan"])
        leader = self.data.get("represent_character_unique_id") or 13010
        return {
            "AccountClanDB": {
                "ClanDBId": 0, "ClanName": "", "ClanChannelName": "",
                "ClanPresidentNickName": "",
                "ClanPresidentRepresentCharacterUniqueId": 0,
                "ClanPresidentRepresentCharacterCostumeId": 0,
                "ClanNotice": "", "ClanMemberCount": 0, "ClanManagerCount": 0,
                "ClanJoinOption": 0,
            },
            "AccountClanMemberDB": {
                "AccountId": self.server_id,                  # 动态
                "AccountLevel": self.account_level,
                "AccountNickName": "",                        # 未找到新号默认昵称规则
                "RepresentCharacterUniqueId": int(leader),
                "RepresentCharacterCostumeId": 0,
                "ClanDBId": 0,
                "AttendanceCount": 0,
                "ClanSocialGrade": 0,
                "JoinDate": ZERO_TIME,
                "SocialGradeUpdateTime": ZERO_TIME,
                "LastLoginDate": ZERO_TIME,
                "GameLoginDate": self.ts(),                   # 就是这次登录（动态）
                "AppliedDate": ZERO_TIME,
                "AttachmentDB": {
                    "AccountId": self.server_id,              # 动态
                    "EmblemUniqueId": self.attached_emblem_unique_id(),
                },
            },
            "ClanAssistSlotDBs": [],
        }


def _academy_location_rank_sum(rules):
    """与 24000 同源：q8.suggested_minimum 的 Rank 之和（新号 = 1）。"""
    sug = ((rules.get("q8_academy") or {}).get("initial") or {}).get("suggested_minimum") or {}
    rows = sug.get("AcademyLocationDBs") or [{"Rank": 1}]
    return sum(int(r.get("Rank", 1)) for r in rows)


# ================================================================ body 构造器
# 每个构造器只返回「子回包去掉 5 个信封字段之后的 body」。
# 4 个双身份 DTO 的构造器在 BODY_BY_PROTO 里再登记一次 —— 是**同一个函数对象**。

def _body_cafe_get_info(st):
    cafes, furniture = st.cafes()
    return {
        "CafeDB": None,        # spec: type=null（官方单数 CafeDB 恒为 null，生效的是 CafeDBs）
        "CafeDBs": cafes,
        "FurnitureDBs": furniture,
    }


def _body_account_currency_sync(st):
    return {
        "AccountCurrencyDB": st.account_currency(),
        "ExpiredCurrency": {},          # spec: observed_empty_only
    }


def _body_character_list(st):
    return {
        "CharacterDBs": st.characters(),
        "TSSCharacterDBs": [],          # 抓包 0 行 + DTO 无定义 → 未建模（report102 §9）
        "WeaponDBs": [],
    }


def _body_equipment_item_list(st):
    return {"EquipmentDBs": list(st.data.get("equipments") or [])}   # 新号无装备（q3）


def _body_character_gear_list(st):
    return {"GearDBs": list(st.data.get("gears") or [])}


def _body_echelon_list(st):
    """5000 Echelon_List 的 body —— 1017 子回包与独立 RPC 共用这一个构造器。"""
    return {"EchelonDBs": st.echelons()}


def _body_memory_lobby_list(st):
    rows = st.data.get("memory_lobby_dbs")
    if rows is None:
        rows = [{
            "Type": int(st.skeleton["MemoryLobbyDBs"][0]["Type"]),          # 8
            "ParcelInfos": None,                                           # spec: null
            "AccountServerId": st.server_id,                               # 动态
            "MemoryLobbyUniqueId": int(st.skeleton["MemoryLobbyDBs"][0]["MemoryLobbyUniqueId"]),
        }]
    return {"MemoryLobbyDBs": rows}


def _body_campaign_list(st):
    """6000 Campaign_List 的 body —— 1017 子回包与独立 RPC 共用这一个构造器。"""
    return {
        "CampaignChapterClearRewardHistoryDBs":
            list(st.data.get("campaign_chapter_clear_reward_history_dbs") or []),
        "StageHistoryDBs": list(st.data.get("stage_history_dbs") or []),
        "CurrentScenarioId": int(st.data.get("current_scenario_id") or 0),
    }


def _body_arena_login(st):
    """ArenaLoginResponse。**未找到**竞技场初始分组/段位规则 → 全部 0 + 零值时间。"""
    info = st.data.get("arena_player_info")
    if info is None:
        info = {"CurrentSeasonId": 0, "PlayerGroupId": 0, "CurrentRank": 0,
                "SeasonRecord": 0, "AllTimeRecord": 0, "CumulativeTimeReward": 0,
                "TimeRewardLastUpdateTime": ZERO_TIME,
                "BattleEnterActiveTime": ZERO_TIME,
                "DailyRewardActiveTime": ZERO_TIME}
    return {"ArenaPlayerInfoDB": dict(info)}


def _body_raid_login(st):
    """RaidLoginResponse。新号未打总力战 → 0 / false。"""
    r = st.data.get("raid_login")
    if r is None:
        r = {"SeasonType": 0, "CanReceiveRankingReward": False,
             "LastSettledRanking": 0, "LastSettledTier": 0}
    return dict(r)


def _body_craft_info_list(st):
    return {"CraftInfos": [], "ShiftingCraftInfos": [], "PresetSlotDBs": []}


def _body_clan_login(st):
    return st.clan()


def _body_momotalk_outline(st):
    """MomoTalkOutLineResponse。**未找到**初始对白/好感日程规则 → 两个都空。"""
    return {
        "MomoTalkOutLineDBs": list(st.data.get("momotalk_outlines") or []),
        "FavorScheduleRecords": dict(st.data.get("favor_schedule_records") or {}),
    }


def _body_scenario_list(st):
    """ScenarioListResponse。新号全空（q6：序章 11000/11002 也不落库）。"""
    return {
        "ScenarioHistoryDBs": list(st.data.get("scenario_history_dbs") or []),
        "ScenarioGroupHistoryDBs": list(st.data.get("scenario_group_history_dbs") or []),
        "ScenarioCollectionDBs": list(st.data.get("scenario_collection_dbs") or []),
    }


def _body_shop_gacha_recruit_list(st):
    return {
        "ShopRecruits": st.shop_recruits(),
        "ShopFreeRecruitHistoryDBs": list(st.skeleton["ShopFreeRecruitHistoryDBs"] or []),
    }


def _body_time_attack_dungeon_login(st):
    return {"PreviousRoomDB": None}     # spec: type=null


def _body_billing_purchase_list(st):
    """29002 Billing_PurchaseListByYostar 的 body —— 1017 子回包与独立 RPC 共用这一个构造器。

    CountList 官方是 4 条 shop cash 的购买计数（含重置日期），这些是运营/购买数据，
    ExcelDB 里无法为新号推出 → 空。OrderList / MonthlyProductList 同理。
    """
    return {
        "CountList": list(st.data.get("purchase_counts") or []),
        "OrderList": [],
        "MonthlyProductList": [],
    }


def _body_event_content_permanent_list(st):
    """30041 EventContent_PermanentList 的 body —— 1017 子回包与独立 RPC 共用这一个构造器。

    官方 22 条 {EventContentId, IsStageAllClear}。新号没有任何永久活动进度 → 空。
    """
    ids = st.data.get("permanent_event_ids")
    rows = st.data.get("permanent_event_dbs")
    if rows is None and ids is not None:
        rows = [{"EventContentId": int(i), "IsStageAllClear": False} for i in ids]
    return {"PermanentDBs": list(rows or [])}


def _body_attachment_emblem_list(st):
    return {"EmblemDBs": st.emblems()}


def _body_attachment_get(st):
    return {"AccountAttachmentDB": {
        "AccountId": st.server_id,                             # 动态
        "EmblemUniqueId": st.attached_emblem_unique_id(),
    }}


def _body_content_sweep_multi_sweep_preset_list(st):
    """官方 MultiSweepPresetDBs 恰好 1 条（PresetId 0 / PresetName "" / StageIds 10 个 / ParcelIds []）。

    新号没有扫荡预设 → 给「1 个空预设」而不是 0 条：官方那 1 条 PresetId=0、名称为空，
    形态上就是"默认槽"。StageIds 给空（那些关卡 id 是玩家进度，新号没有）。
    """
    rows = st.data.get("content_sweep_presets")
    if rows is None:
        rows = [{"PresetId": 0, "PresetName": "", "StageIds": [], "ParcelIds": []}]
    return {"MultiSweepPresetDBs": rows}


def _body_eliminate_raid_login(st):
    r = st.data.get("eliminate_raid_login")
    if r is None:
        r = {"SeasonType": 0, "CanReceiveRankingReward": False,
             "ReceiveLimitedRewardIds": [], "SweepPointByRaidUniqueId": {},
             "LastSettledRanking": 0, "LastSettledTier": 0}
    return dict(r)


def _body_sticker_list(st):
    return {"StickerBookDB": {
        "AccountId": st.server_id,                             # 动态
        # **未找到**默认贴纸集合（StickerPageContent 23 行 ≠ 官方 20 条，无法推出）→ 空
        "UnusedStickerDBs": list(st.data.get("stickers_unused_ids") or []),
        "UsedStickerDBs": list(st.data.get("stickers_used_ids") or []),
    }}


def _body_multi_gacha_sync(st):
    return {"MultiFloorRaidDBs": None}     # spec: type=null


def _body_multi_floor_raid_login(st):
    return {"LastClearedDifficulty": int(st.data.get("last_cleared_difficulty") or 0)}


# ---- 4 个散落在顶层的非子回包字段（官方 DTO 把它们排在 MultiFloorRaid* 中间/末尾）
def _scalar_friend_count(st):
    return int(st.data.get("friend_count") or 0)


def _scalar_friend_code(st):
    return st.friend_code()


def _scalar_pickup_first_get_history(st):
    """新号没抽过卡 → 空。官方那条 {ShopRecruitId, LogDate} 是抽卡历史（运营数据）。"""
    return list(st.data.get("pickup_first_get_history_dbs") or [])


def _scalar_account_level_reward_ids(st):
    return st.account_level_reward_ids()


# ---- 注册表：DTO 名 → 构造器
BODY_BY_NAME = {
    "CafeGetInfoResponse": _body_cafe_get_info,
    "AccountCurrencySyncResponse": _body_account_currency_sync,
    "CharacterListResponse": _body_character_list,
    "EquipmentItemListResponse": _body_equipment_item_list,
    "CharacterGearListResponse": _body_character_gear_list,
    "EchelonListResponse": _body_echelon_list,
    "MemoryLobbyListResponse": _body_memory_lobby_list,
    "CampaignListResponse": _body_campaign_list,
    "ArenaLoginResponse": _body_arena_login,
    "RaidLoginResponse": _body_raid_login,
    "CraftInfoListResponse": _body_craft_info_list,
    "ClanLoginResponse": _body_clan_login,
    "MomoTalkOutLineResponse": _body_momotalk_outline,
    "ScenarioListResponse": _body_scenario_list,
    "ShopGachaRecruitListResponse": _body_shop_gacha_recruit_list,
    "TimeAttackDungeonLoginResponse": _body_time_attack_dungeon_login,
    "BillingPurchaseListByYostarResponse": _body_billing_purchase_list,
    "EventContentPermanentListResponse": _body_event_content_permanent_list,
    "AttachmentEmblemListResponse": _body_attachment_emblem_list,
    "AttachmentGetResponse": _body_attachment_get,
    "ContentSweepMultiSweepPresetListResponse": _body_content_sweep_multi_sweep_preset_list,
    "EliminateRaidLoginResponse": _body_eliminate_raid_login,
    "StickerListResponse": _body_sticker_list,
    "MultiFloorRaidSyncResponse": _body_multi_gacha_sync,
    "MultiFloorRaidLoginResponse": _body_multi_floor_raid_login,
}

# ---- 双身份：独立 RPC 号 → **同一个**构造器对象（复用，不是重写）
BODY_BY_PROTO = {
    5000: _body_echelon_list,                          # Echelon_List
    6000: _body_campaign_list,                         # Campaign_List
    29002: _body_billing_purchase_list,                # Billing_PurchaseListByYostar
    30041: _body_event_content_permanent_list,         # EventContent_PermanentList
}

# 独立 RPC 的 DTO 名（顶层 sub-response 名去掉 Response 后缀，用于日志）
DUAL_RPC_NAME = {5000: "Echelon_List", 6000: "Campaign_List",
                 29002: "Billing_PurchaseListByYostar", 30041: "EventContent_PermanentList"}

# ---- 顶层 4 个散字段（不是子回包，官方把它们排在 DTO 序里）
SCALAR_BY_NAME = {
    "FriendCount": _scalar_friend_count,
    "FriendCode": _scalar_friend_code,
    "PickupFirstGetHistoryDBs": _scalar_pickup_first_get_history,
    "AccountLevelRewardIds": _scalar_account_level_reward_ids,
}


# ================================================================ 骨架枚举（全部来自 spec）
def sub_response_names(spec=None):
    """从 spec 推出「哪些顶层键是具名子回包」。

    判据：不是信封字段，且（type=null 或 object 里带 Protocol）。
    ⇒ 官方实测 = 26 个（其中 ItemListResponse 是 null 槽），余下 4 个是散字段。
    """
    spec = spec or _load_spec()
    fields = spec.schema(PROTO)["fields"]
    names = []
    for k, fs in fields.items():
        if k in ENVELOPE_FIELDS:
            continue
        if fs.get("type") == "null" or "Protocol" in (fs.get("fields") or {}):
            names.append(k)
    return names


def scalar_names(spec=None):
    """顶层除了信封 + 子回包之外的散字段。"""
    spec = spec or _load_spec()
    sub = set(sub_response_names(spec))
    return [k for k in spec.schema(PROTO)["fields"]
            if k not in ENVELOPE_FIELDS and k not in sub]



# ================================================================ 组装
def _make_state(account_state, session, rules, master, request_id, now):
    return AccountState(account_state, session, rules, master,
                        request_id=request_id, now=now)


def build(account_state=None, session=None, request_id=None, now=None,
          spec=None, rules=None, master=None, issues=None):
    """核心入口：`(account_state, session)` → 完整 1017 dict。

    返回前已经过 specgen.Spec.build 投影，所以返回值**必然**符合 official_spec.json
    的形状（spec_check 不会 FAIL）。丢弃/强制记账落在 issues 里，调用方可以查。
    """
    own_master = master is None
    if spec is None:
        spec = _load_spec()
    if rules is None:
        rules = _load_rules()
    if master is None:
        master = _open_master()
    if issues is None:
        issues = G.Issues()
    try:
        st = _make_state(account_state, session, rules, master, request_id, now)
        # 角色必须先跑：编队/咖啡厅/战队都要引用角色 ServerId
        st._last_characters = st.characters()

        values = st.envelope(session)
        root = spec.schema(PROTO)
        for key, fs in (root.get("fields") or {}).items():
            if key in ENVELOPE_FIELDS:
                continue
            if fs.get("type") == "null":
                values[key] = None                      # spec: 官方只见过 null，只能发 null
                continue
            fn = BODY_BY_NAME.get(key) or SCALAR_BY_NAME.get(key)
            if fn is not None:
                values[key] = fn(st)
            # 未登记 → **不写**，交给 spec.build 用该节点的结构性默认值补
            #           （int 0 / str "" / bool false / [] / {} / 零值信封）。
            #           这才是"骨架由 spec 驱动"：spec 里多一个子回包，这里不用改代码。

        out = spec.build(PROTO, values, issues)
        out_issues = issues
        build.last_state = st
        build.last_issues = out_issues
        return out
    finally:
        if own_master:
            master.close()


def build_standalone(proto, account_state=None, session=None, request_id=None, now=None,
                     spec=None, rules=None, master=None, issues=None):
    """用**同一个** body 构造器拼一个独立 RPC 的响应（5000/6000/29002/30041）。

    存在的意义：证明这 4 个 DTO 只写了一遍。返回的 dict 可以独立跑 spec_check。
    """
    proto = int(proto)
    if proto not in BODY_BY_PROTO:
        raise KeyError("%d 不是 1017 的双身份 DTO，可选 %s" % (proto, list(BODY_BY_PROTO)))
    own_master = master is None
    if spec is None:
        spec = _load_spec()
    if rules is None:
        rules = _load_rules()
    if master is None:
        master = _open_master()
    if issues is None:
        issues = G.Issues()
    try:
        st = _make_state(account_state, session, rules, master, request_id, now)
        st.characters()                                   # 编队要引用角色 ServerId
        values = st.envelope(session)
        values["Protocol"] = proto                        # 独立 RPC 的信封是真的
        values.update(BODY_BY_PROTO[proto](st))
        return spec.build(proto, values, issues)
    finally:
        if own_master:
            master.close()


# ================================================================ 资源
_SPEC_CACHE = {}
_RULES_CACHE = {}


def _load_spec(path=None):
    p = path or DATA["spec"]
    if not p or not os.path.isfile(p):
        raise SystemExit("[gen1017] 找不到 official_spec.json；设 %s=<path>。已尝试: %s"
                         % (SPEC_ENV, DATA["spec"]))
    if p not in _SPEC_CACHE:
        _SPEC_CACHE[p] = G.Spec(p)
    return _SPEC_CACHE[p]


def _load_rules(path=None):
    p = path or DATA["rules"]
    if not p or not os.path.isfile(p):
        raise SystemExit("[gen1017] 找不到 initial_state_rules.json；设 %s=<path>。已尝试: %s"
                         % (RULES_ENV, DATA["rules"]))
    if p not in _RULES_CACHE:
        with open(p, "r", encoding="utf-8") as fh:
            _RULES_CACHE[p] = json.load(fh)
    return _RULES_CACHE[p]


def _open_master(path=None):
    p = path or DATA["exceldb"]
    if not p or not os.path.isfile(p):
        raise SystemExit("[gen1017] 找不到 ExcelDB.db；设 %s=<path>。已尝试: %s"
                         % (EXCELDB_ENV, DATA["exceldb"]))
    return G.MasterData(p)


# ================================================================ 自检 / 指纹
def selfcheck(resp, session=None):
    """结构不变量。返回 (errors, notes)；errors 非空 = 生成器有 bug（不是数据少）。"""
    errs, notes = [], []

    # 1) 顶层键 = spec 的 35 个，且顺序一致
    spec = _load_spec()
    order = spec.top_key_order(PROTO)
    if list(resp) != order:
        errs.append("顶层键序与 spec 不一致: got %s" % (list(resp)[:6],))
    if len(resp) != 35:
        errs.append("顶层键数 %d != 35" % len(resp))

    # 2) 子回包信封必须是零值
    for k, v in resp.items():
        if k in ENVELOPE_FIELDS or not isinstance(v, dict) or "Protocol" not in v:
            continue
        for f, want in ZERO_ENVELOPE.items():
            if v.get(f) != want:
                errs.append("%s.%s=%r 应为 %r（子回包信封必须全零）" % (k, f, v.get(f), want))

    # 3) 绝不发 Responses 数组
    def _scan(node, path):
        if isinstance(node, dict):
            if "Responses" in node:
                errs.append("%s 里出现了 Responses（1017 不发数组）" % path)
            for kk, vv in node.items():
                _scan(vv, path + "." + kk)
        elif isinstance(node, list):
            for i, el in enumerate(node[:8]):
                _scan(el, "%s[%d]" % (path, i))
    _scan(resp, "$")

    # 4) spec 说 null 的槽必须真的是 null
    for name in ("ItemListResponse",):
        if resp.get(name) is not None:
            errs.append("%s 必须是 null（spec type=null）" % name)
    if resp["CafeGetInfoResponse"].get("CafeDB") is not None:
        errs.append("CafeGetInfoResponse.CafeDB 必须是 null（spec type=null）")
    if resp["TimeAttackDungeonLoginResponse"].get("PreviousRoomDB") is not None:
        errs.append("TimeAttackDungeonLoginResponse.PreviousRoomDB 必须是 null")
    if resp["MultiFloorRaidSyncResponse"].get("MultiFloorRaidDBs") is not None:
        errs.append("MultiFloorRaidSyncResponse.MultiFloorRaidDBs 必须是 null")

    # 5) ServerId 引用闭合：编队 → 角色，且都指向本账号
    sk = resp["SessionKey"]
    sid = int(sk.get("AccountServerId") or 0)
    chars = resp["CharacterListResponse"]["CharacterDBs"]
    char_sids = [int(c["ServerId"]) for c in chars]
    if len(set(char_sids)) != len(char_sids):
        errs.append("角色 ServerId 有重复: %s" % char_sids)
    for e in resp["EchelonListResponse"]["EchelonDBs"]:
        lid = int(e["LeaderServerId"])
        if lid and lid not in char_sids:
            errs.append("EchelonDBs.LeaderServerId=%d 不在 CharacterDBs.ServerId 里（引用必须闭合）" % lid)
        if int(e["AccountServerId"]) != sid:
            errs.append("EchelonDBs.AccountServerId=%s != SessionKey.AccountServerId=%s"
                        % (e["AccountServerId"], sid))
        for fld in ("MainSlotServerIds", "SupportSlotServerIds"):
            for v in e[fld]:
                if int(v) and int(v) not in char_sids:
                    errs.append("EchelonDBs.%s 里有非本账号角色 %s" % (fld, v))

    # 6) AccountId 一致
    for c in resp["CafeGetInfoResponse"]["CafeDBs"]:
        if int(c["AccountId"]) != sid:
            errs.append("CafeDBs.AccountId=%s != %s" % (c["AccountId"], sid))
        if int(c["CafeDBId"]) != sid * 10 + int(c["CafeId"]):
            errs.append("CafeDBId=%s != AccountServerId*10+CafeId" % c["CafeDBId"])
    for path, val in (
            ("AttachmentGetResponse.AccountAttachmentDB.AccountId",
             resp["AttachmentGetResponse"]["AccountAttachmentDB"]["AccountId"]),
            ("StickerListResponse.StickerBookDB.AccountId",
             resp["StickerListResponse"]["StickerBookDB"]["AccountId"]),
            ("ClanLoginResponse.AccountClanMemberDB.AccountId",
             resp["ClanLoginResponse"]["AccountClanMemberDB"]["AccountId"]),
            ("ClanLoginResponse.AccountClanMemberDB.AttachmentDB.AccountId",
             resp["ClanLoginResponse"]["AccountClanMemberDB"]["AttachmentDB"]["AccountId"]),
            ("MemoryLobbyListResponse.MemoryLobbyDBs[0].AccountServerId",
             resp["MemoryLobbyListResponse"]["MemoryLobbyDBs"][0]["AccountServerId"]),
    ):
        if int(val) != sid:
            errs.append("%s=%s != SessionKey.AccountServerId=%s" % (path, val, sid))

    # 7) 顶层 RequestId 必须是合法 uuid4（客户端会拿它当下一条请求的 REQUEST-ID）
    try:
        uuid.UUID(str(resp["RequestId"]))
    except Exception:
        errs.append("RequestId=%r 不是合法 uuid" % (resp["RequestId"],))
    if int(resp["Protocol"]) != PROTO:
        errs.append("Protocol=%r != %d" % (resp["Protocol"], PROTO))
    if len(str(resp["FriendCode"])) != 7:
        errs.append("FriendCode=%r 不是 7 位" % (resp["FriendCode"],))

    subs = sub_response_names(spec)
    scals = scalar_names(spec)
    notes.append("顶层 %d 键 = 5 信封 + %d 具名子回包 + %d 散字段；子回包里发 null 的 %d 个"
                 % (len(resp), len(subs), len(scals),
                    sum(1 for k in subs if resp.get(k) is None)))
    return errs, notes


def _shape(node, depth=0, maxdepth=40):
    """值的形状树（键 → 子形状 / 类型名），用于"结构是否变了"的可复现对比。"""
    if depth > maxdepth:
        return "..."
    if isinstance(node, dict):
        return {k: _shape(v, depth + 1, maxdepth) for k, v in node.items()}
    if isinstance(node, list):
        return [len(node), _shape(node[0], depth + 1, maxdepth)] if node else [0]
    return type(node).__name__


def struct_fingerprint(resp):
    """**顶层**结构指纹：只取键序 + 每个键是 object/array/标量 → 跨账号必相同。"""
    top = []
    for k, v in resp.items():
        if isinstance(v, dict):
            top.append([k, "object", list(v)])
        elif isinstance(v, list):
            top.append([k, "array"])
        elif v is None:
            top.append([k, "null"])
        else:
            top.append([k, type(v).__name__])
    return _sha256(json.dumps(top, ensure_ascii=False))


def shape_fingerprint(resp):
    """**深层**形状指纹（含每个对象的键序、数组长度）→ 同数据密度才相同。"""
    return _sha256(json.dumps(_shape(resp), ensure_ascii=False, sort_keys=False))


# ================================================================ 输出
def _ensure_dir(path):
    d = os.path.dirname(os.path.abspath(path))
    if d and not os.path.isdir(d):
        os.makedirs(d)


def write_json(obj, path, pretty=True):
    _ensure_dir(path)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        if pretty:
            json.dump(obj, fh, ensure_ascii=False, indent=1)
            fh.write("\n")
        else:
            json.dump(obj, fh, ensure_ascii=False, separators=(",", ":"))
            fh.write("\n")
    return os.path.getsize(path)


def write_md(text, path):
    _ensure_dir(path)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text if text.endswith("\n") else text + "\n")
    return os.path.getsize(path)


def spec_check(proto, resp):
    """复用 proto/spec_check.py（不在本文件里重写校验器）。返回 (rep, entry)。"""
    p = DATA["spec"]
    d = os.path.dirname(p)
    if d not in sys.path:
        sys.path.insert(0, d)
    sys.dont_write_bytecode = True
    import spec_check as SC
    with open(p, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    return SC.check_one(int(proto), resp, raw, "<gen1017>")


# ================================================================ CLI
def main(argv=None):
    ap = argparse.ArgumentParser(
        description="生成 1017 Account_LoginSync 响应（spec 驱动 + 账号状态驱动）",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--account-id", "--server-id", dest="account_id", type=int,
                    default=DEFAULT_SERVER_ID, help="AccountServerId（默认 %d）" % DEFAULT_SERVER_ID)
    ap.add_argument("--state-json", default=None,
                    help="账号状态 JSON（白名单键，见 KNOWN_STATE_KEYS）；给了就覆盖 --account-id")
    ap.add_argument("--session-json", default=None,
                    help='真实 SessionKey，如 \'{"AccountServerId":1,"MxToken":"<REDACTED_TOKEN>"}\'')
    ap.add_argument("--request-id", default=None, help="不传 = uuid4（外层 requestid 必须同值）")
    ap.add_argument("--now", default=None, help="固定时间（UTC，YYYY-MM-DDTHH:MM:SS）")
    ap.add_argument("--out", default=None, help="输出文件路径")
    ap.add_argument("--pretty", action="store_true", default=True, help="缩进输出（默认开）")
    ap.add_argument("--compact", dest="pretty", action="store_false", help="紧凑输出")
    ap.add_argument("--standalones", action="store_true",
                    help="额外渲染 5000/6000/29002/30041 四个独立 RPC（证明构造器复用）")
    ap.add_argument("--no-spec-check", dest="spec_check", action="store_false", default=True)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    account_state = {}
    if args.state_json:
        with open(args.state_json, "r", encoding="utf-8") as fh:
            account_state = json.load(fh)
        if not isinstance(account_state, dict):
            raise SystemExit("--state-json 必须是 JSON object")
    if args.account_id and not account_state.get("server_id"):
        account_state["server_id"] = args.account_id

    session = None
    if args.session_json:
        session = json.loads(args.session_json)

    spec = _load_spec()
    rules = _load_rules()
    master = _open_master()
    issues = G.Issues()
    try:
        resp = build(account_state, session, request_id=args.request_id, now=args.now,
                     spec=spec, rules=rules, master=master, issues=issues)
        st = build.last_state
        errs, notes = selfcheck(resp, session)
        out = args.out or os.path.join(HERE, "out", "1017.json")
        size = write_json(resp, out, pretty=args.pretty)

        rep = entry = None
        if args.spec_check:
            rep, entry = spec_check(PROTO, resp)

        standalone = []
        if args.standalones:
            base, ext = os.path.splitext(os.path.abspath(out))
            for proto in DUAL_RPC_PROTOS:
                sub = build_standalone(proto, account_state, session,
                                       request_id=args.request_id, now=args.now,
                                       spec=spec, rules=rules, master=master)
                sp = "%s_%d.json" % (base, proto)
                sz = write_json(sub, sp, pretty=args.pretty)
                srep = None
                if args.spec_check:
                    srep, _ = spec_check(proto, sub)
                standalone.append((proto, sp, sz, srep, sub))
    finally:
        master.close()

    if args.quiet:
        return 0 if not errs else 1

    print("=" * 78)
    print("1017 Account_LoginSync 动态生成 — spec 驱动骨架 + 账号状态驱动数据")
    print("=" * 78)
    print("account_id        : %d" % st.server_id)
    print("session           : %s" % ("真实 session" if session else "由 account_id 派生（MxToken=sha384）"))
    print("now / ticks       : %s / %d" % (st.ts(), st.ticks))
    print("RequestId         : %s" % st.request_id)
    print("输出文件          : %s (%d bytes, %s)"
          % (os.path.abspath(out), size, "pretty" if args.pretty else "compact"))
    _m = measure(resp, request_id=st.request_id)
    print("三层体积          : inner %d B / outer %d B / wire %d B（官方口径 = wire）"
          % (_m["inner"], _m["outer"], _m["wire"]))
    print("-" * 78)
    print("顶层键数          : %d (spec 必填 %d)" % (len(resp), len(spec.mandatory_top_keys(PROTO))))
    _subs, _scals = sub_response_names(spec), scalar_names(spec)
    print("具名子回包        : %d 个（其中 null %d 个） / 散字段 %d 个 %s"
          % (len(_subs), sum(1 for k in _subs if resp.get(k) is None),
             len(_scals), _scals))
    print("conform 记账      : dropped=%d forced=%d %s"
          % (len(issues.dropped), len(issues.forced),
             "OK" if not issues.dropped and not issues.forced else "!! 见下"))
    for pth, k, det in issues.dropped[:10]:
        print("   DROP  %s.%s  %s" % (pth, k, det))
    for pth, det in issues.forced[:10]:
        print("   FORCE %s  %s" % (pth, det))
    print("结构自检          : %s" % ("PASS（0 处不变量违反）" if not errs else "FAIL %d" % len(errs)))
    for e in errs:
        print("   !! %s" % e)
    for n in notes:
        print("   %s" % n)
    print("结构指纹(top)     : %s" % struct_fingerprint(resp))
    print("形状指纹(deep)    : %s" % shape_fingerprint(resp))
    if st.ignored_state_keys:
        print("未识别的 state 键 : %s（已忽略）" % st.ignored_state_keys)
    for n in st.notes:
        print("   note: %s" % n)
    if rep is not None:
        cats = {}
        for k, _p, _d in rep.warns:
            cats[k] = cats.get(k, 0) + 1
        print("spec_check        : %s  FAIL %d / WARN %d %s"
              % ("PASS" if not rep.fails else "FAIL", len(rep.fails), len(rep.warns),
                 ("(" + ", ".join("%s=%d" % kv for kv in sorted(cats.items())) + ")") if cats else ""))
        for k, p, d in rep.fails[:20]:
            print("   FAIL [%s] %s  %s" % (k, p, d))
        for k, p, d in rep.warns:
            print("   WARN [%s] %s  %s" % (k, p, d))
    if standalone:
        print("-" * 78)
        print("双身份 DTO 独立 RPC（同一个 body 构造器）:")
        for proto, sp, sz, srep, sub in standalone:
            ok = "PASS" if (srep is None or not srep.fails) else "FAIL %d" % len(srep.fails)
            fn = BODY_BY_PROTO[proto]
            print("  %-6d %-32s %6d B  键 %d  spec_check %s   builder=%s"
                  % (proto, DUAL_RPC_NAME[proto], sz, len(sub), ok, fn.__name__))
            if srep is not None:
                for k, p, d in srep.fails[:10]:
                    print("     FAIL [%s] %s  %s" % (k, p, d))
    print("-" * 78)
    bad = errs or (rep is not None and rep.fails)
    print("结果              : %s" % ("PASS" if not bad else "FAIL"))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
