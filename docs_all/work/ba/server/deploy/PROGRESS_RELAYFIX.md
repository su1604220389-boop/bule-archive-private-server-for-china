# PROGRESS_RELAYFIX — relay 上线三问题修复（v1）

> 任务：写 `patch_relay_fix.py`，修掉上线后暴露的三个真问题。
> 范围：**纯本地**。全程没有 ssh / scp、没有连服务器、没有连远端；所有验证都在本机沙箱副本 + 127.0.0.1 假 Shittim 上完成。
> Python：`C:\Users\su\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe`（3.12.14）。本机 MSYS2 的 python 未使用。

---

## 0. 结论

| 问题 | 状态 | 证据 |
|---|---|---|
| ① 协议号被拼错（190044 / 900111 / 350033 / 160000） | **已修**，通用实现 | 线上 4 个协议 × 两条 relay 路径 × 正常/畸形 fragment = 16/16 重建正确；另有 90,000 个 5 位协议号 × 11 种 fragment 共 990,000 例全过 |
| ② `Session expired or invalid` 被拒后不重试 | **已修**，只重试一次 | 首包 `{"Protocol":-1,"ErrorCode":3}`、第二包正常 -> `rl_session_retry=True / ok=True`，转发恰好 2 次；两次都失败 -> 落回、不 500 |
| ③ `EncryptedUID` 写死假值 | **本轮只登记，不修** | 硬编码在 `cn_inner27.py:98`，不在本补丁文件范围；需按真实 UID 派生，属独立任务（见 §4） |

- 沙箱最终状态（已回滚）：**128,309 B / sha256 `e5fb03b87433741ed61ad6f7cc010707193fbd46d7c2086608fb0c11d66f5581`**，`BAPATCH-RLFIX` 残留 0。
- 本补丁**不新增开关**：`cn_relay_unknown.txt` / `cn_relay_known.txt` 打开时自动生效；两个都关时响应与「摘掉本补丁的基线」逐字节一致（F7，冻结 time/datetime/uuid 后 295 B / 300 B / 304 B 三例全等）。
- 新增访问日志字段：`rl_req_build` / `rl_req_frag_head` / `rl_req_build_err` / `rl_session_retry` / `rl_session_retry_ok`，外加两条 relay 路径都写 `req_frag_head`。

---

## 1. 环境与基线

工作目录：`C:\Users\su\Desktop\大肥鱼项目\BAServer`
脚本目录：`work\ba\server\deploy`
沙箱目标：`work\ba\server\deploy\_sandbox\p3\account_auth_probe.py`

按任务给的两步重建线上现状（**实际执行**，两步都是幂等替换，写回字节不变）：

```text
python patch_relay.py  --src _sandbox\p3\account_auth_probe.py --apply --switches 1
src     : _sandbox\p3\account_auth_probe.py
          128309 字节 / 3082 行 / sha256 e5fb03b87433741ed61ad6f7cc010707193fbd46d7c2086608fb0c11d66f5581
patched : 是
  PAYLOAD: 替换已有块（旧 270 行 -> 新 270 行，幂等）
  HOOK-A: 替换已有块（旧 15 行 -> 新 15 行，幂等）
  写入后 128309 字节 / sha256 e5fb03b87433741ed61ad6f7cc010707193fbd46d7c2086608fb0c11d66f5581
自检: 有 FAIL（见上）
```

```text
python patch_relay2.py --src _sandbox\p3\account_auth_probe.py --apply --switches 1
src     : _sandbox\p3\account_auth_probe.py
          128309 字节 / 3082 行 / sha256 e5fb03b87433741ed61ad6f7cc010707193fbd46d7c2086608fb0c11d66f5581
patched : 是
  PAYLOAD: 替换已有块（旧 234 行 -> 新 234 行，幂等）
  HOOK: 替换已有块（旧 17 行 -> 新 17 行，幂等）
  写入后 128309 字节 / sha256 e5fb03b87433741ed61ad6f7cc010707193fbd46d7c2086608fb0c11d66f5581
自检: 全绿
```

说明：`patch_relay.py` 的自检在「relay2 已打」的目标上本来就有 2 条 FAIL（摘掉 relay1 后应为 103,900 B / 零 RELAY 残留，实测 116,298 B / 有残留）——它的 R0 夹具假设目标是 patch_3 + patch_relay 单独一层。文件写入的字节是幂等的，128,309 / e5fb03b8 未变。这是既有夹具过期，与本补丁无关（§7 同样解释）。

基线指纹（本补丁硬闸）：

```text
128,309 B
e5fb03b87433741ed61ad6f7cc010707193fbd46d7c2086608fb0c11d66f5581
```

---

## 2. 问题 ①：协议号被拼错

### 2.1 现象与根因

Shittim 日志收到 `190044 / 900111 / 350033 / 160000`（应为 `19004 / 90011 / 35003 / 16000`），全部报
`doesn't have corresponding type registered`。

根因在 relay v1 的请求重建：

```python
obj = _rljson.loads('{"Protocol":%d' % int(num) + text)   # 见基线第 2708 行
```

它假设 `text`（即 `decoded['fragment']`）一定以 `,` 开头。线上 4 个样本全是 5 位协议号，而 fragment 开头残留了协议号的**最后一位数字**，于是：

```text
'{"Protocol":19004' + '4,"Hash":...,"IsTest":false}'  ->  Protocol = 190044
'{"Protocol":90011' + '1,"Hash":...}'                 ->  Protocol = 900111
'{"Protocol":35003' + '3,"Hash":...}'                 ->  Protocol = 350033
'{"Protocol":16000' + '0,"Hash":...}'                 ->  Protocol = 160000
```

`Hash` 本身是完整的（`Hash >> 32 == num` 仍然成立），坏的只是拼接。

### 2.2 改法（通用，不只治这 4 个）

新增 `_rl_build_request(num, text, rec=None)`，按下列候选顺序逐个尝试，**返回第一个**
`json.loads` 成功 + 解析出的 `Protocol == num` + 非空 dict 的结果；**全部不成立 -> `None`**（放弃转发、落回原逻辑，不猜）：

| 候选号 | 规则 |
|---|---|
| 1 | `'{"Protocol":%d' % num + text`（原逻辑原样保留） |
| 2 | `text[0]` 是数字：从 `text` 第一个逗号处截断后再拼 |
| 3–10 | 依次去掉 `text` 开头 1..8 个字符，再从第一个逗号处截断后拼 |
| 11 | `text` 以 `}` / `,` 之外的可疑字符开头：同样按「截到第一个逗号」处理 |

实现位置与调用：

- `patch_relay_fix.py` 的 `RLFIX_HELPER_SRC` 内嵌 `_rl_build_request` / `_rl_frag_candidates`，整块插在 `rl_request_json` 定义之前；
- `rl_request_json` 尾部原来那 5 行 `try: _rljson.loads(...)` 改成：

  ```python
  # BAPATCH-RLFIX: 统一走 _rl_build_request（候选顺序 + Protocol 硬校验；全失败 -> None）
  return _rl_build_request(num, text, rec)
  ```

- relay v1（`_rl_relay_once`）与 relay2（`_rl2_relay_once`）都复用同一个 `rl_request_json`，所以两条路径一起修好。

日志（写进 `rec`，随访问日志落盘）：

| 字段 | 含义 |
|---|---|
| `rl_req_build` | 用了第几个候选；`0` = 全部候选失败 |
| `rl_req_frag_head` | `fragment.strip()[:200]` |
| `rl_req_build_err` | 失败原因摘要（最多前 4 条候选错误 + 总尝试数，截断 300 字符） |
| `req_frag_head` | `fragment.strip()[:300]`；**两条 relay 路径都写**，上层已写则不覆盖（replay 用 `UPSTREAM-SENTINEL` 验证过） |

### 2.3 锚点与行号

基线（128,309 B，行号来自 `--dry-run` 的「将要改动的位置」）：

| 改动 | 基线起始行 | 补丁后新代码行 |
|---|---|---|
| 插入 RLFIX helper 块（161 行 / 5,623 字符 / 6,411 B） | 第 2673 行之前（`rl_request_json` 定义前） | 2673–2833 |
| `req-frag-head`（`rl_request_json` 内补 `req_frag_head`） | 2691 | 2855 |
| `req-tail`（改调 `_rl_build_request`） | 2707 | 2871 |
| `relay1-frag-head`（`_rl_relay_once`） | 2777 | 2938 |
| `relay1-session-retry`（`_rl_relay_once`） | 2822 | 2993 |
| `relay2-frag-head`（`_rl2_relay_once`） | 3002 | 3182 |
| `relay2-session-retry`（`_rl2_relay_once`） | 3051 | 3243 |

补丁后文件：3,282 行 / 136,894 B（+8,585 B）。`rl_request_json` 定义行 2673 -> 2834。
补丁后 helper 块 sha256：`ccdc3780246a93998bced42cf28d7473ed9a277bf47feda98450617e21217986`。

### 2.4 「对所有 5 位协议号都成立」的证据

用最终 helper（`patch_relay_fix.py` 里的 `RLFIX_HELPER_SRC`）做全量穷举：

```text
normal_ok=90000/90000 malformed_ok=900000/900000 bad=0 elapsed=5.5s
first_bad= []
```

- `normal`：`10000..99999` 每个协议号构造 `,"Hash":<num<<32|5>,"IsTest":false}`，全部候选 1、Protocol 正确；
- `malformed`：同一批协议号 × 前导数字 `0..9`（`d + fragment`），共 900,000 例，全部候选 2、Protocol 恢复成原 `num`；
- 0 例外。原因：候选 1 会把 5 位数拼成 6 位数（`19004` -> `190044`），`Protocol == num` 失败；候选 2 去掉首字符后从逗号处重建，Protocol 必然回到 `num`。若协议号真是 6 位（如 190044），候选 1 的 `Protocol == num` 成立，会原样接受——不会把合法 6 位号误改。

线上 4 个协议的端到端取证（假 Shittim 实际收到的值，replay F1）：

```text
relay1 19004/Scenario_Select normal    -> Protocol=19004 / rl_req_build=1 / Shittim 收到 19004（错误号 190044 出现 0 次）
relay1 19004/Scenario_Select malformed -> Protocol=19004 / rl_req_build=2 / Shittim 收到 19004（错误号 190044 出现 0 次）
relay1 90011/Shop_ListTutori normal    -> Protocol=90011 / rl_req_build=1 / Shittim 收到 90011（错误号 900111 出现 0 次）
relay1 90011/Shop_ListTutori malformed -> Protocol=90011 / rl_req_build=2 / Shittim 收到 90011（错误号 900111 出现 0 次）
relay1 35003/MiniGame_Missio normal    -> Protocol=35003 / rl_req_build=1 / Shittim 收到 35003（错误号 350033 出现 0 次）
relay1 35003/MiniGame_Missio malformed -> Protocol=35003 / rl_req_build=2 / Shittim 收到 35003（错误号 350033 出现 0 次）
relay1 16000/Toast_List normal         -> Protocol=16000 / rl_req_build=1 / Shittim 收到 16000（错误号 160000 出现 0 次）
relay1 16000/Toast_List malformed      -> Protocol=16000 / rl_req_build=2 / Shittim 收到 16000（错误号 160000 出现 0 次）
relay2 19004/Scenario_Select normal    -> Protocol=19004 / rl_req_build=1 / Shittim 收到 19004（错误号 190044 出现 0 次）
relay2 19004/Scenario_Select malformed -> Protocol=19004 / rl_req_build=2 / Shittim 收到 19004（错误号 190044 出现 0 次）
relay2 90011/Shop_ListTutori normal    -> Protocol=90011 / rl_req_build=1 / Shittim 收到 90011（错误号 900111 出现 0 次）
relay2 90011/Shop_ListTutori malformed -> Protocol=90011 / rl_req_build=2 / Shittim 收到 90011（错误号 900111 出现 0 次）
relay2 35003/MiniGame_Missio normal    -> Protocol=35003 / rl_req_build=1 / Shittim 收到 35003（错误号 350033 出现 0 次）
relay2 35003/MiniGame_Missio malformed -> Protocol=35003 / rl_req_build=2 / Shittim 收到 35003（错误号 350033 出现 0 次）
relay2 16000/Toast_List normal         -> Protocol=16000 / rl_req_build=1 / Shittim 收到 16000（错误号 160000 出现 0 次）
relay2 16000/Toast_List malformed      -> Protocol=16000 / rl_req_build=2 / Shittim 收到 16000（错误号 160000 出现 0 次）
```

---

## 3. 问题 ②：`Session expired or invalid` 被拒后一直不重试

### 3.1 成因

桥缓存 `SESSION.session_key` 与 Shittim 内存表 `_activeSessions` 不一致（线上实测：`sessions.json` 是 `a25071d4…`，桥缓存是 `0793ebba…`）。Shittim 的 `SessionKeyService.cs:153` 一直把请求判成 `Session expired or invalid`，桥每次都拿同一个死缓存重发，永远失败。

### 3.2 改法

在**两条** relay 转发路径拿到 Shittim 响应、且 `obj` 是 dict 之后加同一个判断：

```python
def _rl_is_auth_fail(obj):
    if not isinstance(obj, dict):
        return False
    if obj.get('Protocol') == -1:
        return True
    ec = obj.get('ErrorCode')
    if isinstance(ec, int) and ec != 0:
        return True
    msg = str(obj.get('Msg') or obj.get('Message') or '')
    return 'Session' in msg and ('expired' in msg.lower() or 'invalid' in msg.lower())
```

命中后由 `_rl_retry_on_auth_fail(rec, req, post, unwrap, ensure, timeout=None)` 执行：

1. `rec['rl_session_retry'] = True`、`rec['rl_session_retry_ok'] = False`；
2. `_rl_clear_session()`：**拿同一把 `SESSION.lock`** 把 `SESSION.session_key` / `SESSION.account_id` 置 `None`（拿不到锁/异常只记 `rl_session_clear_err`，不抛）；
3. 重新 `ensure_session(rec)`（内部会重打 1014 CheckNexon 铸新会话）；
4. 把新会话写回 `req['SessionKey']`（重试必须用新票，不能拿旧票重放）；
5. 重新 `post_gateway`（relay v1 默认超时；relay2 仍用 `timeout=8`，没有 timeout 形参时退回无参调用）；
6. 仍失败（`code == 0` / 非 dict / 仍是鉴权失败 / 异常）-> `rl_session_retry_ok=False`、返回 `None`，调用方记 `relay_fallthrough='session-retry-failed'` / `relay2_fallthrough='session-retry-failed'` 并落回原逻辑——**不 500、不循环**。

同一个 `rec` 上 `_rl_retry_on_auth_fail` 第二次调用会直接返回 `None`（`if rec.get('rl_session_retry'): return None`），保证「只重试一次」。

日志：

| 字段 | 含义 |
|---|---|
| `rl_session_retry` | 命中鉴权失败、发起过重试 |
| `rl_session_retry_ok` | 重试后拿到正常响应 |
| `rl_session_retry_err`（辅助） | 重试失败原因（`ensure_session returned None` / `gateway unreachable/timeout` / `still auth-failed` / 异常 repr） |
| `rl_session_clear_err`（辅助） | 清缓存异常 |

行为边界：按任务给定的 `_rl_is_auth_fail`，**任何非 0 的 int `ErrorCode` 都算鉴权失败**。若某个业务协议用非 0 ErrorCode 表达业务错误，会多一次重试，第二次仍是同一错误时落回 `min+base`（不 500）。这是按规格实现的已知取舍。

### 3.3 端到端取证（replay F4/F5）

```text
F4 首包鉴权失败 -> 重试成功：bridge 200 / retry=True / ok=True / 内层=8006
F4 只重试 1 次：转发 8006=2 次 / CheckNexon=2 次（期望 2 / 2）
F4 第二次转发用的是重新铸的 SessionKey（AgICAgIC… -> AwMDAwMD…）
F5 两次都鉴权失败 -> bridge 200 / relay2_used=False / fallthrough='session-retry-failed' / retry_ok=False / 内层 Protocol=8006（落回、不 500）
F5 不循环：转发 8006=2 次 / CheckNexon=2 次（恰好 2 / 2）
```

---

## 4. 问题 ③：`EncryptedUID` 写死假值（本轮只登记，不修）

线上 1002 响应里：

```json
"EncryptedUID":"FUQPRE2OHCSXGOQRNGJQOAOCD4"
```

该值是硬编码在 **`cn_inner27.py:98`**（另一个文件，不在本补丁范围），客户端因此弹 `InvalidProtocol`。

- 本补丁**没有改** `cn_inner27.py`，也没有在 `account_auth_probe.py` 里伪造新值；
- 正确修法是按真实 UID 派生 `EncryptedUID`（换算法/密钥/输入域），需要单独定位 `cn_inner27.py` 的生成路径、对照官方抓包验证，属于**独立任务**；
- 任务 ① / ② 的修复不依赖它，也不会被它阻塞。

---

## 5. 开关与日志

- **不新增开关**。修复的是既有 relay 行为：
  - `cn_relay_unknown.txt` 打开 -> relay v1（HOOK-A）路径生效；
  - `cn_relay_known.txt` 打开 -> relay2（`if proto_int:` 之前）路径生效；
  - 两个都关 -> `rl_route` / `rl2_route` 在 switch 检查处直接返回 `None`，不进入 decode / `rl_request_json` / 重试代码。
- F7 用「冻结 `time.time` / `datetime.datetime.now` / `uuid.uuid4`」把两次响应变成可逐字节比较，验证：

  ```text
  F7 未知 8006 开关关：响应 295 B 与基线逐字节一致 / Shittim 0 次 / RLFIX 字段=[]
  F7 已知 8000 开关关：响应 300 B 与基线逐字节一致 / Shittim 0 次 / RLFIX 字段=[]
  F7 已知 19004 开关关：响应 304 B 与基线逐字节一致 / Shittim 0 次 / RLFIX 字段=[]
  ```

- 新增日志字段见 §2.2 / §3.2；访问日志按既有 `rec` 全量落盘（`account_auth_probe.py` 第 1171 行附近 `json.dumps(rec)`）。

---

## 6. 六步真实输出

### 第 1 步：`--verify`（基线，硬闸）

```text
python patch_relay_fix.py --src _sandbox\p3\account_auth_probe.py --verify
src     : _sandbox\p3\account_auth_probe.py
          128309 字节 / 3082 行 / sha256 e5fb03b87433741ed61ad6f7cc010707193fbd46d7c2086608fb0c11d66f5581
patched : 否
  INFO  状态 = 校验基线 + 锚点
  PASS  python 语法检查 compile()
  PASS  基线大小 == 128309（实测 128309）
  PASS  基线 sha256 == e5fb03b87433741ed61ad6f7cc010707193fbd46d7c2086608fb0c11d66f5581（实测 …）
  PASS  基线里零 BAPATCH-RLFIX 残留（实测 0 处）
  PASS  helper 插入锚点唯一 1 次（第 2673 行）
  PASS  req-tail: 原文恰好 1 处、新文 0 处（可安全替换）
  …（6 条替换各 1 条，另 4 块上一版补丁标记齐全）
结论: PASS
```

反向验证硬闸：拿 115,911 B 的 relay1-only 文件执行 `--apply`：

```text
!! 基线指纹不符，拒绝打补丁
   实测 115911 字节 / sha256 377176809ff25949a45e54224a274ad2b701e02c2d6d8a787a4a6eb16e815a07
   期望 128309 字节 / sha256 e5fb03b87433741ed61ad6f7cc010707193fbd46d7c2086608fb0c11d66f5581
EXIT=1
```

### 第 2 步：`--dry-run`（mtime 不变）

```text
== 改动动作 ==
  RLFIX: 在原文件第 2673 行之前插入 helper 块（161 行 / 5623 B）
  req-tail: 替换 1 处（165 B -> 121 B）
  req-frag-head: 替换 1 处（61 B -> 209 B）
  relay1-frag-head: 替换 1 处（40 B -> 322 B）
  relay1-session-retry: 替换 1 处（340 B -> 959 B）
  relay2-frag-head: 替换 1 处（36 B -> 318 B）
  relay2-session-retry: 替换 1 处（344 B -> 1033 B）
  ---- helper 摘要 ----
  161 行 / sha256 ccdc3780246a9399
语法检查: PASS
--dry-run：没有写文件。mtime/size 未变: True（(1794853625674876500, 128309)）
```

### 第 3 步：`--apply`

```text
已写入。备份: _sandbox\p3\account_auth_probe.py.rlf.bak.20261117-022918
  写入后 136894 字节 / sha256 60f34664933656f460e5c4e74e4cacb19273bac213302b184f8ce12070e785ee
  PASS  helper 块正文逐字节 == patch_relay_fix.py 的 RLFIX_HELPER_SRC（sha256 ccdc3780246a9399 / ccdc3780246a9399）
  PASS  helper 块在 rl_request_json 之前（helper@102969 < def@108592）
  …
自检: 全绿
```

补丁后 `--verify`：**31 PASS / 0 FAIL / 结论 PASS**；幂等复跑 `--apply` 写入后 sha 仍为 `60f34664…`（前后一致）。

### 第 4 步：`py_compile`

```text
python -m py_compile _sandbox\p3\account_auth_probe.py
PYCOMPILE_EXIT=0
```

### 第 5 步：回归 + 新功能重放

```text
_p3_replay.py           --target <patched>   -> 22 项断言 / 0 FAIL / ALL PASS
_relay_replay.py        --target <patched>   -> 44 项断言 / 1 FAIL（仅 R0，夹具基线过期）
_relay2_replay.py       --target <patched>   -> 61 项断言 / 1 FAIL（仅 S0，夹具基线过期）
_relayfix_replay.py     --target <patched>   -> 39 项断言 / 0 FAIL
```

夹具对照（证明上一版 replay 本身没坏）：

```text
_relay_replay.py  --target <115,911 B relay1-only 夹具> -> 45 项断言 / 0 FAIL / ALL PASS
_relay2_replay.py --target <128,309 B 补丁前夹具>        -> 62 项断言 / 0 FAIL / ALL PASS
```

### 第 6 步：`--rollback`（最终态）

```text
src     : _sandbox\p3\account_auth_probe.py
          136894 字节 / 3282 行 / sha256 60f34664…
patched : 是
  跳过备份 account_auth_probe.py.rlf.bak.20261117-023049（sha256 60f34664… 不是基线 e5fb03b8…）
已用备份还原: …\account_auth_probe.py.rlf.bak.20261117-022918
  还原后 128309 字节 / sha256 e5fb03b87433741ed61ad6f7cc010707193fbd46d7c2086608fb0c11d66f5581
  与基线 128309 B / e5fb03b8… 逐字节一致
  残留 BAPATCH-RLFIX 标记: 无（干净）
EXIT=0
```

最终核验：

```text
FINAL_LEN=128309
FINAL_SHA=E5FB03B87433741ED61AD6F7CC010707193FBD46D7C2086608FB0C11D66F5581
MARK_HITS=0
```

另外单独验证了「无备份可用时按块摘除」的回滚路径（在 `_scratch` 副本上先 `--apply`、再删掉 `.rlf.bak.*`、再 `--rollback`）：

```text
relay2-session-retry: 还原 1 处（1033 B -> 344 B）
relay2-frag-head: 还原 1 处（318 B -> 36 B）
relay1-session-retry: 还原 1 处（959 B -> 340 B）
relay1-frag-head: 还原 1 处（322 B -> 40 B）
req-frag-head: 还原 1 处（209 B -> 61 B）
req-tail: 还原 1 处（121 B -> 165 B）
RLFIX: 摘掉 helper 块（5623 B）
还原后 128309 字节 / sha256 e5fb03b8…
残留 BAPATCH-RLFIX 标记: 无（干净）
```

---

## 7. 回归逐条说明（为什么 R0 / S0 是夹具问题）

### 7.1 `_p3_replay.py`：22/22 全过

与 relay 无关，直接证明协议 3 的 P3 补丁未被本补丁影响（620 B / 键序 / tick / 异常回退都过）。

### 7.2 `_relay_replay.py`（目标 = 最终 136,894 B）：44 项 / 1 FAIL

唯一失败：

```text
FAIL  R0  摘掉 PAYLOAD+HOOK-A 后 == 基线 103900 B / 563c1942289968e3（实测 117331 B / c52561cf33385baf）
```

为什么是夹具过期：

1. `_relay_replay.py` 的文档写的是「target = 已打 patch_3 + patch_relay 的 account_auth_probe.py」，R0 期望摘掉 relay1 两块后回到 **103,900 B**；
2. 实际目标是 `patch_3 + patch_relay + patch_relay2 + relayfix`。只摘 relay1 两块后，文件里仍留着 relay2 载荷/钩子（12,398 B）和本补丁落在 relay2 里的两处改动（约 1,033 B），所以结果 = 103,900 + 12,398 + 1,033 = **117,331 B**，不可能是 103,900；
3. **在本补丁之前就失败**：对补丁前的 128,309 B 目标跑 `patch_relay.py --verify`，同一条断言实测 **116,298 B**（= 103,900 + 12,398），FAIL 2 条（大小 + 残留标记）；
4. 其余 43 条（HOOK-A 位置 / 注入 / 转发 / 500 / 超时 / 异常 / 回退）全 PASS；
5. 用该 replay 自己的夹具（115,911 B，relay1-only）跑：**45 项 / 0 FAIL / ALL PASS**，证明 patch_relay 自身行为没被破坏。

### 7.3 `_relay2_replay.py`（目标 = 最终 136,894 B）：61 项 / 1 FAIL

唯一失败：

```text
FAIL  S0  摘掉 PAYLOAD+HOOK 后 == 基线 115911 B / 377176809ff25949（实测 123463 B / 1a1bf64d4ba4a61c）
```

为什么是夹具过期：

1. S0 只摘 relay2 的 PAYLOAD + HOOK，期望回到补丁前的 **115,911 B**；
2. 本补丁的 helper 必须放在 **relay1 的 RL_PAYLOAD** 里：relay2 可能没打（只有 relay1 时也要能修协议号），helper 放进 relay2 会让 relay1 单独失效；
3. helper（6,411 B）+ relay1 的 4 处改动（-12+190+320+643 = +1,141 B）= 7,552 B 留在 115,911 B 之上，正好 **123,463 B = 115,911 + 7,552**；
4. 其余 60 条全 PASS（S1 开关关 / S2 转发 / S3 10 个协议 / S4 失败回退 / S5 9 个回归协议 / S6 1014 不递归 / S7 字段 / S8 纯本地）；
5. 用补丁前的 128,309 B 夹具跑：**62 项 / 0 FAIL / ALL PASS**，证明 relay2 自身行为没被破坏。

### 7.4 `_relayfix_replay.py`：39 项 / 0 FAIL

覆盖任务要求的全部新功能取证（§2.4 / §3.3 / §5），外加：

```text
F0  摘掉 RLFIX 后 == 基线 128309 B / e5fb03b8…（实测 128309 / e5fb03b8…）
F2  正常 fragment -> rl_req_build=1 / Protocol=19004
F2  开头残留末位数字 "4" -> rl_req_build=2 / Protocol=19004
F2  两字符可疑前缀 -> rl_req_build=3 / Protocol=19004
F3  rl_request_json 直接调用 -> None / rl_req_build=0 / err='all candidates failed (1 tries): c1:JSONDecodeError'
F3  全候选失败 -> bridge 200 / Shittim 请求 0 次 / fallthrough='decode-json' / 内层 Protocol=19004（落回 min+base，不 500）
F6  _rl_is_auth_fail 5 个正样本全部命中（[True, True, True, True, True]）
F6  _rl_is_auth_fail 5 个负样本全部不命中（[False, False, False, False, False]）
F8  relay2：上层已有 req_frag_head -> 不覆盖（'UPSTREAM-SENTINEL'）/ rl_req_build=1
F9  全程只连假 Shittim http://127.0.0.1:<port>/api/gateway（未连任何远端）
```

---

## 8. 回滚与运维注意

回滚（沙箱已执行，最终态见第 6 步）：

```powershell
<python> patch_relay_fix.py --src _sandbox\p3\account_auth_probe.py --rollback
```

- 优先用 `.rlf.bak.<ts>` 中 sha == 基线的那份还原；没有可用备份时按 6 处编辑逆序 + 摘 helper 块还原；
- 两种路径都实测回到 **128,309 B / `e5fb03b8…`**，零 `BAPATCH-RLFIX` 残留；
- 线上回滚同理，把 `--src` 换成 `/www/wwwroot/bapatch/tools/account_auth_probe.py`。

运维注意：

1. **打完本补丁后不要重跑 `patch_relay.py --apply` / `patch_relay2.py --apply`**。它们会把各自的载荷块整块换回未修版本：`patch_relay` 会覆盖 helper + relay1 的 4 处改动，`patch_relay2` 会覆盖 relay2 的 2 处改动。要重新打，顺序是 `rollback -> relay -> relay2 -> relayfix`。
2. 本补丁不碰开关文件；上线时沿用现有 `cn_relay_unknown.txt` / `cn_relay_known.txt` 的取值。
3. `patch_relay_fix.py --verify` 在已打状态下会断言「摘掉本补丁 == 128,309 B / e5fb03b8」；`patch_relay.py --verify` / `patch_relay2.py --verify` 在已打状态下会因载荷被改而报 payload 不一致，属预期（见运维注意 1）。
4. 纯本地：脚本 import 期不碰文件系统/网络；`--apply` 只读写 `--src` 与同目录 `.rlf.bak.*`；replay 只监听 `127.0.0.1`。

---

## 9. 交付物

| 文件 | 字节 | sha256 |
|---|---|---|
| `deploy/patch_relay_fix.py` | 43,992 | `b033ebb65874aa132710c9757ea103bd804bca0bb6eb0e39247788a34d42736a` |
| `deploy/_relayfix_replay.py` | 23,778 | `81fcd583b52c0640d16debe642ae953737ead8b591682cce6f4dc5c264c0c12c` |
| `deploy/PROGRESS_RELAYFIX.md` | 本文件 | 见交付回执 |

沙箱目标（最终）：

| 状态 | 字节 | sha256 |
|---|---|---|
| 补丁后（已验证，已回滚） | 136,894 | `60f34664933656f460e5c4e74e4cacb19273bac213302b184f8ce12070e785ee` |
| **最终 / 回滚后** | **128,309** | **`e5fb03b87433741ed61ad6f7cc010707193fbd46d7c2086608fb0c11d66f5581`** |

---

## 10. 已知边界

- `_rl_build_request` 候选 3–10 可能把 fragment 里自带的 `"Protocol":...` 字段截掉一部分；只有最终 `Protocol == Hash>>32` 且非空 dict 才接受，因此不会转发一个「猜出来」的协议号。
- 会话重试会用新铸的 `SessionKey` **覆盖**请求里原有的 `SessionKey`（否则重试等于拿旧票重放）；重试请求的 `relay*_session_injected` 记为 `True`。
- 重试失败落回后，访问日志仍保留首个响应与重试的痕迹（`relay*_code` / `relay*_resp_len` 更新为最后一次），`relay*_fallthrough='session-retry-failed'` 可 grep。
- `EncryptedUID` 仍是假值，客户端 `InvalidProtocol` 不会因本补丁消失——见 §4，独立任务。
