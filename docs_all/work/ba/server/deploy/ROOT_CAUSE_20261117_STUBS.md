# 根因分析：桥的「桩」层 —— 2026-11-17 18:5x

> 本文只记录**已验证的事实**和**待验证的假设**，两者分开放。
> 用户报告的三个现象：①弹窗 ②卡在幽香记忆大厅 ③杀进程重登后教程从头开始。

---

## 一、已验证的事实（都带证据）

### F1 弹窗内容变了：`account_auth invalidprotocol`

- 修复前：弹窗显示 `FUQPRE2OHCSXGOQRNGJQOAOCD4`
- 修复后（删掉 `cn_inner27.py:98` 那行硬编码 `EncryptedUID`）：弹窗显示 **`account_auth invalidprotocol`**
- 用户描述：点确定后**仍可继续游玩**，但点「跳过剧情进入战斗」这类按钮时**一直弹**
- ⇒ 弹窗不是「假 UID 导致」，而是**客户端真的在做协议校验并且失败**，`EncryptedUID` 只是错误弹窗里附带显示的客服 UID。

### F2 桥对绝大多数协议**没有转发给 Shittim**，用的是写死的桩

`api_all_requests.log`（10:52 那一轮，15 条）里的生成器名：

| 协议 | 路径 | 响应字节 | 生成器 | 性质 |
|---|---|---|---|---|
| 1002 | /api/account/auth | 3520 | (1002 专分支) | 桥自建 |
| 24000 | /api/academy/getinfo | 1772 | `academy-24000-v3` | **桩** |
| 1017 | /api/account/loginsync | 122968 | `loginsync-1017-dynamic` | **桩** |
| 4000 | /api/item/list | 640 | `simple-4000` | **桩** |
| 3 | /api/networktime/sync | 600 | `networktime-3` | **桩** |
| 26000 | /api/contentsave/get | 600 | `simple-26000` | **桩** |
| 90004 | /api/management/data | 2092 | `management-90004` | **桩** |
| **1005** | **/api/account/gettutorial** | **512** | **`simple-1005`** | **桩（关键）** |
| 90011 | /api/shop/listtutorialgacha | 512 | `min+base` | **桩** |
| 8000 | /api/mission/list | 3500 | relay2 → Shittim | 真 |
| 8006 | /api/mission/guidemissionseasonlist | 3500 | relay2 → Shittim | 真 |
| 35003 | /api/minigame/missionlist | 3500 | relay2 → Shittim | 真 |
| 16000 | /api/toast/list | 3500 | relay2 → Shittim | 真 |
| 25003 | /api/event/rewardincrease | 3500 | relay2 → Shittim | 真 |
| 15002 | /api/opencondition/eventlist | 3500 | relay2 → Shittim | 真 |
| 36001 | /api/notification/eventcontentreddotcheck | 3500 | relay2 → Shittim | 真 |

> 注：`3500` 不是「同一个兜底 stub」，而是 CN 信封层的固定开销；15 条响应的 sha256 全部互不相同（实测 15/15 distinct）。

**⇒ `Account_GetTutorial`(1005) 走的是桩 `simple-1005`。** 客户端每次登录问「我教程做到哪」，拿到的是桥里写死的假数组，而不是 Shittim 里 `AccountTutorials` 的真实值。

### F3 教程进度**确实**发到了 Shittim，但没有产生可见变化

- Shittim `log.txt`：`03:09:37` 和 `03:11:53` 各有一次 `Account_SetTutorial`(1006) → 200
- 但库里 `AccountTutorials` 全表**只有一行**：`(AccountServerId=2, TutorialIds=[1,2])`
- **全库没有任何 `2026-11-17 03:1x` 的时间戳**
- `ScenarioHistories` 仍是 11-14 建号时的 4 行；`ScenarioGroupHistories` 0 行

源码语义（`AccountHandler.cs:636-662`）：`SetTutorial` 是**整份覆盖**，无行建行、有行替换，`SaveChangesAsync` 在 `:660`（分支外）。

### F4 库是健康的，不是写不进去

```
PRAGMA journal_mode = wal；integrity_check = ok；quick_check = ok
shittim.sqlite3        626688 B  mtime 2026-11-17 03:16:29
shittim.sqlite3-wal         0 B  mtime 2026-11-17 18:19:16
无 -journal；df 剩 14 G；inode 16%
```
⇒ 排除「磁盘满 / 库锁死 / 权限不对」。

### F5 账号没有「每次登录新建」

`Accounts` 只有 3 行：
```
ServerId 1  PublisherAccountId NULL         DevId schaleLoveSENSEI  Lv90  Schale
ServerId 2  PublisherAccountId 314816420    Lv1   LastConnectTime 2026-11-14 02:51:54  ← 从未更新
ServerId 3  PublisherAccountId 1013178778   Lv1   LastConnectTime 2026-11-17 01:51:21
```
同一个 `PublisherAccountId` 没有多行。

**但**：桥自己的 `accounts.db` sessions 表显示 **10:52 那次登录的 publisherId 是 `1013178778`（=ServerId 3）**，不是卡密对应的 `314816420`（=ServerId 2）。
`1013178778` 恰好是官方抓包 fixture 里那个账号的 `DevId`（`00_1002_api_account_auth.response.json:31`）。

### F6 客户端在某一跳之后**停止发请求**，而且每次停的位置不一样

- 03:12 那一轮：`… → 25003 → 15002 → 36001` 之后静默 18 秒，然后客户端重启（新一次 1002）
- 10:52 那一轮：`… → 16000 toast/list` 之后就没有下一条
- 18:17 那一轮：只发了 `GET /api/state`（676 B），之后**一个游戏协议都没有**

官方时序里 16 条之后应该接着 `7001 mail/check`，而 **7001 / 28019 / 43010 / 29002 / 7003 / 7000 / 6000 / 5000 / 5001 / 6020 在我们的 577 条日志里出现次数 = 0**。

### F7 官方响应 vs 我们的响应（字段级差异）

| 字段 | 官方 `Toast_List` | 我们的 `Toast_List` |
|---|---|---|
| `ServerNotification` | `0` | `8` |
| `ToastDBs` | `null` | `[]` |
| `SessionKey` | 有（含 `MxToken`） | **无** |
| `RequestId` | 有 | **无** |

源码层（`shittim-analyst` 核实）：
- `ServerNotification = 8` = `ServerNotificationFlag.HasUnreadMail`，来源 `GatewayController.cs:352-353`：账号邮箱非空就打这个位。**不是 bug**，官方账号当时没未读邮件所以是 0。
- **`RequestId` 在 Shittim 全树 0 命中** —— 从来没实现过。
- `SessionKey` 只在 4 个协议上回显（`GatewayController.cs:320-325`：`Account_Auth` / `Account_Auth2` / `ProofToken_RequestQuestion` / `ProofToken_Submit`），且是**回显客户端发来的那份**（`:265-266`），客户端不带就为 `null` → 被 `DefaultValueHandling.Ignore` 丢掉。

### F8 记忆大厅：服务端会回空数组，不会报错

- `MemoryLobby_List`(12000) → `MemoryLobbyHandler.cs:34` → 空表时返回 `[]`
- `MemoryLobby_SetMain`(12001) → `:47` `account.MemoryLobbyUniqueId = request.MemoryLobbyId;` **不校验拥有关系**
- `MemoryLobbies` 表 0 行；`Mails` 里 `ParcelInfos` 含 `"Type":8` 的 = 0 条 ⇒ **从来没有发过任何记忆大厅**
- 源码里**不存在**「教程完成 → 发奖励」的逻辑；奖励只能从 `Campaign_TutorialStageResult`(6018) → `CampaignStageRewardExcelT` → ExcelDB 表 `CampaignStageRewardDBSchema` 走
- 而 **6017 / 6015 / 6018 在我们的日志里出现次数 = 0**

---

## 二、根因（已确认到代码行，2026-11-17 19:0x）

### RC1 教程进度永远为 0 —— `simple-1005` 恒返回 `TutorialIds: []`

源码 `account_auth_probe.py`：
```python
1984 # 新号初始教程进度 = 空（q7_tutorials.initial.TutorialIds = []）。
1985 # 只给调试/复现官方样本用 --tutorial-ids 覆盖；bridge 永远发空。
1986 SIMPLE_TUTORIAL_IDS = ()

2115     if num == 1005:
2116         prog = SIMPLE_TUTORIAL_IDS if tutorial_ids is None else tutorial_ids
2117         return {
2118             'Protocol': 1005,
2119             'SessionKey': {'AccountServerId': account_id, 'MxToken': mxtoken},
2120             'ServerTimeTicks': int(ticks),
2121             'ServerNotification': 0,
2122             'RequestId': rid,
2123             # 进度表：新号一条教程都没播过 -> 空
2124             'TutorialIds': [int(x) for x in prog],
2125         }
```
`simple_route()` 在 `L2254` 调 `simple_build(num, account_id, mxtoken, rid, ticks)` —— **不传 `tutorial_ids`** ⇒ 永远走 `SIMPLE_TUTORIAL_IDS = ()`。

运行期实证（`api_all_requests.log`）：
```
10:52:40  simple_proto=1005  simple_name='Account_GetTutorial'  simple_keys=6  simple_tutorial_ids=0
18:26:29  simple_tutorial_ids=0
18:32:29  simple_tutorial_ids=0
```
**⇒ 客户端每次登录问「教程做到哪」都拿到 `[]`，与库里 `AccountTutorials=(2,'[1,2]')` 完全脱钩。**
**⇒ 闭环：「教程从头开始」= 拿到 `[]` → 视为全未完成 → 重播教程 → 半途卡住 → 重登 → 又拿到 `[]`。**

### RC2 `invalidprotocol` —— 响应外层 `protocol` 是字面量 `"Unknown"`

实测落盘 `/www/wwwroot/_ba_state/last_direct_envelope_plain.txt`（mtime `2026-11-17 18:32:29.223945741`，正是用户复现那一秒）：
```json
{"protocol":"Unknown","packet":"{\"Protocol\":90011,\"ServerTimeTicks\":639305371492284570,\"ServerNotification\":0,\"RequestId\":\"fd5bb8cf-1eef-4845-b94d-eff80d38d170\",\"MissionProgressDBs\":[],\"EventMissionProgressDBDict\":{},\"BattlePassMissionProgressDBDict\":{},\"StaticOpenConditions\":[]}","requestid":"fd5bb8cf-1eef-4845-b94d-eff80d38d170"}
```
`_cn_envelope`（`L1257-1285`）把 `proto_name` **一路透传**到 `out["protocol"]`，没有校验、没有 token 化 ⇒ `"Unknown"` 是**通用兜底分支**（`_generic_protocol_response` / `build_min_response`，`rec['fallback']='min-envelope'`）拿不到协议名时的占位名。

官方 fixture 里该字段是 PascalCase 全名，例如 `"Account_Auth"`（`00_1002_api_account_auth.response.json:9`）。
⇒ 客户端按外层名字查协议 → 查不到 → `invalidprotocol` 弹窗。

### RC3 账号身份在转发路径上被拒

```
acct_svc = "fallback:AuthRejected"
acct_err = AuthRejected('请求里既没有 DevId 也没有 DeviceUniqueId —— 没有稳定身份键就拒绝建号，
                          否则每次 token 轮换都会变成一个新账号')
```
出现于**所有 relay/relay2 转发的请求**（24000/4000/3/26000/8006/8000/35003/16000/36001/90011 全部如此）；而 `1002` 自己那次是 `acct_svc="on"`、`acct_server_id=10000000001`。
客户端带来的 `SessionKey.AccountServerId` 一直是 `10000000001`（=桥自己的号），而 `simple_*` 桩固定写 `simple_account_id = 2`（=Shittim 的号）。

---

## 二·旧 根因假设（保留作追溯，已被 RC1/RC2/RC3 取代）

### H1（主假设）桥的「桩层」是根因

客户端问「我教程做到哪」(1005)、「我有哪些道具」(4000)、「我的存档」(26000)、「我有哪些学院」(24000)……这些**全部由桥里写死的桩回答**，与 Shittim 的真实数据库无关。

后果链（假设）：
1. 客户端拿到的永远是桩里的固定 `TutorialIds`
2. 打教程后的真实进度虽然写进了 Shittim（或没写），**客户端下一次登录读不到**
3. ⇒ 重登 = 从头开始
4. 桩的响应里 `protocol` 名字/内容对不上时 ⇒ 客户端抛 `invalidprotocol` ⇒ 弹窗

**验证方法**：把 `simple-1005` 的实际输出正文挖出来，看 `TutorialIds` 是不是写死的。

### H2 `invalidprotocol` 来自 `min+base` 这类兜底生成器

`90011 shop/listtutorialgacha` 走 `min+base`，同时 Shittim 报 `Protocol "90011" doesn't have corresponding type registered`（8 次）。
如果 `min+base` 输出的外层 `protocol` 名字与被请求的不一致，客户端就会判 `invalidprotocol`。
**而这恰好对应「跳过剧情进入战斗」这一步** —— 用户正是在这个动作上反复看到弹窗。

### H3 身份漂移

客户端在 10:52 用的是 `publisherId=1013178778`（ServerId 3），不是卡密的 `314816420`（ServerId 2）。
如果这个值来自桥回吐的 `AccountDB.DevId`，那么身份会随桥的改动而漂移，玩家的存档会"跑到别的账号上"。

---

## 三、修复方向（等 H1/H2 验证后再定稿）

**原则：桥只做协议适配（解密/加密 + token 映射 + 信封），业务数据一律转发 Shittim。桩全部退役。**

分阶段：
1. **1005 改转发** → 验证客户端拿到的 `TutorialIds` 变成 Shittim 真值 → 验证教程进度能否保存
2. **90011 补实现**（Shittim 里没有该协议类型）→ 让教程抽卡不再报错
3. **4017/6000/5000/7000 等未出现协议**：先确认客户端到底有没有发、发去哪了
4. 其余桩（4000/26000/24000/90004/1017/3）逐个改转发，每改一个做一次回归
5. 桩层全部退役后，重新做一次完整的「新号 → 教程 → 大厅 → 存档 → 重登」验收

---

## 三·五、2026-11-17 晚 修复结果（用户实测）

### 已彻底解决（用户亲测确认）

| 现象 | 根因 | 修法 | 结果 |
|---|---|---|---|
| 弹窗 `invalidprotocol` | `cn_wrap_mode=a_proto_int` 让 `_cn_enc_b64` 把所有走 `_cn_envelope` 的响应替换成 `Account_Auth(1002)`；外加 `protocol_names.txt` 是垃圾表（159 行 Redis/IRC 错误码），导致协议名解析成 `"Unknown"` | FIX-1 补协议名映射 + FIX-3 relay 路径改用 `_cn_send_envelope` | ✅ 消失 |
| 教程每次从头开始 | `simple-1005` 恒返回 `TutorialIds: []`（`SIMPLE_TUTORIAL_IDS = ()`），与库里的真值脱钩 | FIX-2 把 1005 移出 `RL2_HANDLED`，改走 relay → Shittim 真读库 | ✅ 消失 |
| 存档不保存 | 同上（进度其实一直写对了，是客户端读回来的值是假的） | 同上 | ✅ 正常 |

**验证证据（客户端实际收到的明文）**
```json
改前 1005: {"protocol":"Account_Auth",        "packet":"{\"Protocol\":1002,...,AccountDB...}"}
改后 1005: {"protocol":"Account_GetTutorial", "packet":"{\"Protocol\":1005,\"TutorialIds\":[1,2]}"}
改后 19003:{"protocol":"Scenario_Skip",       "packet":"{\"Protocol\":19003,...}"}
```

### 仍未解决：大厅引导教程卡住

**症状（用户描述 + 三方取证一致）**
- 点按有动画反馈，但游戏不推进
- 屏幕上有「大厅内引导教程」挡住 UI
- **一切都点不了，只有立绘动画在动**

**取证结论：断点在客户端本地，不是网络**
```
服务端：卡住期间 113 秒内 0 个新请求，最后一条 = 18:42:54.169 Notification_EventContentReddotCheck(36001)
手机侧：DNAT 计数 5 秒零增长（828 pkts / 52,465 B → 完全不变）
        logcat 零异常（无 Exception/NullReference/InvalidProtocol）、无 ANR、/data/anr/ 空
        213 个线程，0 个 D 状态、0 个僵尸；主线程 do_epoll_wait（空闲正常）；UnityMain 在跑
        唯一阻塞：TID 15832 comm=open.yostar.net 卡在 recvfrom()（走真实外网，与私服无关）
        3 条 CLOSE-WAIT 带未读字节（24/24/1 B）——远端 IP 111.2.79.11 / 39.174.179.5 / 112.15.33.35
        **这三个 IP 在我们的 tcp-access.log 里 0 命中，是手机直连真实外网，与私服无关**
        10 条 CLOSE-WAIT 的其它连接同理
```

**当前最强嫌疑：指导任务列表为空**
| 协议 | 官方 | 我们 |
|---|---|---|
| `Mission_GuideMissionSeasonList`(8006) | **160,216 B**，`MissionProgressDBs` 200+ 条（`Category:4`） | `GuideMissionSeasonDBs: []` + `MissionProgressDBs: []` |

官方那 200+ 条的 `MissionUniqueId` 形如 `1000212 / 1000223 / 1000300 / 1000410 / 1000500 ...`，每条带 `{AccountServerId, MissionUniqueId, Category:4, StartDate, ProgressParameters:{...}, Complete?}`。

BA 的大厅引导教程第一步就是引导去看/领指导任务 —— 列表空着，那一步就没有可操作对象。

### 已备好但未部署的修复

`MomoTalkHandler.cs` `MomoTalk_FavorSchedule` 的 `if (amount == 0) continue;` 会丢掉 `ParcelType.MemoryLobby` 且 `amount=0` 的奖励（幽香的大厅就挂在 `AcademyFavorSchedule Id=130101`，`RewardAmount=[20,0]`）。
- 已改 + 本地构建通过：`_build_favorlobby\Shittim-Server.dll` 2,669,568 B / `84517933e942e780fccc168fb2166c0b2a23bd07938a45e346d59c86d467abbc`
- **未部署**（避免在验证期引入第二个变量）

### 当前服务端版本基线

| 部件 | 大小 | sha256 | 备注 |
|---|---|---|---|
| `account_auth_probe.py` | 146,511 B | `128c6ba9bec71590a6443610a3814cfb8d56f0a03b973241e54dabf1bde405d4` | FIX-1 + FIX-2 + FIX-3，pid 2615219 |
| `cn_inner27.py` | — | `7793882d40231f588045862ee8b80f3c1f89e3202d2fda1d7f345150f3257208` | 141 行，假 `EncryptedUID` 已删 |
| `Shittim-Server.dll` | 2,669,568 B | `01f5b906159d81b883f86c03df599bcd7936a26ef7db72c62e75d079946a4a18` | 未动 |
| `shittim.sqlite3` | 626,688 B | — | `MemoryLobbies=[(1,2,13010)]`，`AccountTutorials=[(2,'[1,2,3,4]')]` |

### 数据改动与回滚

```
SessionKey/AccountTutorials:  sqlite3 /www/wwwroot/ba_srv/shittim.sqlite3 "UPDATE AccountTutorials SET TutorialIds='[1,2]' WHERE AccountServerId=2;"
备份: /tmp/shittim.sqlite3.pre-tut.184627  (f9fbe21f93cc3007d90bf7eaa5e1ead60280d98a6e5d836531d90c56e3452291)

SessionKey/MemoryLobbies 那一行:  DELETE FROM MemoryLobbies WHERE AccountServerId=2 AND MemoryLobbyUniqueId=13010;
备份: /tmp/shittim.sqlite3.pre-lobby.183806  (ee9cf4060443ec659dbcd14cfc176fb51b2ba5e104ade718b4360997392dc5ca)

桥回滚(FIX-3 之前):  cp -a account_auth_probe.py.fix3pre.183916 account_auth_probe.py + 重启
桥回滚(FIX-2 之前):  cp -a account_auth_probe.py.fix2pre.183713 account_auth_probe.py + 重启
桥回滚(FIX-1 之前):  cp -a account_auth_probe.py.namefix.pre.20261117-183500 account_auth_probe.py + 重启
```

## 四、可回滚点

- 弹窗修复回滚：`cp -a /www/wwwroot/bapatch/tools/cn_inner27.py.bak.20261117-182233 /www/wwwroot/bapatch/tools/cn_inner27.py` + 重启桥
- 当前桥 pid `2611886`（18:22 重启后）
- 当前 `cn_inner27.py` sha256 `7793882d40231f588045862ee8b80f3c1f89e3202d2fda1d7f345150f3257208`（141 行）
- Shittim 未改动：`01f5b906…` / active
