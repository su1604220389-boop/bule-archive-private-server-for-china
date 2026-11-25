# 玩家等级 UI 故障取证（2026-11-18）

> 只读：未改 .cs、未编译、未部署、未碰服务器/手机
> 主证据源：`work\ba\srv_src\Shittim-Server\`、`work\ba\data\ExcelDB.db`、`work\ba\proto\dto_schema_full_v2.json`
> 标注：**[已证实]** 代码/数据直接读到；**[推断]** 由行为推出未实测；**[未证实]** 需抓包/SQL 才能定

---

## A. 「等级」这个数字从哪来

### A1. DB 列 + 初值（**不是写死，构造函数给 1**）

```csharp
// Schale\Data\GameModel\UserModel\AccountDB.cs:148-149
148  public int Level { get; set; }
149  public long Exp { get; set; }
```
```csharp
// 同文件 :120-124  新账号构造函数
120  public AccountDBServer(long publisherId) : this()
122      PublisherAccountId = publisherId;
123      State = AccountState.Normal;
124      Level = 1;                      // ★ 新号 = 1 级（设计如此）
```
**⇒ 新号 Level=1 是正常设计，不是 bug。** `[已证实]`

### A2. 唯一会让 Level 增长的路径

```csharp
// Services\ParcelResolver.cs:273-284
273  public async Task UpdateAccountExp(ParcelResult parcel, List<AccountLevelExcelT> accountLevelExcels)
275      if (parcel.Amount <= 0) return;
277      var (level, exp, newbieExp, actionPointChargeMax) = MathService.CalculateAccountExp(Account.Level, Account.Exp, parcel.Amount, accountLevelExcels);
278      if (Account.Level != level && actionPointChargeMax > 0)
279          await UpdateAccountCurrency(new ParcelResult(ParcelType.Currency, (long)CurrencyTypes.ActionPoint, actionPointChargeMax));
281      Account.Level = level;          // ★ 全工程唯一"加经验/升级"的地方
282      Account.Exp   = exp;
```
派发入口：
```csharp
// Services\ParcelHandler.cs:117-118
117  case ParcelType.AccountExp:
118      await parcelResolver.UpdateAccountExp(parcel, _accountLevelExcels);
```

**谁会发 `ParcelType.AccountExp`（全工程 7 处，全部是"通关/扫荡"）：**

| 位置 | 场景 |
|---|---|
| `Services\ConcentrateCampaignManager.cs:674` | **主线战术关通关结算**（= 用户现在卡住进不去的那个流程） |
| `Managers\CampaignManager.cs:150`、`:207` | 关卡/子关结算 |
| `Services\EventContentCampaignManager.cs:116`、`:191`、`:459` | 活动关结算 |
| `Managers\WeekDungeonManager.cs:209` | 悬赏/特别依赖 |
| `Core\NetworkProtocol\Handlers\ContentSweepHandler.cs:95`、`:160`、`:204` | 扫荡 |

**⇒ Level 停在 1 的直接原因：账号从未收到过 `ParcelType.AccountExp` 包裹 —— 也就是"从没成功通关过一次"。** `[已证实·代码路径]`
与本轮"战斗进不去/黑屏"是**同一个根因的两面**，等级低是结果不是原因。

### A3. 其它会写 Level 的地方（都不是日常路径）

```csharp
AccountHandler.cs:987     account.Level = 1;                    // Account_Reset（重置账号）
ManagementController.cs:179  if (request.Level.HasValue) a.Level = request.Level.Value;   // 管理端直改
Commands\AccountDataCommand.cs:72  account.Level = accountAuthData.AccountDB.Level;       // 导入存档
```

⚠ **`ManagementController.cs:179` 只写 `Level`、不写 `Exp`** ⇒ 用它把等级改高后，`Exp` 仍是旧值，升级判定会错乱（`MathService` 按 level+exp 一起算）。**若之前有人用管理端改过等级，这就是"等级显示 1 但内部不一致"的一个来源。** `[已证实]`

### A4. 登录时 Level 是原样带出的吗？—— 是

```csharp
// AccountHandler.cs:158  Account_Auth(1002)
158  response.AccountDB = _mapper.Map<AccountDB>(account);
```
`AccountDB` 里 `Level`/`Exp` 直接来自 `AccountDBServer`，**没有任何二次加工**。`[已证实]`
（`Account_LoginSync` 历史上**不带 AccountDB**，只有 `AccountLevelRewardIds`，见 `:606` —— 与之前核对上游的结论一致。）

---

## B. 点击等级弹出的那个页面

### B1. 走哪个协议

| 协议 | 位置 | 作用 |
|---|---|---|
| `Account_CheckAccountLevelReward` | `AccountHandler.cs:688-702` | 查"已领取的等级奖励 id" |
| `Account_ReceiveAccountLevelReward` | `:704-747` | 领取 `Level <= account.Level` 的等级奖励 |

```csharp
// AccountHandler.cs:696-700
696  var rewardIds = db.GetAccountLevelRewards(account.ServerId)   // ★ 只查"已领取"（DB 表）
697      .Select(r => r.RewardId)
700  response.AccountLevelRewardIds = rewardIds;
```
```csharp
// AccountHandler.cs:716-718
716  var availableRewards = _excelService.GetTable<AccountLevelRewardExcelT>()
717      .Where(r => r.Level <= account.Level && !claimedIds.Contains(r.Id))
```
另外登录同步也带这个列表：
```csharp
// AccountHandler.cs:606  Account_LoginSync
606  response.AccountLevelRewardIds = db.GetAccountLevelRewards(account.ServerId).Select(r => r.RewardId).ToList();
```
客户端 DTO 侧也确认这个字段挂在 `AccountLoginSyncResponse` 上（`dto_schema_full_v2.json:3846` 与 `:4332`，均属 `AccountLoginSyncResponse`，定义在 `:3562`）。`[已证实]`

### B2. 需要哪些 Excel 表 / 有没有数据

| 表 | 服务端 ExcelDB（`work\ba\data\ExcelDB.db`）行数 | 判定 |
|---|---|---|
| `AccountLevelExcelT`（等级 → 升级所需经验、AP 回复上限等） | **90 行**（Id 1..90） | ✅ 有数据 |
| `AccountLevelRewardExcelT`（等级奖励） | **仅 6 行**（Level = 30 / 40 / 45 / 50 / …） | ⚠ **1 级账号可领列表必为空** |

`[已证实·数据]`（`select count(*)` 实测：`AccountLevelDBSchema`=90、`AccountLevelRewardDBSchema`=6）

### B3. 缺行时返回什么

- 表**不缺**（90 行在），所以不会抛异常。
- `Account_CheckAccountLevelReward` 对 1 级账号返回 **空数组**（`:696-700` 查不到已领取记录 ⇒ `[]`）。
- `Account_ReceiveAccountLevelReward` 对 1 级账号返回 `availableRewards = []` ⇒ 走 `else` 分支（`:731-738`）只回 `AccountDB` + `AccountCurrencyDB`，**无 parcel**。

---

## C. 「填充块」+「卡死」的可能成因（按可能性排序）

| 排序 | 假设 | 证据强度 |
|---|---|---|
| **1** | **等级页奖励列表本来就该是空的**：唯一 6 条奖励全部要求 `Level ≥ 30`，1 级账号一条都没有 ⇒ 客户端渲染"空网格/占位框" | **已证实（数据）** + 客户端渲染表现 **推断** |
| **2** | **"信息是假的" = Level 1 / Exp 0 就是真值**，只是用户以为异常；根因是**从没通关过**（战斗进不去）⇒ 无 AccountExp | **已证实（代码路径）** |
| **3** | **服务端只回"已领取"而非"可用"**：官方若回"可用奖励 id 列表"，客户端可能拿它当索引用；Shittim 回已领取集合，语义可能相反 | **推断**（需抓官方包对照） |
| **4** | **客户端本地化/表缺失**：`填充块`（豆腐块/占位）在 BA 里通常是**客户端 TableBundle 缺文本 key**，服务端完全不发文本 ⇒ 与 Shittim 无关，属客户端资源问题 | **推断** |
| **5** | 卡死是客户端在等级页发起的某个请求**没有响应**或被判会话失效（`Session expired or invalid`）⇒ 页面等回调 | **未证实**（需抓包） |

### 我的判断（一句话）

> **等级"一直 1"不是等级系统坏了，而是"从来没通关过一次"——`ParcelType.AccountExp` 只在通关/扫荡结算时发，而当前战斗卡在黑屏，所以经验永远是 0、等级永远是 1。等级页里的"填充块"和"卡死"更可能是客户端在为"空奖励列表 + 缺失本地化 key"做渲染，属于这个链条的下游表现。**

**但"卡死"我标 `未证实`**：如果是页面等一个不返回的协议，那就与 Shittim 有直接关系，必须抓包才能定。

---

## D. 一锤定音：还需要看什么

### D1. 抓一次"点击等级"的协议（最关键，能直接定 C1 vs C5）

桥日志（`/www/wwwroot/bapatch/logs/`）或 Shittim 日志里，点等级前后应出现：
```
Account_CheckAccountLevelReward          ← 若有请求、且有响应 ⇒ 服务端没卡，问题在客户端渲染
                                         ← 若请求发出但无响应/超时 ⇒ 服务端异常（查堆栈）
                                         ← 若压根没请求 ⇒ 客户端在本地就崩了（与服务器无关）
```
Shittim 侧关键字：`Account_CheckAccountLevelReward`、`Exception`、`Session expired or invalid`。

### D2. 两条 SQL（在服务器 `shittim.sqlite3` 上只读）

```sql
-- ① 账号真实等级/经验（判断是否真的从没涨过）
SELECT ServerId, Nickname, Level, Exp, LastConnectTime FROM Accounts ORDER BY ServerId;

-- ② 等级奖励领取记录（应为空，因为 1 级拿不到任何奖励）
SELECT * FROM AccountLevelRewards WHERE AccountServerId = 2;

-- ③ 如果 ① 里 Exp 明显 > 0 但 Level 还是 1 ⇒ 升级计算坏了（那种才是真 bug）
```

### D3. 一次对照实验（最快验证"经验发得出去"）

用管理端给该账号跑一次会发 exp 的操作，然后立刻看 `Accounts.Exp` 有没有变：
```sql
-- 操作前
SELECT Level, Exp FROM Accounts WHERE ServerId=2;
-- 管理端执行：POST /api/admin/command {"Uid":2,"Command":"givesweep"} 或直接打一场 1-1 并通关
-- 操作后
SELECT Level, Exp FROM Accounts WHERE ServerId=2;
```
- **Exp 涨了** ⇒ 等级系统正常，问题纯粹是"没通关过" ⇒ 去修黑屏。
- **Exp 不涨** ⇒ 结算链没走到 `ConcentrateCampaignManager.cs:674`，是战斗结算的真 bug。

### D4. 等级奖励表行数对照（判断"填充块"）

```sql
-- 服务端只有 6 行，看一下都是哪些等级
SELECT Id, Level FROM AccountLevelRewardDBSchema ORDER BY Level;
```
若客户端等级页按"每 10 级一档"渲染（1..90 共 9 档）而服务端只有 6 条（30/40/45/50/…），**列表长度对不上** ⇒ 客户端可能渲染占位/异常。这条能解释"填充块"但不解释"卡死"。

---

## E. 附：本次取证用到的关键行号速查

| 事 | 文件:行 |
|---|---|
| 新号 Level=1 | `Schale\Data\GameModel\UserModel\AccountDB.cs:124` |
| Level/Exp 列 | 同文件 `:148-149` |
| 唯一升级路径 | `Services\ParcelResolver.cs:273-294`（`Account.Level = level` 在 `:281`） |
| AccountExp 派发 | `Services\ParcelHandler.cs:117-118` |
| 主线通关发经验 | `Services\ConcentrateCampaignManager.cs:674` |
| 账号重置清等级 | `Core\NetworkProtocol\Handlers\AccountHandler.cs:987` |
| 管理端直改等级（不改 Exp） | `Controllers\ManagementController.cs:179` |
| 查等级奖励 | `AccountHandler.cs:688-702` |
| 领等级奖励 | `AccountHandler.cs:704-747` |
| 登录同步带奖励列表 | `AccountHandler.cs:606` |
| Account_Auth 带 AccountDB | `AccountHandler.cs:158` |
| 升级计算 | `Services\MathService.cs:50-83` |
| Excel 行数 | `AccountLevelDBSchema`=90、`AccountLevelRewardDBSchema`=6 |
