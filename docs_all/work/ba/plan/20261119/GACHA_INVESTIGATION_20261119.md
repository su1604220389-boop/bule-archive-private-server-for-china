# 招募 / 抽卡界面故障 —— 调查汇总（2026-11-19）

- **客户端**：`com.RoamingStar.BlueArchive` 3.0.2（国服，Unity IL2CPP，免 root 重打包：仅改登录 SDK 与服务器地址，资源走官方 CDN）
- **服务端**：自建 Shittim 私服（`/www/wwwroot/ba_srv`，root@<SERVER_IP>）+ 桥（`/www/wwwroot/bapatch`）
- **调查窗口**：2026-11-19 00:00 – 02:00（Asia/Shanghai）
- **本文性质**：汇总。唯一写入文件就是本文件；其余全部只读，未碰服务器、未改代码。
- **编号约定**：`A#` = 已确证（客户端侧），`B#` = 已排除（服务端侧），`C#` = 未决，`E#` = 实验，`P#` = 坑。编号沿用今晚逐条结论的原始序号（1–20）。

---

## 0. 一句话现状

**招募界面进得去、页签也正常，但页签里的标题/说明/点数说明/底部按钮文字全部是红字 `No LocalizeKey`，十连按钮点下去毫无反应且恒显 `1,000`；服务端侧所有能影响这条链路的项（卡池清单、DTO 字段、语言/区域、响应壳、10006、10015、`ServerNotification:8`）已被逐项实测排除，故障点落在客户端本地取文案与本地按钮判据这两条路径上，而这两条路径都必须拿到客户端运行日志才能定论。**

---

## 1. 下一步唯一可行路径

**拿客户端运行日志（`logcat` / Bug report）。在此之前，任何继续改服务端数据或协议的动作都是在没有观测的情况下盲改。**

手机目前未连 adb、无线调试未开，所以这一步是人工前置动作，不是技术难题：

```text
# 前置：手机开「开发者选项 → USB 调试」（或「无线调试」配对，端口占位 5555）
adb devices                      # 必须看到设备且状态为 device
adb logcat -c                    # 清屏，保证复现窗口干净
adb logcat -v time > recruit_repro.log   # 开始记录
#   → 手机关闭客户端重开、登入、进招募界面、点一次十连按钮、开一次「注意事项」、开一次「选择成员」
#   → 停止记录（Ctrl+C）
adb bugreport ba_bugreport.zip   # 完整 Bug report（含 tombstones、dumpsys、包信息）
```

**判读目标（三个必看）**：

1. `No LocalizeKey` 前后的调用栈/上下文日志 —— 判断是「key 为 null/空」还是「key 有值但本地化表 hash 查不到」。
2. 十连按钮被禁用时的本地判据日志/异常 —— 判断是货币不足判定、免费次数判定、`SalePeriod` 判定，还是前置 `PickupSelection` 未完成判定。
3. 是否有 `Exception` / `MissingMethod` / `ArgumentNull`（IL2CPP 下常以 `Unity` tag 打印）。

**拿到日志后的分叉（假设，待日志证实，勿提前动手）**：
- 若日志显示「key 为空 / LocalizeKey 传空」→ 问题在客户端取 key 的那段代码，服务端改不动，需要转向重打包侧的二进制/资源层。
- 若日志显示「key 有值但 hash 查不到」→ 才轮到本地化表/语言槽，与 `LOCALIZE_KEY_DIFF.md` 的 key 空间比对照着看（注意：该文档已证明 532/532 全覆盖）。
- 若十连按钮日志显示某个资源/条件不足 → 回到服务端补对应状态（货币已足，`1,116,895` 青辉石，故优先看票券/免费次数/前置 flag）。

---

## 2. 总览

| 栏位 | 条目 | 编号 | 含义 |
|---|---|---|---|
| **已确证** | **7 条** | A1–A7 | 有偏移 / 行数 / 字节级证据，可直接复核 |
| **已排除** | **8 条** | B8–B15 | 服务端侧假设逐项实测被否，附证据文件 |
| **未决** | **5 条** | C16–C20 | 现象清楚、根因未定，禁止提前下结论 |
| 实验 | 10 项 | E1–E10 | 含一项**阴性单变量实验**（结论是否定证据） |
| 坑 | 10 条 | P1–P10 | 明确不要再走的路 |

---

## 3. 已确证（客户端侧）

### A1 — 红字来源是客户端二进制的字符串字面量，不是服务端数据
`[FF0000]No LocalizeKey` 是编进 IL2CPP 的 **C# 字符串字面量**（连颜色标记 `[FF0000]` 一起写死）。定位：`global-metadata.dat` 的 `stringLiteralData` 区偏移 **`0x000C2BAA`**，XOR key **`0x51`**，**dataIndex 599530**。
证据：`NOLOCALIZEKEY_ORIGIN.md`（解混淆副本 `report\_tmp\patch\md_deob.bin`，38,426,024 B）。

### A2 — `DUMMY` 不在任何一张表里，是客户端写死的兜底占位
在客户端 `ExcelDB.db` 全部 **398 张表**里检索 `DUMMY`：**0 命中**。⇒ 界面上的 `DUMMY` 不是表数据，是客户端本地兜底占位。
补充（同源结论）：`GACHA_CANDIDATE_LIST_V2.md` 结论速览明确 **3 个 `DUMMY` 页签 ≠ `90000000` / `99999999`**（这两条哨兵池字段完整、有卡面图、有本地化）。
证据：`NOLOCALIZEKEY_ORIGIN.md`、`GACHA_CANDIDATE_LIST_V2.md`。

### A3 — 客户端表与官方 Manifest 逐位一致（排除「表被换过/打包坏」）
`ExcelDB.db` = **160,534,528 B**，md5 **`824ce3a8bee2bb5ae36ada1ac95048f1`**，与官方 `TableManifest`（`/prodm39/Manifest/TableBundles/202611051826/TableManifest`）**逐位一致**。
证据：`NOLOCALIZEKEY_ORIGIN.md`、`LOCALIZE_KEY_DIFF.md`（均以此为同一数据源）。

**A3 补强（APK 层核对）**：**APK 里根本没有 `ExcelDB.db`** —— 重打包包 41,307 条目 / 官方包 41,312 条目，`.db`、`.sqlite`、`StreamingAssets`、`Excel*` 命中数**均为 0**，且 `TableCatalog.json` 自述 `"ExcelDB.db": {..., "isInbuild": false}`（明确声明不进包）；160 MB 的表也塞不进任何一个条目（除 `libil2cpp.so` 270,927,056 外最大条目 81,313,204）。⇒ 表**只能来自首次启动下载**，"重打包带了不一致的表"**在 APK 层被证伪**；本地两份客户端表副本（`data\ExcelDB.db`、`srv_live\...\tools\ExcelDB.db`）均是 160,534,528 B / 同 md5 ✅；`resources.arsc` sha256 `cd8943ae…9eecb86` 与历史常量一致；生产包 vs 官方包 **41,301 个条目内容完全相同**（仅 2 新增 / 7 删除 / 4 修改）。
证据：`APK_TABLE_INTEGRITY.md`。

### A4 — `ShopRecruitDBSchema` 实测 532 行；我方 529 条是「有 SalePeriod 的 529 行」
- 行数 **532**（我方下发 **529** 条 = 其中"有 `SalePeriod` 的 529 行"）。
- 字段：`Id` / `CategoryType` / `IsLegacy` / `OneGachaGoodsId` / `TenGachaGoodsId` / `SalePeriodFrom` / `SalePeriodTo` / `IsNewbie` / `IsOverrideSalePeriod` / `DirectPayInvisibleTokenId` / `SelectAbleGachaGroupId` / `SalePeriodDayParameter` / `GachaBannerPath`。
- **`SalePeriodFrom/To` 是 string**（形如 `2026-11-12 14:00:00`），**不是 ticks**。
证据：`OPEN_BANNERS_NOW.md`、`GACHA_CANDIDATE_LIST_V2.md`（532 行扫描表 `gacha_shoprecruit_scan.csv/.json`）。

### A5 — `LocalizeGachaShopDBSchema` 1,235 行：532 个招募 id 一条不缺
- **1,235** 行；532 个招募 id **全部有行，一条不缺**；另有 **703** 行是 5 位 legacy 段（50000–99999）。
- `5004670` 解出 **5 段**：`限时招募` / `限时招募！` / `美咲（泳装）（3★）招募概率提升！` / `选择招募10次…` / `2026/11/12 14:00~2026/11/26  13:59截止`。
- 方向 A（我方 id → 本地化）**差集为空**。
证据：`LOCALIZE_KEY_DIFF.md`（分析脚本 `work\ba\scripts\q_localize_keydiff.py`）。

### A6 — 关键差异：`GachaBannerPath` 的有无由 `CategoryType` 决定
| CategoryType | 行数 | 卡面图 |
|---|---|---|
| 5 (PickupGacha) | 260 | **0 张** |
| 19 (LimitedGacha) | 83 | **0 张** |
| 24 | 16 | **0 张** |
| 11 | 2 | **0 张** |
| 6 (NormalGacha) | 113 | **全有** |
| 23 (DirectPayGacha_DontUseGlobal) | 7 | **全有** |

此刻开放的 **10 个卡池**中，**5 个真限时/限定泳装池（`5004670`/`5004680`/`5004690`/`5004700`/`5004710`）全部无卡面图**；有图的 5 个是 `5004660` / `7000001` / `8000004` / `90000000` / `99999999`。
证据：`OPEN_BANNERS_NOW.md`（含逐池一句话文案表）、`GACHA_CANDIDATE_LIST_V2.md`。

### A7 — 客户端「开放期」判据极简，没有隐藏闸门
`ShopRecruitExcelExt.GetTimelinedShopRecruit`：`DateTime.Parse(From) <= now && DateTime.Parse(To) >= now` —— **闭区间、无额外闸门**；`IsLegacy` **全 532 行 false**。
证据：`OPEN_BANNERS_NOW.md`（引 `work\ba\srv_src\Schale\Excel\ShopRecruitExcelExt.cs:19-25`）。

---

## 4. 已排除（服务端侧，附证据）

### B8 — 卡池清单数据：我方 529 条 vs 官方真实抓包，逐条逐字段差异 = 0
日期格式、Id 区间、哨兵 `90000000` / `99999999` 全吻合。
证据：`OUR_VS_OFFICIAL_SHOPRECRUITS.md`（官方源 `report\_tmp\official_decoded_201\02_1017_api_account_loginsync.response.json`，我方 `our_shoprecruits_20261119.json`）。

### B9 — DTO 字段：客户端只需要 4 个，我方一个不缺
客户端 `ShopRecruitDB` 只有 4 个字段：`Id` / `SalesStartDate` / `SalesEndDate` / `UpdateDate` —— 我方 **4/4 全覆盖**；客户端招募 DTO 里**没有任何文本/本地化字段**。
证据：`CLIENT_SHOPRECRUIT_DTO_VS_OURS.md`。

### B10 — 单变量实验（阴性）：页签不由 `ShopRecruits` 驱动
把下发清单从 **529 条改成只剩 1 条 `5004670`** → 客户端页签**没有变少，反而多了一个**（新增「新手冲刺一」）。⇒ 招募列表/页签是**客户端本地拼的**。已回滚（`GachaRecruitBanners.cn.json` 恢复为 529 条 / 40,739 B / sha256 `3ac8385d77a2921932eedf934de83178f61a6c8c30b588c3ca64718f0c423c77`）。
证据：`BANNER1_DEPLOY.md`、`GACHA_CANDIDATE_LIST_V2.md`。

### B11 — `10006`：客户端从不请求，官方也不发
客户端**从不请求**协议 10006（`Shop_GachaRecruitList`）；卡池走 `LoginSync`(1017) **内嵌子包**，**官方抓包同样如此**，不是我们的 bug。官方抓包里也没有独立的 10006。进招募界面时客户端只发 `POST /api/shop/list`（`CategoryList=[38]`），该窗口 10006 命中 **0 次**。
证据：`SHOPLIST_CATEGORY38_ANALYSIS.md`、`OFFICIAL_SHOPLIST_SHOPRECRUITS_CHECK.md`。

### B12 — 语言/区域：双方都不发，服务端也没有 Cn 槽
我方**一个语言字段都没发**，官方也没发；`LoginSync` / `Account_Auth` / `/api/state` **全 0 命中**。服务端 `Language` 枚举只有 `Kr/Jp/Th/Tw/En`（**没有 Cn 槽**），且只用于邮件文案。
证据：`LANGUAGE_FIELD_DIFF.md`。

### B13 — `ServerNotification: 8` 不是错误码
`8` = `HasUnreadMail`（全局邮箱红点），由网关统一叠加；**官方也只在邮件协议上带 8**。
证据：`ENVELOPE_ALIGN.md`、`ENVELOPE1_DEPLOY.md`（已收窄到邮件类协议 8000–8004）。

### B14 — `10015` 回显这条路原理上不通，且与抽卡按钮无关
响应是空壳；客户端**从不回读 10014（实测 0 次）**，`10015` 重试 **39 次**（均 200 / 384 B）；**两侧 DTO 都 0 字段** ⇒「加回显」不可能实现。该功能与抽卡按钮无关（官方抽卡不需要先选成员）。
证据：`PICKSEL_LIVE_TRACE.md`、`PICKSEL_FIX.md`（停手报告：两侧 DTO 定义均无字段）、`OFFICIAL_PICKSEL_PROTOCOL.md`（官方抓包内 10014/10015 一条都没有，无法观测官方怎么回）。

### B15 — 出口道具过滤 / Item_List 中继 / Shop_List NRE 均已上线且正常
`/api/item/list` 返回 **53 件真实道具**（含 `6998=100`）；`Shop_List` 无 `CategoryList` 时从 500 NRE 变为 200 + `ShopInfos: []`。
证据：`EXPORTFILTER_DEPLOY.md`、`ITEMLIST_RELAY_V2.md`、`SHOPLIST_NRE_FIX.md` / `SHOPLIST_NRE_DEPLOY.md`。

---

## 5. 未决（现象清楚，根因未定 —— 不要提前下结论）

### C16 — 页签名正常，页签内文案全红
页签名正常（「新手冲刺一」「新手冲刺二」「3★自选招募」），但**页签里面的标题 / 说明 / 点数说明 / 底部按钮文字全是红字**；唯独**期间那一行是正常的**：`2026/11/12 14:00~2026/11/26 13:59截止`。
→ 同一屏内「部分文案能取到、部分取不到」，说明不是整条本地化链路全断。

### C17 — 十连按钮完全无反应
点下去**连本地提示都不弹** ⇒ 是客户端**本地判据**在点击前就把按钮禁用了。按钮**恒显示 `1,000`**，与余额无关（该账号上有 **1,116,895 青辉石**）。

### C18 — 客户端拿得到人物数据，坏的只是「文本」
成员信息可以打开；**`DUMMY` 页签也能打开且显示的正确人物**（与左侧动画一致）⇒ 卡池的人物数据链路通畅。

### C19 — 「注意事项」空白；「选择成员」只有档案招募能进
「注意事项」点开是**空白**；「选择成员」只有 `90000000`（档案招募）能进去，选完弹「正在加载中」→ 消失 → **没选上**（与 B14 的 10015 空壳响应一致）。

### C20 — 结论边界：必须拿客户端日志
服务端**能影响到的都已排除**（数据 / 清单 / 语言 / 字段 / 壳）。红字只可能来自**客户端本地取文案**这条路径。
**要定论必须拿到客户端运行日志（logcat / Bug report）**；目前手机未连 adb、无线调试未开。→ 见 §1。

---

## 6. 做过的实验与结果

| # | 实验 | 做法 | 结果 | 结论性质 | 证据 |
|---|---|---|---|---|---|
| E1 | **单变量：卡池清单 529→1** | 只留 `5004670`，其余全删 | 页签**没变少反而多一个**（新增「新手冲刺一」） | **否定证据（阴性）**：页签不由 `ShopRecruits` 驱动 | `BANNER1_DEPLOY.md` |
| E1b | E1 回滚 | 恢复原清单 | sha256 恢复 `3ac8385d…`，登录链路正常 | 已复原 | `BANNER1_DEPLOY.md` |
| E2 | 卡池候选清单产出 V2 | 全库扫描 + 严格筛选 | 严格筛选 3 条候选；`DUMMY` 全库 0 命中；532 行扫描表落盘 | 产出可用，但**不是修复手段**（见 P1） | `GACHA_CANDIDATE_LIST_V2.md` |
| E3 | 响应壳对齐官方 | `SessionKey` 全量回显 + `ServerNotification` 收窄到邮件类协议 | 部署成功、自检全过、判 KEEP | 壳差异已消除；**招募界面状态未变**（C16/C17 仍成立） | `ENVELOPE_ALIGN.md`、`ENVELOPE1_DEPLOY.md` |
| E4 | 10015 回显修复 | 先查 DTO 定义 | **停在第一步未动代码**：两侧 DTO 均 0 字段 | 技术上不可行（否定） | `PICKSEL_FIX.md` |
| E5 | 「服务端发错语言字段」假设 | 递归扫 `LoginSync`/`Account_Auth`/`/api/state` 语言类键 | 双方 **0 命中**，服务端无 Cn 槽 | **假设不成立（否定）** | `LANGUAGE_FIELD_DIFF.md` |
| E6 | 客户端 DTO 字段缺口 | 逐字段比对客户端 `ShopRecruitDB` vs 我方 | 4/4 全覆盖，无多发无漏发 | 假设不成立（否定） | `CLIENT_SHOPRECRUIT_DTO_VS_OURS.md` |
| E7 | `Shop_List(CategoryList=[38])` 只回 2 个商品 | 查 `ShopCategoryType` 与 `ShopExcel` | `38 = CafeSummonTicket`，**不是抽卡分类**；`ShopListResponse` 本身无 `ShopRecruits` 字段 | 解释性（否定「该接口该带卡池」） | `SHOPLIST_CATEGORY38_ANALYSIS.md` |
| E8 | 10014/10015 线上实测追踪 | nginx + wire + 桥日志 | 10015 发 39 次全 200；10014 **回读 0 次** | 观测事实 | `PICKSEL_LIVE_TRACE.md` |
| E9 | 外部调研（有没有人踩过同一坑） | 纯联网检索 | **没有找到直接答案**；4 条线索 + 5 条推论级证据，其中 3 条可改排查方向 | 无现成答案 | `EXTERNAL_RESEARCH_GACHA_UI.md` |
| E10 | 官方流量核对 | 解码官方 HAR（109 对 RPC） | 官方 Shop 家族只有 `10002` 一条，gacha 族一条都没有 | 否定「官方靠 10006 下发卡池」 | `OFFICIAL_SHOPLIST_SHOPRECRUITS_CHECK.md`、`OFFICIAL_PICKSEL_PROTOCOL.md` |

> **E1 的性质要写死**：它是一次**阴性实验**，结论是**否定证据**——「页签由我方下发的卡池清单决定」这个假设**被实验否掉**，不是「修了一半」。当晚 00:17–00:23 还有一次同类事故（清单 529→5 引发登录失败，已回滚），见 `GACHA_CLEAN5_INCIDENT.md`。

---

## 7. 不要重复的坑

- **P1 · 别再试图靠改下发的卡池数据修页签。** E1 阴性实验已否掉：529→1 条，页签反而多一个。页签是客户端本地拼的。
- **P2 · 别再加 10015 回显。** 两侧 DTO 都是 0 字段，加什么都不会被客户端读（`PICKSEL_FIX.md` 已停手）；且该功能与抽卡按钮无关。
- **P3 · 别改 `ServerNotification: 8`。** 它是 `HasUnreadMail` 全局红点，官方也只在邮件协议上带 8；`ENVELOPE_ALIGN` 已收窄，别再扩回去当错误码用。
- **P4 · 别再查 10006。** 客户端从不请求，官方抓包里也没有；卡池就在 `LoginSync`(1017) 内嵌子包里。
- **P5 · 别再查语言/区域字段。** 双方都不发，服务端 `Language` 枚举没有 Cn 槽，且只用于邮件文案。
- **P6 · 别再怀疑 `ExcelDB.db` 被换过/打包坏/重打包弄丢。** md5 与官方 `TableManifest` 逐位一致（A3）；而且 APK 里**两个包都没有**这个文件（`isInbuild: false`，靠首启下载），41,301 个条目与官方逐字节相同（`APK_TABLE_INTEGRITY.md`）。
- **P7 · 别再怀疑 `LocalizeGachaShop` 缺行或 key 空间错位。** 532/532 全覆盖，方向 A 差集为空（A5）；`No LocalizeKey` 的字面量在 metadata 里（A1），不是「key 换了」。
- **P8 · 别把「无卡面图」当病因直接去补数据。** A6 只是**相关性**：此刻 5 个坏池恰好都无图，但 C18 已证明客户端拿得到人物数据。没有日志前，改 `GachaBannerPath` 属于盲改。
- **P9 · 别再补 `ShopRecruitDB` 字段。** 客户端只要 4 个，4/4 全覆盖（B9）。
- **P10 · 任何清单/表改动必须回滚并记 sha256。** 今晚已出过两次事故（`GACHA_CLEAN5_INCIDENT.md` 登录失败、`EXPORT_FILTER.md` 里 `UniqueId=90070000` 导致登录死循环）。改前备份、改后回滚验证，一步都不能省。

---

## 8. 数据速查（复核用锚点）

| 项 | 值 |
|---|---|
| `ExcelDB.db` | 160,534,528 B / md5 `824ce3a8bee2bb5ae36ada1ac95048f1` / 398 表 |
| 官方表清单 | `/prodm39/Manifest/TableBundles/202611051826/TableManifest` |
| `No LocalizeKey` 字面量 | `stringLiteralData` 偏移 `0x000C2BAA`，XOR `0x51`，dataIndex `599530` |
| `ShopRecruitDBSchema` | 532 行（可下发 529 = 有 `SalePeriod` 的 529 行） |
| `LocalizeGachaShopDBSchema` | 1,235 行（532 招募 id 全覆盖 + 703 条 legacy 5 位段 50000–99999） |
| 客户端 `ShopRecruitDB` DTO | 4 字段：`Id` / `SalesStartDate` / `SalesEndDate` / `UpdateDate` |
| 开放期判据 | `Parse(From) <= now <= Parse(To)`，闭区间，无闸门；`IsLegacy` 全 false |
| 此刻开放卡池 | 10 个；有图 5（`5004660`/`7000001`/`8000004`/`90000000`/`99999999`）；无图 5（`5004670`/`5004680`/`5004690`/`5004700`/`5004710`） |
| APK 表完整性 | 两个 APK 内 `.db` 命中 0（`isInbuild:false`）；生产包 vs 官方包 41,301 条目内容相同；`resources.arsc` sha256 `cd8943ae…9eecb86` |
| 账号余额 | 青辉石 `1,116,895`（按钮仍恒显 `1,000` ⇒ 与余额无关） |
| 已回滚实验 | `GachaRecruitBanners.cn.json` 恢复后 sha256 `3ac8385d…` |

---

## 9. 今晚产出文档清单

目录：`work\ba\plan\20261119\`

| 文件名 | 一句话内容 |
|---|---|
| [`NOLOCALIZEKEY_ORIGIN.md`](<work/ba/plan/20261119/NOLOCALIZEKEY_ORIGIN.md>) | 红字 `[FF0000]No LocalizeKey` 的产地取证：metadata 偏移 `0x000C2BAA` / XOR `0x51` / dataIndex `599530`，并证明 `DUMMY` 全库 0 命中 |
| [`LOCALIZE_KEY_DIFF.md`](<work/ba/plan/20261119/LOCALIZE_KEY_DIFF.md>) | 招募界面 `No LocalizeKey` 的 key 空间比对：532/532 全覆盖、方向 A 差集为空、703 条 legacy 段是历史遗留 |
| [`OPEN_BANNERS_NOW.md`](<work/ba/plan/20261119/OPEN_BANNERS_NOW.md>) | 客户端表口径下「此刻处于开放期」的 10 个卡池逐行清单（含卡面图有无、本地化段数、一句话文案）与开放期判据 |
| [`GACHA_CANDIDATE_LIST_V2.md`](<work/ba/plan/20261119/GACHA_CANDIDATE_LIST_V2.md>) | 卡池候选清单 V2：532 行扫描表落盘、严格筛选出 3 条候选、`DUMMY` 页签 ≠ `90000000`/`99999999` |
| [`RECRUIT_LOG_FORENSICS_20261119_0124.md`](<work/ba/plan/20261119/RECRUIT_LOG_FORENSICS_20261119_0124.md>) | 00:50–01:30 招募界面异常的服务端日志取证（nginx / wire / 桥 / 应用日志，全程只读） |
| [`OUR_VS_OFFICIAL_SHOPRECRUITS.md`](<work/ba/plan/20261119/OUR_VS_OFFICIAL_SHOPRECRUITS.md>) | 我方 vs 官方 1017 内嵌 `ShopRecruits` 逐条逐字段对比：差异 0，唯一差别在子包外层壳 |
| [`LOGINSYNC_ENVELOPE_DIFF.md`](<work/ba/plan/20261119/LOGINSYNC_ENVELOPE_DIFF.md>) | 1017 整份响应结构差异：子包顺序、每包少 4 个空壳键、子包 `Protocol` 值不同 |
| [`SHOPLIST_CATEGORY38_ANALYSIS.md`](<work/ba/plan/20261119/SHOPLIST_CATEGORY38_ANALYSIS.md>) | `Shop_List(CategoryList=[38])` 取证：`38 = CafeSummonTicket` 不是抽卡分类，该 DTO 本身没有 `ShopRecruits` |
| [`PICKSEL_LIVE_TRACE.md`](<work/ba/plan/20261119/PICKSEL_LIVE_TRACE.md>) | 「选择成员」线上追踪：10015 发 39 次全 200 / 384 B 空壳，10014 回读 0 次 |
| [`PICKSEL_FIX.md`](<work/ba/plan/20261119/PICKSEL_FIX.md>) | 10015 回显修复的**停手报告**：两侧 DTO 均 0 字段，未动代码 |
| [`OFFICIAL_PICKSEL_PROTOCOL.md`](<work/ba/plan/20261119/OFFICIAL_PICKSEL_PROTOCOL.md>) | 官方抓包里 10014/10015 到底怎么回：整份抓包内一条都没有，无法观测 |
| [`LANGUAGE_FIELD_DIFF.md`](<work/ba/plan/20261119/LANGUAGE_FIELD_DIFF.md>) | 语言/区域字段对照：我方与官方都 0 命中，服务端 `Language` 枚举无 Cn 槽 ⇒ 假设不成立 |
| [`CLIENT_SHOPRECRUIT_DTO_VS_OURS.md`](<work/ba/plan/20261119/CLIENT_SHOPRECRUIT_DTO_VS_OURS.md>) | 客户端 `ShopRecruitDB` 4 字段 vs 我方实际下发：4/4 全覆盖、无多发无漏发 |
| [`EXTERNAL_RESEARCH_GACHA_UI.md`](<work/ba/plan/20261119/EXTERNAL_RESEARCH_GACHA_UI.md>) | 外部调研：网上没有同一坑的现成答案，只有 4 条线索 + 5 条推论（其中 3 条可改排查方向） |
| [`ENVELOPE_ALIGN.md`](<work/ba/plan/20261119/ENVELOPE_ALIGN.md>) | 响应壳对齐官方：`SessionKey` 全量回显 + `ServerNotification` 收窄到邮件类协议（只改代码 + 本地构建） |
| [`ENVELOPE1_DEPLOY.md`](<work/ba/plan/20261119/ENVELOPE1_DEPLOY.md>) | ENVELOPE1 部署与自检：部署成功、自检全过、判 KEEP |
| [`BANNER1_DEPLOY.md`](<work/ba/plan/20261119/BANNER1_DEPLOY.md>) | 卡池清单 529→1 条的单变量实验部署与验证（阴性实验，已回滚 sha256 `3ac8385d…`） |
| [`APK_TABLE_INTEGRITY.md`](<work/ba/plan/20261119/APK_TABLE_INTEGRITY.md>) | APK 表完整性核对：两个包里都没有 `ExcelDB.db`（`isInbuild:false`，表靠首启下载），41,301 条目与官方逐字节相同，`resources.arsc` sha256 与历史常量一致 |

### 9.1 同一目录下其它相关文档（非必列，但今晚同批产出）

| 文件名 | 一句话内容 |
|---|---|
| [`EXPORT_FILTER.md`](<work/ba/plan/20261119/EXPORT_FILTER.md>) | 出口道具过滤（EXPORTFILTER v1）设计与 5 处改动：`UniqueId=90070000` 事故的根因与堵法 |
| [`EXPORTFILTER_DEPLOY.md`](<work/ba/plan/20261119/EXPORTFILTER_DEPLOY.md>) | 出口过滤部署记录：PASS，线上逐字节零变化 |
| [`ITEMLIST_RELAY_V2.md`](<work/ba/plan/20261119/ITEMLIST_RELAY_V2.md>) | `Item_List(4000)` 转发恢复 v2：53 件真实道具、5,016 B |
| [`SHOPLIST_NRE_FIX.md`](<work/ba/plan/20261119/SHOPLIST_NRE_FIX.md>) | `Shop_List` 500 空指针修复（`ShopManager.GetShopList`，+11/−1 行） |
| [`SHOPLIST_NRE_DEPLOY.md`](<work/ba/plan/20261119/SHOPLIST_NRE_DEPLOY.md>) | 该 NRE 修复的部署记录：500 → 200 + `ShopInfos: []`，11 分类数据不受影响 |
| [`OFFICIAL_SHOPLIST_SHOPRECRUITS_CHECK.md`](<work/ba/plan/20261119/OFFICIAL_SHOPLIST_SHOPRECRUITS_CHECK.md>) | 官方抓包核对：`Shop_List`(10002) 带不带 `ShopRecruits`、`10006` 在官方流量里存不存在 |
| [`GACHA_CLEAN5_DEPLOY.md`](<work/ba/plan/20261119/GACHA_CLEAN5_DEPLOY.md>) | 卡池清单收敛到 5 个的部署记录（PASS，10006 返回 5 条对齐） |
| [`GACHA_CLEAN5_INCIDENT.md`](<work/ba/plan/20261119/GACHA_CLEAN5_INCIDENT.md>) | 事故记录：清单 529→5 导致登录失败，已回滚，根因代码待修 |
| [`GACHA_CLIENTROSTER_PLAN.md`](<work/ba/plan/20261119/GACHA_CLIENTROSTER_PLAN.md>) | 招募界面不可用的初期方案稿（方案阶段，未改任何代码，已被今晚实测取代） |

---

## 10. 复核须知

1. 本文件所有结论均来自上述 27 份只读报告（本文件以外）与本地明文数据（`ExcelDB.db`、`global-metadata.dat` 解混淆副本、官方 HAR 解码目录、APK 中央目录）。
2. 任何「现象」类结论（C16–C19）都是**界面观察**，未经客户端日志确认；不得据此推导根因。
3. 下一轮动作只认 §1：**先拿日志，再动手**。没有日志的新改动，一律按 P10 流程（备份 → 改 → 回滚验证 → 记 sha256）。
