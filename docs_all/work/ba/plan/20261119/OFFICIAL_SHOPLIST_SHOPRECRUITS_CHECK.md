# 官方抓包核对：`Shop_List`(10002) 到底带不带 `ShopRecruits`？`10006` 在官方流量里存在吗？

> **纯只读核查**（2026-11-19）。未联网、未改任何代码/数据、未碰服务器；本次唯一写入的文件就是本报告。
> 数据源：`report\_tmp\official_decoded_201\`（源 HAR `report\_tmp\official201.har`，sha256 `e4cabb58…92b65fd`，条目 201 → 解出 **109 对** RPC 请求/响应，共 227 个文件；抓包窗口 `04:30:54.662` → `04:34:32.426`）。

---

## 0. 结论（第 5 条）

**官方客户端的招募卡池清单不是从 `Shop_List`(10002) 拿的。**

1. 本目录**唯一一份** 10002 响应里**没有 `ShopRecruits` 键**（顶层只有 7 个键：`Protocol / SessionKey / ServerTimeTicks / ServerNotification / RequestId / ShopInfos / ShopEligmaHistoryDBs`）。
2. 全目录 grep `ShopRecruits`（以及 `GachaRecruit`）**只命中一个文件**：`02_1017_api_account_loginsync.response.json` —— 它出现在 `Account_LoginSync`(1017) 响应里**内嵌的子包** `ShopGachaRecruitListResponse` 中，共 **529 条**。
3. 官方抓包里**没有**独立的 10006 报文（没有 `/api/shop/gacharecruitlist` 这个路径，109 对 RPC 里没有协议号 10006 的文件）；但 1017 **请求**的 `SyncProtocols` 数组里明确列了 `10006`（第 14 项）——客户端是把它当"随登录同步的协议"来索取的，服务端于是把 10006 的响应体（名字就叫 `ShopGachaRecruitListResponse`）**预置进 LoginSync 响应**。

⇒ **卡池数据 = LoginSync 内嵌的 `ShopGachaRecruitListResponse.ShopRecruits`，不是 `Shop_List`。**
⇒ 反过来也要说清：本抓包**不能**证明"客户端点开招募界面时还会补发一次独立 10006"——这份抓包里没有该报文，也没有证据说它一定会发或一定不发。

**附带的两个硬对照（对当前 bug 很关键）：**

- 官方对 `CategoryList=[38]` 的 `Shop_List` 响应，**也只有 2 个商品**、`ShopExcelId` 就是 **201/202**、`Category=38`。⇒ 我们回 2 条**不是"给少了"**，与官方一致。
- 官方这 2 个商品**都带 `"Price":0`**；我方 `ShopManager` 按注释"官方从不带 Price"而**不发该字段**。⇒ 该注释至少对这份官方样本不成立（详见 §6）。

---

## 1. 目录里所有与 shop 相关的文件

**只有一对**（109 对 RPC 中编号 86）：

| 文件 | 字节数 | 说明 |
|---|---:|---|
| `86_10002_api_shop_list.request.json` | **913** | `POST /api/shop/list`，`meta.id=201`，`bj=04:33:59.137`，`req_bytes=946` |
| `86_10002_api_shop_list.response.json` | **2535** | 同上事务的响应，`status=200`，`resp_bytes=1304`（线上 body 字节数；磁盘上 2535B 是 wrapper 转义后的体积） |

**没有**第二个 shop 文件：目录内不存在 `10006`、`shop/gacharecruitlist`、`shop/buy`、`shop/refresh` 之类的其他文件名。

旁证：`40_bluearchive_hosts.json`（125 条 `*.bluearchive-cn.com` 记录）里 `/api/shop*` **只出现 1 次**，就是 `/api/shop/list`（该文件第 1132 行）——**没有** `/api/shop/gacharecruitlist`。

---

## 2. 唯一的 10002 `Shop_List` 响应逐项核对

### 2.1 文件信封

文件是"带包装的明文 JSON"，三层：

```json
{ "meta": {...}, "plain": "<双次转义的原始报文字符串>", "inner": {...} }
```

- `meta` = `{"id":201,"bj":"04:33:59.137","status":200,"resp_bytes":1304,"protocol":10002}`
- `plain` = 原始 HTTP body（明文 JSON 字符串，含 `RequestId`/`requestid` 两个包装键）
- `inner` = 把 `plain.packet` 再解析出来的响应对象（**下面所有分析用 `inner`**）

### 2.2 响应 `inner` 的**顶层键完整清单**（共 7 个，按出现顺序）

| # | 键 | 值（摘要） |
|---:|---|---|
| 1 | `Protocol` | `10002` |
| 2 | `SessionKey` | `{AccountServerId: 10015354380, MxToken: "Vji5A/Cy…"}`（回显请求） |
| 3 | `ServerTimeTicks` | `639304004389780580` |
| 4 | `ServerNotification` | `0` |
| 5 | `RequestId` | `"43cadb1c-7436-4ca7-826d-a9c59c3a69af"` |
| 6 | `ShopInfos` | 数组，**1** 个元素（见 2.3） |
| 7 | `ShopEligmaHistoryDBs` | `[]` |

### 2.3 有没有 `ShopRecruits`？

**没有。** 该响应里**不存在** `ShopRecruits`，也不存在任何 `*Recruit*` 键（`ShopInfos` 里的商品也没有 recruited 相关字段）。整份响应的键集合到 `ShopEligmaHistoryDBs` 就结束了。

作为对照，`ShopInfos` 的完整内容（**原样**，`inner.ShopInfos[0]`）：

```json
{
  "EventContentId": 0,
  "Category": 38,
  "ShopGroupType": 0,
  "ManualRefreshCount": null,
  "IsRefresh": false,
  "NextAutoRefreshDate": null,
  "LastAutoRefreshDate": null,
  "ShopProductList": [
    { "EventContentId": 0, "ShopExcelId": 201, "Category": 38, "DisplayOrder": 1,
      "PurchaseCount": 0, "SoldOut": false, "PurchaseCountLimit": 1, "Price": 0, "ProductType": 0 },
    { "EventContentId": 0, "ShopExcelId": 202, "Category": 38, "DisplayOrder": 1,
      "PurchaseCount": 0, "SoldOut": false, "PurchaseCountLimit": 1, "Price": 0, "ProductType": 0 }
  ]
}
```

`ShopProductList` 每条元素的键：`EventContentId / ShopExcelId / Category / DisplayOrder / PurchaseCount / SoldOut / PurchaseCountLimit / Price / ProductType`（**含 `Price`**）。
`ShopInfos` 元素的键：`EventContentId / Category / ShopGroupType / ManualRefreshCount / IsRefresh / NextAutoRefreshDate / LastAutoRefreshDate / ShopProductList`。

### 2.4 请求侧对应的 `CategoryList`

**`CategoryList = [38]`**（即 `38` 是本次唯一的分类）。

`86_10002_api_shop_list.request.json` → `json` 字段的顶层键与值：

```
Protocol=10002, CategoryList=[38], Resendable=true, Hash=42958262894679,
IsTest=false, SessionKey={AccountServerId:10015354380, MxToken:"…(已脱敏)"},
AccountId=10015354380, OSType=2
```

原始 `plain`（MxToken 已打码）：

```json
{"Protocol":10002,"CategoryList":[38],"Resendable":true,"Hash":42958262894679,"IsTest":false,
 "SessionKey":{"AccountServerId":10015354380,"MxToken":"Vji5A/…(masked)"},
 "AccountId":10015354380,"OSType":2}
```

同目录**没有**第二份 `Shop_List` 请求可配对；**这一份就是官方客户端在抓包里唯一一次 `Shop_List` 调用**（时间 `04:33:59.137`，登录 `04:30:55.110` 之后约 3 分钟，抓包结束前 ~33 秒）。

> 说明：此前 `work\ba\plan\20261119\SHOPLIST_CATEGORY38_ANALYSIS.md` §7 留的待验证项"官方进招募页时发的 `CategoryList` 到底是哪些值"——本抓包的回答是：**`[38]`，只有 38，别的一个都没有**。也就是说"进招募界面只发 `Shop_List[38]`"这个现象在官方侧**同样发生**，本身不是我们的 bug。

---

## 3. 全目录 grep：`ShopRecruits` / `GachaRecruit`

### 3.1 `ShopRecruits` —— 命中 2 处，同一个文件

| 文件 | 行号 | 命中行（摘录） |
|---|---:|---|
| `02_1017_api_account_loginsync.response.json` | **9** | `…\"ServerNotification\":0,\"RequestId\":\"\",\"ShopRecruits\":[{\"Id\":5000000,\"SalesStartDate\":\"2023-08-03T05:00:00\",…` ← 这是 `plain` 整行（该行 220,418 字符，双次转义），`ShopRecruits` 起始偏移 124343 |
| `02_1017_api_account_loginsync.response.json` | **5769** | `      "ShopRecruits": [` ← `inner` 里的美化版，紧跟 `"ShopGachaRecruitListResponse": {`（第 **5760** 行） |

其余 226 个文件：**0 命中**。

### 3.2 `GachaRecruit` —— 命中 2 处，同一个文件

| 文件 | 行号 | 命中行（摘录） |
|---|---:|---|
| `02_1017_api_account_loginsync.response.json` | **9** | `…\"AccountId\":0…\"ShopGachaRecruitListResponse\":{\"Protocol\":0,…` ← 同上 `plain` 整行 |
| `02_1017_api_account_loginsync.response.json` | **5760** | `    "ShopGachaRecruitListResponse": {` ← 1017 响应 `inner` 的第 21 个顶层子键（`inner` 共 35 个键） |

### 3.3 说明

- 两处都是**同一个对象**：1017 响应的 `ShopGachaRecruitListResponse`（一个内嵌子响应），`GachaRecruit` 出现在对象名里，`ShopRecruits` 出现在它的字段名里。
- 整个 109 对官方 RPC 中，**只有这一个地方**承载卡池清单。

---

## 4. 协议 10006 在官方抓包里是否出现过？

| 检查项 | 结果 |
|---|---|
| 文件名含 `10006` | **无**（109 对 RPC 里没有 `*_10006_*`） |
| 路径含 `gacharecruitlist` | **无**（`40_bluearchive_hosts.json` 125 条记录里都没有） |
| 报文里出现 `"Protocol":10006` | **无**（无任何 10006 请求/响应信封） |
| `10006` 作为**数字**出现 | 有，但几乎都是数据（角色 `UniqueId=10006`、`ShopRecruitId` 等） |
| `10006` 作为**协议号**出现 | **仅 1 处**：`02_1017_api_account_loginsync.request.json` 第 **30** 行，`SyncProtocols` 数组的第 **14** 项 |

1017 请求的 `SyncProtocols`（25 项，原样）：

```json
[20000,1003,2000,3000,5000,12000,6000,22001,17018,21000,28001,33000,19000,
 10006,39006,44000,29002,30041,45000,46000,46001,47000,49000,27002,49004]
```

⇒ **结论：官方抓包里"没有独立的 10006 报文"，但 10006 并不是"不存在"——它以「登录同步子协议」的形式被客户端显式索取，服务端用 1017 请求/响应里的同名子包把它一并下发了。**
（一个直接佐证：内嵌子包的对象名 `ShopGachaRecruitListResponse` 与协议 `Shop_GachaRecruitList` 同源，字段集 `ShopRecruits + ShopFreeRecruitHistoryDBs` 也与 10006 的响应 DTO 完全一致。）

---

## 5. 内嵌 `ShopGachaRecruitListResponse` 的细节（卡池真身）

位置：`02_1017_api_account_loginsync.response.json` → `inner.ShopGachaRecruitListResponse`（第 5760–8946 行）

**顶层键（7 个）**

| # | 键 | 值 |
|---:|---|---|
| 1 | `Protocol` | `0`（内嵌子响应的特征：不重复声明协议号） |
| 2 | `SessionKey` | `{"AccountServerId":0,"MxToken":""}` |
| 3 | `ServerTimeTicks` | `0` |
| 4 | `ServerNotification` | `0` |
| 5 | `RequestId` | `""` |
| 6 | **`ShopRecruits`** | **529 条** |
| 7 | `ShopFreeRecruitHistoryDBs` | `[]` |

**第一条完整元素（原样，压缩 JSON）**

```json
{"Id":5000000,"SalesStartDate":"2023-08-03T05:00:00","SalesEndDate":"2023-08-10T15:59:59","UpdateDate":"0001-01-01T00:00:00"}
```

**条数：529**（`ShopRecruits` 数组长度；ID 唯一，529 个不重复）

元素字段只有 4 个：`Id / SalesStartDate / SalesEndDate / UpdateDate`。

**ID 分布（按百万位分组）**

| ID 段 | 条数 | 备注 |
|---|---:|---|
| `5,000,000`–`5,00x,xxx` | 472 | 主卡池序列（`5000000, 5000010, …` 步长 10） |
| `6,000,001`–`6,004,103` | 32 | 常驻/特殊池 |
| `7,000,000`–`7,000,001` | 2 | |
| `8,000,000`–`8,000,004` | 5 | |
| `9,000,000`–`9,000,203` | 12 | |
| `10,000,000`–`10,000,003` | 4 | |
| `90,000,000` | 1 | `{Id:90000000,"2026-07-16T10:00:00"→"2099-12-31T03:59:59"}` |
| `99,999,999` | 1 | 哨兵值，`{Id:99999999,"2024-08-01T14:00:00"→"2099-12-31T03:59:59"}` |

**销售期跨度**：最早 `2023-08-03T05:00:00`（国服开服日），最晚 `2026-11-12T14:00:00`；按年份 2023:39 / 2024:131 / 2025:176 / 2026:183。⇒ 这是一份完整的、按时间排的卡池档期表，不是占位数据。

---

## 6. 顺带发现（与当前 bug 直接相关，仍然只读）

| 观察 | 官方样本（本目录） | 我方实现（据 `SHOPLIST_CATEGORY38_ANALYSIS.md` §6 转述） | 影响 |
|---|---|---|---|
| 38 分类商品数 | **2**（201/202） | 2 | 一致，**不是"给少了"** |
| `Price` 字段 | **每条都有，值 `0`** | **不发**（代码注释称官方 876 个商品里从未带 Price） | 该注释至少对本样本不成立；缺 `Price` 可能让客户端走默认价格（"1,000"）或禁用按钮——**【推测·待验证】** |
| `CategoryList` | `[38]` | `[38]` | 一致，"只发 38"是官方行为 |
| 卡池来源 | 1017 内嵌子包 | 1017 内嵌 + 10006 都实现 | 卡池清单已经在下发（529 条），问题不在"没给" |

> 注：`SHOPLIST_CATEGORY38_ANALYSIS.md` 依据客户端反编译得出 `38 = ShopCategoryType.CafeSummonTicket`、`ShopListResponse` 压根没有 `ShopRecruits` 字段——**与官方抓包完全吻合**，两条独立证据链互证。

---

## 7. 能判定 / 不能判定（证据边界）

**能判定（基于文件事实）**

1. 官方 `Shop_List`(10002) 响应**不含** `ShopRecruits` —— 本目录唯一一份 10002 响应可证，键表 7 项无此项。
2. 官方 `Shop_List` 对 `CategoryList=[38]` 的行为 = 2 个 `ShopExcelId` 201/202 商品 + `Price:0`，与卡池无关。
3. 官方卡池清单（529 条，含 2023–2026 档期）是在 `Account_LoginSync`(1017) 响应的 `ShopGachaRecruitListResponse` 里下发的。
4. 官方抓包内**无**独立 10006 报文；但客户端在 1017 的 `SyncProtocols` 里**点名要 10006**。

**不能判定（本抓包证据不足）**

1. 客户端**进入招募界面时**是否会另外补发一次独立 10006 —— 抓包窗口内（`04:30:54`–`04:34:32`）没有任何 10006 请求；但如果那次会话根本没有"点开招募并成功渲染卡池"的动作，就属于"没触发"，而不是"不会发"。
2. 客户端招募界面到底读哪个字段渲染卡池（`AccountLoginSyncResponse.ShopGachaRecruitListResponse` vs 10006 响应）—— 需要客户端侧代码/断点确认。

**要补的证据（按性价比排序）**

1. 一份「登录 → 点开招募 → 卡池正常显示」的**官方完整抓包**，重点看 1017 之后、招募界面前后是否有 10006；只要出现一次 10006，就能一锤定音。
2. 若拿不到官方抓包：在客户端反编译里找 `ShopGachaRecruitListResponse` / `ShopRecruits` 的消费点（谁把它塞进 gacha 界面的 model），确认 1017 内嵌子包是否被读取。
3. 官方 `Shop_List` 响应里 `Price` 的类型/默认值（本样本为 `0`），对照我方 DTO 里 `Price` 的字段号，确认"不发"是否等价于 0。

---

## 附录 A：复现命令（全部只读）

```powershell
$d='C:\Users\su\Desktop\大肥鱼项目\BAServer\report\_tmp\official_decoded_201\'

# 1) 列 shop 文件
Get-ChildItem $d -File | Where-Object { $_.Name -match 'shop' } | Select-Object Name,Length

# 2) 10002 响应顶层键
$j = Get-Content "$d`86_10002_api_shop_list.response.json" -Raw | ConvertFrom-Json
$j.inner.PSObject.Properties.Name

# 3) 全目录 grep
Get-ChildItem $d -Filter *.json | Select-String -Pattern 'ShopRecruits' -List | Select-Object Filename,LineNumber
Get-ChildItem $d -Filter *.json | Select-String -Pattern 'GachaRecruit' -List | Select-Object Filename,LineNumber

# 4) 10006 是否有独立报文
Get-ChildItem $d -File | Where-Object { $_.Name -match '10006|gacharecruit' }
Get-ChildItem $d -Filter *.json | Select-String -Pattern '"Protocol":10006' -List

# 5) 卡池条数与首条
$r = $j2.inner.ShopGachaRecruitListResponse   # $j2 = 02_1017_api_account_loginsync.response.json
@($r.ShopRecruits).Count
$r.ShopRecruits[0] | ConvertTo-Json -Compress
```

## 附录 B：本报告引用的文件（相对 `C:\Users\su\Desktop\大肥鱼项目\BAServer\`）

| 路径 | 用途 |
|---|---|
| `report\_tmp\official_decoded_201\86_10002_api_shop_list.request.json` | 10002 请求，`CategoryList=[38]` |
| `report\_tmp\official_decoded_201\86_10002_api_shop_list.response.json` | 10002 响应，7 个顶层键，无 `ShopRecruits` |
| `report\_tmp\official_decoded_201\02_1017_api_account_loginsync.request.json` | `SyncProtocols` 含 `10006` |
| `report\_tmp\official_decoded_201\02_1017_api_account_loginsync.response.json` | 内嵌 `ShopGachaRecruitListResponse.ShopRecruits`（529 条） |
| `report\_tmp\official_decoded_201\40_bluearchive_hosts.json` | 125 条 host 记录，`/api/shop/*` 只有 `/api/shop/list` |
| `report\_tmp\official_decoded_201\_timeline.txt` | 抓包时间线（204 行事件，窗口 04:30:54–04:34:32） |
| `work\ba\plan\20261119\SHOPLIST_CATEGORY38_ANALYSIS.md` | 既有客户端反编译侧分析（作为对照，非官方抓包证据） |
