# 审计报告：account_service.py AccountDB 真值接线补丁

> 审计员：shittim-analyst（实现者以外的人）　·　2026-11-18
> 本地只读；未部署、未重启、未改任何线上/被审计文件
> 全部数字由本机重跑得出，未采信实现者自述

## 基线与产物（本机实测）

| 角色 | 路径 | 大小 | md5 |
|---|---|---|---|
| **真实线上基线** | `work\ba\srv_live\20261118_021609\bapatch\tools\account_service.py` | **102,919** | **`8227f28e7e13c502fcd7666743aa43a8`** |
| **待审补丁产物** | `work\ba\srv_live\20261118_0059\_patched\account_service.py` | **106,139** | **`436cba4df30e503212c2e737bf2f9f0c`** |
| 中间层（仅参考） | `…\_patched\account_service.py.pre_wire.bak` | 98,499 | `a1fe73cb…` |
| 原始版（已过时基线） | `work\ba\server\deploy\_baseline\account_service.py` | 94,576 | `a127e709…` |

**我自己重跑的 diff（live → patched）**：`difflib.unified_diff(n=2)` ⇒ **6 个 hunk / +103 / −20**，与 lead 的 6 hunk 结论一致（行数口径不同只是因为 context 行计入方式）：

```
@@ -51,4  +51,5    @@   import urllib.request
@@ -236,17 +237,33 @@   _pick_ci + _FIELD_SPEC 重写
@@ -272,10 +289,12 @@   fetch_real_account_fields: sid 短路
@@ -379,4  +398,62 @@   _fallback_publisher_id + identify 兜底
@@ -768,7  +845,13 @@   identify(): 硬 raise → 条件化
@@ -1163,5 +1246,5 @@   CallNameUpdateTime
```
**无意外删除**（删除的 20 行全部是被替换的旧实现）。

---

## 总表

| 项 | 结论 | 一句话 |
|---|---|---|
| **A** 语法/结构完整性 | **PASS** | `ast.parse` / `ast.parse(feature_version=(3,10))` / `py_compile` 全通；无方法丢失、无重复定义、无 TODO、无截断痕 |
| **B** `_pick_ci` 语义 | **PASS** | 三种大小写全命中；非 dict 返回 `(False,None)` 不抛；`0/""/None` 均 `found=True` |
| **C** `_FIELD_SPEC` 12 条 | **PASS** | camelCase 载荷 **12/12** 全出（首测 11/12 是我构造的载荷缺 `comment`，补上即 12/12） |
| **D** `CallNameUpdateTime` | **PASS** | 新号→零值、有昵称→created、空昵称+有值→用值；**既有账号不受影响**（实测 `老师0001` 这类非空昵称走 created 分支） |
| **E** 失败模式安全性 | **FAIL（架构级，非本补丁引入）** | sid=0 短路正确；但 `identify()` 兜底会让**所有拿不到 DevId 的设备塌缩到 `dev_id='314816420'` 同一账号** ⇒ 卡业务（公益卡/付费卡）当前不可用 |
| **F** 安全 | **PASS** | 日志无 token/dev_id/admin_key 泄漏；无新增外部地址（仅 `127.0.0.1:5000`）；admin key 不落日志 |
| **G** 会丢失的东西 | **PASS** | 以 102,919 为基线重跑：`gzip/decompress/Content-Length/MAX_/limit/read(` 计数 **live == patched**，本补丁**没有丢掉任何保护**（这些保护本来就不在这两个文件里，可能在 `account_auth_probe.py`，超出本次范围） |

---

## A. 语法 / 结构完整性 —— PASS

| 检查 | 结果 |
|---|---|
| `ast.parse(src)` | OK |
| `ast.parse(src, feature_version=(3,10))` | **OK**（对齐服务器 Python 3.10） |
| `py_compile.compile(doraise=True)` | OK |
| 行数 | 2,259 行 |
| 顶层 `def`/`class` | 55 个顶层函数 / 10 个类 |
| `class AccountService` 方法数 | **P：60 / 线上：59**（新增仅 `_build_account_db_for_shadow`） |
| 丢失的方法 | **无**（`only in ORG: []`） |
| 顶层重复定义 | **无** |
| 类内重复方法 | **无** |
| `# TODO` / `# FIXME` / `# BUG` / `# XXX` | **0 处** |
| 连续 ≥3 行被注释掉的代码块 | **0 处** |

**`import urllib.request` 位置（A 项新增要求）**：补丁在 **L53**，位于文件头部标准库 import 区、`import os`/`import json` 等之后，**不在任何条件块内**，无循环依赖、无 `try/except` 包裹。Python 3.10 下 `urllib.request` 是标准库，无隐性依赖。

**线上版缺 import 已复验**：
```
LIVE : 'import urllib' 出现 0 次 | 'urllib.request.' 出现 2 次   ← NameError 根因
PATCH: 'import urllib' 出现 1 次（L53） | 'urllib.request.' 出现 2 次
```
⇒ **5 轮"部署成功但结果没变"的直接原因确认成立**。

---

## B. `_pick_ci` 语义 —— PASS

实测（`L239-252`）：

| 用例 | 结果 |
|---|---|
| `{'level':90}` + names `("level","Level")` | `(True, 90)` |
| `{'Level':90}` + 同上 | `(True, 90)` |
| `{'LEVEL':90}` + `("LEVEL",)` | `(True, 90)` |
| `vipLevel` / `VipLevel` / `VIPLevel` | 三者均 `(True, 3)` |
| `raw=None` / `[...]` / `"x"` | `(False, None)`，**不抛** |
| `{'level':0}` | `(True, 0)` ✔ 零值不丢 |
| `{'nickname':''}` | `(True, '')` ✔ |
| `{'callName':None}` | `(True, None)` ✔（后续 `merge` 跳过 None） |

**同名不同大小写**：`{'Level':90,'level':1}` 取 **精确同名** 那个（`1`）；若两个都精确同名不可能。**唯一误取场景**：API 同时返回 `Level` 和 `level` 且值不同（当前 Shittim detail API 只返回 camelCase，不会出现）。

---

## C. `_FIELD_SPEC` 12 条 —— PASS

构造 camelCase 载荷（含 `level=90, exp, vipLevel=3, unReadMailCount=5, nickname='111', callName='杂鱼', state=3, representCharacterServerId=9, publisherAccountId=314816420, lastConnectTime, createDate, comment`）：

**12/12 全部 `found=True` 且产出非 None**。

`_to_*` 边界：
| 函数 | 输入 → 输出 |
|---|---|
| `_to_int` | `None→None`、`""→None`、`"123"→123`、`-5→None`、`True→None` ✔ |
| `_to_str` | `None→None`、`"  "→None`、`"111→'111'` ✔ |
| `_to_time` | `None→None`、`"0001-01-01T00:00:00"→None`（零值当缺失）、ISO 原样返回 ✔ |

> `_to_time` 把 `0001-01-01*` 视为缺失 ⇒ API 返回未初始化时间时**不会覆盖**影子值，这是对的。

---

## D. `CallNameUpdateTime` —— PASS

代码（`L1248`）：
```python
'CallNameUpdateTime': (to_iso(account.call_name_update_time) or
    ('0001-01-01T00:00:00' if not (getattr(account,'nickname','') or '').strip() else created)),
```
实测（`to_iso(None) = None`，`or` 链正常工作）：

| 场景 | 输出 |
|---|---|
| 新账号：昵称空 + cnut=None | **`'0001-01-01T00:00:00'`** ✔ 零值 |
| **既有账号**：昵称 `老师0001`/`111` + cnut=None | **`created`** ✔ 与 lead 的边界预期一致 |
| 昵称空 + cnut **有值** | `'2026-11-01T00:00:00'`（用显式值）——**不算 bug**，显式值优先是合理语义 |
| 昵称全空白 `'   '` | 零值 ✔（`strip()` 生效） |

⇒ **既有账号不受影响，只有新建账号走零值分支**，与"保留设置昵称界面"的需求一致。

---

## E. 失败模式安全性 —— 部分 PASS / 架构级 FAIL（**非本补丁引入**）

### E1 `sid=0` 会不会发请求？ **不会** ✔
```python
# L273-275
sid = str(server_id)
if not sid or sid in ("0", "None"):
    return {}
```
### E2 `merge_real_account_db(base, 0)` 是否原样返回？ **是** ✔
`fetch` 返回 `{}` ⇒ 循环不执行 ⇒ 返回**同一个** `base` 对象（`L313-327`）。

### E3 兜底 `dev_id` 到底是啥？ **`'314816420'`**
```python
# L439-456
DEFAULT_FALLBACK_PUBLISHER_ID = 314816420
# L847-855
_fb = _fallback_publisher_id()
if _fb <= 0: raise AuthRejected(...)
_warn_once('identify: no DevId/DeviceUniqueId, falling back to publisher_id=%s' % _fb)
return Identity(dev_id=str(_fb), ...)
```
`get_or_create_account` **只按 `dev_id` 查**：
```python
# L882
row = self._fetchone('SELECT * FROM accounts WHERE dev_id = ?', (identity.dev_id,))
```
⇒ 若 `accounts` 表里**没有** `dev_id='314816420'` 的行 ⇒ **走 `_create_account` 新建空号**（第 4 轮那个坑仍在，只是从"心跳 ID"改成了"固定 publisherId"）。命中与否**取决于线上库现状**，本机无该库，**存疑**。

### E4 兜底会让多设备共用同一账号 —— **是，且卡业务不可实现**
- 公益卡（账号跟随设备 `md5("free:"+device)`）：**当前根本无法实现** —— 兜底 `dev_id` 是常量，与设备无关。
- 付费卡（账号跟随卡密 `md5(card)`）：**同样不成立** —— 兜底忽略卡密，与卡无关。
⇒ **结论：`_fallback_publisher_id()` 是"临时单账号部署形态"的已知代价，必须先修 `identify()` 的真实身份来源，才能上卡业务。**

### E5 双重合并有副作用吗？ **无实质副作用，但冗余**
- `build_account_db_for`（`L1216-1223`）merge 一次；
- `build_state_for`（`L1303`）又 merge 一次。
两次都走 `_REAL_CACHE`（TTL 内命中），**不重复发请求、不写库、无递归**。代价只是多一次函数调用与一次 `resolve_sid_for_account`（后者 60s 缓存）。**建议后续删掉 L1303 那次**（纯清理）。

### E6 key 失败路径会不会 500？ **不会** ✔
`_resolve_admin_key()` 失败返回 `""`（`L176-185`，不 raise）；`_http_json` 空 key `raise RuntimeError`（`L201-202`）→ 被 `fetch_real_account_fields` 的 `except` 吞掉（`L287-289`）→ 返回 `{}` → merge 空操作。`resolve_sid_for_account` 也全程 try（`L391-393`）。**客户端不会拿到 500。**

### E7（新增）`req_frag_head` 到底是什么 —— **存疑，倾向"拿不到真实 DevId"**
- 桥侧：`rec['req_frag_head'] = str(r.get('fragment'))[:600]`（`_baseline\account_auth_probe.py:1116`）——**解密明文的一个片段，截断 600 字符**；
- `acct_apply_to_auth` 把它解析成 dict（`:82-95`）后喂给 `svc.identify(req)`（`:106-109`）；
- `account_service._decode_request` 接受 dict/str/bytes（`L2012-2021`），`identify` 再从 body 里 `_pick(...('DevId','DevID','devId','dev_id'))`（`L834`）。

⇒ **它可以是完整 body 的一个"片段"**：若 `DevId` 落在片段之外（片段起点是被截出来的中段）或缺字段，`_pick` 返回 None ⇒ 走兜底。
**日志里的 `De****` 是日志层脱敏，不代表内存值被脱敏**；但**截断 600 字**是真实的内存行为 ⇒ **不能保证拿到 DevId**。
**定论所需证据**：一次真实请求里打印 `len(frag)` 与 `'DevId' in frag`（桥侧加一行 debug，或看 `api_all_requests.log` 里同一请求的 `req_keys` 是否含 `DevId`）。

---

## F. 安全 —— PASS

- **日志泄漏**：全文件扫描"日志语句里出现 token/DevId/admin_key" ⇒ 仅 `L852` 打的是 `publisher_id=%s`（非敏感）与 CLI 打印 `dev_id=%s`（本地运维命令，非服务路径）。**无 token、无 admin key**。
- **admin key**：只在 `X-Admin-Key` 请求头里使用（`L203`），**从不写日志、不进响应**；`_find_admin_key` 只回一个 `AdminApiKey` 字符串，**不落整份 Config**（`L148-159`）。
- **外部地址**：文件内 http(s) 仅 `http://127.0.0.1:5000`（`L140`，`SHITTIM_ADMIN_URL` 可覆盖）与一条**既有**静态资源 URL（`L1634`，非本补丁新增）。
- **异常形态**：失败一律 `{}` + stderr WARN，不向客户端抛。

---

## G. 会丢失的东西 —— PASS（以 102,919 为基线重跑）

| 关键字 | live | patched | 判定 |
|---|---|---|---|
| `MAX_` | 1 | 1 | 一致 |
| `limit` | 2 | 2 | 一致 |
| `cap` | 0 | 0 | 一致 |
| `gzip` | 0 | 0 | 一致 |
| `decompress` | 0 | 0 | 一致 |
| `Content-Length` / `content_length` | 0 / 0 | 0 / 0 | 一致 |
| `truncat` | 0 | 0 | 一致 |
| `iter_content` | 0 | 0 | 一致 |
| `read(` | 3 | 3 | 一致 |

⇒ **本补丁没有回退任何解压/请求体/超时保护**；这些保护**本来就不在 `account_service.py` 里**（`limit=2` 是 SQL LIMIT 之类，非请求体上限），应在 `account_auth_probe.py`（**不在本次审计范围**，仅注明）。

---

## 部署判定（5 行内）

1. **可以部署**：A/B/C/D/F/G 全 PASS，语法在 Python 3.10 下干净，`import urllib.request` 修复了 5 轮失败的直接原因。
2. **但只能按"单账号部署形态"上**：E 项的 `identify()` 兜底会把所有设备塌缩到 `dev_id='314816420'`，**卡业务（公益卡/付费卡）在修 `identify` 之前无法实现**。
3. **部署后必须验**：`accept_accountdb.py` 四项数值断言全 PASS 才算真生效（`Level=90 / Nickname='111' / RepresentCharacterServerId=9 / publisherAccountId=314816420`）。
4. **E3 存疑项**：线上库若无 `dev_id='314816420'` 的行，第一次登录会**新建空号**；部署前用一条 SQL 确认（`SELECT server_id, dev_id FROM accounts;`）。
5. **建议清理（非阻塞）**：删掉 `L1303` 的重复 merge。
