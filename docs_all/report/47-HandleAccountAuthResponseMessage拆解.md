# 47 · `HandleAccountAuthResponseMessage` 拆解

> 输入（只读，未修改任何二进制）：
> `work\ba\audit\ba-work\x\assets\bin\Data\Managed\Metadata\global-metadata.dat`（38,426,024 B）
> 方法：纯离线静态分析；四层编码（明文 / XOR 0x20 / XOR 0x01 / XOR 0x0E）全部扫过
> 脚本：`report\_tmp\meta\s12_ident.py`、`s13_group.py`（本轮新增），其余复用 39 号的 s1–s11
> 日期：2026-11-14

---

## 0. 先给三条结论

1. **`AccountAuthResponse` 类里根本没有 `MxToken`，也没有 `SessionKey`。**
   它的 20 个属性可以完整列出（§3），三件套（`get_` / `set_` / `<X>k__BackingField`）闭合，
   里面**没有** `MxToken`、没有 `SessionKey`、没有 `EncryptedUID`、没有 `StaticOpenConditions`。
   ⇒ **lead 的推论要修正**：嵌套解析不到是事实，但**平铺成 `"MxToken": ...` 同样解析不到**——
   因为这个类不收这个字段。它只存在于 `SessionDB`（本地存档）那一簇（`0x257D93`–`0x257DC4`）。

2. **客户端每个响应都要求 6 个信封字段，而我们只给了 3 个。**
   `ResponsePacket`（`0x0023019C`）的成员是：`ServerTimeTicks` / `ServerNotification` /
   `MissionProgressDBs` / `EventMissionProgressDBDict` / `BattlePassMissionProgressDBDict` / `StaticOpenConditions`。
   对照 `report\36` 的 24 键，**`MissionProgressDBs`、`EventMissionProgressDBDict`、`BattlePassMissionProgressDBDict` 三个我们根本没发**。
   如果客户端在 `HandleMessage` 里直接遍历它们 → `NullReferenceException` → 被协程的 try/catch 吞 → **既不成功也不失败、不弹窗、不发下一个请求**。
   **这是本轮最有价值的一条可执行假设**（§7）。

3. **`AccountAuthResponse` 没有 `ResultState`，也没有 `ErrorCode`**（对比：`AccountCheckYostarResponse` @`0x0022CB8E` 就有 `ResultState` @`0x0022CC26`）。
   ⇒ 客户端**不可能**从 Auth 响应里读出"业务失败"；它对成功/失败的唯一判据只能是
   **"取字段时有没有抛异常"** 或 **"某个字段是不是 null"**。这正好解释了「不弹窗、不报错、静默停住」。

---

## 1. 查档

| 档案 | 关系 |
|---|---|
| `report\39-metadata字符串挖掘-Account_Auth解析路径.md` §4 | 上一轮：`LoginTask` 状态机、`AccountAuthResponseMessage` 初判。**本轮修正了 DTO 名字**（见 §2） |
| `report\36-Account_Auth响应字段清单.md` | 服务端 24 键清单。本轮把它和**客户端真实字段表**逐条对照（§8） |
| `report\34-国服packet二进制结构分析.md` | `HttpGameMessage` 解码链。本轮不重复 |
| `report\24-state接口schema反推.md` | 早期 metadata 扫描（仅明文层） |

查档结论：**没有**做过按「属性三件套闭合」判定类成员归属的工作，本轮是新的。

---

## 2. 一个必须先纠正的事实：DTO 的真名是 `AccountAuthResponse`

上一轮我把 `AccountAuthResponseMessage`（`0x0012ABDF`）当成响应 DTO，**不准确**。

| 类型 | 偏移 | 性质 |
|---|---|---|
| `AccountAuthResponseMessage` | `0x0012ABDF` | 网络层的**消息包装**（与 `AccountAuthNetworkTask` @`0x0012ABFA` 相邻） |
| **`AccountAuthResponse`** | **`0x0022AE81`** | **真正的响应 DTO，20 个属性在这里** |
| `AccountAuthResponseMessage`（第二处引用） | `0x0013FAD5` | `LoginTask` 里作为泛型参数/局部类型出现 |
| `AccountAuthResponseMessage`（标签） | `0x0040BEE1` | 日志/签名标签 |

同类命名法在整个包里一致：`AccountCheckYostarResponse`（`0x0022CB8E`）、`AccountResetResponse`（`0x0022CC53`）、
`ArenaEnterLobbyResponse`（`0x0022CCC4`）……都是 `XxxResponse` 作 DTO、`XxxResponseMessage` 作消息包装。

> 上一轮据此说的「客户端侧只找到 8 个字段、十来个键 NOT FOUND」——**其中大部分是我的检索方式错了**
> （我用 `get_WeeklyProduct` 去搜，而它们是没有 getter 的裸字段名）。真实情况见 §8 对照表。

---

## 3. `AccountAuthResponse` 的完整成员表（**这就是第 4 问的答案**）

区间 `0x0022AE81`–`0x0022B5AC`（下一个类型 `AccountAuth2Request` @`0x0022B5AC` 接上）。
三件套齐备 ⇒ 这是一个**全部为 auto-property** 的 DTO。

### 3.1 属性（accessor 段，`0x22AE95`–`0x22B1BA`）

| # | 属性 | `get_` | `set_` |
|---|---|---|---|
| 1 | `CurrentVersion` | `0x22AE95` | `0x22AEA8` |
| 2 | `MinimumVersion` | `0x22AEBB` | `0x22AECE` |
| 3 | `IsDevelopment` | `0x22AEE1` | `0x22AEF3` |
| 4 | `BattleValidation` | `0x22AF05` | `0x22AF1A` |
| 5 | `UpdateRequired` | `0x22AF2F` | `0x22AF42` |
| 6 | `TTSCdnUri` | `0x22AF55` | `0x22AF63` |
| 7 | `AccountDB` | `0x22AF71` | `0x22AF7F` |
| 8 | `RepurchasableMonthlyProductCountDBs` | `0x22AF8D` | `0x22AFB5` |
| 9 | `MonthlyProductParcel` | `0x22AFDD` | `0x22AFF6` |
| 10 | `MonthlyProductMail` | `0x22B00F` | `0x22B026` |
| 11 | `BiweeklyProductParcel` | `0x22B03D` | `0x22B057` |
| 12 | `BiweeklyProductMail` | `0x22B071` | `0x22B089` |
| 13 | `WeeklyProductParcel` | `0x22B0A1` | `0x22B0B9` |
| 14 | `WeeklyProductMail` | `0x22B0D1` | `0x22B0E7` |
| 15 | `IssueAlertInfos` | `0x22B0FD` | `0x22B111` |
| 16 | `DailyRecordDBs` | `0x22B125` | `0x22B138` |
| 17 | `OptionDB` | `0x1AF045`（在别处） | `0x22B14B` |
| 18 | `AccountLimitedFlashSaleDBs` | `0x22B158` | `0x22B177` |
| 19 | `Desc` | `0x22B196` | `0x22B19F` |
| 20 | `FunctionClose` | `0x22B1A8` | `0x22B1BA` |

### 3.2 backing field 段（`0x22B1CC`–`0x22B471`，20 条，与上表一一对应）

```
0x22B1CC <CurrentVersion>k__BackingField
0x22B1EC <MinimumVersion>k__BackingField
0x22B20C <IsDevelopment>k__BackingField
0x22B22B <BattleValidation>k__BackingField
0x22B24D <UpdateRequired>k__BackingField
0x22B26D <TTSCdnUri>k__BackingField
0x22B288 <AccountDB>k__BackingField
0x22B2A3 <RepurchasableMonthlyProductCountDBs>k__BackingField
0x22B2D8 <MonthlyProductParcel>k__BackingField
0x22B2FE <MonthlyProductMail>k__BackingField
0x22B322 <BiweeklyProductParcel>k__BackingField
0x22B349 <BiweeklyProductMail>k__BackingField
0x22B36E <WeeklyProductParcel>k__BackingField
0x22B393 <WeeklyProductMail>k__BackingField
0x22B3B6 <IssueAlertInfos>k__BackingField
0x22B3D7 <DailyRecordDBs>k__BackingField
0x22B3F7 <OptionDB>k__BackingField
0x22B411 <AccountLimitedFlashSaleDBs>k__BackingField
0x22B43D <Desc>k__BackingField
0x22B453 <FunctionClose>k__BackingField
```

### 3.3 裸字段名段（`0x22B472`–`0x22B59E`，17 条）

```
CurrentVersion / MinimumVersion / IsDevelopment / BattleValidation / UpdateRequired / TTSCdnUri /
RepurchasableMonthlyProductCountDBs / MonthlyProductParcel / MonthlyProductMail /
BiweeklyProductParcel / BiweeklyProductMail / WeeklyProductParcel / WeeklyProductMail /
IssueAlertInfos / DailyRecordDBs / AccountLimitedFlashSaleDBs / FunctionClose
```

（`AccountDB` / `OptionDB` / `Desc` 的裸名没有落在这段里，但它们的 backing field 在 §3.2 中，仍属本类。）

### 3.4 基类

**未找到**。il2cpp 的继承关系是 `typeDefinitions.parentIndex`（整数索引），不是字符串，
而该文件的表头被混淆（magic `0x12724394` 而非 `0xFAB11BAF`），**无法解析**。
能确定的只有**否定形式**：该类没有从基类继承来的可访问属性，否则那些 `<X>k__BackingField` 会出现在 §3.2 的连续段里没有它们。

---

## 4. 第 4 问的正面回答：`MxToken` 是**谁**的属性

### 4.1 事实

| 检索 | 结果（四层全扫） |
|---|---|
| `MxToken` | **只 4 处**：`0x257D97`(get_) / `0x257DA3`(set_) / `0x257DAC`(<MxToken>k__) / `0x257DC4`(裸名) |
| `SessionKey` | **NOT FOUND** |
| `EncryptedUID` | `0x1B5371`(`SetEncryptedUID`) / `0x3D8957`(UI 标签内) |
| `AccountAuthResponse` 段（0x22AE81–0x22B5AC）内出现 `MxToken` | **0 次** |

`MxToken` 的 4 处全部落在同一个簇（`0x257D93`–`0x257DC4`），紧邻 `SessionDB` @`0x257DCC`：

```
0x257D93 get_MxToken
0x257DA3 set_MxToken
0x257DAC <MxToken>k__BackingField
0x257DC4 MxToken
0x257DCC SessionDB
0x257DD6 get_LastConnect / 0x257DE6 get_ConnectionTime ...
```

### 4.2 判定

**`MxToken` 是 `SessionDB` 这一簇的属性，不是 `AccountAuthResponse` 的。**

判据不是"挨得近"，而是**闭合性**：
`AccountAuthResponse` 的 20 个 `<X>k__BackingField` 在 `0x22B1CC`–`0x22B471` 连续排满、
和 20 个 `get_/set_` 严格一一对应。若它还有第 21 个属性 `MxToken`，
`<MxToken>k__BackingField` 必然出现在这段里 —— 它不在。

> ⚠️ 一个必须说清的歧义：`0x257DCC` 的 `SessionDB` 究竟是"类型名"还是"字段名"，静态上分不清
> （名字堆里两者形态相同，且本包表头被混淆、拿不到 `typeDefinitions`——`field` 索引）。
> 因此「`MxToken` 属于 `SessionDB` 类」置信度**中高**；而
> 「`MxToken` 不属于 `AccountAuthResponse`」置信度**高**（这一条只依赖闭合性，不依赖 `SessionDB` 的归属）。

### 4.3 对 lead 推论的修正

> 原推论：`"SessionKey":{"MxToken":...}` 嵌套 → 解析不到 → 所以 token 空。
> 
> **修正**：嵌套确实解析不到，**但原因更彻底** —— `AccountAuthResponse` 根本没有 `MxToken` 属性，
> 所以 **平铺成 `"MxToken": "..."` 也一样进不去**。
> 想让它生效，得先确认客户端到底在哪一步把 token 写进 `SessionDB`（见 §6，静态上查不到调用方）。

---

## 5. 第 1 问：这个方法内部读了哪些字段？——**静态上答不了，但有边界**

### 5.1 硬限制（必须先说）

`global-metadata.dat` **只含签名、不含函数体**。C# 方法体的 IL 被编译成 `libil2cpp.so` 里的原生代码。
要从"读了哪些字段"这种控制流/数据流问题里得出结论，必须有 method body + `methodPointer`，
而本项目已确认两件事（39 号 §1、`report\15` §4）：
1. `libil2cpp.so` 零命名导出（`.dynsym` 2660 条全 UNDEFINED，无 `.symtab`）；
2. metadata 表头被混淆 → 无法解析 `methodPointers`。

⇒ **"它调用了哪些 setter"、"有没有 `== null` 分支"这类问题，本轮无法给出证据，不给结论。**

### 5.2 能给的是"可达字段全集"

既然方法体不可见，退一步给**它可能触碰的全部字段**（= 反序列化出来的对象图上有什么）：

* `AccountAuthResponse` 的 20 个属性（§3）——其中 6 个是 `Product*` 列表、2 个是版本号、2 个是 bool 开关
* `AccountAuthResponse.AccountDB` 指向的那个 `AccountDB` 对象（`MX.GameLogic.DBModel.AccountDB`，见 `MX-GameLogic-DBModel-AccountDB-IsLevelOrExpHigherThan0` @`0x154604` 标签）
* 信封 `ResponsePacket` 的 6 个字段（§7）
* `LoginTask` 自己的 `LoginState` / `loginState` / `WaitingTicket`（`0x13FDD3` / `0x13FD9B` / `0x13F6F7`）

### 5.3 唯一能从"编译器生成名"推出的结构线索

`AccountAuthResponseMessage` 那一簇（`0x0012AC0F`–`0x0012AC50`）里有：

```
<ProcessSession>b__1_0
<ProcessSession>d__1
<HandleMessage>b__2_0
<HandleMessage>b__2_1
<HandleMessage>b__2_2
<>9__2_1
<>9__2_2
```

`<HandleMessage>b__2_0/1/2` = `HandleMessage` 里至少 **3 个 lambda**；
`<>9__2_1`、`<>9__2_2` = 其中 2 个被**缓存成静态委托**（不会每次都 new）。

⇒ **推断（中）**：`HandleMessage` 里有 3 条分支/回调路径（典型形态：成功回调 / 错误回调 / 完成回调）。
**但这 3 条分别对应什么条件，静态上不可知。**

---

## 6. 第 3 问：`SessionDB.MxToken` 从哪里被赋值？——**查不到，只能排除**

| 尝试 | 结果 |
|---|---|
| 找 `set_MxToken` 的**调用方** | 做不到（无函数体、无 xref；字符串名通过 metadata 索引访问，不在 `.so` 里留可见引用） |
| 找哪个响应类带 `MxToken` 字段 | **没有**。全文件 `MxToken` 仅 4 处，全在 `0x257D9x–0x257DC4` 的存档簇 |
| 找 `SessionKey` 类型/字段 | **NOT FOUND**（四层） |
| 找 `Session_Info` 协议 | 存在，`0x0022D91E`（协议名枚举第 3 条） |

**可排除的**：token **不是**由 `AccountAuthResponse` 承载的。
**仍未定的**：它是从 `Queuing_GetTicket` / `Account_CheckYostar` / **`Session_Info`** 哪一步落库的，
或者干脆是本地生成的。静态上给不出答案。

### 6.1 一条顺手挖到的旁证（与 AES 会话参数有关）

`AccountCheckYostarResponse` @`0x22CB8E` **前面**紧挨着三个字段名
（`0x22CB58` `PassCookieResult`、`0x22CB69` `ClientGeneratedKey`、`0x22CB7C` `ClientGeneratedIV`），
它们属于**它前一个类型**（该类型的 backing field `…ratedIV>k__BackingField` @`0x22CB40` 收尾）。

⇒ 推断（中）：那个类型是 **CheckNexon / GetTicket 的响应**，AES 的 key/IV 是**客户端生成**并在握手响应里回带/确认的
（与 `GameSessionManager.SetAesParameters/VerifyAndSetAesParameters` @`0x219F61`/`0x219FC2` 对得上）。
**这也间接说明：`Account_Auth` 根本不是发放会话凭据的协议** —— 指望从 Auth 响应里补 `MxToken` 的方向本身就是错的。

> ⚠️ 与上一轮报告的一处自我修正：39 号 §4.4 说「`SessionDB.MxToken` 全文件 0 命中」——那是我漏搜，
> 它其实存在（`0x257D93`–`0x257DC4`）。**"`SessionKey` 0 命中"仍然成立。**

---

## 7. 第 2 问：成功/失败判据 —— 以及**最可能被吞掉的那个异常**

### 7.1 事实：Auth 响应里没有任何"结果码"

| 类 | 有 `ResultState`? | 有 `ErrorCode`? |
|---|---|---|
| `AccountAuthResponse`（`0x22AE81`） | **无** | **无** |
| `AccountCheckYostarResponse`（`0x22CB8E`） | **有** @`0x22CC26`（+ `ResultMessage` @`0x22CC32`） | — |

这与 `report\36` §0 的说法一致（"响应里没有 ResultState 也没有 ErrorCode，这是正确的"），
现在有了**客户端侧**的独立证据。

⇒ 客户端无法"读到失败"，只能**在取字段时抛异常**。这就是"不弹窗"的机制解释：
`ErrorAccountAuth` → `OnLoginFail` 本来是要弹窗的，但它**没被触发**；被触发的是某个异常，被协程吞了。

### 7.2 ★ 最可疑的缺口：**信封字段我们只发了一半**

`ResponsePacket` @`0x0023019C` 的成员（三件套闭合，6 条）：

```
0x002301AB get_ServerTimeTicks  / 0x002301BF set_      → 我们发了 ✅
0x002301D3 get_ServerNotification / 0x002301EA set_    → 我们发了 ✅
0x00230201 get_MissionProgressDBs / 0x00230218 set_    → ❌ 没发
0x0023022F get_EventMissionProgressDBDict / ...         → ❌ 没发
0x0023026D get_BattlePassMissionProgressDBDict / ...    → ❌ 没发
0x002302B5 get_StaticOpenConditions / 0x002302CE set_  → 我们发了 ✅
```

对照 `report\36` 的 24 个顶层键：`MissionProgressDBs`、`EventMissionProgressDBDict`、
`BattlePassMissionProgressDBDict` **一个都不在**。

**假设 H1（本轮最高优先级）**：
> 客户端在 `HandleMessage` 里遍历 `MissionProgressDBs` 或其他两个集合，
> 我们没给 → 反序列化后为 `null` → 遍历时 `NullReferenceException`
> → 被 `ProcessSession` 协程的 try/catch 吞掉
> → 既不进 `OnLoginFinish`（不成功），也不进 `OnLoginFail`（不失败）
> → **按钮文字消失、永远不动、不发下一个协议。**

这条假设的可测形态极便宜：**在响应里补 `"MissionProgressDBs": []`、
`"EventMissionProgressDBDict": {}`、`"BattlePassMissionProgressDBDict": {}` 各一次。**

### 7.3 另一条并列假设（同样便宜）

`AccountAuthResponse` 有 7 个「我们没有发」的字段：`MinimumVersion` / `IsDevelopment` /
`BattleValidation` / `UpdateRequired` / `Desc` / `FunctionClose` / `DailyRecordDBs`。
其中 `DailyRecordDBs` 是**集合**（其余是值类型，缺省为 0/false 不会 NRE）。
若客户端在 Auth 之后立刻把 `DailyRecordDBs` 并进本地存档并遍历 → 同样 NRE。

⇒ 建议一次性补齐：`"DailyRecordDBs": []`。

---

## 8. 24 键对照表：客户端到底认哪些

| # | 我们发的键（`report\36`） | 客户端有吗 | 客户端落点（偏移） |
|---|---|---|---|
| 1 | `Protocol` | 包装层字段 | `HttpMessage.<Protocol>k__BackingField` @`0x21A89B` |
| 2 | `CurrentVersion` | ✅ | `0x22AE95` |
| 3 | `TTSCdnUri` | ✅ | `0x22AF55` |
| 4 | `AccountDB` | ✅ | `0x22AF71` |
| 5 | `AccountId` | ⚠️ 只在他处同名属性（`0x11A4BC`），**不在 Auth DTO 里** | — |
| 6 | `SessionKey` | ❌ **NOT FOUND**（四层） | — |
| 7 | `EncryptedUID` | ⚠️ 只有 `SetEncryptedUID`@`0x1B536E` / 字段 `encryptedUID`@`0x1B576D`，**不在 Auth DTO 里** | — |
| 8 | `ServerNotification` | ✅ | `ResponsePacket` @`0x2301D3` |
| 9 | `ServerTimeTicks` | ✅ | `ResponsePacket` @`0x2301AB` |
| 10 | `OptionDB` | ✅ | `0x22B14B`(set_) |
| 11 | `AccountRestrictionsDB` | ❌ **NOT FOUND** | — |
| 12 | `StaticOpenConditions` | ✅ | `ResponsePacket` @`0x2302B5` |
| 13 | `AttendanceBookRewards` | ❌ **NOT FOUND** | — |
| 14 | `AttendanceHistoryDBs` | ❌ **NOT FOUND** | — |
| 15 | `RepurchasableMonthlyProductCountDBs` | ✅ | `0x22AF8D` |
| 16 | `MonthlyProductParcel` | ✅ | `0x22AFDD` |
| 17 | `MonthlyProductMail` | ✅ | `0x22B00F` |
| 18 | `BiweeklyProductParcel` | ✅ | `0x22B03D` |
| 19 | `BiweeklyProductMail` | ✅ | `0x22B071` |
| 20 | `WeeklyProductParcel` | ✅ | `0x22B0A1` |
| 21 | `WeeklyProductMail` | ✅ | `0x22B0D1` |
| 22 | `IssueAlertInfos` | ✅ | `0x22B0FD` |
| 23 | `AccountLimitedFlashSaleDBs` | ✅ | `0x22B158` |
| 24 | `NewlyAddedShopCashIds` | ❌ **NOT FOUND** | — |

**客户端期望但我们没发的**（14 条）：

```
AccountAuthResponse : MinimumVersion  IsDevelopment  BattleValidation  UpdateRequired
                      Desc  FunctionClose  DailyRecordDBs           ← 7 条
ResponsePacket      : MissionProgressDBs  EventMissionProgressDBDict
                      BattlePassMissionProgressDBDict                  ← 3 条
```

> 注：4 条 `❌ NOT FOUND` 说明客户端**没有同名成员**，多发无害（Newtonsoft 忽略未知键），
> 但也**不会产生任何效果**——不要指望靠它们改变行为。

---

## 9. 追加：客户端网络状态机（新的 logcat 抓手）

`NetworkService` 一簇里有一组全大写枚举成员（`0x00219DB0`–`0x00219E32`，紧邻 `GameSessionManager`@`0x219E46`）：

```
0x00219DB0  WAITING_SERVER_RESPONSE
0x00219DC8  RECEIVED_SERVER_RESPONSE
0x00219DE1  FILE_NOT_FOUND
0x00219DF0  FAILED
0x00219DF7  SUCCESS
0x00219DFF  CLIENT_NETWORK_NOT_REACHABLE
0x00219E1C  SERVER_RESPONSE_ERROR
0x00219E32  SERVER_NOT_RESPONSE
```

若客户端把这些状态 `ToString()` 打日志，logcat 里会出现上述字样。
**"停在 WAITING_SERVER_RESPONSE 而始终不到 RECEIVED_SERVER_RESPONSE"** 正好是我们观测到的症状。

```bash
adb logcat -v time | grep -E "WAITING_SERVER_RESPONSE|RECEIVED_SERVER_RESPONSE|SERVER_RESPONSE_ERROR|SERVER_NOT_RESPONSE"
```

> 置信度：串存在 = 高；会进 logcat = 低（同 39 号 §3.3 的保留意见）。

---

## 10. 诚实标注

| 结论 | 状态 |
|---|---|
| `AccountAuthResponse` @`0x22AE81` 的 20 个属性、20 个 backing field、17 个裸字段，偏移如上 | **确证**（逐条可复查） |
| `MxToken` 不属于 `AccountAuthResponse` | **高**（依赖三件套闭合） |
| `MxToken` 属于 `SessionDB` 那一簇 | **中高**（`SessionDB` 是类型名还是字段名，静态分不清） |
| `AccountAuthResponse` 无 `ResultState`/`ErrorCode`；`AccountCheckYostarResponse` 有 | **确证** |
| `HandleMessage` 里 ≥3 个回调分支 | **中**（来自编译器生成名 `<HandleMessage>b__2_0/1/2`） |
| **H1：`MissionProgressDBs` 等三个信封字段缺失 → NRE 被吞** | **纯假设，未证实**。它是"症状最吻合 + 验证成本最低"的一条，不是结论 |
| 方法内部读了哪些字段 / 有没有 null 分支 | **无法确定**（metadata 无函数体，`methodPointer` 拿不到） |
| `SessionDB.MxToken` 的赋值来源 | **无法确定**（无 xref） |
| `AccountAuthResponse` 的基类 | **无法确定**（`parentIndex` 在混淆表头里） |

---

## 11. 脚本（本轮新增）

| 文件 | 作用 |
|---|---|
| `report\_tmp\meta\s12_ident.py` → `ident_hits.tsv` | 四层（明文/0x20/0x01/0x0E）子串检索，输出真实偏移；本轮用它确认 `MxToken` 只 4 处、`SessionKey` 0 处 |
| `report\_tmp\meta\s13_group.py` | 区间内「类型名 / `get_` `set_` / 普通成员」分组打印，用于判定成员归属 |

```powershell
$PY = "C:\Users\su\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
cd report\_tmp\meta
& $PY .\s13_group.py --lo 0x22AE81 --hi 0x22B5AC        # AccountAuthResponse 全成员
& $PY .\s13_group.py --lo 0x23019C --hi 0x230480        # ResponsePacket 信封成员
& $PY .\s12_ident.py --name MxToken --name SessionKey --name AttendanceBookRewards
```

> 注意：`s12_ident.py` 逐层解码时**逐层释放**，不要改成一次性建 4 份副本（38 MB × 4 会 OOM，本轮踩过一次 `0xC0000005`）。

---

## 12. 下一步（给 lead，按性价比）

1. **补 3 个信封字段 + 1 个集合字段**（§7.2/§7.3）：
   `"MissionProgressDBs":[]`、`"EventMissionProgressDBDict":{}`、
   `"BattlePassMissionProgressDBDict":{}`、`"DailyRecordDBs":[]`。零成本，一次请求就能验证 H1。
2. **停止在 `SessionKey` 上做文章**：它不存在于客户端（§4）。补了也无效。
3. 若 H1 不成立，logcat 用 §9 的四个状态词做排除法：
   卡在 `WAITING_SERVER_RESPONSE` ⇒ 响应没被认领；出现 `SERVER_RESPONSE_ERROR` ⇒ 认领了但处理失败。
4. **不要再花时间在静态层面追"方法内部逻辑"** —— 这条路已经被 `methodPointer` 不可得堵死（§5.1）。
   下一步该做的是动态：hook `LoginTask.HandleAccountAuthResponseMessage` 或用
   `il2cpp_class_from_name` 验证 `AccountAuthResponseMessage` 是否被成功反序列化。
