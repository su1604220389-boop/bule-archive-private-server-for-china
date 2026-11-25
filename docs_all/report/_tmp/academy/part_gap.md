### P0 号段逐条清单（59 条）


#### 01000 段（14 条）

| 协议号 | 协议 | Response DTO | metadata 字段数 |
| ---: | --- | --- | ---: |
| 1000 | `Account_Create` | `AccountCreateResponse` | 0 |
| 1004 | `Account_SetRepresentCharacterAndComment` | `AccountSetRepresentCharacterAndCommentResponse` | 2 |
| 1005 | `Account_GetTutorial` | `AccountGetTutorialResponse` | 1 |
| 1006 | `Account_SetTutorial` | `AccountSetTutorialResponse` | 0 |
| 1007 | `Account_PassCheck` | `AccountPassCheckResponse` | 4 |
| 1009 | `Account_CheckYostar` | `AccountCheckYostarResponse` | 7 |
| 1011 | `Account_BirthDay` | `AccountBirthDayResponse` | 1 |
| 1012 | `Account_Auth2` | `AccountAuth2Response` | 0 |
| 1013 | `Account_LinkReward` | `AccountLinkRewardResponse` | 0 |
| 1014 | `Account_ReportXignCodeCheater` | `AccountReportXignCodeCheaterResponse` | 0 |
| 1015 | `Account_DismissRepurchasablePopup` | `AccountDismissRepurchasablePopupResponse` | 0 |
| 1016 | `Account_InvalidateToken` | `AccountInvalidateTokenResponse` | 0 |
| 1018 | `Account_Reset` | `AccountResetResponse` | 0 |
| 1019 | `Account_RequestBirthdayMail` | `AccountRequestBirthdayMailResponse` | 0 |

#### 02000 段（10 条）

| 协议号 | 协议 | Response DTO | metadata 字段数 |
| ---: | --- | --- | ---: |
| 2001 | `Character_Transcendence` | `CharacterTranscendenceResponse` | 2 |
| 2002 | `Character_ExpGrowth` | `CharacterExpGrowthResponse` | 3 |
| 2003 | `Character_FavorGrowth` | `CharacterFavorGrowthResponse` | 3 |
| 2005 | `Character_UnlockWeapon` | `CharacterUnlockWeaponResponse` | 1 |
| 2006 | `Character_WeaponExpGrowth` | `CharacterWeaponExpGrowthResponse` | 1 |
| 2007 | `Character_WeaponTranscendence` | `CharacterWeaponTranscendenceResponse` | 1 |
| 2008 | `Character_SetFavorites` | `CharacterSetFavoritesResponse` | 1 |
| 2009 | `Character_SetCostume` | `CharacterSetCostumeResponse` | 2 |
| 2010 | `Character_BatchSkillLevelUpdate` | `CharacterBatchSkillLevelUpdateResponse` | 2 |
| 2011 | `Character_PotentialGrowth` | `CharacterPotentialGrowthResponse` | 2 |

#### 03000 段（1 条）

| 协议号 | 协议 | Response DTO | metadata 字段数 |
| ---: | --- | --- | ---: |
| 3006 | `Equipment_BatchGrowth` | `EquipmentBatchGrowthResponse` | 4 |

#### 04000 段（6 条）

| 协议号 | 协议 | Response DTO | metadata 字段数 |
| ---: | --- | --- | ---: |
| 4001 | `Item_Sell` | `ItemSellResponse` | 1 |
| 4002 | `Item_Consume` | `ItemConsumeResponse` | 2 |
| 4003 | `Item_Lock` | `ItemLockResponse` | 1 |
| 4004 | `Item_BulkConsume` | `ItemBulkConsumeResponse` | 2 |
| 4005 | `Item_SelectTicket` | `ItemSelectTicketResponse` | 2 |
| 4006 | `Item_AutoSynth` | `ItemAutoSynthResponse` | 1 |

#### 05000 段（3 条）

| 协议号 | 协议 | Response DTO | metadata 字段数 |
| ---: | --- | --- | ---: |
| 5002 | `Echelon_PresetList` | `EchelonPresetListResponse` | 1 |
| 5003 | `Echelon_PresetSave` | `EchelonPresetSaveResponse` | 1 |
| 5004 | `Echelon_PresetGroupRename` | `EchelonPresetGroupRenameResponse` | 1 |

#### 12000 段（3 条）

| 协议号 | 协议 | Response DTO | metadata 字段数 |
| ---: | --- | --- | ---: |
| 12001 | `MemoryLobby_SetMain` | `MemoryLobbySetMainResponse` | 1 |
| 12002 | `MemoryLobby_UpdateLobbyMode` | `MemoryLobbyUpdateLobbyModeResponse` | 0 |
| 12003 | `MemoryLobby_Interact` | `MemoryLobbyInteractResponse` | 0 |

#### 20000 段（22 条）

| 协议号 | 协议 | Response DTO | metadata 字段数 |
| ---: | --- | --- | ---: |
| 20001 | `Cafe_Ack` | `CafeAckResponse` | 1 |
| 20002 | `Cafe_Deploy` | `CafeDeployFurnitureResponse` | 3 |
| 20003 | `Cafe_Relocate` | `CafeRelocateFurnitureResponse` | 2 |
| 20004 | `Cafe_Remove` | `CafeRemoveFurnitureResponse` | 2 |
| 20005 | `Cafe_RemoveAll` | `CafeRemoveAllFurnitureResponse` | 2 |
| 20006 | `Cafe_Interact` | `CafeInteractWithCharacterResponse` | 3 |
| 20007 | `Cafe_ListPreset` | `CafeListPresetResponse` | 2 |
| 20008 | `Cafe_RenamePreset` | `CafeRenamePresetResponse` | 0 |
| 20009 | `Cafe_ClearPreset` | `CafeClearPresetResponse` | 0 |
| 20010 | `Cafe_UpdatePresetFurniture` | `CafeUpdatePresetFurnitureResponse` | 0 |
| 20011 | `Cafe_ApplyPreset` | `CafeApplyPresetResponse` | 2 |
| 20012 | `Cafe_RankUp` | `CafeRankUpResponse` | 3 |
| 20013 | `Cafe_ReceiveCurrency` | `CafeReceiveCurrencyResponse` | 3 |
| 20014 | `Cafe_GiveGift` | `CafeGiveGiftResponse` | 2 |
| 20015 | `Cafe_SummonCharacter` | `CafeSummonCharacterResponse` | 2 |
| 20016 | `Cafe_TrophyHistory` | `CafeTrophyHistoryResponse` | 1 |
| 20017 | `Cafe_ApplyTemplate` | `CafeApplyTemplateResponse` | 2 |
| 20018 | `Cafe_Open` | `CafeOpenResponse` | 2 |
| 20019 | `Cafe_Travel` | `CafeTravelResponse` | 3 |
| 20020 | `Cafe_SummonCharacterTicketUse` | `CafeSummonCharacterTicketUseResponse` | 3 |
| 20021 | `Cafe_PresetDetail` | `CafePresetDetailResponse` | 1 |
| 20022 | `Cafe_UpdateCopyPresetFurniture` | `CafeUpdateCopyPresetFurnitureResponse` | 0 |

### P2 号段汇总（351 条）

| 号段 | 缺口数 | 号段 | 缺口数 | 号段 | 缺口数 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 06000 | 21 || 07000 | 5 || 08000 | 3 |
| 09000 | 1 || 10000 | 16 || 11000 | 1 |
| 15000 | 3 || 16000 | 1 || 17000 | 19 |
| 18000 | 2 || 19000 | 20 || 21000 | 15 |
| 22000 | 14 || 23000 | 4 || 25000 | 1 |
| 26000 | 2 || 27000 | 3 || 28000 | 20 |
| 29000 | 3 || 30000 | 53 || 31000 | 1 |
| 33000 | 3 || 34000 | 2 || 35000 | 42 |
| 36000 | 1 || 37000 | 2 || 38000 | 4 |
| 39000 | 6 || 40000 | 6 || 41000 | 1 |
| 42000 | 18 || 43000 | 13 || 44000 | 2 |
| 45000 | 9 || 46000 | 2 || 47000 | 2 |
| 48000 | 7 || 49000 | 3 || 50000 | 2 |
| 51000 | 7 || 52000 | 1 || 53000 | 1 |
| 54000 | 4 || 90000 | 3 || Unknown | 2 |
