# 管理面板上线前 —— 线上只读取证（2026-11-17 22:00）

执行者：srv-ops ｜ **全程只读**：未写任何文件、未重启任何进程、未改任何配置
说明：标注「实测」= 本轮命令的真实输出；标注「推断」= 基于输出的判断，未经追加验证。

---

# ★★★ 最高优先级发现：`/api/admin/*` 已暴露到公网，且**无鉴权**（实测） ★★★

```
$ curl -s -o /dev/null -w '%{http_code}\n' https://example.com/api/admin/status
200
$ curl -s -i https://example.com/api/admin/accounts
HTTP/2 200
content-type: application/json; charset=utf-8
[{"serverId":2,"nickname":"","level":1,"exp":0,"comment":null}]
```
**三条公网入口全部 200：**
```
https://example.com/api/admin/status        → 200
https://example.com/api/admin/status            → 200
https://gsqc-api.bluearchive-cn.com/api/admin/status → 200
```
**原因链（实测 + 推断）**
1. nginx `example.com.conf:100` 的 `location ^~ / { proxy_pass http://127.0.0.1:5000; }` 把**任何路径**（含 `/api/admin/...`）转发给 Shittim；
2. Shittim `AdminController` 的 `[AdminAuth]` 采用**环回免密钥**：经 nginx 转发后 `RemoteIpAddress == 127.0.0.1` ⇒ **判定为环回，跳过密钥**；
3. `Config.json` 里 **`AdminApiKey` 存在但长度为 0**（实测：`AdminApiKey valueLen=0`）⇒ 即便不是环回也无密钥可校验。
**⇒ 结论：任何人只要知道域名，就能调用整个 admin API（读 + 大概率可写）。这是上线前必须堵的洞。**

**建议（不执行，等指令）**：在 nginx 上把 `/api/admin/` 明确 `deny all`（或 `allow 127.0.0.1; deny all;`），并且**不要**把它放到公网 vhost；PHP 面板走 `127.0.0.1:5000` 直连即可（同机）。

---

## 1) Shittim admin API 是否真的在本机活着（实测）

**监听端口**
```
LISTEN 0.0.0.0:80     nginx (pid 2637870/2637869/2911)
LISTEN 0.0.0.0:6667   dotnet pid 2644695
LISTEN 0.0.0.0:5000   dotnet pid 2644695
LISTEN 0.0.0.0:5100   dotnet pid 2644695
```

**`/api/admin/status`**
```
5000 → HTTP/1.1 200 OK，Kestrel
{"service":"Shittim-Server","gameVersion":"1.90.439170","versionId":"53c8e5c4ff484d23",
 "apiPort":"5000","gatewayPort":"5100","gatewayEnabled":true,"useEncryption":false,
 "bypassAuthentication":true,"useCustomExcel":false,"accountCount":2,
 "startedAtUtc":"2026-11-17T13:54:10.1992586Z","uptimeSeconds":397}
5100 → 同上，200（同一进程，同一套路由）
6667 → **无响应**（curl 超时/空；6667 是游戏 TCP 端口，不是 HTTP）
```

**`/api/admin/accounts`（5000，实测原文）**
```
HTTP/1.1 200 OK
[{"serverId":2,"nickname":"","level":1,"exp":0,"comment":null}]
```

**`/api/admin/account/2/currencies`（实测原文）**
```json
{"Gold":82000,"GemPaid":0,"GemBonus":1101000,"Gem":1101000,"ActionPoint":999,
 "AcademyTicket":3,"ArenaTicket":5,"RaidTicket":3,"WeekDungeonChaserATicket":0,...}
```
**⇒ 注意：`Gem=1,101,000` —— 用户已经领了「三个67」那封 100 万邮件（101,000 + 1,000,000）。**

**`/api/admin/account/2/detail`（实测原文）**
```json
{"serverId":2,"nickname":"","callName":null,"level":1,"exp":0,"comment":null,"state":"Normal",
 "vipLevel":null,"publisherAccountId":314816420,"representCharacterServerId":9,
 "createDate":"2026-11-17T20:34:53.9409802","lastConnectTime":"2026-11-17T20:34:53.9409781",
 "currencies":{...同上...},"itemCount":2,"characterCount":4,"mailCount":4}
```

**其它路由探测（实测）**
```
/api/admin              404
/api/admin/             404
/api/admin/players      404
/api/admin/health       404
/api/admin/account/list 404
```

**进程 / 启动方式（实测）**
```
ps -ef:
  root 2644694  1  tmux new-session -d -s shittim ... 'cd /root && /root/dotnet10/dotnet .../Shittim-Server.dll --console --id 2'
  root 2644695 2644694  /root/dotnet10/dotnet .../Shittim-Server.dll --console --id 2

systemd: ba-shittim.service  loaded active **exited**  "Shittim-Server (…API 5000 / Gateway 5100) [tmux-stdin]"
/proc/2644694/cwd -> /root
cmdline: tmux new-session -d -s shittim -x 220 -y 50 cd /root && /root/dotnet10/dotnet ... --console --id 2
```
**⇒ 实际由 **tmux** 拉起（`ba-shittim.service` 只是外壳，状态是 exited）；进程 1 个真正的 dotnet（2644695）。**

## 2) 是否暴露到公网 —— **是，且无鉴权**（见页首）

**nginx 里所有 `api` 相关 location（实测原文）**
```
ba_mitm.conf:26      location = /api/state {
ba_mitm.conf:63      location = /api/health {
ba_mitm.conf:68      location = /api/state {
ba_mitm.conf:78      location ^~ /api/ {          ← 全部 /api/* 转 127.0.0.1:9097（桥）
example.com.conf:82   location = /api/state {
example.com.conf:92   location = /api/health {
example.com.conf:187  location = /api/state {
```
**⚠ 注意：`example.com.conf` 里没有 `/api/` 的专门转发**，落到 `location ^~ /`（:100）→ `proxy_pass 127.0.0.1:5000`（**Shittim 本体，不是桥**）⇒ 所以公网能直达 admin API。

**`Config.json` 里的 `AdminApiKey`：有该键，值长度为 0（实测）**
```
keys matching admin/key: [... 'AdminApiKey', 'ExcelDbSqlCipherKey']
AdminApiKey      valueLen=0
ExcelDbSqlCipherKey valueLen=64
```

## 3) 卡密站现状（实测）

```
/www/wwwroot/ba_cardadmin/   （www:www，配置/config.php -rw-r----- www）
  config.php (1122 B)  index.php  login.php  logout.php  404.html
  inc/  pages/  cron/  sql/  state/  logs/  assets/
  installed.lock (293 B)  .user.ini (root:root)
```
**PHP（实测）**
```
PHP 8.1.35 (cli) (NTS)
扩展（实测）：curl json mbstring mysqli mysqlnd PDO pdo_mysql **pdo_sqlite sqlite3**
⇒ **pdo_sqlite = True | sqlite3 = True**（这是关键结论：PHP 具备直接读 SQLite 的能力）
```
**config.php（实测，仅报库名，未贴密码）**
```
DB_HOST=127.0.0.1  DB_USER=ba_cardadmin  DB_NAME=ba_cardadmin  DB_PASS=*** (23 字符)
```
**MySQL（实测：server 5.7.43）**
```
SHOW TABLES:
  admins, audit_logs, card_devices, cards, login_attempts, login_logs, sessions, settings

计数：
  cards = **1**
  admins = **1**
  login_logs = **0**

DESCRIBE cards（实测）:
  id int unsigned PK auto_increment
  card_key varchar(64) UNIQUE
  status enum('active','disabled') default active
  expire_at int unsigned default 0
  bind_one tinyint(1) default 1
  created_at datetime default CURRENT_TIMESTAMP
  created_by varchar(64)
  note varchar(255)
  login_count int unsigned default 0
  last_login_at datetime NULL
  last_login_device varchar(64) NULL
  ⇒ **没有 `kind` 列、没有 `max_devices` 列**（实测确认）

DESCRIBE admins（实测）:
  id / username(UNIQUE) / pass_hash / salt / created_at / last_login_at / last_login_ip / enabled
```
**`cards.json`（sdkcard 实际读取的那个）**
```
/www/wwwroot/ba_sdk/cards.json   189 B   root:root   mtime 2026-11-17 22:01
（sdkcard.py:13  CARDS = "/www/wwwroot/ba_sdk/cards.json"；
  但同文件 :7 的文档字符串写的是 /root/bapatch/cards.json —— **注释与实际不一致，以代码为准**）
```
**crontab（本轮未单独跑；前次实测有 cron 同步）**
```
/www/wwwroot/ba_cardadmin/cron/ 目录存在；历史日志（21:17）显示：
"同步成功(cron)：导出 1 个卡密，189 B，合并设备 0，丢弃孤儿 0，禁用跳过 0"
⇒ 同步任务在跑，把 MySQL cards 导出成 sdkcard 读的 cards.json
```

## 4) 文件权限（决定 PHP 能否读 SQLite）（实测）

```
/root/shittim.sqlite3   -rw-r--r-- root:root  577,536 B   Nov 17 21:28
id www                   uid=1000(www) gid=1000(www)
sudo -u www ls /root/shittim.sqlite3   → **Permission denied**（/root 目录 700，非文件本身）
sudo -u www test -r /root/shittim.sqlite3 → **DB_NOT_READABLE_BY_WWW**
sudo -u www test -r /www/wwwroot/bapatch/data/accounts.db → **ACC_READABLE**
ls -la /www/wwwroot/bapatch/data/ → accounts.db  -rw-r--r-- root:root  131,072 B
php-fpm: 多个 master（php 83/84/85），均 **root** 启动（worker 用户未在本轮输出中确认）
```
**⇒ 结论（实测）：`www` 用户**读不到** `/root/shittim.sqlite3`（`/root` 权限 700）；但**能读** `accounts.db`。
**⇒ 若要让 PHP 面板直接读 Shittim 库，必须先解决权限（例如给 www 组读权限 / 或改库文件位置 / 或走 admin API）。**

## 5) SDK / 认证库（实测）

```
/www/wwwroot/ba_sdk/   root:root
  cards.json 189 B (22:01)
  sdkcard.py 13,328 B  sha256 **ed2053dc9de1062565491a1af036610a13bd96be04e5717de04985aac496704e**
  sdkcard.py.order_ep.bak.20261117-202757 (7,874 B)
  check_order_probe.py (3,814 B) / order_probe.log (3,884 B) / pay.json (47 B)
  __pycache__/ resp/ run-1794587616.log

pm2: **command not found**（实测）⇒ sdkcard 不是 pm2 管理，是裸 python 进程（监听了 127.0.0.1:8080，见 sdkcard.py:384）

accounts.db 结构（实测）:
  tables: schema_meta(3) id_alloc(1) accounts(3) sessions(76) account_blobs(63) protocol_log(0)
  accounts 列：server_id, dev_id, device_unique_id, sdk_token, publisher_account_id, nickname,
              call_name, state, level, exp, comment, lobby_mode, represent_character_server_id,
              memory_lobby_unique_id, location, birthday, call_name_update_time, link_reward_date,
              last_returning_date, retention_days, vip_level, unread_mail_count, next_entity_id,
              created_at, last_login_at, token_seen_at, login_count
  样本 3 行：
    10000000000 / dev 314816420  / '老师0001' / lobby_mode=1 / rep=1000001 / next_entity=1000005
    10000000001 / dev 1013178778 / '老师0002' / lobby_mode=0 / rep=210001  / next_entity=1100005
    10000000002 / dev 999888777  / '老师0003' / lobby_mode=0 / rep=1200001 / next_entity=1200005
```
**⇒ accounts.db 是 **DevId ↔ 桥账号(server_id) ↔ publisher_account_id** 的映射库（**不含卡密**；卡密只在 MySQL + cards.json）。**
**⇒ `lobby_mode`/`represent_character_server_id` 已被写进这张表 —— 之前对账号 2（10000000001）的改动确实在这里（`lobby_mode=0, rep=210001`）。**
**⇒ `sdk_token` 列明文存着 SDK token（如 `61de1d1b…`）—— 属敏感数据，面板展示需脱敏。**

## 6) 审计与日志（实测）

```
/www/wwwroot/bapatch/cn_*.txt（21 个开关文件，示例值）：
  cn_1017_relay.txt = 1        cn_devid.txt = 1
  cn_dedup.txt = 1             cn_dedup_window.txt = 900
  cn_billing_block.txt = 1     cn_account_svc.txt = 1
  cn_nametoken.txt = 1         cn_protonum_remap.txt = 0
  cn_relay_known.txt = 1       cn_inner_src.txt = spec26 ...

/www/wwwroot/ba_sdk/:
  sdk.log 22,282 B  -rw-r----- root:www   最后写入 20:52
  最后几条：20:50:02 /common/config dev=   / 20:52:26 /common/config dev=
  order_probe.log 3,884 B (20:30)
```
**⇒ 面板若要"审计"，可用素材：`audit_logs`/`login_logs`/`login_attempts`（MySQL，当前 login_logs=0）、
`/www/wwwlogs/*.log`（nginx + tcp-access + ba_raw）、`ba_srv/logs/log.txt`（Shittim 业务日志）、`ba_sdk/sdk.log`。**

---

## 7) 给 Lead 的关键判断（区分实测 / 推断）

| # | 事项 | 判定 | 依据 |
|---|---|---|---|
| 1 | admin API 本机可用（5000/5100） | **实测 ✅** | curl 200 + 有效 JSON |
| 2 | admin API **公网可打且无鉴权** | **实测 ⚠️ 严重** | 公网 curl 200 + 返回真实数据；`AdminApiKey` 为空 |
| 3 | 6667 是 HTTP？ | **实测 ❌** | 无响应（游戏 TCP 端口） |
| 4 | PHP 有 pdo_sqlite/sqlite3 | **实测 ✅** | `php -m` 列出 |
| 5 | PHP(www) 能直接读 Shittim 库 | **实测 ❌** | `/root` 700 → Permission denied |
| 6 | PHP(www) 能读 accounts.db | **实测 ✅** | test -r 通过 |
| 7 | cards 表有 kind/max_devices | **实测 ❌ 没有** | DESCRIBE 输出 |
| 8 | sdkcard 由 pm2 管理 | **实测 ❌** | `pm2: command not found`（裸 python，127.0.0.1:8080） |
| 9 | accounts.db 是否存卡密 | **实测 ❌ 不存** | 表结构无卡密字段；卡密在 MySQL+cards.json |
| 10 | 面板读玩家数据应走哪条路 | **推断**：优先 admin API（同机 127.0.0.1），而非直读 SQLite（权限不通） | 见 2、5 |

## 8) 本轮只读声明
```
未写任何文件（除 /tmp 下临时 .py 脚本——已删除）
未重启任何进程 / 未 reload nginx / 未改 Config / 未动 DB
```

---

# 补充取证（22:02，只读）：(a)-(d)

## 0) 确认：三个67 已到账（实测）
```
GemBonus=1,101,000 / Gem=1,101,000   （基线 101,000）→ +1,000,000 ✅
```

## (a) `accounts.db` 完整结构 + 3 行真实数据

**`accounts` 有 `dev_id` 列**（27 列，逐个）：
```
 1 server_id                2 dev_id                3 device_unique_id
 4 sdk_token                5 publisher_account_id  6 nickname
 7 call_name                8 state                 9 level
10 exp                     11 comment              12 lobby_mode
13 represent_character_server_id  14 memory_lobby_unique_id  15 location
16 birthday                17 call_name_update_time 18 link_reward_date
19 last_returning_date     20 retention_days       21 vip_level
22 unread_mail_count       23 next_entity_id       24 created_at
25 last_login_at           26 token_seen_at        27 login_count
```
**关键回答：`dev_id` 存的是 `Account_Auth` 请求里的 `DevId` 原值**，不是卡密、不是 md5：
```
dev_id 样本：['314816420', '1013178778', '999888777']
其中 314816420 == publisher_account_id（第一行两者相同）
```
**⇒ 而 `md5('11111111111')[:8] == '314816420'`（此前已验证）—— 说明「卡密 → DevId」这一步**在客户端/SDK 侧**完成（SDK 把卡密派生成 DevId），桥只认 DevId。**
**⇒ 面板要做「卡密↔玩家」映射，唯一可行的连接键是：`cards.card_key` →(SDK 派生规则)→ `accounts.dev_id`。这条派生规则目前**不在服务器上**（在 sdkcard.py 或客户端里），需要 Lead 让 logcat-architect 确认 `md5(card_key)[:8]` 是否就是该规则。**

**三行完整数据**
```
row1: server_id=10000000000 dev_id='314816420'  device='3849b23a…87c6' sdk_token='61de1d1b…210'
      publisher_account_id=314816420 nickname='老师0001' lobby_mode=1 rep=1000001
      next_entity_id=1000005 login_count=36 last_login_at='2026-11-17T20:35:20'
row2: server_id=10000000001 dev_id='1013178778' device='6b186f8a…c35c' sdk_token='076b037e…7852'
      publisher_account_id=1013178778 nickname='老师0002' lobby_mode=0 rep=210001
      next_entity_id=1100005 login_count=39 last_login_at='2026-11-17T21:57:03'
row3: server_id=10000000002 dev_id='999888777'  device='deadbeefcafe0001' sdk_token='61de1d1b…210'
      publisher_account_id=999888777 nickname='老师0003' lobby_mode=1 rep=1200001
      next_entity_id=1200005 login_count=1 last_login_at='2026-11-17T20:28:38'
```
**`id_alloc`**：`('server_id', 10000000003)` —— 下一个桥账号号段。
**`schema_meta`**：`schema_version=1` / `server_id_base=10000000000` / `created_by=work/ba/server/schema_sqlite.sql`。
**⚠ 敏感**：`sdk_token` 明文存（3 行都有），面板展示需脱敏。

## (b) 桥接：DevId → publisherId（grep 实测）
```
110:  req = {'DevId': rec.get('req_DevId') or '', ...
499:  rec['req_DevId'] = dv.strip()
（grep 里没有 alloc/publisher_id/10000000000 的其它命中 —— 说明这部分逻辑在 account_service.py，不在 probe 主文件）
```
**⇒ 桥（account_auth_probe.py）只负责把 DevId 塞进 rec；真正的"建号 + 分配 publisher_account_id"在 `/www/wwwroot/bapatch/tools/account_service.py`（`identify()` → `get_or_create_account()` → `_alloc_server_id()`）。**

## (c) 卡密站 vhost（实测）
```
卡密站绑在 **独立 IP 的 vhost**：/www/server/panel/vhost/nginx/<SERVER_IP>.conf
  server_name <SERVER_IP>;
  root /www/wwwroot/ba_cardadmin;
  （文件内 :24-32 有 "ba_cardadmin protect -- BEGIN/END" 段）
不是 example.com/cards/ 子路径，也不是独立域名 —— 是 **https://<SERVER_IP>**（IP 直连）
其它 vhost 的 server_name/root：
  0.default.conf        server_name _;                     root /www/server/nginx/html
  example.com.conf server_name example.com example.com;  root /www/wwwroot/example.com (+ noroot_payloads)
  ba_mitm.conf          state-api/stateqc-api/gsqc-api/gs-api/static .bluearchive-cn.com（无 root）
  phpfpm_status.conf    server_name 127.0.0.1
```
**⚠ 注意：`<SERVER_IP>.conf` 与 `ai_example_tech.conf` 都声明了 `server_name <SERVER_IP>` —— 又是一个重复 server_name（与 www 那个同类问题），可能有一个被 ignored。**

## (d) PHP 扩展与目录权限（实测）
```
php -i: curl ✔（curl.cainfo=/etc/ssl/certs/ca-certificates.crt）
        openssl ✔（openssl.cafile 同路径；capath=no value）
目录：/www/wwwroot/ba_cardadmin/logs   drwxrwxr-x www:www
      /www/wwwroot/ba_cardadmin/state  drwxrwxr-x www:www
      state 内容：cards.backup.json(189B root:root)、.htaccess(www)、sync.lock(root, 0666, 0B)
php-fpm：master 全是 root（83/84/85/81/82 五套），worker 用户未在本次输出中列出
⇒ **www 对 state/ 与 logs/ 有写权限（rwxrwxr-x），PHP 可做 API 缓存/日志**（但 state 里现有两个文件是 root 所有者，
   PHP 若需覆盖它们会失败；新建文件没问题）
```

## 结论补充（给 Lead 决策用）
1. **「卡密↔玩家」的映射键 = `dev_id`**，但 `dev_id` 是 SDK 从卡密派生出来的值（`314816420 = md5('11111111111')[:8]`），**派生规则不在服务器上** ⇒ 面板要么让 SDK 上报卡密明文（新增字段），要么在 PHP 侧复刻派生规则。
2. **卡密站入口是 `https://<SERVER_IP>`（IP 直连）**，不是 example.com 子路径 —— 面板集成时注意别改错 vhost。
3. **`<SERVER_IP>` 的 server_name 重复声明**（与 ai_example_tech.conf 冲突），建议顺手记一笔（不修）。
