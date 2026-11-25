# AUDIT_PROTO_LAYER_20261118 — 协议/传输层只读安全审计

> 时间：2026-11-18 00:50–01:2x | **严格只读**：仅 read/grep，未改任何代码、未编译、未碰服务端与手机
> 唯一写入：本文件
> 审计对象（两条真实链路，**先分清再用结论**）：

| 链路 | 实际处理代码 | 用什么信封 | 与本审计的关系 |
|---|---|---|---|
| **国服客户端 → 桥接** | Python：`work\ba\server\deploy\_scratch\rlf2\rb\account_auth_probe.py`（136,894 B，线上同名脚本）+ `report\_tmp\mx_crypto\cn_cipher.py` | `multipart` 的 `protocol`/`encode`/`packet` + `[u32][gzip(IV16+ct+KEY32)]` | **lead 描述的正是这条**，A/B 的绝大多数问题在这条上 |
| **桥接 → Shittim** | C#：`work\ba\srv_src\Shittim-Server\Controllers\Api\GatewayController.cs` | multipart 的 `mx` 文件 + `[crc][typeConv][keyLen][ivLen][key][iv]` + gzip/XOR | 实际也接收网络输入（`/api/gateway`），本次一并审计 |

> ⚠️ **范围提示（重要）**：lead 指定的 `Core\NetworkProtocol\` 目录里**只有 Handlers**（66 个业务文件，`ls` 实测），
> 不做任何报文解析——它只处理"已经反序列化好的请求对象"。真正的解析全部在
> `Controllers\Api\GatewayController.cs`（C#）与上面的 Python 桥接里。**下面把两者分开写，避免把结论安错对象。**

---

## A. 请求解析

### A1. `protocol` / `encode` / `packet` 三字段的缺失/空/超长/非法 base32

| # | 结论 | 证据 | 严重度 | 等级 |
|---|---|---|---|---|
| A1-1 | **Python 桥接不校验任何字段格式**，把整个 body 直接交给 `_bridge(body, rec)`；字段抽取失败时的报错会以 **500 + `repr(e)`** 返回客户端 | `account_auth_probe.py:1204-1224`<br>`1206: n = int(self.headers.get('Content-Length') or 0)`<br>`1207: body = self.rfile.read(n) if n else b''`<br>`1222: except Exception as e:`<br>`1224: code, resp = 500, json.dumps({'error': repr(e)}).encode()` | 中危 | 已证实 |
| A1-2 | **`Content-Length` 非数字时，异常发生在 `try` 之外**（`try` 从 :1215 才开始）⇒ 根本不是 500，而是 handler 抛异常、连接被直接掐断，客户端拿到空响应 | 同上 `1206` vs `1215` | 低危 | 已证实（代码位置） |
| A1-3 | `protocol` 非法 base32 / 未知令牌：**没有"拒绝"路径的证据**——映射表是普通 dict（`account_auth_probe.py:198-203` 的 `EXTRA_TOKENS`/token→name 表），查不到时落到 `Unknown`（`1407` 有 `if name and name != 'Unknown'` 的兜底）⇒ **不会抛未捕获异常，但会被当成 `Account_LoginSync` 之类继续处理**（`1407: _nm = name if (name and name != 'Unknown') else 'Account_LoginSync'`） | `1407` | 中危 | 已证实 |
| A1-4 | 请求体**没有大小上限**：`self.rfile.read(n)` 按客户端给的 `Content-Length` 一次性读进内存，读之前不比较任何上限 | `1206-1207` | **高危** | 已证实 |
| A1-5 | C# 侧：`Request.Form.Files.GetFile("mx")` 缺失 → 400 明文文本，**不回 JSON**（无害但泄露是 Kestrel，不是堆栈） | `GatewayController.cs:160-166` | 低危 | 已证实 |

### A2. 未知 `protocol` 令牌 → handler 映射

| # | 结论 | 证据 | 严重度 | 等级 |
|---|---|---|---|---|
| A2-1 | Python：未知令牌**不抛异常**（dict `.get` + `Unknown` 兜底），但会**静默降级为别的协议**（见 A1-3）——比抛异常更危险（会拿错误 DTO 去构造响应） | `account_auth_probe.py:1407` | 中危 | 已证实 |
| A2-2 | C#：`ReadProtocol` 用 `Enum.TryParse`，失败返回 null → 走 `CreateProtocolErrorResponse`（**有**兜底，不抛） | `GatewayController.cs:424`（`return Enum.TryParse<Protocol>(...)`）+ `:180-186` | 低危 | 已证实 |

### A3. 请求体大小上限

| # | 结论 | 证据 | 严重度 | 等级 |
|---|---|---|---|---|
| A3-1 | **Python 桥接：无任何上限**（`read(Content-Length)` 直接进内存） | `account_auth_probe.py:1206-1207` | **高危** | 已证实 |
| A3-2 | **C#：全仓 grep 无 `MaxRequestBodySize` / `RequestSizeLimit` / `AddRateLimiter`**，只有 `builder.Services.AddControllers()` ⇒ 仅靠 Kestrel 默认 30 MB 兜底，且无法按路由收紧 | `GameServer.cs:89`（唯一命中）+ 全仓 grep 0 命中 | 中危 | 已证实 |

---

## B. 报文解码

### B1. `[u32 LE len][gzip(IV16+ct+KEY32)]` 的 `len` 与真实长度不符

| # | 结论 | 证据 | 严重度 | 等级 |
|---|---|---|---|---|
| B1-1 | `len` 只被读出来**做告警比较**，**不参与任何边界计算**；实际长度以 `gzip.decompress` 解出为准 ⇒ **没有越界读**（Python 切片安全），但也**没有校验**（声明 100 实际 4 GB 也照收） | `cn_cipher.py:52-58`<br>`53: declared = struct.unpack("<I", raw[:4])[0]`<br>`54: inner = gzip.decompress(raw[4:])`<br>`56-59: if len(inner) != INNER_LEN: print("[warn] ...")` | 中危 | 已证实 |
| B1-2 | C# 侧 `ReadExact` **有**截断校验（读不满就抛 `Truncated gateway ...`） | `GatewayController.cs:450-452` | 低危（做对了） | 已证实 |

### B2. 解压炸弹

| # | 结论 | 证据 | 严重度 | 等级 |
|---|---|---|---|---|
| B2-1 | **Python：完全无解压上限**，`gzip.decompress()` 一次性把解压结果全部读进内存（1 KB → 数 GB 可直接打爆进程） | `cn_cipher.py:54` | **高危** | 已证实 |
| B2-2 | **C#：同样无上限**，`GZipStream.CopyTo(MemoryStream)` 全量展开、无 `maxBytes`、无 `Length` 预检 | `GatewayController.cs:457-463`（`return payloadMs.ToArray();`） | **高危** | 已证实 |
| B2-3 | 三种解包变体（xor-length / clear-length / xor-no-length）**都会各解一次**，等于把 1 次解压炸弹放大成最多 3 次 | `GatewayController.cs:469-493` | 中危（放大） | 已证实 |

### B3. AES 参数 / padding / 完整性

| # | 结论 | 证据 | 严重度 | 等级 |
|---|---|---|---|---|
| B3-1 | 请求 IV = 包内前 16 字节（**每包随机**，客户端生成）；响应 IV = **硬编码常量 `JOSYdf8ys97uhFYS`** | `cn_cipher.py:8-9` 注释与 `33-34` 常量；`patch_relay2` 侧同一常量 | 中危 | 已证实 |
| B3-2 | **padding 不校验**：`pkcs7_unpad` 在尾部不是合法填充时**原样返回数据**，不抛错 | `cn_cipher.py:70-74`<br>`72: if 1 <= n <= bs and data.endswith(bytes([n]) * n): return data[:-n]`<br>`74: return data`（失败即返回原文） | 中危 | 已证实 |
| B3-3 | **无 MAC / 无认证加密**：纯 AES-256-CBC，无 HMAC、无 AEAD、无 CRC 校验（C# 侧读出的 `crc` 字段**从未被验证**） | `cn_cipher.py:82-88`；`GatewayController.cs:370`（读 `crc`）、全文件无 crc 比较 | **高危** | 已证实 |
| B3-4 | **密钥明文附在包尾（`KEY32`）** ⇒ 加密**形同虚设**：任何人拿到包即可解密，也可伪造任意包 | `cn_cipher.py:9-10`、`63-67`（`return inner[:16], inner[16:-32], inner[-32:]`） | **高危** | 已证实（**设计如此**：客户端就是这么发的，见 `report\35`；不是服务端引入的 bug，但服务端**完全接受**这种"自带钥匙"的包，等于对伪造零防护） |

### B4. 解密后的 protobuf/flatbuffer（字段缺失/超范围/未知字段）

| # | 结论 | 证据 | 严重度 | 等级 |
|---|---|---|---|---|
| B4-1 | 国服这条链路实际是 **JSON**（`decode_packet` 后 `json.loads`），不是 protobuf；未知字段由 Newtonsoft/`json` 容忍，**字段缺失 → DTO 默认值**，不抛 | `cn_cipher.py:91-104`；`GatewayController.cs:215-221`（`JsonConvert.DeserializeObject` + catch → Error 信封） | 低危（做对了） | 已证实 |
| B4-2 | **超范围没校验**：数值只做类型转换，没有业务范围检查（例：`AccountServerId`、货币数量、`Level` 直接进 DB 查询/写回）；这属于业务层，但入口没有任何 schema 白名单 | `GatewayController.cs:215`；Handlers 里 `request.*` 直接使用（如 `AccountHandler.cs` 全文） | 中危 | 推断（未逐 handler 验证） |

---

## C. 异常与信息泄露

| # | 结论 | 证据 | 严重度 | 等级 |
|---|---|---|---|---|
| C1 | **畸形包 → 500 + 异常原文**（`repr(e)` 含 Python 异常消息，可能带路径/解析位置），并且会写进 `api_all_requests.log` 的 `err` 字段 | `account_auth_probe.py:1222-1224` | 中危 | 已证实 |
| C2 | **无全局异常处理中间件**（C# 侧）：只有 `GatewayController` 内部三段 try/catch；其它 controller（`ServerInfoController` 等）抛异常走 Kestrel 默认 500（开发环境会带堆栈，生产默认不带） | `GatewayController.cs:283-301`（局部 catch）；`GameServer.cs:89` 只有 `AddControllers()` | 中危 | 已证实（局部 catch）/ 推断（Kestrel 默认行为） |
| C3 | **日志泄露密钥与会话**（最严重的一条）：`rec` 里直接记录**完整请求头**、body 前 1024 字节，以及解密中间产物 `req_key` / `req_iv` / `req_frag_head`；实测日志里就有 `<MxToken>` 明文 | `account_auth_probe.py:1211`（`'headers': dict(self.headers.items())`）、`1213`（`body_printable`）；真实日志样本：`api_all_requests.log` 的 `"req_key":"MmY0..."`、`"req_frag_head":"...\"MxToken\":\"d2528ad0-...\""` | **高危** | 已证实 |
| C4 | C# 侧把**完整请求明文**打到 Debug 日志（含 `SessionKey`），并把响应明文也打出来 | `GatewayController.cs:199`（`_logger.LogDebug("Request {ProtocolInt} / {Protocol}: {Payload}", ..., payloadStr)`）、`:275`（`"Response: {Rsp}"`） | 中危 | 已证实（仅 Debug 级别；生产若开 Debug 即高危） |

---

## D. 防护

| # | 结论 | 证据 | 严重度 | 等级 |
|---|---|---|---|---|
| D1 | **无限流、无单 IP 并发限制**：Python 桥接是 `http.server`（单进程/多线程取决于 `ThreadingHTTPServer`，未见限流）；C# 侧全仓无 `RateLimiter` | `account_auth_probe.py:1165`（`BaseHTTPRequestHandler`）；全仓 grep `AddRateLimiter` 0 命中 | 中危 | 已证实 |
| D2 | **无重放保护**：请求里的 `Hash` 字段（`req_frag_head` 里可见）只被转发/记录，**没有任何 nonce/时间窗/去重表**；同一份抓包原样重放会被再执行一次（对 `*_Reward`、`Mail_Receive` 这类协议就是重复发奖） | `account_auth_probe.py:444`（`cn_hash_mode`）与 `:1211-1213`（只记录）；全文件无 "replay"/"nonce"/"used" 计数 | **高危** | 推断（强）——代码里没看到任何去重，但未做端到端重放实验 |
| D3 | **会话与请求没有绑定**：`SessionKey` 是请求体里的一个 JSON 字段，桥接/Shittim 都不校验"这个请求是否属于这个 socket/IP"（HTTP 无连接语义），⇒ **一个会话可被并发重放/多点使用** | `GatewayController.cs:262-263`（回显 `payload.SessionKey`）；`AccountHandler` 用 `request.SessionKey` 查会话 | **高危** | 推断（强） |
| D4 | `Account_Nickname` 等**改名类协议没有频率限制**，且 `HandleMessage` 直接写库 | `AccountHandler.cs:253-269`（Nickname handler） | 中危 | 推断 |

---

## 附：C# 侧已做对的三处（避免只列缺点）

1. `ReadExact` 对截断有校验（`GatewayController.cs:450-452`）；
2. `DecodeGatewayPayload` 对最小长度有校验（`:367-368`、`:378-379`）；
3. `ReadProtocol` 未知协议走 Error 信封而不是抛异常（`:424` + `:180-186`）。

---

## 总体风险判断（一句话）

> **高危三条**：①Python 桥接与 C# 网关**都没有解压体积上限**（gzip 炸弹可一键打爆内存）；
> ②**桥接日志明文记录 `MxToken` 与每包 AES key**（`api_all_requests.log` 已证实）；
> ③**无重放保护 + 会话不绑定连接**（奖励类协议可原样重放）。
> 叠加"**密钥明文附在包尾**"这一设计，**这条链路的加密只防旁观、不防伪造**；
> 真正的安全边界只能靠"服务端不信任任何请求字段"来守，而当前代码**没有任何入口校验层**（无大小限制、无 schema 白名单、无速率限制）。
