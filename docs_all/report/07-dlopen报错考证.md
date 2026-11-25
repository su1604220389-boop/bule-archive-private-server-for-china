# 07 · `dlopen failed: file offset for the library "libil2cpp.so" >= file size: 0 >= 0` 考证

> 侦察员：`dlopen-scout`（不接触设备，仅资料考证 + 静态分析 + 推导）
> 日期：2026-11-14
> 目标：`com.RoamingStar.BlueArchive` / Unity 2021.3.56f2 / targetSdk 33 / `extractNativeLibs=true` / `primaryCpuAbi=arm64-v8a` / Android 14 (OPPO PLR110, KernelSU)
>
> **取证方式说明**：本会话的 `web_fetch` / `research` 全文抓取通道返回 `HTTP 404`（backend `api.deepseek.com/v1/tools/fetch` 不可用），**无法下载 AOSP 源文件全文**。因此 bionic 源码引用来自搜索引擎索引到的 `android.googlesource.com` / `GitHub aosp-mirror` / `LineageOS` 源码片段（下方逐条给链接）；本轮**未逐字核对 android-14 分支的最终行号**，凡属此类均标注「推断」。Unity 侧结论**全部来自本地真机 APK 里 `libmain.so` 的反编译**（Ghidra，sha256 `e2a12641…`），不是猜测。

---

## 一、结论速览

| # | 结论 | 性质 |
|---|---|---|
| 1 | 报错串出自 bionic `linker/linker.cpp` 的 `load_library()`，格式 `"file offset for the library \"%s\" >= file size: %" PRId64 " >= %" PRId64`，两个数字依次是 **`file_offset`** 和 **`fstat(fd).st_size`**。`0 >= 0` 的唯一算术含义是：**`file_offset == 0` 且 `fstat` 返回的文件大小 `st_size == 0`**——即 loader 打开的那个 fd 指向**一个 0 字节对象**。 | **确证** |
| 2 | Unity 的 `loadNative` 对该 so 做了**两次 `dlopen`**：先 `dlopen("<nativeLibraryDir>/libil2cpp.so", RTLD_LAZY)`，失败再 `dlopen("libil2cpp.so", RTLD_LAZY)`；报错文本里 Unity 打的是**全路径**、linker 打的是**裸 soname `libil2cpp.so`**，二者不一致说明 **报错来自第二次（裸名）调用，且两次都返回了 NULL**。`libmain.so+0xcbc` 精确落在**调用 `JNIEnv->FatalError` 的间接调用返回地址**上，因此可反推：失败点是「两次 dlopen 都失败」，**不是** `JNI_OnLoad` 失败、也**不是**找不到 `il2cpp_init` 符号。 | **确证** |
| 3 | 根因：`<nativeLibraryDir>/libil2cpp.so` 在**应用视角**是 0 字节。判据是结构性的、不需要设备——同一个 `LoadTask` 里 **`libunity.so` 先加载且成功**（否则报错里的文件名会是 `libunity.so`），它与 `libil2cpp.so` **同目录、同函数、同一次 `snprintf`**；目录/watchdog/SELinux 标签/命名空间若是坏的，`libunity.so` 也活不了。故坏的只有那个被 `cat new > dst` 覆盖过的文件本身；`cat` 的 `>` 是 `O_TRUNC` 语义，**写入未落地就留下 0 字节文件**。 | **推断（高置信）** |

---

## 二、错误字符串的确切出处

### 2.1 位置

`bionic/linker/linker.cpp` → **`load_library()`**（Android 10 起该函数签名改为接收 `LoadTask*`；打开动作被拆到 `open_library()` + 三个 `open_library_*` 助手）。该 `DL_ERR` 位于 `fstat` 之后的分支：

```cpp
// bionic/linker/linker.cpp  —— load_library()（Android 10~14 结构一致）
static soinfo* load_library(android_namespace_t* ns,
                            LoadTask* task,
                            LoadTaskList& load_tasks,
                            int rtld_flags,
                            const std::string& realpath) {
  off64_t file_offset = task->get_file_offset();   // ← 第一个数字的来源
  const char* name = task->get_name();             // ← 报错里被引号括起来的名字
  const android_dlextinfo* extinfo = task->get_extinfo();

  if ((file_offset % PAGE_SIZE) != 0) {
    DL_ERR("file offset for the library \"%s\" is not page-aligned: %" PRId64, name, file_offset);
    return nullptr;
  }
  if (file_offset < 0) {
    DL_ERR("file offset for the library \"%s\" is negative: %" PRId64, name, file_offset);
    return nullptr;
  }

  struct stat file_stat;
  if (TEMP_FAILURE_RETRY(fstat(task->get_fd(), &file_stat)) != 0) {
    DL_ERR("unable to stat file for the library \"%s\": %s", name, strerror(errno));
    return nullptr;
  }
  if (file_offset >= file_stat.st_size) {          // ★★★ 就是这一条
    DL_ERR("file offset for the library \"%s\" >= file size: %" PRId64 " >= %" PRId64,
           name, file_offset, file_stat.st_size);  // ← 第二个数字 = fstat 的 st_size
    return nullptr;
  }
  ...
}
```

来源（索引片段，逐字）：

- `android.googlesource.com/platform/bionic/+/ca10ac6/linker/linker.cpp` — 显示 `open_library(const char* name, off64_t* file_offset)` → `open_library_in_zipfile()` → `open_library_on_ld_library_path()` → `open_library_on_default_path()` 的调用链，以及 `load_library()` 开头的 `file_offset % PAGE_SIZE` / `file_offset < 0` / `fstat` 三条检查：
  <https://android.googlesource.com/platform/bionic/+/ca10ac6/linker/linker.cpp>
- `LineageOS/android_bionic @ cm-14.1 linker.cpp` — 同一函数里 `if (file_offset >= file_stat.st_size)` 与本文所引 `DL_ERR` 逐字一致：
  <https://github.com/LineageOS/android_bionic/blob/cm-14.1/linker/linker.cpp>
- `*file_offset = 0;` 出现在 `open_library()` 入口（"`*file_offset = 0;` … `if (!realpath_fd(fd, realpath))` … `printing warning: unable to get realpath for the library`"）：
  <https://android.googlesource.com/platform/bionic/+/8b14256/linker/linker.cpp>

### 2.2 两个数字分别由谁算出

| 数字 | 变量 | 产生者 | 备注 |
|---|---|---|---|
| 第一个 `0` | `file_offset` = `LoadTask::get_file_offset()` | **`open_library()` 入口无条件 `*file_offset = 0`**；只有三条路径会改写它：① `open_library_in_zipfile()` 用 `ZipEntry.offset`；② `do_dlopen()` 里 `ANDROID_DLEXT_USE_LIBRARY_FD_OFFSET` → `extinfo->library_fd_offset`；③ `open_library_in_zipfile` 命中后 `*file_offset = entry.offset` | 普通路径/绝对路径/`LD_LIBRARY_PATH` 搜索路径 **恒为 0** |
| 第二个 `0` | `file_stat.st_size` | **`TEMP_FAILURE_RETRY(fstat(task->get_fd(), &file_stat))`** | `fstat` 成功时才有意义；失败会走另一条 `unable to stat` 分支 |

> 因此 `0 >= 0` **不是**「offset 越界」的一种特例，而是「**文件长度本身是 0**」的判据。这是本次考证最关键的一步，它一次性排除了「zip 偏移算错」「对齐不对」「APK 解压长度记成 0」等所有猜想——那些都会让两个数字**不相等**。

### 2.3 哪次重构引入（推断）

三条检查（`is not page-aligned` / `is negative` / `>= file size`）**只对非 0 的 `file_offset` 才有意义**，所以它们与「从 APK 内直接 mmap 加载 .so」这条特性（`open_library_in_zipfile`，服务 `extractNativeLibs=false`，Android 6.0 起）**同批引入**。旁证：Android 7.1（`cm-14.1`）源码已含全部三条；Android 5.x 的 `linker.cpp` 尚无 zip 加载路径。
**推断**：引入者即该特性的作者（Dmitriy Ivanov 的 "load libraries from APK" 系列改动），此后 `load_library` 在 Android 10 被重构成 `LoadTask` 形式，**报错文本本身至今未变**（这正是能拿 2017 年的源码片段对照 2026 年 Android 14 报错的原因）。

---

## 三、`0 >= 0` 的所有可能来源（含前置条件表）

### 3.1 先钉死第二个数字：`st_size == 0` 才可能

| # | 让 `st_size == 0` 的可能 | 前置条件 | 本案判定 |
|---|---|---|---|
| a | **文件真的是 0 字节**（被 `O_TRUNC` 打开后写入未落地：`cat src > dst` 的 src 打不开 / 写入 ENOSPC / 写入中途被杀） | 有人对该 inode 做过 `>` 或 `dd` 之类写入 | ✅ **首席候选**（与「原位替换之后才出现」完全吻合） |
| b | **app 看到的对象 ≠ root shell 看到的对象**（mount namespace / overlayfs / KernelSU 模块把该路径分流到 0 字节上层副本） | app 与 `su` shell 的 mount ns 不同；overlay 的 upper 有 0 字节副本 | ⚠️ 备选。**但**同目录 `libunity.so` 正常 ⇒ 只可能是「单文件级」分流，概率低 |
| c | **fd 指向管道/匿名文件**（`fstat` 对 pipe 恒返回 `st_size = 0`） | 必须由调用方传入 fd：`ANDROID_DLEXT_USE_LIBRARY_FD` + 一个 `AssetManager` 压缩资产 fd（AOSP `Asset::getFileDescriptor()` 对压缩条目**就是建 pipe**） | ❌ `libmain.so` **不 import `android_dlopen_ext`**（见 §4.1），够不到这条路 |
| d | `fstat` 本身失败 | —— | ❌ 那会报 `unable to stat file for the library`，文本不同 |
| e | 被 `open(..., O_PATH)` 之类取出 | 走的是别的 open 封装 | ❌ 方向不符 |

### 3.2 `file_offset == 0` 的五条路径，逐条判死

| # | 路径 | `file_offset` 由谁算 | 要得 0 需满足 | 选中的前置条件 | 本案 |
|---|---|---|---|---|---|
| 1 | **直接/绝对路径** `dlopen("/data/app/…/libil2cpp.so")` → `open_library()`（内部走 `open_library_on_default_path` 或直接 `open`） | `*file_offset = 0`（入口置零） | **恒为 0** | 名字含 `/` | ✅ 本案第 1 次调用 |
| 2 | **裸 soname + `LD_LIBRARY_PATH` 搜索** `dlopen("libil2cpp.so")` → `open_library_on_ld_library_path()`，逐个 `<dir>/<name>` 试 | 同上，恒 0 | **恒为 0** | 名字不含 `/`；由 `nativeloader` 建的 classloader namespace 的 `ld_library_paths` 含 app 的 `nativeLibraryDir` | ✅ **本案报错实际来自这一次**（见 §4.3） |
| 3 | **zip 内加载** `open_library_in_zipfile()` | `ZipEntry.offset`（`FindEntry` 填） | 需 zip 条目起始偏移恰为 0（即条目就是文件第一个对象） | **名字必须含 `!/`**（`<apk>!/lib/arm64-v8a/libil2cpp.so`）；只有 `nativeloader` 在 `extractNativeLibs=false` 的 app 上、或 app 自己传这种路径时才会出现 | ❌ 报错名 `libil2cpp.so` 不含 `!`，直接排除 |
| 4 | **`ANDROID_DLEXT_USE_LIBRARY_FD`** | `extinfo->library_fd_offset`（未置 `…_FD_OFFSET` 时保持 0） | 恒 0 | 调用方用 `android_dlopen_ext()` 并自备 fd | ❌ 无 import，排除 |
| 5 | **`ANDROID_DLEXT_USE_ZIP_FILE`** | —— | —— | **该 flag 不存在** | ❌ 概念性排除，见下 |

#### ★ 关于 `ANDROID_DLEXT_USE_ZIP_FILE`：这个 flag 在 Android 上不存在

`android/dlext.h` 的 `android_dlextinfo.flags` 全集是：

```
ANDROID_DLEXT_RESERVED_ADDRESS      = 0x1
ANDROID_DLEXT_RESERVED_ADDRESS_HINT = 0x2
ANDROID_DLEXT_WRITE_RELRO           = 0x4
ANDROID_DLEXT_USE_RELRO             = 0x8
ANDROID_DLEXT_USE_LIBRARY_FD        = 0x10
ANDROID_DLEXT_USE_LIBRARY_FD_OFFSET = 0x20
ANDROID_DLEXT_FORCE_LOAD            = 0x40
ANDROID_DLEXT_USE_NAMESPACE         = 0x200
ANDROID_DLEXT_...RESERVED_ADDRESS…  = 0x800 等
```

出处：NDK `libdl` 参考文档枚举（`USE_LIBRARY_FD=0x10` / `USE_LIBRARY_FD_OFFSET=0x20` / `FORCE_LOAD=0x40` / `USE_NAMESPACE=0x200`）：
<https://developer.android.google.cn/ndk/reference/group/libdl>
以及 `dlext.h` 原文：
<https://gitorious.ti.com/cgit/android-sdk/platform-bionic/plain/libc/include/android/dlext.h>

**zip-direct 不是靠 flag 触发的，而是靠「名字里带 `!/`」这个字符串约定**触发 `open_library_in_zipfile()`。所以「`android_dlopen_ext` 的 `ANDROID_DLEXT_USE_ZIP_FILE` 路径」这条候选**在代码层面不成立**，应从排查树里删掉；真正存在的是 `USE_LIBRARY_FD`（+可选 `_FD_OFFSET`）和 `!/` 名字约定两条。

#### 关于 `namespace / nativeloader`「bug 132443820」兼容路径

那是 **Android 9 (P) 私有库访问限制**带来的 classloader-namespace 与 `DSO` 可见性变更（`isGreylist()` / `is_accessible()`），它的失败形态是：

```
dlopen failed: library "libc++_shared.so" not found: needed by …libPulseC.so in namespace clns-9
dlopen failed: library "…" is not accessible for namespace "clns-N"
```

**它从不产生 `file offset … >= file size`**——这是个**在 `open()` 成功之后**、对已打开 fd 做的完整性检查。灰名单/命名空间只会让 `open()` 前就失败。故与本错误正交，排除。

（旁证：nativeloader 的 `Load … using class loader ns clns-9 (caller=…/base.apk): <err>` 日志格式，见 <https://discourse.kitware.com/t/failing-to-load-pulsec-android-phone/1660/3> 与 <https://discuss.grapheneos.org/d/21495-dji-mimo-app-crash>，其中后者的 Qt 例子里 zip-direct 的路径长这样：`Load /data/app/~~…==/base.apk!/lib/arm64-v8a/libc++_shared.so using class loader ns clns-6` —— **带 `!/`**，再次印证 §3.2 第 3 行。）

---

## 四、Unity 加载链分析（真机 APK 静态分析）

对象：`work/ba/audit/ba-apk/lib/arm64-v8a/libmain.so`（18,608 B，sha256 `e2a12641542457e7…`，`.text` 仅 1,008 B，41 个符号，`AARCH64`）。

### 4.1 先回答「走哪条 API」

**`dynsym` 里只有 `dlopen` / `dlsym` / `dlerror` / `dlclose` / `snprintf` / `malloc` / `memcpy` / `free` / `__cxa_atexit` / `__cxa_finalize` / `__stack_chk_fail`。没有 `android_dlopen_ext`，没有 `AAssetManager_*`，没有 `open`/`mmap`。**

⇒ **不是 `System.loadLibrary`，不是 zip-fd，不是 `android_dlopen_ext`；就是最普通的 `dlopen()`。** 结论一句话：**Unity 2021.3 的 `loadNative` = 两次 `dlopen`（先全路径、后裸 soname）。**

### 4.2 完整链条（反编译，非推测）

```c
/* ── JNI_OnLoad @ libmain.so+0x96c (144 B) ───────────────────────── */
jint JNI_OnLoad(JavaVM* vm) {
    JNIEnv* env; (*vm)->GetEnv(vm, (void**)&env, 0);            /* vtable+0x20 */
    jclass c = (*env)->FindClass(env, "com/unity3d/player/NativeLoader");  /* +0x30 */
    if ((*env)->RegisterNatives(env, c, &g_methods_0x8000, 2) < 0) {  /* +0x6b8 */
        (*env)->FatalError(env, "com/unity3d/player/NativeLoader");
        return -1;
    }
    return 0x10006;                                             /* JNI_VERSION_1_6 */
}

/* ── NativeLoader.load(String path) @ +0x9fc (220 B) ─────────────── */
/* 注册的 2 个 native 方法 = load(String)Z 与 unload(String)Z；
   Java 侧 com.unity3d.player.UnityPlayer.loadNative 就是调 NativeLoader.load() */
jboolean Utils_LoadLibraries(JNIEnv* env, jclass, jstring jpath) {
    int   n     = (*env)->GetStringUTFLength(env, jpath);        /* +0x540 */
    char  *dir  = (*env)->GetStringUTFChars(env, jpath, NULL);   /* +0x548 */
    char  *copy = malloc(n + 1); memcpy(copy, dir, n + 1);
    (*env)->ReleaseStringUTFChars(env, jpath, dir);              /* +0x550 */

    load_one(env, copy, "libunity.so",   &g_unity);   /* ← 先 libunity  */
    load_one(env, copy, "libil2cpp.so", &g_il2cpp);   /* ← 后 libil2cpp */
    free(copy);
    return g_unity != 0;
}

/* ── load_one @ +0xbd4 (332 B) —— 崩溃点所在函数 ─────────────────── */
void load_one(JNIEnv* env, const char* dir, const char* soname, void** slot) {
    if (*slot != NULL) return;
    JavaVM* vm;
    if ((*env)->GetJavaVM(env, &vm) < 0) {                  /* JNIEnv vtable+0x6d8 */
        (*env)->FatalError(env, "Unable to retrieve Java VM");   /* +0xca8 */
        return;
    }
    char full[2048];
    snprintf(full, 0x7ff, "%s/%s", dir, soname);            /* ★ 唯一构造路径的地方 */
    void* h = dlopen(full, RTLD_LAZY);                      /* ★ 第 1 次：全路径 */
    if (h == NULL) h = dlopen(soname, RTLD_LAZY);           /* ★ 第 2 次：裸 soname */
    if (h == NULL) {
        char msg[1024];
        snprintf(msg, 0x400, "Unable to load library: %s [%s]", full, dlerror());
        (*env)->FatalError(env, msg);                       /* ★ 返回地址 = +0x0cbc */
        return;
    }
    void* sym = dlsym(h, "JNI_OnLoad");
    if (sym == NULL || ((jint(*)(JavaVM*,void*))sym)(vm, NULL) < 0x10007) {
        *slot = h;                                          /* 成功 */
        return;
    }
    (*env)->FatalError(env, "Unsupported VM version");      /* 同一处 +0x0cbc */
}
```

`.rodata` 逐字核对无误：`com/unity3d/player/NativeLoader`、`(Ljava/lang/String;)Z`、`libunity.so`、`libil2cpp.so`、`"%s/%s"`、`"Unable to load library: %s [%s]"`、`"Unable to retrieve Java VM"`、`"Unsupported VM version"`、`"JNI_OnLoad"`、`"JNI_OnUnload"`。

### 4.3 从 `libmain.so+0xcbc` 反推「哪一句失败」——可以精确到语句

`load_one` 的 CFG（Ghidra，14 基本块）里，`0xcbc` 落在基本块 `0xcb4–0xcc4` 内：

```
0xcb4: ldr  x8, [x8, #0x90]     ; x8 = (*env)->FatalError   (JNIEnv 函数表偏移 0x90)
0xcb8: blr  x8                  ; ★ 间接调用 FatalError
0xcbc: <返回地址>               ; ← 崩溃栈里的 libmain.so+0xcbc
```

这是**三个 `FatalError` 出口汇合后的唯一调用点**，其三个上游分别是：

| 上游块 | 消息 | 触发条件 |
|---|---|---|
| `0xca8` | `Unable to retrieve Java VM` | `GetJavaVM` 返回 < 0 |
| `0xc98` | `Unsupported VM version` | `dlsym("JNI_OnLoad")` 拿到、但返回 ≥ `0x10007` |
| `0xcf0` | **`Unable to load library: %s [%s]`** | **两次 `dlopen` 都返回 NULL** |

配合 Abort message 的正文是 `Unable to load library:`，可定位到 `0xcf0` 这一支，于是得到三条**确定性**结论：

1. **失败 = 两次 `dlopen` 都返回 NULL**（不是 `JNI_OnLoad` 失败，也不是 `dlsym` 找不到 `il2cpp_init`——后者根本不是 libmain 的活，是 libunity 的事）。
2. **报错的 `[%s]` 来自 `dlerror()`，而 `dlerror()` 只保留最后一次错误 ⇒ 报的是第 2 次 `dlopen("libil2cpp.so")` 的错误。** 第 1 次（全路径）的错误文本已被覆盖，**永久丢失**。
3. 报错里 Unity 打 `%s` = `full`（全路径 `/data/app/…/lib/arm64/libil2cpp.so`），linker 打 `\"%s\"` = `task->get_name()` = **dlopen 的入参**。现场日志里前者是**全路径**、后者是**裸名 `libil2cpp.so`** —— 这个不一致本身就是「错误来自第 2 次调用」的独立佐证，同时**排除**了 §3.2 第 3 行（`!/`）与任何「路径拼错」的猜想。

### 4.4 结构性判据：为什么能确定「只有那个文件坏了」

`Utils_LoadLibraries` 里 **`libunity.so` 与 `libil2cpp.so` 是同一次调用、同一个 `dir`、同一个 `snprintf` 模板**，且 `libunity.so` **排在前面**。现场报错的文件名是 `libil2cpp.so`，**说明 `libunity.so` 已经成功进去了**（否则第一次 `load_one` 就 FatalError，栈一样、消息里的名字会是 `libunity.so`）。

推论（重要）：

- `dir` 正确 ✅（否则 libunity 也失败）
- namespace / `ld_library_paths` 正确 ✅（libunity 就是在同一 ns 里找到的）
- SELinux 标签、目录权限、mount namespace ✅（libunity 从**同一目录**被 `open()` 成功了）
- `/data` 可读、非 ENOSPC-只读 ✅
- **⇒ 剩下的唯一变量就是 `libil2cpp.so` 这个文件本身，而 `fstat` 说它 0 字节。**

这条推理**不需要设备**就能排除「路径错/命名空间错/标签错/挂载错」四大类，并把 §3.1 的候选 (b)(c) 压到很低。

---

## 五、`extractNativeLibs=true` + `Defl:N` 会走 zip-direct 吗？

**不会。** 分三层说明：

1. **`extractNativeLibs=true` 时，`installd` 在安装阶段就把所有 `.so` 从 APK 解压落盘**到 `/data/app/~~<hash>/<pkg>-<hash>/lib/arm64/`，`ApplicationInfo.nativeLibraryDir` 就指向那里。APK 内条目是 `Stored` 还是 `Defl:N` **无所谓**——反正要解压。本机磁盘上 270,927,056 B 的文件就是这次解压的产物。
2. zip-direct（`open_library_in_zipfile`）**只服务 `extractNativeLibs=false` 的 app**，而且要求条目是 **`Stored` 且按页对齐**（否则无法 `mmap`）。这条路上 path 形如 `…/base.apk!/lib/arm64-v8a/libil2cpp.so`（**带 `!/`**）。
3. **本案的调用方根本够不到它**：`libmain.so` 只 import `dlopen`（§4.1），`dlopen` 的入参是全路径或裸 soname，**都不含 `!/`**。

### 5.1 若 `FindEntry` 失败，会给什么错？

**绝不是 `0 >= 0`。** `FindEntry` 失败给的是 `library "…!/…" not found` 系列。`linker.cpp` 里 zip 路径的完整错误分支（按出现顺序）：

| 位置 | 文本 | 触发 |
|---|---|---|
| `open_library_in_zipfile()` 入口 | `library name "%s" does not contain "!"` | 名字里没有 `!/` 分隔符 |
| `ZipArchiveCache::get_or_open()` | `couldn't open zip archive "%s": %s` | APK 打不开 / zip 头坏 |
| `ZipArchiveCache::find_entry()` | `couldn't find entry "%s" in "%s"` | **`FindEntry` 返回非 0（条目不存在 / CD 写坏 / CRC 不匹配）** |
| `find_library()` 全部候选耗尽 | `library "%s" not found` / `dlopen failed: library "%s" not found` | 所有搜索路径都没 open 成功 |
| **`load_library()`（open 成功之后）** | `unable to stat file for the library "%s": %s` | `fstat` 失败 |
| **同上** | **`file offset for the library "%s" >= file size: %" PRId64 " >= "% PRId64`** | **`fstat` 成功且 `st_size == 0`（或 offset ≥ size）** |

> `FindEntry` 填的是 `entry.offset`（→ `file_offset`）；**`entry.uncompressed_length` 在 linker 里完全没被用到**。所以「APK 里 uncompressed_length 记成 0」也**不会**产生 `0 >= 0`——loader 拿 APK 的 `st_size`（2.13 GB）跟 offset 比，只会是「offset 越界」而不是 `0 >= 0`。
>
> ⚠️ 顺带纠一个常见误区：**「把 APK 里该条目改成 `Stored` 再重新对齐」对本错误毫无意义**。那是 `extractNativeLibs=false` 才需要的动作；本案 `extractNativeLibs=true`，改了也白改（反而若真切成 `false`，`Defl:N` 条目才会真的加载失败）。

---

## 六、设备侧排查命令清单（可直接复制执行）

> 只依赖 root shell + `/proc` + `logcat`。**第一步是「冻结」，不是「抢拍」**——先把进程打停，再慢慢看，彻底绕开 0.3 秒窗口。

### 6.0 一次性取路径（后续命令都用这几个变量）

```sh
PKG=com.RoamingStar.BlueArchive
SUITE=$(pm path $PKG | head -1 | sed 's|/base.apk$||')
LIBDIR=$SUITE/lib/arm64
echo "SUITE=$SUITE"; echo "LIBDIR=$LIBDIR"
```

### 6.1 【最关键·5 秒出结论】app 视角下这个文件到底多大

```sh
su -c "
  PKG=com.RoamingStar.BlueArchive
  SUITE=\$(pm path \$PKG | head -1 | sed 's|/base.apk\$||')
  LIBDIR=\$SUITE/lib/arm64
  echo '--- 全目录 ---'
  ls -l \$LIBDIR/
  echo '--- 关键两个文件 ---'
  stat -c 'size=%s inode=%i blocks=%b mtime=%y %n' \$LIBDIR/libil2cpp.so \$LIBDIR/libunity.so
  echo '--- SELinux 标签 ---'
  ls -lZ \$LIBDIR/ | head -5
  echo '--- 剩余空间 ---'
  df -h /data
"
```

**判读**：`libil2cpp.so` 若 `size=0` → 根因落实（写入没落地），直接跳 §7 方案 A。
若 `size=270927056` → 进 6.2 对照命名空间。

### 6.2 【跨命名空间对照】app 看到的是不是同一个 inode

应用进程继承 **zygote 的 mount namespace**，所以直接借 zygote 的视角看，**不需要抓到目标进程**：

```sh
su -c '
Z=$(pidof zygote64); [ -z "$Z" ] && Z=$(pidof zygote); echo "zygote=$Z"
SUITE=$(pm path com.RoamingStar.BlueArchive | head -1 | sed "s|/base.apk$||")
LIBDIR=$SUITE/lib/arm64
echo "--- 当前 shell（可能被 KSU 模块挂载影响）---"
stat -c "size=%s inode=%i dev=%d %n" $LIBDIR/libil2cpp.so
echo "--- zygote 视角（= app 视角）---"
nsenter -t $Z -m -- stat -c "size=%s inode=%i dev=%d %n" $LIBDIR/libil2cpp.so
echo "--- 两份 mountinfo 差异（只看 /data 相关）---"
diff <(nsenter -t $Z -m -- cat /proc/1/mountinfo) <(cat /proc/1/mountinfo) | head -30
'
```

**判读**：两行 `size/inode` 若不同 → 是 §3.1(b) 的挂载/overlay 分流；若完全相同且都是 270,927,056 → §3.1(a) 与 (b) 都不成立，进 6.4 看是不是第一次 `dlopen` 因别的原因失败、第二次命中了别处的 0 字节同名文件。

### 6.3 【冻结取证】把进程停住，再慢慢解剖

```sh
su -c '
PKG=com.RoamingStar.BlueArchive
logcat -c
( while :; do
    P=$(pidof $PKG)
    if [ -n "$P" ]; then
      kill -STOP $P 2>/dev/null
      echo "FROZEN pid=$P"
      cat /proc/$P/maps            > /data/local/tmp/ba_maps.txt    2>/dev/null
      ls -l /proc/$P/fd            > /data/local/tmp/ba_fd.txt      2>/dev/null
      cat /proc/$P/mountinfo       > /data/local/tmp/ba_mountinfo.txt 2>/dev/null
      grep -i il2cpp /proc/$P/maps >> /data/local/tmp/ba_maps.txt
      ls -l /proc/$P/task/ | head
      break
    fi
  done ) &
monkey -p $PKG -c android.intent.category.LAUNCHER 1
wait
'
echo "=== maps 里跟 so 相关的行 ==="
su -c 'grep -E "\.so" /data/local/tmp/ba_maps.txt | grep -E "libil2cpp|libunity|libmain|libtprt"'
echo "=== fd 里跟 apk/so 相关的 ==="
su -c 'grep -E "\.so|\.apk" /data/local/tmp/ba_fd.txt'
```

> `kill -STOP` 之后进程不再前进（它本来 0.3 s 后就 abort），`/proc/<pid>/` 全程可读；看完用 `kill -CONT <pid>` 放开、`kill -9` 清掉。
> **预期**：`libmain.so`、`libunity.so` 在 maps 里、**`libil2cpp.so` 不在**（因为它压根没 map 成功）——这正好反向印证 §4.4。

### 6.4 【读 nativeloader 行】判定「谁在加载、走没走 zip」

```sh
su -c 'logcat -b all -d -v threadtime' | grep -E \
  'nativeloader|linker|dlopen|UnityPlayer|libil2cpp|file offset for the library' | tail -60
```

判读表（这是本次最省事的「路径判定器」）：

| 现场看到 | 含义 |
|---|---|
| `nativeloader: Load …/lib/arm64/libmain.so using class loader ns clns-N (caller=…/base.apk): ok` | `System.loadLibrary("main")` 成功，ns = `clns-N` |
| `nativeloader: Load …/lib/arm64/libil2cpp.so using class loader ns …: ok/失败` | 有人走了 **Java 层**（`System.loadLibrary`） |
| `nativeloader: Load …/base.apk**!/**lib/arm64-v8a/libil2cpp.so …` | 走了 **zip-direct**（`extractNativeLibs=false` 形态）→ 与本案不符 |
| **完全没有 `libil2cpp` 的 nativeloader 行**，只有 `JNI FatalError called:` / `UnityPlayer` | **说明是 `libmain.so` 里的原生 `dlopen()` 直接调的**——与 §4 的静态分析一致，**这是本案的预期结果** |
| `libunity.so` 有 `: ok` 而 `libil2cpp.so` 无任何行 | 再次印证「只有那一个文件有问题」 |

### 6.5 【辅助】把「写出去了但内容坏」与「根本没写进去」区分开

```sh
su -c '
SUITE=$(pm path com.RoamingStar.BlueArchive | head -1 | sed "s|/base.apk$||")
sha256sum $SUITE/lib/arm64/libil2cpp.so \
          /data/local/tmp/libil2cpp.orig_001113.so 2>/dev/null
ls -l /data/local/tmp/*.so /sdcard/ba_slot_backup.bin 2>/dev/null
dmesg | grep -iE "overlay|no space|EXT4-fs error|F2FS" | tail -20
'
```

**判读**：`sha256sum` 要跟 `report/08-手机接管与真因.md` 里那张表对得上（原厂 `5ac1cbe0…` / patched `a473ba16…` / 改 4 字节后 `0edaedad…`）。对不上且 `size=270927056` ⇒ 内容被改坏（但**不会**报 `0 >= 0`，会报 ELF 解析错），说明还叠加了第二个问题。

---

## 七、修复方案排序（前提：不重装、不改 UID、11 GB 外部资源不迁移）

> **先纠正一个前提错误**：**UID 不跟「装」绑定，跟「包名 + 签名 + 是否走过 uninstall」绑定。`pm install -r`（reinstall、保留数据）对已存在的包是**同一个 UID**、数据目录与 `/sdcard/Android/data` 归属**全部不变**。会换 UID 的只有 `pm uninstall` 之后再 `pm install`（或在 `pm install -r` 失败后被迫清装）。**所以「不能重装」实际只是「不能 uninstall」，`-r` 是可用武器。**（推断/经验规则，可现场用 `dumpsys package $PKG | grep -E "userId|codePath"` 前后对比自证。）

| 排序 | 方案 | 前提 | 风险 | 判定成功的方法 |
|---|---|---|---|---|
| **A（首选）** | **原子恢复那个 so**：同目录写临时文件 → 校验 sha256 → `mv` 覆盖 → `restorecon`。**不要再用 `cat src > dst`** | 有 270,927,056 B 的可信备份（`/data/local/tmp/libil2cpp.orig_001113.so` 或 `work/ba/bapatch/libil2cpp.bin`） | 低。`mv` 是 `rename(2)`，**全程无 0 字节窗口**；变更 inode 需补 `restorecon`。若备份本身是坏的那份，等于没修 | 6.1 里 `size=270927056` + `sha256sum` 命中期望值 + app 能过 `dlopen` 进到 `DT_INIT` |
| **B** | **`pm install -r <base.apk>`** 强制 `installd` 重新解压整个 `lib/arm64/`（并生成**新的** `~~hash==` 目录，`nativeLibraryDir` 随之刷新） | ① 有与在装包**同签名**的 APK；② `/data` 至少再腾出 ~2.5 GB；③ 能接受 app 被杀 | 中。签名不一致 → `INSTALL_FAILED_UPDATE_INCOMPATIBLE`；空间不足会**重蹈 0 字节覆辙**；UID/数据不变（见上方纠正） | 安装后 `pm path` 的 `SUITE` 变了，且新 `lib/arm64/libil2cpp.so` 大小正确、能启动 |
| **C** | `restorecon -R $LIBDIR` | 仅当 6.1 的 `ls -lZ` 显示标签异常（`u:object_r:apk_data_file:s0` 之外） | 低 | 标签变回 `apk_data_file` 且能启动。⚠️ 但 §4.4 已表明标签大概率没问题，**预期无效** |
| **D** | 把 `libil2cpp.so` 从 APK 里**重新单独解压**再放回去（`unzip -o base.apk lib/arm64-v8a/libil2cpp.so`），避开可疑备份 | 能读 APK（2.13 GB，`funzip`/`unzip` 在 toybox 里可能没有，需 busybox） | 中。解压需要 ~271 MB 临时空间 | 同 A |
| **E** | 改 APK 内条目为 `Stored` + 重新对齐 + 重打包 | —— | **无效**。见 §5：`extractNativeLibs=true` 下 `Defl:N` 完全正常，zip-direct 根本没走。改了纯属浪费 2 小时 + 冒签名风险 | —— |
| **F** | `cmd package compile -m speed -f $PKG` / `rm -rf $SUITE/oat` / 删 `vdex` | —— | **无效**。`libil2cpp.so` 是 native so，**不进 oat/vdex**。这些只影响 dex | —— |
| **G** | `ldconfig` / 「刷新 linker 缓存」 | —— | **不存在该机制**。Android 的 `ld.config.txt` 是只读系统配置，无运行时 so 缓存需要刷 | —— |
| **H** | `pm clear $PKG` | —— | **有害且无效**。清数据不动 `lib/`，白丢 11 GB 映射的游戏数据 | —— |
| **I** | 切 `extractNativeLibs=false` 重打包重装 | —— | **反向恶化**。`Defl:N` 条目在 zip-direct 下**真的**加载不了；且必须 uninstall → 换 UID → 11 GB 要 chown，正是要避免的 | —— |

### 若 §6.2 显示两个命名空间的 `size/inode` 不一致（即走到 §3.1(b)）

上面 A/B 都不解决。要先定位是哪个 KernelSU 模块在 `overlay`/bind-mount 该路径：

```sh
su -c 'cat /proc/self/mountinfo | grep -E "/data/app|overlay"; ls -l /data/adb/modules/'
```

把冲突模块 `touch /data/adb/modules/<id>/disable` 后重启（或 `ksud module disable <id>`），再用 6.2 复核 inode 是否一致，然后回到 A。

---

## 八、留给下一轮的两个待办（本会话能力边界）

1. **AOSP android-14 分支的逐字源码未取到**（`web_fetch`/`research` 的抓取后端返回 404）。上述 `load_library` 片段来自 2017 年（cm-14.1）与 `ca10ac6` 两个镜像，**报错文本与分支逻辑一致**，但 Android 14 的具体行号、以及是否已把该检查挪进 `ElfReader::Read()`，需在有网络抓取能力时补一次核对。
2. **`libmain_patched.so`（`work/ba/bapatch/libmain_patched.so`，sha256 `B1CE0142…`）相对原厂只改了 8 字节**：`0x59D` 处 `liblog.so` → `libdg.so`（DT_NEEDED 改名注入），另 2 字节在 `0x3F38/0x3F40`。**现场 logcat 里 `libmain.so` 能正常加载，说明设备上装的是原厂那份**（否则会先报 `libdg.so not found`）。若后续要复现/回滚，注意别把这版当成"原厂"。
