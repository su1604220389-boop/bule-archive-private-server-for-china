# 黑屏取证报告 — 任务界面右上角「大厅」按钮 → 全屏黑屏

- 取证者：srv-ops
- 时间：2026-11-17 19:35–19:36（北京时间 UTC+8）
- 窗口：**2026-11-17 19:31:33 ~ 19:33:30**
- 只读取证；唯一新增物是 `/root/ba_watch/`（本次新建），一键撤除命令见 §D。

---

## 0. 已完成事实（Lead 已核，不重复验证）

| # | 事实 |
|---|---|
| 1 | 黑屏落在 19:31:33–19:33:30 窗口内 |
| 2 | 桥进程存活：pid **2617833**（19:00 启动），LISTEN 127.0.0.1:9097 |
| 3 | `api_all_requests.log` 最后一条 = **19:31:33 /api/event/rewardincrease**；到 19:33:30 **零请求**；`all_paths.log` 同样止于 19:31:33 |
| 4 | `tcp-access.log` 19:31:53 有一条 `sni=gsqc-api.bluearchive-cn.com → 127.0.0.1:8443`，`bytes_sent=62820 / bytes_received=32423 / session_time=73.487`，但 `ba_raw.log`/`ba_mitm.log` **无对应 HTTP 行** |
| 5 | 应用未崩（`openlog.tapapis.cn` 心跳 19:31:45 / 19:32:45 / 19:33:45 连续） |
| 6 | 8443 vhost = `/www/server/panel/vhost/nginx/ba_mitm.conf` |

---

## A. 那条 19:31:53 的 stream 连接到底发生了什么

### A-1 三个 error log 在窗口内**全部为空**（原始证据）

```
/www/wwwlogs/nginx_error.log        mtime 2026-11-16 03:28:09   47 行   窗口内 0 条
/www/wwwlogs/ba_mitm.error.log      mtime 2026-11-16 04:22:40   34 行   窗口内 0 条
/www/wwwlogs/tcp-error.log          mtime 2026-11-17 19:16:13  157 行   窗口内 0 条
journalctl -u nginx --since '2026-11-17 19:30'   →  -- No entries --
```

三个 error log 的内容也都是**更早**的事故，与本次窗口无关：

```
nginx_error.log  最后 3 条：2026/11/15 07:11 / 09:03 / 10:25  [alert] write() to access.log failed (28: No space left on device)
ba_mitm.error.log 最后 3 条：2026/11/14 13:31 / 13:52 / 13:52  [alert] write() ... No space left on device
tcp-error.log     最后 2 条：2026/11/17 19:09:26 / 19:16:13  [error] upstream timed out (110) ... upstream 199.16.156.38 / 157.240.17.35
                            （都是 443 stream 对**外网**的 passthrough 超时，与 8443 无关）
```

**⇒ 结论：nginx 在 19:31:53 这条连接上**没有记录任何 error**。既没有 TLS 握手失败，也没有 upstream 连接失败、没有 HTTP/2 协议错误。**

### A-2 这条连接本身（`tcp-access.log` 原文 + 同时段对照）

log_format（`/www/server/nginx/conf/nginx.conf:10`）：
`$time_local|$remote_addr|$protocol|$status|$bytes_sent|$bytes_received|$session_time|$upstream_addr|$upstream_bytes_sent|$upstream_bytes_received|$upstream_connect_time|sni=`

```
17/Nov/2026:19:31:53 +0800|39.182.87.249|TCP|200|62820|32423|73.487|127.0.0.1:8443|32423|62820|0.000|sni=gsqc-api.bluearchive-cn.com
                              ↑客户端收 62820   ↑客户端发 32423         ↑upstream         ↑发往upstream 32423  ↑upstream回 62820
```
同源 IP、同 SNI 的**前一条**（19:30:25）作对照：
```
17/Nov/2026:19:30:25 +0800|39.182.87.249|TCP|200|181748|14813|69.318|127.0.0.1:8443|14813|181748|0.000|sni=gsqc-api.bluearchive-cn.com
```
- 两条都是 `upstream_connect_time=0.000` → 上行（127.0.0.1:8443）**连接建立成功**。
- 两条都是 `status=200` → stream 层把会话判为**正常结束**（非 reset/失败）。
- 19:31:53 这条：**客户端发 32,423 B、收 62,820 B**，持续 **73.487 s**。

### A-3 但 HTTP 层完全没记录

```
ba_raw.log / ba_mitm.log 在 19:31:5x 的行数 = 0
ba_raw.log 最后 3 条：
  19:31:31  POST /api/campaign/chapterclearreward   200 bytes=2612
  19:31:33  POST /api/event/rewardincrease          200 bytes=408
  19:31:37  GET  /.env                              404  （扫描器，host=<SERVER_IP>，与手机无关）

ba_mitm.log 最后 3 条：
  19:27:30  GET /api/health 200 2  okhttp/4.9.2
  19:27:39  GET /api/health 200 2  okhttp/4.9.2
  19:31:37  GET /.env 404（扫描器）
```
**⇒ 19:31:53 这条连接**确实建立了 TLS、确实双向传了数据（32 KB 上行 / 62 KB 下行）、确实存活 73 秒，但**没有任何一个 HTTP 请求在 nginx 侧完成到"可记录"的状态**。**

### A-4 判定（给结论 + 明确不确定）

| 候选 | 支持证据 | 反对证据 | 结论 |
|---|---|---|---|
| ① TLS 握手后客户端主动放弃 | error log 零记录；stream 判 200 正常结束；无 HTTP 行 | 传了 62 KB 下行，不像"握手完就走" | **可能** |
| ② 证书被客户端拒绝 | — | 证书被拒会在握手期失败、双向字节≈0；这里传了 62 KB/32 KB；且同证书在 19:30:25 那条会话上成功了 | **基本排除** |
| ③ HTTP/2 请求中途取消（RST_STREAM / 连接被中断） | 8443 vhost 是 `http2 on`（`ba_mitm.conf:14,50`）；无 access_log 行（未完成即取消，nginx 不写 access 行）；73 秒长会话 | 需要 pcap 才能看到帧级 RST | **可能，且与"黑屏→用户杀进程"的行为最吻合** |
| ④ 其它（例如请求体超大被丢弃、被 WAF 拦） | — | 三个 error log 全空；WAF 只在 80/流式层 | **无证据** |

**⇒ 我能给的结论：**这不是证书问题，也不是 upstream 连不上，更不是应用崩溃。**证据一致指向「TLS 建立、数据双向流动、但 HTTP 请求从未完成」，即 ① 或 ③；现有日志无法在 ①/③ 之间二选一 —— 要定性必须有 8443 loopback 的 pcap（已按 §D 打开）。**

---

## B. `access_log` 有没有 `buffer=`（排除"日志延迟/丢日志"）

```
grep -n 'access_log' /www/server/panel/vhost/nginx/ba_mitm.conf
22:    access_log /www/wwwlogs/ba_mitm.log;
23:    access_log /www/wwwlogs/ba_raw.log ba_raw;
30:        access_log /www/wwwlogs/ba_raw.log ba_raw;
58:    access_log /www/wwwlogs/ba_mitm.log;
59:    access_log /www/wwwlogs/ba_raw.log ba_raw;
73:        access_log /www/wwwlogs/ba_raw.log ba_raw;
74:        access_log /www/wwwlogs/ba_gwstate.log ba_raw;
84:        access_log /www/wwwlogs/ba_raw.log ba_raw;
112:    access_log /www/wwwlogs/ba_static.log ba_raw;

grep -n 'buffer' /www/server/panel/vhost/nginx/ba_mitm.conf  →  (none)
全局 grep -n 'access_log' /www/server/nginx/conf/nginx.conf
10:    access_log /www/wwwlogs/tcp-access.log tcp_format;   ← stream 层
99:    access_log  /www/wwwlogs/access.log;
```
**⇒ 全部 `access_log` 都**没有** `buffer=`（= 默认每条请求完成即写，不缓冲）。**
**⇒ 所以"没有 HTTP 行"不是日志延迟/丢日志，而是**真的没有完成的请求**。**

---

## C. 同一窗口 Shittim 侧有没有东西（有没有绕过桥接直达 5000）

### C-1 `journalctl -u ba-shittim --since '2026-11-17 19:30'`
```
-- No entries --
```
（该 unit 的 `StandardOutput=append:/var/log/ba-shittim.log`，journal 不记录业务日志 —— 属已知。）

### C-2 `logs/log.txt` 在 19:31:00–19:34:00 窗口内 **29 行**，全部是**经桥转发**的请求

```
19:31:11.241  HTTP POST /api/gateway responded 200 in 11.3434 ms
19:31:13.489  "Campaign_ChapterClearReward"(6010) -> 200 in 9ms
19:31:16.179  "Campaign_ChapterClearReward"(6010) -> 200 in 9ms
19:31:18.651  "Campaign_ChapterClearReward"(6010) -> 200 in 11ms
19:31:21.036  "Campaign_ChapterClearReward"(6010) -> 200 in 10ms
19:31:24.840  "Campaign_ChapterClearReward"(6010) -> 200 in 14ms
19:31:27.109  "Campaign_ChapterClearReward"(6010) -> 200 in 11ms
19:31:29.289  "Campaign_ChapterClearReward"(6010) -> 200 in 10ms
19:31:31.551  "Campaign_ChapterClearReward"(6010) -> 200 in 11ms
19:31:33.770  "Event_RewardIncrease"(25003) -> 200 in 2ms      ← 最后一条游戏协议
19:31:37.045  HTTP GET /.env responded 404 in 1.1539 ms        ← 扫描器
窗口内总计 29 行；19:31:37 之后到 19:34:00 **再无任何一行**
```
**⇒ Shittim 在窗口内**完全正常**：6010 章奖励 ×8 + 25003 各 200，无 ERR；黑屏期间（19:31:37 之后）**收到 0 个请求**。**
**⇒ 没有任何请求绕过桥接直达 5000**（Shittim 的 gateway 日志全部来自桥；`ss -tnp | grep :5000` 当前无 established 连接）。

### C-3 sqlite WAL mtime

```
-rw------- 684032  2026-11-17 19:34:02.492760797 +0800  /www/wwwroot/ba_srv/shittim.sqlite3
（-wal / -shm 存在，说明 19:31 的写入在 19:34:02 被 checkpoint 过）
```
**⇒ 黑屏窗口内数据库有写入落盘（19:31 那批 6010/25003 的结果），19:34:02 完成 checkpoint；不是"写库卡住"。**

---

## D. 只读抓包装置（已启动，可一键撤除）

### D-1 启动命令（已执行）
```bash
mkdir -p /root/ba_watch && chmod 700 /root/ba_watch
setsid nohup tcpdump -i lo -p -U -Z root -s 0 -C 20 -W 5 \
    -w /root/ba_watch/blackout_lo.pcap 'tcp port 8443 or tcp port 9097' \
    >/root/ba_watch/tcpdump.out 2>&1 < /dev/null &
```

### D-2 当前状态（已实测可用）
```
PID   = **2622291**（root，命令如上）
文件  = /root/ba_watch/blackout_lo.pcap0（-C 20 -W 5 → 最多 5×20MB 环形）
验证  = 一次 curl 9097 后文件从 0 → 2166 → 6974 B，tcpdump -r 能读出 SYN/ACK/数据包
9:[+] 说明抓包**真的在工作**（不是空跑）
stderr= tcpdump: listening on lo, link-type EN10MB (Ethernet), snapshot length 262144 bytes
```

### D-3 **停止命令（一键撤除）**
```bash
kill 2622291                       # 或：pkill -x tcpdump
rm -rf /root/ba_watch              # 彻底撤除（本任务新建的唯一目录）
```
（若换过 pid，用 `pidof tcpdump` 取当前 pid；`rm -rf` 前请确认路径就是 `/root/ba_watch`。）

### D-4 读取/分析命令
```bash
ls -l /root/ba_watch/blackout_lo.pcap*
tcpdump -r /root/ba_watch/blackout_lo.pcap0 -nn 'tcp port 8443' | head -50
# 看是否有 RST / FIN 提前出现：
tcpdump -r /root/ba_watch/blackout_lo.pcap0 -nn 'tcp[tcpflags] & (tcp-rst|tcp-fin) != 0' | head -30
# 按时间窗过滤（黑屏发生在 19:31:33 之后）：
tcpdump -r /root/ba_watch/blackout_lo.pcap0 -nn -tttt | awk '$2 ~ /19:3[1-3]/'
# 把某条会话单独导出给 Wireshark：
tcpdump -r /root/ba_watch/blackout_lo.pcap0 -w /root/ba_watch/one_flow.pcap 'host 127.0.0.1 and port 8443'
```
**注意**：只抓 `lo`（8443 + 9097），**未抓 443 全量**，磁盘余量 14 G，5×20 MB 环形上限 100 MB。

---

## E. 还缺什么才能定性

1. **8443 的帧级证据** —— 需要下一次复现时的 `/root/ba_watch/blackout_lo.pcap`（已就绪）。要回答的具体问题：
   - 客户端在收到多少字节后停止 ACK / 发 RST；
   - TLS record 的最后一个方向（是客户端先关，还是 nginx 先关）；
   - 若是 HTTP/2，是否有 `RST_STREAM`/`GOAWAY`（需要 TLS 解密才能看帧，或看 TCP 层 RST 位置）。
2. **nginx 对"未完成请求"的记录** —— 现有 `access_log` 只在请求完成时写。若要在下次直接看到"客户端取消"，可临时加 `error_log ... info;`（会改变配置，**需 Lead 批准**，本次未做）。
3. **客户端侧日志** —— 黑屏瞬间客户端是否报 `invalidprotocol` / 资源加载失败 / 场景名缺失，只有手机侧 logcat 能回答。
4. **`Campaign_ChapterClearReward`(6010) ×8 的上下文** —— 19:31:13–19:31:31 客户端连续 8 次领章奖励（都 200），随后 19:31:33 收尾，19:31:53 开新连接后黑屏。**这是本次窗口里最反常的行为序列**，值得在客户端侧确认是否卡在"领奖→刷新"循环里。

---

## 附：本次取证未改动任何东西

```
未改 nginx 配置（ba_mitm.conf / ba_sni.conf 未动）
未改桥（account_auth_probe.py 未动）
未改 Shittim DLL（Shittim-Server.dll=db465934…, Schale.dll=6745ee5f…）
未改数据库
新增仅：/root/ba_watch/（tcpdump 输出目录）
```
