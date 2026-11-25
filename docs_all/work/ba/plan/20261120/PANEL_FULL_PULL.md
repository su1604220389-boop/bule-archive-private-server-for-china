# 综合管理站整站只读拉取（PANEL_20261120）

- 时间：2026-11-21 00:00–00:01（Asia/Shanghai）｜ 执行：srv-ops
- 性质：**单向只读下载**（服务器 → 本地），服务器侧**未执行任何写命令**
- 本地路径：`work\ba\srv_live\PANEL_20261120\ba_cardadmin\`

## 一句话结论

**整站已拉下：119 个文件 / 750,694 B（733.1 KB）**，与服务器逐文件 sha256 **119/119 完全一致**（0 缺失 / 0 多出 / 0 内容不一致）。
已按规则排除 `logs/`（3.8 MB）、`*.log`、`*.lock`、`*.pid`、`.git`。

---

## 1. 站点环境（只读查得）

| 项 | 实际值 |
|---|---|
| 站点根 | `/www/wwwroot/ba_cardadmin` |
| 站点总体积（含 logs） | 4.9 MB ｜ 原始文件数 124 / 目录 9 |
| **php-fpm** | **PHP 8.2.31 (NTS)**，服务 `php-fpm-82`（active） |
| **pool** | `php-fpm.conf` 里 `[global]` + **`[www]`**（`php-fpm.d/` 下只有 `www.conf.default`，无额外 pool） |
| **open_basedir** | **`/www/wwwroot/ba_cardadmin/:/tmp/:/www/wwwroot/ba_sdk/:/www/wwwroot/bapatch/`**（来自 `.user.ini`，`php.ini` 中为 0 处设置 → 纯靠 `.user.ini`） |
| `.user.ini` 属性 | `----i---------e-------`（**带 immutable 位**，改它必须先 `chattr -i`） |

## 2. 拉取结果：文件数 / 总大小 / 分组统计

| 一级目录 | 文件数 | 字节 |
|---|---|---|
| `(root)`（含 `.htaccess`、`.user.ini`、`config.php`、`README.md` 等） | 12 | 38,300 |
| `assets/` | 2 | 28,220 |
| `cron/` | 2 | 4,896 |
| `inc/` | 10 | 283,854 |
| `pages/` | 17 | 314,296 |
| `sql/` | 2 | 7,997 |
| `state/` | 74 | 73,131 |
| **合计** | **119** | **750,694（733.1 KB）** |

完整性核对（本地重算 vs 服务器 `sha256sum`，同一过滤规则）：
```
服务器清单条目 = 119
本地文件数     = 119
缺失（服务器有本地无）= 0
多出（本地有服务器无）= 0
内容不一致            = 0
```

清单文件：`work\ba\srv_live\PANEL_20261120\SHA256SUMS.txt`
（头部统计：`# 文件数 = 119  总字节 = 750694 (733.1 KB)`；行格式 `sha256  字节数  相对路径`）

## 3. 含敏感信息的文件（**只列文件名与字段名，无任何值**）

| 文件 | 敏感字段名 | 说明 |
|---|---|---|
| **`config.php`** | `DB_PASS`、`DB_USER`、`DB_NAME`、**`APP_SECRET`** | 数据库口令 + 应用密钥（**最高敏感**） |
| `config.php.example` | 同名字段（占位值） | 模板文件，非真实口令 |
| `inc/db.php` | `DB_PASS`、`DB_USER`、`DB_NAME` 的兜底 `define` | 若 config 未定义则用这里的空值 |
| `inc/ba.php` | `BA_ADMIN_KEY`（从 config → 回落 `settings` 表 `ba_admin_key`） | 调 Shittim `/api/admin/*` 的密钥来源 |
| `inc/auth.php` | 会话 `token`（Cookie 名 `SESSION_COOKIE`，32 字节 hex） | 管理站登录态 |
| `pages/settings.php` | `password` / `secret` / `api_key` 等表单字段名 | 设置页会写库（含 GM key） |
| `pages/admins.php` | `password`（管理员密码哈希） | 管理员账号管理 |
| `pages/gacha_rates.php` | `api_key`（读 `ba_admin_key`） | 概率页调后台接口 |
| `login.php` | `password`（校验入口） | 登录 |
| **`state/precsrf_*.json`**（74 个） | 预登录 CSRF 一次性 token | 运行期产生的临时票据（见 §5 说明） |

> **本报告不含任何口令/密钥明文**（`DB_PASS`、`APP_SECRET`、`BA_ADMIN_KEY` 均只写字段名）。
> 提醒：`config.php`（1,122 B）与 `state/precsrf_*.json` 属于敏感内容，交付包里要**控制分发范围**。

## 4. 被排除的内容（及原因）

| 排除项 | 实际内容 | 原因 |
|---|---|---|
| `logs/`（整目录） | `logs/sync.log`（**3.8 MB**）、`logs/.htaccess`、`logs/.gitkeep` | 运行时日志，体积大且含业务数据 |
| `*.log` | `logs/sync.log`（同上） | 运行时日志 |
| **`*.lock`** | `installed.lock`（293 B）、`state/sync.lock`（0 B） | 按你的规则排除；**⚠ 见 §5 提醒** |
| `*.pid` | **0 个**（站点内无 pid 文件） | — |
| `.git` | **不存在**（站点不是 git 仓库） | — |
| `sessions/`、`cache/`、`tmp/`、`uploads/` | **均不存在**（本站点把会话放 MySQL `sessions` 表、预登录票据放 `state/`） | 无需排除 |
| 上传临时目录 | 不存在（上传限制 `MAX_UPLOAD_BYTES=2 MB`，未见临时目录） | — |

**异常大文件检查**：`> 50 MB` = **0 个**；`> 5 MB` = **0 个**；最大单文件是 `pages/bans.php`（60,571 B）与 `inc/bans.php`（107,659 B）级别，均为源码。

## 5. 两个需要你决定的点（我只如实报告，未自行处理）

1. **`installed.lock`（293 B）被 `*.lock` 规则排除了。**
   它其实不是运行期锁，而是"**已安装**"标记（`inc/db.php` 用它判断 `CARDADMIN_INSTALLED`）。
   如果这份快照要**直接部署成可运行站点**，缺它会走"未安装"引导流程 → 需要的话我再单独拉这一个文件（只读）。
2. **`state/` 被完整包含了（74 个 `precsrf_*.json`，73 KB）。**
   它是运行期"预登录 CSRF 一次性票据"，不是源码。按要求 `state/` 不在排除名单内，所以我保留了；
   但如果你认为它属于"运行时/缓存"，我可以从本地快照里删掉（**只删本地副本，不碰服务器**）。

## 6. 拉取方式（供审计）

```powershell
# 单向：服务器 tar 流 → 本地文件（服务器侧无任何写操作）
ssh … "tar -czf - -C /www/wwwroot \
        --exclude=ba_cardadmin/logs --exclude=*.log --exclude=*.pid \
        --exclude=*.lock --exclude=.git ba_cardadmin" > %TEMP%\panel_pull_20261120.tgz
tar -xzf %TEMP%\panel_pull_20261120.tgz -C work\ba\srv_live\PANEL_20261120
```
- 服务器侧只执行：`find / du / ls / cat / sed（输出到管道，不写盘）/ tar -c（输出到 stdout）/ sha256sum`
- **没有** `mv` / `cp` 覆盖 / `sed -i` / `chmod` / `chown` / `rm` / `tee` / 任何写盘命令
- **没有** `systemctl restart|reload|stop|start`（只用了 `is-active` 查询）
- 未部署、未构建、未重启机器

## 7. 本地产物

```
work\ba\srv_live\PANEL_20261120\
├── SHA256SUMS.txt          （头部统计 + 119 行"sha256 字节数 相对路径"）
└── ba_cardadmin\           （整站 119 个文件，目录结构原样保留）
    ├── .htaccess  .user.ini  .user.ini.bak.1794777086
    ├── 404.html  config.php  config.php.example  index.html  index.php
    ├── login.php  logout.php  nginx.conf.example  README.md
    ├── assets\  (app.css, app.js)
    ├── cron\    (sync_cards.php, .htaccess)
    ├── inc\     (auth, ba, bans, db, gacha, gm_lobby, helpers, players, sync, .htaccess)
    ├── pages\   (17 个页面 php)
    ├── sql\     (2 个 sql)
    └── state\   (74 个 precsrf_*.json)
```
