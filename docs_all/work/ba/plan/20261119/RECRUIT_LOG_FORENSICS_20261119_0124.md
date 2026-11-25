# 招募界面异常 — 日志取证报告（2026-11-19 00:50–01:30）

- 取证时间：2026-11-19 01:25–01:27（Asia/Shanghai）
- 执行：srv-ops（**全程只读**：未重启任何服务、未改动服务器任何文件、未部署）
- 服务器：root@<SERVER_IP>

---

## 1. 时间窗与数据来源

| 数据源 | 路径 | 窗口内情况 |
|---|---|---|
| nginx access（客户端真实请求清单，**最权威**） | `/www/wwwlogs/example.com.log` | **363 条**（00:53:39 – 01:24:25） |
| Shittim 应用日志 | `/www/wwwroot/ba_srv/logs/log.txt` | 505 行，首行 `00:48:19`（本次启动） |
| Shittim wire（唯一记「真正到 5000」的报文） | `/www/wwwroot/ba_srv/logs/wire-2026-11-19.txt` | 11,205,767 B，最后写入 01:24 |
| 桥请求日志 | `/www/wwwroot/bapatch/logs/api_all_requests.log` | 20.4 MB，最后写入 01:24 |
| 桥 stdout | `/www/wwwroot/bapatch/tools/bridge.restart.log` | 最后写入 01:24 |
| journalctl | `journalctl -u ba-shittim --since 00:50 --until 01:30` | **仅 1 行**（服务日志走文件，不走 journal） |
| tmux | `tmux capture-pane -p -t shittim` | 抓到启动段与 `[ClientItemFilter] loaded 1803 …` |

> 注：桥把 `/api/gateway` 转发到 Shittim；被桥直接吸收（stub）的协议不会出现在 wire 里。
> 所以「客户端到底请求了什么」以 nginx 为准，「服务端回了什么」以 bridge 日志 + wire 为准。

---

## 2. 路径聚合表（nginx，00:50–01:30）

| path | 次数 | 状态 | 响应字节 |
|---|---|---|---|
| /checkhealth.html | 33 | 200×33 | 2 |
| / | 33 | 200×33 | 2 |
| /api/health | 33 | 200×33 | 15 |
| /api/event/rewardincrease | 33 | 200×33 | 408 |
| /api/management/data | 19 | 200×19 | 1635–1641 |
| /common/config | 18 | 200×18 | 4871 |
| /api/notification/eventcontentreddotcheck | 17 | 200×17 | 408 |
| /api/mail/check | 15 | 200×15 | 384 |
| /api/clan/check | 15 | 200×15 | 364 |
| /api/friend/check | 15 | 200×15 | 364 |
| /api/mission/list | 12 | 200×12 | 1036–23663 |
| /sdk/heartbeat/pulse | 10 | 200×10 | 51 |
| /api/state | 8 | 200×8 | 720 |
| /api/billing/purchaselistbyyostar | 7 | 200×7 | 536 |
| /api/mail/list | 5 | 200×5 | 364–5534 |
| /api/account/auth | 4 | 200×4 | 2721–2727 |
| /api/academy/getinfo | 4 | 200×4 | 1419–1423 |
| /api/account/loginsync | 4 | 200×4 | 591,181–593,632 |
| **/api/item/list** | 4 | 200×4 | **2465–3870** |
| /api/networktime/sync | 4 | 200×4 | 600 |
| /api/contentsave/get | 4 | 200×4 | 600 |
| /api/account/gettutorial | 4 | 200×4 | 448 |
| …（其余 20 个 path 各 1–4 次，全部 200） | | | |
| **/api/shop/list** | **2** | **200×2** | **208,090 / 728** |

**招募/商店相关（shop、gacha、recruit、banner 关键词）命中 = 2 条，全部是 `/api/shop/list`：**
```
00:54:22  POST /api/shop/list   200   208,090 B   UA=BestHTTP/2 v2.4.0
00:55:34  POST /api/shop/list   200       728 B   UA=BestHTTP/2 v2.4.0
```

**非 200：0 条**（窗口内 nginx 全部 200）。

---

## 3. 时间序列表（节选：登录 + 招募相关；完整 363 条已聚合在 §2）

| 时间 | method | path | status | bytes |
|---|---|---|---|---|
| 00:53:39 | POST | /common/config | 200 | 4,871 |
| 00:53:48 | POST | /sdk/user/quick-login | 200 | 847 |
| 00:54:02 | POST | /sdk/user/login | 200 | 847 |
| **00:54:03** | POST | **/api/account/auth** | 200 | 2,722 |
| **00:54:03** | POST | **/api/account/loginsync** | 200 | **593,605** |
| **00:54:03** | POST | **/api/item/list** | 200 | **2,465** |
| 00:54:04 | POST | /api/mission/list | 200 | 23,216 |
| 00:54:04 | POST | /api/management/data | 200 | 1,635 |
| **00:54:22** | POST | **/api/shop/list** | 200 | **208,090**  ← 商店/招募大包 |
| 00:54:31 | POST | /api/friend/list | 200 | 984 |
| 00:54:38 | POST | /api/mail/list | 200 | 5,534 |
| **00:55:34** | POST | **/api/shop/list** | 200 | **728**  ← 招募页签级小包 |
| 01:00:26 | POST | /api/account/auth | 200 | 2,721 |
| 01:00:27 | POST | /api/account/loginsync | 200 | 591,xxx |
| **00:00–01:24** | — | **无任何 /api/shop/gacharecruitlist 请求** | — | — |
| 01:24:08 | POST | /api/account/auth | 200 | 2,727 |
| 01:24:09 | POST | /api/item/list | 200 | 3,870 |
| 01:24:2x | — | （之后只有周期包：event/mail/clan/friend/management） | — | — |

---

## 4. 招募相关逐条分析（wire 明文为证）

### 4.1 00:54:22 — `/api/shop/list`（208,090 B）
```
# 00:54:22.482 Shop_List aes=False reqKeyLen=0
REQUEST : {"Protocol":10002,"CategoryList":[0,36,37,1,21,2,33,10,25,26,20], …,
           "SessionKey":{"AccountServerId":2,"MxToken":"06389347-…"},"AccountId":10000000000}
RESPONSE: {"protocol":"Shop_List","packet":"{\"Protocol\":10002,\"ShopInfos\":[
             {\"ShopProductList\":[{\"ShopExcelId\":1000,…},{\"ShopExcelId\":1001,…},…]},
             {\"Category\":1,\"ShopProductList\":[{\"ShopExcelId\":20000,…}…]}, …],
             \"ShopEligmaHistoryDBs\":[],\"ServerTimeTicks\":…}"}
```
- 这是**商店**主列表（11 个分类，8 个分类有货，1,900 条商品；与我在 00:48 用网关实测的 205,826 B / 8 分类 / 1,900 商品一致）。
- 响应顶层键：`Protocol` / `ShopInfos` / `ShopEligmaHistoryDBs` / `ServerTimeTicks` / `ServerNotification`
- **没有 `ShopRecruits` 字段**（按协议设计，卡池列表不在 Shop_List 里）。

### 4.2 00:55:34 — `/api/shop/list`（728 B）← **这就是"进招募界面"那一下**
```
# 00:55:34.919 Shop_List aes=False reqKeyLen=0
REQUEST : {"Protocol":10002,"CategoryList":[38], …}
RESPONSE: {"protocol":"Shop_List","packet":"{\"Protocol\":10002,\"ShopInfos\":[
             {\"Category\":38,\"ShopProductList\":[
                {\"ShopExcelId\":201,\"Category\":38,\"DisplayOrder\":1,\"PurchaseCountLimit\":1,\"ProductType\":1},
                {\"ShopExcelId\":202,\"Category\":38,\"DisplayOrder\":1,\"PurchaseCountLimit\":1,\"ProductType\":1}]}],
             \"ShopEligmaHistoryDBs\":[],\"ServerTimeTicks\":…}"}
```
- 请求只带 **Category 38**，响应只有 **2 个商品条目（ShopExcelId 201 / 202）**。
- 顶层键同上，**无 `ShopRecruits`**。
- ⇒ 客户端在招募界面并未请求"卡池清单协议"（见 §5 Q2）。

---

## 5. 五个问题的答案

### Q1. 清数据重下资源后，客户端是否重新走了完整登录？出现哪些协议号/时间/状态？
**是，完整走了两轮**（其余为周期性同步）：

| 轮次 | 时间 | 序列 | 结果 |
|---|---|---|---|
| A | 00:54:03–00:54:05 | auth(1002) → Academy_GetInfo(24000) → **LoginSync(1019, 593,605 B)** → Item_List(4000, 2,465 B) → NetworkTime_Sync(16000) → ContentSave_Get(26000) → Management_Data(90004) → GetTutorial(1005) → Mission_List(8000)×3 → GuideMissionSeason(8006) → MiniGame_MissionList(35003) → Toast_List(16000) → Event_RewardIncrease(25003) → OpenCondition_EventList(15002) → Notification(36001) → Mail_Check(7001) → Clan_Check(28019) → Friend_Check(43010) → Billing_PurchaseListByYostar(29002) | **全部 200** |
| B | 01:00:26–01:00:28 | 同上（LoginSync 783,468 B 经桥 / 591k 经 nginx；Item_List 3,160 B） | **全部 200** |
| C | 01:24:08–01:24:25 | auth → getinfo → LoginSync(591,181) → Item_List(3,870) → … → 周期包 | **全部 200** |

（`Account_CheckNexon(1014)` 在 wire 里出现 9 次，均为桥内部铸会话调用。）

### Q2. **进入招募界面那一刻**客户端发了哪些请求？
```
00:54:22  POST /api/shop/list   200  208,090 B   （CategoryList=[0,36,37,1,21,2,33,10,25,26,20]）
00:55:34  POST /api/shop/list   200      728 B   （CategoryList=[38]）
```
**除此之外没有任何 gacha / recruit 请求。** 整个窗口（乃至整份 nginx 日志）里
**`/api/shop/gacharecruitlist` 只出现过 1 次，是 18/Nov 23:55:36 的 `400 / 35 B`**，
19/Nov 00:50–01:30 期间 **一次都没有**。

### Q3. 有非 200 / `ErrorCode != 0` / `Protocol == -1` 吗？
- **nginx 层：0 条非 200。**
- **Shittim 内部（被桥吞掉、客户端看不到）有 3 类：**
```
① 8× ErrorCode 500 —— 全部来自协议 90009（Clan_Chat_Records），DLL 里没有该 handler：
   00:55:05.380 [ERR] Protocol "90009" doesn't have corresponding type registered
   00:55:05.383 [INF] Error Response: {"Protocol":-1,"ErrorCode":500,"ServerTimeTicks":639306465050000000}
   …重复 4 组（00:55:05 / 00:55:10 / 00:55:15 / 00:55:20，每组 2 次）
   桥侧对应记录：/api/clan/chat/records → relay2_ft=session-retry-failed，回落 536 B 桩
② 2× ErrorCode 3（Session key required）—— Account_Auth(1002)：
   01:00:26.875 [ERR] Error invoking handler for protocol "Account_Auth"
   System.UnauthorizedAccessException: Session key required
      at Shittim_Server.Core.NetworkProtocol.Handlers.AccountHandler.Auth(...)
      at Shittim_Server.Core.ProtocolHandlerRegistry.InvokeHandler(...)
   01:00:26.895 [INF] Error Response: {"Protocol":-1,"ErrorCode":3,…}
   01:24:08.089 同样一条（栈同上）
   ⇒ 但桥对客户端仍返回了 200 的 auth 包（nginx 记录 2,721/2,727 B），客户端无感
③ 无其它异常/堆栈（无 NullReference、无 500 之外的 ERR）
```
- **客户端收到的包里没有 ErrorCode 非 0**（否则 nginx 会出现错误包大小异常或客户端断线）。

### Q4. 有没有"桩/固定小包"？
**有，而且不少**（这些是桥自己生成的，不进 Shittim，大小恒定）：

| path | 响应字节 | 桥日志标记 |
|---|---|---|
| /api/contentsave/get | **600**（恒定） | `relay2_ft=handled-26000` |
| /api/management/data | **2092** | `handled-90004` |
| /api/academy/getinfo | **1772** | `handled-24000` |
| /api/networktime/sync | **600** | — |
| /api/account/gettutorial | **448** | 桥自建 1005 |
| /api/clan/chat/records | **536** | `session-retry-failed`（Shittim 500 后回落桩） |
| /api/event/rewardincrease | **408** | 桥转发（真实回包但内容固定为空数组） |
| /api/mail/check、/api/clan/check、/api/friend/check | **364–384** | 同上（空数据库） |
| 招募相关：**/api/shop/list 的 728 B** | 728 | 真实 Shittim 回包（Category 38 只有 2 商品），**不是桩** |

**⇒ 招募界面拿到的 728 B 是真实数据（2 个商品），不是桩；但它不是"卡池清单"。**

### Q5. 招募相关响应是不是空/字段很少？顶层字段清单
- **招募界面那一下（00:55:34，728 B）**
```
顶层键：Protocol, ShopInfos, ShopElimaHistoryDBs→（正确名为 ShopEligmaHistoryDBs）, ServerTimeTicks, ServerNotification
ShopInfos = 1 个分类（Category 38），ShopProductList = 2 条（ShopExcelId 201、202）
**没有 ShopRecruits / ShopFreeRecruitHistoryDBs**（那是 Shop_GachaRecruitList(10006) 的字段）
```
- **服务端能力对照（我在 00:48 用网关注入会话实测过，非本次改动）**：
  `Shop_GachaRecruitList(10006)` 能正常返回 `ShopRecruits`（当时 529 条，5 条状态下也验证过）。
  **⇒ 服务端能提供卡池清单，但客户端这次根本没有请求 10006。**

### Q6. `ClientItemFilter` 有没有 WARN？
```
tmux 全量抓取里 ClientItemFilter 只出现 1 次：
  [ClientItemFilter] loaded 1803 client item id(s) from /www/wwwroot/ba_srv/Resources/ClientItemIds.txt; item export filter is ON
没有任何 "WARN / filtered / dropped" 行（tmux 里 grep -i warn → 空）
⇒ 过滤启用，本次窗口内没有触发任何丢弃告警
（另有一行无关的 [ExcelTableService] BAPATCH-CLIENTROSTER: dropped 23 character row(s)…，是角色表裁剪，不是道具过滤）
```

---

## 6. 结论（基于日志的事实陈述）

1. **客户端在招募界面只请求了 `Shop_List(10002)`（Category 38），从未请求 `Shop_GachaRecruitList(10006)`**；
   因此它**never 收到 `ShopRecruits`**（卡池清单）——这正是"页签少 / 文案 No LocalizeKey / 按钮恒 1,000"最直接的解释：
   客户端在没有卡池数据时回落到本地默认值。
2. 服务端**有能力**返回卡池清单（10006 实测可返回 529 条），问题在**客户端没有发起该请求**，
   或它把招募页签挂在 `Shop_List(Category=38)` 上而该分类只有 2 个商品（ShopExcelId 201/202）。
3. 窗口内**没有任何非 200**；Shittim 内部有三类被桥兜住的错误：
   `90009`(Clan_Chat_Records) 无 handler ×8 → 500；`Account_Auth` 缺 session ×2 → 3。
   这些都被桥转成 200 交给客户端，**与招募界面无关**。
4. 道具出口过滤已启用（1803 id），**没有 WARN**，也没有丢弃记录。
5. 招募相关唯一的小包（728 B）是**真实数据**，不是桩；但它只是 2 条商品，不含卡池列表。

## 7. 待验证的下一步（不在本次只读范围，供决策）

- 需要抓一次「客户端主动打开招募页签后是否发 10006」的请求：目前证据是**不发**。
  若要强制它发，可能要在 `Shop_List(Category=38)` 的响应里提供客户端期望的招募入口数据，
  或确认客户端 3.0.2 的招募页到底依赖 `Shop_GachaRecruitList` 还是 `Shop_List(category=38)`。
- 已知唯一一次 10006 请求是 18/Nov 23:55:36 的 `400 B/35`（当时桥正在重启，属异常时刻），
  以及 19/Nov 00:19 那轮（当时 clean5 生效、bridge 转发 4000 正常），**映射关系未被推翻**。

## 8. 原始日志摘录（关键行）

```
# wire：进招募界面
# 00:55:34.919 Shop_List aes=False reqKeyLen=0
REQUEST : {"Protocol":10002,"CategoryList":[38],…}
RESPONSE: {"protocol":"Shop_List","packet":"{\"Protocol\":10002,\"ShopInfos\":[{\"Category\":38,
           \"ShopProductList\":[{\"ShopExcelId\":201,…},{\"ShopExcelId\":202,…}]}],
           \"ShopEligmaHistoryDBs\":[],\"ServerTimeTicks\":…}"}

# 商店主列表
# 00:54:22.482 Shop_List
REQUEST : {"Protocol":10002,"CategoryList":[0,36,37,1,21,2,33,10,25,26,20],…}
RESPONSE: …205,826 B 级大包，8 分类 / 1,900 商品…

# 90009 缺失
2026-11-19 00:55:05.380 [ERR] Protocol "90009" doesn't have corresponding type registered
2026-11-19 00:55:05.383 [INF] Error Response: {"Protocol":-1,"ErrorCode":500,…}

# Account_Auth 缺 session（桥内部）
2026-11-19 01:24:08.089 [ERR] Error invoking handler for protocol "Account_Auth"
System.UnauthorizedAccessException: Session key required
   at Shittim_Server.Core.NetworkProtocol.Handlers.AccountHandler.Auth(...)

# 出口过滤
[ClientItemFilter] loaded 1803 client item id(s) from …/ClientItemIds.txt; item export filter is ON

# nginx 唯一一次卡池清单请求（历史）
127.0.0.1 - - [18/Nov/2026:23:55:36 +0800] "POST /api/shop/gacharecruitlist HTTP/2.0" 400 35 "-" "BestHTTP/2 v2.4.0"
```

**取证结束：未重启、未改动、未部署任何东西。**
