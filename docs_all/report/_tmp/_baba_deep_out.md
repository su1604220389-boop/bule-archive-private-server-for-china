### 1) 规模

| 项 | 值 |
|---|---|
| 文件 | `report\_tmp\baba.har` |
| 字节数 | 209296 B |
| HAR version | 1.2 |
| creator | Reqable 3.3.11 |
| entries 条数 | **53** |
| 有时间戳条目 | 53 |
| 首条（本地 UTC+08:00） | 2026-11-14 15:42:18.918 |
| 末条（本地 UTC+08:00） | 2026-11-14 15:42:42.135 |
| 跨度 | **23.217 秒** |
| 首条（UTC） | 2026-11-14T07:42:18.918000+00:00 |
| 独立主机数 | 15 |

**结构非标准项（如实记录）**：
- 无 log.pages（Reqable 常见，可接受）
- 无 log.browser

### 2) 目标域请求（`*bluearchive-cn.com` + `<SERVER_IP>`）按时间排序

| # | 时间(本地) | 方法 | 主机 | 完整 path | 状态 | 响应字节 | 对端IP | SNI/Host |
|---|---|---|---|---|---|---|---|---|
| 19 | 15:42:23.821 | GET | state-api.bluearchive-cn.com | `/api/state` | 200 | 161 B (161) | 39.173.144.14 | state-api.bluearchive-cn.com |
| 20 | 15:42:23.975 | GET | gsqc-api.bluearchive-cn.com | `/api/state` | 200 | 676 B (676) | 112.13.210.86 | gsqc-api.bluearchive-cn.com |
| 21 | 15:42:24.347 | GET | static.bluearchive-cn.com | `/prodm39/Manifest/Patch/202609291539/patch_assetmanifest` | 200 | 78 B (78) | 112.49.41.54 | static.bluearchive-cn.com |
| 22 | 15:42:24.471 | GET | static.bluearchive-cn.com | `/prodm39/Manifest/TableBundles/202611051826/TableManifestHash` | 200 | 10 B (10) | 112.49.41.54 | static.bluearchive-cn.com |
| 23 | 15:42:24.638 | GET | static.bluearchive-cn.com | `/prodm39/Manifest/MediaResources/202611051836/MediaManifestHash` | 200 | 11 B (11) | 112.49.41.54 | static.bluearchive-cn.com |
| 25 | 15:42:25.342 | GET | static.bluearchive-cn.com | `/prodm39/AssetBundles/Catalog/202611051844/Android/bundleDownloadInfo.hash` | 200 | 9 B (9) | 112.49.41.54 | static.bluearchive-cn.com |
| 26 | 15:42:25.532 | GET | static.bluearchive-cn.com | `/prodm39/AssetBundles/Catalog/202611051844/Android/catalog_Android.hash` | 200 | 32 B (32) | 112.49.41.54 | static.bluearchive-cn.com |

目标域条目总数：**7**（其中 POST：0）

#### 2b) `/api/academy/getinfo` 之后的**全部**条目（不分主机）

未在 HAR 中找到 `/api/academy/getinfo`，无法判定"之后"。

### 3) 全部主机 → 路径清单（不截断）

共 **15** 个主机。

#### `down.anticheatexpert.com` — 2 条, 1 个不同 path, IP: 2409:8c30:40:2d07::4

| path | 次数 | 方法 | 状态 |
|---|---|---|---|
| `/gamesafe/mobile/huiwan/android/com.RoamingStar.BlueArchive/config2.xml` | 2 | GET | 404 |

#### `127.0.0.1` — 6 条, 6 个不同 path, IP: 127.0.0.1

| path | 次数 | 方法 | 状态 |
|---|---|---|---|
| `/common/config` | 1 | POST | 200 |
| `/common/geo-ip` | 1 | POST | 200 |
| `/health-game/duration` | 1 | POST | 200 |
| `/heartbeat/pulse` | 1 | POST | 0 |
| `/user/detail` | 1 | POST | 200 |
| `/user/quick-login` | 1 | POST | 200 |

#### `er.ns.aliyuncs.com` — 1 条, 1 个不同 path, IP: 2409:8c28:2880:7:3::43

| path | 次数 | 方法 | 状态 |
|---|---|---|---|
| `/policy?policyKey=d4b34a481dd004d56088ecbeeb6a5df88b8483dd1399cb0ee54d16c015f464bd93fa27316d86d79426a37a91bf0b99d76a9118cc2f3f798cfb69cf8817d45d61&policyVersion=31&aliyunId=1294058570621990&ipaAppId=AzUrJxv6mZ9TPGXXfxUHFn&deviceId=ZjEyYWE1ODllMjUzNGNjMQ==&sdkVer=1.0.1.9&biz=` | 1 | GET | 200 |

#### `yostar-cn-client-logging.cn-shanghai.log.aliyuncs.com` — 6 条, 2 个不同 path, IP: 106.15.253.172

| path | 次数 | 方法 | 状态 |
|---|---|---|---|
| `/logstores/yostar-cn-client-logging/shards/lb` | 5 | POST | 0,200 |
| `/servertime` | 1 | GET | 200 |

#### `example.com` — 12 条, 3 个不同 path, IP: <SERVER_IP>

| path | 次数 | 方法 | 状态 |
|---|---|---|---|
| `/` | 7 | CONNECT,GET | 0,200 |
| `/api/health` | 3 | GET | 200 |
| `/checkhealth.html` | 2 | GET | 200 |

#### `yostar-cn-netsdk-logging.cn-shanghai.log.aliyuncs.com` — 6 条, 2 个不同 path, IP: 106.15.253.211

| path | 次数 | 方法 | 状态 |
|---|---|---|---|
| `/logstores/ipa-azurjxv6mz9tpgxxfxuhfn-raw/shards/lb` | 5 | POST | 0,200 |
| `/servertime` | 1 | GET | 200 |

#### `tapsdk.tapapis.cn` — 1 条, 1 个不同 path, IP: 2408:4003:4::663b:b42d

| path | 次数 | 方法 | 状态 |
|---|---|---|---|
| `/sdk-core/v1/gatekeeper?client_id=fdcxdbtzmnsj0g2au5` | 1 | POST | 400 |

#### `fp-it.fengkongcloud.com` — 2 条, 2 个不同 path, IP: 111.31.3.208

| path | 次数 | 方法 | 状态 |
|---|---|---|---|
| `/deviceprofile/v4` | 1 | POST | 200 |
| `/v3/cloudconf` | 1 | POST | 200 |

#### `udata-api.open.yostar.net` — 7 条, 2 个不同 path, IP: 112.13.210.86

| path | 次数 | 方法 | 状态 |
|---|---|---|---|
| `/daq/track/v2` | 6 | POST | 200 |
| `/daq/init/v2?os=1&code=&sub_channel_name=` | 1 | GET | 200 |

#### `state-api.bluearchive-cn.com` — 1 条, 1 个不同 path, IP: 39.173.144.14

| path | 次数 | 方法 | 状态 |
|---|---|---|---|
| `/api/state` | 1 | GET | 200 |

#### `gsqc-api.bluearchive-cn.com` — 1 条, 1 个不同 path, IP: 112.13.210.86

| path | 次数 | 方法 | 状态 |
|---|---|---|---|
| `/api/state` | 1 | GET | 200 |

#### `static.bluearchive-cn.com` — 5 条, 5 个不同 path, IP: 112.49.41.54

| path | 次数 | 方法 | 状态 |
|---|---|---|---|
| `/prodm39/AssetBundles/Catalog/202611051844/Android/bundleDownloadInfo.hash` | 1 | GET | 200 |
| `/prodm39/AssetBundles/Catalog/202611051844/Android/catalog_Android.hash` | 1 | GET | 200 |
| `/prodm39/Manifest/MediaResources/202611051836/MediaManifestHash` | 1 | GET | 200 |
| `/prodm39/Manifest/Patch/202609291539/patch_assetmanifest` | 1 | GET | 200 |
| `/prodm39/Manifest/TableBundles/202611051826/TableManifestHash` | 1 | GET | 200 |

#### `cbsipv4.shuzilm.cn` — 1 条, 1 个不同 path, IP: 39.107.242.47

| path | 次数 | 方法 | 状态 |
|---|---|---|---|
| `/ip?pkg=com.RoamingStar.BlueArchive&t=1&v=2&s=A76876716F77805B579ACE14873149DC` | 1 | GET | 200 |

#### `gid.tapapis.cn` — 1 条, 1 个不同 path, IP: 39.107.196.62

| path | 次数 | 方法 | 状态 |
|---|---|---|---|
| `/device/v1/query?client_id=fdcxdbtzmnsj0g2au5` | 1 | POST | 200 |

#### `app.adjust.cn` — 1 条, 1 个不同 path, IP: 47.104.30.117

| path | 次数 | 方法 | 状态 |
|---|---|---|---|
| `/event` | 1 | POST | 200 |

#### 3b) 重点关注主机是否出现

| 主机 | 出现? | 条数 |
|---|---|---|
| `gsqc-api.bluearchive-cn.com` | **是** | 1 |
| `gs-api.bluearchive-cn.com` | 否 | 0 |
| `state-api.bluearchive-cn.com` | **是** | 1 |
| `gm-api.bluearchive-cn.com` | 否 | 0 |
| `gs-inter.bluearchive-cn.com` | 否 | 0 |
| `notice.bluearchive-cn.com` | 否 | 0 |
| `customer.yostar.net` | 否 | 0 |
| `sdk-api.yostar.cn` | 否 | 0 |
| `<SERVER_IP>` | 否 | 0 |

所有 `*bluearchive-cn.com` 子域实际出现：`gsqc-api.bluearchive-cn.com`, `state-api.bluearchive-cn.com`, `static.bluearchive-cn.com`

#### 3c) 直连 IP 的条目（含 SNI / Host 头）

| # | 时间 | 方法 | 主机(URL) | 对端IP(serverIPAddress) | SNI/:authority | Host 头 | path | 状态 |
|---|---|---|---|---|---|---|---|---|
| 3 | 15:42:21.389 | POST | `127.0.0.1` | 127.0.0.1 | - | 127.0.0.1:8080 | `/common/config` | 200 |
| 30 | 15:42:29.866 | POST | `127.0.0.1` | 127.0.0.1 | - | 127.0.0.1:8080 | `/user/quick-login` | 200 |
| 33 | 15:42:30.372 | POST | `127.0.0.1` | 127.0.0.1 | - | 127.0.0.1:8080 | `/user/detail` | 200 |
| 39 | 15:42:32.018 | POST | `127.0.0.1` | 127.0.0.1 | - | 127.0.0.1:8080 | `/health-game/duration` | 200 |
| 41 | 15:42:32.547 | POST | `127.0.0.1` | - | - | 127.0.0.1:8080 | `/heartbeat/pulse` | 0 |
| 42 | 15:42:32.547 | POST | `127.0.0.1` | 127.0.0.1 | - | 127.0.0.1:8080 | `/common/geo-ip` | 200 |

#### 3d) `serverIPAddress == <SERVER_IP>` 的条目（对端是我们服务器的）

| # | 时间 | 方法 | 主机 | path | 状态 | 字节 | SNI/:authority | Host |
|---|---|---|---|---|---|---|---|---|
| 6 | 15:42:21.479 | CONNECT | `example.com` | `/` | 0 | 0 B | - | example.com:443 |
| 7 | 15:42:21.481 | CONNECT | `example.com` | `/` | 0 | 0 B | - | example.com:443 |
| 8 | 15:42:21.483 | CONNECT | `example.com` | `/` | 0 | 0 B | - | example.com:443 |
| 10 | 15:42:21.991 | CONNECT | `example.com` | `/` | 0 | 0 B | - | example.com:443 |
| 14 | 15:42:22.264 | GET | `example.com` | `/` | 200 | 2 B | example.com | - |
| 16 | 15:42:22.516 | GET | `example.com` | `/api/health` | 200 | 15 B | example.com | - |
| 31 | 15:42:30.217 | GET | `example.com` | `/checkhealth.html` | 200 | 2 B | example.com | - |
| 32 | 15:42:30.238 | GET | `example.com` | `/checkhealth.html` | 200 | 2 B | example.com | - |
| 34 | 15:42:30.406 | CONNECT | `example.com` | `/` | 0 | 0 B | - | example.com:443 |
| 35 | 15:42:30.967 | GET | `example.com` | `/` | 200 | 2 B | example.com | - |
| 36 | 15:42:31.026 | GET | `example.com` | `/api/health` | 200 | 15 B | example.com | - |
| 37 | 15:42:31.233 | GET | `example.com` | `/api/health` | 200 | 15 B | example.com | - |

### 4) 全量时间线（53 条，按 startedDateTime）

```
15:42:18.918  GET    down.anticheatexpert.com/gamesafe/mobile/huiwan/android/com.RoamingStar.BlueArchive/config2.xml  404  492 B
15:42:19.041  GET    down.anticheatexpert.com/gamesafe/mobile/huiwan/android/com.RoamingStar.BlueArchive/config2.xml  404  492 B
15:42:21.389  POST   127.0.0.1/common/config  200  7.7 KB
15:42:21.447  GET    er.ns.aliyuncs.com/policy?policyKey=d4b34a481dd004d56088ecbeeb6a5df88b8483dd1399cb0ee54d16c015f464bd93fa27316d86d79426a37a91bf0b99d76a9118cc2f3f798cfb69cf8817d45d61&policyVersion=31&aliyunId=1294058570621990&ipaAppId=AzUrJxv6mZ9TPGXXfxUHFn&deviceId=ZjEyYWE1ODllMjUzNGNjMQ==&sdkVer=1.0.1.9&biz=  200  2.0 KB
15:42:21.475  GET    yostar-cn-client-logging.cn-shanghai.log.aliyuncs.com/servertime  200  0 B
15:42:21.479  CONNECT example.com/  0  0 B  [NO-STATUS]
15:42:21.481  CONNECT example.com/  0  0 B  [NO-STATUS]
15:42:21.483  CONNECT example.com/  0  0 B  [NO-STATUS]
15:42:21.487  GET    yostar-cn-netsdk-logging.cn-shanghai.log.aliyuncs.com/servertime  200  0 B
15:42:21.991  CONNECT example.com/  0  0 B  [NO-STATUS]
15:42:22.187  POST   tapsdk.tapapis.cn/sdk-core/v1/gatekeeper?client_id=fdcxdbtzmnsj0g2au5  400  697 B
15:42:22.203  POST   fp-it.fengkongcloud.com/v3/cloudconf  200  88 B
15:42:22.226  GET    udata-api.open.yostar.net/daq/init/v2?os=1&code=&sub_channel_name=  200  194 B
15:42:22.264  GET    example.com/  200  2 B
15:42:22.365  POST   udata-api.open.yostar.net/daq/track/v2  200  51 B
15:42:22.516  GET    example.com/api/health  200  15 B
15:42:22.550  POST   fp-it.fengkongcloud.com/deviceprofile/v4  200  185 B
15:42:23.006  POST   udata-api.open.yostar.net/daq/track/v2  200  51 B
15:42:23.821  GET    state-api.bluearchive-cn.com/api/state  200  161 B
15:42:23.975  GET    gsqc-api.bluearchive-cn.com/api/state  200  676 B
15:42:24.347  GET    static.bluearchive-cn.com/prodm39/Manifest/Patch/202609291539/patch_assetmanifest  200  78 B
15:42:24.471  GET    static.bluearchive-cn.com/prodm39/Manifest/TableBundles/202611051826/TableManifestHash  200  10 B
15:42:24.638  GET    static.bluearchive-cn.com/prodm39/Manifest/MediaResources/202611051836/MediaManifestHash  200  11 B
15:42:25.247  GET    cbsipv4.shuzilm.cn/ip?pkg=com.RoamingStar.BlueArchive&t=1&v=2&s=A76876716F77805B579ACE14873149DC  200  14 B
15:42:25.342  GET    static.bluearchive-cn.com/prodm39/AssetBundles/Catalog/202611051844/Android/bundleDownloadInfo.hash  200  9 B
15:42:25.532  GET    static.bluearchive-cn.com/prodm39/AssetBundles/Catalog/202611051844/Android/catalog_Android.hash  200  32 B  ⬅ 最后一条游戏服请求
15:42:26.371  POST   yostar-cn-client-logging.cn-shanghai.log.aliyuncs.com/logstores/yostar-cn-client-logging/shards/lb  200  0 B
15:42:26.380  POST   yostar-cn-netsdk-logging.cn-shanghai.log.aliyuncs.com/logstores/ipa-azurjxv6mz9tpgxxfxuhfn-raw/shards/lb  200  0 B
15:42:27.379  POST   gid.tapapis.cn/device/v1/query?client_id=fdcxdbtzmnsj0g2au5  200  84 B
15:42:29.866  POST   127.0.0.1/user/quick-login  200  847 B
15:42:30.217  GET    example.com/checkhealth.html  200  2 B
15:42:30.238  GET    example.com/checkhealth.html  200  2 B
15:42:30.372  POST   127.0.0.1/user/detail  200  847 B
15:42:30.406  CONNECT example.com/  0  0 B  [NO-STATUS]
15:42:30.967  GET    example.com/  200  2 B
15:42:31.026  GET    example.com/api/health  200  15 B
15:42:31.233  GET    example.com/api/health  200  15 B
15:42:32.008  POST   yostar-cn-client-logging.cn-shanghai.log.aliyuncs.com/logstores/yostar-cn-client-logging/shards/lb  200  0 B
15:42:32.018  POST   127.0.0.1/health-game/duration  200  70 B
15:42:32.540  POST   udata-api.open.yostar.net/daq/track/v2  200  51 B
15:42:32.547  POST   127.0.0.1/heartbeat/pulse  0  0 B  [NO-STATUS]
15:42:32.547  POST   127.0.0.1/common/geo-ip  200  57 B
15:42:32.641  POST   yostar-cn-netsdk-logging.cn-shanghai.log.aliyuncs.com/logstores/ipa-azurjxv6mz9tpgxxfxuhfn-raw/shards/lb  200  0 B
15:42:36.561  POST   udata-api.open.yostar.net/daq/track/v2  200  51 B
15:42:36.619  POST   udata-api.open.yostar.net/daq/track/v2  200  51 B
15:42:36.642  POST   yostar-cn-netsdk-logging.cn-shanghai.log.aliyuncs.com/logstores/ipa-azurjxv6mz9tpgxxfxuhfn-raw/shards/lb  200  0 B
15:42:36.783  POST   app.adjust.cn/event  200  70 B
15:42:37.011  POST   yostar-cn-client-logging.cn-shanghai.log.aliyuncs.com/logstores/yostar-cn-client-logging/shards/lb  200  0 B
15:42:39.068  POST   yostar-cn-client-logging.cn-shanghai.log.aliyuncs.com/logstores/yostar-cn-client-logging/shards/lb  200  0 B
15:42:40.627  POST   yostar-cn-netsdk-logging.cn-shanghai.log.aliyuncs.com/logstores/ipa-azurjxv6mz9tpgxxfxuhfn-raw/shards/lb  200  0 B
15:42:40.942  POST   udata-api.open.yostar.net/daq/track/v2  200  51 B
15:42:42.135  POST   yostar-cn-client-logging.cn-shanghai.log.aliyuncs.com/logstores/yostar-cn-client-logging/shards/lb  0  0 B  [NO-STATUS]
15:42:42.135  POST   yostar-cn-netsdk-logging.cn-shanghai.log.aliyuncs.com/logstores/ipa-azurjxv6mz9tpgxxfxuhfn-raw/shards/lb  0  0 B  [NO-STATUS]
```

- 最后一条**游戏服**请求：**15:42:25.532 `static.bluearchive-cn.com/prodm39/AssetBundles/Catalog/202611051844/Android/catalog_Android.hash`** 状态 200，32 B
- 之后还有 **27** 条请求（非游戏服）：
  - 15:42:26.371 `yostar-cn-client-logging.cn-shanghai.log.aliyuncs.com/logstores/yostar-cn-client-logging/shards/lb` 200 0 B
  - 15:42:26.380 `yostar-cn-netsdk-logging.cn-shanghai.log.aliyuncs.com/logstores/ipa-azurjxv6mz9tpgxxfxuhfn-raw/shards/lb` 200 0 B
  - 15:42:27.379 `gid.tapapis.cn/device/v1/query?client_id=fdcxdbtzmnsj0g2au5` 200 84 B
  - 15:42:29.866 `127.0.0.1/user/quick-login` 200 847 B
  - 15:42:30.217 `example.com/checkhealth.html` 200 2 B
  - 15:42:30.238 `example.com/checkhealth.html` 200 2 B
  - 15:42:30.372 `127.0.0.1/user/detail` 200 847 B
  - 15:42:30.406 `example.com/` 0 0 B
  - 15:42:30.967 `example.com/` 200 2 B
  - 15:42:31.026 `example.com/api/health` 200 15 B
  - 15:42:31.233 `example.com/api/health` 200 15 B
  - 15:42:32.008 `yostar-cn-client-logging.cn-shanghai.log.aliyuncs.com/logstores/yostar-cn-client-logging/shards/lb` 200 0 B
  - 15:42:32.018 `127.0.0.1/health-game/duration` 200 70 B
  - 15:42:32.540 `udata-api.open.yostar.net/daq/track/v2` 200 51 B
  - 15:42:32.547 `127.0.0.1/heartbeat/pulse` 0 0 B
  - 15:42:32.547 `127.0.0.1/common/geo-ip` 200 57 B
  - 15:42:32.641 `yostar-cn-netsdk-logging.cn-shanghai.log.aliyuncs.com/logstores/ipa-azurjxv6mz9tpgxxfxuhfn-raw/shards/lb` 200 0 B
  - 15:42:36.561 `udata-api.open.yostar.net/daq/track/v2` 200 51 B
  - 15:42:36.619 `udata-api.open.yostar.net/daq/track/v2` 200 51 B
  - 15:42:36.642 `yostar-cn-netsdk-logging.cn-shanghai.log.aliyuncs.com/logstores/ipa-azurjxv6mz9tpgxxfxuhfn-raw/shards/lb` 200 0 B
  - 15:42:36.783 `app.adjust.cn/event` 200 70 B
  - 15:42:37.011 `yostar-cn-client-logging.cn-shanghai.log.aliyuncs.com/logstores/yostar-cn-client-logging/shards/lb` 200 0 B
  - 15:42:39.068 `yostar-cn-client-logging.cn-shanghai.log.aliyuncs.com/logstores/yostar-cn-client-logging/shards/lb` 200 0 B
  - 15:42:40.627 `yostar-cn-netsdk-logging.cn-shanghai.log.aliyuncs.com/logstores/ipa-azurjxv6mz9tpgxxfxuhfn-raw/shards/lb` 200 0 B
  - 15:42:40.942 `udata-api.open.yostar.net/daq/track/v2` 200 51 B
  - 15:42:42.135 `yostar-cn-client-logging.cn-shanghai.log.aliyuncs.com/logstores/yostar-cn-client-logging/shards/lb` 0 0 B
  - 15:42:42.135 `yostar-cn-netsdk-logging.cn-shanghai.log.aliyuncs.com/logstores/ipa-azurjxv6mz9tpgxxfxuhfn-raw/shards/lb` 0 0 B

### 5) 异常条目

#### 5.1 CONNECT 隧道（未解密）

共 5 条 CONNECT：

| # | 时间 | 目标 | 状态 |
|---|---|---|---|
| 6 | 15:42:21.479 | `https://example.com` | 0 |
| 7 | 15:42:21.481 | `https://example.com` | 0 |
| 8 | 15:42:21.483 | `https://example.com` | 0 |
| 10 | 15:42:21.991 | `https://example.com` | 0 |
| 34 | 15:42:30.406 | `https://example.com` | 0 |

#### 5.2 `_error` 非空

无 `_error` 非空条目。

#### 5.3 响应体为 0 字节

共 **18** / 53 条。

| # | 时间 | 方法 | 主机 | path | 状态 | content.size | bodySize | content.mimeType |
|---|---|---|---|---|---|---|---|---|
| 5 | 15:42:21.475 | GET | `yostar-cn-client-logging.cn-shanghai.log.aliyuncs.com` | `/servertime` | 200 | 0 | 0 | None |
| 6 | 15:42:21.479 | CONNECT | `example.com` | `/` | 0 | 0 | 0 | None |
| 7 | 15:42:21.481 | CONNECT | `example.com` | `/` | 0 | 0 | 0 | None |
| 8 | 15:42:21.483 | CONNECT | `example.com` | `/` | 0 | 0 | 0 | None |
| 9 | 15:42:21.487 | GET | `yostar-cn-netsdk-logging.cn-shanghai.log.aliyuncs.com` | `/servertime` | 200 | 0 | 0 | None |
| 10 | 15:42:21.991 | CONNECT | `example.com` | `/` | 0 | 0 | 0 | None |
| 27 | 15:42:26.371 | POST | `yostar-cn-client-logging.cn-shanghai.log.aliyuncs.com` | `/logstores/yostar-cn-client-logging/shards/lb` | 200 | 0 | 0 | None |
| 28 | 15:42:26.380 | POST | `yostar-cn-netsdk-logging.cn-shanghai.log.aliyuncs.com` | `/logstores/ipa-azurjxv6mz9tpgxxfxuhfn-raw/shards/lb` | 200 | 0 | 0 | None |
| 34 | 15:42:30.406 | CONNECT | `example.com` | `/` | 0 | 0 | 0 | None |
| 38 | 15:42:32.008 | POST | `yostar-cn-client-logging.cn-shanghai.log.aliyuncs.com` | `/logstores/yostar-cn-client-logging/shards/lb` | 200 | 0 | 0 | None |
| 41 | 15:42:32.547 | POST | `127.0.0.1` | `/heartbeat/pulse` | 0 | 0 | 0 | None |
| 43 | 15:42:32.641 | POST | `yostar-cn-netsdk-logging.cn-shanghai.log.aliyuncs.com` | `/logstores/ipa-azurjxv6mz9tpgxxfxuhfn-raw/shards/lb` | 200 | 0 | 0 | None |
| 46 | 15:42:36.642 | POST | `yostar-cn-netsdk-logging.cn-shanghai.log.aliyuncs.com` | `/logstores/ipa-azurjxv6mz9tpgxxfxuhfn-raw/shards/lb` | 200 | 0 | 0 | None |
| 48 | 15:42:37.011 | POST | `yostar-cn-client-logging.cn-shanghai.log.aliyuncs.com` | `/logstores/yostar-cn-client-logging/shards/lb` | 200 | 0 | 0 | None |
| 49 | 15:42:39.068 | POST | `yostar-cn-client-logging.cn-shanghai.log.aliyuncs.com` | `/logstores/yostar-cn-client-logging/shards/lb` | 200 | 0 | 0 | None |
| 50 | 15:42:40.627 | POST | `yostar-cn-netsdk-logging.cn-shanghai.log.aliyuncs.com` | `/logstores/ipa-azurjxv6mz9tpgxxfxuhfn-raw/shards/lb` | 200 | 0 | 0 | None |
| 52 | 15:42:42.135 | POST | `yostar-cn-client-logging.cn-shanghai.log.aliyuncs.com` | `/logstores/yostar-cn-client-logging/shards/lb` | 0 | 0 | 0 | None |
| 53 | 15:42:42.135 | POST | `yostar-cn-netsdk-logging.cn-shanghai.log.aliyuncs.com` | `/logstores/ipa-azurjxv6mz9tpgxxfxuhfn-raw/shards/lb` | 0 | 0 | 0 | None |

#### 5.4 状态码非 2xx（含 0 / null）

共 **11** 条：

| # | 时间 | 方法 | 主机 | path | 状态 | 字节 | _error |
|---|---|---|---|---|---|---|---|
| 1 | 15:42:18.918 | GET | `down.anticheatexpert.com` | `/gamesafe/mobile/huiwan/android/com.RoamingStar.BlueArchive/config2.xml` | **404** | 492 B | - |
| 2 | 15:42:19.041 | GET | `down.anticheatexpert.com` | `/gamesafe/mobile/huiwan/android/com.RoamingStar.BlueArchive/config2.xml` | **404** | 492 B | - |
| 6 | 15:42:21.479 | CONNECT | `example.com` | `/` | **0** | 0 B | - |
| 7 | 15:42:21.481 | CONNECT | `example.com` | `/` | **0** | 0 B | - |
| 8 | 15:42:21.483 | CONNECT | `example.com` | `/` | **0** | 0 B | - |
| 10 | 15:42:21.991 | CONNECT | `example.com` | `/` | **0** | 0 B | - |
| 11 | 15:42:22.187 | POST | `tapsdk.tapapis.cn` | `/sdk-core/v1/gatekeeper?client_id=fdcxdbtzmnsj0g2au5` | **400** | 697 B | - |
| 34 | 15:42:30.406 | CONNECT | `example.com` | `/` | **0** | 0 B | - |
| 41 | 15:42:32.547 | POST | `127.0.0.1` | `/heartbeat/pulse` | **0** | 0 B | - |
| 52 | 15:42:42.135 | POST | `yostar-cn-client-logging.cn-shanghai.log.aliyuncs.com` | `/logstores/yostar-cn-client-logging/shards/lb` | **0** | 0 B | - |
| 53 | 15:42:42.135 | POST | `yostar-cn-netsdk-logging.cn-shanghai.log.aliyuncs.com` | `/logstores/ipa-azurjxv6mz9tpgxxfxuhfn-raw/shards/lb` | **0** | 0 B | - |

#### 5.5 命中 `bluearchive-cn.com` 的主机（nginx SNI 白名单需覆盖）

- `gsqc-api.bluearchive-cn.com` — 1 条，IP 112.13.210.86
- `state-api.bluearchive-cn.com` — 1 条，IP 39.173.144.14
- `static.bluearchive-cn.com` — 5 条，IP 112.49.41.54

#### 5.6 时间空档 > 2s（可能藏着未抓到的请求）

| 空档 | 从前 | 到后 |
|---|---|---|
| **3.920s** | 15:42:32.641 `yostar-cn-netsdk-logging.cn-shanghai.log.aliyuncs.com/logstores/ipa-azurjxv6mz9tpgxxfxuhfn-raw/shards/lb` | 15:42:36.561 `udata-api.open.yostar.net/daq/track/v2` |
| **2.487s** | 15:42:27.379 `gid.tapapis.cn/device/v1/query?client_id=fdcxdbtzmnsj0g2au5` | 15:42:29.866 `127.0.0.1/user/quick-login` |
| **2.348s** | 15:42:19.041 `down.anticheatexpert.com/gamesafe/mobile/huiwan/android/com.RoamingStar.BlueArchive/config2.xml` | 15:42:21.389 `127.0.0.1/common/config` |
| **2.057s** | 15:42:37.011 `yostar-cn-client-logging.cn-shanghai.log.aliyuncs.com/logstores/yostar-cn-client-logging/shards/lb` | 15:42:39.068 `yostar-cn-client-logging.cn-shanghai.log.aliyuncs.com/logstores/yostar-cn-client-logging/shards/lb` |

### 6) 加密信封探测

#### 6.1 响应体以 `{"protocol":` 开头

**无**。HAR 里没有任何游戏协议加密响应。

#### 6.2 响应体 base64 + gzip/zlib 可解

**无**。

base64 可解但非 gzip/zlib 的响应（1 条，可能是图片/加密块）：
- 15:42:25.532 `static.bluearchive-cn.com/prodm39/AssetBundles/Catalog/202611051844/Android/catalog_Android.hash` — b64 ok (magic=f37d5ad5) but not gzip/zlib

#### 6.3 请求体 `packet` 字段可见性

POST 请求体中可见字段：

| # | 时间 | 主机 | path | 请求体字节 | JSON keys | 有 packet? |
|---|---|---|---|---|---|---|
| 3 | 15:42:21.389 | `127.0.0.1` | `/common/config` | 2 | `` | 否 |
| 11 | 15:42:22.187 | `tapsdk.tapapis.cn` | `/sdk-core/v1/gatekeeper?client_id=fdcxdbtzmnsj0g2au5` | 117 | `package_name,package_sign,platform` | 否 |
| 12 | 15:42:22.203 | `fp-it.fengkongcloud.com` | `/v3/cloudconf` | 257 | `data,organization` | 否 |
| 15 | 15:42:22.365 | `udata-api.open.yostar.net` | `/daq/track/v2` | 2251 | `data` | 否 |
| 17 | 15:42:22.550 | `fp-it.fengkongcloud.com` | `/deviceprofile/v4` | 4488 | `appId,compress,data,encode,ep,organization,os,tn` | 否 |
| 18 | 15:42:23.006 | `udata-api.open.yostar.net` | `/daq/track/v2` | 1143 | `data` | 否 |
| 27 | 15:42:26.371 | `yostar-cn-client-logging.cn-shanghai.log.aliyuncs.com` | `/logstores/yostar-cn-client-logging/shards/lb` | 25672 | `(非JSON)` | 否 |
| 28 | 15:42:26.380 | `yostar-cn-netsdk-logging.cn-shanghai.log.aliyuncs.com` | `/logstores/ipa-azurjxv6mz9tpgxxfxuhfn-raw/shards/lb` | 4544 | `(非JSON)` | 否 |
| 29 | 15:42:27.379 | `gid.tapapis.cn` | `/device/v1/query?client_id=fdcxdbtzmnsj0g2au5` | 1056 | `metadata,platform` | 否 |
| 30 | 15:42:29.866 | `127.0.0.1` | `/user/quick-login` | 2 | `` | 否 |
| 33 | 15:42:30.372 | `127.0.0.1` | `/user/detail` | 2 | `` | 否 |
| 38 | 15:42:32.008 | `yostar-cn-client-logging.cn-shanghai.log.aliyuncs.com` | `/logstores/yostar-cn-client-logging/shards/lb` | 7628 | `(非JSON)` | 否 |
| 39 | 15:42:32.018 | `127.0.0.1` | `/health-game/duration` | 2 | `` | 否 |
| 40 | 15:42:32.540 | `udata-api.open.yostar.net` | `/daq/track/v2` | 1337 | `data` | 否 |
| 41 | 15:42:32.547 | `127.0.0.1` | `/heartbeat/pulse` | 0 | `(空)` | 否 |
| 42 | 15:42:32.547 | `127.0.0.1` | `/common/geo-ip` | 2 | `` | 否 |
| 43 | 15:42:32.641 | `yostar-cn-netsdk-logging.cn-shanghai.log.aliyuncs.com` | `/logstores/ipa-azurjxv6mz9tpgxxfxuhfn-raw/shards/lb` | 7020 | `(非JSON)` | 否 |
| 44 | 15:42:36.561 | `udata-api.open.yostar.net` | `/daq/track/v2` | 1318 | `data` | 否 |
| 45 | 15:42:36.619 | `udata-api.open.yostar.net` | `/daq/track/v2` | 1309 | `data` | 否 |
| 46 | 15:42:36.642 | `yostar-cn-netsdk-logging.cn-shanghai.log.aliyuncs.com` | `/logstores/ipa-azurjxv6mz9tpgxxfxuhfn-raw/shards/lb` | 4512 | `(非JSON)` | 否 |
| 47 | 15:42:36.783 | `app.adjust.cn` | `/event` | 1152 | `(非JSON)` | 否 |
| 48 | 15:42:37.011 | `yostar-cn-client-logging.cn-shanghai.log.aliyuncs.com` | `/logstores/yostar-cn-client-logging/shards/lb` | 12072 | `(非JSON)` | 否 |
| 49 | 15:42:39.068 | `yostar-cn-client-logging.cn-shanghai.log.aliyuncs.com` | `/logstores/yostar-cn-client-logging/shards/lb` | 8168 | `(非JSON)` | 否 |
| 50 | 15:42:40.627 | `yostar-cn-netsdk-logging.cn-shanghai.log.aliyuncs.com` | `/logstores/ipa-azurjxv6mz9tpgxxfxuhfn-raw/shards/lb` | 3848 | `(非JSON)` | 否 |
| 51 | 15:42:40.942 | `udata-api.open.yostar.net` | `/daq/track/v2` | 1142 | `data` | 否 |
| 52 | 15:42:42.135 | `yostar-cn-client-logging.cn-shanghai.log.aliyuncs.com` | `/logstores/yostar-cn-client-logging/shards/lb` | 0 | `(空)` | 否 |
| 53 | 15:42:42.135 | `yostar-cn-netsdk-logging.cn-shanghai.log.aliyuncs.com` | `/logstores/ipa-azurjxv6mz9tpgxxfxuhfn-raw/shards/lb` | 0 | `(空)` | 否 |

非 JSON 的 POST 体（可能是 base64 加密包）9 条：
- 15:42:26.371 `yostar-cn-client-logging.cn-shanghai.log.aliyuncs.com/logstores/yostar-cn-client-logging/shards/lb` — 25672 B，前 60: `8p8K1gEI4aHg1wYSkQEKA21zZxKJAVtBaXJpU0RLXVsxLjE2LjFdWzE5NTU3`
- 15:42:26.380 `yostar-cn-netsdk-logging.cn-shanghai.log.aliyuncs.com/logstores/ipa-azurjxv6mz9tpgxxfxuhfn-raw/shards/lb` — 4544 B，前 60: `8nkK/hgI4aHg1wYSGQoEbmFtZRIRbmV0d29ya19kaWFnbm9zaXMSDgoEa2lu`
- 15:42:32.008 `yostar-cn-client-logging.cn-shanghai.log.aliyuncs.com/logstores/yostar-cn-client-logging/shards/lb` — 7628 B，前 60: `8yAKqAEI56Hg1wYSZAoDbXNnEl1bQWlyaVNES11bMS4xNi4xXVsxOTU1N11b`
- 15:42:32.641 `yostar-cn-netsdk-logging.cn-shanghai.log.aliyuncs.com/logstores/ipa-azurjxv6mz9tpgxxfxuhfn-raw/shards/lb` — 7020 B，前 60: `8nkK9hoI6KHg1wYSGQoEbmFtZRIRbmV0d29ya19kaWFnbm9zaXMSDgoEa2lu`
- 15:42:36.642 `yostar-cn-netsdk-logging.cn-shanghai.log.aliyuncs.com/logstores/ipa-azurjxv6mz9tpgxxfxuhfn-raw/shards/lb` — 4512 B，前 60: `8nkKyhoI66Hg1wYSGQoEbmFtZRIRbmV0d29ya19kaWFnbm9zaXMSDgoEa2lu`
- 15:42:36.783 `app.adjust.cn/event` — 1152 B，前 60: `country=CN&ff_coppa=1&api_level=37&hardware_name=PLR110_17.0`
- 15:42:37.011 `yostar-cn-client-logging.cn-shanghai.log.aliyuncs.com/logstores/yostar-cn-client-logging/shards/lb` — 12072 B，前 60: `9FwKmQ0I7KHg1wYS1AwKA21zZxLMDFtBaXJpU0RLXVsxLjE2LjFdWzE5NTU3`
- 15:42:39.068 `yostar-cn-client-logging.cn-shanghai.log.aliyuncs.com/logstores/yostar-cn-client-logging/shards/lb` — 8168 B，前 60: `/lQK2QEI7qHg1wYSiwEKA21zZxKDAVtBaXJpU0RLXVsxLjE2LjFdWzE5NTU3`
- 15:42:40.627 `yostar-cn-netsdk-logging.cn-shanghai.log.aliyuncs.com/logstores/ipa-azurjxv6mz9tpgxxfxuhfn-raw/shards/lb` — 3848 B，前 60: `8nkKyxQI8KHg1wYSGQoEbmFtZRIRbmV0d29ya19kaWFnbm9zaXMSDgoEa2lu`

### 7) 与「服务端应有 2 条」对账

| 项 | HAR 实际 | 服务端应有 | 差 |
|---|---|---|---|
| 目标域请求总数 | 7 | ? | - |
| 目标域 POST 数 | **0** | 2 | **-2** |

目标域 POST 明细：

| # | 时间 | 方法 | 主机 | path | 状态 | 请求字节 | 响应字节 |
|---|---|---|---|---|---|---|---|


**不一致：HAR 目标域 POST = 0，服务端应有 = 2。**
