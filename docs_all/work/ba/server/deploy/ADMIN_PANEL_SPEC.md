# 碧蓝档案私服 · 综合管理站 施工图

写于 2026-11-17 02:1x。作者：Lead。依据：`srv-ops` 对卡密系统 / 现有管理站 / Shittim 数据库的只读侦察，以及 `shittim-analyst` 对上游源码的阅读。**所有表结构与命令能力都是实测或源码确证。**

---

## 0. 用户要的能力（原话整理）

- 签发卡密 / 签发**公益卡**
- 选择是否**绑定设备**
- 查看**有多少注册玩家**
- 给某个账号的**邮箱里下发东西**
- 直接**改账号的数值**
- 改**每日登录领的东西**
- **能改的都要能改**

---

## 1. 现有资产盘点（不用重写，在上面加）

### 1.1 卡密层 `ba_cardadmin`（PHP + MySQL）

```
pages/  dashboard.php cards.php cards_new.php cards_import.php cards_export.php
        admins.php logs.php audit.php settings.php
inc/    db.php auth.php helpers.php sync.php
sql/schema.sql → 8 张表：
        admins / sessions / cards / card_devices / login_logs / audit_logs / settings / login_attempts
当前数据：cards = 1 行，admins = 1 行
```

**同步机制（现有架构的核心，不要动）**
```
MySQL = 唯一真源
cron 每分钟 */1 → cron/sync_cards.php → 导出到 cards.json
  · 原子替换 + flock（避免 sdkcard.py 读到半个 JSON）
  · 反向合并：cards.json 里 sdkcard.py 新绑的设备补回 MySQL（只补不删）
  · 孤儿（json 有、MySQL 无）不导出，只计数提醒
```

### 1.2 SDK 层 `ba_sdk/sdkcard.py`（127.0.0.1:8080）

暴露 7 条路径：

| 路径 | 作用 |
|---|---|
| `POST /user/login` | `OpenID` 字段就是卡密；校验 → 绑设备 → 签 token |
| `POST /user/quick-login` | 设备已在 `devices` 里 → 直接放行（不看卡密）|
| `POST /user/detail` | 同上，返回 `user_payload` |
| `POST /common/config` | 真实配置，把官方域名改写成 `example.com` |
| `POST /common/geo-ip` | 固定 `{"Prov":"浙江省"}` |
| `POST /health-game/duration` | 固定 `{"Code":110170,"Msg":"用户已成年,不需要计时"}` |
| `POST /heartbeat/pulse` | 固定 `{"Delay":3600}` |
| 其余路径 | 通用 `{"Code":200,"Msg":"OK","Data":{}}` |

**身份派生公式（`sdkcard.py:44-47`）**
```python
token        = sha256(card + '|' + device).hexdigest()[:40]          # 40 位 hex
User.ID      = int(md5(card).hexdigest()[:8], 16) % 900000000 + 100000000   # 只由卡密决定
Pass.NickName= 'BA' + card[-4:]
```

**设备绑定与有效期**
```
dev = Authorization.Head.DeviceID
if dev not in rec['devices']:
    if rec['bind_one'] and rec['devices']: → 400101 卡密已绑定其他设备
    else: rec['devices'].append(dev); save_cards()
if rec['expire'] > 0 and rec['expire'] < now: → 400101 卡密已过期
（没有次数限制，无 counter 字段）
```

### 1.3 `cards.json` 结构（sdkcard.py 的输入）

```json
{ "cards": {
    "11111111111": {
      "devices": ["09a4d0ab0ee93616"],   // 已绑定设备，数组，数量取决于 bind_one
      "expire": 0,                        // unix 秒；0 = 永不
      "bind_one": false                   // true = 只允许一台设备
    }
} }
```

---

## 2. ⚠️ 认证链的缺口（**这是对外开放的前置条件**）

```
玩家填卡密 → 魔改 SDK → sdkcard.py 校验卡密/设备/有效期 → 签 token
                                                        ↓
                                     客户端 1002 请求里带 Token + DevId
                                                        ↓
                    ★ 桥校验 token？ —— **完全没有**
                                                        ↓
                    桥用硬编码 ENTER_TICKET 打 Shittim → 铸造 ServerId=2 的会话
```

**现状后果**：任何人只要知道 `example.com/api/` 地址，就能直接调游戏 API，Shittim 会**自动建号**（实测：未知 publisherId `1013178778` 自动建出了 `ServerId=3` 并种了 4 个角色）。**卡密体系形同虚设。**

### 2.1 待用户决策：账号主键绑谁

| | 绑**卡密** | 绑**设备**（现状）|
|---|---|---|
| 换手机 | 进度保留 | **进度丢失**（新 ServerId）|
| 一号多端 | 天然支持 | 不支持 |
| 防共享 | 靠 `bind_one` 在 SDK 层控 | 天然一台一号 |
| 改动 | `publisherId` 用卡密数字，设备只做授权门禁 | 无需改动 |

**Lead 建议：绑卡密。** 私服玩家换机/重装是常态，丢档直接劝退；防共享在 SDK 层已经够了。

### 2.2 改造清单（合并"多玩家"与"token 校验"，一次做完）

1. 删掉 `ENTER_TICKET` 硬编码常量（`account_auth_probe.py` L164-166）
2. `ensure_session(rec)` 改为从请求的 `Token`/`DevId` 现算 `EnterTicket = base64(PublisherId + "/" + Token)`
   - Shittim 侧格式约束：`parts[0]` 必须能 `long.Parse`，token 不能含 `/`（`AccountHandler.cs:58-63`）
3. **先验 token**：向 `sdkcard.py`（或直接读 `cards.json` + 重算 sha256）确认「这张卡存在、未过期、该设备已授权」，验不过直接拒绝，不转发
4. `SESSION` 从模块级全局单例 → `dict[publisher_id]` 分片 + 每键一把锁
   - 现状：全文件仅 14 处读写、`ensure_session` 仅 3 个调用点，改动集中
5. 并发保护：同一 `publisherId` 的首登要互斥（Shittim 的"查不到→建号"之间**没有唯一约束保护**，两个并发首登可能各建一行）

---

## 3. Shittim 数据面：每个功能落到哪张表

### 3.1 邮件（发东西到玩家邮箱）

```sql
CREATE TABLE "Mails" (
  "ServerId" INTEGER PRIMARY KEY AUTOINCREMENT,
  "AccountServerId" INTEGER NOT NULL,
  "Type" INTEGER NOT NULL,           -- 13 = 系统礼物, 1 = 签到奖励
  "UniqueId" INTEGER NOT NULL,       -- 模板/批次号
  "Sender" TEXT, "Comment" TEXT,
  "LocalizedSender" TEXT,            -- JSON: {"Kr":"Arona","Jp":"Arona",...}
  "LocalizedComment" TEXT,           -- JSON
  "SendDate" TEXT, "ReceiptDate" TEXT NULL,  -- NULL = 未读
  "ExpireDate" TEXT NULL,
  "ParcelInfos" TEXT NULL,           -- ★ 附件：JSON 数组
  "RemainParcelInfos" TEXT NULL,     -- 领取后残余，JSON 数组
  "IsRefresher" INTEGER
)
```

**附件格式（实测样本）**
```json
[{"Key":{"Type":2,"Id":3},"Amount":1200,
  "Multiplier":{"rawValue":10000},"MultipliedAmount":1200,
  "Probability":{"rawValue":10000}}]
```
⇒ **纯 JSON 文本，无 BLOB、无附表，写入简单。**

### 3.2 货币

`Currencies.CurrencyDict`（JSON 字典，27 种）、`UpdateTimeDict`（JSON）、`AccountLevel`、`AcademyLocationRankSum`

⚠️ **Gem 特殊**：`CurrencyCommand.cs:64-70` 注释——直接写 `Gem` 会被丢弃，必须写 `GemBonus`/`GemPaid` 再走 `UpdateGem()`。

### 3.3 账号标量

`Accounts`：`Nickname / CallName / Level / Exp / State / LobbyMode / Comment / RepresentCharacterServerId / MemoryLobbyUniqueId / VIPLevel / UnReadMailCount / RetentionDays / LastConnectTime / BirthDay`

### 3.4 角色

`Characters`：`ServerId`(自增主键) / `AccountServerId` / **`UniqueId` = `CharacterExcel.Id`** / `StarGrade` / `Level` / `Exp` / `FavorRank` / `FavorExp` / 5 个技能等级 / `IsFavorite` / `EquipmentServerIds`(JSON) / `PotentialStats`(JSON) / `EquipmentSlotAndDBIds`(JSON)

⚠️ **顺序坑**：`Echelons.LeaderServerId` / `MainSlotServerIds` 和 `Accounts.RepresentCharacterServerId` 引用的是 **`Characters.ServerId`（自增主键）**，不是 `UniqueId`。必须先插 `Characters` 拿到 id 再回填。

### 3.5 每日登录 / 签到

```sql
AttendanceHistories(ServerId PK, AccountServerId FK, AttendanceBookUniqueId,
                    AttendedDay TEXT NULL, Expired INT, LastAttendedDay INT,
                    LastAttendedDate TEXT, AttendedDayNullable TEXT NULL)
```
**奖励定义来自 Excel `AttendanceExcelT`**（`AttendanceService.cs:30` `OpenBooks()`）。
领奖时**通过邮件发放**（`Type=1`，sender `UI_MAILBOX_POST_SENDER_ARONA`，7 天过期，回 `ServerNotification 12`）。

⚠️ **这是唯一不能 SQL 改的东西**：Excel 是 SQLCipher 加密（`Config.json` 有 `ExcelDbSqlCipherKey`），且 `UseCustomExcel=true`。
要改奖励内容，得用那个 key 打开 Excel 写入，或改用 `Resources/Custom` 覆盖机制。**单独立项。**

---

## 4. GM 命令能力边界（关键限制）

23 条命令：`accountdata addEleph character checkItem clearInventory currency gacha giveAll giveAllEquip give giveEquip help inventory listItem mail max setaccount setraid setseason setting unlockAll unlockBattlePass`

| 需求 | GM 命令 | 说明 |
|---|---|---|
| 发邮件（含附件） | ✅ `!mail <type> <id,...> <amount>` | 走同一套 Parcel 逻辑，最安全 |
| 改货币 | ✅ `!currency <id\|name> <amount>` | Gem 有专门处理 |
| 改账号数值 | ✅ `!setaccount <Property> <Value>` | **反射赋值**，覆盖 `AccountDBServer` 全部属性 |
| 给角色/装备/道具 | ✅ `!give` `!giveequip` `!giveall` `!giveallequip` `!addeleph` | |
| 满级角色 | ✅ `!max all` | Lv90 + 满星 + Favor100 + 技能 10/5/10/10 + 潜能满 |
| 整档导入/导出 | ✅ `!accountdata export/load` | **"发满级存档"最正规的入口** |
| 解锁内容/通行证/卡池 | ✅ `!unlockall` `!unlockbattlepass` `!gacha` `!setraid` `!setseason` | |
| 每日登录奖励**定义** | ❌ | 只能改 Excel（见 §3.5） |
| **跨账号操作**（给指定 ServerId 发东西）| ❌ | **GM 命令全部绑定"当前控制台账号"（`--id 2`），没有 target 入参** |

### 4.1 ★ 这是管理站最大的结构性障碍

只想给**控制台绑定的那个号**发东西 → GM 命令够用。
要给**任意玩家**发东西 → GM 命令做不到。三条路：

1. **给 Shittim 加 admin API（C#）** ← 推荐，走它自己的 EF Core，天然安全
   - 障碍：服务器**只有 .NET 10 运行时，没有 SDK**（`--list-sdks` 空）⇒ 需先装 SDK
2. **SQL 直写** ← 可行但仍需谨慎（JSON 格式、enum 数字键、自增主键顺序）
3. 每条命令重开控制台换 `--id` ← 不现实

**Lead 建议：1 + 2 组合。** 常用/高危操作走 admin API（EF Core 保证一致性），批量/查询走只读 SQL。

---

## 5. 建议架构

```
浏览器
  ↓ HTTPS
PHP 管理站（ba_cardadmin 扩页面：+玩家、+邮件、+数值、+签到）
  ↓ 只调本地 HTTP 接口（127.0.0.1:xxxx）
本地 admin 后端（Python）
  ├─ 读：shittim.sqlite3（mode=ro）      → 玩家列表/账号详情/邮件历史
  ├─ 写：Shittim admin API（需装 SDK）   → 发邮件、改数值、给角色
  ├─ 写：GM 控制台（tmux send-keys）      → 仅限 --id 2 的兜底操作
  └─ 写：审慎 SQL                        → admin API 未覆盖的批量操作
卡密数据：MySQL（唯一真源）→ cron → cards.json（现有机制不动）
```

**为什么不让 PHP 直接写 Shittim 库**：写库约束散在 C# 源码里（JSON 的 enum 键是数字、`Echelon` 引用自增主键、`AccountCurrencyDB.AccountLevel` 与 `AccountDB.Level` 是两个字段、Gem 必须写 GemBonus/GemPaid…）。PHP 那边看不见这些，写错就是"某界面崩"，极难排查。**把写操作收敛到一个地方，是唯一能管住的办法。**

---

## 6. 分阶段计划

| 阶段 | 内容 | 前置 |
|---|---|---|
| **P-A** | 认证链：删硬编码 ticket + 验 token + per-player session（§2.2）| 用户定"绑卡密还是绑设备" |
| **P-B** | 装 .NET SDK，给 Shittim 加 admin API（列出/改数值/发邮件/给角色）| P-A 可并行 |
| **P-C** | 管理站加"玩家"页（列表、注册总数、单号详情）| P-B 的只读接口 |
| **P-D** | 管理站加"邮件"页（单人/群发，附件选择器）| P-B 的发邮件接口 |
| **P-E** | 管理站加"数值"页（等级/货币/角色）| P-B 的改数值接口 |
| **P-F** | 签到奖励定义（Excel SQLCipher）| 单独立项 |
| **P-G** | 卡密页扩字段：公益卡（不限期不绑设备）、批量签发、设备解绑 | 现有机制已够 |

---

## 7. 未确认项

- `cards.json` 的反向合并只"补不删"，如果管理站要**解绑设备**，需要改 `sync_cards.php` 的合并规则（现在是只补不删）
- Shittim 是否对账号数据有内存缓存（外部 SQL 写入能否立刻生效，未验证）
- `AttendanceExcelT` 的自定义覆盖机制（`UseCustomExcel=true` 时读哪个路径）未确认
- GM 控制台 `--id` 能否在不重启进程的情况下切换（未确认；若能，则跨账号操作有第三条路）
