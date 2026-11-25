# C# 侧：ID 卡未初始化修复（方案 + 提议补丁，未落地）

> 作者：shittim-analyst　·　2026-11-18　·　**只读分析 + 只出 diff**：未改 `srv_src`、未构建、未部署、未重启、未动数据库

---

## 0. 三条核实结论（先回答你的第一步）

### ① `BackgroundId` ↔ `CardBackgroundId`：**是同一个东西，而且写进去了**

```csharp
// FriendHandler.cs:147
147  card.CardBackgroundId = request.BackgroundId;
```
```csharp
// NetworkProtocol.cs:4332  FriendSetIdCardRequest
4332  public long BackgroundId { get; set; }
```
两个只是**成员名不同**（请求侧短名、DTO 侧带前缀），赋值是直连的。⇒ **不存在"Set 写不进、永远为 0"的问题**。`[已证实]`

> 对照组：`ShowMultiFloorRaidClearedDifficulty` **在请求 DTO 里（`:4331`）却没被 `SetIdCard` 写（`:137-147` 共 11 行赋值，唯独漏它）** ⇒ 这个开关**永远为 false**，是一个**独立的真 bug**（见 §4 B2）。

### ② 有没有更可靠的"从未保存过"标记？—— **没有专用标记，只能用"全体字段皆默认"来判定**

- `ContentInfoDB.IdCard = new()`（`ContentInfoDB.cs:21`）⇒ 新号 `Comment=null`、`CardBackgroundId=0`、`EmblemId=0`、**所有 `Show*`=false**、`SearchPermission/AutoAcceptFriendRequest`=false、Ranking 全 `null`。
- `ContentInfo` 是**一个 JSON 列**，没有版本号字段、没有 `IsConfigured` 布尔；`FriendIdCardDB` 22 个字段里也没有任何"初始化时间/标记"。
- **最可靠的单一判据是 `Comment == null`**：`SetIdCard` 执行 `card.Comment = request.Comment`（`:137`），只要客户端保存过一次，`Comment` 就从 `null` 变成 `""` 或字符串（JSON 往返会保留 `""` 与 `null` 的区别）。
- **建议判据 = `Comment == null` 且 其余配置项全为默认值**（双条件，避免"老数据 Comment 为 null 但其实配过"的极端情况）：
```csharp
Comment == null && CardBackgroundId == 0 && EmblemId == 0
&& !SearchPermission && !AutoAcceptFriendRequest
&& !ShowAccountLevel && !ShowFriendCode && !ShowRaidRanking
&& !ShowArenaRanking && !ShowEliminateRaidRanking
&& !ShowMultiFloorRaidClearedDifficulty
```

### ③ 现网账号 2 的 IdCard 实际值 —— 本机查不到，请 srv-ops 跑这条

本机没有 `shittim.sqlite3`（只有 ExcelDB），无法查。`ContentInfo` 是 TEXT(JSON) 列：
```sql
SELECT ServerId, Nickname,
       json_extract(ContentInfo, '$.IdCard.Comment')            AS comment,
       json_extract(ContentInfo, '$.IdCard.CardBackgroundId')   AS bg,
       json_extract(ContentInfo, '$.IdCard.EmblemId')           AS emblem,
       json_extract(ContentInfo, '$.IdCard.SearchPermission')   AS search_perm,
       json_extract(ContentInfo, '$.IdCard.ShowAccountLevel')   AS show_lv,
       json_extract(ContentInfo, '$.IdCard.ShowFriendCode')     AS show_fc
FROM Accounts WHERE ServerId = 2;
```
判读：全 `NULL/0` ⇒ 从未保存过（正是本 bug）；`bg` 非 0 或 `comment` 非 null ⇒ 用户保存过，那问题就不在"未初始化"而在别处（须回头查）。

---

## 1. 方案 A（推荐）vs 方案 B

| | 方案 A：读取时补默认（**不写库**） | 方案 B：建号时初始化并落库 |
|---|---|---|
| 改动点 | 只改 `FriendHandler.GetIdCard`（+2 个私有静态方法） | 改 `AccountService.InitializeCompleteAccount` + `GetIdCard` 兜底 |
| 迁移 | **零迁移**；现网账号下次进 ID 卡页面自动生效 | 需给**存量账号**补一次数据（SQL 或一次性脚本） |
| 回退 | 删掉 2 个方法 + 1 行分支即回到现状 | 要回退得再改存量数据，**回退成本高** |
| 一致性 | 每次读都算一次（纯内存，可忽略） | 一次写入，之后恒一致 |
| 风险 | **不落库** ⇒ 用户"改了没保存"的预期不变；但也意味着**永不持久**，每次都是默认值 | 若默认值判错，会把错误值**永久写进账号** |
| 结论 | **✅ 推荐**（与你倾向一致） | 留作二期（等默认值经实测确认后，再改成"首次读取时写回"） |

---

## 2. 方案 A 的默认值清单（逐项给依据）

| 字段 | 建议默认 | 依据 / 强度 |
|---|---|---|
| `ShowAccountLevel` | **true** | 用户报的 prefab 里 `Lv. 72` 是**展示态**；私有服希望卡片有信息。`[推断]`（无官方抓包） |
| `ShowFriendCode` | **true** | 同上，prefab 明确展示 `好友码：AAAAAAAAAA` `[推断]` |
| `ShowRaidRanking` | **true** | prefab 有 `100,000 ×2` 这类排名位；且无数据时值为 null，客户端会显示"—"或留空，不会崩 `[推断]` |
| `ShowArenaRanking` | **true** | 同上 `[推断]` |
| `ShowEliminateRaidRanking` | **true** | 同上 `[推断]` |
| `ShowMultiFloorRaidClearedDifficulty` | **true** | 同上；⚠ 同时要修 **B2**（否则这个开关用户永远存不住） |
| `Comment` | **`""`（空串）** | 不与 `AccountDB.Comment` 混用（那是账号签名，语义不同）。空串让客户端渲染空文本区，而不是 prefab 的 `Schale's Teacher`。`[推断]`；**若实测空串仍显示 prefab，改用 `" "`（单空格）** |
| `CardBackgroundId` | **1** | `0` 很可能被客户端当作"未设置"从而落回 prefab；1 是自然首项。**⚠ 需先用 Excel 核对 `IdCardBackgroundExcel` 是否存在 `Id=1`**（本机 ExcelDB 未解这张表，标 `未证实`） |
| `EmblemId` | **0** | 0 = 无徽章；不伪造 `OFFICIAL`（prefab 里那个 `OFFICIAL` 是占位，给真值反而更怪） `[推断]` |
| `RepresentCharacterUniqueId` | 保持现有逻辑 | 已有 `:120-121` 从 `account.RepresentCharacterServerId` 兜底 `[已证实]` |
| `RepresentCharacterCostumeId` | **0** | 无服装；客户端按 0 走默认立绘 `[推断]` |
| `ArenaRanking` / `RaidRanking` / `EliminateRaidRanking` | **null** | 三者在 DTO 里是 `Nullable<T>`（`DBModel.cs:1405/1406/1408`）⇒ **设计上"无数据"就是 null**；给 0 会被当"第 0 名" `[已证实·类型]` |
| `RaidTier` / `EliminateRaidTier` / `MultiFloorRaidClearedDifficulty` | **null** | 同上（`Nullable<int>`，`:1407/1409/1410`）`[已证实·类型]` |
| `SearchPermission` | **true** | 私有服人少，默认可被搜到；`false` 会让好友搜索形同虚设 `[推断]` |
| `AutoAcceptFriendRequest` | **false** | 自动同意好友是社交决定，默认关更安全 `[推断]` |

> 所有 `[推断]` 项都建议**上线前先在测试账号上肉眼验一遍**，确认后可以改成方案 B（读时补齐 + 写回），把默认值固化。

---

## 3. 提议补丁（unified diff，**未应用到 srv_src**）

```diff
--- a/Shittim-Server/Core/NetworkProtocol/Handlers/FriendHandler.cs
+++ b/Shittim-Server/Core/NetworkProtocol/Handlers/FriendHandler.cs
@@ FriendHandler.GetIdCard @@
     [ProtocolHandler(Protocol.Friend_GetIdCard)]
     public async Task<FriendGetIdCardResponse> GetIdCard(
         SchaleDataContext db,
         FriendGetIdCardRequest request,
         FriendGetIdCardResponse response)
     {
         var account = await _sessionService.GetAuthenticatedUser(db, request.SessionKey);
 
         // the stored card only holds what SetIdCard writes; the live bits come off the account
         var card = account.ContentInfo.IdCard;
         card.Level = account.Level;
         card.FriendCode = AccountHandler.BuildFriendCode(account.ServerId);
         card.LastConnectTime = account.LastConnectTime;
         if (card.RepresentCharacterUniqueId == 0)
             card.RepresentCharacterUniqueId = account.RepresentCharacterServerId;
 
-        response.FriendIdCardDB = card;
+        // >>> BAPATCH-IDCARDDEFAULT v1 BEGIN >>>
+        // A row that never went through SetIdCard carries ContentInfoDB's bare new FriendIdCardDB: every Show* flag
+        // false, Comment null, CardBackgroundId 0. The client reads that as "this teacher never configured a card"
+        // and renders its prefab placeholder text (Lv.72 / username / AAAAAAAAAA), which is exactly what the reported
+        // screenshot shows. Answer with a configured card instead. Nothing is written back: the stored row stays
+        // untouched, so this is reversible without a migration.
+        response.FriendIdCardDB = IdCardNeverConfigured(card) ? BuildDefaultIdCard(card) : card;
+        // <<< BAPATCH-IDCARDDEFAULT v1 END <<<
 
         return response;
     }
+
+    // Every field SetIdCard writes is still at its ContentInfoDB default, so the row cannot have been saved by a user.
+    private static bool IdCardNeverConfigured(FriendIdCardDB c) =>
+        c.Comment == null
+        && c.CardBackgroundId == 0
+        && c.EmblemId == 0
+        && !c.SearchPermission
+        && !c.AutoAcceptFriendRequest
+        && !c.ShowAccountLevel
+        && !c.ShowFriendCode
+        && !c.ShowRaidRanking
+        && !c.ShowArenaRanking
+        && !c.ShowEliminateRaidRanking
+        && !c.ShowMultiFloorRaidClearedDifficulty;
+
+    // A fresh object, never the tracked ContentInfo.IdCard: filling defaults into the tracked entity would arm a
+    // later SaveChanges in the same request to silently persist them.
+    private static FriendIdCardDB BuildDefaultIdCard(FriendIdCardDB live) => new()
+    {
+        Level = live.Level,
+        FriendCode = live.FriendCode,
+        Comment = "",
+        LastConnectTime = live.LastConnectTime,
+        RepresentCharacterUniqueId = live.RepresentCharacterUniqueId,
+        RepresentCharacterCostumeId = 0,
+        CardBackgroundId = 1,
+        EmblemId = 0,
+        SearchPermission = true,
+        AutoAcceptFriendRequest = false,
+        ShowAccountLevel = true,
+        ShowFriendCode = true,
+        ShowRaidRanking = true,
+        ShowArenaRanking = true,
+        ShowEliminateRaidRanking = true,
+        ShowMultiFloorRaidClearedDifficulty = true,
+        ArenaRanking = null,
+        RaidRanking = null,
+        RaidTier = null,
+        EliminateRaidRanking = null,
+        EliminateRaidTier = null,
+        MultiFloorRaidClearedDifficulty = null,
+    };
```

**B2（独立小 bug，建议同批修）**：`SetIdCard` 漏写 `ShowMultiFloorRaidClearedDifficulty`
```diff
         card.ShowEliminateRaidRanking = request.ShowEliminateRaidRanking;
+        card.ShowMultiFloorRaidClearedDifficulty = request.ShowMultiFloorRaidClearedDifficulty;
         card.CardBackgroundId = request.BackgroundId;
```

---

## 4. 第三步：ID 卡上的 `username` 是谁给的 —— **存疑（需客户端侧确认）**

可确证的事实（两侧 DTO 都核过）：
- **`FriendIdCardDB` 22 个字段里没有任何昵称字段**（服务端 `DBModel.cs:1390-1411` 与客户端 `dto_schema_full_v2.json` 完全一致，22/22）。
- **`FriendDB` 有 `Nickname`**（客户端 DTO，10 字段中的第 3 个）—— 也就是说**好友列表**那条路有名字，**ID 卡**这条路没有。
- `FriendGetIdCardRequest` **没有目标账号 id 字段**（`NetworkProtocol.cs:4307-4310`）⇒ `Friend_GetIdCard` 只返回**自己的**卡。

⇒ 结论：**ID 卡上的名字不来自 `Friend_GetIdCard`**。最可能是客户端从本地 `AccountInfo.Nickname`（即 `Account_Auth` 下发的 `AccountDB.Nickname`）取。
**但我无法从服务端源码证明客户端渲染哪一位** ⇒ **存疑，需客户端侧确认**（不建议继续猜）。
一条可验证的旁证：把 `AccountDB.Nickname` 改成明显不同的值（如 `ZZZ`）后进 ID 卡页 —— 若卡上名字跟着变，即证实走的是 `AccountInfo.Nickname`。

---

## 5. 构建说明

| 项 | 说明 |
|---|---|
| 需要重建 DLL？ | **需要**（改的是 `Shittim-Server` 项目里的 `.cs`） |
| 构建命令 | `cd work\ba\srv_src` → `dotnet build Shittim-Server\Shittim-Server.csproj -c Release -o <独立输出目录> --nologo` |
| 预期 sha256 | **现在给不出来**：补丁尚未应用到 `srv_src`，没有构建产物就没有 sha。应用后我可以马上构建并报 `大小 / sha256`，与线上基线（`_build_panel` = `3ec7c46d…` / 2,674,688 B）对比，增量应在数百字节级（仅新增 2 个方法 + 1 行分支 + 1 行赋值） |
| 部署 | **本轮不做**（你在实测） |

---

## 6. 一句话

> **可以动手**：方案 A 是纯读时兜底、零迁移、可秒回退；但 `CardBackgroundId=1` 与 `Comment=""` 两个默认值建议先用测试号肉眼验一次（Excel 里 `IdCardBackgroundExcel` 是否有 `Id=1` 我没核到，标 `未证实`）。**ID 卡名字位存疑，需客户端侧确认，不要基于它做改动。**

---

# 追加：根因改到 `Friend_List`（2026-11-18 第二轮）

> 补丁文件：`_audit\patch_idcard_friendlist.udiff`（**未应用、未构建、未部署**）
> 与上一节的"读时补默认值"无关：那一节的前提（客户端能拿到卡）不成立，**先修这个**

## 1. `IdCardBackgroundDBs` 两个问题

### ① 客户端拿到空数组会不会崩 / 影响背景渲染？

**答：从服务端源码判不了，标 `存疑`。** 可确证的只有三点：
- `FriendListResponse.IdCardBackgroundDBs` 是 **`IdCardBackgroundDB[]?`**（可空数组），协议层允许 `null` 与 `[]` 两种形态；
- 目前该字段**从来没被赋值**（`FriendHandler.cs:47-49` 只设三个 friend 列表）⇒ 线上一直是 `null`，而客户端**没有因此崩**（用户能进大厅）—— 说明 `null` 至少不致命；
- 我们手里的反汇编只覆盖 `UIIdCardObject.SetMyIdCard()` 的 `get_MyIdCardClone` 分支，**没有**覆盖背景列表的遍历代码。

**取舍**：给 **`[]` 而不是 `null`**。理由：数组型字段被客户端 `foreach`/索引是最常见的写法，`null` 与 `[]` 在"崩溃"这一维度上 `[]` 严格更安全；若客户端把"无背景"渲染成空选择器，也不影响卡本身。

### ② 玩家已拥有的背景从哪取？—— **能可靠取到，就取真值**

| 环节 | 证据 |
|---|---|
| 表 / DbSet | `SchaleDataContext.cs:33` `DbSet<IdCardBackgroundDBServer> IdCardBackgrounds` |
| 账号关系 | `AccountDB.cs:22` / `:79`（`ICollection<IdCardBackgroundDBServer>`，构造时 `new()`） |
| 查询扩展 | `IdCardBackgroundDB.cs:32-35` `GetAccountIdCardBackgrounds(this SchaleDataContext, long accountId)` → `IQueryable<...>` |
| DTO 映射 | `ModelToList.cs:82` `ToMapList(this IQueryable<IdCardBackgroundDBServer>, IMapper)` |
| 行从哪来 | `ParcelResolver.cs:420-436` `UpdateIdCardBackground()`，由 `ParcelHandler.cs:147-148` 在收到 `ParcelType.IdCardBackground` 包裹时调用 |
| 新号是否有 | `AccountService.cs:32-34` 遍历 `DefaultParcelExcelT` 建号发默认包裹 —— **该表里是否含 `ParcelType.IdCardBackground(20)` 的行使，本轮未核实（`未证实`）** |

**结论**：用 `db.GetAccountIdCardBackgrounds(account.ServerId).ToMapList(_mapper).ToArray()`。
真实取其一是**准确**（背景是账号资产，ID 卡编辑器要用它画已拥有的列表），其二是**代价极小**（一张小表、一次按索引查）。
如果该账号一个背景都没有（很可能是现状），结果天然就是 `[]`，与"给空数组"等价，不多付任何代价。

## 2. 改动会不会影响 `Friend_List` 的其他字段

| 字段 | 影响 |
|---|---|
| `FriendDBs` / `SentRequestFriendDBs` / `ReceivedRequestFriendDBs` | **无影响**，仍是 `[]`（`:47-49` 未改动） |
| `FriendIdCardDB` | **新赋值**（本次修复目标） |
| `IdCardBackgroundDBs` | **新赋值**（`[]` 或真值） |
| 其它副作用 | `BuildMyIdCard` 会写 `account.ContentInfo.IdCard` 的 4 个**实时字段**（Level/FriendCode/LastConnectTime/RepresentCharacterUniqueId），与上一版 `GetIdCard` 行为完全一致；`List` 里**没有 `SaveChanges`**，所以这些只存在于本次请求的内存副本里，**不会落库**。 |

**新增的 DB 查询**：`Friend_List` 多一次 `IdCardBackgrounds` 按 `AccountServerId` 的查询（走索引，行数 = 玩家拥有的背景数，通常 0–个位数）。`Friend_List` 本身已经很轻（三次空数组赋值），此增量可忽略。

## 3. 与"改动 3（新号默认值）"的关系

- 本轮**不做**改动 3（你说得对：不要猜）。但注意：**改动 1 上线后，未保存过卡的新号会把自己那份"全默认"的 `FriendIdCardDB` 发给客户端**（所有 `Show*=false`、`Comment=null`、`CardBackgroundId=0`）。
- 客户端会因此**不再显示 prefab 占位**（clone 非 null 了），但显示出来的可能是"关掉所有开关的空卡"。**这正是需要 srv-ops dump 一次"用户刚保存后的 IdCard"来定默认值的原因** —— 拿到那份之后，改动 3 就是照着填。
- 也就是说：**改动 1 单独上线 = 从"占位卡"变成"空卡"，是否可接受需要你判断**；若不可接受，就和改动 3 一起上。
