# 通用空构造引擎（empty_builder）设计与风险交割

> 交付物：`work\ba\server\deploy\empty_builder.py` + `empty_skeleton_rules.json` +
> `dto_extra\proto35003_minigame_mission.json` + `dto_extra\proto29002_purchase_count.json` +
> `empty_builder_selftest.py`（+ 本文件）。
>
> 边界：**纯本地**。不连服务器、不 ssh、不碰 bridge / 手机 / nginx、不改
> `specgen.py` / `official_spec.json` / `initial_state_rules.json` / `ExcelDB.db` /
> 任何 `gen*.py` / `generator_registry.py` / `registry_selftest.py` / `account_auth_probe.py`，
> 不删任何文件。所有比对基准来自 `report\_tmp\official_decoded_201`（109 条官方解密响应）。

---

## 0. 一句话 + 实测数字

**「1017 之后那 9 个没有生成器的小协议，8 个用通用空构造就能上，1 个（35003）配一张 18 行的静态骨架，
0 个需要玩家真实进度」——这句话落地成了一个 700 行的适配层 + 一张 18 条的规则表 + 2 份骨架数据。**

自测实跑结果（`python work\ba\server\deploy\empty_builder_selftest.py`，退出码 0）：

| 验收项 | 结果 |
|---|---|
| 42 条断言 | **PASS 42 / FAIL 0** |
| 18 个协议键序与官方一致 | **18 / 18** |
| 18 个协议键集合与官方一致 | **18 / 18** |
| `spec_check` 判定 | **18 / 18 PASS**（0 FAIL） |
| record 级形状错误（缺键 / 多键 / 类型 / 键序） | **0**（18/18 干净） |
| 与官方 inner 逐字节相同 | **11 / 18** |
| 9 个未覆盖协议（U 组）产物无形状错误 | **9 / 9** |
| 三个拒绝断言 | **3 / 3 生效**（另加 4 个 forbidden/delegate 也全拒） |
| 规则表硬约束 | **0 个问题**（10 条 empty 全部有 `until`） |

18 个协议的构成：**U 组 9 个原本无生成器**（16000 / 25003 / 15002 / 7001 / 28019 / 43010 / 7003 / 7000 / 35003）
＋**C 组 9 个有生成器做对照**（4000 / 3 / 26000 / 90004 / 1005 / 8000 / 8006 / 36001 / 29002）。
C 组不是拿本引擎跑，而是拿 **`generator_registry.build_inner`** 跑 —— 这样同一套断言落在**独立产物**上也能过，
才说明这套比对方法是灵敏的，而不是自证。

---

## 1. 引擎原理：`Spec.build(proto, {})` 为什么能出正确骨架

真正干活的仍是 `work\ba\server\prototype\specgen.py`（531 行，已经在支撑 1005 / 4000 / 26000 / 1017）。
本层一行都没改它，只是把它的能力重新组织。

### 1.1 三个动作

```
Spec.default(node)           每个节点的「结构性零值」：int→0 · float→0.0 · str→"" · bool→false
                             array→[] · map→{} · type=null→None · object→递归
Spec.conform(value, node)    把任意残缺数据投影到 spec 形状上：
                               spec 有、数据没有 + always:true  → 用零值补
                               spec 有、数据没有 + always:false → **省略**（proto3 presence 语义）
                               数据有、spec 没有                → 丢弃并记账（spec 完整性探针）
Spec.build(proto, values)    conform + 按 top_key_order 重排 → 官方键序
```

关键在 `always`：`official_spec.json` 的 `always` 是「官方 109 条里这个键**每次都在**」的统计结果，
正好等于 proto3 的「字段有 presence（optional）」与「无 presence（总是序列化）」的分界。
抓包里 `{"SeasonId":5}`（8006 的 TeamInfo 只有 1 个键）就是 `always:false` 的活证据 ——
**省略不是丢数据，是 proto3 的零值省略。**

### 1.2 为什么产物必然 PASS `spec_check`（R9 的正确解读）

`spec_check.py` 的判定里，**FAIL 只有四类**：缺必填键 / 多键 / 类型不符 / 可空性不符（+ 数组元素形状）。
而 `conform()` 是**按 spec 逐节点投影**出来的：

* 必填键缺失 → `default()` 补上 → 不可能缺；
* 多键 → 只输出 `fields` 里有的键 → 不可能多；
* 类型不符 → 标量强制转换、容器强制空 → 不可能不符；
* null 出现在 `nullable=false` → `value is None` 分支直接 `default()` → 不可能。

长度越界 / 空数组首见只是 **WARN**（`spec_check.py` 第 16–18 行明确写了合法）。
所以：**「18/18 PASS」只证明形状合法，不证明客户端接受**（R9）。
这也是本设计把「形状」和「语义」分两层的原因：形状交给 spec + conform（可证明），
语义交给规则表（一条条写清依据和到期日）。

### 1.3 本层补的三件事（specgen 不管的）

| # | 事情 | 为什么必须在本层做 |
|---|---|---|
| 1 | **信封真值** | `Spec.build(proto,{})` 直接发出去是 `Protocol:0 / MxToken:"" / ServerTimeTicks:0 / RequestId:""`，必死。这 5 键在 spec 里全是 `always:true`，所以在产物上**原位替换**、键序不变 —— 零键序风险（UNCOVERED_ANALYSIS §5.3 实测过）。 |
| 2 | **骨架 / 回显** | 35003 的 18 行、29002 的 4 行、36001 的 25 键、15002 的请求键回显。这些不是「形状」能表达的东西。 |
| 3 | **拒绝** | `3` 禁止空构造（R3）；未登记协议禁止静默生成；`forbidden/delegate` 一律抛异常。**「不生成」比「生成一个看起来合法的空壳」更安全** —— 后者会把未覆盖伪装成已覆盖。 |

---

## 2. 接口与数据流

```
调用方（bridge / 未来的 registry 适配层）
   │  ctx = {account_id, mx_token, request_id, server_time_ticks | now,
   │         session_key?, request_body?, server_notification?, <注入槽>…}
   ▼
empty_builder.build_inner(protocol, ctx) →  dict（inner 明文树）
   │     ├─ rule(protocol)                → 规则表（没登记 → RuleNotRegistered）
   │     ├─ mode 检查                     → forbidden/delegate → EmptyBuildRefused
   │     ├─ _envelope()                   → 5 个信封键真值
   │     ├─ SKELETONS / ECHOES / HOOKS    → 骨架 / 回显 / 真值注入槽
   │     └─ specgen.Spec.build(proto, values) → 形状投影 + 官方键序 + 不变量自检
   ▼
调用方：envelope 已含在 dict 里 → 打包器出外层明文 → cn_wire 出 wire body
```

**返回值是 `dict`，不是 `bytes`。** 加密（AES-256-CBC + 32B 随机密钥 + base64）与信封 wire 化归
bridge / `cn_wire`；本层按约定不 import bridge、不引入 `cryptography`。
这跟现有 8 个生成器**完全一致**（它们的返回值全是 dict）。

`ctx` 契约与 `generator_registry.CTX_KEYS` 逐键对齐：
`account_id` / `mx_token`(别名 `mxtoken`) / `request_id` / `server_time_ticks` / `now` /
`session_key` / `request_body` / `server_notification`。
缺必填键抛 `MissingContext`（带协议号 + 缺哪个键 + 提示），**绝不静默发空响应**。

### 2.1 真值注入槽（「桥不是终点」的那一半）

同一份代码，数据一到位就不必改生成器，只改调用方传不传：

| 协议 | ctx 槽 | 空值 | 有值时 |
|---|---|---|---|
| 7000 | `mail_rows` / `mail_count` | `MailDBs: []` / `Count: 0` | 真邮件行 + 同源计数（R5） |
| 7001 | `mail_count` | `Count: 0` | 与 7000 同源 |
| 1005 | `tutorial_ids` | `[]` | `[1..27]` 跳过新手教程（R4） |
| 25003 | `reward_increase_rows` | `[]` | 运营活动窗口行 |
| 16000 | `toast_rows` | `null` | spec 只允许 null → 被 conform 强制回 null 并记账 |
| 15002 | `request_body.ConquestEventIds` / `conquest_event_ids` | 回显 `{id: []}`（R2） | 同左（格子数据再往值里填） |
| 35003 | `progress_rows` / `event_content_id` | 18 行零进度骨架 | 真进度行 |
| 29002 | `purchase_rows` / `reset_dates` | 4 行 `PurchaseCount:0` | 真购买次数（回灌官方 4 行 → **逐字节相同**） |
| 36001 | `cg_keys` / `reddots` | 25 键全 `[]` / `{}` | 真解锁列表 |

---

## 3. 规则表 `empty_skeleton_rules.json`

### 3.1 格式

顶层是**协议号键**（`"16000"` 这种）+ 一个 `_meta`（仓库既有约定，`dto_extra\*.json` 也是这么写的）。

```jsonc
"16000": {
  "name": "Toast_List",              // 必须与 official_spec.json 的 name 一致（validate_rules 会查）
  "mode": "empty",                   // empty | skeleton | delegate | forbidden
  "until": "Toast / 公告弹窗投递功能上线前",   // ★ mode=empty 必填，非空
  "until_owner": "toast_delivery",   // 到期触发器（机器可读的短名）
  "own_fields": ["ToastDBs"],        // ★ 本协议「自己的」顶层字段（自测拿它判定差异是否越界）
  "empty_output": {"ToastDBs": null},// 只记「与 spec 零值不同」的覆盖（大部分是零覆盖）
  "echo_keys_from_request": {...},   // 只有 15002 有：键来自请求
  "overlay_keys": [],                // 这几个键由骨架/回显/注入槽接管
  "skeleton_from": null,             // mode=skeleton 必填
  "official_observations": 1,        // 官方抓包里这个协议有几条样本（置信度）
  "risk": ["R10"],                   // 对应 UNCOVERED_ANALYSIS 的风险编号
  "note": "..."                      // 判断依据 + 坑
}
```

### 3.2 四种 mode

| mode | 条数 | 含义 | `build_inner` 行为 |
|---|---|---|---|
| `empty` | **10** | 只靠 spec 零值 + 真实信封 | 生成 |
| `skeleton` | **3** | spec 零值 + 一组静态骨架 | 生成 |
| `delegate` | **1**（90004） | 数据是**运营数据**不是账号数据，交给既有生成器 | 抛 `EmptyBuildRefused` |
| `forbidden` | **4**（3 / 4000 / 8000 / 8006） | **禁止**任何空构造（置零会让客户端算错状态） | 抛 `EmptyBuildRefused` |

10 条 `empty`：`16000 / 25003 / 15002 / 7001 / 28019 / 43010 / 7003 / 7000 / 26000 / 1005`
3 条 `skeleton`：`35003 / 29002 / 36001`

> `26000` / `1005` 加 `"prefer": "generator_registry"`：它们已有逐字节生成器，
> 登记成 empty 是为了证明**两条路等价**（自测第 (8) 段：26000 / 1005 / 36001 两条路产物逐字节相同），
> 生产仍走 registry。

### 3.3 每条 `empty` 的 `until`（战略：空构造是桥，不是终点）

| 协议 | until | 到期后的动作 |
|---|---|---|
| 16000 | Toast / 公告弹窗投递功能上线前 | 换真生成器（`toast_rows` 槽已有） |
| 25003 | 活动加成运营配置接入前 | 填 `reward_increase_rows` |
| 15002 | 征服战格子数据接入前 | 回显骨架保留，往值里填 tiles |
| 7001 | 邮件投递上线前 | `mail_count` 必须与 7000 同源（R5） |
| 28019 | 工会系统上线前 | 换真生成器（Clan 状态） |
| 43010 | 好友系统上线前 | 换真生成器（Friend 状态） |
| 7003 | 半永久 / 运营邮件投递上线前 | 换真生成器（**和 7000 是两个门**，别只改一个） |
| 7000 | 邮件投递上线前 | `mail_rows` + `mail_count`（R6） |
| 26000 | 存档同步功能上线前 | 走 registry（已逐字节） |
| 1005 | 新手教程流程接上真实进度前 | `tutorial_ids`（R4 是产品决策） |

（`skeleton` 的三条也写了 `until`：35003 要真进度时 / 29002 要真购买次数时 / 36001 要真 CG 状态时。
键目录那 25 个**永久保留**，只换值。）

---

## 4. 骨架数据：哪些是推导的，哪些是抄的

**逐条注明来源**（这是本节最重要的事）：

| 协议 | 来源类型 | 具体 | 验证 |
|---|---|---|---|
| **35003** | **推导**（ExcelDB）+ 抄一份做兜底 | `MiniGameMissionDBSchema` 里 `slot1(EventContentId)==10838` 的 18 行；`SQL Id` 就是 `MissionUniqueId`；`slot4` 是 `Category`(恒 7)；`slot18` 是 `vector<int64>` 进度参数键 | MissionUniqueId 18/18、Category 18/18、ProgressParameters 键 **18/18** 与官方一致（自测第 (5) 段当场断言） |
| **29002** | **抄**（官方抓包） | 4 个 `ShopCashId`（900000 / 1597 / 11023 / 15039）；`PurchaseCount` 归 0；`ResetDate` 用官方原文 | 4 个 id 全部在 `ShopCashDBSchema`(656 行) 里（存在性 4/4）；行数 4/4；回灌官方 `CountList` → **逐字节相同** |
| **36001** | **已有 DTO**（不新增文件） | `work\ba\proto\dto_extra\proto36001_reddot.json` → `catalog_constants.eventcontentunlockcg_keys.keys`（25 个） | 键集合与官方 10/10 稳定集合一致；键序按**字符串**字典序（protojson 输出 Go map 的口径）→ 与官方**逐字节相同** |
| 90004 | 不接管 | 交给 `dto90004.build_90004_management_data`（`ops` 槽） | 自测 C 组逐字节 |

独立骨架文件放在 **`work\ba\server\deploy\dto_extra\`**（任务书指定的位置），
`_load_dto()` 先找这里、再找 `work\ba\proto\dto_extra\`，所以 36001 的 DTO **零拷贝**引用。

### 4.1 35003 的 `ProgressParameters` 键是怎么推导出来的（含语义边界）

`MissionUniqueId = EventContentId × 10000 + i` 上一轮已经指出了；真正没解的是 **`ProgressParameters` 的键**。
解在 `MiniGameMissionDBSchema.slot18`：它是一个 `vector<int64>`：

| 行 | slot18 | 官方 `ProgressParameters` | 规则 |
|---|---|---|---|
| 0–5（108380000–005） | `[10838]` | `{"10838": 0}` | 键 = `EventContentId` 本身 |
| 6–16（108380006–016） | `[10838, 110838101…]` | `{"110838101": 0}` | 键 = `MiniGameDefenseStageDBSchema.Id`（11 行，Id 升序逐个对应） |
| 17（108380017） | `[108380006 … 108380016]`（11 个 MissionUniqueId） | `{}` | 全是本表 MissionUniqueId → 一个都不剩 |

于是规则写成一句可执行的：

> **`key` = `slot18` 里「不属于本表 `MissionUniqueId` 集合」的元素中的最大值；一个都不剩 → `{}`。**

**18/18 拟合官方。** 但必须说清楚：**这是经验规则，不是语义**。
推测的解释是「slot18 列出这行任务挂在哪些进度参数上，前面的更粗（活动级）、后面的更细（关卡级），
服务端只落最细的那个；行 17 是『通关前 11 关』的复合目标，进度按子任务记，所以自身为空」——
**没有任何客户端 / 服务端代码证据**。已知的行为等价，未知的是「换一个活动内容还成不成立」，
所以规则表与 DTO 都把这条标成 `unknowns`，并留了 `progress_rows` 注入槽 + `captured_rows` 兜底。

---

## 5. 与 `generator_registry.py` 的集成点（**不改那个文件**）

现状：`generator_registry.py`（857 行）已经把「登记 → 适配 → 打包」三层做好了，
`REGISTRY_DESIGN.md` 定的接口就是 `build_inner(proto, ctx) -> dict`。
本层的返回值与它**完全同构**，所以接线是「加 9 行登记」，不是改造：

```python
# ---- 在 deploy/ 里新增（不要改 generator_registry.py 本体，除非走 patch 流程）
def _adapt_empty(proto):
    def builder(ctx):
        EB = _mod("empty_builder")            # 与 _mod("gen3") 同一套延迟 import
        return EB.build_inner(int(proto), ctx) # ← 本层的对外接口
    builder.__name__ = "adapt_empty_%d" % proto
    return builder

# adapter_table() 追加（现有 14 条一行不动）：
#   (16000, "Toast_List", _adapt_empty(16000),
#    ["account_id", "mx_token", "request_id", "server_time_ticks"],
#    ["request_body", "now", "session_key", "server_notification"],   # ← request_body 给 15002/35003
#    "empty_builder.build_inner", "dict", "通用空构造：spec 零值 + 真实信封；until 见规则表"),
#   … 25003 / 15002 / 7001 / 28019 / 43010 / 7003 / 7000 / 35003 …
# ADAPTER_MODULES 追加：16000: ("empty_builder",), …
```

三个接线注意事项（都是踩过的坑）：

1. **把 `request_body` 写进 `optional`**，否则 `check_ctx()` 会把 bridge 传进来的 `request_body`
   列进 `unused`（只提示、不报错，但会误导）。15002/35003 **必须**真的传，否则 R2 复活 / 35003 退回默认活动号。
2. **`mx_token` 必须传**：`Registration.requires` 里本来就有它，本层的 `_session_key()` 也要求非空 ——
   两侧契约一致，不会出现「registry 放行、本层抛 MissingContext」的错位。
3. **`build_inner` 已经带着信封**，所以 registry 的 `packer` / `cn_wire` **不要再 update 一次信封**。
   现有 `gen36001` 等也是这个约定（`account.envelope(proto)` 在生成器内部完成）。
   `pack_plaintext()` 只做 `{"protocol": name, "packet": inner, "requestid": rid}`，与本层不冲突。

另一条更轻的接法（如果不想动 registry）：bridge 侧直接
`from empty_builder import build_inner` 然后 `cn_wire.wrap_response(pack_plaintext(...))`。
本层不 import bridge，两条路都成立。

---

## 6. 风险清单：`UNCOVERED_ANALYSIS.md` 的 R1–R10 逐条落到实现

| 编号 | 原风险 | 本实现怎么处理 / 规避 | 自测断言 |
|---|---|---|---|
| **R1** | 36001 `EventContentUnlockCGDBs` 从 25 键变 0 键 → 客户端 `dict[id]` 抛 `KeyNotFoundException` | **填满 25 键**（`cg_keys()` 从既有 DTO 取）；**键序按字符串排**（protojson 输出 Go map 的口径），否则键集合对但字节不对。代价≈0，不冒这个险 | `25 键` / `键集合一致` / `键序一致` / `逐字节相同` 4 条 |
| **R2** | 15002 `ConquestTiles` 从 `{"50822":[]}` 变 `{}` → 客户端可能遍历自己发的 id 去查 map | **从 `ctx['request_body']['ConquestEventIds']` 逐个填 `[]`**；`request_body` 缺失时退回 `{}` 并**记账**（`issues.force`），不静默 | `ConquestTiles 键 == 请求 ConquestEventIds`（请求 `[50822,50823,849]` → 响应同序）+ `官方请求体回放逐字节相同` |
| **R3** | 3 `NetworkTime_Sync` 两个 tick 置 0 → 客户端时钟偏移算错、所有倒计时错乱 | **规则表 `mode:"forbidden"` + `build_inner` 直接抛 `EmptyBuildRefused`**。双保险：即使有人手工往规则表里加 `"3": {"mode":"empty"}`，`own_fields` 里那两个 tick 也不会有值 —— 但正确做法是别改这一条 | `build_inner(3, …) 被拒绝` |
| **R4** | 1005 `TutorialIds: []` → 客户端重放整个新手教程（**产品风险不是异常风险**） | 结构合法（`q7_tutorials` confidence high）+ **`tutorial_ids` 注入槽**。文档与规则表都写明「这是产品决策」：1017 如果已经给了教程之后的东西，就该填 `[1..27]` | 「新号模式 13/13 PASS」覆盖；R4 本身**不是**自测能判的（要客户端证据） |
| **R5** | 7001 `Count` 与 7000 `MailDBs` 不一致 → 红点亮着但点进去 0 封 | 空构造下两边天然都是 0；**注入槽要求调用方传同一个 `mail_count`**（规则表 note 写明「必须同源」） | 两个协议的注入槽共用 `mail_count` 键 |
| **R6** | 7000 `MailDBs: []` 但服务端其实发了邮件 → 在撒谎 | 规则表 `until` 明确写「邮件投递上线前」；`default_mail` 一旦落地就必须换成 `mail_rows`。这是**本批最可能提前过期的一条** | 规则表 `until` + 自测第 (1) 段强制非空 |
| **R7** | 35003 官方字段名是 `ClearedOrignalMissionIds`（`Orignal` 拼错），改拼写会让 `spec_check` FAIL | 代码里写死 `ClearedOrignalMissionIds` 并加注释；**`conform` 只输出 spec 里有的键**，所以就算有人手写 `ClearedOriginalMissionIds` 也会被丢弃 + 记账（`dropped`）而不是漏出去 | `拼写坑：字段名必须是 ClearedOrignalMissionIds` 断言 |
| **R9** | `spec_check` PASS 不能当「语义正确」的证据（长度越界/空数组首见都是 WARN） | 自测**不把 PASS 当结论**：另设「差异定位」段（值差异必须落在 `own_fields` ∪ 信封里）+ 逐协议 **WARN 计数明示**。回放模式下 U 组只有 7000 / 25003 各 2 条 WARN；新号模式下 1005 / 7000 / 25003 各 2 条、15002 1 条 —— **全部是「空数组 / 空 map / 长度越界」这类被 `spec_check` 显式承认为合法的形态** | `所有差异都落在容器字段/信封上` + 控制台逐行 WARN 数 |
| **R10** | 字节数不能当结构证据（wire 长度 = `4·ceil((PKCS7pad(plain,16)+32)/3)`，分辨率 16 B） | 自测**从不比字节数**：比的是「键序 / 键集合 / record 形状 / 逐字节 inner」。逐字节比的是 **inner 紧凑 JSON**（= `packet` 字段里的那串字节），不是 wire body | 全部 18 行的比对口径 |
| R8（90004，不在本批） | `Data` 全 `[]` 会让抽卡概率公示页空白（合规） | 规则表 `mode:"delegate"`，交给 `dto90004` + `ops` 注入槽，本层不接管 | C 组 `逐字节相同` |

补充：`_invariants()` 在每次 `build_inner` 之后自检「信封 5 键非空 + `Protocol` 自洽 + 顶层键序 == spec」，
不满足就抛异常 —— 这是防止未来有人改规则表把信封改坏的最后一道闸。

---

## 7. 到期提醒（谁上线，谁就得换）

> 规则表的 `until` 是**机器可读的到期日**：`validate_rules()` 强制 `mode:"empty"` 必须有非空 `until`，
> 所以这张表不可能悄悄变成「假装是终态的空构造」。

| 触发器（`until_owner`） | 到期协议 | 到期后必须做什么 | 证据/备注 |
|---|---|---|---|
| `mail_delivery`（邮件投递） | **7000 / 7001 / 7003** | 7000 填 `mail_rows`，7001 填同源 `mail_count`；7003 是**另一个邮箱**（半永久/运营邮件），要单独实现 | R5 / R6；`default_mail` 字段映射尚未闭合（confidence medium） |
| `clan_system` | 28019 | 换真生成器（Clan 状态：加入/申请/红点） | 零自有字段，但「有工会」之后不能永远回 5 键信封 |
| `friend_system` | 43010 | 换真生成器（好友申请/在线状态） | 同上 |
| `toast_delivery` | 16000 | 换真生成器（`toast_rows`） | spec 现在只见过 `null`，一旦非 null 出现，spec 会先报错 |
| `event_reward_increase_config` | 25003 | 填 `reward_increase_rows`（活动窗口） | 官方 21/21 恒 1 行、无 AccountServerId |
| `conquest_tile_data` | 15002 | 保留回显骨架，往 `[]` 里填 tiles | R2 的回显是永久的，只有值会变 |
| `minigame_mission_progress` | 35003 | 填 `progress_rows`（真进度）；键规则要按新活动内容重新核对 | 规则是 18 行经验拟合，换 EventContentId 要重验 |
| `shop_purchase_state` | 29002 | 填 `purchase_rows` / `reset_dates`（按商品周期算最近重置点） | `ResetDate` 目前抄官方，是**纯猜测** |
| `event_content_cg_state` | 36001 | 只换值（`cg_keys` 25 键**永久保留**） | R1 |
| `content_save_sync` | 26000 | 走 registry（已逐字节） | — |
| `tutorial_progress` | 1005 | 填 `tutorial_ids`（R4 产品决策） | `q7_tutorials` confidence high：新号就是 `[]` |

**一句话**：这 10 条里，**7000/7001/7003（邮件）+ 28019（工会）+ 43010（好友）** 是最可能最先到期的 5 条，
它们同时也是「空构造最省事」的 5 条（自有字段 ≤ 1）。这正是「用桥换时间」的价值所在。

---

## 8. 还需要更多证据的地方（诚实清单）

1. **`StartDate` 的时区口径未定。** 35003 官方 18 行同值 `2026-11-12T21:05:39.015`（= 该号首次见到该活动内容
   的时间，不可从配置推）。本引擎按仓库既有口径（`fmt_time`，UTC）输出。
   **但有一条反证**：25003 的 `BeginDate: 2026-11-12T04:00:00` / `EndDate: 2026-11-19T03:59:59`
   与 29002 的 `ResetDate: 2026-11-16T04:00:00`（抓包时刻 = bj 04:31）都像是 **+08 本地时间**（04:00 起算）。
   现有生成器**没有任何一个**是「自己算出一个时间戳然后被官方逐字节验证过」的（8006/24000 都是从抓包抄时间），
   所以这个口径在本项目里**从来没有被证实过**。要闭环需要一次「新号 + 已知时间」的抓包。
2. **35003 `slot18` 的语义未闭合**（见 §4.1）：18/18 拟合，但没有代码证据，换活动内容要重验。
   顺带一个实测：同一个推导函数对 `EventContentId=804`（另一个历史小游戏活动）给出 **44 行 / Category=6**，
   键规则照样套得上（`[804]` / `[804, 8040101]` 两种形态）——
   说明这套推导**不是只为 10838 写死的一套常数**，但 `official_spec.json` 里 `ProgressDBs` 的
   `len_min=len_max=18` 只是 10838 的观测，行数一变就会出 WARN（合法，不 FAIL）。
3. **29002 `ResetDate` 对新号该是什么，纯猜。** 4 个商品看着是 日 / 月 / 自定义 三种周期（都是 04:00），
   本实现保留官方值（过去时刻 + `PurchaseCount:0` 语义自洽）。
4. **29002「哪 4 个商品该出现」不可从配置推导。** 4 个 id 都在 `ShopCashDBSchema`(656 行) 里，
   但逐字段试过没有任何 slot 组合能把 656 行精确筛成这 4 行（共同的只有 `slot2==1 / slot3==1`，
   表里几百行都这样）。所以这是**账号购买记录**决定的，不是配置。
5. **`ServerNotification` 位掩码语义是推测。** 抓包里它按协议恒定（7001→8 / 28019→2048 / 43010→0 / 7000→8），
   本层默认 0（= 什么都不用刷新，poll 型 RPC 安全）。官方原值可用 `ctx['server_notification']` 覆盖。
   本批 U 组里 7000/7001/28019 的「差异」就是这一项。
6. **15002 请求里的 `WorldRaidSeasonAndGroupIds` 没有回显位置。** 响应 spec 只有 6 键（`ConquestTiles` 是唯一自有字段），
   所以这部分信息被丢弃。如果客户端要世界战/集团数据，那会走别的协议 —— 未验证。
7. **8000 的 `ServerTimeTicks` 与官方差几个 tick。** C 组对照里 8000 唯一「非容器」差异就是它 ——
   `gen8000` 没有 ticks 入参，内部由 `now` 推，`100ns → µs` 会丢最后 5 个 tick（`REGISTRY_DESIGN.md` §3.3 已知）。
   **不是本引擎的问题**，但提醒：本批之外如果要做到逐字节，ticks 必须原样透传。
8. **4 个协议 spec `confidence: low`、观测只有 1 次**：35003 / 16000 / 15002 / 7000 / 7003（`observations: 1`）。
   形状是按「唯一观测形态」定的，**次生形态未验证**（例如 16000 的 `ToastDBs` 非 null 会长什么样，spec 不知道）。
   这是 `official_spec.json` 的边界，不是本层的。

---

## 9. 交付物清单与复现

| 文件 | 行数/大小 | 作用 |
|---|---|---|
| `work\ba\server\deploy\empty_builder.py` | 768 行 / 34 KB | 适配层（`build_inner` + 骨架/回显/注入槽 + FlatBuffers 最小读取 + CLI） |
| `work\ba\server\deploy\empty_skeleton_rules.json` | 277 行 / 17 KB，18 条 + `_meta` | 规则表（唯一事实源） |
| `work\ba\server\deploy\dto_extra\proto35003_minigame_mission.json` | 10.7 KB | 35003 推导说明 + 推导快照（兜底）+ 官方 18 行（回归基准） |
| `work\ba\server\deploy\dto_extra\proto29002_purchase_count.json` | 3.5 KB | 29002 4 行骨架 + 官方 4 行（回归基准）+ 「4 个 id 不可推导」的证据 |
| `work\ba\server\deploy\empty_builder_selftest.py` | 570 行 / 29 KB | 42 条断言的自测（只读，不写任何输出文件） |
| `work\ba\server\deploy\EMPTY_BUILDER_DESIGN.md` | 本文件 | 设计 + 风险交割 + 到期提醒 |

```powershell
cd C:\Users\su\Desktop\大肥鱼项目\BAServer
$env:PYTHONDONTWRITEBYTECODE="1"

# 自测（42 条断言；退出码 0 = 全过）
python work\ba\server\deploy\empty_builder_selftest.py

# 规则表硬约束
python work\ba\server\deploy\empty_builder.py check-rules

# 手工跑一发（15002 要读请求体）
python work\ba\server\deploy\empty_builder.py build 15002 --json `
  --request-body report\_tmp\official_decoded_201\15_15002_api_opencondition_eventlist.request.json
```

**没有部署、没有连服务器、没有改任何既有文件。**
`python` 侧全部 `sys.dont_write_bytecode = True`，跑完 `work\ba\*\__pycache__` 无新增 `.pyc`。
