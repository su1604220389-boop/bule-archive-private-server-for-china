# 「选择成员」实测追踪（PickupSelectionGacha）— 2026-11-19 01:38–01:52

- 取证时间：2026-11-19 01:48 ｜ 执行：srv-ops（**只读**：未改服务器任何文件、未重启、未部署）
- 数据源：nginx access、Shittim wire log、桥 api 日志、Shittim `log.txt`、`journalctl`

## 一句话结论

**客户端发了，而且发了 39 次**：`POST /api/shop/pickupselectiongachaset`（协议 10015），载荷
`{"ShopRecruitID":90000000,"PickupCharacterSelection":{"1":10014}}`；
**我方每次都回 200，但响应里只回 `Protocol/ServerTimeTicks/ServerNotification`，没有回显 `PickupCharacterSelection`（也没有 `ShopRecruitID`）** ——
**无异常、无 500、无 ErrorCode**。所以不是"服务器无响应"，而是**响应内容缺了客户端用来确认选择的字段**。

---

## 1. nginx：01:38–01:52 请求清单（共 211 条，全部 200）

| path | 次数 | 状态 | 响应字节 |
|---|---|---|---|
| **/api/shop/pickupselectiongachaset** | **39** | **200×39** | **384（恒定）** |
| /api/event/rewardincrease | 23 | 200×23 | 408 |
| /api/notification/eventcontentreddotcheck | 13 | 200×13 | 408 |
| /api/shop/buyap | 13 | 200×13 | 536–4,864 |
| /api/management/data | 12 | 200×12 | 1635–1642 |
| /api/mail/check | 11 | 200×11 | 384 |
| /api/shop/list | 7 | 200×7 | 600–620 |
| /api/mission/list | 6 | 200×6 | 1034–23,660 |
| /api/clan/check、/api/friend/check | 各 6 | 200 | 364 |
| /api/billing/purchaselistbyyostar | 6 | 200 | 536 |
| /api/campaign/list | 4 | 200 | 155,480–155,566 |
| /api/contentsweep/request | 4 | 200 | 19,992–39,470 |
| 其余（auth/loginsync/item/raidlobby/…) | 各 1–3 | 200 | 正常 |

**非 200 = 0 条。**

**「选择成员」那一刻的时间序列（都是 Set）**
```
01:45:16.xxx  pickupselectiongachaset 200 384
01:45:17.xxx  ×3                      200 384
01:47:05–01:47:10  ×19                200 384
01:47:16–01:47:18  ×7                 200 384
（39 次，持续 ~2 分钟 ⇒ 客户端在重试循环，与「正在加载中 → 消失」吻合）
```

## 2. 我方回了什么（wire 明文，逐字节）

**客户端请求（10015）**
```json
{"Protocol":10015,"ShopRecruitID":90000000,
 "PickupCharacterSelection":{"1":10014},
 "Resendable":true,"Hash":43014097469465,"IsTest":false,
 "SessionKey":{"AccountServerId":4,"MxToken":"d1507dc8-…"},"AccountId":10000000003,"OSType":2}
```
**我方响应（`# 01:45:16.235` wire 原文）**
```json
{"protocol":"Shop_PickupSelectionGachaSet",
 "packet":"{\"Protocol\":10015,\"ServerTimeTicks\":639306495160000000,\"ServerNotification\":8}"}
```
⇒ **响应里没有 `PickupCharacterSelection`，也没有 `ShopRecruitID`。**

**对照 Get（10014，仅 00:19 出现过一次）**
```json
响应 = {"protocol":"Shop_PickupSelectionGachaGet","packet":"{\"Protocol\":10014,\"PickupCharacterSelection\":{},\"ServerTimeTicks\":…,\"ServerNotification\":8}"}
```
⇒ Get 是**有** `PickupCharacterSelection` 字段的（空字典），说明字段名本身没错；**Set 少了这个回显**。

## 3. 请求载荷分布（39 次 Set 去重）

| ShopRecruitID | PickupCharacterSelection | 次数 |
|---|---|---|
| **90000000** | **{"1":10014}** | **35** |
| **90000000** | **{"1":20009}** | **4** |
| （解析失败/不完整行） | — | 1 |

- `ShopRecruitID` **恒为 90000000**（就是我方 ShopRecruits 里的哨兵 Id，`SalesEndDate=2099-12-31`）。
- `PickupCharacterSelection` 的 key 是槽位号 `"1"`，value 是角色 Id（10014、20009 两名学生）。

## 4. 异常检查（窗口 01:38–01:52）

```
Shittim log.txt：`[ERR] / Exception / NullReference` → **0 条**
wire 里 `Protocol:"Error"` 事件：22 次，但时间都在 **01:38 前后与 01:40:27–01:40:29**（BuyAP 一批），
   与 01:45/01:47 的选择成员**不同时刻**，且 log.txt 里这些响应没有 ErrorCode 记录
journalctl（01:38–01:52）：14 行，全部是 01:43:06 的一次 start/stop（BANNER1 回滚重启），无异常
```

## 5. 新协议号检查

窗口内出现的协议（wire 统计）：
```
39 Shop_PickupSelectionGachaSet   ← 本次重点（此前只在 00:19 出现过 1 次）
36 Event_RewardIncrease ｜ 21 Notification_EventContentReddotCheck ｜ 19 Account_CheckNexon
16 Mail_Check ｜ 11 Friend_Check ｜ 11 Clan_Check ｜ 9 Billing_PurchaseListByYostar ｜ 8 Shop_List
6 Mission_List ｜ 4 Shop_BuyAP ｜ 4 ContentSweep_Request ｜ 4 Campaign_List ｜ 4 Account_LoginSync
3 Raid_Lobby ｜ 3 OpenCondition_EventList ｜ 3 Equipment_Equip ｜ 3 Account_DismissRepurchasablePopup
2 Shop_GachaRecruitList ｜ 2 Item_List ｜ 2 Account_SetCheckAdultAgree ｜ …
1 Scenario_Skip ｜ 1 Scenario_GroupHistoryUpdate ｜ 1 Echelon_List ｜ 1 Raid_OpponentList …
```
**没有全新协议号**（`Shop_PickupSelectionGachaSet` 之前就存在，只是这次被密集触发）。

## 6. 判断（基于事实）

1. 「选择成员」→ 客户端走的是 **`Shop_PickupSelectionGachaSet`(10015)**，走的路径、协议号、SessionKey 都正确到达 Shittim。
2. 我们回了 **200 + 一个只有 `Protocol/ServerTimeTicks/ServerNotification` 的 384 B 空壳**：
   - **没有回显 `PickupCharacterSelection`**；
   - **没有回显 `ShopRecruitID`**。
   客户端拿不到"已选学生"的确认，于是反复重发（39 次），UI 表现为"正在加载中 → 消失、什么都没选上"。
3. `Get`(10014) 会回 `PickupCharacterSelection`（空字典），说明**字段名是对的**，问题专属于 **Set 的响应缺字段**。
4. 另外：客户端上报的 `ShopRecruitID` 恒为 **90000000**（我方清单里的哨兵档期），
   该 id 在客户端本地表里是否有对应条目也会影响「注意事项/概率信息」是否空白——这属另一条线索，本次不下结论。
5. 全过程**没有任何服务端异常**：不是崩溃、不是超时、不是 500，是**响应内容不完整**。

## 6. 协议流水时间线（01:44:00–01:48:30，Shittim 实际收到的每一条）

> 来源：`logs/wire-2026-11-19.txt`（wire 只记录真正到达 5000 的报文），按时间升序、不合并。
> 请求/响应大小 = 该报文 JSON 明文长度（字节）。

| 时间 | 协议号 | 协议名 | 请求 B | 响应 B | 标记 |
|---|---|---|---|---|---|
| 01:45:16.216 | ?(1014) | Account_CheckNexon | 233 | 1,085 | 桥内部铸会话 |
| **01:45:16.235** | **10015** | **Shop_PickupSelectionGachaSet** | 256 | 139 | ★ **SET** `ShopRecruitID=90000000 sel={"1":20009}` |
| **01:45:17.433** | **10015** | Shop_PickupSelectionGachaSet | 256 | 139 | ★ SET `sel={"1":20009}` |
| **01:45:17.735** | **10015** | Shop_PickupSelectionGachaSet | 256 | 139 | ★ SET `sel={"1":20009}` |
| **01:45:18.103** | **10015** | Shop_PickupSelectionGachaSet | 256 | 139 | ★ SET `sel={"1":20009}` |
| 01:45:37.167 | 29002 | Billing_PurchaseListByYostar | 193 | 253 | |
| 01:45:44.301 | 29002 | Billing_PurchaseListByYostar | 193 | 253 | |
| **01:47:05.100** | **10015** | Set | 256 | 139 | ★ SET `sel={"1":10014}` |
| **01:47:05.316** | **10015** | Set | 256 | 139 | ★ |
| **01:47:05.499** | **10015** | Set | 256 | 139 | ★ |
| **01:47:05.647** | **10015** | Set | 256 | 139 | ★ |
| **01:47:05.810** | **10015** | Set | 256 | 139 | ★ |
| **01:47:05.998** | **10015** | Set | 256 | 139 | ★ |
| **01:47:06.159** | **10015** | Set | 256 | 139 | ★ |
| **01:47:06.327** | **10015** | Set | 256 | 139 | ★ |
| **01:47:06.505** | **10015** | Set | 256 | 139 | ★ |
| **01:47:06.666** | **10015** | Set | 256 | 139 | ★ |
| **01:47:06.873** | **10015** | Set | 256 | 139 | ★ |
| **01:47:07.026** | **10015** | Set | 256 | 139 | ★ |
| **01:47:07.281** | **10015** | Set | 256 | 139 | ★ |
| **01:47:08.030** | **10015** | Set | 256 | 139 | ★ |
| **01:47:08.192** | **10015** | Set | 256 | 139 | ★ |
| **01:47:08.356** | **10015** | Set | 256 | 139 | ★ |
| **01:47:08.506** | **10015** | Set | 256 | 139 | ★ |
| **01:47:08.643** | **10015** | Set | 256 | 139 | ★ |
| **01:47:08.811** | **10015** | Set | 256 | 139 | ★ |
| **01:47:09.002** | **10015** | Set | 256 | 139 | ★ |
| **01:47:09.151** | **10015** | Set | 256 | 139 | ★ |
| **01:47:09.332** | **10015** | Set | 256 | 139 | ★ |
| **01:47:09.499** | **10015** | Set | 256 | 139 | ★ |
| **01:47:09.677** | **10015** | Set | 256 | 139 | ★ |
| **01:47:09.849** | **10015** | Set | 256 | 139 | ★ |
| **01:47:10.021** | **10015** | Set | 256 | 139 | ★ |
| **01:47:10.167** | **10015** | Set | 256 | 139 | ★ |
| **01:47:10.346** | **10015** | Set | 256 | 139 | ★ |
| **01:47:16.162** | **10015** | Set | 256 | 139 | ★ |
| **01:47:16.306** | **10015** | Set | 256 | 139 | ★ |
| **01:47:16.631** | **10015** | Set | 256 | 139 | ★ |
| 01:47:18.176 | ?(1014) | Account_CheckNexon | 233 | 1,085 | 桥再次铸会话 |
| **01:47:18.181** | **10015** | Set | 256 | 139 | ★ |
| **01:47:18.339** | **10015** | Set | 256 | 139 | ★ |
| **01:47:18.503** | **10015** | Set | 256 | 139 | ★ |
| **01:47:18.672** | **10015** | Set | 256 | 139 | ★（最后一条 SET） |
| 01:47:37.177 | 25003 | Event_RewardIncrease | 193 | 161 | |
| 01:47:37.297 | 15002 | OpenCondition_EventList | 280 | 184 | |
| 01:47:37.455 | 36001 | Notification_EventContentReddotCheck | 193 | 162 | |
| 01:47:37.968 | 7001 | Mail_Check | 191 | 142 | |
| 01:47:38.044 | 25003 | Event_RewardIncrease | 193 | 161 | |
| 01:47:38.124 | 28019 | Clan_Check | 193 | 124 | |
| 01:47:38.187 | 43010 | Friend_Check | 193 | 123 | |
| 01:47:38.341 | 29002 | Billing_PurchaseListByYostar | 193 | 253 | |
| 01:47:47.640 | 25003 | Event_RewardIncrease | 193 | 161 | |
| 01:47:47.772 | 36001 | Notification_EventContentReddotCheck | 193 | 162 | |
| 01:47:52.092 | 25003 | Event_RewardIncrease | 193 | 161 | |
| 01:47:52.220 | 36001 | Notification_EventContentReddotCheck | 193 | 162 | |
| 01:47:52.721 | 7001 | Mail_Check | 191 | 142 | |
| 01:47:52.793 | 25003 | Event_RewardIncrease | 193 | 161 | |
| 01:47:52.864 | 28019 | Clan_Check | 193 | 124 | |
| 01:47:52.931 | 43010 | Friend_Check | 193 | 123 | |
| 01:48:08.094 | 19006 | Scenario_LobbyStudentChange | 312 | 138 | |
| 01:48:11.055 | 28000 | Clan_Lobby | 193 | 1,434 | |
| 01:48:12.421 | 90009 | **Error**（Clan_Chat_Records 无 handler） | 193 | 106 | ErrorCode 500（客户端无感） |
| 01:48:12.441 | ?(1014) | Account_CheckNexon | 233 | 1,085 | |
| 01:48:12.445 | 90009 | **Error** | 193 | 106 | 同上 |
| 01:48:19.576 | 25003 | Event_RewardIncrease | 193 | 161 | |
| 01:48:19.697 | 36001 | Notification_EventContentReddotCheck | 193 | 162 | |
| 01:48:20.192 | 7001 | Mail_Check | 191 | 142 | |
| 01:48:20.260 | 25003 | Event_RewardIncrease | 193 | 161 | |
| 01:48:20.328 | 28019 | Clan_Check | 193 | 121 | |
| 01:48:20.398 | 43010 | Friend_Check | 193 | 123 | |

### 6.1 统计

| 协议号 | 协议名 | 次数 |
|---|---|---|
| **10015** | Shop_PickupSelectionGachaSet | **39** |
| 25003 | Event_RewardIncrease | 7 |
| 36001 | Notification_EventContentReddotCheck | 4 |
| 28019 | Clan_Check | 3 |
| 29002 | Billing_PurchaseListByYostar | 3 |
| 43010 | Friend_Check | 3 |
| 7001 | Mail_Check | 3 |
| (1014) | Account_CheckNexon（桥内部铸会话） | 3 |
| 90009 | Error（Clan_Chat_Records 无 handler） | 2 |
| 15002 | OpenCondition_EventList | 1 |
| 19006 | Scenario_LobbyStudentChange | 1 |
| 28000 | Clan_Lobby | 1 |

```
**10014 出现次数 = 0**
10015 出现次数 = 39
distinct 协议号 = 7001, 10015, 15002, 19006, 25003, 28000, 28019, 29002, 36001, 43010, 90009, (1014)
```

### 6.2 10015 的 `ShopRecruitID` / 选择载荷分布

```
ShopRecruitID = 90000000                      ×39   （**只有这一个值**，没有任何一次不同）
PickupCharacterSelection = {"1":10014}        ×35
PickupCharacterSelection = {"1":20009}        ×4
```

### 6.3 判定

1. **窗口内 `10014`（Get）出现 0 次** ⇒ 客户端在 Set 之后**从未回读**，
   说明它并不靠 Get 的值判断成功，而是**看 Set 响应本身的内容**。
2. 我方 39 次 Set 响应全部是 139 B 明文：
   `{"Protocol":10015,"ServerTimeTicks":…,"ServerNotification":8}` ——
   **没有回显 `PickupCharacterSelection`，也没有 `ShopRecruitID`** ⇒ 客户端认为"没选上"，于是无限重试。
3. 期间桥还额外铸了 3 次会话（`Account_CheckNexon` 1014），说明每次重试前重做了 session；
   这解释了为什么连发 19 次也能每次都拿到有效会话。
4. 唯一的服务端错误是 `90009`（`Clan_Chat_Records` 在 DLL 里无 handler）→ ErrorCode 500，
   客户端无感（桥回落空包），**与选择成员无关**。

## 7. 若要修（供决策，本次未做）

最小修法方向：`ShopHandler` 里 `PickupSelectionGachaSet` 的响应补上
```json
{"Protocol":10015,
 "ShopRecruitID":<请求里的值>,
 "PickupCharacterSelection":<请求里的字典>,
 "ServerTimeTicks":…,"ServerNotification":…}
```
并按 (AccountServerId, ShopRecruitID) 持久化，供下一次 `Get`(10014) 返回非空字典。
（参考：Get 现在是内存字典、默认空；Set 存了但没回显，也没验证落库。）
