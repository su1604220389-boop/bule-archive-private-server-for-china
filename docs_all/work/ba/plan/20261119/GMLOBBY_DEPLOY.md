# GM 面板「一键发放全部记忆大厅」部署（GMLOBBY）

- 时间：2026-11-19 23:43（Asia/Shanghai）｜ 执行：srv-ops
- 站点根：`/www/wwwroot/ba_cardadmin`
- **最终判定：部署成功 · 全部验证通过 · KEEP（保留）**

## 1. 两份文件（sha256 实测与要求一致）

| 相对路径 | 操作 | 字节 | sha256 | 实测 |
|---|---|---|---|---|
| `inc/gm_lobby.php` | **新增** | 15,579 | `7623fe9889eac4c26e1d8b45eaad7a21049f45c158288f7247b06cbdb74ec268` | ✅ |
| `pages/items.php` | **覆盖** | 24,248 | `25f7e2b3d29fec83fcc5abf57b121c2c733e491dd958d712f9693f4767dc0c26` | ✅ |

覆盖前 `pages/items.php` 基线：`9ff1f66bf5e4213bdaf24cb8fcbf76bc6cca3561383c71a0e56f227d0edc1b97` / 15,807 B / `www:www 644`
`inc/gm_lobby.php` 部署前**确认不存在**（`ls` 报 No such file）。

## 2. 备份与回滚

```
备份目录：/root/GMLOBBY_20261119_234350/
   items.php     （改前 9ff1f66b… / 15,807 B / www:www 644）
   BEFORE.txt    （sha256 + 字节数 + 属主权限）
   ROLLBACK.sh
```

**ROLLBACK.sh 完整路径：**
```
/root/GMLOBBY_20261119_234350/ROLLBACK.sh
```
逻辑：还原 `pages/items.php` → 删除 `inc/gm_lobby.php` → `systemctl reload php-fpm-82` → 打印恢复后 sha256 → 打一次 `items.php` 状态码。
（另有全量备份 `/root/PRE_P0_20261119_023546/panel_ba_cardadmin.tgz`。）

## 3. 语法检查

**替换前（上传件）**
```
No syntax errors detected in /tmp/gm_lobby_inc.php
No syntax errors detected in /tmp/gm_items_page.php
```
**替换后（线上两份）**
```
No syntax errors detected in /www/wwwroot/ba_cardadmin/inc/gm_lobby.php
No syntax errors detected in /www/wwwroot/ba_cardadmin/pages/items.php
```

## 4. 未登录访问

```
/pages/items.php       -> **302**  redirect=http://127.0.0.1:8081/login.php?next=%2Fpages%2Fitems.php
/pages/gacha_rates.php -> 302
⇒ 跳登录，**没有 500、没有白屏** ✅
```

## 5. 关键字与页面内容

```
grep -c '发放全部记忆大厅' pages/items.php = **7**
grep -c 'gm_lobby'        pages/items.php = **2**
相关行：
  16: require_once __DIR__ . '/../inc/gm_lobby.php';
  39: 'give_memory_lobby' => array('发放全部记忆大厅', '',
  40:     '把客户端认识的 258 个记忆大厅做成邮件附件发给玩家（幂等，重复点只会多几封邮件）'),
  102: /* ── 发放全部记忆大厅：走邮件接口，不走 GM 命令 ── */
  109: flash_set('「发放全部记忆大厅」需要页面上的二次确认（确认框）', 'err');
  308: /* 记忆大厅：258 个 id 的发送计划（不发请求），供按钮下方那行说明与输入框用 */
  329: 每封邮件的包裹数（1–<?php echo (int)$lobbyCount; ?>，…）
  340: 记忆大厅自检：…
  344: 只发放客户端认识的 … 个记忆大厅
```

## 6. 258 个 id 自检（实际输出）

```
$ php -r 'require ".../inc/gm_lobby.php"; ...'
  ids 类型 = array ｜ 数量 = **258**
  唯一值数量 = **258**
  selfcheck: {"ok":true,"expected":258,"actual":258,"unique":258,"warn":""}
```
页面级加载自检（模拟真实包含链）：
```
  helpers+gm_lobby loaded OK ｜ ids=258
```

## 7. 文件权限 / 属主

```
-rw-r--r-- 1 www www 15579 Nov 19 23:43 /www/wwwroot/ba_cardadmin/inc/gm_lobby.php
-rw-r--r-- 1 www www 24248 Nov 19 23:43 /www/wwwroot/ba_cardadmin/pages/items.php
-rw-r--r-- 1 www www 17396 Nov 18 01:03 /www/wwwroot/ba_cardadmin/pages/mail.php   （同目录对照）
```

## 8. 错误日志（零新增）

```
php-fpm 日志最近 20 行：**无 error/fatal/warn**
/www/wwwlogs/php_82_error.log 最近 6 行：全是 11-18 的历史记录
  （03:19–03:21 open_basedir 警告；21:51/21:55 我早前探测脚本造成的 db_installed 重声明）
⇒ **本次部署没有产生任何新的 PHP 告警**
```

## 9. 不该变的三个文件（部署后逐一对比）

```
/www/wwwroot/ba_cardadmin/inc/gacha.php          1152ff4c…  未变 ✅
/www/wwwroot/ba_cardadmin/pages/gacha_rates.php  105f151c…  未变 ✅
/www/wwwroot/ba_cardadmin/inc/ba.php             752f1637…  未变 ✅
```

## 10. 测试邮件（按要求未动）

```
ServerId  AccountServerId  Sender  Comment                       ReceiptDate
128       4                GM      测试：记忆大厅 A 单个-字符串Type     （空）
129       4                GM      测试：记忆大厅 C 60个              （空）
130       4                GM      测试：记忆大厅 D 258个             （空）
131       4                GM      测试：记忆大厅 F 500个(重复id…)     （空）
132       4                GM      测试：记忆大厅 G 1000个(重复id…)    （空）
⇒ 5 封全部保留、均未领取，等用户确认 131/132 是否删
```

## 11. 未触碰

nginx / 数据库 / 桥（9097）/ Shittim（DLL 仍 `c013f442…`）/ 其它 PHP 文件 —— 全部未动。

## 12. 面板侧使用提示

- 登录面板 → 「道具/物品」页（`pages/items.php`）应看到新增的 **「发放全部记忆大厅」** 按钮与「每封邮件的包裹数」输入框（默认 60，范围 1–258）。
- 按钮需要**页面二次确认**；重复点击只会多发邮件（幂等语义：不会重复发同一封）。
- 想**一封发完**：把输入框填 **258**（实测 258 个包裹一封 = 200，13 KB 请求体）。
- `Type` 在实现里已按实测用字符串 `"MemoryLobby"`（`GM_MEMORY_LOBBY_TYPE_ID=8` 仅作数值常量/说明）。
