# 90004 Management_Data 补丁准备（本地产物，未部署）

- 时间：2026-11-19 02:03–02:12（Asia/Shanghai）
- 执行：本地（Windows / Python 3.12.11），**未 SSH、未改服务器、未改 `work/ba/srv_src`、未改快照原件**
- 目标：确认 `dto90004.py` / `patch_90004.py` 能对当前桥版本工作，并产出 ops 数据、预期响应、验证脚本
- 结论：**补丁在副本上跑通（两个基线都 PASS）；ops 文件 9 键条数全对、与官方 `inner.Data` 逐字节相同；e2e 31 项检查 FAIL=0**

---

## 0. 先说一个必须知道的版本差距（不影响补丁，但影响「拿哪个文件打」）

| 来源 | 大小 | sha256 / md5 | 说明 |
|---|---:|---|---|
| `work/ba/srv_live/20261118_022226/bapatch/tools/account_auth_probe.py`（任务说的「最新快照」） | 161,194 B | sha256 `b571c72b…` / md5 `1db27e4c…` | 快照时间 **11-18 02:22** |
| `work/ba/server/deploy/_build_banreply2/account_auth_probe.py` | 222,486 B | sha256 `ba322fae…` / md5 `af1bc9a5…` | 正是 `ITEMLIST_RELAY_V2.md` 记录的「线上改动前」那一版 |
| 线上（据 `ITEMLIST_RELAY_V2.md`，11-19 00:49） | 222,539 B | md5 `da07749d…` | = 上一行 + 一行 `RL2_HANDLED` 改动（53 B） |

也就是说 **srv_live 快照比线上少了 ~61 KB**（11-18 之后的 8000 list / 90011 / relay 等补丁没进快照）。
所以我把补丁在**两个基线**上都跑了一遍（161,194 B 快照 和 222,486 B 接近线上那一版），都 PASS。
**部署时不要直接推我打好的文件**（它基于 161 KB 快照，会丢线上后续改动）；正确做法见 §7：
把线上真身拉成副本 → 重跑 `patch_90004.py` → 校验 → 覆盖。补丁是纯文本锚点插入，7 个锚点在两个基线上都在。

---

## 1. 打补丁前后 diff（关键片段）

完整 diff：`work/ba/server/deploy/_p90004/90004_patch.full.diff`（228 行）
分支级 diff：`work/ba/server/deploy/_p90004/90004_patch.branch.diff`（45 行）

### 1.1 改动点一：内联 `dto90004.py` 正文（+163 行）

插在「第一个顶层 `def`」之前（`_LAST_SID = None` 之后、`def acct_svc_on():` 之前）：

```
 49  _SVC_INST = None
 50  _LAST_SID = None
 51 +# ==== BEGIN 90004-PATCH v1 (from work/ba/server/deploy/dto90004.py)
 52 +# 本块由 work/ba/server/deploy/patch_90004.py --apply 生成，不要手改。
 53 +# 改逻辑请改 work/ba/server/deploy/dto90004.py，然后重新 --apply（幂等）。
 ...
 58 +P90004_DATA_KEYS = ("Notices", "Events", "Issues", "Banners", "GachaProbabilityDisplay",
 63 +P90004_NULL_KEYS = ("GachaPeriodDisplay", "RaidPeriodDisplay", "Survey")
 99 +P90004_OPS_PATHS = ("/www/wwwroot/bapatch/_ba_state/90004_ops.json",
100 +                    "/www/wwwroot/bapatch/90004_ops.json")
150 +def build_90004_management_data(session_key, ticks, request_id, ops=None):
184 +def load_90004_ops(path=None):
192 +def data_key_report(obj):
213 +# ==== END 90004-PATCH v1 ====
```

### 1.2 改动点二：`if num == 90004:` 分支（旧 23 行 16 键 → 新 25 行 6 键 + Data(9 键)）

```diff
--- if num == 90004:  (BEFORE, 23 lines)   L1880
+++ if num == 90004:  (AFTER, 25 lines)    L2044
@@ -1,23 +1,25 @@
         if num == 90004:
             from datetime import datetime as _d9
+            import uuid as _uuid9
             _n9 = _d9.now()
             _t9 = int((_n9 - _d9(1, 1, 1)).total_seconds()) * 10_000_000 + _n9.microsecond * 10
-            obj = {"Protocol": 90004,
-                   "ServerTimeTicks": _t9,
-                   "ServerNotification": 0,
-                   "MissionProgressDBs": [],
-                   "EventMissionProgressDBDict": {},
-                   "BattlePassMissionProgressDBDict": {},
-                   "StaticOpenConditions": dict(cn_inner.STATIC_OPEN_CONDITIONS),
-                   "Notices": [],
-                   "Events": [],
-                   "Issues": [],
-                   "Banners": [],
-                   "GachaProbabilityDisplay": False,
-                   "ContentLock": False,
-                   "GachaPeriodDisplay": False,
-                   "RaidPeriodDisplay": False,
-                   "GuidePopup": {}}
-            rec['gen_kind'] = 'management-90004'
+            _sk9 = getattr(SESSION, 'session_key', None)
+            if not isinstance(_sk9, dict):
+                _sk9 = {}
+            _sk9 = {'AccountServerId': _sk9.get('AccountServerId')
+                                  or getattr(SESSION, 'account_id', 0) or 0,
+                    'MxToken': _sk9.get('MxToken') or ''}
+            _rid9 = pick_requestid(rec) or str(_uuid9.uuid4())
+            if not rec.get('requestid_source'):
+                rec['requestid_source'] = 'random'
+            obj = build_90004_management_data(_sk9, _t9, _rid9, load_90004_ops())
+            rec['gen_kind'] = 'management-90004-official'
             rec['fallback'] = 'generic-envelope'
+            rec['gen_90004_data_keys'] = len(obj.get('Data') or {})
+            rec['gen_90004_bytes'] = len(json.dumps(obj, ensure_ascii=False,
+                                                        separators=(',', ':')))
+            _r9 = data_key_report(obj)
+            rec['gen_90004_lists'] = dict((k, _r9[k]) for k in (
+                'Notices', 'Events', 'Issues', 'Banners',
+                'GachaProbabilityDisplay', 'GuidePopup'))
             return self._cn_send_envelope(name or 'Management_Data', obj, rec)
```

### 1.3 改动点三：`_cn_send_envelope` 的 outer requestid（L2128/2131）

```diff
     def _cn_send_envelope(self, proto_name, obj, rec):      # L2128
         import uuid as _uuid
-        rid = str(_uuid.uuid4())                             # L1965（旧）
+        rid = (obj.get('RequestId') if isinstance(obj, dict) else '') or str(_uuid.uuid4())  # 90004-PATCH: outer requestid = inner RequestId
```

> 这条对所有走 `_cn_send_envelope` 的协议生效，但只有**带 `RequestId` 的 obj** 行为才会变；
> 官方 109/109 条证据：`outer.requestid == inner.RequestId`。实测 e2e 里两者一致。

---

## 2. 三项检查（实际输出）

### 2.1 语法

```
$ python -c "import ast;ast.parse(open(r'..._p90004\account_auth_probe.py',encoding='utf-8').read());print('ast.parse OK')"
ast.parse OK                                    # 161 KB 基线版
$ python -c "import ast;ast.parse(open(r'..._p90004\_v222486\account_auth_probe.py',encoding='utf-8').read());print('ast.parse OK')"
ast.parse OK                                    # 222 KB 基线版
```

`check_patch_90004.py` 里还各跑了一次 `py_compile`：两个文件都是 `py_compile : PASS`。

### 2.2 幂等（`--apply` 复跑）

161 KB 基线版：

```
sha256[:16] = 16d4efcb2cb0b03c  167430 bytes
补丁动作: {"inlined": false, "branch": false, "outer_rid": "already", "already": true}
已经是打过补丁的版本（幂等，无改动）
  compile               : PASS
  markers               : 1/1
  legacy_16key          : gone
  branch_calls_helper   : True
  branch_has_data       : True
  branch_names_resolved : PASS
  inline_spec_check     : PASS
  inline_data_keys      : 9
  inline_inner_bytes    : 420
  inline_dirty_input    : PASS
  outer_requestid       : synced

sha before 2nd apply : 16d4efcb2cb0b03c380942c66c6a0887b270596ce04741b0dd1895a2c5108688
sha after  2nd apply : 16d4efcb2cb0b03c380942c66c6a0887b270596ce04741b0dd1895a2c5108688
same=True   backups after=1 (no new backup = True)
```

222 KB 基线版：`rc=0  sha_same=True  backups 1 -> 1`，`补丁动作: {"already": true}`。

### 2.3 无残留（`check_patch_90004.py`，161 KB 基线版实际输出；完整见 `_p90004/check.log`）

```
size : 167430 bytes / 4081 lines / sha256=16d4efcb2cb0b03c380942c66c6a0887b270596ce04741b0dd1895a2c5108688

[A] syntax
  ast.parse   : PASS
  py_compile  : PASS

[B] idempotency markers
  BEGIN marker: 1 (expect 1)
  END   marker: 1 (expect 1)

[C] 90004 branch block: chars [73011,74445) = FOUND
  OK   in-branch=0  "ContentLock"
  OK   in-branch=0  "StaticOpenConditions"  (全文件 2 处，均在其它协议分支/helper)
  OK   in-branch=0  "MissionProgressDBs"  (全文件 2 处，均在其它协议分支/helper)
  OK   in-branch=0  "EventMissionProgressDBDict"  (全文件 2 处，均在其它协议分支/helper)
  OK   in-branch=0  "BattlePassMissionProgressDBDict"  (全文件 2 处，均在其它协议分支/helper)
  OK   in-branch=0  "GachaProbabilityDisplay": False
  OK   in-branch=0  "GachaPeriodDisplay": False
  OK   in-branch=0  "RaidPeriodDisplay": False
  OK   in-branch=0  "GuidePopup": {}
  OK   in-branch=0  cn_inner.STATIC_OPEN_CONDITIONS
  OK   in-branch=0  rec['gen_kind'] = 'management-90004'
  OK   in-branch=0  build_min_response(90004

[C2] 90004 dispatch sites (whole file)
  `if num == 90004:`             : 1 (expect 1)
  `build_90004_management_data(` : 2 (expect 2 = def + call)
  `"Protocol": 90004` literal    : 1 (expect 1)
  branch calls helper            : True
  branch returns obj             : True

[C3] before/after 分支对照
  before: 23 行 / 顶层键 16 个 / Protocol 字面量 1 处
  after : 25 行 / Protocol 字面量 0 处 / 调 helper True

RESULT: PASS
```

（上面是节选：`[C4] all lines mentioning 90004` 的清单省略，全文在 `_p90004/check.log`。）

> 说明：`StaticOpenConditions` / `MissionProgressDBs` 这两个键全文件各有 2 处，都在
> **1019 legacy 分支**（L2108-2123）和几个 helper 里（L972 / L1033 / L1633），是历史代码、不是 90004 残留。
> 检查因此按「90004 分支块内」定性。全文件 `if num == 90004:` 只有 1 处，`"Protocol": 90004`
> 只有 1 处（在 helper 里），不存在第二套 90004 生成逻辑。

---

## 3. `90004_ops.json`（运营数据）

| 项 | 值 |
|---|---|
| 路径 | `work/ba/server/deploy/_p90004/90004_ops.json` |
| 大小 | **10,883 B** |
| sha256 | **`938ae90855b5fa5fa11342854f2e0f28e7130b466c303621151685efc06107fb`** |
| 编码 | UTF-8 **无 BOM**，`\n` 换行，中文原样（`ensure_ascii=False`） |
| 来源 | `report/_tmp/official_decoded_201/06_90004_api_management_data.response.json` → `inner.Data` |

条数（生成脚本自检输出）：

```
OK   Notices                  list  n=6   (expect 6)
OK   Events                   list  n=14  (expect 14)
OK   Issues                   list  n=0   (expect 0)
OK   Banners                  list  n=7   (expect 7)
OK   GachaProbabilityDisplay  list  n=12  (expect 12)
OK   GuidePopup               list  n=0   (expect 0)
OK   GachaPeriodDisplay       null
OK   RaidPeriodDisplay        null
OK   Survey                   null

[1] 逐字节保真（紧凑 JSON 对比）
  compact(extracted) == compact(official inner.Data) : True
[3] 写出
  bom    : no
  reread == official : True
```

「逐字节」的口径：抽出前后都用 `json.dumps(..., ensure_ascii=False, separators=(",",":"))` 比较，
**9,432 B 完全相同**（sha256 `abc695f8f61deb60a33595b9311832f988c9422d1e17f612e05fecdfe7b95270`）。
没有翻译、没有裁剪、没有改标点；10 份官方 90004 样本（`06/21/22/32/40/57/66/85/95/105`）的
Data 键集合与各列表条数**10/10 完全一致**（都是 6/14/0/7/12/0 + 3 个 null）。

再往下一层：把这 9 键喂给 `dto90004.build_90004_management_data()`，输出 Data 仍是同一串 9,432 B
（`selftest_90004.py`：`equal=True`、`inlined == dto`、`spec_check FAIL=0 WARN=2`）。
那 2 个 WARN 是官方样本自身形状（`Banners[5].BannerType` 缺、`Banners[6].LinkedLobbyBannerId` 缺，
都是 proto3 optional presence），不是我们的 bug —— 官方样本本身跑出来也是这 2 条。

---

## 4. `expected_90004.json`（部署后一键比对的基准）

| 项 | 值 |
|---|---|
| 路径 | `work/ba/server/deploy/_p90004/expected_90004.json` |
| 大小 | 11,408 B |
| sha256 | `a2d0fee9dcfb0e56cbdb09c063ce70757c15ac2df2102c2ab7542af4ab104e65` |
| 结构 | 官方 6 层：`Protocol / SessionKey / ServerTimeTicks / ServerNotification / RequestId / Data` |
| Data | = 上面那 9 键（与官方逐字节相同） |
| 占位 | `SessionKey={"AccountServerId":0,"MxToken":""}`、`ServerTimeTicks=0`、`RequestId="0000…0000"` |

`verify_90004.py` 对这 3 个字段只查形状/合理性（类型、`ServerTimeTicks` 与本机时钟差 < 10 min、
`RequestId` 是 uuid；`SessionKey` 为空只记 WARN），**不比值**；Data 全部比值和条数。

---

## 5. `verify_90004.py`（打一次 90004 比对键集合）

```
python3 verify_90004.py                       # 默认 http://127.0.0.1:9097/api/management/data
python3 verify_90004.py --port 9097 --dump raw_90004.json --raw body.bin
```

- 请求：自己按 `cn_cipher` 容器加密（`base64([u32][gzip(iv16|ct|key32)])`，`Hash=(90004<<32)|7`，
  与官方 06 请求的 `386564236509191` 同构），POST 到 `/api/management/data`；
- 响应：按 `cn_wire` 容器解（`base64(ct|key32)`，IV 固定 `JOSYdf8ys97uhFYS`），再 `json.loads(packet)`；
- **零第三方依赖**：AES-256-CBC 是内联的纯 Python 实现（摘自项目 `bapatch/tools/aes_pure.py`，
  已用 FIPS-197 测试向量 `69c4e0d8…` / `8ea2b7ca…` 验证），服务器不需要 `cryptography`；
- 检查 31 项：HTTP 200 / 顶层键集合（6）/ 键序 / `Protocol` / `SessionKey` 形状 / `ServerTimeTicks` /
  `ServerNotification` / `RequestId` / `outer == inner RequestId` / `Data` 是 dict / Data 键集合（9）与键序 /
  每个列表的**条数**、元素类型 / 3 个 null / Data 紧凑 JSON **逐字节** / 无旧 16 键残留 /
  `GachaProbabilityDisplay`+`GuidePopup` 必须是 list；
- 输出 `PASS/FAIL` 表格 + `FAIL` 明细（键名、条数、类型、具体值的 `act != exp`），退出码 `0/1/2`。

### 5.1 本地 e2e 实测（不是纸上谈兵）

用**未改动的线上桥 + 打补丁后的副本**在本机 127.0.0.1 起服务（`cryptography` 用测试 shim 顶替，
不联网），`launcher.py` 把 `P90004_OPS_PATHS` 指向 `90004_ops.json`，然后跑 `verify_90004.py`：

```
POST http://127.0.0.1:9097/api/management/data  (417 B, Hash=386564236509191)
  -> HTTP 200 / 14016 bytes / text/plain; charset=utf-8
解码: cn_wire  (plain 10072 B / inner 6 键)

[PASS] HTTP 200                                  14016 bytes
[PASS] 顶层键集合（6 键）                          got=6 ['Protocol','SessionKey','ServerTimeTicks','ServerNotification','RequestId','Data']
[PASS] Protocol == 90004                         got=90004 (int)
[PASS] SessionKey 形状                            {'AccountServerId': 0, 'MxToken': ''}
[WARN] SessionKey 非空                            AccountServerId=0 MxToken=空（bridge 尚未登录过账号，不影响结构）
[PASS] ServerTimeTicks 合理                       got=639306508605747980 (与本机 now 差 -0.1 s)
[PASS] outer requestid == inner RequestId        outer='942fd93a…' inner='942fd93a…'
[PASS] Data 键集合（9 键）                         got=9 [Notices, Events, Issues, Banners, GachaProbabilityDisplay, GuidePopup, GachaPeriodDisplay, RaidPeriodDisplay, Survey]
[PASS] Data.Notices 条数                          6 条（期望 6）
[PASS] Data.Events 条数                           14 条（期望 14）
[PASS] Data.Banners 条数                          7 条（期望 7）
[PASS] Data.GachaProbabilityDisplay 条数          12 条（期望 12）
[PASS] Data.GachaPeriodDisplay is null           got=None (null)
[PASS] Data.RaidPeriodDisplay is null            got=None (null)
[PASS] Data.Survey is null                       got=None (null)
[PASS] Data 逐字节（紧凑 JSON）                    9432 B (sha abc695f8f61deb60)
[PASS] 无旧 16 键多余额外键                        无
31 checks / FAIL=0 / WARN=1
RESULT: PASS
```

（节选：省略了键序、`Data.Issues/GuidePopup 条数`、`元素是 dict` 等 PASS 行；完整 31 行见日志。）

同样一条链路在 **222,486 B 那一版补丁产物**上也跑了一次：`FAIL=0 / WARN=1 / RESULT: PASS`
（日志 `_p90004/_e2e/log_verify_pass.txt`、`log_verify_pass_v222486.txt`）。

### 5.2 负向对照（证明这个脚本真能抓到旧结构）

拿**没打补丁**的快照起同一个 Handler，再跑验证（节选）：

```
-> HTTP 200 / 2092 bytes
解码: cn_wire  (plain 1532 B / inner 17 键)
[FAIL] 顶层键集合（6 键）  got=17 | 缺键 'SessionKey'; 缺键 'Data';
       多键 'MissionProgressDBs' ← 旧 16 键平铺残留; 多键 'EventMissionProgressDBDict' …
[FAIL] SessionKey 形状     got=None
[FAIL] Data 是 dict        got=None (null)
10 checks / FAIL=3
RESULT: FAIL
```

日志 `_p90004/_e2e/log_verify_old_bridge.txt`。

### 5.3 `preflight_90004.py`（上线前只读体检，防止版本对不上）

```
python3 preflight_90004.py --file /www/wwwroot/bapatch/tools/account_auth_probe.py
```

输出 size/sha256/md5 + 7 个锚点（`if num == 90004:`、分支以 `_cn_send_envelope` 收尾、
`def _cn_send_envelope`、函数内 `rid = str(_uuid.uuid4())`、`pick_requestid`、`SESSION = Session()`、
`import json`）+ marker 状态，判定 `READY` / `PATCHED` / `BLOCKED`（退出码 0/10/2）。
在 222,486 B 未打版上实测 `READY`，在打好的 167,430 B 版上实测 `PATCHED`。

---

## 6. 落地产物清单

| 文件 | 作用 | 大小 / sha256 |
|---|---|---|
| `_p90004/account_auth_probe.py` | 161,194 B 快照 → 打补丁后的副本 | 167,430 B / `16d4efcb2cb0b03c…` |
| `_p90004/account_auth_probe.py.bak.90004.20261119-020421` | 打补丁前备份（快照原件未动） | 161,194 B / `b571c72b…` |
| `_p90004/_v222486/account_auth_probe.py` | 222,486 B 基线 → 打补丁后的副本 | 228,722 B / `6756a5defb8e1c33…` |
| `_p90004/_v222486/account_auth_probe.py.bak.90004.*` | 上述基线打前备份 | 222,486 B / `ba322fae…` |
| `_p90004/90004_ops.json` | **运营数据（部署物）** | 10,883 B / `938ae908…` |
| `_p90004/expected_90004.json` | 预期响应（比对基准） | 11,408 B / `a2d0fee9…` |
| `_p90004/verify_90004.py` | 部署后验证（服务器上跑） | 纯标准库 |
| `_p90004/preflight_90004.py` | 上线前锚点体检 | 只读 |
| `_p90004/check_patch_90004.py` | 语法/幂等/无残留 三项静态检查 | 只读 |
| `_p90004/make_ops_90004.py` | ops + expected 生成器（可重跑） | 只读官方包 |
| `_p90004/selftest_90004.py` | dto/内联/官方三者逐字节一致性 | 只读 |
| `_p90004/90004_patch.full.diff` / `.branch.diff` | diff 存档 | — |
| `_p90004/_e2e/` | 本地 e2e 脚手架（shim/launcher/日志/dump） | **不部署** |

快照原件、`work/ba/srv_src`、服务器：**均未改**。

---

## 7. 部署步骤（给 srv-ops，可直接复制）

> 前提：只动 `/www/wwwroot/bapatch/`。**先拉真身、再打补丁、最后覆盖**；不要直接推本地打好的
> 文件（§0 的版本差距）。以下 `HOST` 用项目既有服务器 `root@<SERVER_IP>`。

### 7.0 本地打包（在 `C:\Users\su\Desktop\大肥鱼项目\BAServer` 下）

```powershell
$B = "work\ba\server\deploy\_p90004"
$STAGE = "$env:TEMP\ba90004_bundle"; Remove-Item $STAGE -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory $STAGE | Out-Null
Copy-Item work\ba\server\deploy\patch_90004.py, work\ba\server\deploy\dto90004.py, `
          work\ba\server\deploy\gen_common.py, work\ba\proto\official_spec.json, `
          work\ba\proto\spec_check.py, `
          "$B\preflight_90004.py", "$B\check_patch_90004.py", "$B\verify_90004.py", `
          "$B\expected_90004.json", "$B\90004_ops.json" $STAGE
Get-ChildItem $STAGE | Select-Object Name,Length
ssh root@<SERVER_IP> "mkdir -p /www/wwwroot/bapatch/_p90004_bundle"
scp $STAGE\* root@<SERVER_IP>:/www/wwwroot/bapatch/_p90004_bundle/
```

### 7.1 （可选但推荐）拉一份线上真身回本地，让我按真身重打

```powershell
scp root@<SERVER_IP>:/www/wwwroot/bapatch/tools/account_auth_probe.py `
    work\ba\server\deploy\_p90004\live_real.py
(Get-FileHash work\ba\server\deploy\_p90004\live_real.py -Algorithm SHA256).Hash.ToLower()
```
> 若 sha256 与 §0 两个基线都不同，把哈希发我，我重跑 `patch_90004.py` + `check` + e2e 后再给部署版。
> 不走这条路也行 —— 7.2 直接在服务器上对副本打补丁，效果一样（补丁自己会校验候选内容）。

### 7.2 服务器上：体检 → 在副本上打补丁 → 校验

```bash
set -e
cd /www/wwwroot/bapatch/_p90004_bundle
# 要求 python3 >= 3.7（gen_common.py / 这几个脚本都用了 from __future__ import annotations）
python3 -V

# 0) 体检（只读）。期望最后一行 VERDICT: READY
python3 preflight_90004.py --file /www/wwwroot/bapatch/tools/account_auth_probe.py

# 1) 把线上真身复制成工作副本（原件先不动）
cp -a /www/wwwroot/bapatch/tools/account_auth_probe.py ./live.work.py
sha256sum ./live.work.py

# 2) 打补丁（自动备份 live.work.py.bak.90004.<ts>，写入前先自检候选内容）
python3 patch_90004.py --src ./live.work.py --apply
python3 patch_90004.py --src ./live.work.py --verify | tail -5      # 期望 结果: PASS
python3 check_patch_90004.py --file ./live.work.py | tail -3        # 期望 RESULT: PASS
python3 -c "import ast;ast.parse(open('./live.work.py',encoding='utf-8').read());print('ast OK')"

# 3) 幂等复跑：sha 必须不变（应打印「已经是打过补丁的版本」）
sha256sum ./live.work.py
python3 patch_90004.py --src ./live.work.py --apply | head -4
sha256sum ./live.work.py
```

### 7.3 装 ops 数据（90004 的 9 键运营数据）

```bash
install -m 644 /www/wwwroot/bapatch/_p90004_bundle/90004_ops.json \
               /www/wwwroot/bapatch/_ba_state/90004_ops.json
sha256sum /www/wwwroot/bapatch/_ba_state/90004_ops.json
# 期望 938ae90855b5fa5fa11342854f2e0f28e7130b466c303621151685efc06107fb
```

> bridge 的 `P90004_OPS_PATHS[0]` 就是这个路径；读不到会退回「4 列表全空 + 3 null」的合法新号形状
> （结构对、但 Notices/Events/Banners/Gacha 条数会是 0，`verify_90004.py` 会 FAIL 提示）。

### 7.4 备份线上 → 覆盖 → 重启

```bash
set -e
TS=$(date +%Y%m%d-%H%M%S)
BAK=/www/wwwroot/bapatch/tools/account_auth_probe.py.bak.90004.$TS
cp -a /www/wwwroot/bapatch/tools/account_auth_probe.py "$BAK"
echo "backup: $BAK"; sha256sum "$BAK"

install -m 644 /www/wwwroot/bapatch/_p90004_bundle/live.work.py \
               /www/wwwroot/bapatch/tools/account_auth_probe.py
sha256sum /www/wwwroot/bapatch/tools/account_auth_probe.py

# 重启（线上现状：kill 旧 pid → cd tools + umask 007 + setsid nohup）
OLD=$(pgrep -f "account_auth_probe.py" | head -n1)
echo "old pid = $OLD"
kill "$OLD"
for i in $(seq 1 20); do kill -0 "$OLD" 2>/dev/null || break; sleep 0.5; done
cd /www/wwwroot/bapatch/tools
umask 007
setsid nohup python3 account_auth_probe.py >> /www/wwwroot/bapatch/logs/bridge_stdout.log 2>&1 &
sleep 2
ss -ltnp | grep 9097
pgrep -af account_auth_probe.py          # 实例数必须 = 1
```

### 7.5 验收（三条，缺一不可）

```bash
cd /www/wwwroot/bapatch/_p90004_bundle
python3 verify_90004.py --port 9097 --dump /tmp/90004_resp.json
# 期望：31 checks / FAIL=0，最后一行 RESULT: PASS

# 日志里要能看到新分支的记账
grep -c management-90004-official /www/wwwroot/bapatch/logs/api_all_requests.log
# 期望 >= 1（我们的探针会产生 1 条）；同一条日志里应有 "gen_90004_data_keys": 9
# 与 "gen_90004_lists": {"Notices":6,...}

# 客户端真机再打开一次公告/横幅页，确认不 NRE（页面有 6 条公告 / 7 个横幅 / 12 条概率公示）
```

> 若 `verify_90004.py` 全 PASS 但客户端仍不显示内容：看 `gen_90004_lists` 是否 6/14/0/7/12/0；
> 若全 0 说明 ops 文件没读到（路径/权限），不是结构问题。

### 7.6 回滚（30 秒）

```bash
set -e
# 自动取最近一份 90004 备份（7.4 打的那份）
BAK=$(ls -t /www/wwwroot/bapatch/tools/account_auth_probe.py.bak.90004.* | head -n1)
echo "rollback from: $BAK"
cp -a "$BAK" /www/wwwroot/bapatch/tools/account_auth_probe.py
sha256sum /www/wwwroot/bapatch/tools/account_auth_probe.py
OLD=$(pgrep -f "account_auth_probe.py" | head -n1); kill "$OLD"
for i in $(seq 1 20); do kill -0 "$OLD" 2>/dev/null || break; sleep 0.5; done
cd /www/wwwroot/bapatch/tools && umask 007
setsid nohup python3 account_auth_probe.py >> /www/wwwroot/bapatch/logs/bridge_stdout.log 2>&1 &
sleep 2; ss -ltnp | grep 9097
# 可选：rm -f /www/wwwroot/bapatch/_ba_state/90004_ops.json（旧代码不读它，留着无害）
```

回滚后 `verify_90004.py` 应该回到 FAIL（旧 16 键），这正是回滚成功的标志。

---

## 8. 边界与风险

1. **版本**：快照 161,194 B ≠ 线上 222,539 B（差 61 KB，见 §0）。补丁在两个基线上都验证过，
   但**上线前必须在线上副本上重新 `--apply`**，不要直接覆盖我打的 161 KB 产物。
2. **SessionKey**：`MxToken` 来自 `SESSION.session_key`；新号/未登录时是 `""`、`AccountServerId=0`。
   结构合法（官方字段 `string`/`int64`），`verify_90004.py` 给 WARN 不算 FAIL。客户端登录后自然有值。
3. **响应体积**：本地 e2e 是 14,016 B（官方 06 抓包 `resp_bytes`=14,124 B），差的 ~108 B 主要是
   `MxToken` 为空 + 外层 base64 分块；结构/键数/条数一致。
4. **`expected_90004.json` 是「装配好的运维状态」**：要求客户端能看到 6 公告 / 14 活动 / 7 横幅 /
   12 概率公示。这些是官方 2026-11-11 前后的排期数据，过期后需要换新的官方抓包重跑
   `make_ops_90004.py`（数据源一行改 `--src`）。
5. **旁路开关**：若线上 `cn_bridge_exp.txt` 非空（`decrypt+…`）或 `cn_bridge_mode.txt=forward`，
   90004 会被 path A / forward 直接代理走，**不经过**我们这条分支。部署后验收前先确认：
   `cat /www/wwwroot/bapatch/cn_bridge_exp.txt /www/wwwroot/bapatch/cn_bridge_mode.txt`（不存在 = 默认）。
6. **relay2 不会抢 90004**：`RL2_HANDLED` 里含 90004，`cn_relay_known.txt` 开着也不会转发。
7. **本报告所有哈希只对本仓库里的两份基线成立**；线上文件不同则哈希不同，以 7.2 输出为准。

---

## 9. 一句话结论

补丁在 161,194 B 快照副本和 222,486 B 近线上副本上都**打成功、语法通过、幂等、无残留**；
`90004_ops.json` = 10,883 B / `938ae908…`，**6/14/0/7/12/0 + 3 null**，与官方 `inner.Data`
逐字节相同；`verify_90004.py` 在本地 e2e 上 **31 项 FAIL=0**，对旧桥会正确报 FAIL。
上线只剩：拉线上真身 → `patch --apply` → 装 ops → 覆盖 + 重启 → `verify_90004.py` → PASS。
