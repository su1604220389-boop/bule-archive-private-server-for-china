# 设备标识清理（2026-11-18）

> 起因：用户在**封禁页面的「设备」**一栏看到「一台手机被识别成 3 个」。
> 结论：**物理设备识别本身没问题**，是面板把三种不同性质的编号都当成"设备"列出来了。

## 一、现象与原始数据

同一台真机（SDK 上报的 `Authorization.Head.DeviceID` 恒定）：

```
ce8ffeb7d08cfb36
```

它在 `card_devices` 里有 3 行（因为绑了 3 张卡）：

```
id=3 → card 3 (11111111111)  2026-11-18 00:34
id=4 → card 6 (12222222222)  2026-11-18 03:18
id=6 → card 8 (<REDACTED_CONTACT>)  2026-11-18 21:09
```

但**同一张卡下面没有出现 ≥2 个 device_id**（唯一的 card 3 是两台不同设备：`09a4d0ab0ee93616` 与 `ce8ffeb7d08cfb36`）。

## 二、根因：3 种编号被当成同一种东西

以玩家 `pub=819675745`（8 号卡）为例，那一格列出的 3 条：

| 值 | 真实身份 | 是设备号吗 |
|---|---|---|
| `ce8ffeb7d08cfb36` | SDK 上报的 `DeviceID`（16 位 hex） | ✅ 是 |
| `6393c610745ae96e89450daee98b42c9` | **桥自己算的** `accounts.device_unique_id`（32 位 md5 形） | ⚠️ 是同一台机，但**没有任何一层拿它做拦截** |
| `819675745` | **`publisherId`** —— 账号身份（9 位数字） | ❌ 根本不是设备 |

代码位置（修复前）：

- `pages/bans.php:135` → `foreach (array('device', 'dev_id') as $k)`
- `inc/bans.php:484-486` → `ban_device_cand_add($devs, $row['dev_id'], 'accounts.db.dev_id', ...)`
- `inc/bans.php:1222` → `foreach (array('device_unique_id', 'dev_id') as $k)`

`accounts.db.dev_id` 与 `publisher_account_id` **恒等**（实测 4/4 行相等，全是 9 位数字），
它是桥把 `DevId` 改写为 publisherId 之后的副产物，不是设备号。

## 三、为什么"假设备"有实际危害

设备封禁是**整串精确匹配**：`bans(kind='device', target=<原样>)`。

所以点那条 9 位数字去"封设备"，会写出一条**永远匹配不到任何真机**的封禁记录 ——
看着封了，实际没封。

## 四、哪一层真的会拦设备封禁

| 层 | 是否会拦 `kind='device'` | 依据 |
|---|---|---|
| `sdkcard.py` | ✅ **唯一真正执行的一层** | `device_banned(dev)` 读 `device_ban.txt`；命中 `/user/login`、`/user/quick-login`、`/user/detail` 返回 `{'Code':400101,'Msg':'设备已被限制'}` |
| 桥 `account_auth_probe.py` | ❌ 不判 device | 只读 `kind='account'`（`DELETE FROM bans WHERE kind='account' AND target=?`） |
| `device_ban.txt` | 读：`sdkcard.py`；写：`inc/bans.php` `ban_device_set()` | 永久封才写文件；限时封只写 `bans` 表 |

**⇒ 只有 16 位 SDK DeviceID 是可封的。** 32 位桥侧 id 封了不生效。

## 五、修法（三轮，全部面板侧）

### 第 1 轮 `DEVFIX`（`/root/DEVFIX_20261118_215524`）
1. `inc/bans.php` `ban_device_candidates()`：去掉 `accounts.db.dev_id` 这一路
2. `inc/bans.php` `ban_devices_of_account()`：`array('device_unique_id','dev_id')` → `array('device_unique_id')`
3. `pages/bans.php` `bans_row_devices()`：`array('device','dev_id')` → `array('device')`
4. `inc/bans.php` `ban_delete_account()`：删号后 `UPDATE card_players SET server_id=0 WHERE server_id=?`
   （不删行、不动 `publisher_account_id`；1 分钟内自动绑定会把新 ServerId 补回来）
5. `inc/players.php` `player_autobind_cards()`：`publisher` 相同但 `server_id` 不同 → **纠正**而不是跳过
6. `inc/sync.php`：日志带上「纠正 ServerId N 条」

### 第 2 轮 `DEVFIX2`（`/root/DEVFIX2_20261118_215734`）
7. 32 位桥侧 id **也去掉**（`ban_device_candidates` / `ban_devices_of_account` / `bans_row_devices`）
8. `inc/sync.php` 计数修正：`新增 = bound - fixed`（`bound` 已把纠正算进去，原来同一张卡数了两次）

## 六、验收（线上实测）

```
设备候选 count = 2
  09a4d0ab0ee93616    len=16  src=cards.json,mysql.card_devices  cards=1
  ce8ffeb7d08cfb36    len=16  src=cards.json,mysql.card_devices  cards=3
违规条数（9 位数字 + 32 位）= 0

card_players: card 8 | pub 819675745 | server_id 9 | auto     ← 曾经过期成 7
cron 幂等：不再打印「卡密自动绑定」行（新增 0 / 纠正 0 时不输出）
device_ban.txt = 0 B ｜ 无 PHP Warning/Fatal 新增
```

## 七、已知缺口（未修，等决定）

1. **桥不判 `kind='device'`**。设备维度只有 SDK 一层在拦；如果玩家绕过 SDK 直连，设备封禁形同不存在。
2. **`player.delete` 不删 `card_players`**（只清零 `server_id`）。删号后绑定行仍在，靠自动绑定回填 —— 这是有意选择的非破坏性做法。
3. `accounts.db` 里 `shittim_server_id IS NULL` 的历史行，删号时不会被清理（`ban_delete_account` 只删 `shittim_server_id = ?` 的行）。

## 八、回滚

```
# 第 2 轮
cp -a /root/DEVFIX2_20261118_215734/inc/bans.php   /www/wwwroot/ba_cardadmin/inc/bans.php
cp -a /root/DEVFIX2_20261118_215734/pages/bans.php /www/wwwroot/ba_cardadmin/pages/bans.php
cp -a /root/DEVFIX2_20261118_215734/inc/sync.php   /www/wwwroot/ba_cardadmin/inc/sync.php
# 第 1 轮
cp -a /root/DEVFIX_20261118_215524/inc/players.php /www/wwwroot/ba_cardadmin/inc/players.php
cp -a /root/DEVFIX_20261118_215524/inc/bans.php    /www/wwwroot/ba_cardadmin/inc/bans.php   # 需先回第2轮
cp -a /root/DEVFIX_20261118_215524/pages/bans.php  /www/wwwroot/ba_cardadmin/pages/bans.php # 需先回第2轮
```

当前线上 md5：

```
inc/bans.php     d50d59a5fa1be0ea7a672c2892027379
pages/bans.php   6c06f2efcdb203fd53366499d764a59e
inc/players.php  7722f9c109c056a7b6ad89920d60f2d4
inc/sync.php     14ae093fbc599467e9738e61d5ae093b
```
