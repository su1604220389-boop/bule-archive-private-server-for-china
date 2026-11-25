# DD1: P2 重打包加 networkSecurityConfig 可行性

> 执行者：DD1 子 agent ｜ 时间：2026-11-16 ｜ 工作目录 `C:\Users\su\Desktop\大肥鱼项目\BAServer`
> **边界**：只读既有文件；未连服务器、未连手机、未做任何网络操作；产物只写 `work\ba\noroot\`。
> **口径**：**确证** = 有字节/日志/原文实证；**推断** = 由实证推出但未上机；**未知** = 查不到，不编。
> 行号均为 read 工具行号。

---

## 结论速览

1. **P2 的第一半（"给 manifest 加 `android:networkSecurityConfig`"）根本不需要做——这个属性本来就有。**
   我用二进制 AXML 解析器直接读了官方包的 `AndroidManifest.xml`：`<application android:networkSecurityConfig="@0x7f120001" android:usesCleartextTraffic=true android:extractNativeLibs=true>`；
   再解 `resources.arsc`：`0x7f120001` = `xml/http` → **`res/Dk.xml`，该条目确实在 APK 里**（`zip_listing.txt:24988`）。
   ⇒ `report\DEADENDS.md:343`、`report\INDEX.md:243`/`:513`、`report\06-手机基线恢复.md:628,630` 里"本 APK 没有该属性 / 没有 Dk.xml"是**错的**（它们和自己的审计底稿 `work\ba\audit\ba-java.md:169` 直接矛盾）。
2. **重打包这条路从没被"证明不可行"，是被成本淘汰的**：E30 明确"已签名、已安装、不崩"（`ba-pitfalls.md:163`）；E38（纯填充字节翻转+重签）正常跑 45 s+（`report\02:236`）；E42（换 res+arsc+assets 并重签）"能进主程序、SDK 卡密登录通过"（`ba-pitfalls.md:149-150,155`）。**没有一次失败是"签名变了所以装不上/被杀"**。
3. **ACE 是真的在跑，但它做的是"选择性逐文件哈希 + 结构校验"，不是整包签名校验**：
   钉死 `libunity.so`（4 B→SIGBUS）、`libairisgcore.so`、dex 结构、包名；**不钉** `libil2cpp.so`（代码洞/DT_INIT/原位替换全活）、`res/*`、`resources.arsc`、`assets/*.json`（`ba-pitfalls.md:50-57,171,192,197`）。
   ⇒ "改了 .so 都能跑"这条对 P2 有利，但**不能外推成"签名任意改都安全"**——签名确实被数美/nirvana 现算上报（`anticheat-full.md:92-93`），只是**没有本地杀进程的签名校验**（确证：E38/E42 都跑起来了）。
4. **§4 的核心疑点（NSC 对 libcurl 是否有效）现有证据不足以判定，但风险比预想窄。** 客户端 TLS 校验发生在 **libunity 的 native 栈**（`E Unity : Curl error 60 … UnityTls error code: 7`，`report\06:643`），而 NSC 是 **Java 层**机制（`report\20:145-159`）。三种可能的 trust source 模型里，**只有"纯目录直读"这一种会让 NSC 完全失效**；另两种（NSC 闸门的 TrustManagerFactory / `AndroidCAStore`）都会让"用户 CA 被信任"成立，**后者甚至不需要改包**。
5. **判定：需真机验证（不是不可行，也不是可行）。** 且第一发实验**不需要重打包**——先验"用户 CA（PEM）+ 与我们链同根"是否就够（§5 的 E1），成本 10 分钟；E1 成立则 P2 整个作废、免 root 目标直接达成。

---

## 0. 本次新增的字节级复核（我自己算的，可复现）

| # | 复核项 | 方法 | 结果 | 置信度 |
|---|---|---|---|---|
| R1 | 官方包 `AndroidManifest.xml` 里到底有没有 NSC 属性 | 自写 AXML 解析器（chunk `0x0102` START_ELEMENT → 属性数组），读 `work\ba\audit\ba-apk\AndroidManifest.xml`（50,552 B 二进制 AXML） | `<application>` line 202，**11 个属性**，含 `networkSecurityConfig @0x7f120001`、`usesCleartextTraffic bool True`、`extractNativeLibs bool True` | **确证** |
| R2 | 该资源 id 指向哪个文件 | 自写 `resources.arsc` 解析器（`ResTable_type` type id 18 = `xml`，10 个条目） | `0x7f120000 filepaths→res/oS.xml`；**`0x7f120001 http→res/Dk.xml`**；`0x7f120002 sdk_file_provider_paths→res/XP.xml`；…共 10 条 | **确证** |
| R3 | `res/Dk.xml` 在包里吗 | `work\ba\audit\ba-apk\zip_listing.txt`（41,312 行） | **第 24988 行 = `res/Dk.xml`** | **确证** |
| R4 | jadx 侧交叉验证 | 读 `work\ba\audit\ba-apk\jadx\resources\AndroidManifest.xml` | `:187 extractNativeLibs="true"`、`:188 usesCleartextTraffic="true"`、**`:189 networkSecurityConfig="@xml/http"`**、`:12 minSdk=24`、`:13 targetSdk=33` | **确证** |
| R5 | 是不是官方包（不是某次改包） | 版本 + so sha + 审计底稿 | `versionCode=73 / versionName=3.0.2`；`ba-apk\lib\arm64-v8a\libil2cpp.so` = `5ac1cbe0…` = 纯原厂（`report\57:96`、`report\02:51`）；`ba-java.md:168-169` 独立记过同一属性 | **确证（高）** |

> 复现：把 §0 的两段脚本（AXML / ARSC 解析）存成 `.py` 直接跑即可，只读 `work\ba\audit\ba-apk\`。
> ⚠️ 注意：这个包的 `res/` 是 **AndResGuard 式扁平混淆**（`res/Dk.xml`、`res/oS.xml`…，不是 `res/xml/http.xml`）。
> `report\06:629-630` 把"资源**名字**列表"当成了"res/xml **路径**列表"，于是得出"没有 Dk.xml"——这是那次误判的机理。

---

## 1. 重打包历史与失败现象（证据）

### 1.1 结论：做过，而且成功过不止一次

| 版本 | 改了什么 | 装机后表现 | 出处 | 置信度 |
|---|---|---|---|---|
| **E30** | 资源/文案类 | **"已签名，已安装，不崩"**（2,126,498,053 B） | `ba-pitfalls.md:163` | **确证**（一手安装记录） |
| E32 / E34 | `res/*` + `resources.arsc` | ✅ 正常，能进主程序、文案生效 | `ba-pitfalls.md:55`、`report\01:123` | **确证** |
| E35 | 整库换 `libairisgcore.so` | ❌ `SIGBUS (reason=2 status=7)` | `ba-pitfalls.md:51`、`DEADENDS.md:20-26` | **确证** |
| E36 | `libunity.so` 4 B 补丁 | ❌ `SIGBUS`，无 tombstone | `ba-pitfalls.md:50`、`report\02:237` | **确证** |
| **E38** | **纯填充字节翻转（无注入）** | ✅ **正常启动 45 s+ 存活** | `report\02:236`、`report\57:328` | **确证** |
| E39/E40/E41 | 新增 `classes3.dex`（660 B 空类） | ❌ 卡 Android 启动界面（与 ACE 无关） | `ba-pitfalls.md:52` | **确证** |
| **E42** | 官方资源基线 + **原厂 libunity** + 我们的 `res` + `assets/SDKConfigSettings.json` + 删 `__tpinfo` | ✅ **能进主程序、SDK 卡密登录通过**，停在上游网关拒绝（2,126,782,882 B） | `ba-pitfalls.md:149-150,155` | **确证** |
| E43 | 重编 `classes.dex` | ❌ 卡启动界面 | `ba-pitfalls.md:53` | **确证** |
| E44 | 重编 `classes2.dex`（改一个 `const-string`） | ⚠️ 首次成功，**之后同批全部卡启动界面** | `ba-pitfalls.md:54` | **确证** |
| 现役包 | APK 内嵌 `libil2cpp.so` = `6e2edf5a…`（洞口有桩，非原厂 `5ac1cbe0`） | 设备能跑（多轮实验都在这份上做） | `report\08:132`、`report\57:97,101`、`INDEX.md:506` | **推断（高）**：字节旁证成立，但**没有 `pm install` 原文** |

**⇒ 全项目没有一条"签名换了导致装不上 / 被杀"的记录。** 唯一"装不上"类问题都是**磁盘空间**（`apksigner` 要 ≥2.1 GB 余量，`ba-pitfalls.md:138`；设备只剩 4 GB，`INSTALL_FAILED_INSUFFICIENT_STORAGE`，`ba-pitfalls.md:200`）和 **arsc 对齐**（`ba-pitfalls.md:140`），与签名无关。

### 1.2 那为什么最后不走改 APK？

不是"改包不行"，是**改包买不到想要的东西 + 每次迭代太贵**。按证据强度排序：

| # | 理由 | 证据 | 置信度 |
|---|---|---|---|
| 1 | **能达成的目标有限**：`res/*`、`resources.arsc`、`assets/*.json` 改完，游戏"能进主程序"但**网关仍是官方**（E42 原文），因为登录判定/网关地址在 **il2cpp 代码或 metadata** 里，改它们才动得了行为 | `ba-pitfalls.md:150`、`report\52:436-437` | 确证 |
| 2 | **改代码就得改 APK 内条目**，2.1 GB 全量重打 + 重签 + 卸载重装 | `report\52:541` | 确证 |
| 3 | **重装必改 UID** ⇒ 丢 `/data/data`（卡密登录态）+ 11 GB 资源要 `mv` 回并 `chown -R <新UID>:1078`，一次实验 ≈ 半小时 | `ba-pitfalls.md:203`、`report\52:544-546` | 确证 |
| 4 | **工具链在本机就不稳**：`apksigner` 需 ≥2.1 GB；`zipalign` 对大文件 `Illegal instruction`；arsc 必须首条+STORED+4 字节对齐 | `ba-pitfalls.md:138,140` | 确证 |
| 5 | **原位替换 so 一条 `mv` 就完成**，免去每次重打 2.1 GB | `ba-pitfalls.md:200`、`:197` | 确证 |
| 6 | **ACE 会"记账"**：一次坏改动后，**连之前能跑的 E42 也会被 `kill(SIGBUS)`**，必须删 4 个文件复位 —— 这让每次改包实验的失败代价变成"设备可能被污染" | `ba-pitfalls.md:59-70`（`:61` 为原文） | 确证 |
| 7 | ACE native 拿到 `sourceDir`/`splitSourceDirs`（改包后路径与签名必然变），是**已知但未量化**的风险面 | `anticheat-full.md:111-112`、`:150`（未验证） | 确证（机制）/ 未知（后果） |

⇒ **准确表述**：改 APK 不是 dead end，是**被降级为"最后手段"**（`report\52:549` 原话："闸门 1 没确认之前，不要做任何需要重打包的补丁"）。最终项目主线选了 **改 `libil2cpp.so` 代码洞**（`report\51` / `patch_login_bypass.py` / `report\57:283`），理由是"无 hash pin + 一条 `mv` 就能迭代"。

### 1.3 一个必须一起记住的副作用

装过 E43/E44 之后，**再装回 E42 也会被杀**，必须先删
`files/ace_shell_di.dat`、`files/shell_cache`、`files/ano_tmp`、`files/data/app`（`ba-pitfalls.md:61-69`）。
⇒ P2 真机实验**必须**把这 4 个文件的复位动作写进脚本，否则会把"ACE 记账"误读成"P2 被 ACE 杀了"。

---

## 2. ACE / 完整性校验判定（证据）

### 2.1 ACE 确实在跑（确证）

| 证据 | 内容 | 出处 |
|---|---|---|
| manifest 里的 ACE 组件 | `com.ace.gshell.GP7Worker`(`:198`)、`GP6Service`(`:207`)、`GP7Service`(`:216`)，各自独立 `:process` | `jadx\...\AndroidManifest.xml:198/207/216`（我本次直读） |
| 加载时机 | `AceApplication.attachBaseContextShell → libtprt.initialize()`，**早于 Unity** | `ba-pitfalls.md:77-82` |
| 交给 native 的东西 | `packageName / nativeLibraryDir / **sourceDir** / filesDir` + 反射取 `ApplicationInfo.splitSourceDirs` | `anticheat-full.md:111` |
| 失败形态 | ACE 杀 = `SIGBUS`（`reason=2 status=7`）；`status=9` 是系统回收，**不是 ACE** | `ba-pitfalls.md:102`、`DEADENDS.md:23` |

### 2.2 完整性校验是"选择性"的 —— 关键矩阵

| 对象 | ACE 行为 | 证据 | 置信度 |
|---|---|---|---|
| `libunity.so` | **磁盘哈希钉死**，改 4 B → SIGBUS；对照组换回原厂立刻正常 | `ba-pitfalls.md:50`、`report\02:237`、`DEADENDS.md:15` | 确证 |
| `libairisgcore.so` | 整库替换 → SIGBUS（"NEEDED 干净/无人依赖"不是免死金牌） | `ba-pitfalls.md:51` | 确证 |
| `libtprt.so` | 改任意字节 → `kill(SIGBUS)`；改它自己的校验点无效 | `report\02:116`、`DEADENDS.md:64` | 确证 |
| **`libil2cpp.so`** | **不钉**：填充字节翻转 / 代码洞注入 / 改 `DT_INIT` / root 原位替换 **全部可用** | `ba-pitfalls.md:57,171,192,197`、`report\01:73,133`、`INDEX.md:524` | 确证 |
| **`res/*` + `resources.arsc`** | ✅ 正常（E32/E34/E42） | `ba-pitfalls.md:55`、`report\01:123` | 确证 |
| **`assets/*.json`** | ✅ 正常（SDK 登录链走到我们服务器） | `ba-pitfalls.md:56` | 确证 |
| dex（新增/重编） | ❌ 卡启动界面（**是启动链不接受结构变化，不是 ACE**） | `ba-pitfalls.md:52-54` | 确证 |
| 包名 | 改 → SIGBUS | `DEADENDS.md:44-50`、`ba-pitfalls.md:244` | 确证 |
| `global-metadata.dat` | **未知**，从未实测 | `report\52:532`、`report\30:386` | 未知 |
| **APK 签名 digest** | **没有本地校验**（E38/E42/E30 都是重签包，全都能跑）；但签名 hexdigest 被**数美/nirvana 现算并上报** | `ba-pitfalls.md:163`、`report\02:236`、`anticheat-full.md:92-93` | 本地=确证"无" / 上报=确证 / 服务端判定=推断 |

### 2.3 对 P2 的两条推论

1. **"重签会不会被 ACE 杀"这个担心，现有证据不支持**（E30/E38/E42 三次重签包都跑起来了，其中 E42 走完了整条 SDK 登录）。
   ⇒ 但"能跑"≠"不被标记"：`sourceDir` 与签名 hexdigest 都进了 ACE native / 数美上报面（`anticheat-full.md:112,140`），**账号级风险未量化**。
2. **改 `res/*` 是已实测的最安全改动面**（`report\18:213` 原话："成本最低、风险最小的一条"）。
   而 P2 唯一真正要改的文件 **`res/Dk.xml` 正好落在这个面里**。

---

## 3. 当前 APK 的 networkSecurityConfig 状态

### 3.1 实测状态（确证）

```
<application
    android:label="@string/app_name"
    ...                                    jadx\resources\AndroidManifest.xml:183
    android:name="com.tech.core.TechApplication"      :185
    android:extractNativeLibs="true"                  :187
    android:usesCleartextTraffic="true"               :188
    android:networkSecurityConfig="@xml/http"         :189   ← 已存在
    ...>

二进制侧同一结论（我本次解析）：
<application> line 202, attrCount=11
   networkSecurityConfig  @0x7f120001
   usesCleartextTraffic   bool True
   extractNativeLibs      bool True

resources.arsc:
   0x7f120001  key=http  ->  res/Dk.xml        ← 目标文件
zip_listing.txt:24988  =  res/Dk.xml           ← 文件存在
```

### 3.2 与既有文档的三处冲突（必须更正，否则后面全盘推理都错）

| 文档原话 | 实际 | 性质 |
|---|---|---|
| `report\06-手机基线恢复.md:628`「AndroidManifest.xml 里 grep 'networkSecurityConfig\|cleartext\|network' → 全空」 | **三条全都有**（`:189`/`:188`，且我二进制复核） | **事实错误** |
| `report\06:630`「res/xml 只有 …，**没有 Dk.xml**」 | `res/Dk.xml` **存在**（`zip_listing.txt:24988`）；该包 `res/` 是 AndResGuard 扁平混淆，本就没有 `res/xml/` 目录 | **事实错误（把资源名当路径）** |
| `report\DEADENDS.md:343`、`report\INDEX.md:243`(#45)、`:513`(A-20)「本 APK 根本没有这个属性 / Dk.xml 不存在」 | 同上，全部作废 | **事实错误** |

> 有趣的是，项目自己的**更早、更细**的审计是对的：`work\ba\audit\ba-java.md:168-169`
> 「`usesCleartextTraffic` **true**；`networkSecurityConfig` **`@xml/http`**」，`anticheat-full.md:23`/`:95` 也照抄了这个结论。
> 也就是说 **§7.10a 是一次回退性错误**：它晚出（01:33）却推翻了一个正确的早期结论，而 D-40 / A-20 又继承了这个错误。

### 3.3 `res/Dk.xml` 的**内容**：未找到（不编）

- 2.1 GB 的 `.apk` 本体已被删（`report\57:141`：为腾空间），`slim.apk` 只有 4 个条目，`res.apk`（3.1 MB）是**替换用资源包**、不含 `res/Dk.xml`。
- 因此**无法直接读 Dk.xml 的字节**。可用的间接记录只有两条，且互相一致：
  - `work\ba\audit\ba-sdk-protocol.md:10-11`「`res/Dk.xml`（network-security-config）里是 `cleartextTrafficPermitted=true`，**全域名允许明文**」
  - `report\06:631`「`res/xml/http.xml` 的 strings = `base-config` / `cleartextTrafficPermitted` / `network-security-config`」
- ⇒ **内容判定：`<base-config cleartextTrafficPermitted="true">`，且没有记录到 `trust-anchors` / `certificates` 字样**（推断，中等置信）。
  这条很关键：这意味着当前生效的是**默认 trust anchors**，而 `targetSdk=33 ≥ 24` 的默认 = **只信系统 CA**（`report\20:170` 一手：`ApplicationConfig` 只在 `targetSdkVersion <= 23` 才 `addCertificatesEntryRef(UserCertificateSource)`）。
- 附带影响：`cleartextTrafficPermitted=true` + `usesCleartextTraffic=true` 双保险 ⇒ **明文 http 在本包是放行的**（`report\01:54`、`report\03:396`；注意 `INDEX.md:513` A-20 否认的是"`res/Dk.xml` 字符错写成 `Dk.xml` 的引用方式"，不是这条能力本身）。

---

## 4. networkSecurityConfig 对 libcurl 是否是有效控制点（核心疑点分析）

### 4.1 先把机制钉死：NSC 是 **Java 层**的东西（确证，有一手源码）

- 生效点：每个 App 进程在 `ActivityThread.handleBindApplication()` 里调 `NetworkSecurityConfigProvider.install()`，把默认的 `TrustManagerFactory`/`SSLContext` 换成 `android.security.net.config.RootTrustManager`。
  来源：`report\20:141`（【一手】frameworks/base 路径）。
- "系统 CA / 用户 CA 怎么选"这件事本身，就发生在**这个 Java 类**里：
  `SystemCertificateSource.getDirectory()` 硬编码优先级 → `system.certs.enabled` ? `/system/etc/security/cacerts` : (sdk≥34 且 APEX 目录非空 ? `/apex/com.android.conscrypt/cacerts` : `/system/...`)。来源：`report\20:145-159`（贴了完整 Java 源码）。
- ⇒ **NSC 只影响两件事**：① Java 层 `TrustManager`/`SSLContext` 的默认信任锚集合；② `NetworkSecurityPolicy.isCleartextTrafficPermitted()` 的返回值（供 Java/libcore socket 用）。
  它**不是**内核/套接字层的策略，也**不会**改写 `/system/etc/security/cacerts` 的目录内容。**这是我对机制的核心判断，置信度：确证。**

### 4.2 客户端到底谁在做 TLS 校验？—— 一手 logcat 给了答案

```
E Unity : Curl error 60: Cert verify failed. Certificate is not correctly signed by a trusted CA.
          UnityTls error code: 7
W LogProducerHttpTool: java.security.cert.CertPathValidatorException: Trust anchor for certification path not found.
W sls_android_native : send network error … Trust anchor for certification path not found.
```
出处：`report\06-手机基线恢复.md:643-645`（pid 7238 当前游戏进程原文）。

判读（**确证**）：
- 游戏那条错的是 **`E Unity` tag + `Curl error 60` + `UnityTls error code: 7`** ⇒ 证书链校验发生在 **libunity 内的 libcurl + UnityTLS(mbedtls)**，**不是** Java TrustManager。
  （旁证：`report\11:225` 从 `libunity.so.txt` 里数出 107 条 `mbedtls*` 字符串，TLS 栈就是 UnityTLS；`:223-224` 还有 `CertificateHandlerProxy` / `ValidateCertificateNative`。）
- 同一时刻的 `CertPathValidatorException` 来自 **`LogProducerHttpTool` / `sls_android_native`**，那是**阿里云 SLS 日志 SDK 自己的 Java/okhttp 栈**，与游戏网关**不是同一条链**。
  ⇒ **不能**把这条 Java 侧报错当成"游戏走 Java TrustManager"的证据（这正是 `report\20:110` 那句"你的 App 是 Unity + JNI TrustManagerFactory = Java 侧"最可疑的地方：它没有区分两条栈）。

### 4.3 三种可能的 trust source 模型，与各自对 P2 的含义

| 模型 | Unity 取 CA 的方式 | NSC `src="user"` 有用吗 | 用户 CA（PEM）够吗 | 支持它的证据 | 反对它的证据 |
|---|---|---|---|---|---|
| **A** | JNI → Java `TrustManagerFactory`（**被 NSC 劫持**） | **有用** ⇒ P2 成立 | 不够（targetSdk 33 默认排除 user） | `report\20:110`；Unity 官方文档"against **OS store**"（`report\12:150`） | 若真是 A，用户 CA 从未被干净测试过（见 §4.4），无法排除 |
| **B** | JNI → `KeyStore("AndroidCAStore")`（**不被 NSC 劫持**，且**本来就含 user**） | 无用（但无害） | **够** ⇒ **P2 完全不需要** | UUM-73839：`2021.3.48f1` 修的就是"user installed certificates 进不了 `trusted_ca` 列表"（`report\12:162`）——**说明 Unity 确实去枚举用户库** | `report\20:130` 推断"Unity 默认不走 AndroidCAStore" |
| **C** | native 直接读目录 `/system/etc/security/cacerts`（无 Java 参与） | **无用** ⇒ P2 失败 | 不够 ⇒ 只有 root 装系统 CA | 项目实测"系统库（apex+system，root 装）后 TLS 通了" | `report\12:143,162` 的 release note 与 C 矛盾（若 C，则"用户库进 trusted_ca"这个 bug 不该存在） |

**关键洞察（本报告最重要的一条判断）**：
> **P2 在 A、B 两模型下都"安全"，只在 C 下失效。** 而 B 模型下你连重打包都不用做。
> 所以真正的分水岭不是"要不要加 NSC"，而是**先花 10 分钟验 B 是否成立**——成立就免 root 且免改包，不成立再谈重打包。

### 4.4 项目"用户 CA 无效"的既有结论**是被污染的**，不能当反证

证据链（全部可查）：

1. 用户库那份 CA **是 DER**（819 B，`/data/misc/user/0/cacerts-added/fd8b2b01.0`，`report\06:608`）；系统/APEX 那两份是**后来现场转的 PEM**（`report\06:605-607`）。
2. 而那段时间**服务端下发的链的根 ≠ 我们装进库的那个根**：
   `report\06:655` 原文「服务端当前链的根 ≠ 我们装进信任库的 `BA Test Root CA`」；`:649-654` 的判据是手机侧 `curl --cacert ba_ca_pem.pem … → 000 verify failed`。
   ⇒ 所以"三处全装仍 unknown CA"（`report\06:612`）**首先**能用"根不匹配"解释，**不能**证明"用户库不被读"。
3. 真正让 TLS 通的那一刻，**系统库同时也装着**：`report\22:15-16`「46 条 `fatal alert 49` 全部落在 01:24:58–01:33:45，之后**一条都没有**，01:34:52 同一条链路直接 200 ⇒ **CA 生效时刻 = 01:33:45**」，且 `:22-23` 明确换成 `ca2/chain.crt`（根 = `BA Test Root CA`，与库里那份同尺寸）后立即通。
4. ⇒ **从没有任何一次实验是"只有用户库、没有系统库、且链根匹配"的干净对照。**
   `report\06:593` 那句"用户 CA 对 UnityTLS 无效"是一个**表格里的候选解释**，不是实验结果。

**额外一条强机制（把 DER 这个变量也解释了）**：
`report\20:116-131` 一手引了 conscrypt `TrustedCertificateStore` 的读函数——**它只认 PEM**，头不是 `-----BEGIN CERTIFICATE-----` 就抛异常。
而 `KeyStore.getInstance("AndroidCAStore")` 的后端就是 `TrustedCertificateStore`。
⇒ **如果 Unity 走模型 B，那份 DER 的用户 CA 会被直接跳过（=`logcat` 里连错都看不到，只是"没有"）**，而 PEM 的会生效。
这同时解释了"三处全装、PEM/DER 都对、label 对、app 也读得到（`report\06:636-639` 用 `head -c 30` 证明 PEM 可读）、TLS 仍 unknown CA"——因为没读的那份是 DER，读到的那份根却不匹配。

### 4.5 那"别的做法让原生层信任用户 CA"有哪些（逐条评估）

| 方案 | 可行性 | 依据 |
|---|---|---|
| 改 `res/Dk.xml` 加 `<certificates src="user"/>`（= P2 本体） | **取决于模型 A/B/C**，见 §4.3 | 机制见 §4.1 |
| 把 CA 塞进 APK assets + 改 libcurl 的 `CURLOPT_CAINFO` | **不可行** | `CURLOPT_CAINFO` 是**代码里设的**，不在配置里；要改就得改 libunity（有 hash pin）或改 libil2cpp 里调用 libunity 的点（目标函数在编码页，见 `report\57:246-247`）。且 APK 里**根本没有** cacert/bundle 可换（`DEADENDS.md:351`、`report\06:461-465`） |
| 改 libunity 内置 CA bundle | **禁止** | 无 bundle（同上）；且 libunity 有 hash pin，4 B 即 SIGBUS（`ba-pitfalls.md:50`、`report\16:140`） |
| `SSL_CERT_FILE` / `CURL_CA_BUNDLE` 环境变量 | **不可行** | libcurl 认，但 Android app 进程 env 由 zygote 派生，应用层设不了（`report\16:138`） |
| 运行期改 libil2cpp RW 段里的 UnityTLS trust store | 理论可行、实践不划算 | 需先知道结构布局；每次握手重建（`report\16:139`）；且我们连 `ValidateCertificate` 的方法地址都还没拿到（`report\11:376`「需要方法地址才能反编译（**证据不足**）」） |
| 系统库装 CA（root + zygote ns `--rbind`） | **已实证有效**（这是目前唯一的成功路径） | `report\22:15-16`、`report\21:57-68` |
| 只装用户 CA（PEM）+ 链根匹配、**什么都不改** | **未测，但这是最便宜的一发** | `report\12:162`（UUM-73839）+ §4.4 的污染分析 |

---

## 5. P2 判定：**需真机验证**（并给可执行验证序列）

### 5.1 判定

| 子问题 | 判定 | 置信度 |
|---|---|---|
| 需要"给 manifest 加属性"吗？ | **不需要**，属性已在（`@xml/http`） | 确证 |
| 需要改的文件 | 只有 **`res/Dk.xml`**（编译后的二进制 AXML），加 `<trust-anchors><certificates src="system"/><certificates src="user"/></trust-anchors>` 进 `<base-config>` | 确证 |
| 改动面安全吗（ACE） | **安全**：`res/*` 是 E32/E34/E42 实测过关的改动面；`resources.arsc` 甚至不用动（资源 id 与路径都不变） | 确证（改动面）/ 推断（本例） |
| 会因"重签"被 ACE 杀吗 | **现有证据不支持**（E30/E38/E42 三次重签都跑起来了）；但 `sourceDir`+签名上报是**未量化的账号风险** | 确证（不杀）/ 未知（上报后果） |
| NSC 能生效吗（对 libcurl） | **不确定**。只在模型 A 下生效；模型 B 下"本来就生效、不需要它"；模型 C 下完全无效 | **未知（核心未决点）** |
| P2 能达成"免 root"吗 | **只能解决 CA 信任这一半**。host 重定向仍需另half（`default_state_url` 在 metadata 里 ⇒ 又要改包；或 `Hosts` 文件；或明文 http） | 推断 |

**⇒ 总判定：`需真机验证`。不建议直接上 2.1 GB 重打包，先跑 §5.2 的 E1。**

### 5.2 验证序列（成本从 10 分钟到半天，逐级否决）

**E1（10 分钟，零重打包、零 root）—— 分水岭实验**
```
前置：服务端链的**根** = 手机用户库里那张 CA（PEM，不是 DER），leaf+root 一起下发（UnityTLS 不补链，report\12:182）
① 只往用户库装 CA：设置→安全→安装证书→CA 证书（或 adb push 后由系统设置导入），确认落成 **PEM**
② 确认系统库/APEX 里**没有**同一张（`ls /apex/com.android.conscrypt/cacerts | wc -l` 应为原厂数；本次基线 146/147，见 report\06:637）
③ 冷启动（TrustManager/UnityTLS 都是启动期建 context，report\18:130）
④ 判据：`logcat | grep -iE "UnityTls|Curl error 60"` 与 DNAT 后的 pcap（flight 之后有没有 `GET /api/state` 200）
成立  ⇒ 模型 B 成立 ⇒ **P2 作废**，免 root 路线 = 装用户 CA + 解决 host 重定向
不成立 ⇒ 进 E2
```
> E1 的关键细节：**必须 PEM**。DER 会被 `TrustedCertificateStore` 静默跳过（`report\20:116-131`），这正是历史那次失败最可能的单点原因。

**E2（半天，一次重打包）—— 验 NSC 是否有效**
```
① 只改 res/Dk.xml：<base-config cleartextTrafficPermitted="true">
     <trust-anchors><certificates src="system"/><certificates src="user"/></trust-anchors>
   </base-config>
   （用 aapt2 单独编译这一条 xml，抽出二进制 XML；**不动 resources.arsc**：id 0x7f120001 与路径 res/Dk.xml 都不变）
② 外科式重写 zip：只替换 res/Dk.xml 这一个条目（defalted，大小可变），**resources.arsc 保持首条 + STORED + 4 字节对齐**（ba-pitfalls.md:140）
③ zipalign → apksigner（ba_private.keystore, alias ba/baserver，见 report\57:137）
④ 卸载重装（签名变了必须卸）→ 复 E1 的 ④ 判据
成立  ⇒ 模型 A 成立 ⇒ P2 可行（但代价：每次发版都要重签 + 用户要卸载重装）
不成立 ⇒ 模型 C ⇒ P2 不可行，回到 root/系统 CA 路线
```

**E3（只在 E1/E2 都失败时才做）**：确认 C 模型的绕法 —— 只有运行期内存补丁 libunity 的 UnityTLS trust store（`report\21:90` 的兜底方案 D），或继续 DNAT+系统 CA。

### 5.3 必须先写进脚本的两个保护
1. **ACE 记账复位**：每次装新包前后删 `ace_shell_di.dat`/`shell_cache`/`ano_tmp`/`data/app`（`ba-pitfalls.md:61-69`），否则"被记账"会被误判成"P2 被 ACE 杀"。
2. **空间**：`apksigner` 要 ≥2.1 GB 余量（`ba-pitfalls.md:138`），设备侧只剩 4 GB（`ba-pitfalls.md:200`）⇒ 在 PC 侧签、只把成品推上去。

---

## 6. 关键引文摘录（带 文件:行号）

**A. 重打包成功过的直接证据**
- `work\ba\audit\ba-pitfalls.md:163`「E30 APK：`/sdcard/Download/BA_E30.apk`（2,126,498,053 B，**已签名，已安装，不崩**）」
- `work\ba\audit\ba-pitfalls.md:55`「`resources.arsc` / `res/*` | ✅ 正常 | E32/E34/E42 | 能进主程序、文案生效」
- `work\ba\audit\ba-pitfalls.md:149-150`「E42：官方资源基线 + 原厂 `libunity` + 我们的 `res`（卡密文案）+ `assets/SDKConfigSettings.json`（`sdk_url` 指本机）+ 删 `__tpinfo` / 表现：**能进主程序、SDK 卡密登录通过**」
- `report\02-注入链审计.md:236`「libil2cpp 填充字节翻转（E38）| **正常启动 45 s+ 存活**」（`report\02:32` 补充：E38 是纯填充翻转、无注入）
- `report\57-既有补丁资产清点.md:328`「**E38/E42 是"能进主程序"的那两版**」

**B. ACE 选择性校验 / 无整包签名校验**
- `work\ba\audit\ba-pitfalls.md:57`「`libil2cpp.so` 填充字节翻转（EOF 后 1600 B slack）| ✅ **正常启动（45 s+）** | E38 | 与 `ace-ipc.md` §3「无 hash pin」一致」
- `work\ba\audit\ba-pitfalls.md:171`「往 libil2cpp RX 段尾部空隙(`0xf2c2410`)写入 ARM64 代码，改 PLT 首指令为 B | ✅ **不触发 ACE**，进程正常启动运行」
- `work\ba\audit\ba-pitfalls.md:192`「`DT_INIT` 改成代码洞地址 | ✅ 可用 | 日志 `IN / BA / DON` 出现，进程存活，**未触发 ACE**」
- `work\ba\audit\ba-pitfalls.md:197`「**root 直接替换 `/data/app/.../lib/arm64/libil2cpp.so` 原位文件** | ✅ 可用 | 替换后启动正常、`DT_INIT` 钩子照跑，**未触发 ACE**」
- `work\ba\audit\ba-pitfalls.md:50`「`libunity.so` 4 字节证书补丁 `@0xA53A38` | ❌ **SIGBUS** | E36 | `ApplicationExitInfo reason=2 status=7`，无 tombstone」
- `work\ba\audit\anticheat-full.md:92-93`「数美 `…/l111l1111lIl.java:38-46`：`getPackageInfo(str, 64).signatures` → `MessageDigest("SHA1")` → hex」/「nirvana `AppUtils.java:73`：`APP_SIGNATURE = hexdigest(…)`」
- `work\ba\audit\anticheat-full.md:111-112`「`AceApplication` `:50-58` 传入 `packageName / nativeLibraryDir / sourceDir / filesDir`，并反射取 `ApplicationInfo` 的 `splitSourceDirs`」/「ACE 拿 `sourceDir + splitSourceDirs` 在 native 做 APK 完整性/路径校验」

**C. NSC 现状（我的字节级复核 + 一手记录）**
- `work\ba\audit\ba-apk\jadx\resources\AndroidManifest.xml:187-189`
  `android:extractNativeLibs="true"` / `android:usesCleartextTraffic="true"` / **`android:networkSecurityConfig="@xml/http"`**
- 二进制 AXML 复核（本次）：`<application>` line 202 → `networkSecurityConfig @0x7f120001`
- `resources.arsc` 复核（本次）：`0x7f120001 key=http -> res/Dk.xml`
- `work\ba\audit\ba-apk\zip_listing.txt:24988` = `res/Dk.xml`
- `work\ba\audit\ba-java.md:168-169`「`usesCleartextTraffic` **true**」「`networkSecurityConfig` **`@xml/http`**」
- `work\ba\audit\ba-sdk-protocol.md:10-11`「`res/Dk.xml`（network-security-config）里是 `cleartextTrafficPermitted=true`，全域名允许明文」

**D. "没有该属性"的错误结论（需更正）**
- `report\06-手机基线恢复.md:628`「AndroidManifest.xml 里 grep 'networkSecurityConfig|cleartext|network' → 全空（无该属性）」
- `report\06-手机基线恢复.md:630`「res/xml 只有 … —— **没有 Dk.xml**」
- `report\DEADENDS.md:343`「**本 APK 根本没有这个属性**」
- `report\INDEX.md:243`（#45）、`report\INDEX.md:513`（A-20）同义

**E. NSC 的机制边界（Java 层）**
- `report\20-AndroidCA注入深度调研.md:141`「`ActivityThread.handleBindApplication()` 里对每个 App 进程调用 `NetworkSecurityConfigProvider.install()`」【一手】
- `report\20-AndroidCA注入深度调研.md:145-159` `SystemCertificateSource.getDirectory()` 全文【一手】
- `report\20-AndroidCA注入深度调研.md:170`「`targetSdk=33 ≥ 24` 时，默认 config **只收系统 CA**，不收用户 CA（除非 App 在自己的 `network_security_config.xml` 里写 `<certificates src="user"/>`）」【一手 Android 官方文档】
- `report\20-AndroidCA注入深度调研.md:116-131` conscrypt `TrustedCertificateStore` 只认 PEM【一手】
- `report\20-AndroidCA注入深度调研.md:110`「你的 App 是 **Unity + JNI TrustManagerFactory = Java 侧**」（**与 §4.2 的 logcat 证据冲突，本报告不采信其无条件形式**）

**F. 客户端 TLS 在 native（UnityTLS/libcurl）**
- `report\06-手机基线恢复.md:643`「`E Unity : Curl error 60: Cert verify failed. … UnityTls error code: 7`」
- `report\11-客户端静态逆向-网关与证书.md:225`「`External/Mbedtls/builds/library/ssl_msg.c` 等 107 条 `mbedtls*` | TLS 栈是 **mbedtls（UnityTLS）**，在 libunity 里」
- `report\11:223-224`「`CertificateHandlerProxy` … `ValidateCertificateNative`」
- `report\12-外部资料-证书与网关重定向.md:150`「validated against **the root certificate store available on the system**」【一手 Unity 文档】
- `report\12:162`「**2021.3.48f1 | Fixes | Android | Fixed issue where user installed certificates directly to an Android device wouldn't show up in the `trusted_ca` list.**」【一手 UUM-73839】
- `report\12:168`「你们的 `2021.3.56f2` > 48f1，修复已在」
- `report\12:182`「UnityTLS **不自动补中间证书**」⇒ 必须 leaf+root 一起下发

**G. 用户 CA 实验被污染的证明**
- `report\06:608`「`/data/misc/user/0/cacerts-added/fd8b2b01.0` **DER（保留）**」
- `report\06:605-607`「由 DER 现场生成 PEM（1161 B）→ `/system/...` 147 项 / `/apex/...` 147 项」
- `report\06:655`「**服务端当前链的根 ≠ 我们装进信任库的 `BA Test Root CA`**」
- `report\06:612`「CA 路线判定为走到头（三处 store、PEM/DER、正确 label、冷启动全试过）」← **结论被 §655 自我否定**
- `report\22-服务端取证记录.md:15-16`「01:33:45 之前 46 条 `fatal alert 49`，之后一条都没有，01:34:52 同一条链路直接 200 ⇒ **CA 真正生效时刻 = 01:33:45**」
- `report\22:22-23`「证书目录已被换成 `ca2/chain.crt`（`CN=BA Test Root CA`）… `ca2/ca.crt` = 1164 B，与手机信任库里装的同尺寸 ⇒ 手机信任的是 ca2 的根」
- `report\INDEX.md:503`（A-10）「46 条 `alert 49` **全部落在 01:24:58–01:33:45**（CA 生效之前）… 49 的消失与 CA 生效严格同步，指向 trust store」

**H. 重打包被降级的成本理由**
- `report\52-客户端补丁方案-metadata绕过登录.md:530-532` 三库 hash pin 矩阵（libunity 钉 / libil2cpp 不钉 / metadata **未知**）
- `report\52:544`「重打包 → 签名变 → 撞 ACE 的 sourceDir/签名完整性面 … → 必须卸载重装 → 丢 `/data/data` + 11 GB 资源要 mv 回来并 `chown`」
- `report\52:549`「**闸门 1 没确认之前，不要做任何需要重打包的补丁**」
- `work\ba\audit\ba-pitfalls.md:138,140,200`（apksigner 2.1 GB / zipalign Illegal instruction / 原位替换免重打 2.1 G）
- `work\ba\audit\ba-pitfalls.md:61-69`（ACE 记账 + 4 文件复位）
- `report\18-Frida与运行时绕过调研.md:213`（F4：改 `res/xml` 的 NSC，已实测 `res/*`+arsc 改动不被 ACE 杀，"成本最低、风险最小的一条"）
- `report\23-主线改判-TLS已通应用层卡点.md:84`（优先级：改 `res/xml` NSC > 明文 `http://` > 运行期内存补丁 libunity）
- `report\90-项目总纲-可交接版.md:264`「整套依赖 **DNAT（需 root/iptables）+ 系统 CA**，且 Unity 走 **libcurl 系统 CA 库**（非 App 内 CA bundle）⇒ 用户侧必须有一台被 root/可控的设备或网关」

---

## 7. 与既有文档冲突的更正表 + 明确"未找到"

| 项 | 旧说法 | 本次结论 | 处理建议 |
|---|---|---|---|
| APK 有无 `android:networkSecurityConfig` | 无（`DEADENDS.md:343`、`INDEX.md:243,513`、`report\06:628`） | **有，= `@xml/http`（确证，字节级）** | 更正 DEADENDS D-40 / INDEX A-20 / #45 / `report\06` §7.10a |
| `res/Dk.xml` 是否存在 | 不存在（`report\06:630`） | **存在（`zip_listing.txt:24988`）** | 同上 |
| D-40 的"为什么失败"三条 | ①属性不存在 ②Unity 不理 NSC ③重签撞 ACE | ①**假** ②仍是本报告 §4.3 的未决点 ③**证据不支持**（E30/E38/E42） | D-40 应降级为"未验证"，不是"死路" |
| 用户 CA 无效 | `report\06:612`、`DEADENDS.md:311-312`(D-36) | **实验被污染**（链根不匹配 + 用户库那份是 DER） | 必须重做，见 §5.2 E1 |
| `report\20:110`「Unity = Java 侧 TrustManagerFactory」 | 当作既成事实 | **与 `report\06:643` 的 `E Unity : Curl error 60` 冲突**，不能无条件采信 | 标为"待定" |

**明确未找到（不编）**
1. `res/Dk.xml` 的**字节内容** —— 2.1 GB APK 本体已删，`slim.apk`/`res.apk` 都不含它。只能靠 `ba-sdk-protocol.md:10-11` + `report\06:631` 两条间接记录。
2. 游戏包的 **`pm install` 原文** —— 全项目没有（`report\57:384` 也这么写）。E30 的"已安装"是记录性描述，不是日志。
3. **ACE `initialize()` 对 `sourceDir`/`splitSourceDirs` 到底算什么**（签名？CRC？dex？）—— 从未验证（`anticheat-full.md:150`）。
4. **签名 hexdigest 上报后服务端如何处置** —— 无证据。
5. **Unity 在 Android 上取 CA 的真实实现**（模型 A/B/C 哪一个）—— 无静态证据（`libunity` 有 hash pin 不能改；`libil2cpp.so` 里 `CustomCertificateHandler`/`ValidateCertificate` **0 命中**，`report\11:234`；`ValidateCertificate` 的方法地址未拿到，`report\11:376`；运行期 dump 明文 metadata 已证伪，`DEADENDS.md:296-302`）。

---

## 8. 交给下游的一句话

> P2 的"加属性"是无用功，属性本来就在；真正要改的只有 `res/Dk.xml` 一个文件，而 `res/*` 恰好是已实测最安全的改动面、且重签没有被 ACE 杀过的记录。
> **但先别打包**：花 10 分钟做 §5.2 的 E1（用户库装 **PEM** 的 CA + 服务端下发同根 leaf+root + 冷启动），
> 因为只要 Unity 走 `AndroidCAStore` 那一路，**免 root 就已经成立，P2 根本不需要**；E1 不成立再花半天做 E2 验 NSC。
