# 61 — 服务端 `Account_Auth` 格式修正：`Protocol` 整数化 + 27 字段

> 时间：2026-11-14 05:19–05:25
> 角色：**srv-ops**（服务端执行与取证）。本文件记录**已实施的服务端变更 + 两组实际响应的解密明文**。
> 上游：lead 2026-11-14 05:19 通报（两份反汇编证据），`report\47`（20 属性闭合表），`report\33:92`（1019 协议名）
> 状态：**A 组已激活（`cn_wrap_mode = a_proto_int`），等待手机侧实测**

---

## 0. 一句话结论

按反汇编证据把内层 `Protocol` 从字符串改成 **int32 `1002`**，并把内层字段数从「我们自己拼的 27 键（含 `_probe`、含基类字段、缺 9 个 DTO 字段）」换成 **「`AccountAuthResponse` 声明的 27 个字段 + `Protocol`」**。
两组（A: int / B: str）除 `Protocol` 类型外**逐字节相同**，作为严格的单变量 A/B。

---

## 1. 证据链（来自 lead 通报，本报告不重新验证）

### 1.1 分发按 int32 协议号，不是字符串名

`NetworkService.ParseProtocol` 尾部指令：

```
0x73a89b4  ldr x8,[x9,#0x40]      ; 实际 klass
0x73a89b8  ldr x9,[x1,#0x40]      ; 期望 klass
0x73a89bc  cmp x8,x9
0x73a89c0  b.ne 0x73a89e0         ; klass 不符 → InvalidCastException
0x73a89c4  bl   0x63c73b8         ; 拆箱
0x73a89c8  ldr  w0,[x0]           ; ★ 返回 int32
0x73a89dc  bl   0x63c73d0         ; 另一条 bail：抛异常
```

- 客户端把协议字段**拆箱成 int32**；我们此前一直发字符串 `"Account_Auth"` ⇒ `cmp x8,x9` 当场不等 ⇒ `InvalidCastException`。
- **三条 bail 全部是"抛异常"，没有 `return null` 的静默分支**。Unity Release 构建里异常被上层吞掉、日志关闭 ⇒ 现象正是"发一条请求后永久静默、无弹窗、无第二次请求、无崩溃"。
- 这条同时解释了为什么改 `Nickname` / `UpdateRequired` / `CurrentVersion` 的**值**毫无作用 —— 解析在第一个字段就死了。

### 1.2 `AccountAuthResponse` 真实字段数 = 27

`type[10689]`，`MX.NetworkProtocol`，解混淆后 metadata 确证，声明顺序：

```
 1 CurrentVersion                  2 MinimumVersion                  3 IsDevelopment
 4 BattleValidation                5 UpdateRequired                  6 TTSCdnUri
 7 AccountDB                       8 AttendanceBookRewards           9 AttendanceHistoryDBs
10 RepurchasableMonthlyProductCountDBs 11 MonthlyProductParcel       12 MonthlyProductMail
13 BiweeklyProductParcel          14 BiweeklyProductMail            15 WeeklyProductParcel
16 WeeklyProductMail              17 EncryptedUID                   18 AccountRestrictionsDB
19 IssueAlertInfos                20 DailyRecordDBs                 21 OptionDB
22 IsArenaAnonymous               23 AccountLimitedFlashSaleDBs     24 NewlyAddedShopCashIds
25 IsNew                          26 Desc                           27 FunctionClose
```

**我们从来没发过的 9 个**：`MinimumVersion`、`IsDevelopment`、`BattleValidation`、`UpdateRequired`、`DailyRecordDBs`、`IsArenaAnonymous`、`IsNew`、`Desc`、`FunctionClose`

不属于这 27、而在**信封/基类层**的 6 个：
`Protocol`（`HttpMessage`）、`AccountId` / `ServerNotification` / `ServerTimeTicks` / `StaticOpenConditions`（`ResponsePacket`）
**`SessionKey` 确认客户端不存在，禁止再加。**

> 注：本报告 §1.1 的 `ParseProtocol` 与 §1.2 的 27 字段是两条**独立**证据，一处支持"类型"，一处支持"字段集合"。

---

## 2. ⚠️ 风险注记（必须保留，不做美化）

**`NetworkService.ParseProtocol` 属于网关/通道解包路径；而 `POST /api/account/auth` 走的是 BestHTTP + `GameSessionManager` 这一条 REST 路径。两者是否共用同一个 protocol 解析逻辑，目前没有任何证据。**

因此本轮的三种可能都是开着的：

| 情形 | A 组（int 1002）表现 | 说明 |
|---|---|---|
| REST 路也走 `ParseProtocol` | **应当推进**（出现第二条请求 / 界面变化） | A 必中 |
| REST 路不用内层 `Protocol`，只用外层 `protocol` 名字配对 | **与 B 完全一致**（即现状静默） | `Protocol:1002` 只是个被忽略的合法 int，不会更糟 |
| REST 路把 `Protocol:1002` 当成"未知协议名" | **可能触发与之前不同的失败路径** | ← **这正是我们要的可读信号**，不是纯负面 |

**换句话说：A 组的阴性结果不能证明"int 不是答案"，只能证明"在 REST 这条路上 int 也没被用来配对"。** 这条区别在后续阶梯里必须保留，否则会把 A 的阴性当成交互层已死的结论。

---

## 3. A/B 定义（只差一个变量）

外层信封保持不变：`{"protocol":"Account_Auth","packet":"<内层 JSON 序列化后的字符串>","requestid":"<uuid4>"}`，用 CN 加密（AES-256-CBC，key 在包尾 32 字节，IV 固定 `JOSYdf8ys97uhFYS`，整体 base64）。
**只改 `packet` 内层。**

### A 组：`Protocol` = 裸数字 `1002`
### B 组：`Protocol` = 字符串 `"Account_Auth"`

其余 27 字段两组完全相同：

```json
{"CurrentVersion":446690,"MinimumVersion":0,"IsDevelopment":false,"BattleValidation":false,
 "UpdateRequired":false,"TTSCdnUri":"","AccountDB":{},
 "AttendanceBookRewards":[],"AttendanceHistoryDBs":[],
 "RepurchasableMonthlyProductCountDBs":[],"MonthlyProductParcel":[],"MonthlyProductMail":[],
 "BiweeklyProductParcel":[],"BiweeklyProductMail":[],"WeeklyProductParcel":[],"WeeklyProductMail":[],
 "EncryptedUID":"","AccountRestrictionsDB":{},"IssueAlertInfos":[],"DailyRecordDBs":[],
 "OptionDB":{},"IsArenaAnonymous":false,"AccountLimitedFlashSaleDBs":[],
 "NewlyAddedShopCashIds":[],"IsNew":false,"Desc":"","FunctionClose":{}}
```

取值规则（lead §四）：
- 嵌套对象一律 `{}`、集合一律 `[]`、字符串 `""`、布尔 `false`、int 真实值或 `0`
- **`AccountDB` 发空对象 `{}`** ⇒ 规避 `LastConnectTime` / `BirthDay` / `CallNameUpdateTime` / `CreateDate` 四个 `DateTime` 字段的格式风险
- **不含 `SessionKey`**（客户端不存在该字段）
- **不含 `_probe` / canary**：本轮为干净 A/B，`cn_canary=on` 但**标记不进 JSON**，桥记录里记 `canary_skipped=true`

---

## 4. 实现与字节数

新增模块 `/www/wwwroot/bapatch/tools/cn_inner27.py`（可单独 `python3 cn_inner27.py` 复现两组）：

```
A (int 1002)          keys = 28   json = 631 B   线上 = 1088 B
B (str Account_Auth)  keys = 28   json = 641 B   线上 = 1112 B
```

新增桥模式：`a_proto_int` / `b_proto_str`（热切换，读 `cn_wrap_mode.txt`）。
留档：`/www/wwwroot/_ba_state/round18_A_wire.bin`、`round18_A_plain.txt`、`round18_B_wire.bin`、`round18_B_plain.txt`。

---

## 5. 两组实际响应的解密明文（逐字）

### A 组（`Protocol` = 1002）
```json
{"protocol":"Account_Auth","packet":"{\"Protocol\":1002,\"CurrentVersion\":446690,\"MinimumVersion\":0,\"IsDevelopment\":false,\"BattleValidation\":false,\"UpdateRequired\":false,\"TTSCdnUri\":\"\",\"AccountDB\":{},\"AttendanceBookRewards\":[],\"AttendanceHistoryDBs\":[],\"RepurchasableMonthlyProductCountDBs\":[],\"MonthlyProductParcel\":[],\"MonthlyProductMail\":[],\"BiweeklyProductParcel\":[],\"BiweeklyProductMail\":[],\"WeeklyProductParcel\":[],\"WeeklyProductMail\":[],\"EncryptedUID\":\"\",\"AccountRestrictionsDB\":{},\"IssueAlertInfos\":[],\"DailyRecordDBs\":[],\"OptionDB\":{},\"IsArenaAnonymous\":false,\"AccountLimitedFlashSaleDBs\":[],\"NewlyAddedShopCashIds\":[],\"IsNew\":false,\"Desc\":\"\",\"FunctionClose\":{}}","requestid":"1705b733-2968-4226-b28b-19d64904aa1c"}
```

### B 组（`Protocol` = "Account_Auth"）
```json
{"protocol":"Account_Auth","packet":"{\"Protocol\":\"Account_Auth\",\"CurrentVersion\":446690,\"MinimumVersion\":0,\"IsDevelopment\":false,\"BattleValidation\":false,\"UpdateRequired\":false,\"TTSCdnUri\":\"\",\"AccountDB\":{},\"AttendanceBookRewards\":[],\"AttendanceHistoryDBs\":[],\"RepurchasableMonthlyProductCountDBs\":[],\"MonthlyProductParcel\":[],\"MonthlyProductMail\":[],\"BiweeklyProductParcel\":[],\"BiweeklyProductMail\":[],\"WeeklyProductParcel\":[],\"WeeklyProductMail\":[],\"EncryptedUID\":\"\",\"AccountRestrictionsDB\":{},\"IssueAlertInfos\":[],\"DailyRecordDBs\":[],\"OptionDB\":{},\"IsArenaAnonymous\":false,\"AccountLimitedFlashSaleDBs\":[],\"NewlyAddedShopCashIds\":[],\"IsNew\":false,\"Desc\":\"\",\"FunctionClose\":{}}","requestid":"84d2f401-aec7-4bee-913d-3636b42070b9"}
```

### 响应头（A 组实测，经 nginx）
```
HTTP/1.1 200 OK
Date: Fri, 13 Nov 2026 21:20:18 GMT
Content-Type: text/plain; charset=utf-8
Content-Length: 1088
Connection: keep-alive
Vary: Accept-Encoding
（无 Content-Encoding / 无 Transfer-Encoding）
```

---

## 6. 变更清单与回滚

| 项 | 原值 | 新值 | 回滚 |
|---|---|---|---|
| 新增文件 | — | `tools/cn_inner27.py` | `rm` |
| `tools/account_auth_probe.py` | 支持 `e4_strict_dto` 等 | 新增 `a_proto_int` / `b_proto_str` 分支 + `import cn_inner27` | `cp -a account_auth_probe.py.ab27.1794604815 account_auth_probe.py` |
| `cn_wrap_mode.txt` | `e4_strict_dto` | **`a_proto_int`** | `echo e4_strict_dto > cn_wrap_mode.txt`（热） |

**备份点**：`/www/wwwroot/bapatch/tools/account_auth_probe.py.ab27.1794604815`
（更早：`.e4.1794603502`、`.e3.1794603141`、`.realcap.1794601220`、`.spec26.1794601009`、`cn_wire.py.e3.1794603141`）

**一行回滚（代码级）**
```sh
cp -a /www/wwwroot/bapatch/tools/account_auth_probe.py.ab27.1794604815 /www/wwwroot/bapatch/tools/account_auth_probe.py \
 && pkill -f account_auth_probe.py \
 && cd /www/wwwroot/bapatch/tools && nohup python3 account_auth_probe.py > /www/wwwroot/bapatch/logs/api_probe.out 2>&1 &
```

**A ↔ B（热切换，不重启）**
```sh
echo b_proto_str > /www/wwwroot/bapatch/cn_wrap_mode.txt
echo a_proto_int > /www/wwwroot/bapatch/cn_wrap_mode.txt
```

---

## 7. 本轮未改动（冻结确认）

```
cn_bridge_mode = bridge        cn_bridge_exp = decrypt+plain+http200
cn_resp_format = cn_envelope   cn_proto_val  = name        cn_packet_wrap = raw_gzip
cn_field_patch = on            cn_flatten_keys = on        cn_hash_mode  = off
cn_inner_src   = spec26        cn_inner_min = off          cn_relay      = off
cn_requestid_mode = random     cn_canary    = on（但本轮标记不入 JSON）

static  = SNI 透传（真 RapidSSL 证书），未动
宝塔 WAF = 未碰；`drop_ip.log` 最后一条 127.0.0.1 封禁 03:50:06，早已过期
```

---

## 8. 判读表（lead 定义）

| 现象 | 含义 |
|---|---|
| A 有推进（第二条请求 / 弹窗 / 昵称框），B 没有 | **Protocol 整数化定性闭合** |
| A、B 都静默 | 说明还有别的问题（例如"会话认领"那一层），A 的阴性**不等于** int 假设被否 |
| A 出现与之前不同的失败路径 | 也是信息：说明 `Protocol:1002` 被读取了 |

**下一步关键观测**：`Account_Auth` 之后是否出现 `Account_LoginSync`(1019)（base32 `P3OMQZD2FXV7XXEGA7ETCXIJ4Q`，见 `report\33:92`）。
- 有 ⇒ 会话被正确认领
- 无 ⇒ 响应仍在"认领"这一步被丢弃
