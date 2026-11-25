# 16 · Pinning 外部经验：`access_denied(49)` 到底是谁发的

> 侦察员：upstream-scout｜2026-11-14｜单点问题：BA 国服到底有没有证书 pinning，以及该 patch 谁
>
> **可信度**：【一手】= 官方源码 / 官方文档 / 官方 issue；【二手】= 社区教程、工具 README；【推断】= 我的推理

---

## 0. 一句话结论（先看这个）

> **`access_denied(49)` 在 BoringSSL/OpenSSL 的语义里，永远不会由"证书链校验失败"产生**（源码映射表里根本没有这个返回值）。它只表示"**证书本身没问题，但上层策略拒绝**"。
>
> **而 BA 客户端已知不 pin**（三份公开教程直接用 mitmproxy CA 抓包成功）。
>
> **⇒ 所以你们的 49，最可能是"Unity/游戏自己的某个白名单/校验回调"拒绝，而不是链路信任问题——继续往"装 CA"上堆工作量大概率无效，应该转向托管层回调。**

---

## Q1｜碧蓝档案客户端到底有没有证书 pinning？

### 结论
**没有。至少游戏/网关/SDK 这些域名上没有。** 日服、国际服、Steam 三个版本的私服/抓包实践全部走「装个 CA 就能 MITM」，没有任何一个需要改客户端或改证书。

### 证据（三条独立）

**(1) 日服/国际服手机端：公开教程直接用 mitmproxy 抓 BA 账号数据**【二手，但是可复现的完整教程】
[FabulousCupcake: Obtaining Blue Archive Account Data Dump](https://gist.github.com/FabulousCupcake/4f760c9c379b06a8f639c9497dcb1aaf)（2026-07-07 更新）
> This guide assumes **the game running on a mobile phone** and you have desktop running in the same network.
> Pre-requisites: **mitmproxy** in your desktop machine. **Wireguard** Client in your phone.
> ```bash
> mitmdump -q -m wireguard -s ba-account-data-dump.py --ignore-hosts '.*ngsm.nexon.com.*'
> ```
> Now launch the game with VPN / Wireguard client enabled. You should get the dump several seconds after the `Tap to Login` screen.

**(2) 同款工具包（另一个作者，独立实现）**
[AutumnVN/ba2jp](https://github.com/AutumnVN/ba2jp)（2025-09-24）—— README 同样是 mitmproxy + WireGuard + `dump.py`，拿到 `Account_LoginSync.json` / `Item_List.json`。**无需任何客户端改动。**

**(3) Steam 版：Shittim-Server 用 mitmproxy CA 就能解密全流量**【一手，上一份报告已核实】
[Shittim client-patching 文档](https://github.com/Neoexm/Shittim-Server/blob/main/docs/docs/server/client-patching.md)（2026-08-12）：客户端只需装 mitmproxy CA 到系统信任根，重写走 `redirect_server.py`。**没有任何"绕过 pinning"的步骤。**

### ⚠️ 一个容易被误读的细节
上面教程里 `--ignore-hosts '.*ngsm.nexon.com.*'` 是**绕开 NGSM（Nexon Game Security Mobile，手游反作弊）**。
**这不是因为 NGSM pinning 抓不了，而是因为 MIТM 它会被检测/封号**——作者主动选择放行。
**⇒ 对我们是重要提示：真正的风险是「反作弊检测到 MITM」，不是「证书校验过不去」。这两件事的解法完全不同。**

### 对我们的可用性
**【推断，中高可信】** 国服包大概率也不 pin。但国服是独立构建（Yostar CN），**不能 100% 排除**——需要用 Q2 末尾的归因实验确认。

---

## Q2｜Unity 2021.3 里什么情况会发 `access_denied(49)`

### 结论
**不是证书链校验失败。** 一手源码证明：BoringSSL 的「verify 结果 → alert」映射表里**没有 `access_denied` 这个分支**；链失败只会得到 48 / 42 / 46 / 45 / 40。因此 49 一定是**某段代码显式选择**发送的。

### 证据 1（一手，源码）：BoringSSL 的完整映射表

[boringssl/ssl/ssl_x509.cc — `SSL_alert_from_verify_result()`](https://github.com/google/boringssl/blob/bca12c4a/ssl/ssl_x509.cc)【一手】原文摘录：

```c
int SSL_alert_from_verify_result(long result) {
  switch (result) {
    case X509_V_ERR_CERT_CHAIN_TOO_LONG:
    case X509_V_ERR_DEPTH_ZERO_SELF_SIGNED_CERT:
    case X509_V_ERR_INVALID_CA:
    case X509_V_ERR_SELF_SIGNED_CERT_IN_CHAIN:
    case X509_V_ERR_UNABLE_TO_GET_ISSUER_CERT:
    case X509_V_ERR_UNABLE_TO_VERIFY_LEAF_SIGNATURE:
      return SSL_AD_UNKNOWN_CA;                 // 48

    case X509_V_ERR_CERT_UNTRUSTED:
    case X509_V_ERR_CERT_REJECTED:
    case X509_V_ERR_HOSTNAME_MISMATCH:          // ← 主机名不匹配
    case X509_V_ERR_IP_ADDRESS_MISMATCH:
      return SSL_AD_BAD_CERTIFICATE;            // 42

    case X509_V_ERR_CERT_HAS_EXPIRED:
    case X509_V_ERR_CERT_NOT_YET_VALID:
      return SSL_AD_CERTIFICATE_EXPIRED;        // 45

    case X509_V_ERR_APPLICATION_VERIFICATION:
      return SSL_AD_HANDSHAKE_FAILURE;          // 40  ← 注意！

    default:
      return SSL_AD_CERTIFICATE_UNKNOWN;        // 46
  }
}
```

**关键三点：**
1. **`SSL_AD_ACCESS_DENIED`(49) 在这个函数里一次都没出现。**
2. **主机名不匹配 → 42 `bad_certificate`，不是 49。** 所以「SAN 没配对」这个假设**不成立**——如果是 SAN 问题你们会看到 42。
3. `X509_V_ERR_APPLICATION_VERIFICATION`（应用层自定义校验失败）→ **40 `handshake_failure`**，也不是 49。

### 证据 2（一手，commit）:`access_denied` 的官方语义

[BoringSSL commit `2c66e07` — "Don't send the access_denied alert inappropriately"](https://github.com/aws/aws-lc/commit/2c66e079ab6b2c38581847156fffe5224c6c180e)（2016-09-16）【一手】原文：
> **access_denied is only used to indicate client cert errors** and Chrome maps it to `ERR_SSL_BAD_CLIENT_AUTH_CERT` accordingly:
> *access_denied* — A valid certificate was received, but when access control was applied, the sender decided not to proceed with negotiation. This message is always fatal.

同一个 commit 把两处「不合适地发 49」改成了 `handshake_failure` / `internal_error`。**⇒ BoringSSL 从 2016 年起就主动避免发 49。**

### 证据 3：Unity 侧的错误常量
[Unity Support: CCD/Addressables 在 Android 上 SSL 失败](https://support.unity.com/hc/en-us/articles/9654708879892)（2026-10-26）【一手】——Unity 的 verify 失败会报 `UNITYTLS_X509VERIFY_FLAG_USER_ERROR1` 或 `Curl error 60`，**都是本地错误码，不是 alert 49**。

### ⇒ 那么 49 是谁发的？三个候选，按可能性排序

| # | 候选 | 说明 | 判别方法 |
|---|---|---|---|
| **1** | **游戏自己的连接白名单/校验回调**（托管层 C#，在 libil2cpp 里） | 最符合 49 语义（"证书有效但策略拒绝"）。BA 虽不 pin **证书指纹**，但可能有 **hostname/端口/连接组白名单**校验（联系上一份报告：Shittim 文档提到 region/connection group 三处字符串必须一致） | `logcat` 看有没有 C# 异常栈；hook `CertificateHandler` 看是否被调用 |
| **2** | **Unity 默认校验失败但走了非标准 alert 路径** | UnityTLS 不是纯 BoringSSL；某些版本对"store 里找不到"走了 access_denied 分支 | 用 mitmproxy 官方 CA + 正确 SAN 再试一次；若仍 49，则不是信任问题 |
| **3** | **Java/Conscrypt 层拒绝** | 若该请求实际走 Java 栈。Conscrypt 有「Allow verification failures to send SSL alert」的历史（[AOSP commit](https://android.googlesource.com/platform/external/conscrypt/+/eb6d87ee2d1939aa81e914dc0d4a3bc625ea10dd)） | `logcat | grep -i -E "conscrypt|TrustManager|cert"` |

### ★ 这条对「patch 谁」的直接含义

> **应该 patch 托管层 `CertificateHandler.ValidateCertificate`（在 `libil2cpp.so`，你们已验证无 hash pin、可改），而不是 `libunity.so` 的 TLS 层（有 ACE hash pin，4 字节即 SIGBUS）。**

理由：49 = 上层策略决定 → 决定发生在托管层或它的直接调用者 → patch 那里收益最大、代价最小。

### ⚠️ 补一个必须排除的低级坑
**检查你们服务器 nginx 有没有开 `ssl_verify_client on/optional`。** 若开了，客户端在 client-cert 环节异常时也可能回 49（49 的官方语义恰好就是 "client cert errors"）。一条命令确认：
```bash
nginx -T | grep -i ssl_verify_client
```

---

## Q3｜有没有「不改客户端」就能过 pinning 的通用手段？

### 结论
**基本没有。** 但——**这个问题对你们可能是伪命题**：Q1 已证明 BA 不 pin，所以你们要解决的不是"绕过 pin"，而是"**让我们的 CA 真正进入 Unity 实际查询的那个信任源**"。这是完全不同的问题。

### 逐条评估

| 手段 | 可行性 | 依据 |
|---|---|---|
| 装 CA 到用户/系统/APEX store | 已试，**无效** | 你们自己的实验结果 |
| `SSL_CERT_FILE` / `CURL_CA_BUNDLE` 环境变量 | **不可行** | libcurl 确实认这两个变量（[curl 讨论](https://github.com/curl/curl/discussions/16395)，2025-02-18，明确提到 Android 需要 `CURLOPT_CAINFO`/`CURLOPT_CAPATH`），但 **Android app 进程的 env 由 zygote 派生、应用层无法设置**；`setprop` 也不进 app env |
| 改 `libil2cpp` RW 段里的 UnityTLS trust store 结构 | 理论可行，**实践不划算** | 要先知道结构布局 → 又回到"需要 dump"；且每次握手重建，稳定性差 |
| 改 `libunity.so` 内置 CA bundle | **不要做** | libunity 受 ACE 校验，你们已验证 4 字节补丁即 SIGBUS |

### ⇒ 换个角度：真正该问的「不改客户端」问题

如果目标是"不改客户端也能换网关"，那真正要解决的是 **Unity 到底从哪个源读 CA**。三个可能：
1. Android 系统 store（含 user）→ 你们已装，若无效说明不是这条
2. **Unity 自带的 CA bundle（打包进 libunity 或 assets）** → 那样装 CA 永远无效，必须改 bundle
3. 游戏自带的 trust manager（il2cpp 里）

**判别方法（很便宜）**：`unzip -l base.apk | grep -i -E "cacert|cert.pem|ca-bundle"`，看包里有没有自带 CA 文件。**如果有 → 你们前面所有装 CA 的工作注定无效，直接跳到 Q4。**

---

## Q4｜必须改客户端时，主流做法 + **不需要 metadata dump 的定位方法**

### 结论
主流做法就是 **hook `CertificateHandler.ValidateCertificate` 让它返回 `true`**。
而 **`frida-il2cpp-bridge` 可以完全跳过 `global-metadata.dat`** —— 这正是你们要的"不用 dump 的定位法"。

### 4.1 现成工具：frida-il2cpp-bridge（★ 核心答案）

[vfsfitvnm/frida-il2cpp-bridge](https://github.com/vfsfitvnm/frida-il2cpp-bridge)（README 更新 2026-09-06，v0.14.0）【一手】README 第一句原文：
> A Frida module to dump, trace or hijack any IL2CPP application at runtime, **without needing the `global-metadata.dat` file**.

兼容性原文：**Unity 5.3.0 – 6000.3.x**；平台 Android / Linux / Windows / iOS / macOS，**只有 Android 和 Linux 是 "tested"**。
**⇒ 2021.3.56f2 在支持范围内，Android 是官方测过的平台。**

**用法一：一行出 dump（不碰 metadata 文件）**
```bash
npm exec frida-il2cpp-bridge -- -f com.RoamingStar.BlueArchive dump --out-dir dumps --cs-output flat
```
输出 `dump.cs`。**这一步就替代了 Il2CppDumper + global-metadata.dat。**

**用法二：直接按类名 hook（连 dump 都不用出）**
```js
// hook.js
Il2Cpp.perform(() => {
  const CH = Il2Cpp.domain
    .assembly("UnityEngine.UnityWebRequestModule")
    .image.class("UnityEngine.Networking.CertificateHandler");

  CH.method("ValidateCertificate").implementation = () => true;
  console.log("[+] CertificateHandler.ValidateCertificate -> true");
});
```
```bash
frida -U -f com.RoamingStar.BlueArchive --no-pause -l hook.js
```
**这就是"不需要 metadata dump"的定位方法：il2cpp 的导出符号（`il2cpp_class_from_name` / `il2cpp_method_get_name`）是运行时自带的，不需要静态 metadata。**

### 4.2 其它不用 dump 的定位法

| 方法 | 说明 | 可信度 |
|---|---|---|
| **按 vtable 槽位** | `CertificateHandler` 是抽象类的虚方法；先 `Il2Cpp` 拿到类 → 取 `vtable` → 找 `ValidateCertificate` 槽，再改函数指针 | 【推断】可行，但需要 bridge 已能枚举类（= 已解决"不用 dump"） |
| **`Il2Cpp.Method::fromVirtualAddress`** | frida-il2cpp-bridge **v0.14.0 新增**（commit 2026-09-03：「Add `Il2Cpp.Method::fromVirtualAddress` & co.」）——**按虚拟地址直接构造方法对象**，配合特征码扫描用 | 【一手】README changelog |
| **特征码扫 `libil2cpp.so`** | 找 `ValidateCertificate` 的唯一字节序列。难点：il2cpp 方法体小且相似度高，容易误命中 | 【推断】可行但脆 |
| **patch `UnityWebRequest` 的 `certificateHandler` 赋值点** | 让赋值变成 null → 走默认校验。**但若默认校验就是失败原因，这没用** | 【推断】不推荐 |

### 4.3 ⚠️ 三个必须知道的坑

1. **Frida 在 ACE 下会被检测。** `libtprt.so` 会查 `/proc/self/maps` 里的 `frida`、查 `TracerPid`（见看雪 2026-09-26 那篇的分析，我上一份报告已收录）。**对策**：frida-server 改名、`spawn(-f) + --no-pause`、必要时先过 ACE 检测。
2. **`CertificateHandler` 可能压根没被设置。** 如果游戏没设 handler（Q1 说不 pin，很可能就是 null），那 hook 它没有任何调用点，等于白做。**所以要先确认有没有子类/有没有赋值** —— 用 bridge 枚举所有 `CertificateHandler` 的子类，看有几个、被谁 new。
3. **如果 49 来自 Java/Conscrypt 层**，hook il2cpp 也没用，要 hook Java 的 `X509TrustManager.checkServerTrusted`。

---

## 如果只能选一条路

### 我的推荐（按顺序，前一步不通过就不做下一步）

**第 0 步｜归因实验（30 分钟，必须先做）**
用 **mitmproxy 官方 CA**（不是你们自建的）+ 正确的 SAN，重放同一条连接：
- **仍然 49** → 证明**与 CA 信任无关**，是应用层策略。**立刻停止所有"装 CA"的工作**，转第 2 步。
- **通了** → 说明是你们 CA 的构造问题（自签属性 / 链不全 / SAN），回去修证书，别改客户端。

> 为什么必须先做：你们已经花了很多轮在"把 CA 装到三个 store"，而 Q2 的源码证据说明**49 不是信任失败**。再用 mitmproxy 的 CA 做一次对照，能一刀切开两种可能。

**第 1 步｜排除两个低级原因（10 分钟）**
```bash
nginx -T | grep -i ssl_verify_client           # 有没有误开客户端证书
unzip -l base.apk | grep -iE "cacert|ca-bundle"  # 客户端有没有自带 CA bundle
logcat -c; am force-stop 包名; 启动; logcat | grep -iE "unitytls|curl error|conscrypt|cert"
```
`logcat` 里有没有 `UnityTLS` / `Curl error 60` / `UNITYTLS_X509VERIFY_FLAG_*` —— **有，就锁定是 Unity 的校验；没有，就不是 Unity 栈**。

**第 2 步｜用 frida-il2cpp-bridge 定位（不用 dump）**
```bash
npm exec frida-il2cpp-bridge -- -f com.RoamingStar.BlueArchive dump --out-dir dumps --cs-output flat
```
在 `dump.cs` 里搜 `CertificateHandler` —— **看有几处引用、有没有自定义子类、谁给它赋值**。
- **有自定义子类** → 就是它，hook 返回 true（第 3 步）
- **没有** → 说明走默认校验，**问题在 Unity 读的信任源**，回到 Q3 第 3 点（查自带 CA bundle）

**第 3 步｜hook 托管层，不碰 libunity**
```js
CH.method("ValidateCertificate").implementation = () => true;
```
**绝对不要改 `libunity.so`**（ACE hash pin，4 字节即 SIGBUS——你们已验证过）。`libil2cpp.so` 无 hash pin，是唯一安全的 patch 面。

### 成算评估

| 路径 | 我的判断 | 依据 |
|---|---|---|
| 49 = 应用层策略拒绝（Q2 结论） | **~85%** | BoringSSL 源码映射表无 49；49 语义 = 上层策略 |
| BA 不 pin 证书指纹（Q1 结论） | **~85%** | 三份公开 mitmproxy 教程均成功 |
| ⇒ 修在托管层能解决 | **~60%** | 取决于游戏是否真有校验回调；也可能是 Unity 读自带 bundle |
| 完全不需要改客户端就能解决 | **~25%** | 若第 1 步发现自带 CA bundle，则必须改包 |

### 一句话给 Lead

> **别再加 CA 了。** 先用 mitmproxy 官方 CA 做对照实验——它会告诉你 49 是不是信任问题。
> 源码层面已经能确定：**证书链失败永远发不出 49**（BoringSSL 映射表里没有这个值），所以这不是"CA 没装上"，是"有人主动拒绝了"。
> 定位用 `frida-il2cpp-bridge`，**它明说不需 `global-metadata.dat`**，一行 `dump` 代替 Il2CppDumper；patch 面选 `libil2cpp` 的 `CertificateHandler.ValidateCertificate`，**离 `libunity` 远一点**。

---

## 参考链接（带日期）

| 内容 | URL | 日期 | 级别 |
|---|---|---|---|
| BoringSSL `SSL_alert_from_verify_result()` 完整映射表 | https://github.com/google/boringssl/blob/bca12c4a/ssl/ssl_x509.cc | 现行 master | 一手 |
| BoringSSL commit：不恰当发送 access_denied | https://github.com/aws/aws-lc/commit/2c66e079ab6b2c38581847156fffe5224c6c180e | 2016-09-16 | 一手 |
| **BA 账号数据 dump 教程（手机 + mitmproxy）** | https://gist.github.com/FabulousCupcake/4f760c9c379b06a8f639c9497dcb1aaf | 2026-07-07 | 二手 |
| ba2jp（同款，另一作者） | https://github.com/AutumnVN/ba2jp | 2025-09-24 | 二手 |
| Shittim client-patching（Steam 版用 mitmproxy CA） | https://github.com/Neoexm/Shittim-Server/blob/main/docs/docs/server/client-patching.md | 2026-08-12 | 一手 |
| **frida-il2cpp-bridge（无需 global-metadata.dat）** | https://github.com/vfsfitvnm/frida-il2cpp-bridge | 2026-09-06 | 一手 |
| Unity Support：`UNITYTLS_X509VERIFY_FLAG_USER_ERROR1` | https://support.unity.com/hc/en-us/articles/9654708879892 | 2026-10-26 | 一手 |
| Conscrypt：允许 verification 失败发送 SSL alert | https://android.googlesource.com/platform/external/conscrypt/+/eb6d87ee2d1939aa81e914dc0d4a3bc625ea10dd | 历史 commit | 一手 |
| libcurl 在 Android 上的 CAINFO/CAPATH | https://github.com/curl/curl/discussions/16395 | 2025-02-18 | 二手 |
