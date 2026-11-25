# 协议字段 ↔ ExcelDB 表 映射

> 项目：BA 国服私服 ｜ 生成时间 2026-11-16 ｜ 机器可读版：`excel_field_map.json`
> 数据源：`work/ba/data/ExcelDB.db`（**只读**，398 张 `XxxDBSchema`，707,896 行，153 MB）
> 官方样本：`report/_tmp/official_decoded_201/*.response.json`（109 份响应 / 38 个协议）
> 附录（同目录）：`_sub_mission.md`（8000/8002/8006 专项）、`_sub_1017.md`（1017 其余 22 个子回包专项）

## 0. 一句话结论

- **能查到表的字段只有一小半**：1340 条映射里 `static`（真·查表）142 条，其中 `verified` 32 条、`ambiguous` 99 条、`weak` 12 条；`player`（玩家进度）369 条；`enum/echo` 20 条；`not_found`（库里确实没有）21 条；其余 787 条是「值太小/太常见，纯值匹配无法判定」。
- 私服真正需要「查表」的地方集中在：**角色/道具/装备/家具/关卡/剧情/招募池/学院地点/货币** 这几类，它们全部有 verified 证据（见 §3）。
- **编队(5000) 0 条查表**；咖啡厅(20001) 只有 4 条（CafeId / 家具 UniqueId / CafeRank 上限 / 产出道具 id）；竞技场、任务进度、邮件几乎全是玩家数据 —— 私服只需要自己存状态。
- **招募活动的开放/结束时间不在 ExcelDB 里**（398 表 × 29 种日期编码 0 命中），必须私服自己配。

## 1. 方法（不是按表名猜的）

ExcelDB 每张表 = 若干 SQL 索引列 + 一列 `Bytes`（FlatBuffers，**没有 .fbs**）。所以做了一张**全库倒排索引**：把所有表的整数（SQL 索引列 + FlatBuffers 标量槽位）映射到 `(表, 槽位)`，再用官方响应里的**真实值**反查。表名只用来事后命名，不参与判定。

判定口径：

| 结论 | 条件 |
|---|---|
| `verified` | 官方该字段的全部不同值都在这个槽位里命中，每个值只对应 1 行，且不是「稠密 id 段」巧合（density≤0.5），且满命中槽位数 ≤8 |
| `ambiguous` | 值全覆盖但有多个候选（低基数/FK 并列），需要行内一致性或结构证据才能裁定 |
| `weak` | 官方值太少（<5）或全是「到处都有」的小整数，值匹配证明不了任何事 |
| `player` | 全库 0 命中，且量级像账号内自增 id / 时间戳 / 计数 |
| `enum` | 客户端枚举常量（ParcelType、EchelonType…），ExcelDB 里没有对应表 |
| `not_found` | 全库确实没有这些值（如招募开放时间） |

**槽位表示法**：`f<N>` = FlatBuffers 第 N 个槽位（无 .fbs 只能给序号）；`sql:<列名>` = SQL 索引列（多数表就是主键 `Id`）。

复现命令（全部只读）：

```bash
python work/ba/proto/xls_lib.py build                 # 建倒排索引（5 秒，产出 _xls_index.pkl）
python work/ba/proto/xls_lib.py find 150041           # 某个值出现在哪些表/槽位
python work/ba/proto/xls_match.py 4000                # 整个协议逐字段反查
python work/ba/proto/xls_match.py explain 6000 "StageHistoryDBs[].StageUniqueId"   # 单字段全部候选
python work/ba/proto/xls_join.py 6000 "StageHistoryDBs[]" CampaignStageDBSchema f0 StageUniqueId
python work/ba/data/dump_table.py --table ShopRecruitDBSchema --where "Id in (1,2,3)"
python work/ba/proto/probe_claims.py                  # 本文件里每条「结论级」判断的复核脚本
python work/ba/proto/probe_1017_ids.py / probe_shop.py / scan_dates.py
```

## 2. 398 张表清单（按命名分类 + 行数）

分类只按表名词根做，纯粹为了导航；**映射结论一律来自值匹配**。

| 分类 | 中文 | 表数 | 行数 |
|---|---|---|---|
| `character` | 角色 | 38 | 87645 |
| `tutorial` | 教程 | 3 | 762 |
| `item` | 道具 | 2 | 1821 |
| `equipment` | 装备 | 3 | 452 |
| `shop` | 商店/商品 | 19 | 21929 |
| `mission` | 任务 | 8 | 4780 |
| `scenario` | 剧情/文本 | 16 | 371089 |
| `cafe` | 咖啡厅/家具 | 8 | 2763 |
| `academy` | 学院 | 9 | 16883 |
| `echelon` | 编队/助战 | 6 | 351 |
| `stage` | 关卡/战役 | 66 | 17500 |
| `enemy` | 敌人/战斗几何 | 9 | 15718 |
| `gacha` | 抽卡 | 11 | 20535 |
| `event` | 活动/小游戏 | 87 | 39041 |
| `arena` | 竞技场 | 6 | 242 |
| `raid` | 总力战/Raid | 30 | 11555 |
| `clan` | 社团/好友/邮件 | 2 | 177 |
| `combat` | 技能/战斗逻辑 | 19 | 21166 |
| `craft` | 制造 | 5 | 16469 |
| `currency` | 货币/账号 | 3 | 125 |
| `battlepass` | 通行证 | 5 | 411 |
| `localize` | 本地化文本 | 7 | 39922 |
| `audio` | 音频 | 8 | 14768 |
| `ui` | UI/弹窗 | 17 | 1608 |
| `misc` | 杂项 | 10 | 175 |
| `other` | 未归类 | 1 | 9 |

### 2.1 分类明细（表名(行数)）

**`character` 角色**（38 张）：

CharacterAIDBSchema(70), CharacterAcademyTagsDBSchema(253), CharacterCalculationLimitDBSchema(22), CharacterCombatSkinDBSchema(1), CharacterDBSchema(7223), CharacterDialogBattlePassDBSchema(54), CharacterDialogDBSchema(11784), CharacterDialogEmojiDBSchema(414), CharacterDialogEventDBSchema(7629), CharacterDialogSubtitleDBSchema(5501), CharacterGearDBSchema(104), CharacterGearLevelDBSchema(1), CharacterIllustCoordinateDBSchema(254), CharacterLevelDBSchema(90), CharacterLevelStatFactorDBSchema(200), CharacterPotentialDBSchema(762), CharacterPotentialRewardDBSchema(254), CharacterPotentialStatDBSchema(1638), CharacterSkillListDBSchema(6708), CharacterStatDBSchema(7242), CharacterStatLimitDBSchema(224), CharacterStatsDetailDBSchema(10), CharacterStatsTransDBSchema(16), CharacterTranscendenceDBSchema(789), CharacterVictoryInteractionDBSchema(16), CharacterVoiceDBSchema(9493), CharacterVoiceSubtitleDBSchema(6529), CharacterWeaponDBSchema(254), CharacterWeaponExpBonusDBSchema(11), CharacterWeaponLevelDBSchema(70), CostumeDBSchema(5913), EmblemDBSchema(1065), FavorLevelDBSchema(100), FavorLevelRewardDBSchema(12650), IdCardBackgroundDBSchema(17), MemoryLobbyDBSchema(258), StickerGroupDBSchema(3), StickerPageContentDBSchema(23)

**`tutorial` 教程**（3 张）：

TutorialCharacterDialogDBSchema(303), TutorialDBSchema(33), TutorialFailureImageDBSchema(426)

**`item` 道具**（2 张）：

ItemDBSchema(1803), ParcelAutoSynthDBSchema(18)

**`equipment` 装备**（3 张）：

EquipmentDBSchema(191), EquipmentLevelDBSchema(70), EquipmentStatDBSchema(191)

**`shop` 商店/商品**（19 张）：

GoodsDBSchema(9422), ProductBattlePassDBSchema(12), ProductDBSchema(605), ProductDailyRecordDBSchema(4), ProductDailyRecordInfoDBSchema(1), ProductDailyRecordRewardDBSchema(14), ProductMonthlyDBSchema(36), ProductSelectDBSchema(0), ProductSelectionGroupDBSchema(249), ShopCashDBSchema(656), ShopCashScenarioResourceInfoDBSchema(504), ShopDBSchema(7908), ShopFilterClassifiedDBSchema(1453), ShopFreeRecruitDBSchema(8), ShopFreeRecruitPeriodDBSchema(67), ShopInfoDBSchema(18), ShopRecruitDBSchema(532), ShopRefreshDBSchema(430), ShopTabGroupDBSchema(10)

**`mission` 任务**（8 张）：

AttendanceDBSchema(31), AttendanceRewardDBSchema(334), BattlePassMissionDBSchema(19), GuideMissionDBSchema(923), GuideMissionOpenStageConditionDBSchema(9), GuideMissionSeasonDBSchema(20), MissionDBSchema(3444), MissionEmergencyCompleteDBSchema(0)

**`scenario` 剧情/文本**（16 张）：

BGMDBSchema(378), BGMRaidDBSchema(828), BGMUIDBSchema(202), ScenarioBGEffectDBSchema(86), ScenarioBGNameDBSchema(3663), ScenarioCharacterEmotionDBSchema(63), ScenarioCharacterNameDBSchema(2403), ScenarioCharacterSituationSetDBSchema(2), ScenarioContentCollectionDBSchema(10), ScenarioEffectDBSchema(6), ScenarioModeDBSchema(581), ScenarioModeRewardDBSchema(630), ScenarioModeSpoilerPopupDBSchema(1), ScenarioResourceInfoDBSchema(9), ScenarioScriptDBSchema(362158), ScenarioTransitionDBSchema(69)

**`cafe` 咖啡厅/家具**（8 张）：

CafeInfoDBSchema(2), CafeInteractionDBSchema(253), CafeProductionDBSchema(30), CafeRankDBSchema(20), FurnitureDBSchema(876), FurnitureGroupDBSchema(23), FurnitureTemplateDBSchema(21), FurnitureTemplateElementDBSchema(1538)

**`academy` 学院**（9 张）：

AcademyFavorScheduleDBSchema(1053), AcademyLocationDBSchema(11), AcademyLocationRankDBSchema(12), AcademyMessangerDBSchema(15050), AcademyRewardDBSchema(564), AcademyTicketDBSchema(5), AcademyZoneDBSchema(95), SchoolDungeonRewardDBSchema(81), SchoolDungeonStageDBSchema(12)

**`echelon` 编队/助战**（6 张）：

AssistEchelonTypeConvertDBSchema(6), AssistRewardDBSchema(7), AssistSlotDBSchema(12), EchelonConstraintDBSchema(4), FixedEchelonSettingDBSchema(266), FormationLocationDBSchema(56)

**`stage` 关卡/战役**（66 张）：

CampaignChapterDBSchema(29), CampaignChapterRewardDBSchema(60), CampaignStageDBSchema(407), CampaignStageRewardDBSchema(3004), CampaignStrategyObjectDBSchema(133), CampaignUnitDBSchema(1630), ConquestCalculateDBSchema(3), ConquestCameraSettingDBSchema(14), ConquestErosionDBSchema(7), ConquestErosionUnitDBSchema(29), ConquestEventDBSchema(5), ConquestGroupBonusDBSchema(36), ConquestGroupBuffDBSchema(24), ConquestMapDBSchema(24), ConquestObjectDBSchema(12), ConquestPlayGuideDBSchema(24), ConquestProgressResourceDBSchema(24), ConquestRewardDBSchema(1422), ConquestTileDBSchema(152), ConquestUnexpectedEventDBSchema(2), ConquestUnitDBSchema(218), LevelExpMasterCoinDBSchema(2), MinigameCCGCardDBSchema(66), MinigameCCGCharacterDBSchema(73), MinigameCCGEnemyDBSchema(144), MinigameCCGEnemyGroupDBSchema(41), MinigameCCGInfoDBSchema(2), MinigameCCGLevelDBSchema(42), MinigameCCGLevelNodeDBSchema(570), MinigameCCGLevelStageDBSchema(110), MinigameCCGLogicEffectDBSchema(131), MinigameCCGOpenDialogDBSchema(120), MinigameCCGPerkDBSchema(52), MinigameCCGRewardCardDBSchema(116), MinigameCCGRewardCardRateDBSchema(13), MinigameCCGRewardItemDBSchema(101), MinigameCCGSkillDBSchema(282), MinigameCCGStartDeckCardDBSchema(20), MinigameCCGStartDeckCharacterDBSchema(2), MinigameDreamVoiceDBSchema(32), MinigameRoadPuzzleAdditionalRewardDBSchema(15), MinigameRoadPuzzleMapDBSchema(27), MinigameRoadPuzzleMapTileDBSchema(38), MinigameRoadPuzzleRailTileDBSchema(8), MinigameRoadPuzzleRoadRoundDBSchema(19), MinigameTBGDiceDBSchema(48), MinigameTBGEncounterDBSchema(187), MinigameTBGEncounterOptionDBSchema(362), MinigameTBGEncounterRewardDBSchema(1122), MinigameTBGItemDBSchema(64), MinigameTBGObjectDBSchema(21), MinigameTBGSeasonDBSchema(2), MinigameTBGThemaDBSchema(13), MinigameTBGVoiceDBSchema(56), MultiFloorRaidRewardDBSchema(3478), MultiFloorRaidSeasonManageDBSchema(18), MultiFloorRaidStageDBSchema(744), MultiFloorRaidStatChangeDBSchema(992), TimeAttackDungeonDBSchema(4), TimeAttackDungeonGeasDBSchema(200), TimeAttackDungeonRewardDBSchema(1), TimeAttackDungeonSeasonManageDBSchema(39), WeekDungeonDBSchema(58), WeekDungeonGroupBuffDBSchema(13), WeekDungeonOpenScheduleDBSchema(7), WeekDungeonRewardDBSchema(786)

**`enemy` 敌人/战斗几何**（9 张）：

BossExternalBTDBSchema(10693), BulletArmorDamageFactorDBSchema(56), GroundDBSchema(4399), GroundModuleRewardDBSchema(42), ObstacleFireLineCheckDBSchema(1), ObstacleStatDBSchema(468), TacticEntityEffectFilterDBSchema(16), TacticSkipDBSchema(21), TacticalSupportSystemDBSchema(22)

**`gacha` 抽卡**（11 张）：

GachaCombinedCostDBSchema(24), GachaCraftNodeDBSchema(141), GachaCraftNodeGroupDBSchema(291), GachaCraftOpenTagDBSchema(3), GachaElementDBSchema(14922), GachaElementRecursiveDBSchema(669), GachaGroupDBSchema(1556), GachaSelectPickupGroupDBSchema(98), PickupDuplicateBonusDBSchema(2769), PickupFirstGetBonus2DBSchema(11), PickupFirstGetBonusDBSchema(51)

**`event` 活动/小游戏**（87 张）：

EventContentArchiveBannerOffsetDBSchema(25), EventContentBoxGachaManageDBSchema(204), EventContentBoxGachaShopDBSchema(2478), EventContentBuffDBSchema(160), EventContentBuffGroupDBSchema(141), EventContentCardDBSchema(159), EventContentCardShopDBSchema(835), EventContentCardShopModifyDBSchema(13), EventContentChangeDBSchema(20), EventContentChangeScenarioDBSchema(24), EventContentCharacterBonusDBSchema(2172), EventContentClueDBSchema(0), EventContentClueSearchDBSchema(0), EventContentClueSearchRewardDBSchema(0), EventContentClueSearchRoundDBSchema(0), EventContentCollectionDBSchema(153), EventContentConcentrationCardDBSchema(6), EventContentConcentrationDBSchema(1), EventContentConcentrationRewardDBSchema(14), EventContentConcentrationVoiceDBSchema(10), EventContentCurrencyItemDBSchema(415), EventContentDebuffRewardDBSchema(22), EventContentDiceRaceDBSchema(5), EventContentDiceRaceEffectDBSchema(45), EventContentDiceRaceNodeDBSchema(90), EventContentDiceRaceProbDBSchema(60), EventContentDiceRaceTotalRewardDBSchema(99), EventContentFortuneGachaDBSchema(154), EventContentFortuneGachaModifyDBSchema(9), EventContentFortuneGachaShopDBSchema(188), EventContentLobbyMenuDBSchema(32), EventContentLocationDBSchema(6), EventContentLocationRewardDBSchema(240), EventContentMeetupDBSchema(121), EventContentMeetupInfoDBSchema(4), EventContentMiniEventShortCutDBSchema(2), EventContentMiniEventTokenDBSchema(19), EventContentMissionDBSchema(2384), EventContentNotifyDBSchema(12), EventContentPlayGuideDBSchema(484), EventContentScenarioDBSchema(955), EventContentSeasonDBSchema(412), EventContentShopDBSchema(3874), EventContentShopInfoDBSchema(276), EventContentShopRefreshDBSchema(0), EventContentSpecialOperationsDBSchema(2), EventContentSpineDialogOffsetDBSchema(645), EventContentSpineDisplayPeriodDBSchema(13), EventContentSpoilerPopupDBSchema(15), EventContentStageDBSchema(2353), EventContentStageRewardDBSchema(16642), EventContentStageTotalRewardDBSchema(1525), EventContentTreasureCellRewardDBSchema(9), EventContentTreasureDBSchema(9), EventContentTreasureRewardDBSchema(114), EventContentTreasureRoundDBSchema(61), EventContentZoneDBSchema(48), EventContentZoneVisitRewardDBSchema(0), MiniGameAudioAnimatorDBSchema(11), MiniGameDefenseCharacterBanDBSchema(15), MiniGameDefenseFixedStatDBSchema(8), MiniGameDefenseInfoDBSchema(2), MiniGameDefenseStageDBSchema(22), MiniGameDreamCollectionScenarioDBSchema(48), MiniGameDreamDailyPointDBSchema(22), MiniGameDreamEndingDBSchema(4), MiniGameDreamEndingRewardDBSchema(8), MiniGameDreamInfoDBSchema(2), MiniGameDreamParameterDBSchema(8), MiniGameDreamReplayScenarioDBSchema(20), MiniGameDreamScheduleDBSchema(8), MiniGameDreamScheduleResultDBSchema(48), MiniGameDreamTimelineDBSchema(70), MiniGameMissionDBSchema(402), MiniGamePlayGuideDBSchema(134), MiniGameRhythmBgmDBSchema(7), MiniGameRhythmDBSchema(20), MiniGameRoadPuzzleInfoDBSchema(2), MiniGameRoadPuzzleRailSetRewardDBSchema(1), MiniGameRoadPuzzleRewardDBSchema(7), MiniGameRoadPuzzleVoiceDBSchema(12), MiniGameShootingCharacterDBSchema(197), MiniGameShootingGeasDBSchema(16), MiniGameShootingStageDBSchema(7), MiniGameShootingStageRewardDBSchema(98), MiniGameTBGThemaRewardDBSchema(70), PermanentRaidManageDBSchema(13)

**`arena` 竞技场**（6 张）：

ArenaLevelSectionDBSchema(52), ArenaMapDBSchema(60), ArenaNPCDBSchema(13), ArenaRewardDBSchema(108), ArenaSeasonCloseRewardDBSchema(0), ArenaSeasonDBSchema(9)

**`raid` 总力战/Raid**（30 张）：

EliminateRaidRankingRewardDBSchema(74), EliminateRaidRankingRewardUODBSchema(74), EliminateRaidSeasonManageDBSchema(27), EliminateRaidStageDBSchema(490), EliminateRaidStageLimitedRewardDBSchema(40), EliminateRaidStageRewardDBSchema(121), EliminateRaidStageSeasonRewardDBSchema(1854), InteractiveWorldRaidArcadeMachineDBSchema(1), InteractiveWorldRaidBossGroupDBSchema(12), InteractiveWorldRaidCarrierDBSchema(7), InteractiveWorldRaidCarrierMapDBSchema(44), InteractiveWorldRaidCarrierRecipeDBSchema(25), InteractiveWorldRaidConditionDBSchema(21), InteractiveWorldRaidSeasonManageDBSchema(0), InteractiveWorldRaidSkillDescriptionListDBSchema(56), InteractiveWorldRaidStageDBSchema(56), InteractiveWorldRaidStatusPresetDBSchema(20), RaidContentPlayGuideDBSchema(2), RaidRankingRewardDBSchema(265), RaidRankingRewardUODBSchema(265), RaidSeasonManageDBSchema(78), RaidStageDBSchema(156), RaidStageRewardDBSchema(161), RaidStageSeasonRewardDBSchema(3008), WorldRaidBossGroupDBSchema(21), WorldRaidConditionDBSchema(5), WorldRaidFavorBuffDBSchema(150), WorldRaidSeasonManageDBSchema(5), WorldRaidStageDBSchema(103), WorldRaidStageRewardDBSchema(4414)

**`clan` 社团/好友/邮件**（2 张）：

ClanChattingEmojiDBSchema(176), ClanRewardDBSchema(1)

**`combat` 技能/战斗逻辑**（19 张）：

BattleLevelFactorDBSchema(51), CombatEmojiDBSchema(29), ContentTargetGroupDBSchema(3), FixedStrategyDBSchema(9), GrowthScoreCalculationDBSchema(18), LogicEffectCommonVisualDBSchema(211), OperatorDBSchema(237), PersonalityDBSchema(149), PresetCharacterGroupDBSchema(165), PresetCharacterGroupSettingDBSchema(254), PresetParcelsDBSchema(1636), SkillAdditionalTooltipDBSchema(45), SkillDBSchema(18028), SkillSelectExTooltipDBSchema(6), SpineLipsyncDBSchema(93), StatLevelInterpolationDBSchema(199), StrategyObjectBuffDefineDBSchema(4), TerrainAdaptationFactorDBSchema(18), UnderCoverStageDBSchema(11)

**`craft` 制造**（5 张）：

RecipeDBSchema(6973), RecipeIngredientDBSchema(6899), RecipeSelectionAutoUseDBSchema(267), RecipeSelectionGroupDBSchema(2243), ShiftingCraftRecipeDBSchema(87)

**`currency` 货币/账号**（3 张）：

AccountLevelDBSchema(90), AccountLevelRewardDBSchema(6), CurrencyDBSchema(29)

**`battlepass` 通行证**（5 张）：

BattlePassExpLimitDBSchema(5), BattlePassFlavorTextDBSchema(45), BattlePassInfoDBSchema(1), BattlePassLevelDBSchema(120), BattlePassRewardDBSchema(240)

**`localize` 本地化文本**（7 张）：

LocalizeCharProfileChangeDBSchema(4), LocalizeCharProfileDBSchema(264), LocalizeDBSchema(18456), LocalizeErrorDBSchema(429), LocalizeEtcDBSchema(5379), LocalizeGachaShopDBSchema(1235), LocalizeSkillDBSchema(14155)

**`audio` 音频**（8 张）：

AudioAnimatorDBSchema(1212), SoundUIDBSchema(9), VoiceCommonDBSchema(34), VoiceDBSchema(10895), VoiceLogicEffectDBSchema(85), VoiceRoomExceptionDBSchema(8), VoiceSpineDBSchema(2510), VoiceTimelineDBSchema(15)

**`ui` UI/弹窗**（17 张）：

AlertPopupDBSchema(1), CameraDBSchema(81), ContentSpoilerPopupDBSchema(1), FloaterCommonDBSchema(11), HpBarAbbreviationDBSchema(300), InformationDBSchema(243), InformationStrategyObjectDBSchema(7), KeyMappingDBSchema(128), KeyMappingPopupDBSchema(253), LoadingImageDBSchema(57), MessagePopupDBSchema(77), MomotalkScheduleSpoilerPopupDBSchema(2), ShortcutTypeDBSchema(5), ToastDBSchema(98), TrophyCollectionDBSchema(13), VideoDBSchema(308), WebSeasonDBSchema(23)

**`misc` 杂项**（10 张）：

ContentEnterCostReduceDBSchema(60), ContentsFeverDBSchema(4), ContentsScenarioDBSchema(28), ContentsShortcutDBSchema(12), CouponCompleteDBSchema(1), DuplicateBonusDBSchema(5), FarmingDungeonLocationManageDBSchema(8), OpenConditionDBSchema(54), PossessionCheckDBSchema(1), ServiceActionDBSchema(2)

**`other` 未归类**（1 张）：

StoryStrategyDBSchema(9)

### 2.2 全表行数（字母序，398 行）

| 表 | 行数 | SQL 键列 | 被用作来源的协议字段数 |
|---|---|---|---|
| `AcademyFavorScheduleDBSchema` | 1053 | Id,ScheduleGroupId | 1 |
| `AcademyLocationDBSchema` | 11 | Id | 1 |
| `AcademyLocationRankDBSchema` | 12 | Rank | 0 |
| `AcademyMessangerDBSchema` | 15050 | MessageGroupId,Id,CharacterId | 2 |
| `AcademyRewardDBSchema` | 564 | Id | 0 |
| `AcademyTicketDBSchema` | 5 | LocationRankSum | 0 |
| `AcademyZoneDBSchema` | 95 | Id | 0 |
| `AccountLevelDBSchema` | 90 | Id | 0 |
| `AccountLevelRewardDBSchema` | 6 | Id,Level | 1 |
| `AlertPopupDBSchema` | 1 | Id | 0 |
| `ArenaLevelSectionDBSchema` | 52 | ArenaSeasonId | 0 |
| `ArenaMapDBSchema` | 60 | UniqueId | 0 |
| `ArenaNPCDBSchema` | 13 | UniqueId | 1 |
| `ArenaRewardDBSchema` | 108 | UniqueId,ArenaRewardType | 0 |
| `ArenaSeasonCloseRewardDBSchema` | 0 | SeasonId | 0 |
| `ArenaSeasonDBSchema` | 9 | UniqueId | 0 |
| `AssistEchelonTypeConvertDBSchema` | 6 | Contents | 0 |
| `AssistRewardDBSchema` | 7 | RewardType,EchelonType | 0 |
| `AssistSlotDBSchema` | 12 | SlotId | 0 |
| `AttendanceDBSchema` | 31 | Id | 0 |
| `AttendanceRewardDBSchema` | 334 | AttendanceId | 0 |
| `AudioAnimatorDBSchema` | 1212 | ControllerNameHash | 0 |
| `BGMDBSchema` | 378 | Id | 0 |
| `BGMRaidDBSchema` | 828 | StageId,PhaseIndex | 0 |
| `BGMUIDBSchema` | 202 | UIPrefab,EventContentId | 0 |
| `BattleLevelFactorDBSchema` | 51 | LevelDiff | 0 |
| `BattlePassExpLimitDBSchema` | 5 | BattlePassId | 0 |
| `BattlePassFlavorTextDBSchema` | 45 | GroupId | 0 |
| `BattlePassInfoDBSchema` | 1 | Id | 0 |
| `BattlePassLevelDBSchema` | 120 | BattlePassId,Level | 0 |
| `BattlePassMissionDBSchema` | 19 | BattlePassId,Id | 0 |
| `BattlePassRewardDBSchema` | 240 | Id,RewardGroupId,Level | 0 |
| `BossExternalBTDBSchema` | 10693 | ExternalBTId | 0 |
| `BulletArmorDamageFactorDBSchema` | 56 | DamageFactorGroupId,BulletType,ArmorType | 0 |
| `CafeInfoDBSchema` | 2 | CafeId | 2 |
| `CafeInteractionDBSchema` | 253 | CharacterId | 0 |
| `CafeProductionDBSchema` | 30 | CafeId | 0 |
| `CafeRankDBSchema` | 20 | CafeId,Rank | 0 |
| `CameraDBSchema` | 81 | UniqueId | 0 |
| `CampaignChapterDBSchema` | 29 | Id | 4 |
| `CampaignChapterRewardDBSchema` | 60 | Id | 0 |
| `CampaignStageDBSchema` | 407 | Id | 3 |
| `CampaignStageRewardDBSchema` | 3004 | GroupId | 0 |
| `CampaignStrategyObjectDBSchema` | 133 | Id | 0 |
| `CampaignUnitDBSchema` | 1630 | Id | 0 |
| `CharacterAIDBSchema` | 70 | Id | 0 |
| `CharacterAcademyTagsDBSchema` | 253 | Id | 0 |
| `CharacterCalculationLimitDBSchema` | 22 | TacticEntityType,CalculationValue | 0 |
| `CharacterCombatSkinDBSchema` | 1 | GroupId | 0 |
| `CharacterDBSchema` | 7223 | Id,ProductionStep,MainCombatStyleId | 5 |
| `CharacterDialogBattlePassDBSchema` | 54 | CostumeUniqueId,OriginalCharacterId,BattlePassID,DialogCategory,DialogCondition | 0 |
| `CharacterDialogDBSchema` | 11784 | CharacterId,DialogCategory,DialogCondition | 0 |
| `CharacterDialogEmojiDBSchema` | 414 | GroupId,CharacterId | 0 |
| `CharacterDialogEventDBSchema` | 7629 | CostumeUniqueId,OriginalCharacterId,EventID,DialogCategory,DialogCondition | 0 |
| `CharacterDialogSubtitleDBSchema` | 5501 | LocalizeCVGroup,CharacterId | 0 |
| `CharacterGearDBSchema` | 104 | Id | 0 |
| `CharacterGearLevelDBSchema` | 1 | Level | 0 |
| `CharacterIllustCoordinateDBSchema` | 254 | Id | 0 |
| `CharacterLevelDBSchema` | 90 | Level | 0 |
| `CharacterLevelStatFactorDBSchema` | 200 | Level | 0 |
| `CharacterPotentialDBSchema` | 762 | Id,PotentialStatBonusRateType | 0 |
| `CharacterPotentialRewardDBSchema` | 254 | Id | 0 |
| `CharacterPotentialStatDBSchema` | 1638 | PotentialStatGroupId,PotentialLevel | 0 |
| `CharacterSkillListDBSchema` | 6708 | CharacterSkillListGroupId,MinimumGradeCharacterWeapon,MinimumTierCharacterGear,FormIndex,TSAInteractionId | 0 |
| `CharacterStatDBSchema` | 7242 | CharacterId | 0 |
| `CharacterStatLimitDBSchema` | 224 | Id | 0 |
| `CharacterStatsDetailDBSchema` | 10 | Id | 0 |
| `CharacterStatsTransDBSchema` | 16 | EchelonExtensionType,StatTransType | 0 |
| `CharacterTranscendenceDBSchema` | 789 | CharacterId | 0 |
| `CharacterVictoryInteractionDBSchema` | 16 | CostumeId01 | 0 |
| `CharacterVoiceDBSchema` | 9493 | CharacterVoiceGroupId,VoiceHash | 0 |
| `CharacterVoiceSubtitleDBSchema` | 6529 | LocalizeCVGroup,CharacterVoiceGroupId | 0 |
| `CharacterWeaponDBSchema` | 254 | Id | 0 |
| `CharacterWeaponExpBonusDBSchema` | 11 | WeaponType | 0 |
| `CharacterWeaponLevelDBSchema` | 70 | Level | 0 |
| `ClanChattingEmojiDBSchema` | 176 | Id | 0 |
| `ClanRewardDBSchema` | 1 | ClanRewardType | 0 |
| `CombatEmojiDBSchema` | 29 | EmojiEvent | 0 |
| `ConquestCalculateDBSchema` | 3 | EventContentId | 0 |
| `ConquestCameraSettingDBSchema` | 14 | Id | 0 |
| `ConquestErosionDBSchema` | 7 | EventContentId,Id,ErosionType,StepIndex | 0 |
| `ConquestErosionUnitDBSchema` | 29 | TilePrefabId | 0 |
| `ConquestEventDBSchema` | 5 | EventContentId,MainStoryEventContentId | 0 |
| `ConquestGroupBonusDBSchema` | 36 | ConquestBonusId | 0 |
| `ConquestGroupBuffDBSchema` | 24 | ConquestBuffId | 0 |
| `ConquestMapDBSchema` | 24 | EventContentId | 0 |
| `ConquestObjectDBSchema` | 12 | Id,EventContentId,ConquestObjectType,StepIndex | 0 |
| `ConquestPlayGuideDBSchema` | 24 | EventContentId | 0 |
| `ConquestProgressResourceDBSchema` | 24 | EventContentId,Group | 0 |
| `ConquestRewardDBSchema` | 1422 | GroupId | 0 |
| `ConquestTileDBSchema` | 152 | Id,TileType | 0 |
| `ConquestUnexpectedEventDBSchema` | 2 | EventContentId | 0 |
| `ConquestUnitDBSchema` | 218 | Id | 0 |
| `ContentEnterCostReduceDBSchema` | 60 | EnterCostReduceGroupId | 0 |
| `ContentSpoilerPopupDBSchema` | 1 | ContentType | 0 |
| `ContentTargetGroupDBSchema` | 3 | TargetGroup | 0 |
| `ContentsFeverDBSchema` | 4 | ConditionContent | 0 |
| `ContentsScenarioDBSchema` | 28 | Id | 0 |
| `ContentsShortcutDBSchema` | 12 | ContentType,EventContentId,ScenarioModeType,ScenarioModeVolume,ScenarioModeChapter | 0 |
| `CostumeDBSchema` | 5913 | CostumeGroupId,CostumeUniqueId | 0 |
| `CouponCompleteDBSchema` | 1 | GroupId | 0 |
| `CurrencyDBSchema` | 29 | ID | 1 |
| `DuplicateBonusDBSchema` | 5 | ItemId,CharacterId | 0 |
| `EchelonConstraintDBSchema` | 4 | GroupId | 0 |
| `EliminateRaidRankingRewardDBSchema` | 74 | RankingRewardGroupId | 0 |
| `EliminateRaidRankingRewardUODBSchema` | 74 | RankingRewardGroupId | 0 |
| `EliminateRaidSeasonManageDBSchema` | 27 | SeasonId | 0 |
| `EliminateRaidStageDBSchema` | 490 | Id | 0 |
| `EliminateRaidStageLimitedRewardDBSchema` | 40 | LimitedRewardId | 0 |
| `EliminateRaidStageRewardDBSchema` | 121 | GroupId | 0 |
| `EliminateRaidStageSeasonRewardDBSchema` | 1854 | SeasonRewardId | 0 |
| `EmblemDBSchema` | 1065 | Id | 2 |
| `EquipmentDBSchema` | 191 | Id | 1 |
| `EquipmentLevelDBSchema` | 70 | Level | 0 |
| `EquipmentStatDBSchema` | 191 | EquipmentId | 0 |
| `EventContentArchiveBannerOffsetDBSchema` | 25 | EventContentId | 2 |
| `EventContentBoxGachaManageDBSchema` | 204 | EventContentId | 0 |
| `EventContentBoxGachaShopDBSchema` | 2478 | EventContentId | 0 |
| `EventContentBuffDBSchema` | 160 | EventContentBuffId | 0 |
| `EventContentBuffGroupDBSchema` | 141 | EventContentId,BuffContentId,BuffGroupId | 0 |
| `EventContentCardDBSchema` | 159 | CardGroupId,EventContentId | 0 |
| `EventContentCardShopDBSchema` | 835 | EventContentId,Id,CardGroupId | 1 |
| `EventContentCardShopModifyDBSchema` | 13 | EventContentId | 0 |
| `EventContentChangeDBSchema` | 20 | EventContentId | 0 |
| `EventContentChangeScenarioDBSchema` | 24 | EventContentId | 0 |
| `EventContentCharacterBonusDBSchema` | 2172 | EventContentId,CharacterId | 0 |
| `EventContentClueDBSchema` | 0 | EventContentId,ClueId | 0 |
| `EventContentClueSearchDBSchema` | 0 | EventContentId | 0 |
| `EventContentClueSearchRewardDBSchema` | 0 | Id | 0 |
| `EventContentClueSearchRoundDBSchema` | 0 | EventContentId,Round | 0 |
| `EventContentCollectionDBSchema` | 153 | EventContentId,GroupId | 0 |
| `EventContentConcentrationCardDBSchema` | 6 | EventContentId,CardId | 0 |
| `EventContentConcentrationDBSchema` | 1 | EventContentId | 0 |
| `EventContentConcentrationRewardDBSchema` | 14 | EventContentId,UniqueId,ConcentrationRewardType | 0 |
| `EventContentConcentrationVoiceDBSchema` | 10 | EventContentId,UniqueId | 0 |
| `EventContentCurrencyItemDBSchema` | 415 | EventContentId,ItemUniqueId | 0 |
| `EventContentDebuffRewardDBSchema` | 22 | EventContentId,EventStageId | 0 |
| `EventContentDiceRaceDBSchema` | 5 | EventContentId | 0 |
| `EventContentDiceRaceEffectDBSchema` | 45 | EventContentId | 0 |
| `EventContentDiceRaceNodeDBSchema` | 90 | EventContentId | 0 |
| `EventContentDiceRaceProbDBSchema` | 60 | EventContentId | 0 |
| `EventContentDiceRaceTotalRewardDBSchema` | 99 | EventContentId | 0 |
| `EventContentFortuneGachaDBSchema` | 154 | FortuneGachaGroupId | 0 |
| `EventContentFortuneGachaModifyDBSchema` | 9 | EventContentId | 0 |
| `EventContentFortuneGachaShopDBSchema` | 188 | EventContentId | 0 |
| `EventContentLobbyMenuDBSchema` | 32 | EventContentId,EventContentType | 0 |
| `EventContentLocationDBSchema` | 6 | EventContentId | 0 |
| `EventContentLocationRewardDBSchema` | 240 | Id | 0 |
| `EventContentMeetupDBSchema` | 121 | Id,EventContentId,ConditionScenarioGroupId | 0 |
| `EventContentMeetupInfoDBSchema` | 4 | EventContentId | 0 |
| `EventContentMiniEventShortCutDBSchema` | 2 | Id | 0 |
| `EventContentMiniEventTokenDBSchema` | 19 | EventContentId,ItemUniqueId | 0 |
| `EventContentMissionDBSchema` | 2384 | Id,EventContentId | 0 |
| `EventContentNotifyDBSchema` | 12 | Id | 0 |
| `EventContentPlayGuideDBSchema` | 484 | EventContentId | 0 |
| `EventContentScenarioDBSchema` | 955 | EventContentId | 0 |
| `EventContentSeasonDBSchema` | 412 | EventContentId,EventContentType | 0 |
| `EventContentShopDBSchema` | 3874 | Id | 0 |
| `EventContentShopInfoDBSchema` | 276 | EventContentId,CategoryType | 0 |
| `EventContentShopRefreshDBSchema` | 0 | Id | 0 |
| `EventContentSpecialOperationsDBSchema` | 2 | EventContentId | 0 |
| `EventContentSpineDialogOffsetDBSchema` | 645 | EventContentId,EventContentType,CostumeUniqueId | 0 |
| `EventContentSpineDisplayPeriodDBSchema` | 13 | EventContentId,DialogCategory | 0 |
| `EventContentSpoilerPopupDBSchema` | 15 | EventContentId | 0 |
| `EventContentStageDBSchema` | 2353 | Id,EventContentId | 0 |
| `EventContentStageRewardDBSchema` | 16642 | GroupId | 0 |
| `EventContentStageTotalRewardDBSchema` | 1525 | EventContentId | 0 |
| `EventContentTreasureCellRewardDBSchema` | 9 | Id | 0 |
| `EventContentTreasureDBSchema` | 9 | EventContentId | 0 |
| `EventContentTreasureRewardDBSchema` | 114 | Id | 0 |
| `EventContentTreasureRoundDBSchema` | 61 | EventContentId | 0 |
| `EventContentZoneDBSchema` | 48 | Id | 0 |
| `EventContentZoneVisitRewardDBSchema` | 0 | EventContentId,EventContentLocationId | 0 |
| `FarmingDungeonLocationManageDBSchema` | 8 | FarmingDungeonLocationId | 0 |
| `FavorLevelDBSchema` | 100 | Level | 0 |
| `FavorLevelRewardDBSchema` | 12650 | CharacterId | 0 |
| `FixedEchelonSettingDBSchema` | 266 | FixedEchelonID | 0 |
| `FixedStrategyDBSchema` | 9 | Id | 0 |
| `FloaterCommonDBSchema` | 11 | TacticEntityType | 0 |
| `FormationLocationDBSchema` | 56 | GroupID | 0 |
| `FurnitureDBSchema` | 876 | Id | 3 |
| `FurnitureGroupDBSchema` | 23 | Id | 0 |
| `FurnitureTemplateDBSchema` | 21 | FurnitureTemplateId | 0 |
| `FurnitureTemplateElementDBSchema` | 1538 | FurnitureTemplateId | 0 |
| `GachaCombinedCostDBSchema` | 24 | GroupId | 0 |
| `GachaCraftNodeDBSchema` | 141 | ID | 0 |
| `GachaCraftNodeGroupDBSchema` | 291 | NodeId | 0 |
| `GachaCraftOpenTagDBSchema` | 3 | NodeTier | 0 |
| `GachaElementDBSchema` | 14922 | ID,GachaGroupID | 2 |
| `GachaElementRecursiveDBSchema` | 669 | ID,GachaGroupID | 0 |
| `GachaGroupDBSchema` | 1556 | ID | 0 |
| `GachaSelectPickupGroupDBSchema` | 98 | Id | 0 |
| `GoodsDBSchema` | 9422 | Id | 0 |
| `GroundDBSchema` | 4399 | Id | 0 |
| `GroundModuleRewardDBSchema` | 42 | GroupId | 0 |
| `GrowthScoreCalculationDBSchema` | 18 | IncludeGrowthFactor | 0 |
| `GuideMissionDBSchema` | 923 | Id | 3 |
| `GuideMissionOpenStageConditionDBSchema` | 9 | SeasonId,OrderNumber | 0 |
| `GuideMissionSeasonDBSchema` | 20 | Id | 1 |
| `HpBarAbbreviationDBSchema` | 300 | MonsterLv | 0 |
| `IdCardBackgroundDBSchema` | 17 | Id | 0 |
| `InformationDBSchema` | 243 | GroupID | 0 |
| `InformationStrategyObjectDBSchema` | 7 | StageId | 0 |
| `InteractiveWorldRaidArcadeMachineDBSchema` | 1 | EventContentId | 0 |
| `InteractiveWorldRaidBossGroupDBSchema` | 12 | Id,WorldRaidBossGroupId | 0 |
| `InteractiveWorldRaidCarrierDBSchema` | 7 | CarrierSkillListGroupId | 0 |
| `InteractiveWorldRaidCarrierMapDBSchema` | 44 | Id,WorldRaidSeasonId,WorldRaidPhaseId | 0 |
| `InteractiveWorldRaidCarrierRecipeDBSchema` | 25 | SkillId | 0 |
| `InteractiveWorldRaidConditionDBSchema` | 21 | WorldRaidSeasonId,WorldRaidPhaseId | 0 |
| `InteractiveWorldRaidSeasonManageDBSchema` | 0 | SeasonId,PhaseId | 0 |
| `InteractiveWorldRaidSkillDescriptionListDBSchema` | 56 | Id | 0 |
| `InteractiveWorldRaidStageDBSchema` | 56 | Id,WorldRaidBossGroupId | 0 |
| `InteractiveWorldRaidStatusPresetDBSchema` | 20 | Id | 0 |
| `ItemDBSchema` | 1803 | Id | 5 |
| `KeyMappingDBSchema` | 128 | Id | 0 |
| `KeyMappingPopupDBSchema` | 253 | PrefabName | 0 |
| `LevelExpMasterCoinDBSchema` | 2 | Id | 0 |
| `LoadingImageDBSchema` | 57 | ID | 0 |
| `LocalizeCharProfileChangeDBSchema` | 4 | CharacterId | 0 |
| `LocalizeCharProfileDBSchema` | 264 | CharacterId | 0 |
| `LocalizeDBSchema` | 18456 | Key | 0 |
| `LocalizeErrorDBSchema` | 429 | Key | 0 |
| `LocalizeEtcDBSchema` | 5379 | Key | 0 |
| `LocalizeGachaShopDBSchema` | 1235 | GachaShopId | 1 |
| `LocalizeSkillDBSchema` | 14155 | Key | 0 |
| `LogicEffectCommonVisualDBSchema` | 211 | StringID | 0 |
| `MemoryLobbyDBSchema` | 258 | Id | 1 |
| `MessagePopupDBSchema` | 77 | StringId | 0 |
| `MiniGameAudioAnimatorDBSchema` | 11 | ControllerNameHash | 0 |
| `MiniGameDefenseCharacterBanDBSchema` | 15 | EventContentId | 0 |
| `MiniGameDefenseFixedStatDBSchema` | 8 | MinigameDefenseFixedStatId | 0 |
| `MiniGameDefenseInfoDBSchema` | 2 | EventContentId | 0 |
| `MiniGameDefenseStageDBSchema` | 22 | Id,EventContentId | 0 |
| `MiniGameDreamCollectionScenarioDBSchema` | 48 | EventContentId | 0 |
| `MiniGameDreamDailyPointDBSchema` | 22 | EventContentId | 0 |
| `MiniGameDreamEndingDBSchema` | 4 | EventContentId,EndingId | 0 |
| `MiniGameDreamEndingRewardDBSchema` | 8 | EventContentId,EndingId | 0 |
| `MiniGameDreamInfoDBSchema` | 2 | EventContentId | 0 |
| `MiniGameDreamParameterDBSchema` | 8 | Id,EventContentId,ParameterType | 0 |
| `MiniGameDreamReplayScenarioDBSchema` | 20 | EventContentId | 0 |
| `MiniGameDreamScheduleDBSchema` | 8 | EventContentId,DreamMakerScheduleGroupId | 0 |
| `MiniGameDreamScheduleResultDBSchema` | 48 | EventContentId,DreamMakerScheduleGroup | 0 |
| `MiniGameDreamTimelineDBSchema` | 70 | EventContentId,DreamMakerDays,DreamMakerActionPoint | 0 |
| `MiniGameMissionDBSchema` | 402 | Id | 0 |
| `MiniGamePlayGuideDBSchema` | 134 | EventContentId | 0 |
| `MiniGameRhythmBgmDBSchema` | 7 | RhythmBgmId,EventContentId | 0 |
| `MiniGameRhythmDBSchema` | 20 | UniqueId | 0 |
| `MiniGameRoadPuzzleInfoDBSchema` | 2 | EventContentId | 0 |
| `MiniGameRoadPuzzleRailSetRewardDBSchema` | 1 | EventContentId,UniqueId | 0 |
| `MiniGameRoadPuzzleRewardDBSchema` | 7 | EventContentId,UniqueId | 0 |
| `MiniGameRoadPuzzleVoiceDBSchema` | 12 | EventContentId,UniqueId,VoiceCondition | 0 |
| `MiniGameShootingCharacterDBSchema` | 197 | UniqueId | 0 |
| `MiniGameShootingGeasDBSchema` | 16 | UniqueId | 0 |
| `MiniGameShootingStageDBSchema` | 7 | UniqueId | 0 |
| `MiniGameShootingStageRewardDBSchema` | 98 | GroupId | 0 |
| `MiniGameTBGThemaRewardDBSchema` | 70 | EventContentId,ThemaUniqueId,MiniGameTBGThemaRewardType | 0 |
| `MinigameCCGCardDBSchema` | 66 | Id | 0 |
| `MinigameCCGCharacterDBSchema` | 73 | Id | 0 |
| `MinigameCCGEnemyDBSchema` | 144 | Id,GroupId | 0 |
| `MinigameCCGEnemyGroupDBSchema` | 41 | GroupId | 0 |
| `MinigameCCGInfoDBSchema` | 2 | EventContentId | 0 |
| `MinigameCCGLevelDBSchema` | 42 | LevelId | 0 |
| `MinigameCCGLevelNodeDBSchema` | 570 | LevelId,NodeId | 0 |
| `MinigameCCGLevelStageDBSchema` | 110 | Id | 0 |
| `MinigameCCGLogicEffectDBSchema` | 131 | Id | 0 |
| `MinigameCCGOpenDialogDBSchema` | 120 | DialogId,ConditionCard | 0 |
| `MinigameCCGPerkDBSchema` | 52 | Id,CCGId | 0 |
| `MinigameCCGRewardCardDBSchema` | 116 | Id | 0 |
| `MinigameCCGRewardCardRateDBSchema` | 13 | RarityGroupId | 0 |
| `MinigameCCGRewardItemDBSchema` | 101 | CCGId | 0 |
| `MinigameCCGSkillDBSchema` | 282 | Id | 0 |
| `MinigameCCGStartDeckCardDBSchema` | 20 | CCGId | 0 |
| `MinigameCCGStartDeckCharacterDBSchema` | 2 | CCGId | 0 |
| `MinigameDreamVoiceDBSchema` | 32 | EventContentId | 0 |
| `MinigameRoadPuzzleAdditionalRewardDBSchema` | 15 | EventContentId,UniqueId | 0 |
| `MinigameRoadPuzzleMapDBSchema` | 27 | EventContentId,UniqueId,MapGroupId | 0 |
| `MinigameRoadPuzzleMapTileDBSchema` | 38 | EventContentId,UniqueId,MapTileType | 0 |
| `MinigameRoadPuzzleRailTileDBSchema` | 8 | EventContentId,UniqueId,RailTileType | 0 |
| `MinigameRoadPuzzleRoadRoundDBSchema` | 19 | EventContentId,UniqueId,Round,MapGroupId | 0 |
| `MinigameTBGDiceDBSchema` | 48 | EventContentId,DiceGroup | 0 |
| `MinigameTBGEncounterDBSchema` | 187 | UniqueId | 0 |
| `MinigameTBGEncounterOptionDBSchema` | 362 | UniqueId | 0 |
| `MinigameTBGEncounterRewardDBSchema` | 1122 | GroupId | 0 |
| `MinigameTBGItemDBSchema` | 64 | UniqueId | 0 |
| `MinigameTBGObjectDBSchema` | 21 | UniqueId | 0 |
| `MinigameTBGSeasonDBSchema` | 2 | EventContentId | 0 |
| `MinigameTBGThemaDBSchema` | 13 | EventContentId,ThemaIndex,ThemaType | 0 |
| `MinigameTBGVoiceDBSchema` | 56 | EventContentId,VoiceCondition | 0 |
| `MissionDBSchema` | 3444 | Id | 0 |
| `MissionEmergencyCompleteDBSchema` | 0 | MissionId | 0 |
| `MomotalkScheduleSpoilerPopupDBSchema` | 2 | FavorScheduleId | 0 |
| `MultiFloorRaidRewardDBSchema` | 3478 | RewardGroupId | 0 |
| `MultiFloorRaidSeasonManageDBSchema` | 18 | SeasonId | 0 |
| `MultiFloorRaidStageDBSchema` | 744 | Id,BossGroupId | 0 |
| `MultiFloorRaidStatChangeDBSchema` | 992 | StatChangeId | 0 |
| `ObstacleFireLineCheckDBSchema` | 1 | MyObstacleFireLineCheck | 0 |
| `ObstacleStatDBSchema` | 468 | StringID | 0 |
| `OpenConditionDBSchema` | 54 | OpenConditionContentType | 0 |
| `OperatorDBSchema` | 237 | GroupId,OperatorCondition | 1 |
| `ParcelAutoSynthDBSchema` | 18 | RequireParcelType,RequireParcelId | 0 |
| `PermanentRaidManageDBSchema` | 13 | Type | 0 |
| `PersonalityDBSchema` | 149 | Id | 0 |
| `PickupDuplicateBonusDBSchema` | 2769 | Id,ShopId | 0 |
| `PickupFirstGetBonus2DBSchema` | 11 | Id | 0 |
| `PickupFirstGetBonusDBSchema` | 51 | ShopRecruitId | 0 |
| `PossessionCheckDBSchema` | 1 | UniqueId | 0 |
| `PresetCharacterGroupDBSchema` | 165 | PresetCharacterGroupId | 0 |
| `PresetCharacterGroupSettingDBSchema` | 254 | CharacterId | 0 |
| `PresetParcelsDBSchema` | 1636 | PresetGroupId | 0 |
| `ProductBattlePassDBSchema` | 12 | Id | 0 |
| `ProductDBSchema` | 605 | Id | 0 |
| `ProductDailyRecordDBSchema` | 4 | Id | 0 |
| `ProductDailyRecordInfoDBSchema` | 1 | Id | 0 |
| `ProductDailyRecordRewardDBSchema` | 14 | Id,Day | 0 |
| `ProductMonthlyDBSchema` | 36 | Id | 0 |
| `ProductSelectDBSchema` | 0 | Id | 0 |
| `ProductSelectionGroupDBSchema` | 249 | ProductSelectionGroupId,ProductSelectionGroupComponentId | 0 |
| `RaidContentPlayGuideDBSchema` | 2 | Id | 0 |
| `RaidRankingRewardDBSchema` | 265 | RankingRewardGroupId | 0 |
| `RaidRankingRewardUODBSchema` | 265 | RankingRewardGroupId | 0 |
| `RaidSeasonManageDBSchema` | 78 | SeasonId | 0 |
| `RaidStageDBSchema` | 156 | Id | 0 |
| `RaidStageRewardDBSchema` | 161 | GroupId | 0 |
| `RaidStageSeasonRewardDBSchema` | 3008 | SeasonRewardId | 0 |
| `RecipeDBSchema` | 6973 | Id | 0 |
| `RecipeIngredientDBSchema` | 6899 | Id | 0 |
| `RecipeSelectionAutoUseDBSchema` | 267 | ParcelType,TargetItemId | 0 |
| `RecipeSelectionGroupDBSchema` | 2243 | RecipeSelectionGroupId,ParcelType,ParcelId | 0 |
| `ScenarioBGEffectDBSchema` | 86 | Name | 0 |
| `ScenarioBGNameDBSchema` | 3663 | Name | 0 |
| `ScenarioCharacterEmotionDBSchema` | 63 | Name | 0 |
| `ScenarioCharacterNameDBSchema` | 2403 | CharacterName | 0 |
| `ScenarioCharacterSituationSetDBSchema` | 2 | Name | 0 |
| `ScenarioContentCollectionDBSchema` | 10 | Id | 0 |
| `ScenarioEffectDBSchema` | 6 | Name | 0 |
| `ScenarioModeDBSchema` | 581 | ModeId | 3 |
| `ScenarioModeRewardDBSchema` | 630 | ScenarioModeRewardId | 0 |
| `ScenarioModeSpoilerPopupDBSchema` | 1 | ModeType,VolumeId,ChapterId | 0 |
| `ScenarioResourceInfoDBSchema` | 9 | Id | 0 |
| `ScenarioScriptDBSchema` | 362158 | GroupId | 1 |
| `ScenarioTransitionDBSchema` | 69 | Name | 0 |
| `SchoolDungeonRewardDBSchema` | 81 | GroupId | 0 |
| `SchoolDungeonStageDBSchema` | 12 | StageId | 0 |
| `ServiceActionDBSchema` | 2 | ServiceActionType | 0 |
| `ShiftingCraftRecipeDBSchema` | 87 | Id | 0 |
| `ShopCashDBSchema` | 656 | Id | 1 |
| `ShopCashScenarioResourceInfoDBSchema` | 504 | ScenarioResrouceInfoId,ShopCashId | 0 |
| `ShopDBSchema` | 7908 | Id,CategoryType | 5 |
| `ShopFilterClassifiedDBSchema` | 1453 | GoodsId | 0 |
| `ShopFreeRecruitDBSchema` | 8 | Id | 0 |
| `ShopFreeRecruitPeriodDBSchema` | 67 | ShopFreeRecruitId | 0 |
| `ShopInfoDBSchema` | 18 | CategoryType | 1 |
| `ShopRecruitDBSchema` | 532 | Id | 2 |
| `ShopRefreshDBSchema` | 430 | Id,CategoryType | 0 |
| `ShopTabGroupDBSchema` | 10 | ShopGroupType | 1 |
| `ShortcutTypeDBSchema` | 5 | Id | 0 |
| `SkillAdditionalTooltipDBSchema` | 45 | GroupId | 0 |
| `SkillDBSchema` | 18028 | GroupId,Level | 0 |
| `SkillSelectExTooltipDBSchema` | 6 | GroupId | 0 |
| `SoundUIDBSchema` | 9 | SoundUniqueId | 0 |
| `SpineLipsyncDBSchema` | 93 | VoiceId | 0 |
| `StatLevelInterpolationDBSchema` | 199 | Level | 0 |
| `StickerGroupDBSchema` | 3 | Id | 0 |
| `StickerPageContentDBSchema` | 23 | Id | 1 |
| `StoryStrategyDBSchema` | 9 | Id | 0 |
| `StrategyObjectBuffDefineDBSchema` | 4 | StrategyObjectBuffID | 0 |
| `TacticEntityEffectFilterDBSchema` | 16 | TargetEffectName | 0 |
| `TacticSkipDBSchema` | 21 | LevelDiff | 0 |
| `TacticalSupportSystemDBSchema` | 22 | Id | 0 |
| `TerrainAdaptationFactorDBSchema` | 18 | TerrainAdaptation,TerrainAdaptationStat | 0 |
| `TimeAttackDungeonDBSchema` | 4 | Id | 0 |
| `TimeAttackDungeonGeasDBSchema` | 200 | Id | 0 |
| `TimeAttackDungeonRewardDBSchema` | 1 | Id | 0 |
| `TimeAttackDungeonSeasonManageDBSchema` | 39 | Id | 0 |
| `ToastDBSchema` | 98 | Id | 0 |
| `TrophyCollectionDBSchema` | 13 | GroupId | 0 |
| `TutorialCharacterDialogDBSchema` | 303 | TalkId | 0 |
| `TutorialDBSchema` | 33 | ID | 0 |
| `TutorialFailureImageDBSchema` | 426 | Contents | 0 |
| `UnderCoverStageDBSchema` | 11 | GroupId | 0 |
| `VideoDBSchema` | 308 | Id | 0 |
| `VoiceCommonDBSchema` | 34 | VoiceEvent | 0 |
| `VoiceDBSchema` | 10895 | Id | 0 |
| `VoiceLogicEffectDBSchema` | 85 | LogicEffectNameHash | 0 |
| `VoiceRoomExceptionDBSchema` | 8 | CostumeUniqueId | 0 |
| `VoiceSpineDBSchema` | 2510 | Id | 0 |
| `VoiceTimelineDBSchema` | 15 | Id | 0 |
| `WebSeasonDBSchema` | 23 | WebId | 0 |
| `WeekDungeonDBSchema` | 58 | StageId | 0 |
| `WeekDungeonGroupBuffDBSchema` | 13 | WeekDungeonBuffId | 0 |
| `WeekDungeonOpenScheduleDBSchema` | 7 | WeekDay | 0 |
| `WeekDungeonRewardDBSchema` | 786 | GroupId | 0 |
| `WorldRaidBossGroupDBSchema` | 21 | Id,WorldRaidBossGroupId | 0 |
| `WorldRaidConditionDBSchema` | 5 | Id | 0 |
| `WorldRaidFavorBuffDBSchema` | 150 | WorldRaidFavorRank | 0 |
| `WorldRaidSeasonManageDBSchema` | 5 | SeasonId | 0 |
| `WorldRaidStageDBSchema` | 103 | Id,WorldRaidBossGroupId | 0 |
| `WorldRaidStageRewardDBSchema` | 4414 | GroupId | 0 |

## 3. 重点协议：逐字段映射

口径：`来源` 只有在这一列有**官方真实值**撑住时才填；`玩家进度` = 私服自己存；`枚举` = 客户端常量；`未判定` = 官方值太小证明不了（不代表没有来源）。

### 4000.Item_List — `Item_List`

字段 5 个：静态表 1（verified 1 / ambiguous 0 / weak 0）｜玩家进度 3｜枚举/回显 1｜库里没有 0｜未判定 0

| 协议字段 | 判定 | 来源 | 置信度 | 证据 |
|---|---|---|---|---|
| `ItemDBs[].UniqueId` | 静态表 | `ItemDBSchema.Id` | **verified** | 134/134 命中 ItemDBSchema.Id（1803 行），其中 2 个值在全库仅 ≤8 个槽位出现、只有 ItemDBSchema 能全部解释；f0/f1 是同一 Id 的重复字段 |
| `ItemDBs[].Type` | 枚举(非表) | — | — | ParcelType 枚举，本响应恒为 4(=Item)。不是表字段：ItemDBSchema 与其 f5 只有 14/134 巧合相等；Equipment 列表里同位置恒为 3，所以 Type 由「在哪个背包 DB 里」决定 |
| `ItemDBs[].ServerId` | 玩家进度 | — | — | 玩家实例 id（24xxxxxx）：全库 398 张表 0 命中，每个账号各自分配 |
| `ItemDBs[].StackCount` | 玩家进度 | — | — | 玩家持有数量；50 个不同值，任何表都只是数值巧合命中 |
| `ExpiryItemDBs[]` | 玩家进度 | — | — | 本响应为空；限时道具按账号存 |

### 5000.Echelon_List — `Echelon_List`

字段 11 个：静态表 0（verified 0 / ambiguous 0 / weak 0）｜玩家进度 9｜枚举/回显 2｜库里没有 0｜未判定 0

| 协议字段 | 判定 | 来源 | 置信度 | 证据 |
|---|---|---|---|---|
| `EchelonDBs[].AccountServerId` | 玩家进度 | — | — | 账号 id |
| `EchelonDBs[].EchelonType` | 枚举(非表) | — | — | 编队类型枚举（观察到 1,2,3,4,6,11）；ExcelDB 里没有 EchelonType 表，是客户端 enum |
| `EchelonDBs[].EchelonNumber` | 玩家进度 | — | — | 第几队（1..3），玩家自己排的 |
| `EchelonDBs[].ExtensionType` | 枚举(非表) | — | — | 0=无扩展；枚举 |
| `EchelonDBs[].LeaderServerId` | 玩家进度 | — | — | 指向 CharacterDBs[].ServerId（角色实例 id），6 个值全库 0 命中 |
| `EchelonDBs[].MainSlotServerIds[]` | 玩家进度 | — | — | 同上，角色实例 id 列表；3043301/3002868 等可在 1017.CharacterListResponse.CharacterDBs[].ServerId 里找到 |
| `EchelonDBs[].SupportSlotServerIds[]` | 玩家进度 | — | — | 同上（支援位） |
| `EchelonDBs[].TSSInteractionServerId` | 玩家进度 | — | — | 战术支援角色实例 id，0=空 |
| `EchelonDBs[].UsingFlag` | 玩家进度 | — | — | 是否使用中 |
| `EchelonDBs[].SkillCardMulliganCharacterIds[]` | 玩家进度 | — | — | 洗牌保留用的角色实例 id |
| `EchelonDBs[].CombatStyleIndex[]` | 玩家进度 | — | — | 每格战斗风格下标 |

### 6000.Campaign_List — `Campaign_List`

字段 18 个：静态表 4（verified 1 / ambiguous 2 / weak 1）｜玩家进度 13｜枚举/回显 1｜库里没有 0｜未判定 0

| 协议字段 | 判定 | 来源 | 置信度 | 证据 |
|---|---|---|---|---|
| `StageHistoryDBs[].StageUniqueId` | 静态表 | `CampaignStageDBSchema.Id` | **verified** | 90/90 命中 CampaignStageDBSchema.Id（407 行）；5 个候选槽位里只有这张表能解释全部值 |
| `StageHistoryDBs[].ChapterUniqueId` | 静态表 | `CampaignChapterDBSchema.Id` | **ambiguous** | 16/16 值(101..116)都落在 CampaignChapterDBSchema.Id(101..129, 29 行)；纯值匹配有并列候选（FurnitureGroupDBSchema 等也含 101..116），但行级一致性可证：同一元素的 floor(StageUniqueId/10000) 对 90/90 条都等于 ChapterUniqueId |
| `CampaignChapterClearRewardHistoryDBs[].ChapterUniqueId` | 静态表 | `CampaignChapterDBSchema.Id` | **ambiguous** | 12/12 值落在 CampaignChapterDBSchema.Id；同上属低基数并列 |
| `CampaignChapterClearRewardHistoryDBs[].RewardType` | 枚举(非表) | — | — | 奖励类型枚举 |
| `CampaignChapterClearRewardHistoryDBs[].ReceiveDate` | 玩家进度 | — | — | 领取时间 |
| `StageHistoryDBs[].StoryUniqueId` | 玩家进度 | — | — | 剧情片段实例 id（0/小整数） |
| `StageHistoryDBs[].TacticClearCountWithRankSRecord` | 玩家进度 | — | — | S 评价通关次数 |
| `StageHistoryDBs[].ClearTurnRecord` | 玩家进度 | — | — | 最少回合数 |
| `StageHistoryDBs[].Star1Flag` | 玩家进度 | — | — | 星级条件 1 达成 |
| `StageHistoryDBs[].Star2Flag` | 玩家进度 | — | — | 星级条件 2 达成 |
| `StageHistoryDBs[].Star3Flag` | 玩家进度 | — | — | 星级条件 3 达成 |
| `StageHistoryDBs[].TodayPlayCount` | 玩家进度 | — | — | 今日游玩次数 |
| `StageHistoryDBs[].LastPlay` | 玩家进度 | — | — | 最后游玩时间 |
| `StageHistoryDBs[].FirstClearRewardReceive` | 玩家进度 | — | — | 首通奖励已领 |
| `StageHistoryDBs[].StarRewardReceive` | 玩家进度 | — | — | 星级奖励已领 |
| `StageHistoryDBs[].AccountServerId` | 玩家进度 | — | — | 账号 id |
| `CurrentScenarioId` | 静态表 | `ScenarioModeDBSchema.Id` | **weak** | 41200 命中 ScenarioModeDBSchema.Id（581 行，SQL 键列名 ModeId）；单值无法统计验证 |
| `CampaignChapterClearRewardHistoryDBs[].AccountServerId` | 玩家进度 | — | — | 值太少无法统计验证，且全库 0 命中、量级(≥1e7)像账号内自增 id /时间戳，推断为玩家数据（仅按量级推断） |

### 10002.Shop_List — `Shop_List`

字段 16 个：静态表 7（verified 2 / ambiguous 3 / weak 2）｜玩家进度 6｜枚举/回显 2｜库里没有 0｜未判定 1

| 协议字段 | 判定 | 来源 | 置信度 | 证据 |
|---|---|---|---|---|
| `ShopInfos[].EventContentId` | 回显/常量 | — | — | 0 = 非活动商店；活动商店时等于 EventContentId（玩家可见性） |
| `ShopInfos[].Category` | 静态表 | `ShopInfoDBSchema.CategoryType` | **ambiguous** | 官方值 38；ShopInfoDBSchema 的 18 个 CategoryType 键里含 38。单值无法统计验证，但同表 ShopDBSchema 中 CategoryType=38 恰好只有 2 行(Id 201/202)，与响应完全一致 |
| `ShopInfos[].ShopGroupType` | 静态表 | `ShopTabGroupDBSchema.ShopGroupType` | **weak** | 官方值 0（=无页签）；ShopTabGroupDBSchema 的键是 1..10，0 表示不在页签里，属于「缺省」而非查表 |
| `ShopInfos[].ManualRefreshCount` | 玩家进度 | — | — | 手动刷新次数 |
| `ShopInfos[].IsRefresh` | 玩家进度 | — | — | 刷新标记 |
| `ShopInfos[].NextAutoRefreshDate` | 玩家进度 | — | — | 下次自动刷新时间（null=无） |
| `ShopInfos[].LastAutoRefreshDate` | 玩家进度 | — | — | 上次自动刷新时间 |
| `ShopInfos[].ShopProductList[].ShopExcelId` | 静态表 | `ShopDBSchema.Id` | **verified** | 官方 201/202；ShopDBSchema 里 CategoryType=38 只有 2 行且 Id 正是 201/202，商品清单与表行一一对应（且 DisplayOrder=1 与 f6/f10=1 一致） |
| `ShopInfos[].ShopProductList[].Category` | 静态表 | `ShopDBSchema.CategoryType` | **verified** | 与 ShopExcelId 同源的列：201/202 行的 CategoryType 都是 38，官方也是 38 |
| `ShopInfos[].ShopProductList[].DisplayOrder` | 静态表 | `ShopDBSchema.f6/f10` | **ambiguous** | 官方值 1；ShopDB 行里 f6=1、f10=1、f11=1 都是 1，无法区分哪个是 DisplayOrder |
| `ShopInfos[].ShopProductList[].PurchaseCountLimit` | 静态表 | `ShopDBSchema.f6/f10/f11` | **ambiguous** | 官方值 1；同上，候选槽位值都是 1 |
| `ShopInfos[].ShopProductList[].PurchaseCount` | 玩家进度 | — | — | 已购买次数 |
| `ShopInfos[].ShopProductList[].SoldOut` | 玩家进度 | — | — | 是否售罄 |
| `ShopInfos[].ShopProductList[].Price` | 静态表 | `ShopDBSchema` | **weak** | 官方 Price=0；FlatBuffers 里 0 = 字段未写入，ShopDB 行里也没有可靠的 0 值槽位可对照（价格多半在 GoodsDBSchema 侧） |
| `ShopInfos[].ShopProductList[].ProductType` | 枚举(非表) | — | — | 0=单次商品；枚举 |
| `ShopInfos[].ShopProductList[].EventContentId` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |

### 20001.Cafe_Ack — `Cafe_Ack`

字段 27 个：静态表 4（verified 3 / ambiguous 0 / weak 1）｜玩家进度 21｜枚举/回显 2｜库里没有 0｜未判定 0

| 协议字段 | 判定 | 来源 | 置信度 | 证据 |
|---|---|---|---|---|
| `CafeDB.CafeId` | 静态表 | `CafeInfoDBSchema.CafeId` | **verified** | CafeInfoDBSchema 只有 2 行(CafeId=1,2)，1017 里两个 CafeDB 的 CafeId 正好是 1 和 2 |
| `CafeDB.CafeDBId` | 玩家进度 | — | — | 账号内咖啡厅实例 id = AccountId*100+n（100153543801） |
| `CafeDB.AccountId` | 玩家进度 | — | — | 账号 id |
| `CafeDB.CafeRank` | 玩家进度 | — | — | 玩家等级，上限由 CafeRankDBSchema(CafeId,Rank) 的 10 级 × 2 咖啡厅定义 |
| `CafeDB.LastUpdate` | 玩家进度 | — | — | 时间戳 |
| `CafeDB.LastSummonDate` | 玩家进度 | — | — | 上次召唤时间 |
| `CafeDB.IsNew` | 玩家进度 | — | — | 新内容标记 |
| `CafeDB.CafeVisitCharacterDBs.*.UniqueId` | 静态表 | `CharacterDBSchema.Id` | **verified** | 键/值都是角色 id，全部命中 CharacterDBSchema.Id（7223 行） |
| `CafeDB.CafeVisitCharacterDBs.*.ServerId` | 玩家进度 | — | — | 角色实例 id（与 CharacterDBs[].ServerId 同一空间） |
| `CafeDB.CafeVisitCharacterDBs.*.LastInteractTime` | 玩家进度 | — | — | 时间戳 |
| `CafeDB.FurnitureDBs[].UniqueId` | 静态表 | `FurnitureDBSchema.Id` | **verified** | 14/14 命中 FurnitureDBSchema.Id（876 行）；第二名候选只覆盖 93% |
| `CafeDB.FurnitureDBs[].ServerId` | 玩家进度 | — | — | 家具实例 id；全库 0 命中 |
| `CafeDB.FurnitureDBs[].Type` | 枚举(非表) | — | — | ParcelType，家具是 6 |
| `CafeDB.FurnitureDBs[].StackCount` | 玩家进度 | — | — | 持有数量 |
| `CafeDB.FurnitureDBs[].Location` | 玩家进度 | — | — | 摆在哪个咖啡厅（玩家选择） |
| `CafeDB.FurnitureDBs[].PositionX` | 玩家进度 | — | — | 摆放坐标（玩家选择） |
| `CafeDB.FurnitureDBs[].PositionY` | 玩家进度 | — | — | 摆放坐标；值匹配到 GachaCraftNodeDBSchema 只是数值巧合（坐标 3/5/7 这种小整数到处都是） |
| `CafeDB.FurnitureDBs[].Rotation` | 玩家进度 | — | — | 旋转（玩家选择） |
| `CafeDB.FurnitureDBs[].ItemDeploySequence` | 玩家进度 | — | — | 摆放顺序号；全库 0 命中 |
| `CafeDB.FurnitureDBs[].CafeDBId` | 玩家进度 | — | — | 所属咖啡厅实例 |
| `CafeDB.ProductionAppliedTime` | 玩家进度 | — | — | 生产结算时间 |
| `CafeDB.ProductionDB.ComfortValue` | 玩家进度 | — | — | 舒适度 = 家具累加，玩家派生值 |
| `CafeDB.ProductionDB.AppliedDate` | 玩家进度 | — | — | 时间戳 |
| `CafeDB.ProductionDB.CafeDBId` | 玩家进度 | — | — | 实例 id |
| `CafeDB.ProductionDB.ProductionParcelInfos[].Key.Id` | 静态表 | `ItemDBSchema.Id` | **weak** | 产出道具 id（2 个值，太小无法统计验证） |
| `CafeDB.ProductionDB.ProductionParcelInfos[].Key.Type` | 枚举(非表) | — | — | ParcelType |
| `CafeDB.ProductionDB.ProductionParcelInfos[].Amount` | 玩家进度 | — | — | 产出数量 |

### 24000.Academy_GetInfo — `Academy_GetInfo`

字段 9 个：静态表 2（verified 2 / ambiguous 0 / weak 0）｜玩家进度 7｜枚举/回显 0｜库里没有 0｜未判定 0

| 协议字段 | 判定 | 来源 | 置信度 | 证据 |
|---|---|---|---|---|
| `AcademyLocationDBs[].LocationId` | 静态表 | `AcademyLocationDBSchema.Id` | **verified** | 官方 9 个 [1,7,11,12,13,15,16,17,19] 全部命中表内 11 个 Id；表里多出 14(Trinity)、18(Shanhaijing) 两条官方响应没有 |
| `AcademyLocationDBs[].Rank` | 玩家进度 | — | — | 玩家把该地点升到几级，上限由 AcademyLocationRankDBSchema 的 Rank(1..12) 定义 |
| `AcademyLocationDBs[].Exp` | 玩家进度 | — | — | 该地点的经验值 |
| `AcademyLocationDBs[].AccountId` | 玩家进度 | — | — | 账号 id |
| `AcademyDB.AccountId` | 玩家进度 | — | — | 账号 id |
| `AcademyDB.LastUpdate` | 玩家进度 | — | — | 时间戳 |
| `AcademyDB.ZoneVisitCharacterDBs.*[].UniqueId` | 静态表 | `CharacterDBSchema.Id` | **verified** | 107 个不同角色 id 全部命中 CharacterDBSchema.Id(7223 行)，其中 2 个为稀有值 |
| `AcademyDB.ZoneVisitCharacterDBs.*[].ServerId` | 玩家进度 | — | — | 角色实例 id；全库 0 命中 |
| `AcademyDB.ZoneVisitCharacterDBs.*[].LastInteractTime` | 玩家进度 | — | — | 时间戳 |

### 1017.Account_LoginSync — `Account_LoginSync（26 个子回包）`

字段 240 个：静态表 28（verified 13 / ambiguous 7 / weak 8）｜玩家进度 102｜枚举/回显 12｜库里没有 5｜未判定 93

| 协议字段 | 判定 | 来源 | 置信度 | 证据 |
|---|---|---|---|---|
| `CharacterListResponse.CharacterDBs[].UniqueId` | 静态表 | `CharacterDBSchema.Id` | **verified** | 46/46 命中 CharacterDBSchema.Id(7223 行, 10000..838060812)；并列候选 CharacterStatDBSchema(7242 行) 也是角色 id 键，两者都成立 |
| `CharacterListResponse.CharacterDBs[].ServerId` | 玩家进度 | — | — | 角色实例 id(3002894…)——注意：题目里说的 CharacterDBs[0].UniqueId=3002894 其实是 ServerId，UniqueId=10006 才是角色定义 id |
| `CharacterListResponse.CharacterDBs[].Type` | 枚举(非表) | — | — | ParcelType=1(角色) |
| `CharacterListResponse.CharacterDBs[].StarGrade` | 玩家进度 | — | — | excel 里是 StarGrade 上限(CharacterDB.f4=3)，实际星级是玩家练度 |
| `CharacterListResponse.CharacterDBs[].Level` | 玩家进度 | — | — | 等级上限由 CharacterLevelDBSchema(90 行) 定义 |
| `CharacterListResponse.CharacterDBs[].Exp` | 玩家进度 | — | — | 经验 |
| `CharacterListResponse.CharacterDBs[].FavorRank` | 玩家进度 | — | — | 好感等级 |
| `CharacterListResponse.CharacterDBs[].FavorExp` | 玩家进度 | — | — | 好感经验 |
| `CharacterListResponse.CharacterDBs[].PublicSkillLevel` | 玩家进度 | — | — | 技能等级 |
| `CharacterListResponse.CharacterDBs[].ExSkillLevel` | 玩家进度 | — | — | 技能等级 |
| `CharacterListResponse.CharacterDBs[].PassiveSkillLevel` | 玩家进度 | — | — | 技能等级 |
| `CharacterListResponse.CharacterDBs[].ExtraPassiveSkillLevel` | 玩家进度 | — | — | 技能等级 |
| `CharacterListResponse.CharacterDBs[].LeaderSkillLevel` | 玩家进度 | — | — | 技能等级 |
| `CharacterListResponse.CharacterDBs[].IsNew` | 玩家进度 | — | — | 新获得标记 |
| `CharacterListResponse.CharacterDBs[].IsLocked` | 玩家进度 | — | — | 锁定标记 |
| `CharacterListResponse.CharacterDBs[].IsFavorite` | 玩家进度 | — | — | 收藏标记 |
| `CharacterListResponse.CharacterDBs[].EquipmentServerIds[]` | 玩家进度 | — | — | 装备实例 id；全库 0 命中 |
| `CharacterListResponse.CharacterDBs[].PotentialStats.*` | 玩家进度 | — | — | 能力解放等级 |
| `CharacterListResponse.WeaponDBs[]` | 玩家进度 | — | — | 本响应为空 |
| `CharacterListResponse.TSSCharacterDBs[]` | 玩家进度 | — | — | 本响应为空 |
| `EquipmentItemListResponse.EquipmentDBs[].UniqueId` | 静态表 | `EquipmentDBSchema.Id` | **verified** | 54 个不同值(1000..109005) 全部命中 EquipmentDBSchema.Id(191 行)；EquipmentStatDBSchema 也有同一列（同键的另一张表） |
| `EquipmentItemListResponse.EquipmentDBs[].Type` | 枚举(非表) | — | — | ParcelType=3(装备) |
| `EquipmentItemListResponse.EquipmentDBs[].ServerId` | 玩家进度 | — | — | 装备实例 id |
| `EquipmentItemListResponse.EquipmentDBs[].StackCount` | 玩家进度 | — | — | 数量 |
| `EquipmentItemListResponse.EquipmentDBs[].IsNew` | 玩家进度 | — | — | 标记 |
| `EquipmentItemListResponse.EquipmentDBs[].IsLocked` | 玩家进度 | — | — | 标记 |
| `ScenarioListResponse.ScenarioHistoryDBs[].ScenarioUniqueId` | 静态表 | `ScenarioModeDBSchema.Id` | **verified** | 191/191 命中 ScenarioModeDBSchema.Id(581 行)，191 个全部唯一；ScenarioScriptDBSchema.GroupId 也 191/191，但那是 1:N 的脚本正文(3153 个 group)，定义表应取 ScenarioMode |
| `ScenarioListResponse.ScenarioHistoryDBs[].ClearDateTime` | 玩家进度 | — | — | 时间戳 |
| `ScenarioListResponse.ScenarioGroupHistoryDBs[].ScenarioGroupUniqueId` | 静态表 | `ScenarioScriptDBSchema.GroupId` | **verified** | 21/21 命中 ScenarioScriptDBSchema.GroupId（3153 个不同 group）；同样 21 个值在 ScenarioModeDBSchema.ModeId 上 **0/21** —— 所以这个字段是「剧本组」不是「剧情模式」，两者是不同表（实测脚本 probe_scenario_group.py） |
| `ScenarioListResponse.ScenarioGroupHistoryDBs[].ScenarioType` | 枚举(非表) | — | — | 枚举 |
| `ScenarioListResponse.ScenarioGroupHistoryDBs[].EventContentId` | 回显/常量 | — | — | 活动 id，0=主线 |
| `ScenarioListResponse.ScenarioGroupHistoryDBs[].ClearDateTime` | 玩家进度 | — | — | 时间戳 |
| `ScenarioListResponse.ScenarioGroupHistoryDBs[].IsReturn` | 玩家进度 | — | — | 标记 |
| `ScenarioListResponse.ScenarioGroupHistoryDBs[].IsPermanent` | 玩家进度 | — | — | 标记 |
| `MomoTalkOutLineResponse.MomoTalkOutLineDBs[].CharacterId` | 静态表 | `CharacterDBSchema.Id` | **weak** | 值 13010 命中 CharacterDBSchema.Id（单值） |
| `MomoTalkOutLineResponse.MomoTalkOutLineDBs[].CharacterDBId` | 玩家进度 | — | — | 角色实例 id（3002866，等于 CharacterDBs[].ServerId） |
| `MomoTalkOutLineResponse.MomoTalkOutLineDBs[].LatestMessageGroupId` | 静态表 | `AcademyMessangerDBSchema.MessageGroupId` | **weak** | 130100140 命中 AcademyMessangerDBSchema.MessageGroupId(15050 行，10389 个不同 group)；行级佐证：命中的那几行 CharacterId 全等于元素里的 CharacterId(13010)；单值无法统计验证 |
| `MomoTalkOutLineResponse.FavorScheduleRecords` | 静态表 | `AcademyFavorScheduleDBSchema.Id` | **weak** | 值 130101 命中 AcademyFavorScheduleDBSchema.Id(1053 行)，该行 ScheduleGroupId=13010（=元素里的 CharacterId）；单值无法统计验证 |
| `MomoTalkOutLineResponse.MomoTalkOutLineDBs[].ChosenMessageId` | 玩家进度 | — | — | 已选选项 |
| `MomoTalkOutLineResponse.MomoTalkOutLineDBs[].LastUpdateDate` | 玩家进度 | — | — | 时间戳 |
| `MomoTalkOutLineResponse.FavorScheduleRecords.*` | 玩家进度 | — | — | 好感日程完成记录 |
| `AccountCurrencySyncResponse.AccountCurrencyDB.CurrencyDict` | 静态表 | `CurrencyDBSchema.Id` | **verified** | CurrencyDict 的 29 个 key 恰好等于 CurrencyDBSchema 的 29 行（f0/f2/sql:ID 三个槽位 distinct 都是 29）；value 是玩家持有量 |
| `AccountCurrencySyncResponse.AccountCurrencyDB.AccountLevel` | 玩家进度 | — | — | 账号等级（上限表 AccountLevelDBSchema 90 行） |
| `AccountCurrencySyncResponse.AccountCurrencyDB.AcademyLocationRankSum` | 玩家进度 | — | — | 学院地点等级总和 |
| `AccountCurrencySyncResponse.AccountCurrencyDB.UpdateTimeDict.*` | 玩家进度 | — | — | 时间戳 |
| `StickerListResponse.StickerBookDB.UnusedStickerDBs[].StickerUniqueId` | 静态表 | `StickerPageContentDBSchema.Id` | **verified** | 20 个不同值全部命中 StickerPageContentDBSchema.Id(23 行) |
| `AttachmentEmblemListResponse.EmblemDBs[].UniqueId` | 静态表 | `EmblemDBSchema.Id` | **ambiguous** | 14 个值(1..1011020) 中玩具段 1..5 是全库到处都有的小整数，EmblemDBSchema(1065 行) 含大值 1011020，但没有全覆盖证据，按弱证据处理 |
| `AttachmentEmblemListResponse.EmblemDBs[].Type` | 枚举(非表) | — | — | ParcelType=20(徽章) |
| `EventContentPermanentListResponse.PermanentDBs[].EventContentId` | 静态表 | `EventContentArchiveBannerOffsetDBSchema.sql:EventContentId` | **verified** | 22/22 命中 EventContentArchiveBannerOffsetDBSchema(25 行) 的 EventContentId |
| `EventContentPermanentListResponse.PermanentDBs[].IsStageAllClear` | 玩家进度 | — | — | 玩家进度 |
| `MemoryLobbyListResponse.MemoryLobbyDBs[].MemoryLobbyUniqueId` | 静态表 | `MemoryLobbyDBSchema` | **weak** | 13010 属于 MemoryLobbyDBSchema(258 行) 的 id 段；单值无法统计验证 |
| `MemoryLobbyListResponse.MemoryLobbyDBs[].Type` | 枚举(非表) | — | — | ParcelType=8 |
| `ContentSweepMultiSweepPresetListResponse.MultiSweepPresetDBs[].StageIds[]` | 静态表 | `CampaignStageDBSchema.Id` | **verified** | 10 个关卡 id 全部命中 CampaignStageDBSchema.Id |
| `PickupFirstGetHistoryDBs[].ShopRecruitId` | 静态表 | `ShopRecruitDBSchema.Id` | **weak** | 5004170 命中 ShopRecruitDBSchema.Id（单值） |
| `PickupFirstGetHistoryDBs[].LogDate` | 玩家进度 | — | — | 时间戳 |
| `ShopGachaRecruitListResponse.ShopRecruits[].Id` | 静态表 | `ShopRecruitDBSchema.Id` | **verified** | 529/529 命中 ShopRecruitDBSchema.Id(532 行)；表里多出的 3 条是 Id=1,2,3（老版常驻池占位行） |
| `ShopGachaRecruitListResponse.ShopRecruits[].SalesStartDate` | **库里没有** | — | — | ★ 全库找不到：398 张表 × 29 种编码(ISO 文本/.NET ticks/unix 秒/毫秒/yyyymmddhhmmss, 4B&8B) 全部 0 命中。招募开放时间不在客户端 Excel 里，只能私服自己配 |
| `ShopGachaRecruitListResponse.ShopRecruits[].SalesEndDate` | **库里没有** | — | — | 同上（SalesStartDate 的姊妹字段，同样 0 命中） |
| `ShopGachaRecruitListResponse.ShopRecruits[].UpdateDate` | 回显/常量 | — | — | 恒为 0001-01-01（未设置） |
| `ShopGachaRecruitListResponse.ShopFreeRecruitHistoryDBs[]` | 玩家进度 | — | — | 免费抽记录 |
| `EchelonListResponse.EchelonDBs[].EchelonType` | 枚举(非表) | — | — | 同 5000 |
| `EchelonListResponse.EchelonDBs[].LeaderServerId` | 玩家进度 | — | — | 同 5000 |
| `EchelonListResponse.EchelonDBs[].MainSlotServerIds[]` | 玩家进度 | — | — | 同 5000 |
| `EchelonListResponse.EchelonDBs[].SupportSlotServerIds[]` | 玩家进度 | — | — | 同 5000 |
| `CampaignListResponse.StageHistoryDBs[].StageUniqueId` | 静态表 | `CampaignStageDBSchema.Id` | **verified** | 同 6000 |
| `CampaignListResponse.CurrentScenarioId` | 静态表 | `ScenarioModeDBSchema.Id` | **weak** | 同 6000 |
| `CafeGetInfoResponse.CafeDBs[].CafeId` | 静态表 | `CafeInfoDBSchema.CafeId` | **verified** | CafeId=1,2 与表 2 行完全一致 |
| `CafeGetInfoResponse.CafeDBs[].FurnitureDBs[].UniqueId` | 静态表 | `FurnitureDBSchema.Id` | **verified** | 25 条家具 id 全部命中 FurnitureDBSchema.Id |
| `CharacterGearListResponse.GearDBs[]` | **库里没有** | — | — | ★ 无法证实：官方 GearDBs=[] 元素数为 0，没有任何值可验证。库内 CharacterGearDBSchema(104 行, Id 200000…) 只是候选，等第二个账号样本再定 |
| `BillingPurchaseListByYostarResponse.OrderList[].ShopCashId` | 静态表 | `ShopCashDBSchema.Id` | **ambiguous** | 4/4 命中 ShopCashDBSchema.Id(656 行)；但 ProductDBSchema(605 行) 与它 Id 大面积重合(604/605)，值层面无法二选一，按语义取 ShopCash |
| `AccountLevelRewardIds[]` | 静态表 | `AccountLevelRewardDBSchema.Id` | **weak** | 1/1 命中（单样本） |
| `ClanLoginResponse.AccountClanDB.ClanDBId` | 玩家进度 | — | — | 27353，全库 0 槽位 → 服务器发号 |
| `ClanLoginResponse.AccountClanMemberDB.ClanDBId` | 玩家进度 | — | — | 同上 |
| `EchelonListResponse.EchelonDBs[].AccountServerId` | 玩家进度 | — | — | 账号 id（同 5000.EchelonDBs[].AccountServerId，字段名与语义一一对应） |
| `EchelonListResponse.EchelonDBs[].EchelonNumber` | 玩家进度 | — | — | 第几队（1..3），玩家自己排的（同 5000.EchelonDBs[].EchelonNumber，字段名与语义一一对应） |
| `EchelonListResponse.EchelonDBs[].ExtensionType` | 枚举(非表) | — | — | 0=无扩展；枚举（同 5000.EchelonDBs[].ExtensionType，字段名与语义一一对应） |
| `EchelonListResponse.EchelonDBs[].TSSInteractionServerId` | 玩家进度 | — | — | 战术支援角色实例 id，0=空（同 5000.EchelonDBs[].TSSInteractionServerId，字段名与语义一一对应） |
| `EchelonListResponse.EchelonDBs[].UsingFlag` | 玩家进度 | — | — | 是否使用中（同 5000.EchelonDBs[].UsingFlag，字段名与语义一一对应） |
| `EchelonListResponse.EchelonDBs[].SkillCardMulliganCharacterIds[]` | 玩家进度 | — | — | 洗牌保留用的角色实例 id（同 5000.EchelonDBs[].SkillCardMulliganCharacterIds[]，字段名与语义一一对应） |
| `EchelonListResponse.EchelonDBs[].CombatStyleIndex[]` | 玩家进度 | — | — | 每格战斗风格下标（同 5000.EchelonDBs[].CombatStyleIndex[]，字段名与语义一一对应） |
| `CafeGetInfoResponse.CafeDBs[].CafeDBId` | 玩家进度 | — | — | 账号内咖啡厅实例 id = AccountId*100+n（100153543801）（同 20001.CafeDB.CafeDBId，字段名与语义一一对应） |
| `CafeGetInfoResponse.CafeDBs[].AccountId` | 玩家进度 | — | — | 账号 id（同 20001.CafeDB.AccountId，字段名与语义一一对应） |
| `CafeGetInfoResponse.CafeDBs[].CafeRank` | 玩家进度 | — | — | 玩家等级，上限由 CafeRankDBSchema(CafeId,Rank) 的 10 级 × 2 咖啡厅定义（同 20001.CafeDB.CafeRank，字段名与语义一一对应） |
| `CafeGetInfoResponse.CafeDBs[].LastUpdate` | 玩家进度 | — | — | 时间戳（同 20001.CafeDB.LastUpdate，字段名与语义一一对应） |
| `CafeGetInfoResponse.CafeDBs[].LastSummonDate` | 玩家进度 | — | — | 上次召唤时间（同 20001.CafeDB.LastSummonDate，字段名与语义一一对应） |
| `CafeGetInfoResponse.CafeDBs[].IsNew` | 玩家进度 | — | — | 新内容标记（同 20001.CafeDB.IsNew，字段名与语义一一对应） |
| `CafeGetInfoResponse.CafeDBs[].CafeVisitCharacterDBs.*.UniqueId` | 静态表 | `CharacterDBSchema.Id` | **verified** | 键/值都是角色 id，全部命中 CharacterDBSchema.Id（7223 行）（同 20001.CafeDB.CafeVisitCharacterDBs.*.UniqueId，字段名与语义一一对应） |
| `CafeGetInfoResponse.CafeDBs[].CafeVisitCharacterDBs.*.ServerId` | 玩家进度 | — | — | 角色实例 id（与 CharacterDBs[].ServerId 同一空间）（同 20001.CafeDB.CafeVisitCharacterDBs.*.ServerId，字段名与语义一一对应） |
| `CafeGetInfoResponse.CafeDBs[].CafeVisitCharacterDBs.*.LastInteractTime` | 玩家进度 | — | — | 时间戳（同 20001.CafeDB.CafeVisitCharacterDBs.*.LastInteractTime，字段名与语义一一对应） |
| `CafeGetInfoResponse.CafeDBs[].FurnitureDBs[].ServerId` | 玩家进度 | — | — | 家具实例 id；全库 0 命中（同 20001.CafeDB.FurnitureDBs[].ServerId，字段名与语义一一对应） |
| `CafeGetInfoResponse.CafeDBs[].FurnitureDBs[].Type` | 枚举(非表) | — | — | ParcelType，家具是 6（同 20001.CafeDB.FurnitureDBs[].Type，字段名与语义一一对应） |
| `CafeGetInfoResponse.CafeDBs[].FurnitureDBs[].StackCount` | 玩家进度 | — | — | 持有数量（同 20001.CafeDB.FurnitureDBs[].StackCount，字段名与语义一一对应） |
| `CafeGetInfoResponse.CafeDBs[].FurnitureDBs[].Location` | 玩家进度 | — | — | 摆在哪个咖啡厅（玩家选择）（同 20001.CafeDB.FurnitureDBs[].Location，字段名与语义一一对应） |
| `CafeGetInfoResponse.CafeDBs[].FurnitureDBs[].PositionX` | 玩家进度 | — | — | 摆放坐标（玩家选择）（同 20001.CafeDB.FurnitureDBs[].PositionX，字段名与语义一一对应） |
| `CafeGetInfoResponse.CafeDBs[].FurnitureDBs[].PositionY` | 玩家进度 | — | — | 摆放坐标；值匹配到 GachaCraftNodeDBSchema 只是数值巧合（坐标 3/5/7 这种小整数到处都是）（同 20001.CafeDB.FurnitureDBs[].PositionY，字段名与语义一一对应） |
| `CafeGetInfoResponse.CafeDBs[].FurnitureDBs[].Rotation` | 玩家进度 | — | — | 旋转（玩家选择）（同 20001.CafeDB.FurnitureDBs[].Rotation，字段名与语义一一对应） |
| `CafeGetInfoResponse.CafeDBs[].FurnitureDBs[].ItemDeploySequence` | 玩家进度 | — | — | 摆放顺序号；全库 0 命中（同 20001.CafeDB.FurnitureDBs[].ItemDeploySequence，字段名与语义一一对应） |
| `CafeGetInfoResponse.CafeDBs[].FurnitureDBs[].CafeDBId` | 玩家进度 | — | — | 所属咖啡厅实例（同 20001.CafeDB.FurnitureDBs[].CafeDBId，字段名与语义一一对应） |
| `CafeGetInfoResponse.CafeDBs[].ProductionAppliedTime` | 玩家进度 | — | — | 生产结算时间（同 20001.CafeDB.ProductionAppliedTime，字段名与语义一一对应） |
| `CafeGetInfoResponse.CafeDBs[].ProductionDB.ComfortValue` | 玩家进度 | — | — | 舒适度 = 家具累加，玩家派生值（同 20001.CafeDB.ProductionDB.ComfortValue，字段名与语义一一对应） |
| `CafeGetInfoResponse.CafeDBs[].ProductionDB.AppliedDate` | 玩家进度 | — | — | 时间戳（同 20001.CafeDB.ProductionDB.AppliedDate，字段名与语义一一对应） |
| `CafeGetInfoResponse.CafeDBs[].ProductionDB.CafeDBId` | 玩家进度 | — | — | 实例 id（同 20001.CafeDB.ProductionDB.CafeDBId，字段名与语义一一对应） |
| `CafeGetInfoResponse.CafeDBs[].ProductionDB.ProductionParcelInfos[].Key.Id` | 静态表 | `ItemDBSchema.Id` | **weak** | 产出道具 id（2 个值，太小无法统计验证）（同 20001.CafeDB.ProductionDB.ProductionParcelInfos[].Key.Id，字段名与语义一一对应） |
| `CafeGetInfoResponse.CafeDBs[].ProductionDB.ProductionParcelInfos[].Key.Type` | 枚举(非表) | — | — | ParcelType（同 20001.CafeDB.ProductionDB.ProductionParcelInfos[].Key.Type，字段名与语义一一对应） |
| `CafeGetInfoResponse.CafeDBs[].ProductionDB.ProductionParcelInfos[].Amount` | 玩家进度 | — | — | 产出数量（同 20001.CafeDB.ProductionDB.ProductionParcelInfos[].Amount，字段名与语义一一对应） |
| `CampaignListResponse.StageHistoryDBs[].ChapterUniqueId` | 静态表 | `CampaignChapterDBSchema.Id` | **ambiguous** | 16/16 值(101..116)都落在 CampaignChapterDBSchema.Id(101..129, 29 行)；纯值匹配有并列候选（FurnitureGroupDBSchema 等也含 101..116），但行级一致性可证：同一元素的 floor(StageUniqueId/10000) 对 90/90 条都等于 ChapterUniqueId（同 6000.StageHistoryDBs[].ChapterUniqueId，字段名与语义一一对应） |
| `CampaignListResponse.CampaignChapterClearRewardHistoryDBs[].ChapterUniqueId` | 静态表 | `CampaignChapterDBSchema.Id` | **ambiguous** | 12/12 值落在 CampaignChapterDBSchema.Id；同上属低基数并列（同 6000.CampaignChapterClearRewardHistoryDBs[].ChapterUniqueId，字段名与语义一一对应） |
| `CampaignListResponse.CampaignChapterClearRewardHistoryDBs[].RewardType` | 枚举(非表) | — | — | 奖励类型枚举（同 6000.CampaignChapterClearRewardHistoryDBs[].RewardType，字段名与语义一一对应） |
| `CampaignListResponse.CampaignChapterClearRewardHistoryDBs[].ReceiveDate` | 玩家进度 | — | — | 领取时间（同 6000.CampaignChapterClearRewardHistoryDBs[].ReceiveDate，字段名与语义一一对应） |
| `CampaignListResponse.StageHistoryDBs[].StoryUniqueId` | 玩家进度 | — | — | 剧情片段实例 id（0/小整数）（同 6000.StageHistoryDBs[].StoryUniqueId，字段名与语义一一对应） |
| `CampaignListResponse.StageHistoryDBs[].TacticClearCountWithRankSRecord` | 玩家进度 | — | — | S 评价通关次数（同 6000.StageHistoryDBs[].TacticClearCountWithRankSRecord，字段名与语义一一对应） |
| `CampaignListResponse.StageHistoryDBs[].ClearTurnRecord` | 玩家进度 | — | — | 最少回合数（同 6000.StageHistoryDBs[].ClearTurnRecord，字段名与语义一一对应） |
| `CampaignListResponse.StageHistoryDBs[].Star1Flag` | 玩家进度 | — | — | 星级条件 1 达成（同 6000.StageHistoryDBs[].Star1Flag，字段名与语义一一对应） |
| `CampaignListResponse.StageHistoryDBs[].Star2Flag` | 玩家进度 | — | — | 星级条件 2 达成（同 6000.StageHistoryDBs[].Star2Flag，字段名与语义一一对应） |
| `CampaignListResponse.StageHistoryDBs[].Star3Flag` | 玩家进度 | — | — | 星级条件 3 达成（同 6000.StageHistoryDBs[].Star3Flag，字段名与语义一一对应） |
| `CampaignListResponse.StageHistoryDBs[].TodayPlayCount` | 玩家进度 | — | — | 今日游玩次数（同 6000.StageHistoryDBs[].TodayPlayCount，字段名与语义一一对应） |
| `CampaignListResponse.StageHistoryDBs[].LastPlay` | 玩家进度 | — | — | 最后游玩时间（同 6000.StageHistoryDBs[].LastPlay，字段名与语义一一对应） |
| `CampaignListResponse.StageHistoryDBs[].FirstClearRewardReceive` | 玩家进度 | — | — | 首通奖励已领（同 6000.StageHistoryDBs[].FirstClearRewardReceive，字段名与语义一一对应） |
| `CampaignListResponse.StageHistoryDBs[].StarRewardReceive` | 玩家进度 | — | — | 星级奖励已领（同 6000.StageHistoryDBs[].StarRewardReceive，字段名与语义一一对应） |
| `CampaignListResponse.StageHistoryDBs[].AccountServerId` | 玩家进度 | — | — | 账号 id（同 6000.StageHistoryDBs[].AccountServerId，字段名与语义一一对应） |
| `CafeGetInfoResponse.SessionKey.AccountServerId` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `CafeGetInfoResponse.SessionKey.MxToken` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `CafeGetInfoResponse.FurnitureDBs[].Type` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `CafeGetInfoResponse.FurnitureDBs[].ServerId` | 玩家进度 | — | — | 没有任何表包含这些值，且量级(≥1e7)像账号内自增 id / 时间戳，推断为玩家数据（仅按量级推断） |
| `CafeGetInfoResponse.FurnitureDBs[].UniqueId` | 静态表 | `FurnitureDBSchema.f900` | **ambiguous** | 命中 16/16，但有 1 个满命中槽位，未裁定 |
| `CafeGetInfoResponse.FurnitureDBs[].StackCount` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `CafeGetInfoResponse.FurnitureDBs[].Location` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `CafeGetInfoResponse.FurnitureDBs[].PositionX` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `CafeGetInfoResponse.FurnitureDBs[].PositionY` | 静态表 | `ArenaNPCDBSchema.f900` | **ambiguous** | 命中 4/5，但有 8 个满命中槽位，未裁定 |
| `CafeGetInfoResponse.FurnitureDBs[].ItemDeploySequence` | **库里没有** | — | — | 没有任何表包含这些值 |
| `CafeGetInfoResponse.FurnitureDBs[].CafeDBId` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `CafeGetInfoResponse.FurnitureDBs[].Rotation` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `AccountCurrencySyncResponse.SessionKey.AccountServerId` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `AccountCurrencySyncResponse.SessionKey.MxToken` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `AccountCurrencySyncResponse.AccountCurrencyDB.CurrencyDict.*` | 静态表 | `GachaElementDBSchema.f900` | **ambiguous** | 命中 8/10，但有 0 个满命中槽位，未裁定 |
| `CharacterListResponse.SessionKey.AccountServerId` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `CharacterListResponse.SessionKey.MxToken` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `EquipmentItemListResponse.SessionKey.AccountServerId` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `EquipmentItemListResponse.SessionKey.MxToken` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `EquipmentItemListResponse.EquipmentDBs[].Level` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `EquipmentItemListResponse.EquipmentDBs[].Tier` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `EquipmentItemListResponse.EquipmentDBs[].BoundCharacterServerId` | **库里没有** | — | — | 没有任何表包含这些值 |
| `CharacterGearListResponse.SessionKey.AccountServerId` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `CharacterGearListResponse.SessionKey.MxToken` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `EchelonListResponse.SessionKey.AccountServerId` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `EchelonListResponse.SessionKey.MxToken` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `MemoryLobbyListResponse.SessionKey.AccountServerId` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `MemoryLobbyListResponse.SessionKey.MxToken` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `MemoryLobbyListResponse.MemoryLobbyDBs[].AccountServerId` | 玩家进度 | — | — | 值太少无法统计验证，且全库 0 命中、量级(≥1e7)像账号内自增 id /时间戳，推断为玩家数据（仅按量级推断） |
| `CampaignListResponse.SessionKey.AccountServerId` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `CampaignListResponse.SessionKey.MxToken` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `CampaignListResponse.CampaignChapterClearRewardHistoryDBs[].AccountServerId` | 玩家进度 | — | — | 值太少无法统计验证，且全库 0 命中、量级(≥1e7)像账号内自增 id /时间戳，推断为玩家数据（仅按量级推断） |
| `ArenaLoginResponse.SessionKey.AccountServerId` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `ArenaLoginResponse.SessionKey.MxToken` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `ArenaLoginResponse.ArenaPlayerInfoDB.CurrentSeasonId` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `ArenaLoginResponse.ArenaPlayerInfoDB.PlayerGroupId` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `ArenaLoginResponse.ArenaPlayerInfoDB.CurrentRank` | 玩家进度 | — | — | 值只有 1 个且全库 0 命中，值域太小 —— 属玩家状态/枚举，不是静态表数据 |
| `ArenaLoginResponse.ArenaPlayerInfoDB.SeasonRecord` | 玩家进度 | — | — | 值只有 1 个且全库 0 命中，值域太小 —— 属玩家状态/枚举，不是静态表数据 |
| `ArenaLoginResponse.ArenaPlayerInfoDB.AllTimeRecord` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=1.00），值匹配无法判定 |
| `ArenaLoginResponse.ArenaPlayerInfoDB.CumulativeTimeReward` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `ArenaLoginResponse.ArenaPlayerInfoDB.TimeRewardLastUpdateTime` | 玩家进度 | — | — | 日期/时间戳字符串，ExcelDB 里没有时间序列（玩家或运营侧数据） |
| `ArenaLoginResponse.ArenaPlayerInfoDB.BattleEnterActiveTime` | 玩家进度 | — | — | 日期/时间戳字符串，ExcelDB 里没有时间序列（玩家或运营侧数据） |
| `ArenaLoginResponse.ArenaPlayerInfoDB.DailyRewardActiveTime` | 玩家进度 | — | — | 日期/时间戳字符串，ExcelDB 里没有时间序列（玩家或运营侧数据） |
| `RaidLoginResponse.SessionKey.AccountServerId` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `RaidLoginResponse.SessionKey.MxToken` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `RaidLoginResponse.SeasonType` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `RaidLoginResponse.LastSettledRanking` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `RaidLoginResponse.LastSettledTier` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `CraftInfoListResponse.SessionKey.AccountServerId` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `CraftInfoListResponse.SessionKey.MxToken` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `ClanLoginResponse.SessionKey.AccountServerId` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `ClanLoginResponse.SessionKey.MxToken` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `ClanLoginResponse.AccountClanDB.ClanName` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `ClanLoginResponse.AccountClanDB.ClanChannelName` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `ClanLoginResponse.AccountClanDB.ClanPresidentNickName` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `ClanLoginResponse.AccountClanDB.ClanPresidentRepresentCharacterUniqueId` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `ClanLoginResponse.AccountClanDB.ClanPresidentRepresentCharacterCostumeId` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `ClanLoginResponse.AccountClanDB.ClanNotice` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `ClanLoginResponse.AccountClanDB.ClanMemberCount` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `ClanLoginResponse.AccountClanDB.ClanManagerCount` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `ClanLoginResponse.AccountClanDB.ClanJoinOption` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `ClanLoginResponse.AccountClanMemberDB.AccountId` | 玩家进度 | — | — | 值太少无法统计验证，且全库 0 命中、量级(≥1e7)像账号内自增 id /时间戳，推断为玩家数据（仅按量级推断） |
| `ClanLoginResponse.AccountClanMemberDB.AccountLevel` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `ClanLoginResponse.AccountClanMemberDB.AccountNickName` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `ClanLoginResponse.AccountClanMemberDB.RepresentCharacterUniqueId` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `ClanLoginResponse.AccountClanMemberDB.RepresentCharacterCostumeId` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `ClanLoginResponse.AccountClanMemberDB.AttendanceCount` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `ClanLoginResponse.AccountClanMemberDB.ClanSocialGrade` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `ClanLoginResponse.AccountClanMemberDB.JoinDate` | 玩家进度 | — | — | 日期/时间戳字符串，ExcelDB 里没有时间序列（玩家或运营侧数据） |
| `ClanLoginResponse.AccountClanMemberDB.SocialGradeUpdateTime` | 玩家进度 | — | — | 日期/时间戳字符串，ExcelDB 里没有时间序列（玩家或运营侧数据） |
| `ClanLoginResponse.AccountClanMemberDB.LastLoginDate` | 玩家进度 | — | — | 日期/时间戳字符串，ExcelDB 里没有时间序列（玩家或运营侧数据） |
| `ClanLoginResponse.AccountClanMemberDB.GameLoginDate` | 玩家进度 | — | — | 日期/时间戳字符串，ExcelDB 里没有时间序列（玩家或运营侧数据） |
| `ClanLoginResponse.AccountClanMemberDB.AppliedDate` | 玩家进度 | — | — | 日期/时间戳字符串，ExcelDB 里没有时间序列（玩家或运营侧数据） |
| `ClanLoginResponse.AccountClanMemberDB.AttachmentDB.AccountId` | 玩家进度 | — | — | 值太少无法统计验证，且全库 0 命中、量级(≥1e7)像账号内自增 id /时间戳，推断为玩家数据（仅按量级推断） |
| `ClanLoginResponse.AccountClanMemberDB.AttachmentDB.EmblemUniqueId` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `MomoTalkOutLineResponse.SessionKey.AccountServerId` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `MomoTalkOutLineResponse.SessionKey.MxToken` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `MomoTalkOutLineResponse.FavorScheduleRecords.*[]` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=1.00），值匹配无法判定 |
| `ScenarioListResponse.SessionKey.AccountServerId` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `ScenarioListResponse.SessionKey.MxToken` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `ScenarioListResponse.ScenarioHistoryDBs[].AccountServerId` | 玩家进度 | — | — | 值太少无法统计验证，且全库 0 命中、量级(≥1e7)像账号内自增 id /时间戳，推断为玩家数据（仅按量级推断） |
| `ScenarioListResponse.ScenarioGroupHistoryDBs[].AccountServerId` | 玩家进度 | — | — | 值太少无法统计验证，且全库 0 命中、量级(≥1e7)像账号内自增 id /时间戳，推断为玩家数据（仅按量级推断） |
| `ShopGachaRecruitListResponse.SessionKey.AccountServerId` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `ShopGachaRecruitListResponse.SessionKey.MxToken` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `TimeAttackDungeonLoginResponse.SessionKey.AccountServerId` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `TimeAttackDungeonLoginResponse.SessionKey.MxToken` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `BillingPurchaseListByYostarResponse.SessionKey.AccountServerId` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `BillingPurchaseListByYostarResponse.SessionKey.MxToken` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `BillingPurchaseListByYostarResponse.CountList[].ShopCashId` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=1.00），值匹配无法判定 |
| `BillingPurchaseListByYostarResponse.CountList[].PurchaseCount` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `BillingPurchaseListByYostarResponse.CountList[].ResetDate` | 玩家进度 | — | — | 日期/时间戳字符串，ExcelDB 里没有时间序列（玩家或运营侧数据） |
| `BillingPurchaseListByYostarResponse.CountList[].PurchaseDate` | 玩家进度 | — | — | 日期/时间戳字符串，ExcelDB 里没有时间序列（玩家或运营侧数据） |
| `EventContentPermanentListResponse.SessionKey.AccountServerId` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `EventContentPermanentListResponse.SessionKey.MxToken` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `AttachmentEmblemListResponse.SessionKey.AccountServerId` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `AttachmentEmblemListResponse.SessionKey.MxToken` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `AttachmentEmblemListResponse.EmblemDBs[].ReceiveDate` | 玩家进度 | — | — | 日期/时间戳字符串，ExcelDB 里没有时间序列（玩家或运营侧数据） |
| `AttachmentGetResponse.SessionKey.AccountServerId` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `AttachmentGetResponse.SessionKey.MxToken` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `AttachmentGetResponse.AccountAttachmentDB.AccountId` | 玩家进度 | — | — | 值太少无法统计验证，且全库 0 命中、量级(≥1e7)像账号内自增 id /时间戳，推断为玩家数据（仅按量级推断） |
| `AttachmentGetResponse.AccountAttachmentDB.EmblemUniqueId` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `ContentSweepMultiSweepPresetListResponse.SessionKey.AccountServerId` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `ContentSweepMultiSweepPresetListResponse.SessionKey.MxToken` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `ContentSweepMultiSweepPresetListResponse.MultiSweepPresetDBs[].PresetId` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `ContentSweepMultiSweepPresetListResponse.MultiSweepPresetDBs[].PresetName` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `EliminateRaidLoginResponse.SessionKey.AccountServerId` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `EliminateRaidLoginResponse.SessionKey.MxToken` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `EliminateRaidLoginResponse.SeasonType` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `EliminateRaidLoginResponse.LastSettledRanking` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `EliminateRaidLoginResponse.LastSettledTier` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `StickerListResponse.SessionKey.AccountServerId` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `StickerListResponse.SessionKey.MxToken` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `StickerListResponse.StickerBookDB.AccountId` | 玩家进度 | — | — | 值太少无法统计验证，且全库 0 命中、量级(≥1e7)像账号内自增 id /时间戳，推断为玩家数据（仅按量级推断） |
| `FriendCount` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `FriendCode` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `MultiFloorRaidSyncResponse.SessionKey.AccountServerId` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `MultiFloorRaidSyncResponse.SessionKey.MxToken` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `MultiFloorRaidLoginResponse.SessionKey.AccountServerId` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `MultiFloorRaidLoginResponse.SessionKey.MxToken` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `MultiFloorRaidLoginResponse.LastClearedDifficulty` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |

### 8000.Mission_List —— `Mission_List`（mission id 分散在 4 张表，路由键是 Category）

官方 `ProgressDBs[]` 有 **1240 个不同的 `MissionUniqueId`**。任何**单张** mission 表的覆盖率都只有 38%~56%，所以自动匹配一开始把它判成 ambiguous。逐个反查后 **1240/1240 全部有归属，0 个悬空**：

| 归属表 | 值个数 | 行数 |
|---|---|---|
| `GuideMissionDBSchema` | 690 | 923 |
| `MissionDBSchema` | 475 | 3444 |
| `EventContentMissionDBSchema` | 56 | 2384 |
| `MiniGameMissionDBSchema` | 18 | 402 |
| 撞号（Mission + Guide 两张表都有同一 id） | 1 | — |
| **合计** | **1240** | — |

**真正的路由键不是 id 段，而是 `ProgressDBs[].Category`**（用行级一致性证明，与表名无关）：

| Category | 应查表 | 证据 |
|---|---|---|
| 0 / 1 / 2 / 3 / 9 / 10 | `MissionDBSchema` | 475+1 个 id 全在；`MissionDBSchema.f1 == Category` 404/476 |
| 4 | `GuideMissionDBSchema` | 690/690；`f2 == Category` **690/691** |
| 7 | `MiniGameMissionDBSchema` | 18/18；`f4 == Category` **18/18** |
| 8 | `EventContentMissionDBSchema` | 56/56；`f4 == Category` **56/56** |

私服查任务定义的正确写法：`Category=4 → GuideMission`、`7 → MiniGame`、`8 → EventContentMission`、其余 → `MissionDBSchema`；撞号时以 Category 为准。复核脚本：`work/ba/proto/probe_mission_category.py`。

`MissionHistoryUniqueIds[]` 与 `ClearedOriginalMissionIds[]` 各 372 个值且**完全同序相等**（玩家通关历史；id 本身是静态的，整条列表是玩家数据）。

**`ProgressDBs[].Progress` 这个字段在协议里根本不存在** —— 8000/8002/8006 三份响应递归扫描 0 次出现，只有 `ProgressDBs` 与 `ProgressParameters`。写服务端时别照抄。

**8006 是单表**：`MissionProgressDBs[].MissionUniqueId` **733/733** → `GuideMissionDBSchema.Id`（Category 全为 4，行内 `f2 == Category` 733/733）；`GuideMissionSeasonDBs[].SeasonId` **17/17** → `GuideMissionSeasonDBSchema.Id`。

| 协议字段 | 判定 | 来源 | 置信度 | 证据 |
|---|---|---|---|---|
| `ProgressDBs[].MissionUniqueId` | 静态表 | `MissionDBSchema∪GuideMissionDBSchema∪EventContentMissionDBSchema∪MiniGameMissionDBSchema.Id` | verified | 1240 个不同值逐个反查，**0 个未命中**：GuideMissionDBSchema 690 / MissionDBSchema 475 / EventContentMissionDBSchema 56 / MiniGameMissionDBSchema 18 / 撞号(Mission+Guide 同时有) 1。任何单表覆盖率都只有 38%~56%，所以必须分表查 |
| `ProgressDBs[].Category` | 静态表 | — | verified | ★ 这才是 mission 表的**路由键**（行级一致性证明，不靠表名）：Category=4 → GuideMission(690/690)，7 → MiniGame(18/18)，8 → EventContentMission(56/56)，0/1/2/3/9/10 → Mission(475+1)；且 GuideMissionDBSchema.f2==Category 690/691、EventContentMission.f4==Category 56/56、MiniGame.f4==Category 18/18、Mission.f1==Category 404/476。核对脚本 work/ba/proto/probe_mission_category.py |
| `MissionHistoryUniqueIds[]` | 静态表 | `同上 4 张 mission 表的并集.Id` | verified | 372 个值，与 ClearedOriginalMissionIds **完全同序相等**（玩家通关历史列表，id 本身静态） |
| `ClearedOriginalMissionIds[]` | 静态表 | `同上 4 张 mission 表的并集.Id` | verified | 372 个值，与 MissionHistoryUniqueIds 同序相等 |
| `ProgressDBs[].Progress` | nonexistent | — | verified | ★ 该字段在 8000/8002/8006 三份响应里递归扫描 0 次出现 —— 协议里没有 Progress，只有 ProgressDBs / ProgressParameters（写服务端时别照抄） |
| `ProgressDBs[].ProgressParameters.*` | 玩家进度 | — | — | value 是玩家计数；key 部分静态（Category=0 段的 key 72/72 == MissionDBSchema.f19），但 Category 1/3/4/7 段的 key 无法 1:1 归到某张表，未强行归因 |
| `ProgressDBs[].StartDate` | 玩家进度 | — | — | 1314 个值只有 23 个不同，日期字符串在库里 0 命中 → 玩家进度 |
| `ProgressDBs[].ReceiveDate` | 玩家进度 | — | — | 奖励领取时间 |
| `ProgressDBs[].AccountServerId` | 玩家进度 | — | — | 账号 id |
| `ProgressDBs[].IsComplete` | 玩家进度 | — | — | 完成标记 |
| `DailySuddenMissionInfo.Id` | 未判定 | — | — | 值太少或全是常见小整数（rare_frac=1.00），值匹配无法判定 |

#### 1017 按子回包拆分

| 子回包 | 字段数 | 静态表字段 | verified | ambiguous | 玩家进度 | 未判定 |
|---|---|---|---|---|---|---|
| `CafeGetInfoResponse` | 39 | 6 | 3 | 2 | 22 | 9 |
| `ClanLoginResponse` | 27 | 0 | 0 | 0 | 9 | 18 |
| `CharacterListResponse` | 22 | 1 | 1 | 0 | 18 | 2 |
| `CampaignListResponse` | 20 | 4 | 1 | 2 | 13 | 2 |
| `EchelonListResponse` | 13 | 0 | 0 | 0 | 9 | 2 |
| `ScenarioListResponse` | 12 | 2 | 2 | 0 | 6 | 2 |
| `EquipmentItemListResponse` | 11 | 1 | 1 | 0 | 4 | 5 |
| `ArenaLoginResponse` | 11 | 0 | 0 | 0 | 5 | 6 |
| `MomoTalkOutLineResponse` | 10 | 3 | 0 | 0 | 4 | 3 |
| `AccountCurrencySyncResponse` | 7 | 2 | 1 | 1 | 3 | 2 |
| `ShopGachaRecruitListResponse` | 7 | 1 | 1 | 0 | 1 | 4 |
| `BillingPurchaseListByYostarResponse` | 7 | 1 | 0 | 1 | 2 | 4 |
| `AttachmentEmblemListResponse` | 5 | 1 | 0 | 1 | 1 | 2 |
| `MemoryLobbyListResponse` | 5 | 1 | 0 | 0 | 1 | 2 |
| `ContentSweepMultiSweepPresetListResponse` | 5 | 1 | 1 | 0 | 0 | 4 |
| `RaidLoginResponse` | 5 | 0 | 0 | 0 | 0 | 5 |
| `EliminateRaidLoginResponse` | 5 | 0 | 0 | 0 | 0 | 5 |
| `StickerListResponse` | 4 | 1 | 1 | 0 | 1 | 2 |
| `EventContentPermanentListResponse` | 4 | 1 | 1 | 0 | 1 | 2 |
| `AttachmentGetResponse` | 4 | 0 | 0 | 0 | 1 | 3 |
| `CharacterGearListResponse` | 3 | 0 | 0 | 0 | 0 | 3 |
| `MultiFloorRaidLoginResponse` | 3 | 0 | 0 | 0 | 0 | 3 |
| `PickupFirstGetHistoryDBs[]` | 2 | 1 | 0 | 0 | 1 | 0 |
| `CraftInfoListResponse` | 2 | 0 | 0 | 0 | 0 | 2 |
| `TimeAttackDungeonLoginResponse` | 2 | 0 | 0 | 0 | 0 | 2 |
| `MultiFloorRaidSyncResponse` | 2 | 0 | 0 | 0 | 0 | 2 |
| `AccountLevelRewardIds[]` | 1 | 1 | 0 | 0 | 0 | 0 |
| `FriendCount` | 1 | 0 | 0 | 0 | 0 | 1 |
| `FriendCode` | 1 | 0 | 0 | 0 | 0 | 1 |

## 4. 其他协议概览（自动匹配，未人工复核）

| 协议 | API | 字段数 | 静态表 | verified | ambiguous | 玩家 | 枚举/回显 | 库里没有 | 未判定 |
|---|---|---|---|---|---|---|---|---|---|
| 22004 | `arena_enterbattle` | 562 | 49 | 0 | 49 | 62 | 0 | 3 | 448 |
| 20013 | `cafe_receivecurrency` | 56 | 4 | 0 | 4 | 20 | 0 | 1 | 31 |
| 6021 | `campaign_mainstagestrategyskipresult` | 51 | 3 | 0 | 3 | 17 | 0 | 0 | 31 |
| 8002 | `mission_multiplereward` | 46 | 7 | 0 | 7 | 16 | 0 | 0 | 23 |
| 22000 | `arena_enterlobby` | 45 | 7 | 0 | 7 | 6 | 0 | 1 | 31 |
| 1002 | `account_auth` | 43 | 1 | 0 | 1 | 13 | 0 | 0 | 29 |
| 28000 | `clan_lobby` | 40 | 4 | 1 | 3 | 17 | 0 | 0 | 19 |
| 22009 | `arena_dailyreward` | 35 | 1 | 0 | 1 | 12 | 0 | 0 | 22 |
| 22008 | `arena_cumulativetimereward` | 32 | 1 | 0 | 1 | 12 | 0 | 0 | 19 |
| 90004 | `management_data` | 26 | 5 | 1 | 4 | 7 | 0 | 9 | 5 |
| 7000 | `mail_list` | 13 | 0 | 0 | 0 | 4 | 0 | 0 | 9 |
| 5001 | `echelon_save` | 11 | 0 | 0 | 0 | 2 | 0 | 1 | 8 |
| 90009 | `clan_chat_records` | 10 | 3 | 0 | 3 | 1 | 0 | 1 | 5 |
| 8006 | `mission_guidemissionseasonlist` | 9 | 3 | 2 | 1 | 4 | 0 | 0 | 2 |
| 25003 | `event_rewardincrease` | 5 | 0 | 0 | 0 | 2 | 0 | 0 | 3 |
| 35003 | `minigame_missionlist` | 5 | 1 | 0 | 1 | 2 | 0 | 0 | 2 |
| 6020 | `campaign_entermainstagestrategyskip` | 4 | 1 | 0 | 1 | 1 | 0 | 0 | 2 |
| 29002 | `billing_purchaselistbyyostar` | 4 | 0 | 0 | 0 | 2 | 0 | 0 | 2 |
| 3 | `networktime_sync` | 2 | 0 | 0 | 0 | 2 | 0 | 0 | 0 |
| 1005 | `account_gettutorial` | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 0 |
| 7001 | `mail_check` | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| 22016 | `arena_syncechelonsettingtime` | 1 | 0 | 0 | 0 | 1 | 0 | 0 | 0 |
| 30041 | `eventcontent_permanentlist` | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0 |

### 4.1 非重点协议里 **verified** 的映射（可直接用）

| 协议字段 | 来源 | 证据 |
|---|---|---|
| `28000.ClanMemberDBs[].AttachmentDB.EmblemUniqueId` | `EmblemDBSchema.f900` | 官方值 20 个去重，命中 20/20，覆盖率 1.00（自动匹配，未人工复核） |
| `30041.PermanentDBs[].EventContentId` | `EventContentArchiveBannerOffsetDBSchema.f900` | 官方值 22 个去重，命中 22/22，覆盖率 1.00（自动匹配，未人工复核） |
| `90004.Data.GachaProbabilityDisplay[].LinkedLobbyBannerId` | `LocalizeGachaShopDBSchema.f900` | 官方值 12 个去重，命中 12/12，覆盖率 1.00（自动匹配，未人工复核） |

> 说明：`22004 Arena_EnterBattle`（562 字段）等战斗回包字段数巨大但几乎全是战斗过程状态，自动匹配给的 ambiguous 候选多半是数值巧合，**不要直接用**。

## 5. ★ 找不到来源的字段（决定还要不要做别的事）

分三类，性质完全不同：

### 5.1 A 类：ExcelDB 里**确实没有**（必须私服自己造配置）— 21 条

| 协议字段 | 说明 |
|---|---|
| `1017.ShopGachaRecruitListResponse.ShopRecruits[].SalesStartDate` | ★ 全库找不到：398 张表 × 29 种编码(ISO 文本/.NET ticks/unix 秒/毫秒/yyyymmddhhmmss, 4B&8B) 全部 0 命中。招募开放时间不在客户端 Excel 里，只能私服自己配 |
| `1017.ShopGachaRecruitListResponse.ShopRecruits[].SalesEndDate` | 同上（SalesStartDate 的姊妹字段，同样 0 命中） |
| `1017.CharacterGearListResponse.GearDBs[]` | ★ 无法证实：官方 GearDBs=[] 元素数为 0，没有任何值可验证。库内 CharacterGearDBSchema(104 行, Id 200000…) 只是候选，等第二个账号样本再定 |
| `1017.CafeGetInfoResponse.FurnitureDBs[].ItemDeploySequence` | 没有任何表包含这些值 |
| `1017.EquipmentItemListResponse.EquipmentDBs[].BoundCharacterServerId` | 没有任何表包含这些值 |
| `5001.EchelonDB.MainSlotServerIds[]` | 没有任何表包含这些值 |
| `20013.CafeDBs[].FurnitureDBs[].ItemDeploySequence` | 没有任何表包含这些值 |
| `22000.OpponentUserDBs[].NickName` | 没有任何表包含这些值 |
| `22004.ArenaBattleDB.AttackingUserDB.TeamSettingDB.MainCharacters[].ServerId` | 4 个不同值全部在全库 0 命中 —— 属于服务器侧/运营侧数据，ExcelDB 里没有 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Heroes[].ServerId` | 4 个不同值全部在全库 0 命中 —— 属于服务器侧/运营侧数据，ExcelDB 里没有 |
| `22004.BattleSetting.LeftTeam.Starters[].ServerId` | 4 个不同值全部在全库 0 命中 —— 属于服务器侧/运营侧数据，ExcelDB 里没有 |
| `90004.Data.Notices[].Url` | 没有任何表包含这些值 |
| `90004.Data.Notices[].Title` | 没有任何表包含这些值 |
| `90004.Data.Events[].NoticeId` | 没有任何表包含这些值 |
| `90004.Data.Events[].Url` | 没有任何表包含这些值 |
| `90004.Data.Events[].Title` | 没有任何表包含这些值 |
| `90004.Data.Banners[].BannerId` | 没有任何表包含这些值 |
| `90004.Data.Banners[].CdnUrl` | 没有任何表包含这些值 |
| `90004.Data.Banners[].BannerDisplayType` | 没有任何表包含这些值 |
| `90004.Data.GachaProbabilityDisplay[].Url` | 没有任何表包含这些值 |
| `90009.ChatRecords[].ChatId` | 没有任何表包含这些值 |

**A 类里最要命的是招募时间**：

官方 `1017.ShopGachaRecruitListResponse.ShopRecruits[]` 有 529 条，每条带 `SalesStartDate/SalesEndDate`（真实期，如 `2023-08-03T05:00:00`）。`ShopRecruitDBSchema` 里能查到 529/529 个 `Id`，但**日期一个都找不到**：

- 398 张表 × 29 种编码（ISO 文本 / .NET ticks / Unix 秒 / Unix 毫秒 / yyyyMMddHHmmss，各 4 字节与 8 字节小端）全库逐字节扫描 → **0 命中**（`work/ba/proto/scan_dates.py`）。
- 结论：招募排期是**服务器侧/运营侧数据**，客户端 Excel 不含。私服必须自己在 `ShopRecruitDBSchema.Id` 之外补一张「招募排期表」（Id → 开始/结束时间）。

### 5.2 B 类：官方值太小，**纯值匹配证明不了**（不代表没来源）— 787 条

这些字段的官方样本只有 1~4 个值、或全是 1..50 这种「几百张表里都有」的小整数。例如 `EchelonType`（1,2,3,4,6,11）、`ItemDBs[].Type`（恒 4）、`AcademyLocationDBs[].Rank`（1~2）。对这类字段我**不给来源**，宁缺勿滥 —— 想看候选可以跑 `xls_match.py explain <协议> "<字段>"`。

<details><summary>B 类全量列表（点开）</summary>

| 协议字段 | 为什么没结论 |
|---|---|
| `1002.CurrentVersion` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1002.MinimumVersion` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1002.TTSCdnUri` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1002.AccountDB.Nickname` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1002.AccountDB.CallName` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1002.AccountDB.State` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1002.AccountDB.Level` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1002.AccountDB.Exp` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1002.AccountDB.Comment` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1002.AccountDB.LobbyMode` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1002.AccountDB.MemoryLobbyUniqueId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1002.AccountDB.PublisherAccountId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1002.AccountDB.RetentionDays` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1002.AccountDB.VIPLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1002.AccountDB.UnReadMailCount` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1002.AccountDB.Location` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1002.AttendanceHistoryDBs[].ServerId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1002.AttendanceHistoryDBs[].AttendanceBookUniqueId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1002.EncryptedUID` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1002.FunctionClose.Arena` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1002.FunctionClose.CloseAutoBan` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1002.FunctionClose.CloseAutoClearRaidRank` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1002.FunctionClose.OpenGift` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1002.FunctionClose.ProductPriceCheck` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1002.FunctionClose.Raid` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1002.FunctionClose.ShowCharacterCN` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1002.FunctionClose.ShowCharacterChange` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1002.OptionDB.CafeAllowCopy` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1002.OptionDB.MainScenarioForceEnterSeriesId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.CafeGetInfoResponse.SessionKey.AccountServerId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.CafeGetInfoResponse.SessionKey.MxToken` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.CafeGetInfoResponse.FurnitureDBs[].Type` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.CafeGetInfoResponse.FurnitureDBs[].StackCount` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.CafeGetInfoResponse.FurnitureDBs[].Location` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.CafeGetInfoResponse.FurnitureDBs[].PositionX` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.CafeGetInfoResponse.FurnitureDBs[].CafeDBId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.CafeGetInfoResponse.FurnitureDBs[].Rotation` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.AccountCurrencySyncResponse.SessionKey.AccountServerId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.AccountCurrencySyncResponse.SessionKey.MxToken` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.CharacterListResponse.SessionKey.AccountServerId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.CharacterListResponse.SessionKey.MxToken` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.EquipmentItemListResponse.SessionKey.AccountServerId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.EquipmentItemListResponse.SessionKey.MxToken` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.EquipmentItemListResponse.EquipmentDBs[].Level` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.EquipmentItemListResponse.EquipmentDBs[].Tier` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.CharacterGearListResponse.SessionKey.AccountServerId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.CharacterGearListResponse.SessionKey.MxToken` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.EchelonListResponse.SessionKey.AccountServerId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.EchelonListResponse.SessionKey.MxToken` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.MemoryLobbyListResponse.SessionKey.AccountServerId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.MemoryLobbyListResponse.SessionKey.MxToken` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.CampaignListResponse.SessionKey.AccountServerId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.CampaignListResponse.SessionKey.MxToken` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.ArenaLoginResponse.SessionKey.AccountServerId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.ArenaLoginResponse.SessionKey.MxToken` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.ArenaLoginResponse.ArenaPlayerInfoDB.CurrentSeasonId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.ArenaLoginResponse.ArenaPlayerInfoDB.PlayerGroupId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.ArenaLoginResponse.ArenaPlayerInfoDB.AllTimeRecord` | 值太少或全是常见小整数（rare_frac=1.00），值匹配无法判定 |
| `1017.ArenaLoginResponse.ArenaPlayerInfoDB.CumulativeTimeReward` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.RaidLoginResponse.SessionKey.AccountServerId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.RaidLoginResponse.SessionKey.MxToken` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.RaidLoginResponse.SeasonType` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.RaidLoginResponse.LastSettledRanking` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.RaidLoginResponse.LastSettledTier` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.CraftInfoListResponse.SessionKey.AccountServerId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.CraftInfoListResponse.SessionKey.MxToken` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.ClanLoginResponse.SessionKey.AccountServerId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.ClanLoginResponse.SessionKey.MxToken` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.ClanLoginResponse.AccountClanDB.ClanName` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.ClanLoginResponse.AccountClanDB.ClanChannelName` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.ClanLoginResponse.AccountClanDB.ClanPresidentNickName` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.ClanLoginResponse.AccountClanDB.ClanPresidentRepresentCharacterUniqueId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.ClanLoginResponse.AccountClanDB.ClanPresidentRepresentCharacterCostumeId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.ClanLoginResponse.AccountClanDB.ClanNotice` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.ClanLoginResponse.AccountClanDB.ClanMemberCount` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.ClanLoginResponse.AccountClanDB.ClanManagerCount` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.ClanLoginResponse.AccountClanDB.ClanJoinOption` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.ClanLoginResponse.AccountClanMemberDB.AccountLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.ClanLoginResponse.AccountClanMemberDB.AccountNickName` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.ClanLoginResponse.AccountClanMemberDB.RepresentCharacterUniqueId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.ClanLoginResponse.AccountClanMemberDB.RepresentCharacterCostumeId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.ClanLoginResponse.AccountClanMemberDB.AttendanceCount` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.ClanLoginResponse.AccountClanMemberDB.ClanSocialGrade` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.ClanLoginResponse.AccountClanMemberDB.AttachmentDB.EmblemUniqueId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.MomoTalkOutLineResponse.SessionKey.AccountServerId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.MomoTalkOutLineResponse.SessionKey.MxToken` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.MomoTalkOutLineResponse.FavorScheduleRecords.*[]` | 值太少或全是常见小整数（rare_frac=1.00），值匹配无法判定 |
| `1017.ScenarioListResponse.SessionKey.AccountServerId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.ScenarioListResponse.SessionKey.MxToken` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.ShopGachaRecruitListResponse.SessionKey.AccountServerId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.ShopGachaRecruitListResponse.SessionKey.MxToken` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.TimeAttackDungeonLoginResponse.SessionKey.AccountServerId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.TimeAttackDungeonLoginResponse.SessionKey.MxToken` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.BillingPurchaseListByYostarResponse.SessionKey.AccountServerId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.BillingPurchaseListByYostarResponse.SessionKey.MxToken` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.BillingPurchaseListByYostarResponse.CountList[].ShopCashId` | 值太少或全是常见小整数（rare_frac=1.00），值匹配无法判定 |
| `1017.BillingPurchaseListByYostarResponse.CountList[].PurchaseCount` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.EventContentPermanentListResponse.SessionKey.AccountServerId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.EventContentPermanentListResponse.SessionKey.MxToken` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.AttachmentEmblemListResponse.SessionKey.AccountServerId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.AttachmentEmblemListResponse.SessionKey.MxToken` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.AttachmentGetResponse.SessionKey.AccountServerId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.AttachmentGetResponse.SessionKey.MxToken` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.AttachmentGetResponse.AccountAttachmentDB.EmblemUniqueId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.ContentSweepMultiSweepPresetListResponse.SessionKey.AccountServerId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.ContentSweepMultiSweepPresetListResponse.SessionKey.MxToken` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.ContentSweepMultiSweepPresetListResponse.MultiSweepPresetDBs[].PresetId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.ContentSweepMultiSweepPresetListResponse.MultiSweepPresetDBs[].PresetName` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.EliminateRaidLoginResponse.SessionKey.AccountServerId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.EliminateRaidLoginResponse.SessionKey.MxToken` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.EliminateRaidLoginResponse.SeasonType` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.EliminateRaidLoginResponse.LastSettledRanking` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.EliminateRaidLoginResponse.LastSettledTier` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.StickerListResponse.SessionKey.AccountServerId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.StickerListResponse.SessionKey.MxToken` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.FriendCount` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.FriendCode` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.MultiFloorRaidSyncResponse.SessionKey.AccountServerId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.MultiFloorRaidSyncResponse.SessionKey.MxToken` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.MultiFloorRaidLoginResponse.SessionKey.AccountServerId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.MultiFloorRaidLoginResponse.SessionKey.MxToken` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `1017.MultiFloorRaidLoginResponse.LastClearedDifficulty` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `5001.EchelonDB.EchelonType` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `5001.EchelonDB.EchelonNumber` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `5001.EchelonDB.ExtensionType` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `5001.EchelonDB.SupportSlotServerIds[]` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `5001.EchelonDB.TSSInteractionServerId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `5001.EchelonDB.UsingFlag` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `5001.EchelonDB.SkillCardMulliganCharacterIds[]` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `5001.EchelonDB.CombatStyleIndex[]` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `6020.ParcelResultDB.AccountCurrencyDB.AccountLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `6020.ParcelResultDB.AccountCurrencyDB.AcademyLocationRankSum` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `6021.MissionProgressDBs[].Category` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `6021.TacticRank` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `6021.CampaignStageHistoryDB.StoryUniqueId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `6021.CampaignStageHistoryDB.ChapterUniqueId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `6021.CampaignStageHistoryDB.StageUniqueId` | 值太少或全是常见小整数（rare_frac=1.00），值匹配无法判定 |
| `6021.CampaignStageHistoryDB.ClearTurnRecord` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `6021.CampaignStageHistoryDB.TodayPlayCount` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `6021.ParcelResultDB.AccountDB.Nickname` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `6021.ParcelResultDB.AccountDB.CallName` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `6021.ParcelResultDB.AccountDB.DevId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `6021.ParcelResultDB.AccountDB.State` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `6021.ParcelResultDB.AccountDB.Level` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `6021.ParcelResultDB.AccountDB.Exp` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `6021.ParcelResultDB.AccountDB.Comment` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `6021.ParcelResultDB.AccountDB.LobbyMode` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `6021.ParcelResultDB.AccountDB.MemoryLobbyUniqueId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `6021.ParcelResultDB.AccountDB.PublisherAccountId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `6021.ParcelResultDB.AccountDB.RetentionDays` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `6021.ParcelResultDB.AccountDB.VIPLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `6021.ParcelResultDB.AccountDB.UnReadMailCount` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `6021.ParcelResultDB.AccountDB.Location` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `6021.ParcelResultDB.AccountCurrencyDB.AccountLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `6021.ParcelResultDB.AccountCurrencyDB.AcademyLocationRankSum` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `6021.ParcelResultDB.ItemDBs.*.Type` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `6021.ParcelResultDB.ItemDBs.*.UniqueId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `6021.ParcelResultDB.ItemDBs.*.StackCount` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `6021.ParcelResultDB.DisplaySequence[].Key.Type` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `6021.ParcelResultDB.DisplaySequence[].Key.Id` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `6021.ParcelResultDB.DisplaySequence[].Amount` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `6021.ParcelResultDB.BaseAccountExp` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `6021.ParcelResultDB.AdditionalAccountExp` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `7000.MailDBs[].AccountServerId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `7000.MailDBs[].Type` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `7000.MailDBs[].UniqueId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `7000.MailDBs[].Sender` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `7000.MailDBs[].Comment` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `7000.MailDBs[].ParcelInfos[].Key.Type` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `7000.MailDBs[].ParcelInfos[].Key.Id` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `7000.MailDBs[].ParcelInfos[].Amount` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `7000.Count` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `7001.Count` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `8000.DailySuddenMissionInfo.Id` | 值太少或全是常见小整数（rare_frac=1.00），值匹配无法判定 |
| `8002.MissionProgressDBs[].Category` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `8002.MissionProgressDBs[].ProgressParameters.*` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `8002.ParcelResultDB.AccountDB.Nickname` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `8002.ParcelResultDB.AccountDB.CallName` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `8002.ParcelResultDB.AccountDB.DevId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `8002.ParcelResultDB.AccountDB.State` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `8002.ParcelResultDB.AccountDB.Level` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `8002.ParcelResultDB.AccountDB.Exp` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `8002.ParcelResultDB.AccountDB.Comment` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `8002.ParcelResultDB.AccountDB.LobbyMode` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `8002.ParcelResultDB.AccountDB.MemoryLobbyUniqueId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `8002.ParcelResultDB.AccountDB.PublisherAccountId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `8002.ParcelResultDB.AccountDB.RetentionDays` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `8002.ParcelResultDB.AccountDB.VIPLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `8002.ParcelResultDB.AccountDB.UnReadMailCount` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `8002.ParcelResultDB.AccountDB.Location` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `8002.ParcelResultDB.AccountCurrencyDB.AccountLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `8002.ParcelResultDB.AccountCurrencyDB.AcademyLocationRankSum` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `8002.ParcelResultDB.EquipmentDBs.*.Type` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `8002.ParcelResultDB.EquipmentDBs.*.UniqueId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `8002.ParcelResultDB.EquipmentDBs.*.StackCount` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `8002.ParcelResultDB.ItemDBs.*.Type` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `8002.ParcelResultDB.DisplaySequence[].Key.Type` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `8006.MissionProgressDBs[].Category` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `8006.GuideMissionSeasonDBs[].LoginCount` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `10002.ShopInfos[].ShopProductList[].EventContentId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `20013.CafeDBs[].CafeId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `20013.CafeDBs[].CafeRank` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `20013.CafeDBs[].CafeVisitCharacterDBs.*.ServerId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `20013.CafeDBs[].FurnitureDBs[].Type` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `20013.CafeDBs[].FurnitureDBs[].StackCount` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `20013.CafeDBs[].FurnitureDBs[].Location` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `20013.CafeDBs[].FurnitureDBs[].PositionX` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `20013.CafeDBs[].FurnitureDBs[].Rotation` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `20013.CafeDBs[].ProductionDB.ComfortValue` | 值太少或全是常见小整数（rare_frac=0.50），值匹配无法判定 |
| `20013.CafeDBs[].ProductionDB.ProductionParcelInfos[].Key.Type` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `20013.CafeDBs[].ProductionDB.ProductionParcelInfos[].Key.Id` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `20013.CafeDBs[].ProductionDB.ProductionParcelInfos[].Amount` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `20013.ParcelResultDB.AccountDB.Nickname` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `20013.ParcelResultDB.AccountDB.CallName` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `20013.ParcelResultDB.AccountDB.DevId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `20013.ParcelResultDB.AccountDB.State` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `20013.ParcelResultDB.AccountDB.Level` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `20013.ParcelResultDB.AccountDB.Exp` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `20013.ParcelResultDB.AccountDB.Comment` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `20013.ParcelResultDB.AccountDB.LobbyMode` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `20013.ParcelResultDB.AccountDB.MemoryLobbyUniqueId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `20013.ParcelResultDB.AccountDB.PublisherAccountId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `20013.ParcelResultDB.AccountDB.RetentionDays` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `20013.ParcelResultDB.AccountDB.VIPLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `20013.ParcelResultDB.AccountDB.UnReadMailCount` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `20013.ParcelResultDB.AccountDB.Location` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `20013.ParcelResultDB.AccountCurrencyDB.AccountLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `20013.ParcelResultDB.AccountCurrencyDB.AcademyLocationRankSum` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `20013.ParcelResultDB.DisplaySequence[].Key.Type` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `20013.ParcelResultDB.DisplaySequence[].Key.Id` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `20013.ParcelResultDB.DisplaySequence[].Amount` | 值太少或全是常见小整数（rare_frac=0.33），值匹配无法判定 |
| `22000.MapId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22000.ArenaPlayerInfoDB.CurrentSeasonId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22000.ArenaPlayerInfoDB.PlayerGroupId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22000.ArenaPlayerInfoDB.AllTimeRecord` | 值太少或全是常见小整数（rare_frac=1.00），值匹配无法判定 |
| `22000.ArenaPlayerInfoDB.CumulativeTimeReward` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22000.OpponentUserDBs[].AccountServerId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22000.OpponentUserDBs[].Level` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22000.OpponentUserDBs[].Exp` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22000.OpponentUserDBs[].TeamSettingDB.EchelonType` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22000.OpponentUserDBs[].TeamSettingDB.MainCharacters[].StarGrade` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22000.OpponentUserDBs[].TeamSettingDB.MainCharacters[].PublicSkillLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22000.OpponentUserDBs[].TeamSettingDB.MainCharacters[].ExSkillLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22000.OpponentUserDBs[].TeamSettingDB.MainCharacters[].PassiveSkillLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22000.OpponentUserDBs[].TeamSettingDB.MainCharacters[].ExtraPassiveSkillLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22000.OpponentUserDBs[].TeamSettingDB.MainCharacters[].LeaderSkillLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22000.OpponentUserDBs[].TeamSettingDB.MainCharacters[].Position` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22000.OpponentUserDBs[].TeamSettingDB.MainCharacters[].CombatStyleIndex` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22000.OpponentUserDBs[].TeamSettingDB.MainCharacters[].SlotNumber` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22000.OpponentUserDBs[].TeamSettingDB.SupportCharacters[].StarGrade` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22000.OpponentUserDBs[].TeamSettingDB.SupportCharacters[].PublicSkillLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22000.OpponentUserDBs[].TeamSettingDB.SupportCharacters[].ExSkillLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22000.OpponentUserDBs[].TeamSettingDB.SupportCharacters[].PassiveSkillLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22000.OpponentUserDBs[].TeamSettingDB.SupportCharacters[].ExtraPassiveSkillLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22000.OpponentUserDBs[].TeamSettingDB.SupportCharacters[].LeaderSkillLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22000.OpponentUserDBs[].TeamSettingDB.SupportCharacters[].Position` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22000.OpponentUserDBs[].TeamSettingDB.SupportCharacters[].CombatStyleIndex` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22000.OpponentUserDBs[].TeamSettingDB.SupportCharacters[].SlotNumber` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22000.OpponentUserDBs[].TeamSettingDB.MapId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22000.OpponentUserDBs[].TeamSettingDB.TSSInteractionCharacterId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22000.OpponentUserDBs[].AccountAttachmentDB.AccountId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22000.OpponentUserDBs[].AccountAttachmentDB.EmblemUniqueId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.MissionProgressDBs[].Category` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.MissionProgressDBs[].ProgressParameters.*` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.Season` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.Group` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.AttackingUserDB.RepresentCharacterUniqueId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.AttackingUserDB.NickName` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.AttackingUserDB.Level` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.AttackingUserDB.Exp` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.AttackingUserDB.TeamSettingDB.EchelonType` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.AttackingUserDB.TeamSettingDB.LeaderCharacterId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.AttackingUserDB.TeamSettingDB.MainCharacters[].UniqueId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.AttackingUserDB.TeamSettingDB.MainCharacters[].StarGrade` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.AttackingUserDB.TeamSettingDB.MainCharacters[].Level` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.AttackingUserDB.TeamSettingDB.MainCharacters[].PublicSkillLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.AttackingUserDB.TeamSettingDB.MainCharacters[].ExSkillLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.AttackingUserDB.TeamSettingDB.MainCharacters[].PassiveSkillLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.AttackingUserDB.TeamSettingDB.MainCharacters[].ExtraPassiveSkillLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.AttackingUserDB.TeamSettingDB.MainCharacters[].LeaderSkillLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.AttackingUserDB.TeamSettingDB.MainCharacters[].EquipmentDBs[].Type` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.AttackingUserDB.TeamSettingDB.MainCharacters[].EquipmentDBs[].StackCount` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.AttackingUserDB.TeamSettingDB.MainCharacters[].EquipmentDBs[].Level` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.AttackingUserDB.TeamSettingDB.MainCharacters[].EquipmentDBs[].Tier` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.AttackingUserDB.TeamSettingDB.MainCharacters[].FavorRankInfo.*` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.AttackingUserDB.TeamSettingDB.MainCharacters[].PotentialStats.*` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.AttackingUserDB.TeamSettingDB.MainCharacters[].Position` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.AttackingUserDB.TeamSettingDB.MainCharacters[].CombatStyleIndex` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.AttackingUserDB.TeamSettingDB.MainCharacters[].SlotNumber` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.AttackingUserDB.TeamSettingDB.SupportCharacters[].UniqueId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.AttackingUserDB.TeamSettingDB.SupportCharacters[].StarGrade` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.AttackingUserDB.TeamSettingDB.SupportCharacters[].Level` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.AttackingUserDB.TeamSettingDB.SupportCharacters[].PublicSkillLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.AttackingUserDB.TeamSettingDB.SupportCharacters[].ExSkillLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.AttackingUserDB.TeamSettingDB.SupportCharacters[].PassiveSkillLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.AttackingUserDB.TeamSettingDB.SupportCharacters[].ExtraPassiveSkillLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.AttackingUserDB.TeamSettingDB.SupportCharacters[].LeaderSkillLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.AttackingUserDB.TeamSettingDB.SupportCharacters[].EquipmentDBs[].Type` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.AttackingUserDB.TeamSettingDB.SupportCharacters[].EquipmentDBs[].UniqueId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.AttackingUserDB.TeamSettingDB.SupportCharacters[].EquipmentDBs[].StackCount` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.AttackingUserDB.TeamSettingDB.SupportCharacters[].EquipmentDBs[].Level` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.AttackingUserDB.TeamSettingDB.SupportCharacters[].EquipmentDBs[].Tier` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.AttackingUserDB.TeamSettingDB.SupportCharacters[].FavorRankInfo.*` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.AttackingUserDB.TeamSettingDB.SupportCharacters[].PotentialStats.*` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.AttackingUserDB.TeamSettingDB.SupportCharacters[].Position` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.AttackingUserDB.TeamSettingDB.SupportCharacters[].CombatStyleIndex` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.AttackingUserDB.TeamSettingDB.SupportCharacters[].SlotNumber` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.AttackingUserDB.TeamSettingDB.MapId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.AttackingUserDB.TeamSettingDB.TSSInteractionCharacterId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.AttackingUserDB.AccountAttachmentDB.EmblemUniqueId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.DefendingUserDB.AccountServerId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.DefendingUserDB.RepresentCharacterUniqueId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.DefendingUserDB.NickName` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.DefendingUserDB.Level` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.DefendingUserDB.Exp` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.DefendingUserDB.TeamSettingDB.EchelonType` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.DefendingUserDB.TeamSettingDB.LeaderCharacterId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.DefendingUserDB.TeamSettingDB.MainCharacters[].UniqueId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.DefendingUserDB.TeamSettingDB.MainCharacters[].StarGrade` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.DefendingUserDB.TeamSettingDB.MainCharacters[].Level` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.DefendingUserDB.TeamSettingDB.MainCharacters[].PublicSkillLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.DefendingUserDB.TeamSettingDB.MainCharacters[].ExSkillLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.DefendingUserDB.TeamSettingDB.MainCharacters[].PassiveSkillLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.DefendingUserDB.TeamSettingDB.MainCharacters[].ExtraPassiveSkillLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.DefendingUserDB.TeamSettingDB.MainCharacters[].LeaderSkillLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.DefendingUserDB.TeamSettingDB.MainCharacters[].Position` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.DefendingUserDB.TeamSettingDB.MainCharacters[].CombatStyleIndex` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.DefendingUserDB.TeamSettingDB.MainCharacters[].SlotNumber` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.DefendingUserDB.TeamSettingDB.SupportCharacters[].UniqueId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.DefendingUserDB.TeamSettingDB.SupportCharacters[].StarGrade` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.DefendingUserDB.TeamSettingDB.SupportCharacters[].Level` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.DefendingUserDB.TeamSettingDB.SupportCharacters[].PublicSkillLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.DefendingUserDB.TeamSettingDB.SupportCharacters[].ExSkillLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.DefendingUserDB.TeamSettingDB.SupportCharacters[].PassiveSkillLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.DefendingUserDB.TeamSettingDB.SupportCharacters[].ExtraPassiveSkillLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.DefendingUserDB.TeamSettingDB.SupportCharacters[].LeaderSkillLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.DefendingUserDB.TeamSettingDB.SupportCharacters[].Position` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.DefendingUserDB.TeamSettingDB.SupportCharacters[].CombatStyleIndex` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.DefendingUserDB.TeamSettingDB.SupportCharacters[].SlotNumber` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.DefendingUserDB.TeamSettingDB.MapId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.DefendingUserDB.TeamSettingDB.TSSInteractionCharacterId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.DefendingUserDB.AccountAttachmentDB.AccountId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.DefendingUserDB.AccountAttachmentDB.EmblemUniqueId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.HashKey` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.StageId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.GroundId` | 值太少或全是常见小整数（rare_frac=1.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Winner` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.EndType` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.EndFrame` | 值太少或全是常见小整数（rare_frac=1.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.TeamId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.TSSInteractionServerId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.TSSInteractionUniqueId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.TssUseCount` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Heroes[].OwnerAccountId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Heroes[].CharacterId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Heroes[].CostumeId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Heroes[].Grade` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Heroes[].Level` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Heroes[].PotentialStatLevel.AttackPower` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Heroes[].PotentialStatLevel.HealPower` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Heroes[].PotentialStatLevel.MaxHP` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Heroes[].ExSkillLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Heroes[].PublicSkillLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Heroes[].PassiveSkillLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Heroes[].ExtraPassiveSkillLevel` | 值太少或全是常见小整数（rare_frac=0.50），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Heroes[].FavorRank` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Heroes[].HPRateBefore` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Heroes[].HPRateAfter` | 值太少或全是常见小整数（rare_frac=0.67），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Heroes[].CrowdControlCount` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Heroes[].CrowdControlDuration` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Heroes[].EvadeCount` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Heroes[].DamageImmuneCount` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Heroes[].CrowdControlImmuneCount` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Heroes[].MaxAttackPower` | 值太少或全是常见小整数（rare_frac=0.75），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Heroes[].AverageCriticalRate` | 值太少或全是常见小整数（rare_frac=0.50），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Heroes[].AverageStabilityRate` | 值太少或全是常见小整数（rare_frac=1.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Heroes[].AverageAccuracyRate` | 值太少或全是常见小整数（rare_frac=0.75），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Heroes[].DeadFrame` | 值太少或全是常见小整数（rare_frac=1.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Heroes[].DamageGivenAbsorbedSum` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Heroes[].TacticEntityType` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Heroes[].GivenNumericLogs[].EntityType` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Heroes[].GivenNumericLogs[].Category` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Heroes[].GivenNumericLogs[].Source` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Heroes[].GivenNumericLogs[].CriticalMultiplierMax` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Heroes[].ObstacleBattleNumericLogs[].EntityType` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Heroes[].ObstacleBattleNumericLogs[].Category` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Heroes[].ObstacleBattleNumericLogs[].Source` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Heroes[].ObstacleBattleNumericLogs[].CalculatedSum` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Heroes[].ObstacleBattleNumericLogs[].AppliedSum` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Heroes[].ObstacleBattleNumericLogs[].Count` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Heroes[].ObstacleBattleNumericLogs[].CriticalMultiplierMax` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Heroes[].ObstacleBattleNumericLogs[].CriticalCount` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Heroes[].ObstacleBattleNumericLogs[].CalculatedMin` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Heroes[].ObstacleBattleNumericLogs[].CalculatedMax` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Heroes[].ObstacleBattleNumericLogs[].AppliedMin` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Heroes[].ObstacleBattleNumericLogs[].AppliedMax` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Heroes[].Equipments[].Level` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Heroes[].Equipments[].Tier` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Heroes[].KillLog.*` | 值太少或全是常见小整数（rare_frac=0.75），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Heroes[].DetailFlag` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Heroes[].TakenNumericLogs[].EntityType` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Heroes[].TakenNumericLogs[].Category` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Heroes[].TakenNumericLogs[].Source` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Heroes[].TakenNumericLogs[].CriticalCount` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Heroes[].SkillCount.ExSkill01` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Heroes[].SkillCount.PublicSkill01` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Supporters[].OwnerAccountId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Supporters[].CharacterId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Supporters[].CostumeId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Supporters[].Grade` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Supporters[].Level` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Supporters[].PotentialStatLevel.AttackPower` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Supporters[].PotentialStatLevel.HealPower` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Supporters[].PotentialStatLevel.MaxHP` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Supporters[].ExSkillLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Supporters[].PublicSkillLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Supporters[].PassiveSkillLevel` | 值太少或全是常见小整数（rare_frac=0.50），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Supporters[].ExtraPassiveSkillLevel` | 值太少或全是常见小整数（rare_frac=1.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Supporters[].FavorRank` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Supporters[].HPRateBefore` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Supporters[].HPRateAfter` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Supporters[].CrowdControlCount` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Supporters[].CrowdControlDuration` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Supporters[].EvadeCount` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Supporters[].DamageImmuneCount` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Supporters[].CrowdControlImmuneCount` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Supporters[].MaxAttackPower` | 值太少或全是常见小整数（rare_frac=1.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Supporters[].AverageCriticalRate` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Supporters[].AverageStabilityRate` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Supporters[].AverageAccuracyRate` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Supporters[].DeadFrame` | 值太少或全是常见小整数（rare_frac=1.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Supporters[].DamageGivenAbsorbedSum` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Supporters[].TacticEntityType` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Supporters[].Equipments[].Level` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Supporters[].Equipments[].Tier` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Supporters[].Equipments[].UniqueId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Supporters[].SkillCount.PublicSkill01` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Supporters[].DetailFlag` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Supporters[].GivenNumericLogs[].EntityType` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Supporters[].GivenNumericLogs[].Category` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Supporters[].GivenNumericLogs[].Source` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Supporters[].GivenNumericLogs[].CalculatedSum` | 值太少或全是常见小整数（rare_frac=1.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Supporters[].GivenNumericLogs[].AppliedSum` | 值太少或全是常见小整数（rare_frac=1.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Supporters[].GivenNumericLogs[].Count` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Supporters[].GivenNumericLogs[].CriticalMultiplierMax` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Supporters[].GivenNumericLogs[].CriticalCount` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Supporters[].GivenNumericLogs[].CalculatedMin` | 值太少或全是常见小整数（rare_frac=1.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Supporters[].GivenNumericLogs[].CalculatedMax` | 值太少或全是常见小整数（rare_frac=1.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Supporters[].GivenNumericLogs[].AppliedMin` | 值太少或全是常见小整数（rare_frac=1.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Supporters[].GivenNumericLogs[].AppliedMax` | 值太少或全是常见小整数（rare_frac=1.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.Supporters[].SkillCount.ExSkill01` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.SkillCostSummary.InitialCost` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.SkillCostSummary.CostPerFrameSnapshots[].Frame` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.SkillCostSummary.CostUseSnapshots[].Frame` | 值太少或全是常见小整数（rare_frac=0.67），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.SkillCostSummary.CostUseSnapshots[].CharId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group01Summary.SkillCostSummary.CostUseSnapshots[].Level` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.TeamId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.TSSInteractionServerId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.TSSInteractionUniqueId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.TssUseCount` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Heroes[].ServerId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Heroes[].OwnerAccountId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Heroes[].CharacterId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Heroes[].CostumeId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Heroes[].Grade` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Heroes[].Level` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Heroes[].ExSkillLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Heroes[].PublicSkillLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Heroes[].PassiveSkillLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Heroes[].ExtraPassiveSkillLevel` | 值太少或全是常见小整数（rare_frac=1.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Heroes[].FavorRank` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Heroes[].HPRateBefore` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Heroes[].HPRateAfter` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Heroes[].CrowdControlCount` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Heroes[].CrowdControlDuration` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Heroes[].EvadeCount` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Heroes[].DamageImmuneCount` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Heroes[].CrowdControlImmuneCount` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Heroes[].MaxAttackPower` | 值太少或全是常见小整数（rare_frac=0.50），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Heroes[].AverageCriticalRate` | 值太少或全是常见小整数（rare_frac=0.75），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Heroes[].AverageStabilityRate` | 值太少或全是常见小整数（rare_frac=1.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Heroes[].AverageAccuracyRate` | 值太少或全是常见小整数（rare_frac=0.75），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Heroes[].DeadFrame` | 值太少或全是常见小整数（rare_frac=0.75），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Heroes[].DamageGivenAbsorbedSum` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Heroes[].TacticEntityType` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Heroes[].GivenNumericLogs[].EntityType` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Heroes[].GivenNumericLogs[].Category` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Heroes[].GivenNumericLogs[].Source` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Heroes[].GivenNumericLogs[].CriticalMultiplierMax` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Heroes[].GivenNumericLogs[].CriticalCount` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Heroes[].TakenNumericLogs[].EntityType` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Heroes[].TakenNumericLogs[].Category` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Heroes[].TakenNumericLogs[].Source` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Heroes[].TakenNumericLogs[].CriticalMultiplierMax` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Heroes[].TakenNumericLogs[].CriticalCount` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Heroes[].TakenNumericLogs[].AppliedMin` | 值太少或全是常见小整数（rare_frac=0.50），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Heroes[].SkillCount.PublicSkill01` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Heroes[].DetailFlag` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Heroes[].SkillCount.ExSkill01` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Heroes[].ObstacleBattleNumericLogs[].EntityType` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Heroes[].ObstacleBattleNumericLogs[].Category` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Heroes[].ObstacleBattleNumericLogs[].Source` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Heroes[].ObstacleBattleNumericLogs[].CalculatedSum` | 值太少或全是常见小整数（rare_frac=1.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Heroes[].ObstacleBattleNumericLogs[].AppliedSum` | 值太少或全是常见小整数（rare_frac=1.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Heroes[].ObstacleBattleNumericLogs[].Count` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Heroes[].ObstacleBattleNumericLogs[].CriticalMultiplierMax` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Heroes[].ObstacleBattleNumericLogs[].CriticalCount` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Heroes[].ObstacleBattleNumericLogs[].CalculatedMin` | 值太少或全是常见小整数（rare_frac=0.50），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Heroes[].ObstacleBattleNumericLogs[].CalculatedMax` | 值太少或全是常见小整数（rare_frac=1.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Heroes[].ObstacleBattleNumericLogs[].AppliedMin` | 值太少或全是常见小整数（rare_frac=0.50），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Heroes[].ObstacleBattleNumericLogs[].AppliedMax` | 值太少或全是常见小整数（rare_frac=1.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Supporters[].ServerId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Supporters[].OwnerAccountId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Supporters[].CharacterId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Supporters[].CostumeId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Supporters[].Grade` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Supporters[].Level` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Supporters[].ExSkillLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Supporters[].PublicSkillLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Supporters[].PassiveSkillLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Supporters[].ExtraPassiveSkillLevel` | 值太少或全是常见小整数（rare_frac=1.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Supporters[].FavorRank` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Supporters[].HPRateBefore` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Supporters[].HPRateAfter` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Supporters[].CrowdControlCount` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Supporters[].CrowdControlDuration` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Supporters[].EvadeCount` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Supporters[].DamageImmuneCount` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Supporters[].CrowdControlImmuneCount` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Supporters[].MaxAttackPower` | 值太少或全是常见小整数（rare_frac=1.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Supporters[].AverageCriticalRate` | 值太少或全是常见小整数（rare_frac=0.50），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Supporters[].AverageStabilityRate` | 值太少或全是常见小整数（rare_frac=0.50），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Supporters[].AverageAccuracyRate` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Supporters[].DeadFrame` | 值太少或全是常见小整数（rare_frac=1.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Supporters[].DamageGivenAbsorbedSum` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Supporters[].TacticEntityType` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Supporters[].SkillCount.PublicSkill01` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Supporters[].DetailFlag` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Supporters[].GivenNumericLogs[].EntityType` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Supporters[].GivenNumericLogs[].Category` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Supporters[].GivenNumericLogs[].Source` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Supporters[].GivenNumericLogs[].CalculatedSum` | 值太少或全是常见小整数（rare_frac=0.50），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Supporters[].GivenNumericLogs[].AppliedSum` | 值太少或全是常见小整数（rare_frac=1.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Supporters[].GivenNumericLogs[].Count` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Supporters[].GivenNumericLogs[].CriticalCount` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Supporters[].GivenNumericLogs[].CalculatedMin` | 值太少或全是常见小整数（rare_frac=1.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Supporters[].GivenNumericLogs[].CalculatedMax` | 值太少或全是常见小整数（rare_frac=1.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Supporters[].GivenNumericLogs[].AppliedMin` | 值太少或全是常见小整数（rare_frac=0.50），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Supporters[].GivenNumericLogs[].AppliedMax` | 值太少或全是常见小整数（rare_frac=0.50），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.Supporters[].SkillCount.ExSkill01` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.SkillCostSummary.InitialCost` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.SkillCostSummary.CostUseSnapshots[].Frame` | 值太少或全是常见小整数（rare_frac=0.33），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.SkillCostSummary.CostUseSnapshots[].CharId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.Group02Summary.SkillCostSummary.CostUseSnapshots[].Level` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.ArenaSummary.ArenaMapId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.ArenaSummary.EnemyAccountId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaBattleDB.BattleSummary.ArenaSummary.EnemyAccountLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaPlayerInfoDB.CurrentSeasonId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaPlayerInfoDB.PlayerGroupId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.ArenaPlayerInfoDB.AllTimeRecord` | 值太少或全是常见小整数（rare_frac=1.00），值匹配无法判定 |
| `22004.ArenaPlayerInfoDB.CumulativeTimeReward` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.AccountCurrencyDB.AccountLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.AccountCurrencyDB.AcademyLocationRankSum` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.VictoryRewards.AccountDB.Nickname` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.VictoryRewards.AccountDB.CallName` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.VictoryRewards.AccountDB.DevId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.VictoryRewards.AccountDB.State` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.VictoryRewards.AccountDB.Level` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.VictoryRewards.AccountDB.Exp` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.VictoryRewards.AccountDB.Comment` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.VictoryRewards.AccountDB.LobbyMode` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.VictoryRewards.AccountDB.MemoryLobbyUniqueId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.VictoryRewards.AccountDB.PublisherAccountId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.VictoryRewards.AccountDB.RetentionDays` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.VictoryRewards.AccountDB.VIPLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.VictoryRewards.AccountDB.UnReadMailCount` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.VictoryRewards.AccountDB.Location` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.VictoryRewards.AccountCurrencyDB.AccountLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.VictoryRewards.AccountCurrencyDB.AcademyLocationRankSum` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.VictoryRewards.DisplaySequence[].Key.Type` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.VictoryRewards.DisplaySequence[].Key.Id` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.VictoryRewards.DisplaySequence[].Amount` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.SeasonRewards.AccountDB.Nickname` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.SeasonRewards.AccountDB.CallName` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.SeasonRewards.AccountDB.DevId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.SeasonRewards.AccountDB.State` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.SeasonRewards.AccountDB.Level` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.SeasonRewards.AccountDB.Exp` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.SeasonRewards.AccountDB.Comment` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.SeasonRewards.AccountDB.LobbyMode` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.SeasonRewards.AccountDB.MemoryLobbyUniqueId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.SeasonRewards.AccountDB.PublisherAccountId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.SeasonRewards.AccountDB.RetentionDays` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.SeasonRewards.AccountDB.VIPLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.SeasonRewards.AccountDB.UnReadMailCount` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.SeasonRewards.AccountDB.Location` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.SeasonRewards.AccountCurrencyDB.AccountLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.SeasonRewards.AccountCurrencyDB.AcademyLocationRankSum` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.SeasonRewards.DisplaySequence[].Key.Type` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.SeasonRewards.DisplaySequence[].Key.Id` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.SeasonRewards.DisplaySequence[].Amount` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.EchelonType` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.Buid` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.BattleDurationInFrame` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.GroundUniqueId` | 值太少或全是常见小整数（rare_frac=1.00），值匹配无法判定 |
| `22004.BattleSetting.StageId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.EnvironmentType` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.LeftTeam.TeamId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.LeftTeam.TeamName` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.LeftTeam.FormationLocationKey.GroupId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.LeftTeam.Starters[].EntityId.uniqueId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.LeftTeam.Starters[].AssistRelation` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.LeftTeam.Starters[].OwnerAccountId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.LeftTeam.Starters[].CharacterId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.LeftTeam.Starters[].HeroId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.LeftTeam.Starters[].Grade` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.LeftTeam.Starters[].FavorRankInfo.*` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.LeftTeam.Starters[].FavorRank` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.LeftTeam.Starters[].CombatStyleIndex` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.LeftTeam.Starters[].Level` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.LeftTeam.Starters[].AIId` | 值太少或全是常见小整数（rare_frac=0.33），值匹配无法判定 |
| `22004.BattleSetting.LeftTeam.Starters[].EchelonSlotType` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.LeftTeam.Starters[].EchelonSlotNumber` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.LeftTeam.Starters[].Line` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.LeftTeam.Starters[].LineIndex` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.LeftTeam.Starters[].InitialHPRate.rawValue` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.LeftTeam.Starters[].SkillLevelTable.ExSkill01` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.LeftTeam.Starters[].SkillLevelTable.ExtraPassive01` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.LeftTeam.Starters[].SkillLevelTable.Passive01` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.LeftTeam.Starters[].SkillLevelTable.PublicSkill01` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.LeftTeam.Starters[].EquipmentSettings[].Level` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.LeftTeam.Starters[].EquipmentSettings[].Tier` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.LeftTeam.Starters[].PotentialStatLevelDict.*` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.LeftTeam.Supporters[].EntityId.uniqueId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.LeftTeam.Supporters[].AssistRelation` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.LeftTeam.Supporters[].OwnerAccountId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.LeftTeam.Supporters[].CharacterId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.LeftTeam.Supporters[].HeroId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.LeftTeam.Supporters[].Grade` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.LeftTeam.Supporters[].FavorRankInfo.*` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.LeftTeam.Supporters[].FavorRank` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.LeftTeam.Supporters[].CombatStyleIndex` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.LeftTeam.Supporters[].Level` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.LeftTeam.Supporters[].AIId` | 值太少或全是常见小整数（rare_frac=1.00），值匹配无法判定 |
| `22004.BattleSetting.LeftTeam.Supporters[].EchelonSlotType` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.LeftTeam.Supporters[].EchelonSlotNumber` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.LeftTeam.Supporters[].Line` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.LeftTeam.Supporters[].LineIndex` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.LeftTeam.Supporters[].InitialHPRate.rawValue` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.LeftTeam.Supporters[].SkillLevelTable.ExSkill01` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.LeftTeam.Supporters[].SkillLevelTable.ExtraPassive01` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.LeftTeam.Supporters[].SkillLevelTable.Passive01` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.LeftTeam.Supporters[].SkillLevelTable.PublicSkill01` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.LeftTeam.Supporters[].EquipmentSettings[].UniqueId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.LeftTeam.Supporters[].EquipmentSettings[].Level` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.LeftTeam.Supporters[].EquipmentSettings[].Tier` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.LeftTeam.Supporters[].PotentialStatLevelDict.*` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.LeftTeam.ArenaSetting.TeamLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.LeftTeam.ArenaSetting.RepresentCharacterId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.LeftTeam.ArenaSetting.ArenaMapUniqueId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.LeftTeam.ArenaSetting.EmblemId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.RightTeam.TeamId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.RightTeam.TeamName` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.RightTeam.FormationLocationKey.GroupId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.RightTeam.Starters[].EntityId.uniqueId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.RightTeam.Starters[].ServerId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.RightTeam.Starters[].AssistRelation` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.RightTeam.Starters[].OwnerAccountId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.RightTeam.Starters[].CharacterId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.RightTeam.Starters[].HeroId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.RightTeam.Starters[].Grade` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.RightTeam.Starters[].FavorRank` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.RightTeam.Starters[].CombatStyleIndex` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.RightTeam.Starters[].Level` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.RightTeam.Starters[].AIId` | 值太少或全是常见小整数（rare_frac=0.50），值匹配无法判定 |
| `22004.BattleSetting.RightTeam.Starters[].EchelonSlotType` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.RightTeam.Starters[].EchelonSlotNumber` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.RightTeam.Starters[].Line` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.RightTeam.Starters[].LineIndex` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.RightTeam.Starters[].InitialHPRate.rawValue` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.RightTeam.Starters[].SkillLevelTable.ExSkill01` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.RightTeam.Starters[].SkillLevelTable.ExtraPassive01` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.RightTeam.Starters[].SkillLevelTable.Passive01` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.RightTeam.Starters[].SkillLevelTable.PublicSkill01` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.RightTeam.Starters[].SkillLevelTable.HiddenPassive01` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.RightTeam.Supporters[].EntityId.uniqueId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.RightTeam.Supporters[].ServerId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.RightTeam.Supporters[].AssistRelation` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.RightTeam.Supporters[].OwnerAccountId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.RightTeam.Supporters[].CharacterId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.RightTeam.Supporters[].HeroId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.RightTeam.Supporters[].Grade` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.RightTeam.Supporters[].FavorRank` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.RightTeam.Supporters[].CombatStyleIndex` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.RightTeam.Supporters[].Level` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.RightTeam.Supporters[].AIId` | 值太少或全是常见小整数（rare_frac=0.50），值匹配无法判定 |
| `22004.BattleSetting.RightTeam.Supporters[].EchelonSlotType` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.RightTeam.Supporters[].EchelonSlotNumber` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.RightTeam.Supporters[].Line` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.RightTeam.Supporters[].LineIndex` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.RightTeam.Supporters[].InitialHPRate.rawValue` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.RightTeam.Supporters[].SkillLevelTable.ExSkill01` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.RightTeam.Supporters[].SkillLevelTable.ExtraPassive01` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.RightTeam.Supporters[].SkillLevelTable.Passive01` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.RightTeam.Supporters[].SkillLevelTable.PublicSkill01` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.RightTeam.ArenaSetting.TeamLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.RightTeam.ArenaSetting.RepresentCharacterId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.RightTeam.ArenaSetting.ArenaMapUniqueId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.RightTeam.ArenaSetting.EmblemId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22004.BattleSetting.StageIndex` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22008.TimeRewardAmount` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22008.ParcelResult.AccountDB.Nickname` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22008.ParcelResult.AccountDB.CallName` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22008.ParcelResult.AccountDB.DevId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22008.ParcelResult.AccountDB.State` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22008.ParcelResult.AccountDB.Level` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22008.ParcelResult.AccountDB.Exp` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22008.ParcelResult.AccountDB.Comment` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22008.ParcelResult.AccountDB.LobbyMode` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22008.ParcelResult.AccountDB.MemoryLobbyUniqueId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22008.ParcelResult.AccountDB.PublisherAccountId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22008.ParcelResult.AccountDB.RetentionDays` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22008.ParcelResult.AccountDB.VIPLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22008.ParcelResult.AccountDB.UnReadMailCount` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22008.ParcelResult.AccountDB.Location` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22008.ParcelResult.AccountCurrencyDB.AccountLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22008.ParcelResult.AccountCurrencyDB.AcademyLocationRankSum` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22008.ParcelResult.DisplaySequence[].Key.Type` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22008.ParcelResult.DisplaySequence[].Key.Id` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22009.ParcelResult.AccountDB.Nickname` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22009.ParcelResult.AccountDB.CallName` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22009.ParcelResult.AccountDB.DevId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22009.ParcelResult.AccountDB.State` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22009.ParcelResult.AccountDB.Level` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22009.ParcelResult.AccountDB.Exp` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22009.ParcelResult.AccountDB.Comment` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22009.ParcelResult.AccountDB.LobbyMode` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22009.ParcelResult.AccountDB.MemoryLobbyUniqueId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22009.ParcelResult.AccountDB.PublisherAccountId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22009.ParcelResult.AccountDB.RetentionDays` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22009.ParcelResult.AccountDB.VIPLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22009.ParcelResult.AccountDB.UnReadMailCount` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22009.ParcelResult.AccountDB.Location` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22009.ParcelResult.AccountCurrencyDB.AccountLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22009.ParcelResult.AccountCurrencyDB.AcademyLocationRankSum` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22009.ParcelResult.ItemDBs.*.Type` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22009.ParcelResult.ItemDBs.*.UniqueId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22009.ParcelResult.ItemDBs.*.StackCount` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22009.ParcelResult.DisplaySequence[].Key.Type` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22009.ParcelResult.DisplaySequence[].Key.Id` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `22009.ParcelResult.DisplaySequence[].Amount` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `25003.EventRewardIncreaseDBs[].EventTargetType` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `25003.EventRewardIncreaseDBs[].RewardRealType` | 值太少或全是常见小整数（rare_frac=1.00），值匹配无法判定 |
| `25003.EventRewardIncreaseDBs[].Multiplier.rawValue` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `28000.AccountClanDB.ClanName` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `28000.AccountClanDB.ClanChannelName` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `28000.AccountClanDB.ClanPresidentNickName` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `28000.AccountClanDB.ClanPresidentRepresentCharacterUniqueId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `28000.AccountClanDB.ClanPresidentRepresentCharacterCostumeId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `28000.AccountClanDB.ClanNotice` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `28000.AccountClanDB.ClanMemberCount` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `28000.AccountClanDB.ClanManagerCount` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `28000.AccountClanDB.ClanJoinOption` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `28000.AccountClanMemberDB.AccountLevel` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `28000.AccountClanMemberDB.AccountNickName` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `28000.AccountClanMemberDB.RepresentCharacterUniqueId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `28000.AccountClanMemberDB.RepresentCharacterCostumeId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `28000.AccountClanMemberDB.AttendanceCount` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `28000.AccountClanMemberDB.ClanSocialGrade` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `28000.AccountClanMemberDB.AttachmentDB.EmblemUniqueId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `28000.ClanMemberDBs[].AccountNickName` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `28000.ClanMemberDBs[].RepresentCharacterCostumeId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `28000.ClanMemberDBs[].ClanSocialGrade` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `29002.CountList[].ShopCashId` | 值太少或全是常见小整数（rare_frac=1.00），值匹配无法判定 |
| `29002.CountList[].PurchaseCount` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `35003.ProgressDBs[].Category` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `35003.ProgressDBs[].ProgressParameters.*` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `90004.Data.Banners[].BannerType` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `90004.Data.Banners[].LinkUrl` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `90004.Data.Banners[].SurveyId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `90004.Data.GachaProbabilityDisplay[].GachaProbabilityDisplayId` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `90004.Data.GachaProbabilityDisplay[].GachaDisplayTag` | 值太少或全是常见小整数（rare_frac=1.00），值匹配无法判定 |
| `90009.ChatRecords[].MessageType` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `90009.ChatRecords[].SubType` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `90009.ChatRecords[].SocialGrade` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `90009.ChatRecords[].AccountNickname` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |
| `90009.ChatRecords[].Text` | 值太少或全是常见小整数（rare_frac=0.00），值匹配无法判定 |

</details>

### 5.3 C 类：玩家进度（不是「找不到」，是本来就不该查表）— 369 条

典型：`ServerId`/`AccountServerId`/`AccountId`（账号内自增 id，全库 0 命中）、各种 `Level/Exp/StarGrade/FavorRank/PurchaseCount/ClearTurnRecord`、所有 `*Date`/`*Time`（时间戳）、`EchelonDBs[].LeaderServerId`（指向角色实例 id）。
这些私服自己存即可。**注意区分同一个元素里两个 id 的角色**：

| 协议元素 | 静态 id（查表） | 玩家实例 id（自己存） |
|---|---|---|
| `ItemDBs[]` | `UniqueId` → `ItemDBSchema.Id` | `ServerId`（24xxxxxx） |
| `EquipmentDBs[]` | `UniqueId` → `EquipmentDBSchema.Id` | `ServerId` |
| `CharacterDBs[]` | `UniqueId` → `CharacterDBSchema.Id` | `ServerId`（3002894…） |
| `FurnitureDBs[]` | `UniqueId` → `FurnitureDBSchema.Id` | `ServerId` |

## 6. 四个特别问题的回答

### Q1. `CharacterDBSchema` 有 7223 行，官方账号只有 46 个角色 —— 玩家角色是子集还是另有表？

**是子集，没有另一张表。**

- 官方 46 个 `CharacterListResponse.CharacterDBs[].UniqueId` 实测是：
  `10006 10026 10037 10043 10055 10063 10081 10108 10114 10117 13000~13013 16000~16017 20032 23000~23008 26000~26005`，
  **46/46 全部命中** `CharacterDBSchema.Id`（该表 Id 范围 10000..838060812，7223 行）。
- 每个角色在表里是 1 行（`Id` 唯一），7223 行覆盖了所有版本/所有形态（换装 Costume 也在里面，`CostumeDBSchema` 5913 行单独存换装）。
- 玩家「拥有角色」这件事**不存在于 ExcelDB**：它是 `CharacterDBs[]` 这条 SQL 行本身（`ServerId` 是账号内自增实例 id，加上 `StarGrade/Level/Exp/FavorRank/技能等级` 等练度列）。
- 所以私服建号时：从 `CharacterDBSchema` 取静态定义（名字/立绘/技能组/星级上限），自己在 DB 里存 (账号, CharacterId, ServerId, 练度…)。
- 校验命令：`python work/ba/proto/probe_claims.py` 的 [C11] 一段。

### Q2. 官方 `ItemDBs` 134 条 → `ItemDBSchema` 多少行？

**`ItemDBSchema` 1803 行；134 个 `UniqueId` 全部命中，是它的一小部分。**

- 134/134 命中 `ItemDBSchema.Id`（`sql:Id`，同时 flatbuffer `f0`/`f1` 是同一 Id 的重复字段）。
- 只占 1803 行的 7.4%：账号只持有其中一部分道具（其余是未获得/活动限定/版本未开）。
- 同理 `EquipmentDBs` 84 条（54 个不同 id）→ `EquipmentDBSchema` **191 行**，全部命中。
- 注意 `ItemDBs[].Type`（恒 4）**不是** `ItemDBSchema` 的字段：我核对过它和 `ItemDBSchema.f5` 只有 14/134 巧合相等；`Type` 是 ParcelType 枚举，由「这条记录在哪个背包 DB 里」决定（装备列表里同位置恒为 3）。

### Q3. 官方 `ShopRecruits` 529 条 → `ShopRecruitDBSchema` 532 行，差的 3 条是什么？

**差的就是 `Id = 1, 2, 3` 这三行**（官方 529 条 ⊂ 表 532 条，差值集合 = {1,2,3}，已实测）。

内容是 **id 段最靠前的 3 行**（1/2/3），字段值与正式卡池明显不同，且官方从不下发它们：

| 槽位 | Id=1/2/3 | Id=5000000（真实卡池） |
|---|---|---|
| `f1` | 11 / 11 / 32 | 6 |
| `f3` | 3 | 5000001 |
| `f4` | 1 | 5000002 |
| `f5` | 76 / 76 / 108 | 148 |
| `f7` | 20 | 30 |
| `f8` | 84 | 120 |
| `f9` | [5000] | [5000] |
| `f12` | 19457 | 1280000001 |
| `f13/f14` | 76 / 72 | 100 / 80 |
| `f15/f16` | 79999 / 19999 | 1900000 / 1900000 |

- 1、2、3 属于「新手/基础池」段（id 段 1..3），5000000+ 是正式限定池，6000000+/7000000+/9000000+/99999999 是各版本追加池。
- 官方响应从 5000000 开始，说明服务器只下发 5000000+ 的池子；私服过滤规则：**跑 `ShopRecruitDBSchema` 全表，排除 Id ≤ 3 即可得到 529 条**。
- 复核：`python work/ba/data/dump_table.py --table ShopRecruitDBSchema --where "Id in (1,2,3,5000000)"`

### Q4. 学院 `AcademyLocationDBSchema` 11 行 vs 官方 9 条 —— 缺的 14/18 在表里是什么？

**表里 11 个 Id = [1,7,11,12,13,14,15,16,17,18,19]；官方 9 个 = [1,7,11,12,13,15,16,17,19]；缺的正是 14 和 18。**

| Id | 表内 `f2`（prefab 路径） | 含义 |
|---|---|---|
| 1 | `Academy/Location_SchaleOffice` | 夏莱办公室（大厅） |
| 7 | `Academy/Location_SchaleResidence` | 夏莱宿舍 |
| 11 | `Academy/Location_Gehenna` | 格黑娜 |
| 12 | `Academy/Location_Abydos` | 阿拜多斯 |
| 13 | `Academy/Location_Millennium` | 千年 |
| **14** | **`Academy/Location_Trinity`** | **三一（官方响应里没有）** |
| 15 | `Academy/Location_RedWinter` | 红冬 |
| 16 | `Academy/Location_Hyakkiyako` | 百鬼夜行 |
| 17 | `Academy/Location_DU_Shiratori` | D.U. 白鸟区 |
| **18** | **`Academy/Location_Shanhaijing`** | **山海经（官方响应里没有）** |
| 19 | `Academy/Location_Haruhabara` | 春叶原 |

- 这两行本身是**完整的合法配置**（有 prefab、有 `f7` 区域号、有 `f8`），不是脏数据。
- 官方账号缺它们的原因在**玩家侧**：`AcademyLocationDBs[]` 是每账号一行（带 `AccountId/Rank/Exp`），账号没解锁/没访问过就不下发。私服要么按剧情进度解锁、要么干脆 11 个全发（客户端不会崩，这两行只多一个可点的地标）。

## 7. 对做私服的直接结论

**必须查 ExcelDB 的（都有 verified 证据）：**

| 用途 | 表 | 键 | 对应协议字段 |
|---|---|---|---|
| 道具定义 | `ItemDBSchema`(1803) | `Id` | `4000.ItemDBs[].UniqueId` |
| 装备定义 | `EquipmentDBSchema`(191) | `Id` | `1017.EquipmentDBs[].UniqueId` |
| 角色定义 | `CharacterDBSchema`(7223) | `Id` | `1017.CharacterDBs[].UniqueId`、咖啡厅/学院到访角色 |
| 家具定义 | `FurnitureDBSchema`(876) | `Id` | `20001.FurnitureDBs[].UniqueId` |
| 关卡定义 | `CampaignStageDBSchema`(407) | `Id` | `6000.StageHistoryDBs[].StageUniqueId` |
| 章节定义 | `CampaignChapterDBSchema`(29) | `Id` | `6000.StageHistoryDBs[].ChapterUniqueId` |
| 剧情定义 | `ScenarioModeDBSchema`(581) | `Id`(SQL 列名 `ModeId`) | `1017.ScenarioHistoryDBs[].ScenarioUniqueId` |
| 招募池 | `ShopRecruitDBSchema`(532) | `Id` | `1017.ShopRecruits[].Id` |
| 商店商品 | `ShopDBSchema`(7908) | `Id` + `CategoryType` | `10002.ShopProductList[].ShopExcelId/Category` |
| 商店分类 | `ShopInfoDBSchema`(18) | `CategoryType` | `10002.ShopInfos[].Category` |
| 咖啡厅 | `CafeInfoDBSchema`(2) | `CafeId` | `20001.CafeDB.CafeId` |
| 咖啡厅等级上限 | `CafeRankDBSchema`(20) | (`CafeId`,`Rank`) | 校验 `CafeDB.CafeRank` |
| 学院地点 | `AcademyLocationDBSchema`(11) | `Id` | `24000.AcademyLocationDBs[].LocationId` |
| 学院地点等级上限 | `AcademyLocationRankDBSchema`(12) | `Rank` | 校验 `AcademyLocationDBs[].Rank` |
| 货币 | `CurrencyDBSchema`(29) | `ID` | `1017.AccountCurrencyDB.CurrencyDict` 的 **key** |
| 招募时间 | ❌ 没有 | — | 私服自造排期表 |

**完全不用查表的协议**：`5000 Echelon_List`（编队=玩家数据）、`22000/22004 Arena`（战斗状态）、`8000 Mission_List` 的进度部分（任务定义表在 `MissionDBSchema` 等，但 `ProgressDBs[]` 本身是玩家状态）、`7000 Mail`、`28019 Clan_Check`。

**每个账号建号时必需的自增 id 空间（ExcelDB 里没有）**：
`CharacterDBs[].ServerId`（3xxxxxx）、`EquipmentDBs[].ServerId`/`ItemDBs[].ServerId`（24xxxxxx）、`CafeDBId`（AccountId*100+n）、`AccountServerId`/`AccountId`。

## 8. 局限 / 还能怎么继续

1. **没有 .fbs**：ExcelDB 的 FlatBuffers 字段只能给槽位序号（`f0/f1/…`）。要拿到字段名，需要客户端 `Assembly-CSharp` 里各 `*Excel` 类的 `Add*` 顺序（`dump_table.py --fields` 支持贴名）。本报告里的字段名（`Id`/`CategoryType`/`MessageGroupId`…）来自 **SQL 索引列**或协议字段名，不是猜的。
2. **`ambiguous` 的 99 条需要逐条裁定**：低基数 id（章节号 101..116、地点号 1..19）天生无法靠值区分，我用了「行内一致性」（如 `floor(StageUniqueId/10000)==ChapterUniqueId` 通过 90/90）和「域恰好相等」（`ShopDBSchema.CategoryType=38` 恰好 2 行 = 官方 2 个商品）来补，但仍有部分（如 `DisplayOrder` 具体是 `f6` 还是 `f10`）需要按客户端实际读取顺序确认。
3. **`8002/6021/22004` 等回包的深层字段**只是自动匹配，没人工复核，`ambiguous` 结果不要直接写进服务端。
4. **官方样本只有 1 个账号**（10015354380 / 2026-11 的快照）。「玩家数据」的判定基于「全库 0 命中 + 量级」，如果某个 id 恰好是静态 id 但该账号没有，可能会被误判成 player —— 有第二个账号样本时应该重跑 `xls_match.py` 对比。
5. 索引只收了**整数**（和 ≤64 字符的字符串槽位）。浮点字段（坐标、倍率）没有进索引，所以 `PositionX/PositionY` 这类字段天然只能判 `player`。

---

产物：`excel_field_map.json`（机器读，含 398 表 + 1340 条字段映射 + 每协议统计）、本文、`_match_report.json`（全协议原始匹配结果）、`_inventory.json`、`_xls_index.pkl`（倒排索引）。
