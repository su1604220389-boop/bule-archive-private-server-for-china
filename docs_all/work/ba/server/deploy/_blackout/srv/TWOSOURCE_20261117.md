# 双真相源 + 支付链路 + 免费礼包幂等 —— 取证报告

- 取证者：srv-ops
- 时间：2026-11-17 20:06（北京时间 UTC+8）
- 只读；未改任何配置/代码/库

---

## 0. 一句话结论

**付费礼包走的是 `Billing_TransactionStartByYostar`（客户端号 29000）；支付地址**不来自我们的响应**，来自客户端内置的 Yostar SDK（`open.yostar.net` / `sdk-api.yostar.cn`，passthrough 直连官方）；最小拦截改法 = 让 29000 在桥里直接回非 0 `ErrorCode`（客户端不进 SDK），并把 29002 的商品列表继续置空。**

---

## 1. 支付链路全图

### 1-1 客户端实际发过哪些 billing 协议（全部 24 条，历史累计）

| 路径 | 客户端 token | 我们解析的名 | **客户端号(gen_protocol)** | Shittim 实际收到的名 | 次数 |
|---|---|---|---|---|---|
| `/api/billing/purchaselistbyyostar` | `UXIHQC2AXRZCEBTL2NPBMBBI6I` | `Billing_PurchaseListByYostar` | 29002 | `Billing_PurchaseListByYostar` | 13 |
| `/api/billing/purchasefreeproduct` | `EG2DYZYABN6E5CHUSZPXOI7BPQ` | `Billing_PurchaseFreeProduct` | **29003** | **`Billing_PurchaseCashShopVerifyByNexon`** ⚠️ | 7 |
| `/api/billing/transactionstartbyyostar` | `2CM4FRDYGGIB2W4VPZMVGHVL6Y` | `Billing_TransactionStartByYostar` | 29000 | `Billing_TransactionStartByYostar` | 4 |

**⇒ `Billing_TransactionEndByYostar`(29001) 从未出现** ⇒ 用户的付费尝试**只走到"开始交易"就交给了客户端 SDK**，没有进入服务端结算。

### 1-2 ★ 发现第二个编号错位（与 1017 同类）

```
客户端：「Billing_PurchaseFreeProduct」 的 Hash>>32 = **29003**
Shittim 枚举（ProtocolData.cs:293,298）：
    Billing_PurchaseCashShopVerifyByNexon = 29003
    Billing_PurchaseFreeProduct          = **29008**
⇒ 桥把客户端的 29003 原样发过去，Shittim 执行的是 **PurchaseCashShopVerifyByNexon**，不是 FreeProduct。
日志实证（每一条都这样）：
  20:01:28 /api/billing/purchasefreeproduct
    protocol_raw            'EG2DYZYABN6E5CHUSZPXOI7BPQ'   ← 权威表 = Billing_PurchaseFreeProduct
    relay2_protocol         29003
    relay2_gateway_protocol 'Billing_PurchaseCashShopVerifyByNexon'
    req_frag_head           '3,"ShopCashId":900000,...'
```
**⇒ 这是 FIX-5b（按名字查 Shittim 编号再发）没有上线造成的 —— `cn_protonum_remap.txt` 现在是 0（关），补丁当时因锚点不唯一中止。**

### 1-3 支付地址从哪来 —— **不是我们给的字段**

`BillingPurchaseListByYostarResponse` 全部字段（`NetworkProtocol.cs`）：
```
CountList                    List<PurchaseCountDB>?
OrderList                    List<PurchaseOrderDB>?
MonthlyProductList           List<MonthlyProductPurchaseDB>?
BlockedProductDBs            List<BlockedProductDB>?
BattlePassProductList        List<BattlePassProductPurchaseDB>?
PendingProductShopCashIds    List<long>?
```
**⇒ 6 个字段，**全部是列表**，**没有任何 `Url` / `StoreUrl` / `PaymentUrl` / `PurchaseUrl` / `PriceTierId` 字段**。**
而 Shittim 的实现（`BillingHandler.cs:106-145`）把这 6 个列表**全部置空**（`response.CountList = []` …），响应只有 492 B。

**⇒ 客户端拉起官方支付 SDK、扫码显示「优星网络」，用的是**客户端内置的 Yostar SDK 配置**（运行期请求 `open.yostar.net` / `sdk-api.yostar.cn`），我们既不参与也无法从响应里"改地址"。**

（链路证据：`tcp-access.log` 里这些域名全部是 **passthrough 到真实外网**，例如 `sdk-api.yostar.cn → 112.48.163.29:443`、`udata-api.open.yostar.net → 106.15.x`，`sni=static` 那种例外规则不适用它们。）

### 1-4 最小拦截改法（**方案，未执行**）

| 方案 | 做法 | 效果 | 风险 |
|---|---|---|---|
| **Z1（推荐）** | 桥在 `Billing_TransactionStartByYostar`(29000) 上**直接返回非 0 ErrorCode**（不进 relay） | 客户端 SDK 拉不起支付页 → 无法真付 | 极低；只影响付费流程 |
| Z2 | `Billing_PurchaseListByYostar`(29002) 继续返回 6 个空列表（现状已是空） | 商店无商品可点 | 低；但用户已经能点到"付费礼包"说明商品来源不在这个接口（可能在 29008/90011 或本地配置），**单靠 Z2 不够** |
| Z3 | 在 9097 桥上加"billing 白名单"：除 29002 外一律 404/错误码 | 一刀切 | 中；可能影响免费领取以外的正常 UI |

**⇒ Z1 + Z3 组合最稳（先 Z1 立刻止血，再观察是否需要 Z3）。**

---

## 2. 1017 与 1002 的 AccountDB 归属关系

**`AccountLoginSyncResponse`（1017）的 31 个字段（原文清单）：**
```
Responses / CafeGetInfoResponse / AccountCurrencySyncResponse / CharacterListResponse /
EquipmentItemListResponse / CharacterGearListResponse / ItemListResponse / EchelonListResponse /
MemoryLobbyListResponse / CampaignListResponse / ArenaLoginResponse / RaidLoginResponse /
EliminateRaidLoginResponse / CraftInfoListResponse / ClanLoginResponse / MomotalkOutlineResponse /
ScenarioListResponse / ShopGachaRecruitListResponse / TimeAttackDungeonLoginResponse /
EventContentPermanentListResponse / AttachmentGetResponse / BillingPurchaseListByNexonResponse /
AttachmentEmblemListResponse / ContentSweepMultiSweepPresetListResponse / StickerListResponse /
MultiFloorRaidSyncResponse / MultiFloorRaidLoginResponse / FriendCount / FriendCode /
PickupFirstGetHistoryDBs / AccountLevelRewardIds
```
**⇒ **`AccountLoginSyncResponse` 里没有 `AccountDB`**（`'AccountDB' in body == False`）。**

**⇒ 身份字段只由 `Account_Auth`(1002) 提供，而 1002 是**桥自造**（`account_service.build_account_db_for` + `cn_inner27.build(1002)`）；**
**⇒ 1017 转发 Shittim 后，**身份仍来自 1002（桥）、数据来自 Shittim（真库）** —— 这就是"600 vs 7000 多"两套真相源的直接机制：**
```
青辉石 600   ← gen1017 动态生成器的模板（桥）
青辉石 7000+ ← Shittim Currencies 真库（29×200 + 邮箱 1200）
```
**⇒ 所以 1017 转发只能解决"数据"这一半；`1002` 的 `AccountDB` 仍是桥的账（Level=1、Nickname=''、RepresentCharacterServerId 等），两边**必须再对一次**。**

---

## 3. 免费礼包无限领 —— 幂等缺陷定位

**文件:行号**：`Shittim-Server/Core/NetworkProtocol/Handlers/BillingHandler.cs:215-270`（`Billing_PurchaseFreeProduct`）

**原文关键段（无任何"已领过"检查）：**
```csharp
215  [ProtocolHandler(Protocol.Billing_PurchaseFreeProduct)]
216  public async Task<BillingPurchaseFreeProductResponse> PurchaseFreeProduct(
...
221      var account = await _sessionService.GetAuthenticatedUser(db, request.SessionKey);
226      var shopCash = shopCashExcels.FirstOrDefault(x => x.Id == request.ShopCashId);
234      var product = productExcels.FirstOrDefault(x => x.Id == shopCash.CashProductId);
246      var parcels = new List<ParcelInfo>();
247      for (int i = 0; i < parcelTypes.Count; i++) { parcels.Add(...); }        ← 每次无条件重建奖励
257      var parcelResult = await _parcelHandler.BuildParcel(db, account, parcels, parcelResultDB);  ← 每次无条件发奖
260      response.PurchaseProduct = new PurchaseCountDB { ShopCashId = ..., PurchaseCount = 1, ... };  ← 只回显，不落库
```
**⇒ 三个问题叠加：**
1. **没有任何"该 ShopCashId 已购买过"的查询**；
2. **也没有把 `PurchaseCountDB` 写入数据库**（只放在响应里）⇒ 下一次调用完全不知道之前领过；
3. **客户端实际打到的是 29003 → `PurchaseCashShopVerifyByNexon`**（编号错位），那个 handler（`BillingHandler.cs:283-333`）同样没有幂等检查。

**⇒ 因此"无限重复领"是必然的，不是偶发。**

---

## 4. 待办（按优先级，未执行）

1. **止血**：29000 返回非 0 ErrorCode（阻断真实支付）。
2. **修编号错位**：上线 FIX-5b（按名字查 Shittim 编号；29003→29008、1017→1019）。
3. **1017 转 Shittim**（方案待批）：消除"600 vs 7000+"双源。
4. **免费礼包幂等**：`PurchaseFreeProduct`/`VerifyByNexon` 加"已购查询 + 落库"。
