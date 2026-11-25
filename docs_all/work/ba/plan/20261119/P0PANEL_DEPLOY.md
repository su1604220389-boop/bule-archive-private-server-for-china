# P0 管理站「抽卡概率」页面部署（P0PANEL）

- 时间：2026-11-19 03:00（Asia/Shanghai）｜ 执行：srv-ops
- 站点根：`/www/wwwroot/ba_cardadmin`
- **最终判定：部署成功 · 全部验证通过 · KEEP（保留）**

## 1. 三份文件（sha256 实测与要求逐项一致）

| 相对路径 | 类型 | 字节 | sha256 | 实测 |
|---|---|---|---|---|
| `inc/gacha.php` | **新增** | 17,073 | `1152ff4c5f16372f7cec78a3b458d45dd0e4ed2781b4f396d6634d2f1e3a4e94` | ✅ |
| `pages/gacha_rates.php` | **新增** | 24,050 | `105f151cd539322f26ffaa54d32a250c084b82d99536516249f3318d36e1bfdd` | ✅ |
| `inc/helpers.php` | **修改**（+1 行导航） | 29,131（改前 29,059） | `0bd35a74fed7c932bf232f1fb0bf49efd738448e6bd122c1c9830539a4d4a371` | ✅ |

改前 `inc/helpers.php` 基线：`4440c2c9845e0a97c411cbbc5a564fa97b025eea935b855235ebc05e7ba6c87e` / 29,059 B / `root:root 644`
两个新增文件在部署前**确认不存在**（`ls` 报 No such file）。

## 2. 备份与回滚

```
备份目录：/root/P0PANEL_20261119_030005/
   helpers.php      （改前 4440c2c9… / 29,059 B / root:root 644）
   BEFORE.txt       （sha256 + 字节数 + 属主权限）
   ROLLBACK.sh
```

**ROLLBACK.sh 完整路径：**
```
/root/P0PANEL_20261119_030005/ROLLBACK.sh
```
逻辑：还原 `inc/helpers.php` → 删除 `inc/gacha.php` 与 `pages/gacha_rates.php` → `systemctl reload php-fpm-82`
→ 打印恢复后 sha256 → 打一次 `gacha_rates.php` 状态码。
（另有全量备份 `/root/PRE_P0_20261119_023546/panel_ba_cardadmin.tgz` 可整站恢复。）

## 3. 语法检查（服务器上实测，替换前后各一次）

**替换前（对上传件）**
```
No syntax errors detected in /tmp/p0_gacha_inc.php
No syntax errors detected in /tmp/p0_gacha_page.php
No syntax errors detected in /tmp/p0_helpers.php
```
**替换后（对线上三份）**
```
No syntax errors detected in /www/wwwroot/ba_cardadmin/inc/gacha.php
No syntax errors detected in /www/wwwroot/ba_cardadmin/pages/gacha_rates.php
No syntax errors detected in /www/wwwroot/ba_cardadmin/inc/helpers.php
```

## 4. opcache

```
$ /www/server/php/82/bin/php -i | grep -i 'opcache.validate_timestamps'
（无输出 —— 该 PHP 未启用/未加载 opcache 扩展）
⇒ 不存在 "validate_timestamps=0 导致改文件不生效" 的风险
```
仍按要求执行了 `systemctl reload php-fpm-82` → **active**（确保 opcache（若有）与 `include` 缓存刷新）。

## 5. 未登录访问（关键验证）

```
8081 /pages/gacha_rates.php -> **302**  redirect=http://127.0.0.1:8081/login.php?next=%2Fpages%2Fgacha_rates.php
80   /pages/gacha_rates.php -> 404   （80 端口不是面板站点，符合预期）
8081 /index.php             -> 302  redirect=.../login.php?next=%2Findex.php
8081 /pages/cards.php       -> 302
⇒ **302 到登录页，没有 500、没有白屏** ✅
```

## 6. 文件权限 / 属主

```
inc/ 目录（对照）
  -rw-r--r-- 1 www  www   19244 auth.php
  -rw-r--r-- 1 www  www   17073 gacha.php        ← 新增
  -rw-r--r-- 1 www  www   29131 helpers.php      ← 覆盖（改前 root:root，现统一为 www:www 644）
  -rw-r--r-- 1 root root 107659 bans.php
  -rw-r--r-- 1 root root 26083 players.php
pages/
  -rw-r--r-- 1 www  www   24050 gacha_rates.php  ← 新增
```
说明：`inc/` 下多数文件为 `www:www 644`，本次三份统一为 **`www:www 644`**；
`helpers.php` 改前是 `root:root`（历史遗留），现在与多数文件一致（**只读使用，属主变化不影响功能**）。

## 7. 导航行原文（`inc/helpers.php`）

```php
875:        'gacha'      => array('抽卡概率', 'pages/gacha_rates.php'),
```
（`grep -c gacha_rates inc/helpers.php` = 1，且实测 `require helpers.php` 正常、`nav count=1`。）

## 8. 错误日志

```
php-fpm 日志：最近 20 行里 **无 error/fatal**（只有 reload NOTICE）
站点根：无 error_log 文件
/www/wwwlogs/php_82_error.log 最近 5 行：**全是 11-18 的历史行**（03:21 open_basedir 警告、21:51/21:55 我早前探测脚本的 db_installed 重声明）
⇒ **本次部署没有产生任何新的 PHP 错误**
```

## 9. 顺带清理（测试残留）

**删除前（`ls -l`）**
```
-rw-r--r-- 1 root root 399 Nov 19 02:47 /www/wwwroot/ba_srv/Data/gacha_rates.backup.20261119_024700_114.json
-rw-r--r-- 1 root root 399 Nov 19 02:47 /www/wwwroot/ba_srv/Data/gacha_rates.backup.20261119_024711_231.json
```
**删除后（Data/ 目录）**
```
drwx------ 2 root root  4096 Excel
-rw-r--r-- 1 root root   312 Nov 19 02:46 gacha_rates.defaults.json     ← 正式文件，保留
-rw-r--r-- 1 root root 40739 Nov 18 22:24 GachaRecruitBanners.cn.json
drwx------ 2 root root  4096 Koyuki
drwx------ 2 root root  4096 ProhibitedWord
gacha_rates.json 是否存在 = no ｜ backup 残留数 = 0
```

## 10. 未触碰

nginx 配置 / 数据库 / 桥（9097）/ Shittim（DLL 仍 `c013f442…`）/ `Data/` 其它文件 —— 全部未动。

## 11. 后续人工验证建议

登录面板（`http://<SERVER_IP>:8081/`）→ 左侧应出现 **「抽卡概率」** 菜单 →
页面应显示 Normal/Pickup/Limited/Fes 四组当前值，且与 `GET /api/admin/gacha/rates` 一致
（Normal 30/185；Pickup 7/23/185；Limited 7/23/185；Fes 7/9/44/185），并带保存/重置按钮。
