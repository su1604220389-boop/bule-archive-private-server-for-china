# 40 — logcat 取证方案（200 静默窗口）

> 时间：2026-11-14 03:4x
> 交付物：`kit/logcat_kit/{capture.sh, tagprobe.sh, pull.sh, READ.md, checklist.md}`
> 本文件只写方案与判读，不代替 phone-ops 执行；手机操作见 `checklist.md`。

---

## 一、一句话

**这套流程能回答的问题只有一个：客户端拿到 200 之后，托管层（C#）有没有抛异常、抛在哪一行。**
它**不能**回答「客户端为什么决定不发第二个请求」——那是异常之后的分支问题。所以本方案的价值在于**把「猜」换成一条带类名和协程名的证据**，或者**用对照组证伪 logcat 这条路**，两者都能让项目少走一轮。

---

## 二、先纠正三个前提（查档结果）

### 2.1 「从来没在 200 之后抓过 logcat」——不准确

`report/21-手机侧执行记录.md:1469-1476` 已经有过一次覆盖 02:54–02:59 的全量 dump（10583 行 / 1.65 MB），里面**包含一次真实点击**（同节 `:1479-1483` 记了 02:56:37 / 02:56:40 / 02:56:41 三行 `I/input_interaction`）。那次结论是 `[VDIWEF]/Unity` = **0 行**。

但那次采集有四个缺陷，**不能拿来否定 logcat 路线**：

| 缺陷 | 后果 |
|---|---|
| 没有先 `logcat -c` | 窗口起点不干净，无法把「响应引起」与「启动残留」分开 |
| 没有按 pid 限定 | 关键行会被同名/同 tag 的其它进程淹没 |
| 没有对照组 | 0 行无法区分「没异常」与「日志关了」 |
| `grep -E ' E '` / 仅 `E/` 前缀 | **格式不匹配**：`-v time` 是 `E/Tag( pid):`，不是空格夹级别（`report/21:247`、`report/26:92` 已纠正） |

⇒ 本方案不是「第一次抓」，而是**第一次用「清缓冲 + 按 PID + 三组对照 + 正确 grep」抓**。

### 2.2 Unity tag 是 `Unity`，已被实证（不是猜的）

`report/21:501-503` 抓到过原始样本：

```
11-14 01:49:09.333 E/Unity (26473): NullReferenceException: Object reference not set to an instance of an object.
11-14 01:49:09.333 E/Unity (26473):   at ServerInfoDataRepository+<GetApiServerInfo>d__23.MoveNext () [0x00000]
11-14 01:49:09.333 E/Unity (26473):   at UnityEngine.SetupCoroutine.InvokeMoveNext (...) [0x00000]
```

`report/26:15-16` 记录两次独立复现，`:92` 明确更正了「Unity 一条日志都不打」的错误说法（那是 `E/` 前缀过滤造成的假象）。

⇒ **难点 2（确定 Unity tag）在查档层面已经解决**。`tagprobe.sh` 只是把它变成**每次冷启动的可验证前置**：跑一次就知道本次启动 app 有没有打过 `Unity`/`il2cpp`/`Mono` 行，避免在「logger 被关」的版本上白抓一轮。

### 2.3 SELinux 挡读 logcat——本机尚未发生

`report/20:258` 提示 ksu 域读 logcat 可能被挡；但 `report/21:102-104` 的实测是 `logcat cleared rc=0`、`logcat -d -b all` 出 8732 行。⇒ 直接读是通的，`su -c` 只作兜底（脚本自动切，`verdict.txt` 里 `LOGCAT_WRAP=su` 会标出）。

### 2.4 附：与 `report/41`（字段级排查）的口径对齐

`report/41-Account_Auth字段级排查.md` 在 03:45 后把主线改成「传输/格式层优先」，并给出 `§9.C` 的 L5 **毒化探针**（`packet` 里塞 `{"CurrentVersion":"P41-CANARY"}`，只改一个字段、必然触发 `JsonSerializationException`）。本方案与它**不冲突，且正好互补**：

| | 41 号 | 本方案 |
|---|---|---|
| 毒化/正控 | L5：类型毒化（改一个字段） | §6 L1：语法毒化（尾部加 1 字节）。**建议直接用 41 的 L5 包**，本方案只负责抓它的 logcat 侧 |
| 三信号 | `btn_px` / fresh sport / `E/Unity` 行数 | 本方案专门产出第三个信号（`TAGGED_LINES` / `tagged.txt`），且带 PID 限定与对照组 |
| 0 行怎么算 | 41 §2 用「02:54–02:59 Unity 0 行」推断「catch 住的异常不进 logcat」 | 方向可能对，但**该观测不能证明仪器可见**——catch 里不 `Debug.LogException` 才静默，catch 里打了就照样有行。本方案 §6 的正控就是给这一步补证 |

⇒ 两个报告合起来才是完整判据：**41 决定「打哪一枪」，本方案决定「这一枪有没有留下日志、以及怎么证明日志是这一枪引起的」。**

---

## 三、事实基础（判读要用到的四条）

| # | 事实 | 出处 |
|---|---|---|
| 1 | 200 → 不弹窗、无第二条协议请求（`fresh sport` 恒为 1 条） | `report/21` §36.5、§37.2（g 轮：新增 fresh sport = 1，未达 ≥2 阈值） |
| 2 | 404 → 弹「服务器处理请求失败」 | 用户实测；本方案把它当**正控** |
| 3 | **每次点击稳定触发一次新的网关请求** | `report/21:1534`（z 轮）、`:1418-1423`（t 轮 fresh sport 倒推建立时刻） |
| 4 | 该路径目前**没有崩溃/ANR/tombstone** | `report/25:57-62`、`report/26:17` |

事实 1+3 决定了方案形状：**窗口由「用户点一次」划定，点击时刻可在日志里用 `input_interaction` 复核，响应到达在点击后 50–500 ms。**

---

## 四、采集设计

### 4.1 三组，缺一不可

| 组 | 服务端 | 用户动作 | 窗口 | 作用 |
|---|---|---|---|---|
| A 基线 | 200 | 不点 | 25 s | 本底噪声；B 组里与 A 同形的行不得归因 |
| B 目标 | 200 | 点一次 | 60 s（第 15 s） | 拿到「响应之后」的托管层日志 |
| C 对照 | **404** | 点一次 | 60 s（第 15 s） | 仪器的正控：证明「会弹窗的失败」在 logcat 里长什么样 |

判据链：`B − A` = 响应引起；`C` 证明仪器可见性；三组都必须 `CLICK_SEEN>0`。

### 4.2 为什么同时留两份日志（stream + dump）

`logcat` 被 `SIGTERM` 杀掉时，**stdio 缓冲区里没 flush 的尾巴会丢**——而那条尾巴恰好就是「回包后几十毫秒」。所以脚本在 T1 时刻先做一次 `logcat -d` 全量 dump（从 logd 读，不经过 stream 进程），**再**杀 stream：

```
T1:  logcat -d -b main -b system -b crash  > buffer_dump.txt
     logcat -b crash -d                    > crash.txt
     kill -TERM <stream>
```

- `cap_raw.txt`（stream）：保证整窗完整，不会被环形缓冲覆盖；
- `buffer_dump.txt`（dump）：保证尾巴不丢，且因为 T0 已清缓冲，它**恰好就是这一窗**；
- 两者按整行去重后合成 `app_lines.txt`，分析只在这一份上做。

### 4.3 为什么多抓 events + kernel

`am_crash` / `am_anr` / `am_proc_died` **不在** main/system 里，而在 `events` 缓冲；`avc: denied` / `lowmemorykiller` 在 `kernel`。分开抓一份 `side.txt`，不污染主日志。

### 4.4 时间锚点

- 内部：`input_interaction`（system_server 打的，点击必出）
- 外部：conntrack 新 sport（`report/21:1418-1423` 的方法）
- **不需要用户报时**，也不需要在脚本里做「提醒铃」——前台执行时 `[cue]` 行要等结束才回到 PC，真正的提醒靠人开口。

### 4.5 纯 ASCII + LF

脚本注释、`echo`、路径全 ASCII；写入时强制 LF。理由写在脚本头：本项目曾因 `.sh` 里的中文注释编码问题导致服务 502 40 秒。`checklist.md` 步骤 0.3 用 `tr -cd "\r"` 逐文件验 CR=0。

---

## 五、判读矩阵（摘要）

完整版在 `kit/logcat_kit/READ.md` §2，这里只放主干：

| 看到的 | 结论 | 下一步 |
|---|---|---|
| `E Unity : NullReferenceException` + `at Xxx+<Yyy>d__N.MoveNext () [0x00000]` | 响应字段缺失/类型不符，协程第一次解引用炸 | **类名+协程名就是坐标** → 对 `report/36` 的 24 键 → 补字段 |
| `MissingFieldException` / `KeyNotFoundException` / `InvalidCastException` | schema 不匹配 | 同上，优先 `AccountDB`/`SessionKey`/`StaticOpenConditions` |
| `JsonReaderException` / `Unexpected character` | body 不是 JSON（WAF 200+HTML / gzip 截断 / packet 编码错） | 服务端看 body 与 `Content-Type` |
| `E Unity : <业务文案>`（无 Exception） | 业务分支主动失败且**愿意打日志** | 文案反查 `global-metadata.dat`，定位分支条件 |
| `E Unity : Protocol not supported` | **协议名认不出** → 外层 `protocol` 的值与请求 token 对不上，不是字段层 | 改外层 `protocol`（`report/41` §9.C 的 L1）；出处 metadata `0x0008E65A` |
| `Unity : POPUP_NETWORK_ERROR_TITLE` | 弹窗的**本地化 key**，不是文案 | 弹窗是否出现仍以截图 `btn_px` 为准；grep 不要只找中文 |
| `E Unity : UNSUPPORTED` | 枚举/状态不支持（metadata `0x000BBE54`） | 看前后 3 行定位是哪个枚举 / 版本分支 |
| 0 行，进程在，`CLICK_SEEN>0` | ①卡 await/协程；②日志被关 | **先看 C 组**：C 有行 → ①；C 也 0 行 → ② |
| 进程消失 / `am_crash` / `FATAL SIGNAL` | 崩溃 | `crash.txt` + `tomb_new.txt` |
| `am_kill` / lowmemorykiller | 系统杀的 | 不是客户端问题 |
| `avc: denied` + `logd` | SELinux 挡读 | `su -c` 兜底 → adb → 最后由 lead 决定 |
| `chatty ... expired` | 日志被折叠丢失 | `BUF=8M` 重跑 |
| 只有 `VRI` / `input_interaction` / `WindowManager` | 管道通、应用层没打 | 不能推「无异常」 |

> 上面三条文案是 `il2cpp-analyst` 解混淆后挖出的**真实字面量**（metadata 里有一层 **XOR 0x20 大小写翻转**，`pROTOCOL` → `Protocol`；此前所有关键词 grep 落空就是因为它）。`capture.sh` 的 `signals.txt` H 段与 `verdict.txt` 的 `LITERAL_HITS` 已用 `grep -i` 收编，能同时命中 `pROTOCOL not supported` 这类形态。

---

## 六、仪器可见性：0 行怎么才能算结论

`report/21:1471-1476` 的 0 行先例说明：**B 组 0 行是可能发生的**，而且它本身不证明任何事。要把它变成结论，必须先做正控。

> **lead 决定（2026-11-14 03:5x）：L5 毒化升为必做前置（G2）**。理由：C 组（404）只能证明「404 路径下仪器可见」，**证不了「200 路径下 body 进了反序列化器」**；L5 是唯一能补上这半边的包。包由 `srv-ops` 提供，本方案只负责抓 logcat 侧、跑完立刻回滚。

### L1（必做 = `report/41` §9.C 的 L5 毒化包）
- 包体：`{"protocol":"Account_Auth","packet":"{\"CurrentVersion\":\"P41-CANARY\"}"}`（`CurrentVersion` 给字符串，Newtonsoft 必抛）。
- 判读：出现 `JsonSerializationException` / `JsonReaderException` / `Unexpected character` → **仪器可见，且 200 路径下 body 确实进了反序列化器**；字段层的一切结论这时才算数。
- 没出现 → 这一层不打日志，**logcat 路线到此为止**，转 `report/38` 的 hook 路线。

### L2（备用，只证明启动路径）
- 做法：`state-api` 回 `Servers:null`，冷启动，5 s 内必出 `E/Unity NullReferenceException`（`report/26:15` 两次复现）。
- 局限：它证明的是**启动路径**日志可见，不如 L1 贴近本问题。

> L1 不做、C 组也没跑 → 结论只能写「窗口内无 Unity 输出；仪器可见性未验证」，**不得写「无异常」**。

---

## 七、交付物与自测

| 文件 | 作用 |
|---|---|
| `kit/logcat_kit/capture.sh` | 三参数采集：`capture.sh <tag> <秒> <输出>`。清缓冲 → 后台多 buffer 抓 → 到点先 dump 再停 → 自动分析出 `verdict.txt` |
| `kit/logcat_kit/tagprobe.sh` | 冷启动后一次：全系统 tag 直方图 + app PID 的 tag 直方图 + `Unity/il2cpp/mono` 命中 + log 相关 prop + 包版本 |
| `kit/logcat_kit/pull.sh` | `tar+gzip+base64` 一行回传（15 MB 日志 ≈ 500 KB） |
| `kit/logcat_kit/READ.md` | 判读表（含历史实测样本、栈怎么读、噪音白名单、反误判清单） |
| `kit/logcat_kit/checklist.md` | 给 phone-ops 的逐步命令（含推送、CR 校验、三组、L5、回传、故障分支） |
| `kit/logcat_kit/RUNBLOCK.md` | **可直接整块粘给 phone-ops 的指令块** + 最短可用路径（3 样东西）+ 两个前置 |
| `kit/logcat_kit/push_kit.ps1` | 生成 LF-only 的 `push_kit.sh`（避免 `AppendLine` 的 CRLF 把 heredoc 终止符写坏） |

`capture.sh` 产物（`<outfile>.d/`）：`meta.txt` / `marks.txt` / `cap_raw.txt` / `side.txt` / `buffer_dump.txt` / `crash.txt` / `app_lines.txt` / `tagged.txt` / `signals.txt` / `filtered.txt` / `tags.txt` / `files_new.txt` / `verdict.txt` / `done`。

**已做的自测**（本机 WSL + 桩 `logcat`，非真机）：

| 场景 | 结果 |
|---|---|
| 正常窗口 | 正常产出全部文件，`TAGGED_LINES`/`EXC_LINES`/`CLICK_SEEN` 计数正确，stream 与 dump 整行去重生效 |
| 进程不存在 | 不报错，`ALIVE_T1=0`，`HINT=process_gone` |
| 多 `-b` 被拒 | 自动降级 `-b main,system,crash` → 再降 `-b all`，`meta.txt` 记录 `capbuf` |
| 窗口内 PID 消失 | `PID_GONE_AT` 写入 `marks.txt`，`PID_CHANGED=1` |
| 三条真实文案 | `signals.txt` H 段命中 `Protocol not supported` / `POPUP_NETWORK_ERROR_TITLE`，`LITERAL_HITS=2`，`HINT` 优先指向 H 段 |
| 推送 wrapper | 3 个 `.sh` 经 heredoc 落盘后 **sha256 与原文件完全一致**、`CR=0`、`sh -n` 通过；`push_kit.ps1` 从任意 cwd 生成结果 CR=0 |

> 过程中修掉一个真 bug：`tagprobe.sh` 最初漏了 `-d`，在真机上会**永久阻塞**（`logcat` 不带 `-d` 不会退出）。已修并加多 buffer 探测与 `su -c` 兜底。

> 真机未验证项：`logcat -b main -b system -b crash` 在本机是否被接受（脚本有降级）、`dumpsys activity exit-info` 是否可用（失败即忽略）、`find -newer` 在 `/data/data` 的耗时（已限 `maxdepth 5`）。

---

## 八、执行 runbook

见 `kit/logcat_kit/RUNBLOCK.md`（可直接粘贴）与 `kit/logcat_kit/checklist.md`（详细版）：

0. 推送 + CR/语法校验（`push_kit.ps1` + 2 条命令）
1. 冷启动 + 记 PID/启动 ticks/uptime + `tagprobe`（闸门：`UNITY_TAG_SEEN`）
2. **A 组**（25 s，不点）——时间紧可砍
3. **B 组**（60 s，第 15 s 由**用户手动**点；`CLICK_SEEN` 必须 >0）
4. **C 组**（同上，服务端 404；lead 协调 `srv-ops` 在采集前 30 s 切、采完切回）
4A. **L5 毒化**（服务端 200 + `packet={"CurrentVersion":"P41-CANARY"}`；必做，优先级高于 A 组）
5. 回传 + 解包
6. 回报（6 行）

**前置（由 lead 确认，phone-ops 不得自判）**：G1 服务端 `exp` = 200/404；G2 L5 已上线。

**红线**：不自动点屏；不碰服务端与 WAF；**不 `setenforce 0`（lead 已明确不允许）**；单连接；不改 `report/` 已有文件。

---

## 九、拿到结果后的分叉（下一步找谁）

```
B 组有 E/Unity + 栈里有 MoveNext
├─ 类/方法与 Account_Auth 响应字段对得上 → 补字段（il2cpp-analyst / 36 号报告的 24 键）
└─ 对不上（UI/资源/本地化/网络层）      → 说明异常不在响应解析，回 state/prefs 与 catalog 线
B 组有 E/Unity，只有业务文案没有栈
└─ 文案反查 metadata → 该文案的调用点条件 → 改响应使其不满足
B 组 0 行，C 组有行
└─ 200 路径静默：被 try/catch 吞 或 await 卡住 → 内存扫描 / hook（report/38 的 TLS 层优先）
B 组 0 行，C 组也 0 行
└─ 仪器哑 → L1 灯泡 → 仍哑 → 放弃 logcat，转 Frida/TLS hook 或内存扫描
B 组进程消失
└─ crash.txt / tombstone → native 线
```

---

## 十、本方案明确不做的事

| 不做 | 原因 |
|---|---|
| 自动点击 / 注入 touch | 用户明确要求所有点屏由本人完成；`sendevent` 命中不稳定 |
| 改网关 / 改 WAF / 改返回码 | 不在本角色职责内；C 组由 lead 协调 `srv-ops` 切 |
| `setenforce 0` | **lead 已明确不允许**（与 WAF 同类「改错可能回不去」的系统状态风险）；只走 `su -c` / adb 兜底，全哑了再由用户决定 |
| 把 `filtered.txt` 当证据 | 它按噪音表删过东西；证据只认 `cap_raw.txt` / `buffer_dump.txt` |
| 在 `report/` 已有文件里改结论 | 本轮只新增本文件与 `kit/` |

---

## 十一、查档清单（本方案直接复用，未自造）

| 复用内容 | 出处 |
|---|---|
| Unity tag = `Unity`、NRE 原文、栈格式 | `report/21-手机侧执行记录.md:501-503` |
| 「Unity 不打日志」是误判（`E/` 前缀） | `report/26-进度-NRE已修-卡点后移.md:92` |
| ksu 域 `logcat -c` / `-d -b all` 可用 | `report/21:102-104` |
| `-s` 用法坑、`grep -E ' E '` 格式坑 | `report/21:246-247` |
| 窗口内 Unity 0 行的先例（02:54–02:59） | `report/21:1469-1476` |
| 点击 → 新连接 / fresh sport 判据 | `report/21:1418-1423`、`report/21:1534` |
| 噪音白名单 | `report/29:78-87`、`report/21:52-62,183-187` |
| crash buffer / tombstone 抓法、FORTIFY 噪音 | `report/06:39,107-110,217-228,420` |
| 无崩溃/ANR 的历史观测 | `report/25:57-62` |
| logcat 一击定位、SELinux 备注 | `report/20:246-258` |
| 24 键响应清单（补字段方向） | `report/36-Account_Auth响应字段清单.md:22-53` |
| il2cpp 无导出 → TLS hook 降级路线 | `report/38-Frida部署清单.md:165-205` |
| 字段级排查与 L5 毒化探针（本方案 §6 的等价正控） | `report/41-Account_Auth字段级排查.md` §0.6、§9.C |
| 三条真实错误文案 + XOR 0x20 大小写翻转 | `il2cpp-analyst` 2026-11-14 03:5x 转达：`0x0008E65A` / `0x0008A25A` / `0x000BBE54` |
| 崩溃后「自退出」不是崩溃 | `report/21:49` |

---

## 十二、一句话给 lead

**先抓的不是「第二个协议请求」，而是「点击后 3 秒内第一条来自 app PID 的 `Unity` tag 日志」**——它带类名与协程名，是唯一能把「猜字段」变成「补字段」的证据；若这条是 `Protocol not supported`，则卡点根本不在字段层而在外层 `protocol` 值。抓不到时，C 组（404）与 L5 毒化包负责证明这是「真的没异常」还是「仪器是哑的」。
