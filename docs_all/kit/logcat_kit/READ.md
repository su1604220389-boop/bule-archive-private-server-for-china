# logcat 取证包 · 判读表（READ）

> 配套：`capture.sh`（采集）、`tagprobe.sh`（tag 自检）、`pull.sh`（回传）、`checklist.md`（给 phone-ops 的逐步命令）
> 目标：在「用户点一下 → 客户端回 200 → 静默」这几十毫秒的窗口里，拿到 app PID 自己的托管层日志，并**能证明这份日志是响应引起的**。
> 写于 2026-11-14 03:4x，基于 `report/` 已有 40 份报告的实证（引用见文末「查档」）。

---

## 0. 三条铁律（先读，能省一整轮返工）

1. **`cap_raw.txt` / `buffer_dump.txt` 是证据，`filtered.txt` 只是给人看的视图。**
   任何结论必须能回到 raw 行；`filtered.txt` 里没出现 ≠ 日志里没有（它按已知噪音做了删除）。
2. **`TAGGED_LINES=0` 不等于「没抛异常」。**
   release 包里 Unity 日志可能被业务代码关掉、也可能这条路径压根不打日志。**没有对照组（C 组）或灯泡测试（§5）时，0 行只能记为「仪器不确定」**，不能写「无异常」。
3. **点击时刻不需要你精确记。**
   日志里 `input_interaction` 行就是点击锚点；外部的锚点是 conntrack 里新出现的 sport。你要保证的只是「点击落在窗口内」，不是「几点几分几秒」。

---

## 1. 30 秒判读：先看 `verdict.txt`

| 键 | 含义 | 怎么用 |
|---|---|---|
| `ALIVE_T1` | 抓完时进程还在不在（1/0） | 0 → 直接跳 `crash.txt` / `tomb_new.txt` |
| `PID_CHANGED` | 窗口内 PID 变了没有（1/0） | 1 → 进程重启过，日志要按两个 PID 分别看（脚本已自动合并） |
| `PID_GONE_AT` | 第几秒发现 PID 消失 | 有值 → 看这个秒数之后有没有 `am_proc_died` |
| `TAGGED_LINES` | **`Unity` tag 的行数**（本次核心指标） | >0 → 读 `tagged.txt`；=0 → 先做 §5 判定 |
| `LITERAL_HITS` | 三条真实错误文案的命中数（见 §2A 末尾） | >0 → HINT 会直接指向 `signals.txt` H 段 |
| `EXC_LINES` | 含 `Exception / NullReference / Json / KeyNotFound …` 的行数 | >0 → 读 `signals.txt` 的 A 段 |
| `CLICK_SEEN` | 窗口内 `input_interaction` 行数 | 0 → 点击可能没落进窗口，或该机型不打这个 tag；用 conntrack 复核 |
| `CRASH_FATAL` / `NEW_TOMBSTONE` | 崩溃缓冲 / 新 tombstone | >0 → 崩了，走 native 判读 |
| `AM_CRASH` / `AM_ANR` / `AM_KILL` / `AM_PROC_DIED` | events 缓冲里的生命周期事件 | 用来区分「崩了」「被系统杀」「自己退了」 |
| `AVC_DENIED` | `avc: denied` 行数 | >0 且与 logcat 相关 → SELinux 挡读，走 §7 备选链 |
| `CHATTY` | 日志被折叠/丢弃的告警行数 | >0 → 关键行**可能已丢**，用 `BUF=8M` 重跑 |
| `HINT` | 脚本给的一句话指向 | 只是入口，不是结论 |

---

## 2. 判读总表（主表）

> 左列是你在 `tagged.txt` / `signals.txt` / `crash.txt` / `verdict.txt` 里**实际能看到的东西**；不是猜测。

### A. 托管层（Unity / C#）——本次主战场

| 现象 | 结论 | 下一步 |
|---|---|---|
| `E Unity : NullReferenceException: Object reference not set to an instance of an object.` 后面跟 `at Xxx+<Yyy>d__N.MoveNext () [0x00000]` | **响应被读进去了，但某个字段是 null / 类型不符**，协程第一次解引用就炸 | 记下类名 `Xxx` 与协程名 `Yyy`（这就是读取点）；拿 `report/36-Account_Auth响应字段清单.md` 的 24 键逐键比对，找 il2cpp-analyst 补字段 |
| `E Unity : MissingFieldException` / `KeyNotFoundException` / `InvalidCastException` / `ArgumentNullException` | schema 不匹配（键名拼错、类型错、该是数组的给了对象） | 同上；优先查 `AccountDB` / `SessionKey` / `StaticOpenConditions` 三块 |
| `E Unity : JsonReaderException` / `Unexpected character` / `Invalid JSON` / `Additional text encountered` | body **不是合法 JSON**：WAF 顶成 200+HTML、gzip 截断、`packet` 没做 base64、明文/密文给反 | 服务端 `head -c 300` 看 body 与 `Content-Type`；查网关信封层（`report/32`、`report/35`） |
| `E Unity : <一句中文/英文业务文案>`（没有 Exception 字样） | 业务逻辑主动判定失败，**并且它愿意打日志** | 拿这句文案去 `global-metadata.dat` 反查字符串字面量 + 交叉引用，定位分支条件 |
| `E Unity : Protocol not supported` | **协议名认不出** —— 响应外层 `protocol` 的值与请求 token 对不上，**不是字段层问题** | 改外层 `protocol`（`report/41` §9.C 的 L1 那一枪）；这句是 metadata `0x0008E65A` 的真实文案 |
| `Unity : POPUP_NETWORK_ERROR_TITLE`（任意级别） | 这是弹窗的**本地化 key**，不是文案 | 说明弹窗文案走 i18n 表；grep 不要只找中文；弹窗有无仍以截图像素（`btn_px`）为准 |
| `E Unity : UNSUPPORTED` | 枚举/状态不支持（metadata `0x000BBE54`） | 看它前后 3 行，定位是哪个枚举 / 版本分支 |
| `I Unity : <业务文案>`（Info 级，无异常） | 有日志、无异常：代码自己放弃 / 在等某个条件 | 记时间戳，对照点击；再看 `signals.txt` D 段与 conntrack 有没有第二个请求 |
| `E Unity` 行**存在但时间戳早于点击** | 与本次响应无关（启动期/上一轮残留） | 不要归因；只认「点击后 0–3 s」的那几条 |
| `tagged.txt` **0 行**，进程还在，`CLICK_SEEN>0` | 两种可能：①没抛未捕获异常，卡在 await/协程；②Unity 日志被关 | **必须先看 C 组（404）**：C 组有 Unity 行 → ①成立；C 组也没有 → ②，转内存扫描路线 |
| `tagged.txt` 0 行、`CLICK_SEEN=0` | 本次没抓到点击，窗口无效 | 重跑；先确认用户确实点了（屏幕变了没有） |

> **为什么以前 grep 这些文案全是 0 命中**：`il2cpp-analyst` 在 metadata 里发现一层 **XOR 0x20 大小写翻转**（`pROTOCOL` → `Protocol`）。所以本包对这三条一律用 `grep -i`，`pROTOCOL not supported` 这种形态也能命中。同理，看到「大小写怪异的英文」不要当成乱码，先按 XOR 0x20 还原再看。

### B. 进程生命周期——「人还在不在」

| 现象 | 结论 | 下一步 |
|---|---|---|
| `ALIVE_T1=0` + `am_proc_died` | 进程死了 | 看 `crash.txt`、`tomb_new.txt`；再看 `am_proc_died` 的 `reason`（`report/21:47` 有原文示例） |
| `am_kill` 事件 | **被系统/AMS 杀的**，不是客户端自己退 | 看 lowmemorykiller / 厂商清理；不是代码 bug |
| `am_crash` 事件 / `F/libc` / `FATAL SIGNAL` / `SIGSEGV` / `SIGABRT` | native 崩 | `tomb_new.txt` + tombstone；交给 native 侧，不是 C# 层 |
| `E AndroidRuntime : FATAL EXCEPTION` | Java 层崩（不是 C#） | 读 Java 栈；多半在 SDK 里，与网关响应无关 |
| `PID_CHANGED=1` 且没有 `am_proc_died` | 进程被重启过（崩溃循环/被拉活） | 看两个 PID 的行；`am_proc_start` 会给出新 PID 的启动时刻 |
| `ALIVE_T1=1`、`PID_CHANGED=0`、无 crash | 进程健康 | 卡点是「逻辑停住」，不是崩溃 |

### C. 网络 / 连接

| 现象 | 结论 | 下一步 |
|---|---|---|
| `signals.txt` F 段出现 `timeout` / `refused` / `reset` / `EOF`（且来自 app PID） | 连接层出问题 | 抓包；对照服务端 pcap |
| 日志里**没有任何**网络错误，但也没有第二个协议请求 | 响应被吃掉了，代码停在解析/分支里 | 回到 A 组；同时用 conntrack 的 fresh sport 证明「真的没有第二个请求」 |
| conntrack 出现新 sport（外部证据，不在 logcat 里） | 第二个请求真的发了 | 该与网关 `api_all_requests.log` 的同一秒对齐 |
| `ss` 里 `CLOSE-WAIT`（外部证据） | 服务端 FIN 后客户端不读不关 | `report/26` 记录过 state-api 的同类现象；不要当崩溃 |
| **TCP 出现 RST / FIN**（logcat 里通常看不到；只能从抓包或 `ss` 看） | 连接被对端主动关 | 手机 `tcpdump` 或服务端 pcap 分析；同时 `ss -tnp` 看是 `CLOSE-WAIT`（我们 FIN 了它不读）还是 `TIME_WAIT`（它先关）。`report/29:67-73` 的判据纪律：只认 pcap |

### D. 仪器层——「这份日志本身可不可信」

| 现象 | 结论 | 下一步 |
|---|---|---|
| `CLEAR_RC≠0` 或 `CLEAR_LEFT` 明显 >5 | 清缓冲失败，窗口起点不干净 | 只信 T0 之后时间戳的行；重跑一次确认 |
| `chatty: ... expired` / `chatty: uid=10576` | logd 折叠/丢弃了日志，**关键行可能没了** | `BUF=8M` 重跑；并检查 `CHATTY` 计数 |
| `avc: denied { read }` 且 `tcontext=u:r:logd:s0` | SELinux 挡了 root 域读 logcat | 脚本已自动尝试 `su -c`；仍失败 → 见 §7 |
| `LOGCAT_WRAP=su` | 直接读被挡，已用 `su -c` 兜底 | 正常，但要在报告里写明走了兜底 |
| `CAPBUF=-b all` | 多 buffer 写法被拒，退化成 all | 正常；`-b all` 也会含 events，噪声更多 |
| 只有系统 tag（`VRI` / `WindowManager` / `input_interaction`） | 日志管道通，只是**应用层没打** | 不能推「无异常」；见 §5 |

---

## 3. 三组差分（这是「证明」的部分）

| 组 | 服务端 | 用户动作 | 窗口 | 这组要回答什么 |
|---|---|---|---|---|
| **A 基线** | 200 | **不点**，停在标题页 | 25–30 s | 「没有请求」时日志长什么样 = 本底噪声。B 组里与 A 组同形的行都不能算线索 |
| **B 目标** | 200 | 点 | 60 s（第 15 s 点） | 响应回来之后，app 自己打了什么 / 什么都没打 |
| **C 对照** | **404** | 点 | 60 s（第 15 s 点） | 「会弹窗的失败」在日志里长什么样 = 仪器的正控 |

判读规则：

1. **B − A = 响应引起的日志。** 只在 B 出现、A 没有的行，才允许归因给这次响应。
2. **C 是仪器的照妖镜。**
   - C 出现 `E Unity` 之类，B 没有 → 强证据：**200 路径没有抛未捕获异常**（要么被 try/catch 吞了，要么卡在 await）。
   - C 也没有 → 说明这个错误路径也不打日志 → **logcat 对这一层是哑的**，B 的 0 行不能作任何推断，转 §5 灯泡测试或内存扫描。
3. 三组的 `CLICK_SEEN` 都必须 >0，否则该组作废。
4. 三组必须**同一次冷启动流程**（kill → 拉起 → 等标题页 → 再抓），不要用「已经卡住的那次进程」凑数。

---

## 4. 一条 Unity 日志怎么读

历史实证样本（`report/21-手机侧执行记录.md:501-503`，当时用的是 `-v time`，所以 pid 在括号里）：

```
11-14 01:49:09.333 E/Unity (26473): NullReferenceException: Object reference not set to an instance of an object.
11-14 01:49:09.333 E/Unity (26473):   at ServerInfoDataRepository+<GetApiServerInfo>d__23.MoveNext () [0x00000]
11-14 01:49:09.333 E/Unity (26473):   at UnityEngine.SetupCoroutine.InvokeMoveNext (...) [0x00000]
```

本套脚本用 `-v threadtime`，同一条会变成（列不同，文本一样，别以为抓错了）：

```
11-14 03:20:01.400  2676  2700 E Unity : NullReferenceException: Object reference not set to an instance of an object.
11-14 03:20:01.401  2676  2700 E Unity :   at ServerInfoDataRepository+<GetApiServerInfo>d__23.MoveNext () [0x00000]
```

逐段含义：

| 片段 | 含义 |
|---|---|
| `E` | 级别。`E` = Error（`Debug.LogError`/异常），`I` = Info（`Debug.Log`），`W` = Warning |
| `Unity` | **这个包的 Unity 日志 tag 已实证就是 `Unity`**（见上引） |
| `2676 2700` | pid / tid。**按 pid 过滤才是可靠的**（tag 名可能有空格） |
| `NullReferenceException: ...` | 异常类型 + .NET 的固定文案 |
| `ServerInfoDataRepository` | **类名** ← 这就是要回填字段的坐标 |
| `+<GetApiServerInfo>d__23` | 编译器为协程 `GetApiServerInfo` 生成的状态机类（`d__23` 是编号） |
| `.MoveNext()` | 协程体；异常发生在这里面 |
| `[0x00000]` | **release 版没有调试信息**（不是「地址 0」），所以拿不到行号——别去找行号 |
| `at UnityEngine.SetupCoroutine.InvokeMoveNext` | Unity 的协程调度器，说明这是**协程里抛的**，不是 Update 里 |

⇒ 给 il2cpp-analyst 的一句话：**「`<类名>.<方法>` 的协程在 MoveNext 第一次解引用时 NRE；对应响应里哪个字段，按 24 键清单查」。**

---

## 5. 仪器盲区：0 行到底说明了什么

`report/21:1471-1476` 已经有过一次「窗口内 `[VDIWEF]/Unity` = 0 行」的记录（02:54–02:59，含一次点击）。所以 **B 组 0 行是完全可能发生的，而且不构成结论**。要把它变成结论，必须先证明仪器可见——二选一：

### L1（本轮**必做**：lead 已定为前置 G3）
由 `srv-ops` 在服务器侧提供毒化包 `packet = {"CurrentVersion":"P41-CANARY"}`（类型毒化，只改一个字段），本包只负责抓它的 logcat 侧；跑完立刻回滚。
- 出现 `JsonSerializationException` / `JsonReaderException` / `Unexpected character` → **仪器可见，且证明 200 路径下 body 真的进了反序列化器**。这是 C 组（404）证不了的那一半。
- 什么都没出现 → 这一层根本不打日志，logcat 路线到此为止，转内存扫描（`report/38` 的 Frida/TLS 钩子路线）。

### L2（备用，利用已知可复现的 NRE）
把 `state-api` 的 `Servers` 改回 `null`，冷启动，5 s 内应出现 `E/Unity NullReferenceException`（`report/26:15-16` 两次独立复现）。
- 出现 → tag 与管道都正常（但只证明了**启动路径**的日志可见，不如 L1 贴近本问题）。
- 不出现 → 说明日志能力变了（版本/配置），必须先查 tag（跑 `tagprobe.sh`）。

> 没做 L1/L2 也没做 C 组时，结论只能写成：**「窗口内无 Unity 输出；仪器可见性未验证」**。

---

## 6. 点击时刻怎么对齐（不需要秒表）

1. 日志内的锚点：`input_interaction` 行，例如
   `11-14 02:56:37.597 4005 4010 I input_interaction: Interaction with: [5abe2c5 com.RoamingStar.BlueArchive/...]`
   （原文见 `report/21:1479-1483`；`CLICK_SEEN` 就是这个计数）
2. 外部锚点：conntrack 里**新出现的 sport**。`report/21:1418-1423` 与 `:1534` 已证明「每次点击稳定触发一次新连接」。同一节 `:1479-1483` 还给出过 02:56:37/40/41 三行 `I/input_interaction` 的原样（那是 02:54–02:59 那轮的日志）。
3. 响应到达 ≈ 点击 + 50–500 ms（同一台机器上 TLS 已建连，走的是长连接或新连接）。**判读窗口取「点击 − 1 s ～ 点击 + 5 s」**足够覆盖几十毫秒的静默点。
4. 脚本里的 `[cue] t=15` 只是记录一个名义时刻，**不是提醒铃**（前台跑时输出要等结束才回到 PC）。真正的提醒由人来做：开抓前先跟用户说「我开始抓，大约 15 秒后你点」。

---

## 7. SELinux / 读不到日志时的备选链

现状：`report/21:102-104` 已实证 **KSU root 域 `u:r:ksu:s0` 直接 `logcat -c` / `logcat -d -b all` 都成功**（rc=0）。`report/20:258` 的担心在本机尚未发生。但脚本仍按顺序兜底：

1. 直接 `logcat`（默认路径）
2. `su -c 'logcat ...'`（脚本自动切换，`verdict.txt` 的 `LOGCAT_WRAP=su` 会标出来）
3. 只读 `-b main`（去掉 system/crash）
4. PC 侧 `adb logcat`（若 USB 在线；`adb shell` 天然有 READ_LOGS）
5. **最后**才是 `setenforce 0`：必须 lead 批准、只在一次采集期间打开、结束立刻 `setenforce 1`。它会提高 ACE 的「环境异常」命中率，**不要默认用**。

---

## 8. 已知噪音白名单（出现 ≠ 线索，别再查一遍）

| 噪音 | 真相 | 出处 |
|---|---|---|
| `TapSDK: 包名、签名错误。详见 ErrLog` | 改包/重签的必然结果，不影响流程（用户已确认） | `report/29:81` |
| `RetryUtils req_1/req_2 网络请求失败` | 阿里 netspeed 诊断（pid 4747 那个），与游戏无关 | `report/29:82` |
| `LogProducerHttpTool ... not verified` / `sls_android_native` | 阿里 SLS 日志上传；`not verified` 是**主机名不匹配**（证书 DN 是 `*.bluearchive-cn.com`），不是链问题 | `report/21:183-187`、`report/29:83` |
| `openlog.cpp ... status=404` | TapTap 埋点 | `report/29:84` |
| `hiddenapi: Accessing hidden method ... denied` | TapSDK 的 okhttp 反射，Android 9+ 常态 | `report/21:55` |
| `F/libc: FORTIFY: pthread_mutex_lock called on a destroyed mutex` | ACE/pushcore 子进程退出的固有噪音，主进程始终活着 | `report/06:420` |
| `DNS_CACHE: hanle request` | netd(1937) 的解析流水 | `report/06:196-197`、`report/10:15` |
| `Oplus*` / `VRI[...]` / `relayout` / `updateBlast` | ColorOS 窗口系统 | `report/21:175` |
| `Adjust` / `tapsdk/events.db` | 第三方埋点落盘 | `report/21:1447-1449` |

> `filtered.txt` 已按这张表做过删除；`app_lines.txt` 保留全部。

---

## 9. 速查命令

手机侧（在 `*.d/` 目录里）：

```sh
grep -E ' (Unity|il2cpp|Mono|BestHTTP) *:' app_lines.txt      # 只看 Unity 家族
grep -inE 'protocol not supported|popup_network_error_title|unsupported' app_lines.txt   # 三条真实文案（-i 兼容 XOR 0x20）
awk '$3==PID' app_lines.txt                                    # 只看某个 pid
grep -nE 'Exception|NullReference| at ' app_lines.txt | head   # 异常 + 托管栈
sed -n '/== A/,/== C/p' signals.txt                            # 异常段 + Unity 段
sed -n '/== H/,$p' signals.txt                                 # 三条真实文案
sed -n '1,40p' verdict.txt                                     # 先看这个
```

PC 侧（PowerShell，解包后）：

```powershell
Get-Content .\verdict.txt
Select-String -Path .\tagged.txt -Pattern 'Exception| at '
Get-Content .\signals.txt | Select-Object -First 120
```

回传 + 解码：

```powershell
python report\_tmp\rsh.py --out lc.b64 "sh /sdcard/logcat_kit/pull.sh /sdcard/lc"
[IO.File]::WriteAllBytes("$PWD\lc.tgz",[Convert]::FromBase64String(((Get-Content .\lc.b64 -Raw) -replace '\s','')))
tar -xzf .\lc.tgz
```

---

## 10. 不能下的结论（反误判清单）
1. **「没抓到 Unity 日志 = 没抛异常」** —— 错，除非有 C 组或 L1/L2 正控。
2. **「有 `E Unity` = 是我们的响应引起的」** —— 不一定，先看时间戳是否在点击后 0–3 s，再看栈里是不是 `MoveNext`。
3. **「`am_proc_died` = 崩溃」** —— 不一定。`report/21:49` 记录过 `exit_self_13466_10576`：用户点「确定」后**自己退的**。
4. **「进程活着 + CPU 80% = 死锁」** —— 报告 21 多轮里就是活着 + CPU 高 + 无新文件；这是「停住」，不是死锁。
5. **「`RetryUtils` / `SLSAndroid` / `LogProducerHttpTool` 又出现了 = 有关」** —— 与本问题无关，见 §8。
6. **「日志时间 = PC 时间」** —— 错，logcat 用手机本地时钟；只与手机上的 `date` 比。
7. **「窗口没抓到点击也照样分析」** —— 该组作废，重跑；否则会把「没点到」误读成「没响应」。

---

## 11. 本轮前置与执行入口

- **时间紧**：直接把 `RUNBLOCK.md` 里「══ 指令块 ══」之间那段整块转给 phone-ops，不要让它自己读本文件。
- **两个前置（由 lead 确认，phone-ops 不得自判）**：
  - **G1** 服务端 `exp`：B 组 = `200`；C 组 = `404`（`decrypt+plain+http404`，srv-ops 在采集窗口前 30 秒切、采完切回）；
  - **G2（若做 L5）** 毒化包已上线：`packet = {"CurrentVersion":"P41-CANARY"}`。
- **SELinux**：不 `setenforce 0`（lead 已定）。读不到就走 `su -c` / adb，全哑了回报 lead 由用户决定。

---

## 查档

| 用了什么 | 出处 |
|---|---|
| Unity tag = `Unity`，NRE 原文与栈格式 | `report/21-手机侧执行记录.md:501-503`、`report/26-进度-NRE已修-卡点后移.md:15-16,92` |
| 「Unity 一条日志都不打」是**误判**（`E/` 前缀过滤导致） | `report/26:92` |
| 00 清理缓冲在 ksu root 域可用（rc=0） | `report/21:102-104` |
| `-s` 用法坑、`grep -E ' E '` 匹配不到 `-v time` 格式 | `report/21:246-247` |
| 窗口内 Unity 0 行的先例（02:54–02:59） | `report/21:1471-1476` |
| 点击 → 新连接（判据） | `report/21:1418-1423`、`report/21:1534` |
| logcat 噪音白名单 | `report/29:78-87`、`report/21:52-62,183-187` |
| 无崩溃/ANR/tombstone 的历史观测 | `report/25:57-62`、`report/06:39,217-228` |
| `Logcat` 一击定位与 SELinux 备注 | `report/20:246-258` |
| 24 键响应清单（补字段方向） | `report/36-Account_Auth响应字段清单.md:22-53` |
| 崩溃缓冲抓取范式 | `report/06:39,107-110,217-228` |
| il2cpp 无导出符号 → 降级路线 | `report/38-Frida部署清单.md:165-205` |
