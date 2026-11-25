# Android 14–17 系统 CA 注入深度调研（Q1–Q7）

> 调研时间：2026-11-14 01:30–03:00（Asia/Shanghai）
> 目标设备现场（不推翻，作为约束）：`PLR110` / Android 17 / SDK 37 / KernelSU（`u:r:ksu:s0`）/ 无 Magisk /
> `com.RoamingStar.BlueArchive` 3.0.2 (versionCode 73) / `targetSdk=33` / `primaryCpuAbi=arm64-v8a` / UID `10576`
> 现状：TLS 证书 **已 100% 送达**（pcap 实证 ServerFlight 2601 B），客户端回加密 alert，明文形态为 `access_denied(49)`。
> 本文只解决一个问题：**为什么这份 CA 没被 AndroidCAStore 读到，以及怎么让它被读到。**

标注约定：**【一手】**＝AOSP 源码/官方文档/仓库 README 原文/issue 原帖；**【二手】**＝第三方博客、论坛、经验帖；**【推断】**＝本文基于前两者的推理，未直接验证。

---

## 0. TL;DR（先看这张表）

| 问题 | 结论 | 置信度 |
|---|---|---|
| **Q1 系统 CA 目录里是 PEM 还是 DER** | **原厂文件是 PEM 文本**（`-----BEGIN CERTIFICATE-----`）。但 **DER 也不是致命错误**：App 走的 `DirectoryCertificateSource` 用 `CertificateFactory.generateCertificate()`，PEM/DER 通吃。**所以「装 DER」不是你的直接原因** —— 别再在这上面耗时间（除非走 `AndroidCAStore` KeyStore 路径，见 Q1.4） | 高（AOSP 源码 + AOSP 仓库文件） |
| **Q1 真正的死因（三条写入全废）** | ①目标 SDK 33 → **用户证书库默认不被信任**（Android 7 起的设计）；②A14+ `SystemCertificateSource` **优先读 APEX 目录且只要非空就完全忽略 `/system`** → 你写 `/system` 的那份是死代码；③写 `/apex` 的文件**不在 App 的 mount namespace 里**（`/apex` 是 private propagation） | 高 |
| **Q2 SELinux** | 目录/文件标准 label 是 `u:object_r:system_file:s0`；**从 `/sdcard` 或 `/data/local/tmp` 直接 `cp -a` 会把 `shell_data_file` 带进去**（`cp` 不带 `-a` 则新 inode 继承父目录 label，通常反而是对的）。**必须显式 `chcon` 并 `ls -Z` 实证**。A14+ SELinux 本身**不阻止** App 读这个目录 | 中高 |
| **Q3 `/apex` 挂载语义** | **关键：`/apex` 挂载点被设成 private propagation**。基础挂载在全局可见（所以你在 App ns 里看到 `dev/ino` 一致 —— 这个观察是**对的**），但**你在自己 ns 里新加的 mount 不会传播给 App**。→ 必须在 **zygote / zygote64 的 mount namespace 里**做 bind mount（新 fork 的 App 继承），再对已在跑的 App 进程各做一次 | 高 |
| **Q4 缓存** | `SystemCertificateSource` 是**进程内单例**（`NoPreloadHolder.INSTANCE`），`DirectoryCertificateSource` 还有自己的缓存。**已在运行的进程永远看不到新 CA**；同进程内重新 `SSLContext.init(null,…)` 也拿不到。唯一可靠手段：**杀进程冷启**。`am broadcast -a android.security.action.TRUST_STORE_CHANGED` 存在但在你这台机器上 `am` 被 SELinux 挡 | 高 |
| **Q5 Android 17** | CA store 位置/策略**没变**（仍以 APEX 为准）。CT（证书透明度）在 **targetSdk≥37** 才默认强制；**你是 33，不强制** → 我们的自签 CA 不需要 SCT，这条不是障碍 | 高 |
| **Q6 最可能在 A17+KSU 成功** | ①手动 nsenter 注入（最快验证）；②持久化用 **System CA Manager**（`cacerts_bind_manager`，KSU 原生、不依赖元模块、显式处理 zygote ns 与 `/apex` private propagation）或 **AlwaysTrustUserCerts v1.3** / **MoveCertificate v1.6.2**（README 明示 7–17） | 中高 |
| **Q7 不用装 CA** | 有：`system.certs.enabled=true`（需 zygote 起来之前设，等于要模块+重启）；LSPosed 的 **UserCABridge / JustTrustMe**（hook 的是**框架类**，跟你说的「进程内 XposedBridge 是混淆替身」不冲突）；Frida hook `X509TrustManager.checkServerTrusted` | 中 |

> **一句话**：你三次写入失败是三个**不同**的原因，不是同一个「格式错」。
> 最可能的单点解法：**把「合并后的证书目录」bind mount 进 `zygote64` 的 mount namespace，再 `kill -9` 游戏进程重拉。**

---

## Q1 ★ 系统 CA 目录里的文件到底是什么格式

### 1.1 原厂文件 = PEM 文本【一手】

AOSP 的系统 CA 源仓库是 `platform/system/ca-certificates`，证书本体就放在 `files/` 下，**提交进 git 的内容就是 PEM 文本**。看这个新增 `files/1b0f7e5c.0` 的提交 diff，新增行全是 armor：

```
+-----BEGIN CERTIFICATE-----
+MIIFWjCCA0KgAwIBAgISEdK7udcjGJ5AXwqdLdDfJWfRMA0GCSqGSIb3DQEBDAUA
+MEYxCzAJBgNVBAYTAkJFMRkwFwYDVQQKExBHbG9iYWxTaWduIG52LXNhMRwwGgYD
+VQQDExNHbG9iYWxTaWduIFJvb3QgUjQ2MB4XDTE5MDMyMDAwMDAwMFoXDTQ2MDMy
...
```
- 来源：<https://android.googlesource.com/platform/system/ca-certificates/+/c8d7f51bbb3de2c40a0d868972be008070eb25d8%5E!/>（提交说明里同时给出 `openssl x509 -text` 的人读输出，文件名 `1b0f7e5c.0` = GlobalSign Root R46）
- 同仓库镜像可交叉验证：<https://git.replicant.us/mirrors/AOSP/platform_system_ca-certificates/commit/?h=android10-qpr2-release&id=93f8c6181ac45851f27b7a9938a560424194f095>（同样是 PEM 行）

这些文件在构建时**原样**装进 `/system/etc/security/cacerts`；Android 14 起同一份文件也被装进 `com.android.conscrypt` APEX 的 `cacerts/`。【推断·高置信：`Android.bp` 里是 `prebuilt_etc` 直接拷贝，没有转码步骤】

官方文档也确认存放位置从 system 分区扩展到 APEX，但没有"转 DER"这一步：
- 【一手】AOSP《Conscrypt》模块文档，**最后更新 2026-10-11**：<https://source.android.com/docs/core/ota/modular-system/conscrypt>（中文镜像 https://source.android.google.cn/docs/core/ota/modular-system/conscrypt）
  > "自 Android 14 起，根信任凭证会储存在 Conscrypt 模块 APEX 和系统分区中。应用仍可自行选择凭证，并使用 NetworkSecurityConfig 修改凭证行为。"

**现场 10 秒自证**（比任何博客都硬）：

```sh
# 看你机器上原厂证书的头 40 字节
ls /apex/com.android.conscrypt/cacerts | head -1
head -c 40 /apex/com.android.conscrypt/cacerts/$(ls /apex/com.android.conscrypt/cacerts | head -1); echo
# 期望输出：-----BEGIN CERTIFICATE-----
# 再看你自己那份
head -c 40 /apex/com.android.conscrypt/cacerts/fd8b2b01.0 | od -c | head -3
# 若第一字节是 0x30 0x82 → 是 DER
```

### 1.2 DER 为什么"可能"也能用：消费端代码【一手】

App 的 `TrustManagerFactory` 在 Android 上并不直接用 conscrypt 的 `TrustedCertificateStore`，而是走**框架层 NetworkSecurityConfig**。关键类 `android.security.net.config.DirectoryCertificateSource`：

```java
private final CertificateFactory mCertFactory;

protected DirectoryCertificateSource(File caDir) {
    mDir = caDir;
    try { mCertFactory = CertificateFactory.getInstance("X.509"); }
    catch (CertificateException e) { throw new RuntimeException(e); }
}

private X509Certificate readCertificate(String file) {
    InputStream is = null;
    try {
        is = new BufferedInputStream(new FileInputStream(new File(mDir, file)));
        return (X509Certificate) mCertFactory.generateCertificate(is);   // ← 注意这里
    } catch (CertificateException | IOException e) {
        return null;                                                      // ← 静默跳过！
    } finally { IoUtils.closeQuietly(is); }
}
```
- 【一手】源码：<https://android.googlesource.com/platform/frameworks/base/+/d4b6c69/core/java/android/security/net/config/DirectoryCertificateSource.java>
- 第三方镜像同文：<https://chromium.googlesource.com/android_tools/+/dea822cdc3db593d4bcd54a929c1d515cbc27fa7/sdk/sources/android-25/android/security/net/config/DirectoryCertificateSource.java>

`CertificateFactory.generateCertificate()` 在 Android 上由 `OpenSSLX509CertificateFactory` 实现，**同时接受 PEM 与 DER**（先探测 PEM armor，否则按 DER `d2i_X509` 解析）。【推断·高置信，但结论被大量实践印证：无数帖子里 DER 文件丢进目录也能生效】

> **⚠ 这段代码里最重要的一行是 `return null;`**：读不到 / 解析失败 / SELinux 拒绝，**全部静默吞掉，只打一条 `Log.e`**（TAG `DirectoryCertificateSrc`）。这解释了为什么你"没有任何报错但就是不信任"。**这也是最好的探针，见 §Q2.4。**

### 1.3 那"必须 DER"的说法是哪来的？【二手·有误】

`ys1231/MoveCertificate` 的 README 里有一句：

> "# pem 证书　Android 系统使用 der 所以移动后的证书格式需要转成 der"
> —— <https://github.com/ys1231/MoveCertificate>（README 更新至 v1.6.2，2026-09-02）

这句话**与 AOSP 事实相反**，且它自己的 README 前面又写着"优先使用系统设置安装，不需要处理编码问题"——自相矛盾。同类项目直接打脸：

> "**Automatic DER-to-PEM conversion** — certificates in DER (binary) format are automatically converted to PEM, ensuring compatibility with BoringSSL/Flutter apps that require PEM format."
> ——【一手】`Magisk-Modules-Alt-Repo/custom-certificate-authorities` README（magisk.dev 收录页 **2026-06-15** 更新）：<https://magisk.dev/modules/custom-certificate-authorities/>

> "Flutter 只接收 PEM 格式的证书，如果是 DER 的证书也会导致问题"
> ——【二手】语雀《系统证书安装》，2026-10-24：<https://www.yuque.com/again-719bb/pfhi8f/xh5lruo7gy9apsv9>

**判读**：真正要求 PEM 的是 **BoringSSL / Flutter / 原生 libcurl**（`X509_STORE_load_locations` 只解析 PEM）。Java 侧的 `CertificateFactory` 两种都吃。你的 App 是 **Unity + JNI TrustManagerFactory = Java 侧**，所以：

> **结论：DER 大概率不是你这次失败的原因。** 但把它转成 PEM 是**零成本的保险**（同时兼容未来任何走 BoringSSL 的旁路），建议做，**不要指望它单独解决问题**。

### 1.4 唯一会因为 DER 而死的路径（留档）

conscrypt 自己的 `TrustedCertificateStore`（`KeyStore.getInstance("AndroidCAStore")` 的后端）用的是**另一个**读函数，**只认 PEM**：

```java
private static final String PREFIX = "-----BEGIN CERTIFICATE-----";
...
String header = br.readLine();
if (header == null || !header.startsWith(PREFIX)) {
    throw new CertificateException("file " + file + " does not contain a certificate, header: '" + header + "'");
}
```
- 【一手】`platform/external/conscrypt` → `platform/src/main/java/org/conscrypt/TrustedCertificateStore.java`：
  <https://android.googlesource.com/platform/external/conscrypt/+/master/platform/src/main/java/org/conscrypt/TrustedCertificateStore.java>
  （早期布局同文件：<https://android.googlesource.com/platform/external/conscrypt/+/e06e74231e91185621de39de468c4fec6ad76a36/src/platform/java/org/conscrypt/TrustedCertificateStore.java>）

哪些 App 走这条路：显式 `KeyStore.getInstance("AndroidCAStore")` 自己建 `SSLContext` 的。Unity 默认不走。【推断】
**这就是"PEM 一定安全、DER 只在某些路径安全"的准确边界。**

### 1.5 Q1 最终答案

1. **原厂文件是 PEM 文本**（一手，可现场 `head -c 40` 自证）。
2. **DER 在 App 实际使用的 `CertificateFactory` 路径上同样能解析**，所以**装 DER 不是根因**。
3. 你三次写入全废的真正原因在 Q1.6 / Q3 / Q4。

### 1.6 ★ 你的三条写入为什么**逐条**失效（这是今晚最有价值的一段）

App 里 `javax.net.ssl.TrustManagerFactory` 被框架劫持到 `AndroidNSSP` provider → `RootTrustManager` → `SystemCertificateSource` → `DirectoryCertificateSource`。【一手：`ActivityThread.handleBindApplication()` 里对每个 App 进程调用 `NetworkSecurityConfigProvider.install()`；类名 `android.security.net.config.NetworkSecurityConfigProvider`】

而 `SystemCertificateSource` 的目录选择逻辑是**硬编码的优先级**：

```java
private static File getDirectory() {
    if ((System.getProperty("system.certs.enabled") != null)
            && (System.getProperty("system.certs.enabled")).equals("true")) {
        return new File(System.getenv("ANDROID_ROOT") + "/etc/security/cacerts");
    }
    File updatable_dir = new File("/apex/com.android.conscrypt/cacerts");
    if ((sdkVersion == null || sdkVersion >= 34)
            && updatable_dir.exists()
            && !ArrayUtils.isEmpty(updatable_dir.list())) {   // ← 目录非空就用它，彻底忽略 /system
        return updatable_dir;
    }
    return new File(System.getenv("ANDROID_ROOT") + "/etc/security/cacerts");
}
```
- 【一手】`frameworks/base` 现行源码：<https://android.googlesource.com/platform/frameworks/base/+/refs/heads/main/core/java/android/security/net/config/SystemCertificateSource.java>
- 【一手】引入该逻辑的提交（提交信息："Add conscrypt updatable certificates … certificates are taken from conscrypt apex files by default and if that fails, we fallback to the usual system location"）：<https://android.googlesource.com/platform/frameworks/base/+/8b192b19f264a8829eac2cfaf0b73f6fc188d933%5e%21>
- 【一手】Android 14 SDK 镜像同文（第三方镜像站转的 code review）：<https://android-review.googlesource.com/c/platform/prebuilts/fullsdk/sources/+/2704396/1/android-34/android/security/net/config/SystemCertificateSource.java>
- 【一手】Dart/Flutter 侧同一规则的补丁说明（明确写"exists **and is non-empty**"，否则回退）：
  <https://dart.googlesource.com/monorepo/+/7455b4627f9f09b534a23a64439dd7940096d7c9>

于是：

| 你写的地方 | 为什么没用 | 依据 |
|---|---|---|
| `/data/misc/user/0/cacerts-added/` | 这是**用户证书库**。`targetSdk=33 ≥ 24` 时，默认 config **只收系统 CA**，不收用户 CA（除非 App 在自己的 `network_security_config.xml` 里写 `<certificates src="user"/>`） | 【一手】Android 官方《Network security configuration / Trusting added CAs》：<https://developer.android.com/training/articles/security-config#TrustingAddedCAs>　以及 `ApplicationConfig` 里 `targetSdkVersion <= 23` 才 `addCertificatesEntryRef(UserCertificateSource)` |
| `/system/etc/security/cacerts/` | APEX 目录存在且**非空** → `getDirectory()` 直接返回 APEX 路径，**`/system` 那份连打开都不会打开**。写得再对也是死代码 | 【一手】上面 `getDirectory()` 源码 |
| `/apex/com.android.conscrypt/cacerts/` | 目录选对了，但**你写进去的 inode 不在 App 的 mount namespace 里**（详见 Q3） | 【一手/二手】Q3 |

> **这就是"三条全废"的完整机制**：不是格式，是**选择逻辑 + 命名空间**。
> 顺带解释了一个反直觉现象：**你越努力往 `/system` 里拷，越没用**——A14 起那条路是给"APEX 目录不存在/为空"的老设备兜底的。

---

## Q2 SELinux label 与权限

### 2.1 准确 label 是什么【一手·需现场实证】

AOSP 里 `/apex/com.android.conscrypt/cacerts` 下的证书文件 label 是 **`u:object_r:system_file:s0`**，这是所有主流注入脚本统一使用的值：

```sh
# nccgroup/ConscryptTrustUserCerts 的 service.sh
set_perm_recursive /system/etc/security/cacerts root root 644 644 u:object_r:system_file:s0
# 等价的裸命令版本（lefo.me / velog 等多个 2024–2025 帖）
chown root:root /system/etc/security/cacerts/*
chmod 644       /system/etc/security/cacerts/*
chcon u:object_r:system_file:s0 /system/etc/security/cacerts/*
```
- 【一手】`nccgroup/ConscryptTrustUserCerts/service.sh`（原始文件）：<https://raw.githubusercontent.com/nccgroup/ConscryptTrustUserCerts/master/service.sh>
- 【二手】lefo.me《android 14安装CA证书》2025-07-31：<http://lefo.me/2025/07/31/android-14-install-ca/>
- 【二手】velog `@wyzz`《Android 14 이상 버전에서의 인증서 세팅》2026-03-29：<https://velog.io/@wyzz/Android-14-이상-버전에서의-인증서-세팅>
- 【二手】StackExchange 答案（2023-10-17）直接写明"That cert needs to have 644 permissions and the system_file SELinux flag set"：<https://security.stackexchange.com/questions/272686/move-a-user-ca-cert-to-a-trusted-root-cert-in-android-13>

**现场先看真相，别照抄**：

```sh
ls -lZ /apex/com.android.conscrypt/cacerts | head -5
# 期望形如：-rw-r--r-- 1 root root u:object_r:system_file:s0 2xxx-xx-xx xx:xx 9a5ba575.0
```

### 2.2 从 `/sdcard` / `/data/local/tmp` 拷进去，label 会是什么？

两个不同来源，行为不一样：

| 源 | `cp`（不带 -a） | `cp -a` / `cp -p` |
|---|---|---|
| `/sdcard/...`（FUSE，`media_rw_data_file`） | 目标新 inode **继承父目录 label** → 通常直接就是 `system_file` ✅ | **复制源 xattr → `media_rw_data_file`** ❌ App 读不了 |
| `/data/local/tmp/...`（`shell_data_file`） | 同上 → `system_file` ✅ | **带成 `shell_data_file`** ❌ |

依据：`/apex` 与 `/system` 所在挂载（tmpfs / ext4）在 SELinux 里分别是 `fs_use_trans` / `fs_use_xattr` 语义，**新建 inode 时按"父目录类型 + 进程类型"做 type_transition，无匹配则继承父目录**；`cp -a` 会显式写 xattr 覆盖这个继承结果。【推断·高置信，机制层面】

> **所以**：如果你当初用的是 `cp -a`（或 `mv` 一个已带 label 的文件），**label 就是错的**，App 静默读不到。
> 如果你用的是普通 `cp`，label 大概率没问题——那就别在 label 上纠结，**去查 Q3**。
> **不要猜，`ls -Z` 一看就知道。这才是本节的价值。**

### 2.3 可直接抄的修正命令

```sh
# 变量
D=/apex/com.android.conscrypt/cacerts
F=$D/fd8b2b01.0

# 1) 权限 + 属主
chown 0:0 "$F"
chmod 644 "$F"

# 2) label（toybox 自带 chcon；没有就用 KSU 的 busybox）
chcon u:object_r:system_file:s0 "$F" || /data/adb/ksu/bin/busybox chcon u:object_r:system_file:s0 "$F"

# 3) 更稳的写法：以同目录原厂文件为模板（避免记错类型名）
chcon --reference="$D/$(ls $D | head -1)" "$F"

# 4) 目录本身也要能 search（如果你把整个目录 bind 上去，目录 label 同样关键）
chcon u:object_r:system_file:s0 "$D"

# 5) 验证（唯一可信的验证）
ls -lZ "$F"
```

`restorecon` 在这个场景**不要用**：tmpfs 上的文件不参与 `file_contexts` 的默认恢复路径匹配，结果常常是"看起来跑了但没改"。【推断】

### 2.4 ★ 用 logcat 一击定位（强烈建议先做这个）

因为 `DirectoryCertificateSource.readCertificate()` 解析失败/打不开时**只打一条 `Log.e` 然后 `return null`**，所以：

```sh
# 拉起 App 后立刻抓
logcat -d -v brief | grep -iE "DirectoryCertificateSrc|TrustedCertificate|CertPathValidator|TrustAnchor|CertPath" | tail -40
```
- 有 `Failed to parse certificate` / `... does not contain a certificate` → **格式或 label/读权限问题**（回到 Q1/Q2）
- 有 `Trust anchor for certification path not found` → **CA 根本没进 store**（Q3 namespace / Q1.6 选择逻辑）
- **什么都没有** → 说明这个 trust manager 压根没被调用 → **App 可能不是用系统 store 校验的**（转 Q7 / 逆向）

> 备注：root 域（`u:r:ksu:s0`）读 logcat 可能被 SELinux 挡；被挡就换 `dmesg`/`logcat -b main` 试探，或从 App 侧触发后再抓。

### 2.5 Android 14+ 的 SELinux 会不会阻止 App 读这个目录？

**不会。** `system_file` 对 `untrusted_app` 是 `r_file_perms` 可读的（全机所有 App 都要读 CA store），这也是为什么任何"证书模块"都能生效。A14+ 新增的墙**不是 SELinux**，而是：①`getDirectory()` 的路径选择（Q1.6）；②mount namespace（Q3）。【一手/推断】

---

## Q3 ★ `/apex/com.android.conscrypt/cacerts` 的挂载语义（最容易搞错）

### 3.1 那个目录是什么？谁在什么时候弄的？

| 事实 | 依据 |
|---|---|
| Android 14 起系统根证书**实际来源** = `com.android.conscrypt` APEX 内的 `cacerts/`；APEX 由 Mainline（Google Play 系统更新）投递，**内容不随 ROM 走** | 【一手】AOSP《Conscrypt》文档（2026-10-11）：<https://source.android.com/docs/core/ota/modular-system/conscrypt> |
| 该目录**在只读 APEX 镜像里**，正常不可写；能 `touch` 说明**其上有 tmpfs 或 bind mount**（可能来自你之前的实验，也可能来自 init/KSU 的中间层） | 【推断】+ 你的实测（三处 tmpfs rw） |
| 你的三处都是 tmpfs rw，**这本身就是异常信号**：原厂 `/data/misc/user/0/cacerts-added` 在 `/data`（ext4/f2fs），不可能是 tmpfs | 【推断·高】→ 说明你所在 shell 的 namespace 里有别人挂的覆盖层 |

**现场定性**（先搞清楚自己在看什么）：

```sh
# 你自己 ns 里的挂载
grep -E "cacerts|/apex" /proc/self/mountinfo

# App 进程 ns 里的挂载（关键对照！）
P=$(pidof com.RoamingStar.BlueArchive | awk '{print $1}')
grep -E "cacerts" /proc/$P/mountinfo

# 逐个看：tmpfs? mount id? 传播标记 shared/private?
cat /proc/self/mountinfo | awk '$5 ~ /cacerts/ {print $1, $3, $5, $7, $9}'
```
判读：`mountinfo` 第 7 列是挂载点，其后 `shared:N` = 共享传播，`-` 前的可选字段里若是 `master:N` = slave，**完全没有 shared/master 标记 = private**。
**如果 App 的 mountinfo 里根本没有一条 tmpfs 挂在 `/apex/com.android.conscrypt/cacerts`，而你的有 → 你已经拿到答案了：你写的是自己 ns 里的影子目录。**

### 3.2 ★ 权威解释：为什么"dev/ino 一致"和"App 看不见"能同时成立

这是本次调研最关键的一条，直接解决你笔记里那个矛盾（"有说是 private propagation，但 `nsenter` 进去看 dev/ino 是一致的"）。

> **`/apex` 这个挂载点被设成了 private propagation。**
> private 的语义**不是**"每个进程看到不同的 `/apex`"，而是：**基础挂载对所有 namespace 可见、`dev/ino` 完全相同；但此后在任一 namespace 里新增的 mount 不会向任何其它 namespace 传播。**

- 【二手·但解释精确】velog `@nzero`《[AOS] Android 14 이상 https 인증서 시스템 인증서로 설치하기》2024-11-06：
  <https://velog.io/@nzero/AOS-Android-14-이상-https-인증서-시스템-인증서로-설치하기>
  > "마운트는 기본적으로는 'SHARED'로 생성되며 … 자동으로 전파 된다. … 그럼 우리가 인증서를 삽입해야 할 /apex는 어떨까? 안타깝게도 'PRIVATE' 설정이 되어 있어 마운트에 대한 변경이 [전파되지 않는다]"
  > （译：挂载默认是 SHARED、会自动跨 namespace 传播；但我们要塞证书的 `/apex` 不幸被设成了 **PRIVATE**，所以对挂载的改动**不会传播**。）

**于是你那个观察完全正确、且不矛盾**：

| 你看到的现象 | 真相 |
|---|---|
| `nsenter` 进 App ns，`stat` 出来的 `dev/ino` 和你自己 ns 一样 | ✅ 对。基础 `/apex/...cacerts` 挂载是**同一个**，元数据当然一样 |
| App 就是不信任你的 CA | ✅ 也对。**你写的是"目录里的一个文件"还是"一个挂载"取决于你当时的操作**：<br>· 若是 `cp` 进"原厂只读目录"→ 根本写不进去（除非 tmpfs）<br>· 若是先 `mount -t tmpfs` 再 `cp` → **这个 tmpfs 只在你 ns 里存在**，App ns 完全没有它，`dev/ino` 一致是因为你看的是**你自己**的 ns |

**判别方法（一条命令定生死）**：

```sh
P=$(pidof com.RoamingStar.BlueArchive | awk '{print $1}')
# 从 App 的 namespace 里看：你的文件到底在不在、多大、什么 label、能不能读
nsenter --mount=/proc/$P/ns/mnt -- /system/bin/ls -lZ /apex/com.android.conscrypt/cacerts/ | grep fd8b2b01
nsenter --mount=/proc/$P/ns/mnt -- /system/bin/cat /apex/com.android.conscrypt/cacerts/fd8b2b01.0 | head -c 40; echo
```
- `ls` 找不到 → **namespace 问题**（本文 §3.4 解决）
- 找得到、`cat` 出 `-----BEGIN...` 或 `0\x82` → **namespace 没问题**，问题在 label（Q2）或 App 不读这个 store（Q7）
- `cat: Permission denied` → **label/权限**（Q2）

> ⚠ `nsenter --mount=` **只切换 mount namespace，不切换 root/cwd**。用它做判断时必须用**绝对路径**（上面命令已如此），否则你测的是自己的目录树。这也是很多"我 nsenter 进去看到一样"的误判来源。

### 3.3 正确注入方式：往 zygote 的 namespace 里挂

**原理**：App 进程是 `zygote`/`zygote64` `fork()` 出来的，**fork 会复制父进程的 mount table**。所以：

1. 把合并后的证书目录 `mount --rbind` 到 **`zygote64`（以及 `zygote`）的 namespace** → 从此**新 fork 的每个 App 进程都自带这份证书**；
2. 对**已经在跑**的 App 进程再各做一次（或直接杀掉重拉）。

这被两个项目在 README 里明说：

> "On devices that use the Mainline Conscrypt APEX, its service waits for boot completion, prepares the merged store with the required ownership and SELinux labels, and **mounts it into the zygote and application process namespaces**."
> ——【一手】AlwaysTrustUserCerts（magisk.dev 模块页，**2025-05-21**）：<https://magisk.dev/modules/alwaystrustusercerts/>

> "内置 Bind Mount 模式（默认）… 将合并后的工作目录挂到系统证书目录，并**在 Android 14+ 下自动向 zygote / zygote64 挂载命名空间注入，解决 `/apex` 私有挂载传播问题**"
> ——【一手】`jjh138792/System-CA-Manager` README（**2026-10-31**）：<https://github.com/jjh138792/System-CA-Manager>

> "Android apps don't all share one mount namespace, so a mount done in one shell is invisible to everyone else. The injection script **walks every mount namespace on the device and uses `nsenter`** to do the bind-mount in each."
> ——【二手】ZAP 官方博客《Intercepting all Android traffic with ZAP》，**2026-11-10**：<https://github.com/zaproxy/zaproxy-website/blob/b5c9e4faf029c1cd953a075bcf75d19faf6fd9a9/site/content/blog/2026-11-10-intercepting-android-traffic/index.md>

### 3.4 ★ 可直接抄的完整脚本（已适配你的现场：ksu 上下文 / 无 python / `am` 被挡）

存成 `/data/local/tmp/ca_inject.sh`，`chmod 755` 后 `su -c sh /data/local/tmp/ca_inject.sh` 跑。

```sh
#!/system/bin/sh
# CA inject for Android 14+ via zygote mount-namespace injection.
# Derived from nccgroup/ConscryptTrustUserCerts + HTTP Toolkit's android-14 flow.

set -u
PKG=com.RoamingStar.BlueArchive
SRC_CERT=/data/local/tmp/fd8b2b01.0          # 你的 CA（DER 或 PEM 都行，下面会归一化）
NAME=fd8b2b01.0
WORK=/data/local/tmp/cacerts-work
APEX=/apex/com.android.conscrypt/cacerts
SYS=/system/etc/security/cacerts
BB=/data/adb/ksu/bin/busybox

log() { echo "[ca-inject] $*"; }

# ---------- 0. 前置检查 ----------
[ -f "$SRC_CERT" ] || { log "missing $SRC_CERT"; exit 1; }
[ -x /system/bin/nsenter ] || { log "no nsenter"; exit 1; }

# ---------- 1. 合并原始证书到暂存目录 ----------
rm -rf "$WORK"; mkdir -p "$WORK" || exit 1
if [ -d "$APEX" ] && [ -n "$(ls -A "$APEX" 2>/dev/null)" ]; then
    log "seeding from APEX ($(ls -A $APEX | wc -l) certs)"
    cp -f  "$APEX"/* "$WORK"/ 2>/dev/null
else
    log "seeding from /system"
    cp -f  "$SYS"/*  "$WORK"/ 2>/dev/null
fi

# ---------- 2. 归一化成 PEM（两路消费端都安全） ----------
if head -c 27 "$SRC_CERT" 2>/dev/null | grep -q -- '-----BEGIN CERTIFICATE'; then
    log "input is already PEM"
    cp -f "$SRC_CERT" "$WORK/$NAME"
else
    log "input looks like DER -> converting to PEM"
    if openssl x509 -inform DER -in "$SRC_CERT" -out "$WORK/$NAME" 2>/dev/null; then
        :
    else
        # 没有 openssl 时退回 DER 原样（CertificateFactory 也能吃）
        log "no usable openssl; keeping raw DER (still OK for Java TrustManager)"
        cp -f "$SRC_CERT" "$WORK/$NAME"
    fi
fi

# ---------- 3. 权限 + label（目录本身也要！） ----------
chown -R 0:0 "$WORK"
chmod 755 "$WORK"
chmod 644 "$WORK"/*
if chcon -R u:object_r:system_file:s0 "$WORK" 2>/dev/null; then
    log "chcon ok (toybox)"
else
    $BB chcon -R u:object_r:system_file:s0 "$WORK" 2>/dev/null && log "chcon ok (busybox)" \
      || log "WARN chcon failed - verify with: ls -lZ $WORK | head"
fi

# ---------- 4. 挂到 zygote / zygote64 的 namespace（新 App 继承） ----------
for z in $(pidof zygote64) $(pidof zygote); do
    [ -d /proc/$z ] || continue
    log "inject into zygote ns pid=$z"
    nsenter --mount=/proc/$z/ns/mnt -- /system/bin/mount --rbind "$WORK" "$APEX" 2>/dev/null \
        && log "  $APEX ok" || log "  $APEX FAILED"
    nsenter --mount=/proc/$z/ns/mnt -- /system/bin/mount --rbind "$WORK" "$SYS"  2>/dev/null \
        && log "  $SYS ok"   || log "  $SYS FAILED"
done

# ---------- 5. 已在跑的 App 进程也补一遍 ----------
for p in $(pidof "$PKG"); do
    log "inject into running app pid=$p"
    nsenter --mount=/proc/$p/ns/mnt -- /system/bin/mount --rbind "$WORK" "$APEX" 2>/dev/null
    nsenter --mount=/proc/$p/ns/mnt -- /system/bin/mount --rbind "$WORK" "$SYS"   2>/dev/null
done

# ---------- 6. 验证（在 App 的 ns 里） ----------
P=$(pidof "$PKG" | awk '{print $1}')
if [ -n "${P:-}" ]; then
    log "--- verify inside app ns (pid=$P) ---"
    nsenter --mount=/proc/$P/ns/mnt -- /system/bin/ls -lZ "$APEX" 2>&1 | grep -E "$NAME|total" 
    nsenter --mount=/proc/$P/ns/mnt -- /system/bin/sh -c "head -c 40 $APEX/$NAME" 2>&1; echo
else
    log "app not running; zygote injection alone is enough for the next launch"
fi
log "done"
```

**逐段解释（对应你要求的"核心 shell 逻辑摘出来，逐步解释"）**

| 步骤 | 为什么必须这么做 | 不做会怎样 |
|---|---|---|
| 1 先把原厂证书 **拷到暂存目录** | 一旦你 `mount` 覆盖了目标目录，**原来目录里的证书就被盖住了**，不先拷出来就全丢（所有版本都强调 "Otherwise, when we add the mount we can't read the current certs anymore"） | App 只信任你那一张 CA，其它域名全挂 |
| 1' 源优先用 **APEX** | A14+ 的 APEX store 才是"现行"的那份（可能比 `/system` 那份新，Mainline 单独更新过） | 少信任几张新根证书 |
| 2 归一化成 **PEM** | 兼容性最大化（Java + BoringSSL/Flutter 都吃 PEM）；成本 0 | 未来若走 BoringSSL 旁路会踩坑 |
| 3 `chown 0:0 / 644` | App 以 `untrusted_app` 读，需要 world-readable | `EACCES`，静默 `return null` |
| 3' `chcon -R system_file` **且包含目录** | bind mount 之后，`/apex/.../cacerts` 这个路径解析到的是**你暂存目录的 inode**，它的 label 决定 App 能否 `search` | 目录 `shell_data_file` → 整个目录进不去，文件 label 再对也没用 |
| 4 进 **zygote64/zygote** ns 挂 | fork 复制 mount table → 之后所有新 App 进程自动继承；这是"一次注入、长期有效"的关键 | 只挂自己 ns = 完全无效 |
| 5 对**已运行** App 补挂 | 已存在的进程 mount table 是 fork 时快照，不会回溯更新 | 必须杀掉重拉（见 Q4） |
| 6 在 **App ns 里**验证 | 只有 App 视角的 `ls -Z` / `cat` 才是证据；自己 ns 的验证全是自我安慰 | 误判"已生效" |

**几个容易翻车的细节**

1. **`--rbind` 而不是 `--bind`**：如果你覆盖的源目录里，某些条目本身是挂载点（Magisk/元模块会给每个证书文件做单文件 bind，`mount | grep cert` 能看到 `/dev/block/dm-7 on /system/etc/security/cacerts/bf64f35b.0`），`--bind` **不会**递归带过去，结果就是"证书全没了"。
   - 【二手】微信公众号《Android Conscrypt 与 TLS 证书安全》2025-11-23（明确写 "Wrong: `--bind` / Correct: `--rbind`"）；旁证【二手】NVISO 2025-06-05（A15 上装完模块"所有证书消失"，根因就是单文件挂载没递归）：<https://blog.nviso.eu/2025/06/05/intercepting-traffic-on-android-with-mainline-and-conscrypt/>
2. **`mount` 要用绝对路径**：`nsenter -- cmd` 不继承你的 `PATH`。统一写 `/system/bin/mount`、`/system/bin/ls`。
3. **KSU 的 App Profile / "卸载模块(umount)"**：如果这个游戏在 KSU 里被设成"卸载模块"，KSU 会在该进程 ns 里 **umount 掉你的挂载层**，证书白装。
   - 【一手】CertBridge 文档明确："对某 App 开启「卸载模块 / Umount / DenyList+umount / 排除修改」后，该进程命名空间里证书层也会被卸掉"：<https://eikeitsu.github.io/CertBridge/guide/hide.html>
   - 你的 KSU 现在没装模块，但**如果给这个游戏开过任何"隐藏 root"配置，先关掉**。
4. **不用重启 zygote**：zygote 的 mount table 是运行时可改的（上面就是运行时改），`kill zygote` 会让系统软重启、反而丢掉注入。**不用、也不要重启 zygote。**
5. **不用重启设备**：全部运行时可做；重启后需要重跑（要持久化就做成模块，见 Q6）。

### 3.5 你的现场适配：`am` 被挡怎么"冷启"

你的笔记里写明 `am` / `cmd package` / `settings` 在 `u:r:ksu:s0` 下都 `Failed transaction`。所以**不要用 `am force-stop`**，直接杀进程（对本目的等价）：

```sh
# 杀干净（含 Unity 的多个进程）
for p in $(pidof com.RoamingStar.BlueArchive); do kill -9 $p; done
sleep 1
pidof com.RoamingStar.BlueArchive   # 期望空

# 拉起（你的笔记里验证过 monkey 可用）
monkey -p com.RoamingStar.BlueArchive -c android.intent.category.LAUNCHER 1
```
> 注意：`kill -9` 后 App 可能被 launcher/系统自动拉起；先 `kill` 再立刻 `monkey` 更稳。若要"必须冷启"的确定性，可 `kill` 后等 2 秒确认 `pidof` 为空再 `monkey`。

### 3.6 `ys1231/MoveCertificate` 到底做了什么（逐行对照）

- 仓库：<https://github.com/ys1231/MoveCertificate>（主仓）、<https://github.com/ys1231/MoveCertificate-ksu>（KSU 分支）、KSU 模块索引页 <https://modules.kernelsu.org/en/modules/MoveCertificate/>
- **最新 release：v1.6.2，2026-09-02**（`domain_search → github_releases` 实查）；README 声称 **Android 7–17**、兼容 `magisk v20.4+ / kernelsu / APatch`
- **它的核心逻辑与 HTTP Toolkit / nccgroup 那套同源**（不是独立发明）。它做的是：
  1. **收集**：把「原厂系统 CA（A14+ 从 `/apex/com.android.conscrypt/cacerts`，否则 `/system/etc/security/cacerts`）」+「用户 CA（`/data/misc/user/<id>/cacerts-added`）」拷进一个暂存目录（`$MODDIR/system/etc/security/cacerts` 或 `/data/local/tmp/...`）；
  2. **建层**：对目标目录 `mount -t tmpfs tmpfs`，再把暂存内容搬回去 → 得到一个**可写的影子 store**；
  3. **下推**：用 `nsenter` 进入 **zygote / 各 App 进程** 的 mount namespace，`mount --rbind` 影子 store 到 `/apex/com.android.conscrypt/cacerts`；
  4. **修属性**：`chown root:root`、`chmod 644`、`chcon u:object_r:system_file:s0`；
  5. **重启后自动重做**（模块 `service.sh` 等 `sys.boot_completed`）。
- **它的两个坑（也是所有同类模块的坑）**：
  - README 里"Android 系统使用 der"这句**是错的**（见 Q1.3），照它转 DER 不会更糟但也没用；
  - 它 README 里说"优先用系统设置安装证书"——在你的设备上**这条路对你无效**，因为 `targetSdk=33` 不收用户 CA（Q1.6）。**别按它推荐的主流程走。**

---

## Q4 `TrustManagerFactory` / `AndroidCAStore` 的缓存

### 4.1 结论表

| 问题 | 答案 | 依据 |
|---|---|---|
| 已在运行的 App 进程会读到新 CA 吗？ | **不会，永远不会。** | 【一手】`SystemCertificateSource.NoPreloadHolder.INSTANCE` 是**进程内单例**，类的 static 初始化只做一次 |
| `TrustManagerFactory.getTrustManagers()` 结果被缓存吗？ | **trust manager 对象本身每次新建**，但它**依赖的证书源是缓存的**。所以"再调一次"没用 | 【一手】`RootTrustManagerFactorySpi.engineInit/engineGetTrustManagers` + `SystemCertificateSource.getInstance()` |
| 缓存在哪几层？ | ①`SystemCertificateSource`（进程单例）②`DirectoryCertificateSource`（目录快照/mCertificates 缓存）③`TrustedCertificateStore`（若走 `AndroidCAStore` 路径，有静态实例 + `update()`） | 【一手】源码 |
| 同进程重新 `SSLContext.init(null, tm, null)` 会拿到新 store 吗？ | **不会。** 因为 `tm` 背后还是同一个 `SystemCertificateSource` 单例 | 【推断·高】 |
| 除了 force-stop 冷启，有别的刷新方式吗？ | 有设计上的：`CertificateSource.handleTrustStorageUpdate()`，由系统在信任库变更时（`android.security.action.TRUST_STORE_CHANGED`）触发。**但**：这是受保护广播，且**不会**让 `SystemCertificateSource` 重新选目录（目录选择只在类初始化时算一次）；在你的 `ksu` 上下文里 `am` 直接被挡 → **实务上不可用** | 【一手】`DirectoryCertificateSource.handleTrustStorageUpdate()` / `WebViewCore` 里 `TRUST_STORAGE_UPDATED` 分支：<https://android.googlesource.com/platform/frameworks/base/+/93ba4fedebb78ba47c24e8472c8960ea8fdc933a%5E%21/core/java/android/webkit/WebViewCore.java>；【二手】你的实测（`am` 被挡） |

### 4.2 实操建议

1. **注入顺序必须是：先注入（含 zygote ns）→ 再杀进程 → 再启动**。反过来一定失败。
2. 判断"是不是缓存问题"的最快方法：注入后 `kill -9` 再启；若结果变化 → 是缓存/时序；若毫无变化 → 是 namespace/store 选择（Q3/Q1.6）。
3. **不要指望热更新**：即便 `am broadcast` 能用，`getDirectory()` 的返回值也已固化。A14+ 没有"热加 CA"这条路。【推断·高】

---

## Q5 Android 17 / SDK 37 有什么新变化

### 5.1 已确认的变化（官方）

| 变化 | 影响你吗 | 依据 |
|---|---|---|
| **Certificate Transparency：Android 16 可选启用，Android 17 对 `targetSdk≥37` 默认强制** | **不影响**。你 `targetSdk=33` → CT 不强制，我们的自签 CA 不需要 SCT，也不需要把证书提交进 CT log | 【一手】Android 17 行为变更（最后更新 **2026-10-31**）：<https://developer.android.com/about/versions/17/behavior-changes-17>　功能清单（**2026-11-09**）：<https://developer.android.com/about/versions/17/summary>　中文：<https://developer.android.google.cn/about/versions/17/summary?hl=zh-cn> |
| CT 机制细节：Android 16（API 36）起才有平台级 CT；无 log list 或 log list 超 70 天 → **自动关闭强制** | 同上，不影响 | 【一手】Google CT 团队 2025 峰会材料：<https://transparency.dev/pdfs/summit2025/android_ct.pdf> |

> ⚠ 但 CT 这条要**留一个心眼**：如果哪天为了别的目的把 `targetSdk` 抬到 37（比如重签 APK），CT 会立刻变成新的一堵墙，而且**自签 CA 永远过不了 CT**。**别抬 targetSdk。**

### 5.2 CA store 位置/策略有没有变？

**没有。** 截至 AOSP 现行文档（2026-10-11 更新）与 `SystemCertificateSource` 现行源码，规则仍是：
`system.certs.enabled=true` → `/system`；否则 `sdkVersion>=34 && APEX 目录存在且非空` → APEX；否则 `/system`。
Android 17 没有引入第四条路径，也没有改 `getDirectory()`。【一手】

### 5.3 厂商 ROM 的已知坑（你的机器是 OnePlus / ColorOS，国行）

| 坑 | 现象 | 应对 |
|---|---|---|
| `/system` 是 **EROFS + 动态分区 + AVB**，不是独立可 remount 分区 | `mount -o rw,remount /system` 失败 | 别 remount，用 tmpfs/bind（本文路线） |
| 部分 ROM 把 `/system/etc/security/cacerts` 做成**符号链接**或加了自己的影子目录 | `ls -l /system/etc/security/cacerts` 显示 `->`；或里面混入厂商 CA | `ls -ld` 先看；是链接就 `readlink -f` 找真实路径再加 |
| 国行 ROM **预装自己的 CA**、且可能带"安全支付"类环境检测 | 目录里多出 `bytedance`/`alipay` 之类 | 只增不改，别删原厂证书（删了会触发一堆系统异常） |
| 厂商可能在 `init` 里把 `/apex/.../cacerts` **再做一层 bind**（这就是你看到 tmpfs 的原因之一） | 你在 shell ns 里 `touch` 成功但 App 看不到 | 见 Q3.2 判据；以 App ns 为准 |
| ColorOS/HyperOS 的"应用行为记录/权限监控"可能拦 `mount` | `mount` 返回 `EPERM` 而非 `EACCES` | `dmesg | grep avc` 看 denial；必要时临时 `setenforce 0` 验证（**验证完立刻恢复**） |

### 5.4 额外提醒：A15+ 的"每张证书一个挂载"

Android 15 起（在 Magisk/模块环境下尤其明显）`/system/etc/security/cacerts/*.0` **每个文件都可能是一个独立 bind mount**：

```
$ mount | grep cert
/dev/block/dm-7 on /system/etc/security/cacerts/bf64f35b.0 type ext4 (ro,seclabel,noatime)
/dev/block/dm-7 on /system/etc/security/cacerts/5acf816d.0 type ext4 (ro,seclabel,noatime)
```
- 【二手】NVISO Labs，**2025-06-05**：<https://blog.nviso.eu/2025/06/05/intercepting-traffic-on-android-with-mainline-and-conscrypt/>
→ 所以覆盖时**必须 `--rbind`**，否则你会把 100+ 张证书"覆盖成空目录"，然后所有 TLS 全挂（NVISO 的原话就是"all of the certificates have disappeared"）。

---

## Q6 现成方案横向对比

> 星级/更新时间取自各仓库页与 magisk.dev / modules.kernelsu.org 收录页（调研时点 2026-11-14）。

| 方案 | 类型 | 支持 Android | KSU | 原理 | A14+ 还行吗 | 最近更新 |
|---|---|---|---|---|---|---|
| **ys1231/MoveCertificate** | Magisk/KSU/APatch 模块 | README 称 **7–17** | ✅ | tmpfs 影子 store + `nsenter` 下推到 zygote/App ns | ✅（就是为 A14+ 写的） | **v1.6.2 / 2026-09-02** |
| **AlwaysTrustUserCerts**（NVISO / Jeroen Beckers） | Magisk/KSU 模块 | **7 – 16 Beta** | ✅ | 启动完成后合并 store，"mounts it into the **zygote and application process namespaces**" | ✅ 文档最清楚 | **v1.3 / 2025-05-21** |
| **MagiskTrustUserCerts**（SekiBetu fork） | Magisk/KSU/KSU-Next | 广（含 mainline/non-mainline 双路径） | ✅ | 用户 CA → 系统 CA 目录 + 覆盖挂载 | ✅ | 约 2025-06-24（2.6k★） |
| **hax3xploit/MagiskTrustUserCerts-Android14** | Magisk fork | 14+ | ❌（Magisk 向） | 同上，专修 A14 路径 | ✅ | 约 2026-05 |
| **Cert-Fixer**（pwnlogs） | Magisk 模块 | 14/15 实测（API 34/35） | ❌ 未见 KSU 声明 | 开机把用户 CA 拷进系统目录 | ✅（有 bootloop 修复史，v1.1） | 约 2026-07（289★） |
| **TrustUserCertificates**（lupohan44） | Magisk 模块 | 8.0+（A14 实测） | ❌ | **明确写了 `inject_into_apex()`，逻辑抄 HTTP Toolkit** | ✅ | 2024-01（老但干净） |
| **ConscryptTrustUserCerts**（nccgroup / Fox-IT） | Magisk 模块 | A14 | ❌ | 就是 HTTP Toolkit 那套 `service.sh` 的模块化 | ✅ | 2023-10 起（原版） |
| **custom-certificate-authorities**（Magisk-Modules-Alt-Repo） | Magisk/KSU/APatch | 14+ 明示 | ✅ | 双目录注入 + **DER→PEM 转换** + 多用户 | ✅ | **2026-06-15**（magisk.dev 页） |
| **binbard/android-system-ca-overlay** | **KernelSU 模块** | 14+（**含 Android 16**） | ✅ | 开机拷原厂 store + 加自己的 → bind 到 APEX 路径，**不写 /system、不写 APEX 磁盘** | ✅ | **2026-08-07** |
| **System CA Manager**（`cacerts_bind_manager`，jjh138792） | KSU/SukiSU/APatch + Magisk | 7 – 14+ | ✅ **KSU 原生** | 纯内置 bind mount 引擎，**不依赖元模块**；`post-mount.sh` 在元模块之后执行；**显式处理 `/apex` private propagation，向 zygote/zygote64 注入**；带 WebUI | ✅ **最贴合你的场景** | **2026-10-31** |
| **CertBridge**（eikeitsu） | 模块 + SuSFS | 14+ | ✅ | bind mount + `try_umount` 隐藏 | ✅ | 2026 |
| **RootCertManager**（shiqiufeng） | SukiSU/KSU/Magisk/APatch | 14+ | ✅ | 往 `module/system/etc/security/cacerts/` 丢 `.0` 即可 | ✅ | 2026 |
| **JustTrustMe**（Fuzion24） | LSPosed 模块 | 老（4.x–9 时代为主） | ✅(LSPosed) | hook `X509TrustManager`/`SSLContext`/okhttp | ⚠ 高版本常失效、对新 TLS 栈覆盖不全 | 长期未更新 |
| **TrustMeAlready**（ViRb3） | LSPosed 模块 | 较广 | ✅(LSPosed) | hook 各类 TrustManager / HostnameVerifier / okhttp | ⚠ 取决于 App 是否走 Java 校验 | v1.11（2023 前后） |
| **UserCABridge**（takattowo） | **LSPosed 模块** | **8–16（API 26–36）** | ✅(LSPosed) | 把"用户 CA 源"塞进**框架默认 trust 配置**，**不碰任何证书文件** | ✅ 思路最干净 | **2026-11-01** |

### 6.1 在「Android 17 + KernelSU」上最可能成功的是谁

**排序（结合你的现场）**：

1. **手动 nsenter 注入脚本（本文 §3.4）** —— 不是"模块"，但**这是最可能在 A17+KSU 上立刻成功的**：不依赖元模块、不依赖模块框架、绕开所有 ROM 适配问题、10 秒可回滚（`umount` 或重启）。**Android 17 太新，任何模块的"7–16"声明都不能假设覆盖 17；手写脚本没有这个风险。**
2. **System CA Manager（cacerts_bind_manager）** —— 如果要在重启后仍然生效，这是**唯一在 README 里明确写"解决 `/apex` 私有挂载传播 + 向 zygote/zygote64 注入 + 不依赖 KSU 元模块"**的模块，且 `post-mount.sh` 专门处理 KSU 的挂载时序（"确保排在元模块和其他模块的目录级挂载之后"）。更新时间 2026-10-31，是这一批里最新的。
3. **AlwaysTrustUserCerts v1.3 / MoveCertificate v1.6.2** —— 都成熟，但一个是 2025-05（早于 A17），一个 README 含错误格式指引。可作备选。
4. `binbard/android-system-ca-overlay`（KSU 专用、含 A16 声明）—— 干净可读，适合当"第二实现"对照。

**⚠ 一个必须先确认的前置条件（很多人栽在这）**：
现代 KernelSU **把模块挂载能力拆给了"元模块(metamodule)"**。官方文档原话：

> "可插拔的模块基础架构，支持无系统修改。**安装 meta-overlayfs 等 metamodule 来启用模块挂载。**"
> ——【一手】<https://kernelsu.org/zh_CN/>（首页）；元模块文档：<https://github.com/kernelsu-next/kernelsu-next/blob/aefab5770c92c0db4b49c6127227d88bd81d5327/website/docs/zh_CN/guide/metamodule.md>
> "**如果没有安装元模块，依赖挂载的模块，其挂载功能将不会生效。**"

→ 所以在你的机器上装模块前**先确认**：
```sh
ls /data/adb/modules/            # 看有没有 meta-overlayfs 之类
getprop | grep -iE "ksu|kernelsu"
```
没有元模块 → **所有靠 `$MODDIR/system/` overlay 的模块都不会挂载**（但自带 `post-mount.sh`/`service.sh` 自己做 bind mount 的模块，如 System CA Manager，仍可用）。**这也是我把"手动脚本"排第一的原因：它不依赖任何这套机制。**

---

## Q7 有没有"根本不用装 CA"的旁路

### 7.1 方案清单（按可行性排序）

| # | 方案 | 需改什么 | 对 il2cpp/Unity 有效性 | 依据/备注 |
|---|---|---|---|---|
| 1 | **Frida hook `X509TrustManager.checkServerTrusted`**（或 `SSLContext.init`） | 不改 App/系统；只需 `frida-server`（KSU 下可跑） | **高**。Unity 走 JNI Java TLS，hook Java 层即可；且**不依赖 LSPosed** | 【推断·高】+ 你的现场（已确认走 TrustManagerFactory） |
| 2 | **LSPosed 模块 hook 框架类**（UserCABridge / JustTrustMe / TrustMeAlready） | 需 LSPosed + 作用域勾选该游戏 | **中高**。关键：这类模块 hook 的是 **`android.security.net.config` / `javax.net.ssl` 等框架类**，**不是 App 自己的类** → 你说的"进程内 `XposedBridge` 是混淆替身类"**不影响它** | 【一手】UserCABridge README（2026-11-01）：<https://github.com/takattowo/usercabridge> 明确"includes Android's existing user-installed CA source alongside system CAs in **framework default trust configurations**" |
| 3 | **`system.certs.enabled=true`** + 把 CA 放 `/system/etc/security/cacerts` | 需在 **zygote 起来之前**设属性（= 要模块 + 重启） | **高**（若属性生效）；但落地成本高 | 【一手】raise-isayan/OverrideSysPropModule README（2023-09-08）：<https://github.com/raise-isayan/OverrideSysPropModule> |
| 4 | 重签 APK + 加 `network_security_config.xml`（`<certificates src="user"/>` 或直接信任） | 改 APK + 重签 | 低（游戏有签名/完整性校验，且 `libil2cpp` 有 ACE hash pin，你已经踩过 SIGBUS） | 你的实测 |
| 5 | 改 conscrypt 全局宽松化（"有没有属性/环境变量放宽校验"） | — | **没有这种开关** | 见 7.2 |

### 7.2 关于"conscrypt 有没有可配属性"

- **唯一的官方开关就是 `system.certs.enabled`**，而且它**不是"放宽校验"**，只是**换目录**（把 store 从 APEX 切回 `/system`）。它不会让校验变松。【一手：`SystemCertificateSource.getDirectory()` 源码】
- 没有 `conscrypt.trustAll` / `-Djavax.net.ssl.trustStore` 之类可用开关：Android 的 `Platform` 固定走 `AndroidCAStore`/`NetworkSecurityConfig`，`javax.net.ssl.trustStore` 系统属性在 Android 上**不生效**。【推断·高】
- `setprop system.certs.enabled true` **直接在你现在的 shell 里试是没用的**：`System.getProperty()` 在 libcore 里是**进程启动时的属性快照**，而 App 进程是 zygote `fork()` 出来的 → 它们继承的是 **zygote 启动时**的快照。必须在 **zygote 之前**（`post-fs-data` 阶段，且 KSU 没有 Magisk 的 `resetprop`，得自己塞 `/data/local/tmp/resetprop` 或用 `magiskboot` 工具链）设好，再重启。【推断·高】
  → **性价比低，不建议作为第一步。**

### 7.3 你那个「XposedBridge 是混淆替身」的问题，要分开看

你的原话是：这台机器上 LSPosed 的 Java hook 对**这个游戏**无效（进程内 `XposedBridge` 是混淆替身类）。这句话要拆成两半：

| 情形 | 会不会受影响 | 原因 |
|---|---|---|
| 模块 hook **App 自己的类/方法**（如 `XposedHelpers.findAndHookMethod("com.xxx.Foo", …)`） | **会**。App 自带了一个同名 `de.robv.android.xposed.*` 混淆替身，模块按名查找会命中错的东西 | 类加载器遮蔽 |
| 模块 hook **框架/系统类**（`javax.net.ssl.*`、`android.security.net.config.*`、`java.net.*`） | **不会**。这些类在 **boot classpath**，由 LSPosed 的注入器自己的 classloader 解析，App 里的同名类无法遮蔽 | 【推断·高】 |
| LSPosed **能否注入进这个进程**（Zygisk/`app_process` 层） | 只要 App 没做反 LSPosed 检测就没问题 | 你的 ACE 反作弊可能检测 `/data/adb/modules`、`maps` 里的 `lspd`、`XposedBridge` 符号 |

→ **所以"LSPosed 对这个游戏无效"这个结论下得太早了。** 值得用 **UserCABridge**（它只改框架 trust 配置，不 hook App 代码，API 26–36，正好覆盖 36 但**未声明 37**）或 **JustTrustMe 系** 试一次，成本 10 分钟。

---

## 附 A：一页纸诊断决策树

```
TLS 失败
├─ logcat 有 "Trust anchor for certification path not found"
│   └─ CA 没进 store → Q1.6 选择逻辑 + Q3 namespace
│       ├─ App ns 里 ls 不到你的文件 → 【namespace】跑 §3.4 脚本
│       ├─ App ns 里 ls 到但 cat 报 Permission denied → 【label】§2.3
│       └─ App ns 里 ls 到、能读、仍不信任 → 查文件名 hash 是否 == subject_hash_old
├─ logcat 有 "Failed to parse certificate" / "does not contain a certificate"
│   └─ 【格式/内容】转 PEM（§3.4 step2）+ 校验 BasicConstraints CA:TRUE
├─ logcat 什么都没有（trust manager 没被调用）
│   └─ App 不走系统 store → Q7（Frida / LSPosed）
└─ alert 仍是 access_denied(49) 且以上全清
    └─ 强证据指向 App 自校验/pinning → 回逆向线（libil2cpp）
```

> 关于 **`access_denied(49)`** 这个 alert 值本身，值得提一句：证书链校验失败在 TLS 里更常见的是 `unknown_ca(48)` / `bad_certificate(42)` / `certificate_unknown(46)` / `handshake_failure(40)`；**49 更多出现在"对端拒绝"的语境**。这**不能推翻**你的实测，但它提示：**存在"不是标准 trust manager 拒绝"的可能**（例如 App 自己 catch 后主动断链，或自定义 `X509TrustManager` 包装）。→ 所以 **logcat 那条证据必须先拿到**，否则可能在错的层上打转。【推断·中，仅供交叉验证】

## 附 B：现场核验清单（照着跑，5 分钟）

```sh
# B1 格式：原厂 vs 你的
ls /apex/com.android.conscrypt/cacerts | head -3
head -c 40 /apex/com.android.conscrypt/cacerts/$(ls /apex/com.android.conscrypt/cacerts | head -1); echo
head -c 40 /apex/com.android.conscrypt/cacerts/fd8b2b01.0 | od -An -tx1 | head -2

# B2 hash 是否匹配文件名
/data/adb/ksu/bin/busybox openssl x509 -inform DER -in /apex/com.android.conscrypt/cacerts/fd8b2b01.0 -noout -subject_hash_old 2>/dev/null \
  || echo "no openssl on device; compute on PC"

# B3 是不是 CA
# (PC 上) openssl x509 -inform DER -in ca.der -noout -text | grep -A1 "Basic Constraints"
#   期望 CA:TRUE

# B4 mount 实况：自己 ns vs App ns
grep cacerts /proc/self/mountinfo
P=$(pidof com.RoamingStar.BlueArchive | awk '{print $1}'); echo "app pid=$P"
grep cacerts /proc/$P/mountinfo

# B5 App ns 里到底看得见什么
nsenter --mount=/proc/$P/ns/mnt -- /system/bin/ls -lZ /apex/com.android.conscrypt/cacerts/ | grep -E "fd8b2b01|total"
nsenter --mount=/proc/$P/ns/mnt -- /system/bin/sh -c 'head -c 40 /apex/com.android.conscrypt/cacerts/fd8b2b01.0'; echo

# B6 KSU 侧：有没有元模块 / 有没有给游戏开 umount
ls /data/adb/modules/
cat /data/adb/modules/*/module.prop 2>/dev/null | grep -E "^name|^id"

# B7 logcat
logcat -d | grep -iE "DirectoryCertificateSrc|TrustAnchor|CertPathValidator|SSLHandshake" | tail -30
```

---

## ★ 如果只能做一件事

### 唯一动作

**跑 §3.4 的脚本**（核心是这一条，其余都是配角）：

```sh
# 1) 建影子 store（原厂证书全带上 + 你的 fd8b2b01.0，PEM，root:root 644，system_file）
# 2) 挂进 zygote64（新 App 继承）+ 已跑的 App 进程
nsenter --mount=/proc/$(pidof zygote64)/ns/mnt -- /system/bin/mount --rbind /data/local/tmp/cacerts-work /apex/com.android.conscrypt/cacerts
nsenter --mount=/proc/$(pidof zygote64)/ns/mnt -- /system/bin/mount --rbind /data/local/tmp/cacerts-work /system/etc/security/cacerts
# 3) 杀干净再拉起
for p in $(pidof com.RoamingStar.BlueArchive); do kill -9 $p; done; sleep 1
monkey -p com.RoamingStar.BlueArchive -c android.intent.category.LAUNCHER 1
```

### 为什么是它（而不是换证书格式、不是装模块）

1. **它同时命中三个真因中的两个最难缠的**：`getDirectory()` 只认 APEX（所以必须往 APEX 路径上挂，而不是"往 /system 拷"）+ `/apex` private propagation（所以必须挂进 zygote ns，而不是挂自己 ns）。
2. **它不依赖任何未验证的第三方适配**：Android 17 太新，模块声明普遍写"7–16"；手写脚本没有版本假设。
3. **它 10 秒可验证、可回滚**：`umount` 或重启即恢复；不改分区、不刷机、不重签 APK。
4. **它顺手把你原来那三份错误写入的副作用清掉**（影子 store 里是干净的原厂集合 + 1 张你的 CA）。

### 预期结果（区分三种，别混）

| 观察 | 含义 | 下一步 |
|---|---|---|
| **握手成功、进游戏** | 真因 = namespace/store 选择 | 用 Q6 的模块做成开机持久化（推荐 System CA Manager） |
| **仍失败，但 logcat 出现 `Trust anchor for certification path not found`** | store 已生效但 App 用的不是这条链（可能链不全/SAN/签发者名不匹配） | 回证书链：确认 leaf 的 issuer == 我们的 CA subject；把 chain 补到 2 张 |
| **仍失败，logcat 里 trust 相关全空** | 强证据：**App 不走系统 store 校验**（自校验/pinning） | 转 Q7：先 Frida hook `X509TrustManager.checkServerTrusted` 打印调用栈（10 分钟出结论）；同时并行 §3.6 的 `libil2cpp_probe` 路线 |

### 失败后的第二个动作（明确写出，避免临场犹豫）

**拿 logcat 那一条证据 + 在 App ns 里 `ls -lZ` 的结果**，两者一起看：
- 若 `ls` 有你文件、`cat` 通、但 trust 日志为空 → **直接上 Frida**（`frida-server` 走 KSU，`Java.perform` hook `javax.net.ssl.X509TrustManager` 的 `checkServerTrusted`，打 `Thread.currentThread().getStackTrace()`）。这一步会一次性回答"到底有没有 Java 层校验、谁在调"。
- 若 `ls` 看不到文件 → 说明连 zygote 注入都被覆盖（KSU 的 App Profile `umount` / 元模块时序），**先关掉该 App 的"卸载模块/DenyList"** 再重跑脚本。

---

## 参考链接汇总（按一手/二手分组）

### 一手（AOSP / 官方文档 / 仓库原文）

| # | 内容 | 链接 | 日期 |
|---|---|---|---|
| 1 | AOSP `system/ca-certificates` 提交：`files/*.0` 是 PEM | <https://android.googlesource.com/platform/system/ca-certificates/+/c8d7f51bbb3de2c40a0d868972be008070eb25d8%5E!> | — |
| 2 | `DirectoryCertificateSource.java`（`CertificateFactory` 读证书、失败 `return null`） | <https://android.googlesource.com/platform/frameworks/base/+/d4b6c69/core/java/android/security/net/config/DirectoryCertificateSource.java> | — |
| 3 | `SystemCertificateSource.java`（`system.certs.enabled` + APEX 优先） | <https://android.googlesource.com/platform/frameworks/base/+/refs/heads/main/core/java/android/security/net/config/SystemCertificateSource.java> | — |
| 4 | 提交「Add conscrypt updatable certificates」 | <https://android.googlesource.com/platform/frameworks/base/+/8b192b19f264a8829eac2cfaf0b73f6fc188d933%5e%21> | — |
| 5 | conscrypt `TrustedCertificateStore.java`（PEM-only 读法） | <https://android.googlesource.com/platform/external/conscrypt/+/master/platform/src/main/java/org/conscrypt/TrustedCertificateStore.java> | — |
| 6 | AOSP《Conscrypt》模块文档（根证书存 APEX + 系统分区） | <https://source.android.com/docs/core/ota/modular-system/conscrypt> | 2026-10-11 |
| 7 | Android 17 行为变更（CT 默认对 targetSdk 37） | <https://developer.android.com/about/versions/17/behavior-changes-17> | 2026-10-31 |
| 8 | Android 17 功能清单 | <https://developer.android.com/about/versions/17/summary> | 2026-11-09 |
| 9 | Android 官方：`targetSdk>=24` 不信任用户 CA | <https://developer.android.com/training/articles/security-config#TrustingAddedCAs> | — |
| 10 | nccgroup `ConscryptTrustUserCerts/service.sh` | <https://raw.githubusercontent.com/nccgroup/ConscryptTrustUserCerts/master/service.sh> | — |
| 11 | `lupohan44/TrustUserCertificates`（含 `inject_into_apex()`） | <https://github.com/lupohan44/TrustUserCertificates> | 2024-01 |
| 12 | `ys1231/MoveCertificate` README / release | <https://github.com/ys1231/MoveCertificate>　<https://github.com/ys1231/MoveCertificate/releases/tag/v1.6.2> | 2026-09-02 |
| 13 | AlwaysTrustUserCerts（"mounts into zygote and application process namespaces"） | <https://magisk.dev/modules/alwaystrustusercerts/> | 2025-05-21 |
| 14 | `SekiBetu/MagiskTrustUserCerts` | <https://github.com/SekiBetu/MagiskTrustUserCerts> | 2025-06 前后 |
| 15 | `custom-certificate-authorities`（DER→PEM 转换） | <https://magisk.dev/modules/custom-certificate-authorities/> | 2026-06-15 |
| 16 | `binbard/android-system-ca-overlay`（KSU，含 A16） | <https://github.com/binbard/android-system-ca-overlay> | 2026-08-07 |
| 17 | `jjh138792/System-CA-Manager`（KSU 原生，处理 `/apex` private propagation） | <https://github.com/jjh138792/System-CA-Manager> | 2026-10-31 |
| 18 | `raise-isayan/OverrideSysPropModule`（`system.certs.enabled`） | <https://github.com/raise-isayan/OverrideSysPropModule> | 2023-09-08 |
| 19 | `takattowo/UserCABridge`（LSPosed，改框架 trust 默认） | <https://github.com/takattowo/usercabridge> | 2026-11-01 |
| 20 | KernelSU 元模块文档（"没元模块，挂载类模块不生效"） | <https://github.com/kernelsu-next/kernelsu-next/blob/aefab5770c92c0db4b49c6127227d88bd81d5327/website/docs/zh_CN/guide/metamodule.md> | 2026-11-09 |
| 21 | KernelSU issue #1354（KSU 下 HTTP Toolkit 注入的 CA 对多数 App 不可见） | <https://github.com/tiann/KernelSU/issues/1354> | 2024-02-05 |
| 22 | `pwnlogs/cert-fixer` / `hax3xploit/MagiskTrustUserCerts-Android14` | <https://github.com/pwnlogs/cert-fixer/releases>　<https://github.com/hax3xploit/MagiskTrustUserCerts-Android14> | 2026-07 / 2026-05 |
| 23 | CT 平台机制（Android 16 起才支持，log list 70 天） | <https://transparency.dev/pdfs/summit2025/android_ct.pdf> | 2025 |

### 二手（博客 / 论坛 / 经验帖）

| # | 内容 | 链接 | 日期 |
|---|---|---|---|
| a | HTTP Toolkit《Android 14 breaks system certificate installation》 | <https://httptoolkit.com/blog/android-14-breaks-system-certificate-installation/> | 2023-10 前后 |
| b | HTTP Toolkit《New ways to inject system CA certificates in Android 14》 | <https://httptoolkit.com/blog/android-14-install-system-ca-certificate/> | 2023-09-21 |
| c | NVISO Labs《Intercepting traffic on Android with Mainline and Conscrypt》（A15 上"证书全消失"→ `--rbind`） | <https://blog.nviso.eu/2025/06/05/intercepting-traffic-on-android-with-mainline-and-conscrypt/> | 2025-06-05 |
| d | velog `@nzero`（**`/apex` 是 PRIVATE propagation** 的准确解释） | <https://velog.io/@nzero/AOS-Android-14-이상-https-인증서-시스템-인증서로-설치하기> | 2024-11-06 |
| e | velog `@wyzz`（完整 chcon 命令） | <https://velog.io/@wyzz/Android-14-이상-버전에서의-인증서-세팅> | 2026-03-29 |
| f | lefo.me《android 14安装CA证书》（完整脚本含 nsenter 循环） | <http://lefo.me/2025/07/31/android-14-install-ca/> | 2025-07-31 |
| g | 52pojie《雷电Android14模拟器安装证书》 | <https://www.52pojie.cn/thread-2106728-1-1.html> | 2026-05-08 |
| h | 微信公众号《Android Conscrypt 与 TLS 证书安全》（`--bind` vs `--rbind`） | <https://mp.weixin.qq.com/s/2nVJpoczgxuPQCyKVvgONw> | 2025-11-23 |
| i | ZAP 官方博客（walk 所有 mount ns + nsenter） | <https://github.com/zaproxy/zaproxy-website/blob/b5c9e4faf029c1cd953a075bcf75d19faf6fd9a9/site/content/blog/2026-11-10-intercepting-android-traffic/index.md> | 2026-11-10 |
| j | CertBridge 文档（"开了 umount 模块，该进程 ns 里证书层也被卸掉"） | <https://eikeitsu.github.io/CertBridge/guide/hide.html> | 2026 |
| k | 语雀《系统证书安装》（Flutter 只吃 PEM） | <https://www.yuque.com/again-719bb/pfhi8f/xh5lruo7gy9apsv9> | 2026-10-24 |
| l | StackExchange《Move a user CA cert to a trusted root cert in Android 13》 | <https://security.stackexchange.com/questions/272686/move-a-user-ca-cert-to-a-trusted-root-cert-in-android-13> | 2023-10-17 |
| m | httptoolkit-server issue #114（A14 注入失败实战） | <https://github.com/httptoolkit/httptoolkit-server/issues/114> | 2024-03-30 |
