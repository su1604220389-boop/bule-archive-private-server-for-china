# SDK 同源性核实：登录 SDK 与支付 SDK 是不是同一个

> 只读核查。未修改任何客户端文件、未连服务器、未碰手机。
> 证据来源：本地解包 APK（`work\ba\audit\ba-apk\jadx\sources` = jadx 反编译产物）、
> 已落盘的官方 SDK 真实响应（`work\ba\bapatch\sdk_resp\*.json`）、历史改造脚本（`work\ba\bapatch\repack_e*.py`）、
> 以及项目内既有报告（`01` / `04` / `06` / `09` / `ba-pentest.md`）。
> 日期：2026-11-17

---

## 0. 一句话答案

**SDK = `com.airi.core`（AiriSDK，`libairisgcore.so`，v1.16.1）；登录与支付是**同一个 SDK**；
支付能随登录一起指向我们的服务器 —— 而且「`open.yostar.net` 那条路」不需要改 `ba_sni.conf`，只要改我们自己的 `/common/config` 响应即可。**

---

## 1. SDK 身份

| 项 | 值 | 出处 |
|---|---|---|
| 库包名 | **`com.airi.core`** / `com.airi.common` / `com.airi.plugin.*` | `jadx/sources/com/airi/core/BuildConfig.java`（`LIBRARY_PACKAGE_NAME = "com.airi.core"`） |
| 版本 | **`1.16.1`** | `SdkConst.SDK_VERSION_NAME = "1.16.1"` |
| 产品 ID | `SDK_PID = "CN-BA"`（配置项名 `SDK_PID`） | `SdkConst.java:78` + `ba-sdk-protocol.md:7` |
| 渠道 | `channel = "official"`；`Channel_ID = "CHANNEL"` | `SdkConst.java:15` + `SDKConfigSettings.json` 原值 |
| 原生 SO | **`libairisgcore.so`**（2,658,312 B，签名/加密核心 `com.airi.core.sign.AiriSgClient`） | `report\01` §2；`work\ba\audit\ba-apk\lib\arm64-v8a\` |
| Java 侧入口 | `com.tech.core.TechSplashActivity`、`com.tech.sdk.bridge.TechSDKUnityPlayerActivity`（Unity 壳） | `report\_tmp\sdk_scan\manifest.txt` |
| 同包内其它插件 | `com.airi.plugin.jpush`（推送）、`com.airi.plugin.alipay`（**支付宝支付**） | jadx sources |

> 「TechSDK」只是外包的 Unity 桥壳；真正的 SDK 内核是 `com.airi.*` + `libairisgcore.so`。

---

## 2. 同源判定：**同一个 SDK**（证据 3 条）

### 证据 A：支付与登录的**请求 DTO 在同一个包里、同一个序列化体系**

`com.airi.core.beans.request` 同一个目录下并列存在：

```
LoginReq.java            LoginThirdReq.java      GetTokenReq.java
UserInfoReq.java         BindAccountReq.java     DeviceListReq.java
OrderCreateReq.java   ← 支付：创建订单
OrderDetailReq.java   ← 支付：查订单
OrderProductsReq.java ← 支付：商品列表
```

`com.airi.core.beans.response` 下对应：

```
OrderCreateEntity.java / OrderDetailEntity.java / OrderProductsEntity.java
```

### 证据 B：支付回调是**同一个 SDK 的公开接口**

```
com.airi.common.listener.ISDKPayCallback:
    void paySuccess();
    void payFailed(int code, String msg);
com.airi.common.model.bean.PayInfo / OrderInfo
com.airi.plugin.alipay.model.AliPayResult
```

⇒ 支付不是游戏侧自己做，是 **SDK 内部**做完再回调游戏。

### 证据 C：**只有一套配置**

`com.airi.common.model.params.SDKConfigSettings`（jadx 反编译全文）的顶层字段只有：

```java
private Ali ali;
private Android android;      // 内部: cs_enable / cs_url / qq_appid / weibo_appid / weixin_appid / udata_oeappid / weibo_callback
private String sdk_url = "";  // ★ 唯一的基础地址
private String channel = "";
```

**没有任何 `pay_url` / `billing_url` / `order_url` 之类的独立地址字段。**
`android.cs_url` 是**客服**地址，`ali.internet_detection.*` 是**支付宝网络诊断**，都不是支付网关。

⇒ **SDK 只有一个服务端基址 `sdk_url`；登录与支付共用它。**

---

## 3. base URL 的**具体位置**与**当初的改法**

| 项 | 内容 |
|---|---|
| 文件 | APK 内 **`assets/SDKConfigSettings.json`**（zip 条目，`zip_listing.txt` 第 29066 行证明存在） |
| 原值 | `{ "sdk_url": "https://sdk-api.yostar.cn", "sdk_pid": "CN-BA", "channel": "official" }` |
| 改法（历史） | `work\ba\bapatch\repack_e31.py:6` 定义 `SDK_OLD = b'https://sdk-api.yostar.cn'`；`:17` `assert SDK_OLD in cfg`，随后把该 26 字节**等长/变长替换**成我们的地址（E32/E34/E35 都做 `-> http://127.0.0.1:8080`） |
| 生效实证 | `report\06` §：改完后抓到 `POST /common/config → 200`、`/user/quick-login → 200`、`/user/detail → 200`，客户端进入标题画面 |
| 免 root 版 | `work\ba\noroot\build_noroot_apk.py`（`--sdk-url` 参数），未传则保持官方值（`AUDIT_BUILD_NOROOT.md:402`） |

**⇒ 我们是"换基址"，不是"打补丁绕过"。同一个基址下的所有路径都会跟着走。**

---

## 4. 支付相关路径清单与回调

### 4.1 SDK 侧（基址 = `sdk_url`）

| 路径 | 用途 | 证据 |
|---|---|---|
| `POST /order/products` | 拉商品列表 → `OrderProductsEntity{ Product:[{ID, Name, Price, GameProductID, StoreProductID, GameMoney}] }` | `OrderProductsReq` / `OrderProductsEntity` |
| **`POST /order/create`** | **创建订单** → `OrderCreateEntity{ Alipay \| AlipayQRCode \| Wechat \| WechatQRCode \| Bilibili \| Order }` | `OrderCreateReq{ PayType, ProductId, ExtraData, NotifyURL }` + `OrderCreateEntity` |
| `POST /order/detail` | 查订单状态 → `OrderDetailEntity` | `OrderDetailReq` |

已抓到的 SDK 通用路径（我们 sdkcard 已实现的）：`/common/config`、`/user/login`、`/user/quick-login`、`/user/detail`、`/common/client-code`、`/common/geo-ip`、`/health-game/duration`、`/heartbeat/pulse`、`/channel-user/destroy`、`/user/relink-check`、`/user/set-info`。

### 4.2 ★ 关键：支付页 URL **不是客户端硬编码，是服务端下发的**

`OrderCreateEntity` 的六个字段（`Alipay` / `AlipayQRCode` / `Wechat` / `WechatQRCode` / `Bilibili` / `Order`）
**全部由 `/order/create` 的响应填充**。客户端只是把服务端给的东西交给支付宝/微信 SDK 去拉起。

⇒ **我们在 `/order/create` 里回什么，客户端就按什么走。** 不需要任何官方域名。

### 4.3 回调

* **客户端请求里带 `NotifyURL`**（`OrderCreateReq.NotifyURL`）—— 这是"支付完成后通知谁"的地址，**由客户端（游戏）决定**。
* 支付结果回到 SDK → `ISDKPayCallback.paySuccess()` → 游戏侧再走
  `Billing_TransactionStartByYostar`(29000?) / `Billing_TransactionEndByYostar` 两条**游戏协议**到**我们的游戏服务器**。
* 游戏协议里的 `BillingPurchaseListByYostarResponse` 6 个字段全是列表、**没有 URL**（与 lead 的既有结论一致）——
  这正好说明：**支付地址根本不由游戏协议决定，而由 SDK 的 `sdk_url` 决定**。

---

## 5. 结论

> **「支付可以随登录一起指向我们的服务器」——成立。**

推论链（每一步都有上面的证据）：

1. 登录走 `sdk_url`（已实证：改 `assets/SDKConfigSettings.json` 后 6 个真实请求全落到我们 8080）；
2. 支付 DTO 与登录 DTO 在同包同目录（`com.airi.core.beans.request`）；
3. 支付回调是同一 SDK 的 `ISDKPayCallback`；
4. SDK 配置里**没有第二个基址**，只有 `sdk_url`；
5. 支付页/渠道参数由服务端在下发（`OrderCreateEntity`）。

⇒ **同一基址 ⇒ 支付请求会打到我们服务器 ⇒ 我们回什么订单，客户端就认什么。**

---

## 6. ★ 对 `open.yostar.net` 的解释与"不用碰 ba_sni.conf"的办法

lead 观察到 passthrough 到真实外网的目标是 `open.yostar.net` / `sdk-api.yostar.cn`。
从已落盘的官方 `/common/config` 真实响应（`work\ba\bapatch\sdk_resp\common_config.json`）可以直接看清：

```json
"ChannelConfig": {
  "Udata": { "Enable": true, "URL": "https://udata-api.open.yostar.net", ... }
},
"DetectionAddress": {
  "Auto": { "HTTP": ["https://static.bluearchive-cn.com/checkhealth.html",
                     "https://sdk-api.yostar.cn",
                     "https://gs-api.bluearchive-cn.com/api/health"], ... }
}
```

**⇒ `open.yostar.net` 是 `ChannelConfig.Udata.URL`，即埋点上报（Udata）的地址，不是支付网关。**
而这个 `/common/config` **正是由我们的 sdkcard 下发的**（`report\04:111`、`report\09:216` 记载：我们路由含 `/common/config`，其余一律 `200 {}`）。

所以现在还在访问 `udata-api.open.yostar.net` 的原因很可能是：**我们下发的是官方原样 `common_config.json`，里面 `Udata.Enable=true` 且 URL 指官方。**

**⇒ 处置办法（零风险，不需要 `ba_sni.conf`）：**
把 `/common/config` 响应里的 `ChannelConfig.Udata.Enable` 改成 `false`（或把 `URL` 改成我们的地址），
同时可把 `DetectionAddress.Auto.HTTP/MTR` 里的 `https://sdk-api.yostar.cn` 一并替换/删除。
客户端拿到新配置后就不会再往官方域名发这笔流量。

> ⚠️ 这条是**推断**（"发往 `open.yostar.net` 的流量就是 Udata"），依据是配置字段名与已知的
> `report\ba-pentest.md:139`「`udata-api.open.yostar.net` 9 条，埋点上报 `/daq/track/v2`」。
> 未在真机复验。**但它是可当天验证的**：改完 `common_config.json` 重跑一次，看 passthrough 是否消失。

---

## 7. 不确定 / 做不到

| 项 | 状态 |
|---|---|
| SDK 里 `/order/create` 等路径的**字面量** | **未在 jadx 里找到**（只有 `/common/*`、`/user/*`、`/channel-user/*`、`/user/relink-check`、`/user/set-info` 这些常量）。`/order/create` 的存在依据是 `report\01:417`（`ba-pentest.md §28/§34` 的真实端点枚举）与 DTO 命名，**属推断（中）**。 |
| 支付请求是否真的用 `sdk_url` 前缀 | **推断（强）**：SDK 只有这一个基址，且登录已实证走它。**没有抓到过 `/order/create` 的真实请求**（因为没买过）。 |
| `open.yostar.net` = Udata | **推断（中）**，见 §6 的验证方法。 |
| `libairisgcore.so` 里是否有第二套地址 | **未查**（本次只读 Java 层与资产）。SDK 的网络层若在 native 侧，仍需一次 `strings` 复核。 |

---

## 8. 可执行的下一步（按性价比）

1. **改 `/common/config` 响应**：`Udata.Enable=false`（+ 替换 `DetectionAddress` 里的官方地址）。
   零 APK 改动、可当天验证，**直接消掉 `open.yostar.net` 的 passthrough**。
2. **跑一次真机购买**，在 `tcp-access.log` 里确认 `POST /order/create` 是否落在我们 8080。
   这一步**一次就能把 §7 的两条推断变成事实**。
3. 若成立：把 sdkcard 的 `/order/create` 从"兜底 `200 {}`"改成返回一个**自洽的假订单**
   （`Order` 字段给一个订单号即可），并把游戏侧 `Billing_TransactionStart/EndByYostar` 改成"直接发货"。
   —— 这样整个充值链路不需要任何真实支付渠道。
4. **不要碰 `ba_sni.conf`**：本报告给出了不让流量出去的替代路径。

---

# §订单契约（第 2 轮追加）

> 只读核查。证据来源：`jadx` 反编译产物、`classes.dex` 字符串池、il2cpp metadata（`md_deob.bin`）。
> **推断与实测严格分开标注。**

## 1. SDK 的网络层结构（实测：dex 类名）

```
com.airi.core.data.net.http.ApiService                     ← Retrofit 接口（未反编译）
com.airi.core.data.net.http.SignProvider                   ← 签名提供者（未反编译）
com.airi.core.data.net.http.AiriHttpClient(Impl)           ← 实现（未反编译）
com.airi.core.data.net.http.ErrorHandler
com.airi.core.data.net.FCallBack<T> { onSuccess(ResponseMod<T>); onFail(ResponseMod<T>); }
com.airi.core.data.net.ResponseMod<T> { int code; String msg; T data; }   ← 通用响应信封
com.airi.core.sign.AiriSgClient { native getAAesIv(); native getAAesKey(); native sign(byte[],int); }
                                  static { System.loadLibrary("airisgcore"); }
```

`AiriHttpClientImpl` 的方法（由内部回调类名枚举，实测 32 个）：
`createOrder` / `getOrderDetail` / `getOrderProducts` / `genToken` / `sessionLogin` / `mobileLogin` /
`userDetail` / `initAiriSdk` / `heartbeatPulse` / `getClientCode` / `getGEOIp` / `getDuration` /
`relinkCheck` / `setUserInfo` / `getDeviceList` / `bindAccount` / `reBindAccount` / `authSendCode` /
`authVerifyCode` / `authRealName` / `uploadIdCard` / `checkCaptCha` / `queryTextLegality` /
`openUserSurvey` / `getUserAgreement` / `sendEmail` / `sendSMS` / `queryCSTicket` / `removeDevice` /
`destroyUser` / `destroyChannelUser` / `cancelDestroyUser` / `getIp`

> **⇒ 登录与支付在同一个 `AiriHttpClientImpl` 里，用同一套基址、同一套签名、同一个信封。**
> 这是本轮最硬的同源证据（比上一版更强）。

## 2. 路径字面量（实测：`classes.dex` 字符串池）

```
0x00792250  order/create
0x0079225E  order/detail
0x0079226C  order/products
```

**注意：没有前导斜杠**（与 `SdkConst` 里的 `/user/quick-login` 不同）⇒ 拼装处会自己补 `/`，
或 `ApiService` 的 `@POST("order/create")` 相对 Retrofit baseUrl。

## 3. 三组 DTO 字段全表（实测：jadx 反编译原文）

### 3.1 请求

```java
class OrderCreateReq {
    String ExtraData;   // 透传数据
    String NotifyURL;   // 支付完成通知地址（由游戏侧给）
    String PayType;     // 支付渠道，如 "alipay" / "wechat" / "bilibili"
    int    ProductId;   // ★ 商品 id（见 §6）
}
```

`OrderProductsReq` / `OrderDetailReq`：**未反编译出字段**（类存在、字段未落盘）。
按 `ApiService` 命名推断 `OrderDetailReq` 含订单号、`OrderProductsReq` 含 `PayType`（**推断，弱**）。

### 3.2 响应 `OrderCreateEntity`（270 行，6 个顶层字段 + 6 个内部类）

```java
class OrderCreateEntity {
    Alipay        Alipay;         // { String PayParam }
    AlipayQRCode  AlipayQRCode;   // { String PayParam }
    Wechat        Wechat;         // { appid, partnerid, prepayid, noncestr, timestamp, packageValue, sign }
    WechatQRCode  WechatQRCode;   // { String PayParam }
    Bilibili      Bilibili;       // { game_money:int, notify_url, order_sign, out_trade_no, total_fee:int }
    Order         Order;          // ★★ { Amount:int, DeliveryState:int, FirstPurchase:int,
                                  //        OrderNo:String, PayState:int, PayType:String }
}
```

### 3.3 商品列表 / 订单详情

```java
class OrderProductsEntity implements Serializable {
    ArrayList<ProductItems> Product;
    static class ProductItems { String GameMoney, GameProductID, Name, Price, StoreProductID; int ID; }
}
class OrderDetailEntity { /* 类存在，字段未反编译出 */ }
```

## 4. 请求的编码 / 签名要求（实测 + 推断）

| 项 | 结论 | 依据 |
|---|---|---|
| 传输 | HTTP(S) + JSON（`ResponseMod{code,msg,data}` 信封） | `ResponseMod.java`（实测） |
| 鉴权头 | `Authorization` | dex 字符串 `Authorization` @0x604DDD（实测存在） |
| 签名 | **有签名**，由 `SignProvider` + `AiriSgClient.sign()`（**native**，`libairisgcore.so`） | `AiriSgClient.java`（实测） |
| 签名算法 | **拿不到**（在 native 里；官方侧观测为 `RSA-2048` base64，见 `ba-pentest.md:142`） | **推断（中）** |
| 我们是否能伪造 | **能，而且已经在伪造** —— 客户端跑的是我们替换过的 `libairisgcore.so`（`bapatch\airisg\`，假 SG），签名是我们自己实现的 | 实测（`report\01` §2） |
| 响应是否需要校验签名 | **未见 `AiriSgClient` 有 verify 方法**（只有 `getAAesIv`/`getAAesKey`/`sign`）⇒ 响应大概率**不验签** | **推断（中）** |

> **关键结论**：因为签名器 `libairisgcore.so` 已被我们替换，**"请求要合法签名"这条对我们不构成障碍**——
> 我们的 SDK 服务端可以完全忽略 `Authorization`，客户端也不会因此报错（它只负责发）。

## 5. 六个支付字段的语义（实测字段 + 推断用法）

| 字段 | 结构 | 客户端怎么用 | 置信度 |
|---|---|---|---|
| `Alipay.PayParam` | 1 个 string | 交给**支付宝 SDK** `payV2(...)` 拉起收银台 | 推断（高，标准阿里 SDK 约定） |
| `AlipayQRCode.PayParam` | 1 个 string | 二维码支付参数（扫码） | 推断（高） |
| `Wechat.{appid,partnerid,prepayid,noncestr,timestamp,packageValue,sign}` | 7 个 string | **微信支付 App 调起参数**（`PayReq` 七元组） | 实测字段名即微信官方字段名，**高** |
| `WechatQRCode.PayParam` | 1 个 string | 微信扫码 | 推断（高） |
| `Bilibili.{out_trade_no,total_fee,game_money,notify_url,order_sign}` | 5 个 | B 站渠道下单参数 | 推断（中） |
| **`Order.{OrderNo, Amount, PayState, DeliveryState, FirstPurchase, PayType}`** | 6 个 | **状态载体**：`PayState`=支付状态、`DeliveryState`=发货状态 | 推断（中高） |

### ★ 哪个字段能让客户端"判定支付成功"

**不是那 5 个渠道字段，而是 `Order.PayState` / `Order.DeliveryState`。**

依据：
1. dex 里存在 `getOrderDetail`（客户端**有**查订单状态的能力）；
2. 游戏的 billing 任务类名是 **`BillingCheckPurchaseStateTask`**（type[3086]，7 字段）——
   "check purchase state" 这个命名说明流程是**轮询订单状态**，而不是等渠道回调；
3. `Order` 里的 `PayState` / `DeliveryState` 就是被轮询的对象。

⇒ **实现假支付的最短路径：让 `/order/create`（以及随后的 `/order/detail`）返回
`Order{ PayState: <已支付>, DeliveryState: <已发货> }`**，客户端就会认为支付完成。

> ⚠️ **`PayState` / `DeliveryState` 的具体取值（0/1/2）我拿不到** —— 这些是 `int` 常量，
> 在 `ApiService`/`BillingCheckPurchaseStateTask` 的代码里，而那两处都未反编译。
> **需要一次真机观测**（买一次，抓 `/order/create` 的官方响应，看 `PayState` 的值）。这是唯一还缺的数据。

## 6. 商品 id 的来源（实测）

`BillingTransactionStartByYostarRequest`（type[10798]，3 字段）：

```java
long  ShopCashId;                              // ★ 商品 id，与游戏内 ShopCashId 一致
List<ShopCashProductSelectionDBs> ...;         // 商品选择项（可选礼包）
bool  VirtualPayment;                          // 虚拟支付标记
```

⇒ **游戏侧用的是 `ShopCashId`（long）**，就是商城里的商品 id。
但 **SDK 的 `/order/create` 传的是 `ProductId`（int）** —— 两者不是同一个值。

**推断（中）**：SDK 的 `ProductId` 来自 `OrderProductsEntity.ProductItems[].ID`（该结构里有
`ID`/`GameProductID`/`StoreProductID` 三个 id，`ID` 是 SDK 内部商品 id）。
游戏侧 `ShopCashId` → SDK `ProductId` 的映射表**必须在 SDK 服务端（我们）维护**，
或者由 `/order/products` 下发时对齐。

> **⇒ 这条对 lead 的 Q7 的回答**：**客户端的商品标识是"两个 id"**——
> 游戏协议层用 `ShopCashId`(long)，SDK 层用 `ProductId`(int)。
> **不能仅凭 `ShopCashId` 就断定收到哪个商品**，中间需要一张映射表（我们自己是服务端，可以自建）。

## 7. paySuccess 之后：奖励应该在哪一层发

### 7.1 游戏侧的 billing 协议（实测字段）

```java
class BillingTransactionStartByYostarRequest  { long ShopCashId; List<...>; bool VirtualPayment; }
class BillingTransactionStartByYostarResponse { long PurchaseCount; DateTime PurchaseResetDate;
                                                string MXSeedKey; ... PurchaseServerTag;
                                                string PurchaseServerCallbackUrl;   // ★
                                                string PurchaseOrderId; }
class BillingTransactionEndByYostarRequest    { EndType EndType; string PurchaseOrderId; }
class BillingTransactionEndByYostarResponse   { ParcelResult ParcelResult;   // ★ 发货载体
                                                MailDB MailDB;               // ★ 补发邮件
                                                List CountList; int PurchaseCount;
                                                List MonthlyProductList;
                                                BattlePassInfo BattlePassInfo;
                                                List BattlePassProductList; }
```

### 7.2 调用链（**推断，中强**）

```
用户点购买
  → 游戏侧 BillingCashShopTask(type[3082], 8 字段)
     → SDK: AiriHttpClientImpl.createOrder(OrderCreateReq{ProductId, PayType, ExtraData, NotifyURL})
        ← OrderCreateEntity{ Alipay.PayParam | Wechat.* | Order{...} }
     → 拉起支付宝/微信 → 用户支付
  → 游戏侧 BillingCheckPurchaseStateTask(type[3086], 7 字段)   ← 轮询
     → SDK: getOrderDetail  ← Order{PurchaseState / DeliveryState}
  → 游戏侧 发 Billing_TransactionStartByYostar
     ← 我们回 { PurchaseOrderId, PurchaseServerCallbackUrl, MXSeedKey, ... }
  → 游戏侧 发 Billing_TransactionEndByYostar{ EndType, PurchaseOrderId }
     ← 我们回 { ParcelResult, MailDB, CountList, ... }   ★★ 这就是发货
```

**证据等级**：
- `BillingCashShopTask` / `BillingCheckPurchaseStateTask` /
  `<<RequestBillingTransactionEndByYostar>g__Co_RequestBillingTransactionEndByYostar|0>d`
  三个类型名**实测存在**（il2cpp metadata，type[3082]/[3086]/[3080]）；
- 它们之间的**具体调用顺序**是**推断**（方法体在密文区，未反编译）。

### 7.3 ★ 结论：奖励应该在**游戏服务端**发

**依据（三条）**：

1. **发货载体在游戏协议里**：`BillingTransactionEndByYostarResponse` 有
   `ParcelResult` / `MailDB` / `CountList` —— 这三个正是游戏内发道具的通用载体。
   **SDK 侧没有任何"给游戏道具"的概念**（SDK 只产 `PayParam` 和 `Order` 状态）。
2. **客户端有专门的 billing 任务链**（`BillingCashShopTask` → `BillingCheckPurchaseStateTask`
   → `RequestBillingTransactionEndByYostar`），说明**发放在游戏层闭环**。
3. **我们的 SDK 服务端与游戏服务端都是我们自己**，但**职责边界必须按客户端的协议来**：
   SDK 服务端只负责"让客户端认为支付成功"，奖励必须由 29001 的响应下发，否则客户端不会刷新背包。

> **⇒ 实现位置：`Billing_TransactionEndByYostar`(29001) 的响应里发 `ParcelResult`。**
> SDK 服务端只需要把 `/order/create` + `/order/detail` 做成"立刻成功"。

## 8. 本轮拿不到的（明确写死）

| 项 | 原因 |
|---|---|
| `PayState` / `DeliveryState` 的**具体整数值** | `ApiService`/`BillingCheckPurchaseStateTask` 未反编译 |
| `OrderProductsReq` / `OrderDetailReq` / `OrderDetailEntity` 的字段 | 同上，jadx 未产出 |
| `SignProvider` 的签名算法 | 类未反编译；`AiriSgClient.sign` 是 native |
| 请求的 Content-Type / 是否 form | `ApiService` 未反编译（但 `ResponseMod` 是 JSON 信封，**推断**也是 JSON 请求） |
| 29000/29001 的真实触发链 | 方法体在 ACE 密文区 |

**唯一还缺的关键数据：`PayState`/`DeliveryState` 的取值。**
建议：**真机买一次 0 元/最小额商品，抓 `/order/create` 的官方响应**——一次就够，之后假支付就能 100% 对齐。
