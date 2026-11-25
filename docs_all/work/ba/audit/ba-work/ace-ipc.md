# ACE（Anti-Cheat Expert）三服务 IPC + libtprt 取证

> 取证：APK 静态（jadx 反编译 + 手写 DEX method_ids/invoke 扫描 + ELF dynsym/字符串/原始字节比对）。未运行游戏、未联网、未解包到第三方目录。
> 证据强度标注：**[确证]** = 静态可直接复核；**[推断]** = 由导入面/邻证推出，需设备侧实验。

## 1. 三服务 IPC 面（`jadx/resources/AndroidManifest.xml:197-223`）

| 组件 | 进程 | exported | intent-filter action | Java 入口 | native 落点 |
|---|---|---|---|---|---|
| `com.ace.gshell.GP7Worker` | `:GP7Worker` | true | `com.ace.gshell.GP7Worker` | `onStartCommand` → `getStringExtra("ioctl")` | `AceApplication.gp7ioctl(String)`；`onDestroy` 还补一次 `gp7ioctl("stop")` |
| `com.ace.gshell.GP6Service` | `:GP6Service` | true | `com.ace.gshell.GP6Service` | 同上 | `AceApplication.gp6ioctl(String)` |
| `com.ace.gshell.GP7Service` | `:GP7Service` | true | `com.ace.gshell.GP7Service` | 同上 | `AceApplication.gp7ioctl(String)` |

- **action 名 = 服务类全名**（同一字符串两用）；三个 `onBind` 全部 `return null` → **不是 Binder IPC**，而是 `startService` + 自定义 `ioctl` 载荷 [确证，GP6Service.java:38-40 / GP7Service.java:39-41 / GP7Worker.java:39-41]
- 载荷约定：`Intent` extra **`ioctl`（String）原样丢给 native**，Java 层不解析 → 命令语义全在 `libtprt.so` [确证，GP6Service.java:18-20]
- Java 层**没有任何调用点**：`com/ace/gshell` 仅 4 个文件且互不引用；classes2.dex 内 `com/ace/gshell/GP6Service` 字面量仅 1 处（类描述符）→ 拉起者只能是 native 侧 [推断]
- 主进程另有 Application 级入口：`attachBaseContext → attachBaseContextShell → initialize(pkg, filesDir, nativeLibDir, sourceDir, splits)`
  - **修正旧结论**：`initialize(...) != 0` 确实 `throw`，但被外层空 `catch` 吞掉（AceApplication.java:62-66）→ **不会崩进程**，只是 ACE 处于半初始化。这意味着"hook initialize 关 ACE"不崩 ≠ 安全，不要据此放松。
- 六个 native 方法：`gp6ioctl/gp7ioctl/ioctl(int,String)/handleLoad(Object,int)/handleLoad(byte[],int,int)/handleLoadV22`

## 2. libtprt.so 特征串命中表（1,692,296 B，md5 `19d564494ef4eed5b1b655dc9554c3bf`）

| 关键词 | 命中 | 说明 |
|---|---|---|
| `ptrace` | 1 | **只在 `.dynsym` UNDEF**（`ptrace@LIBC`），无字面串 |
| `TracerPid` / `/proc/self/maps` / `/proc/%d/maps` / `/proc/self/status` / `/proc/self/task` / `/proc/self/mem` | **0 / 0 / 0 / 0 / 0 / 0** | 见下"为什么 0 不等于没有" |
| `memfd` / `inotify` / `dl_iterate_phdr` | 0 / 0 / 0 | — |
| `dlopen` / `dlclose` / `dlsym` / `dladdr` | 1 / 1 / 1 / 1 | 均仅 `.dynsym` UNDEF（**`dladdr` = 地址反查所属 so**） |
| `libil2cpp` / `libunity.so` | 0 / 0 | 无模块名字面量 |
| `Xposed` / `frida` / `magisk` / `AnoGs` | 0 / 0 / 0 / 0 | — |
| `a64.dat` / `a64.sig` | 4 / 4 | ACE 自身装载体 |
| 可打印率（每 1 MB） | **0.31 / 0.29** | `.rodata` 加密/VM：**"0 命中" ≠ "无检测"** |

**为什么 0 不等于没有** [确证]：`__ENABLE_OBJ_VM__`、`.text.shellcode_%s`、`shell_cast1/2`、版本串 `2.5.4.3/6/7/8/10/11`、`4.9.31.51305_cn`、`12479018` → 这是带 VM 的 ACE 壳，字符串不可静态还原。
**导入面自证能力** [确证]：`ptrace + syscall + prctl + mprotect/madvise + fork/execv/waitpid + socket/connect/bind/listen/accept + opendir/readdir/closedir/readlink + sscanf/strcasestr/access/unlink/rename/fstatat`，另有字符串 `127.0.0.1`、`%s.tmp`、`error 0..15`、`XTask_%s_%s`、`DLS_%d_%d`、`tsb_cnt/tsc_cnt` → 具备：自调试/反调试、`/proc` 与目录遍历、解壳落盘（`%s.tmp`+`rename`）、本地 socket 通道。

## 3. 有没有 libil2cpp 完整性校验？

- **无直接证据**：libtprt 无 `libil2cpp` 字面量；且 libtprt 内 5 个 32-hex 常量（`c94b211b…` / `743e07b0…` / `740be822…` / `28435730…` / `36bc2fdb…`）与本包**全部 26 个 so/dex 的 md5 都不等**（已逐个比过）[确证]
- **完整性设施确实存在，但对象是 ACE 自己的装载体**：`assets/__tpinfo.tp`、`__tpinfo.tsc` + `__tpinfo.tsc.sig`、`__tpinfo.tsd` + `__tpinfo.tsd.sig`、`__tpcfinfo.tsa`、`__tpsinfo.t.p.sin`（7 个文件）+ libtprt 内 `a64.dat`/`a64.sig` [确证]
- **反证（旧 kw-hits 结论要改）**：`libunity.so` 的 `signature=24 / ace_=25`、`libil2cpp.so` 的 `signature=2 / ace_=3` **全是假阳性** —— 实为 `space_Injected`、`FaceIndex`、`mono_method_signature`、`LoadFontFace_` 等子串，**不代表 APK/so 签名校验** [确证]
- 结论：**未发现 libil2cpp.so 的 hash/CRC pin**（静态弱否定：只覆盖明文常量与导入面）；ACE 的校验焦点是装载体与签名配置，不是 IL2CPP 代码段

## 4. 有没有扫已加载 so？

- 导入面支持：`dlopen/dlclose/dlsym/**dladdr**`（dladdr 正是"按地址判断属于哪个已加载模块"）+ `opendir/readdir/closedir/readlink/sscanf` [确证]
- 但没有 `/proc/self/maps` 明文串、没有 `dl_iterate_phdr` → 静态**无法证明**它遍历 maps [确证]
- 同包另一 SDK `libmsaoaidsec.so` 命中 `ptrace=1 / /proc/self/maps=1 / /proc/self/fd=2 / LD_PRELOAD=1 / LD_LIBRARY_PATH=1`（`out/kw-hits.tsv`）→ 说明"读 maps"能力在这一类 SDK 里是常态 [确证]
- 结论：**"libtprt 会扫已加载 so" = 推断（中高）**；要证实只能在测试机 hook `dladdr/readdir` 计数或观测 `maps` 访问，不在本报告范围内

## 5. 待实测（不改上面任何结论）

1. 三服务由谁拉起：测试机 `dumpsys activity services com.RoamingStar.BlueArchive | grep -i "GP[67]"`
2. maps 扫描证实：测试机对 `libtprt` 的 `dladdr/readdir/sscanf` 计数
3. `__tpinfo.tsd` 内容：需原始 APK（当前工作区只剩 slim.apk / dexonly.apk，7 个 `__tp*` 资源未落盘）
4. 模块侧对照：我们 `libNeko.so` 在 maps 的路径见 `audit/anti-detection.md` 第 1 档第 1 条