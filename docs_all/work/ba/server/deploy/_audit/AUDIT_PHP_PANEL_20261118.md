# PHP 面板安全审计（只读）

> 目标：`http://<SERVER_IP>:8081/`（宝塔站点，root `/www/wwwroot/ba_cardadmin`）
> 日期：2026-11-18 00:47–01:0x
> 方式：**只读**。本地源码 `work/ba/cardadmin_php/` + 线上 `ls/cat/grep/sha256sum` 对照；未写入、未改任何 php、未做 MySQL 写操作、未访问公网页面。
> 证据规则：每条给「文件:行号 + 代码原文」，≤6 行；标注 **高危/中危/低危/已做对** 与 **已证实/推断**。

---

## 0. 本地 vs 线上：一致性结论

用 `sha256sum` 对全部 `*.php/*.js/*.css` 做双向比对：

| 结果 | 内容 |
|---|---|
| **27/27 逐字节一致** | 所有已部署的 php/js/css（含新增的 `inc/ba.php`、`inc/players.php`、`pages/{players,player_detail,mail,currency,items,console}.php`） |
| 线上缺失 | `install.php`（安装完已删，**正确**） |
| 仅线上有 | `config.php`（含 DB 口令，640 www:www） |
| 线上额外数据 | `state/`（bacache、cards.backup.json、sync.lock）、`logs/sync.log` |

⇒ **本报告的本地行号 = 线上行号**。没有"本地与线上漂移"这一类高危发现。

---

## 1. 总表

| # | 级别 | 结论 | 位置 | 证实 |
|---|---|---|---|---|
| H1 | **高危** | 面板监听 **8081 明文 HTTP**，无 TLS；登录口令/会话 Cookie/Admin Key 全程可被中间人读取 | live `<SERVER_IP>.conf:3` | 已证实 |
| H2 | **高危** | PHP **`display_errors=On`**：任何 warning/未捕获异常会把绝对路径、SQL 片段打到浏览器 | live `/www/server/php/82/etc/php.ini:508` | 已证实 |
| M1 | 中危 | Shittim **AdminApiKey 明文回显在 HTML**（`type="text"`），key 等价 Shittim 全权 admin API | `pages/settings.php:390` | 已证实 |
| M2 | 中危 | **无角色/权限分级**：任意管理员可管理其他管理员，也可发邮件/改货币/执行 GM 命令/封号 | `pages/admins.php:5-6` | 已证实（代码注释自述） |
| M3 | 中危 | **路径设置无白名单**：`cards_json_path` 可指到任意绝对路径，最终以 www 身份 `atomic_write`；受 `.user.ini` 的 `open_basedir`（`ba_cardadmin:/tmp:ba_sdk`）约束，可覆盖**面板自身文件**（如把 `config.php` 写成 cards JSON ⇒ 面板锁死），但写不进 `ba_sdk`（root:root 755） | `pages/settings.php:65-79` → `inc/sync.php:417` | 已证实（逻辑） |
| M4 | 中危 | **发奖/改货币不写 `audit_logs`**，只写 `panel_ops`；审计页看不到这些操作 | `pages/mail.php:134`、`pages/currency.php:109`（`audit_log` 0 次） | 已证实 |
| M5 | 中危 | 登录失败路径**回显 DB 异常原文**（叠加 H2 会暴露 DSN/路径） | `login.php:50-53` | 已证实 |
| M6 | 中危 | **高危操作无二次确认**：GM 命令台/全服发邮件/批量改货币/发道具，`confirm=` 均为 0 | `pages/console.php:147`、`pages/mail.php:308` 等 | 已证实 |
| L1 | 低危 | 明文卡密查看/导出走 **GET**，仅会话校验、无 CSRF | `pages/cards.php:15-26`、`pages/cards_export.php:14-16` | 已证实 |
| L2 | 低危 | 登录页 CSRF token 存 **cookie**（`ca_csrf`），非会话绑定 | `inc/auth.php:288-294` | 已证实 |
| L3 | 低危 | 会话 token **明文入库**（`sessions.token`），DB 只读泄露即可劫持会话 | `inc/auth.php:243-250` | 已证实 |
| L4 | 低危 | `logs/sync.log` 权限 **666**（世界可写），仅靠 nginx deny `/logs/` 兜底 | live `ls -l`：`-rw-rw-rw- 1 www www` | 已证实 |
| L5 | 低危 | 本地仍保留 `install.php`（线上已删）；误传回线上即可重装/接管 | 本地 `install.php`；线上 `ls` 无 | 已证实 |

---

## A. SQL 注入

### A1. 有没有字符串拼接进 SQL —— **没有**

全站 SQL 都是 `db_run/db_all/db_row/db_val`（预处理）。检索 `query(`/`mysql_query`/`mysqli_` 且同行含 `$_`：**0 命中**；`SELECT|INSERT|UPDATE|DELETE|WHERE` 后接 `$_GET/$_POST/$_REQUEST`：**0 命中**。

`inc/db.php:112-119`：

```php
$dsn = 'mysql:host=' . DB_HOST . ';port=' . (int)DB_PORT . ';dbname=' . DB_NAME . ';charset=utf8mb4';
$pdo = new PDO($dsn, DB_USER, DB_PASS, array(
    PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
    PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
    PDO::ATTR_EMULATE_PREPARES   => false,
```

### A2. 统一预处理 —— **是**

`inc/db.php:143-148`：

```php
function db_run($sql, $params = array())
{
    $st = db()->prepare($sql);
    $st->execute($params);
    return $st;
}
```

动态 `ORDER BY`/`LIMIT` 都是白名单或 `(int)`，例如 `inc/players.php:167`：`... LIMIT ' . (int)$limit`。
**结论：已做对。** 唯一"拼接"是 `db.php:112` 的 DSN，值来自 `config.php` 常量（非用户输入）。

---

## B. 鉴权与会话

### B1. 登录态怎么存 —— 自定义 Cookie + sessions 表（**没有用 PHP session**）

`inc/auth.php:243-250`（登录成功时**新建** 32 字节随机 token，等效 `session_regenerate_id`）：

```php
$token = rand_token(32);
$csrf  = rand_token(16);
$exp   = $now + (int)SESSION_TTL;
db_run(
    'INSERT INTO sessions (token, admin_id, created_at, expires_at, ip, user_agent, csrf, flash)
     VALUES (?, ?, ?, ?, ?, ?, ?, NULL)',
    array($token, (int)$row['id'], $now, $exp, $ip, user_agent(), $csrf)
);
```

Cookie 属性 `inc/auth.php:46-54`：`httponly=true, samesite=Strict, secure=is_https()`。
会话校验 `inc/auth.php:86,105-115`：64-hex 正则、过期即删、`admins.enabled!==1` 立即失效。
**已做对**（L3 是 token 明文入库的残余风险）。

### B2. 有没有未鉴权可访问的页面/接口 —— **没有**

逐个文件确认：所有 `pages/*.php`、`index.php` 第 5–21 行内都有 `require_login();`（`index.php:14`、`pages/players.php:16`、`pages/settings.php:14` 等）。
`login.php` / `logout.php` 是唯一例外（设计如此）。
`cron/sync_cards.php:20-27` 有 CLI-only 闸：

```php
if (PHP_SAPI !== 'cli') {
    ...
    echo "403 Forbidden: this script is CLI-only\n";
    exit(1);
}
```

`inc/`、`cron/`、`sql/`、`state/`、`logs/` 由 nginx 403（见 E3）。
**已做对。**

### B3. 越权 —— 同类越权没有；**横向越权（管理员之间）存在**

- 玩家数据：所有动作按 `sid`（ServerId）走 Shittim admin API，**不存在"玩家登录态"这一层**，所以没有玩家侧越权入口。
- 管理员之间：**没有任何权限分级**，`pages/admins.php:5-6` 原文自述：

```php
 * 说明：这里没有角色体系，任何管理员都能管理其他管理员。
 * 想更安全就只留一个管理员账号，并改掉默认用户名。
```

⇒ 任意管理员 = 超管（可重置/禁用其它管理员、执行 GM 命令、发全服邮件）。**M2，已证实。**

---

## C. CSRF / XSS

### C1. 所有 POST 表单有没有 CSRF —— **有，且统一**

`inc/auth.php:304-330`：

```php
function verify_csrf()
{
    $sent = isset($_POST['_csrf']) ? (string)$_POST['_csrf'] : '';
    $want = csrf_token();
    if ($sent === '' || $want === '' || !hash_equals($want, $sent)) {
```

每个写操作页首个 POST 分支即 `require_post_csrf()`：`pages/cards.php:93`、`cards_new.php:25`、`cards_import.php:31`、`admins.php:18`、`mail.php:40`、`currency.php:39`、`items.php:50`、`console.php:65`、`players.php:20`、`player_detail.php:20`、`settings.php:24`、`logs.php:101`、`dashboard.php:18`。
模板里 `csrf_field()`（`auth.php:298-301`）。
**已做对。** 残余：L1（GET 明文卡密）、L2（登录页 cookie token）。

### C2. 输出到 HTML 有没有转义 —— **有，统一 `e()`**

`inc/helpers.php:18-21`：

```php
function e($v)
{
    return htmlspecialchars((string)$v, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}
```

- `echo $_GET/$_POST/$_COOKIE` 裸输出：**0 命中**。
- 列表/详情里的昵称、卡密、日志原文都包了 `e()`：如 `pages/console.php:134` `e($p['nickname'])`、`pages/logs.php:343` `e(str_limit((string)$r['raw'], 60))`。
- 内联 JSON 用 `json_encode`（`pages/mail.php:391`、`pages/players.php:292`），未发现拼字符串进 `<script>`。
**已做对。**

---

## D. 危险操作

### D1. `exec/system/shell_exec/passthru/popen` —— **没有**

全站只有一处 `exec()`，且是安装向导执行**内置** schema 语句（非用户输入）：

`install.php:195`：

```php
$pdo->exec($s);
```

（`install.php` 线上已删除；本地保留仅作参考。）
**已做对。**

### D2. 文件上传/删除/读写 —— 上传无路径拼接；**存在"任意绝对路径写"**

- 导入：`cards_import.php` 只读上传内容入 MySQL，**不落盘**；`MAX_UPLOAD_BYTES=2MB`（`db.php:65-67`）。
- cards.json 写出：路径来自设置，未做白名单。`pages/settings.php:65-79`：

```php
} elseif ($act === 'save_paths') {
    $jp = trim(post_q('cards_json_path'));
    $lp = trim(post_q('sdk_log_path'));
    if ($jp === '' || substr($jp, 0, 1) !== '/') {
        flash_set('cards.json 必须是绝对路径（以 / 开头）', 'err');
```

`inc/sync.php:417`：

```php
$wr = atomic_write($json_path, $built['payload'], 0644);
```

⇒ 管理员可把 `cards_json_path` 指到 www 可写的任意文件（内容固定为 cards JSON）。**实际可写范围 = `open_basedir` 内的 `ba_cardadmin/` 与 `/tmp/`**（`.user.ini:1`：`open_basedir=/www/wwwroot/ba_cardadmin/:/tmp/:/www/wwwroot/ba_sdk/`；`ba_sdk` 为 root:root 755，www 写不进去）。后果：可把 `config.php`/`index.php` 覆盖成 JSON ⇒ **面板锁死**，或把同步目标指到错文件。**M3，已证实（需管理员会话 + CSRF token）。**
- 删除：只删 MySQL 行 / 调 admin API，无 `unlink($_...)`。
- `ba_cache_flush()` 用 `glob($d.'/*.json')` + `unlink`，目录固定 `state/bacache`（`inc/ba.php:210-222`）。

### D3. `eval` / 动态 include —— **没有**

`include/require` 带变量的只有 `db.php:18` `require_once $__ca_cfg;`，路径固定 `dirname(__DIR__).'/config.php'`。

---

## E. 敏感信息

### E1. 硬编码口令/密钥（只列字段名）

`config.php.example:28-43`（模板）：`DB_HOST / DB_PORT / DB_NAME / DB_USER / DB_PASS / APP_SECRET`。
线上 `config.php` 定义了：`DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASS/APP_NAME/APP_SECRET/APP_TIMEZONE/APP_DEBUG/APP_BASE/CARDS_JSON_PATH/SDK_LOG_PATH/SESSION_TTL/MAX_UPLOAD_BYTES/MAX_BATCH_GEN`（**不含 BA_ADMIN_KEY**，key 落 MySQL `settings.ba_admin_key`）。
线上权限 `-rw-r----- 1 www www`（640）——**已做对**。
**未贴任何值。**

### E2. 错误输出会不会露 SQL/路径 —— **会（H2 + M5）**

- 运行时 `display_errors=On`：`/www/server/php/82/etc/php.ini:508` ⇒ 任何 warning/异常都会打到页面（含绝对路径）。
- 代码里再主动回显一次：

`login.php:50-53`：

```php
} catch (Throwable $e) {
    /* 数据库挂了也要给出人话，不要白屏 */
    $err = '数据库暂时不可用，请检查 config.php 与 MySQL 状态：' . $e->getMessage();
}
```

⇒ 建议线上 `display_errors=Off` 且此处只回显固定文案（**只出结论，不写修复代码**）。

### E3. 目录/文件暴露面（补充）

live `<SERVER_IP>.conf:25-31` 已 deny：`config.php`、`/inc/`、`/cron/`、`/sql/`、`/state/`、`/logs/`，`autoindex off`。**已做对。**
但 `logs/sync.log` 本身 666（L4），若哪天 nginx 规则被改，就是"可读 + 可篡改"。

---

## F. 与 BA 服务端的桥接

### F1. AdminApiKey 从哪来、有没有进前端

`inc/ba.php:24-47`：先读 `config.php` 的 `BA_ADMIN_KEY`，没有则回落 MySQL `settings.ba_admin_key`；`inc/ba.php:88-91` **只在服务端**加请求头：

```php
$headers = array('Accept: application/json');
if ($c['key'] !== '') {
    $headers[] = 'X-Admin-Key: ' . $c['key'];
}
```

⇒ key 不进前端 JS（好）。**但**设置页把它明文渲回 HTML——**M1**：

`pages/settings.php:389-390`：

```php
<div class="field"><label>Admin Key（X-Admin-Key）</label>
  <input type="text" name="ba_admin_key" value="<?php echo e($baKey); ?>" placeholder="与服
务端 Config.json 的 AdminApiKey 一致" autocomplete="off">
```

保存时也只记 `key_len`（`settings.php:97-98`），这点是对的；问题只在**回显**：任何拿到会话的人（或 XSS/截图/浏览器自动填充）都能读走 key，而 key 持有者可直接调 Shittim `/api/admin/*`（改账号、发邮件、执行命令）。

### F2. 危险功能有没有二次确认/权限分级/审计

| 功能 | 二次确认 | 权限分级 | 审计 |
|---|---|---|---|
| GM 命令台 `console.php` | ❌（`confirm=` 0，`console.php:147` 直接 submit） | ❌ 所有 admin | ✅ `audit_log('console.command')` + `panel_op_log`（`:99-102`） |
| 发邮件/发奖 `mail.php` | ❌（`mail.php:308`） | ❌ | ⚠️ 仅 `panel_op_log('mail.send')`（`:134`），**无 `audit_log`** |
| 批量改货币 `currency.php` | ❌ | ❌ | ⚠️ 仅 `panel_op_log('currency.batch')`（`:109`） |
| 发道具/快捷动作 `items.php` | ❌ | ❌ | ⚠️ `panel_op_log`（`:99,114,135`） |
| 封号/解封 `players.php`/`player_detail.php` | ✅ 前端 confirm（`players.php:190`、`player_detail.php:184`） | ❌ | ✅ `audit_log`（`players.php:47`、`player_detail.php:30`） |
| 清空邮件 `player_detail.php:350` | ✅ confirm | ❌ | ✅（action 分支内） |

⇒ 结论：**审计有，但分裂在两套表**（`audit_logs` vs `panel_ops`），且**高危操作没有二次确认、没有权限分级**。**M4/M6/M2。**

---

## G. 已做对（不要重复改）

1. SQL 全预处理、`EMULATE_PREPARES=false`（A1/A2）。
2. 所有写页统一 `require_post_csrf()` + `hash_equals`（C1）。
3. 输出统一 `e()`（ENT_QUOTES），无裸 echo 超全局（C2）。
4. 登录成功即发新随机 token（等效 session_regenerate_id），Cookie HttpOnly+SameSite=Strict，`secure` 随 https（B1）。
5. 登录限速：同 IP 5 次失败锁 10 分钟 + 失败固定 0.3s 延迟（`auth.php:185-233`）。
6. 密码 `bcrypt(hmac_sha256(pw,salt))`，新建/改密要求 ≥12 位（`auth.php:424-428`、`admins.php:31`）。
7. 管理员不能禁用自己；系统至少保留 1 个启用管理员（`admins.php:83-93`）。
8. 改密后使该管理员其它会话失效（`admins.php:70-73`）。
9. 无 `exec/eval/动态 include`（D1/D3）。
10. Shittim 库只读打开（`SQLITE_OPEN_READONLY`，`inc/players.php:45-54`），不直写游戏库（`players.php:10` 注释）。
11. cron 脚本 CLI-only；`install.php` 线上已删除（B2）。
12. nginx deny 敏感目录 + `autoindex off`（E3）。
13. 卡密默认脱敏展示，明文查看/导出有审计（`cards.php:24`、`cards_export.php` 头注）。

---

## H. 按优先级排序的"缺什么校验"（不写修复代码）

1. **H1** 缺 HTTPS/TLS（或至少只监听 127.0.0.1 + SSH 隧道）；缺 `Secure` cookie 的传输前提。
2. **H2** 缺生产环境 `display_errors=Off`。
3. **M1** 缺 Admin Key 的"只写不回显"（改 password 类型/掩码 + 留空表示不变）。
4. **M2** 缺角色模型（至少区分"只读运营"与"超管"）。
5. **M3** 缺路径白名单（`cards_json_path` 应只允许固定目录）。
6. **M4** 缺统一审计（发奖/改货币应同时写 `audit_logs`）。
7. **M6** 缺高危操作二次确认（GM 命令、全服邮件、批量货币）。
8. **L1/L2/L3/L4/L5** 见总表。

---

## 附：本文的核对命令（只读）

```bash
# 本地 vs 线上逐文件哈希
find /www/wwwroot/ba_cardadmin -type f -exec sha256sum {} +
# 目录/权限
ls -laR /www/wwwroot/ba_cardadmin
# nginx 保护规则
grep -n 'listen 8081\|location' /www/server/panel/vhost/nginx/<SERVER_IP>.conf
# PHP 错误显示
grep -n '^display_errors\|^error_reporting' /www/server/php/82/etc/php.ini
# 与本报告对应的代码起点
grep -n 'require_login\|require_post_csrf' pages/*.php
```
