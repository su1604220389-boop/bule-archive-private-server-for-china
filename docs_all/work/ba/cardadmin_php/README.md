# 卡密管理后台（PHP + MySQL，宝塔直接部署）

给 `sdkcard.py` 那套卡密服务用的 **Web 管理后台**。纯 PHP + MySQL，不依赖任何框架、不依赖 CDN，
放到宝塔里加个网站、指向本目录、建个 MySQL 库就能用。

- **唯一真源是 MySQL**：面板只写数据库，`cards.json` 由 cron 从数据库导出（原子替换）。
- 卡密变更**最多 60 秒生效**（cron 每分钟跑一次），面板里也能手动催一次。
- 兼容 **PHP 7.4 与 8.x**，只用自带扩展 `pdo_mysql / mbstring / json / openssl`。

---

## 目录

- [§0 目录结构与功能](#0-目录结构与功能)
- [§1 宝塔部署步骤](#1-宝塔部署步骤)
- [§2 cron 定时同步](#2-cron-定时同步)
- [§3 与 sdkcard.py 的对接（同步机制）](#3-与-sdkcardpy-的对接同步机制)
- [§4 安全建议](#4-安全建议)
- [§5 常见问题](#5-常见问题)
- [§6 数据库表与索引](#6-数据库表与索引)
- [§7 已知限制与风险](#7-已知限制与风险)

---

## §0 目录结构与功能

```
ba_cardadmin/                 ← 网站根目录（建议 /www/wwwroot/ba_cardadmin）
  index.php                   首页：未登录跳登录，已登录显示仪表盘
  login.php                   登录（失败 5 次锁 10 分钟）
  logout.php                  退出
  install.php                 ★ 安装向导（装完自锁，建议删除）
  config.php.example          配置模板（正常不用手工复制）
  config.php                  ← install.php 自动生成，含密码，勿泄露
  installed.lock              ← install.php 写下的安装锁
  .htaccess                   Apache 用（宝塔是 nginx，见 nginx.conf.example）
  nginx.conf.example          nginx 规则模板（手工粘贴到站点配置）
  .gitignore
  .htaccess / inc/ cron/ sql/ state/ logs/  → 这些目录都禁止 web 访问

  inc/
    db.php                    PDO 连接（单例）+ 常量 + 查询小工具
    helpers.php               转义、URL、布局、分页、设置、sdk.log 解析
    auth.php                  会话表登录、CSRF、审计日志、密码哈希
    sync.php                  ★ 同步引擎（MySQL → cards.json，原子替换 + flock）

  pages/
    dashboard.php             仪表盘（统计 / 最近 20 条登录 / 同步状态）
    cards.php                 卡密列表（分页 50·100·200、搜索、筛选、批量操作、编辑）
    cards_new.php             单个新建 + 批量生成（≤5000，一键复制/导出）
    cards_import.php          文本/文件批量导入（≤2 MB）
    cards_export.php          导出 txt / csv
    logs.php                  登录日志（只读解析 sdk.log 入库 + 筛选分页）
    admins.php                管理员（增删、改密、启停）
    audit.php                 审计日志
    settings.php              设置（同步、生成默认规则、路径、环境自检）

  assets/app.css, app.js      纯原生前端，离线可用，手机自适应

  cron/sync_cards.php         ★ 定时任务：MySQL → cards.json（只能 CLI 跑）
  sql/schema.sql              建表语句（install.php 逐条执行）
  logs/sync.log               cron 输出（运行期生成）
  state/                      同步锁、备份、同步请求标记（运行期生成）
```

功能一览：

| 模块 | 能力 |
|---|---|
| 安装 | 测试连接 → 建表 → 建管理员 → 生成 config.php → 自锁 |
| 登录 | 会话存库（32 字节随机 token，HttpOnly + SameSite=Strict），5 次失败锁 10 分钟 |
| 卡密 | 列表/搜索/按状态·期限·绑定筛选/排序/分页；单个新建；批量生成（≤5000）；导入；导出 txt/csv |
| 批量操作 | 删除 / 延期 N 天 / 永不过期 / 解绑设备 / 启用 / 禁用 |
| 单个操作 | 编辑（到期/绑定/状态/备注）、解绑、复制、删除、看该卡日志 |
| 展示 | 卡密默认脱敏 `abcd****wxyz`，点「显示明文」才明文；复制走 AJAX 取明文（不落 HTML 源码） |
| 日志 | 只读解析 `/root/bapatch/sdk.log`（容错、跳过计数、去重入库）+ 分页筛选 |
| 审计 | 所有写操作记一条（谁/何时/什么动作/影响多少条/IP） |
| 同步 | cron 每分钟导出；面板可「立即同步」；首次同步有安全拦截；设备绑定回灌 |

---

## §1 宝塔部署步骤

> 目标：`https://你的域名/` 或 `http://IP/` 打开就是登录页。
> 下面假设站目录用 `ba_cardadmin`（你可以改名，**cron 路径跟着改**）。

### 1.1 上传代码

把 `cardadmin_php/` **里面的内容**（不是这个目录本身）传到服务器：

```
/www/wwwroot/ba_cardadmin/
    index.php
    install.php
    inc/  pages/  assets/  cron/  sql/  ...
```

命令行方式（推荐，能保住权限）：

```bash
mkdir -p /www/wwwroot/ba_cardadmin
# 把压缩包里的内容解进去（解压后确认 index.php 直接在 ba_cardadmin 下）
cd /www/wwwroot/ba_cardadmin && unzip -o /tmp/cardadmin_php.zip
```

### 1.2 宝塔「添加网站」

1. 宝塔 → **网站** → **添加站点**
2. 域名：填你的域名；没有域名就填 `服务器IP:端口`（例如 `1.2.3.4:8080`）——但见 §4，建议只给自己 IP 开。
3. 根目录：`/www/wwwroot/ba_cardadmin`
4. PHP 版本：**7.4 或 8.1/8.2**（都支持）
5. 数据库：**MySQL**，一起创建（见下一步）。不用勾 PHP 项目/Node 项目。

### 1.3 创建 MySQL 库

宝塔 → **数据库** → **添加数据库**：

- 数据库名：`ba_cardadmin`
- 用户名：`ba_cardadmin`
- 密码：点「随机」，**复制保存好**（安装向导要填）
- 字符集：`utf8mb4`
- 访问权限：**本地服务器**

> 也可以先建站点时一起建。装的时候把库名/用户名/密码填进 install.php。

### 1.4 目录权限

```bash
chown -R www:www /www/wwwroot/ba_cardadmin
chmod -R 755 /www/wwwroot/ba_cardadmin
# 运行期需要写的两个目录
chmod 775 /www/wwwroot/ba_cardadmin/state /www/wwwroot/ba_cardadmin/logs
```

### 1.5 跑安装向导

浏览器打开：

```
http://你的域名或IP/install.php
```

按顺序：

1. **填数据库信息** → 点「测试连接」（只连库，不写任何东西，成功会显示 MySQL 版本）
2. 填**管理员用户名**（默认 `admin`，**建议改成别的**）+ **密码（≥12 位，前端有强度提示）**
3. 确认 `cards.json` 路径（默认 `/root/bapatch/cards.json`）与 `sdk.log` 路径（默认 `/root/bapatch/sdk.log`）
4. 勾选「把 cards.json 里已有的卡密导入数据库」（**强烈建议勾**，否则首次 cron 同步会被安全拦截）
5. 点「开始安装」

向导会：建 8 张表 → 建管理员 → 建表完成后自动生成 `config.php`（含随机 `APP_SECRET`，权限 0640）
→ 写 `installed.lock` 自锁。装完再访问 `install.php` 会被拒绝。

### 1.6 删除 install.php

装完页面上有「删除 install.php」按钮（PHP 用户没权限时会提示你手动删）。手动方式：

```bash
rm -f /www/wwwroot/ba_cardadmin/install.php
```

### 1.7 加 nginx 防护规则（**重要**）

宝塔的 nginx **不读 `.htaccess`**，所以要把 `nginx.conf.example` 里的 location 规则加到站点配置：

> 宝塔 → 网站 → 本站点 → **设置** → **配置文件** → 在 `server { ... }` 里粘贴
> `nginx.conf.example` 的第 1~5 段（敏感文件/内部目录/隐藏文件/autoindex）→ 保存。

自检（应全部 403/404，不能是 200）：

```bash
curl -I http://127.0.0.1/config.php
curl -I http://127.0.0.1/inc/db.php
curl -I http://127.0.0.1/cron/sync_cards.php
curl -I http://127.0.0.1/sql/schema.sql
```

> ⚠️ 只在**本站点的**配置文件里加规则，不要动 `/www/server/nginx/conf/nginx.conf` 全局配置，
> 也不要自己去 `nginx -s reload`（宝塔保存时会自动 reload）。

### 1.8 登录

打开 `http://你的域名/` → 用刚才的管理员账号登录 → 点开「仪表盘」看看同步状态。

---

## §2 cron 定时同步

**这一步不做，卡密改了也不会生效。** 面板的写操作只进 MySQL。

### 2.1 宝塔计划任务（推荐）

宝塔 → **计划任务** → 添加任务：

- 任务类型：**Shell 脚本**
- 任务名称：`卡密同步`
- 执行周期：**N 分钟** → **1 分钟**
- 脚本内容：

```bash
/usr/bin/php /www/wwwroot/ba_cardadmin/cron/sync_cards.php >> /www/wwwroot/ba_cardadmin/logs/sync.log 2>&1
```

> 宝塔的计划任务默认以 **root** 运行 —— 这是必须的，因为要写 `/root/bapatch/cards.json`。

### 2.2 crontab 方式

```bash
crontab -e
# 加一行：
* * * * * /usr/bin/php /www/wwwroot/ba_cardadmin/cron/sync_cards.php >> /www/wwwroot/ba_cardadmin/logs/sync.log 2>&1
```

### 2.3 手工验证

```bash
# 1) 只看会导出什么，不写文件
/usr/bin/php /www/wwwroot/ba_cardadmin/cron/sync_cards.php --dry-run

# 2) 真跑一次
/usr/bin/php /www/wwwroot/ba_cardadmin/cron/sync_cards.php

# 3) 看结果
tail -n 20 /www/wwwroot/ba_cardadmin/logs/sync.log
ls -l --time-style=full-iso /root/bapatch/cards.json
```

参数：

| 参数 | 作用 |
|---|---|
| `--dry-run` / `-n` | 只计算，不写文件（安全演练） |
| `--force` / `-f` | 首次同步时也允许丢弃"数据库里没有"的旧卡（以数据库为准） |
| `--import-orphans` | 先把 cards.json 里库里没有的卡密导入数据库，再同步 |
| `--quiet` / `-q` | 少输出 |
| `--help` / `-h` | 用法 |

> 脚本**故意没有 shebang**（`#!/usr/bin/env php`），因为 shebang 在 web 访问时会被当成输出，
> 导致 header() 失效、状态码错成 200。所以请一律用 `php 路径/sync_cards.php` 调用（上面的 cron 就是）。
> 想直接 `./sync_cards.php` 跑，自己 `chmod +x` 并加回 shebang，同时确认 nginx 规则已挡住 `/cron/`。

---

## §3 与 sdkcard.py 的对接（同步机制）

### 3.1 为什么不让面板直接写 cards.json

1. `php-fpm` 是 `www` 用户，**没有** `/root/bapatch/` 的写权限；
2. `sdkcard.py` **每次请求都重新 `json.load(open(CARDS))`**（见其 23-26 行 `load_cards()`），
   如果面板直接 `json.dump`，客户端有概率读到**写了一半的 JSON** → 全服登录炸；
3. 多进程/定时任务并发写会直接撕坏文件。

所以链路固定为：

```
        ┌──────────────┐   cron 每分钟（root）    ┌────────────────────┐
写操作 →│   MySQL      │ ───────────────────────→│ /root/bapatch/     │← 每次请求重新读
（面板）│  （唯一真源） │  cron/sync_cards.php     │    cards.json      │   sdkcard.py
        └──────────────┘  原子替换 + flock        └────────────────────┘
```

### 3.2 目标文件结构（必须和 sdkcard.py 一致）

```json
{
  "cards": {
    "11111111111": {
      "devices": ["09a4d0ab0ee93616"],
      "expire": 0,
      "bind_one": true
    }
  }
}
```

- `expire`：unix 时间戳，`0` = 永不过期
- `devices`：该卡已绑定的设备 ID 列表（`sdkcard.py` 用它判定"是否已绑定其他设备"）
- `bind_one`：`true` = 只允许一台设备

### 3.3 原子替换怎么做的（`inc/sync.php`）

1. 取 `flock(LOCK_EX | LOCK_NB)` 排他锁（`state/sync.lock`，权限 0666 让 root/www 都能开；
   拿不到锁就直接退出，不会两个进程同时写）。
2. 先读**现有** `cards.json`，把里面**新出现、数据库没有的设备**合并回 `card_devices`
   （见 3.4，这一步防丢绑定）。
3. 组装新 JSON，写入**同目录**临时文件 `cards.json.tmp.<pid>.<rand>`，`fflush` 后 `chmod 0644`。
4. `rename()` **原子替换**（同目录同文件系统，POSIX 保证读者要么看到旧文件要么看到新文件，
   永远不会看到半个文件）。
5. **回读校验**：重新 `json_decode` 落盘文件，失败则用 `state/cards.backup.json` 回滚。
6. 更新 `settings.last_sync_at`，写 `logs/sync.log`。

### 3.4 设备绑定不会被"同步一次就冲掉"

`sdkcard.py` 自己在 `/user/login` 里发现新设备时会**直接写 `cards.json`**（它的 `save_cards()`，
非原子，属于历史行为）。这些设备数据库并不知道。如果同步时直接覆盖，用户刚绑的设备就没了。

所以每次同步**先把 `cards.json` 里的设备补进 MySQL**（`INSERT IGNORE card_devices`），再导出。
效果：两种来源的设备并集，谁都不丢。

### 3.5 过期 / 禁用的处理

| 数据库状态 | 导出到 cards.json | 客户端表现 |
|---|---|---|
| `active` 且未过期 | `expire` = 真实时间戳 | 正常进游戏 |
| `active` 但已过期 | `expire` = **过去的时间戳**（照样导出） | `卡密已过期`（400101） |
| `disabled` | **不导出** | `卡密不正确`（400101） |
| 已删除 | 不导出 | `卡密不正确` |

> 过期卡选择"导出但 expire 设为过去"，而不是"干脆不导出"：这样 `sdkcard.py` 会走到它自己的
> 过期分支，给用户的提示更准确（`卡密已过期` 而不是 `卡密不正确`）。

### 3.6 首次同步保护

`cards.json` 里可能存在数据库完全不知道的卡密（历史手工加的）。首次同步如果直接以数据库为准，
会把它们**全部删掉**。所以：

- 首次同步（`settings.last_sync_at` 为空）时，如果发现"孤儿卡密"，**直接拒绝覆盖**，
  并在日志里报数。
- 处理方式二选一：
  - 面板 →「系统设置」→「从 cards.json 导入」→ 孤儿卡密进库，然后再同步；
  - 或确认可以丢弃：`php cron/sync_cards.php --force`。

### 3.7 手动同步（不到 60 秒也能生效）

面板上的「立即同步」按钮有两种走法，代码自动判断：

| 当前 PHP 用户能否写 cards.json 目录 | 行为 |
|---|---|
| 能（例如 www 对目录有写权限） | **当场同步**，立刻生效 |
| 不能（宝塔默认情况） | 在 `state/sync.request` 写一个请求标记，cron 下次运行（≤60 秒）时优先执行，并记一条审计 |

> 想让面板直接同步也可以：`chown -R www:www /root/bapatch`（**不建议**，会削弱权限隔离）。
> 更稳的做法是把 cron 周期设成 1 分钟，或加一个每 10 秒跑一次的 cron（注意别把 sync.log 刷爆）。

---

## §4 安全建议

这个后台会**暴露在公网**，请至少做完下面几条：

1. **安全组/防火墙只放行必要端口**（80/443；连面板自己都只给自己 IP 开更好）。
2. **只放行你自己的 IP**（最有效的一条）：
   - 宝塔 → 网站 → 设置 → **访问限制**（或 nginx 站点配置里加）
     ```nginx
     allow 你的办公IP;
     allow 你的家庭IP;
     deny all;
     ```
   - 备选：宝塔 → 安全 → 防火墙 → 端口规则只对指定 IP 开放。
3. **改掉默认管理员名**：不要用 `admin`；密码 ≥12 位，别和别处复用。
   （`pages/admins.php` 里可以新增/删除管理员、改密码；系统不阻止你在知道密码的情况下改用户名——
   最简单是新建一个管理员、确认能登录、再删掉 `admin`。）
4. **给面板上 SSL**：宝塔 → 网站 → SSL → Let's Encrypt，然后强制 HTTPS。
   否则密码/IP 在明文里过公网。
5. **别把 `config.php` 交出去**：它含数据库密码。已在 `.gitignore` 里忽略；也不要贴到聊天/工单/截图中。
6. **别把 `cards.json` 目录放开权限**：`chmod 777 /root/bapatch` 会让任何本地用户替全服发卡。
   保持只让 root 写。
7. **定期看审计日志**：`pages/audit.php` 里能看到谁在什么时候改了哪些卡。
8. **限制导出**：导出会返回明文卡密，只给你信任的账号开后台。
9. **装完删 `install.php`**（自锁已经挡住，但删掉更干净）。
10. **确认 nginx 规则生效**（§1.7 的 4 条 curl 自检）。

---

## §5 常见问题

**Q1. 打开就是 500 / 白屏？**
看宝塔 → 网站 → 本站点 → **日志** 里的 PHP 错误日志；常见原因：
`config.php` 里的库信息错（这时访问会提示"数据库连接失败"）、`state/` `logs/` 不可写、
PHP 版本 < 7.4、缺 `pdo_mysql`（宝塔 → 软件商店 → PHP 设置 → 安装扩展）。

**Q2. 面板里改了卡密，客户端没反应？**
90% 是 cron 没跑或跑失败：
```bash
tail -50 /www/wwwroot/ba_cardadmin/logs/sync.log
/usr/bin/php /www/wwwroot/ba_cardadmin/cron/sync_cards.php   # 手工跑看报错
ls -l --time-style=full-iso /root/bapatch/cards.json          # mtime 有没有更新
```
另外确认 cron 用的是**同一个 PHP 版本**（宝塔计划任务里可指定，或者写死 `/www/server/php/74/bin/php`）。

**Q3. 点「立即同步」提示没有权限？**
正常现象。web 用户通常没有 `/root/bapatch` 的写权限，按钮会改成"写同步标记"，由 root 的 cron 执行
（≤60 秒）。想让按钮直接生效，见 §3.7。

**Q4. 登录提示"次数过多已锁定"？**
同一 IP 失败 5 次锁 10 分钟。急着进可以清表：
```sql
DELETE FROM login_attempts WHERE ip = '你的IP';
```

**Q5. 装完了，还能再访问 install.php 吗？**
不能，`installed.lock` 会拦住。要重装：删掉 `installed.lock` 与 `config.php`（**数据表不会自动删**，
要重来请先手动清库），再访问 install.php。

**Q6. 时间/统计不对？**
后台用 `APP_TIMEZONE`（默认 `Asia/Shanghai`）。`sdk.log` 只有 `HH:MM:SS` 没有日期，
导入时用**日志文件最后修改时间**做日期锚点；跨天重新解析历史行时可能补进少量重复（已知限制）。

**Q7. 导入说"没有解析到有效卡密"？**
一行一个卡密；不能含空格、逗号、引号、反斜杠；长度 ≤64；只有可见 ASCII。
上传的 txt/csv 会先去 BOM，CSV 只取第一列。

**Q8. CSV 用 Excel 打开乱码？**
导出文件已带 UTF-8 BOM，直接双击打开即可；若用 WPS 旧版仍乱，选"数据 → 从文本导入 → UTF-8"。

**Q9. 卡密显示成 `abcd****wxyz` 是什么？**
默认脱敏。点右上「显示明文」看全部；单条要复制点行尾「复制」（会走一个需要登录的接口取明文）。

**Q10. 数据库连不上，报 2054 / caching_sha2_password？**
MySQL 8 默认认证插件较新。两个办法：宝塔里把该用户改成 `mysql_native_password`，
或直接把 PHP 升到 8.1+（其 mysqlnd 支持 caching_sha2）。

**Q11. 解绑了设备，为什么客户端还能进？**
解绑后要等 cron 同步（≤60 秒）。点「立即同步」催一下。另外：如果客户端还持有旧的 token，
`/user/detail`、`/heartbeat/pulse` 这些接口不校验设备（这是 `sdkcard.py` 现有逻辑），
真正拦得住的是 `/user/login` 和 `/user/quick-login`。

**Q12. 卡密很多（几万张）会不会慢？**
面板分页查询没问题。但 `cards.json` 是 `sdkcard.py` **每次请求都 `json.load`** 的，
文件越大每次请求越慢。实测建议：**5 万张以内**。再多就考虑分库/给 `sdkcard.py` 加缓存
（那属于改 `sdkcard.py`，本次没动它）。

**Q13. 会不会把现有服务搞坏？**
明确没碰的：`sdkcard.py`、`account_auth_probe.py`、现有 nginx 配置、现有数据库、宝塔防火墙/WAF。
只新增了：本站目录 + 一个新库。同步写 `cards.json` 用了 flock + 临时文件 + rename，
即使同步进程被 kill，`sdkcard.py` 读到的仍是完整的旧文件或完整的新文件。
**唯一的竞态**在 `sdkcard.py` 自己写 `cards.json` 的那一瞬间（它不原子，属历史行为，本次未改），
同步侧已经用"设备回灌"把数据损失降到"极小概率丢一次绑定"，见 §3.4/§7。

---

## §6 数据库表与索引

8 张表（`sql/schema.sql`，InnoDB / utf8mb4）：

| 表 | 作用 | 关键索引 |
|---|---|---|
| `admins` | 管理员 | `UNIQUE(username)` |
| `sessions` | 登录会话（自定义 token） | `PK(token)`、`(admin_id)`、`(expires_at)` |
| `cards` | 卡密主表 | `UNIQUE(card_key)`、`(status)`、`(expire_at)`、`(created_at)`、`(last_login_at)` |
| `card_devices` | 卡密-设备绑定（一对多） | `UNIQUE(card_id, device_id)`、`(device_id)`、FK→cards ON DELETE CASCADE |
| `login_logs` | 登录日志（sdk.log 解析 + 平台记录） | `UNIQUE(line_hash)`、`(ts)`、`(card_key)`、`(device_id)` |
| `audit_logs` | 审计日志 | `(ts)`、`(admin_id)`、`(action)` |
| `settings` | 设置 k-v | `PK(k)` |
| `login_attempts` | 登录失败/锁定计数 | `(ip, ts)`、`(username, ts)` |

`schema.sql` 全部 `CREATE TABLE IF NOT EXISTS`，重复执行不丢数据。

---

## §7 已知限制与风险

1. **生效延迟**：面板改完最长 60 秒才进 `cards.json`。要更快就调 cron 频率或用「立即同步」。
2. **没有权限分级**：任何管理员都能管理其他管理员。建议只留一个账号。
3. **`sdkcard.py` 自身的写不是原子的**：它在绑定新设备时 `json.dump(open(CARDS,'w'))`，
   如果恰好在同步的 rename 前后发生，可能丢一次绑定/写入旧内容。本平台不改它（按约定一个字节不动），
   已用"设备回灌 + flock + 原子替换"把影响压到最小。要彻底消除，需改 `sdkcard.py` 为
   "先读 MySQL 或先写临时文件再 rename"——属于另一个任务。
4. **`sdk.log` 无日期**：跨天重复解析可能补进少量重复记录（已按 `(ts|来源|原始行)` 做 hash 去重）。
5. **手动同步依赖 cron**：web 用户通常写不了 `/root/bapatch`。
6. **`cards.json` 体积**：卡越多，`sdkcard.py` 每次请求越慢（见 Q12）。
7. **`logs/sync.log` 会增长**：cron 启动时超过 5 MB 会自动截到后 200 KB。
8. **`login_logs` 会增长**：登录日志页有「清理 N 天前」按钮。

---

## 附：本地自检记录

本机**没有 MySQL 服务**，所以不是"真库跑一遍"，而是「静态检查 + 契约测试 + HTTP 冒烟」：

| 检查项 | 方法 | 结果 |
|---|---|---|
| PHP 语法 | `php -l`（PHP 7.4.33 与 8.3.36 各跑一遍），18 个文件 | **0 错误** |
| 纯函数单测 | 自写断言（sdk.log 解析含真实日志/垃圾行容错、脱敏、卡密生成、原子写、分页、URL、无库降级） | **60 条全通过** |
| SQL × schema 一致性 | 扫出 96 条 SQL、12 条 INSERT，逐条核对表名/字段名/值个数 | **全部匹配** |
| 函数调用检查 | 105 个自定义函数 × 1021 个 PHP 内置函数 | **无未定义调用** |
| 前端 | `node --check app.js`、CSS 括号平衡 | 通过 |
| HTTP 冒烟 | PHP 内置服务器：install 页渲染、未登录 302、`inc/` 与 `cron/` 返回 403、CSRF 错误返回 419、弱密码拦截、连不上库时给友好错误 | 通过 |
| 与 `sdkcard.py` 的 JSON 契约 | 用 `sdkcard.py` 的原逻辑（第 23-30、93-129 行）消费我们导出的 `cards.json`：绑定限制、过期提示、quick-login、多设备、sdkcard 自己写回设备 | **12 条全通过** |

**没做到的**：真实 MySQL 上的端到端（建库 → 安装 → 增删改 → cron 同步）。部署后请按下面
「部署后 5 分钟自检」走一遍。

### 部署后 5 分钟自检

```bash
# 1) 面板能登录（浏览器）→ 仪表盘能看到 0 张卡
# 2) 建 2 张测试卡：一张永久、一张已过期（「新建卡密」页「有效期(天)」填 0 和 -1 不行，
#    请用「具体到期时间」选一个过去时间）
# 3) 先演练同步，不写文件
/usr/bin/php /www/wwwroot/ba_cardadmin/cron/sync_cards.php --dry-run

# 4) 真同步
/usr/bin/php /www/wwwroot/ba_cardadmin/cron/sync_cards.php

# 5) 核对文件：应只含 active 卡，过期卡 expire 是过去时间
cat /root/bapatch/cards.json

# 6) 用客户端试一张卡：能登进去；把该卡在面板里禁用 -> 等 1 分钟 -> 再登应提示"卡密不正确"
# 7) 面板「登录日志」点「解析 sdk.log 入库」，能看到刚才的登录记录
```

---

## 附：交付清单（文件与行数）

合计 **31 个文件 / 6463 行**，其中 PHP **18 个文件 / 5222 行**。

| 文件 | 行数 | 作用 |
|---|---|---|
| `install.php` | 627 | 安装向导（自锁） |
| `index.php` | 14 | 首页/仪表盘入口 |
| `login.php` | 117 | 登录（5 次锁 10 分钟） |
| `logout.php` | 9 | 退出 |
| `inc/db.php` | 151 | PDO + 常量 |
| `inc/helpers.php` | 772 | 工具/布局/设置/sdk.log 解析 |
| `inc/auth.php` | 395 | 会话/CSRF/审计/密码 |
| `inc/sync.php` | 594 | 同步引擎（原子写 + flock） |
| `pages/dashboard.php` | 187 | 仪表盘 |
| `pages/cards.php` | 543 | 卡密列表/批量/编辑 |
| `pages/cards_new.php` | 330 | 新建 + 批量生成 |
| `pages/cards_import.php` | 246 | 批量导入 |
| `pages/cards_export.php` | 167 | 导出 txt/csv |
| `pages/logs.php` | 324 | 登录日志 |
| `pages/admins.php` | 254 | 管理员 |
| `pages/audit.php` | 124 | 审计 |
| `pages/settings.php` | 256 | 设置 |
| `cron/sync_cards.php` | 112 | 定时同步（仅 CLI） |
| `sql/schema.sql` | 122 | 建表（8 表） |
| `assets/app.css` / `app.js` | 298 / 295 | 前端（无 CDN、离线可用） |
| `.htaccess` ×6 + `nginx.conf.example` | 56 + 40 + 51 | 访问控制 |
| `config.php.example` / `.gitignore` / `README.md` | 47 / 18 / 本文件 | 模板与说明 |


