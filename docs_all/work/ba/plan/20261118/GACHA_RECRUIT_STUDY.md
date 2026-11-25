# GACHA_RECRUIT_STUDY — 招募（抽卡）不可用：根因与修复方案

> 只读分析。**未改任何线上文件、未重启、未改数据库。**
> 版本：2026-11-18 22:xx

---

## 1. 现象

- 客户端 **招募（Gacha）** 页面不可用：无法选 banner、无法抽卡。
- 三天 wire 日志（11-14 / 11-17 / 11-18）中，客户端**从未发出** `Shop_BuyGacha`(10001) / `Shop_BuyGacha2`(10005) / `Shop_BuyGacha3`(10008) / `Shop_GachaRecruitList`(10006)（Lead 已核，采信）。
- 登录同步里内嵌的 `ShopGachaRecruitListResponse` 只有 `{"Protocol":10006,"ShopFreeRecruitHistoryDBs":[]}` —— **`ShopRecruits` 缺失**。

---

## 2. 证据

### 2.1 服务端确实从不填 `ShopRecruits`（已证实）

`Shittim-Server\Core\NetworkProtocol\Handlers\ShopHandler.cs:42-61`：
```csharp
42:  [ProtocolHandler(Protocol.Shop_GachaRecruitList)]
43:  public async Task<ShopGachaRecruitListResponse> GachaRecruitList(
...
50:      var recruitHistories = db.GetAccountRecruitHistory(account.ServerId).ToList();
51:      response.ShopFreeRecruitHistoryDBs = recruitHistories
...
58:          .ToList();
59:
60:      return response;          // ← ShopRecruits 从未赋值
61:  }
```
全仓 `Select-String "ShopRecruits"`（`Shittim-Server\**\*.cs`）**命中 0 处**。

DTO 定义（`Schale\MX\NetworkProtocol\NetworkProtocol.cs:6676`）：
```csharp
public class ShopGachaRecruitListResponse : ResponsePacket {
    public List<ShopRecruitDB>? ShopRecruits { get; set; }
    public List<ShopFreeRecruitHistoryDB>? ShopFreeRecruitHistoryDBs { get; set; }
}
```

`ShopRecruitDB`（`Schale\...\DBModel.cs:2273`）**只有 4 个字段**：
```csharp
public class ShopRecruitDB {
    public long Id { get; set; }
    public DateTime SalesStartDate { get; set; }
    public DateTime SalesEndDate { get; set; }
    public DateTime UpdateDate { get; set; }
}
```
> ⚠️ 注意：**"免费次数/剩余/已购买次数"不在这张 DTO 里**。它在 `ShopFreeRecruitHistoryDB`（`UniqueId / RecruitCount / LastUpdateDate`），由 `GachaRecruitList` 已正确填充。

### 2.2 官方一定返回这张表（已证实，有样本）

官方 1006 解码样本 `report\_tmp\official_decoded_201\02_1017_api_account_loginsync.response.json`
→ `inner.ShopGachaRecruitListResponse.ShopRecruits`：

```
count = 529
keys  = ["Id","SalesStartDate","SalesEndDate","UpdateDate"]
first = {"Id":5000000,"SalesStartDate":"2023-08-03T05:00:00","SalesEndDate":"2023-08-10T15:59:59","UpdateDate":"0001-01-01T00:00:00"}
second= {"Id":5000010,"SalesStartDate":"2023-08-03T05:00:00","SalesEndDate":"2023-08-10T15:59:59","UpdateDate":"0001-01-01T00:00:00"}
id range = 5000000 .. 99999999
id < 5,000,000 的条数 = 0
SalesStartDate 为空的条数 = 0
```
⇒ 官方**一次性下发全部历史 banner（含已过期）**，由客户端按当前时间过滤；`UpdateDate` 为 `DateTime.MinValue`（0001-01-01）。

### 2.3 我们的 Excel 表恰好对得上（已证实）

`work\ba\data\ExcelDB.db` → 表 `ShopRecruitDBSchema`：
```
total = 532
Id <  5,000,000 : 3   （ids = 1, 2, 3，legacy）
Id >= 5,000,000 : 529
```
**529 与官方条数完全一致**，且 3 条 legacy 正是官方不发的那些。

`ShopRecruitExcelT`（`Schale\Excel\ShopRecruitExcel.cs:307-`）关键列：
`Id / CategoryType / IsLegacy / SalePeriodFrom / SalePeriodTo / RecruitCoinId / PurchaseCountLimit / ...`
—— `SalePeriodFrom/To` 是**字符串**，现有代码用 `DateTime.Parse` 解析（`ShopRecruitExcelExt.cs:19-25`）。

### 2.4 客户端消费该字段（已证实其存在，消费逻辑未证实）

`work\ba\audit\ba-apk\out\metadata-strings.txt` 含：
```
ShopGachaRecruitListRequest / get_ShopRecruits / set_ShopRecruits
ShopFreeRecruitHistoryDBs / <ShopRecruits>k__BackingField
```
⇒ 字段确实被客户端读。但**"空列表 ⇒ UI 禁用"这一步没有反编译证据**，见 §3.2。

---

## 3. 结论

### 3.1 已证实
1. 服务端 `GachaRecruitList` 从不填 `ShopRecruits`（代码 + 全仓 grep）。
2. 官方每次登录同步/列表都返回 **529 条** banner（Id 全 ≥ 5,000,000）。
3. 我们的 Excel 里正好有 **529 条**对应的招募行（外加 3 条 legacy）。
4. 客户端确实定义了 `ShopRecruits` 的读写访问器。

### 3.2 推测（强，但非硬证）
**`ShopRecruits` 为空 ⇒ 招募页没有可展示的 banner ⇒ 用户无法发起抽卡。**
- 支持：官方必发 529 条；三天日志里客户端**一次都没发过**任何 `BuyGacha*`，与"卡在 UI 层"一致；`Shop_PickupSelectionGachaSet`(10015) 有过 2 次，说明招募界面**能打开**、但**选不到可抽取的 banner**。
- 缺口：没有 il2cpp 反编译证据表明客户端对 `null/[]` 是"禁用按钮"还是"空卡片列表"。**这条需真机验证**（见 §6）。

---

## 4. 修复方案（`GachaRecruitList` 填 `ShopRecruits`）

### 4.1 改前（`ShopHandler.cs:42-61`，现状）
```csharp
    [ProtocolHandler(Protocol.Shop_GachaRecruitList)]
    public async Task<ShopGachaRecruitListResponse> GachaRecruitList(
        SchaleDataContext db,
        ShopGachaRecruitListRequest request,
        ShopGachaRecruitListResponse response)
    {
        var account = await _sessionService.GetAuthenticatedUser(db, request.SessionKey);

        var recruitHistories = db.GetAccountRecruitHistory(account.ServerId).ToList();
        response.ShopFreeRecruitHistoryDBs = recruitHistories
            .Select(h => new ShopFreeRecruitHistoryDB
            {
                UniqueId = h.UniqueId,
                RecruitCount = h.RecruitCount,
                LastUpdateDate = h.LastUpdateDate
            })
            .ToList();

        return response;
    }
```

### 4.2 改后（在 `return response;` 之前插入）
```csharp
        // [FIX-GACHA-LIST] 官方每次都下发全部招募 banner（实测 529 条，Id 全 >= 5,000,000，
        // 含已过期档期，由客户端按时间过滤）。此前该字段从未赋值 => 招募页无 banner。
        var recruitBanners = _excelService.GetTable<ShopRecruitExcelT>()
            .Where(r => r.Id >= 5000000)
            .Where(r => !string.IsNullOrEmpty(r.SalePeriodFrom) && !string.IsNullOrEmpty(r.SalePeriodTo))
            .Where(r => DateTime.TryParse(r.SalePeriodFrom, out _) && DateTime.TryParse(r.SalePeriodTo, out _))
            .OrderBy(r => r.Id)
            .Select(r => new ShopRecruitDB
            {
                Id = r.Id,
                SalesStartDate = DateTime.Parse(r.SalePeriodFrom),
                SalesEndDate = DateTime.Parse(r.SalePeriodTo),
                UpdateDate = DateTime.MinValue      // 官方样本即为 0001-01-01
            })
            .ToList();

        response.ShopRecruits = recruitBanners;
```

### 4.3 依据
| 项 | 取值 | 依据 |
|---|---|---|
| 数据源 | `ExcelTableService.GetTable<ShopRecruitExcelT>()` | `ShopManager.cs:42` 已有同样调用；`ShopHandler` 已注入 `_excelService`（`:19/:28/:35`），**无需新增依赖** |
| 过滤 Id | `>= 5000000` | 官方 529 条全 ≥5e6；DB 里 <5e6 的 3 条是 legacy（1/2/3），官方不发 |
| 起止时间 | `SalePeriodFrom/To`（string → DateTime） | `ShopRecruitExcelExt.cs:19-25` 已在用同名字段 |
| `UpdateDate` | `DateTime.MinValue` | 官方样本首条即 `0001-01-01T00:00:00` |
| 顺序 | 按 Id 升序 | 官方样本 Id 单调（5000000, 5000010, 5000020…） |
| 免费次数 | 保持现状（`ShopFreeRecruitHistoryDBs`） | 现有实现已正确 |

---

## 5. `Shop_BuyGacha3`（10008）可用性与崩溃点

调用链：`BuyGacha3`(`ShopHandler.cs:254-321`) → `_shopManager.TryBuyStudent` → 否则 `ConsumeCurrency` → `CreateTenGacha`。

### 5.1 不会"进程崩"，但有几处会抛异常（客户端收到错误响应）
| 位置 | 代码 | 风险 |
|---|---|---|
| `ShopManager.cs:115-127` | `characterBanner == null` → 回退到 `CategoryType == NormalGacha` 的 banner；仍无 → `WebAPIException` | **有**：若 `req.ShopUniqueId` 不是 Excel 里的 Id，会被静默换成常驻池 banner（抽错池）或报错 |
| `ShopManager.cs:135` | `rateUpPickUp = _pickupDuplicateBonusExcels.GetPickupDuplicateBonusByShopId(req.ShopUniqueId)` | **有**：`PickupDuplicateBonusExcelExt.cs:7` 用 `First(...)`，**缺行直接抛 `InvalidOperationException`** |
| `ShopManager.cs:136` | `_characterExcels.GetCharacter(rateUpPickUp.PickupCharacterId)` | **有**：`CharacterExcelExt.cs:7` 也是 `First(...)`，Id 不存在即抛 |
| `ShopManager.cs:53-58` | `req.Cost == null` → 直接返回当前货币、**不扣费**，`gachaAmount` 固定 10 | 逻辑上"免费十连"；若客户端漏传 `Cost` 会被白嫖 |
| `ShopHandler.cs:287-305` | `ShopFreeRecruitHistories` 读写 | 正常 |

### 5.2 必须的入参校验（修好列表后建议加，防"一点就报错"）
```
① req.ShopUniqueId 必须 ∈ ShopRecruitExcelT.Id 且 Id >= 5000000（否则客户端拿到的 banner 与服务端不一致）
② 该 banner 的 SalePeriodFrom <= now <= SalePeriodTo
③ 非 NormalGacha 的 banner，必须存在 PickupDuplicateBonus 行（否则 First() 抛异常）
④ req.Cost 为空时按"无消耗"处理是现有行为，需业务确认是否保留
```
本轮**只读**，以上为建议，未改代码。

---

## 6. 协议号核对（问题 D 的答案：**没有不一致**）

客户端协议表 `work\ba\proto\protocol_map.json` vs 服务端 enum：

| 协议 | 客户端 id | 服务端 enum | dto_match | 结论 |
|---|---|---|---|---|
| `Shop_GachaRecruitList` | **10006** | `Shop_GachaRecruitList` | exact/exact | 一致 |
| `Shop_BuyGacha` | 10001 | 10001 | exact/exact | 一致 |
| `Shop_BuyGacha2` | 10005 | 10005 | exact/exact | 一致 |
| `Shop_BuyGacha3` | **10008** | 10008 | exact/exact | 一致 |
| `Shop_PickupSelectionGachaGet/Set/Buy` | 10014/10015/10016 | 同 | exact/exact | 一致 |

⇒ **CN 3.0.2 客户端与服务端招募协议号完全一致，不存在 enum 错位。** 招募不可用不是协议号问题。

---

## 7. 风险与回滚

| 风险 | 说明 | 缓解 |
|---|---|---|
| 列表过长 | 529 条 × 4 字段，登录同步体积增加（官方同样下发，客户端能处理） | 与官方一致，无需裁剪 |
| 日期解析失败 | 个别行 `SalePeriodFrom` 为空/格式异常 | 已用 `TryParse` 过滤，坏行跳过而不是抛 |
| Id 空间不符 | 若客户端只认某一段 Id（如 5e6 段） | 采用官方实测过滤条件 `>= 5000000`，与 529 条样本一致 |
| 抽卡时抛异常 | §5.1 的 `First(...)` | 部署后先用一次 `BuyGacha3` 实测；必要时加 §5.2 校验 |
| 回滚 | 删除 §4.2 插入的代码块即可（无 DB 迁移、无配置变更） | 一行 `git checkout -- ShopHandler.cs` |

---

## 8. 必须真机确认的点（客户端侧无法静态证明）

1. 填上 `ShopRecruits` 后，招募页是否**出现 banner 列表**（而不是仍然空白）；
2. 点击抽取时，客户端发出的 `ShopUniqueId` 是否等于我们下发的某个 `Id`（抓 `Shop_BuyGacha3`(10008) 请求体即可验证）；
3. 若客户端只认"当前时间在档期内"的 banner：我们的 Excel 档期多为 2023/2024，**可能需要把档期改到当前时间或让客户端忽略时间** —— 这一条决定"列表有数据但按钮仍灰"的可能性，**必须真机验证**。
