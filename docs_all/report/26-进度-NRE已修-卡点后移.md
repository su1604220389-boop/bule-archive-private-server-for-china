# 26 — 进度：NRE 已修掉，卡点后移到「拿到 Servers 之后」

> 时间：2026-11-14 02:00 前后

---

## 一、已确认的因果链（按时间顺序，全部有实证）

| # | 事实 | 证据 |
|---|---|---|
| 1 | CA 生效于 **01:33:45** | 46 条 fatal `desc=49` 全落在 01:24:58–01:33:45，之后归零 |
| 2 | `/api/state` 应答决定弹窗正文 | `Msg` 从 `""` 换成 `PROBE-M1-STATE-ZQ7`，四帧截图正文逐像素 `0 px` 差异跟着变 |
| 3 | `Msg` 为空 → 弹窗正文空白 | 同上（反向验证） |
| 4 | `state-api` 应回 `{Servers, State, Msg}`；`gsqc-api` 应回 24 字段大 DTO | 元数据 `ServerInfoConnectionGroupData` 25 属性 + 真实抓包 |
| 5 | `Servers` 为 null → `GetApiServerInfo` **NullReferenceException** | 两次独立复现（pid 26473 / 29531），均「启动后约 5 s」 |
| 6 | 补上 `Servers` 后 **NRE 消失** | 第三次启动 pid 31717，`grep -E 'E/Unity\|NullReference'` = **0 条** |
| 7 | 但客户端**对 `gsqc-api` / `gs-api` 零连接、零 DNS 查询** | `ss` + `conntrack` + netd DNS 记录，三处同时为空 |

---

## 二、当前卡点

> **NRE 修掉后，客户端读了 `Servers`（否则 NRE 不会消失），却没有对其中任何地址发起连接，反而弹出一个正文空白的「提示」框。**

即：卡点从「`Servers` 为 null」后移到了「拿到服务器列表之后的某一步」，而这一步**没有任何出网动作**。

### 同轮观察到的唯一网络活动
- `state-api` → CLOSE-WAIT，`rx_queue=24`（服务端 FIN 后客户端不读不关）
- `openlog.tapapis.cn` → ESTAB（TapTap 埋点，与主线无关）
- **5 条直连 `<SERVER_IP>:443`**（= `example.com`），数量与 `detection_address` 里 3 条 HTTP + 3 条 MTR 大致对应

---

## 三、新发现：客户端在做「网络环境检测」

手机 pref `cn_official_sp_default.xml`（01:54 被改写）：

```json
"detection_address":"{\"Auto\":{\"HTTP\":[\"https://example.com/checkhealth.html\",\"https://example.com\",\"https://example.com/api/health\"],\"MTR\":[同三条]},\"Enable\":true,\"Internet\":\"https://example.com\"}"
```

同一文件里还有缓存登录态：
```json
"local_user_config":"{\"loginName\":\"177****1532\",\"login_type\":1,\"token\":\"61de1d1b…\",\"uid\":314816420}"
```

**关键疑问**：`detection_address` 指向**我们自己的域名**，国服官方客户端不可能自带这个。⇒ 必须查清是**服务端下发**还是**被写死进 prefs**。这决定后面能不能改。

手机侧实测三个检测地址：
```
https://example.com/checkhealth.html  → 200 / 2 字节
https://example.com/                   → 200 / 2 字节
https://example.com/api/health         → 200 / 15 字节 JSON
```

⚠️ `detection_address` 里 **`MTR` 与 `HTTP` 并列、地址相同**。手机侧 DNAT 是 `-p tcp --dport 443` 全量劫持，**TCP MTR 的每一个 TTL 探测包都会被劫到我们服务器**，跳数恒为 1。若客户端要求 MTR 成功，这里必然失败。

---

## 四、已排除（本轮新增）

| 假设 | 排除依据 |
|---|---|
| IPv6 导致连不上 gsqc/gs-api | 三个域名 **AAAA 记录为空**；游戏进程无 tcp6 套接字；`ip6tables` 增量来自 `tapsdk.tapapis.cn` 的 v6 |
| NRE 仍在 | 第三次启动 0 条 |
| 弹窗来自「维护态」 | 真实抓包 `State:1` 才是维护；我们给的是 `State:0` |

---

## 五、正在跑的实验

| 实验 | 做法 | 判读 |
|---|---|---|
| **E1：弹窗归属** | `state-api` 的 `Msg` 改成 `MSGSTATE-M2-K9`，`Servers`/`State` 不动 | 弹窗出现标记 → 仍是 `state-api` 的 `Msg` 驱动；仍空白 → 弹窗来自别处（检测/SDK/本地化表） |
| **E2：`detection_address` 来源** | 启动前后比对 prefs 的 `md5` 与 `mtime` | md5 不变+mtime 变 → 客户端自己重写；md5 变 → 有东西下发 |
| **E3：弹窗与检测的先后** | 1.5 s 粒度记录连接建立时间 + 8 张截图 | 弹窗在检测前 → 检测不是成因；在检测后 → 检测判定失败 |
| **E4：Unity 业务日志** | 去掉 `E/` 前缀，抓全量 `[VDIW]/Unity` | 找 `ServerInfo`/`Connect`/`Gateway`/`Login` 相关行 |

---

## 六、顺手要解决的两件事

1. **目录统一到 `/www/wwwroot/bapatch/`**（用户明确要求，见 `MEMORY.md`）。`/root/bapatch`、`/root/ba_pcap`、`/www/wwwroot/_ba_state` 三处合并。**reload 等实验间隙再做**，避免在链路上制造抖动。
2. **安全审计**：`/www/wwwroot` 是 web 根目录的父目录，必须确认没有任何 vhost 把它当 root 对外提供，否则 `ca/ca2/ca.key` 会被公网下载。三条 curl 必须全是 404/403。

---

## 七、口径修正记录（自我纠正）

| 旧说法 | 更正 |
|---|---|
| 「Unity 一条日志都不打」 | **错**。那是基于 `E/` 前缀过滤得出的。Unity 会打，只是之前没走到出错位置；本轮 `E/Unity` NRE 就是靠它抓到的。以后抓业务日志要去掉级别前缀 |
| 「客户端不发 SNI」 | **错**。`state-api` 明确带 SNI；无 SNI 那条是别的连接 |
| 「RetryUtils 无第 6 次重试」 | **错**（抓早了）。实际一路重试到第 7 次 128 s |
| 「access_log 有记录 = 通过」 | **错**。只认 pcap |
| 「我们服务器上没记录 = 客户端没发请求」 | 本场景已被「手机侧全量按 uid 劫持」排除，但该推论本身在一般情形下不成立 |
