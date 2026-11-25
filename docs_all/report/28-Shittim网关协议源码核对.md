# 28 — Shittim-Server 网关协议源码级核对

> 上游仓库：**`Neoexm/Shittim-Server`**（`https://github.com/Neoexm/Shittim-Server`）
> 核对基准：`main` @ `5f3910ea44a8798c213ea12a3e85f182194f92c6`（`pushed_at` 2026-08-20T14:33:23Z）
> 仓库描述：`Blue Archive Private Server For Steam`；语言 C#；465 star / 56 fork；无 LICENSE
> 本地源码副本：`report\_tmp\shittim\src\`（逐文件从 GitHub Contents API 取回并 base64 解码）
> 取证时间：2026-11-14 02:10–02:20

**证据分级**：本节所有结论都标注 `[源码实测]`（我读到的源码原文）或 `[推断]`。
凡是标注「读不到」的，说明我没有拿到对应文件，不做编造。

---

## 0. 一句话总览

| 问题 | 答案 |
|---|---|
| `POST /api/gateway`（2 段）能不能命中 | **能。** 路由前缀就是 `api`，动作就是 `gateway`，正好 2 段。之前「要求三段」的结论是错的 |
| 为什么 `GET /api/state` 会 404 | 因为 `GatewayController` 里**根本没有 `state` 这个动作**。控制器上确实存在 `Queuing/Ping`（3 段）、`gateway`（2 段）等，但没有任何 `state` |
| 国服客户端能直接用吗 | **协议层是原生支持的**（Yostar 系列协议号齐全，还带 `ClientInfaceConfigPatchService`）。**真正的拦路虎是网关 RSA 公钥被编译进客户端 `global-metadata.dat`**，Shittim 的做法是直接改客户端的 metadata |
| 我们最该抄的一件事 | `Account_CheckYostar` **不验签、不校验 token，账号不存在会自动建号**，返回 `ResultState = 1` 即成功 |

---

## Q1. 网关的真实路由模板

### 1.1 控制器声明 `[源码实测]`

`Shittim-Server/Controllers/Api/GatewayController.cs:98-102`

```csharp
namespace Shittim_Server.Controllers.Api
{
    [ApiController]
    [Route("api")]
    public class GatewayController : ControllerBase
```

### 1.2 全部端点 `[源码实测]`

| 行号 | 特性 | 组合出的完整路径 | HTTP 方法 |
|---|---|---|---|
| `:150-152` | `[HttpGet]` + `[Route("Queuing/Ping")]` | `/api/Queuing/Ping` | GET |
| `:154-155` | `[HttpGet("gateway")]` | `/api/gateway` | GET |
| **`:157-158`** | **`[HttpPost("gateway")]`** | **`/api/gateway`** | **POST** |

`:150-158` 原文：

```csharp
[HttpGet]
[Route("Queuing/Ping")]
public IResult Ping() => Results.Ok("Pong");

[HttpGet("gateway")]
public IResult GatewayHealthCheck() => Results.Ok();

[HttpPost("gateway")]
public async Task GatewayRequest()
```

### 1.3 结论

- **`POST /api/gateway`（2 段）完全合法且是唯一业务入口。** `[Route("api")]` 提供前缀，`[HttpPost("gateway")]` 提供子路径，ASP.NET Core 会拼成 `api/gateway`。
- **不存在任何 `/{path1}/{path2}` 之类的通配模板。** 我对本地全部 `.cs` 做了 `path1|\{path\}|api/\{` 正则检索，**唯一命中**是 `ClientMetadataPatchService.cs:305` 里一个 `.shittim_patch.json` 文件名拼接，与路由无关。
  ⇒ 之前「DLL 字符串里看到 `api/{path1}/{path2}`，所以要求三段」的判断是**误读**。那段字符串应来自其它类（例如 `IasController` 的 `/ias/{env}/public/{*path}`）或编译器生成的模板缓存。
- **`/api/state` 404 的真正原因**：控制器里没有任何名为 `state` 的动作。`Queuing/Ping` 是三段，`gateway` 是两段，两者都能命中，所以「段数不够」不成立。

### 1.4 是否有前缀 / CORS / Host 校验 `[源码实测]`

- **没有 `UsePathBase`、没有 `MapGroup`、没有路由前缀。** `GameServer.cs:252` 只有 `app.MapControllers();`
- **CORS**：`GameServer.cs:121-130` 只放行 `http://localhost:3000` 与 `https://tauri.localhost`（给 Tauri 控制台用），并在 `:253` `app.UseCors("ShittimGM");`。**对游戏客户端没有实际约束**（OkHttp/UnityWebRequest 不发 Origin）。
- **Host 校验**：`appsettings.json:9` `"AllowedHosts": "*"` —— **不限制**。
- **没有鉴权中间件**：`GameServer.cs:234` 只有 `app.UseAuthorization()`，**没有 `UseAuthentication`**，控制器上也没有 `[Authorize]`（`GatewayController` 只有 `[ApiController]`）。
  ⇒ **任何人只要能连上 5000/5100 端口就能直接发 gateway 请求**，认证完全靠协议内的 `SessionKey`。

---

## Q2. `Protocol` 枚举与信封格式

### 2.1 枚举定义位置 `[源码实测]`

`Schale/MX/NetworkProtocol/ProtocolData.cs:16-519`，`public enum Protocol : int`，**全文 1268 行**。

### 2.2 我们关心的成员（含全部 `Account_*` 与 `Queuing_*`）`[源码实测]`

```
Common_Cheat = -9999,  Error = -1,  None = 0,
System_Version = 1,  Session_Info = 2,  NetworkTime_Sync = 3,  NetworkTime_SyncReply = 4,
Audit_GachaStatistics = 5,

Account_Create                       = 1000
Account_Nickname                     = 1001
Account_Auth                         = 1002
Account_CurrencySync                 = 1003
Account_SetRepresentCharacterAndComment = 1004
Account_GetTutorial                  = 1005
Account_SetTutorial                  = 1006
Account_PassCheck                    = 1007
Account_VerifyForYostar              = 1008
Account_CheckYostar                  = 1009   ← 用 AuthTicket 换 SessionKey
Account_CallName                     = 1010
Account_BirthDay                     = 1011
Account_Auth2                        = 1012
Account_LinkReward                   = 1013
Account_CheckNexon                   = 1014   ← 国际服对应物
Account_DetachNexon                  = 1015
Account_ReportXignCodeCheater         = 1016
Account_DismissRepurchasablePopup     = 1017
Account_InvalidateToken               = 1018
Account_LoginSync                     = 1019
Account_VerifyCheckAdultAgree         = 1020
Account_SetCheckAdultAgree            = 1021
Account_Reset                         = 1022
Account_RequestBirthdayMail           = 1023
Account_CheckAccountLevelReward       = 1024
Account_ReceiveAccountLevelReward     = 1025

...
Queuing_GetTicket            = 50000
Queuing_GetCryptoKeys        = 50001   ← 网关会话密钥握手
Queuing_GetAuthTicket        = 50002   ← 拿 AuthTicket
Queuing_ProcessWaitingQueue  = 50003

Management_BannerList        = 100000
Management_ProtocolLockList  = 100001
```

### 2.3 信包结构 `[源码实测]`

`Schale/MX/NetworkProtocol/Packet.cs:6-62`（全文 62 行）

```csharp
public class SessionKey
{
    public long AccountServerId { get; set; }
    public required string MxToken { get; set; }
}

public abstract class BasePacket
{
    public SessionKey? SessionKey { get; set; }
    public abstract Protocol Protocol { get; }
    public long AccountId => SessionKey?.AccountServerId ?? 0;
}

public abstract class RequestPacket : BasePacket
{
    private static int _counter;
    public int ClientUpTime { get; set; }
    public bool Resendable { get; set; } = true;
    public long Hash { get; set; }
    public bool IsTest { get; set; }
    public DateTime? ModifiedServerTime__DebugOnly { get; set; }

    public static long CreateHash(Protocol protocol)
        => _counter++ | (((long)protocol) << 32);
}

public class ServerResponsePacket
{
    public required string Protocol { get; set; }
    public required string Packet { get; set; }
}

public abstract class ResponsePacket : BasePacket
{
    public long ServerTimeTicks { get; set; } = TruncateToSeconds(DateTimeOffset.Now.Ticks);
    public ServerNotificationFlag ServerNotification { get; set; } = ServerNotificationFlag.None;

    public static long TruncateToSeconds(long ticks) => ticks - (ticks % TimeSpan.TicksPerSecond);
    public List<MissionProgressDB>? MissionProgressDBs { get; set; }
    public Dictionary<long, List<MissionProgressDB>>? EventMissionProgressDBDict { get; set; }
    public Dictionary<OpenConditionContent, OpenConditionLockReason>? StaticOpenConditions { get; set; }
}
```

### 2.4 请求信封（`mx` 文件）—— **二进制，不是 JSON** `[源码实测]`

`GatewayController.cs:157-166` + `:360-373`

```csharp
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

⇒ **必须是 `multipart/form-data`，字段名 `mx`。** 我们之前实测「Shittim 期望 multipart 而不是 JSON」在源码里得到确认。

`mx` 文件字节布局 `GatewayController.cs:360-373`：

```
偏移  类型      字段
0     uint32    crc
4     int32     typeConversion
8     uint8     keyLength
9     uint8     ivLength
10    byte[keyLength]  headerKey
..    byte[ivLength]   headerIv
..    byte[]    rawPayload
```

`rawPayload` 的解码 `GatewayController.cs:462-493`：**XOR 0xD9 + GZip**，而且**会尝试三种长度前缀排布**（`RequestXorKey = { 0xD9 }`，见 `:107`）：

```csharp
private static List<GatewayDecodedPayload> DecodeGatewayPayloadBodies(byte[] rawPayload, List<string> failures)
{
    var decoded = new List<GatewayDecodedPayload>();

    // 变体 1：先整段 XOR，再把前 4 字节当 int32 长度
    var xorLengthPayload = (byte[])rawPayload.Clone();
    XOR.Crypt(xorLengthPayload, RequestXorKey);
    var xorExpectedLength = BitConverter.ToInt32(xorLengthPayload, 0);
    if (TryDecompressGZip(xorLengthPayload[4..], out var xorLengthPlain))
        decoded.Add(new GatewayDecodedPayload("xor-length-prefix", xorLengthPlain, xorExpectedLength));

    // 变体 2：前 4 字节明文当长度，剩下的再 XOR
    var clearExpectedLength = BitConverter.ToInt32(rawPayload, 0);
    var clearLengthCompressed = rawPayload[4..].ToArray();
    XOR.Crypt(clearLengthCompressed, RequestXorKey);
    if (TryDecompressGZip(clearLengthCompressed, out var clearLengthPlain))
        decoded.Add(new GatewayDecodedPayload("clear-length-prefix", clearLengthPlain, clearExpectedLength));

    // 变体 3：整段 XOR，无长度前缀
    var xorNoLengthPayload = (byte[])rawPayload.Clone();
    XOR.Crypt(xorNoLengthPayload, RequestXorKey);
    if (TryDecompressGZip(xorNoLengthPayload, out var xorNoLengthPlain))
        decoded.Add(new GatewayDecodedPayload("xor-no-length", xorNoLengthPlain, null));

    return decoded;
}
```

解出来的明文就是**协议 JSON**。协议号从 JSON 顶层字段读，**大小写都认** `GatewayController.cs:412-422`：

```csharp
var protocolNode = jsonNode["Protocol"] ?? jsonNode["protocol"];
if (protocolNode == null) return null;
if (protocolNode.Type == JTokenType.Integer) return (Protocol)protocolNode.Value<int>();
return Enum.TryParse<Protocol>(protocolNode.Value<string>(), out var protocol) ? (Protocol?)protocol : null;
```

⇒ 协议号可以是**整数**（`50002`）也可以是**枚举名字符串**（`"Queuing_GetAuthTicket"`）。

`:514` 的注释给出了客户端侧的完整写入格式（这是最准确的描述）：

> `PacketCryptManager.EncryptRequest writes [crc][typeConversion][keyLen][ivLen][aesEncryptedKey][aesEncryptedIV][gzip+XOR body], so headerKey/headerIv are the handshake blobs we handed out, not key material - 32 bytes each, since they wrap the base64 of a 16-byte key under PKCS7. Handshake requests (GetCryptoKeys/CheckNexon) send keyLen=0 and both directions stay plaintext.`

### 2.5 响应信封 `[源码实测]`

`GatewayController.cs:791-800`：

```csharp
private async Task CreateProtocolResponse(ServerResponsePacket packet, GatewayCryptoContext crypto)
{
    // The whole {protocol, packet} envelope goes inside the ciphertext, not around it. ...
    string json = JsonConvert.SerializeObject(packet, serverPacketSettings);   // camelCase
    if (ShouldUseAes(crypto))
        json = Convert.ToBase64String(HybridCryptor.EncryptGatewayResponse(Encoding.UTF8.GetBytes(json), crypto.Key, crypto.Iv));

    Response.ContentType = "application/json; charset=utf-8";
    await Response.WriteAsync(json);
}
```

- 序列化用 `CamelCasePropertyNamesContractResolver`（`:133-138`）⇒ 线上字段是 **`protocol` / `packet`** 小写开头。
- `ShouldUseAes` 条件（`:759-762`）：`crypto.UseAes && 合法 AES 长度 && IV 长度 == 16`。握手阶段 `UseAes = false`，响应是明文 JSON。
- **一旦进入会话，整个 `{protocol, packet}` 信封被 AES-CBC 加密后整体 base64**，不是在明文信封里再套一层密文。`:793` 的注释说明了原因：
  > `HttpGameSession.WaitForRequest` 协程（`0x180da2773`）把原始 `DownloadText` 交给 `HttpGameMessage.DecodeResponse`，后者先 base64 解码、AES 解密整个 body，然后才看 protocol 字段。

### 2.6 加密字段一览（握手响应里出现）`[源码实测]`

`GatewaySessionCrypto.cs:53-70`：

```csharp
var encryptedKey = HybridCryptor.EncryptTextAES(Encoding.UTF8.GetBytes(Convert.ToBase64String(serverKey)), clientKey, clientIv);
var encryptedIv  = HybridCryptor.EncryptTextAES(Encoding.UTF8.GetBytes(Convert.ToBase64String(serverIv)),  clientKey, clientIv);
...
SignBase64(encryptedKey), ... SignBase64(encryptedIv));
```

- `EncryptedKey` = `AES-CBC(base64(serverKey), clientKey, clientIv)`
- `SignedKey` = **`RSA-SHA1-PKCS1(SHA1)` 对 `EncryptedKey` 的密文字节签名**（`:227-240`）
  > `:62` 注释：客户端 `GameSessionManager.VerifyAndSetAesParameters` 会 base64 解码 `EncryptedKey`，直接送进 `HybridCryptor.VerifySignatureKeyAndIVWithRSA`，**从不解密它**，所以签名必须覆盖线上那串密文本身。
  > `:239` 注释：`SHA1` 是因为客户端就是这么验的（客户端那两个 `rsa.VerifyData` 都用 `HashAlgorithmName.SHA1`）。
- `EncryptedIV` / `SignedIV` 同理。
- 客户端侧发来的 `ClientGeneratedKey` / `ClientGeneratedIV`：**可能是 RSA 密文**，服务端用网关私钥解（`:90-125`，依次尝试 `OaepSHA256 / OaepSHA1 / Pkcs1 / OaepSHA384 / OaepSHA512`），解出的长度必须正好合法才接受。

---

## Q3. `Queuing_GetAuthTicket` 与 `Account_CheckYostar` 完整实现

### 3.1 DTO 定义 `[源码实测]`

`Schale/MX/NetworkProtocol/NetworkProtocol.cs:5836-5861`

```csharp
public class QueuingGetAuthTicketRequest : RequestPacket
{
    public override Protocol Protocol { get => Protocol.Queuing_GetAuthTicket; }
    public string? ClientGeneratedKey { get; set; }
    public string? ClientGeneratedIV { get; set; }
    public long YostarUID { get; set; }
    public string? YostarToken { get; set; }
    public bool PassCheck { get; set; }
    public bool MakeStandby { get; set; }
    public bool PassCheckYostar { get; set; }
    public string? ClientVersion { get; set; }
    public string? OSType { get; set; }
}

public class QueuingGetAuthTicketResponse : ResponsePacket
{
    public override Protocol Protocol { get => Protocol.Queuing_GetAuthTicket; }
    public string? EncryptedKey { get; set; }
    public string? SignedKey { get; set; }
    public string? EncryptedIV { get; set; }
    public string? SignedIV { get; set; }
    public string? EncryptedSqlCipherKey { get; set; }
    public string? EncryptedSqlCipherLicense { get; set; }
    public string? Birth { get; set; }
    public string? AuthTicket { get; set; }
}
```

`NetworkProtocol.cs:382-403`

```csharp
public class AccountCheckYostarRequest : RequestPacket
{
    public override Protocol Protocol { get => Protocol.Account_CheckYostar; }
    public long UID { get; set; }
    public string? EnterTicket { get; set; }
    public bool PassCookieResult { get; set; }
    public string? Cookie { get; set; }
    public string? ClientGeneratedKey { get; set; }
    public string? ClientGeneratedIV { get; set; }
}

public class AccountCheckYostarResponse : ResponsePacket
{
    public override Protocol Protocol { get => Protocol.Account_CheckYostar; }
    public int ResultState { get; set; }
    public string? ResultMessag { get; set; }     // ← 上游拼写就是 ResultMessag，少一个 e
    public string? Birth { get; set; }
    public string? EncryptedKey { get; set; }
    public string? SignedKey { get; set; }
    public string? EncryptedIV { get; set; }
    public string? SignedIV { get; set; }
}
```

### 3.2 `Queuing_GetAuthTicket` handler 原文 `[源码实测]`

`Shittim-Server/Core/NetworkProtocol/Handlers/QueuingHandler.cs:76-97`

```csharp
[ProtocolHandler(Protocol.Queuing_GetAuthTicket)]
public Task<QueuingGetAuthTicketResponse> GetAuthTicket(
    SchaleDataContext db,
    QueuingGetAuthTicketRequest request,
    QueuingGetAuthTicketResponse response)
{
    var gatewayCrypto = GatewaySessionCryptoBuilder.Build(request.ClientGeneratedKey, request.ClientGeneratedIV);
    var sqlCipher = BuildSqlCipherResponse(request.ClientGeneratedKey, request.ClientGeneratedIV);
    var rawTicketBytes = Encoding.UTF8.GetBytes($"{request.YostarUID}/{request.YostarToken}");

    response.EncryptedKey = gatewayCrypto.EncryptedKey;
    response.SignedKey  = gatewayCrypto.SignedKey;
    response.EncryptedIV = gatewayCrypto.EncryptedIV;
    response.SignedIV  = gatewayCrypto.SignedIV;
    response.EncryptedSqlCipherKey = sqlCipher.EncryptedKey;
    response.EncryptedSqlCipherLicense = sqlCipher.EncryptedLicense;
    response.Birth = "";
    response.AuthTicket = Convert.ToBase64String(rawTicketBytes);   // base64("<YostarUID>/<YostarToken>")
    response.ServerTimeTicks = 0;

    return Task.FromResult(response);
}
```

**要点**：
- `AuthTicket` = `base64( UTF8( "{YostarUID}/{YostarToken}" ) )` —— **无签名、无时间戳、无 nonce、无防重放**。
- 它**原样把客户端自己发来的 `YostarUID` / `YostarToken` 回吐**，没有做任何校验。
- `Birth = ""`，`ServerTimeTicks = 0`（`:64` 注释：队列类响应官方不带 `ServerTimeTicks`）。
- 同一文件 `:42-74` 的 `Queuing_GetTicket`（国际服走这条）也是同一套路：`EnterTicket = base64("{NpSN}/{NpToken}")`。

### 3.3 `Account_CheckYostar` handler 原文 `[源码实测]`

`Shittim-Server/Core/NetworkProtocol/Handlers/AccountHandler.cs:898-953`

```csharp
// the Yostar build's counterpart to CheckNexon; the Steam client never sends it, but our inface flow mints the same uid/token EnterTicket either way.
[ProtocolHandler(Protocol.Account_CheckYostar)]
public async Task<AccountCheckYostarResponse> CheckYostar(
    SchaleDataContext db,
    AccountCheckYostarRequest request,
    AccountCheckYostarResponse response)
{
    var ticketBytes = Convert.FromBase64String(request.EnterTicket);
    var ticketString = Encoding.UTF8.GetString(ticketBytes);
    var parts = ticketString.Split('/');

    var publisherId = long.Parse(parts[0]);
    var token = parts[1];

    var user = await db.UserAccounts
        .FirstOrDefaultAsync(u => u.NpSN == publisherId);

    if (user == null)
    {
        var newUser = new UserAccount
        {
            Uid = -1,
            NpSN = publisherId,
            NpToken = token
        };
        db.UserAccounts.Add(newUser);

        var newAccount = new AccountDBServer(publisherId);
        db.Accounts.Add(newAccount);

        await db.SaveChangesAsync();

        user = await db.UserAccounts.FirstAsync(u => u.NpSN == publisherId);
        var account = await db.Accounts.FirstAsync(a => a.PublisherAccountId == publisherId);

        user.Uid = account.ServerId;
        await AccountInitializationService.InitializeCompleteAccount(db, account);
        await db.SaveChangesAsync();
    }
    else if (user.NpToken != token)
    {
        user.NpToken = token;
        await db.SaveChangesAsync();
    }

    var sessionKey = await _sessionService.GenerateSession(publisherId);
    var gatewayCrypto = GatewaySessionCryptoBuilder.Build(request.ClientGeneratedKey, request.ClientGeneratedIV);

    response.ResultState = 1;
    response.SessionKey = sessionKey;
    response.EncryptedKey = gatewayCrypto.EncryptedKey;
    response.SignedKey  = gatewayCrypto.SignedKey;
    response.EncryptedIV = gatewayCrypto.EncryptedIV;
    response.SignedIV  = gatewayCrypto.SignedIV;
    return response;
}
```

**要点（逐条）**：

| 项 | 结论 |
|---|---|
| 请求字段 | `UID`(long)、`EnterTicket`(string, base64)、`PassCookieResult`(bool)、`Cookie`(string)、`ClientGeneratedKey/IV` |
| `EnterTicket` 解包 | `base64decode` → UTF-8 → `Split('/')` → `parts[0]` = publisherId(`long.Parse`)、`parts[1]` = token |
| **验签** | **没有。** 不验签、不验时间戳、不验 nonce、不查重放 |
| **token 校验** | **没有。** 只在 `user.NpToken != token` 时静默覆盖写回 |
| **自动建号** | **会。** 账号不存在时自动创建 `UserAccount` + `AccountDBServer` 并跑完整初始化 |
| 响应字段 | `ResultState`、`ResultMessag`(拼写如此)、`Birth`、`EncryptedKey/SignedKey/EncryptedIV/SignedIV`、`SessionKey` |
| `ResultState` 成功值 | **`1`**（`:946`） |
| 会话 | `_sessionService.GenerateSession(publisherId)` 生成 `SessionKey { AccountServerId, MxToken }` |
| `UID` 字段用途 | **handler 里完全没用到 `request.UID`**，只用 `EnterTicket` 里解出来的 publisherId |

### 3.4 `ResultState` 的取值语义 —— 只能给部分答案 `[源码实测 + 推断]`

**成功值确定是 `1`**（`:946` 唯一一处赋值）。失败值我没有找到 `Account_CheckYostar` 的失败分支——它不抛失败，全都走成功路径。

不过相关错误码在 `WebAPIErrorCode` 枚举里（`ProtocolData.cs:692-732`），可以说明「如果有失败会被归到哪一类」：

```
GatewayPassCheckNotSupport       = 901
GatewayWaitingTicketTimeOut      = 902
ClientUpdateRequire              = 903
YostarServerNotSuccessStatusCode = 1009
YostarNetworkException           = 1010
YostarException                  = 1011
YostarCheckFail                  = 1019
EnterTicketInvalid               = 1020
EnterTicketTimeOut               = 1021
EnterTicketUsed                  = 1022
InvalidSession                   = (见 GatewayController 用法)
```

⇒ `ResultState` 是**协议内部的业务状态**（0/1/其它），跟上面这套 HTTP 层 `WebAPIErrorCode` 是两套东西。`[推断]` `ResultState != 1` 时客户端会读 `ResultMessag` 弹框。

### 3.5 会话与鉴权 `[源码实测]`

`Shittim-Server/Services/SessionKeyService.cs:17-28` —— 免会话白名单：

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

⇒ **`Queuing_GetAuthTicket` 和 `Account_CheckYostar` 都在免会话名单里**，这也是它们能作为登录第一枪的原因。

`SessionKeyService.cs:30-33` 还有个实用设计：会话**持久化到磁盘**（`Config/sessions.json`），否则重启后客户端手里的 `MxToken` 失效，会表现为「Abnormal client」/「A request that cannot be processed」。

`GatewayController.cs:287-295` 对失效会话的处理值得抄：

```csharp
catch (UnauthorizedAccessException ex)
{
    // A dead or mismatched session must NOT surface as the generic 500
    // ("A request that cannot be processed"); InvalidSession triggers the client's clean return-to-title + relogin flow.
    await CreateProtocolErrorResponse(ex.Message, WebAPIErrorCode.InvalidSession, responseCrypto);
}
```

---

## Q4. 部署侧

### 4.1 端口 `[源码实测]`

`Shittim-Server/CLI/GameServer.cs:158-180`

```csharp
var apiPort     = ParsePort(Config.Instance.ServerConfiguration.HostPort,     5000, nameof(...HostPort));
var gatewayPort = ParsePort(Config.Instance.ServerConfiguration.GatewayPort,  5100, nameof(...GatewayPort));

builder.WebHost.ConfigureKestrel(options =>
{
    if (httpsCert != null)
    {
        options.Listen(System.Net.IPAddress.Any, 443, listenOptions => { listenOptions.UseHttps(httpsCert); });
        Console.WriteLine("HTTPS on port 443 for SDK endpoints");
    }
    options.Listen(System.Net.IPAddress.Any, apiPort);
    if (gatewayPort != apiPort)
        options.Listen(System.Net.IPAddress.Any, gatewayPort);
});
```

- **同一个 Kestrel 同时监听 5000（API）和 5100（Gateway）** —— 两个端口路由完全一样（`MapControllers` 只有一份），所以 `POST /api/gateway` 在 5000 和 5100 上**都能打**。
- **443 HTTPS 只在 `../../certs/selfsigned_cert.pem` + `selfsigned_key.pem` 存在时才开**（`:139-174`），用于 SDK/IAS 那些必须走 HTTPS 的端点。
- 我们实测「5000 和 5100 都监听」与此一致。

### 4.2 配置 `[源码实测]`

`Shittim-Server/appsettings.json`（全文 18 行）：

```json
{
  "Logging": { "LogLevel": { "Default": "Information", "Microsoft.AspNetCore": "Warning", "Microsoft.EntityFrameworkCore": "Warning" } },
  "AllowedHosts": "*",
  "ConnectionStrings": { "BAContext": "Data Source=BlueArchive.db" },
  "ServerConfiguration": {
    "VersionId": "b97c05ca58a24270",
    "UseCustomExcel": false,
    "DownloadExcelTables": true
  }
}
```

**`ServerConfiguration` 的完整可配项**在 `Shittim-Server/Configuration/ConfigType/ServerConfig.cs`（84 行）。与我们直接相关的：

| 键 | 默认值 | 说明（源码注释摘要） |
|---|---|---|
| `GameVersion` | `"1.90.439170"` | 队列里比对客户端版本用 |
| `AuthCurrentVersion` | `446690` | `Account_Auth.CurrentVersion` 上报值 |
| `HostAddress` | `"127.0.0.1"` | |
| `HostPort` | `"5000"` | API |
| `GatewayPort` | `"5100"` | Gateway |
| `EnableGateway` | `true` | |
| **`GatewayRsaPrivateKeyPem` / `Path`** | `""` | 网关 RSA 私钥 |
| **`GatewayRsaPublicKeyPem` / `Path`** | `""` | 网关 RSA 公钥（对应要注入客户端 metadata 的那把） |
| `ClientInstallDirectory` | `""` | 留空则自动找 Steam 库 |
| **`AutoPatchClientMetadata`** | **`true`** | **自动改客户端 `global-metadata.dat` 换 RSA 公钥** |
| `ClientMetadataPath` | `""` | |
| `AutoPatchClientSteamOffline` | `false` | 会改 `GameAssembly.dll` |
| `AutoPatchClientGamescaleIas` | `true` | |
| `ClientInfacePath` / `ClientInfaceConfigPath` / `ClientPluginDirectory` | `""` | 改 launcher 的 `NXI_DIRS` |
| `AutoPatchClientBanners` / `ClientExcelDbPath` | `true` / `""` | |
| `RegionDisplayText` | `""` | 标题界面区域名（客户端从自己 metadata 生成，不在线上传） |
| `SQLProvider` | `"SQLite3"` | |
| `SQLConnectionString` | `"Data Source=shittim.sqlite3"` | |
| `UseEncryption` | `false` | |
| **`BypassAuthentication`** | **`false`** | 旁路鉴权 |
| **`SelectedAccountId`** | **`0`** | **非 0 时，任何身份登录都直接答这个账号** |
| **`UseCustomExcel`** | **`false`** | 我们已知开这个会触发 `ResetDumped()` 删 316 MB 后崩，**保持 false** |
| `KoyukiIncident` | `false` | |
| `WorldRaidCoordinatorUrl` | `https://raid.shittem-server.com` | |
| `AutoCheckVersion` / `AutoUpdateVersion` / `AutoUpdateResources` | `true` | |
| `AdminApiKey` | `""` | 空 = 只允许 loopback 访问 admin |
| `ExcelDbSqlCipherKey` / `License` | 有默认值 | ExcelDB 的 SQLCipher 密钥 |
| `ServerInfoUrl` | cloudfront 的 `439170_Live_...json` | 国际服版本信息 |

`Shittim-Server/config/` 目录内容：

| 文件 | 大小 | 用途 |
|---|---|---|
| `GatewayPrivateKey.pem` | 3272 B | 网关 RSA 私钥（4096 位） |
| `GatewayPublicKey.pem` | 800 B | 网关 RSA 公钥 |
| `ba_version_cache.json` | 215 B | 见下 |

`ba_version_cache.json`：

```json
{ "VersionId": "6aa77ef8c06d45ef",
  "CdnBaseUrl": "https://ba.dn.nexoncdn.co.kr/com.nexon.bluearchive/6aa77ef8c06d45ef",
  "SourceBuildVersion": "1.93.452511",
  "LastUpdatedUtc": "2026-08-19T12:45:23.0363674Z" }
```

⇒ **默认拉的是国际服（Nexon）CDN**，`VersionId` 会指向 `com.nexon.bluearchive` 的资产。

### 4.3 账号会不会自动建 `[源码实测]`

**会。** `AccountHandler.cs:915-936`：`UserAccounts` 里查不到 `NpSN == publisherId` 就新建 `UserAccount` + `AccountDBServer` 并 `InitializeCompleteAccount`。

### 4.4 `UserAccounts` 表结构 `[源码实测]`

`Schale/Data/Models/UserAccount.cs`（全文 17 行）：

```csharp
public class UserAccount
{
    [Key] public long Id { get; set; }
    public long Uid { get; set; }
    public long NpSN { get; set; }        // ← 这里放的是 pubisherId（即 EnterTicket 的 parts[0]）
    public string? NpToken { get; set; }  // ← 放 token（parts[1]），不校验
}
```

注意：`Uid` 初始写 `-1`，随后被 `account.ServerId` 覆盖（`:933`）。**真正的账号 ID 在 `Accounts.ServerId`**，`UserAccounts` 只是 publisher 身份 → 本地账号的映射表。

### 4.5 数据库初始化链路 `[源码实测]`

`GameServer.cs:186-206`：
1. `context.Database.CanConnect()` → 否则 `EnsureCreated()`
2. `GetPendingMigrations().Any()` → `Migrate()`
3. **`SchemaReconciler.ReconcileAsync(context)`** —— 从 EF 模型反推表/列并自动补齐（`:199-201` 注释说明项目没有 migrations，靠它加列）
4. `AccountInitializationService.Initialize(excelService, parcelHandler)`

⇒ 换库/加字段不用手写 DDL，重启即可。

---

## Q5. 国服客户端兼容性

### 5.1 结论先说

**协议层：兼容。** 国服客户端用的 Yostar 系列协议号在枚举里齐全（`Account_VerifyForYostar = 1008`、`Account_CheckYostar = 1009`、`Billing_*ByYostar = 29000-29002`），而且源码里有一整套专门给"inface"客户端准备的补丁服务。

**真正的拦路虎：网关 RSA 公钥被编译进客户端 `global-metadata.dat`，服务端必须持有对应的私钥，或者改客户端的 metadata。** 这是本项目最硬的一道坎，见 5.3。

### 5.2 源码里关于国服/Yostar 的直接证据 `[源码实测]`

| 位置 | 原文 | 含义 |
|---|---|---|
| `AccountHandler.cs:898` | `// the Yostar build's counterpart to CheckNexon; the Steam client never sends it, but our inface flow mints the same uid/token EnterTicket either way.` | 作者明确区分了 **Steam（Nexon）** 与 **Yostar** 两套登录，并说自己的 "inface flow" 走的是同一套 uid/token |
| `GameServer.cs:102` | `builder.Services.AddHostedService<ClientInfaceConfigPatchService>();` | 有专门的 inface 客户端补丁服务 |
| `GameServer.cs:107` | `builder.Services.AddHostedService<ClientRegionLabelPatchService>();` | 有区域标签补丁 |
| `ServerConfig.cs:27-30` | `ClientInfacePath` / `AutoPatchClientInfaceConfig` / `ClientInfaceConfigPath` / `ClientPluginDirectory` | inface launcher 的配置路径、插件目录 |
| `ServerConfig.cs:37-38` | `RegionDisplayText` + 注释「Replaces the title-screen region label, which the client builds from its own metadata rather than from anything on the wire」 | **区域名不在线上传**，是客户端从自己 metadata 拼的 → 想改必须改客户端 |

`ClientInfaceConfigPatchService.cs:88-130` 干的事很具体：读 inface 的 launcher 配置 JSON，把 `NXI_DIRS` 数组改写成私有服的插件目录，停机时还原：

```csharp
currentJson["NXI_DIRS"] = new JsonArray(targetDirectory);
var patchedRaw = EncodeConfig(currentJson);
```

⇒ **这是 PC launcher 层面的改造，跟我们 Android 国服客户端不是同一条路。** 对我们有参考价值的是"思路"（改客户端配置/元数据），不是代码本身。

### 5.3 最硬的一道坎：`global-metadata.dat` 里的网关 RSA 公钥 `[源码实测]`

`Shittim-Server/Services/ClientMetadataPatchService.cs:10-33`：

```csharp
// The key is three separate string literals in the metadata rather than one run, and the split lands wherever
// the build's literal packing put it: 272/272/255 for the RSA-4096 key, and 150/150/150 for the RSA-2048 one it replaced.
private static readonly int[] ChunkLengths = [272, 272, 255];
private const int ChunkCount = 3;

// The official Nexon gateway RSA-4096 public key, exactly as it is embedded inside the client's global-metadata.dat.
// The client RSA-encrypts the 50001 gateway handshake with this key, so swapping in the private server's own key
// is what lets the gateway decode the handshake. Ours has to be 4096-bit as well: the chunks are fixed-size holes
// in fieldAndParameterDefaultValueData, and a PEM of any other length cannot go into them without shifting the
// section and every offset past it.
//
// The three byte runs are located by content (an AOB scan) rather than by fixed file offsets: the offsets move
// every time the client is rebuilt, and build 439170 shifted all three by +0x49B0.
// Writing at a stale offset corrupts whatever IL2CPP metadata now lives there and hangs the client at
// "Unpacking game resources". A scan also fails safe: a chunk that cannot be found means no write at all.
```

**这段注释把整条链路讲清楚了**：

1. 客户端把 `Queuing_GetCryptoKeys`（`50001`）的握手用**编译进 `global-metadata.dat` 的那把 RSA-4096 公钥**加密；
2. 所以服务端要么持有**对应私钥**（不可能，那是官方私钥），要么**把客户端里那把公钥换成自己的**；
3. 替换必须**等长**（4096 位对 4096 位），因为三个 chunk 是 `fieldAndParameterDefaultValueData` 里的**定长空洞**，PEM 长度一变就要挪段偏移；
4. 定位用 **AOB 扫描（按内容找）**，不能用固定偏移——每次客户端重编译都会挪（build 439170 整体挪了 `+0x49B0`）；
5. 改错位置的后果是**卡在「Unpacking game resources」**，而且屏幕上没有任何提示。

`:19-33` 给出了官方公钥 PEM 原文（RSA-4096，`MIICIjANBgkqhkiG9w0BAQEFAAOCAg8AMIiCCAgKCAgEAz1oODtVINPQsTIbFDiL2...`）。

**这对我们的直接含义**：
- 我们之前从 `global-metadata.dat` 里翻出过一段 PEM——**它的角色到这里彻底确认了：那是网关握手的 RSA 公钥，不是证书 pin**。
- 之前逆向结论说「CN 客户端的 metadata 头部被加密（magic `0x12724394` ≠ `0xFAB11BAF`）」——但 Shittim 的 AOB 扫描**只依赖字符串区明文**，而我们另一路逆向已经确认「字符串区完全明文，只有头部的索引/偏移表被混淆」。⇒ **AOB 换 PEM 这条路在 CN 客户端上大概率仍然可行，不需要先解密 metadata 头部。**
- 三个 chunk 长度 `272/272/255` 是**国际服 RSA-4096 的切分**。国服客户端的切分点**几乎肯定不同**，必须**按内容自己扫**，不能照抄这三个长度。`[推断，需实测]`

### 5.4 国服客户端与国际服的协议差异 `[源码实测 + 推断]`

**源码里没有任何 region/version 分支影响协议结构。** 我全文检索 `Region`，只命中两处：`ClientRegionLabelPatchService`（改标题界面文字）和 `ServerConfig.RegionDisplayText`（同一个东西）。`GatewayController` 里没有任何 `if (region == ...)` 之类的判断。

差异体现在**走哪条登录协议**：

| | 国际服（Steam/Nexon） | 国服（Yostar） |
|---|---|---|
| 队列握手 | `Queuing_GetTicket`(50000) | `Queuing_GetAuthTicket`(50002) `[推断]` |
| 凭证字段 | `NpSN`(long) + `NpToken` | `YostarUID`(long) + `YostarToken` |
| EnterTicket | `base64("{NpSN}/{NpToken}")` | `base64("{YostarUID}/{YostarToken}")` |
| 登录协议号 | `Account_CheckNexon`(1014) | `Account_CheckYostar`(1009) `[推断]` |
| 反作弊 | Nexon Game Security（`ServerSeed` 那 1 KB） | 腾讯 ACE |

`QueuingHandler.cs:65` 注释：`ServerSeed` 保持空串，因为「官方那 1 KB seed 只喂 Nexon Game Security，本服务端有意绕过」。

**`[推断]` 的标注说明**：源码没有明确写"国服走 50002 + 1009"，但从三处可以推出来：① `AccountHandler.cs:898` 说 Yostar 版对应 CheckNexon；② `QueuingGetAuthTicketRequest` 的字段就是 `YostarUID`/`YostarToken`；③ `Queuing_GetAuthTicket` 生成的 `EnterTicket` 格式与 `CheckYostar` 解包的格式**完全一致**（都是 `uid/token`）。这条链是自洽的，但没有实机抓包佐证。

### 5.5 GitHub 上有没有人用它接过国服 `[读不到]`

我没有拿到 issue / discussion 内容（需要额外 API 分页抓取，本轮未做）。**这一项标注为未完成**，不能凭感觉回答。

已知的间接信号：
- 仓库 description 明确写 `Blue Archive Private Server For Steam`，README 也只讲 Steam。
- 但源码里 `inface` / Yostar 的痕迹是**作者自己写进去的**，不是第三方 PR 痕迹（`AccountHandler.cs:898` 用的是第一人称 "our inface flow"）。
- ⇒ **作者本人至少试过 Yostar 版客户端**，但官方支持范围仍以 Steam 为准。`[推断]`

---

## 6. 给我们的可执行清单

目标：让国服客户端走通 `Queuing_GetAuthTicket`(50002) → `Account_CheckYostar`(1009)。

### 6.1 nginx 侧（我们的 MITM，改成打到 Shittim 的 5000）

**关键：路径必须原样透传，不能加前缀。** 客户端请求的就是 `/api/gateway`。

```nginx
# gsqc-api / gs-api 的 vhost 里
client_max_body_size 32m;                 # mx 是二进制文件，别卡在 1m 默认值

location / {
    proxy_pass http://127.0.0.1:5000;     # 原样转发，不要 rewrite 掉 /api
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $remote_addr;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_request_buffering on;           # multipart 要缓冲完整
    proxy_read_timeout 300s;
}
```

**必须确认的三件事**：
1. `POST /api/gateway` 打到 5000 后**返回 400 "Expecting an mx file"** ⇒ 说明路由通了、只是 body 不对，这是对的方向；如果返回 404 ⇒ 请求没到 Shittim 或 Shittim 没起。
2. `GET /api/gateway` 返回 **200 空 body** ⇒ 健康检查通了。
3. `GET /api/Queuing/Ping` 返回 `"Pong"` ⇒ 路由前缀确认正确。

**`/api/state` 不要指望 Shittim 提供**——它没有这个动作。我们继续用 nginx 静态合成（当前已实现，`state-api` 130 B / `gsqc-api` 838 B）。**注意：`gsqc-api` 的 `/api/state` 要保留 nginx 的 `location = /api/state` 精确匹配，其它路径才走 `location /` 到 5000。**

### 6.2 Shittim 配置侧（`appsettings.json` 的 `ServerConfiguration`）

```jsonc
"ServerConfiguration": {
  "VersionId": "b97c05ca58a24270",      // 保持默认，或对齐我们自己的资产版本
  "UseCustomExcel": false,               // ← 绝对保持 false（开它会 ResetDumped 删 316MB 后崩）
  "DownloadExcelTables": true,

  "HostPort": "5000",
  "GatewayPort": "5100",
  "EnableGateway": true,

  // 关键：换成我们自己的 RSA-4096 密钥对，两边都要
  "GatewayRsaPrivateKeyPath": "/www/wwwroot/bapatch/shittim/gateway_private.pem",
  "GatewayRsaPublicKeyPath":  "/www/wwwroot/bapatch/shittim/gateway_public.pem",

  // 客户端自动补丁在 Linux 服务器上全部关掉（它找的是 Steam 安装目录，我们改的是手机上的 APK）
  "AutoPatchClientMetadata": false,
  "AutoPatchClientSteamOffline": false,
  "AutoPatchClientGamescaleIas": false,
  "AutoPatchClientInfaceConfig": false,
  "AutoPatchClientBanners": false,
  "AutoPatchClientStoreUrl": false,
  "AutoManageGrap64": false,

  // 登录旁路：先用这两个把流程跑通，再决定要不要真校验
  "BypassAuthentication": false,
  "SelectedAccountId": 0,

  "AutoCheckVersion": false,             // 别去拉 Nexon 的版本
  "AutoUpdateVersion": false,
  "AutoUpdateResources": false
}
```

**`AutoPatchClientMetadata` 必须在服务端关掉**：`GameServer.cs` 把它们注册成 `IHostedService`，`ServerConfig.cs:18-19` 注释说它会去 Steam 库里找客户端。在 Linux 上它找不到会打 warning 然后跳过（`ClientInfaceConfigPatchService.cs:46-50` 的 `File.Exists` 分支），但**关掉更干净**，也避免它在未来某个版本里做出意外写入。

**密钥对生成**（4096 位，PEM，两把都要给 Shittim）：

```bash
mkdir -p /www/wwwroot/bapatch/shittim && cd /www/wwwroot/bapatch/shittim
openssl genrsa -out gateway_private.pem 4096
openssl rsa -in gateway_private.pem -pubout -out gateway_public.pem
openssl rsa -in gateway_private.pem -noout -text | head -2   # 确认 4096 bit
wc -c gateway_private.pem gateway_public.pem                 # 私钥 ~3272B、公钥 ~800B（对照上游 config/ 的两个文件大小）
```

### 6.3 客户端侧：唯一必须做的一件"侵入性"工作

**把国服 APK 的 `global-metadata.dat` 里那把官方网关 RSA-4096 公钥，换成长度完全相同的我们的公钥。**

流程（照抄 Shittim 的做法，但**参数必须自己重新测**）：

1. 从 APK 取 `assets/bin/Data/Managed/Metadata/global-metadata.dat`（我们已从手机拿到：38,426,024 B，sha256 `2352cb57…`）
2. 把我们的 `gateway_public.pem`（800 B 含 BEGIN/END）**按客户端的字符串切分规则拆成 3 段**
   - `[推断]` 上游是 `272/272/255` = 799 B（PEM 去换行）三段切分。**国服的切分点必须实测**——做法是：先在 metadata 里 AOB 搜索官方公钥的 PEM 文本，看它被切成几段、每段多少字节
3. 用 AOB 扫描定位这三段（**不要用固定偏移**，每次重编译都会挪）
4. 原地等长覆盖
5. 重新打包进 APK，签名，装到手机

**风险与判据**：
- 换错位置 ⇒ **卡在「Unpacking game resources」**，屏幕上没有任何提示（这是上游注释里明确记录的失败形态）
- **ACE 是否会因为 metadata 被改而杀进程：未知。** 我们已实测 `libunity.so` 被磁盘哈希钉死（改 4 字节即 SIGBUS），但 `libil2cpp.so` 改 5 字节能跑。`global-metadata.dat` 属于**资源文件**，不在 `.so` 哈希范围内——`[推断]` 大概率安全，但**必须实测**。
- 回滚：保留原始 metadata（我们有 sha256 `2352cb57…`），随时还原。

### 6.4 我们的 SDK 签发端要输出什么

**给定结论：Shittim 的 `Account_CheckYostar` 什么都不要，只要两段字符串恰好像 `uid/token`。**

我们的卡密 SDK（`sdkcard.py` / `example.com/sdk`）现在签发的：

```json
"User": { "ID": 314816420, "PID": "CN-BA", "State": 1,
          "Token": "61de1d1b7519ab1231866f74c11fcfdd1f80b210" }
```

**直接可用，不需要改格式。** 因为：
- `uid` = `314816420`（9 位数字）→ 满足 `long.Parse(parts[0])`
- `token` = `61de1d1b…`（40 位 hex）→ `parts[1]` 随便什么字符串都行，**不校验**

**唯一要保证的是**：客户端最终发给 `Account_CheckYostar` 的 `EnterTicket` 必须是 `base64("314816420/61de1d1b7519ab1231866f74c11fcfdd1f80b210")`。

而 `EnterTicket` 是 `Queuing_GetAuthTicket` 的响应的 `AuthTicket` 字段原样回吐的——**也就是说这个 base64 串由 Shittim 自己生成，我们只要保证客户端发给 `Queuing_GetAuthTicket` 的 `YostarUID`/`YostarToken` 正确即可**。

`YostarUID` / `YostarToken` 从哪来？`[推断]` 由客户端的 Yostar SDK 登录后填进请求，也就是**我们魔改 SDK 下发的 `User.ID` 和 `User.Token`**。这条链是：
```
我们的 SDK → (ID, Token) → 客户端 → Queuing_GetAuthTicket{YostarUID, YostarToken}
   → Shittim 回 AuthTicket = base64("{ID}/{Token}")
   → 客户端 → Account_CheckYostar{EnterTicket}
   → Shittim 自动建号 + 发 SessionKey → 进入游戏
```

**验证这个 `[推断]` 的方法**：抓 `Queuing_GetAuthTicket` 的请求体，看 `YostarUID` 是不是 `314816420`。如果不是，说明中间还有一层映射需要补。

### 6.5 顺序建议（按代价从低到高）

| # | 动作 | 代价 | 验证方式 |
|---|---|---|---|
| 1 | 在服务器上 `curl http://127.0.0.1:5000/api/Queuing/Ping` | 1 分钟 | 回 `Pong` |
| 2 | `curl -X POST http://127.0.0.1:5000/api/gateway` | 1 分钟 | 回 400 `Expecting an mx file` |
| 3 | nginx 把 `gsqc-api` 的 `location /` 指到 5000（保留 `/api/state` 精确匹配） | 5 分钟 | 手机打 `gsqc-api` 出现 400，`ba_raw.log` 有记录 |
| 4 | 手机跑一轮，抓 `Queuing_GetAuthTicket` 的**完整请求体** | 10 分钟 | 看到 `YostarUID`/`YostarToken` 的实际值 |
| 5 | 根据第 4 步的实际值，决定改 Shittim 还是改我们的 SDK | 视情况 | — |
| 6 | 处理 `global-metadata.dat` 的 RSA 公钥替换（这是**唯一无法绕过**的硬活） | 大 | 卡「Unpacking game resources」= 位置改错 |

**第 6 步之前，1–5 步可以先做**，因为握手加密只影响 `Queuing_GetCryptoKeys` / `Account_CheckYostar` 的 `ClientGeneratedKey/IV` 解密，**不通过时会表现为服务端解不出 key**（`DecodeClientCrypto` 失败 → `EncryptedKey` 等字段为空），而不是路由 404。所以能先验证路由和协议链路。

---

## 7. 与本项目既有结论的差异（需要修正的）

| 既有结论 | 源码事实 | 处置 |
|---|---|---|
| 「Shittim 路由模板 `api/{path1}/{path2}` 要求三段，`/api/state` 两段所以 404」 | **错。** 路由前缀 `api` + 动作 `gateway` = 2 段，`POST /api/gateway` 完全合法。没有 `{path1}` 这种模板；`/api/state` 404 是因为**没有 state 这个动作** | 修正报告 `09-服务器盘点.md` 与相关决策记录 |
| 「`global-metadata.dat` 里那段 PEM 是证书 pin / 网关 RSA 握手键（未定论）」 | **定论：它既不是证书 pin，也不是普通握手键——它是客户端用来 RSA 加密 `50001` 握手 key/IV 的公钥，服务端必须持有对应私钥** | 更新 `15-PEM公钥与pinning判读.md` |
| 「Shittim 只管游戏网关，不管 state」 | **对**，源码确认无 `state` 动作 | 保持不变 |
| 「`/api/state` 必须由 nginx 合成」 | **对** | 保持不变 |

---

## 8. 我没拿到 / 读不到的部分（诚实标注）

| 项 | 状态 | 卡在哪 |
|---|---|---|
| GitHub issue / discussion 里有没有人接过国服 | **未做** | 需要额外分页抓 `/issues`、`/discussions`，本轮未抓 |
| `ResultState` 的完整取值表（0/1/2 各代表什么） | **只确定 1 = 成功** | 源码里 `Account_CheckYostar` 只有成功路径；其余取值要从客户端逆向或抓包确定 |
| 国服客户端 `global-metadata.dat` 里 PEM 的实际切分长度 | **未测** | 需要在 38 MB 的 metadata 里 AOB 扫官方 PEM 文本，本轮未做 |
| 国服客户端的 `YostarUID`/`YostarToken` 是否真的等于我们 SDK 下发的 `User.ID`/`User.Token` | **推断，未验证** | 需要抓 `Queuing_GetAuthTicket` 请求体 |
| ACE 是否会因 `global-metadata.dat` 被修改而杀进程 | **未知** | 只能实测 |
| `IasController` / `SDK` 目录下的 SDK 端点 | **未读** | 与主线（gateway）关系不大，本轮跳过 |
| `AdminController` / `GM` / `Dev` 控制器 | **未读** | 同上 |

---

## 附录 A：本地文件清单

`report\_tmp\shittim\src\` 下已解码的源码（全部来自 `main` @ `5f3910e`）：

| 文件 | 字节 | 行数 |
|---|---|---|
| `Shittim-Server__Controllers__Api__GatewayController.cs` | 38,566 | 803 |
| `Shittim-Server__Controllers__Api__ServerInfoController.cs` | 2,701 | 70 |
| `Shittim-Server__Core__NetworkProtocol__Handlers__AccountHandler.cs` | 48,829 | 1,057 |
| `Shittim-Server__Core__NetworkProtocol__Handlers__QueuingHandler.cs` | 7,810 | 185 |
| `Shittim-Server__Core__GatewaySessionCrypto.cs` | 16,051 | 395 |
| `Shittim-Server__Core__ProtocolHandlerRegistry.cs` | 6,626 | 183 |
| `Shittim-Server__Core__ProtocolHandlerAttribute.cs` | 389 | 16 |
| `Shittim-Server__Core__ProtocolHandlerBase.cs` | 159 | 9 |
| `Shittim-Server__CLI__GameServer.cs` | ~13,693 | 276 |
| `Shittim-Server__CLI__Arguments.cs` | 294 | 14 |
| `Shittim-Server__Configuration__Config.cs` | 10,715 | — |
| `Shittim-Server__Configuration__ConfigResources.cs` | 8,149 | — |
| `Shittim-Server__Configuration__ConfigType__ServerConfig.cs` | 6,227 | 84 |
| `Shittim-Server__Configuration__ConfigType__ServerInfoConfig.cs` | 654 | — |
| `Shittim-Server__Services__ClientMetadataPatchService.cs` | 18,931 | 434 |
| `Shittim-Server__Services__ClientInfaceConfigPatchService.cs` | 11,925 | 321 |
| `Shittim-Server__Services__ClientRegionLabelPatchService.cs` | 11,859 | — |
| `Shittim-Server__Services__SessionKeyService.cs` | 7,606 | 206 |
| `Shittim-Server__appsettings.json` | 398 | 18 |
| `Shittim-Server__config__ba_version_cache.json` | 215 | — |
| `Schale__MX__NetworkProtocol__NetworkProtocol.cs` | 284,761 | 7,181 |
| `Schale__MX__NetworkProtocol__ProtocolData.cs` | 49,615 | 1,269 |
| `Schale__MX__NetworkProtocol__Packet.cs` | 2,358 | 62 |
| `Schale__Data__Models__UserAccount.cs` | 322 | 17 |
| `README.md` | 1,864 | 32 |

## 附录 B：复现命令

```powershell
# 取单个文件的原始内容（GitHub Contents API 返回 base64）
curl.exe -sS -L -H 'User-Agent: dsh-research' `
  -o out.json -w '%{http_code}' `
  'https://api.github.com/repos/Neoexm/Shittim-Server/contents/Shittim-Server/Program.cs?ref=main'
```

```python
# 解码
import json, base64
j = json.load(open("out.json", encoding="utf-8"))
open(j["path"].replace("/", "__"), "wb").write(base64.b64decode(j["content"]))
```

注：本机 `git clone` 失败（`RPC failed; curl 56 Recv failure: Connection was reset`），`raw.githubusercontent.com` 与 jsDelivr 均不可达，**只有 `api.github.com` 通**，所以全部改走 Contents API。
