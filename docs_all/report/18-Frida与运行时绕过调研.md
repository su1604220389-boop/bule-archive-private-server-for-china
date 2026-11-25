# Frida 与运行时绕过调研（Android 17 / 腾讯 ACE / Unity il2cpp）

> 调研对象：《碧蓝档案》国服 `com.RoamingStar.BlueArchive` 3.0.2（Unity 2021.3.56f2 + il2cpp，arm64-v8a，`targetSdk=33`），设备 OPPO/一加 `PLR110`，**Android 17 / SDK 37**，**KernelSU** root（无 Magisk）。
> 现状：自建 MITM 网关，客户端 TLS 拒绝（`access_denied(49)`），客户端**不发 SNI**；`libunity.so` 有 ACE 磁盘哈希钉死（改 4 字节即 SIGBUS），`libil2cpp.so` 没有。
> 时效口径：优先 2025–2026 资料；老资料标「可能过时」。凡查不到公开来源的，明确标「未找到公开证据，以下为推断」。

---

## 0. 三条最影响决策的结论（先看这个）

| # | 结论 | 影响 |
|---|---|---|
| **0.1** | **Android 17 对 `targetSdk>=37` 的 app 强制 Certificate Transparency**：系统信任的证书如果没有 SCT，一律不认。**我们 `targetSdk=33`，暂时不受影响**，但这是一颗定时炸弹 | 若客户端某次更新到 target 37，装 CA 这条路彻底死；只能 hook |
| **0.2** | **Android 14+ 的系统 CA 是 APEX 模块，证书文件按进程单独挂载**（不是简单一个目录），所以「往目录里 cp 一个文件」在多数情况下**不够**，正确做法是把新证书**递归 remount 进所有运行中的进程** | 我们现在这套"写进 `/apex/.../cacerts`"很可能就是因此在 app 里不可见 |
| **0.3** | **Frida 最新版 17.25.2（2026-11-02）**，17.25.1 明确修了「**Android 16 上 attach Unity 游戏导致目标崩溃**」；KernelSU 有现成模块 `frida-ksu`（17.24.3，2026-11-12 更新） | 版本上可用；但 ACE 会检测，见 Q1 |

---

## 1. Q1 — Frida 在 Android 17 / SDK 37 上的可用性

### 1.1 版本与 Android 支持

| 版本 | 日期 | 与 Android 相关的关键内容 |
|---|---|---|
| 17.1.4 | 2025-06-10 | `frida-java-bridge` 升到 7.0.3，**加入 Android 16 支持**（system_server agent） |
| 17.25.1 | 2026-11-01 | **修「Android 16 上 attach Unity 游戏会让目标崩溃」**——新 mapper 把库基址取错，绑 import 到不可执行内存；改为优先取 linker 真正加载的映射。同一版还修了「mapper 映射的 agent Bionic 不认识」的问题 |
| 17.25.2 | 2026-11-02 | 修 17.25.1 在 **x86_64 Android** 上 attach 崩（`libdl.so` 基址取到高了一页） |

- 来源：[Frida 17.1.4 Released](https://github.com/frida/frida-website/blob/4e2cd7da242dc4d41e0bb8326eb8846f29f215b7/_i18n/en/_posts/2025-06-10-frida-17-1-4-released.markdown)、[Frida 17.25.1](https://frida.re/news/2026/11/01/frida-17-25-1-released/)、[Frida 17.25.2](https://frida.re/news/2026/11/02/frida-17-25-2-released/)
- **关键点**：17.25.1 修的那个 bug 恰好是「**Unity 游戏 + Android 16**」——说明 Unity + 新 Android 的 attach 是有已知坑的，而且**刚修完不久**（2026-11）。
- **Android 17 / SDK 37 的官方支持状态：未找到公开证据**。官方 release note 里目前最高只提到 Android 16。**推断**：17 与 16 的 linker/Bionic 差异不大，17.25.x 大概率能跑，但没有官方背书，需要实测。

### 1.2 KernelSU 上跑 frida-server

| 项 | 现状 |
|---|---|
| 现成模块 | **`frida-ksu`**（`ReverserID/KSU_Frida`）：把 `frida-server` 作为 root daemon 开机自启，自带 WebUI 管理 start/stop/restart/update，**安装器自动拉上游最新 release 匹配 ABI**，默认监听 `127.0.0.1:27042`。最新记录版本 17.24.3（2026-11-12） |
| 来源 | [frida-ksu 模块页](https://modules.kernelsu.org/zh-CN/modules/frida-ksu/)、[GitHub](https://github.com/ReverserID/KSU_Frida) |
| 已知坑①：**spawn 超时** | Android 15 + KernelSU 上 `device.spawn()` / `frida -U -f` 会 `Failed to spawn: unexpectedly timed out while waiting for signal`，严重时 zygote64 `SIGABRT` 导致**手机重启**。根因是 **USAP（Unspecialized App Process）**，见 [frida/frida#2516](https://github.com/frida/frida/issues/2516)。**attach 模式（`frida -U -p <pid>`）正常** |
| 已知坑②：SELinux | 该案例里 SELinux 已 Permissive 仍失败，说明**不是 SELinux 问题**；`u:r:ksu:s0` 上下文下 frida-server 一般能起 |
| 已知坑③：脚本路径 | frida-server 放 `/data/local/tmp/` 并 `chmod 755`；KernelSU 下更稳的是做成模块（`frida-ksu` 就是干这个的） |
| 来源 | [Frida spawn 小米设备 超时问题排查与解决（2026-07-29，KernelSU + Android 15）](https://bbs.kanxue.com/thread-292217.htm) |

**对本项目的直接含义**：如果要用 Frida，**优先 attach 模式**（先手动把游戏点到标题页，再 `frida -U -p <pid>`），避开 spawn 的 USAP 坑。但 attach 模式**赶不上早期 JNI 调用**（见 Q3）。

### 1.3 ACE 的检测面 与 "能过 ACE 的 Frida 加固"

**ACE（`libtprt.so` / anogs 系）的检测点**（公开资料整理）：

| 类别 | 具体项 | 来源 |
|---|---|---|
| 进程环境 | `/proc/self/maps` 扫 `frida`/`gum-js-loop`/`linjector`/`substrate` 特征；`/proc/self/status` 的 `TracerPid`；`ptrace` 自附加 | ACE 已知行为 + [tencent-ace-anogs-notes](https://github.com/shiedless/tencent-ace-anogs-notes) |
| 端口/套接字 | 默认 `27042` 监听（可改） | 同上 |
| 自保护 | **`.text` 完整性校验和**、反调试、**self-kill watchdog**（校验失败直接杀进程） | [tencent-ace-anogs-notes](https://github.com/shiedless/tencent-ace-anogs-notes) |
| 上报通道 | 自带 HTTPS / 走游戏通道上报 TDM 报告 | 同上 |
| 串与检测表 | ACE 取串走 `sub_111740(id)=off_163750[id%100]()`，unidbg 枚举出 **101 条**；检测点表；**自退点 `0x2603c`**；协议魔数 `0x87920101`；**绕 libc**（自带内联 svc） | [yh-top3](https://github.com/Machao147258-max/yh-top3)（ACE 细节最全的一篇，2026-09-25） |

**社区"过 ACE"的做法**（按可行性）：
1. **改名 + 改端口 + 去特征**：`frida-server` 重命名、改监听端口（非 27042）、剥离 `frida`/`gum` 字符串、用 `frida-gadget` 以自定义库名内置进 APK（如某项目把 gadget 改名 `libflorida.so` 注入 PvZ）。来源：[obs-G 分析（2026-09-13）](https://dc.jiellll1219.qzz.io/1w6qn/DoctorateTs_mirror/raw/commit/a9ee924dc4a7fd5c0f4d5c891a69962710193093/docs/obs-G-analysis-2026-09-13.md)
2. **gadget 内置（免 root 路线）**：apktool 拆包 → 注入 `frida-gadget` → 改包名 → 重编译签名。**但**：本项目已经实测「改 APK 的 dex 会卡启动界面」，而且 ACE 会做 `.text` 校验和，gadget 注入会改 native 加载布局 → **高风险**。
3. **ptrace/TracerPid 绕过**：patch `ptrace` 返回、伪造 `/proc/self/status`。对 ACE 效果**未验证**，且 ACE 是**内核级**（有 ioctl 通道），用户态伪造很可能被抓。

**判定**：**Frida 在这台机器上大概率被 ACE 杀掉**，而且 ACE 是"堵漏斗不堵点"的架构（`libtprt → gp*ioctl → AceManager → h.trace.qq.com`），单点伪装收益低。**结论：Frida 只适合做一次性侦察（只观测不写内存），不适合作为长期载体。**

---

## 2. Q2 — 用 Frida 绕过「系统信任库校验」的 hook 点（按可靠性排序）

### 2.1 先纠正一个前提：Android 7+ 的证书校验**不止** AndroidCAStore

`targetSdk>=24` 的 app 默认走 **`android.security.net.config.RootTrustManager`**（Network Security Config 子系统），它在 `AndroidCAStore` **之上**再做一层策略（是否信任 user CA、是否 pin、CT 策略）。所以只 hook `AndroidCAStore`/`TrustManagerFactory` 可能**不生效**，必须 hook `RootTrustManager` 或更下层。

来源：[StackOverflow 关于 RootTrustManager 的说明](https://stackoverflow.com/revisions/2178fbb9-f265-4ab0-aa5e-a553231004d8/view-source)、[Android 网络安全配置官方文档](https://developer.android.com/privacy-and-security/security-config)

### 2.2 候选 hook 点（从最可靠往下排）

| # | 层级 | Hook 目标 | 时机 | 代码片段 | 失效风险 |
|---|---|---|---|---|---|
| **H1** | Native | `SSL_CTX_set_custom_verify(ctx, mode, cb)` 里把 cb 换掉；或直接用 `SSL_CTX_set_verify(ctx, SSL_VERIFY_NONE, 0)` | 模块加载时（`Interceptor.attach(Module.findExportByName("libssl.so"/"libconscrypt_jni.so", ...))`） | `Interceptor.replace(SSL_CTX_set_custom_verify, new NativeCallback((ctx,mode,cb)=>{ return 0; }, 'int', ['pointer','int','pointer']))` | **我们的栈里没有独立 libssl**：Unity 用 libunity 内的 BoringSSL / 或 conscrypt native。若函数在 `libunity.so` 里且**未导出**，需要按偏移找（本项目符号被 strip，但 `libunity.so` **未被 strip**，可以 `Module.findExportByName` 或按符号表找） |
| **H2** | Java | `RootTrustManager.checkServerTrusted` / `NetworkSecurityTrustManager` / `TrustManagerImpl.checkTrustedRecursive` | `Java.perform` 尽早 | 见 §2.3 代码 | 需要 app 真的用这套；若走 conscrypt 的 native 路径则 hook 不到 |
| **H3** | Java | `SSLContext.init(km, tm, sr)`：把传入的 `TrustManager[]` 换成"全信任"实现 | `Java.perform` 尽早，**必须早于第一次 `SSLContext.init`** | 见 §2.3 | **时序敏感**（见 Q3） |
| **H4** | Java | `X509TrustManager.checkServerTrusted` 直接 return（对所有实现） | `Java.perform` | `Java.enumerateLoadedClasses` + `Java.use("javax.net.ssl.X509TrustManager")` 的 `$init.overload` / 或对具体实现类 hook | 只对 Java 层调用有效；Unity native 若直接走 conscrypt JNI 可能绕过 |
| **H5** | Native | BoringSSL：`X509_verify_cert` 返回 1、`X509_STORE_CTX_get_error` 返回 0、`SSL_get_verify_result` 返回 0 | 模块加载时 | `Interceptor.replace(ptr, new NativeCallback(()=>1,'int',[...]))` | 需要先定位函数（可能在 libunity 里未导出，要靠特征码/偏移） |
| **H6** | Unity 托管层 | `CertificateHandler.ValidateCertificate` 返回 true | il2cpp 层，需要 il2cpp API（本项目 `.dynsym` 被抹，`frida-il2cpp-bridge` **必定失败**，因为它也走 `getExportByName`） | 不适用 | **本项目不可用**（见 §2.4） |

### 2.3 Java 层参考代码（H3，最通用）

```javascript
Java.perform(function () {
  const X509TrustManager = Java.use("javax.net.ssl.X509TrustManager");
  const SSLContext = Java.use("javax.net.ssl.SSLContext");

  const TrustAll = Java.registerClass({
    name: "com.frida.TrustAll",
    implements: [X509TrustManager],
    methods: {
      checkClientTrusted: function () {},
      checkServerTrusted: function () {},
      getAcceptedIssuers: function () { return []; }
    }
  });

  SSLContext.init.overload(
    "[Ljavax.net.ssl.KeyManager;", "[Ljavax.net.ssl.TrustManager;", "java.security.SecureRandom"
  ).implementation = function (km, tm, sr) {
    console.log("[*] SSLContext.init intercepted");
    return this.init(km, [TrustAll.$new()], sr);
  };
});
```

- 来源（同款脚本范式）：[安卓逆向 cookbook 的 SSL Pinning 绕过节](https://overkazaf.github.io/reverse_engineering/pdf/android_reverse_engineering_cookbook.pdf)、[frida-mobile-kit 的 `bypass-trustmanager.js` / `bypass-conscrypt.js`](https://github.com/unrandoms/frida-mobile-kit)

### 2.4 ★ 关于 `frida-il2cpp-bridge`：**在本项目上直接排除**
它在内部用 `Module.getExportByName("libil2cpp.so", "il2cpp_*")` 拿 API。本项目 `.dynsym` 的 `st_name` 被清零（`.dynstr`/`.gnu.hash` 完好但符号不可按名解析），**必然抛 `Unable to find export`**。这不是 ACE 的问题，是**符号表问题**。
（旁证：本项目已实测 AzusaBA 那套 `xdl_sym` 26 个 hook 全部失效。）

### 2.5 客户端**不发 SNI** 对 hook 的影响

- 影响 `SSL_CTX_set_tlsext_servername_callback` 类 hook —— 我们**用不上这个回调**（客户端不发 SNI，回调不会被调用），所以这条路本来就没意义。
- 但**不影响** H1/H3/H4/H5：这些不依赖 SNI。
- **反过来是好事**：不发 SNI 意味着我们可以用一个「无 SNI 也返回正确证书」的 default server 兜住（本项目已用 `listen 443 ssl default_server` 实现）。

---

## 3. Q3 — Java 层 hook 能不能赶上？（时序是关键）

### 3.1 `TrustManagerFactory` 是不是每次请求都调？

**不是。** 典型实践是进程内初始化一次 `SSLContext` 并缓存（OkHttp/Unity 的 `UnityTLS` 都是启动期建一次 context）。所以 **Frida 必须在第一次 `SSLContext.init` 之前完成 hook**。

- 参考：[Script Timing（TomeSec）](https://e1mazahy.gitbook.io/tomesec/droidtomesec/android-pentesting/frida/script-timing)：`-f` spawn 模式脚本在 app 完全加载前运行；`-n`/`-p` attach 在 app 加载后才运行 → **attach 模式对初始化期调用不可靠**。

### 3.2 注入时机的下限

| 方式 | 能赶上早期 JNI 调用吗 | 说明 |
|---|---|---|
| `frida -U -p <pid>`（attach） | ❌ 大概率赶不上 | 需要先跑起来，`SSLContext` 早建好了 |
| `frida -U -f <pkg>`（spawn） | ✅ 可以（脚本在 `Application.attach` 之前） | **但本机 KernelSU + Android 15/16 有 USAP spawn 超时坑**（见 1.2），可能直接失败甚至重启 |
| `frida -f --enable-spawn-gating` + `%resume` | ✅ 最稳 | spawn gating 让进程停在最早点，脚本加载完再 `%resume` |
| gadget 内置 | ✅ | 但改 APK → ACE 风险 |

### 3.3 已知 Unity + Frida 时序问题

- Frida 17.25.1 明确修了「**Android 16 上 attach Unity 游戏导致目标崩溃**」——说明 Unity + 新 Android 的 attach 路径本身有雷，**必须先确认 17.25.2 在 Android 17 上 attach 不崩**。
- Unity 的 TLS 在 **native 线程**上通过 JNI 调 Java，因此 `Java.perform` 之外的 native hook（H1/H5）在这条路径上**更可靠**（不依赖 Java 类是否已加载）。

**结论**：如果走 Frida，**优先 native 层 hook（H1/H5）**，且用 **spawn gating**；Java 层（H3/H4）作为补充。

---

## 4. Q4 — 与「系统 CA 注入」这条路的对比

### 4.1 Android 14+ 到底读哪一份？

| 事实 | 依据 |
|---|---|
| **Android 14 起，系统 CA 移进 Conscrypt APEX 模块**，路径 `/apex/com.android.conscrypt/cacerts`，**声明为不可变**，且**证书文件按进程单独挂载** | [HTTP Toolkit: New ways to inject system CA certificates in Android 14](https://httptoolkit.com/blog/android-14-certificate-injection/)（该博主最早系统分析这事的） |
| **Conscrypt 在 Android 14+ 会先看 `/apex/com.android.conscrypt/cacerts`：存在且非空就用它，否则回落 `/system/etc/security/cacerts`** | AOSP/Dart monorepo 提交原文：「On Android 14+, Conscrypt's TrustedCertificateStore checks that `/apex/com.android.conscrypt/cacerts` both exists and is non-empty before using it, falling back to `/system/etc/security/cacerts` when … missing or empty」 |
| 因此**往 `/system/etc/security/cacerts` 写，只有在 APEX 目录为空时才生效**；正常设备上**写了没用** | 同上 |
| 二进制内容应为 **PEM 文本**（`-----BEGIN CERTIFICATE-----`），文件名 `<subject_hash_old>.0` | 本项目实测：设备上 147 个原装文件全部是 PEM 开头 |

> ⚠️ **本项目当前状态**：我们把 CA（1164 B **PEM**）写进了 `/apex/com.android.conscrypt/cacerts/fd8b2b01.0` 和 `/system/etc/security/cacerts/fd8b2b01.0`，label 改成 `u:object_r:system_security_cacerts_file:s0`，两个目录各 147 个文件。
> **但这可能仍然不够**——见下一条。

### 4.2 ★ 关键：证书是「按进程单独挂载」的

HTTP Toolkit 的原文：Android 14 把 store 移进 APEX 后是 **"stored immutably, with its certificates individually mounted directly into each process"**，所以「往目录里放文件」在**已经运行的进程**里**看不见**；解决方案是**递归地把新证书 remount 进所有运行中的进程**（这也正是 `AlwaysTrustUserCerts` / `MoveCertificate` 这类模块在做的事）。

对本项目的含义：
- **app 冷启动**（新进程）**应该**能看到我们新加的文件（因为 mount 是在进程创建时做的）；
- 但如果 mount 列表是**开机时快照**，那新文件要到**重启设备**后才可见 → 这解释了为什么"文件在、label 对、格式对，但客户端还是不认"。
- **判定实验**：`nsenter --mount=/proc/<游戏pid>/ns/mnt -- ls /apex/com.android.conscrypt/cacerts | wc -l` 看**游戏进程自己的 ns 里**是否包含我们的文件（147 还是 146）。

来源：[HTTP Toolkit: New ways to inject system CA certificates in Android 14](https://httptoolkit.com/blog/android-14-certificate-injection/)、[Android 14 blocks modification of system certificates, even as root](https://httptoolkit.com/blog/android-14-certificate-blocking/)

### 4.3 `TrustManagerFactory` / `AndroidCAStore` 有没有进程内缓存？

- **有**。Conscrypt 的 `TrustedCertificateIndex` / `TrustedCertificateStore` 是**懒加载 + 进程内缓存**（AOSP conscrypt 提交注释原文：「This is lazily initialized in the AndroidCAStore case since it forces us to bring all…」）。
- 含义：**改磁盘后不重启进程，不会生效**。必须 `force-stop` + 冷启动（本项目已做）。
- 来源：[platform/external/conscrypt 提交](https://android.googlesource.com/platform/external/conscrypt/+/04e7d1db5375010e717aa3633ce7ad547183c1c3%5E%21/)

### 4.4 现成模块横向对比

| 模块 | 支持 Android | KernelSU | 原理 | 现状（2026-11） |
|---|---|---|---|---|
| **AlwaysTrustUserCerts**（NVISOsecurity） | **7 → 16** | ✅ Magisk / KernelSU / KernelSU Next | 把用户证书**拷进系统 store**，并**自动适配** `/system/etc/security/cacerts` 与 `/apex/com.android.conscrypt/cacerts` 两种布局 | **维护中**，最新 v1.3（2025-05-21）。**首选** |
| `MoveCertificate`（ys1231） | 7 → 17（README 自称） | ✅ | 移动证书进系统 store + 处理 APEX | 待核（README 声称支持到 17） |
| `MagiskTrustUserCerts` | 老版本为主 | ⚠️ | Magisk 专用 | **可能过时** |
| `Cert-Fixer` | 中版本 | ⚠️ | 修 cert 命名/hash | 可能过时 |
| `TrustMeAlready` / `JustTrustMe` | — | — | **LSPosed Java hook** | **本项目不可用**（进程内 `XposedBridge` 是混淆替身类） |

> 注意：**AlwaysTrustUserCerts 的思路和我们手工做的一样（拷文件），它解决的是"两种布局都适配"**，但**同样不解决"按进程挂载"的问题**——它依赖的是「app 冷启动时重新 mount」。所以它和我们现在的做法等价，**不是银弹**。

### 4.5 更"官方"的注入方式

| 方式 | 可行性 | 说明 |
|---|---|---|
| KernelSU 模块（`service.d` / `post-fs-data.d`） | ✅ | 开机时把 cert 塞进 store，**保证冷启动可见**。这是把我们现在的手工操作**持久化**的正确方式 |
| `overlay.d`（KernelSU 的 overlayfs） | ✅ | 覆盖 `/system/etc/security/cacerts`，但**对 APEX 无效**（APEX 是独立挂载） |
| 直接改 APEX 镜像 | ❌ | erofs 只读 + 签名校验 |
| `nsenter` 递归 remount 进所有进程 | ✅ 但复杂 | HTTP Toolkit 用的就是这个；**改完立刻对所有运行进程生效，不用重启** |

---

## 5. Q5 — 如果 Frida 也被 ACE 杀掉，还有什么路

| # | 方案 | 原理 | 代价 / 风险 |
|---|---|---|---|
| **F1** | **从 `libil2cpp` 的 `DT_INIT` 起线程，运行时 `mprotect` + 内存补丁 `libunity`** | `libil2cpp` **没有** ACE 磁盘哈希钉死（已实测可改）；在其中注入代码、等进程起来后在内存里把 `libunity` 的证书校验函数改成 `return true`，**绕开磁盘哈希** | 风险：ACE 可能做**内存 CRC**（`libtprt` 有 `.text` 完整性校验和）。本项目已实测「`libunity` 4 字节磁盘补丁 → SIGBUS」，说明磁盘校验肯定有；内存校验**未知** |
| **F2** | **`LD_PRELOAD` / `soinfo` 注入自写 so** | 让 linker 先加载我们的库，导出一个同名符号覆盖 | KernelSU 下改 `LD_PRELOAD` 很难（zygote 环境变量受控）；ACE 会扫 maps。**低把握** |
| **F3** | **协议降级：让客户端走 `http://`** | 改网关 URL 的 scheme（或改 `ServerInfoConnectionGroupData.get_ApiUrl` 返回值），彻底不碰 TLS | 需要改客户端（il2cpp 层），但**这是最彻底的路**：一旦 scheme 是 http，证书问题整个消失。本项目已确认 metadata 里默认 ApiUrl 字面量就是 `http://test-ba.yostar.net:5210/api/state` → **消费端接受明文** |
| **F4** | **改 `res/xml` 的 networkSecurityConfig** | 加 `<certificates src="user"/>` + 显式 trust-anchor，让 app 主动信任我们的 CA | 本项目已实测 `res/*` 与 `resources.arsc` 改动**不会被 ACE 杀**（E32/E34/E42 都能启动）。**这是成本最低、风险最小的一条**，但它只解决"信任 user CA"，对**按进程挂载**问题无效 |
| **F5** | **自建 CT 日志 + 给证书塞 SCT** | 只在 `targetSdk>=37` 时才有意义 | 我们 33，暂不需要；但要记着这颗炸弹 |

---

## 6. 推荐排序（如果 CA 注入这一轮失败）

| 顺序 | 动作 | 为什么 | 预计耗时 |
|---|---|---|---|
| **1** | **先做 5 分钟判定：`nsenter` 进游戏进程的 mount ns 数一下 `/apex/.../cacerts` 有没有我们的文件** | 这一步能**直接判定**"按进程挂载"是不是我们失败的原因，比任何 hook 都便宜 | 5 min |
| **2** | 若上一步是 **146（没有我们的）** → 做 **"重启设备后再试"** 或 **`nsenter` 递归 remount** | 验证「开机快照」假设；如果是，那 CA 路就通了 | 20 min |
| **3** | 若上一步是 **147（有我们的）但仍失败** → 改走 **F4（改 `res/xml` 的 networkSecurityConfig）** | 成本最低、已证明 res 改动不触发 ACE；万一 app 内部有"只信 system"的策略，这一改能绕过 | 1–2 h |
| **4** | 若 F4 也不行 → **F3（协议降级到 http）** | 最彻底，但需要 il2cpp 层改动；本项目已有符号表恢复成果可用 | 1–2 天 |
| **5** | Frida 只做**一次性侦察**（只观测不写内存，验证 `ValidateCertificate` 是否真被调用） | ACE 会杀，不适合当载体；但作为"验证假设"的工具仍有价值 | 2–3 h |

---

## 7. 未找到公开证据 / 需要实测的点（诚实标注）

1. **Frida 17.25.x 在 Android 17 / SDK 37 上的官方支持状态**——官方 release note 最高只提 Android 16，**17 未提及**。
2. **Android 17 是否对 `targetSdk<37` 的 app 也强制 CT**——官方文档只写 `>=37`，但本机实测未验证。
3. **ACE 是否有内存 CRC（而不只是磁盘哈希）**——本项目只证明了磁盘侧（改 4 字节 SIGBUS），内存侧未知。
4. **`/apex/com.android.conscrypt/cacerts` 的 mount 列表是开机快照还是进程创建时扫描**——这条决定了"加文件后要不要重启设备"，**必须实测**。
5. **`libunity.so` 里 BoringSSL 相关符号是否导出**（`SSL_CTX_set_verify` / `X509_verify_cert`）——若导出，H1/H5 可行；若没导出，需按偏移/特征码。
