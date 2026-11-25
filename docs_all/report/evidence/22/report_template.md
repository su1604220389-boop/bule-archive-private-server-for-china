# 22 真实上游接口取证（state-api / gsqc-api / 卡密 SDK / static）

> **取证时间**：2026-11-14 01:39 – 01:50 CST（UTC 2026-11-13 17:39 – 17:50）
> **取证机**：本机 Windows 直连，**无代理**（`netsh winhttp show proxy` → `Direct access (no proxy server)`，`HTTP_PROXY / HTTPS_PROXY / ALL_PROXY` 均为空）
> **工具**：`curl 8.22.0 (Windows) libcurl/8.22.0 Schannel`、`OpenSSL 3.5.2`、`Resolve-DnsName`（DNS = 223.5.5.5 public1.alidns.com）
> **走了哪条路**：**方案 A（本机直连）一次成功**。方案 B（服务器 iptables 临时 RETURN）**完全没用**，服务器全程未被登录；方案 C 也没用。
> **一句话结论**：三条真实上游（state-api / gsqc-api / static）**全部依赖 SNI 选证书**，不带 SNI 只能拿到别人的默认证书；`state-api /api/state` 的真实应答是 **HTTP 200 + 0 字节**（不是我们编的那 180 B）；`gsqc-api /api/state` 是**真的活网关**，返回 214 B 的 state 结构体，但缺平台号时只回 `Msg:"platform id error"`；`example.com` 的 A 记录就是**我们自己那台 <SERVER_IP>**，不是上游；`static` 根路径的 200 列表是**十月的旧缓存**，回源节点直接 403。

---

## 0. 先看这三条（会直接改我们的做法）

### 0.1 「客户端不带 SNI」这个假设 **不成立**

| 验证 | 结果 |
|---|---|
| `openssl s_client -noservername` 连 state-api | 握手成功（TLS1.3），但拿到**阿里云兜底证书** `CN=*.certfallback.com`，主机名校验 **62 hostname mismatch** |
| 同上连 gsqc-api | 拿到**银联默认证书** `CN=*.unionpayintl.com`，校验 **62** |
| 同上连 static | 拿到**百度默认证书** `CN=*.a.bdydns.com`，校验 **62** |
| state-api 用**未知 SNI**（`example.com`） | 直接 **fatal alert 40 handshake_failure**，连证书都不给 |
| 同样请求换成**正确 SNI** | 三个域名全部拿到 `CN=*.bluearchive-cn.com`（DigiCert RapidSSL），`-verify_hostname` 返回 **0 (ok)** |

**结论**：上游是「SNI → 选哪张证书」的模型。一个**真的不带 SNI** 的客户端去打真实上游，必然拿到 `*.certfallback.com` / `*.unionpayintl.com` / `*.a.bdydns.com` 这三张不匹配的证书，任何做主机名校验的 TLS 栈都会失败。

所以只有两种可能：① 客户端其实带 SNI（与 `23-主线改判` 里 pcap 353 B ClientHello 明示含 SNI 一致）；② 我们之前那条「无 SNI」的观测来自**另一条连接**。第 ③ 种更贴近真相的可能见 0.3。

### 0.2 `state-api /api/state` 的真实应答是 **200 + 空 body**

```
HTTP/1.1 200 OK
Server: Tengine
Content-Length: 0
Connection: keep-alive
Date: Fri, 13 Nov 2026 17:39:17 GMT
Via: cache53.l2et15-7[23,0], cache20.cn1447[35,0]
Timing-Allow-Origin: *
EagleId: 6f034f2817945915575665447e
```

- body：**0 字节**（sha256 = `e3b0c442...b855`，即空串）。
- 复测 7 次（含 `?platform=1/2/3`、`?platform_id=1`、`?platformId=1`、加 Unity UA、加 `version=`）**全部 200 / 0 字节**。
- `POST /api/state` → **404**（该路由只吃 GET）。
- 根路径 `/` 与 `/api/` → **404 text/plain "404 page not found"**（18 B，带 `x-alicdn-da-ups-status: endOs,0,404`）。

也就是说：**真实上游在这个 URL 上什么都不回**，我们那 181 B 的假应答在「内容量」上比真实上游还多。`state-api` 到底是不是客户端启动第一跳、客户端拿到空 body 后会怎样，需要拿 pcap 的 reqlen/headers 再核（见 §8.3 的边界说明）。

### 0.3 `example.com` 不是上游，是**我们自己那台服务器**

| 项 | 值 |
|---|---|
| A 记录 | `example.com → <SERVER_IP>`（= SSH 目标机，无 CNAME） |
| 带 SNI=example.com 时给什么证书 | `CN=example.com`，Issuer `TLC DV TLS CA`（泰尔认证，Certum 链），有效期 2025-12-12 → 2026-12-12 |
| **不带 SNI** 时给什么证书 | `CN=*.bluearchive-cn.com`，Issuer **`CN=BA Test Root CA, O=BA`**（自签），SAN 含 `state-api / gsqc-api / gs-api / static` |
| `/sdk/` | `200 {"Code": 200, "Msg": "OK", "Data": {}}`（38 B，nginx） |

**这就是「客户端不带 SNI 也能通」的真相**：只要 DNS/hosts 把 `*.bluearchive-cn.com` 指到我们这台机器，nginx 的默认 server 会**无差别**丢出 `CN=*.bluearchive-cn.com` 的 BA Test 证书——无论带不带 SNI、带什么 SNI。那条「无 SNI 的 ClientHello」极可能就是客户端在打**我们**，而不是打真实上游。

---

## 1. 摘要表

| # | URL | 状态码 | Content-Type | body 大小 | 证书 Subject | 证书 Issuer |
|---|---|---|---|---|---|---|
| 1 | `https://state-api.bluearchive-cn.com/api/state` | **200** | *（无）* | **0 B** | `CN=*.bluearchive-cn.com` | `RapidSSL TLS RSA CA G1`（DigiCert） |
| 2a | `https://gsqc-api.bluearchive-cn.com/` | **404** | `text/plain` | 18 B（`404 page not found`） | `CN=*.bluearchive-cn.com` | 同上 |
| 2b | `https://gsqc-api.bluearchive-cn.com/api/state` | **200** | `application/json; charset=utf-8` | **214 B**（见 §3.2） | 同上 | 同上 |
| 3a | `https://example.com/sdk` | **301** | `text/html` | 162 B（nginx 跳转页） | `CN=example.com` | `TLC DV TLS CA`（泰尔 / Certum 链） |
| 3b | `https://example.com/sdk/` | **200** | `application/json` | 38 B（`{"Code": 200, "Msg": "OK", "Data": {}}`） | 同上 | 同上 |
| 3c | `https://example.com/api/` | **404** | *（无）* | 0 B | 同上 | 同上 |
| 4 | `https://static.bluearchive-cn.com/` | **200**（缓存节点）/ **403**（回源节点） | `application/xml` | 408 560 B（S3 桶列表）/ 376 B（AccessDenied） | `CN=*.bluearchive-cn.com` | 同上 |

补充：三条 `bluearchive-cn.com` 子域共用**同一张**证书（SHA256 指纹 `E4:06:EE:F4:88:05:3F:CC:E8:03:CB:E6:0E:D1:61:7B:9E:7C:D4:DB:71:E0:2E:E0:15:B2:6C:1F:E6:C5:7B:12`），通配 `*.bluearchive-cn.com`，**没有单独给 state-api / gsqc-api 的证书**。

---

## 2. 方法、命令与边界

### 2.1 实际执行的命令（原始）

```powershell
# 方案 A：本机直连（首选，已成功）
curl.exe -sS -m 20 -D - "https://state-api.bluearchive-cn.com/api/state" -o state_real.json
curl.exe -sS -m 20 -D - "https://gsqc-api.bluearchive-cn.com/" -o gsqc_real.txt
curl.exe -sS -m 25 -D - "https://gsqc-api.bluearchive-cn.com/api/state"
curl.exe -sS -m 25 -D - "https://example.com/sdk"          # 301
curl.exe -sS -m 25 -D - "https://example.com/sdk/"        # 200
curl.exe -sS -m 25 -D - "https://example.com/api/"        # 404
curl.exe -sS -m 25 -D - "https://static.bluearchive-cn.com/" -o static_list.xml

# TLS / 证书链 / SNI 依赖
openssl s_client -connect <host>:443 -servername <host> -showcerts -state
openssl s_client -connect <host>:443 -servername <host> -verify_hostname <host>
openssl s_client -connect <host>:443 -noservername -showcerts -state
openssl s_client -connect <host>:443 -noservername -verify_hostname <host>
openssl s_client -connect <host>:443 -servername example.com        # 未知 SNI
openssl s_client -connect <SERVER_IP>:443 -servername <host>     # 验我们自己的机器

# DNS
Resolve-DnsName <host>        # A / CNAME / TTL
nslookup <host>
```

### 2.2 边界（必须写清楚，避免把结论用超）

1. **没有抓包**。本次只从**服务器侧断言**反推客户端行为，没有客户端 pcap。关于「客户端到底带不带 SNI」，本文给的是「上游依赖 SNI」的硬证据 + 与 23 号报告 pcap 的交叉印证，**不是**本轮抓到的 ClientHello 原文。
2. **我们复现不了客户端的原始请求头**。`state-api` 的「空 200」是在我们发出的这些请求（GET，各种 platform/version 参数、Unity UA）下观测到的；如果真实客户端带了别的头（鉴权头/设备头）导致后端走另一分支，我们看不到。这一点已在 §8.3 明确标为「不确定」。
3. 全程只读：只有 `GET`，外加两条 `POST`（用于确认路由不存在，均返回 404，未产生副作用），没有写任何服务器配置。

---

## 3. 每个 URL 的完整原始记录

### 3.1 `https://state-api.bluearchive-cn.com/api/state`

**状态行 / 全部响应头**

```
HTTP/1.1 200 OK
Server: Tengine
Content-Length: 0
Connection: keep-alive
Date: Fri, 13 Nov 2026 17:39:17 GMT
Via: cache53.l2et15-7[23,0], cache20.cn1447[35,0]
Timing-Allow-Origin: *
EagleId: 6f034f2817945915575665447e
```

- 远端 IP：`111.3.79.58`（CNAME 到 `*.w.kunluncan.com` 的 8 个 A 记录之一）
- **body：0 字节**（没有 `Content-Type`，因为根本没有 body）
- 复测（同一 URL，仅换参数/UA）：

| 请求 | 结果 |
|---|---|
| `GET /api/state` | `200`，`Content-Length: 0` |
| `GET /api/state?platform=1` / `=2` / `=3` / `platform_id=1` / `platformId=1` / `platform=2&version=1` | 全部 `200`，`Content-Length: 0` |
| `GET /api/state` + `User-Agent: UnityPlayer/2021.3.16f1 (UnityWebRequest/1.0, libcurl/7.84.0-DEV)` | `200`，`Content-Length: 0` |
| `POST /api/state`（空 body / JSON `{"platform":1}`） | **`404`** `text/plain`，18 B `404 page not found` |
| `GET /` | `404` + `x-alicdn-da-ups-status: endOs,0,404`，18 B |
| `GET /api/` | `404`，同上 |

**结论**：这个路由存在（GET 返回 200 而不是 404），但**在我们所有请求形态下 body 恒为空**。

### 3.2 `https://gsqc-api.bluearchive-cn.com/` 与 `/api/state`

**2a. 根路径**

```
HTTP/1.1 404 Not Found
Content-Type: text/plain
Server: TencentEdgeOne
Content-Length: 18
Connection: keep-alive
Date: Fri, 13 Nov 2026 17:39:21 GMT
EO-LOG-UUID: 6116895958664533795
EO-Cache-Status: MISS
```

body（18 B）：`404 page not found`（Go `http.NotFound` 的默认文案）

**2b. `/api/state`（本次最有价值的一条）**

```
HTTP/1.1 200 OK
Content-Type: application/json; charset=utf-8
Server: TencentEdgeOne
Content-Length: 214
Connection: keep-alive
Date: Fri, 13 Nov 2026 17:39:21 GMT
EO-LOG-UUID: 6274926345958253779
EO-Cache-Status: MISS
```

body 原文（214 B，sha256 `5EEF7965C89A79CB35C0F8E5083A09468077A5CE91338DE4ABE6F5D64AB76CD0`）：

```json
{"CallbackUrl":"","CustomerServiceUrl":"","AddressablesCatalogUrlRoots":null,"ResourceVersion":"","TableVersion":"","MediaVersion":"","PatchVersion":"","State":0,"Msg":"platform id error","IsOpenPreDownload":false}
```

格式化：

```json
{
  "CallbackUrl": "",
  "CustomerServiceUrl": "",
  "AddressablesCatalogUrlRoots": null,
  "ResourceVersion": "",
  "TableVersion": "",
  "MediaVersion": "",
  "PatchVersion": "",
  "State": 0,
  "Msg": "platform id error",
  "IsOpenPreDownload": false
}
```

- 远端 IP：`39.173.157.74`（TencentEdgeOne，CNAME `*.eo.dnse0.com`）
- **注意**：`POST` 到同一路径 → `404 page not found`；`/api/state/1`、`/api/v1/state`、`OPTIONS` → 全部 404。**只有 `GET /api/state` 这一条路由**。
- 换参数无效：`?platform=1/2/0/android/iOS/ios/cn`、`?platform_id=1`、`?platformId=1`、`?platformid=1`、`?platform=2&platform_id=2`、加 `X-Platform-Id` / `platform-id` / `platformId` / `Platform` 头、加 Unity UA —— **一律同样 214 B 的 `platform id error`**。

### 3.3 `https://example.com/sdk`、`/sdk/`、`/api/`

**3a. `/sdk` → 301**

```
HTTP/1.1 301 Moved Permanently
Server: nginx
Date: Fri, 13 Nov 2026 17:39:22 GMT
Content-Type: text/html
Content-Length: 162
Location: https://example.com/sdk/
Connection: keep-alive
Strict-Transport-Security: max-age=31536000
Alt-Svc: quic=":443"; h3=":443"; h3-29=":443"; ...
```

body（162 B，nginx 默认跳转页）：

```html
<html>
<head><title>301 Moved Permanently</title></head>
<body>
<center><h1>301 Moved Permanently</h1></center>
<hr><center>nginx</center>
</body>
</html>
```

**3b. `/sdk/` → 200**

```
HTTP/1.1 200 OK
Server: nginx
Date: Fri, 13 Nov 2026 17:41:50 GMT
Content-Type: application/json
Content-Length: 38
Connection: keep-alive
Strict-Transport-Security: max-age=31536000
Alt-Svc: quic=":443"; ...
```

body（38 B）：`{"Code": 200, "Msg": "OK", "Data": {}}`

**3c. `/api/` → 404**

```
HTTP/1.1 404 Not Found
Server: nginx
Date: Fri, 13 Nov 2026 17:39:22 GMT
Content-Length: 0
Connection: keep-alive
```

（无 body；nginx 直接 404，不是跳转也不是 JSON）

> `example.com` = `<SERVER_IP>` = 我们的服务器（§0.3）。这三个应答都是**我们自己 nginx 的**，**不能**当作上游情报。

### 3.4 `https://static.bluearchive-cn.com/`

**行为是分节点的**，同一个 URL 会得到两种完全不同的结果：

**4a. 命中旧缓存的边缘节点 → 200 + S3 桶列表（408 560 B）**

```
HTTP/1.1 200 OK
Server: nginx
Date: Fri, 13 Nov 2026 17:39:23 GMT
Content-Type: application/xml
Content-Length: 408560
Connection: keep-alive
Age: 719645
Accept-Ranges: bytes
x-amz-request-id: 6AD4CF01159B393437780697
x-amz-bucket-region: oss-cn-shanghai
x-oss-server-time: 66
Ohc-Global-Saved-Time: Sun, 18 Oct 2026 13:52:01 GMT
Ohc-Cache-HIT: huzcm54 [3], tz2ix50 [4]
Ohc-File-Size: 408560
X-Cache-Status: HIT
```

- 只在 `112.15.33.35`、`112.16.250.35` 这两个节点上复现（强制 `--resolve` 验证）；sha256 `9A07018651CA898628A84D80411BC907F5F385E2CBFD8A933911C774F1B15184`。
- 内容结构（前 4000 字符见附录 E）：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">
  <Name>bluearchive-static</Name>
  <Prefix></Prefix><Marker></Marker><MaxKeys>1000</MaxKeys>
  <IsTruncated>true</IsTruncated>
  <NextMarker>cbt1/AssetBundles/Android/assets-_mx-hexamaps-default-...</NextMarker>
  ...
```

- 统计：桶名 `bluearchive-static`，**1000 条**（`IsTruncated=true`，还有下一页），顶层目录只有 `.well-known/`、`apple/`、`apple-app-site-association`、`cbt1/`；正文全是 `cbt1/AssetBundles/Android/*.bundle`（`_mx-hexamaps` 系列等）。
- **`Ohc-Global-Saved-Time: Sun, 18 Oct 2026 13:52:01 GMT`** —— 这是 26 天前的缓存快照，`Age: 719645s ≈ 8.33 天`。

**4b. 回源节点 → 403 AccessDenied（376 B）**

```
HTTP/1.1 403 Forbidden
Server: AliyunOSS
Date: Fri, 13 Nov 2026 17:41:50 GMT
Content-Type: application/xml
x-amz-request-id: 6AF74BDE3AD86E3236896341
x-amz-bucket-region: oss-cn-shanghai
x-oss-server-time: 15
x-oss-ec: 0003-00000001
Content-Length: 376
Connection: keep-alive
EO-LOG-UUID: 10821529344436083394
EO-Cache-Status: MISS
```

body（376 B）：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Error>
  <Code>AccessDenied</Code>
  <Message>The bucket you access does not belong to you.</Message>
  <RequestId>6AF74BDE3AD86E3236896341</RequestId>
  <HostId>bluearchive-static.oss-cn-shanghai.aliyuncs.com</HostId>
  <EC>0003-00000001</EC>
  <RecommendDoc>https://api.aliyun.com/troubleshoot?q=0003-00000001</RecommendDoc>
</Error>
```

- 当前 DNS 已经只返回 `120.226.195.66`，该节点 10/10 次都是 **403**。

**4c. 前 256 字节 hex（200 那份 body）**

```
3C 3F 78 6D 6C 20 76 65 72 73 69 6F 6E 3D 22 31
2E 30 22 20 65 6E 63 6F 64 69 6E 67 3D 22 55 54
46 2D 38 22 3F 3E 0A 3C 4C 69 73 74 42 75 63 6B
...
```

（`3C 3F 78 6D 6C` = `<?xml`；完整 408 560 B 原文在 `report/evidence/22/A_static_root.body`）

**结论**：`static` 的根路径**不是一个可用的接口**——它只是 OSS 桶的目录列表，而且现在**源站已关（403）**，能看到 200 纯属旧缓存。

---

## 4. 证书链详情

### 4.1 state-api / gsqc-api / static（三个域名同一张叶子证书）

| # | Subject | Issuer | 有效期（UTC） | SAN | CA? | 公钥/签名 |
|---|---|---|---|---|---|---|
| 0（叶子） | `CN=*.bluearchive-cn.com` | `C=US, O=DigiCert Inc, OU=www.digicert.com, CN=RapidSSL TLS RSA CA G1` | 2026-09-04 00:00:00 → **2027-03-11 23:59:59** | `*.bluearchive-cn.com`, `bluearchive-cn.com` | **FALSE** | RSA 2048 / sha256WithRSA |
| 1（中间） | `C=US, O=DigiCert Inc, OU=www.digicert.com, CN=RapidSSL TLS RSA CA G1` | `CN=DigiCert Global Root G2` | 2017-11-02 12:24:33 → 2027-11-02 12:24:33 | 无 | **TRUE**, pathlen:0 | RSA 2048 / sha256 |
| 2（根） | `CN=DigiCert Global Root G2` | `CN=DigiCert Global Root CA` | 2024-01-18 → 2031-11-09 | 无 | TRUE | RSA 2048 |
| 3（**仅 gsqc** 多一张，交叉签名的老根） | `CN=DigiCert Global Root CA` | 自签 | 2006-11-10 → 2031-11-10 | 无 | TRUE | RSA 2048 / **sha1WithRSA** |

- 链长：state-api **3 张**；static **3 张**；gsqc-api **4 张**（比另外两个多一张老根交叉签名）。
- **有中间证书**（RapidSSL TLS RSA CA G1），并且服务器连根都一起发下来了。
- 叶子 SHA256 指纹：`E4:06:EE:F4:88:05:3F:CC:E8:03:CB:E6:0E:D1:61:7B:9E:7C:D4:DB:71:E0:2E:E0:15:B2:6C:1F:E6:C5:7B:12`
- `-verify_hostname` 结果：**0 (ok)**；`-verify` 到根：0 (ok)。

### 4.2 `example.com`（我们自己的机器）

| # | Subject | Issuer | 有效期 | SAN | CA? |
|---|---|---|---|---|---|
| 0 | `CN=example.com` | `C=CN, O=泰尔认证中心有限公司, CN=TLC DV TLS CA` | 2025-12-12 10:21:29 → **2026-12-12 10:21:28**（约 1 个月后到期） | `example.com`, `example.com` | FALSE |
| 1 | `CN=TLC DV TLS CA` | `CN=Certum Trusted Root CA` | 2024-12-17 → 2034-12-05 | 无 | TRUE, pathlen:0 |
| 2 | `CN=Certum Trusted Root CA` | `CN=Certum Trusted Network CA`（Unizeto） | 2023-09-19 → 2028-09-19 | 无 | TRUE |

### 4.3 **不带 SNI** 时实际拿到的证书（关键对照）

| 域名 | no-SNI 时给的证书 Subject | Issuer | 有效期 | 主机名校验 |
|---|---|---|---|---|
| state-api | `CN=*.certfallback.com`（阿里云兜底，杭州） | `GlobalSign GCC R46 OV TLS CA 2025` | 2026-07-30 → 2027-02-14 | **62 mismatch** |
| gsqc-api | `CN=*.unionpayintl.com`（银联） | `DigiCert Basic OV G2 TLS CN RSA4096 SHA256 2022 CA1` | 2026-10-08 → 2027-04-24 | **62 mismatch** |
| static | `CN=*.a.bdydns.com`（百度） | `sslTrus (RSA) OV CA` | 2026-02-09 → 2027-03-07 | **62 mismatch** |
| example.com（我们的机器） | `CN=*.bluearchive-cn.com` | **`CN=BA Test Root CA, O=BA`**（自签） | 2026-11-13 16:49:33 → 2029-02-15 | 62（根不受信）/ 主体名本身匹配 |

> `example.com` 的 no-SNI 证书 SAN = `*.bluearchive-cn.com, bluearchive-cn.com, state-api.bluearchive-cn.com, gsqc-api.bluearchive-cn.com, gs-api.bluearchive-cn.com, static.bluearchive-cn.com` —— 这张就是我们给客户端准备的「一套域名通吃」测试证书。

### 4.4 TLS 参数

| 域名 | TLS1.3 | TLS1.2 | ALPN（offer h2,http/1.1） |
|---|---|---|---|
| state-api | `TLS_AES_128_GCM_SHA256` | `ECDHE-RSA-AES128-GCM-SHA256` | **h2** |
| gsqc-api | `TLS_AES_256_GCM_SHA384` | `ECDHE-RSA-AES256-GCM-SHA384` | **http/1.1 only** |
| static | `TLS_AES_128_GCM_SHA256` / 1.2 `ECDHE-RSA-AES256-GCM-SHA384` | 同左 | **h2** |
| example.com | `TLS_AES_256_GCM_SHA384` | `ECDHE-RSA-CHACHA20-POLY1305` | **h2** |

> gsqc-api **只谈 http/1.1**，与 23 号报告里「gsqc 的 ALPN 仅 http/1.1」一致；state-api 支持 h2，但客户端 pcap 用的是 TLS1.2 + HTTP/1.1（无碍，1.2 也通）。

---

## 5. DNS 解析结果

解析器：`223.5.5.5`（public1.alidns.com），采集时间 2026-11-14 01:39 CST。

| 域名 | 类型 | 值 | TTL |
|---|---|---|---|
| `state-api.bluearchive-cn.com` | CNAME | `state-api.bluearchive-cn.com.w.kunluncan.com` | 468 |
| `…w.kunluncan.com` | A | `111.3.79.58 / .59 / .60 / .61 / .62 / .63 / .64 / .65`（8 条） | 60 |
| `gsqc-api.bluearchive-cn.com` | CNAME | `gsqc-api.bluearchive-cn.com.eo.dnse0.com` | 600 |
| `…eo.dnse0.com` | A | `39.174.179.5`, `112.13.210.86`, `39.173.157.74` | 18 |
| `example.com` | A | **`<SERVER_IP>`**（无 CNAME） | 600 |
| `static.bluearchive-cn.com` | CNAME | `l9xtcnm1jdf6tp68.ysdp.top` | 1 |
| `l9xtcnm1jdf6tp68.ysdp.top` | CNAME | `static.bluearchive-cn.com.eo.dnse0.com` | 1 |
| `static.bluearchive-cn.com.eo.dnse0.com` | CNAME | `5dda5f5ea80ed366.eo.dl.sched.dma.tdnsdl1.cn` | 1 |
| `…dma.tdnsdl1.cn` | A | 采到时 `112.15.33.35`, `112.16.250.35`（Age 4s）；后段变为 `120.226.195.66`（TTL 27） | 4–27 |
| `bluearchive-cn.com` | A | `36.134.185.30` | 600 |

要点：

- `state-api` 走 **金山云/昆仑 CDN**（`kunluncan.com`）+ **阿里云 Tengine**（`Server: Tengine`、`EagleId`、`x-alicdn`）；
- `gsqc-api` 与 `static` 都走 **腾讯 EdgeOne**（`eo.dnse0.com`），后面分别接 **阿里云 OSS**（`x-amz-bucket-region: oss-cn-shanghai`）和 **百度 CDN**（`*.a.bdydns.com`）；
- **`example.com` 直接 A 到 `<SERVER_IP>`**，没有任何 CDN——这就是我们那台机器；
- `static` 的 DNS 是**调度型**（`dma.tdnsdl1.cn`，TTL 4s），不同时间会解析到不同节点，这正是 §3.4「一会有缓存 200、一会回源 403」的原因。

---

## 6. SNI 依赖性结论（关键假设验证）

### 6.1 直接回答

> **问：这几个上游域名在不带 SNI 的情况下还能不能正常握手？**
> **答：TCP/TLS 握手能完成（state-api 的 no-SNI 也回了证书），但拿到的证书与主机名不匹配 → 任何做证书校验的客户端都会失败。所以功能上「不能」；上游是依赖 SNI 的。**

> **问：那是不是说明真实客户端其实是带 SNI 的？**
> **答：是。** 上游的证书选择完全由 SNI 决定（§6.2 的对照实验），无 SNI 的客户端在真实上游上必然失败。因此「客户端不带 SNI」与我们观测到的上游行为**互相矛盾**——要么客户端其实带 SNI（23 号报告 pcap：ClientHello 353 B 含 SNI），要么那条无 SNI 的 ClientHello 根本不是发给真实上游的。

### 6.2 证据链（三组对照）

| 实验 | state-api | gsqc-api | static |
|---|---|---|---|
| SNI = 正确域名 | `CN=*.bluearchive-cn.com`，verify ok | 同左，verify ok | 同左，verify ok |
| SNI = `example.com`（未知） | **fatal alert 40 `handshake_failure`，无证书** | `CN=*.unionpayintl.com`（默认证书） | `CN=*.a.bdydns.com`（默认证书） |
| **完全无 SNI** | `CN=*.certfallback.com`，verify **62** | `CN=*.unionpayintl.com`，verify **62** | `CN=*.a.bdydns.com`，verify **62** |

- 阿里云（state-api）最严格：**未知 SNI 直接掐握手**；无 SNI 则退到 `*.certfallback.com` 兜底站。
- 腾讯 EdgeOne（gsqc）与百度 CDN（static）：无 SNI 一律给「该节点默认证书」，谁的证书就看它默认站是谁（这里分别是银联、百度自家域名）——这本身就是「没按 SNI 选，所以给了默认站」的铁证。

### 6.3 为什么之前会看到「无 SNI 也能通」

因为我们自己的机器（`<SERVER_IP>`）**无论 SNI 是什么、甚至没有 SNI**，都返回同一张 `CN=*.bluearchive-cn.com` 的 BA Test 证书（§4.3 最后一行）。

只要客户端被 hosts/DNS 指到我们这边，「不带 SNI 的 ClientHello + 证书 CN 匹配 + 业务 200」这套组合就完全成立。**这条观测不能用来推断真实上游的行为**——它只证明我们自己的 nginx 配置是对的（默认 server 兜底）。

---

## 7. 对私服的含义（逐字段读真实 `/api/state`）

### 7.1 真实结构体（以 gsqc-api 的 214 B 为准）

Go `encoding/json` 按**结构体字段顺序**输出，真实顺序是：

`CallbackUrl → CustomerServiceUrl → AddressablesCatalogUrlRoots → ResourceVersion → TableVersion → MediaVersion → PatchVersion → State → Msg → IsOpenPreDownload`

| # | 字段 | 类型 | 真实值（错误分支） | 解读 | 我们现在的假应答（181 B） |
|---|---|---|---|---|---|
| 1 | `CallbackUrl` | string | `""` | 回调/公告跳转地址，空=无 | ✅ 有（空） |
| 2 | `CustomerServiceUrl` | string | `""` | 客服页地址 | ✅ 有（空） |
| 3 | `AddressablesCatalogUrlRoots` | array\|null | `null` | **Unity Addressables 远端 catalog 根 URL 列表**；成功时应为字符串数组，客户端据此拉 catalog | ✅ 有，但我们是 1 项 |
| 4 | `ResourceVersion` | string | `""` | 资源版本号 | ❌ **缺** |
| 5 | `TableVersion` | string | `""` | 表格（Excel/DB）版本号 | ❌ **缺** |
| 6 | `MediaVersion` | string | `""` | 媒体（bundle/视频）版本号 | ❌ **缺** |
| 7 | `PatchVersion` | string | `""` | 补丁版本号 | ❌ **缺** |
| 8 | `State` | int | `0` | 状态枚举；**错误应答里也是 0**，所以 0 不等于「成功」，语义未知（不能拿 0/1 猜） | ✅ 有（0） |
| 9 | `Msg` | string | `"platform id error"` | 服务端文案；成功时大概率为 `""` | ✅ 有（但我们恒为空） |
| 10 | `IsOpenPreDownload` | bool | `false` | 预下载开关 | ❌ **缺** |
| — | `Servers` | array | **不存在** | 我们假应答里有 `["https://example.com/api/"]`，**真实结构体里没有这个字段** | ⚠️ 多出来的 |

**结论（对私服）**：

1. 我们的 schema **少了 5 个字段**（4 个版本号 + 预下载开关），多了 1 个 `Servers`。
2. 缺字段在 Unity/Newtonsoft 反序列化时通常会被填默认值（`""`/`false`），**不会**直接抛异常；所以「客户端卡住」未必是 schema 缺字段导致的。但**如果客户端用 `ResourceVersion` 拼 URL 或做版本比对，空串会走到错误分支**——这是下一步最值得查的点。
3. 要「字节级更像」，照抄字段顺序 + 214 B 这种紧凑无空格格式（Go 默认不缩进、不转义中文）。
4. **真实成功应答我们没拿到**：`platform id error` 说明这个网关要一个「平台号」，我们试遍 query/header 都没命中（§3.2 / §9.1）。`AddressablesCatalogUrlRoots` 的真实内容仍未知，**不要编**。

### 7.2 真实应答指向哪些下一步地址？

**一个都没有。** 本次拿到的真实 state 应答里，三个「地址类」字段全是空：

- `CallbackUrl` = `""`
- `CustomerServiceUrl` = `""`
- `AddressablesCatalogUrlRoots` = `null`

也就是说 **`gsqc-api` 的错误分支不告诉客户端任何后续地址**。唯一能看到的「真实下一步线索」只有 `static` 桶里的目录结构：`cbt1/AssetBundles/Android/*.bundle`（说明真实资源根大概率是 `https://static.bluearchive-cn.com/cbt1/...` 形态，**但这只是桶列表里的 key 结构，不是 state 应答说的**，别当结论用）。

### 7.3 与「180 B 假应答」的对比

我们服务器现在对 `state-api.bluearchive-cn.com/api/state` 实际返回 **181 B**（`Content-Length: 181`）：

```json
{"Servers":["https://example.com/api/"],"State":0,"Msg":"","CallbackUrl":"","CustomerServiceUrl":"","AddressablesCatalogUrlRoots":["https://static.bluearchive-cn.com/prodm39"]}
```

- 真实上游同 URL 返回 **0 B**（§0.2）。
- 真实网关（gsqc）返回的字段集合与我们的**不一致**（见上表）。
- 结论：这份 181 B 是**我们自己设计的**，与真实上游无对应关系；它现在能过 TLS、能拿到 200，但**不能声称「格式与真实一致」**。

---

## 8. 打不通 / 不可靠清单

| URL | 状态 | 现象 | 错误码/证据 |
|---|---|---|---|
| `https://state-api.bluearchive-cn.com/api/state` | ⚠️ **通，但空** | 200 + `Content-Length: 0`，7 次复测一致 | 无错误码；body sha256 = 空串 |
| `https://state-api.bluearchive-cn.com/`、`/api/` | ❌ 404 | `404 page not found`，带 `x-alicdn-da-ups-status: endOs,0,404` | HTTP 404 |
| `https://state-api.bluearchive-cn.com/api/state`（POST） | ❌ 404 | 路由只支持 GET | HTTP 404 |
| `https://gsqc-api.bluearchive-cn.com/` | ❌ 404 | Go 默认 `404 page not found` | HTTP 404 |
| `https://gsqc-api.bluearchive-cn.com/api/state` | ✅ 200 但**业务错误** | `Msg:"platform id error"`，所有参数组合都一样 | 业务层错误，非 HTTP 错误 |
| `https://example.com/api/` | ❌ 404 | nginx 空 body 404 | HTTP 404 |
| `https://static.bluearchive-cn.com/`（当前 DNS 节点 `120.226.195.66`） | ❌ **403** | 回源 AliyunOSS `AccessDenied`：`The bucket you access does not belong to you.` | HTTP 403，`x-oss-ec: 0003-00000001`，10/10 次 |
| `https://static.bluearchive-cn.com/`（旧缓存节点 `112.15.33.35` / `112.16.250.35`） | ✅ 200（**旧缓存**） | 桶列表 408 560 B，`Ohc-Global-Saved-Time: 2026-10-18` | 仅缓存命中时存在 |

> **没有任何一个域名是 TCP/TLS 层打不通的**。所有「打不通」都在应用层（404 / 403 / 空 body / 业务错误）。

### 8.3 必须保留的不确定性

`state-api` 的「空 200」有可能取决于**客户端原始请求头**（我们复现不了，23 号报告里 reqlen=323 B）。如果后续拿到 pcap 的请求头原文，应原样重放一次再定论；在那之前，**「真实应答就是 0 字节」只在我们发出的请求形态下成立**。

---

## 9. 附加探测（都为只读 GET，结果原样记录）

### 9.1 gsqc 的 `platform id` 参数穷举

| 尝试 | 结果 |
|---|---|
| `?platform=1` / `=2` / `=0` / `=3` / `=android` / `=Android` / `=iOS` / `=ios` / `=cn` | 全部 `platform id error` |
| `?platform_id=1` / `?platformId=1` / `?platformid=1` / `?platform=2&platform_id=2` | 同上 |
| Header `X-Platform-Id: 1` / `platform-id: 1` / `platformId: 1` / `Platform: 1` | 同上 |
| UA `UnityPlayer/2021.3.16f1 (UnityWebRequest/1.0, libcurl/7.84.0-DEV)` | 同上 |
| `POST`（空 body / `{"platform":1}` / `{"Platform":1}`） | `404 page not found` |
| `/api/state/1`、`/api/v1/state?platform=1`、`OPTIONS /api/state` | `404 page not found` |

→ **平台号不是 query/header 里这些名字**（也可能还叠加了签名/设备头）。这条线要继续，得靠客户端 pcap 里的原始请求。

### 9.2 `test-ba.yostar.net:5210`（来自 `23-主线改判` 里提到的 metadata 默认 ApiUrl）

```
GET http://test-ba.yostar.net:5210/api/state
HTTP/1.1 200 OK
Date: Sun, 15 Nov 2026 13:35:28 GMT
Content-Length: 0
```

- DNS：`test-ba.yostar.net → 106.14.164.191`。
- HTTPS 443：**连接超时**（`curl: (28)`）。
- ⚠️ **不可采信**：响应只有 `Date`/`Content-Length` 两个头（没有 `Server`），而且 `Date` 比本机时钟**快 2 天**——这更像中间设备/代理的空回包，不像真实业务应答。记录在此仅为留痕，**不要**把它当上游证据。

---

## 10. iptables 还原验证

**本次未使用方案 B，服务器上一条命令都没执行**（没 SSH 登录，更没碰 `iptables`）。

- 方案 A（本机直连）直接成功，8 个 HTTP 事务全部 200/301/403 有响应，无连接失败。
- 因此不存在「临时 RETURN 规则」，也就没有需要还原的东西；`iptables -t nat -L OUTPUT` 前后对比**不适用**（本次全程没有进入服务器）。
- 服务器上那条 443 DNAT 劫持规则**保持原样**，未读、未改、未删。

> 如果后续确实需要从服务器内部发起请求，再按方案 B 走，并补一节「前后对比」。

---

## 11. 证据文件清单（`report/evidence/22/`）

| 文件 | 内容 |
|---|---|
| `RAW_HTTP.log` | 7 个 HTTP 事务的原始命令 + 完整头 + 完整 body |
| `A_state_api.hdr` / `.body` | state-api 200/0B 的头与空 body |
| `A_gsqc_root.hdr/.body`、`A_gsqc_state.hdr/.body` | gsqc 404 / 214B JSON |
| `A_xlh_sdk.hdr/.body`、`A_xlh_api.hdr/.body` | 卡密域名 301 / 404 |
| `A_static_root.body`（408 560 B）、`static_try*.hdr/.body` | static 桶列表与 403 两份应答 |
| `A_static_root2.body` | 403 AccessDenied 的 376 B XML |
| `*.sni.txt`（4 份） | `s_client -servername` 完整握手 + 完整证书链 PEM |
| `*.nosni.txt`（4 份） | `-noservername` 完整握手 + 兜底证书 |
| `*.sni_verify.txt` / `*.nosni_verify.txt`（8 份） | `-verify_hostname` 的逐 depth 校验输出 |
| `cert_details.txt` | 每条链每张证书的 subject/issuer/起止/SAN/CA/指纹/签名算法汇总 |
| `*.chain*.pem` / `*.nosni.leaf.pem` | 从握手里拆出来的单张证书 PEM |
| `tls_probe.sh` / `cert_detail.sh` / `sni_bogus.sh` / `ourserver_sni.sh` / `tls12_alpn.sh` | 本次所有 TLS 探测脚本（可直接复跑） |

---

## 附录 A：HTTP 原始输出（完整）

{{RAW:RAW_HTTP.log}}

## 附录 B：证书详情汇总（完整）

{{RAW:cert_details.txt}}

## 附录 C：各域名 TLS 握手原文（带 SNI）

### C1 state-api.bluearchive-cn.com
{{RAW:state-api.bluearchive-cn.com.sni.txt}}

### C2 gsqc-api.bluearchive-cn.com
{{RAW:gsqc-api.bluearchive-cn.com.sni.txt}}

### C3 example.com
{{RAW:example.com.sni.txt}}

### C4 static.bluearchive-cn.com
{{RAW:static.bluearchive-cn.com.sni.txt}}

## 附录 D：各域名 TLS 握手原文（无 SNI）

### D1 state-api.bluearchive-cn.com
{{RAW:state-api.bluearchive-cn.com.nosni.txt}}

### D2 gsqc-api.bluearchive-cn.com
{{RAW:gsqc-api.bluearchive-cn.com.nosni.txt}}

### D3 example.com
{{RAW:example.com.nosni.txt}}

### D4 static.bluearchive-cn.com
{{RAW:static.bluearchive-cn.com.nosni.txt}}

## 附录 E：static 桶列表（前 4000 字符，全文见证据文件）

{{HEADCHARS:A_static_root.body}}
