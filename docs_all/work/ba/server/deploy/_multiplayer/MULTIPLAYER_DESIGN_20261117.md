# 多玩家 / 账号体系 / 卡密表改造 设计方案（2026-11-17）

> 作者：shittim-analyst · 独占目录 `work\ba\server\deploy\_multiplayer\`
> 纪律：**只读现有服务端代码**；本文件只给 `文件:行号 + 补丁片段`，**不改任何现有文件**
> 依据文件：`work\ba\bapatch\sdkcard.py`、`work\ba\cardadmin_php\inc\sync.php`、`work\ba\bapatch\cards.json`、`work\ba\server\account_service.py`、`work\ba\server\schema_v2.sql`、桥接 `_bridge_ref/account_auth_probe.py`

---

## 0. ★ 真实卡点（srv-ops 2026-11-17 只读实测，直接改写了本方案的形态）

### 0.0 一句话

> **分流机制在、开关开着、库里已有 2 个账号（`server_id` 10000000000 / 10000000001）——
> 但因为拿不到稳定身份键，`acct_apply_to_auth()` 每次都走 `except` 退回硬编码 UID/TOKEN。
> 这不是"逻辑缺失"，是"身份键没接上"，而且是 2 行代码就能接上的那种。**

原始口径（`_blackout\srv\SRV_FINDINGS_20261117.md` + `acct_svc.log` 18:32 / 18:37）：

```
account_auth_probe.py:76   import account_service as _m      ← 服务已接入
account_auth_probe.py:1737 inner = acct_apply_to_auth(inner, rec)
/www/wwwroot/bapatch/cn_account_svc.txt = 1                   ← 开关开着
accounts.db: 2 行（server_id 10000000000 / 10000000001）      ← 分流确实成功过
acct_svc.log: [acct] fallback to hardcoded: 既没有 DevId 也没有 DeviceUniqueId
```

### 0.1 `rec` 是怎么构造的（问题 1）

`work\ba\server\deploy\_baseline\account_auth_probe.py`（与线上同源，行号以该副本为准；线上对应位置需 srv-ops 用注释串定位）：

```python
98   def acct_apply_to_auth(inner, rec):
101      if not acct_svc_on():                       # cn_account_svc.txt 开关
102          rec['acct_svc'] = 'off'; return inner
106      req = _req_dict(rec)                        # ★ 主路径：从 rec['req_frag_head'] 解析
107      if not req:
108          req = {'DevId': rec.get('req_DevId') or '', 'Token': rec.get('req_Token') or ''}
109      ident = svc.identify(req)                   # ★ 这里抛「既没有 DevId 也没有 DeviceUniqueId」
110      acct = svc.get_or_create_account(ident)
111      sess = svc.issue_session_key(acct)
112      adb  = svc.build_account_db_for(acct)
114      inner['AccountDB'] = adb                    # ← 真值回填 Account_Auth 响应
115      inner['SessionKey'] = sk
116      _LAST_SID = adb.get('ServerId')
```

`_req_dict(rec)`（`:82-95`）只读一个来源：

```python
82   def _req_dict(rec):
84       frag = (rec.get('req_frag_head') or '').strip()
85       if not frag: return {}
87       body = frag.lstrip(',')                     # 国服片段以 ',' 开头
89       if not body.startswith('{'): body = '{' + body
91       if not body.endswith('}'):   body = body + '}'
93       return json.loads(body)
```

而 `req_frag_head` **只在 CN 解密成功的那一条分支里被赋值**（`:1106-1119`）：

```python
1106  if r is not None:                               # r = CN 信封解密结果
1107      rec['decrypted'] = True
1112      req_json = r.get('json')
1113      if isinstance(req_json, dict):
1116          rec['req_frag_head'] = str(r.get('fragment'))[:600]   # ★ 唯一写入点
1119          rec['req_Token'] = req_json.get('Token')
1120          rec['req_Hash']  = req_json.get('Hash')
```

### 0.2 为什么 18:32 那两次是空的（问题 2）—— **是桥自己丢了，不是客户端没发**

`[源码实测]` 两条结构性原因，**互不排斥**：

1. **`rec['req_DevId']` 是死代码**：全文件 grep，`req_DevId` **只有 `:108` 一处读取，没有任何写入点**。
   所以一旦 `req_frag_head` 为空，`:108` 的兜底字典里 `DevId` 恒为 `''` ⇒ `identify()` 必然抛。
2. **`req_frag_head` 只有一个写入点且失败即清空**（`:1116` 成功 / `:1118` `''`）⇒ **只要那一轮的 CN 信封没解出来（`r is None`，走 `:1104` `rec['decrypt_err']`），DevId 就彻底拿不到**。

而**客户端是发的**：`[团队实测]` 国服 `Account_Auth` 明文里明确有 `"DevId":"314816420"`（`report\35:55` 的 11 键明文），只是桥在"没解密成功"的那条路径上把它丢了。

⇒ **判别方法（给 srv-ops 的一条 grep）**：在 18:32/18:37 那两条请求的日志记录里看
- `decrypted == true` 且 `req_keys` 含 `DevId` ⇒ 是 `identify()`/兜底逻辑问题（本文件 §0.4 的补丁 1 就够）
- `decrypt_err` 存在 或 无 `decrypted` 字段 ⇒ 那一轮根本没解密（**先修解密/那条分支**，否则补丁 1 无效）

### 0.3 `DevId = md5(card)[:8]` 这条路（问题 4）—— **它天然稳定，而且已经被验证过了**

| 事实 | 证据 |
|---|---|
| `sdkcard.py:43` `tpl['User']['ID'] = int(md5(card).hexdigest()[:8], 16) % 900000000 + 100000000` | 卡密 → `User.ID` 是**确定性映射**，同卡恒同值 |
| 客户端把 `User.ID` 当 `DevId` 发（`Account_Auth` 明文 `"DevId":"314816420"`） | `report\35:55` |
| **`md5('11111111111')[:8] → 314816420`**（本轮实算） | **= 桥里硬编码的 `UID`（`_bridge_ref:62`）** |

⇒ **结论：`DevId` 一直是稳定的；硬编码的 `314816420` 就是测试卡 `11111111111` 的 `DevId`。**
"没有 DevId"**不是**因为 SDK 传空，而是因为**桥在非解密分支上没把它记录下来**。换卡即换 `DevId` ⇒ 换 `server_id` ⇒ **天然一卡一号**（这正是 ② 想要的）。

### 0.4 最小接线：**2 处 / +3 行**

> 均在桥接 `account_auth_probe.py`（srv-ops 独占文件，我只给片段；行号用 `_baseline` 副本，线上用 `req_Token`/`req_Hash` 那两行做锚点定位）

**补丁 1 —— 把 DevId/DeviceUniqueId 记进 `rec`（`_baseline:1119` 之后）**

```python
1119          rec['req_Token'] = req_json.get('Token')
                rec['req_DevId'] = req_json.get('DevId') or ''                    # +1
                rec['req_DeviceUniqueId'] = req_json.get('DeviceUniqueId') or ''  # +2
1120          rec['req_Hash']  = req_json.get('Hash')
```

**补丁 2 —— 兜底字典补上 DeviceUniqueId（`_baseline:108`）**

```python
108      req = {'DevId': rec.get('req_DevId') or '',
                'DeviceUniqueId': rec.get('req_DeviceUniqueId') or '',             # +3
                'Token': rec.get('req_Token') or ''}
```

**可选加固（不建议本轮做）**：`_req_dict` 失败时，用 `Token` 反推一个稳定键（`"tok:" + sha1(token)[:16]`）作为 `dev_id`——但那是"设备/卡密指纹"，与卡密换绑语义不同，会造出新账号，**先不做**。

**验收判据（3 条，全部来自现有日志字段）**
1. `acct_svc.log` 不再出现 `fallback to hardcoded`；
2. `api_all_requests.log` 里 `acct_svc='on'` 且 `acct_server_id` 出现**多个不同值**（换卡应换号）；
3. `accounts.db` 行数随测试卡数量增长（现有 2 行 → N 行）。

### 0.5 本卡点对后文方案的影响

| 原方案 | 修正后 |
|---|---|
| ②"缺口 3 处" | **降级为 1 处（身份键落库）+ 1 处开关语义**：分流代码、`get_or_create_account`、会话、21 个 blob **全是现成的**，不需要重写 |
| ②路线 A（`publisherId = server_id`） | **仍然成立且更简单**：`acct_apply_to_auth` 已经把 `AccountDB`/`SessionKey` 回填进 1002 响应（`:114-115`），只要 `DevId` 稳定，Shittim 侧按 `server_id` 建号即可 |
| ①token 签名 | **优先级下降**：签名解决的是"凭证可信"，而当前卡点是"身份没落库"。**建议顺序改为：§0.4 两行 → 观察多账号 → 再做 ①** |
| ④面板 | 不变：`accounts.db` 已有 `server_id` 台账，正好当玩家维度的主键 |

---

## 0.6 现状核对（我先读到的，与任务书一致的部分只列结论）

| 事实 | 证据 |
|---|---|
| token = `sha256(card + '|' + device)[:40]`，**无密钥/无签名/无有效期** | `bapatch\sdkcard.py:41` `tok = hashlib.sha256((card + '|' + device).encode()).hexdigest()[:40]` |
| `User.ID` 只由卡密决定：`md5(card)[:8] → 100000000..999999999` | `sdkcard.py:43` |
| 设备 ID 取自请求头 `DeviceID` | `sdkcard.py:30-34` |
| 卡密库是**单个 JSON 文件**，面板只写 MySQL，cron 导出 | `sdkcard.py:10` `CARDS='/root/bapatch/cards.json'`；`sync.php:3-8` 头注释 |
| `cards.json` 结构（三字段） | `bapatch\cards.json`：`{"cards":{"<card>":{"devices":[],"expire":0,"bind_one":true}}}` |
| 导出时**只取 4 列、只吐 3 键** | `sync.php:227` `SELECT id, card_key, expire_at, bind_one`；`sync.php:186-187` 只映射 `expire`/`bind_one` |
| 桥接身份硬编码 | `_bridge_ref\account_auth_probe.py:62-64` `UID/TOKEN/ENTER_TICKET`；`:1001` 仅把请求里的 `Token` 记进日志 |

### ★ 一个必须先说清的发现：**账号分流其实已经实现了**

`work\ba\server\account_service.py`（1853 行）**本身就是多账号服务**：

| 能力 | 位置 |
|---|---|
| `server_id` 从 `10_000_000_000` 起发（对齐官方 11 位账号号量级） | `:59` `DEFAULT_SERVER_ID_BASE = 10_000_000_000` |
| 实体 id 分带（每账号 10 万个，跨账号不撞） | `:59-61` `ENTITY_ID_BASE/STRIDE`、`:72-80` 的 BANDS 说明 |
| `get_or_create_account(identity)`：按 `dev_id` 查/建，建号同时写 21 个初始 blob | `:513-586`（INSERT `:582`） |
| `issue_session_key()`：uuid4 → 36 字符 GUID，写 `sessions` 表 | `:677-705`（INSERT `:700`） |
| `resolve_session()`：大小写不敏感的会话校验 | `:707-` |
| 表结构（`accounts` / `sessions` / `account_blobs` / `id_alloc` / `protocol_log`） | `work\ba\server\schema_v2.sql` R1/R2/R3 + `schema_sqlite.sql` v1 |

⇒ **缺的不是"分流逻辑"，而是"桥接没有接上它"**。这决定了方案②的形态：**接线，不是重写**。

---

# ① token 真校验方案

## 1.1 目标

`token` 从「身份指纹」升级成「**带签名、带有效期、带绑定信息**的凭证」，且：

- **PHP 卡密站能签发**（`/user/login`、`/user/quick-login`）
- **桥接能离线验签**（不查库、不回调 PHP，避免每包一次 HTTP）
- 换设备 / 过期 / 超台数 ⇒ 验签失败，且**失败原因可区分**

## 1.2 令牌格式（`v2`）

```
BA2.<b64url(payload)>.<b64url(hmac_sha256(key, "BA2." + b64url(payload)))>
```

`payload` = JSON（紧凑、无空格）：

```json
{"v":2,"c":"11111111111","d":"09a4d0ab0ee93616","k":0,"m":1,
 "uid":1389321844,"iat":1763400000,"exp":1765989600,"j":"3f9a1c7e2b8d4f60"}
```

| 字段 | 含义 | 说明 |
|---|---|---|
| `v` | 版本 | 2 = 新格式；缺省/1 = legacy 指纹 |
| `c` | 卡密明文 | 需要（桥接要用它做 `ENTER_TICKET` 的 uid/token 源） |
| `d` | 设备 ID | 绑定的 `DeviceID` |
| `k` | 卡密类型 | `0`=普通（跟随卡密）、`1`=公益卡（跟随设备） |
| `m` | 允许台数 | `0` = 不限 |
| `uid` | 桥接/客户端用的数字 id | 继续沿用 `md5(card)[:8]` 的算法，保证**老玩家账号不迁移** |
| `iat/exp` | 签发/过期（unix 秒） | `exp=0` 表示不限期 |
| `j` | 令牌随机串（16 hex） | 防同一秒内同输入产出相同 token（重放谱系追踪） |

**签名算法**：`HMAC-SHA256`，key 为 32 字节随机串（hex 64 字符）。
**为什么不是 RSA/Ed25519**：两边都要能实现、且只需要"我签发我验证"，对称 HMAC 足够；PHP 有 `hash_hmac`，Python 有 `hmac`，零依赖。

## 1.3 密钥存放

| 位置 | 用途 | 权限 |
|---|---|---|
| `/www/wwwroot/ba_cardadmin/inc/token_key.php` | PHP 签发/校验读它（**唯一真源**） | `0640 www:www` |
| `/root/bapatch/token_key` **或** `/www/wwwroot/bapatch/token_key` | 桥接离线验签读它 | `0640 root:root`（桥接以 root 跑） |

```php
<?php // inc/token_key.php —— 由运维生成后写入，不进 git
return ['kid' => 'k1', 'key' => '<64 hex chars>'];
```

> **轮换**：`token_key.php` 允许是 `['k1'=>hex, 'k2'=>hex, 'current'=>'k2']`，验签时按 `kid` 选 key，**双 key 并存 48 小时**后删旧。
> 桥接侧同样支持多 key（按 token 里的前缀不含 kid ⇒ 用 `current` + 旧 key 依次试）。

## 1.4 有效期与绑定

| 卡密类型 | `exp` | 绑定维度 | 台数校验 |
|---|---|---|---|
| **普通卡**（`k=0`） | `expire_at`（0 = 不限期） | **卡密 + 设备**（`c` + `d` 都进签名） | `m`（`max_devices`）；`m=1` 即"一卡一机" |
| **公益卡**（`k=1`） | `0`（不限期） | **仅设备**（`c` 可以为空或公共标识，签名仍覆盖 `d`） | `0`（不限） |

**关键设计点：普通卡换设备怎么办？**
`d` 进签名 ⇒ 换设备后旧 token 立刻失效。这**正是我们要的**：设备绑定是卡密站授权的一部分。
换设备的唯一合法路径 = 重新走 `/user/login`（用卡密 + 新设备 ID 重新签发）。

## 1.5 防重放

1. **`exp`**：令牌自带过期，桥接验签时校验 `now <= exp`（`exp=0` 跳过）；建议 `exp = min(card.expire_at, now+30d)`，避免"不限期卡"产生永久凭证。
2. **`j` 随机串 + 服务端吊销表**：卡密站维护一张 `token_revocations(j, revoked_at)`（或直接复用 `devices` 表：`d` 不在该卡的设备列表里 ⇒ 拒绝）。
3. **桥接侧不存储状态**：只做「签名有效 + 未过期 + `d` 与当前请求 `DeviceID` 一致」，**不查库**；吊销靠"PHP 不再签发新 token + `d` 不匹配"自然生效（旧 token 仍会活到 `exp`，可把 TTL 设短，例如 7 天，客户端每次登录都重新取）。
4. **不引入 nonce 缓存**：桥接是无状态代理，加 nonce 表会破坏"离线校验"目标；用短 TTL 换取简单性。

## 1.6 改动点清单

| # | 文件 | 位置 | 改动 |
|---|---|---|---|
| 1 | `/www/wwwroot/ba_cardadmin/inc/token_key.php` | **新增** | 存放 HMAC key（见 1.3） |
| 2 | `/www/wwwroot/ba_cardadmin/inc/token_v2.php` | **新增** | `ba_token_issue(array $card, string $device): string` / `ba_token_verify(string $token): ?array`（纯函数，无 DB） |
| 3 | `/www/wwwroot/ba_cardadmin/inc/sync.php` | `:186-187`（组装 `expire`/`bind_one`）+ `:227`（SELECT 列） | 追加 `kind`/`max_devices` 输出与查询（见 ③） |
| 4 | `work\ba\bapatch\sdkcard.py`（**srv-ops 的文件，我只给片段**） | `:41` token 计算处 | 改为：优先返回 PHP 已签发的 token；若请求里没有，则**本地按同算法签发**（读同一个 key 文件），保留 legacy 分支 |
| 5 | 桥接 `account_auth_probe.py` | `:62-64` | `ENTER_TICKET` 改为由 token 解出的 `uid/token` 生成（见 ②） |

### 伪代码（桥接侧验签，Python）

```python
def token_verify(tok: str, device: str) -> dict | None:
    parts = tok.split('.')
    if len(parts) != 3 or parts[0] != 'BA2':
        return legacy_verify(tok, device)          # v1 指纹：只比对 sha256(card|device)[:40]
    body, sig = parts[1], parts[2]
    for key in load_keys():                        # 多 key：current 优先
        want = b64url(hmac.new(key, ("BA2." + body).encode(), sha256).digest())
        if hmac.compare_digest(want, sig):
            p = json.loads(b64decode(body))
            if p.get('exp') and time.time() > p['exp']:
                return None                        # 过期
            if p.get('d') != device:
                return None                        # 换设备
            return p
    return None
```

### 风险

| 风险 | 缓解 |
|---|---|
| key 泄露 ⇒ 任何人可伪造 token | key 只在两个 root 可读文件里；轮换双 key 机制；PHP 侧不返回 key |
| 桥接与 PHP 的 base64url 实现不一致（padding） | 统一 `rstrip('=')`，`+/` → `-_`，两端各写一个自测用例 |
| 老客户端仍发 legacy token | **保留 legacy 分支**，只在 `BAPATCH-MU=1` 时强制 `BA2`（灰度） |
| `exp` 太短导致玩到一半掉线 | 令牌只在登录时用，**游戏会话用 `MxToken`**（account_service 的 uuid4，独立 TTL）⇒ 令牌过期不影响在线玩家 |

### 回滚

删 `token_v2.php` + 把 `sdkcard.py:41` 还原 → 秒回 legacy。令牌格式自带版本前缀，桥接的 `legacy_verify` 分支不需要改。

---

# ② 账号分流方案（多玩家核心）

## 2.1 `account_service` 已经做了什么 / 还差什么

| 环节 | 现状 | 结论 |
|---|---|---|
| 身份 → 账号 | `get_or_create_account(Identity)`，按 `dev_id` 查/建（`account_service.py:513-586`） | ✅ **现成** |
| `server_id` 分配 | `10_000_000_000` 起、`id_alloc` 表 | ✅ 现成 |
| 会话 | `issue_session_key` / `resolve_session`（`:677`, `:707`） | ✅ 现成 |
| 初始存档 | `bootstrap_state` 写 21 个 blob（`:582-586`） | ✅ 现成 |
| **桥接是否调用它** | ❌ **完全没调用**：桥接用 `UID/TOKEN/ENTER_TICKET` 硬编码（`account_auth_probe.py:62-64`），SessionKey 自己铸 | ❌ **缺口** |
| **`dev_id` 从哪来** | ❌ 桥接从没把"token→身份"接进来，`Token` 只被记录（`:1001`） | ❌ **缺口** |
| **`BAPATCH-MU` 开关** | ❌ 全仓 grep 无实现（`_bridge_ref` 里 0 命中） | ❌ **缺口** |

⇒ **缺口 = 3 处**（接线、身份来源、开关）。

## 2.2 目标链路

```
客户端 /user/login(card, DeviceID)
   └─> PHP 校验卡密/过期/台数 ──> 签发 BA2 令牌（含 uid）
        └─> 客户端把它当 SDK token 用
             └─> 桥接收到请求（CN 信封里带 Token/DevId）
                  ├─ token_verify() → {c(卡密), d(设备), uid}
                  ├─ identity = Identity(dev_id=<稳定数字身份>)      ← 见 2.3
                  ├─ account = account_service.get_or_create_account(identity)
                  ├─ sk = account_service.issue_session_key(account)
                  └─ 转发 Shittim 时：SessionKey = {AccountServerId: account.server_id, MxToken: sk.mx_token}
```

## 2.3 `dev_id` 用什么（**关键决策**）

| 候选 | 稳定性 | 多设备同卡 | 与现有账号兼容 | 结论 |
|---|---|---|---|---|
| 卡密原文 | 极高 | 同卡多设备 → 同账号（符合"一卡一号"） | ✅ 现有 `md5(card)` = 同值 | **推荐（普通卡）** |
| 设备 ID | 中（换机换号） | 同卡多机 → 多账号（**不符合**） | ❌ | 公益卡才用 |
| 卡密+设备 | 中 | 同卡多机 → 多账号 | ❌ 老玩家账号会漂移 | 不采用 |

⇒ **`dev_id = str(uid)`**，其中 `uid` 就是签名里的 `md5(card)[:8]`（`sdkcard.py:43` 的同一算法）。
**这样老玩家的 `dev_id` 不变、`server_id` 不变、存档不迁移**，且天然"一卡一号"。
公益卡（`k=1`）：`dev_id = "PUB-" + md5(device)[:8]`，每人一档，不占卡密绑定。

## 2.4 `BAPATCH-MU` 怎么开

新增运行时开关（与既有 `BAPATCH-MU=0` 环境变量/文件同源），**三种取值**：

| 值 | 行为 |
|---|---|
| `0`（默认） | 完全走旧路径：硬编码 UID/TOKEN，会话自铸 ⇒ **现状不变** |
| `1`（灰度） | 走 account_service 分流，但 **legacy token 也接受**（按旧 UID 映射） |
| `2`（严格） | 只接受 `BA2` 签名令牌；无签名 ⇒ 403 |

伪代码（桥接，插入在 `account_auth_probe.py` 处理 `Account_CheckNexon/Auth` 之前）：

```python
if os.getenv('BAPATCH-MU', '0') != '0':
    p = token_verify(req.get('Token') or '', req.get('DeviceUniqueId') or '')
    if p is None and MU_MODE == '2':
        return 403, b'{"error":"bad token"}'
    dev_id = str(p['uid']) if p else legacy_dev_id(req)   # 灰度兼容
    acct = SVC.get_or_create_account(Identity(dev_id=dev_id))
    sk   = SVC.issue_session_key(acct)
    ENTER_TICKET = b64(("%d/%s" % (acct.server_id, sk.mx_token)))
```

## 2.5 开了之后会不会互相踩数据？

| 层面 | 是否共享 | 结论 |
|---|---|---|
| `account_service` 的 `accounts/sessions/account_blobs` | 表共享，**行按 `server_id` 隔离**（`schema_v2.sql` R2：每表都有 `server_id` + FK CASCADE） | ✅ 不踩 |
| **Shittim 的 `schale.sqlite3`** | ❗**现在只有 2 个账号行**（`Accounts` 2 行、`UserAccounts` 1 行） | ⚠ **会踩**：桥接若仍用**同一个** `publisherId`（`314816420`），所有玩家都会落到 `Accounts.ServerId=2` 这一行 |
| 实体 id（角色/咖啡厅） | `account_service` 分带（每账号 10 万） | ✅ 不踩 |
| 会话 | `sessions` 表按 `mx_token`；Shittim 侧另有自己的 `sessions.json` | ⚠ **两套会话**必须二选一（见下） |

**⇒ 真正的踩踏点在 Shittim，不在 account_service。** 两条可选路线：

- **路线 A（推荐，最小改）**：让桥接把 `ENTER_TICKET` 的 `publisherId` 换成 **`account.server_id`**（而不是常量 `314816420`）⇒ Shittim 自动为每个 `server_id` 建 `Accounts` 行（`AccountHandler.cs:68-89` 自动建号 + `:935` 初始化）。**Shittim 一行代码不用改。**
- **路线 B**：桥接继续用 Shittim 的 `SessionKey`，让 `account_service` 只管"业务存档"，两套身份并存 ⇒ **两个真源，必然打架**（青辉石 600/7000 那种）。**不推荐。**

## 2.6 改动点清单

| # | 文件 | 位置 | 改动 |
|---|---|---|---|
| 1 | 桥接 `account_auth_probe.py` | `:62-64` | `UID/TOKEN/ENTER_TICKET` 改为函数 `identity_from_request(req)` 的返回值 |
| 2 | 同上 | `Account_CheckNexon` 处理入口 | 插入 2.4 的分流块（`BAPATCH-MU` 开关） |
| 3 | 同上 | `:1001` | `rec['req_Token']` 之外补 `rec['mu_uid']/rec['mu_server_id']/rec['mu_mode']`（可观测） |
| 4 | `account_service.py` | **不改** | 现状已够用；若要多玩家统计，另加只读查询 |

## 2.7 风险 / 回滚

| 风险 | 缓解 |
|---|---|
| 老玩家 `dev_id` 变化 ⇒ 新建账号丢档 | `dev_id = str(md5(card)[:8])` 与旧 UID 同值 ⇒ **不漂移**（上线前必须用现有测试卡验一次 `get_or_create_account` 命中旧行） |
| 两套会话打架 | 路线 A 下 **只用 Shittim 的会话**（`ENTER_TICKET` 由桥接按 `server_id` 铸），`account_service.issue_session_key` **不参与**协议层，只用于管理面板 |
| `BAPATCH-MU=1` 灰度期新旧混用 | 灰度期只接受"能解析出 legacy UID"和"BA2 有效"两类，其余 403；观察 1 天后切 `2` |
| 并发首登双开 | 见 SHITTIM_ROOT_PLAN §9.6：对同一 `dev_id` 加互斥（`accounts` 表 `UNIQUE(dev_id)` 已在 `:582` 附近兜底） |

**回滚**：`BAPATCH-MU=0` 一行 → 完全回到现状（硬编码）。数据层无破坏性写入（account_service 只新增行）。

---

# ③ 卡密表改造方案

## 3.1 要加什么

| 用途 | 新列 | 类型/默认 | 说明 |
|---|---|---|---|
| 卡密种类 | `kind` | `TINYINT NOT NULL DEFAULT 0` | `0`=普通（跟随卡密）、`1`=公益（跟随设备） |
| 绑定台数 | `max_devices` | `INT NOT NULL DEFAULT 1` | `0`=不限；普通卡常用 1 |
| （可选）备注 | `note` | `VARCHAR(64) NULL` | 面板显示 |

**只加 2 张列（`kind` / `max_devices`）**，其余复用现有 `bind_one` / `expire_at`。

> `bind_one=true` 与 `max_devices=1` 语义重叠 ⇒ **保留 `bind_one` 不动**（向后兼容），新逻辑以 `max_devices` 为准；`max_devices` 缺省时按 `bind_one ? 1 : 0` 推导。

## 3.2 DDL 与迁移

```sql
ALTER TABLE cards
  ADD COLUMN kind        TINYINT NOT NULL DEFAULT 0,
  ADD COLUMN max_devices INT     NOT NULL DEFAULT 1;
-- 迁移：现有卡默认 kind=0 / max_devices = IF(bind_one, 1, 0)
UPDATE cards SET max_devices = IF(bind_one = 1, 1, 0) WHERE max_devices = 1;
```

## 3.3 `sync.php` 改哪两处

| 位置 | 现在 | 改成 |
|---|---|---|
| `sync.php:227` | `SELECT id, card_key, expire_at, bind_one` | `SELECT id, card_key, expire_at, bind_one, kind, max_devices` |
| `sync.php:186-187` | 只映射 `expire`/`bind_one` | 追加 `'kind'=>$r['kind'], 'max_devices'=>$r['max_devices']` |

**⚠ 这就是"每分钟被冲掉"的根因**：`sync.php:186-187` 每次只吐 3 个键 ⇒ **任何手工加进 `cards.json` 的字段都会在 60 秒内消失**。所以**必须改 sync.php**，不能只改 json。

## 3.4 `cards.json` 升级到 v2（**向后兼容是硬要求**）

```json
{
 "version": 2,
 "generated_at": 1763400000,
 "cards": {
  "11111111111": {"devices":["09a4d0ab0ee93616"], "expire":0, "bind_one":true, "kind":0, "max_devices":1},
  "PUB0001":     {"devices":["aa11bb22cc33dd44"], "expire":0, "bind_one":false,"kind":1, "max_devices":0}
 }
}
```

**兼容规则（两个方向）**

| 方向 | 规则 |
|---|---|
| 新 `cards.json` → 老解析器（`sdkcard.py` 未升级） | 多出 `version/generated_at/kind/max_devices` 键 ⇒ 老代码只读 `devices/expire/bind_one`，**忽略即可**（`sdkcard.py:20-27` 是 `json.load` 后按键取值，不校验多余键） |
| 老 `cards.json`（无 `version`）→ 新解析器 | 缺 `version` 视为 1；缺 `kind` → 0；缺 `max_devices` → `bind_one ? 1 : 0` |

**现有测试卡不坏**：`11111111111` / `22222222222` 两条在 v2 里只多两个键，行为不变（`max_devices=1` 对 `bind_one=true` 是等价的）。

## 3.5 台数校验落点（`sdkcard.py`）

`/user/quick-login`（已绑定设备放行）需改成：

```python
rec = cards['cards'].get(card)
if not rec: return deny('no such card')
devs = rec.get('devices', [])
maxd = rec.get('max_devices', 1 if rec.get('bind_one') else 0)
if dev not in devs:
    if maxd != 0 and len(devs) >= maxd:
        return deny('device limit reached')      # 台数满
    devs.append(dev); save_cards(cards)          # 绑新设备
```

> 注意：`sdkcard.py` 自己会写 `cards.json`（`sync.php:8` 注释已提示"非原子，历史行为"），而 `sync.php` 下次导出会把它合并回 MySQL（`sync.php:102/201` 的 `import_devices`）。**新增字段不参与这个回写**，无冲突。

## 3.6 风险 / 回滚

| 风险 | 缓解 |
|---|---|
| `ALTER TABLE` 锁表 | `cards` 表行数极小（测试期 2 行）；直接 `ALTER` 即可 |
| `sync.php` 改错导致导出失败 | 先 `sync.php` 的 `sync_build(no_mutate=true)` 干跑一次比对输出 |
| 面板写库后被 cron 覆盖 | 改完 `sync.php` 后新增列会随导出保留；**面板写入后等 ≤60 s 生效** |
| 回滚 | `ALTER TABLE cards DROP COLUMN kind, DROP COLUMN max_devices;` + `sync.php` 还原两处 ⇒ 老版本 `cards.json` 会立刻把新键冲掉（这正是我们要的回滚路径） |

---

# ④ 管理面板「玩家维度」数据方案

## 4.1 两个库

| 库 | 路径 | 内容 |
|---|---|---|
| **认证库** `accounts.db` | `work\ba\server\ba_accounts.sqlite3`（由 `schema_sqlite.sql` + `schema_v2.sql` 建） | `accounts`（`server_id`/`dev_id`/`sdk_token`/`last_login_at`）、`sessions`、`account_blobs`、`protocol_log` |
| **游戏库** `shittim.sqlite3` | `/www/wwwroot/ba_srv/schale.sqlite3`（`SchaleDataContext` 默认 `Data Source=schale.sqlite3`） | `Accounts`（`ServerId`/`PublisherAccountId`）、`Characters`、`Currencies`、`Mails`… |

**关联键**：`accounts.db.accounts.server_id` ↔ `shittim.Accounts.ServerId`
（路线 A 下 `publisherId == server_id`，见 ②2.5）

## 4.2 跨库读取方案（三选一，推荐 A）

| 方案 | 做法 | 优点 | 缺点 |
|---|---|---|---|
| **A. `ATTACH` 只读连接（推荐）** | 面板用一个 `sqlite3` 连接 `file:accounts.db?mode=ro`，再 `ATTACH DATABASE 'file:schale.sqlite3?mode=ro' AS game;` | 零复制、实时 | 需要同一台机；`ATTACH` 需可写 `-wal`/`-shm` 目录（`mode=ro` 下略有兼容问题）⇒ 用 `mode=ro` + `immutable=1` 更稳 |
| B. 物化视图表 | 每天把 `game.Accounts/Characters/Currencies` 摘要同步进 `accounts.db.player_view` | 面板查询快、跨机也行 | 有延迟 |
| C. 服务层聚合 | 面板调 Shittim 的 `/gm/*`（若可用） | 无 SQL 耦合 | 现有 GM 端点未验证 |

**推荐 A + B 兜底**：实时查询用 A；面板列表页读 B 的 `player_view`（避免每次 `ATTACH`）。

```sql
-- accounts.db 里建一张本地缓存表（B）
CREATE TABLE IF NOT EXISTS player_view (
  server_id   INTEGER PRIMARY KEY,
  dev_id      TEXT,
  kind        TEXT,          -- 'b'.'normal' | 'public'
  last_login  TEXT,
  nickname    TEXT,
  level       INTEGER,
  sync_at     TEXT NOT NULL
);
```

刷新任务（cron，1 分钟一次，与 `sync_cards.php` 同批）：

```sql
INSERT OR REPLACE INTO player_view(server_id,dev_id,kind,last_login,nickname,level,sync_at)
SELECT a.server_id, a.dev_id, 'normal', a.last_login_at,
       g.Nickname, g.Level, datetime('now')
FROM accounts a
LEFT JOIN game.Accounts g ON g.ServerId = a.server_id;
```

## 4.3 批量发奖：走**邮件**的落库路径

Shittim 的邮件表 = **`Mails`**（EF 实体 `MailDBServer`，`SchaleDataContext` 的 `DbSet<Mails>`）。
建号时写的字段可以照抄 `AccountService.cs:323-345`（欢迎邮件）那一段：

| 列 | 值 |
|---|---|
| `AccountServerId` | `server_id` |
| `Type` | `MailType.InventoryFull`（或普通系统邮件类型） |
| `SendDate` | `account.GameSettings.ServerDateTime()`（**账号时钟**，不是 `DateTime.Now`——见 `GatewayController.cs:348` 注释） |
| `ExpireDate` | `SendDate + 7d` |
| `ParcelInfos` | `[{Key:{Type:<ParcelType>,Id:<id>},Amount:<n>}]`（JSON 列） |
| `RemainParcelInfos` | `[]` |

**发奖清单（可复用）**：`ParcelType.Currency=2`（青辉石 `Id=3`）、`Character=1`、`Item=4`、`MemoryLobby=8`（**amount 必须 ≥1**，见 `SHITTIM_ROOT_PLAN` 里 MomoTalk 那个坑）。

## 4.4 "一键发给 N 个人"的幂等保证

**必须有一个发奖台账**（写在认证库，不写游戏库）：

```sql
CREATE TABLE IF NOT EXISTS grant_batches (
  batch_id    TEXT PRIMARY KEY,       -- uuid4，面板生成
  created_at  TEXT NOT NULL,
  operator    TEXT,
  parcel_json TEXT NOT NULL,          -- 统一奖励模板
  total       INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS grant_items (
  batch_id    TEXT NOT NULL,
  server_id   INTEGER NOT NULL,
  state       TEXT NOT NULL,          -- pending | sent | failed
  mail_hint   TEXT,                   -- 可空：便于日志定位
  updated_at  TEXT NOT NULL,
  PRIMARY KEY (batch_id, server_id)
);
```

发送流程（幂等关键：**先占位，再写邮件**）：

```python
tx = auth_db.begin()
n = tx.execute("INSERT OR IGNORE INTO grant_items(batch_id,server_id,state,updated_at) VALUES(?,?, 'pending', now)", ...)
if n == 0:                       # 已发过/正在发
    return skip
tx.commit()                      # 占位落盘（跨库不能同一事务）

if game_db.execute("SELECT 1 FROM Mails WHERE AccountServerId=? AND Comment=?", (sid, batch_id)).fetchone():
    auth_db.mark(sid, 'sent'); return skip     # 用 Comment 存 batch_id 做二次兜底

game_db.execute("INSERT INTO Mails(AccountServerId,Type,SendDate,ExpireDate,ParcelInfos,RemainParcelInfos,Comment) VALUES(...)",
                (sid, mail_type, send_time, expire, parcels_json, '[]', batch_id))
game_db.commit()
auth_db.mark(sid, 'sent')
```

**幂等三重保险**
1. `grant_items` 主键 `(batch_id, server_id)` ⇒ 同批次同玩家只能占一次位；
2. `Mails.Comment` 里写 `batch_id` ⇒ 即使台账丢了，也能靠游戏库查出"这封已发"；
3. 面板按钮在前端禁用 + 后端 `batch_id` 由服务端生成（不接受客户端传），**重复点击 = 同一 batch 重放 = 全部 skip**。

## 4.5 风险 / 回滚

| 风险 | 缓解 |
|---|---|
| 直接写 `schale.sqlite3` 与运行中的 Shittim 冲突 | 用 **WAL + `busy_timeout=5000`**（`schema_v2.sql` 头注释同款），并**只 INSERT 邮件行**，不碰其它表；更稳的做法是让 Shittim 自己发（走 GM 命令 `!mail`），但需服务端可达 |
| 跨库事务无法原子 | 用"台账先行 + 邮件行 `Comment` 兜底"，接受"极小概率漏发"（可重放补齐），绝不重复发 |
| `SendDate` 用错时钟 | 必须与 Shittim 一致：`account.GameSettings.ServerDateTime()`（`GatewayController.cs:348` 已踩过这个坑） |
| 回滚 | 停面板写权限即可；`grant_batches/grant_items/player_view` 都是新表，`DROP` 不影响任何既有逻辑 |

---

# 5. 一页总表（改动点 × 归属）

| # | 文件 | 行号 | 归属 | 危险度 |
|---|---|---|---|---|
| 1 | `ba_cardadmin/inc/token_key.php`（新） | — | 运维 | 低（新增文件） |
| 2 | `ba_cardadmin/inc/token_v2.php`（新） | — | srv-ops/我出方案 | 低 |
| 3 | `ba_cardadmin/inc/sync.php` | `:186-187`、`:227` | srv-ops | **中**（写错则卡片导出坏） |
| 4 | MySQL `cards` | `ALTER TABLE` ×2 列 | 运维 | 低 |
| 5 | `bapatch/sdkcard.py` | `:41`（签发）、`:30-34` 后（台数） | **srv-ops 独占** | **中**（登录入口） |
| 6 | 桥接 `account_auth_probe.py` | `:62-64`、CheckNexon 入口、`:1001` | **srv-ops 独占** | **高**（身份核心） |
| 7 | `account_service.py` | **不改** | — | — |
| 8 | Shittim 源码 | **不改**（路线 A） | — | — |
| 9 | 面板新表 | `player_view` / `grant_batches` / `grant_items` | 面板立项 | 低 |

**实施顺序（建议）**：③ 表结构 + sync.php（向后兼容，可独立上线）→ ① token 签发 + 验签（灰度 `BAPATCH-MU=1`）→ ② 分流接线（灰度 1 天）→ ④ 面板。

**全局回滚**：`BAPATCH-MU=0` + 还原 `sdkcard.py:41`/`sync.php` 两处 ⇒ 完全回到 2026-11-17 的行为。
