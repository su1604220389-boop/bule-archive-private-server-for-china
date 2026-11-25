# RUNBLOCK — 可直接粘给 phone-ops 的指令块

> 用途：lead 把下面「══ 指令块 ══」之间的内容**整块复制**进给 `phone-ops` 的 message。
> 设计原则：不要求 phone-ops 读 40 号报告或 READ.md，贴进去就能跑；所有需要人判断的地方都写成「停，回报」。
> 生成时间：2026-11-14 03:5x。命令与 `kit/logcat_kit/checklist.md` 同源，但已压平为一屏可执行的序列。

---

## 最短可用路径（时间紧，只抓这 3 样也够判）

| # | 抓什么 | 在哪 | 为什么这 3 样就够 |
|---|---|---|---|
| 1 | **B 组 `tagged.txt`**（0 行也是结论） | `B_200.txt.d/tagged.txt` | 唯一能给出「类名+协程名」的证据；有 `E Unity` + `at Xxx+<Yyy>d__N.MoveNext` 就能直接定位要补的字段 |
| 2 | **C 组的 `TAGGED_LINES` + 两组 `CLICK_SEEN`** | `C_404.txt.d/verdict.txt`、`B_200.txt.d/verdict.txt` | 区分「真没异常」与「仪器哑」；`CLICK_SEEN=0` 的组必须作废，否则会把「没点到」读成「没响应」 |
| 3 | **`tagprobe_1.txt` 的 `UNITY_TAG_SEEN=` 行** | `/sdcard/lc/tagprobe_1.txt` | 仪器自检：这次冷启动到底有没有打过 `Unity` tag；=0 时后面所有 0 行都不算证据 |

**可以砍的**：A 组基线（25 s，不点）——它只用于「B 组某行是不是本底噪声」的追认，时间紧时优先保 B/C/L5。
**不要砍的**：`tagprobe`（10 秒）、B 组、C 组。
**L5 一旦 lead 说上线了，优先级高于 A 组**：它是唯一能证明「200 路径下 body 真的进了反序列化器」的包。

---

## 本轮开始前必须由 lead 确认的两个前置（缺一不开抓）

| 编号 | 前置 | 谁提供 | 判定 |
|---|---|---|---|
| **G1** | 服务器 `exp` = **目标值**：B 组 = `200`（当前 `cn_envelope` + `code=200`）；C 组 = `404`（`decrypt+plain+http404`，只改 exp 文件、不重启进程） | lead 协调 `srv-ops`，**在采集窗口开始前 30 秒**切，采完立刻切回 | lead 消息里必须出现「B 组 200 已确认」/「C 组 404 已确认」 |
| **G2** | 若做 L5：**毒化包已上线** —— `packet` = `{"CurrentVersion":"P41-CANARY"}`（`CurrentVersion` 给字符串，Newtonsoft 必抛） | lead 让 `srv-ops` 在服务器侧提供 | lead 消息里必须出现「L5 已上线」 |

> **phone-ops 不许自己判断服务端状态**，也不许用 curl 去猜。没看到对应的确认句 → 停，回一句「缺前置 Gn」。
> C 组的 404 切换时机由 lead 控制；冷启动本身约 27 秒，正好覆盖「提前 30 秒切」。

---

## 需要回报的 grep 清单（本轮新增三条真实文案）

`il2cpp-analyst` 发现 metadata 有 **XOR 0x20 大小写翻转**（`pROTOCOL` → `Protocol`），解混淆后挖出真实错误文案。这三条已并入 `capture.sh` 的 `signals.txt` H 段与 `verdict.txt` 的 `LITERAL_HITS`：

| 文案 | 含义 | 判读 |
|---|---|---|
| `Protocol not supported`（`0x0008E65A`） | 协议名认不出 | **出现在 200 之后 ⇒ 客户端认不出响应外层 `protocol` 的值** |
| `POPUP_NETWORK_ERROR_TITLE`（`0x0008A25A`） | 弹窗的**本地化 key**，不是文案 | 弹窗文案走 i18n；grep 别只找中文，也别指望看到这句中文 |
| `UNSUPPORTED`（`0x000BBE54`） | 枚举/状态不支持 | 看前后 3 行确定是哪个枚举 |

因存在大小写翻转，脚本用 `grep -i`，能同时命中 `pROTOCOL not supported` 这类形态。

---

══ 指令块（从这里整块复制）══

```
【任务】logcat 取证：一次手动点击窗口（BA 国服 3.0.2，包名 com.RoamingStar.BlueArchive）
【角色】只执行、只回报，不做方案判断。所有屏幕点击由用户手动完成。
【红线】① 绝不自动点屏（不用 input tap / sendevent / monkey 点按钮）；
        ② 不碰服务端、不碰宝塔 WAF、不 setenforce；
        ③ 同一时刻只开一条 rsh 连接；
        ④ 只写 /sdcard/lc/，不改 report/ 下任何文件。
【分母】PC 工作目录固定为 C:\Users\su\Desktop\大肥鱼项目\BAServer ，所有 python 命令都在这里跑。

====== 前置闸门：没有 lead 的确认句就停 ======
G1  B 组 = 200        → lead 须说「B 组 200 已确认」
G2  C 组 = 404        → lead 须说「C 组 404 已确认」（srv-ops 提前 30s 切，采完切回）
G3  L5 毒化 = 上线    → lead 须说「L5 已上线」（packet = {"CurrentVersion":"P41-CANARY"}）
缺哪条就停，回 lead：「缺前置 Gn，等待确认」。禁止自己用 curl 猜服务端状态。

====== 步骤 0：推送（一次性，约 20 秒） ======
powershell -ExecutionPolicy Bypass -File kit\logcat_kit\push_kit.ps1
python report\_tmp\rsh.py --file push_kit.sh
python report\_tmp\rsh.py 'cd /sdcard/logcat_kit; for f in capture.sh tagprobe.sh pull.sh; do n=$(tr -cd "\r" < $f | wc -c); echo "$f CR=$n"; done; sh -n capture.sh && sh -n tagprobe.sh && sh -n pull.sh && echo SYNTAX_OK'
预期：三行 CR=0 + SYNTAX_OK。任一行 CR 不为 0 或没有 SYNTAX_OK → 停，回 lead「推送校验失败」。

====== 步骤 1：冷启动 + 记录 PID + 仪器自检（约 35 秒） ======
python report\_tmp\rsh.py 'for p in $(pidof com.RoamingStar.BlueArchive); do kill -9 $p; done; sleep 2; monkey -p com.RoamingStar.BlueArchive -c android.intent.category.LAUNCHER 1; sleep 25; P=$(pidof com.RoamingStar.BlueArchive); echo PID=$P; sed "s/^.*) //" /proc/$P/stat | awk "{print \"START_TICKS=\" \$20}"; echo -n "UPTIME="; cat /proc/uptime; date "+DEVICE_EPOCH=%s"'
预期：PID= 一个数字。为空 → 重跑一次；连续两次为空 → 停，回报。

python report\_tmp\rsh.py 'sh /sdcard/logcat_kit/tagprobe.sh /sdcard/lc/tagprobe_1.txt; echo TAGPROBE_RC=$?'
预期：末行 TAGPROBE_DONE，且 UNITY_TAG_SEEN=1。
      UNITY_TAG_SEEN=0 → 停，把 tagprobe_1.txt 的前 30 行发回 lead
      （说明这次启动没打过 Unity tag，后面 0 行都不算证据）。

====== 步骤 2：B 组（服务端 200，用户手动点一次） ======
先对用户说：「我按下去大约 15 秒，你点一下屏幕中间的『点击任意区域进入游戏』，只点一次。」
python report\_tmp\rsh.py 'for p in $(pidof com.RoamingStar.BlueArchive); do kill -9 $p; done; sleep 2; monkey -p com.RoamingStar.BlueArchive -c android.intent.category.LAUNCHER 1; sleep 25; screencap -p /sdcard/lc/B_before.png; echo READY'
预期：READY。看一眼画面必须是标题页 +「点击任意区域进入游戏」；不是 → 重跑本步。

python report\_tmp\rsh.py 'sh /sdcard/logcat_kit/capture.sh Unity 60 /sdcard/lc/B_200.txt'
说明：阻塞约 65 秒；第 15 秒左右由【用户手动点击】，你绝不代点。
      PC 端要等命令结束才看到输出，所以提醒靠你开口，不要等终端提示。

python report\_tmp\rsh.py 'screencap -p /sdcard/lc/B_after.png; grep -E "^(PID_T0|ALIVE_T1|PID_CHANGED|CLICK_SEEN|TAGGED_LINES|EXC_LINES|LITERAL_HITS|CHATTY|HINT)=" /sdcard/lc/B_200.txt.d/verdict.txt'
硬判据：CLICK_SEEN 必须 > 0。=0 → 本组作废，重跑步骤 2（先确认用户点的时候屏幕上有那行字）。

====== 步骤 3：C 组（服务端 404，用户手动点一次） ======
只在 G2 已确认后执行。
python report\_tmp\rsh.py 'for p in $(pidof com.RoamingStar.BlueArchive); do kill -9 $p; done; sleep 2; monkey -p com.RoamingStar.BlueArchive -c android.intent.category.LAUNCHER 1; sleep 25; screencap -p /sdcard/lc/C_before.png; echo READY'

python report\_tmp\rsh.py 'sh /sdcard/logcat_kit/capture.sh Unity 60 /sdcard/lc/C_404.txt'
说明：同样由【用户手动点击】。

python report\_tmp\rsh.py 'screencap -p /sdcard/lc/C_after.png; grep -E "^(ALIVE_T1|CLICK_SEEN|TAGGED_LINES|EXC_LINES|LITERAL_HITS|CHATTY|HINT)=" /sdcard/lc/C_404.txt.d/verdict.txt'
预期：C_after 有弹窗（这是对照组的意义）。CLICK_SEEN 同样必须 > 0。

====== 步骤 4：L5 毒化（仅在 G3 已确认后执行，优先级高于 A 组） ======
python report\_tmp\rsh.py 'for p in $(pidof com.RoamingStar.BlueArchive); do kill -9 $p; done; sleep 2; monkey -p com.RoamingStar.BlueArchive -c android.intent.category.LAUNCHER 1; sleep 25; screencap -p /sdcard/lc/L5_before.png; echo READY'

python report\_tmp\rsh.py 'sh /sdcard/logcat_kit/capture.sh Unity 60 /sdcard/lc/B_L5.txt'
说明：同样由【用户手动点击】。这一包只在被反序列化时才会炸。

python report\_tmp\rsh.py 'screencap -p /sdcard/lc/L5_after.png; grep -E "^(CLICK_SEEN|TAGGED_LINES|EXC_LINES|LITERAL_HITS|HINT)=" /sdcard/lc/B_L5.txt.d/verdict.txt'

====== 步骤 5：回传（只一次） ======
python report\_tmp\rsh.py --out lc.b64 'sh /sdcard/logcat_kit/pull.sh /sdcard/lc; echo PULL_DONE'
预期：终端出现 PULL_DONE，lc.b64 大小 0.3–5 MB。

[IO.File]::WriteAllBytes("$PWD\lc.tgz",[Convert]::FromBase64String(((Get-Content .\lc.b64 -Raw) -replace '\s',''))); tar -xzf .\lc.tgz; Get-ChildItem -Recurse .\sdcard\lc | Select-Object FullName,Length
预期：解出 .\sdcard\lc\ 下的 *.txt.d 目录与 5 张 PNG。

====== 步骤 6：回报格式（严格照抄这 6 行，不要贴全文） ======
TAGPROBE  UNITY_TAG_SEEN=?
B_200     CLICK_SEEN=? TAGGED_LINES=? ALIVE_T1=? HINT=?
C_404     CLICK_SEEN=? TAGGED_LINES=?
L5        CLICK_SEEN=? TAGGED_LINES=? LITERAL_HITS=?      （没做就写 SKIP）
B_200 tagged.txt 前 10 行（0 行就写 EMPTY）
屏幕：B_after 有无弹窗 / C_after 有无弹窗（各一句话）

====== 出错时（只这 4 条，不要自由发挥） ======
capture.sh: not found / syntax error  → 回步骤 0 重推；CR != 0 必须重推
ACCESS_RC 非 0 或 tagprobe raw_lines=0 → 停，把 meta.txt 全文发回（不要 setenforce）
CHATTY > 0 → 用 BUF=8M 重跑该组：python report\_tmp\rsh.py 'BUF=8M sh /sdcard/logcat_kit/capture.sh Unity 60 /sdcard/lc/B_200.txt'
点完 App 退回桌面 → 先回传再回报（这本身是重要现象）
```

══ 指令块结束 ══

---

## 给 lead 的三行摘要（可直接转给 srv-ops）

1. B 组前后服务器必须是 `exp = 200`；C 组**采集窗口开始前 30 秒**切 `exp = 404`（`decrypt+plain+http404`），采完立刻切回。
2. L5 组服务器是 `200` + `packet = {"CurrentVersion":"P41-CANARY"}`。
3. 三组之间**不要重启服务进程**（只换 exp 文件），否则「同一次冷启动」这个前提会破。
