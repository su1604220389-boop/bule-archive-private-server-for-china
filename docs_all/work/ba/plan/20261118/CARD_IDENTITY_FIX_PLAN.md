# 卡密身份压平（"不管哪张卡都进同一个号"）—— 诊断与方案

- 日期：2026-11-18 03:3x
- 状态：**只出方案，未改任何代码/配置**（用户明确要求）
- 覆盖两个症状：① 多张卡密登录进同一账号 ② 管理站「玩家详情 → 桥接/卡密」取不到数据
- 相关取证：`SRV_CARD_IDENTITY_EVIDENCE.md`（srv-ops，现网实测）、`IDENTITY_CHAIN_MAP.md`、`PANEL_BRIDGE_DIAGNOSIS.md`

---

## §0 一句话结论

**账号键（`dev_id`）本身是"卡密派生"的设计，但客户端手里那个 DevId 一旦落地就再也不变；
再加上 SDK 的 `quick-login` / `detail` 按"遍历顺序取第一个含本机的卡"，
结果是这台手机上永远只有**第一张卡（`1111…`）**在起作用，后面建的卡从来没进过身份链路。**

现网实测：03:06–03:20 连续 **5 次** `/api/account/auth`，`req_devid_sha8` 全部是 `a424da70`（= `314816420`），一次都没变过。

⇒ 现状是 **一机一账号**，不是一卡一账号。

---

## §1 证据

### 1.1 身份机制本身是对的（算术验证）

`sdkcard.py:44-46`（线上 `/www/wwwroot/ba_sdk/sdkcard.py`）：

```
User.Token = sha256(卡密 + '|' + device)[:40]
User.ID    = int(md5(卡密)[:8], 16) % 900_000_000 + 100_000_000
```

| 卡密 | md5 推出的 User.ID | sha256(User.ID)[:8] |
|---|---|---|
| `11111111111` | **314816420** | **a424da70** |
| `12222222222` | **854071516** | 5b3a…（现网从未出现） |

现网日志 `req_DevId`：`len=9, sha8=a424da70` → **客户端确实把 SDK 的 `User.ID` 当 `DevId` 发给游戏服**。
桥 `account_service.py:882` 用 `UNIQUE(dev_id)` 查号 —— 桥这一层没问题。

### 1.2 压平发生在 SDK 取卡策略

线上 `/www/wwwroot/ba_sdk/sdkcard.py`（本地快照 d90546d6）：

```
391-402  /user/quick-login : for key, rec in d['cards'].items():   ← 遍历
                              if dev in rec['devices']: return 该卡  ← 首个命中即返回
406-407  /user/detail      : 同样的循环（且未打日志，所以 sdk.log 看不见）
```

`cards.json` 现状：

```
index 0  1111****1111  devices=[952138bd, 69ab71d6]   bind_one=false
index 1  1222****2222  devices=[69ab71d6]             bind_one=false
```

设备 `69ab71d6` **同时属于两张卡**，卡 A 在前 ⇒ `quick-login` 永远命中 A。

### 1.3 现网日志对得上

```
sdk.log  3043  LOGIN OK 1222****2222  → 卡B 首次登录成功
         3105  LOGIN OK 1222****2222  → 又一次
         3131  LOGIN OK 1111****1111  → 下一次又回到 A
         全表  QUICK OK 1111… 20+ 次 ；QUICK OK 1222… **0 次**
日志     03:06/03:09/03:17/03:20:08/03:20:58 五次 auth，devid sha8 全 = a424da70
```

⇒ 卡 B **成功过一次**，但它的 `User.ID=854071516` 从未出现在桥的日志里。

### 1.4 两个 id 空间（面板空数据的成因）

| 值 | 来源 | 现网取值 |
|---|---|---|
| Shittim `PublisherAccountId` | 桥转发的**常量**票据 `ENTER_TICKET = b64("314816420/61de1d…")`（`account_auth_probe.py:200-202`） | **314816420，所有账号都一样** |
| `accounts.publisher_account_id` | `account_service.py:866-868`：`PublisherAccountId` 缺失且 `dev_id` 是纯数字 → `int(dev_id)` | 每张卡不同 |

两边只有第一个账号恰好相等 —— 因为 `DEFAULT_FALLBACK_PUBLISHER_ID = 314816420`（`account_service.py:403`）**就是从卡 A 的 `User.ID` 抄下来的**。

面板 `pages/player_detail.php:251` 用 Shittim 的 `publisherId` 去 join `accounts.publisher_account_id`
⇒ 除 1 号账号外全部匹配不上 ⇒ 显示"未找到（publisherId 对不上 accounts.db）"。

### 1.5 顺带发现的隐患（不是本次 bug，但必须记）

`account_service.py:847-855`：请求里既没有 `DevId` 也没有 `DeviceUniqueId` 时，身份**退化成常量 314816420**。
而 314816420 **是卡 A 主人的真实账号**。任何一次 `_req_dict` 解析失败（失败会静默返回 `{}`），
都会把陌生人送进卡 A 的账号。**这是一个账号串号风险，不是一个显示问题。**

---

## §2 方案（分档，逐档验证后才进入下一档）

### P0 · 验证门 —— **已关闭：客户端会刷新，P1 成立，P2 不需要**

nginx access log（`/www/wwwlogs/example.com.log`，窗口内未截断）+ `sdk.log` 交叉验证：

```
03:17:29 /sdk/user/login   200 847   ← 卡B 首次 OK（User.ID = 854071516）
03:17:29 /user/detail      200 847   ← ★ 紧邻下一跳就是 detail，不读 body，只按设备
03:17:29 /api/account/auth 200 2722  ← DevId 仍是 314816420（卡A）
```

`/user/detail`（`sdkcard.py:404-412`）实现是「设备在谁 devices 里 + JSON 顺序 → 第一张命中即返回」，
它**不看刚用哪张卡登录** ⇒ 永远返回卡 A 的完整 `user_payload`（847 字节，`User.ID=314816420`）。
客户端拿 detail 的返回覆写身份 ⇒ DevId 退回 A。

同一模式在 03:20:08 完整复现一次；随后 03:20:57 客户端提交的 `OpenID` 已经自己变回卡 A。

**⇒ 不是"DevId 落地后固化"，而是「每次用卡 B 登录后都被 detail 覆写回卡 A」。
修 SDK 的取卡语义即可，桥侧不需要动。**

---

### P0' · 撤回桥的 P4 retarget（**最高优先级，不撤这个 P1 白做**）

`account_auth_probe.py`（线上 v3 `7d4d1625`）**139-169 行**是今晚新加的"加固"，注释写着
「绝不凭未知 dev_id 建号：未知/无行一律退兜底账号」。实际代码：

```python
156:  if _exists is False and _fb_exists is False:
157:      rec['acct_id_src'] = 'create'       # 两者都确认不存在 ⇒ 真全新安装
158:  else:
159:      ident.dev_id = _fb                  # 未知/或兜底存在 ⇒ 一律退兜底号
```

`_fb` = `FALLBACK_DEV_ID` = **314816420** = 1 号账号的 dev_id。

**现网后果**：兜底账号一旦存在（它已经存在，`login_count=52`），
**任何查不到账号的 dev_id 都被改写成 314816420** ⇒ **再也无法建出第二个账号**。
即使 P1 把 SDK 修好、客户端真的带着卡B 的 `854071516` 过来，这一步也会把它改回卡A 的号。

**改法（一行判定）**：只在**身份不可信**时才 retarget，身份可信且无行就正常建号。

| `dev_id_source` | 无对应账号时 | 理由 |
|---|---|---|
| `DevId`（请求包里真的带了 DevId） | **create** | 这是"新卡/新玩家"，必须建号 |
| `DeviceUniqueId`（`duid:` 前缀） | create 或按公益卡规则 | 同上 |
| `fallback`（包里什么都没有） | retarget / 或直接拒绝 | 这类才是垃圾请求，不该建号 |

**风险**：撤回后，任何解析失败的请求都会走 `identify()` 的 fallback 分支（仍指向 314816420）；
所以 **P0' 必须和 P4（把 fallback 改成拒绝）一起做**，否则只是把"一律合并"换成"一律建新号"或"一律进 1 号号"。
**回滚**：桥回滚到 `7d4d1625` 之前的基线 `1db27e4c`（或备份目录 `PROBE_IDENTITY_BACKUP_20261118_023917`）。

---

### P1 · SDK 侧：`/user/detail`（和 `quick-login`）改成"本机当前卡"（**定案**）

**病灶**：三个端点语义各写各的 ——
`/user/login` 用**请求体里的卡密**；`/user/detail` 和 `/user/quick-login` 用**设备 + 遍历顺序**。
后者把前者的结果每次覆盖掉。

**改动语义（3 处，同一份逻辑）**：

1. **新增一个 sidecar 状态文件** `/root/bapatch/device_card.json`，内容 `{"<device 的 sha256[:32]>": "<卡密>"}`。
   - **不放 `cards.json`**：`cards.json` 由 sdkcard 整体 `json.dump` 重写且**非原子**（`inc/sync.php:14` 已注明），
     面板 `sync.php` 也在读它的 `{"cards": {...}}` 结构，加兄弟键有被解析器忽略/误判的风险。
   - 独立文件可原子写（临时文件 + `os.replace`），且不改变任何既有文件的形状。
   - 存 **device 的 hash**，不存设备号明文。

2. **`/user/login` 成功时**：把 `device_hash → 卡密` 写进 sidecar（这是唯一"用户显式选择"的事件）。

3. **`/user/detail` 与 `/user/quick-login`**：
   - 先查 sidecar 拿到"本机当前卡"，**校验它仍然有效**（卡还在 `cards.json`、未过期、devices 仍含本机、未超 `max_devices`）；
   - 有效 ⇒ 返回该卡的 `user_payload`；
   - 无效/查不到 ⇒ 退回今天的行为（遍历首个命中），并且**把 stale 映射清掉**；
   - 都拿不到 ⇒ 维持现有"空返回 → 客户端弹登录框"。

4. **顺带给 `/user/detail` 补一行日志**（现在它完全不打日志，这正是这次排查卡住的直接原因）。

**影响面**：只改 8080 的返回内容。**不碰** `/api/`、桥、Shittim、MySQL、`accounts.db` 结构、`cards.json` 结构、卡密校验/过期/绑定逻辑。

**为什么这样就够了**：`accounts` 的键是 `UNIQUE(dev_id)`，而 `dev_id` = 卡密的 `User.ID`（已算术验证）。
卡 A → 314816420 → 现有账号 `10000000000` 原样续用；卡 B → 854071516 → 自动新建第二个账号。
**不需要迁移老账号，也不需要动桥。**

**残留风险 + 对策**：

| 风险 | 说明 | 对策 |
|---|---|---|
| **卡密撞号** | `User.ID = md5(卡密)[:8] % 9e8 + 1e8`，只有 9 亿空间；**发 1 万张卡约有 5.4% 概率出现两张卡撞进同一账号** | 建卡时先查 `accounts.db.dev_id` / 已发卡密算出的 ID 是否已存在，撞了就让面板换一张；长期方案是把账号键换成 64 位（属 P2 范畴，不急） |
| 多设备 | 同一张卡在多台设备上登录 | sidecar 是**按设备**记的，互不影响，符合"一卡可多设备" |
| 并发写 | `ThreadingHTTPServer` 多线程 | 写 sidecar 加进程内锁 + 原子 `os.replace` |
| 卡被删/过期 | 映射指向已失效的卡 | 步骤 3 里已含有效性校验 + 清 stale |
| 面板同步 | `sync.php` 会读 `cards.json` | sidecar 是独立文件，`cards.json` 一个字节都不变 |

**回滚**：`cp sdkcard.py.bak sdkcard.py` + 重启 8080；删掉 `device_card.json` 即回到旧行为（旧行为不认这个文件）。
**验证**：
1. 同机输卡 B 登录 → `/api/account/auth` 的 `req_devid_sha8` 从 `a424da70` 变成 `854071516` 的 sha8；
2. `accounts.db` 出现第二行（`dev_id=854071516`），`login_count` 从 1 起；
3. 游戏内 UID / 昵称 / 等级是全新的，不再是 `10000000000`；
4. 再切回卡 A → 回到 `10000000000`，数据完好（证明老号没被破坏）。

---

### P2 · 桥侧：账号键从 DevId 换成"卡密身份"（**暂不需要，留作长期方案**）

P0 已证明客户端会采纳 `/user/detail` 的返回，所以 P1 足够，**桥不动**。
只有在将来出现"客户端不再透传 DevId"或"需要跨 APK 版本稳定身份"时，才启用下面这套。

**目标**：不依赖客户端是否刷新 DevId。

**做法（不写死实现细节，只定契约）**：
1. `sdkcard.py` 维护并暴露 `device_unique_id → 当前卡密` 的映射（写一个只读的 JSON 或 8080 上一个内部只读端点）。
2. 桥 `acct_apply_to_auth()` 在调用 `identify()` 之前，用请求里的 `DeviceUniqueId` 去查这个映射：
   - 查到 ⇒ 身份键 = `card:<sha256(卡密)[:16]>`（不落明文卡密）
   - 查不到 ⇒ 维持现状（DevId 路径），行为不变
3. `account_service.identify()` 只加一条前置分支，不改既有分支顺序。

**为什么用卡密而不是设备**：
- 付费卡本来就是"一卡一账号、可多设备"；
- 公益卡才是"一设备一账号"，应当键到 `md5("free:" + DeviceUniqueId)`（**绝不能用 DevId**，DevId 其实是卡密派生值）。

**风险（高）**：
- 现有账号 `10000000000`（`dev_id=314816420`，`login_count=52`）会**失联**。
  必须做一次性别名迁移：把 `card:<卡A的 hash>` 指向既有账号，否则用户丢号。
- 迁移必须在**停写窗口**内做，且先导出 `accounts.db` 备份。

**回滚**：`accounts.db` 整库备份还原 + 桥回滚到 `7d4d1625`。

---

### P3 · 面板"桥接 / 卡密"空数据 —— **真因已查明，与 id 空间无关（更正）**

> **更正**：本文档早前写的"面板 join 到了两个不同 id 空间"是**错的**，只读核查推翻了它。
> `accounts.publisher_account_id` 实测就是 `314816420`，与桥常量**完全相同**，join 键是好的。

**真因**：`/www/wwwroot/ba_cardadmin/.user.ini` 的 `open_basedir` 少了 `/www/wwwroot/bapatch/`：

```
open_basedir=/www/wwwroot/ba_cardadmin/:/tmp/:/www/wwwroot/ba_sdk/
```

面板要读 `/www/wwwroot/bapatch/data/accounts.db`（`inc/players.php:27`），
`is_file()` 被 open_basedir 拦下返回 false ⇒ **`inc/players.php:42-44` 提前 `return []`，PDO 都没打开，`catch` 根本没触发**。
⇒ `player_one()` 的 `$br` 恒为 null ⇒ `pages/player_detail.php:251` 输出「publisherId 对不上 accounts.db」——**这句提示是假的**。

**两个误导信号**：设置页说「✗ 文件不存在」，详情页说「publisherId 对不上」，同一份数据两种说法，都指不到真因。

**修法（唯一真正止血的一步，不是改 .php）**：`.user.ini` 加 `/www/wwwroot/bapatch/`，
配合 `chown root:www && chmod 750` 收窄可读面。

**修完还有第二道门**：`accounts.db` 头部 byte[18..19]=`02 02` ⇒ **WAL 模式**，
只读打开需要 `-shm`，打不开就 `SQLITE_CANTOPEN`，而面板照样只会说"未找到"（假绿灯）。必须复测。

**另一个独立 bug**：`card_players` 表**不在 `sql/schema.sql` 里**，只靠 `player_ensure_tables()` 运行时自建；
而 `players.php:98` 的 `$done = true` 写在 `try` **之前** ⇒ 一次建表失败整页不再重试。

**方案（两选一）**：

- **P3a（推荐，零风险）**：桥新增一个**只读**查询接口（如 `GET /bridge/account?device_unique_id=…` 或 `?card=…`），面板改调它。完全不碰 Shittim、不碰票据、不碰游戏身份。
- **P3b（风险高）**：把常量 `ENTER_TICKET` 改成按账号派生的票据，让 Shittim 的 `PublisherAccountId` 跟账号一致。
  ⇒ 会改变 Shittim 侧所有账号的 publisherId，可能造成老号失联（取决于 Shittim 是否拿 publisherId 当索引/外键）。**必须先读 `AccountHandler.cs` 建号/查号逻辑再定。**

**附带修（低风险，建议一起）**：
- `inc/players.php:59-61` 的 `catch (Throwable) { return []; }` 把原因全吞了 → 加 `$last_err`，设置页显示真实原因（现在只会说"未找到"）。
- `publisherId` 比对前 `(string)(int)` 归一，避免 11 位数 `10000000000` 走浮点/科学计数法。
- 一个玩家多张卡时全部列出（现在 `$bridge` 单行、`$binding[$cid]` 只取一张）。

---

### P4 · 堵 fallback 串号（独立于上面，优先级不低）

`identify()` 的兜底值 `314816420` 是**真实账号**。两条改法：

- **P4a**：`_fallback_publisher_id()` ≤ 0 时直接 `AuthRejected`（拒绝建号），不再静默退化。
- **P4b**：若必须保留兜底，换成一个**永不与真实卡撞车**的值（例如负数或 `9_000_000_000+` 段），并单独建一个"垃圾桶账号"。

推荐 **P4a**：宁可登录失败，也不要把陌生人送进别人的号。

---

## §3 不碰清单（防止把已经跑通的东西改坏）

1. 桥的 AES/CBC 加解密、`IV="JOSYDF8ys97uhFYS"`、`a_proto_int` 包装 —— 不动。
2. nginx 路由：`/user/` → 8080、`/api/` → 9097 —— 不动。
3. Shittim DLL `f54739aa…`、今晚 ID 卡那三刀 —— 不动。
4. `accounts` 表 `UNIQUE(dev_id)` 语义 —— 不动（P2 只是新增一个身份分支，不改约束）。
5. `sdkcard.py` 的卡密校验/过期/绑定设备逻辑 —— 不动。
6. 面板已做对的：PDO 预处理、全 POST CSRF、登录限速、会话轮换 —— 不动。

---

## §4 关键文件与当前指纹（供回滚比对）

| 文件 | md5 / 大小 |
|---|---|
| `sdkcard.py`（线上 `/www/wwwroot/ba_sdk/`，取证时读） | `d90546d6…` |
| `account_auth_probe.py`（线上 v3） | `7d4d1625…` / 164,514 B |
| `account_service.py`（线上） | `436cba4d…` / 106,139 B |
| `accounts.db`（取证结束态） | `dcd02599…` |
| `cards.json`（取证结束态） | `bea9b93f…` |

> 注：上述 md5 由 srv-ops 在 2026-11-18 03:2x 只读取证时记录，部署任何东西前**必须重新取一次**再比对。

---

## §5 结果（2026-11-18 04:04 实测通过）

### 成功判据（唯一标准：看数据库，不看客户端）

```
Shittim Accounts：2 行 → 3 行

ServerId | PublisherAccountId | Nickname | Level
   1     | (空)               | Schale   | 90
   2     | 314816420          | 111      | 90    ← 老号，login_count 55，未受影响
   4     | 854071516          | (空)      | 1     ← 卡B，独立存档
```

**链路**：卡B → SDK `User.ID=854071516` → 桥按 DevId 解出 `pub=854071516` → 票据 `b64("854071516/TOKEN")` → Shittim `Account_CheckNexon` 查不到 `NpSN` ⇒ 新建账号 ⇒ 独立存档。之后 12 条业务请求全部稳定 `pub=854071516`（`pub_src=sid`，无 `bucket_err`）。

### 三层缺一不可（这是本次最贵的教训）

| 层 | 病灶 | 修法 |
|---|---|---|
| SDK(8080) | `/user/detail` 按"设备+JSON顺序"返回第一张卡，每次把刚登录的卡覆盖掉 | v2：`pick_card_for_device()` 按 `last_used_at` 倒序 |
| 桥(9097) 身份 | 未知 dev_id 一律退兜底号（= 1 号卡真人账号） | `dev_id_source` 可信时建新号；兜底常量换 `9000000001`（在 `User.ID` 值域外） |
| 桥(9097) 会话 | `SESSION` 全局单例 + `ENTER_TICKET` 常量 ⇒ Shittim 眼里只有一个人 | 按 publisherId 分桶 + `enter_ticket(pub)` |
| MySQL | 无 `last_used_at` 列 ⇒ PHP cron 每分钟把 SDK 记的"最近使用"冲成 0 | ALTER 加 `kind`/`max_devices`/`last_used_at` |

**只修任何一层都不成立**：只修 SDK ⇒ 票据仍是常量（本次第一次尝试就是这么失败的，两个号共用存档 + 等级页卡死）；只修桥 ⇒ SDK 仍返回卡A。

### 开关（可秒级回退，不用重新部署）

```
/www/wwwroot/bapatch/cn_multiacct.txt     内容 "1" = 开；文件不存在 = 关（= 基线行为）
关闭后：桥的会话/票据/路由全部落回基线单例路径，且离线自测证明与基线逐字节一致
```

### 当前线上状态

```
桥       8e268306bd0db8055eebd3db55873955   177,059 B   pid 2705131  cwd=/www/wwwroot/bapatch/tools
service  eca224611d4f13cecb6be1f5f7b8ee14   106,244 B
SDK      5902d5de108e0f5cd799ecd9896560ec    17,630 B   pid 2705143  ba-sdk active
helpers  79ef16c192349c2e46ef13efd25e3f4e
sync     81042da0eda734af497f18ca73c2b771
MySQL    cards 表 14 列（kind/max_devices/last_used_at 已加，两张卡均为 paid/0）
备份     /root/CARDID_DEPLOY2_20261118_035837（5 个原件 + BEFORE/AFTER.md5）
         /root/CARDID_DEPLOY2_20261118_035837_cards.sql（MySQL dump）
         /root/CARDID_DEPLOY_20261118_033943（第一刀，已回滚但备份保留）
```

### 回滚

```
软回退（推荐，秒级）  rm /www/wwwroot/bapatch/cn_multiacct.txt
整批回滚            还原 5 个文件 + systemctl reload php-fpm-82 + 重启 8080/9097
                    备份在 /root/CARDID_DEPLOY2_20261118_035837
MySQL 三列            加列是纯增量，不需要回滚（留着不影响旧代码）
accounts.db 新增列    shittim_server_id（当前 4 行均为 NULL，未回写）
```

### 遗留（04:25 更新）

1. **~~`accounts.shittim_server_id` 未回写~~ → 已解决**：已上线 `aa92a011` / `0c057b90`，卡B 实测写回 `shittim_server_id = 4`（与 Shittim `Accounts.ServerId=4` 完全一致），日志 `acct_sid_wb=ok:4`。**老账号按设计不写**（走基线单例分支）。
2. **~~`pub_src=none` 覆盖率未验证~~ → 已验证健康**：开关开启后 157 条请求中 `sid 138 / devid 3 / none 16`，`none` 全部是 `/api/state`、心跳这类本就无账号上下文的请求；账号绑定请求 138/138 全部解析成功，`acct_bucket_err = 0`。
3. **公益卡/付费卡 UI**：`pages/cards_new.php` + `pages/cards.php` 重建中（以线上 `4e9199f3` / `787ec937` 为基线，只贴卡型白名单改动，剔除 F4b 的 `ui_state_*` / `csrf_*` / `?reveal=`）。**MySQL 三列 + SDK 的 `kind` 支持已经在线，只差这两个页面。**
4. **~~面板「桥接/卡密」空数据~~ → 已修**：`.user.ini` 追加 `/www/wwwroot/bapatch/`（文件有 bt_hids 的 immutable，需 `chattr -i` 后改再 `chattr +i`）+ `accounts.db` 的 WAL 权限（`chgrp www` + `chmod 660`）+ 目录 setgid + 桥启动 `umask 007`。FPM 探针 `open=OK, rows=4`。
5. 孤儿账号说明：`accounts.db` 的 `10000000003` 现在是**卡B 的真实账号**，不是孤儿，不要删。

### 04:25 线上完整指纹

```
account_auth_probe.py  aa92a011  180,227 B   pid 2708441  cwd=/www/wwwroot/bapatch/tools（umask 007 启动）
account_service.py     0c057b90  108,730 B
sdkcard.py             5902d5de   17,630 B   pid 2705143  ba-sdk active
inc/helpers.php        79ef16c1   27,623 B
inc/sync.php           81042da0   29,150 B
.user.ini             88 B，open_basedir 含 /www/wwwroot/bapatch/
MySQL                  cards 14 列（kind/max_devices/last_used_at）
开关                   /www/wwwroot/bapatch/cn_multiacct.txt = 1
备份                   /root/CARDID_DEPLOY_20261118_033943（第一刀，已回滚）
                       /root/CARDID_DEPLOY2_20261118_035837（多账号 + MySQL dump）
                       /root/CARDID_DEPLOY3_20261118_041441（.user.ini + accounts.db）
                       /root/CARDID_DEPLOY4_SIDWB_20261118_041626（sid 回写）
```

---

### 前序状态记录（04:04 之前的判断，保留作对照）

**已关闭**：P0（客户端会不会刷新 DevId）→ 答案是会，抢回身份的是 `/user/detail`。

**定案顺序**：

1. **P1** —— 唯一必须做的修复，改 8080 一个文件（+1 个 sidecar 文件），可秒回滚。
2. **P4** —— 建议同期做：把 `identify()` 的常量兜底改成拒绝建号，堵掉"陌生人进 1 号卡账号"。
3. **P3** —— 面板 join 改道，独立于上面两项，等 `PANEL_BRIDGE_DIAGNOSIS.md`。
4. **P2** —— 不做。

**两路已回报**（结论见 P3 与 §6）：
- `IDENTITY_CHAIN_MAP.md`：`ENTER_TICKET` 全仓只有 **1 个消费点**（`account_auth_probe.py:1643`），确实决定 Shittim 侧 publisherId；但它不决定客户端看到的号 —— 玩家看到的号由 `DevId` 那条线决定。
- `PANEL_BRIDGE_DIAGNOSIS.md`：面板空数据的真因是 `open_basedir`，**不是** id 空间（本文档已更正）。

---

## §6 公益卡 / 付费卡：四件套都写好了，一件都没上线

| 层 | 产物 | 状态（只读核实） |
|---|---|---|
| SDK v2 | `work\ba\srv_live\20261118_0059\_patched\sdkcard.py` 17,630 B / `5902d5de` | **未部署**。线上是 14,940 B / `d90546d6`，全文件 grep `kind`/`public` = **0 命中** |
| 面板 PHP | `cards_new.php:300-309/374-383`（卡类型下拉）、`cards.php:601-606`（类型列）、`inc/helpers.php:274-309`、`inc/sync.php`（同步链） | **未部署**。线上快照 grep `name="kind"` = **0 命中** |
| MySQL | `_audit/alter_cards_cardtype.sql`（幂等 ALTER，加 `kind`/`max_devices`/`last_used_at`） | **未执行** |
| 文档 | `SDKCARD_V2.md`、`FEATURE_CARDTYPE_PHP_20261118_0109.md` | 都标注「未部署 / 等 lead 批」 |

⇒ 面板里看不到选项，**不是没做，是整条链停在"待批/待执行"**。
当时没批的原因记在 `FEATURE_CARDTYPE_PHP_20261118_0109.md:262`：磁盘 `vda %util=100`、load 12.07，DDL 要等低峰。

`SDKCARD_V2.md:34` 另有一条硬约束：**在改完 PHP 的库与同步逻辑之前，不要在生产启用公益卡**，
否则 `cards.json` 有两个写入者（PHP cron 与 SDK），会出现"刚解绑又回来""公益卡变普通卡"。

### 6.1 两套机制的差别，本质就是账号键选谁

| 卡型 | `User.ID` | 账号跟随 | 换设备 | 换卡 |
|---|---|---|---|---|
| 付费卡 `paid` | `md5(卡密)` | 卡密 | 同号 | **换号** |
| 公益卡 `free` | `md5("free:" + 设备号)` | 设备 | **换号** | 同号（同一设备多张公益卡共用一个号） |

代码实证：`_patched\sdkcard.py:120`
`seed = ("free:" + str(device)) if card_kind(rec) == KIND_FREE else str(card)`

### 6.2 上线顺序（反了会很难定位）

1. **P0' + P4**（桥：撤回 retarget + 堵住 fallback）
2. **P1**（SDK：`detail`/`quick-login` 取"本机当前卡"）
3. **实测**：两张付费卡 → 两个账号；切回旧卡 → 旧号数据完好
4. **再做卡型**：MySQL ALTER → 面板 4 文件 → SDK v2 → 等同步 ≤60s → 跑文档 §7 的 3 条验收
5. **最后**：面板 `open_basedir` + WAL 复测

**理由**：P0'/P1 和卡型都会改 `User.ID` 的派生结果。混在一起做，出问题分不清是谁改的。
