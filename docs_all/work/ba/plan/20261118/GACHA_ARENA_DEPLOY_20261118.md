# 招募 / 战术对抗赛 —— 2026-11-18 22:15 部署记录

## 一、招募（抽卡）不能用的根因

### 已证实
1. 服务端 `ShopHandler.GachaRecruitList`（`ShopHandler.cs:42`，协议 10006）**只填了 `ShopFreeRecruitHistoryDBs`，从来没填 `ShopRecruits`**。
   `ShopGachaRecruitListResponse` 的 DTO 有两个字段（`Schale\MX\NetworkProtocol\NetworkProtocol.cs:6676`）：
   ```csharp
   public List<ShopRecruitDB>? ShopRecruits { get; set; }
   public List<ShopFreeRecruitHistoryDB>? ShopFreeRecruitHistoryDBs { get; set; }
   ```
   线上实际下发（2026-11-18 22:01:44 `Account_LoginSync`）：
   `"ShopGachaRecruitListResponse":{"Protocol":10006,"ShopFreeRecruitHistoryDBs":[]}` —— **`ShopRecruits` 整段缺失**。
2. `Account_LoginSync` 里的这份也是硬编码的（`AccountHandler.cs:508-511`，原先只有 `ShopFreeRecruitHistoryDBs = []`）。
3. 三天明文 wire 日志（11-14 / 11-17 / 11-18）里，客户端**一次都没发过** `Shop_BuyGacha`(10001) / `Shop_BuyGacha2`(10005) / `Shop_BuyGacha3`(10008)。
   只有 11-17 有 2 次 `Shop_PickupSelectionGachaSet`(10015)，说明招募界面确实打开过、有交互，但点「招募」不发请求。
4. 协议号无问题：客户端与服务端的 `10006 / 10001 / 10005 / 10008 / 10014-10016` 全对得上。
5. 官方解密样本 `report\_tmp\official_decoded_201\02_1017_api_account_loginsync.response.json` 里 `ShopRecruits` 有 **529 条**，
   Id 5000000~99999999，`UpdateDate` 恒为 `0001-01-01`，**包含已过期档期**（如 2023-08-03 05:00:00 ~ 2023-08-10 15:59:59）。

### 修复
在 `ShopHandler` 里加 `BuildRecruitBanners(ExcelTableService)`：取 `ShopRecruitExcelT` 全表、按 Id 升序、
`SalePeriodFrom/SalePeriodTo` 非空且能解析的行，映射成 `ShopRecruitDB { Id, SalesStartDate, SalesEndDate, UpdateDate = DateTime.MinValue }`。
两个下发点都接上：`GachaRecruitList` 与 `Account_LoginSync`。
**任何解析失败都退化成空列表**（`try/catch` + `DateTime.TryParse`）—— 绝不能让 LoginSync 抛异常把人挡在门外。

> 注意：线上 `Resources/Excel/*.bytes` 里的 `ShopRecruitExcel` 是 **717 行、Id 为 9 位（90050002~900900000）**的版本，
> 与官方样本的 5,000,000 段不是同一批号；其中当前在档期的有 3 条：
> `90070001`（新手，2024-07-23 ~ 2099-12-31）、`90080004`（自选，2025-12-16 ~ 2026-11-24）、`900900000`（2025-09-23 ~ 2099-12-31）。
> 客户端截图里的三个页签「新手冲刺II / 3★自选招募 / DUMMY」正好对应 `IsNewbie` / `IsSelectRecruit` / 占位，
> 说明客户端与本服 Excel 同源，因此下发本服 Excel 的 Id 是自洽的。**这一条仍待真机验证。**

## 一之补充：22:24 第二批（v2，卡池号两套合并）

22:19:59 的 `Account_LoginSync` 已确认 `ShopRecruits` **下发成功、714 条**（Id 90050002~900900000），
但用户反馈「招募界面没有变化」⇒ 大概率是**卡池号对不上**：客户端那几个页签来自它自己那份 Excel，
而本服 `Resources/Excel/shoprecruitexceltable.bytes` 是另一批号（717 行、8~9 位 Id）。
官方 CN 解密样本里的卡池号是 **529 条、7 位为主（5,000,000~9,999,999）+ 6 条 8 位（90000000 / 99999999）**，
与本服 Excel 的号段（90050002 起）**基本不相交**。

因此 v2 改成**两套合并下发**：
- 本服 Excel 的 714 条（`ShopRecruitExcelT`，Id ≥ 5000000 且档期可解析）
- 官方 CN 的 529 条（`report\_tmp\official_decoded_201\02_1017_api_account_loginsync.response.json` 导出成
  `Shittim-Server\Data\GachaRecruitBanners.cn.json`，40,739 B）
- 按 Id 去重后升序，客户端按 Id 匹配，不认识的自然被忽略

排除的假设：
- `ShopFreeRecruitHistoryDBs` —— 官方样本同样是 `[]`，不是原因。
- `Shop_PickupSelectionGacha*` —— 11-17 只出现过 `Set`，不是原因。
- 协议号 —— 10006/10001/10005/10008/10014-10016 客户端与服务端完全一致。

- 线上 DLL sha256：`f2d346c7f9f2226d437b1bdb91c5719cd8a6e12938e0db9b5678ee84249afc7d`（2,679,808 B）
- 数据文件 sha256：`3ac8385d77a2921932eedf934de83178f61a6c8c30b588c3ca64718f0c423c77`（40,739 B）
  → `/www/wwwroot/ba_srv/Data/GachaRecruitBanners.cn.json`
- 备份目录：`/root/GACHALIST2_20261118_222416`（注意：只备份了 DLL；JSON 是新增文件，回滚时删掉即可）

## 一之补充二：22:28 第三批（登录同步补 `ItemListResponse`）

22:25:59 的登录同步已下发 **1243 条**（5000000~900900000，两套号段合并），用户反馈「还是一样」。
并且从 nginx 访问日志确认：**按招募时客户端一个请求都没发出去**（`/api/shop/*`、`/api/gateway` 都没有新请求），
所以是客户端本地拦住的，不是网络/服务端拦的。

与官方 `Account_LoginSync` 逐键对比（官方 35 键 vs 我们 31 键），我们**缺**：
`ItemListResponse`、`FriendCount`、`RequestId`、`SessionKey`。
其中 `ItemListResponse` 是玩家道具列表（`AccountLoginSyncResponse:332`，全工程无人赋值），
缺它客户端本地道具状态为空 —— 招募/商店这种「按道具判断能不能买」的界面会停在不可用。第三批补上它。

- 线上 DLL sha256：`a14aa68fd73213c4c754edbb861c8664bc2442f5b1c51c657ed359d15d98d7e1`（2,679,808 B）
- 备份目录：`/root/LOGINITEM_20261118_222818`，回滚 `bash /root/LOGINITEM_20261118_222818/ROLLBACK.sh`

排除：`ShopFreeRecruitHistoryDBs`（官方也是 `[]`）、`Shop_List`（两边都只有 Category 38）、`StaticOpenConditions`（官方响应里根本没有）。

**待用户提供**：按「招募10次」时界面到底有没有反应（变灰/转圈/弹字/完全不动），以及「选择成员」按钮有没有反应。
这两条决定下一步是查「按钮可用性判定」还是「选择成员子流程」。

## 二、战术对抗赛（竞技场）发不出 `Arena_EnterBattle`

### 已证实
1. `ArenaEnterLobbyResponse.AutoRefreshTime` / `ArenaOpponentListResponse.AutoRefreshTime` 字段存在
   （`NetworkProtocol.cs:474`、`:509`），但服务端**从来没赋值** ⇒ 恒为 `0001-01-01T00:00:00`（且因为是默认值，连字段都不出现在 JSON 里）。
2. 官方样本 `69_22000_api_arena_enterlobby.response.json` 里 `"AutoRefreshTime":"2026-11-16T04:33:12.320169288"` ≈ 请求时刻。
3. 三天日志里客户端从没发过 `Arena_EnterBattle`(22004)，只有 `22000/22003/22016/22009`。
4. 客户端侧 `UIArena` 有 `ShowNeedToRefreshPopup`、`FindOpponentIndex` 等方法（il2cpp 取证），
   但 39 个方法里 34 个是 ACE 密文，**无法静态证实**「AutoRefreshTime 过期就会弹刷新而不是开战」。

### 修复
`ArenaHandler.EnterLobby` 与 `ArenaHandler.OpponentList` 都补上
`response.AutoRefreshTime = account.GameSettings.ServerDateTime();`

## 三、部署

- 构建：`work\ba\srv_src\_build_gacha1`（`dotnet publish -c Release`，仅 2 个 warning 级别的既有告警，无 error）
- 线上 DLL sha256：`4dbaf922026afa9d716646d16075b12721df7a20c7672011b5c400469b727549`（2,677,760 B）
- 旧 DLL sha256：`f54739aa94f0f3f734fdb37d1e4807be1d9fb1029fae029b617914655ce2e2bf`（2,676,736 B）
- 备份目录：`/root/GACHALIST_20261118_221526`
- **一行回滚**：`bash /root/GACHALIST_20261118_221526/ROLLBACK.sh`
- 源码备份：`work\ba\srv_src\_srcbackup_gacha_20261118_2215\`
  - `ShopHandler.cs` md5 `96214EA032812E6D70897E1818D7062A`
  - `AccountHandler.cs` md5 `F69C1BD6C58E70E47BFBCC8CCC8933A0`
  - `ArenaHandler.cs` md5 `B73FB07ABAD2337A37E98AFDA46C1EBC`
- 重启后：`5000/5100` 均在监听，`/api/admin/accounts` 200（0.26s），`/api/admin/gacha/banners` 返回 717 条。

## 四、待验证（需要真机）

| 项 | 观察点 |
|---|---|
| 招募页 | 三个页签下面是否不再是 `No LocalizeKey`、点「招募10次」是否**不再灰**、是否发出 `Shop_BuyGacha3`(10008) |
| wire 日志 | `grep -a 'Shop_BuyGacha' /www/wwwroot/ba_srv/logs/wire-2026-11-18.txt` 应出现请求 |
| 竞技场 | 点「对战」后是否出现 `Arena_EnterBattle`(22004) |

## 五、总力战 / 大决战（22:18 第二批，已部署）

### 证据
- 客户端在 39 秒里把 `Raid_EnterBattle`(17005) 重发 **83 次**，服务端每次 200 + 完整 JSON，客户端不推进。
- 线上响应里 **没有** `RaidDB.IsEnterRoom`（全工程 grep：只有 2 处定义、**零赋值零读取**，恒 false 且被"跳过默认值"的序列化吞掉）。
- 线上响应里 `RaidDB.Owner.CharacterId = 9`、`RaidBattleDB.RaidMembers[0].CharacterId = 9`
  —— 是**账号内 ServerId**，不是角色 UniqueId(13003)。来源 `RaidManager.cs:155/206` 把 `RepresentCharacterServerId` 当 CharacterId。
  官方 22004 样本同族字段是 `13010`（5 位 UniqueId），我们是 1 位数。
- `BIEchelon` 全工程从未赋值 ⇒ 永远 `""`（无官方格式样本，**本轮不动**，不猜）。

### 修复（只改下发，不落库）
新增 `Shittim-Server/Services/RaidWireNormalizer.cs`，在 4 个下发点各加一行调用：
`RaidHandler.CreateBattle`、`RaidHandler.EnterBattle`、`EliminateRaidHandler.CreateBattle`、`EliminateRaidHandler.EnterBattle`。
- `raid.IsEnterRoom = true`
- `Owner.CharacterId` / `RaidMembers[*].CharacterId` → `GetAccountCharacters(accountId).FirstOrDefault(c => c.ServerId == value)?.UniqueId ?? value`
  （**已经是 UniqueId 的行查不到 ⇒ 原样返回**，不会改坏；存量行也被覆盖，因为转换发生在读取时）

写路径 `RaidManager.cs:155/206` **不动**（那是落库值，判错会污染新行）。

### 部署
- 线上 DLL sha256：`df2f4aa9861dffb0fbea33273dabd67f3fa4d39e1ec799b1752a86baabab22fd`（2,678,784 B）
- 上一版：`4dbaf922026afa9d716646d16075b12721df7a20c7672011b5c400469b727549`（2,677,760 B）
- 备份目录：`/root/RAIDWIRE_20261118_221845`
- **一行回滚**：`bash /root/RAIDWIRE_20261118_221845/ROLLBACK.sh`
- 构建目录：`work\ba\srv_src\_build_raid1`

### 仍然未解决
- 竞技场 `Arena_EnterBattle`(22004)：官方是「**服务端算完整场战斗**再回放」（响应里带 `BattleSetting` 整块 + `BattleSummary`），
  我们是「下发数据让客户端自己打」。**这不是补字段能补的架构差**，属下一个立项。
- `BIEchelon`：无官方样本，未动。
