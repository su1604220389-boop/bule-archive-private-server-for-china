# sdkcard_v2 交付说明（卡密认证 v2）

> 交付文件：`work/ba/sdk/sdkcard_v2.py`、`work/ba/sdk/selftest_sdkcard_v2.py`、`work/ba/sdk/SDKCARD_V2.md`。
> 只新增文件；v1 `work/ba/bapatch/sdkcard.py` 与 `work/ba/bapatch/cards.json` 均未改动（sha256 见 §12）。
> 本次没有执行任何 ssh / scp / 远程命令；§7、§10 的上线命令只是交给 srv-ops 的文本。

---

## 0. 先看：一个必须先决策的阻断项

当前 PHP 管理站（`work/ba/cardadmin_php`）的设计是 **MySQL 是唯一真源**，`cron/sync_cards.php` 每分钟把 MySQL 重新导出成 `cards.json`，而导出函数只写三个字段：

```php
$out[$key] = array(
    'devices'  => ...,
    'expire'   => ...,
    'bind_one' => ...,
);
```

这会导致 v2 的新东西在 **60 秒内被覆盖**：

| v2 写入的东西 | 下一次 PHP cron 同步后 |
|---|---|
| `kind`（public） | 丢失 → 该卡按 `normal` 处理 |
| `max_devices` | 丢失 → 退回按 `bind_one` 推导 |
| `self_unbind_limit` / `cooldown` / `used` / `last` | 丢失 → 自助解绑默认关闭（limit 缺失=0） |
| 只通过 `/admin/issue` 建、MySQL 里没有的卡 | 整张卡消失（或 `--import-orphans` 时被当成普通卡导入） |
| `/admin/unbind` 或 `/auth/self-unbind` 从 `devices` 删掉的设备 | 只要 `card_devices` 表里还有，就会被重新导出、重新出现 |

**结论：**

- **第一阶段（今天就能上）**：只启用 `/auth/verify` + 现有普通卡登录。`/auth/verify` 是只读的，只依赖 `devices` / `expire`，PHP cron 可以照常跑。这是最安全的落地方式。
- **第二阶段（公益卡 / max_devices>1 / 自助解绑）**：必须先改 PHP 的数据库与同步逻辑，或者冻结 PHP cron、让 v2/卡密管理端成为 `cards.json` 的唯一写入者。**在改完之前，不要在生产上启用公益卡和自助解绑**，否则会出现“刚解绑又回来”“公益卡变普通卡”的问题。

详见 §9。

---

## 1. 交付物与兼容性红线

### 1.1 交付物

| 文件 | 作用 | 字节 | sha256 |
|---|---|---:|---|
| `work/ba/sdk/sdkcard_v2.py` | v2 主服务 | 35701 | `e4884f66057dc4e102e8af3eaf7096722a8a1b1f61dbb37301bee653bcbdde45` |
| `work/ba/sdk/selftest_sdkcard_v2.py` | 自检脚本（86 项） | 35186 | `eef9ee977f828b3eb4bca73837a21b86e4601bbf39c3f0885924efca0fc7a3ed` |
| `work/ba/sdk/SDKCARD_V2.md` | 本说明 | — | 见交付回执 |

### 1.2 身份与 token（一个字节都没改）

```python
tok = hashlib.sha256((card + "|" + device).encode()).hexdigest()[:40]
User.ID = int(hashlib.md5(card.encode()).hexdigest()[:8], 16) % 900000000 + 100000000
NickName = "BA" + card[-4:]
```

已知真值（线上实测过）：

| 输入 | 值 |
|---|---|
| 卡密 | `11111111111` |
| 设备 | `09a4d0ab0ee93616` |
| `User.ID` | `314816420` |
| `User.Token` | `61de1d1b7519ab1231866f74c11fcfdd1f80b210` |
| `Pass.NickName` | `BA1111` |

v2 自检里把这四项全部重新算了一遍（见 §11）。

### 1.3 旧 7 条 HTTP 路径原样保留

| 路径 | v1 行为 | v2 变化 |
|---|---|---|
| `/user/login` | `OpenID`=卡密；校验过期/设备绑定；返回模板 | 仅增加 `kind` 分叉；normal 路径不变 |
| `/user/quick-login` | 按设备找卡；过期则 `40003` | public 卡忽略 `expire`；normal 不变 |
| `/user/detail` | 按设备找卡返回模板；找不到回空 `Data` | 仅 `User.ID` 按 kind 派生；其余不变 |
| `/common/config` | 读 `resp/common_config.json`，做 4 组域名替换 | 不变 |
| `/common/geo-ip` | `{"Code":200,"Data":{"Prov":"浙江省"}}` | 不变 |
| `/health-game/duration` | `Code 110170 / 用户已成年,不需要计时` | 不变 |
| `/heartbeat/pulse` | `{"Delay":3600}` | 不变 |
| 其余路径 | `{"Code":200,"Msg":"OK","Data":{}}` | 不变 |

另外保留 v1 的：`protocol_version = HTTP/1.1`、`do_GET = do_POST`、`Content-Length`、`log_message` 静默、`Authorization` 里 `Head.DeviceID` 的解析方式。

### 1.4 旧 ID 区间收窄：必须知道的兼容性边界

新公式：

```python
user_id_normal(card)   = 100_000_000 + _h8(card)         % 450_000_000   # [1e8, 5.5e8)
user_id_public(device) = 550_000_000 + _h8("public|"+device) % 450_000_000  # [5.5e8, 1e9)
```

对 `11111111111` 的验算（自检里会打印）：

```text
_h8("11111111111")             = 2914816420
2914816420 % 900000000         = 214816420
旧公式 100000000 + 214816420   = 314816420
新公式 100000000 + 2914816420 % 450000000 = 314816420
```

**旧值 < 5.5e8 的卡**：新值 = 旧值，逐字节相同。
**旧值 >= 5.5e8 的卡**：新值 = 旧值 - 4.5e8，**会换 User.ID**。

任务描述里写“与旧公式在 90% 情况下一致”，按公式推导实际是“低半区（<5.5e8）一致”，均匀分布下约 50%。这不是实现偏差，是“两套 ID 必须分区间、且 public 必须落在 [5.5e8,1e9)”的硬约束决定的。

本地 `work/ba/bapatch/cards.json` 的两张真实卡都落在低半区，实测 **2/2 不变**：

```text
11111111111 old=314816420 new=314816420 SAME
22222222222 old=426253058 new=426253058 SAME
```

上线前必须对线上 `cards.json` 跑一次只读审计（§7.2）。若出现 `CHANGED`，需要业务上决定：接受该卡下次登录换新 ID，还是先人工处理/推迟。

### 1.5 公益卡的 ID 特性

`user_id_public(device)` 只依赖设备，不依赖卡密。因此：

- 同一台设备即使绑了多张公益卡，`User.ID` 相同；
- 区分是哪张卡靠 `Token = sha256(card|device)[:40]`；
- `/auth/verify` 会用 Token 反查 Card，返回命中的那张。

这是任务规格本身的设计，不是 bug，但运营上要知道“换公益卡不换号”。

---

## 2. `cards.json` 字段

结构仍是：

```json
{"cards": {"<卡密>": { ... }}}
```

每条卡支持：

| 字段 | 类型 | 默认/缺失 | 含义 |
|---|---|---|---|
| `kind` | string | `normal` | `normal` / `public`；缺失或非法一律按 `normal` |
| `max_devices` | int | 缺失时按 `bind_one` 推导 | `0` = 不限；`n>0` = 最多 n 台；存在时优先于 `bind_one` |
| `bind_one` | bool | `false` | **旧字段，保留兼容**；`max_devices` 缺失时：true→1，false→0 |
| `devices` | string[] | `[]` | 已授权设备；public 也记录（只用于校验，不做数量限制） |
| `expire` | int | `0` | unix 秒；`0` = 永不过期；**public 忽略** |
| `self_unbind_limit` | int | `0` | 允许自助解绑次数；`0` = 不允许；`-1` = 不限 |
| `self_unbind_cooldown` | int | `0` | 两次自助解绑最小间隔（秒）；`0` = 无冷却 |
| `self_unbind_used` | int | `0` | 已用次数，由服务端维护 |
| `self_unbind_last` | int | `0` | 上次自助解绑 unix 秒，由服务端维护 |

未知字段/未知顶层键 **原样保留**：v2 每次写回都是整份 JSON 读改写，不会像 PHP sync 那样按白名单重建。

### 2.1 普通卡示例

```json
{
 "cards": {
  "11111111111": {
   "kind": "normal",
   "max_devices": 1,
   "devices": ["09a4d0ab0ee93616"],
   "expire": 0,
   "bind_one": true
  }
 }
}
```

### 2.2 公益卡示例

```json
{
 "cards": {
  "PUB-2026-001": {
   "kind": "public",
   "max_devices": 0,
   "devices": ["dev-a", "dev-b"],
   "expire": 0,
   "bind_one": false,
   "self_unbind_limit": 3,
   "self_unbind_cooldown": 86400,
   "self_unbind_used": 0,
   "self_unbind_last": 0
  }
 }
}
```

`expire` 对 public 可以填任意值（包括过去时间），登录与 `/auth/verify` 都会忽略它；这样即使 PHP 侧习惯性填了到期时间，公益卡也不会被误杀。

---

## 3. 新接口

统一约定：

- 请求/响应都是 JSON；除 admin 鉴权失败（403）和后端读文件失败（503）外，业务失败也返回 **HTTP 200**，靠 `ok` / `Reason` 区分。
- 外部经 nginx 的路径要带 `/sdk` 前缀（`/sdk/auth/verify`），nginx 剥掉后到本服务是 `/auth/verify`。
- 新增接口的日志用 `[v2]` 前缀，不写请求 body，不会把 Token 写进 `sdk.log`；cardadmin 的 `HH:MM:SS /path dev=` 解析器不会把它误吞成登录事件。

### 3.1 `POST /auth/verify`（游戏网关调用）

请求：

```json
{"DevId": "314816420", "Token": "61de1d1b7519ab1231866f74c11fcfdd1f80b210"}
```

- `DevId`：**十进制字符串**，就是客户端实际发的 `User.ID`（客户端把它当 DevId 用）。
- `Token`：40 位 hex，就是 `User.Token`。

成功：

```json
{"ok": true, "Kind": "normal", "Card": "11111111111"}
```

失败：

```json
{"ok": false, "Reason": "device_revoked"}
```

`Reason`：

| Reason | 触发条件 |
|---|---|
| `bad_request` | `DevId`/`Token` 缺失、空、类型不对 |
| `unknown_identity` | 全表没有任何卡的 ID 能对上 `DevId` |
| `device_revoked` | 身份对上了，但 Token 不在该卡任何已授权设备上（**解绑后立即落在这里**） |
| `expired` | 普通卡 Token 对上了，但 `expire` 已过 |
| `backend_error` | 读 `cards.json` 失败；HTTP 503（额外运维态，不属于正常业务） |

匹配规则：

- **normal**：先看 `str(user_id_normal(card)) == DevId`；再对该卡 `devices` 里每个 `d` 算 `sha256(card|d)[:40]`，用 `hmac.compare_digest` 比较；token 命中且未过期 → 通过。
- **public**：在 `devices` 里找 `d` 使 `str(user_id_public(d)) == DevId`；再对**这个 d** 比 token；命中即通过（不看 `expire`）。
- 找不到任何身份 → `unknown_identity`；身份对上但 token 不对 → `device_revoked`。
- 过期与解绑同时存在时：**先比 token**，token 不对就是 `device_revoked`；token 对但过期才是 `expired`。这样“解绑后立即失效”优先于“过期”。

实现细节：

- 全表遍历（卡少，可接受）；`RLock` 保护读；**读路径绝不写盘**。
- 5 秒内存缓存，键是 `cards.json` 的 `(mtime_ns, size)`；文件一变立即重读，5 秒只是“没变时复用”。
- `hmac.compare_digest` 做 token 比较；对同一张卡的多个设备不提前 break，避免按设备位置泄漏时序。

示例（旧卡真值）：

```bash
curl -sS -X POST http://127.0.0.1:8080/auth/verify \
  -H 'Content-Type: application/json' \
  -d '{"DevId":"314816420","Token":"61de1d1b7519ab1231866f74c11fcfdd1f80b210"}'
# {"ok": true, "Kind": "normal", "Card": "11111111111"}
```

示例（公益卡，卡 `PUB-DEMO`、设备 `09a4d0ab0ee93616`）：

```text
User.ID = user_id_public("09a4d0ab0ee93616") = 853248039
Token   = sha256("PUB-DEMO|09a4d0ab0ee93616")[:40]
        = 40ac91ebd77239b58d5199d57f4ac4ad35b020ea
```

```json
{"DevId": "853248039", "Token": "40ac91ebd77239b58d5199d57f4ac4ad35b020ea"}
→ {"ok": true, "Kind": "public", "Card": "PUB-DEMO"}
```

### 3.2 `POST /auth/self-unbind`（自助解绑）

请求：

```json
{"Card": "SELF-DEMO", "Device": "dev-a"}
```

成功：

```json
{"ok": true, "remaining": 2}
```

失败：

```json
{"ok": false, "Reason": "cooldown"}
```

`Reason`：

| Reason | 触发条件 |
|---|---|
| `unknown_card` | 卡不存在 |
| `limit_reached` | `self_unbind_limit == 0`，或 `used >= limit` |
| `cooldown` | `cooldown > 0` 且 `last > 0` 且 `now - last < cooldown` |
| `not_bound` | 设备不在 `devices` 里 |
| `bad_request` | `Card`/`Device` 缺失、空、类型不对（额外防护） |
| `backend_error` | 读写 `cards.json` 失败；HTTP 503 |

检查顺序严格按规格：**卡存在 → 次数未超 → 冷却已过 → 设备在不在**。因此“次数已用尽 + 设备本来就没绑”会返回 `limit_reached`，不是 `not_bound`。

`remaining`：

- 有限次数：`max(0, limit - used_after)`；
- `limit == -1`：返回 `-1`（表示不限）。

写回：

- 临时文件（同目录）+ `fsync` + `os.replace` + `flock`（Linux `fcntl.flock`；Windows 本地自测用 `msvcrt.locking`）；
- 格式与 v1 `save_cards` 一致：`json.dump(..., ensure_ascii=False, indent=1)`；
- 保留原文件权限与 owner（POSIX 上 root 运行时 `os.chown` 回原 uid/gid）。

### 3.3 `POST /admin/unbind`（管理端直接解绑）

必须带：

```http
X-Admin-Key: <BA_ADMIN_KEY>
```

请求：

```json
{"Card": "11111111111", "Device": "09a4d0ab0ee93616"}
```

响应：

```json
{"ok": true, "RemainingDevices": 0}
```

- 直接从 `devices` 删除该设备（含重复项），**不增加** `self_unbind_used`、**不更新** `self_unbind_last`；
- 卡不存在 → `{"ok":false,"Reason":"unknown_card"}`；
- 设备没绑 → `{"ok":false,"Reason":"not_bound"}`；
- 参数不合法 → `bad_request`。
- 删除后同一 Token 立即 `/auth/verify` 失败（`device_revoked`）。

### 3.4 `POST /admin/issue`（管理端建卡）

必须带 `X-Admin-Key`。

请求：

```json
{
  "Card": "PUB-2026-001",
  "Kind": "public",
  "Expire": 0,
  "MaxDevices": 0,
  "SelfUnbindLimit": 3,
  "SelfUnbindCooldown": 86400
}
```

响应：

```json
{"ok": true, "Card": "PUB-2026-001", "Kind": "public"}
```

字段默认值：

| 字段 | 默认 | 约束 |
|---|---:|---|
| `Kind` | `normal` | 只接受 `normal` / `public`（大小写不敏感，去空格） |
| `Expire` | `0` | `>= 0`；0=永不过期 |
| `MaxDevices` | `1` | `>= 0`；0=不限 |
| `SelfUnbindLimit` | `0` | `>= -1`；0=不允许，-1=不限 |
| `SelfUnbindCooldown` | `0` | `>= 0` 秒 |

落盘记录：

```json
{
  "kind": "public",
  "max_devices": 0,
  "devices": [],
  "expire": 0,
  "bind_one": false,
  "self_unbind_limit": 3,
  "self_unbind_cooldown": 86400,
  "self_unbind_used": 0,
  "self_unbind_last": 0
}
```

说明：

- `bind_one` 由 `kind == "normal" && max_devices == 1` 自动推出，保留给旧工具读；
- **public 的 `max_devices` 原样落盘，但登录/校验路径完全忽略它**（规格：公益卡不限设备）。因此即使写成 2，也还能继续加第 3、4 台；
- 重复卡 → `card_exists`；非法 Kind/数值 → `bad_request`；
- 只新建，不覆盖。给已有卡改 `max_devices` / 自助配额请用 §8 的一次性脚本（目前没有 update 接口）。

### 3.5 admin 鉴权

- 密钥只从环境变量 `BA_ADMIN_KEY` 读；
- **没设置 / 空字符串 → 所有 `/admin/*` 一律 403**，不存在“默认放行”；
- 头名 `X-Admin-Key`，值用 `hmac.compare_digest` 比较；
- 所有 `/admin/*` 前缀统一守卫，未来新增第三个 admin 接口不用再单独加鉴权（任务正文写了“三个 admin 接口”，但只列了两个：`/admin/unbind`、`/admin/issue`；这里用前缀守卫覆盖“第三个”）。

403 响应：

```json
{"ok": false, "Reason": "forbidden"}
```

### 3.6 HTTP 状态码一览

| 场景 | HTTP | Body |
|---|---:|---|
| 业务成功 | 200 | `{"ok":true,...}` |
| 业务失败（verify/self-unbind/admin 动作） | 200 | `{"ok":false,"Reason":"..."}` |
| admin 无/错 key，或未配置 `BA_ADMIN_KEY` | 403 | `{"ok":false,"Reason":"forbidden"}` |
| 新接口后端读文件失败 | 503 | `{"ok":false,"Reason":"backend_error"}` |
| 旧接口内部异常 | 500 | `{"Code":500,"Msg":"internal error","Data":{}}`（v1 会直接断连接，这是小幅加固） |
| 未知 `/admin/*`（key 正确） | 404 | `{"ok":false,"Reason":"not_found"}` |

---

## 4. 旧接口在新 kind 下的行为

| 场景 | normal | public |
|---|---|---|
| `/user/login` 过期检查 | 生效 | 忽略 |
| `/user/login` 设备上限 | `max_devices`（0=不限） | 不限 |
| `/user/login` 是否写 `devices` | 新设备写入 | 新设备写入（仅用于 verify，不做拒绝） |
| `/user/quick-login` 过期检查 | 生效（命中过期卡直接 `40003`） | 忽略 |
| `/user/detail` 过期检查 | 不检查（v1 原样） | 不检查 |
| `User.ID` | `user_id_normal(card)` | `user_id_public(device)` |
| `Token` | `sha256(card|device)[:40]` | 同左 |
| `Pass.NickName` | `BA` + 卡后 4 位 | 同左 |

`/user/login` 返回码保持 v1：

- 未知卡：`{"Code":400101,"Msg":"卡密不正确"}`
- 过期：`{"Code":400101,"Msg":"卡密已过期"}`
- 设备超限：`{"Code":400101,"Msg":"卡密已绑定其他设备"}`
- 成功：`{"Code":200,"Msg":"OK","Data":{...模板...}}`

`/user/quick-login` 未命中仍是 `{"Code":40003,"Msg":"请输入卡密"}`。

---

## 5. 运行与配置

### 5.1 环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `BA_CARDS` | `<脚本目录>/cards.json` | 卡密库 |
| `BA_LOG` | `<脚本目录>/sdk.log` | 日志 |
| `BA_CONFIG` | `<脚本目录>/resp/common_config.json`，找不到再试 `sdk_resp/` | `/common/config` 模板 |
| `BA_TEMPLATE` | `<脚本目录>/resp/user_quick-login.json`，找不到再试 `sdk_resp/` | 登录响应模板 |
| `BA_HOST` | `127.0.0.1` | 监听地址；要对其他机器提供 verify 才改 `0.0.0.0` |
| `BA_PORT` | `8080` | 监听端口 |
| `BA_ADMIN_KEY` | 无 | admin 共享密钥；**不设置 = admin 全拒** |

默认值就是按线上实际目录 `/www/wwwroot/ba_sdk` 设计的：`cards.json`、`sdk.log`、`resp/` 都在同目录，不需要改任何路径常量。

### 5.2 启动

```bash
cd /www/wwwroot/ba_sdk
BA_ADMIN_KEY='<long-random-secret>' python3 sdkcard_v2.py
```

systemd 建议用独立 env 文件，避免密钥出现在 `systemctl show` / shell history：

```ini
# /www/wwwroot/ba_sdk/sdkcard.env   (chmod 600, root)
BA_ADMIN_KEY=<long-random-secret>
# 可选
# BA_HOST=127.0.0.1
# BA_PORT=8080
```

```ini
# /etc/systemd/system/ba-sdk.service 里补一行
EnvironmentFile=/www/wwwroot/ba_sdk/sdkcard.env
```

改 env 文件后需要 `systemctl restart ba-sdk`（进程只在启动时读环境；admin key 是每请求读 `os.environ`，但 systemd 不会热更新进程环境）。

### 5.3 权限

- 原子替换会保留原 `cards.json` 的权限和 owner；新文件默认 0644。
- 建议 v2 与 `cards.json` 的 owner 用同一个用户跑；如果 PHP 以 `www` 写同一个文件/目录，要么把目录权限调好，要么让 PHP 改走 v2 的 `/admin/*`。
- `cards.json.lock` 由服务自动创建（0600），不要删；它不是卡密数据。

### 5.4 日志

- 旧 7 条路径：完全保留 v1 的 `HH:MM:SS /path dev=` + `BODY ...` 两行格式，cardadmin 的 `sdk.log` 解析不受影响。
- 新接口：`[v2] /auth/verify ...`、`[v2] SELF-UNBIND ...`、`[v2] ADMIN ...`，不写 body/token。
- 启动时额外写三行：版本、四个路径、监听地址。
- `sdk.log` 没有自动轮转；建议 logrotate 或定期归档（v1 也没有）。

---

## 6. 给游戏网关的对接说明

网关只需要在原本要拿 `(uid, token)` 的地方改成调用：

```python
import json
import urllib.request

def verify(dev_id: str, token: str) -> dict:
    body = json.dumps({"DevId": str(dev_id), "Token": token}).encode()
    req = urllib.request.Request(
        "http://127.0.0.1:8080/auth/verify",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=2) as resp:
        return json.loads(resp.read().decode("utf-8"))
```

- 成功时用返回的 `Card` 去找账号/卡密记录；`Kind` 只用于日志/分支。
- `DevId` 是 `User.ID` 的十进制字符串，**不是** Authorization 头里的原始 `DeviceID`（原始设备 ID 形如 `09a4d0ab0ee93616`）。
- 失败时按 `Reason` 处理：`unknown_identity` / `device_revoked` / `expired` 都应拒绝进入游戏；`bad_request` 说明网关传参有问题；`backend_error`（HTTP 503）建议短重试 + 告警，不要当成“卡密错误”。
- 路径：如果网关和 sdkcard 不在同一台机器，必须设 `BA_HOST=0.0.0.0` 并加防火墙/只允许网关 IP；更推荐把网关与 sdkcard 放同一台，走 127.0.0.1。

---

## 7. 迁移步骤（平滑升级）

> 下面命令只写给 srv-ops；本次执行 agent 没有连服务器。

### 7.1 备份

```bash
ts=$(date +%Y%m%d-%H%M%S)
cd /www/wwwroot/ba_sdk
cp -a cards.json "cards.json.bak.$ts"
cp -a sdkcard.py "sdkcard.py.bak.$ts"
cp -a resp "resp.bak.$ts" 2>/dev/null || true
cp -a /etc/systemd/system/ba-sdk.service "/root/ba-sdk.service.bak.$ts"
# PHP 侧也备份
cp -a /www/wwwroot/ba_cardadmin/config.php "/root/ba_cardadmin.config.php.bak.$ts" 2>/dev/null || true
crontab -l > "/root/crontab.bak.$ts" 2>/dev/null || true
```

### 7.2 旧 ID 只读审计（上线前必做）

```bash
cd /www/wwwroot/ba_sdk
python3 - <<'PY'
import json, hashlib
d = json.load(open('cards.json', encoding='utf-8'))
changed = 0
for card, rec in d.get('cards', {}).items():
    h = int(hashlib.md5(card.encode()).hexdigest()[:8], 16)
    old = h % 900000000 + 100000000
    new = 100000000 + h % 450000000
    flag = 'SAME' if old == new else 'CHANGED'
    if old != new:
        changed += 1
    print('%-7s %-24s old=%-10d new=%-10d' % (flag, card, old, new))
print('changed=%d / total=%d' % (changed, len(d.get('cards', {}))))
PY
```

- 全 `SAME` → 直接继续。
- 有 `CHANGED` → 先确认这些卡是否还有效、是否能接受“下次登录换 ID”；必要时先不改用 v2，或与业务确认后再切。
- 本地 `work/ba/bapatch/cards.json` 实测 2/2 `SAME`（`314816420`、`426253058`）。

### 7.3 预检

```bash
cd /www/wwwroot/ba_sdk
python3 -m py_compile sdkcard_v2.py
ls -l cards.json resp/common_config.json resp/user_quick-login.json
ss -tlnp | grep ':8080' || echo '8080 free'
systemctl status ba-sdk --no-pager || true
crontab -l | grep sync_cards || true
```

确认：

- `resp/` 存在，且 `common_config.json`、`user_quick-login.json` 在；
- PHP 的 `config.php` 里 `cards_json` 指向 `/www/wwwroot/ba_sdk/cards.json`，`sdk_log` 指向 `/www/wwwroot/ba_sdk/sdk.log`；
- `crontab` 里有没有每分钟的 `sync_cards.php`（决定 §9 走 A 还是 C）。

### 7.4 灰度（推荐先跑只读）

```bash
cp -a /www/wwwroot/ba_sdk/cards.json /tmp/cards.canary.json
cd /www/wwwroot/ba_sdk
BA_CARDS=/tmp/cards.canary.json BA_PORT=8081 BA_HOST=127.0.0.1 \
  python3 sdkcard_v2.py
```

```bash
curl -sS -X POST http://127.0.0.1:8081/heartbeat/pulse -H 'Content-Type: application/json' -d '{}'
curl -sS -X POST http://127.0.0.1:8081/auth/verify -H 'Content-Type: application/json' \
  -d '{"DevId":"314816420","Token":"61de1d1b7519ab1231866f74c11fcfdd1f80b210"}'
```

canary 用 `/tmp` 的副本，避免和线上 v1 同时写同一份 `cards.json`。只做读接口 smoke；要测登录绑定/解绑，必须用副本。

### 7.5 切换（二选一）

**方式 A：符号链接（推荐，回滚最快）**

```bash
systemctl stop ba-sdk
cd /www/wwwroot/ba_sdk
cp -a sdkcard.py sdkcard_v1.py
ln -sfn sdkcard_v2.py sdkcard.py
systemctl start ba-sdk
systemctl status ba-sdk --no-pager
ss -tlnp | grep ':8080'
```

**方式 B：直接覆盖**

```bash
systemctl stop ba-sdk
cd /www/wwwroot/ba_sdk
cp -a sdkcard.py sdkcard_v1.py
cp -a sdkcard_v2.py sdkcard.py
systemctl start ba-sdk
```

两种方式都必须先停 v1，不能两个进程同时抢 8080。

### 7.6 上线后冒烟

```bash
# 1) 旧路径
curl -sS -X POST http://127.0.0.1:8080/heartbeat/pulse -H 'Content-Type: application/json' -d '{}'
# {"Code":200,"Msg":"OK","Data":{"Delay":3600}}

# 2) 旧卡真值
curl -sS -X POST http://127.0.0.1:8080/user/quick-login \
  -H 'Content-Type: application/json' \
  -H 'Authorization: {"Head":{"DeviceID":"09a4d0ab0ee93616"}}' -d '{}'
# Data.User.ID 应为 314816420，Token 61de...b210

# 3) 网关校验
curl -sS -X POST http://127.0.0.1:8080/auth/verify -H 'Content-Type: application/json' \
  -d '{"DevId":"314816420","Token":"61de1d1b7519ab1231866f74c11fcfdd1f80b210"}'
# {"ok":true,"Kind":"normal","Card":"11111111111"}

# 4) admin 无 key 必须 403
curl -sS -i -X POST http://127.0.0.1:8080/admin/unbind \
  -H 'Content-Type: application/json' -d '{"Card":"x","Device":"y"}' | head

# 5) admin 带 key 走一个不存在的卡，应 200 + unknown_card（证明 key 生效）
curl -sS -X POST http://127.0.0.1:8080/admin/unbind \
  -H 'Content-Type: application/json' -H "X-Admin-Key: $BA_ADMIN_KEY" \
  -d '{"Card":"__smoke__","Device":"__none__"}'
# {"ok":false,"Reason":"unknown_card"}
```

再检查 `sdk.log` 最后几行、`systemctl status`、nginx 的 `/sdk/` 反代。

### 7.7 回滚

```bash
systemctl stop ba-sdk
cd /www/wwwroot/ba_sdk
ln -sfn sdkcard_v1.py sdkcard.py     # 方式 A
# 或 cp -a sdkcard_v1.py sdkcard.py  # 方式 B
systemctl start ba-sdk
```

`cards.json` 不需要回滚：新字段是增量，v1 读得懂（它只碰 `devices` / `expire` / `bind_one`，未知字段原样保留）。但 v1 下：

- public 卡会按 normal 处理：用旧卡密派生的 ID、按 `expire` 判断、忽略 `max_devices`；
- `/auth/verify` 不存在，网关要同步回滚；
- 自助解绑字段不再生效，但 `devices` 的当前状态保留。

详见 §10。

---

## 8. 旧 `cards.json` 如何平滑升级

### 8.1 最省事：不升级

v2 对缺失字段全部有 fallback：

- `kind` 缺失 → normal；
- `max_devices` 缺失 → `bind_one ? 1 : 0`；
- `self_unbind_limit` / `cooldown` / `used` / `last` 缺失 → 0。

所以**现有 `cards.json` 可以一个字节不改直接给 v2 用**。旧卡的 ID/token/绑定行为不变（高半区 ID 例外，见 §1.4）。

### 8.2 可选：一次性补字段（只在决定让 v2 主写时做）

```bash
cd /www/wwwroot/ba_sdk
python3 - <<'PY'
import sys
sys.path.insert(0, '/www/wwwroot/ba_sdk')
import sdkcard_v2 as s

data = s.load_cards()
for card, rec in data['cards'].items():
    rec.setdefault('kind', 'normal')
    if 'max_devices' not in rec:
        rec['max_devices'] = 1 if rec.get('bind_one') else 0
    rec.setdefault('self_unbind_limit', 0)
    rec.setdefault('self_unbind_cooldown', 0)
    rec.setdefault('self_unbind_used', 0)
    rec.setdefault('self_unbind_last', 0)
s.save_cards(data)
print('upgraded', len(data['cards']), 'cards')
PY
```

- 走的是 v2 的原子写 + flock，格式与 v1 一致；
- 先备份 `cards.json`；
- **如果 PHP cron 还在跑，补完 60 秒内就会被覆盖**，所以只在 §9 的 B/C 方案下做。

### 8.3 给已有卡开 `max_devices > 1` / 自助解绑

目前 `/admin/issue` 只新建、不更新。已有卡用上面的脚本改：

```python
data = s.load_cards()
rec = data['cards']['<卡密>']
rec['max_devices'] = 3
rec['self_unbind_limit'] = 3
rec['self_unbind_cooldown'] = 86400
s.save_cards(data)
```

注意：改 `max_devices` 不会踢掉已经绑定的设备；它只影响下一次新设备登录。

### 8.4 把已有卡改成公益卡

```python
data = s.load_cards()
rec = data['cards']['<卡密>']
rec['kind'] = 'public'
rec['expire'] = 0          # public 忽略，但建议置 0，避免 v1 回滚时误杀
rec['bind_one'] = False
rec['max_devices'] = 0     # public 忽略，置 0 更直观
# devices 保留；没有 devices 的设备下次登录会自动补
s.save_cards(data)
```

改造后，同一设备的下一次 `/user/login` 会拿到 public 的 `User.ID`（与之前不同）；如果该设备还在旧账号里，网关侧需要按新 ID 重新映射。

---

## 9. 与 PHP 管理站的冲突（上线阻断项 / 集成契约）

### 9.1 现状

- `work/ba/cardadmin_php/README.md` 明确写：**唯一真源是 MySQL，`cards.json` 由 cron 从数据库导出**；
- `cron/sync_cards.php` 建议每分钟跑一次；
- `inc/sync.php` 的 `sync_make_payload()` 只输出 `devices` / `expire` / `bind_one` 三个字段；
- 它还会把旧 `cards.json` 里多出来的设备**合并回** MySQL（只增不减）。

### 9.2 后果（按严重度）

1. **公益卡会被打回普通卡**：`kind` 丢失 → 下一次同步后按 normal 派生 ID、按 expire 判断。
2. **`max_devices` 丢失**：退回 `bind_one`，多设备卡会被限制成 1 台或完全放开（取决于旧值）。
3. **自助解绑失效/被回滚**：`self_unbind_*` 丢失 → 默认 limit=0，直接不可用；如果将来只保留 limit 而丢 used，则会出现配额绕过。
4. **`/admin/unbind` 不持久**：v2 从 `cards.json` 删了设备，但 MySQL `card_devices` 还有，下一次 cron 又导出来。
5. **只存在于 `cards.json` 的新卡会消失**：`/admin/issue` 建卡不会写 MySQL；cron 按 MySQL 重建时会丢掉（除非 `--import-orphans`，但那样会以普通卡导入）。
6. **登录新绑的设备可能丢**：v2 写 `cards.json` 与 cron 读旧文件合并之间有竞态；cron 读得早就会覆盖掉刚绑的设备。

### 9.3 三种可选路线

**A. 第一阶段（推荐立刻做）：只用 `/auth/verify` + 现有普通卡**

- 不改 PHP、不停 cron；
- v2 只读 `cards.json`，`/auth/verify` 不写；
- 旧 7 条路径照常，normal 卡行为不变（高半区 ID 先审计）；
- 不启用 public、`max_devices>1`、自助解绑、`/admin/*`。
- 这是风险最低、当天可回滚的方案。

**B. 冻结 cron，让 v2/卡密管理端成为唯一写入者**

- `crontab` 注释掉 `sync_cards.php`；
- 用 v2 `/admin/*` 或一次性脚本维护 `cards.json`；
- PHP 管理站只读或停用（它的写操作只进 MySQL，不会再生效）；
- 风险：PHP 面板的“新建/解绑/延期”全部失效，运营流程要改。

**C. 完整改造 PHP（要全功能就必须做）**

至少需要：

1. `cards` 表加列：

   ```sql
   ALTER TABLE cards
     ADD COLUMN kind VARCHAR(16) NOT NULL DEFAULT 'normal',
     ADD COLUMN max_devices INT NOT NULL DEFAULT 1,
     ADD COLUMN self_unbind_limit INT NOT NULL DEFAULT 0,
     ADD COLUMN self_unbind_cooldown INT NOT NULL DEFAULT 0;
   ```

   `self_unbind_used` / `self_unbind_last` 建议也进 DB，或者由 sync 从旧 JSON 原样保留（否则每次同步清零）。

2. `inc/sync.php` 的 `sync_make_payload()` 输出新字段，并在合并旧 JSON 时保留 `self_unbind_used/last`；
3. `cards_new.php` / `cards.php` / `cards_import.php` / `cards_export.php` 增加/展示新字段；
4. 解绑按钮：删 `card_devices` 行的同时调用 v2 `POST /admin/unbind`（先删 DB 再调 API，或反过来；API 失败要告警/重试），保证两边立即一致；
5. 自助解绑：v2 没有 DB 权限，需要新增 v2 → PHP 的回调/事件，或让 cron 以 `cards.json` 为设备权威并处理 tombstone。**这是二期设计，不在本次交付里。**
6. PHP 的 `cards_json` / `sdk_log` 路径确认指向 `/www/wwwroot/ba_sdk/`。

在 C 完成前，**不要把 `/auth/self-unbind` 暴露给玩家**，也不要把公益卡放进生产。

### 9.4 Python 卡密管理端（可选）

`work/ba/cardadmin` 的 `CardStore` 是整份 JSON 读改写，不会像 PHP sync 那样按白名单重建，理论上能保留 `kind` / `max_devices` / 自助字段。但它的 UI 目前只认识旧三字段；如果用它，仍要遵守“只能有一个写入者”，不要和 PHP cron 同时写。把它作为 B 方案的过渡工具可以，不要当成 C 的替代。

---

## 10. 回滚方式

### 10.1 服务回滚

见 §7.7：停 v2 → `ln -sfn sdkcard_v1.py sdkcard.py`（或 `cp`）→ 启 v1。

### 10.2 数据回滚

- `cards.json` **不需要**回滚到旧格式：v1 只读写 `devices` / `expire` / `bind_one`，未知字段保留；
- v2 写入的 `self_unbind_used/last` 会留在文件里，v1 不碰，未来再上 v2 还能继续用（除非 PHP cron 覆盖）；
- 如果 v2 期间删过设备，v1 不会自动加回；需要重新登录绑定或从备份恢复 `devices`；
- 切换前建议留一份 `cards.json.bak.<ts>`，真出问题时整份恢复。

### 10.3 回滚后的行为差异

| 项 | v2 | 回滚到 v1 |
|---|---|---|
| `/auth/verify` | 有 | 无，网关要一起回滚 |
| `/auth/self-unbind` | 有 | 无 |
| `/admin/*` | 有 | 无 |
| 公益卡 | 按设备派生 ID、不限期、不限设备 | 按卡密派生旧 ID、按 expire、忽略 max_devices |
| `max_devices>1` | 生效 | 忽略，退回 `bind_one` |
| 旧普通卡 | 低半区 ID 不变 | 不变 |
| 高半区旧卡 | ID 已换成低半区 | 回滚后 v1 仍用旧高半区 ID（如果客户端还缓存旧 ID，反而对得上；但 v2 期间签发的 token 仍可用，因为 token 只依赖 card/device） |

> 注意：token 公式两版一致，所以回滚不会让已签发的 token 失效；变的是 `User.ID`（仅高半区旧卡）和 public 卡的身份。

---

## 11. 自检

运行：

```bash
cd work/ba/sdk
python selftest_sdkcard_v2.py
```

本机 **Windows（Python 3.12.14，`msvcrt.locking` 分支）** 与本地 **WSL Ubuntu 24.04（Python 3.12.3，`fcntl.flock` 分支）** 各跑了一遍：**两次都是 86 项检查全部通过，exit 0**。自检使用 `tempfile.mkdtemp()` 的临时目录和临时 `cards.json`，不读写真实卡密库；只在最后对 v1 两个文件做只读 sha256 校验。

覆盖：

| # | 内容 | 结果 |
|---|---|---|
| 1 | `user_id_normal('11111111111') == 314816420`、public 区间/唯一性/无交集 | 5/5 |
| 2 | 旧卡（无 kind）行为、旧 token、过期、bind_one、无 bind_one | 13/13 |
| 3 | `/auth/verify` 正例、篡改 token、未知 DevId、空参数、过期 | 5/5 |
| 4 | `/admin/unbind` 后立即 `device_revoked`、不计自助次数、重复解绑 | 5/5 |
| 5 | `max_devices=2` 第 3 台拒绝、`max_devices=0` 不限 | 6/6 |
| 6 | 公益卡过期仍通过、5 台设备、token、quick-login、跨设备 token | 8/8 |
| 7 | 自助解绑 remaining/cooldown/limit/not_bound/unknown_card/limit=-1 | 14/14 |
| 8 | `/admin/issue` 字段、public、重复、非法 Kind、默认值 | 9/9 |
| 9 | admin 无 key/错 key/未配置环境变量 | 4/4 |
| 10 | 3 线程并发解绑后 JSON 合法、计数正确、无临时文件 | 5/5 |
| 11 | v1 七条路径 + GET + 未知路径 + 未知设备 | 9/9 |
| 12 | 外部改 `cards.json` 后 mtime 缓存立即失效 | 1/1 |
| 13 | v1 `sdkcard.py` / `cards.json` sha256 不变 | 2/2 |

关键输出（原文摘录）：

```text
=== 1. 身份公式验算 ===
  _h8('11111111111')                    = 2914816420
  h % 900000000               = 214816420
  旧公式 100000000 + h%9e     = 314816420
  新公式 100000000 + h%4.5e   = 314816420
  user_id_public('09a4d0ab0ee93616') = 853248039
[OK]   1.1 user_id_normal(11111111111) == 314816420 == 旧值

=== 2. 旧卡行为不变（11111111111 / 09a4...）===
  login: HTTP 200 Code=200 ID=314816420 Token=61de1d1b7519ab1231866f74c11fcfdd1f80b210 Nick=BA1111
[OK]   2.2 旧卡 User.ID == 314816420
[OK]   2.3 旧卡 Token == 61de1d1b...b210
[OK]   2.7 旧 token 在 /auth/verify 通过（无 kind 字段按 normal）

=== 3. /auth/verify 正反例 ===
  改一个字符: {'ok': False, 'Reason': 'device_revoked'}
  不存在的 DevId: {'ok': False, 'Reason': 'unknown_identity'}
  过期普通卡: {'ok': False, 'Reason': 'expired'}

=== 4. admin unbind 后立即失效 ===
  解绑后 verify: {'ok': False, 'Reason': 'device_revoked'}

=== 6. 公益卡：不限期 + 不限设备 ===
  公益卡已记录设备: ['pub-run-0', 'pub-run-1', 'pub-run-2', 'pub-run-3', 'pub-run-4']

=== 10. 3 线程并发自助解绑 ===
  并发结果: [('conc-1', 200, {'ok': True, 'remaining': 98}), ...]
[OK]   10.3 并发写后 cards.json 仍是合法 JSON

=== 13. 原始 v1 文件未被修改 ===
[OK]   13.1 work/ba/bapatch/sdkcard.py sha256 不变
[OK]   13.2 work/ba/bapatch/cards.json sha256 不变
```

说明：两套锁分支都实际跑过——Windows 走 `msvcrt.locking`，WSL Ubuntu 24.04 走 `fcntl.flock`（含 3 线程并发自助解绑）。线上是 Linux，与 WSL 分支一致；`cards.json` 所在文件系统需支持 `flock`（本地盘/常规 ext4 都可以，NFS 除外）。

---

## 12. 交付校验

| 文件 | 字节 | sha256 |
|---|---:|---|
| `work/ba/sdk/sdkcard_v2.py` | 35701 | `e4884f66057dc4e102e8af3eaf7096722a8a1b1f61dbb37301bee653bcbdde45` |
| `work/ba/sdk/selftest_sdkcard_v2.py` | 35186 | `eef9ee977f828b3eb4bca73837a21b86e4601bbf39c3f0885924efca0fc7a3ed` |
| `work/ba/sdk/SDKCARD_V2.md` | — | 见交付回执 |
| `work/ba/bapatch/sdkcard.py`（v1，未改） | — | `AFAEC5637C63C56093A677FE4255D5D6A31AF6101B475A5928D719A3D6D819AE` |
| `work/ba/bapatch/cards.json`（v1，未改） | — | `8AD2AE17E9197102D65E2D8563B3616CA622E13A873E123B486620C9413856B3` |

---

## 13. 已知限制 / 运维注意

1. **PHP cron 冲突**：见 §9；全功能上线前必须解决。
2. **高半区旧 ID**：见 §1.4；上线前跑审计。
3. **没有限流**：`/auth/self-unbind` 暴露给玩家时，建议 nginx `limit_req`；`/admin/*` 建议只允许 127.0.0.1 或 `deny all`（PHP 在同一个机器上直接调 127.0.0.1:8080 即可）。
4. **admin key 轮换**：改 `sdkcard.env` 后 `systemctl restart ba-sdk`；不要把 key 写进代码/仓库。
5. **`/auth/verify` 日志量**：每次调用一行 `[v2] AUTH VERIFY`；高频网关建议 logrotate。
6. **5 秒缓存**：mtime/size 变了立即失效；如果放在 NFS 上且 mtime 不可靠，建议把 `CACHE_TTL` 调 0 或把 `cards.json` 放本地盘。
7. **单一写入者**：v1 与 v2 不能同时监听 8080；v2 与 PHP cron 同时写会丢更新（§9）。
8. **public 同设备同 ID**：见 §1.5；运营上不要把多张公益卡当成多账号。
9. **public 的 `devices` 会无限增长**：因为不限制设备数；定期清理或接受。
10. **`/admin/issue` 不能更新已有卡**：改 `max_devices`/配额用 §8.3 的脚本。
11. **Token 长度不强制 40**：非 40 位 token 只要身份对上就会被判 `device_revoked`，不会单独报 `bad_request`；`bad_request` 只用于缺失/空/类型错误。
12. **过期 vs 解绑优先级**：先比 token，token 不对就是 `device_revoked`；token 对但过期才是 `expired`。
13. **后端错误**：新接口返回 503 + `backend_error`，这是额外运维态；网关应短重试 + 告警，不要当成卡密错误。
14. **`cards.json.lock`**：服务自动创建，用来做跨进程写锁；不要删、不要提交到仓库。
15. **无自动备份**：v1 也没有；上线前手工备份，必要时用 `cards.json.bak.<ts>` 恢复。
16. **Python 版本**：v2 只用标准库，要求 Python 3.7+（`ThreadingHTTPServer` / `from __future__ import annotations`）；本机 3.12.14 实测通过。
