# Config 持久化修复记录（P1-11 / P1-12 + save/load 加固）

- 负责人：config-fixer（第 1 层项目经理）
- 日期：2026-11-11
- 基线：`audit/AzusaBA-bug-report.md` 的 P1-11、P1-12
- 备份（未改动）：`audit/orig_backup/jni/Config.cpp`（233 行，改造前原件）

## 0. 一句话结论

`Game/Config.cpp` 已按报告要求重写读取/校验/落盘路径：**读取不再静默截断**、**数值不再回绕**、**二进制分支必须先验 9 字节 magic**、**任何「不是我们的文件」只改名保留现场而不再 `unlink`**、**保存失败一律打 logcat**。交叉编译 `-fsyntax-only` 干净通过（EXIT=0），并且用宿主机可执行的差分测试证明新旧行为差异（新代码 29/29 全过，旧代码在 9 项上失败）。

## 1. 改动文件

| 文件 | 改动 | 行数变化 |
|---|---|---|
| `AzusaBA/app/src/main/jni/Game/Config.cpp` | 主体重写 | 233 → 429 |
| `AzusaBA/app/src/main/jni/Game/Config.h` | 仅在 `save_config` / `load_config` 声明处补 5 行中文说明（结构体、`kCfgVersion = 9` 未动） | 69 → 74 |
| `AzusaBA/docs/CHANGES.md` | 末尾追加「## 七、修复记录（bug 报告 P0/P1）」+「### 七.1 Config 持久化（P1-11 / P1-12）」，**未删改任何已有内容**（原 186 行逐行保持不变，`sed -n '185,187p'` 可复核旧尾部仍在原位） | 186 → 205（+19） |
| `audit/cfgtest/`（新增，仅 3 个小文件） | 宿主机差分测试用的 `stub/Includes.h`、`stub/android/log.h`、`test_cfg.cpp`，便于复现 | — |

未改动：`main.cpp`、任何 Java、任何 ImGui backend、`key=value` 字段名、`kCfgVersion`（仍为 9）。

## 2. 逐条修复

### P1-11-a 读取固定 `char data[4096]`（原 `Game/Config.cpp:166-170`）

- 原问题：一次 `read(fd, data, 4095)` 后直接解析，超过 4095 字节的尾部被静默丢弃；下一次 `save_config` 用这份被截断的内存落盘，被丢弃字段被永久覆盖。
- 新行为：
  - `fstat` 取 `st_size`；`st_size <= 0`（空文件/取不到大小）→ 隔离为 `.bad`，返回 -1。
  - 文本路径上限 `kCfgMaxTextSize = 64KB`，超限按「不是我们的文件」隔离为 `.bad`。
  - 上限内 `std::vector<char> buf(size + 1)` 堆分配，`CfgReadExact()`（`pread` 循环、处理 `EINTR`）按实际大小**读满**；提前 EOF/短读 → `return -1`，绝不拿半截数据解析。
  - 结尾仍补 `'\0'`，`strtok_r` 解析逻辑与字段名完全不变（`strstr(data, kCfgMagic)` 校验保留，因此带 BOM/前导空白的老文本仍能认出来）。

### P1-11-b `CfgToI` 不查 `errno`（原 `Game/Config.cpp:60-65`）

- 原问题：`strtoll` 溢出时返回 `LLONG_MAX/MIN` 并置 `ERANGE`，但代码只看 `*end == 0`，于是 `characterId=99999999999999999999` 会被当成 `LLONG_MAX` 再被 `CfgClamp` 钳到上限；bool 字段的 `iv != 0` 同样会被回绕值误判。
- 新行为：`errno = 0` 后 `strtoll`；`errno == ERANGE` 直接返回 `def`；解析不完整仍返回 `def`。

### P1-12 二进制分支靠 `st_size == sizeof(sConfig)` 猜格式（原 `Game/Config.cpp:152-164`）

- 原问题：结构体缩小、或某个纯文本配置恰好等长时被误判成二进制；读失败后 **`unlink(filename)`** 把用户配置静默删除。
- 新行为：
  - 先 `pread` 头部 **9 字节**，只有 `memcmp(hdr, "AZUSABIN\n", 9) == 0` 才进二进制分支，并要求 `st_size == 9 + sizeof(sConfig)`、`pread` 读满、`version == kCfgVersion`。
  - 二进制分支里版本不符 → 改名 `<path>.v%d.bak`，返回 -2；尺寸/短读异常 → 隔离为 `.bad`。
  - **旧的裸结构体分支已删除**：v9 之前没有 magic 的旧文件现在走文本分支 → 认不出 `kCfgMagic` → 改名 `<path>.bad` 回默认值，**不再静默 unlink**（代码注释已写明这一取舍）。

### 额外 1：`save_config()` 不再静默失败（原 `Game/Config.cpp:78-141`）

- `open(tmp, O_WRONLY|O_CREAT|O_TRUNC|O_CLOEXEC, 0600)`：加 `O_CLOEXEC`（root 注入模式会 `fork/exec`，不让配置 fd 泄漏进子进程）。
- `.tmp` 路径拼接判长度（`snprintf` 返回值 `>= sizeof` → 失败），避免写到被截断的错误路径。
- `snprintf` 返回 `n <= 0 || (size_t)n >= sizeof(buf)` → **视为失败**（关 fd、删 `.tmp`、`return -1`），不再把截断内容写盘（与 P1-11 同一类丢字段问题）。
- `CfgWriteAll` 处理 `EINTR`；`write` / `fsync` / `close` / `rename` 任一失败都 `CfgWarn(...)` 打 logcat（**tag `AzusaBA-cfg`**，`adb logcat -s AzusaBA-cfg` 可单看）并返回 -1。
- `rename` 成功后 `CfgFsyncParent()`：`open(dirname, O_RDONLY|O_DIRECTORY|O_CLOEXEC)` + `fsync`，失败一律忽略（Android 上 `/data` 的目录 `fsync` 常返回 `EINVAL`）。

### 额外 2：`load_config()` 不再 `unlink`（原 `Game/Config.cpp:172-176`）

- 无 magic / 空文件 / 超 64KB / 二进制截断 → `CfgQuarantine()` 改名 `<path>.bad` 保留现场，然后回默认值返回 -1；改名失败只打日志、文件原样保留（不删）。
- 版本不符 → `CfgRenameVersioned()` 改名 `<path>.v%d.bak`，返回 -2（行为与改造前一致，但补了路径长度判断与日志）。
- 副作用说明：`rename()` 会覆盖同名旧 `.bad`，即只保留**最近一次**现场（代码注释已标明这是有意取舍）。

## 3. 编译自检

工作区根：`/data/user/0/com.ai.assistance.operit/files/workspace/9dc0fd0c-7cad-4366-8d0b-bad7165d8587`，`SRC=$WS/AzusaBA/app/src/main/jni`，proot Ubuntu（aarch64）。

### 3.1 任务指定命令（NDK 自带 clang++）——本环境不可执行

```sh
NDK=/root/ndk/android-ndk-r27c; SYS=$NDK/toolchains/llvm/prebuilt/linux-x86_64/sysroot
$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/clang++ --target=aarch64-linux-android26 --sysroot=$SYS \
  -stdlib=libc++ -isystem $SYS/usr/include/c++/v1 -std=c++17 -fno-rtti -fno-exceptions \
  -I$SRC -I$SRC/il2cppApi -I$SRC/Game -I$SRC/Tools -I$SRC/ImGui -I$SRC/ImGui/backends -I$SRC/libs \
  -fsyntax-only $SRC/Game/Config.cpp
```

实际输出：

```
Illegal instruction
EXIT=132
```

原因：`uname -m` = `aarch64`，而 NDK r27 prebuilt 是 **linux-x86_64** 二进制；本 proot 无可用 x86_64 运行时，连 `clang --version` 都是 `Illegal instruction`（`NDKCLANG_EXIT=132`）。这是**环境限制，不是代码问题**。

### 3.2 等价替代（同 target / 同 sysroot / 同 libc++ 头文件，编译器本体换成宿主原生的 clang 18）——EXIT=0

```sh
clang++ --target=aarch64-linux-android26 --sysroot=$SYS -stdlib=libc++ \
  -isystem $SYS/usr/include/c++/v1 -std=c++17 -fno-rtti -fno-exceptions \
  -I$SRC -I$SRC/il2cppApi -I$SRC/Game -I$SRC/Tools -I$SRC/ImGui -I$SRC/ImGui/backends -I$SRC/libs \
  -fsyntax-only $SRC/Game/Config.cpp
```

```
EXIT=0
```

### 3.3 叠加 `Android.mk` 里的真实告警旗标（`-Wall -Wextra -Wno-*` + section/visibility）——EXIT=0 且零告警

```sh
clang++ --target=aarch64-linux-android26 --sysroot=$SYS -stdlib=libc++ -isystem $SYS/usr/include/c++/v1 \
  -std=c++17 -fno-rtti -fno-exceptions -fvisibility=hidden -fvisibility-inlines-hidden \
  -ffunction-sections -fdata-sections -Wall -Wextra -Wno-unused-parameter \
  -Wno-missing-field-initializers -Wno-sign-compare -Wno-c++11-narrowing -Wno-unused-variable -Wno-unused-function \
  -I$SRC -I$SRC/il2cppApi -I$SRC/Game -I$SRC/Tools -I$SRC/ImGui -I$SRC/ImGui/backends -I$SRC/libs \
  -fsyntax-only $SRC/Game/Config.cpp
```

```
EXIT=0
```

未做的更强验证（本机无法完成，需 lead/设备侧）：`ndk-build` 出 `.so`（`Android.mk` 的 `LOCAL_SRC_FILES` 已含 `Game/Config.cpp`，无需改构建脚本）、真机回归保存/热重载。

## 4. 运行期差分验证（宿主机可执行，非设备实测）

`Config.cpp` 只依赖 `Includes.h`（jni/ImGui/GLES 全家桶）与 `<android/log.h>`，为了在 proot 里直接跑起来，`audit/cfgtest/` 提供了两个 stub（`Includes.h` 只留标准头、`android/log.h` 把 `__android_log_print` 打到 stderr）+ 一个测试 `main`。被测源文件是**真实**的 `Game/Config.cpp`（不是抄一份）。

```sh
WS=/data/user/0/com.ai.assistance.operit/files/workspace/9dc0fd0c-7cad-4366-8d0b-bad7165d8587
SRC=$WS/AzusaBA/app/src/main/jni; WT=$WS/audit/cfgtest; mkdir -p /tmp/cfgtest
# 新代码
clang++ -std=c++17 -O1 -I$WT/stub -I$SRC/Game $WT/test_cfg.cpp $SRC/Game/Config.cpp -o /tmp/cfgtest/cfgtest
/tmp/cfgtest/cfgtest; echo "RUN_EXIT=$?"
# 旧代码（同一份测试，对照基线）
clang++ -std=c++17 -O1 -I$WT/stub -I$SRC/Game $WT/test_cfg.cpp $WS/audit/orig_backup/jni/Config.cpp -o /tmp/cfgtest/cfgtest_orig
/tmp/cfgtest/cfgtest_orig; echo "RUN_EXIT=$?"
```

### 4.1 新代码：29 项 CHECK 全过

```
ok   61 [save_config(kP) == 0]
ok   63 [txt.find("# AzusaBA-config") != std::string::npos]
ok   64 [txt.find("version=9") != std::string::npos]
ok   65 [!Exists(kTmp)]
ok   72 [save_config(kP) == 0]
ok   74 [Config.localLevel.level == 90]
ok   75 [load_config(kP) == 0]
ok   76 [Config.memoryLobby.characterId == 12345]
ok   77 [Config.battle.damageMultiplier == 42]
ok   78 [Config.localLevel.level == 77]
ok   79 [Config.localLevel.enable == true]
ok   86 [big.size() > 4096]
ok   89 [load_config(kP) == 0]
ok   90 [Config.localLevel.level == 55]
ok   91 [Config.localLevel.enable == true]
[AzusaBA-cfg] load: /tmp/cfgtest/t.ini: no AzusaBA-config magic -> renamed to /tmp/cfgtest/t.ini.bad
ok   97 [load_config(kP) == -1]
ok   98 [!Exists(kP)]
ok   99 [Exists(kBad)]
[AzusaBA-cfg] load: /tmp/cfgtest/t.ini: version 5 != 9 -> renamed to /tmp/cfgtest/t.ini.v5.bak
ok  105 [load_config(kP) == -2]
ok  106 [!Exists(kP)]
ok  107 [Exists(kV5)]
ok  108 [Config.localLevel.level == 90]
ok  113 [load_config(kP) == 0]
ok  114 [Config.memoryLobby.characterId == 0]
[AzusaBA-cfg] load: /tmp/cfgtest/t.ini: no AzusaBA-config magic -> renamed to /tmp/cfgtest/t.ini.bad
ok  123 [load_config(kP) == -1]
ok  124 [!Exists(kP)]
ok  125 [Exists(kBad)]
ok  139 [load_config(kP) == 0]
ok  140 [Config.localLevel.level == 66]
RESULT: ALL CHECKS PASSED
RUN_EXIT=0
```

### 4.2 旧代码（`audit/orig_backup/jni/Config.cpp`）：9 项失败，正好对应 P1-11/P1-12

```
FAIL 90 [Config.localLevel.level == 55]        ← P1-11：4KB 之后的字段被截断丢失
FAIL 91 [Config.localLevel.enable == true]     ← 同上
FAIL 99 [Exists(kBad)]                         ← P1-12：无 magic 文件被 unlink，没留 .bad
FAIL 114 [Config.memoryLobby.characterId == 0] ← P1-11：ERANGE 回绕成 9999999999
FAIL 123 [load_config(kP) == -1]               ← P1-12：恰好 sizeof(sConfig) 的裸结构体被误判成二进制（返回 0）
FAIL 124 [!Exists(kP)]                         ← 被“接受”后原文件被吃掉
FAIL 125 [Exists(kBad)]
FAIL 139 [load_config(kP) == 0]                ← 9+sizeof 的带 magic 文件旧代码不认（只认恰好 sizeof）
FAIL 140 [Config.localLevel.level == 66]
RESULT: 9 CHECK(S) FAILED
RUN_EXIT=1
```

结论：测试对缺陷是有区分度的（同一份测试、同一份字段），不是“写完自证通过”。

## 5. 风险与注意事项（给 lead / 后续整合）

1. **`fsync` 失败现在会让 `save_config` 返回 -1**。`main.cpp` 的自动保存是「失败就置 `g_cfgDirty` 下次再试（800ms 后）」，所以磁盘满/只读时会变成每 800ms 打一条 `AzusaBA-cfg` 警告并重试。这是有意为之（不假装保存成功），但如果觉得日志吵，可改成「首次失败打一次 + 退避」。
2. **P1-1 未解决（不在本次范围）**：`save_config` 仍是被 GL 渲染线程每 800ms 调用，`fsync` 仍会阻塞整帧；本次只是把 `fsync` 结果纳入成败判断，没有移出渲染线程。
3. **`.bad` 会被同名覆盖**：只保留最近一次现场。若要保留历史，可改成 `<path>.bad.<时间戳>`（本次按任务口径固定 `.bad`）。
4. **64KB 上限是硬失败**：真实配置 < 1KB，误伤概率极低；但若将来字段暴增到 64KB 以上，会表现为「配置回默认 + 生成 `.bad`」，需要同步抬 `kCfgMaxTextSize`（注释已标）。
5. **二进制分支只认带 magic 且长度精确的旧文件**：仓库内没有任何地方写二进制格式，磁盘上实际只会是文本；这条分支现在是「验过 magic 才走」的安全兜底。
6. 未在设备上实测（按用户协作约定：构建方只做只读取证/编译交付，真机测试由用户本人进行）。
