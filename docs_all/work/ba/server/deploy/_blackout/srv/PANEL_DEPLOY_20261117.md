# 统一面板 —— 步骤 5–8 执行记录（2026-11-17 22:08–22:09）

执行者：srv-ops ｜ 前提：**未重启 Shittim、未动 nginx**（只传 PHP + 写 MySQL settings）

---

## 修正 B：三条取证（只读）

### B-(1) Config 生效路径
```
ls -la /root/Config.json                        → No such file or directory
ls -la /www/wwwroot/ba_srv/Config/Config.json   → -rw------- 2639 B  2026-11-17 22:07
grep SQLConnectionString → 37: "Data Source=/root/shittim.sqlite3"     ← **已是绝对路径**
AdminApiKey 长度 → key_len=64（在本文件里）
```
**⇒ 生效的是 `/www/wwwroot/ba_srv/Config/Config.json`；`SQLConnectionString` **已经是绝对路径**，上一轮设的"雷"已排除。**

### B-(2) Accounts 状态
```
ServerId | State | PublisherAccountId | Nickname
   1     |   1   | None               | 'Schale'
   2     |   1   | 314816420          | ''
```
**⇒ 全部 State=1（Normal），没有 Dormant，封禁门禁不会误伤。**

### B-(3) State 分布
```
State=1  count=2
```

---

## 5) 上传 13 个文件

### 5a 上传前：线上已存在文件的 sha256（Lead 要的"没被别人改过"核对）
```
10999d649752f4011e4100738478c54508a300d2fad00ec4f89006b4c662b323  inc/helpers.php
fd4d66c1395999536593defecdc6dbebd27d29da798fb8cd3f5907a1fc67b1b7  assets/app.css
4afd04ff8e8bcb939b3b376b8bd895fc9094a411226a3aa5d1bdbd1234974483  pages/dashboard.php
dd4f7cd47e927c71f4c9b533833c0bec93acfe6d88ad4a25344e3b58cfce3c4e  pages/settings.php
3caaf5b0aafc86df6c0d2ef00efb641a56808ded6ed76e85582e6653dfa40aaf  pages/cards.php
```
（均为**旧版本**，接下来被覆盖；无人并发修改的迹象。）

### 5b /tmp 校验（13/13 OK）
```
inc/ba.php                 17298  OK
inc/players.php            16702  OK
inc/helpers.php            25872  OK
assets/app.css             18146  OK
pages/dashboard.php        14386  OK
pages/settings.php         19474  OK
pages/players.php          13015  OK
pages/player_detail.php    20780  OK   ← 按 Lead 修正后的值
pages/mail.php             16303  OK
pages/currency.php          8749  OK   ← 按 Lead 修正后的值
pages/items.php            15075  OK
pages/console.php           9976  OK
pages/cards.php            25199  OK   ← 第 13 个
--- OK=13  BAD=0 ---
```

### 5c/5d 落盘 + 权限
```
13 个文件全部 copied 到位
chown www:www 逐文件成功；chmod 644 成功
-rw-r--r-- 1 www www 17298 inc/ba.php
-rw-r--r-- 1 www www 25199 pages/cards.php
-rw-r--r-- 1 www www  8749 pages/currency.php
⚠ `chown -R` 在 `.user.ini` 上报 "Operation not permitted"（该文件被宝塔设为不可改），
  与 13 个目标文件无关，已改用逐文件 chown 规避。
```

### 5e 全量 sha256 复核（与清单逐一比对，全部一致）
```
752f1637…  inc/ba.php              6731f39d…  inc/helpers.php
f60536d3…  inc/players.php         acdbc8a1…  assets/app.css
d09e8bb2…  pages/dashboard.php     9212b2f6…  pages/settings.php
de294ef9…  pages/players.php       fd505d52…  pages/player_detail.php
95ca56ed…  pages/mail.php          dd80a83b…  pages/currency.php
74a0ee2a…  pages/items.php         01d59035…  pages/console.php
cc20f29e…  pages/cards.php
```

## 6) php -l 全站
```
文件数=26   通过=26   非通过行=0
⇒ ✅ 全部通过，无语法错误
```

## 7) MySQL settings 3 行 + 缓存目录
```
conn user=ba_cardadmin host=127.0.0.1 db=ba_cardadmin（密码未打印）

查询结果：
  ba_accounts_db   /www/wwwroot/bapatch/data/accounts.db
  ba_admin_base    http://127.0.0.1:5000
  ba_admin_key     len=64

缓存目录：
  drwxr-xr-x 2 www www 4096 Nov 17 22:09 /www/wwwroot/ba_cardadmin/state/bacache
```

## 8) 面板自检（**修正：卡密站实际监听 8081，不是 443/80**）
```
vhost: /www/server/panel/vhost/nginx/<SERVER_IP>.conf
  listen 8081;  server_name <SERVER_IP>;  root /www/wwwroot/ba_cardadmin;

http://<SERVER_IP>:8081/login.php   → **200**（1,497 B，<title>登录 · 卡密管理后台</title>）
http://<SERVER_IP>:8081/            → **302** → /login.php?next=%2F
http://<SERVER_IP>:8081/index.php   → **302** → /login.php?next=%2Findex.php
http://<SERVER_IP>:8081/pages/dashboard.php → **302** → /login.php?next=%2Fpages%2Fdashboard.php（未登录正确拦截）

https://<SERVER_IP>/login.php → **000**
  原因（curl -v）：`SSL certificate problem: self-signed certificate in certificate chain`
  ⇒ 该 IP vhost 只监听 8081（HTTP），443 走 SNI 分流到 MITM 自签证书 ⇒ HTTPS+IP 不可用属预期。
  **面板入口 = `http://<SERVER_IP>:8081/`**
```

## 8b) `sudo -u www` 连 Shittim（模拟 php-fpm 视角）
```
www_status=**200**
[{"serverId":2,"nickname":"","callName":null,"level":1,"exp":0,"comment":null,
  "publisherAccountId":314816420,"state":"Normal","vipLevel":null,
  "lastConnectTime":"2026-11-17T20:34:53.9409781","createDate":"…","unReadMailCount":null}]
```
**⇒ PHP 进程（www）能带 key 正常调用 admin API 拿到真实数据 —— 面板不会白屏。**

---

## 更新后的判定表（0–8 全量）

| 项 | 结果 |
|---|---|
| 旧 DLL sha = `cd8c5c99…` | ✅ |
| 新 DLL sha = `adcb1e03…` | ✅（2,672,640 B） |
| key_len = 64 | ✅ |
| Shittim 监听 5000/5100 | ✅（pid 2646805，单实例） |
| 带 key 本机 200 | ✅ |
| 不带 key 本机 403 | ✅ |
| 公网 `/api/admin/accounts` 403 | ✅（www/bare 403；gsqc 桥路径 200 但 body 是 403 JSON，零泄露） |
| accounts 含 publisherAccountId | ✅（+state/lastConnectTime/createDate/unReadMailCount） |
| **php -l 全通过** | **✅ 26/26** |
| **settings 3 行已写入** | **✅（含 ba_admin_key len=64）** |
| **`sudo -u www` 连通 admin API** | **✅ 200 + JSON** |
| 面板入口可达 | ✅ `http://<SERVER_IP>:8081/login.php` 200；`/` 302 → login |

## 回滚（未执行）
```bash
STAMP=$(cat /root/panel_backup_LATEST.txt)
# PHP 侧
rm -rf /www/wwwroot/ba_cardadmin && cp -a /root/panel_backup_$STAMP/ba_cardadmin /www/wwwroot/
# DLL/Config（本轮未改，若要回滚 DLL）
cp -a /root/panel_backup_$STAMP/Shittim-Server.dll /www/wwwroot/ba_srv/Shittim-Server.dll
cp -a /root/panel_backup_$STAMP/Config.json        /www/wwwroot/ba_srv/Config/Config.json
# MySQL：删除面板新增的 3 行
#   DELETE FROM settings WHERE k IN ('ba_admin_base','ba_admin_key','ba_accounts_db');
```
（注：本轮 PHP 文件是"覆盖式更新"，`ba_cardadmin` 的其它文件保持原样；上面 rm+cp 是完整还原。）

---

## 待修清单（P2，本轮不修）

**P2-1 · 桥把上游 HTTP 状态码抹平成 200**
```
现象：经 gsqc-api/gs-api（location ^~ /api/ → 桥 9097）的任何请求，
      上游 4xx/5xx 都被桥改写成 200，body 原样透传。
实测：/api/admin/accounts 经 gsqc → HTTP 200 + {"error":"Admin API requires a valid X-Admin-Key header."}（58 B）
影响：任何"靠状态码判断"的调用方（包括以后的面板、监控、SDK）都会误判成功。
      当前不造成数据泄露（body 是错误 JSON）。
建议：桥在转发时透传上游 status（现在 `code=200` 是桥自己拍的）。
```

**P2-2 · 面板 HTTPS 入口缺失（观察项，非缺陷）**
```
卡密站 vhost 只 listen 8081（HTTP），https://<SERVER_IP> 因 SNI/IP 分流落在 MITM 自签证书上 → 000。
若要 HTTPS，需要给该 vhost 配证书并改 SNI 分流（属 nginx 改动，需用户授权）。
```

---

# 附录：步骤 0–4 的关键原始输出（完整版见 22:08 那条消息）

```
STAMP=20261117_220711
备份：/root/panel_backup_20261117_220711/{ba_cardadmin/, Config.json, Shittim-Server.dll}
旧 DLL sha  cd8c5c99482ec810f047a30f655bfbe04fda5dc267c4b9ea8747a6b735700a9f   ✅
旧 Config   eeb48ba44c112d1a2dd41c3479fc066c2b89dd5f42a6d4c6c91ed6347167e837
新 DLL      adcb1e03bc82b8fcad97a27e2054483f75c0079dd80e799615a76b6b55229377   2,672,640 B ✅
AdminApiKey old_len=0 → key_len=64；Config sha d64d6350bce0e1f83f825b7e9eac9bd03122ced8ce2bf528e5b1774104386f8b

重启（因 tmux Ctrl-C 会销毁会话，改用 new-session）：
  [22:07:46 INF] Now listening on: http://0.0.0.0:5000
  [22:07:46 INF] Now listening on: http://0.0.0.0:5100
  dotnet pid 2646805（单实例），5000/5100/6667 LISTEN

验证：
  带 key 本机 status        → 200
  不带 key 本机 status      → 403  {"error":"Admin API requires a valid X-Admin-Key header."}
  公网 www/bare accounts    → 403（HTTP/2，body 同上）
  经 gsqc 桥 accounts       → 200 + 同一 403 JSON（58 B，零泄露；见 P2-1）
  accounts(带key)          → 含 publisherAccountId=314816420 / state=Normal / lastConnectTime / createDate / unReadMailCount
  detail / currencies      → 正常（Gem=1,101,000 等）
  accounts.db Config 生效路径 → /www/wwwroot/ba_srv/Config/Config.json（/root/Config.json 不存在）
  SQLConnectionString      → Data Source=/root/shittim.sqlite3（绝对路径）
  Accounts State           → 1 / 1（无 Dormant）
```

---

# 第 9 步：12 页面「真渲染」冒烟（2026-11-17 22:10，带登录态）

方法：MySQL 插一条 10 分钟临时会话（`user_agent='lead-smoke'`，token `24207301…e555f`），
用 `curl -H "Host: <SERVER_IP>" -b "ca_sid=$TOK" http://127.0.0.1:8081/<page>` 逐页 GET；
结束后**已删除**该会话（`left_smoke = 0`，sessions 总数回到 4）。

## 2) 逐页结果（原始表）

```
page                                         code   bytes     err_hits
pages/players.php                            200    8383      0
pages/mail.php                               200    68836     0
pages/currency.php                           200    8690      0
pages/items.php                              200    160226    0
pages/console.php                            200    9513      0
pages/cards.php                              200    8132      0
pages/dashboard.php                          200    8327      0
pages/settings.php                           200    12932     0
pages/logs.php                               200    5672      0
pages/admins.php                             200    6269      0
pages/audit.php                              200    8471      0
pages/player_detail.php?sid=2                200    33896     0
```
**⇒ 12/12 code=200，err_hits 全 0。**

## 3) err_hits>0 的错误原文
```
含错误的文件数: 0
（Fatal/Parse/Uncaught/Undefined 关键字全部 0 命中）
```

## 4) 数据流验证（不是空壳）

**发奖页 `pages/mail.php`（68,836 B）**
```
青辉石 / 青辉石/金币/体力
青辉石(付费)（#2 / 青辉石(免费)（#3 / 青辉石(合计)（#4
青辉石免费=3
GemPaid / GemBonus 均出现
<option> 共 713 个，样例：
  <option value="Currency" selected>货币/青辉石/金币/体力
  <option value="Item">道具
  <option value="Character">角色
  <option value="Equipment">装备
  <option value="MemoryLobby">记忆大厅（L2D）
```
**详情页 `pages/player_detail.php?sid=2`（33,896 B）**
```
青辉石是派生值（Gem…
青辉石(付费)（#2 / 青辉石(免费)（#3 / 青辉石(合计)（#4
GemBonus
角色（4）   ← 与 DB 中 Characters acct2=4 一致
Lv 1
```
**设置页 `pages/settings.php`（12,932 B）**
```
在线 / 可读 / pdo_sqlite / ok      ← 服务端连通与 PHP 扩展状态都在渲染
```
**卡密页 `pages/cards.php`（8,132 B）**
```
玩家                                ← 新增的「玩家」列已渲染
```
**玩家页 `pages/players.php`（8,383 B）**
```
#2<  /  314816420  /  dev
```
**首页 `pages/dashboard.php`（8,327 B）**
```
玩家 / 在线 / 账号
```

## 判定

| 判定项 | 结果 |
|---|---|
| 12 页全部 code=200 | **✅** |
| err_hits 全 0 | **✅** |
| Fatal/Parse/Uncaught/Undefined | **✅ 0 命中** |
| 数据真的渲染出来（非空壳） | **✅**（青辉石/GemBonus/角色（4）/玩家列/在线/可读） |
| 临时会话已删除 | **✅ left_smoke = 0**（sessions 4→4） |
| 临时 html 已清理 | **✅ removed /tmp/smoke_*.html** |

**⇒ 面板 12 个页面全部可正常渲染，可以交给用户点。**
（`/tmp` 下临时会话 token 已随删除失效；会话表恢复原状。）
