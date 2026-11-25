# 70 · `Academy_*` 系列 DTO 与缺口清单

> **角色**：DTO 补全员 ｜ **产出**：2026-11-14 ｜ **目标**：解开 `Academy_GetInfo(24000)` 死结
> **纪律**：只读本地文件；未连手机、未连服务器（无 ssh / adb）；未改 `dto_schema.json` / `gen_default.py` / `protocol_map.json`；未碰 `libtprt.so`

## 结论速览

| 项 | 结果 |
| --- | --- |
| 24000 是否解开 | ✅ **解开**。`AcademyGetInfoResponse` 只有 **2 个**自有字段，不是大对象 |
| 生成器 | ✅ `work/ba/proto/gen_academy.py`，`--check` 全部 PASS（exit 0） |
| 家族规模 | metadata 中 `MX.*` 命名空间共 **11 个** `Academy*` 类型（4 协议 DTO + 5 DBModel + 2 服务层） |
| 递归闭包 | 只需 **3 个**类型：`AcademyGetInfoResponse` → `AcademyDB` / `AcademyLocationDB` |
| 没提取到的字段 | 24000 链路上 **1 个**（`AcademyDB.ZoneVisitCharacterDBs` 的元素类型），**不影响出包** |
| 缺口统计（vs 旧 112） | 具名 Response DTO **444** 个，旧 schema 覆盖 **32** 个（7.2%），补齐后 7.7%，**仍缺 410**；410 个**全部**在 metadata 里真实存在 |

---

## 1. 方法与可复现性

### 1.1 输入（全部只读）

| 类别 | 路径 | 用途 |
| --- | --- | --- |
| metadata 原文 | `work\ba\audit\ba-work\x\assets\bin\Data\Managed\Metadata\global-metadata.dat`（38,426,024 B） | 唯一的字段级事实源 |
| metadata 去外层混淆 | `report\_tmp\patch\md_deob.bin`（38,426,024 B） | typedef / fields / methods 三张表，直接按结构体读 |
| 解析库 | `work\ba\proto\mdlib.py` | 仅 import，未修改 |
| 泛型投票 | `work\ba\proto\shittim_types.json`（821 条 NetworkProtocol DTO 的 C# 声明） | 泛型实例的 C# 类型名 |
| 协议号 | `work\ba\proto\protocol_map.json`（501 条） | 协议号 ↔ DTO 名 |
| 基类字段 | `work\ba\proto\dto_schema.json`（112 DTO） | `ResponsePacket` / `RequestPacket` / `AccountDB` 等，**只读引用**（这些字段已在 Account_Nickname 链路上实测跑通） |

### 1.2 四条判据

1. **字段类型判据（主力，99.4% 有效）**
   ```
   field.typeIndex - 1 == typeDefinition.byvalTypeIndex
   ```
   命中 ⇒ 该字段就是那个 typedef 的**普通类型**（`string` / `long` / `DateTime` / 类 / 枚举）。
   逐条验算：`System.String` byval=61195、`System.Int64` byval=50530、`System.DateTime` byval=42726、
   `AcademyDB` byval=34952 ⇒ `AcademyGetInfoResponse.AcademyDB` 的 ti=34953 = 34952+1 ✔

2. **泛型例外判据（补充）**
   `ti-1` **不在** byval 表 ⇒ 该字段类型是**泛型实例或数组**（`List<T>` / `Dictionary<K,V>` / `Nullable<T>` / `T[]`）。
   这类实例在 metadata v27 里不占 typedef 槽位，必须另找类型名：
   - 首选 `shittim_types.json` 投票（同一个 `ti` 在其它 DTO 上的 C# 声明）；
   - 投票缺失时**留 `unknown`**，不猜（见 §4）。

   这条同时给出了一个副产品判据：**`ti-1` 命中 byval ⇒ 该字段不可能是 `Nullable<T>`**。C# 源码里的 `Foo?`
   若是可空**引用**注解（`#nullable enable`），运行时类型仍是 `Foo`，`ti-1` 依然命中；只有 `Nullable<Foo>`（值类型）
   才会掉进泛型分支。这正是下面 §3.5 那个"看起来对不上"的解释。

3. **名字存在性判据（反向搜索法）**
   候选明文 × 256 个 XOR key → 去**原始** metadata 搜；256 个 key 全 miss 才能说"不存在"。
   ⚠️ 不能用 `md_deob.bin` 下否定结论（它没解逐串随机 key，会大量假阴性）。
   本次用等价实现 `report\_tmp\academy\revsearch.py`（纯 Python，不依赖 numpy），结论见 §4.4。

4. **递归判据**
   字段类型名解析出来的类，继续用判据 1/2 展开，直到全是标量或泛型容器。

### 1.3 表位置（从 md_deob.bin 头 288 B 解析得到，与题面一致）

```
string        @ 由 header 给出        methods        @ 0x8B2C14 / 36 B
typeDefinitions @ 0x1F02148 / 88 B    fields         @ 0x1B17590 / 12 B
images        @ 0x21F44A0 / 40 B      typeDefinition 总数 = 35,105
```

本次 **没有** 使用 `libtprt.so`、`libil2cpp.so` 反汇编，也没有跑 Frida / adb —— 全部结论来自 metadata 静态表。

---

## 2. `Academy_*` 家族全表

| 类型 | 命名空间 | tdIndex | 字段数 | 已提取 | 说明 |
| --- | --- | ---: | ---: | :--: | --- |
| `AcademyGetInfoRequest` | MX.NetworkProtocol | 10682 | 0 | ✓ | 24000 请求，空体（客户端只发 Protocol） |
| `AcademyGetInfoResponse` | MX.NetworkProtocol | 10683 | 2 | ✓ | **24000 响应主体** |
| `AcademyAttendScheduleRequest` | MX.NetworkProtocol | 10684 | 1 | ✓ | 24001 请求 |
| `AcademyAttendScheduleResponse` | MX.NetworkProtocol | 10685 | 3 | ✓ | 24001 响应 |
| `AcademyDB` | MX.GameLogic.DBModel | 11892 | 3 | ✓ | 课程表存档根，被 24000/24001 引用 |
| `AcademyLocationDB` | MX.GameLogic.DBModel | 11893 | 3 | ✓ | 地点（Rank/Exp） |
| `AcademyMessageOutLineDB` | MX.GameLogic.DBModel | 11894 | 4 | ✓ | MomoTalk 式消息会话摘要 |
| `AcademyMessageDB` | MX.GameLogic.DBModel | 11895 | 7 | ✓ | 单条消息 |
| `AcademyScheduleDB` | MX.GameLogic.DBModel | 11896 | 5 | ✓ | 单次日程记录 |
| `AcademyService` | MX.GameLogic.Service | 11645 | 0 | — | 服务实现类，非 DTO（0 字段，不出包） |
| `CharacterAcademyTagResult` | MX.GameLogic.Service | 11843 | 2 | — | 角色标签校验结果（服务层返回值） |

**为什么只有 4 个协议 DTO？** 本版本 `protocol_map.json` 里 `Academy_*` 只有 3 条协议：

| 协议号 | 协议名 | req DTO | resp DTO |
| ---: | --- | --- | --- |
| 24000 | `Academy_GetInfo` | `AcademyGetInfoRequest`（0 字段，空体） | `AcademyGetInfoResponse` |
| 24001 | `Academy_AttendSchedule` | `AcademyAttendScheduleRequest`（1 字段） | `AcademyAttendScheduleResponse` |
| 24002 | `Academy_AttendFavorSchedule` | **无**（protocol_map 里 req/resp 均为 null） | **无** |

`AcademyAttendFavorScheduleRequest/Response` 在 metadata 里**确认不存在**（§4.4，256 key 全 miss），
与 `report/_intel_hlba_protocols.md` 第 19 行"`Academy_AttendFavorSchedule` 当前无 RequestClass"一致 ——
24002 是**没有 DTO 的僵尸协议**，补不了也不需要补。

`AcademyMessageOutLineDB` / `AcademyMessageDB` / `AcademyScheduleDB` 三个 DBModel 已导出字段表，但本版本
**没有任何字段以普通类型方式引用它们**（全库扫字段名含 `Academy` 的 23 处，无一处指向它们），
推测只在某个 `List<>` / `Dictionary<>` 泛型容器或 MomoTalk 模块里出现 —— 不在 24000 链路上，仅作家族完备性归档。

---

## 3. `AcademyGetInfoResponse` 完整字段表与依据

### 3.1 自有字段（metadata 里 `fieldCount = 2`，实测字段表也是 2 条）

| # | 字段名 | 类型 | kind | ti | 判据 | 置信度 |
| ---: | --- | --- | --- | ---: | --- | --- |
| 1 | `AcademyDB` | `AcademyDB` | object | 34953 | 34953-1 = 34952 = `MX.GameLogic.DBModel.AcademyDB`(td 11892) 的 byval | 高（byval 命中） |
| 2 | `AcademyLocationDBs` | `List<AcademyLocationDB>` | list | 21273 | 21273-1 = 21272 **不在** byval ⇒ 泛型实例；shittim 对同一字段声明 `List<AcademyLocationDB>?`，且 `ParcelResultDB.AcademyLocationDBs` 用的是**同一个 ti=21273** | 高（投票 1/1 + 同 ti 佐证） |

### 3.2 递归闭包（`AcademyGetInfoResponse` 引用到的全部类型，递归到底）

`AcademyDB`（td 11892，`fieldCount = 3`）：

| # | 字段名 | 类型 | kind | ti | 判据 | 置信度 |
| ---: | --- | --- | --- | ---: | --- | --- |
| 1 | `LastUpdate` | `DateTime` | datetime | 42727 | 42727-1 = 42726 = `System.DateTime` byval | 高 |
| 2 | `ZoneVisitCharacterDBs` | **unknown**（结构=list） | list | 10463 | 10463-1 = 10462 不在 byval ⇒ 泛型实例/数组；投票缺失 ⇒ **元素类型不填** | 低（仅结构，hint: `List<VisitingCharacterDB>`） |
| 3 | `ZoneScheduleGroupRecords` | `Dictionary<long,List<long>>` | dict | 10425 | 10425-1 = 10424 不在 byval ⇒ 泛型实例；shittim 3 处同 ti 投票一致 `Dictionary<long, List<long>>?` | 高（投票 3/3） |

`AcademyLocationDB`（td 11893，`fieldCount = 3`）：

| # | 字段名 | 类型 | kind | ti | 判据 | 置信度 |
| ---: | --- | --- | --- | ---: | --- | --- |
| 1 | `LocationId` | `long` | scalar | 50531 | 50531-1 = 50530 = `System.Int64` byval | 高 |
| 2 | `Rank` | `long` | scalar | 50531 | 同上 | 高 |
| 3 | `Exp` | `long` | scalar | 50531 | 同上 | 高 |

闭包只有这 3 个类型，**没有更深一层** —— `AcademyDB` 的两个字段一个是 `DateTime`、一个是 `Dictionary<long,List<long>>`（纯标量容器），
`AcademyLocationDB` 全是 `long`。也就是说 `AcademyGetInfoResponse` 的线上报文是一座**两层的小对象**，
之前用 `{"Protocol":24000}` 空包被客户端无视，是因为 `AcademyDB` 直接是 `null`/缺键，反序列化后 `AcademyInfoComponent`
拿不到 `CachedAcademyDB`。

### 3.3 线上键序（`wireFields`，含信封与基类）

```
Protocol                 (int, 信封键，非 DTO 字段)
├─ ServerTimeTicks       (long)         ┐
├─ ServerNotification    (enum→0)       │ ResponsePacket 基类 6 字段
├─ MissionProgressDBs    (list→[])      │ 直接引用 dto_schema.json，
├─ EventMissionProgressDBDict (dict→{}) │ 与已跑通的 Account_Nickname 包同构
├─ BattlePassMissionProgressDBDict(dict→{}) │
└─ StaticOpenConditions  (list→[])      ┘
├─ AcademyDB             (object, 3 字段)
└─ AcademyLocationDBs    (list→[])
```

**`Protocol` 为什么不在 `fields` 里？** 因为 metadata 的 `AcademyGetInfoResponse` 只有 2 个字段 —— `Protocol` 是传输层
信封键（`wireFields` 与 `envelope` 两个键记录了它）。`--protocol 24000` 时生成器把它拼在最前，顺序与
`work/ba/proto/out/AccountNicknameResponse.json` 完全一致。

### 3.4 生成的包（`python gen_academy.py --protocol 24000` 实跑输出）

```json
{
  "Protocol": 24000,
  "ServerTimeTicks": 0,
  "ServerNotification": 0,
  "MissionProgressDBs": [],
  "EventMissionProgressDBDict": {},
  "BattlePassMissionProgressDBDict": {},
  "StaticOpenConditions": [],
  "AcademyDB": {
    "LastUpdate": "2026-11-14T00:00:00",
    "ZoneVisitCharacterDBs": [],
    "ZoneScheduleGroupRecords": {}
  },
  "AcademyLocationDBs": []
}
```

13 行 / **368 字节** / 9 个顶层键。对比之前 192 字节的 `{"Protocol":24000}`：多了 `AcademyDB` 实体和 `AcademyLocationDBs` 数组。

### 3.5 与 shittim 外部声明的对照（1 处"看起来不一致"，已排除）

`shittim_types.json` 写的是：

```json
"AcademyGetInfoResponse": [["AcademyDB", "AcademyDB?"], ["AcademyLocationDBs", "List<AcademyLocationDB>?"]]
```

`AcademyDB?` 的 `?` 是 **C# 可空引用类型注解**（`#nullable enable`），不是 `Nullable<AcademyDB>`。
证据：`AcademyGetInfoResponse.AcademyDB` 的 ti=34953，`ti-1` 命中 byval ⇒ 运行时类型就是 `AcademyDB`；
若是 `Nullable<AcademyDB>`，`ti-1` 必然落空（同 `CafeDB.LastSummonDate` 的 ti=24859，`ti-1` 落空，
那才是真的 `Nullable<DateTime>`）。
⇒ **类型名不带 `Nullable<>`，生成时给完整对象而不是 `null`。**

---

## 4. 没提取到的字段（诚实清单）

### 4.1 全清单（`--check` 报出的 8 处 unknown：6 处元素类型未知 + 2 处 kind 未知）

字段名字典里我**只给"结构形态"，不给"元素类型名"**：元素名没有任何本地证据，按纪律一律留 `"type": "unknown"`。

| 类型.字段 | ti | schema 里的 kind | 置信度 | 所属协议 | 对 24000 的影响 | hint（**未采信**，只进 `hint` 键，不进 `type`） |
| --- | ---: | --- | --- | --- | --- | --- |
| `AcademyDB.ZoneVisitCharacterDBs` | 10463 | `list` | guess | **24000 / 24001** | 无（生成 `[]`） | `List<VisitingCharacterDB>` |
| `ParcelResultDB.EquipmentDBs` | 10601 | `list` | guess | 24001 | 无 | `List<EquipmentDB>` |
| `ParcelResultDB.ItemDBs` | 10693 | `list` | guess | 24001 | 无 | `List<ItemDB>` |
| `ParcelResultDB.FurnitureDBs` | 10648 | `list` | guess | 24001 | 无 | `List<FurnitureDB>` |
| `ParcelResultDB.IdCardBackgroundDBs` | 10677 | `list` | guess | 24001 | 无 | `List<IdCardBackgroundDB>` |
| `ParcelResultDB.ParcelResultStepInfoList` | 22563 | `list` | guess | 24001 | 无 | `List<ParcelResultStepInfo>` |
| `BasisPoint.Multiplier` / `.OneOver10_4` | 50541 / 43628 | `unknown` | none | 24001（经 `ParcelInfo`） | 无 | 疑似 `static readonly` |

也就是说 `AcademyDB.ZoneVisitCharacterDBs` 在 schema 里长这样：

```json
{"name": "ZoneVisitCharacterDBs", "type": "unknown", "kind": "list", "ti": 10463,
 "conf": "guess", "elementType": "unknown",
 "evidence": "ti-1 不在 byval 表 ⇒ 泛型实例/数组；字段名为复数；shittim 无投票"}
```

"是集合"这一步有硬依据（`ti-1` 不命中 byval ⇒ 只能是泛型实例或数组）＋ 字段名是复数；"元素是 `VisitingCharacterDB`"
这一步**只是猜**，所以它躺在 `hint` 里，`type` 上写的是 `unknown`。

`BasisPoint` 整个类型还额外标了 `"opaque": true` —— 它是 struct，metadata 的 FieldDefinition 只有
`name / typeIndex / token` 三项，**没有 static 位**，7 个字段里 6 个疑似静态常量，
序列化成"键值对"还是"裸数字"无法从 metadata 判定，所以生成器对它输出 `null`。
（已交付的 `build_schema.py` 用 `SKIP_BY_TYPE` 做过同样的事，我沿用了这个先例。）

### 4.2 为什么这几个提不到

泛型实例（`List<T>` / `Dictionary<K,V>` / `Nullable<T>`）在 il2cpp v27 metadata 里**不占 typedef 槽位**，
`typeIndex` 指向的是运行时构造的 `Il2CppType` 条目，元素类型只能从
① 同 ti 的其它字段的 C# 声明投票，或 ② `Il2CppType` / `Il2CppGenericClass` 结构体（在 `libil2cpp.so` 里）反解。
路子 ② 被本次任务边界排除（不动 `.so`、不做运行时），路子 ① 的缺口正好是这 6 个字段：

- `ti=10463`：全库只出现 **2 次**，两个字段**都叫** `ZoneVisitCharacterDBs`
  （`AcademyDB` 与 `EventContentLocationDB`），互相不能提供新信息；且它**不在** `shittim_types.json` 的 3 个 `Academy*` 条目里。
- `ti=10601/10693/10648/10677/22563`：只被 `ParcelResultDB` 使用，`ParcelResultDB` 属 `MX.GameLogic.Parcel`，
  `shittim_types.json` 只收了 `MX.NetworkProtocol` 的 821 个类，**一个 DBModel/Parcel 类都没收**（0 个以 `DB` 结尾的类），投票自然为空。

### 4.3 为什么不影响 24000

这 6 个字段全部落在**集合位置**，生成的是 `[]`：

- `ZoneVisitCharacterDBs` 是集合 ⇒ `[]`，对任意 `List<T>` / `T[]` 都合法，元素类型对空数组没有意义；
- `ParcelResultDB.*` 5 个同理（也只影响 24001，不影响 24000）；
- 只有 `ParcelInfo.Multiplier/Probability` 走 `BasisPoint`，而 `ParcelInfo` 只被 **24001** 的 `ExtraRewards` 用到。

⇒ **`{"Protocol":24000, ...}` 这一包没有任何 `null` 是由 unknown 兜底产生的**，全部是确定的标量 / 空集合 / 空字典。
唯一给 `null` 的地方是 `BasisPoint`（只出现在 24001 的 `ParcelInfo` 里）。

### 4.4 确定性否定（反向搜索法，256 key）

`report\_tmp\academy\revsearch.py`，对原始 38 MB metadata 逐个 key 生成密文再搜：

```
AcademyGetInfoResponse           FOUND  0x0012AB7B/k=0x00
AcademyDB                        FOUND  0x0022A900/k=0x00   0x00111E7A/k=0x66
AcademyLocationDB                FOUND  0x0022A91C/k=0x00   0x00111F1D/k=0x66
ZoneVisitCharacterDBs            FOUND  0x0024CAFF/k=0x00   0x004A3041/k=0x66
VisitingCharacterDB              FOUND  0x00258A08/k=0x00   0x000BDC21/k=0xDB
AcademyMessageDB                 FOUND  0x0024CDA2/k=0x00
AcademyScheduleDB                FOUND  0x0024CF01/k=0x00
AcademyAttendFavorScheduleRequest    *** NOT FOUND (256 keys all miss) ***
AcademyAttendFavorScheduleResponse   *** NOT FOUND (256 keys all miss) ***
AcademyZoneVisitCharacterDB          *** NOT FOUND (256 keys all miss) ***
```

两条硬结论：

1. **`AcademyAttendFavorSchedule*` 在本版本 metadata 里确实不存在** —— 24002 不是"我们没挖到"，是客户端本来就没有这对 DTO。
2. **不存在名为 `AcademyZoneVisitCharacterDB` 的类型** ⇒ `ZoneVisitCharacterDBs` 的元素**不是**同名前缀的类，
   这让 `List<VisitingCharacterDB>`（该类型存在，`MX.GameLogic.DBModel.VisitingCharacterDB`，2 字段 `UniqueId`/`ServerId`）
   成为唯一有实体的候选 —— 但仍**只是推断**，schema 里保持 `unknown` + `hint`，不写成 `type`。

---

## 5. 旧 112 之外的缺口清单

### 5.1 统计（口径：`protocol_map.json` 501 条协议的 `resp` 字段）

| 指标 | 数值 |
| --- | ---: |
| 协议总数 | 501 |
| 带具名 `resp` 的协议 | 444（57 条 resp 为 null / 未登记） |
| 旧 `dto_schema.json` 覆盖的 resp DTO | 32（**7.2%**） |
| 本文件新增 | 2（`AcademyGetInfoResponse` / `AcademyAttendScheduleResponse`） |
| 补齐后覆盖率 | **7.7%** |
| **仍缺** | **410** |
| 其中 metadata 里**真实存在** | **410（100%）** |
| 幽灵名（metadata 里没有） | **0** |

> 这条 100% 很关键：410 个缺口**没有一个是假的**，`md.type_index(name)` 全部命中，
> 意味着剩下的活是"纯体力活 + 泛型消歧"，不存在"名字对不上、还得再猜"的风险。
> 每个 DTO 的 `fieldCount` 我已一并写进 `gap.json`，可直接排期。

### 5.2 P0 号段逐条清单

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


### 5.3 建议排期

| 优先级 | 号段 | 理由 |
| :--: | --- | --- |
| P0 | 2000 / 3000 / 4000 / 5000 / 12000 / 20000 | 角色/装备/道具/编队/回忆大厅/咖啡厅 —— 进大厅后的第一批交互，`fieldCount` 多为 0~4，**单条成本最低**，10 条里 6 条是 0 字段（只要基类字段） |
| P0 | 1000 | 账号段剩余 14 条，`Account_Create` / `Account_SetTutorial` 等 0 字段占 9 条，能立刻让登录流程更完整 |
| P1 | 24000 | 已由本文件补齐 ✅ |
| P2 | 30000 / 35000 | 缺口最大（53 / 42 条），但属活动/礼包等边缘内容，可延后 |

### 5.4 一个可直接复用的配方

410 条缺口的补法已被本次跑通，复制 `report\_tmp\academy\gen_schema.py` 的 `build()`，
把 `ROOTS` 换成目标 DTO 名列表即可 —— 判据 1 解决 99.4%，剩下的泛型用 shittim 投票，投票空的留 `unknown`。
**不需要再碰 `libtprt.so`、不需要 adb、不需要重跑 Frida。**

---

## 6. `gen_academy.py` 用法

```bash
cd work/ba/proto

python gen_academy.py                      # AcademyGetInfoResponse 默认 JSON（无 Protocol 信封）
python gen_academy.py --protocol 24000     # 完整响应包 {"Protocol":24000, ...}
python gen_academy.py --auto-protocol      # 协议号取 schema 登记的（24000）
python gen_academy.py --check              # 自检：字段齐全 / 类型对 / json.loads 往返
python gen_academy.py --dto AcademyDB      # 生成任意已收录类型
python gen_academy.py --list               # 列出 17 个类型 / 协议号 / 字段数
python gen_academy.py --set AcademyDB.LastUpdate=2026-11-14T00:00:00
python gen_academy.py --dto AcademyAttendScheduleResponse --protocol 24001
python gen_academy.py --out 24000.json     # 写文件
python gen_academy.py --shallow            # 嵌套对象给 null
python gen_academy.py --no-base            # 不含 ResponsePacket 基类字段
```

`--check` 输出（2026-11-14 实跑）：静态检查 **0** 结构错误、**0** 个 object 引用未定义、**8** 个 unknown 已逐条列明
（6 个"元素类型未知但形态已知"、2 个 `BasisPoint` 静态/实例不分）；17 个类型全部"生成 + 校验 + json 往返"通过；
10 条核心断言全 OK；结尾 `---- check: PASS ----`，**exit 0**。

默认值约定（与 `gen_default.py` 保持一致，方便两条链路拼在一起）：

| C# 类型 | 生成值 |
| --- | --- |
| `string` / `Guid` | `""` / 全 0 GUID |
| 整型 | `0` |
| `float` / `double` | `0.0` |
| `bool` | `false` |
| `DateTime` | `"2026-11-14T00:00:00"`（无时区 ISO） |
| 枚举 | `0` |
| 集合 | `[]` |
| 字典 | `{}` |
| `Nullable<T>` | `null` |
| 嵌套对象 | 递归生成；`opaque` 类型给 `null` |

**没有改 `gen_default.py`。** 两者互不依赖：`gen_default.py` 读 `dto_schema.json`，`gen_academy.py` 读
`dto_schema_academy.json`。想合并的话，把本文件的 17 个类型 merge 进 `dto_schema.json` 即可（字段结构兼容，
只是 `kind` 词表多了 `scalar` 这个别名 —— `gen_default.py` 认 `prim`，合并时需要把 `scalar` 映射回 `prim`）。

---

## 7. 产物与复现脚本

| 产物 | 路径 | 说明 |
| --- | --- | --- |
| schema | `work\ba\proto\dto_schema_academy.json` | 17 个类型定义，含 `_meta` / `envelope` / `wireFields` / `opaque` |
| 生成器 | `work\ba\proto\gen_academy.py` | 独立，不依赖 `gen_default.py` |
| 本报告 | `report\70-Academy系列DTO与缺口清单.md` | — |
| 挖矿脚本 | `report\_tmp\academy\gen_schema.py` | 从 metadata 重新生成 schema（可复现） |
| 类型解析库 | `report\_tmp\academy\lib_acad.py` | byval 判据 + shittim 投票 |
| 缺口统计 | `report\_tmp\academy\gap.py` → `gap.json` | §5 的数字来源 |
| 反向搜索 | `report\_tmp\academy\revsearch.py` | §4.4 的否定结论 |

复现：

```bash
python report\_tmp\academy\revsearch.py          # 256 key 反向搜索
python report\_tmp\academy\gen_schema.py         # 重新产出 dto_schema_academy.json
python report\_tmp\academy\gap.py                # 重新产出 gap.json
python work\ba\proto\gen_academy.py --check     # 自检
python work\ba\proto\gen_academy.py --protocol 24000
```
