# §五 不可行 / 极高风险方向（12 条 · 每条四要素）

> 负责人：infeasible-scout（第 2 层，承接 recon-hooks 的 ba-hook-survey.md §五）。
> 性质：**只读**。未解包 base.apk、未联网、未安装/启动游戏、未改任何源码；本文件是唯一写入产物。
> 目标包：`com.RoamingStar.BlueArchive` 国服，仅 arm64-v8a。

## 证据源与缺口（先看）

| 证据源 | 用途 | 状态 |
|---|---|---|
| `audit/ba-hook-survey.md` | APK/IL2CPP 结构事实、现有模块能力边界 | 已读 |
| `audit/ba-java.md` | Java/dex 层事实、数美 Xposed 检测面 | 已读 |
| `audit/_parts/_frag/blob.md` | `ConstCombatExcel` 风控字段归属 | 已读 |
| `audit/ba-apk/out/kw-hits.tsv` | 反作弊关键词 × so 命中矩阵（85 列） | 已读（本文件按列名复核） |
| `audit/ba-apk/out/metadata-strings.txt` | 768,396 行；名字/协议名/字段名明文 | 本文件新增 grep 取证 |
| `audit/ba-apk/out/strings/libil2cpp.so.txt` | 77,730 行；用于**证伪** frida 命中 | 本文件新增 grep 取证 |

**缺口（不编造）**：`audit/_parts/thresholds.md` 与 `audit/_parts/endpoints.md` 在本文件写作时**尚未落盘**（分别由 risk-thresholds / ep-harvester 在跑）。本文件不引用不存在的文件，相关结论一律改用 `metadata-strings.txt` 直接取证。

**证据强度口径**：
- **实测** = 本工作区跑过命令并留有输出；
- **静态确证** = 文件里确实存在的结构/字符串/类名，可复现 grep；
- **推断** = 由前者推演、未验证执行行为（写「推断」时不许当结论用）。

**全局三条（用户最容易想做、但必须先劝退）**：
1. **静态 Il2CppDumper 扒 metadata**（方向 1）——头部已不是标准 IL2CPP 头，第一步读 header 就废；
2. **改包重签 / 改托管 DLL**（方向 2）——本包纯 IL2CPP，没有 DLL 可改，改包要过 ACE 启动链；
3. **全局 TimeScale 无上限加速**（方向 6）——`AllowedMaxTimeScale` / `MinimumClearTime` / `CheckCheaterMaxUseCost*` / `ExcessiveTouchCheck*` 就是一整族「加速与连点」风控常量。

---

## 方向 1：静态 Il2CppDumper 直接吃 global-metadata.dat

- **为什么不行**：标准 IL2CPP metadata（v24~v31）首字段是 sanity `0xFAB11BAF`、第二字段是版本号（如 `0x1F`）；实测前 8 字节 `9443 7212 184b 9eec` → magic `0x12724394`、第二字段 `0xEC9E4B18`（不可能是版本号），且 `grep -abo $'\xaf\x1b\xb1\xfa'` 全文件 **0 命中**（`audit/ba-hook-survey.md:74,78,80,84-85`）。同文件里名字明文字节**遍布 38 MB**（0 MB 桶就有 15,743 条，逐 MB 桶计数见 `ba-hook-survey.md:90-106`）→ 这不是整文件加密，而是「**头/结构表被改写或自定义 magic**」，而 Il2CppDumper 的第一步正是读 header 取各表偏移。
- **失败点/风控点**：解析在 header 处即失败；即使强行按标准布局读，type/import/method 偏移全是垃圾，后续「按名解析」全错。纯离线操作，无风控面，**代价是时间被烧掉且结论不可信**。
- **可替代方案**：运行时按名解析——`il2cpp_*` 导出 237 个、7 个关键 API 全命中（`ba-hook-survey.md:59-66`），AzusaBA 的 `GetMethodInfo` 已在 3.0.2 跑通（`ba-hook-survey.md:66`）；只需「这个名字存在吗」时 `strings` 已足够（`ba-hook-survey.md:108-111`）。「先还原头再静态 dump」**无可行替代**：要先逆出加密/改写算法，而算法未验证（`ba-hook-survey.md:135`）。
- **证据强度**：**静态确证**（头部数值、无 magic、明文分布均是实测）；「Il2CppDumper 必失败」为**推断**（本工作区未真的跑 dump）。

---

## 方向 2：改包重签 / 改托管 DLL 回包

- **为什么不行**：`assets/bin/Data/Managed/` 下**只有** `Metadata/global-metadata.dat`，没有任何 `Assembly-CSharp.dll`（`ba-hook-survey.md:47-54`）→ 老式「dnSpy 改 DLL 再回包」在本包**不存在**。改包还要过完整性面：`libunity.so` 命中 `signature=24 / Signature=9 / GET_SIGNATURES=1 / crc32=2 / checksum=4 / digest=2 / ace_=25`，`libil2cpp.so` 命中 `signature=2 / ace_=3`（`audit/ba-apk/out/kw-hits.tsv`，列 48/49/50/43/44/47/80；行 `libunity.so` / `libil2cpp.so`）。ACE 在 `AceApplication.attachBaseContext → attachBaseContextShell → native initialize(...) + System.loadLibrary("tprt")` 时启动（`audit/ba-java.md:63-64`）。
- **失败点/风控点**：重签后签名/摘要不一致；`initialize` 非 0 直接抛异常（`ba-java.md:63`）→ **崩在启动阶段，进不到游戏逻辑**；即使侥幸启动，检测结果还有独立上报通道（见方向 4）。
- **可替代方案**：LSPosed 运行时注入、不改包（现有 AzusaBA 路线，`ba-hook-survey.md:199`）。「改包回包」**没有替代，只能放弃**。
- **证据强度**：**静态确证**（无 DLL + 关键字命中 + 初始化链）；「ACE 启动即校验签名」为**推断**（`ba-java.md:223` 列入未验证清单）。

---

## 方向 3：Java 层改战斗数值 / 掉落 / 抽卡 / 奖励

- **为什么不行**：三条独立证据链（`audit/ba-java.md:151-158`）：① 类名 243 条命中剔除三方 SDK 后为 **0**，`com.RoamingStar.*` 仅 20 个类且全是 `BuildConfig`/`R$*`（`ba-java.md:32`）；② dex 字符串 `damage / critical / gacha / drop_rate / reward` 命中 **0/0/0/0/0**（`ba-java.md:155`）；③ 标准 IL2CPP 结构，dex 中无任何 `UnityEngine.*` / `Il2Cpp.*` 绑定类（`ba-java.md:156`）。
- **失败点/风控点**：Java 层**没有可改入口**；强行反射拿 Unity 对象 → `NoSuchMethod`/`CNFE`；唯一可写的 `TechSDK$SdkCallBack#onCallBack`（`ba-java.md:99`）是登录/支付回调，改它只会改坏流程，碰不到战斗。
- **可替代方案**：走 native stat 表通道——`get_CurrentStat` hook + `ApplyStatMods` 的 `switch(key)`（`ba-hook-survey.md:159-183`，对应 `main.cpp:1479` / `main.cpp:1549`）。新增数值维度只加 key，不新增 hook 点、不新增反射调用。
- **证据强度**：**静态确证**。

---

## 方向 4：改服务端权威项（掉率 / 抽卡结果 / 结算奖励 / 体力 / 货币）

- **为什么不行**：整个客户端-服务端协议是 `NetworkTask` / `Response` 对（`metadata-strings.txt` 中 `NetworkTask` 命中 **1,071** 处）；战斗结算以「带 BattleResult 的 NetworkTask」提交：`ConquestConquerWithBattleResultNetworkMessage`(29752) / `ConquestConquerWithBattleResultNetworkTask`(29770) / `ConquestMainStoryConquerWithBattleResultNetworkTask`(29775) / `ConquestEventObjectBattleResultNetworkTask`(29781) / `ConquestErosionBattleResultNetworkTask`(29787) / `WeekDungeonBattleResultNetworkTask`(30374)，并带 `-HandleMessage0`(136859) / `-ErrorHandler0`(136860) / `-ProcessSession0`(136861) 的完整收发管线；抽卡进度 `SyncBoxGachaDB`(27508)；账户 `Account_CurrencySync`(73056) / `Account_LoginSync`(73070)；客户端 DB 有 **148** 个 `Sync*` 入口（`SyncSaveDB` 21324、`SyncDBs` 22177、`SyncChapterClearRewardHistory` 22860）→ **本地 DB 是服务端回灌的下游副本**，不是真相源。
- **失败点/风控点**：客户端能造的只有「结果上报」，服务端按自己的房间/时间/消耗重算，不一致→拒绝/回滚；`ReloadDAOIfCheat`(36154) 表明检测到作弊时客户端会**重载 DAO**（把你改的 DB 冲掉）；检测结果另有独立上报 API：`Account_ReportXignCodeCheater`(73067) + `AccountReportXignCodeCheaterRequest/Response`(72752/72753) + `...ResponseMessage/NetworkTask`(29216/29217)；重复领奖由服务端去重。
- **可替代方案**：只能改「本地表现层」（动画、伤害数字、预演、UI 状态），**改不了实际资源与奖励**。要「看起来像」可以；要「真的拿到」**无替代**。
- **证据强度**：**静态确证**（协议名/同步名/上报 API 全部是 metadata 明文）；「服务端会校验/回滚」为**推断**（服务端代码不可见）。

---

## 方向 5：关 ACE / 关反作弊进程（含 hook `initialize`、杀 `:GP6/:GP7`）

- **为什么不行**：`AceApplication.attachBaseContext → attachBaseContextShell → native initialize(pkg, filesDir, nativeLibDir, sourceDir, splits)` + `System.loadLibrary("tprt")`（`audit/ba-java.md:63-64`）；`:GP6Service` / `:GP7Service` / `:GP7Worker` 是 `exported=true` + 独立进程 + 自定义 action 的服务（`ba-java.md:67,180`）；`libtprt.so` 命中 `ptrace`（`kw-hits.tsv` 行 `libtprt.so`）。Java 层 hook 只能让 `initialize` 失败（非 0 直接抛异常），**不会停掉已起的 native 线程/扫描**（`ba-java.md:63,193`）。
- **失败点/风控点**：让 `initialize` 失败 = 启动即抛异常；杀 `:GP*` 进程 = 反作弊组件缺失/被重启（推断），并在上报面留下「检测组件不在」的异常特征；hook 检测函数返回值的做法本身新增 ART 方法篡改特征（deopt/inline），只能测试机实验（`ba-java.md:250`）。
- **可替代方案**：**不碰 ACE**。只在主进程注入、最小作用域（`:GP*`/`:push*` 不挂：`ba-java.md:243`、`ba-hook-survey.md:199`）。想「关掉」**没有替代**。
- **证据强度**：**静态确证**（初始化链/进程清单/字符串）；「杀进程会重启或上报」为**推断**。

---

## 方向 6：全局 TimeScale 无上限加速

- **为什么不行**：客户端常量表 `ConstCombatExcel` 里存在一整族可读的风控常量：`AllowedMaxTimeScale`(60875/60974/形参 61069)、`MinimumClearTime`(60871) 与**独立槽位** `ArenaMinimumClearTime`(60878)、`CheckCheaterMaxUseCostNonArena/Arena/MultiFloorRaid`(60873/60874/60901)、`ExcessiveTouchCheckTime/Count`(60902/60903)（`audit/_parts/_frag/blob.md:40-159`，原始行号 `metadata-strings.txt:60625-61100`）。改 `TimeScale`（`set_TimeScale` 2 处、`TimeScale` 93 处，`ba-hook-survey.md:123`）**不会**改这些常量；一旦超过 `AllowedMaxTimeScale`、或通关时长短于 `MinimumClearTime`、或消耗超 `CheckCheaterMaxUseCost*`，就正落在这些判据上。
- **失败点/风控点**：结算侧被「最短通关时长 / 最大消耗」判据抓；连点/宏被 `ExcessiveTouchCheckTime + ExcessiveTouchCheckCount`（触摸频率）抓；这些字段**没有服务端同名 DTO**（`blob.md:165-167`）→ 判据是「客户端常量 + 本地逻辑」，但结论仍会进结算上报（方向 4）。默认数值**未知**（`blob.md:36,167` 明写未取到），所以「多少倍会触发」不能写死。
- **可替代方案**：只在游戏自带档位里用——`NormalTimeScale`(60863) / `FastTimeScale`(60864) / `BulletTimeScale`(60865) 证明游戏本身有多档时间缩放（`metadata-strings.txt:60863-60865`，`blob.md:62`）；或干脆不走时间轴，改「我方 stat」（方向 3 的替代）。「全局无上限加速」**只能放弃**。
- **证据强度**：**静态确证**（字段存在与归属）；具体阈值与触发行为为**推断**。

---

## 方向 7：直接内存改 stat 表绕过 hook

- **为什么不行**：stat 表布局是版本相关的逆向结构：`stat+0x28 → valueTable`、`+0x18 entries`、`+0x20 count`（代码限 ≤512 做防御）、`entry = +0x20 + i*24`、`+0 key / +8 value`（`ba-hook-survey.md:161-171`）；现有 hook 还维护**原值缓存 + 撤销**（`StatGetOrig` / `StatWriteOrigForKey` / `StatRestoreRecent`，`ba-hook-survey.md:184`），并按 `TT_Student` 只改我方（`ba-hook-survey.md:183`）。绕过 hook 直写内存 = 放弃这整套「时机 + 回滚」保障。
- **失败点/风控点**：实体生成 / buff / 升级 / 换装时游戏自己重算会覆盖你的写入；写错偏移直接崩在 UnityMain/GLThread；版本更新偏移漂移；写入面被进程内扫描看到（`libil2cpp.so` 命中 `/proc/self/maps=2`、`ace_=3`、`tss=8`，`kw-hits.tsv`）。
- **可替代方案**：继续用 `get_CurrentStat` hook：游戏自己算完、我们在返回路径改写（`ba-hook-survey.md:159-187`），天然对齐每次重算；关闭时用原值缓存回写。
- **证据强度**：**静态确证**（机制来自现有代码与 survey）+ **推断**（重算时机）。

---

## 方向 8：替换 / patch `libil2cpp.so`（ELF patch、换 so、改资源）

- **为什么不行**：`libil2cpp.so` = **270,927,056 B**（`ba-hook-survey.md:20,41`），随版本整体变化；`libunity.so` 命中 `signature=24 / Signature=9 / GET_SIGNATURES=1 / crc32=2 / checksum=4 / digest=2 / ace_=25`，`libil2cpp.so` 命中 `signature=2 / ace_=3`（`kw-hits.tsv`）；ACE 在 Application attach 阶段就加载 `libtprt`（`ba-java.md:63-64`）；APK 2.1 GB 且 `extractNativeLibs=true`（`ba-java.md:171`）→ so 会被解出到 lib 目录参与加载。
- **失败点/风控点**：签名/摘要/CRC 类校验（静态关键字命中，实际校验点未验证）；即使过了，每次游戏更新都要重做 270 MB so 的 patch；替换 so 也改不了服务端（方向 4）。
- **可替代方案**：Dobby inline hook（运行时，不落盘改 so：`ba-hook-survey.md:195`，`main.cpp:1698`）或 payload 内存 patch。**反向提醒**：不要改回 `Anti/MemoryHide.h` / `Anti/SeccompHook.h`——那套已实测多线程 SIGSEGV（`ba-hook-survey.md:196`）。
- **证据强度**：**静态确证**（体积/关键字/加载链）；「启动即校验」为**推断**。

---

## 方向 9：Frida / 通用内存搜值

- **为什么不行**：dex 里没有 `frida` / `27042` / `gum-js-loop` / `linjector` / `substrate` 特征串（`ba-java.md:115`）；`libil2cpp.so` 的 `frida=1 / Frida=1` 经本文件复核是**噪声**——`strings/libil2cpp.so.txt:32291` 是 `Friday`、`:34035` 是 `...fridayjuniordollar...`（`grep -i frida`）。但进程侧并非没牙：`libtprt.so` 命中 `ptrace=1`，`libmsaoaidsec.so` 命中 `ptrace=1 / /proc/self/maps=1 / /proc/self/fd=2 / LD_PRELOAD=1 / LD_LIBRARY_PATH=1`（`kw-hits.tsv`）；数美在 Java 层枚举 `XposedHelpers.fieldCache/methodCache/constructorCache`、`XposedInit.loadedModules`、`XposedBridge` 字段（`ba-java.md:104-113`），native 侧还可读 maps/TracerPid（`ba-java.md:251`，原文标注为能力推断）。
- **失败点/风控点**：Frida agent/gadget 会在 `/proc/self/maps` 留映射，`ptrace` 面可反附加；数美把设备指纹与检测结果直接进风控上报（`ba-java.md:101,252`）。内存搜值：IL2CPP 对象在 native 堆、数值高频重算，静态搜到的地址很快失效。
- **可替代方案**：不用 Frida；用 LSPosed + 自有 payload（Dobby）在进程内 hook，最小作用域 + 全模块不用 `XposedHelpers.find*`（`ba-java.md:241,252`）。搜值只在测试机用于定位偏移，**不进交付链**。
- **证据强度**：**静态确证**（字符串/关键字/噪声证伪）；「Frida 会被抓」为**推断**（本工作区无实测样本）。

---

## 方向 10：模拟器 / 多开（分身、VirtualApp 类环境）

- **为什么不行**：`com.airi...EmulatorCheckUtil` 有 `checkFeaturesByAbi/Board/BaseBand/Cgroup/Flavor/Hardware/Manufacturer/Model/Platform` + `getInstalledSimulatorPackages` + `getSensorNumber` + `getProperty`，并配 `CommandUtil.exec("sh")`（`audit/ba-java.md:118`）；dex 字符串命中 `ro.kernel.qemu` / `goldfish` / `test-keys`（`ba-java.md:115`，归属类未验证）；数美 `SmAntiFraud#create/getDeviceId` + 腾讯 Turing `TuringSDK/TuringRiskService/TuringIDService` 构成设备指纹面（`ba-java.md:147`）。native so 关键词矩阵里几乎没有  `qemu/goldfish`（85 列中仅 `libpns` 命中 `Emulator=4`，`kw-hits.tsv`）→ 模拟器检测主要在 Java/SDK 侧，但**同样存在**。
- **失败点/风控点**：多开/分身会改包名、uid、进程环境 → 设备指纹变化 + `getInstalledSimulatorPackages` 命中；一旦被标记，后续所有行为都在「异常设备」上下文里被加权。
- **可替代方案**：真机 + LSPosed（**不伪装环境**）。要并行第二账号，用第二台真机，别用分身/虚拟多开。
- **证据强度**：**静态确证**（检测类与字段存在）；实际拦截未实测。

---

## 方向 11：砍埋点来降低检测面

- **为什么不行**：`userEventUpload` / `roleInfoUpload` 走的是发行 SDK 运营通道（`ba-java.md:100`），而数美/Turing 是**独立风控通道**（`ba-java.md:147,195`）→ 关埋点只丢统计，不减风控特征；反而可能因「角色信息缺失」造成服务端校验差异（`ba-java.md:195`，原文标注推断）。
- **失败点/风控点**：不减少 ACE/数美任何检测点；改 `TechSDK$SdkCallBack` 或上报方法还会改变 SDK 流程（`ba-java.md:99`）。
- **可替代方案**：真正能减的检测面只有三件（`ba-java.md:241,252`）：① 全模块不用 `XposedHelpers.find*`（改 `Class.getDeclaredMethod` + `XposedBridge.hookMethod`）；② 只勾游戏主进程（最小作用域）；③ hook 后清三个 cache。**埋点保持原样**。
- **证据强度**：**静态确证**（通道分离）+ **推断**（缺失导致异常）。

---

## 方向 12：Java 层绕签名 / 证书固定，去抓改游戏协议

- **为什么不行**：dex 里没有 `sha256/...` pin 字面量（0 命中，`ba-java.md:131`），`CertificatePinner` 存在但启用未验证；游戏业务 base url **不在 dex 字符串表**（只有 SDK 域名，`ba-java.md:130`）→ 抓包也拿不到业务域名；业务请求在 IL2CPP 内（`metadata-strings.txt` 中 `UnityWebRequest=159`、`WebRequest=206`）。hook `TrustManager` 只影响 SDK 的 Java 请求，对 native/Unity 流量无意义（`ba-java.md:194`）。
- **失败点/风控点**：绕过了也看不到游戏流量；改 `PackageManager` 签名返回会与 native 侧 `GET_SIGNATURES`/`signature` 关键字面（`kw-hits.tsv`，`libunity.so`）不一致；还会碰 SDK 自己的完整性自检。
- **可替代方案**：只在 SDK 侧做观测——`AiriSgClient.getAAesKey/getAAesIv/sign` 是 Java 可见的 native 接口（`ba-java.md:122-129`），能拿到 SDK 的 AES Key/IV 与签名结果；**游戏业务协议无替代**（要么运行时 hook IL2CPP 内部网络函数，要么放弃）。
- **证据强度**：**静态确证**（无 pin 字面量、业务 URL 不在 dex）；其余**推断**。

---

## 汇总表

| # | 方向 | 证据强度 | 结论 |
|---|---|---|---|
| 1 | 静态 Il2CppDumper | 静态确证（失败行为推断） | 放弃，改运行时按名解析 |
| 2 | 改包重签 / 改 DLL | 静态确证（校验行为推断） | 放弃，改 LSPosed 注入 |
| 3 | Java 层改战斗数值 | 静态确证 | 无入口，改 native stat |
| 4 | 服务端权威项 | 静态确证（校验行为推断） | 只能改本地表现，资源无解 |
| 5 | 关 ACE / 反作弊进程 | 静态确证（重启行为推断） | 放弃；只做最小作用域 |
| 6 | 全局 TimeScale 无上限 | 静态确证（阈值推断） | 放弃；只用游戏自带档位 |
| 7 | 直改内存 stat 表 | 静态确证 + 推断 | 不划算；继续用 hook |
| 8 | 替换 / patch so | 静态确证（校验行为推断） | 放弃；用 Dobby 内存 hook |
| 9 | Frida / 内存搜值 | 静态确证 + 推断 | 不进交付；最多测试机用 |
| 10 | 模拟器 / 多开 | 静态确证（拦截未实测） | 用真机，不伪装环境 |
| 11 | 砍埋点降检测面 | 静态确证 + 推断 | 无效；只做三件减痕动作 |
| 12 | Java 绕签名 / 证书固定 | 静态确证 + 推断 | 拿不到业务流量，放弃 |

## 未验证清单（不要在正文当结论）

1. metadata 头部的改写/加密算法与密钥来源（`ba-hook-survey.md:135`）——决定方向 1 是否有可能「还原头」。
2. `libunity.so` 的 `signature/crc32/checksum/digest` 关键字是否真参与包完整性校验、在哪个时机执行——决定方向 2/8 的失败点是在启动还是首次联网。
3. `ConstCombatExcel` 各风控字段的**默认数值**（`blob.md:36,167` 未取到）——决定方向 6「多少倍算超限」。
4. 数美 / Turing / TapTap Themis / AirSDK 是否**实际初始化**（`ba-java.md:224`）——决定方向 9/10 的实际风险权重。
5. `:GP6Service` / `:GP7Service` / `:GP7Worker` 被 kill 后是否被系统/ACE 重新拉起——决定方向 5 的失败模式。
6. 「服务端按自己的模型重算并回滚」的具体判据（`BattleResult` 处理逻辑在 native）——方向 4 的失败点为推断。
