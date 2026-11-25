# GM 管理站「一键」能力盘点（服务端只读审计）

- 审计对象：`work/ba/srv_src/Shittim-Server`（C# ASP.NET Core + EF Core/SQLite）、DTO 库 `work/ba/srv_src/Schale`
- 审计方式：**纯只读**静态阅读源码 + 只读查询本地客户端表 `work/ba/data/ExcelDB.db`（153.1 MB，398 张表）。未联网、未改任何文件、未连服务器。
- 时间：2026-11-19
- 已读关键文件与行号在文中以 `文件:行` 标注，全部可在源码里复核。

---

## 0. 结论速览

| 口径 | 数量 / 结论 |
|---|---|
| 已注册 GM 控制台命令 | **22 个**（`[CommandHandler]` 22 个类，`Commands/` 目录 22 个实现文件 + 基类 `Command.cs`） |
| 带 `[AdminAuth]` 的管理 API 路由 | **36 条**（`ManagementController` 29 + `AdminController` 4 + `GachaRatesAdminController` 3），全部在 `/api/admin` 下 |
| **无鉴权**的 GM 路由 | **17 条**在 `/dev/api` 下（`GM/*Controller`，无 `[AdminAuth]`、无 `[Authorize]`）；另有 5 条 `/dev/*` 仅 DEBUG 编译 |
| 服务端 EF 表（DbSet） | **71 个**（`Schale/Data/SchaleDataContext.cs:15-89`） |
| 语义上真正「批量 / 一键」的 REST 端点 | **2 个**：`POST /api/admin/command`（跑任意 GM 命令）、`POST /api/admin/events/unlock`（单活动多动作） |
| **可直接做成按钮的能力类别** | **7 类**（见 §0.1） |

### 0.1 现成能直接做成按钮的能力（7 类）

1. **发道具 / 发货币**（`items/give`、`currency/set`、`mail/send`、命令 `give` / `currency` / `addeleph`）
2. **发邮件（含任意包裹类型，可一次多包裹）**（`mail/send` + `MailManager`，走正规包裹链路）
3. **角色养成拉满 / 解锁学生**（命令 `max`、`giveall`、`character add|modify`）
4. **进度批量解锁**（命令 `unlockall campaign|story|weekdungeon|schooldungeon|battlepass|mission`）——面板已经在用
5. **整包发放 collection（含记忆大厅、家具、徽章、剧情）**（命令 `inventory add all|lobbies|furnitures|emblems|scenarios`）
6. **赛季 / 活动切换与活动解锁**（命令 `setseason`、`setraid`；`events/schedule`、`events/unlock`）
7. **账号管理 / 封禁 / 重置**（`account/update` 的 `State`、`account/delete`；协议层 `Account_Reset` 已有全套重置逻辑，缺 HTTP 壳）

> 缺口只有一类：**没有「一个 HTTP 端点 = 一个业务按钮」的结构化接口**。除 `events/unlock` 外，所有"一键"能力都藏在**字符串命令**里，面板只能 `POST /api/admin/command {Uid, Command}` 转发。所以"加按钮"的实际工作 = 前端加按钮 + （可选）后端加结构化壳，不需要新写业务逻辑。

---

## 1. GM / 控制台命令总表

### 1.1 命令的注册与执行机制

- 基类：`Commands/Command.cs`。参数校验靠属性 `[Argument(position, pattern, description, flags)]`，`Validate()` 用正则逐个校验（`Command.cs:19-52`）。
- 注册表：`CommandFactory.commands`，`LoadCommands()` 反射扫描 `[CommandHandler(name, hint, usage)]`（`Command.cs:104-144`），启动时调用一次（`CLI/GameServer.cs:74`）。
- **命令名大小写敏感**：字典 key 就是特性里的名字（全小写），`/api/admin/command` 不做 `ToLower()`（`ManagementController.cs:443`），传 `UnlockAll` 会得到 `Unknown command`。控制台路径反而会 lower（`Services/Client/ConsoleCommand.cs:22`）。
- 三个入口：
  1. 服务器控制台：`ConsoleCommandListener`（`ConsoleCommand.cs:8-35`），`/命令 参数`，默认账号 `--id` 缺省 = **2**（`GameServer.cs:221-231`）；注意它 `command?.Execute()` 不 await（fire-and-forget）。
  2. **`POST /api/admin/command`**（`ManagementController.cs:436-477`，始终编译，正式可用）。
  3. `POST /dev/execute-command`（`Dev/CommandDevController.cs:140-178`）——**仅 DEBUG**，无鉴权。
- 命令内部**各自开 DbContext、各自 SaveChanges**，没有跨命令事务；一条命令里多表写入中途异常会留下半成品。

### 1.2 命令总表（22 条）

危险级：**只读** = 不写库；**写入** = 改账号数据但可预期；**破坏性** = 大范围删改 / 不可逆 / 会让客户端状态崩。

| # | 命令 | 参数（正则/取值） | 作用 | 涉及表 | 危险级 |
|---|---|---|---|---|---|
| 1 | `help` | `[command]` | 列命令 / 单命令用法 | — | 只读 |
| 2 | `give` | `<名称\|id> [数量]` | 按 ItemExcel 名称/ID 加道具；`credit`/`activity` 走整类刷 | `Items` | 写入 |
| 3 | `giveall` | — | 只补**缺失**的可玩学生（`IsPlayableCharacter && !IsNPC && ProductionStep.Release`），初始 1 级/默认星 | `Characters` | 写入 |
| 4 | `giveequip` | `<id\|名称> <tier> <数量>` | 加单件装备（`BoundCharacterServerId=0`） | `Equipments` | 写入 |
| 5 | `giveallequip` | — | **全装备 × Tier 1..10 × 999 堆叠**（`GiveAllEquipCommand.cs:22-40`） | `Equipments` | 写入（量爆炸） |
| 6 | `inventory` | `add\|remove` + `all\|characters\|weapons\|equipments\|items\|gears\|lobbies\|scenarios\|furnitures\|emblems` + `barebone\|basic\|ue30\|ue50\|max` | 批量增/删整套 collection（`InventoryGM.*`） | `Characters`/`Weapons`/`Equipments`/`Items`/`Gears`/`MemoryLobbies`/`ScenarioHistories`/`Furnitures`/`Emblems` | **破坏性**（`remove all` 清空） |
| 7 | `mail` | `<type 2/3/4/13> <id,...> [数量]` \| `clear` | 发系统邮件；`clear` 删未读邮件 | `Mails` | 写入 |
| 8 | `currency` | `<货币名\|id> <数量>` \| `show` | **绝对赋值**货币；`Gem` 走 `GemBonus+GemPaid` 再由 `UpdateGem` 推导（`CurrencyCommand.cs:64-78`） | `Currencies` | 写入 |
| 9 | `character` | `add\|remove\|modify\|show` + `all\|角色id` + `barebone..max` / `level\|star\|skill\|ps` + 数值 | 学生增删改；`remove all` 保留默认角色并复位，`modify all` 全量改 | `Characters`（+`Equipments`/`Weapons`/`Gears`） | **破坏性** |
| 10 | `max` | `<all\|角色名>` | 已拥有学生 **Lv90 / MaxStarGrade / 好感100 / 技能 10-5-10-10 / 潜力 25-25-25**，武器 **4★ / Lv60**（`MaxCommand.cs:50-59,73-74`） | `Characters`、`Weapons` | 写入 |
| 11 | `addeleph` | `<角色名> [数量=9999]` | 设该角色碎片的 **StackCount = 数量（绝对覆盖，不是累加）**（`AddElephCommand.cs:55-58`） | `Items` | 写入 |
| 12 | `setaccount` | `<属性> <值>` | **反射写 `AccountDBServer` 任意可转换属性**：`Level`/`Nickname`/`State`(封禁)/`RaidSeasonId`/`MemoryLobbyUniqueId`…（`SetAccountCommand.cs:38-53`） | `Accounts` | **破坏性** |
| 13 | `setting` | `trackpvp\|usefinal\|bypassteam\|bypasssummon\|changetime` `[enable\|disable\|±天数]` | 改 `GameSettings`（含强制改时区/日期） | `Accounts`（JSON 列 `GameSettings`） | 写入 |
| 14 | `setseason` | `total\|grand\|drill\|final\|show` `<id>` | 切总力战/大决战/演习/最终限制赛季（`ContentGM.SetContentSeason`） | `Accounts`(ContentInfo)、`SingleRaidLobbyInfos`/`EliminateRaidLobbyInfos`/`TimeAttackDungeonRooms`/`MultiFloorRaids` | 写入 |
| 15 | `setraid` | `total\|grand` `to\|show` `[snapshotId] [battleId]` | 用历史快照覆盖总力战队伍/战绩（`SetRaidCommand.cs`，13.9KB） | `Raids`/`RaidBattles`/`BattleSummaries`/`RaidSummaries` | 写入 |
| 16 | `gacha` | `rate\|guarantee\|reset\|settings\|show` `[值] [百分比]` | 改爆率/保底 — **只写进程内静态字典**（`GachaCommand.cs:22-23,136-177`），重启即失效 | 无表（内存） | 写入（不持久） |
| 17 | `unlockall` | `campaign\|story\|weekdungeon\|schooldungeon\|battlepass\|mission` | 批量解锁（详见 §3.2） | `CampaignStageHistories`/`ScenarioHistories`/`WeekDungeonStageHistories`/`SchoolDungeonStageHistories`/`BattlePasses`/`MissionProgresses` | 写入 |
| 18 | `unlockbattlepass` | — | 只开通行证付费轨（`PurchaseGroupId=1`），**不动等级/经验** | `BattlePasses` | 写入 |
| 19 | `clearinventory` | — | 删全部 `Items` + 未绑定 `Equipments` | `Items`、`Equipments` | **破坏性** |
| 20 | `accountdata` | `list\|load\|export` `<file.json>` | 整包存档导入/导出（`AccountDataCommand.cs`，378 行，逐表 `RemoveRange` + 重灌 + 旧 ServerId 重映射） | 10+ 表整体替换 | **破坏性** |
| 21 | `listitem` | `<类别\|关键词>` | 列道具 | — | 只读 |
| 22 | `checkitem` | `<名称>` | 查单件道具明细 | — | 只读 |

**要点（容易被面板写错的地方）**

- `giveall` 与 `inventory add characters` **不等价**：后者调 `InventoryGM.AddAllCharacters`（`InventoryGM.cs:44-88`），会把**已拥有角色**的等级/星级/技能/好感一起改写（副作用），前者只补缺失。
- `max` 里的 **90 级是硬编码**（`MaxCommand.cs:50`）。本地客户端 `CharacterLevelDBSchema` 恰好 **90 行**，所以当前安全；若服务端表等级上限与客户端不一致，这里就是脏数据入口。
- `inventory add` 默认 `barebone`，会把已有角色**降级**（`starGrade=0 → DefaultStarGrade`、`Level=1`）。做按钮时选项必须显式传 `max`。
- `mail` 的 `type` **只支持 2/3/4/13**（Currency/Item/Equipment/Furniture，`MailCommand.cs:127-145,152`），**不支持 8（MemoryLobby）**——见 §3.1 的纠错。
- `addeleph` 是**赋值**不是累加，重复点会变小。
- `gacha` 命令与新的文件制 `GachaRateConfig`（`/api/admin/gacha/rates`）是**两套并存**的爆率来源（§5-R8）。

---

## 2. 管理 API 总表

### 2.1 鉴权模型（先看这个，决定按钮的安全边界）

`Controllers/AdminAuthAttribute.cs`（84 行，`[AdminAuth]` = `IAuthorizationFilter`）：

- 取 key：`SHITTIM_ADMIN_API_KEY` 环境变量 → 否则 `Config.Instance.ServerConfiguration.AdminApiKey`（`:53-60`）。
- **配了 key**：任何来源（含 127.0.0.1 / 反代后的 loopback）都必须带 `X-Admin-Key`，`CryptographicOperations.FixedTimeEquals` 定时比较（`:62-71`），否则 403。
- **没配 key**：只放行 loopback（含 `::ffff:127.0.0.1`），其余 403。
- 代码注释明确写了动机：`app.UseAuthorization()` 没有注册 scheme、没有任何 `[Authorize]`，**没有这个 filter 的话，邮件/货币/控制台命令/删号端点对任何能连上端口的人开放**（`AdminAuthAttribute.cs:12-13`）。

> 也就是说：`/api/admin/*` 的安全性**完全取决于是否配了 `AdminApiKey`**。面板直连时若只靠 loopback，则等于无鉴权（任何本机进程 / 反代转发都能调）。

### 2.2 `[AdminAuth]` 路由总表（36 条，前缀 `api/admin`）

#### ManagementController（29 条，`Controllers/ManagementController.cs`）

| # | 方法 + 路径 | 参数 | 作用 | 写表 |
|---|---|---|---|---|
| 1 | `GET status` | — | 服务/版本/端口/开关/账号数/运行时长 | — |
| 2 | `GET account/{serverId}/detail` | path | 账号详情 + 货币字典 + 道具/角色/邮件计数 | — |
| 3 | `POST account/create` | `{Nickname, CallName}` | 建号（合成 `PublisherAccountId`，再 `InitializeCompleteAccount` 全量播种） | `UserAccounts`、`Accounts`、初始化所有子表 |
| 4 | `POST account/update` | `{ServerId, Nickname, CallName, Comment, Level, Exp, VIPLevel, State}` | 改账号字段；**`State=Dormant(2)` 就是封禁**（注释明说唯一受支持封禁方式） | `Accounts` |
| 5 | `POST account/delete` | `{ServerId}` | **级联删号**：从 `sqlite_master` 找出所有带 `AccountServerId` 列的表逐表 `DELETE`，再删 `Accounts`/`UserAccounts`，清 `SelectedAccountId` | 全部子表 + `Accounts` + `UserAccounts` |
| 6 | `GET account/selected` | — | 当前"游戏登录用哪个号" | — |
| 7 | `POST account/select` | `{ServerId}` | 改 `ServerConfiguration.SelectedAccountId`（下次 `Account_CheckNexon` 生效，无需重启） | 配置 + `config.json` |
| 8 | `GET account/{serverId}/items` | path | 背包列表（含名称/图标） | — |
| 9 | `POST items/give` | `{AccountServerId, UniqueId, Amount, SetExact}` | 加道具（`SetExact=true` 改为绝对赋值） | `Items` |
| 10 | `POST items/remove` | `{AccountServerId, UniqueId}` | 删该道具行 | `Items` |
| 11 | `GET account/{serverId}/characters` | path | 学生列表（含 DevName/中名） | — |
| 12 | `GET account/{serverId}/mails` | path | 邮件列表（含包裹） | — |
| 13 | `POST mail/delete` | `{AccountServerId, MailServerId?, ClearAll}` | 删单封 / 清空 | `Mails` |
| 14 | **`POST command`** | **`{Uid, Command}`** | **跑任意 GM 命令**（§2.3） | 取决于命令 |
| 15 | `GET static/items` | `search, limit(≤2000)` | 道具静态表 | — |
| 16 | `GET static/characters` | `search, limit` | 学生静态表（`IsPlayable && IsPlayableCharacter && !IsNPC && !IsDummy`） | — |
| 17 | `GET static/equipment` | `search, limit` | 装备静态表 | — |
| 18 | `GET static/currencies` | — | 货币枚举 | — |
| 19 | `GET meta/parceltypes` | — | `ParcelType` 枚举（含 `MemoryLobby=8`） | — |
| 20 | `GET gacha/config` | — | 旧制 `gacha_config.json` 状态 | — |
| 21 | `POST gacha/config` | `{Ssr, Sr, R, Guaranteed, ClearRates}` | 写 `gacha_config.json`（旧制） | 文件 |
| 22 | `GET gacha/banners` | — | 卡池列表（`ShopRecruitExcel`） | — |
| 23 | `GET events/seasons` | `uid?` | 四类赛季全表 + 该 uid 当前赛季 | — |
| 24 | `GET notice` | — | 维护公告 flags / gate 错误码 | — |
| 25 | `POST notice` | `{Flags, GateError, GateMessage}` | 设维护公告（内存 + 落盘） | 内存/文件 |
| 26 | `GET events/schedule` | — | 活动总表（含 rail/图标/banner/学生加成/币种/开关状态） | — |
| 27 | `POST events/schedule` | `{Enabled:[long]}` | 设"开哪些活动"（写 excel 的 open/close，行级改） | Excel 覆盖 + 文件 |
| 28 | `GET events/{eventContentId}/unlocks` | path, `uid?` | 单活动**进度统计**（关卡/任务/商店/收集/小游戏完成数） | — |
| 29 | `POST events/unlock` | `{AccountServerId, EventContentId, ClearStages, CompleteMissions, ResetShop, UnlockCollections, UnlockMinigame, ClearMinigames, Currency{id:amt}}` | 单活动**多动作批量解锁**（唯一真批量写端点） | `CampaignStageHistories`/`MissionProgresses`/`ShopPurchaseHistories`/`EventContentCollections`/`MiniGame*Histories`/`EventContentPermanents`/`Items` |

#### AdminController（4 条，`Controllers/AdminController.cs`）

| # | 方法 + 路径 | 参数 | 作用 |
|---|---|---|---|
| 30 | `POST mail/send` | `{AccountServerId, Sender?, Comment, Parcels:[{Type:"ParcelType 名", Id, Amount}], ExpireDate?}` | **发系统邮件（多包裹 / 任意包裹类型，含 `MemoryLobby`）**，走 `MailManager.SendSystemMailMultipleParcels` |
| 31 | `POST currency/set` | `{AccountServerId, CurrencyType, Amount}` | 绝对赋值货币（`Gem` 同样走 `GemBonus`+`GemPaid` 再到 `UpdateGem`） |
| 32 | `GET accounts` | — | 账号名册（`DevId == null`，过滤服务器自己的 Schale bot；含 PublisherAccountId / State） |
| 33 | `GET account/{serverId}/currencies` | path | 货币字典 |

#### GachaRatesAdminController（3 条，`Controllers/GachaRatesAdminController.cs`）

| # | 方法 + 路径 | 参数 | 作用 |
|---|---|---|---|
| 34 | `GET gacha/rates` | — | 当前生效爆率 + 默认值 + 文件状态 + 备份信息 |
| 35 | `POST gacha/rates` | `{"rates":{"Pickup":{"ssrThreshold":30}, ...}}` | 合并写覆盖文件（校验 → 备份 → 原子写），下次抽卡即生效 |
| 36 | `POST gacha/rates/reset` | `{"scope":"all"\|"Normal"\|"Pickup"\|"Limited"\|"Fes"}` | 重置某组/全部 |

### 2.3 【重点】`POST /api/admin/command` —— 执行任意 GM 命令

**鉴权**：类级 `[AdminAuth]`（`ManagementController.cs:24-27`），规则见 §2.1 —— 配了 `AdminApiKey` 就必须带 `X-Admin-Key`，没配就只允许 loopback。

**代码**（`ManagementController.cs:428-477`）：

```csharp
public class RunCommandRequest
{
    public long Uid { get; set; }
    public string Command { get; set; } = "";
}

// Always-on bridge to the full console command set (give / max / giveall / unlockall / setseason / gacha / ...).
// Mirrors the DEBUG-only /dev/execute-command but ships in every build so the GUI can drive it.
[HttpPost("command")]
public async Task<IActionResult> RunCommand([FromBody] RunCommandRequest request)
{
    if (request == null || request.Uid <= 0 || string.IsNullOrWhiteSpace(request.Command))
        return BadRequest(new { error = "uid and command are required" });

    var parts = request.Command.Trim().Split(' ', StringSplitOptions.RemoveEmptyEntries);
    var name = parts.First().TrimStart('/', '!', '.', '*').Split('/').Last();
    var args = parts.Skip(1).ToArray();
    ...
    var connection = _webService.GetClient(request.Uid, writer);   // 绑定 AccountServerId = Uid
    cmd = CommandFactory.CreateCommand(name, connection, args);    // 校验参数正则
    if (cmd == null) return BadRequest(new { error = $"Unknown command: {name}" });
    await cmd.Execute();                                           // 命令内部自己 SaveChanges
    ...
    return Ok(new { success = true, output = ... });
}
```

**参数结构**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `Uid` | long（>0） | 是 | **目标账号 `Accounts.ServerId`**。任意 uid：改哪个号就传哪个号，不做归属/权限校验 |
| `Command` | string | 是 | 整条命令行，空格分隔。首段允许带 `/`、`!`、`.`、`*` 前缀并取最后一个 `/` 后的段；**其余按已注册的小写命令名精确匹配** |

**调用示例**

```bash
# 给账号 4 解锁全部主线关卡
curl -s -X POST http://127.0.0.1:<API_PORT>/api/admin/command \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: <TOKEN>" \
  -d '{"Uid":4,"Command":"unlockall campaign"}'
# => {"success":true,"output":"Unlocked all campaign stages (1132 new, rest updated in place)!"}
```

```bash
# 拉满某账号全部角色
curl -s -X POST .../api/admin/command -H "X-Admin-Key: <TOKEN>" \
  -d '{"Uid":4,"Command":"max all"}'
# => {"success":true,"output":"Maxed out 143 characters and 141 weapons!"}

# 整包解锁记忆大厅（服务端 MemoryLobbyExcel 全表）
curl -s -X POST .../api/admin/command -H "X-Admin-Key: <TOKEN>" \
  -d '{"Uid":4,"Command":"inventory add lobbies"}'
# => {"success":true,"output":"Added all Memory Lobbies!"}

# 非法参数 -> 400，message 来自 [Argument] 描述
curl -s -X POST .../api/admin/command -d '{"Uid":4,"Command":"give 1"}'
# => HTTP 400 {"error":"Argument AmountStr is invalid!"}
```

**返回值语义**：命令里的 `connection.SendChatMessage(...)` 全被重定向到 `MemoryStream`，成功时以纯文本 `output` 返回（多行拼接）；异常/校验失败为 HTTP 400 + `{error}`。

**行为细节（做按钮必须知道）**

1. **只作用于一个 uid**，没有多选 / 批量 uid 参数；批量要面板循环。
2. `Uid` 必须真实存在：命令内部 `context.GetAccount()` 是 `First()`（`Schale/Data/GameModel/UserModel/AccountDB.cs:166-169`），不存在会抛 `InvalidOperationException`，被外层 catch 成 400 `{"error":"Sequence contains no elements"}`（不是"账号不存在"这种友好文案）。
3. **命令名大小写敏感**（不 `ToLower`）→ 面板必须发小写。
4. 缺少 `Uid`/`Command`、`Uid<=0` → 400 `uid and command are required`。
5. `WebService.GetClient(uid, writer)` 会**按 uid 缓存连接**并把 `StreamWriter` 换成本次的（`Services/WebClient/WebService.cs:28-46`）；同一 uid 并发两条命令会互相覆盖 writer，且 `MemoryStream` 已 dispose → 可能 `ObjectDisposedException`。**按钮层应对同一 uid 串行化**。
6. 无超时、无事务、无审计日志（不写 Log，除了命令内部自身的错误）。面板侧 `ba_command()` 给了 30s 超时（`panel_work/p0rates/inc/ba.php:402-408`）。
7. 部分命令（如 `unlockall weekdungeon`/`schooldungeon`）是**无幂等判断的 `Add`**（`UnlockAllCommand.cs:138,160`），重复点会报主键/唯一约束错误或产生重复行（见 §5-R10）。

### 2.4 「批量」能力盘点（用户特别问的）

| 想做的批量操作 | 现有端点 | 结论 |
|---|---|---|
| **批量发道具** | `items/give`（一次 1 个 `UniqueId`）；`mail/send`（一次 1 个账号 N 个包裹） | ❌ 无数组批量；要么循环 M 次 `items/give`，要么 1 封邮件挂 N 个包裹（**推荐**，客户端可一次性领取，且有 `ParcelResult` 回执） |
| **批量发邮件（多账号）** | `mail/send` 单账号 | ❌ 无多账号入参，面板循环 |
| **改等级** | `account/update.Level` = **账号等级**（不是学生等级） | ⚠️ 学生等级只能靠命令 `max` / `character modify level` |
| **清关卡** | 无 | ❌ 只能 `inventory remove scenarios`（清剧情）/ 直接删 `CampaignStageHistories` 行 |
| 批量解锁全部学生 | 命令 `giveall` / `inventory add characters` | ✅ 但两者语义不同（见 §1.2 要点） |
| 批量发全图鉴道具 / 全家具 | 命令 `inventory add items` / `inventory add furnitures` | ✅（有客户端 id 风险，§5） |
| 活动内多动作批量 | `events/unlock`（关卡+任务+商店+收集+小游戏+货币，一次调用） | ✅ **已经是"一键"形态，可作为新端点的模板** |

---

## 3. 五个点名能力的实现路径

### 3.1 「发放全部记忆大厅」

#### 3.1.1 记忆大厅在数据里到底是什么（**确切位置**）

| 层面 | 位置 | 说明 |
|---|---|---|
| **拥有集合（要写的表）** | EF `DbSet<MemoryLobbyDBServer> MemoryLobbies`（`Schale/Data/SchaleDataContext.cs:30`）→ SQLite 表 **`MemoryLobbies`** | 一行 = 账号拥有一个大厅 |
| **表结构** | `Schale/Data/GameModel/UserModel/MemoryLobbyDB.cs:9-25` | `ServerId` (PK, 自增 long)、`AccountServerId` (long)、`MemoryLobbyUniqueId` (long) —— **只有这三个字段**，没有 "unlocked/level" 之类状态列 |
| **"当前选用"（不是拥有）** | `Accounts.MemoryLobbyUniqueId`（`AccountDBServer`），由 `MemoryLobby_SetMain` 写（`Core/NetworkProtocol/Handlers/MemoryLobbyHandler.cs:39-52`） | 只改它**改不出"拥有"**，大厅列表仍为空 |
| **静态档案（id 段来源）** | `MemoryLobbyExcel`（`Schale/FlatData/MemoryLobbyExcel.cs`）字段：`Id` / `ProductionStep` / `LocalizeEtcId` / `CharacterId` / `PrefabName` / `MemoryLobbyCategory` / `BGMId` / 资源路径 | 服务端通过 `ExcelTableService.GetTable<MemoryLobbyExcelT>()` 读 |
| **包裹类型** | `ParcelType.MemoryLobby = 8`（`Schale/FlatData/ParcelType.cs:18`） | 唯一"正规"发放通道的 type |
| **唯一会写这张表的运行时路径** | `Services/ParcelHandler.cs:114-116` → `Services/ParcelResolver.cs:253-271 UpdateMemoryLobby()` | 幂等：`(AccountServerId, MemoryLobbyUniqueId)` 已存在就 return，否则 `Add` |

#### 3.1.2 id 段（实测，不是推测）

来源：本地客户端表 `work/ba/data/ExcelDB.db` 的 `MemoryLobbyDBSchema`（`Id INTEGER, Bytes BLOB`），只读 SQL 统计 + 逐行解析 `Bytes` 里的 `PrefabName` 字符串：

- **总行数 258**，`Id` 最小 `10000`，最大 `2300501`。
- **253 个 5 位 id，完全等于同名角色的 `CharacterId`/`UniqueId`**（例：`10000 LobbyAru`、`13010 LobbyYuuka`；234/253 能在 `CharacterDBSchema` 里找到同 id，剩 19 个是 NPC/敌方占位，如 `10127-10136`、`16018-16019`、`20050-20056`）。
- **5 个 7 位 `_multi` id**（多人立绘）。

**客户端可见 id 全集（12 段，258 个）**：

```
10000-10098, 10100-10136, 13000-13014, 16000-16019,
20000-20056, 23000-23008, 26000-26015,
1000501, 1001001, 1300401, 1300801, 2300501
```

分段含义（按角色 100 号段分组）：`10xxx` 阿拜多斯系、`13xxx` 千年/三一系、`16xxx` 格黑娜系、`20xxx` 百鬼/山海系、`23xxx` 阿里乌斯/女武神系、`26xxx` 其余。

> ⚠️ 上面 258 是**客户端（CN，160.5 MB）**的行数。服务端跑的是**日服表（311.1 MB）**，`MemoryLobbyExcel` 行数是它的**超集**（`ClientItemFilter.cs:13-16` 记录了这两个尺寸）。两者条数之差（服务端多出来的那批 id）正是脏 id 风险的来源，见 §5-R3。

#### 3.1.3 四条写入路径对比（哪条能用）

| 路径 | 代码 | 会不会过客户端 id 白名单 | 是否走正规包裹链 | 何时对客户端生效 | 评价 |
|---|---|---|---|---|---|
| **A. 命令 `inventory add lobbies`** | `InventoryGM.AddAllMemoryLobbies`（`GameMasters/InventoryGM.cs:327-348`） | ❌ 不过滤 `ProductionStep`，不过滤客户端不存在的 id | ❌ 直接 INSERT | 客户端下次拉 `MemoryLobby_List` / 重登 | 最省事但**最脏**，必须加白名单才能上按钮 |
| **B. `POST /api/admin/mail/send`** `Parcels:[{"Type":"MemoryLobby","Id":<id>,"Amount":1}]` | `AdminController.cs:31-60` → `MailManager.SendSystemMailMultipleParcels`（`Services/MailManager.cs:81-98`）→ 客户端领取 → `ParcelResolver.UpdateMemoryLobby` | 取决于你放的 id（可只放 258 个） | ✅ 幂等 + 返回 `ParcelResultDB.MemoryLobbyDBs`，**领完立刻生效、不用重登** | 客户端领邮件那一刻 | **推荐**：一次邮件挂 N 个包裹（258 个也只是一个 `Parcels` 数组） |
| **C. 命令 `mail 8 <id> 1`** | `Commands/MailCommand.cs:121-146` | — | — | — | ❌ **不可用**：`_itemDict` 只注册了 `Currency(2)/Item(4)/Equipment(3)/Furniture(13)`，type 8 直接回 `"Error: Please enter the correct type and id"` |
| **D. 直接 SQL / EF 插 `MemoryLobbies`** | — | 完全绕过 | ❌ 无包裹回执、无 `DisplaySequence` | 重登 | 只在运维脚本里用，不做按钮 |

> **纠错**：`work/ba/server/deploy/MEMORYLOBBY_GRANT.md` 写的 `!mail 8 13010 1` 与当前源码不符（该文档自己也标了"待验证"）。当前代码下 **`!mail` 拒绝 type 8**，同一个目的请用 **B（`/api/admin/mail/send`）** 或 A+白名单。

#### 3.1.4 建议实现（"一键发放全部记忆大厅"按钮）

```text
1) 读服务端 MemoryLobbyExcelT 全表（GetTable<MemoryLobbyExcelT>()）
2) 与客户端白名单取交集（白名单来源：客户端 MemoryLobbyDBSchema.Id，
   生成方式与 Resources/ClientItemIds.txt 完全一样，见 scripts/gen_client_item_ids.py）
3) 只对交集打包：POST /api/admin/mail/send
   { "AccountServerId": UID, "Sender": "Schale", "Comment": "Memory Lobby (all)",
     "Parcels": [ {"Type":"MemoryLobby","Id":10000,"Amount":1}, ... ] }
4) 玩家登录后领邮件 -> MemoryLobbies 幂等插入 -> MemoryLobby_List 立刻可见
```
若要做"立刻生效、不等玩家点领取"，才需要新写一个复用 `ParcelResolver.UpdateMemoryLobby` 的端点（照抄 §3.1.3 B 的链路，少一次领取动作）。

**不要做的事**：不要只改 `Accounts.MemoryLobbyUniqueId`（那是"当前选用"，玩家不拥有就无法切回去）；不要给 `MemoryLobbies` 塞 `ProductionStep != Release` 的大厅。

---

### 3.2 「一键解锁全部任务 / 关卡」

**服务端现成实现 = `Commands/UnlockAllCommand.cs`（命令 `unlockall`）**，六个 target 各自写不同表：

| target | 写什么 | 关键实现 | 备注 |
|---|---|---|---|
| `campaign` | `CampaignStageHistories`：遍历 `CampaignChapterExcel.NormalCampaignStageId + Hard + NormalExtra + VeryHard`，已存在则**就地补星**（Star1/2/3、BestStarRecord=3、IsClearedEver、ClearTurnRecord、首通/星奖励时间），否则新建行（`UnlockAllCommand.cs:29-79`） | 幂等（按 `StageUniqueId` 查已有） | **不写** `CampaignChapterClearRewardHistories`（章节全清奖励），见 §5-R7 |
| `story` | `ScenarioHistories`：`ScenarioModeExcel` 里 `ModeType ∈ {Main, Sub, Prologue, SpecialOperation, Mini}` 且 `EventContentId == 0` 的行 | 注释解释了为什么必须写它："只写 stage history 客户端仍然全锁"（`:82-83`） | 排除活动剧情（活动要靠事件协议） |
| `weekdungeon` | `WeekDungeonStageHistories`（`StarGoalRecord` 按 `StarGoal` 生成） | **无幂等判断，直接 Add**（`:138`） | 重复执行 → 重复行/约束冲突 |
| `schooldungeon` | `SchoolDungeonStageHistories`（`StarFlags` 全 true） | **无幂等判断，直接 Add**（`:160`） | 同上 |
| `battlepass` | `BattlePasses`：**所有赛季**创建/更新为 `PassLevel=50, PurchaseGroupId=1, ReceiveRewardLevel=50, ReceivePurchaseRewardLevel=50`（`:171-197`） | upsert | 与 `unlockbattlepass`（只开付费轨、不动等级）不同 |
| `mission` | `MissionProgresses`：全表 upsert，`Complete=true`，`ProgressParameters` 按 `CompleteConditionParameter` 构造（`:199-227`） | upsert | 参数构造是 `count==1 ? [0] : 0`，与 `events/unlock` 里更精细的 `ForcedProgress` 逻辑**不一致**（见 §5-R7） |

**"面板已经有"对应的是哪条链路（已确认）**：

- `panel_work/p0rates/pages/items.php:23-30` 定义快捷动作 `unlock_campaign / unlock_story / unlock_week / unlock_school / unlock_mission / unlock_mission` → 值分别是 `unlockall campaign|story|weekdungeon|schooldungeon|mission`；
- 通过 `panel_work/p0rates/inc/ba.php:402-408 ba_command($uid, $command)` → `POST /api/admin/command`；
- `pages/console.php:41` 也把 `unlockall` 列进命令参考；`:169` 还有 `unlockall campaign` 之类的一键示例按钮。

⇒ **服务端"一键解锁全部任务/关卡"= `unlockall` 命令 + `/api/admin/command` 转发，逻辑完整、可直接复用**。做新按钮不需要写新业务，只需要（可选）把它包装成 `POST /api/admin/progress/unlock-all {AccountServerId, Campaign:true, ...}`，内部逐条 `CommandFactory.CreateCommand(...)` 或直接调同样的写表代码。

**已知缺口**：没有"反向"命令（清关卡/清剧情），只有 `inventory remove scenarios` 和 `inventory remove all`（会连角色一起删）。

---

### 3.3 「一键满级 / 一键满星 / 一键解锁全部学生」

| 能力 | 现成实现 | 写什么 | 缺口 |
|---|---|---|---|
| **满级** | `MaxCommand`（`max all`）→ `Level=90`、`Exp=0` | `Characters.Level/Exp` | 90 是硬编码；等级上限若变化要改代码（客户端 `CharacterLevelDBSchema` = 90 行，当前对齐） |
| **满星** | `max` → `StarGrade = CharacterExcel.MaxStarGrade`（不是硬编码 5） | `Characters.StarGrade` | 想"只满星不动别的"→ `character modify star all 5`（`CharacterGM.ModifyAllCharacters`） |
| **满技能/好感/潜力** | `max` → `PublicSkillLevel=10, ExSkillLevel=5, PassiveSkillLevel=10, ExtraPassiveSkillLevel=10, FavorRank=100, PotentialStats={1:25,2:25,3:25}` | `Characters` | 数值硬编码，与客户端表上限未做交叉校验 |
| **满专武** | `max` → `Weapons.StarGrade=4, Level=60` | `Weapons` | 只改**已拥有**的武器；没有武器不补 |
| **解锁全部学生** | `giveall`（只补缺失，初始 1 级/默认星）或 `inventory add characters max`（补缺失 + **改写已有**为满配） | `Characters`（+ `Equipments`/`Weapons`/`Gears` 取决于选项） | 没有"只加人不改数值"的独立端点；`giveall` 名单来自 `ProductionStep.Release`（`Schale/Excel/CharacterExcelExt.cs:10-19`），`InventoryGM` 也是同一过滤，**但 `GiveAllCommand.cs:19-22` 自己又写了一遍等价条件**（两处名单定义，将来会漂移） |

**建议**：新建一个结构化端点 `POST /api/admin/characters/apply-preset {AccountServerId, Preset:"max"|"ue50"|"star5"|"level90", IncludeMissing:bool}`，内部复用 `InventoryGM.AddAllCharacters(conn, preset)` + `CharacterGM.ModifyAllCharacters`，避免面板拼字符串。

---

### 3.4 「一键发放全图鉴道具 / 全家具」

| 能力 | 现成实现 | 写什么 | 注意 |
|---|---|---|---|
| **全道具（图鉴）** | `inventory add items` → `InventoryGM.AddAllItems`（`InventoryGM.cs:259-325`） | `Items`：`ItemExcel` 全表，每个 `StackCount = StackableMax/2`（`StackableMax-100<=0` 时取 1）；**同时**把 `EquipmentExcel` 里 item 类装备按同样堆叠加进 `Equipments`（`BoundCharacterServerId=0`） | 有客户端 id 出口过滤（`ClientItemFilter`）兜底；仍**不会**发 currency（`ItemCategory.Coin` 之类要不要看具体表） |
| **全家具** | `inventory add furnitures` → `AddAllFurnitures`（`:375-408`） | `Furnitures`：`FurnitureExcel` 全表，`Location=Inventory`，`StackCount=StackableMax`，再把已有行刷成 `StackableMax` | **无出口过滤**；客户端 `FurnitureDBSchema` 只有 876 行 |
| 全徽章 | `inventory add emblems` → `AddAllEmblems`（`:410-432`） | `Emblems` | 无过滤 |
| 全剧情 | `inventory add scenarios` → `AddAllScenarios`（`:350-373`） | `ScenarioHistories` | **不过滤 `EventContentId != 0`**（与 `unlockall story` 相反！）→ 会给客户端塞活动剧情 id |
| 全学生武器/专属装备 | `inventory add weapons|equipments|gears <ue30/ue50/max>` | `Weapons`/`Equipments`/`Gears` + `Characters.EquipmentServerIds` | 会重建绑定关系 |
| 单类刷满 | `give credit <n>` / `give activity <n>` | `Items`（Coin / CharacterExpGrowth 整类） | — |

> 结论：**道具/家具/徽章/剧情/装备/武器/齿轮 7 类"全发放"全部现成**，只需前端按钮 + 客户端 id 白名单前置（§5-R2/R3）。

---

### 3.5 「一键重置某个玩家进度」

**已有实现（协议层，非 HTTP）**：`Core/NetworkProtocol/Handlers/AccountHandler.cs:973-1008`

```csharp
// dev-build reset. The account row and its publisher link survive, everything hanging off it goes, then the fresh-account seeding runs again.
[ProtocolHandler(Protocol.Account_Reset)]
public async Task<AccountResetResponse> Reset(...)
{
    // 1) 从 sqlite_master + pragma_table_info 找出所有带 AccountServerId 列的表
    // 2) 逐表 DELETE FROM "<table>" WHERE AccountServerId = @uid     <-- 不写死表名，新增表自动覆盖
    // 3) 复位 account: Nickname/CallName/Comment/Level=1/Exp=0/RepresentCharacterServerId=0/MemoryLobbyUniqueId=0
    // 4) await AccountInitializationService.InitializeCompleteAccount(db, account);  // 重新播种
}
```

这套级联**已经是"一键重置"的完整实现**，而且是"按 catalog 发现表"的写法，不会漏表（同样的写法在 `ManagementController.DeleteAccount` 里也有一份，`:212-232`）。

**缺的只是 HTTP 壳**。三种落地方式（按侵入度排序）：

1. **零新逻辑**：把 `AccountHandler.Reset` 的级联抽成 `AccountResetService.ResetProgressAsync(db, accountServerId)`，`Account_Reset` 和新的 `POST /api/admin/account/reset` 都调它。
2. 临时方案：用 `POST /api/admin/command {Uid, Command:"inventory remove all"}`——**不等价**：只清 Characters/Weapons/Items/Equipments/Gears/MemoryLobbies/ScenarioHistories/Furnitures/Emblems 的**库存**部分，不清 `CampaignStageHistories`/`MissionProgresses`/`BattlePasses`/`Cafes`/`Echelons`/`Mail`/`Raid*`，也不是"重新播种"。
3. 核弹方案：`POST /api/admin/account/delete` + `account/create`（**服务器当前会把该 uid 的 `PublisherAccountId` 绑定的号整条删掉**，`SelectedAccountId` 也会被清，慎用）。

**重置后必须一并处理的会话/缓存**（否则按钮看起来"没生效"）：
- `WebService.clients`（按 uid 缓存的 `WebClientConnection`，`WebService.cs:11`）→ 该 uid 的连接对象还留着旧 writer / 旧上下文工厂引用；
- 在线会话：客户端不存在主动推送，**必须让玩家重登**；
- 若被重置的号是 `SelectedAccountId`，`Config` 也要一起看（`DeleteAccount` 会清，`Reset` 不会）。

---

## 4. 可行性判断矩阵

| 候选按钮 | 服务端现成函数 | 需新写 | 涉及表 | 一致性 / 缓存风险 | 建议形态 |
|---|---|---|---|---|---|
| 发放全部记忆大厅 | `InventoryGM.AddAllMemoryLobbies`；`ParcelResolver.UpdateMemoryLobby` | 白名单 + 端点壳（可选） | `MemoryLobbies` | 脏 id 进 `LoginSync`（高）；无缓存问题；直接插需重登、邮件链不用 | `mail/send` 打包 258 个 `MemoryLobby` 包裹（推荐）或 `command: inventory add lobbies` + 白名单 |
| 解锁全部主线/困难/额外 | `UnlockAllCommand` campaign | 否 | `CampaignStageHistories` | 缺 `CampaignChapterClearRewardHistories`；无缓存 | `command: unlockall campaign` |
| 解锁全部剧情 | `UnlockAllCommand` story | 否 | `ScenarioHistories` | 已正确排除活动剧情 | `command: unlockall story` |
| 解锁全部任务 | `UnlockAllCommand` mission | 否 | `MissionProgresses` | `ProgressParameters` 构造粗糙 | `command: unlockall mission` |
| 周常/学院地下城 | `UnlockAllCommand` weekdungeon/schooldungeon | **建议加幂等** | `WeekDungeonStageHistories`/`SchoolDungeonStageHistories` | 重复执行产生重复行 | 命令（先加 upsert） |
| 通行证 | `unlockall battlepass` / `unlockbattlepass` | 否 | `BattlePasses` | 两者语义不同，按钮要写清 | 命令 |
| 一键满级/满星/满技能 | `MaxCommand` | 可选结构化壳 | `Characters`,`Weapons` | 硬编码 90/10/5；只对已拥有 | `command: max all` |
| 解锁全部学生 | `GiveAllCommand` / `InventoryGM.AddAllCharacters` | 建议合并名单来源 | `Characters` | `add characters` 会改写已有角色 | 新端点 `characters/apply-preset` |
| 全图鉴道具 | `InventoryGM.AddAllItems` | 否 | `Items`,`Equipments` | 已有出口过滤兜底 | `command: inventory add items` |
| 全家具 | `InventoryGM.AddAllFurnitures` | 是（白名单过滤） | `Furnitures` | **无出口过滤** + 客户端 876 行上限 | 命令 + `ClientFurnitureIds` 白名单 |
| 全徽章/全剧情/全装备/全武器/全齿轮 | `InventoryGM.AddAll*` | 否（剧情需排除活动） | 各自表 | 同 §3.4 | 命令 |
| 重置玩家进度 | `AccountHandler.Reset`（级联逻辑） | **是**（抽 service + HTTP 壳） | 全部带 `AccountServerId` 的表 | 内存连接缓存 + 必须重登 | 新端点 `account/reset` |
| 封禁/解封 | `account/update.State` | 否 | `Accounts` | `Dormant` 是唯一受支持封禁值 | 前端按钮 |
| 发邮件（含任意包裹） | `AdminController.mail/send` | 否 | `Mails` | 邮件链有 `ParcelResult` 回执，即时可见 | 直接 REST |
| 改货币 | `currency/set` | 否 | `Currencies` | `Gem` 必须走 `GemBonus/GemPaid`+`UpdateGem` | 直接 REST |
| 切赛季 | `setseason` / `dev/api/set_raid` | 否 | `Accounts.ContentInfo` 等 | `GameSettings.ForceDateTime` 会影响 AP 结算 | 命令 |
| 活动解锁 | `events/unlock` | 否 | 7 张表 | 唯一的真批量端点，可作模板 | 直接 REST |

**缓存结论（用户关心 `ExcelTableService` 单例）**：

- `ExcelTableService.GetTable<T>()` 是 `ConcurrentDictionary<Type, object>` 的**只读缓存**（`Services/ExcelTableService.cs:13,33-41`）：它缓存的是**服务端 excel 静态表**，命令往里插的是**账号数据表**，二者不交集。⇒ **写账号数据不会让 Excel 缓存失效，也不需要失效**。
- 真正会"改完不生效"的是：① 客户端要重登才重新拉 `LoginSync`；② `WebService.clients` 的按 uid 连接对象；③ `GachaRateConfig`（文件制，每次抽卡读）/`ServerNoticeService`（内存）/`EventScheduleService`（内存+文件）；④ `MailNotificationService.MarkNewMail` 会让客户端**立刻**知道有新邮件（`MailCommand.cs:118`）。
- 没有跨命令事务；`unlockall` 这类上千行写入是单次 `SaveChanges`，失败即整批不落（好），但一个 target 一批，跨 target 不原子。

---

## 5. 风险清单（按严重度）

### R1【致命｜已发生过】服务端表 ⊃ 客户端表
服务端跑**日服** `Resources/Dumped/ExcelDB.db`（**311,083,008 B**），客户端是**国服**（**160,534,528 B**，md5 `824ce3a8…`）。这是 `ClientItemFilter.cs:13-16` 写死的运维事实。**"服务端表里有这个 id" ≠ "客户端能解析这个 id"**。

### R2【致命】出口过滤器只覆盖 `ItemDB` 一类
`ClientItemFilter` 的 Hook 在 `HandlerManager.Dispatch` 出口，反射只找 `List<ItemDB>` / `Dictionary<long,ItemDB>` / `ItemDB` / `ParcelResultDB`（`ClientItemFilter.cs:141-205,303-331`）。**`CharacterDB` / `EquipmentDB` / `WeaponDB` / `GearDB` / `FurnitureDB` / `MemoryLobbyDB` / `EmblemDB` / `StickerDB` / `CostumeDB` 一概没有过滤**。
⇒ 90070000 那次事故的同类问题，在"全家具 / 全记忆大厅 / 全装备 / 全徽章"按钮上会**原样复现**，而且没有任何兜底。

### R3【致命】脏记忆大厅 id 会直接打断登录
`LoginSync` 的主包里就带 `MemoryLobbyListResponse`（`AccountHandler.cs:450-453`），`MemoryLobby_List` 也是整表回传（`MemoryLobbyHandler.cs:34`）。服务端 `MemoryLobbyExcel` 是客户端 258 行的**超集**，而 `InventoryGM.AddAllMemoryLobbies` **完全不过滤 `ProductionStep`、也不过客户端白名单**（`InventoryGM.cs:332-343`）。
⇒ 一旦塞进一个客户端不认识的 `MemoryLobbyUniqueId`，**登录即解析失败**（比 `Items` 更早爆，因为 `Items` 至少在 `LoginSync` 里还有过滤器）。
**上线前必须**：生成 `ClientMemoryLobbyIds.txt`（258 个 = §3.1.2 的 12 段），只发交集；或走 `mail/send`（只放交集 id）。

### R4【高】`ProductionStep` 未过滤
`AddAllMemoryLobbies`、`AddAllFurnitures`、`AddAllScenarios`、`AddAllEmblems` 都是"excel 全表 → 全发"，**没有** `ProductionStep.Release` 过滤（对比 `giveall` 有）。⇒ 未实装/占位内容会进库，客户端轻则空白头像/空家具，重则解析失败。

### R5【高】`unlockall` 的两处不一致
1. `campaign` 只写关卡历史，**不写** `CampaignChapterClearRewardHistories`（章节全清奖励领取记录表，`SchaleDataContext.cs:45`）⇒ 客户端可能显示"章节未全清/奖励未领"，玩家点了会不会重复发奖取决于章节结算 handler 是否幂等（**未验证，上按钮前必须实测**）。
2. `mission` 的 `ProgressParameters` 用 `Count==1 ? [0] : 0` 构造（`UnlockAllCommand.cs:214`），而 `events/unlock` 用了更精细的 `ForcedProgress()`（`ManagementController.cs:1187-1199`，注释解释了"客户端按匹配到的 parameter 取计数"）。两者对同一客户端语义**不一致** ⇒ 任务可能显示"已完成但计数 0/未完成"。

### R6【高】`giveallequip` 的量级
`EquipmentExcel` **191 种**（客户端表实测）× 10 个 Tier × 999 堆叠 = **1910 行/账号**，且 `Tier` 硬编码 1..10（`GiveAllEquipCommand.cs:24`）——服务端装备的 `TierInit/MaxLevel` 不一定是 10 阶。⇒ 客户端背包渲染压力 + 越界 tier 渲染异常。**建议这个不做按钮，或改成"按装备等级上限"生成**。

### R7【中高】`weekdungeon`/`schooldungeon` 无幂等
`UnlockAllCommand.cs:138,160` 直接 `Add`，不查重。重复点按钮 ⇒ 重复行 / 唯一约束异常，客户端星级/奖励状态可能翻倍或报错。

### R8【中】抽卡爆率双轨
`!gacha` 命令写的是 `private static Dictionary<long,double> customRates`（进程内存，重启失效，`GachaCommand.cs:22,220-221`），而管理台 `gacha/rates` 写的是 `gacha_config.json`（`GachaRateConfig`，每次抽卡读）。⇒ "面板显示 30 抽、实际按 23 抽"这类问题会重演（`P0_GACHA_RATES_PLAN.md` 已踩过）。**面板只应暴露文件制的那一套**。

### R9【中】`/dev/api/*` 完全无鉴权
17 条路由（`GM/CharacterController`、`GM/SettingsController`、`GM/CommandController`、`GM/RaidController`、`GM/ArenaController`、`GM/CommonController`）没有 `[AdminAuth]`、没有 `[Authorize]`，能做：改任意玩家角色（`modify_character`）、改 `GameSettings`（含强制改时制）、切赛季、改 Schale 竞技场假人队伍。`GM/CommandController.command` 目前是**空壳**（只回显 `"Command system not yet fully implemented..."`，`GM/CommandController.cs:38`），所以"可跑任意命令"的实锤在 `ManagementController.command`，不在 `/dev/api`。
⇒ 若这些端口暴露在外网（或前面挂了反代），等同无鉴权后台。

### R10【中】无审计、无事务、无确认
`/api/admin/command` 不记录谁在什么时候对谁执行了什么；命令内部逐表 `SaveChanges`；`account/delete` 与 `Account_Reset` 直接 `ExecuteSqlRaw DELETE`。⇒ 破坏性按钮必须有二次确认 + 操作日志（面板侧自建，服务端目前没有）。

### R11【中】"改完不生效"的错觉
除邮件（`MailNotificationService.MarkNewMail`）外，所有 DB 级写入都**不会**推给在线客户端：要等下一次协议响应或重登。面板按钮的文案必须写"重登后生效"，否则会被当成按钮坏了。

### R12【低-中】SQLite 单写者
全部在一个 SQLite 文件上；`inventory add items`（几千行）、`giveallequip`（近两千行）这类批量写会长时间持有写锁，与在线玩家并发时可能 `SQLITE_BUSY`。建议按钮层限流 + 放到低峰执行。

---

## 6. 给"GM 站加按钮"的落地建议（最小改动顺序）

1. **先建两个白名单**（复用 `scripts/gen_client_item_ids.py` 的写法）：
   - `Resources/ClientMemoryLobbyIds.txt`（258 个，12 段）——**这是"全部记忆大厅"上线的前置条件**；
   - `Resources/ClientFurnitureIds.txt`（876 个）——"全家具"的前置。
2. **按钮第一期（零新逻辑，全部走 `/api/admin/command`）**：
   `max all`、`giveall`、`unlockall campaign|story|weekdungeon|schooldungeon|mission`、`unlockbattlepass`、`inventory add items|furnitures|emblems`、`give credit <n>`、`setseason <type> <id>`。
   面板侧对同一 uid 串行化 + 3 次重试 + 结果原文展示。
3. **第二期（需要新端点，但都有现成函数可抄）**：
   - `POST /api/admin/lobby/grant-all {AccountServerId}` → 白名单交集 + `mail/send` 打包（零新业务）；
   - `POST /api/admin/account/reset {ServerId}` → 抽 `AccountResetService`（抄 `AccountHandler.Reset`）；
   - `POST /api/admin/characters/apply-preset {AccountServerId, Preset, IncludeMissing}` → 抄 `InventoryGM.AddAllCharacters` + `CharacterGM.ModifyAllCharacters`。
4. **验收口径**（每个按钮都要过）：
   - 执行后用该账号**真客户端登录一次**，确认不弹"同步账号信息时发生错误"；
   - 检查 `LoginSync` 体积与 `MemoryLobbyListResponse` / `CafeGetInfoResponse.FurnitureDBs` 条数；
   - `grep "withheld ItemDB"` 日志不应新增；
   - 破坏性按钮先在备份库上跑一遍（`account/delete`、`reset`、`inventory remove all`）。

---

## 附录 A：本次审计的证据索引

| 主题 | 文件:行 |
|---|---|
| 命令基类 / 参数校验 / 工厂 | `Commands/Command.cs:8-144` |
| 22 个命令实现 | `Commands/*.cs`（`[CommandHandler]` 见 §1.2 表） |
| `unlockall` 六个 target | `Commands/UnlockAllCommand.cs:29-227` |
| `max` 硬编码 | `Commands/MaxCommand.cs:50-59,73-74` |
| `mail` 只支持 2/3/4/13 | `Commands/MailCommand.cs:127-145,152` |
| `inventory` 类型表 | `Commands/InventoryCommand.cs:17-25,47-150` |
| `InventoryGM.AddAll*` | `GameMasters/InventoryGM.cs:13-432` |
| `magic lobby` 表 / 字段 | `Schale/Data/GameModel/UserModel/MemoryLobbyDB.cs:9-46` |
| `MemoryLobbies` DbSet | `Schale/Data/SchaleDataContext.cs:30` |
| 唯一写入路径 | `Services/ParcelHandler.cs:114-116`；`Services/ParcelResolver.cs:253-271,572-575` |
| 大厅协议（List/SetMain） | `Core/NetworkProtocol/Handlers/MemoryLobbyHandler.cs:26-78` |
| `LoginSync` 带大厅列表 | `Core/NetworkProtocol/Handlers/AccountHandler.cs:450-453` |
| 一键重置（协议层） | `Core/NetworkProtocol/Handlers/AccountHandler.cs:973-1008` |
| `[AdminAuth]` 实现 | `Controllers/AdminAuthAttribute.cs:10-84` |
| `ManagementController`（29 路由 + command） | `Controllers/ManagementController.cs:24-27,51-1258`（command：`428-477`） |
| `AdminController`（mail/send 等 4 条） | `Controllers/AdminController.cs:12-196` |
| `GachaRatesAdminController`（3 条） | `Controllers/GachaRatesAdminController.cs:17-184` |
| 无鉴权 `/dev/api` | `Controllers/GM/*.cs`（`[Route("/dev/api")]`，无 `[AdminAuth]`） |
| DEBUG-only 命令执行 | `Controllers/Dev/CommandDevController.cs:1,140-178`（`#if DEBUG`） |
| 出口过滤器范围 | `Services/ClientItemFilter.cs:13-16,141-205,303-331` |
| 服务端/客户端表尺寸差 | `Services/ClientItemFilter.cs:13-15`；`plan/20261119/EXPORT_FILTER.md:30-38` |
| Excel 表缓存 | `Services/ExcelTableService.cs:13,33-41,47-60` |
| 按 uid 缓存的 Web 连接 | `Services/WebClient/WebService.cs:11,28-63` |
| 面板现有按钮 → command | `panel_work/p0rates/pages/items.php:23-30,235`；`pages/console.php:5,41,169`；`inc/ba.php:402-408` |
| 客户端表实测（258 大厅 / 876 家具 / 1803 道具 / 90 级） | 只读查询 `work/ba/data/ExcelDB.db`（398 表） |

## 附录 B：客户端记忆大厅 id 全集（258，可直接做白名单）

```
10000-10098
10100-10136
13000-13014
16000-16019
20000-20056
23000-23008
26000-26015
1000501
1001001
1300401
1300801
2300501
```

生成方式（与 `Resources/ClientItemIds.txt` 同法）：
```sql
-- 对客户端 ExcelDB.db（只读）
SELECT Id FROM MemoryLobbyDBSchema ORDER BY Id;
```

## 附录 C：已纠正的历史说法

| 旧说法 | 位置 | 现状 |
|---|---|---|
| `!mail 8 13010 1` 可发放记忆大厅 | `work/ba/server/deploy/MEMORYLOBBY_GRANT.md:42` | ❌ 当前 `MailCommand` 的 `_itemDict` 只注册 2/3/4/13，type 8 被拒。改用 `POST /api/admin/mail/send` 的 `{"Type":"MemoryLobby"}` |
| `MemoryLobbies` 只能靠包裹写入 | 同上 `:64-70` | ✅ 仍然成立（`AddMemoryLobbies` 是 GM 侧旁路，不是运行时路径） |
| `/api/admin/command` 是 `GM/CommandController` | — | ❌ 那是空壳（`GM/CommandController.cs:38` 只回显），真正的执行端点在 `ManagementController.RunCommand` |
