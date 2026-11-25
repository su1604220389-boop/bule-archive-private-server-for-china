# 49 — `AccountAuthResponse` 内层 JSON 定稿（可直接上线）

> 时间：2026-11-14 04:15–04:5x
> 角色：协议字段分析员。**未连手机、未连服务器、未发请求、未改任何线上开关。**
> 上游：`report\47`（20 属性闭合表，本轮直接引用，不重做）、`report\36`（真实 3740 B 的值）、
> `report\41`（字段级排查）、lead 2026-11-14 04:13 通报（真实 Error 响应的信封格式）
> 结论等级：**[确证]** 有偏移/有实值；**[映射]** 从 Shittim 真实成功响应搬；**[推断]** 有依据未证；**[占位]** 可随意填

---

## 0. 交付物（复制这一段给 srv-ops）

```python
# -*- coding: utf-8 -*-
# report\49 — Account_Auth 成功响应内层 JSON
# 用法: packet_str = json.dumps(INNER_ACCOUNT_AUTH, separators=(",", ":"), ensure_ascii=False)
#       body_obj  = {"protocol": "Account_Auth", "packet": packet_str, "requestid": <GUID>}
#       body_obj  -> 再按 lead 给的 AES-256-CBC 信封加密

from datetime import datetime

def _ticks(dt=None):
    """C# DateTime.Ticks：自 0001-01-01 起的 100ns 数。用服务器本地时间（UTC+8），与真实样本一致。"""
    dt = dt or datetime.now()
    return int((dt - datetime(1, 1, 1)).total_seconds()) * 10_000_000 + dt.microsecond * 10

def _iso(dt=None):
    """真实样本的格式：yyyy-MM-ddTHH:mm:ss，无时区、无毫秒。"""
    return (dt or datetime.now()).strftime("%Y-%m-%dT%H:%M:%S")

INNER_ACCOUNT_AUTH = {
    # ── 包头（Real Error 样本里这一步是 "Protocol": -1；成功响应应为 1002）──────────
    "Protocol": 1002,                                      # int  | [推断] Shittim=1002 | 必需(见 §5)

    # ── ResponsePacket 基类 6 个（report\47 §7.2，客户端每个响应都要）────────────
    "ServerTimeTicks": _ticks(),                           # long | [确证] 639302236570000000 同型 | 必需
    "ServerNotification": 0,                               # int  | [映射] Shittim=8(HasUnreadMail)，归零更干净 | 可缺省
    "MissionProgressDBs": [],                              # array| [推断] 客户端会遍历，null→NRE | 必需
    "EventMissionProgressDBDict": {},                      # dict | 同上 | 必需
    "BattlePassMissionProgressDBDict": {},                 # dict | 同上 | 必需
    "StaticOpenConditions": {                              # dict<string,int> | [映射] Shittim 55 键全 0 | 必需
        "Academy": 0, "Arena": 0, "Billing": 0, "Cafe": 0, "Cafe_2": 0,
        "Cafe_Invite": 0, "Cafe_Invite_2": 0, "Campaign": 0, "Clan": 0, "Craft": 0,
        "Echelon": 0, "EliminateRaid": 0, "Equip": 0, "EventContent": 0, "EventMiniGame_1": 0,
        "EventPermanent": 0, "EventStage_1": 0, "EventStage_2": 0, "Gacha": 0, "GuideMission": 0,
        "Item": 0, "LobbyIllust": 0, "Main_L_1_2": 0, "Main_L_1_3": 0, "Main_L_1_4": 0,
        "Main_L_1_5": 0, "MiniGameCCG": 0, "MiniGameDefense": 0, "MinigameDreamMaker": 0, "Mission": 0,
        "Mulligan": 0, "MultiFloorRaid": 0, "None": 0, "Raid": 0, "Schedule": 0,
        "SchoolDungeon": 0, "ShiftingCraft": 0, "Shop": 0, "Shop_Gem": 0, "Story": 0,
        "Story_Replay": 0, "Story_Sub": 0, "StrategySkip": 0, "Student": 0, "Tactic_Skip": 0,
        "Tactic_Speed": 0, "Talk": 0, "TimeAttackDungeon": 0, "Unit_Growth_LevelUp": 0, "Unit_Growth_Skill": 0,
        "Unit_Growth_Transcendence": 0, "WeekDungeon": 0, "WeekDungeon_Chase": 0,
        "__Deprecated_WeekDungeon_Blood": 0, "__Deprecated_WeekDungeon_FindGift": 0,
    },

    # ── AccountAuthResponse 的 20 个自有属性（report\47 §3，0x0022AE81）──────────
    "CurrentVersion": 446690,                              # int  | [映射] Shittim 真实成功响应 | 可缺省(见 §5)
    "MinimumVersion": 0,                                   # int  | [映射] Shittim 省略(=0) | 可缺省
    "IsDevelopment": False,                                # bool | [映射] Shittim 省略(=false) | 可缺省
    "BattleValidation": False,                             # bool | 同上 | 可缺省
    "UpdateRequired": False,                               # bool | 同上 | 可缺省
    "TTSCdnUri": "https://ba.dn.nexoncdn.co.kr/tts/version2/",  # str | [映射] Shittim 硬编码 | 可缺省
    "AccountDB": {                                         # obj  | 见 §3
        "ServerId": 2,                                     # int    | [映射] | 必需(客户端后续请求全带它)
        "Nickname": "",                                    # str    | [映射] 空串=正常态，由 1001 设置 | 必需(防 NRE)
        "State": 1,                                        # int    | [映射] 1=正常 | 必需
        "Level": 1,                                        # int    | [映射] | 可缺省
        "RepresentCharacterServerId": 9,                   # int    | [映射] | 可缺省
        "LastConnectTime": _iso(),                         # str    | [映射] yyyy-MM-ddTHH:mm:ss | 可缺省
        "PublisherAccountId": 314816420,                   # long   | [实测] 我们的 SDK uid | 必需(身份锚点)
        "RetentionDays": 0,                                # int    | [映射] | 可缺省
        "CreateDate": _iso(),                              # str    | [映射] | 可缺省
    },
    "RepurchasableMonthlyProductCountDBs": [],             # array| [映射] 空 | 可缺省
    "MonthlyProductParcel": [],                            # array| 空 | 可缺省
    "MonthlyProductMail": [],                              # array| 空 | 可缺省
    "BiweeklyProductParcel": [],                           # array| 空 | 可缺省
    "BiweeklyProductMail": [],                             # array| 空 | 可缺省
    "WeeklyProductParcel": [],                             # array| 空 | 可缺省
    "WeeklyProductMail": [],                               # array| 空 | 可缺省
    "IssueAlertInfos": [],                                 # array| 空 | 可缺省
    "DailyRecordDBs": [],                                  # array| [推断] 集合，null 会被遍历 | 必需(防 NRE)
    "OptionDB": {},                                        # dict | [映射] 官方恒为 {} | 可缺省
    "AccountLimitedFlashSaleDBs": [],                      # array| 空 | 可缺省
    "Desc": "",                                            # str  | [推断] 类型=string；空串防 .Length NRE | 可缺省
    # "FunctionClose": <不写入>                            # ???  | [不确定] 类型未知，见 §5.1
}

# ── 不确定 / 需要第 2 轮再试的 ────────────────────────────────────────────────
UNSURE = ["FunctionClose", "CurrentVersion", "StaticOpenConditions", "TTSCdnUri"]
UNSURE_DETAIL = {
    "FunctionClose": "类型未知（bool / list / dict 三种都可能）。**故意不写入**——缺省=null 对所有类型都合法；"
                     "而写错类型会让整个对象反序列化失败（更糟）。回退顺序见 §5.2",
    "CurrentVersion": "446690 是 Shittim（国际服口径）的实值；国服 3.0.2 的对应值未知。"
                      "若上线后出现『客户端更新』类弹窗，依次改 0 / 73 再试",
    "StaticOpenConditions": "类型推断为 dict<string,int>（沿用 Shittim 真实成功响应）。若反序列化失败，"
                            "先改 {} 再改 []",
    "TTSCdnUri": "Nexon 国际 CDN，国服不可达。但 report\21 §37.4 实测客户端登录期 0 次解析它，"
                 "故 v1 保持原值不引入新变量；若出现 TTS 相关弹窗再换",
}
```

**上面这段是完整可运行的 Python**：`_ticks()` / `_iso()` 每次 import 时求值一次；若要每请求刷新，把 `INNER_ACCOUNT_AUTH` 包成函数即可（见 §6）。

---

## 1. 20 个自有属性逐条

| # | 字段 | 类型 | 建议值 | 来源 | 必需/可缺省 | 客户端后续怎么用 |
|---|---|---|---|---|---|---|
| 1 | `CurrentVersion` | int | `446690` | [映射] Shittim 真实成功响应 | 可缺省 | 与 `MinimumVersion` 比较判强制更新；服务端不做校验 |
| 2 | `MinimumVersion` | int | `0` | [映射] Shittim 省略即 0 | 可缺省 | 同上；0 表示不强制 |
| 3 | `IsDevelopment` | bool | `False` | [映射] 同上 | 可缺省 | 开发模式开关，false 即线上行为 |
| 4 | `BattleValidation` | bool | `False` | [映射] 同上 | 可缺省 | 战斗校验；false = 不校验 |
| 5 | `UpdateRequired` | bool | `False` | [映射] 同上 | 可缺省 | 客户端直接读它决定弹不弹更新框 |
| 6 | `TTSCdnUri` | string | `https://ba.dn.nexoncdn.co.kr/tts/version2/` | [映射] Shittim 硬编码 | 可缺省 | 拼 TTS 资源 URL；`ShowTTSDownLoadPopup` 用 |
| 7 | `AccountDB` | object | 见 §3 | [映射] | **必需** | 账号主体；`Nickname` 空 → 触发改名弹窗，`ServerId` 是后续所有协议的主键 |
| 8 | `RepurchasableMonthlyProductCountDBs` | array | `[]` | [映射] | 可缺省 | 月卡可复购次数 |
| 9 | `MonthlyProductParcel` | array | `[]` | [映射] | 可缺省 | 月卡待领奖励 |
| 10 | `MonthlyProductMail` | array | `[]` | [映射] | 可缺省 | 月卡邮件 |
| 11 | `BiweeklyProductParcel` | array | `[]` | [映射] | 可缺省 | 双周卡 |
| 12 | `BiweeklyProductMail` | array | `[]` | [映射] | 可缺省 | 双周卡 |
| 13 | `WeeklyProductParcel` | array | `[]` | [映射] | 可缺省 | 周卡 |
| 14 | `WeeklyProductMail` | array | `[]` | [映射] | 可缺省 | 周卡 |
| 15 | `IssueAlertInfos` | array | `[]` | [映射] | 可缺省 | 公告/告警条 |
| 16 | `DailyRecordDBs` | array | `[]` | [推断] 集合 | **建议必需** | 每日记录，登录后并进本地存档；null 若被遍历 → NRE |
| 17 | `OptionDB` | object | `{}` | [映射] 官方恒为 `{}` | 可缺省 | 账号选项；空对象=全默认 |
| 18 | `AccountLimitedFlashSaleDBs` | array | `[]` | [映射] | 可缺省 | 限时礼包 |
| 19 | `Desc` | string | `""` | [推断] string | 可缺省 | 与 `FunctionClose` 配套的说明文案；空串防 `.Length` |
| 20 | `FunctionClose` | **未知** | **不写入** | [不确定] | 见 §5.1 | 功能关闭标记；类型未知，写错会毁掉整个反序列化 |

> **一个不多一个不少**：上表 20 个就是 `AccountAuthResponse`（`0x0022AE81`）的全部自有属性，与 `report\47 §3`
> 的 20 条 backing field 一一对应。`MxToken` / `SessionKey` / `EncryptedUID` / `AccountId` / `StaticOpenConditions`
> **都不在这 20 个里**（前四个在客户端根本不存在于该 DTO，最后一个在基类）。

---

## 2. 信封层 6 + 包头 1（不属于那 20 个，但内层 JSON 必须有）

`ResponsePacket` @`0x0023019C`（`report\47 §7.2`，本轮复核偏移一致）：

| 字段 | 类型 | 建议值 | 为什么必须 |
|---|---|---|---|
| `ServerTimeTicks` | long | `_ticks()`（真实值 `639302236570000000` 同型） | 客户端算服务器时间偏移；给 0 → 时间错乱 |
| `ServerNotification` | int | `0` | 红点/推送位；0 = 无未读 |
| `MissionProgressDBs` | array | `[]` | **本报告最看重的一条**：null 若被 `foreach` → NRE |
| `EventMissionProgressDBDict` | dict | `{}` | 同上 |
| `BattlePassMissionProgressDBDict` | dict | `{}` | 同上 |
| `StaticOpenConditions` | dict | 55 键全 `0` | 内容解锁判定；缺省 null 可能在锁判定处炸 |

包头 `Protocol`：真实 Error 样本里是 `"Protocol": -1`（大写 P）。成功响应用 `1002`。
**注意两层大小写不同**：外层 envelope 是 `"protocol":"Account_Auth"`（小写、字符串名），
内层是 `"Protocol":1002`（大写、整数）。

> `ServerTimeTicks` 用**服务器本地时间（UTC+8）**：真实样本 `639302220170000000` 换算 = `2026-11-14 03:00:17`，
> 与当时服务器本地时钟一致（我用 `datetime(1,1,1)+timedelta(microseconds=t//10)` 验算过）。
> 若客户端用 `DateTime.UtcNow` 比对，会有 8 小时偏移——**这是第 2 轮才需要处理的变量，v1 先与真实样本同构**。

---

## 3. `AccountDB` 子对象

| 字段 | 类型 | 值 | 依据 |
|---|---|---|---|
| `ServerId` | int | `2` | [映射] 后续所有 in-session 协议的主键；必须与 nginx/Shittim 侧一致 |
| `Nickname` | string | `""` | [映射] 空串是正常态（改名走 `Account_Nickname` 1001）；**不能为 null**，否则 `.Length` 之类可能 NRE |
| `State` | int | `1` | [映射] 1=正常（国服有 `IsStateMatch`） |
| `Level` | int | `1` | [映射] |
| `RepresentCharacterServerId` | int | `9` | [映射] 代表角色；进大厅才真正用到 |
| `LastConnectTime` | string | `_iso()` | [映射] 格式 `yyyy-MM-ddTHH:mm:ss`，**无时区无毫秒** |
| `PublisherAccountId` | long | `314816420` | [实测] 我们 SDK 签发的 uid；客户端/服务端用它锚定账号 |
| `RetentionDays` | int | `0` | [映射] |
| `CreateDate` | string | `_iso()` | [映射] 同上格式 |

**国服 `AccountDB` 还有、但我们 v1 不写的字段**（`0x24D290`–`0x24D720` 簇 [实测]）：
`LobbyMode`、`MemoryLobbyUniqueId`、`CallNameUpdateTime`、`UnReadMailCount`、`LastReturningDate`、
`NicknameRestriction` / `CommentRestriction` / `CallnameRestriction`。
不写的理由：缺省=默认值，值类型不会 NRE；只有 `CallName`/`Comment`（string）有 `.Length` 风险，
若第 1 轮仍静默，第 2 轮补 `"CallName": ""`、`"Comment": ""` 即可（见 §5.2）。

---

## 4. 类型判定依据（哪些是"确证"，哪些是"推断"）

| 结论 | 依据 | 等级 |
|---|---|---|
| 20 个属性名与顺序 | `report\47 §3.1`（accessor 段 `0x22AE95`–`0x22B1BA`）+ 20 条 backing field `0x22B1CC`–`0x22B471` 严格闭合 | **确证** |
| 这 20 个里没有 `MxToken`/`SessionKey`/`EncryptedUID` | 同上闭合性 + 全文件四层检索（明文 / XOR 0x20 / 0x01 / 0x0E） | **确证** |
| 6 个信封字段属于 `ResponsePacket` | `report\47 §7.2`，偏移 `0x2301AB`–`0x2302CE` | **确证** |
| 各字段的**具体类型**（int/long/string/bool/array/dict） | **metadata 表头被混淆（magic `0x12724394`），`typeIndex` 读不到**；类型是从「值域 + Shittim 同类字段 + 命名惯例」推的 | **推断** |

**本轮补做的 XOR 复核**（回应 lead 的提醒）：对 `SessionKey` / `AttendanceBookRewards` /
`AccountRestrictionsDB` / `NewlyAddedShopCashIds` 四个"0 命中"词，同时搜了明文与 `XOR 0x20` 两种形态，
**两种都是 0**；而 `CurrentVersion` / `TTSCdnUri` / `FunctionClose` / `AccountAuthResponse`
明文各 4 命中、XOR 形态 0 命中 ⇒ **该文件的字符串区就是明文，之前那些 0 命中不是混淆造成的假阴性**。
（`report\47` 的四层扫描结论与此一致。）

---

## 5. 不确定项与回退阶梯

### 5.1 `FunctionClose`（唯一一个"故意不写"的字段）

- 4 处命中全在访问器/backing/裸名段（`0x22B1AC` / `0x22B1BE` / `0x22B454` / `0x22B59E`），**没有任何类型线索**；
- 它没有配套的 `...DB` 类名，也没有 `FunctionType` 之类的枚举出现在附近；
- 三种可能都成立：`bool`（功能关闭总开关）、`List<int>`（被关闭的功能 id）、`Dictionary<int,bool>`。

**为什么不写**：写 `False` 而后端期待 `List<int>` → **整个响应反序列化失败**（比现在更糟）；
不写 → null，对 bool 而言等价于 false，对集合而言只是"空"，NRE 风险留给下游且**只在真被解引用时才炸**。
**不写严格占优。**

### 5.2 若第 1 轮仍静默，按这个顺序改（每次只改一处）

| 轮 | 改动 | 若命中说明 |
|---|---|---|
| R1 | `"FunctionClose": False` | 它是 bool 且被直接读 |
| R2 | `"FunctionClose": []` | 它是集合且被遍历 |
| R3 | AccountDB 补 `"CallName": ""`、`"Comment": ""` | 是 string 字段被 `.Length` |
| R4 | `CurrentVersion` 改 `0` → 再 `73` | 版本比较触发更新分支 |
| R5 | `StaticOpenConditions` 改 `{}` → 再 `[]` | 类型不符 |
| R6 | `ServerTimeTicks` 改 UTC ticks（减 8h） | 客户端用 UtcNow 比对 |

### 5.3 一条必须提前说的判据风险

如果 `AccountDB.Nickname` 是空串，客户端**正常行为**就是弹「输入昵称」框。
**看到改名弹窗 ≠ 失败，那是成功的第一信号**。判据仍以 lead 定的「第二条 HTTP 请求」为准，
但请把改名弹窗单独记一档，不要把两者混在一起。

---

## 6. 每请求刷新版（推荐 srv-ops 用这个，而不是 import 时求值）

```python
def build_inner_account_auth(account_server_id=2, publisher_account_id=314816420, nickname=""):
    import json
    d = dict(INNER_ACCOUNT_AUTH)              # 浅拷贝够用（只替换两个字符串）
    d["ServerTimeTicks"] = _ticks()
    d["AccountDB"] = dict(d["AccountDB"])
    d["AccountDB"]["LastConnectTime"] = _iso()
    d["AccountDB"]["CreateDate"] = _iso()
    d["AccountDB"]["ServerId"] = account_server_id
    d["AccountDB"]["PublisherAccountId"] = publisher_account_id
    d["AccountDB"]["Nickname"] = nickname
    return json.dumps(d, separators=(",", ":"), ensure_ascii=False)

# 自检
if __name__ == "__main__":
    s = build_inner_account_auth()
    import json as _j
    o = _j.loads(s)                            # 必须通过
    assert o["Protocol"] == 1002
    print(len(s), "bytes"); print(s[:160], "...")
```

预期：`json.loads` 通过、无 `NaN`/`Infinity`、体量 **≈ 1.75 KB**（实测 1744 B）。
比 Shittim 的 3740 B 小一半，因为我们裁掉了 4 个国服不存在的键和整块 `AttendanceBookRewards`（约 1400 B）。

---

## 7. Shittim 37 键 → CN 20 属性的裁剪表（给 review 用）

| Shittim 键 | 处置 | 原因 |
|---|---|---|
| `Protocol` | 保留（换成 1002） | 包头 |
| `CurrentVersion` `TTSCdnUri` `AccountDB` `OptionDB` `RepurchasableMonthlyProductCountDBs` `MonthlyProductParcel` `MonthlyProductMail` `BiweeklyProductParcel` `BiweeklyProductMail` `WeeklyProductParcel` `WeeklyProductMail` `IssueAlertInfos` `AccountLimitedFlashSaleDBs` | **保留**（13 条，字段名一字不改） | 国服 DTO 有同名属性 |
| `ServerTimeTicks` `ServerNotification` `StaticOpenConditions` | **保留**（3 条，属基类） | `ResponsePacket` 成员 |
| `AccountId` `SessionKey` `EncryptedUID` `AccountRestrictionsDB` `AttendanceBookRewards` `AttendanceHistoryDBs` `NewlyAddedShopCashIds` | **删除** | 国服 metadata 四层检索 **0 命中**（前四个尤其关键：`SessionKey` 根本不存在） |
| （Shittim 没有的）`MinimumVersion` `IsDevelopment` `BattleValidation` `UpdateRequired` `DailyRecordDBs` `Desc` `FunctionClose` | **补**（前 4 个取默认值，后 3 个见 §5） | 国服 DTO 有这三个属性 |

> `AttendanceBookRewards` 那 1400 字节的签到簿整块删掉：国服签到走**独立协议** `Attendance_Reward`
> （`AttendanceBookUniqueId` / `DayByBookUniqueId` [实测]），不塞在 Auth 响应里。

---

## 8. 诚实标注（做不到 / 没读到的）

| 项 | 状态 | 说明 |
|---|---|---|
| `/www/wwwroot/_ba_state/account_auth_resp_3740.json` | **未读取** | 在服务器上，本轮规定不碰服务器，且工作区无本地副本（我搜过 `report`/`work`/`kit`/`scripts`，只有 `account_auth_full.json` 等 3 个小文件）。本文所有「[映射]」值取自 `report\36` 的逐字段记录与 lead 消息，不是从该文件直接抄的。**若该文件里有本文没覆盖的键，请贴给我，我再补一轮。** |
| 20 个属性的**精确 CLR 类型** | **不确定** | metadata 表头混淆，`Il2CppTypeDefinition` 不可解析（`report\47 §3.4`、`report\24 §3`）。类型是推断 |
| `FunctionClose` 的类型 | **不确定** | 见 §5.1，故意不写 |
| `HandleMessage` 实际读哪些字段 | **不确定** | metadata 无函数体、`libil2cpp.so` 无符号（`report\47 §5.1`） |
| `Protocol: 1002` 是否正确 | **推断（中高）** | 来自 Shittim 真实响应 + 协议号公开规律；且内层 `Protocol` 若不在 DTO 上会被当未知键忽略，风险低 |

---

## 9. 上线后 30 秒自检（不碰手机，srv-ops 侧就能做）

```python
import json
# 1) 能不能 json.loads
json.loads(build_inner_account_auth())
# 2) 体量与键数（实测：1744 B / 26 键）
s = build_inner_account_auth()
assert 1500 < len(s.encode("utf-8")) < 2200
assert len(json.loads(s)) == 26   # 1 包头 + 6 基类 + 19 DTO（FunctionClose 故意不写）
# 3) 没有 NaN / Infinity
assert "NaN" not in s and "Infinity" not in s
# 4) 与真实 Error 样本同构：外层小写 protocol、内层大写 Protocol
assert json.loads(s)["Protocol"] == 1002
```

> 26 个顶层键 = 1（`Protocol`）+ 6（`ResponsePacket`）+ 19（`AccountAuthResponse`，`FunctionClose` 未写）。
> 若第 2 轮按 §5.2 补 `FunctionClose` 则为 27。
