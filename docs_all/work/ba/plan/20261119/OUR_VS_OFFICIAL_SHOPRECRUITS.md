# 我方 vs 官方：LoginSync(1017) 内嵌 `ShopGachaRecruitListResponse.ShopRecruits` 结构对比

- 时间：2026-11-19 01:30（Asia/Shanghai）
- 执行：srv-ops（**只读**：未重启、未部署、未改服务器任何文件）
- 我方数据来源：`/www/wwwroot/ba_srv/logs/wire-2026-11-19.txt` 里最近一条 `Account_LoginSync` 响应（wire 存的是明文 JSON）
- 官方数据来源：`report\_tmp\official_decoded_201\02_1017_api_account_loginsync.response.json`
  （`meta` = `{"id":84,"bj":"04:30:55.110","status":200,"resp_bytes":246808,"protocol":1017}`）
- 落盘数据文件：
  - 我方：`work\ba\data\_tmp\our_shoprecruits_20261119.json`（88,960 B，sha256 `6773411d15d82eff597017dceba9d1638b5fd2ba7357cfa4b7caae566700c5ca`）
  - 官方：`work\ba\data\_tmp\official_shoprecruits_20261119.json`（比对用副产物）

## 一句话结论

**数据本身完全一致**（529 条、字段集合、日期格式、Id 集合、逐条逐字段差异 = **0**）；
**唯一的差异在「子包外层容器」**：官方内嵌子包保留了 5 个零值/空壳字段
（`Protocol=0`、`SessionKey={0,""}`、`ServerTimeTicks=0`、`ServerNotification=0`、`RequestId=""`），
我方**只发了 3 个键**（`Protocol=10006` + `ShopRecruits` + `ShopFreeRecruitHistoryDBs`），没有那 5 个空壳字段，且 `Protocol` 值也不同。

---

## 1. 位置（我方在 LoginSync 哪个字段下）

| | 官方 | 我方 |
|---|---|---|
| LoginSync 响应顶层键数 | 32 | 32 |
| 子包字段名 | `ShopGachaRecruitListResponse` | **`ShopGachaRecruitListResponse`（同名）** |
| 所在层级 | `inner.ShopGachaRecruitListResponse` | `inner.ShopGachaRecruitListResponse` |
| `inner.Protocol` | 1017（int） | 1017（int） |

我方 LoginSync 顶层键（32 个）：
```
Protocol, CafeGetInfoResponse, AccountCurrencySyncResponse, CharacterListResponse,
EquipmentItemListResponse, CharacterGearListResponse, ItemListResponse, EchelonListResponse,
MemoryLobbyListResponse, CampaignListResponse, ArenaLoginResponse, RaidLoginResponse,
EliminateRaidLoginResponse, CraftInfoListResponse, ClanLoginResponse, MomoTalkOutLineResponse,
ScenarioListResponse, **ShopGachaRecruitListResponse**, TimeAttackDungeonLoginResponse,
EventContentPermanentListResponse, AttachmentGetResponse, BillingPurchaseListByYostarResponse,
AttachmentEmblemListResponse, ContentSweepMultiSweepPresetListResponse, StickerListResponse,
MultiFloorRaidSyncResponse, MultiFloorRaidLoginResponse, FriendCode, PickupFirstGetHistoryDBs,
AccountLevelRewardIds, ServerTimeTicks, ServerNotification
```

## 2. 逐项对比

| # | 维度 | 官方 | 我方 | 一致 |
|---|---|---|---|---|
| ① | `ShopRecruits` 条数 | **529** | **529** | ✅ |
| ② | 元素字段集合 | `Id, SalesStartDate, SalesEndDate, UpdateDate` | **同 4 个，无增无减无改名** | ✅ |
| ③ | 日期格式 | `2023-08-03T05:00:00`（无时区 ISO，毫秒位省略） | **逐字相同** | ✅ |
| ④ | Id 区间 / 分段 | `5000000..99999999`；5M=**472**，6M=**32**，其它 25；哨兵 `90000000`、`99999999` | **完全相同**（5M=472 / 6M=32 / 其它 25；哨兵同样两个） | ✅ |
| ⑤ | 子包顶层键 | 7 个：`Protocol, SessionKey, ServerTimeTicks, ServerNotification, RequestId, ShopRecruits, ShopFreeRecruitHistoryDBs` | 3 个：`Protocol, ShopRecruits, ShopFreeRecruitHistoryDBs` | ❌ **缺 4 个空壳字段** |
| ⑥ | 子包 `Protocol` | **0**（int，官方原值就是 0） | **10006**（int） | ❌ 值不同 |
| ⑦ | `ShopFreeRecruitHistoryDBs` | `[]` | `[]` | ✅ |
| ⑧ | 逐条 × 逐字段值差异 | — | — | ✅ **差异数 = 0** |

### ② 字段集合（两侧完全相同）
```
官方: ['Id', 'SalesEndDate', 'SalesStartDate', 'UpdateDate']
我方: ['Id', 'SalesEndDate', 'SalesStartDate', 'UpdateDate']
```

### ③ 日期字符串（逐字样例，各 2 条）
```
官方 #1 = {"Id":5000000,"SalesStartDate":"2023-08-03T05:00:00","SalesEndDate":"2023-08-10T15:59:59","UpdateDate":"0001-01-01T00:00:00"}
我方 #1 = {"Id":5000000,"SalesStartDate":"2023-08-03T05:00:00","SalesEndDate":"2023-08-10T15:59:59","UpdateDate":"0001-01-01T00:00:00"}

官方 #2 = {"Id":5000010,"SalesStartDate":"2023-08-03T05:00:00","SalesEndDate":"2023-08-10T15:59:59","UpdateDate":"0001-01-01T00:00:00"}
我方 #2 = {"Id":5000010,"SalesStartDate":"2023-08-03T05:00:00","SalesEndDate":"2023-08-10T15:59:59","UpdateDate":"0001-01-01T00:00:00"}
```
（`UpdateDate` 一律 `0001-01-01T00:00:00`，两侧相同。）

### ⑤ 子包顶层键（差异点 1）
```
官方（7 键）：
  Protocol             = 0                     （int）
  SessionKey           = {"AccountServerId":0,"MxToken":""}
  ServerTimeTicks      = 0                     （int）
  ServerNotification   = 0                     （int）
  RequestId            = ""                    （str）
  ShopRecruits         = list(529)
  ShopFreeRecruitHistoryDBs = []

我方（3 键）：
  Protocol             = 10006                 （int）
  ShopRecruits         = list(529)
  ShopFreeRecruitHistoryDBs = []
```
⇒ **官方那 5 个容器字段全是零值/空串**（可以理解为"子包壳子"），我方**没有输出这几个键**。

### ⑥ `Protocol` 值（差异点 2）
```
官方 = 0      （原始抓包里就是 0，不是解码失败；同层 inner.Protocol=1017 是正常的）
我方 = 10006
```

## 3. 数据一致性证明（逐条 × 逐字段 diff）

```
按 Id 建索引对比 529 × 3 个日期字段：
  差异数 = 0
  Id 集合相同 = True
  缺失 = 0 条 ｜ 多余 = 0 条
```
即：**除容器外壳外，我方下发的卡池清单与官方抓包逐字节级一致**（同 Id、同起止时间、同更新时间为零值）。

## 4. 事实补充（本窗口无关但需记录）

- 客户端在 00:50–01:30 期间**从未单独请求 10006**（`/api/shop/gacharecruitlist` 零次），
  但 LoginSync 响应里**已经带了这 529 条**（就在 `ShopGachaRecruitListResponse` 下）——
  这与官方的索取方式一致（客户端在 1017 的 `SyncProtocols` 里列 10006，用登录同步批量拿）。
- 因此"客户端没收到卡池数据"这一假设**不成立**：数据已经在那 591–593 KB 的 LoginSync 包里。
  剩下的问题只可能在：客户端解析时是否接受我方这种"缺 5 个空壳字段 + Protocol=10006"的子包形状，
  以及它拿 Id 去查本地 Excel（banner 路径 / 本地化 key）时是否命中。

## 5. 结论与建议（供决策，本次不改）

1. **数据无差**：529 条、字段、日期、Id 全对。
2. **形状有差**：我方子包只有 3 键、`Protocol=10006`；官方是 7 键（4 个零值壳）+ `Protocol=0`。
   若客户端反序列化依赖这些键存在（很多 Unity 自动生成的 Json 反序列化对缺失键会用默认值，通常不致命；
   但若它按 `Protocol` 做子协议分发，`0` 与 `10006` 的差别就可能决定它是否把这段当作 `ShopGachaRecruitListResponse`），
   这是目前**唯一可解释"数据在包里但 UI 不显示"的服务端侧差异**。
3. 若要验证，最小实验是：**在子包里补齐 `SessionKey{0,""} / ServerTimeTicks / ServerNotification / RequestId` 四个零值字段，
   并把 `Protocol` 改成 0**，再比一次真机——但这属于改代码，需你另行下令。
4. 另需注意：`client Excel` 侧是否含这 529 个 Id 的 `GachaRecruitBannerExcel` / 本地化 key，
   是纯客户端数据问题，服务端日志无法证明；若客户端本地没有这些 Id，`No LocalizeKey` / 空图仍会出现——数据再对也没用。
