# 44 — bridge 转发行为对照表（`cn_bridge_v5.py`）

> 时间：2026-11-14 04:25 前后
> 对象：`scripts\cn_bridge_v5.py`（294 行，2026-11-14 02:52）——本地副本；线上路径为 `/www/wwwroot/bapatch/` 下的同名文件（按 `:6-19` 的常量推断，**本地无法直接读取线上文件，版本可能不同**）
> 对照物：`report\_tmp\shittim\src\` 源码快照（只读）
> **未连接手机、未连接服务器、未重启任何服务。**

**查档**：`report\42` §1/§5（网关路径与判定树）、`report\43` §4（Queuing 家族）。`report\` 里**没有**任何既有文件做过 bridge 分支梳理（`grep` 全 `report\*.md` 无 `cn_bridge` 分支表）⇒ 本报告是首份。

---

## 0. 一页结论

| 问题 | 答案 |
|---|---|
| bridge 有几条分支 | **4 条**（`forward` 模式 / 未知协议 / `Account_CheckNexon` / `Account_Auth`·`Account_Auth2`）+ 1 条兜底 |
| 真正被"处理"的协议有几个 | **3 个**：`Account_CheckNexon`、`Account_Auth`、`Account_Auth2`（`:249-274`） |
| 其余全部走什么 | `_forward`（`:224-234`）——**把国服原始请求原样打到 `127.0.0.1:5000 + 原路径`** |
| 转发后必然 404 的有多少 | **除极少数例外，全部。** Shittim 全部游戏路由只有 `api/gateway` 一个 POST 入口（`GatewayController.cs:157`），没有 `api/<service>/<action>` 形态 |
| 唯一两个"转发还能成功"的 | `GET /api/Queuing/Ping`（→"Pong"，`GatewayController.cs:150-152`）与 `POST /log`（客户端错误上报，`ServerInfoController.cs:47`） |
| 名称表正确率 | `BUILTIN_NAMES` **43 条**：**23 条是协议枚举里真实存在的名字，20 条在枚举里根本不存在**（§5） |
| 最危险的一条 | `:276-279` 的"其它已知协议先原样转发"——既转发到错路径，又把**名字写错**的协议伪装成"已知" |

**一句话**：**bridge 目前只对 3 个协议做了翻译，其它一切（包括 Queuing 全家）都会被原样丢给一个不存在的路由，然后拿到 404 空 body。**

---

## 1. 分支全图

```
请求进 _handle()                                           :197-222
 ├─ 读 body：Content-Length → self.rfile.read           :198-199
 ├─ mode = mode()                                        :200  (:65-69 读 cn_bridge_mode.txt，缺省 'bridge')
 ├─ 记 rec（含 headers/body_printable）                   :201-205
 ├─ ╔═ 分支 F：mode == 'forward' ════════════════════╗
 │   ║ _forward(body)  → TARGET_BASE + self.path     ║    :208-210 → :224-234
 │   ║ rec['served'] = 'forward'                       ║
 │   ╚═══════════════════════════════════════════════╝
 └─ 否则（bridge 模式）
    ├─ fields = parse_cn_multipart(body)                :237  抓 protocol / encode / packet
    ├─ name = NAME_TABLE.get(proto_str)                 :240  (:45-63，BASE32(MD5(UTF-16LE(name))))
    ├─ ╔═ 分支 U：name is None（未知协议 / 非协议请求）╗
    │   ║ _forward(body)  + rec['fallback']='forward-unknown-protocol' ║  :242-247
    │   ╚═════════════════════════════════════════════╝
    ├─ ╔═ 分支 C：name == 'Account_CheckNexon' ════════╗
    │   ║ ensure_session(rec)  → 拿 SessionKey          ║    :249-250 → :128-158
    │   ║ 失败 → 500 {"error":"checknexon failed"}      ║    :251-252
    │   ║ 成功 → 200 {"protocol":"Account_CheckNexon",  ║    :253-256
    │   ║            "packet":"{Protocol:1014,...}"}    ║
    │   ╚═══════════════════════════════════════════════╝
    ├─ ╔═ 分支 A：name in ('Account_Auth','Account_Auth2') ═╗
    │   ║ ensure_session(rec)                             ║    :259-261
    │   ║ 合成 {"Protocol":"Account_Auth","SessionKey":sk} ║    :262-263
    │   ║ post_gateway(...) → 失败 502                    ║    :264-269
    │   ║ 成功 → 200 {"protocol":"Account_Auth","packet":obj} ║ :272-274
    │   ╚════════════════════════════════════════════════╝
    └─ ╔═ 分支 X：其它一切（兜底）═══════════════════════╗
        ║ _forward(body) + rec['fallback']='forward-known-other' ║  :276-279
        ╚══════════════════════════════════════════════════╝

收尾：_log(rec) → _send(code, resp, ctype)                  :221-222
```

`do_GET = do_POST = do_PUT = _handle`（`:281-283`）——**GET 也走同一条链**，所以一个 `GET /api/Queuing/Ping` 会进 `_bridge`、`parse_cn_multipart` 返回 `{}`、`NAME_TABLE.get('')` → `None` → 落进**分支 U** → `_forward`。

---

## 2. 逐分支细节（含失败路径）

### 2.1 分支内调用的两个共用件

| 函数 | 行号 | 行为 | 失败形态 |
|---|---|---|---|
| `build_mx(obj)` | `:81-86` | `[u32 0][i32 0][0,0]` + `XOR0xD9(u32 明文长度 + gzip(json))` | — |
| `post_gateway(obj)` | `:88-102` | POST 到 `GATEWAY = http://127.0.0.1:5000/api/gateway`（`:18`），multipart 字段 `mx` | 超时/异常 → `return 0, b'{"error":...}'`（`:100-101`） |
| `unwrap_gateway_response(raw)` | `:104-116` | 解 `{"protocol","packet"}`；`packet` 是字符串则再 `json.loads` 一层 | 解析失败 → `(None, None)` |
| `ensure_session(rec)` | `:128-158` | 缓存命中即返回；否则合成 `Account_CheckNexon{EnterTicket, ClientGeneratedKey, ClientGeneratedIV}` 打 Shittim（`:138-142`），从响应里取 `SessionKey`/`AccountId` | 响应里没有 `SessionKey` → `(None, None)`，`rec['checknexon_err']` 记原因（`:148-151`） |

`ensure_session` 的三个隐性分支：

| 条件 | 行 | 效果 |
|---|---|---|
| `cn_bridge_force_reauth.txt` 存在 | `:130-134` | 清空缓存、删标记文件、重新取会话 |
| 缓存命中 | `:135-137` | `rec['session_source']='cache'`，不打 Shittim |
| 需要新建 | `:138-158` | `rec['session_source']='fresh'`，并把 `session_key` / `account_id` 写进 rec |

★ `ENTER_TICKET` 来自 `:23`：`base64("314816420/61de1d1b…")`。**分支 C 的 `SessionKey` 就是这条链铸出来的，与客户端发来的任何东西无关。**

### 2.2 分支 C：`Account_CheckNexon`（`:249-256`）

```python
if name in ('Account_CheckNexon',):
    sk, aid = ensure_session(rec)
    if sk is None:
        return 500, json.dumps({'error': 'checknexon failed'}).encode(), 'application/json'
    out = {"protocol": "Account_CheckNexon",
           "packet": json.dumps({"Protocol": 1014, "ResultState": 1, "SessionKey": sk,
                                 "AccountId": aid}, ...)}
    return 200, ...
```

- **响应体是 bridge 自己拼的**，不是 Shittim 的 `AccountCheckNexonResponse`（那个有 `Birth`/`EncryptedKey`/`SignedKey`/`EncryptedIV`/`SignedIV`，`NetworkProtocol.cs:438-446`）。这里**只回了 4 个字段**。
- `500` 是**全文件唯一会返回非 200 的地方之一**——所以"HTTP 500"在 bridge 日志里反而是强信号（真失败），与 Shittim 的"200 里藏 Error"完全不同。

### 2.3 分支 A：`Account_Auth` / `Account_Auth2`（`:258-274`）

```python
if name in ('Account_Auth', 'Account_Auth2'):
    sk, aid = ensure_session(rec)
    if sk is None:
        return 500, ...
    req = {"Protocol": "Account_Auth", "SessionKey": sk}     # ★ 只带 SessionKey
    code, raw = post_gateway(req)
    gp, obj = unwrap_gateway_response(raw)
    if not isinstance(obj, dict):
        return 502, raw, 'application/json'                  # ★ 唯一 502
    out = {"protocol": "Account_Auth", "packet": json.dumps(obj, ...)}
    return 200, ...
```

- `Account_Auth2` 请求会被**当成 `Account_Auth` 发出去**（`:262` 硬编码 `"Protocol": "Account_Auth"`），但**响应信封仍写 `"protocol":"Account_Auth"`**（`:272` 硬编码）——**即使客户端问的是 `Account_Auth2`，回的也是 `Account_Auth`**。这是 §8 里的一条待确认项。
- 断链判据：`502` 表示 Shittim 回了不可解析的东西；`200 + obj` 表示成功。`rec['auth_keys']`（`:271`）会记下顶层键，**这是事后核对"响应里到底有什么"的最快入口**。

### 2.4 分支 U / X：两条转发（`:242-247` / `:276-279`）

两者**代码完全相同**，只是 `rec['fallback']` 的标签不同（`forward-unknown-protocol` vs `forward-known-other`）。差别在语义：

- **U**：客户端发来的 `protocol` 字段没在 `NAME_TABLE` 里 ⇒ 我们连它是什么协议都不知道。
- **X**：名字在表里 ⇒ 我们"知道"它是什么，但**依然原样转发**（注释 `:276`：「后面再逐个接管」）。

⇒ **两条分支的结果一样：请求被原路径打到 Shittim。**

---

## 3. `_forward` 打到哪 + Shittim 有哪些路由

### 3.1 转发目标规则

`cn_bridge_v5.py:224-234`

```python
def _forward(self, body):
    url = TARGET_BASE + self.path          # :225   TARGET_BASE = http://127.0.0.1:5000  (:17)
    req = urllib.request.Request(url, data=body if body else None, method=self.command)   # :226
    for k, v in self.headers.items():
        if k.lower() not in HOP:           # :227-229  HOP = host/content-length/connection/accept-encoding/transfer-encoding (:27)
            req.add_header(k, v)
    ... 30s 超时 ...                        # :231
```

⇒ **转发目标 = `http://127.0.0.1:5000` + 客户端原始 URI（一字不改）。**

原始 URI 的形态，我们**只实测过一例**：`POST /api/account/auth`（`report\35` §三 的样本）。按 `Queuing/Ping` 这条路由的存在（三段、大写 `Q`），可推客户端走 **`/api/<服务>/<动作>`** 形态（`[推断]`）。

### 3.2 Shittim 已知路由清单（本地快照可证的 7 条）

| # | 方法 | 路由 | 出处 | 返回 |
|---|---|---|---|---|
| 1 | GET | `api/Queuing/Ping` | `GatewayController.cs:150-152` | `"Pong"` |
| 2 | GET | `api/gateway` | `:154-155` | 200 空 body |
| 3 | **POST** | **`api/gateway`** | **`:157-158`** | **唯一业务入口** |
| 4 | GET | `/com.nexon.bluearchive/server_config/{*filename}` | `ServerInfoController.cs:19` | Steam 版本配置 |
| 5 | GET | `/com.nexon.bluearchivesteam/server_config/{*filename}` | `:20` | 同上 |
| 6 | POST | `/log` | `:47` | 客户端错误上报 |
| 7 | GET | `/health` | `GameServer.cs:251` | `{"status":"ok",...}` |

`[未找到]`：`IasController` / `AdminController` / `DashboardController` 等控制器**不在本地快照**（`report\28` §8 也标为"未读"）。它们可能追加 `/<ias>/...`、`/admin/...` 形态的路由，但**不会**是 `api/<service>/<action>` 的游戏协议形态——因为游戏协议只有 `POST api/gateway` 一条（`report\28` §1.3 已对全项目 `.cs` 做过模板检索）。

### 3.3 结论：转发 = 404 的推导

```
客户端 POST /api/account/auth  → 落到 3.2 的哪一条？→ 一条都不匹配 → 404 空 body
客户端 POST /api/queuing/...   → 同上 → 404（若路径是 POST 到 api/Queuing/Ping 这个 GET 路由，则是 405）
客户端 GET  /api/Queuing/Ping  → ✅ 命中 #1 → "Pong"
客户端 POST /log               → ✅ 命中 #6 → {"status"?} 200（Shittim 记 "Game Client Error Detected!"）
```

> ⚠ 关于大小写：ASP.NET Core 的路由匹配默认**大小写不敏感**（框架默认行为，本仓库**没有**显式配置，`GameServer.cs:234-253` 无相关代码）⇒ `[推断]` `GET /api/queuing/ping` 也能命中 #1。若实测不符，说明中间还有一层（nginx location 大小写敏感）在起作用。

---

## 4. ★ 必然 404 的黑名单

### 4.1 判据（一句话）

> **只要一个请求落进分支 U 或 X（`:242-247` / `:276-279`），并且它的原始 URI 不是 `/api/Queuing/Ping`（GET）也不是 `/log`（POST），它就必然拿到 404 空 body。**

不需要知道协议名，也不需要知道枚举。**这是由"Shittim 只有 `api/gateway` 一个 POST 业务入口"直接推出的。**

### 4.2 黑名单（按"客户端可能发的时间顺序"排）

| 阶段 | 客户端可能发的协议 | bridge 现状 | 转发目标（`TARGET_BASE` + 原路径） | Shittim 路由 | 结果 |
|---|---|---|---|---|---|
| 队列 | `Queuing_GetCryptoKeys`(50001) | **X**（`NAME_TABLE` 里有） | `/api/queuing/getcryptokeys` `[推断]` | 无 | **404** |
| 队列 | `Queuing_GetAuthTicket`(50002) | **X** | `/api/queuing/getauthticket` | 无 | **404** |
| 队列 | `Queuing_GetTicket`(50000) | **X** | `/api/queuing/getticket` | 无 | **404** |
| 队列 | `Queuing_ProcessWaitingQueue`(50003) | **X** | `/api/queuing/processwaitingqueue` | 无 | **404** ← **最像本轮卡点**（`report\43` §6-③） |
| 队列 | `Queuing_Ping`（非协议） | **X**（幽灵名） | `/api/queuing/ping` | **#1 命中** | ✅ `"Pong"` |
| 认证 | `Account_CheckYostar`(1009) | **X**（在表里） | `/api/account/checkyostar` | 无 | **404** ← **国服正牌登录协议！** |
| 认证 | `Account_CheckNexon`(1014) | **C 接管** | 不转发 | — | ✅ 合成 200 |
| 认证 | `Account_Auth`(1002) | **A 接管** | 不转发 | — | ✅ 真 200 |
| 认证 | `Account_Auth2`(1012) | **A 接管**（但按 Auth 发） | 不转发 | — | ⚠ 回的是 `Account_Auth` |
| 认证 | `Account_GetTutorial`(1005) | **X** | `/api/account/gettutorial` | 无 | **404** |
| 认证 | `Account_SetTutorial`(1006) | **X** | … | 无 | **404** |
| 认证 | `Account_Nickname`(1001) | **U**（v5 表里**没有**这个名字！v6 才加） | `/api/account/nickname` | 无 | **404** |
| 认证 | `Account_PassCheck`(1007) | **X** | … | 无 | **404** |
| 认证 | `Account_VerifyForYostar`(1008) | **X** | … | 无 | **404** |
| 认证 | `Account_GetIdCardInformation`（枚举里不存在） | **X**（幽灵名） | `/api/account/getidcardinformation` | 无 | **404** |
| 时间/会话 | `NetworkTime_Sync`(3) | **X** | `/api/networktime/sync` | 无 | **404** |
| 时间/会话 | `Session_Info`(2) | **X** | `/api/session/info` | 无 | **404** |
| 时间/会话 | `System_Version`(1) | **X** | `/api/system/version` | 无 | **404** |
| 大厅灌入 | `Account_LoginSync`(1019) | **U**（v5 表里没有） | `/api/account/loginsync` | 无 | **404** |
| 大厅灌入 | `Character_List`(2000) / `Mission_List`(8000) / `Mail_List`(7000) / `Item_List`(4000) / `Echelon_List`(5000) / `Campaign_List`(6000) … | **X 或 U** | 各自路径 | 无 | **404** |

**⇒ 黑名单的本质：`Account_CheckYostar` 也在里面。** 也就是说，**即使国服走的是它自己那条正牌登录链（50002 → 1009），bridge 也会在第二步把它打到 404**——因为 bridge 认的是 `Account_CheckNexon`(1014)，不是 `Account_CheckYostar`(1009)。

> 这条单独拎出来说：`cn_bridge_v5.py:249` 的分支条件是 `if name in ('Account_CheckNexon',)`，**没有 `Account_CheckYostar`**。若国服发 1009，它就掉进分支 X。`report\43` §4.1 的国服链路（50002 → 1009）在此断掉。

### 4.3 唯一"转发还能成功"的两个例外（务必保留）

| 请求 | 结果 | 意义 |
|---|---|---|
| `GET /api/Queuing/Ping` | Shittim #1 → `"Pong"` | **客户端探活能过**。它过了反而说明"客户端在排队态"，是 `report\42` §5-D3-4 的正面证据 |
| `POST /log` | Shittim #6 → 200，`log.txt` 出现 `Game Client Error Detected!` | **`report\42` §3.4 的判据通道现在就是通的**，不需要改 bridge 就能用 |

⇒ **结论：`POST /log` 不该被接管，让它继续转发。**（这也是为什么 §7 的补路由清单里没有 `/log`。）

---

## 5. `NAME_TABLE` 审计：43 条里 20 条是错名

`NAME_TABLE` 由 `BUILTIN_NAMES`（`:29-40`，43 条）∪ `NAMES_FILE`（`:16`，`/www/wwwroot/bapatch/tools/protocol_names.txt`，**线上文件，本地读不到**）经 `b32md5` 建表（`:45-63`）。

**本地能审计的只有 `BUILTIN_NAMES` 这 43 条。** 逐条对照 `ProtocolData.cs`（全文 1268 行）：

### 5.1 名字正确且在枚举里（23 条）

| 名字 | 协议号 | 出处行 |
|---|---|---|
| `Account_Create` | 1000 | `ProtocolData.cs:26` |
| `Account_Nickname` | 1001 | `:27`（**v5 表里没有，v6 才有**） |
| `Account_Auth` | 1002 | `:28` |
| `Account_GetTutorial` | 1005 | `:31` |
| `Account_SetTutorial` | 1006 | `:32` |
| `Account_PassCheck` | 1007 | `:33` |
| `Account_VerifyForYostar` | 1008 | `:34` |
| `Account_CheckYostar` | 1009 | `:35` |
| `Account_Auth2` | 1012 | `:38` |
| `Account_CheckNexon` | 1014 | `:40` |
| `System_Version` | 1 | `:21` |
| `Session_Info` | 2 | `:22` |
| `NetworkTime_Sync` | 3 | `:23` |
| `Queuing_GetTicket` | 50000 | `:500` |
| `Queuing_GetCryptoKeys` | 50001 | `:501` |
| `Queuing_GetAuthTicket` | 50002 | `:502` |
| `Queuing_ProcessWaitingQueue` | 50003 | `:503` |
| `Character_List` | 2000 | `:52` |
| `Mission_List` | 8000 | `:110` |
| `Mail_List` | 7000 | `:105` |
| `Mail_Receive` | 7002 | `:107` |
| `Shop_List` | 10002 | `:122` |
| `Cafe_Get` | 20000 | `:193` |
| `Scenario_List` | 19000 | `:172` |

（上表 24 行含 `Account_Nickname`——它**不在** v5 的 43 条里，故 v5 实际"名字正确"的是 **23 条**。）

### 5.2 ★ 名字在枚举里**根本不存在**（20 条）

| bridge 里的名字 | 在 `ProtocolData.cs` | 真实协议名 | 危险 |
|---|---|---|---|
| `Account_GetIdCardInformation` | **无** | 无（国服实名认证用名，Steam 侧不存在） | 若国服真发它，`b32md5` 能命中，但转发必 404；**且我们无法用 Shittim 应答** |
| `Queuing_Ping` | **无** | 无协议；只是 HTTP `POST/GET api/Queuing/Ping` | 让它落进"已知"分支，掩盖"这不是协议" |
| `Queuing_GetTicketGL` | **无** | 无协议；是 Shittim 给 GetTicket 响应起的**显示名**（`GatewayController.cs:191-196`） | 同上 |
| `Queuing_GetWaitingQueue` | **无** | 无 | 同上 |
| `System_ServerTime` | **无** | `NetworkTime_Sync`(3)？`System_Version`(1)？ | **两个猜测名**，任一命中都不会有正确响应 |
| `System_GetServerTime` | **无** | 同上 | 同上 |
| `Player_GetSetting` | **无** | 枚举无 `Player_*` | — |
| `Player_SetSetting` | **无** | 同上 | — |
| `Content_GetList` | **无** | 枚举无 `Content_*` | — |
| `Loading_Complete` | **无** | 枚举无 | — |
| `Shop_BuyGoods` | **无** | `Shop_BuyMerchandise` = 10000（`:120`） | 名字错 → 永远命中不了真实协议 |
| `Cafe_GetInfo` | **无** | `Cafe_Get` = 20000（`:193`） | 同上（注意 `CafeGetInfoResponse` **类**存在，但**不是协议**） |
| `Clan_List` | **无** | `Clan_Lobby`=28000 / `Clan_Login`=28001（`:269-270`） | 同上 |
| `Friend_GetList` | **无** | `Friend_List` = 43000（`:451`） | 同上 |
| `Raid_GetInfo` | **无** | `Raid_List`=17000 / `Raid_Detail`=17002（`:148,150`） | 同上 |
| `TimeAttack_GetInfo` | **无** | `TimeAttackDungeon_Lobby`=39000 / `_Login`=39006（`:417,423`） | 同上 |
| `MomoTalk_GetOutline` | **无** | `MomoTalk_OutLine` = 33000（`:356`） | 大小写错 |
| `Sticker_List` | **无** | `Sticker_Login`=47000 / `Sticker_Lobby`=47001（`:485-486`） | 同上 |
| `Event_GetList` | **无** | `EventContent_AdventureList`=30000 等（`:299+`） | 同上 |
| `Campaign_GetList` | **无** | `Campaign_List` = 6000（`:83`） | 同上 |

### 5.3 为什么这 20 条错名**不是"无害的无用条目"**

`NAME_TABLE` 的作用是**把客户端发来的 BASE32 反查成协议名**（`:42-43, 240`）。反查不到 ⇒ 落 **分支 U**（`fallback='forward-unknown-protocol'`）。
但**反查得到**（名字猜对了，只是不在 Shittim 枚举里）⇒ 落 **分支 X**（`fallback='forward-known-other'`）。

⇒ 两种都是转发、都是 404。**错名条目的实际危害是"让人误以为这些协议我们已经接住了"**——`report\42` §5 的判定树里，`fallback` 字段就会被误读成"已知协议"。

**再补一刀（与 43 号联动）**：`report\43` 要在 `:274` 后插 Queuing 分支，插入位置**在分支 X 之前**，所以只要 `name` 能反查出来就一定命中——**前提是 `NAME_TABLE` 里那 4 个 Queuing 名字拼写与客户端完全一致**（这 4 条确实正确，§5.1）。

---

## 6. 从现有日志里直接算出黑名单（给 `srv-ops` 的一条查询）

`_handle` 每次都把 `rec` 落盘（`:180-185, :221`），含 `protocol_name`（`:241`）、`fallback`（`:246/:278`）、`resp_code` / `resp_len`（`:218-219`）、`path`（`:202`）。

⇒ **不需要新实验，历史日志里就能看出哪些协议被转发后 404 了。**

```bash
python3 - <<'PY'
import json, collections
rows=[json.loads(l) for l in open('/www/wwwroot/bapatch/logs/api_all_requests.log') if l.strip()]
c=collections.Counter()
for d in rows:
    c[(d.get('protocol_name'), d.get('fallback'), d.get('resp_code'))]+=1
print('%-34s %-28s %-5s %s' % ('protocol_name','fallback','code','count'))
for (n,f,code),k in sorted(c.items(), key=lambda x:-x[1]):
    print('%-34s %-28s %-5s %d' % (n, f, code, k))
PY
```

**读法**：
- `fallback='forward-known-other'` + `resp_code=404` ⇒ 命中 §5 的黑名单（名字对但路径错）。
- `fallback='forward-unknown-protocol'` + `resp_code=404` ⇒ 客户端发了个我们**连名字都没猜到**的协议（`report\43` §4.4 的实名认证候选就在这里现形）。
- `resp_code=404` 且 `path` 是我们没见过的形态 ⇒ 客户端路径规则与我们推测的不一样。

（本轮**未执行**——不连服务器。这条查询不产生任何新流量，只读历史日志。）

---

## 7. 补路由清单（按"最可能是第二发"排序）

| 优先级 | 协议 | 号 | 现有分支 | 补法 | 备注 |
|---|---|---|---|---|---|
| **P0** | `Queuing_ProcessWaitingQueue` | 50003 | X → 404 | bridge 铸票（`report\43` §5.3） | 空 `EnterTicket` = 卡排队弹窗（`QueuingHandler.cs:106`） |
| **P0** | `Queuing_GetAuthTicket` | 50002 | X → 404 | bridge 铸票 | 国服取票入口 |
| **P0** | `Account_CheckYostar` | 1009 | **X → 404** | **加进分支 C**（`cn_bridge_v5.py:249` 的元组补 `'Account_CheckYostar'`），或直接映射到现有 `ensure_session` | **国服正牌登录协议，当前完全没接** |
| P1 | `Queuing_GetCryptoKeys` | 50001 | X → 404 | 回空壳或走 L1（`report\43` §2.2） | 不回则握手可能中断 |
| P1 | `Account_Nickname` | 1001 | **U**（v5 表里没这名字） | 先补进 `BUILTIN_NAMES`；再接 Shittim | 新号昵称为空时会发（`[推断]`） |
| P1 | `Account_LoginSync` | 1019 | **U**（表里没有） | 补名 + 接 `/api/gateway` | 大厅数据全靠它（`AccountHandler.cs:288+`） |
| P2 | `Account_GetTutorial` / `Account_SetTutorial` | 1005 / 1006 | X → 404 | 补名 + 接 `/api/gateway` | 在免通知集合里（`GatewayController.cs:327-331`），登录期会发 |
| P2 | `NetworkTime_Sync` | 3 | X → 404 | 补名 + 接 `/api/gateway` | 空请求体、纯往返（`NetworkProtocol.cs:5609-5619`），最便宜的验证项 |
| P2 | `Session_Info` / `System_Version` | 2 / 1 | X → 404 | 补名 + 接 `/api/gateway` | — |
| P3 | `Item_List` / `Character_List` / `Echelon_List` / `Campaign_List` / `Mail_List` / `Mission_List` | 4000/2000/5000/6000/7000/8000 | X → 404 | 批量接 `/api/gateway` | 大厅灌入，量大但机械 |
| P3 | `Account_GetIdCardInformation` 等实名认证 | 无 | **U/X** | **Shittim 没有对应协议** | 若出现，只能 bridge 自造响应（或先在客户端侧绕） |

**统一补法的技术形态**（给 `srv-ops` 一句话）：把这些协议从"分支 X"改成"**合成请求 → `post_gateway()` → `unwrap_gateway_response()` → 原样回**"，即把 `cn_bridge_v5.py:276-279` 的 `_forward` 换成：
```python
req = {"Protocol": name, "SessionKey": SESSION.session_key}   # 会话类协议需带 SessionKey
code, raw = post_gateway(req)
gp, obj = unwrap_gateway_response(raw)
return 200, json.dumps({"protocol": name,
                        "packet": json.dumps(obj, ensure_ascii=False, separators=(',', ':'))},
                       ensure_ascii=False).encode(), 'application/json; charset=utf-8'
```
> ⚠ 这只是"骨架"：**每个协议都要有它自己的请求字段**（例如 `Account_Nickname` 必须有 `Nickname`，`Mail_Receive` 必须有 `MailId`）。拿空请求去问 Shittim 通常不会错，但**会改变账号状态或返回默认数据**。所以 P1 起要逐个看 handler。

---

## 8. 未找到 / 推断标注

| 项 | 状态 |
|---|---|
| 线上 `cn_bridge_mode.txt` 当前值 | **未找到**（`/www/wwwroot/bapatch/`，本地无副本）。若为 `forward`，则**整个 bridge 逻辑（含 Account_Auth 接管）都被跳过**，一切转发——这是一个必须首先确认的开关 |
| 线上 `tools/protocol_names.txt` 内容 | **未找到**（`glob` 全工作区无此文件）⇒ §5 只审计了 `BUILTIN_NAMES` 的 43 条 |
| 线上 bridge 版本是否就是本地这份 | **未找到**。若线上更新过（例如 v6 的 `decrypt+encresp1/2/3`），§1 的分支图需重画——**v6（`scripts\account_auth_probe_v6.py`）已多出 `exp` 开关与解密路径，行号完全不同** |
| 客户端 URI 的完整形态规则 | **未验证**（只实测 `/api/account/auth` 一例；`[推断]` 为 `/api/<服务>/<动作>`） |
| `Account_Auth2` 是否该回 `Account_Auth` 信封 | **未验证**（`:262`/`:272` 硬编码） |
| ASP.NET 路由大小写不敏感 | `[推断]`（框架默认行为，本仓库未显式配置） |
| `QueuingHandler` 之外，Queuing 类是否还有第 5 个协议 | **已确证没有**（`ProtocolData.cs:500-503` 只有 4 个；`grep Queuing` 全域仅这几处） |
| `HandlerManager` / `ServerNoticeService` / `HybridCryptor` | **未找到**（不在快照，`report\42` §6 已列）。本报告中凡涉及 `Dispatch`/`IsGated` 的表述均属**基于缺失源码的推断**，已在正文标注 |

---

## 附录：一句话交接

> **bridge 现在只翻译 3 个协议（1009 不在内），其余全打到不存在的路由。**
> 要让国服走通，最小改动是：① 确认 `cn_bridge_mode.txt` 不是 `forward`；② 把 `Account_CheckYostar`(1009) 加进 `:249` 的元组；③ 在 `:274` 后插 Queuing 铸票分支（`report\43` §5.3）；④ 之后按 §7 的 P1/P2 逐个把 `_forward` 换成 `post_gateway`。

**只写入了本文件。** 未修改 `report\` 下任何既有文件，未修改 `scripts\` 下任何脚本，未修改 `report\_tmp\shittim\src\` 下任何源码。
