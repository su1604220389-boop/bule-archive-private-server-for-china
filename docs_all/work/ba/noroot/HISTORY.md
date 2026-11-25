# HISTORY · 免 root 静态改包重定向 —— 历史证据重建

> 生成：2026-11-16 ｜ 性质：只读审计，未连服务器、未连手机、未改任何既有文件 ｜ 产物仅本文件
> 待验证命题：**「BA 国服 APK 不能在没有 root 的情况下，通过静态修改把服务器改成我们的服务器」**
> 纪律：每条结论标 `文件:行号`；找不到写「未找到」；**不补、不圆、不替历史辩护**。

---

## 0. 证据分级（本文统一使用，替换文档自带的 A/B/C）

| 档 | 定义 |
|---|---|
| **[实测]** | 有一手输出（logcat / exit-info / 抓包 / 字节 / sha / 计数），变量隔离干净，可复算 |
| **[实测-弱]** | 有一手输出，但变量未隔离 / 观测指标无判别力 / 结论依赖单一指标 |
| **[推断]** | 有静态证据（反汇编、ELF、metadata、源码），**没上机** |
| **[一句话]** | 只有结论句，无方法、无原始输出、无中间量 —— **不可作为行动依据** |

> 这不是形式主义。`report\63:296-315` 有一整节叫「提出→被推翻结论汇总（方法论留档）」，开头就写
> 「**本节的价值高于任何单条技术结论**。它记录的是：一个看起来成立的推论，是怎么被更硬的证据杀掉的。」

---

## 1. 时间线

| 阶段 | 时间 | 干了什么 | 出处 |
|---|---|---|---|
| ① 首次改包 | 11-13 上午 | E28/E30/E31：libunity 证书补丁 + 删 `__tpinfo` + 改 `sdk_url` | `ba-pitfalls.md:13-18`、`:163` |
| ② 容错矩阵 | 11-13 白天 | E32…E44 一次性铺开，测「改什么会死」 | `ba-pitfalls.md:46-57`、`ba-gateway-host.md:77-89` |
| ③ 地址溯源 | 11-13 下午 | 静态全量扫（dex/so/metadata/assets/6227 表包）+ 改 `Hosts`/`ResUrls`/`gameUrl` | `ba-gateway-host.md:17-45`、`:91-101` |
| ④ 注入链 | 11-13 晚→深夜 | libil2cpp 代码洞 + `DT_INIT` + GOT 改写（E63/E64） | `ba-pitfalls.md:167-244`、`report\02` |
| ⑤ DNAT + 证书 | 11-14 凌晨起 | 改判：不用改包，用 DNAT 兜底 + 证书 | `report\19:7-32`、`report\06` |
| ⑥ 协议层 | 11-14 全天 | 转去打 `Account_Auth` 等协议（与本议题正交） | `report\63` |
| ⑦ 补丁方案评估 | 11-14 05:2x | report 51-55 五份并行评估「绕过登录」的可行性 | `report\51`…`report\55` |

**一句话时间线**：
> 11-13 上午「改包 → 重签 → 装机 → **能进游戏**」；白天系统化试错，得出"能改/不能改"清单；
> 下午发现**网关域名在 APK 里 0 命中**（整条静态路线的真正断点）；
> 晚上转向"不改包改内存"，代码能跑起来但**改不到网络层**；
> 11-14 起放弃静态路线，转 DNAT（**需 root**）—— 这就是现方案的历史来由。

---

## 2. 重打包台账

### 2.0 三条必须先说清的前提

1. **没有逐版装机日志。** `report\57:387`：「`res.apk` / `repack_e35..e42` 的**装机后表现** ｜ 只有 `E38 45s+`、`E42 能进主程序` 这类结论性描述，**无逐轮日志**」。
2. **没有游戏包的 `pm install` 原文。** `report\57:138`：「**缺失**：工程内没有游戏包的 `pm install` 原文日志；`fix-crash.md:59` 那条 `pm install -r -d → Success` 装的是 AzusaBA 模块 3.6 MB，**不是游戏**」→ 故判「**间接确证**」（`report\57:140`）。
3. **APK 本体已被删**（腾 2 GB 给 `apksigner`），只剩 `.idsig`。定性推断链：`e0/e1/e2/e0b/a_signed.apk.idsig` 各 16,750,059 B；用 `Probe13.apk`(21,078 B)→`.idsig`(5,611 B) 定标「固定头 ~5.4 KB + **32 B/4 KB 页**」⇒ 反推 **~2.143 GB APK = 游戏本体**；交叉印证设备 `base.apk` = 2,126,786,978 B、mtime 11-13 18:38（`report\57:21`、`:134-135`、`:141`、`:331`；`report\13:27`）。

### 2.1 台账（E 系列，按代号）

| 代号 | 改了什么 | 出处 | 装机表现（原文） | 档 |
|---|---|---|---|---|
| **E28** | `repack_game.py`：libunity `0xA53A38`（`f803002a`→`f8031f2a`）+ 换 `libmain.so` + 加 `libdg.so` | `report\57:326` | 无记录（标"已废弃"） | **[推断]** |
| **E30** | 同上 libunity 补丁 **+ 删 `__tpinfo` 5 个** | `ba-pitfalls.md:13-18` | 「**这一版不崩，能进游戏**」；`:163`「BA_E30.apk 2,126,498,053 B，已签名，**已安装，不崩**」 | **[实测]** |
| **E31** | libunity 补丁 + `assets/SDKConfigSettings.json` 的 `https://sdk-api.yostar.cn` → `http://127.0.0.1:8080` | `report\57:327` | 「部分有效（思路被后续继承）」 | **[实测]** |
| **E32 / E32b / E34** | 换资源（`res.apk` 的 `resources.arsc`+`res/`）、修 arsc 对齐与 `0xd935` extra pad | `report\57:328` | 「能进主程序、文案生效」 | **[实测-弱]** |
| **E35** | 资源 + **`libairisgcore.so` 整库替换**（自编译假 so，NEEDED 干净、无人依赖） | `ba-pitfalls.md:51`、`ba-gateway-host.md:25` | **SIGBUS**（`reason=2 SIGNALED status=7`），无 tombstone | **[实测-弱]** |
| **E36** | libunity 4 字节证书补丁（= E38/E42 的真正基底：`repack_e38.py:3` / `repack_e42.py:3` 注释 `BASE='/storage/emulated/0/Download/scan.apk' # E36`） | `ba-pitfalls.md:50`、`ba-gateway-host.md:55` | **SIGBUS**（同上） | **⚠️ 冲突，§8.1** |
| **E38** | **纯填充字节翻转（无注入）**：`libil2cpp.so` 文件 `0x10260000` 翻 1 字节（文件尾 1600 B slack、不在任何 LOAD 段）+ 还原原厂 libunity + arsc STORED 首条 | `ba-pitfalls.md:57`、`report\57:328`（**该清单漏列 `repack_e38.py`**） | 「**正常启动（45 s+ 存活）**」 | **[实测]** |
| **E39 / E40 / E41** | **新增 `classes3.dex`**（哪怕 660 B 空类） | `ba-pitfalls.md:52` | 「**卡在 Android 启动界面**」；「Unity 未加载；**与 ACE 无关**（ACE 是 8~10 s 后杀）」 | **[实测-弱]**（归因是猜的） |
| **E42** | **官方资源基线 + 原厂 `libunity` + 我们的 `res`（卡密文案）+ `assets/SDKConfigSettings.json`（`sdk_url` 指本机）+ 删 `__tpinfo`** | `ba-pitfalls.md:149-151` | 「**能进主程序、SDK 卡密登录通过、停在「认证服务器拒绝了请求」（网关仍是官方）**」2,126,782,882 B | **[实测]** |
| **E43** | **重编 `classes.dex`**（baksmali→smali 回编） | `ba-pitfalls.md:53` | 「卡启动界面」 | **[实测-弱]** |
| **E44** | **重编 `classes2.dex` 改一个 `const-string`**（`TechSDKUnityBridge$1.val$gameServerUrl` → `http://127.0.0.1:8080/api/state`） | `ba-pitfalls.md:54` vs `ba-gateway-host.md:84` | **两处冲突**：前者「首次启动成功（E44），但之后同批 APK 全部卡启动界面」；后者「✅ 正常启动、SDK 登录成功」 | **⚠️ 冲突，§8.2** |
| **E63** | libil2cpp `0xf2c2410` 写 ARM64 代码 + 改 PLT 首指令为 `B`；代码内 `dlopen+dlsym` | `ba-pitfalls.md:171-172` | 「✅ 不触发 ACE，进程正常启动」「✅ 可用（`alive=24049`）」 | **[实测]**，但**不是 APK**，是 root 原位替换（`report\57:301`） |
| **E64** | GOT 改写 + 真函数指针持久化（RW bss） | `ba-pitfalls.md:184` | 「从『被官方拒绝』变成『**超时**』」 | **[实测-弱]**，后判**零判别力**（`report\10:61`、`report\13:123`） |

**更早的（非 E 系列）**：
- `repack.py` + `repack4..10.py`（8 个）：**把 LSPosed 模块塞进游戏包**（`classes.dex`+`libdhook.so`）→ 已废弃（`report\57:325`）。
- `repkg{1,2,3}.py` + `scan_axml.py`：等长改 AXML 包名 `com.RoamingStar.BlueArchive` → `com.gm.bluearchiveprivate12`（白名单索引 146–170，不动微信回调类）（`report\57:329`）。改包名 = SIGBUS（`ba-airisdk.md:244`，转引 `report\01:183`）。
- **磁盘上 `repack*.py` 实际 19 个**（含 57 号清单漏掉的 `repack_e38.py`）。

**合计**：有代号的重打包 **≥15 版（E28–E44）**；**能查到"装上去之后怎么样"一句描述的只有 9 版**。
**台账缺口三处**：`repack_e38.py` 存在但 `report\57:328` 漏列；E36 无独立条目（却是 E38/E42 的基底）；**E44 在 `report\57` 全文 0 命中**。

### 2.2 台账里最重要的三条

**事实 A：重签后的 APK 能装、能启动、能进主程序。**
E30（`ba-pitfalls.md:18`）、E38（`:57`）、E42（`:150`）三版独立证据。E42 甚至跑到 SDK 卡密登录成功、停在游戏自己的网关拒绝弹窗。

**事实 B：真正杀进程的是「改 .so 代码 / 加新 .so / 加新 dex」，不是「签名变了」。**
`ba-pitfalls.md:50-54` 矩阵：SIGBUS 只出现在「libunity 4 字节」「libairisgcore 整库替换」两行；「卡启动界面」只出现在「新增 dex / 重编 dex」三行。**没有任何一行是「只重签、内容不变」。**

**事实 C：静态改 APK 内文件并生效，已被证明可行。**
`assets/SDKConfigSettings.json` 的 `sdk_url` → `http://127.0.0.1:8080` → **SDK 6 条请求全部打到我们**（`ba-gateway-host.md:9`、`ba-pitfalls.md:56`、`report\01:124`、`report\54:380-382`「全项目唯一被证明改了立刻生效…无需改代码」，但「**改它要重打包 APK**」）。
⇒ **「静态改包改不动服务器地址」在 SDK 这一层是错的——改得非常成功。问题只出在游戏网关那一层。**

---

## 3. 每次失败的确切原因（三档）

### 3.0 先看一条硬约束：这些"失败"的原始日志基本都不存在

`report\02:221-223` 原文：
> ⚠️ 先说清楚：`bapatch/` 下**没有 tombstone、没有 logcat 原文、没有 `.out`**。只有 `sdk.log`（318 行）和 `relay.log`（1 行 36 字节）。
> **所有 fault addr / pc / signal 都在 `audit/ba-pitfalls.md` 的表格里（二手记录）。**

`report\57:383-389` 再次确认整节「本地无证据」。
`report\DEADENDS.md`：tombstone 只以「**没有**」出现（`:15` 无 tombstone、`:31` 连 tombstone 都没有）。
**整个项目唯一有「时间线 + 日志内容 + 回滚」三件套的真机实验，只有 `libil2cpp_probe` 那 2 分 13 秒，而且失败了**（`report\57:14-16`、`:35-53`、`:301`）。

### 3.1 失败清单

| # | 失败 | 确切原因 | 档 | 出处 |
|---|---|---|---|---|
| 1 | `libairisgcore.so` 整库替换（E35） | 归因「ACE 对 so 做磁盘哈希 / 校验『文件是否被动过』」 | **[实测-弱]** 只有 `exit-info status=7` 一行，无 tombstone；**未做「清 ACE 记账后重试」的对照** | `ba-pitfalls.md:51`、`DEADENDS.md:20-26` |
| 2 | `libunity.so` 4 字节补丁（E36） | 归因「ACE 磁盘哈希钉死」 | **⚠️ 与 E30 直接冲突** | §8.1 |
| 3 | 新增 `classes3.dex`（E39/E40/E41） | 「卡 Android 启动界面（Unity 未加载）」；归因「**与 ACE 无关，是启动链不接受 dex 结构变化**」 | **[推断]** —— 这句只因「ACE 是 8~10 s 后杀而这里 Unity 都没加载」的时间差推出，**无任何 ACE 侧观测** | `ba-pitfalls.md:52`、`DEADENDS.md:36-41` |
| 4 | 重编 `classes.dex`（E43） | 同上 | **[推断]** | `ba-pitfalls.md:53` |
| 5 | 重编 `classes2.dex`（E44） | 无定论 | **⚠️ 两文档冲突** | §8.2 |
| 6 | 改包名 | 「包名被校验，实测 SIGBUS」 | **[一句话]** —— 唯一出处 `ba-airisdk.md:244`，其余全是转引；`DEADENDS.md:48` 只写「SIGBUS」一词，无字段无日志 | `report\01:183` |
| 7 | 加新 `.so` / 改 `libmain` `NEEDED` | 「无日志闪退（ACE 直接杀进程）」 | **[实测-弱]** 无日志 ⇒ 无法区分「ACE 杀」和「linker 拒绝加载」 | `ba-pitfalls.md:10`、`DEADENDS.md:28-34` |
| 8 | 改 `files/Hosts`（裸串） | **不是"文件不被使用"，是"格式不合法被丢弃"**。真实结构 `u32 ver｜u32 count｜loop{u8 hostlen,host,u32=1,u8 urllen,url,u64,u8 flag}` | **[实测]** 已用正确格式复现 | `report\10:31`、`DEADENDS.md:80-86` |
| 9 | `Hosts` 写明文 http URL | **不是 scheme 问题，是"候选项没被选中"**：`ss -tnp` 全程无 `:80` 连接；`Hosts` 被重写成 127 B、我们的 URL 原样保留，仍连官方 `:443` | **[实测]** 变量隔离干净 | `DEADENDS.md:96-102`、`report\06:237` |
| 10 | 调大 `Hosts` 的 u64（+0x100000） | 客户端原样保留但 `conn120=0`（6 次采样）⇒ u64 不是"谁说了算"的开关 | **[实测]** | `DEADENDS.md:104-110` |
| 11 | uid 级 443 REJECT（只断不导） | 「state 拿不到时客户端**直接报网络错，不回落**候选项；`Hosts` 是**写穿缓存**，不是 fallback」 | **[实测]** | `DEADENDS.md:120-126`、`report\06:253` |
| 12 | 改 `/system/etc/hosts`（shell ns bind） | **真因不是 HTTPDNS**，是 app 解析由 **netd(pid 1937)** 代答，netd 在**另一个 mount namespace** | **[实测]** 真因已定位（旧归因作废） | `DEADENDS.md:128-134`、`report\10:89` |
| 13 | `nsenter` 进 netd ns 改 hosts | rc=0 且 ns 内可见，但 `ping` 仍官方 IP。归因：DNS 被 **VPN/Clash tun（`vgate0`）** 接管 | **[实测-弱]** 归因是排除法 | `DEADENDS.md:136-142`、`report\06:186-194` |
| 14 | 改 libil2cpp 的 `getaddrinfo`/`connect` PLT/GOT（v1–v10） | **这两个导入在 libil2cpp 里调用点 = 0**。346 万条 `BL` 全段扫描：`getaddrinfo@plt(0xf2c1000)`=0、`connect@plt(0xf2c1060)`=0，其它 65 个桩共被调 116,219 次 | **[实测]** 强 | `DEADENDS.md:164-170`、`report\00:348`、`report\02:23` |
| 15 | 硬编码 GOT 偏移 | 偏移表读错一格（`0x13d94d0`=`gettimeofday` vs `0x13d94d8`=`getaddrinfo`） | **[实测]** 已三重验证 | `DEADENDS.md:172-178`、`report\02:272-273` |
| 16 | 代码洞 `adr` 指向 `.globl` 符号 | `adr` 取到 0（未链接 `.o` 里全局符号留 imm=0）→ `fault addr=0x1c20` | **[实测]** | `ba-pitfalls.md:223-244` |
| 17 | 运行时 `mprotect` 写 libc 代码页 | SELinux `execmod` 拒绝 | **[实测]** | `ba-pitfalls.md:176`、`DEADENDS.md:204-209` |
| 18 | 写 libil2cpp 自身 GOT | `SIGSEGV/SEGV_ACCERR(write)`；`.got.plt` 整段落 `PT_GNU_RELRO [0xf2c4000, 0xfbb4000)` | **[实测]** | `ba-pitfalls.md:194`、`DEADENDS.md:212-218` |
| 19 | 把 `.rela.plt` 的 `JUMP_SLOT` 改成 `RELATIVE` | 链接器 abort，`status=6 (SIGABRT)`，秒退。**原文明确「失败原因未定」**，并自评「结构本身是对的…**不是纯死路**」，给了两个待查点 | **[实测-弱]** 全清单唯一自认"未定"而非"否定"的条目 | `DEADENDS.md:244-254` |
| 20 | E64「超时」 | **无定论**：「超时」至少有四种成因（地址写错 / 端口不通 / 没人应答 / TLS 挂自签证书），**没有一次 TCP 是否到达的旁证**；且 19:57 起客户端在 0.3 s 自杀循环 | **[实测-弱]** 后被评为**零判别力** | `report\10:61`、`report\13:123`、`report\00:70` |
| 21 | 改 `ResUrls` 劫持 CDN | `ResUrls` 是**资源 CDN 根**，与 API 网关无关；且 9444 是自签证书，TLS 先挂 ⇒ 「cdn.log 没请求」**不可解释** | **[实测-弱]** 判为"从未被有效测试" | `report\10:33`、`DEADENDS.md:152-158` |
| 22 | 改 `gameUrl`（E44） | 登录链照常走完，`/api/state` 命中 **0** ⇒ `gameUrl` 不参与登录 | **[实测]** 变量单一，有计数指标 | `ba-pitfalls.md:132`、`ba-gateway-host.md:91-95`、`report\10:35` |
| 23 | 改 `global-metadata.dat` 的网关 RSA 公钥 | **从未实施**（产物齐全、自测通过、无设备 push 记录） | **[推断]** | `report\57:113-127`、`report\30:334-338` |

### 3.2 「未知」清单（历史上根本没做的）

| 项 | 状态 | 出处 |
|---|---|---|
| ACE `initialize()` 对 `sourceDir/splitSourceDirs` **具体算什么** | **未验证** | `anticheat-full.md:150`、`report\01:336` |
| 数美/nirvana 现算 `signatures[0]` SHA1 的**用途**（自校验 vs 已装应用指纹） | **未验证** | `anticheat-full.md:91-93`、`:153` |
| ACE 是否校验 `global-metadata.dat` | **未验证** | `report\63:340`；`report\30:323`「今晚没有证据」 |
| ACE 是否有**内存 CRC**（不只磁盘哈希） | **未知** | `report\18:210`、`:234` |
| 客户端**从哪读 metadata**（APK 内 zip 条目 vs `files/il2cpp/Metadata/` 外部副本） | **未验证**，但**有一条命令就能验的入口** | `report\52:494-524`、`report\30:336`、`report\21:1116` |
| `res/xml` `networkSecurityConfig` 是否可用来信任用户 CA | **未验证**：本 APK **根本没有这个属性**，`res/xml` 只有 `filepaths/http/sdk_file_provider_paths/...` | `DEADENDS.md:340-346`、`report\INDEX:243` |
| ACE 的块编码/解码算法（决定哪些函数离线可改） | **未逆向**，被称「目前唯一还有价值的静态缺口」 | `report\55:412-413` |
| `files/Hosts` 里 u64 字段的语义 | **未定**（有具体假设，见 §5.5） | `report\10:170`、`report\56:996` |

---

## 4. ★ 专问：「签名变了导致被杀」有没有直接证据？

### 4.1 结论：**没有。而且现有实验表直接反对。**

**反证（三条，都是实测）**：E30「不崩，能进游戏」（`ba-pitfalls.md:18`）、E38「正常启动 45 s+」（`:57`）、E42「能进主程序、SDK 登录成功」（`:150`）。三版都是**重打包 + 重签 + 装机 + 跑起来了**。

**项目从未做过「只改签名、其余字节不动」的对照实验。**（全库 grep，**未找到**）

### 4.2 「签名/路径会被校验」的来源只有一处，而且是推断

> `com/ace/gshell/AceApplication.java:50-58` 传 `packageName / nativeLibraryDir / sourceDir / filesDir`，反射取 `splitSourceDirs`
> → ACE 拿 `sourceDir + splitSourceDirs` 在 native 做 APK 完整性/路径校验。「**这是最现实的风险点**」
> —— `work\ba\audit\anticheat-full.md:111-112`

措辞是「**最现实的风险点**」。同一份文档的未验证清单里明写着：`sourceDir` 具体算什么 = **未验证**（`:150`）；`signatures` 用途 = **未验证**（`:153`）。
`report\17:396`（R6）把「签名重打包被 ACE 的 `sourceDir` 完整性面抓到」评为**风险概率"中"**——**风险评估，不是实验**。

**唯一真正被实测的「改包即闪退」，归因是 `__tpinfo`，不是签名：**
> 「**必须删 `assets/__tpinfo.*`（5 个文件）** ｜ 改过 `libunity.so`/`libmain.so` 后，游戏启动即闪退，**没有任何崩溃日志/tombstone** ｜ 删 `__tpinfo.tsc/.tsc.sig/.tsd/.tsd.sig/.tp`，完整性校验整段跳过」
> 「删除 `__tpinfo` 后 ACE 不再校验文件哈希 —— **这是所有改包能跑的前提**」
> —— `ba-pitfalls.md:9-11`

⚠️ 注意：`__tpinfo` 在 `DEADENDS.md`、`report\30`、`report\56`、`report\57` **全部 0 命中**。这条最关键的机制，只存在于 `ba-pitfalls.md` 与转引它的 `INDEX:45` / `report\01:122` 里。

**而且 `__tpinfo` 那 5 个文件本身没有落盘**（`report\01:505`、`ace-ipc.md §5` 第 3 条：「工作区只剩 slim.apk / dexonly.apk，7 个 `__tp*` 资源未落盘」）——**意味着这条机制无法被复核。**

### 4.3 SIGBUS 的替代解释（现有最强）：ACE「记账」污染

> 触发过一次异常改动（E43 的 dex）后，**后续任何版本**（包括之前能跑的 E42）启动都被 `kill(SIGBUS)`。
> 复位：删 `files/{ace_shell_di.dat, shell_cache, ano_tmp, data/app}`
> **这条解释了「同一版 APK 有时能跑、有时被杀」的全部现象——不是概率，是历史判定被记住。**
> —— `ba-pitfalls.md:59-70`；`ba-gateway-host.md:88-89` 同义

**这条直接命中 E30 vs E36 的矛盾**，项目自己也发现了：

> §4.2 已证明判定会持久化。你现在的记录里出现了**同一改法"有时活有时死"的矛盾**（E30 打 libunity 补丁"不崩能进游戏"，E36 同补丁 SIGBUS）——**这大概率是记账污染，不是概率**。
> —— `report\00:230`

并把它列成**待做实验**：
> | 3 | E30（libunity 补丁活着）vs E36（同补丁 SIGBUS） | **复位 ACE 记账后重跑一次 E30 的改法** |
> —— `report\00:327`（§5.4「需要真机确认的 3 个硬矛盾」）

**该实验的执行记录：未找到。**

### 4.4 还有一条污染源，历史几乎没算进去

> `reason=2 SIGNALED status=9` + `OplusFlexibleDCSManager: startMiniWindow … group_pkg=com.RoamingStar.BlueArchive`
> **status=9 = SIGKILL = 系统小窗/内存回收，不是 ACE（ACE 用 SIGBUS/7）**
> —— `ba-pitfalls.md:99-107`、`DEADENDS.md:569-575`

⇒ **历史上若干"启动失败"样本根本不是 ACE 杀的。** 归因时必须先分 `status=7 / 9 / 6`。

---

## 5. ★ APK 里哪些服务器地址是硬编码的

### 5.1 总表

| 字符串 | 载体 | 硬编码? | 改它要重签? | 改了有没有用 | 出处 |
|---|---|---|---|---|---|
| **`sdk-api.yostar.cn`** | **`assets/SDKConfigSettings.json`**（明文 JSON，`{sdk_url,sdk_pid:CN-BA,channel:official}`） | ✅ **是** | **要**（assets 是 zip 条目） | ✅ **有用**：改 `http://127.0.0.1:8080` → SDK 6 条请求全到我们 | `ba-gateway-host.md:9`、`ba-pitfalls.md:56`、`report\57:327`、`report\54:374-382` |
| **`http://test-ba.yostar.net:5210/api/state` ×3** | `global-metadata.dat` stringLiteralData，key `0xB5`，@`0x000C1732`（另有记 `0xC172B/0xC1756/0xC1781`） | ✅ **是，40 字符** | 取决于 metadata 读取路径（§5.4） | ⚠️ **可以改（等长），但"改了是否被用"从未实测** | `report\52:333,433,474-484`、`report\54:23,80,420,593` |
| **`state-api.bluearchive-cn.com`** | **找不到**：metadata + libil2cpp.so，**256 个单字节 key × ASCII+UTF-16LE 全扫 0 命中** | ❌ | — | 无对象可改 | `report\54:22,84-92,419,592`、`ba-pitfalls.md:130` |
| 同上（补扫） | metadata：单字节 XOR 全 256 key × 全位置 + 周期 ≤8 keystream | ❌ 0 | — | 同上 | `report\11:165-173` |
| 同上（补扫） | **`libil2cpp` 270 MB 全文件**，周期 `L=1..43` 向量化 | ❌ 0 | — | 同上 | `ba-gateway-host.md:44`、`:75` |
| **`gsqc-api.bluearchive-cn.com`** | 同上手段 | ❌ 0 | — | 同上 | `report\54:592`、`report\11:167-171` |
| **`gs-api.bluearchive-cn.com`** | 同上 | ❌ 0 | — | 同上 | 同上 |
| **`static.bluearchive-cn.com`** | ① 服务端下发 `AddressablesCatalogUrlRoots`（`/api/state`）② `LocalizeConfig.txt` 的 `ResUrls`（运行期写入）③ `webseasonexceltable.bytes` 里 1 处**活动页 Web 链接**（非 API） | ⚠️ 只有 ③ | 需重打包 | 与登录网关无关；可接管 CDN（正交） | `ba-gateway-host.md:24`、`report\54:187,235-244,259` |
| **`prodm39`** | 无载体，0 命中。是 `/api/state` 下发的一条 path 段 | ❌ | — | 只能由应答提供 | `report\54:22,137` |
| **`example.com`** | **原包里没有**。我们自己的域名（真证书）：出现在注入桩字面量、证书 SAN、nginx | — | — | 是"要写进去的值"不是"被改对象" | `report\57:108`、`report\22:378`、`report\54:480` |
| **`GameMainConfig.ServerInfoDataUrl`**（**值本身仍是密文**） | `assets/bin/Data/*.assets` 内的 **914 B 加密 TextAsset** | **⚠️ 极可能是** | 要 | **从未定位/解密** | §5.3 |

### 5.2 一处必须先纠正的扫描口径

`report\54:100-113` 自我声明：`md_deob.bin`（report 51 的产物）里 `LocalizeConfig`/`IsLocalize`/`ResUrls` **全为 -1**，
> 「**不要把 `md_deob.bin` 当作 metadata 等价替代去下『某字符串不存在』的结论**」

⇒ §5.1 的所有「0 命中」只在**原始 metadata + 原始 .so** 上成立。任何基于派生/deob 文件的否定**不成立**。

### 5.3 ★★ `GameMainConfig`：地址载荷的候选载体（历史上被主动降级，从未跟进）

**外部逆向实录（`report\56:880-997`，看雪 thread-291406，2026-05-30，[亲验]）**：
- 样本是 BA 日服/国际服，**Unity 2021.3.56，il2cpp 27** —— 与本仓库客户端 **`Unity 2021.3.56f2` 同一版本**（`report\56:919`、`INDEX §1.1`）。
- 原文：
  > `GameMainConfig.ServerInfoDataUrl = https://yostar-serverinfo.bluearchiveyostar.com/r92_69_….json`
  > `GameMainConfig` 大小为 **914B，是密文**；用 `CreateKey('GameMainConfig')` **可以非常轻松的成功解密**（`report\56:974`、`:978-979`）
  > 密文特征：**奇数字节严格周期 8**（`23 06 72 57 23 06 72 57 …`），符合 UTF-16LE 明文 + 8 字节 key 循环异或（`report\56:985`）
- **解密算法已全文给出**：`report\56:1060-1097`
  ```
  create_key(name) = MT32(xxhash32(name)).NextBytes(8)
  xor_bytes(name, data): 每 4 字节取 mt.Next() 一个小端 u32，逐字节 ^
  自检真值: create_password("Excel.zip") == "/wy5f3hIGGXLOIUDS9DZ"
  ```

**国服客户端里这两个字段名确实存在（[实测]）**：
> `report\59:796-808`（§12「用反向搜索法重验所有『字符串 0 命中』的否定结论」，方法=**候选明文 × 256 key 反向搜**）
> - `GameMainConfig` → **存在**，`0x0006FEF5` / key `0x8F`
> - `ServerInfoDataUrl` → **存在**，`0x00095EC7` / key `0xBD`

**扫描口径的缺口（我本人核过 zip 清单，一手）**：
- `work\ba\audit\ba-apk\zip_listing.txt`：41,312 行；`assets/` 共 **40,410** 条，其中 `assets/bin/` **565** 条。
- `assets/bin/Data/` 里是 `sharedassets1.assets`、`boot.config`、`global-metadata.dat` 等，且**大量 Unity 数据文件被改名成 32 位哈希**（如 `a430f55fcf139914a94e8cab58ebaa96`）。
- **`GameMainConfig` 在整份清单里 0 命中** —— 它是 `.assets` 文件**内部**的 TextAsset，不是独立文件。
- 而历史扫描是：`ba-pitfalls.md:130`「assets … **ASCII+UTF-16 全扫**」（明文扫描，打不穿 XOR）；`ba-gateway-host.md:44` 的周期 1..43 扫描**只对 `libil2cpp` 做过**。
- `report\11:200` 自己留了这个缺口：「你们的 assets 扫描 0 命中（**但需确认覆盖了 level0/sharedassets/设备侧 11 GB 资源**）」。

**项目当时怎么处理的（关键）**：
> 「**但我们已经不需要这个值了**——`report/31` 已从真实响应里拿到 `gsqc`/`state-api` 全套 URL。**这条的价值是"机制解释"，不是"要取新情报"**。」
> —— `report\56:991`

⇒ **这是全项目最值得复核的一次"降级"**。因为问题从来不是"值是多少"，而是**"值从哪来"**——
而 `ba-gateway-host.md:103-105` 把「客户端第一次连接网关前，那个主机名是从哪来的」称为**当前唯一未解的问题**，`report\01:286-288` 同义。
`report\56` 恰好给了它一个具体答案（`GameMainConfig.ServerInfoDataUrl`），却被判为"不需要"。

**附带收益**：`report\56:992-997` 把 `files/Hosts` 的二进制结构对上了 `ServerInfoData.ConnectionGroups[]` + `OverrideConnectionGroups{}`，
并给出**D-10/D-12「Hosts 写进去但不被选中」的第一个有指向性的假设**：
> `OverrideConnectionGroups` 是 `Dictionary<string,…>`，**键是"版本串"**。我们改 url 但没改键 ⇒ 客户端拿当前版本去查，查不到就回落官方默认。
> **可检验预测**：`Hosts` 里那个 `u64` 很可能就是**版本键的编码**，必须改成"当前版本能命中的值"，而不是随便加 `0x100000`（D-12 干过的事）。

### 5.4 `global-metadata.dat` 的两条可能读取路径（决定"要不要重签"）

| 路径 | 后果 | 出处 |
|---|---|---|
| APK 内 `assets/bin/Data/Managed/Metadata/global-metadata.dat`（zip 条目） | **必须重打包 + 重签 + 卸载重装** | `report\30:336-338`、`report\52:502` |
| **外部存储 `.../files/il2cpp/Metadata/global-metadata.dat`（设备上确实存在！）** | **一条 `cp` 就够，不需要重打包、不需要重签、不碰 ACE 的 APK 完整性面** | `report\52:503-507`（引 `report\21:1116`，同目录还有 `il2cpp/unity.ver`） |

`report\52:509`：「**一条命令就能验证**（不改任何东西，只读）」。
`report\52:523-524`：「`report\11:282` 早写过同样判据…**但从未真正跑过，这是整条路线的第一个 5 分钟**」。
`report\52:626`、`:638` 把它列为**性价比第 1** 的动作。
**执行记录：未找到。**

### 5.5 ★ `Servers` 数组是不是来自 `state-api/api/state` 的响应？

**是，逐字节对得上。**

- 原始响应：`report\98:361` — `GET https://state-api.bluearchive-cn.com/api/state` → 161 B，十六进制 `7b 22 53 65 72 76 65 72 73 22 3a 5b …`（`{"Servers":[` 的 ASCII）
- `report\100:319`：`Servers = ["https://gsqc-api.bluearchive-cn.com/api/","https://gs-api.bluearchive-cn.com/api/"]`，标注 ★「业务 API 的两个候选基址」
- `report\01:154`：`state-api` 下发 `Servers[]`（出处 `ba-pentest.md:154-158`）
- `report\24:196-230`：`StateServerResponse` ≈ `{"Servers":[string…],"State":int,"Msg":string}`；`GetApiServerInfo` 是**迭代器**（`<i>5__4` 下标、`<isLive>5__3` 存活标记）⇒ **按 `Servers` 逐个探测哪台活着**
- `report\24:224`、`report\INDEX:110`：疑似需要 **≥2 个元素**做故障切换

**⇒ 推论**：把 `gsqc-api` 写死进 APK **没有对象可写**——它是服务器给的。
`report\54:419-422` 原文：「改本地文本文件无法改变 API 主机，因为**文件里根本没有这个字段，代码里也没有这个字符串**」。

**唯一有意义的杠杆是控制 `state` 那一跳的上游。** `report\10:148` 把它列为「理论收益最大的一击」：
> ⑦ 拦截 `/api/state` 那一条请求（控制候选列表的来源）… A5 只证明 `gameUrl` 不参与登录，**没有**测「`/api/state` 的响应体被改后会怎样」。

### 5.6 ⚠️ 一条与此冲突的实测（必须并列标出）

> **[D-17] 删掉 `Hosts` 看客户端是否重建**
> `rm -f .../files/Hosts` → 启动 → 点一下 → 30 s 后 `ls` → `No such file or directory`（**没有被重建**）
> ⇒ 客户端从头到尾**没有请求过 state**。此前「客户端会请求 state」的 M3 模型（`report\11:201`）因此作废。
> ⇒ **网关入口不是 state-api**（0.3 s × 90 s 采样 666 行全指 gsqc）
> —— `report\DEADENDS.md:144-150`、`report\06:309-314`、`report\19:10`（「✅ **已纠正**：是 `gsqc-api`，不是 `state-api`」）

**冲突**：HAR 抓包里 `GET state-api…/api/state` 确实发生过（`report\98:117` 12:34:42.250 → 200/161 B；`report\99:46` 15:42:23.821 → 200/161 B；`report\100:19` 标 **[确证]**）。

**我的判读（[推断]）**：`rm Hosts → 不重建` 只能证明「Hosts 没被写」，不能证明「state 没被请求」。
这与本项目自己总结的第 2 号坑（「把『格式不合法被丢弃』当成『该文件不被使用』」，`report\10:159`）是**同一类错误**——用"写的副作用不存在"反推"读的行为不存在"。
更可能的解释：官方当时是**维护态 `State:1`**（`report\98:418`、`report\100:19`），客户端拿到 `State:1` 后不往下走、也不写缓存。
⇒ §5.5 的结论成立，但「客户端不问 state / 入口是 gsqc」这条 **[实测-弱] 需重测**。

---

## 6. 「为什么静态修改不可行」——完整逻辑链 + 断点

### 6.1 历史链条（按文档原样串）

```
L1. 改包 → 重签 → 装机 → 能启动            ← [实测] E30/E38/E42
L2. 静态改 APK 内文件并生效                ← [实测] sdk_url（E31/E42）
L3. 但"游戏网关域名"在 APK 里 0 命中        ← [实测] 多方法独立证伪  ← ★断点
L4. 退而改 libil2cpp 的 getaddrinfo/connect
      → 这两个导入调用点 = 0               ← [实测] 346 万条 BL 扫描
L5. ⇒ 网络层在 libunity
      → libunity 的 connect GOT 已解析到 libc 0x74df8c9028   ← [实测]
L6. libunity 被指"ACE 磁盘哈希钉死，改 4 字节即 SIGBUS"         ← ⚠️ 矛盾 + 未被隔离
L7. ⇒ 不能改网络层 → 静态路线死                                 ← [一句话]
```

| 环 | 出处 | 档 |
|---|---|---|
| **L1** | `ba-pitfalls.md:18`（E30）、`:57`（E38）、`:150`（E42）、`:163` | **[实测]** |
| **L2** | `ba-gateway-host.md:9`、`ba-pitfalls.md:56`、`report\01:124`、`report\54:380-382` | **[实测]** |
| **L3** | `ba-pitfalls.md:130`、`report\11:165-173`、`ba-gateway-host.md:44,75`、`report\01:198-202`、`report\54:22,84-92,592` | **[实测]**，**但覆盖有缺口（§6.2）** |
| **L4** | `DEADENDS.md:168`、`report\00:348`、`report\02:23`、`ba-pitfalls.md:209-210` | **[实测]** |
| **L5** | `ba-pitfalls.md:211`（`0x13d95d8` → `0x74df8c9028`） | **[实测]** |
| **L6** | `ba-pitfalls.md:50`、`ba-gateway-host.md:55`、`report\01:178` | **⚠️ [实测-弱] + 自相矛盾**（§8.1） |
| **L7** | — | **[一句话]** 没有任何文档写过这个总结句的完整论证 |

### 6.2 断点一：L3 的证据有一个已知未闭合的覆盖缺口

`report\11:200`（写 L3 结论的那份文档自己）：
> 「**M2. 序列化在 Unity 资源里**（boot 场景 / ScriptableObject 的默认连接组）| 磁盘 metadata 里只有 test 环境的 JSON 数组；生产值缺失 | 你们的 assets 扫描 0 命中（**但需确认覆盖了 level0/sharedassets/设备侧 11 GB 资源**）| 中」

我把这条缺口落实成可核查的事实（§5.3）：
- `assets/bin/` **565 条**，`assets/bin/Data/` 里 Unity 数据文件**被改名成 32 位哈希**，`GameMainConfig` 是 `.assets` 内部的 TextAsset；
- 明文扫描（`ba-pitfalls.md:130` ASCII+UTF-16）**打不穿 XOR**；
- 周期扫描（`ba-gateway-host.md:44`，L=1..43）**只做过 `libil2cpp`，没做过 `assets/bin/Data/**`**。

⇒ **L3 的正确表述应该是**：「**在 `global-metadata.dat` 与 `libil2cpp.so` 两个文件上，用 256 key × ASCII/UTF-16 + 周期 1..43，明文域名 0 命中**」，
**而不是**「网关域名不在 APK 任何静态产物里」。

### 6.3 断点二：即使 L6 成立，L7 也推不出来

`report\00:335` 自己指了另一条活路：
> 你现在唯一**确证活得**的落点是 **libunity 的 connect GOT**

也就是说：**从 libil2cpp 的代码洞（`DT_INIT` 里跑我们的代码）去写 libunity 的 GOT** ——
这条路上 **libunity 的磁盘文件一个字节都没改**，它被"钉死"的哈希完全不变。

- `ba-pitfalls.md:243`：libunity 的 GOT 页是 **`rw-p`，可直接 `str` 写，不需要 `mprotect`、不需要 `/proc/self/mem`**（[实测]）
- `ba-pitfalls.md:171-172`（E63）：代码洞里的代码**能跑、ACE 不杀**，`alive=24049`（[实测]）
- `ba-pitfalls.md:181`：libunity GOT 偏移 `getaddrinfo=0x13d94d8`、`connect=0x13d95d8`

⇒ **L6 的"钉死"只约束"磁盘文件"，不约束"运行时内存"。`report\10:146` 把这条评为「⑤ 从没按修正版跑过一次」。**

**断点三：ACE 是否有内存 CRC —— 从未验证。**
`report\18:210`：「磁盘校验肯定有；内存校验**未知**」；`report\18:234` 同义；`report\63:340` §C-6 同义。

### 6.4 真正卡住的是**信息**，不是**防护**

| 命题 | 成立? | 依据 |
|---|---|---|
| 「改了签名/改过包就被 ACE 杀」 | ❌ **不成立** | E30/E38/E42；§4 |
| 「改某些 .so 代码位置会 SIGBUS」 | ⚠️ **部分成立，可能被记账污染** | §8.1、`report\00:230` |
| 「**不知道要改哪个字符串**」 | ✅ **成立，且是唯一硬卡点** | L3（但见 §6.2 缺口） |
| 「网络层在 libunity，libil2cpp 里没调用点」 | ✅ **成立** | L4/L5 |
| 「在 libil2cpp 里执行任意代码」 | ✅ **成立**（E63） | `ba-pitfalls.md:171-172` |
| 「运行时写 libunity 的 GOT」 | ⚠️ **机制成立（rw-p 可 str），端到端未验证** | `ba-pitfalls.md:243` + `report\00:335` |
| 「有一个 40 字符 `http://` URL 可在 metadata 里等长改」 | ✅ **成立**（工具实测 3 处全改 + 旧值消失） | `report\52:433`、`:597` |
| 「改了它，state 请求就直奔我们」 | ❌ **只是预测，从未实测** | `report\52:433` 原文是"预期效果" |

### 6.5 还有一层：TLS（与改包正交）

- 客户端建 TLS **不发 SNI**：`ServerFlight` 带 SNI 2601 B vs 不带 1352 B（`report\19:25-29`，[实测]）。
- 客户端**拒绝**我们的证书：明文 alert `02 31` = `access_denied(49)`（`report\19:13`）。
- **`report\90:264` 的定性**：「免 root 分发不可行 —— 整套依赖 **DNAT（需 root/iptables）+ 系统 CA**，且 Unity 走 **libcurl 系统 CA 库**（非 App 内 CA bundle）⇒ 用户侧必须有一台被 root/可控的设备或网关」
  ⚠️ **这是 [一句话]**：无实验、无证书路径证据，且与 `report\11:241`（「系统 CA 是否被 mbedtls 采用」= **证据不足**）冲突。
  `DEADENDS.md:348-353`（D-41）实测「APK 内**无任何 cacert/pem/cer/der**」，所以"内置 CA bundle"这条不成立；但它推不出"必须系统 CA"。
- `DEADENDS.md:340-346`（D-40）：本 APK **根本没有 `networkSecurityConfig` 属性** ⇒ 想用用户 CA 必须自己加这个属性 ⇒ 必须重签。**未装机验证。**

**避开 TLS 的两条（都有历史记录）**：
1. **让 URL 变 http** —— `report\11:33-36`：「默认 connection group 的字面量就是 `http://`（不是 https），说明 `ApiUrl` 的消费端**接受明文 http**」；`report\10:143` 列为 ②，理由「`cleartextTrafficPermitted=true` 已被 `sdk_url=http://127.0.0.1:8080` **实跑验证**」。
   ⚠️ 但 `DEADENDS.md:96-102`（D-11）实测过：把 `Hosts` 的 url 写成 `http://` → **无 `:80` 连接**，仍连官方 `:443`（原因是"没被选中"，不是 scheme）。
2. **绕证书校验** —— 目标 `CustomCertificateHandler.ValidateCertificate`（metadata `0x1522dc`，`report\11:227`）。
   - `report\11:26-28` 说 metadata 混淆导致标准 Il2CppDumper 不可行 → **后来被推翻**：`report\63:63-83`（A-5）用 `.rela.dyn` 直接解出 methodPointers 基址 `0xFED01C0` 与 **151,085 条** `R_AARCH64_RELATIVE`；`report\51:23-26,185-195` 进一步给出 `CodeGenModule@0x0F90E080`、`methodPointerCount=154173`。
   - 新卡点：**`HandleAccountAuthResponseMessage` / `OnLoginFinish` / 整个 `HttpGameSession` 落在 ACE 编码页**，磁盘上是密文，离线改不了（`report\55:191-197`、`:445`；`report\51:32-33`、`:568`）。编码块 `[0x08A83000, 0x08A87000)` 4 页 16 KB。
   - **但 `ParseProtocol` / `AccountAuthStart` / `RequestAccountAuth` / `IsLoginFinished` 等在明文页**（`report\55:178-190`），且 `report\51` 给了一整套"改明文桩入口 + 代码洞"的方案（首选变体 C：`RequestAccountAuth@0x08A80458` 改 `b 0x08A836C0`）——**从未上机**（`report\57:389`）。

---

## 7. ★ 哪些结论有实验支撑，哪些只是一句话

### 7.1 有实验支撑（可为行动依据）

| 结论 | 支撑 | 出处 |
|---|---|---|
| 重签包能装能跑 | E30/E38/E42 三版 | `ba-pitfalls.md:18,57,150` |
| `assets/SDKConfigSettings.json` 可静态改且生效 | 6 条 SDK 请求实跑 | `ba-gateway-host.md:9`、`report\54:380` |
| `resources.arsc` / `res/*` 可改 | E32/E34/E42 | `ba-pitfalls.md:55` |
| `libil2cpp.so` 无磁盘 hash pin，可改 | E38 填充翻转 / E63 代码洞 / root 原位替换 | `ba-pitfalls.md:57,171,197` |
| 明文生产域名不在 metadata/libil2cpp（256 key × 2 形态 + 周期 1..43） | 4 种方法独立 | `ba-pitfalls.md:130`、`report\11:165-173`、`report\54:84-92` |
| `test-ba.yostar.net:5210` ×3 可等长替换（工具实测 3 处全改、旧值消失） | 工具跑通 | `report\52:433`、`:597` |
| `Servers[]` 由 `state` 响应下发 | 原始响应字节 + DTO 反推 | `report\98:361`、`report\24:196-230` |
| `files/Hosts` 是 `ServerInfoData.ConnectionGroups[]` 的写穿缓存，正确格式写入会被保留 | N7 79 B → 客户端重写成 128 B、我们那条原样保留 | `report\10:19`、`DEADENDS.md:88-94`、`report\56:992` |
| libil2cpp 里 `connect`/`getaddrinfo` 调用点 = 0 | 346 万条 BL 扫描 | `DEADENDS.md:168` |
| libunity 的 `connect` GOT 已解析到 libc | `/proc/pid/mem` 实读 | `ba-pitfalls.md:211` |
| libunity 的 GOT 页是 `rw-p`，可直接 `str` 写 | 实测 | `ba-pitfalls.md:243` |
| libil2cpp 代码洞 + `DT_INIT` 能跑，ACE 不杀 | E63 `alive=24049` + `IN/BA/DON` | `ba-pitfalls.md:171-172,192` |
| ACE 判定持久化，删 4 个文件可复位 | 实测有效 | `ba-pitfalls.md:59-70` |
| DNAT 可用（现役方案） | 兜底 DNAT 1 条 89 包命中 + ip6 全 REJECT | `report\19:11,15-19` |
| 客户端建 TLS 不发 SNI | ServerFlight 1352 vs 2601 B | `report\19:23-32` |
| metadata 方法地址可静态解出 | `.rela.dyn` + 151,085 / 154,173 项 | `report\63:63-83`、`report\51:185-195` |
| `GameMainConfig` / `ServerInfoDataUrl` 两个名字存在于国服 metadata | 反向搜 256 key | `report\59:802-803` |

### 7.2 只是一句话判断（**不可作为行动依据**）

| 一句话 | 出处 | 为什么不可信 | 是否已被推翻 |
|---|---|---|---|
| **「iptables NAT（DNAT）在本机不生效」** | `README_归档说明.md`（转引 `report\01:191`、`report\10:44`） | 「`audit\` 内**无任何记录**：无命令、无链名、无对照输出、无失败现象」 | ✅ **已推翻**：现方案就是 DNAT（`report\19:15-19`） |
| **「免 root 分发不可行」** | `report\90:264` | 无实验、无证书路径证据；与 `report\11:241`（证据不足）冲突 | ❌ 未验证，**不应沿用** |
| 「改包名 → SIGBUS」 | `ba-airisdk.md:244`（转引 `report\01:183`） | 无方法、无对照；`DEADENDS.md:48` 只有"SIGBUS"一词 | 未知 |
| 「新增 dex 卡启动**与 ACE 无关**」 | `ba-pitfalls.md:52`、`report\02:239` | 只因"ACE 8~10 s 后杀而这里 Unity 未加载"的时间差推出，**无 ACE 侧观测**；且 `DEADENDS.md:573` 证明 `status=9`（系统小窗）混淆过同类判断 | 未知 |
| 「ACE 会校验 `libunity.so`，命中即 SIGBUS」 | `ba-gateway-host.md:58` | 与 E30 冲突；项目自判"大概率记账污染" | ⚠️ **待重测** |
| 「证书绕过必须放弃，后续一律走明文 HTTP」 | `ba-gateway-host.md:59` | 前半有 E42 对照；**后半"走明文"从未在任何 API 路径上兑现**（`report\10:130` 自评"半截结论"） | 半截 |
| 「游戏用 HTTPDNS，不走系统解析」 | `ba-pitfalls.md:179` | 真因是 netd 的 mount ns（`DEADENDS.md:132`） | ✅ **已推翻** |
| 「客户端不请求 state / 网关入口是 gsqc 不是 state-api」 | `report\06:314`、`report\19:10` | 单一指标（Hosts 不重建）反推，与 HAR 抓包冲突 | ⚠️ **待重测**（§5.6） |
| 「E64 超时说明路径已改但实现有阻塞」 | `ba-pitfalls.md:184` | 信号零判别力 | ✅ **已推翻**（`report\10:61`、`report\13:123`） |
| 「`libil2cpp.so` 不能改 / 不要 patch」 | `anti-detection.md §3`、`_frag\infeasible.md 方向8` | 静态推断 | ✅ **已推翻**（`report\01:277`、`INDEX:A-31`） |
| 「`files/Hosts` 只是记录/展示，不决定连接目标」 | `ba-pitfalls.md:128`、`ba-gateway-host.md:32` | 写入格式错误导致解析失败，与"不使用"不可区分 | ✅ **已推翻**（N7） |
| 「libil2cpp 走 `-fno-plt` 风格，`.plt` 桩没人走」 | `ba-pitfalls.md:191` | 真因是**这两个导入根本没调用点** | ✅ **已推翻**（`DEADENDS.md:169`、`INDEX:A-5`） |
| 「现役可用包是 E42」 | `ba-pitfalls.md:155` | 设备上装的**不是** E42（内嵌 so 带桩，sha `6e2edf5a`，既非原厂 `5ac1cbe0` 也非 g20 `a473ba16`） | ✅ **已推翻**（`report\13:79`、`INDEX:A-13`、`report\57:19`） |
| 「ACE 钉的是 libunity.so 与 global-metadata.dat」 | `report\53:203-204` | `report\52:536-537` 点名：「那是**转述**、无实验支撑、与 `INDEX §4` 冲突——**不要采信**」；53 这句正是被点名那条的复述 | ❌ 不许用 |
| 「替换资源整条路线判死」 | `DEADENDS.md:353`（D-41） | 证据只是"APK 内无 cacert/pem/cer/der"，推不出整条路线死 | 强度超证据 |
| 「pinning 假设被推翻」 | `DEADENDS.md:360`（D-42） | 推翻它的实验**没有列出** | 强度超证据 |
| 「内存里没有明文 metadata 字符串」 | `DEADENDS.md:301`（D-35） | 证据是 magic 0 命中 ≠ 无字符串（原文自承可能被 scudo 分片/在 dalvik 堆内） | 强度超证据 |
| 「国服是 ARM64，改 metadata 要重签 APK，风险远高于 PC」 | `report\56:1137` | 推断，无实验 | 未验证 |
| 「`Hosts` 的 u64 是时间戳/优先级」 | `report\10:170` | 未验；`report\56:996` 给了更好的假设（**版本键编码**） | 二义 |

---

## 8. 矛盾清单

### 8.1 ★ `libunity.so` 4 字节补丁：活 vs 死

| 说法 | 原文 | 出处 |
|---|---|---|
| **安全** | 「`libunity.so @0xA53A38` 4 字节补丁**安全** ｜ 同上（与官方行为一致，**未见异常**）」（E32/E34/E36 均可启动） | `ba-gateway-host.md:14` |
| **安全** | 「**已验证可用的最小改包（E30）** … **这一版不崩，能进游戏**」 | `ba-pitfalls.md:13-18` |
| **安全** | 「只做**原地字节补丁**：libunity 4 字节证书绕过**已验证可用**」 | `ba-pitfalls.md:10` |
| **死** | 「E32/E34/E36 打了 `@0xA53A38` 证书补丁 → 启动后 **SIGBUS（status=7，无 tombstone）**」 | `ba-gateway-host.md:55`、`:81` |
| **死** | 「`libunity.so` 4 字节证书补丁 `@0xA53A38` ❌ **SIGBUS** E36」 | `ba-pitfalls.md:50` |

**范围**：`ba-gateway-host.md:14` 与 `:55` **在同一文件里，相隔 41 行，直接互否**；`ba-pitfalls.md:10` 与 `:50` 同理。
**项目自己的裁决**：`report\00:230` 判为**记账污染**，并计划「复位 ACE 记账后重跑一次 E30 的改法」（`report\00:327`）。
**该实验是否做过**：**未找到**。
**现状**：`report\10:58`（C7）评为 **[半有效]**，结论保留为「libunity 补丁不可用仍成立」——但**这条评级没有覆盖 E30 这个反例**。

### 8.2 `classes2.dex` 重编（E44）成败

`ba-pitfalls.md:54`「首次启动成功（E44），但之后同批 APK 全部卡启动界面」 vs `ba-gateway-host.md:84`「✅ 正常启动、SDK 登录成功」。
`report\01:182` 并列标注，结论「**不可复现，已放弃**」——**从未在复位 ACE 记账后重试**。

### 8.3 metadata 静态可解性

`report\11:26-28`「标准 Il2CppDumper 不可行；`nameIndex` 反查 0 命中；methods 表 12 种 stride 全 0 候选」
vs `report\63:63-83`（`.rela.dyn` 法给出 151,085 条相对重定位与真方法地址）、`report\51:19-26`（「metadata 可完整解析，推翻 report/24/47/48」，30 段首尾相接 + 三表 count 精确相等）。

**判读**：不是矛盾，是**换了入口**。`report\11` 的"不可行"只针对 Il2CppDumper 标准流程。
⇒ **`report\11:22` 那句「静态只能定位到类/方法，定位不到值 → 值只能运行时取或不解密」的下半句被部分推翻**：值仍取不到，但**方法地址能取到**。

### 8.4 网关入口是 `state-api` 还是 `gsqc-api`

见 §5.6。`report\98/99/100`（HAR，[确证]）vs `report\06:314`、`report\19:10`（删 Hosts 不重建 + 666 行采样）。

### 8.5 区段表 / 加密模型 / 成员数（report 51-55 内部，转引自并行分析）

| # | 冲突 | 双方 |
|---|---|---|
| C1 | `LoginState` 成员数：**4 个**（Ready/Progress/Finished/Failed，`Finished=2`） vs **2 个**（只有 Finished/Failed） | `report\51:75-95`、`:566` vs `report\52:174,427`、`53:505`、`54:430`、`55:341`。**影响**：51 的代码洞靠写 `Finished=2`，按"2 成员"理解会错判状态值 |
| C2 | `get_IsFinished` 归属：属 `SessionStateChangedMessage(65973)@0x06E131A8` vs 属 `HttpGameSession@0x0021A587` vs 两个类各有 | `report\51:97-109`、`:599` vs `report\52:161,349`、`53:52,66`、`54:429`、`55:52,226` vs `53:577` |
| C3 | 卡点位置：三个互斥（`WaitForRequest` 已被削弱 / `get_IsFinished` 是真卡点 / 卡在"认领"层） | `report\51:574,600` vs `report\53:573` vs `report\55:242,451` |
| C4 | ACE 钉不钉 `global-metadata.dat`：钉 vs 未知/不要采信 | `report\53:203-204` vs `report\52:532,627,536-537`（**52 明确点名 53 这类说法是转述、无实验支撑**） |
| C5 | 区段表 offset/条数对不上（同一份 metadata，sha 均 `2352cb57…`） | `report\51:152-153`、`55:67-68`（typeDefinitions `0x1F02148`/35,105-35,116、images `0x21F44A0`/103）vs `report\52:258-263`（`0x01D75FA0`/56,580 等）。52 自承缺 4 段，正是错位成因 |
| C6 | 区段数量：28 / 30 / 31，三份都自称确证 | `report\52:227-237`、`51:155`、`55:59` |
| C7 | 加密页占比：34.2% vs 26.2% vs 26% | `report\51:237` vs `report\52:92`（引 `report\17:484`）vs `53:259` |
| C8 | 「唯一可行补丁落点」三家各说各话：改明文桩入口 vs 改 methodPointer vs `data` 段重定位 addend | `report\51:36-43,322` vs `53:248,66` vs `55:32,361`。**只看 `report\55:361` 会否掉 `report\51` 全部方案** |
| C9 | 字符串混淆模型：全局周期律 vs 每串独立 key（且 54 直接判 51 的产物不可用） | `report\51:125-141`、`55:72-82` vs `report\54:42-63`、`:100-113`、`52:319-320` |
| C10 | `.rela.dyn` 条目数：1,526,842 vs 1,526,832（差 10） | `report\51:197` vs `55:426`。55 的 addend 补丁坐标正依赖这张表 |
| C11 | `test-ba` 偏移写法差 7 B：`0xC172B` vs `0x000C1732` | `report\52:333,433` vs `54:23,80,420`。**打补丁前必须先定死起点** |

### 8.6 `extractNativeLibs` 与 "assets 必须重打包"

`report\30:337`「`extractNativeLibs=true`，`assets/` 仍是未解压 zip 条目 → 改 `assets/` 必须重打包重签」 **vs** `report\63:101`（A7.4）「该 `.so` 是**磁盘上的独立文件**（不是从 APK 内直接 mmap）」。
**不冲突**（一个说 `assets/`，一个说 `lib/`），但 **`report\30:337`「assets 是 zip 条目」这句本身没有独立证据**——它从 `extractNativeLibs=true` 推的，而 `report\30:336` 自己加了 ⚠️「先确认 `global-metadata.dat` 在设备上到底从哪儿读」；`report\52:498-524` 把这条列为**闸门 1：未知**。

---

## 9. 需要重新验证的清单（按性价比排序）

| 序 | 要验什么 | 为什么 | 成本 | 历史状态 |
|---|---|---|---|---|
| **V0** | **`assets/bin/Data/**` 的 565 个文件里，有没有加密的 `GameMainConfig`（914 B 级 TextAsset）；用 `create_key("GameMainConfig")` 解密后 `ServerInfoDataUrl` 是什么** | 这是「客户端第一次连谁」的唯一具体候选；算法已给出（`report\56:1086-1095`），字段名已在国服 metadata 里（`report\59:802-803`）；而明文/周期扫描**从未覆盖这个目录** | 低（纯离线） | `report\56:991` 被主动降级为"不需要" |
| **V1** | **客户端从哪读 `global-metadata.dat`**（APK 内 zip 条目 vs `files/il2cpp/Metadata/` 外部副本） | 决定"改 metadata 要不要重打包重签"。若走外部副本 ⇒ **一条 `cp`**，不碰 ACE 的 APK 完整性面 | 极低（3 条只读命令） | `report\52:523-524`「**从未真正跑过，这是整条路线的第一个 5 分钟**」；列为性价比第 1 |
| **V2** | **复位 ACE 记账后重跑 E30 的 libunity 4 字节改法** | 这是"不能改 libunity"结论的**唯一反例**，项目自己点名要重做 | 极低（1 次装机） | `report\00:327` 列为实验 3，**无执行记录** |
| **V3** | **`test-ba.yostar.net:5210` ×3 等长替换后，客户端 state 请求是否真的改道** | 唯一在 metadata 里、`http://`、40 字符、工具已能改的地址字面量。"改了直奔我们"目前只是**预期效果**，不是实测 | 低（等 V1 定路径） | `report\52:433` 是预测；工具侧 `report\52:597` 已验证替换成功 |
| **V4** | **`GameMainConfig.ServerInfoDataUrl` 等长替换 + repack + 删 `__tpinfo` → 装机能跑吗** | 唯一"地址载荷在 APK 内 + 等长可覆盖 + 改动面已被 E42 证明能跑"的组合 | 中（一版 APK） | 从未做过 |
| **V5** | **客户端到底请求 `state-api` 吗**（直接看 DNS/连接，不靠"Hosts 有没有被写"） | §5.6 冲突；决定"控制 state 上游"这条路成不成立 | 极低 | `report\06:309` 单指标，与 HAR 冲突 |
| **V6** | **`libil2cpp` 代码洞 → 运行时写 libunity GOT**（无 root 版：把它做成一版 APK） | E63/E64 **全是 root 原位替换，没有一个 repack 版本**；而这条路径不需要 root 也能在进程内执行 | 中 | `report\10:146`「从没按修正版跑过一次」 |
| **V7** | **ACE 是否有内存 CRC** | 决定 V6 会不会被抓 | 中 | `report\18:234` 明写未知 |
| **V8** | **ACE `initialize()` 对 `sourceDir/splitSourceDirs` 算什么** | 决定"签名变化"到底有没有代价（分发可行性的关键） | 中 | `anticheat-full.md:150` 未验证 |
| **V9** | **`res/xml` 有无可用于用户 CA 的 `trust-anchors`** | 决定证书路要用户 CA 还是系统 CA（后者才需 root） | 极低 | `DEADENDS.md:340-346` 只说"没有 networkSecurityConfig 属性" |
| **V10** | **改包"必须卸载重装"是不是硬约束** | 决定免 root 方案的分发摩擦（丢 `/data/data` + 11 GB 资源 `chown`，`ba-pitfalls.md:109-122`） | 低 | `report\30:344` 只是操作建议，无实验 |

---

## 10. 一页速查

```
重打包次数      ≥15 版（E28–E44）；另有 8 个"塞模块"脚本 + 3 个改包名脚本；磁盘上 repack*.py 共 19 个
逐版装机日志    没有（report\57:387）；游戏包 pm install 原文也不存在（:138）；唯一真机一手记录是 libil2cpp_probe（2分13秒，失败）
重签能不能跑    能。E30「不崩能进游戏」/ E38「正常启动 45s+」/ E42「能进主程序、SDK 登录成功」
签名被杀证据    零。anticheat-full.md:112 原话是"最现实的风险点"；项目从未做"只改签名、其余不动"的对照
真实的 SIGBUS   libunity 4B 补丁（E36）+ libairisgcore 整库替换（E35）
                但 E30 同补丁"不崩能进游戏" → 项目自判记账污染，重测实验从未做（report\00:327）
真实卡启动      新增/重编 dex（E39-41/E43）；"与 ACE 无关"是推断，且 status=9 曾混淆过同类判断
唯一的硬卡点    「不知道要改哪个字符串」
                └ 但这条的证据有缺口：明文扫描打不穿 XOR，周期扫描只做过 libil2cpp，
                  从未扫过 assets/bin/Data/** 的 565 个（改名为哈希的）Unity 数据文件
可用的静态杠杆  ① assets/SDKConfigSettings.json 的 sdk_url —— 改了就生效（E31/E42），需重打包
                ② global-metadata.dat 里 http://test-ba.yostar.net:5210/api/state ×3 —— 40 字符等长可改，
                   工具已验证替换成功，"改了就改道"从未实测
                ③ GameMainConfig 的 ServerInfoDataUrl（914B 加密 TextAsset）—— 算法已知、字段名国服存在、
                   从未定位。最可能才是"第一次连谁"的答案
服务端下发      Servers[] 来自 state-api 响应（逐字节对上）→ 把 gsqc-api 写死进 APK 没有对象可写
网络层归属      libunity（libil2cpp 里 connect/getaddrinfo 调用点 = 0，346 万条 BL 扫描）
可用落点        libil2cpp 代码洞 + DT_INIT（E63 alive=24049，ACE 不杀）+ libunity GOT 页 rw-p 可直接 str 写
                ⇒ 这两条拼起来就是"改包版免 root 重定向"，从未作为一版 APK 做过
```

---

## 附录 · 引用文档

| 文档 | 用途 |
|---|---|
| `work\ba\audit\ba-pitfalls.md` | **主证据源**：E 系列容错矩阵、ACE 记账、`__tpinfo`、代码洞经验 |
| `work\ba\audit\ba-gateway-host.md` | 网关地址排除法、`gameUrl` 实测、libunity 补丁对照 |
| `work\ba\audit\anticheat-full.md` | `sourceDir/splitSourceDirs`、签名 SHA1 采集、未验证清单 |
| `work\ba\audit\ba-apk\zip_listing.txt` | **本次新核**：41,312 行；`assets/` 40,410 条，`bin/` 565 条，`GameMainConfig` 0 命中 |
| `report\01` | 86 条证伪清单（§4）、可用清单（§3） |
| `report\02` | 注入链全史 + **"无 tombstone 原文"的自我声明**（:221-223） |
| `report\06` | DNS/证书/Hosts 手机侧实验一手记录 |
| `report\10` | **方法论最好的审计**：每条实验的"是否有效"评级 |
| `report\11` | 四种扫描方法证伪"域名是静态字面量"；M1/M2/M3 三模型 + 覆盖率自警（:200） |
| `report\13` | 提出→被推翻结论汇总 |
| `report\19` | DNAT 兜底规则原文 + SNI 根因 |
| `report\30` | metadata 公钥替换（未实施）+ assets 重打包论证 |
| `report\51`–`report\55` | 四条补丁方案的可行性、bail 点、`test-ba` 等长替换、三道未验证闸门 |
| `report\56` | 外部零先例 + **`GameMainConfig.ServerInfoDataUrl` 与解密算法** |
| `report\57` | 资产台账、repack 脚本族、**"本地无证据"清单**（§7） |
| `report\59` | 反向搜 256 key 法；`GameMainConfig`/`ServerInfoDataUrl` 在国服 metadata 中**确实存在** |
| `report\63` | A/B/C 三级分层、`.rela.dyn` 方法地址法、§C 禁止行动清单 |
| `report\90` | 「免 root 分发不可行」这句话一句话判断的出处（:264） |
| `report\DEADENDS.md` | 66 条死路（D-01…D-66），本议题集中在 D-01…D-19 + D-40/D-41 |
| `report\98/99/100` | HAR 抓包：`state-api` 请求与 `Servers[]` 原始字节 |
