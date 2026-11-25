# 管理站（ba_cardadmin）结构摸底 · 新增「抽卡设置」页面的技术底稿

- 生成时间：2026-11-19 02:4x（Asia/Shanghai）
- 作业性质：**只读分析**。未联网、未登录服务器、未修改任何已有文件（含 PHP / SQL / 配置），未执行任何写操作。**本文件是唯一新增文件。**
- 分析对象（相对 `work/ba/`）：
  - 源码主树：`cardadmin_php/`（15 个 pages + 6 个 inc + cron + sql + assets，最新 2026-11-18 01:07）
  - 线上快照：`srv_live/20261118_0059/ba_cardadmin/`（全量）、`srv_live/20261118_2200/ba_cardadmin/`（仅 bans 功能 3 文件）
  - 后端源码（只用于确认接口契约）：`srv_src/Shittim-Server/`
- 代码行号均为本地文件实际行号，路径相对 `work/ba/` 书写。
- **本文件不含任何密码 / token / 密钥 / Admin Key**，只出现变量名与文件名。

---

## TL;DR（先看这一段）

| 项 | 结论 |
|---|---|
| **整体结构** | 经典 **文件即页面** 的 PHP + MySQL 面板。没有前端框架、没有 `?page=` 路由、没有 router。URL 直接对应文件：`/pages/xxx.php`。共享层只有 6 个 `inc/*.php`。 |
| **新增一个页面最少动几个文件** | **2 个新文件 + 1 处改一行**（`inc/<模块>.php` + `pages/<页面>.php` + 在 `inc/helpers.php` 的 `nav_items()` 里加一行）。不做数据表则不需要动 SQL；要建表就在 `inc/<模块>.php` 里用 `CREATE TABLE IF NOT EXISTS` 懒建。见 §6。 |
| **鉴权** | 不用 PHP 原生 session。自建 `sessions` 表 + 64 位 hex Cookie（`ca_sid`）。CSRF token 存在**服务端** `sessions.csrf`，`hash_equals` 比对，失败 419。登录限速 5 次/10 分钟按 IP 落 `login_attempts` 表。**没有权限分级**（任何管理员都能管管理员）。 |
| **数据访问** | `inc/db.php` 单例 PDO，全预处理，`ATTR_EMULATE_PREPARES=false`。统一封装 `db_run / db_all / db_row / db_val`。配置在**站点根目录 `config.php`**（`DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASS`），本地**没有**该文件，只有 `config.php.example`。 |
| **写入模式** | 统一 `POST → require_post_csrf() → 校验 → 写库 → audit_log() → flash_set() → redirect`（PRG）。设置类是 `setting_set()` 的 `INSERT ... ON DUPLICATE KEY UPDATE`。批量写才用事务（`cards_new.php` / `cards_import.php`）。**每次写操作必留 `audit_logs` 一条**。 |
| **「默认值 + 一键恢复默认」有先例吗** | **没有。整个面板没有任何"恢复默认"实现**。只有半套机制：`setting_get($key, $default)` 的第二个参数就是"默认值"，值是写死在调用点的字面量；库里 `settings` 表只存被改过的覆盖值。最接近的 UI 先例是 `settings.php` 的 `$charset_presets` 预设数组 + 「自定义」选项。要"一键恢复"需新建，最省事的做法是 `DELETE FROM settings WHERE k IN (...)` 让 inline 默认值重新生效。见 §5。 |
| **和后端怎么交互** | 三条先例都有，但**没有重启服务端的先例**：① 所有游戏侧写操作走 HTTP `POST /api/admin/*` + `X-Admin-Key`（`inc/ba.php`）；② 直接改服务端侧**数据文件**（`cards.json`，`atomic_write` + flock，cron 每分钟）；③ 面板自己的 `state/` `logs/` 随意写。`systemctl`/`exec`/`proc_open` 全项目 **0 处**。 |
| **对「抽卡设置」最关键的一条风险** | 抽卡概率/消耗**不在**任何可写的 API 或 MySQL 表里，而在服务端 `ExcelDB.db` 的 `GachaElement` / `GachaGroup` / `ShopRecruit` 等表的 **`Bytes` BLOB**（序列化行），由 `ExcelTableService` 单例**启动时**加载、并被各 Manager **构造时缓存进字段**。所以「面板改概率立即生效」目前**不可能**：既没有 `/api/admin/gacha/*`，改 Excel 还必须重启 C# 服务端。详见 §7.4。 |

---

## 0. 资料可信度与「缺哪些文件」

### 0.1 哪份是主树

| 目录 | 性质 | 判断 |
|---|---|---|
| `cardadmin_php/` | 源码主树（含 README 25 KB、sql、config.example、assets） | **以此为准**，功能最全（14 个业务页 + player 域） |
| `srv_live/20261118_0059/ba_cardadmin/` | 线上全量快照 | 与主树同构，用来核对「线上到底跑的是哪版」 |
| `srv_live/20261118_2200/ba_cardadmin/` | 线上增量快照 | **只有 3 个文件**：`inc/bans.php`、`pages/bans.php`、`MD5.txt` → 线上比主树**多一个封禁页** |
| `srv_live/20261118_2210/` | 不是面板快照 | 是 gacha 抓包分析脚本，与面板无关 |
| `server/deploy/_audit/FIX_PHP_20261118_orig/` | 一份 2026-11-18 的历史备份 | 含 `install.php`（主树已删） |

**结论：主树落后线上一个功能（bans）。** 新增页面时以主树为基线没问题，但**部署前必须先确认线上 `pages/bans.php` 与 `inc/bans.php` 已在主树有一份**，否则全量覆盖会删掉线上封禁页。

### 0.2 缺哪些文件 / 需要从服务器拉什么

| 缺的东西 | 影响 | 需要怎么补 |
|---|---|---|
| **`config.php`**（真实配置） | 本地只有 `config.php.example`。真实 `DB_NAME`/`DB_USER`/`APP_SECRET`/`BA_ADMIN_KEY` 未知 | 需要从服务器拉，但**只确认变量是否存在**；密码/token 不进任何报告或 git |
| **线上 `pages/bans.php` + `inc/bans.php`** | 主树没有；全量覆盖会丢功能 | 从 `srv_live/20261118_2200/` 反向补进主树（本地已有副本） |
| **线上真实表结构** | `sql/schema.sql` 只 8 张表，且 `cards` 缺 3 列（`kind`/`max_devices`/`last_used_at`），另有 `card_players`/`panel_ops`/`bans` 三张表**不在 schema.sql 里**。**没有迁移框架** | 必须从服务器拉 `SHOW CREATE TABLE`（或 `mysqldump --no-data`）才能拿到真 schema |
| **`.user.ini`** | 只在快照里有：`open_basedir=/www/wwwroot/ba_cardadmin/:/tmp/:/www/wwwroot/ba_sdk/`。主树没有此文件 | 新页面若想读写面板目录**以外**的路径（如抽卡数据文件）会被 PHP 直接拦，需同步改 open_basedir |
| **线上 nginx 站点配置** | `nginx.conf.example` 只是模板；README §1.7 要求的手工防护规则落地情况未知 | 新增 URL 前缀要确认不被规则拦 |
| **线上 PHP 版本/扩展实测** | README 记 8.2.31；`settings.php` 会自检但不落盘 | 部署前用页面「环境自检」区确认 |
| **`install.php`** | 主树已删（惯例：装完删）；只在 `_audit/FIX_PHP_20261118_orig/` | 不需要补，新表不要依赖它 |

---

## 1. 目录结构与路由方式

### 1.1 目录树（`cardadmin_php/`）

```
cardadmin_php/                  ← 网站根目录（线上 /www/wwwroot/ba_cardadmin）
  index.php          17 行  ← 唯一"入口"：未登录跳 login，已登录 include 仪表盘
  login.php         129 行  ← 登录页（独立 HTML，不走 page_header）
  logout.php          行少  ← 清 Cookie + 删会话行
  (install.php)             ← 装完即删，主树没有
  (config.php)              ← install 生成，含凭据，本地没有；只提交 .example
  .htaccess / nginx.conf.example / .gitignore

  inc/                        ← 公共包含层（目录被 .htaccess 禁 http 访问）
    db.php          170 行  ← PDO 单例 + 常量默认值 + db_* 查询封装
    helpers.php     945 行  ← 转义/URL/时间/分页/**布局**/settings/**nav_items()**
    auth.php        661 行  ← 会话表登录 / CSRF / 一次性令牌 / flash / 审计 / 密码
    sync.php        772 行  ← 同步引擎 MySQL → cards.json（原子替换 + flock）
    ba.php          509 行  ← Shittim /api/admin/* HTTP 客户端（X-Admin-Key）
    players.php     568 行  ← 玩家域 + card_players/panel_ops 懒建表
    (bans.php)               ← 线上有，主树缺

  pages/                      ← 每个文件就是一个页面（15 个）
  assets/app.css, app.js      ← 纯原生前端，无框架、无构建
  cron/sync_cards.php         ← 只能 CLI 跑（有 CLI 保护）
  sql/schema.sql     142 行  ← 8 张表（已落后，见 §0.2）
  state/  logs/               ← 运行期目录（各只有 .htaccess / .gitkeep）
```

### 1.2 路由方式：**文件即页面，没有路由**

`index.php` 全文只有 17 行，核心是最后一行：

`cardadmin_php/index.php:8-17`
```php
require_once __DIR__ . '/inc/auth.php';
if (!db_installed()) { redirect('install.php'); }
require_login();
/* 仪表盘以 include 方式渲染，这样 / 与 /pages/dashboard.php 都能用 */
require __DIR__ . '/pages/dashboard.php';
```

- 没有 `?page=`、没有 PATH_INFO 解析、没有 front controller 分发。
- 每个页面 URL = 文件路径：`/pages/cards.php`、`/pages/settings.php`。
- `pages/dashboard.php` 是**唯一**既能被 `index.php` include、又能被直接访问的页面（它是"自包含"的：自己 `require_login()` + 自己 `page_header()`）。
- 链接统一由 `u()` 生成，会拼 `APP_BASE`（子目录也能跑）：`helpers.php:103-107`。

### 1.3 导航 = 一个硬编码数组

**这是新增页面唯一必须改的公共文件。**

`inc/helpers.php:834-860`
```php
function nav_items()
{
    return array(
        'dashboard' => array('仪表盘', 'pages/dashboard.php'),

        /* 玩家域：全部走 Shittim admin API */
        '__g_player' => array('玩家', null),
        'players'    => array('玩家列表', 'pages/players.php'),
        'mail'       => array('发奖 / 邮件', 'pages/mail.php'),
        'currency'   => array('货币调整', 'pages/currency.php'),
        'items'      => array('道具 / 角色', 'pages/items.php'),
        'console'    => array('GM 命令台', 'pages/console.php'),

        /* 卡密域：现有能力，逻辑不动 */
        '__g_card' => array('卡密', null),
        'cards'    => array('卡密管理', 'pages/cards.php'),
        'new'      => array('新建卡密', 'pages/cards_new.php'),
        'import'   => array('批量导入', 'pages/cards_import.php'),

        /* 系统域 */
        '__g_sys'  => array('系统', null),
        'logs'     => array('登录日志', 'pages/logs.php'),
        'admins'   => array('管理员', 'pages/admins.php'),
        'audit'    => array('审计日志', 'pages/audit.php'),
        'settings' => array('系统设置', 'pages/settings.php'),
    );
}
```
- key 相同者即 `page_header($title, $active)` 里的高亮 key；`$item[1] === null` 的项渲染成 `.nav-group` 分组标题（`helpers.php:895-901`）。
- **注意**：线上 `bans.php` **没有**进 `nav_items()`（全快照 grep 无 `'bans' =>`），说明这个数组可以漏加——漏加后果只是"没链接，只能手敲 URL"。加页面时**应当**加。

### 1.4 页面数量与命名规律

| 分类 | 文件 | 说明 |
|---|---|---|
| 根 | `index.php` `login.php` `logout.php` | 入口 / 登录 / 登出（**都带 `define('CARDADMIN', true)` 守卫**） |
| pages 业务 | `dashboard.php` `players.php` `player_detail.php` `mail.php` `currency.php` `items.php` `console.php` `cards.php` `cards_new.php` `cards_import.php` `cards_export.php` `logs.php` `admins.php` `audit.php` `settings.php` | 15 个 |
| pages 线上增量 | `bans.php` | 线上第 16 个 |
| inc 模块 | `db.php` `helpers.php` `auth.php` `sync.php` `ba.php` `players.php`（+线上 `bans.php`） | 6（+1） |
| cron | `cron/sync_cards.php` | CLI only |

**命名规律**（全部遵守，照抄即可）：
- 页面 = `pages/<小写下划线>.php`，**单数名词或动词短语**：`settings.php` / `cards_new.php` / `cards_import.php` / `player_detail.php`。
- 列表页 + 操作页分离：`cards.php`（列表/批量）→ `cards_new.php`（新建）→ `cards_import.php`（导入）→ `cards_export.php`（导出）。
- inc 模块 = `inc/<领域>.php`，一个领域一个文件，**页面只 require 需要的 inc**，不 require 全部。
- 导航里 12 个链接，`pages/` 有 15 个文件 → `cards_export.php`、`player_detail.php` 是**下钻子页**，从列表页带参数进入，不进导航。
- 每个页面文件头都是一段中文 docblock 说明「这页干什么 + 写操作约束」，例如 `pages/console.php:1-7`、`pages/bans.php:1-21`。**这是本项目的强惯例，新页面必须写。**

### 1.5 页面骨架（所有页面完全一致）

以 `pages/settings.php:1-14` 为例，这是标准头：

```php
<?php
/**
 * pages/settings.php — 系统设置
 *   同步（立即同步 / 从 cards.json 导入）、生成默认规则、路径、环境自检
 */
if (!defined('CARDADMIN')) {
    define('CARDADMIN', true);
}
require_once __DIR__ . '/../inc/auth.php';
require_once __DIR__ . '/../inc/sync.php';
require_once __DIR__ . '/../inc/ba.php';
require_once __DIR__ . '/../inc/players.php';

require_login();
```

结尾一定是 `page_header('标题', 'nav_key')` … HTML … `page_footer()`（`settings.php:198` / `:440`）。
**除 `login.php` 外，所有页面都必须 `require_login()`，否则就是未授权入口。**

---

## 2. 鉴权

### 2.1 设计取舍

`inc/auth.php:1-8` 的注释写明了原因：
```php
/**
 * inc/auth.php — 登录状态、会话表、CSRF、审计日志
 *
 * 设计：不使用 PHP 自带 session 存储（宝塔默认 session 目录常不可写），
 * 而是自定义 Cookie + sessions 表；token 为 32 字节随机 hex。
 * Cookie: HttpOnly + SameSite=Strict（https 时再加 Secure）。
 */
```
→ 所以**不要**在新页面里用 `$_SESSION`，它根本没被启动。用 `current_admin()` / `flash_set()`。

### 2.2 登录：`login.php` → `auth_attempt_login()`

限速是**按 IP 落库**，不是内存、不是 PHP session：

`inc/auth.php:171-198`
```php
$ip    = client_ip();
$now   = time();
$since = $now - LOGIN_LOCK_SEC;          // 600s
...
$fails = (int)db_val(
    'SELECT COUNT(*) FROM login_attempts WHERE ip = ? AND ok = 0 AND ts > ?',
    array($ip, $since), 0
);
if ($fails >= LOGIN_MAX_FAIL) {          // 5
    $last = (int)db_val('SELECT MAX(ts) FROM login_attempts WHERE ip = ? AND ok = 0 AND ts > ?', ...);
    $left = max(1, (int)ceil(($last + LOGIN_LOCK_SEC - $now) / 60));
    return array(false, '密码错误次数过多，已锁定，请 ' . $left . ' 分钟后再试');
}
```
常量：`inc/db.php:71-76`（`LOGIN_MAX_FAIL`=5，`LOGIN_LOCK_SEC`=600）。
失败还会固定拖 0.3s（`auth.php:229 usleep(300000)`），避免用户名枚举靠计时。

密码哈希：**bcrypt(hmac_sha256(密码, 每用户 salt))**，规避 bcrypt 72 字节截断：

`inc/auth.php:642-661`
```php
function make_pass_hash($password, $salt)
{
    return password_hash(hash_hmac('sha256', (string)$password, (string)$salt), PASSWORD_BCRYPT);
}
```
校验时兼容老数据（无 salt 直接 bcrypt）：`auth.php:210-216`。

### 2.3 会话校验：每个请求查一次 `sessions`

`inc/auth.php:75-118`（关键 SQL）：
```php
$token = ca_cookie_get(SESSION_COOKIE);      // 'ca_sid'
if ($token === '' || !preg_match('/^[a-f0-9]{64}$/', $token)) { return null; }

$r = db_row(
    'SELECT s.token, s.admin_id, s.created_at, s.expires_at, s.ip, s.user_agent, s.csrf, s.flash,
            a.username, a.enabled, a.pass_hash
       FROM sessions s
       JOIN admins a ON a.id = s.admin_id
      WHERE s.token = ?
      LIMIT 1',
    array($token)
);
```
逐项校验：`expires_at <= time()` → 顺手删行并返回 null（`:105-112`）；`a.enabled !== 1` → 立即失效（`:113-115`）。
结果缓存在 `$GLOBALS['__ca_sess']`，**同请求内只查一次**；要强制重读得 `auth_session_forget()`（`:70-73`）。

Cookie 参数：`HttpOnly + SameSite=Strict + Secure(仅 https) + path=app_base()`（`auth.php:46-60`）。
`client_ip()` **只信 `REMOTE_ADDR`**，不解析 `X-Forwarded-For`（防伪造，`:33-38`）。

**关于「会话 token 轮换」**（历史审计报告提到的）：实际语义是——
- 每次**登录成功**生成新 token + 新 csrf，旧会话行不动（`auth.php:243-256`）；
- **没有**"每请求轮换"；
- 真正会**踢掉**旧会话的场景：改密码 / 禁用 / 删管理员时 `DELETE FROM sessions WHERE admin_id = ?`（`pages/admins.php:72, 98, 119`）、登出（`auth.php:268`）、过期清理（`auth.php:179`）。
新页面**不需要**自己处理会话轮换，`require_login()` 已覆盖。

### 2.4 权限分级：**没有**

- `admins` 表只有 `enabled`（1/0），**没有 role 列**（`sql/schema.sql:14-25`）。
- 代码里没有任何 `role` / `is_super` / `can_write` 判断（全项目 grep 0 命中）。
- README 自己写明了：`cardadmin_php/README.md:454` —— "**没有权限分级**：任何管理员都能管理其他管理员。建议只留一个账号。"
- 页面里也重复提示：`pages/admins.php:223`。

→ 新页面**不需要**考虑权限粒度；能登录就是全权。若以后要分级，得先加 `admins.role` 列 + 改 `require_login()`，属于另一个工程。

### 2.5 CSRF：token 存在**服务端**，不在 Cookie

生成（已登录 = 会话行里的 csrf；未登录 = `state/precsrf_*.json`，`cookie` 只放不透明 id）：

`inc/auth.php:283-292`
```php
function csrf_token()
{
    $row = auth_session_row();
    if ($row && !empty($row['csrf'])) {
        return (string)$row['csrf'];
    }
    /* 登录页（无会话）：令牌存服务端 state/，cookie 只放一个不透明的随机 id。
       这样 token 不再由客户端 cookie 持有（防固定/伪造）。 */
    return preauth_token_get();
}
```
输出到表单：`auth.php:437-440`
```php
function csrf_field()
{
    return '<input type="hidden" name="_csrf" value="' . e(csrf_token()) . '">';
}
```
校验（失败 **419**，`hash_equals` 恒定时间比较）：

`inc/auth.php:443-469`
```php
function verify_csrf()
{
    $sent = isset($_POST['_csrf']) ? (string)$_POST['_csrf'] : '';
    $want = csrf_token();
    if ($sent === '' || $want === '' || !hash_equals($want, $sent)) {
        http_response_code(419);
        ...
        exit;
    }
    return true;
}

/** 要求必须是 POST + 通过 CSRF */
function require_post_csrf()
{
    if (!isset($_SERVER['REQUEST_METHOD']) || strtoupper((string)$_SERVER['REQUEST_METHOD']) !== 'POST') {
        http_response_code(405);
        header('Allow: POST');
        exit('405 Method Not Allowed');
    }
    verify_csrf();
    return true;
}
```
**所有写操作的第一行都是 `require_post_csrf();`**（`settings.php:24`、`mail.php:40`、`console.php:65`、`bans.php` 同）。

### 2.6 高危操作还有「一次性确认令牌」（防误触，非防攻击）

`inc/auth.php:478-553`：`action_token_get($scope)` 把 32 hex 存 `state/otok_<hash>.json`（TTL 600s），`action_token_check($scope)` 校验后**无论成败立即 unlink**，失败 419。
用于：GM 命令台（`console.php:66 action_token_check('console')`）、发奖（`mail.php:41 action_token_check('mail')`）。

> **给新页面的判断**：「抽卡设置保存」属于**可回滚的配置写**，按现有惯例**不需要** action token（`settings.php` 的 4 个保存动作都没有用）。只有「立即生效 / 重启服务端 / 清空记录」这类不可逆动作才该加。

### 2.7 审计：每个写操作一行，写库不写文件

`inc/auth.php:615-638`
```php
function audit_log($action, $target = '', $detail = '')
{
    ...
    db_run(
        'INSERT INTO audit_logs (admin_id, admin_name, action, target, detail, ip, ts)
         VALUES (?, ?, ?, ?, ?, ?, ?)',
        array($data['admin_id'], $data['admin_name'], $data['action'], $data['target'],
              $data['detail'], $data['ip'], $data['ts'])
    );
    // catch 里注释：审计失败不应影响主流程
}
```
- 调用点都紧跟写库之后，**并记录改了哪些值**（见 `settings.php:62-63`）。
- 审计失败被吞掉（故意），**不会**回滚业务。
- 另有 `panel_ops` 表记"批次型"操作（发奖/批量），`inc/players.php:137-160`。
- **没有**写文件日志的通用机制；`logs/sync.log` 只有 cron 在写（`inc/sync.php:67`）。

### 2.8 `AdminAuthAttribute` 怎么对到 PHP 侧

这是 **C# 服务端** `/api/admin/*` 的守卫，PHP 侧是它的**客户端**，对应关系：

| 侧 | 东西 | 位置 |
|---|---|---|
| C# 守卫 | `AdminAuthAttribute`（`IAuthorizationFilter`），头名 `X-Admin-Key` | `srv_src/Shittim-Server/Controllers/AdminAuthAttribute.cs:17-19` |
| C# 语义 | 配了 key → **所有来源（含环回）都强制校验**；没配 key → 只放行环回 | 同上 `:21-51`；注释 `:10-15` 明确解释"反向代理让所有请求看起来都来自 127.0.0.1，所以环回豁免只在没配 key 时成立" |
| C# 比较 | `CryptographicOperations.FixedTimeEquals`（恒定时间） | 同上 `:62-71` |
| key 来源 | 环境变量 `SHITTIM_ADMIN_API_KEY` 优先，否则 `Config.ServerConfiguration.AdminApiKey` | 同上 `:53-60`；`Configuration/ConfigType/ServerConfig.cs:59-61` |
| PHP 侧发送 | `ba_http()` 每次请求加头 | `inc/ba.php:88-91` |
| PHP 侧 key 来源 | `config.php` 的 `BA_ADMIN_KEY` → 回落 `settings.ba_admin_key` | `inc/ba.php:24-47` |
| PHP 侧地址 | `BA_ADMIN_BASE` → 回落 `settings.ba_admin_base` → 默认 `http://127.0.0.1:5000` | `inc/ba.php:49-51` |

`inc/ba.php:88-91`
```php
$headers = array('Accept: application/json');
if ($c['key'] !== '') {
    $headers[] = 'X-Admin-Key: ' . $c['key'];
}
```
`inc/ba.php:9-11`（注释即契约）
```php
 * 鉴权：Shittim 的 AdminAuthAttribute 在"配了 key"时强制要求 X-Admin-Key（环回也不例外），
 * 所以这里必须带上。key 从 config.php 的 BA_ADMIN_KEY 读，读不到再回落到 settings 表。
```
→ 新页面若要走后端，**只用 `ba_get()` / `ba_post()`**，绝不自己 `curl`，否则会绕开 key 与错误处理约定（`ba_http` 不抛异常，返回 `['ok'=>bool,'status'=>int,'data'=>mixed,'error'=>string,'ms'=>int,'url'=>string]`，见 `ba.php:78`）。

---

## 3. 数据访问

### 3.1 连接配置在哪（只说文件与变量名）

| 项 | 值 |
|---|---|
| 配置文件 | **站点根目录 `config.php`**（与 `index.php` 同级），由 `install.php` 生成，权限 0640 |
| 谁引入它 | `inc/db.php:16-20`：`$__ca_cfg = dirname(__DIR__) . '/config.php'; if (is_file(...)) require_once ...;` |
| 变量名 | `DB_HOST` / `DB_PORT`（默认 3306）/ `DB_NAME` / `DB_USER` / `DB_PASS` |
| 其他相关常量 | `APP_SECRET`、`APP_NAME`、`APP_TIMEZONE`、`APP_DEBUG`、`APP_BASE`、`SESSION_COOKIE`、`SESSION_TTL`、`CARDS_JSON_PATH`、`SDK_LOG_PATH`、`MAX_UPLOAD_BYTES`、`MAX_BATCH_GEN`、`LOGIN_MAX_FAIL`、`LOGIN_LOCK_SEC` |
| 默认值兜底 | `inc/db.php:28-85` 每个常量都 `if (!defined(...)) define(...)`，**所以 config.php 缺项不会 fatal** |
| 未安装判定 | `inc/db.php:22-26`：`DB_NAME/DB_HOST` 未定义或为空 → `CARDADMIN_INSTALLED=false` → `db_installed()` 返回 false → 自动跳 `install.php` |
| 本地状态 | **`config.php` 不存在**（只有 `config.php.example`，密码处是 `CHANGE_ME`）。线上真实值未知 |

> 报告与文档里**不要**出现 `DB_PASS` / `APP_SECRET` / `BA_ADMIN_KEY` 的值。页面自己也遵守这点：设置页只显示 `••••••••`（`settings.php:333-337`），要看真值得点「显示一次」走 `secret_once_take()`。

### 3.2 PDO 单例 + 全预处理

`inc/db.php:103-125`
```php
function db()
{
    static $pdo = null;
    if ($pdo instanceof PDO) { return $pdo; }
    if (!db_installed()) { throw new RuntimeException('尚未安装：请先访问 install.php 完成安装'); }
    $dsn = 'mysql:host=' . DB_HOST . ';port=' . (int)DB_PORT . ';dbname=' . DB_NAME . ';charset=utf8mb4';
    $pdo = new PDO($dsn, DB_USER, DB_PASS, array(
        PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        PDO::ATTR_EMULATE_PREPARES   => false,     // ← 真·预处理，不是字符串拼接
        PDO::ATTR_STRINGIFY_FETCHES  => false,
    ));
    // catch 里只 throw RuntimeException('数据库连接失败：' . $e->getMessage())
}
```
`ATTR_EMULATE_PREPARES=false` = 服务端预处理，杜绝拼接注入主路径。
`current_admin()` 之外，页面**不应**直接 new PDO。

### 3.3 统一 DB 封装（**新页面只用这四个**）

`inc/db.php:143-169`
```php
function db_run($sql, $params = array())   { $st = db()->prepare($sql); $st->execute($params); return $st; }
function db_all($sql, $params = array())   { return db_run($sql, $params)->fetchAll(); }
function db_row($sql, $params = array())   { $r = db_run($sql, $params)->fetch(); return $r === false ? null : $r; }
function db_val($sql, $params = array(), $default = null) { ... return ($v === false || $v === null) ? $default : $v; }
function db_insert_id() { return (int)db()->lastInsertId(); }
```
辅助：`db_installed()`（`:94`）、`db_is_ok()`（`:127`）。
**惯例：**
- 所有 SQL 用 `?` 占位符，**从不**把用户输入拼进字符串。
- `IN (...)` 动态占位用 `implode(',', array_fill(0, count($ids), '?'))`（`pages/cards.php:139-149` 等处）。**唯一的字符串拼接是 LIMIT/OFFSET**，且都 `(int)` 强转（`helpers.php:542`、`cards.php:319-322`）。
- 表名/列名当变量时用白名单数组映射，不裸拼。

### 3.4 现有的表（从 SQL 反推出的全集：11 张）

`sql/schema.sql` 里 8 张：

| 表 | 用途 | 主要列 |
|---|---|---|
| `admins` | 管理员 | `id, username, pass_hash, salt, created_at, last_login_at, last_login_ip, enabled` |
| `sessions` | 登录会话（**不用 PHP session**） | `token(64), admin_id, created_at, expires_at, ip, user_agent, csrf, flash` |
| `cards` | 卡密唯一真源 | `id, card_key, status, expire_at, bind_one, created_at, created_by, note, login_count, last_login_at, last_login_device` |
| `card_devices` | 卡↔设备 | `id, card_id(FK), device_id, bound_at, last_seen_at` |
| `login_logs` | 登录日志（解析 sdk.log + 平台） | `card_key, device_id, result, source, ts, raw, line_hash(去重)` |
| `audit_logs` | 审计 | `admin_id, admin_name, action, target, detail, ip, ts` |
| `settings` | **k-v 设置（关键）** | 只有两列：`k VARCHAR(64) PRIMARY KEY`, `v TEXT` |
| `login_attempts` | 登录失败计数/锁定 | `ip, username, ts, ok` |

**不在 schema.sql 里、由代码懒建的 3 张**（这就是"加表"的实际做法）：

| 表 | 建在哪 | 说明 |
|---|---|---|
| `card_players` | `inc/players.php:100-113` | 卡密↔玩家绑定 |
| `panel_ops` | `inc/players.php:115-130` | 批次操作流水（`batch_id/action/targets/payload/ok_count/fail_count`） |
| `bans` | `inc/bans.php:1346`（线上快照） | 封禁（账号/卡密/设备三维） |

**另有 `cards` 表的 3 个"后加列"**：`kind`、`max_devices`、`last_used_at`。`sync.php` 用 `information_schema` **特性探测**兼容缺列状态：

`inc/sync.php:139-159`
```php
/** cards 表是否已有卡类型三列（ALTER 之前也能跑，缺列时按老逻辑导出） */
function sync_cards_has_type_cols()
{
    ...
    $n = (int)db_val(
        "SELECT COUNT(*) FROM information_schema.COLUMNS
          WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'cards'
            AND COLUMN_NAME IN ('kind','max_devices','last_used_at')",
        array(), 0
    );
    $has = ($n === 3);
    ...
}
```
→ **本项目没有迁移框架**。加列 = ① 手写幂等 ALTER SQL 放 `server/deploy/_audit/`；② 代码里用 `information_schema` 探测兼容；③ 写一份 feature 报告。范例见 `server/deploy/_audit/alter_cards_cardtype.sql`（全文用 `PREPARE/EXECUTE` + `@has_xxx` 判存在，可重复执行）与 `_audit/FEATURE_CARDTYPE_PHP_20261118_0109.md`。

---

## 4. 写入模式（「保存设置」到底怎么落库）

### 4.1 统一时序（所有页面一致）

```
POST
 → require_post_csrf()            // 405 if not POST / 419 if CSRF bad
 → (高危页) action_token_check()  // 419 if one-shot token bad
 → 分派：$act = post_q('action')  // 单页多表单靠 action 字段区分
 → 逐个字段校验（post_int 夹取范围 + 白名单 + 格式正则）
 → 写库：setting_set() / db_run(INSERT|UPDATE)
 → audit_log('域.动作', 目标, 改了哪些值)
 → flash_set('提示', 'ok'|'err')
 → redirect_self()               // PRG，防刷新重复提交
```

**分派惯例**：一个页面多个表单，靠隐藏字段 `action` 区分（`settings.php` 有 7 个 action：`save_general` / `save_paths` / `save_ba` / `reveal_key` / `test_ba` / `flush_ba_cache` / `cleanup_sessions`），整个 POST 体包在一个 `try/catch (Throwable)` 里，catch 里 `flash_set('保存失败：'.msg,'err')`。

### 4.2 例 1（**最典型，抽卡设置就该照这个写**）：`settings.php` 的「生成默认规则」

`pages/settings.php:35-64`
```php
if ($act === 'save_general') {
    $len     = post_int('auto_gen_len', 16, 8, 64);       // ← 默认值 16 + 范围夹取
    $charset = post_q('auto_gen_charset');
    $prefix  = trim(post_q('auto_gen_prefix'));
    $per     = post_int('page_size', 50, 10, 500);

    $preset_name = $charset;
    if (isset($charset_presets[$charset])) {
        $charset = $charset_presets[$charset][1];         // ← 预设 → 实际值
    }
    $charset = preg_replace('/\s+/', '', (string)$charset);
    if (strlen($charset) < 2) {
        flash_set('字符集至少 2 个字符', 'err');
        redirect_self();
    }
    if (preg_match('/[^\x21-\x7E]/', $charset)) {
        flash_set('字符集只支持可见 ASCII 字符', 'err');
        redirect_self();
    }
    if ($prefix !== '' && !preg_match('/^[A-Za-z0-9_\-]{1,16}$/', $prefix)) {
        flash_set('前缀只能是 1-16 位字母/数字/下划线/减号', 'err');
        redirect_self();
    }
    setting_set('auto_gen_len', $len);
    setting_set('auto_gen_charset', $charset);
    setting_set('auto_gen_prefix', $prefix);
    setting_set('page_size', $per);
    audit_log('settings.save', '生成默认规则',
        'len=' . $len . ' charset_len=' . strlen($charset) . ' prefix=' . $prefix . ' page_size=' . $per);
    flash_set('已保存生成默认规则', 'ok');
}
```
读的时候：`setting_int('auto_gen_len', 16)`（`settings.php:260`）、`setting_get('auto_gen_prefix', '')`（`:276`）。

**核心工具是 UPSERT，不是 INSERT 也不是 REPLACE**：

`inc/helpers.php:482-495`
```php
function setting_set($key, $value)
{
    $key   = (string)$key;
    $value = is_bool($value) ? ($value ? '1' : '0') : (string)$value;
    db_run(
        'INSERT INTO settings (k, v) VALUES (?, ?) ON DUPLICATE KEY UPDATE v = VALUES(v)',
        array($key, $value)
    );
    ...
    $GLOBALS['__ca_setting_cache'][$key] = $value;   // ← 同请求内立即可读
    return true;
}
```
读缓存（**注意：首次访问会把整表读进内存一次**）：

`inc/helpers.php:457-474`
```php
function setting_get($key, $default = null)
{
    if (!isset($GLOBALS['__ca_setting_cache'])) {
        $GLOBALS['__ca_setting_cache'] = array();
        try {
            foreach (db_all('SELECT k, v FROM settings') as $row) {
                $GLOBALS['__ca_setting_cache'][(string)$row['k']] = (string)$row['v'];
            }
        } catch (Throwable $e) { $GLOBALS['__ca_setting_cache'] = array(); }
    }
    if (array_key_exists($key, $GLOBALS['__ca_setting_cache'])) {
        return $GLOBALS['__ca_setting_cache'][$key];
    }
    return $default;          // ← 「默认值」就在这里
}
```
> ⚠️ **缓存坑**：因为整表在**首读**时已进内存，若你在同一个请求里 `DELETE FROM settings` 之后还想读到"恢复后的默认值"，**必须**先调 `setting_reload()`（`helpers.php:498-502`）。否则读回的还是缓存里的旧覆盖值。

### 4.3 例 2：真正的多行写入 + 事务（批量才有）

`pages/cards_new.php:169-195`（批量生成卡密）
```php
db()->beginTransaction();
try {
    // ... 循环 db_run('INSERT INTO cards (...) VALUES (...)')，失败即抛
    db()->commit();
} catch (Throwable $ex) {
    ...
    db()->rollBack();
}
```
`pages/cards_import.php:141-159` 同款（导入）。
另有 `pages/cards.php:129-149` 的多表删除：**先删 `card_devices` 再删 `cards`**（`cards.php:143` 在 `:129` 之后），靠手写顺序而非 FK cascade（虽然 `card_devices` 有 `ON DELETE CASCADE`）。

**事务使用范围**：只在"一个用户动作要写多行/多表"时用。单行 UPSERT / 单个 `UPDATE` **不用事务**（`settings.php`、`admins.php`、`cards.php:176-218` 都直接写）。

### 4.4 例 3：走后端 API 的写（玩家域）

`pages/mail.php:116-149`
```php
$batch  = substr(bin2hex(random_bytes(6)), 0, 12);
foreach ($ids as $sid) {
    $r = ba_mail_send($sid, $sender, $comment, $parcels, $expire);   // HTTP POST /api/admin/mail/send
    ...
    if ($r['ok']) { $okN++; } else { $failN++; }
}
panel_op_log('mail.send', $ids, array(...), $okN, $failN, $batch);   // 批次流水
audit_log('mail.send',
    '邮件批次 ' . $batch . ' → ' . count($ids) . ' 人（成功 ' . $okN . ' / 失败 ' . $failN . '）',
    'sender=' . $sender . ' ... parcels=' . json_encode($parcels, JSON_UNESCAPED_UNICODE));
```
特征：**部分成功不算失败**，把 ok/fail 计数写进流水；页面自己再渲染逐行结果。这条模式在 `currency.php` / `items.php` / `console.php` 复用。

### 4.5 日志：库 vs 文件

| 类型 | 落点 | 谁写 |
|---|---|---|
| 业务审计（谁改了啥） | **MySQL `audit_logs`** | `audit_log()`，所有页面 |
| 批次操作 | **MySQL `panel_ops`** | `panel_op_log()`，玩家域 |
| 同步运行日志 | **文件 `logs/sync.log`** | 只有 `cron/sync_cards.php` / `inc/sync.php:67` |
| 会话一次性数据 | **文件 `state/secret_*.json`、`state/otok_*.json`、`state/uistate_*.json`、`state/precsrf_*.json`** | `auth.php` |

→ 新页面**只需** `audit_log()`；不要自己开 log 文件。

---

## 5. 「默认值 + 一键恢复默认」现在的先例

### 5.1 直接回答：**一键恢复默认完全没有先例**

全项目 grep `恢复默认|重置为默认|reset_default|restore_default|defaults|default_|DEFAULTS|is_default`，**唯一命中**是 `inc/db.php:87` 的 `@date_default_timezone_set(...)`。也就是说：
- ❌ 没有 `defaults.json` / `defaults.php`
- ❌ 没有 `is_default` 字段（`settings` 表只有 `k`、`v` 两列）
- ❌ 没有"恢复默认"按钮、没有 reset action

### 5.2 但"默认值"机制已经存在——写死在 PHP 里当函数参数

现状是**三层取值**，默认值永远是**调用点字面量**：

```
setting_get('k', 默认字面量)  ←  默认值在这里（PHP 代码，不落库）
        ↓ 若 settings 表有 k
    返回库里的覆盖值
```
实例（`pages/settings.php`）：
```php
(int)setting_int('auto_gen_len', 16)                    // :260  默认 16
(string)setting_get('auto_gen_prefix', '')              // :276  默认 空
(int)setting_int('page_size', 50)                       // :279  默认 50
(string)setting_get('sdk_log_path', SDK_LOG_PATH)       // :145  默认 = 常量
(string)setting_get('ba_admin_base', 'http://127.0.0.1:5000')   // inc/ba.php:50
```
其他默认值风格：
- **常量兜底**（config.php 可覆盖，未定义时 `db.php:28-85` 给默认），如 `CARDS_JSON_PATH` 默认 `/root/bapatch/cards.json`（`db.php:53-55`）。
- **预设数组 + 「自定义」选项**（最接近"默认值 UI"的先例）——`pages/settings.php:16-21`：
```php
$charset_presets = array(
    'safe'   => array('不含易混字符（推荐）', 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'),
    'upper'  => array('大写字母', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'),
    'alnum'  => array('大写+小写+数字', 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'),
    'digits' => array('纯数字', '0123456789'),
);
```
  页面渲染时把当前值反查回预设 key，查不到就显示「自定义（当前 …）」（`settings.php:190-196`、`:262-274`）。**这套「预设下拉 + 自定义保留」的交互就是抽卡设置页最该抄的 UI。**
- **PHP 常量写入路径**：`config.php` 里 `define('CARDS_JSON_PATH', ...)` 优先于 `setting`。

### 5.3 「一键恢复默认」最省事的三种实现（按契合度排序）

| 方案 | 怎么做 | 契合现有代码 | 代价 |
|---|---|---|---|
| **A. 删行回落到 inline 默认值**（推荐） | 页面里维护 `$gacha_defaults = array('k'=>v, ...)`；reset 动作执行 `DELETE FROM settings WHERE k IN ('gacha_*', ...)` 后 `setting_reload()`；渲染时本来就 `setting_get($k, $gacha_defaults[$k])` → 自动显示默认值 | ★★★★★ 零 schema 变更，完全复用现有 `settings` 表与 `setting_get` | 需要约定 key 前缀（如 `gacha_`）以便批量删 |
| B. 逐个 `setting_set($k, 默认值)` | reset 时循环 `setting_set()` 把默认值写回库里 | ★★★★☆ 同样零 schema 变更；写库后值=默认，行为与"改过但改成默认值"一致 | 库里会留"覆盖=默认"的行，审计上略含糊；但一样能 `audit_log` 记一条 |
| C. 单独版本表 / `is_default` 列 | 新建 `gacha_settings` 表带 `is_default` | ★☆☆☆☆ 与现有 `settings` k-v 风格冲突，要自建表 + 迁移脚本 | 最重，只在需要多套配置（多卡池、多环境）时才值得 |

**建议 A**，并把默认值集中放在 `inc/gacha.php` 顶部一个 `gacha_defaults()` 函数里（对应"默认值写死在 PHP 数组"——正是本项目既有风格），页面只引用不重复写。

> 恢复默认必须 `audit_log('gacha.reset', '抽卡设置', '恢复 N 项默认值')`，并且**加二次确认**（`onsubmit="return confirm(...)"`，现有页面惯例见 `settings.php:211`）。

---

## 6. 加一个「抽卡设置」页面的最小步骤

### 6.0 先明确一个前提

如果「抽卡设置」只是**面板自己存的值**（面板侧记录 + 后续由别的机制消费），走下面 5 步即可，**不动 C# 服务端**。
如果要求「改完概率立即对玩家生效」，那 5 步**不够**——见 §7.4，必须先给 Shittim 加 `/api/admin/gacha/*` 端点或改 Excel 加载策略，那是一个单独的工程。

### 6.1 最小 5 步（照 bans / players 的既有惯例）

| # | 动作 | 文件 | 内容 |
|---|---|---|---|
| **1** | 新建模块 | `inc/gacha.php`（新文件） | `gacha_defaults()` 默认值数组 + `gacha_ensure_tables()`（若需要新表：`CREATE TABLE IF NOT EXISTS`，并用 `static $done` 守卫，抄 `inc/players.php:92-134`）+ 可选的读写小函数。文件头写中文 docblock 说明数据来源/口径。 |
| **2** | 新建页面 | `pages/gacha.php`（新文件） | 抄 `pages/settings.php` 骨架：`define('CARDADMIN')` → `require inc/auth.php` + `inc/gacha.php` → `require_login()` → `POST` 里 `require_post_csrf()` + `$act = post_q('action')` 分派（`save` / `reset`）→ 校验 → `setting_set()` → `audit_log()` → `flash_set()` → `redirect_self()` → `page_header('抽卡设置','gacha')` … `page_footer()`。 |
| **3** | 注册导航 | `inc/helpers.php`（改 `nav_items()`，1-2 行） | 在游戏/卡密分组后新加一段分组 + 一行链接，如 `'__g_gacha' => array('抽卡', null),` + `'gacha' => array('抽卡设置', 'pages/gacha.php'),` |
| **4** | 建表（**仅当需要存非 k-v 的数据**，如卡池运营记录） | 幂等 ALTER/CREATE SQL 放 `server/deploy/_audit/`，**同时**在 `inc/gacha.php` 里懒建 | 抄 `cardadmin_php/inc/players.php:100-130` 或 `server/deploy/_audit/alter_cards_cardtype.sql`（`PREPARE/EXECUTE` + `@has_xxx` 判存在）。**同步补 `sql/schema.sql`**（否则下一个新环境装出来的库少表） |
| **5** | 部署 | 3 个文件 + 1 个 SQL | ①备份：`mysqldump ba_cardadmin > ...`；②传 `inc/gacha.php`、`pages/gacha.php`、`inc/helpers.php`；③`php -l` 过一遍；④`/etc/init.d/php-fpm-82 reload`；⑤打开 `/pages/gacha.php` 验收 |

**回答"最少动几个文件"：2 个新文件（`inc/gacha.php` + `pages/gacha.php`）+ 1 处修改（`inc/helpers.php` 的 `nav_items()`）= 3 个文件。**
若完全不进导航，可缩到 **2 个**（只能手敲 URL —— 但线上 `bans.php` 就是这么漏掉的，不建议）。

### 6.2 建议的字段与 key 命名（贴合现有风格）

| 项 | key | 默认值 | 校验 |
|---|---|---|---|
| 3★ 出彩率 | `gacha_rate_3` | `0.795` | `float`，0~1 |
| 2★ 出彩率 | `gacha_rate_2` | `0.18` | 同上 |
| 1★ 出彩率 | `gacha_rate_1` | `0.025` | 同上；三项和应为 1（保存时校验，容差 1e-6） |
| 单抽消耗道具 id | `gacha_cost_item_id` | 服务端约定值 | `int > 0` |
| 单抽消耗数量 | `gacha_cost_single` | `1` | `int 1..100` |
| 十连消耗数量 | `gacha_cost_ten` | `10` | `int 1..1000` |
| 十连保底（保底 2★ 及以上） | `gacha_guarantee_ten` | `1` | `0/1` |
| 每日免费次数 | `gacha_free_daily` | `0` | `int 0..99` |
| 卡池开关 | `gacha_banner_enabled` | `1` | `0/1` |

> 注意：`post_int()` 有 min/max 夹取（`helpers.php:55-59`），浮点没有现成封装 —— 需要新写一个 `post_float()` 或在本页内 `(float)` + `is_finite()` + 范围判断。**不要**直接把 `$_POST` 喂 DB。

### 6.3 页面必须包含的"惯例动作"

- 表单里 `<?php echo csrf_field(); ?>`（一个都别漏，`verify_csrf` 是全页 POST 前置）。
- 每个 form 带 `<input type="hidden" name="action" value="...">`。
- 「恢复默认」按钮：`onsubmit="return confirm('确定把 N 项设置恢复为默认值？')"`，POST `action=reset`。
- 保存/恢复后都要 `flash_set()` + `redirect_self()`。
- 底部显示"当前值 vs 默认值"对照表，方便看出哪些被改过（用 `setting_get($k, null) !== null` 判断是否被覆盖——这是本项目现成的"是否被改过"判据）。

---

## 7. 跟后端（C# / Python 桥）的交互方式

### 7.1 先给结论

| 交互类型 | 有没有先例 | 怎么做的 |
|---|---|---|
| 调后端 **HTTP API**（主要方式） | ✅ **有，而且是玩家域唯一方式** | `inc/ba.php` 的 `ba_get()` / `ba_post()` → `POST /api/admin/*`，头带 `X-Admin-Key` |
| 直接改**服务端文件** | ⚠️ 有，但只限 `cards.json` 一个文件 | `inc/sync.php` 用 `atomic_write()`（临时文件 + `rename` + `flock`），且**多数情况是 cron 以 root 身份写，不是 web 用户写** |
| **重启服务端** | ❌ **完全没有** | 全项目 `systemctl` / `service ` / `exec(` / `shell_exec` / `proc_open` **0 处** |
| 直接写 **shittim.sqlite3** | ❌ 明文禁止 | `inc/players.php:10` 注释："不碰 /root/shittim.sqlite3（www 无权限，且写库约束散在 C# 里）"；页面也写明 `settings.php:435-437` |
| 写**面板自己的库/文件** | ✅ 唯一常规路径 | MySQL + `state/` + `logs/` |

### 7.2 HTTP API 的具体清单（`/api/admin/*`，都在 `inc/ba.php`）

| 函数 | 端点 | 用途 |
|---|---|---|
| `ba_status()` | `GET /api/admin/status` | 服务端状态 |
| `ba_accounts()` | `GET /api/admin/accounts` | 账号列表 |
| `ba_account_detail()` | `GET /api/admin/account/{id}/detail` | 账号详情 |
| `ba_account_currencies/items/characters/mails()` | `GET /api/admin/account/{id}/*` | 分域详情 |
| `ba_static_currencies/items/characters()` | `GET /api/admin/static/*` | 静态表 |
| `ba_parcel_types()` | `GET /api/admin/meta/parceltypes` | 包裹类型枚举 |
| `ba_mail_send()` / `ba_mail_delete()` | `POST /api/admin/mail/send` / `delete` | 发奖 / 删邮件 |
| `ba_currency_set()` | `POST /api/admin/currency/set` | 改货币（绝对值） |
| `ba_account_update()` / `ba_account_create()` | `POST /api/admin/account/update` / `create` | 改账号属性 / 建号 |
| `ba_item_give()` / `ba_item_remove()` | `POST /api/admin/items/give` / `remove` | 发/删道具 |
| `ba_command()` | `POST /api/admin/command` | GM 命令（`console.php` 用） |
| `ba_health()` | 综合探测 | 设置页「测试连接」 |

**没有** `/api/admin/gacha/*`、没有 `/api/admin/settings/*`。gacha 相关**唯一**入口是 `console.php` 的命令 `gacha <...> 抽卡模拟`（`pages/console.php:43`），是**对单个玩家做一次抽卡模拟**，不是改概率。

### 7.3 直接改服务端文件的先例（唯一一个，且很谨慎）

`inc/sync.php` 把 MySQL 导出成 `cards.json`，写文件用 `atomic_write`：

`inc/sync.php:488`
```php
$wr = atomic_write($json_path, $built['payload'], 0644);
```
`inc/helpers.php:416-453`（原子替换，跨文件系统退化为 copy+unlink）
```php
function atomic_write($path, $data, $mode = 0640)
{
    $tmp = $path . '.tmp.' . getmypid() . '.' . mt_rand(1000, 9999);
    ... @file_put_contents($tmp, $data, LOCK_EX) ... @chmod($tmp, $mode);
    if (!@rename($tmp, $path)) { /* 跨 fs：copy + unlink */ }
}
```
但注意「谁在写」有权限隔离：web 用户通常**写不了** `/root/bapatch`（`inc/sync.php:6`、`README.md:248`、`:329-332`）。写不了时面板只落一个"同步请求标记"，由 root 的 cron 真写：
```php
$wr = atomic_write(sync_flag_path(), (string)$payload, 0644);   // inc/sync.php:663
```
→ **抽卡设置页若想改服务端文件，会撞同一堵墙**：`open_basedir` 只放行 `ba_cardadmin/`、`/tmp/`、`ba_sdk/`（见 §0.2），且 web 用户对服务端目录无写权限。**不要**设计"页面直接改服务端文件"，除非同时改 open_basedir + 文件属主 + 接受 web 进程能写服务端资产的安全代价。

### 7.4 ★ 抽卡数据到底在哪（这条决定整个方案）

**抽卡概率/消耗不在 MySQL、不在 `settings`、不在任何 admin API，而在服务端 Excel 表**：

- 数据源：`work/ba/data/ExcelDB.db`（国服 `ExcelDB.db`，160 MB，398 张表）。
- 相关表（`plan/20261119/ALL_GACHA_TABLES_SCAN.md`）：
  `GachaElementDBSchema`(14922 行) / `GachaElementRecursiveDBSchema`(669) / `GachaGroupDBSchema`(1556) / `GachaCombinedCostDBSchema`(24) / `GachaSelectPickupGroupDBSchema`(98) / `ShopRecruitDBSchema`(532) / `ShopFreeRecruitDBSchema`(8) / `LocalizeGachaShopDBSchema`(1235) …
- **每张表只有 `Id` + `Bytes BLOB`**（序列化后的 Excel 行），**不是**可 `UPDATE 概率=0.03` 的普通列。

服务端怎么消费（`srv_src/Shittim-Server/`）：
```
ExcelTableService.GetTable<T>()            Services/ExcelTableService.cs:33    // 单例，带 cache
  └─ ShopManager:42   _shopRecruitmentExcels = _excelTableService.GetTable<ShopRecruitExcelT>()   // ← 构造时缓存进字段
  └─ ParcelHandler:42 _gachaElementExcels    = _excelService.GetTable<GachaElementExcelT>()       // ← 同上
  └─ ItemManager:31   gachaElementExcels    = excelTableService.GetTable<GachaElementExcelT>()    // ← 同上
```
`GetTable<T>(bool bypassCache = false, bool isExcelDB = false)` 有 `bypassCache` 逃生口，但各 Manager 已经把列表**存进自己的字段**，绕过缓存对它们无效。

**⇒ 三条硬结论（写需求时必须让 lead 知道）：**

1. **没有任何 API 能改抽卡概率**。要加，得在 Shittim 里新增 `/api/admin/gacha/*`（带 `AdminAuthAttribute`），由它去改 Excel 或改内存——这是 C# 侧的开发量，不是 PHP 页面的工作量。
2. **改 ExcelDB.db 必须重启服务端**才生效（`ExcelTableService` 单例 + Manager 字段缓存）。而**面板没有重启能力**，也没有任何先例，重启只能由运维手动做。
3. 因此「抽卡设置」页**当前只能做到**：把配置存进面板自己的 `settings` 表（默认值 + 一键恢复默认都能完整实现），**并明确标注"需服务端支持后再生效"**。若一定要立即生效，方案只有两个：
   - **方案甲（推荐）**：加 C# `/api/admin/gacha/rates`（读改写内存 + 持久化到 Excel 或自有表），面板只做 HTTP 调用 → 影响面最小、可审计、可回滚。
   - **方案乙**：面板写一个 `gacha_override.json`，C# 启动时叠加到 Excel 之上 → 仍需重启，但至少面板与 Excel 解耦、可 diff。

### 7.5 Python 桥（`sdkcard.py` / `account_service.py`）

- 面板与 Python 侧**不直接调 API**，唯一接触点是 **`cards.json` 文件**（Python 读、面板/cron 写）和 **`sdk.log`**（Python 写、面板只读解析，`helpers.php:579` `parse_sdk_log()`，注释明确"只读，绝不修改文件"）。
- 桥接账号库 `accounts.db`（SQLite）面板**只读**（`inc/players.php` `player_accounts_db_path()`，`settings.php:385-393` 显示可读状态）。
- Python 侧自己有写库（`work/ba/cardadmin/db.py:311` 用 `ALTER TABLE` 自建列），与 PHP 面板是**两套独立库**，别混。

---

## 8. 给「抽卡设置」页面的落地建议（含风险）

1. **第一步只做面板侧**：`inc/gacha.php`（默认值数组 + 读写函数）+ `pages/gacha.php`（表单 + 保存 + 恢复默认）+ `nav_items()` 一行。**先把"默认值 + 一键恢复默认"跑通**，这是本次需求里能 100% 交付的部分。
2. **默认值只写一处**：`gacha_defaults()` 返回数组，页面渲染用 `setting_get($k, $gacha_defaults[$k])`，「恢复默认」用 `DELETE FROM settings WHERE k IN (前缀) + setting_reload()`。**别把默认值同时写进 SQL 的 DEFAULT 和 PHP**，会出现两套真值。
3. **概率三项做"和为 1"校验**，容差 1e-6；不合法直接 `flash_set(...'err')` + `redirect_self()`，**不落库**（照 `settings.php:46-57` 的风格）。
4. **生效问题必须在页面上明说**：页面底部放一行 `muted small`，写清"本页只管理面板配置；服务端 `/api/admin/gacha` 未实现前不会影响实际出货"（现有页面就是这么写"只读/不生效"提示的，如 `settings.php:434-437`）。
5. **别碰 `data/ExcelDB.db`**：160 MB、BLOB 序列化、服务端启动时校验 SQLCipher key（`ExcelTableService.cs:307-345`），面板侧任何直写都会破坏服务端启动。
6. **部署前**先补齐 §0.2 的缺口，尤其：线上 `bans.php` 要先进主树，否则整目录覆盖会删功能。

---

## 9. 一句话索引（改哪里找哪里）

| 想改 | 去哪个文件 | 位置 |
|---|---|---|
| 加/改导航 | `inc/helpers.php` | `nav_items()` `:834-860` |
| 改页面外壳（侧栏/顶栏/flash 渲染） | `inc/helpers.php` | `page_header()` `:867-921` / `page_footer()` `:923-936` |
| 改登录/限速/会话 | `inc/auth.php` | `:166-261`（登录）`:75-118`（会话）`:185-198`（限速） |
| 改 CSRF | `inc/auth.php` | `:283-292` `:437-469` |
| 加审计动作 | 调用方 → `inc/auth.php` | `audit_log()` `:615-638` |
| 加配置项（k-v） | 调用方 → `inc/helpers.php` | `setting_get/set/reload` `:457-502` |
| 加表/加列 | `inc/<模块>.php` 懒建 + `server/deploy/_audit/*.sql` | 抄 `inc/players.php:92-134` |
| 调后端接口 | `inc/ba.php` | `ba_http()` `:80-160`，`ba_get/ba_post` `:161-174` |
| 改导出 cards.json | `inc/sync.php` | `atomic_write` 调用 `:488`；`sync_cards_has_type_cols()` `:139-159` |
| 部署/回滚清单的写法 | `server/deploy/_audit/FEATURE_CARDTYPE_PHP_20261118_0109.md` | `§7` `:197-231` |
| 幂等 ALTER 的写法 | `server/deploy/_audit/alter_cards_cardtype.sql` | 全文 |

---

## 附：本报告的证据边界

- 只读了**本地**文件：`work/ba/cardadmin_php/**`、`work/ba/srv_live/20261118_0059|2200/**`、`work/ba/srv_src/Shittim-Server/**`（仅 `AdminAuthAttribute.cs`、`ExcelTableService.cs`、若干 `GetTable<Gacha*>` 调用点）、`work/ba/server/deploy/_audit/**`、`work/ba/plan/20261118|20261119/*.md`（仅相关几篇）。
- **未**登录服务器、**未**连数据库、**未**执行任何 `mysql/php/curl`、**未**改任何既有文件。
- 「现有表 11 张」是**从 PHP 里的 SQL 语句反推**的，不是从活库 `SHOW TABLES` 读的。线上真实 schema 需按 §0.2 拉取后复核。
- 行数/字节数取自本地文件；线上同文件可能有个位数差异（`bans.php` 已证线上比主树多）。
