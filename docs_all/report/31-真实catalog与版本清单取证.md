# 31 — 真实 catalog 与版本清单取证

> 取证时间：2026-11-14 02:26–02:33
> 方法：本机 Windows 直连（可出国），无代理。**未登录服务器、未碰手机。**
> 原始证据：`report\evidence\31\`

---

## 一、摘要表

| # | 目标 | 结果 | 关键数据 |
|---|---|---|---|
| **E2** | `gsqc-api/api/state` **带 4 个业务头** | ✅ **200 / 676 B，真实 DTO 拿到** | 见 §二 |
| E1 | `gsqc-api/api/state` 无头（基线） | 200 / 214 B，`"Msg":"platform id error"` | 对照组 |
| **E3** | `state-api/api/state` **带 4 个业务头** | ✅ **200 / 161 B，含 `Servers` + `State:1`** | 见 §三 |
| E4 | `state-api/api/state` 无头（基线） | 200 / **0 字节** | 与 `report/22` 一致 |
| **E16** | `prodm39/AssetBundles/Android/AddressbleAssetInfo.txt` | ✅ **200 / 6,553,315 B** | 见 §四 |
| E13 | `cbt1/AssetBundles/Android/AddressbleAssetInfo.txt` | ✅ 200 / 6,497,332 B | 旧内测资源仍在 |
| E5/E12/E15/E17 | `catalog_Remote.json` 的 40+ 条路径猜测（三条 CDN 线路） | ❌ **全部 404** | 见 §五 |
| E8/E9 | 旧缓存节点桶列表 | ✅ 200 / 408,560 B（1000 条，**只有 `cbt1/`**） | 见 §六 |
| E10/E11 | OSS 桶列表 / CDN `?prefix=` | ❌ 403 `AccessDenied`，`ListBucket` 未开放 | — |
| E19 | `global-metadata.dat` 字符串扫描 | ✅ 见 §七 | `catalog_Remote` **0 命中** |

---

## 二、★ 真实 `gsqc-api/api/state`（676 B，最重要的产出）

### 复现命令
```bash
curl -sS -D- \
  -H 'APP-VER: 3.0.2' \
  -H 'PLATFORM-ID: 1' \
  -H 'CHANNEL-ID: 1' \
  -H 'SERVER-NAME: prod' \
  -H 'User-Agent: UnityPlayer/2021.3.56f2 (UnityWebRequest/1.0, libcurl/8.10.1-DEV)' \
  -H 'Accept: */*' \
  -H 'Accept-Encoding: deflate, gzip' \
  -H 'Content-Type: application/octet-stream' \
  https://gsqc-api.bluearchive-cn.com/api/state
```

### 响应头
```
HTTP/1.1 200 OK
Content-Type: application/json; charset=utf-8
Server: TencentEdgeOne
Content-Length: 676
EO-Cache-Status: MISS
```

### 响应体（676 B，原样，可直接落盘当 DTO）
```json
{"CallbackUrl":"{\"order_notify\":\"http://gs-inter.bluearchive-cn.com:4000/api/order/notify\",\"survey_notify\":\"http://gs-inter.bluearchive-cn.com:4000\",\"web_notify\":\"http://gs-inter.bluearchive-cn.com:4000/api/web/notify\",\"account_logout\":\"http://gs-inter.bluearchive-cn.com:4000/api/account/logout\"}","CustomerServiceUrl":"","AddressablesCatalogUrlRoots":["https://static.bluearchive-cn.com/prodm39","https://static-qc.bluearchive-cn.com/prodm39","https://static-hs.bluearchive-cn.com/prodm39"],"ResourceVersion":"202611051844","TableVersion":"202611051826","MediaVersion":"202611051836","PatchVersion":"202609291539","State":1,"Msg":"","IsOpenPreDownload":true}
```

### 逐字段
| 字段 | 真实值 |
|---|---|
| `CallbackUrl` | **转义后的嵌套 JSON**，4 个键，全部指向 `http://gs-inter.bluearchive-cn.com:4000` |
| `CustomerServiceUrl` | `""` |
| `AddressablesCatalogUrlRoots` | **3 个元素**：`static` / `static-qc` / `static-hs` |
| `ResourceVersion` | **`202611051844`** |
| `TableVersion` | **`202611051826`** |
| `MediaVersion` | **`202611051836`** |
| `PatchVersion` | **`202609291539`** |
| `State` | **`1`** ← 正常态就是 1 |
| `Msg` | `""` |
| `IsOpenPreDownload` | **`true`** |

### 四条会立刻改做法的结论
1. **`State:1` + `Msg:""` 就是正常响应**。`platform id error` 那条是 `State:0`。
2. **真实结构只有这 10 个字段**，没有 `ApiUrls` / `AddressablesCatalogUrlRoot`（单数）/ `AssetBundlesUrlRoots` / `CDNLineCount` / 各种 `*UrlRoots`。
3. **四个版本号不是同一个值**，是四个独立的 `yyyyMMddHHmm` 形态时间戳。
4. **`AddressablesCatalogUrlRoots` 有三个元素**，`static-qc` / `static-hs` 是之前完全不知道的两条线路。

---

## 三、真实 `state-api/api/state`（161 B）

### 无头（E4，基线）
```
HTTP/1.1 200 OK
Server: Tengine
Content-Length: 0        ← 空 body
```

### 带 4 个业务头（E3）
```
HTTP/1.1 200 OK
Server: Tengine
Content-Type: application/json; charset=utf-8
Content-Length: 161
```
```json
{"Servers":["https://gsqc-api.bluearchive-cn.com/api/","https://gs-api.bluearchive-cn.com/api/"],"State":1,"Msg":"服务器维护中，请耐心等待开服！"}
```
（`Msg` 是 UTF-8 中文；PowerShell 控制台按 GBK 显示会变乱码，但**文件里是正确 UTF-8**，见 `E3_body.bin`）

**要点**：`Servers` 两个元素、`/api/` 结尾；`State:1`；`Msg` 是维护文案 → 说明**当前真实服务器处于「维护公告」状态**（`State:1` 时仍带公告文案是允许的）。

---

## 四、★ CDN 目录结构（关键发现）

**目录结构是 `prodm39/AssetBundles/Android/`，catalog 不在其中。**

| 路径 | 结果 |
|---|---|
| `/prodm39/AssetBundles/Android/AddressbleAssetInfo.txt` | ✅ **200 / 6,553,315 B / text/plain** |
| `/prodm39/AssetBundles/Android/catalog_Remote.json` | ❌ 404 |
| `/prodm39/Android/AddressbleAssetInfo.txt` | ❌ 404 |
| `/prodm39/AddressbleAssetInfo.txt` | ❌ 404 |
| `/prodm39/` | ❌ 404 |

### 下载产物
```
report\evidence\31\E16_prodm39_AddressbleAssetInfo.txt
  size   6,553,315 B
  sha256 11A92F580790795F7D3AEC2E97BCC4B05A8616DC4F775B70F69F88DFA778D85F
```

### 清单结构（`MXBundle : <名>` + 逐个资产的 `[路径][hash][address]`）
```
MXBundle : MXContentUpdate
MXBundle : InBuildGroup
MXBundle : Academy-_MXLoad-2023-05-30
MXBundle : Arms-_MXLoad-2023-05-30
MXBundle : Audio-SFX_BackGroundEffect-_MXLoad-2023-05-30
...
```
**共 1646 个 MXBundle。** 清单里**没有 `catalog` 字样**（只有 `LogicEffectData.json` / `SkillVisualEffectData.json` / `ObstacleData.json` 三个 RawData 资产）。

### 桶的真实身份
```xml
<HostId>bluearchive-static.oss-cn-shanghai.aliyuncs.com</HostId>
```
即 OSS 桶 **`bluearchive-static`（上海）**。
- `GetObject`：**允许匿名读**（已知 key 能 200）
- `ListBucket`：**拒绝** → `403 AccessDenied` / `Anonymous user has no right to access this bucket`

---

## 五、`catalog_Remote.json` 没找到（40+ 条路径穷举）

三条 CDN 线路 × 以下形态，全部 404：

```
/prodm39/Android/catalog_Remote.json          /prodm39/android/catalog_Remote.json
/prodm39/Android/catalog_Remote.hash          /prodm39/catalog_Remote.json
/prodm39/catalog_Remote.hash                  /prodm39/StandaloneWindows64/catalog_Remote.json
/prodm39/{RV}/catalog_Remote.json             /prodm39/{RV}/Android/catalog_Remote.json
/prodm39/Android/{RV}/catalog_Remote.json     /prodm39/resource/{RV}/catalog_Remote.json
/prodm39/catalog/{RV}/catalog_Remote.json     /prodm39/AddressablesCatalog.json
/prodm39/version.json                         /prodm39/Android/version.json
/prodm39/Android/settings.json                /prodm39/Android/aa/catalog_Remote.json
/prodm39/Android/Addressables/catalog_Remote.json
/prodm39/AssetBundles/Android/catalog_Remote.json
/prodm39/AssetBundles/Android/catalog_Remote.hash
/prodm39/AssetBundles/catalog_Remote.json
/prodm39/AssetBundles/Android/catalog_Remote.bundle
/prodm39/AssetBundles/Android/AddressablesLink.lnk
/prodm39/AssetBundles/Android/version.txt ...
```
（`{RV}` = `202611051844`）

所有 404 的 body 都是 OSS `NoSuchKey` XML，**说明请求确实打到了桶里、只是 key 不存在**（不是路由问题）。

### 结论：远端可能根本没有 catalog 文件
见 §七 —— 客户端本地那份 **`m_DisableCatalogUpdateOnStart = True`**，三个 catalog 位置全指向 `persistentDataPath`。**远端 catalog 很可能从来不需要下载。**

---

## 六、旧缓存节点与桶列表

| 节点 | 根路径 | 结果 |
|---|---|---|
| `112.15.33.35` | `/` | 200 / 408,560 B XML 桶列表（**CDN 缓存**） |
| `112.16.250.35` | `/` | 同上，字节级相同 |

列表内容：`IsTruncated=true`、`NextMarker=cbt1/AssetBundles/Android/assets-_mx-hexamaps-...`、1000 条，**全部在 `cbt1/` 下**（2022–2023 内测资源），另有 `.well-known/`、`apple/`。

**`?prefix=` 被 CDN 忽略**（返回的 `<Prefix>` 为空）→ 无法用它列 `prodm39/`。

---

## 七、客户端 `assets/aa/settings.json` 分析（3161 B）

```json
"m_buildTarget": "Android",
"m_CatalogLocations": [
  {"m_Keys":["AddressablesMainContentCatalogRemoteHash"], "m_InternalId":"{UnityEngine.Application.persistentDataPath}/catalog_Remote.hash"},
  {"m_Keys":["AddressablesMainContentCatalogCacheHash"],  "m_InternalId":"{UnityEngine.Application.persistentDataPath}/catalog_Remote.hash"},
  {"m_Keys":["AddressablesMainContentCatalog"],           "m_InternalId":"{UnityEngine.Application.persistentDataPath}/catalog_Remote.json"}
],
"m_DisableCatalogUpdateOnStart": true,      ← 启动时不检查远端 catalog 更新
"m_IsLocalCatalogInBundle": false,
"m_AddressablesVersion": "1.19.19",
"m_maxConcurrentWebRequests": 500,
"m_CatalogRequestsTimeout": 0
```

### 三条推论
1. **三处 catalog 全部指向本机 `persistentDataPath`**，没有任何 http URL。
2. **`m_DisableCatalogUpdateOnStart = true`** → 启动时不拉远端 catalog。
3. `assets\aa\` 下**只有 `settings.json` 一个文件**（APK 里没有 catalog 本体）。

⇒ **catalog 是客户端自己生成/写在 `persistentDataPath` 的**，远端只提供 **bundle**。

---

## 八、`global-metadata.dat` 字符串扫描（38,426,024 B）

| 关键串 | 命中 |
|---|---|
| `catalog_Remote` | **0** |
| `catalog_Remote.json` | **0** |
| `prodm39` | **0** |
| `.bundle` | **0** |
| `AssetBundles/Android` | **0** |
| `RemoteLoadPath` | **0** |
| `AssetBundles` | 41（全是 C# 字段/方法名） |
| `GetAssetBundlesUrlRoot` / `GetTableUrlRoot` / `GetMediaUrlRoot` | 各 1 |

**⇒ catalog 文件名与 CDN 路径都不在 C# 里，是 Addressables 运行期拼的。**

### 找到的 URL 构造方法（对应 0x0012A1DE 区）
```
get_MediaManifestFileName  get_MediaManifestHashFileName
get_TableManifestFileName  get_TableManifestHashFileName
apiUrls  ResetApiUrl  InitResPaths  GetRuntimePlatform
GetAssetBundlesUrlRoot  GetTableUrlRoot  GetMediaManifestUrlRoot
GetMediaManifestHashUrlRoot  GetMediaUrlRoot  GetTableManifestUrlRoot
remotePatchHash  GetRemotePatchHashFiles
```
以及 DTO 属性表（0x00129D73 / 0x0012A2B6）：
```
AddressablesCatalogUrlRoot  AddressablesCatalogUrlRoots  ApiUrls  ApiUrl
CallbackUrl  Msg  ResourceVersion  TableVersion  MediaVersion  PatchVersion
IsOpenPreDownload  AssetBundlesUrlRoots  BundlesCatalogUrls  BundlesHashUrls
AddressCatalogUrls  AddressHashUrls  MediaUrlRoots  MediaManifestUrlRoots
MediaManifestHashUrlRoots  TableManifestUrlRoots  TableManifestHashUrlRoots
TableUrlRoots  PatchUrlRoots  PatchCatalogUrlRoots  CDNLineCount
```

**⇒ 那 24 个字段是 C# 类的真实属性，但真实服务器只发其中 10 个。** 客户端对缺失字段会用默认值（`GetAssetBundlesUrlRoot` 等会 fallback 到 `AddressablesCatalogUrlRoots`）。

---

## 九、结论与下一步建议

### 已确定的
1. **DTO A 的正确内容已经拿到**（676 B 原文），可以直接替换我们那份 838 B 的伪造版。**这是第一优先级，可能当场解决弹窗。**
2. `State:1` 是正常态；`Msg:""`。
3. CDN 提供 **bundle**：`{root}/AssetBundles/Android/<file>`，`{root}` 就是 `AddressablesCatalogUrlRoots[i]`。
4. 远端 **不需要** catalog 文件（`m_DisableCatalogUpdateOnStart=true`）。

### 尚未拿到的
- `catalog_Remote.json` / `.hash` 的真实远端位置 —— **很可能不存在于远端**。
- 1646 个 bundle 的**完整文件名（含 hash 后缀）** —— 需要 catalog 或一次真实下载才能枚举。

### 建议的下一步（按性价比）
1. **立刻把 §二的 676 B 原文当作 DTO A 上到服务端**（gsqc-api / gs-api 的 `/api/state`），`state-api` 保持 `State:1`。
2. **把 `static*` 三组域名从 MITM 放回透传**（它们是 `*.bluearchive-cn.com`，现在走我们的 404）。让客户端直连真实 CDN 拿 bundle。
3. 若客户端仍要 catalog，**去手机 `persistentDataPath` 找现成的**：
   ```
   /storage/emulated/0/Android/data/com.RoamingStar.BlueArchive/files/catalog_Remote.json
   /storage/emulated/0/Android/data/com.RoamingStar.BlueArchive/files/catalog_Remote.hash
   ```
   如果存在，那**就是这份客户端版本对应的真实 catalog**，可以直接拿来给私服用。
4. bundle 文件名枚举：等客户端真的开始下载时抓 `ba_static.log` / `sni=static`，从请求 URI 反推。

---

## 九·补 — `gs-api` 与另两条 CDN 线路（追加实测）

### E20：`gs-api.bluearchive-cn.com/api/state` 带同样的头
```
HTTP/1.1 200 OK
Server: Tengine
Content-Type: application/json; charset=utf-8
Content-Length: 676
```
**10 个键，值与 `gsqc-api` 完全相同**：
```
keys: AddressablesCatalogUrlRoots, CallbackUrl, CustomerServiceUrl, IsOpenPreDownload,
      MediaVersion, Msg, PatchVersion, ResourceVersion, State, TableVersion
State=1  Msg=''  RV=202611051844  TV=202611051826
```
⇒ **`gsqc-api` 与 `gs-api` 的 `/api/state` 是同一份内容**，两个域名可以共用同一个 alias 文件。

### E21：三条 CDN 线路都服务同一份清单
```
https://static.bluearchive-cn.com/prodm39/AssetBundles/Android/AddressbleAssetInfo.txt    → 200 / 6,553,315 B
https://static-qc.bluearchive-cn.com/prodm39/AssetBundles/Android/AddressbleAssetInfo.txt → 200 / 6,553,315 B
https://static-hs.bluearchive-cn.com/prodm39/AssetBundles/Android/AddressbleAssetInfo.txt → 200 / 6,553,315 B
```
⇒ 三条线路内容一致（同一 OSS 桶或多活同步），**私服只需代理其中一条**，或三条都透传。

---

## 十、原始证据清单（`report\evidence\31\`）

```
E1_headers_nohdr.txt / E1_body_nohdr.bin      gsqc 无头基线 214 B
E2_headers.txt / E2_body.bin                  ★ gsqc 带头 676 B（核心产出）
E3_headers.txt / E3_body.bin                  ★ state-api 带头 161 B
E4_headers.txt / E4_body.bin                  state-api 无头 0 B
E5_catalog_matrix.txt                         3 线路 × 11 路径矩阵
E6_headers.txt / E6_body.xml                  OSS NoSuchKey 原文（暴露 bucket 名）
E7_*.bin / E8_bucketlist.xml                  旧缓存节点桶列表 408,560 B
E9_prodm39_list.xml                           prefix 被忽略的证据
E10_oss_root.xml / E10_oss_p39.xml            OSS ListBucket 403
E11_*.xml                                      CDN ?prefix= 403
E12/E15/E17_*.txt                              40+ 条 catalog 路径猜测结果
E13_*.txt                                     cbt1 与 prodm39 的 AddressbleAssetInfo.txt
E16_prodm39_AddressbleAssetInfo.txt           ★ prodm39 清单 6,553,315 B
E19_meta_scan.txt                             global-metadata 字符串扫描
scan_meta.py                                  扫描脚本（可复跑）
```
