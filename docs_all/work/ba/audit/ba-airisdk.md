# Blue Archive 国服 · AiriSDK（爱瑞发行 SDK）机制全解

> 取证基础：APK 3.0.2（versionCode 73）、`classes.dex` / `classes2.dex` baksmali 反汇编、
> `lib/arm64-v8a/` 全部 28 个 so 的 readelf 分析、设备实测日志（logcat + `dumpsys activity exit-info`）。
> 本文所有结论都有文件/行号/日志支撑，未标注者视为推断。

---

## 一、结论速览

AiriSDK 不是一个 SDK，而是**两个互相独立的组件**：

| 组件 | 形态 | 位置 | 职责 |
|---|---|---|---|
| **签名核心** | native so | `lib/arm64-v8a/libairisgcore.so`（2.66 MB） | 只提供 3 个方法：通信 AES 的 key/iv + 请求签名 |
| **渠道插件宿主** | Kotlin 类 | `com.airi.core.AiriSdkManager`（`classes.dex`） | 动态加载渠道插件（`official` / 各应用商店），承载登录/支付/实名/推送/统计 |

**关键结论：签名核心可以完全替换，签名从此可控。** 这是自建服务端能跑起来的前提之一。

---

## 二、native 签名核心 `libairisgcore.so`

### 2.1 二进制事实

```
大小        2,658,312 B
导出符号    JNI_OnLoad（唯一，@0xf0050）
NEEDED      libandroid.so / liblog.so / libm.so / libdl.so / libc.so
被依赖      无（没有任何其他 so 的 NEEDED 指向它）
```

> `NEEDED` 干净、无人依赖 → **可以整体替换，不会引发链接错误**（与 `libtprt.so` 的处理方式相同）。

### 2.2 Java 侧接口（全部 native 方法仅 3 个）

`com/airi/core/sign/AiriSgClient.java`：

```java
public class AiriSgClient {
    public static native String getAAesIv();
    public static native String getAAesKey();
    public static native String sign(byte[] bArr, int i);
}
```

- `getAAesKey()` / `getAAesIv()` → 返回**网络通信用的 AES 密钥与 IV**（字符串形式）。
- `sign(byte[] data, int len)` → 返回**请求签名串**。

**这三个方法是全游戏网络层加密/签名的源头。** 之前从 `Metadata` 里看到的
`MX-Core-Crypto-HybridCryptor`（`GenerateKeyAndIV` / `LoadPublicKeyFromPem` /
`VerifySignatureKeyAndIVWithRSA` / `DecryptTextAES`）是 C# 层的封装，其底层 key 材料就来自这里。

### 2.3 替换方案（已验证可编译、可加载）

用 8 KB 的假 so 覆盖，`JNI_OnLoad` 里 `RegisterNatives` 注册三个方法：

```c
#define MY_AES_KEY "BAPrivateSrvKey1"   // 16B → AES-128
#define MY_AES_IV  "BAPrivateSrvIV12"

static jstring n_get_key(JNIEnv *e, jclass c) { return (*e)->NewStringUTF(e, MY_AES_KEY); }
static jstring n_get_iv (JNIEnv *e, jclass c) { return (*e)->NewStringUTF(e, MY_AES_IV);  }
static jstring n_sign   (JNIEnv *e, jclass c, jbyteArray d, jint n) {
    return (*e)->NewStringUTF(e, "00000000000000000000000000000000");
}

JNIEXPORT jint JNI_OnLoad(JavaVM *vm, void *r) {
    JNIEnv *env; (*vm)->GetEnv(vm, (void**)&env, JNI_VERSION_1_6);
    jclass cls = (*env)->FindClass(env, "com/airi/core/sign/AiriSgClient");
    static const JNINativeMethod m[] = {
        {"getAAesKey", "()Ljava/lang/String;",    (void*)n_get_key},
        {"getAAesIv",  "()Ljava/lang/String;",    (void*)n_get_iv},
        {"sign",       "([BI)Ljava/lang/String;", (void*)n_sign},
    };
    (*env)->RegisterNatives(env, cls, m, 3);
    return JNI_VERSION_1_6;
}
```

编译（PRoot / 系统 clang + NDK sysroot）：

```bash
clang --target=aarch64-linux-android26 \
  --sysroot=$NDK/toolchains/llvm/prebuilt/linux-x86_64/sysroot \
  -O2 -fPIC -shared -fvisibility=hidden \
  -I$SYSROOT/usr/include \
  -L/usr/lib/gcc/aarch64-linux-gnu/13 \
  -o libairisgcore.so gm_fake_airisg.c
```

集成方式：`zip -u base.apk lib/arm64-v8a/libairisgcore.so` → `zipalign -f 4` → `apksigner sign`。

> **注意**：本机实测中，进程在走到 `AiriSgClient` 之前就被 `OfficialPluginImpl` 的初始化退出，
> 因此这三个方法尚未在真机跑通（详见第五节）。替换方案本身已编译通过、符号正确。

---

## 三、Java 渠道插件宿主 `AiriSdkManager`

### 3.1 类结构（baksmali：`smali1/com/airi/core/AiriSdkManager.smali`，96 KB）

```java
public final class AiriSdkManager {
    public static final Companion Companion;
    public static final AiriSdkManager instance;
    private volatile AbstractPlugin realPlugin;

    public final void onAppAttachBaseContext(Application app);  // :1440
    public final void onAppCreate(Application app);
    public final void onResume(...);
    public final void onStop(...);
    public final void onDestroy(...);
    private final AbstractPlugin loadPlugin(Application app);   // :317 (日志行号)
}
```

### 3.2 启动链（实测日志逐行对应）

```
libtprt.so 的 JNI_OnLoad           ← ACE（已用假 so 替换）
  ↓
AceApplication.attachBaseContext
  → AceApplication.attachBaseContextShell()
      → initialize(pkg, filesDir, nativeLibDir, sourceDir, splitDirs)   ← native，返回 0 表示成功
  ↓
TechApplication.attachBaseContext      （com.tech.core，classes2.dex）
  → super.attachBaseContext()          ← 即 AceApplication 的
  → if (!isMainProcess) return         ← 子进程直接返回
  → MyLog.w("lifecycle_app_attachBaseContext")
  → AiriSdkManager.instance.onAppAttachBaseContext(this)
  ↓
AiriSdkManager.onAppAttachBaseContext   （smali :1440）
  → plugin = loadPlugin(app)             // 日志：AiriSdkManager.kt:317 loadPlugin channelName=official
  → if (plugin == null) plugin = new AbstractPluginAdapter()   // 容错：空插件
  → realPlugin = plugin
  → realPlugin.createUDataOaidFactory()  // 日志：OfficialPluginImpl.java:213
  → UDataOaidFactoryHelper.setUDataOaidProviderFactory(...)
  ↓
TechApplication.onCreate
  → AiriSdkManager.onAppCreate(app)      // 日志：lifecycle_app_onCreate
  ↓
OfficialPluginImpl 初始化
  → EnvUtils.init()                      // 日志：EnvUtils.kt:13 ENV_isGray = false
  ↓
★ 此处 exit(25)（实测：reason=1 EXIT_SELF, status=25）
```

### 3.3 插件容错（重要）

```java
// AiriSdkManager.smali :1449-1466
invoke-direct {p0, p1}, Lcom/airi/core/AiriSdkManager;->loadPlugin(Landroid/app/Application;)Lcom/airi/core/plugin/AbstractPlugin;
move-result-object p1
if-nez p1, :cond_18
    new-instance v0, Lcom/airi/core/plugin/AbstractPluginAdapter;
    const-string v1, "plugin_load_failed, use default empty plugin"
    invoke-static {v1}, Lcom/airi/common/log/MyLog;->w(Ljava/lang/String;)V
```

**插件加载失败不会崩**，会退化为 `AbstractPluginAdapter`（空实现）。
→ 这意味着「把插件干掉」在架构上是允许的，前提是后续调用链能容忍空实现。

### 3.4 与 `TechApplication` 的绑定

```smali
# TechApplication.smali :18-46
.method public attachBaseContext(Landroid/content/Context;)V
    invoke-super {p0, p1}, Lcom/ace/gshell/AceApplication;->attachBaseContext(Landroid/content/Context;)V
    invoke-static {p0}, Lcom/airi/common/utils/CommonUtil;->isMainProcess(Landroid/content/Context;)Z
    ...
    sget-object p1, Lcom/airi/core/AiriSdkManager;->instance:Lcom/airi/core/AiriSdkManager;
    invoke-virtual {p1, p0}, Lcom/airi/core/AiriSdkManager;->onAppAttachBaseContext(Landroid/app/Application;)V
```

`TechApplication` 继承 `AceApplication`（`com.ace.gshell`），这就是为什么 **ACE 与 AiriSDK 是同一条启动链上的父子关系**。

---

## 四、整套保护层清单（本机实测结论）

| 层 | 载体 | 机制 | 实测结果 |
|---|---|---|---|
| ① 文件完整性 | `assets/__tpinfo.tsc`（485 KB，≈7500 个 SHA-256）<br>`assets/__tpinfo.tsd`（1.6 KB，≈25 个 SHA-256）<br>`assets/__tpinfo.*.sig`（RSA-2048） | 验签清单 + 逐文件哈希比对 | **删除 5 个 `__tpinfo.*` 文件后校验直接跳过** ✅ |
| ② ACE 自检 | `libtprt.so`（1.69 MB） | 改任意字节 → `kill(SIGBUS)` | **整体替换为假 so 成功**（导出 `JNI_OnLoad` + `g_tprt_pfn_array` + `g_tprt_ori_array`，注册 7 个 native 方法）✅ |
| ③ 签名核心 | `libairisgcore.so` | 提供 AES key/iv + sign | 假 so 已就绪，**尚未走到** 🟡 |
| ④ 渠道插件 | `OfficialPluginImpl` | 初始化后 `exit(25)` | **当前卡点** ❌ |
| — | `libmsaoaidsec.so`（数美） | 设备指纹/风控 | 未单独验证 |
| — | `libsigner.so` | Adjust 广告归因 | 与本流程无关 |

### 4.1 关于 ②「假 ACE」的技术细节

```
原 libtprt.so 导出：JNI_OnLoad / g_tprt_pfn_array / g_tprt_ori_array
libunity.so、libil2cpp.so 通过 R_AARCH64_GLOB_DAT 引用后两个数组
com.ace.gshell.AceApplication 的 7 个 native 方法：
    gp6ioctl(String) / gp7ioctl(String)
    handleLoad(Object,int) → Object / handleLoad(byte[],int,int) → Object
    handleLoadV22(byte[],int,int) → long
    ioctl(int,String) → int
    initialize(String,String,String,String,String[]) → int     // 返回 0 = 成功（源码确认）
```

要点：
- 两个数组必须**导出**（`GLOB_DAT` 只需要地址，不需要大小），否则 `dlopen libunity.so` 失败 → `JNI FatalError` → abort。
- 数组内容用「忽略参数、`mov x0,#0; ret`」的通用 stub 填满（ACE 这些函数都是检测类，返回 0 = 未发现威胁）。
- `initialize` 返回 **0 表示成功**（`if (initialize(...) != 0) throw new Exception("initialize failed.")`，且该异常被 catch 吞掉）。

### 4.2 实测日志（假 ACE 生效的证据）

```
FAKE-ACE-ctor
FAKE-ACE-JNI_OnLoad
ACE-register-ok          ← 7 个 native 方法注册成功
ACE-initialize           ← initialize 被调用，返回 0
```

---

## 五、当前唯一未解决点

```
OfficialPluginImpl 初始化 → EnvUtils.init() → exit(25)
```

- 位置：`classes.dex` 的 `com/airi/core/plugin/impl/OfficialPluginImpl`（尚未逐行定位）
- 特征：`reason=1 (EXIT_SELF)`、`status=25`、无 tombstone、无 `Fatal signal`
- 已知**不是** ACE 的问题（假 ACE 已通过）、**不是** 签名核心的问题（还没走到）

下一步：直接对 `OfficialPluginImpl` 的初始化做 smali 级 patch（把 `exit` 调用替换为 `return-void`）。

---

## 六、对「一键起号 / 私服客户端」的意义

1. **签名可控**：`getAAesKey/getAAesIv/sign` 三个方法被我们接管后，客户端发出去的每个请求
   其加密与签名规则完全由我们决定，服务端按同一份规则处理即可，**不需要逆向官方私钥**。
2. **协议层已摸清**（前序文档 `api-probe.md` / `routes_found.txt`）：
   - 53 条真实业务路由（含 `raid/sweep`、`mission/reward`、`craft/reward`、`attendance/reward`、`minigame/result` 等）
   - 加密模型：`HybridCryptor`（AES 由客户端生成 + RSA 包裹 key + RSA 签名）
   - 登录链：`MX-SDK-SDKBase.Login` → `LoginToServer`
3. **可以做的形态**：
   - 一键起号：走「本地随机数据 + 服务端放行」路径，卡点在腾讯验证码（前序结论）
   - 私服客户端：改包名 → ❌（包名被校验，实测 SIGBUS）；**原包名 + 删 tpinfo + 假 ACE/SG** → ✅ 方向

---

## 七、未验证 / 风险项

| 项 | 说明 |
|---|---|
| `OfficialPluginImpl` 退出条件 | **未定位**，下一步 smali patch |
| `libmsaoaidsec.so`（数美） | 未单独验证是否有独立校验 |
| 假 SG 的真机执行 | 未跑到（被 ④ 挡住） |
| `sign()` 的真实算法 | 未知（原 so 里实现），目前用固定值替代 |
| `getAAesKey` 的编码 | 推断为 16 字节字符串，**未验证**是否 UTF-8 / Base64 / hex |
| 官方更新 | 每版本需重新核对 28 个 so 的导出符号与 `AceApplication` native 方法表 |
