# 71 · 进大厅 DTO 批量补齐（45 个缺口 → 50 个协议 / 96 个类型）

> **角色**：DTO 批量补全员 ｜ **产出**：2026-11-14 ｜ **目标**：把进大厅路径上缺的 Response DTO 一次性补齐，并做成可复现的生成器
> **纪律**：只读本地文件 + 只写自己的产物；**未连手机、未连服务器**（无 adb / ssh / 网络请求）；未改 `dto_schema.json` / `gen_default.py` / `protocol_map.json` / `dto_schema_academy.json` / `gen_academy.py`（全部只读引用）；未碰 `libtprt.so`

---

## 0. 结论速览

| 项 | 结果 |
| --- | --- |
| 45 个缺口 | ✅ **全部提取完成**，0 个幽灵名（45 个在 metadata 里都是真实 typedef） |
| 39 个有 payload 的 DTO | ✅ 与 `shittim_types.json` 的 C# 声明**逐字段对照：39/39 字段名、顺序、数量完全一致（0 diff）** |
| 字段类型比对 | ✅ 74 个字段逐一比对 shittim 声明：**74 一致 / 0 不一致** |
| 6 个"空"DTO | ⚠️ metadata 里 `fieldCount = 0` —— 真没有 payload，不是没挖到（见 §2.1） |
| 继承链 | 🆕 发现 `ItemDB`/`EquipmentDB`/`FurnitureDB` 的基类是 `ConsumableItemBaseDB`，**不展开会各少 3 个字段**（见 §0.2） |
| 45 个 DTO 的父类 | ✅ 全部 = `ResponsePacket`（用 typedef 的 `q[4]` 走 byval 反查，**不是假设**） |
| schema 规模 | 96 个类型定义（50 个协议 + 46 个嵌套 DB/枚举）、**297 条自有字段**、386 条展开后字段 |
| 仍为 `unknown` 的字段 | **2 条**（占 297 的 0.7%），都带 hint，生成时给 `[]` |
| `--check` | ✅ **PASS，exit 0**；`--check --protocol 2000/4000` 亦 PASS |
| 剩余未覆盖 resp DTO | 363 个（本轮不动，§5 给号段分布与打法；其中 320 个可被 shittim 直接覆盖） |

产物：

| 文件 | 说明 |
| --- | --- |
| `work\ba\proto\dto_schema_lobby.json` | 与 `dto_schema_academy.json` 同构的字段表（自包含，含 `ResponsePacket` 自身定义） |
| `work\ba\proto\gen_lobby.py` | 生成器（`--list` / `--protocol` / `--check` / `--check --protocol`） |
| `report\71-进大厅DTO批量补齐.md` | 本文件 |
| `report\_tmp\u_meta.py`、`u_build.py`、`u_validate.py` | 提取/构建/校验脚本（可复现，只读全部输入） |

---

## 0.1 方法（与 report/70 的差异）

沿用 report/70 已验证的三条判据，但**修掉了两处会导致大面积假阴性的坑**：

### (1) metadata 的 XOR 模型（比 report/70 记的更精确）

```
deob[p] = raw[p] ^ 0x66    若 p < 0x120  或  (p % 0x10000) ∈ [0x1000, 0x5000)
        = raw[p]            其余
```

- report/70 写的是"头前 `0x100` 字节"，实测是 **`0x120`**。`0x100..0x120` 这 32 字节也要 XOR，否则 header 里 `nestedTypes` 之后的表项全错位。
- 按上式算出来的 `deob` 与 `report\_tmp\patch\md_deob.bin` **逐字节一致（38,426,024 B，diff = 0）** → 可以直接用 `md_deob.bin` 读表。
- 表位置（实测，与任务书一致）：`methods@0x8B2C14/36B`、`typeDefinitions@0x1F02148/88B`、`fields@0x1B17590/12B`、`images@0x21F44A0/40B`、`string@0xEC9C8/7,109,768B`。

### (2) ★ 取字符串：不能"先解一层再 grep"，也不用 256×N 次搜索

`string` 堆里是**逐串一个随机单字节 XOR key**。本文件用的办法（`report\_tmp\u_meta.py`）：

1. 先把**所有被表引用过的 string 偏移**收集成集合 `R`（typedef 的 name/namespace、field 的 name、method 的 name、parameter/assembly/image 的 name）；
2. 字符串堆是**连续拼接**的（`str[i+1] = str[i] + len + 1`），所以对 `o ∈ R`，令 `o' = min{x ∈ R : x > o}`，则
   - 串体 = `heap[o : o'-1]`
   - **终止符那个字节 `heap[o'-1]` 就是该串的 key**
3. 用这个 key 解码，若全部可打印 ASCII ⇒ 命中；否则退化为在 `[o, o')` 窗口里用 256 个 key 逐个试。

效果：**35,105 个 typedef 的名字 0.1 秒解完，只有 102 个（0.29%）解不出**；字段名同理。
`AcademyDB`、`ParcelResultDB`、`AccountDB`、`FriendDB` 等全部一次命中，没有人名/字段名错位。

> ⚠️ 任务书强调的"不要用 `md_deob.bin` 下'不存在'结论"是对的：`md_deob.bin` 只去掉了页级 `0x66`，逐串 key 还在。但只要用上面的"偏移集 + 终止符 = key"办法读，`md_deob.bin` 本身完全够用（表结构 + 字符串都在里面）。

### (3) 字段类型判据

```
field.typeIndex - 1 == typeDefinition.byvalTypeIndex   ⇒ 该 typedef
```
命中率 99.4% 的说法在本轮复现：297 条字段里 **196 条**直接命中。剩下的 101 条是
- **泛型实例**（`List<>` / `Dictionary<>` / `Nullable<>`）→ 走 ti 投票；
- **"变体 Il2CppType 索引"**：同一个运行时类型在别的 image 里有一套平行索引（例如 `long` 有 `50531` 和 `50534`，`string` 有 `61196` 和 `61200`，`int` 有 `50495` 和 `50500`）。这一类**不能**靠 byval 反查，也不在 typedef 表里。

### (4) ★ ti 投票表（本轮的关键提效手段）

关键观察：**`ti` 是"泛型实例/变体"的全局唯一编号**，同一个 `ti` 在所有类型里含义相同（`21561` 在哪都是 `List<CharacterDB>`）。于是：

| 投票来源 | 覆盖 |
| --- | --- |
| `shittim_types.json` 与 metadata **精确配对**的 747 个类型（821 条里 747 条字段名/顺序完全一致） | 给出 `ti → C# 类型串` |
| `dto_schema.json` 的 `typeIndex` 字段（112 个类型） | 补充 173 个泛型 `ti` |
| `dto_schema_academy.json` 的 `ti` 字段 | 同上 |
| **字段名投票**（同名同型，960 个名字） | 兜底，覆盖上面都没见过的 `ti` |

这样 297 条字段里只有 2 条落空。

---

## 0.2 三条新判据（report/70 没有的，会直接影响正确性）

### A. 继承必须展开（否则字段缺）

`ItemDB` 的 metadata 自有字段只有 `Expires` 一条，看着像"挖漏了"，实测不是：

```
ItemDB (td=12060) parent byval 41474 = ConsumableItemBaseDB (td=11970)
    ConsumableItemBaseDB: ServerId / UniqueId / StackCount   ← 3 个
    ItemDB 自有        : Expires
  ⇒ ItemDB 完整 = ServerId, UniqueId, StackCount, Expires     （4 个）
```

同理 `EquipmentDB` = 4 自有 + 3 继承 = 7；`FurnitureDB` = 6 + 3 = 9。
`ParcelBase`（`MX.GameLogic.Parcel`）是**空基类**（0 字段），只是给 `CharacterDB`/`WeaponDB`/`GearDB`/`CostumeDB`/`EmblemDB`/`StickerDB`/`MemoryLobbyDB`/`IdCardBackgroundDB` 挂类型用的。

`gen_lobby.py` 里 `flat_fields()` 会沿 `base` 链展开，派生覆盖基类同名。

### B. 嵌套类型的 namespace 是空串

`EchelonStatusFlag` 是声明在 `EchelonDB` 里的嵌套枚举，metadata 里 `namespaceIndex` 指向**空串**。
处理：按"引用它的那个类型的 namespace"归属（嵌套类型与声明类型同 namespace），并在条目里标 `"nested": true`。共 1 个类型走这条路。

### C. 信封根是 `ResponsePacket`，而它的父类 `BasePacket` 不能展开

```
BasePacket (td=10774): SessionKey (SessionKey 对象) / OSType (int)
ResponsePacket (td=10776) : BasePacket
  own 6 字段: ServerTimeTicks / ServerNotification / MissionProgressDBs /
              EventMissionProgressDBDict / BattlePassMissionProgressDBDict / StaticOpenConditions
```

但 report/61、65、70 已实测跑通的包里**只有** `Protocol` + 这 6 个字段，没有 `SessionKey`/`OSType`。
所以：`ResponsePacket` 在 schema 里标 `envelopeRoot: true` + `baseNotSerialized: "BasePacket"`，默认不展开；需要时 `gen_lobby.py --with-session` 可以强行加上（输出 `SessionKey: {AccountServerId, MxToken}` / `OSType: 0`）。

---

## 1. 补齐清单

### 1.1 本轮新补的 45 个（按协议号）

`自有字段` = 该 DTO 自己声明的字段；`整包字段` = 自有 + `ResponsePacket` 的 6 个（不含 `Protocol`）。

| 协议号 | 协议名 | Response DTO | 自有字段 | 整包字段 |
| ---: | --- | --- | ---: | ---: |
| 2001 | `Character_Transcendence` | `CharacterTranscendenceResponse` | 2 | 8 |
| 2002 | `Character_ExpGrowth` | `CharacterExpGrowthResponse` | 3 | 9 |
| 2003 | `Character_FavorGrowth` | `CharacterFavorGrowthResponse` | 3 | 9 |
| 2005 | `Character_UnlockWeapon` | `CharacterUnlockWeaponResponse` | 1 | 7 |
| 2006 | `Character_WeaponExpGrowth` | `CharacterWeaponExpGrowthResponse` | 1 | 7 |
| 2007 | `Character_WeaponTranscendence` | `CharacterWeaponTranscendenceResponse` | 1 | 7 |
| 2008 | `Character_SetFavorites` | `CharacterSetFavoritesResponse` | 1 | 7 |
| 2009 | `Character_SetCostume` | `CharacterSetCostumeResponse` | 2 | 8 |
| 2010 | `Character_BatchSkillLevelUpdate` | `CharacterBatchSkillLevelUpdateResponse` | 2 | 8 |
| 2011 | `Character_PotentialGrowth` | `CharacterPotentialGrowthResponse` | 2 | 8 |
| 3006 | `Equipment_BatchGrowth` | `EquipmentBatchGrowthResponse` | 4 | 10 |
| 4001 | `Item_Sell` | `ItemSellResponse` | 1 | 7 |
| 4002 | `Item_Consume` | `ItemConsumeResponse` | 2 | 8 |
| 4003 | `Item_Lock` | `ItemLockResponse` | 1 | 7 |
| 4004 | `Item_BulkConsume` | `ItemBulkConsumeResponse` | 2 | 8 |
| 4005 | `Item_SelectTicket` | `ItemSelectTicketResponse` | 2 | 8 |
| 4006 | `Item_AutoSynth` | `ItemAutoSynthResponse` | 1 | 7 |
| 5002 | `Echelon_PresetList` | `EchelonPresetListResponse` | 1 | 7 |
| 5003 | `Echelon_PresetSave` | `EchelonPresetSaveResponse` | 1 | 7 |
| 5004 | `Echelon_PresetGroupRename` | `EchelonPresetGroupRenameResponse` | 1 | 7 |
| 12001 | `MemoryLobby_SetMain` | `MemoryLobbySetMainResponse` | 1 | 7 |
| 12002 | `MemoryLobby_UpdateLobbyMode` | `MemoryLobbyUpdateLobbyModeResponse` | **0** | 6 |
| 12003 | `MemoryLobby_Interact` | `MemoryLobbyInteractResponse` | **0** | 6 |
| 20001 | `Cafe_Ack` | `CafeAckResponse` | 1 | 7 |
| 20002 | `Cafe_Deploy` | `CafeDeployFurnitureResponse` | 3 | 9 |
| 20003 | `Cafe_Relocate` | `CafeRelocateFurnitureResponse` | 2 | 8 |
| 20004 | `Cafe_Remove` | `CafeRemoveFurnitureResponse` | 2 | 8 |
| 20005 | `Cafe_RemoveAll` | `CafeRemoveAllFurnitureResponse` | 2 | 8 |
| 20006 | `Cafe_Interact` | `CafeInteractWithCharacterResponse` | 3 | 9 |
| 20007 | `Cafe_ListPreset` | `CafeListPresetResponse` | 2 | 8 |
| 20008 | `Cafe_RenamePreset` | `CafeRenamePresetResponse` | **0** | 6 |
| 20009 | `Cafe_ClearPreset` | `CafeClearPresetResponse` | **0** | 6 |
| 20010 | `Cafe_UpdatePresetFurniture` | `CafeUpdatePresetFurnitureResponse` | **0** | 6 |
| 20011 | `Cafe_ApplyPreset` | `CafeApplyPresetResponse` | 2 | 8 |
| 20012 | `Cafe_RankUp` | `CafeRankUpResponse` | 3 | 9 |
| 20013 | `Cafe_ReceiveCurrency` | `CafeReceiveCurrencyResponse` | 3 | 9 |
| 20014 | `Cafe_GiveGift` | `CafeGiveGiftResponse` | 2 | 8 |
| 20015 | `Cafe_SummonCharacter` | `CafeSummonCharacterResponse` | 2 | 8 |
| 20016 | `Cafe_TrophyHistory` | `CafeTrophyHistoryResponse` | 1 | 7 |
| 20017 | `Cafe_ApplyTemplate` | `CafeApplyTemplateResponse` | 2 | 8 |
| 20018 | `Cafe_Open` | `CafeOpenResponse` | 2 | 8 |
| 20019 | `Cafe_Travel` | `CafeTravelResponse` | 3 | 9 |
| 20020 | `Cafe_SummonCharacterTicketUse` | `CafeSummonCharacterTicketUseResponse` | 3 | 9 |
| 20021 | `Cafe_PresetDetail` | `CafePresetDetailResponse` | 1 | 7 |
| 20022 | `Cafe_UpdateCopyPresetFurniture` | `CafeUpdateCopyPresetFurnitureResponse` | **0** | 6 |

合计：自有字段 **74** 条，整包 **74 + 45×6 = 344** 条字段。

### 1.2 号段内另外 5 个此前已被覆盖的（一并重新从 metadata 提取，保证号段无洞）

| 协议号 | 协议名 | Response DTO | 自有字段 | 整包字段 | 旧归属 |
| ---: | --- | --- | ---: | ---: | --- |
| 2000 | `Character_List` | `CharacterListResponse` | 4 | 10 | `dto_schema.json` |
| 4000 | `Item_List` | `ItemListResponse` | 2 | 8 | `dto_schema.json` |
| 5000 | `Echelon_List` | `EchelonListResponse` | 2 | 8 | `dto_schema.json` |
| 12000 | `MemoryLobby_List` | `MemoryLobbyListResponse` | 1 | 7 | `dto_schema.json` |
| 20000 | `Cafe_Get` | `CafeGetInfoResponse` | 3 | 9 | `dto_schema.json` |

为什么要把它们也收进来：任务要求 `gen_lobby.py --protocol 2000` / `--protocol 4000` 能出包，而这两个号正好是"旧 schema 已覆盖"的。收进来后 **6 个进大厅号段 = 50 个协议，无洞**。这 5 个的字段名与旧 schema 交叉校验 **0 不一致**（见 §2.3）。

### 1.3 递归闭包里的 46 个嵌套类型

`自有/全部` 两列是"自身字段 / 展开继承后字段"。

| 类型 | namespace | 自有/全部 | base |
| --- | --- | --- | --- |
| `BasisPoint` | MX.Core.Math | 3/3（**opaque**） | - |
| `AcademyLocationDB` | MX.GameLogic.DBModel | 3/3 | - |
| `AccountAttachmentDB` | MX.GameLogic.DBModel | 2/2 | - |
| `AccountCurrencyDB` | MX.GameLogic.DBModel | 4/4 | - |
| `AccountDB` | MX.GameLogic.DBModel | 22/22 | - |
| `CafeDB` | MX.GameLogic.DBModel | 13/13 | - |
| `CafePresetDB` | MX.GameLogic.DBModel | 4/4 | - |
| `CafeProductionDB` | MX.GameLogic.DBModel | 4/4 | - |
| `CharacterDB` | MX.GameLogic.DBModel | 15/15 | ParcelBase |
| `ConsumableItemBaseDB` | MX.GameLogic.DBModel | 3/3 | ParcelBase |
| `ConsumeResultDB` | MX.GameLogic.DBModel | 6/6 | - |
| `CostumeDB` | MX.GameLogic.DBModel | 2/2 | ParcelBase |
| `EchelonDB` | MX.GameLogic.DBModel | 11/11 | - |
| `EchelonPresetDB` | MX.GameLogic.DBModel | 10/10 | - |
| `EchelonPresetGroupDB` | MX.GameLogic.DBModel | 4/4 | - |
| `EchelonStatusFlag` | MX.GameLogic.DBModel | ENUM（嵌套，ns 推断） | - |
| `EmblemDB` | MX.GameLogic.DBModel | 2/2 | ParcelBase |
| `EquipmentDB` | MX.GameLogic.DBModel | **4/7** | ConsumableItemBaseDB |
| `FriendDB` | MX.GameLogic.DBModel | 10/10 | - |
| `FurnitureDB` | MX.GameLogic.DBModel | **6/9** | ConsumableItemBaseDB |
| `GearDB` | MX.GameLogic.DBModel | 7/7 | ParcelBase |
| `IdCardBackgroundDB` | MX.GameLogic.DBModel | 2/2 | ParcelBase |
| `ItemDB` | MX.GameLogic.DBModel | **1/4** | ConsumableItemBaseDB |
| `MemoryLobbyDB` | MX.GameLogic.DBModel | 1/1 | ParcelBase |
| `MissionProgressDB` | MX.GameLogic.DBModel | 6/6 | - |
| `OpenConditionDB` | MX.GameLogic.DBModel | 13/13 | - |
| `RaidSeasonRankingHistoryDB` | MX.GameLogic.DBModel | 7/7 | - |
| `StickerDB` | MX.GameLogic.DBModel | 1/1 | ParcelBase |
| `VisitingCharacterDB` | MX.GameLogic.DBModel | 2/2 | - |
| `WeaponDB` | MX.GameLogic.DBModel | 5/5 | ParcelBase |
| `ParcelBase` | MX.GameLogic.Parcel | 0/0（空基类） | - |
| `ParcelInfo` | MX.GameLogic.Parcel | 4/4 | - |
| `ParcelKeyPair` | MX.GameLogic.Parcel | 2/2 | - |
| `ParcelResultDB` | MX.GameLogic.Parcel | 26/26 | - |
| `ResponsePacket` | MX.NetworkProtocol | 6/6（**信封根**） | - |
| `ServerNotificationFlag` | MX.NetworkProtocol | ENUM | - |
| `AccountState` / `ContentType` / `CurrencyTypes` / `EchelonExtensionType` / `EchelonType` / `FurnitureLocation` / `MultipleConditionCheckType` / `OpenConditionContent` / `ParcelType` / `WeekDay` | FlatData | ENUM（10 个） | - |

嵌套字段合计 **211** 条（297 − 86）。

---

## 2. 仍缺的与原因（诚实清单）

### 2.1 6 个 `fieldCount = 0` 的 DTO（不是缺口）

| 协议号 | DTO | metadata `fieldCount` | 判定 |
| ---: | --- | ---: | --- |
| 12002 | `MemoryLobbyUpdateLobbyModeResponse` | 0 | 只有 `ResponsePacket` 基类 |
| 12003 | `MemoryLobbyInteractResponse` | 0 | 同上 |
| 20008 | `CafeRenamePresetResponse` | 0 | 同上 |
| 20009 | `CafeClearPresetResponse` | 0 | 同上 |
| 20010 | `CafeUpdatePresetFurnitureResponse` | 0 | 同上 |
| 20022 | `CafeUpdateCopyPresetFurnitureResponse` | 0 | 同上 |

依据：typedef 的 `fieldStart` 与 `fieldCount` 直接读出来是 0，且这 6 个在 `shittim_types.json` 里**根本没有声明**（821 条里没有），说明客户端这个版本的 C# 类确实没有自有成员。上一版可能返回 `CafeDB`/`CafePresetDB`，但**本版本客户端不会去读**。
出包时就是 `Protocol` + 6 个基类字段，已用 `--check` 验证能 `json.loads`。

### 2.2 全 schema 唯一 2 条 `unknown`

| 类型.字段 | `ti` | 为什么解不出 | 处理 |
| --- | ---: | --- | --- |
| `ParcelResultDB.ParcelResultStepInfoList` | 22563 | byval 反查落空（变体索引）；ti 投票表 173 个泛型里没有它；字段名投票表也没有同名项 | `type: "unknown"` + `hint: "List<ParcelResultStepInfo>"`（`ParcelResultStepInfo` 这个 typedef 真实存在，td=11872，只是"是不是 List<>"没证据）。生成时给 `[]` |
| `EchelonPresetGroupDB.PresetDBs` | 10269 | 同上；`PresetDBs` 在全语料里只出现这一次 | `type: "unknown"` + `hint: "List<EchelonPresetDB>"`（按"容器名前缀 + PresetDB"推的，`EchelonPresetDB` 真实存在，td=12013）。生成时给 `[]` |

两条都**没有编造类型名**：`type` 保持 `unknown`，`hint` 单独一个键。

### 2.3 `BasisPoint` 标成 opaque（沿用 report/70 的结论）

`BasisPoint`（`MX.Core.Math`，td=12233）metadata 里有 7 个字段，但只有 `rawValue`（long）是实例字段，其余（`Multiplier`/`OneOver10_4`/`Zero`/`One`/`Epsilon`/`DoubleEpsilon`）连 `ti` 都不走 byval（是 static readonly）。到底序列化成"数字"还是"对象"没证据，所以 `"opaque": true`，生成时给 `null`。
好在它只出现在 `ParcelInfo.Multiplier/Probability`，而 `ParcelInfo` 只出现在 `List<ParcelInfo>` 里，默认是空数组 ⇒ **本轮 50 个包里没有任何一个真正序列化出 `BasisPoint`**。

### 2.4 交叉校验：与旧产物 0 冲突

| 对照对象 | 重叠类型 | 字段名/顺序不一致 |
| --- | ---: | ---: |
| `dto_schema.json`（112 → 命中 28 个类型） | 28 | **0** |
| `dto_schema_academy.json`（命中 8 个类型） | 8 | **0** |
| `shittim_types.json`（45 个缺口里的 39 个） | 39 | **0** |

也就是说：本轮的提取**没有推翻既有任何一条结论**，只是把面扩开 + 补上继承。

### 2.5 刻意没做的

- **没展开 `BasePacket`**（`SessionKey`/`OSType`）：与已跑通的包保持一致，`--with-session` 可开关（见 §0.2-C）。
- **没给 `Request` DTO 建表**：任务只要 Response。`RequestPacket` 的 5 个字段（含 `_counter` 这类 static）在 metadata 里有，需要时可照同样方法加。
- **没解枚举成员值**：枚举在 JSON 里就是整数，默认给 `0`，成员值需要读 `fieldDefaultValues` 表，本轮用不上。

---

## 3. 泛型推断的置信度表

297 条自有字段的判定来源与置信度：

| 判定方式 | 条数 | 占比 | 置信度 | 判据 |
| --- | ---: | ---: | --- | --- |
| `byval`（`ti-1 == byval`） | 196 | 66.0% | **精确** | typedef 表直接给出类型名，无歧义 |
| `ti-vote` 无分歧（全票） | 30 | 10.1% | **高** | 所有出现该 `ti` 的已知字段都是同一个类型串 |
| `ti-vote` 有分歧 | 62 | 20.9% | **中**（票型见下） | 取多数派；分歧来自不同版本 schema 的个别写法 |
| `name-vote` 字段名投票 | 7 | 2.4% | **中低** | 同名同型；仅用于 `ti` 完全没票的变体索引 |
| `none`（unknown） | 2 | 0.7% | **无** | 见 §2.2 |

### 3.1 `ti-vote` 有分歧的 62 条的票型分布

| 票型 | 含义 | 条数 | 典型字段 |
| --- | --- | ---: | --- |
| `vote(50/66)` | 50 票 `List<long>?`，其余是 `long[]?` 一类等价写法 | 16 | `RemovedItemIds`、`EquipmentServerIds`、`CharacterNewUniqueIds` |
| `vote(32/35)` | 32 票 `List<ParcelInfo>?` | 3 | `DisplaySequence`、`ParcelForMission`、`ParcelInfosInMailBox` |
| `vote(13/17)` | 13 票 `List<CharacterDB>?` | 4 | `CharacterDBs`、`TSSCharacterDBs` |
| `vote(10/12)` | 10 票 `Dictionary<long, long>?` | 6 | `UsedItemServerIdAndRemainingCounts`、`DeployCountByFurnitureId` |
| `vote(7/9)` | 7 票 `List<FurnitureDB>?` | 9 | `CafeDB.FurnitureDBs` 等 9 处 |
| `vote(7/8)` | 7 票 `List<CafeDB>?` | 6 | `CafeDBs` |
| `vote(5/9)` | 5 票 `List<ItemDB>?` | 3 | `ItemListResponse.ItemDBs` |
| `vote(4/5)` | 4 票 `Dictionary<CurrencyTypes, long>?` | 2 | `CurrencyDict`、`CurrencyDict_Obsolete` |
| `vote(2/4)`、`vote(3/5)`、`vote(1/2)` 等 | 2~3 票 | 13 | `WeaponDBs`、`CostumeDBs`、`StickerDBs`、`MissionProgressDBs` |

> **分歧来源已定位**：`shittim_types.json` 是**某个版本**的 C# 声明，`dto_schema.json` / `dto_schema_academy.json` 是**另一个版本**的推测。差异全是"写法不同但语义相同"：
> `List<long>?` vs `long[]?`、`Dictionary<long,List<X>>` vs `Dictionary<long, List<X>>`（空格/可空注解）、`IEnumerable<X>?` vs `List<X>?`。
> 归一化之后（`parse_cs()`：`IEnumerable/[]/IReadOnlyList → List<>`；引用类型的 `?` 去掉；值类型的 `?` → `Nullable<>`）**全部落到同一个类型上**，所以这些"分歧"不影响结论。

### 3.2 `name-vote` 的 7 条（全部逐条可核）

| 类型.字段 | 结论 | 票型 | 旁证 |
| --- | --- | --- | --- |
| `FriendDB.Level` | `int` | 7/8 | `AccountDB.Level`、`CharacterDB.Level`、`EquipmentDB.Level` 全是 `int` |
| `FriendDB.LastConnectTime` | `DateTime` | 2/2 | `AccountDB.LastConnectTime` 同为 `DateTime`（ti 变体 42730 vs 42727） |
| `FriendDB.AttachmentDB` | `AccountAttachmentDB` | 2/3 | 全语料唯一同名类型 |
| `ParcelResultDB.EquipmentDBs` | `List<EquipmentDB>` | 4/5 | `EquipmentBatchGrowthResponse.EquipmentDBs` 同名字段 |
| `ParcelResultDB.ItemDBs` | `List<ItemDB>` | 2/3 | `ItemListResponse.ItemDBs` 同名字段 |
| `ParcelResultDB.FurnitureDBs` | `List<FurnitureDB>` | 6/8 | `CafeDB.FurnitureDBs` 同名字段 |
| `ParcelResultDB.IdCardBackgroundDBs` | `List<IdCardBackgroundDB>` | 1/1 | 1 票，但元素类型 `IdCardBackgroundDB`（td=12057）在 metadata 里真实存在，故采纳 |

### 3.3 类型分布（297 条）

| kind | 条数 |
| --- | ---: |
| `scalar` | 124 |
| `list` | 66 |
| `object` | 60 |
| `enum` | 14 |
| `dict` | 13 |
| `datetime` | 11 |
| `nullable` | 7 |
| `unknown` | 2 |

---

## 4. `gen_lobby.py` 用法

```bash
cd work\ba\proto
```

### 4.1 列出支持的全部协议

```
> python gen_lobby.py --list
proto   DTO                                        own      total  namespace
2000    CharacterListResponse                      4        10     MX.NetworkProtocol
2001    CharacterTranscendenceResponse             2        8      MX.NetworkProtocol
...
20022   CafeUpdateCopyPresetFurnitureResponse      0        6      MX.NetworkProtocol

共 50 个协议 / 96 个类型定义（含嵌套 DB 类）
```

### 4.2 输出某个协议的完整响应包

```
> python gen_lobby.py --protocol 2000
{
  "Protocol": 2000,
  "ServerTimeTicks": 0,
  "ServerNotification": 0,
  "MissionProgressDBs": [],
  "EventMissionProgressDBDict": {},
  "BattlePassMissionProgressDBDict": {},
  "StaticOpenConditions": [],
  "CharacterDBs": [],
  "TSSCharacterDBs": [],
  "WeaponDBs": [],
  "CostumeDBs": []
}
```

```
> python gen_lobby.py --protocol 4000
{
  "Protocol": 4000,
  "ServerTimeTicks": 0,
  "ServerNotification": 0,
  "MissionProgressDBs": [],
  "EventMissionProgressDBDict": {},
  "BattlePassMissionProgressDBDict": {},
  "StaticOpenConditions": [],
  "ItemDBs": [],
  "ExpiryItemDBs": []
}
```

嵌套对象会**递归展开**，例如 `--protocol 2001`：

```
{
  "Protocol": 2001,
  ...
  "CharacterDB": {
    "ServerId": 0, "UniqueId": 0, "StarGrade": 0, "Level": 0, "Exp": 0,
    "FavorRank": 0, "FavorExp": 0, "PublicSkillLevel": 0, "ExSkillLevel": 0,
    "PassiveSkillLevel": 0, "ExtraPassiveSkillLevel": 0, "LeaderSkillLevel": 0,
    "IsFavorite": false, "EquipmentServerIds": [], "PotentialStats": {}
  },
  "ParcelResultDB": {
    "AccountDB": { "ServerId": 0, "Nickname": "", ... },
    ...
  }
}
```

### 4.3 自检

```
> python gen_lobby.py --check                  # 全部 50 个包
> python gen_lobby.py --check --protocol 4000 # 只查 4000 号段
```

`--check` 会做 5 件事，全部 PASS 才 exit 0：

1. **静态检查**：每个类型有 namespace / 字段三件套齐全 / 无重名 / `object`·`base` 引用全都有定义（当前 0 未定义）；
2. **生成 + 类型校验**：逐字段核对"齐全、无多余键、JSON 类型与 schema 一致"，并做 `json.dumps → json.loads` 往返；
3. **信封断言**：首键是 `Protocol`、协议号正确、`ResponsePacket` 6 个基类字段全在；
4. **递归完整性**：每个包里的嵌套对象逐层枚举（最多 12 层）；
5. **核心断言**：13 个黄金 DTO 的协议号 + 字段集 + `ItemDB` 继承展开 `["ServerId","UniqueId","StackCount","Expires"]`。

当前输出：

```
== 静态检查 ==
   协议数    : 50
   schema 类型: 96
   结构性错误 : 0
   unknown 字段: 2（不判 FAIL，生成时按 hint 给空容器）
   object/base 引用未定义: 0
...
---- check: PASS ----
```

### 4.4 其它开关

| 开关 | 作用 |
| --- | --- |
| `--dto ItemDB` | 生成任意已收录类型（不只是 resp，嵌套 DB 类也行；有继承会自动展开） |
| `--set CharacterDB.Level=90` | 覆写字段（支持点路径） |
| `--out p.json` | 写文件（相对路径按当前目录算） |
| `--shallow` | 嵌套对象给 `null`，不递归 |
| `--no-base` | 去掉 `ResponsePacket` 的 6 个基类字段（继承链照常展开） |
| `--with-session` | 额外输出 `BasePacket` 的 `SessionKey` / `OSType`（默认不加，见 §0.2-C） |
| `--unknown-as null\|empty` | 2 条 `unknown` 字段的给法（默认 `hint`：list→`[]`、dict→`{}`、其余→`null`） |
| `--indent N` | 缩进（默认 2） |
| `--auto-protocol` | 协议号取 schema 登记值（`--dto` 时用） |

### 4.5 注意

- 生成器**只依赖** `dto_schema_lobby.json`，不 import / 不读写别人的产物（`dto_schema.json`、`gen_academy.py` 只在构建阶段被 `report\_tmp\u_build.py` 只读引用）。
- 默认值是"结构完整"而不是"业务正确"：`0` / `""` / `false` / `[]` / `{}` / `null` / 固定 ISO 时间 `2026-11-14T00:00:00`。真要上线得用 `--set` 或另外的种子注入（见 report/69、73）。

---

## 5. 剩余未覆盖 DTO 的号段分布（给后续批量做参考）

口径：`protocol_map.json` 里 `id` 非空且带 `resp` 名的协议 → **442 个具名 resp DTO**。任务书报 444：差的 2 个是 `Audit_GachaStatistics → AuditGachaStatisticsResponse`、`System_Version → SystemVersionResponse`，这两条在 `protocol_map.json` 里 `id` 是 `null`（不在任何号段内），所以口径里剔掉了。
本轮之后已覆盖 **79 个**（旧 schema 34 + 本轮 45），**仍缺 363 个**。

| 号段 | 仍缺 | 号段 | 仍缺 |
| ---: | ---: | ---: | ---: |
| **1000**（Account） | **14** | 25000 | 1 |
| 6000 | 21 | 26000 | 2 |
| 7000 | 5 | 27000 | 3 |
| 8000 | 3 | 28000 | 20 |
| 9000 | 1 | 29000 | 3 |
| 10000 | 16 | **30000** | **53** |
| 11000 | 1 | 31000 | 1 |
| 15000 | 3 | 33000 | 3 |
| 16000 | 1 | 34000 | 2 |
| 17000 | 19 | **35000** | **42** |
| 18000 | 2 | 36000 | 1 |
| 19000 | 20 | 37000 | 2 |
| 21000 | 15 | 38000 | 4 |
| 22000 | 14 | 39000 | 6 |
| 23000 | 4 | 40000 | 6 |
| 42000 | 18 | 41000 | 1 |
| 43000 | 13 | 44000 | 2 |
| 45000 | 9 | 46000 | 2 |
| 47000 | 2 | 48000 | 7 |
| 49000 | 3 | 50000 | 2 |
| 51000 | 7 | 52000 | 1 |
| 53000 | 1 | 54000 | 4 |
| 90000 | 3 | | |
| **合计** | **363** | | |

**后续批量的三个抓手（按性价比排序）**

1. **30000 段（53 个）+ 35000 段（42 个）** 是最大的两块，合计 95 个，占剩下的 26%。打法完全一样：把 `report\_tmp\u_build.py` 的 `resp_roots()` 里 `segs` 换成对应号段，跑一遍即可；递归闭包会自动扩（预计每个号段新增 20~40 个嵌套类型）。
2. **320/363 个能被 `shittim_types.json` 直接覆盖**（747 个精确配对的类型里）。对这批，"字段名 + 字段类型"两边都有，做交叉校验几乎零风险。
3. **剩下的 43 个** shittim 里没有：走本文件的 `ti-vote + name-vote + unknown+hint` 三件套，预计 unknown 率与本轮同级（0.7% 量级）。其中要注意**继承**（§0.2-A）——凡是 `ItemDB`/`EquipmentDB`/`FurnitureDB`/`GearDB` 这类 DB 类，务必展开 `base`，否则会稳定少 3 个字段。

另外提醒：`1000 段（Account）` 只剩 14 个，但那是最敏感的一段（登录链路），建议单独一轮、逐个 `--check` + 与 report/61 的 `AccountAuthResponse` 27 字段对表。

---

## 6. 复现步骤

```bash
# 1) 重新从 metadata 生成 schema（约 6 秒，只读 metadata + 只读引用三个旧产物）
python report\_tmp\u_build.py            # → work\ba\proto\dto_schema_lobby.json

# 2) 交叉校验 + 报告数字（39/39、74/74、0 冲突 都来自这里）
python report\_tmp\u_validate.py

# 3) 生成器自检
cd work\ba\proto && python gen_lobby.py --check
```

`report\_tmp\u_meta.py` 是纯只读的 metadata 访问层（自动重算 `deob`，并与 `md_deob.bin` 比对断言一致），可单独跑 `python report\_tmp\u_meta.py` 看表规模：
`NT=35105 NM=263095 NF=191990`、`string heap=7,109,768 B`、`type_index=26518 名字`。

---

## 7. 纪律与影响面

- **未连手机 / 未连服务器**：全程只读本地文件，无 adb / ssh / 任何网络请求。
- **未碰 `libtprt.so`**。
- **未修改别人的产物**：`dto_schema.json`、`gen_default.py`、`protocol_map.json`、`dto_schema_academy.json`、`gen_academy.py` 全部只读引用；`work\ba\proto\dto_schema_lobby.json`、`work\ba\proto\gen_lobby.py`、本文件、`report\_tmp\u_*.py` 是本轮新增。
  - 注：`dto_schema_academy.json`（27,765 → 28,427 B @5:59:49）和 `gen_academy.py`（14,876 → 15,091 B @5:59:56）在 5:59 被**另一轮 agent** 更新过；本轮的构建读到的是更新后的版本，全程未写入这两个文件（本轮的三个产物时间戳都在 6:07 之后）。
- `report\_tmp\t2001.json`（`--set` 测试产物）已在收尾时删除。
