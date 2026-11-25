# 招募链路服务端侧穷举（2026-11-18）

> 作者：shittim-analyst　·　**只读取证**（未改线上、未重启、未动数据库）
> 源码：`work\ba\srv_src\Shittim-Server\`（`_srcbackup_gacha_20261118_2215\` 是 Lead 的备份目录，已排除）

---

## 0. 一句话结论

**服务端不存在"卡池必须存在才能抽"的校验；即使客户端发来一个本服 Excel 里没有的 `ShopUniqueId`（如 90000000），也不会报错 —— 它会静默回退到常驻池出卡。**
所以「按 10 连客户端一个包都不发」**不是服务端拒绝导致的**（服务端根本没机会拒绝）；但**一旦客户端发来，我们会抽错池、并把 RecruitCount 记到一个不存在的池 Id 上**。

---

## 1. `Shop_BuyGacha3(10008)` 完整入参消费链 + 异常点

调用链（全部 `ShopHandler.cs` / `ShopManager.cs`）：

```
ShopHandler.BuyGacha3                         ShopHandler.cs:345-412
 ├─ GetAuthenticatedUser                       :351
 ├─ _shopManager.TryBuyStudent(account, req)   :353   → ShopManager.cs:78-102
 │    ├─ _goodsExcels.FirstOrDefault(Id==req.GoodsId)        ShopManager.cs:81   （不抛，null 则 return null）
 │    ├─ goods.ParcelType.IndexOf(ParcelType.Character)      :85    （null 已在上一步挡住）
 │    ├─ ConsumeCurrency(context, account, req)              :89
 │    └─ _characterExcels.GetCharacter(goods.ParcelId[slot]) :91    ★可能抛
 ├─ ConsumeCurrency(account, req)               :369   （走直抽路径时）
 ├─ CreateTenGacha(account, req, gachaAmount)   :373   → ShopManager.cs:104+
 │    ├─ _shopRecruitmentExcels.FirstOrDefault(x => x.Id == req.ShopUniqueId)   ShopManager.cs:115  （**不抛**）
 │    ├─ 找不到 ⇒ 回退 NormalGacha 常驻池        ShopManager.cs:121
 │    ├─ 连常驻池都没有 ⇒ throw WebAPIException(DataEntityNotFound)  ShopManager.cs:124  ★
 │    ├─ banner 非 NormalGacha ⇒ GetPickupDuplicateBonusByShopId  ShopManager.cs:135  ★可能抛
 │    └─ GetCharacter(rateUpPickUp.PickupCharacterId)              ShopManager.cs:136  ★可能抛
 ├─ GetAccountRecruitHistory + FirstOrDefault   :378-396（不抛，null 则新建行）
 ├─ UpdateMissionProgress(Reset_GachaCount)     :400-404
 └─ SaveChanges                                 :409
```

### 异常点清单（`ShopUniqueId=90000000` 会怎样）

| 行 | 代码 | 行为 |
|---|---|---|
| `ShopManager.cs:115` | `_shopRecruitmentExcels.FirstOrDefault(x => x.Id == req.ShopUniqueId)` | **`FirstOrDefault` ⇒ 不抛**，得 `null` |
| `ShopManager.cs:121` | `characterBanner = _shopRecruitmentExcels.FirstOrDefault(x => x.CategoryType == ShopCategoryType.NormalGacha)` | 回退常驻池 |
| `ShopManager.cs:124` | `throw new WebAPIException(WebAPIErrorCode.DataEntityNotFound, ...)` | **只有当 Excel 里连 NormalGacha 行都没有时才抛** |
| `ShopManager.cs:119` | `Console.WriteLine("[ShopManager] Shop ID ... not found. Available IDs: ...")` | 每次都会打一行日志（可用于线上判定是否真的被回退） |

**⇒ 结论【已证实】**：`ShopUniqueId=90000000`（本服 717 行 Excel 无此 Id）**不会抛异常**，会：
1. 打一行 `[ShopManager] Shop ID 90000000 not found. Available IDs: ...`；
2. **按常驻 NormalGacha 池出卡**（错误池！）；
3. 在 `ShopFreeRecruitHistories` 里**按 `UniqueId=90000000` 建一行**（`ShopHandler.cs:383-390`）。

### 真正会抛的两处

| 行 | 条件 | 后果 |
|---|---|---|
| `ShopManager.cs:91` → `CharacterExcelExt.cs:7-8` `characterExcels.First(...)` | 学生兑换 goods 的 `ParcelId[slot]` 不在 `CharacterExcel` | `InvalidOperationException` ⇒ 500 |
| `ShopManager.cs:135-136` | `ShopUniqueId` 命中一个**非 NormalGacha** 的 banner，但其 pickup 角色/加成行缺失 | `First(...)` 抛 ⇒ 500 |
| `ShopManager.cs:472` | `throw new WebAPIException(ShopExceedPurchaseCountLimit, ...)` | 购买次数超限（正常业务错） |

> `TryBuyStudent` 先查 `GoodsId`（`:81`），`req.GoodsId` 为 0 或无此行 ⇒ 返回 `null` ⇒ 走普通抽卡路径，**不抛**。

---

## 2. 服务端有没有"卡池必须存在才允许抽"的前置校验？

**没有。【已证实】**

- `ShopHandler.cs` 全文 grep `OpenCondition` / `ContentSave` / `Resetable` ⇒ **0 命中**（该文件里唯一相关的是注释）。
- `Shop_GachaRecruitList`（`:42-66`）只读表 + 回 DB，不做任何开放校验。
- `BuyGacha3` 唯一与"池"有关的判断是 `ShopManager.cs:115` 的 `FirstOrDefault` + 回退（见上）。
- ⇒ **只要客户端发 `Shop_BuyGacha3`，服务端一定回 200（除非上面那两处抛异常）。**

---

## 3. `ShopFreeRecruitHistoryDB` 全部读写点

| 类型 | 位置 | 说明 |
|---|---|---|
| **写（建行/累加）** | `ShopHandler.cs:331-337`（BuyGacha2） | `UniqueId = request.ShopUniqueId`，`RecruitCount += gachaAmount` |
| **写** | `ShopHandler.cs:383-396`（BuyGacha3） | 同上 |
| **写** | `ShopHandler.cs:496`（PickupSelectionGachaBuy） | 同上 |
| **读** | `ShopHandler.cs:50-58`（`Shop_GachaRecruitList`） | 转成 `ShopFreeRecruitHistoryDB` 列表下发 |
| **读（写死空）** | `AccountHandler.cs:508-513`（LoginSync） | `ShopFreeRecruitHistoryDBs = []` **常量**，与官方样本一致（官方也是 `[]`） |
| 模型 | `Schale\Data\GameModel\ProgressModel\ShopFreeRecruitHistoryDB.cs:6` / `:26`（`GetAccountRecruitHistory`） | 列：`UniqueId` / `RecruitCount` / `LastUpdateDate` |
| DbSet | `Schale\Data\SchaleDataContext.cs:57` / `:278` | — |
| DTO | `Schale\MX\GameLogic\DBModel\DBModel.cs:2234`；`NetworkProtocol.cs:6624`（`ShopBuyGacha3Response.FreeRecruitHistoryDB`）、`:6680`（List）、`:6802`（另一个响应） | — |

**语义【已证实·代码】**：它就是"**按 ShopUniqueId 记录抽卡次数**"的表，只在**抽卡时**建行；`Shop_GachaRecruitList` 与 LoginSync 都不主动为每个池建行。
⇒ **无需按卡池预先建行**；客户端拿到空列表是正常的（官方 1017 样本也是 `[]`）。

---

## 4. `ItemListResponse` 补进登录同步的副作用

| 项 | 判断 |
|---|---|
| 官方 1017 是否带 | **不带**（前轮已核：官方 LoginSync 无该子包；我们的注释 `AccountHandler.cs` 里也写了"official has NO ItemListResponse child"） |
| 我们的风险 | ①**多发一个官方不发的子包**，客户端若严格按官方形状解析，可能忽略（安全）或影响背包缓存；②若 `ItemDBs` 里含**客户端 Excel 解析不到的道具 Id**，按"未知 id 会让整页/整同步失败"的既往规律（角色 Id 那次），**存在风险**；③`UpdateTime`/`StackCount` 为 0 的异常行也会被带出去 |
| 结论 | **【存疑·中低风险】**。建议：①维持现状观察；②若后续出现"登录后背包异常/登录偶发失败"，**第一件事就是把 ItemListResponse 摘掉**（一行）再复测 |

---

## 5. 让客户端认为"卡池可抽"，服务端还缺什么

### 5.1 `ShopGachaRecruitListResponse`（`NetworkProtocol.cs:6676-6681`）

| 字段 | 我们 | 说明 |
|---|---|---|
| `ShopRecruits` | **已填**（`ShopHandler.cs:62` → `BuildRecruitBanners`：优先 `Data/GachaRecruitBanners.cn.json` 529 条官方号段，Excel 兜底） | 每个 `ShopRecruitDB` 4 字段：`Id` / `SalesStartDate` / `SalesEndDate` / `UpdateDate` |
| `ShopRecruits[].UpdateDate` | **恒 `DateTime.MinValue`（0001-01-01）**（`ShopHandler.cs:100`） | 与官方样本一致（官方也是 0001-01-01）【已证实·样本】 |
| `ShopFreeRecruitHistoryDBs` | **已填**（DB 行；新号为 `[]`） | 与官方一致 |

### 5.2 `ShopBuyGacha3Response`（`NetworkProtocol.cs:6621-6627`，继承 `ShopBuyGacha2Response`）

| 字段 | 我们 | 说明 |
|---|---|---|
| `GemBonusRemain` / `GemPaidRemain` | ✔ 填（`:357-358` / `:370-371`） | — |
| `GachaResults` | ✔ 填 | — |
| `AcquiredItems` | ✔ 填 | — |
| `UpdateTime` | ✔ 填 | — |
| `ServerTimeTicks` | ✔ 填（`:363`/`:407`） | ✅ 用账号时钟，**不是**总力战那种赛季时间 |
| `MissionProgressDBs` | ✔ 填（`:406`；空则 null） | — |
| **`FreeRecruitHistoryDB`** | **恒 `null`** —— **全 handler 从未赋值**（`:355-412` 内无该字段） | ⚠️ 官方是否回这个对象**未知**（无 10008 官方样本）。若客户端拿它刷新"免费十连剩余次数"，null 可能让按钮保持灰 |
| `PickupFirstGetHistoryDBs` | **恒 `[]`**（`:398` 常量） | 官方语义是"首次获得角色的领取记录"，我们没有任何 pickup 首获逻辑 ⇒ 恒空 |

### 5.3 `ShopPickupSelectionGachaGetResponse`（`NetworkProtocol.cs:6774-6778`）

| 字段 | 我们 | 说明 |
|---|---|---|
| `PickupCharacterSelection` | **恒空字典**（`ShopHandler.cs:425`，注释写"客户端接受空 map"） | 若客户端**只在选择过角色后才启用"抽"按钮**，空 map 就会让按钮保持灰 —— 这是一个**未经样本验证的假设**（无 10014 官方样本）【推测】 |

### 5.4 服务端之外的可能（供 Lead 排期参考，不属本文件结论）

客户端"按 10 连完全不发包"更像**客户端本地按钮状态**问题：卡池项能否点击取决于它本地的 `ShopRecruitDB` 匹配（Id/SalesEndDate 是否已过期）+ 本地"免费十连/券"状态。**我们在 5.2/5.3 两个恒默认字段上确实留了缺口**，但这两者只有**发出请求后**才会用到，**解释不了"一个包都不发"**。

---

## 6. 建议的三个可验证实验（不改代码优先）

1. **确认客户端到底认哪套池 Id**：把 `GachaRecruitBanners.cn.json` 与 Excel 两套 Id 同时下发（现状已是），然后让用户点一次"10 连"，看 nginx 是否出现 `POST /api/shop/buygacha3`。**若出现** ⇒ 服务端链路能覆盖，问题只在客户端的"可抽"判定；**若不出现** ⇒ 客户端在本地就把按钮禁用了（转 il2cpp-analyst）。
2. **一旦出现请求**：看服务器控制台是否打出 `[ShopManager] Shop ID <X> not found` —— 若打出，说明客户端认的 Id 与我们下发的池 Id 不是同一套（我们回退了常驻池）。
3. **看 `ShopFreeRecruitHistories` 是否多出一行 `UniqueId=90000000`** —— 出现即证明第 2 点。
