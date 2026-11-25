# 客户端计费链（29000 → 29001）逆向

> 只读产物。未修改任何客户端/服务端文件，未碰手机、nginx、`_card_` / `_noroot_` / `_blackout_` / `_multiplayer_`。
> 证据来源：jadx 反编译产物、`classes.dex` / `classes.2dex` 字符串池、il2cpp `md_deob.bin` + `ba_ptrs.bin` + `libil2cpp.so` 反汇编。
> 日期：2026-11-17

## 0. 适用性前提（lead 已修正，必须写在最前）

**用户在手机上现役的是 11-16 02:58 从应用商店重装的官方原版**：
`libil2cpp.so` sha256 = 原厂值，SDK 基址仍为 `https://sdk-api.yostar.cn`。
⇒ 本文分析的是**离线解包的那份构建**（基址已被我们改成 `127.0.0.1:8080` 的那套），
**结论对"代码逻辑"有效，但不代表当前手机正在跑它**。

---

## 1. 结论速览（先看这个）

| 问题 | 答案 | 置信度 |
|---|---|---|
| 29001 谁触发 | **SDK `paySuccess` → `BillingCashShopTask.purchasedCallback` → `OnPurchaseResponded()` → 发 29001**；另有 `PollingBillingTransactionEndByYostar` 轮询兜底 | **推断（中强）** |
| 29001 请求体 | `{ EndType: None/Success/Cancel, PurchaseOrderId: string }`；`PurchaseOrderId` **来自我们 29000 的响应** | **实测（字段）+ 推断（取值）** |
| "支付成功"的判据 | 客户端读 SDK 返回的 `Order.PayState` / `Order.DeliveryState`（int），**具体取值未拿到** | **部分实测** |
| `ShopCashId` ↔ `ProductId` | **不是同一个 id**。`ProductId` 来自客户端 Excel（`ShopCashData` 的平台商品映射），不是 `/order/products` 现取的 | **推断（中强）** |
| 奖励在哪发 | **游戏服务端（29001 响应里的 `ParcelResult`/`MailDB`）** | **实测（字段语义）** |

---

## 2. ① 29000 → 29001 的真实触发链

### 2.1 两个类各有一个"发 29001"的方法（实测，`ba_ptrs` 反查）

| 类 | 方法 | vaddr | 明文? |
|---|---|---|---|
| `BillingCashShopTask`(type[3082]) | `RequestBillingTransactionEndByYostar` | `0x088587A0` | **明文** |
| `BillingCheckPurchaseStateTask`(type[3086]) | `RequestBillingTransactionEndByYostar` | `0x0885B834` | **明文** |

> **重要**：这两个类的方法**整体都是明文**（`BillingCashShopTask` 18 个方法里 17 个 PLAIN，
> 只有 `OpenShopCash` 是 ENC；`BillingCheckPurchaseStateTask` 21 个方法**全部 PLAIN**）。
> 这与登录链（大量密文）形成鲜明对比 —— **计费链基本可以静态读完**。

### 2.2 调用点（实测：全 section `BL/B` 扫描，148 MB / 3700 万条指令）

```
0x088587A0  BillingCashShopTask.RequestBillingTransactionEndByYostar
   ← 0x08858C4C  在 OnPurchaseResponded (+0x37C)                  ★ 主触发
   ← 0x088585B4  在 ErrorBillingTransactionEndByYostarResponseMessage (+0x224)   （重试）
   ← 0x08BBAB78  在 PollingBillingTransactionEndByYostar (+0x174)  ★ 轮询兜底

0x0885B834  BillingCheckPurchaseStateTask.RequestBillingTransactionEndByYostar
   ← 0x0885B81C  在 HandleBillingTransactionEndByYostarResponseMessage (+0x454)  （重试分支）
   ← 0x0885E618  在 <HandleBillingPurchaseListByYostarResponseMessage>b__18_3 (+0x84)
```

### 2.3 关键字段（实测，metadata 字段表）

**`BillingCashShopTask`（8 字段）**
```
transactionProperty / showRewardUI / refreshUI / purchasedCallback /
respondedOrderIdSet / pollingThreshold / pollingCoroutine / productCategory
```
⇒ `purchasedCallback` + `pollingThreshold` + `pollingCoroutine` 三个字段**直接证明**：
这是一个"**发起支付 → 等回调 → 同时轮询**"的任务。

**`BillingCheckPurchaseStateTask`（7 字段）**
```
onCheckTransactionFailDone / notreceivedOrderQueue / currentPurchaseOrder /
existInvisibleGachaToken / existErrorOrder / receivedResponseQueue / existMailResult
```
⇒ `currentPurchaseOrder` + `receivedResponseQueue` + `existMailResult` 证明：
它按**订单**逐个处理，收到 29001 响应后往 `receivedResponseQueue` 里塞。

### 2.4 结论（推断，中强）

```
用户点购买
  → BillingCashShopTask.StartBillingTransaction()  (0x08859E64, 明文)
      → 游戏协议 Billing_TransactionStartByYostar(29000)
          ← 我们回 { PurchaseOrderId, PurchaseServerCallbackUrl, MXSeedKey, PurchaseServerTag, ... }
      → SDK /order/create（OrderCreateReq{ProductId, PayType, ExtraData, NotifyURL}）
          ← OrderCreateEntity{ Alipay.PayParam | Wechat.* | Order{...} }
      → 拉起支付宝/微信 → 用户支付
  → SDK paySuccess()
      → BillingCashShopTask.purchasedCallback   ← 字段名即证据
      → OnPurchaseResponded()  (0x088588D0, 明文)
          → RequestBillingTransactionEndByYostar(EndType, PurchaseOrderId)   ★ 29001
  （并行兜底）
  → PollingBillingTransactionEndByYostar  (0x08BBAA04)
       按 pollingThreshold 周期重试 29001，直到 receivedResponseQueue 里有结果
```

**`OnPurchaseResponded` 这个名字本身就说明它是"购买已响应"的落点**，
而 `purchasedCallback` 是 `BillingCashShopTask` 的字段（typeIdx 35190 = 一个委托类型）。

> **没有证据表明它是从 Java 层直接回调的**（Unity ↔ Java 的桥类 `com.tech.sdk.bridge`
> 在 jadx 里只有 `BuildConfig`/`R`，真正的桥方法未反编译）。
> 所以"paySuccess → purchasedCallback"这一跳是**推断**，其余各跳都有方法名/调用点为证。

### 2.5 `EndType` 的取值（实测枚举定义）

`BillingTransactionEndType`（type[9651]，namespace `FlatData`）**只有 3 个成员**：

```
None        （= 0，按声明顺序）
Success     （= 1）
Cancel      （= 2）
```

⇒ 客户端发 29001 时，**成功路径应带 `EndType = 1 (Success)`**。
（**推断**：声明顺序 = 值顺序，无显式赋值时 C# 默认如此；未在代码里捕到字面量。）

---

## 3. ② `PayState` / `DeliveryState` 的取值 —— **拿不到，但判据清楚了**

### 3.1 能拿到的（实测）

`OrderCreateEntity.Order`（jadx 反编译原文）：
```java
public static class Order {
    private int Amount;
    private int DeliveryState;   // ★ 发货状态
    private int FirstPurchase;
    private String OrderNo;
    private int PayState;        // ★ 支付状态
    private String PayType;
}
```

### 3.2 拿不到的

* **具体整数值（0/1/2 各代表什么）**：`ApiService`（Retrofit 接口）与
  `AiriHttpClientImpl`（网络实现）**jadx 未产出 `.java`**，
  `classes.dex` 里这两个类只有**名字**，没有方法体。
* 客户端 C# 侧读的是 `OrderDetailEntity` / `ResponseMod.data`，而
  `OrderDetailEntity` **在 il2cpp metadata 里也不存在**（搜 type 表 0 命中）——
  说明它在 **Java 层被消费**（`getOrderDetail` 的 `$1` 回调类），
  消费代码就在那个未反编译的类里。

### 3.3 能给的判据（推断，中）

1. 客户端**不是**等渠道回调，而是**轮询订单状态**——
   证据：`BillingCashShopTask.pollingThreshold` / `pollingCoroutine`、
   `BillingCheckPurchaseStateTask.currentPurchaseOrder` / `receivedResponseQueue`。
2. 轮询调用的 SDK 方法是 `getOrderDetail`（`AiriHttpClientImpl$getOrderDetail$1` 实测存在）。
3. 因此 **`/order/create` 与 `/order/detail` 返回的 `Order.PayState`/`DeliveryState`
   必须与官方语义一致**，否则客户端会一直轮询或判失败。

**⇒ 唯一缺的数据：这两个 int 的取值。**
获取方式只有一条：**真机买一次最小额商品，抓官方 `/order/create` 与 `/order/detail` 的响应**。

> 另有一个可用的旁证方向（未做）：`BillingCheckPurchaseStateTask.CheckPurchaseState`
> (`0x0885C400`) 是判据所在方法，它是**明文**，但它做的第一件事是取
> `[x19+0x144]` 的一个 byte 并 `cbz` 提前返回 —— 这是状态机守卫，不是 PayState 比较。
> 真正读 PayState 的地方在未反编译的 Java 层。**所以 C# 侧挖不到 PayState 的值。**

---

## 4. ③ `ShopCashId` ↔ SDK `ProductId` 的来源

### 4.1 两套 id（实测）

| 层 | 字段 | 类型 | 出处 |
|---|---|---|---|
| 游戏协议 | `BillingTransactionStartByYostarRequest.ShopCashId` | **long** | metadata type[10798] |
| SDK | `OrderCreateReq.ProductId` | **int** | jadx 反编译 |
| SDK 商品列表 | `OrderProductsEntity.ProductItems.ID` / `GameProductID` / `StoreProductID` | int / String / String | jadx 反编译 |

### 4.2 `ProductId` 从哪来（推断，中强）

`MX.Data.ShopCashData`（type[15748]，18 字段）里有整整一组**平台→商品 id 的映射**：

```
<_product>k__BackingField                    (typeIdx 10476)   ← 当前平台商品
<_productMonthly>k__BackingField             (10734)
<_productBattlePass>k__BackingField          (10474)
<_productSelect>k__BackingField              (10736)
<_productDailyRecord>k__BackingField         (10732)
<_productGooglePoint>k__BackingField         (10476)
<_productPCStore>k__BackingField             (10476)
<_productGooglePointByProductId>k__BackingField (10983)        ← 按 ProductId 反查
<_productPCStoreByProductId>k__BackingField  (10983)
<_shopCashExcelIdsByProductId>k__BackingField (10973)         ← ProductId → ShopCashId！
<_productKeyInfoByShopCashId>k__BackingField (10808)          ← ShopCashId → 商品信息
```

**⇒ 映射表就在客户端的 Excel 数据里，`_shopCashExcelIdsByProductId` 与
`_productKeyInfoByShopCashId` 就是那对双向字典。**

**因此 `ProductId` 不是 `/order/products` 现取的，而是客户端本地 Excel 里按平台选出来的。**
`/order/products` 是**另一个**用途（拉商品列表/展示），不是下单前置。

> 对我们建映射表的含义：**商品 ↔ SDK ProductId 的对应关系必须与客户端 Excel 一致**。
> 我们自己是服务端，可以在 `/order/create` 里**不校验 ProductId**，只用它作日志/映射；
> 真正的发货依据用 `ShopCashId`（游戏协议里带）—— 这样完全绕开 Excel 对齐问题。

---

## 5. ④ `order/products` 的响应结构（实测原文）

```java
public class OrderProductsEntity implements Serializable {
    private ArrayList<ProductItems> Product;          // ★ 唯一的顶层字段

    public static class ProductItems implements Serializable {
        String GameMoney;
        String GameProductID;
        int    ID;              // ← 这就是 OrderCreateReq.ProductId 的候选来源
        String Name;
        String Price;
        String StoreProductID;
    }
}
```

字段全表就这 7 个（顶层 1 + 内层 6）。

---

## 6. 奖励发放在哪一层 —— **游戏服务端**

### 6.1 实测字段（metadata）

```java
BillingTransactionStartByYostarRequest {
    long   ShopCashId;
    List   ShopCashProductSelectionDBs;
    bool   VirtualPayment;
}
BillingTransactionStartByYostarResponse {
    long     PurchaseCount;
    DateTime PurchaseResetDate;
    string   MXSeedKey;
    string   PurchaseServerTag;          // 或枚举
    string   PurchaseServerCallbackUrl;  // ★ 服务端回调地址（我们控制）
    string   PurchaseOrderId;            // ★ 客户端回显到 29001
}
BillingTransactionEndByYostarRequest {
    BillingTransactionEndType EndType;   // None / Success / Cancel
    string PurchaseOrderId;
}
BillingTransactionEndByYostarResponse {
    ParcelResult       ParcelResult;        // ★ 发放的包裹
    MailDB             MailDB;              // ★ 邮件补发
    List               CountList;
    int                PurchaseCount;
    List               MonthlyProductList;
    BattlePassInfo     BattlePassInfo;
    List               BattlePassProductList;
}
```

### 6.2 结论（推断，强）

**奖励必须在 `Billing_TransactionEndByYostar`(29001) 的响应里发。**
依据：
1. `ParcelResult` / `MailDB` / `MonthlyProductList` / `BattlePassInfo`
   是游戏内**发道具/发邮件/发月卡**的标准载体；
2. SDK 侧（`OrderCreateEntity`）**只有支付渠道参数与订单状态，没有任何道具概念**；
3. `PurchaseOrderId` 由**我们**在 29000 响应里下发、客户端原样回显到 29001 ⇒
   **我们完全掌控订单号**，可以做"任何订单号都认"的宽松校验。

⇒ **实现分工**：
* **SDK 服务端**：让 `/order/create` + `/order/detail` 返回"已支付"状态即可；
* **游戏服务端**：29000 发 `PurchaseOrderId`，29001 按 `PurchaseOrderId` 发 `ParcelResult`。

---

## 7. 拿不到的（明确写死）

| 项 | 原因 |
|---|---|
| `PayState` / `DeliveryState` 的具体取值 | `ApiService` / `AiriHttpClientImpl` / 全部 `order/*` 消费代码**未被 jadx 反编译出 .java** |
| `OrderProductsReq` / `OrderDetailReq` / `OrderDetailEntity` 的字段 | 同上（`OrderDetailEntity` 在 il2cpp 里也不存在 ⇒ 纯 Java 层 DTO） |
| `SignProvider` 的签名算法 | 类未反编译；`AiriSgClient.sign()` 是 native（`libairisgcore.so`，**已被我们替换**） |
| `/order/create` 的 Content-Type | `ApiService` 未反编译（`ResponseMod` 是 JSON 信封 ⇒ **推断**也是 JSON 请求） |
| paySuccess → `purchasedCallback` 的那一跳 | Unity↔Java 桥（`com.tech.sdk.bridge`）未反编译出方法体 |

## 8. 建议补的一次实验（一次即可闭环）

**真机买一次最小额商品**，抓三样：

1. `POST /order/create` 的**官方响应原文** → 拿到 `Order.PayState` / `DeliveryState` 的真实值；
2. `POST /order/detail`（若有）的响应 → 确认轮询判据；
3. 客户端随后发出的 `Billing_TransactionEndByYostar` 请求 → 确认 `EndType` 实际是 1 还是别的。

拿到这三样，假支付就能 100% 对齐，无需再猜。
