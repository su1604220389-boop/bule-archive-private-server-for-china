# TEST_REQUESTID · 把 `RequestId` 补进包体（outer.requestid == inner.RequestId）

> 生成：2026-11-16 · 作者：子 agent（deploy 线）
> 依据：`report\_tmp\official_decoded_201\`（109 条官方响应，逐条重解密）、`work\ba\server\deploy\_baseline\`（线上基线）、`report\102-最终修复方案.md`
> 交付物：`work\ba\server\deploy\patch_requestid.py`、`work\ba\server\deploy\scan_requestid_positions.py`、本文
> 前提纪律：只新增 `deploy\` 下的文件；未修改 `_baseline\`；未连服务器；所有数字均为本机实跑所得

---

## §0 一页结论

| 项 | 结论 |
|---|---|
| 官方不变量 | `outer.requestid == inner.packet.RequestId`，**109/109 成立，0 例外、0 缺失**（本机重解 `plain` 复算，非引用） |
| 我们的缺口 | `cn_wire.build_plaintext` 只写 outer，`inner_obj` 从未有 `RequestId` → 客户端取不到下一条请求的 REQUEST-ID → 链条停在 24000 |
| 改哪一层 | **方案 A（改 `cn_wire`）**。一个咽喉点覆盖全部 8 处 `wrap_response` 调用点（方案 B 只覆盖 1 处），且插入点位于所有 inner 过滤器下游（含 `MIN_KEEP` 白名单重建，见 §1.4） |
| 改动量 | `cn_wire.py`：**+81 行辅助块 + 函数体内 1 行调用 = +82 行**，删除 0 行、修改 0 行（`166 → 248` 行，`6,368 → 9,778` 字节） |
| 覆盖协议 | **全部协议**（`build_plaintext` 是唯一信封构造点；JSON 里的 `Protocol` 号无关，不按协议白名单过滤） |
| 位置规则 | 紧跟 `ServerNotification` 之后；无则 `ServerTimeTicks` → `SessionKey` → `Protocol`。该规则在官方 109 条上**键序逐字节复现 109/109** |
| 官方 RequestId 位置 | **108/109 在 index 4**（`Protocol,SessionKey,ServerTimeTicks,ServerNotification,RequestId`）；**只有 1002 在 index 3**（`Protocol,ServerTimeTicks,ServerNotification,RequestId,SessionKey`） |
| 六个 gate 复验 | 1002 / 1001 / 1010 / 24000 / 90004 / 1017 各渲一次：`outer == inner` 全 OK，键序无损，`+51` 字节 |
| 官方形状重放 | 把 109 条官方 inner 剥掉 `RequestId` 再走真实链路渲染：**outer==inner 109/109，键序与官方完全一致 109/109** |
| 开关 | `/www/wwwroot/bapatch/cn_inner_requestid.txt`，`1`=开（默认，文件不存在也是开）/`0`=关。**一行秒回滚，不改代码** |
| 验收 | `--dry-run` / `--apply` / `--verify` / `--rollback` 全部本机实跑通过（§8 有原始输出） |

---

## §1 为什么是方案 A（改 `cn_wire.build_plaintext`）而不是方案 B（改 bridge）

### 1.1 调用面：`wrap_response` 在线上 bridge 里有 8 个调用点，其中 7 个不在 `_cn_send_envelope` 里

`_baseline\account_auth_probe.py`（1,245 行，sha256 `f94b4fa0…dbc9`，与线上 11-14 15:38 版本一致）中所有 `cn_wire.wrap_response(` 调用：

| # | 行 | 所在函数 | 覆盖的协议 / 模式 |
|---|---|---|---|
| 1 | L839 | `_cn_send_envelope` | 1001 / 1010 / 24000 / 90004 / 1017 / 通用兜底 / min-envelope |
| 2 | L859 | `_cn_enc_b64`（`a_proto_int` / `b_proto_str`） | 1002 合成体 |
| 3 | L887 | `_cn_enc_b64`（`e4_strict_dto`） | 1002 strict DTO |
| 4 | L922 | `_cn_enc_b64`（`e2_nickname`） | 1002 |
| 5 | L941 | `_cn_enc_b64`（`e1_token`） | 1002（`TOKEN` 协议名） |
| 6 | L960 | `_cn_enc_b64`（`e0_proto_swap` / `cn_enc_b64`） | 1002 |
| 7 | L979 | `_cn_enc_b64`（`real_captured`） | 1002（回放真包） |
| 8 | L1019 | `_cn_enc_b64` 默认尾部（`cn_enc_b64`；`inner=dict(inner_obj)` + `apply_min_inner`） | 任意协议（协议名动态） |

**方案 B 只覆盖第 1 行 = 1/8。**

关键的第二点：`Account_Auth`(1002) **根本不走** `_cn_send_envelope`——它走 `_cn_envelope`（L679）→ `_cn_enc_b64`（L852）→ `wrap_response`（L859/887/922/941/960/979/1019 之一）。而 1002 的 `obj` 是上游网关的原样响应（`post_gateway` → `unwrap_gateway_response`，L1131），**它本来就已经带 `RequestId`**（官方响应形态）。所以：

> 方案 B 改 `_cn_send_envelope` 后，1002 仍然会「inner 有上游 RequestId、outer 是新 uuid」的**不一致**状态；
> 方案 A 在 `build_plaintext` 里做「有则同步」，顺手把 1002 这处不一致也修掉了（这正是 §5 的 [4] 用例）。

### 1.2 对 4 个已过 gate 的影响

| gate | 走的路径 | 本补丁行为 | 影响 |
|---|---|---|---|
| 1002 | `_cn_envelope`→`_cn_enc_b64`→`wrap_response` | inner 已带上游 `RequestId` → **同步分支**（覆盖成 outer 的新 uuid，键位置不动） | 键数不变（32→32），**字节数不变**，只让 inner 值 = outer 值 |
| 24000 | `_cn_send_envelope`（L812） | 无 `RequestId` → **插入分支**，index 3 | `9→10` 键，`inner +51 B`，`body +64 base64 字符` |
| 1001 | `_cn_send_envelope`（L1207） | 无 `RequestId` → 插入，index 1（该对象只有 `Protocol,AccountDB`） | `2→3` 键，`+51 B` |
| 1010 | `_cn_send_envelope`（L1187） | 同上 | `2→3` 键，`+51 B` |

1001/1010 的对象是 `cn_nick.build_nickname_response()` = `{"Protocol":…,"AccountDB":{…}}`，只有 2 键，没有任何信封基础字段，因此插入点落在 index 1（`Protocol` 之后）。**插入本身不影响客户端解析**（客户端按字段名取值），只是位置与官方的 5 键前缀不同——见 §6 的说明。

### 1.3 位置对其它调用者有没有副作用

- `build_plaintext` 的**签名、返回值、outer 三个键的名字与顺序**全部不变（`protocol` / `packet` / `requestid`），`packet` 仍然是「inner 的 JSON 字符串」而不是对象。
- AES-256-CBC + 固定 IV `JOSYdf8ys97uhFYS` + pkcs7 + `base64(ct‖key(32))` 的容器一字未动：密文仍是 `(key, IV, 明文)` 的纯函数，`--verify` 每一例都做了 `wrap_response → unwrap_response` 往返（`plain` 逐字符相同、key 32 字节、外层 JSON 可解析），即 `_baseline\cn_wire.py --selftest` 第 3 步"同一明文重加密得同一密文"的前提仍然成立。
- `wrap_raw` / `unwrap_raw`（`e3_bare_dto` 裸 payload 模式）**不经过** `build_plaintext`，因此不受影响，也**不会**拿到 `RequestId`——该模式没有 outer 信封，本来就无从同步。线上未启用（`cn_wrap_mode.txt` 不是 `e3_bare_dto`），列为已知未覆盖项（§9）。
- `inner_obj` 是**原地修改**（`dict` 的 `clear()/update()`），与 `_cn_send_envelope` 的 `rec['enc_inner_keys'] = len(obj)` 同一对象 → 该日志字段会 `+1`。这是唯一可见的日志变化，属预期（§9 有说明）。

### 1.4 决定性理由：bridge 里有三道会改 inner 的过滤器，方案 B 可能被它们吃掉

`_cn_envelope`（L679）在把 `obj` 交给 `_cn_enc_b64` 之前，会依次跑：

| 过滤器 | 行 | 行为 | 对 `RequestId` 的影响 |
|---|---|---|---|
| `apply_field_patch` | L680 / 定义 L281 | 只**补**缺失的默认键 | 无害 |
| `apply_flatten` | L681 / 定义 L414 | 只**加** `MxToken`/`AccountServerId`/`ServerId` 扁平键 | 无害 |
| `apply_min_inner` | L1017 / 定义 L368 | `cn_inner_min.txt == 'on'` 时用 `MIN_KEEP` 白名单**重建** dict：`out = {k: obj[k] for k in MIN_KEEP if k in obj}` | **`RequestId` 不在 `MIN_KEEP`（L356-365）→ 会被静默丢掉** |

也就是说：**任何在过滤器之前插入 `RequestId` 的做法（方案 B 及其变体）在 `cn_inner_min=on` 时都会白干**——键被白名单重建时丢掉，日志里只会多一条 `inner_min_dropped: ['RequestId']`。
方案 A 的插入点在 `cn_wire.wrap_response → build_plaintext` 里，位于**所有过滤器下游**，结构上免疫。这是选 A 的第四条、也是最硬的一条理由。

---

## §2 精确改动（`cn_wire.py`，166 → 248 行，+82 / −0）

### 2.1 唯一一行语义改动

```diff
 def build_plaintext(protocol_name, inner_obj, requestid=None):
     """Outer envelope. packet is the INNER JSON SERIALISED AS A STRING (so it gets \\" escaped)."""
     requestid = requestid or str(uuid.uuid4())
+    inner_requestid_apply(inner_obj, requestid)  # BA_PATCH_REQUESTID v1: outer requestid == inner RequestId
     plain = json.dumps({
         "protocol": protocol_name,
         "packet": json.dumps(inner_obj, ensure_ascii=False, separators=(',', ':')),
         "requestid": requestid,
     }, ensure_ascii=False, separators=(',', ':'))
     return plain, requestid
```

补丁**不按行号、不按参数名**定位：它先找顶层的 `def build_plaintext(` 块，再在块内找 `requestid = requestid or str(uuid.uuid4())`（找不到就退回 `plain = json.dumps({` 前一行），确认两处锚点后才动刀；任何一处对不上就 `FATAL` 拒绝改（绝不在 wire codec 里猜）。实测已在两份形态不同的 `cn_wire.py` 上落位成功：`_baseline` 那份（参数名 `protocol_name`）与同一工作区另一份最小变体（参数名 `proto_name`、无 `cryptography` 导入），后者同样被正确插入到 `build_plaintext` 体内。

### 2.2 新增的 81 行辅助块（插在 `def build_plaintext(` 之前）

函数级说明：

| 函数 | 作用 |
|---|---|
| `inner_requestid_switch_paths()` | 开关候选路径：`$CN_INNER_REQUESTID_FILE` → `/www/wwwroot/bapatch/cn_inner_requestid.txt` → `<cn_wire.py 同目录>/cn_inner_requestid.txt`（与项目既有 `cn_*.txt` 开关约定一致） |
| `inner_requestid_enabled()` | `1/on/true` = 开；`0/off/false/no/disabled` = 关；**文件不存在 = 开**（默认开，回滚靠写 0） |
| `inner_requestid_index(keys)` | 官方位置规则：紧跟 `ServerNotification`；无则 `ServerTimeTicks`；无则 `SessionKey`；无则 `Protocol`；再无则最前 |
| `inner_requestid_apply(inner_obj, requestid)` | **有则同步**（`inner['RequestId'] = requestid`，键位置不变）／**无则补**（在规则位置插入，`clear()+update()` 保持同一 dict 对象）／非 dict 或开关关闭则原样返回 |
| `LAST_INNER_REQUESTID` | 诊断用（`action` ∈ `kept/synced/inserted/skip-switch-off/skip-not-a-dict`，`index`，`requestid`）。**并发下是弱一致的，只做观测，不要当状态用** |

**为什么用「覆盖」而不是 `setdefault`**：`setdefault` 保留 inner 里已有的旧值，那么当 inner 与 outer 不一致时（1002 从上游透传就是这种情况）不变量仍然破——而那正是我们要修的 bug 类别。所以 outer 赢：`inner['RequestId'] = requestid`。

---

## §3 改前 / 改后对比（真实渲染，非示意）

### 3.1 90004 `Management_Data`（线上 bridge 里的字面量对象，ast 提取）

改前（354 B，16 键，**无 RequestId**）：

```json
{"Protocol":90004,"ServerTimeTicks":null,"ServerNotification":0,"MissionProgressDBs":[],"EventMissionProgressDBDict":{},"BattlePassMissionProgressDBDict":{},"StaticOpenConditions":{},"Notices":[],"Events":[],"Issues":[],"Banners":[],"GachaProbabilityDisplay":false,"ContentLock":false,"GachaPeriodDisplay":false,"RaidPeriodDisplay":false,"GuidePopup":{}}
```

改后（405 B，17 键，`RequestId` 在 index 3，紧跟 `ServerNotification`）：

```json
{"Protocol":90004,"ServerTimeTicks":null,"ServerNotification":0,"RequestId":"a1b2c3d4-e5f6-4a7b-8c9d-0a1b2c3d4e5f","MissionProgressDBs":[],"EventMissionProgressDBDict":{},"BattlePassMissionProgressDBDict":{},"StaticOpenConditions":{},"Notices":[],"Events":[],"Issues":[],"Banners":[],"GachaProbabilityDisplay":false,"ContentLock":false,"GachaPeriodDisplay":false,"RaidPeriodDisplay":false,"GuidePopup":{}}
```

解开后的外层（注意 `packet` 是被转义的字符串，`requestid` 与包体里的值**逐字符相同**）：

```json
{"protocol":"Management_Data","packet":"{\"Protocol\":90004,\"ServerTimeTicks\":null,\"ServerNotification\":0,\"RequestId\":\"a1b2c3d4-e5f6-4a7b-8c9d-0a1b2c3d4e5f\", … ,\"GuidePopup\":{}}","requestid":"a1b2c3d4-e5f6-4a7b-8c9d-0a1b2c3d4e5f"}
```

> `ServerTimeTicks:null` 是验证工具造成的：`ast` 拿不到运行期表达式 `_t9`，用 `None` 顶替（真值是 18 位整数）。因此 §4 里 90004/24000 的**绝对字节数比线上少 14 B**，但 **`+51` 的增量完全不受影响**（插入的是固定 51 字节）。

### 3.2 1001 `Account_Nickname`（最小形态，2 键）

```text
改前  {"Protocol":1001,"AccountDB":{"ServerId":2,"Nickname":"111"}}
改后  {"Protocol":1001,"RequestId":"a1b2c3d4-…-0a1b2c3d4e5f","AccountDB":{"ServerId":2,"Nickname":"111"}}
```

### 3.3 为什么增量恒为 +51

插入的成员序列化后是 `"RequestId":"<36 字符 uuid>"`：

```text
11  ("RequestId" 含两个引号)  +  1  (:)  +  38  ("…" 含两个引号)  =  50 字节
+ 1  (与前后元素之间的分隔逗号)                                  =  51 字节
```

所以 inner JSON 恒 `+51`。往上一层：`packet` 是 inner 的**转义副本**，新片段里的 4 个 `"` 各自变成 `\"`，于是外层明文 `plain` 长 `+55`。再往外是 AES/pkcs7/base64，增量取决于是否跨过 16 字节分块边界，实测落在 `+64` 或 `+84` 个 base64 字符上：

| 协议 | inner | plain（外层明文） | wire（base64 体） |
|---|---|---|---|
| 90004 | 354 → 405（**+51**） | 479 → 534（**+55**） | 684 → 768（**+84**） |
| 24000 | 3488 → 3539（**+51**） | — | 5632 → 5696（**+64**） |
| 1017 | 216 → 267（**+51**） | — | 492 → 576（**+84**） |

90004 的 30 → 34 个密文块即 `+4×16=64` 字节，加 32 字节 key 后 `base64(480+32)=684` → `base64(544+32)=768`。

---

## §4 对全部已知协议的验证（六个 gate 各渲一次）

命令：`python work\ba\server\deploy\patch_requestid.py --verify --target <临时副本>`
链路：`wrap_response` → `build_plaintext` → pkcs7 → **AES-256-CBC(IV=JOSYdf8ys97uhFYS)** → `base64(ct‖key)` → `unwrap_response` 原路解回（本机无 `cryptography`，走脚本内嵌的纯 Python AES，跑 FIPS-197 三组 + NIST SP800-38A CBC 向量自检后才允许验证）。

| 协议 | protocol name | 键数 前→后 | inner 字节 前→后 | 增量 | RequestId 位置 | outer==inner | 用的构造器 |
|---|---|---|---|---|---|---|---|
| 1002 | `Account_Auth` | 32 → **33** | 1317 → 1368 | +51 | index **29** | **OK** | `cn_inner27.build(1002)`（真文件，来自 `_baseline`） |
| 1001 | `Account_Nickname` | 2 → **3** | 441 → 492 | +51 | index **1** | **OK** | `cn_nick.build_nickname_response`（真文件） |
| 1010 | `Account_CallName` | 2 → **3** | 441 → 492 | +51 | index **1** | **OK** | `cn_nick.build_callname_response`（真文件） |
| 24000 | `Academy_GetInfo` | 9 → **10** | 3488 → 3539 | +51 | index **3** | **OK** | 线上 bridge 的 `obj` 字面量（ast 提取） |
| 90004 | `Management_Data` | 16 → **17** | 354 → 405 | +51 | index **3** | **OK** | 同上 |
| 1017 | `Account_LoginSync` | 9 → **10** | 216 → 267 | +51 | index **3** | **OK** | 同上 |

连线字符数（base64 体）：1002 `2112→2200`、1001/1010 `856→920`、24000 `5632→5696`、90004 `684→768`、1017 `492→576`。

1002 的 index 29 需要单独解释：`cn_inner27` 把 `ServerNotification/ServerTimeTicks/SessionKey` 放在**末尾**（`RESTORE` 列表，L126-127），所以规则算出的插入点是 29（`ServerNotification` 的位置 28 + 1）。这不影响正确性——**位置规则是相对的，不是硬编码 index 4**。也正是因为不写死 4，同一个函数才能同时正确服务「官方 1002 形态（index 3）」和「官方其它协议形态（index 4）」。

### 4.1 六个 gate 之外的强力验证：官方 109 条形状重放

做法：把每一条官方 inner **剥掉 `RequestId`**，再喂给打好补丁的 `build_plaintext` 渲染，断言

1. `outer.requestid == inner.RequestId == 注入的固定 rid`
2. `list(inner.keys()) == list(官方 inner.keys())`（**键序逐项相同**）

```text
-- [3] official shape replay: strip RequestId from every capture, re-render --
   captures: report\_tmp\official_decoded_201 (109 files)
   rendered              : 109/109
   outer.requestid==inner: 109/109
   key order == official : 109/109  (position of RequestId reproduced exactly)
```

这一条同时证明了三件事：补丁在**全部 38 个协议、109 条真实形状**上都能落位；落位后键序与官方**完全一致**（不是"差不多"）；`packet` 的转义/序列化没有被破坏（否则 `json.loads` 之后键序或值会变）。

---

## §5 对已过 gate 的影响评估：1002 的结构对比

### 5.1 官方 1002 的 RequestId 位置（核对结论）

任务里问「位置在 `Protocol` 之后 `SessionKey` 之前？」——**是，但要更精确**。`report\_tmp\official_decoded_201\00_1002_api_account_auth.response.json` 的 inner 前 5 键：

```json
{"Protocol":1002,"ServerTimeTicks":639304002545706815,"ServerNotification":0,
 "RequestId":"f24daa29-45e0-4ecb-99bc-6d0ed3bd7c4e",
 "SessionKey":{"AccountServerId":10015354380,"MxToken":"Vji5A/…"}}
```

- `RequestId` 在 **index 3**：`Protocol`(0) `ServerTimeTicks`(1) `ServerNotification`(2) **`RequestId`(3)** `SessionKey`(4)。
- 官方 **108/109** 是另一种：`Protocol, SessionKey, ServerTimeTicks, ServerNotification, RequestId`（index 4）。
- **1002 是唯一例外**，原因很自然：1002 的响应**本身就是发 SessionKey 的那一条**，所以 `SessionKey` 排在 `RequestId` 之后。
- 与既有文档一致：`work\ba\proto\_sub\_patch3.py` / `work\ba\proto\_sub\gen_matrix.py` 早已记录 `account_auth_1002_exception`。

⇒ 任何"写死 index 4"的实现都会在 1002 上把 `RequestId` 挤到 `SessionKey` 之后（或覆盖错键）；本补丁的锚点规则自然得出 3，实测重放 109/109 键序全对。

### 5.2 我们的 1002（`cn_inner27` 形态）vs 官方

| 项 | 官方 | 我们（改前） | 我们（改后） |
|---|---|---|---|
| 键数 | 32 | 32 | **33** |
| 有 `RequestId` | 有（index 3） | **无** | 有（index 29） |
| `SessionKey` 位置 | index 4 | index 30 | index 30 |
| 只我们有的键 | — | `Desc`、`StaticOpenConditions` | 同（未变） |
| 只官方有的键 | — | `RequestId`、`OpenConditions` | **`OpenConditions`** |

即：补完 `RequestId` 之后，差集从 `{+Desc, +StaticOpenConditions, −RequestId, −OpenConditions}` 收敛为 `{+Desc, +StaticOpenConditions, −OpenConditions}`。后三项与本补丁无关（`StaticOpenConditions` 正是 `report\102` §3.5 指出的"自造伪字段"；`OpenConditions` 是官方对应物，值为 `null`），需要独立单据处理。

> 注意：以上是 `a_proto_int` / `b_proto_str` 等模式的 1002 形态（`cn_inner27`）。**若线上 1002 走的是网关照传**（`_cn_envelope`→`_cn_enc_b64`→`wrap_response`，见 §1.1），则 `obj` 就是官方 32 键原样，补丁走**同步分支**：键数 32→32、字节数不变、`RequestId` 停在 index 3。两种情形都不变量成立，这正是「有则同步 / 无则补」要同时具备的原因。

### 5.3 24000 / 90004 / 1017 / 1001 / 1010 的剩余缺口（不在本补丁范围）

`report\102` §3 列了 24000 的 6 处结构错误，本补丁**只解决第 1 条（`RequestId`）**：

| # | 问题 | 官方 24000 | 我们（补后） | 本补丁 |
|---|---|---|---|---|
| 1 | `RequestId` | 有（index 4） | **有（index 3）** | ✅ 已修 |
| 2 | `SessionKey` | 有（index 1） | **缺** | ❌ 未动 |
| 3 | `AcademyDB.AccountId` | 有 | 缺 | ❌ 未动 |
| 4 | `AcademyDB.ZoneVisitCharacterDBs` | map 71 键 | `[]`（list，类型都不对） | ❌ 未动 |
| 5 | `AcademyLocationDBs` | 9 条 | `[]` | ❌ 未动 |
| 6 | 多发键 | 无 | `MissionProgressDBs` / `EventMissionProgressDBDict` / `BattlePassMissionProgressDBDict` / `StaticOpenConditions` | ❌ 未动 |

E 线的结论是「24000 只需让客户端认为这一条完成了 + 取出 `RequestId`」（1017 请求体里没有任何值来自 24000），所以**预期本补丁单独就能解锁 1017**；但若 1017 仍不来，下一步按 `report\102` §3.2-3.5 补 24000 的 2~6（那是另一个补丁，不要在 `cn_wire` 里做）。

---

## §6 顺序问题：JSON 键序要不要跟官方一致

**结论：功能上不需要，工程上需要按官方位置插入。**

1. **功能上**：客户端是 JSON 解析器，按字段名取值；1002 这个 gate 在「我们的键序与官方完全不同」的情况下已经过了（`cn_inner27` 的 `ServerNotification` 在 index 28，官方在 index 2），这本身就证明键序不是判定条件。
2. **工程上**：位置一致才能做三件事——(a) 与官方抓包逐字节 diff 时不被无关差异淹没；(b) 密文长度/分块与官方同量级，排障时 `enc_body_len` 可直接比；(c) 万一某个下游按序取值（例如某些 C# 的 `Utf8JsonReader` 手写 reader），位置对了就不会踩。
3. **本补丁的做法**：不写死 index，而是用**相对锚点**（紧跟最后一个存在的基础信封字段），因此在「官方形态」上必然复现官方位置（109/109 实测），在「我们自己的残缺形态」上给出该形态下的合理位置（1001/1010 → 1，24000/90004/1017 → 3，`cn_inner27` 的 1002 → 29）。
4. 如果将来要求「我们的 24000 与官方键序完全一致」，那是把 `SessionKey` 等字段补上之后的自然结果（补 `SessionKey` 后 `RequestId` 会自动落到 index 4），**不需要再改这个补丁**——这正是锚点规则的价值。

---

## §7 官方每个协议里 `RequestId` 的位置（全表）

脚本：`python work\ba\server\deploy\scan_requestid_positions.py`（只读，109 个 `*response.json`）

### 7.1 全局直方图

```text
response files parsed     : 109 / 109
carry inner RequestId     : 109
MISSING inner RequestId   : 0
outer.requestid == inner  : 109 / 109
outer != inner            : 0

index 3  (1-based 4) :   1 files      <- 只有 Account_Auth(1002)
index 4  (1-based 5) : 108 files
```

### 7.2 逐协议（38 个协议名 / 109 条响应）

| protocol | 条数 | RequestId index | inner 键数 | RequestId 之前的前缀 |
|---|---:|---:|---:|---|
| `Event_RewardIncrease` | 21 | 4 | 6 | Protocol, SessionKey, ServerTimeTicks, ServerNotification |
| `Management_Data` | 10 | 4 | 6 | 同上 |
| `Notification_EventContentReddotCheck` | 10 | 4 | 7 | 同上 |
| `Mail_Check` | 9 | 4 | 6 | 同上 |
| `Clan_Check` | 8 | 4 | 5 | 同上 |
| `Friend_Check` | 8 | 4 | 5 | 同上 |
| `Echelon_List` | 4 | 4 | 6 | 同上 |
| `Billing_PurchaseListByYostar` | 3 | 4 | 8 | 同上 |
| `Mission_List` | 3 | 4 | 10 | 同上 |
| `Academy_GetInfo` | 2 | 4 | 7 | 同上 |
| `Arena_EnterLobby` | 2 | 4 | 10 | 同上 |
| `Clan_Chat_Records` | 2 | 4 | 6 | 同上 |
| `Echelon_Save` | 2 | 4 | 6 | 同上 |
| **`Account_Auth`** | **1** | **3** | **32** | **Protocol, ServerTimeTicks, ServerNotification** |
| `Account_GetTutorial` | 1 | 4 | 6 | Protocol, SessionKey, ServerTimeTicks, ServerNotification |
| `Account_LoginSync` | 1 | 4 | 35 | 同上 |
| `Arena_CumulativeTimeReward` | 1 | 4 | 8 | 同上 |
| `Arena_DailyReward` | 1 | 4 | 7 | 同上 |
| `Arena_EnterBattle` | 1 | 4 | 14 | 同上 |
| `Arena_SyncEchelonSettingTime` | 1 | 4 | 6 | 同上 |
| `Cafe_Ack` | 1 | 4 | 6 | 同上 |
| `Cafe_ReceiveCurrency` | 1 | 4 | 7 | 同上 |
| `Campaign_EnterMainStageStrategySkip` | 1 | 4 | 6 | 同上 |
| `Campaign_List` | 1 | 4 | 8 | 同上 |
| `Campaign_MainStageStrategySkipResult` | 1 | 4 | 12 | 同上 |
| `Clan_Lobby` | 1 | 4 | 9 | 同上 |
| `ContentSave_Get` | 1 | 4 | 8 | 同上 |
| `EventContent_PermanentList` | 1 | 4 | 6 | 同上 |
| `Item_List` | 1 | 4 | 7 | 同上 |
| `Mail_List` | 1 | 4 | 7 | 同上 |
| `Mail_ListSemiPermanent` | 1 | 4 | 5 | 同上 |
| `MiniGame_MissionList` | 1 | 4 | 8 | 同上 |
| `Mission_GuideMissionSeasonList` | 1 | 4 | 7 | 同上 |
| `Mission_MultipleReward` | 1 | 4 | 8 | 同上 |
| `NetworkTime_Sync` | 1 | 4 | 7 | 同上 |
| `OpenCondition_EventList` | 1 | 4 | 6 | 同上 |
| `Shop_List` | 1 | 4 | 7 | 同上 |
| `Toast_List` | 1 | 4 | 6 | 同上 |
| **合计** | **109** | 1×index3 + 108×index4 | — | — |

### 7.3 规则的可证伪性检验

把每条官方内层剥掉 `RequestId`，用规则「紧跟 `ServerNotification`（缺则 `ServerTimeTicks` → `SessionKey` → `Protocol`）之后插入」重建：

```text
files: 109   rule mismatches: 0
```

即该规则在官方全量数据上**零误差**。补丁里的 `INNER_REQUESTID_ANCHORS = ('ServerNotification','ServerTimeTicks','SessionKey','Protocol')` 就是这条规则。

---

## §8 部署 / 回滚 / 验收（全部本机实跑）

### 8.1 验收三连（任务要求）

```bash
# 1) 改前：dry-run（本机没有线上文件时自动回退到 _baseline\cn_wire.py 预览，只读）
python work\ba\server\deploy\patch_requestid.py --dry-run

# 2) 应用到临时副本
cp -a work\ba\server\deploy\_baseline\cn_wire.py \
      work\ba\server\deploy\_baseline\cn_inner27.py \
      work\ba\server\deploy\_baseline\cn_nick.py   <临时副本目录>/
python work\ba\server\deploy\patch_requestid.py --target <临时副本目录> --apply

# 3) 验证 outer == inner
python work\ba\server\deploy\patch_requestid.py --target <临时副本目录> --verify
```

本机实际输出（关键行）：

```text
# --dry-run（无 target，回退基线预览）
NOTE: target absent (/www/wwwroot/bapatch/tools/cn_wire.py)
      previewing against the read-only baseline copy instead: …\_baseline\cn_wire.py
state    : pristine
   * inserted 81-line helper block above build_plaintext (line 52)
   * statement inserted after line 135: `requestid = requestid or str(uuid.uuid4())`
-- dry-run: 82 line(s) added, 0 removed, 0 modified --

# --apply
state    : pristine
backup   : …\live_copy_requestid\cn_wire.py.bak.<TS>  (sha256 verified)
applied  : …\live_copy\cn_wire.py
sha256   : 3a5cb4be537c866e95b4f01d61bc032efeda9809d23288043ed2d1f0c661269a
        -> f2dc6ce1e29cf7b5128a6a4ccdf5f923038ecc5e2a73b77ac17b0c19ed5c1441

# --apply 再来一次（幂等）
state    : PATCHED (v1)
already patched -- nothing to do (idempotent).

# --verify
state         : PATCHED (BA_PATCH_REQUESTID v1)
aes provider  : pure-aes-shim
1002 Account_Auth 32->33 1317->1368 +51 OK | 1001 2->3 +51 OK | 1010 2->3 +51 OK
24000 9->10 3488->3539 +51 OK | 90004 16->17 354->405 +51 OK | 1017 9->10 216->267 +51 OK
rendered 109/109 · outer.requestid==inner 109/109 · key order == official 109/109
[4] sync branch PASS   [5] kill switch PASS   [6] non-dict PASS
RESULT: PASS
```

`--verify` 的 6 段检查：

| 段 | 断言 |
|---|---|
| [2] | 六个 gate 各渲一次：`outer.requestid == inner.RequestId`、键集合无损、AES/pkcs7/base64 往返一致、插入必有 +51 |
| [3] | 109 条官方形状重放：值相等 + **键序逐项等于官方** |
| [4] | inner 已带**不同** `RequestId` 时：被同步成 outer 值、不重复、键序不变（1002 网关照传场景） |
| [5] | 开关 `0` → inner 无 `RequestId`；`1` → 有且相等；**文件不存在 → 默认开**（走真文件，不是 mock） |
| [6] | `inner_obj` 为 `list/str/int/None` 时不崩、不插入（裸 payload 安全） |

对**未打补丁**的文件跑 `--verify`（这就是"改前"的样子，退出码 1）：

```text
state         : PRISTINE (no patch)
1002 32->32 +0 MISMATCH | 1001 2->2 +0 MISMATCH | 1010 2->2 +0 MISMATCH
24000 9->9 +0 MISMATCH | 90004 16->16 +0 MISMATCH | 1017 9->9 +0 MISMATCH
rendered 109/109 · outer.requestid==inner 0/109 · key order == official 0/109
RESULT: FAIL -- target is PRISTINE (patch not applied).
```

### 8.2 部署（在服务器上执行，本机未连）

```bash
# 0) 备份（补丁自己也会备份，这里再保一层）
cp -a /www/wwwroot/bapatch/tools/cn_wire.py \
      /www/wwwroot/bapatch/tools/cn_wire.py.manual.$(date +%Y%m%d_%H%M%S)

# 1) 把 patch_requestid.py 传到 /www/wwwroot/bapatch/
scp work/ba/server/deploy/patch_requestid.py root@HOST:/www/wwwroot/bapatch/

# 2) 预览（不写任何东西）
ssh root@HOST 'cd /www/wwwroot/bapatch && python3 patch_requestid.py --dry-run'

# 3) 应用
ssh root@HOST 'cd /www/wwwroot/bapatch && python3 patch_requestid.py --apply'

# 4) 验证（线上有 cryptography，走真库；首行会打印 aes provider: cryptography）
ssh root@HOST 'cd /www/wwwroot/bapatch && \
  python3 patch_requestid.py --verify --target /www/wwwroot/bapatch/tools/'
#    有官方抓包目录时再加 --captures <dir> 可多做 109 条重放；没有就只跑六 gate + 开关

# 5) 重启 bridge（python 已 import 的模块不会热加载，必须重启进程）
pkill -f account_auth_probe.py && sleep 1 \
  && cd /www/wwwroot/bapatch/tools \
  && nohup python3 account_auth_probe.py > /www/wwwroot/bapatch/logs/api_probe.out 2>&1 &

# 6) 现场确认（看 rec 里的 enc_requestid 与 last_direct_envelope_plain.txt）
grep -o '"requestid":"[^"]*"' /www/wwwroot/_ba_state/last_direct_envelope_plain.txt
grep -o '"RequestId":"[^"]*"' /www/wwwroot/_ba_state/last_direct_envelope_plain.txt
# 两条必须一模一样
```

### 8.3 回滚（两条命令，任选其一）

```bash
# ① 一行秒回滚：只关开关，代码不动（无需重启进程，每次 build_plaintext 都重新读文件）
echo 0 > /www/wwwroot/bapatch/cn_inner_requestid.txt
# 恢复：echo 1 > /www/wwwroot/bapatch/cn_inner_requestid.txt   （或直接 rm，默认开）

# ② 彻底回滚：恢复备份（需重启 bridge）
ssh root@HOST 'cd /www/wwwroot/bapatch && python3 patch_requestid.py --rollback'
#   -> 打印 rollback/preserved/restored/sha256，恢复到 .bak.<TS>，并保留回滚前的文件
```

本机实测：

```text
rollback : …\cn_wire.py.bak.20261116_052254
preserved: …\cn_wire.py.pre_rollback.20261116_052432
restored : …\cn_wire.py
sha256   : 3a5cb4be537c866e95b4f01d61bc032efeda9809d23288043ed2d1f0c661269a   ← 与基线逐字节相同
state    : pristine
# 再跑一次 --rollback：仍是同样的 clean 备份，幂等，不报错
```

连备份都没有时的兜底（`--rollback --force`）也是**逐字节可逆**：它精确删掉"81 行辅助块 + 1 行调用 + 辅助块自带的 2 个空行"，实测回滚后 sha256 同样回到 `3a5cb4be…`；随后再 `--apply` 又得到 `f2dc6ce1…`（同一个补丁指纹，幂等可重复）：

```text
applied  : …\bare2\cn_wire.py          (3a5cb4be… -> f2dc6ce1…)
no backup found; --force: reverting the patch by text edit
sha256   : 3a5cb4be537c866e95b4f01d61bc032efeda9809d23288043ed2d1f0c661269a   ← 回到基线
--- 再 --apply ---
sha256   : 3a5cb4be537c866e95b4f01d61bc032efeda9809d23288043ed2d1f0c661269a -> f2dc6ce1e29cf7b5128a6a4ccdf5f923038ecc5e2a73b77ac17b0c19ed5c1441
```

回滚后 `sha256` 必须等于基线 `3a5cb4be537c866e95b4f01d61bc032efeda9809d23288043ed2d1f0c661269a`（本机已验证两条路径）。

---

## §9 风险 / 已知未覆盖（诚实清单）

| # | 事项 | 说明与处置 |
|---|---|---|
| 1 | **`cn_cipher` 旧分支不覆盖** | `_cn_envelope`（L679）在 `cn_wrap_mode()` **不在** `enc_b64` 家族时走自己的 `payload_text = json.dumps(inner_obj)`（L690）分支，那根本不调 `cn_wire`，本补丁碰不到。**部署前后请核一次**：`cat /www/wwwroot/bapatch/cn_wrap_mode.txt /www/wwwroot/bapatch/cn_resp_format.txt`；四 gate 已过说明线上 1002 实际走的是 `cn_wire` 家族，但仍值得确认。 |
| 2 | **`e3_bare_dto`（`wrap_raw`）不覆盖** | 该模式没有 outer 信封，无从同步。线上未启用。 |
| 3 | **`enc_inner_keys` 日志 +1** | `rec['enc_inner_keys'] = len(obj)` 在 `wrap_response` 之后取，写的是补后的键数。基线日志里 24000 是 9，补后是 10。**不是 bug，但对比旧日志时要记得**。 |
| 4 | `LAST_INNER_REQUESTID` 并发弱一致 | 仅诊断用；bridge 是 `ThreadingTCPServer`，多线程下可能互相覆盖。**不要**用它做业务判断。 |
| 5 | 24000 的另外 5 处结构缺口 | 见 §5.3。本补丁只补 `RequestId`。 |
| 6 | 1002 的 `Desc` / `StaticOpenConditions` / `OpenConditions` | 见 §5.2，与本补丁无关。 |
| 7 | 开关文件读失败 | `inner_requestid_enabled()` 读不到文件 = 开。若担心被误删导致重复开启，写 `1` 固定住即可。 |
| 8 | 本机 `--verify` 的 AES | 本机无 `cryptography`，用的是脚本内嵌纯 Python AES-256-CBC（FIPS-197 ×3 + SP800-38A CBC 向量自检）。服务器上会自动优先用真 `cryptography`（`--verify` 首行会打印 `aes provider`）。**IV / 填充 / base64 布局与 `cn_wire` 完全一致的实现**，密文与真库同值（同 key/IV/明文下 AES-256-CBC 唯一）。 |
| 9 | `--verify` 里 90004/24000 的 `ServerTimeTicks: null` | `ast` 取不到运行期表达式，绝对字节数比线上少 ~14 B；`+51` 增量不受影响。 |
| 10 | 没有在真机上跑过 | 纪律要求「不连服务器」，所以全部验证都在本机副本 + 官方抓包形状上完成。上线时按 §8.2 第 4/6 步做一次现场确认（`last_direct_envelope_plain.txt` 里两个 requestid 相同即成功）。 |
| 11 | `--verify` 的 24000 用例可能回退 | 若线上 24000 分支已被 `scripts\292_24000_official.py` 改成 `_academy_24000_build(...)` **调用**（不再是字面量 dict），`ast` 提取不到对象 → 该用例自动回退成「官方抓包形态」或「最小副本」，`case` 列会标 `official-shape@captures` / `replica-min`。**断言仍然有效**（不变量与负载无关），但那次运行的 24000 pre/post 字节数不是线上真值。想强制用真值就加 `--bridge-src /www/wwwroot/bapatch/tools/account_auth_probe.py`（默认已包含这个候选路径）。 |

---

## §10 复现清单

| 文件 | 作用 |
|---|---|
| `work\ba\server\deploy\patch_requestid.py` | 补丁 + 验证器 + 回滚器（`--apply/--verify/--rollback/--dry-run/--write-switch/--switch/--selftest-aes/--json-out`） |
| `work\ba\server\deploy\scan_requestid_positions.py` | 扫 `official_decoded_201\*response.json`，输出 §7 的全表（`--json` 可机读） |
| `work\ba\server\deploy\TEST_REQUESTID.md` | 本文 |
| `work\ba\server\deploy\_scratch\bridge_sim.py` | bridge 级联调模拟（`_cn_send_envelope` / 网关照传 / 开关三种调用形态，本机 ALL PASS） |

```bash
# 全量复核（三条，全部只读或只写临时副本）
python work\ba\server\deploy\scan_requestid_positions.py
python work\ba\server\deploy\patch_requestid.py --dry-run
python work\ba\server\deploy\patch_requestid.py --selftest-aes
```

### bridge 级联调结果（`_scratch\bridge_sim.py`）

```text
== A) _cn_send_envelope pattern (1001/1010/24000/90004/1017) ==
  24000  keys 6->7  outer==inner=True  ctype=text/plain; charset=utf-8  PASS
  90004  keys 6->7  outer==inner=True  PASS
  1001   keys 2->3  outer==inner=True  PASS
== B) upstream-passthrough pattern (1002 via post_gateway) ==
  upstream RequestId : f24daa29-45e0-4ecb-99bc-6d0ed3bd7c4e
  outer requestid    : 8dd5e4ba-be48-41c1-95b1-189cb6388a1b
  inner RequestId    : 8dd5e4ba-be48-41c1-95b1-189cb6388a1b  (synced, index 3, order kept True)
== C) kill switch flips the wire without touching code ==
  switch=0 -> inner keys ['Protocol']
  switch=1 -> inner keys ['Protocol', 'RequestId']
BRIDGE-LEVEL: ALL PASS
```

---

## §11 顺手得到的一个因果闭环（供主线参考）

只用「已证实的事实 + 已观察到的行为」，不需要新证据就能锁死"客户端读的是内层"：

1. **观察到**：1002 之后客户端**会**发 24000；24000 之后**不发** 1017。
2. **已证实**：1002 的回包是 AES 信封，且其 inner 对象来自上游网关照传（`post_gateway`→`unwrap_gateway_response`→`_cn_envelope`），因此 **1002 的 inner 里本来就有 `RequestId`**（官方形态，index 3）；而 outer 的 `requestid` 是本地 `uuid4()` 新生成的 → 两者**不等**。
3. **已证实**：24000 的 inner 由本地字面量构造，**完全没有** `RequestId`；而它的 outer `requestid` **是有的**（每次新 uuid）。
4. 若客户端读的是 **outer**：24000 的 outer 也非空 → 1017 应该发出来。**但它没发** ⇒ 排除。
5. ⇒ 客户端读的是 **inner**；1002 有（上游给的）所以链条走了一步，24000 没有所以断在那里。

这个推论与本补丁的前提完全吻合，也解释了"为什么 1002/1001/1010/24000 四个 gate 过了、链条还是停在 24000"——**gate 通过 ≠ 信封不变量成立**，1002 是"靠上游偶然带上了"，24000 是"本地生成必然没有"。

---

## §12 一行总结

`cn_wire.build_plaintext` 里加一行 `inner_requestid_apply(inner_obj, requestid)`（有则同步、无则按官方锚点位置插入，锚点规则在官方 109/109 上零误差），一个咽喉点覆盖全部 8 个 `wrap_response` 调用点与全部协议；六个 gate 与 109 条官方形状重放全部 `outer.requestid == inner.RequestId`，键序 109/109 与官方一致，**回滚靠 `echo 0 > cn_inner_requestid.txt` 一行即可**，无需改代码。
