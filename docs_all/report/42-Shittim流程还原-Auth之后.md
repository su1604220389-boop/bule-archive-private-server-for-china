# 42 — Shittim 流程还原：`Account_Auth` 之后客户端该做什么

> 时间：2026-11-14 03:45 前后
> 依据：本地源码快照 `report\_tmp\shittim\src\`（只读，未改一字节）+ 本地桥接脚本 `scripts\*.py`（只读）
> **未连接手机、未连接服务器、未触碰运行中的服务。** 一切结论来自本地文件。

---

## 查档声明（按硬规矩先交代）

| 文件 | 用途 | 结论 |
|---|---|---|
| `report\28-Shittim网关协议源码核对.md` | 网关路由 / 信封 / 认证链 | **已读，作为基线。** 本报告在其基础上补 §1 的完整分派路径与 §3 的"无推送"证据 |
| `report\29-进度-网关未调用与判据纪律.md` | **判据纪律五条** | **已读。** 见本报告 §0.3，第五条"先问这个观测在什么时机写入、覆盖什么状态"直接决定了本报告 §5 的观测有效性前置分支 |
| `report\36-Account_Auth响应字段清单.md` | 1002 响应 24 键 | **已读。** 其中 §0-1「回 200 不弹窗 ⇒ 认为成功」被本报告 §0.2 推翻（判据问题） |
| `report\27-SDK登录协议调研.md` | SDK 面与网关面分层 | 已读 §1–§2.5 |
| `report\30-网关RSA公钥定位与替换.md` | 国服 RSA-2048 / 451 B | 已读，作为 §4 依据 |
| `report\34` / `report\35` | 国服 `packet` 信封 | 已读，作为 §4 依据 |
| `report\04-服务端就绪度.md` | 进大厅时序表 | 已读 §4.1，其中"13 队列票据 → 返回 gateway URL"一条**与 Shittim 的 DTO 不符**，见 §4.5 |
| `report\_tmp\cn_proto\headless-bluearchive__SDK__*` | 第三方协议实现 | 已读 `docs\protocols.md` 头部 + `core\client.py` 全文 |

---

## 0. 一页结论（先看这个）

### 0.1 直接回答核心问题

> **「Shittim 的流程里，客户端在 `Account_Auth` 成功之后，下一个动作是什么？」**

**在 Shittim 的源码里，这个问题没有答案——因为它根本不存在"下一个动作"这个概念。**

`GatewayController` 是**无状态分发表**：一次 HTTP 请求进 → 解出一个 JSON → 按 `Protocol` 字段反射 `Dispatch` → 把 handler 返回的对象序列化 → 写回。没有登录状态机、没有"登录后应发 X"的断言、没有服务端主动触发器、没有会话进度表。

`[源码实测]` 三条硬证据：

1. `GatewayController.cs:157-315` `GatewayRequest()` 从头到尾**只处理"当前这一个包"**，`finally` 里只打一行日志（`:304-313`），提交响应后就返回。没有任何"投递下一包"的代码。
2. `ProtocolHandlerRegistry.cs:124-181` `InvokeHandler()` 的流程是 `GetHandler → GetResponseType → new response → method.Invoke → return`。**handler 签名里没有"下一步"这个返回通道**（`ProtocolHandlerBase.cs` 全文 9 行，只有构造函数）。
3. 唯一与"顺序"沾边的东西是三个**集合常量**（谁免会话、谁发会话、谁在账号管线之外），见 §2。它们是"可以这么用"的白名单，**不是"必须这么用"的时序**。

⇒ **本次卡点的提问方式需要修正**：不是"我们回的响应体让 Shittim 的下一个期望落空"，而是"**客户端自己没走到下一跳**，而服务端对此完全被动"。

### 0.2 顺手推翻一条既有判据（重要，先说）

`report\36` §0-1 写「响应里没有 `ResultState`……这是正确的，不是缺失 bug」——这条对。但同一份报告的隐含推理「**回 HTTP 200 + 不弹窗 ⇒ 客户端认为成功**」**是坏的**。

`[源码实测]` Shittim 的**成功、业务错误、会话失效，三种情况全部是 HTTP 200**：

```csharp
// GatewayController.cs:791-800  CreateProtocolResponse —— 不设 StatusCode，默认 200
private async Task CreateProtocolResponse(ServerResponsePacket packet, GatewayCryptoContext crypto)
{
    ...
    Response.ContentType = "application/json; charset=utf-8";
    await Response.WriteAsync(json);
}

// GatewayController.cs:773-789  CreateProtocolErrorResponse —— 同样不设 StatusCode
private async Task CreateProtocolErrorResponse(string reason, WebAPIErrorCode errorCode, GatewayCryptoContext crypto)
{
    var errorPacket = new ErrorPacket { Reason = reason, ErrorCode = errorCode };
    var res = new ServerResponsePacket { Protocol = Protocol.Error.ToString(), ... };
    ...
    await Response.WriteAsync(json);      // ← 还是 200
}
```

`HTTP 200` 在整个系统里**零信息量**。HTTP 非 200 只有三种来源：`mx` 缺失的 400（`:160-166`）、Kestrel 层故障、以及请求根本没进控制器。

⇒ **判据纪律第 5 条的同型错误**（"先问这个观测在什么时机写入、覆盖什么状态"）：接下来所有实验**不得以 HTTP 状态码作为成败判据**，只能看 body 里的 `protocol` 字段与 `ErrorCode`。

### 0.3 判据纪律落实情况（对 29 号文五条的逐条映射）

| 29 号纪律 | 本报告如何遵守 |
|---|---|
| ① 只认 pcap，`mark` 不算 | §5 的 D0 分支：只凭 bridge 日志**不能**下"客户端没发请求"的结论 |
| ② `tcp-access.log` 会话结束才落盘 | §5 不用它做否定判据 |
| ③ `tcp-access.log` 记上游恒为 127.0.0.1:8443 | §5 不用 `grep 目标IP` |
| ④ 同 IP 多域名，凭 IP 反推域名必错 | §5 的 D0 要求按 **host** 而非 IP 判断 |
| ⑤ 先问观测的时机与覆盖面 | §5 D0 就是这一条制度化 |

**本报告自己的一条新纪律（建议并入 29 号）：**

> **⑥ 源码快照的"没找到"不等于"不存在"。** `report\_tmp\shittim\src` 只有 24 个文件（`_dl.py:6-22` 的白名单），完整仓库有数百个 handler。本报告凡写"未找到"的，都只声明"**本地快照内没有**"，不外推为上游没有。

---

## 1. `Account_Auth` handler 的完整代码路径

从网关入口到字节写出，逐段配文件 + 函数 + 行号。

### 1.1 入口：路由与 `mx` 文件

`Shittim-Server__Controllers__Api__GatewayController.cs:98-158`

```csharp
[Route("api")]                                    // :101
public class GatewayController : ControllerBase   // :102
...
[HttpGet] [Route("Queuing/Ping")]                 // :150-152  → "Pong"
[HttpGet("gateway")]                              // :154-155  → 200 空 body
[HttpPost("gateway")]                             // :157-158
public async Task GatewayRequest()                // :158
{
    var formFile = Request.Form.Files.GetFile("mx");   // :160
    if (formFile is null) { Response.StatusCode = 400; await Response.WriteAsync("Expecting an mx file"); return; }  // :161-166
```

**注意**：全项目 `[Route]` 只有 `api`、`Queuing/Ping`（三段）、`gateway`（两段），**没有任何 `{path1}/{path2}` 通配模板**，也**没有任何 `account`、`networktime`、`state` 动作**（28 号文 §1.3 已核实，本报告复核一致）。⇒ 国服客户端的 `/api/account/auth` **不是 Shittim 的端点**，必须由我们的桥接先接住（事实也确实如此，`scripts\cn_bridge_v5.py:281-283` 同时接管 GET/POST/PUT）。

### 1.2 解密第一段：`mx` 二进制头

`GatewayController.cs:360-409` `DecodeGatewayPayload(IFormFile)`

```
偏移 0  uint32  crc             reader.ReadUInt32()      :367
偏移 4  int32   typeConversion  reader.ReadInt32()       :368
偏移 8  uint8   keyLength       reader.ReadByte()        :369
偏移 9  uint8   ivLength        reader.ReadByte()        :370
        byte[keyLength] headerKey                          :371
        byte[ivLength]  headerIv                           :372
        byte[...]       rawPayload                         :373
```
长度 < 14 → `WebAPIException("Gateway packet is too short")`（`:364-365`）。

### 1.3 解密第二段：XOR 0xD9 + GZip，三变体试解

`GatewayController.cs:462-493` `DecodeGatewayPayloadBodies(byte[] rawPayload, List<string>)`

`RequestXorKey = { 0xD9 }`（`:107`）。三个变体**全部构造出来、谁先成功用谁**：

| 变体名 | 处理 |
|---|---|
| `xor-length-prefix` | 整段 XOR → 前 4B 当 int32 明文长度 → `gzip(raw[4..])` |
| `clear-length-prefix` | 前 4B 明文当长度 → 剩余 XOR → gzip |
| `xor-no-length` | 整段 XOR → 直接 gzip |

### 1.4 解密第三段：明文 / AES / 历史会话 / RSA

`GatewayController.cs:495-596` `TryBuildGatewayPayload(...)`，按顺序尝试：

1. **`TryReadJson(payload.Payload)` 明文直通**（`:505-528`）。首字符必须是 `{`（`:630-656`）。
   响应加密强度**由包头决定**（`:514-517`）：
   ```csharp
   var responseCrypto = (headerKey.Length > 0 && headerIv.Length == 16 && IsValidAesKeyLength(headerKey.Length))
       ? new GatewayCryptoContext(true, headerKey, headerIv)
       : GatewayCryptoContext.None;
   ```
   ⇒ `keyLen=0` 的请求 ⇒ `UseAes=false` ⇒ 响应明文。我们桥接造 `.mx` 时正好写 `keyLen=0/ivLen=0`（`cn_bridge_v5.py:86`），所以**永远走明文响应分支**。
2. **AES 解密**（`:530-553`）：用包头 `headerKey/headerIv` 解 `rawPayload`。
3. **历史会话密钥扫描**（`:555-578`）：`GatewaySessionCryptoBuilder.GetAesCandidates()`，会话持久化在 `Config/gateway_aes_sessions.json`（`GatewaySessionCrypto.cs:24-27, 315-339`），30 分钟 TTL、最多 32 条（`:20-21`）。
4. **RSA 解密**（`:580-591` → `:663-696` `TryDecryptRsaPayload`），padding 顺序 `OaepSHA1 → Pkcs1 → OaepSHA256 → OaepSHA384 → OaepSHA512`（`:750-757`）。
5. 全失败 → `WebAPIException("Gateway payload could not be decoded. First bytes: ...")`（`:398-408`）。

### 1.5 分派：读协议号 → 特殊分支 → 门禁 → 反射

`GatewayController.cs:174-252`

| 步 | 行 | 动作 |
|---|---|---|
| a | `:180`, `:412-422` | `ReadProtocol(jsonNode)`：顶层 `Protocol` 或 `protocol`；**整数或枚举名字符串都认** |
| b | `:191-196` | `ShouldTreatAsQueuingGetTicketGL`（`:424-433`）：`Queuing_GetCryptoKeys` 且**没有** `ClientGeneratedKey/IV` 且带 `NpSN/NpToken/Npacode` ⇒ **改写成 `Queuing_GetTicket`**，并把响应 `Protocol` 覆写成 `50001`（`:435-440` `OverridePacketProtocol`） |
| c | `:201-205` | `ServerNoticeService.IsGated(protocol)` ⇒ 直接回 Error 信封（`GateMessage`/`GateError`） |
| d | `:207-213` | `_handlerManager.GetRequestType(protocol)` 为 null ⇒ Error |
| e | `:215-221` | `JsonConvert.DeserializeObject(payloadStr, requestType)` |
| f | `:223-230` | `_handlerManager.IsImplemented(protocol)` 为 false ⇒ `Error("Protocol not implemented (Server Error)")` |
| g | `:233` | `ReadServerNotificationAsync(payload, protocol)`（`:333-358`）**在处理前**取通知位 |
| h | `:236-242` | 每账号串行闸门 `GetAccountGate(accountId).WaitAsync(20s)`，超时 ⇒ `Error("Server busy")` |
| i | `:247-252` | `_handlerManager.Dispatch(protocol, payload)` |

> `HandlerManager` 类**不在本地快照内**（快照只有 `ProtocolHandlerRegistry.cs`，其 `InvokeHandler` 在 `:124-181`）。`IsImplemented` / `Dispatch` 的实现体 **未找到**。

### 1.6 handler：`Account_Auth`

`Shittim-Server__Core__NetworkProtocol__Handlers__AccountHandler.cs:107-157`

```csharp
[ProtocolHandler(Protocol.Account_Auth)]          // :107
public async Task<AccountAuthResponse> Auth(
    SchaleDataContext db, AccountAuthRequest request, AccountAuthResponse response)
{
    if (request.SessionKey == null)                // :113
        throw new UnauthorizedAccessException("Session key required");   // :114

    var account = await _sessionService.GetAuthenticatedUser(db, request.SessionKey);  // :116
    await EnsureOpenConditionScenariosCleared(db, account);                            // :119

    response.CurrentVersion = Config.Instance.ServerConfiguration.AuthCurrentVersion;  // :122 = 446690
    ...
    response.AccountDB = _mapper.Map<AccountDB>(account);                             // :148
    response.MissionProgressDBs = missionProgresses.Count > 0 ? missionProgresses : null; // :154
    return response;                                                                  // :156
}
```

**关键点（三条，直接影响实验设计）**：

1. **只读 `SessionKey`。** 请求体里的 `Version` / `DevId` / `OSType` / `DeviceUniqueId` / `MarketId` 等**一个都没用到**（`AccountAuthRequest` 有 17 个字段，`:65-85`）。
   ⇒ **响应内容是账号与配置的函数，与客户端请求字段无关。** 我们桥接合成 `{"Protocol":"Account_Auth","SessionKey":sk}`（`cn_bridge_v5.py:262`）丢掉其余字段，**不会**导致响应缺内容。
2. **`SessionKey` 必须真的在 `_activeSessions` 里**（`SessionKeyService.cs:147-164`），否则 `UnauthorizedAccessException` → 网关 `:287-295` 捕获 → `WebAPIErrorCode.InvalidSession` → **同样是 HTTP 200 的 Error 信封**，而客户端会走"回标题 + 重登"。
3. **`Account_Auth` 在免会话白名单里**（`SessionKeyService.cs:25`），但 handler 自己又硬性要求 `SessionKey`。⇒ 白名单只放行**校验环节**，不放行 handler 的入参要求。（我们桥接正是先造一个 `Account_CheckNexon` 拿真 SessionKey，`cn_bridge_v5.py:138-158`。）

### 1.7 响应构造 → 加密封装

`GatewayController.cs:244-278`

```csharp
rsp = await _handlerManager.Dispatch(protocol, payload);                       // :247
if (rsp == null) { ... Error("Handler error"); return; }                       // :254-259
if (rsp.SessionKey == null && ShouldEchoSessionKey(protocol))                  // :262  (Account_Auth 在内, :318-322)
    rsp.SessionKey = payload.SessionKey;                                       // :263
rsp.ServerNotification |= notification;                                        // :266  按位或，不覆盖
var responseJson = JsonConvert.SerializeObject(rsp, jsonSettings);             // :268
...
Core.Diagnostics.GatewayWireLog.Write(...);                                    // :273-275
var serverPacket = new ServerResponsePacket { Protocol = responseProtocolName, Packet = responseJson };  // :277
await CreateProtocolResponse(serverPacket, responseCrypto);                    // :278
```

序列化规则两套（`:122-128` 与 `:133-138`）：

| 用途 | Settings | 效果 |
|---|---|---|
| 内层 `packet` 内容 | `jsonSettings`：`NullValueHandling.Ignore` + `DefaultValueHandling.Ignore` + `OfficialContractResolver` + `OfficialDateTimeConverter` | 0/false/null 全部消失；`[OmitWhenEmpty]` 的空集合消失；`DateTime` 无时区整秒；`DateTime.MaxValue` 特殊处理 |
| 外层信封 | `serverPacketSettings`：`NullValueHandling.Ignore` + `CamelCasePropertyNamesContractResolver` + `FloatConverter` | 线上是 **`protocol` / `packet` 小写开头** |

最终写出（`:791-800`）：

```csharp
string json = JsonConvert.SerializeObject(packet, serverPacketSettings);
if (ShouldUseAes(crypto))                                              // :795  (:759-762: UseAes && key合法 && iv==16)
    json = Convert.ToBase64String(HybridCryptor.EncryptGatewayResponse(Encoding.UTF8.GetBytes(json), crypto.Key, crypto.Iv));
Response.ContentType = "application/json; charset=utf-8";
await Response.WriteAsync(json);
```

**加密的是整个信封，不是信封里套密文**（`:793` 注释：客户端 `HttpGameMessage.DecodeResponse` 先 base64 解码 + AES 解整个 body，之后才读 `protocol` 字段）。

### 1.8 一张图

```
POST /api/gateway (multipart, field "mx")
  └─ GatewayRequest()                                     GatewayController.cs:158
       ├─ DecodeGatewayPayload()                          :360   [crc][tc][kLen][ivLen][key][iv][body]
       ├─ DecodeGatewayPayloadBodies()                    :462   XOR 0xD9 + GZip ×3 变体
       ├─ TryBuildGatewayPayload()                        :495   明文 / AES(header) / AES(历史) / RSA
       ├─ ReadProtocol()                                  :412   Protocol 或 protocol, int 或 name
       ├─ [GL 分支] ShouldTreatAsQueuingGetTicketGL()     :424   50001 → 50000 改写
       ├─ [门禁]   ServerNoticeService.IsGated()          :201
       ├─ GetRequestType / IsImplemented / Deserialize    :207-230
       ├─ ReadServerNotificationAsync()                   :333   (处理前取位)
       ├─ accountGate.WaitAsync(20s)                      :236
       ├─ Dispatch() → ProtocolHandlerRegistry.InvokeHandler()  Registry:124
       │                └─ AccountHandler.Auth()          AccountHandler:108
       ├─ ShouldEchoSessionKey / |= ServerNotification     :262-266
       ├─ SerializeObject(rsp, jsonSettings)               :268
       ├─ GatewayWireLog.Write()                           :273
       └─ CreateProtocolResponse()                         :791   明文 or base64(AES(整信封))
```

---

## 2. Auth 成功后的预期调用序列

### 2.1 先给结论

**Shittim 不校验顺序，也不记录进度。** 它能提供的全部"期望"是三个**成员集合**。把它们摊开，可以还原出**协议族**（谁属于登录链），但**还原不出顺序**——顺序在客户端侧。

### 2.2 集合 A：谁能"第一个发"（免会话白名单）

`SessionKeyService.cs:17-28`

```csharp
private static readonly HashSet<Protocol> _publicProtocols = new()
{
    Protocol.Queuing_GetTicket,
    Protocol.Queuing_GetCryptoKeys,
    Protocol.Queuing_GetAuthTicket,
    Protocol.Queuing_ProcessWaitingQueue,
    Protocol.Account_CheckYostar,
    Protocol.Account_CheckNexon,
    Protocol.Account_Auth,
    Protocol.Account_Create,
    Protocol.ProofToken_RequestQuestion
};
```

`[源码实测]` 只有这 9 个可以**不带** `SessionKey` 通过 `ValidateRequest`（`:114-117`）。

⇒ 它们就是"登录链起点候选集"。国服相关的三个在里面：`Queuing_GetAuthTicket`(50002) / `Account_CheckYostar`(1009) / `Account_Auth`(1002)。

⚠ 但 `Account_Auth` 的 handler 又要求 `SessionKey`（`AccountHandler.cs:113`），所以它实际是"**校验豁免、处理不免**"——**必须已有一张票**。

### 2.3 集合 B：谁负责"发会话"

`GatewayController.cs:317-322`

```csharp
// Protocols whose responses officially carry SessionKey/AccountId, from live captures:
// Account_CheckNexon, Account_Auth, ProofToken_RequestQuestion, ProofToken_Submit.
private static bool ShouldEchoSessionKey(Protocol protocol) => protocol
    is Protocol.Account_Auth or Protocol.Account_Auth2
    or Protocol.ProofToken_RequestQuestion or Protocol.ProofToken_Submit;
```

`[源码实测]` 加上自己 set `SessionKey` 的 `Account_CheckNexon` / `Account_Create`（`AccountHandler.cs:96-100`、`:247-248`），**全套"会发会话"的协议只有 6 个**：`CheckNexon`(1014) / `CheckYostar`(1009) / `Create`(1000) / `Auth`(1002) / `Auth2`(1012) / `ProofToken_*`(37000-37001)。

### 2.4 集合 C：谁"在账号管线之外"被答

`GatewayController.cs:324-331`

```csharp
// These four are answered outside the account pipeline. In a capture whose account had unread mail
// from login to logout every response carried ServerNotification=8 except
// ProofToken_RequestQuestion / NetworkTime_Sync / ProofToken_Submit / Account_GetTutorial.
private static bool SkipsServerNotification(Protocol protocol) => protocol
    is Protocol.NetworkTime_Sync or Protocol.ProofToken_RequestQuestion
    or Protocol.ProofToken_Submit or Protocol.Account_GetTutorial;
```

`[源码实测]` 这一段是**唯一一处来自真实官方抓包的时序旁证**：它说明这四个协议在**一次登录会话里确实都出现过**，且出现时**还没有账号上下文**（否则会被盖上 `HasUnreadMail`）。

⇒ 这四发是**登录期协议**：`NetworkTime_Sync`(3) / `ProofToken_RequestQuestion`(37000) / `ProofToken_Submit`(37001) / `Account_GetTutorial`(1005)。

### 2.5 还原出的登录族（顺序部分标 `[推断]`）

| # | 协议 | 号 | 依据 |
|---|---|---|---|
| 1 | `Queuing_GetCryptoKeys` | 50001 | 集合 A；明文握手，`QueuingHandler.cs:21-40` |
| 2 | `Queuing_GetTicket` / `Queuing_GetAuthTicket` | 50000 / 50002 | 集合 A；票据 + 同一份 crypto，`:42-97` |
| 3 | `Queuing_ProcessWaitingQueue` | 50003 | 集合 A；`WaitingTicket` 轮询，`:99-114` |
| 4 | `Account_CheckNexon` / `Account_CheckYostar` | 1014 / 1009 | 集合 A+B；`AccountHandler.cs:52-106` |
| 5 | `ProofToken_RequestQuestion` → `ProofToken_Submit` | 37000 → 37001 | 集合 A+B+C；反作弊 PoW |
| 6 | **`Account_Auth`** | **1002** | 集合 A+B；`AccountHandler.cs:107-157` |
| 7 | `NetworkTime_Sync` | 3 | 集合 C；**请求体是空类**（`NetworkProtocol.cs:5609-5619`） |
| 8 | `Account_GetTutorial` | 1005 | 集合 C；`AccountHandler.cs:656-670` |
| 9 | `Account_Nickname` | 1001 | `AccountHandler.cs:253-269`；**仅当 `Nickname` 为空时**（`[推断]`） |
| 10 | `Account_LoginSync` | 1019 | `AccountHandler.cs:288+`，一次灌入 cafe/currency/character/echelon/campaign/arena… |
| 11 | `Item_List` 等零散 | — | `AccountHandler.cs:445` 原文见下 |

`AccountHandler.cs:445`（LoginSync 内注释，`[源码实测]`）：

```csharp
// Official Account_LoginSync has NO ItemListResponse child
// (the client fetches Item_List separately right after login), so it stays null here.
```

`AccountHandler.cs:307`（`[源码实测]`）：

```csharp
// the cafe screen is fed from this sync, not from Cafe_Get
// - a client can go a whole session without asking for cafe data again
```

`QueuingHandler.cs:56`（`[源码实测]`）：

```csharp
// Returning a ticket lets startup continue so downstream bootstrap endpoints
// (including gtable fetch) can be observed and aligned.
```

⇒ **队列之后还有一步"gtable 拉取"**（Excel 表 / 资源）。这一条对国服可能非常关键，见 §5 的 D4。

### 2.6 那么"Auth 之后第一发"到底是什么？

按 §2.4 的白名单与"免通知"集合，`Account_Auth` 之后**最自然的下一发是 `NetworkTime_Sync`(3)**（`[推断]`，理由是它是 C 集合里唯一一个"无请求字段、无账号语义"的往返校时，客户端在进大厅前必须知道服务器时钟偏移）。

但必须说清楚：**源码没有任何一行断言"Auth 之后就是 NetworkTime_Sync"。** 这条只能靠客户端侧证据（抓包 / 逆向 / 日志）定。

`NetworkTimeSyncResponse` 的字段（`NetworkProtocol.cs:5614-5619`）值得单独记一笔，因为它决定了这类请求的**幂等性**：

```csharp
public class NetworkTimeSyncRequest : RequestPacket
{
    public override Protocol Protocol { get => Protocol.NetworkTime_Sync; }   // ← 空请求体
}
public class NetworkTimeSyncResponse : ResponsePacket
{
    public override Protocol Protocol { get => Protocol.NetworkTime_Sync; }
    public long ReceiveTick { get; set; }     // 服务器收到时刻
    public long EchoSendTick { get; set; }    // 回声客户端的发送时刻
}
```

⇒ 这是一个**纯往返测量包**，服务端不需要任何账号数据。**如果客户端发它而我们回 404/Error，客户端会认为网络不可用**（`[推断]`，但代价极低、必须验）。

### 2.7 一条反直觉的推论（供 lead 决策）

既然 Shittim 无状态，那么"**客户端发第二发时我们会怎样**"是被 `IsImplemented` 决定的：

`GatewayController.cs:223-230` —— 未实现的协议回 `Error("Protocol not implemented (Server Error)")`。

而我们桥接对**未接管的协议一律 `_forward`**（`cn_bridge_v5.py:276-279`），转发目标是 `http://127.0.0.1:5000 + self.path`（`:225`）。

⇒ **如果客户端第二发是 `/api/networktime/sync`，Shittim 没有这个路由 ⇒ 404 空 body。** 客户端拿到 404 后的行为（弹窗 / 重试 / 静默回标题）未知，但**它绝不会被推进到第三发**。

这条把我们"第二发是否到达"的问题，变成了"**第二发到达后被谁吃掉**"的问题——见 §5 的 D2。

---

## 3. "客户端不发请求"相关机制

### 3.1 有没有服务端主动推送（long-polling / 队列）？

**没有。彻底没有。**

`[源码实测]` 四项证据：

1. **HTTP 面只有 3 个端点**：`GET /api/Queuing/Ping`（`:150-152`）、`GET /api/gateway`（`:154-155`，返回**空 200**，注释名 `GatewayHealthCheck`）、`POST /api/gateway`（`:157`）。外加 `ServerInfoController` 的 2 个（§3.4）。**没有任何挂起连接、没有 `Task.Delay` 后写 body、没有 `IAsyncEnumerable`。**
2. **`ServerNotification` 是"每个响应上的位标志"，不是推送通道**：`Packet.cs:50`（`ServerNotificationFlag ServerNotification`）+ `ProtocolData.cs:521-540`（17 个位：`NewMailArrived=4`、`HasUnreadMail=8`、`CanReceiveArenaDailyReward=32`…）。
   `GatewayController.cs:265-266` 注释明确：「官方在**每个 in-session 响应**上盖基线位」「OR 而不是 assign」。
   ⇒ **红点必须由客户端先发一个请求才拿得到。服务端永远不会主动敲门。**
3. **10 个 `IHostedService` 全是"改客户端文件"或"同步世界 raid 数据"，不与客户端通信**（`GameServer.cs:99-119`）：`ClientMetadataPatchService` / `ClientSteamOfflinePatchService` / `ClientGrap64ManagementService` / `ClientInfaceConfigPatchService` / `ClientNativeIasPatchService` / `ClientExcelBannerPatchService` / `ClientExcelCharacterSyncService` / `ClientCatalogPatchService` / `ClientRegionLabelPatchService` / `ClientStoreUrlPatchService` / `WorldRaidSyncService` / `GameClientService`。
4. **没有 SignalR / WebSocket**：全项目 grep `Push|WebSocket|SignalR|long.?poll|KeepAlive` **零命中**（唯一的 `Push` 类命中在协议名里，如 `Conquest_*`）。

### 3.2 有没有心跳超时？

| 层 | 有/无 | 位置 | 后果 |
|---|---|---|---|
| 服务端对"客户端不理我" | **无** | — | 服务端不会因为客户端沉默做任何事，也不会主动断开 |
| 服务端对"我等这次 handler" | **有，20 秒** | `GatewayController.cs:236-242` | 超时回 `Error("Server busy")`；**只影响当前这一个请求** |
| 会话过期 | **有机制，无调用点** | `SessionKeyService.cs:172-188` `PurgeExpiredSessions(maxInactivity)` | 本地快照内**找不到调用者**（未找到），推测由某个 hosted service 定时调；`LastActivity` 只在 `ValidateRequest`(`:139`) 与 `GetAuthenticatedUser`(`:158`) 更新 |
| 客户端侧重发元数据 | **有字段，服务端不读** | `Packet.cs:27-28` `ClientUpTime` / `Resendable` | 全项目 grep：**除定义外零引用** ⇒ 服务端忽略 |

⇒ **本卡点不是"心跳超时"。** 服务端没有任何超时能把客户端"挂住"。

### 3.3 ★ `Queuing_Ping` 到底扮演什么角色（lead 特别点名）

**结论：`Queuing_Ping` 根本不是协议，它只是一条 HTTP 健康探针；它不推进队列、不改变客户端状态、也不能把客户端从排队界面放出来。**

`[源码实测]` 三层证据：

**(a) `Protocol` 枚举里没有 `Queuing_Ping`。**

`ProtocolData.cs:500-503` 全文只有四个 Queuing：

```csharp
Queuing_GetTicket = 50000,
Queuing_GetCryptoKeys = 50001,
Queuing_GetAuthTicket = 50002,
Queuing_ProcessWaitingQueue = 50003,
```

⇒ 它**没有协议号**，不可能出现在 `packet` 里，`ProtocolHandlerRegistry` 里也没有它的 handler。它是一个**独立的 HTTP GET 路由**：

```csharp
// GatewayController.cs:150-152
[HttpGet]
[Route("Queuing/Ping")]
public IResult Ping() => Results.Ok("Pong");
```

**(b) 它不携带任何排队状态。** 返回 `"Pong"` 两个字面量，没有 ticket、没有序号、没有 ETA、没有会话。
⇒ 客户端轮询它，能得到的唯一信息是"**队列服务活着**"。

**(c) 真正决定"出不出队"的是 `Queuing_*` 响应里的两个数值 + 一个字符串。**

`QueuingHandler.cs:99-114` `ProcessWaitingQueue` —— **本报告最重要的一段注释**（`[源码实测]`）：

```csharp
response.WaitingTicket = request.WaitingTicket;
// the steam build asks for its enter ticket here instead of through Queuing_GetTicket, and only the first
// call carries the nexon credentials - a retry after being queued sends the waiting ticket alone.
// an empty EnterTicket is what holds the client on the queue popup,
// so mint one from NpSN/NpToken the moment they arrive.
response.EnterTicket = request.NpSN != 0
    ? Convert.ToBase64String(Encoding.UTF8.GetBytes($"{request.NpSN}/{request.NpToken}"))
    : string.IsNullOrEmpty(request.AuthTicket) ? request.WaitingTicket : request.AuthTicket;
response.ServerSeed = "";
response.ServerTimeTicks = 0;
```

⇒ **`EnterTicket` 为空 = 客户端被扣在排队弹窗上。** 这是源码里**唯一一处明写"什么条件让客户端停住"的地方**，正是 lead 猜的那条：**客户端认为自己在排队，它就不会发游戏协议。**

`QueuingHandler.cs:61-71` `GetTicket` —— 数值语义（`[源码实测]` + 官方抓包注释）：

```csharp
// Official shape (live captures): Birth is an empty string, the ticket/allowed sequences are large
// non-zero counters with AllowedSequence ahead of TicketSequence (no queue wait),
// and RequiredSecondsPerUser is a small positive value.
response.TicketSequence      = 130_000_000 + (DateTimeOffset.UtcNow.ToUnixTimeSeconds() % 10_000_000);
response.AllowedSequence     = response.TicketSequence + 1722;   // ← 必须“领先”
response.RequiredSecondsPerUser = 0.0058;
```

⇒ **客户端自己算等待**：`AllowedSequence > TicketSequence` ⇒ 不用等。`RequiredSecondsPerUser` 只是 ETA 的系数。**这两个数是客户端本地的判据，服务端不会替它决定。**

顺带排掉一个常见误判：**队列不校验版本**。

`QueuingHandler.cs:48-59`：

```csharp
// Do not hard-fail queue bootstrap when client and server versions differ.
_ = majorMinorMismatch;      // ← 算出来就扔掉
```

⇒ 国服 3.0.2 对 Shittim 的 `GameVersion=1.90.x`，**不会**在队列这里被卡。

**(d) 那么国服的排队怎么走？**（`[推断]`，但可判）

我们桥接**完全绕过队列**：直接造 `Account_CheckNexon` 拿 SessionKey（`cn_bridge_v5.py:138-158`），从不经 `Queuing_*`。
⇒ **从服务端视角看，"客户端从没排过队"。**
⇒ 但**客户端自己有没有排过队，是另一回事**——要去查客户端**有没有发过** `Queuing_GetCryptoKeys` / `Queuing_GetAuthTicket` / `Queuing_ProcessWaitingQueue`。这是 §5 的 D3 分支。

**特别注意一个隐患**：如果客户端发了 `Queuing_ProcessWaitingQueue` 而我们把它 `_forward` 到 `127.0.0.1:5000/api/queuing/processwaitingqueue`，Shittim **没有这条路由**（只有 `api/Queuing/Ping`）⇒ **404 空 body** ⇒ 客户端拿不到 `EnterTicket` ⇒ 按上面注释，**它就一直卡在排队弹窗上，永远不发游戏协议**。这条链**完全能解释"回 200 之后静默停住"**，且与 lead 的直觉一致。

### 3.4 ★ 一条此前没人用的判据通道：`POST /log`

`ServerInfoController.cs:47-67`（`[源码实测]`）：

```csharp
[Route("/")]                                  // :9
public class ServerInfoController : ControllerBase
...
[HttpPost("log")]
public async Task<IResult> GetLog()
{
    ...
    _logger.LogError("Game Client Error Detected!");
    _logger.LogError("Time: {Time}", payload["Time"]);
    _logger.LogError("Account: ID {AccountId} | {Account}", ...);
    _logger.LogError("Error Type: {Type}", payload["Type"]);
    _logger.LogError("Error Message: {ErrorMessage}", message);
    _logger.LogError("Server: {LastServer}", payload["LastServer"]);
    _logger.LogError("LastLoginName: {LastLoginName}", ...);
    _logger.LogError("Revision: {Revision}", ...);
    _logger.LogError("PublisherAccountId: {PublisherAccountId}", ...);
    return Results.Ok();
}
```

⇒ **客户端自己在本地炸了的时候，会 `POST /log` 把 `Type` / `Message` / `Revision` 报给服务器。**

**这是判断"客户端是在引擎里死了，还是在等网络"的一等判据，而且不需要 root、不需要 pcap：**

> 看 nginx 的 `ba_raw.log` 有没有 `POST /log`（或 `/log`）。
> - **有** ⇒ 客户端抛了 C# 异常。`Type` + `Message` 直接告诉你崩在哪。**问题不在协议，在客户端逻辑。**
> - **没有** ⇒ 客户端活着，大概率在等 UI（排队弹窗 / 昵称弹窗 / 加载条）。

（未连接服务器，**本轮没有执行这个检查**；这是给 lead 的现成手段。）

### 3.5 还有一个能"整体变哑"的开关：`ServerNoticeService`

`GatewayController.cs:201-205` + `GameServer.cs:44`：

```csharp
Shittim_Server.Services.ServerNoticeService.Load();      // GameServer.cs:44   启动时加载
...
if (ServerNoticeService.IsGated(protocol))               // GatewayController.cs:201
{
    await CreateProtocolErrorResponse(ServerNoticeService.GateMessage, ServerNoticeService.GateError!.Value, responseCrypto);
    return;
}
```

`[源码实测]` 这是一个**全局协议闸门**：一旦 `IsGated` 为真，所有包都变成 Error 信封（HTTP 仍 200）。类本体**不在本地快照**（未找到），配置来源也读不到。
⇒ **必须先确认它是关的。** 如果它没关，我们所有"响应体分析"都是在分析错误信封。

### 3.6 客户端"必须收到才往下走"的两条硬依赖（顺带记下）

| 依赖 | 位置 | 缺了会怎样 |
|---|---|---|
| `Account_Auth` → `SessionKey` | `GatewayController.cs:262-263` 回显 | 后续所有协议的 `ValidateRequest` 全失败 ⇒ `InvalidSession` ⇒ 客户端回标题重登 |
| `AttendanceBookRewards` / `Nickname` | `AccountHandler.cs:130`、`report\36` §2/§5 | `Nickname=""` 是**新号正常态**（`report\36` §0-3），但客户端**可能弹昵称输入框**（`[推断]`）。**"不弹窗"不等于"没有 UI 在等输入"** |

---

## 4. 国服 vs 国际服的差异点清单

### 4.1 网关 RSA 密钥：国服 2048，`GatewayPrivateKey4096.pem` 是废的

| | 国际服（Nexon / Steam） | 国服（Yostar） |
|---|---|---|
| 密钥位数 | **RSA-4096** | **RSA-2048** |
| 公钥 PEM 规范化后总长 | **799 B** | **451 B** |
| metadata 里的三段切分 | **272 / 272 / 255** | **150 / 150 / 150** |
| RSA 密文长度 | **512 B** | **256 B** |
| 私钥文件大小 | ~3272 B（上游 `config/GatewayPrivateKey.pem`） | ~1732 B（`bapatch/gateway_key/gateway_priv.pem`） |

源码侧的对应：

- `Shittim-Server__Services__ClientMetadataPatchService.cs:10-12`（`[源码实测]`）：
  ```csharp
  // ... the split lands wherever the build's literal packing put it:
  //     272/272/255 for the RSA-4096 key, and 150/150/150 for the RSA-2048 one it replaced.
  private static readonly int[] ChunkLengths = [272, 272, 255];
  private const int ChunkCount = 3;
  ```
  `:207-208` 会**硬校验**替换后 PEM 长度必须等于 `ChunkLengths.Sum()`（= 799），不等直接抛。
- `Shittim-Server__Core__GatewaySessionCrypto.cs:89-91`（`[源码实测]`）：
  ```csharp
  // Account_CheckNexon / Queuing_GetAuthTicket instead RSA-encrypt the key+IV with the gateway PUBLIC key
  // that ClientMetadataPatchService injects into the client (512 bytes for the RSA-4096 key pair),
  // so they arrive as RSA ciphertext.
  ```
  注意这里"512 bytes"是**写给 4096 的**，注释与国服无关。

**关键区分（别搞混）**：

- **代码**对位数**不设限**：`DecodeClientCrypto`（`GatewaySessionCrypto.cs:92-98`）只要求"解出来长度合法"（key 16/24/32、iv 16），`TryRsaDecrypt`（`:105-148`）遍历 5 种 padding、**不检查模长**。
- **约束在客户端 metadata**：三个"洞"是定长的（`ClientMetadataPatchService.cs:14-33` 注释：换长度就要挪 `fieldAndParameterDefaultValueData` 整段及之后全部偏移，改错 = 卡「Unpacking game resources」，**屏幕无提示**）。
- ⇒ 所以 `GatewayPrivateKey4096.pem`（3272 B / 4096 位）对国服**毫无用处**：它解不开 256 B 的密文，而且对应的公钥（799 B）**塞不进 451 B 的洞**。`report\30` §5.3 的拒绝测试已实测：4096 公钥 814 B，工具直接退出。

### 4.2 传输与信封：两套完全不同的栈

| | 国际服（Shittim 面向的 Steam 客户端） | 国服（3.0.2 移动端） |
|---|---|---|
| URL | **`POST /api/gateway`**（唯一业务入口） | **`POST /api/account/auth`** 这类"协议名 → 路径"（`Queuing_Ping` 的路径还有大写） |
| Content-Type | `multipart/form-data`，字段 `mx` | `multipart/form-data`，字段 `protocol` / `encode` / `packet` |
| 协议标识 | `mx` 内层 JSON 的 `Protocol` 字段（int 或 name） | 表单 `protocol` = **BASE32(MD5(UTF-16LE(协议名)))**，26 字符 |
| 请求体结构 | `[crc u32][typeConversion i32][keyLen u8][ivLen u8][key][iv][XOR0xD9(gzip(len+json))]` | `[u32 明文长度][gzip( [iv 16][AES-256-CBC ct][key 32 ASCII] )]` |
| 加密所需密钥 | RSA-4096 包裹 clientKey/IV | **每包随机 32 B，明文附在包尾**（`report\35` §一） |
| 响应信封 | 明文或 `base64(AES(整个 {"protocol","packet"}))` | 待定；客户端有 `DecryptOrReturnOriginal`（`report\34` §六）⇒ 大概率接受明文 |

来源：`report\34` / `report\35`（国服实测解密，100% 命中已知明文）+ `report\36` §7（响应实测）+ `_tmp\cn_proto\...\core\client.py:410-418`（`gateway_url` = `host_url + "/gateway"`，`default_headers` 带 `mx: 2`，第三方实现口径一致）。

⇒ **结论：桥接不是"可选优化"，是硬需求。** Shittim 的路由永远只认 `/api/gateway`，国服的 `/api/account/auth` 必须由 `cn_bridge_v5.py` 那类进程先接住、翻译、再造 `.mx`。

### 4.3 登录协议族

| | 国际服 | 国服 |
|---|---|---|
| 队列票据 | `Queuing_GetTicket`(50000)，字段 `NpSN`/`NpToken`/`Npacode` | `Queuing_GetAuthTicket`(50002)，字段 `YostarUID`/`YostarToken` |
| 会话换取 | `Account_CheckNexon`(1014) | `Account_CheckYostar`(1009) |
| EnterTicket 内容 | `base64("{NpSN}/{NpToken}")` | `base64("{YostarUID}/{YostarToken}")` |
| 反作弊 | Nexon Game Security（`ServerSeed` 官方 1 KB，`QueuingHandler.cs:65` 注释明确置空） | 腾讯 ACE |

`[源码实测]`：`QueuingHandler.cs:76-97`（GetAuthTicket 的 DTO 字段就是 Yostar 那套）、`AccountHandler.cs:52-106`（CheckNexon）、`NetworkProtocol.cs:5836-5861`。
**含义**：Shittim 两条都实现了，国服这条**在协议层本来是通的**——不是卡点的原因。

### 4.4 版本号口径不同（容易误判成门）

| 项 | Shittim 值 | 出处 |
|---|---|---|
| `AuthCurrentVersion`（`Account_Auth.CurrentVersion`） | **446690** | `ServerConfig.cs:6` 注释 + `AccountHandler.cs:122` |
| `GameVersion`（队列比对用） | **1.90.439170** | `ServerConfig.cs` |
| 国服客户端 | **3.0.2 / versionCode 73** | `report\36` 头部 |

`[源码实测]` 服务端**对版本不做任何拒绝**：

- 队列：`_ = majorMinorMismatch;`（`QueuingHandler.cs:48-59`，算完扔掉）
- Auth：`AccountHandler.cs:121` 注释「the client always sends `Version: 0` here; the official server answers with its own current data-build number」
- ⇒ `CurrentVersion` 是"告知"，不是"校验"。**版本不匹配不会造成静默停住。**

⚠ 但 `GameServer.cs:58-61` 启动时 `BlueArchiveVersionResolver.GetOrUpdateVersionIdAsync(...)` 会去拉官方 CDN 版本（落 `config\ba_version_cache.json`，默认是 `com.nexon.bluearchive`）。
⇒ **必须 `AutoCheckVersion=false / AutoUpdateVersion=false`**，否则启动期会有对外依赖（这不是协议卡点，但会让服务启动不稳定）。

### 4.5 与既有报告的一处冲突（需要修正）

`report\04-服务端就绪度.md` §4.1 第 13 行写：

> `Queuing_GetTicket` → **返回 gateway URL**（`ba-client-patching-shittim.md:29`、`ba-protocol-full.md:112`）

**源码不支持这条。** `NetworkProtocol.cs:5806-5816` 的 `QueuingGetTicketResponse` 全文只有 7 个字段：

```csharp
public string? WaitingTicket;  public string? EnterTicket;
public long TicketSequence;    public long AllowedSequence;
public double RequiredSecondsPerUser;  public string? Birth;  public string? ServerSeed;
```

**没有任何 URL / ConnectionGroup 字段**。`ConnectionGroupsJson` / `DefaultConnectionGroup` 在**另一个控制器**里（`ServerInfoController.cs:36-44`，路径 `com.nexon.bluearchive/server_config/{*filename}`，且**只认 `com.nexon.*` 两个前缀**，对国服无用）。

⇒ 处置：`report\04` 那一行标注为"来自第三方文档，Shittim 源码不支持"。**不要**按"队列响应里带 URL"去设计实验。

---

## 5. 判定树：客户端在什么条件下才会发第二个请求

给 lead 直接做实验设计用。**从上往下走，第一个命中的分支就是答案，其余不用试。**

---

### D0 前置：先证明"客户端真的没发"

> **这是判据纪律的直接应用。** 只看 `api_all_requests.log` 只能覆盖打到 bridge 的请求；客户端完全可能打到别的 vhost / 别的 host / 直连别的域名。

```
IF  ba_raw.log 在 Auth 那一轮之后，{任何 host、任何 path} 都没有新行
    且 pcap 里也没有客户端→我们 443/8443 的新 TCP 流
THEN 客户端确实停住了 → 进 D1
ELSE IF ba_raw.log 有新行，但 bridge 日志没有
THEN → 【请求去了别处】记下那条 host+path，回到 D0 重新判断（这一步之前若做过"客户端不请求"的结论，作废）
ELSE IF 只有 bridge 日志有新行
THEN → 看 protocol_name 字段；若为 null 说明 base32 没命中协议名表 → 直接修表
```

**配套要求**：`ba_raw.log` 必须**带 host**（`133_around.sh:65` 已按 `host="gsqc-api` 过滤，说明有这个能力）；判断单位是 **host+path**，不是 IP（纪律④）。

---

### D1 客户端是不是"在本地就死了"

```
IF ba_raw.log 出现 POST /log   （ServerInfoController.cs:47，客户端自报异常）
THEN → 【客户端 C# 层抛异常】
       读 Shittim 日志里那条 "Game Client Error Detected!" 的 Type / Message / Revision
       这是唯一能直接读到客户端崩溃原因的通路
       常见触发：响应 JSON 反序列化失败 / 缺字段导致 NullReference / 资源加载失败
       ⇒ 停止一切协议实验，先去修这个字段
ELSE → 进 D2
```

**本轮没有验证这条通道是否被用过**（不连服务器）。请 lead 一次确认：`grep -c 'POST /log' /www/wwwlogs/ba_raw.log`。若历史轮次里出现过 `/log`，那里面的 `Type`/`Message` 就是客户端自己写下的死因。

---

### D2 Auth 的响应体是不是客户端真正认的那一份

按代价从低到高：

```
2a) 检查响应信封形态
    IF bridge 回的是明文 {"protocol":"Account_Auth","packet":"<json字符串>"}
    THEN 这是 Shittim 的 aes=False 分支形态（GatewayController.cs:791-800）。
         客户端有 DecryptOrReturnOriginal（report\34 §六）⇒ 理论可接受。
         但【未实测确认】，而 125_watch / 126_encresp1 / 127_watch_enc1 系列已在试加密响应。
    IF 试过加密响应仍无第二发
    THEN ⇒ 信封不是问题，进 2b

2b) 检查 packet 里 Protocol 的类型
    IF packet 内 Protocol 是 int(1002) 而客户端期望字符串 "Account_Auth"（或反之）
    THEN 客户端 get_Protocol 匹配失败 → 找不到对应的 pending 请求 → 协程永远挂着
         【这正是"静默停住"最典型的表现】
    判据：拿一份官方视频/资料里 Account_Auth 响应原文对照；
         或让 bridge 把 Protocol 写成 "Account_Auth" 字符串再跑一轮（一次实验即可排除）

2c) 检查 Account_Auth 是否真的"成功"（不是 HTTP 200，而是 body）
    IF packet.protocol == "Error"
    THEN 读 ErrorCode：
         InvalidSession     ⇒ SessionKey 不在 _activeSessions（SessionKeyService.cs:147-164）
         ServerFailedToHandleRequest ⇒ handler 抛异常（如 Excel 表缺失，AccountHandler.cs:151-153 FilterMissionScreenProgresses）
    IF 是 Error ⇒ 客户端已经在走"回标题重登"（GatewayController.cs:289-293 注释明说）
                ⇒ 你会看到它重发 Queuing_*，而不是发第二发游戏协议
```

---

### D3 ★ 客户端是不是认为自己在排队（lead 特别点名的那条）

```
D3-1 客户端在 Auth 之前发过 Queuing_* 吗？
     IF ba_raw 里本轮有 /api/queuing/* 或 base32 命中 Queuing_GetCryptoKeys/GetAuthTicket
     THEN 继续 D3-2；ELSE ⇒ 没排队，跳过 D3，去 D4

D3-2 它拿到的 EnterTicket 是空的吗？
     判据（源码直给）：QueuingHandler.cs:106-109 注释
        "an empty EnterTicket is what holds the client on the queue popup"
     IF 我们对该请求做了 _forward（cn_bridge_v5.py:276-279）而 Shittim 没有对应路由
     THEN 客户端拿到的是 404 空 body ⇒ EnterTicket 缺失 ⇒ 【卡在排队弹窗，永远不发游戏协议】
          ← 这条能完整解释"回 200 之后静默停住"
     修法：在 bridge 里接管 Queuing_*，用 Shittim 的 handler 逻辑回：
           GetAuthTicket → AuthTicket = base64("uid/token")                (QueuingHandler.cs:84,93)
           GetTicket     → TicketSequence/AllowedSequence/RequiredSecondsPerUser  (QueuingHandler.cs:67-69)
           ProcessWaitingQueue → EnterTicket 非空 + WaitingTicket 原样回    (QueuingHandler.cs:105-109)

D3-3 数值对不对？（客户端自己算 ETA）
     IF AllowedSequence <= TicketSequence
     THEN 客户端算出"要等很久" ⇒ 停在排队条
     ⇒ 必须 AllowedSequence = TicketSequence + 1722（或任意正偏移，QueuingHandler.cs:68）

D3-4 客户端在轮询 Queuing_Ping 吗？
     IF ba_raw 里出现 GET /api/Queuing/Ping（高频、周期）
     THEN 【强证据：客户端认为自己在排队界面】
          因为 Queuing_Ping 没有协议号（ProtocolData.cs:500-503），只是 HTTP 探针
          ⇒ 它轮询 = 它在等队列；此时让它出队的唯一办法是把 EnterTicket/序号喂对（D3-2/3-3）
          【注意】轮询 Ping 本身不会让它出队 —— 别去优化 Ping 的响应
```

---

### D4 是不是卡在"资源 / gtable"而不是协议

```
IF ba_raw 里出现 CDN 域名的请求（static.bluearchive-cn.com / ResUrl 里那个）
   且 ResUrl 是客户端在 Auth 请求里自己带的（report\35 解密明文：ResUrl=https://static.bluearchive-cn.com/prodm39）
THEN → 客户端已经过了协议层，在拉资源
      但它拉的是国服 CDN，不是我们的！（report\35 明文里的 ResUrl 是官方域名）
      卡点转移到"资源版本 / catalog 对不对"，不在协议
      ⇒ 判据：资源请求是否 404 / 是否 304 卡住
（QueuingHandler.cs:56 提到 "downstream bootstrap endpoints (including gtable fetch)"
 ⇒ 队列之后确实还有一步表拉取，与我们自己的 Excel 表要对得上）
```

---

### D5 是不是会话/鉴权把后续请求全变成 InvalidSession

```
IF Auth 之后 ba_raw 里**周期性地**看到同一批请求反复出现（Auth → 回标题 → Auth …）
THEN → 每一次第二发都被判 InvalidSession，客户端回标题重登
      根因候选：
        a) bridge 的 SESSION 缓存失效（cn_bridge_v5.py:128-158，force_reauth 标记）
        b) Shittim 重启 ⇒ sessions.json 没落盘（SessionKeyService.cs:30-33 已做持久化，检查文件在不在）
        c) 我们发给客户端的 SessionKey 与发给 Shittim 的那张票不是同一张
      判据：比对 bridge 日志里 session_source（cache / fresh）与客户端回报的 MxToken
```

---

### D6 如果以上全否 —— 那就是"客户端根本没打算发第二发"

```
IF D0~D5 全部排除
THEN ⇒ 结论：国服 3.0.2 的登录状态机在 Account_Auth 之后走的是**客户端侧分支**，
       该分支的前提条件在我们给的响应里不成立（某个字段语义/取值不对），
       或者它走的是一条我们完全没见过的路径（例如先要 /api/state 里的某个字段、
       或先要一个 Shittim 根本不提供的端点）。
       ⇒ 下一步只能往客户端侧取证：抓包对照官方（不可行）/ 逆向 IL2CPP 里
         AccountManager / AuthManager 的协程链 / Frida hook HttpGameSession.Send
       （report\38-Frida部署清单.md 已有部署方案）
```

---

## 6. 未找到 / 读不到（诚实标注）

| 项 | 状态 | 卡在哪 |
|---|---|---|
| `HandlerManager` 类（`GetRequestType` / `IsImplemented` / `Dispatch`） | **未找到** | 本地快照无此文件；只有 `ProtocolHandlerRegistry`（`InvokeHandler`） |
| `ServerNoticeService`（`IsGated` / `Flags` / `GateMessage`） | **未找到** | 类本体与配置来源都不在快照 |
| `MailNotificationService` | **未找到** | 仅被引用（`AccountHandler.cs:341`） |
| `PurgeExpiredSessions` 的调用者 | **未找到** | 快照内只有定义（`SessionKeyService.cs:172`） |
| `HybridCryptor`（`EncryptGatewayResponse` / `DecryptTextAES` / `VerifySignatureKeyAndIVWithRSA`） | **未找到** | 不在快照 |
| `NetworkTime_Sync` / `System_Version` / `Session_Info` 的 handler 是否存在 | **无法判定** | handler 文件不在快照，`IsImplemented` 的真实集合读不到 |
| 国服客户端的 `Account_Auth` 响应 DTO（3.0.2） | **读不到** | 需要反编译或抓官方包；本轮离线 |
| 官方抓包里 `Account_Auth` 之后紧接的协议 | **读不到** | `GatewayController.cs:326` 只给了"出现过哪四个"，没给顺序 |
| 国服客户端是否真的会 `POST /log` | **未验证** | 需在服务器 grep `ba_raw.log`（本轮按规矩不连服务器） |

**快照覆盖范围**（`_dl.py:6-22` 白名单，共 24 文件）：`Program.cs` / `appsettings.json` / `GatewayController` / `ServerInfoController` / `QueuingHandler` / `AccountHandler` / `ProtocolHandlerRegistry` / `ProtocolHandlerAttribute` / `ProtocolHandlerBase` / `GatewaySessionCrypto` / `Packet` / `ProtocolData` / `NetworkProtocol` / `SerializationAttributes` / `UserAccount` + `CLI` / `Configuration` / `Services` 若干。
⇒ **凡是"未找到"的，一律只代表"这份快照里没有"，不能外推。**

---

## 7. 给 lead 的最小实验集（按性价比排序）

| # | 动作 | 代价 | 判据（唯一） | 能排除什么 |
|---|---|---|---|---|
| 1 | `grep -c '"POST /log' /www/wwwlogs/ba_raw.log` | 10 秒 | 有没有客户端自报 | D1：客户端是否在本地崩了（**最高价值、此前未用**） |
| 2 | 确认 `ServerNoticeService` 未开启（`Config` 侧） | 1 分 | 所有响应都不是 `protocol:"Error"` | §3.5 全局闸门 |
| 3 | `ba_raw.log` 按 **host** 统计 Auth 之后的行（不按 IP） | 2 分 | 有新 host 出现即推翻"无第二发" | D0：观测有效性 |
| 4 | 把 `packet` 里的 `Protocol` 改成字符串 `"Account_Auth"`（或数字，取当前没有的那一种）跑一轮 | 5 分 | 客户端是否发第二发 | D2b（协议匹配）—— **一次实验定生死** |
| 5 | 在 bridge 里接管 `Queuing_*`，按 `QueuingHandler.cs` 的语义回（EnterTicket 非空、AllowedSequence 领先） | 20 分 | 客户端是否过排队界面 | D3（排队假象） |
| 6 | 抓一轮 pcap（手机侧），比 `ba_raw.log` 多出的目标 | 20 分 | pcap 里有/无 | D0 兜底（纪律①） |

**不要做的事**（本轮已证伪的方向）：

- ❌ 拿 `HTTP 200` 当成功判据（§0.2：Shittim 三种结果都是 200）
- ❌ 去优化 `Queuing_Ping` 的响应（§3.3：它不是协议，不推进队列）
- ❌ 配 4096 位密钥（§4.1：国服是 2048，metadata 洞只有 451 B）
- ❌ 按"队列响应带 gateway URL"设计实验（§4.5：源码 DTO 里没有这个字段）
- ❌ 指望服务端推送把客户端叫醒（§3.1：全项目零推送）

---

## 附录：本报告引用的本地文件

| 文件 | 行数/大小 | 用途 |
|---|---|---|
| `report\_tmp\shittim\src\Shittim-Server__Controllers__Api__GatewayController.cs` | 802 | 网关全路径 |
| `report\_tmp\shittim\src\Shittim-Server__Core__NetworkProtocol__Handlers__AccountHandler.cs` | 1056 | Auth / Nickname / LoginSync / GetTutorial |
| `report\_tmp\shittim\src\Shittim-Server__Core__NetworkProtocol__Handlers__QueuingHandler.cs` | 184 | 排队语义（§3.3 全部依据） |
| `report\_tmp\shittim\src\Shittim-Server__Services__SessionKeyService.cs` | 206 | 免会话白名单、会话校验 |
| `report\_tmp\shittim\src\Shittim-Server__Core\GatewaySessionCrypto.cs` | 394 | RSA / AES 握手 |
| `report\_tmp\shittim\src\Schale__MX__NetworkProtocol__Packet.cs` | 61 | 信封与通知位 |
| `report\_tmp\shittim\src\Schale__MX__NetworkProtocol__ProtocolData.cs` | 1268 | 协议号、通知位枚举 |
| `report\_tmp\shittim\src\Schale__MX__NetworkProtocol__NetworkProtocol.cs` | 7180 | 全部 DTO（Queuing/Auth/NetworkTime） |
| `report\_tmp\shittim\src\Shittim-Server__Controllers__Api__ServerInfoController.cs` | 69 | **`POST /log` 判据通道** |
| `report\_tmp\shittim\src\Shittim-Server__CLI__GameServer.cs` | 276 | 中间件、hosted services、端口 |
| `report\_tmp\shittim\src\Shittim-Server__Services__ClientMetadataPatchService.cs` | 434 | 4096/2048 切分 |
| `scripts\cn_bridge_v5.py` | 294 | 我们当前的桥接实现 |
| `scripts\account_auth_probe_v6.py` | 431 | 已有实验开关（encresp1/2/3 等） |

**只写入了本文件。** 未修改 `report\_tmp\shittim\src\` 下任何源码，未修改任何他人报告，未连接手机或服务器。
