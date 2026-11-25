# LoginSync(1017) 整份响应：官方 vs 我方 结构差异

- 时间：2026-11-19 01:35（Asia/Shanghai）｜ 执行：srv-ops（**只读**，未重启/未部署/未改服务器文件）
- 官方：`report\_tmp\official_decoded_201\02_1017_api_account_loginsync.response.json`（`inner`，账号 10015354380）
- 我方：wire-2026-11-19.txt 最近一条 `Account_LoginSync` 明文 → `work\ba\data\_tmp\our_loginsync_inner_20261119.json`（728,430 B，账号 4 / ServerId 2）
- 官方请求：`02_1017_api_account_loginsync.request.json`

## 一句话结论

**子包"名字集合"基本一致（我方多 1 个 `ItemListResponse`，官方那份是 `null`），但三处系统性差异：**
① **顺序不同**（我方把 `ItemListResponse` 插到第 6 位，`EliminateRaidLoginResponse` 从官方第 22 位挪到第 12 位，后段 4 个包次序也不同）；
② **每个子包都少了 4 个"空壳键"** `SessionKey / ServerTimeTicks / ServerNotification / RequestId`（官方全部存在且为零值）；
③ **子包 `Protocol` 值**：官方**全部为 `0`**，我方填的是真实协议号（20000/1003/10006…）。

---

## 1. 官方请求的 `SyncProtocols`（25 项，客户端按它索取）

```json
[20000, 1003, 2000, 3000, 5000, 12000, 6000, 22001, 17018, 21000,
 28001, 33000, 19000, 10006, 39006, 44000, 29002, 30041, 45000,
 46000, 46001, 47000, 49000, 27002, 49004]
```
- 其余字段：`SkillCutInOption=OnceADay`、`Resendable=true`、`IsTest=false`、`OSType=2`、`SessionKey.AccountServerId=10015354380`。
- **`10006` 在列表第 14 项** ⇒ 卡池清单确实是"登录同步子协议"方式索取（与我方一直下发 `ShopGachaRecruitListResponse` 一致）。

## 2. 子包清单对照（按响应中出现顺序）

| # | 官方字段名 | 官方 Protocol | 我方字段名 | 我方 Protocol |
|---|---|---|---|---|
| 1 | CafeGetInfoResponse | 0 | CafeGetInfoResponse | 20000 |
| 2 | AccountCurrencySyncResponse | 0 | AccountCurrencySyncResponse | 1003 |
| 3 | CharacterListResponse | 0 | CharacterListResponse | 2000 |
| 4 | EquipmentItemListResponse | 0 | EquipmentItemListResponse | 3000 |
| 5 | CharacterGearListResponse | 0 | CharacterGearListResponse | 44000 |
| 6 | **EchelonListResponse** | 0 | **ItemListResponse ← 我方多出来** | 4000 |
| 7 | MemoryLobbyListResponse | 0 | EchelonListResponse | 5000 |
| 8 | CampaignListResponse | 0 | MemoryLobbyListResponse | 12000 |
| 9 | ArenaLoginResponse | 0 | CampaignListResponse | 6000 |
| 10 | RaidLoginResponse | 0 | ArenaLoginResponse | 22001 |
| 11 | CraftInfoListResponse | 0 | RaidLoginResponse | 17018 |
| 12 | ClanLoginResponse | 0 | **EliminateRaidLoginResponse ← 挪前** | 45000 |
| 13 | MomoTalkOutLineResponse | 0 | CraftInfoListResponse | 21000 |
| 14 | ScenarioListResponse | 0 | ClanLoginResponse | 28001 |
| 15 | ShopGachaRecruitListResponse | 0 | MomoTalkOutLineResponse | 33000 |
| 16 | TimeAttackDungeonLoginResponse | 0 | ScenarioListResponse | 19000 |
| 17 | BillingPurchaseListByYostarResponse | 0 | **ShopGachaRecruitListResponse** | 10006 |
| 18 | EventContentPermanentListResponse | 0 | TimeAttackDungeonLoginResponse | 39006 |
| 19 | AttachmentEmblemListResponse | 0 | EventContentPermanentListResponse | 30041 |
| 20 | AttachmentGetResponse | 0 | AttachmentGetResponse | 46000 |
| 21 | ContentSweepMultiSweepPresetListResponse | 0 | BillingPurchaseListByYostarResponse | 29002 |
| 22 | **EliminateRaidLoginResponse** | 0 | AttachmentEmblemListResponse | 46001 |
| 23 | StickerListResponse | 0 | ContentSweepMultiSweepPresetListResponse | 27002 |
| 24 | MultiFloorRaidSyncResponse | 0 | StickerListResponse | 47000 |
| 25 | MultiFloorRaidLoginResponse | 0 | MultiFloorRaidSyncResponse | 49000 |
| 26 | — | — | MultiFloorRaidLoginResponse | 49004 |

- **官方子包数 = 25，我方 = 26**。
- **首个错位 = 第 6 位**（官方 `EchelonListResponse` vs 我方 `ItemListResponse`）。
- 集合差异：**我方多 `ItemListResponse`**（官方那份为 `null`，不算子包）；**官方无"我方缺"的子包名**。
- 后段还有独立错位：官方 `Billing → EventContent → AttachmentEmblem → AttachmentGet`，我方 `EventContent → AttachmentGet → Billing → AttachmentEmblem`。

## 3. 每个子包的"壳字段"差异（系统性）

官方**每个**子包都带 5 个壳字段（4 个固定零值）：

```json
"SessionKey": {"AccountServerId": 0, "MxToken": ""},
"ServerTimeTicks": 0,
"ServerNotification": 0,
"RequestId": ""
```
我方 26 个子包**一个都没有**这 4 个键（只有 `Protocol` + 数据字段）。

逐包键差（官方有、我方没有）——**26 个包全部命中同一模式**，另有 3 个包还缺具体数据键：

| 子包 | 官方键数 | 我方键数 | 我方缺失 | 我方多出 |
|---|---|---|---|---|
| CafeGetInfoResponse | 8 | 3 | SessionKey/ServerTimeTicks/ServerNotification/RequestId + **CafeDB** | — |
| CampaignListResponse | 8 | 4 | 上述 4 个 + **CurrentScenarioId** | StrategyObjecthistoryDBs |
| ClanLoginResponse | 8 | 2 | 上述 4 个 + **AccountClanDB / ClanAssistSlotDBs** | — |
| ScenarioListResponse | 8 | 3 | 上述 4 个 + **ScenarioCollectionDBs** | — |
| CraftInfoListResponse | 8 | 1 | 上述 4 个 + **CraftInfos / ShiftingCraftInfos / PresetSlotDBs** | — |
| RaidLoginResponse | 9 | 2 | 上述 4 个 + **CanReceiveRankingReward / LastSettledRanking / LastSettledTier** | — |
| EliminateRaidLoginResponse | 11 | 2 | 上述 4 个 + **5 个统计字段** | — |
| TimeAttackDungeonLoginResponse | 6 | 1 | 上述 4 个 + **PreviousRoomDB** | — |
| MultiFloorRaidLoginResponse | 6 | 1 | 上述 4 个 + **LastClearedDifficulty** | — |
| CharacterListResponse | 8 | 5 | 上述 4 个 | **CostumeDBs** |
| BillingPurchaseListByYostarResponse | 8 | 7 | 上述 4 个 | **BlockedProductDBs / BattlePassProductList / PendingProductShopCashIds** |
| 其余 15 个子包 | 6 | 2 | 仅上述 4 个壳字段 | — |

## 4. 顶部（非子包）字段差异

| | 官方（35 键） | 我方（32 键） |
|---|---|---|
| 有 | Protocol, **SessionKey**, **ServerTimeTicks**, **ServerNotification**, **RequestId**, 全部子包, **FriendCount**, FriendCode, PickupFirstGetHistoryDBs, AccountLevelRewardIds | Protocol, ServerTimeTicks, ServerNotification, 全部子包, FriendCode, PickupFirstGetHistoryDBs, AccountLevelRewardIds |
| **我方缺** | — | **SessionKey（缺整键）、RequestId（缺整键）、FriendCount（缺整键）** |

## 5. 空/非空对照（数据字段长度，排除壳字段）

| 子包 | 官方 | 我方 | 说明 |
|---|---|---|---|
| ShopGachaRecruitListResponse | ShopRecruits **529** / ShopFreeRecruitHistoryDBs **0** | ShopRecruits **529** / ShopFreeRecruitHistoryDBs **0** | **完全一致** ✅ |
| ItemListResponse | **null**（官方本次没下发道具表） | dict：ItemDBs **53** / ExpiryItemDBs 0 | 我方多给（结构上更完整） |
| EquipmentItemListResponse | EquipmentDBs **84** | **1910** | 账号不同，数量自然不同 |
| CharacterListResponse | CharacterDBs 46 / WeaponDBs 0 | 234 / 3 | 同上 |
| CafeGetInfoResponse | **CafeDB:null** + CafeDBs 2 + FurnitureDBs 27 | 无 CafeDB 键 + CafeDBs 2 + FurnitureDBs 15 | 缺 `CafeDB` 键（官方为 null） |
| CampaignListResponse | CurrentScenarioId **41200** | 无此键 | 缺键 |
| ClanLoginResponse | AccountClanDB **dict(10)**（有公会） | 无 AccountClanDB（无公会） | 账号状态不同 + 缺键 |
| BillingPurchaseListByYostarResponse | CountList **4** | 全 0（含 3 个我方独有键） | 账号状态不同 |
| CraftInfoListResponse | CraftInfos 0 / ShiftingCraftInfos 0 / PresetSlotDBs 0 | **一个数据键都没有** | 缺 3 个空数组键 |
| ScenarioListResponse | ScenarioCollectionDBs **[]** | 无此键 | 缺空数组键 |
| AttachmentEmblemListResponse | EmblemDBs 14 | 762 | 账号不同 |

- **官方"非空/我方空"或反之**：除 `ItemListResponse`（官方 null / 我方 53 条）外，
  其余差异都能用"账号不同（官方 10015354380 vs 我方 4）"或"我方少发空壳/空数组键"解释；
  **没有任何一个子包在官方非空、在我方被发成空数组**（卡池 529 条两侧都非空）。

## 6. 针对重点子包的回答

| 关注项 | 官方 | 我方 | 判定 |
|---|---|---|---|
| `ShopGachaRecruitListResponse` | 7 键，ShopRecruits 529，Protocol=0 | 3 键，ShopRecruits 529，Protocol=10006 | 数据一致；**封装不同** |
| `ShopFreeRecruitHistoryDBs` | 子包内字段，`[]` | 子包内字段，`[]` | 一致 ✅ |
| `ItemListResponse` | **null** | dict（ItemDBs 53） | 我方多给真实数据 |
| `TutorialDBs` | 两侧都**没有**这个字段 | 同 | —（教程走 1005 独立协议） |
| `AccountCurrencyDBs` | 字段名实际是 `AccountCurrencyDB`（4 项） | 同名同 4 项 | 一致 ✅ |
| `ShopListResponse` | **不存在**（商店列表是独立 10002 协议） | 不存在 | 一致 |

## 7. 结论（事实）

1. **卡池数据本身完全没问题**：`ShopRecruits` 529 条，两侧 1:1（上一条已逐字段 diff = 0），且它就在登录包里下发。
2. **我方与官方的结构性差异共 3 类**：
   - 子包顺序（从第 6 位开始错位；我方把 `ItemListResponse` 提前插入、`EliminateRaid` 前移）；
   - 每个子包缺 4 个零值壳键（`SessionKey/ServerTimeTicks/ServerNotification/RequestId`），顶层也缺 `SessionKey/RequestId/FriendCount`；
   - 子包 `Protocol` 值：官方 `0`，我方实际协议号。
3. **可能的客户端影响**：若客户端按 `SyncProtocols` 的**下标**或按子包 `Protocol` 值来匹配，而不是按 JSON 字段名匹配，
   上述顺序/值差异就可能让它"解析到了但不落地"（表现为 UI 空、`No LocalizeKey`、按钮默认 1,000）。
   这是目前服务端侧**唯一尚未排除**的解释方向。
4. 若要验证，最小改动候选（**需另行下令，本次未做**）：
   - 子包按官方顺序输出、补 4 个零值壳键、`Protocol` 写 0；
   - 顶层补 `SessionKey/RequestId/FriendCount`；
   - 保持 529 条数据不动。
5. 客户端本地是否具备这 529 个 Id 对应的 `GachaRecruitBannerExcel` / 本地化 key，仍属客户端侧数据问题，服务端日志无法判定。
