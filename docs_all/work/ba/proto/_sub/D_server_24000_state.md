# D · 我们服务端 `Academy_GetInfo(24000)` 代码路径现状（只读分析）

> 分析者：只读分析 agent ｜ 时间：2026-11-16
> 纪律：**未改任何既有文件**（只在 `work\ba\proto\_sub\` 下新建本文件与 `D_prior_findings.json`）；未连服务器、未连手机、未跑调试器。
> 分析对象：`work\ba\server\*`、`work\ba\proto\*`、`report\*`、`scripts\*`、`report\_tmp\official_decoded_201\*`

---

## 0. 一页结论

| # | 结论 | 硬度 |
|---|---|---|
| **C1** | 线上那条 `{"Protocol":24000}` / 192 B / `gen_kind="min"` 的回包，**不是** `response_factory.py` 或 `protocol_router.py` 产生的，而是**bridge 的 `_generic_protocol_response()` 兜底分支**产生的。 | **[确证]**（`fallback=generic-envelope` + `wrap_mode=direct_envelope` 只由 `_cn_send_envelope()` 写，见 `_bridge_ref/account_auth_probe.py:718-733`） |
| **C2** | 触发条件是**一处名字查表失败**：`name = NAME_TABLE.get(proto_str) or EXTRA_TOKENS.get(proto_str)` → `None` → `unknown_protocol=True` → 兜底。24000 的 token `KKVAEXLS5QIIB36RQW27XRTJGI` **不在** `EXTRA_TOKENS`（只有 5 条）里；只要 `/www/wwwroot/bapatch/tools/protocol_names.txt` 里没有 `Academy_GetInfo`，24000 就必然走兜底。 | **[确证]** |
| **C3** | `response_factory.py` / `protocol_router.py` **根本没接进线上 bridge**，全仓库只有 `example_auth_flow.py` 和 `test_router.py` import 它们。它们是「设计层」，不是「运行层」。 | **[确证]**（见 §1 的 import 扫描） |
| **C4** | 官方 24000 响应是 **17560 B**，内层 **7 个键**：`Protocol, SessionKey, ServerTimeTicks, ServerNotification, RequestId, AcademyDB, AcademyLocationDBs`。我们任何一条现存代码路径都发不出这 7 个键。 | **[确证]**（`report\_tmp\official_decoded_201\01_24000_api_academy_getinfo.response.json`，`meta.resp_bytes=17560`） |
| **C5** | 官方 **109/109 条**响应都带 `SessionKey` **和** `RequestId`，且 `L2.requestid == 内层 RequestId`。`response_factory.py:105-113` 的 `SESSION_KEY_ECHO_PROTOCOLS` 白名单（7 条）与真服事实**相反**。 | **[确证]**（§3.2 计数脚本结果） |
| **C6** | 修好的模板**已经存在**：`work\ba\proto\academy_24000_official.json` + 部署脚本 `scripts\292_24000_official.py`，并在 `report\_tmp\sandbox292\` 做过本地沙箱验证。**是否已部署到真服务器：未找到证据**（仓内无部署日志/无远端回读）。 | **[确证]**存在 / **[未知]**是否已上线 |

**⇒ 给上层的一句话**：不要再找「24000 该长什么样」——形状已经在 `academy_24000_official.json` 里；剩下的问题是「线上跑的那份 `account_auth_probe.py` 里到底有没有这段，以及名字表里有没有 `Academy_GetInfo`」。

---

## 1. 三层结构：谁才是线上那一段

| 层 | 文件 | 是否线上运行 | 依据 |
|---|---|---|---|
| L0 传输 | `work\ba\server\_bridge_ref\cn_wire.py`（`build_plaintext` / `wrap_response`） | ✅ 是 | `_bridge_ref:37 import cn_wire` |
| **L1 网关/bridge** | **`account_auth_probe.py`**（线上 `/www/wwwroot/bapatch/account_auth_probe.py`，46,790 B @15:07） | ✅ **是** | `LOG='/www/wwwroot/bapatch/logs/api_all_requests.log'`（`:42`），日志字段 `gen_kind/wrap_mode/fallback` 全部由它写 |
| L2 设计层 | `response_factory.py` + `protocol_router.py` | ❌ **否** | 全仓 import 扫描只有 `example_auth_flow.py:44,212` 与 `test_router.py` |

import 扫描结果（`work\ba` 下全部 `*.py`）：

```
import response_factory | from response_factory  →  work\ba\server\example_auth_flow.py
                                                   work\ba\server\response_factory.py (自身)
import protocol_router  | from protocol_router   →  work\ba\server\example_auth_flow.py
                                                   work\ba\server\test_router.py
```

同一结论的行内证据：`work\ba\server\example_auth_flow.py:110`

```python
    24000: (None, 'skeleton', u'与账号无关的静态数据，直接骨架'),
```

`FactoryLayer.dto_of()`（`:220-222`）在 DTO 为 `None` 时返回 `None`，`render()`（`:226-227`）随即 `raise KeyError(u'没有协议号 %s 的 DTO 映射' % pid)`，`handle_auth()` 的 except 分支（`:376-377`）就退回：

```python
            packet, dto, errs, notes = ({'Protocol': protocol}, u'?', [u'%s: %s' % (
                type(exc).__name__, exc)], [])
```

——**这也是一个只含 1 个键的 `{"Protocol":24000}`**。也就是说「1 键 24000」在本仓库里至少有 **两条独立成因**；区分方法是看日志字段：bridge 那条会带 `fallback=generic-envelope` / `wrap_mode=direct_envelope` / `gen_kind=min`，`example_auth_flow` 那条不会写任何线上日志（它只是示例程序）。

---

## 2. Q1 · 24000 今天的响应信封是怎么组装的

### 2.1 运行层：`account_auth_probe.py` 的分发（唯一决定线上形态的地方）

`work\ba\server\_bridge_ref\account_auth_probe.py:942-977`（`_bridge()`）：

```python
942:    def _bridge(self, body, rec):
943:        fields = parse_cn_multipart(body)
944:        proto_str = fields.get('protocol', '')
945:        packet_b64 = fields.get('packet', '')
...
957:        rec['protocol_raw'] = proto_str
958:        rec['exp'] = exp
959:        name = NAME_TABLE.get(proto_str) or EXTRA_TOKENS.get(proto_str)
960:        rec['protocol_name'] = name
...
970:        if name is None:
971:            rec['unknown_protocol'] = True
972:            got = self._generic_protocol_response(proto_str, packet_b64, rec)
973:            if got is not None:
974:                return got
975:            code, resp, ctype = self._forward(body)
976:            rec['fallback'] = 'forward-unknown-protocol'
977:            return code, resp, ctype
```

`NAME_TABLE` 的构成（`:105-122`）＝ `BUILTIN_NAMES`（共 **43** 条，`:70-84`，**没有 `Academy_GetInfo`**）＋ 服务器上的 `protocol_names.txt`（`:57`），键是 `b32md5(name)`（`:89-90`）。`EXTRA_TOKENS`（`:96-102`）只有 5 条，**也没有 24000**：

```python
96: EXTRA_TOKENS = {
97:     'AHTQLQI65FWJGGGK4KL5AEF57A': 'Account_Auth',
98:     'GVDSNCHUMIOS44NDTZM6ZPDDVQ': 'Account_Nickname',
99:     'K3SF6XS7VK7JFL7T2M2WFELUSY': 'Account_CallName',
100:    'FZGO2J3INCGSND5AGKDLB7EBSY': 'Account_CheckNexon',
101:    'P3OMQZD2FXV7XXEGA7ETCXIJ4Q': 'Account_LoginSync',
102: }
```

24000 的 token 是可算出来的（本次只读复算，Python `base64.b32encode(md5(name.encode('utf-16-le')).digest()).rstrip('=')`）：

```
Academy_GetInfo        -> KKVAEXLS5QIIB36RQW27XRTJGI     ← 与 protocol_map.json 一致
Academy_AttendSchedule -> OUUT4DK7VK32GDTKX6IKZ5I4GQ
```

⇒ **因为 `b32md5('Academy_GetInfo')` 能算出 `KKVAEXLS5QIIB36RQW27XRTJGI`，所以只要 `protocol_names.txt` 里写了 `Academy_GetInfo`，24000 就会走「已知协议」分支**；反之必然落进 `unknown_protocol`。

### 2.2 兜底分支本身：`_generic_protocol_response()`

`work\ba\server\_bridge_ref\account_auth_probe.py:643-716`（仓库里的版本**已经**有 24000 专用分支）：

```python
643:    def _generic_protocol_response(self, proto_str, packet_b64, rec, name=None):
644:        """Any protocol we do not implement -> decrypt the request, read Hash>>32, answer with a valid envelope."""
645:        frag = self._cn_decode_any(packet_b64, proto_str)
...
649:        num = None
650:        m = re.search(r'"Hash"\s*:\s*(\d+)', frag)
651:        if m:
652:            num = int(m.group(1)) >> 32
653:        rec['gen_protocol'] = num
...
660:        if num is None:
661:            return None
...
685:        if num == 24000:
686:            obj = {"Protocol": 24000, "ServerTimeTicks": 0, "ServerNotification": 0,
687:                   "MissionProgressDBs": [], "EventMissionProgressDBDict": {},
688:                   "BattlePassMissionProgressDBDict": {}, "StaticOpenConditions": [],
689:                   "AcademyDB": {"LastUpdate": "2026-11-14T00:00:00",
690:                                 "ZoneVisitCharacterDBs": [],
691:                                 "ZoneScheduleGroupRecords": {}},
692:                   "AcademyLocationDBs": []}
693:            rec['gen_kind'] = 'academy-24000'
694:            rec['fallback'] = 'generic-envelope'
695:            return self._cn_send_envelope(name or 'Academy_GetInfo', obj, rec)
696:        if num in (1019, 1017):
...
703:        else:
704:            from datetime import datetime as _dt
705:            _now = _dt.now()
706:            _ticks = int((_now - _dt(1, 1, 1)).total_seconds()) * 10_000_000 + _now.microsecond * 10
707:            obj = {"Protocol": num,
708:                   "ServerTimeTicks": _ticks,
709:                   "ServerNotification": 0,
710:                   "MissionProgressDBs": [],
711:                   "EventMissionProgressDBDict": {},
712:                   "BattlePassMissionProgressDBDict": {},
713:                   "StaticOpenConditions": []}
714:            rec['gen_kind'] = 'min+base'
715:        rec['fallback'] = 'generic-envelope'
716:        return self._cn_send_envelope(name or 'Unknown', obj, rec)
```

**注意 `gen_kind` 没有 `'min'` 这个值**（全文件只有 4 处赋值：`682 management-90004` / `693 academy-24000` / `701 loginsync-%d` / `714 min+base`）。而证据里记的是 `gen_kind="min"` + `inner_keys=1`。⇒ **线上跑的那份 bridge 比仓库 `_bridge_ref` 这份更旧**：那一版的 else 分支是

```python
        else:
            obj = {"Protocol": num}          # ← 只有 1 个键
            rec['gen_kind'] = 'min'
```

`inner_keys = len(obj)` 正是 `_cn_send_envelope()` 在 `:725` 写的：

```python
725:        rec['enc_inner_keys'] = len(obj) if isinstance(obj, dict) else 0
```

⇒ `inner_keys=1` 与「obj 只有 `Protocol` 一个键」严格等价。**这条 1 键构造器在本仓库里还留着一份**，见 `_bridge_ref/cn_nick.py:57-59`：

```python
57: def build_min_response(protocol):
58:     """Fallback for protocols we do not implement: same protocol number, valid packet, no 404/empty body."""
59:     return {"Protocol": int(protocol)}
```

（`_bridge()` 的 path D 在 `:1097-1102` 会调它，并把 `fallback` 记成 `min-envelope` —— 与证据里的 `generic-envelope` 不同，所以 05:46 那条**不是** path D，而是 `_generic_protocol_response` 的旧 else 分支。）

### 2.3 最新（已修好形状）的版本：`report\_tmp\sandbox292\account_auth_probe.py`

`report\_tmp\sandbox292\account_auth_probe.py:856-860`：

```python
856:        if num == 24000:
857:            obj = _academy_24000_build(frag, rec)
858:            rec['gen_kind'] = 'academy-24000'
859:            rec['fallback'] = 'generic-envelope'
860:            return _academy_24000_send(name or 'Academy_GetInfo', obj, rec)
```

`_academy_24000_build()` 在 `:456-554`，渲染 `academy_24000_official.json` 模板；`_academy_24000_send()` 在 `:557-576`，把**外层 `requestid` 与内层 `RequestId` 强制同一个值**（`:562-563`）。这是目前唯一与官方形态一致的实现。

### 2.4 设计层：`protocol_router.route()` + `response_factory.build_with_stats()`

`work\ba\server\protocol_router.py:505-528`：

```python
505:        # ---- ⑤ 查 Response DTO ------------------------------------------
506:        dto, note, w = dto_for(name, pid)
...
514:        if not dto:
515:            return _error_spec(pid, name, warn, path=path,
516:                               ticks=ctx.get('server_time_ticks'))
517:        if dto not in _INDEX.dto_set:
518:            warn.append('DTO %s 不在 schema（%s）' % (dto, note))
519:            return _error_spec(pid, name, warn, path=path,
520:                               ticks=ctx.get('server_time_ticks'))
521:
522:        # ---- ⑥ 交给工厂 --------------------------------------------------
523:        fctx = _factory_context(ctx)
524:        payload, stats = _rf.build_with_stats(dto, pid if isinstance(pid, int) else 0, fctx)
525:        if not payload:
526:            warn.append('工厂返回空体: %s' % dto)
527:            return _error_spec(pid, name, warn, path=path,
528:                               ticks=ctx.get('server_time_ticks'))
```

- `protocol_map.json` 里 **有** `Academy_GetInfo → id 24000, resp AcademyGetInfoResponse`。
- `dto_schema.json`（v1，112 类型）里 **没有任何 Academy\* DTO**；`dto_schema_full_v2.json` / `dto_schema_academy.json` 里才有。
- `response_factory.load_schema()` 的优先级是 v2 → full → v1（`response_factory.py:58-61`），所以**用 v2 时不会掉进 517**；用 v1 时会走 `_error_spec()` → 内层是 `{"Protocol": -1, "ErrorCode": 500, "ServerTimeTicks": ...}`（**3 个键**，`:1027-1036`）——**和证据里的 1 键包不是一回事**。⇒ 再次排除设计层。

工厂到达的根键由 `_emit_object()` 决定（`:742-836`）：`Protocol`（`:766-778`）→ BasePacket（`:781-805`，**含 SessionKey 白名单门**）→ ResponsePacket 6 字段（`:808-815`）→ DTO 自有字段（`:818-829`）。24000 走这条路会得到 **9 个键**：

```
Protocol, ServerTimeTicks, ServerNotification, MissionProgressDBs,
EventMissionProgressDBDict, BattlePassMissionProgressDBDict,
StaticOpenConditions, AcademyDB, AcademyLocationDBs
```

### 2.5 三条路径 vs 官方：键集对照

| 键 | 官方（17560 B） | bridge 旧 else（证据里那条，192 B） | bridge `_bridge_ref` 的 24000 分支 | factory v2 | sandbox292 修复版 |
|---|---|---|---|---|---|
| `Protocol` | ✅ 24000 | ✅ | ✅ | ✅ | ✅ |
| **`SessionKey`** | ✅ 回显 | ❌ | ❌ | ❌（白名单外，省略） | ✅ |
| `ServerTimeTicks` | ✅ | ❌ | ✅（写死 0） | ✅ | ✅ 动态 |
| `ServerNotification` | ✅ 0 | ❌ | ✅ 0 | ✅ | ✅ 0 |
| **`RequestId`** | ✅ | ❌ | ❌ | ❌（schema 无此字段） | ✅ |
| `AcademyDB` | ✅ 4 子键 | ❌ | ✅ 3 子键（缺 `AccountId`） | ✅ 3 子键 | ✅ 4 子键 |
| `AcademyLocationDBs` | ✅ 9 条 | ❌ | ✅ 但 `[]` | ✅ 但 `[]` | ✅ 9 条 |
| `MissionProgressDBs` / `EventMissionProgressDBDict` / `BattlePassMissionProgressDBDict` / `StaticOpenConditions` | **❌ 官方没有** | ❌ | ✅（**多出来的 4 键**） | ✅（多出来） | ❌（去掉） |
| 键数 | **7** | **1** | 9 | 9 | **7** |

---

## 3. Q2 · `RequestId` / `SessionKey` / `MxToken`

### 3.1 `RequestId`：不是回显请求，是**每响应新生成的 GUID**，且必须同时出现在内层与外层

硬证据（本次只读复算 + 既有产物）：

- 官方 24000 **请求**里根本没有 `RequestId` 这个字段
  （`work\ba\proto\_sub\_cmp_out.txt`：`REQ has RequestId field? False`；请求原文见 `report\_tmp\official_decoded_201\01_24000_api_academy_getinfo.request.json`）。
- 官方 24000 **响应**里 `RequestId = 3770c1bc-a631-46fb-a9b6-0421ae2601fe`，外层 `requestid` **一模一样**
  （`_sub\_cmp_out.txt`：`L2 requestid == packet RequestId : True`）。
- 109 条官方响应 **109 条**都有 `RequestId`，**109 条**都有 `SessionKey`（§3.2 的统计脚本）。

**我们现在的代码：**

- bridge 生成了 rid，但只塞进外层：`_bridge_ref/account_auth_probe.py:718-724`

```python
718:    def _cn_send_envelope(self, proto_name, obj, rec):
719:        """Encode exactly the object we were given (no cn_wrap_mode re-building)."""
720:        import uuid as _uuid
721:        rid = str(_uuid.uuid4())
722:        wire, plain, key = cn_wire.wrap_response(proto_name, obj, rid)
723:        rec['wrap_mode'] = 'direct_envelope'
724:        rec['enc_requestid'] = rid
```

  外层信封的形态在 `_bridge_ref/cn_wire.py:52-60`：

```python
52: def build_plaintext(protocol_name, inner_obj, requestid=None):
54:     requestid = requestid or str(uuid.uuid4())
55:     plain = json.dumps({
56:         "protocol": protocol_name,
57:         "packet": json.dumps(inner_obj, ensure_ascii=False, separators=(',', ':')),
58:         "requestid": requestid,
59:     }, ensure_ascii=False, separators=(',', ':'))
```

  ⇒ **内层 `obj` 里永远不会有 `RequestId`**，因为没人往 `obj` 里写它。

- **schema 层完全没有这个字段**：`RequestId` 在 `dto_schema.json` / `dto_schema_full.json` / `dto_schema_full_v2.json` / `dto_schema_academy.json` / `shittim_types.json` / `_full\generic_map.json` 里命中数 **0**；只在 `official_spec.json` 里命中 **153** 次（即「真服里有、我们的类型表里没有」）。

- 已修版本：`report\_tmp\sandbox292\account_auth_probe.py:557-563`

```python
557: def _academy_24000_send(proto_name, obj, rec):
558:     """Same envelope as _cn_send_envelope, but outer requestid == inner RequestId
559:     (that is what the official server does)."""
562:     rid = obj.get('RequestId') or str(_uuid.uuid4())
563:     wire, plain, key = cn_wire.wrap_response(proto_name, obj, rid)
```

### 3.2 `SessionKey`：官方是**回显请求里的那一份**（逐字节相同），不是从 DB 重建

- 真服证据（`work\ba\proto\_sub\_cmp_out.txt`）：

```
== MxToken echo ==
REQ  SessionKey = {"AccountServerId":10015354380,"MxToken":"Vji5A/Cy6X2enQZKeYgrjxAC8MoRDOCT2Tb1SW13PcZTq2cnyCPPdd81pGbzYBKA"}
RESP SessionKey = {"AccountServerId":10015354380,"MxToken":"Vji5A/Cy6X2enQZKeYgrjxAC8MoRDOCT2Tb1SW13PcZTq2cnyCPPdd81pGbzYBKA"}
MxToken byte-identical : True
AccountServerId identical: True
MxToken len = 64 charset-alnum+slash+plus
AcademyDB.AccountId == SessionKey.AccountServerId : True
```

- 109 条官方响应 `SessionKey` 覆盖率 = **109/109**（本次统计脚本，见下），键序统一为
  `Protocol, SessionKey, ServerTimeTicks, ServerNotification, RequestId, <own...>`（21 条 `EventRewardIncreaseDBs`、17 条无自有字段、10 条 `Data` 三种前缀占绝大多数）。

```
responses parsed: 109
with SessionKey : 109
with RequestId  : 109
without SessionKey: []
```

**我们现在的代码：**

- 设计层**从 identity/DB 重建**，且受白名单门禁 —— `response_factory.py:579-592`：

```python
579:        # SessionKey：dict / SessionKey 对象 / 从 identity+state 拼
580:        sk = _coerce_dict(c.get('session_key'))
581:        if sk is None:
582:            token = ident.get('mx_token')
583:            if token:
584:                asid = ident.get('account_server_id')
585:                if not _is_int(asid):
586:                    asid = meta.get('serverId') or acct.get('ServerId')
587:                sk = {'AccountServerId': asid if _is_int(asid) else 0, 'MxToken': token}
```

  `response_factory.py:97-113` 的白名单（**与真服事实相反**）：

```python
105: SESSION_KEY_ECHO_PROTOCOLS = frozenset((
106:     1000,    # Account_Create
107:     1002,    # Account_Auth
108:     1009,    # Account_CheckYostar
109:     1012,    # Account_Auth2
110:     1014,    # Account_CheckNexon（国服没有这条，留位）
111:     37000,   # ProofToken_RequestQuestion
112:     37001,   # ProofToken_Submit
113: ))
```

  `response_factory.py:783-795` 的门：

```python
783:        echo_sk = ctx.may_echo_session_key(ctx.root_protocol_id)
784:        for f in bp.get('fields') or []:
785:            nm = f.get('name')
786:            if nm == 'SessionKey':
787:                if echo_sk:
788:                    out['SessionKey'] = copy.deepcopy(ctx.session_key)
789:                    stats.bound_from_account += 1
790:                elif ctx.may_emit_null_session_key(ctx.root_protocol_id):
791:                    out['SessionKey'] = None
792:                elif ctx.session_key is not None:
793:                    # 有会话但这条协议官方不回显 —— 按官方形态**不发这个键**
794:                    stats.warn('%s 不在 SessionKey 回显白名单，已省略（官方形态）'
795:                               % (ctx.root_protocol_id,))
```

  ⇒ 24000 ∉ 白名单 ⇒ **工厂永远不发 `SessionKey`**，`AccountId`（`:803-805`，派生自 SessionKey）也一并不发。

- bridge 的 24000 分支（`_bridge_ref:685-695`）里**根本没有 `SessionKey`**。

- 已修版本 `_academy_24000_build()`（`sandbox292:487-496`）取值优先级是 **请求 > 缓存会话 > 现造 64 字符**：

```python
487:    # ---- MxToken: request > cached session > fresh random 64-char
488:    tok = None
489:    tsrc = 'session'
490:    m = _re.search(r'"MxToken"\s*:\s*"([^"]+)"', flat)
491:    if m:
492:        tok, tsrc = m.group(1), 'request'
...
496:        tok, tsrc = _academy_24000_mx_token(), 'generated'
```

### 3.3 `MxToken` 的产出/校验：设计层格式**与官方不符**

- 官方：**64 字符 base64**（48 字节、无 padding、含 `+` `/`）。
- 我们的 `account_service.py:716-720`：

```python
716:    def issue_session_key(self, account: Account, client_ip: Optional[str] = None,
...
719:        u"""签发会话：uuid4 → 36 字符小写 GUID，对齐客户端 SessionKey.MxToken 形态。"""
720:        token = str(uuid.uuid4()).lower()
```

  校验正则同样是 UUID 形态（`:131`）：

```python
131: MX_TOKEN_RE = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
```

  ⇒ 注释自称「对齐客户端形态」，但**真服是 64 字符 base64，不是 36 字符 GUID**。`resolve_session()`（`:746-770`）大小写不敏感、查 `sessions` 表、校验 `revoked`/`expires_at`，逻辑本身没问题，问题只在**签发格式**。已修版本用的正是 64 字符：`sandbox292:449-453`

```python
449: def _academy_24000_mx_token():
450:     """64-char base64 MxToken (48 random bytes -> exactly 64 chars, no padding)."""
453:     return _b64.b64encode(_os.urandom(48)).decode('ascii')
```

---

## 4. Q3 · `AcademyDB` 在哪生成、子字段与类型

`Academy_GetInfo` **没有专用 handler 文件**；`account_service.py`（1652 行）里 **0 处** 提到 24000/Academy（全部方法名见 `:139-1790`，都是账号/会话/blob 层）。`AcademyDB` 有 **4 个**独立产出点：

### 4.1 运行层（旧）：`_bridge_ref/account_auth_probe.py:689-692`（内联字面量）

```python
689:                   "AcademyDB": {"LastUpdate": "2026-11-14T00:00:00",
690:                                 "ZoneVisitCharacterDBs": [],
691:                                 "ZoneScheduleGroupRecords": {}},
692:                   "AcademyLocationDBs": []}
```

### 4.2 schema 驱动（设计层）：`dto_schema_full_v2.json` 的 `AcademyDB`

```
== AcademyGetInfoResponse  base= ResponsePacket  fieldCount= 2
   AcademyDB                  kind=object   type=AcademyDB
   AcademyLocationDBs         kind=list     type=List<AcademyLocationDB>
== AcademyDB  base= None  fieldCount= 3
   LastUpdate                 kind=datetime type=DateTime
   ZoneVisitCharacterDBs      kind=unknown  type=unknown          ← 唯一没解出类型的字段（report/70 §4）
   ZoneScheduleGroupRecords   kind=dict     type=Dictionary<long,List<long>>
== AcademyLocationDB  base= None  fieldCount= 3
   LocationId                 kind=scalar   type=long
   Rank                       kind=scalar   type=long
   Exp                        kind=scalar   type=long
```

`ZoneVisitCharacterDBs` 是 `unknown` ⇒ 落到 `response_factory.unknown_default()`（`:384-398`）：

```python
394:    if any(name.endswith(s) for s in DICTISH_SUFFIX):
395:        return {}
396:    if name.endswith('s') or any(name.endswith(s) for s in LISTISH_SUFFIX):
397:        return []
```

字段名以 `s` 结尾 ⇒ **返回 `[]`（list）**。**这就是类型错的代码来源。**

### 4.3 生成器自检把「错的类型」写成了断言：`gen_academy.py:302-306`

```python
302:            ('AcademyDB 含 LastUpdate/ZoneVisitCharacterDBs/ZoneScheduleGroupRecords',
303:             set(body['AcademyDB']) == {'LastUpdate', 'ZoneVisitCharacterDBs', 'ZoneScheduleGroupRecords'}),
304:             ('LastUpdate 是字符串', isinstance(body['AcademyDB'].get('LastUpdate'), str)),
305:             ('ZoneVisitCharacterDBs 是 list', isinstance(body['AcademyDB'].get('ZoneVisitCharacterDBs'), list)),
306:             ('ZoneScheduleGroupRecords 是 dict', isinstance(body['AcademyDB'].get('ZoneScheduleGroupRecords'), dict)),
```

⇒ `python gen_academy.py --check` 会 **PASS**，而它 PASS 的正是错形状；同时第 303 行断言「`AcademyDB` 键集 == 3 个」⇒ **`AccountId` 被制度性地排除在外**。

### 4.4 官方真形状（`report\_tmp\official_decoded_201\01_24000_api_academy_getinfo.response.json` → 内层）

```
Protocol: int = 24000
SessionKey: dict(2)
  AccountServerId: int = 10015354380
  MxToken: str = 'Vji5A/...'                       (64 字符)
ServerTimeTicks: int = 639304002548158993
ServerNotification: int = 0
RequestId: str = '3770c1bc-a631-46fb-a9b6-0421ae2601fe'
AcademyDB: dict(4)
  AccountId: int = 10015354380                     ← 我们 schema 里没有
  LastUpdate: str = '2026-11-16T04:00:06.479'      ← 带毫秒；我们是 '2026-11-14T00:00:00'
  ZoneVisitCharacterDBs: dict(71)                  ← 是 MAP，不是 list
     "1":  list(0)
     "10": list(3)  [{UniqueId:int, ServerId:int, LastInteractTime:str}, ...]
     ...共 71 个键（1,10,11,110,...,97），值的元素固定 3 键
  ZoneScheduleGroupRecords: dict(0)                ← {}，与官方一致（空）
AcademyLocationDBs: list(9)
  [{AccountId:int, LocationId:int, Rank:int, Exp:int}, ...]   ← 每项 4 键，我们 schema 只有 3 个
```

补充旁证（同一份真服里另一条协议的同类形状）：`work\ba\server\prototype\_scratch\_1017_schema.txt:20-30` 显示 `CafeVisitCharacterDBs` 也是 `map`，`key_kind=int_str`，值同样是 `{UniqueId:int, ServerId:int, LastInteractTime:str}`。⇒ **`ZoneVisitCharacterDBs` 的正确类型可以独立推出：`Dictionary<int-as-string, List<{UniqueId, ServerId, LastInteractTime}>>`**。

### 4.5 已经做好的正确产出点（推荐作为唯一事实源）

- 模板：`work\ba\proto\academy_24000_official.json`（16,808 B，71 个 `ZoneVisitCharacterDBs` 键 + 9 条 `AcademyLocationDBs`，4 个占位符 `__SESSION_KEY__ / __TICKS__ / __REQUEST_ID__ / __ACCOUNT_ID__`）
- 生成器：`scripts\291_gen_academy_24000_template.py`（从官方抓包重生成模板）
- 渲染器：`report\_tmp\sandbox292\account_auth_probe.py:456-554`（`_academy_24000_build`）
- 部署器：`scripts\292_24000_official.py`（插 managed block + 替换 `if num == 24000:` 分支，带 `--verify / --rollback / --dry-run`）

---

## 5. Q4 · 代码/文档里有没有「gate」这个机制

**没有「必须先过 1002/1001/1010 才允许其它协议」这类服务端门禁。** 逐处核查：

| 检查点 | 结果 |
|---|---|
| `protocol_router.route()`（`:444-542`） | **零**会话前置条件：只做 id/name/path 解析 → DTO 查表 → 工厂。没有「未认证则拒绝」。 |
| `response_factory._Ctx` | 只是取值器，不做准入。 |
| `account_service` | 只有 `AuthRejected`（`:139`，抛点 `:523`、`:674`）与 `resolve_session() → None`（`:746-770`）。**没有任何协议白名单/阶段机**。 |
| bridge `_bridge()` | 只有 `want_force_reauth()`（`:357`）/ `ensure_session()`（`:409`）影响 **上游 gateway** 调用，不影响「客户端能不能请求 24000」。 |
| 全仓 `gate` 字面量 grep | 命中 3 类，**全部与「协议门禁」无关**：(a) `gate|Gate` 落在 `surrogateescape` 里的 `gate` 子串；(b) `official_probe.py:1084 cmd_probe_gateway`（探网关用）；(c) `scripts\153_gate_grep.sh:3` —— grep 的是**上游 Shittim** 日志里的 `Timed out waiting for the per-account dispatch gate`（人家的 per-account 派发闸门）。 |

⇒ **「4 道门」是客户端侧的调用顺序，不是我们服务端的规则。** 我们能看到的唯一「门」是客户端自己的：它拿到 24000 响应后不再发 1017，是因为**反序列化/校验失败**，不是因为我们在服务端拦了它。（`report\48-登录卡死点-await与推送依赖分析.md` 的 await 链分析是同一结论的另一条证据线。）

---

## 6. Q5 · `diff_vs_official*.py` 会不会抓到「信封字段缺失」

两个脚本都是**纯结构 differ**，都不接在服务器里、也没留 24000 的运行产物（**未找到** 任何 `.diff.json` / run log）：

| 脚本 | 机制 | 能不能发现「缺 SessionKey/RequestId」 |
|---|---|---|
| `work\ba\server\diff_vs_official.py`（224 行） | 拍平成 `a.b.c` 路径，四分类：①只在左 ②只在右 ③类型不同 ④数组长度不同（docstring `:3-23`，`compare()` `:140`） | **能，但不醒目**：缺失键会变成 1 条「只在真服有」。它把 `dict↔list` 的容器冲突拍散成「很多条只在单侧」（`diff_vs_official_at95.py:11-13` 自己指出这个缺陷）。 |
| `work\ba\server\diff_vs_official_at95.py`（383 行） | **先比类型再递归**，把 `dict vs list` 单列为 **HIGH**，并单列「空/非空不一致 ★」；内置 `HOT_KEYS`（`:47-54`）就是 24000 的敏感键集，docstring 明写「这两类恰好是 24000 最可能的失败成因」（`:14-15`） | **能，而且是为此设计的**。只要 `python diff_vs_official_at95.py <official内层> <我们内层>` 就会列出缺 `SessionKey`/`RequestId`、`ZoneVisitCharacterDBs` dict↔list HIGH、`AcademyLocationDBs` 空/非空 ★。 |

**关键缺口**：这两个脚本**从未在 24000 上跑过一次**——`_bridge_ref` 提交的 05:46 那个 1 键包 vs 官方 7 键包，**一次 diff 就能定案**，但仓里没有任何这样的产物。`work\ba\proto\_sub\_cmp_out.txt`（之前的会话产物）其实已经手工做了这件事并给出了 `REQ has RequestId field? False` / `L2 requestid == packet RequestId : True`，只是结论没写进任何 `report/*.md`。

---

## 7. Q6 · 之前会话已经写下的结论（详细条目见 `D_prior_findings.json`）

一句话汇总：**这个问题已经被写清楚了三次，但每次都被下一轮当成「形状假设」重新讨论。**

1. `report\67-客户端协议请求序列.md:21,37`（2026-11-14 5:52，**最准确的一条**）：卡点不是登录同步，「是 `Academy_GetInfo`(24000) 我们压根没实现」，05:46:12 回的是「只含 `{"Protocol":24000}` 的假信封（192 B）」。
2. `report\63-已证实事实冻结版.md:133,137,177`：记录了文案首次出现、失败点后移、以及 05:46 那一轮的完整请求序列（1002→1001→跳过→24000→8 秒弹窗→零请求）。
3. `report\101-官方真服抓包分析.md:199-213,378,394`（2026-11-16 4:11，最新报告）：明确写「我们最近一次真实失败的那一轮，24000 回给客户端的其实是 `min` 兜底 … 根本没跑 Academy 模板」，并把「先把生成器从 `min` 兜底切到真模板」列为 **⓪ 最高性价比动作**。
4. `report\95-真服抓包与对照方案.md:21`：把 `StaticOpenConditions` 一份是 55 键 dict、一份是 `[]` 定为「头号嫌疑」——**方向对但归因错**（官方 24000 根本不发 `StaticOpenConditions`）。
5. `report\76:656` / `report\94:28-30,192,201,217-243`：设计层的假设（`Responses:[]` 会抛异常、24000 应为「6 基类 + 2 自有 = 9 键」、SessionKey 白名单）——**这三条都被 2026-11-16 的官方抓包否定**（真服：7 键；SessionKey 109/109 都有）。
6. `report\83c:15-23`：给出了 24000 的「两个版本」620/640 B（`StaticOpenConditions: []`）与 1964 B（55 键 dict），并诚实标注「新版本 **未验证**」。
7. `report\97:27-36`：把当时的学院部分贴成「`AcademyLocationDBs: []` = 一台账号一个学院地点都没有」，并去 `ExcelDB.db` 挖真实数据 —— **但 §A7 断言 `AcademyLocationDB` 只有 3 键，被官方抓包否定（真服每项还有 `AccountId`）**。
8. `report\74:383` / `report\96:441` / `report\90:75`：分别记录了「服务器侧必然看不到」、`24000 > 1019` 的优先级判断、以及 192 B 假包 + 8 秒 + REQUEST-ID 链断裂的完整事实。

**没有一条**文档记录过：官方 24000 的真实键集（7 键）、`RequestId` 这个字段的存在、`ZoneVisitCharacterDBs` 是 map、`AcademyDB.AccountId`。这些只在 `report\_tmp\` 的中间产物（`_cmp_out.txt`、`_struct_out.txt`、`official_decoded_201\`）里，**没有沉淀进 `report/*.md`**。

---

## 8. Q7 · 我们的 24000 必须补/改什么（按「最可能解锁客户端」排序）

> 下面每一条都给了**改哪里**。**本次不写任何代码进仓库**（纪律要求），只给位置与判据。

| 序 | 改动 | 代码位置 | 判据 / 备注 |
|---|---|---|---|
| **P0-1** | **让 24000 不走 min 兜底**：把 `Academy_GetInfo` 加进名字表（`EXTRA_TOKENS` 或服务器 `protocol_names.txt`），并在 `_generic_protocol_response` 里保证 `if num == 24000` 分支先于 else 命中 | `_bridge_ref/account_auth_probe.py:96-102`（EXTRA_TOKENS）/ `:685`（分支顺序）/ 服务器 `/www/wwwroot/bapatch/tools/protocol_names.txt` | 自检：日志 `gen_kind` 必须变成 `academy-24000` 或 `official-template`，且 `inner_keys == 7`。**这是 05:46 那条失败的直接成因。** |
| **P0-2** | **内层加 `RequestId`，且外层 `requestid` 与它同值** | bridge：`_bridge_ref/account_auth_probe.py:718-733`（`_cn_send_envelope`）；渲染器：`sandbox292:557-563` | 官方 109/109 都有；`L2.requestid == inner.RequestId` 已由 `_sub\_cmp_out.txt` 证。 |
| **P0-3** | **内层加 `SessionKey`（回显请求里的 `AccountServerId`/`MxToken`）** | 同上；并**修白名单**：`response_factory.py:105-113` + `:783-795` | 官方 109/109 都有 SessionKey ⇒ 白名单是伪事实，至少要允许 24000（建议直接改成「有会话就发」）。 |
| **P0-4** | **`ZoneVisitCharacterDBs` 从 list 改成 map**（`Dictionary<int-as-string, List<{UniqueId,ServerId,LastInteractTime}>>`） | 数据源 `academy_24000_official.json`；schema `dto_schema_full_v2.json` 的 `AcademyDB.ZoneVisitCharacterDBs`（现为 `kind=unknown`）；**并修错误断言** `gen_academy.py:305` | 官方是 dict(71)；同类旁证见 `_1017_schema.txt:20-30` 的 `CafeVisitCharacterDBs`。**当前 `gen_academy.py --check` 会为错形状背书。** |
| **P0-5** | **`AcademyDB.AccountId` 加上**（= `SessionKey.AccountServerId`，官方两者相等） | schema `AcademyDB`（现 3 字段）+ 渲染器 `_academy_24000_build`；**并修** `gen_academy.py:303` 的「键集 == 3」断言 | 官方 `AcademyDB.AccountId == SessionKey.AccountServerId : True`。 |
| **P1-1** | **`AcademyLocationDBs` 给非空（官方 9 条），每项补 `AccountId`** | `academy_24000_official.json`；schema `AcademyLocationDB`（现 3 字段）；`report/97` 的 `academy_seed.json` 可作后备数据源（但需补 `AccountId`） | `report/97:27-36` 已论证「空学院 = 一个地点都没有」不合理；官方 9 条 `{AccountId,LocationId,Rank,Exp}`。 |
| **P1-2** | **去掉官方没有的 4 个基类键**：`MissionProgressDBs` / `EventMissionProgressDBDict` / `BattlePassMissionProgressDBDict` / `StaticOpenConditions` | `_bridge_ref/account_auth_probe.py:687-688`（academy 分支内联字面量）；`response_factory.py:808-815`（`ResponsePacket` 6 字段无条件下发） | 官方 24000 只有 3 个基类字段（`ServerTimeTicks`/`ServerNotification` + `RequestId`/`SessionKey`）。**注意**：这也意味着 `report\95:21` 那条「StaticOpenConditions dict vs list」的「头号嫌疑」是**伪命题**——官方 24000 里没有这个键。 |
| **P1-3** | **`AcademyDB.LastUpdate` 补毫秒**（`2026-11-16T04:00:06.479`） | 模板 `academy_24000_official.json`（`_ACADEMY_24000_LASTUPDATE`，`sandbox292:416`） | 官方带 `.479`；我们写 `2026-11-14T00:00:00`。低风险但零成本。 |
| **P2-1** | **`MxToken` 签发格式改成 64 字符 base64**，并同步 `MX_TOKEN_RE` | `account_service.py:131`（正则）、`:716-720`（`issue_session_key`） | 官方 64 字符 base64；我们是 36 字符 uuid4，注释还自称「对齐客户端形态」。 |
| **P2-2** | 若走设计层：在 schema 里**新增 `RequestId`**（`BasePacket`/`ResponsePacket`），否则工厂永远发不出来 | `dto_schema_full_v2.json` / `dto_schema_full.json` 的 `BasePacket` / `ResponsePacket`；`response_factory._emit_object:781-815` | `RequestId` 在全部 `dto_schema*.json` 命中 **0**、`official_spec.json` 命中 **153**。 |
| **P2-3** | 把「官方 7 键」做成**回归门**：每次改完跑 `diff_vs_official_at95.py` 对比官方内层 | `work\ba\server\diff_vs_official_at95.py`（已具备能力，只差接进流程） | 退出码 0 = 无差异，可直接挂 CI / 上线前自检。 |
| **P2-4** | 24000 过了之后立刻会遇到 1017：**官方 1017 请求带 25 条 `SyncProtocols`**（我们观察到的客户端那条是 `[]`） | 见 `_sub\_cmp_out.txt` 的 `SYNC REQ raw` | `[20000,1003,2000,3000,5000,12000,6000,22001,17018,21000,28001,33000,19000,10006,39006,44000,29002,30041,45000,46000,46001,47000,49000,27002,49004]`。**注意**：`observed_sequence.json:205` 的「不能靠 SyncProtocols 决定 Responses」结论只对**我们这台客户端那一刻**成立，对官方不成立。 |

### 8.1 一条关键的实施提醒（避免重犯 `report/83c:3-13` 的教训）

`report\83c` 明确记过：「15:06:37 客户端验证 → 15:07:25 部署 → 1 分 29 秒的时序错位导致『某改动无效』的结论不成立」。⇒ **任何「改了还是不行」的判断，必须先核对部署时间 vs 客户端请求时间**。当前 `scripts\292_24000_official.py` **是否已在真服执行过：未找到证据**（仓内无 `/www/wwwroot/bapatch/academy_24000_official.json` 的回读、无 `--verify` 输出存档、无 bridge 重启记录）。在做任何新实验之前，**第一件事应该是确认这一点**，而不是再改第 11 版形状。

---

## 附录 A · 本次只读复算（可复现）

| 复算 | 方法 | 结果 |
|---|---|---|
| 24000 token | `base64.b32encode(md5('Academy_GetInfo'.encode('utf-16-le')).digest()).rstrip('=')` | `KKVAEXLS5QIIB36RQW27XRTJGI`（与 `protocol_map.json` 一致） |
| 官方 24000 键集 | `json.loads(outer['plain'])['packet']` 再 `json.loads` | `['Protocol','SessionKey','ServerTimeTicks','ServerNotification','RequestId','AcademyDB','AcademyLocationDBs']` |
| `RequestId` 覆盖率 | 遍历 `report\_tmp\official_decoded_201\*_api_*.response.json`（109 条内层可解析） | `SessionKey` 109/109，`RequestId` 109/109 |
| schema 是否含 `RequestId` | 对 6 份 schema/类型表做 `Select-String 'RequestId'` | `dto_schema*.json` **0**；`official_spec.json` **153** |
| `gen_kind` 取值域 | `Select-String 'gen_kind'` `_bridge_ref/account_auth_probe.py` | 4 处：`management-90004` / `academy-24000` / `loginsync-%d` / `min+base`（**无 `min`**） |

## 附录 B · 与题面不一致的三处（必须回给上层）

1. **`Account_LoginSync` 的协议号**：题面写 `1017`，`work\ba\proto\observed_sequence.json:219` 写「`Account_LoginSync = 1019`，`1017 = Account_DismissRepurchasablePopup`」。**仲裁结果：`1017` 是对的** —— `protocol_map.json` 里 `Account_LoginSync → id 1017`，`Account_DismissRepurchasablePopup → id 1015`，`1019 → Account_RequestBirthdayMail`；官方解码目录亦记为 `02_1017_api_account_loginsync`。`observed_sequence.json` 的 `Hash>>32 = 1019` 来自**我们这台客户端**发的一条包（`Hash=4376571674624`），与真服 1017 的 `Hash=4367981740035` 不是同一条 ⇒ 那次「纠错」本身是误判。
2. **「8 秒」与「60 秒」**：05:46 那轮是 ~8 秒（`observed_sequence.json:39`）；`report\74` 记的是 63 秒空窗；`report\97:27` 写 60 秒。三种数字并存，**不是同一轮的同一个量**。
3. **`SyncProtocols` 为空**：只对我们那台客户端成立（`observed_sequence.json:202`），官方是 25 条。
