# Shop_List 500 空指针修复（ShopManager.GetShopList）

- 时间：2026-11-19
- 改动文件：`Shittim-Server/Services/ShopManager.cs`（**唯一**改动的源文件，+11 / −1 行）
- 构建产物：`_build_shoplistnre/Shittim-Server.dll`，sha256 `e90867e2b6c75efdb07ff3bc7ea53fb597e3904a588fbab0fb2212f1c50e632b`，**2,680,320 字节**
- `_build_shoplistnre/Schale.dll`：sha256 `b06f46090f9d8eb8657e51401b789178d9090ad5a5a6d6d1faaa791dad429858`（要求值，**未变**）
- 部署状态：**未部署**（详见 §7）

---

## 0. 一句话结论

`ShopHandler.List` 把 `request.CategoryList` 原样传进 `ShopManager.GetShopList`，而
`ShopListRequest.CategoryList` 是**可空字段**、网关用 **Newtonsoft** 直接反序列化包体——**字段缺省时得到的是 `null`，不是空列表**。
`GetShopList` 旧 392 行用 `foreach` 直接遍历它，`reqCategoryList == null` 时 `List<T>.GetEnumerator()` 抛
`NullReferenceException`，**异常帧就是 `GetShopList` 本身**（无更深的帮助方法帧），与线上堆栈逐字吻合。

卡池清单被砍到 5 条后，客户端这一次 `Shop_List` 不再携带分类列表（空集合被序列化器省略），这个一直存在的空指针第一次被真正打中。

---

## 1. 根因

### 1.1 触发点：`reqCategoryList` 为 null（旧 392 行 / 新 399–400 行）

改动前原文（`Shittim-Server/Services/ShopManager.cs:382-398`）：

```csharp
382:    public async Task<List<ShopInfoDB>> GetShopList(
383:        SchaleDataContext context,
384:        AccountDBServer account,
385:        List<ShopExcelT> shopExcel,
386:        List<ShopCategoryType> reqCategoryList)
387:    {
388:        var dateTime = account.GameSettings.ServerDateTime();
389:        var purchases = context.GetAccountShopPurchases(account.ServerId).ToList();
390:
391:        List<ShopInfoDB> CategoryList = [];
392:        foreach (ShopCategoryType shopCategoryType in reqCategoryList)   // ← 这里：reqCategoryList == null 时抛 NRE
393:        {
```

### 1.2 为什么它是 null（三处代码各自可验证）

| # | 事实 | 证据 |
|---|---|---|
| ① | 请求 DTO 的字段**可空、无默认值** | `Schale/MX/NetworkProtocol/NetworkProtocol.cs:6628-6632`：`public class ShopListRequest : RequestPacket { … public List<ShopCategoryType>? CategoryList { get; set; } }` |
| ② | 网关用 **Newtonsoft** 绑包体，**字段缺省 = null** | `Shittim-Server/Controllers/Api/GatewayController.cs:215`：`var payload = (RequestPacket)JsonConvert.DeserializeObject(payloadStr, requestType)!;` — Newtonsoft 不会为缺失的集合属性创建空列表 |
| ③ | 消费方**直接 `foreach`，没有判空** | 上面的 392 行；`reqCategoryList.Count` / `?? []` / `Any()` 之类的保护一处都没有 |

也就是说：**服务端把"没有分类"这一语义只当作"空列表"处理，而线路上"没有分类"是以"字段缺席"（null）到达的。**

### 1.3 为什么堆栈顶端只有 `GetShopList`（对得上线上日志）

`GetShopList` 方法体内能被 null 打中的解引用只有三处，逐一排除：

| 解引用 | 若为 null 的异常帧 | 是否与线上栈吻合 |
|---|---|---|
| `shopExcel.GetNonSaleShopExcel()`（旧 395 行） | 会先进 `Schale.Excel.ShopExcelExt.GetNonSaleShopExcel`（LINQ 调用不可内联），栈里应多一帧 | ✗ 不吻合 |
| `account.GameSettings.ServerDateTime()`（旧 388 行） | 属性 getter 必内联，`ServerDateTime()` 很小也可能内联，理论上可只有一帧 | ✗ **被日志排除**，见下 |
| `foreach (… in reqCategoryList)`（旧 392 行） | `List<T>.GetEnumerator()` 为 null → 异常在 `GetShopList` 帧内抛出，**不需要任何内联假设** | ✓ 完全吻合 |

**`GameSettings` 被排除的硬证据**：同一窗口内 `Account_LoginSync` 返回 200，而 `AccountHandler.cs:466-473` 在
LoginSync 响应里同样解引用 `account.GameSettings.ServerDateTime()`：

```csharp
466:                CurrentSeasonId = account.ContentInfo.ArenaDataInfo.SeasonId,
...
470:                    ?? account.GameSettings.ServerDateTime(),
473:                DailyRewardActiveTime = account.GameSettings.ServerDateTime()
```

若该账号的 `GameSettings` 为 null，`Account_LoginSync` 会先崩，事故日志里就不会只有 `Shop_List` 一条 NRE。
（`GameSettings` 为 null 的真实可能性仍然存在，属于**同帧同类隐患**，本次一并加了防御，见 §2 第 2 项。）

`purchases` / `product` / `history` 也不成立：`purchases` 是 `ToList()` 出来的 `List`；`product` 来自 `List`；
`history` 在旧 403–407 行有 `history != null &&` 保护。

### 1.4 为什么"卡池清单 529 → 5"会触发（链路，已证实/推断分开写）

**已证实（代码 + 抓包）**

1. 正常态下客户端**是带** `CategoryList` 的——本机 wire 抓包
   `work/ba/srv_live/20261118_2210/wire-2026-11-18.txt.gz`，`# 03:14:24.045 Shop_List`：
   ```
   {"Protocol":10002,"CategoryList":[0,36,37,1,21,2,33,10,25,26,20],"Resendable":true, ... }
   ```
   官方样本同样带：`work/ba/proto/_out_params.txt` `seq=86 proto=10002 Shop_List {"CategoryList": [38]}`。
   ⇒ 该字段**平时有值**，所以这个空指针平时永远打不到。
2. 服务端这一侧对"空分类集合"没有任何容忍：要么 `[]`（能跑，循环 0 次），要么 `null`（NRE）。
   **`null` 与 `[]` 在本方法里的语义本应完全等价，但代码只实现了后者。**

**推断（客户端行为，服务端无法直接观测，标注清楚）**

3. 客户端在卡池清单只剩 5 条时，商店页可打开的分类集合塌缩为空，于是序列化时**空数组字段被省略**，
   请求变成 `{"Protocol":10002,"SessionKey":…}` 这样不带 `CategoryList` 的包体 → 服务端得到 `null` → 500。
   与"529 条时该字段恒有 11 个分类、恢复 529 条后 NRE 归零"的观测一致。

**明确否定的猜想**：本次**不是**"按卡池 id 去另一张表查一行然后直接用"炸的。
`GetShopList` 全文只读两张表——`ShopExcelT`（参数传入）与 `ShopPurchaseHistories`（唯一查询），
**没有任何卡池/招募表查询**，没有 `First()/Single()/[0]`，也没有 `BuildRecruitBanners`/`GachaRecruit` 引用
（`grep` 结果：`ShopManager.cs` 里这些符号只出现在 `CreateTenGacha` / `SimulateGacha` / 构造函数，均不在 `GetShopList` 调用链上）。
卡池 JSON 只经 `ShopHandler.BuildRecruitBanners` 进 `ShopRecruits` 响应字段，不参与商店同步。

---

## 2. 改了什么（文件 + 行 + diff 原文）

唯一改动文件：`Shittim-Server/Services/ShopManager.cs`
（对照基线：`work/ba/srv_src_orig/Shittim-Server/Services/ShopManager.cs`，改前 sha256 `466b3d21…`）

```diff
diff --git a/Shittim-Server/Services/ShopManager.cs b/Shittim-Server/Services/ShopManager.cs
@@ -385,10 +385,20 @@ public class ShopManager
         List<ShopExcelT> shopExcel,
         List<ShopCategoryType> reqCategoryList)
     {
-        var dateTime = account.GameSettings.ServerDateTime();
+        // GameSettings is a JSON-converted column (SchaleDataContext.HasJsonConversion). EF Core never hands a NULL
+        // column to a value converter, so a NULL Accounts.GameSettings materializes null instead of the `= new()`
+        // initializer; fall back to the same wall-clock value ServerDateTime() returns for a default settings row.
+        var dateTime = account.GameSettings?.ServerDateTime() ?? DateTime.Now;
         var purchases = context.GetAccountShopPurchases(account.ServerId).ToList();
 
         List<ShopInfoDB> CategoryList = [];
+
+        // CategoryList is nullable on the wire (ShopListRequest.CategoryList) and GatewayController binds the body
+        // with JsonConvert, so a Shop_List that omits the field arrives as null rather than an empty list. "No
+        // categories requested" is the same sync as "no categories present": return the empty list, don't throw.
+        if (reqCategoryList == null)
+            return CategoryList;
+
         foreach (ShopCategoryType shopCategoryType in reqCategoryList)
         {
             var ShopProductList = new List<ShopProductDB>();
```

### 逐项说明

| 项 | 位置（新行号） | 改了什么 | 为什么 |
|---|---|---|---|
| **主修**（根因行） | 396–400 | `reqCategoryList == null` 时**早退**，返回空 `CategoryList` | null 与 `[]` 在语义上都是"这次没有要同步的分类"。早退 = 跳过而不是抛异常，500 变成 200 + 空 `ShopInfos`，客户端不再判同步失败。没有用 try/catch 吞异常。 |
| **同帧同类隐患** | 388–391 | `account.GameSettings?.ServerDateTime() ?? DateTime.Now` | `GameSettings` 是 **JSON 转换列**（`SchaleDataContext.cs:119` `Property(x => x.GameSettings).HasJsonConversion()`）。EF Core 的值转换器**不处理 NULL**：列是 SQL NULL 时属性直接物化为 `null`，`= new()` 初始化器被覆盖 → 旧 388 行会 NRE，且同样只有 `GetShopList` 一帧。兜底值取 `DateTime.Now`，与 `ServerDateTime()` 非强制时间分支返回的"墙钟时间"同义；本项目已有同样写法（`GatewayController.cs:351`）。 |

> 说明：两处都是**只在缺数据时才生效**的前置判断，没有重构、没有改字段名、没有格式化周边代码（文件仍是纯 LF，507 行）。

---

## 3. 为什么正常 529 条路径**输出完全不变**（逐条论证）

1. **改动范围**：`work/ba/srv_src` 与基线 `srv_src_orig` 逐文件哈希比对——开工前 `ShopManager.cs` 与基线**逐字节一致**，
   本次改动后只多出它一个 DIFF（清单里其余 DIFF 是 11-17/18 的历史改动，开工前就存在，非本次引入）；
   `Schale` 工程零改动——产物 `Schale.dll` 的 sha256 仍为 `b06f4609…`（要求值），可反证。
2. **第 1 处守卫不改变取值**：`account.GameSettings?.ServerDateTime() ?? DateTime.Now`
   在 `GameSettings != null`（正常路径）时 `?.` 调用一次且仅一次 `ServerDateTime()`，`??` 不参与 → 得到的 `DateTime`
   与改前**逐 tick 相同**；无额外副作用、无额外分配、无异常语义变化。
3. **第 2 处守卫不改变控制流**：`reqCategoryList != null`（正常路径）时不进入 `if`，`foreach` 的迭代源、顺序、次数与改前完全一致。
4. **即使进入早退分支也与"空列表"等价**：旧代码在 `== []` 时同样是"循环 0 次后返回空列表"；新代码返回的
   `CategoryList` 就是旧 391 行刚构造的那个空 `List<ShopInfoDB>`（同一类型、同一引用语义），后续 `ShopHandler.List`
   把它赋给 `response.ShopInfos`——即旧的"零次迭代"结果。
5. **循环体一行未动**：`GetNonSaleShopExcel` / `GetAssignedSaleShopExcel().GetTimelinedShopExcel(dateTime)` /
   `Concat` + `DistinctBy(x => x.Id)` / `GetCategorizedShopExcel` 的调用顺序未变；`ShopProductList` 的
   `ShopExcelId/Category/DisplayOrder/PurchaseCount/SoldOut/PurchaseCountLimit/ProductType` 赋值与
   `PeriodStart(...)` 判定未变；`ShopProductList.Count != 0` 的分类过滤未变；`CategoryList` 的分类顺序与条数未变。
6. **接口未动**：方法签名/参数顺序/返回类型未变；`ShopHandler.List`（`ShopHandler.cs:543`）未改；
   `ShopInfoDB` / `ShopProductDB` 的序列化字段（含"不发 `Price`"的既有约定）未改。
7. **结论**：卡池 529 条、数据正常时，`Shop_List` 的响应字节由完全相同的语句序列产生——**逐字节等价**。

---

## 4. 同类隐患审计（改了哪些 / 没改哪些，为什么）

`Shop_List` 之外，把"必须查到/必须非空"的假设逐个过了一遍：

| 位置 | 假设 / 风险 | 处理 | 理由 |
|---|---|---|---|
| `ShopHandler.cs:543` `_shopManager.GetShopList(db, account, shopExcels, request.CategoryList)` | 把可空字段直传 | **已修（在消费端 `GetShopList` 内）** | 根因就在这里落地；在 DTO 上给默认值会改变所有请求体的绑定行为，在 handler 加判空只是把守卫挪远，所以修在解引用那一行。 |
| `ShopManager.cs:405-406` `shopExcel.GetNonSaleShopExcel()` / `GetAssignedSaleShopExcel()` | `shopExcel == null` 会 NRE | **未改** | 数据源是 `_excelService.GetTable<ShopExcelT>()`（返回列表，不存在时为空列表而非 null），且若为 null，栈顶会是 `ShopExcelExt.GetNonSaleShopExcel`，与事故栈不符。 |
| `ShopHandler.cs:78-161` `BuildRecruitBanners` | 逐条读 `Id/From/To`，`GetProperty` 缺键会抛 `KeyNotFoundException` | **未改（已是防御式）** | 整个 JSON 解析块包在 `try/catch` 里，失败即 `Clear()` 并回落到 Excel 表；Excel 回落块同样 `try/catch`。无 `First()/Single()/[0]`，无解引用可空属性。**卡池 JSON 解析失败不会抛到协议层**。 |
| `ShopManager.cs:115-127` `CreateTenGacha` 按 `ShopUniqueId` 找卡池 | 找不到会怎样 | **未改（已是防御式）** | `FirstOrDefault(x => x.Id == …)` → 回落 `NormalGacha` → 仍没有则抛**受控**的 `WebAPIException(DataEntityNotFound)`，不是 NRE。 |
| `ShopManager.cs:135-136`（`CreateTenGacha`）/ `314-315`（`SimulateGacha`）`_pickupDuplicateBonusExcels.GetPickupDuplicateBonusByShopId(...)` + `_characterExcels.GetCharacter(...)` | **就是"按卡池 id 去另一张表查一行直接用"** | **未改（记录在案）** | 两个扩展方法内部是 `First(...)`（`PickupDuplicateBonusExcelExt.cs:9`、`CharacterExcelExt.cs:8`），缺行抛的是 `InvalidOperationException` 而**不是 NRE**；数据源是 Excel 表（`PickupDuplicateBonusExcelT` / `CharacterExcelT`），**不经 `GachaRecruitBanners.cn.json`**，所以本次故障与它无关。改它会把其它协议的异常类型/行为一起改掉，超出"只修这个 NRE"的边界。 |
| `ShopManager.cs:306-307` `SimulateGacha` 的 `?? _shopRecruitmentExcels.First(x => CategoryType == NormalGacha)` | 无兜底行时抛 `InvalidOperationException` | **未改（记录在案）** | 同上：非 NRE、Excel 数据源、`Audit_GachaStatistics` 路径，不在本事故链上。 |
| `ShopHandler.cs:559 / 761 / 845` `FirstOrDefault(x => x.Id == request.ShopUniqueId)` | 商城购买/刷新 | **未改（已是防御式）** | 都有 `if (shopExcel == null) throw new WebAPIException(ShopExcelNotFound, …)`，属于受控业务错误。 |
| `ShopManager.GetShopList` 的 `purchases` / `history` / `product` | 空集合 / 缺行 | **未改（已是防御式）** | `purchases` 恒为 `List`；`history` 有 `history != null &&`；`product` 来自 `List`。 |

**本轮改动合计：`Shittim-Server/Services/ShopManager.cs` 两处（1 处根因 + 1 处同帧同类隐患）。**

---

## 5. 编译

```powershell
cd "C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\srv_src"
& 'C:\Program Files\dotnet\dotnet.exe' publish Shittim-Server\Shittim-Server.csproj -c Release -o _build_shoplistnre --nologo
```

结果：**成功**（`EXITCODE=0`），只有 warning（`CS8632` / `CS0219 hasSSR` / `EF1002` 等历史 warning，无新增 error）。

### 产物

| 文件 | sha256 | 字节数 |
|---|---|---|
| `_build_shoplistnre/Shittim-Server.dll` | `e90867e2b6c75efdb07ff3bc7ea53fb597e3904a588fbab0fb2212f1c50e632b` | **2,680,320** |
| `_build_shoplistnre/Schale.dll` | `b06f46090f9d8eb8657e51401b789178d9090ad5a5a6d6d1faaa791dad429858` | 5,392,896 |
| `_build_shoplistnre/Shittim-Server.pdb` | `405687404be4a681e64b99b2fc555fdb913ea035291774bcd4cdb8d24ab67477` | 524,480 |

- `Schale.dll` **仍是要求值 `b06f4609…`**，与现行部署（`_build_picksel`）中的 `Schale.dll` 哈希一致 ⇒ 没有误改 Schale 工程。
- 现行部署的 `Shittim-Server.dll` 是 `2a98a2b3… 2,680,320 B`（`_build_picksel`）；本次产物 hash 不同是**预期**的（改了 `ShopManager`），字节数相同属正常（差异仅为几字节的 IL + 元数据对齐）。
- 源码文件：`Shittim-Server/Services/ShopManager.cs`，24,876 B，507 行，纯 LF，sha256 `5bc2d1deba973fa74ef0249c974bcbb9a9f42942375d02118cacdaad9223d52d`。

---

## 6. 部署后的验收方式（本次**未执行**，留给 srv-ops）

1. 部署 + `systemctl restart ba-shittim` 后，**先验登录**（Account_Auth → LoginSync → Item_List 全 200），再谈商店。
2. 用 5 条卡池复测：`POST /api/shop/list`（protocol 10002），**故意省略 `CategoryList`** —
   期望 **HTTP 200 + `ShopInfos: []`**（修复前是 500 / `NullReferenceException`）。
3. 带正常 `CategoryList`（如官方的 `[38]` 或客户端的 11 个分类）复测：`ShopInfos` 内容应与改动前**逐字节一致**。
4. 观察 `logs/log.txt` 中 `Error invoking handler for protocol "Shop_List"` 计数应为 **0**。

---

## 7. 未部署声明

- **没有部署**：未执行 `deploy.sh` / `scp` / `ssh` / `systemctl`，未连接 `<SERVER_IP>`，未向 `/www/wwwroot/ba_srv/` 写入任何文件。
- **没有重启任何服务**，没有改动 `GachaRecruitBanners.cn.json`（线上与本地仍是 529 条原样）、`shittim.sqlite3` / `BlueArchive.db`、`ExcelDB.db`、nginx、9097 桥。
- 本次只做了两件事：本机改 1 个 `.cs` 文件；本机 `dotnet publish` 到 `srv_src/_build_shoplistnre/`。
- 生产环境是否需要部署、何时部署、如何回滚，由 srv-ops 决定（建议部署前先备份现行 `Shittim-Server.dll` `2a98a2b3…` 与 `Data/GachaRecruitBanners.cn.json`）。
