# 8000 / 8006 / 8002 字段溯源结论（只读分析）

- 数据源：`work\ba\data\ExcelDB.db`（只读）+ `report\_tmp\official_decoded_201\` 官方解密响应
- 响应：`08_8000`(1240) / `10_8000`(39) / `11_8000`(35) / `09_8006`(733) / `59_8002`(8)
- 方法：官方真实值 → ExcelDB 反查（值匹配 + 行级一致性），**不做表名猜测**
- 判定：`verified / ambiguous / weak / not_found`（`xls_match.py` 口径）

## 0. 先回答最关键的问题：`MissionUniqueId` 分散在哪

库中名字带 `Mission` 的表共 **8 张**：

| 表 | 行数 |
|---|---|
| `BattlePassMissionDBSchema` | 19 |
| `EventContentMissionDBSchema` | 2384 |
| `GuideMissionDBSchema` | 923 |
| `GuideMissionOpenStageConditionDBSchema` | 9 |
| `GuideMissionSeasonDBSchema` | 20 |
| `MiniGameMissionDBSchema` | 402 |
| `MissionDBSchema` | 3444 |
| `MissionEmergencyCompleteDBSchema` | 0 |

> 注意：**没有** `WeekDungeonMission*` 表（不存在）；`MissionEmergencyCompleteDBSchema` 是 **0 行**空表。
> `GuideMissionOpenStageConditionDBSchema` 没有 `Id` 列（只有 `SeasonId`/`OrderNumber`），不参与 id 匹配。

### 0.1 按 `Category` 分桶 → 表（这是真正的分区键）

| Category | id 范围 | 元素数 | 落到表 | 命中/总数 | 覆盖率 |
|---|---|---|---|---|---|
| 0 | 30002..30097 | 72 | `MissionDBSchema` | 72/72 | 1.000 |
| 1 | 1502..400006 | 12 | `MissionDBSchema` | 12/12 | 1.000 |
| 2 | 2300..2400 | 11 | `MissionDBSchema` | 11/11 | 1.000 |
| 3 | 10004..400012 | 380 | `MissionDBSchema` | 380/380 | 1.000 |
| 4 | 1000212..1001875 | 1429 | `GuideMissionDBSchema` | 1429/1429 | 1.000 |
| 7 | 108380000..108380017 | 36 | `MiniGameMissionDBSchema` | 36/36 | 1.000 |
| 8 | 849001..10838017 | 112 | `EventContentMissionDBSchema` | 112/112 | 1.000 |
| 9 | 1606..1606 | 2 | `MissionDBSchema` | 2/2 | 1.000 |
| 10 | 1701..1701 | 1 | `MissionDBSchema` | 1/1 | 1.000 |

Category 与表内槽位的**行级一致性**（同一行的值对比，不是表名猜测）：

| 表 | 槽位 | 该槽位 == Category | 参与行数 |
|---|---|---|---|
| `MissionDBSchema` | `f1` | 1.000 | 406 |
| `GuideMissionDBSchema` | `f2` | 1.000 | 1429 |
| `EventContentMissionDBSchema` | `f4` | 1.000 | 112 |
| `MiniGameMissionDBSchema` | `f4` | 1.000 | 36 |

→ `MissionDBSchema.f1` / `GuideMissionDBSchema.f2` / `EventContentMissionDBSchema.f4` /
`MiniGameMissionDBSchema.f4` **就是 Category 的静态来源**，命中率全部 1.000。
（Category=0 的 81 行 30002..30097 在 FlatBuffers 里 `f1` 槽位整体缺席 —— 默认值 0 不落盘，因此 0/81 显现，语义上仍等于 0。）

### 0.2 按数值段分桶 → 表（8000 的 1240 个值）

| 位数 | 值域 | 值数 | 有归属 | 覆盖率 | 唯一表 | 逐表命中 |
|---|---|---|---|---|---|---|
| 4 位 | 1502..2400 | 24 | 24/24 | 1.000 | `MissionDBSchema` | Mission=24 |
| 5 位 | 10004..90001 | 281 | 281/281 | 1.000 | `MissionDBSchema` | Mission=281 |
| 6 位 | 100000..849039 | 210 | 210/210 | 1.000 | `**混合**` | Mission=171, EventContentMission=39, GuideMissionSeason=1 |
| 7 位 | 1000212..1001875 | 690 | 690/690 | 1.000 | `GuideMissionDBSchema` | GuideMission=690 |
| 8 位 | 10838001..10838017 | 17 | 17/17 | 1.000 | `EventContentMissionDBSchema` | EventContentMission=17 |
| 9 位 | 108380000..108380017 | 18 | 18/18 | 1.000 | `MiniGameMissionDBSchema` | MiniGameMission=18 |

**结论：8000 的 1240 个不同 `MissionUniqueId`，1240/1240 全部有归属（覆盖率 1.000），没有任何一段对不上。**
（三协议合并共 1283 个不同值，同样 100% 有归属，分桶见 JSON 的 `buckets_all_protocols`。）
你初步跑出的 `GuideMissionDBSchema` 0.56 覆盖率是**正常现象**：GuideMission 只覆盖 Category=4，
而 8000 里 Category=4 只占 690/1240。完整分区是：

| id 段 | 表 | 依据 |
|---|---|---|
| Category=0（30002..30097） | `MissionDBSchema` | 槽位 `f1` 一致 1.000 |
| Category=1（1502..400006） | `MissionDBSchema` | 槽位 `f1` 一致 1.000 |
| Category=2（2300..2400） | `MissionDBSchema` | 槽位 `f1` 一致 1.000 |
| Category=3（10004..400012） | `MissionDBSchema` | 槽位 `f1` 一致 1.000 |
| Category=4（1000212..1001875） | `GuideMissionDBSchema` | 槽位 `f2` 一致 1.000 |
| Category=7（108380000..108380017） | `MiniGameMissionDBSchema` | 槽位 `f4` 一致 1.000 |
| Category=8（849001..10838017） | `EventContentMissionDBSchema` | 槽位 `f4` 一致 1.000 |
| Category=9（1606..1606） | `MissionDBSchema` | 槽位 `f1` 一致 1.000 |
| Category=10（1701..1701） | `MissionDBSchema` | 槽位 `f1` 一致 1.000 |

**需要保留的歧义（如实写）**：
1. **6 位段是唯一混合的段**（100000..849039）：`MissionDBSchema` 171 个 + `EventContentMissionDBSchema` 39 个。
   `849001..849039`(Category 8) 走 EventContent，而 `100000`/`400006`(Category 1/3) 走 Mission ——
   **6 位不能用位数定表，必须看 Category**。
2. 其余位数段与表一一对应，没有歧义：4/5 位 -> Mission，7 位 -> GuideMission，
   8 位 `10838001..10838017` -> EventContent(Category 8)，9 位 `108380000..108380017` -> MiniGame(Category 7)。
3. **6 位段有 1 个撞号值**：`100000` 同时是 `MissionDBSchema.Id` 和 `GuideMissionSeasonDBSchema.Id`。
   归属按 Category 判（Category=3 -> MissionDBSchema），不是按表名。

**跨表共存的值**：6 位段 [100000]。

## 1. 五个「静态表 vs 玩家进度」判定

| 字段 | 判定 | 证据 |
|---|---|---|
| `ProgressDBs[].StartDate` | **玩家进度** | 1314 个值仅 23 个不同；格式 `2026-11-16T04:00:06.215`（带毫秒、ISO T）；30 个跨协议去重时间戳在库的字符串槽位命中 **0/30**；静态日期是 `2021-02-15 04:00:00` 风格 |
| `Progress` | **字段不存在** | 3 个协议的全部响应递归扫描字段名，`Progress` 精确命中 **0** 次，只有 `ProgressDBs` / `MissionProgressDBs` / `ProgressParameters` |
| `ProgressParameters` | **玩家进度**（value）/ key 部分静态 | value 分布 n=1118：min=0 p50=1 p90=999 max=29555089，是计数；key 的静态归属见 1.1 |
| `MissionHistoryUniqueIds` | **玩家历史列表**（id 本身静态） | 372 个值 100% 落表（Mission 291 / Guide 77 / EventContent 4），但整张列表是玩家通关历史，另两份响应为空 |
| `ClearedOriginalMissionIds` | **玩家历史列表** | 与 `MissionHistoryUniqueIds` **372/372 同序完全相等**，落表同上 |

### 1.1 `ProgressParameters` 的 key 能追到哪

| Category | 元素数 | key == `MissionDBSchema.f19` | key == `EventContentId`/`f1` | key == `f15` | key ∈ `CampaignStageDBSchema.Id` |
|---|---|---|---|---|---|
| 0 | 72 | 72 | 0 | 0 | 72/72 |
| 1 | 1 | 0 | 0 | 0 | 0/1 |
| 3 | 189 | 0 | 2 | 8 | 36/195 |
| 4 | 548 | 0 | 0 | 0 | 102/558 |
| 7 | 34 | 0 | 12 | 0 | 0/34 |
| 8 | 104 | 0 | 44 | 60 | 0/104 |

→ Category=0 段 **72/72 = 1.000** 由 `MissionDBSchema.f19` 决定；
Category=8 段 `EventContentId`(44) + `f15`(60) = **104/104 = 1.000**（二选一）；
Category 3 段 `36/195 = 18.5%`、Category 4 段 `102/558 = 18.3%`、Category 7 段 `0/34`，
**其余 key 在本数据集内无法定表**（如实记为部分 not_found，未强行归因）。

分协议拆开（同一口径）：

| 协议 | Category | 元素数 | f19 | EventContentId/f1 | f15 | ∈CampaignStage |
|---|---|---|---|---|---|---|
| 8000 | 0 | 72 | 72 | 0 | 0 | 72/72 |
| 8000 | 1 | 1 | 0 | 0 | 0 | 0/1 |
| 8000 | 3 | 189 | 0 | 2 | 8 | 36/195 |
| 8000 | 4 | 273 | 0 | 0 | 0 | 51/278 |
| 8000 | 7 | 34 | 0 | 12 | 0 | 0/34 |
| 8000 | 8 | 104 | 0 | 44 | 60 | 0/104 |
| 8002 | 4 | 1 | 0 | 0 | 0 | 0/1 |
| 8006 | 4 | 274 | 0 | 0 | 0 | 51/279 |

## 2. 逐字段映射

> `verified_by=manual` 为逐值手验；`auto` 为「稀有槽位命中率」自动判定（ParcelResultDB 块）。

### 8000 Mission_List（8 条路径）

| 路径 | 判定 | 表/槽位 | 证据 | 置信度 |
|---|---|---|---|---|
| `ProgressDBs[].MissionUniqueId` | 表名 | `MissionDBSchema/GuideMissionDBSchema/EventContentMissionDBSchema/MiniGameMissionDBSchema` . `sql:Id` | 命中 1240/1240，覆盖率 1.000 | high |
| `ProgressDBs[].Category` | 表名 | `MissionDBSchema.f1 / GuideMissionDBSchema.f2 / EventContentMissionDBSchema.f4 / MiniGameMissionDBSchema.f4` . `f1|f2|f4` | 行级：本协议 1314/1314 元素的行内 Category 槽位与 Category 相等；分表命中率全部 1.000 | high |
| `ProgressDBs[].StartDate` | player | — | 23 个不同时间戳；30 个去重时间戳在库字符串槽位命中 0/30（覆盖率 0.000） | high |
| `ProgressDBs[].ProgressParameters.*` | player | `MissionDBSchema.f19 (仅 Category=0)` . `f19` | 1107 个元素有 PP，其中 673 个含非 0 key；value 无静态源（玩家计数）；key 仅 Category=0（72/72）与 Category=8（104/104）可定表 | medium |
| `ProgressDBs[].AccountServerId` | player | — | 命中 0/1314，覆盖率 0.000 | high |
| `DailySuddenMissionInfo.Id` | 表名 | `MissionDBSchema` . `sql:Id` | 命中 1/1，覆盖率 1.000 | weak |
| `MissionHistoryUniqueIds[]` | 表名 | `MissionDBSchema/GuideMissionDBSchema/EventContentMissionDBSchema` . `sql:Id` | 命中 372/372，覆盖率 1.000 | medium |
| `ClearedOriginalMissionIds[]` | 表名 | `MissionDBSchema/GuideMissionDBSchema/EventContentMissionDBSchema` . `sql:Id` | 命中 372/372，覆盖率 1.000 | medium |

### 8006 Mission_GuideMissionSeasonList（10 条路径）

| 路径 | 判定 | 表/槽位 | 证据 | 置信度 |
|---|---|---|---|---|
| `MissionProgressDBs[].MissionUniqueId` | 表名 | `GuideMissionDBSchema` . `sql:Id` | 命中 733/733，覆盖率 1.000 | high |
| `MissionProgressDBs[].Category` | 表名 | `GuideMissionDBSchema` . `f2` | 行内 f2 == Category：733/733；官方侧 d=1（恒为 4），属弱证据 | medium |
| `MissionProgressDBs[].StartDate` | player | — | 4 个不同时间戳；库字符串槽位命中 0/4（覆盖率 0.000） | high |
| `MissionProgressDBs[].ProgressParameters.*` | player | — | 686 个元素有 PP；key 静态归属 51/279 命中 CampaignStageDBSchema.Id；value 无静态源 | low |
| `MissionProgressDBs[].AccountServerId` | player | — | 命中 0/733，覆盖率 0.000 | high |
| `GuideMissionSeasonDBs[].SeasonId` | 表名 | `GuideMissionSeasonDBSchema` . `sql:Id` | 命中 17/17，覆盖率 1.000 | high |
| `GuideMissionSeasonDBs[].LoginCount` | player | — | 命中 0/6，覆盖率 0.000 | high |
| `GuideMissionSeasonDBs[].StartDate` | player | — | 命中 0/6，覆盖率 0.000 | high |
| `GuideMissionSeasonDBs[].LoginDate` | player | — | 命中 0/6，覆盖率 0.000 | high |
| `GuideMissionSeasonDBs[].IsFinalMissionComplete` | player | — | 命中 0/6，覆盖率 0.000 | high |

### 8002 Mission_MultipleReward（48 条路径）

| 路径 | 判定 | 表/槽位 | 证据 | 置信度 |
|---|---|---|---|---|
| `MissionProgressDBs[].MissionUniqueId` | 表名 | `GuideMissionDBSchema (4) + MissionDBSchema (2)` . `sql:Id` | 命中 6/6，覆盖率 1.000 | medium |
| `MissionProgressDBs[].Category` | 表名 | `GuideMissionDBSchema.f2 / MissionDBSchema.f1` . `f2|f1` | 行内槽位 == Category：8/8 | medium |
| `MissionProgressDBs[].StartDate` | player | — | 4 个不同时间戳；库字符串槽位命中 0/4 | high |
| `MissionProgressDBs[].ProgressParameters.*` | player | — | 8 个元素；key 只有 0 与 20000002 两种；value 为玩家计数，无静态源 | low |
| `MissionProgressDBs[].AccountServerId` | player | — | 命中 0/8，覆盖率 0.000 | high |
| `AddedHistoryDBs[].MissionUniqueId` | echo | `GuideMissionDBSchema` . `sql:Id` | 命中 11/11，覆盖率 1.000 | high |
| `AddedHistoryDBs[].CompleteTime` | player | — | 命中 0/11，覆盖率 0.000 | high |
| `AddedHistoryDBs[].Expired` | player | — | 命中 0/11，覆盖率 0.000 | high |
| `AddedHistoryDBs[].AccountServerId` | player | — | 命中 0/11，覆盖率 0.000 | high |
| `ParcelResultDB.*` | echo | — | AccountDB+AccountCurrencyDB 共 14 个整数标量，命中库稀槽位 0/14（稀有槽位命中率 0.00） | high |
| `ParcelResultDB.DisplaySequence[].Key.Id` | 表名 | `ItemDBSchema` . `sql:Id` | 命中 8/9，覆盖率 0.889 | medium |
| `ParcelResultDB.ItemDBs.*.UniqueId` | 表名 | `ItemDBSchema` . `sql:Id` | 命中 7/7，覆盖率 1.000 | medium |
| `ParcelResultDB.AccountDB.ServerId` | echo | — | d=1，稀有槽位命中率 0.00（1 样本） | medium |
| `ParcelResultDB.AccountDB.RoleId` | echo | — | d=1，稀有槽位命中率 0.00（1 样本） | medium |
| `ParcelResultDB.AccountDB.Nickname` | echo | — | d=1，稀有槽位命中率 0.00（1 样本） | medium |
| `ParcelResultDB.AccountDB.CallName` | echo | — | d=1，稀有槽位命中率 0.00（1 样本） | medium |
| `ParcelResultDB.AccountDB.DevId` | echo | — | d=1，稀有槽位命中率 0.00（1 样本） | medium |
| `ParcelResultDB.AccountDB.State` | echo | — | d=1，稀有槽位命中率 0.00（1 样本） | medium |
| `ParcelResultDB.AccountDB.Level` | echo | — | d=1，稀有槽位命中率 0.00（1 样本） | medium |
| `ParcelResultDB.AccountDB.Exp` | echo | — | d=1，稀有槽位命中率 0.00（1 样本） | medium |
| `ParcelResultDB.AccountDB.Comment` | echo | — | d=1，稀有槽位命中率 0.00（1 样本） | medium |
| `ParcelResultDB.AccountDB.LobbyMode` | echo | — | d=1，稀有槽位命中率 0.00（1 样本） | medium |
| `ParcelResultDB.AccountDB.RepresentCharacterServerId` | echo | — | d=1，稀有槽位命中率 0.00（1 样本） | medium |
| `ParcelResultDB.AccountDB.MemoryLobbyUniqueId` | echo | — | d=1，稀有槽位命中率 0.00（1 样本） | medium |
| `ParcelResultDB.AccountDB.LastConnectTime` | echo | — | d=1，稀有槽位命中率 0.00（1 样本） | medium |
| `ParcelResultDB.AccountDB.BirthDay` | echo | — | d=1，稀有槽位命中率 0.00（1 样本） | medium |
| `ParcelResultDB.AccountDB.CallNameUpdateTime` | echo | — | d=1，稀有槽位命中率 0.00（1 样本） | medium |
| `ParcelResultDB.AccountDB.PublisherAccountId` | echo | — | d=1，稀有槽位命中率 0.00（1 样本） | medium |
| `ParcelResultDB.AccountDB.RetentionDays` | echo | — | d=1，稀有槽位命中率 0.00（1 样本） | medium |
| `ParcelResultDB.AccountDB.VIPLevel` | echo | — | d=1，稀有槽位命中率 0.00（1 样本） | medium |
| `ParcelResultDB.AccountDB.CreateDate` | echo | — | d=1，稀有槽位命中率 0.00（1 样本） | medium |
| `ParcelResultDB.AccountDB.UnReadMailCount` | echo | — | d=1，稀有槽位命中率 0.00（1 样本） | medium |
| `ParcelResultDB.AccountDB.LinkRewardDateDate` | echo | — | d=1，稀有槽位命中率 0.00（1 样本） | medium |
| `ParcelResultDB.AccountDB.Location` | echo | — | d=1，稀有槽位命中率 0.00（1 样本） | medium |
| `ParcelResultDB.AccountDB.LastReturningDate` | echo | — | d=1，稀有槽位命中率 0.00（1 样本） | medium |
| `ParcelResultDB.AccountCurrencyDB.AccountLevel` | echo | — | d=1，稀有槽位命中率 0.00（1 样本） | medium |
| `ParcelResultDB.AccountCurrencyDB.AcademyLocationRankSum` | echo | — | d=1，稀有槽位命中率 0.00（1 样本） | medium |
| `ParcelResultDB.AccountCurrencyDB.CurrencyDict.*` | echo | — | d=10，稀有槽位命中率 0.00（10 样本） | medium |
| `ParcelResultDB.AccountCurrencyDB.UpdateTimeDict.*` | echo | — | d=15，稀有槽位命中率 0.00（15 样本） | medium |
| `ParcelResultDB.EquipmentDBs.*.Type` | echo | — | d=1，稀有槽位命中率 0.00（1 样本） | medium |
| `ParcelResultDB.EquipmentDBs.*.ServerId` | echo | — | d=1，稀有槽位命中率 0.00（1 样本） | medium |
| `ParcelResultDB.EquipmentDBs.*.UniqueId` | echo | — | d=1，稀有槽位命中率 0.00（1 样本） | medium |
| `ParcelResultDB.EquipmentDBs.*.StackCount` | echo | — | d=1，稀有槽位命中率 0.00（1 样本） | medium |
| `ParcelResultDB.ItemDBs.*.Type` | echo | — | d=1，稀有槽位命中率 0.00（1 样本） | medium |
| `ParcelResultDB.ItemDBs.*.ServerId` | echo | — | d=7，稀有槽位命中率 0.00（7 样本） | medium |
| `ParcelResultDB.ItemDBs.*.StackCount` | echo | — | d=6，稀有槽位命中率 0.00（6 样本） | medium |
| `ParcelResultDB.DisplaySequence[].Key.Type` | echo | — | d=3，稀有槽位命中率 0.00（3 样本） | medium |
| `ParcelResultDB.DisplaySequence[].Amount` | echo | — | d=6，稀有槽位命中率 0.00（6 样本） | medium |

## 3. 找不到来源的字段

- `Progress`（8000/8006/8002）：字段根本不存在，只有 `ProgressParameters`。
- `ProgressParameters` 的 key（Category 1/3/4/7 段）：81.5%~100% 的 key 在 398 张表里无 1:1 归属（Category 0 段和 8 段例外，见 1.1）。
- `ProgressParameters` 的 value：本质是玩家计数，**不存在**静态来源（不应去找表）。
- `MissionHistoryUniqueIds` / `ClearedOriginalMissionIds` 的**顺序与集合**：玩家状态，无静态来源。
- `08_8000` 的 `HistoryDBs` 全为 `null`，无法分析。
- `ParcelResultDB` 下 36 个叶子路径：稀有槽位命中率全为 **0.00**，属玩家状态回显，不是静态表字段。

## 4. 复现命令

```
python work/ba/proto/_sub_mission_probe.py mission      # 列出所有 *Mission* 表
python work/ba/proto/_sub_mission_bucket.py             # 分桶 + 逐桶落表
python work/ba/proto/_sub_mission_cat.py                # Category vs 槽位 行级一致性
python work/ba/proto/_sub_mission_misc.py               # 路径清单 / Category=0 / History
python work/ba/proto/_sub_mission_pp.py                 # SeasonId / Progress 存在性
python work/ba/proto/_sub_mission_pp2.py                # 非 0 PP key 溯源
python work/ba/proto/_sub_mission_ppkey.py              # PP key 语义（f19 / EventContentId / f15）
python work/ba/proto/_sub_mission_ppkey2.py             # PP key 静态归属量化
python work/ba/proto/_sub_mission_final_probe.py        # History/Cleared/StartDate
python work/ba/proto/_sub_mission_report.py             # 生成 md/json（本文件）
```

> 只读保证：全程 `sqlite3.connect('file:...?mode=ro', uri=True)` 打开 ExcelDB；
> 本任务只新建了 `_sub_mission*` 产物，未改动任何既有文件。
