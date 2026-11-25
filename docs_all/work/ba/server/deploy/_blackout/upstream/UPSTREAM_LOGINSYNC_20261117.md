# 上游 `Account_LoginSync` 核对（2026-11-17）

> 目的：判断国服 1017 能否从「桥接自造（gen1017/spec26）」改成「转发 Shittim」
> 取证方式：`api.github.com` 取上游源码到本目录（`raw.githubusercontent.com` 在本机被 reset，不可用）
> **未改动本目录以外的任何文件**

---

## 0. 仓库与版本

| 项 | 值 |
|---|---|
| 仓库 | **https://github.com/Neoexm/Shittim-Server** |
| 分支 | `main` |
| HEAD commit | **`5f3910ea44a8798c213ea12a3e85f182194f92c6`** |
| commit 时间 | 2026-08-20T14:33:17Z |
| commit message | `fixed db issue` |
| 上游 `AccountHandler.cs` | 48,829 B / sha256 `6baa2ca838a87631887c203bc43b09d96c214f55f16429ec394a017449506ea3` |
| 本地 `work\ba\srv_src` 同名文件 | 46,226 B / sha256 `297d72928f38619e239d8719b0b55c482a5a70dd30beff0e8596ace3a684b66c` |

### ⚠ 本地树 **不等于** 上游 main（60 行差异，且是本地更旧）

`Compare-Object` 结果：上游 1056 行 / 本地 1020 行 / 单侧差异 60 行。**上游有、本地没有的两处修复**：

1. **交互式世界 Raid 的入口券补满**（上游按 `InteractiveWorldRaidSeasonManageExcelT` 逐 phase 处理 `EnterTicket`；本地只处理单个 `raidSeason.EnterTicket`）
2. **删除"幽灵角色行"前先校验 Excel 表完整性**——上游有 `_excelService.IsTableComplete<CharacterExcelT>()` 守卫，**本地没有，会无条件删掉 `CharacterExcel` 里查不到的角色行**（若 Excel 表残缺，会误删真实学生，且删掉后无从恢复）

⇒ **结论：本地 srv_src 是一份旧修订版**。改成转发前，这一差异本身值得单独评估（尤其第 2 条有破坏性风险）。

---

## 1. 上游 `LoginSync` handler 的完整字段清单

`AccountHandler.cs:288-655`（上游），`[ProtocolHandler(Protocol.Account_LoginSync)]` 在 `:288`，方法签名在 `:289`。
**顶层 `response.X =` 赋值共 30 处**（下表全部来自源码扫描）：

| # | 字段 | 上游行号 | 说明 |
|---|---|---|---|
| 1 | `CafeGetInfoResponse` | — | 咖啡厅 |
| 2 | `AccountCurrencySyncResponse` | — | **货币（青辉石等真值就在这）** |
| 3 | `CharacterListResponse` | — | 角色 + 武器 + 服装 |
| 4 | `EquipmentItemListResponse` | — | 装备 |
| 5 | `CharacterGearListResponse` | — | 爱用品 |
| 6 | `EchelonListResponse` | — | 编队 |
| 7 | `MemoryLobbyListResponse` | — | 纪念大厅 |
| 8 | `CampaignListResponse` | — | 关卡进度 |
| 9 | `ArenaLoginResponse` | — | 竞技场 |
| 10 | `RaidLoginResponse` | — | 总力战（`SeasonType.Open`） |
| 11 | `EliminateRaidLoginResponse` | — | 大决战（`SeasonType.Open`） |
| 12 | `CraftInfoListResponse` | — | 制造 |
| 13 | `ClanLoginResponse` | — | 社团 |
| 14 | `MomotalkOutlineResponse` | **L508** | 桃信（注意键名大小写，见 §3） |
| 15 | `ScenarioListResponse` | — | 剧情 |
| 16 | `ShopGachaRecruitListResponse` | — | 商店免费招募 |
| 17 | `TimeAttackDungeonLoginResponse` | — | 制约解除 |
| 18 | `BillingPurchaseListByNexonResponse` | — | 账单/通行证（**国服叫 ByYostar**） |
| 19 | `EventContentPermanentListResponse` | — | 常驻活动 |
| 20 | `AttachmentGetResponse` | — | 附件 |
| 21 | `AttachmentEmblemListResponse` | — | 头像框 |
| 22 | `ContentSweepMultiSweepPresetListResponse` | — | 扫荡预设 |
| 23 | `StickerListResponse` | — | 贴纸 |
| 24 | `MultiFloorRaidSyncResponse` | — | 综合战术战 |
| 25 | `MultiFloorRaidLoginResponse` | — | 同上 |
| 26 | `PickupFirstGetHistoryDBs` | — | 首次获得记录 |
| 27 | `AccountLevelRewardIds` | — | 账号等级奖励 |
| 28 | `FriendCount` | — | 好友数 |
| 29 | `FriendCode` | — | 好友码 |
| 30 | `StaticOpenConditions` | **L625** | 内容锁（**基类字段**，`response.StaticOpenConditions = BuildOfficialStaticOpenConditions();`） |

### ★ `AccountDB` **不在 LoginSync 里**

`L289-655` 区间内 grep `AccountDB` → **0 命中**。
⇒ **`AccountDB` 只由 `Account_Auth`(1002) 下发**。LoginSync 的真源是 `AccountCurrencySyncResponse`（货币）+ 各子响应（角色/编队/关卡…）。

> 这正好对上「登录显示 600、领完东西跳到 7000+」的现象：桥接自造的 1017 与 `Account_Auth` 的真值来自**两个不同的数据源**。

### 与版本/赛季绑定的硬编码

- **没有** `TableVersion` / `ExcelVersion` 之类的版本号字段。
- 赛季相关是**枚举值写死**：`RaidLoginResponse.SeasonType = RaidSeasonType.Open`（`:453-456`）、`EliminateRaidLoginResponse.SeasonType = RaidSeasonType.Open`（`:458-462`）。
- `ServerTimeTicks` 由基类 `ResponsePacket` 默认生成（`ConcentrateCampaignManager` 那类地方另有 account 时钟），**LoginSync 内不显式设置**。
- `ArenaLoginResponse.CurrentSeasonId` 来自 `account.ContentInfo.ArenaDataInfo.SeasonId`（**账号数据**，非硬编码）。

---

## 2. 与 CN 客户端 DTO 的逐字段对照

客户端权威定义：`work\ba\proto\dto_schema_full_v2.json` → `AccountLoginSyncResponse`，**31 个字段**。

| # | 客户端字段（CN 3.0.2） | 上游是否发 | 判定 |
|---|---|---|---|
| 0 | `Responses`（ResponsePacket 对象） | ❌ | 官方 CN 抓包也用**具名字段**而非 `Responses` 数组（`work\ba\proto\protocol_priority.json:3607`），可不发 |
| 1 | `CafeGetInfoResponse` | ✅ | 一致 |
| 2 | `AccountCurrencySyncResponse` | ✅ | 一致 |
| 3 | `CharacterListResponse` | ✅ | 一致 |
| 4 | `EquipmentItemListResponse` | ✅ | 一致 |
| 5 | `CharacterGearListResponse` | ✅ | 一致 |
| 6 | **`ItemListResponse`** | ❌ | **上游刻意不发**（`AccountHandler.cs:409` 注释：官方 LoginSync 没有 ItemList 子包，客户端随后自己拉 `Item_List`）⇒ 客户端能容忍 null |
| 7 | `EchelonListResponse` | ✅ | 一致 |
| 8 | `MemoryLobbyListResponse` | ✅ | 一致 |
| 9 | `CampaignListResponse` | ✅ | 一致 |
| 10 | `ArenaLoginResponse` | ✅ | 一致 |
| 11 | `RaidLoginResponse` | ✅ | 一致 |
| 12 | `EliminateRaidLoginResponse` | ✅ | 一致 |
| 13 | `CraftInfoListResponse` | ✅ | 一致 |
| 14 | `ClanLoginResponse` | ✅ | 一致 |
| 15 | **`MomotalkOutlineResponse`** | ✅ **同名** | ⚠ **桥接发的是 `MomoTalkOutLineResponse`（大小写不同）** |
| 16 | `ScenarioListResponse` | ✅ | 一致 |
| 17 | `ShopGachaRecruitListResponse` | ✅ | 一致 |
| 18 | `TimeAttackDungeonLoginResponse` | ✅ | 一致 |
| 19 | **`BillingPurchaseListByYostarResponse`** | ❌（上游叫 **`...ByNexonResponse`**） | ⚠ **键名不一致，客户端收不到** |
| 20 | `EventContentPermanentListResponse` | ✅ | 一致 |
| 21 | `AttachmentGetResponse` | ✅ | 一致 |
| 22 | `AttachmentEmblemListResponse` | ✅ | 一致 |
| 23 | `ContentSweepMultiSweepPresetListResponse` | ✅ | 一致 |
| 24 | `StickerListResponse`（类型 `StickerLoginResponse`） | ✅ | 一致 |
| 25 | `MultiFloorRaidSyncResponse` | ✅ | 一致 |
| 26 | `MultiFloorRaidLoginResponse` | ✅ | 一致 |
| 27 | `FriendCount` | ✅ | 一致 |
| 28 | `FriendCode` | ✅ | 一致 |
| 29 | `PickupFirstGetHistoryDBs` | ✅ | 一致 |
| 30 | `AccountLevelRewardIds` | ✅ | 一致 |
| — | （客户端 DTO 未列）`StaticOpenConditions` | ✅ 上游发 | 基类字段，客户端基类也有 ⇒ 无害 |
| — | ~~`AccountDB`~~ | ❌ 上游不发 | 客户端 DTO 也没有 ⇒ 一致 |

**差集小结（上游 vs CN 客户端）**
- 客户端有、上游不发：**`ItemListResponse`**（官方行为一致 ⇒ 无害）、**`BillingPurchaseListByYostarResponse`**（名字不对 ⇒ **真缺**）、`Responses`（官方也不用）
- 上游发、客户端 DTO 未列：`StaticOpenConditions`（基类字段 ⇒ 无害）

---

## 3. 与桥接 `spec26` 模板的差集

桥接产物键（`work\ba\server\prototype\out\1017.json`，**35 键** = 5 信封 + 30 业务）：

```
Protocol / SessionKey / ServerTimeTicks / ServerNotification / RequestId
CafeGetInfoResponse / AccountCurrencySyncResponse / CharacterListResponse /
EquipmentItemListResponse / CharacterGearListResponse / ItemListResponse /
EchelonListResponse / MemoryLobbyListResponse / CampaignListResponse /
ArenaLoginResponse / RaidLoginResponse / CraftListInfoResponse…（同上游 25 个） /
MomoTalkOutLineResponse / BillingPurchaseListByYostarResponse / StickerListResponse /
FriendCount / FriendCode / MultiFloorRaidSyncResponse / MultiFloorRaidLoginResponse /
PickupFirstGetHistoryDBs / AccountLevelRewardIds
```

| 差集 | 字段 | 影响 |
|---|---|---|
| **桥接有、上游无** | `ItemListResponse` | 官方也不发 ⇒ 桥接多发了一个（无害，但与官方不一致） |
| **桥接有、上游无（名字对不上）** | `BillingPurchaseListByYostarResponse` | 上游是 `...ByNexonResponse` ⇒ **转发时客户端拿不到**，通行证/账单页会锁 |
| **桥接名字错、上游对** | `MomoTalkOutLineResponse` vs 客户端 `MomotalkOutlineResponse` | **桥接这边的键名与客户端 DTO 不一致**（上游反而一致） |
| **上游有、桥接无** | `StaticOpenConditions` | 基类字段，客户端能解析 ⇒ 无害（转发后反而更全） |
| 信封 | 桥接额外发 `Protocol/SessionKey/ServerTimeTicks/ServerNotification/RequestId` | 上游网关自动补 `Protocol/ServerTimeTicks/ServerNotification`，`RequestId` 由代理层补 |

---

## 4. 结论

> **「可以安全改成转发」——但必须先处理 1 处键名：`BillingPurchaseListByNexonResponse` → `BillingPurchaseListByYostarResponse`。**
>
> 依据：
> 1. 上游 LoginSync 的 30 个顶层字段与 CN 客户端 DTO（31 个）**逐一对应**，只差 `ItemListResponse`（官方本来就不发）与 `Billing` 的 Nexon/Yostar 命名。
> 2. **`AccountDB` 不在 LoginSync**（上游 `:289-655` 内 0 命中），只在 `Account_Auth`；这与客户端 DTO 完全一致 ⇒ **转发不会引入"两套 AccountDB 打架"的问题，反而消除它**（青辉石从 `AccountCurrencySyncResponse` 取真值）。
> 3. 桥接模板里 `MomoTalkOutLineResponse` 的**大小写是桥接自己的错**，上游 `MomotalkOutlineResponse` 才与客户端一致 ⇒ 转发顺带修掉这个隐患。
>
> **风险/待办（按优先级）**
> 1. **Billing 键名**（必改，否则通行证页锁）
> 2. **本地树落后上游 60 行**（含"删幽灵角色前无 `IsTableComplete` 守卫"这条破坏性风险）——建议先对齐上游再改转发
> 3. `ItemListResponse`：转发后变 null，官方本来也不发 ⇒ 可接受，但**若客户端在 1017 后不再自己拉 `Item_List` 就会缺背包**
> 4. 桥接的 `Protocol/SessionKey/RequestId` 信封层需继续由代理补（上游不产 `RequestId`）
>
> **未确认项**：CN 客户端是否按 `SyncProtocols` 点名分发（上游不读该字段，若客户端严格按点名校验，转发仍需代理侧补 `Responses`）。
