# 免 root 方案枚举与可行性判定

> 产出：`work\ba\noroot\OPTIONS.md`
> 输入：`report\` 全量文档（只读）+ 4 路并行深挖（`_dd1-P2-repack.md`、`_dd2-P9-plaintext.md`、`_dd3-P4-userCA.md`、`_dd4-integrity.md`）+ 本报告自己的独立复核（含自行解 AXML、fetch Unity 发布说明原文）
> 口径：**【确证】**=有文档行号/实测原文；**【推断】**=由确证推出但未上机；**【未知】**=明确未验证；**【已纠错】**=本报告推翻了文档库里的既有结论
> 纪律：本文件不改任何现有文件、不连服务器、不连手机
>
> **本报告在写作过程中推翻了 4 条既有判定**（都是因为找到了更硬的一手证据）：
> ① `report\06:628`+`INDEX:513`「manifest 里没有 networkSecurityConfig」→ **属性存在**（AXML 是 UTF-16，ASCII grep 必 0 命中）§1.1
> ② `report\INDEX:503` 等「客户端不采纳 `Servers[]`」→ **采纳**，只是不决定 hop1（F4）
> ③ 「重签会被 ACE 杀」→ 是风险预判、不是观测（§3.1）
> ④ 「TapSDK 验签是改包路线的卡点」→ 已被明确记为"既知现象、不影响流程"（`report\29:81`）

---

## 0. 一句话结论

**"必须 root" 不成立；"零操作" 也不成立。**

免 root 的真实成本不是 ACE，也不是"改包会不会被杀"，而是两件互相独立的事：

| 要件 | 需要什么权限 | 免 root 是否有替代 |
|---|---|---|
| **A. 引流**：把 `sdk-api.yostar.cn` / `state-api` / `gsqc-api` 的连接导到我们服务器 | 现状用 `iptables -t nat DNAT`（root） | ✅ 有四种：VpnService / 改 DNS / 路由器 / adb 全局代理 |
| **B. 取信**：客户端接受我们服务器出示的证书 | 现状把 CA 写进 `/system`+`/apex`+`/data/misc`（root） | ✅ **可能不需要 root**：Unity 2021.3.48f1 起把"用户安装的 CA"并进 `trusted_ca`（UUM-73839，一手），本包 2021.3.56f2 |

⇒ **最小免 root 路径 = 官方 APK 原样 + 用户手动装我们的 CA 到「用户证书」+ 一次 VpnService/DNS 引流（只拦 hop1 的 1~2 个域名）+ 服务端把 hop2 之后降成明文 http。全程不 root、不改包。**

⇒ 但不是只有这一条：**改包路线（patch `ValidateCertificate`）也已确证没有硬阻碍**（ACE 不拦、TapSDK 不阻断）。所以免 root 有**两条互相独立**的路，任意一条通就够。

⇒ 而路径 A 压着一个**从未被隔离验证**的变量：**用户证书到底吃不吃**（详见 §3.3）。项目的 CA 路线一直是"三处同时装"，从来没有单独试过"只装用户证书"。这是整份报告里最重要的一条待验证项，也是唯一能一票否决路径 A 的变量。

---

## 1. 先钉死五条事实（后面所有判定都建立在这五条上）

### F1【确证】客户端的 TLS 是 **libcurl + UnityTLS**，不是 Android 的 Conscrypt/TrustManager

- 请求头：`User-Agent: UnityPlayer/2021.3.56f2 (UnityWebRequest/1.0, libcurl/8.10.1-DEV)`（`report\101-官方真服抓包分析.md:291`、`report\22-服务端取证记录.md:68`）
- 报错原文：`E Unity : Curl error 60: Cert verify failed. Certificate is not correctly signed by a trusted CA. UnityTls error code: 7`（`report\06-手机基线恢复.md:643`）
- 同一错误串对应 Unity 官方 issue：`[Android] error "Curl error 60 ... UnityTLS error code 7" ... self-signed certificate`（`report\12-外部资料-证书与网关重定向.md:157`）

**推论**：任何"Android 层"的信任控制手段（`networkSecurityConfig`、`X509TrustManager` hook、`SSLContext`）**在原理上就够不到这条链路**。这一条直接决定了 P2、P10 的死刑。

### F2【确证】客户端**确实按信任库校验证书链**，且 CA 一生效 TLS 立刻通过

> 「46 条 `alert 49` **全部落在 01:24:58–01:33:45**（CA 生效之前），01:33:45 后**归零**、01:34:52 同一条链路直接 200 ⇒ 49 的消失与 CA 生效严格同步，指向 **trust store**。后来真正的报错是 `Curl error 60 / UnityTls error code: 7`（unknown CA）」
> —— `report\INDEX.md:503`（附录 A-10，**推翻了 15/16/21 号报告的"pinning"判定**）

配套证据：
- nginx 侧 `GET /api/state HTTP/1.1 200 180` + UA（`report\22-服务端取证记录.md:61`、`:68`）
- 链路切换到 `ca2/chain.crt`（`CN=BA Test Root CA`）后即通（`report\22-服务端取证记录.md:296`、`report\INDEX.md:541`）
- `report\06-手机基线恢复.md:655`：此前失败的**真因是服务端链的根 ≠ 装进信任库的那张 CA**，不是 pinning

**推论**：**"客户端根本不校验证书"这个假设已被证伪**。任何方案都必须解决"根被信任"。这是免 root 路线的真正战场。

### F3【确证·已纠错】`networkSecurityConfig` **确实存在**，明文全放行；但它只控制 Java 层栈，够不到游戏 TLS

> ⚠️ **本条推翻了文档库里的两条"结论"**（`report\06:628`、`report\INDEX.md:513` 附录 A-20）。纠错过程见 §1.1。

实测原文（`work\ba\audit\ba-apk\jadx\resources\AndroidManifest.xml:188-189`）：

```xml
android:usesCleartextTraffic="true"
android:networkSecurityConfig="@xml/http"
```

解开 `@xml/http` 得到（两个独立来源，内容一致）：

```xml
<network-security-config><base-config cleartextTrafficPermitted="true"/></network-security-config>
```

- **它到底是哪个文件**：本包用 **AndResGuard 混淆过资源名**，`resources.arsc` 里 `0x7f120001` 的 key=`http` 指向 **`res/Dk.xml`**（DD1 做的字节级闭环：arsc → `res/Dk.xml` → `zip_listing.txt:24988` 存在）。项目自建的 `work\ba\bapatch\res.apk` 里同一份内容叫 `res/xml/http.xml`（DD2 解出，264 B）。
- **⇒ 所以 `report\01:338` 记的 `res/Dk.xml` 是对的；`INDEX:513`(A-20) 说"该文件不存在"是错的**（把 AndResGuard 混淆名当成了 res/xml 路径），`report\06:628` 的"grep 全空"同样是 ASCII grep 打在二进制 AXML 上的假阴性。

三条结论：
1. **`base-config` 级放行 ⇒ 全域名允许明文**，没有 `domain-config`、**没有 `<trust-anchors>`、没有 `pin-set`**。
2. ⇒ **"targetSdk=33 所以默认禁明文"这个前提在本 App 上不成立。**
3. **但它仍然救不了 P2**：`<base-config>` 里**没有** `<certificates src="user"/>`，而且 NSC 是 **Conscrypt（Java 层 TrustManager）** 的配置；F1 已证游戏 TLS 走 UnityTLS/BestHTTP，**够不到它**。`report\17:124`（"C3 系统/用户 CA、networkSecurityConfig = 已证伪"）、`report\12:387` 结论不变，只是**理由**从"属性不存在"改成"存在但控制的是另一套栈"。
   > **一条诚实的保留**：DD1 认为这一条"未决"而非"不可行"——因为如果 Unity 是通过 Java 的 `AndroidCAStore`/`TrustManagerFactory` 去收集 `trusted_ca`，那 NSC 就是**决定性的**，用户 CA 会被它挡住（此时改 `res/Dk.xml` 才有意义）。三个可能模型里，只有"Unity 自己直读目录"这一种让 NSC 无关。**§3.3 的第一发实验（只装用户证书）能同时把这件事判掉**：如果用户证书直接生效，说明 Unity 没走那条被 NSC 限制的路径，P2 永久作废。

### F4【确证·已纠错】`Servers[]` **会被消费**（hop2 起由我们定）；不被采纳的是 `files/Hosts` 那个落盘缓存

这里历史上把**两套完全不同的机制**混成了一件事，必须拆开：

| 机制 | 是否被采纳 | 证据 |
|---|---|---|
| **`Servers[]`（state 响应，服务端下发）** | **✅ 被采纳**。`ServerInfoDataRepository.GetApiServerInfo` 是**迭代器**，带 `<header>` 对 `Servers` **逐条探活**判断 `<isLive>`；`ApiUrl` 是只读派生值（`apiIndex` 从 `ApiUrls` 取）；下游拼 `{ApiUrl}account/auth` | `report\24:224`、`:147`、`report\41:486`、`:497` |
| **`files/Hosts`（客户端落盘的缓存）** | **❌ 不被选中**。写进去的候选"原样保留但不被选中"，state 失败时也不回落 | `DEADENDS.md:88-110`（D-10/D-11/D-12）、`:120-126`（D-14） |

**⇒ 修正后的判定**：
- **服务端下发 `Servers[]` 是有效控制点**，而且它决定的是 **hop2 及之后**（`{Servers[i]}state` → `ApiUrl` → 全部 RPC）。**这是 P9 能成立的全部机制基础，也是本报告最重要的可利用面。**
- **改不动的是 hop1**：`GET https://state-api.bluearchive-cn.com/api/state` 这一枪的 URL/scheme 是运行时解出来的（`report\11:§3.3` 四重证伪），服务端管不着。**hop1 是免 root 的唯一死结。**
- **但 hop1 只有一跳**。⇒ 证书需求从"所有域名"缩到"一个域名、一次请求"。

> **对核心问题的回答**：这个方案能不能让客户端认为"自己连的是官方服务器"？
> ——**不需要"认为"。** 客户端只校验两件事：① 我连的这条 TLS 里，证书链的根在不在 `trusted_ca` 里；② 证书的主机名对不对得上我要的域名。**它从不反问"对面这个 IP 是不是官方的"**。所以 P8（"用客户端本来就信任的证书"）是伪命题：我们要的不是官方私钥，只是**任意一张根被信任的证书**——这个根我们自己造、用户自己装。

### F5【确证】同一个 App 里跑着**三套 HTTP 栈**，取信必须分别验证

| 请求 | UA / 栈 | 信任来源 |
|---|---|---|
| `GET /api/state`（hop1） | `UnityPlayer/2021.3.56f2 (UnityWebRequest/1.0, libcurl/8.10.1-DEV)` | **UnityTLS 的 `trusted_ca`**（`report\41:496`、`report\101:291`） |
| `POST /api/account/auth` 及之后全部 RPC（hop2+） | **`BestHTTP/2 v2.4.0`**（`Http1Message`，`multipart/form-data`） | **BestHTTP 自带的 TLS 栈**（`report\41:497-499`：metadata 里 `BestHTTP` 命中 135 处、BouncyCastle 整套） |
| SDK 6 个请求 | `okhttp/4.9.2`，**明文 http** | 不涉及 |

**⇒ 这是最容易踩的一个坑**：`/api/state` 通了**不等于** RPC 也通。两套栈的信任锚可能是两套（`report\15:§2.3` 早已提出这个岔路："如果网关请求走 BestHTTP + BouncyCastle，那 `CertificateHandler` 根本不参与"）。
**⇒ 反过来，这也给了 P9 一个巨大价值**：如果把 hop2+ 降成明文 http，**BestHTTP 的 TLS 问题整个消失**，只剩 hop1 一处需要取信。

> ⚠️ **一条必须否掉的误读**（DD3 提出，本报告不采信）：有人据 `report\22:24` 推断"BestHTTP 那条栈对自签证书不设防，所以只有 state 一跳需要 CA"。
> **这条推断是错的**：`report\22:33` 明确记了 `01:25:00 gsqc-api TLS 会话：CH 355 B → flight 2421 B → **7 B 明文 alert(49)** → RST` —— **gsqc 也拒了**。
> 而且那个时刻的 gsqc 连接很可能就是 **UnityWebRequest 的 state 兜底请求**（`report\41:54`：`/api/state` 同时打 state-api 与 gsqc-api，两者 UA 都是 `UnityPlayer`），**根本不是 RPC 栈的观测**。
> **⇒ 正确结论：两套栈都会拒我们的证书。** 所以 §6 第 6 条的"把 `Servers[]` 指向我们**有公网真证书**的域名"不是可选项，而是**必需项** —— 它是唯一能让 hop2+ 在"BestHTTP 有自己独立信任库"这个未知下仍然安全的设计。

### §1.1 档案纠错（两条，都是同一个根因）`report\06-手机基线恢复.md:628` 写"AndroidManifest.xml 里 grep `networkSecurityConfig|cleartext|network` → 全空"，`report\INDEX.md:513`（A-20）据此把"cleartext 全允许"的结论一并废掉。

**根因**：AXML 的 string pool 是 **UTF-16LE**，对二进制 XML 做 ASCII grep **必然 0 命中**。本报告用 jadx 解出的文本 manifest + 手解 `http.xml`（AXML）复核，两条都推翻了。

**教训（写进纪律）**：**"grep 不到"不能当作"不存在"的证据，尤其是对二进制/UTF-16 结构。** 这条同样适用于本报告自己 —— 凡涉及"某属性/某文件不存在"的判定，必须有"解析成功"的正控。

---

## 2. 主表

| # | 路径 | 具体做法 | 前置条件 | 技术卡点 | 可行性 | 需要真机验证什么 |
|---|---|---|---|---|---|---|
| **P1** | 改 APK 里的 `state-api` 域名 → 重打包 → 重签 → 装 | apktool/7z 解包 → 在全文件里替换域名串 → repack → zipalign → apksigner | 无（免 root） | **没有可改的字符串**：4 种方法（ASCII / UTF-16LE / 全 256 单字节 XOR / 周期≤8 keystream）在 metadata + libil2cpp 上对 `state-api`/`bluearchive-cn`/`gsqc-api` **全部 0 命中**（`report\11:§3.3`）⇒ 地址是运行时解密/服务端下发，静态改不到 | **不可行** | 无需（静态已证伪）。**要验的是它的替代 P1b** |
| **P1b** | 改 metadata 里的**默认连接组**字面量 `http://test-ba.yostar.net:5210/api/state` | `global-metadata.dat:0xc172b`，XOR key `0xB5`，换成我们的地址；metadata 在 `assets/` 内 zip 条目 ⇒ **必须重打包重签**（`report\30:337`） | 改包 + 重签 + 2.1 GB 分发 | ①这只是"默认连接组"，生产值由 `/api/state` 覆盖（`report\11:§3.4b`）⇒ **大概率被覆盖、白改**；②重签 → TapTap 验签（见 P12） | **不可行（收益疑为零）** | 默认连接组在 `ServerInfo` 存在时是否参与选路 |
| **P2** | 改 `res/Dk.xml` 加 `<certificates src="user"/>` → 重打包 | **属性已经存在**（`android:networkSecurityConfig="@xml/http"` → arsc `0x7f120001` → `res/Dk.xml`，AndResGuard 混淆名），**不用改 manifest**，只改这**一个** 264 B 的 AXML + 重签（`res/*` 恰是已实测最安全的改动面） | 改包 + 重签 | **死点是打错靶**：NSC 只被 **Java 层（Conscrypt/TrustManager）** 消费，而它只影响 **okhttp（SDK 那 6 个请求）**；SDK 段本来就已经走明文 http（P15/P9），**没有任何需要它信任的事**。游戏 TLS（hop1 UnityTLS、hop2+ BestHTTP）**都不读 NSC**（F1/F5）。⚠️ **DD1 保留异议**：若 Unity 是通过 Java `AndroidCAStore` 收集 `trusted_ca`，NSC 就是决定性的——但那种情况下**用户证书本来就生效（P4 直接赢）**，也用不着改它 | **不可行**（但 §3.3 的第一发实验会顺带把它永久判掉） | 无需单独验：E-USERCA 通过 ⇒ P2 作废；E-USERCA 失败 **且** 怀疑是 NSC 挡的 ⇒ 才做 E2（只改 `res/Dk.xml` 重签） |
| **P3** | VpnService（用户点一次授权，免 root）做 TCP 转发到我们服务器 | 装一个自研/现成 VPN App（mihomo-TUN、TunProxy、proxydroid）→ 按域名/IP 分流 → 把 `state-api`/`gsqc-api` 的 443 转给我们的服务器；TLS 原样透传 | 用户点一次"允许 VPN" | **只解决 A（引流），不解决 B（取信）**。若只做 TCP 转发不改 TLS，客户端看到的是我们的证书 ⇒ 需要 P4 或 P9 配套 | **单独不可行 / 配 P4 可行** | 分流规则是否命中 Unity 的连接（按域名需解 SNI；按 IP 需处理 kunlun CDN 轮换） |
| **P4** | 让客户端信任"用户安装的 CA"（**不改包**） | 用户：设置 → 安全 → 加密与凭据 → 安装证书 → CA 证书 → 选我们的根。**必须走这条正规路径**（让系统自己写文件、自己定格式/权限/label），**不要手工 `cp` 一个 DER 进用户库**（历史上那次"只装用户 CA 失败"就是 DER + 链根不匹配的双重污染） | 用户点几下（Android 11+ 需锁屏密码；Android 14+ 会有常驻警告通知）；**不需要 root** | `targetSdk=33 ≥ 24` **在 Android 框架层**确实不信任用户 CA（`report\20:170`）——**但 UnityTLS 是自研栈，不经过 `ApplicationConfig` 那套判断**。Unity 2021.3.48f1 修复项原文：*"Fixed issue where user installed certificates directly to an Android device wouldn't show up in the `trusted_ca` list"*（UUM-73839，一手，见 `report\12:162`，已由本报告独立核对原发布说明）。本包 `2021.3.56f2 > 48f1` | **需真机验证（强倾向可行）** | **唯一决定性实验**：用户证书单独生效 vs 只有系统 CA 生效（§3.3） |
| **P5** | 改 hosts（需要 root） | — | root | 已被排除；且**手段本身也错**：真因不是 HTTPDNS，而是 app 解析由 **netd(pid 1937)** 代答、netd 在**另一个 mount namespace**（`report\13:122`、`report\INDEX.md:501` 附录 A-8） | **排除（需 root）** | — |
| **P6** | 改手机 DNS（用户设置里改，免 root） | ① Wi-Fi 静态 DNS 指向我们的 DNS（返回我们的 IP）；② 更干净：**私有 DNS（DoT）填 `dns.example.com`**（我们域名有公网真证书 ⇒ DoT 不需要自签 CA） | 用户改一次设置 | 只解决 A。**若手机上有任何 VPN tun（本机实测默认路由走 `vgate0`），DNS 会被 tun 接管**（`DEADENDS.md:136-141`，D-16）⇒ 与 P3 互斥、二选一 | **单独不可行 / 配 P4 可行** | 客户端是否真的走系统 DNS（A-8 说走 netd）；有 VPN tun 时的实际解析路径 |
| **P7** | 路由器/热点层透明代理 | 自家路由器 dnsmasq 劫持 + 端口转发到我们服务器 | **用户得控制路由器**（家庭宽带多数可以；4G/酒店不行） | 同 P3：只解决 A。证书照旧 | **单独不可行 / 配 P4 可行**；依赖用户环境 | 与我们无关，属部署环境变量 |
| **P8** | 让我们的证书变成"客户端本来就信任的" | 两条：① 拿官方私钥（不可能）；② 用**公网 CA 给 `state-api.bluearchive-cn.com` 签一张**（需要该域名 DNS 控制权，我们没有） | — | ①无解；②无解。**但这条命题本身是伪命题**——见 §1 F4 的推论：我们不需要"官方那张证书"，只需要"任意一张根被信任的证书"，而那个根可以由我们自己造、用户自己装（P4） | **不可行（命题本身错）** | 唯一有价值的变体：**客户端是否校验主机名**（若不校验，我们就有 `example.com` 的公网真证书可用 ⇒ 连 CA 都不用装）。见 §3.3「E-HOSTNAME」 |
| **P9** | 让游戏 RPC 走明文 HTTP | **只做 hop2+**：`/api/state` 的响应体里 `Servers` 给 `http://<我们的地址>/api/`，从 `{Servers[i]}state` 起整条链明文 | **零客户端改动、零 root**（只改我们自己的 nginx JSON） | **hop1 动不了**（`state-api` 的 https 由运行时解密而来）；hop2 的 `GetApiServerInfo` **探活**是否接受 `http://` **未实测**（`report\24:224` 的 `<isLive>` 迭代器带 header 逐条试活）；`report\06:240-251` 的 H1 是"没被选中"、**不能**当作"拒绝 http"的证据 | **hop2+ 可行（机制确证，缺一次实测）**；**hop1 不可动** | ① `Servers` 只放一条 `http://`（保持 `State:1`）时是否被探活采纳；② 探活本身是否要求 TLS |
| **P10** | 逆 SDK 层（`sdk-api.yostar.cn` 走 okhttp，Java 层） | hook `X509TrustManager` / 改 dex | root 或改包 | **对目标无意义**：okhttp 只跑 SDK 的 6 个请求（`report\04:288-292`），**游戏 RPC 一条都不走 okhttp**（`report\10:66` C15："即便 hook，也只影响 SDK 的 Java 请求，对 native/Unity 流量无意义"）。而且 SDK 段本来就已经能用明文 http 解决（见 P15） | **不可行（选错了层）** | 无需 |
| **P11** | `adb shell settings put global http_proxy IP:PORT` 或 Wi-Fi 里填代理（**免 root**） | 用户开 USB 调试 / 改 Wi-Fi 高级选项 → 客户端走我们的 HTTP 代理（CONNECT 隧道后**由我们连到我们的服务器**，等价于零 root 的 DNAT） | — | ①只解决 hop1：**UnityWebRequest 吃系统代理**（有实测旁证：`report\101:246` 的抓包同时看到 `okhttp` 与 `UnityWebRequest`，只有 RPC 没进来）⇒ **代理能拦 hop1**；②**BestHTTP（hop2+）不吃系统代理** ⇒ 代理拦不到 RPC。**但这不重要**——hop2+ 可以由 `Servers[]` 指到我们自己**有公网真证书**的域名，本来就无需拦截；③仍然不解决证书（CONNECT 隧道后照旧要 TLS） | **可行（作 hop1 的引流手段）** | 代理能否真的把 CONNECT 的**目标**改到我们服务器（而不是转发到真实官方） |
| **P12** | **改包：patch `CustomCertificateHandler.ValidateCertificate` → return true**，分发 mod APK | ① 定位方法地址（metadata 混淆，标准 Il2CppDumper 走不通，`report\11:§2.3`）② 改 libil2cpp 代码洞（已有成熟载体，`DT_INIT`+代码洞**已证不触发 ACE**）③ repack → zipalign → apksigner → 分发 | 改包 + 重签 + 2.1 GB 分发；主要成本在"定位方法地址" | ①**【已知唯一难点】定位方法地址**（需运行期 dump 明文 metadata）；②**ACE 不拦**（§3.1，已有 2.143 GB 重签包跑到"取得昵称"界面的确证）；③**TapSDK 签名错误不阻断**：toast `TapSDK: 包名、签名错误。详见 ErrLog` 已被列为"**既知现象、不影响流程**"（`report\29:81`，用户确认）；④装不上只影响开发机，新用户无此问题 | **可行**（无已知硬阻碍） | ① `ValidateCertificate` 是否真的只在 hop1 生效、hop2（BestHTTP）还有没有另一处校验；② 分发 2.13 GB 的实际转化率 |
| **P17** | **免 root、免改包：走「外部可写目录」热更通道**（metadata / iFix 补丁） | 客户端在 `/storage/emulated/0/Android/data/<pkg>/files/`（`persistentDataPath`）下有一整套可写数据，其中 `il2cpp/Metadata/global-metadata.dat` + 同目录 `il2cpp/unity.ver = 611ecbd3-…`（`report\21:1116`）。**`unity.ver` 这个版本标记是热更框架的典型布局**（`report\52:506` 也把该目录称为"本路线唯一的低成本入口"）⇒ 用户可用 **adb push / MTP 直接覆盖**（不需要 root） | 一条 USB 线 / 一次 `adb push`；无 root | ①**前提未验证**：APK 内 `assets/bin/Data/Managed/Metadata/global-metadata.dat` 与外部这份谁是权威，**不知道**（`report\52:502-504`：`libil2cpp.so` 里只有一个文件名串，判不了 mmap 还是 read）；②**有一条不利先例**：`report\54:34` 盘清了 13 个本地配置文件 + 86 个 key，结论是"**唯一被证明改了立刻生效的客户端配置是 APK 内的 `sdk_url`**"⇒ 外部配置改了不生效；③**能力边界**：metadata 放的是**数据**（字符串、默认连接组 URL），不是代码 ⇒ 能做"改 URL"，**做不了"跳过证书校验"**（除非 iFix 补丁通道被证实可用——那样 `<>iFixBaseProxy_ValidateCertificate` 就成了入口，`report\11:80`、`report\15:255`） | **需真机验证（10 分钟、只读，性价比最高的一条）** | ① `ls -l` + `sha256sum` 两份 metadata 是否同一份；② 游戏运行时 `ls -l /proc/<pid>/maps \| grep -i metadata` 有没有那条外部路径；③ `persistentDataPath` 下有没有 iFix 的补丁目录、里面有没有 `.dll/.bytes`。**见 §5 路径 C** |
| **P13** | LSPatch（免 root 的 Xposed，本质仍是改包） | LSPatch 内嵌模块进目标 APK → 重签 → 装 | 改包 + 重签 | ①**撞"改包"的同一个面**（ACE `sourceDir` 完整性 / TapTap 验签）；②模块自签名校验（`report\05-AzusaBA可复用资产.md:43`、`:335-342`：`java/HookLoad.java:55-107` 在内嵌重打包时直接拒绝注入）；③仍要解决"改哪个函数" | **不可行（比 P12 更差：同样改包，还多一层）** | — |
| **P14** | Shizuku / adb shell 提权做 DNAT | Shizuku 把 adb 权限借给 App；或用 `adb shell` 执行 `iptables -t nat` | 用户开 USB 调试或装 Shizuku | **`iptables -t nat` 需要 `CAP_NET_ADMIN`，shell uid 没有** ⇒ DNAT 不可行。可做的只有 `settings put`（= P11）、`pm`、`am` | **不可行** | `adb shell iptables -t nat -L` 的返回（预期 permission denied） |
| **P15** | 改包：`assets/SDKConfigSettings.json` 的 `sdk_url` → `http://example.com/sdk` | 改一个 JSON 字段（原值 `https://sdk-api.yostar.cn`，`report\54:377`、`report\96:30`） | 改包 + 重签 | **这是全项目唯一被证明"改了立刻生效"的客户端配置**（`report\54:380`）。把 `https://` 改 `http://` + 指向我们自己的公网域名 ⇒ **SDK 段完全不需要 CA、不需要 DNS 劫持、不需要 VPN，走公网即可** | **可行（但不是全链路）** | SDK 段是否接受非 loopback 的明文域名（loopback 已被 N5 证实） |
| **P16** | 只靠服务端 `Servers[]` 改址（零客户端改动、零 root 的理想路） | nginx 里 `location = /api/state` 回我们想要的 `Servers` | 无 | **只在 hop2 生效**（`Servers` 会被 `GetApiServerInfo` 探活采纳，F4），**hop1 改不动**。所以它省不掉 hop1 的引流与证书，只能把 hop2+ 变成"随便给什么都行" | **部分可行（hop2）** | 同 P9 的两条 |

---

## 3. 三条深挖

### 3.1 P2 深挖：改包加 `networkSecurityConfig` 会不会被 ACE 杀？

**结论：ACE 那一关根本不是问题（已有确证）；问题是这个改动打不中目标，而且属性本来就在。**

#### (a) ACE 确实在跑 —— 但它的完整性校验是"定点"的，不是"整包签名"

反对"改包没事"的最常见疑虑是"ACE 会杀"。**先把 ACE 的存在钉死，再把它的校验范围钉死。**

**ACE 确实装在里面且在跑**【确证】：
- `libtprt.so`（1,692,296 B）被 `libil2cpp.so` 与 `libunity.so` **双向 `DT_NEEDED`** 依赖（`report\78:276-277`，ELF 实测）⇒ 每个游戏进程必加载
- 启动链：`TechApplication.attachBaseContext → AceApplication.attachBaseContextShell → libtprt.initialize()`（`report\DEADENDS.md:71` 的一手 `debuggerd -b` 栈）
- `:GP6Service / :GP7Service / :GP7Worker` 三个 exported 服务（`report\27:564`）
- 冷启动**第 0.00 秒**就给 `down.anticheatexpert.com/…/config2.xml` 发请求（`report\100:52`）

**但被钉死的对象只有三个，且不含 `libil2cpp`**：

| 对象 | 是否被 ACE 钉死 | 证据 |
|---|---|---|
| `libunity.so` | **是**（改 4 字节 → `SIGBUS reason=2 status=7`） | `report\DEADENDS.md:14-15`，E42 原厂对照 |
| `libtprt.so` | **是**（改任意字节 → `kill(SIGBUS)`） | `report\01:38`、`report\INDEX.md:48` |
| **`libil2cpp.so`** | **否**（改 5 字节 / 代码洞 + `DT_INIT` / root 原位替换，全都能跑） | `report\01:§4.1`、`report\10:59-64` |
| `assets/__tpinfo.*`（5 个自身完整性清单） | **删掉就整段跳过校验** | `report\01:§4.1`、`report\03:474-475`（上游把这叫"自身文件完整性"） |

**⇒ 这就是所有改包能跑的总前提**：删 `__tpinfo` + 只动 `libil2cpp`/`res`/`arsc`，不碰 `libunity`/`libtprt`。

#### (b) 重打包/重签：做过、签名真的换过、**装机后跑起来了**

| 事实 | 证据 |
|---|---|
| 链路："解官方 APK → 换 so/资源 → zipalign → apksigner"，E28→E44 十余版 | `report\57:136`、`report\57:328` |
| E30 记"**已签名已安装**"；E38"**正常跑 45 s+**"；**E42"能进主程序"** | `report\57:328`、`report\01:13` |
| `res/*` + `resources.arsc` 改动**不触发 ACE**（E32/E34/E42 均可启动） | `report\01:123`、`report\18:213` |
| 产物确实是 2.143 GB 游戏本体（`.idsig` 反推） | `report\57:21` |
| **设备现役 `base.apk` 内嵌的 `libil2cpp.so` 本身就不是原厂件**（sha `6e2edf5a…`，非原厂 `5ac1cbe0…`，代码洞里带旧桩），而**就是这个包**在 11-14 05:22 冷启动后一路走到"取得昵称"（05:23:37）与"姓名发音"（05:38:49）界面 | `report\08`、`report\INDEX.md:506`（A-13）、dd4 §2 |

**⇒ 证据面内没有任何一次"仅因签名变化 → SIGBUS/闪退"的观测。** 真正的失败全部来自改错了对象（`libunity` / `libtprt` / 加 `.so` / 改 `DT_NEEDED` / 动 dex / 改包名）。

#### (c) 那 P2 到底死在哪？—— 死点已经变了

**死点（唯一，且是原理性的）**：`networkSecurityConfig` 只被 **Java 层（Conscrypt / `TrustManagerFactory`）** 消费。而它在本 App 上唯一能影响的是 **okhttp 那 6 个 SDK 请求**——而 SDK 段本来就已经走明文 http（P15/P9），**没有任何需要它信任的事**。游戏 TLS 的两套栈（hop1 UnityTLS、hop2+ BestHTTP）**都不读 NSC**。

**⇒ P2 判定：不可行。** 不是"有风险"，是**改了一个对本目标无效的开关**。它想达到的目标（信任我们的 CA……其实连 CA 都不需要了）由 **P4（零改包）+ P9（hop2 明文）** 联合达成。

> 有人会问："`report\23:84` 不是说改 `res/xml` 的 NSC 是**优先级最高**的一条吗？"
> 那条是 2026-11-14 01:55 的**当时**优先级，前提是"必须绕 TLS"。`report\17:124` 次日已把它判为"已证伪"。本报告采信后者，并补上了**它为什么无效**的机制解释（F3/F5）。

#### (d) 改包路线真正的成本不在 ACE，在"装不上"（而且只影响开发机）

ACE 不拦，但要分清三种成本：

| 成本 | 影响谁 | 证据 |
|---|---|---|
| 签名变 ⇒ 必须卸载重装（同签名才能覆盖安装）⇒ **UID 变** ⇒ 11 GB 资源要 `chown -R <新UID>:1078`、丢 `/data/data` 登录态 | **只影响开发机**（新用户本来全新安装） | dd4 §5、`report\30:344` |
| `apksigner` 处理 2.13 GB 包需 **≥2.1 GB 空闲**，否则半截输出 | 开发机 | dd4 §5 |
| ACE"记账"：失败一次后后续实验全被 `SIGBUS` 污染，需删 `files/{ace_shell_di.dat, shell_cache, ano_tmp, data/app}` 复位 | **只影响开发机** | `report\01:141`、`report\04:418` |
| ~~TapSDK 验签~~ | — | **不是成本**：toast `TapSDK: 包名、签名错误。详见 ErrLog` 已被明确列为"**既知现象、不影响流程**"（`report\29:81`，用户确认） |

**⇒ 对"分发"来说，改包路线的成本几乎只有"2.13 GB 下载"。** 这一点与文档里"改包很危险"的既有印象相反，值得单独记住。

---

### 3.2 P9 深挖：游戏 RPC 走明文 HTTP，客户端接受吗？

**结论：hop2 以降——机制上确证成立，只差一次实测；hop1 一跳——改不动，是免 root 的唯一死结。**

#### (a) 三层分离

| 层 | 能否明文 | 证据 |
|---|---|---|
| **SDK（okhttp）** | ✅ **已实测跑通** | `sdk_url` 原值 `https://sdk-api.yostar.cn`（`report\54:377`、`report\96:30`），被改成 **`http://127.0.0.1:8080`**（裸 loopback + 明文）后整条卡密登录链通：6 个请求全命中、`quick-login` 200（`report\06:158`、`:355`、`report\10:17` N5、`report\01:55`） |
| **hop1：`GET https://state-api.bluearchive-cn.com/api/state`** | ❌ **我们改不了它的 scheme** | URL 无静态来源（`report\11:§3.3`：ASCII / UTF-16LE / 全 256 单字节 XOR / 周期≤8 keystream **四种方法全 0 命中**）；实测就是 https（`report\22:61`） |
| **hop2+：`{Servers[i]}state` → `{ApiUrl}account/auth` → 全部 RPC** | ✅ **机制确证，scheme 100% 由我们的 JSON 决定** | `ServerInfoDataRepository.GetApiServerInfo` 是迭代器、带 header 对 `Servers` 逐条**探活**、`ApiUrl` 为只读派生、下游拼 `{ApiUrl}account/auth`（`report\24:224`、`:147`、`report\41:486`、`:497`） |

**链条**：
```
hop1  GET  https://state-api.bluearchive-cn.com/api/state     ← 我们改不动（唯一死结）
      → 我们的 JSON: {"Servers":["http://<我们>/api/"], "State":0, ...}
hop2  GET  {Servers[i]}state                                  ← ★ scheme 由我们定
      → 我们的 JSON: {ApiUrl:"http://<我们>/api/", ...}
hop3+ POST {ApiUrl}account/auth …（BestHTTP/2, multipart）     ← 全部明文
```

#### (b) 三条支撑证据

1. **客户端出厂就愿意发明文**：唯一的游戏 API 字面量是 `["http://test-ba.yostar.net:5210/api/state" ×3]`（`global-metadata.dat @0x000c172b`，XOR key `0xB5`），**是 `http://` 不是 https**（`report\11:18`、`:156`）。同一个 DTO 的同一个字段，消费端接受 http（`report\11:313` 判为"强"）。
2. **Android 侧不设障**：`usesCleartextTraffic="true"` + `<base-config cleartextTrafficPermitted="true"/>`（§1 F3 解出的原文）。**而且原生 socket 本来就不受 NSC 管辖**——该策略只在 framework 层被消费。
3. **无 scheme 校验的游戏侧证据**：metadata 里 `StartsWith` / `UriSchemeHttps` 全部来自 BCL/TMP 库，不是游戏逻辑（`report\11:34`）。

#### (c) 与任务书的两处出入（必须更正）

- **`report\09:688` 不是"走 HTTP 实测成功"**。核对原文：结论行是 **`https://example.com/api/state -> 200`**（`:679`），"公网、真证书、无任何证书绕过"——它证明的是**TLS 那道墙可以靠"换自有域名"绕过**（`:688-689`），**不是**明文层的成功。同一 body 里的 `http://127.0.0.1:5000/api/` 是我方 nginx 手写占位（`report\09:513`、`:518`），不是客户端行为。
- **真正"走明文"的记录都是我们自己 curl**：`http://example.com/api/Queuing/Ping → 200`（`report\06:241`、`report\13:58`）。**客户端真发明文 RPC：至今 0 例。**

#### (d) 唯一一次把明文塞进客户端的实验（H1），为什么不算数

`report\06:240-251`：往 `files/Hosts` 写 78 B，`url(28)="http://example.com/api/"` →
- 启动后 **全程无任何 `:80` 连接**，app 仍连官方三台 `:443`
- `Hosts` 被重写成 127 B，**我们的 http URL 原样保留**（⇒ scheme 语法被接受）
- 原文结论："客户端**解析并保留了**我们的候选，但**没有去连它**"

`DEADENDS.md:96-102`（D-11）的教训写得很准："**不是 scheme 问题，是'候选项没被选中'**；scheme 这个变量已经被排除干净了。"

**⇒ 所以"客户端接不接受明文 http"这个变量，在 hop2 上仍然一次有效观测都没有。** 但注意：H1 证伪的是 `files/Hosts` 的**选中优先级**，**不是** `Servers[]` 的消费路径——后者是新证据（F4）。

#### (e) 判定实验（免 root，10 分钟）

```
前提：hop1 已打通（客户端能拿到我们编的 /api/state）
1. 我们 nginx 把 /api/state 的响应改成：
     {"Servers":["http://<我们的IP或域名>/api/"],"State":0,"Msg":""}
   （只放一条，避免"排序/多候选"干扰；保持 State:0 = 开服）
2. 服务端同时开 80 端口 + access_log，记录 UA
3. 冷启动游戏，看 80 端口有没有请求
判据：
   有  UA=UnityPlayer…  → hop2 明文成立，可继续（下一跳会变成 BestHTTP）
   有  UA=BestHTTP/2    → hop3 明文也成立 ⇒ hop2 之后整条链不需要证书
   无  + 客户端报网络错 → 探活要求 TLS ⇒ 回退到 https（仍需要证书，但只需一张覆盖该域名的）
排除：必须确认 hop1 本身是通的（否则是空测）
```

**要排除的已知陷阱**：`GetApiServerInfo` 的**探活**带一个 `<header>` 逐条试活（`report\24:224`）。如果它在探活阶段就要求 TLS，那么"给了 http 就不活"⇒ 整条 `Servers` 被跳过 ⇒ 表现得和"客户端不认明文"一模一样。**报告这个结果时必须能区分这两种情况**（看服务端 80 端口有没有任何字节/有没有 TCP 连接）。

#### (f) P9 判定（诚实版）

- **hop2+：可行（机制确证，待一次实测）。价值巨大**——它把证书需求从"所有域名 + CDN + SNI 分流"压缩到"**hop1 一个域名、一次请求**"，并且**顺带绕开 BestHTTP 那套独立 TLS 栈的信任问题**（F5）。
- **hop1：不可行（改不动）。** 免 root 仍必须解决它。
- **所以 P9 不能独立成立，但它是"最小免 root 方案"里不可或缺的一块**（见 §4 C1'）。

---

### 3.3 P4 深挖：免 root 实验设计（本报告最重要的一节）

#### 先说清楚这个实验在赌什么

- 赌赢：**免 root 全链路成立**，分发成本 = 用户点 3 下 + 开一个 VPN App。
- 赌输：免 root 只剩"改包分发 mod APK"一条，且要过 TapTap 验签。

外部依据（一手，本报告已独立核对原发布说明原文）：
> **2021.3.48f1 | Fixes | Android | Fix Android: Fixed issue where user installed certificates directly to an Android device wouldn't show up in the `trusted_ca` list. (UUM-73839)**
> —— https://yusjoel.github.io/UnityReleaseNotes/2021/2021.3.48f1.md（页面原文，本报告已 fetch 核对）

同一修复被 backport 到 `2022.3.55f1 / 6000.0.32f1 / 6000.1.0a6`（`report\12:165`）。**本包 2021.3.56f2 已包含。**
UUM-73839 对应 issue 的标题，就是本包 logcat 里那条一模一样的错误串（`report\12:157` vs `report\06:643`）——**同一个 bug、同一个修复**，这是这条推断最硬的一环。

剩下的不确定性只有一条：**Unity 把用户证书并进 `trusted_ca` 时，会不会被 `targetSdk=33` 挡住？** 判断依据（【推断】，必须实测）：
- `targetSdk ≥ 24` 的用户 CA 限制是在 **Conscrypt / `ApplicationConfig`** 里实现的（`report\20:170` 引 AOSP 源码逻辑）；
- Unity 若走的是自己枚举证书目录的 JNI 代码，则**绕过了那层判断**；
- Unity 能"修复"这个问题本身，也反证它不是走被限制的那条路。

#### 实验 E-USERCA（**全程不需要 root**）

**前置（缺一不可）**
1. 一台**没有 root** 的 Android 手机（**必须是干净机器** —— 这是整个实验的核心。用现在那台 KernelSU 机器做等于没做，因为系统库里已经有 `fd8b2b01.0`）
2. 官方 APK 原样安装（未改包、未重签），登录到能出网关请求的那一步
3. 我们服务器：`ca2/chain.crt`（leaf + root **一起下发**，UnityTLS 不补中间证书，`report\12:182`）
4. 我们的根证书 PEM/DER 文件（`BA Test Root CA`）
5. 引流手段（三选一，都不需要 root）：mihomo/Clash **TUN 模式**（VpnService）；或 Wi-Fi 静态 DNS 指向我们的 DNS；或私有 DNS(DoT)

**步骤**

| # | 动作 | 观测点 |
|---|---|---|
| 0 | 服务端正控：`curl --cacert ca.crt --resolve state-api.bluearchive-cn.com:443:<IP> https://state-api.bluearchive-cn.com/api/state` | 必须 **200**。不 200 就别往下做（否则会重演 `report\06:653` 那个"链根不对"的假阴性） |
| 1 | **对照 A（阴性对照）**：手机**不装 CA**，其余全同，冷启动游戏 | 预期 `Curl error 60 / UnityTls error 7` |
| 2 | 装 CA：设置 → 安全 → 加密与凭据 → 安装证书 → **CA 证书** → 选我们的根 | 设置里"用户证书"下出现 `BA Test Root CA` |
| 3 | `logcat -c`；`kill -9` 游戏进程；重新拉起 | — |
| 4 | 抓 `logcat -b all \| grep -iE "UnityTls\|Curl error\|trust anchor\|ssl"` | 有没有 `Curl error 60` |
| 5 | 服务端同时抓：nginx access_log + tcpdump | 有没有 `GET /api/state` 200 |
| 6 | **对照 B**：装 CA + 服务端换回 `ca3/chainS.crt`（别的根） | 必须失败（证明"信任锚必须是我们装的那把"，排除"随便什么证书都过"） |
| 7 | **对照 C**：删掉用户证书，其余不变 | 必须失败（排除 CA 泄漏/缓存） |

**判据表**

| 观测 | 结论 | 下一步 |
|---|---|---|
| 步骤 1 失败 + 步骤 4~5 通过 | **用户证书生效 ⇒ 免 root 成立** | 直接做分发包装（§5 路径 A） |
| 步骤 1 失败 + 步骤 4 仍 `Curl error 60`，且步骤 0 已正控 200 | **用户证书不被 UnityTLS 采用** ⇒ 免 root 必须改包（P12）或仍是 root | 查 `logcat` 有没有 `DirectoryCertificateSrc` / Conscrypt 相关（分层判据见 `report\21-决策日志-CA路线攻坚.md:§三`） |
| 步骤 1 **就通过**（不装 CA 也通） | 说明该机器/该证书链不校验 —— 但 F2 已证会校验，**先怀疑实验污染**（系统库里已有旧 CA、或流量没被劫持成功） | 回步骤 0/6 |
| 步骤 6 意外通过 | **客户端不校验信任锚**（= 不校验链）⇒ 与 F2 矛盾，实验设计有洞 | 检查是不是没走到我们服务器（看服务端日志） |

#### ★ 判据必须覆盖**两套栈**（否则会得出"通过"的假结论）

F5 已证 hop1（UnityWebRequest/UnityTLS）与 hop2+（BestHTTP/2）是两套 TLS 栈。**只看 `/api/state` 200 是不够的**：

| 判据 | 覆盖哪套栈 | 怎么判 |
|---|---|---|
| 服务端 access_log 出现 `GET /api/state` + UA `UnityPlayer/…` | hop1（UnityTLS） | 有 ⇒ hop1 取信成功 |
| 服务端出现 **`POST /api/account/auth` + UA `BestHTTP/2`** | hop2+（BestHTTP） | 有 ⇒ **BestHTTP 那套也取信成功**（这是更强的一条） |
| 只有 hop1、没有 hop2 | 只解决了 UnityTLS | 需再查 BestHTTP 的信任锚是不是另一套 |

**⇒ 一个更强的设计**：直接把 `Servers` 降成 `http://`（P9 的判定实验）——如果 hop2 明文成立，**BestHTTP 的 TLS 问题就整个不存在**，本实验只需保证 hop1 通过。这是把两个未知量拆开、一次只赌一个的做法。

#### 现成器材：`p4_proxy.py`（本目录，已落盘）

实施这个实验不需要从零写代码，`work\ba\noroot\p4_proxy.py` 已经写好（`py_compile` 通过，**未联网自测**）：

| 参数 | 用途 |
|---|---|
| `--mode proxy` | 起一个 **CONNECT + TLS 终止** 的代理，配合手机 Wi-Fi 里的代理设置 —— **全零 root 的引流方案** |
| `--pass-others` | 只 MITM 目标主机，其它域名原样透传 ⇒ **不会把 SDK 段打断**（否则实验会因为别的原因失败，污染判据） |
| `--mode direct` | DNAT 变体，按 **SNI** 判主机（给"客户端不吃代理"的情况用，把"重定向"与"取信"两个变量解耦） |
| 输出 `P4-TLS-OK` / `P4-TLS-REJECT alert=…` | **判据就在这两行**。`REJECT` 会带 alert 号，可按 `report\16` 的 alert 语义表分层定位 |

**⇒ 判定是"非对称"的，这一点很重要**：
- 拿到 **`P4-TLS-OK`** ⇒ **自证成立，不需要任何正控、全程没碰过 root**。（因为不装 CA 时它必失败——步骤 1 是阴性对照，已经在同一轮里做掉了。）
- 拿到 **`REJECT`** ⇒ **本轮不下结论**，必须补一个**需要 root 的正控**：把同一张 CA 装进系统库（`4cc9cfb3.0` + `chcon system_security_cacerts_file`，且**必须在 App 的 mount namespace 里 `ls` 得到**才算装上），若正控也 `REJECT`，说明实验装置本身有问题，本轮作废。

**⇒ 也就是说：免 root 的"证明"不需要 root，只有"证伪"才需要 root。** 这是一个很划算的赌注结构——先花 30 分钟就能拿到肯定答案；否定答案要更贵一点，但也顺便把"是不是装置坏了"排除掉。

#### 反例排除（这一条是历史教训，必须写进实验纪律）

- ❌ **不要靠 `files/Hosts` 引流** —— 那是**落盘缓存**，候选不被选中（D-10/D-11/D-12/D-14 五次失败全栽在这上面）。要绕的是 hop1，只能走网络层拦截。
- ❌ **不要用"三处同时装 CA"的机器做实验** —— 分不出是哪一处生效的。
- ❌ **不要手工 `cp` 一个 DER 到用户库** —— 这是**一个真实的污染源**：那次"只装用户 CA 失败"的实验里，用户库放的是 **DER**（`report\06:608`），而 conscrypt 的 `TrustedCertificateStore` 读的是 **PEM**（`report\20:116-131`）。**必须走「设置 → 安全 → 加密与凭据 → 安装证书 → CA 证书」这条正规路径**，让系统自己写文件（格式/权限/label 都由系统决定）。
- ❌ **不要把那次失败当成 P4 的反证** —— 同一个时间窗（01:27–01:31）里，服务端用的根是 `ca3`（伪装 RapidSSL），**和用户库里的 `BA Test Root CA` 不是同一张**；失败被"链根不匹配"完整解释（`report\06:653-659`）。**这是本项目第一次、也是唯一一次"只装用户库"，而它是被污染的。**
- ❌ **不要只看 `access_log` 有没有记录就判 TLS 通过** —— 红线（`report\21-决策日志-CA路线攻坚.md:§八.1`）。
- ✅ **必须验证链完整性** —— UnityTLS 不补中间证书，根直接签叶子、握手时 leaf+root 一起发。
- ✅ **顺手把 `res/Dk.xml` 那条也判掉** —— 如果用户证书**直接生效**，就说明 Unity 没走被 NSC 限制的那条路径 ⇒ **P2 永久作废**，不用再花一次重打包去验它。

**这个实验能不能在无 root 手机上完成？**
**能，而且必须。** 装用户证书、开 VpnService、改 DNS 三件事全部不需要 root。反过来说：**如果这个实验必须在 root 机器上做，那它就已经失去意义了** —— 因为它要回答的就是"去掉 root 还成不成立"。

#### 顺便：一个可能让 CA 都省掉的实验（E-HOSTNAME，10 分钟）

如果客户端**不校验主机名**，那我们可以直接用 `example.com` 的**公网真证书**（Let's Encrypt/宝塔，链天然被信任）来答 `state-api` 的握手 ⇒ **连装 CA 都不需要**，免 root 链条只剩"引流"一个动作。

做法：nginx 保持 `ca2` 之外，另起一个 vhost，对 `SNI=state-api.bluearchive-cn.com` 出示 `example.com` 的真证书链 → 看客户端是 `hostname mismatch` 还是握手成功。
判断：libcurl 默认 `CURLOPT_SSL_VERIFYHOST=2` 会查主机名 ⇒ **大概率失败**，但成本 10 分钟、收益是整个 CA 层归零，**值得排在 E-USERCA 前面做**（它不需要装任何东西、不需要干净机器，可以在任何机器上做）。

---

## 4. 组合方案

单独一条能全通的**没有**。必须"引流 × 取信"两维各选一个。**而在两维之外还有一个乘法器：P9（hop2 明文）能把"取信"的面积从全部域名压到 hop1 一个域名。**

| 组合 | 引流 | 取信 | hop2 明文 | 改包 | root | 用户操作 | 判定 |
|---|---|---|---|---|---|---|---|
| **C1 ★最优** | P3 VpnService（mihomo TUN） | **P4 用户证书**（只服务 hop1） | ✅ P9 | ❌ | ❌ | 装 CA + 点一次"允许 VPN" | **全部免 root、免改包；证书面只剩 1~2 个域名** |
| **C1'** | 同上 | P4（要覆盖全部域名，含 BestHTTP） | ❌ | ❌ | ❌ | 同上 | 可行但**多赌一个未知**：BestHTTP 那套独立 TLS 栈认不认用户证书（F5） |
| **C2** | P6 私有 DNS(DoT) | P4 | ✅ | ❌ | ❌ | 装 CA + 填一个 DoT 主机名 | 比 C1 少一个 App，但手机上有 VPN tun 时会打架（D-16） |
| **C3** | P7 路由器 | P4 | ✅ | ❌ | ❌ | 装 CA + 改路由器 | 只适合有路由器控制权的用户；可批量 |
| **C4** | P11 adb 全局代理 | P4 | ✅ | ❌ | ❌（要电脑） | 装 CA + 插线跑一条命令 | 可行但体验最差；且 Unity 认不认系统代理【未知】 |
| **C5** | P3/P6 任意 | **P12 改包 patch `ValidateCertificate`** | 可选 | ✅ | ❌ | 装我们的 APK + 引流 | **可行（无已知硬阻碍）**；代价是 2.1 GB 分发 + 定位方法地址 |
| **C6** | 不需要（公网直连） | — | — | ✅ 仅 P15 改 `sdk_url` | ❌ | 装我们的 APK | 只解决 SDK 段，**不构成完整方案** |
| **C9** | 不需要（若 hop2 全明文） | — | ✅ | ❌ | ❌ | **adb push 一个文件** | **若 P17 成立**：免 root 免改包，但只能改数据不能改代码 |
| **C7（现状）** | iptables DNAT | 系统 CA 注入（3 处） | ❌ | ❌ | **✅ 需要** | — | 在跑，但是**最贵**的一条 |
| **C8** | 服务端 `Servers[]` | — | — | ❌ | ❌ | — | **只在 hop2 生效**（P16），省不掉 hop1 |

**三条"看起来能省事"的捷径，明确否掉：**
- **"只做 VPN 不改证书"** —— 客户端看到的是我们的证书，**hop1 必定失败**（F2 已证它会校验链）。必须配 P4 或 P12。
- **"只装 CA 不改引流"** —— 装了也没用，包根本不来我们这。
- **"改 `networkSecurityConfig` 让它信任用户 CA"** —— P2，控制错层（F3），对本目标零效果。

---

## 5. 最小可行路径

### 路径 A（首选：零改包、零 root）

> **★ 关键简化（本报告最重要的工程结论）**：**只有 hop1 需要证书，而且 hop1 可以从头到尾不涉及我们的 CA。**
> 只要 `/api/state` 的 `Servers[]` 指向**我们自己的、有公网真证书的域名**（`https://example.com/api/`，TLC 商业 DV，2026-12-12 到期），那么 hop2 起的每一跳都是"连我们自己的域名、看我们自己的真证书"——**不需要 client 信任我们自签的根，也不需要拦截、不需要证书覆盖 `gsqc-api`**。
> ⇒ **DNAT/引流的面积可以从"一串域名"缩到 `state-api.bluearchive-cn.com` 一个**（加 `gsqc-api` 的 state 兜底那一拦）。这是把免 root 从"很难"变成"可行"的那一步。

```
① 官方 APK 原样安装（用户从官方渠道装，我们一个字节都不碰）
② 用户把我们的根证书装到「用户证书」（3 次点击；Android 11+ 需锁屏密码，Android 14+ 有常驻警告）
③ 引流：只把 state-api / gsqc-api 两个域名的 443 转到我们服务器
   手段任选（都不需要 root）：VpnService / Wi-Fi 代理 / 私有 DNS(DoT)
④ 我们 nginx：
   · /api/state 回 {"Servers":["https://example.com/api/"],"State":0,"Msg":""}
     ⇒ hop2 起走我们自己的域名 + 公网真证书，**零证书风险、零拦截**
   · hop1 的 TLS：leaf + root 一起下发（UnityTLS 不补中间证书），SAN 覆盖 state-api / gsqc-api
```
**我们改的客户端文件：0 个。** **每用户操作：2 个。**
**前提**：E-USERCA 赢（§3.3，只针对 hop1 这一个请求）。
**注意**：这条路**不需要 P9**——hop2 用真证书域名就够了。P9（`http://`）是一个**可选加强**：如果将来需要让 hop2 也落到一个没证书的端口，它才派上用场。

### 路径 B（A 输了之后的退路：改包，仍免 root）

```
① patch libil2cpp 的 CustomCertificateHandler.ValidateCertificate → 恒返回 true
   （载体沿用已证不触发 ACE 的「代码洞 + DT_INIT」）
② repack → zipalign → apksigner 重签
③ 分发 2.13 GB APK（用户正常安装，不需要 root）
④ 引流仍需 P3/P6（或顺势把 hop2 也降成明文 http）
```
**唯一真难点：定位方法地址**（metadata 混淆，标准 Il2CppDumper 走不通，需运行期 dump 明文 metadata）。
**不是阻碍的两件事**：ACE（§3.1 已证重签包能跑到"取得昵称"界面）、TapSDK 签名错误（`report\29:81` 明确列为"既知现象，不影响流程"）。
**真实成本在安装侧**（只影响开发机，不影响新用户）：2.13 GB 包、apksigner 需 ≥2.1 GB 空闲、签名变必须卸载重装、UID 变 ⇒ 11 GB 资源 `chown -R <UID>:1078`、丢 `/data/data` 登录态。

### 路径 C（若 P17 成立，最省事的一条）

```
先花 10 分钟验证（只读，不改任何东西）：
  adb shell 'ls -l /storage/emulated/0/Android/data/com.RoamingStar.BlueArchive/files/il2cpp/Metadata/'
  adb shell 'sha256sum .../files/il2cpp/Metadata/global-metadata.dat'
  adb shell 'sha256sum /data/app/*/com.RoamingStar.BlueArchive*/base.apk'   # 与 APK 内那份比
  游戏运行时：adb shell 'ls -l /proc/<pid>/maps | grep -i metadata'         # 有没有那条外部路径
  adb shell 'find .../files -iname "*ifix*" -o -iname "*.bytes" -o -iname "*.dll"'  # iFix 补丁通道
```
- **若客户端确实从外部那份读** ⇒ 换 metadata = **一条 `adb push` / MTP 拷贝**，免 root、免改包、不碰 ACE 的 APK 完整性面。
- **信号偏正面**：该目录下 metadata 旁边还有 `il2cpp/unity.ver = 611ecbd3-…`（`report\21:1116`）——**版本标记文件是热更框架的典型布局**，说明这份 metadata 不是随手备份，而是被某个加载/校验流程管理的。
- **但有一条不利先例**：项目盘清过 `persistentDataPath` 下 13 个本地配置文件、86 个 key，结论是"**唯一被证明改了立刻生效的客户端配置是 APK 内的 `sdk_url`**"（`report\54:34`）⇒ 外部配置普遍不被采纳。**所以这条必须先验，不能先信。**
- **能力边界**：metadata 里放的是**数据**，不是代码 ⇒ 能做"改 URL"，**做不了"跳过证书校验"**。唯一可能的例外是 **iFix 热更通道**：metadata 里有 `<>iFixBaseProxy_ValidateCertificate`（`report\11:80`、`report\15:255`），说明 iFix 给这个方法生成过代理；如果 iFix 的补丁文件是从可写目录加载的，那才是真正"免 root 改代码"的入口 —— **值得一起验**。

### 路径 D（诚实兜底）

若 E-USERCA 输 **且** P12/P17 都不可行 ⇒ 免 root 没有完整路径 ⇒ **必须 root**。此时可行的降级分发只有两种：
1. **只发给能接受 root 的用户**（KSU/Magisk 机型）；
2. 退回 **PC/模拟器**形态（不涉及手机 root）。

### 四条路径的对比

| | 改包 | root | 用户操作 | 分发体量 | 卡在哪 |
|---|---|---|---|---|---|
| **A** | ❌ | ❌ | 装 CA + 开 VPN | 0（官方包） | 押在 E-USERCA + hop2 明文两个实验上 |
| **B** | ✅ | ❌ | 装 APK + 引流 | 2.13 GB | 定位 `ValidateCertificate` 地址 |
| **C** | ❌ | ❌ | adb push 一个文件 | 0 | 前提未验证；且只能改数据 |
| **D** | ❌ | ✅ | 一大堆 | — | 就是现在这样 |

---

## 6. 诚实结论

**"必须 root" 这个结论不成立。** 但也不是"改个 DNS 就行"——**免 root 需要用户配合两个动作，而且第一动作（装 CA）还压着一个未验证的假设。**

证据链（按强度排）：

1. **【确证】客户端会校验证书链**，错误码 `Curl error 60 / UnityTls error 7`，**不是 pinning**（`report\06:643`、`report\INDEX.md:503` A-10）。
2. **【确证】这条链路是 libcurl + UnityTLS**，Android 的 `networkSecurityConfig` / `TrustManager` 全部够不到（F1 + F3）。**⇒ P2 这类"改 Android 信任配置"的思路一律无效。**
3. **【确证】重打包 + 重签从来没被 ACE 杀过**（E28→E44 十余版；E42"能进主程序"；设备现役包内嵌的 `libil2cpp.so` 就不是原厂件，而它跑到了"取昵称"界面）。ACE 是"定点校验"：钉 `libunity` / `libtprt` / `libairisgcore` / 加载布局 / **包名**，**不钉 `libil2cpp`**，且 `assets/__tpinfo.*` 删掉就整段跳过。
   **⇒ "改包会被反作弊杀"是流传在文档里的风险预判，不是观测。** 这条长期疑虑可以正式划掉。
4. **【确证】`Servers[]` 会被消费，但只决定 hop2 之后**（`GetApiServerInfo` 逐条探活）；hop1 的 URL/scheme 改不动。**⇒ 免 root 必须做网络层拦截，但拦截面只要覆盖 hop1 的 1~2 个域名。**
5. **【一手外部证据 + 待真机】Unity 2021.3.48f1 起把用户安装的 CA 并入 `trusted_ca`**（UUM-73839；本报告已 fetch 核对发布说明原文），本包 2021.3.56f2 ⇒ 用户证书**极可能**直接生效。
   - **这是唯一一票否决路径 A 的变量，而项目从来没做过隔离实验**（一直是三处同时装；唯一那次"只装用户库"用户库是 DER + 服务端根不匹配，双重污染）。
6. **【确证 + 一步推理】需要拦截的面比想象的小得多。** 因为 `Servers[]` 归我们控制（第 4 条），把它指向**我们自己有公网真证书的域名**（`example.com`，TLC DV 有效到 2026-12-12），那么 hop2 起的每一跳都是"连我们自己的域名、看我们自己的真证书"——**不需要拦截、不需要任何自定义 CA**。
   ⇒ **DNAT / 引流的面积可以从"一串域名 + CDN + SNI 分流"缩到 `state-api` 一个域名（加 `gsqc-api` 的 state 兜底那一拦）。**
   ⇒ 这一步把"免 root"从"要在手机上接管一堆域名"变成"只要接管一次 TLS 握手"。**这是本报告最有实操价值的一条。**

**所以最诚实的说法是：**

> **免 root 有两条互相独立的可行路径，不是一条。**
> - **路径 A（零改包）**：成功概率我估 **60~70%**（一手 release note + 版本号符合 + 错误串与 issue 逐字对应；扣掉"targetSdk/NSC 是否挡住"和"BestHTTP 那套栈"两个未知）。成本：每用户装一次 CA + 一次引流。
> - **路径 B（改包）**：技术上**确定可行**（ACE 不拦、TapSDK 不阻断都已确证），成本是 2.13 GB 分发 + 定位一个方法地址。
> **两条都不需要 root。所以"必须 root"是错的。**
> 但"现在这套必须 root"是对的 —— 因为现在这套同时用了 iptables（可换 VpnService/代理/DNS）和系统 CA 注入（可换用户证书），两个都能换掉，只是**还没人试过换**。
>
> **顺手纠正一条写进总纲的"边界"**：`report\90-项目总纲-可交接版.md:264` 的"免 root 分发不可行"是把"重定向必须 DNAT"当成了前提。**这个前提是错的**：DNAT 只是他们当时选的实现，而证书那条也已经有了用户证书这条替代路。这条边界应改成"**免 root 分发需用户配合两个动作，且压着一个未验证的假设**"。

---

## 7. 汇总（≤60 行）

```
一、总判定
  免 root 可行，而且有两条独立路径：
    路径 A 零改包（用户装 CA + 开 VPN）—— 概率 60~70%，押在两个未验证的假设上
    路径 B 改包（patch ValidateCertificate，正常安装）—— 技术确定可行
  "必须 root" 不成立。现在这套之所以要 root，只是因为它同时用了
  iptables（可换 VpnService/DNS）+ 系统 CA 注入（可换用户证书），两个都能换。

二、逐条判定（20 条：可行 2 / 机制成立待实测 4 / 条件可行 4 / 不可行 10）
  可行（2）        P15 改包 sdk_url → http 明文          —— 只解决 SDK 段
                   P12 改包 patch ValidateCertificate      —— ACE 不拦、TapSDK 不阻断（已确证）
  机制成立，待实测（4）P4  ★ 用户证书能否被 UnityTLS 采用   —— 唯一一票否决路径 A
                   P9   hop2+ 明文（只差一次观测）         —— 把证书面压到 hop1 一个域名
                   P17  adb 覆盖外部 metadata             —— 10 分钟只读可验，最便宜的意外
                   P11  adb 全局代理 Unity 认不认
  条件可行（4）     P3 / P6 / P7  —— 只解决引流，必须配 P4
                   P16 服务端 Servers[] 改址 —— 只在 hop2 生效，省不掉 hop1
  不可行（10）     P1 域名非静态字面量 · P1b 会被服务端覆盖（收益 0）· P5 hosts 需 root（真因是 netd 在别的 mount ns）
                   P2 NSC 存在但只管 Java 层（okhttp/WebView），游戏 TLS 走 UnityTLS/BestHTTP，够不到
                   P8 "要官方证书"是伪命题（只需任意一张根被信任的证书）· P10 okhttp 只跑 SDK，RPC 一条不走它
                   P13 LSPatch 同样是改包、还多一层模块校验 · P14 shell 无 CAP_NET_ADMIN · C8=P16 · C6 不构成完整方案
  ⇒ 回答"几条可行"：**确定的 2 条 + 待测的 4 条 + 条件可行的 4 条；10 条不可行。**
  ⇒ 单独一条能全通的**没有**；但"引流 + 取信"两维各取一条即可，且两维都不需要 root。

三、五条必须钉死的事实（§1）
  F1【确证】TLS = libcurl + UnityTLS，不是 Conscrypt
  F2【确证】客户端确实校验证书链（46 条 alert 49 全在 CA 生效之前，之后归零）
  F3【确证】NSC 属性确实存在（@xml/http，base-config 明文全放行），但只管 Java 层栈
  F4【确证】Servers[] 会被消费，只决定 hop2 之后；hop1 改不动
  F5【确证】三套 HTTP 栈：hop1=UnityWebRequest/UnityTLS，hop2+=BestHTTP/2，SDK=okhttp

四、最小可行路径 A（零改包、零 root）
  ★ 关键简化：把 Servers[] 指向我们自己【有公网真证书】的域名（example.com），
    hop2 起就是"连我们自己域名、看我们自己的真证书"⇒ 不需要拦截、不需要自定义 CA。
    ⇒ 引流面从"一串域名 + CDN + SNI 分流"缩到 state-api 一个域名（含 gsqc 兜底那一拦）。
  ① 官方 APK 原样装
  ② 用户装我们的根证书到「用户证书」（3 次点击；必须走"设置→安装证书"，别手工 cp DER）
  ③ 引流：只把 state-api / gsqc-api 的 443 转给我们（VpnService / 代理 / 私有 DNS 任选）
  ④ /api/state 回 {"Servers":["https://example.com/api/"],"State":0,"Msg":""}
  ⑤ hop1 的 TLS：leaf + root 一起下发（UnityTLS 不补中间证书）
  我们改的客户端文件：0 个。每用户操作：2 个。**这条路不需要 P9。**

五、必须先做的三个实验（都免 root）
  E-HOSTNAME（10 min，任何机器）：对 SNI=state-api 出示 example.com 的真证书
      → 若过，客户端不校验主机名 ⇒ 连 CA 都不用装（CA 层归零）
  E-USERCA（30 min，必须【无 root】的干净手机）：器材已备好 `p4_proxy.py --mode proxy --pass-others`
      → 步骤 0 先 curl --cacert 正控 200，否则重演"链根不对"的假阴性
      → 判据在 p4_proxy 的 `P4-TLS-OK` / `P4-TLS-REJECT alert=…` 两行
      → **非对称**：拿到 OK 即自证、全程不碰 root；拿到 REJECT 才需补一个需 root 的正控
      → 判据要看两套栈：有 UnityPlayer 的 /api/state ≠ hop2 也通（BestHTTP 也拒过，见 F5 注）
  E-PLAIN（选做，10 min）：Servers 只放一条 http://，看 80 端口有没有 TCP 连接
      → 有 = hop2 明文也成立，可用于将来免证书的新端点

六、红线（历史踩过，别重踩）
  1) 不要靠 files/Hosts 引流 —— 那是写穿缓存，候选不被选中（D-10~D-14 五次失败）
  2) 不要在三处都装了 CA 的机器上做实验 —— 分不出哪处生效
  3) access_log 有记录 ≠ TLS 通过
  4) UnityTLS 不补中间证书 —— 根直签叶子，握手同时下发 leaf+root
  5) 别信"grep 不到就不存在" —— AXML 是 UTF-16，ASCII grep 必 0 命中（§1.1 两次翻车）
```
