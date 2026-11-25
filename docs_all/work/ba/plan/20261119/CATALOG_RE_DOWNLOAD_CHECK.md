# 客户端「清数据 + 重下资源」是否真拿到 160 MB 的 ExcelDB.db（只读取证）

- 时间：2026-11-19 01:57（Asia/Shanghai）｜ 执行：srv-ops（**只读**：未改任何文件、未重启、未部署）
- 数据源：`/www/wwwlogs/tcp-access.log`（13,162,856 B，含 `sni=` 字段的 stream 层日志；共 **115,859** 行可解析，0 行解析失败）
- 字段序：`时间|client|proto|status|bytes_sent|bytes_received|dur|upstream|upstream_bytes_sent|upstream_bytes_received|upstream_dur|sni=`

## 一句话结论

**没有。整份日志里从来没有出现过 ~160 MB 级别的单次下行；`static.bluearchive-cn.com` 的单条最大只有 8,688 B（约 8 KB），
且 19/Nov 全天（含 01:00–01:30 重下窗口）**连一条 static/bluearchive 的记录都没有**。**

---

## 1. 日志与轮转情况

```
ls /www/wwwlogs/
  tcp-access.log    13,162,856 B   Nov 19 01:57   ← 主日志（无 .log.1 / .gz 轮转文件）
  tcp-error.log         62,052 B   Nov 19 01:20
（其余为各站点 access/error 日志，无 stream 轮转副本；tcp-access.log 覆盖 16/Nov 04:52 → 19/Nov 01:57）
⇒ 轮转不是问题：两个窗口都在主日志覆盖范围内
```

## 2. 两个窗口的总体情况

| 窗口 | 记录数 | bytes_sent 合计 | upstream_recv 合计 | >1 MB 条数 | 单条最大 |
|---|---|---|---|---|---|
| **19/Nov 01:00–01:30**（清数据重下） | **39** | **2,075,716 B ≈ 1.98 MB** | 1.98 MB | **0** | **639,469 B（0.61 MB）**，sni=`example.com`，01:00:49 |
| **18/Nov 22:00–23:59** | **166** | **9,748,663 B ≈ 9.30 MB** | 9.30 MB | **1** | **1,748,065 B（1.67 MB）**，sni=`example.com`，22:05:14 |

### 01:00–01:30 窗口内按 sni 汇总（全部）
```
example.com     n=23   sent=1.97 MB   （upstream 127.0.0.1:8443 ← 本机反代/抓包）
(空)                 n=4    sent=0.01 MB
-                    n=2    sent=0.00 MB
<SERVER_IP>       n=10   sent=0.00 MB
⇒ **没有任何 static.bluearchive-cn.com / 其它 CDN 域名**
```

### 01:00–01:30 窗口最大 10 条
| 时间 | sni | bytes_sent | dur | upstream |
|---|---|---|---|---|
| 01:00:49 | example.com | 639,469 | 22.456 | 127.0.0.1:8443 |
| 01:28:49 | example.com | 638,890 | 10.011 | 127.0.0.1:8443 |
| 01:24:32 | example.com | 638,861 | 24.643 | 127.0.0.1:8443 |
| 01:24:29 | example.com | 21,642 | 19.250 | 127.0.0.1:8443 |
| 01:25:07 | example.com | 13,293 | 105.994 | 127.0.0.1:8443 |
| 01:00:21 | example.com | 10,660 | 60.126 | 127.0.0.1:8443 |
| 01:28:32 | example.com | 10,644 | 60.124 | 127.0.0.1:8443 |
| 01:00:12 | example.com | 6,757 | 45.750 | 127.0.0.1:8443 |
| 01:23:42 | example.com | 6,757 | 17.871 | 127.0.0.1:8443 |
| 01:28:23 | example.com | 6,757 | 48.368 | 127.0.0.1:8443 |

> 三条约 0.61 MB 的传输与 `LoginSync` 量级（585 KB + 信封）吻合 —— 是 API 响应，不是资源包。

## 3. `static.bluearchive-cn.com` 单独看（**决定性**）

```
记录数 = 183     时间范围 = 16/Nov 05:53:24 .. **18/Nov 18:56:23**（19/Nov 之后 0 条）
sent 合计 = 1.25 MB（整整 4 天累计）   单条最大 = **8,688 B（0.008 MB）**
样本（节选）：
  16/Nov 05:53:24  static.bluearchive-cn.com  sent=6,953   up=101.68.219.169:443
  16/Nov 06:06:01  static.bluearchive-cn.com  sent=8,684   up=101.68.219.169:443   dur=61.2
  17/Nov 02:33:00  static.bluearchive-cn.com  sent=8,685   up=101.68.219.169:443
  18/Nov 18:56:23  …（最后一条）
⇒ 4 天里没有任何一次超过 8.7 KB 的 static 传输，**更没有 160 MB**
```

## 4. 全部 bluearchive 子域（含 api/state/gs）对照

```
记录数 = 893     时间范围 = 16/Nov 05:50:37 .. 18/Nov 18:56:42
sent 合计 = 30.75 MB        单条最大 = **2,329,321 B（2.22 MB）**
分布：gs/state/gsqc-api 都指向 upstream 127.0.0.1:8443（本机反代），单条多为 2–4 KB
      static.* 指向真实 CDN IP（101.68.x / 39.175.x / 112.25.x / 183.131.x …），单条 6–8.7 KB
⇒ 19/Nov 全天：**sni 含 static/bluearchive 的记录 = 0 条**
```

## 5. 判定

| 问题 | 结论 |
|---|---|
| 有没有 ~160 MB 级别的单次 `recv`/`sent`？ | **没有**（全日志最大单条 **2.22 MB**，且是 bluearchive API 子域；static 最大 8.7 KB） |
| 那次重下有没有拉 `ExcelDB.db`（160 MB）？ | **没有证据表明拉到了**；01:00–01:30 完全没有 static/CDN 流量 |
| 那段时间客户端主要从哪拉数据？ | **`example.com`（→ 127.0.0.1:8443 本机反代）**，共 1.97 MB，全是 API 响应（最大的三条 ≈ LoginSync 0.61 MB） |
| 总下行量大概多少？ | 01:00–01:30：**1.98 MB**；18/Nov 22:00–23:59：**9.30 MB** |

**⇒ 结论：那次"清数据重下资源"没有通过我们的代理拉到 160 MB 的表；`static` 方向的流量在 19/Nov 是 0。**
两条可能（本日志无法区分）：
1. 客户端发现 `TableBundles/ExcelDB.db` 在官方 CDN 上 404（我们之前测过），**重下事实上没有拿到表**，继续用旧/残缺表 → 与"页签能出、文案全红"高度吻合；
2. 客户端从**不经过本机的直连路径**拿到了表（本日志看不到）—— 但 19/Nov 全天 0 条 static 记录，且 static 历史上也从未超过 8.7 KB，支持"没拿到"多于"从别处拿到"。

## 6. 局限（如实说明）

- `tcp-access.log` 只记录**经过本机 stream 反代**的连接。若客户端 DNS 直连官方 CDN 且不走我们的入口，日志里不会出现——**这部分无法判定**。
- 但可以确定的是：**经由我们服务器的下行里，从头到尾没有出现过 160 MB 级别的传输**；连 MB 级别的都只有 1 条（1.67 MB，18/Nov 22:05，API 响应）。
- 若需要 100% 确认"表到底有没有下载"，只能在客户端侧看（APK 的 `files/` 或 `shared_prefs` 里 `ResourceVersion`/下载完成标记），服务端日志到此为止。

## 7. 原始数据文件

```
/www/wwwlogs/tcp-access.log            13,162,856 B（16/Nov 04:52 – 19/Nov 01:57，无轮转）
/www/wwwlogs/tcp-error.log                 62,052 B
（本次分析脚本 /tmp/979_tcp_window.py、/tmp/980_static_sni.py，仅读）
```

**只读完成：未修改任何文件、未重启、未部署。**
