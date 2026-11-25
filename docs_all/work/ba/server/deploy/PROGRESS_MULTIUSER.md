# PROGRESS_MULTIUSER — bridge 按请求身份分流 + token 校验

一次性执行记录。**全程本地，没有 ssh / scp，没有连任何服务器。**
Python = `C:\Users\su\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe`（3.12.14）。

交付物（`work/ba/server/deploy/`）：

| 文件 | 字节 | sha256 | 作用 |
|---|---|---|---|
| `patch_multiuser.py` | 87,513 | `7304c7ecacea1e46e34b38bdbde7bbaaf93455ccb0469b034807cf4041310383` | 打/摘补丁（--verify/--dry-run/--apply/--rollback） |
| `_multiuser_replay.py` | 42,867 | `003611ce3822842eacb2435bbbba76b7808a786dbf35411170d079f612eb0513` | 新功能取证（57 项，含假认证服务 + 假 Shittim） |
| `PROGRESS_MULTIUSER.md` | 本文件 | — | 锚点行号 / 插入代码 / 六步真实输出 / 回滚 / 上线顺序 |

沙箱最终状态：`_sandbox/p3/account_auth_probe.py` = **128,309 B / `e5fb03b87433741ed61ad6f7cc010707193fbd46d7c2086608fb0c11d66f5581`**（= 线上现状，已 `--rollback`，零 `BAPATCH-MU` 残留）。

---

## §1 问题（已确证，不是推测）

基线文件里三处硬编码 + 一处全局单例，构成"所有玩家共用一个 Shittim 账号"：

```python
# L164-166  ── 硬编码，所有客户端共用
UID   = '314816420'
TOKEN = '61de1d1b7519ab1231866f74c11fcfdd1f80b210'
ENTER_TICKET = base64.b64encode(('%s/%s' % (UID, TOKEN)).encode()).decode()

# L1063    ── ensure_session(rec)：永远用上面那张 ticket 去打 Account_CheckNexon(1014)
# L508     ── SESSION = Session()   ← 模块级单例，并发会互相覆盖
```

⇒ 所有玩家共用 Shittim 的 `ServerId=2`，并且并发时还会串号。

客户端身份本来就在请求里（已实测）：`DevId`（数字字符串 = f(卡密)）、`Token`（`sha256(卡密|设备)[:40]`）、
`DeviceUniqueId`、`Hash`。Shittim 的 `EnterTicket = base64(UTF8("{publisherId}/{token}"))`，
`publisherId` 必须能 `long.Parse`（`AccountHandler.cs:58-63`），按 `UserAccounts.NpSN == publisherId`
匹配，**没见过的 publisherId 会自动建号**（`:68-89`）。

---

## §2 基线重建（带指纹闸）

```powershell
cd work\ba\server\deploy
<python> patch_relay.py  --src _sandbox\p3\account_auth_probe.py --apply --switches 1   # → 115,911 B / 377176809f…
<python> patch_relay2.py --src _sandbox\p3\account_auth_probe.py --apply --switches 1   # → 128,309 B / e5fb03b8…
```

本次实测（第二步的收尾输出）：

```
=== after ===
Length : 128309
E5FB03B87433741ED61AD6F7CC010707193FBD46D7C2086608FB0C11D66F5581
```

与任务书给的指纹**逐字节一致**，才继续。`patch_multiuser.py` 把 `128309 / e5fb03b8…` 写成
`BASE_SIZE / BASE_SHA256` 硬闸：不等就拒绝 `--apply`（可用 `--expect-sha` 覆盖）。

---

## §3 两个开关

| 文件 | 值 | 含义 |
|---|---|---|
| `cn_multiuser.txt` | `1` / `on` / `true` / `yes` | 按请求身份分流 + 每人独立 session |
| | 缺失 / `0` / 其它 | **完全不动**（逐字节维持现状，连一个 `mu_*` 字段都不写） |
| `cn_auth_enforce.txt` | `1` / `on` / `true` / `yes` | token 校验失败**真的拦** |
| | 缺失 / `0` | 只记录不拦（**观察模式**） |

- 查找顺序复用 `patch_relay.py` 的 `rl_read_file`：**bridge 同目录 → `/www/wwwroot/bapatch/tools` → `/www/wwwroot/bapatch`**
  （`mu_read_file` 优先调 bridge 里的 `rl_read_file`，没有才自己按同样顺序找）。
- `--switches keep`（默认）**不创建**缺失文件 —— 实测断言见 M0：
  `--switches keep：缺失的 cn_multiuser.txt **没有**被创建`。
- `cn_auth_enforce=1` 而 `cn_multiuser` 关着时，enforce 是**惰性**的（闸根本不进）—— 这是"关 = 现状不变"的直接推论。

---

## §4 插入点与插入代码

三个锚点（基线行号 = `e5fb03b8` 那份）：

| 单元 | 锚点 | 基线行 | 打完后行 | 缩进 |
|---|---|---|---|---|
| `PAYLOAD` | `if __name__ == '__main__':` 之前 | 3076 | 3106–3711 | 0（模块级） |
| `HOOK-ENSURE` | `def ensure_session(rec):` 之后 | 1063 | 1064–1078 | **4**（函数体第一行） |
| `HOOK-GATE` | `rec['protocol_name'] = name` 之后 | 1689 | 1705–1719 | **8**（`_bridge` 方法体） |

字符偏移（打完后）：`ensure anchor@37713 < ensure@37742`；
`gate anchor@67574 < gate@67618 < P3-HOOK-E@68415`；`payload@120047 < main@140907`。

### §4.1 HOOK-ENSURE（4 空格，插在 `ensure_session` 函数体第一行，`with SESSION.lock:` 之前）

```python
def ensure_session(rec):
    # >>> BAPATCH-MU-HOOK-ENSURE v1 BEGIN >>>
    # 按请求身份分流：cn_multiuser.txt 打开、且能从请求里取到 (DevId, Token) 时，用
    # base64("DevId/Token") 当 EnterTicket 去铸**这个玩家专属**的会话（每个 publisher 一份
    # 缓存 + 一把锁），不再用下面那个全局硬编码 ENTER_TICKET。
    # 取不到身份 / 开关关 -> 返回 None，继续走下面**一个字节都没改动**的旧路径
    # （单例 SESSION + 硬编码 ENTER_TICKET = 打补丁前的行为）。
    # 有身份但 Shittim 铸不出来 -> 返回 (None, None)，和旧代码 1014 失败一样 500，
    # 绝不静默退回公共账号。
    try:
        _mu_sess = mu_ensure_session(rec)
        if _mu_sess is not None:
            return _mu_sess
    except Exception as _mu_ensure_err:
        rec['mu_ensure_err'] = repr(_mu_ensure_err)
    # <<< BAPATCH-MU-HOOK-ENSURE v1 END <<<
    with SESSION.lock:                 # ← 旧函数体，一个字节没动
        if want_force_reauth():
            rec['force_reauth'] = True
            ...
```

### §4.2 HOOK-GATE（8 空格，插在 `rec['protocol_name'] = name` 之后、P3-HOOK-E / path A / path B 之前）

```python
        name = NAME_TABLE.get(proto_str) or EXTRA_TOKENS.get(proto_str)
        rec['protocol_name'] = name
        # >>> BAPATCH-MU-HOOK-GATE v1 BEGIN >>>
        # 多用户分流 + token 校验闸（开关 cn_multiuser.txt；缺失 / 0 = 这段完全不生效）。
        # 位置 = `rec['protocol_name'] = name` 之后、HOOK-E / experror / path A / path B 之前，
        # 也就是**任何转发给 Shittim 的动作之前**：enforce 打开且 token 校验失败时，请求在
        # 这里就以 {"Protocol":-1,"ErrorCode":3,...} 的标准信封打回，不会打到 Shittim。
        # 观察模式（cn_auth_enforce 缺失 / 0）只记 mu_verify_* 字段，照常放行；
        # 认证服务连不上 / 超时（2 秒）同样放行并记 mu_verify_err。
        # 任何异常都不往外抛：记 mu_gate_err 后原路继续（绝不 500）。
        try:
            _mu_gate = mu_gate(rec, proto_str, name, self._cn_envelope, packet_b64)
            if _mu_gate is not None:
                return _mu_gate
        except Exception as _mu_gate_err:
            rec['mu_gate_err'] = repr(_mu_gate_err)
        # <<< BAPATCH-MU-HOOK-GATE v1 END <<<
```

**为什么闸必须在 path A / path B 之前**：path A（`exp=decrypt+…`）和 path B（合成 Account_Auth /
CheckNexon）都会调 `post_gateway(...)` 打 Shittim；relay / relay2 的钩子也在后面。
挂在 `rec['protocol_name'] = name` 之后 = 名字已解出（拒绝信封要用它算 `base32(md5)`），而**任何**
发往 Shittim 的包都还没发出去。

### §4.3 PAYLOAD（606 行，`if __name__ == '__main__':` 之前）

`MU_PAYLOAD_SRC` 里带 `sha256=3fb4b6bf5108378f…`（`--verify` 会逐字节比对 + 跑单测）。函数清单：

| 函数 | 作用 |
|---|---|
| `mu_read_file / mu_multiuser_on / mu_enforce_on` | 开关（复用 `rl_read_file`；缺失 = 关） |
| `mu_norm_dev / mu_norm_tok` | `DevId` 归一成数字串（`long.Parse` 前提）、`Token` 合法性 |
| `mu_identity` | rec 已记录字段 → `cn_cipher.decode_packet` 的 `json`/`fragment` → 正则 → rec 其它文本字段 |
| `mu_bind_ids / mu_current_ids` | 把身份挂到**本次请求的线程槽**（绑 `rec` 对象；**不写进 rec**，rec 会进日志） |
| `mu_mask` | `DevId 前 4 位.../Token 前 6 位...` |
| `mu_enter_ticket` | `base64(UTF8("DevId/Token"))` |
| `mu_verify` | POST `/auth/verify`，2 秒超时；`True / False / None(未知→放行)`；连续失败 3 秒短熔断 |
| `mu_gate` | 闸：开关关=零痕迹；取不到身份=`mu_fallthrough=no-identity`；失败 + enforce=1=拒绝 |
| `mu_reject` | 拒绝信封：名字已知走 `self._cn_envelope(name, {"Protocol":-1,"ErrorCode":3,"ServerTimeTicks":…})`；名字表里没有的 token 走等价形状（`protocol` 直接用客户端 token） |
| `mu_ensure_session` | per-publisher 铸会话：`MU_SESSIONS[publisher] = {session_key, account_id, created}` + `MU_LOCKS[publisher]` |
| `MuSessionView` | mu 打开时把全局 `SESSION` 换成**按线程**视图（1017 动态生成器 / 账号号解析等直接读 `SESSION.*` 的地方也能看到"自己这个玩家"），本线程没会话就回落旧单例 |
| `mu_reset_sessions / mu_sessions_snapshot` | ops 用（清缓存 / 只看 publisher→account_id，不含 session_key） |

**per-publisher 会话缓存**（对应任务书里的 "SESSION 从单例 → `{publisher_id: {...}}`"）：

```python
MU_SESSIONS = {}      # publisher_id(=DevId) -> {'session_key','account_id','created','publisher','code'}
MU_LOCKS    = {}      # publisher_id -> threading.Lock()（锁的创建在 MU_GUARD 下）
```

旧单例 `SESSION` 仍然保留（`cn_multiuser=0` 的旧路径要用它，这是"逐字节不变"的前提）；
`cn_multiuser=1` 时它被换成一个 `MuSessionView`，按线程返回当前请求的会话 —— 两个玩家并发时
各读各的（M9 实测）。

---

## §5 缩进：8 / 4 是怎么定的（前两版都在这踩过坑）

| 补丁 | 错的那版 | 实际需要 |
|---|---|---|
| `patch_relay.py` | 第一稿写 8 空格 | 目标在 `if name is None:` 里 → 需要 **12** |
| `patch_relay2.py` | —— | `if proto_int:` 是 **8** 空格 |
| **本补丁 GATE** | —— | `_bridge` 方法体 = **8** 空格（与 `rec['protocol_name'] = name` 同级） |
| **本补丁 ENSURE** | 第一稿用两行锚点（`def` + `with SESSION.lock:`）→ 块被插到 `with` **后面**，`with` 没有函数体 | 只锚 `def` 行，插完是函数体第一行 = **4** 空格 |

第一稿的错由 `--dry-run` 的语法闸当场抓住（`IndentationError line 1073: expected an indented block
after 'with' statement on line 1064`，**没有写文件**），改成单行锚点后通过。

`--verify` 的缩进/AST 断言（全部 PASS）：

```
PASS  HOOK-GATE 起始行缩进 == 8 / try: == 8 / 体内 == 12
PASS  HOOK-ENSURE 起始行缩进 == 4 / try: == 4 / 体内 == 8
PASS  AST：mu_gate(...) 全文件唯一（1 处）
PASS  AST：含 mu_gate(...) 的 Try 是 `_bridge` 函数体的一条直接语句（下标 9）
PASS  AST：它就紧跟在 `rec[protocol_name] = name`（下标 8）之后，且是 P3-HOOK-E（下标 10）的前一条
PASS  AST：GATE 的父节点 == 'FunctionDef'（不是 If/Try/ExceptHandler）
PASS  AST：含 mu_ensure_session(...) 的 Try 是 `ensure_session` 函数体的第一条语句（下标 0）
PASS  AST：它后面紧跟 `with SESSION.lock:`（旧路径原样）
PASS  反证：HOOK-GATE 整体右移 4 空格 -> 编译失败（IndentationError line 1713: unexpected indent）
PASS  反证：HOOK-ENSURE 整体右移 4 空格 -> 编译失败（IndentationError line 1079: unindent does not match）
```

---

## §6 六步真实输出（原样摘录）

命令都在 `work\ba\server\deploy`，`<python>` = 上面那个 3.12.14。

### 步骤 1 —— `--verify`（基线，未打补丁）

```
src     : _sandbox\p3\account_auth_probe.py
          128309 字节 / 3082 行 / sha256 e5fb03b87433741ed61ad6f7cc010707193fbd46d7c2086608fb0c11d66f5581
patched : 否
  PASS  基线大小 == 128309（实测 128309）
  PASS  基线 sha256 == e5fb03b8…（实测 e5fb03b8…）
  PASS  基线里没有 BAPATCH-MU 残留（实测 0 处）
  PASS  既有补丁 BAPATCH-{SIMPLE,P3,RELAY,RELAY2}-PAYLOAD 的 BEGIN/END 都在（各 2 处）
  PASS  既有补丁 …-HOOK-{D,E,G,A} / RELAY2-HOOK 的 BEGIN/END 都在（各 2 处）
  PASS  旧常量/单例原样在：UID / TOKEN / ENTER_TICKET / SESSION = Session()
  PASS  锚点 PAYLOAD 唯一命中 1 次（第 3076 行）
  PASS  锚点 HOOK-GATE 唯一命中 1 次（第 1689 行）
  PASS  锚点 HOOK-ENSURE 唯一命中 1 次（第 1063 行）
  PASS  锚点 `rec[protocol_name] = name` 缩进 == 8（实测 8）
  PASS  锚点 `def ensure_session(rec):` 在 0 列、`with SESSION.lock:` 在 4 列（实测 0 / 4）
  PASS  AST：`rec[protocol_name] = name` 是 `_bridge` 直接语句（下标 8）
  PASS  AST：它的下一条语句是 Try（P3-HOOK-E，line 1695）
  PASS  AST：`ensure_session` 的第一条语句是 `with SESSION.lock:`（line 1064）
结论: PASS        ← 31 PASS / 0 FAIL
```

### 步骤 2 —— `--dry-run`（mtime 不变）

```
  PAYLOAD: 在原文件第 3076 行之前插入 606 行
  HOOK-GATE: 在原文件第 1689 行之后插入 15 行  -> 落在第 1690 行，缩进 8 空格（体内 12）
  HOOK-ENSURE: 在原文件第 1063 行之后插入 15 行 -> 落在第 1064 行，缩进 4 空格（体内 8）
  ---- 开关 ----
  ...\_sandbox\p3\cn_multiuser.txt: 缺失（= 关）
  ...\_sandbox\p3\cn_auth_enforce.txt: 缺失（= 关）
== diff（56 行）==      ← 只有 3 个 hunk + PAYLOAD 占位（载荷正文被 mask）
语法检查: PASS
--dry-run：没有写文件。mtime/size 未变: True（(1794853248681286800, 128309)）
           开关文件也没动
mtime unchanged: True
```

### 步骤 3 —— `--apply --switches 1`

```
已写入。备份: _sandbox\p3\account_auth_probe.py.mu.bak.20261117-022059
  写入后 153728 字节 / sha256 c8f1eb667249436b7d4c9d8f238810b53a14c4722a77ea5b84df5fcfcddcaf4b
开关:
  ...\_sandbox\p3\cn_multiuser.txt=1（新建）
  ...\_sandbox\p3\cn_auth_enforce.txt（缺失，未创建 —— 缺失=关）
== 打完补丁后的自检 ==
  PASS  BAPATCH-MU 标记总数 == 6（实测 6）
  PASS  内嵌 PAYLOAD 逐字节 == MU_PAYLOAD_SRC（sha256 3fb4b6bf5108378f / 3fb4b6bf5108378f）
  PASS  HOOK-GATE / HOOK-ENSURE 代码块逐字节 == 生成的那份
  PASS  GATE 整块在 `rec[protocol_name] = name` 之后、P3-HOOK-E 之前（67574 < 67618 < 68415）
  PASS  ENSURE 整块在 `def ensure_session(rec):` 之后（37713 < 37742）
  PASS  ENSURE 整块后面紧跟 `with SESSION.lock:`（旧函数体没被挤开）
  PASS  10 项缩进断言（8/12、4/8）+ 3 项 AST 定位 + 2 项反证
  PASS  摘掉 PAYLOAD+两个 HOOK 后逐字节 == 基线 128309 B / e5fb03b8…（实测 128309 B / e5fb03b8…）
  PASS  自检 102 项全绿（含内嵌运行时单测）
自检: 全绿        ← 102 PASS / 0 FAIL
```

产物：**153,728 B / `c8f1eb667249436b7d4c9d8f238810b53a14c4722a77ea5b84df5fcfcddcaf4b`**（= 128,309 + 15,419）。

### 步骤 4 —— `py_compile`

```
py_compile exit=0
```

### 步骤 5 —— 回归 + 新功能取证

| 套件 | 结果 | 说明 |
|---|---|---|
| `_p3_replay.py --target <产物>` | **22 项 / 0 FAIL / ALL PASS** | 协议 3 的 620 B、7 键序、双 tick 全绿 |
| `_relay_replay.py --target <产物>` | **44 PASS / 1 FAIL** | 唯一 FAIL = `R0 摘掉 PAYLOAD+HOOK-A 后 == 基线 103900 B / 563c1942…（实测 141717 B / 15effda0…）` |
| `_relay2_replay.py --target <产物>` | **61 PASS / 1 FAIL** | 唯一 FAIL = `S0 摘掉 PAYLOAD+HOOK 后 == 基线 115911 B / 37717680…（实测 141330 B / 7757fdf6…）` |
| `_multiuser_replay.py --target <产物>` | **57 项 / 0 FAIL / ALL PASS** | 本次新增，见 §7 |

`R0` / `S0` 这两个 FAIL 是**夹具假设过期**：它们的断言是"把本套件的块摘掉后 == 它当年的基线
（103,900 / 115,911）"，而现在产物上还叠了 `relay2` + `multiuser` 两个补丁，摘掉一层当然不等于
当年的基线。任务书已预告 `R0` 会这样；`S0` 是同一类（本补丁又叠了一层）。**其余每一项行为断言
（逐字段比对、开关开/关对照、故障落回、1014 不递归）都 PASS。**

以 `_relay2_replay` 的 S5 为例（9 个已知协议：开关开 / 开关关 / 打补丁前 三者逐字段一致）：

```
PASS  S5 Account_Auth(1002) / Account_CheckNexon(1014) / Academy_GetInfo(24000) /
         Account_LoginSync(1017) / Item_List(4000) / Account_GetTutorial(1005) /
         Content_SaveGet(26000) / NetworkTime_Sync(3) / Management_Data(90004)
         ：开关开 vs 开关关 vs 打补丁前 响应逐字段一致
```

### 步骤 6 —— `--rollback`

```
src     : _sandbox\p3\account_auth_probe.py
          153728 字节 / 3718 行 / sha256 c8f1eb66…
patched : 是
已用备份还原: _sandbox\p3\account_auth_probe.py.mu.bak.20261117-022059
  还原后 128309 字节 / sha256 e5fb03b87433741ed61ad6f7cc010707193fbd46d7c2086608fb0c11d66f5581
  与基线 128309 B / e5fb03b87433741e 逐字节一致
  残留 BAPATCH-MU 标记: 无（干净）

=== final ===
size=128309 sha256=e5fb03b87433741ed61ad6f7cc010707193fbd46d7c2086608fb0c11d66f5581 patched=0
```

`--rollback` 的挑备份逻辑：从新到旧扫 `.mu.bak.*`，只接受 **sha == 基线** 的备份（本次日志里能看到
它跳过了 3 个"打完补丁"的备份）；一个都不匹配才退化成"直接摘块"，摘完也校验 sha。
本次两种路径都验证过（先摘块、后备份还原，结果都是 `e5fb03b8…`）。

---

## §7 新功能取证 `_multiuser_replay.py`（57 项 / 0 FAIL）

装置：`http.server` 假认证服务（优先 `127.0.0.1:8080`，被占则随机端口）+ 复用 `_relay2_replay.py`
的假 Shittim（**会解 `EnterTicket` 并按 publisher 建号**，每个 publisher 一个稳定 AccountId）。
全程只监听 `127.0.0.1`。

| 组 | 断言 | 实测 |
|---|---|---|
| M0 | 结构 / 开关语义 | 摘块 == 基线；3 块标记成对；GATE 8 / ENSURE 4；AST 定位同 §5；`--switches keep` **不创建**缺失文件 |
| M0 | 默认端点 | 不加配置时默认就是 `POST http://127.0.0.1:8080/auth/verify`（`mu_verify_ok=True`） |
| **M1** | **两个不同 `(DevId, Token)`** | 假 Shittim 收到 **2 次 1014**，`EnterTicket` 解出**两个不同 publisherId**（`['271828182','314816420']`）、两个不同 token；两个玩家 **AccountId 100001 vs 100002**；两次业务转发各带**自己**的 SessionKey（`[100001, 100002]`） |
| M2 | 同一身份连发两次 | `fresh` → `cache`，假 Shittim 只收到 **1 次** 1014；两次同一套 SessionKey |
| M3 | `enforce` 缺失/0 + `ok:false` | **仍 200 放行**，`mu_verify_reason='device_revoked'`，`mu_rejected=False`，照常铸会话 |
| **M4** | `enforce=1` + `ok:false` | 200 + `application/json` 信封：外层 `protocol == 客户端 token`，内层 `{"Protocol":-1,"ErrorCode":3,"ServerTimeTicks":639304788647836220}`；**假 Shittim 0 次调用**；没铸任何会话 |
| M5 | 认证服务连不上 | 放行（`URLError: timed out` 2.02 s），`mu_verify_err` 非空，会话照常铸 |
| M5 | 连续失败熔断 | 下一个请求 **0.001 s** 返回（`breaker-open: …`），照样放行 |
| M5 | 认证服务 hang | **2.0 s**（2 秒超时）后放行，`mu_verify_err='TimeoutError: timed out'` |
| **M6** | `cn_multiuser=0` / 缺失 | `Account_Auth(1002)` / `Account_CheckNexon(1014)` / `Mission_List(8000)` / `NetworkTime_Sync(3)`：与"摘掉本补丁的现状"**响应逐字段一致 + rec 逐字段一致 + 零 `mu_*` 字段**（1002/1014 连**原始字节**都相同；8000/3 仅差 ticks/uuid） |
| M6 | `=0` 且从不调认证服务 | 一次都没调 `/auth/verify`；1014 用的仍是硬编码 ticket（publisher=`314816420`），请求里的 `DevId` 被无视 |
| M7 | 开关开但取不到身份 | `mu_fallthrough=no-identity`，落回旧路径（硬编码 publisher=`314816420`），走单例 `SESSION` |
| **M8** | 8 线程同一身份首登 | 假 Shittim 只收到 **1 次** 1014（每 publisher 一把锁）；恰好 1 个 `fresh`、7 个 `cache`；8 个线程同一 AccountId、全部 200 |
| M9 | 两个身份并发 | 各铸一个账号（100001 / 100002）；**每个线程读到的 `SESSION.account_id` 都是自己的**（`MuSessionView` 按线程隔离）；共 2 次 1014 |
| M10 | 名字表里没有的 token + enforce | 信封 `protocol` 直接用客户端给的那个 token（`token-literal` 等价形状），0 次打 Shittim |
| M11 | 日志安全 | `mu_identity='3148.../aaaaaa...'`；`mu_*` 里没有全量 Token；真 `EnterTicket`（68 B）没进日志（`synth_checknexon` 已打码）；`Kind` 记了、`Card` 只留前 4 位 |

---

## §8 上线顺序（**先部署新版 sdkcard**）

1. **必须先部署新版 sdkcard**，确认 `POST http://127.0.0.1:8080/auth/verify` 可用：
   - 成功 `{"ok":true,"Kind":"normal|public","Card":"…"}`
   - 失败 `{"ok":false,"Reason":"bad_request|unknown_identity|device_revoked|expired"}`
   - **没部署就先开 `cn_auth_enforce=1` = 把所有玩家拦在门外。**
2. 备份 `/www/wwwroot/bapatch/tools/account_auth_probe.py` 与 Shittim 的 account DB。
3. 上传新 bridge（`--apply` 打出来的 153,728 B / `c8f1eb66…`），**先不建任何开关文件**（= 全关，
   行为与现网逐字节一致），重启，观察 `api_all_requests.log` 无异常。
4. 建 `cn_multiuser.txt=1`，**不建** `cn_auth_enforce.txt`（= 观察模式），重启。
   此时每人独立账号生效，token 只记录不拦。
5. 观察 1–2 天：
   ```bash
   grep -c '"mu_session_source": "fresh"'   /www/wwwroot/bapatch/logs/…   # 新铸会话数
   grep -c '"mu_fallthrough": "no-identity"' /www/wwwroot/bapatch/logs/…  # ★ 最关键的指标
   grep -o '"mu_verify_reason": "[^"]*"'     /www/wwwroot/bapatch/logs/… | sort | uniq -c
   grep -c '"mu_ensure_err"'                 /www/wwwroot/bapatch/logs/…
   ```
   - `mu_fallthrough=no-identity` 的比例必须接近 0。**只要它不是 0，那部分请求就还在用公共账号**
     —— 说明那个协议/那条路径的请求体里没有 `DevId`/`Token`，需要单独补抽取规则（见 §10）。
   - `mu_verify_reason` 里出现的 `unknown_identity` / `device_revoked` / `expired` 应当与
     sdkcard 自己的统计吻合；不吻合先别开 enforce。
6. 上述都对，再建 `cn_auth_enforce.txt=1`，重启。出问题立刻 `cn_auth_enforce.txt=0`（**不用**改补丁）。

> 注意：Shittim 会给没见过的 `publisherId` **自动建号**，所以第 4 步一开，每个玩家第一次登录都会
> 新建一个 Shittim 账号 —— 原来那个公共号 `314816420`（ServerId=2）上的存档**不会**被这些玩家
> 继承。这是预期行为，但必须先备份 account DB，并且想清楚"老存档怎么办"。

---

## §9 回滚

```powershell
python deploy\patch_multiuser.py --src <file> --rollback           # 优先用 .mu.bak.*（sha 必须 == 基线）
python deploy\patch_multiuser.py --src <file> --rollback --from-block-removal   # 不用备份，直接摘 3 块
```

两者都验证过：结果都是 **128,309 B / `e5fb03b87433741ed61ad6f7cc010707193fbd46d7c2086608fb0c11d66f5581`**，
零 `BAPATCH-MU` 残留。摘块后文件与基线**逐字节相同**（`--verify` 每次都会断言这一条）。

线上回滚还有两条等价路径：`cp -a <file>.mu.bak.<ts> <file>`，或者把 `cn_multiuser.txt` 删掉/写 0
（**行为立刻回到现状，不用改文件**）—— 后者才是应急首选。

---

## §10 已知边界 / 需要盯的地方

1. **分流成立的前提 = 每个请求都能取到 `(DevId, Token)`。** 取不到就 `mu_fallthrough=no-identity`
   落回公共账号（旧行为）。抽样看到的身份字段是在"解密后的请求片段"里，所以：
   - 只有 `exp=decrypt+…` 那条 path A 会自己记 `rec['req_Token']`；**本补丁的闸会自己解一次包**
     （多一次 `cn_cipher.decode_packet`，与 relay/relay2 的钩子同样的开销），不依赖 exp。
   - 如果某个协议客户端不带这两个字段，它会一直走旧路径 —— 上线观察期用 §8 的 grep 盯住。
2. **铸造失败不静默降级**：有身份但 Shittim 不给 `SessionKey` → 返回 `(None,None)`，和旧代码
   1014 失败一样回 500（`mu_fallthrough=mint-failed`）。**不会**偷偷换回公共账号（那等于把玩家
   的存档写到别人号上）。
3. **认证服务慢 = 游戏慢**：每个请求一次本机 `POST /auth/verify`，超时 2 秒。连不上/超时会放行，
   并触发 3 秒短熔断（熔断期间直接放行不等待）。所以 sdkcard 挂了游戏还能玩，但日志里会有大量
   `mu_verify_err`。熔断窗口、超时都是 `MU_VERIFY_TIMEOUT / MU_BREAKER_SEC` 常量，可按需调。
4. **`rec['req_Token']` 是旧代码（L1760）本来就会写的字段**，本补丁不改它（改了就不是"逐字节不变"）；
   本补丁自己新增的 `mu_*` 一律只记掩码。如果以后要收紧日志里的 token 暴露，应该单独做一次
   （会让日志逐字段变化，属于另一个补丁的范围）。
5. **`MuSessionView` 是运行时替换**：`cn_multiuser` 从 1 改回 0 之后建议重启进程（视图会回落读旧单例，
   值相同，只是类型不再 `is Session`）。
6. **`_relay_replay.py` 的 R0 / `_relay2_replay.py` 的 S0 会一直 FAIL**，因为它们把"摘掉本套件的块 ==
   当年基线"写死了。要它们转绿就得改成"== 上一层产物"，那是改夹具的活，不是改产物。
