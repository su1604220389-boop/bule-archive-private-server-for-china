# 反检测评估：Blue Archive 国服 × AzusaBA（LSPosed 模块）

> 取证口径：全部为 **APK / 模块源码静态取证**，未运行游戏、未联网、未在真机抓包。
> 证据强度：**[确证]** 静态可直接复核；**[推断]** 由导入面/邻证推出，需测试机实验；**[未验证]** 明确未取证。
> 配套细节：`audit/ba-work/ace-ipc.md`（ACE 三服务 + libtprt）、`audit/ba-work/shumei-xposed.md`（数美 4 方法调用方）。

## 0. 三件必须先接受的事实

1. **ACE 关不掉，也不该去关。** `initialize()` 失败时异常被空 catch 吞掉（`AceApplication.java:62-66`）→ 不崩、但 ACE 半初始化；`:GP6Service/:GP7Service/:GP7Worker` 三个 `exported=true` 独立进程由 native 拉起（Java 层无调用点）。[确证/推断]
2. **数美的 Xposed 枚举是真的，而且结果进上报 JSON。** 4 个方法共 5 处真实 `invoke-static`，聚合器 2173 条指令，最终 `MapUtilsKt.mapToJsonObject(Map)` → 上报体，常量池含键 `"hookJava"`。[确证]
3. **我们的 payload 是唯一"必然留下痕迹"的东西。** `libNeko.so` / `libNeko_linker.so` 被解到 `getFilesDir()` 再用 `System.load(绝对路径)` 加载（`HookLoad.java:471-472, 501/507`），进程 = 游戏主进程 → `/proc/self/maps` 里必然出现 `…/files/libNeko.so`。[确证]

## 1. 档位一：必做（改代码就能降特征，代价低）

| 检测项 | 实现位置（证据） | 我们会不会中 | 规避 | 代价 |
|---|---|---|---|---|
| **payload 路径出现在 `/proc/self/maps`** | `HookLoad.java:466-482`：`new File(ctx.getFilesDir(),"libNeko.so")` + `System.load(pay.getAbsolutePath())`；`ctx=activity.getApplicationContext()`（`:261` 在 UnityPlayerActivity.onCreate 里 → 游戏 Context）→ 映射路径 `/data/user/0/com.RoamingStar.BlueArchive/files/libNeko.so` | **100% 中**（只要加载成功）[确证] | ① 名字去特征化：`libNeko.so`→`libmain2.so` 之类中性名；② 加载成功后立刻 `unlink()` 文件（已 mmap 的段继续可用），maps 显示 ` (deleted)`；③ 进一步改内存加载（memfd + `dlopen("/proc/self/fd/N")`，maps 只剩 `/memfd:xxx (deleted)`） | ①0 成本 ②低（只需在 load 成功后删文件，注意别删 linker 副本前先 load 完）③中（要重做加载链，Android 10+ W^X/`execmem` 有兼容风险，需测试机验证） |
| **hook 实现方式污染 `XposedHelpers` 三 cache** | `HookLoad.java:248 / 278 / 284` 三处 `XposedHelpers.findAndHookMethod`；数美 `l111l11111Il()`（`…l111l111111Il.java:313`）直接读 `fieldCache/methodCache/constructorCache` | **可能中**（`findMethodExact` 走 `getDeclaredMethod`，理论不写 cache；但 `findField`/`findMethodBestMatch` 会写）→ **需实测** | 三处改 `XposedBridge.hookMethod(反射拿 Member, cb)`；实测方法：hook 起来后打印 `XposedHelpers.methodCache.size()` 前后对比 | 低（改动只在模块 Java；风险是反射拿 Member 的写法比 helpers 啰嗦） |
| **作用域过大导致检测面×N** | 现有约定只挂主进程（`ba-hook-survey.md:199`、`ba-java.md:243`）；`:GP6Service/:GP7Service/:GP7Worker/:pushservice/:pushcore` 不挂 | 已规避 | 保持；LSPosed 作用域里不要图省事勾"全部进程" | 0 |
| **主动踩 ACE 的 ioctl 通道** | 三服务 `exported=true`、action=类名、extra `"ioctl"`（`GP6Service.java:18-20`）；Java 侧无调用点 | 已规避（我们不发 `startService`） | 保持：**不要**为了"探一探"给 `:GP6/:GP7` 发 Intent —— 等于主动给反作弊送事件 | 0 |
| **日志关键字** | `HookLoad.java:653` 起：已删 `XposedBridge.log`，注释说明反检测原因 | 已规避 | 保持；native 日志默认收敛（`azusa_native_log.txt` 只在外部目录，见档位二） | 0 |
| **调试器痕迹** | 数美聚合器 `android.os.Debug#isDebuggerConnected()`（`…l1111l111111Il#l1111l111111Il`，code_off 0x62fc24）；`ba-java.md:167`：`debuggable` 未出现（release 默认 false） | 不中（正式包不可调试、我们不 attach 调试器） | 保持：发布包不许带 `debuggable`；测试机也别边跑 gdb/lldb 边进游戏 | 0 |

## 2. 档位二：建议（要做，但需测试机实测或框架侧配置）

| 检测项 | 实现位置（证据） | 我们会不会中 | 规避 | 代价 |
|---|---|---|---|---|
| **libtprt 的 `/proc` 与模块枚举能力** | libtprt 导入 `ptrace/dlopen/dlclose/dlsym/`**`dladdr`**`/opendir/readdir/closedir/readlink/sscanf`；`.rodata` 可打印率 0.31/0.29（字符串加密/VM）→ 明文 0 命中 ≠ 无检测（详见 `ace-ipc.md` §2） | **推断中（中高）**：有 `dladdr`（按地址反查 so）+ 目录遍历 | 静态侧无更强规避；只能把"maps 里的可疑条目"减到最少（档位一 1）+ 不在游戏进程内留可读文件。**证实方式**：测试机 hook `dladdr/readdir` 计数 | 中（需一轮设备实验） |
| **libmsaoaidsec.so 的 maps / LD_PRELOAD 检查** | `out/kw-hits.tsv`：`ptrace=1、/proc/self/maps=1、/proc/self/fd=2、LD_PRELOAD=1、LD_LIBRARY_PATH=1` | 推断中（同一条 maps 暴露） | 与档位一 1 同一套动作；另确认我们**没有**改 `LD_PRELOAD`/`LD_LIBRARY_PATH`（qemu 环境变量那套不能用在游戏进程） | 0（顺带确认） |
| **Xposed API 类在目标进程可见** | 数美 `l111l1111l1Il()`（`:344`）`Class.forName("de.robv.android.xposed.XposedBridge")` + `getDeclaredFields()` + `XposedInit.loadedModules`（`:471-483`）+ `XposedBridge$CopyOnWriteSortedSet`；另 `XposedInit.loadedPackagesInProcess`（`:675-694`） | **100% 中**（只要用 Xposed API 注入） | 模块侧**无解**：`loadedModules` 由 LSPosed 框架写。可选：① LSPosed 的"隐藏模块列表/作用域隐藏"开关；② 彻底换 Zygisk 原生注入（不走 Xposed API） | ①低（框架开关，需用户配合）②极高（放弃现有全部 Java hook 架构） |
| **我们的 hook 记录本身** | 任何 `XposedBridge.hookMethod` 都会写 `XposedBridge.sHookedMethodCallbacks`；数美 `l111l1111l1Il()` 正是枚举 XposedBridge 字段 | **100% 中** | 无法消除；只能少 hook（只挂真正需要的 `onCreate/dispatchKeyEvent/onResume/onStop`），减少可枚举条目 | 0（约束设计） |
| **root / Magisk / /data/adb 指纹** | 数美 dex 字符串命中 `/system/bin/su`、`/system/xbin/su`、`magisk`、`/data/adb` 等（`ba-java.md:115`）；用户设备本身是 KernelSU+root | **中**（设备层，非模块层） | 只能在 LSPosed/Magisk 侧做 root 隐藏（DenyList / KSU 隐藏），不属本模块职责 | 低（配置项，但会与其它 root 工具互相影响） |
| **native 日志写到外部目录** | `HookLoad.java:486-489`：`getExternalFilesDir(null)/azusa_native_log.txt` | 可能中（同机其它应用/取证工具可读；量级小） | 默认只在排障时开；正式版本把 verbose 日志关掉或改写到 `filesDir` | 低 |
| **数美入口是否真开** | `classes.dex` `Lcom/airi/udata/component/SMComponent;` → `SmAntiFraud.create/getSDKVersion/registerServerIdCallback`；`SMComponent` jadx 未反编译 | 接线已确证，**是否被 `SDKConfigSettings.json` 门控 = 未验证** | 先别动；要在测试机用 `logcat | grep -i shumei/smantifraud` 或 hook `SmAntiFraud.create` 观测 | 低（纯观测） |

## 3. 档位三：不划算（别做 / 代价 > 收益）

| 检测项 | 实现位置（证据） | 我们会不会中 | 规避（结论：**不处理 / 放弃**） | 代价 |
|---|---|---|---|---|
| 关 ACE / hook `initialize` / 杀 `:GP6/:GP7` | `AceApplication.java:62-66`（异常被吞）、三服务清单（`AndroidManifest.xml:197-223`） | — | `initialize` 失败**不崩**但半初始化；杀进程=反作弊组件缺失+可疑重启；Java 层 hook 本身新增 ART 篡改特征。没有任何观测能证明"关掉就更安全" | 高（崩溃/风控双风险） |
| 改包重签 / patch `libil2cpp.so`（270,927,056 B） | `ba-hook-survey.md:20,41`；`assets/bin/Data/Managed/` 只有 metadata、无托管 DLL | — | 纯 IL2CPP 没有 DLL 可改；270 MB so 每版本重做；且**未发现 libil2cpp 的 hash pin（见 ace-ipc §3）不代表改包安全**——ACE 的校验焦点在装载体（`a64.dat/a64.sig`、`__tpinfo.tsc/.tsd + .sig`） | 极高 |
| hook 数美 4 个方法让它们返回 false | `…l111l111111Il.java:305/313/344/686`；调用方见 `shumei-xposed.md` §2 | 我们本来就是"有 Xposed"环境 | 返回值被改写本身即异常特征（且 4 个方法分别覆盖不同的证据源：文件/三 cache/Bridge 字段/EdXp 配置），改一个漏三个 → 更容易被判"结果自相矛盾" | 高 |
| Frida / 内存搜值工具进游戏进程 | 我们不用 Frida；`libtprt` 有 `ptrace` 导入 | 不中 | 引入 Frida 会把"必中项"从 3 条变 6 条（`frida-agent`/`gum-js-loop`/`27042`/ptrace 冲突） | 高 |
| 模拟器 / 多开伪装 | `ba-java.md:118` `com.airi...EmulatorCheckUtil`（checkFeaturesByAbi/Board/BaseBand/Cgroup + `getInstalledSimulatorPackages` + `CommandUtil.exec("sh")`） | 真机不中 | 用户真机实测，改这些没有收益 | 高 |
| 反调试对抗（自己 ptrace 回去 / 藏 TracerPid） | `libtprt` 只用 `ptrace` 导入、无 `TracerPid` 明文 | 不中 | 我们不 ptrace，就不会有 TracerPid 痕迹；主动 ptrace 反而可能和 ACE 抢 | 高 |
| C# 侧 `XIGNCODE3Interface` 相关 | `md-xign.txt`：`XIGNCODE3Interface-OnHackDetected` 等只在 GameMain 类名池（发行壳遗留） | 无实际运行时 | 运行时反作弊是 ACE，不是 XIGNCODE3；这条线没有可操作面 | — |

## 4. 可复现命令（工作区内，≤30 行输出）

```bash
WS=/data/user/0/com.ai.assistance.operit/files/workspace/9dc0fd0c-7cad-4366-8d0b-bad7165d8587
# libtprt 特征串命中
python3 $WS/audit/ba-work/.recon/tprt_kw.py
# 数美 4 方法的调用方（DEX 指令级）
python3 $WS/audit/ba-work/.recon/dexcall2.py
# 任意类的调用方（第 2 参数选 classes.dex / classes2.dex）
python3 $WS/audit/ba-work/.recon/dexcalls.py com.ishumei.smantifraud.SmAntiFraud classes.dex
# 26 个 so/dex 的 md5（与 libtprt 内 5 个 32-hex 常量比对，全部不等）
md5sum $WS/audit/ba-apk/lib/arm64-v8a/* $WS/audit/ba-apk/classes*.dex
```

## 5. 一句话结论

能改的只有 **3 件事**：payload 名字/落盘方式（maps）、hook 实现方式（三 cache）、作用域与日志面。

改不了的 2 件事：**Xposed API 类可见性（框架层）** 与 **设备 root 指纹**。

不该碰的 1 件事：**ACE 三进程与数美上报链**——它们没有"关掉更安全"的证据，只有"关掉更像被搞过"的证据。