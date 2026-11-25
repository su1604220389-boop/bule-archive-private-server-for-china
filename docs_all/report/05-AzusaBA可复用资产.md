# 05 · AzusaBA 可复用资产清单（面向 BA 国服私服）

> 分析对象：`AzusaBA模块5.2.5全源.zip`（取自 `ba辅助源码\AzusaBA5.2.5全源.zip`，4 层嵌套 + WinZip-AES）
> 解出位置：`C:\Users\su\Desktop\大肥鱼项目\BAServer\report\_tmp\azusa\src\AzusaBA\`（174 个 entry；138 个文本文件另存 UTF-8 副本在 `report\_tmp\azusa\src_utf8\app\...`，行号与原文件逐行一致，仓库里引用行号以本报告为准）
> 路径简写：**`jni/`** = `AzusaBA/app/src/main/jni/`，**`java/`** = `AzusaBA/app/src/main/java/com/kai/lobby/`，**`app/`** = `AzusaBA/app/`
> 生成时间：2026-11-13

---

## 0. 先更正一条既有结论：5.2.5 是能解开的

`项目理解-AzusaBA.md` §9 判定「密码 `圈钱狗全家死光` 与本包不匹配」。**这个结论是错的**，错在 PBKDF2 派生布局，不在密码。

- 正确布局：`dkLen = encKey(32) + macKey(32) + pv(2) = 66`，`pv = dk[64:66]`（AE-2，AES-256，salt 16 B）。
- 旧脚本 `_tools/decrypt.js:13` 用的是 `KEYLEN = 16 * STRENGTH = 48`，于是 pv 被取成 `dk[58:60]`，**密码对也永远不等**。
- 用正确布局验证：pv `4587` 命中 → 认证码 `HMAC-SHA1(macKey, ciphertext)[:10] = 0bc8dc60670bd21d4aee` 与包内一致 → inflate 后 `PK\x03\x04`，6571849 B 校验通过。

包结构（逐层都是「单 entry 套娃」，很容易误判成「就一个压缩包」）：

```
AzusaBA5.2.5全源.zip            (outer, 明文)
└─ 必看.txt + " AzusaBA5.2.5全源.zip"(注意文件名前有空格, stored)
   └─ AzusaBA5.2.5全源.zip      (AES-256 加密, 6571849 → 6573879)
      └─ AzusaBA模块5.2.5全源.zip
         └─ AzusaBA/  ← 真正的源码树（app/src/main/{java,jni,res,assets}）
```

复现命令：`report\_tmp\azusa\unlock.js`（含正确布局的 WinZip-AES 解密器，可直接复用）。

**这条修正对团队的意义**：以后任何「AzusaBA 后续版本」的包，只要还是这套 AE-2 布局，用 `unlock.js` 改密码即可解，不要再花时间爆破。

---

## 1. 结论速览

| 问题 | 一句话结论 |
|---|---|
| native 钩子框架 | **纯 Dobby inline hook**（`jni/main.cpp:1529-1532`），配套一套「指针槽改写 + keystone 现场汇编 trampoline」（`jni/Tools/PtrHook.cpp`）。没有 GOT/PLT 自动扫描器，作者是**逐个符号解析后直接 inline**。 |
| il2cpp 偏移表 | **零函数偏移硬编码**。全部走 metadata（`getaddr` → `il2cpp_class_get_method_from_name` → `methodPointer`）。il2cpp base 走 `dladdr().dli_fbase`。只有 il2cpp 运行时容器布局（List/Dictionary/array/string）是硬编码常量。 |
| 网络层 | **一行都没碰**。jni/ 下 `connect|getaddrinfo|send|recv|SSL|cert|okhttp|UnityWebRequest|socket|curl` 命中 0（仅 ImGui 上游注释误命中）。Java 侧只有它自己的公告/背景图/统计上报。 |
| 怎么绕 ACE | **没绕**。全源 `ACE|tprt|tpinfo|Tencent|xigncode` 命中 0。只有两个浅层 Java 反检测（清洗 Xposed 栈帧、清洗 native 修饰符）。真正的反检测工具箱 `jni/Anti/` 存在但**没编进 so**，作者实测崩了就删了（`jni/main.cpp:1526-1528`）。 |
| Java 侧基础设施 | **没有** Dump/Native/Probe 这类通用内存 RPC。只有 `Bridge`（toast/剪贴板/openUrl/主线程投递）+ `GLES3JNIView`（12 个 native 入口）。一切内存与反射都在 native，Java 只当系统 API 门面。 |
| 零 root 可行吗 | 是**标准 Xposed 模块**，LSPatch 理论上能跑通；但有一道**模块自签名校验**（`java/HookLoad.java:55-107`）会在「模块被内嵌重打包」时直接拒绝注入。源码里**没有任何**关于 LSPatch / 重打包 / ACE 对改包反应的注释或规避代码。 |
| 功能清单 | 26 个 hook，全部集中在**大厅解锁 / 外观 / 本地等级 / 战斗数值**。抽卡、掉落、体力、货币、关卡这些**一个都没有**——对私服反而是好消息（服务端权威的东西它本来也改不了）。 |

一句话定位：**AzusaBA 5.2.5 不是「网络中间人」也不是「反检测框架」，它是一个「il2cpp 符号驱动的客户端内存修改器」，其真正的可复用价值是那套 xdl + il2cpp 导出绑定 + 符号解析 + Dobby 装钩的底座。**

---

## 2. Q1：native 钩子框架（它到底怎么装的）

### 2.1 装钩只有一条路：DobbyHook

```c
// jni/main.cpp:1529-1532
static int InstallHook(uintptr_t target, void* replacement, void** origin) {
    if (!target) return -1;
    return DobbyHook((void*)target, replacement, origin);
}
```

`jni/main.cpp:1526-1528` 的注释是本次分析里最有价值的一段工程经验：

> 不用 MemoryHide / SeccompHook：那套会内联 hook libc 的 openat/prctl/dladdr/sigaction，还会用 mremap 把已加载的可执行页替换成诱饵页。多线程运行时替换执行页会直接 SIGSEGV（实测崩在 GLThread / UnityMain，pc 落在匿名映射）。这里只保留 DobbyHook 本身。

- 支持的签名：**任意**。Dobby 是 inline hook，不挑调用约定；代码里对所有被 hook 函数手写 AArch64 函数指针类型（例：`jni/main.cpp:793`、`1249-1250`、`1252`）。
- 没有 GOT/PLT 定位逻辑：`DobbyHook` 的目标地址全部来自 `getaddr(...)` 的返回值（metadata 解析），不是 ELF 符号表遍历。
- 返回码约定：`rc == 0 && *origin != nullptr` 才算装成功并计数（`jni/main.cpp:1695`）。

### 2.2 第二条腿：PtrHook（指针槽改写 + 现场汇编 trampoline）

这套东西 main.cpp 主流程没用，但**对我们做 connect 改写是最直接的料**：

| 能力 | 位置 | 说明 |
|---|---|---|
| 任意地址写入 | `jni/Tools/PtrHook.cpp:10-40` | `mprotect(page, RWX)` → `memcpy` → 恢复 `RX` → `__builtin___clear_cache` |
| 改写函数指针槽 | `jni/Tools/PtrHook.cpp:51-66` | `Patch(ptr_addr, target_addr)`，返回原值——**GOT 槽、vtable 槽、函数指针数组通用** |
| 分配可执行页 | `jni/Tools/PtrHook.cpp:42-49` | `mmap(RWX, MAP_ANON)` |
| 动态汇编 trampoline | `jni/Tools/PtrHook.cpp:88-157` | keystone 生成 AArch64 桩：`ldr x16,_call_point; cmp x16,x30; b.ne return`（可选的调用点校验）→ `blr _orig_func` → 执行 payload → `br` 回原函数 |
| 汇编器 | `jni/Tools/HookUtils.cpp:88-117` | `ks_open(KS_ARCH_ARM64)` + `ks_asm` |
| 全寄存器保护壳 | `jni/Tools/HookUtils.cpp:9-79` | `getRegs`/`setRegs` 成对：x0-x30 + q0-q31 全压栈/恢复，32 B 对齐，可直接嵌进我们的 shellcode 桩 |

### 2.3 它是怎么拿到 libil2cpp 基址与符号的

```c
// jni/il2cppApi/il2cpp_boot.cpp:12-32
void il2cpp_api_init(void *handle) {
    il2cpp_api_init();                       // 用 xdl_sym 把 200+ 个 il2cpp 导出绑一遍
    if (il2cpp_domain_get_assemblies) {
        Dl_info dlInfo;
        if (dladdr((void *)il2cpp_domain_get_assemblies, &dlInfo))
            il2cpp_base = (uint64_t)dlInfo.dli_fbase;     // ← 基址就是这么来的
    } else if (il2cpp_capture_memory_snapshot) { ... }    // 备用符号
    while (!il2cpp_is_vm_thread(nullptr)) sleep(1);       // 等 VM 线程
    Il2CppDomain* domain = il2cpp_domain_get();
    il2cpp_thread_attach(domain);
}
```

- 句柄来源：`jni/main.cpp:1860-1864` 用 `xdl_open("libil2cpp.so", 0)` 轮询 120 次 × 500 ms（最多等 60 s）。
- `xdl` 是自带的一套 linker 遍历/符号查找实现（`jni/il2cppApi/xdl/`，8 个文件，xdl.c 32 KB）：`xdl_open` 走 `dl_iterate_phdr` + `/proc/self/maps` 双路（`xdl.c:499-501`、`823-856`），能绕开 bionic 命名空间对 `dlsym` 的限制；`xdl_sym` 同时支持 GNU hash 与 SysV hash（`xdl.c:599-612`）。
- **这套 xdl 对我们是刚需**：国服进程里我们要拿 `libil2cpp.so` / `libunity.so` / `libmain.so` 的句柄和符号，标准 `dlopen` 常被 linker namespace 挡住。

### 2.4 能不能直接搬来做「connect 改写 / 证书校验绕过」

能搬的是**底座**，不是现成功能。三档拆开：

1. **可直接用**：`xdl_*`（拿句柄/找符号）、`PtrHook::Patch`（改 GOT 槽）、`DobbyHook`（inline hook `getaddrinfo` / `connect` / `SSL_CTX_set_verify`）、`HookUtils::Assemble`（写桩）。
2. **必须自己补**：没有任何网络符号解析、没有任何证书校验点定位。`getaddr` 只能按 il2cpp metadata 找托管方法，**找 libc/openssl 的符号要另写一套 `xdl_sym(handle, "connect")` 封装**（`xdl_sym` 本身有，但项目里没包一层 net 专用 helper）。
3. **风险提示**：inline hook 会在目标函数头部写 4/8 字节跳转。我们的审计结论是 `libil2cpp` 无 hash pin（`work/ba/audit/ace-ipc.md`），但 `libtprt.so` 具备 `mprotect/ptrace/dladdr/access/readlink` 全套能力（`work/ba/audit/anticheat-full.md:77`）——**改 libc 的 `connect` 是全局可见的**，`connect` 在 bionic 里是 thin wrapper，hook 后所有 socket 都走我们的桩，任何一次 `dladdr` + 代码段比对都会暴露。相比之下 **`PtrHook::Patch` 改目标 .so 的 GOT 槽风险小得多**（只动数据页，但会让该页从 `r--` 变 `rw-`，若 ACE 扫段权限仍可见）。

---

## 3. Q2：它用的 il2cpp 偏移表（重点：几乎没有偏移）

### 3.1 符号解析入口（26 个 hook 全部走这里）

```c
// jni/il2cppApi/il2cpp-api-functions.cpp:874-918（节选）
void *getaddr(const char *dllname, const char *namespacename,
              const char *classname, const char *methodsname, int count) {
    ...
    auto assemblies = il2cpp_domain_get_assemblies(domain, &size);
    for (int i = 0; i < size; ++i) {
        auto image = il2cpp_assembly_get_image(assemblies[i]);
        if (strcmp(il2cpp_image_get_name(image), dllname) == 0) {
            auto USclass = il2cpp_class_from_name(image, namespacename, classname);
            const MethodInfo* USmethod =
                il2cpp_class_get_method_from_name(USclass, methodsname, count);
            if (USmethod && USmethod->methodPointer) return (void*)USmethod->methodPointer;
        }
    }
}
```

调用形态：`(dll, namespace, class, method, 参数个数)`，例如

- `getaddr("BlueArchive.dll", "MX.Data", "CharacterData", "InitializeCommon", 0)` — `jni/main.cpp:1564-1565`
- `getaddr("BlueArchive.dll", "MX.Data", "MemoryLobbyData", "GetListByCharacterId", 1)` — `jni/main.cpp:1569-1570`
- `getaddr("spine-unity.dll", "Spine.Unity", "SkeletonAnimation", "LateUpdate", 0)` — `jni/main.cpp:1574-1575`

**结论：没有任何一个硬编码函数偏移。**版本更新只要类名/方法名不变，就自动跟着走。

### 3.2 自动定位（三条兜底）

| 场景 | 手段 | 位置 |
|---|---|---|
| il2cpp 基址 | `dladdr(某个 il2cpp 导出).dli_fbase`，备用 `il2cpp_capture_memory_snapshot` | `jni/il2cppApi/il2cpp_boot.cpp:17-26` |
| il2cpp API 表 | `xdl_sym(handle, #name)` 逐个按符号名绑（200+ 个），失败只 WARN 不中断 | `jni/il2cppApi/il2cpp-api-functions.cpp:18-25` + `273-278` |
| 抽象方法（无函数体） | **属性指纹找具体子类**：拿一组属性名去比对类，再取方法 | `jni/main.cpp:1420-1445`，调用 `1630-1664` |
| `MethodInfo`（要调托管方法时） | `Il2CppGetMethodOffset` / `il2cpp_class_get_method_from_name` | `jni/main.cpp:403-452`、`1622-1623` |

指纹兜底的实战价值（伪代码，见 `jni/main.cpp:1634-1662`）：

```
BattleEntity 是 abstract → ApplyDamage 没有函数体
  ↓ 找"有 HitPoint / MaxHPCapGauge 属性 且 有 ApplyDamage(3)"的类
  ↓ 找不到 → 再找"有 WeaponSetting / CostumeSetting / GearSetting"的类（= Character）
  ↓ 取其 methodPointer
```

这套「属性指纹 + 方法签名」定位法，正是我们后续换版本时最省事的东西。

### 3.3 真正硬编码的部分（都是 il2cpp 运行时布局，跨版本稳定）

| 结构 | 偏移 | 位置 |
|---|---|---|
| `Il2CppString` | `length @ +0x10`，`chars @ +0x14`（UTF-16） | `jni/main.cpp:208-210` |
| `Dictionary` | `entries @ +0x18`，`count @ +0x20`，桶体 `+0x20`，entry stride 24（`hashCode@0` `key@+8` `value@+16`） | `jni/main.cpp:258-260`、`297-304`、`1323-1325` |
| `List<T>` | `items @ +0x10`，`size @ +0x18`，元素数组数据 `+0x20`，stride 16 | `jni/main.cpp:318-332` |
| 托管对象头 | 指针有效性判据 `< 0x1000` 判非法 | `jni/main.cpp:284-295` |

### 3.4 游戏类字段偏移（少而精，版本敏感）

| 字段 | 偏移 | 位置 |
|---|---|---|
| `MemoryLobbyData.sortTable`（`Dictionary<long, List<MemoryLobbyExcel>>`） | `+0x30` | `jni/main.cpp:293-297` |
| `CharacterData.characterDic` | `+0x30`（另有 `characterSpawnTempleteIdDic @ +0x28`） | `jni/main.cpp:247-258` |
| `EntityVisual.<MyTransform>k__BackingField` | `+0x38` | `jni/main.cpp:551` |
| `DamageApplyResult.DamageTaken` | `+0x18`（`Int64`） | `jni/main.cpp:1283` |
| `BattleStat` → 数值表 | `stat + 0x28` 取 valueTable，`+0x18` entries，`+0x20` count | `jni/main.cpp:1311-1315` |

### 3.5 metadata 偏移

**不直接读 `global-metadata.dat`**，全走 il2cpp 导出 API。唯一的「dump 能力」是内置的 Perfare 版 dumper：

- `jni/il2cppApi/il2cpp_dump.cpp:182-290` 生成 `dump.cs` + `method_info.txt`，每个方法写 `0x<rva>`；
- `jni/il2cppApi/il2cpp_dump.cpp:486-535` 生成 `il2cpp_base + 0x<rva>` 形式的头文件；
- 入口 `jni/il2cppApi/Dump.cpp:28-44`（`hack_start` 轮询 `xdl_open("libil2cpp.so")`）+ `Dump.cpp:205/229`（起线程）。
- 但 `main.cpp` 主流程**没调 dump**（`jni/main.cpp:1871` 只 `il2cpp_api_init`），所以 dumper 是「带着没用的备用工具」——对我们是白捡的偏移生成器。

---

## 4. Q3：它有没有碰网络层（答案：完全没碰）

检索范围：`jni/**`、`java/**` 全部文本文件。

关键词 `connect` `getaddrinfo` `send` `recv` `SSL` `cert` `UnityWebRequest` `Http` `socket` `okhttp` `curl` `AiriSDK`：

- **`jni/**` 命中 0**（唯一命中出现在 `jni/ImGui/imgui_demo.cpp:3264` 这类上游库英文注释里，与网络无关）。
- `java/**` 只有它自己的三条链路，全部与游戏流量无关：

| 用途 | 实现 | 位置 |
|---|---|---|
| 拉公告正文 | `HttpURLConnection`，8 s 超时，16 KB 上限，60 s 节流 | `java/RemoteNotice.java:33-38`、`79` |
| 拉面板背景图 | `RemoteBg.refresh()` | `java/Bridge.java:62-69` |
| 启动统计上报 | `POST https://xn--i0vn2h5xj.top/ht/api.php`，带 `STATS_TOKEN` | `java/LauncherActivity.java:59-65` |

两条对**我们**有用的注释：

1. `java/RemoteNotice.java:16-17` —— 「跑在游戏进程里（模块是 LSPosed 注入的），所以用的是游戏自己的 INTERNET 权限，模块 APK 不需要额外声明任何权限」。
   → **载体继承目标 App 的网络权限**，重定向方案里我们不需要给自己加任何网络权限声明，这一点很重要。
2. `java/RemoteNotice.java:19-22` —— 「游戏 targetSdk=33，明文 HTTP 被系统默认禁止（`NetworkSecurityPolicy.isCleartextTrafficPermitted()==false`），所以只能用 https」。
   → 我们的私服如果走明文 HTTP，不是改客户端就行，得处理 `networkSecurityConfig`（我们审计里也记着国服 `networkSecurityConfig=@xml/http`）。这条在 AzusaBA 里是踩过的坑，直接抄结论。

**结论：AzusaBA 没有拦过任何网络/认证调用。`connect` 改写、证书校验绕过，100% 要我们自己从零写。**

---

## 5. Q4：它怎么绕 ACE（答案：没绕，而且作者明确放弃过）

### 5.1 全源检索结果

`ACE` / `tprt` / `tpinfo` / `anticheat` / `Tencent` / `xigncode`：

- `jni/**`：**0 命中**。
- `java/**`：只有一处 —— `java/HookLoad.java:684` 的类名白名单 `epic` / `xigncode` / `antihack`。

没有任何 `libtprt` 加载检测、`__tpinfo` 完整性校验绕过、签名伪造、`/proc/self/maps` 清理代码被编译进产物。

### 5.2 它实际做的两件事（都很浅）

**① 清洗 Xposed 栈帧**（`java/HookLoad.java:616-640`）

```java
private static final String[] STACK_KEYWORDS = {"xposed", "lsposed", "lspd", "weishu", "edxp"};
...
XposedHelpers.findAndHookMethod(Throwable.class, "getStackTrace", stackTraceHook);
XposedHelpers.findAndHookMethod(Thread.class,  "getStackTrace", stackTraceHook);
```

作用：任何异常栈里出现 xposed/lsposed 等包名的帧会被剔掉。**只对 Java 反射式检测有效**，对 native 扫描无效。

**② 清洗 native 修饰符**（`java/HookLoad.java:642-686`）

```java
// 665-675
if (Modifier.isNative(mod)) { ... if (shouldClean(clsName)) param.setResult(mod & ~Modifier.NATIVE); }
// 684
return lower.contains("epic") || lower.contains("xigncode") || lower.contains("antihack");
```

作用：让 `epic/xigncode/antihack` 这几个类里的 native 方法「看起来不是 native」。注意 `677-679` 的 `fixInternal` 是**空函数体**，说明这条链只做了一半。

顺带：`java/HookLoad.java:200-205` 在 `handleLoadPackage` 里先跑 `LSPosedBypass.init` / `ArtBypass.init` 再装业务 hook，包在一个 try 里（失败只记日志）。

### 5.3 真正的反检测工具箱：存在、但没编译

`jni/Anti/` 下 5 个头文件，**`jni/Android.mk:41-60` 的 `LOCAL_SRC_FILES` 里一个都没有**：

| 文件 | 体量 | 做法（对我们的 ACE 对抗极有参考价值） |
|---|---|---|
| `jni/Anti/ShadowHook.h` | 25 KB | 影子页 hook：`MAX_SHADOW_PAGES 32`（`16`），用 `MAP_FIXED_NOREPLACE` 在目标页附近 mmap RWX 影子页（`434-444`），把 hook 点搬到影子页，**原页不动** → 抗代码段比对 |
| `jni/Anti/MemoryHide.h` | 33 KB | `/proc/self/maps` 视图伪造：段重映射（file-backed → `MAP_SHARED` anon，`624-662`）、屏蔽 `/proc/self/map_files/`（`347`）、**追踪 Dobby trampoline 的匿名可执行页并记下 hook 入口原始字节**（`672-712`） |
| `jni/Anti/SeccompHook.h` | 37 KB | seccomp BPF 拦系统调用：`readlinkat` / `newfstatat` / `faccessat` / `fstat` / `mincore` / `pread64` / `readv` / `preadv` / `process_vm_readv` / `getdents64` 等（syscall 号表 `28-104`），用 `memfd_create` 造假 `/proc/self/status`（`204-206`） |
| `jni/Anti/Syscalls.h` | 10 KB | `anti_raw_syscall` 内联 svc（`19-21`），完全绕 libc |
| `jni/Anti/common.h` | 216 B | `MapEntry` 结构 |

**为什么没编**：`jni/main.cpp:1526-1528` 明写 —— 多线程下 mremap 替换执行页直接 SIGSEGV（崩在 GLThread / UnityMain，pc 落匿名映射）。

**这是本次最有价值的一条负面情报**：作者试过「maps 隐藏 + 影子页 + seccomp」，在真实游戏进程里**不可用**。如果我们想走这条路，要预期同样的崩溃率，且必须重新设计（不能整页 mremap，只能在 hook 点做原地跳转 + 事后清 maps 条目）。

### 5.4 现在的载体自身暴露面（和我们自己的审计对得上）

- payload 加载方式：模块把 `libNeko.so` 从**自己 APK 的 `lib/arm64-v8a/`** 里 copy 到**游戏自己的 `filesDir`**（`java/HookLoad.java:399-400`、`582-600`），然后 `System.load(绝对路径)`（`429` / `435`）。
- `jni/main.cpp:4304-4310` 注释也证实：`libNeko.so` 在 LSPosed 里是被**自定义 linker dlopen** 的，`JNI_OnLoad` 里 `FindClass` 找不到模块类 → 所以额外提供 `Java_com_kai_lobby_GLES3JNIView_*` 导出名（`4312-4324`）让 ART 自己绑定，并且 `JNI_OnLoad` **永远返回成功**（`4326-4338`）。
- 这条路径的痕迹：`/proc/self/maps` 里出现 `/data/data/com.RoamingStar.BlueArchive/files/libNeko.so` —— 和我们审计里「`libNeko.so` 明文可见是唯一确定未解决暴露面」（`work/ba/audit/anticheat-full.md:139-140`）**是同一个问题，作者也没解决**。

---

## 6. Q5：Java 侧基础设施（没有 Dump/Native/Probe，但有一副现成的壳）

### 6.1 有什么

| 组件 | 能力 | 位置 |
|---|---|---|
| `HookLoad` | Xposed 入口；签名自检；日志落盘（三路径回落）；payload 解压/加载（三种加载策略）；音量键唤起；运行模式读取（四级回落） | `java/HookLoad.java:37`、`152-235`、`394-536` |
| `Bridge` | native→Java 回调：`onInjected` / `refreshNotice` / `refreshBg` / `openUrl` / `paste`（剪贴板）/ `postToMain`（投递到 UnityMain）/ `toast` | `java/Bridge.java:41-48`、`53-69`、`72-83`、`88-101`、`107-119` |
| `GLES3JNIView` | 12 个 native 入口；overlay 用 `GLSurfaceView` + `ZOrderOnTop` + `TRANSLUCENT` | `java/GLES3JNIView.java:52-83`、`12-18` |
| `MainActivity` | 把 overlay 挂到 `android.R.id.content`（不是 WindowManager，因此**不需要悬浮窗权限、不会 BadTokenException**），按需挂载 | `java/MainActivity.java:52-60`、`13-23`（注释） |
| `ModeProvider` | `ContentProvider.call("getMode")` 跨 uid 传运行模式；注释点名 **Android 16 上 `XSharedPreferences` 返回空 map** | `java/ModeProvider.java:34-48`、`13-15` |
| `LauncherActivity` | 模块自家 UI：公告弹窗、模式选择（写三处）、统计上报 | `java/LauncherActivity.java:43-46`、`51`、`59-65` |

### 6.2 没有什么（这决定了我们必须自建什么）

- **没有 Java 侧内存读写**（没有 `/proc/pid/mem`、没有 `process_vm_readv` 的 Java 封装）。
- **没有 Java 反射调用托管方法的 RPC**（没有 `Dump.java` / `Native.java` / `Probe.java` 之类）。
- 一切「读/写游戏内存、调托管方法」都在 native，Java 只负责：Toast、剪贴板、浏览器、主线程投递、GL overlay。

### 6.3 对「在游戏进程里做内存读写 / 调 native / 反射」的复用判断

- **要内存读写**：用 `jni/Tools/Tools.cpp:9-30`（`process_vm_readv/writev` 封装）+ `jni/Tools/Syscalls.h`（`sys_open/read/write/mprotect/memcpy` 直接 svc，绕 libc hook）。
- **要调托管方法**：用 `Il2CppGetMethodOffset` / `il2cpp_runtime_invoke`（`jni/il2cppApi/il2cpp-api-functions.h:259-265`）。
- **要跨线程动游戏状态**：必须走 `Bridge.postToMain` → `GLES3JNIView.doAction`（`java/Bridge.java:107-119`），注释解释了「Unity 的 UnityMain 就是 Android 主线程」（`104-105`）。这套「native 算 → Handler 投递 → 主线程执行」的骨架是现成的、可复用的。
- **进程内日志**：`java/HookLoad.java:163-198` 三路径回落 + `559-580` 批量 flush；native 侧 `jni/main.cpp:38-64`。这套「写游戏自己 files 目录」的做法在 LSPosed/LSPatch 下都成立，值得抄。

---

## 7. Q6：零 root（LSPatch）交付可行性

### 7.1 它是标准 Xposed 模块（证据）

| 证据 | 位置 |
|---|---|
| 入口声明 | `app/src/main/assets/xposed_init` → `com.kai.lobby.HookLoad`（1 行） |
| manifest 元数据 | `app/src/main/AndroidManifest.xml:40-53`：`xposedmodule=true`（40）、`xposeddescription`（44）、`xposedminversion=53`（48）、`xposedscope=@array/xposed_scope`（52-53） |
| API 依赖 | `app/libs/xposed-api-82_compileonly.jar`（`compileOnly`，见 `app/build.gradle:47-48`） |
| 接口实现 | `implements IXposedHookLoadPackage, IXposedHookZygoteInit`（`java/HookLoad.java:37`） |
| 依赖 `modulePath` | `java/HookLoad.java:61-64`（`initZygote` 存路径）→ `585`（`new ZipFile(MODULE_PATH)` 解 payload） |

目标包名 4 个（`java/HookLoad.java:47-50`）：国际服 `com.nexon.bluearchive`、`com.YostarJP.BlueArchive`、`com.RoamingStar.BlueArchive`（**国服**）、`com.RoamingStar.BlueArchive.bilibili`。

### 7.2 LSPatch 能不能跑：能，但要过三道坎

**坎 1：模块自签名校验（最可能踩的坑）**

```java
// java/HookLoad.java:52-56
private static boolean sModuleTampered = false;
private static final String EXPECTED_SHA256 =
        "a40da80a59d170caa950cf15c18c454d47a39b26989d8b640ecd745ba71bf5dc";

// 152-159
if (sModuleTampered || !verifyModuleSignature()) {
    sModuleTampered = true;
    Log.w(TAG, "模块被篡改/重打包，拒绝注入 " + param.packageName);
    return;
}
```

- 校验对象是**模块 APK 自身**的签名（`84-85` 用 `getPackageArchiveInfo(MODULE_PATH, GET_SIGNATURES)`）。
- **LSPatch 不重签模块** → 正常能过。
- **但如果把模块「内嵌」进被 patch 的 APK（本地模式合并）**，`MODULE_PATH` 指向的就不是原模块 APK，签名必然变 → 直接拒绝注入。
- 已知的放行口子（改造成本极低）：`MODULE_PATH == null` 直接 `return true`（`71-73`）；任何异常也 `return true`（`101-106`）；`PackageManager` 未就绪也放行（`76-83`，注释说明了历史上因为这个自锁导致注入彻底不工作）。

**坎 2：payload 的取用路径**

- 模块从**自己 APK** 里 `zip.getEntry("lib/arm64-v8a/libNeko.so")` 和 `assets/libNeko_linker.so` 取（`java/HookLoad.java:586-592`）。
- 若模块被内嵌合并进游戏 APK，`MODULE_PATH` 里就没有这两个 entry → `extractLibs` 返回 false → 提示「解压 so 失败」（`402-407`）。
- 若模块以独立 APK 存在（LSPatch 的「模块管理」模式），则完全正常。

**坎 3：加载策略只剩一条能用**

三套加载依次尝试（`java/HookLoad.java:422-447`）：`System.load(payload 绝对路径)` → `System.loadLibrary("Neko")` → `System.load(linker 绝对路径)`。每步都用 `GLES3JNIView.IsUIOpen()` 验证 native 方法**真的绑定上了**（`440-441`，注释说「linker 方式会 load 成功但方法解析不到」）。

→ 这套「解压到私有目录 + 绝对路径 `System.load` + 实测探测」的写法，**本身就是免 root 的**（不依赖 `/data/local/tmp`、不依赖 `su`、不依赖改 APK 的 `lib/`）。可直接移植。

### 7.3 APK 被 LSPatch 重打包后 ACE 会怎么处理

**源码里没有任何相关注释或规避代码**（全源 `LSPatch|重打包|__tpinfo` 命中 0）。AzusaBA 之所以不碰这个问题，是因为它**根本不改游戏 APK**——纯运行时注入，这是它最大的架构优势。

结合我们自己的审计结论，重打包的代价是明确的：

| 改动 | 结果 | 出处 |
|---|---|---|
| 往 APK 加新 `.so` / 改 `libmain.so` 的 `DT_NEEDED` | 无日志闪退（ACE 直接杀） | `work/ba/audit/ba-pitfalls.md:10` |
| 不删 `assets/__tpinfo.{tsc,tsc.sig,tsd,tsd.sig,tp}` | 改包后启动即闪退 | `work/ba/audit/ba-pitfalls.md:9`、`16` |
| 新增 `classes3.dex`（哪怕 660 B） | 卡 Android 启动界面（与 ACE 无关，是启动链问题） | `work/ba/audit/ba-pitfalls.md:52` |
| 只做原地字节补丁（如 libunity 证书绕过 4 B） | 可用 | `work/ba/audit/ba-pitfalls.md:10` |
| ACE 把 `sourceDir` / `splitSourceDirs` 交给 native 做完整性校验 | **签名/路径必然与原包不同 = 最现实风险点** | `work/ba/audit/anticheat-full.md:108-112` |

**结论**：LSPatch 是「改 APK」路线，直接撞 ACE 的完整性面；LSPosed 是「不改 APK」路线，不撞这一面。如果必须零 root，正确姿势是 **LSPatch 的「模块独立 APK + 只 patch 目标 App 的最小集合」**，并且**绝不**把 payload `.so` 塞进 APK。

---

## 8. Q7：功能清单（以及对我们「私服要不要自己实现」的判断）

### 8.1 26 个 hook（`jni/main.cpp:1740-1766`，idx 与其后注释一一对应）

| idx | 目标符号 | 作用 | 归类 |
|---|---|---|---|
| 0 | `LobbySpineLoadInfo.SameCharacterAndCostume` | 让「不同角色」被判为同一角色 | 换皮 |
| 1 | `UILobbyService.CreateLobbySpineLoadInfo` | 造任意角色的 LoadInfo | 换皮 |
| 2 | `UILobbyService.TryGetMemoryLobbyExcelByIndex` | 伪造记忆大厅 Excel 记录 | 解锁 |
| 3 | `UILobbyService.LobbySpineCount` | 大厅立绘数量 | 解锁 |
| 4 | `UILobbyService.MemorialLobbySpineCount` | 纪念大厅立绘数量 | 解锁 |
| 5 | `UILobbyService.CanRotateLobbySpine` | 允许旋转 | 解锁 |
| 6 | `MemoryLobbyData.HasDataByCharacterId` | 判定「有该角色」→ 恒真 | 解锁 |
| 7 | `MemoryLobbyData.InitializeCommon` | 捕获单例 | 底座 |
| 8 | `CharacterData.InitializeCommon` | 捕获单例 | 底座 |
| 9 | `LobbyCharacterSelectData.IsMemorial` | 纪念模式判定 | 解锁 |
| 10 | `MemoryLobbyData.GetListByCharacterId` | **真正的解锁点**（返回伪造列表） | 解锁 |
| 11 | `BattleEntity.ApplyDamage`（指纹定位到 `Character`） | 伤害倍率 / 锁血 | 战斗 |
| 12 | `BattleEntity.get_CurrentStat` | 改 BattleStat 表 | 战斗 |
| 13 | `SkeletonAnimation.LateUpdate` | 大厅/战斗立绘逐帧变换 | 外观 |
| 14-15 | `SpineBase.OnEnable` / `Awake` | 挂接角色骨架 | 外观 |
| ~~16~~ | ~~`AccountDB.get_Level`~~ | **永久移除**（`jni/main.cpp:1756`，闪退元凶） | — |
| 17 | `AccountLevelExpIndicator.SetLevelExp` | 本地等级 | 外观 |
| 18 | `UILobbyAccountInfo.RefrehsLevelExp` | 大厅等级标签 | 外观 |
| 19-22 | `UIAccountInfo.RefreshLevelExp / RefreshFavorite / RefreshAll / OnOpened` | 账号页立绘与等级 | 外观 |
| 23 | `UIService.LoadPortraitSpineCharacterAsync` | 账号页立绘换人 | 外观 |
| 24-26 | `EntityVisual.Awake / Start`、`CharacterVisual.LateUpdate` | 3D 战斗角色外观 | 外观 |

### 8.2 配置面（`jni/Game/Config.h:8-61`）

- 大厅：`unlockAllMemoryLobby`、`replaceCharacter`(默认 ID 10059)、`globalReplace`、`autoApply`
- 战斗：`enableDamageMult`(10x)、`enableGodMode`、`enableMoveSpeed`(3x)、`enableAttackRange`(3x)、`enableFireRate`(5x)
- 外观：`enableRain`、`enableSnow`、`fontScalePercent`
- 大厅人物：`autoRotate`、`rotateSpeedDeg`、`customScale`、`scalePercent`、`upsideDown`
- 本地等级：`enable`（默认关）、`level`（1-90）

配置持久化是**裸结构体直接写文件**：`jni/Game/Config.cpp:13-41`，用 `sys_open/sys_write`（走 `jni/Tools/Syscalls.h`，绕 libc），带 `version = 8` 字段（`Config.h:60`）。简单粗暴但够用。

### 8.3 两条值得抄的工程细节

1. **`localLevel` 的血泪注释**（`jni/Game/Config.h:47-52`）：
   > 必须默认关闭：开启后 `AccountDB.get_Level` 返回 90，获胜结算走升级流程时会去查 `AccountLevelExcel[91]` → 空行 → `__strcmp(null)` → SIGSEGV。
   → 凡是「把本地值改到表范围外」的功能，都会在结算链路上炸。私服如果做本地等级展示，同理会踩。
2. **两套故障隔离**（`jni/main.cpp:1705-1736`）：`azusa_safe.flag`（只加载 so、一个 hook 都不装，用来区分「游戏自身闪退」vs「hook 导致」）+ `azusa_hookmask.txt`（十进制位掩码，按位跳过指定 hook，用来二分定位崩哪个钩子）。这套排查手法比任何日志都好用，**直接搬**。

### 8.4 对私服的取舍（服务端权威 vs 客户端本地）

| 类别 | AzusaBA 做了吗 | 私服要不要自己做 | 理由 |
|---|---|---|---|
| 抽卡结果、掉落、体力、货币、关卡解锁、任务、Cost | **完全没做**（26 个 hook 里 0 个碰这些） | **必须自己做** | 服务端权威，客户端改不了（也不该改） |
| 战斗伤害/锁血/移速/射程/射速 | 做了（idx 11/12，改客户端 BattleStat） | **不必做** | 客户端本地计算 + 上报，模块改的就是本地表 |
| 记忆大厅/角色解锁、立绘 | 做了（idx 0-10、19-23） | **不必做** | `Config.h:36` 明写「都是本地视觉，不改服务器数据」；服务端不校验 |
| 大厅人物旋转/缩放/倒立、雨雪特效、字号 | 做了（idx 13-15、24-26） | **不必做** | 纯本地渲染 |
| 本地等级显示 | 做了（idx 17-22） | **不必做**，但注意 §8.3-1 的坑 | 纯显示 |
| 秒通关/一键起步/自动战斗 | **5.2.5 没有**（这是 3.5 Lua 版的功能，见 `rlgg全源AzusaBA3.5(1).lua`） | 视服务端实现 | 3.5 走 GameGuardian 内存搜特征值，与本源码无关 |

也就是说：**AzusaBA 5.2.5 改的全部是「服务端不管的东西」，这正是私服最不需要自己实现的那一块 —— 反过来说，AzusaBA 源码里没有任何一段能帮我们实现私服真正需要的那部分（协议、账号、抽卡、掉落）。**

---

## 9. 三档资产总表

### 9.1 可直接搬（授权明确、无需改动或只需改常量）

| # | 资产 | 位置 | 为什么能直接用 |
|---|---|---|---|
| A1 | `xdl` 全套（8 文件，约 66 KB） | `jni/il2cppApi/xdl/` | 绕 bionic 命名空间拿 `.so` 句柄/符号；`xdl_open`/`xdl_sym`/`xdl_addr`/`xdl_iterate_phdr` 全有，独立无依赖 |
| A2 | il2cpp 导出绑定表 | `jni/il2cppApi/il2cpp-api-functions.cpp:18-278` + `.h` | 200+ 个 `il2cpp_*` 的函数指针声明 + `DO_API` 宏，粘上就能用 |
| A3 | `getaddr` 符号解析 | `jni/il2cppApi/il2cpp-api-functions.cpp:874-918` | 「dll+ns+class+method+argc → 函数地址」，与游戏版本解耦 |
| A4 | `il2cpp_boot.cpp` | `jni/il2cppApi/il2cpp_boot.cpp:1-32` | 32 行完成「绑 API → 取 base → 等 VM → attach」 |
| A5 | il2cpp 类型定义 | `jni/il2cppApi/il2cpp-class.h`、`il2cpp-tabledefs.h` | `Il2CppClass`/`MethodInfo`/字段结构，标准件 |
| A6 | 直接系统调用层 | `jni/Tools/Syscalls.h`（64-252） | `sys_openat/read/write/mprotect/memcpy/strtoul_hex` 全走 `svc 0`，绕 libc hook |
| A7 | 内存工具 | `jni/Tools/Tools.cpp:9-179` | `process_vm_readv/writev`、`/proc/self/maps` 基址、`editMemProt`、`getMemPermission` |
| A8 | 字符串混淆 | `jni/Includes/obfuscate.h:191`（`OBFUSCATE`）+ `Logger.h:22-27` | 编译期加密全部日志与关键路径串 |
| A9 | Dobby | `jni/libs/dobby.h`、`jni/libs/libraries/*/libdobby.a`（366 KB arm64 / 283 KB armv7） | 预编译 inline hook 引擎 |
| A10 | 指针槽改写 + trampoline | `jni/Tools/PtrHook.cpp:10-157`、`HookUtils.cpp:9-117` | 见 §2.2 |
| A11 | 故障隔离 | `jni/main.cpp:1705-1736` | safe flag + hook 位掩码 |
| A12 | 日志落盘 | `java/HookLoad.java:163-198`、`559-580`；`jni/main.cpp:38-64` | 三路径回落 + 批量 flush |
| A13 | `Bridge` / `GLES3JNIView` 桥骨架 | `java/Bridge.java`、`java/GLES3JNIView.java`、`java/MainActivity.java` | toast/剪贴板/openUrl/主线程投递/overlay 挂载，全是不依赖 root 的常规 API |
| A14 | 跨 uid 传参 | `java/ModeProvider.java:34-48` | 比 `XSharedPreferences` 稳（Android 16 上后者返回空） |
| A15 | WinZip-AES 解密器（我们修的） | `report\_tmp\azusa\unlock.js` | 配套 66 字节派生布局，以后解同族包直接用 |

### 9.2 需改造

| # | 资产 | 位置 | 要改什么 |
|---|---|---|---|
| B1 | Xposed 入口 | `java/HookLoad.java:37-235` | 包名/签名常量（`47-56`）换我们的；**必须验证 `onCreate` hook 在国服能装上**（见 §10-风险 3） |
| B2 | payload 加载链 | `java/HookLoad.java:394-536`、`582-614` | so 名、assets linker 名、加载顺序；`libNeko_linker.so`（1.15 MB）**无源码**，要么逆向要么删掉只留 `System.load` 绝对路径 |
| B3 | 反检测 | `java/HookLoad.java:616-686` | 现在只藏 Xposed，我们要藏的是「模块 so 在 maps 可见」+「代码段被改」；`ArtBypass.fixInternal`（`677-679`）是空实现，等于没做 |
| B4 | 装钩表 | `jni/main.cpp:1740-1766` | 26 个里只留我们需要的 2-3 个（或全删），换成 `connect`/`getaddrinfo`/`SSL_CTX_set_verify` 的解析 |
| B5 | 符号解析扩展 | `jni/il2cppApi/il2cpp-api-functions.cpp:874` | 现有 `getaddr` 只认 il2cpp metadata；要为 libc/openssl/libunity 写一个 `xdl_sym` 版 helper |
| B6 | ImGui overlay | `jni/main.cpp:2340-4260`（页面与控件，约 1900 行）+ `jni/ImGui/*`（含 11 MB `Font.h`） | 体量太大，建议**砍掉**只留 `GLES3JNIView` 空壳；要留则换页面 |
| B7 | 公告/统计通道 | `java/RemoteNotice.java`、`java/LauncherActivity.java:59-65` | 换成我们自己的下发地址；`STATS_TOKEN` 硬编码要清掉 |
| B8 | 运行模式 | `java/HookLoad.java:311-376` | 四级回落保留，去掉 `XSharedPreferences` 分支（LSPatch 下不可用） |
| B9 | 目标包名 | `java/HookLoad.java:47-50`、`jni/main.cpp:53-57`、`1705-1727` | 只留国服 `com.RoamingStar.BlueArchive` |

### 9.3 只能参考（思路价值 > 代码价值）

| # | 资产 | 位置 | 参考什么 |
|---|---|---|---|
| C1 | ShadowHook 影子页 | `jni/Anti/ShadowHook.h:16`、`434-444` | 「hook 点搬到 `MAP_FIXED_NOREPLACE` 影子页、原页不动」——抗代码段比对的正解，但作者没敢用 |
| C2 | MemoryHide maps 伪造 | `jni/Anti/MemoryHide.h:347`、`624-712` | 段重映射 + `map_files` 屏蔽 + 记录 hook 入口原始字节。**作者实测崩，只能当设计参考** |
| C3 | SeccompHook | `jni/Anti/SeccompHook.h:28-104`、`204-206` | seccomp BPF 拦 `readlinkat/stat/fstatat/faccessat/mincore/pread64/process_vm_readv/getdents64`；用 `memfd_create` 造假 `/proc/self/status`。这是对付 `libtprt` 扫描最对口的思路 |
| C4 | 属性指纹定位类 | `jni/main.cpp:1420-1445` | 抽象基类 → 具体子类的定位法（换版本时救命） |
| C5 | 战斗数值修改 | `jni/main.cpp:1283`、`1307-1378` | statKey 表（13/21/14/38/2/39/34/20）+ 原值缓存回滚。**版本敏感，仅参考** |
| C6 | 大厅解锁 10 个 hook | `jni/main.cpp:1740-1750` | 业务价值低，但「客户端解锁判定点在哪」这十个符号名是很好的地图 |
| C7 | 配置持久化 | `jni/Game/Config.cpp:13-41` | 裸结构体 + version 字段，简单但升级会错位 |
| C8 | 加载器三策略 + 实测探测 | `java/HookLoad.java:422-447` | 「load 成功 ≠ 方法绑定成功，必须调一次 native 探测」这条经验很硬 |
| C9 | safemode/hookmask 二分法 | `jni/main.cpp:1705-1736` | 崩溃归因方法论 |

---

## 10. 如果我们用 LSPosed 模块作为重定向载体：风险与工作量评估

### 10.1 前提（必须先承认的两条硬事实）

1. **国服进程里的 `XposedBridge` 是混淆替身类，Java hook 全废。**
   → AzusaBA 那套 `java/HookLoad.java:616-686` 的 Java 反检测，以及所有 `XposedHelpers.findAndHookMethod` 对**游戏类**的 hook，在我们环境里**不可用**。
   → 但这**不否定载体本身**：`IXposedHookLoadPackage` 回调是由 LSPosed/LSPatch 自己调起来的（不是靠 hook 游戏类），只要它被调起来，我们就能在回调里**加载自己的 .so / 执行我们的 Java 代码**。所以正确用法是：**把 LSPosed 当「进入游戏进程的跳板」，进入后一切靠 native。**
2. **AzusaBA 已在真实游戏里验证过：Dobby inline hook + il2cpp 符号解析 + 不改 APK，不触发 ACE 杀进程。**
   → 我们沿用同一套底座，增量风险主要来自「我们新加的网络 hook」和「我们自己的 .so 在 maps 里的可见性」。

### 10.2 风险清单（按严重度）

| # | 风险 | 依据 | 缓解 |
|---|---|---|---|
| R1 | **我们自己的 `.so` 在 `/proc/self/maps` 明文可见** | `work/ba/audit/anticheat-full.md:139-140`；AzusaBA 同样暴露（`java/HookLoad.java:399`、`429`） | 三条路，按代价排序：①**不加载自有 .so**（逻辑全塞进 `libil2cpp.so` 的 hook + 模块 dex，但 inline hook 必须有代码页 → 只能改 GOT 槽）；②照 `Anti/MemoryHide.h:624-662` 的思路把自有段的 `maps` 行伪装，但**作者实测崩**（`jni/main.cpp:1526-1528`）；③接受暴露，赌 ACE 不上报（审计结论是「能力有、调用未证」） |
| R2 | **inline hook 改代码段被比对** | `libtprt` 有 `mprotect/dladdr/ptrace`（`anticheat-full.md:77`）；`libil2cpp` 无 hash pin（`ace-ipc.md`） | 优先用 **GOT 槽改写**（`PtrHook::Patch`）而不是 inline hook；若必须 inline，只 hook 冷路径（如 `getaddrinfo` 只在解析域名时调） |
| R3 | **Xposed 入口在国服可能装不上** | HookLoad 依赖 hook `com.unity3d.player.UnityPlayerActivity.onCreate`（`java/HookLoad.java:207-233`）；而国服主 Activity 是它的子类 `com.tech.sdk.bridge.TechSDKUnityPlayerActivity`（`work/ba/audit/ba-java.md:55-59`） | 子类**没重写 `onCreate`**，所以 hook 父类仍会触发（`ba-java.md:84` 已确认）。但若 XposedBridge 是替身类导致 `findAndHookMethod` 失败，`231-233` 只记日志 → **payload 永不加载**。**移植第一优先级：把「进游戏进程后加载 payload」的触发改成不依赖 Xposed hook 游戏类**（例如 LSPosed 的 `IXposedHookLoadPackage` 里直接用 `Application.attachBaseContext` 之前/之后的时机起线程，或用自己的 `ContentProvider` 被系统拉起） |
| R4 | **重定向的落点未知** | AzusaBA 全源 0 行网络代码；我们审计已知 `CertificatePins=0`、`networkSecurityConfig=@xml/http`、客户端走 HTTPS（`RemoteNotice.java:19-22`）表明 targetSdk 33 禁明文 | 先抓包确认国服到底走 `UnityWebRequest`+UnityTLS 还是 okhttp/AiriSDK 自建栈，再决定 hook 点。**这一步不做，工作量估算全部是猜** |
| R5 | **LSPatch 改 APK 直接撞 ACE 完整性面** | `work/ba/audit/ba-pitfalls.md:9-11`、`anticheat-full.md:108-112` | 若要零 root：只走「模块独立 APK」模式，payload 一律运行时解压到私有目录，**绝不**往游戏 APK 里加 `.so`/dex 类 |
| R6 | **`libNeko_linker.so` 无源码** | `app/src/main/assets/libNeko_linker.so`（1.15 MB），全源无对应 C/CPP | 该文件作用是把 payload 从非标准路径 dlopen 进来。我们若不换路径就直接用它的**行为**（黑盒），换路径则要自己写 mini-linker（约 1-2 人日） |

### 10.3 工作量（按「能跑起来」为准，不含调试发现期）

| 阶段 | 内容 | 人日 |
|---|---|---|
| P1 骨架移植 | 模块改名/包名、清理 26 个业务 hook 与 2000 行 ImGui、只留 `Bridge`+`GLES3JNIView`+日志+safe flag | 2-3 |
| P2 native 底座 | 搬 `xdl` + `il2cpp-api-functions` + `il2cpp_boot`；验证 `getaddr` 在国服版本能解析（这是最快的一次「能跑」验证点） | 1-2 |
| P3 入口可靠性 | 解决 R3：不依赖「hook Unity 类」就能在游戏进程里起我们的 native 线程 | 1-2 |
| P4 网络 hook | R4 定位 + `getaddrinfo`/`connect` 重定向 + 主机名替换 + 失败回落 + 多路备选 | 3-5 |
| P5 证书 | 自签根证书注入（`SSL_CTX_set_verify` / `X509_check_host` 或 UnityTLS 对应点）+ 证书 pinning 兜底 | 2-4（取决于 R4 结果） |
| P6 隐蔽性 | maps 清理 / 段权限还原 / 反 `dladdr` 反查；按 R1 选型 | 3-5，**成功率不可保证**（作者试过并放弃） |
| P7 免 root（可选） | LSPatch 打包 + 过 `EXPECTED_SHA256` + 过 `__tpinfo` + 签名差异 | 2-4 |
| **合计** | | **14-25 人日**（不含 R4 的未知数） |

### 10.4 我的建议（结论）

1. **技术底子直接拿 A1-A5**（xdl + il2cpp 绑定 + `getaddr` + `il2cpp_boot`）。这四件是 AzusaBA 最硬的资产，且完全不涉及作弊业务逻辑，风险最低。
2. **不要拿它的 UI 和业务 hook**（26 个 hook 对私服毫无用处，ImGui 那 2000 行是纯负担）。
3. **重定向的落点要自己做一次抓包定位**（R4），不要指望从 AzusaBA 源码里找到答案 —— 它一行网络代码都没有。
4. **载体选型建议**：如果目标只是「让客户端指向我们服务器」，我们 `bapatch` 里已有的 `patch_got*.py` / `patch_host*.py` / `patch_connect*.py` 系列是**改包原地补丁**路线，已经验证可行（`ba-pitfalls.md:10`「只做原地字节补丁」）—— 这条路的 ACE 面比 LSPatch 小得多，也比模块路线成熟。
   LSPosed 模块路线**唯一不可替代的优势**是：**完全不动 APK**，因此不触碰 ACE 的 `sourceDir` 完整性校验面（`anticheat-full.md:108-112`）。如果哪天改包被 ACE 收紧了，模块路线就是备用方案 —— 但请按 §10.2-R1 的代价预期它。
5. **一个必须提前说清的数字**：ACE 对抗（P6）占 3-5 人日却「成功率不可保证」；如果不做 P6，模块在 maps 里的暴露是**已知且未解决**的（作者也没解决）。所以在方案评审时，不要把它写成「已解决」。

---

## 附录 A：关键行号速查

| 想找什么 | 去哪 |
|---|---|
| Xposed 入口 / 目标包名 | `java/HookLoad.java:37`、`47-50` |
| 模块自签名校验（LSPatch 拦路虎） | `java/HookLoad.java:52-56`、`72-107`、`152-159` |
| payload 解压与加载 | `java/HookLoad.java:394-536`、`582-614` |
| 运行模式四级回落 | `java/HookLoad.java:311-376` |
| 反检测（浅） | `java/HookLoad.java:616-686` |
| native 桥 / 主线程投递 | `java/Bridge.java:41-119` |
| native 入口声明（12 个） | `java/GLES3JNIView.java:52-83` |
| overlay 挂载（免权限） | `java/MainActivity.java:13-23`、`52-60` |
| 装钩函数（Dobby） | `jni/main.cpp:1529-1532` |
| 为什么弃用 Anti/ | `jni/main.cpp:1526-1528` |
| 26 个 hook 表 | `jni/main.cpp:1740-1766` |
| 符号解析调用 | `jni/main.cpp:1548-1673` |
| 属性指纹找类 | `jni/main.cpp:1420-1445`、`1630-1664` |
| il2cpp 基址 | `jni/il2cppApi/il2cpp_boot.cpp:17-26` |
| il2cpp API 绑定宏 | `jni/il2cppApi/il2cpp-api-functions.cpp:18-25`、`273-278` |
| `getaddr` 本体 | `jni/il2cppApi/il2cpp-api-functions.cpp:874-918` |
| xdl 句柄/符号 | `jni/il2cppApi/xdl/xdl.c:539`、`599-612`、`823-856` |
| 指针槽改写 | `jni/Tools/PtrHook.cpp:51-66` |
| keystone trampoline | `jni/Tools/PtrHook.cpp:88-157`、`HookUtils.cpp:88-117` |
| 直接 syscall | `jni/Tools/Syscalls.h:64-252` |
| 内存读写 / maps 基址 | `jni/Tools/Tools.cpp:9-30`、`68-109` |
| 字符串混淆 | `jni/Includes/obfuscate.h:191` |
| 编译清单（Anti/ 缺席的证据） | `jni/Android.mk:41-60` |
| 反检测工具箱（未编译） | `jni/Anti/ShadowHook.h`、`MemoryHide.h`、`SeccompHook.h`、`Syscalls.h` |
| 配置结构 | `jni/Game/Config.h:8-61`、`Config.cpp:13-41` |
| il2cpp dumper（备用） | `jni/il2cppApi/Dump.cpp:28-44`、`il2cpp_dump.cpp:182-290`、`486-535` |
| 解锁 5.2.5 的密码器 | `report\_tmp\azusa\unlock.js` |

## 附录 B：本次分析产出物（均在 `report\_tmp\azusa\`）

| 文件 | 说明 |
|---|---|
| `unlock.js` | 正确的 WinZip-AES 解密器（32+32+2 布局），含 pv/HMAC/解压校验 |
| `crack.py` / `crack2.py` / `verify.js` | 密码候选扫描与 HMAC 复核（证实 2 B pv 会大量假阳性，必须做 HMAC 复核） |
| `level4.zip` / `src\AzusaBA\` | 最终解出的源码树（138 个文本文件 + 资源） |
| `src_utf8\` | 同结构 UTF-8 副本，行号与原文件一致，便于检索与引用 |
