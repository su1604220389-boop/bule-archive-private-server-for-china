# 国服 3.0.2 资源下载（CDN）地址溯源 —— 静态分析 + 本地取证

> 工作目录：`work\ba\noroot\`
> 日期：2026-11-17
> 原料：`report\_tmp\cn_base.apk`（2,126,400,085 B，sha256 `dd30a285b58508252df09a503b025850a27a73c89f1162454bee55a60d7f83bb`，**只读，未修改**）
> 抓包：`report\_tmp\official201.har`（1,969,336 B，sha256 `e4cabb5840b30341d0470765433f90e47bd383eba49e3e2c5a701919a92b65fd`）
> 约束遵守：**未连任何服务器，未改 APK，未触碰 `build_noroot_apk.py`**
> 本轮新增脚本（全部只读）：`_cdn_scan_apk.py` `_cdn_scan_aa.py` `_cdn_scan_catalog_ctx.py` `_cdn_scan_meta.py` `_cdn_ctx.py` `_cdn_xor256.py` `_cdn_fullapk.py` `_cdn_har_cross.py`

---

## 0. 一句话结论

| 问题 | 答案 | 强度 |
|---|---|---|
| 资源 CDN 地址是否静态写在 APK 里 | **否。全 APK 2,461.9 MB 里 `prodm39` 0 命中；`AddressablesCatalogUrlRoots` 只作为"字段名"存在于 metadata。** | **实测**（全包穷举） |
| 那它从哪来 | **`/api/state` 第二跳的应答**（`ServerInfoConnectionGroupData.AddressablesCatalogUrlRoots`，3 条） | **实测 + 静态确证** |
| 客户端拿它干什么 | 填进 `assets/aa/catalog.json` 的 24,131 处占位符 `{PlatformUtils.AddressableLoadPath}`，拼成真正的 `.bundle` URL | **静态确证** |
| 只改 `ServerInfoDataUrl` 会不会破坏官方 CDN 下载 | **不会破坏机制，但必须由你的服务端把官方那 3 条 root + 4 个版本号原样回吐。** 否则客户端不是"改用别的 CDN"，而是**根本没有 CDN 可用** | **静态确证 + 推断** |
| 会不会因版本号不匹配卡住 | **会，这是最可能的卡点。** 版本号是 URL 路径段而非"声明"，写错 = 404。且版本号**每天在变**（两次抓包相差 14 天，`ResourceVersion` 已从 `202610221737` 变为 `202611051844`） | **实测** |
| `ResUrl` 请求字段的语义 | **客户端上报"我当前正在用的 CDN 根"，是 output 不是 input。值 == `AddressablesCatalogUrlRoots[0]` 字面量等同** | 字段归属**静态确证** / 值**实测** / 用途**推断** |
| `files/LocalizeConfig.txt` 的 `ResUrls` 算不算第二个来源 | **算"次载体"，但它是运行期写入的**（真机实测值就是官方那 3 条）。全新安装时该文件不存在 ⇒ **首启必然从 state 取** | 真机**实测**（转引）/ 覆盖 vs 缓存**未判定** |

---

## 1. 资源 CDN 地址的确切来源

### 1.1 结论：**协议下发（`/api/state` 第二跳）**，不是静态配置

完整链条如下，每一环都有独立证据：

```
①  APK 静态：assets/bin/Data/e37c46fea17834108a4756797197d05a  (GameMainConfig, 5212 B)
      └─ ServerInfoDataUrl = ["https://state-api.bluearchive-cn.com/api/state",
                             "https://stateqc-api.bluearchive-cn.com/api/state"]
                    │
                    ▼  ServerInfoDataRepository.GetConfig → get_StateServerUrl → DownloadServerInfoDataHttp2
②  实测 04:30:45.180  GET https://state-api.bluearchive-cn.com/api/state   → 131 B
      └─ {"Servers":["https://gsqc-api.bluearchive-cn.com/api/",
                     "https://gs-api.bluearchive-cn.com/api/"], "State":1, "Msg":"..."}
                    │
                    ▼  StateServerResponse.Servers → GetApiServerInfo（迭代器，逐个探活）
③  实测 04:30:45.398  GET https://gsqc-api.bluearchive-cn.com/api/state   → 676 B
      └─ ServerInfoConnectionGroupData：
         AddressablesCatalogUrlRoots = ["https://static.bluearchive-cn.com/prodm39",
                                        "https://static-qc.bluearchive-cn.com/prodm39",
                                        "https://static-hs.bluearchive-cn.com/prodm39"]
         ResourceVersion = 202611051844   TableVersion = 202611051826
         MediaVersion    = 202611051836   PatchVersion = 202609291539
                    │
                    ▼  InitResPaths / GetAssetBundlesUrlRoot / GetTableManifestUrlRoot ...
④  实测 04:30:45.979 ~ 04:30:47.118  直接按 root + 版本号拼路径去 static 拉清单（见 §2.3）
                    │
                    ▼  运行期赋值 → PlatformUtils.AddressableLoadPath
⑤  静态确证：assets/aa/catalog.json 内 24,131 处 {PlatformUtils.AddressableLoadPath}/<x>.bundle
      └─ 占位符被 ④ 的值替换后，才是真正下载资源的 URL
```

### 1.2 逐环证据

| 环节 | 证据 | 形式 | 强度 |
|---|---|---|---|
| ① `ServerInfoDataUrl` 在 GameMainConfig | `_extract_cn\CN_GameMainConfig_plain.json`；密文条目 `0x1019..0x145B` | 文件 | **静态确证**（前一轮已完成，本轮复核一致） |
| ①→② 的方法名 | `global-metadata.dat` 明文字符串区（key=0x00）：`ServerInfoDataRepository` / `get_StateServerUrl` / `DownloadServerInfoDataHttp2` / `StateServerResponse` / `Servers` / `GetApiServerInfo` / `GetGameServerInfo` | 见 §1.3 偏移表 | **静态确证** |
| ② 实测应答 | `report\_tmp\official_decoded_201\10_state-api_state.json` — 131 B，`{"Servers":[...],"State":1,"Msg":"..."}` | HAR 解码 | **实测** |
| ③ 实测应答 | `report\_tmp\official_decoded_201\11_gsqc-api_state.json` — 676 B，含 3 条 root + 4 版本 | HAR 解码 | **实测** |
| ③ 的 DTO 结构 | metadata `ServerInfoConnectionGroupData` 字段全表，见 §1.3 | 字符串区 | **静态确证** |
| ③→④ 的拼路径逻辑 | metadata：`InitResPaths` / `GetAssetBundlesUrlRoot` / `GetTableUrlRoot` / `GetMediaUrlRoot` / `GetMediaManifestUrlRoot` / `GetMediaManifestHashUrlRoot` / `GetTableManifestUrlRoot` / `GetRuntimePlatform` / `GetRemotePatchHashFiles` | 见 §1.3 | **静态确证**（方法名）+ **实测**（§2.3 的 5 条 URL 与 4 个版本号 1:1 对上） |
| ④→⑤ 的桥 | `assets/aa/catalog.json` 24,131 处 `{PlatformUtils.AddressableLoadPath}`，**0 个 URL 字面量** | 见 §1.4 | **静态确证** |
| ⑤ 属性存在 | metadata 0x1538e6（key=0x66）：`...CurrentPlatformService.PlatformUtils.AddressableLoadPath.LocalCatalogLoadPath...` | 见 §1.3 | **静态确证** |
| 反证：APK 里没有 | `prodm39` 全 APK **0 命中**（41,312 条目 / 2,461.9 MB 全流式扫过）；`static-qc` / `static-hs` 也 0 | `_cdn_fullapk.py` | **实测（强·穷举）** |

### 1.3 关键偏移表（`assets/bin/Data/Managed/Metadata/global-metadata.dat`，38,426,024 B）

> 字符串堆里有两种存放形态：**key=0x00 明文区** 与 **key=0x66 区**（与 `report\52` 记载的 header XOR 0x66 同 key）。
> `stringLiteralData` 区段则是**逐条字面量各自一个单字节 key**（`report\52` §5 已确证），所以本报告对关键串额外做了 ×256 全 key 扫描（§1.5）。

| 字符串 | 偏移 | key | 说明 |
|---|---|---|---|
| `...d__19.ServerInfoConnectionGroupData.get_AddressablesCatalogUrlRoot.set_...` | `0x00129d73` | 0x00 | `ServerInfoConnectionGroupData` 后面的属性名块 |
| `get_AddressablesCatalogUrlRoots` / `set_AddressablesCatalogUrlRoots` | `0x00129d93`+ | 0x00 | 复数版本 |
| `<AddressablesCatalogUrlRoots>k__BackingField` | `0x0012a2b6`+ | 0x00 | 自动属性后备字段 |
| `...<CDNLineCount>k__BackingField.callbackUrlData.apiIndex...` | `0x0012a5f4` | 0x00 | **完整字段名列表**（见下） |
| `AssetBundlesUrlRoots` | `0x00129ec0` / `0x0012a3cc` / `0x0012a66c` | 0x00 | |
| `PatchCatalogUrlRoots` | `0x0012a0ea` / `0x0012a57d` / `0x0012a751` | 0x00 | |
| `CDNLineCount` | `0x0012a11c` / `0x0012a5a3` / `0x0012a766` | 0x00 | |
| `TableManifestHash` | `0x0012a066` / `0x0012a514` | 0x00 | |
| `MediaManifestHash` | `0x00129ff6` / `0x0012a220` | 0x00 | |
| **`PlatformUtils.AddressableLoadPath`** | **`0x001538e6`** | **0x66** | ★ 占位符的解析目标 |
| `PlatformUtils.LocalCatalogLoadPath` | `0x001538f4` | 0x66 | 本地 catalog 路径 |
| `get_ResUrl` / `set_ResUrl` | `0x0022ac8e` / `0x0022ac99` | 0x00 | 位于 `AccountAuthRequest`（类名 `0x0022ab1b`）内 |
| `<ResUrl>k__BackingField` | `0x0022adf6` | 0x00 | 同上 |

**`ServerInfoConnectionGroupData` 完整字段表**（`0x12a5f4` 附近，key=0x00，原样摘录）：

```
AddressablesCatalogUrlRoot      AddressablesCatalogUrlRoots    ApiUrls      ApiUrl
CallbackUrl                     Msg                            ResourceVersion
TableVersion                    MediaVersion                   PatchVersion
IsOpenPreDownload               AssetBundlesUrlRoots           BundlesCatalogUrls
BundlesHashUrls                 AddressCatalogUrls             AddressHashUrls
MediaUrlRoots                   MediaManifestUrlRoots          MediaManifestHashUrlRoots
TableManifestUrlRoots           TableManifestHashUrlRoots      TableUrlRoots
PatchUrlRoots                   PatchCatalogUrlRoots           CDNLineCount
MediaManifestFileName           MediaManifestHashFileName
TableManifestFileName           TableManifestHashFileName
```

**说明**：这些 `*UrlRoots` 是 DTO 的**可选派生字段**；实测官方应答只给了 `AddressablesCatalogUrlRoots` + 4 个版本号，其余为 null，由 `InitResPaths` 本地推导。这与 `report\31` §二「真实结构只有这 10 个字段」一致。

### 1.4 `assets/aa/catalog.json` —— 地址的真正"接线板"

| 项 | 值 |
|---|---|
| 条目 | `assets/aa/catalog.json`，**81,313,204 B** |
| 内容 | Unity Addressables 内置 catalog（JSON） |
| URL 字面量 | **0 个**（`https?://` 正则 0 命中） |
| `{PlatformUtils.AddressableLoadPath}` 出现次数 | **24,131** |
| 首次出现偏移 | `0x000006c9` |

首次出现的原文（`0x6c9`，原样）：

```json
{PlatformUtils.AddressableLoadPath}/academy-_mxload-prefabs-2026-06-04_assets_all_2136914256.bundle
```

**这就是"资源 URL 从哪来"的最终落点**：catalog 里每个远程 bundle 的 internalId 都是 `{PlatformUtils.AddressableLoadPath}/<name>.bundle`，运行期把占位符替换成 state 下发的 root 派生值。

配套 `assets/aa/settings.json`（3,161 B）显示 catalog 被放在 `{UnityEngine.Application.persistentDataPath}/catalog_Remote.hash|json`，`m_DisableCatalogUpdateOnStart: true`、`m_maxConcurrentWebRequests: 500` —— **远程 catalog 是运行期下载到持久化目录的**，本地不预置远端地址。

### 1.5 反向排除：×256 单字节 XOR 全扫

因为 `report\52` 已证 `stringLiteralData` 是**逐条字面量各自一个单字节 key**，单一的"明文 / XOR 0x20"搜索会漏。故对 metadata 做 **key=0..255 全扫**：

| 字符串 | 结果 |
|---|---|
| `prodm39` | **0 命中**（×256 全 key） |
| `static.bluearchive-cn.com` | **0 命中** |
| `bluearchive` | 1 命中：`0x000d3e2d` key=0xb9 → `https://bluearchive.jp/help?data=`（**日服帮助页，与国服资源无关**） |
| `PlatformUtils` | 1 命中：`0x001538e6` key=0x66 |
| `AddressableLoadPath` | 1 命中：`0x001538f4` key=0x66 |

作为方法有效性对照：`https://` 在 metadata 明文区 90 命中、`/api/` 28 命中 ⇒ 该扫法对"确实存在的字面量"能正常命中，0 命中有意义。

### 1.6 唯一一处 `static.bluearchive-cn.com` 硬编码 —— **不是资源地址**

全 APK 穷举发现 `static.bluearchive-cn.com` 仅 2 个载体，且**都只是健康检查**：

| 载体 | 偏移/位置 | 内容 |
|---|---|---|
| `assets/SDKConfigSettings.json`（2,840 B） | 键 `ali.internet_detection.auto_url.http` / `.mtr`，字节偏移 `5112` / `5316` | `https://static.bluearchive-cn.com/checkhealth.html` |
| `assets/bin/Data/129346de773e72d2ec581682f32d43da`（6,964 B） | 同一 JSON 的 Unity 序列化副本（`SDKConfigSettings` MonoBehaviour，字符串起始 4,126） | 同上 |

这解释了抓包里一个容易误读的现象：`static.bluearchive-cn.com/checkhealth.html` 出现在 **04:30:42.949**，比 `/api/state`（04:30:45.180）**早 2.2 秒**。

> **不是硬编码 CDN 回退**，而是 SDK 网络探测（`internet_detection`）在启动时对配置里的 URL 做连通性探测。它指向 `/checkhealth.html`，**不具备任何资源下载语义，也不含 `prodm39` 路径段**。
> ⚠️ 这一条很容易被误判为"APK 里硬编码了 CDN"。**不成立**：同一域名下 `prodm39` 这个路径段在 APK 内 0 命中，而资源 URL 的真实前缀必须是 `.../prodm39`。

### 1.7 次载体：`files/LocalizeConfig.txt` 的 `ResUrls`（运行期写入）

除了 state 应答，还有一个**本地文件**参与：`{persistentDataPath}/files/LocalizeConfig.txt`（即 `/data/data/<pkg>/files/LocalizeConfig.txt`）。

| 项 | 内容 | 强度 |
|---|---|---|
| 文件名来源 | 字面量 `/LocalizeConfig.txt` @ `0x000393F1` key `0x8B`（`report\54` §2 L1，本轮一致） | **静态确证** |
| 文件格式 | `key=value` 逐行、`;` 分隔多值、无引号、无 section，共 3 行 | **真机实测**（`report\54` §7.1） |
| 三行内容 | `Env=dev` / `IsLocalize=false` / `ResUrls=https://static.bluearchive-cn.com/prodm39;https://static-qc.bluearchive-cn.com/prodm39;https://static-hs.bluearchive-cn.com/prodm39` | **真机实测**（`report\21:1118`、`report\54:259`） |
| 写入时机 | 冷启动读；**文件不存在则用内置模板写一份**（模板只到 `ResUrls=`，值为空）；**之后整个生命周期不重写**（真机 mtime 自 2026-11-13 08:53 未变） | **实测**（`report\54` §4.3 证据 3） |
| 二进制里有没有这个值 | **没有**。模板只写到 `ResUrls=` 为止，三条 URL 在 APK 内 0 命中（与 §1.6 的全包穷举一致） | **静态确证** |

**它与 state 的关系：两种模型，目前未判定**（这是 `report\54` §4.3 明确保留的歧义，本报告不擅自裁决）：

- **模型 A（覆盖）**：`ResUrls` 非空 → **覆盖** `/api/state` 的 `AddressablesCatalogUrlRoots`。
- **模型 B（缓存）**：`ResUrls` 只是把 state 回合的值落盘留档，下载根始终以 state 为准。

两种模型在**既有样本上不可区分**，因为两边的值**逐字符相同**（都是官方那 3 条）。判定需要 `report\54` §11.2 的那个单变量实验（把 `ResUrls` 第 1 条改成自己的 http 地址，看 CDN 是否被引走）。

**但对"免 root、装上即用"这个目标，两种模型给出的结论一致**：

> **全新安装时 `files/LocalizeConfig.txt` 根本不存在** ⇒ 客户端先写一份 `ResUrls=` 为空白的默认文件
> ⇒ **首次启动必然要从 `/api/state` 取 root**。所以 **state 应答必须是权威且正确的来源**，这一点与模型 A/B 无关。

---

## 2. 找到的全部 CDN / 资源相关 URL 字面量（原样）

### 2.1 APK 静态配置内（原样）

`assets/SDKConfigSettings.json`：

```
https://sdk-api.yostar.cn
https://static.bluearchive-cn.com/checkhealth.html
https://gs-api.bluearchive-cn.com/api/health
https://customer.yostar.net/
https://www.baidu.com
https://api.weibo.com/oauth2/default.html
https://cn-shanghai.log.aliyuncs.com
applinks:static.bluearchive-cn.com
```

`assets/bin/Data/e37c46fea17834108a4756797197d05a`（GameMainConfig，解密后）：

```
https://state-api.bluearchive-cn.com/api/state
https://stateqc-api.bluearchive-cn.com/api/state
```

> APK 内**没有任何** `prodm39` 字面量，也没有 `static-qc` / `static-hs` 两个域名。

### 2.2 抓包内（`gsqc-api /api/state` 应答，676 B，原样）

```
https://static.bluearchive-cn.com/prodm39
https://static-qc.bluearchive-cn.com/prodm39
https://static-hs.bluearchive-cn.com/prodm39
http://gs-inter.bluearchive-cn.com:4000/api/order/notify
http://gs-inter.bluearchive-cn.com:4000
http://gs-inter.bluearchive-cn.com:4000/api/web/notify
http://gs-inter.bluearchive-cn.com:4000/api/account/logout
```

`state-api /api/state` 应答（131 B，原样）：

```
https://gsqc-api.bluearchive-cn.com/api/
https://gs-api.bluearchive-cn.com/api/
```

抓包其他相关主机：`notice.bluearchive-cn.com/static/event/694ad7600be7531d7fde26291629fad2.html`、`webcnstatic.yostar.net`、`sdk-api.yostar.cn`、`customer.yostar.net`。

### 2.3 实测的资源请求（这是 CDN 地址被使用的现场，**4 个版本号 1:1 对上**）

| # | 完整 URL | 使用的版本字段 |
|---|---|---|
| 1 | `https://static.bluearchive-cn.com/prodm39/Manifest/Patch/202609291539/patch_assetmanifest` | **PatchVersion** = `202609291539` |
| 2 | `https://static.bluearchive-cn.com/prodm39/Manifest/TableBundles/202611051826/TableManifestHash` | **TableVersion** = `202611051826` |
| 3 | `https://static.bluearchive-cn.com/prodm39/Manifest/MediaResources/202611051836/MediaManifestHash` | **MediaVersion** = `202611051836` |
| 4 | `https://static.bluearchive-cn.com/prodm39/AssetBundles/Catalog/202611051844/Android/bundleDownloadInfo.hash` | **ResourceVersion** = `202611051844` |
| 5 | `https://static.bluearchive-cn.com/prodm39/AssetBundles/Catalog/202611051844/Android/catalog_Android.hash` | **ResourceVersion** + `GetRuntimePlatform`→`Android` |

时间线（北京时间，全部在 `Account_Auth` 之前）：

```
04:30:45.398  GET gsqc-api/api/state          → 676 B（拿到 root + 4 版本）
04:30:45.979  GET static.../Patch/202609291539/patch_assetmanifest              200/78 B
04:30:46.059  GET static.../TableBundles/202611051826/TableManifestHash          200/10 B
04:30:46.207  GET static.../MediaResources/202611051836/MediaManifestHash        200/11 B
04:30:46.929  GET static.../Catalog/202611051844/Android/bundleDownloadInfo.hash  200/9 B
04:30:47.118  GET static.../Catalog/202611051844/Android/catalog_Android.hash     200/32 B
04:30:54.662  POST gsqc-api/api/account/auth  （才第一次带 Token / ResUrl）
```

> **副产品**：`report\31` §五曾用 40+ 条猜测路径找 `catalog_Remote.json` 全部 404。真相是——真实 catalog 路径形态是
> `/prodm39/AssetBundles/Catalog/{ResourceVersion}/Android/catalog_Android.hash`，
> **带 ResourceVersion 目录段**，这就是为什么之前那些不带版本段的猜测全 404。

---

## 3. `ResUrl` 请求字段的语义

### 3.1 字段归属（静态确证）

`ResUrl` 是 **`AccountAuthRequest`** 的自动属性，不是应答字段：

- 类名 `AccountAuthRequest` @ `0x0022ab1b`
- `get_ResUrl` @ `0x0022ac8e`、`set_ResUrl` @ `0x0022ac99`、`<ResUrl>k__BackingField` @ `0x0022adf6`
- 紧邻字段：`Version` / `OSType` / `OSVersion` / `DeviceUniqueId` / `DeviceModel` / `DeviceSystemMemorySize` / `SubChannel`
- 下一个类型是 `AccountAuthResponse` @ `0x0022ae81`（其字段为 `CurrentVersion` / `MinimumVersion` / `AccountDB` / …，**不含 `ResUrl`**）

⇒ `ResUrl` **只出现在客户端发出的请求里**，服务端不会回吐它。

### 3.2 实测值（唯一实例）

`report\_tmp\official_decoded_201\00_1002_api_account_auth.request.json`（明文已解）：

```json
{"Protocol":1002,...,"SdkPid":"CN-BA","SubChannel":"",
 "ResUrl":"https://static.bluearchive-cn.com/prodm39","Hash":4303557230593}
```

### 3.3 语义判定

| 观察 | 事实 | 强度 |
|---|---|---|
| 值的字面量 | `https://static.bluearchive-cn.com/prodm39` | **实测** |
| 与 state 应答比对 | **完全等同 `AddressablesCatalogUrlRoots[0]`**（三条 root 的第 0 条，一字不差） | **实测** |
| 与 §2.3 实际下载主机比对 | 5 条资源请求全部落在 `static.bluearchive-cn.com`（即第 0 条线路） | **实测** |
| 时序 | `ResUrl` 在 `04:30:54.662` 发出；资源清单在 `04:30:45.979~47.118` 已拉完，**早 7.5 秒** | **实测** |
| 方向 | 位于 request DTO ⇒ 客户端→服务端 | **静态确证** |

**结论（语义）**：`ResUrl` = **客户端向上报"本轮实际选用的 CDN 线路根"**，用于服务端侧统计/灰度/排障。
它是 **output 快照，不是 input 指令**——客户端不会读回自己发的这个字段来决定下载地址，因此**改它不影响行为**（只能观测）。

> ⚠️ **`ResUrl`（单数）与 `ResUrls`（复数）是两个完全不同的东西，不要混用：**
>
> | | `ResUrl`（单数） | `ResUrls`（复数） |
> |---|---|---|
> | 归属 | 协议 **1002 `AccountAuthRequest`** 的字段 | `files/LocalizeConfig.txt` 的**文本 key** |
> | 方向 | 客户端 → 服务端（请求体） | 本地文件读写（不在协议里） |
> | 形态 | 单个 URL | `;` 分隔的 URL 列表（对应 3 条 CDN 线） |
> | 偏移 | `get_/set_ResUrl` @ `0x0022ac8e`/`0x0022ac99` | 字面量 `ResUrls` @ `0x00091F1F`（key `0x83`）、`ResUrls=` @ `0x00091F26`（key `0xBA`） |
> | 本报告结论 | **上报值，不决定下载** | **次载体，见 §1.7** |
>
> 复数 `ResUrls` 的两条字面量，本轮 ×256 全 key 扫**独立复现出了与 `report\54` §2（L4/L5）完全相同的偏移与 key**（互为交叉验证）。
> 本报告最初只做了 5 种编码（明文 / XOR 0x20 / UTF-16LE / UTF-16BE / UTF-16LE^0x20）扫描，据此曾误判"复数不存在"；
> 后来按 `report\52` 的方法补做 ×256 全 key 扫描才发现是自己方法不全。**凡"不存在"类结论必须用 ×256 全扫**，这是本轮的教训。

### 3.4 线路选择提示

`ServerInfoConnectionGroupData` 里有 `CDNLineCount` 与 `apiIndex`（`0x12a5f4` 附近）。
实测两条链路都取了 **index 0**：`Servers[0]` = `gsqc-api`，`AddressablesCatalogUrlRoots[0]` = `static`（非 `-qc`/`-hs`）。
二者同为 0，**疑似同一个"线路索引"同时决定网关与 CDN 线路** —— 但**未确认**（见 §5）。

---

## 4. 结论

### 4.1 只改 `ServerInfoDataUrl`、不动其它，客户端还会从官方 CDN 下资源吗？

**会 —— 但前提是你服务端把官方那份 root 清单原样回吐。**

理由（本轮已闭合）：资源 CDN 地址**根本不经过 APK**，它 100% 来自 `/api/state` 第二跳的
`AddressablesCatalogUrlRoots`。所以：

- ✅ **改 `ServerInfoDataUrl` 本身不会破坏 CDN 下载**——APK 里没有"资源 CDN 地址"这个东西可被破坏。
- ⚠️ **但它会把"CDN 地址由谁决定"整个移交给你的服务端。** 这不是"继续用官方 CDN"的自动保证，而是"你必须主动把官方 CDN 地址填回去"。
  如果你回 `null` / 空数组（`report\22` 记录过你们确实回过 `"AddressablesCatalogUrlRoots":null`），
  客户端拿不到任何下载源 —— 不是"换了个 CDN"，而是**资源系统直接没有根地址**。

**最小必要应答（原样照抄官方即可，字段顺序无关）：**

```json
{
  "AddressablesCatalogUrlRoots": [
    "https://static.bluearchive-cn.com/prodm39",
    "https://static-qc.bluearchive-cn.com/prodm39",
    "https://static-hs.bluearchive-cn.com/prodm39"
  ],
  "ResourceVersion": "202611051844",
  "TableVersion": "202611051826",
  "MediaVersion": "202611051836",
  "PatchVersion": "202609291539",
  "State": 0,
  "Msg": "",
  "IsOpenPreDownload": true
}
```

（`State` 取 0 据 `report\24` §4.3「State:1=维护中、State:0=正常」；本条为本报告**转引既有结论**，未在本轮重测。）

**追加一条（§1.7 的推论）**：你交付的是"免 root、装上即用"的 APK，**目标机是全新安装**。
全新安装时 `files/LocalizeConfig.txt` 不存在 → 客户端写默认模板（`ResUrls=` 空）→ **首次启动唯一能拿到 CDN 根的路径就是你的 `/api/state`**。
所以"把官方 root 填进 state"不是可选项，而是**必做项**；§1.7 里"覆盖 vs 缓存"那个未判定歧义，在首启场景下不构成风险。

### 4.2 会不会因为版本号不匹配而卡住？

**会。这是最现实的卡点，而且比"CDN 地址"更容易翻车。**

三点实测依据：

1. **版本号是 URL 路径段，不是"声明"。** §2.3 五条 URL 里 4 个版本号各自占一个目录段。填错 = 该 URL 404 = 清单拉不到 = 资源更新中断。**不存在"版本号不符就自动降级/自动纠正"的机制**（客户端从 APK 里拿不到任何替代版本号，见 §1.5：`prodm39` 0 命中，本地也没有版本号字面量）。
2. **版本号是动态的，不能写死。** 同一客户端（同一份 APK）在不同日期的抓包里：

   | 抓包 | ResourceVersion | TableVersion | MediaVersion | PatchVersion |
   |---|---|---|---|---|
   | `reqable_udata.har` | `202610221737` | `202610292033` | `202610221638` | `202609291539` |
   | `official201.har` / `baba.har` / `new0416.har` / `最全的一个.har` | `202611051844` | `202611051826` | `202611051836` | `202609291539` |

   ⇒ `Resource/Table/Media` 三个版本 14 天内全部变化，`PatchVersion` 未变。**硬编码任何一份快照都会在官方下一次热更后失效。**
3. **与 APK 版本号无关。** `GameMainConfig.VersionCode = "73"`（= versionCode 73）是**应用版本**，与 `ResourceVersion` 是两个体系；客户端不会拿 73 去校验资源版本。且资源清单拉取发生在 `Account_Auth` **之前 7.5 秒**，此时连 Token 都还没有 ⇒ **资源链路完全独立于登录/鉴权，也独立于 `ServerInfoDataUrl` 之外的任何 APK 改动**。

**运维含义**：你的 `/api/state` 必须**定期（建议每次官方热更后）从官方刷新这 4 个版本号 + 3 条 root**，不能冻结在 2026-11-05 这一份快照上。

### 4.3 实施时必须注意的一个结构性问题（两跳同 URL）

因为 `ServerInfoDataUrl` 被改成 `https://example.com/api/state`，而第一跳应答里的 `Servers` 若也指向你自己的域名（形如 `https://example.com/api/`），
则第二跳会被拼成 `Servers[i] + "state"` = **`https://example.com/api/state`** —— **与第一跳完全同一个 URL**。

- 官方是靠**两个不同 Host**（`state-api` vs `gsqc-api`）区分两个 DTO 的（`report\24` §6 已指出必须按 Host 拆两个 DTO）。
- 你把它合并到一个域名后，**按 Host 拆分的方法失效**。
- 可选解法（按推荐度）：
  1. **回一份"超集"JSON**：同时含 `Servers`（DTO B 要的）与 `AddressablesCatalogUrlRoots` + 4 版本（DTO A 要的）。两跳各取所需，多余字段被忽略。← 改动最小
  2. 保留 `Servers` 指向**两个不同 path** 的自有端点，让第二跳落在另一个路径上（例如 `Servers: ["https://example.com/api/gw/"]`），按路径拆 DTO。
  3. 若确实想让第二跳直接落到官方（资源绝对安全、版本永远最新），就把 `Servers` 填官方 gsqc/gs-api —— 但那也意味着**所有游戏协议都走官方**，与私服目标冲突。

> 本小节 4.3 的第 1 条（超集 JSON 会被两跳各自正确解析）为 **推断**：依据是 field-based 反序列化通常忽略未知字段。
> 未做运行时验证（本轮禁止连服务器）。

### 4.4 不受影响的项（可以放心）

| 项 | 结论 | 强度 |
|---|---|---|
| `static.bluearchive-cn.com/checkhealth.html` 连通性探测 | 硬编码在 `SDKConfigSettings.json`，**不经过 state**，改 `ServerInfoDataUrl` 不影响它 | **静态确证** |
| 资源下载是否需要登录/Token | **不需要**。5 条清单请求全部发生在 `Account_Auth` 之前，请求头无 Token | **实测** |
| 本地 `assets/aa/catalog.json` | 内置，只含占位符，无 URL；不会被 state 改动破坏 | **静态确证** |
| `assets/SDKConfigSettings.json` 的 `sdk_url` | 卡密/SDK 入口，与资源无关 | **静态确证** |

---

## 5. 未确认清单

| # | 项 | 现状 | 为什么没定 |
|---|---|---|---|
| U1 | `PlatformUtils.AddressableLoadPath` 的**精确拼接式** | **推断**为 `{AddressablesCatalogUrlRoots[i]}/AssetBundles/Android` | catalog 里占位符后直接接 `/<name>.bundle`，没有 `AssetBundles` 段；`report\31:254` 也推断 bundle 在 `{root}/AssetBundles/Android/<file>`。本次抓包**没有任何 `.bundle` 请求**（资源已是最新，只拉了 hash），无法实测佐证 |
| U2 | `CDNLineCount` / `apiIndex` 是否就是"线路索引"，是否同时决定网关与 CDN 线路 | **未确认** | 两条链路实测都取 index 0，样本不足以区分"同一索引"与"两个独立索引" |
| U3 | `AddressablesCatalogUrlRoot`（**单数**）与 `ResUrl` 的关系 | **推断**：`InitResPaths` 把 `Roots[0]` 赋给单数字段，`ResUrl` 上报它 | 值完全相等，但看不到赋值代码；单数字段在实测应答里为 null |
| U4 | `State` 的 0/1/2 精确语义 | **转引** `report\24` §4.3（1=维护，0=正常） | 本轮未重测；且官方在 `State:1`（维护）时**仍下发了完整 root + 版本**，说明资源信息与开服状态解耦 |
| U5 | 第二跳 DTO 是否**必须**补齐 `report\24` 建议的 10 字段（含 `ApiUrls` 等） | **未确认** | 官方 676 B 应答里确实只有 10 个键；但哪些是硬必填、哪些可缺省，需运行时逐字段删测 |
| U6 | ×256 单字节 XOR 的**完备性** | **未确认**：多字节 key / 压缩存储的可能性未排除 | `report\52` 已证 `stringLiteralData` 是逐条单字节 key，但 `stringLiteral` 表本身「未解」（该报告 §7 自述）。所以"0 命中"严格说是"在单字节 XOR 假设下 0 命中" |
| U7 | `GetApiServerInfo` 的 `isLive` 探活是否要求 `Servers` ≥ 2 项 | **未确认** | `report\24` §4.1 记了迭代器 `<i>5__4` / `<isLive>5__3`，但没实测 1 项是否够 |
| U8 | `Assets/aa/catalog.json` 24,131 条与线上实际 bundle 总数是否一致 | **未确认** | 未与 CDN 清单比对（禁止连服务器） |
| U9 | 是否存在**绕过 state** 的第二条资源路径（如本地 `AddressbleAssetInfo.txt` 预置清单） | **未确认** | APK 内 `prodm39` 0 命中，未见本地预置版本号；但 `assets/bin/Data/` 下 565 个条目未逐个人工审阅（仅自动化扫描） |
| U10 | `files/LocalizeConfig.txt` 的 `ResUrls` 是**覆盖** state 的 `AddressablesCatalogUrlRoots`，还是仅**缓存** | **未判定** | 两边值逐字符相同，既有样本不可区分。判定实验见 `report\54` §11.2（把第 1 条改成自己的 `http://` 地址看 CDN 是否被引走）。**对首启场景无影响**（见 §4.1 追加条） |
| U11 | 非全新安装（机器上已有 `LocalizeConfig.txt` 且 `ResUrls` 非空）时，改 `ServerInfoDataUrl` 后客户端用的是缓存值还是 state 值 | **未确认** | 取决于 U10。若为覆盖模型，则旧缓存会**遮蔽**你的 state root —— 但这反而意味着仍走官方 CDN，风险方向是"你的改动不生效"而非"资源挂掉" |

---

## 附录 A：复现命令

```powershell
$py = 'C:\Users\su\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe'
$d  = 'C:\Users\su\Desktop\大肥鱼项目\BAServer'

# 1) assets/ 配置型条目 + URL/关键字
& $py "$d\work\ba\noroot\_cdn_scan_apk.py" "$d\report\_tmp\cn_base.apk"

# 2) Addressables settings / catalog 流式扫（0 个 URL，24,131 个占位符）
& $py "$d\work\ba\noroot\_cdn_scan_aa.py"
& $py "$d\work\ba\noroot\_cdn_scan_catalog_ctx.py"

# 3) metadata / libil2cpp 多编码关键字
& $py "$d\work\ba\noroot\_cdn_scan_meta.py" `
      "assets/bin/Data/Managed/Metadata/global-metadata.dat" `
      "AddressablesCatalogUrlRoots,ResUrl,prodm39,static.bluearchive-cn.com"

# 4) metadata ×256 单字节 XOR 全扫（结论：prodm39 0 命中）
& $py "$d\work\ba\noroot\_cdn_xor256.py" `
      "assets/bin/Data/Managed/Metadata/global-metadata.dat" `
      "prodm39,bluearchive,static.bluearchive-cn.com,PlatformUtils,AddressableLoadPath"

# 4b) 复数 ResUrls / LocalizeConfig 校验（结论：均存在，且与 report\54 §2 偏移一致）
& $py "$d\work\ba\noroot\_cdn_xor256.py" `
      "assets/bin/Data/Managed/Metadata/global-metadata.dat" `
      "ResUrls,LocalizeConfig,IsLocalize"

# 5) 全 APK 2,461.9 MB 穷举（prodm39 = 0 命中）
& $py -u "$d\work\ba\noroot\_cdn_fullapk.py"

# 6) 全部 HAR 交叉核对（6 份 HAR 的 root 三件套一致，版本号有变化）
& $py -u "$d\work\ba\noroot\_cdn_har_cross.py"
```

## 附录 B：本轮产出物

| 文件 | 说明 |
|---|---|
| `_cdn_scan_apk.out.txt` | assets/ 配置条目清单与 URL 命中 |
| `_cdn_scan_aa.out.txt` | `aa/settings.json` 全字符串 + `aa/catalog.json` 扫描 |
| `_cdn_scan_catalog_ctx.out.txt` | 占位符 24,131 次 / 首现 0x6c9 / 上下文 |
| `_scan_gmd_*.txt` / `_sanity_il2cpp.txt` / `_scan_il2cpp.txt` | metadata 与 libil2cpp 多编码扫描记录 |
| `_xor256_gmd.txt` | ×256 单字节 XOR 全扫结果（含 §1.5 三条命中上下文） |
| `_xor256_resurls.txt` | 复数 `ResUrls` / `LocalizeConfig` / `IsLocalize` 的 ×256 全扫（§1.7、§3.3） |
| `_ctx_gmd_addressables.txt` / `_ctx_gmd_resurl.txt` / `_ctx_platformutils.txt` / `_ctx_serverinfo.txt` | 关键偏移的字符串上下文原文 |
| `_ctx_129346de.txt` | `static.bluearchive-cn.com` 第二个载体的完整 dump（= SDKConfigSettings 副本） |
| `_cdn_fullapk.out.txt` | 全 APK 穷举结果（终局判据） |
| `_har_cross.out.txt` / `_har_versions.txt` | 6 份 HAR 的 root 与版本号对照 |
