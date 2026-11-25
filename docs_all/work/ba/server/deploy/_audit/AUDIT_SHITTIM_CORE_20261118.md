# Shittim 主程序（C#）只读安全审计 — 2026-11-18

> 范围：`work\ba\srv_src\Shittim-Server\`（源码只读）
> 方法：`read` / `grep` / 脚本化静态扫描（501 个 `[ProtocolHandler]` 全覆盖）
> **未修改任何 .cs、未编译、未触碰服务端与手机**
> 标注：**[已证实]** = 代码直接读到；**[推断]** = 由代码行为推出未实跑；**[我猜]** = 明确猜测

---

## 总览

| 严重度 | 条数 |
|---|---|
| **高危** | **5** |
| **中危** | **7** |
| **低危** | **2** |
| **已做对（值得记录）** | **6** |

---

# A. 认证与会话

## A1. 票据解析（`Account_CheckNexon` / `Account_CheckYostar`）

```csharp
// AccountHandler.cs:58-63  （CheckYostar 在 :885-890，逐字相同）
58  var ticketBytes  = Convert.FromBase64String(request.EnterTicket);
59  var ticketString = Encoding.UTF8.GetString(ticketBytes);
60  var parts        = ticketString.Split('/');
62  var publisherId  = long.Parse(parts[0]);
63  var token        = parts[1];
```

**缺什么校验**（全部缺失）：

| 缺项 | 后果 | 严重度 |
|---|---|---|
| `parts.Length == 2` 不检查 | 少于 2 段 ⇒ `IndexOutOfRangeException`（未捕获 ⇒ 500） | 低危 **[已证实]** |
| `base64` 非法不捕获 | `FormatException` ⇒ 500 | 低危 **[已证实]** |
| `long.Parse` 无 `TryParse`/范围检查 | 超长/负数/0 都能进（`publisherId = -1` 合法） | **中危 [已证实]** |
| **token 内容完全不校验**（见 A1-2） | 任意字符串均可登录 | **高危 [已证实]** |

## A1-2. ★ 高危①：token **从不校验**，任意 `publisherId` 可登录任意账号

```csharp
// AccountHandler.cs:65-94
65  var user = await db.UserAccounts.FirstOrDefaultAsync(u => u.NpSN == publisherId);
68  if (user == null) { ...建号... }
90  else if (user.NpToken != token)
92      user.NpToken = token;        // ★ 覆盖写，不是拒绝
```

- **身份只有 `parts[0]`（`publisherId`）**，`token` 的唯一作用是"变了就更新记录"。
- ⇒ 只要知道/猜到一个 `publisherId`（卡密口径是 **9 位、md5(card) 派生、连续可枚举量级**），**任何人都能登录该账号**，无需卡密、无需任何凭证。
- 对照：`Account_Auth(1002)` 只校验 `SessionKey != null`（`:123-124`），而 SessionKey 正是上面这条免费发出来的。
- **严重度：高危 [已证实]**

## A2. `Account_Auth(1002)` 的 SessionKey 校验路径

```csharp
// AccountHandler.cs:123-126
123  if (request.SessionKey == null)
124      throw new UnauthorizedAccessException("Session key required");
126  var account = await _sessionService.GetAuthenticatedUser(db, request.SessionKey);
```

- 真正的校验在 `SessionKeyService.GetAuthenticatedUser`（`SessionKeyService.cs:160-174`）：会话存在性、`MxToken` 比对、账号存在性 —— **这三步做得对**。
- **但校验的是"会话"而不是"身份"**：会话是从 A1-2 那条免费路径拿到的，所以校验强度等于 0。
- **严重度：中危（校验本身对，但上游凭证不可信）[已证实]**

## A3. `SessionKeyService` 的签发/过期/复用/绑定

| 项 | 现状 | 严重度 |
|---|---|---|
| 签发 | `Guid.NewGuid()`（`:103-105`）⇒ **不可预测，做得对** | 已做对 |
| 绑定 | 只绑 `account.ServerId`（`:109,115`），**不绑 IP/设备** | 低危 |
| 过期 | `ValidateRequest` 里有 `BypassAuthentication` 短路（`:133`），`GetAuthenticatedUser` **不检查过期**，只检查存在性 | 中危 **[已证实]**：会话可长期有效（`PurgeExpiredSessions` 需外部定时调用） |
| 复用 | `BAPATCH-SESSION-REUSE`（`:92-101`）让**同账号永不重铸**，旧 token 一直有效 | 低危（原生行为，但扩大了泄露窗口） |
| **`SelectedAccountId` 覆盖** | `:84-87` `if (selectedId > 0) account = ...SelectedAccountId... ?? account;` ⇒ **任何 publisher 都会被强制映射到同一个账号** | **中危/高危（取决于配置）[已证实]** |

```csharp
// SessionKeyService.cs:84-87
84  // Account selected in the Control Center wins over the publisher mapping, so any Steam identity logs into the chosen roster entry.
85  var selectedId = Config.Instance.ServerConfiguration.SelectedAccountId;
86  if (selectedId > 0)
87      account = await db.Accounts.FirstOrDefaultAsync(a => a.ServerId == selectedId) ?? account;
```
⇒ 多玩家场景下这是**越权**：任何人登录都会落到"选中账号"。

## A4. 是否每个 handler 都调了 `GetAuthenticatedUser`？

**脚本全量扫描 501 个 `[ProtocolHandler]`，13 个没有直面 `GetAuthenticatedUser`**，逐个人工核对：

| handler | 文件:行 | 判定 |
|---|---|---|
| `Account_CheckNexon` | `AccountHandler.cs:52` | 登录前协议，**正常** |
| `Account_CheckYostar` | `:879` | 同上 |
| `Account_Auth2` | `:793` | `:799 await Auth(...)` 委托，**有校验** |
| `Account_PassCheck` | `:863` | 只生成会话密钥（`GatewaySessionCryptoBuilder`），不碰账号数据，**可接受** |
| `Account_LinkReward` | `:773` | **空实现** `return response;`，无数据访问 |
| `Billing_CheckConditionCashShopGoods` | `BillingHandler.cs:272` | **永远 `result = true`**（`:278-280`），无数据访问 |
| `Clan_Join` | `ClanHandler.cs:482` | 经 `SchaleNetworkSeat`(:511) → `GetAuthenticatedUser`(:513)，**有校验（脚本误判）** |
| `Queuing_*` ×4 | `QueuingHandler.cs:21/42/76/99` | 排队阶段、登录前，**正常** |
| `System_Version` / `Error` | `SystemHandler.cs:27/65` | 公开协议，**正常** |

**⇒ 结论：没有发现"漏调鉴权导致越权读数据"的 handler。A4 = 已做对（唯一可议的是 `Billing_CheckConditionCashShopGoods` 恒 true）。**

---

# B. 管理/高危接口

## B5. `[AdminAuth]` 是否每个 action 都挂？

```csharp
// AdminController.cs:12-15
12  [ApiController]
13  [Route("api/admin")]
14  [AdminAuth]
15  public class AdminController : ControllerBase

// ManagementController.cs:24-27
24  [ApiController]
25  [Route("api/admin")]
26  [AdminAuth]
27  public class ManagementController : ControllerBase
```
- **两个 Controller 都是类级挂载** ⇒ 全部 28 个 action **无一遗漏**。全工程 grep `[AllowAnonymous]` = **0 命中**（唯一命中在注释里 `AdminAuthAttribute.cs:12`）。
- **⇒ 已做对 [已证实]**

## B6. ★ 高危②：**没有权限分级**

- `AdminAuthAttribute` 是**单一布尔门**：要么 `X-Admin-Key` 完全正确，要么来自环回地址，**没有"只读管理员 / 财务管理员 / 超级管理员"之分**（`AdminAuthAttribute.cs:20-43`）。
- ⇒ 拿到这把 key（或只要能连上本机端口），就可以：改任意账号货币、发任意奖励、**删号**、跑**任意 GM 命令**。
- **严重度：高危（设计缺口）[已证实]**

## B7. ★ 高危③：loopback 豁免 + 无分级 ⇒ 同机任何进程都是超级管理员

```csharp
// AdminAuthAttribute.cs:31-32
31  if (IsLoopback(context.HttpContext.Connection.RemoteIpAddress))
32      return;
```
- 任何能连到本机端口的进程（面板、nginx 反代、被挂马的 web 服务、同机任何用户）都是**免密钥超管**。
- 属性注释自己也承认了这个依赖：`":13 Loopback acceptance leans on the CORS policy staying narrow; widening it needs this revisited."`
- key 比较本身做得好：`CryptographicOperations.FixedTimeEquals`（`:60-62`）、支持环境变量（`:47-49`）。
- **严重度：高危（部署面）[已证实]**

## B8. ★ 高危④：`command` 端点 = 任意代码/文件操作的 GM 后门

```csharp
// ManagementController.cs:431-466
437  var parts = request.Command.Trim().Split(' ', StringSplitOptions.RemoveEmptyEntries);
438  var name = parts.First().TrimStart('/', '!', '.', '*').Split('/').Last();
445  var connection = _webService.GetClient(request.Uid, writer);
450  cmd = CommandFactory.CreateCommand(name, connection, args);
460  await cmd.Execute();
```
- **`Uid` 可指向任意账号**（`WebConnection.cs:31` `AccountServerId = _accountServerId` 直通）。
- **命令无白名单**：`accountdata load` 会**读服务器上的文件**并导入存档（`AccountDataCommand.cs`），`unlockall`、`setaccount`、`currency` 等全部可达。
- 与 B6/B7 叠加 ⇒ 同机任意进程可对**任意玩家**执行任意命令。
- **严重度：高危 [已证实]**

---

# C. 数据层

## C8. 字符串拼接 SQL

全工程原文 SQL 只有 **2 处**：

| 位置 | 形态 | 判定 |
|---|---|---|
| `ManagementController.cs:213-232` | `SqlQueryRaw` 读 `sqlite_master` + `$"DELETE FROM \"{table}\"..."` | **已做对**：表名先经 `IsPlainSqlIdentifier` 白名单（`:222`，实现 `:196-198`），参数用 `{0}` 占位 |
| `AccountHandler.cs:955-966`（`Account_Reset`） | 同上，但**没有** `IsPlainSqlIdentifier` | **中危 [已证实]**：表名直接插入 SQL，缺同款白名单 |

```csharp
// AccountHandler.cs:962-966
962  foreach (var table in tables.Distinct())
963  {
964      await db.Database.ExecuteSqlRawAsync(
965          $"DELETE FROM \"{table}\" WHERE AccountServerId = {{0}}", account.ServerId);
966  }
```
- 注入前提是"库里出现恶意表名"（表名来自 Excel 导入/迁移脚本，**不是** HTTP 输入）⇒ **中危（非高危）**。
- 但**同一份逻辑在另一处有守卫、这一处没有**，属明显疏漏。

## C9. EF 表达式里拼接外部输入

- 扫描 `Where(...)` 中的字符串插值：**未发现**把请求字段拼进 SQL 文本的写法；所有查询是 LINQ 表达式（参数化）。
- ⇒ **已做对 [已证实]**

---

# D. 输入校验

## D10. 各 handler 入参校验覆盖

| 场景 | 现状 | 严重度 |
|---|---|---|
| `Echelon_Save`（编队保存） | `EchelonManager.cs:14-23`：`mapper.Map<EchelonDBServer>(echelonData)` 后**直接落库**，**不校验角色是否属于本账号、不校验槽位数** | **高危 [已证实]** |
| `Shop_Buy` 购买数量 | `ShopHandler.cs:522-527` `ValidatePurchaseCount` + `MaxPurchaseCountPerRequest` | **已做对** |
| `Account_Nickname` | `AccountHandler.cs:271` `account.Nickname = request.Nickname;` **无长度/字符/保留字校验** | 中危 |
| `account/update`（管理端） | `ManagementController.cs:172-177` 同样直接赋值（`Nickname/Comment/Level/Exp`） | 中危 |
| `currency/set` | `AdminController.cs:86` `currencies.CurrencyDict[currencyType] = request.Amount;` **无上界、可为负** | 中危 |
| `items/give` | `ManagementController.cs:306-312` `StackCount` 直接赋 `Amount`（可负、可超大） | 中危 |
| `mail/send` | `AdminController.cs:40-44` `Parcels` **无条数上限**，`Amount` 无范围 | 中危 |
| `Mission_Reward` 等 | 有 `MissionExcel` 存在性校验（查不到返回空），**已做对** | 已做对 |

## D11. 反序列化入口

```csharp
// Controllers\Api\GatewayController.cs:122-128
122  private static readonly JsonSerializerSettings jsonSettings = new JsonSerializerSettings
123  {
124      NullValueHandling = NullValueHandling.Ignore,
125      DefaultValueHandling = DefaultValueHandling.Ignore,
126      ContractResolver = new OfficialContractResolver(),
127      Converters = { new OfficialDateTimeConverter() }
128  };
```
- **未设置 `TypeNameHandling`** ⇒ Newtonsoft 默认 `None` ⇒ **无 `$type` 反序列化 RCE**（已做对 [推断]）。
- **未设置 `MaxDepth` / `CheckAdditionalContent`** ⇒ 深嵌套 JSON 可致栈溢出/CPU 打满（**中危 · 推断**）。
- **全工程无 `MaxRequestBodySize` / `RequestSizeLimit` / Kestrel `Limits`** ⇒ 依赖 Kestrel 默认 30MB 上限（**中危 · 推断**）。
- 另注：`HexaMapService` 用 `TypeNameHandling.Auto` + 自定义 binder（`HexaMapService.cs:16-19`），但输入是**服务器本地 strategymap JSON**，非用户输入 ⇒ 低危。

---

# 汇总表

## 高危（5）

| # | 位置 | 问题 | 证据 |
|---|---|---|---|
| H1 | `AccountHandler.cs:58-63, 90-94` | **token 从不校验**，任意 `publisherId` 可登录任意账号 | 已证实 |
| H2 | `ManagementController.cs:431-466` | `command` 端点 = 任意 GM 命令 + 任意 `Uid`，含读文件的 `accountdata load` | 已证实 |
| H3 | `AdminAuthAttribute.cs:20-43` | **无权限分级**：单 key / 环回 = 全权（改钱、删号、跑命令） | 已证实 |
| H4 | `AdminAuthAttribute.cs:31-32` | **环回免密钥** ⇒ 同机任意进程都是超管 | 已证实 |
| H5 | `EchelonManager.cs:14-23` | `Echelon_Save` **不校验角色归属/槽位数**，客户端可提交他人 `ServerId` | 已证实（无校验）/ 影响面推断 |

## 中危（7）

| # | 位置 | 问题 |
|---|---|---|
| M1 | `SessionKeyService.cs:84-87` | `SelectedAccountId > 0` 时**任何身份都映射到同一账号**（越权） |
| M2 | `SessionKeyService.cs:160-174` | 会话**不检查过期**（只查存在与 token 一致） |
| M3 | `AccountHandler.cs:962-966` | `Account_Reset` 拼表名无 `IsPlainSqlIdentifier`（另一处 `ManagementController.cs:222` 有） |
| M4 | `AccountHandler.cs:271` | 昵称**无长度/字符校验** |
| M5 | `AdminController.cs:86` / `ManagementController.cs:306` | 货币/道具数量**无范围校验**（可负、可超大） |
| M6 | `GatewayController.cs:122-128` | 反序列化**无 `MaxDepth`**、全工程**无请求体大小限制** |
| M7 | `AccountHandler.cs:58-63` | 票据解析无长度/格式/`TryParse` 防护（畸形票据 ⇒ 500） |

## 低危（2）

| # | 位置 | 问题 |
|---|---|---|
| L1 | `SessionKeyService.cs:109,115` | 会话只绑 `ServerId`，不绑设备/IP |
| L2 | `BillingHandler.cs:278-280` | `Billing_CheckConditionCashShopGoods` 恒 `true`（无鉴权，但无数据访问） |

## 已做对（6，值得保留）

1. 管理员 key 用 `CryptographicOperations.FixedTimeEquals` 常量时间比较 — `AdminAuthAttribute.cs:60-62`
2. 两个 Admin Controller **类级** `[AdminAuth]`，28 个 action 全覆盖，无 `[AllowAnonymous]` — `AdminController.cs:14`、`ManagementController.cs:26`
3. 删号 SQL 有 `IsPlainSqlIdentifier` 白名单 + 参数化 — `ManagementController.cs:196-198, 222, 226`
4. 购买数量有上下界校验 — `ShopHandler.cs:522-527`
5. 会话 token 用 `Guid.NewGuid()` 不可预测 — `SessionKeyService.cs:103-105`
6. 网关未启用 `TypeNameHandling`（无反序列化 RCE）— `GatewayController.cs:122-128` [推断]

---

## 附：本次扫描口径

- 全量 `[ProtocolHandler]`：**501** 个，脚本逐个提取方法体检查 `GetAuthenticatedUser`。
- 原文 SQL：全工程 **2 处**（`SqlQueryRaw`/`ExecuteSqlRaw` 共 6 次调用，集中在 2 个方法）。
- `[AllowAnonymous]`/`[Authorize]`：**0 处实际使用**。
