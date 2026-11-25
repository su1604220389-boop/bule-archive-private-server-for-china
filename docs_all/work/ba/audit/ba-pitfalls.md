# BA 私服/改包 踩坑记录（2026-11-13）

> 每一条都是实测踩出来的，不是推测。下次动手前先读这份，不要重走老路。

## 一、APK 改包（ACE 相关）

| # | 坑 | 现象 | 正确做法 |
|---|---|---|---|
| 1 | **必须删 `assets/__tpinfo.*`（5 个文件）** | 改过 `libunity.so`/`libmain.so` 后，游戏启动即闪退，**没有任何崩溃日志/tombstone** | 删 `__tpinfo.tsc` / `.tsc.sig` / `.tsd` / `.tsd.sig` / `.tp`，完整性校验整段跳过 |
| 2 | **绝对不要往 APK 里加新 .so，也不要改 `libmain.so` 的 `DT_NEEDED`** | 同样是无日志闪退（ACE 直接杀进程） | 只做**原地字节补丁**：libunity 4 字节证书绕过已验证可用 |
| 3 | 删除 `__tpinfo` 后 ACE 不再校验文件哈希 | — | 这是所有改包能跑的前提 |

**已验证可用的最小改包（E30）**：
```
libunity.so @0xA53A38:  f8 03 00 2a  ->  f8 03 1f 2a   (mov w24,w0 -> mov w24,wzr)
+ 删除 assets/__tpinfo.{tsc,tsc.sig,tsd,tsd.sig,tp}
```
这一版不崩，能进游戏。

## 二、客户端重定向（把流量导到我们服务器）

| # | 坑 | 现象 | 正确做法 |
|---|---|---|---|
| 4 | **客户端走 HTTP 代理（127.0.0.1:7890）** | 改 `getaddrinfo` 完全无效——`CONNECT 原域名:443` 由代理那侧解析 | 只能在 CONNECT 层处理，或让客户端不经过代理 |
| 5 | 硬编码 GOT 偏移不可靠 | 崩溃在 `strstr`，参数是 `0x2710`（把别的函数当 getaddrinfo 了）| 运行时解析 ELF `PT_DYNAMIC` 的 `DT_JMPREL`，按符号名找 GOT 槽 |
| 6 | `dl_iterate_phdr` 里遍历**所有**模块会崩 | SIGSEGV，fault addr 是垃圾指针 | 只处理 `libunity.so` / `libil2cpp.so`，并校验 `e_phoff/e_phnum` 边界 |
| 7 | 模块日志写到 `/sdcard` 会静默失败 | 以为模块没注入，实际是没权限 | 写 `/data/data/com.RoamingStar.BlueArchive/files/ba_probe.log` |
| 8 | LSPosed 模块**不能把 Xposed API 类打进 dex** | `Cannot load module: com.ba.probe` + "The Xposed API classes are compiled into the module's APK" | stub 只作 `-cp` 编译，d8 只打包业务类 |
| 9 | `ProtectionDomain.getCodeSource()` 在 LSPosed 里是 null | `installHook err: NPE` | 用 `classLoader.getResource("assets/xposed_init")` 解析 APK 路径 |

## 三、服务端数据层

| # | 坑 | 现象 | 正确做法 |
|---|---|---|---|
| 10 | 国服**没有** PC 版那种 SQLCipher `ExcelDB.db` | `ValidateExcelDbKey` 报 SQLITE_NOTADB | 国服的 `ExcelDB.db` 藏在 `files/TableBundles/<id>_824ce3a8…`，是**明文 SQLite（160 MB / 398 张表）** |
| 11 | 玩法表 flatbuffer 版本必须对齐 | `CharacterExcel: skipped 7223 unreadable row(s), loaded 0` | 国服 `CharacterExcel` 是 **65 槽位**；Shittim `v2026.8.8` 是 65 字段，HEAD 是 67 → **用 v2026.8.8** |
| 12 | 服务端会自动下载/覆盖 `Resources/Dumped/ExcelDB.db` | 放进去的明文库被替换成加密库 | `appsettings.json` 设 `UseCustomExcel=true`、`DownloadExcelTables=false` |
| 13 | `.bytes` 表必须放 `Resources/Dumped/Excel/` 子目录 | 放根目录不生效 | `Excel.zip` 解压到 `Dumped/Excel/` |
| 14 | .NET 在设备上起不来 | `GC: Reserving 256 GiB ... failed` | `DOTNET_GCHeapHardLimit=0x40000000`、`DOTNET_gcServer=0` |
| 15 | 服务端只开 HTTP（Kestrel 在代码里禁用 HTTPS）| 客户端说 HTTPS | 前面加一层 TLS 终止（python ssl 代理）→ 127.0.0.1:5000 |

## 四、2026-11-13 下午场：ACE 判定 / 容错矩阵 / 把设备搞挂的根因

> 全部为实测；每条都注明判定依据。

### 4.1 改动面容错矩阵（一次性记住，别再试）

| 改动对象 | 结果 | 版本 | 判定依据 |
|---|---|---|---|
| `libunity.so` 4 字节证书补丁 `@0xA53A38` | ❌ **SIGBUS** | E36 | `ApplicationExitInfo reason=2 status=7`，无 tombstone |
| `libairisgcore.so` 整库替换（NEEDED 干净、无人依赖） | ❌ **SIGBUS** | E35 | 同上 |
| 新增 `classes3.dex`（哪怕只有 660 B 空类） | ❌ **卡在 Android 启动界面** | E39/E40/E41 | Unity 未加载；与 ACE 无关（ACE 是 8~10 s 后杀） |
| 重编 **`classes.dex`**（baksmali→smali 回编） | ❌ 卡启动界面 | E43 | 同上 |
| 重编 **`classes2.dex`** 改一个 `const-string` | ⚠️ 首次启动成功（E44），但**之后同批 APK 全部卡启动界面** | E44 | — |
| `resources.arsc` / `res/*` | ✅ 正常 | E32/E34/E42 | 能进主程序、文案生效 |
| `assets/*.json`（`sdk_url`）、删 `__tpinfo.*` | ✅ 正常 | 同上 | SDK 登录链走到我们服务器 |
| **`libil2cpp.so` 填充字节翻转**（EOF 后 1600 B slack） | ✅ **正常启动（45 s+ 存活）** | E38 | 与 `ace-ipc.md` §3「无 hash pin」一致 |

### 4.2 ACE 会「记账」：判定是持久化的

- 触发过一次异常改动（E43 的 dex）后，**后续任何版本**（包括之前能跑的 E42）启动都被 `kill(SIGBUS)`。
- 复位方法（实测有效）：删除
  ```
  /data/data/com.RoamingStar.BlueArchive/files/ace_shell_di.dat
  /data/data/com.RoamingStar.BlueArchive/files/shell_cache
  /data/data/com.RoamingStar.BlueArchive/files/ano_tmp
  /data/data/com.RoamingStar.BlueArchive/files/data/app
  ```
  然后重新启动即可恢复。
- **这条解释了「同一版 APK 有时能跑、有时被杀」的全部现象**——不是概率，是历史判定被记住。

### 4.3 ★ 最严重的一次事故：清空 `/data/data/<pkg>` 会永久卡启动

- 现象：卡在 Android 启动界面，Unity 从未加载，`/proc/pid/maps` 里只有 `libtprt.so`。
- 根因（`debuggerd -b <pid>` 实测调用栈）：
  ```
  ActivityThread.handleBindApplication
   → TechApplication.attachBaseContext
     → AceApplication.attachBaseContextShell
       → libtprt.so initialize()
         → __sem_timedwait   ← 永远等不到
  ```
  ACE 的 `initialize()` 在等 `:GP6/:GP7` 服务进程应答，而这两个服务依赖
  `/data/data/<pkg>/files/data/app/…` 里的解包产物——**清内部数据会把这个目录删掉**，ACE 无法重新解包，
  于是永久阻塞在 `sem_timedwait`。
- 正确恢复：**卸载重装**（让 ACE 重新解包）。
- 保资源技巧（实测可行）：卸载前把
  `/sdcard/Android/data/com.RoamingStar.BlueArchive`（本机 11 GB 表/资源）
  `mv` 到 `/sdcard/ba_data_bak`，重装后再移回，可免去 11 GB 重下。

### 4.4 网络相关结论（此前误判过）

| 说法 | 实测 |
|---|---|
| 「ACE 联网校验卡住启动」 | ❌ 否。对该 UID 全量 REJECT 外网（仅放行 127.0.0.0/8）后，仍然卡死 → 与网络无关 |
| 「断网就能进主程序」 | 在**另一台手机**上成立，但那台没有本机的 `/data/data` 污染史；本机卡死是 §4.3 的 sem 阻塞 |
| 「`sdkcard.py` 不跑 → 网络异常，请重新连接」 | ✅ 成立。PRoot 里的服务重启后不会自启，**每次重启设备后必须先拉起 `sdkcard.py`**，否则表现就是「网络异常」而不是「卡密不正确」 |

### 4.4b `status=9`（SIGKILL）≠ ACE，是系统内存/多窗口

- 现象：重装后游戏反复退出，`exit-info` 显示 `reason=2 SIGNALED status=9`。
- 判定：**status 9 = SIGKILL**，ACE 用的是 `SIGBUS`（status 7）。当时 `free -m` 显示 free 仅 **876 MB / 15 GB**。
- 关联日志：`OplusFlexibleDCSManager: startMiniWindow ... group_pkg=com.RoamingStar.BlueArchive`
  → 通过 `monkey` 在 Operit 前台时拉起游戏，会被系统塞进小窗，容易被回收。
- 处理：
  1. 清掉我们自己的后台 python（`cdnproxy/tlsproxy/tb_scan/find_host`）后 available 从 0.7 G 回到 **7.7 G**；
  2. 验证启动最好**手动点图标**（避免小窗路径），不要连续 `monkey` 多次拉起。

### 4.3b ★ 卸载重装后恢复资源必须改属主，否则报「Not enough storage」

- 现象：重装后手动打开游戏，弹原生框 **`Error / Not enough storage space to install required resources.`**，
  但磁盘实际有 **28 GB** 空闲。很容易误判成「应用被搞坏」或「空间不足」。
- 根因：卸载重装后应用 **UID 变了**（本机 `10574` → `10575`）。
  从备份 `mv` 回来的 `/sdcard/Android/data/<pkg>`（11 GB）里文件属主还是旧 UID，
  游戏读不到自己的资源 → 认为需要重新安装 → 报空间不足。
- 正确做法（实测一次修好）：
  ```sh
  UID=$(stat -c %u /data/data/com.RoamingStar.BlueArchive)     # 新 UID
  chown -R $UID:1078 /storage/emulated/0/Android/data/com.RoamingStar.BlueArchive
  # 1078 = ext_data_rw（不能用 $UID:$UID，组必须保持 ext_data_rw）
  ```
- 判定成功：重启游戏后不再弹该框，能进到 SDK 登录页。

### 4.5 客户端重定向相关（本轮新增证据）

| # | 结论 | 证据 |
|---|---|---|
| 1 | `files/Hosts` **不决定连接目标**（只做记录/展示） | 写成单条 `127.0.0.1:9443`（时间戳字段设成比官方大 1），登录成功后 9443 **0 连接**，游戏还把官方条目追加回去 |
| 2 | `LocalizeConfig.txt` 的 `ResUrls` 改成本机地址会被忽略 | 改后 `cdn.log` 一条请求都没有，游戏直接提示「网络异常」 |
| 3 | 网关域名**不在** APK 任何静态产物里 | dex / libil2cpp / libunity / global-metadata / assets / 6227 个 TableBundles，ASCII+UTF-16 全扫，0 命中（仅 `webseasonexceltable` 有活动页链接） |
| 4 | 网关域名的真实形态是 `gameUrl`，由**游戏传给 SDK** | 运行内存里 SDK 日志原文：`[AiriSDK][1.16.1][...][AiriSdkManager.kt:32 init] ... gameUrl=https://state-api.bluearchive-cn.com/api/state` |
| 5 | `gameUrl` 只在 init 记录，**不参与登录** | E44 把 `TechSDKUnityBridge$1.val$gameServerUrl` 强制成我们的地址后，SDK 登录链照常走完，`/api/state` 命中 **0** |

### 4.6 工具链坑（打包/安装）

| # | 坑 | 正确做法 |
|---|---|---|
| 1 | `apksigner` 需要 **≥2.1 GB 余量**，否则 `FileNotFoundException`/半截输出 | 签名前先删旧包/临时文件；失败后别 `rm` 输入（会被自己删掉） |
| 2 | `pm install` 失败 `INSTALL_FAILED_INSUFFICIENT_STORAGE`（4.9 GB 仍报） | 用 `pm install-create/-write/-commit`；**先流式写入 session、再删除源 APK、最后 commit**，可省一份空间 |
| 3 | `resources.arsc` 必须**首条 + 不压缩 + 4 字节对齐**（targetSdk 33 强制） | 写 zip 时给 arsc 加 extra 字段补齐；`zipalign` 在本机对大文件会 `Illegal instruction` |
| 4 | 新增 dex 要 4 字节对齐（按**文件绝对偏移**算，不是条目内偏移） | 但见 §4.1：加 dex 反正过不了启动，别在这上面花时间 |
| 5 | `d8` 用 `-o` 参数在部分版本报 `Unsupported source file type` | 改用 `--output <dir>` |
| 6 | LSPosed 模块的 `assets/xposed_init` 若被打成根目录 `xposed_init`，模块不被识别 | zip 时保留 `assets/` 路径；模块里的 so 不能 `loadLibrary`，要先从 APK 解到私有目录再 `System.load` |
| 7 | 游戏进程里的 `XposedBridge` 是**混淆替身类**，`hookMethod/hookAllMethods` 全 `NoSuchMethodError` | 该游戏不能用 Xposed API 做 Java hook；native GOT hook 可用但会被 ACE 处理 |
| 8 | 禁止未经允许 `reboot`/`svc power` | 只在用户明确要求时执行 |

### 4.7 当前已验证可用的一版

- **E42**：官方资源基线 + 原厂 `libunity` + 我们的 `res`（卡密文案）+ `assets/SDKConfigSettings.json`（`sdk_url` 指本机）+ 删 `__tpinfo`
- 表现：能进主程序、SDK 卡密登录通过、停在「认证服务器拒绝了请求」（网关仍是官方）
- 注意：装过 E43/E44 之后要先按 §4.2 清 ACE 判定，或按 §4.3 卸载重装

## 五、当前进度锚点

- **现役可用包：E42**（2,126,782,882 B）＝官方资源基线 + 原厂 `libunity` + 我们的 `res` + `sdk_url` 指本机 + 删 `__tpinfo`
- **必须常驻**：`/root/bapatch/sdkcard.py`（卡密服务，`0.0.0.0:8080`）。**设备每次重启后要手动拉起**，否则游戏显示「网络异常，请重新连接」
- **资源备份**：本机 11 GB 表/资源已 `mv` 到 `/sdcard/ba_data_bak`（卸载重装期间保命用，重装后移回 `Android/data/com.RoamingStar.BlueArchive`）
- **已废弃/不可用**：`libunity` 证书补丁（ACE）、任何 `.so` 替换、新增/重编 dex、`Hosts`/`LocalizeConfig` 重定向
- **唯一还没试完的一条**：`libil2cpp.so` 已验证可改（E38 正常启动），下一步是在其中定位网关地址的产生点（静态/运行时均可，因为不再受 ACE 限制）

### 旧锚点（2026-11-13 上午，已过时，仅供追溯）

- E30 APK：`/sdcard/Download/BA_E30.apk`（2,126,498,053 B，已签名，已安装，不崩）
- 服务端：`/root/bapatch/shittim88`（v2026.8.8 + 国服数据），`http://0.0.0.0:5000` + `5100`
- TLS/连接代理：`/root/bapatch/tlsproxy.py`（9443→5000）、`connectproxy.py`（8443→9443）
- LSPosed 模块：`/root/bapatch/lsp/build10/DHookProbe.apk`（hook 已能装，`slots=3`）
### 4.8 libil2cpp 代码注入实测（2026-11-13 晚）

| 实验 | 结果 |
|---|---|
| 往 libil2cpp RX 段尾部空隙(0xf2c2410)写入 ARM64 代码，改 PLT 首指令为 B | ✅ **不触发 ACE**，进程正常启动运行 |
| 注入代码内调用 `dlopen("libc.so")+dlsym("getaddrinfo")` 后 tail-call 真函数 | ✅ 可用（E63 alive=24049） |
| 把结果写入「代码段里的 .quad 槽」 | ❌ SIGSEGV(ACCERR)，代码页只读 |
| 恢复寄存器时先 `ldp x19,x20,[sp],#N` 再 `br x20` | ❌ 真指针被覆盖 → 跳野地址 |
| `__android_log_print` 从注入代码调用 | ❌ `__strlen` 读到 0x4（可变参数传错） |
| 运行时 `mprotect` 写 libc 代码页 | ❌ SELinux 拒绝（execmod） |
| 改 libil2cpp 的 getaddrinfo PLT | ⚠️ 能拦到，但参数不稳定（有时 x0=2），且**管不到 libunity 的解析** |
| 改 libil2cpp 的 connect PLT | ✅ 生效：连接确实被改到目标 IP（AF_INET 与 AF_INET6 都要处理） |
| 本机 `/system/etc/hosts` 覆盖官方域名 | ❌ 无效（游戏用 HTTPDNS，不走系统解析） |

**libunity 的 GOT 偏移（离线解析）**：`getaddrinfo=0x13d94d8`、`connect=0x13d95d8`；
**libil2cpp RW 段可写区**：文件末尾之后到 memsz 之间（如 `base+0x10300000`），可用于放运行时变量。

**未完成**：把 GOT 改写 + 真函数指针持久化（RW bss）这一版做稳，E64 表现从「被官方拒绝」变成「超时」，说明路径已改但实现仍有阻塞。

### 4.9 客户端注入：触发点与 GOT 的实测结论（2026-11-13 夜）

| 手段 | 结果 | 证据 |
|---|---|---|
| 改 `.plt` 首指令（malloc/gettimeofday/connect/getaddrinfo） | ❌ 无效 | 改成写日志桩后，日志文件连 "IN" 都没有；游戏照常往官方 IP 连 |
| 结论 | 该 so 走 **‑fno‑plt 风格**：直接读 GOT 调用，`.plt` 桩根本没人走 | 同上 |
| `DT_INIT` 改成代码洞地址 | ✅ 可用 | 日志 `IN / BA / DON` 出现，进程存活，未触发 ACE |
| 运行时 `mprotect` + 写 **libunity** GOT | ⚠️ 未证实 | 写入后无流水转向，且无法回读验证 |
| 运行时 `mprotect` + 写 **libil2cpp 自身** GOT | ❌ 崩 | SIGSEGV/SEGV_ACCERR `(write)`，pc 落在代码洞内写 GOT 那条 |
| `open("/proc/self/mem")+lseek+write` 写 GOT | ⚠️ 未证实 | 用 #1(O_WRONLY) 时静默失败；改 #2(O_RDWR) 后日志仍正常，但网关流量未转向 |
| 把 `.rela.plt` 里 connect/getaddrinfo 的 `R_AARCH64_JUMP_SLOT` 改成 `R_AARCH64_RELATIVE` | ❌ 链接器直接 abort | `exit-info status=6 (SIGABRT)`，进程秒退 |
| **root 直接替换 /data/app/.../lib/arm64/libil2cpp.so 原位文件** | ✅ 可用 | 替换后启动正常、`DT_INIT` 钩子照跑，未触发 ACE |

操作要点：
- 原位替换免去每次重打 2.1G APK / 装机（磁盘只剩 4G，装机常报 `INSTALL_FAILED_INSUFFICIENT_STORAGE`）。
- 原始 so 备份：`/data/local/tmp/orig_inst.so`（270,927,056 B）。
- 打点文件：`/data/data/com.RoamingStar.BlueArchive/files/bainj.txt`。
- 卸载重装会改 UID；恢复 11G 资源必须 `chown -R <uid>:1078`（见 §4.3b）。

### 4.10 GOT 实测取值（root 从外部读 `/proc/pid/mem` 得到）

| 目标 | 偏移 | 实测值 | 含义 |
|---|---|---|---|
| libil2cpp `getaddrinfo` GOT | `0xfbafe60` | `0xf2c0010` | 仍指 PLT0 → 该导入**从未被调用** |
| libil2cpp `connect` GOT | `0xfbafe90` | `0xf2c0010` | 同上（解释为何改它全无效果） |
| libunity `connect` GOT | `0x13d95d8` | `0x74df8c9028`（libc） | **已解析、确实在用** |
| libunity `malloc` GOT | `0x13d9738` | `0x74df92dcc0` | 已解析 |

- **libunity 的加载基址不能用 maps 第一行**：本机存在两个 `offset=0` 的映射（整文件 r--p 副本 + r-xp），正确基址取
  `grep 'libunity.so' /proc/$PID/maps | grep 'r-xp 00000000'` 那一行的起始地址。用第一行算基址会让所有 GOT 读写全部落空——这就是 §4.9 里「写了但没反应」的直接原因。
- root 从外部直接改 GOT 可行（实测读回一致）：
  ```sh
  dd if=/sdcard/v.bin of=/proc/$PID/mem bs=1 seek=<十进制绝对偏移> count=8 conv=notrunc
  ```
  **禁止「整页读-改-写」**：页内其他 GOT 槽可能刚被懒绑定改写，回写会把它们退回旧值，实测直接导致进程死亡。
- `mksh` 的 `$(( ))` 是 32 位，大地址必须走分页读（`dd bs=4096 skip=<页号>`）或上面 `dd` 的十进制 `seek`。

### 4.11 ★ 代码洞里 `adr` 指向**全局符号**会拿到 0（2026-11-13 深夜，血亏一轮的坑）

- 现象：注入代码第一条 `blr` 就崩，`fault addr = 0x1c20`（正好是 `|P_OPEN - CAVE|`），
  `#01 pc` 落在代码洞内 `blr` 那条。看起来像「算错了偏移」，其实是 **`adr` 取到 0**。
- 根因：`blob0` 用了 `.globl`。把 `.o` 里的 `.text` **直接抠出来**不做链接时，
  **全局符号的 `adr` 会留成未填的重定位（imm=0）**；只有**局部标签**才会在汇编阶段就解析成正确 PC 相对位移。
- 判定方法（不用上机）：
  ```sh
  objdump -D -b binary -m aarch64 /tmp/m.bin | sed -n '5,16p'
  # 正确：18: 10ffff50  adr x16, 0x0        ← 目标 = 段首
  # 错误：18: 10000010  adr x16, 0x18       ← 目标 = 自己（imm=0，说明是重定位没填）
  ```
- 修法：在段首同时放一个**局部标签**，`adr` 一律用它：
  ```
  blob0:
  Lb0:              ← adr x16, Lb0
  entry:
  ```
- 顺带确认的两条：
  - `dl_iterate_phdr` 给的 `dlpi_addr` **等于** `maps` 里 `r-xp 00000000` 那行的起始地址（实测打出 `72e1c74000`，与 maps 完全一致），所以取基址可以放心用它。
  - `libunity` 的 GOT 所在页是 **rw-p**，可以**直接 `str` 写**，不需要 `mprotect`、也不需要 `/proc/self/mem`；
    之前“写了没反应”是 `adr` 拿到 0 导致写到了地址 0 附近，与权限无关。
