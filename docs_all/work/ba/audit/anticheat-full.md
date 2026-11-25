# 全量反作弊检测点验证（10 类）

> 出具：`anticheat-verify`（本回合用 jadx 全量 grep + ELF 导入表补证；lead 初版框架保留，**修正 3 处断言**，见 §0）
> 扫描对象：`audit/ba-apk/jadx/sources`（3,255 个 .java，`.dex` 全解）、`audit/ba-apk/lib/arm64-v8a/*.so`（ELF .dynsym + 明文串）
> 已确认前提（不重复验证）：反作弊 = **ACE（libtprt + gp6/gp7 三服务）+ 数美 + Turing + Themis**，**不是 XIGNCODE3**；libil2cpp 无 hash pin（`ace-ipc.md`）；libtprt 明文串 0 命中（rodata 加密）。

## §0 本轮修正（3 条，务必以此为准）

1. **`magisk` 在 dex 里是 0 命中**（初版写"1 处模糊匹配"）。`/data/adb`、`ksu`、`busybox`、`which su`、`zygisk` 亦均为 0。
2. **`frida` / `27042` / `ptrace` 在 dex 里真命中 = 0**（`frida` 唯一命中是 `androidx/core/util/PatternsCompat.java:16` 的 TLD 列表，假阳性；`gum` 的 219 个文件全是 `argument` 子串假阳性）。
3. **"客户端侧无改包检测"要打折**：`GET_SIGNATURES` 常量确实 0 命中，但**数美与 nirvana 都用 `getPackageInfo(pkg, 64).signatures` 现算 SHA1**（64 == GET_SIGNATURES），见 §7。

## 总表（10 类 × 有没有 / 我们会不会中 / 置信度）

| # | 类别 | 有没有 | 实现位置（本轮证据） | 我们会不会中 | 置信度 |
|---|---|---|---|---|---|
| 1 | Xposed/LSPosed 检测 | **有** | 数美 `com.ishumei.smantifraud.l111l11111I1l.l1111l111111Il`：`XposedBridge.jar` 文件探测 + `de.robv...XposedHelpers` 的 `fieldCache/methodCache/constructorCache` 反射枚举 + **Riru/EdXposed `EdXpConfigGlobal` 逐 ClassLoader 枚举** + `/proc/self/maps` 扫 `/data/app/` | 已把 `findAndHookMethod` 换成 `getDeclaredMethod+hookMethod` → 缓存零痕迹；**但 maps 扫描与 riru 枚举未针对处理** | 高 |
| 2 | Root 检测 | **Java 层有（2 处）；ACE 层未知** | 阿里云 SLS `RootUtil.java:31/35/44`（test-keys + 10 条 su 路径 + `which su`）；中国移动 `CheckRoot.java:16-18`（**native**：`checkRootPathSU/checkSuperuserApk/isDeviceRooted`）；libtprt 明文 `magisk`/`/data/adb` **0 命中** | 我们不解 root、不清 /data/adb → **若 ACE 内部查 su 路径仍会中**（我们改的是类路径，不是 root 环境） | Java 层=高 / ACE 层=低（静态不可证） |
| 3 | 模拟器/多开 | **有（模拟器）；多开=0 命中** | 支付宝 `com/alipay/sdk/m/a0/d.java:32,151`（`goldfish`、`ro.kernel.qemu`）；`.../a0/b.java:714,717,720`（`ro.hardware=goldfish` / `ro.product.model=sdk` / `ro.build.fingerprint=test-keys`）；中国移动 `EmulatorDetector.java`；数美采集 `ro.boot.hardware` | 真机（骁龙 8 Elite）**不会** | 高 |
| 4 | 调试检测 | **有（3 家）** | Turing `Virgo.java:57`（读 `/proc/self/status`，另有 `/proc/%d/status`，解析 `PPid` 等键）；中国移动 `gatewayauth/utils/a.java:19`（`line.startsWith("TracerPid")`）；阿里云 `AppUtils.java:127 debuggable()` | release 签名、未挂 ptrace/gdb → **不会**；一旦用 frida/gdb attach → **必中** | 高 |
| 5 | Frida/注入检测 | **明文 0，能力齐备** | dex：`frida`/`27042`/`gum`/`ptrace` 全 0（见 §0）；**数美 `l1111l111111Il.java:528` `new FileReader("/proc/self/maps")` 并只保留含 `/data/app/` 的行**（= 找注入 dex / 双开路径）；libtprt 导入 `dlopen/dlclose/dlsym/dladdr`（无明文 frida） | 注入痕迹（LSPosed 模块本体在 `/data/app/...`）**可能被 maps 扫描看到**；是否上报未证 | 中（能力高，调用未证） |
| 6 | 多开/双开检测 | **未发现** | `lbe.parallel` / `VirtualApp` / `io.va.exposed` / `com.qihoo.magic` / `dualapp` 全 0；但数美的 `/data/app/` maps 过滤可顺带暴露非本源路径 | 我们单开 → **不会** | 低（无证据） |
| 7 | 代理/改包检测 | **无显式 VPN/代理判定；签名素材有** | `CertificatePins` = 0；`java.net.Proxy` 仅 `com/criware/filesystem/CriFsWebInstaller.java:16`（下载用）；`ProxySelector` 仅 `taptap .../NullProxySelector`（空实现）；`TRANSPORT_VPN` 常量 0；**但** 数美 `l111l1111lIl.java:38-46` 对任意包算 `signatures[0]` 的 SHA1 hex，nirvana `AppUtils.java:73` 取本包签名 hexdigest；Turing `Sagittarius.java:85-95` 反射 `mTransportTypes` + `hasTransport(0..63)` 组位图上报（服务端可判 VPN=bit4）；manifest `networkSecurityConfig=@xml/http`（`ba-java.md:169`，白名单未解出） | 我们的 dex 重打包会改签名 → 若签名被上报/比对即中；挂代理若走 443 且无证书固定 → 未必拦 | 中高（改包）/ 中（代理） |
| 8 | 内存/代码段校验 | **无 libil2cpp 校验** | `ace-ipc.md`：libtprt 内 5 个 32-hex 常量 ≠ 本包 26 个 so/dex 的 md5；libtprt 明文 `magisk/frida/...` 全 0、可打印率 **0.286**（本轮实测，初版 0.31 以此为准） | 改 native 安全 | 高 |
| 9 | 进程/模块扫描 | **推断会（中高）** | libtprt `.dynsym` 146 个 UND 导入含 `dladdr`(按地址反查模块)、`opendir/readdir/readlink/access/stat/fstatat/symlink/unlink/rename`、`socket/bind/listen/accept/connect`；无 `/proc/self/maps` 明文；libmsaoaidsec.so 明文 `/proc/self/maps`=1 | `libNeko.so` 在 maps 明文可见 → **可能中**（唯一确定未解决的暴露面） | 中高（推断） |
| 10 | 输入/行为检测 | **有（纯本地）** | `ExcessiveTouchCheck`（MonoBehaviour）：`StartCheck/StopCheck/CoCheck` + `checkExpireDuration/checkTouchCount` + `inputTimeList/inputFrameList` + `ExcessiveTouch(bool)` | 已 hook `StartCheck` → **不会** | 高 |

## 逐类证据（文件 + 行号 + 命中原文）

### 1) Xposed / LSPosed（数美，唯一一处真检测）

`com/ishumei/smantifraud/l111l11111I1l/l1111l111111Il.java`

```java
:307   return l1111l111111Il("XposedBridge.jar");                     // 文件级探测
:316   Class<?> c = ClassLoader.getSystemClassLoader()
                 .loadClass("de.robv.android.xposed.XposedHelpers");
       // 逐个读 fieldCache / methodCache / constructorCache 三个静态 Map
:500   Class.forName("com.elderdrivers.riru.edxp.config.EdXpConfigGlobal", false,
                     (ClassLoader) entry.getValue());               // 遍历 mLoaders，命中即取包名
:528   BufferedReader(new FileReader("/proc/self/maps"))             // 只保留 indexOf("/data/app/") 行
```

→ 这是**四个维度**的注入检测（文件 / 类 / 缓存内容 / 已加载模块），比初版记的"4 个枚举方法"更完整。

### 2) Root

| 文件:行 | 命中原文 | 归属 |
|---|---|---|
| `com/aliyun/sls/android/core/utils/RootUtil.java:31` | `return str != null && str.contains("test-keys");` | 阿里云 SLS 日志 SDK |
| 同上 `:35` | `{"/system/app/Superuser.apk","/sbin/su","/system/bin/su","/system/xbin/su","/data/local/xbin/su","/data/local/bin/su","/system/sd/xbin/su","/system/bin/failsafe/su","/data/local/su","/su/bin/su"}` | 同上（10 条路径 `File.exists`） |
| 同上 `:44` | `Runtime.getRuntime().exec(new String[]{"/system/xbin/which","su"})` | 同上（子进程探测） |
| `com/mobile/auth/gatewayauth/utils/security/CheckRoot.java:16-18` | `native boolean checkDeviceDebuggable();` `native boolean checkRootPathSU();` `native boolean checkSuperuserApk();` `native String isDeviceRooted();` | 中国移动一键登录（实现在 `libpns-2.14.23-...so`） |

**ACE 侧**：`libtprt.so`（1,692,296 B）明文 `magisk` / `/data/adb` / `ksu` / `test-keys` / `/system/bin/su` **全部 0 命中**；但 `.dynsym` 具备 `access / stat / fstatat / readlink / opendir / readdir / getuid` —— **有能力查，查什么静态看不到**。

### 3) 模拟器 / 多开

| 文件:行 | 命中原文 |
|---|---|
| `com/alipay/sdk/m/a0/d.java:32` | `java.lang.String r2 = "goldfish"` |
| 同上 `:151` | `return a("ro.kernel.qemu", "0");` |
| `com/alipay/sdk/m/a0/b.java:714/717/720` | `linkedHashMap.put("ro.hardware","goldfish")` / `("ro.product.model","sdk")` / `("ro.build.fingerprint","test-keys")`（属性取不到时的缺省填充，等于把设备当模拟器兜底） |
| `com/mobile/auth/gatewayauth/utils/security/EmulatorDetector.java` | 类存在（方法体本轮未展开，置信度中） |
| 数美 `l111l11111I1l/l11l1111Il.java:26-30` | `ro.boot.hardware` 等 5 个属性（见"新增发现"） |

多开：`lbe.parallel`/`VirtualApp`/`io.va.exposed`/`com.qihoo.magic`/`LBE`/`dualapp` **0 命中**；`ranchu`/`generic_x86` 亦 0。

### 4) 调试 / 反调试

| 文件:行 | 命中原文 |
|---|---|
| `com/tencent/turingfd/sdk/ams/ad/Virgo.java:57` | `java.lang.String r7 = "/proc/self/status"`（另 `:48` `/proc/%d/status`）；逐行 `split(":")` 塞 HashMap，取 `PPid`（:65）→ 父进程/调试器判定 |
| `com/mobile/auth/gatewayauth/utils/a.java:19` | `if (line.startsWith("TracerPid"))` |
| `com/aliyun/sls/android/core/utils/AppUtils.java:127` | `public static boolean debuggable(Context context)` |

**libtprt 反调试能力（本轮新增硬证据）**：`.dynsym` 152 项 / 146 UND，含 **`ptrace`（符号 #132，`ptrace@LIBC`）、`fork`、`execv`、`waitpid`、`kill`、`sigaction`、`prctl`、`syscall`、`mprotect`** → 反调试/自校验的完整工具箱（导入 ≠ 调用，但能力确凿）。

### 5) Frida / 注入

- dex 明文：`frida` 0（真）、`27042` 0、`gum` 0（真）、`libfrida` 0、`/proc/self/maps` **1 处**（数美 `:528`）、`/proc/self/status` 1 处（Turing `:57`）。
- 数美 `:528` 的过滤逻辑值得注意：**只保留含 `/data/app/` 的行** —— 典型的"找出被注入/非系统路径加载的模块"手法（LSPosed 模块本体与其 base.apk 就在 `/data/app/`）。
- libtprt：明文 0，但导入 `dlopen/dlclose/dlsym/dladdr`（可枚举/反查模块）。

### 6) 多开

无 Java 侧证据（见总表）。唯一相关：数美 maps 过滤 `/data/app/` 时，双开环境（`/data/user/<多用户 id>/...`）与正常路径不同，**服务端拿到 maps 片段即可反推**。

### 7) 代理 / 改包

- **签名读取（真存在）**：
  - 数美 `com/ishumei/smantifraud/l111l11111I1l/l1111l111111Il/l111l1111lIl.java:38-46`：`getPackageInfo(str, 64).signatures` → `MessageDigest("SHA1")` → hex 串（**入参是包名**，逐包计算，可作已安装应用指纹/改包素材）。
  - `com/nirvana/tools/core/AppUtils.java:73`：`APP_SIGNATURE = hexdigest(pm.getPackageInfo(getPackageName(), 64).signatures[0].toByteArray())`。
- **VPN/代理**：`TRANSPORT_VPN` 0；`NetworkCapabilities` 4 个文件里，`cn/shuzilm/core/u.java:50` 是 `hasTransport(1)` = **WIFI 判定（不是 VPN，勿误读）**；Turing `Sagittarius.java:85-95` 是 `mTransportTypes` 位图上报（bit4 才代表 VPN，**由服务端判**）。
- **传输安全**：manifest `android:networkSecurityConfig="@xml/http"`（`ba-java.md:169`）；`res/xml` jadx 未导出，**证书固定细节未验证**。

### 8/9/10) 代码段校验 / 模块扫描 / 行为

沿用既有结论 + 本轮补充：`libthemis.so`(849,496 B) / `libsigner.so` / `libjutils.so` / `libdu.so` / `libairisgcore.so` 明文 `root/magisk/emulator/frida/xposed/debug/proxy` **全 0**；`libmsaoaidsec.so`（OAID）明文 `/proc/self/maps` **1 处**（自校验/注入检测）。

## 新增发现（10 类以外）

**① 数美采集 5 个系统属性（环境指纹，非"检测即杀"）**

`com/ishumei/smantifraud/l111l11111I1l/l11l1111Il.java:26-30`：`ro.debuggable` / `ro.boot.hardware` / `gsm.sim.state` / `gsm.operator.alpha` / `sys.usb.state`。
风险：测试机未插 SIM 时 `gsm.sim.state`、`gsm.operator.alpha` 为空 → 数美模型里是"模拟器/群控/农场号"特征，**拉高账号风险分**。

**② ACE 的 Java 层只做一件事：把包路径交给 native（改包校验面）**

`com/ace/gshell/AceApplication.java`（整包仅 4 个 java 文件）：
`:31 System.loadLibrary("tprt")`；`:16/:18 native gp6ioctl(String)/gp7ioctl(String)`；`:26 native int ioctl(int,String)`；`:28 initialize(String,String,String,String,String[])`；`:50-58` 传入 `packageName / nativeLibraryDir / sourceDir / filesDir`，并**反射取 `ApplicationInfo` 的数组字段（splitSourceDirs）**。
→ **全部 Root/调试/模拟器判定都不在 dex**；ACE 拿 `sourceDir + splitSourceDirs` 在 native 做 APK 完整性/路径校验。我们**重打包 dex 这条路，签名与 APK 路径必然与原包不同**，这是最现实的风险点。

**③ libtprt 是"能反调试、能扫描、能 IPC"的全能体**：`ptrace/fork/waitpid/execv` + `access/stat/readlink/opendir` + `socket/bind/listen/accept`（配合 gp6/gp7 三服务）。

**④ 中国移动一键登录把 root/调试判定放进 native**（`libpns-2.14.23-...so`），dex 只见声明 → 若该 SDK 被初始化，风控链路上会出现 root/调试标志。

## 我们新加的功能会不会导致反作弊

| 功能 | 是否碰服务端 | 风险 | 说明 |
|---|---|---|---|
| `autoBattle` 自动战斗 / 自动推进剧情 | **否**（纯本地 hook + 本地 UI 操作） | **低** | 不改结算数字；但操作节奏会被记录，建议战斗时长保持 ≥10 s（`MinimumClearTime`） |
| `autoFarm` 跳过新手引导（清空 `GetCompulsoryTutorialList` 返回的 List） | **否**（纯本地旁路） | **中** | 客户端认为"引导已完成"，服务端仍记录"未完成"→ 状态不一致；重启可能又被下发引导，或该账号在数美侧出现"引导跳过但无对应 SetTutorial 请求"的异常序列 |
| `autoFarm` 的 SetTutorial / 领奖 / 编队（3 项未适配，未启用） | 会是（设计上要走正规接口） | 未启用 → 无风险 | 一旦接线属真实请求，风险看服务端频率容忍度 |
| `bypassExcessiveTouch`（绕过输入频率检测） | **否** | **低** | 只让本地检测器不启动，不产生网络痕迹 |
| 敌人削弱 / 秒杀 / 无限弹药等数值类 | 否 | **低-中** | 纯本地；但秒杀让通关时长趋 0，直接撞 `MinimumClearTime` |

## 是否已经全部绕过

**客户端层：✅ 基本已绕过**

- 数美 Xposed 四维枚举 → 已改 `getDeclaredMethod + hookMethod`，`methodCache` 零痕迹（成品 dex 验证 `findAndHookMethod` = 0）；**残留**：`XposedBridge.jar` 文件探测、riru 枚举、maps 扫 `/data/app/` 未针对处理
- 输入频率检测 → 已 hook `StartCheck`
- 调试 / 模拟器 / 反调试 / 多开 → 天然不命中（release 包、真机、未 ptrace）
- `XposedBridge.log` → 已移除

**native / 环境层：❌ 未绕过**

1. **`libNeko.so` 在 `/proc/self/maps` 明文可见**，libtprt 有 `dladdr` → 目前**唯一确定存在、未解决**的暴露面
2. **APK 签名/路径已交给 ACE native**（`sourceDir`/`splitSourceDirs`）→ 重打包必然与官方不同
3. **数美采集的系统属性无法伪造**（SIM/USB/硬件代号）
4. **ACE 三服务 IPC 指令集未知**（`gp6ioctl/gp7ioctl` 静态拿不到）

**结论：不能算"全部绕过"。** 准确表述：**客户端注入痕迹已清理干净，但 native 模块暴露、APK 签名/路径、环境指纹三条仍在。**

## 未验证清单（不猜）

1. libtprt 是否**真的调用** `ptrace`/`waitpid`（导入 ≠ 调用；需真机 hook 计数）
2. libtprt 是否遍历 `/data/adb`、`su` 路径（明文 0，推不出来）
3. ACE `initialize()` 对 `sourceDir`/`splitSourceDirs` 具体算什么（签名？dex 校验？CRC？）
4. 数美 maps 扫描结果是否进上报 JSON、riru 枚举结果是否上报
5. `res/xml/http.xml`（networkSecurityConfig）的域名白名单与是否含证书固定
6. 数美逐包 `signatures` 的用途（自校验 vs 已安装应用指纹）
7. 中国移动 `CheckRoot.isDeviceRooted()` 是否被业务真正调用
8. 数美两个调用方类（`l1111l111111Il/l1111l111111Il.java` 与 `$1`）dex 指令级可证有调用但源码级不可见 → 数美部分代码经过处理，静态可见性不完整
