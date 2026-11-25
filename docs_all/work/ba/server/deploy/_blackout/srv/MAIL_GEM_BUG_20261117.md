# 邮件发 Gem 丢失 —— 根因与修法（只读定位，未改代码）

- 执行者：srv-ops
- 时间：2026-11-17 21:51（北京时间 UTC+8）
- 依据事实：21:36 Gem=1800 → 21:44 领取 1,000,000 邮件后 Gem=1845（+45 来自 arena dailyreward），邮件行被删除

---

## 结论一行

**邮件里的 Gem 写进了 `CurrencyDict[CurrencyTypes.Gem]`(4)，紧接着被 `UpdateGem()` 用 `GemBonus + GemPaid` **重算覆盖**；覆盖点是 `ParcelResolver.cs:136`。**
**影响面 = **所有**通过 parcel 发的 Gem（邮件、任务、商店、竞技场…），不只是邮件。**
**修法 = 在 `ParcelResolver.UpdateAccountCurrency` 里，非消耗型的 Gem 改成加到 `GemBonus`（源字段），再 `UpdateGem()` 重算。**

---

## ① 发奖路径全链路（文件:行号）

```
MailHandler.cs:96   [ProtocolHandler(Protocol.Mail_Receive)] Receive(...)
MailHandler.cs:104  mailsToReceive = db.GetAccountMailbox(account, now).Where(m => request.MailServerIds.Contains(m.ServerId))
MailHandler.cs:112-118  遍历 mail.ParcelInfos → parcelResults.Add(new ParcelResult(type, id, amount))
MailHandler.cs:119  db.Mails.Remove(mail)          ← **邮件被删**
MailHandler.cs:122  await db.SaveChangesAsync()    ← **删除已落库（此后即使发奖失败，邮件也不会回来）**
MailHandler.cs:124  await _parcelHandler.BuildParcel(db, account, parcelResults)

ParcelHandler.cs:70      BuildParcel(...)
  → ParcelResolver.UpdateAccountCurrency(parcel)   ← 见下
```

## ② `UpdateAccountCurrency` 的 Currency 分支（`ParcelResolver.cs:112-161`）

```csharp
112  public async Task UpdateAccountCurrency(ParcelResult parcel, bool isAccountLevelUp = false)
114      var type = (CurrencyTypes)parcel.Id;              // ← 我们这封：Id=4 → Gem
...
132      if (IsConsume && type == CurrencyTypes.Gem)
133          accountCurrencyDB.SubtractGem(amount, dateTime);
135      accountCurrencyDB.UpdateCurrency(type, amount, dateTime);   // ★ 非消耗：直接 += 到 type 本身（= Gem）
136      accountCurrencyDB.UpdateGem(dateTime);                      // ★★ 立刻重算并**覆盖** Gem
```

## ③ `UpdateGem` 实现原文（`Schale/Data/GameModel/UserModel/AccountCurrencyDB.cs:88-95`）

```csharp
88  public void UpdateGem(DateTime timestamp)
89  {
90      var bonusGems = GetCurrencyAmount(CurrencyTypes.GemBonus);   // GemBonus
91      var paidGems  = GetCurrencyAmount(CurrencyTypes.GemPaid);    // GemPaid
92
93      CurrencyDict[CurrencyTypes.Gem] = bonusGems + paidGems;      // ★★★ 直接赋值覆盖
94      UpdateTimeDict[CurrencyTypes.Gem] = timestamp;
95  }
```
**调用点**（全仓库 grep `UpdateGem`）：
```
ParcelResolver.cs:136            ← 每次 parcel 更新都会调用（**就是这里覆盖的**）
Commands/CurrencyCommand.cs:77   ← GM /currency（它先写 GemBonus/GemPaid 再重算，所以 GM 命令是对的）
AccountCurrencyDB.cs:106         ← SubtractGem 内部（消耗路径）
Controllers/AdminController.cs:78（注释说明同一坑）
```

## ④ 判定：**是不是所有 parcel 的 Gem 都会丢？**

**是，所有非消耗型（grant）的 Gem parcel 都会丢。** 依据：
```
UpdateCurrency(Gem, +amount)  →  CurrencyDict[Gem] = 旧Gem + amount     (AccountCurrencyDB.cs:75)
UpdateGem()                   →  CurrencyDict[Gem] = GemBonus + GemPaid (同文件:93)  ← 覆盖
而 GemBonus/GemPaid 从未被加过 ⇒ Gem 回到旧值
```
**⇒ 受影响的调用面**（凡是 `new ParcelResult(ParcelType.Currency, 4, amount)` 的地方）：
```
邮件领取（MailHandler:116）
任务/活动奖励（MissionHandler / EventContentHandler 等走 parcel 的）
竞技场/总力战等结算
商店购买赠送的 Gem
新手/签到奖励
```
**⇒ 但有两个例外是安全的**：
1. **`GemPaid`(2) / `GemBonus`(3) 作为 parcel Id 发的**（如欢迎信的 `Id=3 GemBonus 1200` —— 所以那封是**真的到账了**，也解释了为什么 GemBonus 历史上是对的）；
2. **`/currency` GM 命令**（它写的是 GemBonus/GemPaid 再重算，语义正确）；
3. **消耗型**（`IsConsume=true` 走 `SubtractGem`，内部从 GemBonus/GemPaid 扣，也正确）。

## ⑤ 修法方案（**未部署**）

**改动点：`Shittim-Server/Services/ParcelResolver.cs`（约 132-136 行）**

现状：
```csharp
if (IsConsume && type == CurrencyTypes.Gem)
    accountCurrencyDB.SubtractGem(amount, dateTime);

accountCurrencyDB.UpdateCurrency(type, amount, dateTime);
accountCurrencyDB.UpdateGem(dateTime);
```

**补丁（BAPATCH-GEMGRANT v1）**
```csharp
if (IsConsume && type == CurrencyTypes.Gem)
{
    accountCurrencyDB.SubtractGem(amount, dateTime);
}
else if (type == CurrencyTypes.Gem)
{
    // Gem is derived (Gem = GemBonus + GemPaid) and UpdateGem() rewrites it right below, so a
    // grant must land on a source field - otherwise it is silently discarded.
    accountCurrencyDB.UpdateCurrency(CurrencyTypes.GemBonus, amount, dateTime);
}
else
{
    accountCurrencyDB.UpdateCurrency(type, amount, dateTime);
}
accountCurrencyDB.UpdateGem(dateTime);
```

**为什么不会破坏别的货币**
- `Gold / ActionPoint / 各种 Ticket` 的 Id **不是** 4，走 `else` 分支，行为与现在**完全一致**（`UpdateCurrency` 直接 +=、`UpdateGem` 不动它们）。
- `GemBonus(3)` / `GemPaid(2)` 作为 parcel Id 时：走 `else` 分支 → 直接 += 到源字段 → `UpdateGem` 重算 → 与现在一致（正确）。
- 消耗型 Gem：走第一个分支 `SubtractGem`，不变。
- **唯一变化**：`type == Gem(4) && !IsConsume` 时改为加 `GemBonus` —— 这正是修 bug 的那一支。

**幂等性（同一封邮件重复领取不能重复发钱）**
- 现状已有天然保护：`MailHandler.cs:119-122` **先删邮件并 `SaveChangesAsync()`，再发奖**。
  ⇒ 同一封邮件第二次领取时 `GetAccountMailbox` 查不到该行 → 不会再发奖。
- **但这也意味着**：若 124 行 `BuildParcel` 抛异常，邮件已删、奖未发 → **玩家净损失**（这正是今晚很可能发生的事，只不过这里是"静默丢失"而不是抛错）。
- **建议一并改（可选，BAPATCH-MAILATOMIC v1）**：把 `db.Mails.Remove(mail)` 从 119 行挪到 `BuildParcel` 成功**之后**，并把两次 `SaveChangesAsync` 合成一次（或用事务）。这样"要么都成、要么都不成"。
- 若只做 Gem 映射修复、不改顺序：**重复领取仍安全**（邮件行已删），只是异常时仍会丢信。

**影响面 / 部署成本**
```
改 1 个文件（ParcelResolver.cs）约 8 行；若要原子化再改 MailHandler.cs 约 5 行
需要重建 Shittim DLL（dotnet publish）+ 重启 Shittim
不涉及 nginx / 桥 / 数据库 schema
```

## ⑥ 另一个缺陷：`Shop_BuyAP` 满 AP 抛异常

```
文件：Core/NetworkProtocol/Handlers/ShopHandler.cs（BuyAP handler）
现象：21:44:49 起 8 次、21:45:21 起 4 次
      [ERR] Error invoking handler for protocol "Shop_BuyAP"
      但 HTTP 仍回 200（`POST /api/gateway "Shop_BuyAP"(10009) -> 200 in 3ms`）
原因：AP 已达上限 999（`ParcelResolver.cs:139-146` 的 OverChargeLimit 逻辑把 AP 截到上限），
      购买时应先判"是否已满"，现在直接进扣费/加 AP 流程抛 WebAPIException。
建议：购买入口先检查 `CurrencyDict[ActionPoint] >= OverChargeLimit` → 返回友好错误码，不要抛。
（列入 Shittim 待修清单，今晚不修）
```

---

## 本轮未改动
```
未改任何 .cs / DLL / Config / DB（Diagnosis only）
唯一写入是上一轮的 /currency 4 100000（已在 GEM_100K 报告里）
```
