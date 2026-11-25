# IDENTITY_CHAIN_MAP — 账号身份链路判定图（只读分析，2026-11-18）

> 本文件只读分析产出，**未改动任何既有文件、未重启服务、未连服务器**。
> 全篇结论均带 `文件:行号` 或命令原始输出；无法直接观测的一律标「推测」。
> **不含代码补丁**——按要求只给判定链与账号键选择依据。

---

## 0. 行号基准与版本核对（**先读这节，否则行号会对不上**）

### 0.1 md5 匹配结果（任务要求的两份都**精确命中**，字节数一致）

| 角色 | 路径 | md5 | 字节 | 行数 |
|---|---|---|---|---|
| **桥（线上 v3，本文主基准）** | `work\ba\srv_live\20261118_022226\_patched\account_auth_probe.py` | `7d4d162516c2ac1dd6b140bb6a01779b` | 164,514 | **3,998** |
| 桥（基线） | `work\ba\srv_live\20261118_022226\bapatch\tools\account_auth_probe.py` | `1db27e4c5d9074bf8ad15b216327aef4` | 161,194 | 3,914 |
| **account_service（线上）** | `work\ba\srv_live\20261118_0059\_patched\account_service.py` | `436cba4df30e503212c2e737bf2f9f0c` | 106,139 | **2,259** |
| SDK（**实际线上**） | `work\ba\srv_live\20261118_0059\_patched\_work\sdkcard.py` | `d90546d6f8265e8d56b7d7bff97f5410` | 14,940 | 433 |
| SDK（任务所指"线上快照"） | `work\ba\srv_live\20261118_0059\ba_sdk\sdkcard.py` | `383d09ed2182d9e655653f6c62597f87` | 13,328 | 384 |
| SDK（本地源） | `work\ba\bapatch\sdkcard.py` | `1245d895668ea8198a43657593c5b22e` | 5,814 | 160 |
| Shittim | `work\ba\srv_src\Shittim-Server\Core\NetworkProtocol\Handlers\AccountHandler.cs` | — | 49,850 | 1,062 |

命令与原始输出（节选）：
```
7d4d162516c2ac1dd6b140bb6a01779b | account_auth_probe.py | 164514B | 3772 lines | ...\20261118_022226\_patched\account_auth_probe.py
436cba4df30e503212c2e737bf2f9f0c | account_service.py  | 106139B | 2191 lines | ...\20261118_0059\_patched\account_service.py
1db27e4c5d9074bf8ad15b216327aef4 | account_auth_probe.py | 161194B | 3690 lines | ...\20261118_022226\bapatch\tools\account_auth_probe.py
```
（`Get-Content.Count` 与 `read` 工具的行数不同，因前者按物理行切、后者按换行符切；**本报告统一用 `read` 工具行数**，与任务给的 3,914 / 3,999 同一标准。）

**⇒ 结论：**「有线上那份就用线上那份」——**两份都找到了**，故本文**桥用 `_patched`（7d4d1625）、account_service 用 `_patched`（436cba4d）**，**不需要**「以基线为准」，行号无偏移问题。

### 0.2 三处必须纠正的前提（都会影响读表）

1. **`identify()` 不在 748 行，在 `account_service.py:825`；模块级包装在 `:2084`**（不是 ~2001）。
   偏移 ~+77 / +83，本文全部用实测行号。
2. **任务的"线上快照" `ba_sdk\sdkcard.py`(13,328 B) 不是当前线上 SDK。**
   线上是 `14,940 B / d90546d6`（见上表）。两者 `Compare-Object` 差异**只涉及** body 上限、cards.json 原子写+损坏备份、日志 `_mask()`，
   **`device_of` / `user_payload` / `quick-login` / `detail` 的身份语义逐字相同** ⇒ 身份结论对两版通用。本文 SDK 行号取**线上版（14,940 B）**。
3. **`DEFAULT_FALLBACK_PUBLISHER_ID = 314816420` 与卡 `11111111111` 的 SDK `User.ID` 数值完全相同**（下文 §3/§4 核心）。

---

## 1. 现状链路图

```
【客户端】                【SDK sdkcard.py :8080】        【桥 account_auth_probe.py :9097】      【account_service.py】        【Shittim :5000/5100】
   │                          │                                  │                                      │                          │
   │ Authorization header      │                                  │                                      │                          │
   │ Head.DeviceID=09a4d0ab..  │                                  │                                      │                          │
   ├─────── /user/login ──────►│ device_of()            :76-82    │                                      │                          │
   │        OpenID=卡密明文     │  key=OpenID            :371      │                                      │                          │
   │                          │  cards.json 查表+过期+绑定        │                                      │                          │
   │◄── User.ID / User.Token ──┤ user_payload()        :85-91     │                                      │                          │
   │    User.ID = md5(卡密)    │   :89  ID  = f(卡密)             │                                      │                          │
   │    User.Token=sha256(卡│dev)[:40] :87                        │                                      │                          │
   │                          │                                  │                                      │                          │
   │ （客户端把 User.ID 当作 DevId 发进游戏包 —— 推测，见 §4.7）      │                                      │                          │
   │                          │                                  │                                      │                          │
   ├──── post /api/account/auth (1002) 密文包 ─────────────────►│ decrypt → _FRAG_TLS.v   :2342    │                          │
   │    packet 内含:            │                                  │        + req_frag_head  :2351(已脱敏!)│                    │
   │    DevId(str:10)          │                                  │ _req_dict()              :95-122  │                          │
   │    DeviceUniqueId(str:32) │                                  │ acct_apply_to_auth()     :125-184 │                          │
   │    Token(str:40)          │                                  │   └─ P4 retarget :139-169 ───────►│                          │
   │    SdkPid / Hash / ...    │                                  │ identify(req)             ───────►│ :825-873                 │
   │                          │                                  │                                      │  dev_id 优先级：          │
   │                          │                                  │                                      │  DevId > DeviceUniqueId  │
   │                          │                                  │                                      │  > 兜底 314816420        │
   │                          │                                  │ get_or_create_account()  ───────►│ :876-895 (UNIQUE dev_id) │
   │                          │                                  │ issue_session_key()      ───────►│ :1046                    │
   │                          │                                  │ build_account_db_for()   ───────►│ :1216-1255               │
   │◄──── AccountDB+SessionKey（**来自 account_service，不是 Shittim**）│  ServerId=accounts.server_id :1235                        │
   │                          │                                  │                                      │                          │
   │                          │                                  │ ensure_session()         :1633-1662│                          │
   │                          │                                  │  ENTER_TICKET = b64(UID/TOKEN) :259 │                          │
   │                          │                                  │  UID='314816420' :257              │                          │
   │                          │                                  │─────────────────────────────────────────────────────────────►│ CheckNexon
   │                          │                                  │                                      │    publisherId=parts[0]  │ AccountHandler.cs:62
   │                          │                                  │◄──── SessionKey（**进程级全局缓存**）──────────────────────────┤ :65-66 FirstOrDefault(NpSN)
   │                          │                                  │                                      │    :114 GenerateSession  │
```

**两条互不相同的"同号"通路，必须分开看：**

- **通路 A（决定玩家看到哪个号）**：`SDK User.ID → 客户端 DevId → identify().dev_id → accounts.dev_id → AccountDB.ServerId`。
  证据：`account_service.py:1235` `'ServerId': int(account.server_id)`。
- **通路 B（决定 Shittim 侧落在哪个号）**：`ENTER_TICKET 常量 → Shittim publisherId='314816420' → 单一 UserAccount`。
  证据：`AccountHandler.cs:62/65-66/114`。

> 通路 B **不**决定客户端看到的 `AccountDB.ServerId`（那是 account_service 发的），但它让所有会话共用同一个 Shittim 账号与同一个 session key（`account_auth_probe.py:1640-1642` 全局缓存）。

---

## 2. `identify()` 完整分支表

`account_service.py:825-873`（模块级 `identify(req)` 在 `:2084-2085`，只是一行转发到 `default_service().identify(req)`）。

### 2.1 取值与优先级

| 字段 | 行号 | 候选键名（按 `_pick` 顺序） | `_pick` 语义 |
|---|---|---|---|
| `dev_id_raw` | 834 | `DevId`, `DevID`, `devId`, `dev_id` | `:2039-2054` 顶层精确 → 大小写不敏感 → **嵌套一层** dict 里找 |
| `duid` | 835 | `DeviceUniqueId`, `DeviceUniqueID`, `DUID`, `deviceUniqueId` | 同上 |
| `token` | 836 | `Token`, `SdkToken`, `sdkToken` | 同上 |
| `pub` | 837 | `PublisherAccountId`, `PublisherID`, `publisherAccountId` | 同上 |

### 2.2 分支表（`dev_id` 判定，优先级从上到下）

| # | 行号 | 条件 | 结果 | `dev_id_source` |
|---|---|---|---|---|
| 0 | 832 | `_decode_request(req)`：dict→原样 / str、bytes→`json.loads` / 其它→`TypeError` | `body, protocol, counter` | — |
| 1 | **841-842** | `dev_id_raw is not None` **且** `strip()` 后 **∉** `('', '0', 'null', 'None')` | `dev_id = str(dev_id_raw).strip()` | `'DevId'` |
| 2 | **843-845** | 条件 1 不成立，且 `duid` 为真值 **且** `str(duid).strip()` 非空 | `dev_id = 'duid:' + duid.strip().lower()` | `'DeviceUniqueId'` |
| 3 | **846-855** | 以上都不成立 | `dev_id = str(_fb)`；`publisher_account_id = _fb`；**`_fb` = 314816420** | `'fallback'` |
| 3a | 848-851 | `if _fb <= 0: raise AuthRejected(...)` | **不可达分支** —— `_fallback_publisher_id()` 恒返回 >0（见 §3.2） | — |

> **注意 1**：`DevId` 取到 `'0'` / `'null'` / `'None'` / `''` 都**不算有效**，会落到分支 2（DeviceUniqueId）。这个黑名单在 `:841`。
> **注意 2**：`DeviceUniqueId` **没有**黑名单 —— `duid='0'` 时 `'0'.strip()` 为真 ⇒ `dev_id='duid:0'`，**所有 DeviceUniqueId 为 "0" 的设备会坍缩成同一个键**（`:843-844`）。

### 2.3 `publisher_account_id` 判定（`:860-868`）

| # | 行号 | 条件 | 结果 |
|---|---|---|---|
| 4 | 861-863 | `pub not in (None, '', 0, '0')` | `int(pub)` |
| 4a | 863-865 | 上式 `int()` 抛 `TypeError/ValueError` | `0` |
| 5 | 866-868 | 否则 `dev_id.isdigit()` | `int(dev_id)`（注释自承是**推断关系**，非源码证据） |
| 6 | （隐含） | 否则（即 `dev_id='duid:xxx'`） | **`0`** |

> **注意 3**：走 DeviceUniqueId 分支建的号，`publisher_account_id` 恒为 **0**；`sid_resolve(pub=0, ...)` 会走 shadow 返回 0（`account_service.py:385-399`），即**拿不到 Shittim 真数据**。

### 2.4 `Identity` 字段全集（`:533-547`）

| 字段 | 类型 | 默认 | 来源行 |
|---|---|---|---|
| `dev_id` | `str` | 必填 | 841/844/853 |
| `device_unique_id` | `Optional[str]` | `None` | 857（小写化） |
| `token` | `Optional[str]` | `None` | 858 |
| `publisher_account_id` | `int` | `0` | 860-868 |
| `dev_id_source` | `str` | `'DevId'` | 840/845/854 |
| `protocol` | `Optional[int]` | `None` | 832 `_decode_request`；`Hash>>32` |
| `counter` | `Optional[int]` | `None` | 832；`Hash & 0xFFFFFFFF` |
| `raw` | `Dict` | `{}` | 853/873 = 整个 body |

### 2.5 关键：**`token` 不参与身份判定**

- `token` 只在 `_create_account` 落库：`account_service.py:923` `sdk_token=identity.token`。
- 查账号**只用 `dev_id`**：`:882` `SELECT * FROM accounts WHERE dev_id = ?`。
- `require_token_stable` 默认 **False**（`:634`，env `BA_REQUIRE_TOKEN_STABLE` 默认 `'0'`，`:656`）。
  ⇒ **SDK Token 轮换不会换号，也不会拒登**；它是审计字段，不是键。

---

## 3. 退化到 `314816420` 的**全部**路径

### 3.1 常量定义处

| # | 位置 | 内容 |
|---|---|---|
| P0 | `account_service.py:403` | `DEFAULT_FALLBACK_PUBLISHER_ID = 314816420`（注释 `:401` 自述"单账号部署形态专用"） |
| P0b | `account_auth_probe.py:257-259` | `UID='314816420'`；`TOKEN='61de1d1b...'`；`ENTER_TICKET=b64(UID+'/'+TOKEN)` |
| P0c | `cn_inner27.py:78, 89` | 硬编码模板 `"DevId":"314816420"` / `"PublisherAccountId":314816420`（`cn_inner.py:45` 默认参数同值） |
| P0d | `account_auth_probe.py:85-92` | `_fallback_dev_id()` → `'314816420'`；`FALLBACK_DEV_ID = _fallback_dev_id()` |

### 3.2 `_fallback_publisher_id()`（`account_service.py:439-456`）

| 顺序 | 行号 | 条件 | 返回 |
|---|---|---|---|
| 1 | 440-443 | env `BA_FALLBACK_PUBLISHER_ID` 为纯数字且 >0 | 该值 |
| 2 | 444-452 | `Config.json` 里 `FallbackPublisherId` / `FallbackPublisherID` / `fallbackPublisherId`（`_find_key_named` 递归 4 层，`:425-436`） | 该值 |
| 3 | **455-456** | 以上都没有（**当前默认情形**） | **`DEFAULT_FALLBACK_PUBLISHER_ID` = 314816420** |

命令侧：`_SRV_CONFIG_JSON` 默认 `/www/wwwroot/ba_srv/Config/Config.json`（`:141`）。
⇒ **只要配置里没写 `FallbackPublisherId`，就恒为 314816420，且恒 >0**，因此 `:848` 的 `AuthRejected` 守卫**永远不会触发**——“没有稳定身份就拒绝建号”的设计被兜底常量抵消了。

### 3.3 `identify()` 内兜底

| # | 行号 | 触发条件 | 结果 |
|---|---|---|---|
| P1 | `account_service.py:846-855` | `DevId` 缺失/为空/`'0'`/`'null'`/`'None'` **且** `DeviceUniqueId` 缺失/空 | `Identity(dev_id='314816420', publisher_account_id=314816420, dev_id_source='fallback')` |

### 3.4 调用方传空 dict / 解析失败

| # | 行号 | 触发条件 | 结果 |
|---|---|---|---|
| P2 | `account_auth_probe.py:108-111` | `_FRAG_TLS` 无值 **且** `rec['req_frag_head']` 空 | `_req_dict` → `{}` |
| P3 | `:117-120` | 拼出来的 body `json.loads` 失败 | `_req_dict` → `{}`（**静默**，不打日志、不抛） |
| P4 | `:122` | `json.loads` 成功但不是 dict | `_req_dict` → `{}` |
| P5 | `:134-137` | `if not req:` → 用 `rec['req_DevId']/req['req_DeviceUniqueId']/rec['req_Token']` 组装 `req` | 见 P6 —— 这三个字段在解析失败时**必然为空** |
| P6 | `:121` + `:639-653` | `rec['req_DevId']` / `rec['req_DeviceUniqueId']` **唯一写入点**是 `devid_stash()`，而 `devid_stash` **只在 `_req_dict` JSON 解析成功后**被调用（`:121`） | ⇒ P5 组出的字典恒为 `{'DevId':'','DeviceUniqueId':'','Token':''}` ⇒ 进 P1 |
| P7 | `:109` | `rec['req_frag_head']` 是 `mask_secret(...)` 产物（`:2351`） | 形如 `{"De****...}(len=600,sha8=xxxx)`，**不是合法 JSON** ⇒ 必在 P3 失败 |

> **P7 要点**：`mask_secret`（`:214-222`）为脱敏把 600 字符的 fragment 截成 `s[:4] + '****' + s[-4:] + '(len=..,sha8=..)'`。
> 也就是说 **`req_frag_head` 从设计上就不可能被 `json.loads` 还原**。它能"工作"只是靠线上新增的 `_FRAG_TLS` 旁路（`:82, 99-105, 2342-2343`）携带**未脱敏**的原文。
> `_FRAG_TLS` 生效条件很窄：**同一线程 + `seq == id(rec)` + 本次请求确实走过 decrypt 分支**（`:2335-2346`）。任一条不满足 ⇒ 回落到 P7 ⇒ P3 ⇒ `{}` ⇒ P1。

### 3.5 P4 retarget（线上新增，基线没有）

| # | 行号 | 触发条件 | 结果 |
|---|---|---|---|
| P8 | `account_auth_probe.py:141-162` | `identify()` 给出了**非空** `dev_id`，但 `svc.get_account_by_dev_id(dev)` **不是 True**（无行，或查询抛异常 ⇒ `_exists=None`），**且** `FALLBACK_DEV_ID` 的行存在/未知 | `ident.dev_id = FALLBACK_DEV_ID`（`:159`）⇒ **314816420** |
| P8a | `:156-157` | 例外：`_exists is False` **且** `_fb_exists is False`（两边都确认无行） | 保留原 `dev_id`，`acct_id_src='create'` —— 这是**唯一**能让新卡建新号的口子 |
| P8b | `:163-169` | 上面整段抛异常 | `ident.dev_id = str(FALLBACK_DEV_ID)`（`:166`） |

> 基线版 **没有** P8/P8a/P8b：基线 `:108-114` 是 `req=_req_dict(rec)` → `ident=svc.identify(req)` → 直接 `get_or_create_account`。
> **⇒ "线上多 84 行"里最要命的就是这段 retarget**：它把「未知 dev_id 建新号」改成「未知 dev_id 一律并入兜底号」。

### 3.6 异常兜底（不走常量，但同样落到"同一个号"）

| # | 行号 | 触发条件 | 结果 |
|---|---|---|---|
| P9 | `:180-183` | `acct_apply_to_auth` 整个 try 抛异常 | `rec['acct_svc']='fallback:...'`，`inner` **原样返回** |
| P10 | `cn_inner27.py:74-97` | 承接 P9 / 或 `_cn_enc_b64` 未被走到 | 客户端收到硬编码 AccountDB：`DevId="314816420"`、`PublisherAccountId=314816420`、`SessionKey.AccountServerId=ACCOUNT_SERVER_ID` |

### 3.7 Shittim 侧常量（通路 B）

| # | 行号 | 说明 |
|---|---|---|
| P11 | `account_auth_probe.py:1643-1644` | `ensure_session` 发 `Account_CheckNexon`，`EnterTicket=ENTER_TICKET`（常量） |
| P12 | `AccountHandler.cs:58-63` | `publisherId = long.Parse(parts[0])` ⇒ **`parts[0]='314816420'`**；`token=parts[1]` |
| P13 | `AccountHandler.cs:65-66` | `FirstOrDefault(u => u.NpSN == publisherId)` ⇒ **只按 publisherId 找人** |
| P14 | `AccountHandler.cs:68-89` | 查不到就 `new UserAccount{NpSN=publisherId,...}` + `new AccountDBServer(publisherId)` |
| P15 | `AccountHandler.cs:90-102` | token 不一致**默认不拒**：仅当 `EnforceTicketToken && NpToken非空` 才抛（`:97-98`），否则 `:100` **直接覆盖写** |
| P16 | `account_auth_probe.py:1640-1642` | `SESSION.session_key` 是**进程级全局缓存**，所有客户端复用同一个 Shittim session |
| P17 | `account_auth_probe.py:260-261` | `CLIENT_KEY/CLIENT_IV` = `bytes(range(32/16))` **常量** ⇒ 每会话加密材料固定 |

> **Q4 直接回答**：`ENTER_TICKET` 的消费点**全文件只有 `:1643` 一处**（另 `:259` 定义）。
> 它确实决定了 Shittim 侧 `publisherId`（`AccountHandler.cs:62` → `:65-66` → `:114`），且 token **从不校验**（`:90-102`）。
> 但**它不决定客户端看到的 `publisherId`**：客户端收到的 `AccountDB` 由 `account_service.build_account_db_for` 生成（`:1216-1255`），`DevId`/`PublisherAccountId` 取 `accounts` 行（`:1238, :1249`）。
> **⇒ "所有卡都变成同一个 publisherId" 是的，但这条线只锁死 Shittim 侧；玩家看到的号是被通路 A（DevId）锁死的。**

---

## 4. 无法唯一标识一张卡密的环节（按可疑度排序）

### #1 【已读代码证实】SDK `/user/quick-login` 按遍历顺序返回"第一张命中卡"，多卡同设备时恒定同一张

- 线上：`_patched\_work\sdkcard.py:391-401`（`for key, rec in d['cards'].items():` `:393`，命中即 `return` `:400`）
- 快照：`ba_sdk\sdkcard.py:342-353`
- 本地源：`bapatch\sdkcard.py:118-129`
- `/user/detail` 同构：线上 `:404-412`、快照 `:355-363`、本地 `:131-139`

```python
391:         if path == '/user/quick-login':
392:             d = load_cards()
393:             for key, rec in d['cards'].items():
394:                 if dev and dev in rec.get('devices', []):
395:                     if rec.get('expire', 0) and rec['expire'] < time.time():
396:                         break
397:                     w('QUICK OK %s _mask(dev)=%s' % (_mask(key), _mask(dev)))
398:                     self._send({'Code': 200, 'Msg': 'OK',
399:                                 'Data': user_payload(key, dev)})
400:                     return
```
多张卡的 `devices` 都含本机时，`dict` 插入序在前的那张**永远**胜出。`user_payload(key, dev)` 于是恒定返回同一张卡的 `User.ID`。
`/user/login`（显式输卡密）反而是**正确**的：用 `OpenID` 精确查表（线上 `:371`，块范围 `:366-389`；本地 `:98`）。

### #2 【已读代码证实】兜底常量 `314816420` 与卡 `11111111111` 的 `User.ID` **数值完全相同** ⇒ 兜底与"卡A"在账号键上不可区分

- 公式：`sdkcard.py:89` `tpl['User']['ID'] = int(md5(card)[:8],16) % 900000000 + 100000000`
- 本地复算（只读，无网络）：
```
card='11111111111' md5[:8]=adbc91a4 -> User.ID=314816420
card='12222222222' md5[:8]=629720dc -> User.ID=854071516
card='314816420'  md5[:8]=f70b4b68 -> User.ID=644712552
card='1013178778' md5[:8]=c519b9ac -> User.ID=706797484
```
- 常量：`account_service.py:403`、`account_auth_probe.py:257`、`cn_inner27.py:78,89`

**⇒ 后果（这是本次 bug 最恶心的部分）：** 只要链路任何一环退化（§3 的 P1–P10 任一条），结果 `dev_id=314816420` 与"卡A正常登录"的结果 `dev_id=314816420` **完全一样**。
运维侧无法从账号号段区分"这是卡A"还是"这是兜底"。**卡B 永远不可能拿到 314816420（它算出来是 854071516）**，所以现象必然是"不管用哪张卡，进的都是同一个号"——那个号就是卡A/兜底号。

### #3 【已读代码证实】`req_frag_head` 是脱敏字符串，`_req_dict` 结构上无法解析它

- `:2351` `rec['req_frag_head'] = mask_secret(str(r.get('fragment'))[:600])`
- `:214-222` `mask_secret` 返回 `s[:4]+'****'+s[-4:]+'(len=%d,sha8=%s)'`
- `:109` `_req_dict` 取它当 JSON 源；`:112-120` 只补 `{`/`}` 再 `json.loads` ⇒ 必失败 ⇒ `{}`

**唯一补偿**是 `_FRAG_TLS`（`:82, :2342-2343` 写；`:99-105` 读）。它靠 `seq == id(rec)` 认领，**跨线程/跨请求即失效**；而 `acct_apply_to_auth` 在 `:2044`（`_cn_enc_b64` 内）被调，与 decrypt 分支（`:2329-2360`）**不在同一处**，只要实际走的响应模式不含 `acct_apply_to_auth`，或线程被复用，就退回掩码串。

### #4 【已读代码证实】P4 retarget：未知 `dev_id` 一律并入兜底号

- `:139-169`，核心 `:156-162`
```python
156:                if _exists is False and _fb_exists is False:
157:                    rec['acct_id_src'] = 'create'       # 两者都确认不存在 ⇒ 真全新安装
158:                else:
159:                    ident.dev_id = _fb                  # 未知/或兜底存在 ⇒ 一律退兜底号
160:                    ident.dev_id_source = (... or 'DevId') + '+retarget'
161:                    rec['acct_id_retarget'] = True
```
只要 `get_account_by_dev_id(_dev)` 返回 `None`（新卡=新 DevId 必然如此）**且**兜底行存在（现网存在），就 retarget。
**⇒ 即便通路 A 的 DevId 完全正确，新卡也会被强行并到 314816420。** 这是 Baseline→线上 引入的回归。

### #5 【已读代码证实】`devid_stash` 的"补救字典"是自毁式兜底

- 唯一写点 `:639-653`；唯一调用点 `:121`（在 `_req_dict` **解析成功之后**）
- `:134-137` 用 `rec['req_DevId']` 补救 —— 但解析失败时这些键**从未被写过**
⇒ P5 的补救分支 100% 产出全空字典，等于把 P2/P3 直接转成 P1。

### #6 【已读代码证实】桥侧完全不认识卡密

全文件 grep `cards\.json|OpenID|openid|sdk_token|SdkToken` ⇒ **仅 1 处命中**，且是日志脱敏名单 `:210`。
⇒ 卡密 → 身份的唯一通道是**客户端手里的 DevId**。桥没有任何办法自行把卡密映射成账号。

### #7 【推测】客户端把 SDK `User.ID` 当作 Account_Auth 的 `DevId`

- 抓包结构证据（`work\ba\proto\_scan_inventory.json`，proto 1002 `/api/account/auth`）：
```
"req_keys": ["Protocol","DevId","OSVersion","DeviceUniqueId","DeviceModel",
             "DeviceSystemMemorySize","Token","SdkPid","SubChannel","ResUrl","Hash"]
"req_shape": {"Protocol":"int","DevId":"str:10","OSVersion":"str:65",
              "DeviceUniqueId":"str:32","DeviceModel":"str:14",
              "DeviceSystemMemorySize":"int","Token":"str:40",
              "SdkPid":"str:5","SubChannel":"str:0","ResUrl":"str:41","Hash":"int"}
```
- 实抓样本（`work\ba\...\_cmp_out.txt:27`）：`AUTH REQ raw: {"Protocol":1002,"DevId":"1013178778",...}`
  —— `1013178778` **正是** `sdk_resp\user_quick-login.json` 模板里的 `User.ID`（模板 1 行，`"User":{"ID":1013178778,...}`）。
- `Token` 长度 `str:40` **正好**等于 `sdkcard.py:87` 的 `sha256(...)[:40]` ⇒ 客户端把 SDK Token 原样转发成 `Token`。
- 现网 5 次 auth 的 `DevId` 恒为 `314816420`（=卡A 的 `User.ID`），见同目录 `SRV_CARD_IDENTITY_EVIDENCE.md` §4。

⇒ **推断链完整但客户端代码不在本仓库**：`User.ID`(10 位数字) 与 `DevId`(str:10) 长度、取值、模板值三重吻合，且"恒等于卡A User.ID"无法用其他机制解释。**标推测。**

### #8 【已读代码证实】Shittim 层 `ENTER_TICKET` 硬编码 + 全局 session 缓存

`:257-259` + `:1643` + `AccountHandler.cs:62/65-66/114`；`:1640-1642` 全局复用。
影响：所有客户端共用**同一个** Shittim 账号与 session key ⇒ Shittim 侧状态（1017/1019、blob）串号。
**不**改变客户端 `AccountDB.ServerId`（来自 `account_service.py:1235`），但会污染 `sid_resolve`/`merge_real_account_db` 取到的"真数据"。

### #9 【已读代码证实】`DeviceUniqueId` 无黑名单，`'0'` 会坍缩

`:843-844` 只判 `str(duid).strip()` 真值 ⇒ `duid='0'` → `dev_id='duid:0'`。批量刷机/模拟器常见 `DeviceUniqueId=0` ⇒ 全部同号。

---

## 5. 候选账号键对比表 + 推荐

### 5.1 对比

| 候选键 | 从哪一层拿得到 | 代码位置 | 重装/刷机漂移 | 换卡漂移 | 多设备 | 是否需改客户端 | 现网是否已在用 |
|---|---|---|---|---|---|---|---|
| **A. SDK `User.ID` → 客户端 `DevId`** | SDK 算出 → 客户端放进 1002 包 | `sdkcard.py:89`（算）；`identify():834,841`（取）；抓包 `_scan_inventory.json` `DevId` | **不漂移**（纯 `f(卡密)`，与设备无关） | **换卡即变**（正是要的语义） | 同卡多设备**同号**（正确） | **否** | **是**（`acct_id_src=exact`，dev_id=314816420） |
| **B. `DeviceUniqueId`** | 1002 包内 `str:32` | `identify():835,843` | **会漂移**（重装/恢复出厂/换机） | 不随卡变 ⇒ **换卡不换号（反目标）** | 每设备一个号 ⇒ **同卡多设备变多号** | 否 | 是（仅当 DevId 缺失时兜底，`dev_id_source='DeviceUniqueId'`） |
| **C. SDK `User.Token`** | 1002 包内 `str:40` | `identify():836,858`；`sdkcard.py:87` | **会漂移**（`sha256(卡密|设备)`，换设备即变） | 随卡变 | 每设备不同 | 否 | **否，只落 `accounts.sdk_token`（`:923`），不参与查找（`:882`）** |
| **D. 卡密明文** | **只有 SDK 侧**（`cards.json` / `OpenID`） | `sdkcard.py` 线上 `:371`、本地 `:98`；桥 **grep 0 命中** | 不漂移 | 换卡即变 | 一致 | **是**（桥必须新增"卡密→账号"表，或客户端把卡密带进 1002） | 否 |
| E. `Head.DeviceID`（HTTP header） | **只有 SDK 侧** | `sdkcard.py:76-82`；`sdk.log` 每行 `dev=09a4d0ab0ee93616` | 会漂移 | **不随卡变** | 每设备一个 | **是**（桥读不到，须改转发层） | 否（桥全文件无 `Authorization`/`DeviceID` 命中） |

补证：`sdk.log` 原文（每条请求都带设备号，说明 header 通道稳定存在但桥用不上）：
```
65: 10:41:17 /user/login dev=09a4d0ab0ee93616
66: BODY {"OpenID":"11111111111","Secret":"","Token":"123456","Type":"mobile","UserName":""}
67: LOGIN OK 11111111111 dev=09a4d0ab0ee93616
5:  QUICK OK 11111111111 dev=09a4d0ab0ee93616
```

### 5.2 可靠性排序与推荐

**排序：A ≫ B > C ≫ E > D**（D 最不可行，因为桥拿不到；E 次差，因为桥读不到且换卡不换号）

**推荐：以 A（SDK `User.ID`，即客户端 1002 包里的 `DevId`）为唯一一级账号键。**

理由（每条都可回指行号）：

1. **它已经是现成的"一卡一号"函数**：`sdkcard.py:89` 是纯 `f(卡密)`，与设备无关；`md5(card)` 天然分散（实测卡A=314816420、卡B=854071516）。
2. **它已经端到端打通**：`identify():841-842` 把它当第一优先级；`get_or_create_account():882` 按它精确查；`build_account_db_for():1238` 把它原样回给客户端。
3. **它不需要改客户端**：抓包证明客户端**已经在发** `DevId`（`_scan_inventory.json` `req_shape.DevId = str:10`），且语义就是 SDK 的 `User.ID`（`DevId:"1013178778"` == 模板 `User.ID`）。
4. **重装/刷机不漂移**：`User.ID` 不含设备因子（对比 C 含 `|device`，`sdkcard.py:87`）。这直接解决"换机/重装后变新号"的老毛病。
5. **换卡必然换号**：不同卡密 → 不同 `md5` → 不同 `User.ID`，语义正好符合"一卡一密一号"。

**用它必须同时成立的两条前提（都属于"判定"而非补丁）：**

- **前提 1：SDK 必须按"请求里的卡密"发身份，不能按"遍历顺序第一张命中卡"发。**
  这是 §4 #1 那个 `/user/quick-login` 遍历（`:391-401`）。只要这条不改，A 键再正确，客户端拿到的永远是同一张卡的 `User.ID`。
- **前提 2：兜底常量必须与任何真实卡的 `User.ID` 不相等，且 retarget 不可把未知 DevId 并进真实账号。**
  现状 `314816420` 恰好等于卡A（§4 #2），P8 retarget（`:156-162`）又把新 DevId 并进来 ⇒ 即使前提 1 修好，新卡首次登录仍会被 P8 吞掉。
  **判定**：`314816420` 必须从"账号键值域"里退出——要么兜底改成一个不可能与 `md5%9e8+1e8` 相撞的值并只用于"服务不可用"语义，要么彻底取消兜底身份（让 `:848` 的 `AuthRejected` 真正可达）。

**二级键的定位（不要拿来当主键）：** `DeviceUniqueId` 只适合做"同一账号的设备指纹/风控"，不适合做账号键——它换卡不换号（反目标）且重装漂移。

**明确不建议：** 用 `Token` 建键（`sha256(card|device)`，换设备即换号，`sdkcard.py:87`）；用 `Head.DeviceID` 建键（桥读不到，须改转发契约）。

---

## 6. 不该动的东西（必须原样保留）

### 6.1 SDK 层（sdkcard.py）

| 机制 | 行号（线上 14,940B 版） | 为什么不能动 |
|---|---|---|
| `user_payload` 的 `User.ID` 公式 | `:89` | **这就是"一卡一号"的现成机器**（§5 推荐键的生产者）。改了它等于换账号键 |
| `User.Token` 公式 | `:87` | 客户端 `Token` 字段形状（`str:40`）已与之对齐，改了契约破裂 |
| `device_of()` 读 `Authorization→Head.DeviceID` | `:76-82` | 唯一可靠设备号来源；`sdk.log` 证明它每请求都在 |
| `/user/login` 的卡密校验/过期/绑定 | `:366-389`（本地 `:93-116`） | 这是**唯一正确**的卡密→身份入口，是修 §4#1 的落脚点，不是被改的对象 |
| `cards.json` 结构 `{cards:{卡密:{devices,expire,bind_one}}}` | `load_cards :30-52` / `save_cards :54-68` | 已与卡密后台（`cardadmin*`）对齐，改结构会连带崩后台 |
| `_mask()` 日志脱敏 | `:71-74` 定义、`:387` 使用 | 防止卡密/设备号进日志 |

### 6.2 桥层（account_auth_probe.py）

| 机制 | 行号 | 为什么不能动 |
|---|---|---|
| `_FRAG_TLS` 原始 fragment 旁路 | `:82, :2342-2343, :99-105` | **这是 DevId 真正能到达 `identify()` 的唯一通路**（`req_frag_head` 是脱敏串，见 §3.4/P7）。动它 = 身份全部退化 |
| `mask_secret` 脱敏 | `:214-222` | 不要为了"让 `req_frag_head` 可解析"去撤脱敏——那会把明文 devid 写进 `api_all_requests.log` |
| `_req_dict` 的"缺失即 `{}`"语义 | `:95-122` | 它的 `{}` 是**上游信号**（配合 `acct_id_src`/`req_devid_src` 诊断字段定位问题），不要改成"猜一个默认值" |
| 诊断字段 `req_devid_src` / `acct_id_src` / `acct_id_retarget` | `:107, :150, :157, :161-162` | 这是本次定位问题**唯一可用**的观测面，必须保留 |
| `acct_writeback` 失败不影响响应 | `:187-201` | 昵称/呼号写库失败不能拖垮登录 |
| `acct_svc_on()` 开关 | `:51-56` | 线上排障用的急停，保留 |

### 6.3 account_service 层

| 机制 | 行号 | 为什么不能动 |
|---|---|---|
| `Identity` 数据类字段语义 | `:533-547` | 桥、CLI、自检全部依赖这套字段名 |
| `identify()` 的 `DevId > DeviceUniqueId` 优先级 | `:841-845` | 与客户端实际发包顺序（`DevId` 在前）一致；反转会把主键让给会漂移的 DUID |
| `accounts` 表 `UNIQUE(dev_id)` + 精确查/建 | `:876-895, :882` | 并发首登靠唯一键兜底（`:886-891`），换成模糊匹配会炸并发 |
| `SessionKey{AccountServerId, MxToken}` 结构与 `MxToken` 正则 | `:592-607, :1046` | 客户端 DTO 契约（对齐 `MX.GameLogic.SessionKey`） |
| `build_account_db_for` 的 22 字段 + `ServerId = account.server_id` | `:1216-1255, :1235` | **玩家看到的号就是这里发的**，字段顺序/时间格式（`to_iso` `:485-501`）都不能动 |
| `sid_resolve` 的 shadow 语义（拿不到 Shittim 号就返回 0 并告警） | `:385-399` | 保证"没有 Shittim 行"时不伪造号 |
| `require_token_stable` 默认关 | `:634, :656` | Token 轮换是**正常**行为（`sha256(卡|设备)`），开启会大量误拒 |
| `_decode_request` 的 `Hash=(协议<<32)|计数器` | `:2012-2036` | 已实测；protocol/counter 诊断依赖它 |

### 6.4 Shittim 层

| 机制 | 行号 | 为什么不能动 |
|---|---|---|
| `CheckNexon` 的 `parts[0]` → publisherId → `GenerateSession` 主流程 | `AccountHandler.cs:58-63, 65-66, 114-122` | 已在跑通的会话签发链；**要改的是喂给它的 ticket，不是解析逻辑** |
| `BAPATCH-TOKENGATE`（token 不一致拒绝，可配） | `AccountHandler.cs:90-102` | 防"拿 publisherId 抢号"的安全闸，别为了图省事关掉 |
| `BAPATCH-BAN`（`AccountState.Dormant` 拒绝） | `AccountHandler.cs:104-112` | 封禁唯一生效点 |
| `GatewaySessionCryptoBuilder` 用客户端 Key/IV | `AccountHandler.cs:115, 119-122` | 国服加密握手契约 |
| `AccountInitializationService.InitializeCompleteAccount` | `AccountHandler.cs:87` | 新号初始化 21 个 blob 的唯一入口 |

### 6.5 一句话总结"别动什么"

> **已经跑通的链路不要改结构，只改"喂给它的那张卡"。**
> `DevId → accounts.dev_id → AccountDB.ServerId` 这条主干是**健康**的（现网 `acct_id_src=exact` 就是证据）；
> 真正要动的是**上游两个点**：SDK 按卡发 `User.ID`（`:391-401`），以及兜底常量/retarget 不得与真实卡号段重叠（`:403`、`:156-162`）。

---

## 附：本文所有结论的证据强度自评

| 结论 | 强度 | 依据 |
|---|---|---|
| md5 两份文件精确命中 | 已证实 | `Get-FileHash` 原始输出 |
| `User.ID=314816420` = 卡 `11111111111` | **已证实** | 本地复算 md5 公式（§4#2 输出） |
| `identify()` 分支与优先级 | 已证实 | 直接读 `:825-873` |
| `req_frag_head` 不可解析 | 已证实 | `:2351` + `:214-222` + `:112-120` 三段闭合 |
| `devid_stash` 只在解析成功后写 | 已证实 | grep 唯一调用点 `:121` |
| P8 retarget 是线上新增回归 | 已证实 | 基线 `:108-114` vs 线上 `:139-169` 逐行比对 |
| `quick-login` 恒返回首张命中卡 | 已证实 | 读 `:391-401` + `sdk.log` 20+ 次同一卡号 |
| `ENTER_TICKET` 决定 Shittim publisherId | 已证实 | `:1643` + `AccountHandler.cs:62/65-66/114` |
| 客户端把 `User.ID` 当 `DevId` | **推测** | 抓包 shape `str:10` + 实抓 `1013178778`(==模板 User.ID) + 现网恒为卡A值；**客户端代码不在仓库** |
| 现网 5 次 auth 的 DevId 恒定 | **非本文观测** | 引自同目录 `SRV_CARD_IDENTITY_EVIDENCE.md` §4（他人只读取证，本文未复验服务器） |

**拿不到的**：客户端实现（`DevId` 赋值点）、`/www/wwwroot/bapatch/logs/api_all_requests.log` 原文、线上 `cards.json` 当前内容、`accounts.db` 当前行——均在服务器上，本次受"绝对只读 + 不连服务器"约束未取。
