# 75 — L0 传输层：Shittim 对照与改造方案

- 取证对象：`report\_tmp\shittim\raw\*.json`（34 份，JSON 包装的 C# / JSON 源码，base64 解出 28 个有效文件）
- 解包产物：`report\_tmp\L0_transport\src\`（本文所有行号引用都指向这里；解包脚本 `report\_tmp\L0_transport\decode.py`，只写自己的产物，未改动 `report\_tmp\shittim\src\`）
- 上游仓库：`Neoexm/Shittim-Server` @ `main`（每份 JSON 自带 `html_url` / `sha`，可回溯）
- 对照物：`scripts\cn_bridge_v5.py`、`scripts\account_auth_probe_v6.py`（本地副本）、`report\74-63秒空窗期取证.md`
- **本次未连手机、未连服务器、未重启任何服务、未触碰 `libtprt.so`、未改他人产物**

---

## §0 一页结论

| # | 问题 | 结论 | 置信度 |
|---|---|---|---|
| 1 | Shittim 跑在什么上 | ASP.NET Core **.NET 10** + **Kestrel**；一个明文 HTTP 端口（默认 5000 API / 5100 Gateway）+ 可选 443 HTTPS | 源码直证 |
| 2 | `Connection` 头怎么处理 | **项目没有任何显式处理**（`Connection` / `Keep-Alive` / `Limits` 全仓 0 命中）。完全交给 Kestrel 默认：HTTP/1.1 隐式持久连接 | 源码直证 |
| 3 | 超时三件套 | **项目一个都没配**。生效的是 Kestrel 默认：空闲 2 分钟（≈130s）、请求头 30s、整请求超时**不启用**、体积上限 30,000,000 B | 源码直证 + 框架默认 |
| 4 | 一次登录三条请求 | 服务器**完全不管连接**：状态全挂在 `MxToken` 和 `(AES key,iv)` 上，不挂在 TCP 上。复用/新建对它等价 | 源码直证 |
| 5 | 网关路径设计 | **短连接一问一答**。`POST /api/gateway`，multipart 里塞一个 `mx` 文件，回一个完整 JSON body | 源码直证 |
| 6 | **有没有服务端推送** | **没有。一条都没有。** 无 WebSocket / SSE / SignalR / 长轮询 / 挂起 GET | **强（全量 grep 0 命中）** |
| 7 | 客户端是否必须建推送通道 | **不需要。** 客户端停在原地不是"等推送" | 强 |
| 8 | 我们的 20.000s 拆连是谁干的 | **大概率是客户端自己**（BestHTTP/2 `MaxConnectionIdleTime` 出厂默认 20s）；我们这套栈里没有任何 20s 计时器 | 高（非直证，见 §4.0） |
| 9 | 我们该改什么 | 见 §4。**核心是"别在 20s 之前关连接"+"永不 5xx"+"HTTP/1.1 钉死"**，不是加推送通道 | — |

---

## §1 Shittim 传输层实际配置

### §1.1 运行时与监听

| 项 | 值 | 出处 |
|---|---|---|
| 框架 | ASP.NET Core（Kestrel），**.NET 10** | `README.md:3`「written in C# on ASP.NET Core (.NET 10)」 |
| 入口 | `await ConsoleApp.RunAsync(args, Arguments.RunServerAsync)`，仅 5 行 | `Shittim-Server__Program.cs:1-5` |
| Web builder | `WebApplication.CreateBuilder(Environment.GetCommandLineArgs())` | `Shittim-Server__CLI__GameServer.cs:81` |
| Kestrel 配置点 | `builder.WebHost.ConfigureKestrel(options => { ... })` | `GameServer.cs:161` |
| 监听 | ① 443 HTTPS（仅当 `../../certs/selfsigned_cert.pem` + `_key.pem` 存在）② `apiPort` ③ `gatewayPort`（≠apiPort 时） | `GameServer.cs:161-179` |
| 端口来源 | `HostPort` 默认 `"5000"`、`GatewayPort` 默认 `"5100"` | `Shittim-Server__Configuration__ConfigType__ServerConfig.cs:11-12` |
| 绑地址 | `IPAddress.Any`（不是 `127.0.0.1`） | `GameServer.cs:165,176,178` |
| 证书 | `X509Certificate2.CreateFromPem` → `LoadPkcs12`，失败仅打日志不中断 | `GameServer.cs:138-156` |

**注意 `HostAddress` 是假的**：`ServerConfig.HostAddress` 默认 `"127.0.0.1"`（`ServerConfig.cs:10`），且 `Config.ApplyLocalhostAddress()` 每次 Load/Save 都强制改写回 `"127.0.0.1"`（`Shittim-Server__Configuration__Config.cs:113-119`）。它只用于 IRC 配置和 `ServerInfoConfig` 生成，**不影响 Kestrel 绑 `0.0.0.0`**。

### §1.2 `Connection` 头：项目零显式处理

`ConfigureKestrel` 的**全部**内容（`GameServer.cs:161-179`）只有 5 个分支、3 个 `Listen` 调用，一行 `options.Limits.*` 都没有：

```csharp
builder.WebHost.ConfigureKestrel(options =>
{
    if (httpsCert != null)
        options.Listen(System.Net.IPAddress.Any, 443, listenOptions => { listenOptions.UseHttps(httpsCert); });
    else
        Console.WriteLine("HTTPS on port 443 disabled (no certificate)");

    options.Listen(System.Net.IPAddress.Any, apiPort);
    if (gatewayPort != apiPort)
        options.Listen(System.Net.IPAddress.Any, gatewayPort);
});
```

全量 grep（`report\_tmp\L0_transport\src\*.cs|*.json|*.md`，`Select-String -SimpleMatch`）结果：

| 检索词 | 命中 |
|---|---|
| `Limits.` | **0** |
| `KeepAliveTimeout` | **0** |
| `RequestTimeout` | **0** |
| `MaxRequestBodySize` | **0** |
| `MinRequestBodyDataRate` | **0** |
| `"Connection"` / `Connection: close` | **0** |
| `ConnectionClose` / `AddServerHeader` | **0** |
| `UseHttpsRedirection` / `UseHsts` | **0** |
| `UseResponseCompression` | **0** |
| `HttpProtocols` / `Protocols =`（传输层） | **0**（唯一 1 处是 `SessionKeyService.cs:17` 的 `_publicProtocols = new()`，与传输层无关） |

响应侧唯一被显式设置的头是 `Content-Type`：

```csharp
// GatewayController.cs:787-788（错误路径）
Response.ContentType = "application/json; charset=utf-8";
await Response.WriteAsync(json);

// GatewayController.cs:798-799（正常路径）
Response.ContentType = "application/json; charset=utf-8";
await Response.WriteAsync(json);
```

⇒ **`Connection` / `Keep-Alive` / `Content-Length` / `Transfer-Encoding` 一个都没显式写**。客户端看到的一切都是 Kestrel 行为。

**结论：Shittim 的传输层语义 = Kestrel 默认语义。** 这是"框架默认 ≥ 项目显式配置"里最典型的一例——项目只是"没反对"。

### §1.3 超时三件套（连接 / 空闲 / 请求）

先分清两层：

| 层 | 项 | 值 | 性质 |
|---|---|---|---|
| 项目 | TCP/TLS 建连超时 | 源码中未见 | — |
| 项目 | 空闲（keep-alive）超时 | 源码中未见 | — |
| 项目 | 整请求超时 | 源码中未见 | — |
| 框架（Kestrel） | `Limits.KeepAliveTimeout` | **2 分钟**（Kestrel 内部常量 130 秒） | 默认值 |
| 框架 | `Limits.RequestHeadersTimeout` | **30 秒** | 默认值 |
| 框架 | `Limits.RequestTimeout`（整请求） | **默认不启用（null）** | 默认值 |
| 框架 | `Limits.MaxRequestBodySize` | **30,000,000 B**（≈28.6 MB） | 默认值 |
| 框架 | `Limits.MinRequestBodyDataRate` / `MinResponseDataRate` | 240 B/s，grace 5s | 默认值 |
| 框架 | `Limits.MaxConcurrentConnections` | null（无限） | 默认值 |

（Kestrel 默认值出处：<https://learn.microsoft.com/en-us/aspnet/core/fundamentals/servers/kestrel/options?view=aspnetcore-9.0> —— 文档写 "Defaults to 2 minutes"；Kestrel 内部常量是 130 秒，两者一致到"约 2 分钟"这个粒度。）

**唯一和"20 秒"沾边的项目内常量**，注意它**不是**连接超时：

```csharp
// GatewayController.cs:236-242 —— 每账号串行门的等待上限
var accountGate = GetAccountGate(payload.SessionKey?.AccountServerId ?? 0);
if (!await accountGate.WaitAsync(TimeSpan.FromSeconds(20)))
{
    _logger.LogError("Timed out waiting for the per-account dispatch gate on {Protocol}", protocol);
    await CreateProtocolErrorResponse("Server busy", WebAPIErrorCode.ServerFailedToHandleRequest, responseCrypto);
    return;
}
```

**这条极重要**：Shittim 等 20 秒等不到，行为是**回一个完整的错误信封**（HTTP 200 + `ErrorPacket`），**不是断连、不是空回包**。见 §4.3。

另一处 20 分钟量级的是资源下载用 `HttpClient.Timeout = 10 分钟`（`Shittim-Server__Configuration__ConfigResources.cs:14-17`），与本议题无关。

### §1.4 HTTP 版本

- **源码中未见任何 `HttpProtocols` / `Protocols` 设置**（grep 0 命中）⇒ 用 `ListenOptions` 默认值 `Http1AndHttp2`。
- 明文端口（5000 / 5100）没有 TLS，**HTTP/2 需要 TLS 或 prior-knowledge**，默认走不上 ⇒ 实际只有 **HTTP/1.1**。
- 443 端口用了 `UseHttps`，ALPN 会同时 offer `h2` 和 `http/1.1` ⇒ 理论上可协商 HTTP/2。**但项目没有显式钉 HTTP/1.1。**

### §1.5 管道里"没有"的东西（都是显式缺失，不是默认）

`GameServer.cs:228-255` 全部中间件，逐条看：

```csharp
if (app.Environment.IsDevelopment()) { app.UseSwagger(); app.UseSwaggerUI(); }
app.UseAuthorization();                       // :234
app.UseSerilogRequestLogging(...);            // :235-242
app.Use(async (context, next) => { ... });    // :243-249  IAS 日志
app.MapGet("/health", ...);                   // :251
app.MapControllers();                         // :252
app.UseCors("ShittimGM");                     // :253
app.Run();                                    // :255
```

缺失清单（全部影响传输层可观测行为）：

- 无 `UseHttpsRedirection` / `UseHsts` ⇒ 明文 HTTP 端口就是明文，不跳转、不加 HSTS。
- 无 `UseResponseCompression` ⇒ 响应永不带 `Content-Encoding: gzip`（客户端 `Accept-Encoding: gzip` 被忽略）。
- 无 `UseWebSockets` / `UseSignalR` / `MapHub`。
- 无 `UseStaticFiles`（静态资源走 CDN，见 `ServerConfig.CdnBaseUrl`）。

### §1.6 请求 / 响应编码

**请求**：`POST /api/gateway`，**multipart/form-data 里一个名为 `mx` 的文件**：

```csharp
// GatewayController.cs:157-166
[HttpPost("gateway")]
public async Task GatewayRequest()
{
    var formFile = Request.Form.Files.GetFile("mx");
    if (formFile is null)
    {
        Response.StatusCode = 400;
        await Response.WriteAsync("Expecting an mx file");
        return;
    }
```

`mx` 的二进制布局（`GatewayController.cs:360-409`）：`[crc u32][typeConversion i32][keyLen u8][ivLen u8][key][iv][body]`，`body` 先 gzip 再 XOR `0xD9`（`RequestXorKey = { 0xD9 }`，`:107`），并额外尝试 3 种变体（`:462-493`）。

**响应**：**单个** `{"protocol": "...", "packet": "<json 字符串>"}`，或 AES 加密后整包 base64（`GatewayController.cs:791-800`）：

```csharp
string json = JsonConvert.SerializeObject(packet, serverPacketSettings);
if (ShouldUseAes(crypto))
    json = Convert.ToBase64String(HybridCryptor.EncryptGatewayResponse(...));
Response.ContentType = "application/json; charset=utf-8";
await Response.WriteAsync(json);
```

⇒ **一次请求 = 一个完整 body，没有分块语义、没有流式、没有多响应。**

---

## §2 多请求模式与连接绑定

### §2.1 三条请求：服务器完全不关心走几条连接

Shittim 里**没有任何"连接"对象**。全源码 grep `Connection`（除传输无关的注释）0 命中，也没有 `HttpContext.Connection.Id` 被用于会话的地方。

**理由**：所有跨请求状态都挂在**业务凭据**上，不挂在 socket 上：

| 状态 | 载体 | 出处 |
|---|---|---|
| 登录会话 | `ConcurrentDictionary<long, ActiveSession>`，key = `AccountServerId`，值里是 `MxToken`(GUID) | `Shittim-Server__Services__SessionKeyService.cs:14,39` |
| 会话校验 | 比对 `request.SessionKey.MxToken`（忽略大小写） | `SessionKeyService.cs:135-144`；另一处 `GetAuthenticatedUser` `:147-164` |
| 会话持久化 | 写穿到 `Config/sessions.json`，重启不失效 | `SessionKeyService.cs:30-33,60-75` |
| 网关 AES 会话 | `ConcurrentDictionary<string, StoredGatewayAesCrypto>`，key = `SHA256(key‖iv)` 的 hex | `Shittim-Server__Core__GatewaySessionCrypto.cs:22,218-225` |
| AES 会话寿命 | 30 分钟不活跃淘汰；最多 32 条；落盘 `gateway_aes_sessions.json` | `GatewaySessionCrypto.cs:20-21,27,201-216` |

⇒ **结论：Shittim 对"auth / nickname / academy 三条请求"是"每条一个新连接"还是"复用一条连接"完全没有意见，两种都工作。** 它没有会话-连接绑定，因此不存在"换连接就掉会话"的问题（我们的 bridge 如果做了这层绑定，那是自找麻烦）。

### §2.2 有"串行化"，但那是按账号、不是按连接

```csharp
// GatewayController.cs:109-112
private static readonly ConcurrentDictionary<long, SemaphoreSlim> _accountGates = new();
private static SemaphoreSlim GetAccountGate(long accountServerId)
    => _accountGates.GetOrAdd(accountServerId, _ => new SemaphoreSlim(1, 1));
```

设计意图在注释里写死了（`GatewayController.cs:235`）：

> The client fires bursts of claims concurrently, e.g. several Mission_Reward at once, and parallel write transactions on one SQLite file can stall past the client's socket timeout; an unanswered request soft-locks the game, so dispatch is serialized per account.

**关键判读**：这条注释本身就是 Shittim 作者踩过同一个坑的自述——"**一个没有应答的请求会把游戏软锁**"。他的解法是**串行 + 20s 上限 + 到点回错误包**，不是断连。

### §2.3 `/api/gateway` 的形态：短连接，一问一答

| 路由 | 方法 | 行为 | 出处 |
|---|---|---|---|
| `/api/gateway` | **POST** | 唯一业务入口；解析 `mx` → 分发 → 回一个 body | `GatewayController.cs:157-315` |
| `/api/gateway` | GET | `Results.Ok()`，空 200（健康探针） | `GatewayController.cs:154-155` |
| `/api/Queuing/Ping` | GET | `Results.Ok("Pong")`，**text/plain**，不是 JSON | `GatewayController.cs:150-152` |
| `/health` | GET | `{status:"ok",service:"BlueArchiveAPI"}` | `GameServer.cs:251` |
| `/log` | POST | 客端错误上报，读 body 打日志后 `Results.Ok()` | `ServerInfoController.cs:47-67` |
| `/com.nexon.bluearchive*/server_config/{*filename}` | GET | 下发给客户端的 `ConnectionGroupsJson`（网关地址表） | `ServerInfoController.cs:19-45` |

**不是**长轮询、**不是** WebSocket、**不是** SSE。整个响应在 handler 返回前就已完整生成（`:278 await CreateProtocolResponse(...)`）。

### §2.4 与国服客户端的形态差异（重要，别照搬路由）

Shittim 服务的是 Steam/国际版客户端：**所有业务都 POST 到同一个 `/api/gateway`**，用 body 里的 `Protocol` 字段区分。
我们取的国服客户端（`report\74`）用的是**按动作分路径**：`/api/account/auth`、`/api/account/nickname`、`/api/academy/getinfo`。

⇒ **§4 只能照搬"传输层语义"（头、超时、关闭时机、状态码），不能照搬"路由形态"。** `report\44 §0` 已经写过这一点（bridge 把国服请求转发到 Shittim 必然 404）。

---

## §3 有没有服务端推送机制

> ## **结论：没有。Shittim 里一条服务端主动推送通道都不存在。**
> ### **客户端也不需要建立任何推送通道才能继续。**
>
> 具体：**无 WebSocket、无 SSE、无 SignalR、无长轮询、无挂起 GET。** (全量 grep 0 命中 + 管道结构不可能 + 三个 action 全一次性返回)

证据链（三道，互相独立）：

**① 全量 grep，0 命中。**（范围：`report\_tmp\L0_transport\src\` 下 28 个解码文件，`*.cs` + `*.json` + `*.md`）

| 检索词 | 命中 |
|---|---|
| `WebSocket` | **0** |
| `SignalR` | **0** |
| `text/event-stream` | **0** |
| `EventSource` / `ServerSentEvents` | **0** |
| `IHttpResponseBodyFeature` | **0** |
| `HttpResponse.Body` | **0** |
| `FlushAsync` | **0** |

**② 管道结构上不可能。** 没有任何 `UseWebSockets()` / `MapHub` / `IAsyncEnumerable` 返回（`GameServer.cs:228-255` 全文见 §1.5）。没有 `FlushAsync` 意味着连"写一半挂住"都做不到——`Response.WriteAsync` 之后方法就 return 了。

**③ 三个 action 全是一次性返回。** `Ping()` → `Results.Ok("Pong")`（`:152`）；`GatewayHealthCheck()` → `Results.Ok()`（`:155`）；`GatewayRequest()` → 走到 `CreateProtocolResponse` 就结束（`:278`）。没有任何一个继续持有 `HttpContext`。

### §3.1 唯一像"推送"的东西：**客户端轮询** `Queuing_ProcessWaitingQueue`

```csharp
// QueuingHandler.cs:99-114
[ProtocolHandler(Protocol.Queuing_ProcessWaitingQueue)]
public Task<QueuingProcessWaitingQueueResponse> ProcessWaitingQueue(...)
{
    response.WaitingTicket = request.WaitingTicket;
    // the steam build asks for its enter ticket here instead of through Queuing_GetTicket, and only the first call carries
    // the nexon credentials - a retry after being queued sends the waiting ticket alone. an empty EnterTicket is what holds
    // the client on the queue popup, so mint one from NpSN/NpToken the moment they arrive.
    response.EnterTicket = request.NpSN != 0
        ? Convert.ToBase64String(Encoding.UTF8.GetBytes($"{request.NpSN}/{request.NpToken}"))
        : string.IsNullOrEmpty(request.AuthTicket) ? request.WaitingTicket : request.AuthTicket;
    ...
}
```

判读：

- 方向是**客户端反复问**，不是服务端推。
- 但注释 `:106` 揭示了一个**真实的卡死机制**：`EnterTicket` 回空串，客户端就会**停在排队弹窗上不动**。这不是传输层问题，而是"服务端回了一个语义上的'等一下'"。
- **如果我们的某条响应用了类似的"空/占位"语义（例如 academy 走的 `generic-envelope` 兜底），客户端会静默停住而不是报错。** 这一条值得进 §4 的排查清单（但我们已知 on-wire 字节是对的、客户端也把响应消费完了，见 §4.0 推论）。

### §3.2 唯一的"通道"：`IrcServerConfig`（公会聊天），与登录主链无关

```csharp
// NetworkProtocol.cs:590-596
public class IrcServerConfig
{
    public string? HostAddress { get; set; }
    public int Port { get; set; }
    public string? Password { get; set; }
    public bool IsValid { get; }
}
```

只在 **3 个公会相关响应**里出现：`ClanLobbyResponse`（`NetworkProtocol.cs:1916`）、`ClanJoinResponse`（`:2001`）、`ClanAutoJoinResponse`（`:2014`），且都是 **`IrcServerConfig?` 可空**——不填就不下发。

服务端自己侧：`builder.Services.AddIrcService()`（`GameServer.cs:95`）、`using Shittim.Services.IrcClient`（`:9`）、`IrcConfig{ IrcAddress="127.0.0.1", IrcPort=6667, IrcPassword="mx123" }`（`ServerConfig.cs:64-69`）。`Services/IrcClient/` 目录在 dump 的目录清单里存在，但**实现文件未包含在本次源码快照中** ⇒ 具体协议细节：**源码中未见**。

判读：这是"服务端把 IRC 服务器地址告诉客户端、客户端自己去连"的**聊天**通道，进入公会界面才用，**登录链完全不经过它**。而且 `Config.ApplyLocalhostAddress()` 会把 `IrcAddress` 强制成 `127.0.0.1`（`Config.cs:118`），单机私服下客户端根本连不上——Shittim 也没打算让它连上。

### §3.3 对"取证发现客户端在第 4 条请求之前就停住了"的直接含义

**排除"缺推送通道"这个假设。** Shittim 在完全没有推送的情况下能把客户端带进大厅并正常游玩（`README.md:3-20` 列了一整串已实现玩法）。所以：

> 客户端停在第 3 个响应之后，**不是因为我们少了一条推送通道**。任何"补一条长连接/SSE/WS 就能过"的方案，在 Shittim 这份实现面前都没有依据。

---

## §4 给 Python 服务端的改造清单

### §4.0 先纠一条前提：20.000s 大概率不是我们的

这一节先于改造，因为**改造方向完全取决于这个归因**。

**证据 1（正面）：客户端的出厂默认值就正好是 20 秒和 60 秒。**
客户端 UA 恒为 `BestHTTP/2 v2.4.0`（`report\74 §2.1` 原始 headers）。BestHTTP/2 官方文档 GlobalSettings 页明写：

| 参数 | 默认值 | 原文 |
|---|---|---|
| `HTTPManager.MaxConnectionIdleTime` | **20 秒** | "the idle time BestHTTP should wait before it destroys the connection after it's finished the last request" |
| `HTTPManager.RequestTimeout` | **60 秒** | "the default Timeout value" |
| `HTTPManager.ConnectTimeout` | 20 秒 | — |
| `HTTPManager.KeepAliveDefaultValue` | `true` | — |

（<https://besthttp-documentation.readthedocs.io/en/dev/7.GlobalTopics/GlobalSettings/>）

**证据 2（反向）：我们这套栈里没有任何 20s 计时器。**

| 环节 | 空闲关闭参数 | 值 | 出处 |
|---|---|---|---|
| nginx stream（client↔443） | `proxy_timeout` | 600s | `report\74 §2.4` 引 `ba_sni.conf:34` |
| nginx http（443→8443） | `keepalive_timeout` | 60s | `report\74 §2.4` 引 `nginx.conf:39` |
| bridge（`account_auth_probe` / `cn_bridge_v5`） | 无 socket timeout | `ThreadingTCPServer` 未设 `timeout` | `account_auth_probe_v6.py:428-429`；`cn_bridge_v5.py:291-294` |
| bridge 关闭路径 | **根本不存在** | `_send()` 只 `write`，`protocol_version='HTTP/1.1'`，不发 `Connection: close`，之后回到 `handle_one_request` 阻塞读 | `account_auth_probe_v6.py:252-260`；`cn_bridge_v5.py:187-195,177-178` |

⚠ `patch_L0.py` 加的 `Connection: close`，其配套脚本 `scripts\244_L0_deploy.sh` 的时间戳是 **06:18**，**晚于 06:06–06:07 的取证窗口**，不能用来解释取证数据。（是否已真正部署到线上，本次未核实、也不猜测。）

**证据 3：计时口径完全吻合。** BestHTTP 的 20s 从"最后一个请求收尾"起算；观测值是「06:06:41.002 最后响应 → 06:07:01.000 拆除 = 19.998s」，5/5 次样本全一致（`report\74 §2.4`）。server 侧 idle timer 也是这个口径，**这一条不能区分**，但和证据 1+2 合起来指向客户端。

**⇒ 修正建议**：`report\74 §2.4` 末尾"20.000s 最可能来自 bridge 后端 127.0.0.1:9098 或客户端自身"这句，应把权重**压倒性移到客户端**；§4「能确定」第 6 条"20 秒 keep-alive 拆连是我方一个稳定、可复现的既有行为"**建议改写**。

**⇒ 连带推翻"死 socket"假设**：第 4 条请求若在 ~06:06:44 创建，那时连接**还活着**（06:07:01 才拆），所以"写进已被拆掉的死管道"在时间上不成立。

**一个较强的正面推论**：客户端那个 20s 闲置计时器能**正常起跳**，说明第 3 个响应在客户端侧被**完整消费完**（`Content-Length` 与实际字节一致、无残留半包）。否则连接会被标记为"忙/脏"而不会被当成 idle 回收。
⇒ **不要再往 `Content-Length` / chunked / gzip 方向查了**（`report\41` 也已实测 chunked/gzip 均正常）。第 4 条请求"创建了但一个字节都没写出去"，更像是**客户端自己的请求准入/回调链把请求挡在池外**，等满 `RequestTimeout=60s` 才炸——这块属于上层（`report\48`）。

> 上述"客户端"结论是**高置信推断，不是直证**。唯一能定死 FIN 方向的办法（本次不允许）：在服务器上 `ss -tanp 'dport = :443'` 观察一个闲置会话 20s 后是否从 `ESTAB` 变 `FIN-WAIT-1/2`（我方先关）还是 `CLOSE-WAIT`（对方先关），或对着同一条流抓 `tcpdump` 看 FIN 方向。**在拿到这个之前，改造要按"两边都不能先关"的保守策略做（§4.1）。**

### §4.1 P0-1：全链路空闲关闭时间必须 **严格 > 20s**，推荐 130s

**改什么**

| 位置 | 现在 | 改成 | 理由 |
|---|---|---|---|
| nginx http server（`nginx.conf`） | `keepalive_timeout 60` | `keepalive_timeout 130s;` | 60s 已经 >20s，**不是必须改**；改成 130s 是为了对齐 Kestrel，把"谁是最后一个关的"这件事彻底从我们手里拿出去 |
| nginx→bridge 的 upstream 块 | 若有 `keepalive N` + `keepalive_timeout` | `keepalive 32; keepalive_timeout 130s;` | upstream 空闲池默认 60s，同样 >20s，但同样建议抬到 130s |
| nginx stream（`ba_sni.conf`） | `proxy_timeout 600s` | 不动 | 600s 已经远大于 20s |
| bridge | 无 socket timeout | **保持无 timeout** | 加任何 `settimeout(20)` 都会把巧合变成自杀 |
| 反向代理方向头 | — | `proxy_http_version 1.1;` + `proxy_set_header Connection "";` | 否则 nginx 对上游用 HTTP/1.0 或主动 `Connection: close`，keep-alive 直接失效 |

**为什么**：Shittim 的实际策略是 `KeepAliveTimeout = 130s`，而客户端是 20s。130 ≫ 20 ⇒ **永远是客户端先关**，服务端永远不可能持有一条客户端已经认为死掉的连接。我们现在的处境是 **20 vs 20 的平局**：谁的计时器先跳纯属运气。把任何一个常量挪出平局区，就永久消灭了这类竞态。

**风险**：极低。副作用只是"多占用几条 fd 十几秒"。若担心 fd 泄漏，用 `MaxConcurrentConnections`-等价手段（`worker_connections`）兜底，**不要**用缩短 idle 超时兜底。

**验证**：改完观察 `tcp-access.log`，`session_time` 应仍在 ~20s 附近（客户端拆的），**而不是**出现 <20s 的会话；`bytes_sent` 收支仍应闭合。

### §4.2 P0-2：响应头模板钉死（含可直接用的代码）

**改什么**：所有响应统一走一个出口，固定发这 4 个头，**不多不少**：

```
HTTP/1.1 200 OK
Content-Type: application/json; charset=utf-8
Content-Length: <精确字节数>
Cache-Control: no-transform
Date: <自动>
Server: <自动>
```

- **`Connection` 头：不发。** 与 Shittim 一致（源码 0 命中），HTTP/1.1 隐式持久。
  - 例外：只有在 §4.4 决定"主动关"时才发 `Connection: close`。
- **`Keep-Alive: timeout=...` 头：不发。** Shittim 不发；BestHTTP 对它的支持无依据。发了多一个变量。
- **`Content-Length` 必须精确**，绝不 chunked。
- **不发 `Content-Encoding`**（即使客户端 `Accept-Encoding: gzip`）——Shittim 也没有压缩中间件（§1.5）。
- **`Cache-Control: no-transform`**：给 CDN/中间盒（我们前面有 EdgeOne 的同构物）一个"别改写 body"的提示。现网 `patch_L0` 里已经用到了这个思路，保留。

**代码（替换 `account_auth_probe*.py` 的 `_send`）**：

```python
def _send(self, code, body: bytes, ctype='application/json; charset=utf-8'):
    """L0 传输层唯一出口。固定 4 个头，不 chunked，不发 Connection。"""
    try:
        self.send_response(code)                     # 自动加 Server / Date
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))   # ← 必须是 len(body)，不是估算
        self.send_header('Cache-Control', 'no-transform')
        self.end_headers()
        self.wfile.write(body)
        # 不发 Connection: close ⇒ close_connection 保持 False ⇒ 连接留作 keep-alive
    except Exception:
        pass
```

**为什么**：客户端是 BestHTTP 的 HTTP/1.1 解析器。少一个 `Content-Length` 会退化成 chunked/或读到 EOF（连接不关就永久挂住）；多发一个字节会污染下一条响应。这 4 个头是我们能控制的全部。

**风险**：极低。`report\41` 已实测客户端对 chunked/gzip 都不敏感，所以这步**不是解药**，只是"别引入新变量"。

### §4.3 P0-3：网关层错误**一律 HTTP 200**，错误放在信封里

**改什么**：`_bridge()` 里所有失败分支，从 `500` / `502` 改成 **200 + 完整的 `{"protocol":"Error","packet":...}` 信封**（或与国服客户端约定的等价错误信封）。

**为什么**：Shittim 的错误路径**从不改状态码**：

```csharp
// GatewayController.cs:773-789 —— 注意：全函数没有一行 Response.StatusCode = ...
private async Task CreateProtocolErrorResponse(string reason, WebAPIErrorCode errorCode, GatewayCryptoContext crypto)
{
    var errorPacket = new ErrorPacket { Reason = reason, ErrorCode = errorCode };
    var res = new ServerResponsePacket { Protocol = Protocol.Error.ToString(), Packet = JsonConvert.SerializeObject(errorPacket, jsonSettings) };
    ...
    Response.ContentType = "application/json; charset=utf-8";
    await Response.WriteAsync(json);          // ← 状态码保持默认 200
}
```

调用点覆盖了全部分支：`WebAPIException`（`:280-286`）、`UnauthorizedAccessException`（`:287-295`，显式选 `InvalidSession` 而不是泛错）、兜底 `Exception`（`:296-303`）、`Server busy`（`:240`）、协议未实现（`:228`）。

注释 `:289` 还说明了**为什么**必须这么分：

> A dead or mismatched session must NOT surface as the generic 500 ("A request that cannot be processed"); InvalidSession triggers the client's clean return-to-title + relogin flow.

**风险**：低。但要注意：如果客户端目前依赖我们的 500 来触发某些分支，改成 200 会**改变行为** ⇒ 改之前先确认客户端对 500 路径的处理（`report\50` 有相关分析）。**这是本清单里唯一"可能改变现有行为"的一项，建议单独一步、可回滚。**

**我们现在的实况**（必须修）：

| 文件:行 | 现状 |
|---|---|
| `account_auth_probe_v6.py:281` | 未捕获异常 → `500` |
| `account_auth_probe_v6.py:370,393,399` | CheckNexon 失败 → `500` |
| `account_auth_probe_v6.py:381,407` | Auth 响应不可解析 → `502` |
| `cn_bridge_v5.py:252,261` / `:269` | 同上（`500` / `502`） |

这 6 处都该变成 **200 + Error 信封**。

### §4.4 P0-4：不要主动关连接；**如果必须关，必须用头告诉客户端**

这是对 `patch_L0.py` 的明确评估。

| 方案 | 做法 | 优点 | 缺点/风险 | 结论 |
|---|---|---|---|---|
| **A. 长 keep-alive（对齐 Shittim）** | 不关，idle 130s | 与参考实现一致；3 个请求共用 1 条连接（省 2 次 TLS）；**不产生任何"关/复用的时间竞态"** | 需要保证全链路 >20s | **推荐（默认）** |
| **B. 每条响应 `Connection: close`（`patch_L0.py` 现状）** | 响应头 `Connection: close` + `close_connection=True` | **确定性最强**：连接在响应体解析完就被客户端从池里删掉，物理上不可能复用 | ① 每次请求重启 TLS（3 次握手，延迟 +RTT×2）；② **偏离 Shittim**，多一个未知变量；③ 对高延迟链路放大首包时间；④ 如果 someday 换成真并发请求，连接数暴涨 | 仅作 A 的**降级备选** |

**关键判断**：B 是**针对"我方 20s 提前拆连"这个前提的补丁**。而 §4.0 认为这个前提大概率不成立（20s 是客户端自己的）。**前提不成立时，B 的收益归零，成本（TLS 次数 ×3、偏离参考实现）照付。**

**建议路线**：
1. 先落 §4.1（把 idle 预算拉出 20s 平局区），**保留 keep-alive**。
2. 若改完仍复现 → 再上 B（`Connection: close`），因为它此时确实能排除"复用"这一整类原因，是很好的**二分判据**。
3. B 的回滚极其简单（删两行），无状态残留。

**注意 B 的实测方法**：`report\74 §2.4` 已建立"一次登录 = 1 条 TCP 会话承载 3 个请求"的基线（`bytes_received=4327`）。上了 B 之后，`tcp-access.log` 里应该看到 **3 条独立的 gsqc 会话**，每条只承载 1 个请求。**这就是 B 生效的判据**；如果仍是 1 条，说明 `Connection: close` 没真正生效（或被 nginx 吃掉了）。

### §4.5 P1-1：给 bridge 加"源端口"取证字段（一行，立刻能做）

**改什么**：`_handle()` 的 `rec` 里加 `'cport': self.client_address[1]`。

```python
rec = {'t': ..., 'from': self.client_address[0], 'cport': self.client_address[1], ...}
```

**为什么**：这一列直接回答"三条请求是一条连接还是三条"。

- 3 个请求 = **同一个 `cport`** ⇒ keep-alive 生效（当前应如此）。
- 3 个请求 = **3 个不同 `cport`** ⇒ 有东西在每次响应后关连接（`Connection: close` 生效 / nginx 在关）。
- 第 4 个请求**完全不出现** ⇒ 客户端根本没写（与 §4.0 推断一致）。

**风险**：零（只加日志字段）。日志体积 +12 字节/行。

### §4.6 P1-2：HTTP/1.1 钉死

**改什么**：
- nginx 侧：给 API 的 `server` 块**只** `listen 443 ssl;`（不加 `http2`/`quic`），并 `proxy_http_version 1.1;`。
- 若将来直连 Kestrel 等价物：只开 HTTP/1.1。

**为什么**：Shittim **没有**钉（§1.4，grep `HttpProtocols` = 0），在 443 上会 ALPN offer `h2`。但证据侧国服客户端是纯 HTTP/1.1：`report\74 §2.2` 三行 nginx 日志全是 `"POST /api/account/auth HTTP/1.1"`（`$server_protocol` 反映真实请求行，若是 h2 会记 `HTTP/2.0`）。**既然客户端是 1.1，服务端 offer h2 只会增加一个不该存在的分支。** 这一条是"比 Shittim 更严"，属于**明知偏离但有意为之**，理由是无收益的复杂度应当消除。

**风险**：低。唯一损失是 h2 的多路复用（我们一次登录只有 3 个串行请求，用不上）。

### §4.7 P2-1：复刻"每账号串行 + 到点回错误包"

**改什么**：如果 bridge 后续会做真实业务（现在只翻译了 3 个协议），要一并抄 `accountGate` 的语义：**按 `AccountServerId` 串行**，等不到就回 `Server busy` 错误包（**不是断连、不是空回**）。

**为什么**：`GatewayController.cs:235` 的注释是 Shittim 作者用血换来的："an unanswered request soft-locks the game"——**没有应答的请求会把游戏软锁**。这与我们看到的 60s 静默 → 弹窗是同一类故障。**宁可早回一个明确错误，也不要让客户端等。**

**风险**：中。串行化会提高延迟，若响应本身慢（>几百 ms）会叠加。当前 3 条请求 `ms = 104 / 3 / 2`（`report\74 §2.1`），完全安全。

### §4.8 P2-2：推送通道 —— **不需要**，最小实现 = 空

**改什么**：什么都不做。

**为什么**：§3 已证 Shittim 无任何推送通道且客户端跑得通。加一条通道 = 加一条会超时、会被中间盒切断、会引入新失败模式的连接，而**没有任何证据表明客户端在等它**。

**如果**（仅当后续拿到客户端侧硬证据表明它在等某条连接）：最小实现就是一个**永不主动结束的 `GET`**，但要清楚代价——它会被客户端的 20s idle 计时器/60s RequestTimeout 杀掉，需要应用层心跳，这已经是一个新子系统。**不要在没有任何证据时开这个口子。**

### §4.9 改造矩阵总表

| 优先级 | 改什么 | 为什么 | 风险 | 回滚 |
|---|---|---|---|---|
| **P0-1** | 全链路 idle 关闭 >20s（推荐 130s）；bridge 不加 socket timeout | 消灭 20 vs 20 平局，让"最后关"永远是客户端 | 极低（多占 fd） | 改回原值 |
| **P0-2** | 响应固定 `Content-Type`/`Content-Length`/`Cache-Control`，不发 `Connection`/`Keep-Alive`，不 chunked，不 gzip | 客户端是 HTTP/1.1 解析器，头部要可预测 | 极低 | 删头 |
| **P0-3** | 错误一律 200 + Error 信封（含 CheckNexon/Auth 的 500/502） | 对齐 `CreateProtocolErrorResponse`；防 60s 静默 | 中（可能改变客户端分支） | 改回 500/502 |
| **P0-4** | 不主动关连接；暂缓 `Connection: close`，留作降级备选 | §4.0 已推翻"我方 20s"前提 | 低 | `patch_L0.py` 反向 |
| **P1-1** | 日志加 `cport` | 一行判据回答"复用没复用" | 零 | 删字段 |
| **P1-2** | 钉 HTTP/1.1（nginx 不开 h2、`proxy_http_version 1.1`） | 客户端是 1.1，消除无用分支 | 极低 | 加回 http2 |
| **P2-1** | 每账号串行 + 到点上限 + 明确错误包 | 抄 `:235` 注释里的教训 | 中（延迟） | 去锁 |
| **P2-2** | 不实现推送通道 | §3 已证不存在 | 零 | — |

---

## §5 不确定性 / 未验证项（不许当成结论用）

1. **20s 拆连的 FIN 方向未直证。** 依据是"客户端默认 20s + 我方无 20s 计时器"的排除法。唯一硬办法是服务器侧 `ss`/`tcpdump`（本次禁止）。已按"两边都不先关"的保守策略写进 §4.1，所以**即使归因错了，P0-1 也仍然是对的**。
2. **Shittim 的响应到底是 `Content-Length` 还是 `Transfer-Encoding: chunked`：源码中未见显式设置。** `Response.WriteAsync(json)`（`GatewayController.cs:788,799`）只走 body 流，Kestrel 在未知长度时对 HTTP/1.1 用 chunked——但这是**框架推演，不是观测**。要确认只需对本地 Shittim 打一发 `curl -D-`（shittim 就在 `127.0.0.1:5000`，但本次禁止连服务器，故未做）。**这条不影响 §4.2 的建议**（我们一律用 Content-Length，不会被框架行为牵着走）。
3. **`IrcClient` 的实现未包含在本次 dump 里**，`Services/IrcClient/` 目录存在、`AddIrcService()` 有注册（`GameServer.cs:95`），但协议细节：**源码中未见**。
4. **`Shittim-Server__config.json` 不是一个文件**，它是 `DIR__Shittim-Server__config.json` 这个**目录列表**（含 `GatewayPrivateKey.pem` / `GatewayPublicKey.pem` / `ba_version_cache.json`）。任务描述里的文件名有误。
5. **appsettings 只有一份**（`Shittim-Server__appsettings.json`，18 行，无 Kestrel 段）。`GameServer.cs:135-136` 反而把 `Kestrel:Certificates:Default:Path/KeyPath` 显式置 `null`，说明作者**知道** Kestrel 配置节存在但选择不用配置节。仓库里是否有 `appsettings.Development.json`：**本次 dump 未包含，源码中未见**。
6. **`444`/`Kestrel` 在 .NET 10 上的默认值是否与文档一致**：文档对 `KeepAliveTimeout` 只写"2 minutes"，Kestrel 内部常量为 130s。两者差异（120 vs 130）不影响本报告任何结论。

---

## §6 复现命令

```powershell
# 1) 解包（只写自己的产物）
& "C:\Users\su\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe" `
  "report\_tmp\L0_transport\decode.py"

# 2) 传输层关键词全量计数（本文 §1.2 / §3 的 0 命中表可复现）
$src = "report\_tmp\L0_transport\src"
foreach($t in @('WebSocket','SignalR','text/event-stream','IHttpResponseBodyFeature','FlushAsync',
                'Limits.','KeepAliveTimeout','RequestTimeout','MaxRequestBodySize','"Connection"',
                'HttpProtocols','UseHttpsRedirection','UseResponseCompression','AddServerHeader')){
  $n = (Select-String -Path "$src\*.cs","$src\*.json","$src\*.md" -SimpleMatch -Pattern $t | Measure-Object).Count
  "{0,-28} {1}" -f $t, $n
}

# 3) Kestrel 配置点全文（应只有 Listen，无 Limits）
Select-String -Path "$src\Shittim-Server__CLI__GameServer.cs" -Pattern "ConfigureKestrel" -Context 0,20
```

---

## §7 合规声明

- 全程**只读本地文件**；新增产物仅 `report\75-L0传输层-Shittim对照与改造方案.md` 与 `report\_tmp\L0_transport\{decode.py, src\*}`。
- **未连接手机、未连接服务器**（无 ssh / adb / curl 到远端），未执行任何 `scripts\243_*` / `244_*` / `patch_L0.py`。
- **未修改** `report\_tmp\shittim\src\`（他人产物）、`scripts\` 下任何文件、未触碰 `libtprt.so`。
- 引用的外部资料：BestHTTP/2 官方文档 GlobalSettings 页、Microsoft Learn Kestrel options 页（URL 见正文）。
