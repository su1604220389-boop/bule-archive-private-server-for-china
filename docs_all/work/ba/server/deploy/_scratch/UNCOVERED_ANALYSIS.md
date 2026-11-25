# 1017 之后那批协议：能不能用「spec 驱动的通用空构造」一次覆盖

> **纯只读分析**。没有写生成器、没有新建 `.py`、没有改 `work\ba\proto\*` 与 `work\ba\server\deploy\*` 下任何现有文件、
> 没有连服务器、没有碰 bridge / 手机 / nginx、没有删文件。本文件是唯一新增产物。
>
> 数据来源：`report\_tmp\official_decoded_201\`（109 条官方解密响应，38 个协议）、`_timeline.txt`、
> `work\ba\proto\official_spec.json`、`protocol_map.json`、`initial_state_rules.json`、
> `work\ba\proto\dto_extra\proto36001_reddot.json`、`work\ba\data\ExcelDB.db`（只读打开）。
> 所有"验证过"的结论都是当场跑出来的（见 §8 复现命令），代码全部走 `python -` 标准输入，未落盘。

---

## 0. 结论先行

**你的假设基本成立，但有三处要先纠正，然后结论比你想的更干净。**

### 0.1 三个前提纠正（都有硬证据）

| # | 任务描述 | 实际 |
|---|---|---|
| 1 | `api/mission/guidemission` 160,216 B | **这个 endpoint 不存在。** 真名是 `api/mission/guidemissionseasonlist` = **协议 8006 `Mission_GuideMissionSeasonList`**。`_timeline.txt` 第 67 行的 URL 列截断到 54 字符，`gsqc-api.bluearchive-cn.com/api/mission/guidemission` 恰好卡在截断边界，"seasonlist" 被切掉了。`protocol_map.json` 里 501 个协议中带 Guide 的只有 8006 / 8003 / 8004 三个，**没有独立 `guidemission`**。文件是 `09_8006_api_mission_guidemissionseasonlist.response.json`，`meta.resp_bytes = 160216` 对得上 |
| 2 | 「估计有 15 个落在这 24 个里」 | **第 61–120 行里只有 9 个**：35003 / 16000 / 25003 / 15002 / 7001 / 28019 / 43010 / 7003 / 7000。另外 9 个（4000 / 3 / 26000 / 90004 / 1005 / 8000 / 8006 / 36001 / 29002）**都已经有生成器**，而且其中 8 个是逐字节的。把窗口放宽到第 160 行（越过竞技场一族）才会涨到 17 个 —— "15"大概是更宽窗口的数字 |
| 3 | 「38 个协议里 24 个没生成器」 | **对，且这个划分是干净的**：14 已覆盖 ∪ 24 未覆盖 = 38，交集 0（当场核对过） |

### 0.2 核心结论

| 结论 | 数字 |
|---|---|
| 第 61–120 行 = 41 个 game_api 请求 / 18 个不同协议 | 41 / 18 |
| 其中**已生成器覆盖** | 9 个协议，20 个请求（其中 8 个协议逐字节） |
| 其中**落在 24 个未覆盖里** | 9 个协议，21 个请求 |
| 这 9 个里 **✅ 纯空构造就够** | **8 个**：16000 / 25003 / 15002 / 7001 / 28019 / 43010 / 7003 / 7000 |
| 这 9 个里 **⚠ 要一组静态骨架** | **1 个**：35003（18 行小游戏任务骨架） |
| 这 9 个里 **❌ 要真实数据** | **0 个** |

**一句话：你那 9 个没有生成器的协议，8 个用通用空构造就能上，1 个加一张 18 行的静态骨架表，没有任何一个需要玩家真实进度。** 18 个协议里真正 ❌ 的 4 个（4000 / 3 / 8000 / 8006）**恰好全都已经有生成器了**。

### 0.3 最硬的一个结果

通用空构造**不是要新写，它已经写好了**：`work\ba\server\prototype\specgen.py` 的 `Spec.build(proto, {})`。

我对 18 个协议逐一跑了它，然后用抓包里的**真实信封**（`Protocol` / `SessionKey` / `ServerTimeTicks` / `ServerNotification` / `RequestId`）覆盖回去：

| 指标 | 结果 |
|---|---|
| 顶层键序与官方一致 | **18 / 18** |
| 顶层键集合与官方一致 | **18 / 18**（无缺键、无多键） |
| `spec_check` 判定 | **18 / 18 PASS**，FAIL 0 |
| 加上真实信封后与官方 inner **逐字节相同** | **5 个**：26000 / 16000 / 28019 / 43010 / 7003 |
| 其余 13 个的差异位置 | 全部集中在**恰好那几个容器字段**上，没有一处"形状不对" |

也就是说：**spec 已经把形状说全了，缺的只有"那几个容器里填什么"这一层数据决策。** 这就是 §5 要回答的问题。

---

## 1. 主表：18 个协议 × 空构造可行性

路径按官方 URL 列；「抓包文件」列省略公共前缀 `report\_tmp\official_decoded_201\`。
「已覆盖」= 在 `REGISTRY_DESIGN.md` 的 14 个里。

| # | 协议号 | 协议名 | 官方路径 | 响应字节 | 抓包文件 | 顶层键数 | 空构造 | 依据 |
|---|---|---|---|---|---|---|---|---|
| 1 | **4000** | Item_List | `api/item/list` | 16,088 | `03_4000_api_item_list.response.json` | 7 | **❌** | `ItemDBs` 134 行道具实例（`Type/ServerId/UniqueId/StackCount/IsNew`），spec 标 `is_player_data`；空构造 = `[]` → 背包全空。**已覆盖，逐字节**（需 `item_rows` 注入槽） |
| 2 | **3** | NetworkTime_Sync | `api/networktime/sync` | 620 | `04_3_api_networktime_sync.response.json` | 7 | **❌** | 不是缺玩家数据，是**缺请求回显**：`ReceiveTick` / `EchoSendTick` 必须回显客户端发包时的 tick。置 0 会让客户端算出一个荒谬的时钟偏移（推测：影响所有倒计时/每日重置显示）。**已覆盖，逐字节** |
| 3 | **26000** | ContentSave_Get | `api/contentsave/get` | 640 | `05_26000_api_contentsave_get.response.json` | 8 | **✅** | `HasValidData=false` + `ContentSaveDB=null` + `EventContentChangeDB=null`，**与 spec 零值一字不差**。回灌真实信封后与官方 inner **逐字节相同** |
| 4 | **90004** | Management_Data | `api/management/data` | 14,124 | `06_90004_api_management_data.response.json` | 6 | **⚠** | `Data` 里是**运营数据不是玩家数据**：6 公告 / 14 活动 / 7 banner / 12 抽卡概率公示 / `Issues[]` / `GuidePopup[]` / 3 个 null。空构造全 `[]` 结构合法，但抽卡概率公示页会空（国服合规要求，推测会被审核/客服盯）。**已覆盖，逐字节**（`ops` 注入槽） |
| 5 | **1005** | Account_GetTutorial | `api/account/gettutorial` | 640 | `07_1005_api_account_gettutorial.response.json` | 6 | **✅** | 唯一自有字段 `TutorialIds`，官方 21 个 = 该号进度；`initial_state_rules.json` 的 `q7_tutorials`（**confidence: high**）明确 **新号 `TutorialIds = []`**。空构造 = spec 默认 `[]`。**已覆盖，逐字节**（`tutorial_ids` 注入槽） |
| 6 | **8000** | Mission_List | `api/mission/list` | 268,396 / 8,768 / 8,216 | `08` / `10` / `11`_8000_api_mission_list.response.json` | 10 | **❌** | `ProgressDBs` 1240 行玩家进度 + `MissionHistoryUniqueIds` 372 + `ClearedOriginalMissionIds` 372；`DailySuddenMissionInfo.Id=1606` 是账号 jitter。**已覆盖，结构级**（缺 `progress_rows` 注入口） |
| 7 | **8006** | Mission_GuideMissionSeasonList | `api/mission/guidemissionseasonlist` | 160,216 | `09_8006_api_mission_guidemissionseasonlist.response.json` | 7 | **❌** | **不是静态配置树**（见 §4.3）。`MissionProgressDBs` 733 行、每行都带 `AccountServerId`；`GuideMissionSeasonDBs` 17 行带 `LoginCount` / `LoginDate` / `IsFinalMissionComplete`。**已覆盖，逐字节**（默认从 ExcelDB 推 733/17） |
| 8 | **35003** | MiniGame_MissionList | `api/minigame/missionlist` | 4,480 | `12_35003_api_minigame_missionlist.response.json` | 8 | **⚠** | `ProgressDBs` **恒 18 行**、进度**全是 0**（`ProgressParameters: {"10838":0}` 等），`MissionUniqueId = 10838×10000 + 0..17`。是"每个 EventContentId 一份静态任务骨架 + 零进度"。空构造 = `[]` → 小游戏任务页全空 |
| 9 | **16000** | Toast_List | `api/toast/list` | 556 | `13_16000_api_toast_list.response.json` | 6 | **✅** | `ToastDBs` 在 spec 里 **`type: "null"`**（唯一观测形态就是 null）。空构造 = `null`，**逐字节相同** |
| 10 | **25003** | Event_RewardIncrease | `api/event/rewardincrease` | 792 | `14_25003_api_event_rewardincrease.response.json`（另 20 条同形） | 6 | **✅** | `EventRewardIncreaseDBs` 恒 1 行，内容是 `{EventTargetType:4, RewardRealType:100473, Multiplier{rawValue:20000}, BeginDate:2026-11-12T04:00:00, EndDate:2026-11-19T03:59:59}` —— **服务端活动窗口，行内没有 AccountServerId**。空 = `[]` 语义就是"当前无加成活动"，正确 |
| 11 | **15002** | OpenCondition_EventList | `api/opencondition/eventlist` | 600 | `15_15002_api_opencondition_eventlist.response.json` | 6 | **✅** | `ConquestTiles = {"50822": []}`，键 **= 请求里的 `ConquestEventIds:[50822]`**，值是空数组。空构造 = `{}` 结构合法，只丢了"回显"（风险见 §6 R3） |
| 12 | **36001** | Notification_EventContentReddotCheck | `api/notification/eventcontentreddotcheck` | 1,088 | `16_36001_api_notification_eventcontentreddotcheck.response.json`（另 9 条同形） | 7 | **⚠** | `Reddots: {}` 是零值（对），但 `EventContentUnlockCGDBs` **恒 25 键、值全 `[]`**（spec `key_count 25/25`，10/10 样本键集合稳定）。空构造 = `{}` → 丢 25 个键（风险见 §6 R1）。**已覆盖，逐字节**（25 键在 `dto_extra\proto36001_reddot.json` 的 `catalog_constants`） |
| 13 | **7001** | Mail_Check | `api/mail/check` | 556 | `17_7001_api_mail_check.response.json`（另 8 条同形） | 6 | **✅** | 唯一自有字段 `Count`（官方 2）。新号无邮件 → `0`。回灌信封后唯一差异就是这个 `Count` |
| 14 | **28019** | Clan_Check | `api/clan/check` | 536 | `19_28019_api_clan_check.response.json`（另 7 条同形） | **5** | **✅** | **零自有字段，纯 5 键信封**。回灌信封后**逐字节相同**（唯一差异是 `ServerNotification 2048→0`，属信封） |
| 15 | **43010** | Friend_Check | `api/friend/check` | 536 | `20_43010_api_friend_check.response.json`（另 7 条同形） | **5** | **✅** | **零自有字段，纯 5 键信封**，且官方 `ServerNotification` 本来就是 0 —— 回灌信封后**逐字节相同** |
| 16 | **29002** | Billing_PurchaseListByYostar | `api/billing/purchaselistbyyostar` | 1,280 | `23_29002_api_billing_purchaselistbyyostar.response.json`（另 2 条同形） | 8 | **⚠** | `CountList` 恒 4 行，`ShopCashId` = 900000 / 1597 / 11023 / 15039 **全部是 `ShopCashDBSchema`（656 行配置表）里的行**（当场查过）；`PurchaseCount` 是玩家购买次数（1/1/0/0）；`OrderList` / `MonthlyProductList` 官方本来就是 `[]`。**已覆盖，结构级** |
| 17 | **7003** | Mail_ListSemiPermanent | `api/mail/listsemipermanent` | 556 | `24_7003_api_mail_listsemipermanent.response.json` | **5** | **✅** | **零自有字段，纯 5 键信封**。回灌信封后**逐字节相同** |
| 18 | **7000** | Mail_List | `api/mail/list` | 1,600 | `25_7000_api_mail_list.response.json` | 7 | **✅** | `MailDBs` 2 行（1 封签到奖励 Type=1、1 封商店购买 Type=14）+ `Count: 2`。新号无邮件 → `MailDBs: []` / `Count: 0`。注意两行 `AccountServerId` 都是 **0**（官方就这么发的） |

**合计：✅ 10（26000/1005/16000/25003/15002/7001/28019/43010/7003/7000）· ⚠ 4（90004/35003/36001/29002）· ❌ 4（4000/3/8000/8006）**

### 1.1 请求级覆盖账（第 61–120 行，41 个请求）

| 处置 | 协议 | 请求数 |
|---|---|---|
| 纯空构造即可 | 25003(×7) · 7001(×3) · 28019(×3) · 43010(×3) · 16000(×1) · 15002(×1) · 7003(×1) · 7000(×1) | **20（49%）** |
| 加骨架即可 | 35003(×1) | **1** |
| 现有生成器已覆盖 | 90004(×5) · 36001(×4) · 8000(×3) · 29002(×3) · 4000(×1) · 3(×1) · 26000(×1) · 1005(×1) · 8006(×1) | **20（49%）** |
| **需新写真实数据生成器** | — | **0** |

---

## 2. 「新号 / 空数据」版本长什么样（逐协议，Q4 的答案）

下面每一条都是 `specgen.Spec().build(proto, {})` + 真实信封的实际输出，**不是手抄**。
`<aid>` / `<mx>` / `<ticks>` / `<rid>` 由 session 填（`AccountServerId` / `MxToken` / `.NET 100ns ticks` / 外层 `requestid`，且 `requestid` 必须 == 内层 `RequestId`）。

### 2.1 ✅ 纯空构造（10 个）

```jsonc
// 26000 ContentSave_Get                       —— 回灌信封后与官方逐字节相同
{"Protocol":26000,"SessionKey":{"AccountServerId":<aid>,"MxToken":"<mx>"},"ServerTimeTicks":<ticks>,
 "ServerNotification":0,"RequestId":"<rid>","HasValidData":false,"ContentSaveDB":null,"EventContentChangeDB":null}

// 16000 Toast_List                            —— 逐字节相同
{...(信封)..., "ToastDBs":null}

// 28019 Clan_Check                            —— 纯信封，逐字节相同
{...(信封)...}

// 43010 Friend_Check                          —— 纯信封，逐字节相同（连 ServerNotification 都是 0）
{...(信封)...}

// 7003 Mail_ListSemiPermanent                 —— 纯信封，逐字节相同
{...(信封)...}

// 7001 Mail_Check                             —— 直接抄抓包，把 Count 归 0
{...(信封)..., "Count":0}

// 7000 Mail_List                              —— 把两个容器清空
{...(信封)..., "MailDBs":[],"Count":0}

// 1005 Account_GetTutorial                    —— 空数组（q7 confidence: high）
{...(信封)..., "TutorialIds":[]}

// 25003 Event_RewardIncrease                  —— 空 = 当前无加成活动
{...(信封)..., "EventRewardIncreaseDBs":[]}

// 15002 OpenCondition_EventList               —— 空 map（建议改成回显请求键为 []，见 R3）
{...(信封)..., "ConquestTiles":{}}
```

> 信封 5 键的**取值**是：`Protocol` = 协议号、`SessionKey` = `{AccountServerId, MxToken}`、
> `ServerTimeTicks` = 现在、`ServerNotification` = 0、`RequestId` = 外层同一个 uuid。
> `ServerNotification` 是个**通知位掩码**，见 §4.2 —— 抓包里它按协议恒定取 0 / 3 / 4 / 8 / 1024 / 2048，
> 不是"永远是 0"。空构造填 0 = "什么都没推送"，语义上安全。

### 2.2 ⚠ 需要骨架（4 个）

| 协议 | 骨架内容 | 骨架从哪来 | 空构造会丢什么 |
|---|---|---|---|
| **35003** | `ProgressDBs` 18 行：`{AccountServerId:<aid>, MissionUniqueId:10838×10000+i, Category:7, StartDate:<now>, ProgressParameters:{<parcelKey>:0}}`；`MissionHistoryUniqueIds:[]`；`ClearedOrignalMissionIds:null`（**注意官方字段名拼错成 `Orignal`，不能修正**） | `MissionUniqueId` 可由 `EventContentId` 算；`ProgressParameters` 的键（`10838` / `110838101` / …）**必须查 ExcelDB 的 mission 表**。官方样本的 18 行进度已经全是 0，所以骨架 = 抓包 18 行换掉 `AccountServerId` + `StartDate` | 小游戏任务页 0 条任务 |
| **36001** | `Reddots: {}` + `EventContentUnlockCGDBs` 25 键全 `[]`（`10838, 50822, 849, 900801–900806, 900808–900820, 900825–900827`） | **已有现成的**：`dto_extra\proto36001_reddot.json` → `catalog_constants.eventcontentunlockcg_keys.keys`，`gen36001.cg_keys_from_dto()` 已经在用 | 25 个活动内容键全丢（客户端若按硬编码 id 索引该 map → 风险见 R1） |
| **25003** | 想让"奖励加成"活动生效才需要：1 行 `{EventTargetType:4, RewardRealType:100473, Multiplier:{rawValue:20000}, BeginDate, EndDate}` | 抓包原文；但**日期是 2026-11-12→11-19 的周活动窗口**，过期后本来就不该出现 | 不丢 —— 空 `[]` 就是"无加成活动"，**所以这个其实可以不填骨架，✅ 也成立** |
| **29002** | `CountList`：4 行 `{ShopCashId, PurchaseCount:0, ResetDate, PurchaseDate:"0001-01-01T00:00:00"}`；`OrderList:[]`；`MonthlyProductList:[]` | `ShopCashId` 全是 `ShopCashDBSchema`（656 行）的配置行，可查；`ResetDate` 是每商品的周期锚点，**新号该填什么是纯猜测** | 购买次数记录为空。客户端商店商品目录走 `10002 Shop_List`，不走这里 → 大概率无感 |

### 2.3 ❌ 需要真实数据（4 个，全部已有生成器）

| 协议 | 缺什么 | 空构造会怎样 |
|---|---|---|
| **4000** | 134 行道具实例 | 空背包（新号本来就只有 `DefaultParcelExcelTable` 1 行） |
| **3** | 请求回显的两个 tick | 时钟偏移算错 |
| **8000** | 1240 行任务进度 + 372 个历史 id | 任务页全空 |
| **8006** | 733 行向导任务进度 + 17 行赛季登录记录 | 向导任务页全空 |

**这 4 个全都不在新写的范围里 —— 一个都不用为它们操心。**

---

## 3. 分组结论

### 3.1 完全空构造就能覆盖的（✅ 10 个）

**未覆盖的 8 个（本批新增可上线的）**：
`16000 Toast_List` · `25003 Event_RewardIncrease` · `15002 OpenCondition_EventList` · `7001 Mail_Check` ·
`28019 Clan_Check` · `43010 Friend_Check` · `7003 Mail_ListSemiPermanent` · `7000 Mail_List`

**已覆盖的 2 个**：`26000 ContentSave_Get`（逐字节）· `1005 Account_GetTutorial`（逐字节，需 `tutorial_ids` 注入）

> 共同特征：**自有字段 ≤ 1 个，且该字段的空值是客户端能理解的"没有东西"**。
> 其中 3 个（28019 / 43010 / 7003）自有字段数 = **0**，就是纯信封，抄都省了。

### 3.2 需要抄一组静态骨架的（⚠ 4 个）

- **35003**（未覆盖）—— 18 行小游戏任务骨架，**唯一一个需要新工作的**
- **36001** —— 25 键 catalog 常量，**骨架已经在 `dto_extra` 里了**，加个 adapter 即可
- **29002** —— 4 行 CountList，配置行可从 ExcelDB 查，`ResetDate` 要猜
- **90004** —— 运营数据（公告/活动/banner/抽卡公示），跟账号无关，可全 `[]`；但为了抽卡概率公示页建议保留 12 行

> 共同特征：**骨架对所有账号相同**（或只差 `AccountServerId` / `StartDate` 两个可算字段），
> 也就是说 3.2 的所有内容都是**"抄一次，永久用"**，不产生 per-account 状态。

### 3.3 必须真实数据的（❌ 4 个）

`4000 Item_List` · `3 NetworkTime_Sync` · `8000 Mission_List` · `8006 Mission_GuideMissionSeasonList`

> 共同特征：字段内容**逐元素绑定账号**（道具实例 id / 任务进度 / 登录记录），或者**必须回显请求**（Netw时间同步）。
> **难点：这 4 个已经全都有生成器了**，其中 4000 / 3 / 8006 是逐字节的，8000 只差一个 `progress_rows` 注入槽。
> 所以「❌」在这份清单里**不构成新工作量**。

---

## 4. 特别要查的 5 个问题

### 4.1 `contentsave/get` 和 `account/gettutorial` 都是 640 B —— 是同一个空骨架吗？

**不是。完全是两个不同的东西。**

| | 26000 ContentSave_Get | 1005 Account_GetTutorial |
|---|---|---|
| 顶层键数 | **8** | **6** |
| 自有字段 | `HasValidData:bool` + `ContentSaveDB:null` + `EventContentChangeDB:null` | `TutorialIds:[21 个 int]` |
| plaintext 长度 | **438** | **437** |
| 空版本 | `HasValidData:false` + `null` + `null` | `TutorialIds:[]` |

**为什么都是 640 B**：wire 长度 = `4·ceil((PKCS7pad(plain,16)+32)/3)`（+32 是随包下发的 AES 密钥）。
按这个公式算，**plain ∈ [433,448] 全部落在 640 B**，这是一个 **16 字节宽的 AES 块平台**，不是结构相等。
437 和 438 都在平台里。

> **方法论警告：这批响应字节数的分辨率就是 16 字节（AES 块宽）。**
> "两个协议大小一样"在这批数据里**完全不能**作为"结构一样"的证据 —— 差 15 个字符都可能同尺寸。

### 4.2 `mail/check` / `clan/check` / `friend/check` 都是 536–556 B —— 是同一个布尔型响应吗？

**不是同一个，而且它们根本不是"布尔型响应"。**

| 协议 | 顶层键数 | 自有字段 | `ServerNotification` |
|---|---|---|---|
| 7001 Mail_Check | 6 | `Count: int`（官方 2） | **8**（9/9 样本） |
| 28019 Clan_Check | **5** | **无** | **2048**（8/8 样本） |
| 43010 Friend_Check | **5** | **无** | **0**（8/8 样本） |

两件事：

1. **7001 比另外两个多一个 `Count`，字节数就差了 20**。`28019 / 43010` 是**字面上的"只有信封"**——
   连一个自有字段都没有，服务端"没什么可说的"就直接回 5 个键了事。
   所以 **28019 / 43010（536 B）和 7003（556 B）是同一类东西：纯信封、零自有字段**。
   536 ↔ 556 的分界正好是 plaintext = 367/368（一个 AES 块边界的两侧，PKCS#7 在整块时再补满一块）：
   28019=360、43010=359 → 536；7001=368、7003=368、16000=375 → 556。

2. **"有没有新东西"这个信号不在响应体里，在 `ServerNotification` 位掩码里。**
   抓包里它**按协议恒定**：`7001→8`、`28019→2048`、`43010→0`、`7000→8`、`20013→1024`、`28000→4`、
   `8002→3`、`22004→3`、其余 0。同一个协议 8~21 次观测一次都没变过。
   - **事实**：它是位掩码式的服务端通知标志，且在本抓包内**按协议是常量**。
   - **推测**：位 3(8)=邮件/签到有变化、位 11(2048)=工会、位 10(1024)=咖啡厅、位 0|1(3)=任务/货币 ——
     即"告诉客户端哪些面板该刷新"。这段是推断，**没有客户端代码证据**。
   - **落地含义**：空构造填 0 = "什么都不用刷新"，对 poll 型 RPC 语义安全（不会异常，只是红点不亮）。

### 4.3 `mission/guidemission` 160 KB —— 是一整棵教程任务树（静态配置）吗？

**不是。它是一份"逐账号的任务进度表"，不是静态配置数据。** 而且它**不是** `api/mission/guidemission`，是 8006（见 §0.1 第 1 条）。

三个反证：

1. `MissionProgressDBs` **733 行，每行第 1 个字段就是 `AccountServerId: 10015354380`**
2. 每行有 `StartDate`，而且是**账号真实的首次见到时间**：`"2026-06-06T11:44:44.202"` —— 和 `GuideMissionSeasonDBs[0].StartDate` 一模一样（= 该号创建时刻）。这个值**没法从配置推**
3. `GuideMissionSeasonDBs` 17 行里 `{SeasonId:3, LoginCount:7, StartDate:…, LoginDate:2026-07-29T03:10:47.63, IsFinalMissionComplete:true}` ——
   `LoginCount` / `LoginDate` / `IsFinalMissionComplete` **是纯玩家行为**。注意后面 14 行只剩 `{"SeasonId":5}` 这种形态，
   那是 proto3 零值省略（`LoginCount:0`、`IsFinalMissionComplete:false` 被省掉了），**不是缺数据**

**但有一个例外值得记**：733 行的 `ProgressParameters` **全部是 `{"0":0}` / `{"7100042":0}` 这种"进度 0"**，
也就是这份"733 行"是服务端在登录时给当前赛季**整体铺出来的任务骨架**，进度还没动。
`gen8006` 默认就是从 ExcelDB **推 733/17** 这两组行数的 —— 所以**行数和行内容是可配置推导的**，
不可推导的只有 `AccountServerId` 和两个 `StartDate`。这把它从"❌ 要真实进度"降级成
"❌ 要真实数据里最轻的一档"，也解释了它为什么能逐字节（回灌官方 `mission_rows` 时）。

### 4.4 `billing/purchaselist` 1,280 B —— 是商店列表（静态）吗？

**不是商店目录。** 真正的商店目录是 `10002 Shop_List`（抓包 `86_10002`，2,535 B）。

29002 是**购买次数覆盖层**：
- `CountList`：4 行 `{ShopCashId, PurchaseCount, ResetDate, PurchaseDate}` —— 只记"这个商品你买过几次、周期何时重置"
- `OrderList: []`、`MonthlyProductList: []` —— 官方这个号两个都是空的

`ShopCashId` 的 4 个值（900000 / 1597 / 11023 / 15039）**全部是 `ShopCashDBSchema` 656 行配置表里的行**（当场 SQL 查过），
所以"哪些商品该出现"是配置决定的；`PurchaseCount` 是玩家买了几次。

**结论：⚠ 骨架。** 纯空 `CountList: []` 结构合法、语义是"没买过任何东西"，
**大概率更正确**；风险只在"客户端若拿它算剩余可购买次数"（推测，无证据）。

### 4.5 `event/rewardincrease` / `opencondition/eventlist` / `notification/eventcontent` 是活动配置、跟账号无关吗？

**三个都对，但"跟账号无关"的程度不一样：**

| 协议 | 判定 | 依据 |
|---|---|---|
| **25003 Event_RewardIncrease** | **✅ 完全跟账号无关** | 行内只有 `EventTargetType / RewardRealType / Multiplier / BeginDate / EndDate`，**没有 AccountServerId**。21/21 观测恒 1 行、内容完全相同。纯服务端活动窗口 |
| **15002 OpenCondition_EventList** | **✅ 跟账号无关，但跟请求有关** | 唯一的自有字段 `ConquestTiles` 是 `map<conquestEventId, tiles[]>`，键 **= 请求里的 `ConquestEventIds`**（请求原文：`"ConquestEventIds":[50822], "WorldRaidSeasonAndGroupIds":{"821":[821602],"823":[823100]}`）。所以它不是"账号数据"也不是"配置数据"，而是**"你问什么我答什么"的回显容器** |
| **36001 Notification_EventContentReddotCheck** | **⚠ 键是配置目录，值是账号状态** | `EventContentUnlockCGDBs` 的 25 个键是**活动内容目录常量**（10/10 样本键集合完全稳定）；值是**该号已解锁的 CG 列表**，官方这里 25 个全是 `[]`（= 一个都没解锁）。`Reddots: {}` 也是账号状态（没红点） |

> 注意 `notification/eventcontent` 的完整 URL 是 `api/notification/eventcontentreddotcheck` = **36001**，
> 而 36001 **已经有逐字节生成器**。所以这条虽然"活动类"，但不在待办里。

---

## 5. 通用空构造的技术可行性判断

### 5.1 结论

**可行，而且引擎已经存在，不需要新写。**

`work\ba\server\prototype\specgen.py` 的 `Spec.build(proto, values)` 就是这台机器：
- `Spec.default(node)`：int→0、float→0.0、str→""、bool→false、array→[]、map→{}、null→None、object→递归
- `Spec.conform({}, node)`：spec 里 `always:true` 的键用默认值补，`always:false` 的键**省略**
  （正好对上 proto3 的零值省略——抓包里 `{"SeasonId":5}` 就是活证据）
- `Spec.build()` 最后按 `top_key_order` 重排 → **官方键序**

实测：`Spec().build(p, {})` 对 18 个协议**键序 18/18 一致、键集合 18/18 一致、`spec_check` 18/18 PASS**。

### 5.2 输入需要什么

| 输入 | 够不够 | 说明 |
|---|---|---|
| **`official_spec.json`** | **够产出"形状"，但不够产出"语义"** | 它给了：字段树、类型、`always`（必填/可选 presence）、`nullable`、map 的 `key_kind`、array 的 `items` 形状、`top_key_order`、`is_player_data`。它**没给**：`"values_included": false` —— 一个具体值都没有。更要命的是 `len_min/len_max` 是**观测范围不是合法范围**：`spec_check.py` 把「长度越界」和「空数组首见」都列成 **WARN（合法）**。所以 spec 无法回答"这 18 行是不是必需的" |
| **`initial_state_rules.json`** | **部分够，缺本次这 4 条** | 它已经有 `server_apply_skeleton`（16 类：`CharacterDBs/ItemDBs/EquipmentDBs/EmblemDBs/AccountAttachmentDB/AccountCurrencyDB/EchelonDBs/CafeDBs/ScenarioHistoryDBs/ScenarioGroupHistoryDBs/TutorialIds/ShopRecruits/ShopFreeRecruitHistoryDBs/MemoryLobbyDBs/AcademyLocationDBs`）+ `q7_tutorials`（`TutorialIds:[]`，high）+ `other_initial_state.default_mail`。**但它一条都不覆盖本次需要的 35003 / 36001 / 29002 骨架** |
| **`dto_extra\*.json` 的 `catalog_constants`** | **补上了 36001** | 25 个 CG 键已在 `proto36001_reddot.json` 里，`gen36001` 正在用。这是"目录常量"的正确存放位置 |
| **ExcelDB.db** | 35003 / 29002 的骨架来源 | `MissionUniqueId = EventContentId×10000+i`、`ProgressParameters` 的键、`ShopCashDBSchema` 的 656 行 |
| **session（ctx）** | **必需，不可省** | 信封 5 键必须由 ctx 覆盖：`Protocol` / `SessionKey{AccountServerId, MxToken}` / `ServerTimeTicks` / `RequestId`。`build(proto,{})` 直接发出去会是 `Protocol:0, MxToken:"", ticks:0, RequestId:""` —— 必死 |

**所以：`official_spec.json` 够做"形状"，要落地必须再加一层"每个协议的骨架/覆盖规则"。**
最小新增物是一张 per-protocol 规则表（可以长在 `initial_state_rules.json` 新 section 里，也可以单开一个
`empty_skeleton_rules.json`），每条 3 个字段：

```jsonc
"35003": {
  "mode": "skeleton",                    // empty | skeleton | custom
  "skeleton_from": "exceldb:mission_table+event_content_id",   // 骨架来源
  "overlay_keys": ["ProgressDBs"]        // 这几个键用骨架，其余走 spec 零值
}
```

### 5.3 输出形态

和现有 8 个生成器**完全一致**：**返回 inner dict**（不是 bytes）。
布线是三层，注册表已经定好：

```
specgen.Spec.build(proto, skeleton)   →  inner dict（键序由 spec 决定）
        ＋ obj.update(account.envelope(proto))            ← 信封 5 键
        →  R.build_inner(proto, ctx)  →  cn_wire.wrap_response(...)  →  wire body
```

**一个实测过的实现细节（省掉一个坑）**：`Spec.build()` 产出的 dict **已经包含**那 5 个信封键
（因为 `always:true`），所以在它上面 `obj.update(envelope)` 是**原位替换、键序不变**。
我验证过 18/18 键序仍然与官方一致。也就是说套信封这一步**零键序风险**，不需要额外排序。

### 5.4 一句话评价

> 这不是"造一个新引擎"，是**给 `Spec.build` 配一张 9 行的配置表**。
> 引擎（`specgen.py`，531 行）已经在仓库里跑了很久（1005 / 4000 / 26000 就是它在支撑）；
> `generator_registry.py` 已经把分发和 ctx 契约做好了。
> **真正缺的那一块，是"哪个协议允许空、哪个要骨架"这个判断 —— 而这份报告就是它。**

---

## 6. 风险：哪些协议空构造会被客户端当异常

按风险从高到低。**以下"客户端会怎样"全部是推测**（没有客户端反编译证据），
但"抓包长什么样"是事实。

### R1 —— `36001 EventContentUnlockCGDBs` 从 25 键变 0 键｜**中高风险**

官方 10/10 样本都是**恒定 25 个键**、值全 `[]`。这是"键集合完全稳定"的强信号：
它更像**服务端把活动内容目录整份铺下来**，而不是"有解锁才出现"。
- **推测**：客户端很可能拿着硬编码的 event content id 去索引这个 `Dictionary<long, List<…>>`。
  C# 里 `dict[id]` 缺键抛 `KeyNotFoundException`；`TryGetValue` 则安全。**无法从抓包判断它用的是哪种**。
- **代价**：填 25 键的成本 ≈ 0（`dto_extra` 里就有）。**没有理由冒险，直接填。**
- 这条已经在 `gen36001` 的逐字节实现里了 → 不是新工作。

### R2 —— `15002 ConquestTiles` 从 `{"50822":[]}` 变 `{}`｜**中风险**

同 R1 的机制，但更明显：**键就是请求里的 `ConquestEventIds`**。
客户端问什么、服务端答什么，这是"按 id 回显"的典型形状。
- **推测**：客户端可能遍历自己发出去的 id 列表去查响应 map。
- **代价**：低成本化解 —— 从 `ctx['request_body']` 取 `ConquestEventIds`，逐个填 `[]`。
  这正是 `generator_registry.py` 已经预留的 `request_body` 槽（`CTX_KEYS` 里有，现在没人用）。
  **这是本批唯一一个"空构造需要读请求"的协议。**

### R3 —— `3 NetworkTime_Sync` 两个 tick 置 0｜**高风险（但已覆盖）**

`ReceiveTick` / `EchoSendTick` 是客户端发包时打的时间戳，服务端原样回来。
- **推测**：客户端用它们算 RTT 和 server-time offset；0 会导致偏移量巨大，
  所有倒计时 / 每日重置 / 活动结束时间显示错乱。
- **结论**：**绝对不要对 3 用空构造。** 它已有逐字节生成器（`gen3.build_3` 收 `recv_tick/echo_tick`）。放心。

### R4 —— `1005 TutorialIds` 置 `[]`｜**玩法风险，不是异常风险**

结构上 100% 合法（`q7` 明说新号就是 `[]`）。但语义上：
- **推测**：`TutorialIds` 是"已播过的教程"记录，空 = 客户端认为你**一步教程都没走**，
  于是重放整个新手教程。
- **真实风险**：如果你的 1017 状态里已经给了玩家"教程之后才有的东西"（编队、抽取角色），
  就会出现"教程重放 + 状态已经是老号"的自相矛盾。**这是产品决策，不是 bug。**
- 已有 `tutorial_ids` 注入槽，想跳过就填 `[1..27]` 之类。

### R5 —— `7001 Count` 与 `7000 MailDBs` 不一致｜**中低风险**

`7001 Mail_Check` 的 `Count`（官方 2）和 `7000 Mail_List` 的 `Count`（官方 2）是同一个数。
- **推测**：客户端拿 `7001.Count` 决定信箱红点、拿 `7000.MailDBs` 渲染列表。
  两个必须同源，否则"红点亮着但点进去 0 封"。
- **代价**：空构造下两边都给 0，天然一致。**只要你不同时实现邮件投递，就没有风险。**

### R6 —— `7000 MailDBs:[]` 但服务端其实发了邮件｜**中高风险（一旦你实现邮件）**

`initial_state_rules.other_initial_state.default_mail` 说新号可能有 **1 封**默认邮件
（`defaultmailexceltable`，3 个附件 `[2]/[3]/[1200]`，置信度只到"medium"，且字段映射**未闭合**）。
- 一旦你的服务端真的给新号发邮件，`MailDBs:[] + Count:0` 就是**在撒谎**。
- **边界**：空构造的适用前提是"服务端确实没有邮件"。这条要写进规则表的注释里。

### R7 —— `35003 ProgressDBs:[]`｜**低风险（体验）**

不会异常，但小游戏任务页 0 条。**推测**客户端只是渲染空列表。
- 顺带一个**必须注意的坑**：官方字段名是 **`ClearedOrignalMissionIds`**（`Orignal`，拼错的）。
  spec 里就是这么记的，`Spec.build` 也照抄。**任何"顺手修正拼写"都会让 `spec_check` FAIL。**

### R8 —— `90004 Data` 全 `[]`｜**低风险（合规）**

结构合法。但 12 行 `GachaProbabilityDisplay` 是**国服抽卡概率公示**，属监管要求。
- **推测**：空数组会让"概率公示"页面空白。不至于崩，但会很难看，且可能被审核挑。
- **代价**：`gen90004` 已经有 `ops` 注入槽，抄抓包 12 行即可。

### R9 —— 全局：`spec_check` PASS **不能**当"语义正确"的证据｜**方法论风险**

`spec_check.py` 第 16–18 行把「长度越界」「空数组首见」定义为 **WARN（合法）**，
第 233–237 行就是这两条的实现。所以 `Spec.build(proto,{})` 的结果**按构造必然 PASS**。
- **含义**：18/18 PASS 只证明"形状合法"，**不证明"客户端接受"**。
- **含义**：反过来也说明本项目从来不认为"空数组"是错误——它是一个被显式承认的合法态。

### R10 —— 字节数不能当结构证据｜**方法论风险**

见 §4.1。wire 长度 = `4·ceil((PKCS7pad(plain,16)+32)/3)`，**分辨率 16 字节**。
- `437` 和 `438` → 都 640 B
- `359`/`360` → 536 B；`368`/`375` → 556 B
- 结论：**"536–556 是同一个东西"和"640 是同一个东西"两个直觉，在数学上都不成立。**

---

## 7. 工作量估计

### 7.1 做通用空构造（推荐）

| 工作项 | 量 | 说明 |
|---|---|---|
| 引擎 | **0 行** | `specgen.Spec.build(proto, {})` 已经在跑，实测 18/18 |
| per-protocol 规则表 | **1 个文件，~40 行 JSON** | 18 条，每条 `mode` + `skeleton_from` + `overlay_keys`。其中 10 条是 `{"mode":"empty"}` |
| 骨架数据 | **3 条**（35003 / 29002 / 90004） | 36001 的骨架**已有**（`dto_extra` 的 catalog_constants） |
| 35003 骨架推导 | **~80 行** | `MissionUniqueId = EventContentId×10000+i` 可算；`ProgressParameters` 的键要查 ExcelDB mission 表 → 复用 `gen_common.ExcelDB` / `fb_slot_int` |
| registry adapter | **~15 行** | 一个 `_adapt_specgen(proto)`：`S.build(proto, skeleton)` + `obj.update(envelope)`。键序已验证无风险 |
| 15002 回显 | **~5 行** | 从 `ctx['request_body']['ConquestEventIds']` 填键 |
| 回归测试 | **~50 行** | 对 41 个请求逐个比对"结构合法 + 键集合 + 字节数落位" |

**合计 ≈ 200 行新代码 + 1 张规则表。按现有节奏是半天到一天。**
**收益：一次性拿下 9 个协议里的 8 个（+35003 一个骨架槽），覆盖率 21/38 → 30/38。**

### 7.2 逐个手写

按现有生成器的实际体量外推（`gen36001.py` = 112 行是**最简的那个**，`gen8006.py` = 11 KB，`gen8000.py` = 41 KB）：

| 协议 | 预估 | 依据 |
|---|---|---|
| 28019 / 43010 / 7003 | 各 ~30 行 | 纯信封，连字段都没有，抄 5 行 JSON 就完了 |
| 16000 / 25003 / 15002 | 各 ~40-60 行 | 1 个空容器 |
| 7001 / 7000 | 各 ~60-100 行 | 1-2 个字段 + 邮件行 |
| 35003 | **~150 行** | 18 行骨架 + ExcelDB mission 表查询 + `ProgressParameters` 键 |
| 每个都要配套 | 自测 + `--verify-official` + DTO 交叉校验 | 参照 `gen36001` 的 `verify_official()` |

**合计 ≈ 600–800 行 + 9 套自测。2 天左右，且每个协议一份独立维护负担。**

### 7.3 结论

> **通用空构造的性价比是 ~4 倍**（半天 vs 2 天），而且它产出的东西**天生与 spec 对齐**
> （`Spec.build` 保证 PASS `spec_check`，手写的不会）。
>
> **但要说清楚：通用空构造是个桥，不是终点。** 它成立的唯一原因是
> **"现在私服确实没有邮件 / 没有工会 / 没有好友 / 没有活动加成"**。
> 一旦你实现邮件投递、工会创建、活动配置，这 8 个协议里至少
> **7000 / 7001（邮件）、28019（工会）、25003 / 15002（活动）** 必须换成真生成器。
>
> **所以建议的写法是**：规则表里给每个协议标 `mode: "empty"` 的同时写一句
> `"until": "邮件投递上线前"` —— 让它明确是一条**有到期日的占位**，而不是假装它是终态。
> 这比手写 9 个生成器再多删掉 5 个要省事得多。

---

## 8. 复现命令（全部只读，不落盘任何 `.py`）

```powershell
cd C:\Users\su\Desktop\大肥鱼项目\BAServer
$env:PYTHONDONTWRITEBYTECODE="1"

# ① 确认 guidemission 就是 8006、且没有独立 protocol
python work\ba\proto\lookup.py find mission

# ② 空构造 18 个协议 → 与抓包比键序/键集合/逐字节
#    代码经 stdin 送入 python，不创建文件（见本报告 §1 / §0.3 的实现，共 ~25 行）

# ③ 空构造过 spec_check
python work\ba\proto\spec_check.py --all            # 109/109 PASS（既有结果）

# ④ 25 个 CG 键的来源
python -c "import json;print(json.load(open(r'work\ba\proto\dto_extra\proto36001_reddot.json'))['catalog_constants']['eventcontentunlockcg_keys']['keys'])"

# ⑤ ShopCashId 是否配置行
python -c "import sqlite3;c=sqlite3.connect(r'file:work/ba/data/ExcelDB.db?mode=ro',uri=True);print(len(c.execute('SELECT Id FROM ShopCashDBSchema').fetchall()))"
```

---

## 附录 A：本报告用到的关键数字（一次查表）

`plaintext` = 官方外层明文 `plain` 字段的 UTF-8 字节数（**不是** inner 紧凑 JSON 的长度，两者差一个信封）；
`wire` = 实际响应字节数。**18/18 用 `wire = 4·ceil((PKCS7pad(plaintext,16)+32)/3)` 复算全部命中**
（当场验过，0 例外）—— 所以 `plaintext` 这一列是唯一能把"字节数巧合"和"结构相同"区分开的量。

| 协议 | 顶层键 | 自有字段 | plaintext | wire | 空构造后与官方的差异位置 |
|---|---|---|---|---|---|
| 4000 | 7 | ItemDBs, ExpiryItemDBs | 12,031 | 16,088 | `ItemDBs` |
| 3 | 7 | ReceiveTick, EchoSendTick | 430 | 620 | `ReceiveTick`, `EchoSendTick` |
| 26000 | 8 | HasValidData, ContentSaveDB, EventContentChangeDB | **438** | **640** | **无（逐字节）** |
| 90004 | 6 | Data | 10,548 | 14,124 | `Data` |
| 1005 | 6 | TutorialIds | **437** | **640** | `TutorialIds` |
| 8000 | 10 | HistoryDBs, ProgressDBs, DailySuddenMissionInfo, MissionHistoryUniqueIds, ClearedOriginalMissionIds | 201,253 | 268,396 | 4 处 |
| 8006 | 7 | MissionProgressDBs, GuideMissionSeasonDBs | 120,115 | 160,216 | 2 处 |
| 35003 | 8 | MissionHistoryUniqueIds, ProgressDBs, ClearedOrignalMissionIds | 3,327 | 4,480 | `ProgressDBs` |
| 16000 | 6 | ToastDBs(null) | **375** | **556** | **无（逐字节）** |
| 25003 | 6 | EventRewardIncreaseDBs | 556 | 792 | `EventRewardIncreaseDBs` |
| 15002 | 6 | ConquestTiles | 403 | 600 | `ConquestTiles` |
| 36001 | 7 | Reddots, EventContentUnlockCGDBs | 773 | 1,088 | `EventContentUnlockCGDBs` |
| 7001 | 6 | Count | **368** | **556** | `Count` |
| 28019 | **5** | — | **360** | **536** | **无（逐字节）** |
| 43010 | **5** | — | **359** | **536** | **无（逐字节）** |
| 29002 | 8 | CountList, OrderList, MonthlyProductList | 922 | 1,280 | `CountList` |
| 7003 | **5** | — | **368** | **556** | **无（逐字节）** |
| 7000 | 7 | MailDBs, Count | 1,157 | 1,600 | `MailDBs`, `Count` |

## 附录 B：本次会话的边界

- 新增文件：**只有本文件**（`work\ba\server\deploy\_scratch\UNCOVERED_ANALYSIS.md`）
- 修改文件：**无**
- 新建 `.py`：**无**（所有分析代码走 `python -` stdin，且 `PYTHONDONTWRITEBYTECODE=1` + `sys.dont_write_bytecode` 双保险，未产生 `.pyc`）
- 服务器 / bridge / 手机 / nginx：**未接触**
- 删除：**无**
- 所有 `specgen` 调用都是 `Spec()` 的只读方法（`build` / `default` / `conform` / `name` / `top_key_order`），
  **没有调用 `write_json`**，没有落盘任何生成物
