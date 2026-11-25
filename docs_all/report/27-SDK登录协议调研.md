# 27 — 碧蓝档案国服 SDK 登录协议调研（TapSDK / Airi 聚合 SDK / Yostar 认证 / 网关）

> 产出时间：2026-11-14
> 任务性质：纯调研 + 静态分析。**未修改任何文件、未连服务器、未碰手机。**
> 依据等级标注：**[实测]** = 本次从本地 APK / 上游源码读到的原文；**[官方文档]** = 厂商文档；**[推断]** = 由命名/结构推出的合理结论，需实测验证；**[未知]** = 查不到，不编。

---

## 一、一页摘要

### 1.1 结论先行

用户设想的方案（"魔改 SDK 服务端直接发 token 给游戏"）**架构上是成立的，而且比想象的更好办**，因为：

> **国服客户端的 SDK 层（Airi 聚合 SDK）把登录服务端地址写在 `assets/SDKConfigSettings.json` 的 `sdk_url` 里，而这个值已经被我们改成自己的服务器。也就是说：登录 token 的签发端本来就在我们手里。**

游戏侧（Shittim-Server）也**已经实现了接收这个 token 的握手**（`Protocol.Account_CheckYostar` / `Protocol.Queuing_GetAuthTicket`），它不校验 token 真假，只是把 `base64("uid/token")` 解开当账号 ID 用。

**⇒ 所以整条链的两端都在我们控制之下，中间只差"把两边的格式对上"。**

### 1.2 完整登录链路

```
┌─────────────────────────── 客户端 ───────────────────────────┐
│                                                              │
│  [TapSDK 4.6.3]                [Airi 聚合 SDK]               │
│   accounts.taptap.cn/authorize  com.airi.core.AiriSdkManager │
│   tapsdk.tapapis.cn             │                            │
│   gid.tapapis.cn                │ 读 assets/SDKConfigSettings.json
│        │                        │   → sdk_url = <我们>        │
│        │ AccessToken            │                            │
│        └────────────────────────┤                            │
│                                 ▼                            │
│                    POST {sdk_url}/auth/v1/login-by-token     │
│                    POST {sdk_url}/auth/v1/login-by-authorization-code
│                    GET  {sdk_url}/account/v1/profile         │
│                                 │                            │
│                                 ▼  uid + token                │
│                    [TechSDK 桥接] com.tech.sdk.TechSDK        │
│                                 │                            │
│                                 ▼                            │
│                    C# 层: yostarUid / yostarToken             │
│                                 │                            │
│                    ┌────────────┴─────────────┐              │
│                    ▼                          ▼              │
│      POST {ApiUrl}gateway            GET {ApiUrl}state        │
│      Protocol.Queuing_GetAuthTicket  (24 字段 DTO)            │
│      Protocol.Account_CheckYostar    ← 顺带拿 RSA 公钥/加解密 │
│                                                              │
└──────────────────────────────┬───────────────────────────────┘
                               ▼
                     ┌───────────────────┐
                     │  Shittim-Server   │  POST /api/gateway
                     │  已实现上述两个     │  Protocol 信封
                     │  ProtocolHandler  │
                     └───────────────────┘
```

### 1.3 三个关键判断

| # | 判断 | 依据等级 |
|---|---|---|
| 1 | 国服 SDK 是 **Airi 聚合 SDK + TapSDK + TechSDK 三层**，不是纯 TapSDK | **[实测]** dex 类名 + manifest 组件 |
| 2 | 登录服务端地址由 `SDKConfigSettings.json` 的 `sdk_url` 决定，**该文件在 assets 里，可改** | **[实测]** dex 类 `com.airi.common.services.SDKConfigManager` / `SDKConfigSettings$*`；任务背景已确认该值被改为我们的中继 |
| 3 | 游戏把 SDK 给的 uid/token **通过网关的 `Account_CheckYostar` 上传**，EnterTicket = `base64("uid/token")`，服务端不验签 | **[实测]** Shittim 源码 |

---

## 二、端点清单

### 2.1 协议分层（**必须先看懂这一节，否则会找错方向**）

国服客户端对服务端的请求分成**三个完全不同的平面**：

| 平面 | 端点 | 形态 | 承载什么 |
|---|---|---|---|
| **A. SDK 登录面** | `{sdk_url}/auth/v1/*`、`/account/v1/*`、`/app/v1/*` 等 | 普通 REST，JSON | **签发 uid + token** |
| **B. 配置面** | `{检测域名}/api/state` | GET，返回 24 字段 DTO | ApiUrls、版本、CDN 地址 |
| **C. 游戏网关面** | `POST /api/gateway` | **单一端点 + Protocol 数字信封**（可压缩/加密） | 一切游戏操作，含登录握手 |

⚠️ **最容易踩的坑**：`Account_CheckYostar` **不是 URL 路径**，是 `POST /api/gateway` 信封里的**协议号**。别去拼 `/api/Account/CheckYostar`。

**[实测]** Shittim `docs/docs/server/protocol.md` 原文：
> "The client sends everything through one endpoint, `POST /api/gateway` on the gateway port. The body is a protocol envelope: a protocol number and a JSON payload, optionally compressed and encrypted."

### 2.2 A 面：SDK 登录相关端点

全部来自 `classes2.dex @0x0025F8B8` 的一张**路径字面量表**（**[实测]**，原文照抄）：

```
/account/v1/profile
/agcgw/backurl
/agcgw/url
/agcgw_all/CN          /agcgw_all/CN_back
/agcgw_all/DE          /agcgw_all/DE_back
/agcgw_all/RU          /agcgw_all/RU_back
/agcgw_all/SG          /agcgw_all/SG_back
/api
/app/v1/get-latest
/app/v1/get-uri-by-identifier
/auth/v1/login-by-authorization-code
/auth/v1/login-by-token
/device/v1/query
/deviceprofile/v4
/friend-lite/v1/fans-by-me
/friend-lite/v1/following-by-me
/friend-lite/v1/list-by-me
/friend-lite/v1/sync
/friend/v1/list-by-me
/friendship/v1/create
/friendship/v1/delete
/message/v1/share
/oaid/query
/oaid_scp/get
/sdk-core/v1/gatekeeper
/v3/cloudconf
/unicomAuth/android/v3.0/qc?
/unisdk/rs/scripAndTokenForHttps
/log/logReport
```

| 主机/路径 | 方法 | 用途 | 依据 |
|---|---|---|---|
| `{sdk_url}/auth/v1/login-by-token` | POST | **用第三方 token 换游戏 uid/token** ← 核心 | **[实测]** 路径字面量 | **[推断]** 语义（命名直白） |
| `{sdk_url}/auth/v1/login-by-authorization-code` | POST | 用授权码换 token（扫码/TapTap 授权码流） | **[实测]** 路径 / **[推断]** 语义 |
| `{sdk_url}/account/v1/profile` | GET | 取账号资料（uid、昵称、token） | **[实测]** 路径 |
| `{sdk_url}/app/v1/get-latest` | GET | 版本检查 | **[实测]** 路径 |
| `{sdk_url}/app/v1/get-uri-by-identifier` | GET | 按标识取 URI（域名/资源调度） | **[实测]** 路径 |
| `{sdk_url}/sdk-core/v1/gatekeeper` | GET | SDK 网关配置（GateKeeper）| **[实测]** 路径 |
| `{sdk_url}/v3/cloudconf` | GET | 云端配置 | **[实测]** 路径 |
| `{sdk_url}/agcgw/url`、`/agcgw/backurl` | GET | **聚合网关地址选择**（含 CN/DE/RU/SG 分区与 backurl） | **[实测]** 路径 |
| `{sdk_url}/device/v1/query`、`/oaid/query`、`/oaid_scp/get` | POST | 设备指纹 / OAID | **[实测]** 路径 |
| `{sdk_url}/log/logReport` | POST | 日志上报 | **[实测]** 路径 |

**Airi 聚合 SDK 的类结构 [实测]**（`classes2.dex` 0x0069A88E 附近）：
```
com.airi.common.model.params.SDKConfigSettings
  ├── SDKConfigSettings$Auto_url
  ├── SDKConfigSettings$Init
  ├── SDKConfigSettings$Internet_detection      ← 对应我们已见到的 detection_address
  └── SDKConfigSettings$Log
com.airi.common.services.SDKConfigManager
com.airi.core.AiriSdkManager
com.airi.core.data.net.http.ApiService / SignProvider / ErrorHandler
com.airi.official.core.http.net.ErrorCodeInfo
```

⇒ **`SDKConfigSettings` 里就是 `sdk_url` 的家。** 这跟既有事实（`assets/SDKConfigSettings.json` 的 `sdk_url` 被指向 `127.0.0.1:8080` → 中继到 `example.com/sdk`）完全吻合。

### 2.3 TapSDK 相关端点（客户端内嵌 TapSDK **4.6.3**）

**[实测]** `classes2.dex` 里 `TapSDK-Android/4.6.3` 与 `com.taptap.sdk.*` 类名；**dex 里的完整 URL 字面量只有这几个**：

| URL | 用途 | 依据 |
|---|---|---|
| `https://accounts.taptap.cn/authorize` | TapTap OAuth 授权页（CN） | **[实测]** |
| `https://accounts-io.xdrnd.com/authorize` | 海外/IO 授权页 | **[实测]** |
| `https://accounts.xdrnd.cn/authorize` | 备用授权页 | **[实测]** |
| `https://www.taptapauth.com/authorize` | 授权 |
| `https://tapsdk.tapapis.cn` / `https://tapsdk.tapapis.com` | TapSDK 主 API | **[实测]** |
| `https://gid.tapapis.cn` / `https://gid.tapapis.com` | GID（游客/设备 ID）服务 | **[实测]** |
| `https://e.tapdb.net` / `https://e.tapdb.ap-sg.tapapis.com` | TapDB 埋点 | **[实测]** |
| `https://tapsdk.api.xdrnd.cn` / `.com` | TapSDK 备用 API | **[实测]** |

**TapTap 侧的关键机制 [官方文档]**（[TapTap OAuth 接口](https://developer.taptap.cn/docs/en/v3/sdk/taptap-login/guide/taptap-oauth/)）：

- SDK 拿到的 **AccessToken 是 MAC Token**，字段为：
  `kid` / `token_type` / `mac_key` / `mac_algorithm`（`hmac-sha-1`）/ `scopeSet`
- **AccessToken 不直接是游戏账号**。它要**上传给游戏服务端**，由服务端做 MAC 签算，再调：
  - `https://open.tapapis.cn/account/basic-info/v1?client_id=<CID>` → `openid` / `unionid`
  - `https://open.tapapis.cn/account/profile/v1?client_id=<CID>` → 再加 `name` / `avatar`
- 请求头形如：
  `Authorization: MAC id="<kid>",ts="<unix>",nonce="<随机>",mac="<base64 hmac-sha1>"`
- 错误码：`invalid_request` / `invalid_time` / `invalid_client` / `access_denied` / `forbidden` / `not_found` / `server_error` / `insufficient_scope`
- **单个 AccessToken 最长有效期 30 天**；SDK 每次启动自动刷新。

⚠️ **本客户端可见的 `tapsdk.tapapis.cn` / `gid.tapapis.cn` 都是"SDK 自己的服务"（埋点、设备 ID、更新），不是游戏账号签发端。** 游戏账号签发端是 Airi SDK 指向的 `sdk_url`。

### 2.4 B 面：配置端点（我们已经实现）

| 主机 | 路径 | 返回 | 依据 |
|---|---|---|---|
| `state-api` / `stateqc-api` | `/api/state` | `{"Servers":[...],"State":int,"Msg":string}` | **[实测]** 真实上游 + 元数据 |
| `gsqc-api` / `gs-api` | `/api/state` | 24 字段 `ServerInfoConnectionGroupData` | **[实测]** 元数据逆向（已实测过 838 B 应答） |

### 2.5 C 面：网关端点与登录协议

**[实测]** Shittim 源码 `docs/docs/server/protocol.md`：
> - 唯一入口 `POST /api/gateway`，body 是「协议号 + JSON payload」信封，可压缩/加密
> - **第一次交换 `Account_CheckNexon`（50001）是 RSA**：「The server's public key has been patched into the client's global-metadata.dat in three 150-byte chunks, and the server decrypts with `Config/GatewayPrivateKey.pem`」
> - 握手后会话带 AES key；**实测这个客户端 in-session key 实际为 null，响应走明文**
> - 序列化用 Newtonsoft；日期 `YYYY-MM-DDTHH:mm:ss`（无时区、整秒）；整数值浮点不带小数点；**向量必须带 x/y/z 三个分量**，缺一个客户端会**静默吞掉整个响应**

#### 登录相关 Protocol（**[实测]** 完整请求/响应类定义）

```csharp
// ===== 上传 token 的那一步 =====
public class AccountCheckYostarRequest : RequestPacket {
    public long    UID              { get; set; }   // SDK 给的 uid
    public string? EnterTicket      { get; set; }   // base64("uid/token")
    public bool    PassCookieResult { get; set; }
    public string? Cookie           { get; set; }
    public string? ClientGeneratedKey { get; set; } // 客户端生成的 AES key
    public string? ClientGeneratedIV  { get; set; }
}
public class AccountCheckYostarResponse : ResponsePacket {
    public int     ResultState  { get; set; }   // 服务端置 1
    public string? ResultMessag { get; set; }   // 注意原文拼写是 ResultMessag
    public string? Birth        { get; set; }
    public string? EncryptedKey { get; set; }   // RSA 加密的 AES key
    public string? SignedKey    { get; set; }
    public string? EncryptedIV  { get; set; }
    public string? SignedIV     { get; set; }
}

// ===== 排队/取票那一步 =====
Queuing_GetTicket      : Request{NpSN:long, NpToken:string}       → Response{EnterTicket, TicketSequence, AllowedSequence, RequiredSecondsPerUser, Birth, ServerSeed}
Queuing_GetAuthTicket  : Request{YostarUID, YostarToken}          → Response{AuthTicket, EncryptedKey/SignedKey/EncryptedIV/SignedIV, EncryptedSqlCipherKey, EncryptedSqlCipherLicense, Birth}
Queuing_GetCryptoKeys  : Request{ClientGeneratedKey, ClientGeneratedIV} → Response{同上四个加密字段 + SqlCipher 两个}
Queuing_ProcessWaitingQueue : Request{WaitingTicket, ...}         → Response{WaitingTicket, EnterTicket, ServerSeed}

// ===== 建号 / 会话 =====
Account_Auth / Account_Auth2 → Response{CurrentVersion, MinimumVersion, UpdateRequired, AccountDB, EncryptedUID, StaticOpenConditions, ...}
Account_Create / Account_Nickname / Account_CallName / Account_BirthDay
Account_LoginSync  → Response{ 几十个子 Response 打包 }
Account_PassCheck  → Response{EncryptedKey, SignedKey, EncryptedIV, SignedIV}
Account_InvalidateToken / Account_Reset / Account_GetTutorial / Account_SetTutorial
Account_VerifyForYostar  → 空（JP/GL 用，Steam 不发）
```

**[实测]** Shittim `AccountHandler.CheckYostar` 的处理逻辑（决定 token 形态）：

```csharp
var ticketBytes  = Convert.FromBase64String(request.EnterTicket);
var ticketString = Encoding.UTF8.GetString(ticketBytes);
var parts        = ticketString.Split('/');
var publisherId  = long.Parse(parts[0]);
var token        = parts[1];
// 按 publisherId 查/建 UserAccount，然后
var sessionKey    = await _sessionService.GenerateSession(publisherId);
var gatewayCrypto = GatewaySessionCryptoBuilder.Build(request.ClientGeneratedKey, request.ClientGeneratedIV);
response.ResultState = 1;
response.SessionKey  = sessionKey;
response.EncryptedKey / SignedKey / EncryptedIV / SignedIV = gatewayCrypto...
```

⇒ **服务端完全信任 EnterTicket 里的 publisherId，不做任何签名校验。**

---

## 三、token 形态

### 3.1 分三层，别混

| token | 形态 | 生命周期 | 谁来验 | 依据 |
|---|---|---|---|---|
| **TapTap AccessToken** | MAC Token：`kid` / `token_type` / `mac_key` / `mac_algorithm=hmac-sha-1` / `scopeSet` | ≤ 30 天，SDK 每次启动刷新 | TapTap 服务器（`open.tapapis.cn`），**游戏服务端不直接验** | **[官方文档]** |
| **SDK 游戏 token（yostarToken）** | **任意字符串**。Shittim 只要求：**不含 `/`**（因为要 `split('/')`），能被 `long.Parse` 的是前面的 uid | 由 SDKS 服务端定 | **不验** | **[实测]** |
| **EnterTicket** | `base64( UTF8( "<uid>/<token>" ) )` | 一次性 | 不验 | **[实测]** |
| **SessionKey** | 服务端生成的会话键，后续每个 `RequestPacket` 都带 | 会话期 | Shittim `ISessionKeyService` | **[实测]** |

### 3.2 现场观察到的 `local_user_config`

```json
{"loginName":"177****1532","login_type":1,"token":"61de1d1b7519ab1231866f74c11fcfdd1f80b210","uid":314816420}
```

- `token` = **40 位小写十六进制**（160 bit）—— 这是**我们自己的卡密 SDK 已经发过的**形态 **[推断]**，不是 TapTap / Yostar 官方格式
- `uid` = **9 位十进制数字** = `314816420`

⇒ **这恰好证明了方案 B 的可行性**：只要 uid 是数字、token 是任意不含 `/` 的串，游戏侧就能用。

⚠️ **硬约束（务必记住）**：
1. `uid` 必须能 `long.Parse`（纯数字，且 ≤ 9.2e18）
2. `token` **不能包含 `/`**（含 `/` 会把 `Split('/')` 切碎 → `parts[1]` 错位）
3. `ResultState` 必须回 `1`（非 1 客户端会走 `ErrorAccountCheckYostar`）

---

## 四、"游戏把 token 上传给认证服务器"那一步 —— 精确答案

这正是任务里最缺的一块。**完整答案是：分两步、走两个 Protocol，全部在 `POST /api/gateway` 里。**

### 第 1 步：`Protocol.Queuing_GetAuthTicket`

| | 内容 |
|---|---|
| 请求 | `YostarUID` + `YostarToken`（客户端从 SDK 拿到的两个值） |
| 响应 | `AuthTicket` = `base64("{YostarUID}/{YostarToken}")`，外加 4 个网关加密字段 + 2 个 SqlCipher 字段 |
| 作用 | **把 SDK 凭证"打包成票"**，同时下发网关 AES key（RSA 加密） |

**[实测]** Shittim `QueuingHandler.GetAuthTicket`：
```csharp
var rawTicketBytes = Encoding.UTF8.GetBytes($"{request.YostarUID}/{request.YostarToken}");
response.AuthTicket = Convert.ToBase64String(rawTicketBytes);
```

### 第 2 步：`Protocol.Account_CheckYostar`

| | 内容 |
|---|---|
| 请求 | `UID` + `EnterTicket`(=上一步的 AuthTicket) + `PassCookieResult` + `Cookie` + `ClientGeneratedKey` + `ClientGeneratedIV` |
| 响应 | `ResultState=1` + `SessionKey` + `EncryptedKey/SignedKey/EncryptedIV/SignedIV` |
| 作用 | **认证完成，发会话**。之后所有请求带 `SessionKey` |

**[实测]** 客户端 C# 侧的调用链（`global-metadata.dat` 字面量）：
```
StartLoginWithAccountCheckYostar  →  RequestAccountCheckYostar  →  AccountCheckYostarNetworkTask
   ↑                                     ↓
RetryLoginWithAccountCheckYostar  ←  ErrorAccountCheckYostar
                                      HandleAccountCheckYostarResponseMessage
                                         → get_EnterTicket / get_Cookie
LoginTask 持有：yostarUid / yostarToken / enterTicket / serverSeed
```

### 差异说明（Steam 版 vs 国服版）

Shittim 的 `CheckYostar` 注释说：
> "the Yostar build's counterpart to CheckNexon; **the Steam client never sends it**"

而 `VerifyForYostar` 注释说：
> "yostar verification belongs to the JP/GL builds"

⇒ **`Account_CheckYostar` 正是 Yostar 系（含国服）走的那条路**，Steam/Nexon 版才走 `Account_CheckNexon`。**这对我们是有利的** —— 我们要做的就是 Yostar 这条路，而 Shittim 已经把它实现了。

---

## 五、方案 B 的可执行建议

### 5.1 目标形态

```
我们魔改的 SDK 服务端（example.com/sdk）
   └─ 发一个固定 uid + token 给客户端
        └─ 客户端 C# 层存成 yostarUid / yostarToken
             └─ 走 Queuing_GetAuthTicket → Account_CheckYostar
                  └─ Shittim 直接认，建号/进游戏
```

**整条链里没有任何一方真的去校验 token 的合法性。** 唯一需要「对上」的是**格式**。

### 5.2 SDK 服务端要实现哪些端点（按必要性排序）

| 优先级 | 端点 | 是否必须 | 说明 |
|---|---|---|---|
| **P0** | `POST /auth/v1/login-by-token` | **是** | 客户端主登录路径。回 uid + token |
| **P0** | `GET /account/v1/profile` | **是** | 登录后立刻拉资料，缺了会中断 |
| **P1** | `GET /app/v1/get-latest` | 高 | 版本检查 |
| **P1** | `GET {sdk_url}/sdk-core/v1/gatekeeper` | 高 | SDK 自身配置（域名/gatekeeper），可能决定后续打哪个域名 |
| **P1** | `POST /auth/v1/login-by-authorization-code` | 中 | 若走扫码/授权码流才需要 |
| **P2** | `GET /agcgw/url`、`/agcgw/backurl` | 中 | 聚合网关地址选择（国内走 `/agcgw_all/CN`） |
| **P2** | `GET /app/v1/get-uri-by-identifier` | 中 | 资源 URI 调度 |
| **P2** | `POST /device/v1/query`、`/oaid/query` | 低 | 设备指纹，可敷衍 |
| **P3** | `POST /log/logReport` | 低 | 日志，回 `{"code":0}` 即可 |
| **P3** | `GET /v3/cloudconf` | 低 | 云端开关 |

### 5.3 关键端点的应答样例

> ⚠️ **以下 JSON 结构是 [推断]**。Airi SDK 的应答字段名**没有公开文档**，我按国内聚合 SDK 的通行形态（`code`/`msg`/`data` + `userID`/`token`）给模板。
> **验证方法**：手机侧 DNAT 已全量劫持，客户端打 `{sdk_url}/auth/v1/login-by-token` 时**必然经过我们服务器**——把真实请求/应答抓一次（或让现有中继透传并记录），即可把真实字段名补全。**这一步不能省，否则只能靠试。**

**`POST /auth/v1/login-by-token`** —— 最关键的响应

```json
{
  "code": 0,
  "msg": "success",
  "data": {
    "userID": "314816420",
    "token":  "61de1d1b7519ab1231866f74c11fcfdd1f80b210",
    "uid":    "314816420",
    "nickname": "Sensei",
    "expireTime": 0,
    "isNewUser": false,
    "channelId": "1001"
  }
}
```

字段要求（**[实测]** 由 Shittim 的解析反推）：
- `userID` / `uid` 必须是**纯数字字符串**，能 `long.Parse`
- `token` 必须**不含 `/`**
- 不确定客户端读哪个键名 → **把 `userID`/`uid` 两个都放上**，最省事

**`GET /account/v1/profile`**

```json
{ "code": 0, "msg": "success",
  "data": { "userID": "314816420", "uid": "314816420",
            "nickname": "Sensei", "avatar": "", "level": 1 } }
```

**`GET /app/v1/get-latest`**

```json
{ "code": 0, "msg": "success",
  "data": { "version": "3.0.2", "versionCode": "73",
            "downloadUrl": "", "forceUpdate": false, "updateContent": "" } }
```

**`POST /log/logReport`** 与 **`POST /device/v1/query`**

```json
{ "code": 0, "msg": "success", "data": {} }
```

### 5.4 游戏侧（Shittim）需要确认的三件事

| # | 事项 | 为什么 |
|---|---|---|
| 1 | **`POST /api/gateway` 必须能通到 Shittim 的 5000 端口，且 nginx 不能吃掉 body** | 已知曾出现 `/api/gateway` → 500（Shittim 期望 `multipart/form-data` 的 `mx` 字段）。nginx 需 `client_max_body_size` 足够且**不要改写 Content-Type** |
| 2 | **RSA 密钥必须和客户端 `global-metadata.dat` 里打进去的公钥配对** | 第一次交换是 RSA。若用 Shittim 自带流程，需用它的 `Config/GatewayPrivateKey.pem` 并把公钥按「三段 150 字节」塞进 metadata；若我们用自己的一对，两边都要换 |
| 3 | **`Account_CheckYostar` 的 `ClientGeneratedKey/IV` 必须原样回加密结果** | 我们用 Shittim 现成实现，它已经处理好（`GatewaySessionCryptoBuilder.Build`） |

### 5.5 最小验证路径（建议顺序）

1. 让客户端真的发出 `{sdk_url}/auth/v1/login-by-token`，**把请求体原样记录**
2. 用真实字段名回 `code=0 + data.userID/data.token`
3. 观察客户端是否把值存进 `shared_prefs` 或走 `StartLoginWithAccountCheckYostar`
4. 观察是否出现 `POST {ApiUrl}gateway`，日志里看协议号
5. 对照 Shittim 的 handler 表补齐缺失 Protocol（缺 handler 会回 500，客户端显示"无法处理的请求"）

---

## 六、Q3 答案：开源实现

### 6.1 我们服务器上跑的就是它

> **`Neoexm/Shittim-Server`** —— <https://github.com/Neoexm/Shittim-Server>
> "A private server for Blue Archive's **Steam release**, written in C# on ASP.NET Core (.NET 10)"

**[实测]** 与现场完全吻合：

| 现场 | 仓库 |
|---|---|
| `Shittim-Server.dll`，.NET 10 | 同名目录 + `Directory.Build.props` |
| 监听 5000 + 5100 | `ServerConfig.cs`：`HostPort="5000"`、`GatewayPort="5100"`、`EnableGateway` |
| SQLite `BlueArchive.db` | "Progress lives in a local SQLite database" |
| `Schale 2026.8.8` | 仓库里有 `Schale/` 目录（游戏模型/协议库） |
| 客户端补丁 | `Tools/` 里 "ask the patch api as the build thats actually current" |

**目录结构 [实测]**：
```
Shittim-Server/          ← 服务端主体
  Core/NetworkProtocol/Handlers/   ← 65 个 handler 文件
Schale/                  ← 游戏数据模型 + MX.NetworkProtocol
  MX/NetworkProtocol/NetworkProtocol.cs   ← 所有 Request/Response 类定义（我们已抓到全文）
MemoryDumper/            ← 内存 dump 工具
Tools/                   ← 补丁工具
ShittimControlCenter/    ← 安装/管理 GUI
docs/docs/server/protocol.md            ← 协议说明
docs/docs/server/client-patching.md     ← 客户端补丁说明
```

### 6.2 它是否实现了「签发 token」或「接受外部 token」？

| 能力 | 结论 | 依据 |
|---|---|---|
| **接受外部 token** | ✅ **已实现** | `AccountHandler.CheckYostar` / `CheckNexon`；`QueuingHandler.GetAuthTicket` / `GetTicket` |
| **签发 token** | ❌ **不实现，也不需要** | 它把 EnterTicket 里的 uid/token 当事实直接采信，`NpToken` 只是存进 `UserAccounts` 表 |
| **SDK 登录** | ❌ **完全不碰** | 它面向 Steam 版，SDK 层不经过它；`README` 说用 **mitmproxy** 拦客户端 |

**⇒ 这正好是我们需要的最优点**：签发端我们在 SDK 侧自由发挥，接收端它全盘接受。

### 6.3 其他可参考项目

| 项目 | 说明 | 与本任务的关系 |
|---|---|---|
| **`Neoexm/Shittim-Server`** | 上表 | **直接就是我们在跑的** |
| ~~`UZQueen/Blue-Archive-...` 等旧项目~~ | 未核实 | **[未知]** —— 本次未能逐一核实 star 与活跃度，不做推荐 |
| `ba-pentest.md`（本地已存在的抓包记录） | 记录了真实 `state-api` / `CallbackUrl` 应答 | 本项目内部资料 |

⚠️ **诚实标注**：本次对"其他 BA 私服项目"的检索**只确认了 Shittim 一个**。其他仓库我没有可靠来源，不编。

---

## 七、从本地 APK 挖到的原始证据（Q4）

### 7.1 `global-metadata.dat` 里的 C# 字面量（**[实测]**）

**登录链相关符号**（`0x0013F798` 附近，原文连续）：
```
LoginTask
CheckContinueCampaign / CheckContinueStoryStrategy / CheckContinueConquestBattle
get_WaitingTicket / set_WaitingTicket
ErrorQueuingGetTicket / HandleQueuingGetTicketResponseMessage
ErrorAccountPassCheck / HandleAccountPassCheckResponseMessage
ErrorAccountCheckYostar / HandleAccountCheckYostarResponseMessage
AccountAuthStart
ErrorAccountCreate / HandleAccountCreateResponseMessage
ErrorAccountNickname / HandleAccountNicknameResponseMessage
ErrorAccountCallname / HandleAccountCallnameResponseMessage
HandleSessionFinishedMessage
yostarUid
yostarToken
RequestQueuingGetTicket
RequestQueuingGetTicketRetry
enterTicket
serverSeed
RequestAccountCheckYostar
RequestAccountAuth
```

**`Account` 类别的 23 个 op 名**（`Account_XXX` 形式，**[实测]**）：
```
Auth  Auth2  BirthDay  CallName  CheckAccountLevelReward  CheckYostar  Create
CurrencySync  DismissRepurchasablePopup  GetTutorial  InvalidateToken  LevelReward
LinkReward  LoginSync  Nickname  PassCheck  ReceiveAccountLevelReward
ReportXignCodeCheater  RequestBirthdayMail  Reset
SetRepresentCharacterAndComment  SetTutorial  VerifyForYostar
```

**`Billing`（Yostar 计费）**：
```
PurchaseFreeProduct  PurchaseListByYostar  PurchaseProduct  PurchaseProductSelect
TransactionEndByYostar  TransactionStartByYostar
```

**`Queuing`**：`GetCryptoKeys`、`GetTicket`
**`Session`**：`Info`

**SDK 相关类 [实测]**：
`BillingPurchaseListByYostarNetworkTask` / `BillingTransactionStartByYostarNetworkTask` / `BillingTransactionEndByYostarNetworkTask`
异常类：`YostarServerNotSuccessStatusCode` / `YostarNetworkException` / `YostarException` / `YostarCheckFail`
字段：`get_YostarUID` / `set_YostarUID` / `get_PassCheckYostar` / `set_PassCheckYostar`

### 7.2 `classes.dex` / `classes2.dex` 里的 SDK 关键字（**[实测]**）

```
TapSDK-Android/4.6.3
com.taptap.sdk.core.TapTapSdk / TapTapSdkOptions / TapTapSdkBaseOptions
com.taptap.sdk.login.TapTapAccount / AccessToken / TapTapLogin / TapTapLoginActivity
com.taptap.sdk.login.internal.LoginEntrance / NetworkClient
com.taptap.sdk.gid.TapSdkGid / GidService
com.taptap.sdk.themis.lite.ThemisProvider        ← TapTap 反作弊
com.tech.sdk.TechSDK / TechSDK$SdkCallBack
com.tech.sdk.bridge.TechSDKUnityBridge$1..15     ← Unity 桥接（15+ 个内部类 = 15+ 个 SDK 接口）
com.tech.core.TechApplication / TechSplashActivity
com.airi.core.AiriSdkManager
com.airi.core.data.net.http.ApiService / SignProvider / ErrorHandler
com.airi.common.services.SDKConfigManager
com.airi.common.model.params.SDKConfigSettings$Auto_url / $Init / $Internet_detection / $Log
com.yostar.supersdk.UnityFileProvider            ← Yostar SuperSDK（只剩 FileProvider，核心在 native/插件）
```

**Yostar SuperSDK 的持久化键 [实测]**：
```
agg_yostar_sdk  aggsdk_comm_release  aggsdk_domain_release  aggsdk_official_release
aggyostarsdk.db  yostarsdk.db  yostarsdk_config_info  yostarsdk_device_id
youstar_check_network_now  youstar_no_network        ← 注意原文拼写 youstar
```
⇒ `aggsdk_domain_release` 说明**域名是从远端配置下发的**，这跟 `detection_address` 被打成我们域名的事实一致。

### 7.3 `AndroidManifest.xml`（**[实测]**）

关键组件：
```
com.tech.core.TechSplashActivity
com.tech.sdk.bridge.TechSDKUnityPlayerActivity      ← 游戏主 Activity（运行期已观察到此焦点）
com.taptap.sdk.login.ui.TapTapLoginActivity
com.taptap.sdk.kit.internal.TapTapKitInitProvider
com.taptap.sdk.themis.lite.ThemisProvider
com.RoamingStar.BlueArchive.TapTapKitInitProvider
com.ace.gshell.GP6Service / GP7Service / GP7Worker   ← 腾讯 ACE 反作弊
com.airi.udata.util.InitProvider
com.airi.official.core.ui.activity.* （SdkWebviewActivity / CodeWebviewActivity / OneKeyHelperActivity）
com.aliyun.sls.android.producer.provider.SLSContentProvider
com.adjust.sdk.SystemLifecycleContentProvider
com.qq.gdt.action.GDTInitProvider
cn.jpush.android.* （极光推送）
com.huawei.hms.* / com.huawei.agconnect.*
com.tencent.connect.common.AssistActivity / AuthActivity
com.sina.weibo.sdk.* / com.alipay.sdk.*
com.mobile.auth.gatewayauth.LoginAuthActivity       ← 运营商一键登录
com.bun.miitmdid.*                                 ← OAID
```
meta-data：`JPUSH_APPKEY`、`JPUSH_CHANNEL`、`ads-identifier:3.4.62.300`、`base:6.13.0.301`、`opendevice:6.13.0.300`、`push:6.13.0.300`（HMS 版本号）

版本：`versionName=3.0.2`，另见字面量 `2.0.3`（可能是 TechSDK 版本）

> ⚠️ **没有找到 TapTap 的 `client_id`**。Airi/TapSDK 的 client_id 在运行期从 `SDKConfigSettings` 或远端 config 取，**不在 manifest 的 meta-data 里**。**[实测]**（manifest 全文 UTF-16LE + UTF-8 双路扫描，无 `client_id` 键）

### 7.4 `assets/aa/settings.json`

Unity Addressables 的远程目录配置，指向
`{UnityEngine.Application.persistentDataPath}/catalog_Remote.hash`，并带 `m_IgnoreFailures=true`。
**与登录无关**，列此以证明该文件已查过。

---

## 八、风险与坑（按严重度）

| # | 坑 | 后果 | 依据 |
|---|---|---|---|
| 1 | **`token` 里含 `/`** | `EnterTicket.Split('/')` 错位 → `parts[1]` 不是 token → 建号失败 | **[实测]** Shittim 源码 |
| 2 | **`uid` 不是纯数字 / 超 long** | `long.Parse` 抛异常 → 500 → 客户端"无法处理的请求" | **[实测]** |
| 3 | `ResultState != 1` | 客户端走 `ErrorAccountCheckYostar`，可能静默重试 | **[实测]** |
| 4 | **`/api/gateway` 未被正确转发** | 已实测出现过 500（Shittim 期望 multipart 的 `mx` 字段）。nginx 不能改 Content-Type、`client_max_body_size` 要够 | **[实测]** 现场 |
| 5 | **RSA 公私钥不配对** | 首次交换失败，客户端**卡在"Unpacking game resources"且不报错** | **[实测]** protocol.md |
| 6 | 缺 Protocol handler | 统一回 500，客户端显示"A request that cannot be processed"，**与 handler 内部异常完全无法区分** | **[实测]** protocol.md |
| 7 | 向量缺 x/y/z | 客户端反序列化抛异常在无 try/catch 的方法里 → **整个响应被静默吞掉** | **[实测]** protocol.md |
| 8 | Airi SDK 应答字段名猜错 | 客户端解析失败 → 登录中断 | **[推断]** 未验证 |
| 9 | `detection_address` 的 **MTR 必失败** | 已在 `files/sls/logs/net_d_000` 观察到 798 条 `lastHop:0`；手机侧 DNAT 抹平跳数 | **[实测]** 现场 |
| 10 | TapSDK 有 `themis` 反作弊 + ACE `gshell` | 运行时 hook 有被检测风险 | **[实测]** manifest |

---

## 九、所有来源

### 本地实测（一手）
- `work\ba\audit\ba-work\x\assets\bin\Data\Managed\Metadata\global-metadata.dat`（38,426,024 B）
- `work\ba\audit\ba-work\x\classes.dex`（9,327,708 B）/ `classes2.dex`（10,158,904 B）
- `work\ba\audit\ba-work\x\AndroidManifest.xml`（50,552 B）
- `work\ba\audit\ba-work\x\assets\aa\settings.json`（3,161 B）
- 中间产物：`report\_tmp\sdk_scan\{scan.txt, targeted.txt, ops.txt, yostar.txt, manifest.txt}`

### 上游源码
- [Neoexm/Shittim-Server](https://github.com/Neoexm/Shittim-Server) —— 我们在跑的私服本体
- [Shittim-Server `AccountHandler.cs`](https://github.com/Neoexm/Shittim-Server/blob/main/Shittim-Server/Core/NetworkProtocol/Handlers/AccountHandler.cs)
- [Shittim-Server `QueuingHandler.cs`](https://github.com/Neoexm/Shittim-Server/blob/main/Shittim-Server/Core/NetworkProtocol/Handlers/QueuingHandler.cs)
- [Shittim-Server `NetworkProtocol.cs`](https://github.com/Neoexm/Shittim-Server/blob/main/Schale/MX/NetworkProtocol/NetworkProtocol.cs)
- [Shittim-Server `docs/server/protocol.md`](https://github.com/Neoexm/Shittim-Server/blob/main/docs/docs/server/protocol.md)
- [Shittim-Server `ServerConfig.cs`](https://github.com/Neoexm/Shittim-Server/blob/main/Shittim-Server/Configuration/ConfigType/ServerConfig.cs)

### 官方文档
- [TapTap OAuth 接口（MAC Token 签算、open.tapapis.cn 端点、错误码）](https://developer.taptap.cn/docs/en/v3/sdk/taptap-login/guide/taptap-oauth/)
- [TapTap 扫码登录 / 设备码模式（accounts.tapapis.cn/oauth2/v1/device/code）](https://developer.taptap.cn/docs/en/sdk/taptap-login/device-code/)

### 未找到公开证据的部分（明确标注）
- **Airi 聚合 SDK 的应答 JSON 字段名** —— 无公开文档。**[推断]** 按国内聚合 SDK 通行形态给出，必须用真实抓包校正
- **`/sdk-core/v1/gatekeeper`、`/v3/cloudconf` 的具体语义** —— 仅有路径字面量，**[推断]**
- **Yostar SuperSDK 的网络端点** —— 核心不在 dex 里（只剩 `UnityFileProvider`），**[未知]**
- **`Protocol` 枚举的具体数字** —— 在 `Schale/MX/NetworkProtocol/ProtocolData.cs`，本次未取到，需从仓库或按协议名反查
- **TapTap `client_id` 的实际值** —— manifest 与 dex 均无明文，在运行期配置里

---

## 十、给 Lead 的三句话

1. **方案 B 成立且比预期简单**：签发端（SDK 的 `sdk_url`）和接收端（Shittim 的 `Account_CheckYostar`）都在我们手里，中间不校验 token 合法性，只校验格式。
2. **唯一必须做的验证**：抓一次真实的 `POST {sdk_url}/auth/v1/login-by-token` 往返，把 Airi SDK 的真实字段名定下来——这是整份报告里唯一不能靠推理补的环节。
3. **顺手发现的独立 bug**：`detection_address` 里的 MTR 永远失败（`net_d_000` 里 798 条 `lastHop:0`），因为手机侧 DNAT 抹平了跳数。这与登录链无关，但会让客户端持续做无效网络诊断。
