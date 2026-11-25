# OFFICIAL_BAN_UI_STUDY — 官服怎么封人、客户端怎么知道、我们怎么零改客户端照样弹

- 调研时间：2026-11-18 夜（**只读**，未连服务器、未改任何既有文件；所有我自己写的脚本/输出都在 `work\ba\plan\20261118\_banui_tmp\`）
- 调研对象：CN 客户端 `com.RoamingStar.BlueArchive` 3.0.2/vc73 的 il2cpp 元数据 + 本地化 Excel、`work\ba\srv_src\` 的 Shittim 源码、桥 `account_auth_probe.py`、面板导出
- 结论等级：**已证实** = 有 `文件:行号 / 偏移 / 字符串` 可复现；**强推断** = 证据直指但不排除另一种布局；**需真机验证** = 必须跑设备才有定论（每条都给了具体办法）

---

## 0. 摘要（先回答四问）

| # | 问题 | 答案 | 依据 |
|---|---|---|---|
| ① | 客户端认不认服务端下发的 `State`？ | **客户端"认"这个字段，但它不是 UI 触发器。** 客户端 `AccountDB.State` 的静态类型就是 `FlatData.AccountState`（5 个值，`Dormant=2`），字段确实存在、确实被反序列化；但 35105 个客户端类型里**没有任何一个封禁/停权 UI 类**，`Protocol` 枚举 501 个协议里**没有 `Ban_*`**。⇒ 把 `State` 改 2，客户端**不会**因为"看到 State=2"而弹任何东西；封禁判定完全在服务端，客户端只有在**收到错误包**时才会弹。 | `md_deob.bin` type idx 9661 / 11900；`q1_scan.out.txt`；§1 |
| ② | 官方封禁靠哪个协议字段？ | **`Protocol.Error`（协议号 0）+ `ErrorCode`，`ErrorCode` 就是"封禁种类"。** 官方为此专门准备了 4 个错误包子类，其中两个就是封禁：<br>• `AccountBanErrorPacket{ BanReason }`，`ErrorCode` 硬编码为 **`AccountLoginError = 1025`**<br>• `AccountContentBanErrorPacket{ ContentType, BanStartDate, BanEndDate }`，`ErrorCode` 硬编码为 `AccountContentBan`<br>客户端本地化表里正正好好有两条**只有这两种包才对得上的文案**（含 `{1}~ {2}` 两个日期占位符）。 | `NetworkProtocol.cs:782-809`；`ProtocolData.cs:720`；`ExcelDB.db` → `LocalizeErrorDBSchema`；§2 |
| ③ | 有没有"服务端推文本、客户端弹"的零改客户端通道？ | **有，而且是官方的这一条。** 在 `Account_CheckNexon`(1014) 回包时不要回 `ErrorPacket`，改回 **`AccountBanErrorPacket` 并把日期区间塞进 `BanReason`**：客户端弹的就是它自己那句 `账号已被禁止使用，/ 如有任何问题请咨询客服！/ 封禁周期至：` + 我们的 `BanReason`。**零改客户端、不需要 `/common/client-code`、不需要改 dex/res/AXML。**<br>次选才是 SDK 层 `/common/client-code`（也是零改，但开机第一次必然显示"未知错误"，见 §3-B1）。 | §3、§4 |
| ④ | 最推荐的一句话 | **`State=Dormant` 继续当开关，但把 1014 的拒绝从"抛异常→`ErrorPacket(InvalidSession)`"改成"返回 `AccountBanErrorPacket`，`BanReason` 填 `2026-11-18 20:00 至 2026-11-20 20:00`"**——这正好是官方那条路。 | §4 |

> ⚠️ 一个必须先修的前提：**桥 `account_auth_probe.py` 把 1014 用进程内缓存回了**（`BAN_AND_DELETE_STUDY.md:39`、`:150-164`）。缓存命中时**根本打不到 Shittim**，那么无论我们让 Shittim 回什么包，客户端都看不到 ⇒ **不修桥的 TTL/强刷，任何封禁弹窗方案都是空转**。

---

## 1. §1 客户端封禁 UI 的现状

### 1.1 客户端到底有没有"封禁界面"

**没有独立的封禁界面/场景/prefab 类，但有封禁文案 + 封禁错误包。** 这是本次调研最反直觉的一点，也是结论的关键。

做法：把 `report\_tmp\patch\md_deob.bin`（38426024 B，已反混淆的 global-metadata）用现成的解析器（`report\_tmp\patch\md_lookup.py` / `tool.py` 的布局）全量解出 **35105 个 type / 263095 个 method / 191990 个 field**，然后做名字普查。

工具（本次新写，不改既有文件）：

- `work\ba\plan\20261118\_banui_tmp\mdq.py` —— 元数据查询库（type/field/method/字符串堆/`mdef→Type.Method`）
- `_banui_tmp\q1_scan.py` / `q1_scan.out.txt` —— 类型名普查
- `_banui_tmp\q1_types.py` / `q1_types.out.txt` —— 封禁相关类型的字段/方法逐条 dump

普查结果（`q1_scan.out.txt`）：

| 搜索式 | 命中 | 结论 |
|---|---|---|
| `(?<![a-z])Ban[A-Z]\|Ban(s\|ned)?$\|...\|Suspend\|Penalty\|Restriction` | 23 个类型 | **除了协议 DTO，全是 Unity/.NET 标准库**（`AssetReferenceUILabelRestriction`、`XmlSchema*Restriction`…） |
| `Suspend\|Banned\|Blocked\|Abnormal\|Restrict` | 30 个类型 | 同上；业务侧只有 `BlockedProductDB`（商品屏蔽）、`BlockedArea*`（战斗格） |
| `^UI.*(Popup\|Dialog\|Tips\|Alert)` | 369 个 UI 类 | **没有一个**名字带 Ban/Suspend/Penalty |

**⇒ 客户端 35105 个类型里，与"封号"有关的类型只有 4 个，全部是协议 DTO：**

| 类型 | idx | ns | 字段 |
|---|---|---|---|
| `AccountBanErrorPacket` | 10780 | `MX.NetworkProtocol` | `<BanReason>`（61196 = string，与 `Nickname/Reason/Url/Subject` 同号） |
| `AccountContentBanErrorPacket` | 10781 | `MX.NetworkProtocol` | `<ContentType>`(41579)、`<BanStartDate>`(42727 = DateTime)、`<BanEndDate>`(42727) |
| `BanDB` | 11915 | `MX.GameLogic.DBModel` | `ServerId/UniqueId/BanStartDate/BanEndDate/RegisterDate/CancelFlag/CancelDate/Reason` |
| `AccountRestrictionsDB` | 11903 | `MX.GameLogic.DBModel` | `NicknameRestriction/CommentRestriction/CallnameRestriction`（**只是"不许改昵称"**，不是封号） |

`q1_types.py` 原始输出节选（可信复现）：

```
### AccountBanErrorPacket  (idx=10780, ns=MX.NetworkProtocol, token=0x2002A1D)
    field  <BanReason>k__BackingField   typeIndex=61196
    method get_Protocol / get_ErrorCode / get_BanReason / set_BanReason / .ctor
### AccountContentBanErrorPacket  (idx=10781, ns=MX.NetworkProtocol, token=0x2002A1E)
    field  <ContentType>k__BackingField   typeIndex=41579
    field  <BanStartDate>k__BackingField  typeIndex=42727      ← DateTime
    field  <BanEndDate>k__BackingField    typeIndex=42727      ← DateTime
### AccountDB  (idx=11900)   field  <State>k__BackingField  typeIndex=35149
### AccountState (idx=9661, ns=FlatData)
    WaitingSignIn / Normal / Dormant / Comeback / Newbie
```

> 注意 `AccountBanErrorPacket` **没有 `ErrorCode` 字段**，只有一个 `get_ErrorCode` 方法 ⇒ 它的 `ErrorCode` 是**编译期常量**（服务端同一份代码里写着 `=> WebAPIErrorCode.AccountLoginError`，`NetworkProtocol.cs:807`）。这一点决定了客户端只能用 `ErrorCode` 做**类型分派**，见 §4.1。

### 1.2 `AccountDB.State` 被谁读、读了之后做什么

- 字段存在且被反序列化：`AccountDB`(idx 11900) 第 5 个字段 `<State>`，字段类型索引 **35149**。
  > ⚠️ 读法说明：`field.typeIndex` 指向 **Il2CppType 表**，不在 `typeDefinitions` 里，所以按 typeDefinition 解出来的名字是乱名（例如 `AccountDB` 的 `<AccountDB>` 字段会解成 `DebugMaterialMode`）。能可靠比对的是**索引相同即同一类型**：全部 string 字段都是 **61196**（`Nickname/Comment/Reason/Url/Subject/BanReason/TTSCdnUri` 同号），全部 DateTime 字段都是 **42727**（`StartDate/EndDate/BanStartDate/BanEndDate/LastConnectTime` 同号）。`State` 的 35149 只出现这一类语义，但**没有第二个同号字段可交叉验证**，所以"35149 == `FlatData.AccountState`"是按语义断言，不是硬证据。
- 旁证：`AccountDB.get_State` 反汇编为 `ldr w0,[x0,#0x30]; ret`（`_banui_tmp\diag_bl.py`）⇒ 字段是**4 字节值类型**（偏移 0x30=48），与 `int32` 底层枚举一致；客户端也确实单独声明了 `FlatData.AccountState`(idx 9661) 的 5 个同名成员。⇒ **客户端有完整的 `AccountState` 枚举，值与服务端逐字相同**（`WaitingSignIn 0 / Normal 1 / Dormant 2 / Comeback 3 / Newbie 4`）。
- 客户端 `AccountAuthResponse`（idx 10689）27 个字段里 `AccountDB` 是第一个数据字段。
- **但没有任何 UI 以它为条件。** 判据不是"没搜到"这么弱：35105 个类型全量枚举后，**不存在**任何形如 `UIPopup_Ban` / `UIBan` / `UISuspended` / `BanPopup` / `PenaltyPopup` 的类型；`Protocol` 枚举（idx 10770，**501 个成员**）里 `Ban` 命中 **0**。
- 想直接读 `State` 的 getter 调用者会撞上内联：`AccountDB.get_State`（mdef 78413 @ `0x0DB6FAE4`）反编译出来就是 `ldr w0,[x0,#0x30]; ret`，两指令，被 IL2CPP 内联，**没有任何 `bl` 调用点**（`_banui_tmp\diag_bl.py`、`q1_callers.out.txt`：连 `AccountDB.get_Nickname` 也是 0 caller）。⇒ "用调用图证明没人读 State"这条路在 release 包上不成立，只能靠类型普查 + 真机验证（§6-1）。

**结论（明确）：** 客户端"认"`State` 这个字段（结构和枚举都在），**但不存在"State==2 → 弹某个界面"的分支**。`State` 在客户端只是**数据**，不是**开关**。封禁的可见性 100% 依赖服务端在协议层**拒绝**并**说明原因**。

### 1.3 那客户端凭什么弹"封禁"？——本地化表里的两条铁证

客户端所有错误文案是**本地**的：`SessionTask::HandleErrorMessage`（mdef **65624**，va `0x0739F478`）里能直接看到 `bl -> MX.Data.LocalizeData::GetText`（`_banui_tmp\q1_outline.py` 输出）。

那条本地文案在哪？在本机已解出的 Excel 数据里：

```
work\ba\data\ExcelDB.db   (160,534,528 B, 398 张表)
  └─ LocalizeErrorDBSchema  (429 行；列 Key, Bytes；Bytes 是 FlatBuffer，含 UTF-8 中文)
```

`_banui_tmp\q5_excel3.py` 把 429 行全部解出来，与"封/客服/限制/禁止"有关的只有 8 行，其中**两条就是封禁文案**：

| 行 | `Key` | 文案（原文，`\n` 为换行） |
|---|---|---|
| 167 | `1749817446` | `账号已被禁止使用，`<br>`如有任何问题请咨询客服！`<br>`封禁周期至：` |
| 407 | `3146430479` | `检测到异常游戏记录，相关内容的使用将被限制 {0} 天。限制时间：{1}~ {2}` |

对应关系（强推断，理由见下）：

- 行 167 的文案**以冒号结尾**，后面等着拼接一段文本 ⇒ 只能是 `AccountBanErrorPacket.BanReason`（这个包唯一的数据字段就是一个 string）。**"封禁周期至：" + 服务端给的字符串。**
- 行 407 有**三个占位符**：`{0}` 天数、`{1}~ {2}` 起止时间 ⇒ 只能是 `AccountContentBanErrorPacket{ ContentType, BanStartDate, BanEndDate }`（3 个数据字段，其中 2 个是 DateTime，客户端自己格式化）。
- 这两条文案在全表里**没有别的候选包能装得下**（`ErrorPacket` 只有 `ErrorCode`，`Reason` 是 log-only）。

**⇒ 客户端不但"认封禁"，而且它的封禁弹窗是"本地固定文案 + 服务端填空"。这就是我们要的机制。**

### 1.4 客户端在登录阶段弹错的能力

同一张表里多条文案写着"将返回标题画面。"（如 `服务器处理请求失败。`、`数据库处理请求失败。`、`客户端异常。`）⇒ **登录握手阶段（1014 之前后）客户端确实会弹模态错误框**，而不是静默。封禁文案**没有**"将返回标题画面"这句 ⇒ 它是一个可点掉、停在标题的模态框。这一点很重要：我们不需要"进大厅之后才能弹"。

---

## 2. §2 官服封禁的协议表达（字段级）

### 2.1 服务端侧的全部封禁相关结构

| 结构 | 文件:行 | 字段 | 客户端有没有 | 被哪个协议用 |
|---|---|---|---|---|
| `AccountState` enum | `Schale\FlatData\AccountState.cs:8-15` | `WaitingSignIn 0 / Normal 1 / Dormant 2 / Comeback 3 / Newbie 4` | ✅（idx 9661，逐字相同） | `AccountDB.State` |
| `AccountDB.State` | `Schale\MX\GameLogic\DBModel\DBModel.cs:130` | `AccountState` | ✅（idx 11900） | `Account_Auth` / `Account_LoginSync` 的回包 |
| `BanDB` | `DBModel.cs:297-307` | `ServerId/UniqueId/BanStartDate/BanEndDate/RegisterDate/CancelFlag/CancelDate/Reason` | ✅（idx 11915） | **没有任何协议引用**（`Select-String BanDB` 在 `NetworkProtocol.cs` 0 命中）⇒ 死 DTO |
| `AccountBanByNexonDB` | `DBModel.cs:94-105` | `AccountId/Npsn/AccountBanId/BanType/BanDay/BanStartDate/BanEndDate/BanComment/DeleteFlag` | ❌ **客户端 3.0.2 里没有这个类型** | `AccountAuthResponse.accountBanByNexonDBs`（`NetworkProtocol.cs:112`，注释自认"official 从不带它"） |
| `AccountRestrictionsDB` | `DBModel.cs:154-159` | `NicknameRestriction/CommentRestriction/CallnameRestriction` | ✅（idx 11903） | `AccountAuthResponse.AccountRestrictionsDB`（`:109`）——**只限制改昵称**，不是封号 |
| `IssueAlertInfoDB` | `DBModel.cs:1475-1485` | `IssueAlertId/IssueAlertType/StartDate/EndDate/DisplayOrder/PublishId/Url/Subject` | ✅（idx 12059） | `AccountAuthResponse.IssueAlertInfos`（`:110`）——**"服务端给标题串 + URL + 起止日期"的告警条目** |
| `AccountBanErrorPacket` | `NetworkProtocol.cs:804-809` | `ErrorCode => AccountLoginError`（常量）、`BanReason`（string） | ✅（idx 10780） | `Protocol.Error` |
| `AccountContentBanErrorPacket` | **Shittim 源码里没有**（客户端 idx 10781 有） | `ErrorCode => AccountContentBan`、`ContentType`、`BanStartDate`、`BanEndDate` | ✅ | `Protocol.Error` |

### 2.2 `ErrorCode` 的真实取值（不是 0..N 的连号！）

`Schale\MX\NetworkProtocol\ProtocolData.cs:649` 起是 `enum WebAPIErrorCode : int`，**显式赋值**、611 个成员（客户端 629 个）：

| 名字 | 值 | 位置 | 用途 |
|---|---|---|---|
| `None` | 0 | `:650` | |
| `InvalidSession` | **3** | `:654` | **现在封禁实际走的那个（错的）** |
| `AccountUpdateStateFail` | 1017 | | 改 State 失败 |
| `AccountLoginError` | **1025** | `:720` | **`AccountBanErrorPacket` 的 ErrorCode —— 官方封禁码** |
| `InappositeNicknameRestricted` | 1034 | | 昵称违规（不是封号） |
| `ClientSuspectedAsCheater` | 402 | | 疑似作弊 |
| `ServerFailedToHandleRequest` | 500 | | 通用 500 |
| `SessionTimeOver` | 33005 | | 会话超时 |
| `AccountContentBan` | **ABSENT** | — | **客户端 629 个成员里有，Shittim 611 个成员里没有** ⇒ 想用内容封禁要自己补 |
| `FeatureSuspendedNotice` | **ABSENT** | — | 同上（"功能暂停公告"） |

### 2.3 官方会怎么封一个人（结论）

```
官方面板/风控 → 把账号置为 Dormant（或写 NCC 封禁记录）
    → 客户端 1014 Account_CheckNexon
        → 服务端拒绝：Protocol=Error, ErrorCode=AccountLoginError(1025), BanReason="<日期/事由>"
            → 客户端按 ErrorCode 选包体 = AccountBanErrorPacket
                → 弹本地文案「账号已被禁止使用，/ 如有任何问题请咨询客服！/ 封禁周期至：」+ BanReason
```

**之所以敢下这个结论**：客户端本地化表里那条封禁文案是**以冒号结尾、等拼一段串**的（行 167），而 `AccountBanErrorPacket` 的全部数据字段就是**一个 string** —— 两者互为唯一解。

### 2.4 我们现在实际走的是哪条（重要：现在弹不出来是"设计"问题，不是 bug）

- 守卫：`AccountHandler.cs:104-112`（BAPATCH-BAN v1），`State == Dormant` ⇒ `throw new UnauthorizedAccessException("ACCOUNT_SUSPENDED")`。
- 网关兜底：`GatewayController.cs:290-297`
  ```csharp
  catch (UnauthorizedAccessException ex) {
      // ... InvalidSession triggers the client's clean return-to-title + relogin flow.
      await CreateProtocolErrorResponse(ex.Message, WebAPIErrorCode.InvalidSession, responseCrypto);
  }
  ```
- 包体：`GatewayController.cs:778-799` 固定构造 `new ErrorPacket { Reason = reason, ErrorCode = errorCode }`；
- 而 `ErrorPacket.Reason` **是 `[Newtonsoft.Json.JsonIgnore]`**（`NetworkProtocol.cs:786-787`，注释："official error packets are exactly Protocol/ErrorCode/ServerTimeTicks - no reason text on the wire"）⇒ 线上只有 `{"ErrorCode":3}`。
- 客户端拿到 `InvalidSession` → 本地文案是 `无效的会话。`（`LocalizeErrorDB` 行 4）→ 干净地回标题、重新登录。

**⇒ 现在被封的人看到的是"无效的会话"，不会看到任何封禁说明。** 要把"封号时间 X 至 Y，请联系客服"显示出来，**必须换包体**，不是换 `Reason` 字符串。

---

## 3. §3 服务端推文本的可用通道清单（按实现难度排序）

> "改客户端"这一列是**本表最重要的一列**。全部候选都验过。

| # | 通道 | 协议/字段 | 客户端在哪渲染、渲染成什么 | 我们能不能注入任意文本 | **需要改客户端吗** | 难度 | 结论 |
|---|---|---|---|---|---|---|---|
| **A** | **`AccountBanErrorPacket`（官方封禁包）** | `Protocol.Error` + `ErrorCode=1025(AccountLoginError)` + `BanReason`(string) | 本地文案行167 + `BanReason` 拼在"封禁周期至："后面 → **模态弹窗**（登录阶段就会弹，见 §1.4） | ✅ `BanReason` 是**自由字符串**（日期区间、事由都可） | **❌ 不需要** | ★★ | **✅ 首选** |
| **B** | `AccountContentBanErrorPacket`（内容封禁区） | `Protocol.Error` + `ErrorCode=AccountContentBan` + `ContentType` + `BanStartDate`/`BanEndDate` | 本地文案行407：`检测到异常游戏记录，相关内容的使用将被限制 {0} 天。限制时间：{1}~ {2}` → 弹窗，客户端自己格式化两个日期 | ⚠️ 只能填"种类/起止时间"，**文案固定**；且 `AccountContentBan` 的数值 Shittim 里没有 | **❌ 不需要**（但要给服务器补枚举值） | ★★★ | 备选（语义是"功能封禁"，不是封号） |
| **C** | SDK `/common/client-code` 错误码表 | SDK 层 HTTP：`{"Code":400101,"Msg":"…","Data":{}}` 从 `/user/login`、`/user/quick-login`、`/user/detail` 返回，配合 `/common/client-code` 下发 `{"CodeList":[{"Code":"400101","Type":"dialog","Value":"<文案>"}]}` | 写进客户端 SQLite `error_msg(code,msg,type)`；`TipsActivity`（`res/o4.xml`）弹窗，`type="toast"` 走 toast | ✅ `Value` 完全自由 | **❌ 不需要** | ★★★ | ⚠️ **能，但有两个坑**：<br>① `initAllErrorMsg()` 懒加载 ⇒ **开机后第一次报错必显"未知错误，请联系客服。"**，第二次才用我们的文案（`SDK_LOGIN_UI_STUDY.md:485-487`）；<br>② **`Msg` 本身不显示**（只进 logcat + 交给 Unity 的 `R_MSG`，`SDK_LOGIN_UI_STUDY.md:439`）⇒ 现成的 `_build_banexp\ban_message.py` 把文案放在 `Msg` 里，**玩家一个字都看不到**（`:533-541`） |
| **D** | SDK `/user/login` 的 `Msg` | `{"Code":400101,"Msg":"封号时间…"}` | **不渲染**（只 `MyLog.e` + `map.put("R_MSG", msg)`） | ✅ 但没用 | ❌ | — | **❌ 无效通道**（`SDK_LOGIN_UI_STUDY.md:414-439`） |
| **E** | `AccountAuthResponse.IssueAlertInfos` | `IssueAlertInfoDB{ Subject, Url, StartDate, EndDate, DisplayOrder, PublishId }` | 客户端有 `NoticeSortingService`（`CompareDisplayOrder`/`CompareDate`/`Sort`）与 `ManagementNoticeData{Id,StartDate,EndDate,Url,Title,DisplayOrder}` —— **两个结构字段一一对应** ⇒ 是"公告/告警列表"数据源，**列表项，不是强制弹窗** | ✅ `Subject` 自由 | ❌ 不需要 | ★★★ | 可用作"运营公告"，**不满足"必须看到的封禁提示"** |
| **F** | 公告 `Notice_*` | — | **客户端 `Protocol` 枚举 501 个成员里 `Notice` 命中 0 个**（`_banui_tmp\q3_protocol.py`）⇒ 游戏协议层**根本没有公告协议**；`UINotice`/`UIEventNoticeList` 由非协议数据驱动（`ManagementNoticeData` 来自本地/网表） | ❌ | — | — | **❌ 不存在这条通道**（不是"难"，是"没有"） |
| **G** | 邮件 `Mail_List` | `MailDB{ Sender, Comment, LocalizedComment(Dictionary<Language,string>), SendDate, ExpireDate, ParcelInfos… }`（`DBModel.cs:1495-1515`） | 邮箱列表里的**一封信**，点开看正文 | ✅ `Comment`/`LocalizedComment` 自由 | ❌ 不需要 | ★★ | ⚠️ 只能"通知"，**没有"必须确认"的弹窗**；`MailDB` 也没有"弹窗"字段 |
| **H** | `AccountDB.State` | `Account_Auth` 回包里的 `State` | **没有任何 UI 分支**（§1.2） | ❌ | — | — | **❌ 单独改 State 不会弹任何东西**（但它仍是封禁的"开关"，见 §4） |
| **I** | `WebAPIErrorCode.AccountUpdateStateFail(1017)` 等普通错误码 | `Protocol.Error` + 某个既有码 | 本地文案（如 `无效的会话。`） | ❌ 文案固定在客户端 | ❌ | ★ | **❌ 只能选预置文案** |
| **J** | Shittim 自制"维护公告" `ServerNoticeService` | `server_notice.json` → `GateError`/`GateMessage`；`ManagementController.cs:732-760` | `GateMessage` **只进日志**；线上只有 `ErrorCode`（`GatewayController.cs:243,260,304` 全部走 `CreateProtocolErrorResponse`） | ✗（`GateMessage` 不上线） | ❌ | ★ | **❌ 现状无效**（但 `GateError` 这套"拦所有协议 + 回错误码"的框架**可以复用**到 A 上） |
| **K** | 改 `LocalizeError` Excel 表（asset 侧） | — | 改文案本身 | ✅ | ✅ **需要**（改 asset，不是改 dex） | ★★★★ | 见 §4.4：**不推荐且基本不可行** |
| **L** | 改 dex（`HttpCallBack.handleErrorCode` 用入参 msg） | — | 首个错误即生效 | ✅ | ✅ **需要** | ★★★★★ | ❌ **dex 不能重编**（E43，`ba-pitfalls.md:53`、`_dd4-integrity.md:444`） |

**一句话：零改客户端的任意文本弹窗，只有 A（首选）和 C（次选）两条；A 是官方的路，且没有 C 的"第一次报错"缺陷。**

---

## 4. §4 零改客户端的实现路径

### 4.1 为什么一定会分派到 `AccountBanErrorPacket`（强推断，附验证办法）

客户端要为 `Protocol.Error` 选一个具体类型来反序列化，可用的判别信息只有 `ErrorCode`（包里其它字段都因 `NullValueHandling.Ignore` 而缺失）。而客户端/服务端这套 DTO 的写法给了直接线索：

| 包 | `ErrorCode` 是"字段"还是"常量 getter" | 含义 |
|---|---|---|
| `ErrorPacket` | `<ErrorCode>k__BackingField`（**字段**） | 可承载任意码 |
| `InventoryFullErrorPacket` | `get_ErrorCode`（**常量** = `InventoryAlreadyFull`） | 码即类型 |
| `MailBoxFullErrorPacket` | `get_ErrorCode`（**常量** = `MailBoxFull`） | 码即类型 |
| `AccountBanErrorPacket` | `get_ErrorCode`（**常量** = `AccountLoginError`） | **码即类型** |
| `AccountContentBanErrorPacket` | `get_ErrorCode`（**常量** = `AccountContentBan`） | **码即类型** |

⇒ 这 5 个类构成一个**"按 ErrorCode 分派"的封闭集合**；除了 `ErrorPacket`，每个都把自己的码写死。这正是"服务端只发码、客户端据此选类"的设计。**所以发 `ErrorCode=1025` 时，客户端应当解成 `AccountBanErrorPacket` 并拿到 `BanReason`。**

> 这是本次唯一"强推断而非铁证"的关键环节（元数据不含 IL，`libil2cpp.so` 有 iFix 包装层，纯静态拿不到分派表）。**§6-1 给了 10 分钟真机验证法。**

### 4.2 实现路径（推荐 A：官方封禁包）

**改动面：2 个文件、约 25 行。**

#### ① 让封禁守卫带上"时间窗"

`work\ba\srv_src\Shittim-Server\Core\NetworkProtocol\Handlers\AccountHandler.cs:104-112`

```csharp
// >>> BAPATCH-BAN v1 BEGIN >>>
var loginAccount = await db.Accounts.FirstOrDefaultAsync(a => a.PublisherAccountId == publisherId);
if (loginAccount != null && loginAccount.State == AccountState.Dormant)
    throw new UnauthorizedAccessException("ACCOUNT_SUSPENDED");
// <<< BAPATCH-BAN v1 END <<<
```

改成（`CheckNexon` 与 `CheckYostar` 两个入口都要改，源码里这段是复制了两份）：

```csharp
// >>> BAPATCH-BAN v2 BEGIN >>>
var loginAccount = await db.Accounts.FirstOrDefaultAsync(a => a.PublisherAccountId == publisherId);
if (loginAccount != null && loginAccount.State == AccountState.Dormant)
{
    // BanWindow: 起止时间文案。为空 -> 永久封禁。
    var window = BanWindowService.Describe(publisherId);   // "2026-11-18 20:00 至 2026-11-20 20:00" 或 ""
    throw new WebAPIException(WebAPIErrorCode.AccountLoginError, "BANEXP|" + window);
}
// <<< BAPATCH-BAN v2 END <<<
```

- 用 `WebAPIException`（已有：`Schale\MX\NetworkProtocol\WebAPIException.cs`）而不是 `UnauthorizedAccessException`，好处是 `catch (WebAPIException)` 分支（`GatewayController.cs:283-288`）会**原样保留我们给的 `ErrorCode`**，不会被改写成 `InvalidSession`。
- `BanWindowService.Describe()`：复用已经存在的文案实现 —— `work\ba\server\deploy\_build_banexp\ban_message.py:53-63,136-153`（`fmt_time()` / `ban_message()`，规则：Asia/Shanghai 写死 UTC+8、`%Y-%m-%d %H:%M`、秒截断、起点缺失退化成"起点=终点"）。数据源用面板的 `bans` 表（`kind='account', target=<publisherId>, until_epoch, created_at`，见 `_build_banexp\schema.sql` 与 `CHECK.md:125`）。

#### ② 让网关把 `AccountLoginError` 出成 `AccountBanErrorPacket`

`work\ba\srv_src\Shittim-Server\Controllers\Api\GatewayController.cs:778-799`（`CreateProtocolErrorResponse`）

```csharp
private async Task CreateProtocolErrorResponse(string reason, WebAPIErrorCode errorCode, GatewayCryptoContext crypto)
{
    var errorPacket = new ErrorPacket { Reason = reason, ErrorCode = errorCode };
    ...
}
```

改成：

```csharp
private async Task CreateProtocolErrorResponse(string reason, WebAPIErrorCode errorCode, GatewayCryptoContext crypto)
{
    // >>> BAPATCH-BANPACKET v1 >>>
    ResponsePacket errorPacket;
    if (errorCode == WebAPIErrorCode.AccountLoginError)
    {
        // "BANEXP|<window>"；window 为空 = 永久封禁，不给尾巴（客户端的固定文案本身就带"请联系客服"）
        var tail = reason.StartsWith("BANEXP|") ? reason.Substring(7) : reason;
        errorPacket = new AccountBanErrorPacket { BanReason = tail };   // ErrorCode 由类常量给出 = 1025
    }
    else
    {
        errorPacket = new ErrorPacket { Reason = reason, ErrorCode = errorCode };
    }
    // <<< BAPATCH-BANPACKET v1 <<<
    var res = new ServerResponsePacket { Protocol = Protocol.Error.ToString(), Packet = JsonConvert.SerializeObject(errorPacket, jsonSettings) };
    ...
}
```

要点：
- `AccountBanErrorPacket` **已在源码里**（`NetworkProtocol.cs:804-809`），不用新增类型。
- `jsonSettings` 是 `NullValueHandling.Ignore`（`GatewayController.cs:122-124`）⇒ `BanReason` 必须非空才上线；永久封禁时给 `""` 会被省略，客户端就只显示三行固定文案（这正好是想要的效果）。
- 注意 `AccountBanErrorPacket.BanReason` 是 string；`ErrorPacket.Reason` 是 `[JsonIgnore]`，两者别搞混。

#### ③ 客户端会看到什么

```
┌──────────────────────────────────┐
│  账号已被禁止使用，                 │
│  如有任何问题请咨询客服！            │
│  封禁周期至：2026-11-18 20:00 至 2026-11-20 20:00 │
│                        [ 确定 ]   │
└──────────────────────────────────┘
```

- 文案前两行半 = 客户端本地（`LocalizeErrorDB` 行 167，`_banui_tmp\q5_excel3.py`）。
- 冒号后 = 我们的 `BanReason`（完全自由）。
- **"请联系客服"这句天然就有**，不需要我们自己写。

#### ④ 必须同时做的事（否则前面全白做）

| # | 事项 | 依据 |
|---|---|---|
| 1 | **桥的 1014 缓存必须加 TTL 或强制失效**，否则封禁永远打不到 Shittim | `BAN_AND_DELETE_STUDY.md:39,104-124,150-164`；`account_auth_probe.py:1890-1898`（缓存直接 return）、`:1914`（`created` 只写不读） |
| 2 | 确认现网 DLL 是**含 BAPATCH-BAN** 的构建 | `BAN_AND_DELETE_STUDY.md:58-65`（`strings -e l ... \| grep -c ACCOUNT_SUSPENDED`，必须 `-e l`） |
| 3 | `SelectedAccountId` 为 0（否则守卫查的号和发出去的号不是同一行） | `ServerConfig.cs:48`、`SessionKeyService.cs:84-87` |
| 4 | 面板写库确实落库（`SELECT State FROM Accounts WHERE ServerId=N` 立刻验） | `BAN_AND_DELETE_STUDY.md:45,73` |

### 4.3 如果 A 那条路真机上不显示（备选 C，仍然零改客户端）

1. 桥（或 SDK 服务）实现 **`/common/client-code`**，返回
   ```json
   {"Code":200,"Msg":"success","Data":{"CodeList":[
      {"Code":"400101","Type":"dialog","Value":"封号时间 2026-11-18 20:00 至 2026-11-20 20:00，请联系客服"}
   ]}}
   ```
   （形状与 `error_msg` 建表 SQL：`SDK_LOGIN_UI_STUDY.md:456-480`）
2. `/user/login` / `/user/quick-login` / `/user/detail` 命中封禁时返回 `{"Code":400101,"Msg":"...","Data":{}}`。
3. 玩家看到：第一次 `Code≠200` → **"未知错误，请联系客服。"**（因为 `initAllErrorMsg()` 懒加载）；这时表已被填充，**玩家再登一次就显示我们的文案**。
4. 若把 `Type` 写成 `"toast"`：走 toast，`res/RT.xml` 的 TextView `singleLine=false`、**无 maxLines 上限**，但**前面永远带 `"<code>:  "` 前缀**且 ~3.5 s 消失（`SDK_LOGIN_UI_STUDY.md:411-412`）。

### 4.4 "必须改客户端"时的最小改法（结论：代价高，不建议）

**前提是铁律：dex 不能重编**（改 dex 会卡启动界面：`work\ba\audit\ba-pitfalls.md:53`、`work\ba\noroot\_dd4-integrity.md:444` 的 R4）。所以在"不改 dex"的约束下，客户端侧只剩两个地方可动：

| 路径 | 可行性 | 说明 |
|---|---|---|
| **res/ + AndroidManifest.xml（AXML）** | **❌ 做不出"动态文案弹窗"** | res 只能加静态字符串/布局；`TipsActivity` 的文案来自 SQLite `error_msg` 表（运行时数据），不是 `R.string`。改 AXML 最多能改 Activity 的 label/图标，改不了弹窗内容。而且改 AXML 要重签，会踩完整性校验 | 
| **assets（`LocalizeError` Excel 表）** | **⚠️ 理论可行、工程不可行** | 文案在 `ExcelDB`-类资源里（FlatBuffer，`LocalizeErrorDBSchema`）；改了就换掉全局错误文案，**改不了"不弹"变成"弹"**，也无法携带动态时间。同时这是 asset 改动，同样要重签 |
| **dex/smali** | **❌ 硬禁** | E43 + R4 |

**⇒ 结论：不要走"改客户端"这条路。** 上面 A 已经能做到零改客户端，且用的就是官方机制。

---

## 5. §5 文本容量与格式限制

| 通道 | 承载字段 | 服务端侧上限 | 客户端渲染上限 | 结论 |
|---|---|---|---|---|
| **A `AccountBanErrorPacket.BanReason`** | JSON string | **无协议级限制**（JSON 字符串；网关整体 body 受 Kestrel/反代限制，远超需求） | 固定前缀 `账号已被禁止使用，`+`如有任何问题请咨询客服！`+`封禁周期至：` 已占 **3 行 / 27 个全角字符**；`BanReason` 拼在第 3 行冒号后。**弹窗 TMP label 的 `maxLines` 未取到（元数据里没有 UI 布局参数），需要真机量。** | **建议 `BanReason` ≤ 40 字符**（如 `2026-11-18 20:00 至 2026-11-20 20:00` = 35 字符），保证 4~5 行内放下 |
| **B `AccountContentBanErrorPacket`** | `ContentType`(int) + 2 个 DateTime | — | 文案 `检测到异常游戏记录，相关内容的使用将被限制 {0} 天。限制时间：{1}~ {2}`（2 行 + 约 40 字符） | 日期由客户端格式化，**格式未知**（依赖客户端 CultureInfo，需真机确认是 `2026-11-18 20:00` 还是 `2026/11/18 20:00`） |
| **C `/common/client-code`（弹窗）** | `Value` string | — | `TipsActivity` + `res/o4.xml`，`@id/tv_tips_content` **`maxLines=4` 硬上限**，超出以 "…" 截断 ⇒ **约 50–60 个汉字**（`SDK_LOGIN_UI_STUDY.md:27-28,363-370`） | 我们的文案 `封号时间 2026-11-18 20:00 至 2026-11-20 20:00，请联系客服` = **45 字符**，**贴边、能放下但很紧** |
| **C'（toast 变体）** | `Value` string | — | `res/RT.xml`，`maxWidth=@dimen/dp300`、`singleLine=false`、**无 maxLines**；**自动消失 ~3.5 s**；**前缀强制 `"<code>:  "`** | 不截断但会消失，且多一个码前缀，不适合"封禁通知" |
| **E `IssueAlertInfoDB.Subject`** | string | — | 列表项标题 | 无强制弹出 |
| **G `MailDB.Comment` / `LocalizedComment`** | string / 多语言字典 | — | 邮件正文（可滚动） | 容量最大，但不是弹窗 |

**格式注意（A 通道）**

- 时间格式跟 `ban_message.py` 一致：`%Y-%m-%d %H:%M`、Asia/Shanghai（**写死 UTC+8，不依赖 tzdata**）、秒截断不四舍五入（`ban_message.py:11-22,34-42`）。
- 文案里**不要带换行 `\n`**：客户端是把它拼在第 3 行冒号后，带换行可能把 label 撑出边界。
- 永久封禁：`BanReason` 传空 ⇒ `NullValueHandling.Ignore` 会整字段省略 ⇒ 只剩三行固定文案（`封禁周期至：` 后为空），**建议永久封禁时给 `BanReason = "永久"`**，避免出现"周期至："后面空着。
- 若一定要"永久"语义干净，也可用 `AccountContentBan` 之外的 `BanDay` 语义（`AccountBanByNexonDB.BanDay`）——但客户端没有这个类型，别用。

---

## 6. §6 不确定项（直说，不编）

| # | 不确定的事 | 为什么不确定 | **怎么验（具体办法）** |
|---|---|---|---|
| **1** | **`ErrorCode=1025` 时客户端是否真的解成 `AccountBanErrorPacket` 并把 `BanReason` 显示出来** | 本次结论的最关键一环靠的是"5 个错误包按 `ErrorCode` 分派"这一**强推断**（§4.1）。元数据不含 IL；`libil2cpp.so` 的协议 DTO getter 落在 `0x07EE6xxx` 这种**非可读页**（`_banui_tmp\diag_bl.py` 反汇编为空），且客户端有 iFix 包装层（`SessionTask::HandleErrorMessage` 里就能看到 `IFix.WrappersManagerImpl::IsPatched/GetPatch`），纯静态拿不到分派逻辑 | **10 分钟定论**：① 桥/网关把 1014 的拒绝临时改成 `AccountBanErrorPacket{BanReason="TEST-2026-11-20 20:00"}`；② 手机 `adb logcat -s AiriSDK Unity` 看有没有 `HandleErrorMessage`/`LocalizeError` 痕迹；③ 看屏幕：出现"账号已被禁止使用…封禁周期至：TEST-2026-11-20 20:00" ⇒ **A 通道成立**；只出现"无效的会话。"或静默回标题 ⇒ 不成立，转 C。④ 想更硬：`adb shell settings put global http_proxy` + `tcpdump -A -s0 -i any port 5000` 抓明文包头，确认线上真的发出 `{"ErrorCode":1025,"BanReason":"..."}` |
| **2** | `BanReason` 是拼在"封禁周期至："**后面**，还是**替换**整段文案 | 只能从"文案以冒号结尾"推 | 同 #1 的观察；或故意传一个明显串（`TEST123`）看它出现在哪 |
| **3** | 客户端 `AccountContentBan` 的**数值** | `fieldDefaultValues` 段取不出来（取值全是乱的，疑似同样被 XOR 混淆）；Shittim 的 611 成员里根本没有这个成员 | 真机抓官方包，或对 iFix 层断点；**在此之前不要用 B 通道**，只用 A（`AccountLoginError=1025` 是现成可用的） |
| **4** | `LocalizeError` 行 → `ErrorCode` 的**数值映射** | `LocalizeErrorDBSchema.Key` 是 `TableEncryptionService.Convert(uint)` 的产物，我按 `Schale\Crypto\{TableEncryptionService,MersenneTwister,XOR}.cs` 逐行实现（xxHash32→MT19937→8 字节 key，见 `_banui_tmp\q2_keys.py`）**解出来不是错误码**（429 行全部 > 700）⇒ 该 ExcelDB 的 Key 不是"服务端配方能解的那种密文"（可能导出时 `UseEncryption=false`，Key 仍是客户端侧密文） | 不影响结论（文案与包的对应靠"占位符/冒号"形状确定）；若要精确：真机 hook `LocalizeData.GetText` 打出入参即可 |
| **5** | 弹窗在 **1014 阶段**（还没进大厅）到底弹不弹 | 本地化表里多条登录期错误写着"将返回标题画面"，说明登录期有模态框；但封禁文案没有这句，无法 100% 确定它在 1014 阶段可用（也可能只在 `Account_Auth` 之后） | 若 1014 不弹，把同一包的发送点挪到 **`Account_Auth`**（`AccountHandler.cs:125-175`）的守卫位置——同样零改客户端，注意会话已生成、要同时 `RevokeSession` |
| **6** | 桥的 1014 合成缓存现网到底命中率多高 | 需要现网日志 | `grep -c '"session_source": "cache"' /www/wwwroot/bapatch/logs/api_all_requests.log`；或 `touch /www/wwwroot/bapatch/cn_bridge_force_reauth.txt` 后重登，看是否才被封（`BAN_AND_DELETE_STUDY.md:74-75`） |
| **7** | 游戏内弹窗 label 的 `maxLines` / 字号 | 布局参数不在元数据里（在 asset bundle 的 prefab 上） | 真机截图量；或按 §5 的建议把 `BanReason` 压到 ≤40 字符 |
| **8** | `BanDB` 是不是真有协议在用它 | Shittim 源码里 0 引用；客户端有类型 | 抓官方包看有没有哪个 response 带 `BanDB`；**目前用不上** |

---

## 附录 A：本次新增的只读工具（都在 `_banui_tmp\`，不碰既有文件）

| 文件 | 作用 |
|---|---|
| `mdq.py` | il2cpp 元数据查询库（type/field/method/字符串堆/`mdef→Type.Method`），读 `report\_tmp\patch\md_deob.bin` |
| `q1_scan.py` / `.out.txt` | 35105 个类型名的封禁/告警/弹窗普查 |
| `q1_types.py` / `.out.txt` | 封禁相关类型的字段/方法逐条 dump |
| `q1_auth.py` / `.out.txt` | 客户端 `AccountAuthResponse`(27 字段) / `ErrorPacket` / `WebAPIErrorCode`(629) 形状 |
| `q1_errpath.py` / `.out.txt` | 错误码→文案→弹窗管线的方法名普查 |
| `q1_popups.py` | `LocalizeErrorExcel` / `AlertPopup*` / `MessagePopup*` / `UITitleAlertPopup` 形状 |
| `q1_callers.py` / `.out.txt` + `diag_bl.py` | `ba_ptrs.bin`(154173) + BL 扫描做调用者分析（用于发现 getter 被内联，从而排除这条路） |
| `q1_outline.py` | 方法 → 反汇编 → 每个 `bl` 还原成 `Type::Method`（发现 `SessionTask::HandleErrorMessage` 调 `LocalizeData::GetText`） |
| `q3_notice.py`、`q3_protocol.py` | 公告/邮件/DTO 普查；证明客户端 501 个协议里 `Notice` = 0 |
| `q5_excel.py`、`q5_excel2.py`、`q5_excel3.py` | 从 `work\ba\data\ExcelDB.db` 解 `LocalizeErrorDBSchema` 429 行中文文案 |
| `q2_align.py`、`q2_keys.py`、`q2_enumvals*.py` | 行序对齐、Key 解密尝试、客户端枚举常量还原（均未成功，已在 §6 记录） |

## 附录 B：证据来源（可复核）

```
客户端元数据   report\_tmp\patch\md_deob.bin (38426024 B) + ba_ptrs.bin
               report\_tmp\patch\{md_lookup.py,tool.py,build_ptrs.py,build_codemap.py}   ← 既有，未重生成
               布局：22×u32/type(SZ 88), 9×u32/method(SZ 36), 3×u32/field(SZ 12)
本地化数据     work\ba\data\ExcelDB.db → LocalizeErrorDBSchema(429) / AlertPopupDBSchema(1) / MessagePopupDBSchema(77)
客户端代码     work\ba\audit\ba-work\x\lib\arm64-v8a\libil2cpp.so (270927056 B)
               SessionTask::HandleErrorMessage  mdef 65624  va 0x0739F478
               HttpGameSession::BuildErrorMessage mdef 65994  va 0x06E138FC  (2 指令, 空实现)
服务端 DTO     work\ba\srv_src\Schale\MX\NetworkProtocol\NetworkProtocol.cs
                 :87-118 AccountAuthResponse(27 字段)   :782-789 ErrorPacket
                 :791-796 InventoryFullErrorPacket      :798-802 MailBoxFullErrorPacket
                 :804-809 AccountBanErrorPacket
               work\ba\srv_src\Schale\MX\NetworkProtocol\ProtocolData.cs :649 enum WebAPIErrorCode / :720 AccountLoginError=1025
               work\ba\srv_src\Schale\MX\GameLogic\DBModel\DBModel.cs
                 :94-105 AccountBanByNexonDB   :154-159 AccountRestrictionsDB   :297-307 BanDB
                 :1468-1485 IssueAlertTypeCode/IssueAlertInfoDB   :1470-1472 All=1/File_Target=2/AllButFile_Exception=3
                 :1495-1515 MailDB            :122-147 AccountDB(State=w130)
               work\ba\srv_src\Schale\FlatData\AccountState.cs :8-15
网关           work\ba\srv_src\Shittim-Server\Controllers\Api\GatewayController.cs
                 :122-124 jsonSettings(NullValueHandling.Ignore)   :283-306 三段 catch
                 :290-297 UnauthorizedAccessException → InvalidSession   :778-799 CreateProtocolErrorResponse
封禁守卫       work\ba\srv_src\Shittim-Server\Core\NetworkProtocol\Handlers\AccountHandler.cs :104-112
维护公告       work\ba\srv_src\Shittim-Server\Services\ServerNoticeService.cs :11-66（GateMessage 不上线）
SDK 链路       work\ba\plan\20261118\SDK_LOGIN_UI_STUDY.md
                 :24-28 摘要  :292-348 链路  :363-370 TipsActivity maxLines=4
                 :411-412 toast  :414-439 Msg 不显示  :443-487 /common/client-code 与两个坑  :533-541 banexp 用 Msg ⇒ 玩家看不到
封禁现状       work\ba\plan\20261118\BAN_AND_DELETE_STUDY.md
                 :39 桥缓存绕过  :45 面板落库判定  :58-65 DLL 守卫扫描  :104-124 守卫位置  :150-164 实际时序
文案实现(已存在) work\ba\server\deploy\_build_banexp\ban_message.py :41-42,53-63,136-153
                 （`封禁，请联系客服` / `封号时间 %s 至 %s，请联系客服`，Asia/Shanghai 写死 UTC+8、%Y-%m-%d %H:%M、秒截断）
面板           work\ba\cardadmin_php\inc\players.php:420-427 → inc\ba.php:368-382 → ManagementController.cs:167-191
```
