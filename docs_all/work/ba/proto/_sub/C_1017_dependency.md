# Account_LoginSync(1017) 依赖分析与响应清单

**数据源**：`report/_tmp/official_decoded_201/`（官方国服 HAR 解密，201 条条目 / **109 条游戏 RPC 请求 + 109 条响应**）
**产出机器可读件**：`C_1017_dependency.json`、`C_1017_response_inventory.json`（本目录）
**生成脚本**：`analyze1017.py`、`build_deliverables.py`（本目录，只读抓包，仅写本目录）

---

## 中文提要（结论先行）

1. **1017 的请求与 24000 的响应之间没有数据依赖。** 1017 的 9 个请求字段全部可以归因为：客户端常量（`OStype/Resendable/IsTest/Protocol/OSType`）、1002 响应（`SessionKey`/`AccountId`）、本地请求计数器（`Hash`）、以及客户端自己的常量表（`SyncProtocols`、`SkillCutInOption`）。**24000 的响应里没有任何一个字段能产出这 25 个协议 id 组成的数组。**
2. 24000 → 1017 是 **顺序依赖 / 派发-完成依赖**：客户端登录协程 `1002 → 24000 → 1017` 是写死的代码顺序，24000 必须**成功返回**，协程才继续发 1017；但 1017 的内容不读取 24000 的任何返回值。0.130 s 是 await + 序列化耗时。
3. **1017 的响应是一个 35 键的扁平聚合包**（26 个 `*Response` 成员槽 + 5 个外层信封键 + 4 个聚合尾部字段），其中 25 个成员被填充、`ItemListResponse` 为 `null`。**这 25 个填充成员与请求里的 25 个 `SyncProtocols` 一一对应（集合精确匹配）**，唯一不在 `SyncProtocols` 里的槽 `ItemListResponse`(4000) 恰好就是 `null`，而客户端在 1017 响应后 **0.350 s** 立刻单独发了 `Item_List(4000)`。
4. **21 个协议在整份抓包里从未被单独调用**——1017 的响应是它们在登录期的唯一数据来源。这决定了我们私服必须一次性把 25 个成员都填好。

---

## Part 1 — 1017 的 REQUEST 是否依赖 24000 的 RESPONSE？

### 1.1 原始请求

文件：`report/_tmp/official_decoded_201/02_1017_api_account_loginsync.request.json`
`meta`: bj `04:30:55.110`，`req_bytes` 1182，`protocol` 1017，`protocol_name` `Account_LoginSync`

```json path=report/_tmp/official_decoded_201/02_1017_api_account_loginsync.request.json
{"Protocol":1017,
 "SyncProtocols":[20000,1003,2000,3000,5000,12000,6000,22001,17018,21000,28001,33000,19000,
                  10006,39006,44000,29002,30041,45000,46000,46001,47000,49000,27002,49004],
 "SkillCutInOption":"OnceADay",
 "Resendable":true,
 "Hash":4367981740035,
 "IsTest":false,
 "SessionKey":{"AccountServerId":10015354380,"MxToken":"Vji5A/Cy6X2enQZKeYgrjxAC8MoRDOCT2Tb1SW13PcZTq2cnyCPPdd81pGbzYBKA"},
 "AccountId":10015354380,
 "OSType":2}
```

**恰好 9 个键，没有 `RequestId`。**

### 1.2 逐字段归因表

严格性约定（与 `C_1017_dependency.json` 的 `presence_test_caveat` 一致）：字面值命中只有在**同名字段也存在于该响应**时才算证据；`true`/`false`/`2` 这类布尔和小整数在任何响应里都能"命中"，属平凡命中。**晚于 1017 的响应一律不作为来源证据。**

| # | 字段 | 类型 | 字面值 | 归因 | 证据（文件 + 次数） | 置信度 |
|---|---|---|---|---|---|---|
| 1 | `Protocol` | int (Protocol 枚举) | `1017` | 客户端常量（请求自身的协议号） | 109/109 请求都有；`1017` 作为标量值在**任何**响应中出现 **0** 次 | certain |
| 2 | `SyncProtocols` | array\<int\>（DTO: `List<Protocol>`） | 25 个协议 id | **客户端常量表**（按 DTO 类型只可能是协议 id） | 25 个 id 中 **16 个在整份抓包里作为标量值出现 0 次**；其余 9 个只命中无关的 `UniqueId`/`MissionUniqueId`；24000 响应里无任何协议 id 数组 | certain |
| 3 | `SkillCutInOption` | string | `"OnceADay"` | **客户端常量 / 本地设置**，未找到任何服务端来源 | `"OnceADay"` 在 **109 个请求 + 109 个响应中总共只出现 1 次**（即本请求）；`dto_schema.json` 里该字段声明为普通 `string`；另一份观测（`observed_sequence.json`）中同一客户端发的是 `""` | high |
| 4 | `Resendable` | bool | `true` | **客户端常量**（基类 `RequestPacket` 默认值） | 108/109 请求都有，**唯一取值 `true`**；作为 JSON **键**在任何响应中出现 **0** 次；唯一没有它的是 1002（不同信封） | certain |
| 5 | `Hash` | int64 | `4367981740035` | **本地客户端状态**：`(Protocol<<32) \| 会话请求计数器` | `1017<<32 = 4367981740032`，`+3 = 4367981740035`；全 109 条请求 hi32==Protocol **109/109**，low32 = 1,2,3,…,109 严格递增。1002=1、24000=2、**1017=3** | certain |
| 6 | `IsTest` | bool | `false` | **客户端常量** | 108/109 请求都有，**唯一取值 `false`**；作为 JSON 键在响应中出现 **0** 次 | certain |
| 7 | `SessionKey.AccountServerId` | int64 | `10015354380` | **1002 `Account_Auth` 响应** | 1002 响应的 `SessionKey.AccountServerId` / `AccountDB.ServerId` / `RoleId` 均为该值；**1002 的请求里根本没有 `SessionKey` 字段**（故只能由 1002 响应进入客户端状态）；24000 响应只是回显 | certain |
| 8 | `SessionKey.MxToken` | string(64, base64) | `Vji5A/Cy6…YBKA` | **1002 `Account_Auth` 响应** | 与 1002 响应 `SessionKey.MxToken` **逐字节相同**。（对外层 `plain` 做子串扫描得 0 次，是因为 1002 的 `plain` 是转义后的嵌套 JSON 字符串；解码后的 `inner` 精确匹配。）24000 响应再次回显 | certain |
| 9 | `AccountId` | int64 | `10015354380` | **1002 `Account_Auth` 响应**（`AccountDB.ServerId`，与 `SessionKey.AccountServerId` 同值） | 该值在**早于 1017 的响应中出现 14 次**，全部位于 1002 响应内部；1002 的请求没有 `AccountId` | certain |
| 10 | `OSType` | int (枚举，2) | `2` | **客户端常量（平台字面量）**，非服务端数据 | 108/109 请求都有且**只有 1 种取值（2）**；作为 JSON 键在**任何响应中出现 0 次**；1002 响应里没有 `OSType` 字段（1002 请求已用 `OSVersion:"Android OS 17 / ..."` 声明平台） | high |
| — | `RequestId` | — | **不存在** | 请求无此字段 | 1017 请求键集合就是上面 9 个；`RequestId` 是**响应侧**服务端生成的 UUID | certain |

> **关键否证**：`24000` 的请求（bj `04:30:54.980`）**已经包含** `SessionKey`/`AccountId`/`OSType`/`IsTest`/`Resendable`/`Hash` 全部信封字段——比 1017 早 0.130 s，且这些值的来源是 1002 响应与本地计数器。24000 的响应不可能"回头"决定 1017 的信封。

### 1.3 `SyncProtocols` 25 个数字 → 协议名映射

`SyncProtocols` 是 `List<Protocol>`，所以每个数字都是**协议号**。映射后与 1017 响应里的 25 个 `*Response` 成员**一一对应**：

| # | id | 协议名 | 对应的响应成员 | 抓包内是否另发单独调用 |
|---|---|---|---|---|
| 0 | 20000 | `Cafe_Get` | `CafeGetInfoResponse` | 否（只有 20001 `Cafe_Ack`、20013 `Cafe_ReceiveCurrency`） |
| 1 | 1003 | `Account_CurrencySync` | `AccountCurrencySyncResponse` | 否 |
| 2 | 2000 | `Character_List` | `CharacterListResponse` | 否 |
| 3 | 3000 | `Equipment_List` | `EquipmentItemListResponse` | 否 |
| 4 | 5000 | `Echelon_List` | `EchelonListResponse` | **是**，+42.137 s 起共 4 次 |
| 5 | 12000 | `MemoryLobby_List` | `MemoryLobbyListResponse` | 否 |
| 6 | 6000 | `Campaign_List` | `CampaignListResponse` | **是**，+31.520 s |
| 7 | 22001 | `Arena_Login` | `ArenaLoginResponse` | 否（另发的是 22000 `Arena_EnterLobby`） |
| 8 | 17018 | `Raid_Login` | `RaidLoginResponse` | 否 |
| 9 | 21000 | `Craft_List` | `CraftInfoListResponse` | 否 |
| 10 | 28001 | `Clan_Login` | `ClanLoginResponse` | 否（另发的是 28000 `Clan_Lobby`） |
| 11 | 33000 | `MomoTalk_OutLine` | `MomoTalkOutLineResponse` | 否 |
| 12 | 19000 | `Scenario_List` | `ScenarioListResponse` | 否 |
| 13 | 10006 | `Shop_GachaRecruitList` | `ShopGachaRecruitListResponse` | 否（另发的是 10002 `Shop_List`） |
| 14 | 39006 | `TimeAttackDungeon_Login` | `TimeAttackDungeonLoginResponse` | 否 |
| 15 | 44000 | `CharacterGear_List` | `CharacterGearListResponse` | 否 |
| 16 | 29002 | `Billing_PurchaseListByYostar` | `BillingPurchaseListByYostarResponse` | **是**，+6.136 s 起共 3 次 |
| 17 | 30041 | `EventContent_PermanentList` | `EventContentPermanentListResponse` | **是**，+124.230 s |
| 18 | 45000 | `EliminateRaid_Login` | `EliminateRaidLoginResponse` | 否 |
| 19 | 46000 | `Attachment_Get` | `AttachmentGetResponse` | 否 |
| 20 | 46001 | `Attachment_EmblemList` | `AttachmentEmblemListResponse` | 否 |
| 21 | 47000 | `Sticker_Login` | `StickerListResponse` | 否 |
| 22 | 49000 | `MultiFloorRaid_Sync` | `MultiFloorRaidSyncResponse` | 否 |
| 23 | 27002 | `ContentSweep_MultiSweepPresetList` | `ContentSweepMultiSweepPresetListResponse` | 否 |
| 24 | 49004 | `MultiFloorRaid_Login` | `MultiFloorRaidLoginResponse` | 否 |

**这是固定客户端常量还是服务端数据派生的？→ 固定客户端常量。** 依据：
- DTO 声明 `SyncProtocols: List<Protocol>`，类型上只能装协议号；
- 25 个 id 里 16 个（`1003,22001,17018,21000,28001,33000,19000,39006,44000,45000,46000,46001,47000,49000,27002,49004`）**在整份抓包的任何响应里作为标量值一次都没出现过**；
- 另外 9 个的命中全部是巧合的 `UniqueId`/`MissionUniqueId`（例：`20000` 命中 51 次，首次是 `01_24000_…response.json::AcademyDB.ZoneVisitCharacterDBs.25[1].UniqueId`；`29002` 命中的是自己响应的 `Protocol` 头）；
- **24000 的响应里不存在任何协议 id 数组**，从结构上无法派生这个列表；
- `24000` 自己并不在列表里，尽管它刚刚执行过——说明这张表与"刚跑过哪些协议"无关；
- 另一份观测（`observed_sequence.json`，无有效 `SessionKey` 的会话）里同一客户端发的是 **`SyncProtocols: []` + `SkillCutInOption: ""`**，证明这两字段随客户端本地状态变化，而非服务端下发。

### 1.4 结论：**不是数据依赖**

**分类：SEQUENCING（代码顺序）/ DISPATCH-completion（派发-完成）依赖。**
机制：客户端登录协程 `Account_Auth(1002) → await → Academy_GetInfo(24000) → await 响应 → 用本地常量表组装 LoginSync 请求 → Account_LoginSync(1017)`。1017 只在 24000 **成功返回**后发出，但**不读取 24000 的任何返回值**；0.130 s = await + 序列化耗时。

**决定性证据（5 条）**

1. **计数器证据**：1002 的 `Hash` low32 = 1、24000 = 2、1017 = 3；109 条请求 low32 严格 = 1…109。1017 只是本会话第 3 次发送，其内容不因 24000 跑过而改变。
2. **`SessionKey`/`AccountId` 的来源不是 24000**：1002 的**请求**完全没有 `SessionKey` 字段，而 1002 的**响应**首次引入它。24000 请求（早 0.130 s）已经带着同样的值。24000 只是回显。
3. **`SyncProtocols` 无法从 24000 派生**：16/25 在整份抓包中作为标量值 0 命中，其余 9 个只是无关 `UniqueId` 巧合；24000 响应无协议 id 数组；`24000` 本身不在列表内。
4. **`SkillCutInOption` 无服务端来源**：`"OnceADay"` 在 218 个协议文件中出现 **1 次（仅本请求）**，任何响应中 0 次；另一会话同客户端发 `""`。
5. **组成证据**：1017 的键集合 = 基类信封（`Resendable/Hash/IsTest/SessionKey/AccountId/OSType`，108/109 请求共有且各只有 1 种取值）+ `Protocol` + 2 个请求私有字段（`SyncProtocols`、`SkillCutInOption`）。**没有任何 Academy 形状的字段。**

**被否证的假设**（写入 `C_1017_dependency.json.disproved_hypotheses`）

| 假设 | 否证 |
|---|---|
| `SyncProtocols` 由 24000 响应派生 | 24000 响应无协议 id 数组；16/25 全局 0 命中；`24000` 自身不在表中 |
| `SessionKey`/`AccountId`/`OSType` 由 24000 响应提供 | 三者已在 24000 请求中出现（更早 0.130 s），源头是 1002 响应；`OSType` 在响应中作为键出现 0 次 |
| `SkillCutInOption` 是服务端状态 | 任何响应 0 次；DTO 类型为普通 `string`；同客户端另一次发 `""` |
| `Hash` 是服务端签发的种子/令牌 | 109/109 满足 `(Protocol<<32)\|counter`，counter 1…109 严格递增 |
| `RequestId` 由客户端生成 | 1017 请求根本没有该键；它是响应侧服务端 UUID，且 1017 与 24000 响应的值不同 |

**对我们私服仍然重要的两点**

- 24000 必须**成功返回**（HTTP 200 + 合法信封）；失败/转发/零长度会让客户端卡在 1017 之前。这与 `work/ba/proto/observed_sequence.json` 里 2026-11-14 的实测记录一致（"loginsync 回包后需要 24000"）。
- 解析 1017 请求时**不能假设 `SyncProtocols` 有 25 项**——实测存在 `[]`。

---

## Part 2 — 1017 的 RESPONSE 满足了什么？

文件：`report/_tmp/official_decoded_201/02_1017_api_account_loginsync.response.json`
`meta.resp_bytes` = **246808**（线上字节）；解码后明文 `inner` JSON = **167287 B**；线上/明文 = **1.475**。

### 2.1 外层信封（与 24000 对比）

| 字段 | 1017 响应 | 24000 响应 | 1002 响应 | 与 24000 相同？ |
|---|---|---|---|---|
| `Protocol` | `1017` | `24000` | `1002` | 否（各自协议号） |
| `SessionKey` | `{"AccountServerId":10015354380,"MxToken":"Vji5A/Cy6…"}` | 同 | 同 | **是（三者逐字节相同）** |
| `ServerTimeTicks` | `639304002549765374` | `639304002548158993` | `639304002545706815` | 否——**每次响应都新取服务器时钟**，不回显请求 |
| `ServerNotification` | `0` | `0` | `0` | 是（恒 0） |
| `RequestId` | `"bef95b60-6b60-419a-8844-d81f61ca0e05"` | `"3770c1bc-a631-46fb-a9b6-0421ae2601fe"` | `"f24daa29-45e0-4ecb-99bc-6d0ed3bd7c4e"` | 否——**每个响应都是新 UUID**，客户端并不回传 |

### 2.2 顶层键清单（35 个，按线上出现顺序）

`size` 为该键的**明文字节数**（精确）；`%` 为占明文总量的比例。

| 序 | 键 | 类型 | 元素/子键数 | size (B) | % | 映射协议 |
|---|---|---|---|---|---|---|
| 1 | `Protocol` | int | 0 | 4 | 0.00 | — 外层信封 |
| 2 | `SessionKey` | object | 2 | 108 | 0.06 | — 外层信封 |
| 3 | `ServerTimeTicks` | int | 0 | 18 | 0.01 | — 外层信封 |
| 4 | `ServerNotification` | int | 0 | 1 | 0.00 | — 外层信封 |
| 5 | `RequestId` | str | 0 | 38 | 0.02 | — 外层信封 |
| 6 | `CafeGetInfoResponse` | object | 8 | 9799 | 5.86 | **20000 `Cafe_Get`** |
| 7 | `AccountCurrencySyncResponse` | object | 7 | 1096 | 0.66 | **1003 `Account_CurrencySync`** |
| 8 | `CharacterListResponse` | object | 8 | 15595 | 9.32 | **2000 `Character_List`** |
| 9 | `EquipmentItemListResponse` | object | 6 | 9506 | 5.68 | **3000 `Equipment_List`** |
| 10 | `CharacterGearListResponse` | object | 6 | 133 | 0.08 | **44000 `CharacterGear_List`** |
| 11 | `ItemListResponse` | **null** | 0 | 4 | 0.00 | **4000 `Item_List`**（本槽为 null） |
| 12 | `EchelonListResponse` | object | 6 | 2638 | 1.58 | **5000 `Echelon_List`** |
| 13 | `MemoryLobbyListResponse` | object | 6 | 227 | 0.14 | **12000 `MemoryLobby_List`** |
| 14 | `CampaignListResponse` | object | 8 | 30410 | 18.18 | **6000 `Campaign_List`** |
| 15 | `ArenaLoginResponse` | object | 6 | 418 | 0.25 | **22001 `Arena_Login`** |
| 16 | `RaidLoginResponse` | object | 9 | 210 | 0.13 | **17018 `Raid_Login`** |
| 17 | `CraftInfoListResponse` | object | 8 | 179 | 0.11 | **21000 `Craft_List`** |
| 18 | `ClanLoginResponse` | object | 8 | 1000 | 0.60 | **28001 `Clan_Login`** |
| 19 | `MomoTalkOutLineResponse` | object | 7 | 327 | 0.20 | **33000 `MomoTalk_OutLine`** |
| 20 | `ScenarioListResponse` | object | 8 | 22858 | 13.66 | **19000 `Scenario_List`** |
| 21 | `ShopGachaRecruitListResponse` | object | 7 | **66828** | **39.95** | **10006 `Shop_GachaRecruitList`** |
| 22 | `TimeAttackDungeonLoginResponse` | object | 6 | 142 | 0.08 | **39006 `TimeAttackDungeon_Login`** |
| 23 | `BillingPurchaseListByYostarResponse` | object | 8 | 613 | 0.37 | **29002 `Billing_PurchaseListByYostar`** |
| 24 | `EventContentPermanentListResponse` | object | 6 | 1237 | 0.74 | **30041 `EventContent_PermanentList`** |
| 25 | `AttachmentEmblemListResponse` | object | 6 | 1098 | 0.66 | **46001 `Attachment_EmblemList`** |
| 26 | `AttachmentGetResponse` | object | 6 | 187 | 0.11 | **46000 `Attachment_Get`** |
| 27 | `ContentSweepMultiSweepPresetListResponse` | object | 6 | 283 | 0.17 | **27002 `ContentSweep_MultiSweepPresetList`** |
| 28 | `EliminateRaidLoginResponse` | object | 11 | 269 | 0.16 | **45000 `EliminateRaid_Login`** |
| 29 | `StickerListResponse` | object | 6 | 803 | 0.48 | **47000 `Sticker_Login`** |
| 30 | `FriendCount` | int | 0 | 1 | 0.00 | — 聚合尾部 |
| 31 | `FriendCode` | str | 0 | 9 | 0.01 | — 聚合尾部（值 `"slmv4wc"`） |
| 32 | `MultiFloorRaidSyncResponse` | object | 6 | 145 | 0.09 | **49000 `MultiFloorRaid_Sync`** |
| 33 | `MultiFloorRaidLoginResponse` | object | 6 | 146 | 0.09 | **49004 `MultiFloorRaid_Login`** |
| 34 | `PickupFirstGetHistoryDBs` | array | 1 | 63 | 0.04 | — 聚合尾部 |
| 35 | `AccountLevelRewardIds` | array | 1 | 3 | 0.00 | — 聚合尾部（值 `[1]`） |

**尾部字段实际值**：
`FriendCount = 0`；`FriendCode = "slmv4wc"`；
`PickupFirstGetHistoryDBs = [{"ShopRecruitId":5004170,"LogDate":"2026-08-10T13:52:19.949"}]`；
`AccountLevelRewardIds = [1]`。

### 2.3 尺寸要点（我们服务器要吐多少字节）

| 量 | 值 |
|---|---|
| 线上响应体 | **246 808 B** |
| 解码明文（inner JSON 整体） | **167 287 B** |
| 其中 26 个 `*Response` 成员合计 | 166 151 B（99.3%） |
| 其中 5 个信封键 + 4 个尾部键合计 | 1 136 B（0.7%） |
| **Top 5 成员** | `ShopGachaRecruitList` 66 828 + `CampaignList` 30 410 + `ScenarioList` 22 858 + `CharacterList` 15 595 + `CafeGetInfo` 9 799 = **145 490 B = 86.97%** |
| Top 6（含 `EquipmentItemList` 9 506） | 155 996 B = **92.65%** |
| 最小 6 个成员（`CharacterGearList` 133 起） | 合计仅约 1 170 B |

> 尺寸口径说明：`size` 是解码明文的精确 UTF-8 长度；线上字节/明文比在本包为 1.475，但该比值**不是常数**（小包实测 1.98–2.11，如 `19_28019` 536/254=2.110、`13_16000` 556/267=2.082），所以按成员换算的线上字节只能当作**比例估计**，不是测量值。

### 2.4 关键结构发现

1. **每个被填充的 `*Response` 成员都是一个完整的 `ResponsePacket`，且信封头被清零**：
   `"Protocol":0, "SessionKey":{"AccountServerId":0,"MxToken":""}, "ServerTimeTicks":0, "ServerNotification":0, "RequestId":""`
   即：**嵌套成员不继承外层信封的 `SessionKey`**，必须发**全零**头。
2. **成员集合与 `SyncProtocols` 精确双射**：25 个 `SyncProtocols` id ↔ 25 个被填充成员。唯一不在 `SyncProtocols` 的槽 `ItemListResponse`(4000) **就是 null**。
3. **但顺序不是 `SyncProtocols` 顺序**：这是服务端 DTO 顺序（例如 `CharacterGearListResponse`(44000) 排第 10 位而 44000 在 `SyncProtocols` 第 16 位；`EliminateRaidLoginResponse`(45000) 排第 28 位而 45000 是第 19 位）。**照抄观测顺序即可。**
4. `MultiFloorRaidSyncResponse` / `MultiFloorRaidLoginResponse` 虽然对应 `SyncProtocols` 里的 49000/49004，却排在 `FriendCount`/`FriendCode` **之后**。
5. **不要发 `Responses` 数组**：`dto_schema.json` 的 `AccountLoginSyncResponse` 里有一个 `Responses: List<ResponsePacket>`（置信度 `mid`），但官方明文里 `"Responses"` 出现 **0 次**。国服实际是"扁平命名成员"，不是数组。

### 2.5 每个成员 → 能满足哪些请求

抓包窗口：`04:30:55.110`（1017 响应）→ `04:34:22.916`（最后一条），约 3 分 28 秒。

- **21 个协议在整份抓包里从未被单独调用** → 1017 的响应是它们在登录期的**唯一**数据来源：
  `20000 Cafe_Get, 1003 Account_CurrencySync, 2000 Character_List, 3000 Equipment_List, 12000 MemoryLobby_List, 22001 Arena_Login, 17018 Raid_Login, 21000 Craft_List, 28001 Clan_Login, 33000 MomoTalk_OutLine, 19000 Scenario_List, 10006 Shop_GachaRecruitList, 39006 TimeAttackDungeon_Login, 44000 CharacterGear_List, 45000 EliminateRaid_Login, 46000 Attachment_Get, 46001 Attachment_EmblemList, 47000 Sticker_Login, 49000 MultiFloorRaid_Sync, 27002 ContentSweep_MultiSweepPresetList, 49004 MultiFloorRaid_Login`
  注意相邻但**不同**的协议被单独调用，不能拿来替代：`20001 Cafe_Ack`、`20013 Cafe_ReceiveCurrency`、`22000 Arena_EnterLobby`、`28000 Clan_Lobby`、`10002 Shop_List`。
- **4 个协议仍然被单独调用**（属 UI 触发的重新拉取，不是"1017 没提供"）：

| 协议 | 首次单独调用 | 距 1017 响应 | 次数 |
|---|---|---|---|
| 29002 `Billing_PurchaseListByYostar` | `04:31:01.246` | +6.136 s | 3 |
| 6000 `Campaign_List` | `04:31:26.630` | +31.520 s | 1 |
| 5000 `Echelon_List` | `04:31:37.247` | +42.137 s | 4 |
| 30041 `EventContent_PermanentList` | `04:32:59.340` | +124.230 s | 1 |

- **完全不在 1017 覆盖范围、客户端必然另发**的协议（节选，已观察到）：`4000 Item_List`（+0.350 s）、`3 NetworkTime_Sync`、`26000 ContentSave_Get`、`90004 Management_Data`（10 次）、`1005 Account_GetTutorial`、`8000 Mission_List`、`8006 Mission_GuideMissionSeasonList`、`35003 MiniGame_MissionList`、`16000 Toast_List`、`25003 Event_RewardIncrease`（21 次）、`15002 OpenCondition_EventList`、`36001 Notification_EventContentReddotCheck`（10 次）、`7001 Mail_Check`（9 次）、`7000 Mail_List`、`7003 Mail_ListSemiPermanent`、`28019 Clan_Check`（8 次）、`43010 Friend_Check`（8 次）、`24000 Academy_GetInfo`、`22000 Arena_EnterLobby`、`28000 Clan_Lobby`、`10002 Shop_List`、`20001 Cafe_Ack`、`20013 Cafe_ReceiveCurrency`、`90009 Clan_Chat_Records`。

**`ItemListResponse` 是"未请求"而非"无数据"的干净证明**：
①`ItemListResponse` 是一个存在的成员槽，值为 `null`；②`4000 Item_List` 是**唯一**不在请求 `SyncProtocols` 里的成员协议；③客户端因此在 1017 响应后 **0.350 s** 单独发 `Item_List(4000)`，服务端回 16 088 线上字节。
→ 规则：`4000` 不在 `SyncProtocols` 时，`ItemListResponse` 发 `null`，不要"顺手"填充。

### 2.6 私服发 1017 响应的落地顺序（照抄官方）

1. 外层信封顺序：`Protocol, SessionKey, ServerTimeTicks, ServerNotification, RequestId`；`SessionKey` 取会话真实值，`ServerTimeTicks` 每次新取，`RequestId` 每次新 UUID。
2. 26 个 `*Response` 成员**按 2.2 表里的观测顺序**输出。
3. 按请求 `SyncProtocols` 决定填哪些；未请求的槽发 `null`（观测：4000 缺席 → `ItemListResponse: null`）。
4. 每个被填充成员给**全零 `ResponsePacket` 头**，不要复制外层 `SessionKey`。
5. 不要输出 `Responses` 数组。
6. 收尾：`FriendCount, FriendCode, PickupFirstGetHistoryDBs, AccountLevelRewardIds`。
7. 两个 `MultiFloorRaid*` 成员放在 `FriendCode` 之后。

---

## 未找到 / 不可验证

| 项 | 状态 |
|---|---|
| 24000 返回非 200 / 空包时，客户端是"跳过 1017"还是"重试 1017" | **未找到**（抓包只有一次成功登录） |
| `SyncProtocols` 25 项**顺序**是否携带语义（还是纯集合） | **未找到**（只有 1 个正常样本 + 1 个空表样本） |
| 未请求的成员槽除了 `null` 是否可以**直接省略** | **未找到**（官方样本里 26 槽全在，不存在省略样本） |
| `SkillCutInOption` 的枚举全集（`"OnceADay"` 之外的值） | **未找到**（除 `""` 外无第二样本） |
| `AccountLoginSyncResponse` 的 `Responses` 数组形态是否在其它版本/服区使用 | **未找到**（国服明文 0 次出现） |
| 线上字节与明文 1.475 倍的确切编码开销构成 | **未找到**（实测比值随包体变化 1.46–2.11，非固定开销） |
| "21 个协议从未单独调用"在本次 3 分 28 秒窗口之外的会话里是否仍成立 | **窗口受限**（只覆盖到 `04:34:22`） |

---

## 本目录产出

| 文件 | 内容 |
|---|---|
| `C_1017_dependency.json` | 11 条字段级归因（含 `literal_present_*` / `literal_match_is_meaningful_*` 严格判定）、`sync_protocols_mapping`（25 项）、`verdict`、`disproved_hypotheses`、`what_1017_response_satisfies` |
| `C_1017_response_inventory.json` | 35 个顶层键的 `{key, type, size_bytes_json_exact, size_bytes_wire_estimate, mapped_protocol, element_count, separate_calls}`、`envelope_comparison`、`syncprotocols_vs_response_members`、`the_itemlist_proof`、`emission_recipe` |
| `C_1017_dependency.md` | 本文件 |
| `analyze1017.py` / `build_deliverables.py` | 可复现的分析与生成脚本（只读抓包） |
