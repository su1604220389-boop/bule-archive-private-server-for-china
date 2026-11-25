# DD3: P4 信任用户 CA 的可行性与实验设计

> 任务：判定「不改包，让客户端信任装到**用户证书库**的 CA」这条路（P4）能不能成立，并设计一个**不需要 root** 的实验把它钉死。
> 工作目录 `C:\Users\su\Desktop\大肥鱼项目\BAServer`。本文只读其它文件，新增文件全部在 `work\ba\noroot\`。
> **没有连服务器、没有连手机、没有执行任何网络操作**（本文的命令都是给下一轮执行的，本轮未运行）。
>
> 标注：**确证** = 有字节/行号/实测日志；**推断** = 由确证事实推出但未上机；**未知** = 项目内没有能判定的观测。
> 引用格式：`文件:行号`（路径相对工作区根）。

---

## 结论速览

1. **App 不信任用户 CA，而且这是显式写死的**：`AndroidManifest.xml` 里 `android:networkSecurityConfig="@xml/http"`，而 `res/xml/http.xml` **只有** `<base-config cleartextTrafficPermitted="true"/>`，**没有任何 `<trust-anchors>`/`<certificates src="user"/>`** ⇒ `targetSdk=33` 下 Java 侧只收系统 CA（**确证**，本轮用 AXML 解析器实测，见 §1）。顺带纠正：`report/06:628`「manifest 里 grep 全空、无该属性」是**方法错误**（二进制 AXML 用 ASCII grep，连 `targetSdkVersion` 都 0 命中）。
2. **libcurl 这一栈的 CA 来源 = 设备的信任库（不是 App 内 bundle、不是硬编码 pin）**，且**已经被实测证明它确实在读这个库**：把 CA 装进系统库 + 服务端链根换成同一张 CA 后，`Curl error 60 / UnityTls error code: 7` 消失、同一链路 `GET /api/state 200`、46 条 `fatal alert 49` 在 01:33:45 归零（**确证**，§2.2）。所以「用户证书这一格根本不参与验证」这个最坏情形**已被排除**——问题只剩「它读的那个库**含不含**用户库」。
3. **这一步项目内从来没做过干净实验**：历史上唯一一次「只装用户 CA」失败（01:27–01:31），同窗口服务端用的根证书是 `ca3`（伪装 RapidSSL），与用户库里的 `BA Test Root CA` **不是同一张**，失败被「链根不匹配」完整解释（**确证**，`report/06:653-659`）⇒ 不能据此判 P4 死。`report/17:124`「系统/用户 CA 已证伪」结论过宽。**并且那次装进用户库的是 819 B 的 DER**——`AndroidCAStore` 的读法（conscrypt `TrustedCertificateStore`）**只认 PEM**，DER 会被静默跳过（§2.4）⇒ 实验必须用 PEM 装、装完看字节。
4. **文档证据倾向可行**：Unity `UUM-73839` 明写「2021.3.48f1 起，用户装到 Android 设备上的证书会出现在 `trusted_ca` 列表里」，本包是 **2021.3.56f2 > 48f1**（**一手 release note，项目内转引** `report/12:161-168`）。但对手方证据是 §1 那份 `@xml/http`——若 Unity 走 `TrustManagerFactory(null)`，app 自己的 config 才是最终裁决者，用户 CA 会被挡。
5. **P4 判定：需真机验证（30 分钟可定），证据偏「可行」**。实验**完全不需要 root**：Wi-Fi 系统代理（零 root 改重定向）+ 设置里装用户 CA（零 root），判据是代理端一行 `P4-TLS-OK` / `P4-TLS-REJECT`。附带修正 `report/90:264`「免 root 分发不可行」——它把「重定向必须 DNAT」当成了前提，而项目自己已有正证据表明 `UnityWebRequest` 吃系统代理（`report/101:246`）。

---

## 1. App 是否声明信任用户 CA（证据）

### 1.1 方法先纠正：不能用 grep 读 AXML

`work/ba/audit/ba-apk/AndroidManifest.xml` 是**二进制 AXML**，不是文本：

```
size=50552  前 16 字节 = 03 00 08 00 78 c5 00 00 01 00 1c 00 5c 55 00 00
→ type=0x0003 (RES_XML_TYPE), headerSize=8, totalSize=0x0000c578
字符串池：338 条，编码 = **UTF-16LE**（flags 无 0x100）
```

对它做 ASCII `grep` 时，**连一定存在的 `targetSdkVersion` 都是 0 命中**（本轮实测）。所以
`report/06-手机基线恢复.md:628`、`report/DEADENDS.md:343`、`report/INDEX.md:513`（A-20）里那条
「`grep 'networkSecurityConfig|cleartext|network'` → 全空（无该属性）」**不能作为证据**。它只证明了 grep 看不见 AXML。

本轮写了正规解析器并实跑：`work/ba/noroot/_dump_axml.py`（自写，纯标准库，只读）
→ 输出落盘 `work/ba/noroot/_axml_out.txt`。

### 1.2 实测结果（原包 manifest，确证）

`[   2] <manifest>`：

| 属性 | 值 |
|---|---|
| `versionCode` / `versionName` | `73` / `3.0.2` |
| `package` | `com.RoamingStar.BlueArchive` |
| `compileSdkVersion` / `Codename` | `33` / `13` |

`[   8] <uses-sdk>`：`minSdkVersion = 24`，`targetSdkVersion = 33`
（与背景给的 SDK 值一致，**确证**；同时说明「targetSdk<24 的例外」这条**不存在**。）

`[ 202] <application>`（11 个属性，逐条）：

```
label                        = @ref/0x7f0f0028
name                         = com.tech.core.TechApplication
allowBackup                  = false
extractNativeLibs            = true
usesCleartextTraffic         = true            ← ★
networkSecurityConfig        = @ref/0x7f120001 ← ★
requestLegacyExternalStorage = true
（其余 4 个为 icon/theme 一类引用）
```

**`0x7f120001` 是哪个文件？** 用 jadx 出来的 R.java 反查（三份 R.java 一致）：

```
com\airi\official\core\R.java:599   public static final int http = 0x7f120001;
com\RoamingStar\BlueArchive\R.java:6677  public static final int http = 0x7f120001;
com\unity3d\player\R.java:6587      public static final int http = 0x7f120001;
```

⇒ `@ref/0x7f120001` = **`R.xml.http`** = `res/xml/http.xml`。

### 1.3 `res/xml/http.xml` 里到底写了什么（确证）

从 `work/ba/bapatch/res.apk`（3,145,659 B，含 1646 个 entry、完整 `res/xml/*` + `resources.arsc`）抽出
`res/xml/http.xml`（**264 B**），用同一解析器解出：

```
[hdr] type=0x0003 ... isAXML=True
[pool] strings=3 utf8=True
[    2] <network-security-config>  attrs=0
[    3] <base-config>  attrs=1
          cleartextTrafficPermitted          = true
[elements] total start-elements = 2

[keyword scan]  trust-anchors=0   certificates=0   src="user"=0
```

内容等价于：

```xml
<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <base-config cleartextTrafficPermitted="true" />
</network-security-config>
```

（这是 Unity "Allow downloads over HTTP" 开关生成的模板，`report/06:631` 记录的三个字符串
`base-config / cleartextTrafficPermitted / network-security-config` 与之吻合。）

> **路径注意**：我抽的这个 `res/xml/http.xml` 来自 `work\ba\bapatch\res.apk`（**重建版**资源包，1646 个 entry，名字可读）。**原包**的 `res/` 做过 AndResGuard 式**扁平混淆**（`_dd1-P2-repack.md:36`），所以在 2.1 GB 原包里按 `res/xml/http.xml` 找不到它；两者靠 **resource id `0x7f120001`** 对齐，内容相同这一点另有 `report/06:631` 的三字符串记录独立佐证。

### 1.4 判定

| 命题 | 结论 | 置信度 | 依据 |
|---|---|---|---|
| App 是否声明 `networkSecurityConfig` | **是**，`@xml/http` | **确证** | `work/ba/audit/ba-apk/AndroidManifest.xml` AXML 解析（`_axml_out.txt`）；`res.apk` 内重建版 manifest 同样字段（50,220 B，attr 数 11，两处关键属性一致） |
| 是否声明信任用户 CA（`<certificates src="user"/>`） | **否**。`http.xml` 只有 `base-config`，**零 `trust-anchors`** | **确证** | 同上的 AXML 解析 + 关键字扫描 |
| `usesCleartextTraffic` | **true**（且 `http.xml` 的 base-config 也是 `true`） | **确证** | 同上 |
| `targetSdk` | 33 ⇒ 用户 CA 默认不被信任的例外**不存在** | **确证** | `<uses-sdk>` 实测 + `report/20:170`（AOSP：`targetSdkVersion<=23` 才 `addCertificatesEntryRef(UserCertificateSource)`） |
| ⇒ **对 Java 栈**（`TrustManagerFactory`/`NetworkSecurityConfig`），用户库**不参与** | **成立** | **确证**（机制） | `report/20:141-172`（`SystemCertificateSource`/`ApplicationConfig` 源码） |
| ⇒ **对 native 栈（libcurl/UnityTLS）**，用户库**是否参与** | **未知，必须实验** | **未知** | 见 §2 |

> 一句话：**§1 只关掉了「Java 侧会不会信任用户 CA」这一个问题**（答案：不会）。它**不能**直接推出 P4 死，
> 因为本项目真正卡证书的那条链路（`/api/state`）走的是 **native libcurl + UnityTLS**，不是 Java 栈（§2.1）。
> 这也正是本节最容易被误读的地方——`report/06:626` 这一节被标题写成「`networkSecurityConfig` 这条路在本 APK 上不存在」，**结论方向反了**。

**交叉验证（同期另一份交付物，独立方法、同结论）**：
`work/ba/noroot/_dd1-P2-repack.md:12-13,129-136` 用**另一个**自写 AXML 解析器 + jadx 解出的
`work/ba/audit/ba-apk/jadx/resources/AndroidManifest.xml:187-189` 独立得到同一组事实：
`usesCleartextTraffic="true"`、`networkSecurityConfig="@xml/http"`（同一个 `0x7f120001`）。
两份独立实现互相印证 ⇒ §1 的结论达到**确证**级。
（注意：该包的 `res/` 做过 AndResGuard 式扁平混淆，所以「`res/Dk.xml` 存不存在」这种按文件名争的题目没有意义；
`resource id 0x7f120001 → R.xml.http` 这条映射与混淆无关，另见 `_dd1-P2-repack.md:36`。）

---

## 2. libcurl 的 CA 来源（核心，决定 P4 生死）

### 2.1 先钉死：客户端里**有两条** HTTP/TLS 栈，UA 可区分（确证）

| 栈 | UA（实测原文） | 承载的请求 | 出处 |
|---|---|---|---|
| **UnityWebRequest + libcurl + UnityTLS** | `UnityPlayer/2021.3.56f2 (UnityWebRequest/1.0, libcurl/8.10.1-DEV)` | `GET /api/state`、AssetBundles 下载、地址表 | `report/22-服务端取证记录.md:61,68`、`report/101:291`、`report/100:278` |
| **BestHTTP/2（托管，含 BouncyCastle）** | `BestHTTP/2 v2.4.0` | `POST /api/account/auth`、`/api/account/nickname`、`/api/academy/getinfo` | `report/41:54-61,496-500`、`report/63:23`、`report/74:156-158` |

`report/41:499` 的原话：「登录这一枪走的是 `Http1Message`(BestHTTP) 分支，它的响应解码路径与 `/api/state` 不是同一段代码」。
⇒ **两条栈要分开判**，任何「客户端不 pin / 客户端 pin」的整体结论都是把两条栈混成了一句话。

### 2.2 libcurl 这条栈的 CA 从哪来：一层层排除（全部确证）

| 假设 | 排除/确认 | 证据 |
|---|---|---|
| ① App 内自带 CA bundle（`assets/cacert.pem` 等） | **排除**。APK 无 `cacert/ca-bundle/*.pem`；`libunity` 无内嵌证书；`-----BEGIN PUBLIC KEY-----` 那处是 libcurl 自己的 PEM 标签串（上下文 `CURL_SSL_BACKEND/ALPN`） | `report/06:459-475`、`report/19:48` |
| ② 硬编码 pinning（比 SPKI/指纹） | **排除**。真实报错是 `Curl error 60: ... not correctly signed by a trusted CA` + `UnityTls error code: 7`（= unknown CA），pinning 拒绝不长这样；且此后换根证书即通 | `report/06:643-647`、`report/16:104`（Unity 侧 verify 失败只会报 `UNITYTLS_X509VERIFY_FLAG_USER_ERROR1`/`Curl error 60`） |
| ③ 校验发生在**托管** `CustomCertificateHandler.ValidateCertificate` | **对 `/api/state` 不成立**。若 handler 被装上，托管方法就是终裁，**不会**出现 native 的 `Curl error 60`/`UnityTls error 7`。该类确实存在（metadata `0x1522b3`，覆写 `ValidateCertificate`），但**没有作用在这条路径上** | `report/11:227-231`、`report/06:643` |
| ④ 校验读**设备信任库** | **确认**。三件事同时发生：CA 以 PEM + label `u:object_r:system_security_cacerts_file:s0` 装进系统库、服务端链根改成同一张 `BA Test Root CA` ⇒ (a) `UnityTls error 7` 消失；(b) 同一链路 `GET /api/state` 200/180 B；(c) 46 条 `fatal alert 49` 在 **01:33:45 归零**，01:34:52 起应用数据正常 | `report/29:11`、`report/22-服务端取证记录.md:15,23,32,37,78`、`report/06:653-659`、`report/23:16-21` |

**⇒ 判断（本节答案）：`libcurl/UnityTLS` 的 CA 来源 = 设备信任库。不是 App 内 bundle，不是硬编码 pin，不是托管 handler。**
这直接否掉了任务里那个「最坏情形」——用户证书这一格的**容器**（设备信任库）确实是客户端真正读的东西。
剩下唯一没定的就是：**它读的这个库里，用户库那一半算不算数。**

### 2.3 它到底用哪个 API 读这个库（决定用户 CA 能不能进）

`libunity` 里有 JNI 侧字符串（确证，`report/11:226`）：

```
javax/net/ssl/X509TrustManager      libunity.so.txt L31594
checkServerTrusted                  libunity.so.txt L31597
CertificateHandlerProxy             libunity.so.txt L17664
ValidateCertificateNative           libunity.so.txt L17681
mbedtls*（107 条）                   libunity.so.txt  ← TLS 实现在 libunity（UnityTLS/mbedTLS）
```

三种可能的实现（**项目内无法区分 ⇒ 未知**）：

| 机制 | 用户 CA 是否进 `trusted_ca` | 受 app 的 `@xml/http` 约束吗 | 依据 |
|---|---|---|---|
| (a) JNI 调 `TrustManagerFactory.getInstance("X509").init((KeyStore)null)` + `getAcceptedIssuers()` | **否**（`RootTrustManagerFactorySpi` → `RootTrustManager` → `NetworkSecurityConfig` → targetSdk≥24 只给系统 CA） | **是**（config 决定） | `report/20:141-172`（AOSP 机制） |
| (b) 直接 `KeyStore.getInstance("AndroidCAStore")` 枚举 alias（`system:` + `user:` 前缀） | **是**（conscrypt `TrustedCertificateStore` 天然含 `user-added`） | **否** | `report/20:116-131`（该路径只认 PEM，与 targetSdk 无关） |
| (c) 逐文件扫 `/system/etc/security/cacerts`（或含 `/apex/com.android.conscrypt/cacerts`） | **否** | **否** | `report/20:110`（原生 libcurl/BoringSSL 只解析 PEM 文件） |

**支持 (b) 的最强证据（一手 release note）**：

> `2021.3.48f1 | Fixes | Android | Fix | Fixed issue where user installed certificates directly to an Android device wouldn't show up in the trusted_ca list.`
> —— Unity 2021.3.48f1 release notes（`report/12:161-168` 转引，原文链接在同处）

本包 UA 是 **2021.3.56f2**（`report/101:291`）⇒ 数值上晚于 48f1，**该修复应在**。
「user installed certificates … would show up in the `trusted_ca` list」这句话的措辞本身很有信息量：
它说的是 Unity **自己构建的那张 `trusted_ca` 列表**——如果是 (a)，那么修不修都受 `networkSecurityConfig` 支配，
Unity 也就无法通过一个引擎版修复来改变行为；能「修好」说明它多半走 (b) 或 (b)+(a)。
**置信度：推断·中偏高（一手 release note + 机制推理，未在本包验证）。**

**反对证据（必须摆出来）**：本包**自己声明了** `@xml/http`（§1）。如果实现是 (a)，
那么即使引擎有 UUM-73839 的修复，app 的 config 依然是终裁者 ⇒ 用户 CA 被挡 ⇒ **P4 死**。
这条无法从静态证据排除，**只能实验**。

### 2.4 历史「用户 CA 无效」的结论为什么不能用

时间线（全部出自 `report/06-手机基线恢复.md`、`report/22-服务端取证记录.md`）：

| 时刻 | 用户库 | `/system` + `/apex` | 服务端链根 | 结果 |
|---|---|---|---|---|
| 00:5x–01:31 | `fd8b2b01.0`（819 B **DER**） | **无**（`report/06:601`：「之前我们从未真正把 CA 放进 /system 或 /apex」） | **`ca3/chainS.crt`（伪装 RapidSSL，根 ≠ BA Test Root CA）** | 失败（alert 49 / 网络错） |
| 01:27 | 同上 | 同上 | 同上 | 「请确认网络连接状态后重试」 |
| 01:31 | 同上 | **写入 PEM，147 项，label 正确** | 仍 `ca3` | 仍失败 |
| **01:33 后** | 同上 | 同上 | **切回 `ca2`（根 = `BA Test Root CA`）** | **TLS 通过**，01:34:52 `GET /api/state` 200 |

`report/06:653-659` 的结论是明确的：

> `curl --cacert /data/local/tmp/ba_ca_pem.pem`（= 信任库里那张 BA Test Root CA）→ **000 verify failed**
> ⇒ 服务端当前链的根 ≠ 我们装进信任库的 BA Test Root CA。这解释了「三处 store 全装、PEM/DER 都对、label 对、app 也读得到，TLS 仍 unknown CA」。

⇒ **「用户 CA 不生效」从来没有在「链根正确」的前提下被观测过。**
所以：
- `report/17:124`「系统/用户 CA、`networkSecurityConfig` → **已证伪**」——**结论过宽**，应降级为「未做干净实验」。
- `report/13:92` 把 P1（用户证书实验）标成「进行中 / 尚未出结果」——**这才是准确状态**，而且**至今没有结果**。


两张证书的字节/哈希见下面这段（本轮用本地文件复核，**确证**）；然后是本节的**第 4 个混淆变量**。

**★ 第 4 个混淆变量：用户库那一份是 DER，而 `AndroidCAStore` 的读法只认 PEM**

| 事实 | 证据 |
|---|---|
| 用户库那份 = **819 B DER** | `report/06:305`（sha256 `6F9E7C0B…`，本轮本地复核同值） |
| 系统/APEX 那两份 = **后来现场转的 1164 B PEM** | `report/06:605-607`、`report/21-手机侧执行记录.md:23-24` |
| `KeyStore("AndroidCAStore")` 的后端 conscrypt `TrustedCertificateStore` **读函数只认 PEM**（首行必须是 `-----BEGIN CERTIFICATE-----`，否则抛异常） | `report/20:116-131`（一手源码） |

⇒ **如果 Unity 走 §2.3 的机制 (b)，那份 DER 用户 CA 会被静默跳过**（不报错、不出现、就是"没有"），
而系统库那两份 PEM 会被读到。
⇒ 这可能就是「历史那次用户 CA 看起来无效」的**单点原因**，与「用户库不被信任」是两回事。
⇒ **本实验的铁律：用户证书必须用 PEM 安装**，并在装完后**亲眼看字节**（§4.2 ②）。
同一条机制也解释了为什么 §2.4 的历史窗口里「PEM 进系统库 → 立刻生效、DER 进用户库 → 毫无反应」能同时成立。
（这条与 `_dd1-P2-repack.md:219-223` 独立得出，措辞不同、结论一致。）

```
work\ba\ba_test_root_ca.crt  1164 B  sha256 286F0099C95C86D0E5EDB83CE3C1B7909E9633C6707154C7F48F89FA6916B2EB
                                    = report/21-手机侧执行记录.md:26 记录的 /system/etc/security/cacerts/fd8b2b01.0
work\ba\ba_test_root_ca.der   819 B  sha256 6F9E7C0B40E7F7D2938E990069E585CD73DB4B3C0B0806E13B11A312DF13411D
                                    = report/06:305 记录的用户库文件（同一张证书的 DER）
subject=CN=BA Test Root CA, O=BA   subject_hash_old=fd8b2b01   subject_hash=65baadd6
notBefore=Nov 13 16:49:32 2026 GMT  notAfter=Nov 10 16:49:32 2036 GMT
**扩展：无（openssl: "No extensions in certificate"）→ 没有 BasicConstraints CA:TRUE**
```


> ⚠ 最后一行是个**必须记住的坑**：这张 CA **没有 `CA:TRUE`、没有任何 v3 扩展**，
> 而它**实测被客户端接受了**（01:33 之后全链路通过）。所以：
> 「证书缺 basicConstraints」**不能**用来解释实验失败；反过来，也不要因为「它本来就不规范」而改用它做正控——
> 实验请用 §4.1 那张**规范**的 CA（`CA:TRUE critical` + `keyUsage` + SAN 齐备）。

### 2.5 另一条栈（BestHTTP）对 P4 的意义（重要副产品）

`report/22-服务端取证记录.md:24` 记了一条被埋掉的关键观测：

> `gsqc-api`：CH 440 B、带 SNI、ALPN 仅 http/1.1、sigalgs 无异常 → flight ≈2600 → CCS(1) → APP(53)(112)(19)。**握手成功**，之后客户端自己停了。
> ——`report/23:24`（01:25:00，**在 01:33:45 CA 生效之前**）

即：**走 BestHTTP 的那条链路，在我们自签证书还没被信任时就握手成功了**，而且 `report/22-服务端取证记录.md:32` 的 46 条 alert 里
**没有任何一条来自 `gsqc-api`**（全是 state-api ×19、stateqc-api ×17、yostar/tap ×10）。

⇒ **推断·高**：BestHTTP/2 这条栈对我们的自签证书**不做严格校验**（或校验了但不产生 alert）。
⇒ **对 P4 的直接影响**：**真正需要「让客户端信任用户 CA」的只有 libcurl/UnityWebRequest 那一条（`/api/state` + 资源下载）**。
登录链的主体（`/api/account/auth` 等）**可能压根不需要 CA**——这与 `report/23:21` 的「TLS 已通」「卡点在应用层」是自洽的。
⇒ 另外：`/api/state` 的响应由**我们**给，`Servers` 可以给 `http://`（`report/11:313`：默认连接组字面量本身就是 `http://`；
`usesCleartextTraffic=true` 已确证 §1.2），**后续链路可以整层明文**，于是 CA 问题收敛到**唯一一个请求**。

### 2.6 §2 小结

```
用户 CA 有没有可能被采纳？
  ├─ libcurl/UnityTLS（state、下载） → **可能**（走 (b) 的话），**不可能**（走 (a) 的话）→ 未知，必须实验
  └─ BestHTTP（account/auth 等）      → 观测上：**不需要**被采纳（自签也过）→ 推断·高
```

---

## 3. 非 root 注入/提权候选（Shizuku / adb / 沙盒 / LSPatch）逐个判定

先给一条**贯穿全表**的事实：P4 需要两件互相独立的事，**别混在一起判**：

- **T（信任）**：客户端接受「根只在用户库」的证书 → 只能靠 §4 的实验回答；
- **R（重定向）**：把 `state-api:443` 的流量引到我们这边 → **有多种免 root 做法**（代理 / per-app VPN），不必 DNAT。

`report/90:264`「免 root 分发不可行」的推理是「DNAT（需 root）+ 系统 CA（需 root）」，**R 这一半的前提已经过时**
（见 #6、#7）。真正卡免 root 的是 T。

| # | 方案 | 需要 root？ | 对 P4 有作用吗 | 判定 | 依据 / 置信度 |
|---|---|---|---|---|---|
| 1 | **系统设置安装用户 CA**（设置→安全→加密凭据→安装证书→CA） | **否** | 这就是 P4 的前置 | **可用** | 该机用户库已有第三方 CA `c8750f0d.0`（`CN=mitmproxy`，825 B DER）= 这条路在这台机器上成立（**确证**，`report/06:304`） |
| 2 | `adb shell` 里跑 `iptables`（DNAT） | 免 root 但需开 USB 调试 | 只用 R | **不可行**。`shell`(uid 2000) 没有 `CAP_NET_ADMIN`，`iptables` 会报 `Permission denied (you must be root)` | **推断·高**（AOSP capability 分配） |
| 3 | `adb shell` 直接往 `/apex/.../cacerts` 或 `/system/.../cacerts` 写文件 | 免 root | 相当于装系统 CA | **不可行**：DAC（root:root 644 / 目录 root 所有）+ SELinux `shell_data_file` 进不去 `system_file` | **推断·高**（`report/20:205-218` 的 label 机制） |
| 4 | `pm install-ca` / `pm install-existing` 装 CA | — | — | **不存在该能力**：`pm install-existing` 是「重装已安装的应用」，与 CA 无关；Android 没有 shell 级 CA 安装子命令（只有设置 UI / 特权应用） | **推断·高**（未在项目文档中出现过；如要 100% 确认，`adb shell pm help \| grep -i ca` 一条命令即可） |
| 5 | `adb root`（Android 14+） | — | 拿到 root 后可用 #11 | **零售机不可行**：`adbd` 只允许 `userdebug/eng` 提权，成品机报 `adbd cannot run as root in production builds` | **确证**（Android 平台规则；本机是 PLR110 成品机 + KernelSU，不走这条路） |
| 6 | **`settings put global http_proxy <PC>:7890`**（或手动填 Wi-Fi 代理） | **否**（`shell` 有 `WRITE_SECURE_SETTINGS`；手动填更是零权限） | 解决 **R** | **可用，且是本轮首选**。项目已有正证据：Reqable「系统代理」模式下**抓到了 `UnityWebRequest` 的请求** | **正证据·推断高**：`report/101:246`「抓到 `okhttp` 与 `UnityWebRequest` 的请求，说明这两条栈吃代理」；`report/12:276` 把 `settings put global http_proxy` 列为最简方案 |
| 7 | **per-app VPN（`VpnService` + `addAllowedApplication`）** | **否** | 解决 **R** | **可用**（工程量大：写 TUN + 转 TCP） | **确证方向**：`report/12:301-322`（列出 TunProxy/FlowTrans/proxydroid 等现成实现）；`report/12:319` 明确指出「VPN 只改路由，不改 TLS 信任」——即它只解决 R |
| 8 | **Shizuku** | 免 root（`adb` 授权一次） | — | **对 P4 无帮助**。Shizuku 把 `app_process` 跑在 `shell`(2000) 身份下，能调的是 **ADB 权限面**：`pm` / `am` / `settings` / `appops` / `cmd` / `content`。它**不是** root、**没有** `CAP_NET_ADMIN`、**不能**写 `/system` `/apex` ⇒ 既不能 DNAT，也不能装系统 CA | **推断·高**（Shizuku 的定位就是「ADB 级权限」） |
| 9 | Magisk / KernelSU / APatch 模块（AlwaysTrustUserCerts、MoveCertificate、System CA Manager…） | **要** | 系统 CA 注入（已验证可用） | **不是免 root**（现状就是用这类能力） | **确证**：`report/20:548-576`；`report/20:579-591` 还提醒 KSU 没装 metamodule 时挂载类模块全废 |
| 10 | **LSPatch**（免 root Xposed） | 免 root，但**必须重打包 + 重签** | hook 的是 **Java 框架类**（`javax.net.ssl.*` / `android.security.net.config.*`），对 **native libcurl/UnityTLS 无效**；且重签直接撞 ACE 的签名面 | **不可行（对本目标）** | **推断·高**：`report/18:213`、`report/20:568`（UserCABridge 那类模块改的是「框架默认 trust 配置」＝ Java 侧）；`report/DEADENDS.md:340-344`（重签撞 ACE）；项目已实测改 dex 会卡启动界面（`report/18:60`） |
| 11 | VirtualXposed / 太极 / VirtualApp 双开沙盒 | 免 root | guest 进程的 `networkSecurityConfig` 会变成**宿主 App** 的（宿主若声明 `src="user"` 可影响 Java 侧）；但 **native 栈不受 config 约束**，Unity 走的是自己的枚举 | **基本不可行**（对 native 无效 + Android 17 兼容性极差 + ACE 检测） | **推断·低置信（未验）**：机制理由见 §2.3；A17(SDK 37) 上 VirtualApp 类容器依赖大量隐藏 API，风险未评估 |
| 12 | Island / 工作资料（work profile） | 免 root | 只换了 **user 分区**（另一个 profile 的 `/data/misc/user/<id>/cacerts-added`）；`targetSdk>=24` 的门槛**不变** | **无帮助** | **确证（机制）**：`report/20:170`；用户 CA 的 profile 归属不改变 NetworkSecurityConfig 的默认策略 |
| 13 | 重打包改 `AndroidManifest` / 那个 `0x7f120001` 的 AXML（原包里是混淆名，重建包里是 `res/xml/http.xml`），在 `base-config` 里加 `<trust-anchors><certificates src="system"/><certificates src="user"/></trust-anchors>` | 免 root，但**重签** | 只有机制 (a) 有效；机制 (b)/(c) 下无关（本来就能/本来就不看 NSC） | **技术可行，留作 Plan B** | 改动面：`res/*` + `resources.arsc` 实测不被 ACE 杀（`report/18:213`、`report/23:84`）；重签风险：`_dd1-P2-repack.md:247-250` 记录三次重签（E30/E38/E42）**都跑起来了**，但 `sourceDir`+签名上报是**未量化的账号风险**；注意 `report/DEADENDS.md:340-344` 的「本 APK 没有该属性」要按 §1.2 改写 |
| 14 | 换一张「公信 CA」签的证书（Let's Encrypt 等） | 免 root | 若能给 `state-api.bluearchive-cn.com` 签出公信证书，T 就直接消失 | **不可行**：我们对这个域名没有控制权，无法过 ACME 校验 | **确证**（基本常识；仅当我们自己的域名出现在 `Servers` 里时才适用，见 #15） |
| 15 | 把 `state` 响应的 `Servers` 指到**我们自有域名**（真证书） | 免 root | 只解决 state **之后**的请求；`state` 本身仍要过 T | **部分有效**（杠杆很大，见 §2.5） | **推断·高**：`report/101:277` 显示官方 `Servers` 就是两个 `https://.../api/`；我们可给 `http://` |
| 16 | 改**路由器 / NAT 网关**（DNS 覆盖 + 端口重定向） | 手机免 root（但要网络设备权限） | 解决 **R** | **可用**（重定向候选 3） | **推断**：与 #6/#7 等价，代价是换设备权限 |
| 17 | Frida（`frida-server` 或 gadget） | `frida-server` 要 root；gadget 要重打包 | 直接绕 TLS 校验 | **不是免 root**（或退化成 #13 的重签风险） | `report/18:60`、`report/23:82`（KSU + A15/16 spawn 会 timed out 甚至 zygote64 SIGABRT） |

### 3.1 对「Shizuku / ADB 权限」这条的正面回答（任务点名）

- **`adb shell` 能不能做 DNAT？不能。** `iptables` 需要 `CAP_NET_ADMIN`，`shell` 域没有；拿到的就是
  `iptables: Permission denied (you must be root)`。**（推断·高）**
- **`adb shell settings put` 能不能改？能**，但只能改设置类（`http_proxy`、`private_dns_*`、`appops`…），
  并且 `http_proxy` **恰好就是免 root 的重定向手段**（#6）。**（推断·高 + 项目正证据 `report/101:246`）**
- **`pm install-ca` 存在吗？不存在。** Android 没有任何 shell 级「安装 CA」子命令；
  用户 CA 只能由设置 UI（或 `system_server` 的特权调用）装。**（推断·高）**
- **`adb shell` 能把 CA 推进系统 CA 目录吗？不能。** 目录/文件属 root、label `system_security_cacerts_file`，
  `shell` 既无 DAC 也无 SELinux 权限。**（推断·高）**
- **`adb root`？** 只有 `userdebug/eng` 可行；成品机 `adbd cannot run as root in production builds`。**（确证）**
- ⇒ **结论：Shizuku/ADB 这条线的价值在「重定向」，不在「装 CA」。** 把这两件事分开看，
  免 root 就不再是「不可能」，而是「取决于 §4 的实验结果」。

---

## 4. 免 root 实验设计（可直接照做）

> 目标只有一个：**回答「客户端的 `trusted_ca` 里到底有没有用户库那一半」**。
> 设计原则：**一次只改一个变量**；T（信任）与 R（重定向）分别取证；**先拿到"客户端确实连到我们"的证据，再谈信任**。

### 4.0 前提

| 项 | 要求 | 说明 |
|---|---|---|
| 设备 | 任意 Android（**可以完全不 root**） | 测试机建议用现在这台（已 KSU，便于做 §4.3 正控）；纯用户视角则用另一台成品机更有说服力 |
| 锁屏凭据 | **必须已设 PIN/图案/密码** | Android 安装用户 CA 的前置（系统要求 secure lock screen）**（推断·高）** |
| 电脑 | 与手机**同一 Wi-Fi**，能起 Python 3 服务 | 起 TLS 终止代理；不需要公网 |
| 工具 | `openssl`（PC）、`python` 3、可选 `adb`（能开 USB 调试） | 不用 adb 也能做：手动强停 + 手动点屏 |
| 代码 | `work\ba\noroot\p4_proxy.py`（本轮新增）、`BA_probe_kit_v1.zip` 里的 `pc/state_gw.py`（项目已验证的 E4 工具） | 见 §4.6 资产复用 |
| 禁止 | 不要同时换证书链、不要同时挂 VPN、不要 `setenforce 0` | 任一条都会让判据失效 |

### 4.1 步骤 0：准备证书（10 分钟，一次性）

**优先复用项目已有的规范证书**（`CA:TRUE critical` + `keyUsage` + 完整 SAN，且**私钥在本地**，可以随时重签）。
它们在 `kit\state_kit_v1\pc\certs\`（**不在** `BA_probe_kit_v1.zip` 里 —— 那个 zip 只带 `make_certs.ps1`，证书要跑脚本现生成）：

```
kit\state_kit_v1\pc\certs\ca.crt    1250 B   subject=CN=BA State Gateway Root CA, O=BA State Gateway
                                             subject_hash_old = 4cc9cfb3        ← 本轮 openssl 实测
                                             BasicConstraints: critical, CA:TRUE ← 本轮 openssl 实测
kit\state_kit_v1\pc\certs\ca.key    1732 B   （私钥，别外传）
kit\state_kit_v1\pc\certs\leaf.crt  1480 B   issuer=BA State Gateway Root CA
                                             SAN: *.bluearchive-cn.com, bluearchive-cn.com,
                                                  *.yostar.cn, yostar.cn, *.yostar.net, *.yostar.com,
                                                  *.aliyuncs.com, *.adjust.cn, IP:127.0.0.1
                                             notBefore=Nov 13 16:18:33 2026 GMT  notAfter=Feb 15 16:18:33 2029 GMT
kit\state_kit_v1\pc\certs\leaf.key  1732 B
```

自检（必须做，避免「证书本身有问题」变成混淆变量）。以下命令已在**本轮实跑通过**（工作区根为 cwd）：

```powershell
openssl verify -CAfile kit\state_kit_v1\pc\certs\ca.crt kit\state_kit_v1\pc\certs\leaf.crt
#   → kit\state_kit_v1\pc\certs\leaf.crt: OK
openssl x509 -in kit\state_kit_v1\pc\certs\ca.crt -noout -subject -dates -subject_hash_old
#   → subject=CN=BA State Gateway Root CA, O=BA State Gateway … / 4cc9cfb3
openssl x509 -in kit\state_kit_v1\pc\certs\ca.crt -noout -text | Select-String "CA:TRUE"
openssl x509 -in kit\state_kit_v1\pc\certs\leaf.crt -noout -issuer -dates -ext subjectAltName
#   → 与上表一致
# 可选：确认 leaf.key 与 leaf.crt 是同一对（两条 sha256 必须相同）
(openssl x509 -in kit\state_kit_v1\pc\certs\leaf.crt -noout -pubkey | openssl dgst -sha256)
(openssl pkey -in kit\state_kit_v1\pc\certs\leaf.key -pubout        | openssl dgst -sha256)
```

> 期望 `subject_hash_old = 4cc9cfb3`。这个值**只用于**给系统库里的文件命名（§4.3）；
> 用户库由设置 UI 自己算名字，不用我们操心。
> ⚠ 不要用 `work\ba\ba_test_root_ca.crt`（`CN=BA Test Root CA`）：它**没有 `CA:TRUE`**（本轮 openssl 实测），
> 而且它的私钥不在本地（只能由服务器签叶子），会把变量搞混。
> 想换一张全新 CA：跑 `work\ba\noroot\_kit\BA_probe_kit_v1\pc\make_certs.ps1`（会在**它自己的目录下**生成 `certs\`，
> CN 变成 `CN=*.bluearchive-cn.com / O=BA Prober`，CA 名叫 `BA Prober Root CA`）——换了就**必须重新算 hash_old**。

### 4.2 步骤 1～6：主实验 E-P4-1（零 root）

#### ① 先证明「重定向」这一半成立（60 秒，只观察不改任何东西）

PC：

```powershell
cd C:\Users\su\Desktop\大肥鱼项目\BAServer        # 以下命令全部以工作区根为 cwd
python work\ba\noroot\p4_proxy.py --mode proxy --port 7890 `
    --cert kit\state_kit_v1\pc\certs\leaf.crt --key kit\state_kit_v1\pc\certs\leaf.key `
    --pass-others --mitm "state-api|stateqc-api|gsqc-api|gs-api"
```

手机：`设置 → WLAN → 长按当前网络 → 修改网络 → 高级选项 → 代理 = 手动 → 主机名 = <PC 的局域网 IP>，端口 = 7890 → 保存`
（用 adb 也行：`adb shell settings put global http_proxy <PC_IP>:7890`）

启动游戏（**先别装 CA**，这一遍只看连接）：

- PC 控制台出现 `P4-CONNECT state-api...:443` 或 `P4-CONNECT gsqc-api...:443`
  → **R 成立（零 root 重定向可用）**，继续 ②。
- 60 秒内**一条 `P4-CONNECT` 都没有** → 客户端不吃系统代理 → 本实验的 R 半边改用
  **E-P4-2（DNAT，需 root）**；T 的结论不受影响，只是不能再声称「全链路零 root」。

> 这一遍之所以必须做：`--pass-others` 会让不匹配的主机原样隧道出去，所以 SDK/公告/ACE 不会被打断，
> 游戏能正常走到 state 那一跳（否则「SDK 初始化失败导致压根不发 state」会伪装成「证书失败」）。

#### ② 装用户 CA（零 root）

```powershell
adb push kit\state_kit_v1\pc\certs\ca.crt /sdcard/Download/ba_prober_ca.crt
# 或手动把 ca.crt 拷进手机 Download 目录，改名 ba_prober_ca.crt
```

手机：`设置 → 安全 → 更多安全设置 → 加密与凭据 → 安装证书 → CA 证书 → 仍然安装 → 选 ba_prober_ca.crt`
（ColorOS/Android 17 的路径文字可能略有差异，关键词是「加密与凭据 / 安装证书 / CA 证书」。）

**验证已装（零 root 也可验）**：`设置 → 加密与凭据 → 信任的凭据 → 「用户」标签页` 里应出现
**`BA State Gateway Root CA`**。（有 root 时的等价验证：`su -c 'ls -l /data/misc/user/0/cacerts-added/'`）

> 格式不必纠结：`CertificateFactory` PEM/DER 通吃（`report/20:78-93`，一手 AOSP 源码）；
> 扩展名用 `.crt`/`.pem` 最稳。

**★ 但装完必须再看一眼字节（PEM 还是 DER）** —— 见 §2.4 的「第 4 个混淆变量」：

```sh
su -c 'D=/data/misc/user/0/cacerts-added; ls -l $D; for f in $D/*; do echo "== $f"; head -c 30 $f; echo; done'
# 期望：-----BEGIN CERTIFICATE-----        ← PEM，判据有效
# 若看到  0\x82 之类的二进制               ← DER，会被 TrustedCertificateStore 静默跳过，判据无效
```

若落成 **DER**（设置 UI 有可能按 DER 落盘；本项目用户库那两个历史文件都是 DER 尺寸 819/825 B），
本轮判据对「DER 用户 CA」**不成立**，必须换成 PEM 后重跑 ③④⑤：

1. **（有 root，最稳）** 覆盖进去，名字用 `hash_old`：
   ```sh
   adb push kit\state_kit_v1\pc\certs\ca.crt /data/local/tmp/4cc9cfb3.0
   ```
   ```sh
   su -c 'D=/data/misc/user/0/cacerts-added; cp -f /data/local/tmp/4cc9cfb3.0 $D/4cc9cfb3.0; \
          chown system:system $D/4cc9cfb3.0; chmod 644 $D/4cc9cfb3.0; \
          chcon u:object_r:misc_user_data_file:s0 $D/4cc9cfb3.0; head -c 30 $D/4cc9cfb3.0'
   ```
2. **（无 root）** 换一个「导入时按 PEM 落盘」的安装器（mitmproxy / HTTP Toolkit 的 CA 安装向导），
   或者接受「本次只测了 DER」这个限制并写进结论（⇒ 结论只能算「不完整」）。

#### ③ 切到 MITM 模式（同一条命令，只换 `--servers`）

```powershell
# 停掉 ①，用假 state 让客户端能往下走；Servers 用 http:// 让后续链路明文，
# 这样唯一需要 TLS 的就只剩 state / 网关入口
python work\ba\noroot\p4_proxy.py --mode proxy --port 7890 `
    --cert kit\state_kit_v1\pc\certs\leaf.crt --key kit\state_kit_v1\pc\certs\leaf.key `
    --pass-others --mitm "state-api|stateqc-api|gsqc-api|gs-api" `
    --servers "http://<PC 的局域网 IP>:5000/api/" --state 0
```

#### ④ 冷启动（**必须**，这一步做错整个实验作废）

```powershell
adb logcat -c
adb shell am force-stop com.RoamingStar.BlueArchive
adb logcat -v time > p4_logcat.txt      # 另开一个窗口挂着
adb shell monkey -p com.RoamingStar.BlueArchive -c android.intent.category.LAUNCHER 1
# 没有 adb：设置 → 应用 → 碧蓝档案 → 强行停止，然后手动点图标
```

为什么必须冷启：`SystemCertificateSource` 是**进程内单例**（`report/20:487-503`，一手源码），
Unity 侧的 `trusted_ca` 也是进程内构建的 ⇒ 已在跑的进程**永远看不到新 CA**。

#### ⑤ 用户手动点一次屏（**本实验不允许脚本点击**）

#### ⑥ 同时收两侧证据

```powershell
# A) 代理侧（判据本体）
Get-Content work\ba\noroot\p4logs\p4_*.log -Tail 80
# B) 客户端侧（对照）
Select-String -Path p4_logcat.txt -Pattern "UnityTls|Curl error|CERT|X509|Trust|ssl|SSL" |
    Select-Object -First 40
```

### 4.3 正控（**只在 ② 得到「拒绝」时才必须做**）

把**同一张** `ca.crt` 装进**系统库**，重跑 ③④⑤，必须得到「接受」；否则说明我们自己的配置有问题（链/SAN/时间/ALPN），
本轮结论作废。

```powershell
adb push kit\state_kit_v1\pc\certs\ca.crt /data/local/tmp/4cc9cfb3.0
```

```sh
# 手机上（root）
D=/apex/com.android.conscrypt/cacerts
cp -f /data/local/tmp/4cc9cfb3.0 $D/4cc9cfb3.0
chown 0:0 $D/4cc9cfb3.0; chmod 644 $D/4cc9cfb3.0
chcon u:object_r:system_security_cacerts_file:s0 $D/4cc9cfb3.0    # 若失败用 --reference 同目录原厂文件
ls -lZ $D/4cc9cfb3.0

# ★ 必须从 App 自己的 mount namespace 里验证（自己 ns 里的成功是自我安慰）
P=$(pidof com.RoamingStar.BlueArchive)
nsenter --mount=/proc/$P/ns/mnt -- /system/bin/ls -lZ $D/ | grep 4cc9cfb3
nsenter --mount=/proc/$P/ns/mnt -- /system/bin/sh -c "head -c 30 $D/4cc9cfb3.0"; echo
```

- 若 App ns 里**看不到** → 按 `report/20:343-430`（或 `report/21-决策日志-CA路线攻坚.md:57-68`）往 **zygote64/zygote 的 mount ns** 做
  `mount --rbind`，再补已运行进程，然后冷启。
- 若 App ns 里**看得到**却仍拒绝 → 是 §2.3 的 (a) 机制在起作用（config 决定），**这正是 P4 的死刑判决**。

> 这台机器上「直接 cp 进 tmpfs + 正确 label 就生效」是**实测成立**的（`report/06:270-277,636-639`），
> 所以正控成本很低；但**必须**保留「App ns 里 ls 得到」这条证据，否则无法区分「没装进去」与「不采纳」。

### 4.4 备选：E-P4-2（DNAT 变体，需 root；用于把 T 与 R 解耦）

当 ① 拿不到 `P4-CONNECT`（客户端不吃代理）时用：

```sh
# 1) 重启以清掉 tmpfs 里的系统 CA（report/06:270-271：两处 cacerts 都是 tmpfs，重启即失效）
#    重启后确认系统库里没有我们的 CA：
ls /apex/com.android.conscrypt/cacerts | grep -E "4cc9cfb3|fd8b2b01"   # 期望空
ls /system/etc/security/cacerts       | grep -E "4cc9cfb3|fd8b2b01"   # 期望空
ls -l /data/misc/user/0/cacerts-added/                                  # 期望有 4cc9cfb3.0（② 装的）

# 2) 只把 state/网关入口 443 劫到 PC（按 uid，别全劫，否则 SDK 段一起断）
iptables -t nat -I OUTPUT -p tcp -m owner --uid-owner 10576 --dport 443 \
    -j DNAT --to-destination <PC_IP>:443
iptables -t nat -L OUTPUT -n -v | head

# 3) PC 侧换成直连模式（没有 CONNECT，用 SNI 判主机）
python work\ba\noroot\p4_proxy.py --mode direct --port 443 `
    --cert kit\state_kit_v1\pc\certs\leaf.crt --key kit\state_kit_v1\pc\certs\leaf.key

# 4) 冷启 + 点屏 + 收证据（同 4.2 ④⑤⑥）
```

回滚：`iptables -t nat -D OUTPUT -p tcp -m owner --uid-owner 10576 --dport 443 -j DNAT --to-destination <PC_IP>:443`；
系统库里的 `4cc9cfb3.0` 直接 `rm`（tmpfs，重启也会没）。

### 4.5 反例排除清单（11 条，逐条都要能自证）

| # | 会被误判成「用户 CA 不被信任」的原因 | 怎么排除 |
|---|---|---|
| 1 | 服务端**链不全/根不对**（历史真凶） | 正控（§4.3）必须「接受」；`openssl verify -CAfile ca.crt leaf.crt` = OK |
| 2 | SAN 不覆盖 SNI 主机 | 上表那张 leaf 的 SAN 已含 `*.bluearchive-cn.com`；`openssl x509 -ext subjectAltName` 亲眼看 |
| 3 | 证书/系统时间不对 | `fsclk`/`date` 与 leaf 的 `notBefore/notAfter` 对照 |
| 4 | **进程缓存**（没冷启） | 每次判定前 `am force-stop` + 确认新 pid（`adb shell pidof`） |
| 5 | 文件命名 hash 不对（系统库按 `<hash_old>.0`） | `openssl x509 -subject_hash_old` 必须 == 文件名前缀 |
| 6 | SELinux label / 权限错（系统库） | `ls -lZ`，label 必须是 `u:object_r:system_security_cacerts_file:s0`、`root:root 644` |
| 7 | **文件根本不在 App 的 mount ns 里** | `nsenter --mount=/proc/<app pid>/ns/mnt -- ls -lZ <dir>`（自己 ns 里的 ls 无效） |
| 8 | 客户端**没连到我们**（重定向失败） | 判据只认两侧同时有：`P4-CONNECT` + 服务端 accept；只有一侧 = 无效 |
| 9 | VPN/Clash 抢了路由 | `dumpsys connectivity \| grep -i vpn`、`ip rule`、`ls /sys/class/net \| grep tun`（本项目踩过：`report/06:192-201`、`report/21-手机侧执行记录.md:1007-1023`） |
| 10 | **ALPN 不匹配**伪装成证书失败 | `p4_proxy.py` 只 offer `http/1.1`；state 的 CH 本就是 `ALPN 仅 http/1.1`（`report/22-服务端取证记录.md:24`）。若 `P4-TLS-REJECT` 的 reason 是 `no application protocol`，那是 ALPN 不是信任 |
| 11 | **用户 CA 是 DER 而不是 PEM**（`AndroidCAStore`/`TrustedCertificateStore` 只认 PEM，静默跳过） | §4.2 ② 的 `head -c 30` 必须看到 `-----BEGIN CERTIFICATE-----`；是 DER 就先换成 PEM 再判定（§2.4 第 4 个混淆变量） |

额外两条纪律（项目用血换的）：
- **判 TLS 通过只认「ServerFlight 之后有应用数据/HTTP 请求」**（`report/23:90-92` 的红线），不要看 `access_log`/`error_log`；
- **不要把 `access_denied(49)` 当成「证书不受信」的唯一解释**（`report/21-决策日志-CA路线攻坚.md:26-31`、`report/INDEX.md:503` A-10 已把这条降级）。

### 4.6 资产复用（现成能用的都在这）

| 资产 | 位置 | 怎么用 |
|---|---|---|
| **规范 CA + leaf（含私钥）** | `kit\state_kit_v1\pc\certs\{ca.crt,ca.key,leaf.crt,leaf.key}`（**不是**从 zip 解出的；zip 里只有生成脚本） | 本实验的证书，`hash_old=4cc9cfb3`、`CA:TRUE`、SAN 齐；`openssl verify` 与「key↔cert 同一对」本轮都实测通过 |
| **TLS 终止代理（项目已验证）** | `work\ba\noroot\_kit\BA_probe_kit_v1\pc\state_gw.py`（`--mode logonly/passthrough/tls`） | `state_gw.py` 的 `TLS-OK` / `TLS-REJECT` 就是 P4 的判据；`logonly` 是 20 秒域名harvest |
| **本轮新增代理** | `work\ba\noroot\p4_proxy.py` | 比 `state_gw.py` 多三件事：`--pass-others`（只 MITM 目标主机，其余隧道，避免 SDK 段被打断）、`--mode direct`（配 DNAT，用 SNI 判主机）、退出时输出 `P4-VERDICT` + JSON 汇总 |
| 生成证书脚本 | `work\ba\noroot\_kit\BA_probe_kit_v1\pc\make_certs.ps1` | 需要换 CN/SAN/年限时用；注意它会**优先复用**已有 `certs\ca.key` |
| 只读采集 | `work\ba\noroot\_kit\BA_probe_kit_v1\phone\00_collect.sh` | 包信息 / so 哈希 / Hosts 十六进制 / ACE 记账 / maps / logcat 一次抓齐 |
| 纯观测网络 | `work\ba\noroot\_kit\BA_probe_kit_v1\phone\02_net_watch.sh` | 记录游戏连了哪些 IP:端口（不改任何东西），用于交叉验证 `P4-CONNECT` |
| 生产 CA（**别用于实验**） | `work\ba\ba_test_root_ca.crt` / `.der` | 无 `CA:TRUE`；私钥不在本地；只适合当「已知可被接受的参照物」 |
| 服务端 MITM vhost | `work\ba\ba_mitm.conf` | `listen 443 ssl` + `proxy_pass 127.0.0.1:5000`；实验里我们**不**用它（会引入 nginx/链/ALPN 三个额外变量） |
| logcat 器材 | `report/40-logcat取证方案.md`（`kit/logcat_kit/*`） | 三组对照 + `-b crash` + 按 pid 限定；Unity 的 tag 就是 `Unity`（`report/40:35-45`） |
| AXML 解析器 | `work\ba\noroot\_dump_axml.py` | 复核 manifest / `res/xml/*.xml` 用（§1 就是它的产物） |

---

## 5. 实验判据与解读表

### 5.1 判据链（顺序不能乱）

```
S0 代理侧有 P4-CONNECT <目标主机>:443        ← 先证明"连到我们了"（R）
        │  没有 → 不是信任问题，是重定向问题 → 换 E-P4-2 / per-app VPN
        ▼
S1 代理侧出现 P4-TLS-OK 或 P4-TLS-REJECT    ← 客户端确实发了 ClientHello 并做了判断
        │  都没有（连上就断） → 查 ALPN / 时间 / 证书链
        ▼
S2 P4-TLS-OK  → 客户端【接受】了「根只在用户库」的证书 ⇒ 用户 CA 在 trusted_ca 里
   P4-TLS-REJECT alert=<reason> → 客户端【拒绝】 ⇒ 用户 CA 不在 trusted_ca 里
        ▼
S3 logcat 交叉验证：
   - 拒绝时应有 Curl error 60 / UnityTls error code 7（对应 alert 46/48/49 一类）
   - 接受时应**没有**这两行，且有 P4-REQ <host> GET /api/state
```

### 5.2 解读表（结果 → 结论 → 下一步）

| # | 观察到的现象 | 结论 | 置信度 | 下一步 |
|---|---|---|---|---|
| **A** | `P4-CONNECT` 有；`P4-TLS-OK state-api` + `P4-REQ ... GET /api/state`；logcat 无 `Curl error 60` | **用户 CA 被采纳**。P4 的 T 半边**成立**，机制是 §2.3 (b)（枚举 `AndroidCAStore`/用户库），与 app 的 `@xml/http` 无关 | **确证（对该客户端、该主机）** | P4 = **可行** → 转「免 root 全链路」工程：重定向固化为 per-app VPN 或「PC 常开代理」；把 `Servers` 给 `http://` 以避开后续 TLS |
| **B** | `P4-CONNECT` 有；`P4-TLS-REJECT state-api alert=unknown ca / certificate unknown / access denied`；logcat 有 `Curl error 60 / UnityTls error code 7` | **用户 CA 未被采纳**。机制是 §2.3 (a)：`TrustManagerFactory(null)` → `NetworkSecurityConfig` → app 的 `@xml/http` 只给系统 CA。**前置检查：用户库那份必须是 PEM**（DER 会因格式被跳过，见 §2.4），否则本条只判到「DER 无效」 | **确证**（但**必须先过正控 + PEM 检查**） | 先做 §4.3 正控：<br>· 正控「接受」→ P4 = **不可行**，免 root 只剩 §3 的 #13（重签改 xml，撞 ACE）或换标的<br>· 正控也「拒绝」→ 本轮作废，修证书配置（链/SAN/时间/ALPN）后重来 |
| **C** | 有的主机 `TLS-OK`、有的 `TLS-REJECT`（同一轮里） | **两条栈行为不同**（§2.1）：说明其中一条的 `trusted_ca` 含用户库、另一条不含 | **确证（现象）** | 分开记账：只要**需要 CA 的那条**（`/api/state`，libcurl）拿到 OK，P4 就够用了；把解析出来的 `Servers` 改成 `http://` 可以彻底绕开另一条 |
| **D** | 一条 `P4-CONNECT` 都没有（60 秒） | 客户端**不吃系统代理**；这是**重定向**失败，与信任无关 | **确证** | 换 E-P4-2（DNAT，需 root）或 per-app VPN（零 root，工程量大）；T 的判定照旧 |
| **E** | 有 `P4-CONNECT`，但既无 `TLS-OK` 也无 `TLS-REJECT`（连接秒断） | 客户端连上但没完成 ClientHello，或我们 accept 后读超时 | **推断** | 查：PC 防火墙、`--mitm` 正则是否匹配到该主机、`P4-HTTP` 是否为明文代理请求、`no application protocol`（ALPN） |
| **F** | `P4-TLS-OK` 但客户端**什么都没发**（`P4-EMPTY`），屏幕报网络错 | **信任成立**（握手完成本身就是信任证明），但应用层拒绝/挂住 | **确证（信任）** | 这已经足够判 P4=T 成立；应用层问题另案（本项目当前主线正是应用层，`report/90:20`） |
| **G** | 用户 CA 装了、也在「信任的凭据→用户」里，但 `P4-TLS-REJECT` | 同 B；**附加信息**：证明「装上 ≠ 采纳」，可用来排除「没装上」这一解释 | **确证** | 同上 |

### 5.3 这个实验能不能在**不用 root 的手机**上完成？

**能——而且这是本设计最重要的性质。**

| 环节 | 要不要 root | 说明 |
|---|---|---|
| 重定向（Wi-Fi 代理 / `settings put global http_proxy`） | **不要** | 设置项；adb 的 `shell` 有 `WRITE_SECURE_SETTINGS` |
| 装用户 CA | **不要** | 设置 UI；需已设锁屏凭据 |
| 冷启 / 收 logcat | **不要** | `adb shell am force-stop` + `adb logcat` |
| 读判据（`P4-TLS-OK/REJECT`） | **不要** | 判据在 PC 端的代理日志里 |
| **正控（把同一张 CA 装进系统库）** | **要** | 只在 ② 得到「拒绝」时才必须做 |

⇒ 结论的**非对称性**（务必写进交接）：
- 拿到 **A（接受）** ⇒ 结论**自证**，**不需要**正控、不需要 root，可以直接判定 P4 可行；
- 拿到 **B（拒绝）** ⇒ 必须做正控才能排除「我们自己配错了」，而正控要 root。

**「如果必须 root 才能做这个实验，说明什么？」**
说明我们把 `T（信任）` 和 `R（重定向）` 绑成了一件必须 root 的事——
而这台项目机器上正好有人这么想过（`report/90:264`）。本设计把它拆开了：**R 有零 root 解**，
于是「必须 root 才能做实验」只剩一种情形，即 **`:443` 劫持被当成唯一的重定向手段**（PC 代理不被客户端采用，D 情形）。
这种情况下真正该记录的不是「实验做不了」，而是「**这个客户端的系统代理支持需要另案验证**」——
它本身就是一个对免 root 路线至关重要的独立结论。

---

## 6. P4 判定：可行 / 不可行 / 需真机验证

### 6.1 判定

> **【需真机验证】**（30 分钟可定，零 root；证据分布为「文档与机制偏可行、静态配置偏不可行」）

| 判据 | 支持「可行」 | 支持「不可行」 |
|---|---|---|
| 文档 | Unity `UUM-73839`：2021.3.48f1 起用户装到设备上的证书会进 `trusted_ca`；本包 2021.3.56f2（`report/12:161-168`） | — |
| 静态配置 | — | app 自己声明 `@xml/http`，`base-config` 只给系统 CA（§1.3）。若走 `TrustManagerFactory(null)`，用户 CA 必被挡 |
| 机制 | `libunity` 有 `X509TrustManager`/`checkServerTrusted` JNI 串（`report/11:226`），说明它确实通过 Java 侧取证书——而 `AndroidCAStore` 这条路径天然含 `user:` 别名（`report/20:116-131`） | 若它用的是 `TrustManagerFactory(null)` 而不是 `AndroidCAStore`，同样的 JNI 串也会出现——两条路径**在静态层面无法区分** |
| 实测 | 系统库里的 CA **确实被采纳**（`report/29:11`、`report/22-服务端取证记录.md`）⇒ 「读设备库」这件事已证 | **用户库从来没有在「链根正确」前提下被测过**（§2.4）⇒ 既无正证也无反证 |

### 6.2 判定为什么只能到这一步（诚实边界）

- **不能判「可行」**：唯一直接证据（UUM-73839）是**引擎级 release note**，不保证本包没被
  `networkSecurityConfig` 或 BestHTTP/自定义 handler 覆盖；而且同一份 note 的另一面是「修之前确实不含用户库」，
  谁也无法从字节上证明 56f2 的 `trusted_ca` 构建逻辑。
- **不能判「不可行」**：历史上那次「用户 CA 失败」已被证明是**服务端链根不匹配**（`report/06:653-659`），
  不是用户库的问题；把它当作 P4 的死刑证据是**用了一个被污染的实验**。
- **能判「不值得现在做重活」**：即使 P4 可行，免 root 还差「重定向」这一环（§3 #6/#7），
  而这一环又有自己的不确定性（D 情形）。⇒ **先做 §4.2 的 60 秒 S0 步骤**，两个不确定性一起收敛。

### 6.3 如果 P4 成立 / 不成立，各自的下一步

| P4 = 可行（A/C） | P4 = 不可行（B + 正控接受） |
|---|---|
| 1. 重定向固化：per-app VPN app（`VpnService`）或「PC 常开代理」两条路线选一 | 1. 只剩两条非 root 路：**重签改 `res/xml/http.xml` 加 `<certificates src="user"/>`**（撞 ACE 签名面，`report/DEADENDS.md:340-344`）或**换标的** |
| 2. `state` 响应里 `Servers` 给 `http://`，后续链路整层明文（`report/11:313` + §1.2 的 `usesCleartextTraffic=true`） | 2. 或者接受「要么 root、要么重签」：本项目的 DNAT + 系统 CA 组合已实测可用（`report/06:277`） |
| 3. 用户侧只需：装用户 CA +（可选）装我们的代理 app | 3. 把 §1.2 的 manifest 事实回写进 `report/06:628` / `DEADENDS.md:343` / `INDEX.md:513`，避免下一个人再被「grep 全空」误导 |

---

## 7. 关键引文摘录（带 文件:行号）

**① libcurl 这条栈的校验来源（确证链的核心）**

> `E Unity : Curl error 60: Cert verify failed. Certificate is not correctly signed by a trusted CA. UnityTls error code: 7`
> `UnityTls error code: 7` = **unknown CA / trust anchor not found**，不是 pinning 拒绝。
> —— `report/06-手机基线恢复.md:643`, `:647`

> `curl --cacert /data/local/tmp/ba_ca_pem.pem`（= 信任库里那张 BA Test Root CA）→ **000 verify failed**
> ⇒ 服务端当前链的根 ≠ 我们装进信任库的 `BA Test Root CA`
> —— `report/06-手机基线恢复.md:653-655`

> | 1 | 系统 CA 不生效 | 重新以 **PEM**、label `u:object_r:system_security_cacerts_file:s0` 装入 | 46 条 `fatal 49` 在 **01:33:45** 后归零 |
> —— `report/29-进度-网关未调用与判据纪律.md:11`

> 46 条 `alert 49` 全部落在 `01:24:58–01:33:45`（CA 生效之前），01:33:45 后归零、01:34:52 同一条链路直接 200
> ⇒ 49 的消失与 CA 生效严格同步，指向 trust store
> —— `report/INDEX.md:503`（A-10）

**② 两条 TLS 栈（UA 分流）**

> `GET /api/state` → `UnityPlayer/2021.3.56f2 (UnityWebRequest/1.0, libcurl/8.10.1-DEV)` → `Http2Message` / `Http2DownloadMessage`
> `POST /api/account/auth` → `BestHTTP/2 v2.4.0` → `Http1Message`
> ⇒ **登录这一枪走的是 `Http1Message`(BestHTTP) 分支，它的响应解码路径与 `/api/state` 不是同一段代码**
> —— `report/41-Account_Auth字段级排查.md:496-499`

> 客户端在 **05:23:05** 发出 `POST /api/account/auth`，`ua=BestHTTP/2 v2.4.0`，`clen=1138`，`reqlen=1531`
> —— `report/63-已证实事实冻结版.md:23`

**③ BestHTTP 那条栈「自签也过」（时间早于 CA 生效）**

> `gsqc-api`：CH 440 B、带 SNI、ALPN 仅 http/1.1、sigalgs 无异常 → flight ≈2600 → CCS(1) → APP(53)(112)(19)。**握手成功**，之后客户端自己停了。
> —— `report/23-主线改判-TLS已通应用层卡点.md:24`（该条时间 `01:25:00`，见 `report/22-服务端取证记录.md:32` 的窗口 01:24:58–01:33:45）

**④ Unity 读哪个库 / UUM-73839**

> `2021.3.48f1 | Fixes | Android | Fix | Fixed issue where user installed certificates directly to an Android device wouldn't show up in the trusted_ca list.`
> ⇒ 这条 release note 的含义非常明确：Unity Android 的 `trusted_ca` 列表 = 系统库 ∪ 用户库。修复前漏了用户库，修复后补上。
> ⇒ 你们的 2021.3.56f2 > 48f1，修复已在。
> —— `report/12-外部资料-证书与网关重定向.md:162`, `:167-168`

> `javax/net/ssl/X509TrustManager` / `checkServerTrusted`（libunity strings L31594 / L31597）
> —— `report/11-客户端静态逆向-网关与证书.md:226`

**⑤ Android 侧的门槛（为什么用户库默认不算）**

> `/data/misc/user/0/cacerts-added/`：**用户证书库**。`targetSdk=33 ≥ 24` 时，默认 config **只收系统 CA**
> —— `report/20-AndroidCA注入深度调研.md:170`

> 唯一会因为 DER 而死的路径：conscrypt `TrustedCertificateStore`（`KeyStore("AndroidCAStore")` 后端）只认 PEM；
> 哪些 App 走这条路：显式 `KeyStore.getInstance("AndroidCAStore")` 自己建 `SSLContext` 的。Unity 默认不走。【推断】
> —— `report/20-AndroidCA注入深度调研.md:116-131`

**⑥ 缓存（为什么必须冷启）**

> `SystemCertificateSource.NoPreloadHolder.INSTANCE` 是**进程内单例**；已在运行的 App 进程**永远不会**读到新 CA
> —— `report/20-AndroidCA注入深度调研.md:487-503`

**⑦ 代理这条重定向路线（免 root 的关键正证据）**

> **A. Reqable 处于「系统代理」模式…** | 抓到 `okhttp` 与 `UnityWebRequest` 的请求，说明这两条栈吃代理
> —— `report/101-官方真服抓包分析.md:246`

> `settings put global http_proxy`（最简单，Unity 2019.3+ 支持）> per-app VPN（最干净，但工程量大）> iptables DNAT（你们已在用）
> —— `report/12-外部资料-证书与网关重定向.md:276`

> **证书怎么办？** 一样要装 CA。VPN 只改路由，不改 TLS 信任。
> —— `report/12-外部资料-证书与网关重定向.md:319`

**⑧ 被本轮推翻/降级的两条旧结论**

> `AndroidManifest.xml` 里 grep 'networkSecurityConfig|cleartext|network' → 全空（无该属性）
> —— `report/06-手机基线恢复.md:628`（**方法错误**：该文件是二进制 AXML，见 §1.1；实测属性存在，`@xml/http`）

> | **C3** | 系统/用户 CA、`networkSecurityConfig` | **已证伪** | — | 无 | Unity 用自己的信任库
> —— `report/17-运行时hook方案评估.md:124`（**结论过宽**：那次实验的失败可被「链根不匹配」完整解释，见 §2.4）

**⑨ `access_denied(49)` 的正确读法（别再拿它当 pinning 证据）**

> 标准证书链失败 alert 是 `46 certificate_unknown` / `42 bad_certificate` / `48 unknown_ca`。`49 access_denied` 出现在握手阶段，更可能是 **App 自身的 TLS 包装层** …
> ⇒ 因此**不得**继续把「客户端拒绝」直接等同于「信任库不认证书」
> —— `report/21-决策日志-CA路线攻坚.md:28-31`

**⑩ 本项目已确认的东西（用来给实验兜底）**

> `/apex/com.android.conscrypt/cacerts` 与 `/system/etc/security/cacerts` 都是 **tmpfs (rw)**，可写（146/147 个 `<hash>.0`）；`iptables -t nat … DNAT` **rc=0 可用**
> —— `report/13-总账-2026-11-14凌晨.md:33`

> 用户库已存在：`/data/misc/user/0/cacerts-added/c8750f0d.0` = `CN=mitmproxy`（825 B，11-13 02:56 装）
> —— `report/06-手机基线恢复.md:304`

---

## 附 A：本轮新增/产生的文件（全部在 `work\ba\noroot\`，只读其它目录）

| 文件 | 作用 |
|---|---|
| `_dd3-P4-userCA.md` | 本报告 |
| `_dump_axml.py` | 二进制 AXML 解析器（解 `<uses-sdk>` / `<application>` 属性 + 字符串池关键字扫描），§1 的全部结论由它产出 |
| `_axml_out.txt` | 对 `work\ba\audit\ba-apk\AndroidManifest.xml` 的解析结果（原包） |
| `_axml_res_apk.txt` | 对 `work\ba\bapatch\res.apk` 内重建版 manifest 的解析结果（交叉对照） |
| `_res_xml_http.bin` / `_res_apk_manifest.bin` | 从 `res.apk` 抽出的 `res/xml/http.xml`(264 B) 与 manifest(50,220 B)，供复核 |
| `p4_proxy.py` | §4 实验用的 TLS 终止代理（`--mode proxy|direct`、`--pass-others`、`P4-TLS-OK/REJECT` 判据行、JSON 汇总）。**只做了 `py_compile` 语法校验，未联网自测**（本次任务禁止联网）；主路径与项目已验证的 `state_gw.py` 同源 |
| `_kit\BA_probe_kit_v1\*` | `BA_probe_kit_v1.zip` 的解包：`pc\state_gw.py`、`pc\make_certs.ps1`、`pc\run.ps1`、`phone\00_collect.sh`、`phone\01_fix_got_slot.sh`、`phone\02_net_watch.sh`、`README.md`。**zip 里没有证书**（证书要跑 `make_certs.ps1` 现生成，或直接用 `kit\state_kit_v1\pc\certs\`） |
| `_dbg_chunks.py` / `_dbg_all.py` | AXML 调试用临时脚本（保留以便复算） |

## 附 B：三条给交接者的最短路径

1. **只想 60 秒知道「免 root 重定向」成不成？** 起 `p4_proxy.py --mode proxy`，Wi-Fi 代理指过去，看有没有 `P4-CONNECT`。
2. **只想 15 分钟知道「用户 CA 成不成」？** 装 `kit\state_kit_v1\pc\certs\ca.crt` 为**用户证书** → 冷启 → 看 `P4-TLS-OK` / `P4-TLS-REJECT`。
3. **只想复算本文 §1 的结论？** `python work\ba\noroot\_dump_axml.py work\ba\audit\ba-apk\AndroidManifest.xml`，看 `<application>` 那 11 个属性。
