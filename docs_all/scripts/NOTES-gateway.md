# /api/gateway 协议笔记（实测 + 源码核对）

> ⚠️ **本文顶部两条「覆盖早前结论」——早前结论作废，以此为准。**

## 覆盖早前结论（1/2）

**❌ 作废：**「`api/{path1}/{path2}` 要三段，所以 `/api/state` 返回 404」
**✅ 更正：** `GatewayController.cs:101` 是 `[Route("api")]`、`:157` 是 `[HttpPost("gateway")]`，
`POST /api/gateway` **只有两段，完全合法**，路由没毛病。
**`/api/state` 404 的真正原因是：Shittim 里根本没有 `state` 这个动作**，不是路由段数问题。

## 覆盖早前结论（2/2）

**❌ 作废：**「`global-metadata.dat` 里那把 PEM 是证书 pin」
**✅ 更正：** 它是**网关握手用的 RSA 公钥**（`ClientMetadataPatchService.cs:14-18`），
不是 TLS 证书 pin。它的用途是加密 `Queuing_GetCryptoKeys`(50001) 的 key/IV。

---

## 结论：路由存在，吃 FlatBuffers 的 `.mx` 文件，不是 JSON

| 请求 | 结果 |
|---|---|
| `GET /api/Queuing/Ping` | **200**，body = `"Pong"` |
| `GET /api/gateway` | **200**，`Content-Length: 0` |
| `POST /api/gateway`（无 body / 无 Content-Type） | **500**，0.002s |
| `POST /api/gateway` + `application/x-www-form-urlencoded` | **400**，body=`Expecting an mx file`，0.002s |

## 500 的原始异常（Shittim 日志原文）
```
System.InvalidOperationException: This request does not have a Content-Type header.
Forms are available from requests with bodies like POSTs and a form Content-Type of
either application/x-www-form-urlencoded or multipart/form-data.
   at Microsoft.AspNetCore.Http.Features.FormFeature.ReadForm()
   at Shittim_Server.Controllers.Api.GatewayController.GatewayRequest()
      in /root/bapatch/shittim88/Shittim-Server/Controllers/Api/GatewayController.cs:line 160
```

## 判读
- `GatewayController.GatewayRequest()` 先 `ReadForm()`，再从表单里取一个 **`.mx`（FlatBuffers）文件**。
- 400 的 body 直说 `Expecting an mx file`。
- ⇒ 客户端是 `multipart/form-data`，字段内是 flatbuffer 二进制。
- 该路由**不阻塞**：所有打法毫秒级返回。

---

# 判据清单（血泪教训，务必先读）

## 规则 1：日志要问「什么时机写入」
- `tcp-access.log`（stream 层）是**会话结束时**才落一行。
  ⇒ **不能用它否定一条「一直 ESTAB」的长连接**（它还没结束，自然没日志）。
- `access_log`（http 层）也是请求结束后写。
- **要判断「包有没有到我们」，只认 pcap**（逐包，不受会话状态影响）。

## 规则 2：`mark=262253` 只证明手机侧规则匹配，不证明包到了我们
```
ipv4 2 tcp 6 ESTABLISHED src=192.168.0.5 dst=39.174.179.5 sport=36690 dport=443
     src=<SERVER_IP> dst=192.168.0.5 sport=443 dport=36690 [ASSURED] mark=262253 use=2
```
实测：`sport=36690` 在 `r_013747.pcap` 与 `allport_020316.pcap` 里 **0 包**。
⇒ conntrack 有 `mark` + `reply src` 改写，**不等于**包真的发到了 `<SERVER_IP>`（可能在出网路径被代理 App 截走）。
⇒ **判断连接有没有到我们，只认 pcap 里有没有这个 5 元组的包。**

## 规则 3：`tcp-access.log` 记的是「上游」，不是「客户端原始目的地址」
被接管的连接上游写 `127.0.0.1:8443`，**永远不会出现** `39.174.179.5`。
⇒ `grep 39.174.179.5 = 0` 对「被劫持 / 被绕过」两种情形**都成立**，无区分力。

## 规则 4：用词要精确
- ✅「读了 DTO A」= `GET gsqc-api/api/state`
- ✅「走了网关业务握手」= `POST gsqc-api/api/gateway`（multipart + `.mx`）
- ❌ 不要用含糊的「调网关」

---

## 其它路由实测（同批）
```
POST /api/Queuing/GetAuthTicket  → 404
POST /api/Account/CheckYostar    → 404
POST /api/gateway/Queuing        → 404
POST /gateway                    → 404
```
⇒ 只有 `/api/gateway` 是业务入口；协议号（如 `Account_CheckYostar`）走 `POST /api/gateway` 的信封，不是 URL 路径。
`GET /api/Queuing/Ping → "Pong"` 证明 `Queuing` 控制器是活的。

---

# Shittim 侧关键配置（Config/Config.json → ServerConfiguration）

```json
"GatewayRsaPrivateKeyPem": "",      // 空
"GatewayRsaPrivateKeyPath": "",     // 空 → 回退到 Config/GatewayPrivateKey.pem
"GatewayRsaPublicKeyPem": "",       // 空
"GatewayRsaPublicKeyPath": "",      // 空 → 回退到 Config/GatewayPublicKey.pem
"BypassAuthentication": true,       // 已是 true，认证环已绕过
"SelectedAccountId": 0,
"UseEncryption": false,
"EnableGateway": true,
"PacketLogging": { "RequestPacket": true, "ResponsePacket": false, "WireDump": true }
```

## 密钥现状与硬坎
```
旧：Config/GatewayPrivateKey.pem  1704 B  PKCS#8  2048 bit
    Config/GatewayPublicKey.pem    451 B          2048 bit     （配对 md5 一致）
新：Config/GatewayPrivateKey4096.pem  3268 B  52 行  4096 bit
    Config/GatewayPublicKey4096.pem    800 B  14 行  4096 bit  （配对 md5 1c3105786abf87621183b8faba133b86）
```
**客户端 metadata 里那把是 4096 位、且位于定长空洞** ⇒ 只能**等长**替换 ⇒ 必须用 4096 位的钥匙。
**切换顺序（不可颠倒）**：造 4096 → Shittim 指向 4096 → metadata 等长替换 → 重打包 APK。
**现在只做了第一步，`Config.json` 尚未改。**

## WireDump
DLL 里有 `DumpedDir` / `packetSettings` / `get_WireDump` 字段，
但 `Config/` 下**没有任何 dump 目录/文件**（说明还没处理过合法 gateway 请求）。
`PacketLogging.RequestPacket = true` 一旦有真实请求，应会 dump 出请求包 —— 届时先找 `DumpedDir` 的默认值。
