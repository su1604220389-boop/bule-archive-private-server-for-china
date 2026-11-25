# 免 root 机「同步帐号信息时发生错误」取证（2026-11-18）

> 只读取证。未改任何 `.cs`、未重编译、未碰服务端/手机。
> 源码：`work\ba\srv_src\Shittim-Server\`（`AccountHandler.cs` 1046 行、`SessionKeyService.cs`、`ExcelTableService.cs`）
> 标注：`[确证]` = 直接读到代码；`[推断]` = 由代码行为推出，未实跑；`[未证实]` = 需要日志/DB 才能确认

---

## 0. 结论先行（TL;DR）

**服务端对 token 的校验是「零」。** `Account_CheckNexon` / `Account_CheckYostar` 只把票据 `base64("<publisherId>/<token>")` 拆成 `publisherId` 和 `token`，**token 只被写进 `UserAccounts.NpToken`，从头到尾没有一次比对/签名验证**（`AccountHandler.cs:58-63, 90-94`；`:885-890, 917-921`）。

⇒ **token 校验不可能是"这台机报错"的原因**——它根本不校验，行为对两台机完全一致。

**最可能的真凶（按证据强度排序）**：

| # | 假设 | 强度 | 一句话 |
|---|---|---|---|
| **1** | 桥的 `acct_apply_to_auth` 把 `AccountDB.ServerId`/`SessionKey` 覆盖成 **account_service 的 10_000_000_000 号段**，而 Shittim 的 `_activeSessions` 里没有这个 key ⇒ LoginSync 第一步 `GetAuthenticatedUser` 抛 `Session expired or invalid` | **已证实（代码）/ 未证实（哪台机触发）** | 会话表和注入的身份不在一套 id 空间 |
| **2** | 免 root 机是**全新安装、无本地缓存**，所以第一次就带着注入的 SessionKey 走完整登录；root 机可能复用旧缓存或走了 fallback 分支 | 推断 | 缓存差异而非服务端差异 |
| **3** | 新机 `DevId` 与旧机不同 ⇒ account_service 建了**新账号行**，`AccountDB` 指向一个 Shittim 里不存在的账号 | 推断（与 1 同源） | 见 §B5 |
| **4** | 客户端 roster 不匹配（BAPATCH-CLIENTROSTER 那 23 个 id） | 低 | 同一台服务端、同一份 Excel，root 机能过 ⇒ 除非新机装的是不同 build |

---

## A. token 校验

### A1. `Account_Auth(1002)` 里怎么校验 token？—— **不校验**

`Account_Auth` 的完整校验逻辑只有两行（`AccountHandler.cs:117-126`）：

```csharp
117  [ProtocolHandler(Protocol.Account_Auth)]
118  public async Task<AccountAuthResponse> Auth(...)
123      if (request.SessionKey == null)
124          throw new UnauthorizedAccessException("Session key required");
126      var account = await _sessionService.GetAuthenticatedUser(db, request.SessionKey);
```

- **`Account_Auth` 的入参里根本没有 token 字段**：它只认 `SessionKey`（`McToken` + `AccountServerId`）。
- **没有任何"只接受我们自己签发的 token"这一步**：全文件 0 处校验 token 内容/签名/长度/来源。
- `[确证]` grep `AccountHandler.cs` 的 `throw new` 只有 5 处：`:103`(ACCOUNT_SUSPENDED)、`:124`(Session key required)、`:248`(Session required)、`:253`(Account not linked to publisher)、`:930`(ACCOUNT_SUSPENDED)。**没有一处与 token 相关。**

**token 唯一出现的地方是 `Account_CheckNexon`（`AccountHandler.cs:52-116`）**：
```csharp
58      var ticketBytes  = Convert.FromBase64String(request.EnterTicket);
59      var ticketString = Encoding.UTF8.GetString(ticketBytes);
60      var parts        = ticketString.Split('/');
62      var publisherId  = long.Parse(parts[0]);     // ← 身份只取这一段
63      var token        = parts[1];                 // ← token 只做下面这件事
...
90      else if (user.NpToken != token)
92          user.NpToken = token;                   // ★ 只是"更新记录"，不是"校验"
93          await db.SaveChangesAsync();
```
⇒ **客户端随便传什么 token 都能过**；`user.NpToken != token` 分支是**覆盖写**，不是拒绝。

`Account_CheckYostar` 是同一段代码的复制（`AccountHandler.cs:879-943`，`:885-890` 解析、`:917-921` 同样的覆盖写）。

### A2. token 与什么绑定？校验失败返回什么？

- **绑定关系（现状）**：token 只被存进 `UserAccounts.NpToken`（`AccountHandler.cs:74`、`:92`），**不参与任何判定**。
- **校验失败的错误码**：**不存在**（因为没有校验）。
- 真正会抛的只有会话层（`SessionKeyService.cs:160-174`，`GetAuthenticatedUser`）：

| 行 | 条件 | 抛出的异常 |
|---|---|---|
| `:163-164` | `_activeSessions` 里没有 `sessionKey.AccountServerId` | `UnauthorizedAccessException("Session expired or invalid")` |
| `:166-167` | `MxToken` 与 `ActiveSession.Token` 不一致 | `UnauthorizedAccessException("Session token mismatch")` |
| `:171-174` | 会话存在但 `Accounts` 里找不到该 `ServerId` | `UnauthorizedAccessException("User not found")` |
| `:160-161` | `SessionKey == null` | `UnauthorizedAccessException("Session key is required")` |

### A3. 桥那一层做没做校验？

`[推断·基于本地副本]` 桥（`account_auth_probe.py`）**没有 token 校验**，它做的是**替换**：
```python
# _baseline\account_auth_probe.py:98-124  acct_apply_to_auth
114      inner['AccountDB'] = adb            # ← 用 account_service 的账号覆盖
115      inner['SessionKey'] = sk            # ← 用 account_service 的会话覆盖
```
它的 `identify()` 只认 `DevId`/`DeviceUniqueId`（`:108` 的兜底字典），**不看 token 是否是"我们签发的"**。
⇒ **服务端源码里没有校验；桥里也没有校验（只有身份替换）。** 明确结论：**未找到任何 token 签发-校验闭环。**

---

## B. 账号定位

### B4. `Account_Auth` 之后服务端用哪个字段查/建账号？

**`PublisherAccountId`**，且它只来自票据的第一段：
```csharp
// AccountHandler.cs:62   （CheckNexon）
62      var publisherId = long.Parse(parts[0]);
65      var user = await db.UserAccounts.FirstOrDefaultAsync(u => u.NpSN == publisherId);
68      if (user == null)                                   // 首次登录 → 建号
78          var newAccount = new AccountDBServer(publisherId);   // PublisherAccountId = publisherId
79          db.Accounts.Add(newAccount);
84          var account = await db.Accounts.FirstAsync(a => a.PublisherAccountId == publisherId);
87          await AccountInitializationService.InitializeCompleteAccount(db, account);
```
- **不用 `DevId` 定位**（`DevId` 是 `Accounts` 上的一个可空列，`AccountDB.cs:145`，登录链上从不读取）。
- **不用 openid 映射**（没有 openid 概念）。
- 建号由 `AccountDBServer(publisherId)` 完成，`ServerId` 由 EF 自增分配（`AccountDB.cs:141`）。

### B5. 卡密签出来的 `publisherId` 和"官方优星 token 的 openid"差多远？会不会新建空号？

- **卡密侧**：`sdkcard.py:43` `User.ID = int(md5(card)[:8],16) % 900000000 + 100000000` ⇒ **9 位十进制、100000000–999999999**。
- **桥侧目前是常量**：`UID = '314816420'`（`_bridge_ref\account_auth_probe.py:62`）——**这正是卡 `11111111111` 的 `User.ID`**（本轮实算 `md5('11111111111')[:8] → 314816420`）。
- **形态度量**：官方 `PublisherAccountId` 在抓包里是 11 位（`10015354380` 量级，见 `account_service.py:73` 注释）；卡密口径是 9 位。
- **会不会新建空号？会，而且这是本次事故最可疑的一环**：
  1. 新机卡密不同 → `User.ID` 不同 → `publisherId` 不同 → `UserAccounts` 查不到 → **`AccountHandler.cs:68-89` 走建号分支，新建一个 `Account` 行**；
  2. 新行只有 `InitializeCompleteAccount` 的默认种子（角色/货币/编队），**其余全空**；
  3. 若同时有桥的 `acct_apply_to_auth` 注入（见 D1），`AccountDB.ServerId` 会变成 account_service 的 `10_000_000_000+`，而 `Accounts` 表里根本没有这一行 → LoginSync 走到 `SessionKeyService.cs:171-174` 的 `"User not found"`。

---

## C. `Account_LoginSync(1019)` 的失败条件

### C6. 服务端在 LoginSync 里哪些情况会失败？

**`[确证]` LoginSync 方法体（`:298-635`）里没有任何 `throw`**（全文件 throw 只有 5 处，见 A1，均不在该区间）。**失败全部来自它调用的第一行**：

```csharp
298  [ProtocolHandler(Protocol.Account_LoginSync)]
304      var sw = System.Diagnostics.Stopwatch.StartNew();
305      var account = await _sessionService.GetAuthenticatedUser(db, request.SessionKey);   // ★ 唯一硬失败点
306      ArgumentNullException.ThrowIfNull(account);                                          // ★ 次生失败点
307      _logger.LogInformation("GetAuthenticatedUser took {Ms}ms", sw.ElapsedMilliseconds);
```

| 失败点 | 触发条件 | 客户端表现 |
|---|---|---|
| `:305` → `SessionKeyService.cs:163-164` | **会话表里没有这个 `AccountServerId`** | 拿不到 LoginSync 响应 ⇒ 弹「同步帐号信息时发生错误」 |
| `:305` → `:166-167` | `MxToken` 不匹配（会话被别的 token 顶掉/重铸） | 同上 |
| `:305` → `:171-174` | 会话有、`Accounts` 无该行 | 同上 |
| `:306` | 理论不可能（会话里有同 id 的行才会到这里） | 同上 |
| `:305` 之前/之后的深层调用 | 极少数 EF 异常、Excel 缺表（`_excelService.GetTable<CurrencyExcelT>().First(...)` `:333` 若 `ActionPoint` 行缺失会 `InvalidOperationException`） | 同上 |

> 注意 `:333` 这一句是**登录必经路径**：`GetTable<CurrencyExcelT>().First(x => x.CurrencyType == ActionPoint)` —— 若 Excel 表残缺（BAPATCH-CLIENTROSTER 只过滤 `CharacterExcelT`，不动 `CurrencyExcelT`），这里会直接抛 `InvalidOperationException: Sequence contains no elements`。

### C7. "客户端遇到不认识的 CharacterId 就中止"的证据

**有，就是 `BAPATCH-CLIENTROSTER v1`**（`ExcelTableService.cs:202-281`）。原注释把因果写死了：

```csharp
202  // >>> BAPATCH-CLIENTROSTER v1 BEGIN >>>
203  // The server's ExcelDB and the installed client's TableBundles are NOT the same build. The server roster carries
204  // students the CN client cannot resolve, and the client aborts the whole login sync when the save holds a
205  // character row with no excel entry ("The client aborts loading on a character id with no excel entry" -
206  // see AccountHandler.LoginSync). Removing those rows from the TABLE rather than policing every producer means...
210  // Measured on 2026-11-17 against the CN 3.0.2 client. The server's playable set had 257 entries; intersecting the
211  // client's CharacterAcademyTagsDBSchema (253 ids) with its CharacterDBSchema (7223 rows) leaves 234 the client can
212  // actually resolve. The 23 below are exactly that difference...
214  private static readonly long[] DefaultClientUnsupportedCharacters =
218      10099, 10137, 10138, 20057,
221      10127 ... 10136, 16018, 16019,
223      20050 ... 20056,
```

配套运行期扩展（不用重编译）：`Resources/ClientUnsupportedCharacters.txt`（`:237-246`，一行一个 id）。
过滤实现：`:257-280`（只对 `CharacterExcelT` 生效，`:259`），命中的行从**表**里删掉，因此 `!giveall`/`!give`/邮件/抽卡/商店都拿不到这些 id。

⚠ **但它救不了"新机装的是另一个 build"的情况**：过滤名单是**按 CN 3.0.2 实测的 23 个 id**（`:210`），如果免 root 包重签自另一个 build，需求集可能不同。这是**假设 4**，可通过 §D10 的方法排除。

### C8. 新账号走 LoginSync 会不会命中"数据不完整"分支？

| 数据 | 新号是否为空 | 会不会炸 | 依据 |
|---|---|---|---|
| `Characters` | **不为空**：建号时 `InitializeCompleteAccount` 种默认角色（13010 优香★2 / 16003 ★1 / 13003 ★2 / 26000 ★1） | 否 | `AccountHandler.cs:87`、`AccountInitializationService` |
| `Currencies` | 建号时种 28 项 | 否 | 同上；但 `:333` 的 `First(ActionPoint)` 依赖**Excel 表**，不是账号数据 |
| `Tutorial` | `AccountTutorials` **不建号时种**；`GetTutorial` 回 `Range(1,27)` 兜底 | 否 | `AccountHandler.cs` 的 `Account_GetTutorial` |
| `ScenarioGroupHistory` | 由 `EnsureOpenConditionScenariosCleared`（`:129`，在 **Account_Auth** 里跑）补齐 | 否（LoginSync 前已补） | `:197-214` |
| `Mails` | 空 ⇒ `mailCount=0` | 否 | — |
| **会话** | **新号第一次 LoginSync 用的 SessionKey 必须来自同一次 CheckNexon** | **是 —— 见 D1** | `SessionKeyService.cs:163` |

---

## D. 结论

### D9. 最可能是什么差异？

**按可能性排序：**

1. **【已证实·代码层】会话 id 空间冲突：** 桥把 `AccountDB.ServerId` + `SessionKey` 覆盖成 account_service 的 `10_000_000_000+`（`account_auth_probe.py:114-115`），但 Shittim 的 `_activeSessions` 只认 `GenerateSession()` 里写入的 `account.ServerId`（`SessionKeyService.cs:115`，key = `account.ServerId`）。客户端拿着注入的 SessionKey 调 LoginSync ⇒ `:163-164` 抛 `Session expired or invalid` ⇒ **「同步帐号信息时发生错误」**。
   **为什么 root 机不报**：`[推断]` root 机的请求命中了 `acct_apply_to_auth` 的 fallback 分支（`_baseline:120-123` 的 `except` ⇒ 不改响应），于是它拿到的是 Shittim 自铸的合法会话；或者它复用上一轮缓存的会话（`BAPATCH-SESSION-REUSE` 让旧会话长期活着，`SessionKeyService.cs:92-101`）。
2. **【推断】新机 = 全新安装、零缓存**：必然从 `Account_CheckNexon` 开始走完整链路，第一次就吃到注入的 SessionKey；root 机装得早、缓存在前。
3. **【推断】`DevId` 不同 ⇒ 新建账号行**：新卡/新设备 → 新 `User.ID` → `UserAccounts` 无 → `AccountHandler.cs:68-89` 建号；若随后 `Accounts` 里查不到注入的 `ServerId`，`SessionKeyService.cs:171-174` 再抛 `User not found`。
4. **【未证实】客户端 roster**：新机若装了不同 build，`BAPATCH-CLIENTROSTER` 的 23 个 id 名单可能不够 —— 但同一服务端同一 TableBundle，root 机能进大厅 ⇒ 可能性低。

**明确排除**：**token 校验不是原因**（服务端根本不校验，见 A1）。

### D10. 下一步取证（只读，二选一即可定论）

**① 一条日志 grep（最快）**：在 Shittim 日志里搜
```
Session expired or invalid
Session token mismatch
User not found
```
- 命中 `Session expired or invalid` ⇒ **假设 1 成立**（会话 id 空间冲突），直接定论。
- 命中 `User not found` ⇒ **假设 3 成立**（注入的 ServerId 在 Shittim 不存在）。
- 一条都不命中 + 有 `GetAuthenticatedUser took` ⇒ 会话过了，问题在响应内容（转 §C7 roster 方向）。

**② 两条 SQL（`schale.sqlite3`）**
```sql
-- 失败时刻有没有凭空多出一个账号行（假设 3）
SELECT ServerId, PublisherAccountId, DevId, State, Nickname, CreateDate, LastConnectTime
FROM Accounts ORDER BY ServerId DESC LIMIT 10;

-- 该 publisher 的票据 token 是否被改写（A1 的覆盖写）
SELECT NpSN, Uid, NpToken FROM UserAccounts ORDER BY rowid DESC LIMIT 10;
```
判读：若失败那台机的 `Accounts` 行 `ServerId` 是新号且 `PublisherAccountId` = 9 位卡密 UID ⇒ 假设 3；若 `Accounts` 里**压根没有** `10_000_000_000+` 的行，而日志报 `User not found` ⇒ **假设 1+3 同时成立（桥注入的就是这个号段）**。

**③ 一条桥日志（确认注入是否发生）**
```
/www/wwwroot/bapatch/tools/acct_svc.log   → 搜 "fallback to hardcoded"
```
- **失败那一次出现 `fallback`** ⇒ 桥没注入 ⇒ 问题在 Shittim 侧（转 roster/Excel，§C7）。
- **失败那一次没有 fallback 但有 `acct_server_id=1000000000x`** ⇒ **注入发生了 ⇒ 就是假设 1**。

---

## 附录：可疑点清单（本次顺带发现，建议单独立项）

| # | 发现 | 依据 | 影响 |
|---|---|---|---|
| 1 | `GenerateSession` 里 **`SelectedAccountId > 0` 会覆盖 publisher 映射** | `SessionKeyService.cs:84-87` | 开了"选中账号"后，**任何身份都会登录到同一个号**——多玩家方案必须关掉它（`SelectedAccountId=0`） |
| 2 | `Account_Auth` 只校验 `SessionKey != null` | `AccountHandler.cs:123-126` | 任何人拿到一个有效 SessionKey 就能读任意会话所属账号 |
| 3 | `AccountHandler.cs:253` `throw new InvalidOperationException("Account not linked to publisher")` | `Account_Create` 分支 | 若新号 `PublisherAccountId` 为空会在这里炸 |
| 4 | LoginSync `:333` 硬依赖 `CurrencyExcel ActionPoint` 行存在 | `AccountHandler.cs:333` | Excel 残缺时登录直接 500 |
| 5 | `BAPATCH-CLIENTROSTER` 只过滤 `CharacterExcelT` | `ExcelTableService.cs:259` | 其它表（道具/装备/活动）没有同类保护 |
