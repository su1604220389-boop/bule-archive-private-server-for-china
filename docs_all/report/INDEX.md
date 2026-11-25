# 全档案索引

> 用法：接手任何任务前，先在本文件里按关键词找一遍。找到"已定案/已否决"就直接引用，不要重试。
> 覆盖范围：`report/*.md` 顶层 41 份（编号 00–38，含重复编号：两个 21、两个 22、两个 23）+ `scripts/NOTES-gateway.md` + `work/ba/audit/ba-pitfalls.md` + `work/ba/bapatch/PROBE_README.md`。**全部逐份读完**，行号为 read 工具行号。
> 报告编号重复的，一律用**完整文件名**区分（`21-决策日志-CA路线攻坚.md` vs `21-手机侧执行记录.md`）。
> 深度死路细节见 `report/DEADENDS.md`；本章末 **附录 A** 是"曾经的错误结论 → 后来的正确结论"，**新接手务必先读它**。

---

## 0. 三十秒现状（截至 2026-11-14 03:15）

| 层 | 状态 | 出处 |
|---|---|---|
| APK 完整性 / ACE | ✅ 已测绘到"能改什么不能改什么" | `report/01-现状与已试方向.md:118`、`work/ba/audit/ba-pitfalls.md:46` |
| SDK 登录（卡密） | ✅ 已打通，`/common/config`→`quick-login`→`detail` 全 200 | `report/09-服务器盘点.md:922` |
| 客户端 → 我们服务器 | ✅ 流量 100% 被 DNAT 劫持到 `<SERVER_IP>:443` | `report/21-手机侧执行记录.md:21` |
| TLS | ✅ 已通（`state-api` 4 次握手 + GET /api/state 200） | `report/22-服务端取证记录.md:38` |
| `/api/state` 双 DTO | ✅ 真实应答已拿到（676 B / 161 B） | `report/31-真实catalog与版本清单取证.md:53` |
| title→点击→网关请求 | ✅ 客户端进标题页、点击后确实发一条 gsqc 请求 | `report/21-手机侧执行记录.md:1184`、`:1229` |
| **网关协议** | ⏸ **信封加密已破解**（口令 = 包尾明文 key），**桥接器行为已定标但客户端仍不推进** | `report/35-国服网关信封加密破解.md:13` |
| 当前唯一卡点 | **客户端收到 200 后不发第二个协议请求**（本地停住） | `report/21-手机侧执行记录.md:1617` |

---

## 1. 已定案的事实（不要再验证，直接用）

### 1.1 设备与 root 环境

| 事实 | 出处 | 备注 |
|---|---|---|
| 设备 `PLR110`（一加），Android 17 / sdk 37，`targetSdk=33`、`minSdk=24`、`extractNativeLibs=true`、arm64-v8a、UID **10576** | `report/06-手机基线恢复.md:70`、`report/07-dlopen报错考证.md:5` | targetSdk=33 ⇒ Android 17 的 CT 不咬我们 |
| root 通道 = `busybox nc -ll -p 18080 -e /system/bin/sh`，`uid=0 context=u:r:ksu:s0` | `report/08-手机接管与真因.md:15` | PC 侧驱动 `report/_tmp/rsh.py`，**单连接不能并发** |
| **不能**用：`am start` / `am force-stop` / `cmd package` / `settings get\|put` / `input` → 一律 `Failed transaction (2147483646)` | `report/08-手机接管与真因.md:20`、`report/21-手机侧执行记录.md:97` | SELinux 挡 binder；冷启只能用 `kill -9` + `monkey` |
| **能**用：`sh(mksh)` / `curl` / `nc` / `busybox`(含 unzip) / `od` / `dd` / `sha256sum` / `iptables` / `ip6tables` / `sendevent` / `monkey` / `nsenter` | `report/08-手机接管与真因.md:18`、`report/20-AndroidCA注入深度调研.md:365` | **无** python / wget / socat / ssh / tcpdump（`python3` = `NOT_FOUND`，`report/21-…:668`） |
| `/system/etc/hosts` 是只读 EROFS（`touch` → Read-only file system） | `report/25-根因定案-状态接口schema错误.md:92` | 系统 hosts 这条路从文件系统层就死了 |
| 触摸注入必须走 `sendevent /dev/input/event5`（`touchpanel`），`ABS_MT_POSITION_X max 20351`/`Y max 44799`（=像素×16），屏幕中心 raw(10176,22400) | `report/06-手机基线恢复.md:347`、`report/21-手机侧执行记录.md:7` | **Unity SurfaceView 不响应注入触摸**，见 §2 D-48 |
| 手机上有第三方自动化 App `com.ai.assistance.operit` 常驻悬浮窗（会遮挡约 10% 屏，且有 shell 子进程） | `report/21-手机侧执行记录.md:262` | 做截图判读时要排除它的遮挡 |
| 手机出网默认路由 `vgate0`（Clash tun），但对 `example.com` 目标不劫持，请求真实落到我们服务器 | `report/09-服务器盘点.md:838` | `com.follow.clash` 未接管流量（无 tun、无 VPN 网络）见 `report/21-手机侧执行记录.md:1014` |
| 本 PC 会随机 bugcheck（11 天 3 次，代码各不同：0x139 / 0x1E / 0x3B） | `report/08-手机接管与真因.md:180` | **长跑任务必须落盘断点**；`report/35-国服网关信封加密破解.md:177` 记了 13 次 0xC0000005 崩溃靠断点续跑 |

### 1.2 客户端改包 / ACE 的硬边界

| 事实 | 出处 | 备注 |
|---|---|---|
| 必须删 `assets/__tpinfo.{tsc,tsc.sig,tsd,tsd.sig,tp}` 5 个文件，否则改包即闪退（无日志、无 tombstone） | `work/ba/audit/ba-pitfalls.md:9` | 这是**一切改包能跑的前提** |
| `libil2cpp.so` **无 hash pin，可改**：填充字节翻转 / 代码洞注入 / 改 `DT_INIT` / root 原位替换 全部实测可用 | `report/01-现状与已试方向.md:128`、`work/ba/audit/ba-pitfalls.md:171` | E38 / E63 / 原位替换三条独立证据 |
| `libunity.so` **有 ACE 磁盘哈希钉死**：改 4 字节即 `SIGBUS (reason=2 status=7)` | `report/01-现状与已试方向.md:178`、`work/ba/audit/ba-pitfalls.md:50` | 对照组 E42 用原厂 libunity 才正常 |
| `libtprt.so`（ACE 核心）改任意字节 → `kill(SIGBUS)`；整库替换成假 so 可过启动，但**用户已否决** | `report/01-现状与已试方向.md:179`、`:185` | 否决理由：假 ACE 会破坏 Unity 需要的返回 |
| ACE 判定**持久化**（"记账"）：触发过一次异常改动后，后续任何版本启动都被 SIGBUS，直到删 `files/{ace_shell_di.dat,shell_cache,ano_tmp,data/app}` | `work/ba/audit/ba-pitfalls.md:59` | 复位实测有效；这条解释了"同一版 APK 有时活有时死" |
| 清空 `/data/data/<pkg>` 会**永久卡启动**（`initialize()` 在 `__sem_timedwait` 等 `:GP6/:GP7`，依赖被删的解包产物）→ 只能卸载重装 | `work/ba/audit/ba-pitfalls.md:72` | 重装前先把 11 GB 资源 `mv` 到 `/sdcard/ba_data_bak` |
| 卸载重装后恢复资源必须 `chown -R <新UID>:1078`（组必须是 `ext_data_rw`），否则报 `Not enough storage space` | `work/ba/audit/ba-pitfalls.md:109` | 本机 UID 10574→10575 那次踩的 |
| `status=9`＝SIGKILL＝系统小窗/内存回收，**不是 ACE**；ACE 用 SIGBUS(status=7) | `work/ba/audit/ba-pitfalls.md:99` | 当时 free 仅 876 MB/15 GB |
| 清掉我们自己的后台 python 后 available 从 0.7 G 回到 7.7 G；验证启动要**手动点图标**，不要连续 monkey | `work/ba/audit/ba-pitfalls.md:106` | monkey 在 Operit 前台时会拉起小窗 |
| 现役"能进主程序"的包是 **E42**（官方资源基线 + 原厂 libunity + 我们的 res + sdk_url 指本机 + 删 __tpinfo），2,126,782,882 B | `work/ba/audit/ba-pitfalls.md:149` | ⚠️ 但**设备上实际装的不是 E42**（APK 内嵌 so 带桩），见附录 A-13 |

### 1.3 SDK 登录链

| 事实 | 出处 | 备注 |
|---|---|---|
| `assets/SDKConfigSettings.json` 的 `sdk_url = http://127.0.0.1:8080`（裸 loopback+端口，明文 HTTP） | `report/06-手机基线恢复.md:158` | `res/Dk.xml` 的 `cleartextTrafficPermitted=true` 曾被认为是依据，**该文件实测不存在**，见附录 A-20 |
| 客户端登录请求**带 `/sdk` 前缀**（`sdk_url = https://example.com/sdk`），nginx `location /sdk/` 剥前缀后 sdkcard 收到 `/common/config` | `report/09-服务器盘点.md:961` | **不要在根路径加 /common/ /user/ 反代**，现有配置就是对的 |
| 101404 = **AiriSDK 网络错误**（`InitManager_initOnFail {"code":101404,"R_MSG":"网络异常?请重新连接"}`），不是资源错误 | `report/06-手机基线恢复.md:150` | 8080 有中转后立刻消失 |
| "网络异常，请重新连接" = `sdkcard.py` 没起，**与网关无关** | `work/ba/audit/ba-pitfalls.md:97` | 极易误判成网关问题 |
| 卡密身份形态：`uid = 314816420`（9 位十进制）、`token = 61de1d1b7519ab1231866f74c11fcfdd1f80b210`（40 位 hex） | `report/27-SDK登录协议调研.md:265` | 恰好满足 Shittim 的两条硬约束 |
| 登录链 5 条全部 200：`/sdk/common/config`(7837B) → `/user/quick-login`(847) → `/user/detail`(847) → `/health-game/duration`(70) → `/common/geo-ip`(57) | `report/09-服务器盘点.md:933` | UA `okhttp/4.9.2` = Yostar SDK |
| `udata_sdk_config.xml` 的 `inited_failed_time = 0` 且 `cur_server_time ≠ cur_start_time` ⇒ Udata SDK 初始化成功 | `report/21-手机侧执行记录.md:833` | 由"服务端 443 SNI 分流"带来 |
| `TapSDK: 包名、签名错误。详见 ErrLog` 是**既知现象**（改包重签的必然结果），不影响流程 | `report/29-进度-网关未调用与判据纪律.md:81` | 全量 logcat `grep 签名\|包名\|ErrLog` = 0 行 |
| `detection_address`（3 条 HTTP + 3 条 MTR，全指 `example.com`）**是持久化的**，客户端每次启动不重写 | `report/21-手机侧执行记录.md:617` | mtime 停在 00:41:11 |
| MTR 那三条**必然失败**（DNAT 把 TTL 探测包一跳直达），与登录链无关 | `report/21-手机侧执行记录.md:757` | `net_d_000` 里 798 条 `lastHop:0` |

### 1.4 TLS / 证书

| 事实 | 出处 | 备注 |
|---|---|---|
| **TLS 对 `state-api` 已通**：01:34:52 起 4 次完整握手 + nginx 解出明文 `GET /api/state` 并回 200 | `report/22-服务端取证记录.md:38`、`report/25-根因定案-状态接口schema错误.md:58` | 判据：ServerFlight 之后出现应用数据/GET（只认 pcap） |
| **CA 生效时刻 = 01:33:45**：46 条明文 `fatal alert 49 access_denied` 全部落在 01:24:58–01:33:45，之后归零 | `report/22-服务端取证记录.md:112` | 49 的消失与 CA 生效严格同步 ⇒ 指向 trust store，不是 pinning |
| 上游三个域名（state-api / gsqc-api / static）**全部依赖 SNI 选证书**；无 SNI 时分别得到 `*.certfallback.com`(阿里) / `*.unionpayintl.com`(银联) / `*.a.bdydns.com`(百度)，主机名校验 62 | `report/22-真实上游接口取证.md:373`、`:435` | 未知 SNI 时阿里最严格：直接 `fatal alert 40`，不给证书 |
| 客户端到 `state-api` 的 ClientHello **353 B，明确带 SNI** | `report/23-主线改判-TLS已通应用层卡点.md:14` | 「客户端不发 SNI」被推翻，见附录 A-9 |
| 上游三域名共用**同一张**叶子 `CN=*.bluearchive-cn.com`（RapidSSL/DigiCert，`E4:06:EE:F4…`），链长 3（gsqc 4 张，多一张交叉签名老根） | `report/22-真实上游接口取证.md:351` | gsqc-api 的 ALPN **只谈 http/1.1**，state-api/static 支持 h2 |
| 我们服务器 no-SNI 时给 `CN=*.bluearchive-cn.com` / `issuer=CN=BA Test Root CA,O=BA`（自签，SAN 覆盖 6 个域名） | `report/22-真实上游接口取证.md:376` | 这就是"客户端不带 SNI 也能通"的真相——它打的是我们 |
| `example.com` 的真证书 = **TLC DV TLS CA**（Certum 链），2025-12-12 → **2026-12-12**，SAN 只含 `example.com` + `www` | `report/09-服务器盘点.md:860` | **deadline 2026-12-05 前必须处理** |
| `vhost/letsencrypt/example.com/` 里那份 LE 证书 `notAfter=2026-11-26` **且从未部署** | `report/09-服务器盘点.md:863` | **不要让它自动部署**，换上会让 TLS 立刻失效 |
| `acme.sh --renew` 这条路**不存在**：本机无 acme.sh / certbot / cron / timer | `report/09-服务器盘点.md:578` | 只剩宝塔面板部署或 TLC 后台重签 |
| 用户证书库（`/data/misc/user/0/cacerts-added/`）在 `targetSdk=33` 下**默认不被信任** | `report/20-AndroidCA注入深度调研.md:170` | Android 7 起的设计 |
| A14+ `SystemCertificateSource.getDirectory()`：`system.certs.enabled=true`→`/system`；否则 `sdk>=34 && APEX 目录非空`→**APEX，完全忽略 /system** | `report/20-AndroidCA注入深度调研.md:151` | 所以往 `/system` 拷是死代码 |
| `/apex` 挂载点是 **private propagation**：基础挂载全局可见（dev/ino 一致），但任一 ns 里**新加的 mount 不传播** | `report/20-AndroidCA注入深度调研.md:296` | 这就是"nsenter 看 dev/ino 一致但 App 看不见"的解释 |
| `SystemCertificateSource` 是**进程内单例**，改磁盘后必须杀进程冷启 | `report/20-AndroidCA注入深度调研.md:493` | 热更新无路 |
| 两个 CA 目录都是 **tmpfs (rw)**（146 / 147 个 `<hash>.0`），`touch` 可写，重启即失效 | `report/06-手机基线恢复.md:270` | 两个目录都需在 zygote ns 里 bind mount 才对新进程生效 |
| 原厂证书文件是 **PEM 文本**；但 `CertificateFactory.generateCertificate()` **PEM/DER 通吃** | `report/20-AndroidCA注入深度调研.md:17`、`:53` | "必须 DER"的说法与 AOSP 相反（`report/20-…:100` 记了那条错误 README） |
| 覆盖 CACERTS 必须用 `mount --rbind`（A15+ 每张证书可能是单文件挂载，`--bind` 会把 100+ 张证书覆盖成空） | `report/20-AndroidCA注入深度调研.md:447` | NVISO 原文 "all of the certificates have disappeared" |
| `kit/state_kit_v1/pc/certs/ca.crt` 是**另一张** CA（`CN=BA State Gateway Root CA`，hash_old `4cc9cfb3`），不能当 `fd8b2b01` 用 | `report/06-手机基线恢复.md:293` | — |

### 1.5 `/api/state` 的真实 schema（两个 DTO）

| 事实 | 出处 | 备注 |
|---|---|---|
| 真实 `gsqc-api/api/state`（**带 4 个业务头**）= **200 / 676 B / `State:1` / `Msg:""` / 10 字段** | `report/31-真实catalog与版本清单取证.md:53` | 4 个头：`APP-VER: 3.0.2`、`PLATFORM-ID: 1`、`CHANNEL-ID: 1`、`SERVER-NAME: prod` |
| 不带这 4 个头 → **200 / 214 B / `State:0` / `Msg:"platform id error"`** | `report/22-真实上游接口取证.md:176` | 平台号不是任何 query/header 名字，只能靠原始请求 |
| 真实 `gsqc` 10 字段顺序：`CallbackUrl → CustomerServiceUrl → AddressablesCatalogUrlRoots → ResourceVersion → TableVersion → MediaVersion → PatchVersion → State → Msg → IsOpenPreDownload` | `report/22-真实上游接口取证.md:454` | Go 结构体序，紧凑无空格 |
| 四个版本号是**四个独立的 `yyyyMMddHHmm` 时间戳**：RV `202611051844` / TV `202611051826` / MV `202611051836` / PV `202609291539` | `report/31-真实catalog与版本清单取证.md:62` | 不是同一个值 |
| `AddressablesCatalogUrlRoots` 真实是**三个元素**：`static` / `static-qc` / `static-hs` + `/prodm39` | `report/31-真实catalog与版本清单取证.md:61` | `static-qc`/`static-hs` 是此前完全不知道的两条线路 |
| `CallbackUrl` 是**转义成字符串的嵌套 JSON**（4 键：order_notify / survey_notify / web_notify / account_logout，全指 `gs-inter.bluearchive-cn.com:4000`） | `report/31-真实catalog与版本清单取证.md:53`、`report/24-state接口schema反推.md:186` | 类 `CallbackUrlData` |
| 真实 `state-api/api/state`（**带 4 个头**）= **200 / 161 B**：`Servers` 2 项 + `State:1` + `Msg:"服务器维护中，请耐心等待开服！"` | `report/31-真实catalog与版本清单取证.md:95` | `Servers` 都是 `https://<host>/api/` 结尾 |
| 真实 `state-api` **不带**头 = 200 / **0 字节** | `report/31-真实catalog与版本清单取证.md:84` | 0 字节是"没带业务头"，不是"真实语义" |
| **`State` 是流程触发器**：`State:0` 停在 state 校验阶段（弹窗显示 state-api 的 `Msg`）；`State:1` 才继续去请求网关（弹窗换成 gsqc 的 `Msg`） | `report/21-手机侧执行记录.md:1047`、`:1069` | 真实生产态也是 `State:1` |
| **`Msg` 只是弹窗正文**，不是触发器：`Msg:""` 时弹窗照样出现（正文空白） | `report/29-进度-网关未调用与判据纪律.md:28`、`report/25-根因定案-状态接口schema错误.md:29` | 探针 `PROBE-M1-STATE-ZQ7` 逐像素验证 |
| `Servers` 为 null → `ServerInfoDataRepository.GetApiServerInfo` 协程 **NullReferenceException**，启动后约 5 s | `report/21-手机侧执行记录.md:501` | 两次独立复现（pid 26473 / 29531），补上 Servers 后 0 条 |
| `CustomerServiceUrl` **客户端根本不读**（metadata 0 命中） | `report/24-state接口schema反推.md:41` | 写什么都无所谓 |
| `StateResultCode` 枚举成员 = `{Maintain, AppUpdate}`（全局唯一 1 处 `0x001D70E7`） | `report/24-state接口schema反推.md:337` | 具体数值未读出来（头部加密） |
| 我们伪造的 `Servers` 只有 1 个元素；`GetApiServerInfo` 是迭代器（有 `<i>5__4` 下标、`<isLive>5__3` 存活标记、`<header>5__2`），疑似需要 ≥2 做故障切换 | `report/24-state接口schema反推.md:224` | — |

### 1.6 网关协议与信封

| 事实 | 出处 | 备注 |
|---|---|---|
| Shittim 网关唯一入口 = `POST /api/gateway`（**两段，完全合法**）。`[Route("api")]` + `[HttpPost("gateway")]` | `report/28-Shittim网关协议源码核对.md:18`、`:63`；`scripts/NOTES-gateway.md:7` | 路由模板 `api/{path1}/{path2}` 是误读 |
| 非 multipart 的 POST 必 500：`InvalidOperationException: This request does not have a Content-Type header`（`GatewayController.cs:160`） | `report/09-服务器盘点.md:441`、`scripts/NOTES-gateway.md:30` | 带 `x-www-form-urlencoded` → 400 `Expecting an mx file` |
| 字段名必须是 **`mx`**（`Request.Form.Files.GetFile("mx")`） | `report/28-Shittim网关协议源码核对.md:185` | — |
| Shittim `.mx` 布局：`[crc u32][typeConversion i32][keyLen u8][ivLen u8][headerKey][headerIv][payload]`；payload = `XOR(0xD9)` + gzip（三种长度前缀变体都试） | `report/28-Shittim网关协议源码核对.md:196` | `RequestXorKey = {0xD9}`（`:107`） |
| **国服不发 `.mx`**，发 multipart 三个文本字段：`protocol` / `encode` / `packet` | `report/32-国服网关信封混淆分析.md:15` | 两边信封**不兼容**，`report/32-…:252` |
| 国服 `packet` = `base64( [u32 LE 明文长度][gzip(内层)] )`，**外层无 XOR**（`1f 8b` 明文可见） | `report/32-国服网关信封混淆分析.md:160`、`report/33-国服网关协议开源情报.md:128` | — |
| **国服内层 432 B = `[iv:16][AES-256-CBC 密文:384][key:32 ASCII]`**，key 就是包尾那 32 字节明文本身 | `report/35-国服网关信封加密破解.md:13` | 16+384+32=432，三段边界干净 |
| 解密**实测 100% 命中已知明文**（`DevId=314816420`、`Token=61de1d1b…`），解出 373 B 片段（以 `,` 开头） | `report/35-国服网关信封加密破解.md:55` | 完整 JSON = `{"Protocol":"Account_Auth"` + 片段 = 399 B，`json.loads` 通过 |
| `{"Protocol":"<名字>"` 这一段**在密文之外**，所以解密结果以 `,` 开头 | `report/35-国服网关信封加密破解.md:83` | — |
| **`protocol` 字段 = `BASE32( MD5( UTF-16LE(协议名) ) )` 去 padding** | `report/33-国服网关协议开源情报.md:67` | 关键：**UTF-16LE，不是 UTF-8**；26 字符（不是 base64 的 4 倍数） |
| 常见协议的 token 表已算出（`Account_Auth`=`AHTQLQI65FWJGGGK4KL5AEF57A`、`Account_CheckYostar`=`PFJRUKK5IXXQR2XFFCMNXEIKXM`、`Queuing_GetAuthTicket`=`VLWZJ6JP2FMSAXBR2BDAXLLBNQ` …） | `report/33-国服网关协议开源情报.md:81` | 可随时从名字算，不需映射表 |
| 国服首条业务请求就是 **`Account_Auth`(1002)**（02:42:51 样本），不是 CheckNexon | `report/33-国服网关协议开源情报.md:96` | 加密用的是包内明文 key，与 metadata RSA 公钥是两套机制（`report/32-…:271`） |
| `Account_CheckYostar`：**不验签、不校验 token、账号不存在自动建号、`ResultState=1`** | `report/28-Shittim网关协议源码核对.md:459` | 只把 `EnterTicket` 解 base64 再 `Split('/')` |
| `EnterTicket = base64(UTF8("{YostarUID}/{YostarToken}"))`，由 Shittim 自己生成 | `report/28-Shittim网关协议源码核对.md:381` | 无签名、无时间戳、无 nonce、无防重放 |
| 三条硬约束：`uid` 必须纯数字且 ≤ long；`token` **绝不能含 `/`**；`ResultState` 必须回 `1` | `report/27-SDK登录协议调研.md:273`、`report/29-进度-网关未调用与判据纪律.md:62` | 我们当前的值三条全满足 |
| 免会话白名单含 `Queuing_GetTicket/GetCryptoKeys/GetAuthTicket/ProcessWaitingQueue/Account_CheckYostar/CheckNexon/Auth/Create/ProofToken_RequestQuestion` | `report/28-Shittim网关协议源码核对.md:497` | 这是它们能作为登录第一枪的原因 |
| 握手后会话 AES key **实测为 null，响应走明文** | `report/03-上游情报.md:122` | 省掉大量 decrypt 工作 |
| `Account_Auth` 响应 = 24 个顶层键 / **3740 B 明文** / gzip 后 1269 B；**没有 `ResultState`，也没有 `ErrorCode`** | `report/36-Account_Auth响应字段清单.md:128`、`:12` | 这是**正确的**，不是缺失 bug |
| `SessionKey.MxToken` 是 **GUID 字符串**（`0404e715-ec34-4808-b1b1-580aefafc3af`），不是 base64 | `report/36-Account_Auth响应字段清单.md:78` | — |
| `ServerNotification: 8` = `HasUnreadMail`，是正常基线位 | `report/36-Account_Auth响应字段清单.md:14` | — |
| `AccountDB.Nickname` 空串属正常态（昵称由 `Account_Nickname` 1001 单独设） | `report/36-Account_Auth响应字段清单.md:17` | — |
| 客户端有 **`DecryptOrReturnOriginal`**（"解密，或者返回原文"）⇒ 明文 JSON 响应是合法分支 | `report/34-国服packet二进制结构分析.md:274` | 与 Shittim `aes=False` 分支同构 |

### 1.7 客户端静态（il2cpp / metadata）

| 事实 | 出处 | 备注 |
|---|---|---|
| `global-metadata.dat` 38,426,024 B，头部被改写：magic `0x12724394`（非 `0xFAB11BAF`）、version `0xEC9E4B18`、全文件 0 处标准 sanity | `report/24-state接口schema反推.md:29`、`report/11-客户端静态逆向-网关与证书.md:70` | 标准 Il2CppDumper 静态解析不可行 |
| 但**字符串区明文**：存在 `key=0x00` 与 `key=0x66` 两类区段，字面量区还有每串独立 key（如默认连接组 JSON 用 `0xB5`） | `report/11-客户端静态逆向-网关与证书.md:96` | 按名解析完全可用 |
| 唯一与游戏 API 有关的 URL 字面量 = `["http://test-ba.yostar.net:5210/api/state" ×3]`（JSON 数组，`0x0c172b`，XOR `0xB5`） | `report/11-客户端静态逆向-网关与证书.md:156` | **是 http 不是 https** |
| 生产 `state-api` 域名**不是任何形式的静态字面量**（ASCII/UTF-16/单字节 XOR 全 256 key/周期 ≤8 keystream 四重 0 命中） | `report/11-客户端静态逆向-网关与证书.md:173` | 别再去找字符串 |
| metadata 里那把 PEM **= 网关握手 RSA 公钥**（`Queuing_GetCryptoKeys`(50001) 用它加密 key/IV），**不是证书 pin** | `report/28-Shittim网关协议源码核对.md:717`、`report/19-网关攻坚-当前状态.md:49` | 见附录 A-2 |
| 国服这把是 **RSA-2048 / 451 B / 三段 150-150-151**，不是 4096 | `report/30-网关RSA公钥定位与替换.md:12` | 见附录 A-3 |
| 三段偏移：A `0x0178CC60`(150) / M `0x012D5F88`(150) / C `0x0178CBA0`(151)；**末段在首段之前**，中段隔 4.7 MB | `report/30-网关RSA公钥定位与替换.md:16` | 文件里不存在连续完整 PEM |
| 补丁工具 `bapatch/patch_metadata_key.py` 已完成（AOB 定位 + DER 结构验证 + 8 条硬断言），已产出 `global-metadata_patched.dat`（sha `f0a30008…`，差异 337 字节 / 0.0009%） | `report/30-网关RSA公钥定位与替换.md:301` | 用 4096 位 PEM 会被拒（800 B > 451 B 洞） |
| `libil2cpp.so` `.dynsym` 2660 项，**defined 里 `il2cpp_*` = 0**，306 个具名导入 | `report/17-运行时hook方案评估.md:29`、`report/38-Frida部署清单.md:170` | `.symtab` 不存在 |
| 但符号可**离线恢复**：`.gnu.hash` + `.dynstr` 完好，`st_name` 被抹、`st_value` 改字节序（需 `BE(8B)>>8`）→ **1201 个符号，其中 124 个 `il2cpp_*` 带地址**，1721/1721 FUNC 全落在 `.text` | `report/17-运行时hook方案评估.md:39`、`report/19-网关攻坚-当前状态.md:67` | 本项目最有价值的技术资产 |
| 这些 `il2cpp_*` 在 `.text` 尾部是 **4 字节 `b <real>` 跳转桩**，寄存器/栈不变，**可直接当函数调用** | `report/17-运行时hook方案评估.md:73` | `il2cpp_class_for_each` = `0x063c3b50` → `0x6391eb0` |
| `il2cpp_class_for_each` 回调签名 = `void (*)(Il2CppClass *klass, void *userData)`，有反汇编实证 | `work/ba/bapatch/PROBE_README.md:81`、`report/17-运行时hook方案评估.md:468` | +0x10 MOV x19,x1 / +0x14 MOV x20,x0 / +0x58 MOV x1,x19 / +0x5c BLR x20 |
| 代码洞 `0xf2c2410` 容量 **3056 B**（`[0xf2c2410, 0xf2c3000)`）；原厂 `DT_INIT = 0x10496434`（真实的 C++ 静态初始化，不是桩） | `work/ba/bapatch/PROBE_README.md:78`、`:79` | 现役 g20 版洞里 1111 B，把 `DT_INIT` 改成洞地址 |
| **`.text` 有 739/2825 页（26.2%）在磁盘上不是可执行代码**（ACE 编码块，约每 64 KB 12 KB），加载时还原 | `report/17-运行时hook方案评估.md:484` | 区间清单 `work/ba/bapatch/encrypted_pages.txt`（183 区间） |
| ⇒ 离线文件补丁只在**明文页**可行；目标落在编码块内时，只能改 `MethodInfo::methodPointer`（data 段）指向代码洞 | `report/17-运行时hook方案评估.md:503` | — |
| `libil2cpp` RELRO `[0xf2c4000, 0xfbb4000)` 含 `.got.plt`；`DT_FLAGS=BIND_NOW` ⇒ 运行时槽位是已解析的 libc 地址 | `report/02-注入链审计.md:76` | — |
| `libunity` GOT 偏移（三重验证）：`gettimeofday=0x13d94d0`、`getaddrinfo=0x13d94d8`、`basename=0x13d94e0`、`connect=0x13d95d8` | `report/02-注入链审计.md:556` | 见附录 A-4 |
| `libil2cpp` 自身对 `getaddrinfo`/`connect` 的调用点 = **0**（346 万条 BL 扫描，其它 65 个桩被调 116,219 次） | `report/02-注入链审计.md:23` | ⇐ `libil2cpp` PLT/GOT 方向整体无效 |
| 活着的是 `libunity`：`getaddrinfo@plt` 1 个调用点（`0xb84014`）、`connect@plt` 3 个（`0xc036f8/0xcb4720/0xcf50c8`）+ 1 处直接读 GOT（`0x454788`） | `report/02-注入链审计.md:28` | — |
| `dl_iterate_phdr` 的 `dlpi_addr` == maps 里 `r-xp 00000000` 那行起始地址；**不能用 maps 第一行**（存在两个 offset=0 映射） | `work/ba/audit/ba-pitfalls.md:214`、`report/01-现状与已试方向.md:139` | 这是"写了没反应"的直接原因 |
| `libunity` GOT 所在页是 `rw-p`，可**直接 `str` 写**，不需要 mprotect、不需要 `/proc/self/mem` | `work/ba/audit/ba-pitfalls.md:243`、`report/10-网关重定向-已试清单与有效缺口.md:55` | 前提是 `adr` 算对 |

### 1.8 服务端 / 服务器

| 事实 | 出处 | 备注 |
|---|---|---|
| **真正生效的配置是 `Config/Config.json`，不是 `appsettings.json`**（三重证据：UseCustomExcel=false 但 appsettings 是 true；日志打 `Custom Excel is Disabled`；`Bypass Authentication is Enabled` 只存在于 Config.json） | `report/09-服务器盘点.md:94` | `deploy2.sh`/`deploy3.sh` 写 appsettings 对 UseCustomExcel **无效** |
| `GatewayPort = 5100` 是 **gateway 端口**（不是"配置页"） | `report/09-服务器盘点.md:106` | 5000 与 5100 由**同一进程、同一张路由表**服务（`GameServer.cs:160-174`） |
| 公网只有 **443 开放**；5000 / 5100 / 8080 全被安全组挡（超时） | `report/09-服务器盘点.md:428` | 放行端口属禁止项 ⇒ 别设计"客户端直连 5000" |
| `/root/bapatch` **不存在**；实际路径是 `/www/wwwroot/ba_srv`、`/www/wwwroot/ba_sdk`、`/www/wwwroot/ba_private` | `report/09-服务器盘点.md:33` | 归档里所有 `/root/bapatch/*` 路径全部失效 |
| systemd `ba-sdk.service` / `ba-shittim.service` 已 `enabled + active`，`kill -9` 后 **6 秒自愈**（`NRestarts` +1） | `report/09-服务器盘点.md:571` | 日志 `/var/log/ba-{sdk,shittim}.log` |
| 数据管道机制**是通的**：`ExcelDB SQLCipher key validated (912 schema entries)`、`Mapped 499 request types / 501 response types` | `report/09-服务器盘点.md:390` | 缺的是**国服内容**，不是机制 |
| 国服 Excel 数据**一个字节都不在服务器上**（全盘 `find` 0 命中 `*824ce3a8*`） | `report/09-服务器盘点.md:184` | 现有 62 个 `.bytes` 是 Steam/Global 的 |
| `UseCustomExcel=true` 是**陷阱**：`LoadResources` 先 `ResetDumped()` 删 316 MB 资源，再用空 `CdnBaseUrl` 拼非法 URI → `[FTL]` 退出 | `report/09-服务器盘点.md:141` | `.NET` 起不来先查 `DOTNET_gcServer=0`（runtimeconfig 里写死 `System.GC.Server: true`），不是内存不够 |
| 连接组 URL **改不动**：`Config.Save()` 的 `ApplyLocalhostAddress()` 把 `HostAddress` 钉回 loopback；`ApplyGatewayMode` 见到非空 URL 就整份重置 | `report/09-服务器盘点.md:457` | 唯一不碰源码的做法是 nginx `sub_filter`，**但已被明确暂缓**（`report/09-…:494`） |
| `nginx.conf` 是 `user www www`，`/root` 是 `dr-xr-x---` ⇒ **nginx alias 指到 `/root` 必 403** | `report/22-服务端取证记录.md:344` | body 文件必须放 `/www/wwwroot/` 下 |
| 宝塔插件是 **`free_waf` v8.3**（Nginx免费防火墙），运行目录 `/www/server/free_waf/`；全局开关 `config.json` 的 `"open"` | `report/23-手动关闭宝塔WAF操作指引.md:16` | `ba_mitm.conf` **不是宝塔站点**，`site.json` 里没有它 ⇒ 只能动全局规则 |
| WAF 的 `post: 403` 规则会把 multipart POST 换成 **HTTP 200 + `text/html` 的宝塔提示页**（172 B） | `report/21-手机侧执行记录.md:1496` | 客户端必然解析失败且无额外提示 |
| 抓包判读只认 pcap；`access_log` 有记录 ≠ TLS 通过；`error_log` 为空 ≠ TLS 通过 | `report/22-服务端取证记录.md:93`、`report/25-根因定案-状态接口schema错误.md:109` | — |
| `tcpdump` 过滤**不能用 `not src net 172.24.0.0/16`**（服务器自己在该网段，会把整条 ServerFlight 滤掉） | `report/22-服务端取证记录.md:73`、`report/25-根因定案-状态接口schema错误.md:112` | 用无方向过滤或按客户端 IP 钉死 |
| `tcpdump -s 512` 截断 → 记录长度对不上，解析出 `T0(0)` 垃圾；必须 `-s 0` | `report/22-服务端取证记录.md:252` | — |
| pcap 会话**必须按 ISN 分**，按端口聚合会串（手机端口快速复用） | `report/22-服务端取证记录.md:253` | — |
| TLS 1.3 的 alert 一律加密（19 B 记录），**读不到 desc**；要看 desc 得让连接走 TLS 1.2 | `report/22-服务端取证记录.md:254` | — |
| `ba_mitm.log` 只收 SNI 命中 `*.bluearchive-cn.com` 的请求；手机 SDK 流量**全在 `example.com.log`**（`sdkcard.py:78-81` 的 `fix()` 把主机名改写成 `example.com`） | `report/09-服务器盘点.md:778` | **盯错日志 = 误判"客户端没打进来"** |
| 登录取证采集器 `/root/ba_watch/watch.sh` 常驻，输出 `/tmp/ba_watch.log`，**必须同时 tail 两个日志**且用 `tail -F -n0` | `report/09-服务器盘点.md:871` | 旧版只 tail `ba_mitm.log` + 默认 `-n10` 回放，两条都是坑 |
| 磁盘 40 G / 可用 14 G；内存 **1.6 G（available ~738 M）**；Shittim RSS 229 MB、sdkcard 19 MB | `report/09-服务器盘点.md:22` | 内存偏紧 |

---

## 2. 死路清单（试过、失败、不要再试）

> 只列条目与一句话根因；完整版（想法/做法/结果/教训）见 **`report/DEADENDS.md`**。
> 本表 **68 行** = **66 条**有"实际做过"完整记录的（对应 `DEADENDS.md` 的 D-01～D-66）+ **#66 / #67 两条"评估后放弃、从未执行"**（只有速查行，没有详版）。

| # | 方向 | 为什么失败（根因） | 出处 | 试过的时间 |
|---|---|---|---|---|
| 1 | `libunity.so` 4 字节证书补丁 `@0xA53A38` | ACE 磁盘哈希钉死 → `SIGBUS(7)` | `work/ba/audit/ba-pitfalls.md:50` | 11-13 白天（E32/E34/E36） |
| 2 | 整库替换 `libairisgcore.so` | 同上 SIGBUS | `work/ba/audit/ba-pitfalls.md:51` | 11-13（E35） |
| 3 | 往 APK 加新 `.so` / 改 `libmain` 的 `DT_NEEDED` | ACE 直接杀，无日志闪退 | `work/ba/audit/ba-pitfalls.md:10`、`report/02-注入链审计.md:133` | 11-11–11-12 |
| 4 | 新增 `classes3.dex` / 重编 `classes.dex` | 卡 Android 启动界面（与 ACE 无关，启动链问题） | `work/ba/audit/ba-pitfalls.md:52` | E39–E41 / E43 |
| 5 | 重编 `classes2.dex` 改一个 `const-string` | 首次成功（E44）后同批全卡；两处记载冲突 | `work/ba/audit/ba-pitfalls.md:54` vs `report/01-现状与已试方向.md:182` | E44 |
| 6 | 改包名 | 包名被校验 → SIGBUS | `report/01-现状与已试方向.md:183` | — |
| 7 | 假 ACE（整库替换 `libtprt.so`） | 用户明确否决："破坏 Unity 需要的返回" | `report/01-现状与已试方向.md:185` | 11-11 |
| 8 | 改 `libtprt` 的两处校验跳转（`b.eq`→`b`） | 改校验点不解决"文件被改"这个事实；产物无人引用，`final` 是原样回滚 | `report/02-注入链审计.md:105` | — |
| 9 | 清空 `/data/data/<pkg>` 求"干净" | ACE `initialize()` 永久阻塞在 `__sem_timedwait` | `work/ba/audit/ba-pitfalls.md:72` | 11-13 |
| 10 | 用 Xposed Java hook 改游戏逻辑 | 进程内 `XposedBridge` 是混淆替身类，`hookMethod` 全 `NoSuchMethodError` | `work/ba/audit/ba-pitfalls.md:144` | — |
| 11 | 改 `files/Hosts`（裸串 `127.0.0.1:9443`） | 格式不是 `host:port`，是 `hostlen+host+u32+urllen+url+u64+flag` | `report/10-网关重定向-已试清单与有效缺口.md:31` | 11-13 |
| 12 | 改 `files/Hosts`（**正确格式** 79 B） | 客户端读懂并保留为候选，但**不用于连接**（仍连官方 IP） | `report/06-手机基线恢复.md:200`、`report/13-总账-2026-11-14凌晨.md:71` | 11-14 00:45 |
| 13 | `Hosts` 里写**明文 http** URL | 同样不采纳；`ss` 全程无 `:80` 连接 | `report/06-手机基线恢复.md:237` | 11-14（H1） |
| 14 | 调大 `Hosts` 的 u64（+0x100000） | 原样保留但行为不变，不是"最新者优先" | `report/06-手机基线恢复.md:217` | 11-14（实验 B） |
| 15 | 按**单 IP** 阻断 `state-api`/`gsqc` 443 | CDN 轮换 IP，打地鼠 | `report/06-手机基线恢复.md:225` | 11-14（实验 C） |
| 16 | `uid` 级 443 `REJECT`（**只断不导**） | 报「请确认网络连接状态后重试」，**不回落**我们的候选；`Hosts` 该轮甚至没被重写 | `report/06-手机基线恢复.md:253` | 11-14 |
| 17 | 改 `/system/etc/hosts`（shell ns bind-mount） | app 解析由 **netd(1937)** 代答，netd 在另一个 mount ns | `report/06-手机基线恢复.md:176`、`report/10-…:89` | 11-14 |
| 18 | `nsenter` 进 netd ns 再 bind hosts | 仍返回官方 IP（每次查询还在变） | `report/06-手机基线恢复.md:186` | 11-14 |
| 19 | 改 `LocalizeConfig.txt` 的 `ResUrls` | 与 API 网关无关；`cdn.log` 一条请求都没有 | `work/ba/audit/ba-pitfalls.md:129`、`report/10-…:33` | 11-13 |
| 20 | 改 `gameUrl`（`TechSDKUnityBridge$1.val$gameServerUrl`） | 登录链照常走完，`/api/state` 命中 **0** | `work/ba/audit/ba-pitfalls.md:132` | 11-13（E44） |
| 21 | 客户端走 7890 代理时改 `getaddrinfo` | `CONNECT 原域名:443` 由代理侧解析，完全无效 | `work/ba/audit/ba-pitfalls.md:24` | — |
| 22 | 硬编码 GOT 偏移 | 崩在 `strstr`，参数 `0x2710`（把别的函数当 getaddrinfo） | `work/ba/audit/ba-pitfalls.md:25` | — |
| 23 | `dl_iterate_phdr` 里遍历**所有**模块 | SIGSEGV，fault addr 是垃圾指针（未校验边界） | `work/ba/audit/ba-pitfalls.md:26` | — |
| 24 | 改 `.plt` 首指令（malloc/gettimeofday/connect/getaddrinfo） | 日志连 "IN" 都没有（该 so 走 -fno-plt 风格，桩没人走） | `work/ba/audit/ba-pitfalls.md:190` | — |
| 25 | **改 libil2cpp 的 PLT/GOT（GA/CO 两槽）整个方向** | 这两个导入在 libil2cpp 里**没有调用点**（346 万条 BL 0 命中） | `report/02-注入链审计.md:23`、`report/00-下一步总方案.md:76` | 11-13 全天 |
| 26 | 把结果写入"代码段里的 .quad 槽" | 代码页只读 → SIGSEGV(ACCERR) | `work/ba/audit/ba-pitfalls.md:173` | — |
| 27 | 注入代码里调 `__android_log_print` | 可变参传错，`__strlen` 读到 `0x4` | `work/ba/audit/ba-pitfalls.md:175` | — |
| 28 | 运行时 `mprotect` 写 libc 代码页 | SELinux 拒绝（execmod） | `work/ba/audit/ba-pitfalls.md:176` | — |
| 29 | 运行时 `mprotect` + 写 libil2cpp **自身** GOT | SIGSEGV/SEGV_ACCERR(write)，撞 RELRO | `work/ba/audit/ba-pitfalls.md:194` | — |
| 30 | `open("/proc/self/mem", O_WRONLY)` 写 GOT | 静默失败；改 `O_RDWR` 后日志正常但流量没转（其实是 adr/基址错） | `work/ba/audit/ba-pitfalls.md:195` | — |
| 31 | 整页「读-改-写」GOT | 页内其它槽刚被懒绑定改写，回写退回旧值 → 进程直接死亡 | `work/ba/audit/ba-pitfalls.md:220` | — |
| 32 | 代码洞里用 `adr` 指向 `.globl` 符号 | 未链接 `.o` 里 `adr` 留成 imm=0 → `fault 0x1c20` | `work/ba/audit/ba-pitfalls.md:223` | 11-13 深夜 |
| 33 | `.rela.plt` 的 `JUMP_SLOT`→`R_AARCH64_RELATIVE` | 链接器直接 abort，`status=6 (SIGABRT)` | `work/ba/audit/ba-pitfalls.md:196` | — |
| 34 | 恢复寄存器时先 `ldp x19,x20,[sp],#N` 再 `br x20` | 真指针被覆盖 → 跳野地址 | `work/ba/audit/ba-pitfalls.md:174` | — |
| 35 | Frida（frida-server / attach） | ACE 必中项 4 条（maps 的 frida-agent、`gum-js-loop`、27042、TracerPid）；无一份日志证明活过 30 s | `report/17-运行时hook方案评估.md:117`、`:130` | — |
| 36 | `frida-il2cpp-bridge` | 它靠 `getExportByName("libil2cpp.so","il2cpp_*")`，而导出名被抹 = 0 | `report/17-运行时hook方案评估.md:12`、`report/18-Frida与运行时绕过调研.md:114` | — |
| 37 | AzusaBA 的 `xdl_sym`/`getaddr` 26 个 hook 原样搬 | `xdl_sym` 依赖 `st_name`，本 so 全空 → `getaddr()` 永远 `return nullptr`，等 60 s 后放弃 | `report/17-运行时hook方案评估.md:88` | — |
| 38 | 用 Li2CppDumper 静态吃国服 metadata | 头部加密，第一步读 header 即废 | `report/01-现状与已试方向.md:224`、`report/24-state接口schema反推.md:261` | — |
| 39 | 运行期 dump 解密态 metadata | 内存全量扫描（129+214 块、含 1 GB LinearAlloc）**0 命中** ⇒ 不可行 | `report/06-手机基线恢复.md:491`、`:511` | 11-14 01:0x |
| 40 | 在 `libil2cpp.bin` 里 grep `ValidateCertificate` | 0 命中（方法名只在 metadata，so 里没有符号锚点） | `report/02-注入链审计.md:419`、`report/17-运行时hook方案评估.md:214` | — |
| 41 | 装 CA 到用户库 / `/system` / `/apex` 三处 | 三个**不同**原因各自失效（targetSdk、APEX 遮蔽、mount ns） | `report/20-AndroidCA注入深度调研.md:18`、`report/21-决策日志-CA路线攻坚.md:18` | 11-14 01:0x–01:33 |
| 42 | 只往 `/system/etc/security/cacerts` 拷 | A14+ APEX 非空就完全忽略 `/system` ⇒ 死代码 | `report/20-AndroidCA注入深度调研.md:171` | — |
| 43 | 往自己 ns 里 `mount -t tmpfs` 再 `cp` 进 `/apex/...` | 该 tmpfs 只在自己 ns 存在，App ns 完全没有 | `report/20-AndroidCA注入深度调研.md:309` | — |
| 44 | `cp -a` 拷证书 | 把 `shell_data_file` / `media_rw_data_file` label 带进去 | `report/20-AndroidCA注入深度调研.md:211` | — |
| 45 | 重打包改 manifest 的 `networkSecurityConfig` | 本 APK **没有**该属性（`res/xml` 只有 http.xml，无 Dk.xml）；且 Unity 用自己 TLS 栈 | `report/06-手机基线恢复.md:628`、`report/12-外部资料-证书与网关重定向.md:387` | — |
| 46 | 替换 Unity 内置 CA bundle | APK 无 bundle、`libunity`/`libil2cpp`/metadata/catalog 全 0 命中证书 | `report/06-手机基线恢复.md:461`、`report/19-网关攻坚-当前状态.md:48` | 11-14 |
| 47 | 把官方叶证书塞进我们的链里（假设朴素包含式 pinning） | 无变化 | `report/19-网关攻坚-当前状态.md:45`、`report/15-PEM公钥与pinning判读.md:171` | 11-14 |
| 48 | 伪造 DN / serial 与官方逐字一致 | 无变化 | `report/19-网关攻坚-当前状态.md:44` | 11-14 |
| 49 | 服务端加 `listen 443 ssl default_server` 解决"无 SNI" | 加完 ServerFlight 2597 B（确认拿到我们证书），**屏幕仍报网络错** ⇒ SNI 不是根因 | `report/06-手机基线恢复.md:586`、`report/23-主线改判-TLS已通应用层卡点.md:48` | 11-14 01:27 |
| 50 | 用 `access_log` / `error_log` 判 TLS | 时机不对（会话结束才落盘 / alert 后 FIN 不记 error） | `report/22-服务端取证记录.md:93`、`report/25-根因定案-状态接口schema错误.md:110` | — |
| 51 | 用 `mark=262253` 当"包到了我们"的证据 | 只证明手机侧规则匹配；同 sport 在 pcap 里 0 包 | `report/29-进度-网关未调用与判据纪律.md:69`、`scripts/NOTES-gateway.md:55` | — |
| 52 | 用 `tcp-access.log` 否定 ESTAB 长连接 / `grep 目标IP` | 会话结束才写；记的是上游 `127.0.0.1:8443`，恒 0 | `report/29-进度-网关未调用与判据纪律.md:70`、`scripts/NOTES-gateway.md:64` | — |
| 53 | 用 `ss` 判断"流量是否全到我们" | `ss` 显示 DNAT **前**的原始 peer，原理上看不出来 | `report/06-手机基线恢复.md:544` | 11-14 |
| 54 | 凭 IP 反推域名 | 阿里 SLB 上 `gsqc-api` 与 `udata-api.open.yostar.net` **共用同一组 IP** | `report/29-进度-网关未调用与判据纪律.md:72`、`report/21-手机侧执行记录.md:941` | 11-14 |
| 55 | nginx `alias` 指到 `/root/bapatch/state/` | `user www www` 进不去 `dr-xr-x---` 的 `/root` → **403** | `report/22-服务端取证记录.md:344` | 11-14 01:53 |
| 56 | 用**一个** `location = /api/state` 通吃所有 Host | 是两个不同 DTO；第二跳拿 DTO B 的 JSON 反序列化 DTO A 必然全 null | `report/24-state接口schema反推.md:414`、`report/25-根因定案-状态接口schema错误.md:50` | 11-14 01:48 |
| 57 | `static` 回 404 | 客户端弹「通知/网络连接失败」并停住 | `report/21-手机侧执行记录.md:1146` | 11-14 02:30 |
| 58 | 改 `Config/ServerInfoConfig.json` 的连接组 URL | `Save()` 钉回 loopback、`ApplyGatewayMode` 整份重置 | `report/09-服务器盘点.md:472` | — |
| 59 | `UseCustomExcel=true` + `DownloadExcelTables=false`（归档原建议） | 先删 316 MB 再崩 | `report/09-服务器盘点.md:168` | 11-13 13:57 |
| 60 | `.so` 用 `cat > dst` 覆盖 | `>` 是 `O_TRUNC`，被中断留 0 字节 → `dlopen` 报 `0 >= 0` + 0.3 s 自杀循环 | `report/06-手机基线恢复.md:353`、`report/07-dlopen报错考证.md:15` | 11-13 19:47 |
| 61 | 用 `input tap` / `sendevent` 点 Unity 界面 | `input` 被 SELinux 挡；`sendevent` 进队列但 **Unity SurfaceView 不响应** | `report/21-手机侧执行记录.md:1088` | 11-14 02:2x |
| 62 | 连续 `monkey` 拉起 / 在 Operit 前台拉起 | 被系统塞进小窗 → `status=9` 回收 | `work/ba/audit/ba-pitfalls.md:104` | 11-13 |
| 63 | 卸载后直接 `mv` 回 11 GB 资源 | 属主还是旧 UID → 报 `Not enough storage` | `work/ba/audit/ba-pitfalls.md:109` | 11-13 |
| 64 | Frida **spawn** 模式（KSU + Android 15/16） | USAP 导致 `Failed to spawn: timed out`，严重时 zygote64 SIGABRT 手机重启 | `report/18-Frida与运行时绕过调研.md:39` | — |
| 65 | LSPatch **内嵌**模块进目标 APK | 模块自签名校验（`EXPECTED_SHA256`）直接拒绝注入 | `report/05-AzusaBA可复用资产.md:342` | — |
| 66 | 让客户端不说 TLS（改 scheme 成 http） | 需要改 `get_ApiUrl` 返回值（`Il2CppString*`，不是 bool，需构造对象）⇒ 比 patch 证书难两步 | `report/14-运行期dump与证书补丁方案.md:374` | 未做 |
| 67 | 用 `Env=dev` 切 test 环境 | 已经是 `Env=dev`，客户端仍连 `gsqc-api` ⇒ 不是开关 | `report/14-运行期dump与证书补丁方案.md:379` | — |
| 68 | 在 `libil2cpp.so` 里 grep 托管方法名（`ValidateCertificate` / `CustomCertificateHandler`） | **0 命中**——C# 方法名只在 metadata 的字符串区，so 里没有符号锚点，这条路从原理上就不成立 | `report/02-注入链审计.md:419`、`report/17-运行时hook方案评估.md:214` | — |

---

## 3. 主题索引

### 3.1 网关 / 协议 / 加密

**结论一句话**：网关入口是 `POST /api/gateway`（Shittim，两段合法，吃 `multipart` + `mx`），而**国服发的是另一套信封**（`protocol`/`encode`/`packet` 三文本字段）。国服信封**已完全破解**：`packet = base64([u32 len][gzip([iv:16][AES-256-CBC ct][key:32 明文])])`，`protocol = BASE32(MD5(UTF-16LE(名字)))`。剩下唯一未知不在加密，而在**客户端收到 200 之后为什么不发第二个协议请求**。

- 详细：`report/28`（Shittim 源码级核对）、`report/32`（信封对照）、`report/33`（protocol 破解 + 开源情报）、`report/34`（432 B 结构分析，§六 的 `DecryptOrReturnOriginal` 是关键）、`report/35`（**最终解密算法**）、`report/36`（Account_Auth 响应 24 键清单）
- 关键数字：`packet` 内层 **432 = 16+384+32**；`key` = 包尾 32 B ASCII；明文 373 B；完整 JSON 399 B；`Account_Auth` 响应 3740 B（gzip 1269 B）
- 关键文件/工具：`report/_tmp/mx_crypto/cn_cipher.py`（可复用模块，自带 `--selftest`）、`mx_decode.py`、`aes_pure.py`、`sample_432.bin`、`out.mx`（334 B，Shittim 能吃的 `.mx`）
- 待解决：第二份样本交叉验证（尾部 key 应不同）；响应方向加密格式；`protocol`→协议名映射表（但公式已知，可算）
- 判据纪律：`500 ≠ 鉴权失败`（非 multipart 必 500）；`ResultState=1` 只对 CheckYostar/CheckNexon 有意义

### 3.2 证书 / CA / TLS pinning

**结论一句话**：**这条线整体已从主线撤下**。TLS 对 `state-api` 在 01:34:52 就已经通了；46 条 `alert 49` 全在 CA 生效（01:33:45）之前；"客户端不发 SNI"被 pcap 推翻；`access_denied(49)` 的"应用层 pinning"定性也在"客户端落在 `0.default` 拿 `CN=default`"这一前提下失真。**真正的卡点在应用层（协议/响应解析），不在证书。**

- 详细：`report/20`（Android 14–17 CA 注入深度调研，最全）、`report/22-服务端取证记录.md`（alert 逐条统计）、`report/25`（把证书/SNI/pinning 三条一并排除）、**`report/23-主线改判-TLS已通应用层卡点.md`（改判本身）**
- 关键事实：上游三域名依赖 SNI；客户端 ClientHello 353 B 带 SNI；CA 生效时刻 01:33:45；`example.com` 真证书 2026-12-12 到期（deadline 12-05）
- 已退役：自签 `CN=BA Local CA` + `tlsproxy.py`/`connectproxy.py`/`make_certs.ps1` 整套（`report/13-总账-2026-11-14凌晨.md:82`）
- 若将来真需要再攻：`report/20` §3.4 的手写 `ca_inject.sh`（zygote ns `--rbind` 注入）> System CA Manager（KSU 原生）> AlwaysTrustUserCerts / MoveCertificate

### 3.3 服务端（Shittim / .NET / nginx）

**结论一句话**：Shittim 能跑、数据管道通、协议层对国服 **原生支持**（Yostar 系列协议齐全），但**没有 `/api/state` 路由**（必须 nginx 合成），且**连接组 URL 被源码钉死 loopback**（改不动，只能 `sub_filter`，已暂缓）。

- 详细：`report/09`（服务器盘点，最全）、`report/28`（源码级核对）、`report/04`（服务端就绪度审计 + 15 条 blocker）
- 关键路径：`/www/wwwroot/ba_srv`（运行目录）、`/www/wwwroot/ba_sdk`（卡密）、`Config/Config.json`（**真正生效的配置**）
- 关键命令：见 §5.2
- 已废弃：`/root/bapatch/*` 全部不存在；`appsettings*.json` 对 `UseCustomExcel` 无效；`pm2` 未 `save`（改用 systemd）

### 3.4 手机侧操作 / 取证方法

**结论一句话**：这台机器只能"读 + 杀进程 + 点不了的屏幕"。所有"点一下"的操作**必须由人手动完成**；一次实验只能改一个变量，且**判据只认 pcap / conntrack / 截图逐像素**。

- 详细：`report/21-手机侧执行记录.md`（1617 行，最完整的执行流水）、`report/06`（基线恢复 + 第 7 节的取证方法论）、`report/10`（实验有效性的方法论审计）
- 通道：`report/_tmp/rsh.py` → `busybox nc -ll -p 18080 -e /system/bin/sh`（**单连接**）
- 判读纪律五条：见 `report/29-进度-网关未调用与判据纪律.md:67`
- 常驻项（**全部易失，重启即失**）：`/data/local/tmp/relay.sh`（8080 中转）、`/data/misc/user/0/cacerts-added/fd8b2b01.0`、DNAT + ip6 REJECT 规则
- 回滚命令：`report/06-手机基线恢复.md:402`（逐条 `-D`，禁用 `-F`）

### 3.5 客户端静态逆向（il2cpp / metadata / RSA key）

**结论一句话**：metadata 头部加密但**字符串区明文**，所以"按名查"可行、"按表解析"不可行；`il2cpp_*` 导出被抹但**可离线恢复 1201 个符号**（124 个 `il2cpp_*` 带地址，4 字节跳转桩可直接调用）；`.text` 有 26.2% 页被 ACE 加密 ⇒ 离线补丁只在明文页可行。

- 详细：`report/24`（schema 反推）、`report/11`（网关与证书静态）、`report/15`（PEM 判读）、`report/30`（**RSA 公钥定位与等长替换，含可用工具**）、`report/17`（符号恢复 + hook 方案）、`report/02`（注入链审计）
- 工具：`bapatch/patch_metadata_key.py`（metadata 公钥替换）、`report/_tmp/hookeval/recover_final.py`（符号恢复，输出 `il2cpp_syms.json`）、`bapatch/mkprobe.py`（代码洞探针构建）
- 关键地址表：`report/17-运行时hook方案评估.md:49`（16 个 API 的 vaddr + 形态）
- 代码洞：`0xf2c2410`，容量 3056 B；`DT_INIT` 原值 `0x10496434`

### 3.6 上游接口 / state / catalog

**结论一句话**：**必须带 4 个业务头**才能拿到真实应答（`APP-VER`/`PLATFORM-ID`/`CHANNEL-ID`/`SERVER-NAME`）。`gsqc`→676 B/State:1/10 字段；`state-api`→161 B/Servers+State:1；`static` 是 OSS 桶（`bluearchive-static`，匿名可读、不可 ListBucket），资源根是 `{root}/AssetBundles/Android/`，`prodm39/` 下有 1646 个 MXBundle。

- 详细：`report/31`（**真实 catalog 与版本清单，最重要**）、`report/22-真实上游接口取证.md`（TLS/证书/SNI 全量对照，最全）、`report/33` §四（国际服 MX 信封算法：headless-bluearchive SDK）
- 关键：`catalog_Remote.json` **远端很可能不存在**（`m_DisableCatalogUpdateOnStart=true`，三处 catalog 全指 `persistentDataPath`）；客户端是**本地优先**（11 GB 资产在本地）
- 三条 CDN 线路内容一致（`static`/`static-qc`/`static-hs`），只需代理一条或全透传
- 开源参考（不含国服）：`headless-bluearchive/SDK`（Python，`core/crypto.py`+`core/packet.py`+`core/protocol.py`）、`Deathemonic/BA-CY`（Rust+FFI）、`Neoexm/Shittim-Server`（C#）

### 3.7 已知的"看起来是问题其实不是"的噪音

| 现象 | 真相 | 出处 |
|---|---|---|
| `TapSDK: 包名、签名错误。详见 ErrLog` | 改包重签的必然结果，不影响流程 | `report/29-进度-网关未调用与判据纪律.md:81` |
| `RetryUtils [req_1]/[req_2] 网络请求失败`（指数退避到 128 s） | 阿里 netspeed 诊断进程（pid 4747），**与游戏无关** | `report/29-进度-网关未调用与判据纪律.md:82`、`report/21-手机侧执行记录.md:651` |
| `LogProducerHttpTool ... Hostname not verified`（DN=`CN=*.bluearchive-cn.com`） | 阿里 SLS 日志上传，主机名不匹配（不是链问题） | `report/21-手机侧执行记录.md:743` |
| `openlog.cpp:356 Failed to post events status=404` | TapTap 埋点上报 | `report/29-进度-网关未调用与判据纪律.md:84` |
| `TapDB: 当前应用已关闭 TapTapEvent 开关` | 埋点开关 | `report/21-手机侧执行记录.md:533` |
| `net_d_000` 里 798 条 MTR `lastHop:0` | DNAT 抹平跳数导致的无效诊断，与登录无关 | `report/29-进度-网关未调用与判据纪律.md:85` |
| `com.follow.clash` 在跑 | 未建 VPN、无 tun、无 socket、不占 8080 | `report/21-手机侧执行记录.md:1014` |
| `logcat -b crash` 里 `FORTIFY: pthread_mutex_lock called on a destroyed mutex` | ACE/pushcore 子进程退出噪音，非主进程 | `report/06-手机基线恢复.md:420` |
| `status=9` 反复退出 | 系统小窗/内存回收，不是 ACE | `work/ba/audit/ba-pitfalls.md:99` |
| `36.150.72.122` 41 KB 上行 | 未能定名，非主线 | `report/29-进度-网关未调用与判据纪律.md:87` |
| `RetryUtils 5 次退避 = 弹窗成因` | 时序上晚于弹窗，且每轮一样 | `report/25-根因定案-状态接口schema错误.md:63` |
| `uid 10576 的 443 全量劫持会误伤第三方域名` | 是**真实约束**（不是噪音），用 SNI 分流解决 | `report/29-进度-网关未调用与判据纪律.md:12` |

---

## 4. 尚未验证的假设（可以试的）

| 假设 | 依据 | 建议的验证方法 | 出处 |
|---|---|---|---|
| **响应方向不需要加密**（客户端 `DecryptOrReturnOriginal` 会先当明文 JSON 试） | 方法名 + `IsSpecificErrorJson` 必须先能当 JSON 解析 | 回一个明文 JSON 信封，看是否被接受 | `report/34-国服packet二进制结构分析.md:274`、`:320` |
| 客户端"收到 200 后停住"是因为**响应信封没按国服格式封装**（`{"protocol":"Account_Auth","packet":"…"}` 是 Shittim 格式） | 桥已回 200 + 3740 B，客户端无弹窗但无第二请求 | 按国服信封回一次（`protocol` 用 base32 token） | `report/21-手机侧执行记录.md:1617`、`report/36-Account_Auth响应字段清单.md:143` |
| `Hash: 4303557230595`（请求明文里）是防篡改校验，服务端可能需要校验 | 字段名直白 | 改/清 `Hash` 看客户端/服务端行为 | `report/35-国服网关信封加密破解.md:94` |
| `PROTOCOL_HEAD_RESERVE` 实际值 = 16（已按 32 字节对齐拟合） | 数值拟合干净 | 反编译 `PacketCryptManager.EncryptRequest` 或抓多包差分 | `report/34-国服packet二进制结构分析.md:258` |
| 第二份 `packet` 样本的尾部 32 B key 应不同、布局一致 | 每包随机生成 key | 连点两次抓两份差分 | `report/35-国服网关信封加密破解.md:124` |
| `Servers` 需要 ≥2 个元素（`GetApiServerInfo` 是迭代器、有 isLive 标记） | 反编译字段 + 真实上游给 2 个 | 给 1 个 vs 2 个对比 | `report/24-state接口schema反推.md:224` |
| `CDNLineCount = 0` 可能触发除零 | int 默认 0 + 名字 | 给 1 试 | `report/24-state接口schema反推.md:330` |
| ACE 是否校验 `global-metadata.dat`（改 337 字节、文件大小不变） | 只证明 libunity 有磁盘哈希 | 装 patched metadata 冷启，看是否 SIGBUS / 是否过 "Unpacking game resources" | `report/30-网关RSA公钥定位与替换.md:386` |
| 设备上 `global-metadata.dat` 的实际读取路径（APK 内 zip 条目 vs 解包后独立文件） | `extractNativeLibs=true` 但 `assets/` 仍是 zip 条目 | 看是否必须重打包；或查 `files/il2cpp/Metadata/global-metadata.dat`（**外部存储里有一份**！） | `report/30-…:336`、`report/21-手机侧执行记录.md:1116` |
| 用 `--rbind` 注入 zygote ns 能让 CA 真正生效 | A14+ private propagation 的官方解法 | 跑 `report/20` §3.4 脚本后 `nsenter` 在 App ns 里 `ls -lZ` | `report/20-AndroidCA注入深度调研.md:347` |
| LSPosed 模块 hook **框架类**（`javax.net.ssl.*`）不受"替身类"影响 | boot classpath 由 LSPosed 自己的 classloader 解析 | 装 UserCABridge（API 26–36）试一次 | `report/20-AndroidCA注入深度调研.md:621` |
| `State` 的 2 可能是 `AppUpdate`（强制更新） | 枚举 `{Maintain, AppUpdate}` + `State:1`=维护 | 回 `State:2` 看客户端行为 | `report/24-state接口schema反推.md:343` |
| `m_DisableCatalogUpdateOnStart=true` ⇒ 远端无需 catalog | settings.json 原文 + 40 条路径全 404 | 直接把本地 `catalog_Remote.json` 喂回去 | `report/31-真实catalog与版本清单取证.md:195` |
| 664 个 bundle 的完整文件名可从客户端本地 `catalog_Remote.json`（81 MB）反推 | 文件就在手机 `persistentDataPath` | 解析 `catalog_Remote.json` | `report/21-手机侧执行记录.md:1160`、`report/31-…:264` |
| 客户端 `Account_Auth` 之后的下一条协议要等 `SessionKey` 生效 | `SessionKey` 是所有 in-session 协议凭据 | 检查桥回的 3740 B 里 `SessionKey.AccountServerId/MxToken` 是否被正确接受 | `report/36-Account_Auth响应字段清单.md:155` |

---

## 5. 有用的服务器/手机操作命令速查

### 5.1 手机侧（root shell，`u:r:ksu:s0`）

```sh
# ── 通道 ────────────────────────────────────────────────
# 建立（通过 Operit super_admin:shell 执行一次）
su -c 'setsid busybox nc -ll -p 18080 -e /system/bin/sh &'
# PC 侧驱动： report/_tmp/rsh.py  （单连接，不能并发）

# ── 启动/杀掉（am 被 SELinux 挡，只能这么干）─────────────
for p in $(pidof com.RoamingStar.BlueArchive); do kill -9 $p; done; sleep 1
pidof com.RoamingStar.BlueArchive          # 期望空
monkey -p com.RoamingStar.BlueArchive -c android.intent.category.LAUNCHER 1

# ── 原子替换 .so（禁止 cat > dst！）──────────────────────
D=$(pm path com.RoamingStar.BlueArchive | sed 's|/base.apk$||')/lib/arm64
cp /data/local/tmp/il2cpp_orig.so $D/libil2cpp.so.new
sha256sum $D/libil2cpp.so.new               # 比对期望值
restorecon -v $D/libil2cpp.so.new
mv -f $D/libil2cpp.so.new $D/libil2cpp.so   # rename(2)，无 0 字节窗口
chown system:system $D/libil2cpp.so; chmod 0755 $D/libil2cpp.so

# ── 流量劫持（易失，重启即失）────────────────────────────
iptables -t nat -I OUTPUT 1 -p tcp -m owner --uid-owner 10576 --dport 443 \
         ! -d <SERVER_IP> -j DNAT --to-destination <SERVER_IP>:443
ip6tables -I OUTPUT -p tcp -m owner --uid-owner 10576 --dport 443 \
         -j REJECT --reject-with icmp6-port-unreachable
iptables -t nat -L OUTPUT -n -v        # 看命中计数（这是唯一可信的"流量到了"指标）
iptables -S OUTPUT                     # 存档（禁 -F，逐条 -D 回滚）

# ── 判连接（注意：ss 显示 DNAT 前的原始 peer）─────────────
cat /proc/<pid>/net/nf_conntrack | grep <SERVER_IP>   # mark=262253 = 被我们的 DNAT 拿住
ss -tnp | grep tar.BlueArchive
grep -E 'libil2cpp|libunity|libmain' /proc/<pid>/maps

# ── 取证：logcat ────────────────────────────────────────
logcat -c -b all
logcat -d -b all -v time > /sdcard/r.txt          # 全量落盘再 grep（-s 不给 tag 会输出空）
grep -E '[VDIWEF]/Unity' /sdcard/r.txt            # Unity 业务日志（E/Unity 才是关键）
grep -iE 'DNS_CACHE' /sdcard/r.txt                # netd 代答的域名解析（uid:10576）
grep -iE 'trust|anchor|handshake|CertificateException' /sdcard/r.txt
dumpsys activity exit-info com.RoamingStar.BlueArchive   # reason/status：7=SIGBUS(ACE) 9=SIGKILL(系统)

# ── 触摸注入（Unity SurfaceView 不响应，仅记录用）────────
sendevent /dev/input/event5 ...            # event5=touchpanel；raw = 像素×16

# ── CA 注入（zygote ns，A14+ 正解）───────────────────────
nsenter --mount=/proc/$(pidof zygote64)/ns/mnt -- \
        /system/bin/mount --rbind /data/local/tmp/cacerts-work /apex/com.android.conscrypt/cacerts
nsenter --mount=/proc/<gamepid>/ns/mnt -- /system/bin/ls -lZ /apex/com.android.conscrypt/cacerts | grep <hash>
chcon u:object_r:system_file:s0 <file>      # 或 chcon --reference=同目录原厂文件
```

### 5.2 服务端（`<SERVER_IP>`，Ubuntu 22.04 / 宝塔）

```sh
# ── 服务 ────────────────────────────────────────────────
systemctl status ba-sdk ba-shittim; systemctl restart ba-shittim
journalctl -u ba-shittim -n 50; tail -f /var/log/ba-shittim.log
ss -tlnp | grep -E ':5000|:5100|:8080'

# ── 健康检查（路由存在的三条判据）───────────────────────
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:5000/api/gateway          # 200 空 body
curl -sS http://127.0.0.1:5000/api/Queuing/Ping                                      # "Pong"
curl -sS -X POST http://127.0.0.1:5000/api/gateway -o - -w '%{http_code}\n'          # 500（非 multipart）
curl -sS -X POST -F 'mx=@out.mx' http://127.0.0.1:5000/api/gateway                   # 正确姿势

# ── nginx ──────────────────────────────────────────────
nginx -t && nginx -s reload
nginx -T | grep -nE 'server_name|ssl_certificate|location'         # 展开后的真实配置
ls -la /www/server/panel/vhost/nginx/                              # ba_mitm.conf / example.com.conf
tail -f /www/wwwlogs/ba_mitm.log                                   # 只收 *.bluearchive-cn.com 的 SNI
tail -f /www/wwwlogs/example.com.log                          # SDK + 我们域名（**手机流量在这**）
tail -F -n0 /www/wwwlogs/ba_mitm.log /www/wwwlogs/example.com.log | grep --line-buffered -E 'api/state|quick-login'

# ── 判 TLS（只认 pcap）──────────────────────────────────
tcpdump -i any -s 0 -w /root/ba_pcap/r_$(date +%H%M%S).pcap 'tcp port 443'   # 不要加 not src net！
python3 /root/ba_pcap/ana.py <pcap>          # flow 清单 / flight / 记录序列 / CH 解析
grep -c 'ssl_verify_client' <(nginx -T)      # 必须为 0（误开会导致 client-cert 相关 alert）

# ── 数据层 ─────────────────────────────────────────────
cat /www/wwwroot/ba_srv/Config/Config.json                       # ★ 真正生效的配置
grep -E 'Custom Excel|Now listening|SQLCipher|Mapped' /www/wwwroot/ba_srv/logs/log.txt
du -sh /www/wwwroot/ba_srv/Resources/*
xxd -l 16 /www/wwwroot/ba_srv/Resources/Dumped/ExcelDB.db        # 判断是否 SQLCipher
```

### 5.3 PC 侧（一次性工具，全部离线可用）

| 用途 | 命令/脚本 |
|---|---|
| 手机命令通道 | `python report\_tmp\rsh.py --file s1.sh --out s1.txt` |
| 推 271 MB 文件到手机 | `python send_file.py libil2cpp.bin 192.168.0.5 18082`（16.4 MB/s） |
| 构建代码洞探针 | `cd work\ba\bapatch && python mkprobe.py`（需 WSL 的 clang/ld.lld/llvm-objcopy；**msys64 的 as/gcc 是 x86，不能编 aarch64**） |
| 恢复 il2cpp 符号 | `python report\_tmp\hookeval\recover_final.py work\ba\bapatch\libil2cpp.bin il2cpp_syms.json` → 1201 / 124 |
| 替换 metadata 网关公钥 | `python bapatch\patch_metadata_key.py --in global-metadata.dat --dry-run`（再加 `--pubkey/--out/--verify`） |
| 解国服 packet / 造 .mx | `python report\_tmp\mx_crypto\cn_cipher.py --selftest`；`mx_decode.py --log ... --emit-mx out.mx` |
| 逐字节差分 / ELF 结构 | `python report\_tmp\elfdiff.py a.bin b.bin`；`caveid.py`；`gotfacts.py`；`blcount.py`；`unityrefs.py` |
| 弹窗像素判定 | `python _tmp\chkcard.py`（蓝色按钮精确色 ≈RGB(119,221,255)，限定 x1100-1920/y820-1010；已知弹窗 btn_px=58439） |

### 5.4 关键地址/路径速查

| 项 | 值 | 出处 |
|---|---|---|
| libil2cpp 代码洞 | `0xf2c2410`，容量 3056 B | `work/ba/bapatch/PROBE_README.md:78` |
| 原厂 `DT_INIT` | `0x10496434`；`.dynamic` 项在文件 `0xfa2fc48`，值在 `0xfa2fc50` | `report/02-注入链审计.md:72` |
| libil2cpp RX LOAD | `off=va=0x59b8000`，`filesz 0x990a410→0x990b410` | `report/02-注入链审计.md:70` |
| libil2cpp BSS 可写尾 | `0x1024b4f8 – 0x10491d58`（≈2.28 MiB） | `report/02-注入链审计.md:564` |
| libunity GOT | `gettimeofday 0x13d94d0` / `getaddrinfo 0x13d94d8` / `basename 0x13d94e0` / `connect 0x13d95d8` | `report/02-注入链审计.md:556` |
| metadata 公钥三段 | A `0x0178CC60`(150) / M `0x012D5F88`(150) / C `0x0178CBA0`(151)，共 451 B | `report/30-网关RSA公钥定位与替换.md:16` |
| metadata 文件 | `bapatch/global-metadata_patched.dat`（sha `f0a30008…`）/ 原文件 `2352cb57…` | `report/30-…:293` |
| `il2cpp_class_for_each` | `0x063c3b50` → 真身 `0x6391eb0` | `report/17-运行时hook方案评估.md:51` |
| `pthread_create` GOT 槽 | `0x0fbaff00`（另有 open `0xfbafa58` / write `0xfbaf968` / close `0xfbafa70` / nanosleep `0xfbaff48`） | `work/ba/bapatch/PROBE_README.md:75` |
| 手机 `HasGone` 关键路径 | `/data/data/…/files/bainj.txt`（打点）、`…/files/probe.log`（探针）、`/data/local/tmp/libil2cpp.factory.so`（纯原厂）、`/sdcard/ba_data_bak`（11 GB 资源） | `work/ba/audit/ba-pitfalls.md:157`、`report/06-手机基线恢复.md:424` |
| 服务器根 | `/www/wwwroot/ba_srv`、`/www/wwwroot/ba_sdk`、`/www/wwwroot/bapatch/`（项目根，私钥不暴露） | `report/22-服务端取证记录.md:385` |

---

## 附录 A：已撤回的错误结论

> **这一节的存在意义**：团队里多次出现"先下了错结论、后来又自己撤回"的情况。这些错结论**仍然散落在各报告正文里**，新接手的人如果只读正文，会重走歧路。每条给：**曾经的结论 → 后来的正确结论 → 出处 → 现在的效力**。

| # | 曾经（错）的结论 | 更正（对）的结论 | 出处 | 效力 |
|---|---|---|---|---|
| **A-1** | 「`api/{path1}/{path2}` 要求三段，所以 `/api/state` 404」 | 路由前缀是 `[Route("api")]` + 动作 `[HttpPost("gateway")]`，**`POST /api/gateway` 只有两段、完全合法**；`/api/state` 404 是因为 **Shittim 根本没有 `state` 这个动作** | 错：`report/22-服务端取证记录.md:191`；对：`report/28-Shittim网关协议源码核对.md:18`、`:65`；另 `scripts/NOTES-gateway.md:7` | 已废 |
| **A-2** | 「`global-metadata.dat` 里那段 PEM 是**证书 pin**」 | 它是**网关握手 RSA 公钥**（加密 `Queuing_GetCryptoKeys`(50001) 的 key/IV），与 TLS 证书无关 | 错：`report/06-手机基线恢复.md:476`（"pinning 靶子很可能是…"）；对：`report/28-Shittim网关协议源码核对.md:717`、`report/19-网关攻坚-当前状态.md:49`、`report/15-PEM公钥与pinning判读.md:14` | 已废（关键） |
| **A-3** | 「metadata 里那把是 **4096 位**，所以必须造 4096 位的钥匙、等长替换」 | 国服是 **RSA-2048 / 451 B / 三段 150-150-151**；`ChunkLengths=[272,272,255]` 是**国际服**的切分。用 4096 位 PEM（800 B）会被工具拒绝（>451 B 洞） | 错：`scripts/NOTES-gateway.md:105`、`report/28-Shittim网关协议源码核对.md:719`；对：`report/30-网关RSA公钥定位与替换.md:12`、`:168` | 已废（关键） |
| **A-4** | 「`getaddrinfo` 的 libunity GOT 偏移 = `0x13d94d0`；`0x13d94d8` 实为 libc `basename`」（README 自称"这是此前所有注入崩溃的根因"） | **错位一格**：`0x13d94d0 = gettimeofday`，`0x13d94d8 = getaddrinfo`，`0x13d94e0 = basename`。三重验证：`.rela.plt` 符号表 / `unity_full.asm` 的 PLT 注释 / 现役机器码内嵌 `movz #0x94d0` | 错：`report/01-现状与已试方向.md:228`（转述 README）；对：`report/02-注入链审计.md:13`、`:556`；`work/ba/audit/ba-pitfalls.md:181` 的 `0x13d94d8` 反而是**对的** | 已定位；**修正版从未跑过** |
| **A-5** | 「改 libil2cpp 的 PLT/GOT 没反应，是因为该 so 走 **-fno-plt 风格**」 | 真因是这两个导入在 **libil2cpp 里没有调用点**（346 万条 BL 扫描：GA=0、connect=0，其它 65 个桩被调 116,219 次）。方向对、**归因错** | 错：`work/ba/audit/ba-pitfalls.md:190`；对：`report/02-注入链审计.md:23`、`report/00-下一步总方案.md:76` | 已废 |
| **A-6** | 「libil2cpp 的 GA/CO GOT 槽值 = `0xf2c0010`（仍指 PLT0）⇒ 该导入从未被调用」 | **证据链错**：`0xf2c0010` 是**文件里的内容**（RELRO 页 / 文件 r--p 映射），`BIND_NOW` 下运行时槽位是已解析的 libc 地址。结论"确实没调用点"**巧合正确** | 错：`work/ba/audit/ba-pitfalls.md:209`；对：`report/02-注入链审计.md:76` | 结论保留，证据作废 |
| **A-7** | 「`files/Hosts` **不决定连接目标**，只做记录/展示」 | 它是 **`Servers[]` 的写穿缓存**（被解析成候选列表）：state 成功时**覆盖**、失败时**不回落**；写入正确格式的条目会被**原样保留**。旧实验无效是因为**写入格式不对**（裸 `127.0.0.1:9443` vs 二进制结构） | 错：`work/ba/audit/ba-pitfalls.md:128`、`report/01-现状与已试方向.md:198`、`report/10-网关重定向-已试清单与有效缺口.md:31`；对：`report/08-手机接管与真因.md:148`、`report/10-…:110`、`report/13-总账-2026-11-14凌晨.md:121` | 已废（关键） |
| **A-8** | 「`/system/etc/hosts` 覆盖无效，因为**游戏用 HTTPDNS、不走系统解析**」 | 真因是 app 解析由 **netd(pid 1937)** 代答，而 netd 在**另一个 mount namespace**；shell 侧 `mount --bind` 覆盖不到。不是 HTTPDNS | 错：`work/ba/audit/ba-pitfalls.md:179`；对：`report/06-手机基线恢复.md:198`、`report/10-…:89`、`report/13-…:122` | 归因已废（现象仍成立） |
| **A-9** | 「客户端建 TLS **不发 SNI** → 落到 nginx `0.default` → **这是根因**」 | `state-api` 的 ClientHello **353 B 明确带 SNI**；那条"无 SNI"的 ClientHello 是**别的连接**（很可能是 gsqc 或裸 IP）。且加 `default_server` 后 ServerFlight 2597 B（已拿到我们证书）**屏幕仍报错** ⇒ 假设被排除 | 错：`report/19-网关攻坚-当前状态.md:21`、`report/06-手机基线恢复.md:549`；对：`report/23-主线改判-TLS已通应用层卡点.md:48`、`report/06-…:586`、`report/26-进度-NRE已修-卡点后移.md:93`、`report/22-真实上游接口取证.md:13` | 已废 |
| **A-10** | 「`access_denied(49)` = **应用层 pinning/自定义校验拒绝**，所以别装 CA 了、直接打托管层」 | 46 条 `alert 49` **全部落在 01:24:58–01:33:45**（CA 生效之前），01:33:45 后**归零**、01:34:52 同一条链路直接 200 ⇒ 49 的消失与 CA 生效严格同步，指向 trust store。后来真正的报错是 `Curl error 60 / UnityTls error code: 7`（unknown CA） | 错：`report/15-PEM公钥与pinning判读.md:15`、`report/16-pinning外部经验.md:11`、`report/21-决策日志-CA路线攻坚.md:26`；对：`report/22-服务端取证记录.md:15`、`:138`、`report/25-根因定案-状态接口schema错误.md:58`、`report/06-…:643` | 已降级（关键） |
| **A-11** | 「Unity 一条日志都不打」（据此认为 logcat 无信息量） | **错**：是过滤条件用了 `E/` 前缀。改成 `[VDIWEF]/Unity` 后抓到 `NullReferenceException at ServerInfoDataRepository.GetApiServerInfo`，直接定位了卡点 | 错：`report/21-手机侧执行记录.md:371`；对：`report/26-进度-NRE已修-卡点后移.md:92`、`report/21-…:501` | 已废 |
| **A-12** | 「E64 表现从『被官方拒绝』变成**超时**，说明路径已改、实现仍有阻塞」 | **信号零判别力**：超时至少有四种成因（地址写错 / 端口不通 / 没人应答 / TLS 挂自签证书），全程没有一次"TCP 是否到达"的旁证；且 19:57 起客户端在 0.3 s 自杀循环 | 错：`work/ba/audit/ba-pitfalls.md:184`；对：`report/10-…:61`、`report/13-…:123`、`report/08-手机接管与真因.md:107` | 不成立（未定论） |
| **A-13** | 「现役可用包是 E42，能进主程序」 | 设备上**不是 E42**：APK 内嵌的 `libil2cpp.so` 本身带桩（sha 既非原厂 `5ac1cbe0` 也非 g20 `a473ba16`，是第三份 `6e2edf5a`） | 错：`report/01-现状与已试方向.md:13`；对：`report/08-手机接管与真因.md:147`、`:132`、`report/13-…:79` | 已废 |
| **A-14** | 「`status=9` 是 ACE 杀的」 | **9 = SIGKILL = 系统小窗/内存回收**；ACE 用 SIGBUS(status=7)。当时 free 仅 876 MB | 错：`report/01-现状与已试方向.md:190`；对：`work/ba/audit/ba-pitfalls.md:99`、`report/13-…:77` | 已废 |
| **A-15** | 「ACE 联网校验卡住启动」 | 否：对该 UID 全量 REJECT 外网（仅放行 127.0.0.0/8）后**仍卡死** ⇒ 与网络无关（真因是 §4.3 的 sem 阻塞） | 错：`report/01-现状与已试方向.md:188`；对：`work/ba/audit/ba-pitfalls.md:95` | 已废 |
| **A-16** | 「`UseCustomExcel=true` + `DownloadExcelTables=false` 是正确做法」 | **反向**：`LoadResources` 先 `ResetDumped()` 删 316 MB 资源，再用空 `CdnBaseUrl` 拼非法 URI → `[FTL]` 退出。正确值是 `false` | 错：`work/ba/audit/ba-pitfalls.md:37`、`report/04-服务端就绪度.md:168`；对：`report/09-服务器盘点.md:168`、`report/13-…:127` | 已废（反向） |
| **A-17** | 「.NET 在设备上起不来，报 `GC: Reserving 256 GiB … failed` ⇒ 内存不够」 | 真因是 `Shittim-Server.runtimeconfig.json` 里 `System.GC.Server: true`；只要 `DOTNET_gcServer=0` 就不会 reserve。实测 RSS 仅 229 MB，`0x40000000` 只是上限 | 错：`work/ba/audit/ba-pitfalls.md:39`；对：`report/09-服务器盘点.md:380`、`report/13-…:128` | 条件已明确 |
| **A-18** | 「设备侧 `iptables` NAT（DNAT）在本机不生效，不能靠路由劫持」 | 这句只有结论、无命令/无链名/无对照，属"无方法学支撑的一句话否决"。实测 `iptables -t nat … DNAT` **rc=0 可用**，且是全项目最核心的手段 | 错：`report/10-…:44`；对：`report/13-…:84`、`report/06-手机基线恢复.md:272` | 已废（关键） |
| **A-19** | 「278 条外部流量 = 客户端打到我们服务器了」 | **误读**：`/`×93、`/checkhealth.html`×92、`/api/health`×92 = **1:1:1 的 92 轮**崩溃循环里的 SDK 网络探测。`POST /common/config` = **0 次**，客户端从没走到登录层 | 错：`report/09-服务器盘点.md:769`；对：`report/09-…:784`（同文自纠）、`report/13-…:130` | 已废 |
| **A-20** | 「`res/Dk.xml` 证实 `cleartextTrafficPermitted=true`（全域名允许明文）」 | **该文件在 APK 里不存在**：`res/xml` 只有 `filepaths.xml` / `http.xml` / `sdk_file_provider_paths.xml` / `standalone_badge*.xml` / `tapupdate_file_provider.xml` / `unitywebview_file_provider_paths.xml`。`AndroidManifest.xml` 里也**没有** `networkSecurityConfig` 属性 | 错：`report/01-现状与已试方向.md:54`、`report/03-上游情报.md:396`；对：`report/06-手机基线恢复.md:628` | 已废（结论仍由 `http.xml` + 实测 `sdk_url=http://` 支持，但**别quoting Dk.xml**） |
| **A-21** | 「`State:0` = 正常开服，我们回 0 是对的」 | **反了**：`State:0` 停在 state 校验阶段；**`State:1` 才继续去请求网关**。真实生产 DTO 也是 `State:1` | 错：`report/24-state接口schema反推.md:346`、`report/25-根因定案-状态接口schema错误.md:72`；对：`report/21-手机侧执行记录.md:1047`、`:1069`、`report/31-真实catalog与版本清单取证.md:66` | 已废（关键） |
| **A-22** | 「`/api/state` 可以一个 `location =` 返回同一份 JSON 通吃所有 Host」 | **结构性错误**：是两个不同 DTO —— `state-api` 回 `{Servers,State,Msg}`（小），`gsqc-api`/`gs-api` 回 `ServerInfoConnectionGroupData`（大，实测只发 10 字段）。第二跳拿小 DTO 去反序列化大 DTO 必然全 null | 错：`report/09-服务器盘点.md:502`、`report/22-服务端取证记录.md:292`；对：`report/24-…:414`、`report/25-…:50` | 已废 |
| **A-23** | 「真实 `state-api/api/state` 应答就是 **200 + 0 字节**」 | **条件性错误**：不带 4 个业务头才 0 字节；**带上 `APP-VER/PLATFORM-ID/CHANNEL-ID/SERVER-NAME` 后是 161 B**（含 `Servers`+`State:1`）。同理 `gsqc` 从 214 B 变 676 B | 错：`report/22-真实上游接口取证.md:41`、`:495`、`report/25-…:36`；对：`report/31-真实catalog与版本清单取证.md:78`、`:95` | 已修正（关键） |
| **A-24** | 「`example.com` 可以当上游参考」（曾把它的应答当上游证据） | 它的 A 记录就是 `<SERVER_IP>` = **我们自己那台服务器**；之前拿到的 `/sdk/`、`/api/` 应答全是我们自己 nginx 的回响 | 错：`report/04-服务端就绪度.md:407`（把它当"自有域名"之前的混乱）、`report/22-真实上游接口取证.md:47`（§0.3 的定案本身）；对：`report/25-…:61` | 已废 |
| **A-25** | 「`protocol` 字段是 **base64**，解出 19 字节密文」 | **是 base32**：26 字符 = `ceil(16×8/5)`，解出干净的 **16 字节**；且算法是 `BASE32(MD5(UTF-16LE(名字)))`，逐字符吻合 | 错：`report/32-国服网关信封混淆分析.md:114`（`raw : … len : 19`）；对：`report/33-国服网关协议开源情报.md:50`、`:67`、`report/34-国服packet二进制结构分析.md:87`（34 号自己已纠正为 base32）、`report/35-…:86` | 已废（方向错） |
| **A-26** | 「432 B 末尾 32 字节是**明文 base64 token**（协议证明/校验）」（并据此推 Rijndael-256 块） | 那是 **AES-256 的 key 本身**（客户端每包随机生成、明文附在密文后）。算法是标准 **AES-256-CBC + PKCS7**（16 字节块），不是 Rijndael-256 | 错：`report/34-国服packet二进制结构分析.md:96`、`:129`、`:184`；对：`report/35-国服网关信封加密破解.md:13`、`:145` | 已废（关键） |
| **A-27** | 「国服信封是 AES + **passphrase**（`StringCipher.passphrase`）+ PBKDF2 派生密钥，必须爆破口令」 | **没有 passphrase、没有 PBKDF2、没有 RSA**。key 明文附在包尾，一次就解开（590,858 条字符串 × 5 种布局的爆破**全部零命中**，是把问题建模错了） | 错：`report/32-国服网关信封混淆分析.md:21`、`:296`；对：`report/35-…:35`、`:137` | 已废（关键） |
| **A-28** | 「国服首包是 `Account_CheckNexon`(1014) 的 RSA 握手，必须先替换 metadata RSA 公钥才能过」 | 实测首条业务请求是 **`Account_Auth`(1002)**；国服走 Yostar 线（`Account_CheckYostar` 1009），且 `Account_Auth` 的加密用的是**包内明文 AES key**，与 metadata 那把 RSA 公钥是**两套机制** | 错：`report/04-服务端就绪度.md:294`、`report/27-SDK登录协议调研.md:48`、`report/03-上游情报.md:120`；对：`report/27-…:324`、`report/33-…:96`、`report/32-…:271` | 已修正（重要） |
| **A-29** | 「`ResultState` 是成功字段，响应必须回 `1`」（被当成通用规则） | `ResultState` **只属于 `Account_CheckYostar` / `Account_CheckNexon`**；`Account_Auth` 响应里**既没有 `ResultState` 也没有 `ErrorCode`**，这是正确的、不是缺失 | 错（推广）：`report/29-进度-网关未调用与判据纪律.md:62`（原文只讲 CheckYostar，容易被误推广）；对：`report/36-Account_Auth响应字段清单.md:12` | 范围已收窄 |
| **A-30** | 「AzusaBA 5.2.5 在国服 3.0.2 上跑通 26 个 hook」 | **不可能**：它全靠 `xdl_sym("il2cpp_*")`，而本 so 的 `st_name` 全被抹 → `getaddr()` 永远返回 nullptr，60 s 后放弃，`okHooks = 0/26`。作者很可能只在国际服验证过 | 错：`report/05-AzusaBA可复用资产.md:39`（转述）；对：`report/17-运行时hook方案评估.md:88`、`:106` | 已废 |
| **A-31** | 「`libil2cpp.so` 不能改 / 不要 patch，风险极高」 | **已被推翻**：E38 填充字节翻转、E63 代码洞注入、root 原位替换均正常启动；`ace-ipc.md §3` 已证无 hash pin | 错：`report/01-现状与已试方向.md:277`（列为"已被推翻"）；对：`work/ba/audit/ba-pitfalls.md:171`、`report/01-…:128` | 已废（关键） |
| **A-32** | 「`il2cpp_*` 导出为 0 ⇒ 无法按名解析 ⇒ 只能运行期 dump metadata + Il2CppDumper」 | 还有第三条路：**离线从 `.gnu.hash`+`.dynstr` 恢复 1201 个符号（124 个 `il2cpp_*` 带地址，4 字节跳转桩可直接调用）**，完全绕开 dlsym 与 metadata | 错（唯一解）：`report/02-注入链审计.md:383`、`report/14-运行期dump与证书补丁方案.md:25`；对：`report/17-运行时hook方案评估.md:39`、`:73` | 已废（关键） |
| **A-33** | 「运行期 dump 解密态 metadata 大概率可行（内存里应是 38.4 MB 匿名块 + `AF1BB1FA`）」 | **实测不可行**：129 块 rw-p（只看前 16 KB）→ 0 命中；放宽到 214 块 r--p+rw-p 全量 → 仍 0 命中。内存里没有明文 metadata 字符串 | 错（预估）：`report/14-…:18`、`:436`；对：`report/06-手机基线恢复.md:491`、`:511`、`report/15-…:198` | 已废 |
| **A-34** | 「`Hosts` 能证明客户端请求过 state（删掉后会重建）」 | 删掉 `Hosts` 后客户端**没有重建** ⇒ 客户端**从头到尾没请求过 state** | 错（曾作为"客户端会请求 state"的旁证）：`report/11-客户端静态逆向-网关与证书.md:201`（M3 模型）；对：`report/06-手机基线恢复.md:309`、`report/19-网关攻坚-当前状态.md:10` | 已废 |
| **A-35** | 「HTTPS 证书那道墙必须攻（自签 CA / pinning 绕过）」 | **不需要攻**：只要客户端最终访问的 URL 落在**自有域名**（真证书）下，TLS 天然通过。实测 `https://example.com/api/state` 公网、真证书、零绕过 → 200 | 错：`report/04-服务端就绪度.md:407`（R01/R02 前提）；对：`report/09-服务器盘点.md:688`（D04 的实测）、`report/13-…:82` | 已废 |
| **A-36** | 「宝塔 WAF 是卡点（其 `post:403` 规则把请求换成 200+HTML）」 | WAF 是**真实存在的活跃变量**，但**关掉后行为完全不变** ⇒ 不是当前卡点 | 半错：`report/21-手机侧执行记录.md:1500`（建议关）→ `report/21-…:1571`（关掉后无变化） | 已降级为"待排除项" |

---

## 附：报告间的残留冲突（未消化，读时要小心）

| 冲突点 | 甲说法 | 乙说法 | 建议 |
|---|---|---|---|
| `classes2.dex` 可否重编 | `work/ba/audit/ba-pitfalls.md:54`：E44 首次成功、之后同批全卡 | `report/01-现状与已试方向.md:182` 引 `ba-gateway-host.md:84`：✅ 正常启动、SDK 登录成功 | 保守按"不可复现，已放弃" |
| handler 文件数 | 66（`report/04-服务端就绪度.md:229` 引 `ba-protocol-full.md`；`report/01-现状与已试方向.md:112` 也是 66） | 65（`report/27-SDK登录协议调研.md:445` 引 `ba-protocol-shittim.md:51`） | 未解决，需要 `ls Handlers/*.cs \| wc -l` |
| `iFix` 代理是否存在 | 存在 `<>iFixBaseProxy_ValidateCertificate`（metadata `0x1522f2`） | `report/17-运行时hook方案评估.md:381`：在 so 里搜 `iFix` = 0 命中（但**方法名本来只在 metadata**，不能据此否定） | 存在，`class_for_each` 枚举会天然覆盖它 |
| 5100 端口用途 | 曾推断"Configuration page"（`report/04-…:120`） | 实测 = gateway 端口（`report/09-…:106`） | 以 09 为准 |
| 我们的 chain 用哪套 | `ca2/chain.crt`（`CN=BA Test Root CA`）是手机信任的 | `ca3/chainS.crt`（伪装 RapidSSL）；切回 ca3 会复现 46 条 alert 49 | 锁在 `ca2`，见 `/root/bapatch/README_CA_LOCK.txt`（`report/22-服务端取证记录.md:302`） |
