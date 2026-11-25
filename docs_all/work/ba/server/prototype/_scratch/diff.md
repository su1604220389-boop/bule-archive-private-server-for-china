### 1) 结构键集合比对（我们 vs 官方）
- 1017: 顶层键序与官方完全一致；键集合差异 2 处
    [official_only] $.CafeGetInfoResponse.CafeDBs[0].CafeVisitCharacterDBs: ['10044', '10064', '26012', '26015']
    [official_only] $.MomoTalkOutLineResponse.FavorScheduleRecords: ['13010']
    顶层键数 ours=35 official=35
- 24000: 顶层键序与官方完全一致；键集合差异 0 处
    → 逐层递归比完：**没有多余键、没有缺失键**
    顶层键数 ours=7 official=7

### 2) 计数比对（数据差异）
| 协议 | 字段 | 官方32级号 | 本原型新号 | 说明 |
|---|---|---|---|---|
| 1017 | `CharacterListResponse.CharacterDBs` | 46 | 4 | 4 个初始角色 vs 官方 46 个 |
| 1017 | `EquipmentItemListResponse.EquipmentDBs` | 84 | 0 | 新号无装备 |
| 1017 | `CharacterGearListResponse.GearDBs` | 0 | 0 |  |
| 1017 | `ItemListResponse` | null | null | spec 记为 type=null |
| 1017 | `EchelonListResponse.EchelonDBs` | 8 | 1 | 新号只有 1 条初始编队 |
| 1017 | `CafeGetInfoResponse.CafeDBs` | 2 | 2 | 新号 2 个咖啡厅 |
| 1017 | `CafeGetInfoResponse.FurnitureDBs` | 27 | 22 | 新号 11×2；官方 27 = 14+11+2 件未摆放 |
| 1017 | `CafeDBs[1].FurnitureDBs` | 11 | 11 | 官方 cafe2 也是 11 件（初始态） |
| 1017 | `CurrencyDict 键数` | 29 | 29 | 都是 1..29 全 29 键 |
| 1017 | `CurrencyDict 金额合计` | 28263233 | 10774 | 官方玩过 32 级；新号只发 DefaultParcel 的初始量 |
| 1017 | `UpdateTimeDict 键数` | 19 | 19 |  |
| 1017 | `ScenarioListResponse.ScenarioHistoryDBs` | 191 | 0 | 剧情进度 191 → 0 |
| 1017 | `ScenarioListResponse.ScenarioGroupHistoryDBs` | 21 | 0 | 21 → 0 |
| 1017 | `CampaignListResponse.StageHistoryDBs` | 90 | 0 | 关卡 90 → 0 |
| 1017 | `CampaignChapterClearRewardHistoryDBs` | 12 | 0 | 12 → 0 |
| 1017 | `ShopGachaRecruitListResponse.ShopRecruits` | 529 | 529 | 内容目录：两边都 529 |
| 1017 | `AttachmentEmblemListResponse.EmblemDBs` | 14 | 5 | 官方后面又拿了 9 个 |
| 1017 | `EventContentPermanentListResponse.PermanentDBs` | 22 | 0 | 未找到目录来源 → 空 |
| 1017 | `StickerListResponse.UnusedStickerDBs` | 20 | 0 | 未找到 → 空 |
| 1017 | `BillingPurchaseListByYostar.CountList` | 4 | 0 | 新号没氪金计数 |
| 1017 | `MemoryLobbyListResponse.MemoryLobbyDBs` | 1 | 1 |  |
| 1017 | `MomoTalkOutLineResponse.MomoTalkOutLineDBs` | 1 | 0 | 未找到初始规则 → 空 |
| 1017 | `PickupFirstGetHistoryDBs` | 1 | 0 |  |
| 1017 | `AccountLevelRewardIds` | 1 | 0 | 按 Level<=1 算：[]；官方 Level32 → [1] |
| 1017 | `FriendCount` | 0 | 0 |  |
| 24000 | `AcademyDB.ZoneVisitCharacterDBs 键数` | 71 | 71 | 71 = 国服 9 个 location 的全部 zone |
| 24000 | `ZoneVisitCharacterDBs 角色条目合计` | 138 | 0 | 官方 276 条访问记录 → 新号 0 |
| 24000 | `AcademyLocationDBs` | 9 | 1 | 9 → 1（未找到初始条数规则） |
| 24000 | `AcademyLocationDBs Rank 之和` | 14 | 1 |  |
| 24000 | `AcademyDB.ZoneScheduleGroupRecords 键数` | 0 | 0 | 都是 {} |

### 3) 文件字节数
- 24000.json: 1473 bytes
- 1017.json: 106733 bytes
- 01_24000_api_academy_getinfo.response.json (官方 24000): 39364 bytes
- 02_1017_api_account_loginsync.response.json (官方 1017): 502979 bytes
- 官方 4000 Item_List: 35108 bytes, ItemDBs=134 条

### 4) 官方 1017 各子数组条数（真实账号的『进度厚度』）
- CafeGetInfoResponse: SessionKey{2键}, CafeDBs=2, FurnitureDBs=27
- AccountCurrencySyncResponse: SessionKey{2键}, AccountCurrencyDB{4键}, ExpiredCurrency{0键}
- CharacterListResponse: SessionKey{2键}, CharacterDBs=46, TSSCharacterDBs=0, WeaponDBs=0
- EquipmentItemListResponse: SessionKey{2键}, EquipmentDBs=84
- CharacterGearListResponse: SessionKey{2键}, GearDBs=0
- EchelonListResponse: SessionKey{2键}, EchelonDBs=8
- MemoryLobbyListResponse: SessionKey{2键}, MemoryLobbyDBs=1
- CampaignListResponse: SessionKey{2键}, CampaignChapterClearRewardHistoryDBs=12, StageHistoryDBs=90
- ArenaLoginResponse: SessionKey{2键}, ArenaPlayerInfoDB{9键}
- RaidLoginResponse: SessionKey{2键}
- CraftInfoListResponse: SessionKey{2键}, CraftInfos=0, ShiftingCraftInfos=0, PresetSlotDBs=0
- ClanLoginResponse: SessionKey{2键}, AccountClanDB{10键}, AccountClanMemberDB{14键}, ClanAssistSlotDBs=0
- MomoTalkOutLineResponse: SessionKey{2键}, MomoTalkOutLineDBs=1, FavorScheduleRecords{1键}
- ScenarioListResponse: SessionKey{2键}, ScenarioHistoryDBs=191, ScenarioGroupHistoryDBs=21, ScenarioCollectionDBs=0
- ShopGachaRecruitListResponse: SessionKey{2键}, ShopRecruits=529, ShopFreeRecruitHistoryDBs=0
- TimeAttackDungeonLoginResponse: SessionKey{2键}
- BillingPurchaseListByYostarResponse: SessionKey{2键}, CountList=4, OrderList=0, MonthlyProductList=0
- EventContentPermanentListResponse: SessionKey{2键}, PermanentDBs=22
- AttachmentEmblemListResponse: SessionKey{2键}, EmblemDBs=14
- AttachmentGetResponse: SessionKey{2键}, AccountAttachmentDB{2键}
- ContentSweepMultiSweepPresetListResponse: SessionKey{2键}, MultiSweepPresetDBs=1
- EliminateRaidLoginResponse: SessionKey{2键}, ReceiveLimitedRewardIds=0, SweepPointByRaidUniqueId{0键}
- StickerListResponse: SessionKey{2键}, StickerBookDB{3键}
- MultiFloorRaidSyncResponse: SessionKey{2键}
- MultiFloorRaidLoginResponse: SessionKey{2键}
