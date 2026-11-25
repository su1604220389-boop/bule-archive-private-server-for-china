# 审计报告 v2：account_auth_probe.py 身份修复补丁（P1–P5）

> 审计员：shittim-analyst　·　2026-11-18　·　**只读**：未改被审文件、未部署、未重启
> 自述（SELFTEST 14 PASS）**未采信**，全部结论由本机重跑得出

## 基线复验（我自己的 md5）

| 角色 | 大小 | md5 | 与 lead 给的一致？ |
|---|---|---|---|
| BASE `…\20261118_022226\bapatch\tools\account_auth_probe.py` | **161,194** | **`1db27e4c5d9074bf8ad15b216327aef4`** | ✅ |
| PATCH `…\20261118_022226\_patched\account_auth_probe.py` | **163,959** | **`6ac20bc7b4309d4eb0ee33f61f9a1f22`** | ✅ |
| diff | **9 hunk / +75 / −6** | — | 与"9 hunk"一致；净增 +2,765 B |

---

## 总表

| 项 | 结论 | 一句话 |
|---|---|---|
| **A** 账号解析永不误建号 | **FAIL（A4/A6）** | exact/retarget/create 三级判定结构正确，但 **A4 异常分支仍会建号**、**A6 环境变量无校验** |
| **B** TLS 线程配对 | **PASS** | 交错写入不串号、读完 `.v`/`.seq` 同时清、异常不会留旧值 |
| **C** 明文不入日志 | **FAIL** | `devid_stash` 用默认 `keep=(4,4)` ⇒ 9 位 DevId **泄漏 8 位**（`3148****6420`）；且"改用 `keep=(2,0)`"这条要求本身有 bug |
| **D** h5 灌 TLS 的位置 | **PASS** | 在 `if r is not None:` 内、`req_json = r.get('json')` **之前**、`isinstance(req_json, dict)` **之外** |
| **E** 结构完整性 | **PASS** | 149→149 函数、无新增/删除、无重复定义、3.10 语法 OK |
| **F** 兼容性 | **PASS（附 1 处 relay 缺陷）** | 老路径回退可用、`acct_svc_on()` 早退不变、`RL2_LOCAL.busy` 重入保护未动；但 **h9 的 `_frag` 未定义**（见 G） |
| **G**（新增）relay 三处灌 TLS | **FAIL（1 处）** | L3608-3617 的分支使 `_frag` 可能未定义 → `NameError` 被吞 → 该路径 TLS 恒空 |

---

## A. 账号解析：必须证明永远不会误建新号 —— **FAIL**

代码（`L129-160`）：
```python
_dev = (getattr(ident, 'dev_id', '') or '').strip()
_exit = False
if _dev:
    try:
        _exit = svc.get_account_by_dev_id(_dev) is not None
    except Exception:
        _exit = True            # 查询出错按"存在"处理
if not _exit:
    try: _fb_row = svc.get_account_by_dev_id(str(FALLBACK_DEV_ID))
    except Exception: _fb_row = None
    if _fb_row is not None:
        ident.dev_id = str(FALLBACK_DEV_ID); ...   # retarget
    else: rec['acct_id_src'] = 'create'
else:
    rec['acct_id_src'] = 'exact'
acct = svc.get_or_create_account(ident)            # ★ 无论如何都会走到这里
```

| # | 要求 | 结论 | 依据 |
|---|---|---|---|
| A1 | 真 dev_id 有行 → exact，不改 dev_id | **PASS** | `_exit=True` ⇒ 不 retarget，`ident.dev_id` 保持不变 |
| A2 | 真 dev_id 无行 + 兜底有行 → 改成 314816420，仍调 `get_or_create_account` | **PASS** | `L146-149` 改 `ident.dev_id`，随后统一走 `L150`，`_stamp_login` 保留 |
| A3 | 两个都无行 → 才允许建号 | **PASS** | `L150` 是唯一落点，符合"真全新安装" |
| **A4** | `get_account_by_dev_id` 抛异常 → 按存在处理、**不建号** | **FAIL** | `except: _exit = True` 只是**跳过 retarget**；随后 `L150 get_or_create_account(真dev_id)` 在查不到行时**照样 `_create_account`** ⇒ 仍然建号 |
| A5 | `ident.dev_id` 空 / 走兜底 → 行为与改动前一致 | **PASS** | `_dev` 空 ⇒ `_exit=False` ⇒ 查兜底行 ⇒ 有则 retarget 到 `314816420`，等价于旧兜底身份 |
| **A6** | `BA_FALLBACK_DEV_ID` 非法值安全退回默认 | **FAIL** | `FALLBACK_DEV_ID = os.environ.get('BA_FALLBACK_DEV_ID') or '314816420'` **无任何校验**：`abc`/`-5`/`0` 原样接受 |

**A4 最小修法**（3 行）：
```python
    except Exception:
        _exit = True            # 查询出错：不改成 create（
+       try:
+           ident.dev_id = str(FALLBACK_DEV_ID)   # 保守：退到兜底账号
+       except Exception:
+           pass
```
> 语义：查询坏掉时宁可落到已知的兜底账号，也不要走 create。

**A6 最小修法**（1 行）：
```python
-FALLBACK_DEV_ID = os.environ.get('BA_FALLBACK_DEV_ID') or '314816420'
+_fb_env = (os.environ.get('BA_FALLBACK_DEV_ID') or '').strip()
+FALLBACK_DEV_ID = _fb_env if (_fb_env.isdigit() and int(_fb_env) > 0) else '314816420'
```

---

## B. TLS 线程配对 —— **PASS**（实测）

抽取 `_FRAG_TLS` / `_req_dict` 两个节点独立执行（不改文件）：

| 用例 | 结果 |
|---|---|
| A 写 → A 读 | `{'DevId': 'AAA'}` ✔ |
| **A 写 → B 写 → A 读** | `{'DevId': 'AAA'}` —— TLS 因 seq 不匹配被拒，回退到 **A 自己的** `req_frag_head`，**没有读到 B** ✔ |
| 读完清空 | `v=None seq=None`（**两者同时清**）✔ |
| 异常路径 | 清空语句位于**第一个 try 的最前面**（`L93-94`，在任何 `rec` 访问之前）⇒ 后续任何异常都不可能把 `.v` 留成脏值；实测异常后 `v=None seq=None` ✔ |

> `id(rec)` 复用风险：清空是**无条件**的（读完立即置 None），所以即使 Python 复用同一 id，也只会命中"空值"而不是旧值 ✔。

---

## C. 明文有没有漏进日志 —— **FAIL**

`devid_stash`（`L624-638`）：
```python
if isinstance(dv, str) and dv.strip():
    rec['req_DevId'] = mask_secret(dv.strip())          # ← 没传 keep
if isinstance(du, str) and du.strip():
    rec['req_DeviceUniqueId'] = mask_secret(du.strip()) # ← 没传 keep
```
`mask_secret` 默认 `keep=(4,4)`（`L200`）—— 实测：
```
mask_secret('314816420')       -> 3148****6420(len=9,sha8=a424da70)   ← 泄漏 8/9 位
mask_secret('ce8ffeb7d08cfb36')-> ce8f****fb36(len=16,...)            ← 泄漏 12/16 位
```
**⚠ 另外：任务书要求的 `keep=(2,0)` 本身是错的** —— `mask_secret` 里 `s[-keep[1]:]`，当 `keep[1]==0` 时 `s[-0:]` 等于**整个字符串**：
```
mask_secret('314816420', (2,0)) -> 31****314816420(len=9,...)         ← 全泄漏，比默认更糟
```
**最小修法**（二选一）：
```python
# 方案 1（改调用点，最小）
-            rec['req_DevId'] = mask_secret(dv.strip())
+            rec['req_DevId'] = mask_secret(dv.strip(), keep=(2, 1))
# 方案 2（改 mask_secret，一劳永逸，兼容 keep[1]==0）
-    return "%s****%s(len=%d,sha8=%s)" % (s[:keep[0]], s[-keep[1]:], len(s), ...)
+    _tail = s[-keep[1]:] if keep[1] > 0 else ''
+    return "%s****%s(len=%d,sha8=%s)" % (s[:keep[0]], _tail, len(s), ...)
```

其余脱敏点核对：
- `rec['acct_mxtoken'] = mask_secret(...)` ✔（`L162`）
- `rec['req_Token'] = mask_secret(...)` ✔（`L2339`）
- `rec['req_frag_head'] = mask_secret(str(fragment)[:600])` ✔（`L2336`，先遮后存）
- `req_devid_sha8` 用 `hashlib.sha256`（`L636`），**不是** `_hashlib`（注意别混）
- `_FRAG_TLS` 全部 12 处使用点已逐一核对（`L82/91/92/93/94/2327/2328/2330/2331/3520/3521/3523/3524/3613/3614/3616`）——**没有一处**把 `.v` 写进 `rec` / `print` / `_log` ✔

**结论 C：唯一不合格点就是 DevId/DeviceUniqueId 的 keep 参数。**

---

## D. h5 灌 TLS 的位置 —— **PASS**

```
2320  if r is not None:
2321      rec['decrypted'] = True
2322      rec['req_key'] = mask_secret(r.get('key'))
2325      rec['req_frag_len'] = r.get('frag_len')
2326      try:                                  ← 灌 TLS 在这里
2327          _FRAG_TLS.v = r.get('fragment') or None
2328          _FRAG_TLS.seq = id(rec)
2332      req_json = r.get('json')              ← 在它之前 ✔
2333      if isinstance(req_json, dict):        ← 在它之外 ✔
```
逐条对照上一轮的坑：① 在 `if r is not None:` 层内 ✔ ② 在 `req_json = r.get('json')` **之前** ✔ ③ 在 `if isinstance(req_json, dict)` **之外** ✔。

---

## E. 结构完整性 —— **PASS**

| 检查 | BASE | PATCH |
|---|---|---|
| 行数 | 3,914 | 3,983 |
| 函数总数 | **149** | **149**（新增 0 / 删除 0） |
| 类 | 2 | 2 |
| `ast.parse` | OK | OK |
| `ast.parse(feature_version=(3,10))` | OK | OK |
| 顶层名只在 BASE / 只在 PATCH | — | `[]` / `[]` |
| 函数名只在 BASE / 只在 PATCH | — | `[]` / `[]` |
| 重复定义 | — | **无** |
| `TODO/FIXME/BUG` | — | **0** |

---

## F. 兼容性 —— **PASS（附 h9 缺陷）**

| 检查 | 结论 |
|---|---|
| TLS 缺失时回退 `req_frag_head` | ✔ `_req_dict` 里 `if not frag: frag = (rec.get('req_frag_head') or '').strip()` 保留 |
| `acct_svc_on()==False` 早退 | ✔ `L120` 未改（`L51` 定义、`L120` 与 `L175` 两处早退） |
| relay 影响 `RL2_LOCAL.busy` | ✔ 重入保护完整：`L3829 getattr(...,'busy')` → `L3832 busy=True` → `L3836 finally busy=False`；三处 TLS 写入都在 `busy=True` 之内，不改变重入语义 |

### G（新增）h9 的 `_frag` 可能未定义 —— **FAIL**

```
3607  # BAPATCH-RLFIX: ...
3608  if isinstance(rec, dict) and not rec.get('req_frag_head'):
3609      _frag = decoded.get('fragment') if isinstance(decoded, dict) else None
3610      if isinstance(_frag, str):
3611          rec['req_frag_head'] = mask_secret(_frag[:300])
3612  try:
3613      _FRAG_TLS.v = _frag if isinstance(_frag, str) else None   ← 若 3608 为假，_frag 未定义
3614      _FRAG_TLS.seq = id(rec)
3615  except Exception:
3616      _FRAG_TLS.v = None
3617      _FRAG_TLS.seq = None
```
- **触发条件**：`rec` 里**已有** `req_frag_head`（很常见 —— h5 解密路径与 h7 relay-text 路径都会先写它）。
- **后果**：`NameError` 被 `except` 吞掉 ⇒ `.v/.seq` 置 None ⇒ 该 relay 路径**拿不到明文片段**，`_req_dict` 退回**已脱敏**的 `req_frag_head` ⇒ `identify` 拿到 `3148****6420(...)` 这种串 ⇒ 落到兜底身份。
- **最小修法**（1 行，把赋值提出来）：
```python
+    _frag = decoded.get('fragment') if isinstance(decoded, dict) else None
     if isinstance(rec, dict) and not rec.get('req_frag_head'):
-        _frag = decoded.get('fragment') if isinstance(decoded, dict) else None
         if isinstance(_frag, str):
```
> 对照：h7（`L3519-3524`）与另一个 relay 站点写法正确（`_frag` 在使用前已赋值）。

---

## 部署判定（5 行）

1. **不能部署**：C 项硬红线 —— 9 位 DevId 在 `rec['req_DevId']` 里泄漏 8 位（`3148****6420`），审计要求是只留 2 位。
2. **A4 必须修**：查询异常时仍会 `get_or_create_account` → 建新号，正是这轮要防的事故。
3. **A6 必须修**：`BA_FALLBACK_DEV_ID=abc` 会被原样接受，配置写错就静默跑偏。
4. **G 必须修**：h9 的 `_frag` NameError 让该路径 TLS 恒空，身份退回已脱敏串（效果等于没修）。
5. **B/D/E/F 均 PASS**，改动本身方向正确；修完这 4 处（约 8 行）可复审后部署。

---
---

# v3 复审（2026-11-18 追加）

## 身份复验（我自己的 md5）

| 角色 | 大小 | md5 | 与 lead 给的一致？ |
|---|---|---|---|
| BASE | **161,194** | **`1db27e4c5d9074bf8ad15b216327aef4`** | ✅ |
| PATCH v3 | **164,514** | **`7d4d162516c2ac1dd6b140bb6a01779b`** | ✅ |
| 差异 | **11 hunk / +93 / −9** | — | ⚠ lead 说 10 hunk，实测 **11**（口径差异，非缺陷；hunk 头：`-81,-113,-122,-163,-583,-588,-2280,-2287,-3467,-3550,-3798`） |

## v3 总表

| 项 | 结论 | 一句话 |
|---|---|---|
| **A** P4 三值判定 | **PASS** | 四条要求**全部动态验证通过**（用文件里的原样代码跑真值表） |
| **B** mask_secret | **PASS** | `keep=(0,0)` 输出 `****(len=9,sha8=…)` 不含原串；`(4,4)` 行为与 v2 完全一致 |
| **C** relay `_frag` | **PASS** | h8/h9 两处都提前；`req_frag_head` 的写入条件未变；TLS 双重写入无副作用；`busy` 未受影响 |
| **D** 结构 | **PASS** | 149→150（+`_fallback_dev_id`）、无重复定义、3.10 语法 OK、无丢失 |

## A. A4 那把刀——**真修掉了**（动态真值表）

用文件中 **原样代码**（`L140-L170`，dedent 后 exec）+ 假 `svc` 跑：

| 用例 | `ident.dev_id` | `acct_id_src` | 是否建号 |
|---|---|---|---|
| a) 真 dev_id 查询**抛异常** + 兜底**存在** | **314816420**（已改） | `retarget-fallback` | 否（命中兜底行）✔ |
| b) 真 dev_id 抛异常 + 兜底**也抛异常** | **314816420**（已改） | `retarget-fallback` | 否 ✔ |
| c) 真 dev_id **明确无行** + 兜底**明确无行** | **999（保持真值）** | `create` | **是，且建的是真 dev_id** ✔ |
| d) 最外层 except 触发 | **314816420**（已拉回） | — | 否 ✔ |
| e) `ident.dev_id` 为空（兜底身份） | 314816420 | `retarget-fallback` | 否 ✔ |

关键代码（`L149-169`）：
```python
149  if _exists is True:
150      rec['acct_id_src'] = 'exact'
151  else:
153      _fb_exists = svc.get_account_by_dev_id(_fb) is not None
155      except Exception: _fb_exists = None            # 未知
156      if _exists is False and _fb_exists is False:
157          rec['acct_id_src'] = 'create'              # 两者都确认不存在
158      else:
159          ident.dev_id = _fb                         # 未知 ⇒ 一律退兜底
...
163  except Exception as e:
166      ident.dev_id = str(FALLBACK_DEV_ID)            # 兜底中的兜底
```
**`_exists = None` 确实落到 `else`（L158-159）并被改写成兜底号** —— 与要求完全一致。**A4 已修。**

## B. mask_secret —— **修好了，且行为中立**

| 调用 | 实测输出 |
|---|---|
| `mask_secret('314816420', keep=(0,0))` | **`****(len=9,sha8=a424da70)`** —— 不含原串任何片段 ✔ |
| `mask_secret('314816420')`（默认 4,4） | `3148****6420(len=9,sha8=a424da70)` —— **与 v2 输出逐字相同** ⇒ 修 1a 行为中立 ✔ |
| `mask_secret('abc', (0,0))` | `****(len=3,sha8=ba7816bf)` ✔ |

修 1b 已生效：`L646/L648` 两处改用 `keep=(0, 0)`。

**残留（低危，非本次引入）**：仍用**默认 keep** 处理明文的地方有 4 处 ——
`L2351 req_frag_head`（解密明文片段，泄漏前 4+后 4 字符）、`L3541`、`L3632`、`L3886`（同样内容）。
另有 `L179 acct_mxtoken`、`L2337 req_key`、`L2338 req_iv`、`L2354 req_Token` 亦为默认 keep。
这些都是 **v2 就有**的行为（v1 完全不遮），不影响本轮判定；建议下一轮统一改 `keep=(0,0)`。

## C. relay `_frag` 提前 —— **两处都修对了，没有改坏**

| 检查 | 结果 |
|---|---|
| h8：`_frag` 在使用前赋值 | ✔ `L3623` 赋值 → `L3625` 写 TLS → `L3630` 条件写 head |
| h9：同上 | ✔ `L3877` 赋值 → `L3879` 写 TLS → `L3884` 条件写 head |
| `req_frag_head` 写入条件 | ✔ 仍是 `if isinstance(rec, dict) and not rec.get('req_frag_head')`（`L3630`、`L3884`） |
| h7（relay-text） | ✔ `L3534-3539` 先写 TLS，`L3540-3541` 再按同一条件写 head |
| 两处 TLS 是否重复写 | 不会：分属**不同函数**（`_rl_relay_once` L3609 / `_rl2_relay_once` L3854），一次请求最多走一条；即使都走，`seq = id(rec)` 相同、值相同，**覆盖无副作用** |
| `RL2_LOCAL.busy` | ✔ 未改动（v2 审计已确认 `L3829-3836` 结构完整，v3 该区间仅上移行号） |

## D. 其余

- `ast.parse` / `ast.parse(feature_version=(3,10))` 均 OK。
- 函数 149 → **150**，新增仅 `_fallback_dev_id`（`L85-89`），**无删除、无重复定义**。
- `_FRAG_TLS` 使用点全部为读写 TLS 本身，**无一写进 `rec` / `print` / `_log`**。
- 灌 TLS 位置：`L2340-2345`（v3 行号）仍在 `if r is not None:` 内、`req_json = r.get('json')` **之前**、`isinstance(req_json, dict)` **之外**。
- **A6 也已修**：`_fallback_dev_id()` = `isdigit() and 0 < len <= 20 and int(v) > 0`，非法（空/`abc`/`-5`/`0`）回退 `'314816420'` ✔（注意它是**导入期求值**，改环境变量需重启进程）。

## v3 部署判定（5 行）

1. **可以部署**：v2 的 4 个 FAIL（A4 / A6 / C / G）**全部修复并被本机动态验证**，A–D 四项 PASS。
2. 唯一残留是**低危**：`req_frag_head` 等 4 处仍用默认 `keep`，明文片段前 4+后 4 字符会进日志 —— 不阻塞，建议下一轮统一 `keep=(0,0)`。
3. hunk 数实测 **11**（你记的 10），差异来自 context 计法，无实际影响。
4. **卡点不在代码**：`identify()` 能否从 `req_frag_head` 拿到真 DevId 仍未证实（需一次真实请求的 `req_devid_len` / `req_devid_src` 日志）；若拿不到，全部设备仍会走 `retarget-fallback` 落到同一账号。
5. 部署后请先看桥日志里 `acct_id_src` 的分布：出现 `exact` 才算真分流；全是 `retarget-fallback` 就是身份仍未接通。
