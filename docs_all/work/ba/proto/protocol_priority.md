# BA 国服私服 · 109 条游戏 RPC 实现优先级

> 生成：`work/ba/proto/_gen_priority.py`（数据唯一来源），产物：`protocol_priority.json` + 本文件
> 字节数取证：`report/_tmp/official_decoded_201/*.response.json` 的 `meta.resp_bytes`（真实 HTTP body 长度）
> 协议号/名称：`work/ba/proto/protocol_map.json`（501 条）
> 新号初始值：`work/ba/proto/initial_state_rules.json`（10 问 + 附加，逐条带证据）
> 静态表：`work/ba/data/ExcelDB.db`（398 张表）与 `work/ba/proto/_tablelist.txt`（行数/列名）

---

## 0. 一页速览

- **109 条 RPC** = 109 对 request/response 文件；**38 个协议** = 38 个不同协议号。一条协议会被调多次（`25003` 21 次、`36001`/`90004` 各 10 次、`7001` 9 次、`28019`/`43010` 各 8 次）。
- **F 类（纯上报）在这 109 条里 = 0 条**。抓包里确有纯上报流量（`app.adjust.cn/event`、`state-api`、`sdk-api.yostar.cn`），但都不是游戏 RPC，不在本表内。
- **最大的错觉**：`1017` 不是「一条协议」，它一次下发 **30 个子回包**（请求 `SyncProtocols` 点名 25 个协议号），做 `1017` ≈ 做 25 条 List 类协议。

| 类别 | 名称 | 含义 | 协议数 | 协议号 |
|---|---|---|---|---|
| A | 门槛 | 不做客户端就卡住，进不了下一步 | 3 | 1002 24000 1017 |
| B | 大厅必要 | 不做进得了大厅但界面会崩/黑屏/报错 | 7 | 3 26000 90004 1005 4000 8000 8006 |
| C | 功能入口 | 不做某个入口点进去报错 | 14 | 7000 7003 15002 30041 8002 28019 43010 29002 10002 20001 20013 28000 90009 35003 |
| D | 战斗相关 | 不做打不了 | 8 | 6000 5000 5001 6020 6021 22000 22016 22004 |
| E | 可选/装饰 | 不做也能玩（红点 / toast / 活动加成 / 排名奖励） | 6 | 7001 25003 36001 16000 22008 22009 |
| F | 纯上报 | 不影响游戏（本次 109 条里 0 条） | 0 | — |

| 批次 | 目标 | 协议数 | 工作量(人日) | 协议号 |
|---|---|---|---|---|
| 1 | 连通 | 3 | 9.0 | 1002 24000 1017 |
| 2 | 进大厅 | 7 | 15.5 | 3 26000 90004 1005 4000 8000 8006 |
| 3 | 能操作主界面 | 12 | 9.0 | 7001 7000 7003 25003 36001 16000 15002 30041 8002 28019 43010 29002 |
| 4 | 能打一场战斗 | 8 | 26.5 | 6000 5000 5001 6020 6021 22000 22016 22004 |
| 5 | 商店 / 咖啡厅 / 公会 | 6 | 13.5 | 10002 20001 20013 28000 90009 35003 |
| 6 | 可选 | 2 | 1.0 | 22008 22009 |

**总工作量 ≈ 74 人日**（口径：小=0.5 / 中=2 / 大=5）。其中第 4 批（战斗）一个人吃掉 26 人日，是整条路线的真正瓶颈。

---

## 1. 分类口径

````
A 门槛      不做客户端就卡住，进不了下一步
B 大厅必要  不做进得了大厅但界面会崩/黑屏/报错
C 功能入口  不做某个入口点进去报错
D 战斗      不做打不了
E 可选/装饰 不做也能玩（红点 / toast / 活动加成 / 排名奖励）
F 纯上报    不影响游戏（本 109 条里 0 条）
````

**判定依据（不是拍脑袋）**

1. **客户端实调顺序**（`observed_sequence.json` + `report/67`）：启动链 seq 0–13 是必经段，seq 14 以后进入 5 秒轮询，再往后的调用都由「点了哪个按钮」驱动。
2. **响应业务字段数**：只有 5 个信封字段（`Protocol/SessionKey/ServerTimeTicks/ServerNotification/RequestId`）的是空体协议，风险天然低。
3. **响应体积**：字节数就是数据量，直接对应实现成本。
4. **实测反证**：`report/67` §1.A 记录了「24000 回 192B 假包 → 8 秒后弹同步错误并回标题」；`report/83` §5 记录了「1002 内层 `Protocol` 从字符串改整数才推进到昵称界面」。

---

## 2. 分类总表（38 协议）

工作量口径：小 = 0.5 人日（回固定值/回显），中 = 2 人日（1–2 张静态表 + 账号存档），大 = 5 人日（多表 + 大列表 / 战斗 / 多人）。

| 协议号 | 名称 | 类别 | 批次 | 官方响应字节 | 调用次数 | 数据来源 | 工作量 | 已有实现 |
|---|---|---|---|---|---|---|---|---|
| 1002 | Account_Auth | A | 1 | 5056 | 1 | 玩家进度存档<br>初始值规则<br>官方运营配置 | 中 | 手写实现 |
| 1017 | Account_LoginSync | A | 1 | 246808 | 1 | 玩家进度存档<br>ExcelDB.db 静态表<br>初始值规则<br>官方运营配置 | 大 | 手写实现 |
| 24000 | Academy_GetInfo | A | 1 | 17560 | 2 | 玩家进度存档<br>ExcelDB.db 静态表<br>初始值规则 | 中 | 手写实现 |
| 3 | NetworkTime_Sync | B | 2 | 620 | 1 | 纯回显请求参数 / 常量 | 小 | 完全没有 |
| 1005 | Account_GetTutorial | B | 2 | 640 | 1 | 玩家进度存档<br>ExcelDB.db 静态表 | 小 | 通用层可生成 |
| 4000 | Item_List | B | 2 | 16088 | 1 | 玩家进度存档<br>ExcelDB.db 静态表<br>初始值规则 | 中 | 通用层可生成 |
| 8000 | Mission_List | B | 2 | 268396 | 3 | 玩家进度存档<br>ExcelDB.db 静态表 | 大 | 通用层可生成 |
| 8006 | Mission_GuideMissionSeasonList | B | 2 | 160216 | 1 | 玩家进度存档<br>ExcelDB.db 静态表 | 大 | 完全没有 |
| 26000 | ContentSave_Get | B | 2 | 640 | 1 | 玩家进度存档 | 小 | 通用层可生成 |
| 90004 | Management_Data | B | 2 | 14124 | 10 | 官方运营配置 | 中 | 手写实现 |
| 7000 | Mail_List | C | 3 | 1600 | 1 | 玩家进度存档<br>初始值规则<br>官方运营配置 | 中 | 通用层可生成 |
| 7001 | Mail_Check | E | 3 | 556 | 9 | 玩家进度存档 | 小 | 通用层可生成 |
| 7003 | Mail_ListSemiPermanent | C | 3 | 556 | 1 | 纯回显请求参数 / 常量 | 小 | 通用层可生成 |
| 8002 | Mission_MultipleReward | C | 3 | 8320 | 1 | 玩家进度存档<br>ExcelDB.db 静态表 | 中 | 通用层可生成 |
| 15002 | OpenCondition_EventList | C | 3 | 600 | 1 | 官方运营配置<br>玩家进度存档<br>纯回显请求参数 / 常量 | 小 | 通用层可生成 |
| 16000 | Toast_List | E | 3 | 556 | 1 | 玩家进度存档 | 小 | 通用层可生成 |
| 25003 | Event_RewardIncrease | E | 3 | 792 | 21 | 官方运营配置 | 小 | 通用层可生成 |
| 28019 | Clan_Check | C | 3 | 536 | 8 | 纯回显请求参数 / 常量 | 小 | 通用层可生成 |
| 29002 | Billing_PurchaseListByYostar | C | 3 | 1280 | 3 | 玩家进度存档<br>官方运营配置 | 小 | 通用层可生成 |
| 30041 | EventContent_PermanentList | C | 3 | 2156 | 1 | 官方运营配置<br>玩家进度存档 | 小 | 通用层可生成 |
| 36001 | Notification_EventContentReddotCheck | E | 3 | 1088 | 10 | 官方运营配置<br>玩家进度存档 | 小 | 完全没有 |
| 43010 | Friend_Check | C | 3 | 536 | 8 | 纯回显请求参数 / 常量 | 小 | 通用层可生成 |
| 5000 | Echelon_List | D | 4 | 4120 | 4 | 玩家进度存档<br>初始值规则<br>ExcelDB.db 静态表 | 中 | 通用层可生成 |
| 5001 | Echelon_Save | D | 4 | 1004 | 2 | 纯回显请求参数 / 常量<br>玩家进度存档 | 中 | 通用层可生成 |
| 6000 | Campaign_List | D | 4 | 44672 | 1 | 玩家进度存档<br>ExcelDB.db 静态表 | 大 | 通用层可生成 |
| 6020 | Campaign_EnterMainStageStrategySkip | D | 4 | 2072 | 1 | 玩家进度存档<br>ExcelDB.db 静态表 | 中 | 通用层可生成 |
| 6021 | Campaign_MainStageStrategySkipResult | D | 4 | 10284 | 1 | 玩家进度存档<br>ExcelDB.db 静态表 | 大 | 通用层可生成 |
| 22000 | Arena_EnterLobby | D | 4 | 9068 | 2 | 官方运营配置<br>玩家进度存档<br>ExcelDB.db 静态表 | 大 | 通用层可生成 |
| 22004 | Arena_EnterBattle | D | 4 | 67180 | 1 | 玩家进度存档<br>ExcelDB.db 静态表<br>纯回显请求参数 / 常量 | 大 | 通用层可生成 |
| 22016 | Arena_SyncEchelonSettingTime | D | 4 | 640 | 1 | 玩家进度存档 | 小 | 通用层可生成 |
| 10002 | Shop_List | C | 5 | 1304 | 1 | ExcelDB.db 静态表<br>玩家进度存档 | 中 | 通用层可生成 |
| 20001 | Cafe_Ack | C | 5 | 5016 | 1 | 玩家进度存档<br>ExcelDB.db 静态表<br>初始值规则 | 中 | 通用层可生成 |
| 20013 | Cafe_ReceiveCurrency | C | 5 | 11136 | 1 | 玩家进度存档<br>ExcelDB.db 静态表 | 中 | 通用层可生成 |
| 28000 | Clan_Lobby | C | 5 | 35864 | 1 | 玩家进度存档 | 大 | 通用层可生成 |
| 35003 | MiniGame_MissionList | C | 5 | 4480 | 1 | 玩家进度存档<br>ExcelDB.db 静态表 | 小 | 通用层可生成 |
| 90009 | Clan_Chat_Records | C | 5 | 30316 | 2 | 玩家进度存档 | 中 | 通用层可生成 |
| 22008 | Arena_CumulativeTimeReward | E | 6 | 3072 | 1 | 玩家进度存档<br>ExcelDB.db 静态表 | 小 | 通用层可生成 |
| 22009 | Arena_DailyReward | E | 6 | 3224 | 1 | 玩家进度存档 | 小 | 通用层可生成 |

---

## 3. 分批实施计划

### 第 1 批 · 连通 —— 必须最先做，否则连不上

协议数 **3**，工作量 **9.0 人日**。

| 协议号 | 名称 | 类别 | 响应字节 | 依赖数据表 | 工作量 | 人日 | 已有实现 |
|---|---|---|---|---|---|---|---|
| 1002 | Account_Auth | A | 5056 | CurrencyDBSchema(29)、AttendanceDBSchema(31)、AttendanceRewardDBSchema(334) | 中 | 2.0 | 手写实现 |
| 1017 | Account_LoginSync | A | 246808 | 见 §4 的 30 个子回包各自的表 | 大 | 5.0 | 手写实现 |
| 24000 | Academy_GetInfo | A | 17560 | AcademyLocationDBSchema(11)、AcademyLocationRankDBSchema(12)、AcademyZoneDBSchema(95)、AcademyFavorScheduleDBSchema(1053)、AcademyTicketDBSchema(5)、AcademyRewardDBSchema(564) | 中 | 2.0 | 手写实现 |

- 先做 `1002`：`AccountDB` 23 字段 + `SessionKey{AccountServerId, MxToken}`，内层 `Protocol` 必须是**整数** 1002（字符串形态客户端不认，见 report/83）。
- `24000` 只需 `AcademyDB` 骨架 + `AcademyLocationDBs` 至少 1 条（`{LocationId:1, Rank:1, Exp:0}`）；但做完要和 `SessionKey` 问题一起验，单做它未必过得去。
- `1017` 分两步：先回「30 个业务字段名齐全（25 个具名兄弟字段 + 5 个散字段）、全部空列表/空对象」的骨架（这一步就能让客户端不再因缺字段崩溃），再逐个子回包填真数据（第二批）。
- 本批产物应是「客户端能走到大厅第一帧，哪怕所有列表都是空的」。

### 第 2 批 · 进大厅 —— 大厅渲染出第一帧所需

协议数 **7**，工作量 **15.5 人日**。

| 协议号 | 名称 | 类别 | 响应字节 | 依赖数据表 | 工作量 | 人日 | 已有实现 |
|---|---|---|---|---|---|---|---|
| 3 | NetworkTime_Sync | B | 620 | — | 小 | 0.5 | 完全没有 |
| 1005 | Account_GetTutorial | B | 640 | TutorialDBSchema(33) | 小 | 0.5 | 通用层可生成 |
| 4000 | Item_List | B | 16088 | ItemDBSchema(1803) | 中 | 2.0 | 通用层可生成 |
| 8000 | Mission_List | B | 268396 | MissionDBSchema(3444)、EventContentMissionDBSchema(2384) | 大 | 5.0 | 通用层可生成 |
| 8006 | Mission_GuideMissionSeasonList | B | 160216 | GuideMissionDBSchema(923)、GuideMissionSeasonDBSchema(20)、GuideMissionOpenStageConditionDBSchema(9) | 大 | 5.0 | 完全没有 |
| 26000 | ContentSave_Get | B | 640 | — | 小 | 0.5 | 通用层可生成 |
| 90004 | Management_Data | B | 14124 | 未找到（公告/活动/banner 全在官方 GM 后台，ExcelDB 无表） | 中 | 2.0 | 手写实现 |

- `1017` 的 30 个子回包逐个填真数据，顺序建议按字节数从大到小（`ShopGachaRecruitList` 66.8KB → … → `ItemListResponse` 4B）。
- `4000` / `8000` / `8006` 是独立三条大数据量协议，`8000`(268KB) 与 `8006`(160KB) 允许先回空数组降级。
- `90004` 需要自建一份运营配置（公告/banner/活动）；先全回空数组也能过，但大厅顶部会空。

### 第 3 批 · 能操作主界面 —— 大厅轮询 + 各面板可点开

协议数 **12**，工作量 **9.0 人日**。

| 协议号 | 名称 | 类别 | 响应字节 | 依赖数据表 | 工作量 | 人日 | 已有实现 |
|---|---|---|---|---|---|---|---|
| 7000 | Mail_List | C | 1600 | 未找到（ExcelDB 无 Mail 表） | 中 | 2.0 | 通用层可生成 |
| 7001 | Mail_Check | E | 556 | 未找到 Mail 表（ExcelDB 无任何 Mail* 表） | 小 | 0.5 | 通用层可生成 |
| 7003 | Mail_ListSemiPermanent | C | 556 | 未找到（ExcelDB 无 Mail 表） | 小 | 0.5 | 通用层可生成 |
| 8002 | Mission_MultipleReward | C | 8320 | MissionDBSchema(3444)、GuideMissionDBSchema(923) | 中 | 2.0 | 通用层可生成 |
| 15002 | OpenCondition_EventList | C | 600 | ConquestMapDBSchema(24)、ConquestTileDBSchema(152)、OpenConditionDBSchema(54) | 小 | 0.5 | 通用层可生成 |
| 16000 | Toast_List | E | 556 | ToastDBSchema(98) | 小 | 0.5 | 通用层可生成 |
| 25003 | Event_RewardIncrease | E | 792 | 未找到（ExcelDB 无 EventRewardIncrease* 表） | 小 | 0.5 | 通用层可生成 |
| 28019 | Clan_Check | C | 536 | — | 小 | 0.5 | 通用层可生成 |
| 29002 | Billing_PurchaseListByYostar | C | 1280 | ShopCashDBSchema、ProductDBSchema | 小 | 0.5 | 通用层可生成 |
| 30041 | EventContent_PermanentList | C | 2156 | 未找到（常驻活动清单不在 ExcelDB） | 小 | 0.5 | 通用层可生成 |
| 36001 | Notification_EventContentReddotCheck | E | 1088 | 未找到（无红点配置表） | 小 | 0.5 | 完全没有 |
| 43010 | Friend_Check | C | 536 | — | 小 | 0.5 | 通用层可生成 |

- 本批全部是「低字节 + 高调用频次」的轮询协议，主要成本在**把轮询做成幂等且不抛异常**，而不是字段。
- `28019` / `43010` 是 **0 业务字段**，直接回空信封。
- `8002` 引入横切能力 **ParcelResultDB（发奖）**，后面 20013/6020/6021/22004 全部复用 —— 值得在这里做扎实。

### 第 4 批 · 能打一场战斗 —— 主线策略跳过 / 竞技场一场

协议数 **8**，工作量 **26.5 人日**。

| 协议号 | 名称 | 类别 | 响应字节 | 依赖数据表 | 工作量 | 人日 | 已有实现 |
|---|---|---|---|---|---|---|---|
| 5000 | Echelon_List | D | 4120 | EchelonConstraintDBSchema(4) | 中 | 2.0 | 通用层可生成 |
| 5001 | Echelon_Save | D | 1004 | EchelonConstraintDBSchema(4) | 中 | 2.0 | 通用层可生成 |
| 6000 | Campaign_List | D | 44672 | CampaignChapterDBSchema(29)、CampaignStageDBSchema(407)、CampaignStageRewardDBSchema(3004)、CampaignChapterRewardDBSchema(60) | 大 | 5.0 | 通用层可生成 |
| 6020 | Campaign_EnterMainStageStrategySkip | D | 2072 | CampaignStageDBSchema(407)、CampaignStageRewardDBSchema(3004)、CurrencyDBSchema(29) | 中 | 2.0 | 通用层可生成 |
| 6021 | Campaign_MainStageStrategySkipResult | D | 10284 | CampaignStageDBSchema(407)、CampaignStageRewardDBSchema(3004)、MissionDBSchema(3444)、CharacterLevelDBSchema(90) | 大 | 5.0 | 通用层可生成 |
| 22000 | Arena_EnterLobby | D | 9068 | ArenaSeasonDBSchema(9)、ArenaMapDBSchema(60)、ArenaNPCDBSchema(13)、ArenaRewardDBSchema(108)、ArenaLevelSectionDBSchema(52) | 大 | 5.0 | 通用层可生成 |
| 22004 | Arena_EnterBattle | D | 67180 | ArenaSeasonDBSchema(9)、ArenaMapDBSchema(60)、ArenaRewardDBSchema(108)、EchelonConstraintDBSchema(4) | 大 | 5.0 | 通用层可生成 |
| 22016 | Arena_SyncEchelonSettingTime | D | 640 | — | 小 | 0.5 | 通用层可生成 |

- `6020` 是抓包里唯一一条「无战斗直接通关主线」的协议，**建议把它当成第一个战斗里程碑**，不碰战斗服就能证明主线走得通。
- `6021` 要读请求里的 32KB `Summary` 才能结算；单机私服可先「信任 + 结算」，联网再补校验。
- `22004` 是整张表最贵的一条：`BattleSetting` 18 字段 + `BattleSummary` + 三套奖励。官方 `IsServerRunBattle=true`（服务端跑战斗）；若能把该字段改成 false 让客户端自算，成本会掉一个数量级 —— 需实测客户端是否接受。
- `22000` 的对手列表在官方是真人；私服只能用 `ArenaNPCDBSchema(13)` + 随机生成补足 3 个。

### 第 5 批 · 商店 / 咖啡厅 / 公会 —— 功能面板

协议数 **6**，工作量 **13.5 人日**。

| 协议号 | 名称 | 类别 | 响应字节 | 依赖数据表 | 工作量 | 人日 | 已有实现 |
|---|---|---|---|---|---|---|---|
| 10002 | Shop_List | C | 1304 | ShopDBSchema(7908)、ShopInfoDBSchema(18)、ShopCashDBSchema | 中 | 2.0 | 通用层可生成 |
| 20001 | Cafe_Ack | C | 5016 | CafeInfoDBSchema(2)、CafeRankDBSchema(20)、CafeProductionDBSchema(30)、FurnitureDBSchema(876) | 中 | 2.0 | 通用层可生成 |
| 20013 | Cafe_ReceiveCurrency | C | 11136 | CafeProductionDBSchema(30)、CafeRankDBSchema(20)、CurrencyDBSchema(29) | 中 | 2.0 | 通用层可生成 |
| 28000 | Clan_Lobby | C | 35864 | ClanChattingEmojiDBSchema(176)、ClanRewardDBSchema(1)  ← 公会本体无静态表 | 大 | 5.0 | 通用层可生成 |
| 35003 | MiniGame_MissionList | C | 4480 | MiniGameMissionDBSchema(402) | 小 | 0.5 | 通用层可生成 |
| 90009 | Clan_Chat_Records | C | 30316 | 未找到（聊天记录是运行时数据） | 中 | 2.0 | 通用层可生成 |

- `20001` / `20013` 的初始家具已有权威答案（`initial_state_rules` q9：11 件含坐标/朝向），直接照抄。
- `10002` 需要把 `ShopDBSchema(7908)` 按 `CategoryType` 分组；`ShopInfoDBSchema(18)` 给 18 个分类的元信息。
- `28000` / `90009` 依赖公会系统这个「多用户子系统」本身；在公会功能上线前，新号回 `AccountClanDB=null` + 空成员表即可。

### 第 6 批 · 可选 —— 纯奖励与装饰，缺了不影响任何流程

协议数 **2**，工作量 **1.0 人日**。

| 协议号 | 名称 | 类别 | 响应字节 | 依赖数据表 | 工作量 | 人日 | 已有实现 |
|---|---|---|---|---|---|---|---|
| 22008 | Arena_CumulativeTimeReward | E | 3072 | ArenaRewardDBSchema(108) | 小 | 0.5 | 通用层可生成 |
| 22009 | Arena_DailyReward | E | 3224 | 未找到（无 ArenaDailyReward 表；奖励内容自建） | 小 | 0.5 | 通用层可生成 |

- `22008` / `22009` 都是「读档 → 发奖」，可共用第 3 批的 ParcelResultDB。
- 不做也完全不影响任何流程，放到最后。

---

## 4. `1017` 拆解：30 个子回包

请求 `SyncProtocols` 点名 **25 个协议号**（`20000, 1003, 2000, 3000, 5000, 12000, 6000, 22001, 17018, 21000, 28001, 33000, 19000, 10006, 39006, 44000, 29002, 30041, 45000, 46000, 46001, 47000, 49000, 27002, 49004`）；回包是 **25 个具名兄弟字段**（与 25 个点名协议号一一对应，不是 `Responses` 数组）+ 5 个散字段，业务字段合计 30 项（加 5 个信封字段 = 35 个 key）。

> ⚠️ 所有子回包内部的 `Protocol` 字段都是 **0**，不是各自协议号。

> ⚠️ `5000` / `6000` / `29002` / `30041` 这 4 个 DTO **同时**以独立 RPC 出现在 109 条里 —— 同一个构造器两处复用，别写两遍。

| 字段 | 触发协议号 | 序列化字节 | 内容 | 数据来源 | 工作量 |
|---|---|---|---|---|---|
| ShopGachaRecruitListResponse | 10006 | 66828 | ShopRecruits 529 + ShopFreeRecruitHistoryDBs 0 | exceldb_static（+ ShopFreeRecruitHistoryDBs 属 player_progress） | 中 |
| CampaignListResponse | 6000 | 30410 | CampaignChapterClearRewardHistoryDBs 12 + StageHistoryDBs 90 + CurrentScenarioId | player_progress | 大 |
| ScenarioListResponse | 19000 | 22858 | ScenarioHistoryDBs 191 + ScenarioGroupHistoryDBs 21 + ScenarioCollectionDBs 0 | player_progress | 中 |
| CharacterListResponse | 2000 | 15595 | CharacterDBs 46 + TSSCharacterDBs 0 + WeaponDBs 0 | player_progress + initial_state | 中 |
| CafeGetInfoResponse | 20000 | 9799 | CafeDB null + CafeDBs 2 + FurnitureDBs 27 | initial_state + player_progress | 中 |
| EquipmentItemListResponse | 3000 | 9506 | EquipmentDBs 84 | player_progress | 小 |
| EchelonListResponse | 5000 | 2638 | EchelonDBs 8 | initial_state + player_progress | 中 |
| EventContentPermanentListResponse | 30041 | 1237 | PermanentDBs 22 | official_config | 小 |
| AttachmentEmblemListResponse | 46001 | 1098 | EmblemDBs 14 | initial_state + player_progress | 小 |
| AccountCurrencySyncResponse | 1003 | 1096 | AccountCurrencyDB{AccountLevel, AcademyLocationRankSum, CurrencyDict 29 键, UpdateTimeDict} + ExpiredCurrency 0 | initial_state + player_progress | 小 |
| ClanLoginResponse | 28001 | 936 | AccountClanDB + AccountClanMemberDB + ClanAssistSlotDBs 0 | player_progress | 小 |
| StickerListResponse | 47000 | 803 | StickerBookDB{3 字段} | player_progress | 小 |
| BillingPurchaseListByYostarResponse | 29002 | 613 | CountList 4 + OrderList 0 + MonthlyProductList 0 | player_progress | 小 |
| ArenaLoginResponse | 22001 | 418 | ArenaPlayerInfoDB 9 字段 | official_config + player_progress | 小 |
| MomoTalkOutLineResponse | 33000 | 327 | MomoTalkOutLineDBs 1 + FavorScheduleRecords 1 | player_progress | 小 |
| ContentSweepMultiSweepPresetListResponse | 27002 | 283 | MultiSweepPresetDBs 1 | player_progress | 小 |
| EliminateRaidLoginResponse | 45000 | 269 | SeasonType 2 + CanReceiveRankingReward + ReceiveLimitedRewardIds 0 + SweepPointByRaidUniqueId {} | official_config | 小 |
| MemoryLobbyListResponse | 12000 | 227 | MemoryLobbyDBs 1（Type 8 / UniqueId 13010） | initial_state | 小 |
| RaidLoginResponse | 17018 | 210 | SeasonType 1 + CanReceiveRankingReward false + LastSettledRanking/Tier 0 | official_config | 小 |
| AttachmentGetResponse | 46000 | 187 | AccountAttachmentDB{EmblemUniqueId 1} | initial_state | 小 |
| CraftInfoListResponse | 21000 | 179 | CraftInfos 0 + ShiftingCraftInfos 0 + PresetSlotDBs 0 | player_progress | 小 |
| MultiFloorRaidLoginResponse | 49004 | 146 | LastClearedDifficulty 0 | player_progress | 小 |
| MultiFloorRaidSyncResponse | 49000 | 145 | MultiFloorRaidDBs null | player_progress | 小 |
| TimeAttackDungeonLoginResponse | 39006 | 142 | PreviousRoomDB null | player_progress | 小 |
| CharacterGearListResponse | 44000 | 133 | GearDBs 0 | player_progress | 小 |
| ItemListResponse | （无条件） | 4 | null（背包不走 loginsync，走独立 4000） | — | — |
| FriendCount | （无条件） | 1 | 0 | player_progress | — |
| FriendCode | （无条件） | 9 | 'slmv4wc'（7 字符，账号级） | player_progress | — |
| PickupFirstGetHistoryDBs | （无条件） | 63 | [{ShopRecruitId 5004170, LogDate}] | player_progress | — |
| AccountLevelRewardIds | （无条件） | 3 | [1]（= AccountLevelRewardDBSchema 里 Level ≤ 账号等级 的 Id；官方 Lv32 → 只有 Id=1/Lv30；新号 Lv1 → []） | player_progress | — |

> 上表「序列化字节」是把该子对象单独 `json.dumps` 后的长度，30 项合计 166163B（整包 `resp_bytes` 246808B，其余是信封与转义开销）。

---

## 5. 每条协议「需要什么数据」

数据来源只用 5 类：

- `initial_state` — 初始值规则（Excel.zip 的 Default*/Const* 表）
- `exceldb_static` — ExcelDB.db 静态表
- `player_progress` — 玩家进度存档（服务端自建）
- `official_config` — 官方运营配置（公告/活动/banner/赛季）
- `echo` — 纯回显请求参数 / 常量

### 3 · NetworkTime_Sync

- **类别 / 批次**：B（大厅必要）/ 第 2 批（进大厅）
- **官方响应**：620 B；请求 906–906 B；调用 1 次（观测值 620）
- **数据来源**：`echo`
- **依赖表**：—
- **需要什么数据**：ReceiveTick / EchoSendTick 就是对请求里的时间戳回显；ServerTimeTicks 由服务器时钟给。620B 里只有这 2 个业务字段。
- **为什么归这一档**：启动链第 5 条。时钟同步失败会让所有倒计时（体力恢复 / 每日刷新 / 活动剩余）异常。
- **已有实现**：完全没有（`dto_schema_full_v2.json（709 类型）里没有 NetworkTimeSyncResponse → protocol_router 回 Error 信封`）
- **备注**：全表最简单的一条。

### 1002 · Account_Auth

- **类别 / 批次**：A（门槛）/ 第 1 批（连通）
- **官方响应**：5056 B；请求 1138–1138 B；调用 1 次（观测值 5056）
- **数据来源**：`player_progress` + `initial_state` + `official_config`
- **依赖表**：`CurrencyDBSchema(29)`、`AttendanceDBSchema(31)`、`AttendanceRewardDBSchema(334)`
- **需要什么数据**：AccountDB 23 字段 ← 账号存档（ServerId/RoleId/Nickname/Level=32/Exp/State/LobbyMode/RepresentCharacterServerId/Location）；AttendanceHistoryDBs 2 条 ← 打卡进度（新号只有 AttendanceBookUniqueId=28 与 1 两条空记录）；AttendanceBookRewards/DailyRecordDBs/IssueAlertInfos 空；FunctionClose 8 开关、AccountLimitedFlashSaleDBs 15 条(ShopExcelId+SaleFrom/SaleTo)、NewlyAddedShopCashIds ← 官方运维/活动配置；OptionDB 3 字段、AccountRestrictionsDB 3 字段 ← 账号设置；MonthlyProduct*/RepurchasableMonthlyProductCountDBs ← 商城订阅（新号 null/空）；ServerTimeTicks ← 服务器时钟。
- **为什么归这一档**：会话根。不下发 SessionKey，后面每一条都进不去。调用序第 1 条（04:30:54.662）。
- **已有实现**：手写实现（`_bridge:1033-1051 path B + cn_inner27.build(a_proto_int) 27 字段；account_service.py:build_account_db_for() 供数据`）
- **备注**：线上版（2026-11-14 bridge）只回 2648B，官方 5056B。差异主要在 Attendance/FlashSale/Product 这几组。

### 1005 · Account_GetTutorial

- **类别 / 批次**：B（大厅必要）/ 第 2 批（进大厅）
- **官方响应**：640 B；请求 926–926 B；调用 1 次（观测值 640）
- **数据来源**：`player_progress` + `exceldb_static`
- **依赖表**：`TutorialDBSchema(33)`
- **需要什么数据**：TutorialIds 21 条 ← 账号教程进度（新号 = []）。TutorialDBSchema(33) 只是「教程定义表」（27 个基础 ID 1..27 + 6 个活动 ID），**不含进度**。
- **为什么归这一档**：启动链第 8 条。教程进度决定新手引导是否重放；回错会让客户端卡在教学里。
- **已有实现**：通用层可生成（`protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空`）
- **备注**：官方号有 21 条是因为玩过；新号回空数组即可（640B）。

### 1017 · Account_LoginSync

- **类别 / 批次**：A（门槛）/ 第 1 批（连通）
- **官方响应**：246808 B；请求 1182–1182 B；调用 1 次（观测值 246808）
- **数据来源**：`player_progress` + `exceldb_static` + `initial_state` + `official_config`
- **依赖表**：`见 §4 的 30 个子回包各自的表`
- **需要什么数据**：请求 `SyncProtocols` 点名 25 个协议号（20000,1003,2000,3000,5000,12000,6000,22001,17018,21000,28001,33000,19000,10006,39006,44000,29002,30041,45000,46000,46001,47000,49000,27002,49004），回包是 **25 个具名兄弟字段**（与 SyncProtocols 一一对应，不是 Responses 数组）+ 5 个散字段（`ItemListResponse`=null / `FriendCount` / `FriendCode` / `PickupFirstGetHistoryDBs` / `AccountLevelRewardIds`），业务字段合计 30 个（加 5 个信封字段 = 35 个 key）。逐字段见 §4。
- **为什么归这一档**：启动链第 3 条，一次性下发全部存档（246808B，30 个子回包）。不回/回空 → 客户端进大厅后没有任何角色/道具/编队数据。
- **已有实现**：手写实现（`_bridge:696-702 _generic_protocol_response(num in (1019,1017))，492B，4 个空集合 + Responses:[]`）
- **备注**：⚠️ 形态坑：所有子回包内部的 `Protocol` 都是 0（不是各自的协议号）。⚠️ 版本坑：report/67 记的是 1019，本次官方抓包（2026-11-16）明确是 1017（请求 json Protocol=1017、Hash>>32=1017、响应 inner.Protocol=1017）——以本次为准，服务端建议 1017/1019 双别名都收。

### 4000 · Item_List

- **类别 / 批次**：B（大厅必要）/ 第 2 批（进大厅）
- **官方响应**：16088 B；请求 926–926 B；调用 1 次（观测值 16088）
- **数据来源**：`player_progress` + `exceldb_static` + `initial_state`
- **依赖表**：`ItemDBSchema(1803)`
- **需要什么数据**：ItemDBs 134 条{Type, ServerId, UniqueId, StackCount, IsNew} + ExpiryItemDBs ← 玩家背包存档；静态名/图标查 ItemDBSchema(1803)。新号只有 DefaultParcelExcel 里 ParcelType=4 的 1 条（ItemId=2 加速券 ×5）。
- **为什么归这一档**：启动链第 4 条。背包数据，进大厅就要。
- **已有实现**：通用层可生成（`protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空`）
- **备注**：官方 134 条是该号积累的；新号 1 条。响应大小会从 16088B 掉到几百字节。

### 5000 · Echelon_List

- **类别 / 批次**：D（战斗相关）/ 第 4 批（能打一场战斗）
- **官方响应**：4120 B；请求 922–926 B；调用 4 次（观测值 4120）
- **数据来源**：`player_progress` + `initial_state` + `exceldb_static`
- **依赖表**：`EchelonConstraintDBSchema(4)`
- **需要什么数据**：EchelonDBs 8 条{EchelonType, EchelonNumber, ExtensionType, LeaderServerId, MainSlotServerIds[4], SupportSlotServerIds[2], TSSInteractionServerId, UsingFlag, SkillCardMulliganCharacterIds[3], CombatStyleIndex[6]} ← 账号编队存档；新号只有 1 条（DefaultEchelonExcel：type1/number1，主槽 优香/铃美/莲见 + 空，支援槽 千夏）；约束查 EchelonConstraintDBSchema(4)。
- **为什么归这一档**：编队列表——打任何战斗之前都要（109 条里 4 次调用，竞技场前连调 3 次）。
- **已有实现**：通用层可生成（`protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空`）
- **备注**：4120B。官方 8 条是该号解锁各玩法后的累积。

### 5001 · Echelon_Save

- **类别 / 批次**：D（战斗相关）/ 第 4 批（能打一场战斗）
- **官方响应**：1004 B；请求 1394–1418 B；调用 2 次（观测值 984, 1004）
- **数据来源**：`echo` + `player_progress`
- **依赖表**：`EchelonConstraintDBSchema(4)`
- **需要什么数据**：EchelonDB ← 校验请求里的 EchelonDB（槽位数/车型合法）后原样回显 + 写存档。请求带 AssistUseInfos / IsPractice。
- **为什么归这一档**：编队保存（两种 EchelonType：1=主线，3=总力战/大决战）。
- **已有实现**：通用层可生成（`protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空`）
- **备注**：984B / 1004B。典型「回显 + 落库」。

### 6000 · Campaign_List

- **类别 / 批次**：D（战斗相关）/ 第 4 批（能打一场战斗）
- **官方响应**：44672 B；请求 926–926 B；调用 1 次（观测值 44672）
- **数据来源**：`player_progress` + `exceldb_static`
- **依赖表**：`CampaignChapterDBSchema(29)`、`CampaignStageDBSchema(407)`、`CampaignStageRewardDBSchema(3004)`、`CampaignChapterRewardDBSchema(60)`
- **需要什么数据**：CampaignChapterClearRewardHistoryDBs 12 条 + StageHistoryDBs 90 条{StageUniqueId, ChapterUniqueId, Star1/2/3Flag, TodayPlayCount, ClearTurnRecord, FirstClearRewardReceive, StarRewardReceive} + CurrentScenarioId=41200 ← 账号关卡进度；静态查 CampaignChapterDBSchema(29)/CampaignStageDBSchema(407)/CampaignStageRewardDBSchema(3004)。
- **为什么归这一档**：主线关卡列表——进主线之前必须先有它（也要和 1017 内嵌的同一份保持一致）。
- **已有实现**：通用层可生成（`protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空`）
- **备注**：44672B。⚠️ 同一条 DTO 也内嵌在 1017 里（CampaignListResponse），两处必须同源。

### 6020 · Campaign_EnterMainStageStrategySkip

- **类别 / 批次**：D（战斗相关）/ 第 4 批（能打一场战斗）
- **官方响应**：2072 B；请求 990–990 B；调用 1 次（观测值 2072）
- **数据来源**：`player_progress` + `exceldb_static`
- **依赖表**：`CampaignStageDBSchema(407)`、`CampaignStageRewardDBSchema(3004)`、`CurrencyDBSchema(29)`
- **需要什么数据**：ParcelResultDB{AccountCurrencyDB} ← 跳过结算只发货币；关卡查 CampaignStageDBSchema(407)，奖励查 CampaignStageRewardDBSchema(3004)。
- **为什么归这一档**：「策略跳过」= 无战斗直接通关主线（请求 StageUniqueId=1021103）。这是抓包里唯一一条真正的战斗相关主线调用。
- **已有实现**：通用层可生成（`protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空`）
- **备注**：2072B。比完整战斗轻得多，可以当「第一条能打通的主线」的里程碑。

### 6021 · Campaign_MainStageStrategySkipResult

- **类别 / 批次**：D（战斗相关）/ 第 4 批（能打一场战斗）
- **官方响应**：10284 B；请求 32572–32572 B；调用 1 次（观测值 10284）
- **数据来源**：`player_progress` + `exceldb_static`
- **依赖表**：`CampaignStageDBSchema(407)`、`CampaignStageRewardDBSchema(3004)`、`MissionDBSchema(3444)`、`CharacterLevelDBSchema(90)`
- **需要什么数据**：TacticRank + CampaignStageHistoryDB 12 字段 + MissionProgressDBs 31 条 + ParcelResultDB{AccountDB, AccountCurrencyDB, ItemDBs, DisplaySequence, BaseAccountExp, AdditionalAccountExp} + FirstClearReward/ThreeStarReward ← 读请求 Summary 判定胜负/评价，再结算首通+三星奖励 + 推任务进度 + 给账号经验。
- **为什么归这一档**：策略跳过结果上报（请求 32572B 的 Summary 是战斗过程）。这是唯一一条「客户端把战斗结果告诉服务端」的主线协议。
- **已有实现**：通用层可生成（`protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空`）
- **备注**：10284B。**必须校验请求**（否则可伪造通关），但单机私服可以先只做「信任 + 结算」。

### 7000 · Mail_List

- **类别 / 批次**：C（功能入口）/ 第 3 批（能操作主界面）
- **官方响应**：1600 B；请求 1074–1074 B；调用 1 次（观测值 1600）
- **数据来源**：`player_progress` + `initial_state` + `official_config`
- **依赖表**：`未找到（ExcelDB 无 Mail 表）`
- **需要什么数据**：MailDBs 2 条{ServerId, Type, Sender('UI_MAILBOX_POST_SENDER_ARONA' 之类的 localize key), Comment, SendDate, ExpireDate, ParcelInfos[{Key:{Type,Id},Amount}]} + Count ← 服务端自建邮件表。**ExcelDB 没有任何 Mail 表**；初始邮件只能来自 Excel.zip 的 DefaultMailExcel（1 行，字段未完全解出）。
- **为什么归这一档**：邮件面板入口。请求带 IsReadMail/PivotIndex/mailSortingRule/IsDescending/PivotTime（分页游标）。
- **已有实现**：通用层可生成（`protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空`）
- **备注**：官方 2 封里 1 封是签到奖励、1 封是运营补偿，都不是「新号必备」。新号可回空 MailDBs。

### 7001 · Mail_Check

- **类别 / 批次**：E（可选/装饰）/ 第 3 批（能操作主界面）
- **官方响应**：556 B；请求 926–926 B；调用 9 次（观测值 556）
- **数据来源**：`player_progress`
- **依赖表**：`未找到 Mail 表（ExcelDB 无任何 Mail* 表）`
- **需要什么数据**：Count=2/3 ← 未读邮件数的派生值。556B，只有 1 个业务字段。
- **为什么归这一档**：每 ~5s 轮询一次（109 条里 9 次）。只驱动大厅邮件红点。
- **已有实现**：通用层可生成（`protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空`）
- **备注**：最容易的一条之一。

### 7003 · Mail_ListSemiPermanent

- **类别 / 批次**：C（功能入口）/ 第 3 批（能操作主界面）
- **官方响应**：556 B；请求 1074–1074 B；调用 1 次（观测值 556）
- **数据来源**：`echo`
- **依赖表**：`未找到（ExcelDB 无 Mail 表）`
- **需要什么数据**：本次抓包返回 556B = **只有信封，0 个业务字段**（该号没有半永久邮件）。新号可原样回空。
- **为什么归这一档**：半永久邮件面板（与 7000 同一套分页参数）。
- **已有实现**：通用层可生成（`protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空`）
- **备注**：可与 7000 共用同一个邮件子系统。

### 8000 · Mission_List

- **类别 / 批次**：B（大厅必要）/ 第 2 批（进大厅）
- **官方响应**：268396 B；请求 946–946 B；调用 3 次（观测值 8216, 8768, 268396）
- **数据来源**：`player_progress` + `exceldb_static`
- **依赖表**：`MissionDBSchema(3444)`、`EventContentMissionDBSchema(2384)`
- **需要什么数据**：ProgressDBs 1240 条{AccountServerId, MissionUniqueId, Category, StartDate, ProgressParameters} + MissionHistoryUniqueIds 372 + ClearedOriginalMissionIds 372 + DailySuddenMissionInfo ← 账号任务进度；静态定义查 MissionDBSchema(3444) / EventContentMissionDBSchema(2384)。DailySuddenMissionInfo 的 `Id=1606` 在 `MissionDBSchema` 里直接能查到（静态）；三个池按 `EventContentId` 独立（null / 849 / 10838）。
- **为什么归这一档**：启动链第 9 条（连发 3 次：EventContentId=null / 849 / 10838）。任务面板是大厅主界面。
- **已有实现**：通用层可生成（`protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空`）
- **备注**：268396B，全表最大的响应。新号只需要「当前应触发的任务」集合，尚未找到确定规则（见 §7）。

### 8002 · Mission_MultipleReward

- **类别 / 批次**：C（功能入口）/ 第 3 批（能操作主界面）
- **官方响应**：8320 B；请求 1010–1010 B；调用 1 次（观测值 8320）
- **数据来源**：`player_progress` + `exceldb_static`
- **依赖表**：`MissionDBSchema(3444)`、`GuideMissionDBSchema(923)`
- **需要什么数据**：MissionProgressDBs 8 条 + ParcelResultDB{AccountDB, AccountCurrencyDB, EquipmentDBs, ItemDBs, DisplaySequence} + AddedHistoryDBs 11 条 ← 任务进度 + 奖励发放；奖励内容查 MissionDBSchema / GuideMissionDBSchema。
- **为什么归这一档**：一键领取任务奖励（请求 MissionCategory=4 / GuideMissionSeasonId=4）。
- **已有实现**：通用层可生成（`protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空`）
- **备注**：需要实现「发奖」这个横切能力（ParcelResultDB），后面 20013/6020/6021/22004 全都要用。

### 8006 · Mission_GuideMissionSeasonList

- **类别 / 批次**：B（大厅必要）/ 第 2 批（进大厅）
- **官方响应**：160216 B；请求 926–926 B；调用 1 次（观测值 160216）
- **数据来源**：`player_progress` + `exceldb_static`
- **依赖表**：`GuideMissionDBSchema(923)`、`GuideMissionSeasonDBSchema(20)`、`GuideMissionOpenStageConditionDBSchema(9)`
- **需要什么数据**：MissionProgressDBs 733 条 + GuideMissionSeasonDBs 17 条{SeasonId, LoginCount, StartDate, LoginDate, IsFinalMissionComplete} ← 账号引导任务进度；静态查 GuideMissionDBSchema(923) / GuideMissionSeasonDBSchema(20) / GuideMissionOpenStageConditionDBSchema(9)。
- **为什么归这一档**：启动链第 10 条。引导任务赛季是新手主流程的主线。
- **已有实现**：完全没有（`同上，没有 MissionGuideMissionSeasonListResponse → router 回 Error 信封`）
- **备注**：160216B。可先回空数组降级（新手引导会跳过但不崩）。

### 10002 · Shop_List

- **类别 / 批次**：C（功能入口）/ 第 5 批（商店 / 咖啡厅 / 公会）
- **官方响应**：1304 B；请求 946–946 B；调用 1 次（观测值 1304）
- **数据来源**：`exceldb_static` + `player_progress`
- **依赖表**：`ShopDBSchema(7908)`、`ShopInfoDBSchema(18)`、`ShopCashDBSchema`
- **需要什么数据**：ShopInfos 1 组{EventContentId=0, Category=38, ShopGroupType=0, ManualRefreshCount, IsRefresh, NextAutoRefreshDate, LastAutoRefreshDate, ShopProductList 2 条{ShopExcelId 201/202, Price=0, PurchaseCountLimit=1, SoldOut}} + ShopEligmaHistoryDBs ← 请求 CategoryList + 账号购买次数；商品定义查 ShopDBSchema(7908)/ShopInfoDBSchema(18)。Category 38 = 教程扭蛋商店。
- **为什么归这一档**：商店面板入口（请求 CategoryList=[38]）。
- **已有实现**：通用层可生成（`protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空`）
- **备注**：1304B。完整商店需要把 7908 行 ShopDBSchema 按 CategoryType 分组。

### 15002 · OpenCondition_EventList

- **类别 / 批次**：C（功能入口）/ 第 3 批（能操作主界面）
- **官方响应**：600 B；请求 1034–1034 B；调用 1 次（观测值 600）
- **数据来源**：`official_config` + `player_progress` + `echo`
- **依赖表**：`ConquestMapDBSchema(24)`、`ConquestTileDBSchema(152)`、`OpenConditionDBSchema(54)`
- **需要什么数据**：ConquestTiles 1 个 key（'50822' → []）← 请求里 ConquestEventIds=[50822] / WorldRaidSeasonAndGroupIds={821:[821602],823:[823100]} 的回显 + 账号进度。静态查 ConquestEventDBSchema(5)/ConquestTileDBSchema(152)/OpenConditionDBSchema(54)。
- **为什么归这一档**：活动解锁判定（启动链第 16 条）。不回会让活动入口消失或报错。
- **已有实现**：通用层可生成（`protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空`）
- **备注**：600B。请求参数驱动，可按请求 key 回空数组。

### 16000 · Toast_List

- **类别 / 批次**：E（可选/装饰）/ 第 3 批（能操作主界面）
- **官方响应**：556 B；请求 926–926 B；调用 1 次（观测值 556）
- **数据来源**：`player_progress`
- **依赖表**：`ToastDBSchema(98)`
- **需要什么数据**：ToastDBs ← 账号待展示 toast 队列。新号回 null（556B）即可。ToastDBSchema(98) 是 toast 文案定义表，不是队列。
- **为什么归这一档**：一次性提示条队列。官方本次 ToastDBs=null。
- **已有实现**：通用层可生成（`protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空`）
- **备注**：零逻辑。

### 20001 · Cafe_Ack

- **类别 / 批次**：C（功能入口）/ 第 5 批（商店 / 咖啡厅 / 公会）
- **官方响应**：5016 B；请求 946–946 B；调用 1 次（观测值 5016）
- **数据来源**：`player_progress` + `exceldb_static` + `initial_state`
- **依赖表**：`CafeInfoDBSchema(2)`、`CafeRankDBSchema(20)`、`CafeProductionDBSchema(30)`、`FurnitureDBSchema(876)`
- **需要什么数据**：CafeDB 11 字段{CafeDBId, CafeId, CafeRank, LastSummonDate, CafeVisitCharacterDBs, FurnitureDBs, ProductionAppliedTime, ProductionDB} ← 账号咖啡厅存档；静态查 CafeInfoDBSchema(2 个 Cafe)/CafeRankDBSchema(20 档)/CafeProductionDBSchema(30)；**初始 11 件家具 ← DefaultFurnitureExcel**（initial_state_rules q9），新号 CafeRank=1 / LastSummonDate=0001-01-01。
- **为什么归这一档**：咖啡厅面板（请求 CafeDBId=AccountServerId*10+CafeId）。
- **已有实现**：通用层可生成（`protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空`）
- **备注**：5016B。家具初始值已有权威答案（q9 的 11 条含坐标/朝向）。

### 20013 · Cafe_ReceiveCurrency

- **类别 / 批次**：C（功能入口）/ 第 5 批（商店 / 咖啡厅 / 公会）
- **官方响应**：11136 B；请求 990–990 B；调用 1 次（观测值 11136）
- **数据来源**：`player_progress` + `exceldb_static`
- **依赖表**：`CafeProductionDBSchema(30)`、`CafeRankDBSchema(20)`、`CurrencyDBSchema(29)`
- **需要什么数据**：CafeDBs 2 条（全量）+ ParcelResultDB ← 咖啡厅存档 + 产出结算；产出速率查 CafeProductionDBSchema(30)，按 CafeRank 取档。
- **为什么归这一档**：咖啡厅收币（请求 CafeDBId=0 表示领所有咖啡厅）。
- **已有实现**：通用层可生成（`protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空`）
- **备注**：11136B。需要「按时间差算产出」这个逻辑。

### 22000 · Arena_EnterLobby

- **类别 / 批次**：D（战斗相关）/ 第 4 批（能打一场战斗）
- **官方响应**：9068 B；请求 926–926 B；调用 2 次（观测值 9068）
- **数据来源**：`official_config` + `player_progress` + `exceldb_static`
- **依赖表**：`ArenaSeasonDBSchema(9)`、`ArenaMapDBSchema(60)`、`ArenaNPCDBSchema(13)`、`ArenaRewardDBSchema(108)`、`ArenaLevelSectionDBSchema(52)`
- **需要什么数据**：ArenaPlayerInfoDB 9 字段{CurrentSeasonId, PlayerGroupId, CurrentRank, SeasonRecord, AllTimeRecord, CumulativeTimeReward, TimeRewardLastUpdateTime, BattleEnterActiveTime, DailyRewardActiveTime} + OpponentUserDBs 3 个（每个含完整 TeamSettingDB：5 人 × {UniqueId,StarGrade,Level,技能等级,Position}）+ MapId=1001 + AutoRefreshTime ← 赛季配置 + 账号排名 + **对手列表**。对手在官方是真人，私服只能造 NPC/机器人（ArenaNPCDBSchema 只有 13 行，不够就用随机生成）。
- **为什么归这一档**：竞技场大厅（109 条里 2 次）。不进去就打不了竞技场。
- **已有实现**：通用层可生成（`protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空`）
- **备注**：9068B。对手队伍数据是这条的主要重量。

### 22004 · Arena_EnterBattle

- **类别 / 批次**：D（战斗相关）/ 第 4 批（能打一场战斗）
- **官方响应**：67180 B；请求 1010–1010 B；调用 1 次（观测值 67180）
- **数据来源**：`player_progress` + `exceldb_static` + `echo`
- **依赖表**：`ArenaSeasonDBSchema(9)`、`ArenaMapDBSchema(60)`、`ArenaRewardDBSchema(108)`、`EchelonConstraintDBSchema(4)`
- **需要什么数据**：ArenaBattleDB{Season, Group, BattleStartTime, BattleEndTime, Seed, AttackingUserDB, DefendingUserDB, BattleSummary} + BattleSetting 18 字段{BattleType=2097152, EchelonType, RandomSeed, Buid='<account>_<ts>', BattleDurationInFrame=5400, GroundUniqueId=530300011, StageId, EnvironmentType, IsBoss, IsAutoUseSkill, LeftTeam, RightTeam, PlayerActions, RaidSetting, StageIndex, EventSetting, TimeAttackSetting, ClanAssistUseInfo} + MissionProgressDBs 6 + AccountCurrencyDB + 三套奖励(ParcelResult) ← **需要战斗种子/战斗结算**。IsServerRunBattle=true 表示官方在服务端跑战斗。
- **为什么归这一档**：竞技场开战（请求 OpponentAccountServerId / OpponentIndex / OpponentRank）。**67180B，全表第 2 大**。
- **已有实现**：通用层可生成（`protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空`）
- **备注**：最难的一条。要么接一个开源 BA 战斗服，要么把 IsServerRunBattle 改成 false 让客户端自己算（需要验证客户端接不接受）。

### 22008 · Arena_CumulativeTimeReward

- **类别 / 批次**：E（可选/装饰）/ 第 6 批（可选）
- **官方响应**：3072 B；请求 926–926 B；调用 1 次（观测值 3072）
- **数据来源**：`player_progress` + `exceldb_static`
- **依赖表**：`ArenaRewardDBSchema(108)`
- **需要什么数据**：TimeRewardAmount=0 + TimeRewardLastUpdateTime + ParcelResult{AccountDB, AccountCurrencyDB, DisplaySequence} ← 竞技场挂机时长 + 奖励档位表。
- **为什么归这一档**：竞技场累计时间奖励（挂机奖励）。不给也没人缺。
- **已有实现**：通用层可生成（`protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空`）
- **备注**：3072B。首包回 0 即可。

### 22009 · Arena_DailyReward

- **类别 / 批次**：E（可选/装饰）/ 第 6 批（可选）
- **官方响应**：3224 B；请求 926–926 B；调用 1 次（观测值 3224）
- **数据来源**：`player_progress`
- **依赖表**：`未找到（无 ArenaDailyReward 表；奖励内容自建）`
- **需要什么数据**：DailyRewardActiveTime='2026-11-16T14:00:00' + ParcelResult ← 日奖励领取时间 + 档位表。
- **为什么归这一档**：竞技场每日奖励。
- **已有实现**：通用层可生成（`protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空`）
- **备注**：3224B。

### 22016 · Arena_SyncEchelonSettingTime

- **类别 / 批次**：D（战斗相关）/ 第 4 批（能打一场战斗）
- **官方响应**：640 B；请求 922–922 B；调用 1 次（观测值 640）
- **数据来源**：`player_progress`
- **依赖表**：—
- **需要什么数据**：EchelonSettingTime ← 账号存档里的编队设定时间。640B，1 个业务字段。
- **为什么归这一档**：竞技场防守编队设定时间（竞技场进战斗前调）。
- **已有实现**：通用层可生成（`protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空`）
- **备注**：零逻辑。

### 24000 · Academy_GetInfo

- **类别 / 批次**：A（门槛）/ 第 1 批（连通）
- **官方响应**：17560 B；请求 926–926 B；调用 2 次（观测值 17560）
- **数据来源**：`player_progress` + `exceldb_static` + `initial_state`
- **依赖表**：`AcademyLocationDBSchema(11)`、`AcademyLocationRankDBSchema(12)`、`AcademyZoneDBSchema(95)`、`AcademyFavorScheduleDBSchema(1053)`、`AcademyTicketDBSchema(5)`、`AcademyRewardDBSchema(564)`
- **需要什么数据**：AcademyDB{AccountId, LastUpdate, ZoneVisitCharacterDBs(按 zone 分组的驻留角色 [{UniqueId,ServerId,LastInteractTime}]), ZoneScheduleGroupRecords} ← 账号学院存档；AcademyLocationDBs 9 条{LocationId, Rank, Exp} ← 账号进度 + AcademyLocationDBSchema(11 个地点)/AcademyLocationRankDBSchema(12 档升级曲线)；初始 Rank=1 / Exp=0（initial_state_rules q8）。
- **为什么归这一档**：启动链第 2 条（04:30:54.980），排在 loginsync 之前。report/67 §1.A 实证：回 192B 假包 → 客户端 8 秒后弹「同步账号信息时发生错误。将返回标题画面」并回标题，之后零请求。
- **已有实现**：手写实现（`report/_tmp/sandbox292/account_auth_probe.py:408-577 _academy_24000_build（模板 academy_24000_official.json：71 个 ZoneVisitCharacterDBs 键 + 9 条 AcademyLocationDBs）`）
- **备注**：⚠️ 卡点争议：report/83 §5「06:05 Academy_GetInfo 真结构上线」记录客户端表现与 192B 假包完全相同 ⇒ 24000 不是唯一卡点（SessionKey 未被客户端采纳是另一条未解）。分类仍按 A（启动链第 2 条），但落地时应与 SessionKey 问题一起验。

### 25003 · Event_RewardIncrease

- **类别 / 批次**：E（可选/装饰）/ 第 3 批（能操作主界面）
- **官方响应**：792 B；请求 926–926 B；调用 21 次（观测值 792）
- **数据来源**：`official_config`
- **依赖表**：`未找到（ExcelDB 无 EventRewardIncrease* 表）`
- **需要什么数据**：EventRewardIncreaseDBs 1 条{EventTargetType=4, RewardRealType=100473, Multiplier:{rawValue:20000}, BeginDate='2026-11-12T04:00:00', EndDate='2026-11-19T03:59:59'} ← **纯官方活动配置**，无静态表。回空数组即可（客户端只是没有加成横幅）。
- **为什么归这一档**：109 条里出现 21 次（最高频），每轮轮询都调。只影响掉落倍率显示。
- **已有实现**：通用层可生成（`protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空`）
- **备注**：792B。回 [] 是安全降级。

### 26000 · ContentSave_Get

- **类别 / 批次**：B（大厅必要）/ 第 2 批（进大厅）
- **官方响应**：640 B；请求 926–926 B；调用 1 次（观测值 640）
- **数据来源**：`player_progress`
- **依赖表**：—
- **需要什么数据**：HasValidData=false / ContentSaveDB=null / EventContentChangeDB=null ← 账号存档。新号三件套就是 false/null/null，直接回固定值即可（640B）。
- **为什么归这一档**：启动链第 6 条。断线续战存档入口，回 null 客户端就认为没有存档（正常）。
- **已有实现**：通用层可生成（`protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空`）
- **备注**：新号可零逻辑回常量。

### 28000 · Clan_Lobby

- **类别 / 批次**：C（功能入口）/ 第 5 批（商店 / 咖啡厅 / 公会）
- **官方响应**：35864 B；请求 926–926 B；调用 1 次（观测值 35864）
- **数据来源**：`player_progress`
- **依赖表**：`ClanChattingEmojiDBSchema(176)`、`ClanRewardDBSchema(1)  ← 公会本体无静态表`
- **需要什么数据**：AccountClanDB 10 字段{ClanDBId, ClanName, ClanPresidentNickName, ClanNotice, ClanMemberCount=50, ...} + AccountClanMemberDB 14 字段 + ClanMemberDBs **50 个成员** ← **运行时多用户数据**。ExcelDB 只有 ClanChattingEmojiDBSchema(176)/ClanRewardDBSchema(1)，公会/成员表都不存在。
- **为什么归这一档**：公会大厅（要真的进一个公会才有数据）。
- **已有实现**：通用层可生成（`protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空`）
- **备注**：35864B。开公会系统之前，新号回 AccountClanDB=null + ClanMemberDBs=[]（未入会）即可。

### 28019 · Clan_Check

- **类别 / 批次**：C（功能入口）/ 第 3 批（能操作主界面）
- **官方响应**：536 B；请求 922–926 B；调用 8 次（观测值 536）
- **数据来源**：`echo`
- **依赖表**：—
- **需要什么数据**：536B = **只有 5 个信封字段，0 个业务字段**。成功即空体。
- **为什么归这一档**：公会入口解锁检查（8 次轮询）。
- **已有实现**：通用层可生成（`protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空`）
- **备注**：全表最简单的一条：直接回空信封。

### 29002 · Billing_PurchaseListByYostar

- **类别 / 批次**：C（功能入口）/ 第 3 批（能操作主界面）
- **官方响应**：1280 B；请求 922–926 B；调用 3 次（观测值 1280）
- **数据来源**：`player_progress` + `official_config`
- **依赖表**：`ShopCashDBSchema`、`ProductDBSchema`
- **需要什么数据**：CountList 4 条{ShopCashId, PurchaseCount, ResetDate, PurchaseDate} + OrderList(空) + MonthlyProductList(空) ← 账号购买计数。新号应为空列表（那 4 条是该号买过的痕迹）；ShopCashId 空间来自 ShopCashDBSchema(656)，已实测 900000/1597/15039 命中。
- **为什么归这一档**：商店/充值页的次数限制（3 次轮询）。
- **已有实现**：通用层可生成（`protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空`）
- **备注**：1280B。可先回空列表降级。

### 30041 · EventContent_PermanentList

- **类别 / 批次**：C（功能入口）/ 第 3 批（能操作主界面）
- **官方响应**：2156 B；请求 926–926 B；调用 1 次（观测值 2156）
- **数据来源**：`official_config` + `player_progress`
- **依赖表**：`未找到（常驻活动清单不在 ExcelDB）`
- **需要什么数据**：PermanentDBs 22 条{EventContentId, IsStageAllClear} ← 官方常驻活动 id 清单（900801..900827 段，缺 807/811/821..824）+ 账号通关进度。
- **为什么归这一档**：常驻活动列表（启动链第 58 条前）。活动页需要它。
- **已有实现**：通用层可生成（`protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空`）
- **备注**：2156B。id 清单可从本次抓包直接抄成常量表。

### 35003 · MiniGame_MissionList

- **类别 / 批次**：C（功能入口）/ 第 5 批（商店 / 咖啡厅 / 公会）
- **官方响应**：4480 B；请求 942–942 B；调用 1 次（观测值 4480）
- **数据来源**：`player_progress` + `exceldb_static`
- **依赖表**：`MiniGameMissionDBSchema(402)`
- **需要什么数据**：MissionHistoryUniqueIds [] + ProgressDBs 18 条 + ClearedOrignalMissionIds null ← 账号小游戏任务进度；静态查 MiniGameMissionDBSchema(402)。
- **为什么归这一档**：小游戏任务入口（请求 EventContentId=10838）。
- **已有实现**：通用层可生成（`protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空`）
- **备注**：4480B。启动链第 12 条就调了，但失败只影响小游戏入口。

### 36001 · Notification_EventContentReddotCheck

- **类别 / 批次**：E（可选/装饰）/ 第 3 批（能操作主界面）
- **官方响应**：1088 B；请求 926–926 B；调用 10 次（观测值 1088）
- **数据来源**：`official_config` + `player_progress`
- **依赖表**：`未找到（无红点配置表）`
- **需要什么数据**：Reddots={}（空对象）+ EventContentUnlockCGDBs 25 个 key（每个都是空数组，key 是活动 id：10838/50822/849/900801..900827 段）← 官方活动清单 + 账号解锁进度。
- **为什么归这一档**：109 条里 10 次轮询。只驱动红点。
- **已有实现**：完全没有（`同上，没有 NotificationEventContentReddotCheckResponse → router 回 Error 信封`）
- **备注**：1088B。回 `{"Reddots":{},"EventContentUnlockCGDBs":{}}` 即安全降级。

### 43010 · Friend_Check

- **类别 / 批次**：C（功能入口）/ 第 3 批（能操作主界面）
- **官方响应**：536 B；请求 922–926 B；调用 8 次（观测值 536）
- **数据来源**：`echo`
- **依赖表**：—
- **需要什么数据**：536B = 只有信封，0 个业务字段。
- **为什么归这一档**：好友入口检查（8 次轮询）。
- **已有实现**：通用层可生成（`protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空`）
- **备注**：与 28019 完全同构。

### 90004 · Management_Data

- **类别 / 批次**：B（大厅必要）/ 第 2 批（进大厅）
- **官方响应**：14124 B；请求 926–926 B；调用 10 次（观测值 14104, 14124）
- **数据来源**：`official_config`
- **依赖表**：`未找到（公告/活动/banner 全在官方 GM 后台，ExcelDB 无表）`
- **需要什么数据**：Data 9 组：Notices 6 条 / Events 14 条 / Issues 0 / Banners 7 条 / GachaProbabilityDisplay 12 条 / GuidePopup 0 / GachaPeriodDisplay / RaidPeriodDisplay / Survey。全部来自官方运营后台，Url 指向 notice.bluearchive-cn.com 与 webcnstatic.yostar.net ⇒ **必须自建一份静态运营配置**（或全部回空数组，客户端会少公告但不崩）。
- **为什么归这一档**：启动链第 7 条，且每 ~5s 轮询一次（109 条里出现 10 次）。承载公告/活动/banner/维护状态/客户端版本号——大厅顶部与活动页都要它。
- **已有实现**：手写实现（`_bridge:662-684 _generic_protocol_response(num==90004)，16 键，Notices/Events/Issues/Banners 全 []`）
- **备注**：两条实测 14124B / 14104B，差异只在 Banners 的某条字段（同一 BannerId 103869）。

### 90009 · Clan_Chat_Records

- **类别 / 批次**：C（功能入口）/ 第 5 批（商店 / 咖啡厅 / 公会）
- **官方响应**：30316 B；请求 970–970 B；调用 2 次（观测值 556, 30316）
- **数据来源**：`player_progress`
- **依赖表**：`未找到（聊天记录是运行时数据）`
- **需要什么数据**：ChatRecords 100 条{ChatId, MessageType, SubType, SocialGrade, StickerId, CharacterId, AccountNickname, Text, SendTicks, EmblemId} ← 运行时聊天记录，按 LastChatId 增量。无静态表。
- **为什么归这一档**：公会聊天（请求 ClanDBId + LastChatId 增量）。
- **已有实现**：通用层可生成（`protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空`）
- **备注**：30316B（100 条）/ 556B（LastChatId=321945，增量空）。未入会时回空。

---

## 6. 我们已有的实现

按任务的三分口径：**手写实现**（`account_auth_probe.py` 里的分支）/ **通用层可生成但没接线**（`response_factory.py` + `protocol_router.py`）/ **完全没有**。

**结果：手写 4 条 / 通用层可生成 31 条 / 完全没有 3 条。**

### 6.1 逐协议命中

| 协议号 | 名称 | 三分口径 | 实现级别 | 位置 / 依据 |
|---|---|---|---|---|
| 3 | NetworkTime_Sync | 完全没有 | 无 DTO 需反推 | `dto_schema_full_v2.json（709 类型）里没有 NetworkTimeSyncResponse → protocol_router 回 Error 信封` |
| 1002 | Account_Auth | 手写实现 | 完整手写 | `_bridge:1033-1051 path B + cn_inner27.build(a_proto_int) 27 字段；account_service.py:build_account_db_for() 供数据` |
| 1005 | Account_GetTutorial | 通用层可生成 | 通用兜底 | `protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空` |
| 1017 | Account_LoginSync | 手写实现 | 桩/空包 | `_bridge:696-702 _generic_protocol_response(num in (1019,1017))，492B，4 个空集合 + Responses:[]` |
| 4000 | Item_List | 通用层可生成 | 通用兜底 | `protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空` |
| 5000 | Echelon_List | 通用层可生成 | 通用兜底 | `protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空` |
| 5001 | Echelon_Save | 通用层可生成 | 通用兜底 | `protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空` |
| 6000 | Campaign_List | 通用层可生成 | 通用兜底 | `protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空` |
| 6020 | Campaign_EnterMainStageStrategySkip | 通用层可生成 | 通用兜底 | `protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空` |
| 6021 | Campaign_MainStageStrategySkipResult | 通用层可生成 | 通用兜底 | `protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空` |
| 7000 | Mail_List | 通用层可生成 | 通用兜底 | `protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空` |
| 7001 | Mail_Check | 通用层可生成 | 通用兜底 | `protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空` |
| 7003 | Mail_ListSemiPermanent | 通用层可生成 | 通用兜底 | `protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空` |
| 8000 | Mission_List | 通用层可生成 | 通用兜底 | `protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空` |
| 8002 | Mission_MultipleReward | 通用层可生成 | 通用兜底 | `protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空` |
| 8006 | Mission_GuideMissionSeasonList | 完全没有 | 无 DTO 需反推 | `同上，没有 MissionGuideMissionSeasonListResponse → router 回 Error 信封` |
| 10002 | Shop_List | 通用层可生成 | 通用兜底 | `protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空` |
| 15002 | OpenCondition_EventList | 通用层可生成 | 通用兜底 | `protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空` |
| 16000 | Toast_List | 通用层可生成 | 通用兜底 | `protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空` |
| 20001 | Cafe_Ack | 通用层可生成 | 通用兜底 | `protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空` |
| 20013 | Cafe_ReceiveCurrency | 通用层可生成 | 通用兜底 | `protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空` |
| 22000 | Arena_EnterLobby | 通用层可生成 | 通用兜底 | `protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空` |
| 22004 | Arena_EnterBattle | 通用层可生成 | 通用兜底 | `protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空` |
| 22008 | Arena_CumulativeTimeReward | 通用层可生成 | 通用兜底 | `protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空` |
| 22009 | Arena_DailyReward | 通用层可生成 | 通用兜底 | `protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空` |
| 22016 | Arena_SyncEchelonSettingTime | 通用层可生成 | 通用兜底 | `protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空` |
| 24000 | Academy_GetInfo | 手写实现 | 完整手写（仅新版副本） | `report/_tmp/sandbox292/account_auth_probe.py:408-577 _academy_24000_build（模板 academy_24000_official.json：71 个 ZoneVisitCharacterDBs 键 + 9 条 AcademyLocationDBs）` |
| 25003 | Event_RewardIncrease | 通用层可生成 | 通用兜底 | `protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空` |
| 26000 | ContentSave_Get | 通用层可生成 | 通用兜底 | `protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空` |
| 28000 | Clan_Lobby | 通用层可生成 | 通用兜底 | `protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空` |
| 28019 | Clan_Check | 通用层可生成 | 通用兜底 | `protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空` |
| 29002 | Billing_PurchaseListByYostar | 通用层可生成 | 通用兜底 | `protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空` |
| 30041 | EventContent_PermanentList | 通用层可生成 | 通用兜底 | `protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空` |
| 35003 | MiniGame_MissionList | 通用层可生成 | 通用兜底 | `protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空` |
| 36001 | Notification_EventContentReddotCheck | 完全没有 | 无 DTO 需反推 | `同上，没有 NotificationEventContentReddotCheckResponse → router 回 Error 信封` |
| 43010 | Friend_Check | 通用层可生成 | 通用兜底 | `protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空` |
| 90004 | Management_Data | 手写实现 | 桩/空包 | `_bridge:662-684 _generic_protocol_response(num==90004)，16 键，Notices/Events/Issues/Banners 全 []` |
| 90009 | Clan_Chat_Records | 通用层可生成 | 通用兜底 | `protocol_router.route() → response_factory.build(dto, pid, ctx)：结构合法、数据为空` |

### 6.2 手写的那 4 条（`account_auth_probe.py::_bridge` 的分支清单）

`_bridge` 本体在 `probe:942-1109`。它**不按协议号分支，而是先按「名字查不查得到」分流**（`NAME_TABLE` = 43 条 `BUILTIN_NAMES` + 部署机 `protocol_names.txt` + 5 个 `EXTRA_TOKENS`）。

| # | 行范围 | 判据 | 干了什么 | 是否本地造数据 |
|---|---|---|---|---|
| 1 | 943-955 | — | `parse_cn_multipart` 取 `protocol`/`packet`，兜底 urlencoded form（`+`→`%2B` 保护 base64） | — |
| 2 | 956-960 | `NAME_TABLE`/`EXTRA_TOKENS` 命中 | 解出协议名 | — |
| 3 | 962-968 | `exp=='experror'` | 直接回 Error 信封（`Protocol:-1/ErrorCode:500`） | 是（错误包） |
| 4 | 970-977 | `name is None`（未知协议） | 先 `_generic_protocol_response`，解不开就 `_forward` | 半（最小包） |
| 5 | 979-1025 | `exp.startswith('decrypt+')` | **path A**：解真请求 → 注入 SessionKey → `post_gateway` → 重封包 | **否，转官方** |
| 6 | 1027-1032 | `Account_CheckNexon`(1014) | 本地造 `{Protocol:1014, ResultState:1, SessionKey, AccountId}` | 是 |
| 7 | 1033-1051 | `Account_Auth`/`Account_Auth2`(1002/1012) | `post_gateway({'Protocol':'Account_Auth'})` → 官方回包重封 | **否，转官方** |
| 8 | 1053-1068 | `Account_CallName`(1010) | `cn_nick.build_callname_response()` | **是** |
| 9 | 1070-1087 | `Account_Nickname`(1001) | `cn_nick.build_nickname_response()` | **是** |
| 10 | 1089-1102 | `req_Hash>>32` 拿得到号 | `cn_nick.build_min_response()` = 只有 `{Protocol:pid}` | 半（最小包） |
| 11 | 1103-1106 | 认得名字但上面没管 | `_generic_protocol_response(name=…)` | 半（弱结构） |
| 12 | 1107-1109 | 其余 | `_forward` 只转发官方 | 否 |

`_generic_protocol_response`（`probe:643-716`）里**按协议号**硬编码的只有 3 档：

| 行范围 | 判据 | 产出 |
|---|---|---|
| 662-684 | `num == 90004` | Management_Data 16 键（运营内容全空） |
| 685-695 | `num == 24000` | Academy_GetInfo 9 键桩（`_bridge_ref` 旧版） |
| 696-702 | `num in (1019, 1017)` | Account_LoginSync 壳（`Responses:[]`） |
| 703-714 | 其它 | 最小泛型包（`StaticOpenConditions` 是 `[]` 而不是 55 键字典，可能被客户端当类型错 —— 待验） |

**一句话**：`_bridge` 里真正「本地构造响应体」的只有 `1001` / `1010` / `1014` / `1017(1019)` / `24000` / `90004` + `1002` 的实验性构造；其余全是「转发官方」或「最小泛型包」。38 条里只有 **1002 / 1017 / 24000 / 90004** 有号级别的专属分支，其中只有 `24000` 在新版副本里升级成了官方模板渲染（有真实数据），其余三个仍是固定值/空列表。

### 6.3 通用层：结构齐全，但没有一条业务语义

**① `response_factory.py`** —— 靠 `dto_schema_full_v2.json`（2.37MB，709 类型 / 455 个 Response DTO）做**全量 schema 驱动生成**：

- `factory:222 load_schema()` / `:470 base_chain()` / `:498 effective_fields()` / `:742 _emit_object()` / `:839 _value_for()` / `:871 _default_for()`。
- 值只有三种来源：常量默认 / `account_state` 绑定（`factory:140 OBJECT_BINDINGS`、`:157 LIST_BINDINGS`、`:183 DICT_BINDINGS`、`:191 SCALAR_BINDINGS`）/ `context['values']`·`hooks` 注值。
- 实测：schema 里「没有任何协议指向」的 DTO 也能 `build()` 出合法 JSON ⇒ **生成能力只取决于 schema 里有没有这个名字**。反向：不存在的名字 → `{}` + warning。

**② `protocol_router.py`** —— `route()`（`router:444`）**全量路由、无白名单**：`Hash>>32` / base32 token / path 三路解析 → 协议号 + DTO → `ResponseSpec`；解析不出来就降级 `_error_spec()`（`router:429`）回 Error 信封，不抛异常。`coverage()` / `iter_protocols()` 提供全量覆盖率统计。

**③ 三个真空缺**：`3` / `8006` / `36001` 在 schema 里**没有对应的 Response DTO**（709 类型全查过），`route()` 对它们只能回 Error 信封。这三条必须先从抓包反推 DTO 才能进通用层。

**④ 局限（必须记住）**：结构完整 ≠ 客户端会接受（`factory:37-40` 自己写着）；`LIST_BINDINGS` 里没有的类型（如 `MailDB`、`ShopInfoDB`）**永远填不进数据**；全库仍有 264 个字段类型靠字段名启发式，`22004` 实测就踩到一个（`EventHandler` → `{}`）。

### 6.4 账号服务层（真实现，但只覆盖 1002 + 1017 的存档底座）

`work/ba/server/account_service.py`：多用户账号、`SessionKey` 签发/校验、`load_blob`/`save_blob` 存档、`build_account_db_for()`（= 1002 的 `AccountDB`）、`build_state_for()` / `bootstrap_state()`。**不含**任何一条业务协议的回包构造。

### 6.5 本表之外的隐藏前置：`1001` / `1010`

本表按 109 条官方抓包统计，因此不含 `1001 Account_Nickname` 与 `1010 Account_CallName`；但官方账号已建号，**私服新号第一次登录必然走这两步**（`report/67` §1.C：1001 缺 → 停在昵称页，1010 缺 → 停在发音页）。好消息是这两条已手写（各 856B，`cn_nick.py`），可直接搬。**它们实际上比本表任何一条都更靠前。**

---

## 7. 未找到 / 待核

### 7.1 数据表缺口（「找不到」而不是「没找」）

- ExcelDB.db 里没有任何 Mail* 表（邮件 7000/7001/7003 无静态定义，只能自建 + DefaultMailExcel 的 1 封初始邮件）
- ExcelDB.db 里没有任何 EventRewardIncrease* 表（25003 纯官方活动配置）
- ExcelDB.db 里没有公告/活动/banner 表（90004 的 Notices/Events/Banners/GachaProbabilityDisplay 全在官方 GM 后台）
- ExcelDB.db 里没有公会/公会成员表（只有 ClanChattingEmojiDBSchema(176) 与 ClanRewardDBSchema(1)），28000/90009 只能靠运行时多用户数据
- ExcelDB.db 里没有 Attachment* / ContentSweep* / MissionCategory* 表（Mission 的 Category 是 MissionDBSchema.Bytes 里的一个字段，没有独立分类表）
- ArenaSeasonCloseRewardDBSchema 存在但 0 行 → 22004 的 SeasonRewards 内容无法由查表得出（只能按赛季配置自建）
- 没有任何 ArenaDailyReward 表 → 22009 的日奖励内容只能自建配置
- 新号 AcademyLocationDBs 应该有 0/1/9 条——未找到确定规则（initial_state_rules q8 标「未找到」）
- 新号 Mission_List / GuideMissionSeasonList 的初始触发集合——未找到（只有「官方老号 1240/733 条」这一个观测值）
- 29002 CountList 的 4 个 ShopCashId 具体值——未找到
- 90009/28000 的初始态（未入会）在抓包里没有样本——抓包里的号已入会（ClanDBId=27353）

### 7.2 本表之外的隐藏门槛：`1001` / `1010`（详见 §6.5，此处只留索引）

本表按「109 条官方抓包」统计，因此不含 `1001 Account_Nickname` 与 `1010 Account_CallName`。但官方抓包里的账号是**已建号**，新号第一次登录必然走这两步：

- `report/67` §1.C：`1001` 未实现时界面**停在昵称页**；`1010` 未实现时**停在发音页**。
- 落实时：私服必须实现 1001/1010，否则新号连名字都过不去 —— 它们实际上比本表任何一条都更靠前。
- 好消息：这两条已手写（`cn_nick.py`，各 856B），可以直接搬；见 §6.5。

### 7.3 两个需要实测确认的分歧

1. **`1017` vs `1019`**：`report/67`（2026-11-14，来自客户端请求解密）记 `Account_LoginSync = 1019`；本次官方抓包（2026-11-16）三条独立证据都是 `1017`（请求 JSON `Protocol=1017`、`Hash>>32=1017`、响应 `inner.Protocol=1017`）。**以本次为准**，服务端建议 1017/1019 双别名都收。
2. **`24000` 到底是不是卡点**：`report/67` 判定它是报错前最后一条请求；`report/83` §5 记录「06:05 换成真结构后客户端表现与 192B 假包完全相同」⇒ 说明还有别的卡点（`SessionKey` 未被客户端采纳）。分类仍按 A（启动链第 2 条），但落地时不要单验它。

---

## 8. 工程注意（踩坑清单）

1. **内层 `Protocol` 必须是整数**（`1002` 而非 `"1002"`）。`report/83` 记录：改整数才推进到昵称界面。
2. **`1017` 的子回包 `Protocol` 全是 0**，不是各自协议号。
3. **`SyncProtocols` 别当空表**：本次客户端点名了 **25 个协议号**，回包就是这 25 个具名子回包 + 5 个无条件散字段。照抄「按点名返回」即可，不要回 `Responses` 数组。
4. **`Client` 会重放同一个包**（`report/67` D5：同 `req_key`/`req_iv`/`Hash` 字节级重放）⇒ 所有写操作必须**幂等**。
5. **表单里的裸 `+`**：`packet` 是 base64，裸 `+` 会被 `parse_qs` 解成空格（`report/67` D6）⇒ 解析前先把 body 里的 `+` 转成 `%2B` 再解析，或改用 `parse_qsl` 并保留空白。这一条会让「同一协议时而能解、时而 0 字节」。
6. **`ParcelResultDB` 是横切能力**：发奖/扣材料的所有协议（`8002`/`6020`/`6021`/`20013`/`22004`/`22008`/`22009`）都返回它，形态是 `{AccountDB, AccountCurrencyDB, ItemDBs/EquipmentDBs, DisplaySequence, BaseAccountExp, AdditionalAccountExp}` 的子集。先做一套，后面全部复用。
7. **`CurrencyDict` 必须含全部 29 个 key**（含值为 0 的），不能只写发放的 19 个 —— 官方 `CurrencyDict` 的键是 `"1".."29"` 全量。
8. **`CafeDBId = AccountServerId * 10 + CafeId`**（官方实测 `10015354380 → 100153543801 / 100153543802`）。
9. **`Echelon` 的槽位是定长数组**：主槽 4、支援槽 2、`SkillCardMulliganCharacterIds` 3、`CombatStyleIndex` 6 —— 空槽补 0，不能缩短数组。
10. **`ServerTimeTicks` 是 .NET DateTime.Ticks**（自 `0001-01-01` 起的 100ns 计数），不是 Unix 时间戳。
11. **`1017` 内嵌的子响应是「默认值模板」，别拿它反推新号状态**：内层 `AccountLevel=1` 而 `AccountDB.Level=32`；内层 `AcademyLocationRankSum=1` 而 `24000` 实测 9 条 `Rank` 之和 = **14**；子响应 `Protocol/ServerTimeTicks/SessionKey.AccountServerId/RequestId` 全是 0 值。⇒ 新号该有什么必须回到 `initial_state_rules.json` 的规则表判定。
12. **schema 里缺 3 个 Response DTO**：`3` / `8006` / `36001` 在 `dto_schema_full_v2.json`（709 类型）里没有对应 DTO，`protocol_router` 对它们只能回 `Error` 信封。这三条开工第一步是**先从抓包反推 DTO**。
13. **`protocol_map.json` 里 `NetworkTime_Sync` 的 `id` 是 `null`**（`resp` 也是 null）。编号 3 来自抓包文件名 `04_3_api_networktime_sync` 与请求里的 `Protocol:3`，不在映射表里 —— 查表时要小心。
14. **`SessionKey` 不该无条件回**：`response_factory` 的 `SESSION_KEY_ECHO_PROTOCOLS` 白名单只有 `1000/1002/1009/1012/1014/37000/37001`；官方 `1017`/`4000` 等响应确实不带 `SessionKey`/`AccountId` 之外的骨包键，照抄即可。
15. **`22000` 的对手是 NPC 不是真人**：`AccountServerId:0`、`NickName:'Character_<CharacterUniqueId>'`，定义只有 `ArenaNPCDBSchema`(13 行)，给哪 3 个 / 什么 Rank·Level 由服务端按 `PlayerGroupId` 动态生成。
16. **`ArenaSeasonCloseRewardDBSchema` 是 0 行空表** ⇒ `22004` 的 `SeasonRewards` 不可能查表得出，只能按赛季配置自建。
17. **`AttendanceBookDBSchema` / `CharacterSkillDBSchema` 这两个名字不存在**：真实表是 `AttendanceDBSchema`(31) + `AttendanceRewardDBSchema`(334)、`CharacterSkillListDBSchema`(6708) + `SkillDBSchema`(18028)。

---

## 9. 机器可读数据

同目录 `protocol_priority.json`，字段：

- `counts` — 各类别/批次/工作量计数与总人日
- `protocols[38]` — 每条：`id/name/path/category/batch/resp_bytes_official/resp_bytes_instances/sources/tables/effort/effort_days/existing/existing_detail/existing_ref/existing_note/gate/need/note`
- `sub_responses_1017[30]` — 1017 的子回包拆解
- `rpcs[109]` — 逐条 RPC 实例：`seq/protocol/name/path/req_bytes/resp_bytes/category/batch/note`
- `not_found` / `key_findings`

### 自检

`work/ba/proto/_validate_priority.py` 把 JSON 与原始抓包逐条对账：

- 109 条 `req_bytes`/`resp_bytes`/`protocol`/`name` 逐条与 `report/_tmp/official_decoded_201/` 的 `meta` 比对 → **0 mismatch**
- `resp_bytes_official` == 该协议所有实例的最大值；`resp_bytes_instances` == 去重排序后的实例字节集合
- `instances` 求和 == 109；批次/类别计数求和 == 38；1017 子回包 25 具名 + 5 无条件、字节合计 166163
- 结果：**ALL PASS**

### 本目录新增文件（全部为本次任务产物，未改动任何既有文件）

| 文件 | 作用 |
|---|---|
| `protocol_priority.json` | 交付物①：机器可读优先级表 |
| `protocol_priority.md` | 交付物②：本文件 |
| `_gen_priority.py` | 两个交付物的唯一生成器（数据内置，改数据即改产物） |
| `_priority_scan.py` / `_scan_inventory.json` | 把 109 对抓包扫成清单（字节数/字段形状） |
| `_validate_priority.py` / `_out_validate.txt` | 与原始抓包对账的自检脚本与结果 |
| `_probe_*.py` / `_out_*.txt` | 取证脚本与中间输出（1017 子回包权重、逐实例请求参数、表清单、序列） |
| `_sub_impl_inventory.md` | 实现盘点原始报告（含 `_bridge` 全部行号、通用层行号） |
| `_sub_exceldb.md` | ExcelDB 398 表 × 38 协议的数据来源实测报告（逐字段表格） |

