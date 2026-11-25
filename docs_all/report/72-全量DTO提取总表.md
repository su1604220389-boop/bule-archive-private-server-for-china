# 72 全量 DTO 提取总表（国服 444 个具名 Response DTO）

> 生成时间：2026-11-14 06:23:45　|　产物：`work/ba/proto/dto_schema_full.json` + `work/ba/proto/gen_full.py`
> 数据源：`global-metadata.dat`（38,426,024 B，国服客户端）→ `report/_tmp/patch/md_deob.bin`；`protocol_map.json` 501 条协议；`shittim_types.json` 821 条 C# 声明（仅做泛型投票）

## §0 一句话结论

**444 个具名 Response DTO 全部提取到字段表（覆盖率 100%，444/444）：其中 400 个有字段（398 个自有字段 + 2 个仅继承父 DTO），自有字段 1088 个、含继承的有效字段 1131 个；44 个经 `methods` 表验证为「真·空响应」（fieldCount=0，只有 get_Protocol 与 .ctor）。`gen_full.py --check` 对 457 条协议（444 + 13 条额外恢复映射）全部通过（exit 0），每个响应包都能 `json.loads` 且含 ResponsePacket 基类 6 字段。仍缺 0 个 DTO；不确定项集中在 124 个泛型实例与 264 个 support 类型的未知字段上，全部在 §3 列明。**

对照：合并前 `dto_schema.json`(32) + `dto_schema_academy.json`(2) 只覆盖 34 个；本次补齐 410 个。已有 34 个与本次自动提取的**字段表逐项一致（0 处差异）**，说明口径已对齐。

## §1 按段统计

段 = `协议号 // 1000`；「合并前」指旧 schema 已覆盖；「真·空」= metadata fieldCount=0 且 methods 只有 get_Protocol+.ctor。

| 段 | 协议数 | DTO 数 | 合并前已覆盖 | 本次交付 | 非空 | 真·空 | 失败 | 字段数 |
|---|---|---|---|---|---|---|---|---|
| 1 | 19 | 19 | 5 | 19 | 11 | 8 | 0 | 104 |
| 2 | 11 | 11 | 1 | 11 | 11 | 0 | 0 | 22 |
| 3 | 1 | 1 | 0 | 1 | 1 | 0 | 0 | 4 |
| 4 | 7 | 7 | 1 | 7 | 7 | 0 | 0 | 11 |
| 5 | 4 | 4 | 1 | 4 | 4 | 0 | 0 | 5 |
| 6 | 22 | 22 | 1 | 22 | 22 | 0 | 0 | 59 |
| 7 | 5 | 5 | 0 | 5 | 5 | 0 | 0 | 15 |
| 8 | 3 | 3 | 0 | 3 | 2 | 1 | 0 | 4 |
| 9 | 1 | 1 | 0 | 1 | 1 | 0 | 0 | 3 |
| 10 | 17 | 17 | 1 | 17 | 16 | 1 | 0 | 58 |
| 11 | 1 | 1 | 0 | 1 | 1 | 0 | 0 | 3 |
| 12 | 4 | 4 | 1 | 4 | 2 | 2 | 0 | 2 |
| 15 | 3 | 3 | 0 | 3 | 3 | 0 | 0 | 4 |
| 16 | 1 | 1 | 0 | 1 | 1 | 0 | 0 | 1 |
| 17 | 20 | 20 | 1 | 20 | 20 | 0 | 0 | 54 |
| 18 | 2 | 2 | 0 | 2 | 2 | 0 | 0 | 2 |
| 19 | 21 | 21 | 1 | 21 | 13 | 8 | 0 | 32 |
| 20 | 23 | 23 | 1 | 23 | 19 | 4 | 0 | 42 |
| 21 | 15 | 15 | 0 | 15 | 14 | 1 | 0 | 28 |
| 22 | 15 | 15 | 1 | 15 | 11 | 4 | 0 | 32 |
| 23 | 4 | 4 | 0 | 4 | 4 | 0 | 0 | 10 |
| 24 | 2 | 2 | 2 | 2 | 2 | 0 | 0 | 5 |
| 25 | 1 | 1 | 0 | 1 | 1 | 0 | 0 | 1 |
| 26 | 2 | 2 | 0 | 2 | 2 | 0 | 0 | 4 |
| 27 | 4 | 4 | 1 | 4 | 4 | 0 | 0 | 8 |
| 28 | 21 | 21 | 1 | 21 | 16 | 5 | 0 | 39 |
| 29 | 4 | 4 | 1 | 4 | 4 | 0 | 0 | 22 |
| 30 | 54 | 54 | 1 | 54 | 54 | 0 | 0 | 152 |
| 31 | 1 | 1 | 0 | 1 | 1 | 0 | 0 | 2 |
| 33 | 4 | 4 | 1 | 4 | 4 | 0 | 0 | 8 |
| 34 | 2 | 2 | 0 | 2 | 2 | 0 | 0 | 2 |
| 35 | 42 | 42 | 0 | 42 | 38 | 4 | 0 | 90 |
| 36 | 1 | 1 | 0 | 1 | 1 | 0 | 0 | 2 |
| 37 | 2 | 2 | 0 | 2 | 1 | 1 | 0 | 2 |
| 38 | 4 | 4 | 0 | 4 | 4 | 0 | 0 | 9 |
| 39 | 7 | 7 | 1 | 7 | 7 | 0 | 0 | 22 |
| 40 | 6 | 6 | 0 | 6 | 6 | 0 | 0 | 12 |
| 41 | 1 | 1 | 0 | 1 | 1 | 0 | 0 | 1 |
| 42 | 18 | 18 | 0 | 18 | 18 | 0 | 0 | 71 |
| 43 | 13 | 13 | 0 | 13 | 11 | 2 | 0 | 53 |
| 44 | 3 | 3 | 1 | 3 | 3 | 0 | 0 | 6 |
| 45 | 10 | 10 | 1 | 10 | 10 | 0 | 0 | 35 |
| 46 | 4 | 4 | 2 | 4 | 4 | 0 | 0 | 4 |
| 47 | 3 | 3 | 1 | 3 | 3 | 0 | 0 | 5 |
| 48 | 7 | 7 | 0 | 7 | 7 | 0 | 0 | 18 |
| 49 | 5 | 5 | 2 | 5 | 5 | 0 | 0 | 8 |
| 50 | 2 | 2 | 0 | 2 | 2 | 0 | 0 | 13 |
| 51 | 7 | 7 | 0 | 7 | 7 | 0 | 0 | 15 |
| 52 | 1 | 1 | 0 | 1 | 1 | 0 | 0 | 2 |
| 53 | 1 | 1 | 0 | 1 | 0 | 1 | 0 | 0 |
| 54 | 4 | 4 | 0 | 4 | 3 | 1 | 0 | 5 |
| 90 | 7 | 7 | 4 | 7 | 6 | 1 | 0 | 16 |
| nosid | 2 | 2 | 0 | 2 | 2 | 0 | 0 | 4 |
| **合计** | **444** | **444** | **34** | **444** | **400** | **44** | **0** | **1131** |

说明：
- 表中"字段数"= 自有字段 + 从父 DTO 继承的字段（仅 3 个 DTO 有继承，见 2.2）；自有字段合计 1088。
- "合并前已覆盖"只统计任务开始时的 `dto_schema.json`(32) + `dto_schema_academy.json`(2)；并列 agent 在任务期间产出的 `dto_schema_lobby.json` 覆盖了 50 个 resp DTO（其中 45 个是本次缺口），已在合并时交叉校验（字段名 0 差异），不重复计入本列。
- `seg=nosid` 是 2 个没有协议号的 DTO：`AuditGachaStatisticsResponse`（Audit_GachaStatistics）与 `SystemVersionResponse`（System_Version）。
- 44 个真·空响应不是提取失败：metadata 里 `fieldStart=0xFFFFFFFF`、`fieldCount=0`，且 methods 表只有 `get_Protocol`+`.ctor`，没有 get/set 访问器。另有 2 个自身 0 字段但继承父 DTO。逐条证据见 §2。

### 1.1 分段校对（10 个子 agent，互不重叠的文件）

| 文件 | agent | verify | root | 字段 | 修复 | shittim 差异 | 空 DTO |
|---|---|---|---|---|---|---|---|
| `seg_1.json` | A | PASS | 19 | 269 | 2 | 6 | 0 |
| `seg_10-16.json` | E | PASS | 26 | 160 | 4 | 4 | 0 |
| `seg_17-20.json` | F | PASS | 66 | 520 | 5 | 3 | 12 |
| `seg_2-3.json` | B | PASS | 12 | 123 | 6 | 2 | 0 |
| `seg_21-29.json` | G | PASS | 68 | 785 | 5 | 5 | 10 |
| `seg_30-36.json` | H | PASS | 104 | 591 | 5 | 4 | 4 |
| `seg_37-45.json` | I | PASS | 64 | 635 | 5 | 5 | 3 |
| `seg_4-5.json` | C | PASS | 11 | 104 | 7 | 0 | 0 |
| `seg_46-90.json` | J | PASS | 43 | 410 | 6 | 5 | 3 |
| `seg_6-9.json` | D | PASS | 31 | 246 | 5 | 3 | 0 |

每个 agent 都被要求：跑 `verify_seg`、用 `type_lookup --dto` 独立复算字段名/顺序/ti、与 `shittim_types.json` 交叉、检查空响应、做语义体检；只有拿到证据才允许改类型。修复集中在 `ParcelResultDB` 的 5 个 support 字段（各段独立复现了同一结论）。

## §2 仍缺的清单与原因

### 2.1 协议级缺口：0

`gen_full.py --missing` 输出：`schema 已收录 444 / 仍缺 0`。444 个 resp DTO 全部在 `dto_schema_full.json` 里有条目（44 个条目的 `fields` 为空数组，理由见 2.2）。

### 2.2 真·空响应（44 个）+ 仅继承（2 个）

判据（两道独立证据都要满足）：
1. metadata：`fieldCount = 0` 且 `fieldStart = 0xFFFFFFFF`（il2cpp 的"无字段"哨兵）；
2. methods 表：该类型只有 `get_Protocol` 与 `.ctor`，没有任何 `get_/set_` 访问器。

| # | 协议 | DTO | methods |
|---|---|---|---|
| 1 | 1000 | `AccountCreateResponse` | get_Protocol, .ctor |
| 2 | 1015 | `AccountDismissRepurchasablePopupResponse` | get_Protocol, .ctor |
| 3 | 1016 | `AccountInvalidateTokenResponse` | get_Protocol, .ctor |
| 4 | 1013 | `AccountLinkRewardResponse` | get_Protocol, .ctor |
| 5 | 1014 | `AccountReportXignCodeCheaterResponse` | get_Protocol, .ctor |
| 6 | 1019 | `AccountRequestBirthdayMailResponse` | get_Protocol, .ctor |
| 7 | 1018 | `AccountResetResponse` | get_Protocol, .ctor |
| 8 | 1006 | `AccountSetTutorialResponse` | get_Protocol, .ctor |
| 9 | 22007 | `ArenaBattleResultResponse` | get_Protocol, .ctor |
| 10 | 22015 | `ArenaCheckSeasonCloseRewardResponse` | get_Protocol, .ctor |
| 11 | 22017 | `ArenaSettingAnonymousResponse` | get_Protocol, .ctor |
| 12 | 22002 | `ArenaSettingChangeResponse` | get_Protocol, .ctor |
| 13 | 20009 | `CafeClearPresetResponse` | get_Protocol, .ctor |
| 14 | 20008 | `CafeRenamePresetResponse` | get_Protocol, .ctor |
| 15 | 20022 | `CafeUpdateCopyPresetFurnitureResponse` | get_Protocol, .ctor |
| 16 | 20010 | `CafeUpdatePresetFurnitureResponse` | get_Protocol, .ctor |
| 17 | 28015 | `ClanCancelApplyResponse` | get_Protocol, .ctor |
| 18 | 28019 | `ClanCheckResponse` | get_Protocol, .ctor |
| 19 | 28012 | `ClanDismissResponse` | get_Protocol, .ctor |
| 20 | 28009 | `ClanKickResponse` | get_Protocol, .ctor |
| 21 | 28007 | `ClanQuitResponse` | get_Protocol, .ctor |
| 22 | 90010 | `ClanSendChatResponse` | get_Protocol, .ctor |
| 23 | 21016 | `CraftSavePresetNameResponse` | get_Protocol, .ctor |
| 24 | 43010 | `FriendCheckResponse` | get_Protocol, .ctor |
| 25 | 43004 | `FriendSetIdCardResponse` | get_Protocol, .ctor |
| 26 | 12003 | `MemoryLobbyInteractResponse` | get_Protocol, .ctor |
| 27 | 12002 | `MemoryLobbyUpdateLobbyModeResponse` | get_Protocol, .ctor |
| 28 | 35027 | `MiniGameDefenseEnterBattleResponse` | get_Protocol, .ctor |
| 29 | 35001 | `MiniGameEnterStageResponse` | get_Protocol, .ctor |
| 30 | 35002 | `MiniGameResultResponse` | get_Protocol, .ctor |
| 31 | 35007 | `MiniGameShootingBattleEnterResponse` | get_Protocol, .ctor |
| 32 | 8005 | `MissionSyncResponse` | get_Protocol, .ctor |
| 33 | 53000 | `OptionSaveResponse` | get_Protocol, .ctor |
| 34 | 54003 | `PermanentRaidGiveUpResponse` | get_Protocol, .ctor |
| 35 | 37001 | `ProofTokenSubmitResponse` | get_Protocol, .ctor |
| 36 | 19005 | `ScenarioAccountStudentChangeResponse` | get_Protocol, .ctor |
| 37 | 19008 | `ScenarioEnterResponse` | get_Protocol, .ctor |
| 38 | 19015 | `ScenarioEnterTacticResponse` | get_Protocol, .ctor |
| 39 | 19006 | `ScenarioLobbyStudentChangeResponse` | get_Protocol, .ctor |
| 40 | 19004 | `ScenarioSelectResponse` | get_Protocol, .ctor |
| 41 | 19003 | `ScenarioSkipResponse` | get_Protocol, .ctor |
| 42 | 19020 | `ScenarioSkipMainStageResponse` | get_Protocol, .ctor |
| 43 | 19007 | `ScenarioSpecialLobbyChangeResponse` | get_Protocol, .ctor |
| 44 | 10015 | `ShopPickupSelectionGachaSetResponse` | get_Protocol, .ctor |

结论：国服客户端里这些响应确实没有字段，只需回基类 6 字段（生成器就是这么做的）。**不建议**用手册里的国际服字段硬填——那会引入客户端不认识的键。

另有 2 个响应**自身 0 字段、但继承自另一个响应 DTO**，它们不是空响应，生成时必须带上父类字段：

| 协议 | DTO | base | 继承字段数 |
|---|---|---|---|
| 1012 | `AccountAuth2Response` | `AccountAuthResponse` | 27 |
| 10016 | `ShopPickupSelectionGachaBuyResponse` | `ShopBuyGacha3Response` | 9 |

判据：`typeDefinition.q[4]`（父类型 typeIndex）→ 命中 `AccountAuthResponse` / `ShopBuyGacha3Response` 的 byval。全 444 个响应里只有这 3 条非同寻常的继承链：`AccountAuth2Response → AccountAuthResponse`、`ShopBuyGacha3Response → ShopBuyGacha2Response`、`ShopPickupSelectionGachaBuyResponse → ShopBuyGacha3Response`。（463/466 个 `MX.NetworkProtocol.*Response` 的 q[4] 都指向 ResponsePacket，口径自洽。）

### 2.3 support 类型里的 unknown 字段（264 个）

support = 被响应 DTO 间接引用、但自身不是协议响应的类型（DB 模型 / 战斗快照 / 管理等），共 250 个类型、1712 个字段。其中 264 个字段的 `typeIndex` 既没有 byval 命中、也没有任何 C# 声明投票（多为只在国服/战斗内部使用的泛型实例）。

**这些字段不在 444 个响应 DTO 的自有字段里**，不影响 §0 的覆盖率与 `--check`；生成时按字段名兜底（复数/Ids/DBs/List→`[]`，Dict/Map→`{}`，其余→`null`）。清单（前 40 条，完整见 `_full/report_facts.json`）：

| 类型 | 字段 | ti |
|---|---|---|
| `AcademyDB` | `ZoneVisitCharacterDBs` | 10463 |
| `ArenaTeamSettingDB` | `MainCharacters` | 18429 |
| `ArenaTeamSettingDB` | `SupportCharacters` | 18429 |
| `Battle` | `AllActiveCharacters` | 21550 |
| `Battle` | `AllAliveCharacters` | 21550 |
| `Battle` | `AuraSpawned` | 12012 |
| `Battle` | `BattleEntityNodeChanged` | 12038 |
| `Battle` | `BattleEntityRemoved` | 12017 |
| `Battle` | `BattleEntitySkillTriggered` | 12019 |
| `Battle` | `BattleEntitySpawned` | 12022 |
| `Battle` | `BattleItemActivated` | 12024 |
| `Battle` | `BattleItemEffected` | 12026 |
| `Battle` | `BattleItemRecognized` | 12028 |
| `Battle` | `BattleSectionChanged` | 12030 |
| `Battle` | `BeamCollided` | 12032 |
| `Battle` | `BeamSpawned` | 12032 |
| `Battle` | `CharacterDied` | 12089 |
| `Battle` | `CharacterDying` | 12089 |
| `Battle` | `CharacterFormConversion` | 12035 |
| `Battle` | `CharacterInteractWithTSS` | 12040 |
| `Battle` | `CharacterPhaseChanged` | 12043 |
| `Battle` | `CharacterRevived` | 12075 |
| `Battle` | `CoverPointOff` | 37734 |
| `Battle` | `DotAbilityAttached` | 12055 |
| `Battle` | `DotAbilityRemoved` | 12055 |
| `Battle` | `EffectAreaSpawned` | 12057 |
| `Battle` | `EffectCountLimit` | 50505 |
| `Battle` | `EntityMovedByMovingArea` | 12063 |
| `Battle` | `FindGiftClearGrade` | 12045 |
| `Battle` | `FindGiftEnded` | 12059 |
| `Battle` | `GameStateChanged` | 12071 |
| `Battle` | `GroupInitialized` | 12067 |
| `Battle` | `HideNPCWhenBattleEnd` | 37734 |
| `Battle` | `ImmuneHitBeforeTimeOutEnd` | 37734 |
| `Battle` | `LogicEffectExpired` | 12093 |
| `Battle` | `MovingAreaMoved` | 12100 |
| `Battle` | `NormalAttackHit` | 12104 |
| `Battle` | `NormalAttackSpawned` | 12106 |
| `Battle` | `ObstacleDestroyed` | 12111 |
| `Battle` | `ObstacleGroundNodeChanged` | 12111 |
| … | 共 264 条 | |

### 2.4 置信度分布（仅 444 个响应 DTO 的自有字段，共 1088 个）

| conf | 数量 | 含义 |
|---|---|---|
| high | 1044 | `ti-1 == byvalTypeIndex` 直接命中，或 C# 声明全票一致（≥2 票） |
| mid | 44 | 投票 ≥80% 一致，或"抓包 + 源码"双证据（StaticOpenConditions / List<object> 按名还原） |
| low | 0 | 无（所有自有字段至少 mid） |
| none | 0 | 无（已清零） |

### 2.5 额外恢复的协议映射（13 条，超出 444 口径，不计入覆盖率）

`protocol_map.json` 里有 57 条协议 `resp=null`。其中 13 条能用**严格名字规则**从 metadata 反查出响应类，已写入 `work/ba/proto/protocol_extras.json`，并由 `gen_full.py` 一并支持（`--check` 覆盖 457 条）：

| 协议号 | 协议 | 响应 DTO | 证据 |
|---|---|---|---|
| 27000 | ContentSweep_Request | `ContentSweepResponse` | req-name |
| 5001 | Echelon_Save | `EchelonSaveResponse` | req-name |
| 45010 | EliminateRaid_RankingReward | `EliminateRaidRankingRewardResponse` | req-name |
| 45009 | EliminateRaid_SeasonReward | `EliminateRaidSeasonRewardResponse` | req-name |
| 45008 | EliminateRaid_Sweep | `EliminateRaidSweepResponse` | protocol-name |
| 3002 | Equipment_Equip | `EquipmentItemEquipResponse` | equipment-family |
| 3003 | Equipment_LevelUp | `EquipmentItemLevelUpResponse` | equipment-family |
| 3000 | Equipment_List | `EquipmentItemListResponse` | equipment-family |
| 3005 | Equipment_Lock | `EquipmentItemLockResponse` | equipment-family |
| 3001 | Equipment_Sell | `EquipmentItemSellResponse` | equipment-family |
| 3004 | Equipment_TierUp | `EquipmentItemTierUpResponse` | equipment-family |
| 43005 | Friend_Search | `FriendSearchResponse` | protocol-name |
| 8000 | Mission_List | `MissionListResponse` | protocol-name |

剩下的 44 条协议（Attendance/Craft/Event/Conquest 等）名字对不上唯一响应类，**不猜**，保持 `resp=null`。

## §3 泛型与不确定项汇总

### 3.1 泛型实例（metadata 没有实例表，只能投票/推断）

响应 DTO 自有字段里，`ti-1` 命中 byval 的 725 个是"直接证据"；其余 **346 个字段 / 124 个 distinct typeIndex** 属于泛型实例，靠以下三类证据：

- `vote(n,ratio)`：拿 `shittim_types.json`（821 条 C# DTO 声明）+ 已有 schema，对全部 `(类.字段)→typeIndex` 投票；346 个字段属于此类。
- `manual:*`：report/65 等前序人工裁定，11 个字段。
- `infer:*`：无投票时按使用处/形态推断，3 个字段（`ClanChatRecordsResponse.ChatRecords` = `List<ClanChatDB>`，证据：同 ti 被 `UIClanLobby.clanChatDBList` 使用）。

**全部投票一致率**：124 个泛型 ti 中，84 个达到全票一致（conf=high），40 个 ≥80%（mid），0 个 low。

### 3.2 需要点名的推断（Top 25，按使用次数）

| ti | 类型 | 用于 | conf | 证据 |
|---|---|---|---|---|
| 10118 | `Dictionary<CurrencyTypes,long>` | 1 处（AccountCurrencySyncResponse.ExpiredCurrency） | high | `vote(7,1.00)` |
| 10388 | `Dictionary<long,List<ConquestTileDB>>` | 1 处（OpenConditionEventListResponse.ConquestTiles） | mid | `vote(1,1.00)` |
| 10425 | `Dictionary<long,List<long>>` | 2 处（MomoTalkOutLineResponse.FavorScheduleRecords, MomoTalkFavorScheduleResponse.FavorScheduleRecords） | high | `vote(5,1.00)` |
| 10448 | `Dictionary<long,List<ParcelInfo>>` | 4 处（EventContentCardShopListResponse.RewardHistory, EventContentCardShopPurchaseAllResponse.RewardHistory） | high | `vote(5,1.00)` |
| 10465 | `Dictionary<long,List<WorldRaidBossGroup>>` | 1 处（WorldRaidLobbyResponse.BossGroups） | mid | `vote(1,1.00)` |
| 10467 | `Dictionary<long,List<WorldRaidLocalBossDB>>` | 1 处（OpenConditionEventListResponse.WorldRaidLocalBossDBs） | mid | `vote(1,1.00)` |
| 10683 | `Dictionary<long,long>` | 7 处（AuditGachaStatisticsResponse.GachaResult, EliminateRaidLoginResponse.SweepPointByRaidUniqueId） | high | `vote(17,1.00)` |
| 10782 | `Dictionary<long,TimeAttackDungeonRoomDB>` | 1 处（TimeAttackDungeonLobbyResponse.RoomDBs） | mid | `vote(1,1.00)` |
| 10890 | `Dictionary<RewardTag,List<ParcelInfo>>` | 2 处（ConquestMainStoryConquerWithBattleResultResponse.DisplayParcelByRewardTag, ConquestConquerWithBattleResultResponse.DisplayParcelByRewardTag） | high | `vote(2,1.00)` |
| 10922 | `Dictionary<SkillSlot,int>` | 1 处（WorldRaidUpdateCarrierSkillResponse.CarrierSkills） | high | `vote(2,1.00)` |
| 10935 | `Dictionary<StageDifficulty,int>` | 2 处（ConquestGetInfoResponse.DifficultyToStepDict, ConquestMainStoryGetInfoResponse.DifficultyToStepDict） | high | `vote(2,1.00)` |
| 10977 | `Dictionary<string,List<RaidTeamSettingDB>>` | 1 处（EliminateRaidGetBestTeamResponse.RaidTeamSettingDBsDict） | mid | `vote(1,1.00)` |
| 16346 | `List<AttendanceBookReward>` | 1 处（AccountAuthResponse.AttendanceBookRewards） | high | `vote(2,1.00)` |
| 16349 | `List<AttendanceHistoryDB>` | 1 处（AccountAuthResponse.AttendanceHistoryDBs） | high | `vote(2,1.00)` |
| 16500 | `List<ConquestDisplayInfo>` | 9 处（ConquestConquerResponse.DisplayInfos, ConquestGetInfoResponse.DisplayInfos） | high | `vote(9,1.00)` |
| 16620 | `List<EventContentCollectionDB>` | 1 处（EventContentLocationAttendScheduleResponse.EventContentCollectionDBs） | mid | `vote(1,1.00)` |
| 16826 | `List<IssueAlertInfoDB>` | 1 处（AccountAuthResponse.IssueAlertInfos） | high | `vote(2,1.00)` |
| 16967 | `List<MultiSweepPresetDB>` | 3 处（ContentSweepSetMultiSweepPresetNameResponse.MultiSweepPresetDBs, ContentSweepMultiSweepPresetListResponse.MultiSweepPresetDBs） | high | `vote(4,1.00)` |
| 16993 | `List<ParcelInfo>` | 6 处（AccountAuthResponse.MonthlyProductParcel, AccountAuthResponse.MonthlyProductMail） | high | `vote(12,1.00)` |
| 17028 | `List<PurchaseCountDB>` | 1 处（AccountAuthResponse.RepurchasableMonthlyProductCountDBs） | high | `vote(2,1.00)` |
| 17145 | `List<StickerDB>` | 1 处（StickerLobbyResponse.ReceivedStickerDBs） | high | `vote(3,1.00)` |
| 21132 | `List<List<ClearDeckDB>>` | 1 处（ClearDeckGroupedListResponse.ClearDeckGroupedDBs） | mid | `vote(1,1.00)` |
| 21145 | `List<List<ParcelInfo>>` | 8 处（MiniGameShootingSweepResponse.Rewards, TimeAttackDungeonSweepResponse.Rewards） | high | `vote(11,1.00)` |
| 21273 | `List<AcademyLocationDB>` | 1 处（AcademyGetInfoResponse.AcademyLocationDBs） | high | `vote(4,1.00)` |
| 21284 | `List<AccountLimitedFlashSaleDB>` | 1 处（AccountAuthResponse.AccountLimitedFlashSaleDBs） | mid | `infer:field-name→AccountLimitedFlashSaleDB` |

### 3.3 三处"实证纠正"（自动推断会错、靠抓包/源码纠回来）

1. **`ResponsePacket.StaticOpenConditions`：不是 `List<OpenConditionDB>`，是字典。**
   - 真实抓包（report/36 §4）：dict，55 个内容枚举键，值全 0；
   - Shittim 源码（report/28）：`public Dictionary<OpenConditionContent, OpenConditionLockReason>? StaticOpenConditions`；
   - 本表的处理：类型记为 `Dictionary<OpenConditionContent,OpenConditionLockReason>`，生成器默认输出实抓的 55 键全 0 对象（不是 `[]`）。
2. **`BasisPoint` 的线上形态只有 `rawValue`。**
   - 实抓样例（report/36 §5）：`"Multiplier":{"rawValue":10000}`；
   - metadata 里同类型的 `Multiplier/OneOver10_4/Zero/One/Epsilon` 多为成员/静态常量，不参与序列化；本表只保留 `rawValue: long`。
3. **`List<object>` 按字段名还原成具体 DB 类型。**
   - `AccountAuthResponse.DailyRecordDBs`：Shittim 源码写的是 `IEnumerable<object>?`，但国服 metadata 有 `MX.GameLogic.DBModel.DailyRecordDB`；本表还原为 `List<DailyRecordDB>`。
   - 同理 `AccountLimitedFlashSaleDBs` → `List<AccountLimitedFlashSaleDB>`。

### 3.4 国服 vs Shittim 源码的字段差异（不能拿国际服声明当权威）

- metadata 有、Shittim 没有的类：**40 个**（国服更新的字段）；
- Shittim 有、国服 metadata 没有的类：**13 个**（国际服旧字段/被移除）。

因此本表**字段名一律以国服 metadata 为准**，Shittim 只用于泛型类型投票。前 12 个"国服新增字段"：

| 类 | 国服新增字段 |
|---|---|
| `AccountAuthResponse` | `IsNew`, `Desc`, `FunctionClose` |
| `AccountLoginSyncResponse` | `BillingPurchaseListByYostarResponse` |
| `ArenaEnterBattlePart2Response` | `BattleServerError` |
| `ArenaEnterLobbyResponse` | `IsServerRunBattle` |
| `CampaignEnterSubStageResponse` | `RandomSeed` |
| `EliminateRaidCreateBattleResponse` | `BattleSetting` |
| `EliminateRaidEnterBattleResponse` | `BattleSetting` |
| `EventContentEnterMainGroundStageResponse` | `RandomSeed` |
| `EventContentEnterSubStageResponse` | `RandomSeed` |
| `MultiFloorRaidEnterBattleResponse` | `BattleSetting` |
| `RaidCreateBattleResponse` | `BattleSetting` |
| `RaidEnterBattleResponse` | `BattleSetting` |

另：90xxx 段共 7 个 DTO（ClanChatRecordsResponse, ClanSendChatResponse, ManagementDataResponse, ShopBuyTutorialGachaResponse, ShopConfirmTutorialGachaResponse, ShopListTutorialGachaResponse, ShopSaveTutorialGachaResponse），在 Shittim 的协议表与类型声明里**都不存在**，属国服特供/重编号，全部按 metadata 提取。其中 `ManagementData` 的 9 个字段（`Notices/Events/Issues/Banners/GachaProbabilityDisplay/ContentLock/GachaPeriodDisplay/RaidPeriodDisplay/GuidePopup`）没有任何外部证据（无 byval、无投票、无抓包），保持 `unknown`，未臆造。

### 3.5 拿不到的东西（诚实声明）

- **字段偏移拿不到**：本版 metadata 的 `FieldDefinition` 只有 name/typeIndex/token 三个 uint32，没有 FieldOffsets；字段顺序 = 声明顺序。对 JSON 协议无影响。
- **泛型实例表拿不到**：`List<X>`/`Dictionary<K,V>` 的 ti 不在 typeDefinition 表里，只能投票（见 3.1）。
- **static/const 与实例字段无法从 metadata 区分**：只按名字剔除 `Zero/One/Epsilon/MaxValue/...`（记录在条目的 `staticSkipped` 里），BasisPoint 另行人工裁定。
- **metadata 字符串是逐串随机单字节 XOR**：类型名/字段名区恰好可用；但"在 md_deob 里搜不到某串"不能证明它不存在（要搜必须用 256 key 反向搜索法 `report/_tmp/meta/s27_revsearch.py`）。本次已从**原始文件**独立重建并逐字节比对 md_deob（sha256 `245d6e3b…`），证明副本可信。

## §4 `gen_full.py` 用法

```powershell
cd C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\proto

python gen_full.py --list                    # 列出 444 条协议：协议号 / DTO / 段 / 字段数 / 协议名
python gen_full.py --list --segment 2000     # 只看 2xxx 段
python gen_full.py --protocol 24000          # 输出完整响应包（Protocol 信封 + 基类 6 字段 + 自有字段）
python gen_full.py --dto AcademyDB           # 只输出某个类型的默认体（支持 support 类型）
python gen_full.py --protocol 1017 --out 1017.json --indent 2
python gen_full.py --check                   # 自检全部 444 条协议（必须 exit 0）
python gen_full.py --check --segment 2000    # 只查某段
python gen_full.py --missing                 # 报告仍缺的 DTO（当前 0）
python gen_full.py --protocol 1017 --deep    # 嵌套对象递归到底（默认只到 3 层）
python gen_full.py --protocol 1017 --shallow # 嵌套对象给 {}
python gen_full.py --protocol 1017 --now-ticks  # ServerTimeTicks 用当前时间
```

默认值约定：`string`→`""`、`bool`→`false`、整数→`0`、`DateTime`→`"2026-11-14T00:00:00"`（无时区）、枚举→`0`、`List<T>`→`[]`、`Dictionary<K,V>`→`{}`、`Nullable<T>`→`null`、未知泛型按字段名兜底。

`--check` 的判据：每个协议都要 ①`json.dumps/loads` 成功 ②`Protocol` 信封正确 ③含基类 6 字段 ④自有字段齐全且 JSON 类型与 schema 的 kind 相符 ⑤没有 `unknown` 类型的字段。当前：**457/457 通过（444 具名 + 13 额外恢复），exit 0**。

示例输出（`--protocol 24000`，节选）：
```json
{
  "Protocol": 24000,
  "ServerTimeTicks": 639302112000000000,
  "ServerNotification": 0,
  "MissionProgressDBs": [],
  "EventMissionProgressDBDict": {},
  "BattlePassMissionProgressDBDict": {},
  "StaticOpenConditions": { "Shop": 0, "Gacha": 0, ... 共 55 键 ... },
  "AcademyDB": { "LastUpdate": "2026-11-14T00:00:00", "ZoneVisitCharacterDBs": [], "ZoneScheduleGroupRecords": {} },
  "AcademyLocationDBs": []
}
```

12 条代表性协议的完整响应包已生成到 `work/ba/proto/_full/samples/`（`python _full/make_samples.py` 可重跑）：
1001 普通嵌套 / 1002 27 字段 / 1012 仅继承 / 1017 38 键 / 2000 List<CharacterDB> / 24000 Academy / 3000 与 5001 与 27000 额外恢复映射 / 10005 普通 / 10016 两层继承 / 90010 真·空响应（7 键）。

## §5 复现方法（全部本地、只读输入）

```powershell
cd C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\proto

# 0) 工作清单（444 个 resp DTO、按段缺口）
python _full\worklist.py                       # -> _full/worklist.json

# 1) metadata 驱动提取：草稿 / 泛型裁定表 / support 类型
python _full\extract_core.py --stats
python _full\extract_core.py --dump-all        # -> _full/draft/seg_*.json
python _full\extract_core.py --generic-map     # -> _full/generic_map.json
python _full\extract_core.py --support --inner # -> _full/support_types.json

# 2) 分段校对产物（每个分段一个文件，互不重叠）
python _full\make_seg.py --segs 1 --out _full\seg_1.json
python _full\verify_seg.py --segs 1 --file _full\seg_1.json

# 3) 合并 + 自检
python _full\merge_full.py                     # -> dto_schema_full.json
python gen_full.py --check --quiet              # 必须 exit 0

# 4) 独立验证（不信任 md_deob：从原始 global-metadata.dat 重建并逐字节比对）
python _full\verify_raw_metadata.py

# 5) 验收总检（四条验收标准一次跑完）
python _full\final_check.py
```

`final_check.py` 的当前输出：

```
== 1) 规模 ==
   schema 类型      : 707
   具名 resp DTO    : 444（protocol_map 口径）
   额外恢复映射     : 13
   support 类型     : 250
== 2) 覆盖率 / 字段表 ==
   缺 DTO           : 0
   字段表与 metadata 不一致: 0
== 3) 逐协议生成 + json 往返 + 基类 6 字段 ==
   协议数 457，失败 0，真·空响应 44
== 4) gen_full.py --check ==
   exit code        : 0 （通过）
== 5) 覆盖口径 ==
   已提取           : 444/444 = 100.0%
   非空字段表       : 400（398 个自有 + 2 个仅继承）
   真·空响应        : 44
---- final_check: PASS ----
```

证据链：
- 原始 metadata 按「头 0x120 字节 XOR 0x66 + 每 64KB 的 [0x1000,0x5000) XOR 0x66」重建 → 与 `md_deob.bin` **逐字节相同**（sha256 `245d6e3b…`），并用重建结果独立复算 60 个 DTO 字段表，与 schema **0 差异**。
- 已有 34 个 DTO 与本次自动提取字段表 **0 差异**。
- 真实 1017 抓包（`out/1017_Account_LoginSync.json`）37 个顶层键与 `AccountLoginSyncResponse` 的 37 个字段**一一对应**（多出的 `Responses` 是转发层包装，不是 DTO 字段）。
- 与 `shittim_types.json` 的 **1051 个同名字段**做类型归一比对：仅 **5 处**差异，全部可解释为区服版本差异——`OptionDB`（国际服 `Dictionary<string,object>` → 国服类）、`DailyRecordDBs`/`AccountLimitedFlashSaleDBs`（`IEnumerable<object>` → 具体 DB）、`Responses`（单对象 → `List<ResponsePacket>`）、`PurchaseOrderId`（long → string）。

## 附录 A：444 个 Response DTO 明细

`字段数=0` 且标 `empty` 的是真·空响应（§2.2）；`conf` 列是该 DTO 自有字段里最低的一档。

| 协议 | 协议名 | DTO | 段 | 字段数 | 最低置信度 | 状态 |
|---|---|---|---|---|---|---|
| 1000 | Account_Create | `AccountCreateResponse` | 1 | 0 | - | empty(已验) |
| 1001 | Account_Nickname | `AccountNicknameResponse` | 1 | 1 | high | OK |
| 1002 | Account_Auth | `AccountAuthResponse` | 1 | 27 | mid | OK |
| 1003 | Account_CurrencySync | `AccountCurrencySyncResponse` | 1 | 2 | high | OK |
| 1004 | Account_SetRepresentCharacterAndComment | `AccountSetRepresentCharacterAndCommentResponse` | 1 | 2 | high | OK |
| 1005 | Account_GetTutorial | `AccountGetTutorialResponse` | 1 | 1 | high | OK |
| 1006 | Account_SetTutorial | `AccountSetTutorialResponse` | 1 | 0 | - | empty(已验) |
| 1007 | Account_PassCheck | `AccountPassCheckResponse` | 1 | 4 | high | OK |
| 1009 | Account_CheckYostar | `AccountCheckYostarResponse` | 1 | 7 | high | OK |
| 1010 | Account_CallName | `AccountCallNameResponse` | 1 | 1 | high | OK |
| 1011 | Account_BirthDay | `AccountBirthDayResponse` | 1 | 1 | high | OK |
| 1012 | Account_Auth2 | `AccountAuth2Response` | 1 | 27 | high | OK |
| 1013 | Account_LinkReward | `AccountLinkRewardResponse` | 1 | 0 | - | empty(已验) |
| 1014 | Account_ReportXignCodeCheater | `AccountReportXignCodeCheaterResponse` | 1 | 0 | - | empty(已验) |
| 1015 | Account_DismissRepurchasablePopup | `AccountDismissRepurchasablePopupResponse` | 1 | 0 | - | empty(已验) |
| 1016 | Account_InvalidateToken | `AccountInvalidateTokenResponse` | 1 | 0 | - | empty(已验) |
| 1017 | Account_LoginSync | `AccountLoginSyncResponse` | 1 | 31 | mid | OK |
| 1018 | Account_Reset | `AccountResetResponse` | 1 | 0 | - | empty(已验) |
| 1019 | Account_RequestBirthdayMail | `AccountRequestBirthdayMailResponse` | 1 | 0 | - | empty(已验) |
| 2000 | Character_List | `CharacterListResponse` | 2 | 4 | high | OK |
| 2001 | Character_Transcendence | `CharacterTranscendenceResponse` | 2 | 2 | high | OK |
| 2002 | Character_ExpGrowth | `CharacterExpGrowthResponse` | 2 | 3 | high | OK |
| 2003 | Character_FavorGrowth | `CharacterFavorGrowthResponse` | 2 | 3 | high | OK |
| 2005 | Character_UnlockWeapon | `CharacterUnlockWeaponResponse` | 2 | 1 | high | OK |
| 2006 | Character_WeaponExpGrowth | `CharacterWeaponExpGrowthResponse` | 2 | 1 | high | OK |
| 2007 | Character_WeaponTranscendence | `CharacterWeaponTranscendenceResponse` | 2 | 1 | high | OK |
| 2008 | Character_SetFavorites | `CharacterSetFavoritesResponse` | 2 | 1 | high | OK |
| 2009 | Character_SetCostume | `CharacterSetCostumeResponse` | 2 | 2 | high | OK |
| 2010 | Character_BatchSkillLevelUpdate | `CharacterBatchSkillLevelUpdateResponse` | 2 | 2 | high | OK |
| 2011 | Character_PotentialGrowth | `CharacterPotentialGrowthResponse` | 2 | 2 | high | OK |
| 3006 | Equipment_BatchGrowth | `EquipmentBatchGrowthResponse` | 3 | 4 | high | OK |
| 4000 | Item_List | `ItemListResponse` | 4 | 2 | high | OK |
| 4001 | Item_Sell | `ItemSellResponse` | 4 | 1 | high | OK |
| 4002 | Item_Consume | `ItemConsumeResponse` | 4 | 2 | high | OK |
| 4003 | Item_Lock | `ItemLockResponse` | 4 | 1 | high | OK |
| 4004 | Item_BulkConsume | `ItemBulkConsumeResponse` | 4 | 2 | high | OK |
| 4005 | Item_SelectTicket | `ItemSelectTicketResponse` | 4 | 2 | high | OK |
| 4006 | Item_AutoSynth | `ItemAutoSynthResponse` | 4 | 1 | high | OK |
| 5000 | Echelon_List | `EchelonListResponse` | 5 | 2 | high | OK |
| 5002 | Echelon_PresetList | `EchelonPresetListResponse` | 5 | 1 | high | OK |
| 5003 | Echelon_PresetSave | `EchelonPresetSaveResponse` | 5 | 1 | high | OK |
| 5004 | Echelon_PresetGroupRename | `EchelonPresetGroupRenameResponse` | 5 | 1 | high | OK |
| 6000 | Campaign_List | `CampaignListResponse` | 6 | 3 | high | OK |
| 6001 | Campaign_EnterMainStage | `CampaignEnterMainStageResponse` | 6 | 1 | high | OK |
| 6002 | Campaign_ConfirmMainStage | `CampaignConfirmMainStageResponse` | 6 | 2 | high | OK |
| 6003 | Campaign_DeployEchelon | `CampaignDeployEchelonResponse` | 6 | 1 | high | OK |
| 6004 | Campaign_WithdrawEchelon | `CampaignWithdrawEchelonResponse` | 6 | 2 | high | OK |
| 6005 | Campaign_MapMove | `CampaignMapMoveResponse` | 6 | 4 | high | OK |
| 6006 | Campaign_EndTurn | `CampaignEndTurnResponse` | 6 | 2 | high | OK |
| 6007 | Campaign_EnterTactic | `CampaignEnterTacticResponse` | 6 | 1 | high | OK |
| 6008 | Campaign_TacticResult | `CampaignTacticResultResponse` | 6 | 9 | high | OK |
| 6009 | Campaign_Retreat | `CampaignRetreatResponse` | 6 | 2 | high | OK |
| 6010 | Campaign_ChapterClearReward | `CampaignChapterClearRewardResponse` | 6 | 2 | high | OK |
| 6011 | Campaign_Heal | `CampaignHealResponse` | 6 | 2 | high | OK |
| 6012 | Campaign_EnterSubStage | `CampaignEnterSubStageResponse` | 6 | 3 | high | OK |
| 6013 | Campaign_SubStageResult | `CampaignSubStageResultResponse` | 6 | 6 | high | OK |
| 6014 | Campaign_Portal | `CampaignPortalResponse` | 6 | 1 | high | OK |
| 6015 | Campaign_ConfirmTutorialStage | `CampaignConfirmTutorialStageResponse` | 6 | 1 | high | OK |
| 6016 | Campaign_PurchasePlayCountHardStage | `CampaignPurchasePlayCountHardStageResponse` | 6 | 2 | high | OK |
| 6017 | Campaign_EnterTutorialStage | `CampaignEnterTutorialStageResponse` | 6 | 2 | high | OK |
| 6018 | Campaign_TutorialStageResult | `CampaignTutorialStageResultResponse` | 6 | 4 | high | OK |
| 6019 | Campaign_RestartMainStage | `CampaignRestartMainStageResponse` | 6 | 2 | high | OK |
| 6020 | Campaign_EnterMainStageStrategySkip | `CampaignEnterMainStageStrategySkipResponse` | 6 | 1 | high | OK |
| 6021 | Campaign_MainStageStrategySkipResult | `CampaignMainStageStrategySkipResultResponse` | 6 | 6 | high | OK |
| 7000 | Mail_List | `MailListResponse` | 7 | 2 | high | OK |
| 7001 | Mail_Check | `MailCheckResponse` | 7 | 1 | high | OK |
| 7002 | Mail_Receive | `MailReceiveResponse` | 7 | 3 | high | OK |
| 7003 | Mail_ListSemiPermanent | `MailListSemiPermanentResponse` | 7 | 2 | high | OK |
| 7004 | Mail_ReceiveSemiPermanent | `MailReceiveSemiPermanentResponse` | 7 | 7 | high | OK |
| 8001 | Mission_Reward | `MissionRewardResponse` | 8 | 2 | high | OK |
| 8002 | Mission_MultipleReward | `MissionMultipleRewardResponse` | 8 | 2 | high | OK |
| 8005 | Mission_Sync | `MissionSyncResponse` | 8 | 0 | - | empty(已验) |
| 9002 | Attendance_Reward | `AttendanceRewardResponse` | 9 | 3 | high | OK |
| 10000 | Shop_BuyMerchandise | `ShopBuyMerchandiseResponse` | 10 | 5 | high | OK |
| 10001 | Shop_BuyGacha | `ShopBuyGachaResponse` | 10 | 2 | high | OK |
| 10002 | Shop_List | `ShopListResponse` | 10 | 2 | high | OK |
| 10003 | Shop_Refresh | `ShopRefreshResponse` | 10 | 2 | high | OK |
| 10004 | Shop_BuyEligma | `ShopBuyEligmaResponse` | 10 | 3 | high | OK |
| 10005 | Shop_BuyGacha2 | `ShopBuyGacha2Response` | 10 | 7 | high | OK |
| 10006 | Shop_GachaRecruitList | `ShopGachaRecruitListResponse` | 10 | 2 | high | OK |
| 10007 | Shop_BuyRefreshMerchandise | `ShopBuyRefreshMerchandiseResponse` | 10 | 5 | high | OK |
| 10008 | Shop_BuyGacha3 | `ShopBuyGacha3Response` | 10 | 9 | high | OK |
| 10009 | Shop_BuyAP | `ShopBuyAPResponse` | 10 | 5 | high | OK |
| 10010 | Shop_BeforehandGachaGet | `ShopBeforehandGachaGetResponse` | 10 | 2 | high | OK |
| 10011 | Shop_BeforehandGachaRun | `ShopBeforehandGachaRunResponse` | 10 | 1 | high | OK |
| 10012 | Shop_BeforehandGachaSave | `ShopBeforehandGachaSaveResponse` | 10 | 1 | high | OK |
| 10013 | Shop_BeforehandGachaPick | `ShopBeforehandGachaPickResponse` | 10 | 2 | high | OK |
| 10014 | Shop_PickupSelectionGachaGet | `ShopPickupSelectionGachaGetResponse` | 10 | 1 | high | OK |
| 10015 | Shop_PickupSelectionGachaSet | `ShopPickupSelectionGachaSetResponse` | 10 | 0 | - | empty(已验) |
| 10016 | Shop_PickupSelectionGachaBuy | `ShopPickupSelectionGachaBuyResponse` | 10 | 9 | high | OK |
| 11000 | Recipe_Craft | `RecipeCraftResponse` | 11 | 3 | high | OK |
| 12000 | MemoryLobby_List | `MemoryLobbyListResponse` | 12 | 1 | high | OK |
| 12001 | MemoryLobby_SetMain | `MemoryLobbySetMainResponse` | 12 | 1 | high | OK |
| 12002 | MemoryLobby_UpdateLobbyMode | `MemoryLobbyUpdateLobbyModeResponse` | 12 | 0 | - | empty(已验) |
| 12003 | MemoryLobby_Interact | `MemoryLobbyInteractResponse` | 12 | 0 | - | empty(已验) |
| 15000 | OpenCondition_List | `OpenConditionListResponse` | 15 | 1 | mid | OK |
| 15001 | OpenCondition_Set | `OpenConditionSetResponse` | 15 | 1 | mid | OK |
| 15002 | OpenCondition_EventList | `OpenConditionEventListResponse` | 15 | 2 | mid | OK |
| 16000 | Toast_List | `ToastListResponse` | 16 | 1 | mid | OK |
| 17000 | Raid_List | `RaidListResponse` | 17 | 3 | high | OK |
| 17001 | Raid_CompleteList | `RaidCompleteListResponse` | 17 | 4 | high | OK |
| 17002 | Raid_Detail | `RaidDetailResponse` | 17 | 2 | high | OK |
| 17003 | Raid_Search | `RaidSearchResponse` | 17 | 1 | high | OK |
| 17004 | Raid_CreateBattle | `RaidCreateBattleResponse` | 17 | 5 | high | OK |
| 17005 | Raid_EnterBattle | `RaidEnterBattleResponse` | 17 | 5 | high | OK |
| 17006 | Raid_BattleUpdate | `RaidBattleUpdateResponse` | 17 | 1 | high | OK |
| 17007 | Raid_EndBattle | `RaidEndBattleResponse` | 17 | 6 | high | OK |
| 17008 | Raid_Reward | `RaidRewardResponse` | 17 | 3 | high | OK |
| 17009 | Raid_RewardAll | `RaidRewardAllResponse` | 17 | 1 | high | OK |
| 17011 | Raid_Share | `RaidShareResponse` | 17 | 1 | high | OK |
| 17013 | Raid_SeasonReward | `RaidSeasonRewardResponse` | 17 | 2 | high | OK |
| 17014 | Raid_Lobby | `RaidLobbyResponse` | 17 | 5 | high | OK |
| 17015 | Raid_GiveUp | `RaidGiveUpResponse` | 17 | 3 | high | OK |
| 17016 | Raid_OpponentList | `RaidOpponentListResponse` | 17 | 1 | mid | OK |
| 17017 | Raid_RankingReward | `RaidRankingRewardResponse` | 17 | 2 | high | OK |
| 17018 | Raid_Login | `RaidLoginResponse` | 17 | 4 | high | OK |
| 17019 | Raid_Sweep | `RaidSweepResponse` | 17 | 3 | high | OK |
| 17020 | Raid_GetBestTeam | `RaidGetBestTeamResponse` | 17 | 1 | mid | OK |
| 17021 | Raid_RankingIndex | `RaidRankingIndexResponse` | 17 | 1 | high | OK |
| 18000 | SkipHistory_List | `SkipHistoryListResponse` | 18 | 1 | high | OK |
| 18001 | SkipHistory_Save | `SkipHistorySaveResponse` | 18 | 1 | high | OK |
| 19000 | Scenario_List | `ScenarioListResponse` | 19 | 3 | high | OK |
| 19001 | Scenario_Clear | `ScenarioClearResponse` | 19 | 3 | high | OK |
| 19002 | Scenario_GroupHistoryUpdate | `ScenarioGroupHistoryUpdateResponse` | 19 | 1 | high | OK |
| 19003 | Scenario_Skip | `ScenarioSkipResponse` | 19 | 0 | - | empty(已验) |
| 19004 | Scenario_Select | `ScenarioSelectResponse` | 19 | 0 | - | empty(已验) |
| 19005 | Scenario_AccountStudentChange | `ScenarioAccountStudentChangeResponse` | 19 | 0 | - | empty(已验) |
| 19006 | Scenario_LobbyStudentChange | `ScenarioLobbyStudentChangeResponse` | 19 | 0 | - | empty(已验) |
| 19007 | Scenario_SpecialLobbyChange | `ScenarioSpecialLobbyChangeResponse` | 19 | 0 | - | empty(已验) |
| 19008 | Scenario_Enter | `ScenarioEnterResponse` | 19 | 0 | - | empty(已验) |
| 19009 | Scenario_EnterMainStage | `ScenarioEnterMainStageResponse` | 19 | 1 | high | OK |
| 19010 | Scenario_ConfirmMainStage | `ScenarioConfirmMainStageResponse` | 19 | 3 | high | OK |
| 19011 | Scenario_DeployEchelon | `ScenarioDeployEchelonResponse` | 19 | 1 | high | OK |
| 19012 | Scenario_WithdrawEchelon | `ScenarioWithdrawEchelonResponse` | 19 | 2 | high | OK |
| 19013 | Scenario_MapMove | `ScenarioMapMoveResponse` | 19 | 5 | high | OK |
| 19014 | Scenario_EndTurn | `ScenarioEndTurnResponse` | 19 | 3 | high | OK |
| 19015 | Scenario_EnterTactic | `ScenarioEnterTacticResponse` | 19 | 0 | - | empty(已验) |
| 19016 | Scenario_TacticResult | `ScenarioTacticResultResponse` | 19 | 4 | high | OK |
| 19017 | Scenario_Retreat | `ScenarioRetreatResponse` | 19 | 2 | high | OK |
| 19018 | Scenario_Portal | `ScenarioPortalResponse` | 19 | 2 | high | OK |
| 19019 | Scenario_RestartMainStage | `ScenarioRestartMainStageResponse` | 19 | 2 | high | OK |
| 19020 | Scenario_SkipMainStage | `ScenarioSkipMainStageResponse` | 19 | 0 | - | empty(已验) |
| 20000 | Cafe_Get | `CafeGetInfoResponse` | 20 | 3 | high | OK |
| 20001 | Cafe_Ack | `CafeAckResponse` | 20 | 1 | high | OK |
| 20002 | Cafe_Deploy | `CafeDeployFurnitureResponse` | 20 | 3 | high | OK |
| 20003 | Cafe_Relocate | `CafeRelocateFurnitureResponse` | 20 | 2 | high | OK |
| 20004 | Cafe_Remove | `CafeRemoveFurnitureResponse` | 20 | 2 | high | OK |
| 20005 | Cafe_RemoveAll | `CafeRemoveAllFurnitureResponse` | 20 | 2 | high | OK |
| 20006 | Cafe_Interact | `CafeInteractWithCharacterResponse` | 20 | 3 | high | OK |
| 20007 | Cafe_ListPreset | `CafeListPresetResponse` | 20 | 2 | high | OK |
| 20008 | Cafe_RenamePreset | `CafeRenamePresetResponse` | 20 | 0 | - | empty(已验) |
| 20009 | Cafe_ClearPreset | `CafeClearPresetResponse` | 20 | 0 | - | empty(已验) |
| 20010 | Cafe_UpdatePresetFurniture | `CafeUpdatePresetFurnitureResponse` | 20 | 0 | - | empty(已验) |
| 20011 | Cafe_ApplyPreset | `CafeApplyPresetResponse` | 20 | 2 | high | OK |
| 20012 | Cafe_RankUp | `CafeRankUpResponse` | 20 | 3 | high | OK |
| 20013 | Cafe_ReceiveCurrency | `CafeReceiveCurrencyResponse` | 20 | 3 | high | OK |
| 20014 | Cafe_GiveGift | `CafeGiveGiftResponse` | 20 | 2 | high | OK |
| 20015 | Cafe_SummonCharacter | `CafeSummonCharacterResponse` | 20 | 2 | high | OK |
| 20016 | Cafe_TrophyHistory | `CafeTrophyHistoryResponse` | 20 | 1 | high | OK |
| 20017 | Cafe_ApplyTemplate | `CafeApplyTemplateResponse` | 20 | 2 | high | OK |
| 20018 | Cafe_Open | `CafeOpenResponse` | 20 | 2 | high | OK |
| 20019 | Cafe_Travel | `CafeTravelResponse` | 20 | 3 | high | OK |
| 20020 | Cafe_SummonCharacterTicketUse | `CafeSummonCharacterTicketUseResponse` | 20 | 3 | high | OK |
| 20021 | Cafe_PresetDetail | `CafePresetDetailResponse` | 20 | 1 | high | OK |
| 20022 | Cafe_UpdateCopyPresetFurniture | `CafeUpdateCopyPresetFurnitureResponse` | 20 | 0 | - | empty(已验) |
| 21001 | Craft_SelectNode | `CraftSelectNodeResponse` | 21 | 1 | high | OK |
| 21002 | Craft_UpdateNodeLevel | `CraftUpdateNodeLevelResponse` | 21 | 4 | high | OK |
| 21003 | Craft_BeginProcess | `CraftBeginProcessResponse` | 21 | 1 | high | OK |
| 21004 | Craft_CompleteProcess | `CraftCompleteProcessResponse` | 21 | 3 | high | OK |
| 21005 | Craft_Reward | `CraftRewardResponse` | 21 | 2 | high | OK |
| 21007 | Craft_ShiftingBeginProcess | `CraftShiftingBeginProcessResponse` | 21 | 2 | high | OK |
| 21008 | Craft_ShiftingCompleteProcess | `CraftShiftingCompleteProcessResponse` | 21 | 2 | high | OK |
| 21009 | Craft_ShiftingReward | `CraftShiftingRewardResponse` | 21 | 2 | high | OK |
| 21010 | Craft_AutoBeginProcess | `CraftAutoBeginProcessResponse` | 21 | 2 | high | OK |
| 21011 | Craft_CompleteProcessAll | `CraftCompleteProcessAllResponse` | 21 | 2 | high | OK |
| 21012 | Craft_RewardAll | `CraftRewardAllResponse` | 21 | 2 | high | OK |
| 21013 | Craft_ShiftingCompleteProcessAll | `CraftShiftingCompleteProcessAllResponse` | 21 | 2 | high | OK |
| 21014 | Craft_ShiftingRewardAll | `CraftShiftingRewardAllResponse` | 21 | 2 | high | OK |
| 21015 | Craft_SavePreset | `CraftSavePresetResponse` | 21 | 1 | high | OK |
| 21016 | Craft_SavePresetName | `CraftSavePresetNameResponse` | 21 | 0 | - | empty(已验) |
| 22000 | Arena_EnterLobby | `ArenaEnterLobbyResponse` | 22 | 5 | high | OK |
| 22001 | Arena_Login | `ArenaLoginResponse` | 22 | 1 | high | OK |
| 22002 | Arena_SettingChange | `ArenaSettingChangeResponse` | 22 | 0 | - | empty(已验) |
| 22003 | Arena_OpponentList | `ArenaOpponentListResponse` | 22 | 3 | high | OK |
| 22004 | Arena_EnterBattle | `ArenaEnterBattleResponse` | 22 | 6 | high | OK |
| 22005 | Arena_EnterBattlePart1 | `ArenaEnterBattlePart1Response` | 22 | 1 | high | OK |
| 22006 | Arena_EnterBattlePart2 | `ArenaEnterBattlePart2Response` | 22 | 7 | high | OK |
| 22007 | Arena_BattleResult | `ArenaBattleResultResponse` | 22 | 0 | - | empty(已验) |
| 22008 | Arena_CumulativeTimeReward | `ArenaCumulativeTimeRewardResponse` | 22 | 3 | high | OK |
| 22009 | Arena_DailyReward | `ArenaDailyRewardResponse` | 22 | 2 | high | OK |
| 22010 | Arena_RankList | `ArenaRankListResponse` | 22 | 1 | high | OK |
| 22011 | Arena_History | `ArenaHistoryResponse` | 22 | 2 | mid | OK |
| 22015 | Arena_CheckSeasonCloseReward | `ArenaCheckSeasonCloseRewardResponse` | 22 | 0 | - | empty(已验) |
| 22016 | Arena_SyncEchelonSettingTime | `ArenaSyncEchelonSettingTimeResponse` | 22 | 1 | high | OK |
| 22017 | Arena_SettingAnonymous | `ArenaSettingAnonymousResponse` | 22 | 0 | - | empty(已验) |
| 23000 | WeekDungeon_List | `WeekDungeonListResponse` | 23 | 2 | mid | OK |
| 23001 | WeekDungeon_EnterBattle | `WeekDungeonEnterBattleResponse` | 23 | 4 | high | OK |
| 23002 | WeekDungeon_BattleResult | `WeekDungeonBattleResultResponse` | 23 | 3 | high | OK |
| 23003 | WeekDungeon_Retreat | `WeekDungeonRetreatResponse` | 23 | 1 | high | OK |
| 24000 | Academy_GetInfo | `AcademyGetInfoResponse` | 24 | 2 | high | OK |
| 24001 | Academy_AttendSchedule | `AcademyAttendScheduleResponse` | 24 | 3 | high | OK |
| 25003 | Event_RewardIncrease | `EventRewardIncreaseResponse` | 25 | 1 | high | OK |
| 26000 | ContentSave_Get | `ContentSaveGetResponse` | 26 | 3 | high | OK |
| 26001 | ContentSave_Discard | `ContentSaveDiscardResponse` | 26 | 1 | high | OK |
| 27001 | ContentSweep_MultiSweep | `ContentSweepMultiSweepResponse` | 27 | 5 | high | OK |
| 27002 | ContentSweep_MultiSweepPresetList | `ContentSweepMultiSweepPresetListResponse` | 27 | 1 | high | OK |
| 27003 | ContentSweep_SetMultiSweepPreset | `ContentSweepSetMultiSweepPresetResponse` | 27 | 1 | high | OK |
| 27004 | ContentSweep_SetMultiSweepPresetName | `ContentSweepSetMultiSweepPresetNameResponse` | 27 | 1 | high | OK |
| 28000 | Clan_Lobby | `ClanLobbyResponse` | 28 | 5 | high | OK |
| 28001 | Clan_Login | `ClanLoginResponse` | 28 | 3 | high | OK |
| 28002 | Clan_Search | `ClanSearchResponse` | 28 | 1 | high | OK |
| 28003 | Clan_Create | `ClanCreateResponse` | 28 | 3 | high | OK |
| 28004 | Clan_Member | `ClanMemberResponse` | 28 | 3 | high | OK |
| 28005 | Clan_Applicant | `ClanApplicantResponse` | 28 | 1 | high | OK |
| 28006 | Clan_Join | `ClanJoinResponse` | 28 | 3 | high | OK |
| 28007 | Clan_Quit | `ClanQuitResponse` | 28 | 0 | - | empty(已验) |
| 28008 | Clan_Permit | `ClanPermitResponse` | 28 | 2 | high | OK |
| 28009 | Clan_Kick | `ClanKickResponse` | 28 | 0 | - | empty(已验) |
| 28010 | Clan_Setting | `ClanSettingResponse` | 28 | 1 | high | OK |
| 28011 | Clan_Confer | `ClanConferResponse` | 28 | 4 | high | OK |
| 28012 | Clan_Dismiss | `ClanDismissResponse` | 28 | 0 | - | empty(已验) |
| 28013 | Clan_AutoJoin | `ClanAutoJoinResponse` | 28 | 3 | high | OK |
| 28014 | Clan_MemberList | `ClanMemberListResponse` | 28 | 2 | high | OK |
| 28015 | Clan_CancelApply | `ClanCancelApplyResponse` | 28 | 0 | - | empty(已验) |
| 28016 | Clan_MyAssistList | `ClanMyAssistListResponse` | 28 | 1 | high | OK |
| 28017 | Clan_SetAssist | `ClanSetAssistResponse` | 28 | 3 | high | OK |
| 28018 | Clan_ChatLog | `ClanChatLogResponse` | 28 | 1 | high | OK |
| 28019 | Clan_Check | `ClanCheckResponse` | 28 | 0 | - | empty(已验) |
| 28020 | Clan_AllAssistList | `ClanAllAssistListResponse` | 28 | 3 | mid | OK |
| 29000 | Billing_TransactionStartByYostar | `BillingTransactionStartByYostarResponse` | 29 | 6 | high | OK |
| 29001 | Billing_TransactionEndByYostar | `BillingTransactionEndByYostarResponse` | 29 | 7 | high | OK |
| 29002 | Billing_PurchaseListByYostar | `BillingPurchaseListByYostarResponse` | 29 | 6 | high | OK |
| 29003 | Billing_PurchaseFreeProduct | `BillingPurchaseFreeProductResponse` | 29 | 3 | high | OK |
| 30000 | EventContent_AdventureList | `EventContentAdventureListResponse` | 30 | 5 | mid | OK |
| 30001 | EventContent_EnterMainStage | `EventContentEnterMainStageResponse` | 30 | 2 | high | OK |
| 30002 | EventContent_ConfirmMainStage | `EventContentConfirmMainStageResponse` | 30 | 2 | high | OK |
| 30003 | EventContent_EnterTactic | `EventContentEnterTacticResponse` | 30 | 1 | high | OK |
| 30004 | EventContent_TacticResult | `EventContentTacticResultResponse` | 30 | 10 | high | OK |
| 30005 | EventContent_EnterSubStage | `EventContentEnterSubStageResponse` | 30 | 4 | high | OK |
| 30006 | EventContent_SubStageResult | `EventContentSubStageResultResponse` | 30 | 7 | high | OK |
| 30007 | EventContent_DeployEchelon | `EventContentDeployEchelonResponse` | 30 | 1 | high | OK |
| 30008 | EventContent_WithdrawEchelon | `EventContentWithdrawEchelonResponse` | 30 | 2 | high | OK |
| 30009 | EventContent_MapMove | `EventContentMapMoveResponse` | 30 | 4 | high | OK |
| 30010 | EventContent_EndTurn | `EventContentEndTurnResponse` | 30 | 2 | high | OK |
| 30011 | EventContent_Retreat | `EventContentRetreatResponse` | 30 | 2 | high | OK |
| 30012 | EventContent_Portal | `EventContentPortalResponse` | 30 | 1 | high | OK |
| 30013 | EventContent_PurchasePlayCountHardStage | `EventContentPurchasePlayCountHardStageResponse` | 30 | 2 | high | OK |
| 30014 | EventContent_ShopList | `EventContentShopListResponse` | 30 | 2 | high | OK |
| 30015 | EventContent_ShopRefresh | `EventContentShopRefreshResponse` | 30 | 2 | high | OK |
| 30016 | EventContent_ReceiveStageTotalReward | `EventContentReceiveStageTotalRewardResponse` | 30 | 3 | high | OK |
| 30017 | EventContent_EnterMainGroundStage | `EventContentEnterMainGroundStageResponse` | 30 | 4 | high | OK |
| 30018 | EventContent_MainGroundStageResult | `EventContentMainGroundStageResultResponse` | 30 | 8 | high | OK |
| 30019 | EventContent_ShopBuyMerchandise | `EventContentShopBuyMerchandiseResponse` | 30 | 6 | high | OK |
| 30020 | EventContent_ShopBuyRefreshMerchandise | `EventContentShopBuyRefreshMerchandiseResponse` | 30 | 6 | high | OK |
| 30021 | EventContent_SelectBuff | `EventContentSelectBuffResponse` | 30 | 1 | high | OK |
| 30022 | EventContent_BoxGachaShopList | `EventContentBoxGachaShopListResponse` | 30 | 2 | high | OK |
| 30023 | EventContent_BoxGachaShopPurchase | `EventContentBoxGachaShopPurchaseResponse` | 30 | 4 | mid | OK |
| 30024 | EventContent_BoxGachaShopRefresh | `EventContentBoxGachaShopRefreshResponse` | 30 | 2 | high | OK |
| 30025 | EventContent_CollectionList | `EventContentCollectionListResponse` | 30 | 1 | high | OK |
| 30026 | EventContent_CollectionForMission | `EventContentCollectionForMissionResponse` | 30 | 1 | high | OK |
| 30027 | EventContent_ScenarioGroupHistoryUpdate | `EventContentScenarioGroupHistoryUpdateResponse` | 30 | 3 | high | OK |
| 30028 | EventContent_CardShopList | `EventContentCardShopListResponse` | 30 | 2 | high | OK |
| 30029 | EventContent_CardShopShuffle | `EventContentCardShopShuffleResponse` | 30 | 1 | high | OK |
| 30030 | EventContent_CardShopPurchase | `EventContentCardShopPurchaseResponse` | 30 | 3 | high | OK |
| 30031 | EventContent_RestartMainStage | `EventContentRestartMainStageResponse` | 30 | 2 | high | OK |
| 30032 | EventContent_LocationGetInfo | `EventContentLocationGetInfoResponse` | 30 | 1 | high | OK |
| 30033 | EventContent_LocationAttendSchedule | `EventContentLocationAttendScheduleResponse` | 30 | 4 | mid | OK |
| 30034 | EventContent_FortuneGachaPurchase | `EventContentFortuneGachaPurchaseResponse` | 30 | 2 | high | OK |
| 30035 | EventContent_SubEventLobby | `EventContentSubEventLobbyResponse` | 30 | 2 | high | OK |
| 30036 | EventContent_EnterStoryStage | `EventContentEnterStoryStageResponse` | 30 | 2 | high | OK |
| 30037 | EventContent_StoryStageResult | `EventContentStoryStageResultResponse` | 30 | 4 | high | OK |
| 30038 | EventContent_DiceRaceLobby | `EventContentDiceRaceLobbyResponse` | 30 | 1 | high | OK |
| 30039 | EventContent_DiceRaceRoll | `EventContentDiceRaceRollResponse` | 30 | 4 | high | OK |
| 30040 | EventContent_DiceRaceLapReward | `EventContentDiceRaceLapRewardResponse` | 30 | 2 | high | OK |
| 30041 | EventContent_PermanentList | `EventContentPermanentListResponse` | 30 | 1 | high | OK |
| 30042 | EventContent_DiceRaceUseItem | `EventContentDiceRaceUseItemResponse` | 30 | 4 | high | OK |
| 30043 | EventContent_CardShopPurchaseAll | `EventContentCardShopPurchaseAllResponse` | 30 | 4 | high | OK |
| 30044 | EventContent_TreasureLobby | `EventContentTreasureLobbyResponse` | 30 | 3 | high | OK |
| 30045 | EventContent_TreasureFlip | `EventContentTreasureFlipResponse` | 30 | 2 | high | OK |
| 30046 | EventContent_TreasureNextRound | `EventContentTreasureNextRoundResponse` | 30 | 2 | high | OK |
| 30047 | EventContent_ConcentrationGetInfo | `EventContentConcentrationGetInfoResponse` | 30 | 1 | high | OK |
| 30048 | EventContent_ConcentrationFlipCard | `EventContentConcentrationFlipCardResponse` | 30 | 4 | high | OK |
| 30049 | EventContent_ConcentrationRoundComplete | `EventContentConcentrationRoundCompleteResponse` | 30 | 3 | high | OK |
| 30050 | EventContent_ConcentrationRoundSkip | `EventContentConcentrationRoundSkipResponse` | 30 | 3 | high | OK |
| 30051 | EventContent_ClueSearchGetInfo | `EventContentClueSearchGetInfoResponse` | 30 | 1 | high | OK |
| 30052 | EventContent_ClueSearchSubmit | `EventContentClueSearchSubmitResponse` | 30 | 2 | high | OK |
| 30053 | EventContent_ClueSearchRoundComplete | `EventContentClueSearchRoundCompleteResponse` | 30 | 2 | high | OK |
| 31000 | TTS_GetFile | `TTSGetFileResponse` | 31 | 2 | high | OK |
| 33000 | MomoTalk_OutLine | `MomoTalkOutLineResponse` | 33 | 2 | high | OK |
| 33001 | MomoTalk_MessageList | `MomoTalkMessageListResponse` | 33 | 2 | high | OK |
| 33002 | MomoTalk_Read | `MomoTalkReadResponse` | 33 | 2 | high | OK |
| 33004 | MomoTalk_FavorSchedule | `MomoTalkFavorScheduleResponse` | 33 | 2 | high | OK |
| 34000 | ClearDeck_List | `ClearDeckListResponse` | 34 | 1 | mid | OK |
| 34001 | ClearDeck_GroupedList | `ClearDeckGroupedListResponse` | 34 | 1 | mid | OK |
| 35000 | MiniGame_StageList | `MiniGameStageListResponse` | 35 | 1 | mid | OK |
| 35001 | MiniGame_EnterStage | `MiniGameEnterStageResponse` | 35 | 0 | - | empty(已验) |
| 35002 | MiniGame_Result | `MiniGameResultResponse` | 35 | 0 | - | empty(已验) |
| 35003 | MiniGame_MissionList | `MiniGameMissionListResponse` | 35 | 3 | high | OK |
| 35004 | MiniGame_MissionReward | `MiniGameMissionRewardResponse` | 35 | 2 | high | OK |
| 35005 | MiniGame_MissionMultipleReward | `MiniGameMissionMultipleRewardResponse` | 35 | 2 | high | OK |
| 35006 | MiniGame_ShootingLobby | `MiniGameShootingLobbyResponse` | 35 | 1 | mid | OK |
| 35007 | MiniGame_ShootingBattleEnter | `MiniGameShootingBattleEnterResponse` | 35 | 0 | - | empty(已验) |
| 35008 | MiniGame_ShootingBattleResult | `MiniGameShootingBattleResultResponse` | 35 | 1 | high | OK |
| 35009 | MiniGame_ShootingSweep | `MiniGameShootingSweepResponse` | 35 | 2 | high | OK |
| 35010 | MiniGame_TableBoardSync | `MiniGameTableBoardSyncResponse` | 35 | 1 | high | OK |
| 35011 | MiniGame_TableBoardMove | `MiniGameTableBoardMoveResponse` | 35 | 4 | high | OK |
| 35012 | MiniGame_TableBoardEncounterInput | `MiniGameTableBoardEncounterInputResponse` | 35 | 7 | mid | OK |
| 35015 | MiniGame_TableBoardClearThema | `MiniGameTableBoardClearThemaResponse` | 35 | 2 | high | OK |
| 35016 | MiniGame_TableBoardUseItem | `MiniGameTableBoardUseItemResponse` | 35 | 1 | high | OK |
| 35017 | MiniGame_TableBoardResurrect | `MiniGameTableBoardResurrectResponse` | 35 | 2 | high | OK |
| 35018 | MiniGame_TableBoardSweep | `MiniGameTableBoardSweepResponse` | 35 | 2 | high | OK |
| 35019 | MiniGame_TableBoardMoveThema | `MiniGameTableBoardMoveThemaResponse` | 35 | 1 | high | OK |
| 35020 | MiniGame_DreamMakerGetInfo | `MiniGameDreamMakerGetInfoResponse` | 35 | 6 | mid | OK |
| 35021 | MiniGame_DreamMakerNewGame | `MiniGameDreamMakerNewGameResponse` | 35 | 2 | high | OK |
| 35023 | MiniGame_DreamMakerAttendSchedule | `MiniGameDreamMakerAttendScheduleResponse` | 35 | 5 | high | OK |
| 35024 | MiniGame_DreamMakerDailyClosing | `MiniGameDreamMakerDailyClosingResponse` | 35 | 5 | high | OK |
| 35025 | MiniGame_DreamMakerEnding | `MiniGameDreamMakerEndingResponse` | 35 | 4 | high | OK |
| 35026 | MiniGame_DefenseGetInfo | `MiniGameDefenseGetInfoResponse` | 35 | 2 | mid | OK |
| 35027 | MiniGame_DefenseEnterBattle | `MiniGameDefenseEnterBattleResponse` | 35 | 0 | - | empty(已验) |
| 35028 | MiniGame_DefenseBattleResult | `MiniGameDefenseBattleResultResponse` | 35 | 2 | high | OK |
| 35029 | MiniGame_RoadPuzzleGetInfo | `MiniGameRoadPuzzleGetInfoResponse` | 35 | 1 | high | OK |
| 35030 | MiniGame_RoadPuzzleTilePlace | `MiniGameRoadPuzzleTilePlaceResponse` | 35 | 3 | high | OK |
| 35031 | MiniGame_RoadPuzzleSaveStage | `MiniGameRoadPuzzleSaveStageResponse` | 35 | 1 | high | OK |
| 35032 | MiniGame_RoadPuzzleClearStage | `MiniGameRoadPuzzleClearStageResponse` | 35 | 2 | high | OK |
| 35033 | MiniGame_CCGLobby | `MiniGameCCGLobbyResponse` | 35 | 4 | high | OK |
| 35034 | MiniGame_CCGCreateGame | `MiniGameCCGCreateGameResponse` | 35 | 1 | high | OK |
| 35035 | MiniGame_CCGSweep | `MiniGameCCGSweepResponse` | 35 | 2 | high | OK |
| 35036 | MiniGame_CCGEnterStage | `MiniGameCCGEnterStageResponse` | 35 | 1 | high | OK |
| 35037 | MiniGame_CCGEndStageDual | `MiniGameCCGEndStageDualResponse` | 35 | 2 | high | OK |
| 35038 | MiniGame_CCGEndStageEvent | `MiniGameCCGEndStageEventResponse` | 35 | 2 | high | OK |
| 35039 | MiniGame_CCGSelectRewardCard | `MiniGameCCGSelectRewardCardResponse` | 35 | 3 | high | OK |
| 35041 | MiniGame_CCGSelectCampAction | `MiniGameCCGSelectCampActionResponse` | 35 | 2 | high | OK |
| 35042 | MiniGame_CCGCompleteGame | `MiniGameCCGCompleteGameResponse` | 35 | 3 | high | OK |
| 35043 | MiniGame_CCGGiveupGame | `MiniGameCCGGiveupGameResponse` | 35 | 1 | high | OK |
| 35044 | MiniGame_CCGRerollReward | `MiniGameCCGRerollRewardResponse` | 35 | 1 | high | OK |
| 35045 | MiniGame_CCGBuyPerk | `MiniGameCCGBuyPerkResponse` | 35 | 3 | high | OK |
| 36000 | Notification_LobbyCheck | `NotificationLobbyCheckResponse` | 36 | 2 | high | OK |
| 37000 | ProofToken_RequestQuestion | `ProofTokenRequestQuestionResponse` | 37 | 2 | high | OK |
| 37001 | ProofToken_Submit | `ProofTokenSubmitResponse` | 37 | 0 | - | empty(已验) |
| 38000 | SchoolDungeon_List | `SchoolDungeonListResponse` | 38 | 1 | mid | OK |
| 38001 | SchoolDungeon_EnterBattle | `SchoolDungeonEnterBattleResponse` | 38 | 2 | high | OK |
| 38002 | SchoolDungeon_BattleResult | `SchoolDungeonBattleResultResponse` | 38 | 5 | high | OK |
| 38003 | SchoolDungeon_Retreat | `SchoolDungeonRetreatResponse` | 38 | 1 | high | OK |
| 39000 | TimeAttackDungeon_Lobby | `TimeAttackDungeonLobbyResponse` | 39 | 5 | mid | OK |
| 39001 | TimeAttackDungeon_CreateBattle | `TimeAttackDungeonCreateBattleResponse` | 39 | 2 | high | OK |
| 39002 | TimeAttackDungeon_EnterBattle | `TimeAttackDungeonEnterBattleResponse` | 39 | 2 | high | OK |
| 39003 | TimeAttackDungeon_EndBattle | `TimeAttackDungeonEndBattleResponse` | 39 | 5 | high | OK |
| 39004 | TimeAttackDungeon_Sweep | `TimeAttackDungeonSweepResponse` | 39 | 3 | high | OK |
| 39005 | TimeAttackDungeon_GiveUp | `TimeAttackDungeonGiveUpResponse` | 39 | 4 | high | OK |
| 39006 | TimeAttackDungeon_Login | `TimeAttackDungeonLoginResponse` | 39 | 1 | high | OK |
| 40000 | WorldRaid_Lobby | `WorldRaidLobbyResponse` | 40 | 4 | mid | OK |
| 40001 | WorldRaid_BossList | `WorldRaidBossListResponse` | 40 | 1 | mid | OK |
| 40002 | WorldRaid_EnterBattle | `WorldRaidEnterBattleResponse` | 40 | 3 | high | OK |
| 40003 | WorldRaid_BattleResult | `WorldRaidBattleResultResponse` | 40 | 1 | high | OK |
| 40004 | WorldRaid_ReceiveReward | `WorldRaidReceiveRewardResponse` | 40 | 1 | high | OK |
| 40005 | WorldRaid_UpdateCarrierSkill | `WorldRaidUpdateCarrierSkillResponse` | 40 | 2 | high | OK |
| 41000 | ResetableContent_Get | `ResetableContentGetResponse` | 41 | 1 | mid | OK |
| 42000 | Conquest_GetInfo | `ConquestGetInfoResponse` | 42 | 7 | mid | OK |
| 42001 | Conquest_Conquer | `ConquestConquerResponse` | 42 | 5 | high | OK |
| 42002 | Conquest_ConquerWithBattleStart | `ConquestConquerWithBattleStartResponse` | 42 | 2 | high | OK |
| 42003 | Conquest_ConquerWithBattleResult | `ConquestConquerWithBattleResultResponse` | 42 | 7 | high | OK |
| 42005 | Conquest_ManageBase | `ConquestManageBaseResponse` | 42 | 7 | high | OK |
| 42006 | Conquest_UpgradeBase | `ConquestUpgradeBaseResponse` | 42 | 6 | high | OK |
| 42007 | Conquest_TakeEventObject | `ConquestTakeEventObjectResponse` | 42 | 2 | mid | OK |
| 42008 | Conquest_EventObjectBattleStart | `ConquestEventObjectBattleStartResponse` | 42 | 2 | high | OK |
| 42009 | Conquest_EventObjectBattleResult | `ConquestEventObjectBattleResultResponse` | 42 | 5 | high | OK |
| 42011 | Conquest_NormalizeEchelon | `ConquestNormalizeEchelonResponse` | 42 | 1 | high | OK |
| 42012 | Conquest_Check | `ConquestCheckResponse` | 42 | 4 | high | OK |
| 42013 | Conquest_ErosionBattleStart | `ConquestErosionBattleStartResponse` | 42 | 2 | high | OK |
| 42014 | Conquest_ErosionBattleResult | `ConquestErosionBattleResultResponse` | 42 | 4 | high | OK |
| 42015 | Conquest_MainStoryGetInfo | `ConquestMainStoryGetInfoResponse` | 42 | 4 | high | OK |
| 42016 | Conquest_MainStoryConquer | `ConquestMainStoryConquerResponse` | 42 | 4 | high | OK |
| 42017 | Conquest_MainStoryConquerWithBattleStart | `ConquestMainStoryConquerWithBattleStartResponse` | 42 | 2 | high | OK |
| 42018 | Conquest_MainStoryConquerWithBattleResult | `ConquestMainStoryConquerWithBattleResultResponse` | 42 | 6 | high | OK |
| 42019 | Conquest_MainStoryCheck | `ConquestMainStoryCheckResponse` | 42 | 1 | high | OK |
| 43000 | Friend_List | `FriendListResponse` | 43 | 6 | mid | OK |
| 43001 | Friend_Remove | `FriendRemoveResponse` | 43 | 4 | high | OK |
| 43002 | Friend_GetFriendDetailedInfo | `FriendGetFriendDetailedInfoResponse` | 43 | 17 | mid | OK |
| 43003 | Friend_GetIdCard | `FriendGetIdCardResponse` | 43 | 1 | high | OK |
| 43004 | Friend_SetIdCard | `FriendSetIdCardResponse` | 43 | 0 | - | empty(已验) |
| 43006 | Friend_SendFriendRequest | `FriendSendFriendRequestResponse` | 43 | 4 | high | OK |
| 43007 | Friend_AcceptFriendRequest | `FriendAcceptFriendRequestResponse` | 43 | 4 | high | OK |
| 43008 | Friend_DeclineFriendRequest | `FriendDeclineFriendRequestResponse` | 43 | 4 | high | OK |
| 43009 | Friend_CancelFriendRequest | `FriendCancelFriendRequestResponse` | 43 | 4 | high | OK |
| 43010 | Friend_Check | `FriendCheckResponse` | 43 | 0 | - | empty(已验) |
| 43011 | Friend_ListByIds | `FriendListByIdsResponse` | 43 | 1 | high | OK |
| 43012 | Friend_Block | `FriendBlockResponse` | 43 | 4 | high | OK |
| 43013 | Friend_Unblock | `FriendUnblockResponse` | 43 | 4 | high | OK |
| 44000 | CharacterGear_List | `CharacterGearListResponse` | 44 | 1 | high | OK |
| 44001 | CharacterGear_Unlock | `CharacterGearUnlockResponse` | 44 | 2 | high | OK |
| 44002 | CharacterGear_TierUp | `CharacterGearTierUpResponse` | 44 | 3 | high | OK |
| 45000 | EliminateRaid_Login | `EliminateRaidLoginResponse` | 45 | 6 | high | OK |
| 45001 | EliminateRaid_Lobby | `EliminateRaidLobbyResponse` | 45 | 5 | high | OK |
| 45002 | EliminateRaid_OpponentList | `EliminateRaidOpponentListResponse` | 45 | 1 | mid | OK |
| 45003 | EliminateRaid_GetBestTeam | `EliminateRaidGetBestTeamResponse` | 45 | 1 | mid | OK |
| 45004 | EliminateRaid_CreateBattle | `EliminateRaidCreateBattleResponse` | 45 | 5 | high | OK |
| 45005 | EliminateRaid_EnterBattle | `EliminateRaidEnterBattleResponse` | 45 | 5 | high | OK |
| 45006 | EliminateRaid_EndBattle | `EliminateRaidEndBattleResponse` | 45 | 6 | high | OK |
| 45007 | EliminateRaid_GiveUp | `EliminateRaidGiveUpResponse` | 45 | 3 | high | OK |
| 45011 | EliminateRaid_LimitedReward | `EliminateRaidLimitedRewardResponse` | 45 | 2 | high | OK |
| 45012 | EliminateRaid_RankingIndex | `EliminateRaidRankingIndexResponse` | 45 | 1 | high | OK |
| 46000 | Attachment_Get | `AttachmentGetResponse` | 46 | 1 | high | OK |
| 46001 | Attachment_EmblemList | `AttachmentEmblemListResponse` | 46 | 1 | high | OK |
| 46002 | Attachment_EmblemAcquire | `AttachmentEmblemAcquireResponse` | 46 | 1 | high | OK |
| 46003 | Attachment_EmblemAttach | `AttachmentEmblemAttachResponse` | 46 | 1 | high | OK |
| 47000 | Sticker_Login | `StickerLoginResponse` | 47 | 1 | high | OK |
| 47001 | Sticker_Lobby | `StickerLobbyResponse` | 47 | 2 | high | OK |
| 47002 | Sticker_UseSticker | `StickerUseStickerResponse` | 47 | 2 | high | OK |
| 48000 | Field_Sync | `FieldSyncResponse` | 48 | 3 | high | OK |
| 48001 | Field_Interaction | `FieldInteractionResponse` | 48 | 4 | high | OK |
| 48002 | Field_QuestClear | `FieldQuestClearResponse` | 48 | 2 | high | OK |
| 48003 | Field_SceneChanged | `FieldSceneChangedResponse` | 48 | 1 | high | OK |
| 48004 | Field_EndDate | `FieldEndDateResponse` | 48 | 1 | high | OK |
| 48005 | Field_EnterStage | `FieldEnterStageResponse` | 48 | 2 | high | OK |
| 48006 | Field_StageResult | `FieldStageResultResponse` | 48 | 5 | high | OK |
| 49000 | MultiFloorRaid_Sync | `MultiFloorRaidSyncResponse` | 49 | 1 | high | OK |
| 49001 | MultiFloorRaid_EnterBattle | `MultiFloorRaidEnterBattleResponse` | 49 | 2 | high | OK |
| 49002 | MultiFloorRaid_EndBattle | `MultiFloorRaidEndBattleResponse` | 49 | 2 | high | OK |
| 49003 | MultiFloorRaid_ReceiveReward | `MultiFloorRaidReceiveRewardResponse` | 49 | 2 | high | OK |
| 49004 | MultiFloorRaid_Login | `MultiFloorRaidLoginResponse` | 49 | 1 | high | OK |
| 50000 | Queuing_GetTicket | `QueuingGetTicketResponse` | 50 | 7 | high | OK |
| 50001 | Queuing_GetCryptoKeys | `QueuingGetCryptoKeysResponse` | 50 | 6 | high | OK |
| 51000 | BattlePass_GetInfo | `BattlePassGetInfoResponse` | 51 | 1 | high | OK |
| 51001 | BattlePass_BuyLevel | `BattlePassBuyLevelResponse` | 51 | 2 | high | OK |
| 51002 | BattlePass_ReceiveReward | `BattlePassReceiveRewardResponse` | 51 | 2 | high | OK |
| 51003 | BattlePass_MissionList | `BattlePassMissionListResponse` | 51 | 2 | high | OK |
| 51004 | BattlePass_MissionSingleReward | `BattlePassMissionSingleRewardResponse` | 51 | 3 | high | OK |
| 51005 | BattlePass_MissionMultipleReward | `BattlePassMissionMultipleRewardResponse` | 51 | 3 | high | OK |
| 51006 | BattlePass_Check | `BattlePassCheckResponse` | 51 | 2 | high | OK |
| 52000 | DailyRecord_Reward | `DailyRecordRewardResponse` | 52 | 2 | high | OK |
| 53000 | Option_Save | `OptionSaveResponse` | 53 | 0 | - | empty(已验) |
| 54000 | PermanentRaid_Lobby | `PermanentRaidLobbyResponse` | 54 | 3 | mid | OK |
| 54001 | PermanentRaid_EnterBattle | `PermanentRaidEnterBattleResponse` | 54 | 1 | high | OK |
| 54002 | PermanentRaid_EndBattle | `PermanentRaidEndBattleResponse` | 54 | 1 | high | OK |
| 54003 | PermanentRaid_GiveUp | `PermanentRaidGiveUpResponse` | 54 | 0 | - | empty(已验) |
| 90004 | Management_Data | `ManagementDataResponse` | 90 | 1 | high | OK |
| 90009 | Clan_Chat_Records | `ClanChatRecordsResponse` | 90 | 1 | high | OK |
| 90010 | Clan_Send_Chat | `ClanSendChatResponse` | 90 | 0 | - | empty(已验) |
| 90011 | Shop_ListTutorialGacha | `ShopListTutorialGachaResponse` | 90 | 6 | high | OK |
| 90012 | Shop_BuyTutorialGacha | `ShopBuyTutorialGachaResponse` | 90 | 3 | high | OK |
| 90013 | Shop_SaveTutorialGacha | `ShopSaveTutorialGachaResponse` | 90 | 2 | high | OK |
| 90014 | Shop_ConfirmTutorialGacha | `ShopConfirmTutorialGachaResponse` | 90 | 3 | high | OK |
| - | Audit_GachaStatistics | `AuditGachaStatisticsResponse` | nosid | 1 | high | OK |
| - | System_Version | `SystemVersionResponse` | nosid | 3 | high | OK |

---

附：本报告的数据文件
- `work/ba/proto/dto_schema_full.json`：707 个类型（444 响应 + 13 额外映射 + 250 support，support 含 ResponsePacket/RequestPacket 两个基类）；444 响应的自有字段 1088 个、含继承的有效字段 1131 个
- `work/ba/proto/gen_full.py`：统一响应生成器
- `work/ba/proto/_full/`：worklist / 引擎 / 分段产物 / 合并脚本 / 校验脚本 / 统计 JSON
- `report_stats.json`、`report_facts.json`：§1/§2/§3 的数字来源
