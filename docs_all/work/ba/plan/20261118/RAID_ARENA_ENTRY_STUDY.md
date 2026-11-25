# 总力战 / 大决战 / 战术对抗赛「进得去界面、进不了战斗」定位

> 作者：shittim-analyst　·　2026-11-18　·　**只读分析**（未改线上、未重启、未动数据库）
> 证据源：`work\ba\srv_live\20261118_2210\wire-2026-11-18.txt.gz`（Lead 已解析）+ `work\ba\srv_src\` 源码
> 标注：**【已证实】** = 源码/日志直接读到；**【推测】** = 由代码行为推出，未经客户端验证；**【无法证实】** = 服务端源码里没有对应逻辑

---

## 0. 结论速览

| # | 结论 | 强度 |
|---|---|---|
| 1 | **`RaidBattleDB.BIEchelon` 全工程从未被赋过值**（创建时即 `string.Empty`），而它是客户端重建队伍的信息块 | **【已证实·服务端侧】** 客户端是否必需 **【无法证实】** |
| 2 | `RaidMembers[0].CharacterId` 塞的是 **CharacterServerId(9)** 而不是 **UniqueId(13003)** —— 与刚修好的 ID 卡同一个 id 空间错误 | **【已证实】** |
| 3 | `ServerTimeTicks` 被覆写成**赛季开始时间 2021-10-14 12:30**（每条 raid 响应） | **【已证实】**；是否为断点 **【推测】** |
| 4 | 战术对抗赛的对手列表**第一条就是玩家自己**（`"Your Defense"`），且 wire 里 **22001/22002/22004 一次都没有** | **【已证实】**；客户端本地拦截 **【推测】** |
| 5 | 大决战与总力战 **同构**（同一 DTO 家族、同缺 `BIEchelon`、同样的 CharacterId 混用） | **【推测·高置信】**（未逐行读 EliminateRaid 的 EnterBattle） |

---

## A. `Raid_EnterBattle` 响应里哪些字段缺/错

### A1. `BIEchelon` —— **从未被写入过（最可疑）**

```csharp
// Schale\Data\GameModel\GameContentModel\RaidBattleDB.cs:26
26  public string BIEchelon { get; set; } = string.Empty;
```
全工程 grep `BIEchelon`（26 处命中）**全部是 DTO/模型定义或读取，没有一处赋值**：
`RaidBattleDB.cs:26`、`ContentSaveDB.cs:27-43`、`DBModel.cs:941-945`、`:1909`。
创建战斗行的唯一入口也没有写它：

```csharp
// Shittim-Server\Services\RaidManager.cs:196-210   CreateOrUpdateBattle
196  raidBattle = new()
198      AccountServerId = account.ServerId,
199      ContentType = ContentType.Raid,
200      RaidUniqueId = raidId,
201      CurrentBossHP = targetBoss.MaxHP100,
202      RaidMembers = [ new() { ... DamageCollection = new() } ]
210  };                                   // ← 没有 BIEchelon = ...，于是保持 string.Empty
```

**官方语义**：字段名 `BIEchelon`（Battle-Info Echelon）在官方包里是**序列化的队伍信息字符串**（客户端据此在战斗场景里重建上场学生）。
**⇒【已证实】**：服务端永远发 `""`。**【无法证实】**：客户端是否因此无法进入战斗（客户端逻辑不在本仓库）。
**但**：`""` 与"合法但空的序列化串"语义不同，客户端若做 `JsonConvert.DeserializeObject` 会抛/得到 null —— 这与"重发 83 次、每次都是 200 完整 JSON"的表现高度吻合（客户端拿到响应但进不去场景 ⇒ 重试）。

### A2. `RaidMembers[0].CharacterId` —— **id 空间用错（与 ID 卡同一个 bug）**

```csharp
// Shittim-Server\Services\RaidManager.cs:202-209
202  RaidMembers = [
204      AccountId = account.ServerId,
205      AccountName = account.Nickname,
206      CharacterId = account.RepresentCharacterServerId,   // ← 9（ServerId），应为 UniqueId（13003）
207      DamageCollection = new()
209  ],
```
`RaidMemberDescription.CharacterId` 在客户端世界里是**角色 UniqueId**（与 `CharacterDB.UniqueId` 同一空间）。
账号 2 的 `ServerId=9` 对应 `UniqueId=13003`（《莲见》）—— 传 9 客户端解析不到这个学生。
**【已证实】**（与 `FriendHandler` 已修的问题同源）。

### A3. `SubPartsHPs` / `CurrentBossHP` / `DamageCollection` 一致性

| 字段 | wire 实际 | 判定 |
|---|---|---|
| `RaidDB.RaidBossDBs[0].BossCurrentHP` | 50,000,000 | — |
| `RaidBattleDB.CurrentBossHP` | 50,000,000 | **与 RaidDB 一致 ✔** |
| `RaidBattleDB.RaidMembers[0].DamageCollection` | `[]` | 开战前为空**合理** ✔ |
| `RaidBattleDB.SubPartsHPs` | `[]` | 单部位 boss 可为空；多部位 boss 需要值 —— **【推测】**，wire 里该 boss（`CharacterStatExcel.MaxHP100`）没有部位数据 |

### A4. `AssistCharacterDB` 是否漏填

```csharp
// Shittim-Server\Core\NetworkProtocol\Handlers\RaidHandler.cs:212-218
212  if (request.AssistUseInfo != null)
214      response.AssistCharacterDB = RaidService.FinishingAssistCharacterInfo(...);
```
- DTO（`NetworkProtocol.cs:5999-6006`）有该字段，**handler 只在请求带 `AssistUseInfo` 时填**。
- wire 里 `Raid_EnterBattle` 请求若不带 `AssistUseInfo` ⇒ 响应 `AssistCharacterDB` 缺省 ⇒ **不是"漏填"，是条件填充**。
- 客户端是否要求非空：**【无法证实】**。若官方在不带助战时也回一个空对象，则需要改成 `new AssistCharacterDB()`；先不动。

---

## B. `ServerTimeTicks` 冻结到 2021-10-14 是不是断点？

### B1. 已证实的部分

```csharp
// Shittim-Server\Services\RaidManager.cs:26-31
26  public DateTime GetRaidTimeTicks(AccountDBServer account)
28      return DateTime.Parse(
29          raidSeasonExcels.FirstOrDefault(x => x.SeasonId == account.ContentInfo.RaidDataInfo.SeasonId).SeasonStartData
30      );
```
调用点：`RaidHandler.cs:209`（EnterBattle）、`:181`（CreateBattle）。
⇒ wire 里 `ServerTimeTicks=637698114000000000`（=2021-10-14 12:30）与此完全对应。

### B2. 客户端据此做什么 —— **无法从服务端源码证实**

服务端仓库里没有客户端的判断逻辑。能说的只有：
- 该值**落在** `RaidDB.Begin=2021-10-14T12:30` 与 `End=13:30` 之间 ⇒ 如果客户端做"赛季是否开放"的窗口校验，**这个时间反而是通过的**；
- 因此它更可能影响"剩余时间/结算时间"这类展示，**不太可能是"进不去战斗"的直接原因**。【推测】

### B3. 可验证的实验设计

| 项 | 内容 |
|---|---|
| 改哪 | `RaidManager.GetRaidTimeTicks` 改为 `return account.GameSettings.ServerDateTime();`（保留原函数加开关：`If Config.RaidRealTime`） |
| 重启后让用户 | 重新登录 → 进总力战 → 点"战斗"一次 |
| 观察 wire | ① `Raid_EnterBattle` 响应里 `ServerTimeTicks` 是否变成当前时间（**这一步必验**，证明改动生效）；② `Raid_EnterBattle` 是否还连续重发（83 次那种）；③ 是否出现 `Raid_BattleUpdate`/`Raid_EndBattle` |
| 判读 | 若 `ServerTimeTicks` 变了但重发照旧 ⇒ **时间不是根因**，把注意力放回 `BIEchelon`；若重发消失 ⇒ 时间就是根因 |

**建议把这条实验和 A1/A2 的修复分开做**，否则又变成多变量。

---

## C. 战术对抗赛为什么一次都不发 22004

### C1. 已证实：对手列表把自己放了进去

```csharp
// Shittim-Server\Services\ArenaService.cs:33-70  CreateOpponents
37  var accountDefense = CreateArenaUser(
38      account.ServerId,
39      account.RepresentCharacterServerId,
40      "Your Defense",            // ← 昵称硬编码，与 wire 的 "Your Defense" 完全对应
41      2,
42      account.Level,
43      CreateArenaTeamSetting(context, account, mapper, true));
44  result.Add(accountDefense);      // ← 第一条就是自己
...
63  while (result.Count < 3)
65      var dummyDefense = CreateArenaUser(-1, 10065, "Dummy Opponent", result.Count + 2, 90, DummyTeamFormation);
```
- wire 里 3 个对手 `AccountServerId=4`、`NickName:"Your Defense"` **与此逐字对应** 【已证实】。
- 补足的 dummy 用 `AccountServerId = -1`（负数 id）【已证实】。
- 另外：`ArenaUserDB.RepresentCharacterUniqueId = representCharacterServerId`（`ArenaService.cs:77`）—— **又把 ServerId 塞进 UniqueId 槽**【已证实】。

### C2. 已证实：wire 里没有开战流程的任何一步

| 协议 | 编号 | wire 出现次数 |
|---|---|---|
| `Arena_EnterLobby` | 22000 | 4 |
| `Arena_OpponentList` | 22003 | 2 |
| `Arena_SyncEchelonSettingTime` | 22016 | 5 |
| `Arena_DailyReward` | — | 1 |
| **`Arena_EnterBattlePart1`(22001) / `Part2`(22002) / `EnterBattle`(22004)** | — | **0** |

⇒ 客户端连"开战"的第一步都没发。

### C3. 推测（无法从服务端源码证实）

最可能：客户端在 `Arena_OpponentList` 之后做本地校验，发现
① 对手列表里包含自己（`AccountServerId` == 自己）或
② 存在非法对手（`AccountServerId = -1`、`Rank` 重复为 2/3、`RepresentCharacterUniqueId` 解析不到角色）
⇒ 禁用/拦截"战斗"按钮，因此不发 22001。

### C4. 验证实验

修 `CreateOpponents` 三件事后重启，让用户点一次"战斗"：
1. **不再把自己放进列表**（去掉 `accountDefense`，`result` 从空开始）；
2. dummy 的 `AccountServerId` 用 `0` 或真实存在的账号 id，不用 `-1`；
3. `RepresentCharacterUniqueId` 传 **UniqueId** 而不是 `RepresentCharacterServerId`。
判读：wire 出现 `Arena_EnterBattlePart1(22001)` ⇒ C3 假设成立；仍无 ⇒ 问题在客户端其他校验（转 il2cpp-analyst）。

---

## D. 大决战（EliminateRaid）是否同一根因

**同构，高置信（推测）**，依据：
1. 二者的 `EnterBattle` 响应结构在 wire 里**逐字段相同**（Lead 已对比），说明走同一套 DTO/流程；
2. `BIEchelon` 全工程**无任何赋值点**（A1 的 grep 是全局的）⇒ 大决战也没有；
3. `EliminateRaidManager.cs:251` 同样只写 `DamageCollection = new()`，与 `RaidManager.cs:207` 同款；
4. 大决战的 `ServerTimeTicks=637475760000000000`（更早的日期）与总力战同源（同一个 `GetRaidTimeTicks` 家族）。

⇒ **修法一致**：`BIEchelon` + `CharacterId` 用 UniqueId + `ServerTimeTicks` 用真实时间。
（未逐行读 `EliminateRaidHandler.EnterBattle`，标**推测**；若要 100% 确认需补读该文件。）

---

## E. 修复方案（按"证据强度 × 改动量"排序）

### 修复 1（最强、最小）：`RaidMembers[].CharacterId` 改用 UniqueId

| 文件 | 行 | 改前 | 改后 |
|---|---|---|---|
| `Shittim-Server\Services\RaidManager.cs` | 202-209 | `CharacterId = account.RepresentCharacterServerId,` | 先解析：`var memberCharacter = context.GetAccountCharacters(account.ServerId).FirstOrDefault(c => c.ServerId == account.RepresentCharacterServerId);`<br>再 `CharacterId = memberCharacter?.UniqueId ?? account.RepresentCharacterServerId,` |

**风险**：只影响 RaidBattle 的成员角色 id 显示/解析；不影响伤害计算。
**回滚**：还原该文件。
**注意**：这是"改在创建战斗行的时候"，而存量行里已经是 9 ⇒ **还必须修读取端**（`RaidHandler.EnterBattle` 里把 `raidBattle.RaidMembers[i].CharacterId` 现算覆盖），否则老行照旧发 9。

### 修复 2（同源，Arena）：三处 `RepresentCharacterUniqueId`

| 文件 | 行 | 改前 | 改后 |
|---|---|---|---|
| `ArenaService.cs` | 77 | `RepresentCharacterUniqueId = representCharacterServerId,` | 调用方传 UniqueId；或函数内改用 `context` 解析后赋值 |
| `ArenaHandler.cs` | 159 | `RepresentCharacterUniqueId = account.RepresentCharacterServerId,` | 用 `CharacterUniqueIdFor(db, account)`（同 FriendHandler 的 helper 思路） |
| `ArenaHandler.cs` | 271 | 同上 | 同上 |
（`ArenaHandler.cs:159` 在 `EnterBattlePart1`、`:271` 在 `EnterBattle`，均**已证实**为 ServerId。）

### 修复 3（Arena 列表合法性）：`CreateOpponents` 不再包含自己 + dummy id 不用负数

| 文件 | 行 | 改动 |
|---|---|---|
| `ArenaService.cs` | 37-44 | 删除 `accountDefense` 那 8 行（不把自己放进列表） |
| `ArenaService.cs` | 63-67 | `CreateArenaUser(-1, ...)` → `CreateArenaUser(0, ...)`（或真实账号） |

**风险**：若客户端要求"列表里必须有一个自己的防守阵容"（官方语义是展示自己的防守），删掉可能让 UI 少一行 —— **这条风险要在验证时观察**：若删掉后客户端连列表都不显示，就改成"保留自己但放最后/标正确 id"。

### 修复 4（需谨慎）：`ServerTimeTicks`

| 文件 | 行 | 改动 | 风险 |
|---|---|---|---|
| `RaidManager.cs` | 26-31 | 加开关 `Config.RaidRealServerTime`，为 true 时返回 `account.GameSettings.ServerDateTime()` | 若客户端确实用它在赛季窗口判定，可能由"能进界面"变成"直接拒绝" —— **必须单独实验**，不要和其他修复同批上 |

### 修复 5（**暂不做**）：`BIEchelon`

**没有官方格式样本 ⇒ 不猜**。要填就必须先拿到一份官方 `Raid_EnterBattle` 响应（或官方客户端反序列化代码，归 il2cpp-analyst）。
本轮只做"发现与记录"，不写代码。

---

## F. 需要用户做的一次手机操作（用于验证）

```
重新登录 → 进总力战 → 点一次「战斗」→ 等 10 秒 → 退出
```
服务端只要抓 wire，看三件事：
1. `Raid_EnterBattle`（17005）是否仍然连续重发（>3 次即为复现）；
2. 响应里 `RaidMembers[0].CharacterId` 是否从 `9` 变成 `13003`（验证修复 1/读取端）；
3. 是否开始出现 `Raid_BattleUpdate`（17006）。

战术对抗赛同理：**进竞技场 → 点一次「战斗」**，看 wire 是否出现 `Arena_EnterBattlePart1(22001)`。

---

# 第二轮（2026-11-18 夜）：83 次重发的字段级根因 + 可部署补丁

> 前提修正：本文件"第一轮"写于 `ShopRecruits` / `Arena.AutoRefreshTime` 修复上线之前。
> 本轮只看**总力战/大决战链路**，且 **不混入 `ServerTimeTicks` 实验**。

## A0. 先否掉一条（同意 Lead 的自我怀疑）

`RaidMembers` 是 `KeyedCollection<long, RaidMemberDescription>`（`Schale\MX\Logic\Data\Data.cs:15`），Newtonsoft 默认按**数组**序列化（它实现 `IList`）。
`RaidMemberCollection` 多出的 `TotalDamage`/`RaidDamages` 确实不在数组形态里 —— 但**客户端 DTO 是同一个 Schale 库、同一类型**，形状天然一致。
⇒ **`RaidMembers` 的序列化形状不是根因。【已证实·类型层面】**

## A1. H1：`RaidDB.IsEnterRoom` 必须为 true？

| 项 | 内容 |
|---|---|
| 定义 | 服务端模型 `Schale\Data\GameModel\GameContentModel\RaidDB.cs:35`；线上 DTO `Schale\MX\GameLogic\DBModel\DBModel.cs:1944` |
| 全工程读写点 | **只有这 2 处定义，零处赋值、零处读取**（全仓 grep IsEnterRoom） |
| 结论 | 服务端**永远 false**，且我们跳过默认值 ⇒ **该键根本不出现**。官方 17005 模板里该键存在，但模板是零值，不能说明官方线上值 |
| 支持 H1 | ① 字段名直译"已进入房间"；② `RaidManager.cs:148-168` 创建时设了 `RaidState=Playing` 却唯独没设它；③ 官方结构保留该字段说明它承载状态 |
| 反对 H1 | ① 客户端是否读它，服务端源码看不到【无法证实】；② 若只是房间标志没置位，客户端通常停在房间页，而不是狂发 EnterBattle |
| 判定 | **【推测·中等】**。最便宜可试：只在响应 DTO 上置 true，不落库 |

## A2. H2：`RaidMembers[0].CharacterId = 9` 应为 13003

| 项 | 内容 |
|---|---|
| 赋值点 1 | `Shittim-Server\Services\RaidManager.cs:206` `CharacterId = account.RepresentCharacterServerId` |
| 赋值点 2 | `RaidManager.cs:155`（`RaidDB.Owner.CharacterId`）同样 |
| 官方旁证 | 官方 22004 样本 `AttackingUserDB.RepresentCharacterUniqueId = 13010`（**5 位 UniqueId**），我方同类字段发的是 ServerId（9）⇒ **同字段家族官方用 UniqueId【已证实·样本】** |
| 判定 | **【推测·较高】**：对总力战没有 17005 官方样本，不能 100% 断言它阻断 |

## A3. 其余"没发"的字段

| 字段 | 我们 | 官方模板 | 判定 |
|---|---|---|---|
| `RaidDB.IsPractice` | 显式 false（`RaidManager.cs:165`） | false | 不是阻断【推测】 |
| `RaidDB.ClanAssistUsed` | 从未赋值 ⇒ 不发 | false | 不是阻断【推测】 |
| `RaidDB.Owner.DamageCollection` | 空集合 ⇒ `[]` | 有空块 | 不是阻断【推测】 |
| `RaidBattleDB.RaidBossIndex/CurrentBossGroggy/CurrentBossAIPhase/IsClear` | 0/0/0/false ⇒ 被跳过 | 模板有 | 未知；与"刚进战斗"一致，不像阻断【推测】 |
| `AssistCharacterDB` | 仅请求带 `AssistUseInfo` 才填（`RaidHandler.cs:212-218`） | 模板有整块 | 未知；请求没带助战 ⇒ 官方多半也不回【推测】 |

## B. 最小可部署补丁（只改读路径，不落库）

文件 `Shittim-Server\Core\NetworkProtocol\Handlers\RaidHandler.cs`：新增两个私有方法，并在 `EnterBattle`(L206-210 之后) 与 `CreateBattle`(L178-182 之后) 各加一行调用。

```csharp
// >>> BAPATCH-RAIDROOM v1 BEGIN >>>
// Two wire-level repairs for "entered the room but the battle never starts":
//  - RaidDB.IsEnterRoom is never assigned anywhere in the server, so it always serialised away as false.
//  - the member/owner CharacterId carries a CharacterDB.ServerId where the client resolves a UniqueId.
// Applied to the response copy only; nothing is persisted, so reverting is just dropping the call.
private static void NormalizeRaidEnterBattleWire(SchaleDataContext db, long accountServerId, RaidDB? raid, RaidBattleDB? battle)
{
    if (raid != null)
    {
        raid.IsEnterRoom = true;
        if (raid.Owner != null)
            raid.Owner.CharacterId = ToCharacterUniqueId(db, accountServerId, raid.Owner.CharacterId);
    }
    if (battle?.RaidMembers != null)
        foreach (var member in battle.RaidMembers)
            member.CharacterId = ToCharacterUniqueId(db, member.AccountId > 0 ? member.AccountId : accountServerId, member.CharacterId);
}

private static long ToCharacterUniqueId(SchaleDataContext db, long accountServerId, long maybeServerId)
{
    if (maybeServerId <= 0) return maybeServerId;
    // 已经是 UniqueId 就查不到 => 原样返回，不会把正确值改坏
    var character = db.GetAccountCharacters(accountServerId).FirstOrDefault(c => c.ServerId == maybeServerId);
    return character?.UniqueId ?? maybeServerId;
}
// <<< BAPATCH-RAIDROOM v1 END <<<
```

调用点：
```csharp
response.RaidBattleDB = raidBattleDB.ToMap(_mapper);
+ NormalizeRaidEnterBattleWire(db, account.ServerId, response.RaidDB, response.RaidBattleDB);
```

**为什么不成立也能安全留着**：
1. `IsEnterRoom=true` 只多一个布尔键，客户端不读它等于没改；
2. `ToCharacterUniqueId` 只在"传进来的值正好是本账号角色的 ServerId"时才转换，否则原样返回；
3. 全部发生在 `ToMap` 之后的 DTO 上，**不写库**，回滚 = 删掉那两行调用。

**写路径本轮不动**：`RaidManager.cs:206/155` 改的是落库值，判错会污染新行；读路径转换对新旧行都有效，风险更低。

## C. 官方 22004 vs 我方 `Arena_EnterBattle` 差异（只列，不改）

样本 `report\_tmp\official_decoded_201\77_22004_api_arena_enterbattle.response.json`，inner **14 个顶层键**。

| # | 差异 | 官方 | 我方（`ArenaHandler.cs:234-282` / DTO `NetworkProtocol.cs:519-528`） |
|---|---|---|---|
| 1 | `BattleSetting` 整块 | 顶层有：`BattleType=2097152`、`RandomSeed`、`Buid`、`BattleDurationInFrame=5400`、`GroundUniqueId`、`LeftTeam`/`RightTeam`（完整名单：ServerId/HeroId/Grade/Level/AIId/EchelonSlotType/SkillLevelTable/EquipmentSettings）、`ArenaSetting` | **完全没有**（DTO 里没这个字段） |
| 2 | `BattleServerError` | 顶层有（false） | 没有 |
| 3 | `ArenaBattleDB.BattleEndTime` / `BattleSummary` | 都有（`BattleSummary` 是**服务端算完整场战斗**的结果） | 都没有（只填 Season/Group/BattleStartTime/Seed/两个 UserDB） |
| 4 | `AttackingUserDB.RepresentCharacterUniqueId` | 13010（UniqueId） | `account.RepresentCharacterServerId`（`:271`，ServerId）**id 空间错** |
| 5 | `ArenaUserDB.Exp` / `IsAnonymous` | 都有 | `CreateArenaUser`（`ArenaService.cs:72-83`）**没填** |

**架构层【已证实·样本】**：官方 `Arena_EnterBattle` = "服务端算完整场战斗并回放"（`BattleSetting` 双方队伍 + `BattleSummary` + 奖励），我方是"下发一场让客户端自己打" ⇒ 客户端拿不到 `BattleSummary`/`BattleSetting`。

## D. 验证（一次手机操作）

重登 → 总力战 → 点「战斗」→ 等 10 秒 → 退出。看 wire 四件事：
1. `Raid_EnterBattle`(17005) 是否仍 500ms 内连续重发（>3 次 = 未修复）；
2. 响应里是否出现 `"IsEnterRoom":true`（补丁生效的第一证据）；
3. `RaidMembers[0].CharacterId` 是否 `9 → 13003`；
4. 是否出现 `Raid_BattleUpdate`(17006)（修复成功的第一信号）。
