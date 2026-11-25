# PROTO_CLOSE_20261117 — 协议层收尾（token 定性 / LoginSync 字段 / MemoryLobby）

> 时间：2026-11-17 20:25–20:5x | **只读**：本地 pcap/JSON/源码 + 只读 scp 服务器 pcap
> 素材：新抓包 `bk2.pcap00`（1,250,017 B / 20:17:44，已 scp 到本目录）、`blackout_lo.pcap0`、
> `report\_tmp\最全的一个.har`（官方）、`work\ba\proto\protocol_map.json`、`work\ba\srv_src\Shittim-Server\*`、`work\ba\server\deploy\patch_relay2.py`
> 每条标 **实测 / 推断**

---

## 0. 结论速览

| 项 | 结果 |
|---|---|
| ① token 定性 | **6 个全部定性**（外加 1 个号差：客户端 `Account_LoginSync=1017`、Shittim 枚举 `=1019`） |
| ② LoginSync 字段 | 我们（Shittim 转发）**32 键**、官方 **35 键**；官方独有 **6**、我们独有 **3**；24 个子响应每个少 **5 个信封字段** |
| ③ MemoryLobbyDBs | **官方 1 条 / 我们 1 条**（条数一样），但我们这条**缺 `AccountServerId`、缺 `ParcelInfos`** |

---

## 1. ① 七个 token 的定性（实测）

**方法**：先用 `protocol_map.json` 按 **id**（不是按 token）反查名字，再用官方 HAR 的 **URL 路径 + 解密后的响应 `protocol` 名**双向印证；
`token` 对不上的（Y3UK/UXIH）以"官方抓包里这条 token 出现在哪个 path、拿回什么响应"为准。

| # | 客户端 token | 客户端 id | **客户端真名** | Shittim 枚举 | Shittim handler | 桥接现状 | 应该怎么处理 |
|---|---|---|---|---|---|---|---|
| 1 | `GVDSNCHUMIOS44NDTZM6ZPDDVQ` | **1001** | **`Account_Nickname`** | 有（`ProtocolData.cs:27`） | 有（`AccountHandler.cs:253`） | 不在 `RL2_HANDLED` ⇒ **转发 Shittim** | 保持转发；注意 Shittim 只在"请求里带 Nickname"时改名 |
| 2 | `K3SF6XS7VK7JFL7T2M2WFELUSY` | **1010** | **`Account_CallName`** | 有（`ProtocolData.cs:36`） | 有（`AccountHandler.cs:271`） | **转发 Shittim** | 保持转发 |
| 3 | `Y3UKGGQI…`（日志里截断） | **8006** | **`Mission_GuideMissionSeasonList`**（官方 HAR 里这 token 出现在 `/api/mission/guidemissionseasonlist`，响应 160,216 B） | 有（`ProtocolData.cs:116`） | 有（`MissionHandler.cs:259`） | **转发 Shittim** | 保持转发；注意我们响应只有 156 字符，官方 160 KB ⇒ **数据量差 1000 倍** |
| 4 | `UXIHQC2A…`（截断） | **29002** | **`Billing_PurchaseListByYostar`**（官方 HAR 里出现在 `/api/billing/purchaselistbyyostar`，响应 `Billing_PurchaseListByYostar`） | 有（`ProtocolData.cs:292`） | 有（`BillingHandler.cs:106`） | **转发 Shittim** | **必须改**：见下方「Nexon/Yostar 命名冲突」 |
| 5 | `XJER6O4J52SF7TFS6WLCFJNDIM` | **90004** | **`Management_Data`** | **枚举里没有** | **没有 handler** | 在 `RL2_HANDLED` ⇒ **桥接自造桩**（日志 `handled-90004`，2,092 B） | 保持自造（Shittim 没有），但要补齐公告/横幅数据 |
| 6 | `QQAWTCO7TMCITQPOWS7PIBYLCQ` | **90011** | **`Shop_ListTutorialGacha`** | **枚举里没有** | **没有 handler** | **不在 `RL2_HANDLED` ⇒ 会被转发给 Shittim ⇒ 必然吃 Error 信封** ❗ | **必须加进 `RL2_HANDLED` 并自造响应**，否则每次调用都是协议错误 |

**另外发现的号差（实测）**：
- 客户端 `Account_LoginSync` = **1017**（`protocol_map.json`；官方 HAR 响应内层 `Protocol` 也是 **1017**）
- Shittim 枚举 `Account_LoginSync` = **1019**（`ProtocolData.cs:45`）
- 而 `bk2.pcap00` 里我们转发出去的 LoginSync 内层写的是 **`"Protocol": 1019`**。
⇒ **内层协议号与客户端期望差 2**。若客户端校验内层 `Protocol`，这一条就是硬伤（**推断，未验证客户端是否校验**）。

> token 与 `protocol_map` 的偏差只出现在 8006/29002 两个：map 里按名字算出的 token 与客户端实发不符（`26FX4K…` vs `Y3UK…`、`FAVZK2…` vs `UXIH…`），
> 所以**不能只靠 token 反查**，必须用"path + 响应 protocol 名"交叉确认——这也是上面两行结论的方法。

---

## 2. ② `Account_LoginSync` 字段语义表（实测对比）

**两份数据的来源**
- 我们：`bk2.pcap00` 里 `cp=39048` 的 9097 响应，解密后 `packet` = **153,439 字符**（Shittim 转发件），已存 `_ours_loginsync_shittim.json`
- 官方：HAR #147，`packet` 解析后 **35 键**（`_official_loginsync.json`）

### 2.1 顶层：32 vs 35

**官方有、我们没有（6 个）：**

| 字段 | 官方值 | 影响 |
|---|---|---|
| **`SessionKey`** | `{AccountServerId:10015354380, MxToken:"Vji5…"}` | 我们顶层**完全没有**；客户端若用 LoginSync 刷新会话就会拿不到 |
| **`ServerNotification`** | `0` | 红点位；缺省=0，影响小 |
| **`ItemListResponse`** | `null`（键在、值为 null） | 我们连键都没有；**Shittim 注释说官方没有这个子响应，但国服官方有** |
| **`MomoTalkOutLineResponse`** | 有内容 | 我们是 **`MomotalkOutlineResponse`（大小写不同）** ⇒ 见 2.3 |
| **`FriendCount`** | `0` | 好友数；缺省=0，影响小 |
| **`BillingPurchaseListByYostarResponse`** | 有内容（`CountList` 非空） | 我们是 **`BillingPurchaseListByNexonResponse`** ⇒ 见 2.3 |

**我们有、官方没有（3 个）：**

| 字段 | 我们的值 | 说明 |
|---|---|---|
| `BillingPurchaseListByNexonResponse` | `Protocol:29005, CountList:[]…` | Shittim 的"Nexon 版"命名，**国服用 Yostar 版** |
| `MomotalkOutlineResponse` | `Protocol:33000, MomoTalkOutLineDBs:[]…` | 大小写与官方不同 |
| `StaticOpenConditions` | 55 键全 0 | 官方登录包里**没有**这个键（它在 `Account_Auth` 里） |

### 2.2 24 个共有子响应：**每个都少 5 个信封字段**（实测）

以三个为例（原样）：

```
我方 CafeGetInfoResponse      keys = [Protocol, CafeDBs, FurnitureDBs]
官方 CafeGetInfoResponse      keys = [Protocol, SessionKey, ServerTimeTicks, ServerNotification, RequestId, CafeDB, CafeDBs, FurnitureDBs]

我方 ScenarioListResponse     keys = [Protocol, ScenarioHistoryDBs, ScenarioGroupHistoryDBs]
官方 ScenarioListResponse     keys = [Protocol, SessionKey, ServerTimeTicks, ServerNotification, RequestId, ScenarioHistoryDBs, ScenarioGroupHistoryDBs, ScenarioCollectionDBs]

我方 MomoTalkOutLineResponse  keys = [Protocol, MomoTalkOutLineDBs, FavorScheduleRecords]
官方 MomoTalkOutLineResponse  keys = [Protocol, SessionKey, ServerTimeTicks, ServerNotification, RequestId, MomoTalkOutLineDBs, FavorScheduleRecords]
```

⇒ **官方每个子响应都带 `SessionKey`/`ServerTimeTicks`/`ServerNotification`/`RequestId` 四个信封字段 + 自己的 payload；我们只有 `Protocol` + payload。**
（`Shittim` 源码注释声称"国服子响应不带这些"——**这条注释是错的**，至少对 CN 3.0.2 是错的。实测为准。）

### 2.3 三个"名字对不上"（**实测，最该先修**）

| 我们发出的键 | 官方键 | 差异类型 | 后果 |
|---|---|---|---|
| `BillingPurchaseListByNexonResponse` | `BillingPurchaseListByYostarResponse` | **不同词**（Nexon vs Yostar） | **客户端按名字取，取不到 ⇒ 充值列表为空**（Newtonsoft 大小写不敏感也救不了） |
| `MomotalkOutlineResponse` | `MomoTalkOutLineResponse` | **仅大小写**（t vs T、o vs O） | 若按名精确匹配 ⇒ 取不到；Newtonsoft 默认不敏感 ⇒ 可能侥幸 |
| `StaticOpenConditions` | （官方无此键） | 多出来的键 | 无害（未知键被忽略） |

### 2.4 值差异大的字段（实测，按"官方有值我们是空"排序）

| 字段 | 我们 | 官方 | 判定 |
|---|---|---|---|
| `CharacterListResponse.CharacterDBs` | **4 条**（ServerId=7/8/9/10） | **46 条** | 新号 vs 老号，正常；但**代表角色 id 必须在这张表里**（见下） |
| `ScenarioListResponse.ScenarioHistoryDBs` | 0 | 191 | **官方有值我们空**——大厅"剧情进度"相关 |
| `CafeGetInfoResponse` | 3 键 | 8 键（多 `CafeDB`） | 官方多一个 `CafeDB` |
| `EventContentPermanentListResponse.PermanentDBs` | 0 | 22 | 常驻活动入口全空 |
| `EquipmentItemListResponse.EquipmentDBs` | 0 | 84 | —— |
| `CampaignListResponse` | 4 键 | 8 键（多 `StageHistoryDBs: 90`） | 战役进度空 |
| `EchelonListResponse.EchelonDBs` | 1 队 | 8 队 | —— |
| `MomoTalkOutLineResponse.MomoTalkOutLineDBs` | 0 | 1 | 官方有值我们空 |
| `BillingPurchaseListBy*Response.CountList` | 0 | 4 | 官方有值我们空 |
| `AccountCurrencySyncResponse` | 3 键 | 7 键 | 少字段 |
| `PickupFirstGetHistoryDBs` / `AccountLevelRewardIds` | `[]` | 各 1 条 | —— |
| `Protocol`（内层） | **1019** | **1017** | **号差 2**（见 ①） |
| `FriendCode` | `RRYHEALT` | `slmv4wc` | 账号不同 |

**每个字段的语义**（供"一个真相源"引用）：

| 顶层字段 | 语义 |
|---|---|
| `AccountCurrencySyncResponse` | 各货币余额与过期货币 |
| `AccountLevelRewardIds` | 账号等级奖励已领 id |
| `ArenaLoginResponse` | 竞技场登录态（段位/票） |
| `AttachmentEmblemListResponse` | 徽章/称号 |
| `AttachmentGetResponse` | 附件（可领物） |
| `CafeGetInfoResponse` | 咖啡厅：家具、舒适度、收益 |
| `CampaignListResponse` | 战役章节/关卡进度 |
| `CharacterGearListResponse` | 角色装备（Gear） |
| `CharacterListResponse` | 角色列表（大厅/编队都依赖） |
| `ClanLoginResponse` | 社团信息 |
| `ContentSweepMultiSweepPresetListResponse` | 扫荡预设 |
| `CraftInfoListResponse` | 制造（Craft）状态 |
| `EchelonListResponse` | 编队 |
| `EliminateRaidLoginResponse` | 大决战（EliminateRaid） |
| `EquipmentItemListResponse` | 装备道具 |
| `EventContentPermanentListResponse` | 常驻活动入口 |
| `MemoryLobbyListResponse` | **记忆大厅列表（本次 ③ 的主角）** |
| `MultiFloorRaidLogin/SyncResponse` | 综合战术对抗（多楼层） |
| `PickupFirstGetHistoryDBs` | 首次获取（Pickup）记录 |
| `RaidLoginResponse` | 总力战 |
| `ScenarioListResponse` | 剧情进度（含 `ScenarioHistoryDBs`/`ScenarioGroupHistoryDBs`/`ScenarioCollectionDBs`） |
| `ShopGachaRecruitListResponse` | 招募/卡池 |
| `StickerListResponse` | 贴纸 |
| `TimeAttackDungeonLoginResponse` | 制约解除决战 |
| `SessionKey`/`ServerTimeTicks`/`ServerNotification`/`RequestId` | 信封 |

---

## 3. ③ `MemoryLobbyDBs` 专项（实测）

### 3.1 两份原始数据（逐字）

**我们（Shittim 转发件）**：
```json
"MemoryLobbyListResponse": {"Protocol": 12000, "MemoryLobbyDBs": [{"Type": 8, "MemoryLobbyUniqueId": 13010}]}
```

**官方**：
```json
"MemoryLobbyListResponse": {"Protocol": 0, "SessionKey": {...}, "ServerTimeTicks": 0, "ServerNotification": 0, "RequestId": "",
  "MemoryLobbyDBs": [{"Type": 8, "ParcelInfos": null, "AccountServerId": 10015354380, "MemoryLobbyUniqueId": 13010}]}
```

**条数：官方 1 条 / 我们 1 条 —— 一样。** ❗ 所以"记忆大厅没了"**不是条数问题**。

**我们这条缺的字段：`AccountServerId`（整个键不存在）、`ParcelInfos`（键不存在）。**

### 3.2 客户端打开大厅背景需要什么（推断，依据字段名 + 官方行为）

| 数据 | 作用 | 我们的状态 |
|---|---|---|
| `MemoryLobbyDBs[].MemoryLobbyUniqueId` | 记忆大厅（背景/L2D）的 id，客户端据此查 Excel 表取场景 | ✅ 有，`13010`，与官方**同值** |
| `MemoryLobbyDBs[].AccountServerId` | 这条记录属于哪个账号；客户端/服务端按它过滤 | ❌ **整键缺失**（官方有） |
| `MemoryLobbyDBs[].Type` | 类型（8 = 大厅背景类） | ✅ 有，8，与官方一致 |
| `MemoryLobbyDBs[].ParcelInfos` | 该大厅附带的奖励信息 | ❌ 缺（官方是 `null`，缺省多半等价） |
| `AccountDB.LobbyMode`（在 `Account_Auth` 里） | 大厅模式（0=普通 / 1=特殊） | ✅ 最新一份 = **0**（与官方一致；19:54 那轮曾是 1，已修） |
| `AccountDB.MemoryLobbyUniqueId`（在 `Account_Auth` 里） | 当前选中的记忆大厅 | ✅ = **0**（与官方一致） |

### 3.3 结论

> **大厅背景为空、记忆大厅没了的头号嫌疑：`MemoryLobbyDBs` 里那条记录缺 `AccountServerId`。**
> 客户端按账号过滤时，缺字段 → 默认 0 → 匹配不上 `10000000001` → 列表被过滤成空 ⇒ 背景没有可选的大厅。
> **证据等级：推断（中）**。依据是官方每条必带该字段、我们唯独缺它、且条数与 id 都相同——这是两份数据之间**唯一**的差异。

次嫌疑（推断，弱）：`ParcelInfos` 缺失；官方是显式 `null`，我们连键都没有，对背景渲染应无影响。

**建议修法（按代价）**：
1. 让 Shittim 的 `MemoryLobbyDBs` 映射补上 `AccountServerId = account.ServerId`（与官方同构）——**最小改动**；
2. 顺带补 `ParcelInfos: null`；
3. 若仍空，再把 `AccountDB.MemoryLobbyUniqueId` 设成 `13010`（官方是 0，但在"官方有记忆大厅"的账号上可能非 0；**这条与官方抓包不符，仅在 1、2 无效时再试**）。

---

## 4. 诚实标注

| 项 | 状态 |
|---|---|
| 客户端是否校验内层 `Protocol`（1017 vs 1019） | **未验证**（pcap/log 看不出） |
| `MemoryLobbyDBs` 缺 `AccountServerId` 是否真的导致空列表 | **推断（中）**，未做单变量实验 |
| 子响应缺 5 个信封字段是否影响客户端 | **未验证**（官方有、我们无，但客户端可能默认值兜住） |
| `Shop_ListTutorialGacha(90011)` 当前是否每调必错 | **推断（强）**：不在 `RL2_HANDLED` ⇒ 转发 Shittim ⇒ Shittim 无此 handler ⇒ Error 信封；**建议用一次实测确认** |
| 官方 HAR 的 160 KB GuideMission 数据 | 只核对了协议名与大小，未逐字段比对 |
