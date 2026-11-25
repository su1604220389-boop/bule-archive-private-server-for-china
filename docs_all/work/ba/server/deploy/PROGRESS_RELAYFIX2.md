# PROGRESS_RELAYFIX2 — relay 转发时 SessionKey 没被覆盖（v1）

> 任务：写 `patch_relay_fix2.py`，修掉 relay 转发时 **SessionKey 没被覆盖** 的 bug。
> 范围：**纯本地**。全程没有 ssh / scp、没有连服务器；所有验证都在本地沙箱副本 +
> 127.0.0.1 假 Shittim 上完成。
> Python：`C:\Users\su\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe`（3.12.14）。
> 本机 MSYS2 的 python 未使用。

---

## 0. 结论

| 项 | 状态 | 证据 |
|---|---|---|
| 客户端带着错 `SessionKey`（`AccountServerId=10000000001`）被原样转给 Shittim | **已修**（两条路径 + 重试共 3 处入口） | 假 Shittim 实收 `AccountServerId=2`（桥铸的那把）；`rl_session_overwrote=True` / `rl_session_old_sid=10000000001`（G1/G2） |
| 反证：打补丁前的同一请求 | 复现线上根因 | 摘掉本补丁的基线把 `AccountServerId=10000000001` 原样转给 Shittim（G1b）——这就是 12 次 `Session expired or invalid`（`SessionKeyService.cs:153`）的来源 |
| `ensure_session` 返回 `None` | **不覆盖**、落回、不 500 | `fallthrough='ensure-session'`、Shittim 0 次、bridge 200 + 正常内层（G5） |
| 鉴权失败重试路径 | 也走无条件覆盖 | 首包 `Protocol:-1`，第二包收到的仍是桥铸的 `sk`，两次都 `AccountServerId=2`（G6，relay1 + relay2 各一遍） |
| 两个 relay 开关都关 | 与打补丁前**逐字节一致** | 冻结 time/datetime/uuid 后 295 B / 300 B / 304 B 三例全等（G7 + `_relayfix_replay` F7） |

- 沙箱最终状态（已回滚）：**136,894 B / sha256 `60f34664933656f460e5c4e74e4cacb19273bac213302b184f8ce12070e785ee`**，`BAPATCH-RLFIX2` 残留 0。
- 补丁产物（回滚前实测）：**141,066 B / sha256 `aefb38a8ad8c2a0a47d20e7a0d9995024f7d532f119de491e74125d076642b65`**（净增 +4,172 B）。
- 本补丁 **不新增开关**：`cn_relay_unknown.txt` / `cn_relay_known.txt` 打开时自动生效；都关时走不到改动的代码。
- 新增日志字段：`rl_session_overwrote` / `rl_session_old_sid`（relay v1 路径与它触发的重试）、
  `rl2_session_overwrote` / `rl2_session_old_sid`（relay v2 路径与它触发的重试），
  并把既有 `relay_session_*` / `relay2_session_*` 三件套的语义更新为「已用桥铸的 sk」
  （`*_session_injected` 在客户端自带 Key 时也会是 True —— 这正是本补丁要表达的事实）。

---

## 1. 环境与基线（硬闸）

工作目录：`C:\Users\su\Desktop\大肥鱼项目\BAServer`
脚本目录：`work\ba\server\deploy`
沙箱目标：`work\ba\server\deploy\_sandbox\p3\account_auth_probe.py`

沙箱进来时是 128,309 B（= relay + relay2 已打），要先退回 pristine 再按顺序重建。
回退链路（真实输出，只列指纹）：

```text
python patch_relay2.py --src _sandbox\p3\account_auth_probe.py --rollback
  → 115,911 B / 377176809ff25949a45e54224a274ad2b701e02c2d6d8a787a4a6eb16e815a07
python patch_relay.py  --src _sandbox\p3\account_auth_probe.py --rollback
  → 103,900 B / 563c1942289968e3f402c52eb89982cba75f9753ba85d13f6cca0be244ffc5c8
```

正向重建（任务给的三步，**逐条实跑**）：

```text
python patch_relay.py     --src _sandbox\p3\account_auth_probe.py --apply --switches 1
  → 115,911 B / 377176809ff25949…            （自检 全绿）
python patch_relay2.py    --src _sandbox\p3\account_auth_probe.py --apply --switches 1
  → 128,309 B / e5fb03b87433741e…            （自检 全绿）
python patch_relay_fix.py --src _sandbox\p3\account_auth_probe.py --apply
  → 136,894 B / 60f34664933656f460e5c4e74e4cacb19273bac213302b184f8ce12070e785ee
```

**硬闸通过**：136,894 B / `60f34664…`，与任务要求逐字节一致。

基线指纹（本补丁硬闸）：

```text
136,894 B
60f34664933656f460e5c4e74e4cacb19273bac213302b184f8ce12070e785ee
```

---

## 2. 问题：客户端回传的 SessionKey 把桥账号服务号带给了 Shittim

### 2.1 现象与根因

补丁窗口里仍有 **12 次** `Rejected request with invalid session: Session expired or invalid`
（Shittim `SessionKeyService.cs:153`）。

根因链条：

1. 桥自己的账号服务把 `SessionKey.AccountServerId` 改成 `10000000001`（= 桥账号服务号）；
2. 客户端把这个 SessionKey **原样回传**，于是 relay 解出来的请求里 `SessionKey` 存在，
   值是 `{"AccountServerId":10000000001,"MxToken":"…"}`；
3. relay 用的是 **「缺了才注入」**（基线第 2804 行 / 3029 行）：

   ```python
   injected = not req.get('SessionKey')
   if injected:
       req['SessionKey'] = sk
   rec['relay_session_injected'] = bool(injected)
   ```

4. 因为客户端带了 SessionKey，注入被跳过 ⇒ Shittim 拿到一个**不存在的账号 id** ⇒ 拒。
5. 拒了以后虽然会重试一次（`patch_relay_fix` 的 F4/F5 那套），但重试前清缓存、重新铸 Key
   之后**第一次请求的 `req` 还是带着错 Key** —— 关键是重试自己也只在「走到重试分支」时
   才补发，语义上仍是「有条件」。真正要的是：**只要转发，就用桥铸的 Key**。

### 2.2 改法

新增一块运行时（`BAPATCH-RLFIX2`），三条入口共用同一个函数：

```python
def _rlfix2_force_session(rec, req, sk, family=None, log=None):
    if not isinstance(req, dict):
        return False
    if family is None or log is None:
        family, log = _rlfix2_session_family(rec)      # relay -> rl / relay2 -> rl2
    if sk is None:                                      # ← sk 为 None 就不覆盖（落回）
        rec[family + '_session_injected'] = False
        return False
    old = req.get('SessionKey')
    req['SessionKey'] = sk                              # ← 无条件覆盖
    rec[family + '_session_injected'] = True
    rec[family + '_session_overwrote'] = (old is not None and old != sk)
    rec[family + '_session_old_sid'] = old.get('AccountServerId') if isinstance(old, dict) else old
    rec[log + '_session_overwrote'] = rec[family + '_session_overwrote']
    rec[log + '_session_old_sid'] = rec[family + '_session_old_sid']
    return True
```

三条入口：

| 入口 | 位置（基线行号） | 改动 |
|---|---|---|
| relay v1 转发 | `_rl_relay_once` 第 2966 行 | 「缺了才注入」→ `_rlfix2_force_session(rec, req, sk, 'relay', 'rl')` |
| relay v2 转发 | `_rl2_relay_once` 第 3210 行 | 同上，家族 `relay2` / 前缀 `rl2` |
| 鉴权失败重试 | `_rl_retry_on_auth_fail` 第 2792 / 2811 行 | 签名补 `family/log`，内部 `req['SessionKey'] = sk` → `_rlfix2_force_session(rec, req, sk, family, log)` |

`sk is None` 的处理：`_rl_relay_once` / `_rl2_relay_once` 里原本就有
`if sk is None: rec['relay_fallthrough'] = 'ensure-session'; return None`，
本补丁保留它（并在 helper 里再守一次），**不覆盖、直接落回**，行为与打补丁前一致。

### 2.3 改动形态（可整段撤销）

1. 在 `patch_relay_fix` 的 RLFIX 块**尾部**（`# <<< BAPATCH-RLFIX v1 END <<<` 之前）插入
   `BAPATCH-RLFIX2` 块（81 行 / 3,043 B）。
   为什么嵌在里面：① 它修的就是 RLFIX 块里 `_rl_retry_on_auth_fail` 的那一行，同层相邻才看得懂；
   ② 层序天然 **LIFO** —— `patch_relay_fix.py` 整层摘块会把本补丁一起摘掉，
   `_relayfix_replay.py` 的 F0「摘掉 RLFIX 后逐字节 == 128,309 B 基线」因此仍然成立，
   不会留下半个补丁。
2. `_rl_relay_once`：2.2 表格第 1 行（257 B → 294 B）。
3. `_rl2_relay_once`：第 2 行（259 B → 300 B）。
4. `_rl_retry_on_auth_fail`：第 3 行（74 B → 124 B、59 B → 152 B）。

> **管线顺序**：`rollback → patch_relay → patch_relay2 → patch_relay_fix → patch_relay_fix2`。
> 打完 fix2 以后**不要**再单独重跑前四个的 `--apply` —— 它们会把各自载荷整块换回旧版本。

### 2.4 反证（同一请求，前后对照）

| 装置 | 客户端带的 SessionKey | 假 Shittim 实收 | 结论 |
|---|---|---|---|
| 摘掉本补丁（136,894 B） | `{"AccountServerId":10000000001,"MxToken":"bogus"}` | `AccountServerId=10000000001` | 复现线上 12 次被拒 |
| 打上本补丁（141,066 B） | 同上 | `AccountServerId=2`（`MxToken` = 第 1 次 CheckNexon 铸的） | 已修 |

---

## 3. 开关与日志

- **不新增开关**。`cn_relay_unknown.txt` 打开 → relay v1 路径生效；
  `cn_relay_known.txt` 打开 → relay v2 路径生效；两个都关 → `rl_route` / `rl2_route`
  在 `switch-off` 处就返回，改动的代码根本进不去（G7 用冻结时间 + 冻结 uuid 做了逐字节比对）。
- helper 块**不碰任何文件、不读开关**（块内没有 `open(` / `switch` 调用，只有 docstring 提到开关文件名）。
- 新增字段（relay1 / relay2 各一套，前缀区分）：
  - `rl_session_overwrote` / `rl_session_old_sid`
  - `rl2_session_overwrote` / `rl2_session_old_sid`
  - 同时写既有的 `relay_session_injected` / `relay_session_overwrote` / `relay_session_old_sid`
    与 `relay2_session_*` 三件套（名字不变，语义更新为「已用桥铸的 sk」）。

---

## 4. 六步真实输出

### 第 1 步：`--verify`（基线，硬闸）

```text
python patch_relay_fix2.py --src _sandbox\p3\account_auth_probe.py --verify
src     : _sandbox\p3\account_auth_probe.py
          136894 字节 / 3282 行 / sha256 60f34664…
patched : 否
  PASS  基线大小 == 136894（实测 136894）
  PASS  基线 sha256 == 60f34664…（实测 60f34664…）
  PASS  基线里零 BAPATCH-RLFIX2 残留（实测 0 处）
  PASS  P3 层 4 个块全在（BEGIN/END 各 1）
  PASS  SIMPLE 层 3 个块全在（BEGIN/END 各 1）
  PASS  RELAY 层 2 个块全在（BEGIN/END 各 1）
  PASS  RELAY2 层 2 个块全在（BEGIN/END 各 1）
  PASS  RLFIX 块 BEGIN/END 各 1（实测 1 / 1）
  PASS  RLFIX 块正文（摘掉本补丁替换后）sha256 == 头行记录（ccdc3780246a9399 / ccdc3780246a9399）
  PASS  RLFIX 的 5 个函数各 1 处定义
  PASS  rl_request_json 尾部仍走 _rl_build_request（1 处）
  PASS  两条 relay 路径的鉴权失败重试都在（2 处）
  PASS  session-retry-failed 落回分支 2 处（实测 2）
  PASS  RLFIX 的 6 处行内标记齐备（实测 6）
  INFO  前五层取证合计：P3×4 / SIMPLE×3 / RELAY×2 / RELAY2×2 / RLFIX×7
  PASS  helper 插入锚点（RLFIX END 行）唯一 1 次（第 2833 行）
  PASS  relay1-session-overwrite: 原文恰好 1 处、新文 0 处（可安全替换）
  PASS  relay2-session-overwrite: 原文恰好 1 处、新文 0 处（可安全替换）
  PASS  retry-session-overwrite: 原文恰好 1 处、新文 0 处（可安全替换）
  PASS  retry-session-assign: 原文恰好 1 处、新文 0 处（可安全替换）
  PASS  基线确实是「缺了才注入」（两条路径各 1 处 bool(injected)）
  PASS  基线里 _rl_retry_on_auth_fail 还没有 family/log 形参
结论: PASS        （22 PASS / 0 FAIL，exit 0）
```

RLFIX 层的 `N = 7`（BEGIN/END、正文 sha、5 个函数、`_rl_build_request` 尾部、
`_rl_is_auth_fail` 2 处、`session-retry-failed` 2 处、6 处行内标记）。
把同一份 `--verify` 打到 128,309 B 的文件上会 FAIL（大小 / sha / RLFIX 块 0/0 / 5 个函数缺失…），
说明它不是只看大小的橡皮章。

### 第 2 步：`--dry-run`（mtime 不变）

```text
== 改动动作 ==
  RLFIX2: 在原文件第 2833 行之前插入 helper 块（81 行 / 3043 B；即 RLFIX 块尾部）
  relay1-session-overwrite: 替换 1 处（257 B -> 294 B）
  relay2-session-overwrite: 替换 1 处（259 B -> 300 B）
  retry-session-overwrite: 替换 1 处（74 B -> 124 B）
  retry-session-assign: 替换 1 处（59 B -> 152 B）
补丁后大小: 141066 B（基线 136894 B，净增 +4172 B）
--dry-run：没有写文件。mtime/size 未变: True（(1794854390373540800, 136894)）
```

### 第 3 步：`--apply`

```text
已写入。备份: …account_auth_probe.py.rlf2.bak.20261117-…
  写入后 141066 字节 / sha256 aefb38a8ad8c2a0a47d20e7a0d9995024f7d532f119de491e74125d076642b65
自检: 全绿        （39 PASS / 0 FAIL，exit 0）
```

幂等：再跑一次 `--apply`，每个替换都报「已是补丁后形态（跳过）」，文件 sha256 **不变**
（`aefb38a8…` → `aefb38a8…`）。
基线不对时拒绝：拿 128,309 B 的文件跑 `--apply` → 打印实测/期望指纹并 exit 1，**不写文件**。

### 第 4 步：`py_compile`

```text
python -m py_compile _sandbox\p3\account_auth_probe.py   → exit 0
```

（补丁脚本内部还有 `compile()` 语法闸 + 打完自检 + 内嵌 helper 的单元自测。）

### 第 5 步：回归 + 新功能重放（目标 = 141,066 B 产物）

| 装置 | 结果 | 说明 |
|---|---|---|
| `_p3_replay.py` | **22 项 / 0 FAIL** | P3 层未受影响 |
| `_relayfix_replay.py` | **39 项 / 0 FAIL** | RLFIX 层未受影响；F0 见 §7.1 |
| `_relay_replay.py` | 44 项 / **1 FAIL（R0）** | 已知夹具问题（见 §7.2） |
| `_relay2_replay.py` | 61 项 / **1 FAIL（S0）** | 已知夹具问题（见 §7.3） |
| `_relayfix2_replay.py`（新增） | **27 项 / 0 FAIL** | 本补丁取证（见 §6） |

### 第 6 步：`--rollback`（最终态）

```text
python patch_relay_fix2.py --src _sandbox\p3\account_auth_probe.py --rollback
  还原后 136894 字节 / sha256 60f34664933656f460e5c4e74e4cacb19273bac213302b184f8ce12070e785ee
  与基线 136894 B / 60f34664… 逐字节一致
  残留 BAPATCH-RLFIX2 标记: 无（干净）        exit 0
```

回滚有两条路径，**都实测过、都是 136,894 / 60f34664 + 零残留**：
`--rollback` 优先用 `.rlf2.bak.*` 里 sha 命中基线的备份还原（本次走的就是这条）；
没有可用备份时走 `build_removed()`（逆序还原 4 处替换 + 摘掉 helper 块），
用一个不带备份的临时副本实测过：

```text
  retry-session-assign: 还原 1 处（152 B -> 59 B）
  retry-session-overwrite: 还原 1 处（124 B -> 74 B）
  relay2-session-overwrite: 还原 1 处（300 B -> 259 B）
  relay1-session-overwrite: 还原 1 处（294 B -> 257 B）
  RLFIX2: 摘掉 helper 块（3043 B）
  还原后 136894 字节 / sha256 60f34664…   残留: 无（干净）
```

回滚后顺手验了上一层完好：`patch_relay_fix.py --verify` 在 136,894 B 上 **结论 PASS**
（包含「helper 块正文逐字节 == RLFIX_HELPER_SRC」「摘掉本补丁后逐字节 == 128,309 B」），
说明 fix2 没在 RLFIX 层留下任何痕迹。

---

## 5. 删除/新增的「可核对事实」清单

- 4 处替换：原文唯一 1 处、新文 0 处（`--verify` 断言）；
- helper 块：81 行 / 3,043 B，正文 sha256 `9391eb244263eb91…`，头行记的 sha256 与真源一致；
- 三条调用点：`_rlfix2_force_session(...)` 恰好 3 行（relay 1 / relay2 1 / 重试 1）；
- 「缺了才注入」的旧语句（`injected = not req.get('SessionKey')`）在补丁后为 **0 处**；
- `sk is None` 时不覆盖：helper 里 `if sk is None: ... return False`，且两条路径原有的
  `ensure-session` 落回分支保留（G5 实证）。

---

## 6. 新功能取证（`_relayfix2_replay.py`，27 项全绿）

装置：复用 `_relay2_replay.py` 的 `cn_cipher` / `cn_wire` / `cn_nick` 替身与 rig 加载器，
外加本文件的假 Shittim（`127.0.0.1` 随机端口，`normal` / `auth_once` 两种剧本）。
四份装置：修后（开关开）、修后（开关关）、摘掉本补丁的基线（开关关）、
摘掉本补丁的基线（开关开，用于反证）。**四份装置的名字表完全一致**，避免装置差异冒充补丁差异。

| 组 | 断言 |
|---|---|
| G0 | 摘块后逐字节 == 136,894 B / `60f34664…`；`BAPATCH-RLFIX2` BEGIN/END 各 1；前四层 11 个块全在；第五层 RLFIX 在；RLFIX2 块嵌在 RLFIX 块尾部（LIFO） |
| G1 | 客户端带错 Key → Shittim 实收 `AccountServerId=2` / `MxToken`=第 1 次铸的；`rl_session_overwrote=True` / `rl_session_old_sid=10000000001`；既有 `relay_session_*` 三件套同步；bridge 仍 200 |
| G1b | 反证：摘掉本补丁的基线把 `10000000001` 原样转给 Shittim |
| G2 | relay2 路径同 G1（`rl2_session_*` + `relay2_session_*`），且不误写 `rl_session_*` |
| G3 | 请求里没有 SessionKey → 照常注入，`rl_session_overwrote=False` / `old_sid=None` |
| G4 | 请求里的 SessionKey 本来就 == sk → 覆盖（`injected=True`）但 `overwrote=False`；CheckNexon 0 次（走缓存） |
| G5 | `ensure_session` 回 None → 不覆盖、不算 overwrote、`fallthrough='ensure-session'`、Shittim 0 次、bridge 200 + 正常内层 |
| G6 | 重试路径：relay1 / relay2 各一遍，首包 `Protocol:-1` → 第二次转发收到的仍是桥铸的 `sk`；`old_sid=2`（= 上一把桥铸的）；转发恰好 2 次 |
| G7 | 两个开关都关：未知 8006 + 错 Key / 已知 8000 / 已知 19004 三例响应与基线**逐字节一致**，Shittim 0 次，零新字段 |
| G8 | 访问日志字段齐备（`rl_session_overwrote` / `rl_session_old_sid` / `relay_session_injected` / `relay_session_overwrote` / `relay_session_old_sid`） |
| G9 | 全程只连 `127.0.0.1` 的假 Shittim |

---

## 7. 回归逐条说明

### 7.1 `_relayfix_replay.py`（39/39）——F0 的 LIFO 适配（唯一一处既有测试改动）

F0 原本是：`P.build_removed(src_text)` 后必须逐字节等于 128,309 B。本补丁在两条 relay 载荷里
各有 1 处替换（不在 RLFIX 块内），所以只摘 RLFIX 层会剩 128,563 B（`+254 B`）。
改法是**加严**而不是放宽：先按 LIFO 把更晚的层（`BAPATCH-RLFIX2`）摘掉，再摘 RLFIX 层，
**仍然要求逐字节 == 128,309 B / `e5fb03b8…`**，并在日志里写一行
`INFO F0 文件上还叠着更晚的层 'BAPATCH-RLFIX2' -> 先按 LIFO 摘掉再比 RLFIX 基线`。
`_relayfix_replay.py` 的功能断言（F1–F9）完全没动，全部跑在完整产物（含 fix2）上。
改完以后在**纯 RLFIX 目标**（136,894 B，没打 fix2）上重跑仍是 **39 项 / 0 FAIL**，
说明这个适配对「没有更新的层」的文件是零影响的。

### 7.2 `_relay_replay.py`：44 项 / 1 FAIL（R0）

`R0` 断言「摘掉 PAYLOAD+HOOK-A 后 == 103,900 B」。目标文件是叠了 5 层的产物，
摘掉 relay v1 层后实测 117,458 B（还含 relay2 / rlf / fix2 三层）——这是**夹具假设**
（它假设目标是「patch_3 + relay v1 单层」）问题，与本补丁无关。其余 43 项全绿。

### 7.3 `_relay2_replay.py`：61 项 / 1 FAIL（S0）

同理：`S0` 假设「摘掉 PAYLOAD+HOOK 后 == 115,911 B」，实测 127,508 B（还含 rlf / fix2）。
其余 60 项全绿。

### 7.4 `_p3_replay.py`：22/22 全过

P3（`NetworkTime_Sync` 那一层）完全没被碰到：容器大小 620 B、键序、tick 红线、
异常落回 448 B、开关缺失/置 0 的行为全部不变。

---

## 8. 回滚与运维注意

1. **顺序**：`rollback → patch_relay → patch_relay2 → patch_relay_fix → patch_relay_fix2`。
   反向卸载必须 `patch_relay_fix2.py --rollback` 先行；fix2 在 RLFIX 块里改过 2 行，
   先摘 RLFIX 会把本次修复一起带走（LIFO —— 文件不会坏，但修复会消失）。
2. 打完 fix2 后**不要**再单独跑前四个脚本的 `--apply`：它们会整块换回自己那版的载荷。
3. `patch_relay_fix.py` 的 `count_marks()` 数的是子串 `BAPATCH-RLFIX`，而本补丁的标记是
   `BAPATCH-RLFIX2` —— 在打完 fix2 的文件上它的「零残留」类检查会偏大。这是已知的、
   无害的字符串包含关系；本补丁自己的残留判定只数 `BAPATCH-RLFIX2`。
4. 上线前要动的只有 bridge 文件本身；开关沿用 `cn_relay_unknown.txt` / `cn_relay_known.txt`，
   本补丁不新增任何开关文件。
5. 观测量：`rl_session_overwrote=True` + `rl_session_old_sid=10000000001`
   （或 `rl2_*` 那套）就是「客户端回传了桥账号服务号、已被覆盖」的直接证据；
   如果 `rl_session_old_sid` 一直是 `null`，说明客户端这次没带 SessionKey。

---

## 9. 交付物

| 文件 | 字节 | sha256 |
|---|---|---|
| `work\ba\server\deploy\patch_relay_fix2.py` | 43,458 | `f7a31adb8501989c969c77e8bc81e2dbf3199aa389d4abf90f9bea8a1eae2fec` |
| `work\ba\server\deploy\_relayfix2_replay.py` | 27,483 | `6a5e74aa92fdd7fb0cf6d700033c5e63d15c0b49de359df634ed93b2e7a27bcd` |
| `work\ba\server\deploy\PROGRESS_RELAYFIX2.md` | 22,0xx | 自指：写完后的指纹见回报消息 |
| （改）`work\ba\server\deploy\_relayfix_replay.py` | 23,778 → 25,210 | `eec4b2d110af22179664891141cb91e6eab280827e0bfc15161fc321a4d28ce0`（F0 加 LIFO 适配，见 §7.1） |

产物：`_sandbox\p3\account_auth_probe.py` = 141,066 B / `aefb38a8…`（回滚前），
136,894 B / `60f34664…`（当前，已回滚）。

中间日志（不属于交付物，保留在 `_scratch\rlf2\`）：`final_apply.log` / `final_verify.log` /
`final_p3_replay.log` / `final_relayfix_replay.log` / `final_relay_replay.log` /
`final_relay2_replay.log` / `final_relayfix2_replay.log` / `final_rollback.log`。

---

## 10. 已知边界

- 假 Shittim 的判据是「`SessionKey.AccountServerId` 是不是桥铸的那个」，没有真的复刻
  Shittim 的 `SessionKeyService` 校验；线上的 12 次拒绝只作为**根因叙述**，不是本机复现。
- `_rlfix2_session_family()` 的兜底是「带 `timeout` 的调用 = relay2」。当前代码里
  relay2 是唯一带 `timeout=RL2_TIMEOUT` 调 `post_gateway` 的路径；如果以后 relay1 也加
  timeout，需要在调用点显式传 `family` / `log`（本轮不传是为了不动 RLFIX 的 6 处替换点）。
- 两条 relay 路径的 `post_gateway` 仍是同步阻塞调用（与原实现一致），本补丁不碰超时/重试策略。
- 本补丁只修「转发时用哪把 Key」，不修桥账号服务为什么把 `AccountServerId` 改成
  `10000000001`（那是账号服务的独立问题，与本 bug 解耦）。
