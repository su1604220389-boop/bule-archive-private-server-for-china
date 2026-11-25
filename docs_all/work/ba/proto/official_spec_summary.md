# 官方抓包结构规格 (official_spec.json) 摘要

- 来源: `report/_tmp/official201.har` -> 解码目录 `report/_tmp/official_decoded_201/`
- 响应 109 条 / 协议 38 个 / 生成时间 2026-11-16T05:10:24+08:00
- spec 只含形状，不含任何值；玩家数据字段已标注 `is_player_data`

## 1. 协议覆盖

| 协议号 | 名称 | 观测次数 | 置信度 | 顶层键数 | 顶层必填键 | 节点数 |
|---|---|---|---|---|---|---|
| 3 | NetworkTime_Sync | 1 | low | 7 | 7 | 10 |
| 1002 | Account_Auth | 1 | low | 32 | 32 | 90 |
| 1005 | Account_GetTutorial | 1 | low | 6 | 6 | 10 |
| 1017 | Account_LoginSync | 1 | low | 35 | 35 | 490 |
| 4000 | Item_List | 1 | low | 7 | 7 | 17 |
| 5000 | Echelon_List | 4 | high | 6 | 6 | 25 |
| 5001 | Echelon_Save | 2 | medium | 6 | 6 | 24 |
| 6000 | Campaign_List | 1 | low | 8 | 8 | 30 |
| 6020 | Campaign_EnterMainStageStrategySkip | 1 | low | 6 | 6 | 16 |
| 6021 | Campaign_MainStageStrategySkipResult | 1 | low | 12 | 12 | 82 |
| 7000 | Mail_List | 1 | low | 7 | 7 | 27 |
| 7001 | Mail_Check | 9 | high | 6 | 6 | 9 |
| 7003 | Mail_ListSemiPermanent | 1 | low | 5 | 5 | 8 |
| 8000 | Mission_List | 3 | medium | 10 | 10 | 24 |
| 8002 | Mission_MultipleReward | 1 | low | 8 | 8 | 76 |
| 8006 | Mission_GuideMissionSeasonList | 1 | low | 7 | 7 | 24 |
| 10002 | Shop_List | 1 | low | 7 | 7 | 30 |
| 15002 | OpenCondition_EventList | 1 | low | 6 | 6 | 11 |
| 16000 | Toast_List | 1 | low | 6 | 6 | 9 |
| 20001 | Cafe_Ack | 1 | low | 6 | 6 | 44 |
| 20013 | Cafe_ReceiveCurrency | 1 | low | 7 | 7 | 83 |
| 22000 | Arena_EnterLobby | 2 | medium | 10 | 10 | 71 |
| 22004 | Arena_EnterBattle | 1 | low | 14 | 14 | 771 |
| 22008 | Arena_CumulativeTimeReward | 1 | low | 8 | 8 | 48 |
| 22009 | Arena_DailyReward | 1 | low | 7 | 7 | 54 |
| 22016 | Arena_SyncEchelonSettingTime | 1 | low | 6 | 6 | 9 |
| 24000 | Academy_GetInfo | 2 | medium | 7 | 7 | 24 |
| 25003 | Event_RewardIncrease | 21 | high | 6 | 6 | 16 |
| 26000 | ContentSave_Get | 1 | low | 8 | 8 | 11 |
| 28000 | Clan_Lobby | 1 | low | 9 | 9 | 56 |
| 28019 | Clan_Check | 8 | high | 5 | 5 | 8 |
| 29002 | Billing_PurchaseListByYostar | 3 | medium | 8 | 8 | 18 |
| 30041 | EventContent_PermanentList | 1 | low | 6 | 6 | 12 |
| 35003 | MiniGame_MissionList | 1 | low | 8 | 8 | 19 |
| 36001 | Notification_EventContentReddotCheck | 10 | high | 7 | 7 | 12 |
| 43010 | Friend_Check | 8 | high | 5 | 5 | 8 |
| 90004 | Management_Data | 10 | high | 6 | 6 | 50 |
| 90009 | Clan_Chat_Records | 2 | medium | 6 | 6 | 20 |

## 2. 全局必填头字段

| 键 | 响应中出现的条数 | 必填的协议数 | 判定 |
|---|---|---|---|
| `Protocol` | 109/109 | 38/38 | 全部必填 |
| `SessionKey` | 109/109 | 38/38 | 全部必填 |
| `ServerTimeTicks` | 109/109 | 38/38 | 全部必填 |
| `ServerNotification` | 109/109 | 38/38 | 全部必填 |
| `RequestId` | 109/109 | 38/38 | 全部必填 |

## 3. 样本不足的协议 (observations <= 2)

| 协议号 | 名称 | 观测 | 顶层键 | 节点数 |
|---|---|---|---|---|
| 3 | NetworkTime_Sync | 1 | 7 | 10 |
| 1002 | Account_Auth | 1 | 32 | 90 |
| 1005 | Account_GetTutorial | 1 | 6 | 10 |
| 1017 | Account_LoginSync | 1 | 35 | 490 |
| 4000 | Item_List | 1 | 7 | 17 |
| 5001 | Echelon_Save | 2 | 6 | 24 |
| 6000 | Campaign_List | 1 | 8 | 30 |
| 6020 | Campaign_EnterMainStageStrategySkip | 1 | 6 | 16 |
| 6021 | Campaign_MainStageStrategySkipResult | 1 | 12 | 82 |
| 7000 | Mail_List | 1 | 7 | 27 |
| 7003 | Mail_ListSemiPermanent | 1 | 5 | 8 |
| 8002 | Mission_MultipleReward | 1 | 8 | 76 |
| 8006 | Mission_GuideMissionSeasonList | 1 | 7 | 24 |
| 10002 | Shop_List | 1 | 7 | 30 |
| 15002 | OpenCondition_EventList | 1 | 6 | 11 |
| 16000 | Toast_List | 1 | 6 | 9 |
| 20001 | Cafe_Ack | 1 | 6 | 44 |
| 20013 | Cafe_ReceiveCurrency | 1 | 7 | 83 |
| 22000 | Arena_EnterLobby | 2 | 10 | 71 |
| 22004 | Arena_EnterBattle | 1 | 14 | 771 |
| 22008 | Arena_CumulativeTimeReward | 1 | 8 | 48 |
| 22009 | Arena_DailyReward | 1 | 7 | 54 |
| 22016 | Arena_SyncEchelonSettingTime | 1 | 6 | 9 |
| 24000 | Academy_GetInfo | 2 | 7 | 24 |
| 26000 | ContentSave_Get | 1 | 8 | 11 |
| 28000 | Clan_Lobby | 1 | 9 | 56 |
| 30041 | EventContent_PermanentList | 1 | 6 | 12 |
| 35003 | MiniGame_MissionList | 1 | 8 | 19 |
| 90009 | Clan_Chat_Records | 2 | 6 | 20 |

## 4. 样本不足的字段

### 4.1 seen<=2 且父层实例更多 (关键的可选/稀有字段)

| 协议号 | 路径 | 类型 | seen/父实例 |
|---|---|---|---|
| 1017 | `CafeGetInfoResponse.CafeDBs[].FurnitureDBs[].Rotation` | int | 2/25 |
| 1017 | `CafeGetInfoResponse.FurnitureDBs[].Rotation` | int | 2/27 |
| 8006 | `GuideMissionSeasonDBs[].IsFinalMissionComplete` | bool | 1/17 |
| 20001 | `CafeDB.FurnitureDBs[].Rotation` | int | 1/14 |
| 20013 | `CafeDBs[].FurnitureDBs[].Rotation` | int | 2/25 |
| 22004 | `MissionProgressDBs[].Complete` | bool | 1/6 |

### 4.2 观测到缺失但父层实例<=5 (可选性证据弱)

未找到。

## 5. 纯玩家数据字段 (is_player_data)

- 标量玩家数据字段 1054 个(容器节点另有 *DB/*DBs 标注, 子字段继承)
- 完整清单见 `official_spec.json -> player_data_fields`

| 协议号 | 路径 | 类型 | 依据 |
|---|---|---|---|
| 3 | `SessionKey.AccountServerId` | int | name:AccountServerId |
| 3 | `SessionKey.MxToken` | str | name:MxToken |
| 1002 | `AccountDB.BirthDay` | str | inherits:parent_is_player_db |
| 1002 | `AccountDB.CallName` | str | inherits:parent_is_player_db |
| 1002 | `AccountDB.CallNameUpdateTime` | str | inherits:parent_is_player_db |
| 1002 | `AccountDB.Comment` | str | name:Comment |
| 1002 | `AccountDB.CreateDate` | str | inherits:parent_is_player_db |
| 1002 | `AccountDB.DevId` | str | inherits:parent_is_player_db |
| 1002 | `AccountDB.Exp` | int | inherits:parent_is_player_db |
| 1002 | `AccountDB.LastConnectTime` | str | inherits:parent_is_player_db |
| 1002 | `AccountDB.LastReturningDate` | str | inherits:parent_is_player_db |
| 1002 | `AccountDB.Level` | int | inherits:parent_is_player_db |
| 1002 | `AccountDB.LinkRewardDateDate` | str | inherits:parent_is_player_db |
| 1002 | `AccountDB.LobbyMode` | int | inherits:parent_is_player_db |
| 1002 | `AccountDB.Location` | str | inherits:parent_is_player_db |
| 1002 | `AccountDB.MemoryLobbyUniqueId` | int | inherits:parent_is_player_db |
| 1002 | `AccountDB.Nickname` | str | name:Nickname |
| 1002 | `AccountDB.PublisherAccountId` | int | inherits:parent_is_player_db |
| 1002 | `AccountDB.RepresentCharacterServerId` | int | name:RepresentCharacterServerId |
| 1002 | `AccountDB.RetentionDays` | int | inherits:parent_is_player_db |
| 1002 | `AccountDB.RoleId` | int | inherits:parent_is_player_db |
| 1002 | `AccountDB.ServerId` | int | name:ServerId |
| 1002 | `AccountDB.State` | int | inherits:parent_is_player_db |
| 1002 | `AccountDB.UnReadMailCount` | int | inherits:parent_is_player_db |
| 1002 | `AccountDB.VIPLevel` | int | inherits:parent_is_player_db |
| 1002 | `AccountRestrictionsDB.CallnameRestriction` | bool | inherits:parent_is_player_db |
| 1002 | `AccountRestrictionsDB.CommentRestriction` | bool | inherits:parent_is_player_db |
| 1002 | `AccountRestrictionsDB.NicknameRestriction` | bool | inherits:parent_is_player_db |
| 1002 | `AttendanceHistoryDBs[].ServerId` | int | name:ServerId |
| 1002 | `EncryptedUID` | str | name:EncryptedUID |
| 1002 | `OptionDB.ArenaIsAnonymous` | bool | inherits:parent_is_player_db |
| 1002 | `OptionDB.CafeAllowCopy` | int | inherits:parent_is_player_db |
| 1002 | `OptionDB.MainScenarioForceEnterSeriesId` | int | inherits:parent_is_player_db |
| 1002 | `RepurchasableMonthlyProductCountDBs` | null | name:*DBs |
| 1002 | `SessionKey.AccountServerId` | int | name:AccountServerId |
| 1002 | `SessionKey.MxToken` | str | name:MxToken |
| 1005 | `SessionKey.AccountServerId` | int | name:AccountServerId |
| 1005 | `SessionKey.MxToken` | str | name:MxToken |
| 1017 | `AccountCurrencySyncResponse.AccountCurrencyDB.AcademyLocationRankSum` | int | inherits:parent_is_player_db |
| 1017 | `AccountCurrencySyncResponse.AccountCurrencyDB.AccountLevel` | int | name:AccountLevel |
| 1017 | `AccountCurrencySyncResponse.AccountCurrencyDB.CurrencyDict{*}` | int | inherits:parent_is_player_db |
| 1017 | `AccountCurrencySyncResponse.AccountCurrencyDB.UpdateTimeDict{*}` | str | inherits:parent_is_player_db |
| 1017 | `AccountCurrencySyncResponse.SessionKey.AccountServerId` | int | name:AccountServerId |
| 1017 | `AccountCurrencySyncResponse.SessionKey.MxToken` | str | name:MxToken |
| 1017 | `ArenaLoginResponse.ArenaPlayerInfoDB.AllTimeRecord` | int | inherits:parent_is_player_db |
| 1017 | `ArenaLoginResponse.ArenaPlayerInfoDB.BattleEnterActiveTime` | str | inherits:parent_is_player_db |
| 1017 | `ArenaLoginResponse.ArenaPlayerInfoDB.CumulativeTimeReward` | int | inherits:parent_is_player_db |
| 1017 | `ArenaLoginResponse.ArenaPlayerInfoDB.CurrentRank` | int | inherits:parent_is_player_db |
| 1017 | `ArenaLoginResponse.ArenaPlayerInfoDB.CurrentSeasonId` | int | inherits:parent_is_player_db |
| 1017 | `ArenaLoginResponse.ArenaPlayerInfoDB.DailyRewardActiveTime` | str | inherits:parent_is_player_db |
| 1017 | `ArenaLoginResponse.ArenaPlayerInfoDB.PlayerGroupId` | int | inherits:parent_is_player_db |
| 1017 | `ArenaLoginResponse.ArenaPlayerInfoDB.SeasonRecord` | int | inherits:parent_is_player_db |
| 1017 | `ArenaLoginResponse.ArenaPlayerInfoDB.TimeRewardLastUpdateTime` | str | inherits:parent_is_player_db |
| 1017 | `ArenaLoginResponse.SessionKey.AccountServerId` | int | name:AccountServerId |
| 1017 | `ArenaLoginResponse.SessionKey.MxToken` | str | name:MxToken |
| 1017 | `AttachmentEmblemListResponse.EmblemDBs[].UniqueId` | int | name:UniqueId |
| 1017 | `AttachmentEmblemListResponse.SessionKey.AccountServerId` | int | name:AccountServerId |
| 1017 | `AttachmentEmblemListResponse.SessionKey.MxToken` | str | name:MxToken |
| 1017 | `AttachmentGetResponse.AccountAttachmentDB.AccountId` | int | name:AccountId |
| 1017 | `AttachmentGetResponse.AccountAttachmentDB.EmblemUniqueId` | int | inherits:parent_is_player_db |
| 1017 | `AttachmentGetResponse.SessionKey.AccountServerId` | int | name:AccountServerId |
| 1017 | `AttachmentGetResponse.SessionKey.MxToken` | str | name:MxToken |
| 1017 | `BillingPurchaseListByYostarResponse.SessionKey.AccountServerId` | int | name:AccountServerId |
| 1017 | `BillingPurchaseListByYostarResponse.SessionKey.MxToken` | str | name:MxToken |
| 1017 | `CafeGetInfoResponse.CafeDB` | null | name:*DB |
| 1017 | `CafeGetInfoResponse.CafeDBs[].AccountId` | int | name:AccountId |
| 1017 | `CafeGetInfoResponse.CafeDBs[].CafeDBId` | int | name:(?:DB|Db)Id$ |
| 1017 | `CafeGetInfoResponse.CafeDBs[].CafeVisitCharacterDBs{*}.LastInteractTime` | str | inherits:parent_is_player_db |
| 1017 | `CafeGetInfoResponse.CafeDBs[].CafeVisitCharacterDBs{*}.ServerId` | int | name:ServerId |
| 1017 | `CafeGetInfoResponse.CafeDBs[].CafeVisitCharacterDBs{*}.UniqueId` | int | name:UniqueId |
| 1017 | `CafeGetInfoResponse.CafeDBs[].FurnitureDBs[].CafeDBId` | int | name:(?:DB|Db)Id$ |
| 1017 | `CafeGetInfoResponse.CafeDBs[].FurnitureDBs[].ServerId` | int | name:ServerId |
| 1017 | `CafeGetInfoResponse.CafeDBs[].FurnitureDBs[].UniqueId` | int | name:UniqueId |
| 1017 | `CafeGetInfoResponse.CafeDBs[].LastUpdate` | str | name:LastUpdate |
| 1017 | `CafeGetInfoResponse.CafeDBs[].ProductionDB.AppliedDate` | str | inherits:parent_is_player_db |
| 1017 | `CafeGetInfoResponse.CafeDBs[].ProductionDB.CafeDBId` | int | name:(?:DB|Db)Id$ |
| 1017 | `CafeGetInfoResponse.CafeDBs[].ProductionDB.ComfortValue` | int | inherits:parent_is_player_db |
| 1017 | `CafeGetInfoResponse.CafeDBs[].ProductionDB.ProductionParcelInfos[].Amount` | int | inherits:parent_is_player_db |
| 1017 | `CafeGetInfoResponse.CafeDBs[].ProductionDB.ProductionParcelInfos[].Key.Id` | int | inherits:parent_is_player_db |
| 1017 | `CafeGetInfoResponse.CafeDBs[].ProductionDB.ProductionParcelInfos[].Key.Type` | int | inherits:parent_is_player_db |
| 1017 | `CafeGetInfoResponse.FurnitureDBs[].CafeDBId` | int | name:(?:DB|Db)Id$ |
| 1017 | `CafeGetInfoResponse.FurnitureDBs[].ServerId` | int | name:ServerId |
| 1017 | `CafeGetInfoResponse.FurnitureDBs[].UniqueId` | int | name:UniqueId |
| 1017 | `CafeGetInfoResponse.SessionKey.AccountServerId` | int | name:AccountServerId |
| 1017 | `CafeGetInfoResponse.SessionKey.MxToken` | str | name:MxToken |
| 1017 | `CampaignListResponse.CampaignChapterClearRewardHistoryDBs[].AccountServerId` | int | name:AccountServerId |
| 1017 | `CampaignListResponse.SessionKey.AccountServerId` | int | name:AccountServerId |
| 1017 | `CampaignListResponse.SessionKey.MxToken` | str | name:MxToken |
| 1017 | `CampaignListResponse.StageHistoryDBs[].AccountServerId` | int | name:AccountServerId |
| 1017 | `CharacterGearListResponse.SessionKey.AccountServerId` | int | name:AccountServerId |
| 1017 | `CharacterGearListResponse.SessionKey.MxToken` | str | name:MxToken |
| 1017 | `CharacterListResponse.CharacterDBs[].ServerId` | int | name:ServerId |
| 1017 | `CharacterListResponse.CharacterDBs[].UniqueId` | int | name:UniqueId |
| 1017 | `CharacterListResponse.SessionKey.AccountServerId` | int | name:AccountServerId |
| 1017 | `CharacterListResponse.SessionKey.MxToken` | str | name:MxToken |
| 1017 | `ClanLoginResponse.AccountClanDB.ClanChannelName` | str | inherits:parent_is_player_db |
| 1017 | `ClanLoginResponse.AccountClanDB.ClanDBId` | int | name:(?:DB|Db)Id$ |
| 1017 | `ClanLoginResponse.AccountClanDB.ClanJoinOption` | int | inherits:parent_is_player_db |
| 1017 | `ClanLoginResponse.AccountClanDB.ClanManagerCount` | int | inherits:parent_is_player_db |
| 1017 | `ClanLoginResponse.AccountClanDB.ClanMemberCount` | int | inherits:parent_is_player_db |
| 1017 | `ClanLoginResponse.AccountClanDB.ClanName` | str | inherits:parent_is_player_db |
| 1017 | `ClanLoginResponse.AccountClanDB.ClanNotice` | str | inherits:parent_is_player_db |
| 1017 | `ClanLoginResponse.AccountClanDB.ClanPresidentNickName` | str | inherits:parent_is_player_db |
| 1017 | `ClanLoginResponse.AccountClanDB.ClanPresidentRepresentCharacterCostumeId` | int | inherits:parent_is_player_db |
| 1017 | `ClanLoginResponse.AccountClanDB.ClanPresidentRepresentCharacterUniqueId` | int | inherits:parent_is_player_db |
| 1017 | `ClanLoginResponse.AccountClanMemberDB.AccountId` | int | name:AccountId |
| 1017 | `ClanLoginResponse.AccountClanMemberDB.AccountLevel` | int | name:AccountLevel |
| 1017 | `ClanLoginResponse.AccountClanMemberDB.AccountNickName` | str | inherits:parent_is_player_db |
| 1017 | `ClanLoginResponse.AccountClanMemberDB.AppliedDate` | str | inherits:parent_is_player_db |
| 1017 | `ClanLoginResponse.AccountClanMemberDB.AttachmentDB.AccountId` | int | name:AccountId |
| 1017 | `ClanLoginResponse.AccountClanMemberDB.AttachmentDB.EmblemUniqueId` | int | inherits:parent_is_player_db |
| 1017 | `ClanLoginResponse.AccountClanMemberDB.AttendanceCount` | int | inherits:parent_is_player_db |
| 1017 | `ClanLoginResponse.AccountClanMemberDB.ClanDBId` | int | name:(?:DB|Db)Id$ |
| 1017 | `ClanLoginResponse.AccountClanMemberDB.ClanSocialGrade` | int | inherits:parent_is_player_db |
| 1017 | `ClanLoginResponse.AccountClanMemberDB.GameLoginDate` | str | inherits:parent_is_player_db |
| 1017 | `ClanLoginResponse.AccountClanMemberDB.JoinDate` | str | inherits:parent_is_player_db |
| 1017 | `ClanLoginResponse.AccountClanMemberDB.LastLoginDate` | str | inherits:parent_is_player_db |
| 1017 | `ClanLoginResponse.AccountClanMemberDB.RepresentCharacterCostumeId` | int | inherits:parent_is_player_db |
| 1017 | `ClanLoginResponse.AccountClanMemberDB.RepresentCharacterUniqueId` | int | inherits:parent_is_player_db |
| 1017 | `ClanLoginResponse.AccountClanMemberDB.SocialGradeUpdateTime` | str | inherits:parent_is_player_db |
| 1017 | `ClanLoginResponse.SessionKey.AccountServerId` | int | name:AccountServerId |
| 1017 | `ClanLoginResponse.SessionKey.MxToken` | str | name:MxToken |
| 1017 | `ContentSweepMultiSweepPresetListResponse.SessionKey.AccountServerId` | int | name:AccountServerId |
| 1017 | `ContentSweepMultiSweepPresetListResponse.SessionKey.MxToken` | str | name:MxToken |
| 1017 | `CraftInfoListResponse.SessionKey.AccountServerId` | int | name:AccountServerId |
| 1017 | `CraftInfoListResponse.SessionKey.MxToken` | str | name:MxToken |
| 1017 | `EchelonListResponse.EchelonDBs[].AccountServerId` | int | name:AccountServerId |
| 1017 | `EchelonListResponse.EchelonDBs[].LeaderServerId` | int | name:ServerId$ |
| 1017 | `EchelonListResponse.EchelonDBs[].TSSInteractionServerId` | int | name:ServerId$ |
| 1017 | `EchelonListResponse.SessionKey.AccountServerId` | int | name:AccountServerId |
| 1017 | `EchelonListResponse.SessionKey.MxToken` | str | name:MxToken |
| 1017 | `EliminateRaidLoginResponse.SessionKey.AccountServerId` | int | name:AccountServerId |
| 1017 | `EliminateRaidLoginResponse.SessionKey.MxToken` | str | name:MxToken |
| 1017 | `EquipmentItemListResponse.EquipmentDBs[].BoundCharacterServerId` | int | name:BoundCharacterServerId |
| 1017 | `EquipmentItemListResponse.EquipmentDBs[].ServerId` | int | name:ServerId |
| 1017 | `EquipmentItemListResponse.EquipmentDBs[].UniqueId` | int | name:UniqueId |
| 1017 | `EquipmentItemListResponse.SessionKey.AccountServerId` | int | name:AccountServerId |
| 1017 | `EquipmentItemListResponse.SessionKey.MxToken` | str | name:MxToken |
| 1017 | `EventContentPermanentListResponse.SessionKey.AccountServerId` | int | name:AccountServerId |
| 1017 | `EventContentPermanentListResponse.SessionKey.MxToken` | str | name:MxToken |
| 1017 | `FriendCode` | str | name:FriendCode |
| 1017 | `FriendCount` | int | name:FriendCount |
| 1017 | `MemoryLobbyListResponse.MemoryLobbyDBs[].AccountServerId` | int | name:AccountServerId |
| 1017 | `MemoryLobbyListResponse.SessionKey.AccountServerId` | int | name:AccountServerId |
| 1017 | `MemoryLobbyListResponse.SessionKey.MxToken` | str | name:MxToken |
| 1017 | `MomoTalkOutLineResponse.MomoTalkOutLineDBs[].CharacterDBId` | int | name:(?:DB|Db)Id$ |
| 1017 | `MomoTalkOutLineResponse.SessionKey.AccountServerId` | int | name:AccountServerId |
| 1017 | `MomoTalkOutLineResponse.SessionKey.MxToken` | str | name:MxToken |
| 1017 | `MultiFloorRaidLoginResponse.SessionKey.AccountServerId` | int | name:AccountServerId |
| 1017 | `MultiFloorRaidLoginResponse.SessionKey.MxToken` | str | name:MxToken |
| 1017 | `MultiFloorRaidSyncResponse.MultiFloorRaidDBs` | null | name:*DBs |
| 1017 | `MultiFloorRaidSyncResponse.SessionKey.AccountServerId` | int | name:AccountServerId |
| 1017 | `MultiFloorRaidSyncResponse.SessionKey.MxToken` | str | name:MxToken |
| 1017 | `RaidLoginResponse.SessionKey.AccountServerId` | int | name:AccountServerId |
| 1017 | `RaidLoginResponse.SessionKey.MxToken` | str | name:MxToken |
| 1017 | `ScenarioListResponse.ScenarioGroupHistoryDBs[].AccountServerId` | int | name:AccountServerId |
| 1017 | `ScenarioListResponse.ScenarioHistoryDBs[].AccountServerId` | int | name:AccountServerId |
| 1017 | `ScenarioListResponse.SessionKey.AccountServerId` | int | name:AccountServerId |
| 1017 | `ScenarioListResponse.SessionKey.MxToken` | str | name:MxToken |
| 1017 | `SessionKey.AccountServerId` | int | name:AccountServerId |
| 1017 | `SessionKey.MxToken` | str | name:MxToken |
| 1017 | `ShopGachaRecruitListResponse.SessionKey.AccountServerId` | int | name:AccountServerId |
| 1017 | `ShopGachaRecruitListResponse.SessionKey.MxToken` | str | name:MxToken |
| 1017 | `StickerListResponse.SessionKey.AccountServerId` | int | name:AccountServerId |
| 1017 | `StickerListResponse.SessionKey.MxToken` | str | name:MxToken |
| 1017 | `StickerListResponse.StickerBookDB.AccountId` | int | name:AccountId |
| 1017 | `StickerListResponse.StickerBookDB.UnusedStickerDBs[].StickerUniqueId` | int | inherits:parent_is_player_db |
| 1017 | `StickerListResponse.StickerBookDB.UsedStickerDBs[]` | unknown | inherits:parent_is_player_db |
| 1017 | `TimeAttackDungeonLoginResponse.PreviousRoomDB` | null | name:*DB |
| 1017 | `TimeAttackDungeonLoginResponse.SessionKey.AccountServerId` | int | name:AccountServerId |
| 1017 | `TimeAttackDungeonLoginResponse.SessionKey.MxToken` | str | name:MxToken |
| 4000 | `ItemDBs[].ServerId` | int | name:ServerId |
| 4000 | `ItemDBs[].UniqueId` | int | name:UniqueId |
| 4000 | `SessionKey.AccountServerId` | int | name:AccountServerId |
| 4000 | `SessionKey.MxToken` | str | name:MxToken |
| 5000 | `EchelonDBs[].AccountServerId` | int | name:AccountServerId |
| 5000 | `EchelonDBs[].LeaderServerId` | int | name:ServerId$ |
| 5000 | `EchelonDBs[].TSSInteractionServerId` | int | name:ServerId$ |
| 5000 | `SessionKey.AccountServerId` | int | name:AccountServerId |
| 5000 | `SessionKey.MxToken` | str | name:MxToken |
| 5001 | `EchelonDB.AccountServerId` | int | name:AccountServerId |
| 5001 | `EchelonDB.CombatStyleIndex[]` | int | inherits:parent_is_player_db |
| 5001 | `EchelonDB.EchelonNumber` | int | inherits:parent_is_player_db |
| 5001 | `EchelonDB.EchelonType` | int | inherits:parent_is_player_db |
| 5001 | `EchelonDB.ExtensionType` | int | inherits:parent_is_player_db |
| 5001 | `EchelonDB.LeaderServerId` | int | name:ServerId$ |
| 5001 | `EchelonDB.MainSlotServerIds[]` | int | inherits:parent_is_player_db |
| 5001 | `EchelonDB.SkillCardMulliganCharacterIds[]` | int | inherits:parent_is_player_db |
| 5001 | `EchelonDB.SupportSlotServerIds[]` | int | inherits:parent_is_player_db |
| 5001 | `EchelonDB.TSSInteractionServerId` | int | name:ServerId$ |
| 5001 | `EchelonDB.UsingFlag` | int | inherits:parent_is_player_db |
| 5001 | `SessionKey.AccountServerId` | int | name:AccountServerId |
| 5001 | `SessionKey.MxToken` | str | name:MxToken |
| 6000 | `CampaignChapterClearRewardHistoryDBs[].AccountServerId` | int | name:AccountServerId |
| 6000 | `SessionKey.AccountServerId` | int | name:AccountServerId |
| 6000 | `SessionKey.MxToken` | str | name:MxToken |
| 6000 | `StageHistoryDBs[].AccountServerId` | int | name:AccountServerId |
| 6020 | `ParcelResultDB.AccountCurrencyDB.AcademyLocationRankSum` | int | inherits:parent_is_player_db |
| 6020 | `ParcelResultDB.AccountCurrencyDB.AccountLevel` | int | name:AccountLevel |
| 6020 | `ParcelResultDB.AccountCurrencyDB.CurrencyDict{*}` | int | inherits:parent_is_player_db |

(共 1054 条，此处仅列前 200)

## 6. 多次观测中值变过的字段 (values_vary, 不得硬编码)

- 共 430 个标量字段(仅统计观测次数>=2 的协议); 其中 230 个同时 is_player_data
- `is_player_data=false` 的那部分多为官方配置轮换/服务器时间, 生成器同样不能写死

| 协议号 | 路径 | 类型 | 证据 | 玩家数据 |
|---|---|---|---|---|
| 1002 | `AccountLimitedFlashSaleDBs[].ShopExcelId` | int | 9/15 次观测值不同 | 否 |
| 1002 | `AttendanceHistoryDBs[].AttendanceBookUniqueId` | int | 2/2 次观测值不同 | 否 |
| 1005 | `TutorialIds[]` | int | 9/21 次观测值不同 | 否 |
| 1017 | `AttachmentEmblemListResponse.EmblemDBs[].ReceiveDate` | str | 9/14 次观测值不同 | 否 |
| 1017 | `AttachmentEmblemListResponse.EmblemDBs[].UniqueId` | int | 9/14 次观测值不同 | 是 |
| 1017 | `BillingPurchaseListByYostarResponse.CountList[].PurchaseCount` | int | 2/4 次观测值不同 | 否 |
| 1017 | `BillingPurchaseListByYostarResponse.CountList[].ResetDate` | str | 4/4 次观测值不同 | 否 |
| 1017 | `BillingPurchaseListByYostarResponse.CountList[].ShopCashId` | int | 4/4 次观测值不同 | 否 |
| 1017 | `CafeGetInfoResponse.CafeDBs[].CafeDBId` | int | 2/2 次观测值不同 | 是 |
| 1017 | `CafeGetInfoResponse.CafeDBs[].CafeId` | int | 2/2 次观测值不同 | 否 |
| 1017 | `CafeGetInfoResponse.CafeDBs[].CafeRank` | int | 2/2 次观测值不同 | 否 |
| 1017 | `CafeGetInfoResponse.CafeDBs[].CafeVisitCharacterDBs{*}.UniqueId` | int | 7/7 次观测值不同 | 是 |
| 1017 | `CafeGetInfoResponse.CafeDBs[].FurnitureDBs[].CafeDBId` | int | 2/25 次观测值不同 | 是 |
| 1017 | `CafeGetInfoResponse.CafeDBs[].FurnitureDBs[].ItemDeploySequence` | int | 9/25 次观测值不同 | 否 |
| 1017 | `CafeGetInfoResponse.CafeDBs[].FurnitureDBs[].Location` | int | 3/25 次观测值不同 | 否 |
| 1017 | `CafeGetInfoResponse.CafeDBs[].FurnitureDBs[].PositionX` | number | 9/25 次观测值不同 | 否 |
| 1017 | `CafeGetInfoResponse.CafeDBs[].FurnitureDBs[].PositionY` | number | 9/25 次观测值不同 | 否 |
| 1017 | `CafeGetInfoResponse.CafeDBs[].FurnitureDBs[].ServerId` | int | 9/25 次观测值不同 | 是 |
| 1017 | `CafeGetInfoResponse.CafeDBs[].FurnitureDBs[].UniqueId` | int | 9/25 次观测值不同 | 是 |
| 1017 | `CafeGetInfoResponse.CafeDBs[].LastSummonDate` | str | 2/2 次观测值不同 | 否 |
| 1017 | `CafeGetInfoResponse.CafeDBs[].ProductionAppliedTime` | str | 2/2 次观测值不同 | 否 |
| 1017 | `CafeGetInfoResponse.CafeDBs[].ProductionDB.AppliedDate` | str | 2/2 次观测值不同 | 是 |
| 1017 | `CafeGetInfoResponse.CafeDBs[].ProductionDB.CafeDBId` | int | 2/2 次观测值不同 | 是 |
| 1017 | `CafeGetInfoResponse.CafeDBs[].ProductionDB.ComfortValue` | int | 2/2 次观测值不同 | 是 |
| 1017 | `CafeGetInfoResponse.CafeDBs[].ProductionDB.ProductionParcelInfos[].Amount` | int | 2/3 次观测值不同 | 是 |
| 1017 | `CafeGetInfoResponse.CafeDBs[].ProductionDB.ProductionParcelInfos[].Key.Id` | int | 2/3 次观测值不同 | 是 |
| 1017 | `CafeGetInfoResponse.FurnitureDBs[].CafeDBId` | int | 3/27 次观测值不同 | 是 |
| 1017 | `CafeGetInfoResponse.FurnitureDBs[].ItemDeploySequence` | int | 9/27 次观测值不同 | 否 |
| 1017 | `CafeGetInfoResponse.FurnitureDBs[].Location` | int | 4/27 次观测值不同 | 否 |
| 1017 | `CafeGetInfoResponse.FurnitureDBs[].PositionX` | number | 9/27 次观测值不同 | 否 |
| 1017 | `CafeGetInfoResponse.FurnitureDBs[].PositionY` | number | 9/27 次观测值不同 | 否 |
| 1017 | `CafeGetInfoResponse.FurnitureDBs[].ServerId` | int | 9/27 次观测值不同 | 是 |
| 1017 | `CafeGetInfoResponse.FurnitureDBs[].UniqueId` | int | 9/27 次观测值不同 | 是 |
| 1017 | `CampaignListResponse.CampaignChapterClearRewardHistoryDBs[].ChapterUniqueId` | int | 9/12 次观测值不同 | 否 |
| 1017 | `CampaignListResponse.CampaignChapterClearRewardHistoryDBs[].ReceiveDate` | str | 9/12 次观测值不同 | 否 |
| 1017 | `CampaignListResponse.StageHistoryDBs[].ChapterUniqueId` | int | 9/90 次观测值不同 | 否 |
| 1017 | `CampaignListResponse.StageHistoryDBs[].ClearTurnRecord` | int | 4/90 次观测值不同 | 否 |
| 1017 | `CampaignListResponse.StageHistoryDBs[].FirstClearRewardReceive` | str | 9/90 次观测值不同 | 否 |
| 1017 | `CampaignListResponse.StageHistoryDBs[].LastPlay` | str | 9/90 次观测值不同 | 否 |
| 1017 | `CampaignListResponse.StageHistoryDBs[].StageUniqueId` | int | 9/90 次观测值不同 | 否 |
| 1017 | `CampaignListResponse.StageHistoryDBs[].StarRewardReceive` | str | 9/90 次观测值不同 | 否 |
| 1017 | `CampaignListResponse.StageHistoryDBs[].TacticClearCountWithRankSRecord` | int | 2/9 次观测值不同 | 否 |
| 1017 | `CampaignListResponse.StageHistoryDBs[].TodayPlayCount` | int | 3/90 次观测值不同 | 否 |
| 1017 | `CharacterListResponse.CharacterDBs[].EquipmentServerIds[]` | int | 9/138 次观测值不同 | 否 |
| 1017 | `CharacterListResponse.CharacterDBs[].Exp` | int | 7/46 次观测值不同 | 否 |
| 1017 | `CharacterListResponse.CharacterDBs[].FavorExp` | int | 2/46 次观测值不同 | 否 |
| 1017 | `CharacterListResponse.CharacterDBs[].FavorRank` | int | 2/46 次观测值不同 | 否 |
| 1017 | `CharacterListResponse.CharacterDBs[].Level` | int | 5/46 次观测值不同 | 否 |
| 1017 | `CharacterListResponse.CharacterDBs[].ServerId` | int | 9/46 次观测值不同 | 是 |
| 1017 | `CharacterListResponse.CharacterDBs[].StarGrade` | int | 3/46 次观测值不同 | 否 |
| 1017 | `CharacterListResponse.CharacterDBs[].UniqueId` | int | 9/46 次观测值不同 | 是 |
| 1017 | `ContentSweepMultiSweepPresetListResponse.MultiSweepPresetDBs[].StageIds[]` | int | 9/10 次观测值不同 | 否 |
| 1017 | `EchelonListResponse.EchelonDBs[].EchelonNumber` | int | 3/8 次观测值不同 | 否 |
| 1017 | `EchelonListResponse.EchelonDBs[].EchelonType` | int | 6/8 次观测值不同 | 否 |
| 1017 | `EchelonListResponse.EchelonDBs[].LeaderServerId` | int | 6/8 次观测值不同 | 是 |
| 1017 | `EchelonListResponse.EchelonDBs[].MainSlotServerIds[]` | int | 9/32 次观测值不同 | 否 |
| 1017 | `EchelonListResponse.EchelonDBs[].SupportSlotServerIds[]` | int | 5/16 次观测值不同 | 否 |
| 1017 | `EquipmentItemListResponse.EquipmentDBs[].BoundCharacterServerId` | int | 9/30 次观测值不同 | 是 |
| 1017 | `EquipmentItemListResponse.EquipmentDBs[].ServerId` | int | 9/84 次观测值不同 | 是 |
| 1017 | `EquipmentItemListResponse.EquipmentDBs[].StackCount` | int | 9/84 次观测值不同 | 否 |
| 1017 | `EquipmentItemListResponse.EquipmentDBs[].UniqueId` | int | 9/84 次观测值不同 | 是 |
| 1017 | `EventContentPermanentListResponse.PermanentDBs[].EventContentId` | int | 9/22 次观测值不同 | 否 |
| 1017 | `ScenarioListResponse.ScenarioGroupHistoryDBs[].ClearDateTime` | str | 9/21 次观测值不同 | 否 |
| 1017 | `ScenarioListResponse.ScenarioGroupHistoryDBs[].EventContentId` | int | 2/21 次观测值不同 | 否 |
| 1017 | `ScenarioListResponse.ScenarioGroupHistoryDBs[].ScenarioGroupUniqueId` | int | 9/21 次观测值不同 | 否 |
| 1017 | `ScenarioListResponse.ScenarioGroupHistoryDBs[].ScenarioType` | int | 8/21 次观测值不同 | 否 |
| 1017 | `ScenarioListResponse.ScenarioHistoryDBs[].ClearDateTime` | str | 9/191 次观测值不同 | 否 |
| 1017 | `ScenarioListResponse.ScenarioHistoryDBs[].ScenarioUniqueId` | int | 9/191 次观测值不同 | 否 |
| 1017 | `ShopGachaRecruitListResponse.ShopRecruits[].Id` | int | 9/529 次观测值不同 | 否 |
| 1017 | `ShopGachaRecruitListResponse.ShopRecruits[].SalesEndDate` | str | 9/529 次观测值不同 | 否 |
| 1017 | `ShopGachaRecruitListResponse.ShopRecruits[].SalesStartDate` | str | 9/529 次观测值不同 | 否 |
| 1017 | `StickerListResponse.StickerBookDB.UnusedStickerDBs[].StickerUniqueId` | int | 9/20 次观测值不同 | 是 |
| 4000 | `ItemDBs[].ServerId` | int | 9/134 次观测值不同 | 是 |
| 4000 | `ItemDBs[].StackCount` | int | 9/134 次观测值不同 | 否 |
| 4000 | `ItemDBs[].UniqueId` | int | 9/134 次观测值不同 | 是 |
| 5000 | `EchelonDBs[].EchelonNumber` | int | 3/32 次观测值不同 | 否 |
| 5000 | `EchelonDBs[].EchelonType` | int | 6/32 次观测值不同 | 否 |
| 5000 | `EchelonDBs[].LeaderServerId` | int | 6/32 次观测值不同 | 是 |
| 5000 | `EchelonDBs[].MainSlotServerIds[]` | int | 9/128 次观测值不同 | 否 |
| 5000 | `EchelonDBs[].SupportSlotServerIds[]` | int | 5/64 次观测值不同 | 否 |
| 5000 | `RequestId` | str | 4/4 次观测值不同 | 否 |
| 5000 | `ServerTimeTicks` | int | 4/4 次观测值不同 | 否 |
| 5001 | `EchelonDB.EchelonType` | int | 2/2 次观测值不同 | 是 |
| 5001 | `EchelonDB.LeaderServerId` | int | 2/2 次观测值不同 | 是 |
| 5001 | `EchelonDB.MainSlotServerIds[]` | int | 6/8 次观测值不同 | 是 |
| 5001 | `EchelonDB.SupportSlotServerIds[]` | int | 3/4 次观测值不同 | 是 |
| 5001 | `RequestId` | str | 2/2 次观测值不同 | 否 |
| 5001 | `ServerTimeTicks` | int | 2/2 次观测值不同 | 否 |
| 6000 | `CampaignChapterClearRewardHistoryDBs[].ChapterUniqueId` | int | 9/12 次观测值不同 | 否 |
| 6000 | `CampaignChapterClearRewardHistoryDBs[].ReceiveDate` | str | 9/12 次观测值不同 | 否 |
| 6000 | `StageHistoryDBs[].ChapterUniqueId` | int | 9/90 次观测值不同 | 否 |
| 6000 | `StageHistoryDBs[].ClearTurnRecord` | int | 4/90 次观测值不同 | 否 |
| 6000 | `StageHistoryDBs[].FirstClearRewardReceive` | str | 9/90 次观测值不同 | 否 |
| 6000 | `StageHistoryDBs[].LastPlay` | str | 9/90 次观测值不同 | 否 |
| 6000 | `StageHistoryDBs[].StageUniqueId` | int | 9/90 次观测值不同 | 否 |
| 6000 | `StageHistoryDBs[].StarRewardReceive` | str | 9/90 次观测值不同 | 否 |
| 6000 | `StageHistoryDBs[].TacticClearCountWithRankSRecord` | int | 2/9 次观测值不同 | 否 |
| 6000 | `StageHistoryDBs[].TodayPlayCount` | int | 3/90 次观测值不同 | 否 |
| 6021 | `MissionProgressDBs[].Category` | int | 4/31 次观测值不同 | 否 |
| 6021 | `MissionProgressDBs[].MissionUniqueId` | int | 9/31 次观测值不同 | 否 |
| 6021 | `MissionProgressDBs[].StartDate` | str | 5/31 次观测值不同 | 否 |
| 6021 | `ParcelResultDB.DisplaySequence[].Amount` | int | 2/2 次观测值不同 | 是 |
| 6021 | `ParcelResultDB.DisplaySequence[].Key.Id` | int | 2/2 次观测值不同 | 是 |
| 6021 | `ParcelResultDB.DisplaySequence[].Key.Type` | int | 2/2 次观测值不同 | 是 |
| 7000 | `MailDBs[].Comment` | str | 2/2 次观测值不同 | 是 |
| 7000 | `MailDBs[].ExpireDate` | str | 2/2 次观测值不同 | 否 |
| 7000 | `MailDBs[].ParcelInfos[].Amount` | int | 2/2 次观测值不同 | 否 |
| 7000 | `MailDBs[].SendDate` | str | 2/2 次观测值不同 | 否 |
| 7000 | `MailDBs[].Sender` | str | 2/2 次观测值不同 | 否 |
| 7000 | `MailDBs[].ServerId` | int | 2/2 次观测值不同 | 是 |
| 7000 | `MailDBs[].Type` | int | 2/2 次观测值不同 | 否 |
| 7001 | `Count` | int | 2/9 次观测值不同 | 否 |
| 7001 | `RequestId` | str | 9/9 次观测值不同 | 否 |
| 7001 | `ServerTimeTicks` | int | 9/9 次观测值不同 | 否 |
| 8000 | `ClearedOriginalMissionIds[]` | int | 9/372 次观测值不同 | 否 |
| 8000 | `MissionHistoryUniqueIds[]` | int | 9/372 次观测值不同 | 否 |
| 8000 | `ProgressDBs[].Category` | int | 9/1314 次观测值不同 | 否 |
| 8000 | `ProgressDBs[].MissionUniqueId` | int | 9/1314 次观测值不同 | 否 |
| 8000 | `ProgressDBs[].StartDate` | str | 9/1314 次观测值不同 | 否 |
| 8000 | `RequestId` | str | 3/3 次观测值不同 | 否 |

(共 430 条，此处仅列前 120，完整见 official_spec.json -> varying_fields)
