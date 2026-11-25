# 80 · schema 地基修复 —— `BasePacket` 与 `Responses`

> 角色：schema 地基修复员　｜　日期：2026-11-14　｜　约束：只读本地 + 只写自己的产物
> 未连接手机 / 未连接服务器 / 未触碰 `libtprt.so`
> v1 基线（**未修改**）：`work/ba/proto/dto_schema_full.json`
> sha256 = `3404a86f9de42a9cb3487164eea467d2…`，1,689,936 B，707 types
> 修复产物：`work/ba/proto/dto_schema_full_v2.json`
> sha256 = `eeba639e1889be001096c761509fac6f…`，2,370,325 B，709 types

---

## 0. 结论（先看这 8 行）

1. **根因**：v1 把 `ResponsePacket` 当根类型 —— 它的父类 `BasePacket` 从来没被提取进 schema，而 `SessionKey` / `OSType` 只存在于 `BasePacket` 上。⇒ 457 个响应根类型**结构上**不可能产出这两个键，逐协议打补丁永远打不完。
2. **不是"漏了两个字段"，是"漏了一整层继承"**：`extract_core.py` 的基类白名单只有 `ResponsePacket` / `RequestPacket`；`merge_full.py` 把每个 root 的 `base` 硬写成 `ResponsePacket`；`wire_fields()` 把基类字段硬编码成 `ResponsePacket` 的 6 个。三处合起来，`BasePacket` 既没被收进 schema，也没被继承。
3. **还有第 4 处同源缺陷**：`RequestPacket` 的 `base` 同样缺失（它也是 `BasePacket` 的子类）。抓包证明请求明文尾部就是 `"SessionKey":null,"AccountId":0,"OSType":2` —— 请求侧同样命中。
4. **`AccountId` 与 `Protocol` 连"字段"都不是**：metadata 里它们是 `BasePacket` 的**属性**且**无 setter**（`AccountId` 是 `SessionKey?.AccountServerId ?? 0`，`Protocol` 是每 DTO 的 override）。v1 是纯字段驱动的 schema，所以这两个成员连"字段"层面都不存在；`Protocol` 当年只能靠 `wire_fields` 里硬塞一个 `source: 'envelope'` 的假字段来兜。
5. **`Responses` 是单个可空引用，不是 List**：metadata `ti=57877` 的 byval 直指 `ResponsePacket` 本体；v1 因人工裁定 `MANUAL[57877]='List<ResponsePacket>'` 覆盖了 byval 证据 ⇒ 生成器产出 `[]`。v2 标 `emit:false`，不生成该键。
6. **`StaticOpenConditions` 属于 `ResponsePacket` 本层**，而且是那 6 个自有字段里的第 6 个 —— 所以 `ResponsePacket` 自有字段是 **6 个（含它）**，不是"6 个 + 它"。
7. **回归**：444/444 逐个通过（连 extras 共 457/457）。默认参数下 v2 的包与 **v1 的包去掉 `Responses` 一个键逐字节等价**；注入会话后 457/457 都多出 `SessionKey` + `AccountId` + `OSType`，且 `AccountId == SessionKey.AccountServerId`；0 个包 json 失败、0 个 DTO 丢字段。
8. **`--check-all` exit 0**。另有一条 `--no-base` 逃生通道，与 v1 的 `--no-base` 输出**完全相同**（28 键逐字节）。

---

## 1. 问题根因

### 1.1 现象（v1 的实际形态）

```
"ResponsePacket": { "fieldCount": 6, "fields": [...6...] }      ← 没有任何 base 键 ⇒ 被当根
"BasePacket":     不存在                                          ← 整层丢失
"AccountAuthResponse": { "base": "ResponsePacket", "fieldCount": 27 }  ← 27 个自有字段里没有 SessionKey/AccountId
```

`dto_schema_full.json` 里 `base` 取值分布：

| base | 数量 | 含义 |
|---|---|---|
| `ResponsePacket` | 452 | 正常（除 3 个二级继承） |
| `AccountAuthResponse` | 1 | `AccountAuth2Response` |
| `ShopBuyGacha2Response` | 1 | `ShopBuyGacha3Response` |
| `ShopBuyGacha3Response` | 1 | `ShopPickupSelectionGachaBuyResponse` |
| `null` / 无 `base` 键 | 250 + **2** | 250 个是 support 类型；**`ResponsePacket` 与 `RequestPacket` 本身也无 base** |

⇒ 继承链的"最顶层"被钉死在 `ResponsePacket`，而真实的顶层是 `BasePacket`。

### 1.2 三处代码合力造成（不是单点 bug）

| # | 位置 | 代码 | 后果 |
|---|---|---|---|
| a | `_full/extract_core.py:582` | `for b in (RESP_BASE, REQ_BASE):` | 只把 `ResponsePacket`/`RequestPacket` 当基类提取，`BasePacket` 从未进 schema |
| b | `_full/merge_full.py:249-253` | `if pname and pname != 'ResponsePacket' … else: e['base'] = 'ResponsePacket'` | 每个 root 的 base 被硬写成 `ResponsePacket`；`ResponsePacket` 自身没有 base 键 |
| c | `_full/extract_core.py:539-541, 601` | `BASE_FIELDS = [ServerTimeTicks …]` + `wire_fields(...)` | "基类字段"被硬编码成 `ResponsePacket` 的 6 个，`source` 也写成 `'ResponsePacket'` |
| d | `_full/extract_core.py:348, 371` | `skip = pname in ('ResponsePacket','RequestPacket','BasePacket')` | 祖先字段走到这三类就 `break` —— 本意是"基类由 (c) 统一处理"，但 (c) 只处理了 `ResponsePacket` |

**这是一个"看起来闭环、其实断了一环"的设计**：`BasePacket` 被显式写进了跳过名单（说明当初知道它存在），却没有任何一条路径负责把它补回来。

### 1.3 为什么它是"结构级"缺陷

metadata 的 typeDefinitions **只记录 backing field**。`BasePacket` 的 4 个属性里：

| 属性 | getter | setter | backing field | 结论 |
|---|---|---|---|---|
| `SessionKey` | ✔ | ✔ | ✔ | 有字段 ⇒ 能被字段驱动提取 |
| `Protocol` | ✔ | ✘ | ✘ | 抽象/override ⇒ **永远提不出来** |
| `AccountId` | ✔ | ✘ | ✘ | 只读派生 ⇒ **永远提不出来** |
| `OSType` | ✔ | ✔ | ✔ | 有字段 ⇒ 能提（但 v1 没提，见 §1.2） |

⇒ 即使在"字段驱动"的框架里修好 `BasePacket` 的继承，`AccountId` / `Protocol` 仍然只能靠 **属性表** 或 **源码** 才能补。v2 的做法是：`BasePacket.fields` 放两个真字段，另开 `derivedMembers[]` 放两个派生/抽象成员，并给出 `assignable:false` / `emit` 语义。

这解释了报告 43 号、46 号里那句"`AccountId` 由 `SessionKey` 派生"和我们 schema 里"找不到 AccountId"为什么能同时成立：**它在属性层，不在字段层。**

### 1.4 直接证据（本次从 metadata 现取，不只是引用旧报告）

`python _v2/probe_base.py` / `probe_props.py` 的输出（`typeDefinition.q[4]` 是父类型的 Il2CppType 索引，本 build 实测口径）：

```
BasePacket            td=10774  MX.NetworkProtocol
  q[4] → System.Object                      ← 真根
  fields: <SessionKey>k__BackingField  ti=59318 → MX.GameLogic.DBModel.SessionKey
          <OSType>k__BackingField      ti=50495 → System.Int32
  properties(步长 20B, propertyStart=12932..12935):
          SessionKey(get 0,  set 1)        ← 可写
          Protocol  (get 2,  set —)        ← 无 setter
          AccountId (get 3,  set —)        ← 无 setter（只读派生）
          OSType    (get 4,  set 5)        ← 可写

ResponsePacket        td=10776
  q[4] → MX.NetworkProtocol.BasePacket      ← 祖先是 BasePacket，不是 Object
  fields(6): ServerTimeTicks(long) / ServerNotification(enum) / MissionProgressDBs /
             EventMissionProgressDBDict / BattlePassMissionProgressDBDict / StaticOpenConditions

RequestPacket         td=10775
  q[4] → MX.NetworkProtocol.BasePacket      ← 同一处缺陷，请求侧
  fields(5, 其中 _counter 忽略): Resendable / Hash / IsTest / ModifiedServerTime__DebugOnly

SessionKey            td=12135  MX.GameLogic.DBModel
  fields(2): AccountServerId ti=50531 → System.Int64
             MxToken        ti=61196 → System.String
```

### 1.5 旁证：抓包

| 方向 | 证据 | 显示什么 |
|---|---|---|
| 请求 | `report/67` / `work/ba/proto/observed_sequence.json:197-198` | `{"Protocol":"Account_LoginSync",…,"SessionKey":null,"AccountId":0,"OSType":2}` —— 客户端自己在填 `BasePacket` 的三个成员 |
| 响应 | `report/36 §1`（Shittim 实测 24 键，含 `#5 AccountId=2`、`#6 SessionKey{AccountServerId:2, MxToken:<GUID>}`） | 真服 `Account_Auth` 响应确实带这两个键 |
| 代码 | `report/76 §1.3`（`GatewayController.cs:262-263`）= 回显；`report/76 §2.4` = `AccountId => SessionKey?.AccountServerId ?? 0` | 机制：只在会话白名单协议上回显到**顶层**响应对象 |

**关键旁证**：客户端请求明文的尾部键序是 `SessionKey → AccountId → OSType`，而 metadata 里 `BasePacket` 的属性序是 `SessionKey(0) → Protocol(1) → AccountId(2) → OSType(3)` —— **去掉被 override 到最前面的 `Protocol` 后完全一致**。这既是"`BasePacket` 就是这三个成员的宿主"的独立确认，也是 v2 生成器键序的依据（见 §3.5）。

### 1.6 为什么"逐协议打补丁"必然打不完

457 个响应根类型共用同一层基类。补 `AccountAuthResponse` 只是给 1/457 打了补丁，而且补在**错误的位置**（变成该 DTO 自有的 `fieldCount++`，与官方结构不符，还会让 `Account_Auth2` 这类子类重复/冲突）。缺的是一层，不是几个字段。

---

## 2. 修复内容

### 2.1 新增类型 `BasePacket`（td 10774）

```jsonc
"BasePacket": {
  "base": null, "isRoot": true, "direction": "both",
  "rootRole": "packet-envelope-base", "fieldCount": 2,
  "fields": [
    { "name":"SessionKey", "type":"SessionKey", "kind":"object", "nullable":true,
      "ti":59318, "ns":"MX.GameLogic.DBModel", "conf":"high", "src":"byval:…SessionKey" },
    { "name":"OSType", "type":"OSType", "kind":"enum",
      "ti":50495, "conf":"high", "src":"byval:System.Int32 + shittim(report28/76§1)",
      "enumValuesKnown": false }
  ],
  "properties": ["SessionKey","Protocol","AccountId","OSType"],
  "propertyEvidence": { "…getter/setter/backingField 逐项…" },
  "derivedMembers": [
    { "name":"AccountId", "type":"long", "derived":true, "readOnly":true, "assignable":false,
      "emit":"derived", "formula":"SessionKey?.AccountServerId ?? 0",
      "jsonWhenSessionKeyNull":0 },
    { "name":"Protocol", "type":"Protocol", "derived":true, "readOnly":true,
      "assignable":false, "emit":"envelope", "perDto":true }
  ]
}
```

- `SessionKey` 用 `kind:object` + `nullable:true`（C# 是 `SessionKey?`，**可空引用**；JSON 侧就是对象或 null）。
- `OSType` 用 `kind:"enum"`，但**明确记 `enumValuesKnown:false`**：metadata 里根本没有 `OSType` typedef（全表 0 命中），只能证到 `System.Int32`，枚举名来自 Shittim 源码。这是"不编"的写法（详见 §6）。
- `AccountId` / `Protocol` 在 `derivedMembers`，**不在 `fields`** ⇒ 任何生成器都不会把它当"需要赋值的输入字段"。

### 2.2 新增类型 `SessionKey`（td 12135）

| 字段 | type | kind | ti | 备注 |
|---|---|---|---|---|
| `AccountServerId` | `long` | scalar | 50531 → `System.Int64` | `typeAlt:"int"`：Shittim 源码是 `int`，国服 metadata 是 Int64（JSON 无差异，见 §6） |
| `MxToken` | `string` | scalar | 61196 → `System.String` | 36 字符带连字符的小写 GUID |

### 2.3 修改 `ResponsePacket` / `RequestPacket`

| 改动 | v1 | v2 |
|---|---|---|
| `ResponsePacket.base` | **无该键** | `"BasePacket"` |
| `ResponsePacket.baseChain` | — | `["BasePacket"]` |
| `ResponsePacket.isRoot` | — | `false` |
| `ResponsePacket.ownFieldCount` | — | `6` |
| `ResponsePacket.fields` | 6 个 | **原样不动**（6 个） |
| `ResponsePacket.StaticOpenConditions` | dict，conf=mid | 增 `dictKeyCount:55` / `dictValueDefault:0` / `dictKeysSrc` / `valueType` |
| `RequestPacket.base` | **无该键** | `"BasePacket"`（附加修复，第 4 例） |
| `RequestPacket.baseChain` | — | `["BasePacket"]` |

> `StaticOpenConditions` 的归属核实结论：它**在 `ResponsePacket.fields` 里**（metadata td=10776 的第 6 个 backing field，ti=10859），`BasePacket` 只有 2 个字段。所以 `ResponsePacket` 自有字段 = **6 个（含 StaticOpenConditions）**。原始任务描述里"已知 6 个 + StaticOpenConditions"应理解为"6 个里含它"。

### 2.4 修改 `AccountLoginSyncResponse.Responses`

| | v1 | v2 |
|---|---|---|
| `type` | `List<ResponsePacket>` | `ResponsePacket` |
| `kind` | `list` | `object` |
| `nullable` | — | `true` |
| `emit` | — | **`false`** |
| `src` | `manual:report65` | `byval:MX.NetworkProtocol.ResponsePacket(57877) + shittim_types.json(ResponsePacket?)` |

`fieldCount` 仍是 31 = **26 具名子回包 + 4 个非子回包（`FriendCount` / `FriendCode` / `PickupFirstGetHistoryDBs` / `AccountLevelRewardIds`）+ `Responses`**（逐字段清点见 §2.7 校验）。

### 2.5 全量重算 `baseChain` / `wireFields`（457 个响应根类型）

- `baseChain`：`["BasePacket","ResponsePacket"]`（3 个二级继承再加一层，例如 `AccountAuth2Response` → `["BasePacket","ResponsePacket","AccountAuthResponse"]`）。
- `wireFields` 顺序重写为：
  `Protocol` → `SessionKey` → `OSType` → `ResponsePacket` 的 6 个 → 祖先 DTO 字段 → 自身字段
- 每个条目带 `source`（`BasePacket` / `ResponsePacket` / `ancestor:<DTO>` / `own`）与 `emit`。
- 统计：`wireFieldCount` 例如 `AccountAuthResponse` = 36（= 1 Protocol + 2 BasePacket + 6 ResponsePacket + 27 own）。

> 为什么把 `SessionKey/OSType` 排在 `ServerTimeTicks` 前：`AccountId/OSType` 与 `SessionKey` 同属 `BasePacket`，这样分组与"属性表序"一致（§3.5）。JSON 对象无序，客户端反序列化不依赖键序。

### 2.6 只读派生成员的落地方式（生成器契约）

| 成员 | 生成器行为 | 依据 |
|---|---|---|
| `SessionKey` | 由 `--session-key` 三态控制（omit / null / provide） | §4.2 |
| `AccountId` | **不赋值**，恒由 `SessionKey.AccountServerId` 派生；`--account-id {derived,off,always}` | `SessionKey?.AccountServerId ?? 0` |
| `OSType` | `--ostype N`（默认 0）+ `--ostype-emit {auto,always,never}`（auto = 0 时省略） | §4.2 / §6 |
| `Protocol` | 不进 body，由信封输出（`emit:"envelope"`） | 既有行为不变 |

### 2.7 修改清单（逐条可核）

| # | 类型 | 变更 | 影响面 |
|---|---|---|---|
| F1 | `BasePacket` | **新增**（2 字段 + 4 属性 + 2 派生成员） | 459 个类型的继承链 |
| F2 | `SessionKey` | **新增**（2 字段） | `BasePacket.SessionKey` 的类型 |
| F3 | `ResponsePacket` | `base: null→BasePacket`、加 baseChain/ownFieldCount | 452 个直接子类 |
| F4 | `RequestPacket` | `base: 缺→BasePacket` | 请求侧（本次未生成请求） |
| F5 | `AccountLoginSyncResponse.Responses` | `List<>→ResponsePacket?` + `emit:false` | 1 个 DTO / 1 个键 |
| F6 | `StaticOpenConditions` | 固化 55 键字典证据 | 457 个包 |
| F7 | 457 个 root | 重算 `baseChain` / `wireFields` | 全量 |

---

## 3. 回归结果

### 3.1 方法（五组独立断言，缺一不可）

`gen_full_v2.py --check-all`：

| 组 | 断言 | 结果 |
|---|---|---|
| A 结构 | 457 个响应根类型的成员链里都能取到 `SessionKey`/`AccountId`/`OSType`，且 `SessionKey`/`OSType` 的宿主**必须是 `BasePacket`**，`baseChain` 必须以 `BasePacket` 开头且含 `ResponsePacket` | **457/457** |
| B 生成 | 默认参数（omit）逐个生成 → `json.dumps→json.loads` 往返、协议信封正确、字段集无缺无多、类型匹配、`Responses` 未生成 | **457/457**（信封 455，2 个 DTO 无协议号） |
| C 注入 | `--session-key provide --session-account-id 2 --mx-token <36 字符 GUID> --ostype 2` → 每个包都真的有 `SessionKey`(对象/2 键/GUID 36 字符) + `OSType`(int 2) + `AccountId`(2) | **457/457** |
| D 派生一致性 | `AccountId == SessionKey.AccountServerId` | **457/457** |
| E null 语义 | `--session-key null` → `"SessionKey":null` 且 `AccountId:0`，JSON 仍可解析 | **457/457** |

`_v2/regress_v1_vs_v2.py`（v1/v2 逐 DTO 值对比，只读 import `gen_full`）：

| 组 | 断言 | 结果 |
|---|---|---|
| R1 | v2 默认包 **==** "v1 包去掉 `Responses`"，逐键、逐值、递归全等 | **457/457** |
| R2 | v2 provide 包 == R1 包 + 恰好 `{SessionKey, AccountId, OSType}`，其余值一字不变 | **457/457** |
| R3 | v1 的每个顶层键在 v2 里都存在（唯一例外 `Responses`） | **457/457** |
| R4 | v1 的字段集（自有 + 继承 + `ResponsePacket` 6）在 v2 里一个不少 | **丢 0 个** |
| R5 | 两个模式的包 json 往返后与原文全等（无 float/None 变形） | **457/457** |

### 3.2 数字（444 口径 / extras / 合计）

| 口径 | n | == v1−Responses | 移除 Responses | omit 模式无基类键 | provide 模式三键齐 | json 通过 | 键数 v1 → v2 → v2+base |
|---|---|---|---|---|---|---|---|
| protocol_map（**444**） | 444 | 444 | 1 | 444 | 444 | 444 | 4237 → 4236 → 5568 |
| extras | 13 | 13 | 0 | 13 | 13 | 13 | 120 → 120 → 159 |
| **合计** | **457** | **457** | **1** | **457** | **457** | **457** | **4357 → 4356 → 5727** |

> 说明：`omit` 模式下"没有基类键"是**期望行为**（`SessionKey=null`、`AccountId=0`、`OSType=0` 都是默认值，等价于服务端 `DefaultValueHandling.Ignore` 丢弃）。它们**在结构上已经存在**（A 组 457/457 证明），只是取默认值时不落盘。这就是"不给值时应省略或用默认"。

### 3.3 关键协议前后对比

| proto | DTO | v1 顶层键 | v2 默认 | v2 注入会话 | `Responses` |
|---|---|---|---|---|---|
| 1000 | `AccountCreateResponse` | 7 | 7 | **10** | ∅ |
| 1001 | `AccountNicknameResponse` | 8 | 8 | **11** | ∅ |
| 1002 | `AccountAuthResponse` | 34 | 34 | **37** | ∅ |
| 1003 | `AccountCurrencySyncResponse` | 9 | 9 | **12** | ∅ |
| 1017 | `AccountLoginSyncResponse` | 38 | **37** | 40 | `[]` → 不生成 |
| 24000 | `AcademyGetInfoResponse` | 9 | 9 | **12** | ∅ |

### 3.4 拿真包对账：`Account_Auth`(1002) vs `report/36` 的官方 24 键

| | 结果 |
|---|---|
| v1 缺的官方键 | **`['AccountId', 'SessionKey']`** ← 正是本次修的两个 |
| **v2 缺的官方键** | **`[]`（一个不缺）** |
| v2 比官方多出的键 | 13 个：`OSType`、`MissionProgressDBs`、`EventMissionProgressDBDict`、`BattlePassMissionProgressDBDict`、`MinimumVersion`、`IsDevelopment`、`BattleValidation`、`UpdateRequired`、`DailyRecordDBs`、`IsArenaAnonymous`、`IsNew`、`Desc`、`FunctionClose` |
| v2 生成的会话字段 | `SessionKey = {"AccountServerId":2,"MxToken":"0404e715-…"}`，`AccountId = 2`，`OSType = 2` |

> 那 13 个多余键是 **v1 就有的既有行为**（官方对这些"值为默认/空的成员"会省略，我们的生成器一律输出），**不是本次修复引入**，见 §6 的 R-6。

### 3.5 键序与官方形态

`_v2/samples/1002_Account_Auth.with-session.json` 的实际键序：

```
Protocol → SessionKey → AccountId → OSType → ServerTimeTicks → ServerNotification → …
```

- `Protocol` 在最前：每个 DTO 都 override 了 `BasePacket.Protocol`，反射序里它在派生类自己的属性中第一个出（与客户端请求明文 `Protocol` 在首位一致）。
- `SessionKey → AccountId → OSType`：与 `BasePacket` 属性表序（`SessionKey(0) Protocol(1) AccountId(2) OSType(3)`）去掉 `Protocol` 后**完全一致**，也与客户端请求明文尾部一致。
- 官方响应（`report/36`）只给了"按字母序"的 24 行表，**响应侧真实键序未取证** ⇒ 这是推断+对齐客户端方向，不影响正确性（JSON 无序）。

### 3.6 逃生通道与自检命令

```bash
cd work/ba/proto
python _v2/make_v2.py                      # metadata 22 项证据自检全过 + 重建 v2 schema
python gen_full_v2.py --check-all          # exit 0（A–E 五组）
python _v2/regress_v1_vs_v2.py             # exit 0（R1–R5 五组）
python gen_full_v2.py --protocol 1002 --session-key provide \
       --session-account-id 2 --mx-token 0404e715-ec34-4808-b1b1-580aefafc3af --ostype 2
python gen_full_v2.py --protocol 1002 --no-base --out x.json   # 与 v1 --no-base 逐字节相同
```

本次实跑结果：`make_v2` = 22/22 自检通过；`--check-all` = **exit 0**；`regress` = **exit 0**；`--no-base` vs v1 = **完全相同（28 键）**。

### 3.7 产物清单（全部为新建，未覆盖任何他人文件）

| 文件 | 说明 |
|---|---|
| `work/ba/proto/dto_schema_full_v2.json` | **修复后的 schema**（709 types / 457 roots） |
| `work/ba/proto/gen_full_v2.py` | 生成器 + `--check-all`（exit 0） |
| `work/ba/proto/_v2/make_v2.py` | v2 schema 的**可复现构建脚本**（含 metadata 22 项证据断言） |
| `work/ba/proto/_v2/regress_v1_vs_v2.py` | v1↔v2 全量值级回归 |
| `work/ba/proto/_v2/stats444.py` | 444 / 13 / 457 三口径统计 |
| `work/ba/proto/_v2/make_samples_v2.py` | 样例包生成 + 对账表 |
| `work/ba/proto/_v2/probe_base.py` · `probe_props.py` · `probe_chain.py` · `probe_support.py` · `probe_dup.py` · `probe_count.py` · `probe_ex.py` | 只读探针（父链 / 属性 / 支撑类型 / 计数） |
| `work/ba/proto/_v2/samples/*.json`（5 个） | 1002 三态 + 1001 + 1017 样例 |
| `work/ba/proto/_v2/dump_all/*.json`（457 个） | 全量注入会话的产物 |
| `work/ba/proto/_v2/regress.result.json` | 回归机器可读结果 |

---

## 4. `Responses` 与 `StaticOpenConditions` 的处理

### 4.1 `Responses` 是单个可空引用，且恒不赋值

证据链（三条独立，互相印证）：

| 证据 | 内容 | 结论 |
|---|---|---|
| metadata byval | `AccountLoginSyncResponse.Responses` `ti=57877`；`ti-1 = 57876` 正是 `ResponsePacket` 的 `byvalTypeIndex` | 字段类型**就是** `ResponsePacket` 本体 ⇒ 单个引用 |
| shittim 源码声明 | `shittim_types.json` → `AccountLoginSyncResponse[0] = ["Responses","ResponsePacket?"]` | 单个可空引用（`?` 是 C# 可空引用注解） |
| v1 为什么变成 List | `extract_core.py:82` `MANUAL[57877] = ('List<ResponsePacket>','mid','manual:report65')`，而 `_resolve()` **先查 MANUAL 再看 byval** | 人工裁定覆盖了硬证据 ⇒ `kind:list` ⇒ 生成 `[]` |
| 生产代码 | `report/76`：Shittim 从不给该字段赋值 | 值恒为 `null` ⇒ 官方序列化时被 `Ignore` 掉 ⇒ **官方包里没有这个键** |

v2 处理：`type:"ResponsePacket"` / `kind:"object"` / `nullable:true` / **`emit:false`**，生成器**不生成该键**（绝不生成 `[]`）。
保留 `--responses null` 开关（生成 `"Responses": null`）以便 A/B，默认 `omit`。

**为什么 `[]` 有害而不只是"不好看"**：`ResponsePacket?` 是可空引用，给它喂数组是**类型不符**；客户端 `JsonConvert` 遇到"枚举字段给数组"通常会抛 `JsonSerializationException` 或静默置 null。`Report/76` 已经把 `Responses` 归到"非会话协议不该带"的一类，最保守且最像官方的形态是**整键不出现**。

### 4.2 `SessionKey` 为 null 时的序列化行为（这是本次必须讲清的一条）

**两个方向，两种行为，都有实测：**

| 方向 | 序列化器 | `SessionKey=null` 时 | 证据 |
|---|---|---|---|
| 客户端 → 服务端 | 客户端自己的 Json.NET（Unity） | **输出 `"SessionKey":null`**（连 `"AccountId":0` 也一起输出） | `report/67` / `observed_sequence.json:197` 真实请求明文 |
| 服务端 → 客户端 | Shittim `GatewayController.cs:122-128` 的 `jsonSettings`（`DefaultValueHandling.Ignore`） | **整键省略** | `report/76 §2.4`（源码） |

v2 生成器把两种都做成开关，**默认取"服务端语义"**：

| `--session-key` | 产出 | 适用 |
|---|---|---|
| `omit`（**默认**） | 无 `SessionKey`、无 `AccountId`；`OSType` 仅在 `!=0` 时出 | 官方非会话协议形态；与 v1 输出逐字节兼容（只少 `Responses`） |
| `null` | `"SessionKey":null` + `"AccountId":0` | 复刻客户端请求形态，做 A/B 实验 |
| `provide` | `"SessionKey":{"AccountServerId":N,"MxToken":"<36 字符 GUID>"}` + `"AccountId":N` | **`Account_Auth`(1002) 这类必须下发会话的协议** |

`AccountId` 永远**不单独赋值**：`derived`（默认）时它随 `SessionKey` 同进同出，值恒等于 `SessionKey.AccountServerId`；`null` 模式下自动变成 `0`；`omit` 模式下不出现。这正是 `report/76 §2.4` 说的"修 `SessionKey` 一处，`AccountId` 自动就好了"。

`OSType`：`--ostype N`（默认 `0`），`--ostype-emit auto` 时 `0` 视为默认值被省略（对齐 `Ignore` 语义）；客户端请求实测值是 `2`，要复刻官方"带上"就 `--ostype 2 --ostype-emit always`。

### 4.3 `StaticOpenConditions`：Dictionary(55)，属于 `ResponsePacket` 本层

| 项 | 结论 | 依据 |
|---|---|---|
| 归属 | **`ResponsePacket` 自有**（不是 `BasePacket`、也不是更上层） | metadata td=10776 第 6 个 backing field，ti=10859；`BasePacket` 只有 `SessionKey`/`OSType` 两个字段 |
| 形态 | **Dictionary**，不是 List | 抓包 `report/36 §4`：dict(55) 全 0；Shittim 源码 `Dictionary<OpenConditionContent, OpenConditionLockReason>`（`report/28`） |
| 键数 | 55（已固化进 schema：`dictKeyCount:55`、`dictValueDefault:0`） | `report/36 §4` 逐键清单 |
| 生成 | `gen_full_v2.py` 内联 55 键常量，值与 v1 **完全相同**（R1 逐字节证明） | — |

> 早期 `dto_schema.json` 曾把它判成 `List<OpenConditionDB>`（`build_response.py:212` 有注），那是**另一路**（`dto_schema.json`）的遗留问题，本次未改，见 §6 R-8。

---

## 5. 替换说明

### 5.1 最小替换（只影响"全量 DTO"这一路）

```bash
cd work/ba/proto
copy dto_schema_full.json  dto_schema_full.v1.bak.json      # 先留底
copy dto_schema_full_v2.json dto_schema_full.json           # 二选一：直接替换
```

或者**不替换**、用 `--schema` 显式指向 v2（更安全，可 A/B）：

```bash
python gen_full_v2.py --schema dto_schema_full_v2.json --protocol 1002 --session-key provide \
       --session-account-id 2 --mx-token <GUID> --ostype 2 --out 1002.json
```

**注意 v1/v2 的读法差异**（换成 v2 后下游必须知道）：

| 概念 | v1 | v2 |
|---|---|---|
| `ResponsePacket.base` | 无（= 根） | `"BasePacket"` |
| 基类字段来源 | `wireFields` 里 `source=='ResponsePacket'` | 走 `baseChain`（`BasePacket` → `ResponsePacket` → 父 DTO → 自身） |
| `AccountId` | 不存在 | `BasePacket.derivedMembers`，**不是 fields** |
| `Responses` | `fields` 里 `kind:list` | `fields` 里 `kind:object` + `emit:false` |
| 生成器要求 | 认 `base` 一层 | **必须递归走 `baseChain`**，并跳过 `emit:false` |

### 5.2 下游脚本：谁读 `dto_schema_full.json`，谁要改

先说结论（`grep` 实测，见下表）：**真正在跑服务的链路根本不读 `dto_schema_full.json`**。

| 脚本 | 读什么 | 与 v2 的关系 | 要改吗 |
|---|---|---|---|
| `gen_full.py` | `dto_schema_full.json` | **v1 生成器**（把 `ResponsePacket` 当根） | 别改它；用 `gen_full_v2.py` 取代 |
| `_full/final_check.py` | `dto_schema_full.json` + `gen_full` | 自检脚本，只读字段表 | 换成指向 v2 即可（或继续检查 v1 快照） |
| `_full/make_report.py` / `make_samples.py` / `stats_for_report.py` / `report_facts.py` / `qa_draft.py` / `cmp_report65.py` / `cmp_shittim_types.py` / `verify_raw_metadata.py` | `dto_schema_full.json` | **只读报表/核对**，会看到多出 `BasePacket`/`SessionKey` 两个类型、`ResponsePacket` 多一个 `base` 键 | 不改也能跑；若按 `len(schema)` 断言 707 会失败，改成 709 |
| `_full/merge_full.py` | 写 `dto_schema_full.json` | **重建脚本**，跑一次会把 v2 覆盖回 v1 口径 | **不要在执行替换后再跑它**；若要重跑，先按 §5.3 给它加 `BasePacket` 基类 |
| `build_response.py` | **`dto_schema.json`**（+`gen_default`） | **服务实际链路**，与 v2 无关，但**有同一处缺陷**（见 §5.4） | 需要单独打同一套补丁（本次按约束未改） |
| `gen_lobby.py` / `gen_academy.py` / `gen_default.py` | `dto_schema_lobby.json` / `dto_schema_academy.json` / `dto_schema.json` | 同上，三个 schema 也都没有 `BasePacket` | 同上 |
| `make_seeded_out.py` / `merge_seed_into_state.py` / `data_seed.py` | `dto_schema.json` + `seed.json` + `account_state*.json` | 与 v2 无直接耦合 | 不改 |

### 5.3 若要让重建脚本也产出 v2（可选）

`_full/merge_full.py:189` 那一行：

```python
for b in ('ResponsePacket', 'RequestPacket'):        # ← v1
for b in ('BasePacket', 'ResponsePacket', 'RequestPacket'):   # v2
```

并给 `extract_core.py` 的 `wire_fields()` 增加 `BasePacket` 段、`ancestor_own_fields()` 不再在 `BasePacket` 前 break。**本次不动别人的文件**，所以 v2 用 `_v2/make_v2.py` 在自己的产物上做后处理（读 v1 → 补三层 → 重算 baseChain/wireFields）。这条路径的好处是：**v1 一更新，`make_v2.py` 重跑即可复现**。

### 5.4 服务链路（`dto_schema.json` 那一路）的落地补丁草图

`dto_schema.json` / `dto_schema_lobby.json` / `dto_schema_academy.json` **三个都没有 `BasePacket`，`ResponsePacket.base` 都是 null/缺失**。运行时产物可以直接验证这一点：

| 运行期文件 | 顶层键 | `SessionKey` | `AccountId` | `OSType` | `Responses` |
|---|---|---|---|---|---|
| `out/variants/1002_Account_Auth.json` | 34 | ✘ | ✘ | ✘ | ∅ |
| `out/1001_Account_Nickname.json` | 8 | ✘ | ✘ | ✘ | ∅ |
| `out/1017_Account_LoginSync.json` | 38 | ✘ | ✘ | ✘ | **list(26)** ← 形状也不对 |

要改的是两处（**示意，未执行**）：

```python
# gen_default.py:88-91 现状：只上一级
base = entry.get('base')
if base and base in schema:
    for f in schema[base]['fields']: ...

# 需要：递归走 base 链 + 跳过 emit:false + 派生成员单独算
def _chain(dto):
    out, cur, seen = [], dto, set()
    while cur and cur in schema and cur not in seen:
        seen.add(cur); out.append(cur); cur = schema[cur].get('base')
    return list(reversed(out))
# 然后按 BasePacket.fields → ResponsePacket.fields → 祖先 → 自身 的顺序铺平，
# emit:false 跳过；AccountId 在最后按 SessionKey.AccountServerId 现算注入。
```

再加上 schema 侧的 F1/F2/F3/F5（可以从 `dto_schema_full_v2.json` 里把 `BasePacket` / `SessionKey` 两个类型原样 copy 过去，并给 `ResponsePacket` 加 `"base":"BasePacket"`）。**`dto_schema*.json` 不归本任务改，这里只给配方。**

### 5.5 建议的灰度顺序（低风险 → 高风险）

1. **不动服务**：先用 `gen_full_v2.py --no-base` 证明与 v1 逐字节一致（已证：28 键全等）⇒ 说明新生成器本身没有副作用。
2. **只发 1002**：`--session-key provide --session-account-id <真 ServerId> --mx-token <GUID> --ostype 2` 生成 `Account_Auth` 响应，配合 `report/76` 的 P0-1/P0-2 上线。
3. **观察下一协议**：客户端是否开始发 `Account_LoginSync`(1017) 之后的东西（`report/48` 的死点判据）。
4. **全量切**：`--session-key omit`（默认）覆盖其余 456 个协议 —— 与 v1 逐字节等价（只少 `Responses`），风险最低。
5. **`Responses` 单独验**：1017 的 `Responses` 从 `[]`/`list(26)` 变成"不出现"，若客户端对 1017 有反应异常，可回退到 `--responses null` 做二分。

### 5.6 回滚

```bash
# v2 只新增文件，回滚就是"不用它"
copy dto_schema_full.v1.bak.json dto_schema_full.json   # 若已替换
# 或者干脆继续用 gen_full.py + dto_schema_full.json（v1 原封未动）
```

**本次没有修改任何 v1 文件**（`dto_schema_full.json` / `dto_schema.json` / `dto_schema_lobby.json` / `dto_schema_academy.json` / `gen_full.py` / `gen_lobby.py` / `gen_academy.py` / `build_response.py`），所以回滚不需要还原动作。

---

## 6. 风险与不确定项

| ID | 项 | 状态 | 影响 | 建议 |
|---|---|---|---|---|
| R-1 | **`OSType` 的枚举值表** | **未确定**。metadata 全表无 `OSType` typedef，只能证到 `System.Int32`；名字来自 Shittim 源码 | 我们只能发整数。客户端实测发 `2`，我们发 `0` 会不会被误解？**不知道** | 保持 `--ostype 0 --ostype-emit auto`（默认不出现）最安全；要"像官方"就 `--ostype 2`。等有响应侧抓包再定 |
| R-2 | `SessionKey.AccountServerId` 类型 | metadata = `Int64`，Shittim 源码 = `int`（**冲突**） | JSON 都是 number，**无行为差异** | v2 记 `long` + `typeAlt:"int"`；真要抠就按源码改 `int`，不改也安全 |
| R-3 | 响应侧完整键序 | **未取证**（只有客户端请求明文与官方 24 键的字母序表） | JSON 无序，不影响解析；只影响与官方包的字节级比对 | 已按 `BasePacket` 属性序对齐客户端方向；后续抓一条真响应即可校准 |
| R-4 | `StaticOpenConditions` 55 键 | 单次抓包（`report/36`）全 0；`__Deprecated_*` 键是否长期存在**未确定** | 若官方某版本增删键，我们多/少一个枚举键 | 键集已固化在 schema（`dictKeyCount:55`），改动只需改常量；`build_response.py:212` 那一支仍是 List 判断，属另一路的遗留 |
| R-5 | **嵌套子响应是否该带会话凭据** | **推断**（非源码直读）。v2 的实现是"只有顶层包带" | 若官方其实给嵌套子包也带，我们的 1017 内层会少 3 个键（客户端只读它认识的字段，风险低） | 依据是 `GatewayController.cs:262-263` 只对顶层 `rsp` 赋 `SessionKey`。若后续抓包看到嵌套子包带 `SessionKey`，改 `gen_full_v2.build(top=True)` 的默认即可 |
| R-6 | 1002 比官方多 13 个键 | **既有问题**（v1 就有）：官方省略"值为默认/空"的成员，我们一律输出 | 客户端对多余键通常忽略；但 `Desc`/`FunctionClose` 之类若被当有效值可能影响 UI | 与本修复无关；建议另开一条"默认值省略（`Ignore` 语义）"的活 |
| R-7 | v1 文件被并发重写 | `dto_schema_full.json` 的 mtime 在我作业期间从 `6:22:05` 变为 `6:23:08`，**大小/内容未变**（仍无 `BasePacket`，`_meta.counts` 不变，sha256 `3404a86f…`） | 若别的 agent 正在改它，我的 v2 快照可能落后 | 报告已记录 sha256；建议以 `make_v2.py` 重跑为准（它是幂等的后处理） |
| R-8 | `dto_schema.json` / `_lobby` / `_academy` 仍是 v1 口径 | **确认**（三个都无 `BasePacket`） | **服务实际链路仍产出不含 `SessionKey` 的包** —— 这是本次修复**没有覆盖**的范围 | §5.4 给了配方；这是把"结构修复"变成"线上效果"的必经一步 |
| R-9 | 16 个 DB 内部的 `AccountId` 字段 | 与包络无关（`ClanMemberDB`/`FriendDB` 等数据模型自带） | 无 | 别把它们和 `BasePacket.AccountId` 混为一谈（`report/76` 已警示） |
| R-10 | `Protocol` 归属 | metadata 证 `BasePacket.Protocol` 是**无 setter 的抽象属性**；但请求侧实测发**字符串枚举名**、响应侧发**整数** | v2 只登记归属，**不改变**既有"响应发整数"行为 | 若要做请求侧生成，另议（`Protocol` 的线上类型两侧不一致，可能需要单独开关） |

---

## 附录 A · 证据索引

| 事实 | 出处 |
|---|---|
| `BasePacket` td=10774，字段 `SessionKey`/`OSType`，属性 4 个 | 本次 `_v2/probe_base.py` + `probe_props.py`（metadata `q[4]` / properties 段步长 20B） |
| `ResponsePacket`/`RequestPacket` 父类都是 `BasePacket` | 同上（`q[4]` byval 解析） |
| `SessionKey` td=12135 两字段及类型 | 同上 |
| `ResponsePacket` 自有字段恰好 6 个（含 `StaticOpenConditions`） | 同上 + v1 schema 一致 |
| `Responses` ti=57877 的 byval = `ResponsePacket` 本体 | 同上 + `shittim_types.json` |
| 官方 `Account_Auth` 响应 24 键、含 `AccountId=2` / `SessionKey` | `report/36 §1` |
| `StaticOpenConditions` 55 键全 0 | `report/36 §4` |
| 请求明文含 `"SessionKey":null,"AccountId":0,"OSType":2` | `report/67` / `work/ba/proto/observed_sequence.json:197-198` |
| `AccountId => SessionKey?.AccountServerId ?? 0`（只读派生） | `report/76 §2.4` |
| 网关只在**顶层**响应对白名单协议回显 `SessionKey` | `report/76 §1.3`（`GatewayController.cs:262-263`） |
| v1 三处代码成因 | `_full/extract_core.py:582,539-541,601,348,371`；`_full/merge_full.py:189,249-253`；`extract_core.py:82`（`MANUAL[57877]`） |
| 服务链路读的是 `dto_schema.json` | `build_response.py:38`；运行时产物 `out/variants/1002_Account_Auth.json` 无 `SessionKey` |

## 附录 B · 一条命令看结论

```bash
cd work/ba/proto && python gen_full_v2.py --check-all; echo "exit=$?"
# 响应 DTO（protocol_map 口径）: 444  额外恢复 DTO: 13  合计: 457
# A 结构继承: 457/457   B 默认 omit: json 457/457, Responses 未生成 457/457
# C provide 注入: 457/457   D AccountId 派生一致: 457/457   E null 模式: 457/457
# == ALL PASS ==   exit=0
```
