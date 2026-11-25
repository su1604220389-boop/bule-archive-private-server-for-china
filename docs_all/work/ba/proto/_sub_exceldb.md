# BA 私服 · 38 个协议的响应数据来源实测核实

> 只读数据子 agent 产出。生成时间 2026-11-16。
> 本文件是**唯一交付物**；所有临时脚本均在 `work\ba\proto\_sub_*.py`。

---

## 0. 口径与只读证明

| 项 | 值 |
|---|---|
| 静态表库 | `work\ba\data\ExcelDB.db`，160,534,528 B（153 MB） |
| 打开方式 | `sqlite3.connect('file:.../ExcelDB.db?mode=ro', uri=True)` —— 全程 `mode=ro`，未执行任何 INSERT/UPDATE/CREATE/DROP |
| 表总数 | **398**（`SELECT name FROM sqlite_master WHERE type='table'`） |
| 总行数 | **707,896**（逐表 `COUNT(*)` 累加，与 `initial_state_rules.json._meta.table_inventory` 完全一致） |
| SQL 主键 | **398 张表全部没有声明 PRIMARY KEY**（`sqlite_master.sql` 里 `PRIMARY KEY` 出现 0 次；`PRAGMA table_info` 的 `pk` 列全为 0）。每张表都是 `(逻辑键列..., Bytes BLOB)` 形态。本文件的「SQL 主键/关键列」一律指**逻辑键列**，并已实测其唯一性 |
| 抓包目录 | `report\_tmp\official_decoded_201\`，109 对 `.request.json`/`.response.json`；`meta.resp_bytes` 为真实字节数，`inner` 为解析后 JSON |
| 规则文件 | `work\ba\proto\initial_state_rules.json`（UTF-8，用 Python `json.load(..., encoding='utf-8')` 读取） |
| 协议映射 | `work\ba\proto\protocol_map.json`（501 条；协议 3 不在其中） |

### 关于 5 个来源类别的两点口径说明（必读，否则会误读第 3 节）

1. **`echo` 的边界**：这 5 个类别里没有「动态时间戳」这一类。凡「每个包重算、不查任何表、也不来自玩家存档」的字段 —— 服务器 `now()`、回显请求里的 tick、const 开关/版本号、纯信封空响应 —— 本文件一律归 `echo`，并在「具体来源」列注明是 **const** 还是 **now()/回显**。这是 5 类里唯一能表达「无持久化来源」的类别，不是为了凑数。
2. **一个协议的一个字段只给一个类别**，但当该字段同时依赖静态表 + 玩家存档时，「具体来源」列会写全两者，并以主类别排在前面。

---

## 第 1 步：表存在性 + 行数核实

核对方法：先取全部 398 个表名，对 48 个候选做**精确匹配 → 去后缀（`DBSchema`/`Excel`/`Schema`）子串模糊匹配 → 关键词族扫描**三级查找。命中的写真实表名与真实行数；族表（一张候选对应多张真实表）把整族列出。

### 1.1 精确命中（33 个）

| # | 候选表 | 是否存在 | 行数 | 逻辑键 / 关键列（实测唯一性） | 相关协议 |
|---|---|---|---|---|---|
| 1 | `CurrencyDBSchema` | ✅ 存在 | **29** | `ID` = 1..29，29 个值全唯一 | 1017 `AccountCurrencySyncResponse`；所有 `ParcelResultDB.AccountCurrencyDB.CurrencyDict`（6020/6021/8002/20013/22004/22008/22009）的 **key 集合** |
| 2 | `ItemDBSchema` | ✅ 存在 | **1803** | `Id`（1 .. 2000000003），1803 唯一 | 4000 `Item_List`；1017 `ItemListResponse`；8002/22009 的 `ItemDBs` |
| 3 | `EquipmentDBSchema` | ✅ 存在 | **191** | `Id`（1..109009），191 唯一 | 1017 `EquipmentItemListResponse.EquipmentDBs` |
| 4 | `CharacterDBSchema` | ✅ 存在 | **7223** | `Id`（10000..838060812），7223 唯一；另有冗余列 `ProductionStep`、`MainCombatStyleId` | 1017 `CharacterListResponse.CharacterDBs`；22004 队伍快照 |
| 5 | `CharacterLevelDBSchema` | ✅ 存在 | **90** | `Level` = 1..90，90 唯一 | 角色等级/经验曲线（不是账号等级；账号等级见 #29） |
| 6 | `EchelonConstraintDBSchema` | ✅ 存在 | **4** | `GroupId` 有 4 行但只有 **3 个不同值**（10002 出现 2 次、10003、99999）→ 复合键，非单键 | 5000 `Echelon_List` / 5001 `Echelon_Save` 的编队合法性约束 |
| 7 | `ShopDBSchema` | ✅ 存在 | **7908** | `Id`（21..21100170），7908 唯一；冗余列 `CategoryType` 共 **15** 种取值 | 10002 `Shop_List`（`CategoryType=38` → 恰好 **2** 行：Id 201、202） |
| 8 | `ShopInfoDBSchema` | ✅ 存在 | **18** | `CategoryType`（0,1,2,3,4,9,10,20,21,25,26,27,28,29,33,36,37,38），18 唯一 | 10002 `ShopInfos` 的分类定义 |
| 9 | `ShopRecruitDBSchema` | ✅ 存在 | **532** | `Id`（1..99999999），532 唯一 | 1017 `ShopGachaRecruitListResponse.ShopRecruits`；**532 − {1,2,3} = 529** 与官方条数完全相等 |
| 10 | `CafeInfoDBSchema` | ✅ 存在 | **2** | `CafeId` = 1、2 | 20001 `Cafe_Ack` / 20013 `Cafe_ReceiveCurrency` / 1017 `CafeGetInfoResponse` |
| 11 | `CafeRankDBSchema` | ✅ 存在 | **20** | 复合键 `CafeId`+`Rank`（CafeId 只 1/2，各 10 档 Rank）→ 单列不唯一 | 同上，`CafeRank` 上限曲线 |
| 12 | `CafeProductionDBSchema` | ✅ 存在 | **30** | `CafeId` | 20001 `CafeDB.ProductionDB` |
| 13 | `FurnitureDBSchema` | ✅ 存在 | **876** | `Id` | 20001/20013 `FurnitureDBs`；1017 `CafeGetInfoResponse` |
| 14 | `AcademyLocationDBSchema` | ✅ 存在 | **11** | `Id` = **1, 7, 11, 12, 13, 14, 15, 16, 17, 18, 19**（不是 1..11） | 24000 `Academy_GetInfo.AcademyLocationDBs` |
| 15 | `AcademyLocationRankDBSchema` | ✅ 存在 | **12** | `Rank` = 1..12 | 24000 `Rank` 升级曲线（ExpDelta/ExpTotal） |
| 16 | `AcademyZoneDBSchema` | ✅ 存在 | **95** | `Id`（1..127），95 唯一 | 24000 `AcademyDB.ZoneVisitCharacterDBs` 的 zone 键空间 |
| 17 | `AcademyTicketDBSchema` | ✅ 存在 | **5** | `LocationRankSum` = 1, 10, 25, 50, 80 | 24000 按学院总 Rank 发券 |
| 18 | `AcademyFavorScheduleDBSchema` | ✅ 存在 | **1053** | `Id`（100002..2600515），1053 唯一；冗余列 `ScheduleGroupId` | 24000 `AcademyDB.ZoneScheduleGroupRecords`；24002 `Academy_AttendFavorSchedule` |
| 19 | `MissionDBSchema` | ✅ 存在 | **3444** | `Id`（1000..410012），3444 唯一 | 8000 / 8002 / 8006 / 35003 / 6021 / 22004 的 `MissionProgressDBs` |
| 20 | `GuideMissionSeasonDBSchema` | ✅ 存在 | **20** | `Id` = {1..16, 1000, 1001, 2000, 100000} | 8006 `GuideMissionSeasonDBs`（响应只 17 季 = 该号进度） |
| 21 | `CampaignChapterDBSchema` | ✅ 存在 | **29** | `Id` = 101..129 | 6000 `Campaign_List`；1017 `CampaignListResponse` |
| 22 | `CampaignStageDBSchema` | ✅ 存在 | **407** | `Id`（1011101..1292103），407 唯一 | 6000 `StageHistoryDBs`；6021 `CampaignStageHistoryDB` |
| 23 | `ScenarioModeDBSchema` | ✅ 存在 | **581** | `ModeId`（1101..90002260），581 唯一 | 1017 `ScenarioListResponse` |
| 24 | `OpenConditionDBSchema` | ✅ 存在 | **54** | `OpenConditionContentType`（0..57 中 54 个值），54 唯一 | 15002 `OpenCondition_EventList`；1002 `OpenConditions` |
| 25 | `TutorialDBSchema` | ✅ 存在 | **33** | `ID` = {1..27} ∪ {1011301,1011302,1011303,1021304,1031305,1031306} | 1005 `Account_GetTutorial.TutorialIds` |
| 26 | `EmblemDBSchema` | ✅ 存在 | **1065** | `Id`（1..900000003），1065 唯一 | 1017 `AttachmentEmblemListResponse.EmblemDBs`；`AttachmentGetResponse` |
| 27 | `AccountLevelDBSchema` | ✅ 存在 | **90** | `Id` = 1..90 | 账号等级经验表（1002 `AccountDB.Level`、6021 `BaseAccountExp/AdditionalAccountExp`） |
| 28 | `AccountLevelRewardDBSchema` | ✅ 存在 | **6** | `Id` = 1..6；冗余列 `Level` = **30, 40, 45, 50, 55, 60** | 1017 `AccountLevelRewardIds`（= 表中 `Level ≤ 账号等级` 的 Id；Lv32 → 只有 Id=1，官方值正是 `[1]`） |
| 29 | `TimeAttackDungeonDBSchema` | ✅ 存在 | **4** | `Id` = 1000, 2000, 3000, 4000 | 1017 `TimeAttackDungeonLoginResponse`（配套 `TimeAttackDungeonSeasonManageDBSchema` 13 行，SeasonId 4..13…） |
| 30 | `MemoryLobbyDBSchema` | ✅ 存在 | **258** | `Id`（10000..2300501），258 唯一 | 1017 `MemoryLobbyListResponse.MemoryLobbyDBs`（初始 1 条 `Type:8, MemoryLobbyUniqueId:13010`；13010 在表内 ✅） |
| 31 | `ToastDBSchema` | ✅ 存在 | **98** | `Id` | 16000 `Toast_List.ToastDBs`（响应为 `null` = 当前无新 toast；98 行是模板池） |

### 1.2 候选名不存在、但模糊匹配到真实表（族表，11 个）

| # | 候选表 | 存在性 | 命中的真实表（行数 / 关键列） | 相关协议 |
|---|---|---|---|---|
| 32 | `CharacterSkillDBSchema` | ❌ 精确名不存在 | **`CharacterSkillListDBSchema`** 6708 行（复合键 `CharacterSkillListGroupId` + `MinimumGradeCharacterWeapon` + `MinimumTierCharacterGear` + `FormIndex` + `TSAInteractionId`，6 列）<br>配套 **`SkillDBSchema`** 18028 行（键 `GroupId`+`Level`） | 1017 `CharacterListResponse` 的 `ExSkillLevel/PassiveSkillLevel/PublicSkillLevel` 定义侧 |
| 33 | `AttendanceBookDBSchema` | ❌ 精确名不存在 | **`AttendanceDBSchema`** 31 行（`Id` = 1..12… 含 28）<br>**`AttendanceRewardDBSchema`** 334 行（`AttendanceId`） | 1002 `AttendanceHistoryDBs`（含 `AttendanceBookUniqueId: 28` → `AttendanceDBSchema.Id=28` 存在 ✅）、`AttendanceBookRewards` |
| 34 | `RaidDBSchema` | ❌ 精确名不存在（`/^Raid/` 7 张，全为子表） | `RaidStageDBSchema` 156 / `RaidSeasonManageDBSchema` 78 / `RaidStageRewardDBSchema` 161 / `RaidRankingRewardDBSchema` 265 + `RaidStageSeasonRewardDBSchema` / `RaidRankingRewardUODBSchema` / `RaidContentPlayGuideDBSchema`(2) | 1017 `RaidLoginResponse` |
| 35 | `EventContentDBSchema` | ❌ 精确名不存在（`EventContent*` 共 **58** 张） | **`EventContentSeasonDBSchema`** 412 行 / **125** 个不同 `EventContentId`，键是 `EventContentId`+`EventContentType`（复合，单列不唯一）<br>`EventContentStageDBSchema` 2353（Id+EventContentId）<br>`EventContentCharacterBonusDBSchema` 2172（EventContentId+CharacterId） | 25003、30041、36001、15002、1017 `EventContentPermanentListResponse` |
| 36 | `ArenaDBSchema` | ❌ 精确名不存在（`/^Arena/` 6 张） | `ArenaSeasonDBSchema` 9（`UniqueId` 1..9）/ `ArenaMapDBSchema` 60（`UniqueId`，含 1001 ✅）/ `ArenaNPCDBSchema` 13 / `ArenaRewardDBSchema` 108 / **`ArenaSeasonCloseRewardDBSchema` 0 行（空表！）** / `ArenaLevelSectionDBSchema` | 22000 / 22004 / 22008 / 22009（`ArenaLoginResponse`） |
| 37 | `ClanDBSchema` | ❌ 精确名不存在（`/Clan/` 只 2 张） | `ClanRewardDBSchema` 1 行（`ClanRewardType`）/ `ClanChattingEmojiDBSchema` 176（`Id`）—— **公会本体、成员、聊天均无静态表** | 28000 `Clan_Lobby`、28019 `Clan_Check`、90009 `Clan_Chat_Records` |
| 38 | `MultiFloorRaidDBSchema` | ❌ 精确名不存在（4 张子表） | `MultiFloorRaidStageDBSchema` 744（`Id`+`BossGroupId`）/ `MultiFloorRaidSeasonManageDBSchema` 18 / `MultiFloorRaidRewardDBSchema` / `MultiFloorRaidStatChangeDBSchema` | 1017 `MultiFloorRaidSyncResponse` / `MultiFloorRaidLoginResponse` |
| 39 | `EliminateRaidDBSchema` | ❌ 精确名不存在（7 张子表） | `EliminateRaidStageDBSchema` 490 / `EliminateRaidSeasonManageDBSchema` 27 + 5 张 Rank/Reward 子表 | 1017 `EliminateRaidLoginResponse` |
| 40 | `StickerDBSchema` | ❌ 精确名不存在（`/Sticker/` 只 2 张） | `StickerGroupDBSchema` 3（`Id` = 100,101,102）/ `StickerPageContentDBSchema` 23（`Id`） | 1017 `StickerListResponse`；90009 `ChatRecords.StickerId` |
| 41 | `MinigameDBSchema` | ❌ 精确名不存在（`MiniGame*` / `Minigame*` 共 **60** 张） | 无「总表」：按玩法分族（Defense 5 / Dream 13 / CCG 15 / RoadPuzzle 5 / Shooting 3 / TBG 8 / Rhythm 2 …）。35003 只用到 `MiniGameMissionDBSchema` + `MissionDBSchema` | 35003 `MiniGame_MissionList` |
| 42 | `CraftDBSchema` | ❌ 精确名不存在（`/Craft/` 4 张） | `GachaCraftNodeDBSchema` 141（`ID`）/ `GachaCraftNodeGroupDBSchema` 291（`NodeId`）/ `GachaCraftOpenTagDBSchema` 3（`NodeTier`）/ `ShiftingCraftRecipeDBSchema` 87（`Id`）/ 另有 `RecipeDBSchema` 6973 | 1017 `CraftInfoListResponse`（官方响应是空数组） |
| 43 | `WorldRaidDBSchema` | ❌ 精确名不存在（`WorldRaid*` 6 张 + `InteractiveWorldRaid*` 10 张） | `WorldRaidStageDBSchema` 103（`Id`+`WorldRaidBossGroupId`）/ `WorldRaidSeasonManageDBSchema` 5（`SeasonId`）/ `WorldRaidBossGroupDBSchema` 21 / `WorldRaidConditionDBSchema` 5 / `WorldRaidFavorBuffDBSchema` 150 | 1017 `RaidLoginResponse`（`SeasonType`）；无独立协议 |

### 1.3 未找到（4 个 —— ExcelDB 398 张表里确实没有，写「未找到」）

| # | 候选表 | 结论 | 关键词扫描证据 | 相关协议 |
|---|---|---|---|---|
| 44 | **`MissionDBSchema` 以外的 `MissionCategoryDBSchema`** | **未找到** | `/Mission/` 8 张：`BattlePassMission`、`EventContentMission`、`GuideMission`、`GuideMissionOpenStageCondition`、`GuideMissionSeason`、`MiniGameMission`、`Mission`、`MissionEmergencyComplete`。**没有任何 Category/Categor 表**（`/Categor/` 全库 0 命中）。`Category` 是 `MissionDBSchema.Bytes` 里的一个字段（响应里取到 1/4/7/8），分类**没有独立表** | 8000 `Mission_List`、8002 |
| 45 | **`MailDBSchema`** | **未找到** | `/Mail/` 全库 **0 命中**（398 表名里一个 Mail 都没有） | 7000 / 7001 / 7003 —— 邮件**完全**是玩家存档；模板只在 `Excel.zip!defaultmailexceltable.bytes`(1 行) / `systemmailexceltable.bytes`(29 行)，**不在 ExcelDB** |
| 46 | **`EventRewardIncreaseDBSchema`** | **未找到** | `/Increase/`、`/RewardIncrease/` 全库 **0 命中** | 25003 `Event_RewardIncrease` —— 语义最接近的是 `EventContentCharacterBonusDBSchema`（2172 行，EventContentId+CharacterId，活动角色加成），但**无法证实**它就是 `EventRewardIncreaseDBs` 的来源 |
| 47 | **`ContentSweepDBSchema`** | **未找到** | `/Sweep/`、`/Sweepable/` 全库 **0 命中** | 1017 `ContentSweepMultiSweepPresetListResponse`、35003 —— 语义最接近的是 **`TacticSkipDBSchema`** 21 行（键 `LevelDiff`，即「战力差 → 可跳过/扫荡」档位表），但**无法证实**它就是扫荡配置 |
| 48 | **`AttachmentDBSchema`** | **未找到** | `/Attachment/` 全库 **0 命中** | 1017 `AttachmentGetResponse` / `AttachmentEmblemListResponse` —— Attachment 只有 `AccountAttachmentDB{AccountId, EmblemUniqueId}` 一个字段，来源是玩家存档 + `ConstCommonExcel.EmblemDefaultId=1`，**没有静态表** |

> 补充事实（会影响第 3 节判定）：**`ArenaSeasonCloseRewardDBSchema` 是 0 行空表**，所以 22004 `SeasonRewards` 不可能是查表得出的固定内容。

---

## 第 2 步：`initial_state_rules.json` 结论摘录

原文（`_meta.key_discovery`）的核心结论：**初始状态规则不在 `ExcelDB.db` 里，在 `Excel.zip` 的 77 个 `*.bytes` 里**。ExcelDB 398 张表已全量核过，无 Initial/Default/Start/Newbie 类表名。

### 2.1 十问 + other_initial_state + not_found 结论表

| 数据项 | 初始值 / 规则 | 来自哪里 |
|---|---|---|
| **q1 初始角色** | 4 个：优香 `13010`(★2)、铃美 `16003`(★1)、莲见 `13003`(★2)、千夏 `26000`(★1) | `Excel.zip!defaultcharacterexceltable.bytes`（312 B，4 行），slot0=`CharacterId`；与 `constcommonexceltable.bytes.TutorialCharacterDefaultCount=4` 互证 |
| **q2 初始星级/等级/技能** | `Level=1`、`Exp=0`、`FavorRank=1`、`FavorExp=0`、`ExSkillLevel=1`、`PassiveSkillLevel=1`、`ExtraPassiveSkillLevel=1`、`CommonSkillLevel=1`、`LeaderSkillLevel=1`；`StarGrade` 按角色 2/1/2/1；`FavoriteCharacter` 只有 13003=true（medium） | 同上表 12 个 slot（字段名来自 `metadata-strings.txt` 行 62318-62339 的 12 个 `Add*`）；等级上限参考 `ConstCommonExcel.CharacterMaxLevel=90` + `CharacterLevelDBSchema`(90) |
| **q3 初始道具** | `ItemDBs` = 1 行：`{Type:4, ItemId:2(加速券), amount:5}`；`EmblemDBs` = 5 行 `Type:20`、`UniqueId 1..5`、各 1 个；`EquipmentDBs = []` | `Excel.zip!defaultparcelexceltable.bytes`（744 B，25 行）里 `ParcelType=4` 的 1 行 + `ParcelType=20` 的 5 行；ParcelType 枚举 `Character=1/Equipment=3/Item=4` 来自 `_intel_ba_sniff_FINDINGS.md` 实测 |
| **q4 初始货币** | 发放 19 种：`1:10000, 3:600, 5:24, 6:3, 7:5, 8:3, 17:3, 18:0, 19:40, 20:40, 21:40, 22:6, 23:6, 24:1, 25:1, 26:1, 27:1, 28:0, 29:0`；另 `2,4,9..16` 共 10 种**必须仍出现在 `CurrencyDict` 里且 =0**（合计 29 键） | 同上表 `ParcelType=2` 的 19 行，`ParcelId` = `CurrencyDBSchema.ID`(1..29)。交叉验证：官方正式号 11 项精确命中（8/17/19/20/21/22/23/24/25/26/27），且官方 `CurrencyDict` 键恰为 `"1".."29"` 共 29 个 |
| **q5 初始编队** | **1 条**：`EchelonType=1, EchelonNumber=1, ExtensionType=0`；Leader=13010；主槽 `[13010,16003,13003,0]`（4 格）；支援槽 `[26000,0]`（2 格）；`SkillCardMulliganCharacterIds=[0,0,0]`、`CombatStyleIndex=[0×6]`、`TSSInteractionServerId=0`、`UsingFlag=0` | `Excel.zip!defaultechelonexceltable.bytes`（112 B，1 行，字段 `EchlonId/LeaderId/MainId[]/SupportId[]/TssId`）。4 主槽 + 2 支援槽的形状来自官方 `EchelonListResponse.EchelonDBs` 每条形状（不是抄值）。`EchelonConstraintDBSchema`(4 行) 是编队约束，**不是**初始条数 |
| **q6 剧情进度** | `ScenarioHistoryDBs = []`、`ScenarioGroupHistoryDBs = []`、`ScenarioCollectionDBs = []`；序章 `11000/11002` **不写进 history** | `ConstCommonExcel.PrologueScenarioID01=11000 / PrologueScenarioID02=11002`；官方向量 191 条 history 里 11000/11002 都不存在（实测 False）。`ScenarioModeDBSchema`(581) 是模式配置，不含账号解锁 |
| **q7 教程** | `TutorialIds = []`（`TutorialDBSchema` 33 行只是定义表，不是进度） | `TutorialDBSchema` 33 行 = 27 基础 ID + 6 活动 ID（1011301..1031306）；官方 1005 返回 21 条是 27 的**真子集**（缺 15/18/20/24/25/26）→ 只能是进度 |
| **q8 学院** | `Rank = 1`、`Exp = 0`（high）；**「初始几条」= 未找到**；官方 9 条 vs 表 11 条（缺 14/18）**原因未找到**（两个候选解释都无证据闭合） | `AcademyLocationDBSchema` f8 全表恒为 1 → 默认 Rank=1；无 per-location 经验字段 → Exp=0；`AcademyLocationRankDBSchema`(12) 是升级曲线。⚠️ 陷阱：1017 的 `AcademyLocationRankSum=1` 是默认值模板，**不能**用来推「新号只有 1 个地点」（24000 实测 9 条 Rank 之和 = 14，矛盾） |
| **q9 咖啡厅** | **2 个 Café**（`CafeId=1,2`），各 `CafeRank=1`，各带**同一套 11 件**默认家具（`FurnitureId 1..11`，含 Location/Position/Rotation），`LastSummonDate = 0001-01-01T00:00:00`；`CafeDBId = AccountServerId*10 + CafeId` | `CafeInfoDBSchema`(2 行) 定 2 个 Café；`Excel.zip!defaultfurnitureexceltable.bytes`(392 B, 11 行) 定 11 件；`CafeRankDBSchema`(20 = 2×10) 最低 Rank=1。**决定性反证**：官方 `CafeId=2`（Rank 1、从未召唤）家具 UniqueId **恰好 [1..11]** |
| **q10 商店可见性** | `ShopRecruits` = **`ShopRecruitDBSchema` 全部 532 行排除 `Id ∈ {1,2,3}` = 529 条**；日期字段原样下发**不做时间过滤**；`ShopFreeRecruitHistoryDBs = []` | `ShopRecruitDBSchema` 532 行（532 个唯一 Id）；官方 529 条。集合差 `DB−官方 = {1,2,3}`、`官方−DB = {}` 精确闭合。`ShopFreeRecruit` 是另一套表（8 + 67 行） |
| **other · MemoryLobby** | 1 条：`{Type:8, MemoryLobbyUniqueId:13010}`（medium，Type=8 的枚举含义未在 ExcelDB 找到） | 官方向量 `MemoryLobbyListResponse.MemoryLobbyDBs` 只有 1 条；13010 = 优香 = 初始 Leader |
| **other · IdCard** | `CharacterId=13003`（莲见）、`BackgroundId=1` | `ConstCommonExcel.IdCardDefaultCharacterId=13003`、`IdCardDefaultBgId=1`；`IdCardBackgroundDBSchema` 17 行 |
| **other · Emblem** | 拥有 `1..5`，装备 `1` | 拥有 ← DefaultParcelExcel 的 5 行 Type=20；装备 ← `ConstCommonExcel.EmblemDefaultId=1`（与官方 `EmblemUniqueId=1` 一致） |
| **other · 默认邮件** | **未完全解出**：确定是「**1 封**带 3 个向量参数的初始邮件」，向量值 `[2] / [3] / [1200]` | `Excel.zip!defaultmailexceltable.bytes`（176 B，1 行，解出 8 个 slot）。metadata 只 6 个字段名，与 8 slot 数量不符，且日期字段是字符串 → 映射未闭合，不猜 |
| **not_found ①** | ExcelDB 里的「初始/默认」表 → **不存在**（398 表全量核过） | 规则在 `Excel.zip` 的 `*.bytes` |
| **not_found ②** | 学院 `AcademyLocationDBs` 初始条数 → **未找到** | ExcelDB 与 Excel.zip 都无「新号建几个学院地点」的规则表 |
| **not_found ③** | 学院 14(Trinity)/18(Shanhaijing) 为何不在官方响应 → **未找到确定规则** | 两个候选解释（客户端数据更新 / 按首次进入建行）都无法闭合 |
| **not_found ④** | ParcelType 完整数值表 → **部分找到**（Character=1/Equipment=3/Item=4 实测；Currency=2、Emblem=20 反推 high；5/6/8… 未找到） | 见 q3/q4 证据 |
| **not_found ⑤** | DefaultMailExcel 字段完整语义 → **未完全解出** | 6 字段名 vs 8 slot |
| **not_found ⑥** | 新号 AccountLevel / 经验 / 首日任务进度 → 当时范围外；顺带记 `AccountLevelDBSchema`(90)、`AccountLevelRewardDBSchema`(6，Lv 30/40/45/50/55/60) | —— |

### 2.2 「新号应该有哪些行」——直接答案

| 存档集合 | 新号行数 | 内容出处 |
|---|---|---|
| `CharacterDBs` | **4** | DefaultCharacterExcel（13010/16003/13003/26000，Lv1，星 2/1/2/1，技能全 1） |
| `ItemDBs` | **1** | DefaultParcelExcel (Type=4, Id=2, ×5) |
| `EquipmentDBs` | **0** | DefaultParcelExcel 无 ParcelType=3 行 |
| `EmblemDBs` | **5** | DefaultParcelExcel (Type=20, Id 1..5) |
| `AccountCurrencyDB.CurrencyDict` | **29 键**（19 个非零/显式 0 + 10 个补 0） | DefaultParcelExcel + CurrencyDBSchema 的 ID 空间 |
| `EchelonDBs` | **1** | DefaultEchelonExcel |
| `CafeDBs` | **2** | CafeInfoDBSchema |
| `FurnitureDBs` | **11 × 2**（每个 Café 一份） | DefaultFurnitureExcel |
| `MemoryLobbyDBs` | **1** | 官方向量 + 13010 |
| `AccountAttachmentDB` | **1** 行 | ConstCommonExcel.EmblemDefaultId=1 |
| `Scenario*DBs` | **0** | ConstCommonExcel（序章不落库） |
| `TutorialIds` | **0** | TutorialDBSchema 只是定义 |
| `ShopRecruits` | **529**（静态下发，不是存档） | ShopRecruitDBSchema − {1,2,3} |
| `ShopFreeRecruitHistoryDBs` | **0** | —— |
| `MailDBs` | **0 或 1** | DefaultMailExcel（1 封，语义部分未解出） |
| `AcademyLocationDBs` | **未找到**（建议最小实现 1 条 LocationId=1/Rank1/Exp0，待验证） | —— |
| `MissionProgressDBs` / `ProgressDBs` | **未找到**（initial_state_rules 的 10 问不含任务首日进度） | **本文件第 3 节用响应实测补了一条线索，见 §3.8000 备注** |

---

## 第 3 步：逐协议数据来源判定（38 个）

约定：每节标题格式 `### 协议号 名称（resp_bytes / 文件数）`；表内一行一个业务字段。`inner` 里始终只有 6 个信封字段 `Protocol / SessionKey / ServerTimeTicks / ServerNotification / RequestId`（已剔除），下表只列**业务字段**。

### 3.0 先看这一节：两层判定 + 38 协议总览

**两层逻辑（很重要，否则会以为 `initial_state` 没被用到）**

- 第 1 层「**存放位置**」= 每张字段表里的 `来源类别`：这类数据在服务端**存在哪里**（静态表 / 存档 / 运营配置 / 不存）。
- 第 2 层「**新号取值**」= 下表 `新号（initial_state 决定的部分）` 列：该字段在**全新账号**上完全由 `initial_state_rules.json` 的规则表决定时，这里写 `initial_state` + 具体值/条数。

所以同一个字段完全可以是「`player_progress`（存放位置）」而「新号 = `initial_state`（4 个角色）」。第 1 层回答「私服要建哪些表」，第 2 层回答「新号要写哪些行」。

| 协议 | 名称 | B / 文件 | 字段数 | 第 1 层：主来源类别 | 第 2 层：新号由 `initial_state` 决定的字段（值 / 条数） |
|---|---|---|---|---|---|
| `3` | NetworkTime_Sync | 620 / 1 | 2 | `echo` | ——（纯时间戳） |
| `1002` | Account_Auth | 5056 / 1 | 27 | `player_progress` + `official_config` | `AccountDB`(Level=1, Exp=0, UnReadMailCount=0, LastReturningDate=默认)、`AttendanceBookRewards=[]`、`AttendanceHistoryDBs=[]`、`MonthlyProduct*/WeeklyProduct*/BiweeklyProduct*`=None/[]、`OptionDB`=默认、`AccountRestrictionsDB`=全 false |
| `1005` | Account_GetTutorial | 640 / 1 | 1 | `player_progress` | `TutorialIds = []` |
| `1017` | Account_LoginSync | 246808 / 1 | **30** | 混合（**26 个 `player_progress`** + 1 `exceldb_static` + 3 `official_config`） | `CharacterListResponse`=**4** 角色(13010★2/16003★1/13003★2/26000★1，Lv1 技能全 1)、`AccountCurrencySyncResponse`=**29 键**（19 值）、`EchelonListResponse`=**1** 条、`CafeGetInfoResponse`=**2** Café × **11** 家具、`MemoryLobbyListResponse`=**1** 条(8/13010)、`AttachmentEmblemListResponse`=**5** 条(20/1..5)、`AttachmentGetResponse`=`EmblemUniqueId:1`、`ItemListResponse`=**1** 行(Type4/Id2/×5)、`EquipmentItemListResponse`=`[]`、`CharacterGearListResponse`=`[]`、`CampaignListResponse`=全 `[]`、`ScenarioListResponse`=3×`[]`、`CraftInfoListResponse`=全空、`MomoTalkOutLineResponse`=空、`ContentSweepMultiSweepPresetListResponse`=`[]`、`StickerListResponse`=空、`FriendCount=0`、`AccountLevelRewardIds=[]`（Lv1 < 表最低 Level 30） |
| `4000` | Item_List | 16088 / 1 | 2 | `player_progress` | `ItemDBs`=**1** 行 `{Type:4, UniqueId:2, StackCount:5}`、`ExpiryItemDBs=[]` |
| `5000` | Echelon_List | 4120 / 4 | 1 | `player_progress` | `EchelonDBs`=**1** 条（type1/num1/ext0，主槽 `[13010,16003,13003,0]`、支援 `[26000,0]`） |
| `5001` | Echelon_Save | 984-1004 / 2 | 1 | `echo` | ——（新号不会调用） |
| `6000` | Campaign_List | 44672 / 1 | 3 | `player_progress` | 三字段 = `[]` / `[]` / `CurrentScenarioId=0` |
| `6020` | Campaign_EnterMainStageStrategySkip | 2072 / 1 | 1 | `player_progress` | ——（新号不会调用） |
| `6021` | Campaign_MainStageStrategySkipResult | 10284 / 1 | 7 | `player_progress` + `exceldb_static` | ——（新号不会调用） |
| `7000` | Mail_List | 1600 / 1 | 2 | `player_progress` | `MailDBs`=**0 封，或 1 封** DefaultMailExcel 邮件；`Count` 同值 |
| `7001` | Mail_Check | 556 / 9 | 1 | `player_progress` | `Count`=**0**（或无默认邮件时 1） |
| `7003` | Mail_ListSemiPermanent | 556 / 1 | **0** | `echo`（const 空响应） | —— |
| `8000` | Mission_List | 268396 / 3 | 5 | `player_progress` | **`ProgressDBs` 首日条数 = 未找到**；`HistoryDBs=None`、`MissionHistoryUniqueIds=[]`、`ClearedOriginalMissionIds=[]`；`DailySuddenMissionInfo=1606`（静态） |
| `8002` | Mission_MultipleReward | 8320 / 1 | 3 | `player_progress` | ——（新号不会调用） |
| `8006` | Mission_GuideMissionSeasonList | 160216 / 1 | 2 | `player_progress` | `MissionProgressDBs`/`GuideMissionSeasonDBs` 新号条数 = **未找到**（推测只有当前 1 季） |
| `10002` | Shop_List | 1304 / 1 | 2 | `exceldb_static` | `ShopInfos`=默认开放分类（官方只 1 个 Category 38 → **2** 件商品 201/202）、`ShopEligmaHistoryDBs=[]` |
| `15002` | OpenCondition_EventList | 600 / 1 | 1 | `player_progress` | `ConquestTiles = {50822: []}` |
| `16000` | Toast_List | 556 / 1 | 1 | `player_progress` | `ToastDBs = null` |
| `20001` | Cafe_Ack | 5016 / 1 | 1 | `player_progress` | `CafeDB`=`CafeId:1, CafeRank:1, 11 件默认家具, LastSummonDate=0001-01-01`（新号一般不主动 Ack） |
| `20013` | Cafe_ReceiveCurrency | 11136 / 1 | 2 | `player_progress` | ——（新号首日可调用；产出量由 `CafeProductionDBSchema`(30)+舒适度算，**初值未找到**） |
| `22000` | Arena_EnterLobby | 9068 / 2 | 5 | `player_progress` + `official_config` | `ArenaPlayerInfoDB`（`CurrentRank=0/SeasonRecord=0` 全默认）、`MapId=1001`（静态）；`OpponentUserDBs` 由服务端生成 |
| `22004` | Arena_EnterBattle | 67180 / 1 | 9 | `player_progress` | ——（新号不会调用） |
| `22008` | Arena_CumulativeTimeReward | 3072 / 1 | 3 | `player_progress` | `TimeRewardAmount=0` |
| `22009` | Arena_DailyReward | 3224 / 1 | 2 | `player_progress` | ——（新号需先打过竞技场） |
| `22016` | Arena_SyncEchelonSettingTime | 640 / 1 | 1 | `echo` | ——（纯时间戳） |
| `24000` | Academy_GetInfo | 17560 / 2 | 2 | `player_progress` | `AcademyLocationDBs` 每条 `Rank=1/Exp=0`；**条数 = 未找到**；`AcademyDB`=`{}` 或空数组 zone |
| `25003` | Event_RewardIncrease | 792 / 21 | 1 | `official_config` | ——（运营活动，新号也照发） |
| `26000` | ContentSave_Get | 640 / 1 | 3 | `player_progress` | `HasValidData=False`、`ContentSaveDB=None`、`EventContentChangeDB=None` |
| `28000` | Clan_Lobby | 35864 / 1 | 4 | `player_progress` | 4 字段全 `None` / `[]`（新号未入会） |
| `28019` | Clan_Check | 536 / 8 | **0** | `echo`（const 空响应） | —— |
| `29002` | Billing_PurchaseListByYostar | 1280 / 3 | 3 | `player_progress` | `CountList=[]`、`OrderList=[]`、`MonthlyProductList=[]` |
| `30041` | EventContent_PermanentList | 2156 / 1 | 1 | `official_config` | `PermanentDBs`=**22 条**，每条 `IsStageAllClear=False` |
| `35003` | MiniGame_MissionList | 4480 / 1 | 3 | `player_progress` | `MissionHistoryUniqueIds=[]`；`ProgressDBs` 首日条数 = **未找到**；`ClearedOrignalMissionIds=None` |
| `36001` | Notification_EventContentReddotCheck | 1088 / 10 | 2 | `player_progress` + `official_config` | `Reddots={}`；`EventContentUnlockCGDBs`=**25 个键**、值全 `[]` |
| `43010` | Friend_Check | 536 / 8 | **0** | `echo`（const 空响应） | —— |
| `90004` | Management_Data | 14124 / 10 | 1 | `official_config` | ——（公告/banner 与账号无关，新号同内容） |
| `90009` | Clan_Chat_Records | 30316 / 2 | 1 | `player_progress` | `ChatRecords = []` |

**统计（38 个协议，按第 1 层主导类别）**：`player_progress` 主导 **26** 个（1002/1005/4000/5000/6000/6020/6021/7000/7001/8000/8002/8006/15002/16000/20001/20013/22004/22008/22009/24000/26000/28000/29002/35003/36001/90009）；`exceldb_static` 主导 **1** 个（10002）；`official_config` 主导 **3** 个（25003/30041/90004）；`echo` 主导 **6** 个（3/5001/22016 + 3 个纯空响应 7003/28019/43010）；真正「没有单一主导类别」的混合包 **2** 个（1017、22000）。

---

### `3` NetworkTime_Sync（620 B / 1 个响应；**不在 protocol_map.json 里**，按文件名 `04_3_api_networktime_sync` 识别）

| 响应字段 | 来源类别 | 具体来源 |
|---|---|---|
| `ReceiveTick` | `echo` | **now()**：服务端收到包时的 `DateTime.Ticks`（实测 639304002554622693） |
| `EchoSendTick` | `echo` | **回显**：原样返回请求里的 `SendTick`（实测与 `ReceiveTick` 同值） |

---

### `1002` Account_Auth（5056 B / 1 个响应，**27 个业务字段**）

| 响应字段 | 来源类别 | 具体来源 |
|---|---|---|
| `IsNew` | `player_progress` | 账号是否首次登录（官方 `False`）；新号首次 = `True` |
| `CurrentVersion` / `MinimumVersion` | `echo` | **const**：协议/客户端版本号，实测均为 `1` |
| `IsDevelopment` / `BattleValidation` / `UpdateRequired` | `echo` | **const** 开关，实测 `False/False/True` |
| `TTSCdnUri` | `official_config` | 运营下发的 CDN 前缀（实测空串） |
| `AccountDB` | `player_progress` | 账号存档行；新号按 `server_apply_skeleton` 建。字段 `ServerId/RoleId/Nickname/Level/Exp/RepresentCharacterServerId/UnReadMailCount/Location/LastReturningDate` 全靠存档；36 个字段里的 `CreateDate` = 创建时刻 |
| `AttendanceBookRewards` | `player_progress` | 签到未领奖励；新号 `[]`（ID 空间来自 `AttendanceDBSchema`(31) + `AttendanceRewardDBSchema`(334)） |
| `AttendanceHistoryDBs` | `player_progress` | 签到历史（官方 2 条，`AttendanceBookUniqueId=28` 在 `AttendanceDBSchema.Id` 中存在 ✅）；新号 `[]` |
| `OpenConditions` | `official_config` | 被关闭/未开放内容的下发开关（实测 `None`），对应 `OpenConditionDBSchema`(54) 的内容类型 |
| `MonthlyProductParcel` / `MonthlyProductMail` / `BiweeklyProductParcel` / `BiweeklyProductMail` / `WeeklyProductParcel` / `WeeklyProductMail` | `player_progress` | 月/周卡的领取存档；新号 `None` 或 `[]` |
| `RepurchasableMonthlyProductCountDBs` | `player_progress` | 「可复购月卡」计数存档（实测 `None`） |
| `EncryptedUID` | `echo` | **const** 空串（非空时是 UID 加密态） |
| `FunctionClose` | `official_config` | 8 个运营开关：`Arena/CloseAutoBan/CloseAutoClearRaidRank/OpenGift/ProductPriceCheck/Raid/ShowCharacterCN/ShowCharacterChange`，ExcelDB **无**对应表 |
| `AccountRestrictionsDB` | `player_progress` | 昵称/签名/称呼的封禁标记（存档） |
| `IssueAlertInfos` | `official_config` | 运营事故公告条（实测 `[]`） |
| `DailyRecordDBs` | `player_progress` | 日更任务/每日记录存档（实测 `[]`） |
| `OptionDB` | `player_progress` | 玩家设置存档：`ArenaIsAnonymous / CafeAllowCopy / MainScenarioForceEnterSeriesId` |
| `IsArenaAnonymous` | `player_progress` | 派生字段，= `OptionDB.ArenaIsAnonymous` |
| `AccountLimitedFlashSaleDBs` | `official_config` | 限时特卖排期，15 条 `{ShopExcelId, SaleFrom, SaleTo}`。⚠️ 这 15 个 `ShopExcelId`（1668-1672 / 5668-5672 / 8668-8672）**全部不在 `ShopDBSchema`** 里（已实测 `missing == 全部 15 个`）→ 只能是运营后台配置 |
| `NewlyAddedShopCashIds` | `player_progress` | 「新上架」标记（按账号最后登录时间±），实测 `[]` |

---

### `1005` Account_GetTutorial（640 B / 1 个响应，**1 个字段**）

| 响应字段 | 来源类别 | 具体来源 |
|---|---|---|
| `TutorialIds` | `player_progress` | 该账号**已完成/已播放**的教程 ID 列表（官方 21 条 `[1-14,16,17,19,21,22,23,27]`，是 `TutorialDBSchema`(33) 的 27 个基础 ID 的**真子集**）；**新号 `[]`** |

---

### `1017` Account_LoginSync（246,808 B / 1 个响应，**30 个业务字段**）

> 顶层共 35 个键 = **5 个信封字段**（`Protocol / SessionKey / ServerTimeTicks / ServerNotification / RequestId`，该包没有第 6 个信封键）+ **30 个业务字段**。这是全项目最重的包，30 个业务字段几乎全是「子响应 DTO（各自带一套 0 值信封）」。

| 响应字段 | 来源类别 | 具体来源 |
|---|---|---|
| `CafeGetInfoResponse` | `player_progress` | `CafeInfoDBSchema`(2) 定 Café 个数、`CafeRankDBSchema`(20) 定 Rank 上限、`FurnitureDBSchema`(876) 定家具定义；行 = 存档。官方 `CafeId=2` 的 11 件 `FurnitureId 1..11` = 初始态 |
| `AccountCurrencySyncResponse` | `player_progress` | `CurrencyDBSchema`(29) 定 **`CurrencyDict` 必须是 1..29 共 29 键**；数值 = 存档（新号 = DefaultParcelExcel 的 19 行 + 10 个补 0）。`UpdateTimeDict` = 每种货币最后变动时刻（动态） |
| `CharacterListResponse` | `player_progress` | `CharacterDBSchema`(7223) 定 `UniqueId` 空间；行 = 存档（新号 = DefaultCharacterExcel 的 4 行）。`TSSCharacterDBs/WeaponDBs` 也在此 |
| `EquipmentItemListResponse` | `player_progress` | `EquipmentDBSchema`(191) 定 `UniqueId`；行 = 存档（新号 `[]`） |
| `CharacterGearListResponse` | `player_progress` | `CharacterGearDBSchema` / `CharacterGearLevelDBSchema` 定定义；行 = 存档（官方 `GearDBs = []`，新号 `[]`） |
| `ItemListResponse` | `player_progress` | `ItemDBSchema`(1803) 定 `UniqueId`；行 = 存档。**官方这里是 `null`（该号 5 张加速券已耗尽），但新号应为 1 行 `{Type:4, UniqueId:2, StackCount:5}`** —— `null` 不等于「新号没有道具」 |
| `EchelonListResponse` | `player_progress` | `EchelonConstraintDBSchema`(4) 是约束；行 = 存档。**新号只有 1 条**（DefaultEchelonExcel），官方 8 条是解锁累积（type 1×4 / 2 / 3 / 4 / 6 / 11） |
| `MemoryLobbyListResponse` | `player_progress` | `MemoryLobbyDBSchema`(258) 定 `MemoryLobbyUniqueId` 空间（13010 ✅）；行 = 存档（新号 1 条 `{Type:8, 13010}`） |
| `CampaignListResponse` | `player_progress` | `CampaignChapterDBSchema`(29, Id 101..129) + `CampaignStageDBSchema`(407) 定 ID 空间；行 = 存档（新号 `[]`，`CurrentScenarioId=0`） |
| `ArenaLoginResponse` | `player_progress` | `ArenaSeasonDBSchema`(9, UniqueId 1..9) 定 `CurrentSeasonId`（官方 9 = 表最大值）；`CurrentRank/SeasonRecord/AllTimeRecord/CumulativeTimeReward` 与 3 个时间戳 = 存档/动态。新号：Rank=0、时间戳=默认 |
| `RaidLoginResponse` | `official_config` | `SeasonType`(官方 1) 由 `RaidSeasonManageDBSchema`(78) 的赛季排期决定（**运营排期**）；`CanReceiveRankingReward/LastSettledRanking/LastSettledTier` = player_progress（新号 `False/0/0`） |
| `CraftInfoListResponse` | `player_progress` | `GachaCraftNodeGroupDBSchema`(291)/`GachaCraftNodeDBSchema`(141)/`ShiftingCraftRecipeDBSchema`(87)/`RecipeDBSchema`(6973) 定定义；行 = 存档（官方 3 个数组全空，新号同） |
| `ClanLoginResponse` | `player_progress` | **无 Clan 静态表**，公会/成员全部是存档 + 他人数据（官方有公会 `蔚蓝之魂`，新号 `AccountClanDB=None`） |
| `MomoTalkOutLineResponse` | `player_progress` | 聊天列表存档；`FavorScheduleRecords` 的 ID 空间来自 `AcademyFavorScheduleDBSchema`(1053)。新号 `[]` / `{}` |
| `ScenarioListResponse` | `player_progress` | `ScenarioModeDBSchema`(581) 定剧本/模式 ID；行 = 存档。**新号 3 个数组全 `[]`**（序章 11000/11002 不落库，见 q6） |
| `ShopGachaRecruitListResponse` | `exceldb_static` | **`ShopRecruitDBSchema`**：532 行排除 `Id ∈ {1,2,3}` = **529 条**，**日期原样下发不做时间过滤**（已实测集合差精确为 `{1,2,3}`）。`ShopFreeRecruitHistoryDBs = []` 属 player_progress |
| `TimeAttackDungeonLoginResponse` | `player_progress` | `TimeAttackDungeonDBSchema`(4, Id 1000/2000/3000/4000) + `TimeAttackDungeonSeasonManageDBSchema` 定定义；`PreviousRoomDB` = 存档（官方 `None`，新号 `None`） |
| `BillingPurchaseListByYostarResponse` | `player_progress` | `ShopCashDBSchema`(656) 定 `ShopCashId`（900000/1597/15039 全部命中 ✅）；`PurchaseCount/PurchaseDate/ResetDate` = 购买存档（新号 `CountList=[]`、`OrderList=[]`、`MonthlyProductList=[]`） |
| `EventContentPermanentListResponse` | `official_config` | **22 条常驻活动**。ID 空间在 `EventContentSeasonDBSchema`(412/125 个 EventContentId) 里，但**这 22 条集合无法用任何过滤复现**：与「ECS 里 900800-900899 段的 22 个不同 ID」相比 **多 `900701`、少 `900811`**（已实测）。详见 §4 |
| `AttachmentEmblemListResponse` | `player_progress` | `EmblemDBSchema`(1065) 定 `UniqueId`；行 = 存档（新号 = 5 条 `Type:20, UniqueId 1..5`，来自 DefaultParcelExcel） |
| `AttachmentGetResponse` | `player_progress` | `AccountAttachmentDB{AccountId, EmblemUniqueId}` = 存档；**初始 `EmblemUniqueId=1`** 来自 `ConstCommonExcel.EmblemDefaultId`。**ExcelDB 无 Attachment 表** |
| `ContentSweepMultiSweepPresetListResponse` | `player_progress` | 多倍扫荡预设 = 存档（官方 1 条 `{PresetId:0, PresetName:"", StageIds:[1011101×10]}`，`StageIds` 空间来自 `CampaignStageDBSchema`）；**新号 `MultiSweepPresetDBs = []`**。**ExcelDB 无 Sweep 表**（最接近 `TacticSkipDBSchema` 21 行，未证实） |
| `EliminateRaidLoginResponse` | `official_config` | `SeasonType`(官方 2) 由 `EliminateRaidSeasonManageDBSchema`(27) 排期决定（运营）；`ReceiveLimitedRewardIds/SweepPointByRaidUniqueId/CanReceiveRankingReward/LastSettled*` = player_progress（新号 `[]/{}/False/0/0`） |
| `StickerListResponse` | `player_progress` | `StickerGroupDBSchema`(3) + `StickerPageContentDBSchema`(23) 定定义；`UnusedStickerDBs/UsedStickerDBs` = 存档。`StickerUniqueId:100001001` 这类 9 位 ID 是拼出来的（组+页+序） |
| `FriendCount` | `player_progress` | 好友数存档（官方 0） |
| `FriendCode` | `player_progress` | 账号生成时分配的好友码（官方 `"slmv4wc"`），随账号存档 |
| `MultiFloorRaidSyncResponse` | `player_progress` | `MultiFloorRaidStageDBSchema`(744)/`SeasonManage`(18) 定定义；`MultiFloorRaidDBs` = 存档（官方 `None`） |
| `MultiFloorRaidLoginResponse` | `player_progress` | 同上；`LastClearedDifficulty` = 存档（官方 0） |
| `PickupFirstGetHistoryDBs` | `player_progress` | 「首次获得」历史，`ShopRecruitId` 空间来自 `ShopRecruitDBSchema`（官方 1 条 5004170） |
| `AccountLevelRewardIds` | `player_progress` | **= `AccountLevelRewardDBSchema`(6 行；`Level` = 30/40/45/50/55/60) 里 `Level ≤ 账号等级` 的 `Id`**。官方 Lv32 → 只有 `Id=1`(Level 30)，响应正是 `[1]` ✅ 可复现 |

---

### `4000` Item_List（16,088 B / 1 个响应，**2 个字段**）

| 响应字段 | 来源类别 | 具体来源 |
|---|---|---|
| `ItemDBs` | `player_progress` | `ItemDBSchema`(1803) 定 `{Type:4, UniqueId}` 空间（响应里 9 个 UniqueId 全部命中 ✅）；行 = 存档（官方 134 行，新号 **1 行** `{Type:4, UniqueId:2, StackCount:5}`） |
| `ExpiryItemDBs` | `player_progress` | 限时道具存档（官方 `[]`，新号 `[]`） |

---

### `5000` Echelon_List（4120 B / 4 个响应，4 个响应**内容完全相同**，**1 个字段**）

| 响应字段 | 来源类别 | 具体来源 |
|---|---|---|
| `EchelonDBs` | `player_progress` | `EchelonConstraintDBSchema`(4) 是编队约束（GroupId 10002/10003/99999）；行 = 存档。官方 8 条、每条固定形状 `{EchelonType, EchelonNumber, ExtensionType, LeaderServerId, MainSlotServerIds[4], SupportSlotServerIds[2], TSSInteractionServerId, UsingFlag, SkillCardMulliganCharacterIds[3], CombatStyleIndex[6]}`。**新号 1 条**：`type1/num1/ext0`，Leader=13010 的 ServerId，主槽 `[13010,16003,13003,0]` 的 ServerId，支援槽 `[26000,0]` |

---

### `5001` Echelon_Save（984 B / 1004 B / 2 个响应，**1 个字段**）

| 响应字段 | 来源类别 | 具体来源 |
|---|---|---|
| `EchelonDB` | `echo` | **回显写入后的编队对象**（写操作把落库结果原样回吐）。两份响应唯一差别就是回显内容不同：`EchelonType=1`（type1 号1，Leader 3043301）vs `EchelonType=3`（Leader 3100950）。落库前用 `EchelonConstraintDBSchema`(4) 校验 |

---

### `6000` Campaign_List（44,672 B / 1 个响应，**3 个字段**）

| 响应字段 | 来源类别 | 具体来源 |
|---|---|---|
| `CampaignChapterClearRewardHistoryDBs` | `player_progress` | 章节全清奖励领取记录；`ChapterUniqueId` 来自 `CampaignChapterDBSchema`(29, 101..129)、`RewardType` 来自 `CampaignChapterRewardDBSchema`(60)。官方 12 条，**新号 `[]`** |
| `StageHistoryDBs` | `player_progress` | 关卡历史；`StageUniqueId` 来自 `CampaignStageDBSchema`(407)（1011101 命中 ✅）；`Star1/2/3Flag / ClearTurnRecord / TacticClearCountWithRankSRecord / TodayPlayCount / LastPlay / FirstClearRewardReceive / StarRewardReceive` 全是存档。官方 90 条，**新号 `[]`** |
| `CurrentScenarioId` | `player_progress` | 当前主线剧本 ID（官方 41200），存档。**新号 = 0**（序章不落库，见 q6） |

---

### `6020` Campaign_EnterMainStageStrategySkip（2072 B / 1 个响应，**1 个字段**）

| 响应字段 | 来源类别 | 具体来源 |
|---|---|---|
| `ParcelResultDB` | `player_progress` | 跳过战斗后的资源结算：`AccountCurrencyDB.CurrencyDict`（29 键来自 `CurrencyDBSchema`）+ `UpdateTimeDict`（动态）。只含 `AccountCurrencyDB`，无 ItemDBs → 本次掉落只有货币。**新号不会调用此协议** |

---

### `6021` Campaign_MainStageStrategySkipResult（10,284 B / 1 个响应，**7 个字段**）

| 响应字段 | 来源类别 | 具体来源 |
|---|---|---|
| `MissionProgressDBs` | `player_progress` | 任务进度（31 条）；`MissionUniqueId` 来自 `MissionDBSchema`(3444)，`Category/StartDate/ProgressParameters` 是存档 |
| `TacticRank` | `player_progress` | 本次战斗星级（官方 3），由战斗结算给出 |
| `CampaignStageHistoryDB` | `player_progress` | 该关的历史刷新（`StarFlag/ClearTurnRecord/TodayPlayCount/LastPlay` 等）；ID 来自 `CampaignStageDBSchema`(407) |
| `LevelUpCharacterDBs` | `player_progress` | 升级的角色（官方 `None`） |
| `FirstClearReward` | `exceldb_static` | 首通奖励内容查 **`CampaignStageRewardDBSchema`**(3004 行，键 `GroupId`)；「是否已领」由 player_progress 决定。官方 `[]` = 非首通 |
| `ThreeStarReward` | `exceldb_static` | 三星奖励内容查 **`CampaignStageRewardDBSchema`**(3004) + `CampaignStageDBSchema.StarRewardGroupId`；领取状态 = player_progress。官方 `[]` |
| `ParcelResultDB` | `player_progress` | 结算包：`AccountDB`（Level/Exp 变化：`BaseAccountExp:10 + AdditionalAccountExp:15`，曲线查 `AccountLevelDBSchema`(90)）+ `AccountCurrencyDB` + `ItemDBs`（`UniqueId:110` ∈ `ItemDBSchema`）+ `DisplaySequence` |

---

### `7000` Mail_List（1600 B / 1 个响应，**2 个字段**）

| 响应字段 | 来源类别 | 具体来源 |
|---|---|---|
| `MailDBs` | `player_progress` | **ExcelDB 无 Mail 表**（`/Mail/` 全库 0 命中）→ 邮件行**完全**是玩家邮箱存档。官方 2 封都是 `Type:1`、`Sender:"UI_MAILBOX_POST_SENDER_ARONA"`、`ParcelInfos:[{Type:2, Id:5, Amount:100}]`（签到奖励邮件，`Comment` 是 `UI_MAILBOX_ATTENDANCE_REWARD_MESSAGE_*` 本地化 key）。模板只在 `Excel.zip!defaultmailexceltable.bytes`(1 行) / `systemmailexceltable.bytes`(29 行)。**新号：0 封，或 1 封 DefaultMailExcel 邮件** |
| `Count` | `player_progress` | = 当前邮箱内未过期邮件数（官方 2，与 `MailDBs` 长度一致） |

---

### `7001` Mail_Check（556 B / 9 个响应，**1 个字段**）

| 响应字段 | 来源类别 | 具体来源 |
|---|---|---|
| `Count` | `player_progress` | = **该账号未读且未过期**的邮件数。9 个响应取值 3/2/2/2/2/2/2/2/3 —— 同一账号在一次会话里数量随领奖波动，是存档派生量。**新号 = 0，或 1（有 DefaultMailExcel 那封）** |

> ⚠️ 与 `7000.Count` 的区别：7000 是「邮箱全部未过期」，7001 是「未读」。官方同一时刻 7000.Count=2、7001.Count 前后取 2/3，说明是两个口径。

---

### `7003` Mail_ListSemiPermanent（556 B / 1 个响应，**0 个业务字段**）

| 响应字段 | 来源类别 | 具体来源 |
|---|---|---|
| ——（无业务字段，只有 6 个信封；536 B 就是纯信封的固定开销，7001/28019/43010 也都是 536 B） | `echo` | **const 空响应**：该账号没有「半永久邮件」。没有任何字段承载数据 → 不属于任何表 |

---

### `8000` Mission_List（268,396 B / 8768 B / 8216 B，3 个响应，**5 个字段**，三份形状相同、条数不同）

| 响应字段 | 来源类别 | 具体来源 |
|---|---|---|
| `HistoryDBs` | `player_progress` | 任务历史（三份响应都是 `None`）。`MissionEmergencyCompleteDBSchema` 定「紧急完成」规则 |
| `ProgressDBs` | `player_progress` | 进行中任务：1240 / 39 / 35 条，`{MissionUniqueId, Category, StartDate, ProgressParameters}`；`MissionUniqueId` 来自 `MissionDBSchema`(3444)，`Category`（1/4/7/8）是 **`MissionDBSchema.Bytes` 内的字段**（无独立分类表）。**新号：任务首次进大厅时按 `OpenConditionDBSchema`(54) 解锁生成，具体条数未找到规则** |
| `DailySuddenMissionInfo` | `exceldb_static` | `{Id:1606}` —— **`MissionDBSchema` 里 `Id=1606` 确实存在** ✅，是「当日突发任务」的静态定义 ID；「今天是哪一个」若轮换则需运营配置（三份响应都是 1606 → 当日固定） |
| `MissionHistoryUniqueIds` | `player_progress` | 已完成任务 ID 列表（372 / 372 条） |
| `ClearedOriginalMissionIds` | `player_progress` | 已完成原始任务 ID 列表（372 条） |

---

### `8002` Mission_MultipleReward（8320 B / 1 个响应，**3 个字段**）

| 响应字段 | 来源类别 | 具体来源 |
|---|---|---|
| `MissionProgressDBs` | `player_progress` | 领奖后刷新的任务进度（8 条 `Category:4`）；`MissionUniqueId` 来自 `MissionDBSchema`(3444) |
| `ParcelResultDB` | `player_progress` | 奖励结算包：`AccountDB` + `AccountCurrencyDB`（29 键）+ `EquipmentDBs`（`UniqueId:4` ∈ `EquipmentDBSchema`）+ `ItemDBs`（7 种，全部 ∈ `ItemDBSchema`）+ `DisplaySequence` |
| `AddedHistoryDBs` | `player_progress` | 本次新增的任务完成历史（11 条，带 `CompleteTime`） |

---

### `8006` Mission_GuideMissionSeasonList（160,216 B / 1 个响应，**2 个字段**）

| 响应字段 | 来源类别 | 具体来源 |
|---|---|---|
| `MissionProgressDBs` | `player_progress` | 733 条引导任务进度；ID 空间来自 `GuideMissionDBSchema`(923)（抽查 1000212 命中 ✅）+ `MissionDBSchema` |
| `GuideMissionSeasonDBs` | `player_progress` | **17 季**（SeasonId `3..16, 1000, 1001, 2000`）—— 是 `GuideMissionSeasonDBSchema`(20，`{1..16,1000,1001,2000,100000}`) 的**真子集**（少 1、2、100000）→ 只能是该号「参加过」的赛季。`LoginCount/StartDate/LoginDate/IsFinalMissionComplete` 全是存档。**新号：可能只有当前 1 季，规则未找到** |

---

### `10002` Shop_List（1304 B / 1 个响应，**2 个字段**）

| 响应字段 | 来源类别 | 具体来源 |
|---|---|---|
| `ShopInfos` | `exceldb_static` | **`ShopDBSchema` + `ShopInfoDBSchema`**：官方只回 1 个 shop（`Category=38`），而 `ShopDBSchema` 里 `CategoryType=38` **恰好只有 2 行（Id 201、202）**，响应的 `ShopProductList` 正是 `[201, 202]` ✅ 精确对上；`ShopInfoDBSchema`(18) 里 `CategoryType=38` 存在。`PurchaseCount/SoldOut/PurchaseCountLimit/Price/ProductType/DisplayOrder` 属 player_progress（官方 0/False/1/0/0/1）。**新号：默认开放的分类下发；具体开放哪些分类由 `OpenConditionDBSchema`(54) 的 UIShop 条件决定（未找到 per-category 规则）** |
| `ShopEligmaHistoryDBs` | `player_progress` | 神名文字（Eligma）兑换历史（官方 `[]`，新号 `[]`） |

---

### `15002` OpenCondition_EventList（600 B / 1 个响应，**1 个字段**）

| 响应字段 | 来源类别 | 具体来源 |
|---|---|---|
| `ConquestTiles` | `player_progress` | `{50822: []}` —— 键 `50822` 是 **`ConquestMapDBSchema.EventContentId`**（24 行，50822 命中 ✅；`EventContentSeasonDBSchema` 里 50822 是 type 0/17），值 = 该账号已占领的 tile 列表（官方空 → 没打过）。tile 定义来自 `ConquestTileDBSchema`(152，键 `Id`+`TileType`)。**新号：`{50822: []}`（当前开放的征服战地图 → 空 tile 列表）** |

---

### `16000` Toast_List（556 B / 1 个响应，**1 个字段**）

| 响应字段 | 来源类别 | 具体来源 |
|---|---|---|
| `ToastDBs` | `player_progress` | `null` = 当前没有待弹 toast。`ToastDBSchema`(98) 是 toast **模板池**（`Id` 是 8-10 位的大数，如 26526232 / 4139390295，属内容 ID），玩家侧只存「已弹过/待弹」记录 → 归 player_progress。**新号：`null`** |

---

### `20001` Cafe_Ack（5016 B / 1 个响应，**1 个字段**）

| 响应字段 | 来源类别 | 具体来源 |
|---|---|---|
| `CafeDB` | `player_progress` | 单个 Café 的完整状态：`CafeDBId`(=AccountId*10+CafeId) / `CafeId` ∈ `CafeInfoDBSchema`(2) / `CafeRank` ≤ `CafeRankDBSchema`(20，10 档) / `FurnitureDBs` ∈ `FurnitureDBSchema`(876) / `CafeVisitCharacterDBs`（来访学生）/ `ProductionDB.ComfortValue`(=家具舒适度之和) / `ProductionAppliedTime` / `LastSummonDate`。**新号 = `CafeId:1`、`CafeRank:1`、11 件默认家具、`LastSummonDate=0001-01-01`** |

---

### `20013` Cafe_ReceiveCurrency（11,136 B / 1 个响应，**2 个字段**）

| 响应字段 | 来源类别 | 具体来源 |
|---|---|---|
| `CafeDBs` | `player_progress` | 2 个 Café 结算后的状态（同 20001 的来源），`ProductionAppliedTime` 被推到当前时刻 |
| `ParcelResultDB` | `player_progress` | 咖啡厅产出结算：`AccountDB` + `AccountCurrencyDB`（29 键）+ `DisplaySequence:[{Type:2, Id:1, Amount:170000}]`（信用点） |

---

### `22000` Arena_EnterLobby（9068 B / 2 个响应，**5 个字段**）

| 响应字段 | 来源类别 | 具体来源 |
|---|---|---|
| `MapId` | `exceldb_static` | **`ArenaMapDBSchema`**(60 行，`UniqueId` 1001..1006 / 9001..9006)，官方值 1001 命中 ✅ |
| `ArenaPlayerInfoDB` | `player_progress` | `CurrentSeasonId=9` 由 `ArenaSeasonDBSchema`(9，UniqueId 1..9) 决定（= 表最大值）；`PlayerGroupId/CurrentRank/SeasonRecord/AllTimeRecord/CumulativeTimeReward` 与 3 个时间戳 = 存档/动态。**新号：`CurrentRank=0`、`SeasonRecord=0`、时间戳默认** |
| `AutoRefreshTime` | `echo` | **now()**：`= 服务器当前时刻 + 刷新冷却`，两份响应取值差 34 秒，纯动态 |
| `OpponentUserDBs` | `official_config` | **3 个对手全是系统 NPC**：`AccountServerId:0`、`NickName:"Character_13010" / "Character_20001" / "Character_16004"`（= `Character_<CharacterId>` 模板拼出来的假昵称）、`Rank` 9000-12000 段由分组生成。NPC 定义表是 `ArenaNPCDBSchema`(13 行)，但**具体给哪 3 个对手、Rank/Level 多少由服务端按赛季分组（`PlayerGroupId=322`）动态生成** → 归 official_config。`RepresentCharacterUniqueId/EmblemUniqueId=1` 也在 NPC 生成里 |
| `IsServerRunBattle` | `echo` | **const** `True`（服务端跑战斗的总开关） |

---

### `22004` Arena_EnterBattle（67,180 B / 1 个响应，**9 个字段**）

| 响应字段 | 来源类别 | 具体来源 |
|---|---|---|
| `MissionProgressDBs` | `player_progress` | 6 条任务进度（`Category:1`，`MissionUniqueId` ∈ `MissionDBSchema`） |
| `ArenaBattleDB` | `player_progress` | 战斗记录：`Season/Group/BattleStartTime/BattleEndTime/Seed` + `AttackingUserDB`（本人队伍快照）+ `DefendingUserDB`（NPC）+ `BattleSummary`（**战斗服务端模拟结果**：双方 `Heroes/Supporters`、`GivenNumericLogs/TakenNumericLogs`、`HPRate/KillLog/EndFrame` 等）。**没有任何静态表能产出 `BattleSummary`** —— 这是服务端战斗模拟的产物 |
| `ArenaPlayerInfoDB` | `player_progress` | 战后 `CurrentRank` 12909（战前 13720）等 |
| `AccountCurrencyDB` | `player_progress` | 战后货币（29 键） |
| `VictoryRewards` | `player_progress` | 胜利奖励：内容由 `ArenaRewardDBSchema`(108，键 `UniqueId`+`ArenaRewardType`) 定义，**发多少/是否发按战斗结果**（官方 `[{Type:2, Id:1, Amount:1000}]`）→ 以 player_progress 为主 |
| `SeasonRewards` | `player_progress` | 赛季奖励（官方 `[{Type:2, Id:3, Amount:20}]`）。⚠️ **`ArenaSeasonCloseRewardDBSchema` 是 0 行空表**（已实测）→ 奖励内容不可能来自该表，只能是服务端配置/存档 → 归 player_progress + 待定 |
| `AllTimeRewards` | `player_progress` | 历史最高段位奖励（官方 `None`） |
| `BattleSetting` | `player_progress` | 战斗参数快照：`BattleType:2097152 / RandomSeed / Buid / GroundUniqueId / LeftTeam(Starters/Supporters/ArenaSetting) / RightTeam`。**逐字段是本次战斗的输入**（角色等级/技能/装备全来自存档快照）→ player_progress；底层 `GroundUniqueId` 等常量能追到静态表但这里只是回填 |
| `BattleServerError` | `echo` | **const** `False` |

---

### `22008` Arena_CumulativeTimeReward（3072 B / 1 个响应，**3 个字段**）

| 响应字段 | 来源类别 | 具体来源 |
|---|---|---|
| `TimeRewardAmount` | `player_progress` | 累积时间奖励额度（官方 0），存档 |
| `TimeRewardLastUpdateTime` | `echo` | **now()**：本次更新时间（实测 `2026-11-16T04:33:15.253614832` = 收包时刻） |
| `ParcelResult` | `player_progress` | 结算包（`[{Type:2, Id:1, Amount:187110}]`）；本次 `TimeRewardAmount=0` 但仍结算了信用点，说明奖励公式不在静态表里 |

---

### `22009` Arena_DailyReward（3224 B / 1 个响应，**2 个字段**）

| 响应字段 | 来源类别 | 具体来源 |
|---|---|---|
| `DailyRewardActiveTime` | `echo` | **now()/下一可用时刻**：官方 `2026-11-16T14:00:00`（= 当日 14:00 刷新点，收包时 04:33）→ 服务器按每日刷新时刻算出，非表数据 |
| `ParcelResult` | `player_progress` | 每日奖励结算：`AccountDB` + `AccountCurrencyDB` + `ItemDBs:{UniqueId:8, StackCount:130}`（`ItemDBSchema.Id=8` 命中 ✅）+ `DisplaySequence:[{Type:4, Id:8, Amount:30}]`。奖励内容表找**不到**（无 ArenaDailyReward 表）→ 依赖服务端配置 |

---

### `22016` Arena_SyncEchelonSettingTime（640 B / 1 个响应，**1 个字段**）

| 响应字段 | 来源类别 | 具体来源 |
|---|---|---|
| `EchelonSettingTime` | `echo` | **now()**：实测 `2026-11-16T04:33:21.231941118`，就是这个包的发送时刻 → 纯动态时间戳，不查任何表 |

---

### `24000` Academy_GetInfo（17,560 B / 2 个响应，**2 个字段**）

| 响应字段 | 来源类别 | 具体来源 |
|---|---|---|
| `AcademyDB` | `player_progress` | `ZoneVisitCharacterDBs`（zone 键空间来自 `AcademyZoneDBSchema` 95 行；值是「该 zone 有哪些学生来过」= 存档）+ `ZoneScheduleGroupRecords`（`ScheduleGroupId` ∈ `AcademyFavorScheduleDBSchema` 1053 行）+ `LastUpdate`。**新号：`{}` 或只含已解锁 zone 的空数组** |
| `AcademyLocationDBs` | `player_progress` | **9 条**：`LocationId` 空间来自 `AcademyLocationDBSchema`(11，`Id`=1/7/11..19)，`Rank/Exp` 是进度（(1,R2) (7,R1) (11,R1) (12,R2) (13,R1) (15,R1) (16,R2) (17,R2) (19,R2,E200)）。**新号：Rank=1、Exp=0；条数规则「未找到」**（见 §2.1 q8） |

---

### `25003` Event_RewardIncrease（792 B × 21 个响应，内容**完全相同**，**1 个字段**）

| 响应字段 | 来源类别 | 具体来源 |
|---|---|---|
| `EventRewardIncreaseDBs` | `official_config` | 1 条 `{EventTargetType:4, RewardRealType:100473, Multiplier:{rawValue:20000}(=2.0×), BeginDate:"2026-11-12T04:00:00", EndDate:"2026-11-19T03:59:59"}`。**ExcelDB 里没有任何 RewardIncrease/Increase 表**（全库 0 命中）；`RewardRealType=100473` 确实是 `EventContentSeasonDBSchema` 里的一个 EventContentId（type 0），但**加成倍率与起止时间不可能从 412 行的 ECS 推出来** → 运营活动排期。21 个响应字节数完全相同 = 整场会话内这条配置是常量 |

---

### `26000` ContentSave_Get（640 B / 1 个响应，**3 个字段**）

| 响应字段 | 来源类别 | 具体来源 |
|---|---|---|
| `HasValidData` | `player_progress` | `False` = 该账号没有内容存档（= `ContentSaveDB` 是否为空派生）。**新号 `False`** |
| `ContentSaveDB` | `player_progress` | `None`；无静态表（"ContentSave" = 客户端存档上传功能） |
| `EventContentChangeDB` | `player_progress` | `None`；`EventContentChangeDBSchema` 存在于 ExcelDB（定义侧）但这里回的是玩家状态 |

---

### `28000` Clan_Lobby（35,864 B / 1 个响应，**4 个字段**）

| 响应字段 | 来源类别 | 具体来源 |
|---|---|---|
| `AccountClanDB` | `player_progress` | 本账号所属公会（`ClanDBId:27353`、名字/频道名/会长/公告/人数 50）。**ExcelDB 无 Clan 本体表**（只有 `ClanRewardDBSchema` 1 行 + `ClanChattingEmojiDBSchema` 176 行）→ 纯存档 |
| `DefaultExposedClanDBs` | `player_progress` | 推荐公会列表（官方 `[]`） |
| `AccountClanMemberDB` | `player_progress` | 本账号在公会内的成员档案（含 `AttachmentDB{EmblemUniqueId:1}`） |
| `ClanMemberDBs` | `player_progress` | **50 名成员**的跨账号数据（`AccountId/AccountLevel/AccountNickName/RepresentCharacterUniqueId/AttendanceCount/JoinDate/LastLoginDate`）。**新号：未入会 → 全 `None`/`[]`** |

---

### `28019` Clan_Check（536 B / 8 个响应，**0 个业务字段**）

| 响应字段 | 来源类别 | 具体来源 |
|---|---|---|
| ——（无业务字段；536 B 全信封） | `echo` | **const 空响应**：8 个响应字节数完全相同（536）→ 该协议对「检查公会状态」的请求只回一个成功信封 |

---

### `29002` Billing_PurchaseListByYostar（1280 B / 3 个响应，**3 个字段**）

| 响应字段 | 来源类别 | 具体来源 |
|---|---|---|
| `CountList` | `player_progress` | 4 条 `{ShopCashId, PurchaseCount, ResetDate, PurchaseDate}`。`ShopCashId` 空间来自 **`ShopCashDBSchema`(656)**（官方出现 900000 / 1597 / 15039，全部命中 ✅）；`PurchaseCount`/`ResetDate` = 购买存档 + 每日/每周重置时刻。**新号 `[]`** |
| `OrderList` | `player_progress` | 充值订单（官方 `[]`） |
| `MonthlyProductList` | `player_progress` | 月卡（官方 `[]`） |

---

### `30041` EventContent_PermanentList（2156 B / 1 个响应，**1 个字段**）

| 响应字段 | 来源类别 | 具体来源 |
|---|---|---|
| `PermanentDBs` | `official_config` | **22 条**「常驻活动」`{EventContentId, IsStageAllClear}`。ID 空间在 `EventContentSeasonDBSchema`（412 行 / 125 个 EventContentId），但**这 22 条集合无法用任何过滤复现**：ECS 里 900800-900899 段有 **22 个**不同 ID，而响应集合是「那 22 个 **减去 900811、加上 900701**」（已实测双向差集恰好如此）。→ 哪些活动「常驻」是服务端运营登记，不是表数据。`IsStageAllClear` = player_progress（官方全 `False`）。**新号：22 条、全 `False`** |

---

### `35003` MiniGame_MissionList（4480 B / 1 个响应，**3 个字段**）

| 响应字段 | 来源类别 | 具体来源 |
|---|---|---|
| `MissionHistoryUniqueIds` | `player_progress` | 已完成小游戏任务（官方 `[]`） |
| `ProgressDBs` | `player_progress` | 18 条 `{MissionUniqueId:108380000, Category:7, ...}`；ID 空间来自 `MissionDBSchema`(3444)（抽查：响应里的 ID **全部命中** ✅）+ 小游戏专属 `MiniGameMissionDBSchema` |
| `ClearedOrignalMissionIds` | `player_progress` | 官方 `None`；字段名拼写就是客户端原样的 `Orignal`（不是笔误） |

---

### `36001` Notification_EventContentReddotCheck（1088 B / 10 个响应，内容完全相同，**2 个字段**）

| 响应字段 | 来源类别 | 具体来源 |
|---|---|---|
| `Reddots` | `player_progress` | `{}` 空 map = 所有红点都已读（红点是「玩家是否点过」的状态） |
| `EventContentUnlockCGDBs` | `official_config` | **25 个键**：`{849, 10838, 50822} ∪ {900801..900827 段}`（具体是 900801-900806、900808-900820、900811 含、900825-900827）。这与「`EventContentSeasonDBSchema` 里 900800-900899 段的 22 个不同 ID **全含**」+ 3 个额外（849/10838/50822，三个都在 ECS 存在）→ **键集合 = 当前开放的活动列表**，属运营排期；每个键的值是已解锁 CG 列表（官方全 `[]`）。**新号：键集合同、值全 `[]`** |

---

### `43010` Friend_Check（536 B / 8 个响应，**0 个业务字段**）

| 响应字段 | 来源类别 | 具体来源 |
|---|---|---|
| ——（无业务字段；536 B 全信封） | `echo` | **const 空响应**（与 28019 同形）。好友数量走 1017 的 `FriendCount`，不在这个包里 |

---

### `90004` Management_Data（14,124 B / 14,104 B / 10 个响应，**1 个字段**）

| 响应字段 | 来源类别 | 具体来源 |
|---|---|---|
| `Data` | `official_config` | 7 个子数组**全部**来自运营后台，不是 ExcelDB：`Notices`(6 条公告) / `Events`(14 条活动) / `Issues`(0) / `Banners`(7 条 banner，`CdnUrl` 指向 `webcnstatic.yostar.net`、`LinkedLobbyBannerId` 是 `ShopRecruitDBSchema` 里的 banner ID 5004670) / `GachaProbabilityDisplay`(12 条，`Url` 指向 `notice.bluearchive-cn.com`) / `GuidePopup`(0) / `GachaPeriodDisplay`、`RaidPeriodDisplay`、`Survey`(均 `None`)。**ExcelDB 398 张表里没有 Notices/Banners/公告/概率公示任何一张**。两份变体（14124 vs 14104 B）差别只在 `CreateTime`（动态）—— 10 个响应里 `Notices/Events/Banners` 的内容**完全一致**，只有 `CreateTime` 变 |

---

### `90009` Clan_Chat_Records（30,316 B / 556 B / 2 个响应，**1 个字段**）

| 响应字段 | 来源类别 | 具体来源 |
|---|---|---|
| `ChatRecords` | `player_progress` | 公会聊天记录（100 条 / 0 条）。`ChatId/MessageType/SubType/CharacterId/AccountNickname/Text/SendTicks/EmblemId` 全是存档；`StickerId` 的空间来自 `StickerGroupDBSchema`(3)+`StickerPageContentDBSchema`(23)，`EmblemId` 的空间来自 `EmblemDBSchema`(1065)。**新号：未入会 → `[]`** |

---

## 第 4 步：不确定项单独列出

### 4.1 判定为 `official_config` 的字段（共 9 处，19 个字段实例）

| 协议.字段 | 为什么不是 ExcelDB 能算出来的 |
|---|---|
| `1002.TTSCdnUri` | CDN 地址是部署配置，ExcelDB 无 URL 类表（398 张表里没有任何 Cdn/Uri 表） |
| `1002.FunctionClose` | 8 个运营开关，ExcelDB 无对应表 |
| `1002.OpenConditions` | 「哪些内容被关闭」是运营侧状态；`OpenConditionDBSchema`(54) 只描述**条件**，不描述**当前开关** |
| `1002.IssueAlertInfos` | 运营事故公告 |
| `1002.AccountLimitedFlashSaleDBs` | **强证据**：15 个 `ShopExcelId`（1668-1672/5668-5672/8668-8672）**全部不在 `ShopDBSchema`**（已实测差集 = 全部 15 个），只能来自运营后台；`SaleFrom/SaleTo` 也是排期 |
| `1017.RaidLoginResponse.SeasonType` / `1017.EliminateRaidLoginResponse.SeasonType` | 赛季类型由 `RaidSeasonManageDBSchema`(78) / `EliminateRaidSeasonManageDBSchema`(27) 的**起止日期**派生，即「当前在哪个赛季」= 运营排期 |
| `1017.EventContentPermanentListResponse.PermanentDBs` | 22 条集合不可由 ECS 任何过滤复现（多 900701、少 900811）。**这是唯一「ID 全在表里、集合却算不出来」的案例** |
| `22000.OpponentUserDBs` | 对手是 `AccountServerId:0` 的 NPC（昵称 `Character_<id>`）。NPC 定义只有 13 行 `ArenaNPCDBSchema`，但**具体给哪 3 个、Rank/Level 多少**由服务端按 `PlayerGroupId` 分组动态生成 |
| `25003.EventRewardIncreaseDBs` | **ExcelDB 全库无 Increase 表**；`RewardRealType=100473` 是 ECS 的合法 EventContentId，但倍率 2.0× 与 11-12→11-19 的档期推不出来 |
| `30041.PermanentDBs` | 同 1017 的常驻活动列表 |
| `36001.EventContentUnlockCGDBs`（键集合部分） | 25 个键 = 「当前开放的活动」，超出 ECS 能推出的范围（含 849/10838/50822 这 3 个非 9008xx 段） |
| `90004.Data`（整个） | 公告/活动/banner/概率公示全部来自运营后台（URL 指向 `notice.bluearchive-cn.com` / `webcnstatic.yostar.net`），**ExcelDB 398 张表里没有任何一张承载这些** |

### 4.2 判为「未找到」的表 + 由此产生的实现风险

| 表 | 影响 | 私服实现上的现实做法 |
|---|---|---|
| `MailDBSchema` | 7000/7001/7003 的邮件 | 邮件**必须自建存档表**。初始 1 封邮件的内容只能从 `Excel.zip!defaultmailexceltable.bytes`（1 行，8 slot，语义部分未闭合）硬编码；`systemmailexceltable.bytes`(29 行) 可作系统邮件模板 |
| `MissionCategoryDBSchema` | 8000/8002 的 `Category` | `Category` 直接取 `MissionDBSchema.Bytes` 里的字段，**不要**假设有分类表 |
| `EventRewardIncreaseDBSchema` | 25003 | 加成倍率/档期必须写在服务端配置里。最接近的定义表是 `EventContentCharacterBonusDBSchema`(2172)，**未证实** |
| `ContentSweepDBSchema` | 1017 的扫荡预设、35003 | 最接近 `TacticSkipDBSchema`(21，键 `LevelDiff`)，**未证实**；扫荡消耗/次数上限需自建配置 |
| `AttachmentDBSchema` | 1017 的 Attachment | Attachment 只有 `{AccountId, EmblemUniqueId}`，自建存档即可，初始值 `1` 来自 `ConstCommonExcel.EmblemDefaultId` |
| `ClanDBSchema`（族名不存在） | 28000/28019/90009 | 公会/成员/聊天全部自建存档；静态侧只有 `ClanRewardDBSchema`(1) 和 `ClanChattingEmojiDBSchema`(176) |
| `MinigameDBSchema`（无总表） | 35003 | 60 张 `MiniGame*` 表按玩法分族，没有「小游戏总表」；任务走 `MiniGameMissionDBSchema` + `MissionDBSchema` |
| `RaidDBSchema` / `MultiFloorRaidDBSchema` / `EliminateRaidDBSchema` / `WorldRaidDBSchema`（无总表） | 1017 的 4 个 Raid 子响应 | 都是族表（Stage/SeasonManage/Reward 分开），没有单一入口表 |
| `ArenaDBSchema`（无总表） | 22000/22004/22008/22009 | 族表；**且 `ArenaSeasonCloseRewardDBSchema` 是 0 行空表** → 22004 的 `SeasonRewards` 内容无法从表得出 |
| `EventContentDBSchema`（无总表） | 25003/30041/36001/15002 | 用 `EventContentSeasonDBSchema`（键是 `EventContentId`+`EventContentType` **复合**，412 行 / 125 个 ID）作活动索引 |
| `StickerDBSchema`（无总表） | 1017 `StickerList` | `StickerGroupDBSchema`(3) + `StickerPageContentDBSchema`(23) 两表拼 |
| `CraftDBSchema`（无总表） | 1017 `CraftInfoList` | `GachaCraftNodeGroupDBSchema`(291) + `GachaCraftNodeDBSchema`(141) + `ShiftingCraftRecipeDBSchema`(87) + `RecipeDBSchema`(6973) |
| `CharacterSkillDBSchema`（真实名不同） | 1017 技能等级 | 真实表是 `CharacterSkillListDBSchema`(6708)；技能**数值**在 `SkillDBSchema`(18028，键 `GroupId`+`Level`) |
| `AttendanceBookDBSchema`（真实名不同） | 1002 签到 | 真实表是 `AttendanceDBSchema`(31) + `AttendanceRewardDBSchema`(334)；响应里的 `AttendanceBookUniqueId:28` 对应 `AttendanceDBSchema.Id=28` ✅ |

### 4.3 时间/动态值导致的额外不确定

| 字段 | 问题 |
|---|---|
| `3.ReceiveTick`、`3.EchoSendTick`、`22000.AutoRefreshTime`、`22008.TimeRewardLastUpdateTime`、`22009.DailyRewardActiveTime`、`22016.EchelonSettingTime`、`90004.Data.*.CreateTime` | 全是 `now()` 或「now + 冷却」，抓包里每个包都不同（如 22000 两份差 34 秒、90004 十份只有 `CreateTime` 变）→ 无法用静态表或存档解释，本文件归 `echo` |
| `1017.AccountCurrencySyncResponse.UpdateTimeDict` | 29 种货币各自的最后变动时刻，是存档的一部分但每次结算都会变（6020/6021/8002/20013/22004 里同一字段值互不相同） |
| `1002.AccountDB.LastConnectTime/LastReturningDate/CreateDate` | 账号存档时间戳 |
| `25003.EventRewardIncreaseDBs.BeginDate/EndDate` | 活动档期；本次抓到的是 `2026-11-12T04:00:00 ~ 2026-11-19T03:59:59`（7 天周活动），下一期必然不同 |
| `7001.Count` 在同一会话里 2↔3 波动 | 领奖/读信会改变未读数，说明它是存档派生而非常量 |

### 4.4 一个必须提醒的**反例陷阱**（避免下游误判）

**1017 里内嵌的子响应是「默认值模板」，不能拿其中的派生汇总值反推新号状态。** 实测矛盾：
- `AccountCurrencySyncResponse.AccountCurrencyDB.AccountLevel = 1`，而 `AccountDB.Level = 32`
- `AccountCurrencySyncResponse.AccountCurrencyDB.AcademyLocationRankSum = 1`，而 24000 实测 9 条 `Rank` 之和 = **14**
- 内嵌子响应的 `Protocol:0 / ServerTimeTicks:0 / SessionKey.AccountServerId:0 / RequestId:""` 全是 0 值

→ 同级的 `ItemListResponse: null`、`CharacterGearListResponse.GearDBs: []`、`MultiFloorRaidSyncResponse.MultiFloorRaidDBs: null` 也**不能**直接当成「新号这些字段就是空」，必须回到 §2 的规则表判定。这一条与 `initial_state_rules.json` 的 q8「⚠️ 陷阱」是同一个现象，已在此扩展记全。

---

## 附录：复现脚本（全部在 `work\ba\proto\`，只读）

| 脚本 | 作用 |
|---|---|
| `_sub_s0_totals.py` | 398 表 / 707,896 行总数 |
| `_sub_s1_tables.py` | 48 候选的三级查找（精确→模糊→族），输出 `_sub_s1_tables.json` |
| `_sub_s1b_hunt.py` | 未命中候选的关键词族扫描 + 398 表名全量打印 |
| `_sub_s1c_schema.py` | 列名 / 行数 / 逻辑键 |
| `_sub_s1d_keys.py` | 逻辑键唯一性（UNIQUE/DUP）实测 |
| `_sub_s1e_ddl.py` | 证明 398 张表**无 PRIMARY KEY** |
| `_sub_s1f_counts.py` | 族表行数汇总 |
| `_sub_s3_dump.py` | 38 协议 `inner` 业务字段全量 dump → `_sub_s3_dump.txt` |
| `_sub_s3b_verify.py` / `_sub_s3c_reconcile.py` / `_sub_s3d.py` / `_sub_s3e.py` / `_sub_s3f_keys.py` / `_sub_s3g.py` | 逐条把响应里的 ID/条数与具体表对账（Shop 38→2 行、532−3=529、30041 的 900701/900811 差集、8006 的 17/20 季、36001 的 25 键、AccountLevelReward 的 Lv→Id 等） |

---—

### 一句话结论

**38 个协议里，只有 4 个字段组真正「查 ExcelDB 静态表」（且都是固定/整表下发）**：1017 的 529 个招募 banner（`ShopRecruitDBSchema`）、10002 的 2 件商品（`ShopDBSchema.CategoryType=38`）、8000 的当日突发任务 ID（`MissionDBSchema.Id=1606`）、6021 的首通/三星奖励内容（`CampaignStageRewardDBSchema`）；**其余压倒性是 `player_progress`（26/38 协议主导，即必须自建存档表）**；**`official_config` 集中在公告/banner/活动排期/常驻活动集合/赛季类型**（10 处，其中 `1002.AccountLimitedFlashSaleDBs` 与 `30041` 有「表里查不到、集合算不出」的硬证据）；**`echo` 覆盖 3 个纯信封响应（7003/28019/43010，都是 536 B）与全部动态时间戳**。初始状态规则**一条都不在 `ExcelDB.db` 里** —— 在 `Excel.zip` 的 5 张 `Default*` 表 + `ConstCommonExcel`，见第 2 节。
