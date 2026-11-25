# 招募按钮死锁 —— 2026-11-18 22:55 阶段结论

所有结论来源：线上 wire 日志 `/www/wwwroot/ba_srv/logs/wire-2026-11-18.txt`（39,619,007 B）、
客户端表 `work\ba\data\ExcelDB.db`（160,534,528 B，sha256 `c49096aa…`）、
官方 CN 抓包 `report\_tmp\official_decoded_201\`、服务端源码 `work\ba\srv_src\`。

---

## 1. 客户端从不发 Shop 请求（已证实）

22:43 那次完整登录的协议序列（`wire-2026-11-18.txt` 15814–15940 行）：

```
Account_CheckNexon → Account_Auth → Account_LoginSync → Account_GetTutorial
→ Mission_List ×4 → Mission_GuideMissionSeasonList → MiniGame_MissionList
→ Toast_List → Event_RewardIncrease ×2 → OpenCondition_EventList
→ Notification_EventContentReddotCheck → Mail_Check → Clan_Check
→ Friend_Check → Billing_PurchaseListByYostar ×2
```

**没有 `Shop_GachaRecruitList`、没有 `Shop_List`、没有 `Shop_BuyGacha*`。**
今日全量协议直方图（2277 个 header）里 Shop 相关协议数 = 0。

⇒ 卡池列表不是靠单独请求拿的，是 LoginSync 里 `SyncProtocols` 带上 `22001` 一起回的。

## 2. 服务端确实回了卡池列表（已证实）

22:43 的 `Account_LoginSync`（583,124 B 块）响应里：

```
ShopGachaRecruitListResponse = { Protocol, ShopRecruits, ShopFreeRecruitHistoryDBs }
ShopRecruits      = 529 条
第一条            = {"Id":5000000,"SalesStartDate":"2023-08-03T05:00:00","SalesEndDate":"2023-08-10T15:59:59","UpdateDate":"0001-01-01T00:00:00"}
最后一条          = {"Id":99999999,"SalesStartDate":"2024-08-01T14:00:00","SalesEndDate":"2099-12-31T03:59:59","UpdateDate":"0001-01-01T00:00:00"}
ShopFreeRecruitHistoryDBs = []
ItemListResponse  = { Protocol, ItemDBs(21 条), ExpiryItemDBs([]) }
ServerTimeTicks   = 639306386040000000
```

⇒ 卡池列表这一环**是对的**，不是它的问题。

## 3. 客户端闸门在哪（反汇编，已证实但**不完整**）

```
点「招募10次」
 → UIGacha.IsCanBuyGacha            @0x09FB86CC
    → IsShopRecruitOpen(targetExcel, Id, CurrentTime)  @0x0EACBD14
        → TryGetValue(Id, out excel)   未命中 → 分支A @0xEACBDE8
        → excel == null              → 分支C @0xEACBEC4
        → [excel+0x1C] == 0          → 分支B @0xEACBE04
    → false 就 tbz 跳过整个购买分支（0x09FB8994）
```

**分支 A / B / C 具体做什么还没解出来** —— `il2cpp-analyst` 正在做，产出去 `ISSHOPRECRUTOPEN_FULL.md`。

## 4. ★ 已确认的服务端部署错误：发错了券的道具 id

客户端 `ItemDBSchema` 里有 `GachaTicketType` 字段（字段偏移 66）：

| 道具 id | GachaTicketType | IconPath | 含义 |
|---|---|---|---|
| `6400` / `6401` / `6998` | **5** | `RecruitTicket_Normal_1` | 普通单抽券 |
| `6500` / `6800` / `6999` / `6000` | **4** / 4 / 4 / 1 | `RecruitTicket_Normal_10` | 普通十连券 |
| `11000000` | **无该字段（=0）** | `RecruitTicket_Newbie_10` | 新手专用 |
| `11000001` | **无该字段（=0）** | `RecruitTicket_Newbie_11` / `StartDash_1` | 新手冲刺专用 |

我们之前发的是 `11000000` / `11000001` ⇒ **普通卡池完全不能用它们付费**。

### 卡池消耗定义（客户端表，已证实）

```
goods 5004671（单抽）：ConsumeParcelType[2] ConsumeParcelId[4] ConsumeParcelAmount[120]
                      ConsumeGachaTicketType[5] ConsumeGachaTicketTypeAmount[1]
goods 5004672（十连）：ConsumeParcelAmount[1200]，CombinedGachaCostId = 101
goods 100101（新手十连）：ParcelType[4] ParcelId[11000001] Amount[1]
```

`GachaCombinedCostDBSchema` GroupId=101（12 档，`券张数 / 宝石数`）：

| 档 | 券张数 | 宝石 |
|---|---|---|
| 1 | 1 | — |
| 2 | **10** | 0 |
| 3 | 9 | 120 |
| 4 | 8 | 240 |
| 5 | 7 | 360 |
| 6 | 6 | 480 |
| 7 | 5 | 600 |
| 8 | 4 | 720 |
| 9 | 3 | 840 |
| 10 | 2 | 960 |
| 11 | 1 | 1080 |
| 12 | 0 | **1200** |

⇒ **单抽 = 1 张 `GachaTicketType 5` 券**（即 `6400`/`6401`/`6998`），与用户说的「抽一次只要一张」一致。

## 5. 已排除的原因（都验证过，别再回头查）

| 假设 | 结论 | 证据 |
|---|---|---|
| 客户端表过期 | **排除** | `5004670` 行 = `2026-11-12 14:00 ~ 2026-11-26 13:59:59`，现在在区间内 |
| 服务端没发卡池 | **排除** | 529 条 `ShopRecruits` 在 LoginSync 里 |
| 卡池 id 客户端没有 | **排除** | 客户端表 532 行 ⊇ 官方 529 |
| 货币字段名/枚举不对 | **排除** | 官方抓包数字键 `"19"=40,"22"=6,"24"=1` 与 `CurrencyTypes` 枚举（WorldRaidTicketA=19…EliminateTicketD=27）及我们的值完全吻合 |
| `GemPaid=0` 导致付不起 | **排除（待复核）** | 官方抓包同样是 `GemPaid("2")=0` |
| SQLCipher 密钥轮换 | **排除（客户端不来取）** | wire 日志里 `Queuing` 请求数 = 0 |
| 客户端从我们这下表失败 | **排除** | `ba_static.log` 自 11-14 后无客户端访问 |
| 客户端时钟未同步 | **排除** | `NetworkTime_Sync` 请求数 = 0，客户端用本机时间 |
| `Account_Auth` 缺 9 个官方字段 | **已修但在线未验证** | 见 `GACHA_ARENA_DEPLOY_20261118.md` |

## 6. 本轮改动（可回滚）

**DB**：`/root/shittim.sqlite3`
- 备份：`/root/RTICKET2_20261118_225423/shittim.sqlite3`
- 回滚：`bash /root/RTICKET2_20261118_225423/ROLLBACK.sh`
- 内容：对账号 `2` 和 `4` 各插入 `6400 ×100`、`6998 ×100`（都是 `GachaTicketType 5` 的普通单抽券）；
  原有的 `11000000 ×10`、`11000001 ×10` **保留未删**。
- 无需重启（Items 每次请求从 DB 读）。

## 6b. `[excel+0x1C]` = `IsLegacy`（2026-11-18 23:00，已钉死）

`logcat-architect` 从明文 v31 `global-metadata.dat`（`work/ba/noroot/_extract/gm-global-metadata.dat`，
33,351,780 B，`86DB0A21…`）解出 `MX.Data.ShopRecruitExcelData` = typeDef #15782，`fieldStart=69228`，
下一类型 `ShopRefreshExcelData` = 69240 ⇒ **12 个字段**，`parentTypeIndex → System.Object`（无基类字段）。

| 字段 | 类型 | 偏移 |
|---|---|---|
| Id | long | 0x10 |
| CategoryType | enum(int) | 0x18 |
| **IsLegacy** | **bool** | **0x1C** ★ |
| OneGachaGoodsId | long | 0x20 |
| TenGachaGoodsId | long | 0x28 |
| SalePeriodFrom | 16B 时间结构 | 0x30 |
| SalePeriodTo | 16B 时间结构 | 0x40 |
| IsNewbie | bool | 0x50 |
| IsOverrideSalePeriod | bool | 0x51 |
| DirectPayInvisibleTokenId | long | 0x58 |
| SelectAbleGachaGroupId | long | 0x60 |
| SalePeriodDayParameter | long | 0x68 |

交叉验证：反汇编 `ldp x8,x9,[x10,#0x30]` / `ldr q0,[x10,#0x40]` 与上表 0x30/0x40 完全吻合。
flatbuffer：532 行里 `IsLegacy` 槽出现次数 = **0** ⇒ 全为 false。

**⇒ `row+0x1C != 0 → return false` 这条闸门对所有已上线卡池都放行。卡点不在这里。**

## 6c. 闸门只剩这几道（按反汇编顺序）

| # | 判定 | 位置 |
|---|---|---|
| 1 | `IsShopRecruitOpen` → **已放行** | `0x09FB8990` |
| 2 | `freeRecruitId != 0` → `CalcFreeRecruitRemainCount(...) > 0` | `0x09FB89A4` 起 |
| 3 | `FindGoods(targetGoodsId)`，`ByteBuffer == null` → false | — |
| 4 | `ConsumeGachaTicketType × CategoryType` → `bl 0x77C2508` | — |
| 5 | `get_IsCharacterSetSelected`，未选成员 → 跳 `0x09FB8DC8` | — |

用户截图（2026-11-18 22:57）显示：右下角「选择成员」为**可点状态** ⇒ #5 嫌疑最大。
同时十连按钮上显示「券图标 × **1,000**」，而表里该卡池的十连价是 **1200 宝石或 10 张券**，
`GachaCombinedCost 101` 的 12 档里没有任何一档是 1000，全表 9422 个 Goods 里消耗 1000 的
全是 `ParcelType 4 / ItemId 800xx`（与招募无关）⇒ **这个 1,000 来源不明，已派 agent 解按钮数字来源。**

## 6d. ★★ 真因（服务端）：`PickupSelectionGacha` 把玩家的选择直接丢弃

`work\ba\srv_src\Shittim-Server\Core\NetworkProtocol\Handlers\ShopHandler.cs` 原文（改前）：

```csharp
[ProtocolHandler(Protocol.Shop_PickupSelectionGachaGet)]
...
    // Pickup selections are not persisted; the client accepts an empty map.
    response.PickupCharacterSelection = new Dictionary<long, long>();   // ← 恒返回空

[ProtocolHandler(Protocol.Shop_PickupSelectionGachaSet)]
...
    // Just acknowledge                                                  // ← 什么都没存
    return response;
```

反汇编已证实客户端侧（`il2cpp-analyst`，`ISSHOPRECRUTOPEN_FULL.md` §8）：

```
0x09FB8BE4  bl   get_IsCharacterSetSelected
0x09FB8BE8  tbz  w0,#0,#0x09FB8DC8     ; false → 该分支
0x09FB8E18  bl   ShowToast(...)         ; 弹提示（本地化 key 缺失时显示 No LocalizeKey）
0x09FB8E1C  b    → mov w0,wzr           ; return false
```

**闭环**：玩家在「选择成员」里选人 → 客户端发 `Shop_PickupSelectionGachaSet` → 服务端丢弃 →
下次 `Get` 返回空 map → 客户端 `IsCharacterSetSelected == false` → `IsCanBuyGacha` 走
`ShowToast(No LocalizeKey)` + `return false` → **按钮永远点不动、且一条请求都不发**。

这同时解释了用户截图里的 `No LocalizeKey`：它不是乱码，是「不能买」的提示文案没解析出来。

### 修复（BAPATCH-PICKSEL v1，已上线 2026-11-18 23:01）

`ShopHandler.cs` 改成按 `(AccountServerId, ShopRecruitId)` 记住客户端提交的 `PickupCharacterSelection`
并原样回显；进程内 `ConcurrentDictionary` 存储（重启丢，客户端再选一次即可），**不引入 EF 模型/迁移风险**。

- 新 DLL：`2a98a2b36280784e9ff0323fa4ab54c5adaab949e4b1c23e729f80d675ea7e8d`，2,680,320 B
- 旧 DLL：`9006da8c8eecddd08118f8b8ef65ad79cdeea46e1e0fc323dde1a8d6b5ce4926`，2,679,808 B
- `Schale.dll` 未变（`b06f46090f9d8eb8657e51401b789178d9090ad5a5a6d6d1faaa791dad429858`）
- 备份 / 回滚：`bash /root/PICKSEL_20261118_230108/ROLLBACK.sh`
- 构建目录：`work\ba\srv_src\_build_picksel\`

## 7. 待验证 / 未决

1. 重登后看 `ItemListResponse.ItemDBs` 里有没有 `6400`/`6998` 且 `StackCount=100`。
2. 重登后按一次「招募10次」，看：
   - 按钮上的券数量变不变
   - nginx / wire 里出不出 `Shop_BuyGacha*`
3. `[excel+0x1C]` 到底是哪个字段 —— `logcat-architect`（`SHOPRECRUITEXCEL_LAYOUT.md`）+ `il2cpp-analyst`（`ISSHOPRECRUTOPEN_FULL.md`）。
4. 若补了正确券仍无效 ⇒ 闸门在分支 B 的时间判断，需要改**客户端表**或让服务端下发客户端表里 `[excel+0x1C]` 为真的 id。
