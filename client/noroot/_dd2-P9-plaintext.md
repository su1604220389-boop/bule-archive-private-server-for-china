# DD2: P9 明文 HTTP 可行性

> 对象：国服客户端 `com.RoamingStar.BlueArchive`（targetSdk=33 / minSdk=24，IL2CPP，Unity 2021.3.56f2）
> 方法：只读现有档案 + 从本仓库的 APK 资源副本**亲自解出** `res/xml/http.xml`（AXML）与 `AndroidManifest.xml`
> 纪律：每条结论标注 `文件:行号` 与置信度（**确证** / **推断** / **未知**）。未找到的写「未找到」。
> 本轮未连服务器、未连手机、未执行任何网络操作。

---

## 结论速览

1. **【确证】明文 HTTP 在本 App 内是被允许的，而且是"全域名允许"**：`AndroidManifest.xml` 有 `usesCleartextTraffic="true"` 且 `networkSecurityConfig="@xml/http"`；我解出 `http.xml` = `<network-security-config><base-config cleartextTrafficPermitted="true"/>`（**base-config，非 domain-config，无 pin-set、无 domain-config**）。所以"Android 9+ 默认禁明文"这条**在本 App 上不成立**，且这与原生/Java 分层无关——策略本身是放行的。
2. **【确证】游戏 RPC 全部 URL 由服务端 JSON 决定，scheme 完全在我们手里**：hop1 `state-api/api/state` → `Servers[]`（客户端逐条探活，实测会真的去连 `Servers` 里那台，`report/22:20`、`report/101:90-91`）→ hop2 回 `ServerInfoConnectionGroupData.ApiUrl` → 之后所有 RPC 用 `ApiUrl`（`report/24:146-147`、`report/41:486`）。**只要 `Servers` 给 `http://`，从 hop2 起整条链明文。**
3. **【确证】但 hop1 是 https，且这个 URL 在客户端里改不了**：手机实机对 `state-api.bluearchive-cn.com` **4 次完成 TLS 1.2 握手**（`report/22:13`），且该域名在 metadata + libil2cpp 全 0 命中（ASCII/UTF-16/256-key XOR/周期≤8 keystream 四重证伪，`report/11:165-173`）⇒ hop1 的 scheme 不是配置项，改它要改代码。
4. **【推断】P9 对"游戏 RPC 层"可行、对"state 引导层"不可行；它把 TLS 墙从"全链路"缩到"一个请求"，但不消除它。⇒ P9 本身不能实现免 root**，因为免 root 的 DNS（P6）方案必须让 hop1 的 TLS 通过，而我们没有 `state-api.bluearchive-cn.com` 的任何有效证书。
5. **【确证·纠正】`report/09:688` 那条不是"走 HTTP 实测成功"**：它记的是 `https://example.com/api/state` 在公网/真证书/零绕过下 200，用来证明"D04 换自有域名可绕 TLS"。同一响应体里的 `http://127.0.0.1:5000/api/` 是**我们自己写进去的 `Servers` 占位值**，不是客户端走 HTTP 的证据。

---

## 1. `example.com` 走 HTTP 的原始记录（引文）

### 1.1 `report/09:688` 实际写的是什么 —— 是 **HTTPS**，不是 HTTP

`report/09-服务器盘点.md:682-689` 原文：

```
682: 公网取回的 body（一字未改）：
684: ```json
685: {"Servers":["http://127.0.0.1:5000/api/"],"State":0,"Msg":"","CallbackUrl":"","CustomerServiceUrl":"","AddressablesCatalogUrlRoots":["https://static.bluearchive-cn.com/prodm39"]}
686: ```
688: > **这是本轮最有价值的一行结果**：`https://example.com/api/state` 在**公网、真证书、无任何证书绕过**的前提下返回 200。
689: > 即 D04 的判断被实测证实 —— **TLS 这道墙不需要攻，换个落在自有域名下的 URL 就绕过去了。**
```

**判读（确证）**：
- 这条记录证明的是「**TLS 可以靠换域名解决**」，与"明文 HTTP"无关。被请求的 URL 是 `https://`。
- 第 685 行的 `http://127.0.0.1:5000/api/` 是**我方 nginx 里手写的 `return 200` 占位串**（源头见 `report/09:513`、`:518`「按 Lead 要求，`Servers` **保留 `http://127.0.0.1:5000/api/` 占位**」），并且是**服务端→服务端**的本地回环，不是客户端发出的明文请求。
- 所以"688 行 = 客户端走 HTTP 实测成功"是**误读**。

### 1.2 真正"`example.com` 走 HTTP"的记录有两条，但都是**我们自己 curl**，不是客户端

| 记录 | 原文 | 含义 | 置信度 |
|---|---|---|---|
| `report/06-手机基线恢复.md:241` | 「服务端实测：`http://example.com/api/Queuing/Ping` → 200；而 `http://<SERVER_IP>/api/...`（Host 头是 IP）→ 404 落到默认站点 ⇒ **H2 注定失败，不测**」 | 证明我方 nginx 的 **80 端口**在提供服务，且裸 IP 不能当候选 | 确证（是 curl，非客户端） |
| `report/13-总账-2026-11-14凌晨.md:58` | 「S12【已证实】公网 `http://example.com/api/Queuing/Ping` → **200**；`http://<SERVER_IP>/api/…`（无 Host 头）→ **404**」 | 同上，S12 是其总账编号 | 确证（同上） |

**关键区分**：这两条只证明**服务器能发明文**，完全不能证明**客户端愿意发明文**。档案里"客户端自己发出明文 HTTP"的实测记录，只有 §3.1 的 SDK 层那一条。

### 1.3 唯一的"客户端 → 明文 HTTP"实测：SDK 层，且成功（确证）

`work/ba/audit/ba-sdk-protocol.md:64`：
```
| sdk_url 改为本地 HTTP 后 SDK 真的连过来 | ✅ 抓到 6 个真实请求 |
```
`report/04-服务端就绪度.md:288`：
```
| 1 | SDK 配置 | `POST {sdk_url}/common/config` | HTTP 明文（`cleartextTrafficPermitted=true`） | `ba-sdk-protocol.md:5-11`、`sdk.log:1` | ✅ **已实现**（`sdkcard.py:73-90`），实测 6 个请求全抓到 |
```
`report/13-总账-2026-11-14凌晨.md:26`（C7【已证实】）：
```
`assets/SDKConfigSettings.json` 的 `sdk_url = http://127.0.0.1:8080`（裸 loopback+端口）；手机侧靠 `/data/local/tmp/relay.sh`（`busybox nc -l -p 8080` + curl）转发到 `https://example.com/sdk<path>`
```
`report/06-手机基线恢复.md:58` 同义：`127.0.0.1:8080` 的明文 HTTP 转成 `https://example.com/sdk<path>`。

**判读（确证）**：`okhttp/4.9.2`（UA 见 `ba-sdk-protocol.md:30`）向 `http://127.0.0.1:8080` 成功发出了 6 个请求并被 `sdkcard.py` 收下 ⇒ **Java 层明文 HTTP 实跑通过**。这是本仓库最硬的一条明文证据，但它**只覆盖 SDK 层**（`sdk-api.yostar.cn` 那套），与游戏 RPC 无关。
⚠️ 注意它需要改 `assets/SDKConfigSettings.json`（在 APK 里）⇒ 要重新打包，与"免 root 且不改包"无关。

### 1.4 ★ 唯一一次**真把明文 http 塞进客户端**的实验：H1，结论是"被接受但没被选中"（确证）

`report/06-手机基线恢复.md:240-251`：
```
240: ### 步骤 16：实验 H1 —— Hosts 候选改**明文 http** URL
242: 写入 H1（78 B）：
244: 01 00 00 00 | 01 00 00 00 | 1b "gsqc-api.bluearchive-cn.com" | 01 00 00 00
245: | 1c(28) "http://example.com/api/" | 92 dd 89 8b f2 40 df 48 | 01
249: * `ss -tnp | grep <pid>` 全程**无 `<SERVER_IP>:80`**、无任何 `:80` 连接；app 仍连官方 `112.13.210.86:443 / 111.3.79.61:443 / 39.173.157.74:443`。
250: * 启动后 `Hosts` 被重写成 **127 B**：`u32` 计数 1→2，**我们的 http URL 原样保留**，后面追加官方 `https://gsqc-api.bluearchive-cn.com:443`（新 u64）。
251: * **结论（L1=否）**：客户端**解析并保留了**我们的候选，但**没有去连它**。
```

**判读（确证 + 一点推断）**：
- **确证**：客户端**语法上接受了 `http://` scheme**（78 B → 127 B 重写时"原样保留"，说明解析器没有拒绝、没有改写、没有丢弃）。
- **确证**：没有产生任何 `:80` 连接 ⇒ **从未发生一次真实的明文 RPC**。
- **推断（重要）**："没连它"的原因不是"拒绝 http"，而是**候选排序/存活判定**：客户端把官方 `https://gsqc-api…:443` 追加在后并实际去连了官方的三台 IP ⇒ 我们那条被排在后面或未判为 live。这与 `report/10:19`（N7「保留了但没被选中」）一致。
- **⇒ 到本轮为止，"客户端真发明文游戏请求"仍是 0 例。** 这是 P9 最大的证据空档。

---

## 2. `ResUrls` / CDN 走 HTTP 的记录

### 2.1 `ResUrls` 是**资源层**，不是 RPC（确证）

配置载体：`files/LocalizeConfig.txt`（纯文本，3 个 key：`Env` / `IsLocalize` / `ResUrls`）。

`report/54-客户端补丁方案-本地配置绕过.md:259`：
```
| `ResUrls` | `https://static.bluearchive-cn.com/prodm39;https://static-qc.bluearchive-cn.com/prodm39;https://static-hs.bluearchive-cn.com/prodm39` | 资源 CDN 根，3 条 = 3 条 CDN 线；覆盖 `/api/state` 的 `AddressablesCatalogUrlRoots` | **【实锤】**（§6） | 只在"要接管 CDN"时改（§9）。否则**保持官方值** |
```
`report/54:237`（关键）：
```
### 6.2 与「登录」的关系（确证：无关）
`ResUrls` 只喂给资源层。**API 主机名/网关名不来自这里**
```
`report/54:230-233` 逐项列出 `AssetBundles`(6.5 GB) / `Tables`(435 MB) / `Media`(4.0 GB) / `Patch·Catalog` 四组下载根 —— 全部是资源。

### 2.2 `ResUrls` 允许 `http://` —— 但这是**社区情报**，不是本地实测（推断）

`report/54:243`：
```
- **不支持 `https` 自签证书**：社区样例用的是 **`http://`** 明文，说明 CDN 侧不强制 TLS。我们要接就得用 **`https` + 真证书**（`example.com` 有真证书，见 report/09 D04）**或 `http` 明文**。
```
`report/54:452`：
```
| 要证书 | **用真证书的 `example.com`（report/09 D04 已经定了这个方向）或明文 `http`，都不需要自签 CA** |
```

**判读**：
- **推断（中等强度）**：资源层（Addressables，走 UnityWebRequest/libcurl）接受 `http://`。依据是"社区样例用的是 http:// 明文"这一条外部情报（`report/54:243` 未给一手出处）。
- ⚠️ **本仓库没有做过 ResUrls=http 的实测**。未找到该实验记录。
- ⚠️ 这条的价值与 RPC 无关：`ResUrls` **不改变 API 主机**（`report/54:237`、`:419-422`）。

---

## 3. 三层分离：SDK / state-api / 游戏RPC 各自能否明文

先钉清一条**贯穿三层的事实**：本 App 的明文策略是**放行**（见 §4 的原始证据）。所以三层的问题都不是"系统让不让"，而是"**客户端的 URL 从哪来、我们能不能把它变成 http**"。

| 层 | HTTP 栈 | 谁决定 URL | 能否明文 | 依据 | 置信度 |
|---|---|---|---|---|---|
| **① SDK 层** (`sdk-api.yostar.cn`) | Java **okhttp/4.9.2** | `assets/SDKConfigSettings.json.sdk_url`（在 APK 内） | **能**（实测成功） | `ba-sdk-protocol.md:7,30,64`；`report/04:288`；`report/13:26` | **确证** |
| **② state-api 层** (`state-api.bluearchive-cn.com/api/state`) | Unity **UnityWebRequest + libcurl 8.10.1-DEV**（原生） | **客户端内部，无静态来源** → 改不了 | **客户端有能力（NSC 放行 + 自带 http 默认值），但我们无权改它** | URL 来源：`report/54:417-422`、`report/11:165-173`；实测走 https：`report/22:13` | 能力=确证 / 可改=**确证不能** |
| **③ 游戏 RPC / gateway 层** (`POST {ApiUrl}account/auth` 等) | **BestHTTP/2 v2.4.0**（托管 C#，libil2cpp） | **服务端 JSON**：`Servers[]` → hop2 → `ApiUrl` | **能，且 scheme 由我们定** | `report/41:53-55,60,486-489`；`report/24:146-147,224`；`report/22:20`；`report/101:90-91` | **确证（机制）/ 推断（未实跑过明文）** |

### 3.1 第 ③ 层的机制（这是 P9 的全部价值所在，确证）

**链条（三段，逐段都有实测锚点）**：

```
hop1  GET https://state-api.bluearchive-cn.com/api/state        ← scheme 固定 https，改不了
        ↓ 响应 {"Servers":[url...],"State":1,"Msg":""}
hop2  GET {Servers[i]}state                                     ← ★ scheme 由我们的 JSON 决定
        ↓ 响应 ServerInfoConnectionGroupData（25 字段，含 ApiUrl/ApiUrls）
hop3  POST {ApiUrl}account/auth  …  之后所有 RPC                ← ★ scheme 同样由我们决定
```

逐段证据：

1. **hop1 → hop2 是真的按 `Servers` 走的（确证）**
   - `report/101-官方真服抓包分析.md:90-91`：官方客户端 03:59:31.771 `GET state-api…/api/state` 200(161 B)；**0.3 s 后** 03:59:32.063 `GET gsqc-api…/api/state` 200(676 B)。`gsqc-api` 正是 hop1 响应里 `Servers[0]`（`report/101:277`）。
   - `report/22-服务端取证记录.md:20`：「01:42:19 客户端确实发出了下一跳：同一秒并发 4 条 TLS — `state-api`(CH 1561)、`gsqc-api`(1412)、`static.bluearchive-cn.com`(1412)、无 SNI(1412)」⇒ **客户端会主动去连 `Servers` 里那台**，不存在"只信官方硬编码"。
   - `report/24-state接口schema反推.md:224`：`GetApiServerInfo` 是**迭代器**，局部变量 `<i>5__4`（下标）/ `<isLive>5__3`（存活标记）/ `<header>5__2`（一个 HTTP 头）⇒ **按 `Servers` 逐条探活，选一台活的**。

2. **hop2 → hop3 由 `ApiUrl` 决定（确证）**
   - `report/24:146-147`：
     ```
     | 3 | `ApiUrls` | `List<string>` | 复数 + 私有字段 `apiIndex` + `ResetApiUrl` |
     | 4 | `ApiUrl`  | `string`（**只读派生**） | 只有 getter；配合 `apiIndex` 从 `ApiUrls` 取 |
     ```
   - `report/41-Account_Auth字段级排查.md:486`：「`ApiUrl` 来自 `state-api` 的 `Servers`（`https://gsqc-api.../api/`），客户端拼成 `{ApiUrl}account/auth`」；`:488`：「全文件 `"gateway"` 字面量 **0 命中**、`"account/auth"` **0 命中** ⇒ 路径是运行时拼的，不是写死的两个端点」。

3. **`Servers` 里的 scheme 被原样使用，客户端**不做**任何"强制 https"校验（推断，强负证据）**
   - `report/11-客户端静态逆向-网关与证书.md:33-36`：「默认 connection group 的字面量就是 **`http://`**（不是 https），说明 `ApiUrl` 的消费端**接受明文 http**；metadata 里没有任何"强制 https / scheme 校验 / pinning"的游戏侧证据」。
   - `report/11:156`：客户端内**唯一**的游戏 API URL 字面量 =
     ```
     global-metadata.dat @ 0x000c172b, XOR key = 0xB5
     明文：["http://test-ba.yostar.net:5210/api/state", …×3]
     ```
     ⇒ 客户端**出厂默认就是用明文 http 拼游戏 API URL 的**。这是"客户端愿意发明文"的最强静态证据。
   - `report/11:313-314` 自评为「`ApiUrl` 消费端接受 http = **强**」/「没有强制 https 逻辑 = 中（负证据）」。

### 3.2 第 ② 层为什么"能力有、但改不了"（确证）

- **能力有**：NSC 放行明文（§4）；且默认连接组字面量就是 `http://`（`report/11:156`）⇒ 若哪个 `state` URL 是 http，客户端会照发。
- **改不了**：
  - `report/54:417-422`：
    ```
    417: ### 8.2 服务器地址在客户端里**没有静态来源**，只能来自 `/api/state`
    419: - `gsqc-api` / `state-api` / `bluearchive-cn` / `static.bluearchive-cn.com` / `prodm39` 在 **metadata + libil2cpp.so** 里全部 0 命中（256 key × ASCII+UTF-16）。
    420: - 唯一硬编码 URL = **测试环境** `http://test-ba.yostar.net:5210/api/state`（×3，`0x000C1732`，key `0xB5`）。
    422: ⇒ **改本地文本文件无法改变 API 主机**，因为文件里根本没有这个字段，代码里也没有这个字符串。
    ```
  - `report/11:165-173` 四重证伪表（ASCII / UTF-16LE / 单字节 XOR 全 256 key / 周期≤8 keystream，含 libil2cpp.bin）⇒ `state-api` 命中全 0。
  - `report/11:195-204` 三种"URL 来源模型"：M1 运行时解密（**高**）/ M2 序列化在 Unity 资源里（中）/ M3 来自上次 state 的 Hosts 缓存（中），并注明 M3 不能解释首装启动 ⇒ 存在**内置 bootstrap**。
- **而 hop1 实测确实走 https**（确证）：`report/22:12-14`：
  ```
  12: 1. **TLS 已经不是瓶颈。** 手机 `UnityPlayer/2021.3.56f2 (UnityWebRequest/1.0, libcurl/8.10.1-DEV)` 对
  13:    `state-api.bluearchive-cn.com` **4 次**完成 TLS 1.2 握手（ClientHello → 证书 flight → ClientKeyExchange → CCS → Finished → 339 B 应用数据），
  14:    nginx 解出明文 `GET /api/state` 并回 **200**。
  ```
  （另有 `report/23-主线改判-TLS已通应用层卡点.md:48`：「`state-api` 这条**明确带 SNI**」；`report/22-真实上游接口取证.md:25` 记该 pcap 的 ClientHello 为 **353 B**。⇒ hop1 是标准 TLS 连接，不存在"不走 TLS"的可能。）

### 3.3 顺带纠正一处档案内部冲突（对 P9 有影响）

- `report/24:226` 由类名 `DownloadServerInfoDataHttp2` 推出「走 **HTTP/2**」。
- 但实机原始日志显示的是 **HTTP/1.1**：`report/22:61,68`
  ```
  "GET /api/state HTTP/1.1" 200 180 "-" "UnityPlayer/2021.3.56f2 (UnityWebRequest/1.0, libcurl/8.10.1-DEV)"
  ua="UnityPlayer/2021.3.56f2 (UnityWebRequest/1.0, libcurl/8.10.1-DEV)" host="state-api.bluearchive-cn.com" ... clen="-" reqlen="323"
  ```
- **判读（确证）**：**不要假设客户端强制 h2**。`Http2Message` / `Http2DownloadMessage` 是游戏自己的类名（`report/41:496`），不代表协议版本。⇒ 明文侧用 **HTTP/1.1** 就能对齐（这对 P9 是好消息：明文 h2c 的复杂度省掉了）。

### 3.4 网关不是 WebSocket / 不是 KCP / 不是长轮询（确证）

- `report/75-L0传输层-Shittim对照与改造方案.md:20`：「有没有服务端推送 → **没有。一条都没有。** 无 WebSocket / SSE / SignalR / 长轮询 / 挂起 GET」；`:250` 同结论；`:234`：「**不是**长轮询、**不是** WebSocket、**不是** SSE。整个响应在 handler 返回前就已完整生成」。
- 客户端实际用的是 **HTTP POST multipart/form-data**（确证）：`report/41:55,61`
  ```
  55: 03:27:37  POST /api/account/auth → gsqc-api    404 1269B  ua=BestHTTP/2 v2.4.0   ← 唯一一次网关交互
  61: 3. 编码是 `multipart/form-data`（boundary `BestHTTP_HTTPMultiPartForm_*`）。
  ```
- ⇒ **P9 没有 `ws://` vs `wss://` 的问题**：没有 WebSocket。只剩 http/https 一个维度。

---

## 4. Android cleartext 策略对原生 libcurl 是否生效（技术分析）

### 4.1 先把"策略是什么"钉死（★ 本轮新增一手证据）

档案里这条一直是**错的**，必须纠正后再谈分层：
- `report/INDEX.md:513`（A-20）判定「`res/Dk.xml` 证实 `cleartextTrafficPermitted=true`」为**已废**：「**该文件在 APK 里不存在**……`AndroidManifest.xml` 里也**没有** `networkSecurityConfig` 属性」。
- `report/06-手机基线恢复.md:628` 的依据是一句 **`grep 'networkSecurityConfig|cleartext|network'` → 全空**。

⚠️ **这个"全空"极可能是方法学伪影**：BRE（基本正则）里 `|` 是**字面量**，未加 `-E` 时 `grep 'a|b|c'` 等于搜字面串 `a|b|c`，必然全空。此外 `usesCleartextTraffic` 含大写 `C`，而 pattern 写的是小写 `cleartext`，即便用 `-E` 也匹配不到。

**我直接从本仓库的 APK 资源副本里解出原文（确证，一手）**：

1) `work/ba/audit/ba-apk/jadx/resources/AndroidManifest.xml:182-193`（jadx 反编译产物，原样）：
```xml
182:     <application
185:         android:name="com.tech.core.TechApplication"
186:         android:allowBackup="false"
187:         android:extractNativeLibs="true"
188:         android:usesCleartextTraffic="true"
189:         android:networkSecurityConfig="@xml/http"
190:         android:roundIcon="@mipmap/app_icon_round"
193:         android:enableOnBackInvokedCallback="true">
```
（与 `work/ba/audit/ba-java.md:168-169` 一致：「`usesCleartextTraffic` **true** `:188`」/「`networkSecurityConfig` `@xml/http` `:189`」。）

2) `work/ba/bapatch/res.apk!res/xml/http.xml`（264 B，二进制 AXML）—— 我用 `work/ba/noroot/_dd2_axml.py` 解出（日志见同目录）：
```
# magic: 0300080008010000
# string pool (3): [0] 'base-config'  [1] 'cleartextTrafficPermitted'  [2] 'network-security-config'
--- decoded ---
<network-security-config>
  <base-config cleartextTrafficPermitted (resid=0x00000000) -> true  [type=0x12 data=0xffffffff]>
</network-security-config>
```
`type=0x12` = `TYPE_INT_BOOLEAN`，`data=0xffffffff` = **true**。

**交叉校验（确证）**：我从 `res.apk` 的 zip entry 直接取出的 264 B 与目录里**已存在的** `work/ba/noroot/_res_xml_http.bin` **逐字节相同**（sha256 `f4861a2727f78aa4a30a4dc82308b1ec645dcc e1ed7ab8aa05e806684b4dbee7`）⇒ 有前序工作把文件取出来了，但**没有解出来**：`work/ba/noroot/_axml_out.txt:217-218` 记的是 `cleartext hits=0` / `cleartextTrafficPermitted hits=0` —— 那是因为 AXML 的 string pool 是 **UTF-16LE**，ASCII grep 必然 0 命中（`report/06:628` 的"全空"是同一类方法学失效）。**本条结论因此是首次真正解出。**

**结论（确证）**：
- 生效的是 **`<base-config cleartextTrafficPermitted="true"/>`** —— `base-config` 对**所有域名**生效，不是 `domain-config`，因此**不存在"只有 127.0.0.1 放行"这种窄口子**。
- 该 NSC **没有** `<domain-config>`、**没有** `<pin-set>`、**没有** `<trust-anchors>` ⇒ **NSC 层不存在域名白名单式 pinning**（与 `report/11:229`、`report/16` 的结论方向一致：真正的证书裁决在 `CustomCertificateHandler`/UnityTLS，不在 NSC）。
- 同时 `usesCleartextTraffic="true"`：按 Android 规则，**NSC 存在时以 NSC 为准**，两者一致（都放行），无冲突。
- ⇒ **targetSdk=33 "默认禁明文"这条在本 App 上被 App 自己覆盖掉了**。`report/00:97` 的结论方向对（"全链路明文可行"），但它引的**证据文件是错的**（`Dk.xml` 不存在），正确证据是上面这份 `http.xml`。

### 4.2 分层的技术判断

Android 的 cleartext 限制**不是内核/socket 层的能力**，而是 `android.security.net.config` + `NetworkSecurityPolicy` 这一套 **framework API**；执行者是**愿意查询它的 HTTP 栈**：

| 栈 | 本 App 用在 | 是否查 `NetworkSecurityPolicy` | 结论 |
|---|---|---|---|
| okhttp / `HttpURLConnection` | SDK 层（`okhttp/4.9.2`） | **会**（okhttp 的 `AndroidPlatform.isCleartextTrafficPermitted(host)`） | 受策略管辖；**策略=true ⇒ 放行**（且已实测，`ba-sdk-protocol.md:64`） |
| Unity `UnityWebRequest` → **libcurl**（原生 BSD socket） | hop1 state、资源下载 | **不查**（原生 libcurl 不走 `NetworkSecurityPolicy`；平台也没有 socket 级拦截） | 理论上永远能发明文 |
| **BestHTTP/2**（托管 C#，跑在 libil2cpp 里） | 游戏 RPC | **不查**（自带 Socket + 自带 TLS 层，纯托管路径） | 理论上永远能发明文 |

**置信度**：表格第 2/3 行的"不查"是 **推断（强）** —— 依据是机制（Android 未在 socket 层实现 cleartext 拦截，该策略只由 framework 消费）+ 本仓库的一手旁证：`report/12:158`「① 走 libcurl + **UnityTLS**」、`report/06:643` 的报错原文 `Curl error 60 … UnityTls error code: 7` 说明 hop1 的 TLS 由 UnityTLS/mbedtls 自己裁决，而**报错里没有任何 "Cleartext … not permitted" 形态的错**。

**但这一行推断对本问题不重要** —— 因为 **策略本身是 `true`**，所以：
> **无论 cleartext 策略是否作用于原生 socket，P9 在 Android 侧都不会被拦。** 这是本轮最干净的结论，不需要赌"原生是否豁免"。

### 4.3 反向证据：外部作者明确说"明文被禁" —— 与本 App 不符（需注明）

- `report/05-AzusaBA可复用资产.md:213`：「`java/RemoteNotice.java:19-22` —— 「游戏 targetSdk=33，明文 HTTP 被系统默认禁止（`NetworkSecurityPolicy.isCleartextTrafficPermitted()==false`），所以只能用 https」」，`:214` 补「我们审计里也记着国服 `networkSecurityConfig=@xml/http`」。
- `report/56-外部情报-国服私服与客户端绕过.md:109`（国际服 `cc004/BlueArchiveAPI` README）：「2. Set property `cleartextTrafficPermitted` to `True` in `networkSecurityConfig` of the game app.」
- **判读（确证）**：这两条都不适用于本包。AzusaBA 的注释是**按 targetSdk 默认值**推的（没解 `http.xml`）；cc004 讲的是 **Nexon 国际服**包。**本包 NSC 明文为 true，我解出了原文。**

---

## 5. 客户端 URL scheme 是硬编码还是配置下发（证据）

分三类，结论不同：

| # | URL | 形态 | 证据 | 置信度 |
|---|---|---|---|---|
| 1 | `https://state-api.bluearchive-cn.com/api/state`（hop1） | **硬编码/运行时生成，不可配置** | `report/54:417-422`、`report/11:165-173`（四重证伪）；实测 TLS 握手 `report/22:13` | **确证** |
| 2 | `http://test-ba.yostar.net:5210/api/state` ×3 | **硬编码字面量（测试环境）**，XOR `0xB5`，`0xc172b` | `report/11:156`、`:97`；`report/54:420` | **确证** |
| 3 | hop2 的 `{Servers[i]}state`、hop3 的 `{ApiUrl}…` | **服务端下发（我们完全控制）** | `report/24:146-147,224`、`report/22:20`、`report/101:90-91`、`report/41:486-488` | **确证** |
| 4 | SDK 的 `sdk_url` | **`assets/SDKConfigSettings.json`**（APK 内配置） | `ba-sdk-protocol.md:5-9`、`report/04:288` | **确证** |
| 5 | 资源 CDN 根 | **`files/LocalizeConfig.txt` 的 `ResUrls`**（明文 3 条） | `report/54:259` | **确证** |
| 6 | `files/Hosts` 里的候选 | **明文二进制结构**，`u32 ver | u32 count | loop{hostlen,host,u32,urllen,url,u64,flag}` | `report/06:244-245`、`:250` | **确证**（且 `http://` scheme 被原样保留） |

**补充证据（"没有强制 https 的代码")**：`report/11:314`
```
| 没有"强制 https"的游戏逻辑 | metadata 里 `StartsWith`（5 处）全在 BCL/TMP 上下文；`UriSchemeHttps`/`HttpsUri` 是 .NET 标准名；无 `IsHttpAllowed`/`Insecure` 类游戏字段 | 中（负证据） |
```

**关键推论（推断）**：既然 #2 和 #6 都表明客户端**出厂就能吃 `http://`**，那么把 `http://` 放进 #3 是**同一条代码路径**（都是 `ApiUrl`/`Servers` 的消费端），风险很低。但**仍未实跑过**（§1.4）。

---

## 6. P9 判定 + 剩余未知

### 6.1 逐层判定

| 层 | P9 是否可行 | 一句话理由 |
|---|---|---|
| **SDK 层** | ✅ **可行（已实测）** | 改 `sdk_url` 为 `http://…` 后 okhttp 成功发出 6 个请求（`ba-sdk-protocol.md:64`）。但改 `assets` 需重新打包 ⇒ 与"免 root 不改包"无关 |
| **state-api 层（hop1）** | ❌ **不可行（就"我们改它"而言）** | URL 无静态来源、改文件改不到（`report/54:419-422`）；实测它就是 https（`report/22:13`）。客户端**有能力**发明文，但**我们没有任何旋钮**把它变成 http |
| **游戏 RPC / gateway 层（hop2+）** | ✅ **机制上确证可行，缺一次实测** | scheme 100% 来自我们的 `Servers`/`ApiUrl` JSON（`report/24:146-147`、`report/41:486`）；客户端跟随 `Servers` 有两次实机旁证（`report/22:20`、`report/101:90-91`）；无强制 https 校验（`report/11:314`） |

### 6.2 P9 对"免 root 连服务器"到底有没有用 —— **结论：不够**

**链路成本表**（关键）：

| 方案 | 需要劫持的 TLS 连接数 | 需要的证书 | 是否需要 root |
|---|---|---|---|
| 现方案 DNAT 全劫持 | 全部（state-api + gsqc-api + gs-api + static + 探活） | 覆盖 `*.bluearchive-cn.com` + `state-api` 的 CA 链 | **需要**（iptables DNAT，`report/13:84`） |
| **P9 + DNS(P6)** | **只剩 hop1 一条** | 仍需 `state-api.bluearchive-cn.com` 的**有效证书**（我们不可能有） | 不需要 root，但**卡死在证书** |
| **P9 + DNAT** | 1 条 | 同上 | 需要 root（但面积小很多） |

**为什么 P9 不能落地成免 root（确证 + 推断）**：

1. hop1 是 `https://`（确证，`report/22:13` 四次 TLS 1.2 握手）。
2. 免 root 能做的最多是把 `state-api.bluearchive-cn.com` **DNS 解析**到我们（改手机 DNS / 路由器 DNS，不需要 root）。
3. 但 DNS 只改变 IP，**不改变 scheme**：客户端仍会对我们的 443 发 ClientHello，并要求一张能被它信任的、`CN/SAN=state-api.bluearchive-cn.com` 的证书。
4. 我们没有该域名的证书，也装不进系统 CA（装 CA 需要 root：`report/06:303` 的 tmpfs 改 `/apex/.../cacerts`）。
5. **客户端在校验失败时不会回落**：`report/06:593` 的失败形态是 `ClientHello → ServerFlight(~2600B) → 30B alert → FIN`；`report/INDEX:500`（A-7）明确「state 成功时覆盖、**失败时不回落**」；`report/06:253-261` 实测 uid-443 全 REJECT 后「无任何 `:80`」、屏幕「请确认网络连接状态后重试」⇒ **没有"降级到 http"这种兜底**。

⇒ **P9 把"攻 TLS"从"全链路"缩小到"一个请求"，但它没有消除那道墙；免 root 的障碍从"证书太多"变成"证书只有一张、但恰好是我们最不可能拿到的那一张"。**

**P9 真正的价值（如果保留 root）**：
- 只需 MITM **一条** TLS 连接（hop1），证书只需覆盖 `state-api.bluearchive-cn.com` 单域名（不必再凑 `*.bluearchive-cn.com` 通配，也不必管 `gsqc/gs-api/static`）。
- hop2 之后全部明文，**不需要再和 CDN / SNI 分流 / 多域名证书搏斗**；`static` 的资源也可以指向自己的 `http://` CDN 而不用真证书。
- 与 `report/00:97` 的判断一致方向：「只要 `Servers` 里给 `http://`，后面全链路明文，TLS 只需要解决 state 那一个请求」——**我确认这句在机制上成立，但"只需要解决 state 那一个请求"恰恰是最难的一个**。

### 6.3 剩余未知（逐条，不要当成已知）

| # | 未知 | 为什么重要 | 怎么证 |
|---|---|---|---|
| U1 | **没有任何一次"客户端真的发明文游戏请求"的实测** | 是 P9 的核心假设。H1 只证明"scheme 被接受"，没证明"被连上" | 拿到 root 的一次性实验：让 hop1 走通（DNAT+真证书/自签）后把 `Servers` 改成 `http://<我们的IP>:80/api/`，看 access log 有无 `UnityPlayer` UA 的 `GET /api/state` + `POST /api/account/auth` |
| U2 | **`GetApiServerInfo` 探活时会不会因为 `http://` 明文而改变判定** | 它带一个 header 逐条试活（`report/24:224`）；若探活本身走 UnityWebRequest 且失败即跳过，明文没问题；若它要求 TLS 就死 | 同上一次实验，看 hop2 是否命中 |
| U3 | **hop1 那个 https URL 的确切来源**（M1 运行时解密 / M2 Unity 资源 / M3 Hosts 缓存） | 决定"能不能不改包就换成自有域名 + 明文"。若是 M2（ScriptableObject），改 11 GB 资源里的一个 asset 也许比重打包 APK 便宜 | 运行时在 `ServerInfoDataRepository.get_StateServerUrl` 返回处 dump 一次字符串（需 root 或 LSPosed） |
| U4 | **`Servers` 里同时给 http 与 https 时会选哪个** | H1 显示"保留了但没选中"，可能只是排序/live 判定 | 给 `Servers` 只放一条 `http://`（保持 `State:1`），看是否被采用 |
| U5 | **资源层（`AddressablesCatalogUrlRoots` / `ResUrls`）用 http 是否真的可行** | `report/54:243` 只有社区情报，本仓库未实测 | 把 `ResUrls` 改 `http://example.com/prodm39` ×3，看 `files/AssetBundles` 是否开始下载 |
| U6 | **`POST` 的 body 是 `multipart/form-data`（BestHTTP）——明文下 boundary/长度是否要特殊处理** | 与 scheme 无关，但换栈测试时会先撞它 | `report/41:61` 已记边界形态，照抄即可 |

### 6.4 一句话给 Lead

> **P9 在协议机制上成立、在 Android 侧无阻碍（NSC 明文为 true，我解出了原文），但它只覆盖 hop2 之后；hop1（`state-api` 的 https）是免 root 的唯一死结。要么保留 root 但把 MITM 面积从"全域名"降到"单域名单请求"，要么放弃免 root —— P9 不能把 root 省掉。**

---

## 7. 关键引文摘录（带 文件:行号）

**A. 明文策略 —— 一手（我本轮解出）**
```
work/ba/audit/ba-apk/jadx/resources/AndroidManifest.xml:188   android:usesCleartextTraffic="true"
work/ba/audit/ba-apk/jadx/resources/AndroidManifest.xml:189   android:networkSecurityConfig="@xml/http"
work/ba/bapatch/res.apk!res/xml/http.xml (264 B, AXML)
   -> <network-security-config><base-config cleartextTrafficPermitted="true"/></network-security-config>
   -> attr cleartextTrafficPermitted: type=0x12(INT_BOOLEAN) data=0xffffffff = true
   解码脚本: work/ba/noroot/_dd2_axml.py
```
**A'. 档案侧的错与对（供交叉核对）**
```
report/INDEX.md:513                       A-20：res/Dk.xml 不存在 → 已废（但同句承认"结论仍由 http.xml 支撑"）
report/06-手机基线恢复.md:628              grep 'networkSecurityConfig|cleartext|network' 全空（BRE 里 | 是字面量，方法学伪影）
work/ba/audit/ba-java.md:168-169          usesCleartextTraffic=true / networkSecurityConfig=@xml/http  ← 这条是对的
work/ba/audit/ba-sdk-protocol.md:10-11    "cleartextTrafficPermitted=true，全域名允许明文"
report/00-下一步总方案.md:97              "只要 Servers 里给 http://，后面全链路明文，TLS 只需要解决 state 那一个请求"
report/03-上游情报.md:396、:439、:511、:604   同一 Dk.xml 说法的 4 处残留（均需更正引用）
report/56-外部情报…md:109                 cc004 README：让用户自己把 cleartextTrafficPermitted 设 true（国际服）
report/05-AzusaBA可复用资产.md:213        AzusaBA 作者注释：明文被系统默认禁止（按 targetSdk 默认推的，不适用本包）
```

**B. 客户端 URL 来源**
```
report/11-客户端静态逆向-网关与证书.md:33-36   默认 connection group 字面量是 http:// ⇒ ApiUrl 消费端接受明文
report/11:156                            ["http://test-ba.yostar.net:5210/api/state", ×3]  @0x000c172b XOR 0xB5
report/11:160                            "注意它是 http://，不是 https（对 Q3 很重要）"
report/11:165-173                        state-api 四重证伪（ASCII/UTF-16/XOR256/keystream≤8）全 0
report/11:313-314                        "ApiUrl 消费端接受 http = 强" / "没有强制 https 逻辑 = 中（负证据）"
report/54-客户端补丁方案-本地配置绕过.md:419-422   服务器地址无静态来源；改本地文件改不到
report/54:237                            "ResUrls 只喂给资源层。API 主机名/网关名不来自这里"
report/54:243、:452                      社区样例用 http:// 明文（外部情报，未本地实测）
```

**C. 三段链条（Servers → ApiUrl → RPC）**
```
report/24-state接口schema反推.md:146-147   ApiUrls=List<string>+apiIndex+ResetApiUrl；ApiUrl 只读派生=ApiUrls[apiIndex]
report/24:224                            GetApiServerInfo 迭代器：<i>5__4 下标 / <isLive>5__3 / <header>5__2 ⇒ 按 Servers 逐条探活
report/22-服务端取证记录.md:20            01:42:19 同一秒并发 4 条 TLS：state-api / gsqc-api / static / 无SNI ⇒ 客户端真去连 Servers
report/101-官方真服抓包分析.md:90-91      官方客户端 state-api(GET,161B) → 0.3s 后 gsqc-api(GET,676B)
report/41-Account_Auth字段级排查.md:486-488 ApiUrl 来自 Servers，拼成 {ApiUrl}account/auth；"gateway"/"account/auth" 字面量 0 命中
report/75-L0传输层…md:20、:234、:250      无 WebSocket / SSE / SignalR / 长轮询
```

**D. HTTP 栈分层（关键：三条链不是同一个栈）**
```
report/41:53-55    03:23:16 GET /api/state → state-api 200 116B ua=UnityPlayer(UnityWebRequest)
                   03:27:37 POST /api/account/auth → gsqc-api 404 1269B ua=BestHTTP/2 v2.4.0
report/41:60       "HTTP 栈是 BestHTTP/2，不是 UnityWebRequest/libcurl"
report/41:61       "编码是 multipart/form-data（boundary BestHTTP_HTTPMultiPartForm_*）"
report/41:496-497  /api/state → Http2Message/Http2DownloadMessage；/api/account/auth → Http1Message
report/101:291     User-Agent: UnityPlayer/2021.3.56f2 (UnityWebRequest/1.0, libcurl/8.10.1-DEV)
report/22:61、:68  nginx 实录 "GET /api/state HTTP/1.1" 200 … ua="UnityPlayer/…libcurl/8.10.1-DEV"
                   ↑ HTTP/1.1，不是 h2（推翻 report/24:226 的"走 HTTP/2"推断）
work/ba/audit/ba-sdk-protocol.md:30       SDK 层 UA = okhttp/4.9.2
```

**E. 明文实测（唯一的成功案例 + 唯一一次真塞明文）**
```
work/ba/audit/ba-sdk-protocol.md:64   "sdk_url 改为本地 HTTP 后 SDK 真的连过来 ✅ 抓到 6 个真实请求"
report/04-服务端就绪度.md:288         "HTTP 明文 … 已实现（sdkcard.py:73-90），实测 6 个请求全抓到"
report/13-总账…md:26                  C7【已证实】sdk_url=http://127.0.0.1:8080 + relay.sh → https://example.com/sdk
report/06-手机基线恢复.md:240-251     H1：Hosts 写 "http://example.com/api/"（78B→127B 原样保留），
                                     但"全程无 :80 连接"、"解析并保留了我们的候选，但没去连它" ⇒ 被接受、未被选中
report/06:245、:250                     Hosts 结构里 url 字段长度 1c(28) = "http://example.com/api/" 原样写入并保留
```

**F. hop1 绑死 https + 失败不回落**
```
report/22:12-14   "对 state-api.bluearchive-cn.com 4 次完成 TLS 1.2 握手（ClientHello → 证书 flight → ClientKeyExchange → CCS → Finished）"
report/23:48      "state-api 这条**明确带 SNI**"；report/22-真实上游接口取证.md:25 记 ClientHello 353 B
report/06:593     失败形态：ClientHello → ServerFlight(~2600B) → 30B alert → FIN
report/INDEX:500  A-7：Hosts 是 Servers[] 的写穿缓存，state 成功时覆盖、失败时不回落
report/06:253-261 uid 级 443 全 REJECT → "无任何 :80"、"无 <SERVER_IP>:80" ⇒ 无任何明文降级回路
report/06:309-314 删掉 Hosts 不被重建 ⇒ 客户端全程没请求 state（该次实验）
```

**G. 服务器侧能发明文（≠ 客户端愿意）**
```
report/06:241     "服务端实测：http://example.com/api/Queuing/Ping → 200"（curl，非客户端）
report/13:58      S12 同结论
report/09:682-689 §10.8 公网取回 body + "https://example.com/api/state … 返回 200"
                  ↑ 注意是 https；685 行的 http://127.0.0.1:5000/api/ 是我方 nginx 手写占位（09:513、:518）
```

---

## 附：本轮新增/改动的文件（均在允许目录内）

| 文件 | 说明 |
|---|---|
| `work/ba/noroot/_dd2_axml.py` | 我写的 AXML 解码器（只读输入，无网络），用于解 `res.apk!res/xml/http.xml` |
| `work/ba/noroot/_dd2-P9-plaintext.md` | 本文件 |

未修改任何现有文件；未连接服务器/手机；未执行网络操作。
