# 65 · 进大厅协议 DTO 字段表（国服《蔚蓝档案》）

> 生成物，勿手改：`work/ba/proto/make_report.py` 从 `work/ba/proto/dto_schema.json` 生成。
> 数据源：`report/_tmp/patch/md_deob.bin`（国服 metadata，38,426,024 B）+ `report/_tmp/shittim/src/...NetworkProtocol.cs`（C# 声明，仅用于类型交叉校验）。
> 全程本地只读，未连手机、未连服务器、未碰 `libtprt.so`。

## §0 一句话结论

**已从国服 metadata 导出 112 个 DTO / 495 个字段，`unknown` 为 0，`gen_default.py --check-all` 112/112 通过**；`AccountNicknameResponse`（1 字段）→ `AccountDB`（22 字段）链路已可直接产出合法 JSON，P0 的 `Account_CallName`(1010)、`Account_LoginSync`(1019) 及其 31 个子 DTO 也已全量导出（附录 A）。

| 指标 | 值 |
|---|---|
| DTO 数 | 112 |
| 字段总数 | 495 |
| 字段类型分布 | prim 254 / list 84 / object 50 / datetime 48 / enum 29 / nullable 18 / dict 12 |
| 置信度分布 | 高 480 / 中 7 / 低 8 |
| 已挂到协议号的 DTO | 42 |
| 生成器自检 | `--audit` 0 问题（空名/重名/unknown 全 0）+ `--check-all` 0 失败 |

现成可用：`work/ba/proto/out/AccountNicknameResponse.json`（`Account_LoginSync` 等其它响应用生成器现取）。

用法：
```
python work\ba\proto\gen_default.py AccountNicknameResponse --protocol 1001
python work\ba\proto\gen_default.py AccountNicknameResponse --protocol 1001 \
       --set AccountDB.Nickname=一一一 --set AccountDB.CallName=一一一 --out out.json
python work\ba\proto\gen_default.py --check-all
python work\ba\proto\gen_default.py --audit
python work\ba\proto\gen_default.py --selftest
```

## §1 DTO 字段表

### 1.1 P0：取昵称 → 进大厅这一路必用

### **AccountNicknameRequest**  ·  协议 1001  ·  1 字段  ·  base=RequestPacket

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `Nickname` | `string` |  | 高 |

### **AccountNicknameResponse**  ·  协议 1001  ·  1 字段  ·  base=ResponsePacket

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `AccountDB` | `AccountDB` | 对象 | 高 |

引用：`AccountDB`

### **AccountCallNameRequest**  ·  协议 1010  ·  1 字段  ·  base=RequestPacket

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `CallName` | `string` |  | 高 |

### **AccountCallNameResponse**  ·  协议 1010  ·  1 字段  ·  base=ResponsePacket

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `AccountDB` | `AccountDB` | 对象 | 高 |

引用：`AccountDB`

### **AccountLoginSyncRequest**  ·  协议 1019  ·  2 字段  ·  base=RequestPacket

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `SyncProtocols` | `List<Protocol>` | 集合 | 高 |
| 2 | `SkillCutInOption` | `string` |  | 高 |

**AccountLoginSyncResponse（1019，31 字段）** 的主载体 `Responses` 与 30 个子回包见 **附录 A**；`Responses` 的类型是有争议的一项，见 §3。

### 1.2 被反复引用的数据模型

### **AccountDB**  ·  协议号未提取到  ·  22 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `ServerId` | `long` |  | 高 |
| 2 | `Nickname` | `string` |  | 高 |
| 3 | `CallName` | `string` |  | 高 |
| 4 | `DevId` | `string` |  | 高 |
| 5 | `State` | `AccountState` | 枚举 | 高 |
| 6 | `Level` | `int` |  | 高 |
| 7 | `Exp` | `long` |  | 高 |
| 8 | `Comment` | `string` |  | 高 |
| 9 | `LobbyMode` | `int` |  | 高 |
| 10 | `RepresentCharacterServerId` | `long` |  | 高 |
| 11 | `MemoryLobbyUniqueId` | `long` |  | 高 |
| 12 | `LastConnectTime` | `DateTime` | DateTime | 高 |
| 13 | `BirthDay` | `DateTime` | DateTime | 高 |
| 14 | `CallNameUpdateTime` | `DateTime` | DateTime | 高 |
| 15 | `PublisherAccountId` | `long` |  | 高 |
| 16 | `RetentionDays` | `Nullable<int>` | 可空 | 高 |
| 17 | `VIPLevel` | `Nullable<int>` | 可空 | 高 |
| 18 | `CreateDate` | `DateTime` | DateTime | 高 |
| 19 | `UnReadMailCount` | `Nullable<int>` | 可空 | 高 |
| 20 | `LinkRewardDate` | `Nullable<DateTime>` | 可空 | 高 |
| 21 | `LastReturningDate` | `Nullable<DateTime>` | 可空 | 高 |
| 22 | `Location` | `string` |  | 高 |

### **OptionDB**  ·  协议号未提取到  ·  3 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `ArenaIsAnonymous` | `bool` |  | 高 |
| 2 | `CafeAllowCopy` | `CafeAllowCopyPreset` | 枚举 | 高 |
| 3 | `MainScenarioForceEnterSeriesId` | `int` |  | 高 |

### **AccountRestrictionsDB**  ·  协议号未提取到  ·  3 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `NicknameRestriction` | `bool` |  | 高 |
| 2 | `CommentRestriction` | `bool` |  | 高 |
| 3 | `CallnameRestriction` | `bool` |  | 高 |

### **FunctionClose**  ·  协议号未提取到  ·  6 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `Arena` | `int` |  | 高 |
| 2 | `CloseAutoBan` | `int` |  | 高 |
| 3 | `OpenGift` | `int` |  | 高 |
| 4 | `Raid` | `int` |  | 高 |
| 5 | `ShowCharacterCN` | `int` |  | 高 |
| 6 | `ShowCharacterChange` | `int` |  | 高 |

### **AccountCurrencyDB**  ·  协议号未提取到  ·  4 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `AccountLevel` | `long` |  | 高 |
| 2 | `AcademyLocationRankSum` | `long` |  | 高 |
| 3 | `CurrencyDict` | `Dictionary<CurrencyTypes, long>` | 字典 | 高 |
| 4 | `UpdateTimeDict` | `Dictionary<CurrencyTypes,DateTime>` | 字典 | 高 |

### **CharacterDB**  ·  协议号未提取到  ·  15 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `ServerId` | `long` |  | 高 |
| 2 | `UniqueId` | `long` |  | 高 |
| 3 | `StarGrade` | `int` |  | 高 |
| 4 | `Level` | `int` |  | 高 |
| 5 | `Exp` | `long` |  | 高 |
| 6 | `FavorRank` | `int` |  | 高 |
| 7 | `FavorExp` | `long` |  | 高 |
| 8 | `PublicSkillLevel` | `int` |  | 高 |
| 9 | `ExSkillLevel` | `int` |  | 高 |
| 10 | `PassiveSkillLevel` | `int` |  | 高 |
| 11 | `ExtraPassiveSkillLevel` | `int` |  | 高 |
| 12 | `LeaderSkillLevel` | `int` |  | 高 |
| 13 | `IsFavorite` | `bool` |  | 高 |
| 14 | `EquipmentServerIds` | `List<long>` | 集合 | 高 |
| 15 | `PotentialStats` | `Dictionary<int,int>` | 字典 | 低 |

### **EquipmentDB**  ·  协议号未提取到  ·  4 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `Level` | `int` |  | 高 |
| 2 | `Exp` | `long` |  | 高 |
| 3 | `Tier` | `int` |  | 高 |
| 4 | `BoundCharacterServerId` | `long` |  | 高 |

### **ItemDB**  ·  协议号未提取到  ·  1 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `Expires` | `Nullable<DateTime>` | 可空 | 高 |

### **EchelonDB**  ·  协议号未提取到  ·  11 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `AccountServerId` | `long` |  | 高 |
| 2 | `EchelonType` | `EchelonType` | 枚举 | 高 |
| 3 | `EchelonNumber` | `long` |  | 高 |
| 4 | `ExtensionType` | `EchelonExtensionType` | 枚举 | 高 |
| 5 | `LeaderServerId` | `long` |  | 高 |
| 6 | `MainSlotServerIds` | `List<long>` | 集合 | 高 |
| 7 | `SupportSlotServerIds` | `List<long>` | 集合 | 高 |
| 8 | `TSSInteractionServerId` | `long` |  | 高 |
| 9 | `UsingFlag` | `EchelonStatusFlag` | 枚举 | 高 |
| 10 | `SkillCardMulliganCharacterIds` | `List<long>` | 集合 | 高 |
| 11 | `CombatStyleIndex` | `int[]` | 集合 | 高 |

### **MemoryLobbyDB**  ·  协议号未提取到  ·  1 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `MemoryLobbyUniqueId` | `long` |  | 高 |

### **CafeDB**  ·  协议号未提取到  ·  13 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `CafeDBId` | `long` |  | 高 |
| 2 | `CafeId` | `long` |  | 高 |
| 3 | `AccountId` | `long` |  | 高 |
| 4 | `CafeRank` | `int` |  | 高 |
| 5 | `LastUpdate` | `DateTime` | DateTime | 高 |
| 6 | `LastSummonDate` | `Nullable<DateTime>` | 可空 | 高 |
| 7 | `IsNew` | `bool` |  | 高 |
| 8 | `CafeVisitCharacterDBs` | `List<VisitingCharacterDB>` | 集合 | 低 |
| 9 | `FurnitureDBs` | `List<FurnitureDB>` | 集合 | 高 |
| 10 | `ProductionAppliedTime` | `DateTime` | DateTime | 高 |
| 11 | `ProductionDB` | `CafeProductionDB` | 对象 | 高 |
| 12 | `CurrencyDict_Obsolete` | `Dictionary<CurrencyTypes, long>` | 字典 | 高 |
| 13 | `UpdateTimeDict_Obsolete` | `Dictionary<CurrencyTypes,DateTime>` | 字典 | 高 |

引用：`CafeProductionDB`、`FurnitureDB`、`VisitingCharacterDB`

### **ParcelInfo**  ·  协议号未提取到  ·  4 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `Key` | `ParcelKeyPair` | 对象 | 高 |
| 2 | `Amount` | `long` |  | 高 |
| 3 | `Multiplier` | `BasisPoint` | 对象 | 高 |
| 4 | `Probability` | `BasisPoint` | 对象 | 高 |

引用：`BasisPoint`、`ParcelKeyPair`

### **MissionProgressDB**  ·  协议号未提取到  ·  6 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `ServerId` | `long` |  | 高 |
| 2 | `AccountServerId` | `long` |  | 高 |
| 3 | `MissionUniqueId` | `long` |  | 高 |
| 4 | `Complete` | `bool` |  | 高 |
| 5 | `StartTime` | `DateTime` | DateTime | 高 |
| 6 | `ProgressParameters` | `Dictionary<long, long>` | 字典 | 高 |

### **OpenConditionDB**  ·  协议号未提取到  ·  13 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `ContentType` | `OpenConditionContent` | 枚举 | 高 |
| 2 | `HideWhenLocked` | `bool` |  | 高 |
| 3 | `AccountLevel` | `long` |  | 高 |
| 4 | `ScenarioModeId` | `long` |  | 高 |
| 5 | `CampaignStageUniqueId` | `long` |  | 高 |
| 6 | `MultipleConditionCheckType` | `MultipleConditionCheckType` | 枚举 | 高 |
| 7 | `OpenDayOfWeek` | `WeekDay` | 枚举 | 高 |
| 8 | `OpenHour` | `long` |  | 高 |
| 9 | `CloseDayOfWeek` | `WeekDay` | 枚举 | 高 |
| 10 | `CloseHour` | `long` |  | 高 |
| 11 | `CafeIdForCafeRank` | `long` |  | 高 |
| 12 | `CafeRank` | `long` |  | 高 |
| 13 | `OpenedCafeId` | `long` |  | 高 |

### **GachaResult**  ·  协议号未提取到  ·  3 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `CharacterId` | `long` |  | 高 |
| 2 | `Character` | `CharacterDB` | 对象 | 高 |
| 3 | `Stone` | `ItemDB` | 对象 | 高 |

### 1.3 P1：进大厅第一批

### **CharacterListRequest**  ·  协议 2000  ·  0 字段  ·  base=RequestPacket

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|

### **CharacterListResponse**  ·  协议 2000  ·  4 字段  ·  base=ResponsePacket

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `CharacterDBs` | `List<CharacterDB>` | 集合 | 高 |
| 2 | `TSSCharacterDBs` | `List<CharacterDB>` | 集合 | 高 |
| 3 | `WeaponDBs` | `List<WeaponDB>` | 集合 | 高 |
| 4 | `CostumeDBs` | `List<CostumeDB>` | 集合 | 高 |

引用：`CharacterDB`、`CostumeDB`、`WeaponDB`

### **EquipmentItemListRequest**  ·  协议 3000  ·  0 字段  ·  base=RequestPacket

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|

### **EquipmentItemListResponse**  ·  协议 3000  ·  1 字段  ·  base=ResponsePacket

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `EquipmentDBs` | `List<EquipmentDB>` | 集合 | 高 |

引用：`EquipmentDB`

### **ItemListRequest**  ·  协议 4000  ·  0 字段  ·  base=RequestPacket

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|

### **ItemListResponse**  ·  协议 4000  ·  2 字段  ·  base=ResponsePacket

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `ItemDBs` | `List<ItemDB>` | 集合 | 高 |
| 2 | `ExpiryItemDBs` | `List<ItemDB>` | 集合 | 高 |

引用：`ItemDB`

### **EchelonListRequest**  ·  协议 5000  ·  0 字段  ·  base=RequestPacket

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|

### **EchelonListResponse**  ·  协议 5000  ·  2 字段  ·  base=ResponsePacket

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `EchelonDBs` | `List<EchelonDB>` | 集合 | 高 |
| 2 | `ArenaEchelonDB` | `EchelonDB` | 对象 | 高 |

引用：`EchelonDB`

### **MemoryLobbyListRequest**  ·  协议 12000  ·  0 字段  ·  base=RequestPacket

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|

### **MemoryLobbyListResponse**  ·  协议 12000  ·  1 字段  ·  base=ResponsePacket

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `MemoryLobbyDBs` | `List<MemoryLobbyDB>` | 集合 | 高 |

引用：`MemoryLobbyDB`

### **CafeGetInfoRequest**  ·  协议 20000  ·  1 字段  ·  base=RequestPacket

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `AccountServerId` | `long` |  | 高 |

### **CafeGetInfoResponse**  ·  协议 20000  ·  3 字段  ·  base=ResponsePacket

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `CafeDB` | `CafeDB` | 对象 | 高 |
| 2 | `CafeDBs` | `List<CafeDB>` | 集合 | 高 |
| 3 | `FurnitureDBs` | `List<FurnitureDB>` | 集合 | 高 |

引用：`CafeDB`、`FurnitureDB`

### **AccountCurrencySyncRequest**  ·  协议 1003  ·  0 字段  ·  base=RequestPacket

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|

### **AccountCurrencySyncResponse**  ·  协议 1003  ·  2 字段  ·  base=ResponsePacket

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `AccountCurrencyDB` | `AccountCurrencyDB` | 对象 | 高 |
| 2 | `ExpiredCurrency` | `Dictionary<CurrencyTypes, long>` | 字典 | 高 |

引用：`AccountCurrencyDB`

### **AttachmentGetRequest**  ·  协议 46000  ·  0 字段  ·  base=RequestPacket

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|

### **AttachmentGetResponse**  ·  协议 46000  ·  1 字段  ·  base=ResponsePacket

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `AccountAttachmentDB` | `AccountAttachmentDB` | 对象 | 高 |

引用：`AccountAttachmentDB`

### 1.4 P2：国服特供 TutorialGacha（Shittim 无此协议）

> 这四个协议的 **DTO 结构在 metadata 里是全的**，但 **协议号没提取到**（见 §3），`dto_schema.json` 里 `protocol` 为 `null`，需要抓包或客户端枚举补齐。

### **ShopListTutorialGachaRequest**  ·  协议号未提取到  ·  0 字段  ·  base=RequestPacket

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|

### **ShopListTutorialGachaResponse**  ·  协议号未提取到  ·  6 字段  ·  base=ResponsePacket

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `MaxTimes` | `int` |  | 高 |
| 2 | `LastTimes` | `int` |  | 高 |
| 3 | `LastResults` | `List<GachaResult>` | 集合 | 高 |
| 4 | `SaveTimes` | `int` |  | 高 |
| 5 | `SaveResults` | `List<GachaResult>` | 集合 | 高 |
| 6 | `ConfirmTimes` | `int` |  | 高 |

引用：`GachaResult`

### **ShopBuyTutorialGachaRequest**  ·  协议号未提取到  ·  0 字段  ·  base=RequestPacket

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|

### **ShopBuyTutorialGachaResponse**  ·  协议号未提取到  ·  3 字段  ·  base=ResponsePacket

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `GachaTimes` | `int` |  | 高 |
| 2 | `GachaResults` | `List<GachaResult>` | 集合 | 高 |
| 3 | `AcquiredItems` | `List<ItemDB>` | 集合 | 高 |

引用：`GachaResult`、`ItemDB`

### **ShopSaveTutorialGachaRequest**  ·  协议号未提取到  ·  0 字段  ·  base=RequestPacket

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|

### **ShopSaveTutorialGachaResponse**  ·  协议号未提取到  ·  2 字段  ·  base=ResponsePacket

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `SaveTimes` | `int` |  | 高 |
| 2 | `SaveResults` | `List<GachaResult>` | 集合 | 高 |

引用：`GachaResult`

### **ShopConfirmTutorialGachaRequest**  ·  协议号未提取到  ·  1 字段  ·  base=RequestPacket

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `GachaTimes` | `int` |  | 高 |

### **ShopConfirmTutorialGachaResponse**  ·  协议号未提取到  ·  3 字段  ·  base=ResponsePacket

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `UpdateTime` | `DateTime` | DateTime | 高 |
| 2 | `GachaResults` | `List<GachaResult>` | 集合 | 高 |
| 3 | `AcquiredItems` | `List<ItemDB>` | 集合 | 高 |

引用：`GachaResult`、`ItemDB`

### 1.5 基类（每个 Request / Response 都会带）

### **RequestPacket**  ·  协议号未提取到  ·  4 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `Resendable` | `bool` |  | 高 |
| 2 | `Hash` | `long` |  | 高 |
| 3 | `IsTest` | `bool` |  | 高 |
| 4 | `ModifiedServerTime__DebugOnly` | `Nullable<DateTime>` | 可空 | 高 |

### **ResponsePacket**  ·  协议号未提取到  ·  6 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `ServerTimeTicks` | `long` |  | 高 |
| 2 | `ServerNotification` | `ServerNotificationFlag` | 枚举 | 高 |
| 3 | `MissionProgressDBs` | `List<MissionProgressDB>` | 集合 | 高 |
| 4 | `EventMissionProgressDBDict` | `Dictionary<long,List<MissionProgressDB>>` | 字典 | 低 |
| 5 | `BattlePassMissionProgressDBDict` | `Dictionary<long,List<MissionProgressDB>>` | 字典 | 低 |
| 6 | `StaticOpenConditions` | `List<OpenConditionDB>` | 集合 | 中 |

引用：`MissionProgressDB`、`OpenConditionDB`


## §2 类型是怎么推出来的，以及置信度

### 2.1 metadata 解析

`global-metadata.dat` 的头部是 72×uint32 的「偏移/长度」表，按 34 个名字段解释；本项目已知：

| 表 | off | size | 步长 | 条目数 |
|---|---|---|---|---|
| string | 0x0EC9C8 | 0x6C7C88 | - | - |
| methods | 0x8B2C14 | 0x9085BC | 36 | 263077 |
| fields | 0x1B17590 | 0x232788 | 12 | 191990 |
| typeDefinitions | 0x1F02148 | 0x2F2358 | 88 | 35105 |
| images | 0x21F44A0 | 0x1018 | 40 | 103 |

`Il2CppTypeDefinition` 在本 build 里的槽位：`q[0]=名字`、`q[1]=命名空间`、`q[2]=byvalTypeIndex`、`q[8]=fieldStart`、`q[9]=methodStart`、`q[16]=方法数`、`q[17]=字段数`。字段条目是 `(nameIndex, typeIndex, token)`。字段名一律以 `<X>k__BackingField` 形式出现，已还原为属性名。

### 2.2 typeIndex → C# 类型：三条规则

**A（高，主力）** `field.typeIndex - 1 == 某 typedef 的 byvalTypeIndex` → 该类型。这条规则在 `AccountLoginSyncResponse` 的 30 个兄弟字段上 30/30 命中（每个都是对应的 `*Response` 类）。

**B（高）** 同上但落在 `System.Int32/Int64/String/Boolean/Single/Double/DateTime/Guid/...` 上 → 基元类型。验算：`string` 的 byval=61195 ⇒ 字段 61196；`long` 50530 ⇒ 50531；`int` 50494 ⇒ 50495；`DateTime` 42726 ⇒ 42727，与 `AccountDB` 的 `Nickname/ServerId/Level/LastConnectTime` 逐一对上。

**C（中/低）** 剩下的都是**泛型实例**（`List<T>`、`Dictionary<K,V>`、`Nullable<T>`、`T[]`）。它们没有 typedef，只在 `Il2CppType` 表里，而那张表在 `libil2cpp.so` 里、且本 build 的 `.text` 是加密页（`report/_tmp/patch/enc_pages.json` 记录的加密区间覆盖了绝大多数函数体，`get_Protocol` 处读到的就是随机字节），所以**泛型形状是推出来的**：用 Shittim 的 C# 声明对「同名字段」投票，157 个 key 得到纯票（全票一致），1 个 key 混合。再叠加「同一 typeIndex 在全程序里的其它使用点」聚类。手工裁定的 22 个 key 见 §3 表。

### 2.3 置信度定义与实测

| 置信度 | 含义 | 字段数 |
|---|---|---|
| 高 | 规则 A/B 直接命中，或全票一致；可当事实用 | 480 |
| 中 | 泛型实例，票数占比高或聚类一致 | 7 |
| 低 | 只有单点语义/命名证据 | 8 |

**规则 A/B 的准确率校验**：把 CN 解析结果与 Shittim 的 C# 声明逐字段比对，1,508 个可解析字段中 1,499 一致（99.4%）。9 个不一致全部是**国服与日服的版本差异**，不是解析错误：

| DTO.字段 | Shittim(日服) | 国服 metadata |
|---|---|---|
| AccountAuthResponse.OptionDB | Dictionary<string,object> | `OptionDB`（有 3 个字段的实体类） |
| BillingTransaction*.PurchaseOrderId | long | string |
| MailList*.PivotTime | DateTime | string |
| MissionListResponse.DailySuddenMissionInfo | object | `MissionInfo` |
| ArenaEnterBattlePart1Request.OpponentIndex | int | long（复用槽，低风险） |
| MissionInfo.Description | long | uint（复用槽，低风险） |

> 结论：**字段名、字段顺序、字段个数以 metadata 为准（本表）；类型只有泛型那一层是推断**。

## §3 没提取到的 / 推断的（诚实清单）

1. **协议号**：`Protocol` 枚举的字面值不在 metadata 的 `fieldDefaultValues` 里。证据：该表 81,939 条记录的 `fieldIndex` 从 65923 起，而 `MX.NetworkProtocol.Protocol` 的字段在 48891–49392，即**整个枚举没有默认值条目**；`.text` 又是加密页，读不到 `get_Protocol` 的 `mov w0,#imm`。本表的协议号来自 `report/_tmp/cn_proto/headless__data__protocols.json`（外部 SDK 表）+ `work/ba/proto/shittim_enum_numbers.json`（Shittim 的 `enum Protocol : int` 全量 501 条，只补 SDK 表缺的 `Arena_Login`/`Billing_PurchaseListByYostar`）。`Account_Nickname=1001 / Account_CallName=1010 / Account_LoginSync=1019 / Character_List=2000 / Cafe_Get=20000 / Attachment_Get=46000` 与 Shittim 完全一致。

   **国服/日服枚举成员差异**（两边都是 501 条，逐名比对；名字取自 CN metadata 的 typedef 字段表）：

   - **国服独有 14 个**：`Battle_Notify`、`Clan_Chat_Records`、`Clan_Send_Chat`、`Log_TestBattleCheckAsync`、`Log_TestBattleCheckSync`、`Log_TestBattleCheckSyncWithBattleSetting`、`Management_Data`、`Order_Notify`、`Shop_BuyTutorialGacha`、`Shop_ConfirmTutorialGacha`、`Shop_ListTutorialGacha`、`Shop_SaveTutorialGacha`、`Survey_Notify`、`Web_Notify`
   - **日服独有 15 个**（国服没有）：`Account_CheckNexon`、`Account_DetachNexon`、`Account_SetCheckAdultAgree`、`Account_VerifyCheckAdultAgree`、`Billing_*ByNexon` ×4、`Billing_CheckConditionCashShopGoods`、`Management_BannerList`、`Management_ProtocolLockList`、`Queuing_GetAuthTicket`、`Queuing_ProcessWaitingQueue`、`TTS_GetKana`
   - **所以四个 `Shop_*TutorialGacha` 的枚举成员名是确证的，只是数值缺失**——这也是为什么它们的 DTO 结构在 metadata 里完整、协议号却只能留空（`dto_schema.json` 里 `protocol` 为 `null`）。拿到其中任意一条的抓包号后，把 `dto_schema.json` 里对应 DTO 的 `protocol` 填上即可，生成器立刻可用。
2. **`Responses`（LoginSync 第 1 字段）的形状**：Shittim 写成 `ResponsePacket?`（单对象），但客户端是遍历 30 个子回包用的，本表按 `List<ResponsePacket>` 记为集合（中置信度）。若服务端按单对象发，把 schema 里该字段的 `type` 改成 `ResponsePacket` 即可。
3. **泛型实例形状**：以下 22 个 typeIndex 是手工裁定的，`dto_schema.json` 里已内联，依据写在这里：

| typeIndex | 裁定 | 依据 | 置信度 |
|---|---|---|---|
| 10115 | `Dictionary<CurrencyTypes,DateTime>` | 全程序同 key 使用点聚类 / Shittim 纯票 | 高 |
| 10285 | `Dictionary<int,int>` | 全程序同 key 使用点聚类 / Shittim 纯票 | 低 |
| 10442 | `Dictionary<long,List<MissionProgressDB>>` | 全程序同 key 使用点聚类 / Shittim 纯票 | 低 |
| 10584 | `int` | 全程序同 key 使用点聚类 / Shittim 纯票 | 低 |
| 10768 | `List<string>` | 全程序同 key 使用点聚类 / Shittim 纯票 | 低 |
| 10799 | `List<VisitingCharacterDB>` | 全程序同 key 使用点聚类 / Shittim 纯票 | 低 |
| 10859 | `List<OpenConditionDB>` | 全程序同 key 使用点聚类 / Shittim 纯票 | 中 |
| 21727 | `List<CraftNodeDB>` | 全程序同 key 使用点聚类 / Shittim 纯票 | 高 |
| 21731 | `List<CraftPresetNodeDB>` | 全程序同 key 使用点聚类 / Shittim 纯票 | 高 |
| 21752 | `List<DateTime>` | 全程序同 key 使用点聚类 / Shittim 纯票 | 高 |
| 22045 | `List<GachaResult>` | 全程序同 key 使用点聚类 / Shittim 纯票 | 高 |
| 22459 | `List<MissionProgressDB>` | 全程序同 key 使用点聚类 / Shittim 纯票 | 高 |
| 22558 | `List<ParcelInfo>` | 全程序同 key 使用点聚类 / Shittim 纯票 | 中 |
| 23058 | `List<TimeAttackDungeonBattleHistoryDB>` | 全程序同 key 使用点聚类 / Shittim 纯票 | 高 |
| 23060 | `List<CharacterDB>` | 全程序同 key 使用点聚类 / Shittim 纯票 | 中 |
| 23534 | `List<ParcelInfo>` | 全程序同 key 使用点聚类 / Shittim 纯票 | 高 |
| 24859 | `Nullable<DateTime>` | 全程序同 key 使用点聚类 / Shittim 纯票 | 高 |
| 33655 | `int[]` | 全程序同 key 使用点聚类 / Shittim 纯票 | 高 |
| 43628 | `int` | 全程序同 key 使用点聚类 / Shittim 纯票 | 低 |
| 50541 | `int` | 全程序同 key 使用点聚类 / Shittim 纯票 | 低 |
| 57877 | `List<ResponsePacket>` | 全程序同 key 使用点聚类 / Shittim 纯票 | 中 |
| 61200 | `string` | 全程序同 key 使用点聚类 / Shittim 纯票 | 高 |

4. **static / const 字段**：`FieldDefinition` 只有 `(name, typeIndex, token)`，没有 flags，静态字段无法与实例字段区分。已按名单跳过：`RequestPacket._counter`、`ParcelKeyPair.Empty`、`BasisPoint.{One,Zero,Epsilon,DoubleEpsilon}`。若后续发现遗漏的静态字段被写进 JSON，在 `build_schema.py` 的 `SKIP_BY_TYPE` 里加一行即可。
5. **没做的范围**：只导出了「取昵称 → 进大厅」链路 + P1/P2 清单 + 它们的递归引用（112 个）；metadata 里 `MX.*` 的 DTO 总量远大于此（800+ 个 Request/Response 类）。`MX.FlatData.*`（策划表）按设计不导入。

## 附录 A · `Account_LoginSync`(1019) 的 31 个子 DTO

`AccountLoginSyncResponse` 第 1 个字段 `Responses` 是主载体，第 2–27 个字段是各子系统回包（各一个 `*Response`），第 28–31 是标量/集合补充。下表给出每个子 DTO 的**完整字段表**。

### **AccountLoginSyncResponse**  ·  协议 1019  ·  31 字段  ·  base=ResponsePacket

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `Responses` | `List<ResponsePacket>` | 集合 | 中 |
| 2 | `CafeGetInfoResponse` | `CafeGetInfoResponse` | 对象 | 高 |
| 3 | `AccountCurrencySyncResponse` | `AccountCurrencySyncResponse` | 对象 | 高 |
| 4 | `CharacterListResponse` | `CharacterListResponse` | 对象 | 高 |
| 5 | `EquipmentItemListResponse` | `EquipmentItemListResponse` | 对象 | 高 |
| 6 | `CharacterGearListResponse` | `CharacterGearListResponse` | 对象 | 高 |
| 7 | `ItemListResponse` | `ItemListResponse` | 对象 | 高 |
| 8 | `EchelonListResponse` | `EchelonListResponse` | 对象 | 高 |
| 9 | `MemoryLobbyListResponse` | `MemoryLobbyListResponse` | 对象 | 高 |
| 10 | `CampaignListResponse` | `CampaignListResponse` | 对象 | 高 |
| 11 | `ArenaLoginResponse` | `ArenaLoginResponse` | 对象 | 高 |
| 12 | `RaidLoginResponse` | `RaidLoginResponse` | 对象 | 高 |
| 13 | `EliminateRaidLoginResponse` | `EliminateRaidLoginResponse` | 对象 | 高 |
| 14 | `CraftInfoListResponse` | `CraftInfoListResponse` | 对象 | 高 |
| 15 | `ClanLoginResponse` | `ClanLoginResponse` | 对象 | 高 |
| 16 | `MomotalkOutlineResponse` | `MomoTalkOutLineResponse` | 对象 | 高 |
| 17 | `ScenarioListResponse` | `ScenarioListResponse` | 对象 | 高 |
| 18 | `ShopGachaRecruitListResponse` | `ShopGachaRecruitListResponse` | 对象 | 高 |
| 19 | `TimeAttackDungeonLoginResponse` | `TimeAttackDungeonLoginResponse` | 对象 | 高 |
| 20 | `BillingPurchaseListByYostarResponse` | `BillingPurchaseListByYostarResponse` | 对象 | 高 |
| 21 | `EventContentPermanentListResponse` | `EventContentPermanentListResponse` | 对象 | 高 |
| 22 | `AttachmentGetResponse` | `AttachmentGetResponse` | 对象 | 高 |
| 23 | `AttachmentEmblemListResponse` | `AttachmentEmblemListResponse` | 对象 | 高 |
| 24 | `ContentSweepMultiSweepPresetListResponse` | `ContentSweepMultiSweepPresetListResponse` | 对象 | 高 |
| 25 | `StickerListResponse` | `StickerLoginResponse` | 对象 | 高 |
| 26 | `MultiFloorRaidSyncResponse` | `MultiFloorRaidSyncResponse` | 对象 | 高 |
| 27 | `MultiFloorRaidLoginResponse` | `MultiFloorRaidLoginResponse` | 对象 | 高 |
| 28 | `FriendCount` | `long` |  | 高 |
| 29 | `FriendCode` | `string` |  | 高 |
| 30 | `PickupFirstGetHistoryDBs` | `List<PickupFirstGetHistoryDB>` | 集合 | 高 |
| 31 | `AccountLevelRewardIds` | `List<long>` | 集合 | 高 |

引用：`AccountCurrencySyncResponse`、`ArenaLoginResponse`、`AttachmentEmblemListResponse`、`AttachmentGetResponse`、`BillingPurchaseListByYostarResponse`、`CafeGetInfoResponse`、`CampaignListResponse`、`CharacterGearListResponse`、`CharacterListResponse`、`ClanLoginResponse`、`ContentSweepMultiSweepPresetListResponse`、`CraftInfoListResponse`、`EchelonListResponse`、`EliminateRaidLoginResponse`、`EquipmentItemListResponse`、`EventContentPermanentListResponse`、`ItemListResponse`、`MemoryLobbyListResponse`、`MomoTalkOutLineResponse`、`MultiFloorRaidLoginResponse`、`MultiFloorRaidSyncResponse`、`PickupFirstGetHistoryDB`、`RaidLoginResponse`、`ResponsePacket`、`ScenarioListResponse`、`ShopGachaRecruitListResponse`、`StickerLoginResponse`、`TimeAttackDungeonLoginResponse`

### A.1 子回包 DTO

### **CafeGetInfoResponse**  ·  协议 20000  ·  3 字段  ·  base=ResponsePacket

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `CafeDB` | `CafeDB` | 对象 | 高 |
| 2 | `CafeDBs` | `List<CafeDB>` | 集合 | 高 |
| 3 | `FurnitureDBs` | `List<FurnitureDB>` | 集合 | 高 |

引用：`CafeDB`、`FurnitureDB`

### **AccountCurrencySyncResponse**  ·  协议 1003  ·  2 字段  ·  base=ResponsePacket

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `AccountCurrencyDB` | `AccountCurrencyDB` | 对象 | 高 |
| 2 | `ExpiredCurrency` | `Dictionary<CurrencyTypes, long>` | 字典 | 高 |

引用：`AccountCurrencyDB`

### **CharacterListResponse**  ·  协议 2000  ·  4 字段  ·  base=ResponsePacket

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `CharacterDBs` | `List<CharacterDB>` | 集合 | 高 |
| 2 | `TSSCharacterDBs` | `List<CharacterDB>` | 集合 | 高 |
| 3 | `WeaponDBs` | `List<WeaponDB>` | 集合 | 高 |
| 4 | `CostumeDBs` | `List<CostumeDB>` | 集合 | 高 |

引用：`CharacterDB`、`CostumeDB`、`WeaponDB`

### **EquipmentItemListResponse**  ·  协议 3000  ·  1 字段  ·  base=ResponsePacket

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `EquipmentDBs` | `List<EquipmentDB>` | 集合 | 高 |

引用：`EquipmentDB`

### **CharacterGearListResponse**  ·  协议 44000  ·  1 字段  ·  base=ResponsePacket

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `GearDBs` | `List<GearDB>` | 集合 | 高 |

引用：`GearDB`

### **ItemListResponse**  ·  协议 4000  ·  2 字段  ·  base=ResponsePacket

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `ItemDBs` | `List<ItemDB>` | 集合 | 高 |
| 2 | `ExpiryItemDBs` | `List<ItemDB>` | 集合 | 高 |

引用：`ItemDB`

### **EchelonListResponse**  ·  协议 5000  ·  2 字段  ·  base=ResponsePacket

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `EchelonDBs` | `List<EchelonDB>` | 集合 | 高 |
| 2 | `ArenaEchelonDB` | `EchelonDB` | 对象 | 高 |

引用：`EchelonDB`

### **MemoryLobbyListResponse**  ·  协议 12000  ·  1 字段  ·  base=ResponsePacket

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `MemoryLobbyDBs` | `List<MemoryLobbyDB>` | 集合 | 高 |

引用：`MemoryLobbyDB`

### **CampaignListResponse**  ·  协议 6000  ·  3 字段  ·  base=ResponsePacket

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `CampaignChapterClearRewardHistoryDBs` | `List<CampaignChapterClearRewardHistoryDB>` | 集合 | 高 |
| 2 | `StageHistoryDBs` | `List<CampaignStageHistoryDB>` | 集合 | 高 |
| 3 | `StrategyObjecthistoryDBs` | `List<StrategyObjectHistoryDB>` | 集合 | 高 |

引用：`CampaignChapterClearRewardHistoryDB`、`CampaignStageHistoryDB`、`StrategyObjectHistoryDB`

### **ArenaLoginResponse**  ·  协议 22001  ·  1 字段  ·  base=ResponsePacket

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `ArenaPlayerInfoDB` | `ArenaPlayerInfoDB` | 对象 | 高 |

引用：`ArenaPlayerInfoDB`

### **RaidLoginResponse**  ·  协议 17018  ·  4 字段  ·  base=ResponsePacket

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `SeasonType` | `RaidSeasonType` | 枚举 | 高 |
| 2 | `CanReceiveRankingReward` | `bool` |  | 高 |
| 3 | `LastSettledRanking` | `long` |  | 高 |
| 4 | `LastSettledTier` | `Nullable<int>` | 可空 | 高 |

### **EliminateRaidLoginResponse**  ·  协议 45000  ·  6 字段  ·  base=ResponsePacket

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `SeasonType` | `RaidSeasonType` | 枚举 | 高 |
| 2 | `CanReceiveRankingReward` | `bool` |  | 高 |
| 3 | `ReceiveLimitedRewardIds` | `List<long>` | 集合 | 高 |
| 4 | `SweepPointByRaidUniqueId` | `Dictionary<long, long>` | 字典 | 高 |
| 5 | `LastSettledRanking` | `long` |  | 高 |
| 6 | `LastSettledTier` | `Nullable<int>` | 可空 | 高 |

### **CraftInfoListResponse**  ·  协议 21000  ·  3 字段  ·  base=ResponsePacket

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `CraftInfos` | `List<CraftInfoDB>` | 集合 | 高 |
| 2 | `ShiftingCraftInfos` | `List<ShiftingCraftInfoDB>` | 集合 | 高 |
| 3 | `PresetSlotDBs` | `List<CraftPresetSlotDB>` | 集合 | 高 |

引用：`CraftInfoDB`、`CraftPresetSlotDB`、`ShiftingCraftInfoDB`

### **ClanLoginResponse**  ·  协议 28001  ·  3 字段  ·  base=ResponsePacket

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `AccountClanDB` | `ClanDB` | 对象 | 高 |
| 2 | `AccountClanMemberDB` | `ClanMemberDB` | 对象 | 高 |
| 3 | `ClanAssistSlotDBs` | `List<ClanAssistSlotDB>` | 集合 | 高 |

引用：`ClanAssistSlotDB`、`ClanDB`、`ClanMemberDB`

### **MomoTalkOutLineResponse**  ·  协议 33000  ·  2 字段  ·  base=ResponsePacket

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `MomoTalkOutLineDBs` | `List<MomoTalkOutLineDB>` | 集合 | 高 |
| 2 | `FavorScheduleRecords` | `Dictionary<long, List<long>>` | 字典 | 高 |

引用：`MomoTalkOutLineDB`

### **ScenarioListResponse**  ·  协议 19000  ·  3 字段  ·  base=ResponsePacket

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `ScenarioHistoryDBs` | `List<ScenarioHistoryDB>` | 集合 | 高 |
| 2 | `ScenarioGroupHistoryDBs` | `List<ScenarioGroupHistoryDB>` | 集合 | 高 |
| 3 | `ScenarioCollectionDBs` | `List<ScenarioCollectionDB>` | 集合 | 高 |

引用：`ScenarioCollectionDB`、`ScenarioGroupHistoryDB`、`ScenarioHistoryDB`

### **ShopGachaRecruitListResponse**  ·  协议 10006  ·  2 字段  ·  base=ResponsePacket

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `ShopRecruits` | `List<ShopRecruitDB>` | 集合 | 高 |
| 2 | `ShopFreeRecruitHistoryDBs` | `List<ShopFreeRecruitHistoryDB>` | 集合 | 高 |

引用：`ShopFreeRecruitHistoryDB`、`ShopRecruitDB`

### **TimeAttackDungeonLoginResponse**  ·  协议 39006  ·  1 字段  ·  base=ResponsePacket

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `PreviousRoomDB` | `TimeAttackDungeonRoomDB` | 对象 | 高 |

引用：`TimeAttackDungeonRoomDB`

### **BillingPurchaseListByYostarResponse**  ·  协议 29002  ·  6 字段  ·  base=ResponsePacket

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `CountList` | `List<PurchaseCountDB>` | 集合 | 高 |
| 2 | `OrderList` | `List<PurchaseOrderDB>` | 集合 | 高 |
| 3 | `MonthlyProductList` | `List<MonthlyProductPurchaseDB>` | 集合 | 高 |
| 4 | `BlockedProductDBs` | `List<BlockedProductDB>` | 集合 | 高 |
| 5 | `BattlePassProductList` | `List<BattlePassProductPurchaseDB>` | 集合 | 高 |
| 6 | `PendingProductShopCashIds` | `List<long>` | 集合 | 高 |

引用：`BattlePassProductPurchaseDB`、`BlockedProductDB`、`MonthlyProductPurchaseDB`、`PurchaseCountDB`、`PurchaseOrderDB`

### **EventContentPermanentListResponse**  ·  协议 30041  ·  1 字段  ·  base=ResponsePacket

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `PermanentDBs` | `List<EventContentPermanentDB>` | 集合 | 高 |

引用：`EventContentPermanentDB`

### **AttachmentGetResponse**  ·  协议 46000  ·  1 字段  ·  base=ResponsePacket

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `AccountAttachmentDB` | `AccountAttachmentDB` | 对象 | 高 |

引用：`AccountAttachmentDB`

### **AttachmentEmblemListResponse**  ·  协议 46001  ·  1 字段  ·  base=ResponsePacket

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `EmblemDBs` | `List<EmblemDB>` | 集合 | 高 |

引用：`EmblemDB`

### **ContentSweepMultiSweepPresetListResponse**  ·  协议 27002  ·  1 字段  ·  base=ResponsePacket

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `MultiSweepPresetDBs` | `List<MultiSweepPresetDB>` | 集合 | 高 |

引用：`MultiSweepPresetDB`

### **StickerLoginResponse**  ·  协议 47000  ·  1 字段  ·  base=ResponsePacket

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `StickerBookDB` | `StickerBookDB` | 对象 | 高 |

引用：`StickerBookDB`

### **MultiFloorRaidSyncResponse**  ·  协议 49000  ·  1 字段  ·  base=ResponsePacket

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `MultiFloorRaidDBs` | `List<MultiFloorRaidDB>` | 集合 | 高 |

引用：`MultiFloorRaidDB`

### **MultiFloorRaidLoginResponse**  ·  协议 49004  ·  1 字段  ·  base=ResponsePacket

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `LastClearedDifficulty` | `long` |  | 高 |

### A.2 `Responses` 里可能出现的其它回包

`Responses` 是 `List<ResponsePacket>`，实际内容由 `AccountLoginSyncRequest.SyncProtocols` 点名决定。本表已覆盖客户端在登录协程里会点到的 30 个子回包；`SyncProtocols` 里的枚举值是 `Protocol`，其数值同样受 §3 第 1 条限制。

## 附录 B · 全部 112 个 DTO 清单

| DTO | 命名空间 | 协议 | 字段数 | base |
|---|---|---|---|---|
| `AccountAttachmentDB` | MX.GameLogic.DBModel | - | 2 | - |
| `AccountAuthRequest` | MX.NetworkProtocol | 1002 | 16 | RequestPacket |
| `AccountAuthResponse` | MX.NetworkProtocol | 1002 | 27 | ResponsePacket |
| `AccountCallNameRequest` | MX.NetworkProtocol | 1010 | 1 | RequestPacket |
| `AccountCallNameResponse` | MX.NetworkProtocol | 1010 | 1 | ResponsePacket |
| `AccountCurrencyDB` | MX.GameLogic.DBModel | - | 4 | - |
| `AccountCurrencySyncRequest` | MX.NetworkProtocol | 1003 | 0 | RequestPacket |
| `AccountCurrencySyncResponse` | MX.NetworkProtocol | 1003 | 2 | ResponsePacket |
| `AccountDB` | MX.GameLogic.DBModel | - | 22 | - |
| `AccountLoginSyncRequest` | MX.NetworkProtocol | 1019 | 2 | RequestPacket |
| `AccountLoginSyncResponse` | MX.NetworkProtocol | 1019 | 31 | ResponsePacket |
| `AccountNicknameRequest` | MX.NetworkProtocol | 1001 | 1 | RequestPacket |
| `AccountNicknameResponse` | MX.NetworkProtocol | 1001 | 1 | ResponsePacket |
| `AccountRestrictionsDB` | MX.GameLogic.DBModel | - | 3 | - |
| `ArenaLoginResponse` | MX.NetworkProtocol | 22001 | 1 | ResponsePacket |
| `ArenaPlayerInfoDB` | MX.GameLogic.DBModel | - | 9 | - |
| `AttachmentEmblemListResponse` | MX.NetworkProtocol | 46001 | 1 | ResponsePacket |
| `AttachmentGetRequest` | MX.NetworkProtocol | 46000 | 0 | RequestPacket |
| `AttachmentGetResponse` | MX.NetworkProtocol | 46000 | 1 | ResponsePacket |
| `AttendanceBookReward` | MX.Data | - | 17 | - |
| `AttendanceHistoryDB` | MX.GameLogic.DBModel | - | 4 | - |
| `BasisPoint` | MX.Core.Math | - | 3 | - |
| `BattlePassProductPurchaseDB` | MX.GameLogic.DBModel | - | 3 | - |
| `BillingPurchaseListByYostarResponse` | MX.NetworkProtocol | 29002 | 6 | ResponsePacket |
| `BlockedProductDB` | MX.GameLogic.DBModel | - | 3 | - |
| `CafeDB` | MX.GameLogic.DBModel | - | 13 | - |
| `CafeGetInfoRequest` | MX.NetworkProtocol | 20000 | 1 | RequestPacket |
| `CafeGetInfoResponse` | MX.NetworkProtocol | 20000 | 3 | ResponsePacket |
| `CafeProductionDB` | MX.GameLogic.DBModel | - | 4 | - |
| `CampaignChapterClearRewardHistoryDB` | MX.GameLogic.DBModel | - | 3 | - |
| `CampaignListResponse` | MX.NetworkProtocol | 6000 | 3 | ResponsePacket |
| `CampaignStageHistoryDB` | MX.GameLogic.DBModel | - | 13 | - |
| `CharacterDB` | MX.GameLogic.DBModel | - | 15 | - |
| `CharacterGearListResponse` | MX.NetworkProtocol | 44000 | 1 | ResponsePacket |
| `CharacterListRequest` | MX.NetworkProtocol | 2000 | 0 | RequestPacket |
| `CharacterListResponse` | MX.NetworkProtocol | 2000 | 4 | ResponsePacket |
| `ClanAssistSlotDB` | MX.GameLogic.DBModel | - | 6 | - |
| `ClanDB` | MX.GameLogic.DBModel | - | 9 | - |
| `ClanLoginResponse` | MX.NetworkProtocol | 28001 | 3 | ResponsePacket |
| `ClanMemberDB` | MX.GameLogic.DBModel | - | 15 | - |
| `ContentSweepMultiSweepPresetListResponse` | MX.NetworkProtocol | 27002 | 1 | ResponsePacket |
| `CostumeDB` | MX.GameLogic.DBModel | - | 2 | - |
| `CraftInfoDB` | MX.GameLogic.DBModel | - | 5 | - |
| `CraftInfoListResponse` | MX.NetworkProtocol | 21000 | 3 | ResponsePacket |
| `CraftNodeDB` | MX.GameLogic.DBModel | - | 10 | - |
| `CraftNodeResult` | MX.GameLogic.DBModel | - | 2 | - |
| `CraftPresetNodeDB` | MX.GameLogic.DBModel | - | 4 | - |
| `CraftPresetSlotDB` | MX.GameLogic.DBModel | - | 3 | - |
| `EchelonDB` | MX.GameLogic.DBModel | - | 11 | - |
| `EchelonListRequest` | MX.NetworkProtocol | 5000 | 0 | RequestPacket |
| `EchelonListResponse` | MX.NetworkProtocol | 5000 | 2 | ResponsePacket |
| `EliminateRaidLoginResponse` | MX.NetworkProtocol | 45000 | 6 | ResponsePacket |
| `EmblemDB` | MX.GameLogic.DBModel | - | 2 | - |
| `EquipmentDB` | MX.GameLogic.DBModel | - | 4 | - |
| `EquipmentItemListRequest` | MX.NetworkProtocol | 3000 | 0 | RequestPacket |
| `EquipmentItemListResponse` | MX.NetworkProtocol | 3000 | 1 | ResponsePacket |
| `EventContentPermanentDB` | MX.GameLogic.DBModel | - | 3 | - |
| `EventContentPermanentListResponse` | MX.NetworkProtocol | 30041 | 1 | ResponsePacket |
| `FunctionClose` | MX.Data | - | 6 | - |
| `FurnitureDB` | MX.GameLogic.DBModel | - | 6 | - |
| `GachaResult` | MX.NetworkProtocol | - | 3 | - |
| `GearDB` | MX.GameLogic.DBModel | - | 7 | - |
| `IssueAlertInfoDB` | MX.GameLogic.DBModel | - | 8 | - |
| `ItemDB` | MX.GameLogic.DBModel | - | 1 | - |
| `ItemListRequest` | MX.NetworkProtocol | 4000 | 0 | RequestPacket |
| `ItemListResponse` | MX.NetworkProtocol | 4000 | 2 | ResponsePacket |
| `MemoryLobbyDB` | MX.GameLogic.DBModel | - | 1 | - |
| `MemoryLobbyListRequest` | MX.NetworkProtocol | 12000 | 0 | RequestPacket |
| `MemoryLobbyListResponse` | MX.NetworkProtocol | 12000 | 1 | ResponsePacket |
| `MissionProgressDB` | MX.GameLogic.DBModel | - | 6 | - |
| `MomoTalkOutLineDB` | MX.GameLogic.DBModel | - | 5 | - |
| `MomoTalkOutLineResponse` | MX.NetworkProtocol | 33000 | 2 | ResponsePacket |
| `MonthlyProductPurchaseDB` | MX.GameLogic.DBModel | - | 4 | - |
| `MultiFloorRaidDB` | MX.GameLogic.DBModel | - | 6 | - |
| `MultiFloorRaidLoginResponse` | MX.NetworkProtocol | 49004 | 1 | ResponsePacket |
| `MultiFloorRaidSyncResponse` | MX.NetworkProtocol | 49000 | 1 | ResponsePacket |
| `MultiSweepPresetDB` | MX.GameLogic.DBModel | - | 4 | - |
| `OpenConditionDB` | MX.GameLogic.DBModel | - | 13 | - |
| `OptionDB` | MX.GameLogic.DBModel | - | 3 | - |
| `ParcelInfo` | MX.GameLogic.Parcel | - | 4 | - |
| `ParcelKeyPair` | MX.GameLogic.Parcel | - | 2 | - |
| `PickupFirstGetHistoryDB` | MX.GameLogic.DBModel | - | 2 | - |
| `PurchaseCountDB` | MX.GameLogic.DBModel | - | 5 | - |
| `PurchaseOrderDB` | MX.GameLogic.DBModel | - | 3 | - |
| `RaidLoginResponse` | MX.NetworkProtocol | 17018 | 4 | ResponsePacket |
| `RequestPacket` | MX.NetworkProtocol | - | 4 | - |
| `ResponsePacket` | MX.NetworkProtocol | - | 6 | - |
| `ScenarioCollectionDB` | MX.GameLogic.DBModel | - | 3 | - |
| `ScenarioGroupHistoryDB` | MX.GameLogic.DBModel | - | 5 | - |
| `ScenarioHistoryDB` | MX.GameLogic.DBModel | - | 2 | - |
| `ScenarioListResponse` | MX.NetworkProtocol | 19000 | 3 | ResponsePacket |
| `ShiftingCraftInfoDB` | MX.GameLogic.DBModel | - | 5 | - |
| `ShopBuyTutorialGachaRequest` | MX.NetworkProtocol | - | 0 | RequestPacket |
| `ShopBuyTutorialGachaResponse` | MX.NetworkProtocol | - | 3 | ResponsePacket |
| `ShopConfirmTutorialGachaRequest` | MX.NetworkProtocol | - | 1 | RequestPacket |
| `ShopConfirmTutorialGachaResponse` | MX.NetworkProtocol | - | 3 | ResponsePacket |
| `ShopFreeRecruitHistoryDB` | MX.GameLogic.DBModel | - | 3 | - |
| `ShopGachaRecruitListResponse` | MX.NetworkProtocol | 10006 | 2 | ResponsePacket |
| `ShopListTutorialGachaRequest` | MX.NetworkProtocol | - | 0 | RequestPacket |
| `ShopListTutorialGachaResponse` | MX.NetworkProtocol | - | 6 | ResponsePacket |
| `ShopRecruitDB` | MX.GameLogic.DBModel | - | 4 | - |
| `ShopSaveTutorialGachaRequest` | MX.NetworkProtocol | - | 0 | RequestPacket |
| `ShopSaveTutorialGachaResponse` | MX.NetworkProtocol | - | 2 | ResponsePacket |
| `StickerBookDB` | MX.GameLogic.DBModel | - | 3 | - |
| `StickerDB` | MX.GameLogic.DBModel | - | 1 | - |
| `StickerLoginResponse` | MX.NetworkProtocol | 47000 | 1 | ResponsePacket |
| `StrategyObjectHistoryDB` | MX.GameLogic.DBModel | - | 1 | - |
| `TimeAttackDungeonBattleHistoryDB` | MX.GameLogic.DBModel | - | 7 | - |
| `TimeAttackDungeonLoginResponse` | MX.NetworkProtocol | 39006 | 1 | ResponsePacket |
| `TimeAttackDungeonRoomDB` | MX.GameLogic.DBModel | - | 8 | - |
| `VisitingCharacterDB` | MX.GameLogic.DBModel | - | 2 | - |
| `WeaponDB` | MX.GameLogic.DBModel | - | 5 | - |

## 附录 C · 其余 DTO 字段表

### **AccountAttachmentDB**  ·  协议号未提取到  ·  2 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `AccountId` | `long` |  | 高 |
| 2 | `EmblemUniqueId` | `long` |  | 高 |

### **AccountAuthRequest**  ·  协议 1002  ·  16 字段  ·  base=RequestPacket

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `Version` | `long` |  | 高 |
| 2 | `DevId` | `string` |  | 高 |
| 3 | `IMEI` | `long` |  | 高 |
| 4 | `AccessIP` | `string` |  | 高 |
| 5 | `MarketId` | `string` |  | 高 |
| 6 | `UserType` | `string` |  | 高 |
| 7 | `AdvertisementId` | `string` |  | 高 |
| 8 | `OSType` | `string` |  | 高 |
| 9 | `OSVersion` | `string` |  | 高 |
| 10 | `DeviceUniqueId` | `string` |  | 高 |
| 11 | `DeviceModel` | `string` |  | 高 |
| 12 | `DeviceSystemMemorySize` | `int` |  | 高 |
| 13 | `Token` | `string` |  | 高 |
| 14 | `SdkPid` | `string` |  | 高 |
| 15 | `SubChannel` | `string` |  | 高 |
| 16 | `ResUrl` | `string` |  | 高 |

### **AccountAuthResponse**  ·  协议 1002  ·  27 字段  ·  base=ResponsePacket

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `CurrentVersion` | `long` |  | 高 |
| 2 | `MinimumVersion` | `long` |  | 高 |
| 3 | `IsDevelopment` | `bool` |  | 高 |
| 4 | `BattleValidation` | `bool` |  | 高 |
| 5 | `UpdateRequired` | `bool` |  | 高 |
| 6 | `TTSCdnUri` | `string` |  | 高 |
| 7 | `AccountDB` | `AccountDB` | 对象 | 高 |
| 8 | `AttendanceBookRewards` | `List<AttendanceBookReward>` | 集合 | 高 |
| 9 | `AttendanceHistoryDBs` | `List<AttendanceHistoryDB>` | 集合 | 高 |
| 10 | `RepurchasableMonthlyProductCountDBs` | `List<PurchaseCountDB>` | 集合 | 高 |
| 11 | `MonthlyProductParcel` | `List<ParcelInfo>` | 集合 | 高 |
| 12 | `MonthlyProductMail` | `List<ParcelInfo>` | 集合 | 高 |
| 13 | `BiweeklyProductParcel` | `List<ParcelInfo>` | 集合 | 高 |
| 14 | `BiweeklyProductMail` | `List<ParcelInfo>` | 集合 | 高 |
| 15 | `WeeklyProductParcel` | `List<ParcelInfo>` | 集合 | 高 |
| 16 | `WeeklyProductMail` | `List<ParcelInfo>` | 集合 | 高 |
| 17 | `EncryptedUID` | `string` |  | 高 |
| 18 | `AccountRestrictionsDB` | `AccountRestrictionsDB` | 对象 | 高 |
| 19 | `IssueAlertInfos` | `List<IssueAlertInfoDB>` | 集合 | 高 |
| 20 | `DailyRecordDBs` | `List<object>` | 集合 | 高 |
| 21 | `OptionDB` | `OptionDB` | 对象 | 高 |
| 22 | `IsArenaAnonymous` | `bool` |  | 高 |
| 23 | `AccountLimitedFlashSaleDBs` | `List<object>` | 集合 | 高 |
| 24 | `NewlyAddedShopCashIds` | `List<long>` | 集合 | 高 |
| 25 | `IsNew` | `bool` |  | 高 |
| 26 | `Desc` | `string` |  | 高 |
| 27 | `FunctionClose` | `FunctionClose` | 对象 | 高 |

引用：`AccountDB`、`AccountRestrictionsDB`、`AttendanceBookReward`、`AttendanceHistoryDB`、`FunctionClose`、`IssueAlertInfoDB`、`OptionDB`、`ParcelInfo`、`PurchaseCountDB`

### **ArenaPlayerInfoDB**  ·  协议号未提取到  ·  9 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `CurrentSeasonId` | `long` |  | 高 |
| 2 | `PlayerGroupId` | `long` |  | 高 |
| 3 | `CurrentRank` | `long` |  | 高 |
| 4 | `SeasonRecord` | `long` |  | 高 |
| 5 | `AllTimeRecord` | `long` |  | 高 |
| 6 | `CumulativeTimeReward` | `long` |  | 高 |
| 7 | `TimeRewardLastUpdateTime` | `DateTime` | DateTime | 高 |
| 8 | `BattleEnterActiveTime` | `DateTime` | DateTime | 高 |
| 9 | `DailyRewardActiveTime` | `DateTime` | DateTime | 高 |

### **AttendanceBookReward**  ·  协议号未提取到  ·  17 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `UniqueId` | `long` |  | 高 |
| 2 | `Type` | `AttendanceType` | 枚举 | 高 |
| 3 | `TargetGroup` | `TargetGroup` | 枚举 | 高 |
| 4 | `DisplayOrder` | `long` |  | 高 |
| 5 | `AccountLevelLimit` | `long` |  | 高 |
| 6 | `Title` | `string` |  | 高 |
| 7 | `TitleImagePath` | `string` |  | 高 |
| 8 | `CountRule` | `AttendanceCountRule` | 枚举 | 高 |
| 9 | `CountReset` | `AttendanceResetType` | 枚举 | 高 |
| 10 | `BookSize` | `long` |  | 高 |
| 11 | `StartDate` | `DateTime` | DateTime | 高 |
| 12 | `StartableEndDate` | `DateTime` | DateTime | 高 |
| 13 | `EndDate` | `DateTime` | DateTime | 高 |
| 14 | `ExpiryDate` | `long` |  | 高 |
| 15 | `MailType` | `MailType` | 枚举 | 高 |
| 16 | `DailyRewardIcons` | `List<string>` | 集合 | 低 |
| 17 | `DailyRewards` | `Dictionary<long, List<ParcelInfo>>` | 字典 | 高 |

引用：`ParcelInfo`

### **AttendanceHistoryDB**  ·  协议号未提取到  ·  4 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `ServerId` | `long` |  | 高 |
| 2 | `AttendanceBookUniqueId` | `long` |  | 高 |
| 3 | `AttendedDay` | `int` |  | 低 |
| 4 | `Expired` | `bool` |  | 高 |

### **BasisPoint**  ·  协议号未提取到  ·  3 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `Multiplier` | `int` |  | 低 |
| 2 | `OneOver10_4` | `int` |  | 低 |
| 3 | `rawValue` | `long` |  | 高 |

### **BattlePassProductPurchaseDB**  ·  协议号未提取到  ·  3 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `ProductId` | `long` |  | 高 |
| 2 | `BattlePassId` | `long` |  | 高 |
| 3 | `PurchaseBattlePassGroupId` | `long` |  | 高 |

### **BlockedProductDB**  ·  协议号未提取到  ·  3 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `CashProductId` | `long` |  | 高 |
| 2 | `BeginDate` | `DateTime` | DateTime | 高 |
| 3 | `EndDate` | `DateTime` | DateTime | 高 |

### **CafeProductionDB**  ·  协议号未提取到  ·  4 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `CafeDBId` | `long` |  | 高 |
| 2 | `ComfortValue` | `long` |  | 高 |
| 3 | `AppliedDate` | `DateTime` | DateTime | 高 |
| 4 | `ProductionParcelInfos` | `List<ParcelInfo>` | 集合 | 高 |

### **CampaignChapterClearRewardHistoryDB**  ·  协议号未提取到  ·  3 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `ChapterUniqueId` | `long` |  | 高 |
| 2 | `RewardType` | `StageDifficulty` | 枚举 | 高 |
| 3 | `ReceiveDate` | `DateTime` | DateTime | 高 |

### **CampaignStageHistoryDB**  ·  协议号未提取到  ·  13 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `StoryUniqueId` | `long` |  | 高 |
| 2 | `ChapterUniqueId` | `long` |  | 高 |
| 3 | `StageUniqueId` | `long` |  | 高 |
| 4 | `TacticClearCountWithRankSRecord` | `long` |  | 高 |
| 5 | `ClearTurnRecord` | `long` |  | 高 |
| 6 | `Star1Flag` | `bool` |  | 高 |
| 7 | `Star2Flag` | `bool` |  | 高 |
| 8 | `Star3Flag` | `bool` |  | 高 |
| 9 | `LastPlay` | `DateTime` | DateTime | 高 |
| 10 | `TodayPlayCount` | `long` |  | 高 |
| 11 | `TodayPurchasePlayCountHardStage` | `long` |  | 高 |
| 12 | `FirstClearRewardReceive` | `Nullable<DateTime>` | 可空 | 高 |
| 13 | `StarRewardReceive` | `Nullable<DateTime>` | 可空 | 高 |

### **ClanAssistSlotDB**  ·  协议号未提取到  ·  6 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `EchelonType` | `EchelonType` | 枚举 | 高 |
| 2 | `SlotNumber` | `long` |  | 高 |
| 3 | `CharacterDBId` | `long` |  | 高 |
| 4 | `DeployDate` | `DateTime` | DateTime | 高 |
| 5 | `TotalRentCount` | `long` |  | 高 |
| 6 | `CombatStyleIndex` | `int` |  | 高 |

### **ClanDB**  ·  协议号未提取到  ·  9 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `ClanDBId` | `long` |  | 高 |
| 2 | `ClanName` | `string` |  | 高 |
| 3 | `ClanChannelName` | `string` |  | 高 |
| 4 | `ClanPresidentNickName` | `string` |  | 高 |
| 5 | `ClanPresidentRepresentCharacterUniqueId` | `long` |  | 高 |
| 6 | `ClanPresidentRepresentCharacterCostumeId` | `long` |  | 高 |
| 7 | `ClanNotice` | `string` |  | 高 |
| 8 | `ClanMemberCount` | `long` |  | 高 |
| 9 | `ClanJoinOption` | `ClanJoinOption` | 枚举 | 高 |

### **ClanMemberDB**  ·  协议号未提取到  ·  15 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `AccountId` | `long` |  | 高 |
| 2 | `AccountLevel` | `long` |  | 高 |
| 3 | `AccountNickName` | `string` |  | 高 |
| 4 | `ClanDBId` | `long` |  | 高 |
| 5 | `RepresentCharacterUniqueId` | `long` |  | 高 |
| 6 | `RepresentCharacterCostumeId` | `long` |  | 高 |
| 7 | `AttendanceCount` | `long` |  | 高 |
| 8 | `CafeComfortValue` | `long` |  | 高 |
| 9 | `ClanSocialGrade` | `ClanSocialGrade` | 枚举 | 高 |
| 10 | `JoinDate` | `DateTime` | DateTime | 高 |
| 11 | `SocialGradeUpdateTime` | `DateTime` | DateTime | 高 |
| 12 | `LastLoginDate` | `DateTime` | DateTime | 高 |
| 13 | `GameLoginDate` | `DateTime` | DateTime | 高 |
| 14 | `AppliedDate` | `DateTime` | DateTime | 高 |
| 15 | `AttachmentDB` | `AccountAttachmentDB` | 对象 | 高 |

### **CostumeDB**  ·  协议号未提取到  ·  2 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `UniqueId` | `long` |  | 高 |
| 2 | `BoundCharacterServerId` | `long` |  | 高 |

### **CraftInfoDB**  ·  协议号未提取到  ·  5 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `SlotSequence` | `long` |  | 高 |
| 2 | `StartTime` | `DateTime` | DateTime | 高 |
| 3 | `EndTime` | `DateTime` | DateTime | 高 |
| 4 | `CraftSlotOpenDate` | `DateTime` | DateTime | 高 |
| 5 | `Nodes` | `List<CraftNodeDB>` | 集合 | 高 |

引用：`CraftNodeDB`

### **CraftNodeDB**  ·  协议号未提取到  ·  10 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `NodeTier` | `CraftNodeTier` | 枚举 | 高 |
| 2 | `SlotSequence` | `long` |  | 高 |
| 3 | `NodeId` | `long` |  | 高 |
| 4 | `NodeQuality` | `long` |  | 高 |
| 5 | `NodeLevel` | `long` |  | 高 |
| 6 | `NodeRandomSeed` | `int` |  | 高 |
| 7 | `NodeRandomSequence` | `int` |  | 高 |
| 8 | `LeafNodeIds` | `List<long>` | 集合 | 高 |
| 9 | `ResultId` | `long` |  | 高 |
| 10 | `CraftNodeResult` | `CraftNodeResult` | 对象 | 高 |

引用：`CraftNodeResult`

### **CraftNodeResult**  ·  协议号未提取到  ·  2 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `NodeTier` | `CraftNodeTier` | 枚举 | 高 |
| 2 | `ParcelInfo` | `ParcelInfo` | 对象 | 高 |

### **CraftPresetNodeDB**  ·  协议号未提取到  ·  4 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `NodeTier` | `CraftNodeTier` | 枚举 | 高 |
| 2 | `IsActivated` | `bool` |  | 高 |
| 3 | `PriorityNodeIds` | `List<long>` | 集合 | 高 |
| 4 | `CostParcels` | `List<ParcelInfo>` | 集合 | 中 |

### **CraftPresetSlotDB**  ·  协议号未提取到  ·  3 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `PresetIndex` | `int` |  | 高 |
| 2 | `PresetNodeDBs` | `List<CraftPresetNodeDB>` | 集合 | 高 |
| 3 | `PresetName` | `string` |  | 高 |

引用：`CraftPresetNodeDB`

### **EmblemDB**  ·  协议号未提取到  ·  2 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `UniqueId` | `long` |  | 高 |
| 2 | `ReceiveDate` | `DateTime` | DateTime | 高 |

### **EventContentPermanentDB**  ·  协议号未提取到  ·  3 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `EventContentId` | `long` |  | 高 |
| 2 | `IsStageAllClear` | `bool` |  | 高 |
| 3 | `IsReceivedCharacterReward` | `bool` |  | 高 |

### **FurnitureDB**  ·  协议号未提取到  ·  6 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `Location` | `FurnitureLocation` | 枚举 | 高 |
| 2 | `CafeDBId` | `long` |  | 高 |
| 3 | `PositionX` | `float` |  | 高 |
| 4 | `PositionY` | `float` |  | 高 |
| 5 | `Rotation` | `float` |  | 高 |
| 6 | `ItemDeploySequence` | `long` |  | 高 |

### **GearDB**  ·  协议号未提取到  ·  7 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `ServerId` | `long` |  | 高 |
| 2 | `UniqueId` | `long` |  | 高 |
| 3 | `Level` | `int` |  | 高 |
| 4 | `Exp` | `long` |  | 高 |
| 5 | `Tier` | `int` |  | 高 |
| 6 | `SlotIndex` | `long` |  | 高 |
| 7 | `BoundCharacterServerId` | `long` |  | 高 |

### **IssueAlertInfoDB**  ·  协议号未提取到  ·  8 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `IssueAlertId` | `int` |  | 高 |
| 2 | `IssueAlertType` | `IssueAlertTypeCode` | 枚举 | 高 |
| 3 | `StartDate` | `DateTime` | DateTime | 高 |
| 4 | `EndDate` | `DateTime` | DateTime | 高 |
| 5 | `DisplayOrder` | `byte` |  | 高 |
| 6 | `PublishId` | `int` |  | 高 |
| 7 | `Url` | `string` |  | 高 |
| 8 | `Subject` | `string` |  | 高 |

### **MomoTalkOutLineDB**  ·  协议号未提取到  ·  5 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `CharacterDBId` | `long` |  | 高 |
| 2 | `CharacterId` | `long` |  | 高 |
| 3 | `LatestMessageGroupId` | `long` |  | 高 |
| 4 | `ChosenMessageId` | `Nullable<long>` | 可空 | 中 |
| 5 | `LastUpdateDate` | `DateTime` | DateTime | 高 |

### **MonthlyProductPurchaseDB**  ·  协议号未提取到  ·  4 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `ProductId` | `long` |  | 高 |
| 2 | `PurchaseDate` | `DateTime` | DateTime | 高 |
| 3 | `LastDailyRewardDate` | `Nullable<DateTime>` | 可空 | 高 |
| 4 | `RewardEndDate` | `Nullable<DateTime>` | 可空 | 高 |

### **MultiFloorRaidDB**  ·  协议号未提取到  ·  6 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `SeasonId` | `long` |  | 高 |
| 2 | `ClearedDifficulty` | `int` |  | 高 |
| 3 | `LastClearDate` | `DateTime` | DateTime | 高 |
| 4 | `RewardDifficulty` | `int` |  | 高 |
| 5 | `LastRewardDate` | `DateTime` | DateTime | 高 |
| 6 | `ClearBattleFrame` | `int` |  | 高 |

### **MultiSweepPresetDB**  ·  协议号未提取到  ·  4 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `PresetId` | `long` |  | 高 |
| 2 | `PresetName` | `string` |  | 高 |
| 3 | `StageIds` | `List<long>` | 集合 | 高 |
| 4 | `ParcelIds` | `List<ParcelKeyPair>` | 集合 | 高 |

引用：`ParcelKeyPair`

### **ParcelKeyPair**  ·  协议号未提取到  ·  2 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `Type` | `ParcelType` | 枚举 | 高 |
| 2 | `Id` | `long` |  | 高 |

### **PickupFirstGetHistoryDB**  ·  协议号未提取到  ·  2 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `ShopRecruitId` | `long` |  | 高 |
| 2 | `LogDate` | `DateTime` | DateTime | 高 |

### **PurchaseCountDB**  ·  协议号未提取到  ·  5 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `ShopCashId` | `long` |  | 高 |
| 2 | `PurchaseCount` | `int` |  | 高 |
| 3 | `ResetDate` | `DateTime` | DateTime | 高 |
| 4 | `PurchaseDate` | `Nullable<DateTime>` | 可空 | 高 |
| 5 | `ManualResetDate` | `Nullable<DateTime>` | 可空 | 高 |

### **PurchaseOrderDB**  ·  协议号未提取到  ·  3 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `ShopCashId` | `long` |  | 高 |
| 2 | `StatusCode` | `PurchaseStatusCode` | 枚举 | 高 |
| 3 | `PurchaseOrderId` | `string` |  | 高 |

### **ScenarioCollectionDB**  ·  协议号未提取到  ·  3 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `GroupId` | `long` |  | 高 |
| 2 | `UniqueId` | `long` |  | 高 |
| 3 | `ReceiveDate` | `DateTime` | DateTime | 高 |

### **ScenarioGroupHistoryDB**  ·  协议号未提取到  ·  5 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `ScenarioGroupUniqueId` | `long` |  | 高 |
| 2 | `ScenarioType` | `long` |  | 高 |
| 3 | `EventContentId` | `Nullable<long>` | 可空 | 中 |
| 4 | `ClearDateTime` | `DateTime` | DateTime | 高 |
| 5 | `IsReturn` | `bool` |  | 高 |

### **ScenarioHistoryDB**  ·  协议号未提取到  ·  2 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `ScenarioUniqueId` | `long` |  | 高 |
| 2 | `ClearDateTime` | `DateTime` | DateTime | 高 |

### **ShiftingCraftInfoDB**  ·  协议号未提取到  ·  5 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `SlotSequence` | `long` |  | 高 |
| 2 | `CraftRecipeId` | `long` |  | 高 |
| 3 | `CraftAmount` | `long` |  | 高 |
| 4 | `StartTime` | `DateTime` | DateTime | 高 |
| 5 | `EndTime` | `DateTime` | DateTime | 高 |

### **ShopFreeRecruitHistoryDB**  ·  协议号未提取到  ·  3 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `UniqueId` | `long` |  | 高 |
| 2 | `RecruitCount` | `int` |  | 高 |
| 3 | `LastUpdateDate` | `DateTime` | DateTime | 高 |

### **ShopRecruitDB**  ·  协议号未提取到  ·  4 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `Id` | `long` |  | 高 |
| 2 | `SalesStartDate` | `DateTime` | DateTime | 高 |
| 3 | `SalesEndDate` | `DateTime` | DateTime | 高 |
| 4 | `UpdateDate` | `DateTime` | DateTime | 高 |

### **StickerBookDB**  ·  协议号未提取到  ·  3 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `AccountId` | `long` |  | 高 |
| 2 | `UnusedStickerDBs` | `List<StickerDB>` | 集合 | 高 |
| 3 | `UsedStickerDBs` | `List<StickerDB>` | 集合 | 高 |

引用：`StickerDB`

### **StickerDB**  ·  协议号未提取到  ·  1 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `StickerUniqueId` | `long` |  | 高 |

### **StrategyObjectHistoryDB**  ·  协议号未提取到  ·  1 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `StrategyObjectId` | `long` |  | 高 |

### **TimeAttackDungeonBattleHistoryDB**  ·  协议号未提取到  ·  7 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `DungeonType` | `TimeAttackDungeonType` | 枚举 | 高 |
| 2 | `GeasId` | `long` |  | 高 |
| 3 | `DefaultPoint` | `long` |  | 高 |
| 4 | `ClearTimePoint` | `long` |  | 高 |
| 5 | `EndFrame` | `long` |  | 高 |
| 6 | `MainCharacterDBs` | `List<CharacterDB>` | 集合 | 中 |
| 7 | `SupportCharacterDBs` | `List<CharacterDB>` | 集合 | 中 |

### **TimeAttackDungeonRoomDB**  ·  协议号未提取到  ·  8 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `AccountId` | `long` |  | 高 |
| 2 | `SeasonId` | `long` |  | 高 |
| 3 | `RoomId` | `long` |  | 高 |
| 4 | `CreateDate` | `DateTime` | DateTime | 高 |
| 5 | `RewardDate` | `DateTime` | DateTime | 高 |
| 6 | `IsPractice` | `bool` |  | 高 |
| 7 | `SweepHistoryDates` | `List<DateTime>` | 集合 | 高 |
| 8 | `BattleHistoryDBs` | `List<TimeAttackDungeonBattleHistoryDB>` | 集合 | 高 |

引用：`TimeAttackDungeonBattleHistoryDB`

### **VisitingCharacterDB**  ·  协议号未提取到  ·  2 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `UniqueId` | `long` |  | 高 |
| 2 | `ServerId` | `long` |  | 高 |

### **WeaponDB**  ·  协议号未提取到  ·  5 字段

| # | 字段名 | 推断类型 | 标记 | 置信度 |
|---|---|---|---|---|
| 1 | `UniqueId` | `long` |  | 高 |
| 2 | `Level` | `int` |  | 高 |
| 3 | `Exp` | `long` |  | 高 |
| 4 | `StarGrade` | `int` |  | 高 |
| 5 | `BoundCharacterServerId` | `long` |  | 高 |
