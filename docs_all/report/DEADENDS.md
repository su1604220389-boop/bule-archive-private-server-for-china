# 死路清单（试过、失败、不要再试）

> 本文件是 `report/INDEX.md` §2 的详细版。每条 6 个字段：**想法 / 做法 / 结果 / 为什么失败 / 教训 / 出处**。
> 「曾经的错误结论 → 后来的正确结论」不在这里，在 **`report/INDEX.md` 附录 A**（36 条），两者配合看。
> 行号为 read 工具行号。所有"结果"字段都来自报告原文的原始输出，**没有一条是推测**（推测会显式标「推断」）。
> 特别重点项：**D-43～D-45**（Account_Auth 四种变体 / 无第二协议请求证据链 / HTTP 状态码探测）、**D-19～D-29**（改 libil2cpp 与 metadata）、**D-30～D-35**（Frida 与 il2cpp 符号）、**D-36～D-42**（证书注入）、**D-49**（宝塔 WAF）、**D-52～D-60**（ssh/tcpdump/日志判读）。

---

## A. 改包 / ACE 容错面

### [D-01] `libunity.so` 4 字节证书补丁
- **想法**：把 `CertificateHandler` 相关的校验分支改掉（`@0xA53A38`：`f8 03 00 2a → f8 03 1f 2a`，`mov w24,w0` → `mov w24,wzr`），让客户端接受自签证书。
- **做法**：直接在 APK 里的 `libunity.so` 上做 4 字节原地补丁，重打包签名装机（E32/E34/E36）。
- **结果**：启动即 `SIGBUS`，`ApplicationExitInfo reason=2 status=7`，**无 tombstone**。对照组：E42 换回原厂 `libunity` 立刻正常。
- **为什么失败**：ACE 对 `libunity.so` 做**磁盘哈希钉死**，任何一个字节变化都在加载期被抓。
- **教训**：`libunity` 属于"只读区"，一切改动只能走**运行时内存**；先查 `ba-pitfalls` §4.1 的容错矩阵再动手。
- **出处**：`work/ba/audit/ba-pitfalls.md:50`、`report/01-现状与已试方向.md:178`

### [D-02] 整库替换 `libairisgcore.so`
- **想法**：AiriSDK 的签名/加密核心在 `libairisgcore.so`（`getAAesKey`/`getAAesIv`/`sign`），整库换成 8 KB 假 so 就能读到明文 key/iv。
- **做法**：编译假 so（导出符号正确、NEEDED 干净、无人依赖），替换进 APK（E35）。
- **结果**：`SIGBUS (reason=2 status=7)`。
- **为什么失败**：与 libunity 同一道墙——ACE 校验的是"文件是否被动过"，不是"有没有人依赖它"。
- **教训**：「NEEDED 干净 / 无人依赖」**不是**免死金牌；ACE 的校验对象是整文件哈希。
- **出处**：`work/ba/audit/ba-pitfalls.md:51`、`report/01-现状与已试方向.md:179`

### [D-03] 往 APK 加新 `.so` / 改 `libmain.so` 的 `DT_NEEDED`
- **想法**：加自己的 hook 库，或让 loader 先加载我们的 `.so`。
- **做法**：① 重编 `libmain.so` 加一个 `LOAD` 段 + `DT_NEEDED: libgm.so`；② 把 `.dynstr` 的 `liblog.so` 改成 `libdg.so`、把 `.dynamic` 末尾 `DT_NULL` 改写成 `DT_NEEDED`。
- **结果**：**无日志闪退**（ACE 直接杀，连 tombstone 都没有）。产物 `libmain_patched.so` 与 `fix/lib/arm64-v8a/libmain.so` 留在仓库里，证明已回滚。
- **为什么失败**：ACE 禁止"加载布局变化"，`sourceDir`/`splitSourceDirs` 是它的完整性面。
- **教训**：只做**原地字节补丁**；不要改 NEEDED、不要加 so、不要动 libmain。
- **出处**：`work/ba/audit/ba-pitfalls.md:10`、`report/02-注入链审计.md:129`、`:168`

### [D-04] 新增 `classes3.dex` / 重编 `classes.dex` / 重编 `classes2.dex`
- **想法**：加自己的 Java 代码（LSPosed 探针、smali patch）。
- **做法**：① 新增 `classes3.dex`（哪怕只有 660 B 的空类）；② `baksmali → smali` 回编 `classes.dex`；③ 重编 `classes2.dex` 改一个 `const-string`。
- **结果**：①②卡 **Android 启动界面**（Unity 未加载，与 ACE 的 8~10 s 后杀进程无关）；③ 首次启动成功（E44），**但之后同批 APK 全部卡启动界面**（两处记载冲突，见 INDEX 末表）。
- **为什么失败**：不是 ACE，是**启动链本身**不接受 dex 结构变化（多 dex 的 Vdex/oat 与签名校验链）。
- **教训**：`res/*`、`resources.arsc`、`assets/*.json` 才是安全改动面；dex 一律别碰。
- **出处**：`work/ba/audit/ba-pitfalls.md:52`、`:53`、`:54`、`report/01-现状与已试方向.md:180`、`:182`

### [D-05] 改包名
- **想法**：换个包名躲开检测/多开。
- **做法**：改 manifest 包名重打包。
- **结果**：`SIGBUS`。
- **为什么失败**：包名被 ACE 校验（它拿 `sourceDir` 与包名做一致性判断）。
- **教训**：包名是红线。
- **出处**：`report/01-现状与已试方向.md:183`、`work/ba/audit/ba-pitfalls.md:244` 引

### [D-06] 假 ACE（整体替换 `libtprt.so`）
- **想法**：写一个假 `libtprt.so`（导出 `JNI_OnLoad` / `g_tprt_pfn_array` / `g_tprt_ori_array`），让 ACE 变成空壳。
- **做法**：编译假 so，日志能打出 `ACE-register-ok` / `ACE-initialize`，启动**能过**。
- **结果**：启动能过，但**用户明确否决**："假 ACE 会破坏 Unity 需要的返回"。
- **为什么失败**：ACE 不只是"检测器"，它还承担 Unity 依赖的返回语义（`g_tprt_ori_array` 是原始 libc 函数表）。
- **教训**：能过启动 ≠ 可用。这条已被决策层否决，不要再提。
- **出处**：`report/01-现状与已试方向.md:185`、`work/ba/audit/ba-pitfalls.md:244`

### [D-07] 改 `libtprt` 的两处自身校验跳转
- **想法**：把两处"校验失败→自杀"的条件跳转改成无条件跳过（`b.eq +0x10` → `b +0x10`），让它算自己的哈希永远通过。
- **做法**：4 字节 ×2（`patched`），再 12 字节（`patched2` 把 `csel` 改成无条件返回 x19）。
- **结果**：产物**没有任何后续脚本引用**，`libtprt_final.so` 与 `orig` **逐字节相同**（sha `47064882…`）—— 实证放弃。
- **为什么失败**：改"校验点"不解决"文件被改"这个事实；且 `:GP6/:GP7` 是独立进程，一个进程里的 patch 管不到另一个进程的复核。
- **教训**：先问"这个校验发生在哪个进程、哪个时机"，再决定改哪。
- **出处**：`report/02-注入链审计.md:105`、`:113`、`:171`

### [D-08] 清空 `/data/data/<pkg>` 求"干净重置"
- **想法**：客户端状态乱了，清内部数据重来。
- **做法**：删 `/data/data/com.RoamingStar.BlueArchive`。
- **结果**：**永久卡在 Android 启动界面**，Unity 从未加载，`/proc/pid/maps` 里只有 `libtprt.so`。`debuggerd -b` 栈：`ActivityThread.handleBindApplication → TechApplication.attachBaseContext → AceApplication.attachBaseContextShell → libtprt.initialize() → __sem_timedwait`（永远等不到）。
- **为什么失败**：ACE 的 `initialize()` 在等 `:GP6/:GP7` 服务应答，而这两个服务依赖 `files/data/app/…` 里的**解包产物**——清内部数据把它删了，ACE 无法重新解包。
- **教训**：唯一恢复手段是**卸载重装**；保资源先把 `/sdcard/Android/data/<pkg>`（11 GB）`mv` 到 `/sdcard/ba_data_bak`。
- **出处**：`work/ba/audit/ba-pitfalls.md:72`

---

## B. 客户端重定向 / DNS / hosts

### [D-09] 改 `files/Hosts`（裸串 `127.0.0.1:9443`）
- **想法**：`files/Hosts` 里写着网关地址，改掉就能把流量导过来。
- **做法**：手写单条 `127.0.0.1:9443`（"时间戳字段设成比官方大 1"），登录成功后看 9443 连接数。
- **结果**：9443 **0 连接**；游戏还把官方条目追加回去。当时结论"Hosts 只是记录/展示"。
- **为什么失败**：真实结构是 `u32 ver | u32 count | loop{u8 hostlen, host, u32=1, u8 urllen, url(带 scheme+端口), u64, u8 flag}`；裸串格式解析失败 → 整条被丢弃 → 与"不被使用"**不可区分**。
- **教训**：**"格式不合法被丢弃" ≠ "该文件不被使用"**。当年手上其实已有 89 B 的正确样本（`api-probe.md:14`），只是没认出来。
- **出处**：`work/ba/audit/ba-pitfalls.md:128`、`report/10-网关重定向-已试清单与有效缺口.md:31`、`report/08-手机接管与真因.md:58`

### [D-10] 改 `files/Hosts`（**正确格式** 79 B）
- **想法**：既然格式解出来了，按结构写就能生效。
- **做法**：写 79 B（sha `65781f31…`）：`host=gsqc-api.bluearchive-cn.com`、`url=https://example.com/api/`，其余字段照官方。
- **结果**：客户端**读懂了**（u32 计数 1→2、我们的 URL **原样保留**），然后**追加**官方 `https://gsqc-api.bluearchive-cn.com:443`，但本轮连接**仍落官方 IP**。
- **为什么失败**：它是 `Servers[]` 的**写穿缓存**——state 成功时被覆盖；**能否"被选中"**是另一层（u64 优先级/顺序）问题，尚未解决。
- **教训**：这条把"Hosts 已死"整体作废（见 INDEX 附录 A-7）。下一步只需解决"被选中"。
- **出处**：`report/06-手机基线恢复.md:200`、`report/10-…:110`、`report/13-总账-2026-11-14凌晨.md:71`

### [D-11] `Hosts` 里写**明文 http** URL
- **想法**：既然 `cleartextTrafficPermitted=true`（当时认为是），那把 url 写成 `http://` 就能整层跳过 TLS。
- **做法**：写 78 B（sha `13c58d62…`）：`url=http://example.com/api/`。
- **结果**：启动后 `ss -tnp` 全程**无任何 `:80` 连接**；`Hosts` 被重写成 127 B，我们的 http URL **原样保留**，仍连官方 `:443`。
- **为什么失败**：不是 scheme 问题，是"候选项没被选中"（同 D-10）。
- **教训**：**一次只改一个变量**；scheme 这个变量已经被排除干净了。
- **出处**：`report/06-手机基线恢复.md:237`、`report/13-…:73`

### [D-12] 调大 `Hosts` 的 u64（假设"最新者优先"）
- **想法**：u64 是时间戳/优先级，调大就能让我们那条排前面。
- **做法**：`0x48df40f28b89dd92 → 0x48df40f28b99dd92`（+0x100000），小端写回。
- **结果**：客户端把我们的 u64 **原样保留**（没打回旧值），但 `conn120=0`（6 次采样全 0）。
- **为什么失败**：u64 不是"谁说了算"的开关；state 成功时仍优先官方候选。
- **教训**：别把"字段保留"当成"字段生效"。
- **出处**：`report/06-手机基线恢复.md:217`、`report/13-…:74`

### [D-13] 按**单 IP** 阻断 `state-api`/`gsqc` 的 443
- **想法**：让 state 失败，客户端就会回落到 `Hosts` 里我们的候选。
- **做法**：`iptables -I OUTPUT -p tcp --dport 443 -d <ip> -j REJECT`（2 条，-S 存档）。
- **结果**：`conn120=0`；app 改用 CDN 轮换后的另一个 IP（`111.3.79.65` / `39.174.179.5`）。
- **为什么失败**：kunlun CDN 会换 IP/换 v6，单 IP 阻断是**打地鼠**。
- **教训**：要阻断就按 **uid + 端口** 全量，不要按 IP。
- **出处**：`report/06-手机基线恢复.md:225`、`:232`、`report/13-…:75`

### [D-14] `uid` 级 443 `REJECT`（**只断不导**）
- **想法**：彻底断掉官方 443，逼客户端用我们的候选。
- **做法**：`iptables -I OUTPUT -p tcp -m owner --uid-owner 10576 --dport 443 -j REJECT`（v4/v6 各一条）。
- **结果**：屏幕报「请确认网络连接状态后重试」（纯网络错）；app 仍在死磕官方（SYN-SENT `106.15.149.219` / `47.100.134.67`）；**`Hosts` 该轮甚至没被重写**。
- **为什么失败**：state 拿不到时客户端**直接报网络错，不回落**候选项。`Hosts` 是"成功时写穿"，不是"失败时兜底"。
- **教训**：`Hosts` 的语义是**写穿缓存**，不是 fallback 列表。想验证必须先让 state **失败**，而失败后它也不回落 ⇒ 此路不通。
- **出处**：`report/06-手机基线恢复.md:253`、`report/10-…:130`、`report/13-…:76`

### [D-15] 改 `/system/etc/hosts`（shell 的 mount ns 里 bind-mount）
- **想法**：系统 hosts 优先级高，改它就能接管解析。
- **做法**：`cp` 备份 56 B → 追加 4 行 → `mount --bind /data/local/tmp/hosts.new /system/etc/hosts`（`mount_rc=0`，`tail` 已可见）。
- **结果**：`ping gs-api` → 官方 IP；`ping state-api` → 官方 IP。`override_effective=0`。
- **为什么失败**：app 的解析由**系统服务（netd, pid 1937）**代答，netd 在**另一个 mount namespace**；shell 侧 bind 它看不到。
- **教训**：动 hosts 前先问"谁在做解析、它在哪个 ns"。
- **出处**：`report/06-手机基线恢复.md:176`、`report/10-…:89`、`report/13-…:72`

### [D-16] `nsenter` 进 netd 的 mount ns 再 bind hosts
- **想法**：既然 netd 在别的 ns，进它的 ns 改就行。
- **做法**：`nsenter -t 1937 -m -- mount --bind … /system/etc/hosts`（rc=0），并在 netd ns 里 `tail` 确认 4 行可见。
- **结果**：`ping gs-api` → 官方 IP（39.173.144.15），`ping state-api` → 官方 IP 且**每次查询还在变**。`override_effective=0`。
- **为什么失败**：DNS 实际被 **VPN/Clash tun** 层接管（默认路由 `vgate0`），netd 的 hosts 只是其中一环。
- **教训**：这条路的**手段**（shell 侧 bind）错了，但"进 ns 改"这个思路仍然是官方解法（见证书注入 D-38），只是 DNS 这一层还多一层 tun。
- **出处**：`report/06-手机基线恢复.md:186`、`:194`

### [D-17] 删掉 `Hosts` 看客户端是否重建（作为"客户端是否请求 state"的判据）
- **想法**：如果客户端真的请求 state，删掉缓存后它应该重建。
- **做法**：`rm -f .../files/Hosts` → 启动 → 点一下 → 30 s 后 `ls`。
- **结果**：`No such file or directory`（**没有被重建**）。
- **为什么失败**：不是"失败"，是**这是一条成功的证伪实验**——客户端从头到尾**没有请求过 state**。此前"客户端会请求 state"的 M3 模型（`report/11:201`）因此作废。
- **教训**：这条要保留在"已证伪"里；同时说明**网关入口不是 state-api**（0.3 s × 90 s 采样 666 行全指 gsqc）。
- **出处**：`report/06-手机基线恢复.md:309`、`report/19-网关攻坚-当前状态.md:10`

### [D-18] 改 `LocalizeConfig.txt` 的 `ResUrls` / 改 `gameUrl`
- **想法**：① `ResUrls` 是资源 CDN 根，改掉就能劫持 CDN；② SDK init 收到的 `gameUrl` 就是网关地址，Java 层替换它即可。
- **做法**：① 指向 `https://127.0.0.1:9444/prodm39` + 起 TLS 反代；② E44 把 `TechSDKUnityBridge$1.val$gameServerUrl` 强制成 `http://127.0.0.1:8080/api/state`。
- **结果**：① `cdn.log` **一条请求都没有**，游戏提示「网络异常」；② 登录链照常走完（`/common/config`→`quick-login`→…），但 `/api/state` 命中 **0**。
- **为什么失败**：① `ResUrls` 与 API 网关无关（而且 9444 上是自签证书，TLS 先死）；② `gameUrl` **只被记录、不参与登录**（运行时日志证明游戏把 `gameUrl=https://state-api…` 传给 SDK，但登录链不用它）。
- **教训**：① "被忽略"和"TLS 挂了导致没有日志"要分开判；② 一个字段被赋了值 ≠ 它在链路上被消费。
- **出处**：`work/ba/audit/ba-pitfalls.md:129`、`:132`、`report/10-…:33`、`:35`

---

## C. 注入 / GOT / PLT / 代码洞

### [D-19] 改 libil2cpp 的 PLT/GOT（`getaddrinfo` / `connect` 两个槽）整个方向
- **想法**：`libil2cpp` 无 hash pin、可改，那就在它的 `getaddrinfo`/`connect` 桩上做文章。
- **做法**：v1–v10 共十几版脚本（`patch_il2cpp*` / `patch_connect*` / `patch_host*` / `patch_got*`），有改 PLT 首指令的、有改主机名的、有每次调用现场 `dlopen/dlsym` 的。
- **结果**：日志连 `IN` 都打不出来；游戏照常往官方 IP 连。
- **为什么失败**：**这两个导入在 libil2cpp 里根本没有调用点**。346 万条 `BL` 全段扫描：`getaddrinfo@plt(0xf2c1000)` = 0 条、`connect@plt(0xf2c1060)` = 0 条，而其它 65 个桩共被调 116,219 次。触发点不存在，桩永远不会被执行。
- **教训**：**先数调用点，再选落点**。`report/01-现状与已试方向.md:210` 当年归因成 `-fno-plt`，是错的（见 INDEX 附录 A-5）。
- **出处**：`report/02-注入链审计.md:23`、`report/00-下一步总方案.md:76`、`report/10-…:53`

### [D-20] 硬编码 GOT 偏移
- **想法**：`got_scan.py` 已经算出偏移，直接写死。
- **做法**：按固定偏移写 GOT 槽。
- **结果**：崩溃在 `strstr`，参数是 `0x2710`（10000）——把**别的函数**当 `getaddrinfo` 写了。
- **为什么失败**：偏移表被人工读错一格（`0x13d94d0` vs `0x13d94d8`，见 INDEX 附录 A-4），且硬编码本身就脆。
- **教训**：① 偏移必须**三重验证**（`.rela.plt` 符号表 + PLT 反汇编 + 机器码内嵌常量）；② 正确做法是运行时解析 `PT_DYNAMIC`/`DT_JMPREL` 按符号名找槽，**永不硬编码**。
- **出处**：`work/ba/audit/ba-pitfalls.md:25`、`report/02-注入链审计.md:176`

### [D-21] `dl_iterate_phdr` 里遍历**所有**模块
- **想法**：遍历全部已加载模块，找一个能用的。
- **做法**：回调里对每个模块无条件处理。
- **结果**：`SIGSEGV`，fault addr 是垃圾指针。
- **为什么失败**：实现缺陷——没校验 `e_phoff`/`e_phnum` 边界，遍历到异常/被 ACE 处理过的模块就崩。
- **教训**：只处理 `libunity` / `libil2cpp`，**必须**校验 ELF 头边界。`dlpi_addr` 本身是可信的（实测 == maps 里 `r-xp 00000000` 行）。
- **出处**：`work/ba/audit/ba-pitfalls.md:26`、`report/10-…:62`

### [D-22] 把结果写入"代码段里的 `.quad` 槽"
- **想法**：在代码洞旁边留个 `.quad` 当变量槽，存原函数指针。
- **做法**：注入代码 `str` 到代码段的 `.quad`。
- **结果**：`SIGSEGV(ACCERR)` —— 代码页只读。
- **为什么失败**：RX 段不可写（且 RELRO 更严）。
- **教训**：运行时变量必须放**可写段**：`libil2cpp` 的 `.data` 尾部 BSS `0x1024b4f8–0x10491d58`（约 2.28 MiB）是天然候选。
- **出处**：`work/ba/audit/ba-pitfalls.md:173`、`report/02-注入链审计.md:564`

### [D-23] 注入代码里调 `__android_log_print`
- **想法**：在桩里打 logcat 日志。
- **做法**：可变参直接调 `__android_log_print(4, "BAINJ", "…%p…")`。
- **结果**：`__strlen` 读到 `0x4`。之后 `g6.S` 再踩一次同样的问题。
- **为什么失败**：AArch64 可变参调用约定（寄存器/栈布局）手写错了。
- **教训**：`ver2.S` 改成"只把指针留寄存器、用单字符串打点"是正解；**注入代码里别用可变参**，写文件打点最稳。
- **出处**：`work/ba/audit/ba-pitfalls.md:175`、`report/02-注入链审计.md:199`

### [D-24] 运行时 `mprotect` 写 **libc** 代码页（inline hook libc）
- **想法**：inline hook libc 的 `getaddrinfo`（备份 16 B 到 tramp）。
- **做法**：`injb.S`/`inj4.S`，运行期 `mprotect(PROT_EXEC)` 后改入口。
- **结果**：SELinux 拒绝（**execmod**）。
- **为什么失败**：Android SELinux 默认禁止对 file-backed 代码页做可执行写。
- **教训**：只动**数据页**（GOT 槽），不动代码页；这也是为什么整套方案最终选"改 GOT 槽"而不是 inline hook。
- **出处**：`work/ba/audit/ba-pitfalls.md:176`、`report/02-注入链审计.md:212`

### [D-25] 运行时 `mprotect` + 写 **libil2cpp 自身** GOT
- **想法**：把 libil2cpp 自己的 GA/CO GOT 槽也改掉。
- **做法**：`patch_got7/8`，`dl_iterate_phdr` 找基址后 `mprotect` 写。
- **结果**：`SIGSEGV / SEGV_ACCERR (write)`，pc 落在洞内写 GOT 那条。
- **为什么失败**：`libil2cpp` 的 `.got.plt` 整段落在 `PT_GNU_RELRO [0xf2c4000, 0xfbb4000)` 内 —— RELRO 页只读，`mprotect` 也不一定救得回来。
- **教训**：**先判 RELRO 再选写入方式**；而且这两个槽本来就没调用点（见 D-19），改成功也没用。
- **出处**：`work/ba/audit/ba-pitfalls.md:194`、`report/02-注入链审计.md:76`、`:563`

### [D-26] `open("/proc/self/mem", O_WRONLY)` + `lseek` + `write` 写 GOT
- **想法**：绕开 `mprotect` 被拒，用 `/proc/self/mem` 直接写。
- **做法**：`O_WRONLY` 一次、`O_RDWR` 一次；`patch_direct.py` 加了写后回读打点。
- **结果**：`O_WRONLY` **静默失败**；改 `O_RDWR` 后日志正常（`IN/BA/DON` 出现），但网关流量**未转向**。
- **为什么失败**：当时以为是权限问题，实际是**基址取错 + `adr` 取到 0**（写到地址 0 附近），与写权限无关（见 D-28）。
- **教训**：`libunity` GOT 页本来就是 `rw-p`，**直接 `str` 写即可**，根本不需要 `/proc/self/mem`。
- **出处**：`work/ba/audit/ba-pitfalls.md:195`、`:243`、`report/10-…:57`

### [D-27] 整页「读-改-写」GOT
- **想法**：不用 `dd`/`str` 单槽写，而是读整页、改一槽、写回整页。
- **做法**：`dd` 读 4096 B → 改 8 B → 写回。
- **结果**：进程**直接死亡**。
- **为什么失败**：页内其它 GOT 槽可能**刚被懒绑定改写**，回写会把它们退回旧值（作者归因懒绑定；在 BIND_NOW 下更可能是 RELRO/并发写）。
- **教训**：**只做单 8 字节写**。这是硬规矩。
- **出处**：`work/ba/audit/ba-pitfalls.md:220`

### [D-28] 代码洞里用 `adr` 指向**全局符号**（`.globl`）
- **想法**：汇编里用 `.globl` 导出标签，`adr` 就能取到。
- **做法**：`blob0` 用了 `.globl`，直接把 `.o` 的 `.text` 抠出来不链接。
- **结果**：注入代码第一条 `blr` 就崩，`fault addr = 0x1c20`（正好 `|P_OPEN − CAVE|`），`#01 pc` 落在洞内 `blr` 那条。**看起来像算错偏移，实际是 `adr` 取到 0**。
- **为什么失败**：未链接的 `.o` 里，**全局符号的 `adr` 会留成未填的重定位（imm=0）**；只有**局部标签**才会在汇编阶段解析成 PC 相对位移。
- **教训**：① 段首放一个**局部标签** `Lb0`，`adr` 一律用它；② **离线就能判定**：`objdump -D -b binary -m aarch64`，看是 `adr x16, 0x0`（对）还是 `adr x16, 0x18`（错）。
- **出处**：`work/ba/audit/ba-pitfalls.md:223`、`report/02-注入链审计.md:227`

### [D-29] 把 `.rela.plt` 的 `R_AARCH64_JUMP_SLOT` 改成 `R_AARCH64_RELATIVE`
- **想法**：让 **loader 在重定位阶段替我们写 GOT**（不需要运行时可写页，天然持久）。
- **做法**：`patch_reloc2.py`，`r_info=(0<<32)|1027`、`addend=CAVE+off`。
- **结果**：链接器直接 abort，`exit-info status=6 (SIGABRT)`，进程秒退。
- **为什么失败**：结构本身是对的（`report/02:171` 明确说"结构是对的、不是纯死路"），失败原因未定；两个待查点：① bionic 是否允许 `.rela.plt` 里出现非 `JUMP_SLOT`；② 是否被 ACE 的完整性检查 abort（抓 logcat `linker`/`DEBUG` 就能分辨）。
- **教训**：这条**值得按 §8 复查**（是唯一不需要运行时可写页的方案），但不会再靠猜。
- **出处**：`work/ba/audit/ba-pitfalls.md:196`、`report/02-注入链审计.md:153`、`:171`

---

## D. Frida / LSPosed / il2cpp 符号

### [D-30] Frida（frida-server / attach / spawn）作为载体
- **想法**：Frida 能 hook 一切，直接看客户端判断。
- **做法**：`run_frida.py` / `run_spawn.py` / `hook_pfn.js`（hook 53 个 libtprt 函数）；改名、换端口、`spawn -f --no-pause` 都试过。
- **结果**：`exit-info reason=2 status=7`（**SIGBUS**，ACE 主动杀）。团队**确实 attach 成功过**，但**仓库里没有任何一份日志证明进程在 ACE 全功能开启下活过 30 秒**。
- **为什么失败**：4 条**必中项**绕不过——`/proc/self/maps` 的 `frida-agent`、线程名 `gum-js-loop`/`pool-frida`、端口 27042、`/proc/self/status` 的 `TracerPid`（attach 就 ptrace）。dex 里 `frida`/`27042`/`ptrace` 明文 0 命中 ⇒ 它**不靠字符串匹配**，靠行为/结构检测。
- **教训**：Frida 只能当**一次性侦察工具**（只观测、3–5 分钟撤），不能当交付载体。
- **出处**：`report/17-运行时hook方案评估.md:117`、`:130`、`:161`、`report/18-Frida与运行时绕过调研.md:63`

### [D-31] `frida-il2cpp-bridge`
- **想法**：这个库号称"不需要 `global-metadata.dat`"，一行 `dump` 就能替代 Il2CppDumper；还能直接 `CH.method("ValidateCertificate").implementation = () => true`。
- **做法**：`npm exec frida-il2cpp-bridge -- -f com.RoamingStar.BlueArchive dump`；或写 hook 脚本。
- **结果**：**必然抛 `Unable to find export`**（推断，依据是它内部走 `Module.getExportByName("libil2cpp.so","il2cpp_*")`，而本包导出名被抹成 0）。
- **为什么失败**：**不是 ACE 的问题，是符号表问题**。它的所有能力都建立在"能按名拿 il2cpp API"上。
- **教训**：看到"某工具不需要 metadata"时，要先问它**靠什么拿 API**。本项目的正解是"离线恢复符号表"（见 D-32 的对照）。
- **出处**：`report/17-运行时hook方案评估.md:12`、`report/18-…:114`、`report/38-Frida部署清单.md:190`

### [D-32] 把 AzusaBA 的 `xdl_sym` / `getaddr` 26 个 hook 原样搬过来
- **想法**：AzusaBA 5.2.5 是成熟的 il2cpp 符号驱动修改器，搬它的底座就能在国服跑。
- **做法**：直接用它 `il2cpp_api_init()`（200+ 个 `DO_API(xdl_sym)`）+ `getaddr(dll,ns,class,method,argc)`。
- **结果**（源码 + 事实推演，确定非猜测）：`xdl_sym` 依赖 `.dynsym` 的 `st_name` 比字符串 → 本 so 全空 → 返回 NULL → `il2cpp_domain_get` 为 NULL → `getaddr()` 在 `:874` 判空**直接 `return nullptr`** → `init_my_hook()` 在 `:1540` 等 `il2cpp_domain_get != nullptr` **永远等不到** → 60 s 后 return → `okHooks = 0/26`（UI 还能挂起来，但一个功能都没有）。
- **为什么失败**：符号解析层与目标文件不兼容。**「AzusaBA 在国服 3.0.2 跑通 26 hook」这个说法在国服不可能成立**。
- **教训**：可搬的是**底座**（`xdl` / `PtrHook::Patch` / `DobbyHook` / `HookUtils::Assemble` / safe-flag 二分），**不是符号解析策略**。改造只需把符号来源从 `xdl_sym` 换成离线恢复的地址表。
- **出处**：`report/17-运行时hook方案评估.md:88`、`:106`、`report/05-AzusaBA可复用资产.md:118`

### [D-33] 用 LSPosed/Xposed 的 Java hook 改**游戏自己的类**
- **想法**：hook `CertificateHandler`、hook 登录流程。
- **做法**：`XposedHelpers.findAndHookMethod("com.xxx.Foo", …)`。
- **结果**：`hookMethod`/`hookAllMethods` 全 `NoSuchMethodError`。进程内 `XposedBridge` 是**混淆替身类**（`LUnEw/z/NP/i/NLAT/v/Q/S/XposedBridge`）。
- **为什么失败**：App 自带同名 `de.robv.android.xposed.*` 替身，类加载器遮蔽。
- **教训**：**但这条不能推广成"LSPosed 无用"**——hook **框架类**（`javax.net.ssl.*`、`android.security.net.config.*`）不受影响，因为它们在 boot classpath、由 LSPosed 自己的 classloader 解析（`report/20:621`）。正确用法是"把 LSPosed 当进入进程的跳板，进入后一切靠 native"。
- **出处**：`work/ba/audit/ba-pitfalls.md:144`、`report/20-AndroidCA注入深度调研.md:615`、`report/05-…:492`

### [D-34] 用 Il2CppDumper 静态吃国服 `global-metadata.dat`
- **想法**：标准流程——`libil2cpp.so` + `global-metadata.dat` → `dump.cs` → 拿 `ValidateCertificate` 的 RVA。
- **做法**：`Il2CppDumper.exe libil2cpp.bin md.bin out\`。
- **结果**：第一步读 header 即废：magic `0x12724394`（非 `0xFAB11BAF`）、version `0xEC9E4B18`（无意义）、`stringLiteralOffset` 越界、全文件 0 处标准 sanity。12 种 stride×phase 扫 methods 表：**0 个候选**。
- **为什么失败**：头部（可能还有若干段）被加密/混淆，表区不是索引数组。
- **教训**：国服 metadata **只适合"按名查（字符串区明文）"，不适合"按表解析"**。任何"必须先解密头部"的方案都要先算清性价比。
- **出处**：`report/24-state接口schema反推.md:245`、`report/11-客户端静态逆向-网关与证书.md:100`、`report/01-现状与已试方向.md:224`

### [D-35] 运行期 dump 解密后的 metadata（"进程里已经解好了"）
- **想法**：静态解析不行，那就从 `/proc/pid/mem` 把 il2cpp 已解密的 metadata 整段 dump 出来，再喂 Il2CppDumper。
- **做法**：① 先扫 129 个 ≥4 MB 的 `rw-p` 映射的**前 16 KB** 找 `af1bb1fa` / `94437212`；② 放宽到 214 块（`r--p` + `rw-p`，含 dalvik-main 268 MB×2、LinearAlloc 1 GB×2），改用特征串 `CustomCertificateHandler`（meta 内偏移 4306927）反推基址；③ 全量 `dd | grep -abo`。
- **结果**：`af1bb1fa` = 0 命中、`94437212` = 0 命中、`CustomCertificateHandler` = **0 命中**（约 1.5 GB/s，2 秒跑完）。
- **为什么失败**：38.4 MB 的 metadata **不以"整块匿名 mmap 且头即 magic"形态存在**；也可能被 scudo 头/子分配切开或在 dalvik 堆内部。⇒ **内存里没有明文 metadata 字符串**。
- **教训**：这条同时否掉了 `report/14` 的整套"dump → Il2CppDumper → patch `mov w0,#1;ret`"计划。**别再试**；要拿方法地址，走"离线恢复符号 + `class_for_each` 枚举"（`report/17`）。
- **出处**：`report/06-手机基线恢复.md:491`、`:511`、`report/15-PEM公钥与pinning判读.md:198`

---

## E. 证书注入 / CA / pinning

### [D-36] 把 CA 装到三处 store（用户库 / `/system` / `/apex`）
- **想法**：只要 CA 进了信任库，客户端就会接受我们的证书。
- **做法**：① `/data/misc/user/0/cacerts-added/fd8b2b01.0`（819 B DER）；② `/system/etc/security/cacerts/`（PEM 1164 B，label `system_security_cacerts_file`）；③ `/apex/com.android.conscrypt/cacerts/`（同 PEM），冷启动后重打。
- **结果**：**三处全装、PEM/DER 都对、label 对、app 也读得到（`app ns: apex 147 / system 147`），TLS 仍被拒**。DNAT 计数器 89→205 包（+116 条新连接全到我们）。
- **为什么失败**：三个**不同**原因，不是一个：① 用户库在 `targetSdk=33` 下默认不被信任；② A14+ `getDirectory()` 在 APEX 非空时**完全忽略 `/system`** ⇒ 写 `/system` 是死代码；③ 写进 APEX 的文件**不在 App 的 mount namespace 里**（`/apex` 是 private propagation）。
- **教训**：**先判"哪个 store 被选、在哪个 ns"再动手**。正确做法：建影子 store → `mount --rbind` 进 **zygote** ns → 对已在跑的 App 补挂 → `kill -9` 冷启（`report/20:347` 有可抄的完整脚本）。
- **出处**：`report/20-AndroidCA注入深度调研.md:18`、`report/21-决策日志-CA路线攻坚.md:18`、`report/06-手机基线恢复.md:603`

### [D-37] 只往 `/system/etc/security/cacerts` 拷（"系统 CA 就够"）
- **想法**：系统目录是最终真相。
- **做法**：`cp` + `chmod 644` + `chcon`。
- **结果**：不起作用（且**越努力越没用**）。
- **为什么失败**：A14+ 的 `SystemCertificateSource.getDirectory()` 在 APEX 目录存在且非空时**直接返回 APEX 路径，`/system` 那份连打开都不会打开**。
- **教训**：这条是"看起来最自然、实际是死代码"的典型。若真要用 `/system`，唯一开关是 `system.certs.enabled=true` —— 而它必须在 **zygote 起来之前**设（= 要模块 + 重启），性价比低。
- **出处**：`report/20-AndroidCA注入深度调研.md:171`、`:521`、`:611`

### [D-38] 在自己 ns 里 `mount -t tmpfs` 再 `cp` 进 `/apex/.../cacerts`
- **想法**：`/apex` 不可写，就挂个 tmpfs 上去再写。
- **做法**：`mount -t tmpfs tmpfs /system/etc/security/cacerts`（或对 `/apex` 同样做法）→ 搬回原厂证书 → 加我们的 → `touch` 验证可写。
- **结果**：自己 ns 里一切正常（`ls` 能看到 147 个、`cat` 出 `-----BEGIN CERTIFICATE-----`），App 仍不信任。
- **为什么失败**：**`/apex` 是 private propagation**。基础挂载全局可见（所以 `nsenter` 进去看 `dev/ino` 一致——这个观察是**对的**），但**任一 ns 里新加的 mount 不会向任何其它 ns 传播**。你写的是自己 ns 里的影子目录。
- **教训**：判据只有一条——**在 App 自己的 ns 里** `ls -lZ` + `cat`（`nsenter --mount=/proc/<apppid>/ns/mnt -- /system/bin/ls -lZ …`），自己 ns 里的验证全是自我安慰。
- **出处**：`report/20-AndroidCA注入深度调研.md:309`、`:296`、`:313`

### [D-39] 用 `cp -a` / `mv` 把证书搬进信任库
- **想法**：`cp -a` 保留属性更"规范"。
- **做法**：`cp -a /data/local/tmp/fd8b2b01.0 /apex/.../`
- **结果**：label 被带成 `shell_data_file` / `media_rw_data_file`，App 静默读不到（`DirectoryCertificateSource.readCertificate()` 打一条 `Log.e` 后 `return null`，**什么都不报**）。
- **为什么失败**：普通 `cp` 的新 inode 会**继承父目录 label**（通常就对），而 `cp -a` 会显式写源 xattr 覆盖这个继承结果。
- **教训**：装完必须 `ls -lZ` 实证；`chcon --reference=<同目录原厂文件>` 是最稳的写法。`restorecon` 在 tmpfs 上**别用**（不参与 `file_contexts` 恢复，常常"跑了但没改"）。
- **出处**：`report/20-AndroidCA注入深度调研.md:211`、`:244`、`report/06-手机基线恢复.md:601`

### [D-40] 重打包改 `networkSecurityConfig`（把我们的 CA 设成 app 级 trust-anchor）
- **想法**：不用动系统库，只要 app 自己信任我们。
- **做法**：改 manifest 加 `android:networkSecurityConfig` + `<certificates src="user"/>`。
- **结果**：**本 APK 根本没有这个属性**（`AndroidManifest.xml` 里 `grep 'networkSecurityConfig|cleartext|network'` 全空；`res/xml` 只有 `filepaths.xml` / `http.xml` / `sdk_file_provider_paths.xml` / `standalone_badge*.xml` / `tapupdate_file_provider.xml` / `unitywebview_file_provider_paths.xml`）。
- **为什么失败**：① 属性不存在（要自己加，等于重签 + 承担签名变化）；② 即便加了，Unity 用自己的 TLS 栈，"Unity 不理会 networkSecurityConfig"是有据的说法；③ 重签会改签名，直接撞 ACE 的 `sourceDir` 完整性面。
- **教训**：这条路对 Unity 游戏**大概率无效**，且代价最高（重签）。别再作为首选项。
- **出处**：`report/06-手机基线恢复.md:628`、`report/12-外部资料-证书与网关重定向.md:387`、`report/18-…:213`

### [D-41] 替换 Unity 内置 CA bundle
- **想法**：如果 Unity 用自己的 CA 包，那就改那个包。
- **做法**：全量扫 APK `assets/`、`libunity.so`、`libil2cpp.so`、`global-metadata.dat`、`assets/aa/catalog.json`（81 MB）找 `BEGIN CERTIFICATE` / `BEGIN PUBLIC KEY` / SPKI 前缀。
- **结果**：**APK 无任何 cacert/pem/cer/der**；`libunity` 的 `-----BEGIN PUBLIC KEY-----` 是 **libcurl 自带的 PEM 标签串**（上下文 `CURL_SSL_BACKEND`/`ALPN`）；`libil2cpp` 与 metadata 的 `BEGIN CERTIFICATE` = 0；catalog.json 的 4 处长 base64 是二进制误报。
- **为什么失败**：**根本没有内嵌 CA bundle 可换**。
- **教训**：这条把"替换资源"整条路线判死。剩下的可能只有"Unity 用内置 CA 数组"或"游戏在托管层自定义校验"（`report/19:81`）。
- **出处**：`report/06-手机基线恢复.md:461`、`:503`、`report/19-网关攻坚-当前状态.md:48`

### [D-42] 把官方叶证书塞进我们的链里 / 伪造 DN 与 serial（假设是"朴素包含式 pinning"）
- **想法**：如果 pinning 只是"证书 blob 里包含官方证书"，那把官方叶证书作为**第二条证书**塞进我们发的链里就能过（TLS 只用第一张，握手能成）。
- **做法**：① `cat` 官方叶证书到我们 fullchain 末尾；② 伪造 DN 逐字为 `RapidSSL TLS RSA CA G1`；③ 伪造 serial 与官方一致（`020E898BACE422961BAE37D684049427`）；④ 链补到 2 张 / 3 张。
- **结果**：**全部无变化**（仍拒）。
- **为什么失败**：pinning 假设本身就建立在一个后来被推翻的前提上（见 INDEX 附录 A-10）；真实问题是链的根不在信任库里 / 客户端落在错误的 vhost。
- **教训**：**在错误的假设上做的"精巧实验"毫无价值**。做之前先花 10 分钟确认"49 到底是谁发的"。
- **出处**：`report/19-网关攻坚-当前状态.md:44`、`:45`、`report/15-…:171`

### [D-43] 用 `listen 443 ssl default_server` 解释并修复"客户端不发 SNI"
- **想法**：pcap 看到 ServerFlight 只有 1352 B ≈ 无 SNI 的 1355 B（vs 带 SNI 的 2601 B）⇒ 客户端落在 `0.default` 拿了 `CN=default` 证书 ⇒ 这才是根因，加 `default_server` 一行就解决。
- **做法**：`ba_mitm.conf:2` 改成 `listen 443 ssl default_server;`（备份 `ba_mitm.conf.bak.1794590779`）；重载后无 SNI 时 ServerFlight = **2597 B**，三条自验通过。
- **结果**：**屏幕仍报「请确认网络连接状态后重试」**。后来 pcap 显示 `state-api` 的 ClientHello **353 B 明确带 SNI**，且 TLS 全程走完、nginx 解出明文 `GET /api/state` 并回 200。
- **为什么失败**：那条"无 SNI"的 ClientHello 来自**别的连接**（很可能是 `gsqc` 或裸 IP 连接）；`0.default` 假设虽然解释了 ServerFlight 差异，但**不是阻断点**。
- **教训**：① 拿到 pcap 的第一件事应是**比对 ClientHello 有无 SNI + ServerFlight 字节数与对照**，而不是先装 CA/补链；② 一个能"解释现象"的假设 > 一个能"改变现象"的假设，**后者才算证据**。
- **出处**：`report/19-网关攻坚-当前状态.md:21`、`report/06-手机基线恢复.md:572`、`:586`、`report/23-主线改判-TLS已通应用层卡点.md:14`、`:48`

---

## F. 网关响应 / 协议层（本轮最新）

### [D-44] `Account_Auth` 响应的**四种变体** —— 客户端行为完全一致
- **想法**：客户端拿到 200 却不动，那一定是"响应格式不对"。把格式的几种可能都试一遍就能找到对的那种。
- **做法**：桥接器依次输出 4 种响应（每轮**只改一个变量**、冷启动、六帧截图 + conntrack 采样）：
  1. **原封不动的 http 404**（桥前：nginx 直 `proxy_pass` 到 Shittim 5000，Shittim 没有该路由）→ 屏幕「通知 / **服务器处理请求失败**。将返回标题画面。」；
  2. **Error envelope**（`{"protocol":"Error","packet":"{…ErrorCode:500…}"}` 这一族）→ 同样「服务器处理请求失败」；
  3. **真实明文 3740 B**（wire-dump 出来的真响应，24 键）→ **无弹窗**，标题页提示文字淡出、CPU 80%+，**但无第二条协议请求**；
  4. **真实加密响应 4491 B**（`encresp1`，明文 4452 B）→ **与 ③ 完全一致**：无弹窗、仅 1 条 gsqc 请求、无后续协议、catalog 未重写。
- **结果**：**③④ 两种"看起来对"的响应，客户端反应一模一样**；②① 也都只停在"失败弹窗"。逐轮判据：fresh `conntrack sport` 新增恒为 **1 条**（未达"≥2 条"阈值）；`catalog_Remote.hash` / `manifest.db` 只在冷启动期被重写且**值不变**；`shared_prefs` 02:54 后无改动；`grep -E 'E/Unity|NullReference'` = **0 行**。
- **为什么失败**：客户端的判断**不在"响应体形状"这一层**。它收到 200、能解析、不报错、也不落盘任何账号状态 ⇒ 更像**解析后在内存里等某个字段/某个后续条件**，或者把响应当成"非法数据静默丢弃"。
- **教训**：① 先把"客户端到底消费了没有"这条判据钉死（见 D-45）；② **"无弹窗"不等于"成功"**——它可能只是"静默停住"；③ 一次只改一个变量（这一条实验纪律在 D-44 的四轮里执行得很好，是少数"即使失败也干净"的实验）。
- **出处**：`report/21-手机侧执行记录.md:1229`（404 那轮）、`:1430`（明文 3740 B）、`:1572`（WAF 关 + decrypt+plain）、`:1616`（加密 4491 B 与明文完全一致）、`:1617`

### [D-45] 「客户端不发第二个协议请求」的证据链（不是一次观测，是四路交叉）
- **想法**：`/api/account/auth` 是首包，那后面必然还有第二个协议（`Session_Info` / `Account_LoginSync` / `Echelon` …）。只要网关回对了，第二条就会来。
- **做法**：四路同时取证，每轮冷启动后都重测：
  1. **conntrack fresh sport 差分**：把冷启动前 gsqc 的 sport 集合做基线，点击后看新增数量（`38476/40230/43424/47104 + 51190` ⇒ 新增 **N=1**，未达 ≥2 阈值）；
  2. **`ss -tnp`**：点击后只有 1 条新的 gsqc `TIME_WAIT`，其余全是旧连接；
  3. **文件系统**：近 3 分钟被写的文件只有 `BundlePackingInfo.hash / TableCatalog.hash / MediaCatalog.hash / manifest.db / patch_assetmanifest / catalog_Remote.hash`，**全部是冷启动期、值不变**；`shared_prefs` 四个关键文件 mtime 停在 02:54:13（SDK 自己写的）；
  4. **logcat 全量**（10583 行 / 1.65 MB）：`[VDIWEF]/Unity` = **0 行**，app 自身日志窗口内**只有 2 行**（IME 扩展查询 + jank_cuj），`il2cpp/unity/mono/BestHTTP/System.` 无一条来自 App，`ssl/tls/socket/timeout/EOF` 全是系统噪声。
- **结果**：四条**独立**证据一致指向"客户端只发了 1 条、然后本地停住"。
- **为什么失败**（作为推进手段失败）：它只证伪，不给出原因。而且 `catalog` hash 的"值不变"说明客户端**确实完成了 catalog 校验**——也就是说它比"停住"走得更远。
- **教训**：① 判"客户端有没有发第二个请求"**不能**只看 `ss`（DNAT 前 peer / 端口复用 / 长连接干扰）；必须 **conntrack fresh sport + 文件 mtime + logcat** 三路对齐；② `wq.txt` 那种"按对端地址去重"的采样法**无法捕获同 IP 的新连接**，是废方法（`report/21:1535` 自己记了）。
- **出处**：`report/21-手机侧执行记录.md:1586`、`:1608`、`:1611`、`:1439`、`:1535`

### [D-46] 用 HTTP 状态码 / 响应头去"探测客户端行为"（404 会弹窗）
- **想法**：客户端对不同的 HTTP 语义会有不同反应，那就用状态码当探针：回 404 看它弹什么、回 200 空 body 看它是否继续、回 200+HTML 看它是否解析失败。
- **做法**：① `static` 回 **404 + 记 URI**；② `state-api` 回 **200 + content-length 0**（真实上游也是 0）；③ 宝塔 WAF 把 multipart POST 换成 **200 + `text/html`**；④ 真实 676 B DTO A；⑤ `ResultState=0` 注入未知字段。
- **结果**（这张对照表可复用）：
  | 服务端给什么 | 客户端表现 |
  |---|---|
  | `static` 404 | 弹窗换成「**通知 / 网络连接失败，请确认网络连接情况。**」，按钮变"重启/重试" |
  | `state-api` 200 + **0 字节** | `NullReferenceException at ServerInfoDataRepository.GetApiServerInfo`，弹窗消失、画面卡住 |
  | WAF 的 **200 + text/html**（172 B） | 解析失败、无额外提示 ⇒ 与"200 但不动"同貌 |
  | 真实 **3740 B** 明文 | 无弹窗，但仍不发第二条 |
  | 真实 **4491 B** 加密 | 同 3740 B，**完全一致** |
  | 注入未知字段 `ResultState:0` | **完全没变化** ⇒ 客户端忽略未知字段 |
- **为什么失败**：这套探针能**区分层级**（网络层/解析层/业务层），但**不能逼出"下一跳"**。而且 200+HTML 这一条证明了一个重要陷阱：**200 不代表内容对**。
- **教训**：① 状态码只能定位到"哪一层"，不能定位"缺什么"；② **先查 WAF**——它能在你不知情的情况下把 JSON 换成 HTML（见 D-49）；③ 判定要用**像素级弹窗检测**（`_tmp/chkcard.py`，蓝色按钮色 ≈RGB(119,221,255)，已知弹窗 `btn_px=58439`），**文件体积不可作判据**（浅色背景标题页也落在 1.2–1.4 MB）。
- **出处**：`report/21-手机侧执行记录.md:1146`、`:1496`、`:1533`、`:1575`、`report/25-根因定案-状态接口schema错误.md:63`

### [D-47] 用一个 `location = /api/state` 通吃所有 Host
- **想法**：所有 `*.bluearchive-cn.com` 共用一个 server 块，`/api/state` 就回一份 JSON，简单。
- **做法**：`ba_mitm.conf` 里 `location = /api/state { return 200 '{"Servers":[...],"State":0,...}' }`，两个 conf 同步改。
- **结果**：`state-api` / `gsqc-api` / `static` 全回同一份 180 B。第二轮：`state-api` 0 字节 → **NRE**；第三轮补 `Servers` → NRE 消失但**客户端零 gsqc 连接**；真实 676 B DTO A 到手后才发现 gsqc 要的是**完全不同的大 DTO**。
- **为什么失败**：`/api/state` 是**两个不同接口**（两个 DTO）：`state-api` → `{Servers,State,Msg}`；`gsqc-api`/`gs-api` → `ServerInfoConnectionGroupData`（24 属性，实测只发 10 字段）。用第二跳的 JSON 去反序列化第一跳的 DTO，必然全字段 null。
- **教训**：**按 Host 拆 server 块**（`state-api`+`stateqc-api` 一块 / `gsqc`+`gs-api` 一块 / `static` 一块）。这条后来实测确认可行（`report/22-服务端取证记录.md:284` 的 struct1 + dto1）。
- **出处**：`report/24-state接口schema反推.md:414`、`report/25-根因定案-状态接口schema错误.md:50`、`report/22-服务端取证记录.md:292`

### [D-48] `static` 回 404（"先不管资源"）
- **想法**：静态资源 11 GB 都在手机本地，远端 404 应该无所谓。
- **做法**：`static` server 块 `return 404;` + 独立日志。
- **结果**：真实 676 B DTO A 上上去之后，弹窗**从「提示/空白」变成「通知 / 网络连接失败，请确认网络连接情况。」**，客户端首次连 `static`（`120.226.195.66:443`，CLOSE-WAIT rx=24B）。
- **为什么失败**：客户端**在拿完 DTO A 之后确实要连 static**（至少做一次校验/拉 catalog 元数据）。404 直接把它打到"网络失败"分支。
- **教训**：把 `static*` 从 MITM 改成 **SNI 透传真 CDN**，一行解决 —— 之后客户端首次进入**完整标题界面**（`n1`8s 无弹窗 / `n2`16s 完整标题页）。这是整晚少数"一个改动直接推进一个阶段"的例子。
- **出处**：`report/21-手机侧执行记录.md:1146`、`:1157`、`:1184`

### [D-49] 宝塔「Nginx免费防火墙」(`free_waf`) 把请求换成 200 + HTML
- **想法**：把请求打到我们的桥，看客户端怎么处理 200。
- **做法**：`POST /api/account/auth`（multipart，body 1138 B）经 nginx 转发。
- **结果**：两次实测返回体是 **`<html><meta charset="utf-8" /><title>from-data请求error</title><div>宝塔免费WAF提醒您,from-data 请求异常,…</div>`，`HTTP 200 · Content-Type: text/html · 172 字节`**。
- **为什么失败**：`config.json` 里 `post: 403` 规则按"POST 参数里的 SQL 注入/XSS"启发式判定，multipart 被判异常后 WAF **用 200 + HTML 顶替**（不是 403！）。客户端收到 200 但内容不是 JSON ⇒ 必然解析失败、且不报错。
- **教训**：① **200 不代表内容对**；② `ba_mitm.conf` 是**手工配置的 vhost，不是"宝塔站点"**，`site.json` 里没有它 ⇒ 面板里"按站点关"对它无效，只能动全局规则；③ **关 WAF 必须由用户在面板里手动做**（`report/23` 明确写"任何自动化程序/agent 均不得执行本文中的操作"）；④ 关掉后行为完全不变（`report/21:1571`）⇒ WAF 是"真实变量但非当前卡点"。
- **出处**：`report/21-手机侧执行记录.md:1496`、`:1500`、`:1571`、`report/23-手动关闭宝塔WAF操作指引.md:3`、`:35`

### [D-50] 改 `Config/ServerInfoConfig.json` 的连接组 URL（把 loopback 换成公网）
- **想法**：客户端拿到的 `ApiUrl` 是 `http://127.0.0.1:5000/api/`（对手机不可达），改配置文件就行。
- **做法**：手改 `Config/ServerInfoConfig.json` 的 `ConnectionGroupsJson`；或改 `Config.json` 的 `HostAddress`。
- **结果**：被**双重重置**：`Config.Save()` 的 `ApplyLocalhostAddress()` 把 `HostAddress` 钉回 `127.0.0.1`；`ApplyGatewayMode` 见到任何非空 URL 就**整份重建为官方默认**。
- **为什么失败**：源码级硬编码（`Config.cs:111-117` / `:199-201` / `:237` / `:242`）。
- **教训**：唯一不碰源码/防火墙的做法是 **nginx `sub_filter` 改写响应体**——**但已被明确"暂缓，不要上"**（第一层还没通，先解决第二层没意义）。`report/09:479` 有完整片段，留档未应用。
- **出处**：`report/09-服务器盘点.md:457`、`:472`、`:494`

### [D-51] 开 `UseCustomExcel=true`（归档里的"正确做法"）
- **想法**：`ba-pitfalls` 说要用 `UseCustomExcel=true` + `DownloadExcelTables=false` 防止服务端覆盖明文库。
- **做法**：`deploy2.sh`/`deploy3.sh` 写进 `appsettings.json` / `appsettings.Local.json` + 环境变量。
- **结果**：`[INF] Custom Excel is Enabled` → `[WRN] Falling back to expired cache` → **`[FTL] An unhandled exception occurred`**，`InvalidOperationException: An invalid request URI was provided`（`ResourceService.cs:151`）。
- **为什么失败**：`LoadResources` 在 `useCustomFile=true` 时**先 `ResetDumped()` 删掉整个 `Resources/Dumped`（含 311 MB ExcelDB.db）**，再用空 `CdnBaseUrl` 拼 `/Preload/TableBundles/ExcelDB.db`（绝对路径不是绝对 URI）→ 抛异常。
- **教训**：① **`Config/Config.json` 才是生效配置**，`appsettings*.json` 对它无效；② 归档里那条建议**在本机不可执行**，会直接炸掉现存资源；③ 改任何"资源下载开关"前先备份 `Resources/`。
- **出处**：`report/09-服务器盘点.md:141`、`:156`、`report/13-总账-2026-11-14凌晨.md:127`

### [D-52] 用 JSON 打 `/api/gateway`（"Content-Type 错配最多 415"）
- **想法**：Shittim 是 ASP.NET Core 的 API，信封是 JSON，那 `Content-Type: application/json` 应该能通。
- **做法**：`curl -X POST -H 'Content-Type: application/json' --data '{...}' http://127.0.0.1:5000/api/gateway`。
- **结果**：**500**，原文 `System.InvalidOperationException: This request does not have a Content-Type header. Forms are available from requests with bodies like POSTs and a form Content-Type of either application/x-www-form-urlencoded or multipart/form-data`（`GatewayController.cs:160`）。带 `x-www-form-urlencoded` → **400 `Expecting an mx file`**。
- **为什么失败**：`GatewayRequest()` 第一步就是 `Request.ReadForm()`，然后 `Request.Form.Files.GetFile("mx")`。它**只吃 multipart 的文件字段**。
- **教训**：① **500 ≠ 鉴权失败 ≠ 协议号错**，先看异常原文；② 正确姿势 `curl -F 'mx=@out.mx'`；③ `POST /api/gateway` 在 **5000 和 5100 上都能打**（同一进程同一路由表）。
- **出处**：`report/09-服务器盘点.md:441`、`:449`、`report/28-Shittim网关协议源码核对.md:185`、`scripts/NOTES-gateway.md:26`

---

## G. 取证方法论 / 运维判读

### [D-53] 用 `access_log` / `error_log` 判 TLS 是否通过
- **想法**：nginx 日志里有请求 = TLS 通了；`error_log` 空 = 握手成功。
- **做法**：`grep -c UnityPlayer ba_mitm.log`、`wc -c ba_mitm.error.log`。
- **结果**：`error.log` **全程为空**，但客户端一直在发 alert；后来才发现"alert 后正常 FIN，nginx 不记 error"。
- **为什么失败**：① `access_log` 是**请求结束时**才写；② `error_log` 对"对端 alert 后 FIN"这种正常关闭**不记录**。
- **教训**：**判 TLS 只认 pcap**：ServerFlight 之后是否出现 `GET`/`POST`/`PRI *`/应用数据记录。这条后来写进了三份报告的红线。
- **出处**：`report/22-服务端取证记录.md:93`、`report/25-根因定案-状态接口schema错误.md:110`、`report/21-决策日志-CA路线攻坚.md:103`

### [D-54] `tcpdump` 用 `not src net 172.24.0.0/16`
- **想法**：排除我们自己发出去的噪音。
- **做法**：`tcpdump 'not src net 172.24.0.0/16'`。
- **结果**：`tls_min.pcap0` / `r_013747.pcap` 里 **`srv=0`**（一条服务端方向的包都没有），ServerFlight 完全消失，只能靠"客户端 ACK 差值"倒推。
- **为什么失败**：**服务器自己就在 `172.24.44.228/20` 这个网段**，`not src net` 把整条服务端 flight 滤掉了。
- **教训**：① 用**无方向过滤**或按客户端 IP 钉死；② 这条是 Lead 亲自写错又亲自纠正的口径，说明"过滤条件"本身就是高危操作。
- **出处**：`report/22-服务端取证记录.md:73`、`report/23-主线改判-TLS已通应用层卡点.md:92`、`report/25-…:112`

### [D-55] `tcpdump -s 512` 截断 + 按端口聚合会话 + 用 TLS 1.3 读 alert desc
- **想法**：省空间用 `-s 512`；按端口把流量归成"会话"；看到 19 B 的 `17 03 03` 就以为是 alert。
- **做法**：`-s 512`；`25_pcap_v2.py`/`26_pcap_v3.py` 按端口聚合；对 `14 03 03 00 01 01` + `17 03 03 …` 序列直接判读。
- **结果**：记录长度对不上，走出 `T0(0)`/`Txxx` 垃圾；按端口聚合**把不同连接串在一起**（手机端口快速复用）；19 B 的 `17 03 03` 不是 alert 本身。三个早期脚本因此全部废弃。
- **为什么失败**：① 截断破坏 TLS 记录分帧；② 端口不是会话标识（**ISN 才是**）；③ **TLS 1.3 的 alert 一律加密**，要看明文 desc 必须让连接走 **TLS 1.2**。
- **教训**：`-s 0`；**按 ISN 分连接**（`35_window.py` 起）；Alert 明文扫描找 `15 03 03 00 02 XX`。改完立刻拿到 46 条 `desc=49` 的关键统计。
- **出处**：`report/22-服务端取证记录.md:250`、`:252`、`:253`、`:254`

### [D-56] 拿 `mark=262253` 当"包到了我们服务器"的证据
- **想法**：conntrack 里有 `mark=262253` 且有 `reply src=<SERVER_IP>`，说明流量被 DNAT 到我们了。
- **做法**：`cat /proc/<pid>/net/nf_conntrack | grep <SERVER_IP>`。
- **结果**：`sport=36690` 在 `r_013747.pcap` 与 `allport_020316.pcap` 里**0 包**。
- **为什么失败**：`mark` + `reply src` 改写只证明**手机侧 iptables 规则匹配了、conntrack 建了条目**；包可能在出网路径被代理 App 截走。
- **教训**：**判断连接有没有到我们，只认 pcap 里有没有这个 5 元组的包。**
- **出处**：`report/29-进度-网关未调用与判据纪律.md:69`、`scripts/NOTES-gateway.md:55`

### [D-57] 用 `tcp-access.log` 抓客户端流量 / 用 `grep 目标IP` 查它
- **想法**：`tcp-access.log`（stream 层）有连接记录，`grep 39.174.179.5` 就能看到客户端有没有连官方网关。
- **做法**：`grep 39.174.179.5 /www/wwwlogs/tcp-access.log`。
- **结果**：恒为 0 —— 对"被劫持"和"被绕过"两种情形**都成立**。
- **为什么失败**：被接管的连接上游写的是 `127.0.0.1:8443`，**永远不会出现 `39.174.179.5`**；而且该日志是**会话结束时**才落一行，用它否定一条仍 ESTAB 的长连接也无效。
- **教训**：**先问"这条日志在什么时机写入、记的是哪一段地址"**，再决定能不能用它。这是同一个毛病的三个变体（时机 / 方向 / 覆盖范围）。
- **出处**：`report/29-进度-网关未调用与判据纪律.md:70`、`:71`、`scripts/NOTES-gateway.md:64`

### [D-58] 用 `ss` 判断"流量是否全到我们"
- **想法**：`ss -tnp` 里对端只剩 `<SERVER_IP>` 就说明全导过来了。
- **做法**：`ss -tnp | grep <pid>`。
- **结果**：做了 38 条逐条 DNAT 后，`ss` 里仍是官方 IP 列表；一度以为 DNAT 没生效。
- **为什么失败**：**`ss` 显示的是 DNAT 之前的原始 peer**（`nat OUTPUT` 只改报文目的地址，不改 socket 表示）。
- **教训**：判断"流量是否全到我们"只能用 **DNAT 计数器**（`iptables -t nat -L OUTPUT -n -v`）+ 服务端日志；`ss` 只能看"客户端想连谁"。
- **出处**：`report/06-手机基线恢复.md:544`

### [D-59] 凭 IP 反推域名
- **想法**：`ss` 里看到 `39.174.179.5:443`，那就是 `gsqc-api` 在连。
- **做法**：直接用 IP 归属下结论（"游戏连上 gsqc 了" / "有绕过 DNAT 的流量"）。
- **结果**：`nslookup` 复现：`gsqc-api.bluearchive-cn.com` 与 `udata-api.open.yostar.net` **共用同一组 IP**（`39.174.179.5` / `39.173.157.74` / `112.13.210.86`）。那条 ESTAB 实际是 **udata** 的 keep-alive。
- **为什么失败**：阿里 SLB 上多个域名共用同一组 IP。
- **教训**：认域名**只能看 DNS 解析记录或 SNI**，不能凭 IP 反推。同时"不存在绕过 DNAT 的游戏流量"这个结论要靠四路排查（同 netns + 无分身 + DNAT 计数在涨 + conntrack mark）才能成立。
- **出处**：`report/29-进度-网关未调用与判据纪律.md:72`、`report/21-手机侧执行记录.md:937`、`:957`

### [D-60] 盯 `ba_mitm.log` 找手机流量
- **想法**：手机所有请求都该在 `ba_mitm.log` 里。
- **做法**：`tail -f /www/wwwlogs/ba_mitm.log | grep '/api/state'`。
- **结果**：手机 IP `117.147.55.174` 在 `ba_mitm.log` 里命中 **0**，在 `example.com.log` 里 **281** 条。
- **为什么失败**：`sdkcard.py:78-81` 的 `fix()` 把主机名**改写成 `example.com`**，所以这些请求走 `example.com` 的 vhost，只进那个日志。
- **教训**：**采集器必须同时 tail 两个日志**（`/root/ba_watch/watch.sh` 就是这么写的），且要 `tail -F -n0`（默认 `-n10` 会回放历史造成误判）。盯错日志 = 得出"客户端没打进来"的错误结论。
- **出处**：`report/09-服务器盘点.md:778`、`:892`、`:893`

### [D-61] nginx `alias` 指向 `/root` 目录
- **想法**：把 `/api/state` 的 body 文件放 `/root/bapatch/state/`，nginx `alias` 过去最省事。
- **做法**：`location = /api/state { alias /root/bapatch/state/state-api/api-state.json; }`。
- **结果**：**403**。
- **为什么失败**：`nginx.conf:1` 是 `user www www;`，而 `/root` 是 `dr-xr-x---`，worker 进程根本进不去。
- **教训**：body 文件必须放 `/www/wwwroot/` 下（最终落 `/www/wwwroot/bapatch/state/`）。**改 nginx root/alias 前先看 `user` 指令和目录权限**。
- **出处**：`report/22-服务端取证记录.md:344`

### [D-62] 经 SSH/PowerShell 直传含中文或引号的脚本（heredoc 一类）
- **想法**：把一段带中文注释、含 `$`/引号/`&` 的脚本直接管道给远端 `bash` 执行。
- **做法**：PowerShell 里拼字符串 → `ssh root@host 'bash -s' <<< "$script"`（或 `bash -s < file` 的等价写法）。
- **结果**：脚本在远端报**语法错误**、整段执行失败；若这条命令恰好是同一次操作里"改 nginx 并 reload"的前半步，就会留下**服务不可用**的状态（对外表现为 5xx）。团队的实际处置是：**一律落盘 `.sh` 再 `bash -s`，脚本保持纯 ASCII**。
- **为什么失败**：PowerShell → ssh → 远端 shell **三层解析**，中文编码 + 引号 + `$` 插值被反复消费；手机侧同族问题是 toybox `sed` 里 `&` 被当成"整段匹配"占位符，第一次干跑把行改坏成 `&quot;Enable&quot;:truequot`。
- **教训**：① **脚本一律先落盘再执行**，不要 heredoc 直灌；② **注释与字符串保持纯 ASCII**（中文写进报告，不写进被远程执行的脚本）；③ 任何"改配置 + reload"的命令都要**先 `-t` 校验、再 reload、并准备一条回滚命令**（`report/22-服务端取证记录.md:300` 的回滚写法就是范本）。
- **诚实标注**：41 份顶层报告里**没有单列"heredoc 写中文注释导致 502"这一条**。这里收录的是同族、且**有原始记录**的两条（ssh 直传中文/引号、toybox `sed` 的 `&`）。如果确实发生过 502 那次，属于**未落档**——补档时请补上"命令原文 / 错误输出 / 恢复步骤"。
- **出处**：`report/22-服务端取证记录.md:255`、`report/21-手机侧执行记录.md:672`

---

## H. 手机侧操作

### [D-63] 用 `cat > dst` 覆盖 `.so`
- **想法**：把 271 MB 的 patched so 写进 `/data/app/.../lib/arm64/libil2cpp.so`。
- **做法**：`cat /data/local/tmp/x.bin > $DST`。
- **结果**：命令被中断后文件被 `O_TRUNC` 截成 **0 字节**；`dlopen` 报 `file offset for the library "libil2cpp.so" >= file size: 0 >= 0`；`UnityPlayer.loadNative` → `JNI FatalError` → 进程 abort，**0.3 秒一次的重启循环**持续到 00:13:48 之后。
- **为什么失败**：`>` 是 `O_TRUNC` 语义，写入未落地就留 0 字节；而客户端每 0.3 s 重启一次，**在窗口里抢跑**。
- **教训**：**铁律**——永远 `cp` 到同目录 `.new` → `sha256sum` 校验 → `restorecon` → `mv -f`（rename(2)，无 0 字节窗口）。
- **出处**：`report/06-手机基线恢复.md:353`、`report/07-dlopen报错考证.md:15`、`report/13-…:181`

### [D-64] 用 `input tap` / `sendevent` 点 Unity 界面
- **想法**：自动化点击"确定"和"点击任意区域进入游戏"。
- **做法**：① `input tap 1398 919`；② `sendevent /dev/input/event5` 注入单次轻触（raw = 像素×16，中心 raw(10176,22400)）；③ 加 `PRESSURE` + 250 ms 长按；④ 点右上「×」对照 raw(3728,16256)。
- **结果**：① `Failure calling service input: Failed transaction (2147483646)`（SELinux 挡）；②③④ **事件确实进队列了**（`dumpsys input` 回读 `raw/16 = 表面坐标`），但**弹窗纹丝不动**。
- **为什么失败**：**Unity SurfaceView 不响应注入触摸**（`input` 通道被 SELinux 封；`sendevent` 到了内核但 Unity 的输入处理不认）。
- **教训**：点击类操作**交由用户手动完成**。判据设计上要避免"必须点一下"的实验；`deviceId=-1` 的注入事件 6×10s 采样恒为 18（不增长）⇒ 非持续注入，可忽略。
- **出处**：`report/21-手机侧执行记录.md:1088`、`:1094`、`:1096`

### [D-65] 连续 `monkey` 拉起 / 在 Operit 前台拉起
- **想法**：脚本化反复启动游戏做实验。
- **做法**：`monkey -p … 1` 连续多次；Operit 在前台时拉起。
- **结果**：`exit-info` 反复出现 `reason=2 SIGNALED status=9`；日志 `OplusFlexibleDCSManager: startMiniWindow … group_pkg=com.RoamingStar.BlueArchive` ⇒ 被系统塞进**小窗**，随后被回收。
- **为什么失败**：**status=9 = SIGKILL = 系统内存/多窗口回收**，不是 ACE（ACE 用 SIGBUS/7）。当时 free 仅 876 MB。
- **教训**：① 验证启动**手动点图标**；② 先清掉我们自己的后台 python（available 从 0.7 G 回到 7.7 G）；③ 判"是不是 ACE 杀的"只看 `status`：7=SIGBUS(ACE)，9=SIGKILL(系统)。
- **出处**：`work/ba/audit/ba-pitfalls.md:99`、`:106`

### [D-66] 卸载重装后直接 `mv` 回 11 GB 资源
- **想法**：重装后把备份的资源目录移回去就完事。
- **做法**：`mv /sdcard/ba_data_bak /sdcard/Android/data/com.RoamingStar.BlueArchive`
- **结果**：游戏弹原生框 **`Error / Not enough storage space to install required resources.`**，但磁盘实际有 **28 GB** 空闲。
- **为什么失败**：卸载重装后应用 **UID 变了**（本机 10574 → 10575），从备份 `mv` 回来的 11 GB 里文件**属主还是旧 UID**，游戏读不到自己的资源 → 认为需要重新安装 → 报空间不足。
- **教训**：必须 `chown -R $UID:1078`（**组必须是 `ext_data_rw`=1078，不能用 `$UID:$UID`**），一次修好。
- **出处**：`work/ba/audit/ba-pitfalls.md:109`

---

## 附：本清单的计数与索引

- 死路条目：**D-01 ~ D-66** 共 **66** 条（编号连续，无跳号）。`report/INDEX.md` §2 的速查表有 **68 行**——多出的 2 行是"评估后放弃、从未执行"的两条（改 scheme 为 http、`Env=dev` 切 test），它们没有"实际结果"，故不收进本清单。
- 分类计数：A 改包/ACE **8** 条；B 重定向/DNS **10** 条；C 注入/GOT **11** 条；D Frida/符号 **6** 条；E 证书/CA **8** 条；F 网关协议/响应 **9** 条；G 取证方法论 **10** 条；H 手机操作 **4** 条。
- 用户点名的"特别重点"落位：**D-44**（四种变体行为一致）、**D-45**（无第二协议请求的完整证据链）、**D-46**（HTTP 状态码探针，含 404 弹窗）、**D-19～D-29**（改 libil2cpp/metadata 的尝试）、**D-30～D-35**（Frida 与 il2cpp 符号，含 libil2cpp 零命名导出）、**D-36～D-43**（证书/CA 试错）、**D-49**（宝塔 WAF）、**D-53～D-62**（ssh/tcpdump/日志判读，含 nginx alias 403 与 heredoc 同族坑）。
- 相关的"错结论 → 正确结论"在 `report/INDEX.md` 附录 A（36 条），其中与本清单一一对应的：A-1↔D-19/KG、A-4↔D-20、A-5↔D-19、A-7↔D-09/D-10、A-8↔D-15/D-16、A-9↔D-43、A-10↔D-42、A-16↔D-51、A-18↔DNAT、A-21↔D-47、A-22↔D-47、A-23↔INDEX §1.5、A-25/A-26/A-27↔D-44 之前的加密封装误区、A-32↔D-34/D-35、A-35↔D-36。
