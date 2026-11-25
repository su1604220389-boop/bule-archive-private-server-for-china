# STATIC / CDN 取证 —— 「回大厅黑屏 = 卡在资源下载」假设验证

- 取证者：srv-ops
- 时间：2026-11-17 19:43–19:44（北京时间 UTC+8）
- 窗口：**2026-11-17 19:39:00 → 19:44**（取证时刻）
- 只读；未改任何配置；抓包装置仍在跑（见另一份 `SRV_FINDINGS_20261117.md` §D）

---

## 结论（先说）

**「有卡住的 static 连接 / 没有」→ **没有**。**

**对主假设「卡在 static AssetBundle 下载」的判定：**不成立**。**

判定依据（两条，缺一不可）：
1. **客户端侧**（用户澄清，2026-11-17 19:44 追加）：画面闲置时纯黑，**一触碰屏幕就有动画** ⇒ 渲染管线活着、输入可用、能画帧。**"卡在资源下载等死"与"能画动画"互斥。**
2. **服务端侧**（本报告 §1–§6）：窗口内 static 会话全部正常结束（合计 3 条、最大 8.7 KB）、无 SYN-SENT、无任何队列积压、无 499、无 upstream 超时。

⇒ **「回大厅黑屏 = 卡在 static CDN 下载」这条假设：不成立。** 后续不要再沿这条线取证。

- 窗口内 `sni=static.bluearchive-cn.com` 的 stream 会话只有 **3 条**，全部透传到**真实 CDN**，**全部正常结束**，字节量都很小（sent 8055 / 6953 / 8685 B）。
- 没有 SYN-SENT、没有任何 `Recv-Q/Send-Q > 0` 的 443 连接、没有 499、没有任何 nginx error。
- 与此同时客户端在 19:39:55 与 19:42:37 **完整重登了两次**（含 123 KB 的 loginsync 响应，均成功），说明网络栈是通的。
- `ba_static*.log`（static vhost）在窗口内 **0 条** —— 因为 static 在 **stream 层就被透传**，根本不进 8443 vhost，属预期。

---

## 1. `tcp-access.log`：19:39–19:44 的 SNI 分布（原始统计）

命令：
```bash
grep -aE '17/Nov/2026:19:(39|4[0-9])' /www/wwwlogs/tcp-access.log | sed -E 's/.*sni=//' | sort | uniq -c | sort -rn
```
输出：
```
      8 sdk-api.yostar.cn
      5 openlog.tapapis.cn
      4 gsqc-api.bluearchive-cn.com
      4 gs-api.bluearchive-cn.com
      4 down.anticheatexpert.com
      3 static.bluearchive-cn.com          ← 只有 3 条
      2 yostar-cn-netsdk-logging.cn-shanghai.log.aliyuncs.com
      2 yostar-cn-client-logging.cn-shanghai.log.aliyuncs.com
      2 tapsdk.tapapis.cn
      2 state-api.bluearchive-cn.com
      2 gid.tapapis.cn
      2 er.ns.aliyuncs.com
      2 dypnsapi-dualstack.aliyuncs.com
      2 app.adjust.cn
      1 udata-api.open.yostar.net
      1 customer.yostar.net
```
窗口内总连接数 = **42**。

### 三条 static 会话的完整行（原文）
```
17/Nov/2026:19:41:20 +0800|39.182.87.249|TCP|200|8055|1933|121.245|60.188.66.35:443|1933|8055|0.008|sni=static.bluearchive-cn.com
17/Nov/2026:19:42:00 +0800|39.182.87.249|TCP|200|6953|853|0.339|123.148.116.78:443|853|6953|0.010|sni=static.bluearchive-cn.com
17/Nov/2026:19:43:03 +0800|39.182.87.249|TCP|200|8685|1933|61.212|123.148.116.78:443|1933|8685|0.012|sni=static.bluearchive-cn.com
```
字段含义：`bytes_sent(服务器→客户端)|bytes_received(客户端→服务器)|session_time|upstream|…|sni`

**判读（逐条）**
- 全部 `status=200`；`upstream_connect_time` = 0.008 / 0.010 / 0.012 s → 与真实 CDN 建连**毫秒级**，没有超时。
- 传输量都很小（8 KB / 7 KB / 8.7 KB 下行），**不是** AssetBundle 的大块下载（BA 的 bundle 通常 MB 级）。
- `session_time` 121.245 s / 61.212 s 看着像"长"，但**上行只有 1,933 B**、下行 8 KB —— 这是 **keep-alive 空闲保持**，不是"发了个请求等回包等到超时"。同窗口 8443 上也有 `dur=60.071 / 60.072` 的**完全一样形状**的会话（sent 2956 / recv 782），同样是 keep-alive。

**⇒ 没有任何一条 static 连接呈现"大流量卡住"或"零字节挂死"的特征。**

---

## 2. 此刻挂着的连接（`ss`，取证时刻）

```bash
ss -tnp | grep '39.182.87.249'
ss -tn state established '( dport = :443 or sport = :443 )'
ss -tn state syn-sent
```
输出（节选，全部 443 连接的队列都是 0/0）：
```
ESTAB  0 0  172.24.44.228:443  39.182.87.249:7184  nginx fd=63
ESTAB  0 0  172.24.44.228:443  39.182.87.249:7291  nginx fd=36
ESTAB  0 0  172.24.44.228:443  39.182.87.249:7364  nginx fd=53
ESTAB  0 0  172.24.44.228:443  39.182.87.249:7317  nginx fd=19
ESTAB  0 0  172.24.44.228:443  39.182.87.249:7388  nginx fd=57
ESTAB  0 0  172.24.44.228:443  39.182.87.249:7279  nginx fd=30
ESTAB  0 0  172.24.44.228:443  39.182.87.249:7372  nginx fd=55
ESTAB  0 0  172.24.44.228:443  39.182.87.249:7217  nginx fd=28
FIN-WAIT-2 0 0  172.24.44.228:443  39.182.87.249:7344 / :7358 / :7361 / :7363 / :7282
```
```
ss -tn state syn-sent   →  （空，0 条）
```
TCP 细节（`ss -tinpi`）举例：
```
:7184  bytes_sent:6084 bytes_acked:6084 bytes_received:1393 ... lastsnd:114364 lastrcv:114380
:7317  bytes_sent:8472 bytes_acked:8472 bytes_received:9500 ... lastsnd:952    lastrcv:976
:7217  bytes_sent:6706 bytes_acked:6706 bytes_received:2753 ... lastsnd:30796  lastrcv:30808
```
**判读**
- **没有 SYN-SENT**（不存在"连不上一直重试"的连接）。
- 所有 ESTAB 的 **`Recv-Q=0`、`Send-Q=0`、`unacked` 为空、`bytes_acked == bytes_sent`** → **没有任何未送达的数据积压**。
- 5 条 `FIN-WAIT-2`：**服务端已发 FIN、客户端还没回 FIN** —— 这是"服务端超时/正常关连接、客户端没关"，**不是**服务端在等数据。
- `FIN-WAIT-2` 的连接都是 **443 上的 stream 会话**（nginx 侧已收尾）。

**⇒ 此刻没有任何"挂着不返回"的连接。**

---

## 3. static vhost 日志（窗口内 0 条，属预期）

```bash
ls -l /www/wwwlogs/ba_static*.log
grep -acE '17/Nov/2026:19:(39|4[0-9])' /www/wwwlogs/ba_static.log
```
```
/www/wwwlogs/ba_static.log         2132 B   mtime 2026-11-14 04:35:17   窗口内 0 条
/www/wwwlogs/ba_static_mitm.log       0 B   mtime 2026-11-14 04:44:28   窗口内 0 条
/www/wwwlogs/ba_static_status.log     0 B   mtime 2026-11-14 04:44:28   窗口内 0 条
```
**判读：** 这是**预期行为**，不是异常 —— `ba_sni.conf` 把 `static*.bluearchive-cn.com` 在 **stream 层**就透传给真实 CDN（见 §5），**根本不会进入 8443 的 static vhost**，所以 vhost 日志必然为空。**不能用"vhost 日志为空"推断"没有 static 流量"。**

---

## 4. nginx 错误日志（窗口内 0 条）

```bash
for f in nginx_error.log tcp-error.log ba_mitm.error.log; do
  ls -l /www/wwwlogs/$f; grep -aE '2026/11/17 19:(39|4[0-9])' /www/wwwlogs/$f; done
grep -aE '2026/11/17 19:(39|4[0-9])' /www/wwwlogs/*.log | grep -aiE 'timed out|499|handshake'
```
```
/www/wwwlogs/nginx_error.log      mtime 2026-11-16 03:28:09   窗口内 0 条
/www/wwwlogs/tcp-error.log        mtime 2026-11-17 19:16:13   窗口内 0 条
/www/wwwlogs/ba_mitm.error.log    mtime 2026-11-16 04:22:40   窗口内 0 条
grep timed out / 499 / handshake  →  （无输出）
```
**⇒ 窗口内没有 upstream 超时、没有 SSL 握手失败、没有 499。**

---

## 5. `ba_sni.conf` 的 static 规则（原文，未改动）

```
 8-    # IP-as-SNI must NEVER be proxied (it hairpins back to ourselves) -- send to a dead local port
 9-    ~*^[0-9.]+$                 127.0.0.1;
10:    # static CDN must be PASSTHROUGH (real cert / real content), must precede the bluearchive rules
11:    ~*^static(-qc|-hs)?\.bluearchive-cn\.com$   $ssl_preread_server_name;
12-    ""                          127.0.0.1;
13-    ~*^bluearchive-cn\.com$     127.0.0.1;
...
20:    # port 1 = nothing listens -> immediate TCP refuse instead of hairpin loop
21:    ~*^[0-9.]+$                 1;
22:    ~*^static(-qc|-hs)?\.bluearchive-cn\.com$   443;
23-    ""                          8443;
24-    ~*^bluearchive-cn\.com$     8443;
---
34:    resolver 223.5.5.5 119.29.29.29 114.114.114.114 valid=60s ipv6=off;
35:    resolver_timeout 10s;
37:    proxy_connect_timeout 5s;
38:    proxy_timeout 600s;
```
**判读**
- `static(-qc|-hs)?.bluearchive-cn.com` → `$ssl_preread_server_name:443` ⇒ **按 SNI 原样连接到真实 CDN**（DNS 由 resolver 解析、`valid=60s`）。
- `proxy_connect_timeout 5s`：连不上 CDN 会在 **5 秒**内失败并写 `tcp-error.log` —— 窗口内**没有**这类记录。
- `proxy_timeout 600s`：一条空闲会话最长可挂 600 s 才被关；这也解释了 §1 里 121 s / 61 s 的 `session_time`（空闲保活，不是卡住）。

---

## 6. 桥侧日志：**不是"完全空白"，客户在 19:39 和 19:42 各重登了一次**

```bash
tail -3 /www/wwwroot/bapatch/logs/all_paths.log
```
```
2026-11-17 19:42:15 | POST /api/event/rewardincrease                | CL=882 | UA=BestHTTP/2 v2.4.0
2026-11-17 19:42:15 | POST /api/notification/eventcontentreddotchec  | CL=882 | UA=BestHTTP/2 v2.4.0
2026-11-17 19:42:17 | POST /api/event/rewardincrease                | CL=882 | UA=BestHTTP/2 v2.4.0
```
按分钟统计（19:39–19:45）：
```
19:39 : 28 requests
19:42 : 26 requests
（19:40 / 19:41 / 19:43 / 19:44 : 0）
```
这两轮各自都是**完整登录序列**（每轮都有 `account/auth`、`academy/getinfo`、`account/loginsync`、`item/list`、`networktime/sync`、`contentsave/get`、`gettutorial`、`mission/*` …）。

与之对应，`tcp-access.log` 里有两条 **123 KB 级下载**、`sni` 为空（= 走 8443 的会话，`sni=` 字段对 8443 会话不写值）：
```
17/Nov/2026:19:39:55 +0800|39.182.87.249|TCP|200|123394|40369|29.963|127.0.0.1:8443|...
17/Nov/2026:19:42:37 +0800|39.182.87.249|TCP:200|119170|37150|26.460|127.0.0.1:8443|...
```
（123 KB ≈ `Account_LoginSync(1017)` 的响应体 122,968 B，**已完整送达**。）

**⇒ 所以"19:39:35 之后桥日志完全空白"这个前提**不成立**：19:39 与 19:42 各有 26–28 条请求，且都成功返回。**

---

## 7. 对「卡在资源下载」假设的判定

**判定：不成立。**

两条独立证据：

**（A）客户端侧（决定性）** —— 用户 19:44 澄清：**画面闲置时纯黑，一触碰屏幕就有动画**。
渲染通了、能吃输入、会画动画 ⇒ 这不是"资源加载卡死等死"。Unity 主线程 `pthread_cond_wait` + 6 个 `AssetGarbageCol` 更符合**"主线程在等一个应用层回调/状态"**，而不是等 IO。

**（B）服务端侧（本报告 §1–§6）**

| 判据 | 观察 | 是否符合"卡在下载" |
|---|---|---|
| 有没有大流量的 static 会话挂着 | 无；3 条 static 会话最大 8.7 KB，全部 200 结束，`upstream_connect_time` 8–12 ms | ✗ |
| 有没有 SYN-SENT / 队列积压 | 无 SYN-SENT；所有 443 会话 `Recv-Q=Send-Q=0`、`bytes_acked=bytes_sent` | ✗ |
| 有没有 upstream 超时 / 499 / 握手失败 | 三个 error log 窗口内 0 条；无 499 | ✗ |
| 客户端网络是否还通 | 19:39:55 / 19:42:37 两次完整重登成功（含 123 KB loginsync） | ✗ |

**必须说清的边界（不替你把话圆上）：**
- `static*` 是**透传**，服务端只能看到 stream 层的字节数与会话时长，**看不到 HTTP 层的 URL/状态码**。所以本报告能证明的是"**经过我们的 static 连接没有一条是挂着不动的**"；**不能**证明"客户端没有去连一个**不经过我们**的 CDN 地址"。
- 但（A）已经排除了"下载卡死"这一大类可能，所以这条边界**不影响结论**。

---

## 8. 追加复检（2026-11-17 19:44，Lead 指定只查三条）

### 8-1 `19:39:00` 之后 SNI 含 `static` 的长连接
```bash
grep -aE '17/Nov/2026:19:(39|4[0-9])' /www/wwwlogs/tcp-access.log | grep -a 'sni=static'
```
```
17/Nov/2026:19:41:20 +0800 sent=8055 recv=1933 dur=121.245 upstream=60.188.66.35:443
17/Nov/2026:19:42:00 +0800 sent=6953 recv=853  dur=0.339   upstream=123.148.116.78:443
17/Nov/2026:19:43:03 +0800 sent=8685 recv=1933 dur=61.212   upstream=123.148.116.78:443
count = 3
```
同窗口 `dur > 120 s` 的**所有** SNI（含非 static）：
```
19:41:18 sent=6295  recv=1006 dur=120.179 up=47.93.93.145:443     （tap 系）
19:41:20 sent=8055  recv=1933 dur=121.245 up=60.188.66.35:443     （static）
19:41:20 sent=9103  recv=1047 dur=120.117 up=223.109.116.174:443
19:41:22 sent=5496  recv=1933 dur=120.171 up=39.107.196.62:443
19:41:25 sent=18786 recv=4166 dur=128.875 up=112.48.163.29:443
19:41:25 sent=1281  recv=1366 dur=120.128 up=112.48.163.29:443
19:41:56 sent=6084  recv=1393 dur=149.016 up=106.15.7.118:443
19:41:56 sent=8550  recv=9595 dur=159.155 up=61.170.66.121:443
19:44:01 sent=6295  recv=1006 dur=120.165 up=47.93.93.145:443
19:44:04 sent=9103  recv=1047 dur=120.128 up=42.121.149.94:443
```
**⇒ 结论：没有"字节数为 0 或极大"的 static 长连接。所有 `dur>120s` 会话的字节量都在 1–19 KB 区间，是 **keep-alive 空闲**（SDK 心跳/日志上报），不是传输卡住。**

### 8-2 此刻有没有挂住的连接
```bash
ss -tnp | grep 39.182.87.249
ss -tn state syn-sent
```
```
ESTAB      0 0  172.24.44.228:443  39.182.87.249:7184  nginx fd=63
ESTAB      0 0  172.24.44.228:443  39.182.87.249:7317  nginx fd=19
FIN-WAIT-2 0 0  172.24.44.228:443  39.182.87.249:7291 / :7364 / :7344 / :7388 / :7279 / :7372 / :7217
ESTAB      0 108 172.24.44.228:22  39.182.87.249:7403  sshd      ← 我自己的 SSH 会话
状态汇总：3 ESTAB / 7 FIN-WAIT-2
SYN-SENT 数量 = 0
非零队列：仅 SSH 那条（Send-Q=1380，是我的 shell 输出）
```
**⇒ 结论：没有任何挂住的游戏连接，没有 SYN-SENT，没有 Recv-Q 堆积；443 上所有会话队列为 0。**

### 8-3 桥日志最后 3 行
```
all_paths.log:
  2026-11-17 19:42:15 | POST /api/event/rewardincrease                | CL=882 | UA=BestHTTP/2 v2.4.0
  2026-11-17 19:42:15 | POST /api/notification/eventcontentreddotchec  | CL=882 | UA=BestHTTP/2 v2.4.0
  2026-11-17 19:42:17 | POST /api/event/rewardincrease                | CL=882 | UA=BestHTTP/2 v2.4.0
api_all_requests.log:
  19:42:15 /api/event/rewardincrease              200 / 384
  19:42:15 /api/notification/eventcontentreddotcheck 200 / 384
  19:42:17 /api/event/rewardincrease              200 / 384
  total = 973
```
**⇒ 最后一条是 `19:42:17`，**不是 19:39:35**。之后（到取证时刻 19:44:49）服务端零请求。**
**（更正 Lead 的假设：桥日志并非"止于 19:39:35"；19:39 与 19:42 各有一整轮 26–28 条请求的完整重登。）**

---

## 附：本次未改动任何东西

```
未改 ba_sni.conf（仅 grep 读取）
未改 nginx（未 reload）
未改桥 / DLL / 数据库
新增：无（本报告只读产出）
抓包装置：仍在运行（/root/ba_watch/blackout_lo.pcap*，pid 见 SRV_FINDINGS §D）
```
