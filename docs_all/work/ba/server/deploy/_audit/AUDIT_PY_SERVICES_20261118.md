# Python 服务只读安全审计（桥 / 账号服务 / 卡密 SDK）— 2026-11-18 00:47

**范围**（服务器上只 `cat/grep/sed`，未改任何文件）
```
/www/wwwroot/bapatch/tools/account_auth_probe.py   ← 桥 9097（3,818 行）
/www/wwwroot/bapatch/tools/account_service.py      ← 账号服务（被桥 import）
/www/wwwroot/ba_sdk/sdkcard.py                     ← 卡密 SDK 8080（13,328 B）
/www/wwwroot/bapatch/tools/schema_sqlite.sql       ← 账号库 schema
另在跑的 python：account_auth_probe.py(9097) / sdkcard.py(8080) / gwstate_probe.py(旧，44279)
```

---

## A. 身份与鉴权

### A1 卡密校验：**无恒定时间比较、无失败计数、无速率限制** — 高危 · 已证实
```python
sdkcard.py:322   key = str(j.get('OpenID') or '').strip()
sdkcard.py:324   rec = d['cards'].get(key)          ← dict 查找（非 constant-time，可时序侧信道）
sdkcard.py:326   if not rec: → 400101 卡密不正确
sdkcard.py:328   if rec.get('expire',0) and rec['expire'] < time.time(): → 卡密已过期
sdkcard.py:332   if dev and dev not in rec.setdefault('devices', []):
sdkcard.py:333       if rec.get('bind_one') and rec['devices']: → 已绑定其他设备
sdkcard.py:336           rec['devices'].append(dev); save_cards(d)
```
**缺失**：无 `hmac.compare_digest`；无登录失败计数/封禁（`login_attempts` 表在 MySQL 卡密站里有，**sdkcard 完全没查**）；无速率限制 ⇒ **可无限次爆破卡密**（12 位手机号形态 + 无锁 ⇒ 可枚举）。

### A2 设备绑定可被客户端任意指定 — 高危 · 已证实
```python
sdkcard.py:33    def device_of(handler):
sdkcard.py:34        raw = handler.headers.get('Authorization') or ''
sdkcard.py:36        head = json.loads(raw).get('Head', {})
sdkcard.py:37        return head.get('DeviceID', '') or ''
```
**⇒ `DeviceID` 完全来自请求头，客户端可任意填**。`bind_one` 的"一卡一机"因此**只是礼仪**：改个 header 就能换机登录；
`quick-login`（:342-353）也只按 `dev in rec['devices']` 判定 ⇒ **知道/猜中某卡已绑的 DeviceID 即可免卡密登录**。

### A3 SDK token **从不被任何地方校验** — 高危（架构性）· 已证实
```python
sdkcard.py:44   tok = hashlib.sha256((card + '|' + device).encode()).hexdigest()[:40]
sdkcard.py:45   tpl['User']['Token'] = tok
sdkcard.py:46   tpl['User']['ID'] = int(md5(card)[:8],16) % 900000000 + 100000000
```
全仓 grep：**没有任何服务端代码读取/校验 `User.Token`**（`sdkcard` 自己也不校验；桥只把它当 `req_Token` 透传）。
**⇒ 该 token 是"装饰品"**：游戏侧身份完全由桥的 `DevId` 决定，**持有 token 不等于持有身份，反之亦然**。

### A4 桥的 `identify()`：`DevId` 可由客户端任意指定 ⇒ 可冒充他人 — 高危 · 已证实
```python
account_service.py:511   dev_id_raw = _pick(body, ('DevId','DevID','devId','dev_id'))
account_service.py:522   if dev_id_raw ... : dev_id = str(dev_id_raw).strip()
account_service.py:524   elif duid: dev_id = 'duid:%s' % str(duid).strip().lower()
account_service.py:527   else: raise AuthRejected(...)
```
**⇒ 只要在 `Account_Auth` 请求体里写 `DevId=314816420`（或任何已知 DevId），桥就会把请求映射到该账号并**签发合法 session**。**
无签名、无 nonce、无时间窗、无 IP 绑定校验（`issue_session_key(client_ip=...)` 只是**记录**，`resolve_session` 不比对 IP）。

### A5 会话校验本身是**做了的**（这一项做对了）— 已做对 · 已证实
```python
account_service.py:  resolve_session(mx_token):
    SELECT ... FROM sessions s JOIN accounts a ON a.server_id=s.server_id WHERE s.mx_token = ?
    if revoked != 0: return None ; if expires <= now: return None
account_service.py:  issue_session_key(): uuid4().lower() ，写 sessions 表，超 max_active_sessions 旧会话置 revoked=1
```
**⇒ MxToken 是 uuid4（不可猜）、有 TTL、有 revoked、支持多会话上限。** 但**它只保护"桥→Shittim"这一段**，不保护"客户端→桥"（见 A4）。

---

## B. 输入校验

| # | 项 | 结论 | 严重度 | 证据 |
|---|---|---|---|---|
| B5 | `json.loads` 异常处理 | **有**（try/except 后置空 dict） | 已做对 | `sdkcard.py:318-321`、`sdkcard.py:35-39` |
| B5b | 请求体大小上限 | **无**（`sdkcard`） | **中危** | `sdkcard.py:281-282` `n=int(content-length or 0); self.rfile.read(n)` —— 无上限，可传 GB 级 body 打爆内存 |
| B6 | SQL 参数化 | **全部参数化**（`?` 占位） | 已做对 | `account_service.py:369-475` 全部 `_execute(sql,args)`；`694` 的 `%s` 只拼**列名白名单**（来自代码常量，非外部输入） |
| B7 | 文件路径拼接 | **无外部输入进路径** | 已做对 | `sdkcard.py:12-15` 路径全为常量；`account_service` 模板路径来自 config |
| B8 | 请求体上限（桥） | **无显式上限**，但有 `Content-Length` 直读 | 中危（推断） | `account_auth_probe.py:1626` |

---

## C. 敏感信息泄露

### C1 **卡密明文落日志** — 高危 · 已证实
```python
sdkcard.py:289   w('%s %s dev=%s\nBODY %s' % (time, self.path, dev, body[:500].decode('latin1')))
sdkcard.py:326   w('LOGIN REJECT unknown card %s' % key)
sdkcard.py:338   w('LOGIN OK %s dev=%s' % (key, dev))
```
**⇒ `sdk.log` 里存着 `OpenID`（= 卡密）明文、`DeviceID`、以及**每次请求的 body 前 500 字节**。**
实测：`sdk.log` 已有 `{"OpenID":"11111111111",...}` 与 `LOGIN OK 11111111111 dev=ce8ffeb7d08cfb36`。

### C2 硬编码密钥字段（**只列名，不贴值**）— 中危 · 已证实
```
sdkcard.py  → resp/common_config.json（CFG）内含 SLS AccessKeyID / AccessKeySecret（官方配置拷贝，非我们签发）
sdkcard.py:106-143 → pay.json（支付开关，非密钥）
account_auth_probe.py:149-162 → 14 个"开关文件"路径（cn_*.txt），非密钥但可改变行为
```
`/www/wwwroot/ba_srv/Config/Config.json` 里另有 `AdminApiKey`（64 hex）与 `ExcelDbSqlCipherKey`（64）—— 属 .NET 侧，本报告不含。

---

## D. 并发与状态

### D1 `cards.json` **无锁读写** — 高危 · 已证实
```python
sdkcard.py:23    def load_cards():  return json.load(open(CARDS))
sdkcard.py:29    def save_cards(d): json.dump(d, open(CARDS,'w'), ...)
sdkcard.py:336       rec['devices'].append(dev); save_cards(d)   ← 读-改-写，无 flock、无原子替换
```
**⇒ `ThreadingHTTPServer`（:384）多线程并发下，两次同时登录会**互相覆盖 devices**；更严重的是 `json.dump` 直接写目标文件，**进程被杀/磁盘满时会把 cards.json 写成半截 → 全部卡密失效**。
（对比：`account_service` 那边做对了 —— WAL + `BEGIN IMMEDIATE` + `busy_timeout=5000`。）

### D2 桥的调试/放行开关共 **14 个**（文件驱动、无需重启）— 中危 · 已证实
```
account_auth_probe.py:149-162  cn_bridge_mode.txt / cn_bridge_exp.txt / cn_resp_format.txt /
                               cn_field_patch.txt / cn_canary.txt / cn_hash_mode.txt / cn_proto_val.txt /
                               cn_flatten_keys.txt / cn_packet_wrap.txt / cn_wrap_mode.txt /
                               cn_inner_min.txt / cn_inner_src.txt / cn_requestid_mode.txt
account_auth_probe.py:394-395  cn_billing_block.txt —— **注释明写 "1=拦 / 0=放行（fail-open）"**
account_service.py           CN_ACCT_SVC_FILE = cn_account_svc.txt（可整体关掉账号服务）
sdkcard.py:107-143           allow_pay.txt / pay.json —— 支付开关
```
**⇒ 任何能写 `/www/wwwroot/bapatch/` 的人都能改行为（含关闭 billing 拦截、绕过账号服务 fallback）。**
当前值：`cn_billing_block.txt=1`、`cn_account_svc.txt=1`、`cn_devid.txt=1`（fail-open 的默认方向是**危险**的：文件缺失/被删 = 放行）。

### D3 桥的 `_forward` 兜底会把未知 `/api/*` 原样转 5000 — 低危 · 已证实
`account_auth_probe.py:1637/2166/2340` `code, resp, ctype = self._forward(body)`；`:2341 rec['fallback']='forward-known-other'`

---

## 汇总（按严重度）

| 严重度 | 位置 | 一句话 | 证实 |
|---|---|---|---|
| **高危** | sdkcard.py:322-339 | 卡密无速率限制/无失败计数，可无限爆破 | 已证实 |
| **高危** | sdkcard.py:33-38 + 332-336 | 设备号取自请求头可伪造，`bind_one` 形同虚设 | 已证实 |
| **高危** | sdkcard.py:44-46（全仓无校验） | SDK Token 签发后**从不校验**，纯装饰 | 已证实 |
| **高危** | account_service.py:511-528 | `DevId` 可任意指定 ⇒ 可冒充任意已知账号拿 session | 已证实 |
| **高危** | sdkcard.py:23-30,336 | `cards.json` 无锁读-改-写、非原子写 ⇒ 并发丢数据/文件损坏 | 已证实 |
| **高危** | sdkcard.py:289,326,338 | 卡密明文 + 请求体前 500B 落 `sdk.log` | 已证实 |
| 中危 | sdkcard.py:281-282 | 请求体无大小上限 | 已证实 |
| 中危 | 桥 14 个开关 + billing fail-open | 文件驱动行为开关，缺省=放行 | 已证实 |
| 低危 | 桥 `_forward` 兜底 | 未知 `/api/*` 原样转 5000 | 已证实 |
| **已做对** | account_service.py 全部 SQL | 全参数化（`?`），列名来自常量白名单 | 已证实 |
| **已做对** | account_service.py WAL + BEGIN IMMEDIATE + busy_timeout | 并发写有事务保护 | 已证实 |
| **已做对** | account_service.py resolve_session / issue_session_key | uuid4 TTL + revoked + 会话上限 | 已证实 |
| **已做对** | sdkcard.py 路径常量 | 无外部输入进文件路径（无穿越） | 已证实 |

## 一句话总结
**这套 Python 服务的"会话层"做得不错（uuid4 + TTL + revoked + 全参数化 SQL），但"身份层"几乎没有防护：卡密可爆破、设备号可伪造、SDK token 不校验、`DevId` 可冒充，且卡密明文进日志、cards.json 无锁。**
