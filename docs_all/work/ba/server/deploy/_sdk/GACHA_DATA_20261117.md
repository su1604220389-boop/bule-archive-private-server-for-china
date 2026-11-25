# 招募（Gacha）模块数据来源与"塞数据"方案

> 只读核查。未修改任何文件。产物只写本目录。
> 证据：`work\ba\proto\dto_schema_full_v2.json`、`work\ba\srv_src(_orig)`（= 上游 Shittim 快照）、
> il2cpp `md_deob.bin` 类型表、`report\_tmp\最全的一个.har`。
> 日期：2026-11-17

## 0. 一句话

**卡池内容（有哪些角色、概率、pickup）100% 来自客户端本地 Excel（20 张表），服务端只发"哪几个卡池 id 在卖"和"抽卡结果"。上游有完整代码但没有 Excel 数据文件、也没有 `Data/Banner/`。**

**⇒ 用户看到的"假人/占位文字"更可能是表数据/本地化没加载，而不是缺服务端招募响应。**

---

## ① 逐项归类：客户端本地 vs 服务端

| UI 元素 | 来源 | 证据 | 级别 |
|---|---|---|---|
| **卡池里有哪些角色** | **客户端本地 Excel** | 客户端 metadata 有 20 个 Excel 类型：`GachaElementExcel`/`GachaGroupExcel`/`ShopRecruitExcel`/`GachaCombinedCostExcel`/`GachaSelectPickupGroupExcel`/`GachaElementRecursiveExcel`/`LocalizeGachaShopExcel`… | **实测** |
| **抽卡概率** | **客户端本地 Excel** | `GachaElementExcel.Prob`（`GachaGroupHandler` 按 `GachaGroupID` 取 `GachaElementExcel` 后按 `Prob` 加权随机） | **实测**（Shittim 源码） |
| **pickup 角色 / 售卖期** | **客户端本地 Excel** | `ShopRecruitExcelExt` 读 `ShopRecruitExcelT.InfoCharacterId` / `SalePeriodFrom` / `SalePeriodTo` / `CategoryType` | **实测** |
| **概率说明/公告文案** | **客户端本地**（本地化表 `LocalizeGachaShopExcel`） | Excel 类型存在 | **实测**（类型存在）/ 推断（UI 用它） |
| **横幅图（文件本身）** | **CDN/资源包**，不是协议 | 客户端走 Addressables；Shittim 用 `GET /banner/{**path}` 兜底返回 `Data/Koyuki/koyuki.png` | **实测**（Shittim 代码） |
| **"现在有哪些卡池在卖"（id 列表）** | **服务端** | `Shop_GachaRecruitList`(10006) → `ShopRecruits: List<ShopRecruitDB>` + `ShopFreeRecruitHistoryDBs` | **实测**（DTO schema） |
| **抽卡动作** | **服务端** | `Shop_BuyGacha`(10001) / `Shop_BuyGacha2`(10005) / `Shop_BuyGacha3`(10008) | **实测**（Shittim ProtocolData） |
| **抽卡结果** | **服务端**（读 Excel 算） | `ShopBuyGacha2Response.GachaResults: List<GachaResult{CharacterId, Character:CharacterDB, Stone:ItemDB}>` + `AcquiredItems` | **实测** |

### 关键 DTO（实测，`dto_schema_full_v2.json`）

```csharp
// 10006 Shop_GachaRecruitList
class ShopGachaRecruitListResponse {
    List<ShopRecruitDB>           ShopRecruits;                 // 只有 id + 三个日期
    List<ShopFreeRecruitHistoryDB> ShopFreeRecruitHistoryDBs;
}
class ShopRecruitDB { long Id; DateTime SalesStartDate; DateTime SalesEndDate; DateTime UpdateDate; }
class ShopFreeRecruitHistoryDB { long UniqueId; long RecruitCount; DateTime LastUpdateDate; }

// 10001 Shop_BuyGacha
class ShopBuyGachaResponse { ConsumeResultDB ConsumeResultDB; ParcelResultDB ParcelResultDB; }

// 10005 Shop_BuyGacha2 （10008 = 在其基础上加 2 个字段）
class ShopBuyGacha2Response {
    DateTime UpdateTime; long GemBonusRemain; long GemPaidRemain;
    List<ItemDB>      ConsumedItems;
    List<GachaResult> GachaResults;
    List<ItemDB>      AcquiredItems;
    long              GoldRemain;
}
class GachaResult { long CharacterId; CharacterDB Character; ItemDB Stone; }
```

> **注意**：`ShopRecruitDB` **只有 4 个字段（id + 3 个日期）**，**没有任何角色/概率/图片信息**。
> 这从数据契约层面证明了：**卡池内容不在服务端响应里。**

---

## ② 上游有什么 / 没有什么

| 项 | 上游（`srv_src_orig` = Shittim 快照） | 级别 |
|---|---|---|
| gacha 业务代码 | **有**：`Services\GachaService.cs`（概率/消耗/结果）、`Services\GachaGroupHandler.cs`（按组加权抽）、`Commands\GachaCommand.cs`、`Core\GachaCommand.cs` | 实测 |
| gacha 相关协议 Handler | **有**：`Shop_BuyGacha/2/3`、`Shop_GachaRecruitList`、`Shop_BeforehandGacha*`、`Shop_PickupSelectionGacha*` | 实测（ProtocolData + Services） |
| Excel **schema** 类 | **有全套**：`Schale\FlatData\GachaElementExcel.cs`、`GachaGroupExcel.cs`、`ShopRecruitExcel.cs`… + `Schale\Excel\*Ext.cs` | 实测 |
| Excel **数据文件** | **几乎没有**：`Shittim-Server\Data\Excel\` 下只有 **1 个** `MultiFloorRaidSeasonManageExcelT.json` | 实测 |
| `Data\Banner\` 目录 | **不存在**。只有 `Data\Koyuki\koyuki.png`（124,533 B），`BannerController` 拿它兜底 | 实测 |

**⇒ 上游是"有代码、没数据"。** 要把招募跑起来，缺的是**从游戏客户端抽出来的 Excel 表数据**，不是缺代码。

---

## ③ "随便塞一套招募"的可执行方案

先说结论：**这不是"塞服务端数据"能解决的**，因为三样东西分属三层。

### 情况 A：卡池内容 —— **我们塞不了**

角色、概率、pickup、售卖期全在客户端 Excel。服务端**没有任何字段**能改它。
`ShopRecruitDB` 只有 `Id` + 三个日期。

### 情况 B：我们能塞的只有"卡池 id 列表" —— 但**id 必须是 Excel 里真实存在的**

`Shop_GachaRecruitList`(10006) 返回的 `Id` 会被客户端拿去查 `ShopRecruitExcel`：

```
ShopRecruitExcelExt.GetTimelinedShopRecruit(date)   // SalePeriodFrom <= now <= SalePeriodTo
ShopRecruitExcelExt.GetCategorizedShopRecruit(cat)  // CategoryType 匹配
```

⇒ **塞一个 Excel 里不存在的 Id，客户端查不到 → 列表项变空/占位**。
**正确做法**：先把客户端 Excel 的 `ShopRecruitExcel` 导出来，拿到真实 `Id`，再按它的
`SalePeriodFrom/To` 对齐返回。**这一步没做之前，任何"随便塞"都会继续显示占位。**

### 情况 C：抽卡结果 —— 服务端算，但**必须先有 Excel 数据**

`GachaService.InitializeGachaRates(ShopCategoryType)` 是**硬编码概率**（实测源码）：

```csharp
NormalGacha:  permanentSSRRate=30,  SRRate=185
FesGacha:     rateUpSSRRate=7, fesSSRRate=9, permanentSSRRate=44, SRRate=185
Limited/Pickup: rateUpSSRRate=7, permanentSSRRate=23, SRRate=185
TicketGacha:  isSelector=true
```

然后 `GachaGroupHandler.CreateGachaGroupParcel` 用 `GachaElementExcel` 的 `Prob` 做加权随机。
⇒ **没有 `GachaElementExcel` 数据就抽不出东西**（`GetGachaElementsByGroupId` 返回空 → `continue` → 空结果）。

### ★ 我的判断：用户看到"假人/占位文字"的真正原因

**大概率不是缺服务端招募响应，而是"表数据/本地化没加载"。**
理由（推断，中强）：
1. 卡池内容本来就不来自服务端（见 ①），服务端响应里根本没有角色信息；
2. "假人"是 BA 里 **Character/Localize 表缺失时的占位**特征；
3. 客户端是官方原版（lead 已确认），Excel 随包携带，但 **Addressables/TableBundles 没拉全**时同样会缺表；
4. 招募界面渲染卡池要 `LocalizeGachaShopExcel` + `CharacterExcel`，任一缺失就会出现"没有…"。

**⇒ 建议先验证一件事**：进游戏后其它用到 Excel 的界面（角色列表、任务、商店）是否也全是占位？
- **如果也全是 ⇒ 是表数据/本地化整体没加载**（去查 Addressables catalog / TableBundles 下载），跟招募无关；
- **如果只有招募是占位 ⇒** 才是招募专属数据缺（那时再按 ③-B 用真实 Id 塞）。

---

## ④ 官方抓包里有招募吗 —— **没有**

`report\_tmp\最全的一个.har`：**201 条请求，招募相关 0 条**。

抓包覆盖的是登录后的大厅阶段，URL 分布（实测）：
```
21 /api/event/rewardincrease     10 /api/management/data
10 /api/notification/eventcontentreddotcheck   9 /api/mail/check
 8 /api/friend/check   8 /api/clan/check   4 /api/echelon/list
 3 /api/billing/purchaselistbyyostar   3 /api/mission/list
 2 /api/academy/getinfo   2 /api/arena/enterlobby
```
**没有任何 Gacha/Recruit/Banner 请求。**

⇒ **拿不到官方招募响应模板。** 要模板只能再抓一次包（进招募界面 + 抽一次）。

---

## ⑤ 结论与建议（按性价比）

| # | 动作 | 成本 | 价值 |
|---|---|---|---|
| 1 | **先验证"是不是整体表数据没加载"**：看角色列表/商店是否也全占位 | 极低 | 可能直接推翻"塞招募数据"这个前提 |
| 2 | 若确认是招募专属问题：**导出客户端 `ShopRecruitExcel` 的真实 Id 与售卖期**，再按它回 `Shop_GachaRecruitList` | 中 | 让界面列得出卡池 |
| 3 | 若要做抽卡：**必须先把 `GachaElementExcel` / `GachaGroupExcel` 数据导进 Shittim 的 `Data/Excel/`** | 高 | 否则抽卡只能返回空 |
| 4 | 横幅图：Shittim 已用 `GET /banner/{**path}` → `koyuki.png` 兜底，够看 | 零 | — |
| 5 | 要官方招募模板：**再抓一次包**（进招募 + 抽一次），当前 HAR 里没有 | 低 | 仅作参考 |

## ⑥ 拿不到的（明确写死）

| 项 | 原因 |
|---|---|
| 官方 `Shop_GachaRecruitList` / `Shop_BuyGacha*` 的**真实响应** | HAR 里 0 条招募请求（实测） |
| `ShopRecruitExcel` / `GachaElementExcel` 的**真实数据行** | 这些是客户端资源里的表，本项目**未导出**；本地 `Data/Excel/` 只有 1 个无关文件 |
| 客户端招募界面的**任务类**（类似 `BillingCashShopTask`） | 已尝试：客户端侧招募走的是 `Shop_GachaRecruitList` 网络任务 + `MX.Data.ShopCashData`/`ShopRecruitExcel`，**不是"任务类"结构**；具体 UI 绑定未逐层反编译 |
| Excel 表字段的**逐列含义** | `*ExcelT` 类在 il2cpp 里字段被 `__p` 基类折叠（`field_count=1`），列名在 FlatData 的 `__p` 里；Shittim 的 `Schale/FlatData/*.cs` 有完整字段名可作为**权威参考**（`work\ba\srv_src_orig\Schale\FlatData\GachaElementExcel.cs` 8,058 B） |
