# 98 · HAR 深度取证 —— 这份 Reqable 导出里到底有没有官方游戏协议流量

> 分析对象：`report\_tmp\reqable_udata.har`（238,135 B）
> SHA-256：`421a97577f1cfd185460e78838fbf6d3c83afa173656ec33914b8df1f24b292f`
> 生成工具：`report\_tmp\har_deep.py`（本报告由脚本自动生成，表格数据与文件逐字节对应）
> 纪律：**只读原文件，未连手机，未连任何服务器**。

---

## §0 一页结论

| # | 结论 | 硬度 |
|---|------|------|
| **C1** | 文件里有 **57 条** entry，覆盖 **12 个主机**、时间跨度 **138.8 秒（2.3 分钟）**。 | **[确证]** |
| **C2** | **没有 `POST /api/account/auth`，没有 `POST /api/academy/getinfo`，没有任何 `/api/*` 业务协议。** 全部 URL 里 `auth`/`academy`/`getinfo`/`battle`/`gacha`/`lobby` 等 17 个关键词命中数 **全为 0**。 | **[确证]** |
| **C3** | 游戏服域名（`*.bluearchive-cn.com`）只出现 5 个，共 12 条请求，其中 **POST 数为 0**。全是对 **静态资源 / state / health** 的拉取。 | **[确证]** |
| **C4** | **这个 HAR 不是「按 site 导出」。** `log` 只有 3 个键（无 `pages`/`comment`/`browser`），但 entry 横跨 12 个主机、含 5 个 bluearchive-cn 子域 —— 单站点导出不可能长这样。 | **[确证]** |
| **C5** | **`_id` 是 1..57 连续无空洞**（仅并发批次有 ±2 ms 时间抖动）⇒ 导出没有跳过任何记录，Reqable 当时就只录到这些。 | **[确证]** |
| **C6** | **根因不是「解析漏了」，是抓包窗口处于维护期**：`state-api/api/state` 返回 `State:1` + `Msg:"服务器维护中，请耐心等待开服！"`，客户端按设计**不发出任何业务请求**。 | **[确证 + 项目内互证]** |
| **C7** | 旁证：全部 9 条 udata 埋点的 `#account_id` **始终为空**（含最后一条 12:36:59）⇒ udata 从未与游戏账号绑定。注意 `role_login`（`_id`=27）虽已上报，但角色 ID 早在 SDK 快登事件里就有缓存，**不是登录成功的证据**（见 §7.4）。 | **[确证]** |
| **C8** | 体量旁证：57 条响应体**合计仅 14,366 B**，最大一条是 9,724 B 的活动公告 HTML。「登录+大厅+一局战斗」不可能压缩到这个量级。 | **[确证]** |
| **C9** | ★ **决定性**：`_id`=1 是 udata 的 `#app_start`，`_id`=57 是 `#app_end`—— **文件正好覆盖一次 App 会话的首尾，中间无缺口**。⇒ 这段会话内的流量**没有被漏抓**，`account/auth` 是真的没发出。 | **[确证]** |

**一句话**：用户说的「完整流程」与文件内容不符。这份 HAR 是 **2026-11-11 20:34:40 → 20:36:59（北京时间，UTC+8）一次 App 会话的完整抓包**，内容 = 冷启动 → 资源清单 → SDK 登录 → 网关 state/health → 活动公告 WebView → 纯心跳遥测。**游戏协议段（1002/24000 及其后全部）根本没被发出过，因此也不可能被抓到。**

> **给用户的直接答复**：不是解析问题。这份 HAR 里**一个游戏协议包都没有**，而且**可以证明不是抓漏了**（§7.2）。要继续推进，唯一的路是**在开服后用新会话重抓**（§8）。

---

## §1 文件结构（全部键 + pages + comment）

### 1.1 顶层与 log

```text
顶层键 (1)  : ['log']
log 键 (3)   : ['version', 'creator', 'entries']
entries        : 57 条
creator        : {"name": "Reqable", "version": "3.3.11"}
version        : '1.2'
```

**标准 HAR 1.2 的 `log` 键存在性：**

| 键 | 状态 | 说明 |
|---|---|---|
| `version` | ✅ 存在 | `"1.2"` |
| `creator` | ✅ 存在 | `{"name":"Reqable","version":"3.3.11"}` |
| `browser` | ❌ **缺失** | 手机端抓包无浏览器语义，正常 |
| `pages` | ❌ **缺失** | **没有 pageRef 分组信息** |
| `entries` | ✅ 存在 | 57 条 |
| `comment` | ❌ **缺失** | 无任何导出备注 |

### 1.2 `pages` 与 `comment` 的实际内容

```text
log.pages   = <键不存在>
log.comment = None
entry._pageRef 分布: '<无>' x57   ← 57/57 条都没有 pageRef
```

> **这一条很重要**：HAR 规范里 site/分组信息存放在 `log.pages` + `entry.pageRef`。本文件两者全无，所以**无法从 HAR 头部读出「按哪个 site 导出」**。任何「这是按 udata 站点导出的」的说法，在这份文件里**没有元数据支撑**——但下面的 entry 层数据反过来证明它不是单站点导出（见 §4、§7）。

---

## §2 每条 entry 的完整字段审计

entry 总数 **57**。以下是**所有 entry 层键的并集**与出现次数：

| 键 | 出现次数 | 含义 |
|---|---|---|
| `_cid` | 57 | 连接 ID |
| `_clientAddress` | 57 | 源 IP（全 127.0.0.1） |
| `_clientAddressFamily` | 57 | 源 IP 族 |
| `_clientPort` | 57 | 源端口 |
| `_ctime` | 57 | 连接建立毫秒时间戳 |
| `_id` | 57 | Reqable 全局请求序号（1..57） |
| `_serverAddress` | 57 | 目标 IP |
| `_serverAddressFamily` | 57 | IP 族 |
| `_serverPort` | 57 | 目标端口（全 443） |
| `_sid` | 57 | 连接内请求序号 |
| `_stime` | 57 | 请求投递毫秒时间戳 |
| `_uid` | 57 | Reqable 记录 UUID |
| `cache` | 57 | 缓存对象（全为空 `{}`） |
| `comment` | 57 | 注释（全为空串） |
| `connection` | 57 | 连接号 |
| `request` | 57 | 请求对象 |
| `response` | 57 | 响应对象 |
| `serverIPAddress` | 57 | 目标 IP |
| `startedDateTime` | 57 | 请求开始时刻（UTC） |
| `time` | 57 | 总耗时 ms |
| `timings` | 57 | 分段耗时 |

### 2.1 专项检查：Reqable 私有 / 可能承载数据的字段

| 字段 | 命中 | 判定 |
|---|---|---|
| `_webSocketMessages` | 0/57 | **无 WebSocket 载荷** —— 不存在「游戏走 WS 被存在这里」的可能 |
| `_error` | 0/57 | 无抓取失败标记 |
| `_fromCache` | 0/57 | 无缓存命中标记 |
| `_resourceType` | 0/57 | 无资源类型分类 |
| `_reqable` | 0/57 | 无 Reqable 私有块 |
| `response.content.encoding == "base64"` | **0/57** | **无任何二进制响应体** |
| `comment` | 57/57 | 全为空串 `""` |
| `_pageRef` | 0/57 | 无分组关联 |

> **结论**：这个文件里**没有任何「隐藏的数据载体」**。没有 base64 二进制体、没有 WS 消息、没有 error 标记、没有私有块。响应内容全部以明文 `content.text` 存在 —— 也就是说，**如果里面有游戏包，它会以明文 JSON（`{"protocol":...}`）直接摆在那里，不可能被藏起来。**

### 2.2 57 条 entry 完整清单（按 `_id` 即抓包顺序）

`响应字节` 取 `response.content.size`；`内容类型` 取 `response.content.mimeType`。

| `_id` | 时间 (UTC) | 方法 | 完整 URL | 状态 | 响应字节 | 内容类型 |
|---|---|---|---|---|---|---|
| 1 | `12:34:40.814` | POST | `https://udata-api.open.yostar.net/daq/track/v2` | 200 | 51 | application/json |
| 2 | `12:34:41.382` | POST | `https://yostar-cn-client-logging.cn-shanghai.log.aliyuncs.com/logstores/yostar-cn-client-logging/shards/lb` | 200 | 0 | `(空)` |
| 3 | `12:34:41.380` | POST | `https://yostar-cn-netsdk-logging.cn-shanghai.log.aliyuncs.com/logstores/ipa-azurjxv6mz9tpgxxfxuhfn-raw/shards/lb` | 200 | 0 | `(空)` |
| 4 | `12:34:42.250` | GET | `https://state-api.bluearchive-cn.com/api/state` | 200 | 161 | application/json |
| 5 | `12:34:42.637` | GET | `https://gsqc-api.bluearchive-cn.com/api/state` | 200 | 676 | application/json |
| 6 | `12:34:43.185` | GET | `https://static.bluearchive-cn.com/prodm39/Manifest/Patch/202609291539/patch_assetmanifest` | 200 | 78 | application/octet-stream |
| 7 | `12:34:43.356` | GET | `https://static.bluearchive-cn.com/prodm39/Manifest/TableBundles/202610292033/TableManifestHash` | 200 | 10 | application/octet-stream |
| 8 | `12:34:43.572` | GET | `https://static.bluearchive-cn.com/prodm39/Manifest/MediaResources/202610221638/MediaManifestHash` | 200 | 11 | application/octet-stream |
| 9 | `12:34:44.140` | POST | `https://yostar-cn-netsdk-logging.cn-shanghai.log.aliyuncs.com/logstores/ipa-azurjxv6mz9tpgxxfxuhfn-raw/shards/lb` | 200 | 0 | `(空)` |
| 10 | `12:34:44.319` | GET | `https://static.bluearchive-cn.com/prodm39/AssetBundles/Catalog/202610221737/Android/bundleDownloadInfo.hash` | 200 | 10 | application/octet-stream |
| 11 | `12:34:44.534` | GET | `https://static.bluearchive-cn.com/prodm39/AssetBundles/Catalog/202610221737/Android/catalog_Android.hash` | 200 | 32 | application/octet-stream |
| 12 | `12:34:45.138` | POST | `https://yostar-cn-client-logging.cn-shanghai.log.aliyuncs.com/logstores/yostar-cn-client-logging/shards/lb` | 200 | 0 | `(空)` |
| 13 | `12:34:49.262` | POST | `https://sdk-api.yostar.cn/user/quick-login` | 200 | 787 | application/json |
| 14 | `12:34:49.299` | GET | `https://static.bluearchive-cn.com/checkhealth.html` | 200 | 509 | text/html |
| 15 | `12:34:49.511` | GET | `https://static.bluearchive-cn.com/checkhealth.html` | 200 | 509 | text/html |
| 16 | `12:34:49.528` | POST | `https://sdk-api.yostar.cn/user/detail` | 200 | 787 | application/json |
| 17 | `12:34:49.699` | POST | `https://sdk-api.yostar.cn/health-game/duration` | 200 | 65 | application/json |
| 18 | `12:34:49.958` | GET | `https://sdk-api.yostar.cn` | 200 | 44 | application/json |
| 19 | `12:34:49.959` | GET | `https://sdk-api.yostar.cn` | 200 | 44 | application/json |
| 20 | `12:34:49.829` | POST | `https://udata-api.open.yostar.net/daq/track/v2` | 200 | 51 | application/json |
| 21 | `12:34:49.834` | POST | `https://sdk-api.yostar.cn/common/geo-ip` | 200 | 51 | application/json |
| 22 | `12:34:49.956` | POST | `https://sdk-api.yostar.cn/heartbeat/pulse` | 200 | 45 | application/json |
| 23 | `12:34:50.465` | GET | `https://gs-api.bluearchive-cn.com/api/health` | 200 | 2 | text/plain |
| 24 | `12:34:50.468` | GET | `https://gs-api.bluearchive-cn.com/api/health` | 200 | 2 | text/plain |
| 25 | `12:34:50.880` | POST | `https://udata-api.open.yostar.net/daq/track/v2` | 200 | 51 | application/json |
| 26 | `12:34:51.273` | POST | `https://app.adjust.cn/event` | 200 | 70 | application/json |
| 27 | `12:34:51.059` | POST | `https://udata-api.open.yostar.net/daq/track/v2` | 200 | 51 | application/json |
| 28 | `12:34:52.747` | GET | `https://customer.yostar.net/api/open/red_point?player_uid=10015354380&game_pid=CN-BA&sdk_uid=1013178778&device_id=4885e393b419e04f` | 200 | 50 | application/json |
| 29 | `12:34:52.480` | POST | `https://yostar-cn-client-logging.cn-shanghai.log.aliyuncs.com/logstores/yostar-cn-client-logging/shards/lb` | 200 | 0 | `(空)` |
| 30 | `12:34:53.143` | POST | `https://yostar-cn-netsdk-logging.cn-shanghai.log.aliyuncs.com/logstores/ipa-azurjxv6mz9tpgxxfxuhfn-raw/shards/lb` | 200 | 0 | `(空)` |
| 31 | `12:34:53.783` | GET | `https://customer.yostar.net/api/open/red_point?player_uid=10015354380&game_pid=CN-BA&sdk_uid=1013178778&device_id=4885e393b419e04f` | 200 | 50 | application/json |
| 32 | `12:34:55.728` | POST | `https://yostar-cn-client-logging.cn-shanghai.log.aliyuncs.com/logstores/yostar-cn-client-logging/shards/lb` | 200 | 0 | `(空)` |
| 33 | `12:34:56.443` | GET | `https://notice.bluearchive-cn.com/static/event/694ad7600be7531d7fde26291629fad2.html` | 200 | 9724 | text/html |
| 34 | `12:34:56.580` | CONNECT | `https://webcnstatic.yostar.net` | 0 | 0 | — |
| 35 | `12:34:56.580` | CONNECT | `https://webcnstatic.yostar.net` | 0 | 0 | — |
| 36 | `12:34:56.591` | CONNECT | `https://webcnstatic.yostar.net` | 0 | 0 | — |
| 37 | `12:34:56.592` | CONNECT | `https://webcnstatic.yostar.net` | 0 | 0 | — |
| 38 | `12:34:56.592` | CONNECT | `https://webcnstatic.yostar.net` | 0 | 0 | — |
| 39 | `12:34:56.593` | CONNECT | `https://webcnstatic.yostar.net` | 0 | 0 | — |
| 40 | `12:34:59.144` | POST | `https://yostar-cn-netsdk-logging.cn-shanghai.log.aliyuncs.com/logstores/ipa-azurjxv6mz9tpgxxfxuhfn-raw/shards/lb` | 200 | 0 | `(空)` |
| 41 | `12:35:01.732` | POST | `https://yostar-cn-client-logging.cn-shanghai.log.aliyuncs.com/logstores/yostar-cn-client-logging/shards/lb` | 200 | 0 | `(空)` |
| 42 | `12:35:05.146` | POST | `https://yostar-cn-netsdk-logging.cn-shanghai.log.aliyuncs.com/logstores/ipa-azurjxv6mz9tpgxxfxuhfn-raw/shards/lb` | 200 | 0 | `(空)` |
| 43 | `12:35:06.734` | POST | `https://yostar-cn-client-logging.cn-shanghai.log.aliyuncs.com/logstores/yostar-cn-client-logging/shards/lb` | 200 | 0 | `(空)` |
| 44 | `12:36:12.222` | POST | `https://udata-api.open.yostar.net/daq/track/v2` | 200 | 51 | application/json |
| 45 | `12:36:17.294` | POST | `https://yostar-cn-client-logging.cn-shanghai.log.aliyuncs.com/logstores/yostar-cn-client-logging/shards/lb` | 200 | 0 | `(空)` |
| 46 | `12:36:23.708` | POST | `https://sdk-api.yostar.cn/heartbeat/pulse` | 200 | 45 | application/json |
| 47 | `12:36:24.204` | POST | `https://udata-api.open.yostar.net/daq/track/v2` | 200 | 51 | application/json |
| 48 | `12:36:27.270` | POST | `https://yostar-cn-client-logging.cn-shanghai.log.aliyuncs.com/logstores/yostar-cn-client-logging/shards/lb` | 200 | 0 | `(空)` |
| 49 | `12:36:28.278` | POST | `https://udata-api.open.yostar.net/daq/track/v2` | 200 | 51 | application/json |
| 50 | `12:36:32.272` | POST | `https://yostar-cn-client-logging.cn-shanghai.log.aliyuncs.com/logstores/yostar-cn-client-logging/shards/lb` | 200 | 0 | `(空)` |
| 51 | `12:36:52.282` | POST | `https://sdk-api.yostar.cn/heartbeat/pulse` | 200 | 45 | application/json |
| 52 | `12:36:52.738` | POST | `https://udata-api.open.yostar.net/daq/track/v2` | 200 | 51 | application/json |
| 53 | `12:36:56.087` | GET | `https://customer.yostar.net/api/open/red_point?player_uid=10015354380&game_pid=CN-BA&sdk_uid=1013178778&device_id=4885e393b419e04f` | 200 | 50 | application/json |
| 54 | `12:36:56.088` | POST | `https://yostar-cn-client-logging.cn-shanghai.log.aliyuncs.com/logstores/yostar-cn-client-logging/shards/lb` | 200 | 0 | `(空)` |
| 55 | `12:36:57.194` | GET | `https://customer.yostar.net/api/open/red_point?player_uid=10015354380&game_pid=CN-BA&sdk_uid=1013178778&device_id=4885e393b419e04f` | 200 | 50 | application/json |
| 56 | `12:36:59.068` | POST | `https://yostar-cn-client-logging.cn-shanghai.log.aliyuncs.com/logstores/yostar-cn-client-logging/shards/lb` | 200 | 0 | `(空)` |
| 57 | `12:36:59.568` | POST | `https://udata-api.open.yostar.net/daq/track/v2` | 200 | 51 | application/json |

---

## §3 时间跨度分析

| 项目 | 值 |
|---|---|
| 最早 | `2026-11-11T12:34:40.814Z` = **北京时间 2026-11-11 20:34:40** （`_id`=1）|
| 最晚 | `2026-11-11T12:36:59.568Z` = **北京时间 2026-11-11 20:36:59** （`_id`=57）|
| **总跨度** | **138.8 秒 = 2.31 分钟** |
| 相邻间隔中位数 | 0.46 秒（绝大多数是并发的批量请求）|
| 最大空洞 | **65.49 秒**（`_id` 43 → 44，12:35:06.734 → 12:36:12.222）|

**分段还原（把 57 条按意图归并）：**

| 相对时刻 | `_id` | 事件 |
|---|---|---|
| +0.0s | 1 | udata 埋点 `#app_start`（客户端冷启动） |
| +0.6s | 2-3 | 阿里云日志上报 ×2 |
| +1.4s | 4 | **`state-api/api/state`** → `Servers` 列表 + `State:1` **维护中文案** |
| +1.8s | 5 | **`gsqc-api/api/state`** → 676 B 网关配置（4 个版本号 / 3 条 CDN 根） |
| +2.4s～+3.7s | 6-11 | static CDN：Patch / TableBundles / MediaResources / Catalog 清单与哈希 |
| +8.5s | 13 | **`sdk-api.yostar.cn/user/quick-login`** → 200，`User.ID=1013178778` |
| +8.7s | 16 | `sdk-api/user/detail` → 同一份 787 B 用户信息 |
| +8.9s | 17,21,22 | `health-game/duration`（防沉迷，回「用户已成年」）、`geo-ip`、`heartbeat/pulse` |
| +9.7s | 23-24 | **`gs-api/api/health` ×2** → 纯文本 `ok` |
| +12.0s | 26,28,31,53,55 | `customer.yostar.net/api/open/red_point` 轮询 ×4 |
| +15.8s | 33 | **活动公告 WebView** `notice.bluearchive-cn.com/.../*.html`（11/12 活动预告） |
| +15.8s | 34-39 | **6 条 `CONNECT webcnstatic.yostar.net`**（公告配图，未解密，status 0） |
| +18s～+26s | 40-43 | 仅遥测（netsdk-logging ×2、client-logging ×2） |
| **+65.5s 空洞** | — | （用户在公告/维护弹窗上停留） |
| +91s～+139s | 44-57 | **只剩遥测**：udata ×4、client-logging ×3、netsdk ×2、`heartbeat/pulse` ×2、`red_point` ×2。**零游戏服请求** |

**关键判读**：

1. 跨度只有 **2 分 19 秒**，且**最后 47 秒全是心跳/遥测**——这不像「登录→大厅→打一局战斗」（一局战斗本身就要 2–5 分钟，加上大厅往返，最短也要 5–10 分钟）。
2. 请求**密度极高**（中位间隔 0.46 s）且集中在头 26 秒，是典型的**冷启动爆发**。
3. `+9.7s` 的 `gs-api/api/health` 是**网关可达性探针**——它正常返回了 `ok`，**而紧接着就应该出现 `POST /api/account/auth`。它没有出现，而且此后再无任何游戏服请求。**

---

## §4 按主机分组的完整路径清单（URL 不截断）

**不同主机数：12**

### `udata-api.open.yostar.net` — 9 条 / 1 个路径　（遥测埋点 · udata）

| 方法 | 路径 | 次数 |
|---|---|---|
| POST | `/daq/track/v2` | 9 |

### `yostar-cn-client-logging.cn-shanghai.log.aliyuncs.com` — 11 条 / 1 个路径　（遥测日志 · 阿里云 SLS）

| 方法 | 路径 | 次数 |
|---|---|---|
| POST | `/logstores/yostar-cn-client-logging/shards/lb` | 11 |

### `customer.yostar.net` — 4 条 / 1 个路径　（悠星基础设施）

| 方法 | 路径 | 次数 |
|---|---|---|
| GET | `/api/open/red_point?player_uid=10015354380&game_pid=CN-BA&sdk_uid=1013178778&device_id=4885e393b419e04f` | 4 |

### `sdk-api.yostar.cn` — 9 条 / 6 个路径　（悠星 SDK）

| 方法 | 路径 | 次数 |
|---|---|---|
| POST | `/heartbeat/pulse` | 3 |
| POST | `/common/geo-ip` | 1 |
| GET | `/` | 2 |
| POST | `/health-game/duration` | 1 |
| POST | `/user/detail` | 1 |
| POST | `/user/quick-login` | 1 |

### `yostar-cn-netsdk-logging.cn-shanghai.log.aliyuncs.com` — 5 条 / 1 个路径　（遥测日志 · 阿里云 SLS）

| 方法 | 路径 | 次数 |
|---|---|---|
| POST | `/logstores/ipa-azurjxv6mz9tpgxxfxuhfn-raw/shards/lb` | 5 |

### `webcnstatic.yostar.net` — 6 条 / 1 个路径　（悠星基础设施）

| 方法 | 路径 | 次数 |
|---|---|---|
| CONNECT | `/` | 6 |

### `notice.bluearchive-cn.com` — 1 条 / 1 个路径　（官方内容分发 / 静态）

| 方法 | 路径 | 次数 |
|---|---|---|
| GET | `/static/event/694ad7600be7531d7fde26291629fad2.html` | 1 |

### `app.adjust.cn` — 1 条 / 1 个路径　（第三方归因 · Adjust）

| 方法 | 路径 | 次数 |
|---|---|---|
| POST | `/event` | 1 |

### `gs-api.bluearchive-cn.com` — 2 条 / 1 个路径　（**官方游戏服 / 网关**）

| 方法 | 路径 | 次数 |
|---|---|---|
| GET | `/api/health` | 2 |

### `static.bluearchive-cn.com` — 7 条 / 6 个路径　（官方内容分发 / 静态）

| 方法 | 路径 | 次数 |
|---|---|---|
| GET | `/checkhealth.html` | 2 |
| GET | `/prodm39/AssetBundles/Catalog/202610221737/Android/catalog_Android.hash` | 1 |
| GET | `/prodm39/AssetBundles/Catalog/202610221737/Android/bundleDownloadInfo.hash` | 1 |
| GET | `/prodm39/Manifest/MediaResources/202610221638/MediaManifestHash` | 1 |
| GET | `/prodm39/Manifest/TableBundles/202610292033/TableManifestHash` | 1 |
| GET | `/prodm39/Manifest/Patch/202609291539/patch_assetmanifest` | 1 |

### `gsqc-api.bluearchive-cn.com` — 1 条 / 1 个路径　（**官方游戏服 / 网关**）

| 方法 | 路径 | 次数 |
|---|---|---|
| GET | `/api/state` | 1 |

### `state-api.bluearchive-cn.com` — 1 条 / 1 个路径　（**官方游戏服 / 网关**）

| 方法 | 路径 | 次数 |
|---|---|---|
| GET | `/api/state` | 1 |

### 4.1 游戏协议关键词命中表

在**全部 57 条 URL 的 path 段**上做大小写不敏感子串匹配：

| 关键词 | 命中 | | 关键词 | 命中 |
|---|---|---|---|---|
| `account/auth` | **0** | | `auth` | **0** |
| `academy` | **0** | | `getinfo` | **0** |
| `lobby` | **0** | | `character` | **0** |
| `item` | **0** | | `battle` | **0** |
| `campaign` | **0** | | `mission` | **0** |
| `gacha` | **0** | | `cafe` | **0** |
| `shop` | **0** | | `mail` | **0** |
| `friend` | **0** | | `raid` | **0** |
| `arena` | **0** | | `state` | **2** |

**唯一非零命中：`['state']`** —— 就是那两条 `/api/state`，它们是**服务器状态查询**，不是协议包。

再放宽到**整个 URL（含 host 与 query）**搜索：

```text
auth       0
academy    0
getinfo    0
lobby      0
battle     0
gacha      0
mail       0
shop       0
raid       0
arena      0
```

**⇒ `auth` / `academy` / `getinfo` 在整个 HAR 的 URL 里出现 0 次。**

---

## §5 响应体内容抽样（前 80 字节 hex + ascii）

### 5.1 全量统计

| `content.mimeType` | 条数 |
|---|---|
| `application/json` | 25 |
| `None` | 22 |
| `application/octet-stream` | 5 |
| `text/html` | 3 |
| `text/plain` | 2 |

- `encoding == "base64"` 的响应体：**0 条**
- 含 `_webSocketMessages` 的条目：**0 条**
- 含 `_error` 的条目：**0 条**
- 响应体总字节：**14,366 B**（最大 9,724 B）

### 5.2 每一条的 hex / ascii 首 80 字节

`<text 字段缺失>` 的 6 条即 CONNECT 隧道存根（`status=0`、`time=-1`、无响应头）。

| `_id` | 主机 · 路径 | 长度 | 判定 | hex（前 80B）| ascii（前 80B）|
|---|---|---|---|---|---|
| 1 | `udata-api.open.yostar.net/daq/track/v2` | 51 | JSON | `7b 22 63 6f 64 65 22 3a 32 30 30 2c 22 64 61 74 61 22 3a 7b 22 74 73 22 3a 31 37 39 34 34 30 30 34 38 30 33 38 39 7d 2c 22 6d 73 67 22 3a 22 4f 4b 22 7d` | `{"code":200,"data":{"ts":1794400480389},"msg":"OK"}` |
| 2 | `yostar-cn-client-logging.cn-shanghai.log.aliyuncs.com/logs` | 0 | 空体 | `—` | `—` |
| 3 | `yostar-cn-netsdk-logging.cn-shanghai.log.aliyuncs.com/logs` | 0 | 空体 | `—` | `—` |
| 4 | `state-api.bluearchive-cn.com/api/state` | 161 | JSON | `7b 22 53 65 72 76 65 72 73 22 3a 5b 22 68 74 74 70 73 3a 2f 2f 67 73 71 63 2d 61 70 69 2e 62 6c 75 65 61 72 63 68 69 76 65 2d 63 6e 2e 63 6f 6d 2f 61 70 69 2f 22 2c 22 68 74 74 70 73 3a 2f 2f 67 73 2d 61 70 69 2e 62 6c 75 65 61 72 63 68 69` | `{"Servers":["https://gsqc-api.bluearchive-cn.com/api/","https://gs-api.bluearchi` |
| 5 | `gsqc-api.bluearchive-cn.com/api/state` | 676 | JSON | `7b 22 43 61 6c 6c 62 61 63 6b 55 72 6c 22 3a 22 7b 5c 22 6f 72 64 65 72 5f 6e 6f 74 69 66 79 5c 22 3a 5c 22 68 74 74 70 3a 2f 2f 67 73 2d 69 6e 74 65 72 2e 62 6c 75 65 61 72 63 68 69 76 65 2d 63 6e 2e 63 6f 6d 3a 34 30 30 30 2f 61 70 69 2f` | `{"CallbackUrl":"{\"order_notify\":\"http://gs-inter.bluearchive-cn.com:4000/api/` |
| 6 | `static.bluearchive-cn.com/prodm39/Manifest/Patch/202609291` | 78 | 文本 | `33 5f 30 5f 32 2c 61 33 36 64 39 66 65 35 39 33 30 30 66 37 62 62 39 64 36 33 35 66 32 65 30 32 32 33 34 33 33 33 0a 33 5f 30 5f 33 2c 61 33 36 64 39 66 65 35 39 33 30 30 66 37 62 62 39 64 36 33 35 66 32 65 30 32 32 33 34 33 33 33 0a` | `3_0_2,a36d9fe59300f7bb9d635f2e02234333.3_0_3,a36d9fe59300f7bb9d635f2e02234333.` |
| 7 | `static.bluearchive-cn.com/prodm39/Manifest/TableBundles/20` | 10 | 文本 | `31 37 30 33 38 33 30 37 30 0a` | `170383070.` |
| 8 | `static.bluearchive-cn.com/prodm39/Manifest/MediaResources/` | 11 | 文本 | `33 36 30 38 35 31 36 31 39 31 0a` | `3608516191.` |
| 9 | `yostar-cn-netsdk-logging.cn-shanghai.log.aliyuncs.com/logs` | 0 | 空体 | `—` | `—` |
| 10 | `static.bluearchive-cn.com/prodm39/AssetBundles/Catalog/202` | 10 | 文本 | `31 31 30 35 30 32 30 38 37 35` | `1105020875` |
| 11 | `static.bluearchive-cn.com/prodm39/AssetBundles/Catalog/202` | 32 | 文本 | `34 34 31 63 62 33 65 33 65 66 35 39 37 33 32 39 35 39 64 39 35 64 32 33 37 65 36 31 33 30 30 61` | `441cb3e3ef59732959d95d237e61300a` |
| 12 | `yostar-cn-client-logging.cn-shanghai.log.aliyuncs.com/logs` | 0 | 空体 | `—` | `—` |
| 13 | `sdk-api.yostar.cn/user/quick-login` | 787 | JSON | `7b 22 43 6f 64 65 22 3a 32 30 30 2c 22 4d 73 67 22 3a 22 4f 4b 22 2c 22 44 61 74 61 22 3a 7b 22 44 65 73 74 72 6f 79 22 3a 7b 22 44 65 73 74 72 6f 79 41 74 22 3a 30 7d 2c 22 49 64 65 6e 74 69 74 79 22 3a 7b 22 54 79 70 65 22 3a 30 2c 22 52` | `{"Code":200,"Msg":"OK","Data":{"Destroy":{"DestroyAt":0},"Identity":{"Type":0,"R` |
| 14 | `static.bluearchive-cn.com/checkhealth.html` | 509 | HTML | `3c 21 44 4f 43 54 59 50 45 20 68 74 6d 6c 20 50 55 42 4c 49 43 20 22 2d 2f 2f 57 33 43 2f 2f 44 54 44 20 48 54 4d 4c 20 34 2e 30 31 2f 2f 45 4e 22 20 22 68 74 74 70 3a 2f 2f 77 77 77 2e 77 33 2e 6f 72 67 2f 54 52 2f 68 74 6d 6c 34 2f 73 74` | `<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/st` |
| 15 | `static.bluearchive-cn.com/checkhealth.html` | 509 | HTML | `3c 21 44 4f 43 54 59 50 45 20 68 74 6d 6c 20 50 55 42 4c 49 43 20 22 2d 2f 2f 57 33 43 2f 2f 44 54 44 20 48 54 4d 4c 20 34 2e 30 31 2f 2f 45 4e 22 20 22 68 74 74 70 3a 2f 2f 77 77 77 2e 77 33 2e 6f 72 67 2f 54 52 2f 68 74 6d 6c 34 2f 73 74` | `<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/st` |
| 16 | `sdk-api.yostar.cn/user/detail` | 787 | JSON | `7b 22 43 6f 64 65 22 3a 32 30 30 2c 22 4d 73 67 22 3a 22 4f 4b 22 2c 22 44 61 74 61 22 3a 7b 22 44 65 73 74 72 6f 79 22 3a 7b 22 44 65 73 74 72 6f 79 41 74 22 3a 30 7d 2c 22 49 64 65 6e 74 69 74 79 22 3a 7b 22 54 79 70 65 22 3a 30 2c 22 52` | `{"Code":200,"Msg":"OK","Data":{"Destroy":{"DestroyAt":0},"Identity":{"Type":0,"R` |
| 17 | `sdk-api.yostar.cn/health-game/duration` | 65 | JSON | `7b 22 43 6f 64 65 22 3a 31 31 30 31 37 30 2c 22 4d 73 67 22 3a 22 e7 94 a8 e6 88 b7 e5 b7 b2 e6 88 90 e5 b9 b4 2c e4 b8 8d e9 9c 80 e8 a6 81 e8 ae a1 e6 97 b6 22 2c 22 44 61 74 61 22 3a 7b 7d 7d` | `{"Code":110170,"Msg":"...............,...............","Data":{}}` |
| 18 | `sdk-api.yostar.cn/` | 44 | JSON | `7b 22 43 6f 64 65 22 3a 32 30 30 2c 22 4d 73 67 22 3a 22 4f 4b 22 2c 22 44 61 74 61 22 3a 22 48 65 6c 6c 6f 20 77 6f 72 6c 64 22 7d` | `{"Code":200,"Msg":"OK","Data":"Hello world"}` |
| 19 | `sdk-api.yostar.cn/` | 44 | JSON | `7b 22 43 6f 64 65 22 3a 32 30 30 2c 22 4d 73 67 22 3a 22 4f 4b 22 2c 22 44 61 74 61 22 3a 22 48 65 6c 6c 6f 20 77 6f 72 6c 64 22 7d` | `{"Code":200,"Msg":"OK","Data":"Hello world"}` |
| 20 | `udata-api.open.yostar.net/daq/track/v2` | 51 | JSON | `7b 22 63 6f 64 65 22 3a 32 30 30 2c 22 64 61 74 61 22 3a 7b 22 74 73 22 3a 31 37 39 34 34 30 30 34 38 39 34 32 38 7d 2c 22 6d 73 67 22 3a 22 4f 4b 22 7d` | `{"code":200,"data":{"ts":1794400489428},"msg":"OK"}` |
| 21 | `sdk-api.yostar.cn/common/geo-ip` | 51 | JSON | `7b 22 43 6f 64 65 22 3a 32 30 30 2c 22 4d 73 67 22 3a 22 4f 4b 22 2c 22 44 61 74 61 22 3a 7b 22 50 72 6f 76 22 3a 22 e6 b5 99 e6 b1 9f e7 9c 81 22 7d 7d` | `{"Code":200,"Msg":"OK","Data":{"Prov":"........."}}` |
| 22 | `sdk-api.yostar.cn/heartbeat/pulse` | 45 | JSON | `7b 22 43 6f 64 65 22 3a 32 30 30 2c 22 4d 73 67 22 3a 22 4f 4b 22 2c 22 44 61 74 61 22 3a 7b 22 44 65 6c 61 79 22 3a 33 36 30 30 7d 7d` | `{"Code":200,"Msg":"OK","Data":{"Delay":3600}}` |
| 23 | `gs-api.bluearchive-cn.com/api/health` | 2 | 文本 | `6f 6b` | `ok` |
| 24 | `gs-api.bluearchive-cn.com/api/health` | 2 | 文本 | `6f 6b` | `ok` |
| 25 | `udata-api.open.yostar.net/daq/track/v2` | 51 | JSON | `7b 22 63 6f 64 65 22 3a 32 30 30 2c 22 64 61 74 61 22 3a 7b 22 74 73 22 3a 31 37 39 34 34 30 30 34 39 30 34 37 30 7d 2c 22 6d 73 67 22 3a 22 4f 4b 22 7d` | `{"code":200,"data":{"ts":1794400490470},"msg":"OK"}` |
| 26 | `app.adjust.cn/event` | 70 | JSON | `7b 22 61 70 70 5f 74 6f 6b 65 6e 22 3a 22 6b 62 78 38 68 6c 69 6f 38 64 66 6b 22 2c 22 61 64 69 64 22 3a 22 39 64 63 36 34 66 64 35 62 32 64 34 34 65 30 31 31 35 34 33 33 34 32 36 31 35 39 66 34 32 64 36 22 7d` | `{"app_token":"kbx8hlio8dfk","adid":"9dc64fd5b2d44e0115433426159f42d6"}` |
| 27 | `udata-api.open.yostar.net/daq/track/v2` | 51 | JSON | `7b 22 63 6f 64 65 22 3a 32 30 30 2c 22 64 61 74 61 22 3a 7b 22 74 73 22 3a 31 37 39 34 34 30 30 34 39 30 37 32 38 7d 2c 22 6d 73 67 22 3a 22 4f 4b 22 7d` | `{"code":200,"data":{"ts":1794400490728},"msg":"OK"}` |
| 28 | `customer.yostar.net/api/open/red_point` | 50 | JSON | `7b 22 43 6f 64 65 22 3a 32 30 30 2c 22 44 61 74 61 22 3a 7b 22 72 65 64 5f 70 6f 69 6e 74 22 3a 66 61 6c 73 65 7d 2c 22 4d 73 67 22 3a 22 4f 4b 22 7d` | `{"Code":200,"Data":{"red_point":false},"Msg":"OK"}` |
| 29 | `yostar-cn-client-logging.cn-shanghai.log.aliyuncs.com/logs` | 0 | 空体 | `—` | `—` |
| 30 | `yostar-cn-netsdk-logging.cn-shanghai.log.aliyuncs.com/logs` | 0 | 空体 | `—` | `—` |
| 31 | `customer.yostar.net/api/open/red_point` | 50 | JSON | `7b 22 43 6f 64 65 22 3a 32 30 30 2c 22 44 61 74 61 22 3a 7b 22 72 65 64 5f 70 6f 69 6e 74 22 3a 66 61 6c 73 65 7d 2c 22 4d 73 67 22 3a 22 4f 4b 22 7d` | `{"Code":200,"Data":{"red_point":false},"Msg":"OK"}` |
| 32 | `yostar-cn-client-logging.cn-shanghai.log.aliyuncs.com/logs` | 0 | 空体 | `—` | `—` |
| 33 | `notice.bluearchive-cn.com/static/event/694ad7600be7531d7fd` | 9724 | HTML | `3c 21 44 4f 43 54 59 50 45 20 68 74 6d 6c 3e 20 3c 68 74 6d 6c 3e 20 3c 68 65 61 64 3e 3c 6d 65 74 61 20 63 68 61 72 73 65 74 3d 22 55 54 46 2d 38 22 3e 20 3c 2f 68 65 61 64 3e 20 3c 62 6f 64 79 3e 20 3c 70 3e 3c 73 70 61 6e 20 73 74 79 6c` | `<!DOCTYPE html> <html> <head><meta charset="UTF-8"> </head> <body> <p><span styl` |
| 34 | `webcnstatic.yostar.net/` | – | **CONNECT 隧道** | – | – |
| 35 | `webcnstatic.yostar.net/` | – | **CONNECT 隧道** | – | – |
| 36 | `webcnstatic.yostar.net/` | – | **CONNECT 隧道** | – | – |
| 37 | `webcnstatic.yostar.net/` | – | **CONNECT 隧道** | – | – |
| 38 | `webcnstatic.yostar.net/` | – | **CONNECT 隧道** | – | – |
| 39 | `webcnstatic.yostar.net/` | – | **CONNECT 隧道** | – | – |
| 40 | `yostar-cn-netsdk-logging.cn-shanghai.log.aliyuncs.com/logs` | 0 | 空体 | `—` | `—` |
| 41 | `yostar-cn-client-logging.cn-shanghai.log.aliyuncs.com/logs` | 0 | 空体 | `—` | `—` |
| 42 | `yostar-cn-netsdk-logging.cn-shanghai.log.aliyuncs.com/logs` | 0 | 空体 | `—` | `—` |
| 43 | `yostar-cn-client-logging.cn-shanghai.log.aliyuncs.com/logs` | 0 | 空体 | `—` | `—` |
| 44 | `udata-api.open.yostar.net/daq/track/v2` | 51 | JSON | `7b 22 63 6f 64 65 22 3a 32 30 30 2c 22 64 61 74 61 22 3a 7b 22 74 73 22 3a 31 37 39 34 34 30 30 35 37 31 39 30 36 7d 2c 22 6d 73 67 22 3a 22 4f 4b 22 7d` | `{"code":200,"data":{"ts":1794400571906},"msg":"OK"}` |
| 45 | `yostar-cn-client-logging.cn-shanghai.log.aliyuncs.com/logs` | 0 | 空体 | `—` | `—` |
| 46 | `sdk-api.yostar.cn/heartbeat/pulse` | 45 | JSON | `7b 22 43 6f 64 65 22 3a 32 30 30 2c 22 4d 73 67 22 3a 22 4f 4b 22 2c 22 44 61 74 61 22 3a 7b 22 44 65 6c 61 79 22 3a 33 36 30 30 7d 7d` | `{"Code":200,"Msg":"OK","Data":{"Delay":3600}}` |
| 47 | `udata-api.open.yostar.net/daq/track/v2` | 51 | JSON | `7b 22 63 6f 64 65 22 3a 32 30 30 2c 22 64 61 74 61 22 3a 7b 22 74 73 22 3a 31 37 39 34 34 30 30 35 38 33 38 34 30 7d 2c 22 6d 73 67 22 3a 22 4f 4b 22 7d` | `{"code":200,"data":{"ts":1794400583840},"msg":"OK"}` |
| 48 | `yostar-cn-client-logging.cn-shanghai.log.aliyuncs.com/logs` | 0 | 空体 | `—` | `—` |
| 49 | `udata-api.open.yostar.net/daq/track/v2` | 51 | JSON | `7b 22 63 6f 64 65 22 3a 32 30 30 2c 22 64 61 74 61 22 3a 7b 22 74 73 22 3a 31 37 39 34 34 30 30 35 38 38 30 31 34 7d 2c 22 6d 73 67 22 3a 22 4f 4b 22 7d` | `{"code":200,"data":{"ts":1794400588014},"msg":"OK"}` |
| 50 | `yostar-cn-client-logging.cn-shanghai.log.aliyuncs.com/logs` | 0 | 空体 | `—` | `—` |
| 51 | `sdk-api.yostar.cn/heartbeat/pulse` | 45 | JSON | `7b 22 43 6f 64 65 22 3a 32 30 30 2c 22 4d 73 67 22 3a 22 4f 4b 22 2c 22 44 61 74 61 22 3a 7b 22 44 65 6c 61 79 22 3a 33 36 30 30 7d 7d` | `{"Code":200,"Msg":"OK","Data":{"Delay":3600}}` |
| 52 | `udata-api.open.yostar.net/daq/track/v2` | 51 | JSON | `7b 22 63 6f 64 65 22 3a 32 30 30 2c 22 64 61 74 61 22 3a 7b 22 74 73 22 3a 31 37 39 34 34 30 30 36 31 32 34 30 34 7d 2c 22 6d 73 67 22 3a 22 4f 4b 22 7d` | `{"code":200,"data":{"ts":1794400612404},"msg":"OK"}` |
| 53 | `customer.yostar.net/api/open/red_point` | 50 | JSON | `7b 22 43 6f 64 65 22 3a 32 30 30 2c 22 44 61 74 61 22 3a 7b 22 72 65 64 5f 70 6f 69 6e 74 22 3a 66 61 6c 73 65 7d 2c 22 4d 73 67 22 3a 22 4f 4b 22 7d` | `{"Code":200,"Data":{"red_point":false},"Msg":"OK"}` |
| 54 | `yostar-cn-client-logging.cn-shanghai.log.aliyuncs.com/logs` | 0 | 空体 | `—` | `—` |
| 55 | `customer.yostar.net/api/open/red_point` | 50 | JSON | `7b 22 43 6f 64 65 22 3a 32 30 30 2c 22 44 61 74 61 22 3a 7b 22 72 65 64 5f 70 6f 69 6e 74 22 3a 66 61 6c 73 65 7d 2c 22 4d 73 67 22 3a 22 4f 4b 22 7d` | `{"Code":200,"Data":{"red_point":false},"Msg":"OK"}` |
| 56 | `yostar-cn-client-logging.cn-shanghai.log.aliyuncs.com/logs` | 0 | 空体 | `—` | `—` |
| 57 | `udata-api.open.yostar.net/daq/track/v2` | 51 | JSON | `7b 22 63 6f 64 65 22 3a 32 30 30 2c 22 64 61 74 61 22 3a 7b 22 74 73 22 3a 31 37 39 34 34 30 30 36 31 39 32 33 31 7d 2c 22 6d 73 67 22 3a 22 4f 4b 22 7d` | `{"code":200,"data":{"ts":1794400619231},"msg":"OK"}` |

### 5.3 三个关键响应体的原文

**① `_id`=4 `GET https://state-api.bluearchive-cn.com/api/state`（161 B）—— 维护态的直接证据**

```json
{
  "Servers": [
    "https://gsqc-api.bluearchive-cn.com/api/",
    "https://gs-api.bluearchive-cn.com/api/"
  ],
  "State": 1,
  "Msg": "服务器维护中，请耐心等待开服！"
}
```

**② `_id`=5 `GET https://gsqc-api.bluearchive-cn.com/api/state`（676 B）—— 网关配置（`Servers[0]` 就指向它自己）**

```json
{
  "CallbackUrl": "{\"order_notify\":\"http://gs-inter.bluearchive-cn.com:4000/api/order/notify\",\"survey_notify\":\"http://gs-inter.bluearchive-cn.com:4000\",\"web_notify\":\"http://gs-inter.bluearchive-cn.com:4000/api/web/notify\",\"account_logout\":\"http://gs-inter.bluearchive-cn.com:4000/api/account/logout\"}",
  "CustomerServiceUrl": "",
  "AddressablesCatalogUrlRoots": [
    "https://static.bluearchive-cn.com/prodm39",
    "https://static-qc.bluearchive-cn.com/prodm39",
    "https://static-hs.bluearchive-cn.com/prodm39"
  ],
  "ResourceVersion": "202610221737",
  "TableVersion": "202610292033",
  "MediaVersion": "202610221638",
  "PatchVersion": "202609291539",
  "State": 1,
  "Msg": "",
  "IsOpenPreDownload": true
}
```

**③ `_id`=13 `POST https://sdk-api.yostar.cn/user/quick-login`（787 B）—— SDK 登录成功**

```json
{
  "Code": 200,
  "Msg": "OK",
  "Data": {
    "Destroy": {
      "DestroyAt": 0
    },
    "Identity": {
      "Type": 0,
      "RealName": "**仙",
      "IDCard": "330*********06062*",
      "Underage": false,
      "PI": "",
      "BirthDate": "",
      "State": 1
    },
    "IsTestAccount": false,
    "Keys": [
      {
        "Type": "mobile",
        "NickName": "177****1532",
        "NickNameEnc": "j9IbVlKQbotMS62qKOYIq4YXcrEq9c2V65AdeS2r+cZnVW9xZS3dfeGETS18qyuagJwRacrNfSQEUDDFYujGxtKw9K0a3WjsefA2XTasGvx7L9IlhojXhi/9fuF7jpQJgrjMYehJzjokrk1dUsAMwNCtp0QRFaw4AvbL7VG7oVg="
      }
    ],
    "Pass": {
      "ID": 22420602,
      "NickName": "YS1013178778",
      "Picture": "",
      "State": 1,
      "CreatedAt": 1780717450,
      "DefaultNickName": ""
    },
    "PassDestroy": {
      "DestroyAt": 0
    },
    "User": {
      "ID": 1013178778,
      "PID": "CN-BA",
      "Token": "076b037e8ff4226c972cd8ab18d914f0db517852",
      "State": 1,
      "RegChannel": "android_official",
      "DestroyState": 0
    },
    "Wechat": {
      "Bound": false,
      "Follow": 0,
      "NickName": ""
    }
  }
}
```

### 5.4 有没有 `{"protocol":...}` 国服信封？有没有 base64→gzip 的游戏包？

| 检查项 | 结果 |
|---|---|
| 响应体/请求体中出现 `"protocol"` 键 | **0 次** |
| 响应体中出现 `"Protocol":` | **0 次** |
| `encoding=base64` 的响应体 | **0 条** |
| base64 解码后可 gzip/zlib 解压 | **0 条** |
| 响应体魔数为 gzip/zip/png/jpeg 等 | **0 条** |
| `encoding=base64` 的**请求**体 | 16 条，**全部**发往 `*.log.aliyuncs.com`（阿里云 SLS protobuf 上报），**无一条落在游戏服域名上** |

> **结论**：不存在任何「加密的游戏包藏在这个 HAR 里」的可能。国服信封是明文 JSON（`{"protocol":1002,...}`），只要它在，一定是可读的。

---

## §6 明确结论：有没有 `account/auth` / `academy/getinfo`？

### **没有。一条都没有。**

| 用户预期 | 文件实际 | 判定 |
|---|---|---|
| `POST /api/account/auth`（协议 1002）| 不存在 | ❌ **不存在** |
| `POST /api/academy/getinfo`（协议 24000）| 不存在 | ❌ **不存在** |
| 战斗相关几十上百条 `/api/*` | 不存在（游戏服 POST 总数 = 0）| ❌ **不存在** |
| `gsqc-api.bluearchive-cn.com` 的流量 | **只有 1 条 `GET /api/state`** | ⚠️ 有，但只是配置查询 |
| 任意 `/api/*` 业务请求 | **0 条** | ❌ **不存在** |

**这不是「解析漏了」的四种反证：**

1. **没有隐藏载体**（§2.1）：无 base64 响应、无 `_webSocketMessages`、无 `_error`、无 `_pageRef`。所有响应体都以明文 `content.text` 存在。
2. **没有过滤痕迹**（§7）：`_id` = 1..57 **连续无空洞**。Reqable 若在导出时丢了记录，序号必出现缺口。
3. **不是单站点导出**（§4）：12 个主机全在里面，**包含 5 个 `bluearchive-cn.com` 子域**。如果导出被限定在某个站点，`static.bluearchive-cn.com` 的 7 条、`gs-api` 的 2 条、`gsqc-api` 的 1 条就不可能同时出现。
4. ★ **抓包窗口 = 一次完整 App 会话**（§7.2）：`_id`=1 是 `#app_start`、`_id`=57 是 `#app_end`，首尾对齐。**会话内的流量没有一段落在窗口外**——所以「漏抓」这个可能性被结构性排除。

---

## §7 为什么没有？（基于文件内容的解释，不猜）

### 7.1 先排除四个「看起来像」的解释

| 假说 | 文件证据 | 判定 |
|---|---|---|
| **H1「Reqable 只导出了 udata 这一个 site」** | 文件名 `reqable_udata.har` 确实像，**但文件里有 12 个主机、含 5 个 `bluearchive-cn.com` 子域**。单站点导出不可能同时包含 `static` / `gs-api` / `gsqc-api` / `notice` / `sdk-api.yostar.cn` / `log.aliyuncs.com`。而且**网关主机 `gsqc-api` 本身就在文件里**——若真有 `account/auth`（同主机、同端口、同 scheme），任何「按 host 过滤」的规则都会把它一起带进来。 | **❌ 排除** |
| **H2「导出按时间范围截断」** | 窗口起点 `12:34:40.814` 是 `#app_start`，终点 `12:36:59.568` 是 `#app_end`（见 7.2）——**两端正好是 App 会话的生命周期边界**，不是任意时钟刻度。人为裁剪不可能裁得这么准。 | **❌ 排除** |
| **H3「游戏走非 HTTP 通道（裸 socket / WS / QUIC），代理看不见」** | **这是最需要认真对待的一条**，但被三件事否掉：(a) `_webSocketMessages` 0 条、`response.mimeType` 里无 WS 升级；(b) **Reqable 在「无法解密」时会留 `CONNECT` 存根——本文件里就有 6 条现成的样板**（`webcnstatic.yostar.net`：`status=0`、`request._status=processing`、`time=-1`、无响应头）。**而 `gsqc-api` / `gs-api` / `state-api` 一条 CONNECT 都没有**；(c) 项目内已实测 `POST /api/account/auth` 走的是 `BestHTTP/2 v2.4.0` 的明文 HTTP/2，目标就是同一个 `gsqc-api…:443`（`report/41-Account_Auth字段级排查.md:54-55`）。⇒ 若客户端向网关发起过任何连接，Reqable 必留痕迹；**它没有**。 | **❌ 排除** |
| **H4「响应体是加密/压缩二进制，被 base64 藏在某个字段里」** | `encoding=="base64"` 的响应体 **0 条**；`{"protocol"` 出现 **0 次**；base64→gzip 解压成功 **0 条**。国服信封是**明文 JSON**，只要在就必然可读。 | **❌ 排除** |

### 7.2 ★ 决定性证据：这个 HAR 正好覆盖「一次 App 会话」的首尾，中间无缺口

这是本报告最重要的一条发现——它把「有没有漏抓」从推测变成了**可验证**：

```text
_id = 1   12:34:40.814   POST udata-api.open.yostar.net/daq/track/v2
                          └─ #event_type = "#app_start"     ← App 启动（会话开始）

   …… 中间 55 条，_id 2..56 连续无空洞 ……

_id = 57  12:36:59.568   POST udata-api.open.yostar.net/daq/track/v2
                          └─ #event_type = "#app_end"       ← App 退出（会话结束＝文件末尾）
```

**推理链：**

1. `#app_start` 是客户端的**第一条**网络请求，`#app_end` 是**最后一条**；它们分别落在 `_id`=1 与 `_id`=57，而文件里正好只有 1..57。
2. ⇒ **抓包窗口 = 这次 App 启动的完整生命期**（139 秒）。**这次会话之内没有任何一段流量落在窗口之外。**
3. ⇒ 在这个完整会话里 `POST /api/account/auth` 从未出现，所以它**不是被漏抓，而是根本没被发出**。

**会话内部的完整心跳（全部来自本文件的 udata 埋点）：**

| 时间 (UTC) | `_id` | `#event_type` | 说明 |
|---|---|---|---|
| 12:34:40.814 | 1 | `#app_start` | **会话开始 / 抓包起点** |
| 12:34:49.829 | 20 | `passsdk_user_login` | SDK 快登成功（`login_type=quicklogin`）|
| 12:34:50.880 | 25 | `passsdk_role_info_upload` | 上报角色信息 |
| 12:34:51.059 | 27 | `role_login` | 上报角色登录（`role_id=10015354380`）|
| 12:36:12.222 | 44 | **`#app_end`** | **退到后台** |
| 12:36:24.204 | 47 | **`#app_start`** | 回到前台 |
| 12:36:28.278 | 49 | **`#app_end`** | 再次退到后台 |
| 12:36:52.738 | 52 | **`#app_start`** | 再次回到前台 |
| 12:36:59.568 | 57 | **`#app_end`** | **会话结束 / 抓包终点 / 文件末尾** |

> **注意 12:36:12 之后的四次前后台切换**：App 在最后 47 秒被反复切出切入，而这段时间**一个游戏服请求都没有**。这非常像「切到 Reqable 检查抓包 → 切回 → 关掉游戏」——也就是说**用户是在这次会话快结束时才去导出 HAR 的**，导出的自然是这次会话，而这次会话里没有游戏协议。

### 7.3 会话为什么停在那里？—— 服务器处于**维护态**

```text
[+1.4s] _id=4  GET state-api.bluearchive-cn.com/api/state
           → {"Servers":["https://gsqc-api.bluearchive-cn.com/api/", ...],
              "State":1,"Msg":"服务器维护中，请耐心等待开服！"}
                          ↑↑↑↑↑↑↑↑         ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑
                          State=1 = 维护态      文案直接写着「维护中」

[+1.8s]  _id=5   GET gsqc-api…/api/state   → 676 B 网关配置（State:1, Msg:""）
[+9.7s]  _id=23/24 GET gs-api…/api/health  → "ok"   ← 网关可达性探针，通了
[+9.7s]  —— 按正常流程此处应立刻出现 POST /api/account/auth —— 它没有出现，之后也没有
[+15.8s] _id=33  活动公告 WebView（内容是「11/12 维护结束后开启」的新活动预告）
[+15.8s] _id=34~39 6 条 CONNECT webcnstatic（公告配图，未解密）
[+18s ~ +139s] 只剩 udata / aliyun-log / heartbeat / red_point 心跳
```

**四个互相独立的旁证：**

| # | 旁证 | 说明 |
|---|---|---|
| **E1** | `State:1` + `Msg:"服务器维护中，请耐心等待开服！"` | 国服 `/api/state` 的 `State`：**0 = 开服，1 = 维护**。维护态下客户端显示维护弹窗、**不发出任何业务请求**。项目内既有结论一致：`report/00-下一步总方案.md:317`「`State` 必须 0（1 = 维护中，客户端不往下走）」；`report/24-state接口schema反推.md:334`「真实服务器在维护中时返回 `State: 1` + 维护文案，且 `ba-pentest.md §十四` 明确记录「**客户端不会发出任何业务请求**」」。 |
| **E2** | **游戏服连接全部「单次即弃」** | `_cid=4`(state-api)、`_cid=5`(gsqc-api)、`_cid=13`/`_cid=14`(gs-api) 各自只承载 **1 条**请求，用完立即关闭、从不复用。而正常登录后网关是长连接、会持续复用同一 `_cid`。 |
| **E3** | **总字节量只有 14,366 B**，其中 9,724 B 是一条活动公告 HTML（占 68%）| 扣除公告后其余 56 条合计 **4,642 B**。真实的「登录 + 大厅 + 一局战斗」协议流量是几百 KB 量级（单是 `account/auth` 一个响应，项目里记录的就是 1269 B / 3740 B 量级）。 |
| **E4** | **`#account_id` 在全 9 条 udata 埋点里始终为空串**，含最后一条（12:36:59）| `#account_id` 是 udata 在账号关联成功后才会回填的字段。到会话结束仍为空，说明 udata 侧从未完成与游戏账号的绑定。 |

### 7.4 一个必须说清的细节：`role_login` 已上报 ≠ 登录成功

`_id`=27（12:34:51.059）确实上报了 `#event_type="role_login"`，带 `role_id=10015354380`、`role_name=111`。**但它不能证明游戏登录成功**：

1. **同一个角色 ID 早就存在于 SDK 缓存里**：`_id`=20 的 `passsdk_user_login`（早 1.2 秒，紧跟 SDK HTTP 快登）就已经带着 `sdk_role_id=10015354380` / `sdk_role_name=111`。这是 **SDK 把本地缓存的「上次角色」在启动时重放上报**，而不是服务器确认过的新登录。
2. **该事件前后没有任何网关 POST**：`role_login`（12:34:51.059）±2 秒内对 `*.bluearchive-cn.com` 的请求只有 `static/checkhealth.html`（GET ×2）与 `gs-api/api/health`（GET ×2），**POST 数 = 0**。若真有 1002 往返，同一秒内必然出现一条 `POST gsqc-api/api/account/auth`。
3. **`#account_id` 仍为空**（见 E4）。若真完成 1002，udata 的账号字段应被回填。

> ⇒ `role_login` 是 **SDK 侧的「上报上次角色」**，属客户端行为，**不构成「已登录官方服务器」的证据**。

### 7.5 那用户说的「登录、进大厅、打了一场战斗」是怎么回事？

**这份 HAR 在结构上无法支持这个叙述**（7.2 已证明会话覆盖完整）。最可能是以下情况之一，且互不排斥：

1. **时点不对：抓包落在维护窗口里。** 文件时间是北京时间 **2026-11-11 20:34:40 → 2026-11-11 20:36:59**（11 月 11 日晚 20:34）。同一会话加载的活动公告写的是「**11 月 12 日 维护结束后** ~ 11 月 26 日 13:59」——公告描述的是**尚未开始的**活动，说明抓包时**新版本还没上线**，服务器正处在新版本维护前的状态，本来就不可能进大厅。
2. **会话选错了：导出的是一次「开机即退出」的会话，而不是玩耍那次。** App 在 12:36:12–12:36:59 被反复切前后台，随后以 `#app_end` 结束——很像「切到 Reqable 点导出，再回来关掉游戏」。若用户在此**之前**已经玩过，那次是**另一个进程会话**，其流量不在本文件内（本文件的 `#app_start` 到 12:34:40 才发生）。
3. **记忆串了会话 / 换了设备。** 用户若确实完整走过一遍，那次抓包是**另一次 Reqable 会话**，没有被导出到这一份。

> ⚠️ 但无论属于哪一种，**对下游的影响完全一样**：**这个文件里没有游戏协议流量，且这不是解析问题。**不要在这个文件上再投入解析工作。

---

## §8 下一步：怎样才能真的拿到游戏协议流量

本文件的证据已经**排除了「协议层被藏起来」和「导出过滤」**这两种可能，所以重抓时必须换条件，而不是换解析方法。

| 前置条件 | 判据（必须满足才算「抓到了」）|
|---|---|
| **1. 服务器必须处于开服态** | 抓包前先用同一台手机的浏览器（走同一代理）打开 `https://state-api.bluearchive-cn.com/api/state`，**必须看到 `"State":0`**。看到 `State:1` 或「维护中」文案就不要抓了，抓了也是本文件的翻版。 |
| **2. 抓包必须在「点击进入游戏」之前开始，并覆盖到战斗结束之后** | 本文件的最后一条是 12:36:59，之后全空 —— 说明捕获结束太早。要一直录到**看到战斗结算画面**再停。 |
| **3. 验收标准（用本脚本自检）** | `python report\_tmp\har_deep.py <新har> --sections 4` 必须出现 `POST` 到 `gsqc-api.bluearchive-cn.com/api/account/auth`；`--sections 5` 必须出现 `{"protocol":` 信封；响应体总字节应 **> 200 KB**。 |

配套的抓包 SOP 已经在 `report/95-真服抓包与对照方案.md` 里，本报告只补一条最省的验收动作：**用 §7.2 的 E1/E2 两个判据在抓完 5 秒内就能判断这次抓包是否有效**（`State` 必须 0；udata 埋点的 `#account_id` 必须非空）。

---

## §9 复现方式

```powershell
# 全量文本报告（7 个章节）
python report\_tmp\har_deep.py report\_tmp\reqable_udata.har --sections 1234567

# 只看某几节（例：只看主机分组 + 证据链）
python report\_tmp\har_deep.py report\_tmp\reqable_udata.har --sections 47

# 重新生成本 Markdown 报告
python report\_tmp\har_deep.py report\_tmp\reqable_udata.har --markdown report\98-har深度取证.md

# 换任意 HAR 复用
python report\_tmp\har_deep.py <other.har> --markdown out.md
```

脚本只读、不联网、不改原文件，纯标准库。

---

## 附录 A · 与项目内既有结论的一致性核对

| 本报告结论 | 项目内既有记载 | 是否一致 |
|---|---|---|
| 该 HAR 是维护期抓的，57 条里只有 1 条 `gsqc-api`、0 条业务包 | `report/00-下一步总方案.md:238`（D3 条目，原文几乎逐字相同）| ✅ 一致 |
| `State:1` = 维护态，客户端不往下走 | `report/00-下一步总方案.md:317`、`report/24-state接口schema反推.md:334` | ✅ 一致 |
| 676 B `gsqc-api/api/state` 与 161 B `state-api/api/state` 的真实形状 | `report/31-真实catalog与版本清单取证.md:95` | ✅ 逐字节一致 |
| 本地没有任何官方协议层响应（无 24000、无成功 1002）| `report/95-真服抓包与对照方案.md` §0 A1 | ✅ 一致 |

## 附录 B · 本文件里**有**的、可以拿去用的东西

虽然没抓到游戏协议，但这份 HAR 仍然提供了一批**真实上游取值**：

| 数据 | 来源 `_id` | 值 |
|---|---|---|
| `Servers` 列表（网关 base URL，**必须 `/api/` 结尾**）| 4 | `gsqc-api`(主) + `gs-api`(备) |
| 版本号四件套 | 5 | `ResourceVersion=202610221737`、`TableVersion=202610292033`、`MediaVersion=202610221638`、`PatchVersion=202609291539` |
| CDN 根（3 条）| 5 | `static` / `static-qc` / `static-hs` 三个 `bluearchive-cn.com` 子域 |
| 内部回调地址 | 5 | `http://gs-inter.bluearchive-cn.com:4000/api/{order,survey,web,account}` |
| 客户端业务头（state/health 请求）| 4,5 | `APP-VER: 3.0.2`、`PLATFORM-ID: 1`、`CHANNEL-ID: 1`、`SERVER-NAME: prod`、`X-Unity-Version: 2021.3.56f2`、`Content-Type: application/octet-stream` |
| Unity 版本 | 4,5 | `UnityPlayer/2021.3.56f2 (UnityWebRequest/1.0, libcurl/8.10.1-DEV)` |
| SDK 登录返回值形状 | 13 | `User{ID,PID,Token,State,RegChannel}`、`Pass{ID,NickName}`、`Identity{RealName,IDCard,Underage}` |
| 端点存活表 | 全部 | `gs-api/api/health`=`ok`(text/plain 2B)；`gsqc-api/api/state`=200/676B；`state-api/api/state`=200/161B |

---

*报告由 `report\_tmp\har_deep.py` 生成；所有表格数据直接来自 `reqable_udata.har` 的解析结果，未手工填写。*
