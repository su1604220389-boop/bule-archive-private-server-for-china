# 免 root 下让国服客户端信任自签证书 —— 静态分析结论与四条路径评估

> 目标：`com.RoamingStar.BlueArchive` 3.0.2 (vc73)，Unity 2021.3 + IL2CPP，`targetSdk=33`。
> 范围：**纯静态**。未连服务器、未操作手机、未安装 APK、未修改 `report\_tmp\cn_base.apk`、未修改 `work\ba\noroot\` 下任何现有文件。
> 方法：`zipfile` 随机访问（全程零解包，只在内存/流里读），自写 AXML + `resources.arsc` 解析器，正则化 needle 扫描（8 MiB 分块 + 512 B overlap）。
> 解释器：DSH 自带 `C:\Users\su\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe`（3.12.14）。
> 标注：**确证** = 有字节/偏移/计数；**推断** = 由确证事实推出但未上机；**未知** = 本轮无法判定。

---

## 结论速览

| 问题 | 结论 | 置信度 |
|---|---|---|
| `/api/state` 的证书校验在哪层？ | **`libunity.so` 内的 mbedTLS**（UnityTLS）执行 `x509_verify_cert`；**`libil2cpp.so` 里一条 TLS 校验代码都没有** | **确证**（见 §1.1/§1.2） |
| 它从哪拿 CA？ | **不是直接读 `AndroidCAStore`**。`libunity.so` 内是一整套 **JNI 绑定到 Java `TrustManagerFactory` + `X509TrustManager.getAcceptedIssuers()`** 的反射调用表 ⇒ 信任源 = **Java/Conscrypt 的信任管理者** ⇒ **由 app 自己的 `networkSecurityConfig` 裁决** | **确证**（JNI 绑定表存在）+ **推断·高**（调用顺序）；见 §1.3 |
| 有 C# 层钩子吗？ | **有**：metadata 里有 `CustomCertificateHandler-ValidateCertificate0`（游戏自写覆写）与 `SetCertificateHandler` / `ValidateCertificateNative`。但**实测现象证明它不是 `/api/state` 的放行口** | **确证**（符号）+ **推断·高**（未被挂到该请求上）；见 §1.4 |
| BestHTTP 卡不卡证书？ | **不卡**。它自带 BouncyCastle（`BestHTTP.SecureProtocol` 92×）+ `ICertificateVerifyer`/`NotifyServerCertificate`，校验是**托管**的，不经 Java 信任管理者 ⇒ 不受 NSC 约束 | **确证**（符号）+ **推断·高**（与 `_dd3` §2.5 的实测握手成功一致） |
| `AllowUnsafeConnection` 存在吗？ | **不存在**（0 命中）。该名字不是 BestHTTP 2.4.0 的 API，别照它找 | **确证** |
| 免 root 到底行不行？ | **行，但入口不是"装系统 CA"，而是"改 app 自己的 NSC"或"把 URL 改成明文 http"** | **确证**（机制）+ 需一次真机验证 |
| 最该先做哪条？ | **C（`http://` 等长改域名，只动 80 B 密文）**，其次 **B（NSC 加 `<trust-anchors>`）** | 见 §4 |

**一句话**：任务里"客户端读 `AndroidCAStore`（含用户库）"这个前提**被本轮静态证据推翻**了。真实机制是 Unity 走
Java `TrustManagerFactory`，而 `TrustManagerFactory` 读的是 **app 自己的 `networkSecurityConfig`**。
这个差别是决定性的：**NSC 在 APK 里，改它不需要 root**。所以免 root 不是"装不进系统库所以死"，而是"改一个 264 B 的 XML 就行"。

---

## 0. 本轮做了什么（可复核）

| # | 动作 | 结果 |
|---|---|---|
| 1 | APK 条目清单（41,312 条 / 解压后 2,461,895,783 B） | 24 个 `lib/arm64-v8a/*.so`，全部 deflate |
| 2 | 证书类条目全库检索（`.pem/.crt/.cer/.der/.p12/.bks/cacert/ca-bundle/certifi/trust`） | **只有 3 个**：`assets/grs_sp.bks`、`assets/hmsincas.bks`、`assets/hmsrootcas.bks`（华为 HMS，非 Unity 用） |
| 3 | `res/*.xml` 全扫（545 个）找 `network-security-config` | **唯一命中 `res/Dk.xml`（264 B，method=0 stored）** |
| 4 | `libil2cpp.so`（270,927,056 B）扫 44 条 TLS needle | **6 命中，全是 IL2CPP 方法名字符串**（`UnityWebRequest` 23×、`DownloadHandler` 21×、`CertificateHandler` 3×、`BestHTTP` 1×、`Mono.Security` 1×、`certifi`⊂`certificate` 1×）；**curl/SSL/mbedTLS 符号 0 命中** |
| 5 | `libunity.so`（20,950,552 B）扫 47 条 needle | **决定性 8 命中**：`TrustManagerFactory` 5×、`getAcceptedIssuers`、`X509TrustManager`、`checkServerTrusted`、`KeyStore`、`x509_verify_cert`、`CertificateHandlerProxy`、`ValidateCertificateNative`；**`AndroidCAStore` 0 命中** |
| 6 | `global-metadata.dat`（38,426,024 B）扫 28 + 24 条 | `CertificateHandler` 20×、`CustomCertificateHandler` 1×、`ValidateCertificate` 2×、`SetCertificateHandler` 1×、`TlsClientFactory` 3×、`BouncyCastle` 92×、`ICertificateVerifyer` 1×、`NotifyServerCertificate` 1×、`SslStream` 7×、`SslProtocols` 6×、`RemoteCertificateValidationCallback` 5×、`ServicePointManager` 5×、`unitytls_x509verify` 6× |
| 7 | `libairisgcore.so`(2.6 MB) / `libtprt.so`(1.7 MB) 扫 TLS needle | **全部 0 命中** ⇒ 与 TLS 无关 |
| 8 | `AndroidManifest.xml`（50,552 B AXML，338 串）解析 | `<application>` 上确有 `networkSecurityConfig` / `usesCleartextTraffic` / `extractNativeLibs` 三属性 |
| 9 | `resources.arsc` 全局字符串池（6,726 串，UTF-8） | `res/Dk.xml` = 串索引 **101**，被 **1 条** `Res_value{TYPE_STRING}` 引用 ⇒ 它就是 manifest 所指的 NSC |
| 10 | **实建并验证两份补丁产物**（写入 `%TEMP%`，未进 APK） | 见 §3 B/C 与 §8 |

---

## 1. Q1：`/api/state`（native libcurl）的证书校验具体在哪一层？

### 1.1 先说最关键的一条：**不在 `libil2cpp.so`**

对 `libil2cpp.so`（270,927,056 B）扫 44 条 needle，**全部 TLS/curl 校验符号 0 命中**：

```
0x  CURLOPT_SSL_VERIFYPEER   CURLOPT_SSL_VERIFYHOST   curl_easy_setopt
    SSL_CTX_set_verify       SSL_get_verify_result    X509_verify_cert
    SSL_VERIFY_NONE          curl_easy_perform        curl_global_init
    CURLOPT_CAINFO/CAPATH    TrustManagerFactory      AndroidCAStore
```

命中的 6 条**全部是 IL2CPP 生成的 C# 方法名字符串**，不是 TLS 代码：

| 命中 | 次数 | 首偏移 | 性质（已看上下文） |
|---|---|---|---|
| `UnityWebRequest` | 23 | `0x0264f51e` | `UnityEngine.Networking.*` 方法名 |
| `DownloadHandler` | 21 | `0x0264576c` | 同上 |
| `CertificateHandler` | 3 | `0x02667f8b` | 上下文原文：`UnityEngine.Networking.CertificateHandler::Create(UnityEngine.Networking.CertificateHandler)` |
| `BestHTTP` | 1 | `0x0265e310` | 命名空间串 |
| `Mono.Security` | 1 | `0x026799e7` | BCL 程序集名 |
| `certifi` | 1 | `0x037c570e` | ⚠ 是 `certificate` 的子串，**假命中** |

> **为什么 `libil2cpp.so` 里没有 TLS**：Unity 的 SslStream/`UnityWebRequest` 只是**绑定层**，真正的 HTTP/TLS 栈
> （libcurl + UnityTLS/mbedTLS）**静态链接在 `libunity.so`** 里。IL2CPP 生成的是 C# 的 C++ 翻版，不含引擎的传输层。
> 另：`libil2cpp.so` 的 `http://` 20 次命中**全是噪声**——上下文是 IL2CPP 内嵌的 Brotli 压缩字典
> （`http:// <html> <div class=...>` 那种 HTML/CSS 片段），**不是** app 的字符串字面量。

**顺带纠正一个 needle**：任务里的 `CRYPTO_set_lookup_byaddrinfo` **不是任何真实 API**（libcurl/OpenSSL/BoringSSL 都没有这个符号；
真实的名字是 `SSL_CTX_set_cert_verify_callback` / `X509_VERIFY_PARAM_set1_host` 一类）。它是 0 命中，但这**不构成任何证据**，别在上面花时间。

### 1.2 真正的校验层：`libunity.so` 里的 mbedTLS，`x509_verify_cert`

`libunity.so` @ `0x010badeb` 起是一段 **mbedtls_ssl_tls.c / x509_crt.c 的调试与错误字符串**：

```
0x010bae11  mbedtls_ssl_parse_alpn_ext
0x010bae2c  server side, adding alpn extension
0x010bae61  Use context-specific verification callback
0x010bae8c  Use configuration-specific verification callback
0x010baebd  get_hostname_for_verification
0x010baedb  x509_verify_cert                    ← ★ 校验入口
0x010baeec  bad certificate (EC key curve)
0x010baf0b  bad certificate (usage extensions)
0x010baf2e  got no CA chain
0x010baf3e  ! Certificate verification flags %08x
0x010baf64  Certificate verification flags clear
0x010baf96  server_name   ... max_fragment_length, status_request, use_srtp, signature_algorithms
```

⇒ **确证**：`/api/state` 的链校验是 **mbedTLS 的 `x509_verify_cert`** 在 native 里做的（UnityTLS = mbedTLS）。
这与历史报错形状完全自洽：`Curl error 60 ... not correctly signed by a trusted CA` + `UnityTls error code: 7`
（`_dd3-P4-userCA.md:15,151`）—— 这是 **native 校验失败**的报错，不是 Java 异常，也不是 pinning 的报错形状。

> ⚠ 别用"有没有 `CURLOPT_*` / `curl_easy_setopt` 字符串"来判断 libcurl 在不在。libcurl 的 option 名字符串只在
> `curl` 命令行工具/调试构建里出现；Unity 静态链接并 strip 过的 libcurl 不会有。**要判据就用 mbedTLS 的报错串**（上面那组），它一定在。

### 1.3 ★ CA 到底从哪来：JNI 绑定表给出答案（本轮最重要证据）

`libunity.so` `0x0111b74a` 起有一整块**连续、完整的 Java 反射字符串表**，原文逐条如下（已实测导出）：

```
0x0111b74a  javax/net/ssl/TrustManagerFactory
0x0111b76c  getAlgorithm
0x0111b779  getDefaultAlgorithm
0x0111b78d  (Ljava/lang/String;)Ljavax/net/ssl/TrustManagerFactory;          ← getInstance(String)
0x0111b7c5  (Ljava/lang/String;Ljava/lang/String;)Ljavax/net/ssl/TrustManagerFactory;
0x0111b80f  (Ljava/lang/String;Ljava/security/Provider;)Ljavax/net/ssl/TrustManagerFactory;
0x0111b85f  ()Ljava/security/Provider;
0x0111b87a  getTrustManagers
0x0111b88b  ()[Ljavax/net/ssl/TrustManager;
0x0111b8ab  (Ljava/security/KeyStore;)V                                      ← init(KeyStore)
0x0111b8c7  (Ljavax/net/ssl/ManagerFactoryParameters;)V
0x0111b8f3  (Ljavax/net/ssl/TrustManagerFactorySpi;Ljava/security/Provider;Ljava/lang/String;)V
0x0111b947  javax/net/ssl/X509TrustManager
0x0111b966  checkClientTrusted
0x0111b979  ([Ljava/security/cert/X509Certificate;Ljava/lang/String;)V
0x0111b9b4  checkServerTrusted                                          ← ★
0x0111b9c7  getAcceptedIssuers                                          ← ★
0x0111b9da  ()[Ljava/security/cert/X509Certificate;
0x0111bb17  bitter/jnibridge/JNIBridge   ...  newInterfaceProxy / disableInterfaceProxy
```

**判读（三步，全部有据）**：

| # | 事实 | 含义 |
|---|---|---|
| ① | 有 `TrustManagerFactory.getDefaultAlgorithm` + `getInstance(...)` + `getTrustManagers()` + `init(KeyStore)` | Unity 是**通过 Java 的 `TrustManagerFactory` 建信任集** |
| ② | 有 `X509TrustManager.getAcceptedIssuers()` 与 `checkServerTrusted` | 建"可信根列表"用的是 `getAcceptedIssuers()`，链校验另有 `checkServerTrusted` 可用 |
| ③ | **`AndroidCAStore` = 0 命中**；`cacert` / `ca-certificates.crt` / `trusted_ca` / `TrustedCertificateStore` / `getCertificateChain` **全部 0 命中** | **排除了"直接枚举 `AndroidCAStore`"（`_dd3` 的机制 (b)）**，也排除了"读 app 内 PEM bundle"（机制 (c)） |

⇒ **只剩机制 (a)**，而且**无论 Unity 具体走 `init(null)` 还是 `checkServerTrusted`，两者都由 app 自己的
`NetworkSecurityConfig` 裁决**（Conscrypt 的 `RootTrustManager` / `ApplicationConfig`）。
`targetSdk=33` ⇒ 默认只给系统 CA ⇒ 用户库被过滤掉 ⇒ `getAcceptedIssuers()` 里没有我们的 CA ⇒
mbedTLS 拿到的"可信根"不含我们 ⇒ `x509_verify_cert` 失败 ⇒ `Curl error 60`。**全链路闭合。**

**这就是免 root 的突破口**：裁决者是 **APK 内的 `res/Dk.xml`**，不是系统库。改它不需要 root。

> 与任务前提 ① 的冲突（**这是本轮唯一需要推翻的前提**）：
> 前提写"两者读的是 `AndroidCAStore`（系统库 + `/data/misc/user/0/cacerts-added`）"。
> 静态证据表明**用户库那一半根本进不来**：不是"读不到"，而是"它读的容器根本不包含用户库"。
> 前提中"`networkSecurityConfig` 只作用于 Java/Conscrypt 栈"这句**是对的**，但结论反了——正因为
> Unity 走的就是 Java/Conscrypt 栈，NSC 才**恰好**是它的开关。（`_dd3-P4-userCA.md:118-120` 早就警告过
> 「§1 不能直接推出 P4 死」，本轮把这个警告落成了证据。）

### 1.4 `CertificateHandler` 钩子点：存在，但不是 `/api/state` 的闸门

**metadata 里确实有游戏自写的 handler**（`0x0041b7ef`，上下文 ±160 B 原文）：

```
0x0041b760  InputWrapper-GetTouchCount0
0x0041b77c  InputWrapper-GetKey0
0x0041b791  InputWrapper-GetAnyKeyDown0
0x0041b7ad  InputWrapper-GetAnyKeyboardDown0
0x0041b7ce  InputWrapper-IsAnyKeyDownExcept0
0x0041b7ef  CustomCertificateHandler-ValidateCertificate0     ← ★ 类型+方法名紧邻
0x0041b81d  LocalNotificationManager-Init0
0x0041b83c  LocalNotificationManager-RemoveAllScheduledNotifications0
```

即 `CustomCertificateHandler : CertificateHandler`，覆写了 `ValidateCertificate`。相关串还有：

| 串 | 次数 | 首偏移 | 归属 |
|---|---|---|---|
| `CertificateHandler` | 20 | `0x00219eba` | UnityEngine 类型名 |
| `SetCertificateHandler`（Unity API） | 1 | `0x007a5fbb` | `UnityWebRequest.SetCertificateHandler` |
| `certificateHandler`（字段名） | 3 | `0x007a5fd5` | |
| `ValidateCertificateNative` | 1 | `0x007a63ef` | native→managed 回调 |
| `CertificateHandlerProxy` | 1（libunity） | `0x01066565` | `::Scripting::UnityEngine::Networking::CertificateHandlerProxy` |

**为什么说它不是闸门**：如果这个 handler 被挂到 `/api/state` 且 `ValidateCertificate` 返回 `true`，那**根本不会有**
`Curl error 60` + `UnityTls error code 7`（native 校验直接被跳过）；如果它返回 `false`，那打正式服也会全挂。
两种都不成立 ⇒ **它没有作用在 `/api/state` 上**（更可能挂在某个 CDN/资源下载分支上）。这与 `_dd3-P4-userCA.md:150`（③）的判断一致，
但本轮补上了**它确实存在于国服 metadata** 这条实证。

> C# 钩子在**理论上**是最干净的（一行 `return true`），但落地形式是**改 258 MB 的 stripped `libil2cpp.so` 里某段
> IL2CPP 生成的 C++**——没有符号、没有字符串交叉引用，等价于盲改。**不可工程化**（见 §3 A2）。

### 1.5 Q1 小结

```
/api/state  →  libil2cpp(托管绑定)  →  libunity.so(UnityWebRequest + libcurl + mbedTLS)
                                            │
                                            ├─ 链校验：mbedtls x509_verify_cert   （native，报 Curl 60/UnityTls 7）
                                            └─ 可信根：JNI → TrustManagerFactory.getAcceptedIssuers()
                                                            → Conscrypt RootTrustManager
                                                            → ApplicationConfig = app 的 res/Dk.xml
                                                            → targetSdk 33 ⇒ 只有系统 CA
```

**校验层 = libunity 的 mbedTLS；信任源 = app 的 NSC。libil2cpp 里没有可改的东西。**

---

## 2. Q2：BestHTTP 的校验在哪？

### 2.1 证据（全部来自 `global-metadata.dat`，方法/类型名明文）

| 串 | 次数 | 首偏移 | 说明 |
|---|---|---|---|
| `BestHTTP` | 135 | `0x005eeecd` | 命名空间 |
| `Org.BouncyCastle` | 92 | `0x005f6e05` | **BestHTTP 自带 BC** |
| `BestHTTP.SecureProtocol` | 92 | `0x005f6ded` | BC 的重命名命名空间（`BestHTTP.SecureProtocol.Org.BouncyCastle...`） |
| `TlsClient` | 13 | `0x005ef22b` | BC 侧 TLS 客户端 |
| `CertificateVerifyer` | 8 | `0x005ef486` | ★ BC 的证书校验回调接口族 |
| `ICertificateVerifyer` | 1 | `0x00607f9f` | ★ 就是它（可插拔、返回 bool） |
| `NotifyServerCertificate` | 1 | `0x006080ff` | ★ `TlsAuthentication` 的回调 |
| `TlsAuthentication` | 3 | `0x006080df` | |
| `TlsClientFactory` | 3 | `0x005ef22b` | BestHTTP 的客户端工厂钩子 |
| `TlsClientProtocol` | 1 | `0x00609218` | |
| `LegacyTlsClient` | 1 | `0x0060812e` | |
| `HTTPManager` | 1 | `0x005ef24e` | |
| `OnSetup` | 1 | `0x0067ba2f` | BestHTTP 初始化钩子 |
| `SslStream` | 7 | `0x00699a41` | 另一条后端（Mono BCL） |
| `SslProtocols` / `TlsProtocols` / `SecurityProtocolType` | 6 / 1 / 1 | | 协议协商配置 |
| `RemoteCertificateValidationCallback` | 5 | `0x006b09d5` | SslStream 后端的放行口 |
| `ServerCertificate` / `CertificateVerify` / `X509Certificate` | 14 / 5 / 17 | | |
| `unitytls` / `unitytls_x509verify` / `unitytls_interface_struct` | 82 / 6 / 1 | | 引擎侧 UnityTLS 接口（不在 BestHTTP 路径上） |

### 2.2 `AllowUnsafeConnection` —— **不存在**

任务里提到搜 `AllowUnsafeConnection` / `SSLStream`：这两个串在 metadata、`libil2cpp.so`、`libunity.so` 里**全部 0 命中**。
BestHTTP 2.4.0 的放行口是 **`ICertificateVerifyer`（BC 后端）** 和 **`RemoteCertificateValidationCallback`（SslStream 后端）**，
不是 `AllowUnsafeConnection`。**别照一个不存在的 API 名字做搜索。**
（`SSLStream` 全大写也不存在，正确拼写是 `SslStream`，7 次命中。）

### 2.3 结论：BestHTTP **不需要**我们的 CA —— 这对本案是好消息

- BestHTTP 的 TLS 是**托管实现**（自带 BC），校验回调是 C# 层的 `ICertificateVerifyer`，
  **不经过 Java `TrustManagerFactory`** ⇒ **完全不受 `networkSecurityConfig` 约束**。
- 与历史实测吻合：`_dd3-P4-userCA.md:251-257` 记录 `gsqc-api`（走 BestHTTP）在**我们的自签证书还没被信任时**
  就握手成功，且 46 条 fatal alert 里**没有一条来自 `gsqc-api`**。
- ⇒ **全案需要 CA 的只剩 `/api/state` 一个请求**（外加它之后由我们决定的资源下载）。

### 2.4 `libairisgcore.so` / `libtprt.so`：与 TLS 无关

2.6 MB + 1.7 MB，两轮共 35 + 14 条 TLS needle（`SSL_CTX_set_verify` / `SSL_VERIFY_NONE` / `curl_easy_setopt` /
`AndroidCAStore` / `TrustManagerFactory` / `X509TrustManager` / `CertificateHandler` / `SslStream` / `cacert` /
`trusted_ca` / `SSL_get_verify_result` …）**全部 0 命中**。
`libtprt.so` 里连一般可打印串都极少（`work\ba\noroot\_tprt_strings.txt` 只有 19 KB），符合它作为 ACE 保护运行时的形态。
⇒ 这两条不是证书路径，**不要浪费预算**。

---

## 3. 四条路径的可行性

先给一条**贯穿全案的事实**：在免 root 下我们**没有 DNS 控制权**（`iptables` 需 `CAP_NET_ADMIN`，
`adb shell` 拿不到；`_dd3-P4-userCA.md:286,305-306`）。所以要让流量落到我们这边，**必须改 `GameMainConfig` 里的域名**
（等长/短值替换，`GAMEMAINCONFIG_CN.md:269-297` 已实测字节级可行），或者用系统代理（可被客户端忽略）。

> **这条事实有个重要推论**：既然 B 和 C **都必须改 `GameMainConfig` + 重打包 + 重签**，那"改包风险"对两者是**同价**的。
> 差别只在"改完之后还要不要额外的 CA 工作"。这让 C 的优势变得非常大。

---

### 路径 A：改 native 里的校验逻辑（跳过证书验证）

**A1 — 改 `libunity.so` 的 mbedTLS 校验**（任务原意是改 `libil2cpp`，但那里面没有校验代码，见 §1.1）

| 项 | 评估 |
|---|---|
| 技术前提 | 定位 `x509_verify_cert` / `mbedtls_ssl_conf_authmode` 的调用点并 patch 成立即返回 0。**`libunity.so` 被 strip**，只能靠 mbedTLS 报错串的 xref 反推 |
| **致命障碍** | **ACE 定点校验钉 `libunity`**（任务前提 ⑤）。改这个文件等于直接撞校验面 |
| 要改什么 | `libunity.so`（20,950,552 B）里若干条 `RET`/分支；整个文件摘要改变 ⇒ v1/v2/v3 全重算 |
| 能不能验证 | 能（真机启动 + 抓 TLS），但**验证的前提是先过 ACE**，而 A1 恰恰在 ACE 的靶心上 |
| **判定** | **❌ 否决**。不是"难"，是"打在 ACE 钉得最死的那个文件上" |

**A2 — 改 `libil2cpp.so`**（任务原意）

| 项 | 评估 |
|---|---|
| 技术前提 | BestHTTP / `CustomCertificateHandler.ValidateCertificate` 的 IL2CPP 生成代码在 `libil2cpp.so` 里（代码在、**符号不在**） |
| 现实 | 270,927,056 B 的 stripped 二进制里找一段**没有符号、没有字符串 xref** 的 C# 方法体；改错一个字节就是全游戏崩 |
| 打错了目标 | 它管的是**登录链（BestHTTP）**，而登录链**本来就不卡证书**（§2.3）。真正卡住的 `/api/state` 不在这条路径上 |
| 要改什么 | 258 MB 文件的若干条指令 + 全签名重算 |
| **判定** | **❌ 否决**。目标错 + 工程量不可控（比 A1 更差：A1 至少打在对的文件上） |

> A 路线的**唯一残余价值**：如果将来 ACE 的定点校验被证明不覆盖 `libunity` 的 `.text`，A1 会成为"一劳永逸"方案
> （一次 patch 永久绕过，不依赖 CA、不依赖 http）。但在拿到"libunity 改了还能过 ACE"的实证之前，**不要投预算**。

---

### 路径 B：不跳过校验，让客户端**信任**我们的证书 ★ 推荐之一

**核心机制（本轮新增的确证）**：客户端信任集来自 `TrustManagerFactory.getAcceptedIssuers()` ⇒ 受 app 的
`res/Dk.xml` 裁决 ⇒ **把 `<trust-anchors>` 加进 NSC，我们的 CA 就进 `trusted_ca`**，不需要 root、不需要系统库。

| 项 | 评估 |
|---|---|
| 技术前提 | ① NSC 里加 `<trust-anchors>`；② 提供证书。**②有两条子路线**（见下） |
| 改动面 | `res/Dk.xml`：**264 B → 552 B**（+288 B），method=0（stored），无 `resources.arsc` 改动（文件名/ID 不变） |
| ACE 风险 | `res/*` 实测**不被 ACE 定点校验**（任务前提 ⑤；`_dd3-P4-userCA.md:297` 记录三次重签 E30/E38/E42 都跑得起来）。残余风险 = `sourceDir` + 签名上报的**账号级**风险，未量化 |
| 能不能验证 | **能，而且判据很干脆**：冷启后看是否还出现 `Curl error 60` / `UnityTls error code: 7` |

**B 的两个子路线**

- **B1（NSC 指 `user` + 用户手动装一次 CA）** —— 构建最简单，零 `resources.arsc` 改动。
  代价：每台设备要手动「设置 → 安全 → 加密与凭据 → 安装证书 → CA 证书」，**零 root 但有一次人工步骤**。

- **B2（NSC 指 `@raw/<自己的 CA>`，CA 内置进 APK）** —— **完全零人工**，装完即用。
  代价：要新增一个 `res/raw` 条目 + 改 `resources.arsc`（新增一个条目和一条字符串），
  并且这份 APK **自带我们的私钥对应证书**（分发即等于公开我们的根 CA，只能用于私服，**绝不能用于任何别的东西**）。
  > 注意 `@raw` 的证书**必须是我们自己签的那张根 CA**，且 NSC 里 `trust-anchors` 要同时保留 `src="system"`，
  > 否则连官方 CDN 的证书都不认，游戏会在别处炸。

**B 的关键风险（诚实列出）**

1. **重签 = ACE 的账号风险**。历史三次重签都跑起来了，但"跑起来"≠"不被风控"。这条风险 **B 和 C 都要背**。
2. **B1 的人工步骤会被用户跳过**（忘了装 CA ⇒ 现象和没改一样），运维上要配好判据。
3. **NSC 是进程级单例**：装完 CA / 换完 APK **必须冷启**（force-stop 后重启），否则看起来"没生效"。
4. ⚠ 证书格式：历史用户库里那份是 **819 B DER**，而 `_dd3-P4-userCA.md:216-228` 认为 `AndroidCAStore` 的读法只认 PEM。
   本轮不裁决这个争议（两条说法对本方案都不致命），但**工程上统一用 PEM 装、装完回读首 30 字节**，两边都满足。

---

### 路径 C：把 `ServerInfoDataUrl` 改成明文 `http://` ★ 最推荐

**思路**：TLS 问题不解决，而是**让它不存在**。`/api/state` 走明文 ⇒ 不需要任何证书。

| 项 | 评估 |
|---|---|
| 技术前提 | ① 客户端接受 `http://`（**未知**，见下）；② 明文被允许（**已确证**，见下） |
| 明文是否被允许 | **确证**：manifest `<application usesCleartextTraffic="true">`（本轮 AXML 实测该属性存在）；且 NSC 的 `base-config cleartextTrafficPermitted="true"`（`res/Dk.xml` 原文，`_dd3-P4-userCA.md:86-88`）。**两道闸都开着** |
| 改动面 | **80 B 密文**（本轮实测，见下），文件大小 / 全部偏移不变 |
| 后续链路 | state 的响应**由我们给**，`Servers` 直接给 `http://...` ⇒ **整个会话再没有任何 TLS** |
| ACE 风险 | `assets/*` 不被 ACE 定点校验（前提 ⑤；`GAMEMAINCONFIG_CN.md:333-336` 只做了字节级闭环，未上机） |
| 能不能验证 | **能，判据最干净**：PC 上起 `:80` 明文服务，看是否收到一条 `GET /api/state` |

**★ 本轮实测：等长 `http://` 变体（最优解）**

关键技巧：`https` → `http` 少 1 字符，所以**域名取 19 字符**就能让整串 value **仍是 101 字符**，
`layer1 JSON` 仍 545 字符 ⇒ **完全不需要尾部补空格**（比 `GAMEMAINCONFIG_CN.md:303-315` 的方案 B 更干净，
不依赖"客户端容忍 JSON 尾部空白"）。

```
原:  ["https://state-api.bluearchive-cn.com/api/state","https://stateqc-api.bluearchive-cn.com/api/state"]   101
新:  ["http://state-api.bapsvr-prods-cn.com/api/state","http://stateqc-api.bapsvr-prods-cn.com/api/state"]   101
      ↑ https(8)→http(7)  -1 ；域名 bluearchive-cn.com(18)→bapsvr-prods-cn.com(19)  +2 … 逐段对齐后总长不变
```

本轮 `s11/s12` 实跑（**产物已落盘并回读复核**）：

| 变体 | value 长度 | layer1 JSON | 密文差异 | 需要补空格 | 回读 6 字段 |
|---|---|---|---|---|---|
| **C-等长（19 字符域名）** | 101 = 101 | 545 = 545 | **80 B** | **否** | ✅ 6/6 |
| C-补空格（18 字符域名） | 99（少 2） | 537 + **8 空格** = 545 | 313 B | 是 | ✅ 6/6 |
| （对照）仅换 https 域名 | 101 | 545 | 28 B | 否 | ✅（`GAMEMAINCONFIG_CN.md:290`） |

`19` 字符域名举例（**占位，按你的真实域名替换**）：`bapsvr-prods-cn.com`（80 B 差异）、`bapsvr-prod-cn1.com`（88 B 差异）。

**C 的唯一实质未知：客户端是否接受 `http://`**

- 静态上**两边都没有证据**：`libil2cpp.so` 里的 `http://` 全是 Brotli 字典噪声；`https://` 在 metadata 里 86 次
  （多为 SDK 端点）、在两个 .so 里 2~3 次。
- ⚠ **必须纠正一条会误导的话**：`_dd3-P4-userCA.md:260` 写「默认连接组字面量本身就是 `http://`（`report/11:313`）」——
  本轮在国服 3.0.2 的 metadata / 两个 .so 里**找不到任何功能性 `http://` 默认连接组字面量**（域名字面量本身是混淆的，
  `GAMEMAINCONFIG_CN.md:180-183`）。那条很可能是**国际服/旧包**的观测，**不要当国服的依据**。
- 风险的实际大小：URL 是从配置读出来直接喂给 `UnityWebRequest` 的，libcurl 与 UnityWebRequest 都天然支持 http，
  代码里**没有理由**去断言 scheme。⇒ **推断·中高：能通**；但这是 C 的**唯一**死点，必须用一次真机实验钉死。

---

### 路径 D：DNS/hosts 劫持 + 把 CA 内置进 APK 的 `cacert.pem`

| 项 | 评估 |
|---|---|
| 前提①：客户端读 app 内的 PEM bundle | **❌ 已证伪**。全 APK 只有 3 个证书类文件：`assets/grs_sp.bks`、`assets/hmsincas.bks`、`assets/hmsrootcas.bks`（华为 HMS 的 BKS 信任库，给 HMS push/账号 SDK 用），**没有任何 `.pem/.crt/.cer`、没有 `cacert`/`ca-bundle`/`certifi` 资源**。`libunity.so` 里 `cacert` / `ca-certificates.crt` / `trusted_ca` **0 命中** |
| 前提②：hosts/DNS 劫持免 root | **❌ 不可行**。hosts 要 `/system/etc/hosts`（root）；DNS 要改网关/VPN（`VpnService` 只能改路由，不改 TLS 信任，`_dd3-P4-userCA.md:291`） |
| **判定** | **❌ 按字面否决**。但它的**意图（CA 随包走、零人工）由 B2 的 `@raw` 完整实现**，且机制正确 |

> 顺带说明华为那三个 `.bks`：它们是 **BKS** 格式（Java keystore），只有 HMS SDK 自己会读，
> UnityTLS/mbedTLS **根本不解析 BKS**。往里面塞证书**没有任何消费者**。

---

## 4. 排序建议（Q4）

**免 root 可行，且有两条真实路径。排序：C > B2 > B1 ≫ A1 > A2 / D。**

| 排名 | 路径 | 为什么这个次序 |
|---|---|---|
| **1** | **C（`http://` 等长改域名）** | 改动最小（**80 B 密文**，无补空格、无 arsc 改动、无证书、无人工步骤）；TLS 直接消失，**后续整条会话都能明文**；两道明文闸（manifest + NSC）**都已确证开着**。唯一未知是"客户端接不接受 http"，而这是**一条命令就能测**的 |
| **2** | **B2（NSC `@raw` 内置 CA）** | 保留 https（对外观感最好、最像"正常客户端"），零人工步骤；机制本轮已确证。代价是 `resources.arsc` 要新增 raw 条目 + **根 CA 随包分发**（安全上必须认这个账） |
| **3** | **B1（NSC `src="user"` + 手动装 CA）** | 构建最简单（只改 264 B XML），但每台设备一次人工步骤；一旦用户跳过，现象和没改一样 |
| 4 | A1（patch `libunity` 的 mbedTLS） | 文件对了，但 `libunity` **正是 ACE 定点校验钉的那个**。**除非**先拿到"改 libunity 仍过 ACE"的实证 |
| 5 | A2（patch `libil2cpp`） | 目标错（登录链不卡证书）+ 258 MB stripped 无法定位。**双向否决** |
| 6 | D（内置 pem + DNS 劫持） | 机制证伪（无 pem 消费者）+ 免 root 无 DNS 控制权 |

**为什么 C 排第一而不是 B**：两者**都要改 `GameMainConfig` + 重签**（因为免 root 没 DNS 控制权，见 §3 开头），
所以"改包风险"完全同价。在这个前提下，C 只是**多省掉**"证书 + NSC + 可能的 arsc 改动 + 人工步骤"这一整串；
而它新增的未知只有一个可一枪打死的"scheme 接受度"。**风险更少、判据更短。**

**为什么 B 仍然要做**：C 若被"客户端强制 https"挡住，B 就是兜底，而且两者的 `GameMainConfig` 补丁是**同一处**，
只差 `http`/`https` 一个字符 ⇒ 切换成本≈0。**B 和 C 应该当成同一套方案的两个开关来实现。**

**推荐组合**：先出 **C 版**（最少改动），同时把 **B2 版**一起打出来做对照。一次真机实验能同时判定两条。

---

## 5. 如果都不行

**不成立就明确说**：

- 如果 **C** 失败（客户端拒绝明文 / 服务端 80 不通）**且 B** 失败（NSC 改了也不生效 —— 那只能是 ACE 拦了重签包，
  或 NSC 解析失败），那么：
  **免 root 下 TLS 绕不过。** 剩下只有两条：
  1. **root**（KernelSU/Magisk 把 CA 放进 `/apex/com.android.conscrypt/cacerts` —— 项目已实测可用，
     `_dd3-P4-userCA.md:481-504`）；
  2. **改 native**，且必须改 `libunity.so`（**不是** `libil2cpp.so`），而这直接撞 ACE ⇒ 实际等价于"也不行"。

- **不要**把"用户证书装不上"当成死因。本轮已证伪这个死因：用户库进不来是因为**走的不是那条路**，
  而那条路的开关在 APK 里。真正的死因只可能是**重签被 ACE 拦**。

---

## 6. 下一步实验清单（每条路径的最小验证）

> 原则：**先做不需要改包的那一条**（E0），它的结果能一次否掉整份静态结论；然后再做最省的改包实验（E1）。
> 全部实验都应遵守：**一次只改一个变量**、**必须冷启**（NSC / trusted_ca 都是进程内单例）、
> **用户手动点屏，不脚本点击**。

### E0 —— 零改包的"反证"实验（**先做这个**，15 分钟）

只装用户 CA，**不改 APK**，看 `/api/state` 是否通过。

1. `openssl x509 -in <你的CA>.crt -noout -subject -dates -subject_hash_old` 记录 `hash_old`（**确证**证书自身没问题：
   `CA:TRUE` + SAN 覆盖 `state-api.*`）。
2. PC 起 TLS 终止代理（代理模式，`--pass-others` 保证 SDK 段不断）。
3. 手机：设置 → 安全 → 加密与凭据 → 安装证书 → **CA 证书** → 装 `<你的CA>.crt`（**用 PEM**）。
   装完在「信任的凭据 → 用户」里**亲眼看到它**。
4. 手机 Wi-Fi 代理指向 PC。
5. **冷启**：`am force-stop` → `logcat -c` → 手动点图标。
6. 判据：出现 `P4-CONNECT state-api...:443` 且**没有** `Curl error 60` / `UnityTls error code: 7`
   → **静态结论被推翻**，免 root 只需装 CA，**连 APK 都不用改**（最好的结局）。
   反之（预期）→ 机制 (a) 确认，直接进 E1。

### E1 —— 路径 C（**最省**，2 小时）

1. 用 §8 的脚本生成 `GameMainConfig_http_<19字符域名>.bin`（**80 B 差异**那一版）。
2. 把它换回 APK 的 `assets/bin/Data/e37c46fea17834108a4756797197d05a`（zip STORED/DEFLATE 重写该条目即可，
   **不要**动其它条目）。
3. 重签（v1+v2+v3，项目已有 `build_noroot_apk.py` 同款流程）。
4. **服务端先就绪**：`<19字符域名>` 的公网 A 记录指向你的机器，`:80` 起一个能返回合法 state JSON 的服务。
5. 冷启 + 点屏。
6. 判据（三档）：
   - **收到 `GET /api/state`（明文）** → **C 成立**，收工；
   - **完全没请求** → 客户端可能仍按 https 去连（域名的 443 有人接吗？先确认不是在连 https），
     或域名没解析到；看服务端 `:443` 是否有 SNI 到达；
   - **客户端报 URL/scheme 非法** → C 死，转 B。

### E2 —— 路径 B（与 E1 并行准备，同一个 APK 框架）

1. 拿 §8 的 `res_Dk_patched.xml`（**552 B**，已验证 chunk 平铺到 `0x228`），替换 APK 里的 `res/Dk.xml`。
   （该文件 method=0 / STORED，大小变大不影响 `resources.arsc`：**arsc 只记路径不记大小**，本轮已实测 `res/Dk.xml` 仅被
   1 条 `Res_value{TYPE_STRING}` 引用。）
2. **B2**：再加 `res/raw/<name>.pem`（我们的根 CA）并把 NSC 里 `src` 改成 `@raw/<name>` —— 需要同时改 `resources.arsc`
   （新增一个字符串 + 一个 entry）。**B1 则跳过这步**，只让用户装 CA。
3. 重签 → 冷启 → 点屏。
4. 判据：`Curl error 60` / `UnityTls error code: 7` **消失**，`GET /api/state` 返回 200，且**后续无 TLS 报错**。
5. **正控（必做，只在 E2 得到"拒绝"时才跑）**：把**同一张** CA 塞进 `/apex/com.android.conscrypt/cacerts`
   （root，`_dd3-P4-userCA.md:481-504`），重跑 → 必须"接受"；否则说明是我们证书/链路的问题，E2 结论作废。

### E3 —— 只在 E1/E2 都失败时才考虑

- 确认是"重签被 ACE 拦"还是"NSC 没生效"：拿**只改 `res/Dk.xml`、不动 `GameMainConfig`** 的包，
  配合**系统库正控**（root）跑一次：
  - 系统库有 CA + 未改包 → 通过（这条 `_dd3` 已验过）
  - 系统库有 CA + 改过 NSC 的包 → **不通过** ⇒ 重签被 ACE 拦了（问题不在 TLS）
  - 系统库有 CA + 改过 NSC 的包 → 通过 ⇒ NSC 生效，问题只在"用户库/`@raw` 那一步"

---

## 7. 需要回写的既有结论（本轮修正）

| 既有说法 | 本轮实测 | 处理 |
|---|---|---|
| 前提①「两者读的是 `AndroidCAStore`（含用户库）」 | **推翻**：`AndroidCAStore` 在 `libunity.so` **0 命中**；实际走 `TrustManagerFactory` + `X509TrustManager` ⇒ 受 NSC 裁决 | **改写前提**，这是全案转向的关键 |
| `_dd3-P4-userCA.md:116`「native 栈用户库是否参与：未知」 | 本轮给出**机制判定**：不参与（因走 (a)，被 NSC 过滤） | 升级为"机制已定，待 E0/E2 上机确认" |
| `_dd3-P4-userCA.md:260`「默认连接组字面量本身就是 `http://`」 | 国服 3.0.2 里**找不到功能性 `http://` 连接组字面量**；`libil2cpp.so` 的 20 次命中全是 Brotli 字典噪声 | **降级**，勿作依据 |
| 任务里 `AllowUnsafeConnection` / `SSLStream` / `CRYPTO_set_lookup_byaddrinfo` | 三个名字**都不存在**（0 命中，且非真实 API） | 停止用这些 needle |
| 「改 `libil2cpp` 跳过校验」 | `libil2cpp` 内 TLS 符号 0 命中；校验在 `libunity` | **改靶** |
| `_dd3-P4-userCA.md:297`（#13）NSC 改 `src="user"` "留作 Plan B" | 本轮把它**升为一线方案**（机制确证 + 已产出可用的 552 B AXML） | 升级 |

---

## 8. 产物与复现

### 8.1 本轮落盘（全部在 `%TEMP%`，**未进 APK**）

| 文件 | 大小 | 说明 |
|---|---|---|
| `%TEMP%\ba_tls_research\out\res_Dk_patched.xml` | **552 B** | NSC 加了 `<trust-anchors>`（system + user）；chunk 平铺校验到 `0x228` 通过，5 start / 5 end |
| `%TEMP%\ba_tls_research\out\GameMainConfig_http_example.com.bin` | 5,212 B | **C 等长版**：value 仍 101 字符、JSON 仍 545 字符、**密文差 80 B**、无补空格、6/6 字段回读通过 |
| `%TEMP%\ba_tls_research\out\GameMainConfig_http_bapsvr-prod-cn1.com.bin` | 5,212 B | 同上，另一域名，差 88 B |
| `%TEMP%\ba_tls_research\out\GameMainConfig_http_patched.bin` | 5,212 B | **C 补空格版**（18 字符域名 → 99 字符 + 8 空格），差 313 B |

> 这些是**磁盘上的真实字节**，可直接进打包流程；但 `%TEMP%` 会被清理，**可复现脚本见 §8.2/§8.3**。

### 8.2 NSC 补丁的目标 XML（等价语义）

```xml
<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <base-config cleartextTrafficPermitted="true">
        <trust-anchors>
            <certificates src="system"/>
            <certificates src="user"/>
        </trust-anchors>
    </base-config>
</network-security-config>
```

要点：① 必须**保留** `src="system"`，否则官方 CDN 全不认；② B2 变体把第二行换成 `src="@raw/<name>"`（并同步改 arsc）；
③ 原 264 B 里唯一的 `base-config` 属性是 `cleartextTrafficPermitted="true"`（typed value `08 00 00 12 ff ff ff ff`），**必须原样保留**。

### 8.3 复现（AXML 生成器 + 资产改写器，纯标准库）

```python
# 生成 patched res/Dk.xml（等价 AXML；已在 0x228 平铺校验通过）
import struct
class AXML:
    def __init__(self): self.strings=[]; self.body=bytearray()
    def s(self,x):
        if x not in self.strings: self.strings.append(x)
        return self.strings.index(x)
    def _node(self,t,payload,line=1):
        self.body+=struct.pack("<HHI",t,0x10,0x10+len(payload))+struct.pack("<II",line,0xFFFFFFFF)+payload
    def start(self,name,attrs=(),line=1):
        ext=struct.pack("<II",0xFFFFFFFF,self.s(name))+struct.pack("<HHHHHH",0x14,0x14,len(attrs),0,0,0)
        for ns,an,raw,dt,data in attrs:
            ext+=struct.pack("<III",0xFFFFFFFF if ns is None else self.s(ns),self.s(an),
                             0xFFFFFFFF if raw is None else self.s(raw))+struct.pack("<HBBI",8,0,dt,data)
        self._node(0x0102,ext,line)
    def end(self,name,line=1): self._node(0x0103,struct.pack("<II",0xFFFFFFFF,self.s(name)),line)
    def render(self):
        data=bytearray(); offs=[]
        for x in self.strings:
            offs.append(len(data)); b=x.encode(); data+=bytes([len(b)])+b+b"\x00"
        while len(data)%4: data+=b"\x00"
        ss=28+4*len(self.strings)
        pool=struct.pack("<HHI",1,28,ss+len(data))+struct.pack("<IIIII",len(self.strings),0,0x100,ss,0)
        pool+=b"".join(struct.pack("<I",o) for o in offs)+data
        total=8+len(pool)+8+len(self.body)
        return struct.pack("<HHI",3,8,total)+pool+struct.pack("<HHI",0x0180,8,8)+bytes(self.body)

a=AXML()
a.start("network-security-config")
a.start("base-config",[(None,"cleartextTrafficPermitted",None,0x12,0xFFFFFFFF)])
a.start("trust-anchors")
a.start("certificates",[(None,"src",None,0x03,a.s("system"))]); a.end("certificates")
a.start("certificates",[(None,"src",None,0x03,a.s("user"))]);   a.end("certificates")
a.end("trust-anchors"); a.end("base-config"); a.end("network-security-config")
open("res_Dk_patched.xml","wb").write(a.render())     # 552 B
```

```python
# 生成 http:// 版 GameMainConfig（等长，80 B 差异）；需 work\ba\noroot\CRYPTO_MT.py
import base64,json,sys,zipfile
sys.path.insert(0, r"C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\noroot")
from CRYPTO_MT import create_key, xor_with_key8
APK=r"C:\Users\su\Desktop\大肥鱼项目\BAServer\report\_tmp\cn_base.apk"
M="assets/bin/Data/e37c46fea17834108a4756797197d05a"
asset=zipfile.ZipFile(APK).read(M); sl=int.from_bytes(asset[0x1014:0x1018],"little")
k8=create_key("GameMainConfig"); body=asset[0x1018:0x1018+sl]
plain=xor_with_key8(k8,body).decode("utf-16-le"); js=json.loads(plain); CAP=sl//2
cyc=lambda n,k:(create_key(n)*(k//8+2))[:k]
dec=lambda n,ct:bytes(a^b for a,b in zip(ct,cyc(n,len(ct))))
b64d=lambda s:base64.b64decode(s+"="*(-len(s)%4)); b64e=lambda x:base64.b64encode(x).decode()
FN="ServerInfoDataUrl"
kb=next(k for k in js if dec(FN,b64d(k))==FN.encode("utf-16-le"))
NEW=('["http://state-api.{0}/api/state",'
     '"http://stateqc-api.{0}/api/state"]').format("bapsvr-prods-cn.com")   # 域名 19 字符
assert len(NEW)==101, len(NEW)                       # 等长，无需补空格
js[kb]=b64e(dec(FN,NEW.encode("utf-16-le")))
s2=json.dumps(js,separators=(",",":"),ensure_ascii=False)
assert len(s2)==CAP
nb=xor_with_key8(k8,s2.encode("utf-16-le"))
out=bytearray(asset); out[0x1018:0x1018+sl]=nb
open("GameMainConfig_http.bin","wb").write(bytes(out))   # 5212 B
```

### 8.4 证据索引（二进制偏移）

| 证据 | 位置 |
|---|---|
| JNI `TrustManagerFactory` 绑定表 | `libunity.so` `0x0111b74a` … `0x0111b9da` |
| `x509_verify_cert` + mbedTLS 报错串 | `libunity.so` `0x010badeb` … `0x010baf64` |
| `CertificateHandlerProxy` | `libunity.so` `0x01066565` |
| `CertificateHandler::Create` | `libil2cpp.so` `0x02667f74` |
| `CustomCertificateHandler-ValidateCertificate0` | `global-metadata.dat` `0x0041b7ef` |
| `SetCertificateHandler` / `ValidateCertificateNative` | `global-metadata.dat` `0x007a5fbb` / `0x007a63ef` |
| `ICertificateVerifyer` / `NotifyServerCertificate` | `global-metadata.dat` `0x00607f9f` / `0x006080ff` |
| NSC（唯一） | `res/Dk.xml` 264 B，arsc 串索引 101 |
| GameMainConfig | `assets/bin/Data/e37c46fe…` m_Script `0x1018..0x145A`，1,090 B |
