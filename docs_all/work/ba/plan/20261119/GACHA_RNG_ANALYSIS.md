# 抽卡 RNG 全链路与可配置化注入点（只读分析）

> 2026-11-19　·　只读，未改任何文件
> 源码：`work\ba\srv_src\Shittim-Server\`

---

## 0. 结论速览

| 项 | 结论 |
|---|---|
| 3★ 率的**定义位置** | **代码常量**，`Services\GachaService.cs:29-57` `InitializeGachaRates()`，**不是 Excel 表** |
| 3★ 率数值 | 常驻(NormalGacha) `permanentSSRRate = 30`；Pickup/Limited `rateUpSSRRate = 7` + `permanentSSRRate = 23`；Fes `7 + 9 + 44` |
| 2★ 率 | `SRRate = 185`（三种池都一样） |
| 单位 | **千分比**，因为骰子是 `Random.Shared.NextInt64(1000)`（`ShopManager.cs:185`） |
| **实测有效概率** | 常驻 **3.0%**；**Pickup 实际 2.3%（不是 3.0%）**；Fes 实际 4.4% —— 见 §2.3 的阈值 bug |
| 天井/井 | **没有**。只有"十连第 10 抽保底 2★"（`guaranteedSRIndex = 9`）和招募币累积 |
| 消耗校验 | **服务端不校验价格**；`req.Cost == null` 时**完全不扣、还白送十连**（`ShopManager.cs:53-58`） |

---

## 1. 入口与调用链

```
客户端 → POST /api/shop/buygacha3            (协议 10008 Shop_BuyGacha3)
ShopHandler.BuyGacha3                        ShopHandler.cs:345-412
 ├─ _shopManager.TryBuyStudent(...)          ShopHandler.cs:353 → ShopManager.cs:78-102（学生兑换分支，命中则直接返角色）
 ├─ _shopManager.ConsumeCurrency(...)        ShopHandler.cs:369 → ShopManager.cs:47-75   ← 扣费 + 决定 gachaAmount
 ├─ _shopManager.CreateTenGacha(...)         ShopHandler.cs:373 → ShopManager.cs:104-293 ← 真正的 roll
 │    ├─ GachaService.InitializeGachaRates(banner.CategoryType)   GachaService.cs:29-57   ← 概率在这里
 │    ├─ 循环 gachaAmount 次：
 │    │    ├─ randomNumber = Random.Shared.NextInt64(1000)        ShopManager.cs:185
 │    │    ├─ customRates = Core.GachaCommand.GetCustomRates()    ShopManager.cs:186   ← 控制台 !gacha 覆盖
 │    │    ├─ 命中 → GachaService.GetRandomCharacterId(池)         GachaService.cs:125-129
 │    │    └─ GachaService.AddGachaResult(...)                     GachaService.cs:59-...（发角色 / 转碎片）
 │    └─ 招募币累积（RecruitCoinId）                                ShopManager.cs:259-290
 ├─ 写 ShopFreeRecruitHistories（RecruitCount）ShopHandler.cs:383-396
 ├─ MissionProgress(Reset_GachaCount)          ShopHandler.cs:400-404
 └─ SaveChanges                                 ShopHandler.cs:409
```

其它入口（同一套 roll）：
- `Shop_BuyGacha`(10001) `ShopHandler.cs:277-293`、`Shop_BuyGacha2`(10005) `:295-343`、`Shop_PickupSelectionGachaBuy`(10016) `:454-...` —— 都是拼一个 `ShopBuyGacha3Request` 再调同样的 `ConsumeCurrency` + `CreateTenGacha`。
- `Audit_GachaStatistics`(5) → `ShopManager.SimulateGacha()`（`:296-...`）—— 只统计不发奖，**阈值阶梯与正式路径不同**（`:373` 用的是 `i % 10 == guaranteedSRIndex`）。

---

## 2. 概率从哪来（逐字）

### 2.1 唯一来源 = 代码常量

```csharp
// Services\GachaService.cs:29-57
public static (long, long, long, long, long, bool) InitializeGachaRates(ShopCategoryType characterBannerType)
{
    var (rateUpSSRRate, fesSSRRate, limitedSSRRate, permanentSSRRate, SRRate, isSelector) = (0, 0, 0, 0, 0, false);
    switch (characterBannerType)
    {
        case ShopCategoryType.NormalGacha:
            permanentSSRRate = 30;          // 千分比 → 3.0%
            SRRate = 185;                   // 18.5%
            break;
        case ShopCategoryType.FesGacha:
            rateUpSSRRate = 7;              // 0.7%
            fesSSRRate = 9;                 // 0.9%
            permanentSSRRate = 44;          // 4.4%
            SRRate = 185;
            break;
        case ShopCategoryType.TicketGacha:
            isSelector = true;
            break;
        case ShopCategoryType.LimitedGacha:
        case ShopCategoryType.PickupGacha:
        default:
            rateUpSSRRate = 7;              // 0.7%（UP 角色）
            permanentSSRRate = 23;          // 2.3%（常驻）
            SRRate = 185;
            break;
    }
    return (rateUpSSRRate, fesSSRRate, limitedSSRRate, permanentSSRRate, SRRate, isSelector);
}
```

**⇒ 3★ 率 = 30/1000（常驻）、7+23（Pickup 设计意图 3.0%）、7+9+44（Fes 设计意图 6.0%）。全部写死在代码里，Excel 表里没有。**

### 2.2 骰子与判定

```csharp
// ShopManager.cs:185
var randomNumber = Random.Shared.NextInt64(1000);        // 0..999，千分位
// ShopManager.cs:225-256（非 custom 路径，按顺序短路）
225  if (randomNumber < rateUpSSRRate && !NormalGacha)              → rateUpChar
230  else if (randomNumber < rateUpSSRRate && allowedGachaTypes…)   → fest 池
236  else if (randomNumber < fesSSRRate && FesGacha)                → fest 池
242  else if (randomNumber < limitedSSRRate && limitedSSRRate > 0)  → uniq 池
248  else if (randomNumber < permanentSSRRate)                      → 常驻 3★ 池
253  else if (randomNumber < SRRate || (i == guaranteedSRIndex && shouldDoGuaranteedSR)) → 2★ 池
256  else                                                            → 1★ 池
```

### 2.3 ★ 阈值语义 bug（重要）

**这些 `*Rate` 变量被当作"绝对阈值"而不是"区间宽度"来比较，且相互不叠加：**

| 池 | 设计意图 | 代码实际 | 差距 |
|---|---|---|---|
| NormalGacha | 3.0% | `[0,30)` = **3.0%** | 无 |
| **Pickup / Limited** | 0.7%(UP) + 2.3%(常驻) = **3.0%** | `rateUpSSRRate=7` 判 `[0,7)`；`permanentSSRRate=23` 判 `[0,23)` —— 后者**包含了**前者 ⇒ **实际 2.3%** | **比官方低 0.7 个百分点** |
| FesGacha | 0.7+0.9+4.4 = 6.0% | `fesSSRRate=9` 判 `[0,9)`、`permanentSSRRate=44` 判 `[0,44)` ⇒ **实际 4.4%** | 低 1.6 个百分点 |

对照：**custom rates 路径是正确的累加**（`ShopManager.cs:195-197`：`ssrThreshold`、`srThreshold = ssrThreshold + …`），所以"配了自定义概率"和"没配"两条路径**语义不一致**。

### 2.4 保底 / 天井 / Pickup

| 机制 | 现状 | 位置 |
|---|---|---|
| 十连第 10 抽保底 2★ | `const int guaranteedSRIndex = 9;` + `shouldDoGuaranteedSR`（恒 true） | `ShopManager.cs:154`、`:253` |
| 天井（招募点数兑换/硬保底） | **没有** | 全工程 grep `Ceiling` 只命中 `Math.Ceiling`（制造/活动），无抽卡井 |
| Pickup 角色 | `pickupDuplicateBonusExcels.GetPickupDuplicateBonusByShopId(...)` + `rateUpPickup.PickupCharacterId`；**取自 Excel `PickupDuplicateBonus`** | `ShopManager.cs:129-147` |
| 重复获得 3★ 转碎片 | `GachaService.AddGachaResult` 里 `isNew` 分支 | `GachaService.cs:59-...` |
| 招募币（可换井的道具） | `characterBanner.RecruitCoinId` 每抽 +1 | `ShopManager.cs:259-290` |
| 控制台覆盖 | `!gacha rate <ssr|sr|r> <pct>`、`!gacha guarantee <characterId>` | `Commands\GachaCommand.cs:22-23,135-151` |

---

## 3. 抽卡消耗与校验（**这里最能被改包利用**）

```csharp
// ShopManager.cs:47-75
50  long gachaAmount = 10;
53  if (req.Cost == null)
55      var currentCurrencyEntity = context.GetAccountCurrencies(account.ServerId).FirstOrDefault();
56      var currentCurrencyDB = currentCurrencyEntity?.ToMap(_mapper) ?? new AccountCurrencyDB();
57      return (currentCurrencyDB, consumedItems, gachaAmount);      // ★ 什么都不扣，白送十连
63  gachaAmount = parcel.Type switch
65      ParcelType.Currency => parcel.Amount / 120,                  // 1200 石 = 10 抽
66      ParcelType.Item => GachaService.GetGachaAmountByItem(_itemExcels, parcel.Id),
67      _ => 10,
70  var parcelResolver = await _parcelHandler.BuildParcel(context, account, parcelConsume, isConsume: true);  // ★ 扣的是客户端给的量
```

**⇒ 结论【已证实】：**
1. **服务端不校验"该池该商品的官方价格"**——`Cost` 完全由客户端给，服务端只按它扣；
2. **`Cost == null` ⇒ 免费十连**（不扣任何东西，还按 10 抽出货）；
3. `gachaAmount` 由 **客户端给的 `Amount / 120`** 决定 ⇒ 改包可以 `Amount=120000` 一次抽 1000 次（只要它真有那么多石头）；
4. **服务端没有任何 `ShopExcel`/`Goods` 价格比对**（`EnsurePurchasable` 只在普通商品购买路径用）。

---

## 4. 结果怎么回

- 响应 DTO：`ShopBuyGacha3Response : ShopBuyGacha2Response`（`NetworkProtocol.cs:6621-6627`），含
  `GemBonusRemain` / `GemPaidRemain` / `GachaResults: List<GachaResult>` / `AcquiredItems: List<ItemDB>` / `UpdateTime` / `ServerTimeTicks` / `MissionProgressDBs` / `FreeRecruitHistoryDB` / `PickupFirstGetHistoryDBs`。
- `GachaResult` 每项：`CharacterId`（角色 UniqueId）、`Character`（新获得时=完整 `CharacterDB`，已拥有时 null 并转碎片）、`Stone`（碎片）。
- **客户端不参与 roll**，只渲染；`ServerNotification`/`SessionKey` 由网关补（见 `ENVELOPE_ALIGN.md`）。
- 每次抽卡还会写 `ShopFreeRecruitHistories.RecruitCount`（`:383-396`），并推进 `Reset_GachaCount` 任务。

---

## 5. 可配置化注入点（只指位置，不写实现）

| # | 位置 | 当前形态 | 改成可配置后需要的参数 | 影响范围 | 风险 |
|---|---|---|---|---|---|
| **1** | `Services\GachaService.cs:29-57` `InitializeGachaRates()` | 6 个 `long` 常量，按 `ShopCategoryType` 分支硬编码 | `dict<ShopCategoryType, {rateUpSSR, fesSSR, limitedSSR, permanentSSR, SR}>`（千分比）或百分比→由调用方×10 | **所有**抽卡入口（10001/10005/10008/10016）+ 模拟统计 | 中：改这里等于改全局概率；需保留"未配置时回落当前默认值" |
| **2** | `Services\ShopManager.cs:185` `Random.Shared.NextInt64(1000)` + `:225-256` 阈值比较 | 绝对阈值比较（§2.3 的 bug 源） | 需要同时改成**累加区间**（阈值数组）或提供 `cumulative: true` 开关 | 同上 | **高**：这是行为变更，会改变实际出货率；建议单独一次、配统计对比 |
| **3** | `Services\ShopManager.cs:47-75` `ConsumeCurrency()` | `Cost` 由客户端给，`gachaAmount = Amount/120`；`Cost==null` ⇒ 免费十连 | `{单抽价, 十连价, 货币类型, 是否允许 Cost==null}` + 与 `ShopExcel` 价格比对 | 所有抽卡 | **高**：现在可被改包白嫖；可配置化正好顺手补校验，但要确认客户端发的 `Cost` 与配置价一致，否则全员抽不了卡 |
| **4** | `Services\ShopManager.cs:154` `guaranteedSRIndex` / `shouldDoGuaranteedSR` | 常量 9 | `{十连保底位次 or 关闭}` | 十连 | 低 |
| **5** | `Commands\GachaCommand.cs:22` `customRates` + `:135-151` 的 `rate/sr/r`、`:153+` 的 `guarantee` | **已经是"内存里的可配置层"**（控制台命令设置，重启即失） | 直接把这块字典换成**读配置文件**，并把 `GetCustomRates()` 保留为只读访问器 | 只影响 `customRates.Count > 0` 的路径 | **低**：这是最自然的注入点——`ShopManager.cs:186-222` 已经完整支持"外部给定概率"，且走的是**正确的累加阈值** |
| 6（补） | 卡池清单 `ShopHandler.BuildRecruitBanners`（`Data/GachaRecruitBanners.cn.json`） | 已有外部 JSON 覆盖层 529 条 | 卡池 id / 起止时间 / `RecruitCoinId` / `PickupCharacterId` | 决定"哪些池可抽" | 低（已有先例） |

### 5.1 推荐的最小改造顺序

1. **先做 #5**：把 `GachaCommand.customRates` 改为从 `Data/gacha_rates.json` 读取（结构直接复用现有 `Dictionary<long,double>`：`{3: 3.0, 2: 18.5, 1: 78.5}`），**立即就能在管理站改概率，且不需要动业务逻辑**（`ShopManager.cs:186-222` 已经支持）。
   - 注意：这条路径下 `customRates.Count > 0` 会**整体接管**判定，且不区分池类型（UP 角色逻辑走 `:208-211`，仍是"SSR 时把 rateUpChar 混进池"）。
2. **再做 #1**：把 `InitializeGachaRates` 的返回值改成可注入（配置文件优先级 > 代码默认）。
3. **#2 单独立项**：阈值累加 bug 涉及实际出货率，建议先加统计（`Audit_GachaStatistics` 已有）再改。
4. **#3 与安全一起做**：补价格校验 + 禁止 `Cost==null` 免费十连。

### 5.2 必须提前知道的两个坑

- **日服表 vs 国服表**：服务端抽卡池来自 `_sharedDataCacheService.CharaListSSRNormal/SR/…`（由服务端 `Resources\Dumped\ExcelDB.db`，**日服 311 MB** 构建），客户端是**国服 160 MB**。日服池里可能有国服客户端不认识的 `CharacterId` ⇒ 抽到后立绘/详情渲染不出（与之前 `CharacterId` 空间问题同源）。**可配置化时，池子必须按客户端可解析的 id 段过滤**（工程里已有 `BAPATCH-CLIENTROSTER` 的过滤表可复用）。
- **`PickupDuplicateBonus` 也是 Excel**：UP 角色从 `pickupDuplicateBonusExcels.GetPickupDuplicateBonusByShopId(...)` 取，若日服表里没有对应行，`GetCharacter(...)` 会 `First(...)` **抛异常**（`CharacterExcelExt.cs:7-8`）。
