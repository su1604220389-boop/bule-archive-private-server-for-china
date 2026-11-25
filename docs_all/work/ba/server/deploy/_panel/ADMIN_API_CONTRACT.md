# Shittim 内置 Admin API 契约（源码实测）

> 取证：`C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\srv_src\`（`Shittim-Server/` 主工程，`Schale/` 依赖库）
> 纪律：**只读源码，未改任何 .cs、未编译、未上传**
> 标注：`[源码确证]` = 直接读到代码；`[推断]` = 由代码行为推出、未跑过

---

## 0. 前缀、鉴权、总览

| 项 | 结论 | 依据 |
|---|---|---|
| 路由前缀 | **就是 `/api/admin`，没有额外的 `UsePathBase`** | `GameServer.cs:244` `app.MapControllers();`（全工程 grep `UsePathBase` = 0 命中）；两个 Controller 都是 `[Route("api/admin")]`（`AdminController.cs:13`、`ManagementController.cs:25`） |
| 其它路由 | 只有 `/health`（`GameServer.cs:243`）和 `BannerController`（`BannerController.cs:5` 注释说明） | — |
| 鉴权 | **两个 Controller 类上都挂了 `[AdminAuth]`**（`AdminController.cs:14`、`ManagementController.cs:26`）⇒ **全部端点都受保护** | 同左 |
| 免密钥条件 | **环回地址直接放行**（`127.0.0.1` / `::1` / `::ffff:127.0.0.1`） | `AdminAuthAttribute.cs:31-32`、`:65-75` |
| 远程访问 | 必须带 `X-Admin-Key`，值取 `SHITTIM_ADMIN_API_KEY` 环境变量，否则取 `Config.ServerConfiguration.AdminApiKey`；比较用 `FixedTimeEquals` | `AdminAuthAttribute.cs:45-62` |
| 失败响应 | `403 { error: "..." }`；未配置 key 时错误文案会提示去设 `AdminApiKey` | `AdminAuthAttribute.cs:34-42` |
| 绑定地址 | `ManagementController` 与 `AdminController` **同前缀、不同控制器** ⇒ 路径不冲突（前者没有 `mail/send`、后者没有 `status`） | 两端点表对照 |

**⇒ 面板只要跑在** `127.0.0.1`**上（同机反代），就不需要 key；跨机必须配 `SHITTIM_ADMIN_API_KEY`。**

---

## 1. 端点契约表

### 1.1 `AdminController`（4 个，`AdminController.cs`）

| 方法 | 路径 | 请求 | 响应 | 读/写 |
|---|---|---|---|---|
| POST | `/api/admin/mail/send` | `SendMailRequest` | `{ success, message }` / 404 `{error}` / 400 `{error}` | **写** |
| POST | `/api/admin/currency/set` | `SetCurrencyRequest` | `{ success, message }` / 404 / 400 | **写** |
| GET | `/api/admin/accounts` | — | `[{ ServerId, Nickname, Level, Exp, Comment }]` | 读 |
| GET | `/api/admin/account/{serverId}/currencies` | — | `{ "<CurrencyTypes名>": <long>, ... }`（直接吐 `CurrencyDict`） | 读 |

**`SendMailRequest`**（`AdminController.cs:159-173`，原样）：
```csharp
public class SendMailRequest
{
    public long AccountServerId { get; set; }
    public string? Sender { get; set; }
    public string Comment { get; set; } = "";
    public List<ParcelRequest> Parcels { get; set; } = new();
    public DateTime? ExpireDate { get; set; }
}
public class ParcelRequest
{
    public string Type { get; set; } = "";   // ★ 字符串，Enum.Parse<ParcelType>(Type)
    public long Id { get; set; }
    public long Amount { get; set; }
}
```
**`SetCurrencyRequest`**（`AdminController.cs:175-180`）：
```csharp
public class SetCurrencyRequest
{
    public long AccountServerId { get; set; }
    public long CurrencyType { get; set; }   // ★ 数字（(CurrencyTypes)request.CurrencyType）
    public long Amount { get; set; }
}
```
⚠ **`currency/set` 对 Gem 有特殊处理**（`AdminController.cs:79-86`）：`CurrencyType==4(Gem)` 时它把 `GemBonus=Amount`、`GemPaid=0` 再写 `Gem`，**最后 `UpdateGem` 重算**；直接写 `Gem` 会被丢弃。用 `GemBonus(3)` 或 `GemPaid(2)` 更直白。

⚠ **`GET /admin/accounts` 过滤 `DevId == null`**（`AdminController.cs:109`）——把 AI 账号排除，但**也说明它不返回 `DevId`/`PublisherAccountId`**（见 §4）。

### 1.2 `ManagementController`（24 个，`ManagementController.cs`，1253 行）

**只读（11）**

| 方法 | 路径 | 响应形状 | 依据 |
|---|---|---|---|
| GET | `/api/admin/status` | `{ service, gameVersion, versionId, apiPort, gatewayPort, gatewayEnabled, useEncryption, bypassAuthentication, useCustomExcel, accountCount, startedAtUtc, uptimeSeconds }` | `:51-72` |
| GET | `/api/admin/account/{serverId}/detail` | `{ ServerId, Nickname, CallName, Level, Exp, Comment, State(字符串), VIPLevel, PublisherAccountId, RepresentCharacterServerId, CreateDate, LastConnectTime, currencies, itemCount, characterCount, mailCount }` | `:75-105` |
| GET | `/api/admin/account/selected` | `{ selectedAccountId }` | `:243-247` |
| GET | `/api/admin/account/{serverId}/items` | `[{ ServerId, UniqueId, StackCount, name, icon }]` | `:267-283` |
| GET | `/api/admin/account/{serverId}/characters` | `[{ ServerId, UniqueId, StarGrade, Level, FavorRank, devName, name }]` | `:347-368` |
| GET | `/api/admin/account/{serverId}/mails` | `[{ ServerId, Sender, Comment, Type, SendDate, ReceiptDate, ExpireDate, collected, parcels:[{type,id,amount}] }]` | `:370-394` |
| GET | `/api/admin/static/items?search=&limit=300` | `[{ id, name, icon, quality, stackMax }]`（limit 截到 1..2000） | `:474-498` |
| GET | `/api/admin/static/characters?search=&limit=500` | `[{ id, name, devName, defaultStar, maxStar }]`（只出 `IsPlayable && !IsNPC && !IsDummy`） | `:500-525` |
| GET | `/api/admin/static/equipment?search=&limit=500` | `[{ id, name, icon, tier, maxLevel }]` | `:527-550` |
| GET | `/api/admin/static/currencies` | `[{ id, name }]`（枚举，排除 `Invalid`/`Max`） | `:552-559` |
| GET | `/api/admin/meta/parceltypes` | `[{ id, name }]`（排除 `None`） | `:561-568` |
| GET | `/api/admin/gacha/config` | `{ path, exists, ssr, sr, r, guaranteed }` | `:579-604` |
| GET | `/api/admin/gacha/banners` | `banners`（数组） | `:640-661` |
| GET | `/api/admin/events/seasons` | `{ ... }`（活动赛季） | `:664-712` |
| GET | `/api/admin/events/schedule` | `{ events, enabled:[...] }` | `:765-833` |
| GET | `/api/admin/events/{eventContentId}/unlocks` | `{ ... }`（该活动解锁状态） | `:855-903` |
| GET | `/api/admin/notice` | `{ ... }`（当前公告/维护旗标） | `:727-739` |

**写（13）**

| 方法 | 路径 | 请求体 | 响应 | 依据 |
|---|---|---|---|---|
| POST | `/api/admin/account/create` | `CreateAccountRequest { Nickname="Sensei", CallName? }` | `{ success, serverId, nickname }` | `:108-150` |
| POST | `/api/admin/account/update` | `UpdateAccountRequest { ServerId, Nickname?, CallName?, Comment?, Level?, Exp?, VIPLevel? }` | `{ success }` | `:152-186` |
| POST | `/api/admin/account/delete` | `DeleteAccountRequest { ServerId }` | `{ success }` | `:196-235` |
| POST | `/api/admin/account/select` | `SelectAccountRequest { ServerId }` | `{ success, selectedAccountId }` | `:249-265` |
| POST | `/api/admin/items/give` | `GiveItemRequest { AccountServerId, UniqueId, Amount=1, SetExact=false }` | `{ success }` | `:285-316` |
| POST | `/api/admin/items/remove` | `RemoveItemRequest { AccountServerId, UniqueId }` | `{ success }` | `:324-339` |
| POST | `/api/admin/mail/delete` | `DeleteMailRequest { AccountServerId, MailServerId?, ClearAll=false }` | `{ success, deleted }` | `:396-415` |
| POST | `/api/admin/command` | `RunCommandRequest { Uid, Command }` | `{ success, output }` / 400 | `:423-466` |
| POST | `/api/admin/gacha/config` | `SetGachaConfigRequest { Ssr, Sr, R, Guaranteed?, ClearRates=false }` | `{ success, path }` | `:606-632` |
| POST | `/api/admin/notice` | `SetNoticeRequest { Flags, GateError, GateMessage? }` | `{ success }` | `:741-757` |
| POST | `/api/admin/events/schedule` | `SetEventScheduleRequest { Enabled?: List<long> }` | `{ success, rows, enabled }` | `:836-847` |
| POST | `/api/admin/events/unlock` | `EventUnlockRequest { AccountServerId, EventContentId, ClearStages, CompleteMissions, ResetShop, UnlockCollections, UnlockMinigame, ClearMinigames, Currency?: {id:amount} }` | `{ success, stages, missions, shop, collections, items, minigame, minigameStages }` | `:916-1167` |

**`Command` 端点细节**（`:431-466`）：
```csharp
437  var parts = request.Command.Trim().Split(' ', StringSplitOptions.RemoveEmptyEntries);
438  var name = parts.First().TrimStart('/', '!', '.', '*').Split('/').Last();   // 支持 "!give" / "/give" / "give"
450  cmd = CommandFactory.CreateCommand(name, connection, args);
460  await cmd.Execute();
466  return Ok(new { success = true, output = ... });
```

---

## 2. `mail/send` 链路是否安全（**关键**）

### 2.1 调用链（`[源码确证]`）

```
POST /api/admin/mail/send                               AdminController.cs:31-60
 └─ Enum.Parse<ParcelType>(p.Type)                      AdminController.cs:41
 └─ _mailManager.SendSystemMailMultipleParcels(...)      AdminController.cs:46-52
     └─ SendSystemMail(...)                              MailManager.cs:76-90 → :25-53
         └─ new MailDBServer { ... ParcelInfos = parcelInfos, RemainParcelInfos = [] }
         └─ context.Mails.Add(mail); SaveChangesAsync()  MailManager.cs:46-47
         └─ MailNotificationService.MarkNewMail(...)     MailManager.cs:50
```

### ★ 结论：`mail/send` **只写邮件行，不走 `ParcelResolver`**

`MailManager.cs:34-47` 只是构造 `MailDBServer` 并 `Add`，**没有任何 `_parcelHandler` / `ParcelResolver` 调用**。
`_parcelHandler` 在 `MailManager` 里**只在 `ReceiveMail` 用**：

```
Mail_Receive（客户端领取）
 └─ MailManager.ReceiveMail(...)                         MailManager.cs:92-118
     └─ ParcelResult.ConvertParcelResult(mail.ParcelInfos)   :108
     └─ _parcelHandler.BuildParcel(context, account, parcelResults, parcelResultDb)   :111
         └─ ParcelResolver.UpdateAccountCurrency(type, amount, ...)   ← ★ GEMGRANT 打在这里
```

### 2.2 GEMGRANT 补丁是否生效

补丁位置 **`ParcelResolver.cs:132-149`**（原文）：
```csharp
132  // >>> BAPATCH-GEMGRANT v1 BEGIN >>>
133  // Gem is derived (Gem = GemBonus + GemPaid) and UpdateGem() rewrites it right below, so a
134  // grant that lands on CurrencyTypes.Gem is silently discarded. Route grants to GemBonus.
135  if (IsConsume && type == CurrencyTypes.Gem)
137      accountCurrencyDB.SubtractGem(amount, dateTime);
139  else if (type == CurrencyTypes.Gem)
141      accountCurrencyDB.UpdateCurrency(CurrencyTypes.GemBonus, amount, dateTime);
143  else
145      accountCurrencyDB.UpdateCurrency(type, amount, dateTime);
148  accountCurrencyDB.UpdateGem(dateTime);
149  // <<< BAPATCH-GEMGRANT v1 END <<<
```

⇒ **`mail/send` 发的 `Currency + Id=4(Gem)` 会在客户端"领取邮件"时走这段**，即 `GemBonus += Amount`，随后 `UpdateGem()` 重算 `Gem = GemBonus + GemPaid`。**补丁在链路上，没有被绕过。** `[源码确证]`（静态链路；未实跑）

> ⚠ **唯一例外**：`POST /admin/currency/set` 的 `CurrencyType=4` 走的是 `AdminController.cs:79-86` 的**手工分支**（写 `GemBonus=Amount, GemPaid=0`），**不经过** `ParcelResolver`，但效果等价。

### 2.3 `ParcelType` 全表（`Schale/FlatData/ParcelType.cs:8`，31 项）

| id | name | id | name | id | name |
|---|---|---|---|---|---|
| 0 | None | 11 | FavorExp | 22 | Sticker |
| 1 | Character | 12 | TSS | 23 | Costume |
| 2 | **Currency** | 13 | Furniture | 24 | PossessionCheck |
| 3 | Equipment | 14 | ShopRefresh | 25 | BattlePassExp |
| 4 | **Item** | 15 | LocationExp | 26 | SelectedCharacter |
| 5 | GachaGroup | 16 | Recipe | 27 | UnSelectedCharacter |
| 6 | Product | 17 | CharacterWeapon | 28 | ProductBattlePass |
| 7 | Shop | 18 | ProductMonthly | 29 | ProductSelect |
| 8 | **MemoryLobby** | 19 | CharacterGear | 30 | SNSPost |
| 9 | AccountExp | 20 | IdCardBackground | 31 | ProductDailyRecord |
| 10 | CharacterExp | 21 | Emblem | | |

**发青辉石的邮件体**（`[源码确证]` 形状）：
```json
{"AccountServerId":2,"Sender":"Plana","Comment":"补偿","Parcels":[{"Type":"Currency","Id":4,"Amount":1200}]}
```
> `Type` 必须是**枚举名**（`"Currency"`，不是 `"2"`）——`Enum.Parse<ParcelType>` 默认不认数字串以外的别名，传 `"2"` 也能过（`Enum.Parse` 接受数字字符串），但**大小写敏感**。`Id` 填 `CurrencyTypes` 的数值（Gem=4/Gold=1/AP=5）。
> `MemoryLobby`（8）的 `Amount` **必须 ≥1**（0 会被 MomoTalk/包裹链路当无效，见 `SHITTIM_ROOT_PLAN` 的踩坑记录）。

---

## 3. `CurrencyTypes` 全表（`Schale/FlatData/CurrencyTypes.cs:8`，0–30）

| id | name | id | name | id | name |
|---|---|---|---|---|---|
| 0 | Invalid | 11 | WeekDungeonBloodTicket | 22 | ChaserTotalTicket |
| **1** | **Gold** | 12 | WeekDungeonChaserBTicket | 23 | SchoolDungeonTotalTicket |
| **2** | **GemPaid** | 13 | WeekDungeonChaserCTicket | 24 | EliminateTicketA |
| **3** | **GemBonus** | 14 | SchoolDungeonATicket | 25 | EliminateTicketB |
| **4** | **Gem**（派生=2+3） | 15 | SchoolDungeonBTicket | 26 | EliminateTicketC |
| **5** | **ActionPoint** | 16 | SchoolDungeonCTicket | 27 | EliminateTicketD |
| 6 | AcademyTicket | 17 | TimeAttackDungeonTicket | **28** | **CafeSummonTicket1** |
| 7 | ArenaTicket | 18 | MasterCoin | **29** | **CafeSummonTicket2** |
| 8 | RaidTicket | 19 | WorldRaidTicketA | 30 | Max |
| 9 | WeekDungeonChaserATicket | 20 | WorldRaidTicketB | | |
| 10 | WeekDungeonFindGiftTicket | 21 | WorldRaidTicketC | | |

> **`Gem` 是派生值**：写 `Gem` 会被 `UpdateGem()` 覆盖 ⇒ 用 `GemBonus(3)`（免费石）或 `GemPaid(2)`（付费石）。`currency/set` 的 `CurrencyType=4` 已内置等价处理（`AdminController.cs:79-86`）。

---

## 4. `AccountServerId` ↔ 设备/卡密的映射

### 4.1 `AccountDBServer` 的身份字段（`Schale/Data/GameModel/UserModel/AccountDB.cs:141-161`）

```csharp
141  public long ServerId { get; set; }          // ★ 所有协议里的 AccountServerId
143  public string Nickname { get; set; }
144  public string? CallName { get; set; }
145  public string? DevId { get; set; }          // ★ 存在！但 admin/accounts 不返回
146  public long? PublisherAccountId { get; set; }  // ★ 桥传来的 publisherId
147  public AccountState State { get; set; }
148  public int Level ...
150  public string? Comment ...
152  public long RepresentCharacterServerId ...
153  public long MemoryLobbyUniqueId ...
154  public DateTime LastConnectTime ...
156  public DateTime CallNameUpdateTime ...
158  public int? VIPLevel ...
159  public DateTime CreateDate ...
160  public int? UnReadMailCount ...
```

### 4.2 Shittim 怎么把 `EnterTicket` 变成 `PublisherAccountId`（`AccountHandler.cs:52-89`，原文）

```csharp
52  [ProtocolHandler(Protocol.Account_CheckNexon)]
58      var ticketBytes  = Convert.FromBase64String(request.EnterTicket);
59      var ticketString = Encoding.UTF8.GetString(ticketBytes);
60      var parts        = ticketString.Split('/');
62      var publisherId  = long.Parse(parts[0]);      // ★ 票据 = base64("<publisherId>/<token>")
63      var token        = parts[1];
65      var user = await db.UserAccounts.FirstOrDefaultAsync(u => u.NpSN == publisherId);
68      if (user == null)                             // ★ 首次登录：自动建号
70          var newUser = new UserAccount { Uid = -1, NpSN = publisherId, NpToken = token };
76          db.UserAccounts.Add(newUser);
78          var newAccount = new AccountDBServer(publisherId);   // PublisherAccountId = publisherId
79          db.Accounts.Add(newAccount);
86          user.Uid = account.ServerId;
87          await AccountInitializationService.InitializeCompleteAccount(db, account);
90      else if (user.NpToken != token) { ... }       // token 变了会走另一分支
```

⇒ **`ServerId` 是自增主键，`PublisherAccountId` 才是外部身份**；两者**不是同一个数**（建号时 `AccountDBServer(publisherId)` 把 publisher 存进去，`ServerId` 由 EF 分配）。
⇒ 桥的 `ENTER_TICKET = base64("<UID>/<TOKEN>")` 里 **`UID` 就是 `PublisherAccountId`**，`TOKEN` 是 `UserAccounts.NpToken`（**变了会被判 token 不匹配**，见 `:90`）。

### 4.3 桥现在传的 `PublisherId` 是怎么算的

| 层 | 现状 | 依据 |
|---|---|---|
| 卡密 SDK | `User.ID = md5(card)[:8] → 100000000..999999999` | `bapatch\sdkcard.py:43` |
| 桥常量 | `UID='314816420'` / `TOKEN='61de1d1b…'` / `ENTER_TICKET=base64(UID+"/"+TOKEN)` | `_bridge_ref\account_auth_probe.py:62-64` |
| 实测印证 | `md5('11111111111')[:8] → 314816420` = 硬编码 UID | 本轮实算 |
| 分流层 | `acct_apply_to_auth` 会覆盖 `AccountDB`/`SessionKey`，但**只在能拿到 DevId 时成功** | `_baseline\account_auth_probe.py:98-124`（详见 `_multiplayer\MULTIPLAYER_DESIGN_20261117.md` §0） |

### 4.4 ★ `/api/admin/accounts` 有没有 `PublisherAccountId` / `DevId`？

**没有。**（`AdminController.cs:108-118` 只 select `ServerId/Nickname/Level/Exp/Comment`）

**但是有两条现成的替代路径**：
1. **`GET /api/admin/account/{serverId}/detail` 返回 `PublisherAccountId`**（`ManagementController.cs:97`）⇒ 面板可以"列表拿 `accounts`，逐个拿 `detail` 补映射"（N+1 次调用，玩家量小可接受）。
2. **一处 1 行改动**即可让列表直出（**只给方案，未改**）：
   ```csharp
   // AdminController.cs:110-117 的 Select 里加两行
   a.PublisherAccountId,
   a.DevId,
   ```
   ⚠ 注意 `:109` 的 `Where(a => a.DevId == null)` 会把有 DevId 的账号过滤掉 —— 若要让面板看到"卡密玩家"，这行过滤**必须一起改**（否则加了字段也永远看不到人）。

---

## 5. 封号怎么做

### 5.1 `AccountState` 全表（`Schale/FlatData/AccountState.cs:8`）

```csharp
WaitingSignIn = 0,
Normal        = 1,
Dormant       = 2,
Comeback      = 3,
Newbie        = 4,
```

### 5.2 有没有现成的 ban/unban 逻辑？**没有。**

`[源码确证]` 全工程 grep：
- `AccountState.Normal` 只出现在**赋值**处（`AccountDB.cs:123`、`GameClientHelper.cs:25`、`AronaAI.cs:55`）
- 其它 `.State ==` 命中全是 **EF 的 `EntityState`**（`AcademyHandler.cs:214`、`ParcelResolver.cs:530`），与账号状态无关
- **没有任何 `if (account.State != Normal) reject` 之类的门禁**
- **没有 ban/unban 端点，也没有 `BanReason`/`BanUntil` 字段**

⇒ **`State` 目前是个纯装饰字段**，改成任何值客户端都不受影响、也不会被踢。

### 5.3 封了之后客户端表现

**目前不存在"封了"这个状态** ⇒ `[推断]` 即使把 `State` 改成 `Dormant`，`Account_CheckNexon` 也不检查它，玩家照常登录。

### 5.4 最小改动方案（**只给方案，未动源码**）

**A. 加一个真正的封禁值（推荐，2 处）**
```csharp
// 1) Schale/FlatData/AccountState.cs: 枚举末尾追加
Banned = 5,
```
```csharp
// 2) Shittim-Server/Core/NetworkProtocol/Handlers/AccountHandler.cs: CheckNexon 拿到 account 之后（约 :89-95）
if (account.State == AccountState.Banned)
    throw new InvalidOperationException("ACCOUNT_BANNED");   // 或返回明确的错误响应
```
**代价**：`State` 是**数据库列**（`AccountDBServer:147`）⇒ 已有行默认值不变，无需迁移。

**B. 不改枚举，只借用 `Dormant`（0 行新字段，1 处检查）**
```csharp
// AccountHandler.cs CheckNexon
if (account.State == AccountState.Dormant) throw new InvalidOperationException("ACCOUNT_SUSPENDED");
```
**风险**：`Dormant` 在原作语义是"休眠账号"（通常还应允许唤醒），语义被挪用；且**没有任何脚本/面板在写它**，需要先有 `account/update` 支持 `State`（当前 `UpdateAccountRequest` **没有 State 字段**，`ManagementController.cs:152-161`）。

**C. 最轻的"软封"：改 `NpToken`（0 处代码改动）**
把 `UserAccounts.NpToken` 改成随机值 ⇒ 该 publisher 下次登录走到 `AccountHandler.cs:90` 的 `user.NpToken != token` 分支（token 不匹配）。**只给方案，需确认 `:90` 之后的行为**（本次未读到该分支的完整实现，`[未确认]` 是拒绝还是覆盖）。

**⇒ 结论：没有任何"干净的"封号机制。** 最小可用改动 = **A（2 处，1 枚举值 + 1 判断）+ 让 `account/update` 接受 `State`**（第 3 处，`UpdateAccountRequest` 加 `AccountState? State`）。

---

## 6. `command` 端点与 GM 命令

### 6.1 `RunCommandRequest`（`ManagementController.cs:423-427`）

```csharp
public class RunCommandRequest
{
    public long Uid { get; set; }
    public string Command { get; set; } = "";
}
```

### 6.2 ★ `Uid` 是什么？—— **直接就是 `AccountServerId`，与"当前选中账号"无关**

```csharp
445  var connection = _webService.GetClient(request.Uid, writer);        // ManagementController.cs:445
```
```csharp
// Services/WebClient/WebConnection.cs:19-32
public WebClientConnection(..., long _accountServerId)
{
    ...
    AccountServerId = _accountServerId;      // ★ uid → AccountServerId 直通
}
```
⇒ 命令里的 `connection.AccountServerId` = `RunCommandRequest.Uid` ⇒ **每次调用自带目标账号，不需要先 `account/select`**。

**`account/select` 的语义是另一件事**（`ManagementController.cs:251` 注释原文）：
> `Which account the game logs into. Takes effect at the next Account_CheckNexon, no restart needed - GenerateSession reads it live.`
⇒ 它改的是 `Config.ServerConfiguration.SelectedAccountId`（`:262` + `Config.Save()`），**只影响"下一个登录的客户端落到哪个号"**，与 `command` 端点互不干扰。

### 6.3 能跑哪些命令（`Shittim-Server/Commands/`，22 个实现文件）

| 命令名 | 文件 | 典型参数 |
|---|---|---|
| `give` | `GiveCommand.cs` | `<parcelType> <id> <amount>`（或 `name`） |
| `giveall` | `GiveAllCommand.cs` | `[target]` |
| `giveequip` / `giveallequip` | `GiveEquipCommand.cs` / `GiveAllEquipCommand.cs` | `<equipId> [amount]` |
| `max` | `MaxCommand.cs` | `<all\|角色名>` |
| `currency` | `CurrencyCommand.cs` | `<currencyType> <amount>` |
| `character` | `CharacterCommand.cs` | 角色增删/星级 |
| `addeleph` | `AddElephCommand.cs` | `<characterId> <amount>` |
| `inventory` / `listitem` / `checkitem` / `clearinventory` | 同名文件 | 查询/清背包 |
| `mail` | `MailCommand.cs` | 发信 |
| `accountdata` | `AccountDataCommand.cs` | `list\|load\|export`（**导入导出整包存档，含 MemoryLobbies**） |
| `setaccount` | `SetAccountCommand.cs` | `level\|nickname\|raidseasonid\|property` |
| `setseason` | `SetSeasonCommand.cs` | `total\|grand\|drill\|final <id>` |
| `setting` | `SettingCommand.cs` | `trackpvp\|usefinal\|bypassteam\|bypasssummon\|changetime` |
| `setraid` | `SetRaidCommand.cs` | 总力战参数 |
| `unlockall` | `UnlockAllCommand.cs` | `campaign\|story\|weekdungeon\|schooldungeon\|battlepass\|mission` |
| `unlockbattlepass` | `UnlockBattlePassCommand.cs` | — |
| `gacha` | `GachaCommand.cs` | 抽卡模拟 |
| `help` | `HelpCommand.cs` | 列命令 |
| — | `Command.cs` | 基类（`CommandFactory.CreateCommand(name, connection, args)`） |

> 调用格式：`{"Uid": 2, "Command": "giveall"}` / `{"Uid": 2, "Command": "max all"}` / `{"Uid": 2, "Command": "!currency GemBonus 5000"}`（`!` `/` `.` `*` 前缀都会被 `:438` 剥掉）

---

## 7. 结论：面板能做什么

### ✅ 能做的（纯 HTTP，无需改 C#）

| 能力 | 端点 | 依据 |
|---|---|---|
| 玩家列表 + 等级/经验/签名 | `GET /accounts` | `AdminController.cs:102-126` |
| 单人详情（含 `PublisherAccountId`、`State`、货币、计数） | `GET /account/{id}/detail` | `ManagementController.cs:75-105` |
| 背包/角色/邮件列表 | `GET /account/{id}/{items,characters,mails}` | `:267/:347/:370` |
| 改昵称/签名/等级/经验/VIP | `POST /account/update` | `:163-186` |
| 建号 / 删号 | `POST /account/create`、`/account/delete` | `:114`、`:198` |
| 发邮件（含青辉石/角色/道具/纪念大厅） | `POST /mail/send` | `AdminController.cs:31-60` |
| 直接改货币 | `POST /currency/set` | `AdminController.cs:62-100` |
| 发/删道具 | `POST /items/give`、`/items/remove` | `:293`、`:330` |
| 删邮件 | `POST /mail/delete` | `:403` |
| 跑任意 GM 命令（`giveall`/`max`/`unlockall`/`accountdata`…） | `POST /command`（`Uid`=目标 `ServerId`） | `:431-466` |
| 静态数据下拉框（道具/角色/装备/货币/包裹类型） | `GET /static/*`、`/meta/parceltypes` | `:474-568` |
| 抽卡概率、Banner、公告、活动开关/解锁 | `GET/POST /gacha/*`、`/notice`、`/events/*` | 见 §1.2 |
| 服务器状态 | `GET /status` | `:51` |

### ⚠️ 需要小改 C# 才能做的

| 需求 | 改动 | 规模 |
|---|---|---|
| 玩家列表直出 `PublisherAccountId`/`DevId`（卡密↔账号映射） | `AdminController.cs:110-117` 的匿名对象加 2 字段；**同时要放开 `:109` 的 `DevId == null` 过滤** | 3 行 |
| 封号 / 解封 | `AccountState` 加 `Banned=5`（1 行）+ `CheckNexon` 加判断（2-3 行）+ `UpdateAccountRequest` 加 `State?`（1 行 + 赋值 1 行） | 5-6 行，2 个文件 |
| 批量发奖幂等（`Comment` 存 batch_id） | 不需要改：`SendMailRequest.Comment` 已经是自由文本，面板自己塞 `batch_id` 即可 | 0 行 |
| 跨库读 `accounts.db`（认证库） | 不需要改：面板用 SQLite 只读连接 + `ATTACH` | 0 行 |

### ❌ 做不了的

| 需求 | 原因 | 依据 |
|---|---|---|
| 真正的封禁/踢下线 | 无 ban 语义、无 `State` 门禁、无踢人路径 | §5.2 |
| 把"卡密"直接映射到 `ServerId` | Shittim 里**没有卡密概念**，只有 `PublisherAccountId`/`DevId`；卡密→`PublisherAccountId` 的映射在**桥/SDK**，不在 Shittim | `AccountDB.cs:141-161` |
| 查询"某设备绑了几个号" | 同上，Shittim 只存 `DevId` 字符串，不存设备关系 | — |
| 观看/干预进行中的战斗 | 无相关端点 | 端点表已穷举 |

---

## 8. 面板接入建议（一句话版）

- **同机反代到 `127.0.0.1:<gatewayPort>`** ⇒ 免 `X-Admin-Key`，最省事；
- 跨机则设 `SHITTIM_ADMIN_API_KEY` 并带 `X-Admin-Key`；
- 发奖**优先 `POST /command` + `give`/`giveall`**（走 `ParcelResolver` 全链路），**次选 `mail/send`**（延迟到玩家领取时结算，青辉石经 GEMGRANT 正确入账）；
- 玩家身份映射：`GET /accounts` 拿列表 → 需要时 `GET /account/{id}/detail` 补 `PublisherAccountId`；或按 §4.4 改 3 行让列表直出。
