# 24 — `/api/state` 接口 schema 反推（il2cpp 元数据静态分析）

> 目标：从 `global-metadata.dat` 反推 `/api/state` 应答 DTO 的字段清单 / 类型 / `State` 取值语义，解释「提示框正文空白」
> 方法：纯离线静态分析，只读 `work\ba\` 下文件；中间产物在 `report\_tmp\meta_re\`
> 时间：2026-11-14
> 结论一句话：**`/api/state` 其实有两个不同的 DTO，分别由 `state-api` 和 `gsqc-api`/`gs-api` 返回；我们服务端把两者揉成了一份 6 字段的 JSON，缺了 20+ 个必填字段。这就是空白弹窗的根因方向。**

---

## 〇、结论速览（先看这个）

| # | 结论 | 置信度 | 依据 |
|---|---|---|---|
| **1** | 客户端有**两个**不同的 `/api/state` 应答类：`StateServerResponse`（区服列表，3 字段）与 `ServerInfoConnectionGroupData`（网关配置，**25 字段**） | **高（实测）** | 元数据字段表 + 本工程已有真实抓包原文 |
| **2** | 我们服务端现在回的 6 字段 JSON 是**两个 DTO 的混合体**，且 `ServerInfoConnectionGroupData` 缺了 **19 个以上**字段 | **高（实测）** | 逐字段比对 |
| **3** | `CustomerServiceUrl` **客户端根本不读**（元数据 0 命中） | **高（实测）** | 见 §2.3 |
| **4** | `State: 1` = **维护中**，`State: 0` = **正常**。我们现在用的 `0` 是**对的** | **中高** | 见 §4.3 |
| **5** | 弹窗正文**不是**硬编码中文常量（元数据里没有任何真实中文字面量）→ 它必然是运行时填入的，最可能来自服务端某字段的空值 | **中高** | 见 §5 |
| **6** | `global-metadata.dat` 的**头部被加密**（magic 不是 `0xFAB11BAF`），无法索引区段表；但**字符串区是明文**，按名解析完全可用 | **高（实测）** | 见 §3 |

---

## 一、第 1 步：字段名字面量在 `global-metadata.dat` 里的命中情况

### 1.1 文件与头部

```
file size = 38426024
magic(LE) = 0x12724394        ← 不是标准 il2cpp magic 0xFAB11BAF
```

### 1.2 命中计数

| 字面量 | 命中数 | 位置 |
|---|---|---|
| `AddressablesCatalogUrlRoots` | **4** | 0x0012A2B5 / 0x00129D93 / 0x0012A5F4 / 0x00129D73 |
| `CallbackUrl` | **8** | 0x00129DD6, 0x00129DE6, 0x0012A2FC, 0x001D7172, 0x00230E31 … |
| `Servers` | **1** | 0x0012A92B |
| `Msg` | 56 | 其中 API 相关 0x00129DF6 / 0x0012A319 / 0x0012A61F |
| `State` | 1824 | **全部是 Unity NGUI（`UIButton.State`、`UIPlayTween`、`dualState`…）等无关命中，API 区域 0 命中** |
| `CustomerServiceUrl` | **0** | —— |

### 1.3 背街字段（`k__BackingField`）精确探针

```
<State>k__BackingField                       NOT FOUND
<Servers>k__BackingField                     NOT FOUND
<CustomerServiceUrl>k__BackingField          NOT FOUND
<StateServerUrl>k__BackingField              NOT FOUND
<Msg>k__BackingField                         1 hit : 0x0012A318
<ApiUrls>k__BackingField                     1 hit : 0x0012A2E2
<CallbackUrl>k__BackingField                 1 hit : 0x0012A2FB
<AddressablesCatalogUrlRoots>k__BackingField 1 hit : 0x0012A2B5
```

**关键推论**：il2cpp 的字符串表是**全局去重**的。`State`、`Msg` 这类名字在别处已经出现过，所以不会在 API 区域重新出现——因此「`State` 在 API 区域 0 命中」**不能**推出「客户端不读 `State`」。而 `Servers` 只出现 1 次，正因为它全局唯一。

---

## 二、第 2 步：两组 API 字段簇逐个还原

### 2.1 DTO A — `ServerInfoConnectionGroupData`（网关配置，**25 字段**）

类名出现于 `0x00129D13`，紧跟着就是它的属性声明序列。完整截取（`0x0012998F..0x0012A15F`）：

```
... ManagementDataRepository
    get_Data | set_Data | get_IsAlreadyOpenMaintenanacePopup | set_IsAlreadyOpenMaintenanacePopup
    get_NetTime | set_NetTime | GetActiveGuidePopupDataList | GetActiveSurveyGuidePopupData
    RequestManagementData | _Data | UpdateManagementData | managementDataUrl
    <Data>k__BackingField | <IsAlreadyOpenMaintenanacePopup>k__BackingField | <NetTime>k__BackingField
    <GetActiveGuidePopupDataList>b__0 | ...
    <RequestManagementData>b__0 | <RequestManagementData>d__19
>>  ServerInfoConnectionGroupData
    get_AddressablesCatalogUrlRoot  | set_AddressablesCatalogUrlRoot
    get_AddressablesCatalogUrlRoots | set_AddressablesCatalogUrlRoots
    get_ApiUrls                     | set_ApiUrls
    get_ApiUrl                      |              ← 只有 getter，无 setter
    get_CallbackUrl                 | set_CallbackUrl
    get_Msg                         | set_Msg
    get_ResourceVersion             | set_ResourceVersion
    get_TableVersion                | set_TableVersion
    get_MediaVersion                | set_MediaVersion
    get_PatchVersion                | set_PatchVersion
    get_IsOpenPreDownload           | set_IsOpenPreDownload
    get_AssetBundlesUrlRoots        | set_AssetBundlesUrlRoots
    get_BundlesCatalogUrls          | set_BundlesCatalogUrls
    get_BundlesHashUrls             | set_BundlesHashUrls
    get_AddressCatalogUrls          | set_AddressCatalogUrls
    get_AddressHashUrls             | set_AddressHashUrls
    get_MediaUrlRoots               | set_MediaUrlRoots
    get_MediaManifestUrlRoots       | set_MediaManifestUrlRoots
    get_MediaManifestHashUrlRoots   | set_MediaManifestHashUrlRoots
    get_TableManifestUrlRoots       | set_TableManifestUrlRoots
    get_TableManifestHashUrlRoots   | set_TableManifestHashUrlRoots
    get_TableUrlRoots               | set_TableUrlRoots
    get_PatchUrlRoots               | set_PatchUrlRoots
    get_PatchCatalogUrlRoots        | set_PatchCatalogUrlRoots
    get_CDNLineCount                | set_CDNLineCount
    get_MediaManifestFileName       | get_MediaManifestHashFileName
    get_TableManifestFileName       | get_TableManifestHashFileName
```

背街字段区（`0x0012A2B6` 起）**逐个印证**了上面这组，且顺序一致：

```
<AddressablesCatalogUrlRoot>k__BackingField   <AddressablesCatalogUrlRoots>k__BackingField
<ApiUrls>k__BackingField                      <CallbackUrl>k__BackingField
<Msg>k__BackingField                          <ResourceVersion>k__BackingField
<TableVersion>k__BackingField                 <MediaVersion>k__BackingField
<PatchVersion>k__BackingField                 <IsOpenPreDownload>k__BackingField
<AssetBundlesUrlRoots>k__BackingField         <BundlesCatalogUrls>k__BackingField
<BundlesHashUrls>k__BackingField              <AddressCatalogUrls>k__BackingField
<AddressHashUrls>k__BackingField              <MediaUrlRoots>k__BackingField
<MediaManifestUrlRoots>k__BackingField        <MediaManifestHashUrlRoots>k__BackingField
<TableManifestUrlRoots>k__BackingField        <TableManifestHashUrlRoots>k__BackingField
<TableUrlRoots>k__BackingField                <PatchUrlRoots>k__BackingField
<PatchCatalogUrlRoots>k__BackingField         <CDNLineCount>k__BackingField
```

字段区（`0x0012A5F4`）与私有成员：

```
callbackUrlData | apiIndex
AddressablesCatalogUrlRoot | AddressablesCatalogUrlRoots | ApiUrls | ApiUrl | Msg
ResourceVersion | TableVersion | MediaVersion | PatchVersion | IsOpenPreDownload
AssetBundlesUrlRoots | BundlesCatalogUrls | BundlesHashUrls | AddressCatalogUrls | AddressHashUrls
MediaUrlRoots | MediaManifestUrlRoots | MediaManifestHashUrlRoots
TableManifestUrlRoots | TableManifestHashUrlRoots | TableUrlRoots | PatchUrlRoots | PatchCatalogUrlRoots
CDNLineCount | MediaManifestFileName | MediaManifestHashFileName
TableManifestFileName | TableManifestHashFileName
```
方法：
```
ResetApiUrl | InitResPaths | GetRuntimePlatform
GetAssetBundlesUrlRoot | GetTableUrlRoot | GetMediaManifestUrlRoot | GetMediaManifestHashUrlRoot
GetMediaUrlRoot | GetTableManifestUrlRoot | remotePatchHash | GetRemotePatchHashFiles
```

**完整字段清单（推断类型）**

| # | 字段 | 推断类型 | 依据 |
|---|---|---|---|
| 1 | `AddressablesCatalogUrlRoot` | `string` | get/set 成对 |
| 2 | `AddressablesCatalogUrlRoots` | `List<string>` | 名字复数 + `get_…Roots` + `InitResPaths` |
| 3 | `ApiUrls` | `List<string>` | 复数 + 私有字段 `apiIndex` + `ResetApiUrl` |
| 4 | `ApiUrl` | `string`（**只读派生**） | 只有 getter；配合 `apiIndex` 从 `ApiUrls` 取 |
| 5 | `CallbackUrl` | `string`（**内部是 JSON 字符串**） | 私有字段 `callbackUrlData` + 类 `CallbackUrlData` |
| 6 | `Msg` | `string` | get/set 成对 |
| 7 | `ResourceVersion` | `string` | get/set 成对 |
| 8 | `TableVersion` | `string` | 同上 |
| 9 | `MediaVersion` | `string` | 同上 |
| 10 | `PatchVersion` | `string` | 同上 |
| 11 | `IsOpenPreDownload` | `bool` | `Is` 前缀 |
| 12 | `AssetBundlesUrlRoots` | `List<string>` | 复数 |
| 13 | `BundlesCatalogUrls` | `List<string>` | 复数 |
| 14 | `BundlesHashUrls` | `List<string>` | 复数 |
| 15 | `AddressCatalogUrls` | `List<string>` | 复数 |
| 16 | `AddressHashUrls` | `List<string>` | 复数 |
| 17 | `MediaUrlRoots` | `List<string>` | 复数 |
| 18 | `MediaManifestUrlRoots` | `List<string>` | 复数 |
| 19 | `MediaManifestHashUrlRoots` | `List<string>` | 复数 |
| 20 | `TableManifestUrlRoots` | `List<string>` | 复数 |
| 21 | `TableManifestHashUrlRoots` | `List<string>` | 复数 |
| 22 | `TableUrlRoots` | `List<string>` | 复数 |
| 23 | `PatchUrlRoots` | `List<string>` | 复数 |
| 24 | `PatchCatalogUrlRoots` | `List<string>` | 复数 |
| 25 | `CDNLineCount` | `int` | 名字 |

> **类型判断为「推断」**：元数据头部被加密（见 §3），拿不到 `Il2CppFieldDefinition` 的 `typeIndex`，因此类型是从命名惯例（单/复数、`Is` 前缀、有无 setter）推出来的。字段**名字与顺序是实测**。

### 2.2 `CallbackUrl` 的真实结构（**实测**）

`CallbackUrlData` 类就在 `0x001D71` 附近，紧随 `StateResultCode`：

```
CallbackUrlData
  get_order_notify | set_order_notify | <order_notify>k__BackingField
  get_web_notify   | set_web_notify   | <web_notify>k__BackingField
  get_account_logout | set_account_logout | <account_logout>k__BackingField
  get_survey_notify  | set_survey_notify  | <survey_notify>k__BackingField
```

与本工程 `ba-pentest.md §13.1` 里真实抓到的 `CallbackUrl` 完全吻合：

```json
{"order_notify":"http://gs-inter.bluearchive-cn.com:4000/api/order/notify",
 "survey_notify":"http://gs-inter.bluearchive-cn.com:4000",
 "web_notify":"http://gs-inter.bluearchive-cn.com:4000/api/web/notify",
 "account_logout":"http://gs-inter.bluearchive-cn.com:4000/api/account/logout"}
```

⇒ 这**直接证明**：真实 `gsqc-api/api/state` 的 676 B 应答体就是 `ServerInfoConnectionGroupData`。
⇒ 也说明 `CallbackUrl` 是**被转义成字符串的嵌套 JSON**，不是一个普通 URL。

### 2.3 DTO B — `StateServerResponse`（区服列表）

`0x0012A917` 起：

```
ServerInfoDataRepository
  get_DataHash | set_DataHash | get_LastErrorMessage | set_LastErrorMessage
  version | GetConfig | get_StateServerUrl | url
  DownloadServerInfoDataHttp2 | GetApiServerInfo | GetGameServerInfo
  <DataHash>k__BackingField | <LastErrorMessage>k__BackingField | <Instance>k__BackingField
  DataHash | LastErrorMessage | StateServerUrl
  StateServerResponse | Servers
  <DownloadServerInfoDataHttp2>d__22
  <GetApiServerInfo>b__0 | <GetApiServerInfo>b__1 | <>c__DisplayClass23_1 | <GetApiServerInfo>b__2 | <GetApiServerInfo>b__3
  <GetApiServerInfo>d__23
  <header>5__2 | <isLive>5__3 | <i>5__4
  <GetGameServerInfo>b__0 | <GetGameServerInfo>b__1 | <GetGameServerInfo>b__2 | <GetGameServerInfo>b__3
  <GetGameServerInfo>d__24
```

读法：

- `ServerInfoDataRepository` 是**单例**（`<Instance>k__BackingField`），持有
  - `DataHash`（配置内容哈希，用于判断是否变化）
  - `LastErrorMessage`
  - `StateServerUrl`（`get_StateServerUrl` 只读 → 从配置取）
  - `StateServerResponse`（**DTO B 的实例**）
  - `Servers`
- `GetApiServerInfo` 是一个**迭代器**（`<GetApiServerInfo>d__23`），局部变量 `<i>5__4`（下标）、`<isLive>5__3`（存活标记）、**`<header>5__2`（一个 HTTP 头）** → **它要按 `Servers` 列表逐个探测，判断哪台活着**。
- `GetGameServerInfo`（`d__24`）是拿到活的那台之后再去取"游戏服信息"。
- `DownloadServerInfoDataHttp2` → 走 **HTTP/2**。

**DTO B 的字段**：`Servers`（字符串数组）。`State` / `Msg` 因为全局去重不在此处重现（见 §1.3），但真实抓包证明它们存在（§4.1）。

**结论**：`StateServerResponse` ≈ `{ "Servers": [string...], "State": int, "Msg": string }`。

---

## 三、第 3 步：metadata 头部结构（**结论：被加密，放弃**）

### 3.1 实测

```
00000000  94 43 72 12 18 4b 9e ec 66 67 66 66 a6 62 65 66  |.Cr..K..fgff.bef|
00000010  a6 63 65 66 6e a2 6d 66 ae af 68 66 ee 1a 0a 66  |.cefn.mf..hf...f|
00000020  36 20 1d 66 de 5e 66 66 6e 19 1d 66 6a cb 69 66  |6 .f.^ffn..fj.if|
...
```

- `first u32 LE = 0x12724394` ≠ 标准 magic `0xFAB11BAF`
- `next u32 LE = 0xEC9E4B18` ≠ 任何合法版本号（24/27/29/31）
- 全文件前 64 KB 内**找不到** `AF 1B B1 FA`

### 3.2 观察到的强规律

从偏移 `0x08` 开始，**每 4 字节的第 4 个字节恒为 `0x66`**：

```
0x0B=66  0x0F=66  0x13=66  0x17=66  0x1B=66  0x1F=66  0x23=66 ... (0x27=66, 0x2B=66, 0x2F=66, 0x33=66)
```

这是典型的「按 4 字节周期做 XOR/加法混淆」的痕迹——高位字节原文多为 0x00（小整数偏移量），异或常量后变成固定值 `0x66`。

但用 magic 反推的密钥（`3B 58 C3 E8`）与「末位恒 0x66」矛盾，说明**不是固定 4 字节 XOR**，更像滚动密钥或分组置换。

### 3.3 判定

- **走不通**：无法解析 `Il2CppGlobalMetadataHeader` 的区段表 → 拿不到 `fieldDefaultValues`、`typeDefinitions`、`methodDefinitions` 的索引 → **无法给出枚举数值、准确类型、以及精确的"哪些字段必填"**。
- 本工程 `ba-il2cpp.md §四.3` 早已得出同样结论：「`global-metadata.dat` 不值得投人力做解密：名字明文已足够支撑按名解析」。
- **但**：字符串区（`0x00129000` 之后）是**完全明文**的，所以 §2 的字段表还原是可靠的。

尝试过的手段（均记录在案）：
1. 直接读首 4 字节 magic — 失败
2. 全文件搜标准 magic — 前 64KB 内失败
3. 用 magic 反推固定 XOR 密钥 — 与「末位恒 0x66」的观测矛盾
4. 汉字 UTF-8/UTF-16 扫描 — 只得到噪声（见 §5）

**放弃，按任务约定不在此处超过 20 分钟。**

---

## 四、第 4 步：从 DTO 反推「服务端应该回什么」

### 4.1 真实服务器原文（本工程 `work\ba\audit\ba-pentest.md`，实测抓包）

**① `state-api.bluearchive-cn.com/api/state`（区服状态，DTO B）**

```json
{"Servers":["https://gsqc-api.bluearchive-cn.com/api/","https://gs-api.bluearchive-cn.com/api/"],
 "State":1,"Msg":"服务器维护中，请耐心等待开服！"}
```

**② `gsqc-api.bluearchive-cn.com/api/state`（网关配置，DTO A）→ 200 / 676 B**

```json
{"CallbackUrl":"{\"order_notify\":\"http://gs-inter.bluearchive-cn.com:4000/api/order/notify\",
                \"survey_notify\":\"http://gs-inter.bluearchive-cn.com:4000\",
                \"web_notify\":\"http://gs-inter.bluearchive-cn.com:4000/api/web/notify\",
                \"account_logout\":\"http://gs-inter.bluearchive-cn.com:4000/api/account/logout\"}",
 "CustomerServiceUrl":"", "AddressablesCatalogUrlRoots":[...] }
```

**③ 旁证（`ba-pentest.md §13.4`）**：同一网关在 `APP-VER: 1.0.0` 时退化为 **325 B** 空配置（`CallbackUrl=""` / `CatalogUrls=null`）；完全不带身份头时 **214 B**。

### 4.2 我们服务端现在回的（180 B，两个 conf 各一份）

```json
{"Servers":["https://example.com/api/"],"State":0,"Msg":"","CallbackUrl":"",
 "CustomerServiceUrl":"","AddressablesCatalogUrlRoots":["https://static.bluearchive-cn.com/prodm39"]}
```

### 4.3 逐字段比对 — 这是核心

| 字段 | 属于哪个 DTO | 真实值 | 我们的值 | 判定 |
|---|---|---|---|---|
| `Servers` | **DTO B** | 2 个 `…/api/` 结尾的网关 URL | 1 个 `example.com/api/` | ⚠️ **只有 1 个**；`GetApiServerInfo` 是迭代器，疑似需要 ≥2 做故障切换 |
| `State` | **DTO B** | `1`（维护中） | `0` | ✅ **0 = 正常，我们的值是对的**（见下） |
| `Msg` | DTO B / DTO A 都有 | `"服务器维护中，请耐心等待开服！"` | `""` | ⚠️ **空串 → 弹窗正文空白的头号嫌疑** |
| `CallbackUrl` | **DTO A** | 转义后的 JSON 字符串（4 个回调 URL） | `""` | ❌ 空 |
| `CustomerServiceUrl` | **哪都不是** | `""` | `""` | ✅ 客户端**不读**（元数据 0 命中），可以随便写 |
| `AddressablesCatalogUrlRoots` | **DTO A** | `[...]` | `["https://static.bluearchive-cn.com/prodm39"]` | ✅ 值形似，但放错了接口 |
| `ApiUrls` | DTO A | 未记录 | **缺失** | ❌ 缺 |
| `ApiUrl` | DTO A | 未记录（派生） | **缺失** | ❌ `ApiUrls` 为 null ⇒ `ApiUrl` 取不到 |
| `ResourceVersion` | DTO A | 未记录 | **缺失** | ❌ 缺 |
| `TableVersion` | DTO A | 未记录 | **缺失** | ❌ 缺 |
| `MediaVersion` | DTO A | 未记录 | **缺失** | ❌ 缺 |
| `PatchVersion` | DTO A | 未记录 | **缺失** | ❌ 缺 |
| `IsOpenPreDownload` | DTO A | 未记录 | **缺失** | 缺（bool 默认 false，可能无害） |
| `AssetBundlesUrlRoots` | DTO A | 未记录 | **缺失** | ❌ 缺 |
| `BundlesCatalogUrls` / `BundlesHashUrls` | DTO A | 未记录 | **缺失** | ❌ 缺 |
| `AddressCatalogUrls` / `AddressHashUrls` | DTO A | 未记录 | **缺失** | ❌ 缺 |
| `MediaUrlRoots` / `MediaManifestUrlRoots` / `MediaManifestHashUrlRoots` | DTO A | 未记录 | **缺失** | ❌ 缺 |
| `TableManifestUrlRoots` / `TableManifestHashUrlRoots` | DTO A | 未记录 | **缺失** | ❌ 缺 |
| `TableUrlRoots` / `PatchUrlRoots` / `PatchCatalogUrlRoots` | DTO A | 未记录 | **缺失** | ❌ 缺 |
| `CDNLineCount` | DTO A | 未记录 | **缺失** | 缺（int 默认 0，**可能触发除零**） |

### 4.4 `State` 取值语义（推断，中等置信）

- 真实服务器在**维护中**时返回 `State: 1` + `"服务器维护中，请耐心等待开服！"`，且 `ba-pentest.md §十四` 明确记录「**客户端不会发出任何业务请求**」。
- 元数据里 `StateResultCode` 枚举（`0x001D70E7`，**全局唯一 1 处**）成员依次为：
  ```
  StateResultCode | Maintain | AppUpdate
  ```
  其所在类是 SDK 的 `DirRequest`/`Connect` 实现（相邻：`ConnectState | Connecting | _request | _bodyByte | _headerDict | _timeoutSec | readyForRequest | GetHeader | fail | Connect | CheckResultCode | TIMEOUT_ERROR_STRING | TIMEOUT_SEC`）。
- 结合真实抓包（`1` 对应维护），可判定：
  - **`State = 0` → 正常开服**
  - **`State = 1` → Maintain（维护中）**
  - **`State = 2` → AppUpdate（强制更新）**
  - （`Maintain`/`AppUpdate` 的具体数值**未实测**——头部加密拿不到 `fieldDefaultValues`，无法直接读出枚举常量。上面是从「真实抓包 State:1 + 维护文案 + 客户端零业务请求」反推的。）

⇒ **我们现在回 `State:0` 是符合"正常开服"语义的，不需要改。** 这与「客户端弹了一个空白框」并不矛盾——那个框不是维护框（维护框会显示 `Msg` 里的维护文案）。

### 4.5 必填性判断（**这是推断，必须标注**）

- 若客户端用 **Unity `JsonUtility.FromJson<T>`**：缺失字段静默取默认值（`string`→`null`、`int`→`0`、`List<T>`→`null`/空），**不抛异常**。所以"字段缺失"本身不会直接弹错误框，但会在后续解引用 `null` 时炸。
- 若用 **Newtonsoft**（元数据里有 `Newtonsoft.Json` 的痕迹，见 `Ctrl_*` / `Converters`）：`List<T>` 缺字段会留 `null`，同样在后续炸。
- **风险最高的两处**：
  1. `ApiUrls` 为 `null` ⇒ `ApiUrl`（getter 里 `ApiUrls[apiIndex]`）**直接 `NullReferenceException` 或 `IndexOutOfRangeException`**；
  2. `CDNLineCount == 0` 若被用于取模/分片，可能除零。

---

## 五、第 5 步：弹窗路径 —— 中文字面量扫描结果（**关键否定证据**）

### 5.1 扫描方法与结果

对 `global-metadata.dat` 全文做 UTF-8 三字节 CJK 与 UTF-16LE CJK 扫描，命中 **163 + 一批**，但**逐条检查全部是噪声**（随机字节恰好解码成汉字）：

```
0x00001BD0  窵鿡
0x00013ED1  榆敟
0x000312AA  伻巿
...
```

**没有一条是真实中文文案**（没有「提示」「确定」「网络异常」「维护中」「版本过低」）。完整清单见 `report\_tmp\meta_re\s3_cjk.txt`。

### 5.2 这个否定结果本身价值很高

- 说明 **BA 的 UI 文案不在 `global-metadata.dat` 里**，而是走**外部本地化表**（本工程已知 `assets/…/LocalizeConfig.txt` + `TableBundles/` 里的本地化表包）。
- ⇒ **「提示」这个标题和「确定」这个按钮是本地化表里的固定串**，而**正文是运行时传入的参数**。
- ⇒ **正文空白 ⇔ 调用方传了一个空字符串**。最可能的来源就是我们回的 `"Msg":""`。

### 5.3 `libil2cpp.bin` 侧

对 270,927,056 B 的 `libil2cpp.bin` 全文扫描：

```
CustomerServiceUrl            0 hit
AddressablesCatalogUrlRoots   0 hit
CallbackUrl                   0 hit
Servers                       0 hit
ApiUrls                       0 hit
/api/state                    0 hit
/api/gateway                  0 hit
state-api.bluearchive         0 hit
bluearchive-cn.com            0 hit
```

**全部 0 命中**。这符合 il2cpp 的机制：**C# 字符串字面量存放在 `global-metadata.dat` 的 `stringLiteralData` 区，不在 `libil2cpp.so` 里**。所以本报告的"字符串只在 metadata 找"这个方法论是对的，也说明 `.text` 被 ACE 加密这件事不影响本任务。

### 5.4 无法进一步定位的部分（诚实标注）

- 由于头部加密，**拿不到 `methodDefinitions` 索引**，所以无法静态定位「哪个方法调用了弹窗」「弹窗第二个参数来自哪里」。要走这条路只能等运行时 hook。
- 但 §5.2 已经给出了等价结论：**去查我们回的 `Msg` 是不是被塞进了弹窗正文** —— 这正是 Lead 已经安排的那个 `PROBE-M1-STATE-ZQ7` 实验。

---

## 六、给服务端的建议 JSON

### 6.1 关键认知：`/api/state` 是**两个不同接口**，必须按 Host 分流

```
GET https://state-api.bluearchive-cn.com/api/state   → DTO B（区服列表，小）
GET https://gsqc-api.bluearchive-cn.com/api/state    → DTO A（网关配置，大，676B）
GET https://gs-api.bluearchive-cn.com/api/state      → DTO A（备用，同上）
```

我们现在的 `ba_mitm.conf` 用一条 `location = /api/state` 对全部 `server_name` 返回同一份 180 B，**这就是结构性错误**。

### 6.2 建议的 DTO B（给 `state-api.bluearchive-cn.com`）

```jsonc
{
  "Servers": [
    "https://gsqc-api.bluearchive-cn.com/api/",   // 实测：必须 /api/ 结尾
    "https://gs-api.bluearchive-cn.com/api/"      // 实测：真实服务器给 2 个
  ],
  "State": 0,                                      // 推断：0=正常 1=维护 2=强更
  "Msg": "PROBE-M1-STATE-ZQ7"                      // 实测：Msg 是真实字段；此处放探针
}
```
- `Servers`：**实测**真实值形如 `https://<host>/api/`（见 §4.1）。保留两个元素，让 `GetApiServerInfo` 的迭代器有东西可切。
- `State`：**推断** `0`。
- `Msg`：**实测**字段存在；现在是空串，**这是弹窗正文空白的头号嫌疑**。

### 6.3 建议的 DTO A（给 `gsqc-api` / `gs-api`）

```jsonc
{
  "CallbackUrl": "{\"order_notify\":\"\",\"survey_notify\":\"\",\"web_notify\":\"\",\"account_logout\":\"\"}",
  //   实测：CallerId 是"转义 JSON 字符串"，内含 4 个键（类 CallbackUrlData）
  //   实测：真实值是 http://gs-inter.bluearchive-cn.com:4000/...
  //   私服可以先给空串 URL，但**不能是空字符串 `""` 本身**（那会让 callbackUrlData 解析失败）

  "AddressablesCatalogUrlRoot":  "https://static.bluearchive-cn.com/prodm39",
  "AddressablesCatalogUrlRoots": ["https://static.bluearchive-cn.com/prodm39"],
  //   实测：真实响应里有

  "ApiUrls": ["https://gsqc-api.bluearchive-cn.com/api/"],
  //   推断：必填，`ApiUrl` getter 依赖它；给 null 会 NRE

  "ResourceVersion": "",
  "TableVersion":    "",
  "MediaVersion":    "",
  "PatchVersion":    "",
  "IsOpenPreDownload": false,

  "AssetBundlesUrlRoots":         ["https://static.bluearchive-cn.com/prodm39"],
  "BundlesCatalogUrls":           [],
  "BundlesHashUrls":              [],
  "AddressCatalogUrls":           [],
  "AddressHashUrls":              [],
  "MediaUrlRoots":                [],
  "MediaManifestUrlRoots":        [],
  "MediaManifestHashUrlRoots":    [],
  "TableManifestUrlRoots":        [],
  "TableManifestHashUrlRoots":    [],
  "TableUrlRoots":                [],
  "PatchUrlRoots":                [],
  "PatchCatalogUrlRoots":         [],
  "CDNLineCount": 1,
  //   推断：空数组比 null 安全（Newtonsoft 对 null 数组处理更脆）
  //   推断：CDNLineCount 给 1 而不是 0，避免除零/取模

  "Msg": ""
}
```

### 6.4 每个字段的来源依据

| 字段 | 来源 |
|---|---|
| `Servers` / `State` / `Msg`（DTO B） | **实测**：`ba-pentest.md §4.1` 真实抓包 + 元数据 `StateServerResponse`、`Servers` |
| `CallbackUrl` 结构 | **实测**：`ba-pentest.md §13.1` 真实响应 + 元数据 `CallbackUrlData` 类（4 个键完全吻合） |
| 25 个 DTO A 字段名 | **实测**：元数据 `ServerInfoConnectionGroupData` 属性表 + 背街字段表（两处互相印证） |
| 各字段类型 | **推断**：从单/复数命名、`Is` 前缀、有无 setter、兄弟方法名推出 |
| `ApiUrls` 必填 | **推断**：`ApiUrl` 只有 getter 且依赖 `apiIndex` |
| `CDNLineCount ≥ 1` | **推断**：防除零 |
| `State` 的 0/1/2 语义 | **推断**：真实抓包 State:1↔维护 + 元数据 `StateResultCode{Maintain, AppUpdate}` |
| `CustomerServiceUrl` 可忽略 | **实测**：元数据 0 命中 |

### 6.5 被排除的可能（不要再往这些方向查）

| 假设 | 结论 | 依据 |
|---|---|---|
| 客户端有硬编码的「提示」文案常量 | **排除** | metadata 里 0 条真实中文；文案在本地化表 |
| `CustomerServiceUrl` 缺失导致报错 | **排除** | 客户端根本不读这个字段（0 命中） |
| `State:0` 被当成维护态 | **很可能排除** | `State:1` 才是维护（真实抓包佐证）；且维护框会显示 `Msg` 文案而非空白 |
| 字符串常量藏在 `libil2cpp.so` 里 | **排除** | 全文 0 命中；il2cpp 字面量在 metadata |

---

## 七、对主线下一步的直接建议

1. **先看 `PROBE-M1-STATE-ZQ7` 的结果**（Lead 已下发的实验）。它能一次性回答「弹窗正文是不是 `Msg`」。
2. **无论探针结果如何，都要把 `/api/state` 按 Host 拆成两个 DTO。** 现在两份 conf 回同一个 180 B，是结构性错误——即使 `Msg` 不是弹窗来源，第二跳（`gsqc-api/api/state`）拿到 DTO B 的 JSON 去反序列化 DTO A，**必然全字段为 null**，`ApiUrl` 取不到，然后炸。
3. **补一个 `ApiUrls` + `CDNLineCount:1`**，即使其它字段先留空——这两个是最可能在 getter 里直接 NRE 的。
4. 复核 pcap 里那 4 次 `/api/state` 的 `host=` 到底是 `state-api` 还是 `gsqc-api`。如果是 `gsqc-api`，那说明第二跳已经发生了，只是我们回了错 DTO——这与「客户端未发下一跳」的结论并不冲突，只是把卡点后移了一格。

---

## 附：本次所有中间产物

| 文件 | 内容 |
|---|---|
| `report\_tmp\meta_re\s1_scan.py` / `s1b_scan.py` | 字段名字面量扫描（v1 因输出爆炸被废弃，v2 去重） |
| `report\_tmp\meta_re\s1_out2.txt` | 6 个字面量的命中计数 + 去重邻域 |
| `report\_tmp\meta_re\s2_regions.py` / `s2_regions.txt` | API-DTO 簇、StateResultCode、Servers 三个区段的完整 token dump |
| `report\_tmp\meta_re\s2b_probe.py` / `s2b_probe.txt` | 背街字段精确探针 + libil2cpp 全文串搜索 |
| `report\_tmp\meta_re\s3_cjk.py` / `s3_cjk.txt` | 头部 hexdump + UTF-8/UTF-16 中文字面量扫描 |
| `report\_tmp\meta_re\s4_types.py` / `s4_types.txt` | 4 个类型名的完整窗口 dump |
