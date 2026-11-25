# logcat 取证 · 执行清单（给 phone-ops）

> 你只执行 + 取证，不做方案判断。每一步都是**一条命令**，照抄即可。
> 判读在 `kit/logcat_kit/READ.md`，不要在这里下结论。
> 工作目录：`C:\Users\su\Desktop\大肥鱼项目\BAServer`（所有 `python ...` 都在这里跑）
>
> **时间紧就别读这份**：直接用 `kit/logcat_kit/RUNBLOCK.md` 里「══ 指令块 ══」之间那段，整块粘过来即可。

---

## 红线（违反任何一条，本轮数据作废）

1. **不要自动点屏幕。** 所有「点击」都由**用户手动完成**。你只负责：开抓 → 口头告诉用户什么时候点 → 等。
2. **不要改服务端**（返回码、body、WAF 都不归你）。C 组的 404 由 lead 切换，你只记录「lead 说是 404」。
3. **不要 `setenforce 0`。** 脚本读不到日志时先按 §故障分支 处理，是否关 SELinux 由 lead 决定。
4. **不要碰宝塔 WAF / 防火墙。**
5. **不要改 `report/` 下任何已有文件。** 只往 `/sdcard/lc/` 写。
6. **同一时刻只开一条 `rsh.py` 连接**（`nc -e sh` 是单连接）。
7. 每一步都要保留输出：`rsh.py` 的终端输出请原样贴回给 lead。

---

## 步骤 0 · 推送取证包（一次性）

### 0.1 生成推送脚本（PC）

```powershell
$files='capture.sh','tagprobe.sh','pull.sh'; $sb=New-Object Text.StringBuilder; $sb.Append("mkdir -p /sdcard/lc /sdcard/logcat_kit`n"); foreach($f in $files){ $b=((Get-Content "kit\logcat_kit\$f" -Raw) -replace "`r`n","`n") -replace "`r",""; if(-not $b.EndsWith("`n")){ $b += "`n" }; $sb.Append("cat > /sdcard/logcat_kit/$f <<'LC_EOF'`n"); $sb.Append($b); $sb.Append("LC_EOF`n") }; [IO.File]::WriteAllText("$PWD\push_kit.sh",$sb.ToString()); "push_kit.sh bytes=$((Get-Item push_kit.sh).Length)"
```

预期：`push_kit.sh bytes=` 在 18000–26000 之间。若小很多 → `kit\logcat_kit\` 里的脚本不全，停下回报。

> 只推 3 个 `.sh`；`READ.md` / `checklist.md` 在 PC 上读即可（推到手机上还会踩 PowerShell 5.1 的 UTF-8 读取坑）。
> 这一行里所有换行都用 `` `n ``（LF）显式拼出，**不要**改成 `AppendLine`：Windows 的 `AppendLine` 会写 CRLF，heredoc 终止符变成 `LC_EOF\r`，推送会卡死或写出带 CR 的文件名。

### 0.2 推送（PC）

```powershell
python report\_tmp\rsh.py --file push_kit.sh
```

预期：最后打印 `<<< N bytes -> last_out.txt >>>`，`N` 很小（正常只有几十字节）。**若有 `syntax error` / `unexpected` 字样 → 停下回报。**

### 0.3 校验（PC）

```powershell
python report\_tmp\rsh.py 'cd /sdcard/logcat_kit; ls -l; for f in capture.sh tagprobe.sh pull.sh; do n=$(tr -cd "\r" < $f | wc -c); echo "$f CR=$n"; done'
```

预期：3 个文件的 `CR=0`（**任何一个不为 0 就是 Windows 换行混进去了，必须重推**）。

```powershell
python report\_tmp\rsh.py 'cd /sdcard/logcat_kit; sh -n capture.sh && echo SYNTAX_CAPTURE_OK; sh -n tagprobe.sh && echo SYNTAX_TAGPROBE_OK; sh -n pull.sh && echo SYNTAX_PULL_OK'
```

预期：三行 `..._OK`。

---

## 步骤 1 · 冷启动 + 确认进程 + 确认 Unity tag

### 1.1 杀干净并冷启动（PC）

```powershell
python report\_tmp\rsh.py 'for p in $(pidof com.RoamingStar.BlueArchive); do kill -9 $p; done; sleep 2; ps -A | grep -c BlueArchive; monkey -p com.RoamingStar.BlueArchive -c android.intent.category.LAUNCHER 1'
```

预期：`ps -A | grep -c` 打印 `0`，monkey 打印 `Events injected: 1`。

> 注意：`am force-stop` 在本机必失败（`Failed transaction`），这是已知现象，用上面的 `kill -9` 即可。

### 1.2 等 25 秒，然后记录 PID 与启动时间（PC）

```powershell
python report\_tmp\rsh.py 'sleep 25; P=$(pidof com.RoamingStar.BlueArchive); echo PID=$P; sed "s/^.*) //" /proc/$P/stat | awk "{print \"START_TICKS=\" \$20}"; echo -n "UPTIME="; cat /proc/uptime; date "+DEVICE_EPOCH=%s"; grep -E "^(Name|State|PPid|Threads|VmRSS)" /proc/$P/status'
```

预期：`PID=` 是一个数字（主进程，`pushcore` 不会出现在这里）；`START_TICKS=` 是 4–7 位数字；`UPTIME=` 比 `START_TICKS/100` 大。**把这四行抄进 §记录表。**

> 如果 `PID=` 为空 → 进程没起来，回 1.1；连续两次为空 → 停下回报（可能又进了崩溃循环）。

### 1.3 确认 Unity 日志 tag（PC）

```powershell
python report\_tmp\rsh.py 'sh /sdcard/logcat_kit/tagprobe.sh /sdcard/lc/tagprobe_1.txt; echo TAGPROBE_RC=$?'
```

预期：末尾打印 `TAGPROBE_DONE`，并给出 `pids / app_lines / unity_hits / UNITY_TAG_SEEN=`。

**这一步是闸门：**

| 看到 | 含义 | 动作 |
|---|---|---|
| `UNITY_TAG_SEEN=1` | 本次启动确实打了 `Unity` tag 的日志 | 继续步骤 2 |
| `UNITY_TAG_SEEN=0` 但 `app_lines` 很大、`top tags` 里有别的自研 tag | Unity 日志在本包里被关掉了 | **停下回报 lead**，问是否先做 READ.md §5 的 L1 灯泡测试；不要直接往下抓 |
| `pids` 为空 | 进程不在了 | 回 1.1 |

---

## 步骤 2 · A 组（基线：200 + 不点）

### 2.1 截一张当前画面（PC）

```powershell
python report\_tmp\rsh.py 'screencap -p /sdcard/lc/A_idle.png; ls -l /sdcard/lc/A_idle.png'
```

预期：文件 1–4 MB。**你要看到标题页**（`Ver : 3.0.2_73`、「点击任意区域进入游戏」）。看不到标题页 → 回 1.1 重新冷启动。

### 2.2 开抓 25 秒（PC）

```powershell
python report\_tmp\rsh.py 'sh /sdcard/logcat_kit/capture.sh Unity 25 /sdcard/lc/A_idle.txt'
```

**这 25 秒里不要做任何事，也不要让用户点。** 前台执行会等约 30 秒才返回，属正常。

### 2.3 记录判据（PC）

```powershell
python report\_tmp\rsh.py 'grep -E "^(PID_T0|ALIVE_T1|CLICK_SEEN|TAGGED_LINES|CAP_LINES|CHATTY|HINT)=" /sdcard/lc/A_idle.txt.d/verdict.txt'
```

预期：`CLICK_SEEN=0`、`TAGGED_LINES=0`、`ALIVE_T1=1`。这组是「没有请求时的底噪」，0 行是**正常的**。

---

## 前置闸门（在步骤 3 之前必须满足；缺一不开抓）

| 编号 | 前置 | 谁给 | 你要看到什么 |
|---|---|---|---|
| **G1** | 服务端 `exp` 已切到目标值 | lead 协调 `srv-ops`（采集窗口前 30 秒切、采完切回） | lead 消息里出现「B 组 200 已确认」/「C 组 404 已确认」 |
| **G2** | L5 毒化包已上线（若做 L5） | lead 让 `srv-ops` 提供 `packet = {"CurrentVersion":"P41-CANARY"}` | lead 消息里出现「L5 已上线」 |

**不要自己用 curl 猜服务端状态。** 没看到对应确认句 → 停，回一句「缺前置 Gn」。

> C 组 404 的切换由 lead 控制时间点：冷启动本身约 27 秒，正好覆盖「提前 30 秒切」的窗口。

---

## 步骤 3 · B 组（目标：200 + 手动点一次）

### 3.1 确认服务端是 200（口头，不问手机）

向 lead 确认：**网关当前对 `/api/account/auth` 回 200**。把 lead 的原话抄进记录表 `服务端=` 一栏。

### 3.2 冷启动（PC）

```powershell
python report\_tmp\rsh.py 'for p in $(pidof com.RoamingStar.BlueArchive); do kill -9 $p; done; sleep 2; monkey -p com.RoamingStar.BlueArchive -c android.intent.category.LAUNCHER 1; sleep 25; screencap -p /sdcard/lc/B_before.png; echo READY'
```

预期：`READY`。**你看一眼 `B_before.png`：必须是标题页 +「点击任意区域进入游戏」**。

### 3.3 先跟用户说好，再开抓

对用户说：

> 「我按下去之后大约 15 秒，你点一下屏幕中间的『点击任意区域进入游戏』。就点一次。」

**然后**执行（PC）：

```powershell
python report\_tmp\rsh.py 'sh /sdcard/logcat_kit/capture.sh Unity 60 /sdcard/lc/B_200.txt'
```

- 命令会阻塞约 65 秒，**这期间不要开第二条 rsh 连接**。
- 脚本内部会在第 15 秒记一条 `CUE`（写进 `marks.txt`）。但**前台执行时 PC 端要等结束才收到输出**，所以你不要盯着终端等提示——**提醒由你用嘴说**（就是 3.3 开头那句话）。
- 到第 15 秒左右，**由用户手动点**。你**不要**用任何脚本 / `input tap` / `sendevent` 代点（本机注入被拦，且这是红线）。
- 用户点完不用报时间，日志里有 `input_interaction` 会自动标出。

### 3.4 抓完立刻截一张（PC）

```powershell
python report\_tmp\rsh.py 'screencap -p /sdcard/lc/B_after.png; grep -E "^(PID_T0|PID_T1|ALIVE_T1|PID_CHANGED|CLICK_SEEN|TAGGED_LINES|EXC_LINES|CAP_LINES|DUMP_LINES|CHATTY|HINT)=" /sdcard/lc/B_200.txt.d/verdict.txt'
```

**硬判据：`CLICK_SEEN` 必须 >0。** 若 `CLICK_SEEN=0` → 用户没点在窗口里（或点太早/太晚），**本组作废，重跑 3.2–3.4**。不要拿 `CLICK_SEEN=0` 的数据去分析。

把 `B_after.png` 的画面用一句话记进记录表（`无弹窗` / `有弹窗` / `黑屏`…）。

---

## 步骤 4 · C 组（对照：404 + 手动点一次）

### 4.1 确认服务端已切 404

向 lead 确认：**网关现在对 `/api/account/auth` 回 404**（客户端应弹「服务器处理请求失败」）。记下 lead 原话。

> 若 lead 无法切 404：跳过 C 组，改做 `READ.md` §5 的 **L1 灯泡测试**（网关在 `packet` JSON 末尾加 1 字节 `X`，跑完立刻回滚），并在记录表写明「C 组替换为 L1」。

### 4.2 冷启动（PC）

```powershell
python report\_tmp\rsh.py 'for p in $(pidof com.RoamingStar.BlueArchive); do kill -9 $p; done; sleep 2; monkey -p com.RoamingStar.BlueArchive -c android.intent.category.LAUNCHER 1; sleep 25; screencap -p /sdcard/lc/C_before.png; echo READY'
```

### 4.3 同 3.3 的口头提示，然后开抓

```powershell
python report\_tmp\rsh.py 'sh /sdcard/logcat_kit/capture.sh Unity 60 /sdcard/lc/C_404.txt'
```

点击**仍由用户手动完成**，规则同 3.3。

### 4.4 抓完截图 + 判据（PC）

```powershell
python report\_tmp\rsh.py 'screencap -p /sdcard/lc/C_after.png; grep -E "^(ALIVE_T1|CLICK_SEEN|TAGGED_LINES|EXC_LINES|CHATTY|HINT)=" /sdcard/lc/C_404.txt.d/verdict.txt'
```

`CLICK_SEEN` 同样必须 >0，否则重跑。
记下 `C_after.png` 画面：**这一组预期是「有弹窗」**（用来证明「会弹窗的失败」长什么样）。

---

## 步骤 4A · L5 毒化（仅在 lead 说「L5 已上线」后做；优先级高于 A 组）

> 为什么必须有这一组：C 组（404）只能证明「404 路径下仪器可见」，证明不了「200 路径下 body 进了反序列化器」。
> L5 的包 `{"CurrentVersion":"P41-CANARY"}` 只要被 Newtonsoft 解析就必抛，是唯一能补上这半边的正控。**跑完立刻让 srv-ops 回滚。**

### 4A.1 冷启动

```powershell
python report\_tmp\rsh.py 'for p in $(pidof com.RoamingStar.BlueArchive); do kill -9 $p; done; sleep 2; monkey -p com.RoamingStar.BlueArchive -c android.intent.category.LAUNCHER 1; sleep 25; screencap -p /sdcard/lc/L5_before.png; echo READY'
```

### 4A.2 开抓（用户手动点一次）

```powershell
python report\_tmp\rsh.py 'sh /sdcard/logcat_kit/capture.sh Unity 60 /sdcard/lc/B_L5.txt'
```

### 4A.3 截图 + 判据

```powershell
python report\_tmp\rsh.py 'screencap -p /sdcard/lc/L5_after.png; grep -E "^(CLICK_SEEN|TAGGED_LINES|EXC_LINES|LITERAL_HITS|CHATTY|HINT)=" /sdcard/lc/B_L5.txt.d/verdict.txt'
```

判读：出现 `JsonSerializationException` / `JsonReaderException` / `Unexpected character` ⇒ **200 路径下 body 确实进了反序列化器**（仪器可见，字段层的结论才算数）；一条都没有 ⇒ 仪器对 200 路径是哑的，logcat 路线到此为止。

---

## 步骤 5 · 全部拉回电脑

```powershell
python report\_tmp\rsh.py --out lc.b64 'sh /sdcard/logcat_kit/pull.sh /sdcard/lc; echo PULL_DONE'
```

预期：终端出现 `PULL_DONE`，`lc.b64` 大小 0.5–5 MB。

```powershell
[IO.File]::WriteAllBytes("$PWD\lc.tgz",[Convert]::FromBase64String(((Get-Content .\lc.b64 -Raw) -replace '\s',''))); tar -xzf .\lc.tgz; Get-ChildItem -Recurse .\sdcard\lc | Select-Object FullName,Length
```

预期：解出 `.\sdcard\lc\`，里面有 `A_idle.txt.d`、`B_200.txt.d`、`C_404.txt.d`、`tagprobe_1.txt`、三张 PNG。

> 若 `lc.b64` 只有几 KB 或解码报 `FormatException`：改成分目录拉：
> `python report\_tmp\rsh.py --out b.b64 'sh /sdcard/logcat_kit/pull.sh /sdcard/lc/B_200.txt.d'`

---

## 步骤 6 · 记录表 + 回报

填完这张表，连同 §5 的解包结果一起交给 lead：

| 项 | A 组（不点） | B 组（200） | C 组（404） |
|---|---|---|---|
| 服务端返回 | 200 | 200 | 404（或 L1） |
| 冷启动时间 |  |  |  |
| PID / START_EPOCH |  |  |  |
| 用户点击时刻（用户口述） | 无 |  |  |
| `CLICK_SEEN` |  |  |  |
| `TAGGED_LINES` |  |  |  |
| `EXC_LINES` |  |  |  |
| `PID_CHANGED` / `ALIVE_T1` |  |  |  |
| `CHATTY` |  |  |  |
| 抓完屏幕（截图文件名） |  |  |  |
| 异常/失败现象 |  |  |  |

回报给 lead 时请包含：

1. 上表；
2. `tagprobe_1.txt` 的 `UNITY_TAG_SEEN / app_lines / top tags` 三行；
3. B 组 `verdict.txt` 全文（40 行以内）；
4. 一句话：B 组到底有没有 `Unity` 行。

---

## 故障分支（照这个顺序，不要自由发挥）

| 现象 | 处理 |
|---|---|
| `capture.sh: not found` | 步骤 0 没推成功；重跑 0.1–0.3 |
| `capture.sh: syntax error` | CRLF 混入；0.3 的 `CR=` 检查会暴露，重推 |
| `[!] cannot create ...` | `mkdir -p /sdcard/lc` 后重跑 |
| `verdict.txt` 里 `ACCESS_RC` 非 0 | 把 `meta.txt` 全文发回；不要自己 `setenforce 0` |
| `CHATTY` >0 | 用 `BUF=8M` 重跑该组（`python report\_tmp\rsh.py 'BUF=8M sh /sdcard/logcat_kit/capture.sh Unity 60 /sdcard/lc/B_200.txt'`），并在记录表注明 |
| `CLICK_SEEN=0` | 该组作废，重跑；先确认用户点的时候屏幕上确实有「点击任意区域进入游戏」 |
| 点完 App 直接退回桌面 | 立刻 `python report\_tmp\rsh.py 'sh /sdcard/logcat_kit/pull.sh /sdcard/lc'` 留证，然后回报（这本身是重要现象） |
| rsh 连接超时/断开 | 重连后先 `pidof`，再决定是否重跑该组；**不要**在半截数据上继续 |
| 画面停在弹窗、无法开始下一组 | 回步骤 1.1 冷启动（`kill -9`） |

---

## 附：为什么脚本要「先开抓再点」

`report/21-手机侧执行记录.md:1471-1476` 有一次事后 `logcat -d` 全量 dump（10583 行，含一次点击），`[VDIWEF]/Unity` = 0 行。原因不是「没有异常」，而是那次采集**没有清缓冲、没有按 PID 限定、没有对照组、且 grep 用了 `E/` 前缀**（`report/26:92` 已纠正）。本清单的每一步都是为了消掉这四个缺陷——尤其是「清缓冲 + 先开抓 + 手动点 + 三组对照」。
