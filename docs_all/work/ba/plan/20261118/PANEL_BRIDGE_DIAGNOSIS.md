# BA 私服管理面板 · 「桥接 / 卡密」数据取不到 · 只读诊断

- 目标：`C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\cardadmin_php`（源码）
- 线上快照：`work\ba\srv_live\20261118_0059\ba_cardadmin`
- 桥接镜像（旧快照，只用于读 schema）：`work\ba\srv_live\20261118_0059\bapatch\data\accounts.db`
- 报告性质：**只读诊断**。本文件之外没有改动任何 `.php`；所有补丁只以 diff 文本给出，未落地、未部署。
- 取证时间：2026-11-18 03:2x（本地）

---

## 0. TL;DR（先看这三行）

| 项 | 结论 |
|---|---|
| **最可能的原因** | `.user.ini` 的 `open_basedir` 只放行了 `ba_cardadmin/`、`/tmp/`、`ba_sdk/`，**没有 `/www/wwwroot/bapatch/`**。面板默认去读 `/www/wwwroot/bapatch/data/accounts.db`，被 `is_file()` 直接判 false → `player_bridge_accounts()` 第 42-44 行**提前 return []，连 PDO 都没机会打开**，`catch` 根本没触发。于是页面显示「未找到（publisherId 对不上 accounts.db）」——而 publisherId 其实是对的。 |
| **面板上的自相矛盾信号** | 「桥接 / 卡密」区说 **「publisherId 对不上」**（`player_detail.php:251`），「设置 → 游戏服务端」区却说 **「✗ 文件不存在」**（`settings.php:390` ← `players.php:84`）。同一份数据，两种说法，都指向不了真因；而运维 `ls` 一下就知道文件在。**两个说法里，"文件不存在" 才是那个假的。** |
| **补丁该打在哪** | `inc/players.php` 本地源码与线上快照**逐字节完全相同**（20661 B，MD5 `8279F2F76267D4BB1EF0FA499827B607`），一份 diff 两边都能用。`pages\settings.php`、`pages\player_detail.php` **两边不一致**，diff 必须分版本给（见 §3）。 |

---

## 1. 结论一：根因与证据链

### 1.1 直接证据

`work\ba\srv_live\20261118_0059\ba_cardadmin\.user.ini` 第 1 行（全文只有这一行）：

```
open_basedir=/www/wwwroot/ba_cardadmin/:/tmp/:/www/wwwroot/ba_sdk/
```

同目录 `work\ba\srv_live\20261118_0059\ba_cardadmin\.user.ini.bak.1794777086`（宝塔改名备份，epoch 1794777086 ≈ 2026-11-16）：

```
open_basedir=/www/wwwroot/ba_cardadmin/:/tmp/
```

⇒ 这个白名单**被改过一次**：从「2 个目录」扩到「3 个目录」，加进去的正是 `ba_sdk`。
说明此前已经因为 open_basedir 踩过一次坑（`cards.json` / `sdk.log` 在 `ba_sdk`），**当时补了 `ba_sdk`，但同一个坑的第二个受害者 `bapatch` 没补**。

### 1.2 被拒绝的路径

`inc/players.php:21-28`：

```php
function player_accounts_db_path()
{
    if (defined('BA_ACCOUNTS_DB') && BA_ACCOUNTS_DB !== '') {
        return (string)BA_ACCOUNTS_DB;
    }
    $custom = function_exists('setting_get') ? (string)setting_get('ba_accounts_db', '') : '';
    return $custom !== '' ? $custom : '/www/wwwroot/bapatch/data/accounts.db';
}
```

- 默认值：`/www/wwwroot/bapatch/data/accounts.db`（第 27 行）
- 面板设置页可覆盖（`pages/settings.php:100` `setting_set('ba_accounts_db', $acc)`）
- 但无论哪条路，只要落在 `/www/wwwroot/bapatch/` 下，**都不在 open_basedir 里**

### 1.3 文件确实存在（本地快照可证）

`work\ba\srv_live\20261118_0059\bapatch\data\accounts.db` — **143,360 B**。
与 `work\ba\server\deploy\_audit\PRODUCTION_HARDENING_20261118.md:120` 记录的线上真值
「真正的账号库是 /www/wwwroot/bapatch/data/accounts.db（143,360 B）」**字节数完全一致**，
⇒ 快照就是当前线上那份库，文件在，不是"不存在"。

同一文档 `:118` 还记着 `/www/wwwroot/bapatch/accounts.db 0 字节 → 已删`（那是旧位置的空壳，容易误判成"文件没了"）。

### 1.4 join 键本身是对的（不是 publisherId 对不上）

`accounts.db` 实查（`sqlite3` 只读打开本地快照）：

```
server_id      publisher_account_id  typeof     dev_id             login_count  last_login_at
10000000000    314816420             integer    314816420          39           2026-11-18T00:44:42
10000000001    1013178778            integer    1013178778         78           2026-11-18T00:18:45
10000000002    999888777             integer    999888777          1            2026-11-17T20:28:38
```

而 `PRODUCTION_HARDENING_20261118.md` §3.4 记录了桥接侧硬编码：

> `UserAccounts` 只有 1 行：`Id=1 Uid=2 NpSN=314816420` … 桥把 publisherId 硬编码成 314816420 → 两台手机映射到同一个账号

⇒ Shittim 侧 `publisherAccountId = 314816420`，`accounts.publisher_account_id = 314816420`。
**两边键值完全相同。** 所以 `player_detail.php:251` 那句「publisherId 对不上 accounts.db」是**彻头彻尾的误报**。

### 1.5 为什么"整个区块全空"而不是个别玩家空

open_basedir 是**进程级/请求级**限制 → `player_bridge_accounts()` 对**任何**玩家都返回 `[]` → `player_one()` 第 354 行 `$br` 恒为 `null` → 5 行"桥接账号/设备号/dev_id/登录次数/最后登录"**全部**走 `未找到 / —` 分支。
一个玩家的键对不上，只会空一个玩家；**全站全空 = 全局故障**，与 open_basedir 的形态完全吻合。

### 1.6 为什么 catch 抓不到（这是设计缺陷，不是本次故障）

`inc/players.php:42-44` 在 `try` **之外**：

```php
    $path = player_accounts_db_path();
    if (!is_file($path) || !is_readable($path)) {
        return $rows;                     // ← 这里直接返回，异常机制完全不参与
    }
```

open_basedir 命中时 `is_file()` / `is_readable()` 的行为是：**返回 false + 发一条 E_WARNING**
（`is_file(): open_basedir restriction in effect. File(/www/wwwroot/bapatch/data/accounts.db) is not within the allowed path(s)`）。
不抛异常 ⇒ 第 59-61 行的 `catch (Throwable)` **根本没被执行**。
生产环境 `display_errors=Off` 时这条 warning 只进 `error_log`，页面上什么都看不到。

⇒ 这不是"异常被静默吞掉"，而是**比吞异常更早一步、连异常都不产生的静默失败**。这也解释了为什么"给 catch 加日志"这类直觉修法会扑空。

---

## 2. 现状数据流图

```
                         ┌──── 页面：pages/player_detail.php ────┐
                         │ $p = player_one($sid)      (:142)     │
                         │ $bridge = $p['bridge']     (:151)     │
                         │ 渲染                        (:251-256) │
                         └───────────────┬───────────────────────┘
                                         │
                 ┌───────────────────────▼─────────────────────────────┐
                 │ inc/players.php :: player_one($serverId)  :344-388   │
                 │                                                      │
                 │ ① ba_account_detail()  ← Shittim /api/admin/...      │
                 │      :346  得 $d['publisherAccountId'] = 314816420   │
                 │      :351  $pub = (string)(int)$d['publisherAccountId']
                 │                        = "314816420"                 │
                 │                                                      │
                 │ ② $bridge = player_bridge_accounts()      :353       │
                 │      $br = isset($bridge["314816420"]) ? ... : null  │
                 │                                        :354          │
                 │                                                      │
                 │ ③ player_card_bindings() + cards 表      :356-378    │
                 │      → $myCards                                      │
                 └──────┬────────────────────────┬──────────────────────┘
                        │                        │
        ┌───────────────▼─────────┐   ┌──────────▼──────────────────────────┐
        │ ② accounts.db (SQLite)  │   │ ③ MySQL ba_cardadmin                │
        │                         │   │                                     │
        │ player_bridge_accounts()│   │ player_card_bindings()  :174-186    │
        │   :34-63                │   │   → player_ensure_tables() :92-134  │
        │                         │   │     CREATE TABLE IF NOT EXISTS      │
        │ :42  is_file/is_readable│   │       card_players / panel_ops      │
        │      ✗✗✗ open_basedir   │   │   (catch 吞掉一切 :131-133)         │
        │      └─ return [] ◄─────┼───┼─ 实际故障点                          │
        │ :49  new PDO(READONLY)  │   │   :179 db_all('SELECT * FROM        │
        │ :54  SELECT * FROM      │   │        card_players')  (catch :182) │
        │        accounts         │   │   :180 以 (int)card_id 为键         │
        │ :56  $rows[(string)$k]  │   │                                     │
        │ :59  catch(Throwable)   │   │   cards 表 :359 db_all(cards)       │
        │        { $rows = [] }   │   │   :362 绑定存在但 cards 行已删 → 跳过│
        └─────────────────────────┘   └─────────────────────────────────────┘

             全部 3 条链路的失败都被压成同一个 UI 现象：
             ┌──────────────────────────────────────────────────────┐
             │ player_detail.php:251  「未找到（publisherId 对不上…）」│
             │ player_detail.php:259  「还没有绑定卡密。」            │
             └──────────────────────────────────────────────────────┘
             ↑ 前者把 open_basedir/权限/表名/列名/WAL 全压成一句
             ↑ 后者把"表没建/表空/查询失败/卡已删"全压成一句
```

**第三条独立链路（面板没显示但确实存在）**：设置页自检

```
pages/settings.php:332   $brStatus = player_bridge_status()
inc/players.php:66-87    player_bridge_status()
                           :72 exists   = is_file($path)      → false（open_basedir）
                           :73 readable = is_readable($path)  → false
                           :75 has_pdo_sqlite                 → true
                           :77 if (has_pdo_sqlite && readable) → false
                           :79 elseif (!has_pdo_sqlite)        → false
                           :81 elseif (!exists)                → true ⇒ error='文件不存在'
pages/settings.php:386-392  渲染：✗ 文件不存在 + 路径
```

---

## 3. 版本对照：补丁该打在哪个版本上

用 `Get-FileHash -Algorithm SHA256` 逐文件比对「线上快照 vs 本地源码」。
`SAME` = 逐字节相同；`DIFF` = 内容不同；`ONLY-LIVE` = 只在线上有。

### 3.1 本案要动的文件

| 文件 | 本地源码 | 线上快照 | 状态 | 结论 |
|---|---:|---:|---|---|
| `inc\players.php` | 20,661 B | 20,661 B | **SAME**（MD5 `8279F2F7…`） | ✅ **主战场。一份 diff 两边通用。** |
| `inc\db.php` | 4,309 B | 4,309 B | SAME | 不用动 |
| `inc\ba.php` | 17,298 B | 17,298 B | SAME | 不用动 |
| `sql\schema.sql` | 7,779 B | 7,779 B | SAME | 不用动（且它**不含** `card_players`，见 §5） |
| `pages\settings.php` | 22,242 B | 20,164 B | **DIFF** | ⚠️ 分版本给 diff（见 §7.1b） |
| `pages\player_detail.php` | 21,970 B | 21,032 B | **DIFF** | ⚠️ 分版本给 diff（见 §7.3b） |
| `inc\auth.php` | 20,629 B | 13,476 B | DIFF | 不动（安全层，见 §8） |
| `inc\helpers.php` | 27,623 B | 25,872 B | DIFF | 不动 |
| `inc\sync.php` | 29,150 B | 25,122 B | DIFF | 不动 |
| `index.php` / `login.php` | 396 / 4,315 | 396 / 4,315 | SAME | 不动 |

### 3.2 全部不一致文件清单（完整扫描）

```
DIFF      .htaccess
DIFF      assets\app.js
DIFF      inc\auth.php
DIFF      inc\helpers.php
DIFF      inc\sync.php
DIFF      pages\cards.php
DIFF      pages\cards_export.php
DIFF      pages\cards_import.php
DIFF      pages\cards_new.php
DIFF      pages\console.php
DIFF      pages\currency.php
DIFF      pages\dashboard.php
DIFF      pages\items.php
DIFF      pages\mail.php
DIFF      pages\player_detail.php
DIFF      pages\players.php
DIFF      pages\settings.php
ONLY-LIVE .user.ini
ONLY-LIVE .user.ini.bak.1794777086
ONLY-LIVE 404.html
ONLY-LIVE config.php
ONLY-LIVE index.html
ONLY-LIVE installed.lock
ONLY-LIVE logs\sync.log
ONLY-LIVE state\bacache\static_chars_*.json
ONLY-LIVE state\bacache\static_currencies.json
ONLY-LIVE state\bacache\static_items_*.json
ONLY-LIVE state\cards.backup.json
ONLY-LIVE state\sync.lock
ONLY-SRC  .gitignore
```

**方向判断**：本地源码的 `pages\*.php` 全部**大于**线上（如 `settings.php` 22,242 > 20,164），
说明本地是**更新的开发版**，线上跑的是**较旧的已部署版**。
`inc\players.php` 恰好**没有分叉**——本案的 bug 就坐在这个两边一致的快照上。

### 3.3 打补丁的操作建议

| 场景 | 建议 |
|---|---|
| 只修 bug，不动其他 | 只打 `inc\players.php`（两边通用），`settings.php` / `player_detail.php` 按线上版打 |
| 顺手带上本地新功能 | 整包上线，则 diff 用本地版行号 |

⚠️ `pages\settings.php` 与 `pages\player_detail.php` 的 hunk 行号**不能混用**：
本地版比线上版多 2,078 B / 938 B，行号会整体漂移。§7 中每一个 diff 都标注了基准版本。

---

## 4. 问题 1：`$p['bridge']` 从哪来

### 4.1 调用链

```
pages\player_detail.php:142   $p = player_one($sid);
pages\player_detail.php:151   $bridge = $p['bridge'];          ← 取值
pages\player_detail.php:251   …$bridge ? '<code>'.server_id.'</code>' : '未找到（publisherId 对不上 accounts.db）'
```

`$p['bridge']` 由 **`inc\players.php` 的 `player_one()`（第 344-388 行）** 算出，
具体是第 **353-354** 行：

```php
    $bridge = player_bridge_accounts();                                        // :353
    $br     = ($pub !== '' && isset($bridge[$pub])) ? $bridge[$pub] : null;    // :354
```

最终 `player_one()` 第 **384** 行 `'bridge' => $br` 把它交出去。
`$bridge` 的**值**本身来自 `player_bridge_accounts()`（第 34-63 行）返回的 `publisher_account_id => row` 映射。

### 4.2 用哪个键 join

| 侧 | 生产键 | 出处 |
|---|---|---|
| Shittim admin API | `publisherAccountId`（JSON 字段） | `inc\ba.php:237-240` `ba_account_detail()` → `/api/admin/account/{id}/detail`；`inc\ba.php:141` `json_decode($raw, true)` |
| accounts.db | `publisher_account_id`（SQLite 列） | `accounts.db` `CREATE TABLE accounts (... publisher_account_id INTEGER NOT NULL DEFAULT 0 ...)` |

join 语句就是 `isset($bridge[$pub])`（第 354 行），其中
`$bridge` 的键在 `players.php:56` 由 `publisher_account_id` 生成，
`$pub` 在 `players.php:351` 由 `publisherAccountId` 生成。

### 4.3 类型：int / string 在哪一步隐式转换

**四步，两个方向都有，最后一步是 PHP 的隐式行为**：

| # | 位置 | 动作 | 类型变化 |
|---|---|---|---|
| 1 | `inc\ba.php:141` `json_decode($raw, true)` | JSON number → PHP | `314816420` 在 64 位 PHP 上是 **int**（未超 2^63，精确）。若 API 把它序列化成浮点或字符串，这里先变成 `float` / `string` |
| 2 | `inc\players.php:351` `$pub = (string)(int)$d['publisherAccountId']` | **显式** int 再转 string | int/float/数字串 → `"314816420"` |
| 3 | `inc\players.php:56` `$rows[(string)$r['publisher_account_id']] = $r` | **显式** 转 string 当数组键 | `pdo_sqlite` 在 PHP ≥8.1 给 int、<8.1 给 string；这里统一成 `"314816420"` |
| 4 | **PHP 数组键规范化（隐式）** | `$rows["314816420"]` 被静默**转成 int 键** `314816420` | string → int（**唯一一处隐式转换**） |
| 5 | `inc\players.php:354` `isset($bridge[$pub])` | `$pub` 是 `"314816420"`，PHP 在哈希时**又把规范数字串折回 int** | string → int（隐式，第二次） |

**关键点：第 4、5 步两次隐式转换方向一致，所以 `"314816420"` 和 `314816420` 能对上。
只有"非规范形态"会断**：

| 值形态 | 数组键 | 后果 |
|---|---|---|
| `"314816420"` | int `314816420` | ✅ 命中 |
| `314816420`（int） | int `314816420` | ✅ 命中 |
| `"0314816420"`（前导零） | **string** `"0314816420"` | ❌ 永不命中 |
| `" 314816420"`（含空格） | **string** | ❌ 永不命中 |
| `"3.1481642E+8"`（科学计数法串） | **string** | ❌ 永不命中 |
| `null` / 缺列 | 不进 `$rows`（第 55 行 `isset()` 对 NULL 返回 false） | ❌ 该行整条丢失 |

### 4.4 本案实际值：类型不是凶手

```
accounts.publisher_account_id = 314816420  (9 位, typeof=integer)
Shittim publisherAccountId    = 314816420
```
9 位数，64 位 PHP 内 int 精确，`(string)(int)` 与 `(string)` 结果一致 → **类型链没问题**。

⚠️ 但任务描述里担心的「`10000000000` 这类 11 位数走 float/科学计数法」**确实存在，只是不在这个字段上**：

- `10000000000` 是 **`server_id`**（`accounts.db` 的 `CHECK (server_id >= 10000000000)`），不是 publisherId；
- 11 位数 → `1.0E+10` 只有在 **PHP 7.x** 且走了 float 分支时才成立；
- 线上是 **PHP 8.2.31**（`installed.lock` 明写），PHP 8 的 float→string 默认 `serialize_precision=-1`，`(string)1.0E+10` 给 `"10000000000"`，不会变科学计数法；
- 且 `(int)` 在 64 位上对 11 位、15 位都精确，只有在**超过 2^53 (≈9.007e15)** 且中途经过 float 时才丢精度。

⇒ **结论：类型归一值得做（防御性加固），但它不是本次"取不到"的原因。**
不能把 open_basedir 的问题误诊成类型问题——那样修完页面还是空的。

---

## 5. 问题 2：`player_bridge_accounts()` 第 59-61 行静默吞异常——逐条列出返回空数组的条件

`inc\players.php:34-63` 原样（关键行已标）：

```php
function player_bridge_accounts()
{
    static $rows = null;
    if ($rows !== null) {
        return $rows;                                    // ── A
    }
    $rows = array();
    $path = player_accounts_db_path();
    if (!is_file($path) || !is_readable($path)) {
        return $rows;                                    // ── B
    }
    if (!class_exists('PDO') || !in_array('sqlite', PDO::getAvailableDrivers(), true)) {
        return $rows;                                    // ── C
    }
    try {
        $pdo = new PDO('sqlite:' . $path, null, null, array(
            PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
            PDO::SQLITE_ATTR_OPEN_FLAGS  => PDO::SQLITE_OPEN_READONLY,
        ));
        foreach ($pdo->query('SELECT * FROM accounts') as $r) {
            if (isset($r['publisher_account_id'])) {
                $rows[(string)$r['publisher_account_id']] = $r;
            }
        }
    } catch (Throwable $e) {
        $rows = array();                                 // ── D  ← 第 59-61 行
    }
    return $rows;
}
```

### 5.1 全部返回 `[]` 的条件（穷举）

| # | 出口 | 条件 | 触发条件细分 | 面板表现 | 概率 |
|---|---|---|---|---|---|
| **1** | **B (42-44)** | `!is_file($path)` | **1a. `open_basedir` 不含该目录 —— `is_file()` 恒 false** | 设置页：`✗ 文件不存在` | **★★★★★ 命中** |
| 2 | B | `!is_file($path)` | 1b. 文件真的不在 | 同上 | ★ |
| 3 | B | `!is_file($path)` | 1c. 路径拼错（少 `data/`、尾随空格、`setting_get('ba_accounts_db')` 存了脏值） | 同上 | ★★（`settings.php:89` 只校验"以 / 开头"，不校验存在） |
| 4 | B | `!is_readable($path)` | 4a. 文件 `600 root:root`，www 无 r | 设置页：`✗ PHP 用户无读权限（…）` | ★★ |
| 5 | B | `!is_readable($path)` | 4b. 父目录缺 `x` 位，www 无法 traverse | 同上 | ★ |
| 6 | B | `!is_readable($path)` | 4c. `open_basedir`（同 1a） | 同上 | （同 1a） |
| 7 | **C (45-47)** | `!class_exists('PDO')` 或 `'sqlite' ∉ getAvailableDrivers()` | **7a. `pdo_sqlite` 未编译 / 未启用** | 设置页：`✗ PHP 未启用 pdo_sqlite 扩展` + 「PHP 扩展」行 `pdo_sqlite` 变红 | ★★★（PHP 8.2 常默认带，但宝塔可能裁掉） |
| 8 | **D (59-61)** | `new PDO(...)` 抛 `PDOException` | 8a. **WAL 库 + `SQLITE_OPEN_READONLY` + 目录不可写 → `SQLITE_CANTOPEN`**。本库 `journal_mode=wal`（见 5.2），这是**修完 open_basedir 后最可能撞上的下一道门** | 设置页：`✓ 可读 · 0 个账号镜像`（**假绿灯**） | ★★★★（条件性） |
| 9 | D | 同上 | 8b. 文件不是合法 SQLite（被覆盖 / 截断）→ `SQLITE_NOTADB` | 同上 | ★ |
| 10 | D | 同上 | 8c. 库被 SQLCipher 加密 → `file is not a database` | 同上 | ★（本库明文，已排除） |
| 11 | D | 同上 | 8d. 文件被独占锁（`SQLITE_BUSY`） | 同上 | ★ |
| 12 | **D (59-61)** | `$pdo->query('SELECT * FROM accounts')` 抛异常 | **12a. 表名不是 `accounts`** | 同上 | ★（本地快照证实表名就叫 `accounts`） |
| 13 | D | 同上 | 12b. 表存在但 schema 损坏 | 同上 | ☆ |
| 14 | 无（**不抛也不报**） | 查询成功、`$rows` 仍空 | **14a. `accounts` 表 0 行**（库被新建/清空） | 设置页：`✓ 可读 · 0 个账号镜像` | ★★ |
| 15 | 无 | 同上 | **14b. 列名不是 `publisher_account_id`** → 第 55 行 `isset()` 全 false，**一行都不进 `$rows`，而且一个字都不抱怨** | 同上（假绿灯） | ★★ |
| 16 | 无 | 同上 | **14c. 列存在但值为 `NULL`** → `isset()` 对 NULL 返回 **false**，同样整行丢失 | 同上（假绿灯） | ★（本库该列 `NOT NULL DEFAULT 0`，已排除） |
| 17 | 无 | 查询成功、`$rows` 非空 | **17. 键形态对不上（§4.3 表）或该玩家 `publisher_account_id = 0`** → `player_one():354` 的 `isset()` 不中 | 详情页：`未找到（publisherId 对不上…）`，但设置页是 `✓ 可读 · 3 个账号镜像`（**这个组合才是真"对不上"**） | ★★ |

**读法**：
- 出口 1/7 走的是**早退**，`catch` 完全不参与 → **给 catch 加日志救不了本案**（这是 §1.6 的核心）。
- 出口 8/9/10/11/12/13 走 `catch`，但 `catch` 把 `$e` 整个丢掉 → 面板只会说"未找到"。
- 出口 14/15/16 **连异常都没有**，是最阴的一类。
- 出口 17 根本不是"返回空数组"，是"查到了但没匹配上"，可面板措辞和第 1 类**一模一样**。

### 5.2 WAL 这件事（修完 open_basedir 后要盯的）

`accounts.db` 头部字节 16-23：`10 00 02 02 00 40 20 20`
→ byte[18] `write_version=2`、byte[19] `read_version=2` → **库是 WAL 模式**（`PRAGMA journal_mode` 也回 `wal`）。

WAL + `PDO::SQLITE_OPEN_READONLY` 的规则（SQLite ≥3.22 有改善，但仍有坑）：

- 读连接**需要 `-shm` 共享内存索引**；若 `-shm` 不存在且**目录对 www 不可写**，连接可能直接 `SQLITE_CANTOPEN`；
- 桥接进程（bapatch）**正在写**这个库，所以线上几乎总有 `-wal` / `-shm` 在场；
- 但快照里 `work\ba\srv_live\20261118_0059\bapatch\data\` **只有 `accounts.db` 一个文件**（没有 `-wal` / `-shm`）——说明打包时按文件名拷的，**不能据此判断线上有没有**。

⇒ **修完 open_basedir 后必须复测这一步**，否则会从"文件读不到"变成"PDO 打不开"，而面板照样只说"未找到"。
兜底方案见 §7.1 里 `SQLITE_ATTR_OPEN_FLAGS` 的可选降级（改成普通读写连接 + `PRAGMA query_only=1`），或给 `-shm` 目录写权限。

---

## 6. 问题 3：`player_card_bindings()` + `card_players`

### 6.1 表不存在会自动建吗

**会，而且是每次访问都尝试。** `inc\players.php:91-134`：

```php
/** 确保 card_players 表存在（面板首次访问即自建，不依赖 install.php 重跑） */
function player_ensure_tables()
{
    static $done = false;
    if ($done) {
        return;
    }
    $done = true;                       // :98  ← 注意：在 try 之前就置位
    try {
        db_run("CREATE TABLE IF NOT EXISTS `card_players` ( ... )");   // :100-113
        db_run("CREATE TABLE IF NOT EXISTS `panel_ops` ( ... )");      // :115-130
    } catch (Throwable $e) {
        /* 表已存在或数据库不可用：不阻断页面 */                          // :131-133
    }
}
```

`player_card_bindings()`（第 174-186 行）第一件事就是 `player_ensure_tables();` 再 `SELECT * FROM card_players`，
所以**面板第一次点开玩家详情时就会建表**。

### 6.2 建表失败会怎样（三个叠加缺陷）

| 缺陷 | 位置 | 后果 |
|---|---|---|
| **① `$done = true` 在 `try` 之前** | `:98` | 一旦本次请求建表失败，同请求内**后续所有调用直接返回**，不再重试。一次失败 = 整页无表 |
| **② `catch` 完全静默** | `:131-133` | 失败原因（`CREATE` 权限不足 / 表名冲突 / 库不存在 / `sql_mode` 不兼容）**一个字都不留** |
| **③ 判定语义错** | `:132` 注释写"表已存在或数据库不可用" | 把「权限不足」和「表已存在」混为一谈，运维看了注释会以为没事 |

MySQL 用户 `ba_cardadmin`（`config.php:DB_USER`）**只有 DML 没有 DDL 权限**时，
`CREATE TABLE` 会报 `1142 - CREATE command denied to user 'ba_cardadmin'@'localhost'`，
被 `:131` 吃掉 → 接着 `SELECT * FROM card_players` 报 `1146 - Table doesn't exist` → 被 `:182-184` 吃掉 → 返回 `[]`。

**而 `sql\schema.sql` 里根本没有 `card_players`**（已逐行确认：`admins` / `sessions` / `cards` / `card_devices` / `login_logs` / `audit_logs` / `settings` / `login_attempts`，共 8 张，**无 `card_players`、无 `panel_ops`**）。
所以这张表**只能靠运行时自建**，一旦 DDL 权限被卡，就永远建不起来。

### 6.3 「绑定的卡密」为空的 4 种可能 —— 面板现在一种都分不出来

`inc\players.php:174-186`：

```php
function player_card_bindings()
{
    player_ensure_tables();                                  // 可能刚失败（静默）
    $out = array();
    try {
        foreach (db_all('SELECT * FROM card_players') as $r) {
            $out[(int)$r['card_id']] = $r;
        }
    } catch (Throwable $e) {
        return array();                                      // :183  ← 查询失败也是 []
    }
    return $out;
}
```

| 状态 | 代码路径 | 返回值 | 面板显示 |
|---|---|---|---|
| ① **表没建** | `CREATE` 失败(:131) → `SELECT` 抛异常 → `:183 return []` | `[]` | 「还没有绑定卡密。」 |
| ② **表建了但是空** | `SELECT` 成功返回 0 行 | `[]` | 「还没有绑定卡密。」 |
| ③ **查询失败**（无 SELECT 权限 / 库掉线 / 表结构变更） | `:183 return []` | `[]` | 「还没有绑定卡密。」 |
| ④ **绑定行存在，但 `cards` 表里那张卡已被删** | `player_one():359-364` 遍历的是 **`cards` 表**，`if (!isset($binding[$cid])) continue;` —— 反向的"绑定有、卡没有"**被静默跳过** | 该卡消失 | 「还没有绑定卡密。」 |

第 ④ 条很容易被忽略：`player_one()` 的外层循环是 `foreach ($cards as $c)`（第 360 行），
**绑定行只是被用来"过滤卡"**，从来不作为驱动表。所以
`card_players` 里有 5 行、`cards` 里那 5 个 id 都被删了 → 页面空，而 SQL 查 `card_players` 明明有 5 条。

### 6.4 面板上的三个分支完全同形

```php
// pages/player_detail.php:259-260
<?php if (!$p['cards']) { ?>
  <p class="muted small">还没有绑定卡密。绑定之后「玩家列表」就能按卡密查到这个人。</p>
```

`$p['cards']` 为 `[]` 的四个来源（① ② ③ ④）在这里**汇成同一个 `<p>`**，
而且文案还带**引导性**（"绑定之后…"），会让人误以为是"没绑过"而不是"读不到"。
**这就是要补的地方。**

---

## 7. 问题 4：3 步诊断顺序（面板里点几下定位）

### 7.1 `player_bridge_status()`（`pages\settings.php:332` 调，`inc\players.php:66-87` 实现）覆盖到哪

它返回 6 个字段：

```php
    $out = array(
        'path'           => $path,
        'exists'         => is_file($path),
        'readable'       => is_readable($path),
        'rows'           => 0,
        'error'          => '',
        'has_pdo_sqlite' => class_exists('PDO') && in_array('sqlite', PDO::getAvailableDrivers(), true),
    );
    if ($out['has_pdo_sqlite'] && $out['readable']) {
        $out['rows'] = count(player_bridge_accounts());
    } elseif (!$out['has_pdo_sqlite']) {
        $out['error'] = 'PHP 未启用 pdo_sqlite 扩展';
    } elseif (!$out['exists']) {
        $out['error'] = '文件不存在';
    } else {
        $out['error'] = 'PHP 用户无读权限（' . $path . '）';
    }
```

| 能覆盖 | 覆盖不到 |
|---|---|
| ✅ 路径配的是哪个（`path`） | ❌ **PDO 到底打开成功没有**（异常被 `:59` 吞掉，`rows` 只会是 0） |
| ✅ 文件存在与否（`exists`） | ❌ **表名对不对** |
| ✅ PHP 用户可读与否（`readable`） | ❌ **列名对不对**（`isset()` 静默丢行） |
| ✅ `pdo_sqlite` 装没装（`has_pdo_sqlite`） | ❌ **`rows=0` 到底是空库、连接失败、还是列名变了** |
| ✅ **行的数量**（`rows`，但只给数字不给原因） | ❌ **join 键对不对**（它根本不查 Shittim，没有可比对的 `publisherId`） |
| | ❌ **`card_players` / MySQL 侧的任何状态**（这函数完全不碰 MySQL） |

### 7.2 它最致命的两个盲区

**盲区 A：`rows=0` 时 `error` 是空串 ⇒ 假绿灯**

分支 1 的条件是 `has_pdo_sqlite && readable`，进去后**只赋 `rows`，不赋 `error`**。
所以连接失败 / 表名错 / 列名错 / 空库（上述出口 8~16）全都表现为：

```
setting.php:386  if ($brStatus['has_pdo_sqlite'] && $brStatus['readable'])
→ 渲染： ✓ 可读 · 0 个账号镜像
```

设置页 `pages\settings.php:385-393`：

```php
    <tr><th>桥接账号库</th><td>
      <?php if ($brStatus['has_pdo_sqlite'] && $brStatus['readable']) { ?>
        <span class="ok">✓ 可读</span> · <?php echo (int)$brStatus['rows']; ?> 个账号镜像
```

**「✓ 可读 · 0 个」是自相矛盾的**：能读却 0 行。它既可能是真空库，也可能是 PDO 根本没连上。

**盲区 B：`exists=false` 时把 `open_basedir` 谎报成"文件不存在"**

`is_file()` 在 open_basedir 拒绝时返回 **false**（只发 warning），
于是 `:72 exists = false` → `:81 elseif (!$exists)` → `:84 error = '文件不存在'`。
**文件明明在，PHP 说不在** —— 这句话会把运维引向"去找文件"，而不是"去改 open_basedir"。

### 7.3 3 步诊断法（面板里点，不用 SSH）

| 步 | 点哪里 | 看什么 | 判读 |
|---|---|---|---|
| **①** | 设置 → 「游戏服务端（玩家域）」→「**桥接账号库**」行（`settings.php:385`） | 「✓/✗」+ 文案 + 路径 | `✗ 文件不存在` → **open_basedir**（文件确实在，PHP 被挡）；`✗ PHP 用户无读权限（…）` → 真 chmod 问题；`✓ 可读 · N` → 进第②步；`✗ PHP 未启用 pdo_sqlite 扩展` → 装扩展 |
| **②** | 同区块下一行「**PHP 扩展**」（`settings.php:394-398`） | `pdo_sqlite` / `curl` / `json` 三个灯 + 上一行 `N 个账号镜像` | `pdo_sqlite` 红 → 出口 7；`✓ 可读 · 0 个` → 连接/表/列问题（出口 8/14/15），**这是假绿灯，不能信**；`✓ 可读 · 3 个` 且详情页仍"未找到" → 真·键对不上（出口 17） |
| **③** | 玩家详情 → 「**账号资料**」表第 2 行 `publisherId`（`player_detail.php:208`），对比「**桥接 / 卡密**」区第 1 行「桥接账号」（`player_detail.php:251`） | 这一页同时给出 `publisherId` 和"有没有匹配上" | 记下 `publisherId` 数值 → 拿它去 `accounts.db` 里 `SELECT * FROM accounts WHERE publisher_account_id=<值>`。**查到 → 键没问题，问题在读取链路（回第①步）；查不到 → 键真的对不上（出口 17）** |

**顺序为什么是 ①→②→③**：
① 判"路径层"（open_basedir / 权限，**本案命中**）；
② 判"驱动层"（扩展 / 连接 / 表 / 列，假绿灯在这里）；
③ 判"数据层"（键值）。
从便宜到贵、从全局到单点；① 一旦是红的，②③ 全都不用看。

### 7.4 补充：MySQL 那半块（`player_card_bindings`）自检没有覆盖

`player_bridge_status()` **完全不查 MySQL**。要判 §6.3 的 ①②③，面板里只有一条侧路：

> 玩家详情 → 随便点一次「封禁/解封」或「改货币」→ 看是否报"数据库连接失败"

但这只能证明"MySQL 连得上"，**证不了 `card_players` 存在**。
⇒ 所以 §8 的补丁 ④ 是必需的：必须给 `card_players` 加一个和 `player_bridge_status()` 对等的三态自检。

---

## 8. 问题 5：补丁方案（全部只给 diff，未落地）

### 8.0 通用约定

- 基准：**本地源码** `work\ba\cardadmin_php\`（`-p1`，从 `work\ba\cardadmin_php` 目录执行）
- 每个补丁附带：**改哪个文件 / 为什么 / 风险 / 回滚**
- 回滚统一用 `cp -a`（不用 `mv`，保留原件）：
  ```sh
  TS=$(date +%Y%m%d_%H%M%S)
  cp -a inc/players.php "inc/players.php.bak.$TS"     # 打之前
  # 回滚：
  cp -a inc/players.php.bak.<TS> inc/players.php      # 放回来
  ```
- ⚠️ 若 `patch` 报 `Hunk #N FAILED`（行号漂移，`settings.php` / `player_detail.php` 线上版与本地版不同），
  用 `patch -p1 --fuzz=3`，或按 hunk 里的**上下文原文**手工替换那几行。

---

### 补丁 ①a — `inc/players.php`：把真实原因记下来（第 30-63 行）

**为什么**：`player_bridge_accounts()` 的 4 个早退出口 + `catch` 全部只返回 `[]`，不留下任何原因；
第 42 行那次早退**连异常都不产生**，所以"给 catch 加日志"救不了。
必须让每一个出口都写一条人能读的原因，并把 open_basedir 与"真不存在"**显式区分**。

```diff
--- a/inc/players.php
+++ b/inc/players.php
@@ -28,6 +28,104 @@
 }
 
+/** 路径是否在 open_basedir 允许范围内（open_basedir 为空 = 不限制） */
+function player_path_in_open_basedir($path)
+{
+    $ob = trim((string)ini_get('open_basedir'));
+    if ($ob === '') {
+        return true;
+    }
+    $rp  = @realpath($path);
+    $p   = ($rp !== false) ? $rp : (string)$path;
+    $sep = (DIRECTORY_SEPARATOR === '\\') ? ';' : ':';
+    foreach (explode($sep, $ob) as $dir) {
+        $dir = rtrim(trim($dir), '/');
+        if ($dir === '') {
+            continue;
+        }
+        if ($p === $dir || strpos($p, $dir . '/') === 0) {
+            return true;
+        }
+    }
+    return false;
+}
+
+/**
+ * publisherId 归一：统一成「十进制整数字符串」。
+ *
+ * 三个来源的类型并不一致：
+ *   · Shittim admin API → json_decode 出来是 int（64 位 PHP 内 11 位数仍精确）
+ *   · accounts.db       → pdo_sqlite 给 int（PHP >= 8.1）或 string（< 8.1）
+ *   · card_players      → MySQL BIGINT，PDO 给 int 或 string
+ * PHP 数组键会把「规范十进制整数字符串」隐式折成 int，所以 "314816420" 与 314816420
+ * 能对上；但 "0314816420" / " 314816420" / "3.1481642E+8" 不会，会静默变成一个
+ * 永远匹配不上的字符串键。这里先把它们收敛到同一形态。
+ *
+ * @return string '' = 不是合法 publisherId
+ */
+function player_pub_key($v)
+{
+    if ($v === null || $v === '') {
+        return '';
+    }
+    if (is_float($v)) {
+        if (!is_finite($v) || abs($v) > 9007199254740992.0) {
+            return '';                        /* 已超 2^53，精度不可信：宁可对不上也不改数 */
+        }
+        $v = (int)$v;
+    }
+    if (is_int($v)) {
+        return (string)$v;
+    }
+    $s = trim((string)$v);
+    if ($s === '') {
+        return '';
+    }
+    if (preg_match('/^[+]?\d+$/', $s)) {
+        return (string)(int)$s;               /* 去前导零、去 + 号 */
+    }
+    if (preg_match('/^[+]?\d+(\.\d+)?[eE][+-]?\d+$/', $s)) {
+        $f = (float)$s;                       /* 科学计数法串 */
+        if (!is_finite($f) || abs($f) > 9007199254740992.0) {
+            return '';
+        }
+        return (string)(int)$f;
+    }
+    return '';
+}
+
+/**
+ * 桥接镜像上一次读取失败的**真实原因**（'' = 没失败）。
+ * 原来 catch (Throwable) 把异常整个吃掉，页面只剩一句
+ * 「未找到（publisherId 对不上 accounts.db）」，把 open_basedir 拒绝 / 无读权限 /
+ * 缺 pdo_sqlite / 表名变了 / 列名变了 / WAL 只读打不开 这些完全不同的故障压成同一现象。
+ */
+function player_bridge_error()
+{
+    return isset($GLOBALS['__ca_bridge_err']) ? (string)$GLOBALS['__ca_bridge_err'] : '';
+}
+
 /**
  * 读桥接账号镜像（只读）。失败返回 []，面板降级但不崩。
  * @return array publisher_account_id => row
  */
 function player_bridge_accounts()
 {
     static $rows = null;
     if ($rows !== null) {
         return $rows;
     }
     $rows = array();
+    $GLOBALS['__ca_bridge_err'] = '';
     $path = player_accounts_db_path();
     if (!is_file($path) || !is_readable($path)) {
+        /* open_basedir 命中时 is_file()/is_readable() 同样返回 false，只抛 E_WARNING，
+           所以必须显式区分「被 open_basedir 挡住」和「真的不存在 / 没权限」。 */
+        $GLOBALS['__ca_bridge_err'] = player_path_in_open_basedir($path)
+            ? '文件不存在或 PHP 用户无读权限：' . $path
+            : 'open_basedir 禁止访问：' . $path . '（允许范围：' . ini_get('open_basedir') . '）';
         return $rows;
     }
     if (!class_exists('PDO') || !in_array('sqlite', PDO::getAvailableDrivers(), true)) {
+        $GLOBALS['__ca_bridge_err'] = 'PHP 未启用 pdo_sqlite 扩展';
+        return $rows;
+    }
+    if (!defined('PDO::SQLITE_ATTR_OPEN_FLAGS') || !defined('PDO::SQLITE_OPEN_READONLY')) {
+        /* PHP < 7.3 没有这两个常量：PHP 8 抛 Error（可捕获），PHP 7 是致命错误（白屏） */
+        $GLOBALS['__ca_bridge_err'] = 'PHP ' . PHP_VERSION . ' 缺少 PDO::SQLITE_ATTR_OPEN_FLAGS 常量';
         return $rows;
     }
     try {
         $pdo = new PDO('sqlite:' . $path, null, null, array(
             PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
             PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
             PDO::SQLITE_ATTR_OPEN_FLAGS  => PDO::SQLITE_OPEN_READONLY,
         ));
+        $n = 0;
         foreach ($pdo->query('SELECT * FROM accounts') as $r) {
+            $n++;
             if (isset($r['publisher_account_id'])) {
-                $rows[(string)$r['publisher_account_id']] = $r;
+                $k = player_pub_key($r['publisher_account_id']);
+                if ($k !== '') {
+                    $rows[$k] = $r;
+                }
             }
         }
+        if ($n === 0) {
+            $GLOBALS['__ca_bridge_err'] = 'accounts 表能查，但 0 行';
+        } elseif ($rows === array()) {
+            $GLOBALS['__ca_bridge_err'] = 'accounts 表有 ' . $n . ' 行，但没有可用的 publisher_account_id 列'
+                . '（列名变了，或该列全为 NULL —— isset() 对 NULL 返回 false）';
+        }
     } catch (Throwable $e) {
+        $GLOBALS['__ca_bridge_err'] = 'PDO 打开/查询 accounts 失败：' . $e->getMessage();
         $rows = array();
     }
     return $rows;
 }
```

- **改哪个文件**：`inc\players.php`（本地/线上**同哈希**，两边通用）
- **为什么**：把 4 个早退出口 + catch 的内容变成可读字符串；新增 `player_bridge_error()` 供页面取用；`player_pub_key()` 做键归一（顺带满足补丁 ②）。
- **风险**：**极低**
  - 行为完全不变（所有失败仍 `return array()`），只是多写一个全局变量；
  - `player_pub_key()` 对 `314816420` 的输出与原来的 `(string)` 一致；
  - 新增 `defined('PDO::SQLITE_ATTR_OPEN_FLAGS')` 分支在 PHP 8.2.31 上恒为真，等于 no-op；
  - 唯一语义变化：原来非法键（`''`）会占一个 `""` 键，现在被跳过 —— 只会让结果更干净。
- **回滚**：
  ```sh
  cp -a inc/players.php.bak.<TS> inc/players.php
  ```

---

### 补丁 ①b — `pages\settings.php`：把真实原因显示出来

**为什么**：`$brStatus['error']` 现在只在"没 pdo_sqlite / 不存在 / 不可读"三种情况有值；
`✓ 可读 · 0 个` 与"连接失败"无法区分（§7.2 盲区 A）。要把 `player_bridge_error()` 挂上去。

> ⚠️ **基准 = 线上快照版**（`srv_live\20261118_0059\ba_cardadmin\pages\settings.php`，20,164 B）。
> 本地版对应位置在 **385-393 行**（内容一致，行号可能因新增功能漂移；打之前先 `grep -n "桥接账号库" pages/settings.php` 确认）。

```diff
--- a/pages/settings.php
+++ b/pages/settings.php
@@ -384,10 +384,18 @@
       <tr><th>桥接账号库</th><td>
         <?php if ($brStatus['has_pdo_sqlite'] && $brStatus['readable']) { ?>
-          <span class="ok">✓ 可读</span> · <?php echo (int)$brStatus['rows']; ?> 个账号镜像
+          <?php if ($brStatus['rows'] > 0) { ?>
+            <span class="ok">✓ 可读</span> · <?php echo (int)$brStatus['rows']; ?> 个账号镜像
+          <?php } else { ?>
+            <span class="warn">⚠ 文件可读，但一行都没读出来</span> · 0 个账号镜像
+          <?php } ?>
           <br><code class="small"><?php echo e($brStatus['path']); ?></code>
+          <?php if (player_bridge_error() !== '') { ?>
+            <br><span class="bad small">原因：<?php echo e(player_bridge_error()); ?></span>
+          <?php } ?>
         <?php } else { ?>
           <span class="warn">✗ <?php echo e($brStatus['error']); ?></span>
           <br><code class="small"><?php echo e($brStatus['path']); ?></code>
+          <?php if (player_bridge_error() !== '') { ?>
+            <br><span class="bad small">原因：<?php echo e(player_bridge_error()); ?></span>
+          <?php } ?>
         <?php } ?>
       </td></tr>
```

- **改哪个文件**：`pages\settings.php`
- **为什么**：把「✓ 可读 · 0」这个**假绿灯**拆成两种可见状态；把 open_basedir 的真实原因直接打在页面上，运维不用登服务器就能判。
- **风险**：**低**
  - 纯展示层，无写操作、无 SQL、无副作用；
  - `e()` 转义（`inc\helpers.php:18`），不会引入 XSS —— 但注意 `$e->getMessage()` 里可能带路径，**属于信息泄露面**，务必确认设置页已在 `require_login()` 之后（是，`settings.php:14`）；
  - `player_bridge_error()` 若不存在（只打了 ①b 没打 ①a）会 **fatal**。**必须 ①a 先于 ①b 上线**。
- **回滚**：
  ```sh
  cp -a pages/settings.php.bak.<TS> pages/settings.php
  ```

---

### 补丁 ② — publisherId 归一的落点（已含在 ①a 的 `player_pub_key()`，这里给全部调用点）

**为什么**：`player_one()` 与 `player_roster()` 各自手写 `(string)(int)`，
`player_bridge_accounts()` 只有 `(string)` —— **三处口径不统一**，且都没处理前导零/科学计数法。
统一走 `player_pub_key()` 后，键形态问题被一次性收口。

```diff
--- a/inc/players.php
+++ b/inc/players.php
@@ -268,8 +268,8 @@
             'source'    => (string)$b['source'],
         );
-        $byPub[(string)(int)$b['publisher_account_id']][] = $entry;
-        $byServer[(string)(int)$b['server_id']][] = $entry;
+        $byPub[player_pub_key($b['publisher_account_id'])][] = $entry;
+        $byServer[(string)(int)$b['server_id']][] = $entry;
     }
 
     $q     = isset($filters['q']) ? trim((string)$filters['q']) : '';
@@ -279,7 +279,7 @@
     $rows = array();
     foreach ($r['data'] as $a) {
         $sid = (int)$a['serverId'];
-        $pub = isset($a['publisherAccountId']) ? (string)(int)$a['publisherAccountId'] : '';
+        $pub = player_pub_key(isset($a['publisherAccountId']) ? $a['publisherAccountId'] : null);
 
         $br = ($pub !== '' && isset($bridge[$pub])) ? $bridge[$pub] : null;
 
@@ -348,7 +348,7 @@
     }
     $d   = $r['data'];
-    $pub = isset($d['publisherAccountId']) ? (string)(int)$d['publisherAccountId'] : '';
+    $pub = player_pub_key(isset($d['publisherAccountId']) ? $d['publisherAccountId'] : null);
 
     $bridge = player_bridge_accounts();
     $br     = ($pub !== '' && isset($bridge[$pub])) ? $bridge[$pub] : null;
@@ -363,7 +363,7 @@
             }
             $b = $binding[$cid];
-            if ((string)(int)$b['publisher_account_id'] === $pub || (int)$b['server_id'] === (int)$serverId) {
+            if (player_pub_key($b['publisher_account_id']) === $pub || (int)$b['server_id'] === (int)$serverId) {
                 $myCards[] = array(
                     'card_id'   => $cid,
                     'card_key'  => (string)$c['card_key'],
```

- **改哪个文件**：`inc\players.php`
- **为什么**：三处口径统一；把 `(string)(int)` 这个"看起来对但其实会丢形态信息"的写法换成一个会说清楚"非数字就不是 publisherId"的函数。
- **风险**：**低–中**
  - `player_pub_key()` 对合法 int 的输出 = 原 `(string)(int)`，**行为等价**；
  - **风险点**：若某玩家 `publisherAccountId` 真的是非数字（数据脏），原来是 `"0"`（`(int)"abc"` → 0），
    新逻辑返回 `''` → 该玩家 `$pub=''` → 不再参与桥接/绑定匹配。**这是有意收紧**，会改变极少数脏数据的展示；
  - 建议上线前先跑：`SELECT DISTINCT publisher_account_id FROM card_players WHERE publisher_account_id NOT REGEXP '^[0-9]+$';` 确认返回 0 行。
- **回滚**：
  ```sh
  cp -a inc/players.php.bak.<TS> inc/players.php
  ```

---

### 补丁 ③ — 同一玩家多张卡 / 多台设备时全部列出

**为什么**：
1. **`$bridge` 是单行** —— `player_bridge_accounts()` 用 `$rows[$key] = $r` 覆盖写（`players.php:56`），
   同一 `publisher_account_id` 在 `accounts.db` 里有多行时（本部署真实形态：**一个 publisher 对多台设备**，
   见 `PRODUCTION_HARDENING_20261118.md` §3.4「两台手机映射到同一个账号」），**只剩最后解析到的那一行**，
   设备号/登录次数/最后登录都是随机"最后一条"，不是"最新一条"。
2. **`$binding[$cid]` 单行是设计如此**（`players.php:110` `UNIQUE KEY uk_card_players_card (card_id)`），
   但 `player_one()` 是**以 `cards` 表为驱动表**（`:360`），导致"绑定存在、卡已删"的行整条消失（§6.3 状态 ④），
   **面板上完全看不见"有绑定但卡没了"**。

```diff
--- a/inc/players.php
+++ b/inc/players.php
@@ -34,6 +34,13 @@
  * 读桥接账号镜像（只读）。失败返回 []，面板降级但不崩。
  * @return array publisher_account_id => row
  */
+/** 同一 publisherId 在 accounts.db 里的**全部**镜像行（多设备 / 多 server_id 全列） */
+function player_bridge_all($pub)
+{
+    player_bridge_accounts();                /* 触发一次填充（static 缓存） */
+    $k = player_pub_key($pub);
+    return ($k !== '' && isset($GLOBALS['__ca_bridge_multi'][$k])) ? $GLOBALS['__ca_bridge_multi'][$k] : array();
+}
+
 function player_bridge_accounts()
 {
     static $rows = null;
@@ -50,12 +57,22 @@
         ));
         $n = 0;
+        $GLOBALS['__ca_bridge_multi'] = array();
         foreach ($pdo->query('SELECT * FROM accounts') as $r) {
             $n++;
             if (isset($r['publisher_account_id'])) {
                 $k = player_pub_key($r['publisher_account_id']);
                 if ($k !== '') {
-                    $rows[$k] = $r;
+                    $GLOBALS['__ca_bridge_multi'][$k][] = $r;
+                    /* 单行视图保留「最新登录」的那一行，而不是「最后解析到」的那一行 */
+                    if (!isset($rows[$k])
+                        || strcmp((string)(isset($r['last_login_at']) ? $r['last_login_at'] : ''),
+                                  (string)(isset($rows[$k]['last_login_at']) ? $rows[$k]['last_login_at'] : '')) > 0) {
+                        $rows[$k] = $r;
+                    }
                 }
             }
         }
@@ -378,10 +395,26 @@
     } catch (Throwable $e) {
         $myCards = array();
     }
 
+    /* 绑定行存在、但 cards 表里那张卡已被删：原来整条静默消失，这里捡回来给页面提示 */
+    $orphanCards = array();
+    foreach ($binding as $cid => $b) {
+        if (player_pub_key($b['publisher_account_id']) !== $pub && (int)$b['server_id'] !== (int)$serverId) {
+            continue;
+        }
+        $seen = false;
+        foreach ($myCards as $mc) {
+            if ((int)$mc['card_id'] === (int)$cid) {
+                $seen = true;
+                break;
+            }
+        }
+        if (!$seen) {
+            $orphanCards[] = array('card_id' => (int)$cid, 'note' => (string)$b['note']);
+        }
+    }
+
     return array(
         'ok'     => true,
         'error'  => '',
         'detail' => $d,
         'bridge' => $br,
+        'bridges' => player_bridge_all($pub),
         'cards'  => $myCards,
+        'orphan_cards' => $orphanCards,
         'state'  => isset($d['state']) ? (string)$d['state'] : '',
     );
 }
```

**配套（`pages\player_detail.php`，第 248-256 行）：把单行表换成"逐行列出 + 总数"**

> ⚠️ **基准 = 线上快照版**（`player_detail.php` 21,032 B）。本地版在 **248-256 行**，内容一致。

```diff
--- a/pages/player_detail.php
+++ b/pages/player_detail.php
@@ -247,14 +247,34 @@
   <section class="card">
     <div class="card-h"><h2>桥接 / 卡密</h2></div>
-    <table class="kv">
-      <tr><th>桥接账号</th><td><?php echo $bridge ? ('<code>' . e((string)$bridge['server_id']) . '</code>') : '<span class="muted">未找到（publisherId 对不上 accounts.db）</span>'; ?></td></tr>
-      <tr><th>设备号</th><td><?php echo $bridge && $bridge['device_unique_id'] !== '' ? '<code class="small">' . e((string)$bridge['device_unique_id']) . '</code>' : '<span class="muted">—</span>'; ?></td></tr>
-      <tr><th>dev_id</th><td><?php echo $bridge ? '<code class="small">' . e((string)$bridge['dev_id']) . '</code>' : '—'; ?></td></tr>
-      <tr><th>登录次数</th><td><?php echo $bridge ? number_format((int)$bridge['login_count']) : '—'; ?></td></tr>
-      <tr><th>最后登录</th><td><?php echo $bridge ? e(player_dt((string)$bridge['last_login_at'])) : '—'; ?></td></tr>
-    </table>
+    <?php $bridges = isset($p['bridges']) ? $p['bridges'] : ($bridge ? array($bridge) : array()); ?>
+    <?php if (!$bridges) { ?>
+      <p class="muted small">accounts.db 里没有 publisherId = <code><?php echo e(isset($d['publisherAccountId']) ? (string)$d['publisherAccountId'] : '—'); ?></code> 的行。</p>
+      <?php if (player_bridge_error() !== '') { ?>
+        <p class="bad small">读取失败的真实原因：<?php echo e(player_bridge_error()); ?></p>
+      <?php } ?>
+      <?php if ($brStatusRows = count(player_bridge_accounts())) { ?>
+        <p class="muted small">（但 accounts.db 本身读到了 <?php echo (int)$brStatusRows; ?> 行，说明是键对不上，不是读不到。）</p>
+      <?php } ?>
+    <?php } else { ?>
+      <p class="muted small">accounts.db 命中 <b><?php echo count($bridges); ?></b> 行（同一 publisher 多设备会多行）：</p>
+      <div class="table-wrap">
+      <table class="tbl">
+        <thead><tr><th>server_id</th><th>设备号</th><th>dev_id</th><th>登录次数</th><th>最后登录</th></tr></thead>
+        <tbody>
+        <?php foreach ($bridges as $b1) { ?>
+          <tr>
+            <td><code><?php echo e((string)$b1['server_id']); ?></code></td>
+            <td class="small"><?php echo isset($b1['device_unique_id']) && $b1['device_unique_id'] !== '' ? '<code class="small">' . e((string)$b1['device_unique_id']) . '</code>' : '<span class="muted">—</span>'; ?></td>
+            <td class="small"><?php echo isset($b1['dev_id']) ? e((string)$b1['dev_id']) : '—'; ?></td>
+            <td><?php echo number_format((int)$b1['login_count']); ?></td>
+            <td><?php echo e(player_dt((string)$b1['last_login_at'])); ?></td>
+          </tr>
+        <?php } ?>
+        </tbody>
+      </table>
+      </div>
+    <?php } ?>
 
     <h3 style="margin-top:14px">绑定的卡密</h3>
     <?php if (!$p['cards']) { ?>
       <p class="muted small">还没有绑定卡密。绑定之后「玩家列表」就能按卡密查到这个人。</p>
+      <?php if (!empty($p['orphan_cards'])) { ?>
+        <p class="bad small">有 <?php echo count($p['orphan_cards']); ?> 条绑定指向的卡已在 cards 表里被删除（card_id：<?php echo e(implode('、', array_map(function ($x) { return $x['card_id']; }, $p['orphan_cards']))); ?>），所以这里不显示。</p>
+      <?php } ?>
     <?php } else { ?>
```

- **改哪个文件**：`inc\players.php` + `pages\player_detail.php`
- **为什么**：
  - `$bridge` 单行在多设备部署下**必丢数据**，且丢的是"除最后一条之外"的所有设备；
  - `player_one()` 以 `cards` 为驱动表 → "绑定存在、卡已删"的孤儿绑定在面板上**完全隐形**；
  - 同时把「键对不上」和「读不到」在**同一个页面**上分开表述（现在两句混在一句里）。
- **风险**：**中**
  - `player_detail.php` 是**结构性改动**（`<table class="kv">` 5 行 → 动态 `<table class="tbl">`），
    若 `$b1['device_unique_id']` 缺列会走 `isset` 兜底，不会 notice；
  - **强烈建议**：`player_one()` 新增的 `bridges` / `orphan_cards` 两个 key 是**新增**，
    `player_roster()` 不消费它们，`cards.php` 也不消费 → 其他页面不受影响；
  - 唯一行为变化：`$bridge` 现在取"最新登录"而不是"最后解析"，同一 publisher 多设备时**显示的数字会变**（变正确）；
  - `player_bridge_all()` 依赖 `$GLOBALS['__ca_bridge_multi']`，若 `player_bridge_accounts()` 走了早退（读不到），
    该全局未定义 → `isset()` 兜底返回 `[]`，不报错。
- **回滚**：
  ```sh
  cp -a inc/players.php.bak.<TS> inc/players.php
  cp -a pages/player_detail.php.bak.<TS> pages/player_detail.php
  ```

---

### 补丁 ④ — `card_players` 三态可见（**这条是 §6 要求补的**）

**为什么**：「表没建 / 表空 / 查询失败 / 卡已删」四态在 `player_detail.php:259` 汇成一个 `<p>`。
根因是 `player_ensure_tables()` 的 `$done = true` 前置（`:98`）+ 静默 catch（`:131`），
以及 `player_card_bindings()` 的 `catch → array()`（`:183`）。要给它们各留一条可读状态。

```diff
--- a/inc/players.php
+++ b/inc/players.php
@@ -91,16 +91,30 @@
 /** 确保 card_players 表存在（面板首次访问即自建，不依赖 install.php 重跑） */
 function player_ensure_tables()
 {
     static $done = false;
     if ($done) {
         return;
     }
-    $done = true;
+    /* 注意：$done 移到 try 成功之后。原来在 try 之前置位，一次建表失败就整页不再重试，
+       而且失败原因被下面的 catch 吃掉，面板只剩「还没有绑定卡密」。 */
     try {
         db_run("CREATE TABLE IF NOT EXISTS `card_players` (
             `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
             `card_id` INT UNSIGNED NOT NULL,
             `publisher_account_id` BIGINT NOT NULL DEFAULT 0,
             `server_id` BIGINT NOT NULL DEFAULT 0,
             `source` VARCHAR(16) NOT NULL DEFAULT 'manual' COMMENT 'manual / auto / device',
             `note` VARCHAR(255) NOT NULL DEFAULT '',
             `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
             `created_by` VARCHAR(64) NOT NULL DEFAULT '',
             PRIMARY KEY (`id`),
             UNIQUE KEY `uk_card_players_card` (`card_id`),
             KEY `idx_card_players_pub` (`publisher_account_id`),
             KEY `idx_card_players_sid` (`server_id`)
         ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='卡密与玩家的绑定'");
 
         db_run("CREATE TABLE IF NOT EXISTS `panel_ops` (
             `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
             `batch_id` CHAR(16) NOT NULL DEFAULT '',
             `action` VARCHAR(32) NOT NULL DEFAULT '',
             `targets` TEXT NULL,
             `payload` TEXT NULL,
             `ok_count` INT NOT NULL DEFAULT 0,
             `fail_count` INT NOT NULL DEFAULT 0,
             `admin_name` VARCHAR(64) NOT NULL DEFAULT '',
             `ip` VARCHAR(45) NOT NULL DEFAULT '',
             `ts` INT UNSIGNED NOT NULL DEFAULT 0,
             PRIMARY KEY (`id`),
             KEY `idx_panel_ops_batch` (`batch_id`),
             KEY `idx_panel_ops_ts` (`ts`),
             KEY `idx_panel_ops_action` (`action`)
         ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='玩家域写操作批次记录'");
+        $GLOBALS['__ca_card_players_err'] = '';
+        $done = true;
     } catch (Throwable $e) {
-        /* 表已存在或数据库不可用：不阻断页面 */
+        /* 不阻断页面，但必须留下原因（权限不足 / 库不可用 / sql_mode 不兼容） */
+        $GLOBALS['__ca_card_players_err'] = '建表失败：' . $e->getMessage();
     }
 }
+
+/** card_players 的可用性：'' = 正常；否则是可读的失败原因（给设置页/详情页用） */
+function player_card_players_error()
+{
+    player_ensure_tables();
+    return isset($GLOBALS['__ca_card_players_err']) ? (string)$GLOBALS['__ca_card_players_err'] : '';
+}
 
 /** 记一批玩家域写操作（发奖/改货币/封禁/GM 命令） */
 function panel_op_log($action, $targets, $payload, $okCount, $failCount, $batchId = '')
```

```diff
--- a/inc/players.php
+++ b/inc/players.php
@@ -174,14 +174,26 @@
 /** card_id => ['publisher_account_id','server_id','source','note','created_at'] */
 function player_card_bindings()
 {
     player_ensure_tables();
     $out = array();
     try {
         foreach (db_all('SELECT * FROM card_players') as $r) {
             $out[(int)$r['card_id']] = $r;
         }
     } catch (Throwable $e) {
+        /* 表没建 / 无 SELECT 权限 / 库掉线：以前一律 return []，与「表是空的」无法区分 */
+        $GLOBALS['__ca_card_players_err'] = '查询 card_players 失败：' . $e->getMessage();
         return array();
     }
+    if ($out === array()) {
+        $GLOBALS['__ca_card_players_err'] = 'card_players 表存在，但没有绑定记录（表是空的）';
+    } else {
+        $GLOBALS['__ca_card_players_err'] = '';
+    }
     return $out;
 }
```

**配套（`pages\player_detail.php`，第 258-261 行）**

```diff
--- a/pages/player_detail.php
+++ b/pages/player_detail.php
@@ -255,9 +255,14 @@
     <h3 style="margin-top:14px">绑定的卡密</h3>
     <?php if (!$p['cards']) { ?>
       <p class="muted small">还没有绑定卡密。绑定之后「玩家列表」就能按卡密查到这个人。</p>
+      <?php $cpErr = player_card_players_error(); ?>
+      <?php if ($cpErr !== '') { ?>
+        <p class="bad small">诊断：<?php echo e($cpErr); ?></p>
+      <?php } else { ?>
+        <p class="muted small">（card_players 可查、无异常，确认是「真的没绑过」。）</p>
+      <?php } ?>
     <?php } else { ?>
```

**配套（`pages\settings.php`，加一行自检，紧跟在「桥接账号库」行之后）**

```diff
--- a/pages/settings.php
+++ b/pages/settings.php
@@ -393,6 +393,13 @@
     </td></tr>
+    <tr><th>card_players</th><td>
+      <?php $cpE = player_card_players_error(); ?>
+      <?php if ($cpE === '') { ?>
+        <span class="ok">✓ 可用</span> · <?php echo count(player_card_bindings()); ?> 条绑定记录
+      <?php } else { ?>
+        <span class="warn">✗ <?php echo e($cpE); ?></span>
+      <?php } ?>
+    </td></tr>
     <tr><th>PHP 扩展</th><td>
```

- **改哪个文件**：`inc\players.php` + `pages\player_detail.php` + `pages\settings.php`
- **为什么**：把 §6.3 的四态**变成四种可见文案**；`$done` 后移让"一次失败"不再锁死整页；给设置页加一个和 `player_bridge_status()` 对等的 MySQL 侧自检。
- **风险**：**中**
  - `$done = true` 从 try 前移到 try 后：**建表失败时每次访问都会重试**。
    正常情况下 `CREATE TABLE IF NOT EXISTS` 是幂等的、开销极小，但**权限不足时每页会多一次失败的 DDL + 一条 warning**。
    影响可接受（比"永久静默"好），但要知道这个代价；
  - `player_card_players_error()` 内部又调 `player_ensure_tables()`，与 `player_card_bindings()` 形成**一次嵌套调用**（第二次因 `$done` 直接返回），无死循环；
  - `card_players 表存在但没有绑定记录` 这条会写进全局变量 —— **注意它会被"真的空表"和"刚清空"共用**，属于可接受的措辞；
  - 展示端新增两处 `player_card_players_error()` 调用，**必须 ①a 的 `e()` 已存在**（它是 `helpers.php:18`，一直都在）。
- **回滚**：
  ```sh
  cp -a inc/players.php.bak.<TS> inc/players.php
  cp -a pages/player_detail.php.bak.<TS> pages/player_detail.php
  cp -a pages/settings.php.bak.<TS> pages/settings.php
  ```

---

### 补丁 ⑤ — `.user.ini`（**真正的根因修复，不是 .php**）

**为什么**：所有 §8 的 .php 补丁都只是**让故障可见**，一条都不解决"读不到"。
真正让 `$bridge` 恒为 `null` 的是 open_basedir 白名单少了 `/www/wwwroot/bapatch/`。

```diff
--- a/.user.ini
+++ b/.user.ini
@@ -1 +1 @@
-open_basedir=/www/wwwroot/ba_cardadmin/:/tmp/:/www/wwwroot/ba_sdk/
+open_basedir=/www/wwwroot/ba_cardadmin/:/tmp/:/www/wwwroot/ba_sdk/:/www/wwwroot/bapatch/
```

- **改哪个文件**：`/www/wwwroot/ba_cardadmin/.user.ini`（**线上配置文件，不在本仓库 .php 内**）
- **为什么**：面板只读地需要 `accounts.db`，而它在 `/www/wwwroot/bapatch/data/` 下。不加这个目录，任何 .php 补丁都无解。
- **风险**：**低（但要知道边界）**
  - 只**增加**一个只读目录，不扩大写权限面太多 —— 但注意：**open_basedir 是路径级、不是操作级**，
    加进去后 PHP 进程对该目录下的**任何文件都可读可写（取决于 unix 权限）**。
    `bapatch/data/` 里还有 `accounts.db`（桥接真源）⇒ **面板代码一旦被 SSRF/RCE 利用，可读范围扩到了账号库**。
    缓解：`chown root:www /www/wwwroot/bapatch/data && chmod 750`（www 只读，不能改库）；
  - `.user.ini` 有 `user_ini.cache_ttl`（默认 **300 秒**），改完**要等 5 分钟或 reload php-fpm** 才生效，
    否则会以为"改了没用"；
  - 这个文件**很可能被宝塔面板的「防跨站攻击」开关覆盖**，重新打开一次面板设置会把你的改动冲掉 ⇒ 要在宝塔 UI 里加，不要只手改文件。
- **回滚**：
  ```sh
  cp -a /www/wwwroot/ba_cardadmin/.user.ini.bak.<TS> /www/wwwroot/ba_cardadmin/.user.ini
  # 或直接退回快照里那份：
  # cp -a .user.ini.bak.1794777086 .user.ini     （注意：那份连 ba_sdk 都没有，会更糟）
  ```

> 🔁 补丁 ⑤ 与 ⑧ 的关系：⑤ 解决"`is_file()` 判 false"，**不解决**"WAL 库只读打开失败"（§5.2）。
> ⑤ 上线后**必须复测**；若复测发现 PDO 仍打不开，按 §5.2 的兜底（给目录写权限让 SQLite 建 `-shm`，
> 或把 `SQLITE_ATTR_OPEN_FLAGS => SQLITE_OPEN_READONLY` 换成普通连接 + `PRAGMA query_only=1`）。

---

## 9. 问题 6：不该动的地方（**一个都不许碰**）

面板这几层是对的，本次故障与它们无关，任何"顺手优化"都别做：

| 层 | 位置 | 为什么不能动 |
|---|---|---|
| **PDO 预处理** | `inc\db.php:143-148` `db_run()` 全部 `prepare()+execute($params)`；`:117` `ATTR_EMULATE_PREPARES => false`；`:118` `ATTR_STRINGIFY_FETCHES => false` | 真正参数化、禁模拟预处理 = 防注入的根。**不要为了"方便"改成拼接 SQL**（本报告所有补丁都保持了参数化，`player_ensure_tables()` 的 DDL 是常量字符串、无外部输入） |
| **CSRF** | `inc\auth.php:437` `csrf_field()` / `:460` `require_post_csrf()` / `:520` `action_token_field()` / `:529` `action_token_check()` | 每个 POST 入口都先 `require_post_csrf()`（`player_detail.php:20`、`settings.php:24`）；高危动作再加一次性 `action_token`（`pd_cur` / `pd_cmd`）。**不要在新增表单里漏 `<?php echo csrf_field(); ?>`** —— 补丁 ③④ 的 diff 不新增任何 `<form>`，所以不受影响 |
| **登录限速** | `inc\auth.php:186-196`（`login_attempts` 按 IP 计数）、`:190` `LOGIN_MAX_FAIL`（`db.php:72` = 5 次）、`:196` `LOGIN_LOCK_SEC`（`db.php:75` = 600 秒）、`:238` 成功后清计数 | 防爆破的实体。**不要为提高"体验"放宽阈值** |
| **会话轮换 / 自定义 token** | `inc\auth.php` 自建 `sessions` 表（`schema.sql:30-42`），不落 PHP 原生 session；`APP_SECRET`/`SESSION_TTL`（`db.php:59-64`） | 规避"session 目录不可写"的设计，且 `token` 是 32 字节随机 hex。**不要改回 `$_SESSION`** |
| **密码哈希** | `inc\auth.php:650/658` `hash_hmac('sha256', $pass, $salt)` 再 `password_hash(..., PASSWORD_BCRYPT)`；`:211-213` `password_verify` | 双保险设计。**不要"简化"成单层 md5** |
| **输出转义** | `inc\helpers.php:18` `e()`；`player_detail.php` 通篇 `e(...)` | 所有回显都过 `e()`。补丁 ③④ 新增的输出同样走 `e()` / `(int)`，**不要图省事 echo 原值** |
| **整型入参** | `inc\helpers.php:48` `get_int()` / `:55` `post_int()`（带 min/max） | `$sid = get_int('sid', 0, 1)`（`player_detail.php:15`）。补丁里新增的比较都用 `(int)` 归一 |
| **写操作走 API** | `inc\ba.php` 全部写操作打 `/api/admin/*`，**从不直接写 `shittim.sqlite3`**（`players.php:10` 注释、`ba.php:322-416`） | 派生字段/JSON 形状由 EF Core 保证。**不要为了"快"去直连 Shittim 的库** |
| **`accounts.db` 只读** | `inc\players.php:49-53` `SQLITE_OPEN_READONLY` | 桥接真源，面板只许读。**任何补丁都不得对它开写**（§8 补丁⑤ 的风险缓解也是往"限制写"方向走） |
| **审计日志** | `inc\auth.php` `audit_log()`；所有写操作都记（如 `player_detail.php:33-35, 50-51, 91, 120-128`） | 出事时的唯一凭据。补丁④ 给 `$done` 后移**不新增任何写路径**，审计面不变 |

---

## 10. 需要运维在服务器上跑的 3 条命令（验证 + 取证）

> 全部**只读**，不改任何东西。命令 1 直接验证本报告的根因结论。

### 命令 1 —— 证明 open_basedir 把 bapatch 挡在外面（**最高优先级**）

```bash
grep -n 'open_basedir' /www/wwwroot/ba_cardadmin/.user.ini /www/server/php/82/etc/php.ini; echo '--- error_log 里的实锤 ---'; grep -rhoE 'open_basedir restriction in effect\. File\([^)]*\)' /www/wwwlogs/*.log /www/server/php/82/var/log/php-fpm.log 2>/dev/null | sort -u | head -20
```

**判读**：
- 若第一段里**没有** `/www/wwwroot/bapatch` → 根因确认；
- 若第二段出现 `File(/www/wwwroot/bapatch/data/accounts.db)` → **实锤**，PHP 确实尝试过并被拒；
- 若 error_log 为空，**不能**说没问题（可能 `log_errors=Off`）→ 靠第一段判。

### 命令 2 —— 证明文件真实存在、权限不是障碍、库里有数据

```bash
stat -c '%A %U:%G %s %n' /www/wwwroot/bapatch/data /www/wwwroot/bapatch/data/accounts.db; ls -la /www/wwwroot/bapatch/data/; echo '--- 表/列/行 ---'; sqlite3 -readonly /www/wwwroot/bapatch/data/accounts.db "PRAGMA journal_mode; SELECT name FROM sqlite_master WHERE type='table'; SELECT count(*) AS rows FROM accounts; SELECT server_id, publisher_account_id, typeof(publisher_account_id), login_count FROM accounts LIMIT 10;"
```

**判读**：
- `stat` 有输出 → 文件存在（**这就已经证伪了面板的"文件不存在"**）；
- `%A` 里 www 所在组要有 `r`，目录要有 `x`；否则是真权限问题；
- `PRAGMA journal_mode` = `wal` → 记下来，修完 open_basedir 后要盯这个（§5.2）；
- `rows` > 0 且 `publisher_account_id` 与面板上的 `publisherId` 一致 → 键没问题，问题 100% 在读取链路。

### 命令 3 —— 证明 `card_players` 到底建没建、有没有行

```bash
mysql --defaults-file=/etc/my.cnf -e "SELECT CURRENT_USER();" ba_cardadmin -e "SHOW TABLES LIKE 'card_players'; SHOW GRANTS FOR CURRENT_USER(); SELECT COUNT(*) AS bindings FROM card_players;" 2>&1 | head -30
```

（凭据从 `config.php` 的 `DB_USER`/`DB_PASS` 取；宝塔下也可用 `mysql -uroot -p`。）
**判读**：
- `SHOW TABLES` 无输出 → **表没建**（→ 出口 ①，且 `CREATE` 权限大概不足，看 `SHOW GRANTS` 有没有 `CREATE`）；
- 有表、`bindings = 0` → **表是空的**（→ 出口 ②，面板显示"还没有绑"是对的）；
- 有表、`bindings > 0` → **查询没问题，是 `player_one()` 的驱动表逻辑把它吃了**（→ 出口 ④ 或键不匹配）；
- 报 `ERROR 1146` → 表不存在；报 `ERROR 1142` → 权限问题。

---

## 11. 附录：证据清单（文件 + 行号）

### 11.1 源码（本地 `work\ba\cardadmin_php`）

| 结论 | 位置 |
|---|---|
| 桥接库默认路径 `/www/wwwroot/bapatch/data/accounts.db` | `inc\players.php:21-28`（`:27` 是默认值） |
| `player_bridge_accounts()` 定义 | `inc\players.php:34-63` |
| **`is_file()`/`is_readable()` 早退（本案真正出口）** | `inc\players.php:42-44` |
| pdo_sqlite 缺失时早退 | `inc\players.php:45-47` |
| `new PDO(... READONLY)` | `inc\players.php:49-53`（常量在 `:52`） |
| `SELECT * FROM accounts` | `inc\players.php:54` |
| 键只用 `(string)`，未归一 | `inc\players.php:56` |
| **`catch (Throwable) { $rows = array(); }`** | `inc\players.php:59-61` |
| `isset()` 对 NULL 返回 false（静默丢行的来源） | `inc\players.php:55` |
| `player_bridge_status()` | `inc\players.php:66-87` |
| `exists = is_file()` / `readable = is_readable()` | `inc\players.php:72-73` |
| **`rows=0` 时 `error` 保持空串（假绿灯）** | `inc\players.php:77-79` |
| `error='文件不存在'`（把 open_basedir 谎报） | `inc\players.php:84` |
| `player_ensure_tables()`，`$done=true` 前置 | `inc\players.php:92-134`（`:98`） |
| `CREATE TABLE IF NOT EXISTS card_players` | `inc\players.php:100-113`（`UNIQUE KEY` 在 `:110`） |
| **建表失败静默** | `inc\players.php:131-133` |
| `player_card_bindings()`，`catch → array()` | `inc\players.php:174-186`（`catch` 在 `:182-184`） |
| `SELECT * FROM card_players` | `inc\players.php:179` |
| `player_one()` | `inc\players.php:344-388` |
| **`$pub = (string)(int)$d['publisherAccountId']`** | `inc\players.php:351` |
| **`isset($bridge[$pub])` ← join 语句** | `inc\players.php:354` |
| `$myCards` 以 `cards` 表为驱动（孤儿绑定消失） | `inc\players.php:359-364` |
| 绑定匹配条件（publisher 或 server_id） | `inc\players.php:366` |
| `'bridge' => $br` 返回 | `inc\players.php:384` |
| `player_roster()` 同构键处理 | `inc\players.php:270-271`、`:281` |
| JSON 解码位置（类型来源） | `inc\ba.php:141` |
| `ba_account_detail()` | `inc\ba.php:237-240` |
| PDO 连接与预处理 | `inc\db.php:103-125`、`:143-148` |
| `LOGIN_MAX_FAIL` / `LOGIN_LOCK_SEC` | `inc\db.php:72-75` |
| `e()` / `get_int()` / `post_int()` | `inc\helpers.php:18`、`:48`、`:55` |
| `setting_get()` / `setting_set()` | `inc\helpers.php:457-474`、`:482-495` |
| CSRF 四函数 | `inc\auth.php:437`、`:460`、`:520`、`:529` |
| 登录限速 | `inc\auth.php:186-196`、`:238` |
| 密码哈希 | `inc\auth.php:650`、`:658`、`:211-213` |

### 11.2 页面

| 结论 | 位置 |
|---|---|
| **`$bridge = $p['bridge']`** | `pages\player_detail.php:151` |
| `$p = player_one($sid)` | `pages\player_detail.php:142` |
| **`未找到（publisherId 对不上 accounts.db）`** | `pages\player_detail.php:251` |
| 「桥接 / 卡密」区块标题 | `pages\player_detail.php:249` |
| 设备号 / dev_id / 登录次数 / 最后登录 四行 | `pages\player_detail.php:252-255` |
| **`还没有绑定卡密。…`**（四态合一） | `pages\player_detail.php:259-260` |
| 绑定卡下拉（`$bindableCards`） | `pages\player_detail.php:164-177` |
| `publisherId` 显示 | `pages\player_detail.php:208` |
| `$brStatus = player_bridge_status()` | `pages\settings.php:332` |
| **「桥接账号库」自检行** | `pages\settings.php:385-393`（`:386` 是假绿灯条件） |
| 「PHP 扩展」行 | `pages\settings.php:394-398` |
| `ba_accounts_db` 保存（可写成任意绝对路径） | `pages\settings.php:84`、`:89-92`、`:100` |
| `ba_accounts_db` 输入框 | `pages\settings.php:427-430` |

### 11.3 配置 / 线上证据

| 结论 | 位置 |
|---|---|
| **`open_basedir` 不含 `/www/wwwroot/bapatch`** | `srv_live\20261118_0059\ba_cardadmin\.user.ini:1` |
| 白名单曾被改动（加过 `ba_sdk`） | `.user.ini.bak.1794777086`（`open_basedir=...ba_cardadmin/:/tmp/`） |
| PHP 8.2.31（排除"常量不存在"与"PHP7 科学计数法"） | `installed.lock` → `"php": "8.2.31"` |
| 线上 DB 用户 = `ba_cardadmin` | `srv_live\...\ba_cardadmin\config.php` → `define('DB_USER','ba_cardadmin')` |
| `accounts.db` 真实大小 143,360 B（与快照一致） | `server\deploy\_audit\PRODUCTION_HARDENING_20261118.md:120` |
| `/www/wwwroot/bapatch/accounts.db`（旧空壳）0 字节已删（易误判） | `PRODUCTION_HARDENING_20261118.md:118` |
| 桥接 publisherId 硬编码 314816420，两设备共用 | `PRODUCTION_HARDENING_20261118.md` §3.4 |
| 审计已记录 `.user.ini:1` 的 open_basedir 生效 | `AUDIT_PHP_PANEL_20261118.md:201`、`:33` |
| `inc\players.php` 本地=线上（MD5 `8279F2F76267D4BB1EF0FA499827B607`） | §3.1 本次实测 |
| `accounts.db` 为 WAL 模式 | 本次实测：头部 byte[18..19]=`02 02`，`PRAGMA journal_mode`=`wal` |
| `accounts` 表/列/行（3 行，`publisher_account_id` 为 9 位整数） | 本次实测 `PRAGMA table_info(accounts)` + `SELECT` |
| `sql\schema.sql` **不含** `card_players` / `panel_ops` | `sql\schema.sql:14-141`（8 张表，逐一核对） |

### 11.4 拿不到的（不编）

| 想知道的 | 为什么拿不到 |
|---|---|
| 线上 `pdo_sqlite` 是否启用 | 本机无 PHP CLI，无法探测；只能看设置页「PHP 扩展」行或命令 2 输出 |
| 线上 `accounts.db` 当前真实行数 | 只有 00:59 快照（3 行）；桥接在跑，可能已变 |
| 线上有没有 `-wal` / `-shm` | 快照只打包了 `accounts.db` 单文件，无从判断 |
| `card_players` 是否已建、有几行 | 无 MySQL dump、无 DB 连接权限；需命令 3 |
| error_log 里是否真有 open_basedir 警告 | 快照只含 `logs\sync.log`（同步日志，与 PHP 错误无关）；需命令 1 |
| `pages\settings.php` 线上版精确行号 | 线上版 20,164 B ≠ 本地 22,242 B，行号会漂；diff 已给上下文锚点，落地前须 `grep -n` 复核 |

---

## 12. 一页速查

```
症状：玩家详情 →「桥接 / 卡密」整块空
      桥接 5 行全"未找到 / —"
      绑定的卡密 "还没有绑定卡密。"

真因（★★★★★）：.user.ini open_basedir 少了 /www/wwwroot/bapatch/
                 → players.php:42 is_file() 恒 false
                 → 早退 return []（catch 根本不触发）
                 → player_one():354 $br = null
                 → player_detail.php:251 说谎："publisherId 对不上"

铁证三条：
  1) .user.ini:1 只有 ba_cardadmin / tmp / ba_sdk，没有 bapatch
  2) 快照 bapatch\data\accounts.db = 143,360 B，与线上记录字节数一致 → 文件在
  3) accounts.publisher_account_id = 314816420 = 桥接硬编码的 publisherId → 键对得上

误诊陷阱（务必避开）：
  · "给 catch 加日志" → 救不了：失败在 :42 早退，异常压根没产生
  · "改 (string)(int) 类型归一" → 本案 9 位数不受影响，改了页面照样空
  · "去找 accounts.db 文件" → 文件在，PHP 说不在是 open_basedir 的话术
  · "分不清空表/查询失败" → 这是第二个独立缺陷（card_players），别和桥接混谈

修复顺序（不可颠倒）：
  ⑤ .user.ini 加 /www/wwwroot/bapatch/  ← 唯一真正止血的
  ①a ①b 让失败可见（否则下次还得盲猜）
  ② 键归一（防御）
  ③ 多设备全列（本部署真实形态就是一个 publisher 多台机）
  ④ card_players 四态可见（第二个独立 bug）
  复测 §5.2 WAL 只读（修完 ⑤ 后的下一道门）

验证三条命令：grep open_basedir + stat/sqlite3 + mysql SHOW TABLES
```

---

**约束声明**：本报告生成过程中**未修改、未删除、未重命名任何既有文件**，**未部署任何东西**，**未对 `accounts.db` 执行任何写操作**（全部用 `sqlite3` 只读查询 / 只读头部字节）。
`accounts.db` 的打开方式：本地快照副本，`PRAGMA table_info` 与 `SELECT` 均为只读；文件未变（143,360 B）。
所有 `.php` 补丁仅以 diff 文本形式存在于本文件，等待人工评审后再决定是否落地。
