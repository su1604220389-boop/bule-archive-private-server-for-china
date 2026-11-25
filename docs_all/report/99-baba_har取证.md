# 99 · `baba.har` 取证报告：`/api/academy/getinfo` 之后客户端到底发了什么

- **取证对象**：`report\_tmp\baba.har` — 209,296 B — SHA256 `08a7b315…aa5cc5` **（与原任务给定值逐字节一致，未被改动）**
- **抓包工具**：Reqable 3.3.11（HAR `log.version = 1.2`）
- **HAR 内时间范围**：`2026-11-14T07:42:18.918Z` → `2026-11-14T07:42:42.135Z`
- **折算北京时间（UTC+08:00）**：`15:42:18.918` → `15:42:42.135`
- **分析脚本**：`report\_tmp\baba_deep.py`（只读、可复用）
- **只读声明**：全程未修改 `baba.har`，未连接手机，未连接服务器。

---

## 0. 结论先行（请先读这一节）

### 0.1 直接回答「academy 之后有没有第 3 条」

> **这份 HAR 里根本不存在 `/api/academy/getinfo`，也不存在 `/api/account/auth`。**

不是"academy 之后没有第 3 条"，而是**整段登录交换（auth + academy）在这一轮抓包里一条都没有发生**。
在 209,296 字节全文里做子串统计：

| 子串 | 出现次数 |
|---|---|
| `academy` | **0** |
| `getinfo` | **0** |
| `account/auth` | **0** |
| `packet` | **0** |
| `protocol` | **0** |

这既覆盖 URL、也覆盖请求体/响应体、日志正文。不是截断、不是路径改写、不是编码——是**字面上不存在**。

### 0.2 更关键的发现：这一轮客户端在跟**真·官方服务器**说话，不是我们

这份 HAR 里所有 `*bluearchive-cn.com` 请求的落地主机，都不是我们的 nginx：

| 主机 | 对端 IP | 响应 `Server` 头 | 是否我们 |
|---|---|---|---|
| `state-api.bluearchive-cn.com` | `39.173.144.14` | `Tengine` + `Via: cache61.l2et15-7…` + `EagleId`（阿里云 CDN） | **否** |
| `gsqc-api.bluearchive-cn.com` | `112.13.210.86` | `TencentEdgeOne` + `EO-LOG-UUID` | **否** |
| `static.bluearchive-cn.com` | `112.49.41.54` | `AliyunOSS` + `EO-Cache-Status: HIT` | **否** |
| `example.com` | **`<SERVER_IP>`** | **`nginx`** + `strict-transport-security` | **是** |

对照组非常干净：**我们服务器回的是 `server: nginx`，另外三个回的是 CDN 厂商头**。所以 `state-api` / `gsqc-api` / `static` 这三条链路上，我们的 nginx 根本没参与。

### 0.3 客户端为什么停住——HAR 里有明文原因

`state-api.bluearchive-cn.com/api/state`（15:42:23.821，200，161 B）原样返回：

```json
{"Servers":["https://gsqc-api.bluearchive-cn.com/api/","https://gs-api.bluearchive-cn.com/api/"],
 "State":1,"Msg":"服务器维护中，请耐心等待开服！"}
```

`gsqc-api.bluearchive-cn.com/api/state`（15:42:23.975，200，676 B）同步给出官方全量配置（`ResourceVersion":"202611051844"`、`State":1`、`Msg":""`）。

**客户端收到的是"维护中"。** 在这之后它再也没向任何游戏 API 发过一个 POST。

### 0.4 客户端唯一碰过我们服务器的东西，是**网络探测**

`127.0.0.1:8080/common/config`（SDK 本地配置，7,249 B）里写得很清楚：

```json
"DetectionAddress": {
  "Auto": {
    "HTTP": ["https://example.com/checkhealth.html","https://example.com","https://example.com/api/health"],
    "MTR":  ["https://example.com/checkhealth.html","https://example.com","https://example.com/api/health"],
    "DNS": null, "PING": null, "TCP": null
  },
  "Enable": true,
  "Internet": "https://example.com"
}
```

`example.com` = **SDK 的连通性探测域名**（`Internet` + `DetectionAddress`），DNS 指向 `<SERVER_IP>`（我们）。
所以 HAR 里 12 条打到我们 IP 的记录，**全部是健康探测**（`/`→`ok`、`/api/health`→`{"status":"ok"}`、`/checkhealth.html`→`ok`），**没有一条走游戏协议**。这反过来证明一件事：**从客户端视角看，我们的 nginx 是活的、可达的、200 OK 的。**

### 0.5 对诊断方向的影响

原来的假设是"academy 之后可能有一条没到我们服务器的第 3 条请求"。**这个假设在本 file 上无法成立**——因为锚点本身缺席。真正需要解释的问题变成了：

> **这一轮客户端为什么压根没发 auth/academy，而是先去问了官方 `state-api` 并拿到"维护中"？**

即：抓包那一刻手机的 DNS / hosts 覆盖**没有**把 `state-api.bluearchive-cn.com`（更不用说 `gs-api`）导到我们服务器上，客户端跑的是官方线路。

---

## 1. 规模

| 项 | 值 |
|---|---|
| 文件 | `report\_tmp\baba.har` |
| 字节数 | **209,296 B** |
| SHA256 | `08a7b31587799da28947e4af921741044762188f1dac978d1930783785aa5cc5` ✅ 与给定值一致 |
| HAR version | 1.2 |
| creator | Reqable 3.3.11 |
| **entries 条数** | **53** |
| 有时间戳条目 | 53 / 53 |
| **首条（本地）** | **2026-11-14 15:42:18.918** |
| **末条（本地）** | **2026-11-14 15:42:42.135** |
| **时间跨度** | **23.217 秒** |
| 首条（UTC） | `2026-11-14T07:42:18.918Z` |
| 独立主机数 | **15** |
| 连接（`connection`）数 | 33（conn id `5`–`37`，**连续无缺口**） |

**结构非标准项（如实记录）**：

| 项 | 说明 |
|---|---|
| 无 `log.pages` | Reqable 导出常态，可接受；本 HAR 无 page 分组 |
| 无 `log.browser` | 同上 |
| 条目含大量 `_` 私有字段 | `_id/_uid/_cid/_ctime/_sid/_stime/_serverAddress/_serverPort/_clientAddress/_clientPort`，Reqable 私有扩展，标准 HAR 之外，不影响解析 |
| `request._status` | Reqable 私有字段，取值 `completed` / `aborted` / `processing`；**不是** HTTP 状态码 |
| CONNECT 条目 `response.status = 0` | Reqable 把隧道建立单独记成一条伪请求，`status:0` 是它的正常表示，**不是失败** |

> 结论：HAR 结构基本标准，仅缺 `pages`/`browser`，加 Reqable 私有字段，**不影响任何结论**。

---

## 2. ★ 游戏服请求全时序

### 2.1 全部 `*bluearchive-cn.com` 请求（共 **7** 条，**全部 GET**）

| # | 时间(本地) | 方法 | 主机 | 完整 path | 状态 | 响应字节 | 对端 IP | SNI/`:authority` | 响应 Server |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 15:42:23.821 | GET | `state-api.bluearchive-cn.com` | `/api/state` | 200 | 161 | `39.173.144.14` | `state-api.bluearchive-cn.com` | `Tengine`(阿里CDN) |
| 2 | 15:42:23.975 | GET | `gsqc-api.bluearchive-cn.com` | `/api/state` | 200 | 676 | `112.13.210.86` | `gsqc-api.bluearchive-cn.com` | `TencentEdgeOne` |
| 3 | 15:42:24.347 | GET | `static.bluearchive-cn.com` | `/prodm39/Manifest/Patch/202609291539/patch_assetmanifest` | 200 | 78 | `112.49.41.54` | `static.bluearchive-cn.com` | `AliyunOSS` |
| 4 | 15:42:24.471 | GET | `static.bluearchive-cn.com` | `/prodm39/Manifest/TableBundles/202611051826/TableManifestHash` | 200 | 10 | `112.49.41.54` | `static.bluearchive-cn.com` | `AliyunOSS` |
| 5 | 15:42:24.638 | GET | `static.bluearchive-cn.com` | `/prodm39/Manifest/MediaResources/202611051836/MediaManifestHash` | 200 | 11 | `112.49.41.54` | `static.bluearchive-cn.com` | `AliyunOSS` |
| 6 | 15:42:25.342 | GET | `static.bluearchive-cn.com` | `/prodm39/AssetBundles/Catalog/202611051844/Android/bundleDownloadInfo.hash` | 200 | 9 | `112.49.41.54` | `static.bluearchive-cn.com` | `AliyunOSS` |
| 7 | 15:42:25.532 | GET | `static.bluearchive-cn.com` | `/prodm39/AssetBundles/Catalog/202611051844/Android/catalog_Android.hash` | 200 | 32 | `112.49.41.54` | `static.bluearchive-cn.com` | `AliyunOSS` |

**POST 数：0。** 全部 2xx、全部 0.6–0.9 s 内完成。
最后一条游戏服请求 = **#7，15:42:25.532**（`catalog_Android.hash`）。

### 2.2 全部打到我们服务器 IP（`<SERVER_IP>`）的请求（共 **12** 条）

| # | 时间(本地) | 方法 | 主机 | path | 状态 | 字节 | SNI `:authority` | 响应体 |
|---|---|---|---|---|---|---|---|---|
| 1 | 15:42:21.479 | CONNECT | `example.com` | `/` | 0 | 0 | `example.com:443` | 隧道记录 |
| 2 | 15:42:21.481 | CONNECT | `example.com` | `/` | 0 | 0 | `example.com:443` | 隧道记录 |
| 3 | 15:42:21.483 | CONNECT | `example.com` | `/` | 0 | 0 | `example.com:443` | 隧道记录 |
| 4 | 15:42:21.991 | CONNECT | `example.com` | `/` | 0 | 0 | `example.com:443` | 隧道记录 |
| 5 | 15:42:22.264 | GET | `example.com` | `/` | 200 | 2 | `example.com` | `ok` |
| 6 | 15:42:22.516 | GET | `example.com` | `/api/health` | 200 | 15 | `example.com` | `{"status":"ok"}` |
| 7 | 15:42:30.217 | GET | `example.com` | `/checkhealth.html` | 200 | 2 | `example.com` | `ok` |
| 8 | 15:42:30.238 | GET | `example.com` | `/checkhealth.html` | 200 | 2 | `example.com` | `ok` |
| 9 | 15:42:30.406 | CONNECT | `example.com` | `/` | 0 | 0 | `example.com:443` | 隧道记录 |
| 10 | 15:42:30.967 | GET | `example.com` | `/` | 200 | 2 | `example.com` | `ok` |
| 11 | 15:42:31.026 | GET | `example.com` | `/api/health` | 200 | 15 | `example.com` | `{"status":"ok"}` |
| 12 | 15:42:31.233 | GET | `example.com` | `/api/health` | 200 | 15 | `example.com` | `{"status":"ok"}` |

- **SNI / Host 头**：12 条全部是 `example.com`（HTTP/2 用 `:authority`，CONNECT 用 `Host: example.com:443`）。**没有一条带 `bluearchive-cn.com` 的 SNI 打到我服务器。**
- 全部响应头带 `server: nginx`，与我方 nginx 指纹一致。
- 用途：`/common/config` 里 `DetectionAddress.Internet` 指定的**连通性探测**，见 §0.4。

### 2.3 关键窗口：SDK 登录完成后（15:42:30.372 之后）

`POST 127.0.0.1:8080/user/detail`（15:42:30.372，200，845 B）是 SDK 一键登录成功的标志——**这正是"该发 `POST /api/account/auth`"的时刻**。此后到抓包结束的 **11.76 秒**里共 **20** 条请求，逐条如下：

| 时间 | 方法 | 主机 | path | 状态 |
|---|---|---|---|---|
| 15:42:30.406 | CONNECT | `example.com` | `/` | 0 |
| 15:42:30.967 | GET | `example.com` | `/` | 200 |
| 15:42:31.026 | GET | `example.com` | `/api/health` | 200 |
| 15:42:31.233 | GET | `example.com` | `/api/health` | 200 |
| 15:42:32.008 | POST | `yostar-cn-client-logging…` | `/logstores/…/shards/lb` | 200 |
| 15:42:32.018 | POST | `127.0.0.1:8080` | `/health-game/duration` | 200 |
| 15:42:32.540 | POST | `udata-api.open.yostar.net` | `/daq/track/v2` | 200 |
| 15:42:32.547 | POST | `127.0.0.1:8080` | `/heartbeat/pulse` | **0** |
| 15:42:32.547 | POST | `127.0.0.1:8080` | `/common/geo-ip` | 200 |
| 15:42:32.641 | POST | `yostar-cn-netsdk-logging…` | `/logstores/…/shards/lb` | 200 |
| 15:42:36.561 | POST | `udata-api.open.yostar.net` | `/daq/track/v2` | 200 |
| 15:42:36.619 | POST | `udata-api.open.yostar.net` | `/daq/track/v2` | 200 |
| 15:42:36.642 | POST | `yostar-cn-netsdk-logging…` | `/logstores/…/shards/lb` | 200 |
| 15:42:36.783 | POST | `app.adjust.cn` | `/event` | 200 |
| 15:42:37.011 | POST | `yostar-cn-client-logging…` | `/logstores/…/shards/lb` | 200 |
| 15:42:39.068 | POST | `yostar-cn-client-logging…` | `/logstores/…/shards/lb` | 200 |
| 15:42:40.627 | POST | `yostar-cn-netsdk-logging…` | `/logstores/…/shards/lb` | 200 |
| 15:42:40.942 | POST | `udata-api.open.yostar.net` | `/daq/track/v2` | 200 |
| 15:42:42.135 | POST | `yostar-cn-client-logging…` | `/logstores/…/shards/lb` | **0**（抓包中断） |
| 15:42:42.135 | POST | `yostar-cn-netsdk-logging…` | `/logstores/…/shards/lb` | **0**（抓包中断） |

> **游戏 API：0 条。** 这 20 条全是 SDK 探测、日志上报、埋点、心跳。

### 2.4 全量时间线（53 条，一行一条）

```
15:42:18.918  GET     down.anticheatexpert.com/gamesafe/mobile/huiwan/android/com.RoamingStar.BlueArchive/config2.xml       404    492 B
15:42:19.041  GET     down.anticheatexpert.com/gamesafe/mobile/huiwan/android/com.RoamingStar.BlueArchive/config2.xml       404    492 B
15:42:21.389  POST    127.0.0.1:8080/common/config                                                                         200  7,249 B
15:42:21.447  GET     er.ns.aliyuncs.com/policy?policyKey=d4b34a48…                                                        200  2,045 B
15:42:21.475  GET     yostar-cn-client-logging.cn-shanghai.log.aliyuncs.com/servertime                                     200      0 B
15:42:21.479  CONNECT example.com:443  [<SERVER_IP>]                                                                  0      0 B
15:42:21.481  CONNECT example.com:443  [<SERVER_IP>]                                                                  0      0 B
15:42:21.483  CONNECT example.com:443  [<SERVER_IP>]                                                                  0      0 B
15:42:21.487  GET     yostar-cn-netsdk-logging.cn-shanghai.log.aliyuncs.com/servertime                                     200      0 B
15:42:21.991  CONNECT example.com:443  [<SERVER_IP>]                                                                  0      0 B
15:42:22.187  POST    tapsdk.tapapis.cn/sdk-core/v1/gatekeeper?client_id=fdcxdbtzmnsj0g2au5                                  400    697 B
15:42:22.203  POST    fp-it.fengkongcloud.com/v3/cloudconf                                                                   200     88 B
15:42:22.226  GET     udata-api.open.yostar.net/daq/init/v2?os=1&code=&sub_channel_name=                                   200    194 B
15:42:22.264  GET     example.com/                                     [<SERVER_IP>, nginx]                           200      2 B
15:42:22.365  POST    udata-api.open.yostar.net/daq/track/v2                                                                200     51 B
15:42:22.516  GET     example.com/api/health                            [<SERVER_IP>, nginx]                           200     15 B
15:42:22.550  POST    fp-it.fengkongcloud.com/deviceprofile/v4                                                              200    185 B
15:42:23.006  POST    udata-api.open.yostar.net/daq/track/v2                                                                200     51 B
15:42:23.821  GET     state-api.bluearchive-cn.com/api/state                 [39.173.144.14, Tengine CDN]                      200    161 B  ◀ 官方，回“维护中”
15:42:23.975  GET     gsqc-api.bluearchive-cn.com/api/state                  [112.13.210.86, TencentEdgeOne]                   200    676 B  ◀ 官方
15:42:24.347  GET     static.bluearchive-cn.com/…/patch_assetmanifest       [112.49.41.54, AliyunOSS]                         200     78 B
15:42:24.471  GET     static.bluearchive-cn.com/…/TableManifestHash         [112.49.41.54, AliyunOSS]                         200     10 B
15:42:24.638  GET     static.bluearchive-cn.com/…/MediaManifestHash         [112.49.41.54, AliyunOSS]                         200     11 B
15:42:25.247  GET     cbsipv4.shuzilm.cn/ip?pkg=com.RoamingStar.BlueArchive&t=1&v=2&s=A768…                                        200     14 B
15:42:25.342  GET     static.bluearchive-cn.com/…/bundleDownloadInfo.hash   [112.49.41.54, AliyunOSS]                         200      9 B
15:42:25.532  GET     static.bluearchive-cn.com/…/catalog_Android.hash      [112.49.41.54, AliyunOSS]                         200     32 B  ◀ 最后一条游戏服请求
15:42:26.371  POST    yostar-cn-client-logging…/logstores/…/shards/lb                                                      200      0 B
15:42:26.380  POST    yostar-cn-netsdk-logging…/logstores/…/shards/lb                                                      200      0 B
15:42:27.379  POST    gid.tapapis.cn/device/v1/query?client_id=fdcxdbtzmnsj0g2au5                                          200     84 B
15:42:29.866  POST    127.0.0.1:8080/user/quick-login                                                                       200    845 B  ◀ SDK 一键登录成功
15:42:30.217  GET     example.com/checkhealth.html                      [<SERVER_IP>, nginx]                           200      2 B
15:42:30.238  GET     example.com/checkhealth.html                      [<SERVER_IP>, nginx]                           200      2 B
15:42:30.372  POST    127.0.0.1:8080/user/detail                                                                            200    845 B  ◀ 该发 auth 的时刻
15:42:30.406  CONNECT example.com:443  [<SERVER_IP>]                                                                  0      0 B
15:42:30.967  GET     example.com/                                     [<SERVER_IP>, nginx]                           200      2 B
15:42:31.026  GET     example.com/api/health                            [<SERVER_IP>, nginx]                           200     15 B
15:42:31.233  GET     example.com/api/health                            [<SERVER_IP>, nginx]                           200     15 B
15:42:32.008  POST    yostar-cn-client-logging…/logstores/…/shards/lb                                                      200      0 B
15:42:32.018  POST    127.0.0.1:8080/health-game/duration                                                                   200     70 B
15:42:32.540  POST    udata-api.open.yostar.net/daq/track/v2                                                                200     51 B
15:42:32.547  POST    127.0.0.1:8080/heartbeat/pulse                                                                          0      0 B
15:42:32.547  POST    127.0.0.1:8080/common/geo-ip                                                                          200     57 B
15:42:32.641  POST    yostar-cn-netsdk-logging…/logstores/…/shards/lb                                                      200      0 B
15:42:36.561  POST    udata-api.open.yostar.net/daq/track/v2                                                                200     51 B
15:42:36.619  POST    udata-api.open.yostar.net/daq/track/v2                                                                200     51 B
15:42:36.642  POST    yostar-cn-netsdk-logging…/logstores/…/shards/lb                                                      200      0 B
15:42:36.783  POST    app.adjust.cn/event                                                                                   200     70 B
15:42:37.011  POST    yostar-cn-client-logging…/logstores/…/shards/lb                                                      200      0 B
15:42:39.068  POST    yostar-cn-client-logging…/logstores/…/shards/lb                                                      200      0 B
15:42:40.627  POST    yostar-cn-netsdk-logging…/logstores/…/shards/lb                                                      200      0 B
15:42:40.942  POST    udata-api.open.yostar.net/daq/track/v2                                                                200     51 B
15:42:42.135  POST    yostar-cn-client-logging…/logstores/…/shards/lb                                                        0      0 B  ← 抓包在此中断
15:42:42.135  POST    yostar-cn-netsdk-logging…/logstores/…/shards/lb                                                      0      0 B  ← 抓包在此中断
```

**最后一次对游戏服的请求**：`15:42:25.532` `static.bluearchive-cn.com/…/catalog_Android.hash`。
**之后还有没有别的？** 有，27 条，但**全部是 SDK 探测 / 日志 / 埋点 / 本地 SDK**，**没有一条游戏 API**。

> ⚠️ 抓包在 `15:42:42.135` 中断（末两条 `request._status = processing`，响应未回）——是**手动停止抓包**造成，不是客户端静默。因此本 HAR **无法说明 15:42:42.135 之后**客户端做了什么。

---

## 3. 主机 → 路径清单（全量，不截断）

共 **15** 个主机、**53** 条。

### 3.1 `down.anticheatexpert.com` — 2 条，1 个 path，IPv6 `2409:8c30:40:2d07::4`
| path | 次数 | 方法 | 状态 |
|---|---|---|---|
| `/gamesafe/mobile/huiwan/android/com.RoamingStar.BlueArchive/config2.xml` | 2 | GET | 404 |

### 3.2 `127.0.0.1`（设备本地 SDK，:8080）— 6 条，6 个 path
| path | 次数 | 方法 | 状态 |
|---|---|---|---|
| `/common/config` | 1 | POST | 200 |
| `/user/quick-login` | 1 | POST | 200 |
| `/user/detail` | 1 | POST | 200 |
| `/health-game/duration` | 1 | POST | 200 |
| `/common/geo-ip` | 1 | POST | 200 |
| `/heartbeat/pulse` | 1 | POST | **0** |

### 3.3 `er.ns.aliyuncs.com` — 1 条，IPv6 `2409:8c28:2880:7:3::43`
| path | 次数 | 方法 | 状态 |
|---|---|---|---|
| `/policy?policyKey=d4b34a48…&policyVersion=31&aliyunId=1294058570621990&ipaAppId=AzUrJxv6mZ9TPGXXfxUHFn&deviceId=…&sdkVer=1.0.1.9&biz=` | 1 | GET | 200 |

### 3.4 `yostar-cn-client-logging.cn-shanghai.log.aliyuncs.com` — 6 条，IP `106.15.253.172`
| path | 次数 | 方法 | 状态 |
|---|---|---|---|
| `/logstores/yostar-cn-client-logging/shards/lb` | 5 | POST | 0, 200 |
| `/servertime` | 1 | GET | 200 |

### 3.5 **`example.com` — 12 条，IP `<SERVER_IP>`（我们）**
| path | 次数 | 方法 | 状态 |
|---|---|---|---|
| `/` | 7（**5 CONNECT + 2 GET**） | CONNECT, GET | 0, 200 |
| `/api/health` | 3 | GET | 200 |
| `/checkhealth.html` | 2 | GET | 200 |

### 3.6 `yostar-cn-netsdk-logging.cn-shanghai.log.aliyuncs.com` — 6 条，IP `106.15.253.211`
| path | 次数 | 方法 | 状态 |
|---|---|---|---|
| `/logstores/ipa-azurjxv6mz9tpgxxfxuhfn-raw/shards/lb` | 5 | POST | 0, 200 |
| `/servertime` | 1 | GET | 200 |

### 3.7 `tapsdk.tapapis.cn` — 1 条，IPv6 `2408:4003:4::663b:b42d`
| path | 次数 | 方法 | 状态 |
|---|---|---|---|
| `/sdk-core/v1/gatekeeper?client_id=fdcxdbtzmnsj0g2au5` | 1 | POST | **400** |

### 3.8 `fp-it.fengkongcloud.com`（数美）— 2 条，IP `111.31.3.208`
| path | 次数 | 方法 | 状态 |
|---|---|---|---|
| `/v3/cloudconf` | 1 | POST | 200 |
| `/deviceprofile/v4` | 1 | POST | 200 |

### 3.9 `udata-api.open.yostar.net` — 7 条，IP `112.13.210.86`
| path | 次数 | 方法 | 状态 |
|---|---|---|---|
| `/daq/track/v2` | 6 | POST | 200 |
| `/daq/init/v2?os=1&code=&sub_channel_name=` | 1 | GET | 200 |

### 3.10 `static.bluearchive-cn.com` — 5 条，IP `112.49.41.54`（AliyunOSS）
| path | 次数 | 方法 | 状态 |
|---|---|---|---|
| `/prodm39/Manifest/Patch/202609291539/patch_assetmanifest` | 1 | GET | 200 |
| `/prodm39/Manifest/TableBundles/202611051826/TableManifestHash` | 1 | GET | 200 |
| `/prodm39/Manifest/MediaResources/202611051836/MediaManifestHash` | 1 | GET | 200 |
| `/prodm39/AssetBundles/Catalog/202611051844/Android/bundleDownloadInfo.hash` | 1 | GET | 200 |
| `/prodm39/AssetBundles/Catalog/202611051844/Android/catalog_Android.hash` | 1 | GET | 200 |

### 3.11 `gsqc-api.bluearchive-cn.com` — 1 条，IP `112.13.210.86`（TencentEdgeOne）
| path | 次数 | 方法 | 状态 |
|---|---|---|---|
| `/api/state` | 1 | GET | 200 |

### 3.12 `state-api.bluearchive-cn.com` — 1 条，IP `39.173.144.14`（Tengine CDN）
| path | 次数 | 方法 | 状态 |
|---|---|---|---|
| `/api/state` | 1 | GET | 200 |

### 3.13 `cbsipv4.shuzilm.cn`（中国信通院/数盟 IP 查询）— 1 条，IP `39.107.242.47`
| path | 次数 | 方法 | 状态 |
|---|---|---|---|
| `/ip?pkg=com.RoamingStar.BlueArchive&t=1&v=2&s=A76876716F77805B579ACE14873149DC` | 1 | GET | 200 |

### 3.14 `gid.tapapis.cn` — 1 条，IP `39.107.196.62`
| path | 次数 | 方法 | 状态 |
|---|---|---|---|
| `/device/v1/query?client_id=fdcxdbtzmnsj0g2au5` | 1 | POST | 200 |

### 3.15 `app.adjust.cn` — 1 条，IP `47.104.30.117`
| path | 次数 | 方法 | 状态 |
|---|---|---|---|
| `/event` | 1 | POST | 200 |

### 3.16 特别检查清单：这些主机有没有出现？

| 主机 | 出现 | 条数 |
|---|---|---|
| `gsqc-api.bluearchive-cn.com` | **是** | 1（仅 `/api/state`） |
| `gs-api.bluearchive-cn.com` | **否** | **0** |
| `state-api.bluearchive-cn.com` | **是** | 1（仅 `/api/state`） |
| `gm-api.bluearchive-cn.com` | **否** | 0 |
| `gs-inter.bluearchive-cn.com` | **否**（只作为 gsqc 响应体里的字符串出现） | 0 |
| `notice.bluearchive-cn.com` | **否** | 0 |
| `customer.yostar.net` | **否**（只作为 `/common/config` 里的 `AiHelp.ServiceURL` 字符串出现） | 0 |
| `sdk-api.yostar.cn` | **否** | 0 |
| **`<SERVER_IP>`（我们）** | **是** | **12**（`example.com`，全为探测） |

> `gs-api.bluearchive-cn.com` 出现了 0 次——这是官方 `Servers` 列表里的第二项，也正是游戏 API 最可能落地的宿主。**客户端从未连过它。**

---

## 4. 「academy 之后有没有请求」——明确结论

### 4.1 结论

```
锚点 /api/academy/getinfo ： 不存在（0 条）
锚点 /api/account/auth    ： 不存在（0 条）
```

**因此"academy 之后有没有第 3 条"这个问题在这份 HAR 上没有第 3 条可言——因为第 2 条就不存在。**

逐层排除，确认不是"抓到了但没解密"或"被我漏了"：

| 可能被误判为"漏掉"的情形 | 核查结果 |
|---|---|
| 藏在 CONNECT 隧道里没解密 | ❌ 5 条 CONNECT **全部**指向 `example.com:443`；同一主机另有 **7 条成功解密**的 HTTP（`server: nginx` 的完整响应体都在），说明 Reqable 对该主机 MITM 正常，隧道里没有遗留明文 |
| 藏在别的 CONNECT 目标里 | ❌ **没有**任何指向 `bluearchive-cn.com` 的 CONNECT |
| 连接被丢弃（conn id 跳号） | ❌ conn id `5`–`37` **连续 33 个，无缺口**；53 条全部有归属 |
| `_error` 标记的失败请求 | ❌ **53 条中 `_error` 全为空** |
| 响应体为空被丢 | ❌ 18 条空体全部是 CONNECT 伪条目 / `servertime` / SLS 日志 POST / 抓包中断条目，**无一条是游戏 API** |
| 时间空档里漏抓 | 最大空档 **3.920 s**（15:42:32.641 → 15:42:36.561），前后都是 SDK 日志；即便有请求，也不是游戏 API |
| 编码 / 压缩绕过 grep | ❌ 全文 `packet`=0、`protocol`=0；所有 POST 体要么是明文 JSON、要么是 protobuf 日志、要么是 form，**无加密信封** |
| 被截断（Reqable 只存了前 N 条） | ❌ 首末条完整，`entries` 数组闭合，53 条时间连贯无断层 |

### 4.2 真正该问的问题

HAR 已经把"为什么"写在明面上：

1. `15:42:23.821` 客户端问官方 `state-api` → 得到 `"State":1,"Msg":"服务器维护中，请耐心等待开服！"`
2. `15:42:23.975` 客户端问官方 `gsqc-api/api/state` → 拿到官方配置，`ResourceVersion 202611051844`、`State:1`
3. `15:42:24.3–25.5` 客户端按官方配置下载 manifest（`static.bluearchive-cn.com`，AliyunOSS，全部 HIT）
4. **`15:42:25.532` 之后，客户端再没碰过任何 `bluearchive-cn.com`**
5. `15:42:29.866 / 30.372` SDK 一键登录、用户详情**成功**（本地 `127.0.0.1:8080`）
6. 然后就只剩探测 + 日志，直到抓包在 `15:42:42.135` 被手动停止

> **客户端拿到了"维护中"，于是在 SDK 登录之后没有发起 `POST /api/account/auth`，也就永远走不到 `POST /api/academy/getinfo`。**

而这套 `state-api` / `gsqc-api` / `static` 全部落在官方 CDN（Tengine / TencentEdgeOne / AliyunOSS），**不是我们的 nginx（`server: nginx`）**。

### 4.3 与服务端记录的矛盾点（需要下一轮解决）

| 项 | 服务端记录（上一轮 15:33:38） | 本 HAR（15:42:18–15:42:42） |
|---|---|---|
| `POST /api/account/auth` | 有（回 3456 B） | **无** |
| `POST /api/academy/getinfo` | 有（回 6956 B） | **无** |
| 客户端连的游戏宿主 | （我们） | 官方 `state-api` / `gsqc-api` / `static` |
| 客户端拿到的 state | （我们回的） | 官方回 `State:1` 维护中 |

→ 两次抓取的 **DNS 落地完全不同**。15:33 那一轮，客户端被导到了我们服务器；15:42 这一轮，客户端走的是官方线路。
**这是本轮最需要向上游确认的事实，而不是"第 3 条请求去哪了"。**

---

## 5. 异常条目

### 5.1 CONNECT 隧道（未解密）—— 5 条，全部指向我们服务器

| # | 时间 | 目标 | `Host` 头 | 状态 | `request._status` |
|---|---|---|---|---|---|
| 1 | 15:42:21.479 | `example.com:443` | `example.com:443` | 0 | `aborted` |
| 2 | 15:42:21.481 | `example.com:443` | `example.com:443` | 0 | `aborted` |
| 3 | 15:42:21.483 | `example.com:443` | `example.com:443` | 0 | `aborted` |
| 4 | 15:42:21.991 | `example.com:443` | `example.com:443` | 0 | `aborted` |
| 5 | 15:42:30.406 | `example.com:443` | `example.com:443` | 0 | `aborted` |

**判定：不是"抓到隧道但解不开"。** 理由：

- 5 条 CONNECT 分属 conn `11/12/14/15/30`，各自只有 1 条记录；真正的 HTTP 请求落在**另外**的 conn `13/16/27/28/31/32/33` 上，且**全部成功解密**（拿到 `server: nginx` 的完整响应头和响应体）。
- `request._status = aborted` 是 Reqable 对"隧道建立伪请求"的固定标注，非失败。
- **没有任何 CONNECT 指向 `bluearchive-cn.com`** —— 即：不存在"游戏流量被包在解不开的隧道里"这种情况。

### 5.2 `_error` 非空 —— **0 条**

53 条 `_error` 全部为空（Reqable 未记录任何 TLS/握手/证书错误）。这意味着**不存在 MITM 失败导致的静默丢包**。

### 5.3 响应体为 0 字节 —— 18 / 53 条

| 类别 | 条数 | 明细 |
|---|---|---|
| CONNECT 伪条目 | 5 | 全部 `example.com` |
| `servertime`（服务端对时，本来就只有头） | 2 | `yostar-cn-client-logging…`、`yostar-cn-netsdk-logging…` |
| 阿里云 SLS 日志上报（服务端只回 200 无体） | 8 | `…/logstores/…/shards/lb` ×8 |
| `heartbeat/pulse`（本地 SDK，请求被取消） | 1 | `127.0.0.1:8080/heartbeat/pulse`，`_status=aborted` |
| 抓包中断时仍在飞的 | 2 | `15:42:42.135` 两条 SLS 日志，`_status=processing` |

> **无一条空响应体属于游戏 API。** 空响应体在这里是正常的协议设计或抓包中断，不是"被拦/被丢"。

### 5.4 状态码非 2xx —— 11 条

| # | 时间 | 方法 | 主机 | path | 状态 | 字节 | 判定 |
|---|---|---|---|---|---|---|---|
| 1 | 15:42:18.918 | GET | `down.anticheatexpert.com` | `…/com.RoamingStar.BlueArchive/config2.xml` | **404** | 492 | 反作弊配置拉取失败 |
| 2 | 15:42:19.041 | GET | `down.anticheatexpert.com` | 同上（重试） | **404** | 492 | 同上 |
| 3–7 | 15:42:21.479–30.406 | CONNECT | `example.com` | `/` | **0** | 0 | Reqable 伪条目，非失败 |
| 8 | 15:42:22.187 | POST | `tapsdk.tapapis.cn` | `/sdk-core/v1/gatekeeper?…` | **400** | 697 | TapTap gatekeeper 参数/签名问题 |
| 9 | 15:42:32.547 | POST | `127.0.0.1:8080` | `/heartbeat/pulse` | **0** | 0 | 本地 SDK，请求被取消（`aborted`） |
| 10–11 | 15:42:42.135 | POST | `…log.aliyuncs.com` ×2 | `…/shards/lb` | **0** | 0 | 抓包中断，仍在飞 |

**真正意义上的失败只有 3 条**：反作弊 `config2.xml` 404 ×2、TapTap gatekeeper 400 ×1。
**都不是游戏 API，也不是我们的服务器。**

### 5.5 命中 `bluearchive-cn.com` 的主机（nginx SNI 白名单视角）

| 主机 | 条数 | 实际对端 IP | 对端指纹 | 是否经过我们 |
|---|---|---|---|---|
| `gsqc-api.bluearchive-cn.com` | 1 | `112.13.210.86` | `Server: TencentEdgeOne` | **否** |
| `state-api.bluearchive-cn.com` | 1 | `39.173.144.14` | `Server: Tengine` + `Via` + `EagleId` | **否** |
| `static.bluearchive-cn.com` | 5 | `112.49.41.54` | `Server: AliyunOSS` | **否** |

> 没有任何一个 `*.bluearchive-cn.com` 子域被 SNI 透传/回环到我们服务器——它们**根本没解析到我们**。
> 唯一解析到我们（`<SERVER_IP>`）的域名是 `example.com`，且它是 SDK 探测域名，不是游戏域名。

### 5.6 时间空档 > 2 s

| 空档 | 从前 | 到后 |
|---|---|---|
| **3.920 s** | 15:42:32.641 SLS 日志 | 15:42:36.561 `udata/daq/track/v2` |
| 2.487 s | 15:42:27.379 `gid.tapapis.cn/device/v1/query` | 15:42:29.866 `127.0.0.1/user/quick-login` |
| 2.348 s | 15:42:19.041 反作弊 404 重试 | 15:42:21.389 `127.0.0.1/common/config` |
| 2.057 s | 15:42:37.011 SLS 日志 | 15:42:39.068 SLS 日志 |

> 全部 4 个空档的两端都是 SDK / 日志流量，**没有一个是"游戏请求本该出现"的空洞**。

---

## 6. 与服务端对账

### 6.1 对账表

| 项 | HAR 实际 | 服务端应有 | 差 |
|---|---|---|---|
| 游戏域名（`*bluearchive-cn.com`）请求总数 | **7** | ≥2 | — |
| 游戏域名 **POST** 数 | **0** | **2** | **−2** |
| 到我们 IP（`<SERVER_IP>`）的请求 | 12 | ≥2 | 全部是探测，非游戏 |
| `POST /api/account/auth` | **0** | 1 | **−1** |
| `POST /api/academy/getinfo` | **0** | 1 | **−1** |

### 6.2 判定

**不是"HAR 比服务端多出一条"——恰恰相反，HAR 比服务端少两条。**

- 任务描述里"这一轮应该有 2 条"（auth + academy）这一预期，**在本 HAR 中不成立**。
- 所以不存在"多出来的那条请求"，也就无法给出它的请求体前 500 字节——**它不存在**。

### 6.3 时间锚点不重合

| 事件 | 时间 | 来源 |
|---|---|---|
| 服务端收到 `auth` + `academy` | **15:33:38** | 服务端记录（上一轮） |
| 本 HAR 覆盖区间 | **15:42:18.918 – 15:42:42.135** | 本 HAR |
| 本 HAR 中 SDK 登录成功（本该发 auth 的时刻） | **15:42:30.372** | `127.0.0.1:8080/user/detail` |

两者**相隔 8 分 54 秒**。本 HAR 覆盖的 23.2 秒里，含"该发 auth 的时刻"，且该时刻之后 11.76 秒全程无游戏 API。

---

## 7. 加密信封探测

| 检查项 | 结果 |
|---|---|
| 响应体以 `{"protocol":` 开头 | **0 条** |
| 响应体 base64 且可 gzip/zlib 解开（游戏加密响应特征） | **0 条** |
| 请求体含 `packet` 字段 | **0 条**（全文 `packet` 出现 0 次） |
| 全文出现 `protocol` | **0 次** |

**唯一一条 base64 可解但非 gzip 的**：`static…/catalog_Android.hash`（32 B，`magic=f37d5ad5`）——是资源目录哈希，不是加密包。

**9 条非 JSON 的 POST 体，已确认是 protobuf，不是游戏加密包**：
全部为阿里云 SLS 日志批量上报，protobuf 解析后可见

```
f1: "name"  →  f2: "network_diagnosis"
f1: "kind"  →  f2: "CLIENT"
f1: "traceID" → f2: "13aca0d720251178d736c2f0670d0eb4"
f1: "spanID"  → f2: "19b7325ffca1c28c"
```

即 **SDK 的网络诊断日志**（这也正好解释了那 12 条 `example.com` 探测的来源）。另外 `app.adjust.cn/event` 是 form-urlencoded（`country=CN&ff_coppa=1&api_level=37&hardware_name=PLR110_17.0…`）。

> **结论：这份 HAR 里没有任何游戏协议加密信封。** 它是纯 SDK/运营/资源层的明文流量，游戏协议层（`{"protocol":…}` + `packet`）**完全缺席**。

---

## 8. 局限与下一步

### 8.1 本报告的硬边界（必须如实说明）

1. **抓包窗口只有 23.217 秒**，且结束于 `15:42:42.135` 的**手动停止**（两条在飞请求 `_status=processing`）。**15:42:42.135 之后发生什么，本 HAR 无法回答。**
2. **本 HAR 不含游戏登录交换**，所以"academy 之后有没有第 3 条"这个问题**在这份文件上不可判定**——不是"没有"，是"前提不存在"。
3. 无法从 HAR 反推手机当时的 DNS 配置；"为什么客户端走了官方线路"只能由 DNS/hosts 覆盖状态来解释，**本报告不对此下断言**。

### 8.2 建议的下一步（按性价比排序）

1. **先确认抓包那一刻的 DNS/hosts 覆盖是否生效**。本 HAR 已证明：`state-api` → `39.173.144.14`（官方）、`gs-api` 从未被访问。若预期是导到 `<SERVER_IP>`，那么这一轮抓包的**前置条件就没成立**，后面所有分析都白做。
2. **在服务端确认 15:42 前后有没有收到任何 `state-api`/`gs-api` 的 SNI 连接**。若没有，与 HAR 完全自洽：客户端压根没往我们这边解析。
3. **重抓一轮，且必须满足**：
   - 抓包时长 ≥ 3 分钟（覆盖"卡住"的完整过程，不要 23 秒就停）；
   - 抓包前确认 `state-api.bluearchive-cn.com` / `gs-api.bluearchive-cn.com` 的解析结果指向 `<SERVER_IP>`（Reqable 里看对端 IP 即可当场验证）；
   - 同时记录服务端 `access.log` 时间窗口，两边对齐到秒。
4. **顺带排查两条真实失败**（虽非本问题主因，但会干扰启动流程）：
   - `down.anticheatexpert.com/…/config2.xml` → **404 ×2**（反作弊配置拉不到）
   - `tapsdk.tapapis.cn/sdk-core/v1/gatekeeper` → **400**

### 8.3 复现方式

```powershell
python report\_tmp\baba_deep.py                                   # 全量分析到 stdout
python report\_tmp\baba_deep.py --har <other.har>                  # 换文件
python report\_tmp\baba_deep.py --anchor /api/academy/getinfo --expect 2
python report\_tmp\baba_deep.py --out report\_tmp\out.md --json report\_tmp\out.json
```

脚本为**只读**，不改原 HAR；自动完成 §1–§7 全部检查，锚点不存在时会明确打印"未找到"。

---

## 附录 A：本 HAR 的两份关键响应体（原文）

**`state-api.bluearchive-cn.com/api/state`**（15:42:23.821，200，161 B，IP `39.173.144.14`）

```json
{"Servers":["https://gsqc-api.bluearchive-cn.com/api/","https://gs-api.bluearchive-cn.com/api/"],"State":1,"Msg":"服务器维护中，请耐心等待开服！"}
```

**`gsqc-api.bluearchive-cn.com/api/state`**（15:42:23.975，200，676 B，IP `112.13.210.86`）

```json
{"CallbackUrl":"{\"order_notify\":\"http://gs-inter.bluearchive-cn.com:4000/api/order/notify\",\"survey_notify\":\"http://gs-inter.bluearchive-cn.com:4000\",\"web_notify\":\"http://gs-inter.bluearchive-cn.com:4000/api/web/notify\",\"account_logout\":\"http://gs-inter.bluearchive-cn.com:4000/api/account/logout\"}","CustomerServiceUrl":"","AddressablesCatalogUrlRoots":["https://static.bluearchive-cn.com/prodm39","https://static-qc.bluearchive-cn.com/prodm39","https://static-hs.bluearchive-cn.com/prodm39"],"ResourceVersion":"202611051844","TableVersion":"202611051826","MediaVersion":"202611051836","PatchVersion":"202609291539","State":1,"Msg":"","IsOpenPreDownload":true}
```

**`state-api` 请求头**（客户端指纹）

```
Host: state-api.bluearchive-cn.com
User-Agent: UnityPlayer/2021.3.56f2 (UnityWebRequest/1.0, libcurl/8.10.1-DEV)
Accept: */*
Accept-Encoding: deflate, gzip
APP-VER: 3.0.2
PLATFORM-ID: 1
CHANNEL-ID: 1
SERVER-NAME: prod
Content-Type: application/octet-stream
X-Unity-Version: 2021.3.56f2
```

## 附录 B：`/common/config`（`DetectionAddress` 片段，证明 `example.com` 是探测域名）

```json
"DetectionAddress": {
  "Auto": {
    "DNS": null,
    "HTTP": ["https://example.com/checkhealth.html","https://example.com","https://example.com/api/health"],
    "MTR":  ["https://example.com/checkhealth.html","https://example.com","https://example.com/api/health"],
    "PING": null,
    "TCP": null
  },
  "Enable": true,
  "Internet": "https://example.com"
}
```

---

*报告生成：2026-11-14 · 分析目标 `baba.har` sha256 `08a7b315…aa5cc5` · 只读取证*
