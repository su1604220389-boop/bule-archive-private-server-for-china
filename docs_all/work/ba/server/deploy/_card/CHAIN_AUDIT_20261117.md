# 卡密链路审计 · 2026-11-17

> 范围：**卡密网站(PHP/MySQL) → 卡密 SDK 签发 token → 我们的认证桥 → Shittim** + 管理面板改造面。
> 方式：本地代码/镜像审计 + `srv-ops` 线上只读取证（2026-11-17 20:17）。**未改任何线上文件、未重启任何进程。**
> 本文只给结论与方案；改代码前等 lead 点头（§SDK 第一阶段补丁已就绪，见 §SDK-6）。

---

## 0. 一页结论

| 环节 | 判定 | 依据 |
|---|---|---|
| 卡密站（PHP/MySQL）→ `cards.json` | **已打通** | cron 每分钟同步成功：`导出 1 个卡密，189 B`（`srv-ops` 20:17 取到 `sync.log`） |
| `cards.json` → SDK 登录/签发 token | **已打通** | `sdkcard.py` pid 26781 监听 `127.0.0.1:8080`，`/user/login`、`/user/quick-login` 真实实现；`cards.json` 读到 1 张卡 |
| SDK token → 认证桥「校验」 | **完全没打通** | 桥里 `UID/TOKEN/ENTER_TICKET` 是硬编码常量（L164-166），token 只在 L1760 被**记录**；`/auth/verify` 在线上返回的是兜底 `200 {}`，即**该端点不存在** |
| 公益卡 / 自定义绑定台数 | **完全没打通** | MySQL `cards` 只有 `bind_one`(bool)，没有 `kind`/`max_devices`；`cards.json` 的导出函数只写 `devices/expire/bind_one`（`sync.php:199-200`） |
| 管理面板（玩家/发奖/货币/角色） | **没打通（0 实现）** | 现有 PHP 面板只做卡密/日志/管理员；不连 Shittim 库 |

**一句话：卡密"发得出、能登录"，但"进来的人是谁"没有校验——桥用同一个硬编码账号接所有人；公益卡在数据模型里根本不存在。**

三档归类：

- **已打通**：卡密站 → `cards.json`；`cards.json` → SDK 登录并签发 token。
- **半打通**：SDK token → 桥（token 有传、有记，但**不验**；`DevId` 是唯一身份依据，可伪造）。
- **完全没打通**：公益卡、按台数绑定、token 校验、玩家维度的管理面板。

---

## §A 链路五问

### A1 卡密站在哪、什么框架、什么库

| 项 | 值 | 证据 |
|---|---|---|
| 站点 | `/www/wwwroot/ba_cardadmin/`（宝塔站点，端口 **8081**，nginx 反代） | `srv-ops`: `0.0.0.0:8081 nginx`；`scripts/321_final_verify.sh` 全部打 `127.0.0.1:8081` |
| 框架 | 原生 PHP（无框架），宝塔 PHP 8.2 | `README.md §0`、`/www/server/php/82/bin/php cron/sync_cards.php` |
| 库 | **MySQL** `ba_cardadmin`（InnoDB / utf8mb4），账号 `ba_cardadmin`（密码在 `scripts/321`，本文不复制） | `sql/schema.sql`、`321_final_verify.sh:37` |
| 题述"39 份报告"里的 `logs/sync.log` | 真实存在，cron 每分钟写；20:17:08–20:17:10 有三条同步记录 | `srv-ops` 第 6 组输出 |

`CREATE TABLE cards` 线上原文（`srv-ops` 取 `SHOW CREATE TABLE`，与 `sql/schema.sql:47-65` 逐字段一致）：

```sql
CREATE TABLE `cards` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `card_key` varchar(64) NOT NULL COMMENT '卡密字符串',
  `status` enum('active','disabled') NOT NULL DEFAULT 'active',
  `expire_at` int(10) unsigned NOT NULL DEFAULT '0' COMMENT 'unix ts，0=永不过期',
  `bind_one` tinyint(1) NOT NULL DEFAULT '1' COMMENT '1 只允许一台设备',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `created_by` varchar(64) NOT NULL DEFAULT '',
  `note` varchar(255) NOT NULL DEFAULT '',
  `login_count` int(10) unsigned NOT NULL DEFAULT '0',
  `last_login_at` datetime DEFAULT NULL,
  `last_login_device` varchar(64) DEFAULT NULL,
  PRIMARY KEY (`id`), UNIQUE KEY `uk_cards_card_key` (`card_key`),
  KEY `idx_cards_status` (`status`), KEY `idx_cards_expire` (`expire_at`),
  KEY `idx_cards_created` (`created_at`), KEY `idx_cards_last_login` (`last_login_at`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4;
```

其余 7 张表：`admins` / `sessions` / `card_devices`（卡→设备一对多）/ `login_logs`（解析 sdk.log）/ `audit_logs` / `settings` / `login_attempts`（`sql/schema.sql:14-140`）。

**样例行（脱敏）**：

```
cards: 1 行   bind1=0  never=1     ← 即唯一一张卡：不限设备、永不过期
cards.json: 1 张卡  11111111111  devices=1  expire=0  bind_one=false   (189 B)
AUTO_INCREMENT=4                    ← 历史上建过 id=1..3，删过 2 张
```

### A2 卡密类型：库里到底怎么表达

| 用户说的类型 | 当前库里能表达成什么 | 判定 |
|---|---|---|
| 普通卡（一号一卡，绑 1 台） | `bind_one=1` | ✅ 等价 |
| 普通卡（不绑设备 / 不限台数） | `bind_one=0` | ⚠️ 只能"1 台"或"无限台"，**没有"N 台"** |
| **公益卡**（跟随设备、不限期、不限设备/台数） | 只能拼成 `expire_at=0 + bind_one=0` | ❌ **行为不等价**：`DevId` 仍由**卡密**派生（`md5(card)[:8]`，`sdkcard.py:46`），不是设备；换一张公益卡就换一个号 |
| **绑定台数可自定义 N** | 无法表达 | ❌ 只有 bool |

根因有两层：

1. **DB 层**：`cards` 没有 `kind`、没有 `max_devices`、没有 `self_unbind_limit`（线上 `SHOW CREATE TABLE` 已确认）。
2. **同步层**：`inc/sync.php:199-200` 的 `sync_make_payload()` 只导出三个字段——

```php
'expire'   => isset($r['expire_at']) ? (int)$r['expire_at'] : 0,
'bind_one' => (isset($r['bind_one']) && (int)$r['bind_one'] === 1),
```

  即使 `cards.json` 里手工塞了 `kind/max_devices`，**cron 每分钟会把它们冲掉**（`SDKCARD_V2.md §0` 已把这条列为上线阻断项）。

> 结论：**公益卡不是"没配好"，是"库里没有这个概念"**。要支持，必须先改 MySQL 表 + `sync_make_payload()`，再做 SDK 侧 `kind` 分支。

### A3 token 怎么签、存在哪

签发者：**我们的卡密 SDK `sdkcard.py`**（不是 PHP 站，也不是 AiriSDK）。

```python
# sdkcard.py:42-48
def user_payload(card, device):
    tpl = json.load(open(TEMPLATE))['Data']
    tok = hashlib.sha256((card + '|' + device).encode()).hexdigest()[:40]
    tpl['User']['Token'] = tok
    tpl['User']['ID'] = int(hashlib.md5(card.encode()).hexdigest()[:8], 16) % 900000000 + 100000000
    tpl['Pass']['NickName'] = 'BA' + card[-4:]
    return tpl
```

| 项 | 值 |
|---|---|
| 算法 | `sha256(card + "|" + device)` 取**前 40 hex**，`hexdigest()[:40]` |
| 密钥/签名 | **无**。纯哈希指纹，没有 secret、没有 HMAC、没有签名段 |
| 有效期 | **无**。token 自身不过期；只在每次登录时检查卡的 `expire` |
| 存在哪 | ① `cards.json` 的 `devices[]`（间接：token 可由 card+device 重算）；② 返回给客户端 `User.Token`；③ 桥的 `rec['req_Token']`（只记日志）；④ `sdk.log` 明文（`w()` 原样写） |
| 已知真值 | 卡 `11111111111` + 设备 `09a4d0ab0ee93616` → `User.ID=314816420`、`Token=61de1d1b…`（`SDKCARD_V2.md §1.2`，与线上 bridge 的硬编码一致） |

**性质**：它不是"凭证"，是**可推导的身份指纹**——任何人知道卡密和设备号都能算出同一个 token；反过来，token 也不证明"持有者拥有这张卡"。

### A4 认证服务器怎么校验它

**结论：桥 `account_auth_probe.py` 完全不校验 token。** 三处代码：

1. **硬编码身份**（线上 sha `ade3917c…`，行号与 `srv-ops` 输出一致）：

```python
164: UID   = '314816420'
165: TOKEN = '61de1d1b7519ab1231866f54c11fcfdd1f80b210'
166: ENTER_TICKET = base64.b64encode(('%s/%s' % (UID, TOKEN)).encode()).decode()
```

2. **所有玩家都拿这一张 ticket 去铸会话**（`account_auth_probe.py:1063` `ensure_session`）：

```python
1063: def ensure_session(rec):
1073:         req = {"Protocol": "Account_CheckNexon", "EnterTicket": ENTER_TICKET, ...
1077:         code, raw = post_gateway(req)
```

3. **客户端带来的 token 只被记录，不参与任何判断**：

```python
1760:                     rec['req_Token'] = req_json.get('Token')
```

   全文件对 `token` 的引用只有这一处"赋值"，没有任何 `sha256`、没有 `cards.json`、没有 `/auth/verify` 调用。
   （上面这三段行号取自 `_sandbox/lead_fix2/account_auth_probe.py`（136,894 B）；线上 live 版 sha 虽不同，但 `srv-ops` 实测 **L164-166 仍是这三行**，且 `BAPATCH-MU` 标记为 0。）

线上旁证（`srv-ops` 20:17）：

```
POST http://127.0.0.1:8080/auth/verify -> {"Code":200,"Msg":"OK","Data":{}}
```

—— 这是 `sdkcard.py:151` 的兜底响应，说明**线上根本没有 `/auth/verify` 这个端点**（`sdkcard_v2.py` 不存在）。

**连"多用户服务"也不验 token**。`account_service.py:34` 的注释写得非常直白：

```
D2 DevId 是主身份键，Token 只做记录（SDK token 会轮换；本地无法验证它）
```

即：即使开启了 per-user 分流（`cn_account_svc.txt`），身份也只看 `DevId`，而 `DevId = md5(card)[:8]` 是**公开可算**的——任何人构造一个 DevId 就能冒充某个卡主。

### A5 结论：这条链到底通没通

```
卡密站(MySQL) ──cron/1min──► cards.json ──► sdkcard.py 校验卡密/设备/过期
                                                │  签发 Token=sha256(card|device)[:40]、User.ID=md5(card)
                                                ▼
                                        客户端登录（SDK 200）
                                                │
                                                ▼
                                     桥 account_auth_probe.py
                                     ★ 不读 token、不读 cards.json
                                     ★ 只用硬编码 ENTER_TICKET(314816420/61de1d1b…)
                                                │
                                                ▼
                                     Shittim 建号/发 SessionKey（所有人同一个 ServerId=2）
```

- **已打通**：卡密 → `cards.json` → SDK 登录（含过期/设备绑定/`bind_one` 检查）。
- **半打通**：token 传到桥了，但**没有任何校验**；桥的身份是写死的。
- **完全没打通**：公益卡、台数绑定、token 校验、玩家维度。

> 风险直说：**卡密体系目前是"装饰性"的**。知道 API 地址的人不带卡密也能进（Shittim 对未知 publisherId 自动建号，`ADMIN_PANEL_SPEC.md:99` 有实测：`1013178778 → ServerId=3`）。这不是"可能"，是已复现过的行为。

---

## §B 管理面板改造清单

### B1 现状：有什么

**主面板（PHP，线上）**：`/www/wwwroot/ba_cardadmin/`，8 个页面（`work/ba/cardadmin_php/pages/`）：

| 页面 | 能力 |
|---|---|
| `dashboard.php` | 统计 / 最近 20 条登录 / 同步状态 |
| `cards.php` | 卡密列表：分页 50·100·200、搜索、按状态/期限/绑定筛选、排序 |
| `cards_new.php` | 单个新建 + 批量生成（≤5000） |
| `cards_import.php` | 文本/文件批量导入（≤2 MB） |
| `cards_export.php` | 导出 txt / csv |
| `logs.php` | **只读解析 `sdk.log` 入库** + 筛选分页（卡密/设备/结果/时间） |
| `admins.php` | 管理员增删、改密、启停 |
| `audit.php` | 所有写操作的审计日志 |
| `settings.php` | 同步开关/路径/环境自检 |

后端是**服务端渲染的 PHP 页面 + POST action**，不是 REST；写操作全部走 `audit_logs`。
批量操作：删除 / 延期 N 天 / 永不过期 / 解绑设备 / 启用 / 禁用（`README.md §0`）。

**备选实现（Python，未上线）**：`work/ba/cardadmin/`（8899，原生 JS 单页，15 条 `/api/*`：login/logout/password/me/health/dashboard/cards/logs/audit/cards-create/generate/import/export/reveal/update/bulk）。功能面与 PHP 版等价，**同样不碰 Shittim**。

### B2 用户要的 vs 现在（差距表）

| # | 用户要的 | 现状 | 差距 | 依赖 |
|---|---|---|---|---|
| 1 | 显示**全部用户**（公益卡/设备绑定/卡密绑定） | 只有"卡"和"设备"，没有"用户"实体 | **0 实现**；且游戏库里目前只有 1 个公共号 | P-A（身份主键） |
| 2 | 按类型筛选用户 | 无 | 0 | 先有 1 |
| 3 | **一键批量发奖励**（选人/选物/选数量） | 无 | 0 | P-B（跨账号写入） |
| 4 | 封号/解封 | 无 | 0 | P-B |
| 5 | 改密码 | 只有**管理员**改密；玩家侧无密码概念 | 不适用（SDK 无密码） | — |
| 6 | 解绑设备 | ✅ 单卡/批量解绑 | 已具备 | — |
| 7 | 改绑定台数 | 只能 1 / ∞（`bind_one`） | 需 `max_devices` + 改同步 | A2 |
| 8 | 查登录记录 | ✅ `logs.php`（sdk.log） | 已具备；但只有 SDK 侧，无游戏侧登录 | — |
| 9 | 查货币/角色 | 无 | 0 | P-B 只读 |
| 10 | 发补偿 | 无（= 3 的另一种入口） | 0 | P-B |
| 11 | 综合平台（卡+人+游戏数据） | 卡密管理平台 | 需新增两层（admin 后端 + 玩家页） | P-A/P-B |

### B3 数据在哪：两个库 + 跨库方案

| 库 | 内容 | 现状访问方式 |
|---|---|---|
| MySQL `ba_cardadmin` | 卡密、设备、管理员、审计、登录日志 | PHP PDO（已通） |
| SQLite `/www/wwwroot/ba_srv/shittim.sqlite3` | `Accounts` / `Characters` / `Currencies` / `Mails` / `AttendanceHistories` … | **无任何面板在读** |

**推荐（与 `ADMIN_PANEL_SPEC.md §5` 一致，但补上跨库细节）**：

```
浏览器 → PHP 卡密站（现有，不动卡密逻辑）
           └─ 只调本机 127.0.0.1:8899 的 admin 后端（Python，新）
                ├─ 只读：sqlite3 file:shittim.sqlite3?mode=ro   （玩家/角色/货币/邮件）
                ├─ 只读：MySQL ba_cardadmin                      （卡/设备/登录）
                ├─ 写：  Shittim admin API（需 .NET SDK，P-B）
                └─ 写：  受控 SQL（仅 admin API 未覆盖的批量）
```

跨库读的三条落地方式（按推荐顺序）：

1. **只读连接 + 内存 JOIN**（首选，零侵入）：admin 后端分别开 `sqlite3(mode=ro)` 与 MySQL 连接，把 `Accounts.PublisherAccountId` 与 `cards`→`DevId` 在内存里 join。玩家量 <1 万，完全够用。
2. **镜像表**（要 SQL 过滤/分页时）：MySQL 建 `shittim_accounts`（`server_id, publisher_account_id, nickname, level, exp, state, last_connect_at, synced_at`），每 5 分钟从 SQLite 增量同步；面板只查镜像表，不实时打 SQLite。
3. **SQLite ATTACH**：SQLite 可以 `ATTACH 'file:...?mode=ro'`，但**跨 MySQL 不行**；且 PHP 侧要额外 sqlite3 扩展，**不推荐**。

**硬约束**：不要把 SQLite 和 MySQL 放进同一个事务（不存在分布式事务）。写操作只走一个库，读可以两边拼。

---

## §SDK 服务端与假支付

### SDK-1 全图（地址 → 端口 → 进程 → 代码）

```
客户端 assets/SDKConfigSettings.json
  sdk_url = "http://127.0.0.1:8080"          ← repack_e31.py:6,17 把 https://sdk-api.yostar.cn 替换而来
        │
        ▼  （手机 loopback）
设备侧 8080（二选一，互斥）
  ├─ PRoot 里的 sdkcard.py
  └─ relay8080.py → https://example.com/sdk/<path>
        │
        ▼  （宝塔 443）
nginx  location /sdk/  →  http://127.0.0.1:8080/     （带尾斜杠 = 剥前缀）
        │
        ▼
云端 sdkcard.py   pid 26781  python3 /www/wwwroot/ba_sdk/sdkcard.py   （**systemd ba-sdk.service，不是 pm2**）
  日志 /www/wwwroot/ba_sdk/sdk.log     卡密库 /www/wwwroot/ba_sdk/cards.json
```

证据：`report/04-服务端就绪度.md:40-43,79,109-114`、`report/06:58,84-85,157-174`、`add_sdk_loc.py`、`relay8080.py:6`；线上 `srv-ops`：`127.0.0.1:8080 python3 pid=26781 /www/wwwroot/ba_sdk/sdkcard.py`，`/root/bapatch/cards.json` 不存在。

> ⚠️ 执行前先确认手机走的是"形态 2"（relay）：`tail -5 /www/wwwroot/ba_sdk/sdk.log` 若没有今天的 `/common/config` 记录，说明手机跑的是 PRoot 本地 `sdkcard.py`，补丁要打到手机那份上。

### SDK-2 端点现状（AiriSDK 32 条 vs 我们 7 条真实现）

`sdkcard.py` 路由表（`do_POST` 内 if 链，行号见本地 v1 副本）：

| 端点 | 状态 | 说明 |
|---|---|---|
| `POST /common/config` | ✅ **真实现** | 读抓下来的官方 config，做 4 组域名替换（`sdkcard.py:73-90`） |
| `POST /user/login` | ✅ **真实现** | `OpenID`=卡密；校验存在/过期/设备绑定（`:93-116`） |
| `POST /user/quick-login` | ✅ **真实现** | 按 `DeviceID` 反查卡（`:118-129`） |
| `POST /user/detail` | ✅ **真实现** | 按设备返回模板（`:131-139`） |
| `POST /common/geo-ip` | 🟡 桩 | 固定 `{"Prov":"浙江省"}`（`:140-142`） |
| `POST /health-game/duration` | 🟡 桩 | 固定"已成年"（`:143-145`） |
| `POST /heartbeat/pulse` | 🟡 桩 | 固定 `Delay:3600`（`:147-149`） |
| **`POST /order/create`** | ❌ **兜底 200 + 空 Data** | **无路由**，落到 `:151` 的 `{"Code":200,"Msg":"OK","Data":{}}` |
| **`POST /order/detail`** | ❌ 同上 | 同 |
| **`POST /order/products`** | ❌ 同上 | 同 |
| 其余 22 条（`/user/relink*`、`/user/device/*`、`/user/identity-auth*`、`/pass/gen-token`、`/channel-user/destroy`、`/common/agreement`、`/common/client-code`、`/user/set-info`…） | ❌ 兜底 | 一律 200 空 Data |

端点常量原文：`SdkConst.java:196-232`（`NET_ORDER_CREATE = "order/create"` 等 32 条，无前导斜杠，客户端自己补）。

**线上 `/auth/verify` 的 200 也是这个兜底**——即 `sdkcard_v2.py`（含 `verify_identity`、`/admin/unbind`、`/admin/issue`）**只存在于 `work/ba/sdk/`，从未部署**。

### SDK-3 三个端点的实现方案（stage 2）

**共同约定**

- 信封：与登录同一套 `{"Code":…,"Msg":…,"Data":{…}}`。**`Code` 的成功值不硬编码**：`sdkcard.py` 现在返回 `200`，但需用 `/order/create` 真实抓包对齐（probe log 到手后确认；`SdkConst.CODE_SUCCESS=200` 是 Java 侧常量，未必是 `Code` 字段值）。
- 代码落点：`sdkcard.py` 的 `do_POST` 里，在 `if path == '/common/config':` 之前插入三个 `if` 分支；**不要**动现有 7 条。
- 全部读 `pay.json`（见下），**重启才生效**，避免运行期被改。

**`/order/products`**

请求：`OrderProductsReq{StoreType}`。
响应：`Data = {"Product":[{"ID":int,"Name":str,"Price":str,"GameProductID":str,"StoreProductID":str,"GameMoney":str}]}`（`OrderProductsEntity.ProductItems`）。
实现：从商品映射表（SDK-4）读出启用的行；`Price` 用游戏内标价字符串；`GameMoney` 给 `""`（除非有证据要求）。

**`/order/create`**

请求：`OrderCreateReq{PayType, ProductId:int, ExtraData:str, NotifyURL:str}`。
响应：`Data = OrderCreateEntity`，六个子对象**只填一个**，其余为 `null`：

| 开关/模式 | 返回 | 客户端预期行为 |
|---|---|---|
| `allow_pay=1` | `Order{OrderNo:"SDK"+yyyymmddHHMMSS+seq, Amount:<商品价×100?>, PayState=<P>, DeliveryState=<D>, FirstPurchase=0, PayType:<回显>}`，`AlipayQRCode` 等一律 `null` | 读到 `PayState` 判定已支付 → 走游戏 29001 领奖 |
| `allow_pay=0` | `{"Code":<失败码>,"Msg":"PAY_DISABLED","Data":null}` | 弹失败，不发奖 |

**`PayState` / `DeliveryState` 可配置**（关键设计）：`/www/wwwroot/ba_sdk/pay.json`

```json
{
  "allow_pay": 0,
  "ok_code": 200,
  "fail_code": 40007,
  "pay_state_ok": 1,
  "delivery_state_ok": 1,
  "amount_mode": "price_x100",
  "order_prefix": "SDK"
}
```

- 两个 state 值**未知**（常量在未反编译类里），因此做成配置：不改代码即可 `1/1 → 2/2 → 0/1` 试。
- `allow_pay` **默认 0**，文件缺失也按 0。
- 所有字段改动后 `systemctl restart ba-sdk`；本实现已做成**每请求重读** `pay.json`/`allow_pay.txt`，改文件即时生效、不用重启。

**`/order/detail`**

请求：`OrderDetailReq{OrderNo}`。
响应：`Data = {"Order":{...同 create 的 Order...},"Level":"","Event":""}`（`OrderDetailEntity`）。
用途：客户端 `BillingCheckPurchaseStateTask`(3086) 会**轮询**——必须返回与 create 一致的 `Order`，否则会被判"未支付"。

**订单存哪**：`/www/wwwroot/ba_sdk/orders.jsonl`（追加写，按 `OrderNo` 查最后一条）。不引 DB，够用且可回滚。

#### SDK-3A 三端点补丁：已就绪并本地验证（stage 2，**未上服务器**）

补丁：`work/ba/server/deploy/_card/patch_order_endpoints.py`（锚点式、幂等、sha 闸、一行回滚），插入 +155 行，**不动现有 7 条路由**。默认 `pay.json` 缺失 ⇒ **拒绝支付**。

本地实测（WSL，真跑 `sdkcard.py`）：

```
pay.json 缺失（默认拒绝）
  /order/products -> {"Code":200,"Msg":"OK","Data":{"Product":[]}}
  /order/create   -> {"Code":40007,"Msg":"PAY_DISABLED","Data":null}

pay.json: allow_pay=1, pay_state_ok=2, delivery_state_ok=2, 商品 ID 1597/¥30
  /order/products -> Data.Product=[{"ID":1597,"Name":"月卡","Price":"30",...}]
  /order/create   -> Data.Order={OrderNo:SDK2026111720210500001, Amount:3000,
                                PayState:2, DeliveryState:2, FirstPurchase:0, PayType:"alipay_qrcode"}
  /order/detail   -> 同一条 Order（未知名 -> Order:null）
  orders.jsonl    -> 1 行
  /user/login     -> 行为不变
回滚后 sha 回到 afaec563…（逐字节一致）
```

上线命令（stage 1 验证通过后再执行）：

```bash
python3 /tmp/patch_order_endpoints.py --src /www/wwwroot/ba_sdk/sdkcard.py --verify
python3 /tmp/patch_order_endpoints.py --src /www/wwwroot/ba_sdk/sdkcard.py --apply
systemctl restart ba-sdk
```

`pay.json` 初始内容（**先拒绝**）：

```json
{"allow_pay": 0, "ok_code": 200, "fail_code": 40007,
 "pay_state_ok": 1, "delivery_state_ok": 1,
 "amount_mode": "price_x100", "order_prefix": "SDK",
 "products": [{"ID": 1597, "Name": "", "Price": "0", "GameProductID": "", "StoreProductID": "", "GameMoney": ""}]}
```

> 注意：stage 2 补丁与 stage 1 补丁**互不依赖**，可叠加。叠加时顺序是：`body` → stage-1 probe（记录）→ 原有 `w()` → `path` → stage-2 分发。所以 **probe 仍会记录全部 `/order/*`**，包括三条已实现的（它插在 `path` 计算之前）。

### SDK-4 商品映射表（ShopCashId ↔ ProductId）

两套 id 的事实：游戏协议用 `ShopCashId`(long, `BillingTransactionStartByYostarRequest.ShopCashId`)，SDK 用 `ProductId`(int, `OrderProductsEntity.ProductItems[].ID`)。二者**没有任何天然推导关系**。

**推荐：自建两列表，放 MySQL `ba_cardadmin`**（面板可维护，复用现有审计）：

```sql
CREATE TABLE IF NOT EXISTS sdk_products (
  product_id     INT UNSIGNED NOT NULL,          -- 客户端看到的 ID（我们自定）
  shop_cash_id   BIGINT UNSIGNED NOT NULL,       -- 游戏 ShopCashExcel.Id
  name           VARCHAR(128) NOT NULL DEFAULT '',
  price_cents    INT UNSIGNED NOT NULL DEFAULT 0,
  enabled        TINYINT(1) NOT NULL DEFAULT 1,
  note           VARCHAR(255) NOT NULL DEFAULT '',
  PRIMARY KEY (product_id),
  UNIQUE KEY uk_shop_cash (shop_cash_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

- **不从 Excel 自动导**：`ShopCashExcel`/`ProductExcel` 在 SQLCipher 加密的 ExcelDB 里（`ADMIN_PANEL_SPEC.md:179`），导出成本高、且商品会随版本变。
- **从真实流量长出来**：stage 1 的 probe 会记录客户端请求的 `ProductId` 与 `ExtraData`（很可能带 `ShopCashId`）；抓到后由面板"绑定到某个 ShopCashId"，一次一条，人工确认。
- 面板加"商品"页：列表 / 改价 / 停用 / 一键导出 `products.json` 给 sdkcard（同 cron 模式，或让 sdkcard 直接读 MySQL——但会引入 MySQL 依赖，**推荐导出 JSON**）。

### SDK-5 发奖链路与 29001 幂等

**现状（源码确证）**：`BillingHandler.cs:164-213` 的 `TransactionEndByYostar` 已经是**完整实现**：

```csharp
// BillingHandler.cs:148-152（注释原文）
// there is no billing backend to hand the order to, so the ShopCashId doubles as
// the order id and TransactionEnd grants straight off it
...
if (request.EndType != BillingTransactionEndType.Success) return response;
var shopCash = ...FirstOrDefault(x => x.Id == request.PurchaseOrderId);
var product  = ...FirstOrDefault(x => x.Id == shopCash.CashProductId);
... BuildParcel(db, account, parcels, parcelResultDB);   // 直接进背包/货币
response.ParcelResult = parcelResultDB;
```

⇒ **29001 本身能发**，但两个问题：

1. **不发邮件**：`BuildParcel` 直接入账（道具/货币），不是 `Mails` 表。用户要的"邮件发放"它不满足。
2. **无幂等**：代码里**没有任何订单表/去重**，同 `ShopCashId` 调 N 次就发 N 次。

**两条幂等方案（二选一，我推荐 S1）**

**S1 · 桥侧短时去重（今天就能上，零 C# 改动）**

在 `account_auth_probe.py` 的 29001 转发前加一个内存过滤：

```python
# 伪代码，插在 post_gateway(req) 之前，针对 protocol_name == 'Billing_TransactionEndByYostar'
key = (publisher_id, str(req.get('PurchaseOrderId')))
now = time.time()
if key in _END_SEEN and now - _END_SEEN[key] < 900:      # 15 分钟窗口
    rec['end_dedup'] = 'hit'
    return self._json_ok(name, {'ParcelResult': {...空...}, 'CountList': [], ...})  # 不转发
_END_SEEN[key] = now
```

- 优点：不装 .NET SDK、不动 Shittim、当天可上；窗口内重复点击/重试都只发一次。
- 缺点：进程重启丢状态（可用 `/www/wwwroot/bapatch/state/end_seen.json` 落盘，或直接接受重启后重发一次）；跨进程/多实例无效（当前单进程，无碍）。

**S2 · Shittim 侧订单表（根治，但要装 .NET SDK）**

```sql
CREATE TABLE "BillingOrders" (          -- EF 实体 + 迁移
  "ServerId" INTEGER PRIMARY KEY AUTOINCREMENT,
  "AccountServerId" INTEGER NOT NULL,
  "ShopCashId" INTEGER NOT NULL,
  "OrderNo" TEXT,
  "CreatedAt" TEXT NOT NULL,
  UNIQUE("AccountServerId","ShopCashId")     -- 幂等键：按账号+商品只发一次
);
```

`TransactionEndByYostar` 里：先 `INSERT OR IGNORE`，`rows==0` 就返回空 `ParcelResult` 不再发货；否则照旧 `BuildParcel`。
- 优点：唯一约束是硬保证，重启/并发都安全。
- 缺点：要 `dotnet` SDK 构建（服务器只有运行时，`ADMIN_PANEL_SPEC.md:205-206`），且要改 DB schema。

> 建议路径：**S1 先上挡住重复点击；S2 等 admin API 那一期一起做**。

**关于"邮件发放"**：29001 走 `BuildParcel` 是"直发"。若必须走邮件，有两条路：
1. 在 S1 的桥侧**把 29001 拦下，改为写一封 `Mails`**（`ParcelInfos` JSON，见 `ADMIN_PANEL_SPEC.md:145-151`），并给客户端回一个空 `ParcelResult`；幂等用 S1 的键。**推荐**：满足"邮件+幂等+可追溯"，且不依赖客户端行为。
2. 放弃 29001，让 SDK `/order/create` 直接写 `Mails`；但客户端仍可能因 `BillingCheckPurchaseStateTask` 再发 29001，需要同时拦——复杂度更高。

### SDK-6 第一阶段：只加日志（补丁已就绪，**未上服务器**）

**改哪几行**（两处插入，不改任何现有行）：

| # | 位置 | 插入内容 | 行数 |
|---|---|---|---|
| 1 | `class H(BaseHTTPRequestHandler):` **之前** | `ORDER_LOG` 常量 + `_order_probe(handler, body)` 函数 | +52 |
| 2 | `body = self._body()` **之后** | `if self.path.startswith('/order'): _order_probe(self, body)` | +2 |

行为不变：探测完继续走原来的 if 链 → `/order/*` 仍落到 `:151` 的兜底 `200 {"Code":200,"Msg":"OK","Data":{}}`。

**本地端到端验证（已做）**：用 `work/ba/bapatch/sdkcard.py`（sha `afaec563…`）在 WSL 里跑通——

```
POST /order/create  -> {"Code": 200, "Msg": "OK", "Data": {}}      ← 与改前逐字节相同
POST /order/detail  -> {"Code": 200, "Msg": "OK", "Data": {}}      ← 同上
POST /user/login    -> 200（原有逻辑未受影响）
probe log 2 行：path/body_len/client/headers/body 全在
回滚后 sha 回到 afaec563…（逐字节一致）
```

**线上待执行**（`/www/wwwroot/ba_sdk/sdkcard.py`，live sha `5ba1b32c…`，与本地 v1 不同，故必须先 `--verify`）：

```bash
scp work/ba/server/deploy/_card/patch_order_probe.py root@<server>:/tmp/
python3 /tmp/patch_order_probe.py --src /www/wwwroot/ba_sdk/sdkcard.py --verify
python3 /tmp/patch_order_probe.py --src /www/wwwroot/ba_sdk/sdkcard.py --apply --expect-sha 5ba1b32c31d5ded3815db08149e06df270724007d5bee15f7682317707802bda
systemctl restart ba-sdk && sleep 2 && systemctl is-active ba-sdk
```

回滚（一行，脚本会打印实际备份名）：

```bash
cp -a /www/wwwroot/ba_sdk/sdkcard.py.probe.bak.<ts> /www/wwwroot/ba_sdk/sdkcard.py && systemctl restart ba-sdk
```

- 日志 `/www/wwwroot/ba_sdk/order_probe.log`，JSONL，字段：`ts/epoch/client/xff/real_ip/via/method/path/body_len/body_sha256/headers/body_text|body_b64`。
- 紧急关闭：`touch /www/wwwroot/ba_sdk/order_probe_off.txt`（不用重启、不用回滚代码）。
- 20 MB 自动轮转 `.1`。
- **行为不变**的证明方式：跑前后各打一次 `/user/quick-login` 与 `/order/create`，响应逐字节比对。

### SDK-7 Udata 关闭（只出方案）

**核实**：我们下发的 `/common/config` 就是抓下来的官方响应 `work/ba/bapatch/sdk_resp/common_config.json`（7589 B），其中：

```json
"ChannelConfig": {
  "Udata": { "Enable": true, "URL": "https://udata-api.open.yostar.net", ... }
}
```

`sdkcard.py:76-88` 的 `fix()` 只替换 4 个域名（`static/gs-api/sdk-api/www.baidu`），**不碰 `udata-api.open.yostar.net`** ⇒ 客户端拿到 `Enable:true` 就会去打官方 Udata。结论成立：**那条 passthrough 是 Udata 埋点，不是支付**。

**改法（推荐改数据，不改代码）**：

1. 备份：`cp -a /www/wwwroot/ba_sdk/sdk_resp/common_config.json{,.bak.<ts>}`
2. 就地改一个布尔：`"Udata": {"Enable": true` → `"Enable": false`（JSON 单行/多行均可，用 `python3 -c` 读改写，保证仍是合法 JSON）
3. 不需要重启（`sdkcard` 每次请求都 `json.load(open(CFG))`——`sdkcard.py:74`）
4. 验证：客户端重启后，`tcp-access.log` 里 `udata-api.open.yostar.net` 归零；`/common/config` 回包 `Udata.Enable=false`

**风险**：
- Udata 是埋点上报，关掉**不影响登录/支付/游戏**；最坏是厂商侧统计缺失（本地私服无意义）。
- 若客户端对 `Udata` 结构有强校验（未见证据），最坏是 SDK 初始化告警；可秒回滚。
- **不要**顺手改 `DetectionAddress` 里的 `sdk-api.yostar.cn`：它已被 `fix()` 改写成 `example.com`，动它反而可能引入探测失败。

---

## §X 建议的落地顺序（给 lead 的决策清单）

| 步 | 动作 | 前置 | 风险 | 判定成功的信号 |
|---|---|---|---|---|
| 0 | `Udata.Enable=false` | 无 | 极低（可秒回滚） | `tcp-access.log` 里 `udata-api.open.yostar.net` 归零 |
| 1 | **stage-1 probe 上线**（只加日志） | 确认手机走 relay | 零（行为不变） | `order_probe.log` 出现 1 行真实 `/order/create` |
| 2 | 用抓到的真实请求补 `products`/`create`/`detail`，`allow_pay=0` | 步 1 拿到 `ProductId/ExtraData/NotifyURL` 与成功 `Code` | 低（拒绝 = 现状） | 点购买 → 客户端弹「支付失败」，**没有 29001** |
| 3 | `pay.json` 试 `PayState/DeliveryState`（1/1 → 2/2 → 0/1） | 步 2 | 中（试错期间用户会看到失败弹窗） | 客户端发 **29001**，Shittim 发出 `ParcelResult` |
| 4 | `allow_pay=1` + **桥侧 15 分钟去重** | 步 3 | 中（唯一会真发奖的一步） | 同单点两次只到账一次 |
| 5 | 把 29001 改成"写 `Mails` + 空 `ParcelResult`"（邮件发放） | 步 4 | 中 | 邮件里收到附件，背包不加东西 |
| 6 | Shittim 侧 `BillingOrders` 唯一约束（根治幂等） | 装 .NET SDK | 低 | 重启/并发下仍只发一次 |

> 步 0/1 可以今天做；步 2–3 需要一次真机点击配合；步 4 之前**任何情况下都不要默认 `allow_pay=1`**。

---

## §SDK-8 执行记录（2026-11-17 20:22–20:33，云端）

### 8.1 目标判定：**云端 + 手机两份都打**

| 判据 | 结果 |
|---|---|
| 云端 `sdkcard.py` 监听 | `127.0.0.1:8080`（**只绑 loopback**，外网无法直连，必须经 nginx `/sdk/`） |
| 云端 `sdk.log` 今天 | 有 `17:20:02 dev=09a4…`，但**无对应 nginx `/sdk/` 记录** ⇒ 是**服务器本地 curl**（见 §SDK-9） |
| nginx `example.com.log` 的 `/sdk/` | 共 256 条，**UA=okhttp 的最后一条是 14/Nov 14:13:48**；17/Nov 全是 `curl/8.22.0` |
| 手机侧（phone-ops 20:22） | 8080 无监听；今天 10:17–11:24 跑的是**形态 A 本地 sdkcard.py**；无自启入口 |

⇒ 结论：**今天手机没走云端**。为了让"补丁客户端装回去之后"两种情况都能抓到，**两份都打探针**（云端已打，手机侧命令见 8.4）。

### 8.2 云端 stage-1（probe）执行记录

| 项 | 值 |
|---|---|
| 目标 | `/www/wwwroot/ba_sdk/sdkcard.py`（5,832 B，mode 0600） |
| old sha | `5ba1b32c31d5ded3815db08149e06df270724007d5bee15f7682317707802bda` |
| new sha / size | `12f32c0d795e11c7780b0b04fc83f273badcbd100e1233a5457841eb56aa7242` / 7,874 B |
| 备份 | `/www/wwwroot/ba_sdk/sdkcard.py.probe.bak.20261117-202325` |
| 重启 | **`systemctl restart ba-sdk`**（⚠️ 不是 pm2；unit `/etc/systemd/system/ba-sdk.service`，`Restart=always`） |
| 验证 | `/order/create`、`/order/products` 回包与改前逐字节相同；`order_probe.log` 落盘含 `path/body_len/body_sha256/headers/body_text` |
| 回滚 | `cp -a …probe.bak.20261117-202325 /www/wwwroot/ba_sdk/sdkcard.py && systemctl restart ba-sdk` |

### 8.3 云端 stage-2（三端点）执行记录

| 项 | 值 |
|---|---|
| old sha | `12f32c0d…`（stage-1 后） |
| new sha / size | `ed2053dc9de1062565491a1af036610a13bd96be04e5717de04985aac496704e` / 13,328 B |
| 备份 | `/www/wwwroot/ba_sdk/sdkcard.py.order_ep.bak.20261117-202757` |
| 重启 | `systemctl restart ba-sdk` → active，MainPID `2632769`，`LISTEN 127.0.0.1:8080` |
| 回滚 | `cp -a …order_ep.bak.20261117-202757 /www/wwwroot/ba_sdk/sdkcard.py && systemctl restart ba-sdk` |

自测原文（服务器上，20:29–20:30）：

```
D1 默认拒绝（无 allow_pay.txt）
   /order/create -> {"Code": 40007, "Msg": "PAY_DISABLED", "Data": null}
D2 回归
   /heartbeat/pulse      -> {"Code":200,"Msg":"OK","Data":{"Delay":3600}}
   /health-game/duration -> {"Code":110170,"Msg":"用户已成年,不需要计时","Data":{}}
   /common/geo-ip        -> {"Code":200,"Msg":"OK","Data":{"Prov":"浙江省"}}
   /user/quick-login     -> 200（模板正常）
   /common/config        -> 200（7,838 B）
D3 pay.json 写入 {"PayState":2,"DeliveryState":2,"Amount":3000} 后仍拒绝
   /order/create -> {"Code": 40007, "Msg": "PAY_DISABLED", "Data": null}
D4 改文件即生效（不重启）：pay.json 加 "fail_code":40008
   /order/create -> {"Code": 40008, ...}      ← 立即生效
   改回 40007    -> {"Code": 40007, ...}
D5 probe 关闭开关
   7 行 -> touch order_probe_off.txt -> 仍 7 行 -> rm -> 8 行
```

### 8.4 手机侧（PRoot）probe 补丁 —— **已打（phone-ops 20:33 执行）**

| 项 | 值 |
|---|---|
| REAL | `/root/bapatch/sdkcard.py`（proot link2symlink 下 `readlink -f` 返回自身，真身被映射成普通文件） |
| old sha / size | `afaec5637c63c56093a677fe4255d5d6a31af6101b475a5928d719a3d6d819ae` / 5,814 B |
| new sha / size | `8e3a12e89fb502cfce8f4bc4ceaa277e3457ed2cc3a4142fed96485651c7231a` / 7,844 B |
| 备份 | `/root/bapatch/sdkcard.py.probe.bak.20261117-123350`（5,814 B，属主已一并改回 10489） |
| 自检 | `--verify` 前后各一次 PASS；`py_compile` COMPILE_OK |
| 回滚 | `cp -a /root/bapatch/sdkcard.py.probe.bak.20261117-123350 /root/bapatch/sdkcard.py` |
| 紧急关闭 | `touch /root/bapatch/order_probe_off.txt` |
| 当前状态 | **8080 未启动**、游戏未运行（`ss -lntp | grep ':8080 '` 为空），等 v2 装好再起 |

**两个实机坑（已复现，写进流程）**

1. **proot 必须带 `-b` 绑定**，否则 `/data/local/tmp` 不可见、且 `--link2symlink` 的 `/root/bapatch/sdkcard.py` 会变成悬空链接（`ls` 看得到、`sha256sum` 报 No such file）。可用命令（phone-ops 实测）：
   ```bash
   PROOT=/data/user/0/com.ai.assistance.operit/files/usr/bin/proot
   ROOTFS=/data/user/0/com.ai.assistance.operit/files/usr/var/lib/proot-distro/installed-rootfs/ubuntu
   OPER=/data/user/0/com.ai.assistance.operit
   "$PROOT" -0 -r "$ROOTFS" --link2symlink -b /dev -b /proc -b /sys -b /dev/pts \
     -b /proc/self/fd:/dev/fd -b /storage/emulated/0:/sdcard -b /storage/emulated/0 -b /data/local/tmp \
     -b "$OPER" -b "$OPER:/data/data/com.ai.assistance.operit" -b "$OPER/files" -w /root \
     /usr/bin/env -i HOME=/root TERM=xterm-256color LANG=en_US.UTF-8 \
     PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin /bin/bash -lc '<cmd>'
   ```
2. **补丁会把文件属主改成 root:root**（脚本以 root 跑 + `os.replace` 建新文件）⇒ 用应用用户（10489）启动会 Permission denied。phone-ops 已手工 `chown 10489:10489`。**脚本已修复**：`write_atomic` 现在 `copymode` → `chown` → 再 `chmod(st_mode & 0o7777)` 兜底（`hasattr(os,'chown')` 保护，Windows 下自动跳过）。
3. **权限/属主校验三件套**（phone-ops 现场经验，已实测）：`ls -ln <file>` 看 uid/gid、`stat -c %a <file>` 看 mode、`sha256sum` 对比 old/new。
   本次确认：`/root/bapatch/sdkcard.py` = **10489:10489 / 600 / 7,844 B**（组名显示 `android_group_10489`，即 gid 10489）；备份 `…probe.bak.20261117-123350` 同为 10489:10489 / 600 / 5,814 B。
   本地回归：把源文件设成 `640` 后跑 apply/rollback，模式下**全程保持 640**（`mkstemp` 默认 0600，故必须有 chmod 兜底）。

> 手机侧只打 **stage-1（只记录）**；三端点仍只在云端实现。v2 走公网域名直连云端，这一份只对"回退到本机 sdkcard"有用（保留、不着急）。

### 8.5 `Udata.Enable=false`（已执行）

| 项 | 值 |
|---|---|
| 文件 | `/www/wwwroot/ba_sdk/resp/common_config.json`（7,589 B，注意不是 `sdk_resp/`） |
| before | sha `ee713d8abfe9d5d66a55e75490edbeb0c036539b104876c552d36062ec3264a2`，`Udata.Enable=true`，`URL=https://udata-api.open.yostar.net` |
| after | sha `ca6c98dff20def8f3b6929348ff505124f775b6a0a305aebf0837551c37289ee`，`Enable=false`，URL 不变 |
| 生效 | **无需重启**（`sdkcard.py:74` 每请求 `json.load(open(CFG))`）；实测 `/common/config` 回包 `Data.ChannelConfig.Udata.Enable=False` |
| 备份 | `/www/wwwroot/ba_sdk/resp/common_config.json.bak.20261117-203121` |
| 回滚 | `cp -a /www/wwwroot/ba_sdk/resp/common_config.json.bak.20261117-203121 /www/wwwroot/ba_sdk/resp/common_config.json` |

风险：仅埋点上报缺失，不影响登录/支付/游戏；若客户端对 Udata 有强校验（无证据），秒回滚。

---

## §SDK-9 判据：手机到底走云端还是 PRoot 本地（可复现）

**先纠正我自己**：我此前据"云端 `sdk.log` 有今天 17:20 带 `dev=` 的记录"推断"手机走 relay"——**错了**。

**为什么错**：`sdk.log` 的行格式是 `HH:MM:SS path dev=…`，**没有日期、没有客户端 IP**，而 `dev=` 任何 curl 都能伪造。它只能证明"有人调过"，不能证明"手机调过"。

**三条可复现判据（按强度）**

1. **绑定面（最强，一次性）**：云端 `ss -lntp | grep 8080` → `127.0.0.1:8080`。**只绑 loopback ⇒ 外网/手机不可能直连**，任何到达 sdkcard 的请求只能来自（a）服务器本机进程，或（b）nginx `/sdk/` 反代。所以只要查 nginx 有没有对应记录即可。
2. **nginx access（逐请求）**：
   ```bash
   grep '/sdk/' /www/wwwlogs/example.com.log | grep 'okhttp' | tail
   ```
   - 有 `POST /sdk/...` 且 UA=`okhttp/4.9.2` ⇒ 真实客户端（relay 或直连）来过；
   - 只有 `curl/*` ⇒ 是测试，不是手机。
   本次结果：**UA=okhttp 的最后一条是 `14/Nov/2026:14:13:48`**，17/Nov 全是 curl ⇒ **今天手机没走云端**。
3. **手机侧（逐请求）**：`ss -tnp | grep 443` 看对端是否 `example.com` 的 IP；或看 proot 内 `relay.log` / `sdk.log` 的 mtime。今天手机 proot `sdk.log` 末行 `11:24:39`。

**结论（钉死）**：**今天手机走的是 PRoot 本地（形态 A），10:17–11:24 有记录，之后停；云端 17:20 那两条是服务器本地 curl。** 以后判"走哪条路"只看判据 2（nginx okhttp），不要看 `sdk.log`。

---

## §SDK-10 硬前置：没装补丁客户端之前，任何付费操作都是真实交易

现役客户端是**官方包**（`libil2cpp.so` = factory `5ac1cbe0…`，prefs 里搜不到 `127.0.0.1:8080`），`sdk_url` 仍指官方 ⇒ 点付费 = 打开官方「优星网络」收银台，**我们一行日志都拿不到**。

因此：

1. **未装补丁客户端时，禁止让用户点任何付费按钮**（会真实下单）。
2. 装回补丁包 + 起 8080 之后，才允许做 `/order/create` 的真实抓包。
3. 抓包成功的判据：`order_probe.log` 出现 1 行 `path=/order/create` 且 `client` 非 `127.0.0.1`（relay 场景下为 127.0.0.1，因为 relay 在本机——此时看 `headers.Authorization` 里的真实 DevId 即可）。

---

---

## §SDK-11 商品映射表：`ShopCashId` ↔ SDK `ProductId`

### 11.1 先把两个 id 的真实来源钉死

| id | 类型 | 来源 | 证据 |
|---|---|---|---|
| `ShopCashId` | long | `ShopCashExcel.Id`（游戏 Excel） | `BillingHandler.cs:174`：`GetTable<ShopCashExcelT>().FirstOrDefault(x => x.Id == request.PurchaseOrderId)` |
| `CashProductId` | long | `ShopCashExcel.CashProductId` → `ProductExcel.Id` | `BillingHandler.cs:175` |
| `ProductExcel.ProductId` | **string** | 官方商店 SKU（App Store / Google Play / 渠道商品号） | `ProductExcel.cs:6`（`public string ProductId`） |
| SDK `ProductId` | int | **我们自己的命名空间**，只出现在 `/order/create` 请求与 `/order/products` 响应里 | `OrderCreateReq.ProductId`（int）、`OrderProductsEntity.ProductItems.ID`（int） |

⇒ **`ProductId`(int) 与 `ShopCashId`(long) 没有任何天然推导关系**；`ProductExcel.ProductId` 是字符串（官方 SKU），也不能直接当 SDK 的 int 用。所以必须自建映射。

### 11.2 表结构（MySQL `ba_cardadmin`，与卡密同库，复用审计/备份）

```sql
CREATE TABLE IF NOT EXISTS sdk_products (
  product_id    INT UNSIGNED NOT NULL,              -- 下发给 SDK 的 int
  shop_cash_id  BIGINT UNSIGNED NOT NULL,           -- ShopCashExcel.Id
  name          VARCHAR(128) NOT NULL DEFAULT '',   -- 面板显示名
  localize_id   INT UNSIGNED NOT NULL DEFAULT 0,    -- ShopCashExcel.LocalizeEtcId（本地化 key）
  price_cents   INT UNSIGNED NOT NULL DEFAULT 0,    -- 展示价（分）
  use_mail      TINYINT(1) NOT NULL DEFAULT 0,      -- 抄 ShopCashExcel.UseMailParcel
  enabled       TINYINT(1) NOT NULL DEFAULT 1,
  source        VARCHAR(16) NOT NULL DEFAULT 'manual', -- manual/probe/excel
  note          VARCHAR(255) NOT NULL DEFAULT '',
  created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (product_id),
  UNIQUE KEY uk_shop_cash (shop_cash_id),
  KEY idx_enabled (enabled)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

**默认约定：`product_id = shop_cash_id`（若 `shop_cash_id < 2^31`）。** 理由：客户端若把 `ShopCashId` 原样当 `ProductId` 传（完全可能），这条默认就能命中；超过 int 范围再另编号。

### 11.3 数据从哪来（三条，按可靠性排序）

| 来源 | 给什么 | 怎么取 | 注意 |
|---|---|---|---|
| **A. 真实 probe 日志**（最高） | 客户端实际发的 `ProductId`、`ExtraData`、`PayType` | `/www/wwwroot/ba_sdk/order_probe.log`（JSONL） | 唯一能证明"客户端真的用这个 id"的来源；`ExtraData` 很可能带 `ShopCashId`，需实测 |
| **B. ShopCashExcel** | `Id`、`CashProductId`、`LocalizeEtcId`、`UseMailParcel`、`PackageType`、`DisplayOrder` | FlatBuffers；字段名见 `Schale/FlatData/ShopCashExcel.cs` | 需要读 ExcelDB（SQLCipher，`UseCustomExcel=true`），成本高 |
| **C. ProductExcel** | `Id`、`ProductId`(string)、`StoreType`、`Price` | 同上，`ProductExcel.cs` | `Price` 是 long（分？），以官方为准 |

**推荐落地顺序**：**A 先行，B/C 只做只读补全**。因为 `ProductId` 是我们自己的命名空间，Excel 里根本没有这个 int；把 Excel 全量导进来也解决不了映射，只会增加维护面。

### 11.4 填充脚本方案（不建表，先给流程）

```
1) 从 probe 日志抽候选
   python3 tools/extract_probe_products.py /www/wwwroot/ba_sdk/order_probe.log
   -> 输出 candidates.csv: product_id, extra_data, pay_type, first_seen, count

2) 只读导出 Excel 参考（可选，需 SQLCipher key）
   python3 tools/dump_shopcash.py --db <ExcelDB> --key <Config.json 里的 ExcelDbSqlCipherKey>
   -> shopcash.csv: shop_cash_id, cash_product_id, localize_id, use_mail_parcel, display_order
      product.csv:    product_excel_id, product_id_str, store_type, price

3) 人工确认（面板"商品"页）：把 candidates 的 product_id 绑到 shopcash 行
   -> INSERT/UPDATE sdk_products ... source='probe'/'manual'

4) 导出给 SDK（不引 MySQL 依赖）：
   SELECT product_id, name, price_cents FROM sdk_products WHERE enabled=1;
   -> /www/wwwroot/ba_sdk/products.json（sdkcard 启动/每次请求时读，格式同 pay.json 的 products 数组）

5) 回填校验：/order/products 回包必须与 products.json 逐字段一致。
```

> `Price` 与 `Amount` 的关系：SDK `Order.Amount` 目前由 `pay.json` 的 `Amount`（固定 3000）或 `price_x100` 决定；先用固定值跑通链路，再换成真实价。

### 11.5 与"邮件发放"的关系

`ShopCashExcel` 里**本来就有 `UseMailParcel` / `InMailPurchaseLock`** 两个字段（`ShopCashExcel.cs:14-16`），说明官方商品本身区分"直发/邮件"。当前 `BillingHandler.TransactionEndByYostar` **没有读这两个字段**，一律 `BuildParcel` 直发。

⇒ 若要满足用户"通过邮件发放"，两条路：
1. 在 29001 的处理里尊重 `UseMailParcel`（改 C#，需 .NET SDK）；
2. 或在桥侧拦 29001，统一写 `Mails`（Python，当天可做）。
本项目建议 **2**（与 §SDK-5 一致）。

---

## §SDK-12 `allow_pay=1` 验收清单（用户装完 v2 后一次跑完）

> **总前置**：① v2 已装、`sdk_url = https://example.com/sdk`（判据见 12.0）；② 手机 8080 在跑（A/B 均可，B 会落到云端）；③ `allow_pay.txt` **不存在**（当前安全态）；④ 记录基线：`wc -l /www/wwwroot/ba_sdk/order_probe.log`。

### 12.0 先证明"这次真的走我们"（30 秒）

```bash
tail -5 /www/wwwroot/ba_sdk/sdk.log          # 应出现刚刚的 /common/config、/user/quick-login
grep '/sdk/' /www/wwwlogs/example.com.log | tail -3   # UA 应是 okhttp/4.9.2，不是 curl
```
- 两条都对 ⇒ 客户端确实打到我们；任一不对 ⇒ 停，先解决 sdk_url/8080，不要往下走。

### 12.1 **基线：拒绝态点一次（最重要的一步）**

| 项 | 期望 | 失败判据 → 处置 |
|---|---|---|
| 点付费礼包 | 客户端弹支付失败/无法拉起 | 若弹出「优星网络」真收银台 ⇒ **立刻停**，客户端仍在走官方 |
| `order_probe.log` | **新增 1 条 `path=/order/create`** | **0 条 ⇒ 支付流程根本不调用 SDK `/order/create`** ⇒ 放弃 SDK 方案，转"29000 直接发货"（§SDK-5 路线 S2/audit 路线①） |
| `sdk.log` | 新增 `/order/create` 行 | 同上 |
| 桥日志 `api_all_requests.log` | 只有 29000，**无 29001** | 有 29001 反而异常（还没允许支付） |

> 这一步是整个方案的分水岭：**`/order/create` 到底会不会被调用，只有这次点击能回答。**
> 如果答案是"不会"，请把本节的结论改成"SDK 侧假支付不成立"，并立即转 Shittim 29000 发货路线。

**一条命令判定（已就绪，`check_order_probe.py` 已放到 `/www/wwwroot/ba_sdk/check_order_probe.py`）**

```bash
# 点击前先记下时刻（可选，用于精确窗口）
date +%s > /tmp/click_t0

# 用户点完之后（建议 30 秒内）执行：
python3 /www/wwwroot/ba_sdk/check_order_probe.py --minutes 5
echo "rc=$?"
```

判读：

| 输出 | 含义 | 处置 |
|---|---|---|
| `ORDER_CREATE_SEEN=YES` + `VERDICT=SDK_ORDER_ROUTE_ALIVE`（rc=0） | 客户端确实调了 `/order/create` | 继续 12.2 |
| `ORDER_CREATE_SEEN=NO` + `VERDICT=SDK_ORDER_ROUTE_NOT_CALLED`（rc=3） | 没调 | **停**，转 29000 直发路线 |
| `LOG_MISSING` / `VERDICT=UNKNOWN`（rc=2） | 补丁没生效或路径不对 | 先查 `ls -l /www/wwwroot/ba_sdk/order_probe.log` 与 `/www/wwwroot/ba_sdk/sdk.log` |

时间窗怎么界定：`--minutes 5` 取"最近 5 分钟"，足够覆盖"点一下 + 30 秒反应"；若怕噪音，用 `--since $(cat /tmp/click_t0)` 精确到秒。脚本按 `epoch` 字段过滤（不是按字符串），并会打印命中样本的 `client / auth / body` 便于确认是真实客户端而非 curl。

### 12.2 打开允许

```bash
printf '%s\n' '{"PayState":2,"DeliveryState":2,"Amount":3000}' > /www/wwwroot/ba_sdk/pay.json
echo 1 > /www/wwwroot/ba_sdk/allow_pay.txt          # 立即生效，无需重启
curl -s -XPOST 127.0.0.1:8080/order/create -d '{"ProductId":1597}'
# 期望：{"Code":200,...,"Order":{"PayState":2,"DeliveryState":2,...}}
```

### 12.3 再点同一个礼包

| 观察点 | 期望 | 失败判据 → 下一步 |
|---|---|---|
| 客户端 | 不再拉起官方收银台，直接"支付成功/发货中" | 仍拉官方 ⇒ `PayState/DeliveryState` 没被读；试 `1/1`、`0/1`（改 pay.json，秒生效，重试） |
| `order_probe.log` | 第 2 条 `/order/create` | — |
| 桥日志 | **10 秒内出现 29001** | 30 秒无 29001 ⇒ 客户端不认这笔订单 ⇒ 继续试 state 组合；三种都不行 ⇒ 回退 12.6 |
| Shittim | 29001 返回 `ParcelResult` 非空 | 空 ⇒ 查 `ShopCashId` 是否正确（看 29000 请求的 `ShopCashId`） |
| 游戏内 | 道具/货币到账（当前是直发，不是邮件） | 未到账 ⇒ 看 `Mails`/背包表与 29001 响应体 |

### 12.4 邮件发放（第二阶段，需先做桥侧改造）

当前 29001 是 `BuildParcel` 直发。要变成邮件：
- 桥侧拦 29001 → 写 `Mails`（`ParcelInfos` JSON，`Type=13`，`SendDate=now`）→ 回空 `ParcelResult`；
- 或在 Shittim 侧按 `ShopCashExcel.UseMailParcel` 分流（需 .NET SDK）。
- 验收：邮件列表出现带附件的邮件；背包不直接增加；重复请求只发一封。

### 12.5 幂等验收（**已不算阻塞：去重已上线**）

srv-ops 批次 1 已部署 `cn_dedup=1`，窗口 **900 s**；实测同单第二次请求 **283 ms → 3 ms**、`dedup_hit=True`、响应逐字节相同；去重键实测为 `Billing_TransactionEndByYostar|PurchaseOrderId=1597`。

| 动作 | 期望 | 说明 |
|---|---|---|
| 连点两次同一个礼包 | 只到账一次 | 去重已在桥侧生效；第二次应在毫秒级返回且不发奖 |
| 间隔 >15 分钟后重放同一单 | 会再发（窗口外） | 这是设计取舍；要更强保证再加 Shittim 订单表（S2） |

⇒ `allow_pay=1` 现在可以直接测，不必先去重；但**每次测完仍要 `rm allow_pay.txt`**。

### 12.6 立即回滚（任何一步不对）

```bash
rm -f /www/wwwroot/ba_sdk/allow_pay.txt      # 立刻回到"拒绝支付"，无需重启
cp -a /www/wwwroot/ba_sdk/sdkcard.py.order_ep.bak.20261117-202757 /www/wwwroot/ba_sdk/sdkcard.py && systemctl restart ba-sdk
```

### 12.7 关于 `PayState/DeliveryState` 的候选值

未知常量，按 `2/2 → 1/1 → 0/1` 顺序试（每轮：改 `pay.json` → 点一次 → 看 10 秒内有无 29001）。记录每轮结果，形成"值 → 客户端反应"对照表，写回本节。

---

## §SDK-13 v2 产物核验（**v1 已作废**）

| 项 | 值 |
|---|---|
| 正式产物 | `work/ba/server/deploy/_noroot/apk/BA_noroot_v2.apk` |
| 大小 | **2,127,971,177 B**（与 lead 给的一致） |
| sha256（lead 侧） | `682A9EA20DD9C9EC955454ACD937E2A8C002F13EC7B6B1307112B3C61D4EA2EC` |
| **我直接读包内 `assets/SDKConfigSettings.json`** | `sdk_url = https://example.com/sdk`（2,843 B，STORED）**逐字符一致** |

⇒ **v2 会走云端**：所有 SDK HTTP（含 `/order/*`，若客户端会调）都会 `https://example.com/sdk/...` → 宝塔 `location /sdk/` → `127.0.0.1:8080` 的 `sdkcard.py`。**云端那份就是 v2 的目标**。

> **v1 作废**：`work/ba/noroot/BA_noroot_v1.apk` 的 `sdk_url` 仍是 `https://sdk-api.yostar.cn`（构建时没传 `--sdk-url`，`build_noroot_apk.py:1479` 的 `if sdk_url:` 不成立）。**标注：废弃产物，勿装机、勿用于任何结论。**

> 顺带纠正：`_noroot/NOROOT_AUDIT_20261117.md §4.2` 用"20:00 支付流量去了官方"推出"支付不跟 `sdk_url` 走"。但那次装机的是**官方包**，`sdk_url` 本来就指官方 ⇒ **该证据不能否定"v2 走云端"**，也不能肯定它——**只有 12.1 那次点击能定案**。lead 已让 ca-researcher 改该段。



## §Z 现场证据（srv-ops，2026-11-17 20:17–20:18，只读；以下 sdkcard sha 为补丁前）

```
LISTEN 127.0.0.1:8080  python3 pid=26781  /www/wwwroot/ba_sdk/sdkcard.py   (运行 3d19h)
LISTEN 0.0.0.0:8081    nginx                 （PHP 卡密站）
LISTEN 127.0.0.1:9097  python3 account_auth_probe.py
sha256 sdkcard.py       = 5ba1b32c31d5ded3815db08149e06df270724007d5bee15f7682317707802bda
sha256 probe.py(桥)     = ade3917cab391de3d782decbdceda1d71556a9ee7e2487be869afebcd2f73807
POST /auth/verify       -> {"Code":200,"Msg":"OK","Data":{}}     ← 兜底，端点不存在
cards.json              = 1 张卡 11111111111  devices=1 expire=0 bind_one=false  (189 B)
MySQL cards             = 1 行  bind_one=0  expire_at=0  AUTO_INCREMENT=4
桥 UID/TOKEN            = 314816420 / 61de1d1b…（L164-166 硬编码）
桥 BAPATCH-MU 标记      = 0；cn_multiuser.txt / cn_auth_enforce.txt 均不存在
sync.log                = [20:17:10] 同步成功：1 个卡密，189 B
```

---

## §Y 仍需确认（写进结论前必须回填）

1. **线上桥有没有 `account_service` 分流**：live sha `ade3917c…` 与本地任何一版都不匹配；若含 `acct_svc`（且 `cn_account_svc.txt` 缺失时默认 **开**），"共号"要改成"已分流但 token 仍不验"。已请 `srv-ops` 补 4 条 grep（未回）。
2. ~~手机走形态 1 还是形态 2~~ → **已定**：今天走 PRoot 本地（§SDK-9），云端 17:20 是本地 curl；两份都打探针（云端已完成，手机待 phone-ops）。
3. **`/order/create` 真实请求**：**阻塞**——需先装回补丁客户端（§SDK-10）；当前装上的是官方包，点了会真进官方收银台。
4. **`PayState`/`DeliveryState` 真值**：`pay.json` 已可热改（实测 `fail_code` 40007→40008→40007 未重启），等真实请求后试 1/1、2/2、0/1。
5. **`Code` 成功值**：同样是配置项（`ok_code`），等真实响应样本对齐。

---

## 附：本文引用的文件与行号

| 内容 | 路径:行 |
|---|---|
| 卡密表结构 | `work/ba/cardadmin_php/sql/schema.sql:47-65` |
| 同步只导出 3 字段 | `work/ba/cardadmin_php/inc/sync.php:199-200` |
| 同步 cron | `work/ba/cardadmin_php/cron/sync_cards.php:17` |
| token 公式 / User.ID | `work/ba/bapatch/sdkcard.py:42-48` |
| 7 条真路由 / 兜底 | `work/ba/bapatch/sdkcard.py:73-151` |
| 卡密 v2（未部署） | `work/ba/sdk/sdkcard_v2.py:157-159,498-554,611` |
| 桥硬编码身份 | `account_auth_probe.py:164-166,1063-1077,1760` |
| 多用户服务"Token 只做记录" | `work/ba/server/account_service.py:34` |
| 29001 发货实现（无幂等） | `work/ba/srv_src/Shittim-Server/Core/NetworkProtocol/Handlers/BillingHandler.cs:148-213` |
| Billing 协议号 | `work/ba/srv_src/Schale/MX/NetworkProtocol/ProtocolData.cs:290-298` |
| 管理站施工图 | `work/ba/server/deploy/ADMIN_PANEL_SPEC.md:87-121,184-210,233-243` |
| SDK 同源结论 | `work/ba/server/deploy/_sdk/SDK_SAMENESS_20261117.md:96-140` |
| 第一阶段补丁 | `work/ba/server/deploy/_card/patch_order_probe.py` |
