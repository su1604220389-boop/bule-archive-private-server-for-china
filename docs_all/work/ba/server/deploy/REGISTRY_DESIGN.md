# generator_registry 设计文档

> 目标：给 `work\ba\server\deploy\` 下**已经逐字节验证过**的响应生成器做一个统一注册表 / 分发入口，
> 为将来接 bridge 的 `_generic_protocol_response` 分发点做准备。
>
> **本次只新增三个文件**（`generator_registry.py` / `registry_selftest.py` / 本文件），
> 没有 import 也没有改动 `account_auth_probe.py`（bridge 本体），没有改任何 `gen*.py`，
> 没有碰 `official_spec.json` / `dto_schema_full_v2.json` / 任何 schema，没有连服务器。
>
> 环境：`C:\Users\su\Desktop\大肥鱼项目\BAServer`，Windows / Python 3.12。

---

## 0. 结论先行

**这条路走得通，而且比预期干净。** 逐条回答"哪些能直接注册、哪些要额外工作"：

| 结论 | 内容 |
|---|---|
| 能直接注册 | **8 个协议**：`3 / 1005 / 4000 / 8006 / 24000 / 26000 / 36001 / 90004` —— 用官方抓包当输入回灌，产出与官方 **inner 逐字节相同**，外层明文也与官方 `plain` 逐字节相同 |
| 注册成功、只能到"结构级" | **6 个协议**：`1017 / 5000 / 6000 / 8000 / 29002 / 30041` —— record 结构、键序、类型与官方完全一致，但**值不同**：官方样本是"玩过的号"（角色/编队/任务进度），而 `1017/5000/6000/29002/30041` 的状态槽 `account_state` 我们只能传 `None`（手上没有那个号的完整状态），`8000` 则**根本没有状态槽** |
| 本次一共登记 | **14 / 38** 个协议（`official_spec.json` 里 38 个） |
| 额外工作才能逐字节 | `1017`（要账号状态注入 + 两处序列化口径）、`8000`（要 ProgressDBs 注入口）、`5000/6000/29002/30041`（要 account_state） |
| 完全没生成器 | **24 个协议**（见 §6），其中 `25003`(21 条抓包) / `7001`(9) / `28019`(8) / `43010`(8) 是最划算的下一批 |
| 自测结果 | `registry_selftest.py`：**逐字节 8 / 结构一致 6 / 结构不一致 0 / 新号构建合法 14/14**，退出码 0 |
| 阻断问题 | **没有**。唯一需要 bridge 侧配合的是"外层 `requestid` 与 inner `RequestId` 必须是同一个值"（见 §4 步骤 2），这是既有的官方不变量，不是新问题 |

一句话：**生成器不用改一行就能统一注册**；接口不一致全部在适配层吸收掉了。
真正缺的不是"注册机制"，而是**状态注入口**（§5.2）—— 那是 1017/8000 这类"状态型协议"逐字节复现的唯一缺口。

---

## 1. 现有生成器清单

扫描 `work\ba\server\deploy\gen*.py`（8 个文件）+ 两个被它们复用的辅助模块
（`gen_common.py` / `simple_payload.py` / `dto90004.py`）。**文件名与任务描述一致，无出入。**

### 1.1 主表

| 协议 | 文件 | 真入口函数 | 签名 | 返回 | 运行时依赖 | 自检入口 |
|---|---|---|---|---|---|---|
| 3 `NetworkTime_Sync` | `gen3.py` | `build_3` | `(account, recv_tick=None, echo_tick=None, recv_offset_us=0)` | `dict` | `gen_common` → `official_spec.json`（`order_like_spec`）；`dto_extra/proto3_networktime.json` 仅 CLI 交叉校验用 | `--verify-official`（官方回灌逐字节） |
| 1005 `Account_GetTutorial` | `gen_simple.py` + `simple_payload.py` | `simple_payload.simple_build(1005, …)` → `specgen.Spec().build` | `(num, account_id=None, mxtoken=None, rid=None, ticks=None, tutorial_ids=None)` | `dict` | `official_spec.json`（conform）+ `specgen` | `--replay-official`（三条样本逐字节） |
| 1017 `Account_LoginSync` | `gen1017.py` | `build` | `(account_state=None, session=None, request_id=None, now=None, spec=None, rules=None, master=None, issues=None)` | `dict` | `specgen` + `official_spec.json` + `initial_state_rules.json` + `ExcelDB.db` | `selfcheck(resp, session)`；main 默认跑 `spec_check`；`--standalones` |
| 4000 `Item_List` | `gen_simple.py` + `simple_payload.py` | 同上 | 同上 | `dict` | 同 1005 | 同 1005 |
| 5000 `Echelon_List` | `gen1017.py` | `build_standalone` | `(proto, account_state=None, session=None, request_id=None, now=None, spec=None, rules=None, master=None, issues=None)` | `dict` | 同 1017 | 同 1017 |
| 6000 `Campaign_List` | `gen1017.py` | `build_standalone` | 同上 | `dict` | 同 1017 | 同上 |
| 8000 `Mission_List` | `gen8000.py` | `build_response` | `(account_id, profile="seed", event_content_id=None, now=None, request_id=None, mxtoken=None, reset_hour=4, daily_sudden_id=1606, catalog=None)` | **`(inner, issues, meta)` 三元组** | `specgen`（按路径载入）+ `official_spec.json` + `ExcelDB.db` | `--selfcheck` / `--explain-variants` / `--emit-catalog` |
| 8006 `Mission_GuideMissionSeasonList` | `gen8006.py` | `build_8006` | `(account, mission_rows, season_rows, with_complete_false=False)` | `dict` | `gen_common` → `official_spec.json` + `ExcelDB.db`（默认路径推 733/17）；`dto_extra/proto8006_guidemission.json` 仅 CLI 用 | `--verify-official` |
| 24000 `Academy_GetInfo` | `gen24000.py` | `b24000_build` | `(account_id, mxtoken, request_id, ticks, locations=None, last_update=None, zone_scope="service", zone_visit=None)` | `dict` | **无**（71 zone / 9 location 全部内嵌常量；`ExcelDB` 只给 `--verify-db` 用） | `--selfcheck` / `--fidelity` / `--verify-db` / `--compare` |
| 26000 `ContentSave_Get` | `gen_simple.py` + `simple_payload.py` | 同 1005 | 同 1005 | `dict` | 同 1005 | 同 1005 |
| 29002 `Billing_PurchaseListByYostar` | `gen1017.py` | `build_standalone` | 同 5000 | `dict` | 同 1017 | 同上 |
| 30041 `EventContent_PermanentList` | `gen1017.py` | `build_standalone` | 同 5000 | `dict` | 同 1017 | 同上 |
| 36001 `Notification_EventContentReddotCheck` | `gen36001.py` | `build_36001` | `(account, reddots=None, cg_keys=None)` | `dict` | `gen_common` → `official_spec.json` + `dto_extra/proto36001_reddot.json` | `--verify-official`（另断言 10 条样本键集合稳定） |
| 90004 `Management_Data` | `gen90004.py` + `dto90004.py` | `dto90004.build_90004_management_data` | `(session_key, ticks, request_id, ops=None)` | `dict` | `json`/`os` 零依赖；`gen_common.order_like_spec` 需要 `official_spec.json` | `--verify-official` |

> 注意：`gen3.py` / `gen90004.py` / `gen8006.py` / `gen36001.py` 的模块级 `build(args)`
> **吃的是 argparse.Namespace**，不是值 —— 它们不是可复用入口。真入口是表里那 4 个函数。

### 1.2 辅助模块（不是生成器，但注册表要用）

| 文件 | 角色 | 依赖 |
|---|---|---|
| `gen_common.py` | 4 个生成器的地基：`Spec` / `Account` / `order_like_spec` / `official_inner` / `verify_official_bytes` / `ExcelDB` / `fb_slot_int` | `official_spec.json`、`spec_check.py`、`dto_extra/`、`ExcelDB.db`、`report/_tmp/official_decoded_201/` |
| `simple_payload.py` | 1005/4000/26000 的**唯一载荷真源**（同一份源码被 `patch_simple.py` 内联进 bridge） | 纯标准库（`base64/hashlib/json/os/re/uuid`） |
| `dto90004.py` | 90004 的**唯一构造器**（同一份源码被 `patch_90004.py` 内联进 bridge） | 纯标准库（`json/os`） |

### 1.3 返回值类型：**没有一个是 `bytes`**

这是本次调研最重要的一个事实修正：8 个生成器**全部返回 `dict`**（inner packet 明文树），
唯一接近字节的是 `gen8000.b64_bytes()`（调试用）和 `gen_simple` 里那三个字节数口径函数（`wire_len_for_plain` 等）。

真实的字节化链条是：

```
inner dict ──紧凑 JSON──▶ packet 字符串
           ──外层信封──▶ plaintext = {"protocol":<name>,"packet":<packet>,"requestid":<uuid>}
           ──cn_wire──▶ wire body = base64( AES-256-CBC(plaintext, key=随机32B, IV 固定) + key )
```

所以注册表把 **"结构化" 与 "字节化" 拆成两层**（`build_inner()` / `build()`），详见 §3.2。

---

## 2. 接口差异分析

把 8 个生成器的入口摆在一起，暴露了 **11 处**不一致。这些是"硬编码 JSON 补丁"模式的真正根因：

| # | 不一致 | 具体表现 | 适配方案（在哪吸收） |
|---|---|---|---|
| 1 | **返回类型** | 13 个协议返回 `dict`；`gen8000.build_response` 返回 `(inner, issues, meta)` | 适配层取 `[0]`；`Registration.returns="dict(tuple→[0])"` 显式记账 |
| 2 | **时间入口** | `3/24000/8006/36001/90004/1005/4000/26000` 收 `ticks`；`1017/8000/5000/6000/29002/30041` **只收 `now`**（内部推 ticks） | 统一以 `server_time_ticks` 为必填；适配层 `_as_now(ctx)` 由 ticks 反推 `now`（差 ≤ 0.9 µs，见 §5.3） |
| 3 | **协议名字不可得** | 生成器只产出 inner，**不产出外层 `protocol` 字符串**（`"Account_Auth"` 这种），而 `cn_wire.wrap_response` 必须要它 | 注册表登记 `name`，并与 `official_spec.json` 交叉对账（自测 §③ 全一致） |
| 4 | **入口形态** | 4 个生成器的模块级 `build(args)` 吃 `argparse.Namespace` | 适配层直接调下一层真入口（`build_3` / `build_36001` / `build_8006` / `dto90004.build_90004_management_data`） |
| 5 | **一个文件多个协议** | `gen_simple.py` 是 3 协议共用 + argparse 驱动，**没有 per-proto builder** | 适配层调 `simple_payload.simple_build(num, …)` + `specgen.Spec().build()`（与 `gen_simple.render()` 同一段 conform） |
| 6 | **一个协议多文件** | `5000/6000/29002/30041` 没有独立 `gen` 文件，body 构造器长在 `gen1017.py` 里 | 适配层调 `gen1017.build_standalone(proto, …)` |
| 7 | **对象 vs 散参数** | `gen3/36001/8006` 要 `gen_common.Account` 对象；`gen24000/dto90004` 要散标量；`gen1017` 要 `(account_state, session)` 两个大字典 | 适配层 `_account(ctx)` / `_session_key(ctx)` 统一构造 |
| 8 | **状态注入口不存在** | `1017` 收 `account_state`（大字典，白名单 40+ 键）；`8000/5000/6000/29002/30041` **完全不收状态**；`4000` 的 `ItemDBs` 硬编码在 `simple_payload` 里 | `1017` 已可用（`account_state`）；`4000` 适配层加 `item_rows` 注入槽；其余记为"额外工作"（§5.2） |
| 9 | **`requestid` 双份** | 官方 109/109：外层 `requestid` **等于** inner `RequestId`。生成器却都能自己 `uuid4`（不给就各生成一个） | `request_id` 设为 `requires`，强制调用方给同一个值；自测契约面「外层信封自洽 14/14」把它钉住 |
| 10 | **配置依赖不一致** | `gen24000` / `dto90004` **零文件依赖**（deploy 机安全）；`1017/8000/8006` 要 `specgen + spec + rules + ExcelDB.db`；`3/36001/90004` 只要 `official_spec.json`（+`dto_extra`） | 登记表 `ADAPTER_MODULES` 声明依赖，`autodiscover()` 先 import 再登记：缺依赖**不登记**而不是运行时炸 |
| 11 | **请求体没人吃** | 没有生成器读请求 packet；`req` 只在 `simple_payload.simple_*` / bridge 的 `rec` 里 | `ctx['request_body']` 预留（自测已验证陌生键不炸） |

### 2.1 适配层的位置与"不改原生成器"的边界

适配层 = `generator_registry.py` 里的 `_adapt_*` 函数 + `adapter_table()`。原则：

1. 适配层只做 **`ctx` → 原签名** 的搬运、以及 **返回值归一化**（tuple → dict）。
2. 任何数据加工都留在原生成器里，保证"本地验收过的代码 = bridge 跑的代码"。
3. **唯一的例外**：`4000` 的 `item_rows` / `expiry_item_rows` 注入槽。
   `simple_payload.simple_build()` 把 `ItemDBs` 写死成"新号 1 条"，没有行注入参数，
   而道具状态将来必须从账号库来。适配层在 conform 之前替换 `obj["ItemDBs"]`，
   **不改 `simple_payload.py` 一个字符**。这条要在评审时明确认可（属于"适配层扩权"）。

---

## 3. registry 接口定义

### 3.1 三个文件的分工

| 文件 | 职责 | 依赖 |
|---|---|---|
| `work\ba\server\deploy\generator_registry.py` | 注册表本体 + 14 段适配层 + 打包器 | **纯标准库**（`datetime/importlib/json/os/sys/uuid`）；**不 import bridge**；生成器全部延迟 import |
| `work\ba\server\deploy\registry_selftest.py` | 自测（登记面 / 契约面 / 回放面 / 新号面） | 注册表 + `gen_common` + `spec_check`（只读官方抓包） |
| `work\ba\server\deploy\REGISTRY_DESIGN.md` | 本文件 | — |

### 3.2 接口（与任务给的形状一致，外加两个必要扩展）

```python
import generator_registry as R

R.register(protocol:int, name:str, builder:callable, requires:list[str], optional=(), …)
R.build(protocol:int, ctx:dict) -> bytes          # ← 任务要求的形状（字节）
R.build_inner(protocol:int, ctx:dict) -> dict     # ← 新增：字节层的下一层，做结构比对用
R.list_protocols() -> list[int]
R.describe() -> list[dict]                        # 表格数据
R.get(protocol) -> Registration                   # .name / .requires / .optional / .source
R.set_packer(fn)                                  # 注入真实加密打包器（bridge 用，见 §4）
R.autodiscover() -> (registered, failed)          # 把 14 条适配全部登记上（幂等）
R.errors()                                        # 登记失败的 (协议, 模块, 异常)
R.UNCOVERED                                       # 24 个没有生成器的协议号（文档/自测用）
```

错误语义（都不静默）：

| 情况 | 异常 | 例子 |
|---|---|---|
| 协议没登记 | `RegistryError` | `协议 4001 没有注册任何生成器。已注册: [...]` |
| 重复注册 | `RegistryError` | `协议 3 已注册（NetworkTime_Sync，来自 gen3.build_3）；拒绝静默覆盖` |
| 缺 `requires` 键 | `MissingContext` | `协议 24000 (Academy_GetInfo) 缺少 ctx 键 ['server_time_ticks']。…可选键: [...]` |
| 适配层返回非 dict / `Protocol` 自相矛盾 | `RegistryError` | — |

**`build()` 的字节口径（必须说清楚）**：默认打包器 `pack_plaintext()` 产出的是
**加密前的外层明文**，与 `cn_wire.build_plaintext()` / `gen_simple.outer_plain()` **逐字节同口径**，
也就是官方抓包里的 `plain` 字段；它**不是**最终 wire body（`base64(AES-CBC(plain)+key)`）。
这是刻意的分层：注册表按约定不 import bridge、也不引入 `cryptography`；
真 wire body 只需一行 `R.set_packer(...)`（§4 步骤 3），注册表零改动。

### 3.3 ctx 契约

```python
CTX_KEYS = {
  "account_id":        int    # AccountServerId
  "mx_token":          str    # 64 字符 base64；**别名 mxtoken**（兼容既有生成器叫法）
  "request_id":        str    # 外层 requestid，必须 == inner RequestId（官方 109/109）
  "server_time_ticks": int    # .NET 100ns ticks —— 统一时钟入口
  "now":              可选    # datetime / 'YYYY-MM-DDTHH:MM:SS[.ffffff]'；给了就压过 ticks 反推
  "session_key":      可选 dict
  "request_body":     可选 dict   # 已解密请求 packet（预留）
  "protocol":         build_inner 自动注入
}
```

每协议私有键由 `Registration.requires / optional` 声明（`R.describe()` 可直接打表）：

| 协议 | requires | optional |
|---|---|---|
| 3 | account_id, mx_token, request_id, server_time_ticks | recv_tick, echo_tick, recv_offset_us |
| 1005 | 同上 4 个 | tutorial_ids |
| 1017 / 5000 / 6000 / 29002 / 30041 | 同上 4 个 | now, account_state, session_key |
| 4000 | 同上 4 个 | item_rows, expiry_item_rows |
| 8000 | 同上 4 个 | now, profile, event_content_id, reset_hour, daily_sudden_id, catalog |
| 8006 | 同上 4 个 | mission_rows, season_rows, with_complete_false, mission_scope, exceldb |
| 24000 | 同上 4 个 | locations, last_update, zone_scope, zone_visit |
| 26000 | 同上 4 个 | — |
| 36001 | 同上 4 个 | reddots, cg_keys |
| 90004 | 同上 4 个 | ops, session_key |

> **"14 个协议的最小 ctx 是同一组 4 个键"** 是本次适配的成果：
> 不管原生成器收 ticks 还是收 now，调用方只认 `server_time_ticks`。

### 3.4 用法示例

```python
import generator_registry as R
R.autodiscover()                     # 14/14 登记（缺依赖的会进 R.errors()，不会炸）

ctx = {
    "account_id":        10015354380,
    "mx_token":          "<64 字符 base64>",
    "request_id":        "11111111-2222-3333-4444-555555555555",
    "server_time_ticks": 639304002548158993,
}

inner = R.build_inner(24000, ctx)            # dict：可跑 spec_check / 逐字段比对
body  = R.build(24000, ctx)                  # bytes：默认 = 外层明文（可对官方 plain 逐字节比）
plain, rid, inner = R.build_plain(24000, ctx)

# 状态型协议：把账号状态塞进来（1017）
R.build_inner(1017, dict(ctx, account_state={"characters": [...], "currency": {...}}))

# 事件变体（8000）
R.build_inner(8000, dict(ctx, event_content_id=849))

# 官方抓包回灌（自测就是这么跑的）
R.build_inner(90004, dict(ctx, ops=official_inner["Data"]))
```

批量 & 容错：

```python
res = R.REGISTRY.build_all([3, 24000, 90004], ctx)   # {proto: inner 或 异常对象}，不中断
```

CLI（人工核对用，只读）：

```bash
python work\ba\server\deploy\generator_registry.py list
python work\ba\server\deploy\generator_registry.py build 24000 --plain
```

### 3.5 一个适配层的完整示例（24000：零成本）

```python
def _adapt_gen24000(ctx):
    g24 = _mod("gen24000")            # 延迟 import，注册表本身可 import
    return g24.b24000_build(
        int(_need(ctx, "account_id")),
        str(_ctx_get(ctx, "mx_token") or ""),
        str(_ctx_get(ctx, "request_id") or ""),
        _ticks(ctx),                  # ← ticks 缺省时由 now 反推
        locations=_ctx_get(ctx, "locations"),
        last_update=_ctx_get(ctx, "last_update"),
        zone_scope=str(_ctx_get(ctx, "zone_scope", "service") or "service"),
        zone_visit=_ctx_get(ctx, "zone_visit"))
```

登记项（`adapter_table()` 里的一行）：

```python
(24000, "Academy_GetInfo", _adapt_gen24000,
 ["account_id", "mx_token", "request_id", "server_time_ticks"],
 ["locations", "last_update", "zone_scope", "zone_visit"],
 "gen24000.b24000_build", "dict", "全标量签名，零适配成本；官方 2/2 逐字节可复现"),
```

---

## 4. 未来接 bridge 的 3 步方案（本次**不**执行）

bridge 的分发点已经找好了：`work\ba\server\_bridge_ref\account_auth_probe.py`
（部署机上的那份由 `patch_*.py` 把生成器整段内联进去，函数结构同源）。

关键锚点：

| 位置 | 内容 |
|---|---|
| `L643` | `def _generic_protocol_response(self, proto_str, packet_b64, rec, name=None)` —— **分发点** |
| `L645-659` | 解密请求片段 → `Hash >> 32` → `rec['gen_protocol'] = num`（协议号在这里定下来） |
| `L660-661` | `if num is None: return None` |
| `L662-716` | **就是那三段手写硬编码**：`num == 90004` / `num == 24000` / `num in (1019,1017)`，其余落到 `min+base` 兜底信封 |
| `L718-733` | `def _cn_send_envelope(self, proto_name, obj, rec)` → `L722 cn_wire.wrap_response(proto_name, obj, rid)` |
| `L398-406` | `class Session` / `SESSION` —— `account_id`、`session_key` 的权威来源 |

### 步骤 1：在分发点插入"注册表优先"（约 12 行，插在 L661 与 L662 之间）

```python
        # ---- registry 优先：先查注册表，命中就走统一构造 ----
        try:
            import generator_registry as _GR
            _GR.autodiscover()
            if _GR.REGISTRY.is_registered(num):
                _ctx = self._registry_ctx(num, rec, frag)          # 步骤 2 的函数
                _inner = _GR.build_inner(num, _ctx)
                rec['gen_kind'] = 'registry-%d' % num
                rec['fallback'] = 'registry'
                return self._cn_send_envelope(
                    name or _GR.REGISTRY.name_of(num), _inner, rec,
                    rid=_ctx['request_id'])                        # 步骤 2 的同一个 rid
        except Exception as _e:
            rec['registry_err'] = repr(_e)          # 不回退静默：老分支仍在下面兜底
```

要点：**插在 `if num == 90004:` 之前**，老分支一行都不删 —— 这样是"灰度"：
注册表跑挂了自动落到原来的硬编码信封，行为不劣化。`L718` 的 `_cn_send_envelope`
是**直接信封**路径（不经 `L577 _cn_envelope` 的 `apply_field_patch` / `apply_flatten` A/B 开关），
灰度期正合适。

### 步骤 2：加一个 `_registry_ctx(self, num, rec, frag)`（约 20 行）

```python
    def _registry_ctx(self, num, rec, frag):
        import uuid as _u
        from datetime import datetime as _d
        rid = pick_requestid(rec) or str(_u.uuid4())     # 复用 L223 既有开关 → 外层/内层同值
        sess = SESSION.session_key or {}
        now = _d.now()
        ticks = int((now - _d(1, 1, 1)).total_seconds()) * 10_000_000 + now.microsecond * 10
        return {
            'account_id':        SESSION.account_id or sess.get('AccountServerId') or 0,
            'mx_token':          sess.get('MxToken', ''),
            'request_id':        rid,
            'server_time_ticks': ticks,
            'session_key':       sess,
            'request_body':      _try_json(frag),        # 预留；现在没生成器读它
        }
```

**这一步有一个必须同时做的改动**：`L718` 的 `_cn_send_envelope` 现在自己造 rid
（`L721 rid = str(_u4.uuid4())`），要让**外层 requestid == inner RequestId**（官方 109/109），
就必须把它改成 `def _cn_send_envelope(self, proto_name, obj, rec, rid=None)` 并优先用传入的 rid。
这不是 registry 引入的新约束 —— 官方响应本来就这样，只是老的硬编码分支里 inner 根本没有 `RequestId` 字段，
所以这个漏洞一直没暴露出来。

### 步骤 3：删掉硬编码分支 + 注入真打包器（`L662-716` 变空，`L718` 变薄）

```python
        # L662-716 的三段手写 obj 全部删除（注册表已覆盖 90004/24000/1017，
        #   1019 不在 spec 里，保留原兜底）
        return self._cn_send_envelope(name or 'Unknown',
                                      {'Protocol': num, ...}, rec)   # 只剩兜底信封
```

打包器注入（让 `R.build()` 直接产出真 wire body，注册表零改动）：

```python
        _GR.set_packer(lambda pname, inner, rid:
                       cn_wire.wrap_response(pname, inner, rid)[0])   # -> base64 bytes
        body = _GR.build(num, ctx)        # 现在就是客户端收到的 body
```

**执行顺序建议**：`3 → 26000 → 1005 → 4000 → 24000 → 90004 → 36001 → 8006 → 1017 → 8000 → 5000/6000/29002/30041`。
前 8 个在自测里已经是**逐字节**，放上去最安全；后 6 个是结构级，接的是"新号能不能进大厅"，
本来就不该期待和官方那个 32 级号逐字节相同。
**同时停止新写 `patch_*.py`**（`patch_1017/24000/8000/90004/simple/preempt/requestid` 七个文件就是硬编码模式的产物），
否则两套分发会互相覆盖。

---

## 5. 自测结果（实际跑出来的）

`registry_selftest.py` 五段：① 登记面 ② 契约面 ③ 与 spec 对账 ④ 回放面（+ 新号构建）⑤ 接口差异。

命令：

```bash
python work\ba\server\deploy\registry_selftest.py            # 每个协议取首选样本
python work\ba\server\deploy\registry_selftest.py --sweep    # 官方 109 条里能用的全跑
```

退出码 0。三层比对口径（为什么不是"直接比 packet 字节"）：

1. **inner 层**：紧凑 JSON 逐字节比（这就是 `packet` 字段里那串字节）→ 最强
2. **结构层**：遍历比较键集/键序/嵌套形状，忽略标量值与列表长度；record 结构差异算错，
   map 键集合/键序差异算数据（protojson 的 map 是按 key 字符串排序的）
3. **明文层**：我们的 `build()` 字节 vs 官方 `plain` 字段逐字节比 → 证明外层信封也一致

加密层（AES/base64）不在自测范围：那是 bridge 的 `cn_wire` 的事，本自测不 import bridge。

### 5.1 逐协议结果

| 协议 | 名字 | 样本 | 回放 | spec_check | 新号构建 | inner B（回放 / 官方） | 外层明文逐字节 |
|---|---|---|---|---|---|---|---|
| 3 | NetworkTime_Sync | `04` | **PASS_BYTE** | PASS | PASS | 314 / 314 | **YES** |
| 1005 | Account_GetTutorial | `07` | **PASS_BYTE** | PASS | PASS | 320 / 320 | **YES** |
| 1017 | Account_LoginSync | `02` | PASS_SHAPE | PASS | PASS | 83804 / 167287 | no |
| 4000 | Item_List | `03` | **PASS_BYTE** | PASS | PASS | 10582 / 10582 | **YES** |
| 5000 | Echelon_List | `47` | PASS_SHAPE | PASS | PASS | 616 / 2768 | no |
| 6000 | Campaign_List | `44` | PASS_SHAPE | PASS | PASS | 335 / 30540 | no |
| 8000 | Mission_List | `08` | PASS_SHAPE | PASS | PASS | 4297 / 183441 | no |
| 8006 | Mission_GuideMissionSeasonList | `09` | **PASS_BYTE** | PASS | PASS | 109043 / 109043 | **YES** |
| 24000 | Academy_GetInfo | `01` | **PASS_BYTE** | PASS | PASS | 11685 / 11685 | **YES** |
| 26000 | ContentSave_Get | `05` | **PASS_BYTE** | PASS | PASS | 321 / 321 | **YES** |
| 29002 | Billing_PurchaseListByYostar | `23` | PASS_SHAPE | PASS | PASS | 305 / 744 | no |
| 30041 | EventContent_PermanentList | `58` | PASS_SHAPE | PASS | PASS | 269 / 1368 | no |
| 36001 | Notification_EventContentReddotCheck | `16` | **PASS_BYTE** | PASS | PASS | 587 / 587 | **YES** |
| 90004 | Management_Data | `06` | **PASS_BYTE** | PASS | PASS | 9691 / 9691 | **YES** |

**汇总：逐字节 8 / 结构一致 6 / 结构不一致 0 / 新号构建合法 14/14。**

`--sweep`（把官方 109 条里对应协议的全部样本都回灌一遍）的额外战果：

| 协议 | 样本数 | 逐字节 | 说明 |
|---|---|---|---|
| 24000 | 2 | **2** | `01` / `96` 两条都完全相同 |
| 36001 | 10 | **10** | 10 条全同（键集合 10/10 稳定这个断言在 registry 下也成立） |
| 90004 | 10 | **10** | 10 条全同（含运营数据非空的那几条） |
| 5000 | 4 | 0 | 4/4 结构一致 |
| 29002 | 3 | 0 | 3/3 结构一致 |
| 8000 | 3 | 0 | 3/3 结构一致（含 849 / 10838 两个活动变体，行数 39/35 与官方**条数完全相等**） |

### 5.2 逐条解释"为什么不是逐字节"

| 协议 | 差异位置 | 根因 | 是 registry 的问题吗 |
|---|---|---|---|
| 1017 | `CafeVisitCharacterDBs` 只含初始 4 角色（官方 8+）；`CurrencyDict` 键序数值序 vs 官方字符串字典序（Go map）；`ServerTimeTicks` 差 4 ticks（0.4 µs） | `gen1017.build()` **不收 ticks**（只能给 `now` → µs 精度）；账号状态来自 `account_state`，只传了 `None`（骨架） | ❌ 不是。`account_state` 是设计好的注入口，只是我们手上没有官方那个号的完整状态；键序那两处是 `gen1017` 自己的序列化口径（要改就违反本次"不改生成器"） |
| 8000 | `ProgressDBs` 4 条 vs 官方 1240 条；`StartDate` = 今日 04:00+账号 jitter vs 官方玩家真实首见时间 | `build_response()` 只接受 `profile=seed/empty` 和 `event_content_id`，**没有 rows 注入口**；`StartDate` 是合成值（设计如此） | ❌ 不是。这是 `gen8000` 的接口缺口，标注为"额外工作"（给它加一个 `progress_rows=None` 参数即可，属改变现有生成器，本次禁止） |
| 5000/6000/29002/30041 | 行数少（616 vs 2768 B 等） | `build_standalone()` 吃 `account_state`，传 `None` → 走 `initial_state_rules` 骨架 | ❌ 不是。同上，注入口已就绪 |
| 4000 | `ItemDBs` 1 条 vs 官方 134 条 | 新号只有 `DefaultParcelExcelTable` 那 1 行 | ❌ 不是。适配层 `item_rows` 注入了官方 134 条后**逐字节相同**（上面表里的 PASS_BYTE 就是这个模式） |
| 1005 | 回放 PASS_BYTE；新号 267 B vs 官方 320 B | `TutorialIds` 是新号 `[]` vs 官方 21 条 | ❌ 不是。`tutorial_ids` 注入口就绪 |

### 5.3 时钟精度（唯一一个**无法消除**的指标差）

官方 `ServerTimeTicks` 不是整微秒（例：`639304002549765374` → `0.4 µs` 尾巴）。
.NET ticks 是 100 ns，Python `datetime` 是 µs，所以：

- `gen3 / gen24000 / gen8006 / gen36001 / 90004 / 1005 / 4000 / 26000` 收 `ticks` ⇒ **原值直传，0 误差**（这就是它们能逐字节的原因之一）
- `gen1017 / gen8000 / 5000 / 6000 / 29002 / 30041` 只收 `now` ⇒ ticks 由 µs 反推，**最多差 9 ticks（0.9 µs）**

生产上无所谓（`ServerTimeTicks` 本来就是"现在"），但"拿官方抓包当期望值做逐字节比对"时，
这 4 ticks 会稳定出现。registry 的适配层已经用 `server_time_ticks` 优先、`now` 兜底来把这误差压到最小。

### 5.4 registry 契约面（7 项全 PASS）

```
[PASS] 拒绝重复注册              协议 3 已注册（NetworkTime_Sync，来自 gen3.build_3）；拒绝静默覆盖
[PASS] 未知协议拒绝              未知协议抛 RegistryError
[PASS] 缺 ctx 键报 MissingContext  MissingContext: 协议 3 (NetworkTime_Sync) 缺少 ctx 键 ['mx_token', …]
[PASS] 外层信封自洽(14/14)        外层键序恒为 [protocol, packet, requestid]；requestid == inner RequestId；packet 回解 == inner；protocol 名 == 登记名
[PASS] 打包器可注入              set_packer() 生效
[PASS] 陌生 ctx 键容忍            整包 ctx 丢进来不炸
[PASS] mx_token 别名            mx_token / mxtoken 等价
```

第 4 项值得单独说：它把"外层 requestid 必须等于 inner RequestId"这条官方不变量
**从 109 条抓包的经验事实，变成 14 个协议的可执行断言**。这条以前没人管
（`patch_requestid.py` 那一堆工作就是在补这个洞），现在 `build()` 天然满足。

### 5.5 接口不一致：由登记表自身推出来的（自测 ④ 段原样输出）

以下四行不是人工断言，是 `R.get(p).requires / .optional / .returns / .source` 当场统计出来的 ——
**这就是"现有生成器接口不统一"的可执行证据**：

```
返回类型不一致   : tuple 返回 [8000]；其余 13 个返回 dict
时间入口不一致   : 14/14 个协议可由 server_time_ticks 驱动；只有 [1017, 5000, 6000, 8000, 29002, 30041]
                   额外接受 now 覆盖（原生成器只收 now）
状态注入口不一致 : 11 个协议有状态槽 [1005, 1017, 4000, 5000, 6000, 8006, 24000, 29002, 30041, 36001, 90004]
requires 长度分布: {4: 14}（14 个协议现在统一为 4 个必填键）
真入口分散在     : ['dto90004', 'gen1017', 'gen24000', 'gen3', 'gen36001', 'gen8000', 'gen8006', 'simple_payload']
```

两个数字值得记住：适配前 14 个协议的入口分散在 **8 个模块**、必填键各不相同；
适配后**全部收敛成同一组 4 个必填键**（`account_id / mx_token / request_id / server_time_ticks`）。
这就是"统一分发点"能不能成立的分水岭 —— 现在成立。

---

## 6. 已知未覆盖的协议（24 个）

`official_spec.json` 有 38 个协议，registry 覆盖 14 个，剩 24 个**没有任何生成器**。
按"抓包证据量 / 结构复杂度"排序（抓包数是 `report/_tmp/official_decoded_201` 里该协议的 response 条数）：

| 优先级 | 协议 | 名字 | 抓包 | 备注 |
|---|---|---|---|---|
| ★★★ | 25003 | Event_RewardIncrease | **21** | obs=high；结构小，最划算的第一批 |
| ★★★ | 7001 | Mail_Check | **9** | obs=high；信箱是进大厅的必经 RPC |
| ★★★ | 43010 | Friend_Check | **8** | obs=high |
| ★★★ | 28019 | Clan_Check | **8** | obs=high |
| ★★ | 5001 | Echelon_Save | 2 | 写操作，改状态语义要先定 |
| ★★ | 90009 | Clan_Chat_Records | 2 | obs=medium |
| ★★ | 22000 | Arena_EnterLobby | 2 | obs=medium |
| ★★ | 20001 | Cafe_Ack | 1 | 写操作 ACK，要状态机 |
| ★ | 1002 | Account_Auth | 1 | bridge 自己造（登录/鉴权），**不需要**响应生成器 |
| ★ | 6020 / 6021 | Campaign_EnterMainStageStrategySkip / …Result | 1 / 1 | 一对请求-结果，要一起做 |
| ★ | 7000 / 7003 | Mail_List / Mail_ListSemiPermanent | 1 / 1 | 和 7001 同族，可一批 |
| ★ | 8002 | Mission_MultipleReward | 1 | 和 8000 同族 |
| ★ | 10002 | Shop_List | 1 | ExcelDB 有商店表，可推 |
| ★ | 15002 | OpenCondition_EventList | 1 | — |
| ★ | 16000 | Toast_List | 1 | 极简，适合练手 |
| ★ | 20013 | Cafe_ReceiveCurrency | 1 | 写操作 |
| ★ | 22004 / 22008 / 22009 / 22016 | Arena_* | 1 / 1 / 1 / 1 | 竞技场一族 |
| ★ | 28000 | Clan_Lobby | 1 | — |
| ★ | 35003 | MiniGame_MissionList | 1 | 和 8000 同族（小游戏任务表） |

> 注意：**38/38 个协议都有抓包**（109 条 = 14 个已覆盖 40 条 + 24 个未覆盖 69 条），
> 所以"没有生成器"不等于"没有证据"，补起来都有基准可对。

---

## 7. 边界 & 风险

1. **本次零侵入**：没有 import / 修改 `account_auth_probe.py`、`cn_wire.py`；没有改任何 `gen*.py`；
   没有改 `official_spec.json` / `dto_schema_full_v2.json`；没有连服务器；没有删文件。
   已用文件时间戳核对：`gen*.py` / `gen_common.py` / `simple_payload.py` / `dto90004.py` /
   `official_spec.json` / `dto_schema_full_v2.json` / `spec_check.py`（5:10–5:25）与
   `_bridge_ref\account_auth_probe.py` / `_bridge_ref\cn_wire.py`（11/14 14:50）全部**早于本次会话开始**，
   本次只新增三个文件。
   （注：本目录不是 git 仓库；`deploy\_compat_check\`、`deploy\_scratch\` 下另有并行任务的产物，与本任务无关。）
2. **注册表不产 wire body**（默认）：这是分层，不是省事。按约定它不能 import bridge，
   而 AES 加密在 `cn_wire`。接 bridge 时一行 `set_packer()` 即可（§4 步骤 3）。
   如果评审要求 `build()` 必须直接返回可发送字节，那就是引入 `cryptography` 依赖 + 复制
   `cn_wire.IV_FIXED`——反而制造第二份真源，**不建议**。
3. **依赖面**：`1017/8000/8006` 运行时需要 `specgen.py` + `official_spec.json` + `initial_state_rules.json`
   + `ExcelDB.db`。bridge 部署机上如果没有这些文件，`autodiscover()` 会把它们记进 `errors()`
   并**跳过登记**（其余协议照常可用）。接 bridge 前要确认部署机的文件清单。
4. **`--sweep` 的 8000 活动变体判别**是自测里的启发式（全 Category=8 ⇒ 活动样本），
   只用于自测，不进 registry。
5. **1017 的两处序列化口径**（`CurrencyDict` 数值序 / `CafeVisitCharacterDBs` 内容）
   要真正逐字节，必须改 `gen1017`——本次明确不做，已记录在 §5.2。
6. **`item_rows` 注入槽**是适配层对 `4000` 的"扩权"（§2.1 第 3 条），评审需要认可这一处。

---

## 附录 A：文件清单

| 文件 | 行数 | 说明 |
|---|---|---|
| `work\ba\server\deploy\generator_registry.py` | 787 | 注册表 + 14 段适配 + 打包器 + `UNCOVERED` |
| `work\ba\server\deploy\registry_selftest.py` | 601 | 五段自测（登记 / 契约 / 对账 / 回放 / 接口差异） |
| `work\ba\server\deploy\REGISTRY_DESIGN.md` | 424 | 设计 + 结果 + 接 bridge 方案 |

## 附录 B：复现命令

```bash
cd C:\Users\su\Desktop\大肥鱼项目\BAServer

python work\ba\server\deploy\generator_registry.py list       # 14 个协议清单
python work\ba\server\deploy\generator_registry.py build 24000 --plain
python work\ba\server\deploy\registry_selftest.py             # 主自测（exit 0）
python work\ba\server\deploy\registry_selftest.py --sweep     # 官方 109 条全跑
python work\ba\server\deploy\registry_selftest.py --json      # 机器可读结果
python work\ba\server\deploy\registry_selftest.py --only 24000,90004 --verbose
```

对照上游（都不改写）：

```bash
python work\ba\proto\spec_check.py --all                      # 109/109 PASS（已知结果）
python work\ba\server\deploy\gen36001.py --verify-official    # 单个生成器自证
```
