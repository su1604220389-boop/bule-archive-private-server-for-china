# 76 · L1/L2 路由与会话 —— Shittim 服务端源码对照

- 取证范围：**只读本地** `report/_tmp/shittim/raw/*.json`（GitHub API 返回的 JSON 包装，`content` 字段是 base64 的 C# 源码）
- 解码产物（本次自建，未改他人文件）：`report/_tmp/l1l2/src/`（解码脚本 `report/_tmp/l1l2/decode.py`）
- 交叉源（只读）：`work/ba/proto/shittim_types.json`（Shittim DTO 类型转储）、`work/ba/proto/dto_schema_full.json`（客户端 metadata 提取）
- 上游仓库：`Neoexm/Shittim-Server@main`，`sha` 见每个 `.json` 的 `sha` 字段
- 未连接手机 / 未 ssh / 未 adb / 未碰 `libtprt.so`

> **证据纪律**：本文每条结论标注 `[源码]`（直接读到代码）、`[源码推断]`（代码在这、但真实行为要结合客户端）、`[源码中未见]`（该文件不在本地抓取集或该功能不存在）。凡标 `[源码中未见]` 的一律不补猜测。

---

## §0 结论先行（5 行）

1. **`SessionKey` 不是 `Queuing_GetTicket` 下发的**。它只由**三个** handler 生成：`Account_CheckNexon(1014)` / `Account_CheckYostar(1009)` / `Account_Create(1000)`；`Account_Auth(1002)` 自己**不生成**，由网关层**回显请求里带的那个**（`Account_Auth2` 只是 `Auth` 的别名，同样不生成）。
2. **但国服没有 CheckNexon 这一步**（我们客户端只发过 `1001/1002/1010/1019/24000`），所以国服路径上 `Account_Auth` 必须**自己 mint** 一个 SessionKey 塞进响应 —— 这正是我们缺的境界。
3. **`SessionKey` 结构 = `{ AccountServerId: long, MxToken: string }`**，`MxToken` 就是一个 `Guid.NewGuid().ToString()`（36 字符小写带连字符），不是 hex、不是随机字节、不是 base64。
4. **`AccountId` 不是独立字段**，它是 `BasePacket` 上的**只读派生属性** `SessionKey?.AccountServerId ?? 0`。**只要发了 SessionKey，`AccountId` 自动出现**；不发就自动消失。这解释了"真服 24 键含 SessionKey+AccountId、我们的没有"是**同一个缺口**。
5. **`AccountLoginSyncResponse.Responses` 是 `ResponsePacket?`（单个可空引用，且 `ResponsePacket` 是抽象类）**，Shittim **全仓库从不给它赋值**（`grep '\.Responses'` 零命中）。我们发的 `"Responses": []`（数组）**类型不符**。正确做法：**整个 `Responses` 键不要出现**，26 个子回包放在**同名兄弟字段**里。

---

## §1 `SessionKey` 全生命周期（生成 → 下发 → 回填 → 校验）

### 1.1 数据结构

`Schale.MX.NetworkProtocol.Packet.cs:8-12` `[源码]`

```csharp
public class SessionKey
{
    public long AccountServerId { get; set; }
    public required string MxToken { get; set; }
}
```

`Schale.MX.NetworkProtocol.Packet.cs:14-21` `[源码]`

```csharp
public abstract class BasePacket
{
    public SessionKey? SessionKey { get; set; }
    public abstract Protocol Protocol { get; }
    // Official responses carry a top-level AccountId exactly when they carry a SessionKey ...
    public long AccountId => SessionKey?.AccountServerId ?? 0;
}
```

**关键**：`AccountId` 是 **getter-only 派生属性**，没有 setter、没有 backing field。Newtonsoft 序列化只读属性 → 会输出；配合 `DefaultValueHandling.Ignore`，`0` 被丢弃。于是：

| SessionKey | 线上 AccountId | 线上 SessionKey |
|---|---|---|
| `null` | 不出现 | 不出现 |
| `{AccountServerId: 2, MxToken:"..."}` | `2` | 出现 |

`Account_CheckNexon` 的响应 DTO 上还专门留了注释警告这件事（`NetworkProtocol.cs:448`）：**不要写 `new SessionKey` 遮蔽基类属性**，否则 `AccountId` 掉 0 被丢掉。

### 1.2 生成：`ISessionKeyService` 是什么

`Shittim-Server/Services/ISessionKeyService.cs:7-14` `[源码]`

```csharp
public interface ISessionKeyService
{
    Task<SessionKey?> GenerateSession(long publisherAccountId, string? customToken = null);
    bool ValidateRequest(RequestPacket request);
    Task<AccountDBServer> GetAuthenticatedUser(SchaleDataContext context, SessionKey? sessionKey);
    void RevokeSession(long userId);
    int PurgeExpiredSessions(TimeSpan maxInactivity);
}
```

实现：`Shittim-Server/Services/SessionKeyService.cs`（206 行，`AddMemorySessionKeyService` 注册为 **Singleton**，`SessionKeyService.cs:201-204`）。

**生成代码（原文，`SessionKeyService.cs:77-112`）** `[源码]`

```csharp
public async Task<SessionKey?> GenerateSession(long publisherAccountId, string? customToken = null)
{
    await using var db = await _dbFactory.CreateDbContextAsync();

    var account = await db.Accounts
        .FirstOrDefaultAsync(a => a.PublisherAccountId == publisherAccountId);

    // Account selected in the Control Center wins over the publisher mapping ...
    var selectedId = Config.Instance.ServerConfiguration.SelectedAccountId;
    if (selectedId > 0)
        account = await db.Accounts.FirstOrDefaultAsync(a => a.ServerId == selectedId) ?? account;

    if (account == null)
        return null;

    var tokenGuid = string.IsNullOrEmpty(customToken)
        ? Guid.NewGuid()
        : Guid.Parse(customToken);          // ← customToken 必须是 GUID 格式，否则抛

    var session = new ActiveSession
    {
        UserId = account.ServerId,
        Token = tokenGuid,
        CreatedAt = DateTime.UtcNow,
        LastActivity = DateTime.UtcNow
    };

    _activeSessions.AddOrUpdate(account.ServerId, session, (_, _) => session);
    PersistSessions();

    return new SessionKey
    {
        AccountServerId = account.ServerId,
        MxToken = tokenGuid.ToString()      // ← 36 字符小写 "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
    };
}
```

**格式结论** `[源码]`

| 项 | 值 |
|---|---|
| 类型 | `string` |
| 长度 | **36**（`Guid.ToString()` 的 D） |
| 字符集 | `0-9a-f` + 4 个 `-` |
| 示例 | `3f2b9c1e-8a44-4d2f-9c77-1b0e5a6d4c31` |
| 来源 | `Guid.NewGuid()`（v4 随机） |
| **不是** | hex 串、base64、随机字节、JWT、HMAC |

**存在哪 / 生命周期** `[源码]`

| 项 | 值 | 依据 |
|---|---|---|
| 主存储 | 进程内 `ConcurrentDictionary<long /*ServerId*/, ActiveSession>` | `SessionKeyService.cs:14` |
| 持久化 | 写穿到 `Config/sessions.json`（`AppContext.BaseDirectory` 下） | `SessionKeyService.cs:30-33, 60-75` |
| 重启 | 启动时 `LoadPersistedSessions()` 回灌，**重启不掉线** | `SessionKeyService.cs:36-58` |
| 过期 | **不会自动过期**——`PurgeExpiredSessions(maxInactivity)` 有实现但**本地源码里没有调用点** | `SessionKeyService.cs:172-188` + `grep` 零命中 |
| 一个用户一个 session | `AddOrUpdate(UserId, ...)`：同一账号重复登录**覆盖**旧 token | `SessionKeyService.cs:104` |
| 失效 | `RevokeSession(userId)`（`Account_InvalidateToken` 走这里） | `SessionKeyService.cs:166-170` |

> 源码注释还写了一条踩坑记录（`SessionKeyService.cs:30-31`）：会话只在 RAM 时，服务端重启后客户端手里的 `MxToken` 静默失效，下一次请求就死在一个泛化错误上，客户端显示为 "Abnormal client" / "A request that cannot be processed"。**这就是"客户端不报具体错、只报同步失败"这一类症状的已知成因**，对我们有直接参考价值。

### 1.3 下发：SessionKey 到底在哪个响应里？

先给否决项：**`Queuing_GetTicket` 完全不涉及 SessionKey。**

`Shittim-Server/Core/NetworkProtocol/Handlers/QueuingHandler.cs:42-74` `[源码]` 全文只碰 `EnterTicket / Birth / TicketSequence / AllowedSequence / RequiredSecondsPerUser / ServerSeed / ServerTimeTicks`：

```csharp
[ProtocolHandler(Protocol.Queuing_GetTicket)]
public Task<QueuingGetTicketResponse> GetTicket(...)
{
    byte[] rawTicketBytes = Encoding.UTF8.GetBytes($"{request.NpSN}/{request.NpToken}");
    response.EnterTicket = Convert.ToBase64String(rawTicketBytes);
    response.Birth = "";
    response.TicketSequence = 130_000_000 + (DateTimeOffset.UtcNow.ToUnixTimeSeconds() % 10_000_000);
    response.AllowedSequence = response.TicketSequence + 1722;
    response.RequiredSecondsPerUser = 0.0058;
    response.ServerSeed = "";
    response.ServerTimeTicks = 0;
    return Task.FromResult(response);
}
```

它下发的 `EnterTicket`（= base64(`"NpSN/NpToken"`)）是**给 `Account_CheckNexon` 当输入用的票据**，不是会话。

真正的下发点（三处 `[源码]`）：

| 协议 | 位置 | 行为 |
|---|---|---|
| `Account_CheckNexon` (1014) | `AccountHandler.cs:52-106` | **生成**：`var sessionKey = await _sessionService.GenerateSession(publisherId); response.SessionKey = sessionKey;`（96-100 行） |
| `Account_CheckYostar` (1009) | `AccountHandler.cs:899-953` | **生成**：943-947 行，同构 |
| `Account_Create` (1000) | `AccountHandler.cs:231-251` | **重新生成**：`GenerateSession` + `response.SessionKey = newSession`（247-248 行） |
| `Account_Auth` (1002) | `AccountHandler.cs:107-157` | **不生成**！函数体里从头到尾没有 `response.SessionKey = ...` |
| `Account_Auth2` (1012) | `AccountHandler.cs:813-821` | 它是 `await Auth(db, request, response); return response;` —— **也不生成**，只是 Auth 的别名 |
| `ProofToken_RequestQuestion` / `ProofToken_Submit` (37000/37001) | `GatewayController.cs:317-322` | 回显 |

**`Account_Auth` 的 SessionKey 从哪来 —— 网关层回显** `[源码]`

`Shittim-Server/Controllers/Api/GatewayController.cs:261-263`

```csharp
// Official responses echo SessionKey plus the derived top-level AccountId ONLY on the account/security
// handshake protocols; every other response omits both. Handlers that mint a new session (CheckNexon/Create)
// set SessionKey themselves.
if (rsp.SessionKey == null && ShouldEchoSessionKey(protocol))
    rsp.SessionKey = payload.SessionKey;
```

`GatewayController.cs:317-322`

```csharp
// Protocols whose responses officially carry SessionKey/AccountId, from live captures:
// Account_CheckNexon, Account_Auth, ProofToken_RequestQuestion, ProofToken_Submit.
private static bool ShouldEchoSessionKey(Protocol protocol) => protocol
    is Protocol.Account_Auth
    or Protocol.Account_Auth2
    or Protocol.ProofToken_RequestQuestion
    or Protocol.ProofToken_Submit;
```

**这段注释是整份源码里对我们最有价值的一句**：它明确写"官方 `Account_Auth` 的响应**确实带** SessionKey/AccountId（live capture 验证）"，机制是 **echo request.SessionKey**。

`[源码推断]` 由此得到国服路径（无 CheckNexon）的推演：

- 国际服：`Queuing_GetTicket` → `Account_CheckNexon(EnterTicket)` 拿 session → `Account_Auth` 带 session → 回显。
- 国服：**没有** CheckNexon（我们客户端 5 个协议号里没有 1009/1014）。客户端第一条业务协议就是 `Account_Auth`，且请求里 `SessionKey: null`。
- 于是"回显"策略在国服下会回显 `null` → 响应照样没有 SessionKey → **死循环**。
- ⇒ 国服真服**只能在 `Account_Auth` 里自己签发**。这就是我们该做的事。
- 附带地：`Account_Auth2`(1012) 是把 `Auth` 原样转调的别名（`AccountHandler.cs:813-821`），所以它在 Shittim 里同样只靠网关回显拿 SessionKey。

> 边界说明：这一条是**推断**，不是源码直读。源码只能证明"Shittim 走回显"，不能证明"国服走签发"。但两个事实（L1：`[源码]` 回显；L2：`[本地取证 report/67]` 客户端首包即 1002 且 SessionKey 为 null）合起来，只剩"签发"一个自洽解。

### 1.4 回填：客户端把 SessionKey 放哪？

**放在请求体的 `BasePacket.SessionKey` 里，不是 HTTP 头。** `[源码]` 依据：

`SessionKeyService.cs:114-145`

```csharp
public bool ValidateRequest(RequestPacket request)
{
    if (_publicProtocols.Contains(request.Protocol)) return true;
    if (request.SessionKey == null) return false;                       // ← 从 RequestPacket 上取
    ...
    if (_activeSessions.TryGetValue(request.AccountId, out var session)) // ← 从 RequestPacket 上取
    {
        if (session.Token.ToString().Equals(request.SessionKey.MxToken, StringComparison.OrdinalIgnoreCase))
```

`request` 的类型是 `RequestPacket`（`BasePacket` 的子类，`Packet.cs:23`），`request.SessionKey` / `request.AccountId` 都是**包体字段**。整个 `GatewayRequest` 只从 `Request.Form.Files.GetFile("mx")` 取一个二进制体（`GatewayController.cs:160`），没有读任何鉴权头。

我们抓到的客户端请求明文与之吻合（`report/67` §2）：

```json
{"Protocol":"Account_LoginSync","SyncProtocols":[],"SkillCutInOption":"","Resendable":false,
 "Hash":4376571674624,"IsTest":false,"SessionKey":null,"AccountId":0,"OSType":2}
```

⇒ `SessionKey` 与派生 `AccountId` 都在**包体顶层**，和 `Protocol`/`Hash` 平级。

> 注意国服差异：这条请求里有 `"OSType":2`（整数），而 Shittim 的 `BasePacket`（`Packet.cs:14-21`）**没有 `OSType`**，`AccountAuthRequest.OSType` 是 `string?`（`NetworkProtocol.cs:75`）。⇒ 国服 `BasePacket` 多一个 `OSType` 枚举字段，且是数字。我们解析时要容错（忽略即可），不要因为多字段回 400。

### 1.5 校验：服务端怎么验？`GatewaySessionCrypto` 在里面起什么作用？

**结论：`GatewaySessionCrypto` 与 SessionKey 没有半点关系。** `[源码]`

`Shittim-Server/Core/GatewaySessionCrypto.cs:10-14`

```csharp
public sealed record GatewaySessionCrypto(
    string EncryptedKey,
    string SignedKey,
    string EncryptedIV,
    string SignedIV);
```

这是**传输层**握手：客户端在 `Queuing_GetCryptoKeys` / `Account_CheckNexon` 里带 `ClientGeneratedKey` / `ClientGeneratedIV`（AES-128/192/256 key + 16B IV，或 RSA-4096 密文），服务端（`Build`，53-71 行）：

1. 用 `DecodeClientCrypto`（73-101）取出**客户端生成的** key/iv —— 若长度不像 AES key 则按 RSA 解（OAEP-SHA256/SHA1/PKCS1/OAEP-SHA384/SHA512 依次试，`105-148`）。
2. 生成**服务端自己**的 `serverKey`/`serverIv`（`RandomNumberGenerator.GetBytes(16)`），用**客户端的 key/iv** 做 AES-CBC 加密成 `EncryptedKey`/`EncryptedIV`。
3. 用**网关 RSA 私钥**对这些**密文**做签名（`SignBase64`，227-246，**SHA1 + PKCS1**）→ `SignedKey`/`SignedIV`。

它管的是"响应体要不要 AES 加密、用谁的 key"，判断在 `ShouldUseAes`（`GatewayController.cs:759-762`）→ `CreateProtocolResponse`（791-800）把**整个 `{protocol,packet}` 信封**塞进密文再 base64。

**真正的 SessionKey 校验只有两处** `[源码]`：

**(a) `ValidateRequest`（`SessionKeyService.cs:114-145`）—— 定义了但没人调用。**
全仓库 `grep ValidateRequest` 只命中接口声明 + 实现，**零调用点**。它内部还有一条 `_publicProtocols` 白名单（17-28 行）：`Queuing_GetTicket / GetCryptoKeys / GetAuthTicket / ProcessWaitingQueue / Account_CheckYostar / CheckNexon / Account_Auth / Account_Create / ProofToken_RequestQuestion` 免校验。**这是一条死代码路径**（`[源码中未见]` 调用方；`HandlerManager` 不在本地抓取集，无法 100% 排除，但 `GatewayController` 里确实没有）。

**(b) `GetAuthenticatedUser`（`SessionKeyService.cs:147-164`）—— 每个 handler 自己调，这才是真校验。**

```csharp
public async Task<AccountDBServer> GetAuthenticatedUser(SchaleDataContext context, SessionKey? sessionKey)
{
    if (sessionKey == null)
        throw new UnauthorizedAccessException("Session key is required");
    if (!_activeSessions.TryGetValue(sessionKey.AccountServerId, out var session))
        throw new UnauthorizedAccessException("Session expired or invalid");
    if (!session.Token.ToString().Equals(sessionKey.MxToken, StringComparison.OrdinalIgnoreCase))
        throw new UnauthorizedAccessException("Session token mismatch");
    session.LastActivity = DateTime.UtcNow;
    var account = await context.Accounts.FirstOrDefaultAsync(a => a.ServerId == session.UserId);
    return account ?? throw new UnauthorizedAccessException("User not found");
}
```

校验规则就三条：**SessionKey 非 null → AccountServerId 在活跃表里 → MxToken 忽略大小写相等**。

**异常怎么变成响应**（`GatewayController.cs:287-295`）`[源码]`

```csharp
catch (UnauthorizedAccessException ex)
{
    // A dead or mismatched session must NOT surface as the generic 500 ("A request that cannot be processed");
    // InvalidSession triggers the client's clean return-to-title + relogin flow.
    _logger.LogWarning("Rejected request with invalid session: {Message}", ex.Message);
    if (!Response.HasStarted)
        await CreateProtocolErrorResponse(ex.Message, WebAPIErrorCode.InvalidSession, responseCrypto);
}
```

即 `WebAPIErrorCode.InvalidSession = 3`（`ProtocolData.cs:654`），被刻意区别于 `ServerFailedToHandleRequest = 500`（`687`）。**注释明说 500 会被客户端显示成 "A request that cannot be processed"，而 3 会让客户端干净地回标题重登。** 这条对判读症状极有用。

### 1.6 §1 一句话

> SessionKey = `{AccountServerId: <服务端账号主键>, MxToken: "<36 字符 GUID>"}`，**在 `Account_Auth` 响应体顶层下发**（国际服回显自 CheckNexon 签发的那份，国服必须在此处签发），客户端把它连同 `AccountId` 一起塞进**每一条后续请求体的顶层**，服务端用 `GetAuthenticatedUser` 三条件校验。

---

## §2 `AccountId` 的来源与用法

### 2.1 定义

`Packet.cs:20` `[源码]`

```csharp
public long AccountId => SessionKey?.AccountServerId ?? 0;
```

**没有独立字段、没有独立生成逻辑、没有独立存储**。它 100% 是 `SessionKey.AccountServerId` 的镜像。

### 2.2 `AccountServerId` 从哪来

`[源码]`：`SessionKeyService.cs:98` `UserId = account.ServerId`，`:109` `AccountServerId = account.ServerId`。

`account.ServerId` 是 `AccountDBServer` 的**自增主键**（EF Core `[Key]`，`AccountDBServer` 类本体不在本地抓取集 → `[源码中未见]` 具体定义）。间接证据：

- `AccountHandler.cs:78-79` 新建账号：`var newAccount = new AccountDBServer(publisherId); db.Accounts.Add(newAccount); await db.SaveChangesAsync();` → 插入后 `ServerId` 由数据库赋自增。
- `AccountHandler.cs:84` `var account = await db.Accounts.FirstAsync(a => a.PublisherAccountId == publisherId);`
- `Schale.Data.Models.UserAccount`（`UserAccount.cs:5-15`）另有 `Id`/`Uid`/`NpSN`/`NpToken`，`Uid` 被回填成 `account.ServerId`（`AccountHandler.cs:86`）——即"发行商身份 → 游戏账号主键"的映射。

我们侧已知 `account_id=2`（`report/67`），与此一致：**小整数自增**。

### 2.3 客户端会不会回填

**会，而且是照抄。** `[源码]` + `[本地取证]`

- 客户端请求明文里有 `"AccountId": 0`（`report/67` §2）——说明客户端 `BasePacket` 上确实有这个可序列化成员。
- 服务端**从不**从请求里读 `AccountId` 做业务（`GetAuthenticatedUser` 用 `sessionKey.AccountServerId`；`ValidateRequest` 用 `request.AccountId` 但那是死代码；`GatewayController.cs:236` 的串行闸门用 `payload.SessionKey?.AccountServerId ?? 0`）。
- ⇒ 客户端把响应里的 `AccountId` 存下来，之后每条请求原样回填；**它只是会话的一致性标记，不是鉴权凭据**（鉴权靠 MxToken 比对）。

### 2.4 为什么我们"没有这两个键"是同一个缺口

因为 `AccountId` 是派生的：只要 `SessionKey` 为 null，`AccountId` 必然是 0，而 `jsonSettings` 的 `DefaultValueHandling.Ignore`（`GatewayController.cs:122-128`）会把 0 丢掉。

```
我们的 Account_Auth 响应：SessionKey 缺失 → AccountId 派生 0 → 被 Ignore 丢弃 → 两个键同时消失
真服 Account_Auth 响应：SessionKey 存在 → AccountId 派生 2 → 两个键同时出现
```

**修 SessionKey 一处，`AccountId` 自动就好了。** 不需要单独"补 AccountId 字段"。

### 2.5 为什么我们的生成器"结构性"发不出这两个键

这是本轮发现的**第二条硬证据**，解释了我们为什么"无论如何都少这两个键"。

`work/ba/proto/dto_schema_full.json` 里：

```
"ResponsePacket": { "base": null, "fieldCount": 6,
  fields: ServerTimeTicks, ServerNotification, MissionProgressDBs,
          EventMissionProgressDBDict, BattlePassMissionProgressDBDict, StaticOpenConditions }
"AccountAuthResponse": { "base": "ResponsePacket", "fieldCount": 27, ... }   ← 27 个字段里没有 SessionKey / AccountId
"BasePacket": MISSING                                                       ← 根本没解析出来
```

也就是说，我们自己的 schema **把 `ResponsePacket` 当成了根类型**，`BasePacket` 一层完全缺失 —— 于是 `SessionKey` / `AccountId` 这两个**本该由 `BasePacket` 提供的成员在 schema 里不存在**，任何基于 `dto_schema_full.json` 的生成器都**结构上不可能**产出它们。

这也解释了 §1.3 那条注释为什么值得抄：`NetworkProtocol.cs:448` 特意警告"别用 `new SessionKey` 遮蔽基类属性，否则 `AccountId` 掉 0"。**基类成员这件事在这套协议里是有坑的，我们踩的正是同一个坑的镜像版本。**

反证客户端确实有这两个成员：抓到的请求明文里有 `"SessionKey":null,"AccountId":0`（`report/67` §2）。请求侧有，响应侧不可能没有——两边共用同一个 `BasePacket`。

**全库扫描确认这不是个案**：`dto_schema_full.json` 里带 `SessionKey`/`AccountId` 字段的响应 DTO **0 个**（扫到的 16 个 `AccountId` 全是数据模型内部字段，如 `ClanMemberDB`/`FriendDB`，与包络无关）。也就是说 **444 个响应 DTO 全都结构性缺这两个键**。

**和我们的实测现象高度吻合**（这条反向验证了整个 §1.3 推论）：

| 协议 | Shittim `ShouldEchoSessionKey` 白名单 | 我们实测客户端反应 |
|---|---|---|
| `Account_Nickname` (1001) | **不在**（不该带 SessionKey） | ✅ 客户端接受 |
| `Academy_GetInfo` (24000) | **不在** | ✅ 客户端接受 |
| `Account_Auth` (1002) | **在**（官方带 SessionKey + AccountId） | ❌ 客户端随后不再发请求 |

即：**"不该带的我们没带、该带的我们也没带"**——两处都符合，但只有 `Account_Auth` 那一处要命。

⇒ **修复要动两处**：
1. `dto_schema_full.json` 里补 `BasePacket` 根（`SessionKey: SessionKey?` / `AccountId: long`），让 `ResponsePacket.base = "BasePacket"`；
2. `AccountLoginSyncResponse.fieldCount` 目前是 **31**（= 26 具名子回包 + FriendCount/FriendCode/PickupFirstGetHistoryDBs/AccountLevelRewardIds + `Responses`），说明 schema 里 `Responses` 被算成了一个字段；按 §4.2 应把它标记为"不发"而不是生成 `[]`。

---

## §3 协议路由与响应配对机制

### 3.1 注册：按 `Protocol` 枚举（int）建立三张表

`Shittim-Server/Core/ProtocolHandlerRegistry.cs:12-14` `[源码]`

```csharp
private readonly Dictionary<Protocol, MethodInfo> _handlerMethods = new();   // 协议 → handler 方法
private readonly Dictionary<Protocol, Type> _requestTypes  = new();          // 协议 → 请求 DTO
private readonly Dictionary<Protocol, Type> _responseTypes = new();          // 协议 → 响应 DTO
```

**键就是 `Schale.MX.NetworkProtocol.Protocol` 枚举**（`ProtocolData.cs:16` `public enum Protocol : int`，`Account_Auth = 1002`(28)、`Account_LoginSync = 1019`(45)、`Queuing_GetTicket = 50000`(500)）。**不是名字、不是 token、不是 URL。** URL 只有一个：`POST /api/gateway`（`GatewayController.cs:101,157`），表单字段 `mx`（160 行）——**所有协议共用同一路由**，靠包体 `Protocol` 分流。

**(a) 请求/响应 DTO 自动发现**（`ProtocolHandlerRegistry.cs:29-62`）`[源码]`

```csharp
foreach (var type in protocolAssembly.GetTypes())
{
    if (type.IsClass && !type.IsAbstract)
    {
        if (type.IsAssignableTo(typeof(RequestPacket)) && type != typeof(RequestPacket))
        {
            var instance = Activator.CreateInstance(type);
            var protocol = (Protocol)type.GetProperty("Protocol").GetValue(instance)!;
            _requestTypes.TryAdd(protocol, type);
        }
        else if (type.IsAssignableTo(typeof(ResponsePacket)) && type != typeof(ResponsePacket))
        {
            var instance = Activator.CreateInstance(type);
            var protocol = (Protocol)type.GetProperty("Protocol").GetValue(instance)!;
            _responseTypes.TryAdd(protocol, type);
        }
    }
}
```

机制：**反射扫整个协议程序集 → 无参实例化 → 读 `Protocol` 属性（`override Protocol => Protocol.X`）→ 建表**。`TryAdd` = 先到先得，重名不报错。

**(b) handler 方法注册**（`ProtocolHandlerRegistry.cs:64-104`）`[源码]`

```csharp
var methodAttributes = method.GetCustomAttributes<ProtocolHandlerAttribute>();
foreach (var attr in methodAttributes)
    if (!_handlerMethods.ContainsKey(attr.Protocol))
        _handlerMethods[attr.Protocol] = method;
    else
        _logger.LogWarning("Duplicate handler for protocol {Protocol} - ignoring ...");
```

`[ProtocolHandler(Protocol.Account_LoginSync)]` 是**方法级特性**（定义见 `ProtocolHandlerAttribute.cs:5-15`，`AllowMultiple = true`）。同样**先注册者胜**，重复只告警。

> `AddProtocolHandlers()` / `HandlerManager.Dispatch` / `IsImplemented` 的实现文件**不在本地抓取集** → `[源码中未见]`。但 `GatewayController.cs:207-230` 显示 `HandlerManager` 只是三件事的薄壳：`GetRequestType(protocol)`、`IsImplemented(protocol)`、`Dispatch(protocol, payload)`，后者内部必然落到 `ProtocolHandlerRegistry.InvokeHandler`（124-181）。

### 3.2 调用约定（反射硬约束）

`ProtocolHandlerRegistry.cs:150-174` `[源码]`

```csharp
var instance = scope.ServiceProvider.GetService(handlerType);
...
var result = method.Invoke(instance, new object[] { context, request, response });
```

- 方法签名必须是 `(SchaleDataContext, <TRequest>, <TResponse>)` **恰好 3 个参数**——`RegisterHandlerType` 就是按 `m.GetParameters().Length == 3` 找 `HandleInternal` 的（71-73）。
- **响应对象由注册表 `Activator.CreateInstance(responseType)` 建好再传进来**（141 行），handler 填字段后 `return response;`。
- 支持 `Task<TResponse>` / `Task` / 同步返回 `/ ResponsePacket` 直接返回（162-174）。

### 3.3 分发全链路（一次请求）

`GatewayController.cs:157-315` `[源码]`

```
POST /api/gateway  (multipart, field "mx")
  → DecodeGatewayPayload            (解出 JSON 明文 + 判定响应是否走 AES)
  → ReadProtocol(jsonNode)          读顶层 "Protocol"/"protocol"；整数直接 cast，字符串走 Enum.TryParse  (412-422)
  → GetRequestType(protocol)        查表，miss → 错误包 "Failed to handle protocol" (207-213)
  → JsonConvert.DeserializeObject(payloadStr, requestType)   按 DTO 反序列化  (215)
  → IsImplemented(protocol)         miss → 错误包 "Protocol not implemented (Server Error)" (223-230)
  → ReadServerNotificationAsync     在**请求进入时**算 ServerNotification 基线（不是处理完） (232-233)
  → 按 SessionKey.AccountServerId 取串行闸门 SemaphoreSlim(1,1)，20s 超时  (235-242)
  → HandlerManager.Dispatch(protocol, payload) → ProtocolHandlerRegistry.InvokeHandler  (247)
  → rsp.SessionKey 回显（白名单）  (261-263)
  → rsp.ServerNotification |= notification   (266)
  → JsonConvert.SerializeObject(rsp, jsonSettings)  (268)
  → new ServerResponsePacket{ Protocol = protocol.ToString(), Packet = responseJson }  (277)
  → CreateProtocolResponse：可选 AES → 写 body  (791-800)
```

### 3.4 响应怎么和请求配对？

**靠外层信封里的协议名，不靠 SessionKey、不靠连接、不靠 Hash。`[源码]`**

`Packet.cs:39-43`

```csharp
public class ServerResponsePacket
{
    public required string Protocol { get; set; }   // ← 枚举的**名字**
    public required string Packet { get; set; }     // ← 内层响应 JSON 的**字符串**
}
```

`GatewayController.cs:277`：`Protocol = responseProtocolName`，而 `responseProtocolName` 初始化为 `protocol.ToString()`（188 行）→ `"Account_LoginSync"` 这样的**枚举名**。

`GatewayController.cs:133-138` + `794`：外层信封用 `CamelCasePropertyNamesContractResolver`，所以线上形状是

```json
{"protocol":"Account_LoginSync","packet":"{\"Protocol\":1019,\"ServerTimeTicks\":...,\"CafeGetInfoResponse\":{...}, ...}"}
```

**判定依据（排除法，全部来自源码）**：

| 候选配对键 | 是否参与配对 | 依据 |
|---|---|---|
| 外层 `protocol` 字符串 | **是** | 唯一存在的外层元数据（`Packet.cs:41`） |
| 内层 `Protocol` int | 次要/自证 | 每个 DTO 都自带（`override Protocol`），是 DTO 身份而非配对键 |
| `SessionKey` | **否** | 只用于取账号 / 回显；从不出现在信封（`ServerResponsePacket` 只有 2 个字段） |
| `AccountId` | **否** | 同上，且只在响应体顶层 |
| 请求的 `Hash` | **否** | `ServerResponsePacket` 没有 Hash 字段；`GatewayController` 从不读 `payload.Hash`（`Hash` 仅由 `RequestPacket.CreateHash` 在客户端生成，`Packet.cs:33-36`） |
| TCP/HTTP 连接 | **否** | ASP.NET Controller 每请求一套实例（`GatewayController.cs:114` 注释明写），HTTP 无连接亲和 |

> 源码里还有一句来自客户端逆向的旁证（`GatewayController.cs:793` 注释）：
> "HttpGameSession's WaitForRequest coroutine (0x180da2773) hands the raw DownloadText to HttpGameMessage.DecodeResponse, which base64-decodes and AES-decrypts the entire body **before anything looks at the protocol field**."
> ⇒ 客户端是「先解整个 body → 再看 protocol 字段」→ 确认配对发生在**信封层**，且**信封整体在密文里**（不是明文信封套密文）。

`[源码推断]` 由此的直接后果：**同一协议名不能有两条在飞的请求**，否则客户端会错配。客户端是靠协程串行 `await WaitForRequest(Protocol.X)` 保证的 —— 这也是为什么服务端必须"每条请求都回一条包"，任何一条被静默丢弃都会让客户端那个 `await` 永久挂起。

### 3.5 `_handler` 匹配失败时怎么响应？会不会静默丢弃？

**不会静默丢弃，一定回一个 `Error` 协议包。** `[源码]`

`ProtocolHandlerRegistry.InvokeHandler` 在 miss 时 `return null`（127-131、134-138），**但上层接住了**：

`GatewayController.cs:223-230`

```csharp
if (!_handlerManager.IsImplemented(protocol))
{
    _logger.LogError("Protocol {Protocol} is unimplemented and left unhandled. Request: {Payload}", protocol, payloadStr);
    await CreateProtocolErrorResponse("Protocol not implemented (Server Error)", WebAPIErrorCode.ServerFailedToHandleRequest, responseCrypto);
    return;
}
```

`GatewayController.cs:254-259`

```csharp
if (rsp == null)
{
    _logger.LogError("Handler returned null for protocol {Protocol}", protocol);
    await CreateProtocolErrorResponse("Handler error", WebAPIErrorCode.ServerFailedToHandleRequest, responseCrypto);
    return;
}
```

`GatewayController.cs:773-789` `CreateProtocolErrorResponse` 的线上形状：

```csharp
var errorPacket = new ErrorPacket { Reason = reason, ErrorCode = errorCode };
var res = new ServerResponsePacket { Protocol = Protocol.Error.ToString(), Packet = ... };
```

而 `ErrorPacket`（`NetworkProtocol.cs:782-789`）是：

```csharp
public class ErrorPacket : ResponsePacket
{
    public override Protocol Protocol { get => Protocol.Error; }   // = -1
    [Newtonsoft.Json.JsonIgnore] public string? Reason { get; set; } // 只在日志，不上线
    public WebAPIErrorCode ErrorCode { get; set; }
}
```

⇒ 线上是 `{"protocol":"Error","packet":"{\"Protocol\":-1,\"ErrorCode\":500}"}`（`Reason` 被 `[JsonIgnore]`，`ServerTimeTicks` 非 0 会带）。

**四种失败各自回什么**（`[源码]` 汇总）：

| 情况 | 位置 | ErrorCode |
|---|---|---|
| 读不到 `Protocol` | `GatewayController.cs:181-186` | `500 ServerFailedToHandleRequest` |
| 该协议没有请求 DTO | `:207-213` | `500` |
| DTO 反序列化失败 | `:215-221` | `500` |
| 有 DTO 但没实现 | `:223-230` | `500` |
| handler 返回 null | `:254-259` | `500` |
| handler 抛 `UnauthorizedAccessException` | `:287-295` | **`3 InvalidSession`** |
| handler 抛其它异常 | `:296-303` | `500`（message 会跟着传出去） |
| 账号闸门 20s 超时 | `:237-242` | `500` |
| 被 ServerNotice 门禁 | `:201-205` | 配置指定 |

> **我们该抄的行为**：任何认不出的协议、任何异常，都要回 `{"protocol":"Error","packet":{"Protocol":-1,"ErrorCode":<code>}}`，**绝不要回 200 + 空包、也不要 5xx**。回 `Error` 至少客户端会走它的错误分支；静默/空包会让 `await` 挂到超时，正好是我们现在看到的"63 秒 → 同步账号信息时发生错误"的形态。

---

## §4 `Account_LoginSync` 的正确实现（`Responses` 到底怎么填）

### 4.1 DTO 事实

`NetworkProtocol.cs:316-321` `[源码]`

```csharp
public class AccountLoginSyncRequest : RequestPacket
{
    public override Protocol Protocol { get => Protocol.Account_LoginSync; }   // 1019
    public List<Protocol>? SyncProtocols { get; set; }
    public string? SkillCutInOption { get; set; }
}
```

`NetworkProtocol.cs:323-357` `[源码]` —— **完整原文，注意第一行**

```csharp
public class AccountLoginSyncResponse : ResponsePacket
{
    public override Protocol Protocol { get => Protocol.Account_LoginSync; }
    public ResponsePacket? Responses { get; set; }        // ← 单个可空引用，抽象类，且从未赋值
    public CafeGetInfoResponse? CafeGetInfoResponse { get; set; }
    public AccountCurrencySyncResponse? AccountCurrencySyncResponse { get; set; }
    public CharacterListResponse? CharacterListResponse { get; set; }
    public EquipmentItemListResponse? EquipmentItemListResponse { get; set; }
    public CharacterGearListResponse? CharacterGearListResponse { get; set; }
    public ItemListResponse? ItemListResponse { get; set; }
    public EchelonListResponse? EchelonListResponse { get; set; }
    public MemoryLobbyListResponse? MemoryLobbyListResponse { get; set; }
    public CampaignListResponse? CampaignListResponse { get; set; }
    public ArenaLoginResponse? ArenaLoginResponse { get; set; }
    public RaidLoginResponse? RaidLoginResponse { get; set; }
    public EliminateRaidLoginResponse? EliminateRaidLoginResponse { get; set; }
    public CraftInfoListResponse? CraftInfoListResponse { get; set; }
    public ClanLoginResponse? ClanLoginResponse { get; set; }
    public MomoTalkOutLineResponse? MomotalkOutlineResponse { get; set; }
    public ScenarioListResponse? ScenarioListResponse { get; set; }
    public ShopGachaRecruitListResponse? ShopGachaRecruitListResponse { get; set; }
    public TimeAttackDungeonLoginResponse? TimeAttackDungeonLoginResponse { get; set; }
    public EventContentPermanentListResponse? EventContentPermanentListResponse { get; set; }
    public AttachmentGetResponse? AttachmentGetResponse { get; set; }
    public BillingPurchaseListByNexonResponse? BillingPurchaseListByNexonResponse { get; set; }
    public AttachmentEmblemListResponse? AttachmentEmblemListResponse { get; set; }
    public ContentSweepMultiSweepPresetListResponse? ContentSweepMultiSweepPresetListResponse { get; set; }
    public StickerLoginResponse? StickerListResponse { get; set; }
    public MultiFloorRaidSyncResponse? MultiFloorRaidSyncResponse { get; set; }
    public MultiFloorRaidLoginResponse? MultiFloorRaidLoginResponse { get; set; }
    public long FriendCount { get; set; }
    public string? FriendCode { get; set; }
    public List<PickupFirstGetHistoryDB>? PickupFirstGetHistoryDBs { get; set; }
    public List<long>? AccountLevelRewardIds { get; set; }
}
```

### 4.2 `Responses` 到底是什么形状？—— 三源交叉

| 源 | 结论 | 可信度 |
|---|---|---|
| Shittim 源码 `NetworkProtocol.cs:326` | `ResponsePacket?`（**单个**可空引用） | 直接读代码 |
| Shittim 类型转储 `work/ba/proto/shittim_types.json` → `AccountLoginSyncResponse[0]` | `["Responses", "ResponsePacket?"]` | **自动化转储，独立于源码文本**（Il2CppDumper 直读 metadata） |
| 我们自己的 `dto_schema_full.json` | `{"name":"Responses","type":"List<ResponsePacket>","kind":"list","conf":"mid","src":"manual:report65 + metadata(...)"}` | **conf=mid 且 `src` 自认是手工覆盖**，推翻了 metadata 结论 |

⇒ **以 `ResponsePacket?` 为准**。`dto_schema_full.json` 那条是 `report/65` 手工判定的中置信度假设被写进了 schema，并导致 `gen_*.py` 生成 `"Responses": [26 个完整子回包]` —— **与客户端 DTO 类型不符**。

三条硬证据说明它不能是数组、也不该发：

1. `ResponsePacket` 是 **`abstract`**（`Packet.cs:45`）→ 声明为 `ResponsePacket?` 的字段**不可能是裸实例**，只能是某个具体子类实例；Newtonsoft 会按运行时类型序列化，产出**一个对象**。
2. Shittim **全仓库给 `.Responses` 赋值 0 次**（`grep -r '\.Responses' report/_tmp/l1l2/src` → 无命中）。`AccountHandler.LoginSync`（288-643）从头到尾没碰它。
3. 每个具名子字段**自带 `Protocol`**（`override Protocol => Protocol.Cafe_GetInfo` 等），客户端靠它自证身份——根本不需要一个额外容器。

**⇒ 结论：`Responses` 这个键在响应里应当完全不存在。**（`DefaultValueHandling` 下 null 自动省略，等于"不写就对了"。）

我们现在的 `"Responses":[]` / `"Responses":[26 对象]` 有极大概率是**客户端 JSON 解析直接抛异常**，而异常抛出点在登录协程的 `await` 链上，表现为"同步账号信息时发生错误"。**这是本轮最高优先级的一处修正。**

### 4.3 `Responses` 该填什么 → 填 0 个，改用 26 个具名兄弟字段

`AccountHandler.LoginSync`（`AccountHandler.cs:288-643`）**实际赋值的字段**逐条列（源码行号）：

| # | 字段 | 行 | 内容要点 |
|---|---|---|---|
| 1 | `CafeGetInfoResponse` | 314-318 | `CafeDBs`（含 `CafeVisitCharacterDBs`）+ `FurnitureDBs` |
| 2 | `AccountCurrencySyncResponse` | 372-377 | `AccountCurrencyDB` + `ExpiredCurrency = {}`（**官方总是发这个空 map**） |
| 3 | `CharacterListResponse` | 437-443 | `CharacterDBs`+`TSSCharacterDBs`+`WeaponDBs`+`CostumeDBs` |
| 4 | `EquipmentItemListResponse` | 447-450 | `EquipmentDBs` |
| 5 | `CharacterGearListResponse` | 452-455 | `GearDBs` |
| 6 | `EchelonListResponse` | 457-460 | `EchelonDBs` |
| 7 | `MemoryLobbyListResponse` | 462-465 | `MemoryLobbyDBs` |
| 8 | `CampaignListResponse` | 467-472 | `CampaignChapterClearRewardHistoryDBs`+`StageHistoryDBs`+`StrategyObjecthistoryDBs` |
| 9 | `ArenaLoginResponse` | 474-487 | `ArenaPlayerInfoDB`（`PlayerGroupId=1`,`CurrentRank=1`…） |
| 10 | `RaidLoginResponse` | 489-492 | `SeasonType = RaidSeasonType.Open` |
| 11 | `EliminateRaidLoginResponse` | 495-498 | 同上，"官方只带 Protocol + SeasonType" |
| 12 | `CraftInfoListResponse` | 500 | `new()` 空对象 |
| 13 | `ClanLoginResponse` | 502-505 | `AccountClanMemberDB = {AccountId}` |
| 14 | `MomotalkOutlineResponse` | 508-512 | `FavorScheduleRecords`+`MomoTalkOutLineDBs` |
| 15 | `ScenarioListResponse` | 514-518 | `ScenarioHistoryDBs`+`ScenarioGroupHistoryDBs` |
| 16 | `ShopGachaRecruitListResponse` | 520-523 | `ShopFreeRecruitHistoryDBs = []` |
| 17 | `TimeAttackDungeonLoginResponse` | 525-528 | `PreviousRoomDB` |
| 18 | `BillingPurchaseListByNexonResponse` | 531-579 | 8 个必带空表（`CountList`/`OrderList`/`MonthlyProductList`/`BlockedProductDBs`/`GachaTicketItemIdList`/`ProductMonthlyIdInMailList`/`BattlePassIdInMailList`/`DailyRecordIdInMailList`）+ `BattlePassProductList` |
| 19 | `EventContentPermanentListResponse` | 581-584 | `PermanentDBs` |
| 20 | `AttachmentGetResponse` | 586-589 | `AccountAttachmentDB` |
| 21 | `AttachmentEmblemListResponse` | 591-594 | `EmblemDBs` |
| 22 | `ContentSweepMultiSweepPresetListResponse` | 596-599 | `MultiSweepPresetDBs = []` |
| 23 | `StickerListResponse` | 601-604 | `StickerBookDB` |
| 24 | `MultiFloorRaidSyncResponse` | 606-612 | `MultiFloorRaidDBs` + **自定义 `ServerTimeTicks`** |
| 25 | `MultiFloorRaidLoginResponse` | 615 | `new()`（线上就只是 `{"Protocol":49004}`） |
| — | `PickupFirstGetHistoryDBs` | 616 | `[]` |
| — | `AccountLevelRewardIds` | 618 | `List<long>` |
| — | `FriendCount` | 621 | `0` |
| — | `FriendCode` | 623 | 8 位大写字母（`BuildFriendCode`，646-654，SHA256 派生） |
| — | `StaticOpenConditions` | 625 | 55 项 `OpenConditionContent → None`（`BuildOfficialStaticOpenConditions`，160-185，**含 0 值项，顺序固定**） |

**唯一被刻意留 null 的**（`AccountHandler.cs:445`）`[源码]`：

```csharp
// Official Account_LoginSync has NO ItemListResponse child (the client fetches Item_List separately
// right after login), so it stays null here.
```

⇒ `ItemListResponse` **不发**（`null` → 自动省略）。

### 4.4 一个极易踩的坑：子回包必须清 `ServerTimeTicks`

`AccountHandler.cs:627-636` `[源码]`

```csharp
// Official LoginSync children carry only their own payload + Protocol - no per-child
// ServerTimeTicks/SessionKey/notification fields. Zero the tick so the serializer drops it.
foreach (var property in typeof(AccountLoginSyncResponse).GetProperties())
{
    if (typeof(ResponsePacket).IsAssignableFrom(property.PropertyType)
        && property.GetValue(response) is ResponsePacket child
        && !ReferenceEquals(child, response))
    {
        child.ServerTimeTicks = 0;
    }
}
```

原因：`ResponsePacket` 构造函数给 `ServerTimeTicks` 赋了"现在"（`Packet.cs:48`），不清零的话每个子回包都会多带 `ServerTimeTicks`（还可能有 `ServerNotification`），与官方 key 集不符。唯一例外：`MultiFloorRaidSyncResponse` 有意识地保留自定义 tick（`AccountHandler.cs:638-640`）。

### 4.5 `SyncProtocols` 呢？

**服务端完全不读。** `[源码]` 全仓库 `grep SyncProtocols` 只命中 DTO 声明（`NetworkProtocol.cs:319`）。

我们抓到客户端发的是 `"SyncProtocols":[]`（`report/67` §2）。⇒ **空表 + 服务端固定全量返回**是自洽的；不存在"按 SyncProtocols 点名决定填哪些子回包"的逻辑。`report/65` 里那条"Responses 由 SyncProtocols 决定"的假设可以正式废弃。

### 4.6 §4 一句话

> **`Responses` 一个都不要填（键直接不出现）**；26 个子回包按同名兄弟字段填，Shittim 实填 **25** 个（唯一不发的是 `ItemListResponse`），每个子对象带自己的 `Protocol` int、`ServerTimeTicks` 清 0；再加 `PickupFirstGetHistoryDBs:[]`、`AccountLevelRewardIds:[]`、`FriendCount:0`、`FriendCode:"XXXXXXXX"`、`StaticOpenConditions:{55 项}`。`SyncProtocols` 忽略。

---

## §5 给我们 Python 服务端的最小可用实现清单

> 排序 = 性价比。P0 是"决定客户端会不会继续发请求"的，P1 是"决定客户端收包会不会炸"的。

| P | 改什么 | 为什么 | 风险 |
|---|---|---|---|
| **P0-0** | `dto_schema_full.json` 补 `BasePacket` 根（`SessionKey` + `AccountId`），并把 `ResponsePacket.base` 指过去 | 我们 schema 把 `ResponsePacket` 当根、`BasePacket` 缺失 ⇒ 生成器**结构上发不出**这两个键（§2.5） | 低。但要注意这是"改地基"，会影响所有 444 个响应 DTO 的生成结果，需回归一遍 |
| **P0-1** | `Account_Auth`(1002) 响应顶层加 `"SessionKey": {"AccountServerId": <N>, "MxToken": "<36字符GUID>"}` | 客户端首包无 session；Shittim 靠 CheckNexon 签发，国服无此步 ⇒ 只能在此签发（§1.3） | 极低。客户端只是存下来回填，不校验格式 |
| **P0-2** | 同上响应顶层加 `"AccountId": <同一个 N>`（或干脆由 SessionKey 派生自动出现） | 派生属性；显式写死也行，但要保证与 `AccountServerId` 严格相等（§2.4） | 极低。写错值比不写更糟 |
| **P0-3** | 之后所有请求**接受 `SessionKey: null`**，不要因为缺 session 就 4xx/拒包 | 客户端可能仍发 null；Shittim 的真校验 `ValidateRequest` 其实是死代码，业务层只要账号存在（§1.5） | 低。放弃鉴权，本地私服可接受 |
| **P0-4** | `Account_LoginSync`(1019) 响应里**删掉 `"Responses"` 键**（数组和对象都不发） | 客户端 DTO 是 `ResponsePacket?` 单引用；数组 = 解析异常（§4.2） | **低但收益最高**。空 `{}` 也比 `[]` 安全 |
| **P1-1** | 1019 改用**具名兄弟字段**填子回包，先填能跑的最小集：`CafeGetInfoResponse` / `AccountCurrencySyncResponse` / `CharacterListResponse` / `EchelonListResponse` / `ScenarioListResponse` / `MomotalkOutlineResponse` / `CampaignListResponse` / `AttachmentGetResponse` | 客户端登录后各 UI 直接读这些字段，缺了容易 NRE（§4.3） | 中。先小后大，按客户端报错逐个补 |
| **P1-2** | 每个子回包**必须带 `Protocol` int**，并把 `ServerTimeTicks` 置 **0**（`FriendCount`/`FriendCode`/`StaticOpenConditions` 除外） | `override Protocol` 是 DTO 身份；tick 为 0 才被省略，与官方 key 集一致（§4.4） | 低 |
| **P1-3** | 1019 顶层补 `StaticOpenConditions`（55 项 → 0）、`PickupFirstGetHistoryDBs: []`、`AccountLevelRewardIds: []`、`FriendCount: 0`、`FriendCode: "ABCDEFGH"` | 官方必带；`StaticOpenConditions` 决定所有内容锁（§4.3） | 低。45 项以上容易漏，用固定表生成 |
| **P1-4** | **不要**发 `ItemListResponse` | 官方就是不发，客户端另有 `Item_List`（`AccountHandler.cs:445`） | 低 |
| **P2-1** | 未识别协议 / handler 异常 → 回 `{"protocol":"Error","packet":{"Protocol":-1,"ErrorCode":500}}`，不要 200 空包、不要 5xx | 静默丢弃会让客户端 `await WaitForRequest` 挂到超时（§3.5，正好对应 63 秒空窗） | 低。会多弹一条错误，但比挂死好 |
| **P2-2** | 会话失效类错误用 `ErrorCode: 3`（`InvalidSession`），不要用 500 | 3 让客户端干净回标题重登；500 显示 "A request that cannot be processed"（§1.5） | 低 |
| **P2-3** | 请求解析容错 `OSType`（国服 `BasePacket` 多字段，值为 int）；忽略 `Hash`/`ClientUpTime`/`Resendable` | 国服 DTO 与国际服不同；`Hash` 不参与配对（§3.4） | 低 |
| **P2-4** | 响应外层信封保持 `{"protocol":"<枚举名>","packet":"<内层JSON字符串>"}`；`packet` 是**字符串不是对象** | `ServerResponsePacket.Packet` 是 `string`（`Packet.cs:42`）；双序列化（§3.4） | 低。现有实现已能过，别动 |
| **P3-1** | SessionKey 存进程内存 + 可选落盘 `sessions.json`；重启后回灌 | Shittim 明写重启不持久会导致"MxToken 静默失效"（§1.2） | 低。本地开发可先不落盘 |

**不需要做的**（省时间）：

- ❌ 不需要实现 `Queuing_GetTicket`(50000) —— 我们客户端从没请求过它，它也不下发 SessionKey（§1.3 / §6）
- ❌ 不需要实现 `Account_CheckNexon`(1014) / `Account_CheckYostar`(1009)
- ❌ 不需要实现 `GatewaySessionCrypto` 的 RSA 签名链 —— 我们的 AES 层已经过了客户端（`GatewaySessionCrypto` 只管传输加密）
- ❌ 不需要校验 `MxToken` —— 本地私服无此必要

**最小可行 JSON 骨架（1019 响应内层 `packet`）**

> 下面每个子回包的 `Protocol` 数字都已用脚本从 `NetworkProtocol.cs` 的 `override Protocol => Protocol.X` + `ProtocolData.cs` 的枚举值**逐条解析核对**（`report/_tmp/l1l2/probe_proto.py`）。

```json
{
  "Protocol": 1019,
  "ServerTimeTicks": 1763000000,
  "CafeGetInfoResponse": {"Protocol": 20000, "CafeDBs": [], "FurnitureDBs": []},
  "AccountCurrencySyncResponse": {"Protocol": 1003, "AccountCurrencyDB": {}, "ExpiredCurrency": {}},
  "CharacterListResponse": {"Protocol": 2000, "CharacterDBs": [], "TSSCharacterDBs": [], "WeaponDBs": [], "CostumeDBs": []},
  "EchelonListResponse": {"Protocol": 5000, "EchelonDBs": []},
  "ScenarioListResponse": {"Protocol": 19000, "ScenarioHistoryDBs": [], "ScenarioGroupHistoryDBs": []},
  "MomotalkOutlineResponse": {"Protocol": 33000, "FavorScheduleRecords": [], "MomoTalkOutLineDBs": []},
  "CampaignListResponse": {"Protocol": 6000, "CampaignChapterClearRewardHistoryDBs": [], "StageHistoryDBs": [], "StrategyObjecthistoryDBs": []},
  "AttachmentGetResponse": {"Protocol": 46000, "AccountAttachmentDB": {}},
  "PickupFirstGetHistoryDBs": [],
  "AccountLevelRewardIds": [],
  "FriendCount": 0,
  "FriendCode": "ABCDEFGH",
  "StaticOpenConditions": {"Shop": 0, "Gacha": 0, "...": 0}
}
```

**全部 26 个子字段 → 协议号对照表**（`[源码]` 已核对）

| 字段 | Protocol | 字段 | Protocol |
|---|---|---|---|
| `CafeGetInfoResponse` | **20000** `Cafe_Get` | `CraftInfoListResponse` | **21000** `Craft_List` |
| `AccountCurrencySyncResponse` | **1003** `Account_CurrencySync` | `ClanLoginResponse` | **28001** `Clan_Login` |
| `CharacterListResponse` | **2000** `Character_List` | `MomotalkOutlineResponse` | **33000** `MomoTalk_OutLine` |
| `EquipmentItemListResponse` | **3000** `Equipment_List` | `ScenarioListResponse` | **19000** `Scenario_List` |
| `CharacterGearListResponse` | **44000** `CharacterGear_List` | `ShopGachaRecruitListResponse` | **10006** `Shop_GachaRecruitList` |
| `ItemListResponse`（**不发**） | **4000** `Item_List` | `TimeAttackDungeonLoginResponse` | **39006** `TimeAttackDungeon_Login` |
| `EchelonListResponse` | **5000** `Echelon_List` | `EventContentPermanentListResponse` | **30041** `EventContent_PermanentList` |
| `MemoryLobbyListResponse` | **12000** `MemoryLobby_List` | `AttachmentGetResponse` | **46000** `Attachment_Get` |
| `CampaignListResponse` | **6000** `Campaign_List` | `BillingPurchaseListByNexonResponse` | **29005** `Billing_PurchaseListByNexon` |
| `ArenaLoginResponse` | **22001** `Arena_Login` | `AttachmentEmblemListResponse` | **46001** `Attachment_EmblemList` |
| `RaidLoginResponse` | **17018** `Raid_Login` | `ContentSweepMultiSweepPresetListResponse` | **27002** `ContentSweep_MultiSweepPresetList` |
| `EliminateRaidLoginResponse` | **45000** `EliminateRaid_Login` | `StickerListResponse` | **47000** `Sticker_Login` |
| | | `MultiFloorRaidSyncResponse` | **49000** `MultiFloorRaid_Sync` |
| | | `MultiFloorRaidLoginResponse` | **49004** `MultiFloorRaid_Login` |

> 国服差异提醒：`BillingPurchaseListByYostarResponse`（我们 `report/65` 表里的名字）在 Shittim 叫 `BillingPurchaseListByNexonResponse`(29005)。国服客户端字段名/协议号是否也这样，**本轮未验证** → 见 §7。

---

## §6 顺带回答：`Queuing_GetTicket` 在登录流程里的位置（Q12）

**源码层**：`Queuing_GetTicket`(50000) → 回 `EnterTicket`（base64 `"NpSN/NpToken"`）→ 客户端随后拿它调 `Account_CheckNexon`(1014)（`CheckNexon` 第 58 行 `Convert.FromBase64String(request.EnterTicket)` 再 `Split('/')`）→ 那里才签发 SessionKey。

**客户端层**（`report/67` + `report/74`）：我们国服客户端请求过的协议**只有 5 个**：`1001 / 1002 / 1010 / 1019 / 24000`。**没有 50000，也没有 1009/1014。**

⇒ **对我们的客户端：`Queuing_GetTicket` 不是必经步骤，可以完全不实现。** 它不是 LoginSync 的前置门。（`1010 = Account_CallName`，`ProtocolData.cs:36`）

---

## §7 `[源码中未见]` 清单（不猜）

| 想查的东西 | 状态 |
|---|---|
| `HandlerManager` 类本体（`Dispatch` / `IsImplemented` / `GetRequestType`） | **不在本地抓取集**（`Shittim-Server/Core/` 目录列表未抓）。`GatewayController.cs:207-259` 只暴露了它的调用面 |
| `IProtocolHandlerRegistry` 接口定义 | **未抓取** |
| `AddProtocolHandlers()` / `AddHandlers()` 扩展 | **未抓取**（`HandlerExtensions.cs` 在 Services 清单里但未下载） |
| `AccountDBServer` 类 / `ServerId` 自增策略 | **未抓取**；只能从用法推"数据库自增主键" |
| `ValidateRequest` 的调用点 | 本地源码**零命中**；不能 100% 排除在未抓取的中间件里 |
| `PurgeExpiredSessions` 的调用点 | 本地源码**零命中** |
| 官方 `Account_Auth` 响应里 `SessionKey` 是不是"新签发"而非"回显" | 源码只能证"Shittim 回显"；国服行为是**推断** |
| `AccountLoginSyncResponse.Responses` 在官方响应里是否出现、出现时是什么 | **无任何真实 1019 响应抓包**；`work/ba/proto/out/1017_*.json` 全是我们自己生成的模板 |
| `BattlePassMissionProgressDBDict`（国服 `ResponsePacket` 基类上的字段） | 国际服源码无；只在我们的 `dto_schema_full.json` 里出现 |

---

## §8 一句话总结

> **L2**：`SessionKey` 是「服务端账号主键 + 一个 GUID 字符串」，在 `Account_Auth` 响应里下发，客户端在每条请求体顶层原样回填；`AccountId` 是它的派生影子，所以补 `SessionKey` 一处即可让"缺两个键"同时消失。
> **L1**：路由按 `Protocol` 枚举 int 查表，响应配对靠外层信封的 `protocol` 枚举名（不是 SessionKey、不是连接、不是 Hash）；认不出的协议必须回 `Error` 包而不是静默。
> **最该改的一行**：把 1019 响应里的 `"Responses"` 键彻底删掉，改用同名兄弟字段。
