# 新号原型生成器 — 端到端报告（24000 / 1017）

> 目标：多用户私服里「每张卡密 = 一个独立账号」，响应按**账号状态**动态生成，不抄官方快照。
> 本报告记录两个生成器的产物、与官方的结构/数据对比、以及每一个判断的依据与未找到项。
>
> 产物目录：`work/ba/server/prototype/`
> 复现用的账号：`server_id = 99990000001`（虚构），`--now 2026-11-16T05:00:00`

---

## 0. 结论（先给结果）

| 协议 | 生成文件 | 字节数 | 顶层键 | 具名子回包 | spec_check | FAIL | WARN |
|---|---|---|---|---|---|---|---|
| 24000 Academy_GetInfo | `out/24000.json` | **1,473** | 7 / 7 | — | **PASS** | **0** | 1 |
| 1017 Account_LoginSync | `out/1017.json` | **106,733** | 35 / 35 | 26（25 个结构 + 1 个 null） | **PASS** | **0** | 83 |

* 字节数是 `--now 2026-11-16T05:00:00` 下的值；用默认「当前时间」重跑是 1,477 / 106,898（差异只来自时间串的小数位，因为时间格式是 RFC3339Nano 风格、尾零裁掉）。
* 两个响应**结构上没有任何多余键、没有任何缺失键**，顶层键序与官方完全一致；WARN 全部是「新号本来就没有这么多东西」造成的长度差，属于 spec 判定的合法范围。
* 生成过程 `conform` 记账：**dropped_keys = 0，forced_nodes = 0**（两个协议都是）。也就是说 `server_apply_skeleton` 里给的每一个键，spec 都认得 —— 这是 spec 完整性的正面证据。
* 参考量级：官方同一账号 24000 = 39,364 B，1017 = 502,979 B（约 4.7 倍），差距基本等于「46 角色 / 84 装备 / 191 剧情 / 90 关卡 / 138 学院访问记录」这些进度数据。

### 复现（3 条命令）

```bash
# 1) 生成两个响应
python work/ba/server/prototype/gen_new_account.py --now 2026-11-16T05:00:00
python work/ba/server/prototype/gen_1017.py       --now 2026-11-16T05:00:00

# 2) 验收（spec 校验）
python work/ba/proto/spec_check.py --protocol 24000 --file work/ba/server/prototype/out/24000.json
python work/ba/proto/spec_check.py --protocol 1017  --file work/ba/server/prototype/out/1017.json
```

不加参数直接跑也行（时间取当前时间、`request_id` 取 uuid4、`MxToken` 由 server_id 派生成 64 字符 base64）：

```bash
python work/ba/server/prototype/gen_new_account.py
python work/ba/server/prototype/gen_1017.py
```

---

## 1. 交付物

| 文件 | 说明 |
|---|---|
| `specgen.py` | 引擎：spec 形状投影（`conform`/`default`）+ 时间/ticks + ExcelDB 只读主数据 + FlatBuffers 标量读取 + 虚构账号对象 |
| `gen_new_account.py` | 生成 `out/24000.json`（Academy_GetInfo） |
| `gen_1017.py` | 生成 `out/1017.json`（Account_LoginSync，35 键 / 26 子回包） |
| `out/24000.json` / `out/1017.json` | 生成结果（本条验收对象） |
| `REPORT.md` | 本文件 |
| `_scratch/` | 取证脚本与输出（`analyze_diff.py` 结构/计数对比、官方响应格式探针、ExcelDB 查询输出） |

**没有改动任何现有文件**：`official_spec.json` / `initial_state_rules.json` / `spec_check.py` / `work/ba/server/*` 全部只读引用。
`spec_check.py` 是被 `import` 进来复用的（`specgen.Spec.check_report`），不是重写了一份校验逻辑。

---

## 2. 实现思路：把「结构」和「状态」彻底拆成两层

这是能一次跑通 PASS 的关键。如果按「手写一份 JSON、再对着报错改」的路子，1017 的 490 个 spec 节点根本改不完。

```
                 ┌──────────────────────────────────────────┐
  数据层（状态）  │ initial_state_rules.json + ExcelDB.db     │  ← 新号「有什么」
                 │ server_apply_skeleton / q1..q10 / 主数据  │
                 └───────────────┬──────────────────────────┘
                                 │ 残缺的 values（只写有数据的键）
                 ┌───────────────▼──────────────────────────┐
  结构层（形状）  │ official_spec.json  →  Spec.conform()     │  ← 官方「长什么样」
                 │ 必填补默认 / 可选缺席 / 多余记账          │
                 └───────────────┬──────────────────────────┘
                                 ▼
                        响应 JSON（必然 PASS）
```

`Spec.conform(value, node)` 的规则（对应 `spec_check.py` 的判定口径）：

| spec 情况 | 数据情况 | 本引擎行为 | spec_check 判定 |
|---|---|---|---|
| 键 `always=true` | 没给 | 用该节点的结构性默认值补（int 0 / str "" / bool false / [] / {} / null） | 不 FAIL |
| 键 `always=false`（可选标量） | 没给 | **保持缺席**（proto3 可选标量 presence 语义，官方也是这么发的） | WARN，合法 |
| 键 spec 里没有 | 给了 | 丢弃 + 记账 | 本应 FAIL，所以记账计数必须为 0 |
| `type=null` 且 nullable | 给了别的 | 强制 null + 记账 | 不 FAIL |
| `observed_empty_only=true` | 给了非空 | 强制 `{}` + 记账 | 不 FAIL |

因为结构层负责兜底，生成器里每个子回包只写「有数据的那几个键」，没数据的键由 spec 自动补零/补空 —— 这也正是官方 1017 那 26 个子回包**信封全零**的成因：服务端只填了 body，信封字段在 proto3 里没赋值就序列化成 0/""。

**用 `is_player_data` 反查覆盖度**：spec 自己标了「这是玩家数据、私服必须按账号生成」的字段，1017 有 **133** 个、24000 有 **8** 个。本次生成器全部按账号状态产出（ServerId 全部由 `server_id` 派生、AccountId/AccountServerId 全等于 `server_id`、时间全部取账号当前时间），没有一处来自官方样本。

**对象 id 与自指字段的口径**（`specgen.Account`）：

* `ServerId`（角色 / 道具 / 家具）：`account_id * 100000 + kind * 10000 + 序号`，kind = 1 角色 / 2 道具 / 3 家具。官方那套 7~8 位 ServerId 是官方服务端的自增号、没有跨账号含义；改成本公式后**多账号共库不撞号**，且编队引用的 `LeaderServerId / MainSlotServerIds / SupportSlotServerIds` 与 `CharacterDBs[].ServerId` 用同一套函数算出，必然自洽。
* `CafeDBId = account_id * 10 + CafeId`（规则 q9 给的官方公式）。
* `ServerTimeTicks` 用 **.NET 100ns ticks（自 0001-01-01）**，见 §6.5 的实测确认。

---

## 3. 产物 1：24000 Academy_GetInfo

| 顶层键 | 值 | 来源 |
|---|---|---|
| `Protocol` | 24000 | 协议号 |
| `SessionKey` | `{AccountServerId: 99990000001, MxToken: <64 字符 base64>}` | 账号 |
| `ServerTimeTicks` | 639304020000000000（= 2026-11-16T05:00:00Z） | 账号当前时间 |
| `ServerNotification` | 0 | 官方两个样本都是 0 |
| `RequestId` | uuid4 | 账号 |
| `AcademyDB.AccountId` | 99990000001 | 账号 |
| `AcademyDB.LastUpdate` | `2026-11-16T05:00:00` | 账号当前时间 |
| `AcademyDB.ZoneVisitCharacterDBs` | **71 个 zone key，全部 `[]`** | 键集合见 §6.1；值见 §6.1 的四条理由 |
| `AcademyDB.ZoneScheduleGroupRecords` | `{}` | spec: `observed_empty_only`，非空会 FAIL |
| `AcademyLocationDBs` | 1 条 `{AccountId, LocationId: 1, Rank: 1, Exp: 0}` | `q8.initial.suggested_minimum`（= 规则表自己标的「工程最小实现」） |

Result: `PASS`，唯一 WARN 是 `AcademyLocationDBs 数组长度 1 不在观测范围 [9,9]`（§6.1 / §7 第 1 条）。

### 71 个 zone key 是怎么来的（这是本任务第一个必须解开的结）

`spec` 只记得「`ZoneVisitCharacterDBs` 是 `map<int_str, [...]>`、**key_count 恰好 71**」，记不下 71 个键本身。但客户端要按 key 找 zone，键必须是真的。

推导过程（全程主数据，不抄官方键）：

1. `ExcelDB.db!AcademyZoneDBSchema` 有 95 行，`f1` = 该 zone 属于哪个 location。
2. 按 `f1` 分组：`location 1 → 8 个 zone`、`location 7 → 7 个`、`location 11/12/13/14/15/16/17/18/19/20 → 各 8 个`。
3. 国服实际启用的 location 是 9 个：`AcademyLocationDBSchema` 的 11 个（1,7,11,12,13,14,15,16,17,19）去掉 **14 / 18**（官方 24000 的 9 条 AcademyLocationDBs 里没有这两个）。
4. 这 9 个 location 的 zone 数 = 8 + 7 + 8×7 = **71**，正好等于 spec 的 key_count。
5. 交叉验证：把推导出的 71 个 zone id 集合与官方 `ZoneVisitCharacterDBs` 的 71 个键集合做集合比较 —— **完全相等，差集为空**。

所以 71 个键是「主数据 + 一条可验证的启用集合」推出来的，不是从官方响应抄的键。

---

## 4. 产物 2：1017 Account_LoginSync

### 4.1 顶层 35 键 / 26 个具名子回包

| # | 子回包 | 本原型状态 | 条数 | 数据来源 |
|---|---|---|---|---|
| 1 | `CafeGetInfoResponse` | 有内容 | CafeDBs 2 / FurnitureDBs 22 | `q9`（2 厅 × 11 件默认家具）+ `FurnitureDBSchema` |
| 2 | `AccountCurrencySyncResponse` | 有内容 | CurrencyDict 29 / UpdateTimeDict 19 | `q4` + skeleton |
| 3 | `CharacterListResponse` | 有内容 | **4**（官方 46） | `q1/q2` + skeleton |
| 4 | `EquipmentItemListResponse` | 空 | 0（官方 84） | `q3`：新号无装备 |
| 5 | `CharacterGearListResponse` | 空 | 0 | 同上 |
| 6 | `ItemListResponse` | **null** | — | spec 记为 `type=null`（见 §6.3） |
| 7 | `EchelonListResponse` | 有内容 | **1**（官方 8） | `q5` + skeleton，槽位 4+2 补 0 |
| 8 | `MemoryLobbyListResponse` | 有内容 | 1 | `other_initial_state.MemoryLobby` = `{Type:8, MemoryLobbyUniqueId:13010}` |
| 9 | `CampaignListResponse` | 空 | 0 / 0，CurrentScenarioId 0 | 进度类，新号从零 |
| 10 | `ArenaLoginResponse` | 零值结构 | ArenaPlayerInfoDB 9 键全 0 | 未找到初始分组规则（§7-4） |
| 11 | `RaidLoginResponse` | 零值结构 | — | 未找到国服赛季号（§7-14） |
| 12 | `CraftInfoListResponse` | 空 | 0 / 0 / 0 | 无合成进度 |
| 13 | `ClanLoginResponse` | 零值结构 | 10 键 + 14 键 | 「不在战队」的形态（§6.12） |
| 14 | `MomoTalkOutLineResponse` | 空 | 0 / 0 | 未找到初始对白规则（§7-8） |
| 15 | `ScenarioListResponse` | **全空** | 0 / 0 / 0 | `q6`：新号全空，序章也不落库 |
| 16 | `ShopGachaRecruitListResponse` | 有内容 | **529**（官方 529） | `q10`：`ShopRecruitDBSchema` 去掉 Id 1/2/3 |
| 17 | `TimeAttackDungeonLoginResponse` | null 字段 | PreviousRoomDB null | spec nullable |
| 18 | `BillingPurchaseListByYostarResponse` | 空 | 0 / 0 / 0（官方 4） | 没氪金（§7-9） |
| 19 | `EventContentPermanentListResponse` | 空 | 0（官方 22） | 未找到目录来源（§7-6） |
| 20 | `AttachmentEmblemListResponse` | 有内容 | **5**（官方 14） | `q3`：ParcelType=20 五行 |
| 21 | `AttachmentGetResponse` | 有内容 | EmblemUniqueId 1 | `ConstCommonExcel.EmblemDefaultId = 1` |
| 22 | `ContentSweepMultiSweepPresetListResponse` | 1 条空预设 | 1（StageIds 0） | 官方那 1 条本身就是 `PresetId:0 / PresetName:""` 的空预设 |
| 23 | `EliminateRaidLoginResponse` | 零值结构 | — | 未找到赛季号 |
| 24 | `StickerListResponse` | 空 | 0（官方 20） | 未找到默认贴纸集合（§7-7） |
| 25 | `MultiFloorRaidSyncResponse` | null 字段 | MultiFloorRaidDBs null | spec nullable |
| 26 | `MultiFloorRaidLoginResponse` | 零值 | LastClearedDifficulty 0 | 未打过 |
| — | `FriendCount` / `FriendCode` | 0 / 7 位码 | — | `FriendCode` 由 server_id 派生（§7-13） |
| — | `PickupFirstGetHistoryDBs` | 空 | 0（官方 1） | 新号没抽过卡 |
| — | `AccountLevelRewardIds` | 空 | 0（官方 1） | 主数据推导，见 §6.4 |

**信封口径**：26 个子回包的 `Protocol / SessionKey / ServerTimeTicks / ServerNotification / RequestId` 全是零值
（`0 / {AccountServerId:0, MxToken:""} / 0 / 0 / ""`），生成器里一个都没写，是 spec 的必填默认值补出来的；生成后有断言复核（`子包信封零值 OK`）。只有顶层信封带真值。

### 4.2 三条硬口径

1. **子回包信封零值**（官方 26 个子回包全部如此，见 §6.2）。
2. **「内容目录」用主数据撑满**：商店 529 个 banner、咖啡厅 11×2 件默认家具、徽章 5 个、学院 71 个 zone。
3. **「账号进度」一律从零开始**：剧情 0、关卡 0、章节奖励 0、装备 0、抽卡历史 0、等级奖励 0、永久活动 0、贴纸 0、氪金计数 0。

---

## 5. spec 完整性验证（结构对比）

对 `我们 vs 官方` 逐层递归比对**键集合**（对象比字段名、数组比首元素形状），结果：

| 协议 | 顶层键序 | 键集合差异 | 结论 |
|---|---|---|---|
| 24000 | 与官方完全一致 | **0 处** | 24 个 spec 节点全部命中，无多余键、无缺失键 |
| 1017 | 与官方完全一致（35 键顺序相同） | 2 处，都是**空 map 的键** | 见下 |

那 2 处「只有官方有」的键，都不是结构问题，是数据为空：

* `CafeGetInfoResponse.CafeDBs[0].CafeVisitCharacterDBs`：官方 4 个键（4 个访客角色 id），我们是 `{}`（新号还没有访客调度）。
* `MomoTalkOutLineResponse.FavorScheduleRecords`：官方 1 个键（`13010`），我们是 `{}`（新号没有好感日程记录）。

**这轮验证说明 spec 是完整的**：`server_apply_skeleton` 里一共给了角色/道具/徽章/货币/编队/咖啡厅/剧情/教程/商店/记忆大厅/学院地点这些库，`conform` 的 `dropped_keys` 计数是 **0** —— 数据里没有一个键是 spec 不认识的。反过来说，spec 的 490 个 1017 节点、24 个 24000 节点，没有一个是「官方这次碰巧没发、spec 就漏了」的必填键。

同时验证了 spec 的两个已知弱点（都在 `_meta.low_confidence` 里自己标了）：

* `CafeGetInfoResponse.CafeDBs[].FurnitureDBs[].Rotation` 与 `...FurnitureDBs[].Rotation` 被 spec 标成 `fields_rare`（seen 2 / of 25、seen 2 / of 27）—— 出现次数 ≤2，可选性证据很弱。本生成器对应地**只在真有旋转值的那件家具上输出 Rotation**（官方也是 2/25 行有），于是这部分产生 40 条「可选键缺失」WARN，是预期内、且 spec 自己也承认不确定的部分。
* `ItemListResponse` 被记成 `type=null`（官方只观测到 null）—— 这是 spec 的一处**形状信息缺失**，见 §6.3。

---

## 6. 数据差异：官方 32 级号 vs 本原型新号

官方账号真实等级 32（`ClanLoginResponse.AccountClanMemberDB.AccountLevel`）。

| 协议 | 字段 | 官方 32 级号 | 本原型新号 | 说明 |
|---|---|---|---|---|
| 1017 | `CharacterListResponse.CharacterDBs` | 46 | **4** | 4 个初始角色（优香/铃美/莲见/千夏） |
| 1017 | `EquipmentItemListResponse.EquipmentDBs` | 84 | **0** | 新号没有任何装备（`q3`） |
| 1017 | `CharacterGearListResponse.GearDBs` | 0 | 0 | 都是空 |
| 1017 | `ItemListResponse` | null | null | 两边都是 null（spec 的限制，§6.3） |
| 1017 | `EchelonListResponse.EchelonDBs` | 8 | **1** | 官方 8 条是多内容解锁后累积的 |
| 1017 | `CafeGetInfoResponse.CafeDBs` | 2 | 2 | 一致 |
| 1017 | `CafeGetInfoResponse.FurnitureDBs` | 27 | **22** | 官方 27 = cafe1 的 14 + cafe2 的 11 + 2 件未摆放（`CafeDBId=0`） |
| 1017 | `CafeDBs[1].FurnitureDBs` | 11 | 11 | 官方 cafe2 恰好是初始态（Rank 1 + 11 件默认家具），可交叉验证 |
| 1017 | `CurrencyDict` 键数 | 29 | 29 | 都是 1..29 全 29 键（值为 0 的也在） |
| 1017 | `CurrencyDict` 金额合计 | 28,263,233 | **10,774** | 官方玩了很久；新号只发 `DefaultParcelExcel` 的初始量 |
| 1017 | `UpdateTimeDict` 键数 | 19 | 19 | 都是「会随时间恢复的货币」那 19 个 |
| 1017 | `ScenarioHistoryDBs` | 191 | **0** | 剧情进度 |
| 1017 | `ScenarioGroupHistoryDBs` | 21 | **0** | 剧情组进度 |
| 1017 | `CampaignListResponse.StageHistoryDBs` | 90 | **0** | 关卡进度 |
| 1017 | `CampaignChapterClearRewardHistoryDBs` | 12 | **0** | 章节奖励 |
| 1017 | `ShopGachaRecruitListResponse.ShopRecruits` | 529 | **529** | 内容目录：两边一样 |
| 1017 | `AttachmentEmblemListResponse.EmblemDBs` | 14 | **5** | 官方后面又拿了 9 个 |
| 1017 | `EventContentPermanentListResponse.PermanentDBs` | 22 | **0** | 未找到目录来源 |
| 1017 | `StickerListResponse.UnusedStickerDBs` | 20 | **0** | 未找到默认贴纸集合 |
| 1017 | `BillingPurchaseListByYostarResponse.CountList` | 4 | **0** | 新号没氪金 |
| 1017 | `MemoryLobbyListResponse.MemoryLobbyDBs` | 1 | 1 | 一致（`{Type:8, 13010}`） |
| 1017 | `MomoTalkOutLineDBs` | 1 | **0** | 未找到初始规则 |
| 1017 | `PickupFirstGetHistoryDBs` | 1 | **0** | 没抽过卡 |
| 1017 | `AccountLevelRewardIds` | 1 | **0** | 官方 `[1]` = 等级 30 那档已达成；新号 Level 1 → `[]` |
| 1017 | `FriendCount` | 0 | 0 | 一致 |
| 24000 | `ZoneVisitCharacterDBs` 键数 | 71 | 71 | 一致（推导见 §3） |
| 24000 | zone 内角色条目合计 | 138 | **0** | 官方单样本 138 条（两样本合计 276 = spec 的 `seen=276`） |
| 24000 | `AcademyLocationDBs` | 9 | **1** | 初始条数「未找到」，用最小实现 |
| 24000 | `AcademyLocationDBs` Rank 之和 | 14 | **1** | 与上一条同源 |
| 24000 | `ZoneScheduleGroupRecords` | `{}` | `{}` | 一致 |

另外（不在 1017 里，但同属「少了什么」）：官方 `4000 Item_List` 有 **134** 条道具（35,108 B），新号按 `q3` 应该有 **1** 条（加速券 ×5）。因为 1017 的 `ItemListResponse` 只能是 null，这 1 条道具在本次产物里**下发不出去**，要等 4000 实现（§8）。

---

## 7. 逐条判断与踩到的坑

### 7.1 `ZoneVisitCharacterDBs` 的 71 个 zone：给空数组还是填初始角色？→ **给空数组**

四条理由：

1. **语义**：这个库的记录是 `{UniqueId, ServerId, LastInteractTime}`，`LastInteractTime` 是「最近一次交互时间」。新号一次都没访问过学院，没有任何交互时间可写。
2. **上界**：spec 记的 `len_max = 3`（单个 zone 最多 3 个角色）。4 个初始角色若都塞进同一个 zone 就会超出观测上界；分散到 4 个 zone 又没有任何规则支持。
3. **合法性**：spec 记的 `empty_observations = 2` —— 官方样本里**确实出现过空数组**，空是合法形态（官方 71 个 zone 里有 1 个就是空的）。
4. **自洽**：学院访问由 `AcademyDB.ZoneScheduleGroupRecords` 调度驱动，新号这个字段是 `{}`（且 spec 要求必须空）。没有调度却有访问记录，才是自相矛盾。

顺带：71 个键 vs 只有 1 个学院地点，这一点本身有张力 —— 严格状态驱动应该是「本账号拥有的 location 的 zone」= 8 个。所以生成器留了开关：

```bash
python work/ba/server/prototype/gen_new_account.py --zone-scope account   # 8 个 zone（严格状态驱动）
python work/ba/server/prototype/gen_new_account.py                        # 71 个 zone（默认，= spec key_count）
```

默认取 71 的理由：spec 的 `key_count` 就是 71（客户端对这张 map 的遍历期待这个规模），多给空 zone 无害、少给可能让某些 location 的学院渲染不出来。

### 7.2 子回包信封：任务说 3 个字段零值，实测是 **5 个**

任务描述里点名 `SessionKey / Protocol / RequestId` 零值。把官方 1017 的 26 个子回包逐个打开核对，实际是 **5 个字段全零**，多出来两个：

| 字段 | 26 个子回包 |
|---|---|
| `Protocol` | 全 0 |
| `SessionKey` | 全 `{AccountServerId: 0, MxToken: ""}` |
| `ServerTimeTicks` | 全 0（顶层是真值 639304002554622705） |
| `ServerNotification` | 全 0 |
| `RequestId` | 全 `""`（顶层是 36 字符 uuid4） |

本生成器按 5 个全零实现（信封由 spec 默认值补），并在 `gen_1017.py` 里加了断言。**这条只能从样本实测得到** —— spec 是纯形状规格，`values_included: false`，它记不下「这个 int 恒为 0」。

### 7.3 `ItemListResponse` 只能是 `null`，但新号其实有 5 张加速券

`initial_state_rules.server_apply_skeleton.ItemDBs` 明明白白写着新号有 1 种道具（加速券 ×5），`q3` 还专门论证了「官方 4000 的 `ItemListResponse` 是 null 是因为那号把券花完了，null ≠ 新号没道具」。

但 `official_spec.json` 把 1017 的 `ItemListResponse` 记成了 `type: "null", nullable: true` —— 因为官方那次只观测到 null，spec 没有值可提取形状，于是只能记 null。`spec_check.py` 对 `type=null` 的处理是「非 null 一律 FAIL」，所以本原型**必须**发 null。

这是 **spec 的一处形状信息缺失**（同一现象也在 `CraftInfoListResponse` 的 3 个数组、`StickerListResponse.UsedStickerDBs` 等 `items=null` 的位置出现）。要真正下发新号那 5 张加速券，得走 `4000 Item_List`：spec 里 4000 的形状是完整的（`ItemDBs` / `ExpiryItemDBs`，官方 134 条）。**修 spec 的正确做法是补一条 4000 的处理**，而不是把 1017 的 `ItemListResponse` 改成 object —— 后者会让本次验收直接 FAIL（多键 + 形状不符）。

### 7.4 `AccountLevelRewardIds`：规则是推出来的，并复现了官方值

`AccountLevelRewardDBSchema` 6 行、`Level` 列 = `[30, 40, 45, 50, 55, 60]`。假设语义是「等级奖励按等级解锁、`AccountLevelRewardIds` = 已达成的批次」，则：

* 官方 Level 32 → `Level <= 32` 的只有 Id=1（Level 30）→ `[1]`，**与官方样本完全一致**（这是一次强验证）；
* 新号 Level 1 → 一档都达不到 → `[]`（长度 0 会 WARN，属于预期）。

### 7.5 `ServerTimeTicks` 的单位：.NET 100ns ticks（自 0001-01-01）

官方 24000 的 `ServerTimeTicks = 639304002548158993`（18 位），同一条响应里 `AcademyDB.LastUpdate = 2026-11-16T04:00:06.479`。逐个候选单位代入：

| 假设 | 换算结果 | 结论 |
|---|---|---|
| unix 纳秒 | 1990-04-05 | 否 |
| unix 微秒/毫秒 | 越界 | 否 |
| **.NET ticks（自 0001-01-01，100ns）** | **2026-11-16T04:30:54** | **是**（与同响应的时间戳同一天、相差 30 分钟属正常） |

另有一条独立佐证：`3 NetworkTime_Sync` 里 `ReceiveTick` / `EchoSendTick` 与 `ServerTimeTicks` 是同一个量级（639304002554622693）。所以 `specgen.server_time_ticks()` 用 `(dt - 0001-01-01) 的 100ns 数`。

### 7.6 `ComfortValue` 不是抄的 220，是从 `FurnitureDBSchema.f24` 算出来的

咖啡厅 `ProductionDB.ComfortValue` 必须是个数。规则文件没写，但：

* `FurnitureDBSchema`（876 行）的 `f24` 字段，11 件默认家具（Id 1..11）**每件都是 20**；
* 20 × 11 = **220**；
* 官方 `CafeDBs[1]` 恰好是「CafeRank 1 + 只有那 11 件默认家具」的初始态，其 `ComfortValue` 正是 **220**。

于是生成器里写的是「`FurnitureDBSchema.f24` 求和」（`MasterData.furniture_comfort`，自带一个最小 FlatBuffers vtable 读取器），而不是硬编码 220；官方那个值只用来做交叉验证。输出里 `ComfortValue=220 {1:20, …, 11:20}` 就是算出来的。

### 7.7 `FurnitureDB.Type = 13`：规则表没有这个枚举值

规则文件的 `not_found` 里写了「ParcelType 已确认 Character=1 / Currency=2 / Item=4 / Emblem=20，其余未找到」。家具的 `Type` 官方 27 行**恒为 13**（枚举常量，不是账号数据），本原型取 13 并在此登记为「规则表缺项 → 取官方恒定枚举值」。

### 7.8 家具 27 vs 22 的差，不是少了 3 件

官方顶层 `FurnitureDBs` 27 条 = cafe1 的 14 件 + cafe2 的 11 件 + **2 件 `CafeDBId=0`、`ItemDeploySequence=0` 的未摆放家具**。新号 22 条 = 11 × 2（每厅一份），没有「买了还没摆」的存货，所以少 2 条是**状态正确**，不是数据丢失。

### 7.9 「可选键 `Rotation` 40 条 WARN」的解释

`Rotation` 在 spec 里 `always=false`（25 行里只有 2 行出现过，正是 2 个咖啡厅里那件 270° 的「原木收纳柜」）。proto3 里这属于「presence-tracked 可选标量」：没有值就**不出现**。本生成器按同样语义处理 —— 只有 `q9` 表里写了旋转角的那件（FurnitureId=5）输出 `Rotation: 270`，其余 40 行不输出。

如果为了让 WARN 归零而给每行都发 `Rotation: 0`，反而与官方行为不一致（官方 22/25 行是省略的）。所以这里选择「行为对、WARN 留着」。

### 7.10 官方 1017 的子回包 body 本身就是「部分默认值」

几个反例说明这一点：

* `AccountCurrencySyncResponse.AccountCurrencyDB.AccountLevel = 1`，但同一个账号在 `ClanLoginResponse.AccountClanMemberDB.AccountLevel = 32`，且 `CurrencyDict` 合计 2,800 万；
* `AcademyLocationRankSum = 1`，而 24000 里 9 个地点的 Rank 之和是 14（规则文件 q8 也点了这个「陷阱」）。

也就是说登录同步时，服务端只填了一部分字段，其余是 proto3 默认值。这对我们是好事：**新号的 `AccountLevel` 恰好就是 1、`AcademyLocationRankSum` 也恰好是 1**（1 个地点 Rank 1），所以这两处与官方样本「巧合一致」，不会被误判成抄。

### 7.11 `TutorialIds ← []` 这条要求在 1017 里无处安放

任务里列了 `TutorialIds ← 空 list`，但 **1017 的 35 个顶层键里没有 `TutorialIds`**：

* 在 `official_spec.json` 里搜 `TutorialIds`，只出现在 **1005 Account_GetTutorial**（`$.TutorialIds`，`array<int>`，官方 21 条）；
* 真往 1017 里塞这个键，`spec_check.py` 会判「多键 → FAIL」。

所以本原型**按 spec 不输出**；`TutorialIds = []` 属于 1005 的职责（规则 q7 明确新号 `TutorialIds = []`），列进下一步。

### 7.12 「不在战队」的形态没有官方样本可比

官方那个号在战队里（`ClanDBId = 27353`、50 人）。新号不在战队，规则文件也没覆盖。本原型的处理：

* `AccountClanDB` 全零（`ClanDBId 0` / 名称、频道名、公告、会长昵称全 `""` / 人数、管理数、JoinOption 全 0）；
* `AccountClanMemberDB` 里**指代本账号**的字段仍写真值（`AccountId = server_id`、`AccountLevel = 1`、`RepresentCharacterUniqueId = 13010`（初始 Leader 优香）、`AttachmentDB = {AccountId: server_id, EmblemUniqueId: 1}`），与战队相关的（`ClanDBId`、`ClanSocialGrade`、`AttendanceCount`）为 0，日期字段为零值时间，`GameLoginDate` = 本次登录时间。

`ClanChannelName` 官方是 `channel_<ClanDBId>` 的形态；不在战队时给 `""`（不是 `channel_0`）。

### 7.13 WARN 83 条的完整归因（不是结构问题）

| 类别 | 条数 | 归因 |
|---|---|---|
| 可选键缺失（`Rotation`） | 40 | proto3 可选标量 presence 语义，官方同样省略（§7.9） |
| 长度越界・账号规模比官方小 | 5 | 角色 4/46、装备 0/84、编队 1/8、徽章 5/14、家具 22/27 |
| 长度越界・空槽数组 | 4 | 4 个角色的 `EquipmentServerIds` 都是 `[]`（新号无装备） |
| 长度越界・未找到 / 未发生 | 10 | 咖啡访客 0/3..4 ×2、生产队列 0/1..2 ×2、MomoTalk 0/1、好感日程 0/1、永久活动 0/22、贴纸 0/20、氪金计数 0/4、多倍扫荡关卡 0/10 |
| 长度越界・进度归零 | 6 | 章节奖励 0/12、关卡 0/90、剧情 0/191、剧情组 0/21、抽卡首获 0/1、等级奖励 0/1 |
| 空数组首见 | 18 | 上面「新号就是空」的那些位置里，官方样本从未出现空数组的 18 处 |

（40 + 5 + 4 + 10 + 6 + 18 = 83，与 `spec_check.py` 的 WARN 总数一致。）

`spec_check.py` 的口径是「可选键缺失 / 长度越界 / 空数组首见 = WARN（合法），只有缺键 / 多键 / 类型不符 / 可空性不符 / 数组元素形状不符 = FAIL」。本次 FAIL 为 **0**。

---

## 8. 「未找到」清单（明确留空，没有编造）

| # | 项 | 落在哪个字段 | 现状 | 要补什么 |
|---|---|---|---|---|
| 1 | 学院地点初始**条数** | `AcademyLocationDBs`（24000） | 1 条（用 q8 的最小实现） | 官方样本 9 条但规则未闭合；建议按「已访问 location」实现，或从客户端解锁流程反推 |
| 2 | 咖啡厅**访客调度** | `CafeDBs[].CafeVisitCharacterDBs` | `{}` | 官方键是「角色 UniqueId → {UniqueId, ServerId, LastInteractTime}」；选择规则未找到（`CafeInteractionDBSchema` 253 行像是抽取池） |
| 3 | 咖啡厅**生产队列**初值 | `CafeDBs[].ProductionDB.ProductionParcelInfos` | `[]` | 官方是 1~2 条 `{Key:{Type:2,Id}, Amount}`；与 `CafeProductionDBSchema`(30) 的关系未解 |
| 4 | 竞技场初始分组/段位/赛季 | `ArenaPlayerInfoDB` 9 键 | 全 0 + 零值时间 | 官方 `CurrentSeasonId=9 / PlayerGroupId=322 / CurrentRank=13720`，属赛季全局配置 |
| 5 | 「不在战队」的官方形态 | `ClanLoginResponse` | 全零 + 账号自指字段真值 | 需要一个没战队的账号样本 |
| 6 | 永久活动内容目录 | `EventContentPermanentListResponse.PermanentDBs` | `[]` | ExcelDB 里没有 `EventContentPermanentDBSchema`（只有 58 张其他 EventContent 表） |
| 7 | 默认贴纸集合 | `StickerBookDB.UnusedStickerDBs` | `[]` | `StickerPageContentDBSchema` 23 行 ≠ 官方 20 条，数量对不上，不猜 |
| 8 | MomoTalk 初始记录 / 好感日程 | `MomoTalkOutLineDBs` / `FavorScheduleRecords` | `[]` / `{}` | `MomotalkScheduleSpoilerPopupDBSchema` 只有 1 张表，对不上 |
| 9 | 氪金商品计数 | `BillingPurchaseListByYostarResponse.CountList` | `[]` | `ShopCashDBSchema` 656 行 ≠ 官方 4 条，官方那 4 条像「曾购买过的商品计数器」 |
| 10 | 新号昵称 | `AccountClanMemberDB.AccountNickName` | `""` | 建号时的昵称规则（例如是否取「老师」+ 序号） |
| 11 | `FriendCode` 规则 | `FriendCode` | 由 `server_id` 派生 7 位大小写字母数字 | 官方 7 位、字母数字混合；派生规则未找到 |
| 12 | 商店 banner 的日期码解码 | `ShopRecruits[].Sales*Date/UpdateDate` | 合成「长期开放」区间 `2000-01-01 ~ 2099-12-31` | `ShopRecruitDBSchema` 的 f15/f16 是 `1900000+` / `79999` 段日期码，解码规则未解 |
| 13 | 国服当前赛季号 | `RaidLoginResponse.SeasonType` / `EliminateRaidLoginResponse.SeasonType` | 0 | 官方 1 / 2 像全局赛季枚举，属服务端配置 |
| 14 | 当前剧情指针 | `CampaignListResponse.CurrentScenarioId` | 0 | 官方 41200 是进度值；新号起点应为「序章之后」，`q6` 没给 |
| 15 | `ParcelType` 家具枚举 | `FurnitureDBs[].Type` | 13（取官方恒定值） | 规则表 `not_found` 第 4 条：只确认了 1/2/4/20 |

---

## 9. 已知局限 / 下一步

**局限**

1. 没有连服务器、没有连手机、没有跑客户端 —— 本轮的验收标准只有 `spec_check.py`（结构），**行为正确性（客户端能不能进大厅、咖啡厅会不会崩）未验证**。
2. 时间字符串按 RFC3339Nano 风格生成（小数位尾零裁掉），与官方一致；但客户端解析容错度未测。
3. `ServerId` 用的是本实现自己的派生公式（见 §2），与官方自增号不同 —— 结构合法、账号内自洽，但**跨协议一致性**要靠后续所有生成器共用同一套 `obj_id`。
4. WARN 83 条没有清零，这是有意保留的（每一条都对应「新号确实没有」或「可选字段官方也省略」）。

**下一步（按依赖顺序）**

1. **1005 Account_GetTutorial** —— 承接 `TutorialIds = []`（规则 q7 已完备，spec 只有 10 个节点，最快）。
2. **4000 Item_List** —— 承接新号那 1 种道具（加速券 ×5）；同时决定要不要给 spec 补一条「1017 的 `ItemListResponse` 形状」的注记。
3. **5000 Echelon_List / 5001 Echelon_Save** —— 编队读写闭环（spec 置信度 high，obs=4/2）。
4. **咖啡厅访客调度** —— 把 `CafeVisitCharacterDBs` / `ZoneVisitCharacterDBs` 从「空」变成「按日期抽取」，需要先把 `CafeInteractionDBSchema` / `AcademyFavorScheduleDBSchema` 的语义解出来（这两处正是当前 WARN 的主要来源）。
5. **把 71 个 zone 与 `AcademyLocationDBs` 对齐** —— 即 §7.1 的 `--zone-scope account` 变成默认（等学院解锁流程实现后再切）。

---

## 10. 附录：本次实测的格式口径（写生成器时踩过的）

| 项 | 官方实测形态 | 本实现 |
|---|---|---|
| `ServerTimeTicks` | 18 位、.NET 100ns ticks 自 0001-01-01 | 同 |
| 时间串 | `2026-11-16T04:00:06.479`（毫秒、尾零裁掉）；`UpdateTimeDict` 里是 9 位纳秒 | 同（`fmt_time(frac=3/9)`） |
| 零值时间 | `0001-01-01T00:00:00` | 同（常量 `ZERO_TIME`） |
| 顶层 `RequestId` | 36 字符 uuid4 | uuid4 |
| `MxToken` | 64 字符 base64 | sha384 → base64，正好 64 字符 |
| 子回包信封 | 5 字段全零 | 由 spec 默认值补 |
| `ParcelType` | Character 1 / Item 4 / Emblem 20 / Furniture 13 | 同 |
| 空槽 | 编队 `SupportSlotServerIds = [x, 0]`、`MainSlotServerIds` 补 0 | 同 |
| 角色无装备 | 官方样本中没有 `EquipmentServerIds` 为空的行可参照 | `[]`（语义 = 没装备；长度会 WARN） |
