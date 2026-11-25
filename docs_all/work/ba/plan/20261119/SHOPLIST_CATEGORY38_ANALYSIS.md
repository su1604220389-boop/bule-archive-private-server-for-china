# `Shop_List(CategoryList=[38])` 取证：38 是什么、我们为什么只回 2 个商品

> 只读分析（2026-11-19）。未改代码、未部署、未重启。
> 现场：客户端进招募界面（00:55:34）只发 `POST /api/shop/list`，`CategoryList=[38]`；我们回 1 分类 + 2 商品（`ShopExcelId` 201/202），**响应里没有 `ShopRecruits`**；整个窗口 `/api/shop/gacharecruitlist`(10006) **0 次**。

---

## 0. 三句话结论

1. **`38` = `ShopCategoryType.CafeSummonTicket`**（`Schale\FlatData\ShopCategoryType.cs:48`）——**不是任何抽卡分类**。
2. **`Shop_List` 永远不会返回 `ShopRecruits`**：`ShopListResponse` 这个 DTO 里根本没这个字段（`NetworkProtocol.cs:6634-6639`）。
3. 我们只回 2 个商品，是因为 **`ShopExcel` 里 `CategoryType=38` 的行就只有 201 和 202 两行**（实测解码：两行都是 `CategoryType=38`、`DisplayOrder=1`、`PurchaseCountLimit=1`）。

---

## 1. `ShopCategoryType` 全量（`Schale\FlatData\ShopCategoryType.cs:8-51`）

| 值 | 名称 | 值 | 名称 |
|---|---|---|---|
| 0 | General | 21 | SecretStoneGrowth |
| 1 | SecretStone | 22 | TicketGacha |
| 2 | Raid | 23 | DirectPayGacha_DontUseGlobal |
| 3 | Gold | 24 | FesGacha |
| 4 | Ap | 25 | TimeAttack |
| 5 | PickupGacha | 26 | Chaser |
| 6 | NormalGacha | 27 | ChaserTicket |
| 7 | PointGacha | 28 | SchoolDungeonTicket |
| 8 | EventGacha | 29 | AcademyTicket |
| 9 | ArenaTicket | 30 | Special |
| 10 | Arena | 31 | Care |
| 11 | TutoGacha | 32 | BeforehandGacha |
| 12 | RecruitSellection | 33 | EliminateRaid |
| 13 | EventContent_0 | 34 | GlobalSpecialGacha |
| 14 | EventContent_1 | 35 | SelectPickupGacha |
| 15 | EventContent_2 | 36 | GemDaily |
| 16 | EventContent_3 | 37 | GemWeekly |
| 17 | EventContent_4 | **38** | **CafeSummonTicket** |
| 18 | _Obsolete | 39 | SelectPickupFesGacha |
| 19 | LimitedGacha | 40 | SelectPickupLimitedGacha |
| 20 | MasterCoin | | |

> **抽卡相关的是 5/6/7/8/11/12/19/22/24/32/35/39/40，`38` 不在其中。**

---

## 2. `Shop_List` 里 `CategoryList` 怎么被用

```csharp
// ShopHandler.cs:520-532
520  [ProtocolHandler(Protocol.Shop_List)]
526      var account = await _sessionService.GetAuthenticatedUser(db, request.SessionKey);
528      var shopExcels = _excelService.GetTable<ShopExcelT>();
529      response.ShopInfos = await _shopManager.GetShopList(db, account, shopExcels, request.CategoryList);
530      response.ShopEligmaHistoryDBs = [];
```
```csharp
// ShopManager.cs:382-408
399      if (reqCategoryList == null) return CategoryList;      // 无分类 ⇒ 空列表
402      foreach (ShopCategoryType shopCategoryType in reqCategoryList)   // 逐个分类
405          var nonSaleProduct  = shopExcel.GetNonSaleShopExcel();
406          var saleProduct     = shopExcel.GetAssignedSaleShopExcel().GetTimelinedShopExcel(dateTime);
407          var combinedProduct = nonSaleProduct.Concat(saleProduct).DistinctBy(x => x.Id).ToList();
408          var products        = combinedProduct.GetCategorizedShopExcel(shopCategoryType).ToList();   // ← 按 CategoryType 过滤
```
**⇒ 传 38 时**：`GetCategorizedShopExcel(38)` 只在 `ShopExcel` 里挑 `CategoryType == 38` 的行；实测该分类**只有 201、202 两行**，所以响应里就是 2 个 `ShopInfoDB`。**这条路径完全不涉及卡池/招募。**

---

## 3. `ShopRecruits` 到底挂在哪些响应上

| 响应 DTO | 是否含 `ShopRecruits` | 位置 |
|---|---|---|
| **`ShopListResponse`**（`Shop_List`） | **不含**（只有 `ShopInfos` + `ShopEligmaHistoryDBs`） | `NetworkProtocol.cs:6634-6639` |
| **`ShopGachaRecruitListResponse`**（`Shop_GachaRecruitList` 10006） | **含**（`ShopRecruits` + `ShopFreeRecruitHistoryDBs`） | `NetworkProtocol.cs:6676-6681` |
| `AccountLoginSyncResponse.ShopGachaRecruitListResponse`（LoginSync 内嵌一份） | **含**（同一个 DTO） | `AccountHandler.cs:508-513`、DTO `NetworkProtocol.cs:6802` 附近 |

`BuildRecruitBanners`（`ShopHandler.cs:78`）只有两个调用点：
```csharp
// ShopHandler.cs:64   —— 10006 的响应里
response.ShopRecruits = BuildRecruitBanners(_excelService);

// AccountHandler.cs:511 —— LoginSync 内嵌的 ShopGachaRecruitListResponse
ShopRecruits = ShopHandler.BuildRecruitBanners(_excelService),
```
**没有任何 `CategoryList` 条件**：它跟分类无关，纯粹"哪个响应带这个子包"。

---

## 4. 10006 的 handler 与请求

```csharp
// ShopHandler.cs:42-66
42  [ProtocolHandler(Protocol.Shop_GachaRecruitList)]
43  public async Task<ShopGachaRecruitListResponse> GachaRecruitList(
45      ShopGachaRecruitListRequest request, ...)
48      var account = await _sessionService.GetAuthenticatedUser(db, request.SessionKey);
50      var recruitHistories = db.GetAccountRecruitHistory(account.ServerId).ToList();
51      response.ShopFreeRecruitHistoryDBs = ...
62      response.ShopRecruits = BuildRecruitBanners(_excelService);
66      return response;
```
```csharp
// NetworkProtocol.cs:6671-6674
public class ShopGachaRecruitListRequest : RequestPacket
{
    public override Protocol Protocol { get => Protocol.Shop_GachaRecruitList; }
}   // ← 没有任何字段，只认协议号 10006
```
**⇒ 客户端只要发 10006 就命中，不需要任何参数。它没发 = 客户端没走到这一步。**

---

## 5. 如果客户端只用 `Shop_List(category=38)`，我们会给 `ShopRecruits` 吗？

**NO。** 依据：
- `ShopListResponse` 没有该字段（§3）；
- `ShopHandler.List`（`:520-532`）里只有 `ShopInfos` 与 `ShopEligmaHistoryDBs` 两处赋值；
- `BuildRecruitBanners` 的两个调用点都不在 `Shop_List` 里。

**⇒ 客户端若从不发 10006，唯一还能拿到 `ShopRecruits` 的途径是 LoginSync 内嵌的那个子响应**（`AccountHandler.cs:508-513`）。
我方可确认：LoginSync 里确实带了 529 条（Lead 已验证）。所以**如果客户端连 LoginSync 里的都没用上**，那就只能是客户端根本没读这个子包 / 或者它把招募界面数据源定在 10006 而不是 LoginSync。

---

## 6. `ShopExcelId` 201 / 202 是什么

实测（`work\ba\data\ExcelDB.db`，表 `ShopDBSchema`，flatbuffer 解码）：

| Id | CategoryType | DisplayOrder | PurchaseCountLimit | PurchaseCountResetType |
|---|---|---|---|---|
| **201** | **38 (CafeSummonTicket)** | 1 | 1 | 1 |
| **202** | **38 (CafeSummonTicket)** | 1 | 1 | 1 |

⇒ 它们是**"咖啡厅召唤券"类的两个商品**，每人限购 1 次。
客户端渲染时用自己 Excel 的 `ShopExcel[201/202]` 取名与图标；我们的响应按 `ShopManager.cs:419-428` 填 `ShopExcelId/Category/DisplayOrder/PurchaseCount/SoldOut/PurchaseCountLimit/ProductType`，
**并且明确不发 `Price`**——代码注释写着：
```csharp
// ShopManager.cs:428
// No Price: across 876 products in the official Shop_List captures the key appears exactly once, and that one response came from our own local server.
```
**⇒ 客户端拿不到价格 ⇒ 很可能用**默认值**渲染（"1,000" 这类）或直接禁用按钮。【推测·高置信】**
配合客户端报的 `No LocalizeKey`：这两行的 `LocalizeEtcId`（字段 slot 1）指向的文本 key 若不在客户端表里，就会显示占位。

---

## 7. 下一步最该查的一件事（不改代码）

**查 `ShopTabGroupDBSchema` / 客户端"招募页"的页签映射**：客户端要 `38` 说明它认为"招募页第一个页签 = CafeSummonTicket"。
两种可能：
- **A（推测）**：我们的 `ShopTabGroup`/`ShopExcel` 与客户端 Excel 不是同一套 ⇒ 页签被映射到错的分类 ⇒ 拉错数据、显示占位、按钮默认值；
- **B（推测）**：客户端招募页确实先拉 38（咖啡厅召唤），再拉 10006 拿卡池；而 10006 那一步没触发（可能依赖 A 的结果）。

**可验证实验**：把 `CategoryList` 里 38 的返回内容（现为 2 条）与官方样本对照；或直接在服务端临时让 `Shop_List` 对 38 也附加一份 `ShopRecruits`（**需改 DTO，不能做**）——所以更现实的是找一份官方 `Shop_List` 请求，看它进招募页时发的 `CategoryList` 到底是哪些值。
