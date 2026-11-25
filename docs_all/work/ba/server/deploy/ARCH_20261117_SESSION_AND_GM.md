# 架构现状：会话链、账号 ID、GM 控制台（2026-11-17 01:45）

记录人：Lead。所有结论都有实测或源码位置支撑，**推断单独标注**。

---

## 1. 桥 ↔ Shittim 的会话链（已完全打通）

```
客户端 POST /api/...  (CN 信封)
   ↓
桥 _bridge()：parse_cn_multipart → NAME_TABLE/EXTRA_TOKENS 查协议名
   ↓
path A（能解密时）：cn_cipher.decode_packet → req_json
   ↓
ensure_session(rec)                        ← 向内打 1014，铸造 Shittim 的 SessionKey
   ↓
req_json['SessionKey'] = sk                ← 客户端的请求原本没有这个字段，桥注入
   ↓
post_gateway(req_json) → http://127.0.0.1:5000/api/gateway   （multipart 字段名 mx）
   ↓
unwrap_gateway_response → self._cn_envelope(name, obj, rec)  ← Shittim 的答案包进 CN 信封
```

**关键常量（`account_auth_probe.py` L160-168）**
```
TARGET_BASE  = 'http://127.0.0.1:5000'
GATEWAY      = 'http://127.0.0.1:5000/api/gateway'
UID          = '314816420'
TOKEN        = '61de1d1b7519ab1231866f74c11fcfdd1f80b210'
ENTER_TICKET = base64('314816420/61de1d1b…')
```

`ensure_session()`（L1063-1092）的逻辑：
- `SESSION.session_key` 有值 → `session_source = 'cache'` 直接返回
- 没有 → 用**硬编码的 `ENTER_TICKET`** 打 `Account_CheckNexon(1014)`，取回 `SessionKey` → `session_source = 'fresh'`
- 失败 → `checknexon_err`，返回 `(None, None)`

⇒ **ticket 是写死的**，所以任何登录最终铸造的都是 **Shittim 的 `Accounts.ServerId=2`**（即 `UserAccounts.NpSN=314816420`）。单机私服这样正好（存档只有一份）；将来要支持多账号必须改这里。

**实测（2026-11-17 01:45:37，Shittim 重启后）**
```
force_reauth        = True
session_source      = fresh
checknexon_code     = 200      checknexon_ms = 720     checknexon_resp_len = 1085
checknexon_err      = 不存在
session_key         = {'AccountServerId': 2, 'MxToken': '42b76ce4-2b99-4850-a574-f6be3232d265'}
session_injected    = True
auth_code/auth_resp_len = 200 / 3740
Shittim 侧：Account_CheckNexon(1014) -> 200 in 434ms；Account_Auth(1002) -> 200 in 312ms
```

---

## 2. ⚠️ 两套账号 ID 空间（理解 P2 必须知道）

| 侧 | 账号 id | 来源 |
|---|---|---|
| 客户端看到的 `SessionKey.AccountServerId` | **10000000000** | 桥的账号服务（`acct_svc=on, acct_server_id=10000000000`） |
| Shittim 内部 / 数据库 | **2** | `UserAccounts.NpSN=314816420` → `Accounts.ServerId=2` |

桥发给 Shittim 的每个请求里注入的是 **Shittim 的 session（id=2）**，所以 Shittim 永远只认账号 2。
⇒ **GM 命令必须用 `--id 2`**（Shittim 控制台默认就是 `id ?? 2`）。
⇒ 将来若要区分多个玩家，这套映射必须重做。

---

## 3. 强制重建会话（重启 Shittim 后必须做）

```bash
touch /www/wwwroot/bapatch/cn_bridge_force_reauth.txt
```
- `FORCE_FILE = '/www/wwwroot/bapatch/cn_bridge_force_reauth.txt'`
- `want_force_reauth()` 命中 → 清 `SESSION` 缓存 → `clear_force()` **自动删掉这个文件**（一次性）
- 实测：01:45:36 触发，01:45:37 文件已被自动删除

### ⚠️ 踩过的坑：用协议 3 去触发 force-reauth 无效

协议 3 被 `patch_3` 的 **HOOK-E 提前接住**，走的是本地生成器，**根本不经过 `ensure_session()`**。
**只有走 path A / path B 的协议（1002 / 1014 / 任何未被 hook 截获的协议）才会触发会话重建。**

⇒ 验证会话链是否正常，**必须用 `1002 /api/account/auth`**，不能用协议 3。

---

## 4. 转发路径的优先级（决定"谁回答请求"）

`_bridge()` 里的顺序：
```
1. parse_cn_multipart
2. name = NAME_TABLE.get(proto_str) or EXTRA_TOKENS.get(proto_str)
3. exp == 'experror'  → 返回错误（调试用）
4. ★ 各补丁的 hook（HOOK-E 等）在这里接管：patch_3 / patch_simple / patch_1017 / patch_24000_v3
5. name is None：
     → _generic_protocol_response()  → 返回 min+base 空壳 ← 8000/8006/90011/35003/16000 卡在这
     → 否则 _forward(body)  → 把原始 CN multipart 原样 POST 给 Shittim（Shittim 不认，无意义）
6. want_decrypt（cn_bridge_exp 以 decrypt+ 开头）→ path A：转发给 Shittim 并用它的答案
7. 否则 path B：synthetic（自造）
```

**⇒ 业务协议至今从未到达 Shittim 的原因：在第 4 步就被补丁 hook 截获了。**
Shittim 日志全历史只见过 4 种协议：`Account_Auth(1002) 172 次 / Account_CheckNexon(1014) 48 次 / NetworkTime_Sync(3) 2 次 / None 3 次`。

> 注：`cn_relay.txt` 这个开关**代码里根本没读**（grep 0 命中），是幽灵文件，不要指望它。

---

## 5. Shittim 的运行方式（2026-11-17 改动后）

```ini
Type=forking            # tmux 包一层
RemainAfterExit=yes
ExecStart=/usr/bin/tmux new-session -d -s shittim -x 220 -y 50 \
          "/root/dotnet10/dotnet /www/wwwroot/ba_srv/Shittim-Server.dll --console --id 2"
ExecStop=/usr/bin/tmux kill-session -t shittim
Restart=always / RestartSec=5（与原值一致）
```

**`--console --id 2` 是必需的**：`GameServer.Main(bool update, bool console, long? id)` 里 `console` 默认 `false`，
不传就**不会启动控制台监听器**（`GameServer.cs:214-224`）。只把 stdin 接到 pty 是不够的。

**GM 命令**：`tmux send-keys -t shittim '!help' Enter` → `tmux capture-pane -pt shittim | tail -60`
实测可用命令：`giveall / giveallequip / give / giveequip / max / currency / characters / mail / unlockall / unlockbattlepass / addeleph / checkitem / inventory / listitem / clearinventory / setaccount / setraid / setseason / setting / help`

### ⚠️ 已知风险：自动拉起能力丢了

`Type=forking` + `RemainAfterExit=yes` 下，systemd 认的主进程是 **tmux server**；
里面的 dotnet 崩了，systemd 看不见，`Restart=always` **不会触发**。

**已补的临时看门狗**（经宝塔面板 API `crontab.AddCrontab` 注册，id=4，名称 `ba_shittim_watchdog`）：
```
*/1 * * * *  ss -lnt | grep -q ':5000 ' || systemctl restart ba-shittim
```
- crontab 已备份：`/root/crontab.bak.20261117-014545`
- 面板查看路径：宝塔 → 计划任务
- **未在面板 DB 的 `tasks` 表里查到该行**（面板这一版存在别处），需在面板 UI 里确认可见

恢复原状：
```bash
cp -a /etc/systemd/system/ba-shittim.service.bak.20261117-014253 /etc/systemd/system/ba-shittim.service
systemctl daemon-reload && systemctl restart ba-shittim && tmux kill-session -t shittim
```

---

## 6. 一些查清了的杂项（省得再查）

| 项 | 结论 |
|---|---|
| 活库 | **`/www/wwwroot/ba_srv/shittim.sqlite3`**（`-wal`/`-shm` 实时在动）。`appsettings.json` 里的 `Data Source=BlueArchive.db` **文件不存在**，是无效默认值 |
| `server_notice.json` | **两个候选路径都不存在** ⇒ 维护门的 `gate_error` 读不到 ⇒ **不拦任何协议**，不是故障源 |
| ExcelDB.db | **SQLCipher 加密库**（`file` 判为 "not a database"），要 `Config.json` 里的 `ExcelDbSqlCipherKey` 才能只读打开。**未使用该密钥** |
| .NET SDK | 只有**运行时** 10.0.15，`--list-sdks` 为空 ⇒ **不能编译 C# 源码** |
| GM HTTP 端点 | `POST /dev/api/command` 是**空壳**（`CommandController.cs:38` 写死 "not yet fully implemented"，从不调 `CommandFactory`，却回 `Success`）⇒ **别用，只会得到假象** |
| 复杂列存储 | 一律 **JSON TEXT**（唯一转换器 `SchaleDataContext.cs:431-457`），**enum 字典键是数字**（如 `{"2":20000}`）；**空串 `''` = 空对象，不要写 NULL** |
| 裸 SQL 顺序坑 | `Echelon` 槽位与 `Account.RepresentCharacterServerId` 引用的是 **`Characters.ServerId`（自增主键）**，不是 `UniqueId`；`AccountCurrencyDB.AccountLevel` 是独立字段 |
| 现成满级样板 | `Accounts.ServerId=1`（`Schale`，Lv90，10 角色满技能满羁绊） |

---

## 7. 待办（按顺序）

1. **P0**：`patch_relay.py` —— 让 `name is None` 的协议走 path A（转发 Shittim）而不是 `min+base`。开关默认关。**进行中**
2. **P0+**：逐个把已知协议也放给 Shittim（一次一个，验一个），关键是 `1005 gettutorial` 与 `1017 loginsync` —— 它们决定教程状态是否落库
3. **P1**：验收 —— 过一小段教程 → 完整退出 → 重登 → 进度还在；并核对 `AccountTutorials` / `MissionProgresses` / `MemoryLobbies` 从 0 行变成有行
4. **P2**：给 `ServerId=2` 发满级存档：`!giveall` + `!max all` + `!currency Gem 3000000`
5. **STAGE 2**：把 bridge / gwstate / sdk / shittim 全部注册进宝塔面板可见可管
