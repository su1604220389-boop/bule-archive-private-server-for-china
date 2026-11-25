# 43 — Queuing 接管实施规格（可直接照做）

> 时间：2026-11-14 04:10 前后
> 前提假设：**国服客户端确实会发 `Queuing_*`**（`srv-ops` 正在按 host+path 核实，本报告不假设已证实）
> 依据：`report\_tmp\shittim\src\`（只读）+ `scripts\cn_bridge_v5.py`（只读）
> **未连接手机、未连接服务器、未重启任何服务。**

**查档**：`report\42-Shittim流程还原-Auth之后.md` §3.3（本报告是它的实施版）、`report\28` §3.1-3.2（Queuing DTO 与 handler）、`report\36` §7（CN 请求形态）。
**证据分级**：`[源码实测]` = 我读到的源码原文；`[推断]` = 由源码推出的结论；`[未找到]` = 本地快照没有对应文件。

---

## 0. 一页结论

| 问题 | 答案 |
|---|---|
| 出队的**唯一硬条件**是什么 | `EnterTicket` **非空**（`QueuingHandler.cs:106` 注释：空 = 客户端被扣在排队弹窗上） |
| 还有第二硬条件吗 | 有：`AllowedSequence` **必须领先** `TicketSequence`（`QueuingHandler.cs:63` 注释），否则客户端自己算出"要等" |
| 哪些字段可以填 0/空 | `Birth`=`""`、`ServerSeed`=`""`、`ServerTimeTicks`=0（=省略）、`WaitingTicket`（仅 GetTicket 可省） |
| 哪些**必须**真实 | `EnterTicket` / `AuthTicket` / `AllowedSequence` / `RequiredSecondsPerUser` |
| 要接管几个协议 | **4 个真协议**（50000-50003）+ 3 个 bridge 表里的**幽灵名**（不存在于枚举，见 §4.3） |
| 改哪一层 | **bridge（Python），不改 Shittim。** 理由与插入点见 §5 |
| 代码量 | ~35 行 Python，插在 `cn_bridge_v5.py:274` 之后 |

**一句话规格**：给客户端一张**永远已经叫到号**的票——`TicketSequence` 是个大数、`AllowedSequence` 比它大 1722、`EnterTicket`/`AuthTicket` 恒等于 `base64("314816420/61de1d…")`、其余能给空就给空。

---

## 1. 精确的响应结构（DTO 原文抄录）

### 1.1 `Queuing_GetTicket`（50000）

`Schale__MX__NetworkProtocol__NetworkProtocol.cs:5806-5816`

```csharp
public class QueuingGetTicketResponse : ResponsePacket
{
    public override Protocol Protocol { get => Protocol.Queuing_GetTicket; }
    public string? WaitingTicket { get; set; }          // :5809
    public string? EnterTicket { get; set; }            // :5810  ★ 出队的硬条件
    public long TicketSequence { get; set; }            // :5811
    public long AllowedSequence { get; set; }           // :5812  ★ 必须 > TicketSequence
    public double RequiredSecondsPerUser { get; set; }  // :5813
    public string? Birth { get; set; }                  // :5814
    public string? ServerSeed { get; set; }             // :5815
}
```

继承自 `ResponsePacket`（`Packet.cs:45-56`）还有：`ServerTimeTicks`(long)、`ServerNotification`(enum)、`SessionKey`(null)、`AccountId`(由 `SessionKey` 派生，`:18-20`)。

### 1.2 `Queuing_ProcessWaitingQueue`（50003）

`NetworkProtocol.cs:5877-5886`

```csharp
public class QueuingProcessWaitingQueueResponse : ResponsePacket
{
    public override Protocol Protocol { get => Protocol.Queuing_ProcessWaitingQueue; }
    public string? WaitingTicket { get; set; }          // :5880
    public string? EnterTicket { get; set; }            // :5881  ★
    public long TicketSequence { get; set; }            // :5882
    public long AllowedSequence { get; set; }           // :5883  ★
    public double RequiredSecondsPerUser { get; set; }  // :5884
    public string? ServerSeed { get; set; }             // :5885
}
```

注意：**没有 `Birth`**（与 GetTicket 的唯一字段差异）。

### 1.3 `Queuing_GetAuthTicket`（50002）

`NetworkProtocol.cs:5850-5861`

```csharp
public class QueuingGetAuthTicketResponse : ResponsePacket
{
    public override Protocol Protocol { get => Protocol.Queuing_GetAuthTicket; }
    public string? EncryptedKey { get; set; }             // :5853
    public string? SignedKey { get; set; }                // :5854
    public string? EncryptedIV { get; set; }              // :5855
    public string? SignedIV { get; set; }                 // :5856
    public string? EncryptedSqlCipherKey { get; set; }    // :5857
    public string? EncryptedSqlCipherLicense { get; set; }// :5858
    public string? Birth { get; set; }                    // :5859
    public string? AuthTicket { get; set; }               // :5860  ★ 出队的硬条件
}
```

### 1.4 `Queuing_GetCryptoKeys`（50001）

`NetworkProtocol.cs:5825-5834` —— 只有 6 个 crypto 字段（`EncryptedKey` / `SignedKey` / `EncryptedIV` / `SignedIV` / `EncryptedSqlCipherKey` / `EncryptedSqlCipherLicense`），**没有任何 ticket 字段**。

### 1.5 ★ `AllowedSequence` 与 `TicketSequence` 的关系："源码里怎么比较的"

**诚实回答：Shittim 的源码里没有任何一行做这个比较。**

`[源码实测]` 全快照 grep `AllowedSequence|TicketSequence` 只有 8 处命中（`ProtocolData.cs:502`、`NetworkProtocol.cs:5811-5812`、`:5882-5883`、`QueuingHandler.cs:67-68`），**没有一处是关系运算**。比较发生在**客户端**，而客户端代码不在我们手里。

唯一陈述这个关系的是 `QueuingHandler.cs:63-64` 的一句**来自官方抓包的注释**（原文抄录）：

```csharp
// Official shape (live captures): Birth is an empty string, the ticket/allowed sequences are
// large non-zero counters with AllowedSequence ahead of TicketSequence (no queue wait),
// and RequiredSecondsPerUser is a small positive value.
```

以及紧跟着的赋值（`QueuingHandler.cs:67-69`）：

```csharp
response.TicketSequence = 130_000_000 + (DateTimeOffset.UtcNow.ToUnixTimeSeconds() % 10_000_000);
response.AllowedSequence = response.TicketSequence + 1722;
response.RequiredSecondsPerUser = 0.0058;
```

⇒ **可执行结论（`[推断]`，依据上面那条注释）**：

| 关系 | 语义 | 本规格采用 |
|---|---|---|
| `AllowedSequence > TicketSequence` | "已经叫到你的号了，直接进" | `AllowedSequence = TicketSequence + 1722` |
| `AllowedSequence == TicketSequence` | 边界，行为未知 | **不要用** |
| `AllowedSequence < TicketSequence` | "前面还有 (T-A) 个人" → 客户端显示排队条 | 禁止 |
| `TicketSequence` 必须"大且非零" | 注释原话 "large non-zero" | 用 `130_000_000 + now%10^7` |
| `RequiredSecondsPerUser` 必须"小正数" | 注释原话 "small positive" | `0.0058`（照抄 Shittim） |

⚠ `TicketSequence` 若填 `0`：`GatewayController.cs:124-125` 的 `DefaultValueHandling.Ignore`（`:118` 注释「default-valued members omitted（0/false/…）」）会**把这两个字段整个从 JSON 里删掉**，客户端读到的就是 `0 > 0` = 不成立。**这是最容易踩的坑。**

---

## 2. 最少要填什么才能让客户端出队

### 2.1 逐字段判定表

| 字段 | 所在协议 | 必须真实？ | 填什么 | 依据 |
|---|---|---|---|---|
| `EnterTicket` | GetTicket / ProcessWaitingQueue | **必须非空** | `base64("uid/token")` | `QueuingHandler.cs:106` 注释 + `:107-109` |
| `AuthTicket` | GetAuthTicket | **必须非空** | 同上（**同一个串**） | `QueuingHandler.cs:84,93` |
| `AllowedSequence` | GetTicket / ProcessWaitingQueue | **必须** | `TicketSequence + 1722` | `QueuingHandler.cs:63,68` |
| `TicketSequence` | 同上 | **必须非零** | `130_000_000 + now%10^7` | `QueuingHandler.cs:67` + 序列化省略规则 |
| `RequiredSecondsPerUser` | 同上 | **必须 > 0** | `0.0058` | `QueuingHandler.cs:69` |
| `WaitingTicket` | GetTicket / ProcessWaitingQueue | 可省（但**建议给**） | 固定串 `"WT-CN-0001"` | `QueuingHandler.cs:105` 回显请求值；不给则后续回显为空 |
| `Birth` | GetTicket / GetAuthTicket | 可空串 | `""` | `QueuingHandler.cs:66,92` |
| `ServerSeed` | GetTicket / ProcessWaitingQueue | **可以空串** | `""` | `QueuingHandler.cs:65` 注释：官方 1 KB seed 只喂 NGS，本服故意绕过 |
| `ServerTimeTicks` | 全部 | 可 0（=省略） | 不填 | `QueuingHandler.cs:71` 注释「No ServerTimeTicks on queuing responses」 |
| `EncryptedKey/SignedKey/EncryptedIV/SignedIV` | GetCryptoKeys / GetAuthTicket | **可省内层字段**（视 §2.2 档位） | 见 §2.2 | `GatewaySessionCrypto.cs:53-71` |
| `EncryptedSqlCipherKey/License` | 同上 | **条件必须**（见 §2.2 L2） | 见 §2.2 | `QueuingHandler.cs:116-126` |
| `SessionKey` | 全部 | **不要填** | 省略 | `GatewayController.cs:318-322` 只有 Auth/ProofToken 才回显；Queuing 不在内 |

### 2.2 三档保真度（选一档，别混）

| 档 | 做法 | 优点 | 风险 |
|---|---|---|---|
| **L0 纯明文**（**推荐先上**） | crypto 字段**一律不给**（全部 null → 被 `DefaultValueHandling.Ignore` 删掉） | 零依赖、零异常面；与我们现在的 `keyLen=0` 明文 `.mx` 完全自洽（`GatewayController.cs:514-517`：`keyLen=0` ⇒ `UseAes=false` ⇒ 响应明文） | 若客户端硬性要求 `EncryptedSqlCipherKey` 才能开 ExcelDB → 卡在表加载 |
| **L1 走 Shittim 算** | bridge 合成请求 → Shittim `/api/gateway`，用 Shittim 返回的真 crypto 字段 | 字段真实性最高 | 需要注入 `ClientGeneratedKey/IV`（否则 handler 抛异常，见 §6-①）；`SignedKey` 用 **SHA1-PKCS1** 签（`GatewaySessionCrypto.cs:240`），客户端验签依赖**metadata 已换成我们的公钥** |
| **L2 全真** | L1 + 保证 `EncryptedSqlCipherKey/License` 能被客户端解开 | 能开表 | 需要 `ExcelDbSqlCipherKey/License` 与客户端期望一致；**当前是否一致未知** |

**建议路径**：先 L0 跑一轮（这一步只验"客户端会不会因此出队"），失败且 `POST /log` 指向表加载，再上 L1/L2。

---

## 3. "永远放行"的 ticket 长什么样（完整 JSON）

### 3.1 常量（先算好，可硬编码）

```
UID            = 314816420
TOKEN          = 61de1d1b7519ab1231866f74c11fcfdd1f80b210
TICKET         = base64("314816420/61de1d1b7519ab1231866f74c11fcfdd1f80b210")
               = MzE0ODE2NDIwLzYxZGUxZDFiNzUxOWFiMTIzMTg2NmY3NGMxMWZjZmRkMWY4MGIyMTA=       (68 字符)
TicketSequence = 130_000_000 + (now_unix % 10_000_000)      // 例：134598890
AllowedSequence= TicketSequence + 1722                      // 例：134600612
```

`★ TICKET 这一个串同时充当 `EnterTicket`（GetTicket / ProcessWaitingQueue）和 `AuthTicket`（GetAuthTicket）。`AuthTicket` 与 `EnterTicket` 都是 `base64("{uid}/{token}")`，`[源码实测]` `QueuingHandler.cs:62`（GetTicket）与 `:93`（GetAuthTicket）用同一构造函数。

### 3.2 `Queuing_GetTicket` → HTTP 200 响应（L0）

```json
{"protocol":"Queuing_GetTicket","packet":"{\"Protocol\":50000,\"WaitingTicket\":\"WT-CN-0001\",\"EnterTicket\":\"MzE0ODE2NDIwLzYxZGUxZDFiNzUxOWFiMTIzMTg2NmY3NGMxMWZjZmRkMWY4MGIyMTA=\",\"TicketSequence\":134598890,\"AllowedSequence\":134600612,\"RequiredSecondsPerUser\":0.0058,\"Birth\":\"\",\"ServerSeed\":\"\"}"}
```

展开内层 `packet`（客户端实际解析的那份）：

```json
{
  "Protocol": 50000,
  "WaitingTicket": "WT-CN-0001",
  "EnterTicket": "MzE0ODE2NDIwLzYxZGUxZDFiNzUxOWFiMTIzMTg2NmY3NGMxMWZjZmRkMWY4MGIyMTA=",
  "TicketSequence": 134598890,
  "AllowedSequence": 134600612,
  "RequiredSecondsPerUser": 0.0058,
  "Birth": "",
  "ServerSeed": ""
}
```

### 3.3 `Queuing_GetAuthTicket` → L0

```json
{"protocol":"Queuing_GetAuthTicket","packet":"{\"Protocol\":50002,\"Birth\":\"\",\"AuthTicket\":\"MzE0ODE2NDIwLzYxZGUxZDFiNzUxOWFiMTIzMTg2NmY3NGMxMWZjZmRkMWY4MGIyMTA=\"}"}
```

内层展开：

```json
{
  "Protocol": 50002,
  "Birth": "",
  "AuthTicket": "MzE0ODE2NDIwLzYxZGUxZDFiNzUxOWFiMTIzMTg2NmY3NGMxMWZjZmRkMWY4MGIyMTA="
}
```

> 注意：GetAuthTicket **没有** `AllowedSequence`/`TicketSequence` 字段（DTO `:5850-5861`）。它的"放行"信号就是 `AuthTicket` 本身。

### 3.4 `Queuing_ProcessWaitingQueue` → L0

```json
{"protocol":"Queuing_ProcessWaitingQueue","packet":"{\"Protocol\":50003,\"WaitingTicket\":\"WT-CN-0001\",\"EnterTicket\":\"MzE0ODE2NDIwLzYxZGUxZDFiNzUxOWFiMTIzMTg2NmY3NGMxMWZjZmRkMWY4MGIyMTA=\",\"TicketSequence\":134598890,\"AllowedSequence\":134600612,\"RequiredSecondsPerUser\":0.0058,\"ServerSeed\":\"\"}"}
```

### 3.5 `Queuing_GetCryptoKeys` → L0（最小）

```json
{"protocol":"Queuing_GetCryptoKeys","packet":"{\"Protocol\":50001}"}
```

`[推断]`：6 个 crypto 字段全 null ⇒ 全被 `DefaultValueHandling.Ignore` 删掉 ⇒ 客户端拿不到会话 blob ⇒ 继续走明文。**这一条与 §6-③ 的异常绑定，必须与 §5 的"注入 ClientGeneratedKey/IV"配套（若走 L1）或完全不调 Shittim（若走 L0）。**

### 3.6 响应形态的三个开关（与 42 号 D2b 联动）

| 开关 | 本规格默认 | 若 42 号 D2b 判定相反，改成 |
|---|---|---|
| 外层 `protocol` | **名字字符串** `"Queuing_GetTicket"` | 数字 `50000` |
| 内层 `Protocol` | **整数** `50000`（与 Shittim 一致，`report\36` §7 实测） | 字符串 `"Queuing_GetTicket"` |
| 响应体加密 | **明文**（与现有 Account_Auth 路径一致） | `probe_v6` 的 `encresp1/2/3` 三选一 |

⚠ **四个协议必须用同一套开关**，否则客户端会在 Auth 成功、Queuing 失败之间反复回标题，比现在更难定位。

---

## 4. 我们需要接管哪些协议名

### 4.1 `ProtocolData.cs:500-503` 那四行的完整含义

`[源码实测]` 原文（`Schale__MX__NetworkProtocol__ProtocolData.cs:500-503`）：

```csharp
Queuing_GetTicket            = 50000,
Queuing_GetCryptoKeys        = 50001,
Queuing_GetAuthTicket        = 50002,
Queuing_ProcessWaitingQueue  = 50003,
```

| 号 | 名称 | 谁先发 | 请求关键字段（`NetworkProtocol.cs`） | 响应关键字段 | handler |
|---|---|---|---|---|---|
| **50000** | `Queuing_GetTicket` | 国际服（Nexon） | `NpSN`(long) `NpToken` `Npacode` `AccessIP` `MakeStandby` `PassCheck` `PassCheckNexon` `WaitingTicket` `ClientVersion` `OSType` `NgsmToken`（`:5790-5804`） | `EnterTicket` `TicketSequence` `AllowedSequence` `RequiredSecondsPerUser` | `QueuingHandler.cs:42-74` |
| **50001** | `Queuing_GetCryptoKeys` | 国际服 | `ClientGeneratedKey` `ClientGeneratedIV`（`:5818-5823`） | `Encrypted*` / `Signed*` / `EncryptedSqlCipher*` | `QueuingHandler.cs:21-40` |
| **50002** | `Queuing_GetAuthTicket` | **国服（Yostar）** | `YostarUID`(long) `YostarToken` `PassCheck` `MakeStandby` `PassCheckYostar` `ClientVersion` `OSType` `ClientGeneratedKey` `ClientGeneratedIV`（`:5836-5848`） | `AuthTicket` `Birth` + crypto | `QueuingHandler.cs:76-97` |
| **50003** | `Queuing_ProcessWaitingQueue` | 两边都用（"排队中"轮询） | `WaitingTicket` `ClientVersion` `OSType` `AuthTicket` `NpSN` `NpToken` `Npacode` `AccessIP` `NgsmToken`（`:5863-5875`） | `WaitingTicket` `EnterTicket` `TicketSequence` `AllowedSequence` `RequiredSecondsPerUser` `ServerSeed` | `QueuingHandler.cs:99-114` |

**国服最可能走的链**（`[推断]`，依据 `report\28` §5.4 + 两个 DTO 的字段名）：

```
50001 GetCryptoKeys → 50002 GetAuthTicket{AuthTicket} → 1009 CheckYostar{EnterTicket=AuthTicket}
   → （其间可能穿插）50003 ProcessWaitingQueue 轮询 → 1002 Account_Auth
```

⇒ **如果国服确实走这条，我们要接管的是 50001 / 50002 / 50003 三个，50000 可以一并接（便宜）。**

### 4.2 必须接管的清单（4 个）

| 协议名 | 号 | 是否必须接管 | 理由 |
|---|---|---|---|
| `Queuing_GetAuthTicket` | 50002 | **必须** | 国服取票入口，`AuthTicket` 是下游 `CheckYostar` 的凭证 |
| `Queuing_ProcessWaitingQueue` | 50003 | **必须** | 空 `EnterTicket` 的卡点就在这（`QueuingHandler.cs:106`） |
| `Queuing_GetCryptoKeys` | 50001 | **必须**（至少回个空壳） | 不回则 404，客户端可能直接放弃握手 |
| `Queuing_GetTicket` | 50000 | 顺手接 | 国际服口径；万一国服 fallback 到它 |

### 4.3 ⚠ bridge 表里的三个**幽灵名**（枚举里不存在，接了也是错）

`[源码实测]` 在 `ProtocolData.cs` 全文（1268 行）检索，以下三个名字**没有任何枚举成员**：

| bridge 表里的名字 | 出现在 | 枚举里真实是什么 |
|---|---|---|
| `Queuing_Ping` | `cn_bridge_v5.py:33` | **不存在**。只是 HTTP 路由 `api/Queuing/Ping`（`GatewayController.cs:150-152`），无协议号、无 handler |
| `Queuing_GetTicketGL` | `cn_bridge_v5.py:34` | **不存在**。它是 Shittim 在 `GatewayController.cs:191-196` 里给 `Queuing_GetTicket` 响应**临时起的显示名**（`responseProtocolName = "Queuing_GetTicketGL"`） |
| `Queuing_GetWaitingQueue` | `cn_bridge_v5.py:34` | **不存在**。全枚举无此成员 |

⇒ **处置**：这三个从 NAME_TABLE 里删掉，或映射到正确的协议上（`Queuing_Ping` 应该走 HTTP GET，不是协议）。留着它们只会让"未知协议"伪装成"已知"，掩盖真实协议名。

### 4.4 国服特有的、Shittim 完全缺席的候选（`[推断]`，高优先级排查）

| 名字 | 在 Shittim 枚举里？ | 为什么值得查 |
|---|---|---|
| `Account_GetIdCardInformation` | **不在**（检索无命中） | 国服强制实名认证。若客户端 Auth 后先要实名信息，Shittim 根本没有这个协议 ⇒ 必然 400/404 ⇒ 静默停住 |
| `Account_VerifyCheckAdultAgree`(1020) / `Account_SetCheckAdultAgree`(1021) | **在**（`report\28` §2.2 列表） | 韩/日版成年确认；国服可能用实名替代 |
| `Account_BirthDay`(1011) | 在 | 生日弹窗，新号必弹 |

⇒ 这三个是"**Auth 之后的第二发**"的强候选，见 `report\44` §7 的补路由优先级。**注意它们不是 Queuing 家族**，本报告只做指认，不做规格。

---

## 5. 改在哪一层：bridge，不改 Shittim

### 5.1 结论与理由

**改 `scripts\cn_bridge_v5.py`（或线上同名文件），不动 Shittim。**

| # | 理由 | 证据 |
|---|---|---|
| 1 | **Shittim 没有 `api/<service>/<action>` 路由**，接不了国服的按名分路径。要在 Shittim 侧接，等于先写一整套国服信封解密（`[u32 len][gzip(iv+ct+key)]`），工作量 10 倍 | `GatewayController.cs:101,150-158` 全部路由；`report\35` §一 国服信封 |
| 2 | **bridge 已经持有全部所需常量**：UID / TOKEN / ENTER_TICKET / CLIENT_KEY / IV | `cn_bridge_v5.py:21-25` |
| 3 | **bridge 已经是国服↔Shittim 的翻译层**，Queuing 属于"翻译"，不属于"游戏逻辑" | `cn_bridge_v5.py:1-9` 文件头注释 |
| 4 | Shittim 的排队逻辑总共 3 行赋值，**没有值得复用的东西** | `QueuingHandler.cs:67-69` |
| 5 | 改 Shittim = 与上游 `Neoexm/Shittim-Server` 的更新产生冲突，未来合并成本高 | 项目约定见 `report\28` §6.2 |

**唯一例外**：若将来把整条国服链路做进 Shittim（C# 侧），那才需要新增 Controller；届时插入点是 `GameServer.cs:252 app.MapControllers()`（已存在，无需改），新增文件 `Controllers/Api/CnGatewayController.cs`。**本轮不做。**

### 5.2 具体插入点

`scripts\cn_bridge_v5.py` 现有结构：

```
:236  def _bridge(self, body, rec):
:237      fields = parse_cn_multipart(body)
:240      name = NAME_TABLE.get(proto_str)
:242-247  if name is None:  → _forward  （未知协议）
:249-256  if name is Queueing_CheckNexon …（实际是 Account_CheckNexon）
:258-274  if name in ('Account_Auth','Account_Auth2'):  → 合成 → Shittim → 明文回
:276-279  # 其它已知协议：先原样转发 → _forward      ← ★ 所有 Queuing_* 都掉进这里
```

⇒ **在 `:274` 之后、`:276` 之前插入一个 `if name.startswith('Queuing_')` 分支。**
（`:274` 是 Account_Auth 分支的 `return 200, ...;`，`:276` 是注释 `# 其它已知协议（后面再逐个接管）`。）

### 5.3 可直接粘贴的代码（L0 档，分两段）

#### 第一段 —— 模块级，贴在 `cn_bridge_v5.py:116` 之后

（`:116` 是 `unwrap_gateway_response()` 的 `return j.get('protocol'), pkt`。**必须放模块级**，塞进方法体会每次请求重建 dict 并 `def` 一次。）

```python
# ===== Queuing 铸票（L0：纯明文，不调 Shittim） =====
QUEUE_TICKET   = ENTER_TICKET            # 与 EnterTicket / AuthTicket 同串（cn_bridge_v5.py:23）
QUEUE_WAITING  = 'WT-CN-0001'
QUEUE_REQUIRED = 0.0058
QUEUE_NO = {'Queuing_GetTicket': 50000,
            'Queuing_GetCryptoKeys': 50001,
            'Queuing_GetAuthTicket': 50002,
            'Queuing_ProcessWaitingQueue': 50003}

def queue_seq():
    """TicketSequence 必须“大且非零”，AllowedSequence 必须领先（QueuingHandler.cs:63-69）。"""
    ts = 130000000 + (int(time.time()) % 10000000)
    return ts, ts + 1722

def build_queue_packet(name, proto_no, rec):
    ts, allowed = queue_seq()
    rec['queue_ticket'] = QUEUE_TICKET       # 写进 api_all_requests.log，便于事后核对
    rec['queue_seq'] = [ts, allowed]
    if name == 'Queuing_GetAuthTicket':
        body = {"Protocol": proto_no, "Birth": "", "AuthTicket": QUEUE_TICKET}
    elif name == 'Queuing_GetCryptoKeys':
        body = {"Protocol": proto_no}        # 6 个 crypto 字段全省 ⇒ 保持明文（§2.2 L0）
    elif name == 'Queuing_ProcessWaitingQueue':
        body = {"Protocol": proto_no, "WaitingTicket": QUEUE_WAITING,
                "EnterTicket": QUEUE_TICKET, "TicketSequence": ts, "AllowedSequence": allowed,
                "RequiredSecondsPerUser": QUEUE_REQUIRED, "ServerSeed": ""}
    else:                                     # Queuing_GetTicket
        body = {"Protocol": proto_no, "WaitingTicket": QUEUE_WAITING,
                "EnterTicket": QUEUE_TICKET, "TicketSequence": ts, "AllowedSequence": allowed,
                "RequiredSecondsPerUser": QUEUE_REQUIRED, "Birth": "", "ServerSeed": ""}
    return {"protocol": name,
            "packet": json.dumps(body, ensure_ascii=False, separators=(',', ':'))}
```

#### 第二段 —— 类内分支，贴在 `:274` 之后、`:276` 之前

（`:274` 是 Account_Auth 分支最后的 `return 200, ...`；`:276` 是注释 `# 其它已知协议：先原样转发（后面再逐个接管）`。**缩进 8 空格**，与 `:242` / `:249` / `:258` 的 `if` 同级。）

```python
        # ---- Queuing 铸票：永远“已经叫到号”（report\43 §3）----
        if name in QUEUE_NO:
            out = build_queue_packet(name, QUEUE_NO[name], rec)
            rec['served'] = 'queuing-synth'
            return 200, json.dumps(out, ensure_ascii=False, separators=(',', ':')).encode(), \
                   'application/json; charset=utf-8'
        # ---- 插入结束 ----
```

`rec` 上多写的两个键是为了事后从 `api_all_requests.log` 直接核对（`_log` 是 `json.dumps(rec)`，`:180-185`，任何键都能进）。**没有这两个键就说明分支没命中**——比翻日志找痕迹快得多。

### 5.4 如果走 L1（让 Shittim 算 crypto）改哪里

同一个位置，但把"合成响应"换成"合成请求 → `post_gateway()`"：

```python
req = {"Protocol": name,
       "ClientGeneratedKey": CLIENT_KEY, "ClientGeneratedIV": CLIENT_IV}   # ★ 不能省，见 §6-①
if name == 'Queuing_GetAuthTicket':
    req["YostarUID"] = 314816420
    req["YostarToken"] = TOKEN
elif name in ('Queuing_GetTicket', 'Queuing_ProcessWaitingQueue'):
    req["NpSN"] = 314816420          # ★ 不能是 0，见 §6-②
    req["NpToken"] = TOKEN
    req["WaitingTicket"] = QUEUE_WAITING
code, raw = post_gateway(req)        # cn_bridge_v5.py:88-102
gp, obj = unwrap_gateway_response(raw)
```

`post_gateway` / `unwrap_gateway_response` 是现成的（`:88-116`），**不要重写**。

---

## 6. 陷阱清单（每条都是源码级、都会让客户端停在原地）

### ① `Queuing_GetAuthTicket` / `GetCryptoKeys` 缺 `ClientGeneratedKey` ⇒ handler 抛异常 ⇒ Error 信封

`[源码实测]` 调用链：

```
QueuingHandler.cs:82   GatewaySessionCryptoBuilder.Build(request.ClientGeneratedKey, request.ClientGeneratedIV)
GatewaySessionCrypto.cs:55  Build → DecodeClientCrypto(clientKeyText, clientIvText)
GatewaySessionCrypto.cs:75-76
    if (string.IsNullOrWhiteSpace(keyText) || string.IsNullOrWhiteSpace(ivText))
        throw new WebAPIException(WebAPIErrorCode.ServerFailedToHandleRequest, "Missing client generated crypto material");
```

⇒ 客户端不带 key/IV 时，我们拿到的是 `{"protocol":"Error","packet":"{...ErrorCode:500...}"}`，**HTTP 仍 200**（`GatewayController.cs:280-286` → `:773-789`）。
**L1 必须注入；L0 因为不调 Shittim，天然免疫。**

### ② `Queuing_GetTicket` 用 `NpSN=0` 会铸出一张**错误的票**（不是空的，更危险）

`[源码实测]` `QueuingHandler.cs:61-62`：

```csharp
byte[] rawTicketBytes = Encoding.UTF8.GetBytes($"{request.NpSN}/{request.NpToken}");
response.EnterTicket = Convert.ToBase64String(rawTicketBytes);
```

`NpSN` 默认 0、`NpToken` 默认 null ⇒ `EnterTicket = base64("0/")` = `"MC8="` —— **非空，所以不会卡队列，但下游必炸**：

- 走 `Account_CheckYostar`：`AccountHandler.cs:905-911` 解出 `parts = ["0",""]` ⇒ `publisherId = 0`、`token = ""` ⇒ **自动建一个 `PublisherAccountId=0` 的账号** ⇒ 与我们想要的 `314816420` 不是同一个号。
- 走 `Account_CheckNexon`：`AccountHandler.cs:58-63` 同样的 `long.Parse(parts[0])`，`0` 合法，同样错号。

⇒ **"空票"只是卡住，"0 票"是错号。** 后者更难查（会表现为"数据全空/进度不对"，而不是"卡住"）。**必须显式注入 NpSN。**

### ③ `Queuing_ProcessWaitingQueue` 在"什么都没有"时**会回空 `EnterTicket`**（Shittim 自带的漏洞）

`[源码实测]` `QueuingHandler.cs:105-109`：

```csharp
response.WaitingTicket = request.WaitingTicket;
response.EnterTicket = request.NpSN != 0
    ? Convert.ToBase64String(Encoding.UTF8.GetBytes($"{request.NpSN}/{request.NpToken}"))
    : string.IsNullOrEmpty(request.AuthTicket) ? request.WaitingTicket : request.AuthTicket;
```

三分支全落空（`NpSN==0` 且 `AuthTicket` 空 且 `WaitingTicket` 空）⇒ `EnterTicket = null` ⇒ **JSON 里整个字段消失** ⇒ **客户端被扣在排队弹窗上，永不发游戏协议**。

**这正是本轮卡点最像的一条**：如果国服客户端在 `Auth` 前发过一次 `ProcessWaitingQueue`，而我们的 bridge 把它 `_forward` 到 404（`cn_bridge_v5.py:276-279`），客户端连"空票"都拿不到；如果 bridge 改成合成但不填字段，那就是**收到一张空票**。**两种都卡住。**

⇒ 规格：**`ProcessWaitingQueue` 的 `EnterTicket` 必须无条件铸，不许继承请求值。**（我们的 L0 代码正是这么写的。）

### ④ `TicketSequence = 0` 会被序列化吞掉

见 §1.5 的 ⚠。`GatewayController.cs:122-128` + `:118` 注释。

### ⑤ 四个 Queuing 协议**不能**回 `SessionKey`

`[源码实测]` `GatewayController.cs:318-322` `ShouldEchoSessionKey` 只含 `Account_Auth` / `Account_Auth2` / `ProofToken_RequestQuestion` / `ProofToken_Submit`。
多回一个 `SessionKey` 不一定会炸，但**与官方形态不符**，且会让客户端提前进入"有会话"状态（`Packet.cs:18` 注释：官方只在带 `SessionKey` 时才带顶层 `AccountId`）。

### ⑥ `Queuing_*` 是**免会话**协议，但我们的合成请求可以不带会话

`[源码实测]` `SessionKeyService.cs:19-22` 四个 Queuing 全在 `_publicProtocols` 里 ⇒ `ValidateRequest` 直接 `return true`（`:116-117`）。
⇒ **L1 合成请求里不需要塞 `SessionKey`**（塞了反而可能触发 `GetAuthenticatedUser` 校验失败、回 `InvalidSession`、客户端回标题）。

### ⑦ 别把 `Queuing_Ping` 当协议接

见 §4.3。它是 HTTP GET（`GatewayController.cs:150-152`），**让 bridge 放行到 `_forward` 反而是对的**——`/api/Queuing/Ping` 是 Shittim 现存路由里**唯一**能接住转发的那条。

---

## 7. 验证步骤（全部离线可读，不连服务器）

| # | 检查 | 期望 | 若不符 |
|---|---|---|---|
| 1 | `api_all_requests.log` 里 `protocol_name` 是否出现 `Queuing_*` | 出现 ⇒ 前提假设成立，本规格直接可用 | 未出现 ⇒ 客户端没走队列，卡点不在 Queuing，回 `report\42` §5 的 D1/D2 |
| 2 | 出现的那条 `resp_code` / `resp_len` | 若 `404` / `resp_len≈0` ⇒ 命中§6-③ 的推论 | — |
| 3 | 接管后同一 `protocol_name` 的 `resp_len` | 应 > 150 B（有票） | 若仍小 ⇒ 合成分支没命中，查 `NAME_TABLE`（`rec['queue_ticket']` 没写就说明没进分支） |
| 4 | `ba_raw.log` 里下一次出现的协议名 | 应为 `Account_CheckYostar` / `Account_CheckNexon` / `Account_Auth` 之一 | 若变成别的（如 `Account_GetIdCardInformation`）⇒ 走 §4.4，补实名认证 |
| 5 | `POST /log`（`ServerInfoController.cs:47`） | 无 | 有 ⇒ 客户端抛异常，读 `Type`/`Message`，那里写死了死因 |

---

## 8. 未找到 / 推断标注

| 项 | 状态 |
|---|---|
| 客户端侧 `AllowedSequence` vs `TicketSequence` 的**比较代码** | **未找到**（不在快照里；`[推断]` 依据 `QueuingHandler.cs:63` 注释） |
| 国服客户端是否真的发 `Queuing_*` | **未验证**（`srv-ops` 正在查） |
| 国服 `Queuing_*` 请求的真实字段（是否带 `ClientGeneratedKey`） | **未验证** |
| `EncryptedSqlCipherKey` 是否被客户端硬性需要 | **未验证**（依赖 `ExcelDbSqlCipherKey` 与客户端 ExcelDB 是否同源） |
| `HandlerManager.Dispatch` 是否会调 `ValidateRequest` | **未找到**（类不在快照；`[推断]` 会，因为 `_publicProtocols` 白名单否则毫无意义） |
| `Queuing_Ping` 在国服的真实路径形态 | **未验证**（`[推断]` `/api/queuing/ping`；ASP.NET 路由默认大小写不敏感，故应能命中 `api/Queuing/Ping`） |

**只写入了本文件。** 未修改 `report\` 下任何既有文件（含 `report\04`，其错误在 `report\42` §4.5 与本报告 §4.3 以"更正说明"形式记录），未修改 `report\_tmp\shittim\src\` 下任何源码。
