# DD4: 完整性校验 / 反作弊 证据清单

> 扫描范围：`report\` 全目录（`*.md` 全 90 份 + `_tmp\` 下的文本产物）。**只读**，未连手机、未连服务器、未执行任何网络操作。
> 行号一律是 read / grep 工具的行号，未做任何改写。标注 `report\` 前缀的为可直接复核的一手行；标注 "引" 的为报告内对我不可读文件（`work\ba\audit\*.md`、`ba-pitfalls.md` 等）的转引。
> 置信度口径：**确证** = 报告内有一手实测 / 字节级 / 定时观测记录；**推断** = 由已证事实推得但无端到端实测；**未知** = 报告内查不到证据；**冲突** = 报告内两处记载互相矛盾（并列标注）。

---

## 结论速览

1. **客户端绝对不是"干净 Unity 包"。** ACE 装在里面且在跑：`libtprt.so` 1,692,296 B 被 `libil2cpp.so` 与 `libunity.so` **双向 `DT_NEEDED`** 依赖（即每个游戏进程必加载它）；`AceApplication.attachBaseContext → libtprt.initialize()` 在启动链上；`:GP6Service/:GP7Service/:GP7Worker` 三个 exported 服务；`down.anticheatexpert.com/…/config2.xml` 在冷启动第 0.00 秒就发。**"没装 ACE"这个假设可以直接否掉。**
2. **但它的完整性校验是"定点"的，不是"整包签名"的。** 已知被钉死的对象只有 `libunity.so`（改 4 字节 → `SIGBUS status=7`，有 E42 原厂对照）与 `libtprt.so`；**`libil2cpp.so` 明确不在其列**，且 `assets/__tpinfo.*` 这 5 个自身完整性清单文件**删掉就整段跳过校验**——这是项目内所有改包能跑的总前提。
3. **"改 libil2cpp.so 能跑"不是推断，是确证，而且跑得比"能启动"远得多。** 设备现役那份 `base.apk` 内嵌的 `libil2cpp.so` 本身就不是原厂件（sha `6e2edf5a…`，非原厂 `5ac1cbe0…`，代码洞里带旧桩），而**就是这个包**在 11-14 05:22 冷启动后一路走到"取得昵称"（05:23:37）与"姓名发音"（05:38:49）界面。
4. **重打包做过、而且签名真的换过、而且装机后跑起来了。** E28→E44 十余版，`repack_e30…e42.py` 全族"解官方 APK → 换 so/资源 → zipalign → apksigner"，E30 记"已签名已安装"，E38"正常跑 45 s+"，E42"能进主程序"。设备上现役包内嵌打桩 so + 现场 logcat 有 `TapSDK: 包名、签名错误` 的 toast ⇒ **重签是既成事实，且没被 ACE 杀**。
5. **对"免 root 重打包"的判决：反作弊不是主要阻力，安装/签名经济性才是。** 证据面内**没有任何一次**"仅因签名变化 → SIGBUS/闪退"的观测；真正的失败全部来自改错了对象（libunity / libtprt / 加 .so / 改 NEEDED / 动 dex / 改包名）。剩下的硬成本是：签名变 ⇒ 必须卸载重装 ⇒ UID 变 ⇒ 11 GB 资源要 `chown -R <UID>:1078` ⇒ 丢 `/data/data` 登录态；外加 ACE 的"记账"会让失败一次之后的实验全部被 `SIGBUS` 污染。

---

## 1. 关键词扫描命中总表

> 命中量大，下表只收**有实质信息**的行；`class_declaration`/纯格式命中已剔。同一事实多处出现时收最硬的那一处，其余在括号里补。

### 1.1 `ACE` / 反作弊 / 反外挂 / 安全模块 / 安全 SDK

| 文件:行号 | 事实（一句话） | 置信度 |
|---|---|---|
| `report\01-现状与已试方向.md:30` | 客户端链条第一层就是"ACE 壳 `libtprt.so` (1,692,296 B)" | 确证 |
| `report\01-现状与已试方向.md:31` | 启动入口 `AceApplication.attachBaseContext` | 确证 |
| `report\01-现状与已试方向.md:33` | `native initialize(pkg, filesDir, nativeLibDir, sourceDir, splits)` —— **把 `sourceDir` 交给 native** | 确证 |
| `report\01-现状与已试方向.md:34` | 内部在 `__sem_timedwait` 等 `:GP6/:GP7` 应答（清 `/data/data` 会永久卡死） | 确证 |
| `report\01-现状与已试方向.md:35` | `:GP6Service / :GP7Service / :GP7Worker`（`exported=true`，action=类名，extra `"ioctl"`） | 确证 |
| `report\01-现状与已试方向.md:38` | 改 `libtprt` 任意字节 → `kill(SIGBUS)`；整库替换成假 so 可过启动 | 确证 |
| `report\01-现状与已试方向.md:59-64` | 与 ACE 并列的独立风控：数美 `com.ishumei.smantifraud`（4 个 Xposed 枚举方法，DEX 级真实调用）、`com.tencent.turingfd`（读 `TracerPid`）、`libthemis.so`(TapTap)、`libsigner.so`(Adjust) | 确证/部分未验证 |
| `report\02-注入链审计.md:115` | `libtprt` 是 ACE/TP 核心，导出 `JNI_OnLoad`/`g_tprt_pfn_array`/`g_tprt_ori_array`/`tp_syscall_imp` | 确证 |
| `report\02-注入链审计.md:118` | `:GP6/:GP7` 是独立进程，"一个进程里的 patch 管不到另一个进程的复核" | 确证 |
| `report\05-AzusaBA可复用资产.md:41` | 参照项目 AzusaBA 全源 `ACE\|tprt\|tpinfo\|Tencent\|xigncode` 命中 0，即它**根本没绕 ACE** | 确证 |
| `report\27-SDK登录协议调研.md:564` | 反编译 manifest 实测：`com.ace.gshell.GP6Service / GP7Service / GP7Worker`（腾讯 ACE 反作弊） | 确证 |
| `report\27-SDK登录协议调研.md:535` | `com.taptap.sdk.themis.lite.ThemisProvider`（TapTap 反作弊） | 确证 |
| `report\38-Frida部署清单.md:15` | "碧蓝档案国服带 ACE（AntiCheatExpert）+ 腾讯 ACE，对 Frida 有主动检测" | 确证 |
| `report\01-现状与已试方向.md:141` | ACE"记账"可通过删 4 个文件复位（`ace_shell_di.dat`/`shell_cache`/`ano_tmp`/`data/app`） | 确证（引 `ba-pitfalls.md:62-69`） |
| `report\04-服务端就绪度.md:418` | 同一件事的后果版："触发过一次异常改动后，后续任何版本都会 SIGBUS，直到删除…才复位" | 确证（引） |
| `report\02-注入链审计.md:240` | 同上，列为"ACE 判定持久化" | 确证（引） |
| `report\03-上游情报.md:474` | 上游 ACE 检测清单（TracerPid / 进程名 / maps / fd / 模拟器 / ADB / 注入痕迹 / **自身完整性 `assets/__tpinfo.tsc`、`__acinfo.tsc`** / 开关 `DetailSecurityCheck`、`__acignore.acc`） | 确证（外部原文） |
| `report\03-上游情报.md:475` | 上游把这叫"自身文件完整性"，与我方"删 `__tpinfo`"的做法互为印证 | 推断（映射） |
| `report\18-Frida与运行时绕过调研.md:54` | ACE 自保护面含"`.text` 完整性校验和、反调试、**self-kill watchdog**（校验失败直接杀进程）" | 确证（外部资料） |
| `report\18-Frida与运行时绕过调研.md:48` | "ACE（`libtprt.so` / anogs 系）的检测点"整表 | 确证（公开资料整理） |
| `report\95-真服抓包与对照方案.md:558` | "客户端侧 ACE（腾讯 ACE）主要做**进程 / 内存 / 模块 / 调试器**扫描…网络路径不在它的常规扫描范围" | 推断（原文标注为作者判断） |
| `report\14-运行期dump与证书补丁方案.md:118` | "ACE 有 `files/data/app` 解包目录" | 推断 |
| `report\21-手机侧执行记录.md:1101` | 现场读到 `/data/data/<pkg>/files/` 里有 **ACE `ano_tmp/*.dat`** —— ACE 运行期真的在写盘 | 确证（实测目录列表） |
| `report\101-官方真服抓包分析.md:60` | har 第 1 条：`down.anticheatexpert.com` → **反作弊配置 404** | 确证 |
| `report\99-baba_har取证.md:188` | 同上，两次 404（`config2.xml`），IP `2409:8c30:40:2d07::4` | 确证 |
| `report\100-新har取证-为何无登录.md:52` | 冷启动**最早一条**网络请求就是 19:40:18.242 的 `down.anticheatexpert.com/…/config2.xml` | 确证 |
| `report\22-服务端取证记录.md:123` | 服务端侧同样看到 `down.anticheatexpert.com desc=49 x1` | 确证 |
| `report\21-手机侧执行记录.md:828` | `down.anticheatexpert.com` 已能取到真证书（即 ACE 的配置通道在跑） | 确证 |
| `report\06-手机基线恢复.md:420` | `logcat -b crash` 4 条 `F/libc: FORTIFY: pthread_mutex_lock called on a destroyed mutex`，pid 非主进程，**疑似 ACE/pushcore 子进程退出噪音** | 推断 |
| `report\DEADENDS.md:71` | `debuggerd -b` 栈：`ActivityThread.handleBindApplication → TechApplication.attachBaseContext → AceApplication.attachBaseContextShell → libtprt.initialize() → __sem_timedwait`（永远等不到） | 确证（一手栈） |
| `report\DEADENDS.md:72` | ACE 的 `initialize()` 依赖 `files/data/app/…` 解包产物 —— 清内部数据会导致永久卡启动 | 确证 |
| `report\DEADENDS.md:53-56` | 假 `libtprt.so`（导出三符号）能过启动，但用户否决："假 ACE 会破坏 Unity 需要的返回"；理由是 `g_tprt_ori_array` 是原始 libc 函数表 | 确证 |
| `report\00-下一步总方案.md:116` | `libil2cpp.so` 的 `.dynsym` **导入** `g_tprt_ori_array`；该符号是 `libtprt.so` 的导出（`0x1a4b48`/`0x1a3210`） | 确证 |
| `report\00-下一步总方案.md:118` | 含义：ACE 在加载期把 libil2cpp 的部分 PLT 改成"进 libtprt 的 wrapper、再用 `ori_array` 回调" | 确证 |
| `report\78-SQLCipher密钥与表数据二次加密.md:276` | **`libil2cpp.so` 的 `DT_NEEDED` = `liblog, libm, libdl, libc, libstdc++, libtprt`** | 确证（ELF 实测） |
| `report\78-SQLCipher密钥与表数据二次加密.md:277` | **`libunity.so` 的 `DT_NEEDED` 末尾也是 `libtprt`** | 确证（ELF 实测） |
| `report\17-运行时hook方案评估.md:369-371` | `libtprt.so` 导出实测：`g_tprt_pfn_array`@`0x1a3210`（53 指针）、`g_tprt_ori_array`@`0x1a4b48`（20 指针）、`JNI_OnLoad`@`0x2641c`、`tp_syscall_imp`@`0x146be0` | 确证 |
| `report\17-运行时hook方案评估.md:140` | `libtprt.so` 导入 `dlopen/dlclose/dlsym/dladdr`（能反查 agent 属于哪个模块） | 确证（引） |
| `report\19-网关攻坚-当前状态.md:74` | `libil2cpp.so` 的 `.text` 中 **739/2825 页（26.2%）磁盘上不是可执行代码**，ACE 加载时还原 | 确证（字节级） |
| `report\57-既有补丁资产清点.md:305-306` | `libtprt_orig/final.so` 各 1,692,296 B，`final` 与 `orig` 逐字节相同（sha `47064882…`）= 明确回滚件 | 确证 |
| `report\INDEX.md:48` | `libtprt.so`（ACE 核心）改任意字节 → `kill(SIGBUS)` | 确证（引） |

### 1.2 签名 / 验签 / apksigner / 重签 / 重打包 / repack / 包名

| 文件:行号 | 事实 | 置信度 |
|---|---|---|
| `report\01-现状与已试方向.md:451` | "APK 版本链脚本 `repack_e30.py` … `repack_e42.py`、`repack*.py`、`repkg*.py`" —— **E30→E42 每版可复现** | 确证 |
| `report\01-现状与已试方向.md:494` | `/sdcard/Download/BA_E30.apk`（2,126,498,053 B，**已签名已安装**） | 确证 |
| `report\57-既有补丁资产清点.md:136` | 重打包脚本族统一流程："解官方 APK → 换 so/资源 → zipalign → apksigner"；输出 `BA_E28/E30/…/E42_unsigned.apk` | 确证 |
| `report\57-既有补丁资产清点.md:21` | **间接确证改包+重签**：`e0/e1/e2/e0b/a_signed.apk.idsig` 各 16,750,059 B；用 21 KB 的 `Probe13.apk`→5,611 B idsig 定标，反推对应 **~2.143 GB APK = 游戏本体** | 确证（定量） |
| `report\57-既有补丁资产清点.md:137` | idsig 内可见 DN 链含 `CN=BA`；`lsp\build13.sh:32-33` 用 `ba_private.keystore`（alias `ba`, pass `baserver`） | 确证（自签侧） |
| `report\57-既有补丁资产清点.md:140` | "改包+重签+装机**几乎确定发生过**（字节证据 + idsig 定量 + 脚本族），但**缺一手 install 日志**，故写'间接确证'" | 确证（结论句） |
| `report\57-既有补丁资产清点.md:138` | **缺失项**：工程内没有游戏包的 `pm install` 原文日志 | 未知 |
| `report\57-既有补丁资产清点.md:328` | `repack_e32/e32b/e34/e35/e40/e41/e42.py` 换资源（`res.apk` 的 `resources.arsc`+`res/`）；**E38/E42 是"能进主程序"的那两版**；E38 = 纯填充字节翻转（无注入，正常跑 45 s+） | 确证 |
| `report\57-既有补丁资产清点.md:325` | `repack.py`/`repack4..10.py`（装 LSPosed 模块进包）—— 早期迭代，**已废弃** | 确证 |
| `report\57-既有补丁资产清点.md:326` | `repack_game.py`（E28）：打 `libunity @0xA53A38` + 换 `libmain.so` + 加 `libdg.so` —— **已废弃** | 确证 |
| `report\57-既有补丁资产清点.md:327` | `repack_e30/e31.py`：libunity 证书绕过 +（e31）把 `SDKConfigSettings.json` 的 `sdk_url` 改成 `http://127.0.0.1:8080` —— 部分有效 | 确证 |
| `report\21-手机侧执行记录.md:862` | 现场 logcat/toast：**`TapSDK: 包名、签名错误。详见 ErrLog`** | 确证 |
| `report\21-手机侧执行记录.md:869` | "SNI 透传后 TapTap 真实服务端第一次真正执行包名/签名校验，**对重签过的包必然失败**——属应用/签名层，不是网络层" | 确证（+ 推断定性） |
| `report\21-手机侧执行记录.md:1325` | 截图 `s1.png` 02:07:14 黑色 toast「TapSDK: 包名、签名错误。详见 ErrLog」 | 确证 |
| `report\29-进度-网关未调用与判据纪律.md:81` | 同一条被登记为"**既知现象**，改包/重签的必然结果，不影响流程" | 确证 |
| `report\INDEX.md:67` | 同上，并记"全量 logcat `grep 签名\|包名\|ErrLog` = 0 行" | 确证 |
| `report\30-网关RSA公钥定位与替换.md:337` | `assets/` 是未解压 zip 条目、运行时由 AssetManager 读 ⇒ **改 `assets/` 里的文件必须重打包 APK 并重签名** | 确证（机制） |
| `report\30-网关RSA公钥定位与替换.md:340-343` | 路线 A（推荐）：`apktool d`/`7z` 解包 → 换文件 → `zipalign -p 4` → `apksigner sign`（v1+v2+v3） | 确证（方案） |
| `report\30-网关RSA公钥定位与替换.md:344` | **"卸载重装（不要覆盖安装，签名变了会失败）"** —— 签名变化的**真实后果是安装失败，不是反作弊** | 确证 |
| `report\52-客户端补丁方案-metadata绕过登录.md:541` | `extractNativeLibs=true` 但 `assets/` 仍是 zip 条目 ⇒ 必须**重打包 + 重签 + 卸载重装** | 确证 |
| `report\52-客户端补丁方案-metadata绕过登录.md:544` | "重打包 → 签名变 → 撞 ACE 的 sourceDir/签名完整性面（DEADENDS D-03/D-05 都死在这里）" | **推断**（未见独立实测；D-03/D-05 的真实死因见 §1.3） |
| `report\52-客户端补丁方案-metadata绕过登录.md:507` | 反向表述："如果客户端真从那里读，打补丁 = **一条 `cp`**，不需要重打包、不需要重签、不碰 ACE 的 APK 完整性面" | 推断 |
| `report\53-客户端补丁方案-运行时hook绕过登录.md:532` | "改成 `true` 要重打包重签，直接撞 ACE 的签名面（D-04~D-06 已证：dex 结构变化会让 App 卡启动界面）" | 部分确证（dex 一条确证；"签名面"推断） |
| `report\05-AzusaBA可复用资产.md:370` | 假设句："ACE 把 `sourceDir` / `splitSourceDirs` 交给 native 做完整性校验 → **签名/路径必然与原包不同 = 最现实风险点**" | **推断**（原文自标）；`report\01:336` 把它登记为"未做" |
| `report\01-现状与已试方向.md:336` | 未验证清单第 22 条：ACE `initialize()` 对 `sourceDir/splitSourceDirs` **具体算什么（签名？dex 校验？CRC？）** —— **状态：未做** | 未知 |
| `report\17-运行时hook方案评估.md:396` | 风险表 R6："签名重打包被 ACE 的 `sourceDir` 完整性面抓到 / 中 / 启动即杀 / 对策：删 `__tpinfo.*`；只做原地补丁" | 推断（风险，不是观测） |
| `report\20-AndroidCA注入深度调研.md:604` | 表内写"游戏有签名/完整性校验，**且 `libil2cpp` 有 ACE hash pin，你已经踩过 SIGBUS**" | **冲突/过时**：`libil2cpp` 的 SIGBUS 从未发生；晚出的 `report\30:322`、`report\18:4`、`report\38:301` 一致说 libil2cpp **无** hash pin |
| `report\DEADENDS.md:47-49` | D-05 改包名 → **`SIGBUS`**；"包名被 ACE 校验（拿 `sourceDir` 与包名做一致性判断）" | 确证（现象）/ 推断（机理） |
| `report\01-现状与已试方向.md:183` | 同上，"改包名可行 → 包名被校验，实测 SIGBUS" | 确证 |
| `report\DEADENDS.md:40-41` | D-04：新增 `classes3.dex`（660 B 空类）→ **卡 Android 启动界面**；"不是 ACE，是启动链本身不接受 dex 结构变化" | 确证 |
| `report\01-现状与已试方向.md:180-181` | 新增 `classes3.dex`（E39/E40/E41）→ 卡启动界面；重编 `classes.dex`（E43）→ 卡启动界面 | 确证 |
| `report\01-现状与已试方向.md:182` | 重编 `classes2.dex`（E44）**两处记载冲突**：`ba-pitfalls.md:54` 记首次成功、之后同批全卡；`ba-gateway-host.md:84` 记"正常启动、SDK 登录成功" | **冲突** |
| `report\DEADENDS.md:32` | D-03 机理："ACE 禁止加载布局变化，`sourceDir`/`splitSourceDirs` 是它的完整性面" | 推断 |
| `report\01-现状与已试方向.md:250` | `GET_SIGNATURES` 常量 0 命中，**但数美与 nirvana 都用 `getPackageInfo(pkg,64).signatures` 现算 SHA1** | 确证 |
| `report\01-现状与已试方向.md:522` | 反作弊口径："客户端层 ✅ 基本已绕过；native/环境层 ❌ 未绕过，三条暴露面仍在（`libNeko.so` maps / **APK 签名与路径** / 环境指纹）" | 确证（引原文结论句） |
| `report\05-AzusaBA可复用资产.md:342` | LSPatch 内嵌模块 → 模块自签名校验（`EXPECTED_SHA256`）直接拒绝注入 | 确证 |
| `report\INDEX.md:263` | 同上（A-65 行） | 确证 |
| `report\28-Shittim网关协议源码核对.md:21/463` | **服务端** `Account_CheckYostar` **不验签、不校验 token、账号不存在自动建号**，`ResultState=1` | 确证（源码） |
| `report\29-进度-网关未调用与判据纪律.md:58` | 同上，"完全不验签、不回调 TapTap，直接按 publisherId 查/建账号" | 确证 |
| `report\43-Queuing接管实施规格.md:153` | `SignedKey` 用 SHA1-PKCS1 签（`GatewaySessionCrypto.cs:240`），**客户端验签依赖 metadata 已换成我们的公钥** | 推断 |
| `report\17-运行时hook方案评估.md:351` | 签名前确认 ≥2.1 GB 空闲，否则 `apksigner` 会半截输出 | 确证（引） |
| `report\DEADENDS.md:344` | D-40：本 APK **根本没有** `networkSecurityConfig` 属性；`res/xml` 只有 `filepaths/http/sdk_file_provider_paths/standalone_badge*/tapupdate_file_provider/unitywebview_file_provider_paths` | 确证 |
| `report\06-手机基线恢复.md:628` | 同上（原始判定出处） | 确证 |

### 1.3 完整性 / integrity / 校验和 / hash / checksum / digest / md5 / crc

| 文件:行号 | 事实 | 置信度 |
|---|---|---|
| `report\01-现状与已试方向.md:122` | **删 `assets/__tpinfo.{tsc,tsc.sig,tsd,tsd.sig,tp}` → 完整性校验整段跳过；备注"所有改包能跑的前提"** | 确证（引 `ba-pitfalls.md:9-11`） |
| `report\01-现状与已试方向.md:125` | 改 `assets/*.json`（`sdk_url`）时**同步删 `__tpinfo` 后可用** | 确证 |
| `report\01-现状与已试方向.md:129` | "`libil2cpp.so` 无 hash/CRC pin（静态弱否定）… ACE 校验焦点是装载体" | 确证（引） |
| `report\01-现状与已试方向.md:73` | "[已验证] libil2cpp 无 hash pin，可改（E38 填充字节翻转 / 代码洞注入 / DT_INIT 改址 / 原位替换 so）" | 确证 |
| `report\19-网关攻坚-当前状态.md:47` | "改 `libunity`（4 字节证书补丁）→ ❌ **有 ACE hash pin，SIGBUS**" | 确证 |
| `report\18-Frida与运行时绕过调研.md:4` | 一句话总结："`libunity.so` 有 ACE 磁盘哈希钉死（改 4 字节即 SIGBUS），`libil2cpp.so` 没有" | 确证 |
| `report\30-网关RSA公钥定位与替换.md:322` | "已证实：ACE 对 **`libunity.so`** 做磁盘哈希钉死（改 4 字节 → SIGBUS）；对 **`libil2cpp.so`** 未做" | 确证 |
| `report\30-网关RSA公钥定位与替换.md:323` | "**`global-metadata.dat` 是否被哈希、被完整性校验：今晚没有证据**" | 未知 |
| `report\30-网关RSA公钥定位与替换.md:324` | "我们的改动只有 337 字节，且**文件大小完全不变**… 但如果 ACE 对整文件做 CRC/SHA，仍会被抓" | 推断 |
| `report\28-Shittim网关协议源码核对.md:842` | "**ACE 是否会因为 metadata 被改而杀进程：未知**… metadata 属资源文件，不在 `.so` 哈希范围内 ——`[推断]` 大概率安全，但必须实测" | 未知/推断 |
| `report\38-Frida部署清单.md:301` | "ACE 只钉 `libunity.so` 和 `global-metadata.dat`" | **冲突**：与 `report\30:323`（无证据）、`report\57:20/125`（metadata 从未上机）矛盾；本条无实测支撑 |
| `report\DEADENDS.md:16` | D-01 机理："ACE 对 `libunity.so` 做**磁盘哈希钉死**，任何一个字节变化都在加载期被抓" | 确证（现象）/ 推断（机理） |
| `report\DEADENDS.md:25` | D-02 教训："ACE 的校验对象是**整文件哈希**"（由 libairisgcore 整库替换 SIGBUS 得出） | 推断 |
| `report\02-注入链审计.md:117` | "脚本改的是 ACE 自己的校验点，但 **ACE 的 hash pin 不在这两个点上** —— 改校验点不解决'文件被改'这个事实" | 确证（逻辑） |
| `report\02-注入链审计.md:410` | "libil2cpp 可改，**E38 已验证不受 ACE hash pin 限制**" | 确证 |
| `report\02-注入链审计.md:357` | 判据建议："是否被 ACE 的完整性检查 abort（抓 logcat 里 `linker`/`DEBUG` 行即可分辨）" —— 该判定**未执行** | 未知 |
| `report\18-Frida与运行时绕过调研.md:210` | "本项目已实测 libunity 4 字节磁盘补丁 → SIGBUS，说明磁盘校验肯定有；**内存校验未知**" | 确证/未知 |
| `report\18-Frida与运行时绕过调研.md:234` | 未决项："**ACE 是否有内存 CRC（而不只是磁盘哈希）**——只证明了磁盘侧，内存侧未知" | 未知 |
| `report\11-客户端静态逆向-网关与证书.md:243` | "运行时 text patch… **ACE 若校验内存则命中**" | 推断 |
| `report\91-hook写权限bug修复.md:780` | "匿名 `rw-` 页不属于任何 .so，通常不会出现在段保护扫描里；但**如果 ACE 枚举 `/proc/self/maps` 的匿名可写页并做完整性检查**，可能起疑" | 推断 |
| `report\13-总账-2026-11-14凌晨.md:77` | F7 已证伪项："libunity 4 字节补丁 @`0xA53A38` → ACE 校验 → SIGBUS status=7；**E42 用原厂 libunity 才正常**" | 确证（对照实验） |
| `report\19-网关攻坚-当前状态.md:74` | `.text` **739/2825 页（26.2%）在磁盘上不是可执行代码**（ACE 加载时还原）—— 这就是"完整性校验"在磁盘上的物理形态 | 确证 |
| `report\34-国服packet二进制结构分析.md:343` | 同上，"ACE 加密了约 26.2% 的 `.text` 页，但 73.8% 是明文" | 确证 |
| `report\32-国服网关信封混淆分析.md:278` | 同上（引 `report\11`） | 确证 |
| `report\16-pinning外部经验.md:42-44` | 外部经验："真正的风险是'**反作弊检测到 MITM**'，不是'证书校验过不去'" | 确证（外部） |
| `report\100-新har取证-为何无登录.md:225` | `catalog_Android.hash` 返回 32 B MD5，与本地缓存一致 ⇒ 客户端判定"资源无更新"（**这是游戏自己的资源校验，不是反作弊**） | 确证 |
| `report\54-客户端补丁方案-本地配置绕过.md:69` | 该报告的判据列名就叫"完整性证据"，用于本地配置文件的 XOR/明文判定 | 确证 |
| `report\32-国服网关信封混淆分析.md:386` | "实验 3：请求体完整性检查"（协议层，与 APK 完整性无关） | 确证 |
| `report\78-SQLCipher密钥与表数据二次加密.md:367` | 风险："客户端可能校验库的完整性/版本号（未验证）" | 未知 |
| `report\_tmp\shittim_metadata_patch_研究.md:609` | 对照：Shittim 的 metadata patch 服务"校验 = fail-safe 不是 verify；**没有全文件 checksum、没有写后重读校验**" | 确证（源码） |

### 1.4 检测 / 检测到 / 异常 / 封号 / ban / 踢下线

| 文件:行号 | 事实 | 置信度 |
|---|---|---|
| `report\38-Frida部署清单.md:16` | "检测命中通常表现为：**闪退 / 弹'检测到异常环境' / 静默掉线**，一般不会封号（私服单机账号），但会打断实验" | 推断 |
| `report\38-Frida部署清单.md:361`/`:363` | ACE 检测风险表（`Xposed`/`Magisk` 痕迹：中；`/data/local/tmp` 下可执行文件：中） | 推断 |
| `report\DEADENDS.md:259` | D-30 Frida：`exit-info reason=2 status=7`（**SIGBUS，ACE 主动杀**）；"团队确实 attach 成功过，但仓库里没有任何一份日志证明进程在 ACE 全功能开启下活过 30 秒" | 确证 |
| `report\DEADENDS.md:574` | 判据铁律："**7=SIGBUS(ACE)，9=SIGKILL(系统)**"（`status=9` 曾被误判为 ACE） | 确证 |
| `report\01-现状与已试方向.md:144` | "`status=9` 判定为系统回收（非 ACE）；ACE 是 SIGBUS `status=7`" | 确证 |
| `report\01-现状与已试方向.md:190` | 证伪项："`status=9` 是 ACE 杀的 → 否" | 确证 |
| `report\18-Frida与运行时绕过调研.md:63` | "Frida 在这台机器上大概率被 ACE 杀掉…ACE 是'堵漏斗不堵点'的架构" | 推断 |
| `report\53-客户端补丁方案-运行时hook绕过登录.md:20` | ACE 行为/结构检测四条：maps 里的 agent 映射、线程名 `gum-js-loop`/`pool-frida`、端口 27042、`TracerPid != 0`；dex 里 `frida/27042/ptrace` **明文 0 命中** ⇒ 它靠**行为/结构**不靠字符串 | 确证 |
| `report\01-现状与已试方向.md:243` | "libtprt 里有明文检测串（magisk/frida/Xposed/`/proc/self/maps`/TracerPid）→ **全部 0 命中**；因 rodata 加密/VM（可打印率 0.286）。'0 命中' ≠ '无检测'" | 确证 |
| `report\01-现状与已试方向.md:251` | "只有 Java 层有检测 → 否。native 侧也有：数美 `:528` `new FileReader("/proc/self/maps")` 只保留含 `/data/app/` 的行；libtprt 有 `dladdr`" | 确证 |
| `report\95-真服抓包与对照方案.md:552` | 专章："真服有 ACE 会不会检测到？—— 诚实说：**不知道**" | 未知 |
| `report\95-真服抓包与对照方案.md:530` | 抓包后处置："改一次密码/踢下线，让抓到的 token 失效"（**这是我们自己踢，不是 ACE 踢**） | 确证 |
| `report\56-外部情报-国服私服与客户端绕过.md:1133` | PC 端对照："半还原状态会被官服拒绝并报 **'Abnormal client'**" | 确证（外部） |
| `report\06-手机基线恢复.md:356` | 定性："弹'认证服务器拒绝了请求'…**这是 token 层面的拒绝，与客户端完整性无关**" | 确证 |
| `report\03-上游情报.md:84` | 上游症状对照："写错 offset ⇒ 客户端卡 **'Unpacking game resources'**"（PC/国际服） | 确证（外部） |
| `report\83-服务端当前状态快照.md:143` | （无关命中：`base53` token 算法） | — |

### 1.5 `/data/app` / `/data/local/tmp` / `/system/lib` / 安装路径 / apk 路径

| 文件:行号 | 事实 | 置信度 |
|---|---|---|
| `report\63-已证实事实冻结版.md:98` | 现役 so 绝对路径：`/data/app/~~VR_C2zki6QoGBL2wJi1Bww==/com.RoamingStar.BlueArchive-cdcWsUUfK6_dSmh9roP1sg==/lib/arm64/libil2cpp.so` | 确证（`pm path`+`ls`） |
| `report\63-已证实事实冻结版.md:99` | 其 sha256 = `6e2edf5a…`（**= APK 内嵌件，非纯原厂**） | 确证 |
| `report\63-已证实事实冻结版.md:101` | 该 `.so` 是**磁盘上的独立文件**（不是从 APK 内 mmap）⇒ 静态替换路线未被一票否决 | 确证 |
| `report\63-已证实事实冻结版.md:102` | 该文件**从未被修改**（全程 sha 保持 `6e2edf5a…`） | 确证（观察窗内） |
| `report\06-手机基线恢复.md:28` | `/proc/<pid>/maps` 显示 libil2cpp 全部映射自 `/data/app/…/lib/arm64/libil2cpp.so` | 确证 |
| `report\06-手机基线恢复.md:124` | "libil2cpp 从 `/data/app/.../lib/arm64/` 直接 mmap，不是从 `base.apk` 的 zip 条目读 … `extractNativeLibs=true` 这条路是通的" | 确证 |
| `report\07-dlopen报错考证.md:258` | 机制："`extractNativeLibs=true` 时 `installd` 在安装阶段就把所有 `.so` 从 APK 解压落盘到 `/data/app/~~<hash>/<pkg>-<hash>/lib/arm64/`，APK 内条目是 `Stored` 还是 `Defl:N` 无所谓" | 确证 |
| `report\07-dlopen报错考证.md:406` | 单列方案 B：`pm install -r <base.apk>` 强制重新解压整个 `lib/arm64/`；风险："**签名不一致 → `INSTALL_FAILED_UPDATE_INCOMPATIBLE`**" | 确证（机制） |
| `report\02-注入链审计.md:261` | 原位覆盖命令：`su -c 'cp /data/local/tmp/libil2cpp_patched.bin /data/app/~~*/com.RoamingStar.BlueArchive-*/lib/arm64/libil2cpp.so'` | 确证（方案） |
| `report\58-代码洞钩子-观测登录响应.md:327` | 手机侧替换：`su -c 'cp /data/local/tmp/il2cpp_hook.so $LIB/.new_libil2cpp.so'` → 原子替换 | 确证（方案） |
| `report\91-hook写权限bug修复.md:674-675` | `adb push libil2cpp_hook_v2.bin /data/local/tmp/libil2cpp.so` + `su -c "cat /data/local/tmp/libil2cpp.so > $LIB_PATH"` | 确证（方案） |
| `report\93-v3修缺基址与偏移审计.md:506-507` | 同上（v3）：`adb push` → `su -c "cat … > $LIB_PATH"` | 确证（方案） |
| `report\57-既有补丁资产清点.md:35` | "**有。用的是 root `cp .new → restorecon → mv -f`（等效原子替换），不是 adb push**" | 确证 |
| `report\57-既有补丁资产清点.md:15` | 一手证据链：sha256 一致 → 原子替换进 `/data/app/…/lib/arm64/libil2cpp.so` → 启动等 60 s → `probe.log` 只有 6 字节 `START`，进程不存在 → 01:31 回滚并重启成功（pid 32506） | 确证 |
| `report\63-已证实事实冻结版.md:92` | 补丁文件"**已传到手机**并校验一致（反向 TCP，30.2 s / 8.55 MB/s），但**从未替换进系统**" | 确证 |
| `report\DEADENDS.md:553-559` | D-63 用 `cat > dst` 覆盖 `.so` → 被 `O_TRUNC` 截成 **0 字节** → `dlopen: 0 >= 0` → `JNI FatalError` → **0.3 秒一次重启循环** | 确证 |
| `report\08-手机接管与真因.md:212` | 同上事故的现场记录："手机侧 libil2cpp.so 是 0 字节（我在被中断的命令里用 cat > dst 留下的）" | 确证 |
| `report\08-手机接管与真因.md:100-104` | 时间线：18:38:51 安装（base.apk 2,126,786,978 B）→ 19:47 so 被原位替换成 g20 探针 → 19:57 起自杀循环 → 23:xx 归档时 `bainj.txt` 已有 **5976 B 的 `IBDIBD…`**（**更早 E63 时期能启动时留下的**） | 确证 |
| `report\14-运行期dump与证书补丁方案.md:416-417` | 替换目标 / 备份：`/data/app/~~*/…/lib/arm64/libil2cpp.so` ← `/data/local/tmp/libil2cpp.orig.so` | 确证（方案） |
| `report\53-客户端补丁方案-运行时hook绕过登录.md:96` | 前提 P2：`extractNativeLibs=true` ⇒ `/data/app/*/*BlueArchive*/lib/arm64/libil2cpp.so` 存在 | 确证 |
| `report\53-客户端补丁方案-运行时hook绕过登录.md:324` | 该路径的代价："`cp` 覆盖 → 改坏 owner / SELinux label；App 更新后失效；**无法自动回滚**" | 确证 |
| `report\38-Frida部署清单.md:58` | "为什么放 `/data/local/tmp`：这是 Android 唯一稳定可执行的公共目录，且 **ACE 对它的扫描优先级低于 `/data/adb/` 和 `/system`**" | 推断 |
| `report\DEADENDS.md:581` | 卸载重装后 UID 变（本机 10574→10575），`mv` 回来的 11 GB 属主还是旧 UID → `Error / Not enough storage space` | 确证 |

### 1.6 `libil2cpp` / `metadata` / `global-metadata` / `il2cpp`

| 文件:行号 | 事实 | 置信度 |
|---|---|---|
| `report\63-已证实事实冻结版.md:58` | `libil2cpp.so` = **270,927,056 B**（`0x102604D0`），合法 ELF64，14 个 program header | 确证 |
| `report\63-已证实事实冻结版.md:61` | 代码洞 `0xF2C2410` 起 3056 B 全零，位于 RX 段尾部 | 确证 |
| `report\02-注入链审计.md:51` | 基线可信：`libil2cpp.bin` sha 前 32 位 `5ac1cbe0…` 与 **APK 原包** `audit/ba-work/x/lib/arm64-v8a/libil2cpp.so` **完全相同** | 确证 |
| `report\01-现状与已试方向.md:503` | `audit/ba-apk/base.apk` 大小 **2,126,400,085 B** | 确证 |
| `report\57-既有补丁资产清点.md:135` | 设备 `base.apk` = **2,126,786,978 B**，mtime 2026-11-13 18:38 | 确证 |
| `report\08-手机接管与真因.md:132` | "**base.apk 里自带的 libil2cpp 也是打过桩的版本**（cave_head 非零），说明当前装的这份 APK 不是纯官包，而是某次实验的改包。它的 sha 既不等于原厂也不等于 g20，是第三份" | 确证（字节级） |
| `report\57-既有补丁资产清点.md:19` | 同上："手机上装的 `libil2cpp.so` 不是原厂。当前位是 `6e2edf5a…`（'APK 内嵌件'），**洞里带一份更早的旧桩**（cave_head `f353b4a9`，`0xf2c2540=620080d2`）" | 确证 |
| `report\06-手机基线恢复.md:71` | `/sdcard/Android/data/<pkg>`：**11 G 仍在**（AssetBundles 6.5G + TableBundles 435M + MediaPatch 4.0G）。**没有重装，UID 仍是 10576** | 确证 |
| `report\63-已证实事实冻结版.md:25` | A1.3：客户端**从标题画面推进到「取昵称」界面**，界面原文「请告知您的姓名。」/「※名字最多可以输入10个字。」/「确认」 | 确证（截图 md5 + 用户确认） |
| `report\84-手机侧观察时间线.md:35` | 昵称界面首次出现 **05:23:37** | 确证 |
| `report\84-手机侧观察时间线.md:36` | 发音界面「您的姓名如何发音？」首次出现 **05:38:49** | 确证 |
| `report\84-手机侧观察时间线.md:64-67` | 05:22:13 冷启动（PID 9804）→ 05:23:04 标题页 → 05:23:37 昵称界面 | 确证 |
| `report\02-注入链审计.md:266` | 钩子跑起来的判定：`/data/data/<pkg>/files/bainj.txt` 出现 `I`→`B`→`D` | 确证 |
| `report\08-手机接管与真因.md:104` | `bainj.txt` **5976 B 的 `IBDIBD…`** = 注入桩反复执行留下的实证（E63 时期） | 确证 |
| `report\01-现状与已试方向.md:489` | `/data/data/<pkg>/files/bainj.txt` 是注入打点文件 | 确证 |
| `report\30-网关RSA公钥定位与替换.md:386` | 未验证项："ACE 是否校验 `global-metadata.dat` —— **未知，需实测**" | 未知 |
| `report\57-既有补丁资产清点.md:125` | "**手机上的 `global-metadata.dat` 仍是原厂 `2352cb57`**"（公钥替换产物从未上机） | 确证 |
| `report\57-既有补丁资产清点.md:123` | "全项目 push 记录：**无**（检索 `global-metadata` 只命中本地扫描/分析文档，无设备写入）" | 未知（=无记录） |
| `report\78-SQLCipher密钥与表数据二次加密.md:276-277` | `libil2cpp`/`libunity` 的 `DT_NEEDED` 都含 `libtprt` | 确证 |
| `report\63-已证实事实冻结版.md:65` | `DT_RELA=0x1A118`、`DT_RELASZ=0x22F2570`；匹配到 **151,085** 条 `R_AARCH64_RELATIVE` | 确证 |
| `report\63-已证实事实冻结版.md:73-80` | 关键登录方法首 16 字节：`HandleAccountAuthResponseMessage` / `OnLoginFinish` / `ErrorAccountAuth` / `SkipAccountCallname` / `OnLoginFail` / `co_SyncShopListTutorialGacha` / `.ctor` **全是密文**（非 ARM64）；只有 `AccountAuthStart`/`StartRequestRelayPackets`/`IsLoginFinished`/`co_RelayPacketsProcess` 4 个明文 | 确证 |
| `report\90-项目总纲-可交接版.md:59` | 同上结论句："关键 handler 本体在 ACE 编码页" | 确证 |
| `report\24-state接口schema反推.md:395` | "C# 字符串字面量存放在 `global-metadata.dat` 的 `stringLiteralData` 区，不在 `libil2cpp.so` 里…`.text` 被 ACE 加密这件事不影响本任务" | 确证 |
| `report\38-Frida部署清单.md:190` | `libil2cpp` 的 `.dynsym` **`st_name` 被清零**（导出名不可按名解析）⇒ `frida-il2cpp-bridge` 必抛 `Unable to find export` | 确证 |
| `report\DEADENDS.md:267-268` | 同上，并明说"**不是 ACE 的问题，是符号表问题**" | 确证 |
| `report\05-AzusaBA可复用资产.md:229` | AzusaBA 产物里"没有任何 `libtprt` 加载检测、`__tpinfo` 完整性校验绕过、签名伪造、`/proc/self/maps` 清理代码" | 确证 |

### 1.7 明确"未找到相关记录"的项（穷尽扫描后的空集）

| 项 | 结论 |
|---|---|
| `libace*.so` / `libtersafe*.so` 命名的 .so | **未找到相关记录**。全 `report\` 无任何 `libace`/`libtersafe` 字样（`ACE` 一词全部落在 `libtprt.so`/`com.ace.gshell`/`anticheatexpert` 上）。这与"腾讯 ACE 新版的运行时库就叫 `libtprt.so`（TenProtect）"一致，**不是没有 ACE**。 |
| logcat 里 ACE 自己的 tag（如 `gshell`/`GP6`/`AceApp`）的原文行 | **未找到相关记录**。所有 logcat 原文里与 ACE 有关的只有：`down.anticheatexpert.com` 的 404（har，非 logcat）、`F/libc FORTIFY…`（疑似子进程噪音）、`files/ano_tmp/*.dat`（目录列表）。⇒ "有没有 ACE 日志"这一问的答案是：**没有一手 logcat 行**，ACE 的存在是靠"文件 + manifest + 依赖 + 启动栈 + 网络请求"五条独立证据钉的。 |
| 官方 APK 的签名指纹 / 证书 DN / `apksigner verify` 输出 | **未找到相关记录**。报告里只有**我方**自签材料（`CN=BA`、`ba_private.keystore` alias `ba`）。 |
| `apk` 的获取途径（商店/官网/从手机抽） | **未找到相关记录**。只能证明"曾经拥有过完整官方包"（`audit\ba-apk\base.apk` 2,126,400,085 B + 其内 `libil2cpp.so` = 原厂 `5ac1cbe0`）。 |
| "不删 `__tpinfo` 只改签名"的对照实验 | **未找到相关记录**。所有 E 系列包都删了 `__tpinfo`，**因此无法区分**"ACE 不校验签名"与"校验被 `__tpinfo` 删除整段跳过"。 |
| `INSTALL_FAILED_*` 的原文输出 | **未找到相关记录**。只在方案里预判签名不一致会 `INSTALL_FAILED_UPDATE_INCOMPATIBLE`（`report\07:406`）。 |
| 游戏包的 `pm install` 成功原文 | **未找到相关记录**（`report\57:138`、`:384` 自己承认）。 |
| ACE 内存 CRC（非磁盘）的任何实测 | **未找到相关记录**（`report\18:234`、`report\11:243` 皆标"未知"）。 |

---

## 2. 五个关键问题的答案

### Q1 — 项目改了 `libil2cpp.so` 之后，客户端能不能正常跑起来？

**答：能，而且不是"勉强能启动"，是"一路跑到取昵称 / 发音界面"。** 分五条独立证据，按硬度排序：

| # | 证据 | 出处 | 置信度 |
|---|---|---|---|
| **A（最强）** | **设备现役 `base.apk` 内嵌的 `libil2cpp.so` 本身就是改过的**（sha `6e2edf5a…` ≠ 原厂 `5ac1cbe0…`，代码洞里有旧桩 `cave_head f353b4a9`），**而就是这个包**在 11-14 05:22:13 冷启动后 05:23:37 到昵称界面、05:38:49 到发音界面 | `report\08-手机接管与真因.md:132`、`report\57-既有补丁资产清点.md:19`、`report\63-已证实事实冻结版.md:99`、`report\84-手机侧观察时间线.md:35-36`、`:64-67` | **确证**（唯一缺口：05:22 那一分钟没有独立的 sha 快照；但 01:31 回滚 → 05:4x 观测全程 sha 未变，中间无替换记录） |
| **B** | 端到端跑通协议：05:23:05 客户端发出 `POST /api/account/auth`（`ua=BestHTTP/2 v2.4.0`，`clen=1138`），我方回 `200`，随后界面推进 | `report\63-已证实事实冻结版.md:23-25` | 确证 |
| **C** | 注入桩**反复执行过**：`/data/data/<pkg>/files/bainj.txt` 累积 **5976 B 的 `IBDIBD…`**（每次启动追加 `IBD`），是 E63 时期留下的 | `report\08-手机接管与真因.md:104`、`report\02-注入链审计.md:266` | 确证 |
| **D** | 四种改法各自独立验过：填充字节翻转（E38，**APK 版本链内**，正常跑 45 s+）／代码洞 + PLT（E63，`alive=24049`）／`DT_INIT` 改址（日志 `IN/BA/DON`，进程存活）／**root 原位替换**（启动正常、`DT_INIT` 钩子照跑） | `report\01-现状与已试方向.md:128/130/133/134`、`report\02-注入链审计.md:234-236`、`report\10-网关重定向-已试清单与有效缺口.md:59/64`、`report\14-运行期dump与证书补丁方案.md:349` | 确证（D 的前两条是 APK 路径，另两条是 root 路径） |
| **E** | 反面对照很有说服力：**同一批实验里，改 `libunity.so` 4 字节就 SIGBUS、整库替换 `libairisgcore.so` 也 SIGBUS、加 `.so` 无日志闪退、改包名 SIGBUS** —— 说明这套环境**有能力**在加载期杀掉改动，只是**没有对 libil2cpp 下手** | `report\01-现状与已试方向.md:178/179/183/184`、`report\13-总账-2026-11-14凌晨.md:77` | 确证 |

**因此"没有严格的 APK 完整性校验"这个推论要精确化，见 §4。** 一句话版本：**不存在"整包签名/整包哈希"级别的校验；存在的是"按文件、按对象的定点校验"，而 `libil2cpp.so` 不在点名名单里。**

### Q2 — 有没有任何 ACE / 反作弊 相关的观测？

**答：有，而且是从"文件 → 清单 → 依赖 → 启动栈 → 运行期写盘 → 网络回连"六层各自独立钉死的。** 详见 §3。要点：

- **进程里的 ACE .so**：不是靠 `maps` 抓到的，而是靠 **`DT_NEEDED` 结构性证明**——`libil2cpp.so` 与 `libunity.so` 都 `NEEDED libtprt`（`report\78-SQLCipher密钥与表数据二次加密.md:276-277`），所以游戏进程**一定**映射了 `libtprt.so`（1,692,296 B，`report\01-现状与已试方向.md:30`）。
- **启动栈**：`AceApplication.attachBaseContext → attachBaseContextShell() → libtprt.initialize() → __sem_timedwait`（`report\DEADENDS.md:71`）。
- **清单**：`com.ace.gshell.GP6Service / GP7Service / GP7Worker`（`report\27-SDK登录协议调研.md:564`）+ `:GP6/:GP7` 服务（`report\01:35`）。
- **运行期写盘**：`/data/data/<pkg>/files/` 里实测有 **ACE `ano_tmp/*.dat`**（`report\21-手机侧执行记录.md:1101`）。
- **网络**：冷启动第 0.00 秒就拉 `down.anticheatexpert.com/…/com.RoamingStar.BlueArchive/config2.xml`，**404**（`report\100-新har取证-为何无登录.md:52`、`report\101-官方真服抓包分析.md:60`、`report\99-baba_har取证.md:188`）。
- **logcat 里 ACE 自己的日志**：**未找到相关记录**（这是本次扫描的真空集，见 §1.7）。
- **"安全组件初始化"记录**：有，就是 `libtprt.initialize()` 的 `__sem_timedwait`（`report\DEADENDS.md:71-72`、`report\01:34`）。

### Q3 — 客户端的 APK 是从哪来的？

**答：获取途径"未找到相关记录"；能确证的是"曾拥有一份完整的官方包，并且设备上装的是另一份改过的包"。**

| 项 | 值 | 出处 | 置信度 |
|---|---|---|---|
| 包名 | `com.RoamingStar.BlueArchive`（另有 `.bilibili` 变体在参照项目的目标名单里，**本设备装的不是它**） | `report\08-手机接管与真因.md:4`、`report\05-AzusaBA可复用资产.md:321` | 确证 |
| 版本 | `3.0.2` / `versionCode 73` / 标题页 `Ver : 3.0.2_73` | `report\04-服务端就绪度.md:35`、`report\27-SDK登录协议调研.md:397`、`report\84-手机侧观察时间线.md:33` | 确证 |
| 官方原包（归档） | `audit\ba-apk\base.apk` = **2,126,400,085 B**；其内 `libil2cpp.so` = 原厂 `5ac1cbe0…` | `report\01-现状与已试方向.md:503`、`report\02-注入链审计.md:51` | 确证 |
| 设备在装包 | `base.apk` = **2,126,786,978 B**，mtime `2026-11-13 18:38`，安装时刻 `18:38:51`；其内 `libil2cpp.so` = `6e2edf5a…`（**带桩**，≠ 原厂） | `report\57-既有补丁资产清点.md:135`、`report\08-手机接管与真因.md:100`、`:132` | 确证 |
| 官方签名信息 | **未找到相关记录**（无 `apksigner verify` 输出、无官方证书 DN/指纹） | — | 未知 |
| 我方签名材料 | `ba_private.keystore`（alias `ba`，pass `baserver`）；idsig 内 DN 链含 `CN=BA` | `report\57-既有补丁资产清点.md:137` | 确证 |
| 签名是否真的换过 | **换过**：现场 toast `TapSDK: 包名、签名错误。详见 ErrLog`；文档明说"对重签过的包必然失败" | `report\21-手机侧执行记录.md:862`、`:869`、`:1325`、`report\29-进度-网关未调用与判据纪律.md:81` | 确证 |

> 口径提醒：设备在装包与归档官方包**大小差 386,893 B**、内嵌 so 的 sha 不同 ⇒ **设备上那份是改包**，不是原厂。这一点由 `report\08:132` 的字节级判定 + `report\57:133` 复述共同确认。

### Q4 — 有没有尝试过重打包？结果如何？

**答：有，至少 15 个编号版本（E28–E44），全流程到"签名 + 装机 + 冷启动观测"都跑过。失败现象按"改了什么"严格区分如下：**

| 改的对象 | 版本/实验 | 结果（原文） | 出处 | 置信度 |
|---|---|---|---|---|
| **`libunity.so` 4 字节（`@0xA53A38`）** | E32/E34/E36 | **启动即 `SIGBUS`，`ApplicationExitInfo reason=2 status=7`，无 tombstone**；对照组 **E42 换回原厂 libunity 立刻正常** | `report\DEADENDS.md:12-18`、`report\01:178`、`report\13:77` | 确证 |
| **整库替换 `libairisgcore.so`** | E35 | `SIGBUS (reason=2 status=7)` | `report\DEADENDS.md:20-26`、`report\01:179`、`report\02:238` | 确证 |
| **往 APK 加新 `.so` / 改 `libmain.so` 的 `DT_NEEDED`** | — | **无日志闪退**（"ACE 直接杀，连 tombstone 都没有"） | `report\DEADENDS.md:28-34`、`report\01:184`、`report\02:133` | 确证 |
| **新增 `classes3.dex`（660 B 空类）** | E39/E40/E41 | **卡 Android 启动界面**（Unity 未加载）；"与 ACE 的 8~10 s 后杀进程无关" | `report\DEADENDS.md:36-42`、`report\01:180` | 确证 |
| **重编 `classes.dex`（baksmali→smali）** | E43 | 卡启动界面 | `report\01:181` | 确证 |
| **重编 `classes2.dex` 改一个 `const-string`** | E44 | **两处记载冲突**：一处"首次成功、之后同批全卡"；另一处"正常启动、SDK 登录成功" | `report\01:182`、`report\INDEX.md:203` | **冲突** |
| **改包名（manifest）** | — | `SIGBUS`（"包名被 ACE 校验，它拿 `sourceDir` 与包名做一致性判断"） | `report\DEADENDS.md:44-50`、`report\01:183` | 确证（现象） |
| **`res/*` + `resources.arsc`** | E32/E34/E42 | ✅ 均能启动（"安全改动面"） | `report\01:123`、`report\18:213` | 确证 |
| **`assets/SDKConfigSettings.json` 的 `sdk_url`（配合删 `__tpinfo`）** | E30/E42 | ✅ 6 个真实请求全命中我们服务器 | `report\01:124-125` | 确证 |
| **`libil2cpp.so` 填充字节翻转** | **E38** | ✅ **正常启动 45 s+ 存活** | `report\02:236`、`report\01:128`、`report\57:328` | 确证 |
| **`libil2cpp` 代码洞 + PLT 补丁** | E63 | ✅ 不触发 ACE、`alive=24049` | `report\02:234`、`report\10:59` | 确证 |
| **`networkSecurityConfig`（重打包加 manifest 属性）** | — | ❌ **本 APK 根本没有这个属性**（`res/xml` 只有 6 个 xml，无 `Dk.xml`）；且"重签会改签名，直接撞 ACE 的 `sourceDir` 完整性面"（**此句为推断，非观测**） | `report\DEADENDS.md:340-346`、`report\06:628` | 确证（前段）/ 推断（后段） |
| **LSPatch 内嵌模块进目标 APK** | — | ❌ 模块**自签名校验**（`EXPECTED_SHA256`）直接拒绝注入（这是**参照项目**的保护，不是 ACE） | `report\05-AzusaBA可复用资产.md:342`、`report\INDEX.md:263` | 确证 |

**"重打包到底成功过没有"的三个硬指标**：

1. `repack_e30.py … repack_e42.py` 全族可复现（`report\01:451`），脚本内容是"解官方 APK → 换 so/资源 → zipalign → apksigner"（`report\57:136`）。
2. `BA_E30.apk`（2,126,498,053 B）被明确记为"**已签名已安装**"（`report\01:494`）。
3. `e0/e1/e2/e0b/a_signed.apk.idsig` 各 16,750,059 B，反推对应 **~2.143 GB 的游戏本体 APK**（用 21 KB 模块 → 5,611 B idsig 定标）⇒ 这些是**重打包的游戏包**的 v4 签名凭证（`report\57:21`、`:331`）。

**"失败的确切现象"就一句话**：**所有失败都是"SIGBUS(7) / 无日志闪退 / 卡启动界面"三类，没有一类能追到"因为签名变了"**。签名变化唯一被确认的后果是 **安装层面**（`report\30:344`："不要覆盖安装，签名变了会失败"）与 **TapSDK 的一句 toast**（`report\21:862`，不影响流程，`report\29:81`）。

### Q5 — 手机侧是怎么获取/推送 APK 和 `.so` 的？说明了什么？

| 动作 | 实际做法 | 出处 | 置信度 |
|---|---|---|---|
| 控制通道 | 通过 Operit AI Web API 拿 root，起 bind shell：`su -c 'setsid busybox nc -ll -p 18080 -e /system/bin/sh &'`，`id` → `uid=0 context=u:r:ksu:s0` | `report\08-手机接管与真因.md:15-16` | 确证 |
| `.so` 传输 | ① 反向 TCP：30.2 s / **8.55 MB/s**（271 MB）；② `adb push` 到 `/data/local/tmp`；③ 手机主动 `nc` 推到 PC | `report\63-已证实事实冻结版.md:92`、`report\58-代码洞钩子-观测登录响应.md:318`、`report\14-运行期dump与证书补丁方案.md:174-184` | 确证 |
| `.so` 落位 | **root 原子替换**：`cp` 到同目录 `.new` → `sha256sum` → `restorecon` → `mv -f`；或直接 `cp` 覆盖 `/data/app/~~*/…/lib/arm64/libil2cpp.so` | `report\57:35`、`report\02:259-263`、`report\58:327` | 确证 |
| `.so` 事故 | 曾用 `cat > dst` 把 so 写成 **0 字节** → `dlopen: 0 >= 0` → 自杀循环 | `report\DEADENDS.md:553-559`、`report\08:212` | 确证 |
| APK | `/sdcard/Download/BA_E30.apk`（已签名已安装）；`pm install -r` 作为重新解压 `lib/arm64/` 的手段被论证过；签名变了必须 uninstall + install | `report\01:494`、`report\07:406`、`report\30:344` | 确证 |
| 资源 | 卸载重装前把 11 GB `mv` 到 `/sdcard/ba_data_bak`，装回后必须 `chown -R <新UID>:1078`（组必须是 `ext_data_rw`=1078） | `report\DEADENDS.md:577-583`、`report\01:142` | 确证 |

**这说明四件事（对免 root 方案直接相关）：**

1. **设备有 root（KernelSU）**，所以 `/data/app/.../lib/arm64/*.so` 被当作**普通可写文件**改了 —— 这条路径**完全不经过 APK 签名校验**。
2. 因此 **Q1 里最硬的几条证据（C13 原位替换、`DT_INIT` 改址、E63）都属于"root 路径"，不能直接外推到"免 root 重打包"**。真正属于"APK 路径"的证据只有两条：**E38（填充翻转，45 s+）** 与 **设备现役改包 APK 跑到昵称/发音界面**。
3. `/data/app` 下是**磁盘独立文件**（`extractNativeLibs=true` + `report\06:124` 的 maps 实证）⇒ **免 root 下这条路走不通**，必须回到"改 APK → 装"。
4. 改 so 的历史成功率被 **ACE"记账"** 严重污染：触发过一次异常改动后，后续**任何版本**都被 SIGBUS，直到删 `ace_shell_di.dat / shell_cache / ano_tmp / data/app` 才复位（`report\01:141`、`report\04:418`、`report\02:240`）。这正是"同一改法有时活有时死"（`report\00:230`）的解释，也是所有容错矩阵结论必须打问号的原因。

---

## 3. ACE 是否存在：判定与依据

### 判定：**存在，且在运行期活跃。置信度：确证。**

「国服是干净 Unity 包、没装 ACE」这个假设 **必须否掉**。它不成立，而且有六条互不依赖的证据链。

| # | 证据层 | 具体事实 | 出处 |
|---|---|---|---|
| 1 | **包里有 ACE 的 native 库** | `libtprt.so` = **1,692,296 B**，`audit\ba-apk\lib\arm64-v8a\` 24 个 so 之一 | `report\01:30`、`report\01:467`、`report\57:305` |
| 2 | **它是进程级依赖（最强的结构性证据）** | `libil2cpp.so` 的 `DT_NEEDED` = `liblog, libm, libdl, libc, libstdc++, libtprt`；`libunity.so` 的 `DT_NEEDED` 末尾也是 `libtprt` ⇒ 两个 Unity 核心库都靠它，游戏进程**必然**加载它 | `report\78:276-277` |
| 3 | **启动链由它接管** | `TechApplication extends AceApplication`；`attachBaseContextShell() → libtprt.initialize(pkg, filesDir, nativeLibDir, sourceDir, splits)`；不清 `files/data/app` 就卡在 `__sem_timedwait` | `report\01:31-34`、`:41`、`report\DEADENDS.md:71-72` |
| 4 | **manifest/服务面** | `com.ace.gshell.GP6Service / GP7Service / GP7Worker`（反编译实测）；`:GP6/:GP7` 独立进程，靠 `gp6ioctl/gp7ioctl` 通信 | `report\27:564`、`report\01:35-36`、`report\02:118` |
| 5 | **运行期真的在活动** | ① `files/` 下有 **`ano_tmp/*.dat`**；② 冷启动**第 0.00 秒**就 GET `down.anticheatexpert.com/…/config2.xml`（404）；③ `.text` 里 **26.2% 的页磁盘上是密文、加载时被还原**；④ 关键登录 handler（`HandleAccountAuthResponseMessage`/`OnLoginFinish`/`OnLoginFail`…）首 16 字节全是**非 ARM64 密文** | `report\21:1101`、`report\100:52`、`report\99:188`、`report\19:74`、`report\63:73-80` |
| 6 | **它有"能力"被观测到** | 改 `libunity` 4 字节 → **SIGBUS(7)**，而 E42 换回原厂立即正常（**这是本项目里最干净的一次对照实验**）；改 `libtprt` 任意字节 → `kill(SIGBUS)`；改包名 → SIGBUS；加 .so / 改 NEEDED → 无日志闪退 | `report\13:77`、`report\01:38`、`:183`、`:184` |

### 但在它之外还有至少 4 套独立风控（不是同一件事，方案评审不要混算）

| 组件 | 观测 | 出处 | 置信度 |
|---|---|---|---|
| 数美 `com.ishumei.smantifraud` | 4 个 Xposed/EdXposed 枚举方法是**活代码**（DEX 级 5 处真实 invoke）；`l1111l111111Il.java:528` 读 `/proc/self/maps` 只保留含 `/data/app/` 的行 | `report\01:59-60`、`:146`、`:251`、`report\17:137` | 确证 |
| 腾讯图灵盾 `com.tencent.turingfd` | 读 `/proc/self/status` 取 `TracerPid`、`mTransportTypes` 位图上报 | `report\01:62` | 确证（引） |
| TapTap Themis | `com.taptap.sdk.themis.lite.ThemisProvider` + `libthemis.so` | `report\27:535`、`report\01:63` | 确证 |
| Adjust `libsigner.so` | 随包存在 | `report\01:63` | 确证 |
| TapSDK 的签名自检 | 现场 toast `TapSDK: 包名、签名错误` —— **它对重签包有意见，但不阻断** | `report\21:862`、`:869` | 确证 |

> **重要口径**：`report\01:522` 已明确记录团队自己的结论 ——「**不能算'全部绕过'**」（客户端层 ✅ 基本绕过；native/环境层 ❌ 未绕过，三条暴露面仍在：`libNeko.so` 的 maps 可见性 / **APK 签名与路径** / 环境指纹）。所以做方案时不要写"反作弊已解决"。

---

## 4. 改 `.so` 能跑 ⇒ 无严格完整性校验？证据链

### 结论：**"整包级"完整性校验：不存在。"定点级"完整性校验：存在，且名单是明确的。**

```
                    ┌─────────────────────────────────────────────┐
   APK 层面          │ 签名变化 → 未见任何杀进程证据（E30 已签名已安装 │
                    │   + 现役改包跑到昵称页 + TapSDK 只吐槽不拦）    │
                    │ 整包哈希 → 无任何文档/实验涉及                  │
                    └─────────────────────────────────────────────┘
                                        │
                    ┌─────────────────────────────────────────────┐
   自身完整性清单      │ assets/__tpinfo.{tsc,tsc.sig,tsd,tsd.sig,tp} │
                    │  ← 5 个文件删掉 ⇒ "完整性校验整段跳过"          │
                    │  ← 这是所有改包能跑的总前提                    │
                    └─────────────────────────────────────────────┘
                                        │
        ┌───────────────────┬───────────┴────────────┬──────────────────┐
   被钉死的文件         被钉死的"布局"            被钉死的"身份"      没被钉死的
   libunity.so       加新 .so / 改 DT_NEEDED    包名               libil2cpp.so
   改 4 B → SIGBUS    → 无日志闪退              → SIGBUS           4 种改法全活
   libtprt.so        新增/重编 dex
   改任意 B → SIGBUS  → 卡启动界面
   libairisgcore.so
   整库换 → SIGBUS
        │                  │                      │                    │
        └──────────┬───────┴──────────┬───────────┴────────┬───────────┘
                   ▼                  ▼                    ▼
              SIGBUS(7)          无日志闪退           卡 Android 启动界面
           ApplicationExitInfo   （连 tombstone 都没有）  （Unity 从未加载）
           reason=2 status=7
```

### 证据链（每一步都能落到行号）

1. **前提层：删 5 个 `__tpinfo` 文件 ⇒ 自身完整性校验整段跳过。**
   `report\01:122`（"所有改包能跑的前提"）、`report\01:125`（改 `assets/*.json` 时同步删）、`report\03:474-475`（上游把同一批文件叫"自身文件完整性"）。
   ⇒ **推论（强）**：ACE 的自身完整性校验是**数据驱动**的（读 `__tpinfo` 清单），**清单不在就不校验**。这意味着"重打包 = 必然被杀"的前提**不成立** —— 只要删对文件。

2. **否定层：`libil2cpp.so` 明确不在校验名单。**
   - 静态："无 hash/CRC pin（静态弱否定）"（`report\01:129`）。
   - 实验四条独立路线全活：E38（`report\02:236`）、E63（`report\02:234`）、`DT_INIT` 改址（`report\01:133`）、root 原位替换（`report\01:134`、`report\10:64`）。
   - **最强的一条**：设备现役 APK 内嵌的 so 本身就是改过的（`report\08:132`），而这个包跑到了取昵称 / 发音界面（`report\84:35-36`）。
   - 边界：**"内存 CRC"未知**（`report\18:210`、`:234`、`report\11:243`）—— 不能排除"加载后某时刻查内存"。

3. **对照层：项目有能力证明"校验存在"，只是对象不是 libil2cpp。**
   E42 原厂 `libunity` 对照（`report\13:77`）是本项目**唯一一次干净的单变量对照**：同一套其它改动，只换 `libunity` 版本 → 从 SIGBUS 变正常。这条同时证明了 **ACE 的加载期校验确实在工作**，因此"libil2cpp 能跑"不是"校验挂了"，而是"它不在名单里"。

4. **噪点层：ACE"记账"会伪造出"校验变严"的假象。**
   `report\01:141`、`report\04:418`、`report\02:240`、`report\00:230`："同一改法有时活有时死，这大概率是记账污染，不是概率"。
   ⇒ 任何新实验**必须先复位记账**（删 `files/{ace_shell_di.dat, shell_cache, ano_tmp}` + `files/data/app`），否则结论不可信。

5. **真空层：以下三件事报告里**一次都没做过**，因此不能写入任何结论。**
   - 不删 `__tpinfo`、只改签名 → 会不会被杀？**未做**。
   - 改 `global-metadata.dat` → 会不会 SIGBUS？**未做**（metadata 补丁从未上机，`report\57:123/125`）。
   - ACE 是否做内存 CRC / 是否查 `sourceDir` 里的签名？**未做**（`report\01:336`、`report\18:234`）。

### 一句话表述（可直接引用）

> **"改了 `.so` 还能跑"是确证事实，但它证明的是"`libil2cpp.so` 不在 ACE 的完整性校验名单里"，而不是"ACE 没有完整性校验"。真正的完整性校验表现为什么形态、名单上有谁，见上图：`__tpinfo` 是总开关，`libunity`/`libtprt`/`libairisgcore` + 加载布局 + 包名是被点名的对象，`libil2cpp` 是漏网的那一个。**

---

## 5. 对"重打包 APK"的推论

### 5.1 判决

**从反作弊角度：重打包 APK 是可行的。从工程/交付角度：它是本项目最贵的一条路。** 关键差别在于——**"重签会被 ACE 杀"是项目文档里的一个假设，不是一次观测**（`report\17:396`、`report\05:370`、`report\52:544`、`report\53:532`、`report\20:604` 全是风险预判；`report\01:336` 明确列为"未做"）。而**实际做过的十余版重打包，没有一次死于签名**。

### 5.2 如果要做，必须遵守的硬约束（每条都有反面证据）

| # | 约束 | 违反的后果 | 出处 |
|---|---|---|---|
| **R1** | **必须删 `assets/__tpinfo.{tsc,tsc.sig,tsd,tsd.sig,tp}` 这 5 个文件** | 改包即闪退（无日志、无 tombstone） | `report\01:122`、`report\INDEX.md:45` |
| **R2** | **`libunity.so` 必须保持原厂字节**，一个字节都不能改 | 启动即 `SIGBUS reason=2 status=7`，无 tombstone | `report\DEADENDS.md:15-16`、`report\13:77` |
| **R3** | **不要加新 `.so`、不要改 `libmain.so` 的 `DT_NEEDED`** | **无日志闪退**（连 tombstone 都没有） | `report\DEADENDS.md:31-32`、`report\01:184` |
| **R4** | **不要新增/重编任何 `.dex`** | 卡 Android 启动界面（Unity 从未加载） | `report\DEADENDS.md:39-40`、`report\01:180-181` |
| **R5** | **不要改包名** | `SIGBUS` | `report\DEADENDS.md:47-48`、`report\01:183` |
| **R6** | `libil2cpp.so` **可以改** —— 但保持文件大小与段布局不变（填充位/明文页/等长替换），并接受"内存 CRC 未知" | 已知四条路线都能活；内存侧未知 | `report\01:128-134`、`report\18:234` |
| **R7** | 实验前**先复位 ACE 记账** | 否则任何失败都可能是上次的连坐，结论不可用 | `report\01:141`、`report\02:264`、`report\00:230` |
| **R8** | 签名变了 ⇒ **必须 uninstall + install**（不能覆盖装） | `INSTALL_FAILED_UPDATE_INCOMPATIBLE`（预判） | `report\07:406`、`report\30:344` |

### 5.3 真正的成本在安装侧，不在反作弊侧

| 成本项 | 量级 | 出处 |
|---|---|---|
| 包体 | **2.13 GB**；`apksigner` 需要 ≥2.1 GB 空闲，否则**半截输出** | `report\01:503`、`report\17:351`、`report\57:141` |
| 重装 | 签名变 ⇒ 卸载重装 ⇒ **UID 变** ⇒ `/data/data` 全丢（**卡密登录态在里面**） | `report\30:344`、`report\52:545`、`report\DEADENDS.md:581` |
| 资源 | 11 GB 要 `mv` 回 + `chown -R <新UID>:1078`（组必须是 `ext_data_rw`） | `report\01:142`、`report\DEADENDS.md:577-583`、`report\06:71` |
| 迭代速度 | 对比"root 原位替换 `cp` 一下" = 免重打 2.1 GB APK | `report\01:134`、`report\10:64` |
| SDK 层噪声 | 每次启动一句 `TapSDK: 包名、签名错误`（既知、不影响流程） | `report\21:862`、`report\29:81` |
| **ACE 记账** | 失败一次后所有后续版本 SIGBUS，需手动复位 4 处 | `report\04:418`、`report\02:240` |

### 5.4 还没解决、会卡住"重打包路线"的两个前置未知

1. **`global-metadata.dat` 到底从哪读**（APK 内 zip 条目 vs 解包后独立文件）。这决定"改域名/公钥要不要动 APK"：
   - 若是独立文件 ⇒ **一条 `cp`**，不需要重打包（`report\52:507`）。
   - 若是 zip 条目 ⇒ **必须重打包**（`report\30:337`、`report\52:541`）。
   - 状态：**未验证**（`report\30-网关RSA公钥定位与替换.md:386`、`report\INDEX.md:359`；`report\INDEX.md:359` 另提到"`files/il2cpp/Metadata/global-metadata.dat` 外部存储里有一份、值得查"，该线索本次未追）。
2. **ACE 是否校验 `global-metadata.dat`** ⇒ **未知**（`report\30:323`、`report\28:842`；`report\38:301` 说"钉了"但无实测，标为冲突）。

### 5.5 建议给 Lead 的一句话

> **不要再把"重打包会被 ACE 杀"当作已证结论去排除方案。** 项目自己十余版重打包（E28–E44）+ 现役改包跑到昵称界面，已经证明**签名变化本身不触发 ACE**；真正的红线是 **`__tpinfo` 必须删、`libunity`/`libtprt`/`libairisgcore` 不许动、不加 .so/.dex、不改包名**。免 root 重打包的可行性瓶颈在"2.1 GB 包 + 卸载重装 + 11 GB 资源 chown + 丢登录态"，以及"``metadata` 读取路径未知"这两件工程账上，**不在反作弊上**。相反，如果真的只想改域名，**优先验证 metadata 的读取路径**：若是独立文件，`cp` 一下就完事，连重打包都不需要（`report\52:507`）。

---

## 附录 A：本次扫描的方法与可复现性

- **工具**：`grep`（ripgrep 内核）+ `read`，对 `report\` 全目录执行；`*.md` 全量（90 份）+ `_tmp\` 下 `.txt/.log/.sh/.py` 抽样命中。
- **一个已知的扫描缺口**：`report\_tmp\meta_re\s1_out.txt`（**10,426,122,890 B / 10.4 GB**，Archive 属性）会让 ripgrep 直接报 `os error 87` 并中止整个目录的搜索。本次对 `report\_tmp` 采用"逐子目录（跳过 `meta_re`）"的方式绕开。**该文件是 metadata 的原始扫描输出，与完整性校验/ACE 直接相关性低，但严格说未逐字节扫过** —— 若后续要宣称"穷尽"，需单独处理它。
- **未执行**：任何 adb / ssh / curl / 服务端操作；未修改任何既有文件（本文件是唯一新增产物）。

## 附录 B：本报告引用的"上游文档"清单（在 `report\` 之外，本次无法复核）

以下文件被 `report\` 内的文档大量转引，**本次按"转引"处理，未独立验证**：

`work\ba\audit\ba-pitfalls.md`、`ba-gateway-host.md`、`ba-airisdk.md`、`ba-java.md`、`ba-hook-survey.md`、`anticheat-full.md`、`ace-ipc.md`、`anti-detection.md`、`shumei-xposed.md`、`md-xign.txt` 等。

其中**最关键的三条**只在上游有原文，`report\` 内是二手：
1. `ba-pitfalls.md:9-11`（删 `__tpinfo` 5 文件）
2. `ba-pitfalls.md:197`（root 原位替换后 `DT_INIT` 照跑）
3. `ba-pitfalls.md:62-69`（ACE 记账复位 4 文件）

⇒ 若要把本报告结论写进交付文档，建议先花 10 分钟核这三处原文。
