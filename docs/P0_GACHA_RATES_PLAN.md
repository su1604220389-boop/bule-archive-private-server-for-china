# P0 · 抽卡概率可配置化（管理站可调 + 一键恢复默认）方案

> 2026-11-19　·　**只写方案，未改任何文件、未编译、未部署、未碰服务器**
> 只读取证：`work\ba\srv_src\Shittim-Server\`、`work\ba\srv_src\Schale\`、`work\ba\srv_live\20261118_0059\ba_cardadmin\`、`work\ba\server\deploy\_panel\`
> 前置报告：`work\ba\plan\20261119\GACHA_RNG_ANALYSIS.md`（182 行，已通读；本方案不重复它的推导，只补它没查的 4 件事）

本阶段范围（用户已定）：**只做 P0 = 让「出彩概率」可通过管理站调整 + 一键恢复默认。**
不做：消耗校验（P1）、90004 运营数据进管理站（P2）、其它名单类配置（P3）。

---

## 0. 先补的 4 件源码事实（任务要求逐条确认）

### 0.1 `customRates` 的入参形态 —— **没有分类维度，只有 3 个数字**

```csharp
// Core\GachaCommand.cs:9   （★ 注意：是 Core 命名空间下这个，不是 Commands 下那个）
private static Dictionary<long, double>? _customRates;
// :18
public Dictionary<string, double>? custom_rates { get; set; }
// :55-73  从 JSON 的 "ssr"/"sr"/"r" 三个键装进 long 键的字典
_customRates[3] = ssrRate;   // 3 = 三星
_customRates[2] = srRate;    // 2 = 二星
_customRates[1] = rRate;     // 1 = 一星
```

- **类型**：`Dictionary<long, double>`，key 只有 `3 / 2 / 1`，value 是**百分数**（`ShopManager.cs:195-197` 里 `* 10` 转成千分比再比较）。
- **没有 `Dictionary<ShopCategoryType, ...>`**：**一份字典对全部池类型生效**，不含 `rateUpSSR / fesSSR / permanentSSR` 的拆分。
- **构造者有两个，且互不相通**（命名陷阱，必须写清）：

| 构造者 | 文件 | 何时写入 | 谁读它 | 重启后 |
|---|---|---|---|---|
| `Shittim_Server.Core.GachaCommand` | `Core\GachaCommand.cs` | 从 `/www/wwwroot/gacha_config.json` 读（`_lastConfigCheck` 5s TTL） | **`ShopManager.cs:186` 唯一读它** | 文件在就还在 |
| `Shittim.Commands.GachaCommand` | `Commands\GachaCommand.cs:22` | 控制台 `!gacha rate ssr 5` 写内存静态字典（`:136`、`:140`、`:144`） | **`ShopManager` 不读它**（`GetCustomRates()` 在 `:220`，但调用方是控制台自己的 `settings` 子命令） | **丢**（纯内存） |

⇒ 结论：**当前真正能影响出货的是 `gacha_config.json` 这一个文件**，控制台 `!gacha rate` 对正式抽卡无效（除非走 `POST /api/admin/command {Command:"gacha rate ssr 5"}`，那条命令只改内存、改的是没人读的那份字典）。

### 0.2 每次请求现算还是启动缓存 —— **5 秒热加载，改文件不用重启**

```csharp
// Core\GachaCommand.cs:11-12
private static DateTime _lastConfigCheck = DateTime.MinValue;
private static readonly TimeSpan ConfigCacheTime = TimeSpan.FromSeconds(5);
// :22-27
private static void LoadConfigIfNeeded()
{
    if (DateTime.UtcNow - _lastConfigCheck < ConfigCacheTime) return;   // 5s 内不重读
    _lastConfigCheck = DateTime.UtcNow;
    ...
}
// :97-101
public static Dictionary<long, double> GetCustomRates() { LoadConfigIfNeeded(); return _customRates ?? new(); }
```

而且调用点在**每抽循环内部**：

```csharp
// ShopManager.cs:185-186
var randomNumber = Random.Shared.NextInt64(1000);
var customRates = Core.GachaCommand.GetCustomRates();     // ← 循环里，每抽都调
```

⇒ **改配置文件最迟 5 秒后生效，不需要重启服务端。** 这是本项目已经存在的成熟机制（`worldraid_*.json`、`event_schedule.json`、`server_notice.json` 同款写法）。P0 沿用即可，不必新造热加载。

### 0.3 custom 分支怎么被选中 —— **只看一个条件：字典非空**

```csharp
// ShopManager.cs:193
if (customRates.Count > 0)
{
    ...  // 206-222：正确的累加阈值
    continue;
}
// 225-256：否则走"代码常量 + 绝对阈值"阶梯
```

- **选中条件与池类型完全无关**：只要 `gacha_config.json` 里 `custom_rates` 有任意一项，**所有池（常驻/Pickup/Limited/Fes/选择券）一起被接管**。
- 不选中的条件：文件不存在 / `custom_rates` 为 null / 空字典（`Core\GachaCommand.cs:35-41`、`:75-79`）。
- ⚠️ 两个必须知道的后果（决定 P0 不能直接复用这条路径）：
  1. **custom 分支没有十连保底**：`206-222` 整段没有 `i == guaranteedSRIndex` 判断，走了 custom 就没有"第 10 抽保底 2★"。
  2. **custom 分支把 3★ 池压平**：`208-210` 把 `ssrCharacterList + rateUpChar + otherRateUpList` 拼成一个列表再均匀抽 ⇒ UP 角色的实际概率变成 `1/列表长度`，**无法表达"UP 0.7% / 常驻 2.3%"这种拆分**。

### 0.4 单抽（10001/10005/10016）是不是同一个函数 —— **是，一份配置全入口共用**

| 协议 | 处理器 | 行号 | 是否走 `CreateTenGacha` |
|---|---|---|---|
| `Shop_BuyGacha`(10001) | `BuyGacha` | `ShopHandler.cs:277-303`（`:290` `Cost = null`，`:294` 调用） | ✅ |
| `Shop_BuyGacha2`(10005) | `BuyGacha2` | `:305-353`（`:317` `Cost = null`，`:324` 调用） | ✅ |
| `Shop_BuyGacha3`(10008) | `BuyGacha3` | `:355-422`（`:383` 调用） | ✅ |
| `Shop_PickupSelectionGachaBuy`(10016) | `PickupSelectionGachaBuy` | `:468-…`（`:503` 调用） | ✅ |
| `Audit_GachaStatistics`(5) | `ShopManager.SimulateGacha` | `ShopManager.cs:296-380` | ❌ **独立实现**，`:334` 也调 `InitializeGachaRates`，但阈值阶梯是 `:350-377` 的另一份（且保底用 `i % 10`，`:373`） |

`gachaAmount` 全部由 `ConsumeCurrency` 决定（`ShopManager.cs:47-75`）：`Cost == null` → 10（`:50`、`:53-58`，且不扣费）；货币 → `Amount / 120`（`:65`）；券 → `GetGachaAmountByItem`（`:66`）。

⇒ **一份配置可以覆盖 10001/10005/10008/10016 四个入口**；但 `SimulateGacha`（客户端"概率说明/统计"页）是**第二份阈值代码**，P0 必须同步改，否则面板改了率、统计页还是旧账（见 §7 风险⑥）。

---

## 1. 一句话方案 + 改动面清单

**一句话：** 在 `GachaService.InitializeGachaRates()` 之外加一层「`ShopCategoryType` → 4 个千分比」的配置文件（`Data/gacha_rates.json`，沿用现成的 5 秒 TTL 热加载，**默认值仍由代码常量现算、不另存**），把 `ShopManager.CreateTenGacha` 的 `225-256` 绝对阈值阶梯改成**累加阈值**，并新增 4 个 `api/admin/gacha/rates*` 端点，PHP 面板加一页 `pages/gacha.php` 做表格编辑 + 分项/全局恢复默认 + 快照回滚。

### 改动面清单

| # | 文件 | 动作 | 预计行数 |
|---|---|---|---|
| 1 | `Services\GachaRatesConfig.cs` | **新建**：Schema 类、加载器（5s TTL + mtime）、校验、clamp、默认值合并、快照读写 | +170 |
| 2 | `Services\ShopManager.cs` | **改** `225-256` 阶梯 → 累加阈值；`296-380` `SimulateGacha` 同步；`:160` 取率改走新入口 | ~45 改 / +12 净增 |
| 3 | `Services\GachaService.cs` | `InitializeGachaRates` **数值一行不改**，仅加注释标明"这是唯一默认值真源" | +4 注释 |
| 4 | `Controllers\ManagementController.cs` | 新增 4 个端点（GET/POST rates、GET snapshots、POST rollback）；旧 `gacha/config` 两个端点**保持原样不动** | +165 |
| 5 | `Data\gacha_rates.json` | **新建**（带完整默认值） | +30 |
| 6 | `Shittim-Server.csproj` | 加 `<None Update="Data\gacha_rates.json">` + `CopyToOutputDirectory` | +4 |
| 7 | `pages\gacha.php`（PHP 面板） | **新建** | +240 |
| 8 | `inc\ba.php` | 加 `ba_gacha_rates_get/set/rollback/snapshots` 四个薄封装 | +40 |
| 9 | `inc\helpers.php` | `nav_items()` 加 1 行导航 | +1 |
| 10 | `assets\app.css` | 追加 `.rate-tbl` / `.rate-sum` / `.rate-bad` 几条规则 | +18 |

**合计：服务端 5 个文件（1 新建 .cs、1 新建 json）+ csproj；面板 4 个文件（1 新建 .php）。约 690 行，其中净新代码 ~600 行。**

**要不要重启：**
- **改概率值 → 不用重启**（5s 热加载，§3）。
- **部署这次改动本身 → 要重启一次**（改了 DLL）。按 `_panel\PANEL_MERGE_20261117.md §4.1` 的现场记录，重启必须 `tmux kill-session` + `new-session`，**会踢掉当时所有在线玩家**，建议挑维护窗口。

---

## 2. 配置文件设计 `Data/gacha_rates.json`

### 2.1 完整 Schema

```
文件: <AppContext.BaseDirectory>/Data/gacha_rates.json
      ⇒ 线上 = /www/wwwroot/ba_srv/Data/gacha_rates.json
      （与 ShopHandler.cs:88 的 Data\GachaRecruitBanners.cn.json 同一根；★ 不要沿用 gacha_config.json 的
        AppContext.BaseDirectory/".." 写法，那个落在 /www/wwwroot/gacha_config.json，两个不同根）
编码: UTF-8 无 BOM；写入用"临时文件 + 原子 move"
```

| 字段 | 类型 | 必填 | 取值域 | 单位 | 说明 |
|---|---|---|---|---|---|
| `$schemaVersion` | int | 否 | `1` | — | 缺省按 1 处理；未来加字段用 |
| `categories` | object | **是** | 见 2.2 | — | key = `ShopCategoryType` 枚举名，另加保留键 `default` |
| `categories.<key>.rateUpSSR` | int | 否 | `0..1000` | 千分比（`1` = 0.1%） | UP 角色专属区间宽度 |
| `categories.<key>.fesSSR` | int | 否 | `0..1000` | 千分比 | 非 UP 的 Fes 限定角色区间宽度 |
| `categories.<key>.permanentSSR` | int | 否 | `0..1000` | 千分比 | 常驻 3★ 区间宽度（会自动排除 `rateUpChar`） |
| `categories.<key>.SR` | int | 否 | `0..1000` | 千分比 | 2★ 区间宽度 |
| `categories.<key>.limitedSSR` | int | 否 | `0..1000` | 千分比 | **可选**，对应代码里一直为 0、从未被配过的 `limitedSSRRate`（`GachaService.cs:31`、`ShopManager.cs:242`）。默认 `0`，不给也行 |

**硬约束：** 同一组 `rateUpSSR + fesSSR + permanentSSR + SR + limitedSSR ≤ 1000`。
剩下的 `1000 - 总和` 自动成为 1★ 区间，**不需要也不允许单独配 R**。

**缺省语义：**
- 缺字段 → 该字段用代码默认值（不是 0）。
- 缺整个 `categories.<key>` → 整组用代码默认值。
- 文件不存在 / JSON 解析失败 / 校验失败 → **整份回落代码默认值**，并在日志与 `GET` 响应的 `valid:false` 里暴露。
- 未知 key（比如写了 `"Typo"`）→ 忽略 + 日志警告，不阻塞。

### 2.2 按 `ShopCategoryType` 分组（本文件只认这些桶）

`ShopCategoryType` 定义在 `Schale\FlatData\ShopCategoryType.cs:8-51`。抽卡相关的取值与落桶：

| `ShopCategoryType` | 值 | 落桶 | 说明 |
|---|---|---|---|
| `PickupGacha` | 5 | `PickupGacha` | 活动 UP 池 |
| `NormalGacha` | 6 | `NormalGacha` | 常驻/普通池 |
| `PointGacha` | 7 | `default` | 现无专属分支，等同 Pickup 语义 |
| `EventGacha` | 8 | `default` | 同上 |
| `TutoGacha` | 11 | `default` | 新手池（**注意 `TicketGacha` 的 `isSelector` 不覆盖它**） |
| `RecruitSellection` | 12 | `default` | 选择招募 |
| `LimitedGacha` | 19 | `LimitedGacha` | 限定池 |
| `TicketGacha` | 22 | `TicketGacha` | 自选券，`isSelector = true`（`GachaService.cs:44-46`），四个率**都不参与 roll** |
| `DirectPayGacha_DontUseGlobal` | 23 | `default` | 名字已注明不要用 |
| `FesGacha` | 24 | `FesGacha` | Fes 池 |
| `BeforehandGacha` | 32 | `default` | 先行池 |
| `GlobalSpecialGacha` | 34 | `default` | |
| `SelectPickupGacha` | 35 | `default` | 选择招募（UP） |
| `SelectPickupFesGacha` | 39 | `default` | ⚠ 现有 `switch` 不认它 ⇒ **它按 Pickup 算，不按 Fes 算** |
| `SelectPickupLimitedGacha` | 40 | `default` | ⚠ 同上 |

**查找顺序**：精确匹配 `categories[枚举名]` → 不中则 `categories["default"]` → 再不中则代码默认值。
⇒ 上面标 ⚠ 的 39/40 如果希望按 Fes 算，**不用改代码**，直接在 JSON 里给 `"SelectPickupFesGacha": {...}` 建独立 key 即可（schema 天然支持）。

### 2.3 完整默认值示例（值 = 当前代码常量，逐字段对照）

```json
{
  "$schemaVersion": 1,
  "_unit": "per-mille (1 = 0.1%); sum of one group must be <= 1000; missing = code default",
  "categories": {
    "NormalGacha":  { "rateUpSSR": 0, "fesSSR": 0, "permanentSSR": 30, "SR": 185 },
    "PickupGacha":  { "rateUpSSR": 7, "fesSSR": 0, "permanentSSR": 23, "SR": 185 },
    "LimitedGacha": { "rateUpSSR": 7, "fesSSR": 0, "permanentSSR": 23, "SR": 185 },
    "FesGacha":     { "rateUpSSR": 7, "fesSSR": 9, "permanentSSR": 44, "SR": 185 },
    "TicketGacha":  { "rateUpSSR": 0, "fesSSR": 0, "permanentSSR": 0,  "SR": 0   },
    "default":      { "rateUpSSR": 7, "fesSSR": 0, "permanentSSR": 23, "SR": 185 }
  }
}
```

对照来源：`Services\GachaService.cs:29-57`

| 组 | `rateUpSSR` | `fesSSR` | `permanentSSR` | `SR` | 和 |
|---|---|---|---|---|---|
| `NormalGacha` | 0 | 0 | **30**（`:35`） | **185**（`:36`） | 215 |
| `PickupGacha` | **7**（`:50`） | 0 | **23**（`:51`） | **185**（`:52`） | 215 |
| `LimitedGacha` | 7（`:50`，`case` 共用） | 0 | 23（`:51`） | 185（`:52`） | 215 |
| `FesGacha` | **7**（`:39`） | **9**（`:40`） | **44**（`:41`） | **185**（`:42`） | 245 |
| `TicketGacha` | 0 | 0 | 0 | 0 | 0（`isSelector`，不参与） |
| `default` | 7 | 0 | 23 | 185 | 215 |

### 2.4 ⚠️ 行为变更（必须先让用户拍板）

改成**累加语义**后，`Pickup` 与 `Fes` 的实际 3★ 率会**变高**。以下是**按区间**的精确对照（不是只看总数）：

| 池 | 区间 | 现状（绝对阈值，`ShopManager.cs:225-256`） | 改用累加后 | 差异 |
|---|---|---|---|---|
| **Normal** | 3★ 合计 | `[0,30)` = **3.0%** | **3.0%** | **无变化** ✅ |
| | 2★ | 18.5% | 18.5% | 无 |
| **Pickup / Limited** | UP 角色 | `[0,7)` = 0.70% | `[0,7)` = 0.70% | 无 |
| | 常驻 3★ | `[7,23)` = **1.60%** | `[7,30)` = **2.30%** | **+0.70 点** |
| | **3★ 合计** | **[0,23) = 2.30%** | **[0,30) = 3.00%** | **+0.70 点** |
| | 2★ | 18.5% | 18.5% | 无 |
| **Fes** | UP 角色 | `[0,7)` = 0.70% | `[0,7)` = 0.70% | 无 |
| | Fes 限定 | `[7,9)` = **0.20%** | `[7,16)` = **0.90%** | **+0.70 点** |
| | 常驻 3★ | `[9,44)` = **3.50%** | `[16,60)` = **4.40%** | **+0.90 点** |
| | **3★ 合计** | **[0,44) = 4.40%** | **[0,60) = 6.00%** | **+1.60 点** |
| | 2★ | 18.5% | 18.5% | 无 |

**根因**：`*Rate` 被当**绝对上界**比较，而不是区间宽度 ⇒ 实际等于 `max(各阈值)`，不是求和。

**⇒ 请用户在下面三个选项里选一个（我建议 A）：**

| 选项 | 含义 | 结果 | 代价 |
|---|---|---|---|
| **A（推荐）修正** | 改累加语义，默认值 = 上表代码常量 | Pickup 2.3%→**3.0%**、Fes 4.4%→**6.0%**、常驻不变 | 老玩家的"手气基准"变了；但这是回到设计意图 / 官方数值 |
| B 保持现状 | 改累加语义，但默认值改成 `Pickup: rateUp=0, permanentSSR=23`、`Fes: rateUp=0, fesSSR=0, permanentSSR=44` | 合计仍是 2.3% / 4.4% | UP 角色**没有独立权重**（被并进常驻池均匀抽），本质是把 §0.3 的缺陷写进默认值；不推荐 |
| C 修正但压回总数 | `Pickup: rateUp=7, permanentSSR=16`（+2=2.3%）、`Fes: rateUp=7, fes=9, permanent=28`（=4.4%） | 总数不变，但 UP 拿到独立 0.7% | UP 变好、常驻变差；等于偷偷改了池内结构 |

**建议 A**，并在会话里明确告知玩家"出货率已修正到官方数值"。

---

## 3. 生效机制：要不要重启？

### 3.1 两个选择

| | **A. 热加载（推荐）** | **B. 重启生效** |
|---|---|---|
| 实现 | `GachaRatesConfig` 静态类，`_lastCheck` + 5s TTL + `File.GetLastWriteTimeUtc` 比对，`ShopManager` 每抽调一次 | 启动时读一次塞 `static readonly`；或在 `Config` 里缓存 |
| 代价 | **约 25 行**（照抄 `Core\GachaCommand.cs:11-27` 已验证的写法） | 约 5 行（更少），但**每次改率都要重启进程** |
| 改值到生效 | **≤ 5 秒** | 重启耗时 + **踢光在线玩家** |
| 出错回滚 | 改回来，5s 生效 | 再重启一次，二次踢人 |
| 现场风险 | 5s 窗口内新旧混合（可接受，抽卡是逐抽判定的） | 依 `PANEL_MERGE_20261117.md §4.1`：`tmux` 窗口里只有这一个进程，`send-keys C-c` 会**销毁整个会话**，必须 `kill-session` + `new-session`；这是已知的重启脆弱点 |
| 建议 | ✅ **选 A**。理由：本项目已有 4 处同款热加载（`worldraid_manifest.json`、`event_schedule.json`、`server_notice.json`、`gacha_config.json`），不是新风险；而且"管理站改完立刻能验"是 P0 的核心体验 | ❌ 只在 A 做不了时才用 |

### 3.2 优先级（必须写进代码注释，否则运维会被"改了没反应"坑）

```
第 1 优先：gacha_config.json 的 custom_rates 非空  → 整体接管（现有 ShopManager.cs:193 行为，保持不动）
第 2 优先：Data/gacha_rates.json 的 categories     → 按分类走累加阈值
第 3 兜底： GachaService.InitializeGachaRates      → 代码常量
```

⇒ 只要线上残留一个带 `custom_rates` 的 `/www/wwwroot/gacha_config.json`，**新版面板怎么改都不会生效**。
必须让 `GET /api/admin/gacha/rates` 返回 `legacyOverrideActive: true/false`，面板在页面顶部红字提示该状态。这是 P0 的必需项，不是可选美化。

### 3.3 缓存失效

`POST` 保存成功后，服务端主动调 `GachaRatesConfig.Invalidate()`（等价 `Core\GachaCommand.ClearCache()` 的写法），让**保存后第一抽**就用新值，不等 5s。跨进程/手工改文件仍靠 5s 兜底。

---

## 4. 管理站页面（P0 最小版）

### 4.0 关于 `ADMIN_PANEL_STRUCTURE.md`

`work\ba\plan\20261119\ADMIN_PANEL_STRUCTURE.md` **不存在**（已用 glob 全目录确认：`work/ba/plan/20261119/*.md` 共 38 个文件，无此文件）。
按任务要求本该"待报告回来后补 3 个细节"。**但这 3 个细节我已经用实测源码填实了，无需再等**，来源如下（若日后该报告回来，以其为准做校对即可）：

| 待补细节 | 实测答案 | 依据 |
|---|---|---|
| ① 页面文件路径 | `pages/gacha.php`（新建）；导航项注册在 `inc/helpers.php` 的 `nav_items()` | `srv_live\20261118_0059\ba_cardadmin\inc\helpers.php:759-785`；同目录 `pages\*.php` 共 12 个现成样板 |
| ② DB 表名 | 审计写 `audit_logs`（不动表结构）；**本功能不需要新表** | `sql\schema.sql:104-117`（`audit_logs`）、`:122-126`（`settings` k-v） |
| ③ CSRF 复用方式 | `require_post_csrf()` + 表单里 `csrf_field()`；失败直接 419 | `inc\auth.php:282-318`（`csrf_token/csrf_field/verify_csrf`）、`:321-330`（`require_post_csrf`） |

实测的管理站形态（与任务里"PHP 常量数组 / defaults.json / DB 表"三个猜测都不同，以此为准）：

```
浏览器 ─HTTPS→ PHP 面板 http://<SERVER_IP>:8081 （/www/wwwroot/ba_cardadmin，PHP 8.1，MySQL ba_cardadmin）
                 └─ inc/ba.php  ba_post() 带 X-Admin-Key ─→ http://127.0.0.1:5000/api/admin/*
                                                              （Shittim 自己的 EF Core / 文件系统，唯一写入通道）
```

### 4.1 页面内容

新增 `pages/gacha.php`，标题「抽卡概率」，进 `nav_items()` 的**系统域**（与 `settings.php` 同组，因为它是全服配置而非单个玩家操作）：

```php
// inc/helpers.php:779-784  在 '__g_sys' 组里加一行
'gacha'    => array('抽卡概率', 'pages/gacha.php'),
```

页面结构（一屏打完，不做分页、不做历史图表）：

```
┌ 状态条 ─────────────────────────────────────────────────────────────┐
│ 配置文件 /www/wwwroot/ba_srv/Data/gacha_rates.json  [存在] [有效]     │
│ 生效延迟 ≤5 秒（无需重启）    旧覆盖 gacha_config.json：[未启用]      │
│ 默认值来源：GachaService.InitializeGachaRates（服务端实时返回）        │
└─────────────────────────────────────────────────────────────────────┘

┌ 表格：一行一个分类 ─────────────────────────────────────────────────┐
│ 分类          │ rateUpSSR │ fesSSR │ permanentSSR │ SR │ 合计 │ 操作  │
│ 常驻(普通)    │    0      │   0    │      30      │185 │ 215  │[恢复] │
│ Pickup        │    7      │   0    │      23      │185 │ 215  │[恢复] │
│ Limited       │    7      │   0    │      23      │185 │ 215  │[恢复] │
│ Fes           │    7      │   9    │      44      │185 │ 245  │[恢复] │
│ 其它(default) │    7      │   0    │      23      │185 │ 215  │[恢复] │
│ 选择券(Ticket)│    —      │   —    │      —       │ —  │ —    │[恢复] │
└─────────────────────────────────────────────────────────────────────┘
   每格 = <input type="number" min="0" max="1000" step="1">
   "合计" 列只读、实时 JS 求和，>1000 立刻标红
   底部：[保存并生效]  [全部恢复默认]     右上：[恢复上一版]

┌ 快照列表（最近 10 条）─────────────────────────────────────────────┐
│ 时间 │ 操作人 │ 变更摘要 │ [回滚到此版本]                             │
└─────────────────────────────────────────────────────────────────────┘
```

- 每行一个独立 `<form method="post">`（带 `csrf_field()`），加 `oninput` 现算合计，**前端只做提示，校验以服务端为准**。
- "恢复"= 只重置**这一行**（提交 `reset: ["PickupGacha"]`）。
- "全部恢复默认"= `reset: "all"`，**弹二次确认**（这是全服出货率，误点代价高）。
- "TicketGacha" 行四个格置灰只读（`isSelector`，不参与 roll），但仍给"恢复"按钮，避免它挡住整表保存。

### 4.2 校验规则（前端 + 服务端各一遍，以服务端为准）

| 规则 | 前端 | 服务端 |
|---|---|---|
| 每项必须是 `0..1000` 的**整数** | `<input type=number min=0 max=1000 step=1>` | `int.TryParse` + `if (v < 0 \|\| v > 1000) return 400` |
| 同组 `rateUpSSR+fesSSR+permanentSSR+SR+limitedSSR ≤ 1000` | JS 求和标红 + `onsubmit` 拦截 | 逐组求和，超则 `BadRequest({error:"PickupGacha sum 1200 > 1000"})`，**不写文件** |
| 非填项 / 空串 → 用默认值 | 空串按"未填"提交 | `int?` 反序列化，`null` → 取代码默认值 |
| 负数、小数、`1e3`、超长串 | `type=number` 挡一部分 | `JsonElement` 手工解析，非整数直接 400 |
| 未知分类名 | — | 忽略 + 日志警告（不 400，方便以后加池类型） |

### 4.3 保存动作做了什么（服务端 `POST /api/admin/gacha/rates`）

严格按顺序，任一步失败即中止且不改当前文件：

1. **反序列化 + 校验**（§4.2）。非法 → `400 {error}`，**磁盘一字不动**。
2. **读旧文件**，把旧内容存快照：`Config/gacha_rates_history/<yyyyMMddHHmmss>.<n>.json`（`n` 为同秒序号，避免覆盖）。
3. **合并**：把提交值覆盖到"当前生效值"上；`reset` 里的分类先剔除；`reset:"all"` 则整份 `categories` 视为空。
4. **原子写**：写 `gacha_rates.json.tmp` → `File.Move(tmp, target, overwrite: true)`。绝不可 `WriteAllText` 直接盖（避免 5s 轮询读到半个文件）。
5. **失效缓存**：`GachaRatesConfig.Invalidate()`。
6. **清理快照**：目录内按 mtime 排序，**只留最近 20 份**，更老的删掉。
7. **审计**：PHP 侧 `audit_log('gacha.rates.set', '全服', '…')` 写 `audit_logs`；同时服务端写一行 `Console.WriteLine("[GachaRates] saved by …")` 进服务端日志。
8. 返回 `{ success: true, filePath, snapshot: "<ts>", activeWithinSeconds: 5, effective: {…现算的阈值…} }`。

> "生效的值"由服务端**现算后回传**（`effective`），面板拿它刷新表格——这样"面板显示的数字"永远等于"服务端真正在用的数字"，不会出现面板显示 30、实际跑 23 的鬼故事。

### 4.4 一键恢复默认：默认值存在哪？

**结论：不新建 `defaults.json`、不放 DB 表、不在 PHP 里硬编码——默认值的唯一真源就是 `GachaService.InitializeGachaRates()`（`GachaService.cs:29-57`）那 6 个 `switch` 分支，运行时现算现返。**

具体机制：

1. `GET /api/admin/gacha/rates` 每次都调用 `GachaService.InitializeGachaRates(category)` 现算 `defaults`，和文件里的 `current` 一起返回：
   ```json
   { "filePath": "...", "exists": true, "valid": true, "legacyOverrideActive": false,
     "current":   { "PickupGacha": {"rateUpSSR":7,"fesSSR":0,"permanentSSR":23,"SR":185}, ... },
     "defaults":  { "PickupGacha": {"rateUpSSR":7,"fesSSR":0,"permanentSSR":23,"SR":185}, ... },
     "defaultsSource": "GachaService.InitializeGachaRates",
     "sums": { "PickupGacha": 215, ... },
     "snapshots": [ {"id":"20261119_021500_1","ts":...,"summary":"..."} ] }
   ```
2. 面板"默认值"列**直接渲染这个 `defaults`**，不落任何 PHP 端常量。
3. "恢复默认" = `POST { "reset": ["PickupGacha"] }` 或 `{ "reset": "all" }`：
   - 服务端**从 `categories` 里删掉这些 key**（`reset:"all"` 删整份文件或写空 `categories`）。
   - 读取时"缺 key → 用代码默认值"（§2.1）⇒ 天然回到原始常量。
   - 于是**不存在"默认值副本和代码漂移"这个经典 bug**。
4. 防漂移的一个可选加固（建议做，2 行）：`GET` 响应里 `defaultsHash = SHA256(defaults 序列化)`，面板把它显示在页脚。哪天有人改了 `InitializeGachaRates` 的常量，这个 hash 会变 ⇒ 一眼看出"默认值改过了"。

### 4.5 面板代码要点（接入细节）

```php
// pages/gacha.php  —— 新鲜度：直接照抄 pages/currency.php 的骨架
if (!defined('CARDADMIN')) define('CARDADMIN', true);
require_once __DIR__ . '/../inc/auth.php';      // require_login / csrf / audit_log 都在这
require_once __DIR__ . '/../inc/ba.php';
require_login();

$r = ba_gacha_rates_get();                       // GET /api/admin/gacha/rates
if (!$r['ok']) { /* 顶部红色 alert：服务端不可达，把 $r['error'] 原文显示出来 */ }

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    require_post_csrf();                         // inc/auth.php:321 —— 失败 419 直接终止
    $body = ['rates' => [...], 'reset' => $reset];
    $w = ba_gacha_rates_set($body);              // POST /api/admin/gacha/rates
    if ($w['ok']) { audit_log('gacha.rates.set', '全服', $summary); flash_set('已保存，5 秒内生效'); }
    else         { flash_set('失败：' . $w['error'], 'err'); }
    redirect_self();                             // helpers.php:122 —— PRG，防刷新重复提交
}
```

```php
// inc/ba.php 追加四个薄封装（与 :359-366 ba_currency_set 同款写法，复用 :80-159 的 ba_http）
function ba_gacha_rates_get()      { return ba_get('/api/admin/gacha/rates'); }
function ba_gacha_rates_set($b)    { return ba_post('/api/admin/gacha/rates', $b); }
function ba_gacha_rates_snapshots(){ return ba_get('/api/admin/gacha/rates/snapshots'); }
function ba_gacha_rates_rollback($id) { return ba_post('/api/admin/gacha/rates/rollback', ['snapshot' => (string)$id]); }
```

鉴权链不用改：`[AdminAuth]` 在 `ManagementController` 类上（`ManagementController.cs:26`），`ba_http` 已带 `X-Admin-Key`（`ba.php:89-91`）。面板自身登录用 `require_login()`（`auth.php:140-158`）。

---

## 5. 回滚与审计

### 5.1 备份到哪、留几份

```
服务器： /www/wwwroot/ba_srv/Config/gacha_rates_history/
          20261119021500_1.json      ← 每次保存前把"旧文件"整体存一份
          20261119021730_1.json
          ...
命名： <yyyyMMddHHmmss>_<同秒序号>.json
保留： 最近 20 份（按 mtime 排序，超出删最老）
体量： 每份 < 1 KB ⇒ 20 份 < 20 KB，无需压缩、无需异机
```

- 目录放在 `Config/` 下（与 `Config/Config.json`、`Config/sessions.json` 同级，`Config.cs:75` 的目录），**不放进 `Data/`**，避免被 csproj 的 `Data\*` 复制规则带进发布包。
- 快照内容 = 当时的文件原文（若当时文件不存在，则写一份 `{"categories":{}}` 的占位，保证"回滚到第 0 版 = 全默认"可表达）。

### 5.2 一键回滚到上一版

```
GET  /api/admin/gacha/rates          → snapshots: [{id, ts, summary}]
POST /api/admin/gacha/rates/rollback → { "snapshot": "20261119021500_1" }
```

服务端动作：
1. 先把**当前**文件存成新快照（保证"回滚"本身也能再回滚，不会丢现场）；
2. 用目标快照内容原子写回；
3. `Invalidate()`；
4. 返回 `{ success, restoredFrom, activeWithinSeconds: 5 }`。

面板「恢复上一版」按钮 = 取 `snapshots[0].id` 调 rollback；列表里每条也带 `[回滚到此版本]`。

### 5.3 审计

| 层 | 位置 | 内容 |
|---|---|---|
| 面板（人读） | MySQL `ba_cardadmin.audit_logs`（`schema.sql:104-117`） | `action='gacha.rates.set'`、`target='全服'`、`detail='PickupGacha permanentSSR 23→300; sum 215→492'` + 操作人/ip/ts；回滚记 `gacha.rates.rollback` |
| 服务端（机器读） | `Console.WriteLine`（与 `ShopManager.cs:190`、`:202` 现有风格一致） | `[GachaRates] loaded v=20261119021500 src=file sums={...}`、`[GachaRates] saved by=admin snapshot=...` |
| 抽卡行为（核对用） | 每抽首抽打一行 | `[GachaRates] cat=PickupGacha thr[rateUp]=7 thr[fes]=7 thr[lim]=7 thr[perm]=30 thr[sr]=215` |

第三条是 P0 验收的关键（§6）：**一眼就能确认服务端到底在用哪套阈值**，不用赌统计。

---

## 6. 验收清单

### 6.1 服务端侧

**前置：** 确认 `/www/wwwroot/gacha_config.json` **不存在或 `custom_rates` 为空**（否则新配置一律不生效，见 §3.2）。

| # | 步骤 | 判据 |
|---|---|---|
| S1 | `GET /api/admin/gacha/rates`（带 `X-Admin-Key`，本机） | `200`，`defaults.PickupGacha = {7,0,23,185}`，`legacyOverrideActive:false`，`filePath` 指向 `/www/wwwroot/ba_srv/Data/gacha_rates.json` |
| S2 | `POST` 把 `PickupGacha.permanentSSR` 改 `300` | `200`，返回 `effective` 里 `thr[perm]=307`（=7+300） |
| S3 | **等 5 秒**，看服务端日志 | 出现 `[GachaRates] cat=PickupGacha thr[perm]=307 thr[sr]=492` —— **这是最硬的判据，不需要统计** |
| S4 | 真机十连一次（10008） | 返回 10 个 `GachaResults`；`AcquiredItems` 里 `RecruitCoinId` +10 |
| S5 | 连抽 10 次十连（100 抽），统计 3★ | 命中数 ≈ 30.7（期望 30.7，σ≈4.1）；命中率落在 22%–40% 视为通过 |
| S6 | `POST {reset:"all"}` | `200`；`GET` 回读 `current` 与 `defaults` 完全相等；文件被删或 `categories` 为空 |
| S7 | 再抽 100 抽 | 3★ ≈ 3（期望 3.0，σ≈1.7）；**且日志 `thr[perm]=30`** |
| S8 | `POST` 传 `permanentSSR=1200` | **`400`**，`error` 明确写 `sum 1207 > 1000`；`GET` 回读**未变**，日志无 `saved` |
| S9 | `POST` 传 `"abc"` / 小数 / 负数 | 一律 `400`，磁盘不动 |
| S10 | 把 `Data/gacha_rates.json` 手工改坏（截断 JSON） | 抽卡**不崩**（回落默认），`GET` 返回 `valid:false` |
| S11 | `POST /rollback` 到 S2 之前的快照 | 文件恢复成 `permanentSSR=23`，5 秒后日志 `thr[perm]=30` |
| S12 | 十连第 10 抽保底仍在 | 十连结果里**第 10 个**（index 9）必须 ≥ 2★。这是验证"没掉进旧 custom 路径"的关键 |

### 6.2 客户端侧（真机）

| # | 看什么 | 通过标准 |
|---|---|---|
| C1 | 十连抽卡动画 | 正常播放 10 次；不卡在 loading |
| C2 | 第 10 抽 | **必定蓝（2★）或彩（3★）**，不出现灰（1★） |
| C3 | 出彩时 | 立绘、名字、星级、详情全部渲染正常（**不出黑框/空白 = 抽到的 id 在国服客户端里存在**） |
| C4 | 概率说明页 | ⚠️ **大概率仍显示官方旧数字**（那是客户端本地表渲染的，服务端改不了）。**不作为验收依据**，验收只看 S3/S5/S7 的日志与实测命中率 |
| C5 | 抽卡扣费 | 青辉石按 `Amount/120` 扣（P0 不改消耗，行为应与改前一致） |

---

## 7. 风险清单

| # | 风险 | 影响 | 缓解 / P0 处置 |
|---|---|---|---|
| ① | **行为变更**：改累加后 Pickup 3★ 2.3%→**3.0%**、Fes 4.4%→**6.0%**（区间级见 §2.4） | 玩家体感出货变多；若"稀少感"是运营设计的一部分，会被改变 | **必须用户先选 A/B/C（§2.4）**。选 A 就该主动公告"概率已修正为官方数值" |
| ② | **服务端池来自日服 311 MB 表**（`Resources\Dumped\ExcelDB.db` → `_sharedDataCacheService.CharaListSSRNormal/SR/RNormal/Unique/Fest`），**客户端是国服 160 MB** | 抽到国服客户端不认识的 `CharacterId` ⇒ 立绘/详情渲染不出（黑框/空白），玩家以为卡了 | **P0 明确不含过滤**。上线前用 `_panel\good_character_ids.txt` / `bad_character_ids.json` 核对当前开着的池；**P0.5 再加池子过滤**（与 `BAPATCH-CLIENTROSTER` 同一套 id 段逻辑）。注意：**本风险与概率无关——改/不改率都可能抽到**，只是改了率之后抽样变多，撞上的概率也随之变高 |
| ③ | **配置写错导致总和 >1000** | 1★ 区间变负 ⇒ 若直接拿 `1000-sum` 当 R 阈值，会出现"永远抽不到 1★"或越界 | **三层兜底**：<br>(a) 写时 `400` 拒绝，不落盘（§4.2）；<br>(b) 读时若某组 `sum > 1000`，**该组整体回落代码默认值** + `Log.Warning` + `GET` 标 `valid:false`、该行标红；<br>(c) 计算 1★ 时用 `Math.Max(0, 1000 - sum)`，永不为负 |
| ④ | **旧 `gacha_config.json` 残留整体覆盖** | 面板改了没反应，运维排查半天 | `GET` 返回 `legacyOverrideActive`；面板顶部红字；部署时顺手检查该文件 |
| ⑤ | **旧 custom 路径丢十连保底**（§0.3） | 若为省事直接复用 custom 路径，第 10 抽保底消失，玩家立刻发现 | **所以 P0 走新累加阶梯、不复用 custom 路径**；S12 专门验收这条 |
| ⑥ | **`SimulateGacha`（Audit_GachaStatistics）是第二份阈值代码**（`ShopManager.cs:350-377`，保底用 `i % 10`） | 不同步改 ⇒ 客户端"概率/统计"页与真实抽卡不一致，客诉难解释 | P0 一并改累加（约 +10 行）；若时间紧，至少让它也读同一份配置 |
| ⑦ | 5 秒热加载窗口 + 并发写 | 轮询恰好读到半截文件 ⇒ 解析失败回落默认 ⇒ 短暂"概率跳回默认" | **原子写**（tmp + `File.Move(overwrite)`，§4.3 第 4 步）；解析失败只回落、不抛异常 |
| ⑧ | `Data/` 与 `AppContext.BaseDirectory/".."` 两个不同根（§2.1 注意） | 写到错路径 ⇒ 保存成功但永不生效（最坏的静默失败） | `GET` 回传**绝对** `filePath`，面板显示；保存后**回读一次**并比对 `effective`，不一致就报错 |
| ⑨ | 改率可被"套利"（改完狂抽再改回） | 有管理权限的人可以刷号 | 审计已记人+时间+旧值（§5.3）；P0 不做二次确认/审批流，记入 P1 |
| ⑩ | `SelectPickupFesGacha(39)` 等走 `default` 桶 | 以为是 Fes 池、实际按 Pickup 算 | 文档写清（§2.2）；需要就在 JSON 里给它们建独立 key，不改代码 |
| ⑪ | 快照目录无限增长 | 磁盘（实际影响极小） | 只留 20 份（§5.1） |

---

## 8. 工作量估计与验收顺序

### 8.1 估时

| 块 | 内容 | 估时 |
|---|---|---|
| **A. 服务端配置化** | | **5.5 h** |
| A1 | `Services\GachaRatesConfig.cs`：Schema + 加载器（5s TTL、mtime、原子读）+ 校验/clamp + 默认值合并 + 快照读写 | 2.0 h |
| A2 | `ShopManager.cs` `225-256` 改累加阶梯 + `:160` 换入口 + `SimulateGacha` 同步 | 1.5 h |
| A3 | `ManagementController.cs` 4 个端点（含参数校验、错误体、审计日志行） | 1.5 h |
| A4 | `Data\gacha_rates.json` + csproj + `GachaService.cs` 注释 | 0.5 h |
| **B. 管理站页面** | | **5.0 h** |
| B1 | `pages\gacha.php`：表格、JS 求和/标红、四个 POST 分支（保存/单行恢复/全局恢复/回滚）、快照列表 | 2.5 h |
| B2 | `inc\ba.php` 4 个封装 + `inc\helpers.php` 导航 | 0.5 h |
| B3 | `assets\app.css` 样式 + 移动端不塌 | 0.5 h |
| B4 | 自测：`php -l`、CSRF、419、服务端不可达降级、二次确认弹窗 | 1.5 h |
| **C. 验收与取证** | S1–S12 + C1–C5 + 出报告 | **1.5 h** |
| | **合计** | **12 h**（含 buffer ≈ 1.5 人日） |

> 不含：构建/上传/重启的运维时间（`srv-ops` 那边，约 0.5 h，且要挑维护窗口）。
> 不含：若用户选 B/C 选项后需要额外调参。

### 8.2 建议的验收顺序（每步都可独立回滚）

1. **只读打通**（A1+A3 的 GET 部分 → B2 → B1 的只读渲染）
   ⇒ 打开面板能看到"当前值 = 默认值 = 代码常量"。**此时还没有任何行为变更**，可以先给用户看一眼确认 UI。
2. **服务端阈值改造**（A2，配置读默认值）
   ⇒ 此时 `gacha_rates.json` 内容 = §2.3 默认值，**行为按用户选的 A/B/C 走**。跑 S3 + S12（保底仍在）+ S7。
   ⇒ **这一步是唯一的"出货率变更点"，必须在这里停下来让用户拍板后再继续。**
3. **写入链路**（A3 的 POST + 快照 + 审计 → B1 的保存/恢复按钮）
   ⇒ 跑 S2/S6/S8/S9/S11。
4. **真机验收**（C1–C5）
   ⇒ 跑 S4/S5。
5. **出报告 + 交回滚脚本**（§5，快照目录 + DLL 备份戳）

---

## 附：后续阶段（本方案不做，仅登记）

- **P1** 抽卡消耗校验（`ShopManager.cs:47-75`：`Cost==null` 白送十连、不校验价格）
- **P2** 90004 运营数据进管理站
- **P3** 其它名单类配置（池子 id 白名单/黑名单，与风险② 相关）
