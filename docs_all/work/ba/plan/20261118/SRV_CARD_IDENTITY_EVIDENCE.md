# SRV_CARD_IDENTITY_EVIDENCE — 卡密 → 账号映射取证（2026-11-18 03:2x）

> 只读取证。未重启任何服务、未改数据库、未改任何文件、未建账号/卡密、未调用任何会写 cards.json 的端点。
> db 全部用 `sqlite3` 只读打开（`file:...?mode=ro&uri=True`）。日志中的卡密/设备号均脱敏为「前4****后4」或 `sha8=`。

## 0. 结论摘要（三行）

1. **现网实际是「一机一账号」，不是「一卡一账号」。** 决定性证据：`api_all_requests.log` 中 03:00–03:21 的 5 次 `Account_Auth`，`req_devid_sha8` **全部 = a424da70（len=9）**、`req_DeviceUniqueId` sha8 全部 = `cae2cbea`，`acct_server_id` 全部 = `10000000000`、`acct_id_src=exact`。
2. **SDK 侧还有一个独立缺陷**：`/user/quick-login` 遍历 `cards.json` 返回「第一张 devices 里含本机的卡」；两张卡都含同一设备，而卡 A 在 JSON 中索引 0 ⇒ 永远返回卡 A。
3. **桥侧没问题**：身份链路自 02:42 起是 `req_devid_src=fragment` / `acct_id_src=exact`，DevId 来自客户端明文，命中既有账号，没有新建、没有 retarget。

---

## 1. 文件指纹（只读）

| 路径 | 字节 | md5 | mtime | 说明 |
|---|---|---|---|---|
| `/www/wwwroot/ba_sdk/sdkcard.py` | 14,940 | `d90546d6f8265e8d56b7d7bff97f5410` | 2026-11-18 01:01:37 | 线上 SDK（F1–F3 版） |
| `/root/bapatch/sdkcard.py` | — | — | — | **不存在**（`find` 只找到 `/www/wwwroot/ba_sdk/`、备份目录、`/tmp/upload/`） |
| `/www/wwwroot/bapatch/tools/account_auth_probe.py` | 164,514 | `7d4d162516c2ac1dd6b140bb6a01779b` | 2026-11-18 02:38:42 | 桥 v3（含 identity 诊断字段） |
| `/www/wwwroot/bapatch/tools/account_service.py` | 106,139 | `436cba4df30e503212c2e737bf2f9f0c` | 2026-11-18 02:17:05 | 账号服务（realdb 真值版） |
| `/www/wwwroot/ba_sdk/cards.json` | 391 | `bea9b93fd75222b65439b27a90825e3e` | 2026-11-18 03:25:01 | 卡密表（2 张卡） |
| `/www/wwwroot/bapatch/data/accounts.db` | 143,360 | `dcd02599237d940be80f8e14d5cb7836` | 2026-11-18 03:20:58 | 桥账号库（3 行） |
| `/www/wwwroot/ba_sdk/sdk.log` | 102,489 | — | 2026-11-18 03:25 | SDK 日志 |

命令：`stat -c %s` / `md5sum` / `find / -maxdepth 6 -name ...`。

---

## 2. SDK 日志：换卡密之后紧接着发生了什么

数据源：`/www/wwwroot/ba_sdk/sdk.log`（最近 200 行 + 全量 LOGIN/QUICK 事件），
`sdkcard.py:387` 写 `LOGIN OK`、`:397` 写 `QUICK OK`、`:375` 写 `LOGIN REJECT unknown card`、`:383` 返回「卡密已绑定其他设备」。

关键序列（行号来自 `grep -n`，卡密已脱敏）：

```
 984: QUICK OK 1111****1111 _mask(dev)=ce8f****fb36(len=16)
1068: QUICK OK 1111****1111 _mask(dev)=ce8f****fb36(len=16)
 ...
2746: QUICK OK 1111****1111 _mask(dev)=ce8f****fb36(len=16)
2806: QUICK OK 1111****1111 _mask(dev)=ce8f****fb36(len=16)
2835: LOGIN OK 1111****1111 _mask(dev)=ce8f****fb36(len=16)
2985: LOGIN REJECT unknown card 1222****2222(len=11)
2990: LOGIN REJECT unknown card 1222****2222(len=11)
3004: LOGIN REJECT unknown card 1222****2222(len=11)
3010: LOGIN REJECT unknown card 1222****2222(len=11)
3015: LOGIN REJECT unknown card 1222****2222(len=11)
3024: LOGIN REJECT unknown card 1222****2222(len=11)
3043: LOGIN OK 1222****2222 _mask(dev)=ce8f****fb36(len=16)     ← 新卡密 B 首次成功
3105: LOGIN OK 1222****2222 _mask(dev)=ce8f****fb36(len=16)     ← B 再次成功
3131: LOGIN OK 1111****1111 _mask(dev)=ce8f****fb36(len=16)     ← 下一次登录又回到 A
```

同设备号 `dev=ce8ffeb7d08cfb36`（len=16）贯穿全部记录。带时间戳的旁证：
```
3129: 03:20:57 /user/login   dev=ce8ffeb7d08cfb36
3132: 03:20:57 /user/detail  dev=ce8ffeb7d08cfb36
```

**判定（对应你要求的“重点标出”）**：
- 用户输入新卡密 B（`1222****2222`）之后，**紧接着确实出现过 `LOGIN OK B`（3043、3105）**，
  但此后客户端走 `quick-login` 时，SDK 返回的仍是 **`QUICK OK A`**（全表 20+ 次 `QUICK OK 1111…`，`QUICK OK 1222…` **0 次**），
  下一次显式 `/user/login` 也回到 A（3131）。
- **`1222****2222` 在 2985–3024 有 6 次 `LOGIN REJECT unknown card`** —— 说明那几次是「卡还没写入 cards.json 时用户就试了」，
  之后 3043 才成功 ⇒ 卡 B 建好后确实能登录，但**领不到自己的身份**。

---

## 3. cards.json 结构（卡密脱敏）

文件结构：`{"cards": {"<卡密>": {"devices": [...], "expire": 0, "bind_one": false}, ...}}`（顶层 `cards` 下按插入顺序）

| JSON 索引 | 卡密（脱敏） | devices 个数 | devices（len/sha8） | expire | bind_one | kind / max_devices |
|---|---|---|---|---|---|---|
| **0** | `1111****1111` | **2** | `len=16 sha8=952138bd`、`len=16 sha8=69ab71d6` | 0 | false | **无此字段** |
| **1** | `1222****2222` | **1** | `len=16 sha8=69ab71d6` | 0 | false | **无此字段** |

**⇒ 两张卡共享同一设备 `sha8=69ab71d6`（= `ce8ffeb7d08cfb36`），且卡 A 索引为 0。**

SDK 侧 `User.ID`（`sdkcard.py:89`：`md5(card)[:8] % 900000000 + 100000000`）：

| 索引 | 卡密 | User.ID | `User.Token` |
|---|---|---|---|
| 0 | `1111****1111` | **314816420** | `sha256(card|device)[:40]`（随卡+设备变化） |
| 1 | `1222****2222` | **854071516** | 同上 |

**注**：`314816420` 正是桥库 `publisher_account_id` / `dev_id` 的值 —— 即**卡 A 的 User.ID 被客户端当成了 DevId**。

---

## 4. accounts.db（只读）

`.tables` → `account_blobs, accounts, id_alloc, protocol_log, schema_meta, sessions`

`accounts` schema 要点（`STRICT` 表）：
```
server_id INTEGER PK CHECK (server_id >= 10000000000)
dev_id TEXT NOT NULL            -- Account_Auth.DevId，主身份键
device_unique_id TEXT NULL
sdk_token TEXT NULL             -- 轮换，不鉴权
publisher_account_id INTEGER NOT NULL DEFAULT 0
nickname/call_name/level/exp/... login_count/last_login_at
```

行数 = **3**：

| server_id | publisher_account_id | dev_id | device_unique_id | login_count | last_login_at |
|---|---|---|---|---|---|
| 10000000000 | 314816420 | len=9（= `314816420`） | len=32 sha8=cae2cbea | **52** | 2026-11-18T03:20:58 |
| 10000000001 | 1013178778 | len=10 | len=32 sha8=67809fc0 | 78 | 2026-11-18T00:18:45 |
| 10000000002 | 999888777 | len=9 | len=16 sha8=4619df35 | 1 | 2026-11-17T20:28:38 |

桥侧 `Account_Auth` 记录（03:00–03:21，5 条）：
```
t=03:06:08  server_id=10000000000  acct_id_src=exact  req_devid_sha8=a424da70 len=9  devuid_sha8=cae2cbea
t=03:09:05  同上
t=03:17:29  同上
t=03:20:08  同上
t=03:20:58  同上
```
**⇒ 5 次登录（期间用户换过卡密）DevId 与 DeviceUniqueId 完全不变，全部精确命中同一个账号 10000000000。**

---

## 5. nginx 路由：换卡密时打到哪个进程

`/www/server/panel/vhost/nginx/example.com.conf`：
```
162: location ... /sdk/ ...        proxy_pass http://127.0.0.1:8080/;        ← SDK（sdkcard.py）
171: location = /common/config   → 127.0.0.1:8080
172: location ^~ /common/        → 127.0.0.1:8080
173: location ^~ /user/          → 127.0.0.1:8080     ← **/user/login、/user/quick-login、/user/detail**
174: location ^~ /heartbeat/     → 127.0.0.1:8080
175: location ^~ /order/         → 127.0.0.1:8080
178: location ^~ /api/           → 127.0.0.1:9097     ← 桥（account_auth_probe.py）
207: location = /api/state       → 静态 state1.json
```
**⇒ 换卡密走 `/user/login`（8080 sdkcard）；游戏身份走 `/api/account/auth`（9097 桥）。两者之间唯一的传递就是客户端手里的 `DevId`。**

---

## 6. 卡密 → AccountDB.ServerId 的真实映射

```
卡 A (11111111111, index 0)  → SDK User.ID 314816420 ┐
                                                     ├→ 客户端 DevId = 314816420
卡 B (12222222222, index 1)  → SDK User.ID 854071516 ┘   （但 quick-login 永远返回 A）
                                                              ↓
                                          Account_Auth req.DevId = "314816420" (len=9, sha8=a424da70)
                                                              ↓
                                          桥 identify: req_devid_src=fragment → acct_id_src=exact
                                                              ↓
                                          accounts.db: dev_id=314816420 → server_id=10000000000
                                                              ↓
                                          AccountDB.ServerId = 10000000000（两次登录完全相同）
```

**现实 = 「一机一账号」**，成因是两层叠加：

1. **SDK 层（首要）**：`sdkcard.py:391-402` 的 `/user/quick-login` 遍历 `d['cards'].items()`，命中第一张含本机的卡就返回。
   两张卡都含 `ce8ffeb7d08cfb36`，卡 A 索引 0 ⇒ **`quick-login` 永远回卡 A**（日志：`QUICK OK 1111…` 20+ 次，`QUICK OK 1222…` 0 次）。
   `/user/detail`（`:404-407`）同样遍历，同样锁定卡 A。
2. **桥/客户端层**：客户端把 `DevId` 当作稳定设备标识（实测恒为 9 位 `314816420`，5 次登录 sha8 不变），
   桥按 DevId 精确命中既有账号 ⇒ **换卡密不会换账号**。

**证据充分性**：证据足够，无需再做推断。
唯一未直接观测的一环是「客户端究竟在哪一步把 SDK `User.ID` 写成 `DevId`」（属客户端实现，服务器侧只能看到结果恒定），
但**结果层已由 5 条 auth 记录的 `req_devid_sha8` 恒定 + `acct_server_id` 恒定闭环**。

---

## 6b. 决定性补充：抢回身份的是 `/user/detail`（2026-11-18 03:17:29 / 03:20:08 两次完整序列）

数据源：`/www/wwwroot/ba_sdk/sdk.log`（含逐请求 `HH:MM:SS /path dev=…` 与 BODY 行）+ `/www/wwwlogs/example.com.log`。

### 卡 B 首次成功那一次的完整后续（sdk.log 3041–3051）
```
3041: 03:17:29 /user/login   dev=ce8ffe…        BODY {"OpenID":"1222****2222", …}
3043: LOGIN OK 1222****2222  _mask(dev)=ce8f****fb36      ← 新卡 B 登录成功（User.ID=854071516）
3044: 03:17:29 /user/detail  dev=ce8ffe…        BODY {}    ← ★ 紧接着就调 detail（无 body，纯靠设备）
3046: 03:17:29 /health-game/duration
3048: 03:17:29 /common/geo-ip
3050: 03:17:29 /heartbeat/pulse  {"PI":""}
```
`/user/detail` 的实现（`sdkcard.py:404-412`）：
```python
if path == '/user/detail':
    d = load_cards()
    for key, rec in d['cards'].items():
        if dev and dev in rec.get('devices', []):
            self._send({'Code': 200, 'Msg': 'OK', 'Data': user_payload(key, dev)})
            return                                   # ← 第一张命中即返回
```
**该分支不读请求体、不看刚才用哪张卡登录，只按“设备在谁的 devices 里 + JSON 顺序”返回第一张 = 卡 A。**
access log 佐证：`03:17:29 /user/detail 200 resp=847`（847 = 完整 `user_payload`，与 login 成功同样的体积；失败/空返回是 54 或 `{}`）。

### 同一模式重复（sdk.log 3103–3113）
```
3103: 03:20:08 /user/login   BODY {"OpenID":"1222****2222", …}
3105: LOGIN OK 1222****2222
3106: 03:20:08 /user/detail  BODY {}
3108: /health-game/duration   3110: /common/geo-ip   3112: /heartbeat/pulse
```

### 之后客户端就自己“回到卡 A”（sdk.log 3129–3131）
```
3129: 03:20:57 /user/login   BODY {"OpenID":"1111****1111", …}    ← 客户端提交的是卡 A
3131: LOGIN OK 1111****1111
3132: 03:20:57 /user/detail  BODY {}
```
且 `03:20:58` 的 `/api/account/auth` 用的 DevId 仍是 `a424da70`（=`314816420`=卡 A 的 `User.ID`）。

### access log 完整请求序列（03:00–03:30，example.com.log）
```
03:05:30 /common/config          200 4871
03:05:39 /sdk/user/quick-login   200 847      ← quick-login 返回卡 A
03:05:39 /user/detail            200 847      ← detail 也返回卡 A
03:06:08 /api/account/auth       200 2717     ← DevId=314816420 → 账号 10000000000
03:07:58 /common/config          200 4871
03:08:06 /sdk/user/quick-login   200 847
03:08:06 /user/detail            200 847
03:09:04 /sdk/user/login         200 847
03:09:04 /user/detail            200 847
03:09:05 /api/account/auth       200 2719
03:09:17 /user/detail            200 847
03:16:03 /sdk/user/login         200 54       ┐ 卡 B 尚未建，6 次拒绝
03:16:04 /sdk/user/login         200 54       │ （sdk.log 2985–3024 LOGIN REJECT unknown card 1222）
03:16:35 /sdk/user/login         200 54       │
03:16:37 /sdk/user/login         200 54       │
03:16:38 /sdk/user/login         200 54       │
03:16:45 /sdk/user/login         200 54       ┘
03:17:29 /api/account/auth       200 2722     ← 用旧 DevId（卡 A）
03:17:29 /sdk/user/login         200 847      ← **卡 B 首次 LOGIN OK**
03:17:29 /user/detail            200 847      ← **detail 抢回卡 A**
03:20:08 /api/account/auth       200 2725     ← 仍是卡 A 的 DevId
03:20:08 /sdk/user/login         200 847      ← 卡 B 再次 OK
03:20:08 /user/detail            200 847      ← 又被 detail 抢回 A
03:20:57 /sdk/user/login         200 847      ← **客户端这次提交的是卡 A**
03:20:57 /user/detail            200 847
03:20:58 /api/account/auth       200 2722     ← 最终落到账号 10000000000
```

### 回答你的 Q5
**`LOGIN OK 卡B` 之后紧接着的 SDK 调用是 `/user/detail`（不是 quick-login、也不是再次 login）。**
`/user/detail` 用「设备 + JSON 顺序」返回卡 A 的完整 `user_payload`（含 `User.ID=314816420`、`User.Token`），
客户端把这个返回值当作当前身份 ⇒ DevId 落地为 314816420 且此后不再变。
**⇒ 不是“客户端 DevId 一旦落地永不变”，而是“每次登录 B 后都被 detail 覆写回 A 的 User.ID”。**

### 关于 access log 可用性（Q4）
```
文件：/www/wwwlogs/example.com.log  13,555,155 B  mtime 03:21（本窗口数据完整，未轮转截断）
另有一套带端口后缀的历史文件（..._80.log / _88.log / _65454.log / _1027_1027.log），
  最新修改日期都是 6 月 / 10 月 ⇒ 与当前 vhost（443/80 统一写 example.com.log）无关，属旧站点遗留。
宝塔面板侧没有找到 /etc/logrotate.d 里针对 /www/wwwlogs 的规则（grep 无命中），
  面板默认是「按大小切割」（/www/server/panel 配置项里未见显式 wwwlogs 规则）
⇒ **无法从配置断言保留天数；实测当前文件从 11-13 起连续可用（06:5x 之前的记录仍在），至少保留数天**。
```

---

## 7. 供后续修复参考的约束（不是本次动作）

- 修 `/user/quick-login` 的「第一张卡」语义：需按“最近一次显式登录的卡”或“设备→卡”的显式映射来返回，而不是遍历顺序。
- `cards.json` 目前**没有** `kind` / `max_devices` / `last_used_at` 字段（只有 `devices` / `expire` / `bind_one`）。
- 桥的身份入口已通（`req_devid_src=fragment`），但**它信任客户端给的 DevId**；若要“一卡一账号”，必须在 SDK 层让不同卡的 `User.ID`/Token 产生不同 DevId，或在桥侧增加卡→账号绑定表。

---

*生成方式：全部命令只读（`stat`/`md5sum`/`find`/`grep`/`sqlite3 ro`/`python3` 读取），临时脚本仅放在 `/tmp` 并已在使用后删除。*
