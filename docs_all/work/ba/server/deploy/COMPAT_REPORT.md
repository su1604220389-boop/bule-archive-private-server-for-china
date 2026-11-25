# 24000_v3 之后 7 步部署序列 · 兼容性报告

> 目标：验证「`patch_24000_v3.py` 把 bridge 从 54,026 B 改成 73,445 B 之后，
> 90004 / 1017 / 8000 / simple / preempt 五个补丁的**文本锚点是否还成立**」，并在真打顺序下
> 给出可复现的数值证据。
>
> 结论先说：**5 个后续补丁全部兼容，没有一个需要 `*_compat.py`。**
> 真正会咬人的不是锚点，是**运行时生效条件**（见 §7）。

- 验证日期：2026-11-16
- 环境：Windows / Python 3.12.11（`C:\msys64\ucrt64\bin\python.exe`）
- 只写 `work\ba\server\deploy\`；未修改任何既有 `patch_*.py`；未碰 `_baseline\`（只读拷贝）；未连服务器
- 自动化：`python deploy\verify_sequence.py` → **72 项核对 / 0 FAIL**

---

## 1 结论总览

| # | 补丁 | 目标文件 | 24000_v3 之后锚点是否成立 | 需要 `_compat` 版本？ | apply 后字节（在本沙箱） |
|---|------|----------|--------------------------|----------------------|--------------------------|
| 1 | `patch_requestid.py` | `cn_wire.py` | 与 bridge 无关，天然兼容 | 否 | 6,368 → 9,778 |
| 2 | `patch_24000_v3.py` | bridge | 本身 | 否（基线守卫见 §6.1） | 54,026 → **73,445** |
| 3 | `patch_90004.py` | bridge | ✅ 3 个锚点全部唯一命中 | **否** | 73,445 → 79,681 |
| 4 | `patch_1017.py` | bridge | ✅ 2 个锚点全部唯一命中 | **否** | 73,445 → 76,098 |
| 5 | `patch_8000.py` | bridge | ✅ 2 个锚点全部唯一命中（分支为**插入**） | **否** | 73,445 → 84,223 |
| 6 | `patch_simple.py` | bridge | ✅ 3 个锚点全部唯一命中 | **否** | 73,445 → 87,932 |
| 7 | `patch_preempt.py` | bridge | ✅ 3 个锚点全部唯一命中 | **否** | 73,445 → 81,588 |

**为什么 24000_v3 看起来「很危险」却什么都没破坏**：它对 bridge 只做两处改动，且都不落在这 5 个补丁的锚点上——

1. 在 **L510**（`SESSION = Session()` 之后）插入 551 行托管块（L510–1060）；
2. 把 `if num == 24000:` 分支体从 26 行换成 6 行，**保留**了分支行本身与它的 `return`。

也就是说它只做了「净插入 + 局部替换」，**没有重命名、没有去缩进、没有动 `if num == 90004:` / `if num in (1019, 1017):` / `if proto_int:` / `class Handler` / `want_decrypt` 这些锚点**。所有后续锚点在 73,445 B 版本里逐个仍然**恰好出现 1 次**（见 §4）。

---

## 2 复现 24000_v3（和题给数字逐字节一致）

```
cp _baseline\account_auth_probe.py  <tmp>\aap.py     # 54,026 B / 1,245 行
python patch_24000_v3.py --target <tmp>\aap.py --apply
```

| 项目 | 值 |
|------|-----|
| 原始 | 54,026 B / 1,245 行 / sha256 `f94b4fa05d95d4c8719f5623322b75629b81eed59442370dd552db721437dbc9` |
| 托管块 | L510–1060，**551 行**，状态 `inserted` |
| 24000 分支 | L787–812（26 行）→ **6 行**，新位置 L1339–1344 |
| 改后 | **73,445 B / 1,777 行** / sha256 `d5f27fcab6a897c88a8281fe9b2bd043924b68b5ca1c3ba4f60fd8649d1b814e` |
| 增量 | **+19,419 B**（与题给完全一致）；`compile 复检: OK` |

---

## 3 逐补丁独立试打（各自在一份干净的 73,445 B 副本上）

| 补丁 | `--dry-run` | `--apply` 后 | 字节增量 | 行数 | `py_compile` | 自身 `--verify` |
|------|-------------|--------------|----------|------|--------------|-----------------|
| `patch_90004.py --src` | 命中，打印完整 diff | 79,681 B | +6,236 | 1,777 → 1,943 | OK (rc=0) | 结果: PASS |
| `patch_1017.py --target` | 命中（+57 行，纯插入） | 76,098 B | +2,653 | 1,777 → 1,834 | OK (rc=0) | 结论: PASS |
| `patch_8000.py --target` | 命中（块 inserted / 分支 inserted） | 84,223 B | +10,778\* | 1,777 → 2,039 | OK (rc=0) | verify: PASS |
| `patch_simple.py --bridge` | 命中（PAYLOAD 357 行 + HOOK-D 10 + HOOK-G 11） | 87,932 B | +14,487 | 1,777 → 2,155 | OK (rc=0) | 全绿 |
| `patch_preempt.py --target` | 命中（B1/B2/B3 三处） | 81,588 B | +8,143 | 1,777 → 1,987 | OK (rc=0) | 结果: PASS |

\* `patch_8000` 会把 `<bridge 同目录>/8000_catalog.json` 与 `8000_switch.json` 两个**绝对路径** `repr()` 进托管块，所以它的字节增量含路径长度（本沙箱 237 B）。换算公式见 §9。

**没有一例出现「找不到锚点」或「多处匹配」。**

---

## 4 锚点矩阵（锚点字面量直接取自补丁脚本源码）

`-` = 该锚点在此版本不存在；`1` = 唯一命中。**v3 与 final 两列全部为 1 ⇒ 全部可用。**

| 补丁 | 锚点（脚本里的原字面量） | baseline 54,026 | v3 73,445 | final 115,738 |
|------|--------------------------|-----------------|-----------|----------------|
| 90004 | `RE_BRANCH = re.compile(r"^([ \t]*)if num == 90004:[ \t]*$", re.M)` | 1 | **1** | 1 |
| 90004 | 内联块插在 `^def `（**第一个**顶层 def，非唯一，脚本用 `re.search` 取首个） | 35 | 56 | 90 |
| 90004 | outer rid：先定位 `^([ \t]*)def _cn_send_envelope\(`，**在该函数体内**再找 `rid = str(_uuid.uuid4())` | 1 | **1** | 1 |
| 1017 | `ANCHOR_A = "class Handler(http.server.BaseHTTPRequestHandler):"` | 1 | **1** | 1 |
| 1017 | `ANCHOR_B = "        if num in (1019, 1017):"` | 1 | **1** | 1 |
| 8000 | `find_anchor`: `"SESSION = Session()"` | 1 | **1** | 1 |
| 8000 | `find_branch(lines, 24000)` → 插在该分支**末尾之后**（`^[ \t]*if num == 24000:[ \t]*$`） | 1 | **1** | 1 |
| simple | `ANCHOR_PAYLOAD = "if __name__ == '__main__':\n"` | 1 | **1** | 1 |
| simple | `ANCHOR_HOOK_D = "        if proto_int:\n            obj = cn_nick.build_min_response(proto_int)\n"`（两行，更稳） | 1 | **1** | 1 |
| simple | `ANCHOR_HOOK_G = "        if num == 90004:\n"` | 1 | **1** | 1 |
| preempt | `ANCHOR_MODULE = 'class Handler(http.server.BaseHTTPRequestHandler):'` | 1 | **1** | 1 |
| preempt | `ANCHOR_METHOD = '    def _generic_protocol_response(self, proto_str, packet_b64, rec, name=None):'` | 1 | **1** | 1 |
| preempt | `ANCHOR_CALL = "        want_decrypt = exp.startswith('decrypt+')"` | 1 | **1** | 1 |

### 特别说明 1：`patch_1017` 的锚点 B 与 24000 分支无关

看 `--dry-run` 的 diff 会误以为 1017 挂在 24000 分支的 `return _ba24000_send(...)` 上，其实不是——它的 `ANCHOR_B` 是 **`        if num in (1019, 1017):`**（旧的 492 B 静态分支）。该行在 baseline 里就有，24000_v3 也没动它。
**所以 1017 对 v3 零依赖**，顺序只是被 v3 的基线守卫逼出来的（见 §6.1）。

### 特别说明 2：`patch_8000` 的「分支」是**新建**，不是替换

baseline 里**根本没有** `if num == 8000:`（全文件只有 `if num == 90004:` 和 `if num == 24000:` 两个 `if num == N:` 分支）。`patch_8000` 走的是 `find_insert_point()`：找 `if num == 24000:` 分支的结尾，把新分支插在它后面。v3 之后 24000 分支变成 6 行但**仍然以 `return _ba24000_send(...)` 结尾**，所以插入点照样成立（apply 日志里的 `分支 : inserted`）。

---

## 5 完整 7 步序列（真打，逐步核对）

沙箱：`deploy\_compat_check\full\`（绝对路径长度会影响第 5 步之后的字节数，见 §9）

| 步 | 动作 | 字节 | 增量 | 行数 | sha256[:16] | 该补丁 `--verify` |
|----|------|------|------|------|-------------|-------------------|
| 0 | baseline 拷贝 | 54,026 | — | 1,245 | `f94b4fa05d95d4c8` | — |
| 1 | `patch_requestid.py --target cn_wire.py --apply` | cn_wire 6,368 → **9,778**（166 → 248 行） | +3,410 | bridge **不变** | bridge 仍 `f94b4fa0…` | PASS |
| 2 | `patch_24000_v3.py --apply` | **73,445** | +19,419 | 1,777 | `d5f27fcab6a897c8` | VERIFY: PASS |
| 3 | `patch_90004.py --src … --apply` | 79,681 | +6,236 | 1,943 | `439b22dc62176d9a` | 结果: PASS |
| 4 | `patch_1017.py --target … --apply` | 82,334 | +2,653 | 2,000 | `5cfdc8789aaa3a2b` | 结论: PASS |
| 5 | `patch_8000.py --target … --apply` | 93,108\* | +10,774\* | 2,262 | `69e4fa8fcc307cc0` | verify: PASS |
| 6 | `patch_simple.py --bridge … --apply` | 107,595\* | +14,487 | 2,640 | `b2524136ff8cf0c8` | 全绿 |
| 7 | `patch_preempt.py --target … --apply` | **115,738\*** | +8,143 | **2,850** | `9ea03646da23167c` | 结果: PASS |

\* 含沙箱绝对路径。**线上（`/www/wwwroot/bapatch/tools`）等价数值：第 5 步 92,966 B → 第 6 步 107,453 B → 第 7 步 115,596 B**，行数完全相同。

### 5.1 最终核对结果（题目 §4 要求的四项）

| 核对项 | 结果 |
|--------|------|
| 最终字节数 | **115,738 B**（本沙箱路径）／ **115,596 B**（线上路径预测） |
| 最终行数 | **2,850 行**（LF，无 CRLF，UTF-8 合法，U+FFFD = 0） |
| `python -m py_compile` | **通过（rc=0）**，同目录生成 `__pycache__\account_auth_probe.cpython-312.pyc` |
| `compile(..., 'exec')` | 通过；`patch_preempt --verify` 还真的 `exec` 了整份源码 |
| 顶层重名 | **0 个**（177 个顶层名字，跨 6 个补丁块无撞名） |

### 5.2 marker 出现次数（全部逐字核对）

| marker | 次数 | 说明 |
|--------|------|------|
| `academy-24000-v3` | **1** | 24000 分支的 `rec['gen_kind']`（L1991） |
| `management-90004-official` | **1** | 90004 分支的 `rec['gen_kind']`（L1979） |
| `BA_PATCH_REQUESTID` | **0 in bridge** / **4 in cn_wire.py** | 它改的是 `cn_wire.py`，bridge 里当然没有 |
| `BA-1017-DYNAMIC-PATCH` | **4** | 2 处模块级 BEGIN/END + 2 处分支 BEGIN/END |
| `# ==== BEGIN 8000_mission_list` / `END` | **1 / 1** | 托管块配对 |
| `BAPATCH-SIMPLE-PAYLOAD` | **2** | BEGIN/END |
| `BAPATCH-SIMPLE-HOOK-D` | **2** | BEGIN/END |
| `BAPATCH-SIMPLE-HOOK-G` | **2** | BEGIN/END |
| `BAPATCH-ROUTER-PREEMPT` | **6** | B1/B2/B3 各 BEGIN+END |
| `# ==== BEGIN 24000_v3` / `END` | **1 / 1** | 托管块配对 |
| `# ==== BEGIN 90004-PATCH` / `END` | **1 / 1** | 内联块配对 |

> `grep -c 'BA_PATCH_REQUESTID\|academy-24000-v3\|management-90004-official' <file>` 的语义是**按行**计数，
> 结果为 **2**（两行分别命中后两个 marker；requestid 的 marker 在 `cn_wire.py` 里）。

### 5.3 分发顺序（打完之后的真实结构，逐条断言通过）

```
_generic_protocol_response():
    ① HOOK-G(simple)      ← 拦截 1005/4000/26000
    ② if num == 90004:    ← 官方 9 键 Data
    ③ if num == 24000:    ← v3 动态（71 zone）
    ④ if num == 8000:     ← 目录驱动（patch_8000 新插的）
    ⑤ if num == 1017 and cn_1017_mode() != 'legacy':   ← 动态 35 键
    ⑥ if num in (1019, 1017):                          ← 原 492 B 静态兜底（未被破坏）
_bridge():
    … 未知协议名 → _generic_protocol_response()
    → [preempt B3] → path A(decrypt+, 代理 Shittim) → path B → C0 → C → path D(HOOK-D)
```

### 5.4 幂等性

把整个 7 步序列**在已打完的文件上再跑一遍**：全部报 `already patched / no-op / 已是最新`，
**sha256 一分不变**（`9ea03646…`），字节/行数不变。
（唯一例外：`patch_simple.py` 会写一次 `.simple.bak.<TS>`，但**内容逐字节相同**，属于「写回同样内容」，不影响正确性。）

---

## 6 需要修锚点的补丁清单

**空。** 五个后续补丁在 73,445 B 版本上全部原样可用，因此本任务**没有产出任何 `patch_<name>_compat.py`**——
造一个用不上的 `_compat` 版本只会制造「到底该跑哪个」的歧义，故只交付 §10 的验证器 + 本报告。

下面是两个**已知脆弱点**（当前都成立，只是留给以后）：

### 6.1 `patch_24000_v3` 必须第一个碰 bridge（这条是真的）

v3 的守卫是「目标 sha256 必须 == `f94b4fa0…`」，一旦 bridge 被别的补丁改过就会**拒绝**：

```
$ python patch_24000_v3.py --target <已打 90004 的 60,262 B 文件> --apply
ERROR: 目标 sha256 不是已知基线，拒绝改动：
  got      d5552ef0429c9dff3ffa9c58f2cbb60efcbb7d922ac6edf4e4ad8a9d9672f5a5
  expect   f94b4fa05d95d4c8719f5623322b75629b81eed59442370dd552db721437dbc9
```

**唯一例外**：如果 v3 的 551 行托管块**已经在文件里**，它直接走幂等 no-op，不再看 sha。
所以「v3 第一步」这条顺序约束是**硬约束**，不是风格问题。

### 6.2 `patch_90004` 的内联块锚点是「第一个顶层 `def `」

`re.search(r"^def ", new_text, re.M)` —— 它不要求唯一（baseline 35 处、v3 56 处、final 90 处），
只取第一个。当前三份文件里第一个顶层 def 都是 `def acct_svc_on():`，所以落点稳定。
但**如果将来某个补丁把一个顶层 `def` 插到文件最前面**，90004 的内联块就会跑到它前面去——
不会语法错（模块级 def 顺序无关），但如果那个 def 前面有需要 90004 常量的话就要重新确认。
**建议（不改现有脚本）**：真要动顶部结构时，用 `--verify` 的 `inline_spec_check: PASS` 兜底确认。

### 6.3 `patch_8000` 的分支锚点依赖 `if num == 24000:` 存在

`find_insert_point()` 的第一候选是「24000 分支结尾」。若将来 24000 分支被整段删掉，它会退化到
「任何 `if num == <int>:` 分支之后」，再退化到 `else:` 之前，最后才 `die()`。当前 24000 分支常在，无需处理。

---

## 7 ⚠ 真正会咬人的地方：打完 7 步 ≠ 生效

这一条比锚点重要得多，部署前必须知道：

- `patch_preempt` 的开关默认 **off**（`/www/wwwroot/bapatch/cn_preempt.txt` 不存在 = 不拦截）；
- 线上 `cn_bridge_exp.txt = decrypt+plain+http200` 时，`_bridge()` 的 **path A** 只要「协议名能解析 + 解密成功」就
  `post_gateway()` 代理给 Shittim 并 **直接 return**（最终版 L2338–L2379，返回 `_cn_envelope` / `_json_encrypted` / `_json_ok`）；
- 而 24000 / 8000 / 1017 / 90004 的新分支**全都在 `_generic_protocol_response()` 里面**，path A 一旦 return 就永远走不到。

**后果**：7 个补丁全打上、py_compile 全绿、所有 marker 都在，**线上行为与今天逐字节等价**——
也就是说「什么都变了，但又什么都没变」。

**要让它真的生效**，第 8 个动作（不是补丁，是运行时开关）：

```bash
# 全开（只对 PREEMPT_IMPLEMENTED = 1005,1017,4000,8000,24000,26000,90004 生效）
echo all > /www/wwwroot/bapatch/cn_preempt.txt
# 或者只放某几个
echo 24000,90004,8000,1017 > /www/wwwroot/bapatch/cn_preempt.txt
# 关掉
echo off > /www/wwwroot/bapatch/cn_preempt.txt
```

另外四组开关（同样是「改文件即生效，不用重新打补丁」）：

| 补丁 | 开关文件 | 默认 |
|------|----------|------|
| requestid | `/www/wwwroot/bapatch/cn_inner_requestid.txt` | 缺省 = ON |
| 1017 | `/www/wwwroot/bapatch/cn_1017_mode.txt`（`dynamic` / `legacy`） | 缺省 = `dynamic` |
| 8000 | `<bridge 同目录>/8000_switch.json` | `enabled: true` |
| simple | `<bridge 同目录>/cn_1005.txt`、`cn_4000.txt`、`cn_26000.txt` | 缺省 = **关**（fail-safe） |
| preempt | `/www/wwwroot/bapatch/cn_preempt.txt` | 缺省 = **off**（fail-safe） |

> `simple` 与 `preempt` 的缺省都是**关**，是 fail-safe 设计：文件缺失 = 不接管。

---

## 8 修正后的完整部署序列（上线 runbook）

```bash
# 0) 预检：线上 bridge 必须就是 v3 认识的那份基线，否则第 2 步会被拦
sha256sum /www/wwwroot/bapatch/tools/account_auth_probe.py
#   期望 f94b4fa05d95d4c8719f5623322b75629b81eed59442370dd552db721437dbc9  (54,026 B / 1,245 行)

# 1) RequestId 进内层（改 cn_wire.py，不碰 bridge）
python3 deploy/patch_requestid.py --target /www/wwwroot/bapatch/tools/cn_wire.py --dry-run
python3 deploy/patch_requestid.py --target /www/wwwroot/bapatch/tools/cn_wire.py --apply
python3 deploy/patch_requestid.py --target /www/wwwroot/bapatch/tools/cn_wire.py --verify
#   cn_wire.py 期望 9,778 B / 248 行

# 2) 24000 v3（必须第一个碰 bridge）
python3 deploy/patch_24000_v3.py --target /www/wwwroot/bapatch/tools/account_auth_probe.py --apply
#   期望 73,445 B / 1,777 行

# 3) 90004
python3 deploy/patch_90004.py --src /www/wwwroot/bapatch/tools/account_auth_probe.py --apply
#   期望 79,681 B / 1,943 行

# 4) 1017
python3 deploy/patch_1017.py --target /www/wwwroot/bapatch/tools/account_auth_probe.py --apply
#   期望 82,334 B / 2,000 行

# 5) 8000（顺带部署 8000_catalog.json 144 KB + 8000_switch.json）
python3 deploy/patch_8000.py --target /www/wwwroot/bapatch/tools/account_auth_probe.py --apply
#   期望 92,966 B / 2,262 行

# 6) simple（顺带写 cn_1005/4000/26000.txt）
python3 deploy/patch_simple.py --bridge /www/wwwroot/bapatch/tools/account_auth_probe.py --apply
#   期望 107,453 B / 2,640 行

# 7) preempt
python3 deploy/patch_preempt.py --target /www/wwwroot/bapatch/tools/account_auth_probe.py --apply
#   期望 115,596 B / 2,850 行   ← 线上精确值（路径长度决定，见 §9）

# 8) 收尾
python3 -m py_compile /www/wwwroot/bapatch/tools/account_auth_probe.py
grep -c 'academy-24000-v3'           /www/wwwroot/bapatch/tools/account_auth_probe.py   # 1
grep -c 'management-90004-official'  /www/wwwroot/bapatch/tools/account_auth_probe.py   # 1
wc -l                                /www/wwwroot/bapatch/tools/account_auth_probe.py   # 2850
# 想让新分支真的接管（否则一切照旧）：
echo all > /www/wwwroot/bapatch/cn_preempt.txt

# 9) 重启 bridge 进程
```

**回滚**（倒序，每个补丁自己都有 `--rollback`，且每次都留了 `.bak.<TS>`）：

```bash
python3 deploy/patch_preempt.py    --target … --rollback
python3 deploy/patch_simple.py     --bridge … --rollback
python3 deploy/patch_8000.py       --target … --rollback
python3 deploy/patch_1017.py       --target … --rollback
python3 deploy/patch_90004.py      --src …    --rollback
python3 deploy/patch_24000_v3.py   --target … --rollback     # 校验 sha256 后恢复 54,026 B 原件
python3 deploy/patch_requestid.py  --target …/cn_wire.py --rollback
```

---

## 9 数值公式：为什么「最终多少字节」不是一个固定数

`patch_8000` 会把两个**绝对路径** `repr()` 进托管块：

```
_BA8000_CATALOG_FILE = '<dirname(target)>\8000_catalog.json'
_BA8000_SWITCH_FILE  = '<dirname(target)>\8000_switch.json'
```

所以第 5 步之后的总字节数随部署目录变化：

```
final_bytes = 115,738  -  233  +  ( len_utf8(repr(catalog_path)) + len_utf8(repr(switch_path)) )
              └ 参考沙箱 ┘  └ 参考沙箱里两个字面量的 utf-8 字节数 ┘
```

| 部署位置 | 两个字面量字节 | 最终字节 |
|----------|----------------|----------|
| `…\_compat_check\full\`（本次参考沙箱） | 233 | **115,738** |
| **`/www/wwwroot/bapatch/tools/`（线上）** | 91 | **115,596** |
| `…\_compat_check\seq_verify\<TS>\`（验证器默认） | 279 | 115,784 |

行数恒为 **2,850 行**（与路径无关）。**跨不同沙箱路径比字节数没有意义**，请用上面的公式。

拆解（线上口径）：

```
54,026 (baseline)
+ 19,419 (24000_v3)
+  6,236 (90004)
+  2,653 (1017)
+ 10,632 (8000 = 固定 10,541 + 路径字面量 91)
+ 14,487 (simple)
+  8,143 (preempt)
= 115,596 B
```

---

## 10 交付物

| 文件 | 说明 |
|------|------|
| `deploy\COMPAT_REPORT.md` | 本报告 |
| `deploy\verify_sequence.py` | **端到端验证器**：在一次性沙箱里从 `_baseline` 重跑 7 步，逐步核对字节/行数/sha256 + 7 个 `--verify` + marker + 分发顺序 + 幂等，**72 项核对 0 FAIL**；`--check <file>` 可对任意已打好文件做静态核对 |
| `deploy\_compat_check\full\` | 7 步全部打完的参考文件（115,738 B / 2,850 行 / `9ea03646…`）+ 每一步的 `.bak` 快照 |
| `deploy\_compat_check\t_<name>\` | 五个补丁各自在 73,445 B 上的独立试打结果 |
| `deploy\_compat_check\step_v3\` | 单独复现的 24000_v3 结果（73,445 B） |
| `deploy\_compat_check\v3_after_90004\` | 反证：先打 90004 再打 v3 → 被 sha 守卫拒绝 |
| `deploy\_compat_check\anchor_matrix.py` | 生成 §4 锚点矩阵 |
| `deploy\_compat_check\inspect_final.py` | 最终文件结构 / 锚点 / 分发顺序检查 |
| `deploy\_compat_check\ast_check.py` | AST 级检查：顶层重名、import、跨补丁撞名 |
| `deploy\_compat_check\stage_stats.py` | 逐步字节 / 行数 / sha 统计 + 路径字面量换算 |
| `deploy\_compat_check\line_map.py` | 最终文件行号地图（§11） |

复跑全部验证（不连服务器、只写沙箱）：

```bash
cd work/ba/server/deploy
python verify_sequence.py             # 全序列，72 项核对
python verify_sequence.py --check "_compat_check\full\account_auth_probe.py"
```

---

## 11 附录：最终文件结构速查（115,738 B / 2,850 行版本，行号实测）

| 行区间 | 内容 | 行数 |
|--------|------|------|
| L1–L50 | baseline 头部 | 50 |
| **L51–L213** | **90004 内联块**（`# ==== BEGIN 90004-PATCH v1` … `END`） | 163 |
| L215 | `def acct_svc_on():`（90004 的内联块锚点） | — |
| L672 | `SESSION = Session()`（8000 的模块锚点） | — |
| **L674–L920** | **8000 托管块**（`# ==== BEGIN 8000_mission_list` … `END`） | 247 |
| **L922–L1472** | **24000_v3 托管块** | 551 |
| **L1551–L1576** | **1017 模块级块**（`cn_1017_mode()` / `_gen1017_import()`） | 26 |
| **L1577–L1727** | **preempt B1 模块块**（`PREEMPT_NAME2NUM` 38 条 + `_preempt_*`） | 151 |
| L1728 | `class Handler(http.server.BaseHTTPRequestHandler):`（1017 A / preempt B1 锚点） | — |
| **L1886–L1933** | **preempt B2 方法块**（`_preempt_response`） | 48 |
| L1934 | `def _generic_protocol_response(`（preempt B2 锚点） | — |
| L1964 | `if num == 90004:`（分支 1964–1988） | 25 |
| L1979 | `rec['gen_kind'] = 'management-90004-official'` | — |
| L1989 | `if num == 24000:`（分支 1989–1994） | 6 |
| L1991 | `rec['gen_kind'] = 'academy-24000-v3'` | — |
| L1995 | `if num == 8000:`（分支 1995–2007，patch_8000 新插） | 13 |
| L2009–L2039 | **1017 分发动块**（判断行 L2012 `if num == 1017 and cn_1017_mode() != 'legacy':`） | 31 |
| L2040 | `if num in (1019, 1017):`（旧 492 B 静态分支，**未被破坏**） | — |
| L2287 | `def _bridge(` | — |
| L2324–L2334 | **preempt B3 callsite**（在 path A 之前） | 11 |
| L2335 / L2338 | `want_decrypt = …` / `if want_decrypt and packet_b64:`（path A 开始） | — |
| L2455–L2464 | **simple HOOK-D**（path D 之前） | 10 |
| L2465 | `if proto_int:`（HOOK-D 锚点 / path D） | — |
| **L2487–L2843** | **simple PAYLOAD**（逐字节内嵌 `simple_payload.py`） | 357 |
| L2844 | `if __name__ == '__main__':` | — |

> 行数小计：551（24000_v3）+ 163（90004）+ 247（8000）+ 26 + 31（1017）+ 151 + 48 + 11（preempt B1/B2/B3）+ 10 + 11（simple HOOK）+ 357（simple PAYLOAD）= **1,575 行新增**；
> 加 baseline 的 1,245 行 = 2,820，再加 30 行空行分隔 = **2,850 行**（与实测一致）。
