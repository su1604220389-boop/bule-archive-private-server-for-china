# DEPLOY_PLAN.md —— account_auth_probe.py 六线补丁整合部署方案

> 只写 `work/ba/server/deploy/` 下的新文件；没有改动任何已有 `patch_*.py` / `gen_*.py`，
> 没有碰 `_baseline/`，没有连服务器。所有结论都是在本仓库上用 `_baseline` 的副本跑出来的。
>
> 本文所有数值都是**实测**（2026-11-16 05:28–05:38 Asia/Shanghai），不是推算。

---

## 0. 基线与快照

| 项 | 值 |
|---|---|
| 基线文件 | `deploy/_baseline/account_auth_probe.py` |
| 大小 / 行数 | **54,026 B / 1,245 行**（LF 行尾，无 BOM） |
| sha256 | `f94b4fa05d95d4c8719f5623322b75629b81eed59442370dd552db721437dbc9` |
| 线上 gen_kind | `academy-24000-e2`（11-14 15:38 那版） |

参与整合的脚本快照（本次分析的输入；其它 agent 仍在改这几个文件，数值以 sha 为准）：

| 脚本 | 大小 | sha256（前 16） |
|---|---|---|
| `patch_requestid.py` | 57,287 B | `a1fbffe9a8991834` |
| `patch_24000_v2.py` | 43,213 B | `43525e67a64bd767` |
| `patch_24000_v3.py` | 60,504 B | `2b04254dbd31f213` |
| `patch_90004.py` | 30,946 B | `c94bae46d6d05294` |
| `patch_1017.py` | 32,071 B | `b5eb6d971e15d501` |
| `patch_8000.py` | 42,964 B | `045c28d9f4b58469` |
| `patch_simple.py` | 26,656 B | `3c596ee243dd0b4a` |
| `patch_preempt.py`（本次新增） | 43,461 B | —— |

> **patch_24000_v3 是在本次整合过程中出现的**（05:29）。v2 如果存在则默认用 v3；
> `deploy_all.py --24000-script patch_24000_v2.py` 可以切回 v2。

---

## 1. 冲突分析（逐补丁 × 锚点 × 54,026 B 基线）

判定方法不是"肉眼看字符串"，而是**让每个补丁自己的 `--dry-run` / `--apply` 去打基线的副本**，
再看 exit code + marker + `py_compile`。两套证据都列在下面。

| 补丁 | 改哪个文件的哪一段 | 锚点字符串 | 在 54,026 B 基线上能否匹配 | 与谁冲突 |
|---|---|---|---|---|
| `patch_requestid.py` | **`cn_wire.py`（不是 bridge！）**`build_plaintext()`：插 helper 块 + 插一行调用 | `def build_plaintext(`（SIG）；`requestid = requestid or str(uuid.uuid4())`；`plain = json.dumps({` | 基线里没有这个文件。在**cn_wire 替身**上实测：apply exit=0，helper 1 处、调用语句 1 处、`py_compile` PASS、功能 PASS | 无文本冲突（另一个文件）。与 90004 是**语义耦合**，见 §1.1 |
| `patch_24000_v2.py` | bridge：① 模块级托管块插到 `SESSION = Session()` **之后**；② 整段替换 `if num == 24000:` 分支体 | `^(\s*)if num == 24000:\s*$`（1 处）；`SESSION = Session()`（1 处） | **OK**。实测 apply exit=0，+17,559 B，marker `24000_v2` 各 1/1，py_compile PASS | 与 8000 抢同一个模块级插入点（都能成立，只是块顺序不同） |
| `patch_24000_v3.py` | 同上，块标记换成 `24000_v3`，并会顺手拆掉 v2 的托管块 | 同上 + **基线守卫**：目标 sha256 必须 == `f94b4fa0…`，否则 exit 2 | **OK，但只对原始件成立**。实测在打了 90004 之后再打 v3：`ERROR: 目标 sha256 不是已知基线，拒绝改动`（exit 2） | 与"前面已经改过 bridge 的补丁"**顺序冲突** → v3 必须第一个碰 bridge（见 §2） |
| `patch_90004.py` | bridge：① 整段替换 `if num == 90004:` 分支体；② 内联 `dto90004.py` 顶层语句；③ 改 `_cn_send_envelope` 的 `rid` 行 | `^([ \t]*)if num == 90004:[ \t]*$`（**1 处**）；`^def `（**35 处，取第一个** = L51 `def acct_svc_on():`，决定论安全）；`^([ \t]*)rid = str\(_uuid\.uuid4\(\)\)[ \t]*$`（**全文 6 处**，但它把搜索范围**限定在 `_cn_send_envelope` 函数体内**，段内 1 处 → 决定论安全） | **OK**。实测 apply exit=0，+6,236 B，marker 各 1/1，py_compile PASS | 无（`rid` 6 处容易被误判成"多处匹配"，实际有作用域保护） |
| `patch_1017.py` | bridge：① block_a 插到 `class Handler(...)` **之前**（模块级）；② block_b 插到 `if num in (1019, 1017):` **之前** | `class Handler(http.server.BaseHTTPRequestHandler):`（1 处）；`        if num in (1019, 1017):`（1 处）+ 紧跟的 **7 行逐字比对**（`LEGACY_BLOCK`） | **OK**。实测 apply exit=0，+2,653 B，marker BEGIN/END 各 **2/2**，py_compile PASS | 与 `patch_preempt` 抢**同一个** `class Handler` 之前的位置 → 1017 必须先打（见 §2） |
| `patch_8000.py` | bridge：① 模块级托管块插到 `SESSION = Session()` **之后**；② 新插一个 `if num == 8000:` 分支 | `SESSION = Session()`（1 处）；**插入点 = `if num == 24000:` 分支的结束行**（`find_insert_point`） | **OK**。实测 apply exit=0，+10,776 B，marker 各 1/1，py_compile PASS | 插入点依赖 24000 分支 → 语义上 24000 要先定型；实际两种顺序都能成 |
| `patch_simple.py` | bridge：三块 —— PAYLOAD 插到 `if __name__ == '__main__':` 之前；HOOK-D 插到 path D 的 `if proto_int:` 之前；HOOK-G 插到 `if num == 90004:` 之前 | `if __name__ == '__main__':`（1 处）；`        if proto_int:` + `            obj = cn_nick.build_min_response(proto_int)`（1 处，两行连读）；`        if num == 90004:`（1 处） | **OK**。实测 apply exit=0，+14,487 B，3 个 BEGIN 各 1/1，py_compile PASS | 与 90004 抢 `if num == 90004:` 附近 → 两种顺序都能成；与 24000/8000 抢 path D 区域 → 不重叠 |
| `patch_preempt.py`（新） | bridge：① B1 模块级块插到 `class Handler(...)` 之前；② B2 方法插到 `    def _generic_protocol_response(` 之前；③ B3 调用点插到 `        want_decrypt = ...` 之前 | `class Handler(http.server.BaseHTTPRequestHandler):`（1 处）；`    def _generic_protocol_response(self, proto_str, packet_b64, rec, name=None):`（1 处）；`        want_decrypt = exp.startswith('decrypt+')`（1 处） | **OK**。在**已打完前 6 个补丁的 115,740 B 文件**上 apply exit=0，+8,143 B，三块 marker 各 1/1，36 项自检全 PASS | 与 1017 抢 `class Handler` 之前 → preempt 必须最后打 |

打完 7 步之后，**上面所有锚点仍然各唯一**（实测：`class Handler` 1、`_generic_protocol_response` 1、
`want_decrypt` 1、`if num == 24000:` 1、`if num == 90004:` 1、`Session()` 1），
所以任何一个补丁都能单独重跑（幂等）或单独回滚。

### 1.1 关于"patch_90004 与 patch_requestid 冲突"

**结论：没有文本冲突，它们是两个不同的文件。**

* `patch_requestid.py` 的 `LIVE_TARGET = /www/wwwroot/bapatch/tools/cn_wire.py`，它只改
  `cn_wire.build_plaintext()` —— 信封层唯一 choke point。
* `patch_90004.py` 改的是 `account_auth_probe.py`：`if num == 90004:` 分支体、内联 DTO 块，
  以及 `_cn_send_envelope()` 里那一行 `rid = ...`。

它们的关系是**语义耦合**，不是冲突：

```
官方不变量：outer.requestid == inner packet.RequestId   （109/109 抓包）
                                          ↑
patch_requestid：在 build_plaintext 里把 outer rid 写进 inner RequestId
                                          ↑
patch_90004：    把 _cn_send_envelope 的 outer rid 改成 obj['RequestId']（而不是新造一个 uuid4）
```

* 只打 requestid：outer == inner 仍然成立（cn_wire 会把 inner 覆盖成 outer 那个 uuid），
  但 `_cn_send_envelope` 每回都新造 rid，`obj['RequestId']` 会被覆盖 —— 结果是"一致但多绕一圈"。
* 只打 90004：`_cn_send_envelope` 的 rid 来自 `obj['RequestId']`，但 inner 里没有这个字段
  → **outer != inner**，客户端的 REQUEST-ID 链还是断的。
* 两个都打：数据单向流动，无来回覆盖 —— 这是要的状态。

所以顺序上 **requestid 先、90004 后**：先立通道，再谈"把哪个值放进通道"。

---

## 2. 应用顺序（经论证）

`deploy_all.py` 里的实际顺序：

| 步 | 补丁 | 目标 | 这一步之后文件大小 | 累计 sha256（前 16） |
|---|---|---|---|---|
| — | 基线 | —— | 54,026 B | `f94b4fa05d95d4c8` |
| 1 | `patch_requestid.py` | **cn_wire.py** | cn_wire 替身 1,005 → 4,415 B | 不变 |
| 2 | `patch_24000_v3.py` | bridge | 73,445 B | `d5f27fcab6a897c8` |
| 3 | `patch_90004.py` | bridge | 79,681 B | `439b22dc62176d9a` |
| 4 | `patch_1017.py` | bridge | 82,334 B | `5cfdc8789aaa3a2b` |
| 5 | `patch_8000.py` | bridge | 93,110 B | `23bf5116760d37bb` |
| 6 | `patch_simple.py` | bridge | 107,597 B | `8e178727551ccba2` |
| 7 | `patch_preempt.py` | bridge | **115,740 B / 2,850 行** | `438ee1f0884299e8` |

### 为什么是这个顺序（4 条硬理由，不是口味）

1. **`patch_requestid` 第一**：它是唯一改 cn_wire 的，不动 bridge，所以放在最前不占"bridge 已经被改过"
   这个名额；同时 §1.1 的语义链要求先立通道。

2. **`patch_24000_v3` 第二（必须第一个碰 bridge）**：v3 有**基线守卫** —— 目标 sha256 必须等于
   `f94b4fa0…`，否则 `exit 2 拒绝改动`。实测把 90004 先打上去之后 v3 就罢工了。
   所以它必须拿到还没被任何补丁动过的 bridge。
   （如果非要在别人的半成品上续跑，`deploy_all.py` 会自动补 `--allow-other-baseline` 并**打印原因**；
     实测 dirty 目标 + 自动放行后，最终产物与干净跑完全一致：都是 115,740 B / `3504a6a4…`。）

3. **`patch_8000` 在 `patch_24000` 之后**：`patch_8000.find_insert_point()` 用
   `if num == 24000:` 分支的**结束位置**当插入锚。让 24000 先定型，8000 插进去的位置就是终态位置，
   而不是插在一个马上要被整段重写的旧分支后面。
   （实测反序也能成 —— 24000 的 `find_branch` 靠缩进回退，会停在 8000 分支那一行，不会吃掉它。
     但"能成"和"位置确定"是两件事，选确定的那个。）

4. **`patch_preempt` 最后**：两点。
   (a) 它和 `patch_1017` 抢同一个 `class Handler(...)` 之前的插入点 —— 1017 先打，preempt 就紧挨在
       1017 的 block_a 之后，位置确定；反序则反过来。
   (b) 它的 `--verify` 要枚举"已实现协议集合"，必须等其它分支都在位才谈得上验证。

### 顺序到底有多敏感（实测）

同一目录下，24000 之后那 5 个 bridge 补丁的**任意排列**都成功，产物**字节数/行数完全相同**
（107,603 B / 2,640 行，不含 preempt）：

```
A 24000>90004>1017>8000>simple  107603 B 2640 行  全部 exit=0
B 24000>1017>simple>8000>90004  107603 B 2640 行  全部 exit=0
C 24000>8000>simple>1017>90004  107603 B 2640 行  全部 exit=0
```

sha 不同（3 种 sha），但差异**只有 2 个 diff hunk**、且都是"`24000_v3` 托管块与
`8000_mission_list` 托管块谁在前"—— 因为两者的模块级插入点都是 `SESSION = Session()`。

> 注意：跨目录比较会有几字节差异，因为 8000 的托管块里**内嵌了绝对路径**
> （`_BA8000_CATALOG_FILE` / `_BA8000_SWITCH_FILE`）。同一目录下比较才干净。

**一句话**：文本上七步可交换，但上有两条顺序硬约束（v3 的基线守卫、preempt 与 1017 抢锚点），
所以固定成上表这个顺序；顺序固定的代价是 0，收益是"每一步的位置都确定"。

### 每一步之后怎么验证"前面的补丁没被破坏"

`deploy_all.py --apply` **每步自动做这 4 件事**，任何一项不过就立刻停在那一步：

1. **本步 marker 数量正确**（见 §1 表格里的期望值；比如 simple 是 3 个 BEGIN 各 1 次，1017 是 2/2）
2. **之前所有已应用步骤的 marker 仍然正确**（这是"没被互相覆盖"的直接证据）
3. **`python -m py_compile` 通过**（子进程跑，和线上重启前的检查同一条命令）
4. 失败即停，打印已完成步骤 + 立刻回退的命令，**不会再往下打**

实测 7 步全程：每一步 `marker PASS` + `之前补丁完好: PASS` + `py_compile: PASS`。

另外每个补丁自己的 `--verify` 在**打满 7 步之后**依然全绿（实测）：

```
patch_24000_v3 --verify   exit=0
patch_1017     --verify   exit=0
patch_8000     --verify   exit=0   三个 profile 的 spec_check 全 PASS
patch_90004    --verify   exit=0
patch_simple   --verify   exit=0   PASS
patch_preempt  --verify   exit=0   36 项全 PASS
```

---

## 3. path A 问题（最关键的架构问题）与解法

### 3.1 问题

线上 `cn_bridge_exp.txt = decrypt+plain+http200`，于是 `_bridge()` 里：

```python
L1080  if exp == 'experror': ...                       # 不相关
L1088  if name is None:                                # ← 名字解析不到才走这里
           got = self._generic_protocol_response(...)  #    我们的分支住在这个函数里
           ...
L1097  want_decrypt = exp.startswith('decrypt+')       # ← True
L1100  if want_decrypt and packet_b64:                 # ← path A
           r = cn_cipher.decode_packet(...)            # 解密成功
           ...  post_gateway(req_json)                 # 代理给 Shittim
           return self._cn_envelope / _json_ok(...)    # **直接 return**
```

=> **只要协议名能解析（`NAME_TABLE` 命中）+ 解密成功，path A 就赢了并直接返回**，
   我们写的 1005 / 4000 / 26000 / 8000 分支是**死代码**。

`--verify` 把每个协议的"线上入口"算出来了（用 bridge 自己的 `load_names()` + `b32md5()` 判定）：

| 协议 | 名字 | 线上入口 | 靠什么生效 |
|---|---|---|---|
| 24000 | `Academy_GetInfo` | **L1088 直通** | 名字不在表里 → 天然走 `_generic_protocol_response`，不依赖 preempt |
| 1017 | `Account_LoginSync` | **L1088 直通** | 同上 |
| 90004 | `Management_Data` | **L1088 直通** | 同上 |
| 4000 | `Item_List` | L1088 直通 | 同上（**但线上 protocol_names.txt 可能补上这个名字，见下**） |
| 26000 | `ContentSave_Get` | L1088 直通 | 同上 |
| **1005** | `Account_GetTutorial` | **path-A 拦截** | 名字在 `BUILTIN_NAMES` 里 → **必须 preempt** |
| **8000** | `Mission_List` | **path-A 拦截** | 名字在 `BUILTIN_NAMES` 里 → **必须 preempt** |

> **重要**：本地只有 `BUILTIN_NAMES`（45 个）能判定；线上还会读
> `/www/wwwroot/bapatch/tools/protocol_names.txt`，那个文件里可能还有
> `Academy_GetInfo` / `Item_List` / `ContentSave_Get` …… —— 一旦出现在里面，
> 它们就立刻变成"path-A 拦截"，branch 变死代码。
> **所以白名单不要只写 1005,8000，要么写 `all`，要么把 7 个号全列上。**

### 3.2 解法：`patch_preempt.py`（协议白名单拦截）

在 `want_decrypt = ...`（L1097）**之前**插一次白名单拦截：

```python
        # >>> BAPATCH-ROUTER-PREEMPT v1 BEGIN (B3-callsite) >>>
        try:
            _pre_r = self._preempt_response(name, proto_str, packet_b64, rec)
            if _pre_r is not None:
                return _pre_r
        except Exception as _e_pre:
            rec['preempt_err'] = repr(_e_pre)
        # <<< BAPATCH-ROUTER-PREEMPT v1 END (B3-callsite) <<<
```

命中白名单 → 交给 `_generic_protocol_response()`（它内部已有各协议的**真实分支**）；
未命中 → 什么都不做，原样继续走 path A 代理 Shittim（**= 今天的线上行为，逐字节等价**）。

设计要点：

* **不重新实现任何协议**。preempt 只做**路由**，真正的应答仍然来自各补丁自己的分支
  （`_ba24000_build` / `gen1017` / `_ba8000_build` / `simple_route` / `build_90004_management_data`）。
  这样以后加协议，只要往 `_generic_protocol_response` 里加分支即可，路由器不用改。
* **开关文件** `/www/wwwroot/bapatch/cn_preempt.txt`（大小写不敏感）：

  | 内容 | 含义 |
  |---|---|
  | （文件不存在）/ `off` / `0` / `false` / `no` / `none` | **不拦截 = 默认 = 今天的线上行为** |
  | `all` | 拦截 `PREEMPT_IMPLEMENTED` 全集 |
  | `all+` | 拦截任何能解出协议号的请求（调试用，慎用） |
  | `24000,1017,8000` | 只拦这些（逗号/分号/空白分隔） |

  路径优先级：`$CN_PREEMPT_FILE` → `/www/wwwroot/bapatch/cn_preempt.txt` → `<bridge 同目录>/cn_preempt.txt`。
  另支持 `$CN_PREEMPT` 直接给值（只给测试用，免得为跑一次用例去写开关文件）。

* **默认 `off`**：装上去不改变任何线上行为。等其它补丁都验证完了再 `--switch`。

### 3.3 三条安全边界（都能被 `--verify` 实测，不是口头承诺）

1. **白名单只能从 `PREEMPT_IMPLEMENTED` 里选子集** ——
   `(1005, 1017, 4000, 8000, 24000, 26000, 90004)`。
   开关里写一个没实现的号码**不会生效**：`all + 未实现协议(28000) -> skip`。
   **换开关永远变不出实现。**
2. **命中白名单、但内部仍然落到 `min+base` 兜底（7 个假键）→ 不接管**。
   `_generic_protocol_response()` 的兜底 `else:` 分支会把 `rec['gen_kind']` 写成 `min+base`，
   这是"没有真正分支"的唯一可靠指纹。判定为兜底就**原路返回给 path A 代理**，
   不拿假包去顶。实测：`all + 已实现协议只剩 min+base 兜底 -> fallthrough（不接管）`。
   > 顺带一个好处：1005/4000/26000 的开关文件（`cn_1005.txt` 等）关掉时，
   > HOOK-G 返回 None → 继续落到 `min+base` → preempt 判 fallthrough → 回 path A 代理。
   > 也就是"关掉就安全退回代理"，不会卡在半截。
3. **任何异常只写 `rec['preempt_err']`，随后原路返回**。
   实测：`内部分支抛异常 -> 不接管，只记 preempt_err`（`preempt='error'`），不会让别的协议 500。

`patch_preempt.py --verify` 一共 **40 项检查**（结构 10 + 行为 30），全 PASS：

* 结构 10：B1/B2/B3 各 1 次、三个锚点仍唯一、B1 在 `class Handler` 之前、
  B2 在 `_generic_protocol_response` 之前且在类内、B3 在 `want_decrypt` 之前、
  B3 落在 `_bridge()` 体内、`compile()` 通过
* 行为 30：exec 打补丁后的源码、`Handler._preempt_response` 存在、**开关解析 11 项**、
  **判定矩阵 9 项**、名字表/`req_Hash`/明文 Hash 解析 4 项、`PREEMPT_IMPLEMENTED` 一致性 2 项

---

## 4. 部署操作（`deploy_all.py`）

```
python deploy/deploy_all.py --dry-run      # 副本上真跑一遍 + 每步 diff 预览，正式文件 0 字节改动
python deploy/deploy_all.py --apply        # 按顺序打 + 逐步自检 + 收尾全量 verify
python deploy/deploy_all.py --verify       # 全量验证
python deploy/deploy_all.py --rollback     # 逆序一次性回滚（最后比 sha256，不符用原件覆盖）
python deploy/deploy_all.py --status       # 每个补丁的应用状态
```

线上正式用法：

```
cd /www/wwwroot/bapatch
python3 deploy/deploy_all.py --target /www/wwwroot/bapatch/tools/account_auth_probe.py \
                            --cn-wire /www/wwwroot/bapatch/tools/cn_wire.py --dry-run
# 看没问题
python3 deploy/deploy_all.py --target /www/wwwroot/bapatch/tools/account_auth_probe.py \
                            --cn-wire /www/wwwroot/bapatch/tools/cn_wire.py --apply
# 重启 bridge（不重启不生效）
pkill -f account_auth_probe.py
nohup python3 /www/wwwroot/bapatch/tools/account_auth_probe.py >> /www/wwwroot/bapatch/logs/bridge.out 2>&1 &
python3 deploy/deploy_all.py --target ... --verify
# 全绿之后再开拦截（先 all，看日志，也可以先只开一个号）
python3 deploy/patch_preempt.py --target /www/wwwroot/bapatch/tools/account_auth_probe.py \
        --switch-file /www/wwwroot/bapatch/cn_preempt.txt --switch 8000
```

`--apply` 会额外落三个东西：
* `<target>.bapatch_orig.<ts>` —— 部署前的原始件（一次性回滚的兜底）
* `<target>.bapatch_deploy.json` —— manifest：原始 sha、每步 before/after sha、顺序
* 每个补丁自己的 `.bak.*`（它们各自的 `--rollback` 要用）

---

## 5. 回滚

### 5.1 每一步单独回滚（按需，不删别的补丁）

```bash
BR=/www/wwwroot/bapatch/tools/account_auth_probe.py
D=/www/wwwroot/bapatch/deploy

python3 $D/patch_preempt.py --target $BR --switch-file /www/wwwroot/bapatch/cn_preempt.txt --rollback
python3 $D/patch_simple.py  --bridge $BR --rollback
python3 $D/patch_8000.py    --target $BR --rollback
python3 $D/patch_1017.py    --target $BR --rollback
python3 $D/patch_24000_v3.py --target $BR --rollback
python3 $D/patch_90004.py   --src $BR --rollback
python3 $D/patch_requestid.py --target /www/wwwroot/bapatch/tools/cn_wire.py --rollback
```

每个都幂等：不在就跳过，不报错。

> 注意：`patch_24000_v3 --rollback` 只在**目标 sha 等于它的备份**时才放心还原；
> 如果中间又打了别的补丁，它可能要求 `--force`。所以**要么按逆序回滚，要么直接用 §5.2**。

### 5.2 一次性回滚全部

```bash
python3 /www/wwwroot/bapatch/deploy/deploy_all.py --rollback \
    --target /www/wwwroot/bapatch/tools/account_auth_probe.py \
    --cn-wire /www/wwwroot/bapatch/tools/cn_wire.py
```

它做两件事：

1. **逆序**调用每个补丁自己的 `--rollback`（preempt → simple → 8000 → 1017 → 24000 → 90004 → requestid）
2. 比 sha256：等于 manifest 里的 `sha256_original` 就收工；**不等就用 `.bapatch_orig.<ts>` 原件覆盖**再比一次

实测（沙箱）：`438ee1f0… → f94b4fa05d95d4c8719f5623322b75629b81eed59442370dd552db721437dbc9`
= **逐字节回到 54,026 B 基线**，`结果: PASS`。

### 5.3 不改源码的"软关"（最快，重启都不用）

| 想要 | 动作 | 生效方式 |
|---|---|---|
| 停止一切拦截（回到全代理） | `echo off > /www/wwwroot/bapatch/cn_preempt.txt` | 下一个请求立刻生效 |
| 只关掉某个协议 | `echo 24000,1017,8000 > .../cn_preempt.txt`（写你想要的那些） | 立刻 |
| 1017 回旧 492 B 实现 | `echo legacy > /www/wwwroot/bapatch/cn_1017_mode.txt` | 立刻 |
| 8000 关掉 | `patch_8000.py --target $BR --disable` 或把 `8000_switch.json` 的 `enabled` 改 false | 立刻 |
| 1005/4000/26000 关掉 | `echo 0 > <bridge目录>/cn_1005.txt`（依此类推） | 立刻 |
| inner RequestId 同步关掉 | `echo 0 > /www/wwwroot/bapatch/cn_inner_requestid.txt` | 立刻 |
| 24000 调参 | 改 `/www/wwwroot/bapatch/academy_24000_config.json`（按 mtime 缓存） | 立刻 |

> **24000 没有 `enabled` 开关**（v3 的配置只有 `locations/zone_scope/last_update/request_id_mode/default_account_id`）。
> 要关 24000 只能靠：① preempt 白名单里去掉它（**注意：这对 24000 没用**，因为它的 name 解析不到，
> 天然走 L1088，preempt 根本看不到它）；② `patch_24000_v3.py --rollback`。
> 这是本次整合里"最没有软开关"的一个协议，上机时优先盯它。

---

## 6. 全量验证（`--verify` 实际做什么 + 实测结果）

### 6.1 四项内容

| # | 检查 | 做法 |
|---|---|---|
| 1 | 所有补丁 marker 都在、不互相覆盖 | 每个补丁 2–3 个 marker，逐个数字符出现次数 |
| 2 | `py_compile` | **子进程**跑 `python -m py_compile`（和线上重启前同一条命令） |
| 3 | 逐协议渲染 | 把打补丁后的 bridge 源码 `exec` 进独立命名空间（stub 掉 `cn_cipher/cn_wire/cn_inner/cn_inner27/cn_nick`），用假 self 调 `_preempt_response` / `_generic_protocol_response`，截获真正传给 `cn_wire.wrap_response` 的 `(obj, requestid)`；再落成 JSON 交给 **`spec_check.py --protocol N --file`** 子进程判定 |
| 4 | 报告 | 每个协议的 inner 字节数、顶层键数、spec 结果、outer/inner rid、线上入口；写 `deploy/_report/deploy_verify.json` |

关键点：`_cn_send_envelope` 用的是**真方法**（不是我在测试里重写一遍），
所以 `patch_90004` 改的 outer rid 是**真跑出来**的。

cn_wire 侧：
* 有真 `cn_wire.py`（线上）→ 用它 + 跑 `patch_requestid --verify`；
* 没有（本地）→ 用一个只复刻 `patch_requestid` 依赖形状的最小替身（1,005 B），
  在它上面**真打一次** patch_requestid，然后功能性验证
  `build_plaintext()` 出来的 inner packet 的 `RequestId` == 传进去的 `requestid`
  （覆盖"插入 / 覆盖旧值 / 缺省"三种情况）。这叫 `cn_wire 替身`，报告里会标 `mode`。

### 6.2 实测结果（115,740 B / `438ee1f0…`）

```
proto   name                                 via           innerB  keys    spec      rid      线上入口
24000   Academy_GetInfo                      preempt(hit)  1040    7       PASS      OK       L1088直通
1017    Account_LoginSync                    preempt(hit)  83804   35      PASS      OK       L1088直通
1005    Account_GetTutorial                  preempt(hit)  267     6       PASS      OK       path-A拦截
4000    Item_List                            preempt(hit)  361     7       PASS      OK       L1088直通
26000   ContentSave_Get                      preempt(hit)  321     8       PASS      OK       L1088直通
8000    Mission_List                         preempt(hit)  3933    10      PASS      OK       path-A拦截
90004   Management_Data                      preempt(hit)  420     6       PASS      OK       L1088直通
8006    Mission_GuideMissionSeasonList       ——            ——     ——      GEN:PASS  ——       no-branch
3       NetworkTime_Sync                     ——            ——     ——      GEN:PASS  ——       no-branch
36001   Notification_EventContentReddotCheck ——            ——     ——      GEN:PASS  ——       no-branch
```

对应的 `gen_kind`（证明走的是哪个实现，不是兜底）：

| 协议 | gen_kind |
|---|---|
| 24000 | `academy-24000-v3` |
| 1017 | `loginsync-1017-dynamic` |
| 1005 / 4000 / 26000 | `simple-1005` / `simple-4000` / `simple-26000` |
| 8000 | `official-8000` |
| 90004 | `management-90004-official` |

对照组：8006 / 3 / 36001 的 `gen_kind = min+base`（7 个假键），
`inner_bytes` 193–197 —— 正是"bridge 里没有分支、会被 path A 代理"的样子。

### 6.3 8006 / 3 / 36001 的诚实结论

这三个**只有生成器**（`deploy/gen8006.py`、`gen3.py`、`gen36001.py`），
**bridge 里没有对应分支**，`_generic_protocol_response()` 里也没有它们。
所以：

* 现在它们会被 path A 代理给 Shittim（和今天一样）。
* `--verify` 会明确报 `no-branch（已知：只有生成器）` + `GEN:PASS`，
  意思是"**载荷本身**结构合规（生成器 spec_check PASS），但**还没有接线路由**"。
* 要把它们真的接上，需要：① 新写 `patch_8006.py` / `patch_3.py` / `patch_36001.py`
  在 `_generic_protocol_response` 里加分支（或像 `patch_simple` 那样挂 HOOK-G）；
  ② 把对应号码加进 `patch_preempt.py` 的 `PREEMPT_IMPLEMENTED`。
  **这两件事本次没有做**（任务边界外），所以 `PREEMPT_IMPLEMENTED` 里也没有它们。

`--verify` 不会因为它们"没接"而报 FAIL（那是已知状态），但如果某个**本应有分支**的协议
渲染不出来（补丁没生效），就一定会 FAIL —— 这个区分在代码里是显式的
（`expected_branch = (p['via'] != 'none')`）。

---

## 7. 上机验证清单（重启后看什么）

### 7.1 重启前

```bash
# 1) 打完之后 sha 应该是 438ee1f0…（如果你用的是 v3，且基线是 f94b4fa0…）
sha256sum /www/wwwroot/bapatch/tools/account_auth_probe.py

# 2) 语法
python3 -m py_compile /www/wwwroot/bapatch/tools/account_auth_probe.py && echo COMPILE-OK

# 3) 全量验证（不联网、不影响线上）
python3 deploy/deploy_all.py --target ... --cn-wire ... --verify
#    期望：结果: PASS，7 个协议 spec=PASS / rid=OK

# 4) 确认开关是 off（重要！先不要开）
cat /www/wwwroot/bapatch/cn_preempt.txt   # 期望 off 或文件不存在
```

### 7.2 重启后（`exp` 仍是 decrypt+plain+http200，先不开拦截）

期望看到 **行为零变化**（这是第一步的判据）：所有协议照旧被代理，`rec['preempt']` 应该是 `'off'`。

```bash
tail -f /www/wwwroot/bapatch/logs/api_all_requests.log | grep -E '"preempt"|"gen_kind"'
```

| 检查 | 判据 |
|---|---|
| bridge 起来了吗 | `bridge v6 listening on 127.0.0.1:9097` |
| 登录链没断 | 客户端能过 CheckNexon → Auth → Nickname/CallName |
| 24000 变了（v3 生效） | `gen_kind = academy-24000-v3`（旧的是 `academy-24000` / `academy-24000-e2`） |
| 90004 变了 | `gen_kind = management-90004-official`，且 `gen_90004_data_keys = 9` |
| 1017 走动态 | `gen_kind = loginsync-1017-dynamic`（`gen1017_inner_len` 有值） |
| preempt 没乱动 | 每条记录里 `preempt = off` |
| outer==inner | `enc_requestid` 与 `last_direct_envelope_plain.txt` 里 packet 的 `RequestId` 相同 |

### 7.3 打开拦截后（`--switch 8000` 起，逐个开）

先只开一个号，最小化爆炸半径：

```bash
echo 8000 > /www/wwwroot/bapatch/cn_preempt.txt     # 立刻生效，不用重启
```

| 检查 | 判据 |
|---|---|
| 8000 真的被我们自己接管了 | 日志里 `preempt = hit`、`preempt_hit = 8000`、`gen_kind = official-8000` |
| 8000 载荷对不对 | `enc_inner_keys = 10`、`enc_inner_bytes` ≈ 3.9 KB、`enc_requestid == inner RequestId` |
| 客户端任务列表出来了 | 游戏里 Mission 页面有内容（不是空白/不是卡 loading） |
| 其它协议没被误伤 | 其它号码的记录里必须是 `preempt = skip`，**不能**出现 `hit` |
| 出问题怎么退 | `echo off > /www/wwwroot/bapatch/cn_preempt.txt` —— 一条命令，立刻回代理 |

再逐步加：`echo 8000,1005 > ...` → `echo 8000,1005,4000,26000 > ...` → `echo all > ...`。

| 现象 | 含义 | 处理 |
|---|---|---|
| `preempt = hit` 但客户端报错 | 分支载荷有问题 | 立刻 `echo off`；看 `gen_kind`，单协议回滚 |
| `preempt = fallthrough` | 该协议没有真分支（落到 min+base） | 正常降级，已自动回代理；检查对应补丁是否真打上 |
| `preempt = error` + `preempt_err` | 分支抛异常 | 看 `preempt_err`；该协议回滚 |
| `preempt = skip` 且是**想开**的协议 | 号码不在 `PREEMPT_IMPLEMENTED` 里 | 加补丁 + 改常量，不是改开关 |
| `preempt_num = None` | 既不在名字表、也解不出 Hash | 该协议本来就走 L1088，不用管 |

---

## 8. 风险点（按"最可能失败"排序）

### R1（最可能）`patch_24000_v3` 的基线守卫 —— exit 2，目录根本没动

* **症状**：`ERROR: 目标 sha256 不是已知基线，拒绝改动`，`got <x> expect f94b4fa0…`，exit **2**。
* **为什么**：v3 只允许打"原始 54,026 B 基线"。只要在它之前有任何一个补丁改了 bridge，它就罢工。
* **怎么判断**：`--dry-run` / `--apply` 会停在第 2 步，`exit : 2   +0 bytes`
  （**+0 是关键信号**：一个都没写进去，文件是干净的，不需要回滚）。
* **怎么处理**：
  * 正常流程里它本来就在第 2 步（前面只有改 cn_wire 的 requestid），不会有这个错。
  * 如果是在"别人已经改过的半成品"上续跑：`deploy_all.py` 会自动补
    `--allow-other-baseline` 并打印 `!! 基线守卫: ...`。
    实测：先把 90004 打上去（sha `d5552ef0…`），再整轮跑 —— 第 2 步自动放行，
    最终产物 **115,740 B**，与干净跑**同尺寸**；sha 不同只是因为两次跑在不同目录，
    8000 托管块里内嵌的绝对路径长度不一样（`_scratch/…` vs `_sandbox/…`）。
    **同一目录下比 sha 才有意义。**
  * **不要**手工 `--allow-other-baseline` 去糊一个已经变形（比如 `if num == 24000:` 不唯一）的文件。

### R2 `patch_requestid.py` 静默 SKIP（exit 0，看起来成功）

* **症状**：`[1/7] requestid SKIP  cn_wire.py 不存在：...`，exit 0，整体 `--apply` 仍然是 PASS。
* **为什么**：本地/换机时 `--cn-wire` 指错，或者 `cn_wire.py` 不在那个目录。
* **危险点**：**这一步跳过不会让任何东西报错**，但 `outer.requestid == inner RequestId` 就只剩
  bridge 侧的那一半了 —— bridge 侧四个 `*_send` 都自己把 rid 传进去了，所以**看着还是对的**，
  但走 `_cn_send_envelope` 的路径（90004 以及任何 name-None 的协议）就不再保证 inner 有 RequestId。
* **怎么判断**：`--verify` 的第 3 段会打印
  `线上 cn_wire.py 不可用（missing）-> 在替身上验证`；`--status` 里 requestid 那行是 `SKIP`。
* **怎么处理**：确认 `--cn-wire` 指的是**线上真的在跑的那个** cn_wire.py；打完后
  单独跑 `python3 deploy/patch_requestid.py --target <cn_wire.py> --verify`，必须 exit 0。

### R3 `patch_preempt` 打开后，8000 的 catalog 不在/是空的

* **症状**：`preempt = hit`、`gen_kind = official-8000`，但 `enc_inner_bytes` 明显偏小、
  客户端任务页空白。
* **为什么**：`patch_8000 --apply` 会把 `8000_catalog.json`（143,976 B / 7,153 条）部署到
  **bridge 同目录**，并把绝对路径写死进托管块。如果那次 `--apply` 用的 `--target` 目录跟
  实际运行目录不同，或者 catalog 被删了，块里就指向一个空文件。
* **怎么判断**：`patch_8000.py --target <BR> --status` 看 `catalog : ... (N 条)`；
  日志里 `enc_inner_keys` 必须是 **10**、`enc_inner_bytes` 应在 **3.9 KB** 量级
  （实测 3933）。**spec_check 对空数组是 PASS 的**，所以光看 PASS 发现不了 —— 必须看字节数。
* **怎么处理**：`patch_8000.py --target <BR> --apply` 重跑一次（幂等，会重新部署数据文件）；
  或 `--disable` 先关掉 8000，让它退回代理。

### R4 只开一半开关，产生"半新半旧"的错觉

* **症状**：日志里有的协议 `hit`、有的 `skip`，客户端表现为"某些页面正常、某些页面卡"。
* **为什么**：`cn_preempt.txt` 是**每协议**粒度；`cn_1005.txt`/`cn_4000.txt`/`cn_26000.txt`
  是又一层**per-protocol** 开关（缺省=关）。preempt 放行了 1005、但 `cn_1005.txt` 不存在时，
  HOOK-G 返回 None → 落到 `min+base` → preempt 判 fallthrough → **回 path A 代理**
  （安全，但看起来像"开了又没开"）。
* **怎么判断**：看同一条日志里 `preempt` 与 `simple_off` 两个字段：
  `preempt=hit` 但 `gen_kind` 不是 `simple-*` 就不是 simple 在应答。
* **怎么处理**：`patch_simple.py --bridge <BR> --apply --switches 1`（或手工
  `echo 1 > <bridge目录>/cn_1005.txt`）。

### R5 `patch_1017` 的 legacy fallback 被误当成"补丁没生效"

* **症状**：日志 `gen_kind = loginsync-1017`（注意没有 `-dynamic`），载荷 492 B 那套。
* **为什么**：`cn_1017_mode.txt = legacy`，或环境变量 `CN_1017_MODE=legacy`，或
  `import gen1017` 失败（`gen_kind` 会是 `loginsync-1017` + `gen1017_err`）。
* **怎么判断**：`cat /www/wwwroot/bapatch/cn_1017_mode.txt`；日志里有没有 `gen1017_err`。
* **怎么处理**：`echo dynamic > .../cn_1017_mode.txt`；`gen1017_err` 则是部署缺文件
  —— `gen1017.py` 必须和 `account_auth_probe.py` **同目录**（或设 `BA_GEN1017_DIR`）。

### R6 改了文件但没重启

* **症状**：`--verify` 全绿，但线上行为一点没变。
* **怎么判断**：进程启动时间 vs 文件 mtime；`gen_kind` 还是旧值（`academy-24000-e2` 之类）。
* **怎么处理**：重启（见 §4）。托管块是**模块级**的，进程不重启就不会重新执行。

### R7 `_cn_send_envelope` 的 rid 改动是**全局**的

* **症状**：所有走 `_cn_send_envelope` 的协议，outer rid 都改从 `obj['RequestId']` 取。
* **为什么**：`patch_90004` 改的是这个公共方法，不是只给 90004 用。
* **影响面**：`obj` 里没有 `RequestId` 的协议会退回 `uuid4`（与旧行为一致），所以是安全的
  向后兼容；但**如果某个分支的 `obj['RequestId']` 是脏值**，它会被原样当 outer rid 发出去。
* **怎么判断**：`--verify` 的 `rid` 列（7/7 OK）+ 线上 `enc_requestid` 的形态（必须是 UUIDv4 字符串）。
* **怎么处理**：不改这个方法，去修那个分支的 `obj['RequestId']`。

---

## 9. 本次产出的三个新文件

| 文件 | 作用 |
|---|---|
| `deploy/patch_preempt.py` | 协议白名单拦截（B1/B2/B3 三块 + 开关 + 36 项自检）；`--apply/--verify/--rollback/--dry-run/--status/--switch`，幂等 |
| `deploy/deploy_all.py` | 七步统一部署器；`--apply/--verify/--rollback/--status/--dry-run`；逐步 marker+编译自检、manifest、一次性回滚、逐协议渲染验证 |
| `deploy/DEPLOY_PLAN.md` | 本文 |

运行期产物（可随时删，不影响源码）：`deploy/_sandbox/`（演练副本）、`deploy/_scratch/`（dry-run 副本）、
`deploy/_verify_rig/`（渲染台）、`deploy/_report/deploy_verify.json`（最近一次验证报告）。
