# 客户端 ShopRecruitDB（招募卡池）DTO 字段 vs 我方实发 —— 只读比对

- 生成时间：2026-11-19
- 范围：**只比对字段集合**（字段名 / 类型 / 可空 / 默认值 / 是否下发），不做联网、不碰服务器、不修改任何既有文件。
- 判定依据全部来自本地明文文件 + 本地 metadata（`report/_tmp/patch/md_deob.bin`），每条结论后面都给出原文或可复现命令。

---

## 0. 结论（先看这段）

| 问题 | 答案 |
|---|---|
| 客户端 `ShopRecruitDB` 有几个字段 | **4 个**：`Id`(long) / `SalesStartDate`(DateTime) / `SalesEndDate`(DateTime) / `UpdateDate`(DateTime) |
| 我方漏发了哪些 | **没有漏发**。客户端 4 个字段 → 我方 529 条每条都是 4 个键，**4/4 全覆盖** |
| 我方多发了哪些 | **没有多发**（元素级 0 个；响应对象上多一个继承自 `BasePacket` 的 `Protocol`，是协议本来就有的） |
| 官方是不是也只有 4 个键 | 是。官方 1017 的 529 条元素键集合 = `{Id, SalesStartDate, SalesEndDate, UpdateDate}`，与我方 **规范化 JSON 逐字节相同**（sha256 一致） |
| 有没有「客户端有、官方省略、我方也没发」的字段 | **不存在**。客户端 DTO 里就没有第 5 个字段，"省略"无从谈起 |
| 有没有文本/本地化字段（`LocalizeKey`/`Name`/`Title`/`Text`/`TabName`/`LocalizeEtcId`…） | **客户端 `ShopRecruitDB` 里一个都没有**，4 个字段全是数值/时间类型，连 `string` 都没有 → 我方不可能"漏发文本字段" |

> 因此：**「客户端 DTO 有、我方没发」这条假设不成立**，招募界面的红字不能用 DTO 缺字段来解释。
> 客户端这条链上唯一的"文本来源"是它**本地**的 `LocalizeGachaShop` Excel 表（§5.4，主键 `GachaShopId`），那是客户端自己的数据，不是服务端字段。
> 比对过程中另发现同一响应对象上有两处**非元素级**差异（嵌套子响应信封键、LoginSync 顶层键），记录在 §6，供后续排查参考（它们不是招募特有，见 §6.1 的系统性证据）。

---

## 1. 材料与路径核对

| 任务给定路径 | 实际情况 | 状态 |
|---|---|---|
| `work\ba\proto\dto_schema_full_v2.json` | 存在，710 个 DTO，2,370,325 B | ✅ 本报告主依据 |
| `work\ba\srv_src\Shittim-Server\Core\NetworkProtocol\NetworkProtocol.cs` | **该路径不存在**。服务端 DTO 实际在 `work\ba\srv_src\Schale\MX\NetworkProtocol\NetworkProtocol.cs`（L6671–6681）与 `work\ba\srv_src\Schale\MX\GameLogic\DBModel\DBModel.cs`（L2273–2284） | ⚠️ 路径需更正，内容已核对 |
| `work\ba\data\_tmp\our_shoprecruits_20261119.json` | 存在，顶层 3 键，`ShopRecruits` = 529 条 | ✅ |
| `work\ba\data\_tmp\our_loginsync_inner_20261119.json` | 存在，32 个顶层键，含 `ShopGachaRecruitListResponse` | ✅ |
| `report\_tmp\official_decoded_201\02_1017_api_account_loginsync.response.json` | 存在，`{meta, plain, inner}`，`inner.ShopGachaRecruitListResponse.ShopRecruits` = 529 条 | ✅ |

同一目录下另有 `dto_schema.json`(112 DTO) / `dto_schema_full.json`(708) / `dto_schema_lobby.json`(97) / `dto_schema_academy.json`(18)。这三个 Recruit DTO 在 `dto_schema.json` 与 `dto_schema_full.json` 里的字段清单与 v2 **完全一致**（行号按 `ShopFreeRecruitHistoryDB` / `ShopGachaRecruitListResponse` / `ShopRecruitDB` 顺序：`dto_schema.json` L4144 / L4172 / L4261；`dto_schema_full.json` L70686 / L70719 / L71746），不存在版本间漂移。

---

## 2. 客户端 DTO 完整字段清单（原文）

`dto_schema_full_v2.json` 的字段来源是 IL2CPP 解混淆 metadata（`report/_tmp/patch/md_deob.bin` 的 typedef/fields 表，见 `proto/build_schema.py` 头注释），不是从抓包反推，所以字段清单是**结构完整的声明**，不是我方观测结果。

### 2.1 `ShopRecruitDB` — 4 个字段（`dto_schema_full_v2.json` L92764–L92804）

```json
 "ShopRecruitDB": {
  "fieldCount": 4,
  "fields": [
   {
    "conf": "high",
    "kind": "scalar",
    "name": "Id",
    "src": "byval",
    "ti": 50531,
    "type": "long"
   },
   {
    "conf": "high",
    "kind": "datetime",
    "name": "SalesStartDate",
    "src": "byval",
    "ti": 42727,
    "type": "DateTime"
   },
   {
    "conf": "high",
    "kind": "datetime",
    "name": "SalesEndDate",
    "src": "byval",
    "ti": 42727,
    "type": "DateTime"
   },
   {
    "conf": "high",
    "kind": "datetime",
    "name": "UpdateDate",
    "src": "byval",
    "ti": 42727,
    "type": "DateTime"
   }
  ],
  "namespace": "MX.GameLogic.DBModel",
  "referenced": [],
  "support": true,
  "tdIndex": 12143
 },
```

**原始 metadata 复核**（直接读 `md_deob.bin`，tdIndex 12143）：

```
tdInfo(12143): full=MX.GameLogic.DBModel.ShopRecruitDB  fieldCount=4  methodCount=9  token=33566576
field 53837  '<Id>k__BackingField'              typeIndex 50531 -> System.Int64
field 53838  '<SalesStartDate>k__BackingField'  typeIndex 42727 -> System.DateTime
field 53839  '<SalesEndDate>k__BackingField'    typeIndex 42727 -> System.DateTime
field 53840  '<UpdateDate>k__BackingField'      typeIndex 42727 -> System.DateTime
fieldDefaultValues 表（81939 条默认值记录）中没有任何一条指向 53837–53840
```

- 4 个字段 = 4 个自动属性，**没有**隐藏字段、静态字段、常量字段。
- 类型索引全部是 `System.Int64` / `System.DateTime`（`type_index_map.json` 已核对 50531=System.Int64、42727=System.DateTime）。

**字段属性表**

| # | 字段名 | C# 类型 | 可空 | 默认值 | 依据 |
|---|---|---|---|---|---|
| 1 | `Id` | `long` (`System.Int64`) | 否（值类型） | `0` | metadata typeIndex 50531；`fieldDefaultValues` 无条目 → 无初始化器 → 类型默认值 |
| 2 | `SalesStartDate` | `DateTime` | 否（值类型；**不是** `Nullable<DateTime>`，Nullable 的 typeIndex 是 24859，此处是 42727） | `0001-01-01T00:00:00` | 同上 |
| 3 | `SalesEndDate` | `DateTime` | 否 | `0001-01-01T00:00:00` | 同上 |
| 4 | `UpdateDate` | `DateTime` | 否 | `0001-01-01T00:00:00` | 同上 |

### 2.2 `ShopFreeRecruitHistoryDB` — 3 个字段（L91406–L91438）

```json
 "ShopFreeRecruitHistoryDB": {
  "fieldCount": 3,
  "fields": [
   {
    "conf": "high",
    "kind": "scalar",
    "name": "UniqueId",
    "src": "byval",
    "ti": 50531,
    "type": "long"
   },
   {
    "conf": "high",
    "kind": "scalar",
    "name": "RecruitCount",
    "src": "byval",
    "ti": 50495,
    "type": "int"
   },
   {
    "conf": "high",
    "kind": "datetime",
    "name": "LastUpdateDate",
    "src": "byval",
    "ti": 42727,
    "type": "DateTime"
   }
  ],
  "namespace": "MX.GameLogic.DBModel",
  "referenced": [],
  "support": true,
  "tdIndex": 12139
 },
```

metadata 复核：field `53814 UniqueId`→Int64、`53815 RecruitCount`→Int32、`53816 LastUpdateDate`→DateTime，fieldCount=3，与 schema 一致。同样**没有文本字段**。

### 2.3 `ShopGachaRecruitListResponse` — 2 个自有字段（L91439–L91608）

（原文节选到 `wireFieldCount` 为止；同一对象后面还有 `wireFields` 数组的 11 项，名单见下表）

```text
 "ShopGachaRecruitListResponse": {
  "base": "ResponsePacket",
  "baseChain": [
   "BasePacket",
   "ResponsePacket"
  ],
  "envelope": {
   "Protocol": 10006
  },
  "fieldCount": 2,
  "fields": [
   {
    "conf": "high",
    "kind": "list",
    "name": "ShopRecruits",
    "src": "vote(2,1.00)",
    "ti": 22823,
    "type": "List<ShopRecruitDB>"
   },
   {
    "conf": "high",
    "kind": "list",
    "name": "ShopFreeRecruitHistoryDBs",
    "src": "vote(2,1.00)",
    "ti": 22811,
    "type": "List<ShopFreeRecruitHistoryDB>"
   }
  ],
  "namespace": "MX.NetworkProtocol",
  "protocol": 10006,
  "protocolName": "Shop_GachaRecruitList",
  "referenced": [
   "List",
   "ShopRecruitDB",
   "ShopFreeRecruitHistoryDB"
  ],
  "segment": 10,
  "tdIndex": 11553,
  "wireFieldCount": 11,
```

`wireFieldCount = 11`，即上线 JSON 一共 11 个键（2 个自有 + 9 个继承）。11 个键的名单（`wireFields[].name`，原文顺序）：

| # | 键 | 类型 | 来源 |
|---|---|---|---|
| 1 | `Protocol` | int | BasePacket（`abstract, per-Dto override`） |
| 2 | `SessionKey` | `SessionKey`（可空对象，null 时省略） | BasePacket |
| 3 | `OSType` | `OSType`(int32) | BasePacket |
| 4 | `ServerTimeTicks` | long | ResponsePacket |
| 5 | `ServerNotification` | `ServerNotificationFlag` | ResponsePacket |
| 6 | `MissionProgressDBs` | `List<MissionProgressDB>` | ResponsePacket |
| 7 | `EventMissionProgressDBDict` | `Dictionary<long,List<MissionProgressDB>>` | ResponsePacket |
| 8 | `BattlePassMissionProgressDBDict` | `Dictionary<long,List<MissionProgressDB>>` | ResponsePacket |
| 9 | `StaticOpenConditions` | `Dictionary<OpenConditionContent,OpenConditionLockReason>` | ResponsePacket |
| 10 | `ShopRecruits` | `List<ShopRecruitDB>` | 自有 |
| 11 | `ShopFreeRecruitHistoryDBs` | `List<ShopFreeRecruitHistoryDB>` | 自有 |

> 注意：这 11 个是"这个 DTO 作为顶层响应"时的全量键；作为 LoginSync 的**嵌套子响应**出现时，实际键集合以 §6.1 的抓包为准。

### 2.4 名字里带 `Recruit` 的全部类型（metadata 全量 35105 个类型定义扫描）

真正属于网络协议/存档 DTO 的只有 4 个（3 个数据 DTO + 1 个空请求 DTO）：

| 类型 | 字段数 | 性质 |
|---|---|---|
| `MX.GameLogic.DBModel.ShopRecruitDB` | **4** | 卡池元素 DTO（本报告主角） |
| `MX.GameLogic.DBModel.ShopFreeRecruitHistoryDB` | 3 | 免费招募历史 DTO |
| `MX.NetworkProtocol.ShopGachaRecruitListResponse` | 2 | 协议 10006 响应 |
| `MX.NetworkProtocol.ShopGachaRecruitListRequest` | 0 | 协议 10006 请求（空包） |

其余带 Recruit 的都不是协议 DTO（列出以免误判）：`MX.Data.Excel.ShopRecruitDBSchema`(1 字段：只有 `Id`，数据在 `Bytes`)、`MX.Data.Excel.ShopRecruitExcel`(1：`__p` FlatBuffers 表)、`MX.Data.Excel.ShopRecruitExcelRepository`(0)、`MX.Data.ShopRecruitExcelData`(10)、`MX.Data.Excel.ShopFreeRecruitDBSchema`(1)、`MX.Data.Excel.ShopFreeRecruitPeriodDBSchema`(1)、`MX.Data.ShopFreeRecruitExcelData`(8)、`MX.Data.ShopFreeRecruitPeriodExcelData`(4)、`FlatData.ShopFreeRecruitType`(枚举)、`ShopRecruitBuyStudentNetworkTask`(4)、`UIPopupGacha_RecruitShop`(11)、`UIPopupGacha_RecruitShop_One`(1)、`UIRecruitShopInfo`(6，全是 UILabel/UITexture 引用)。

**不存在** `MX.NetworkProtocol.ShopRecruit`（不带 DB 的那个名字）。

---

## 3. 逐字段对照：客户端 `ShopRecruitDB` vs 我方实发

比对对象：`our_shoprecruits_20261119.json` 的 529 条 + `our_loginsync_inner_20261119.json → ShopGachaRecruitListResponse.ShopRecruits`（两份 529 条完全相同）。

| # | 客户端字段 | 客户端类型 | 我方 JSON 键 | 是否下发 | 529/529 覆盖 | 我方样例值 |
|---|---|---|---|---|---|---|
| 1 | `Id` | `long` | `Id` | ✅ | 529/529 | `5000000` |
| 2 | `SalesStartDate` | `DateTime` | `SalesStartDate` | ✅ | 529/529 | `"2023-08-03T05:00:00"` |
| 3 | `SalesEndDate` | `DateTime` | `SalesEndDate` | ✅ | 529/529 | `"2023-08-10T15:59:59"` |
| 4 | `UpdateDate` | `DateTime` | `UpdateDate` | ✅ | 529/529 | `"0001-01-01T00:00:00"` |

**客户端有、我方没发：0 个。**
**我方有、客户端没有：0 个**（元素级）。
我方元素键的顺序 `Id, SalesStartDate, SalesEndDate, UpdateDate` 与官方一致；529 条键集合唯一，**没有任何一条出现缺键或多键**。

我方响应对象（`ShopGachaRecruitListResponse`）实际只有 3 个键：`Protocol`(10006) / `ShopRecruits`(529) / `ShopFreeRecruitHistoryDBs`(0)。其中 `Protocol` 是 §2.3 表里的第 1 个继承字段，不算多余字段；`ShopFreeRecruitHistoryDBs` 与官方一样是空数组。

---

## 4. 官方抓包对照（Q3）

### 4.1 官方元素也是 4 个键，529/529 一致

```
inner.ShopGachaRecruitListResponse.ShopRecruits  n = 529
键集合 (distinct) = {Id, SalesEndDate, SalesStartDate, UpdateDate}
元素 #1 = {"Id":5000000,"SalesStartDate":"2023-08-03T05:00:00","SalesEndDate":"2023-08-10T15:59:59","UpdateDate":"0001-01-01T00:00:00"}
元素 #529 = {"Id":99999999,"SalesStartDate":"2024-08-01T14:00:00","SalesEndDate":"2099-12-31T03:59:59","UpdateDate":"0001-01-01T00:00:00"}
```

原始明文（`02_1017_api_account_loginsync.response.json → plain`，二次转义，偏移 104699 起）：

```
ShopGachaRecruitListResponse\":{\"Protocol\":0,\"SessionKey\":{\"AccountServerId\":0,\"MxToken\":\"\"},
\"ServerTimeTicks\":0,\"ServerNotification\":0,\"RequestId\":\"\",\"ShopRecruits\":[{\"Id\":5000000,
\"SalesStartDate\":\"2023-08-03T05:00:00\",\"SalesEndDate\":\"2023-08-10T15:59:59\",
\"UpdateDate\":\"0001-01-01T00:00:00\"},{\"Id\":5000010,...
```

### 4.2 官方 vs 我方：整份列表逐字节相同

```
official n = 529   our n = 529
exact list equality (Python ==)          : True
sha256(json.dumps(list, sort_keys=True, separators=(",",":")))
  official : 9bf27a83f11b428ce0159424de94a7a71d33ab2009769647d6fe8756111a92cd
  ours     : 9bf27a83f11b428ce0159424de94a7a71d33ab2009769647d6fe8756111a92cd
序列化长度 : 66661 B == 66661 B
```

### 4.3 "省略默认值是否合法"的判定

- **元素级没有任何字段被省略**：客户端 DTO 只有 4 个字段，官方 4 个全写，我方 4 个全写。
- 官方连默认值都**不省略**：同一份明文里 `"UpdateDate":"0001-01-01T00:00:00"`（默认值）是显式写出的；`"ServerNotification":0`、`"ServerTimeTicks":0`、`"RequestId":""` 也全都写了。⇒ 官方序列化器走的是"全量输出"，不是 `DefaultValueHandling.Ignore`。
- 我方 `UpdateDate` 之所以也在，是服务端显式打了 `[JsonProperty(DefaultValueHandling = DefaultValueHandling.Include)]`（`DBModel.cs` L2278–2283 的 `BAPATCH-GACHAJSON v1` 注释），与官方对齐；如果没这个特性，全局 Ignore 会把它省掉 —— 4 个字段里它是**唯一一个值恒为默认值**、因而会被全局 Ignore 吞掉的字段，现已对齐。

**结论：4 个字段两边都是全量显式下发，不存在"官方省略了所以我们也省略"的合法省略项。**

---

## 5. 文本 / 本地化字段专项（Q4、Q5）

### 5.1 三个 DTO 里没有任何文本字段

| DTO | 字段 | 其中 string 类型 |
|---|---|---|
| `ShopRecruitDB` | Id, SalesStartDate, SalesEndDate, UpdateDate | **0** |
| `ShopFreeRecruitHistoryDB` | UniqueId, RecruitCount, LastUpdateDate | **0** |
| `ShopGachaRecruitListResponse` | ShopRecruits, ShopFreeRecruitHistoryDBs | **0** |

- `LocalizeKey` / `Name` / `Title` / `Description` / `Text` / `DisplayName` / `TabName`：`ShopRecruitDB` 里**一个都没有**。
- `LocalizeEtcId` / `LocalizeCode` / `LocalizeCodeID` / `LocalizeEtcKey` / `MsgKey`：`ShopRecruitDB` 里**一个都没有**。

所以"我方有没有发"的答案是：**客户端这个 DTO 根本没有这些字段，我方没有可漏的东西**。

### 5.2 反证：客户端确实有这套本地化约定，只是不用在招募上

全量 metadata 191,990 个字段条目里，名字含 `localize` / `msgkey` / `localkey` 的有 **979 条**，例如：

```
 11  <LocalizeEtcId>k__BackingField          EventNotifyInfo, MX.Data.AcademyLocationData, MX.Data.AcademyScheduleData ...
  3  <LocalizeEtcKey>k__BackingField         MX.Data.EmblemInfo, MX.Data.TimeAttackDungeonGeasInfo ...
  3  <LocalizeCodeID>k__BackingField         MX.Data.EventContentTreasure*RewardInfo ...
  3  <NameLocalizeKey>k__BackingField        MXField.Shared.Data.Field*Info
```

**没有一条落在 `ShopRecruitDB` / `ShopFreeRecruitHistoryDB` / `ShopGachaRecruitListResponse` 上。**

### 5.3 招募链路上的客户端 Excel 行也没有文本

`MX.Data.ShopRecruitExcelData`（客户端招募 Excel 表的行类型，10 个字段）：

```
Id(Int64) / CategoryType(FlatData.ShopCategoryType) / IsLegacy(bool) / OneGachaGoodsId(Int64) /
TenGachaGoodsId(Int64) / SalePeriodFrom(Nullable<DateTime>) / SalePeriodTo(Nullable<DateTime>) /
IsNewbie(bool) / DirectPayInvisibleTokenId(Int64) / SelectAbleGachaGroupId(Int64)
```

也全是数值/布尔/时间，**没有显示名、没有 Localize 键**。

### 5.4 文本在哪：客户端侧的 `LocalizeGachaShop` 本地表（与 DTO 无关）

客户端 metadata 里确实存在招募文案专用的本地化表类型：

```
MX.Data.Excel.LocalizeGachaShopDBSchema   fieldCount=1   主键字段 <GachaShopId>k__BackingField -> System.Int64
MX.Data.Excel.LocalizeGachaShopExcel      fieldCount=1   (Excel 包装类型，单字段未展开)
MX.Data.Excel.LocalizeGachaShopExcelRepository fieldCount=0
```

它是**客户端本地 Excel 表**（不是网络协议字段），所以：文案（页签名/标题）走的是"客户端拿某个 Id 去这张表里查"，而不是"服务端下发文本"。本报告只确认这张表的存在与主键字段；它的键值空间与 `ShopRecruits[].Id` 是否对齐属于另一个问题，请接 `plan/20261119/LOCALIZE_KEY_DIFF.md`、`GACHA_CANDIDATE_LIST_V2.md`，本报告不下结论。

> 推论（有边界）：招募页签的**文字**不可能从 `ShopRecruitDB` 这条链路上取，它只能来自 UI 侧另一处解析（拿 `Id`/`CategoryType`/`OneGachaGoodsId` 去查上面这类本地化表）。因此**"我们少发了文本字段"在结构上就不成立**，红字要找 UI 侧或本地化表的证据，不在本 DTO 里。这一段是排除性结论，不是对红字成因的定案。

---

## 6. 附带发现（不在"元素字段"问题内，但属于同一响应对象的字段集合差异）

### 6.1 LoginSync 里嵌套的 `ShopGachaRecruitListResponse`：我方 3 键，官方 7 键

| 键 | 官方值（抓包原文） | 我方 | 差 |
|---|---|---|---|
| `Protocol` | `0` | `10006` | 值不同 |
| `SessionKey` | `{"AccountServerId":0,"MxToken":""}` | 缺 | 缺键 |
| `ServerTimeTicks` | `0` | 缺 | 缺键 |
| `ServerNotification` | `0` | 缺 | 缺键 |
| `RequestId` | `""` | 缺 | 缺键 |
| `ShopRecruits` | 529 | 529 | 一致 |
| `ShopFreeRecruitHistoryDBs` | `[]` | `[]` | 一致 |

判断：官方这 4 个缺失键的值**全是默认值**（0 / "" / 空对象），且 `Protocol` 在嵌套里是 `0` 而不是 10006 —— 看起来是"把一个新建的响应对象直接序列化"产生的冗余信封（推断，未在客户端代码侧验证），不是业务数据。我方这边按 `DBModel.cs` L2279 注释所述的全局 `DefaultValueHandling.Ignore` 把它们省略了。

**关键：这不是招募特有。** 同一份 LoginSync 的其它嵌套响应，我方同样缺这 4 个键：

| 嵌套响应 | 官方键数 | 我方键数 | 我方缺的键（均含 `RequestId/ServerNotification/ServerTimeTicks/SessionKey`） |
|---|---|---|---|
| `CharacterListResponse` | 8 | 5 | 上述 4 个 |
| `CampaignListResponse` | 8 | 4 | 上述 4 个 + `CurrentScenarioId` |
| `MomoTalkOutLineResponse` | 7 | 3 | 上述 4 个 |
| `ArenaLoginResponse` | 6 | 2 | 上述 4 个 |
| `ShopGachaRecruitListResponse` | 7 | 3 | 上述 4 个 |

所以它**不能单独解释**招募页红字——否则所有走 LoginSync 的页面都该同样异常。

### 6.2 LoginSync 顶层：官方 35 键，我方 32 键

官方独有：`SessionKey` / `RequestId` / `FriendCount`（`official_spec.json` 里 1017 的 `key_count_min = key_count_max = 35`）。我方 32 键。同样与招募无关，仅记录。

### 6.3 我方嵌套 `Protocol=10006`，官方嵌套 `Protocol=0`

仅是 6.1 那一行，不影响 DTO 字段集合。

---

## 7. 判定汇总

| 假设 | 判定 | 证据 |
|---|---|---|
| 客户端 `ShopRecruitDB` 有更多字段、我方漏发 | **排除** | metadata fieldCount=4；schema 4；我方 4 键 529/529 |
| 客户端 DTO 有文本/本地化字段、我方没发 | **排除** | 4 个字段全是 long/DateTime，客户端这条链没有文本字段 |
| 官方省略了某些字段、我方跟着省略是合法的 | **不适用** | 官方 4 键全写（含默认值），我方也 4 键全写 |
| 我方多发了客户端没有的字段 | **排除**（元素级） | 元素键集合与客户端 DTO、与官方三方差集皆空 |
| 招募红字由 DTO 缺字段引起 | **排除** | 上述四条 |

仍然开放（本次只读比对无法定论，需要另外的证据）：
1. UI 侧按 `Id`/`CategoryType`/`OneGachaGoodsId` 查本地化表失败导致的 textKey 回落（红字在 Unity 里常见于 Localize missing-key，但**未在本仓库中找到招募 UI 的直接证据**）；
2. §6.1 的嵌套信封键差异（有系统性证据说明它不独属于招募）；
3. 我方下发的 `Id` 是否被客户端 Excel 认识（另有报告在查：`plan/20261119/GACHA_CANDIDATE_LIST_V2.md`、`OUR_VS_OFFICIAL_SHOPRECRUITS.md`，本报告不重复）。

---

## 8. 复现（全部只读，在仓库根目录 `BAServer\` 下执行）

```powershell
# 1) 客户端 DTO 字段清单
python -c "import json;d=json.load(open(r'work\ba\proto\dto_schema_full_v2.json',encoding='utf-8'));print(json.dumps(d['ShopRecruitDB'],ensure_ascii=False,indent=1))"

# 2) 原始 metadata（tdIndex 12143）字段
python -c "import sys;sys.path.insert(0,r'work\ba\proto');from mdlib import MD;m=MD();k=m.type_index('ShopRecruitDB','MX.GameLogic.DBModel');print(m.td_info(k));[print(f) for f in m.fields_of(k)]"

# 3) 我方元素键集合
python -c "import json;d=json.load(open(r'work\ba\data\_tmp\our_shoprecruits_20261119.json',encoding='utf-8'));print(len(d['ShopRecruits']),{tuple(sorted(e)) for e in d['ShopRecruits']})"

# 4) 官方元素键集合 + 与我方全等
python -c "import json;o=json.load(open(r'report\_tmp\official_decoded_201\02_1017_api_account_loginsync.response.json',encoding='utf-8'))['inner']['ShopGachaRecruitListResponse']['ShopRecruits'];u=json.load(open(r'work\ba\data\_tmp\our_shoprecruits_20261119.json',encoding='utf-8'))['ShopRecruits'];print(len(o),{tuple(sorted(e)) for e in o},o==u)"
```

---

## 9. 一句话给后续排查

`ShopRecruitDB` 是 **4 字段全对齐**的，卡池数据结构本身没有问题；如果招募界面还有红字/异常，往**客户端本地化表与 UI 的 Id→文案解析**、以及 §6.1 的信封差异方向查，不要往"服务端少发字段"方向查。
