# TEST_SIMPLE — 1005 / 4000 / 26000 三协议验收报告

> 生成：2026-11-16 · 账号 `10015354380` · Python 3.12（Windows 本地）
> 交付物（**全部新建**，未改动任何现有文件，未连服务器）：
> `deploy/simple_payload.py`(13,099 B/355 行) · `deploy/gen_simple.py`(15,227 B/327 行) ·
> `deploy/patch_simple.py`(26,543 B/590 行) · `deploy/TEST_SIMPLE.md`(本文件)
> 上游只读：`work/ba/proto/official_spec.json`、`work/ba/proto/initial_state_rules.json`、
> `work/ba/proto/excel_field_map.json`、`work/ba/proto/spec_check.py`、
> `work/ba/server/prototype/specgen.py`、`report/_tmp/official_decoded_201/*`

---

## §0 一页结论

| 协议 | 名称 | 顶层键 | 我们 inner | 我们 wire | 官方 wire | 差 | spec_check | WARN | 开关文件 |
|---|---|---|---|---|---|---|---|---|---|
| 1005 | Account_GetTutorial | 6 | **267 B** | **556 B** | 640 B | −84 | **PASS**（FAIL 0） | 2 | `cn_1005.txt` |
| 4000 | Item_List | 7 | **361 B** | **684 B** | 16,088 B | −15,404 | **PASS**（FAIL 0） | 1 | `cn_4000.txt` |
| 26000 | ContentSave_Get | 8 | **321 B** | **640 B** | 640 B | **0** | **PASS**（FAIL 0） | 0 | `cn_26000.txt` |

三条独立自证（都不是「看着像对」）：

1. **逐字节复现官方**：把官方样本的**数据**喂给同一个构造器，三个协议都吐出**与官方完全相同的 packet 字符串**
   （320 / 10,582 / 321 字节，delta `+0`）。见 §4。结构、键序、JSON 序列化口径只要有一处不同，字符串就对不上。
2. **生成物 PASS spec_check 是构造保证**：载荷先由 `specgen.Spec.build()` 投影到 `official_spec.json` 的形状上，
   `conform` 记账 `dropped_keys=0 / forced_nodes=0`（没有为了过校验而丢键或强改值）。见 §3。
3. **补丁自检 26 项全绿**，含「内嵌副本 == 真源 sha256」「开关独立」「不抢别的协议」「RequestId 回填」
   「载荷 == gen_simple 的 spec_conform 结果」。见 §6.4。

三个开关是**运行时**的（`1`/`0`，缺失=关），一个出问题不影响另外两个；补丁本身也能按单元单独摘（§6.5）。

---

## §1 数据来源（逐字段溯源）

### 1.1 1005 Account_GetTutorial — 6 个顶层键

| 字段 | 值 | 来源 |
|---|---|---|
| `Protocol` | 1005 | `official_spec.json → protocols.1005`（键序 `Protocol,SessionKey,ServerTimeTicks,ServerNotification,RequestId,TutorialIds`，`top_key_order_stable=true`） |
| `SessionKey` | `{AccountServerId, MxToken}` | 账号：bridge 里取 `SESSION.account_id` → 请求片段 `"AccountServerId"` → `cn_simple_account.txt` → 10015354380。`MxToken` **回显客户端请求里的那个**（官方行为），拿不到才按 `sha384("ba-private-server:<id>")` 派生 64 字符 base64 |
| `ServerTimeTicks` | 当前时刻 | `.NET 100ns ticks`。官方实测解出来 = UTC 墙钟（`639304002559071160 → 2026-11-16T04:30:55.9Z`），故默认 UTC（`cn_simple_ticks.txt` 可切 local） |
| `ServerNotification` | 0 | 官方 109 条响应里恒 0 |
| `RequestId` | uuid4，**与 HTTP 外层 `requestid` 同值** | 计划书 §3.6；补丁自检里逐条验证（§6.4） |
| `TutorialIds` | **`[]`** | `initial_state_rules.json → q7_tutorials.initial.TutorialIds = []`（confidence **high**，5 条证据） |

**为什么是空**：`TutorialDBSchema` 那 33 行（`1..27` + `1011301,1011302,1011303,1021304,1031305,1031306`）
是**教程定义表**（每行 = 在哪个 UI 播哪段引导），**不含任何进度**。官方那条 21 条
`[1..14,16,17,19,21,22,23,27]` 是 27 条基础教程的**真子集**（缺 15/18/20/24/25/26），
只能是「这个号播过的」→ 新号 = 空。1005 的请求体里也没有任何「要哪些教程」的参数。

### 1.2 4000 Item_List — 7 个顶层键

| 字段 | 值 | 来源 |
|---|---|---|
| `ItemDBs` | **1 行**（见下） | `initial_state_rules.json → server_apply_skeleton.ItemDBs[0]` + `q3_initial_items.initial.ItemDBs[0]` |
| `ExpiryItemDBs` | `[]` | spec 里 `empty_observations=1`（官方就是空），限时道具按账号存档，新号没有 |
| 其余 5 键 | 同 1.1 | 同上 |

`ItemDBs[0]` 的 5 个键，逐个溯源：

| 键 | 我们的值 | 来源 / 依据 |
|---|---|---|
| `Type` | `4` | **ParcelType 枚举**（不是表字段）。`excel_field_map.json → maps.4000.ItemDBs[].Type`：`kind=enum, source=null`，并写明 4=Item。交叉：`GetName(FlatData.ParcelType, 4)` |
| `ServerId` | `1001535438020001` | 玩家数据，官方是 24xxxxxx 服务端自增号，**398 张表里 0 命中**。我们用项目统一公式 `account_id*100000 + kind*10000 + 序号`（`specgen.Account.obj_id`，kind=2=道具），与 1017 的角色/编队/家具同一套号段，多账号共库不撞号 |
| `UniqueId` | `2` | `excel_field_map.json → maps.4000.ItemDBs[].UniqueId`：`ItemDBSchema.Id`，**134/134 verified**。`ItemDBSchema` 1803 行里 `Id=2` 存在；`ids.json → items[1] = {id:2, name:"加速券"}` |
| `StackCount` | `5` | `DefaultParcelExcelTable` 里唯一一行 `ParcelType=4(Item), ParcelId=2, ParcelAmount=5` → **5 张加速券**（一行 × 5 个，不是 5 行） |
| `IsNew` | `true` | 新号道具带「新」标；`server_apply_skeleton.ItemDBs[0].IsNew = true` |

**`IsLocked` 被刻意丢掉**：skeleton 那一行是 `{Type:4, UniqueId:2, StackCount:5, IsNew:true, IsLocked:false}`，
但 `official_spec.json` 里 `IsLocked` **只出现在** `1017.CharacterDBs` / `1017.EquipmentDBs` /
`8002.ParcelResultDB.EquipmentDBs` / `22004.EquipmentDBs`，**4000 的 ItemDB 只有 5 个键**。
带上它就是「多键」FAIL。这是 `schema_v2.sql` 的列混进规则表的痕迹，不是官方字段。

> **绝不给空**：如果 `ItemDBs` 发 `[]`，背包就是空的（验收红线）。补丁自检里有一条专门断言
> `len(ItemDBs)==1 && Type==4 && UniqueId==2 && StackCount==5 && len(row)==5`。

### 1.3 26000 ContentSave_Get — 8 个顶层键

| 字段 | 值 | 来源 |
|---|---|---|
| `HasValidData` | `false` | `official_spec.json → protocols.26000`（`bool, always=true`） |
| `ContentSaveDB` | `null` | 同上：`type=null, nullable=true`（官方唯一形态就是 null） |
| `EventContentChangeDB` | `null` | 同上 |
| 其余 5 键 | 同 1.1 | 同上 |

**这个协议新号与官方号的唯一差别只有 ticks / RequestId / MxToken 三个「账号相关值」**，
所以 wire 字节数与官方**完全相等**（640 = 640）。见 §2.3。

### 1.4 三条容易踩空的坑（都已避开）

1. `TutorialDBSchema` 33 行是**定义**，不是**进度** —— 抄 33 条进 `TutorialIds` 是错的（客户端会以为你播过全部教程）。
2. `1017` 里的 `ItemListResponse` **是存在的槽但值为 null**，道具**只在 4000 下发** ——
   别指望 1017 补数据，也别往 1017 里塞 `ItemListResponse`。
3. `4000.ItemDBs[].Type` 是 **ParcelType 枚举**（`source=null`），不是 `ItemDBSchema` 的字段，
   `Key.Id` 那一套 join 不适用。

---

## §2 字节数：三个口径 + 与官方差在哪

### 2.1 为什么报三个数

`meta.resp_bytes` 在官方抓包里是 **HTTP body 的字符数**，不是「那串 JSON 的长度」。
容器是 `base64( AES-256-CBC(PKCS7(plaintext)) + 32 字节随机 key )`（`cn_wire.py` 已对真实响应验证过），
所以 **只由明文长度决定，不加密也能算**：

```
padded  = ceil(plain_len / 16) * 16
wire    = 4 * ceil((padded + 32) / 3)          # base64 字符数 == 客户端收到的 body 字数
```

实测对上：1005 官方 `plain=437 → padded 448 → +32=480 → 640`；4000 `plain=12031 → 12032 → +32=12064 → 16088`；
26000 `plain=438 → 480 → 640`。三个官方值全部复算命中，所以这个口径可信。

| 口径 | 是什么 | 用途 |
|---|---|---|
| `inner packet` | 真正塞进 `packet` 字段的那串 JSON | 与官方 packet 逐字节比（§4） |
| `outer plain` | `{"protocol","packet","requestid"}` | 容器入口 |
| `wire` | base64 加密后的 body 字符数 | **与官方 `resp_bytes` 同口径** |

### 2.2 1005：inner 267 vs 官方 320（−53），wire 556 vs 640（−84）

差的**不是结构，只有进度表内容**：

```
官方 TutorialIds 的 JSON 文本  = [1,2,...,27]  = 55 字节
我们的                         = []            =  2 字节
                                    差 53 字节 → packet 320 − 53 = 267 ✓ 一分不差
```

wire 那 −84 是**分组填充的台阶效应**：我们明文 384 已对齐 16（384 = 24×16，不填充），
官方 437 要填到 448。填充后相差 64 字节，`64 × 4/3 ≈ 84` 个 base64 字符。
**结论：−84 完全由「进度为空」解释，没有第二个来源。**

### 2.3 4000：inner 361 vs 官方 10,582（−10,221）

```
官方 134 行 − 我们 1 行 = 133 行
10,221 / 133 = 76.8 字节/行   （官方行形如 {"Type":4,"ServerId":24345791,"UniqueId":23,"StackCount":3208,"IsNew":false}）
```

我们这一行 84 字节（`ServerId` 16 位 vs 官方 8 位），所以是 `361 = 5 个信封 + 84 + []`。
**玩家数据规模差，与结构无关。**

### 2.4 26000：321 / 640，与官方**完全相同（delta +0）**

这条最能说明口径是对的：整个响应里没有一个「随账号规模变化」的字段，
所以我们的生成物与官方那一条**字节数一模一样**。

---

## §3 spec_check 实测

### 3.1 任务书里给的验收命令（原样照跑）

```bash
for p in 1005 4000 26000; do
  python work\ba\server\deploy\gen_simple.py --protocol $p --account-id 10015354380 --out report\_tmp\t$p.json
  cd work\ba\proto && python spec_check.py --protocol $p --file ..\..\report\_tmp\t$p.json
done
```

### 3.2 ⚠ 这条命令里的相对路径少跳一层（已实测确认）

在 `work\ba\proto` 里 `..\..\report\_tmp` 解析成 `BAServer\work\report\_tmp`（**不存在**）。
真实报错：

```
FileNotFoundError: [Errno 2] No such file or directory: '..\\..\\report\\_tmp\\t1005.json'
```

`work\ba\proto` 往上要跳**三层**才回到 `BAServer`。修正后的等价两条都跑过，结果一致：

```bash
# 修正 A（推荐，从 repo 根跑）
python work\ba\proto\spec_check.py --protocol 1005 --file report\_tmp\t1005.json

# 修正 B（保留「cd 进 proto」的原意）
cd work\ba\proto && python spec_check.py --protocol 1005 --file ..\..\..\report\_tmp\t1005.json
```

### 3.3 三条真实输出（修正 A）

```
协议 1005 (Account_GetTutorial)  文件 t1005.json
spec 观测次数: 1
  WARN [长度越界] TutorialIds  数组长度 0 不在观测范围 [21,21]
  WARN [空数组首见] TutorialIds  官方样本中未出现空数组
结果: PASS  (差异 0 条, 提示 2 条)                       ← exit 0

协议 4000 (Item_List)  文件 t4000.json
spec 观测次数: 1
  WARN [长度越界] ItemDBs  数组长度 1 不在观测范围 [134,134]
结果: PASS  (差异 0 条, 提示 1 条)                       ← exit 0

协议 26000 (ContentSave_Get)  文件 t26000.json
spec 观测次数: 1
结果: PASS  (差异 0 条, 提示 0 条)                       ← exit 0
```

修正 B（`cd` 进 `work\ba\proto` 再跑）三条同样 `PASS / exit 0`
（终端是 GBK 代码页，中文显示成乱码，但 `PASS` 结论行与 exit code 一致）。

生成器侧同时打印（`--quiet` 一行版）：

```
1005  Account_GetTutorial    PASS  inner=267 B  wire=556 B  FAIL=0 WARN=2  -> report\_tmp\t1005.json
4000  Item_List              PASS  inner=361 B  wire=684 B  FAIL=0 WARN=1  -> report\_tmp\t4000.json
26000 ContentSave_Get        PASS  inner=321 B  wire=640 B  FAIL=0 WARN=0  -> report\_tmp\t26000.json
```

`conform 记账 : {'dropped_keys': 0, 'forced_nodes': 0}` 三条都是 0 ——
**没有为了过校验而丢任何键或强改任何值**（`specgen.Spec.conform` 的探针恒为 0）。

---

## §4 最强自证：逐字节复现官方那三条

```bash
python work\ba\server\deploy\gen_simple.py --replay-official
```

```
==============================================================================
逐字节复现官方样本（数据取官方、结构取我们的构造器）
协议     官方样本                 结果           ours official    delta
1005   1005_api_account_get PASS          320      320       +0
4000   4000_api_item_list.r PASS        10582    10582       +0
       ItemDBs 行形状: ours=['Type', 'ServerId', 'UniqueId', 'StackCount', 'IsNew']
                       official=['Type', 'ServerId', 'UniqueId', 'StackCount', 'IsNew']  -> key 集/键序相同
26000  26000_api_contentsav PASS          321      321       +0
结论: PASS（三个协议都能逐字节复现官方）
```

读法：把官方样本那一号的 **MxToken / RequestId / ServerTimeTicks / TutorialIds（1005）/
ItemDBs（4000）** 原样喂进 `simple_payload.simple_build()`，输出的紧凑 JSON 与官方 `packet` 字符串
**逐字节相等**。也就是说：我们与官方只差「数据」，一点「结构」都不差。
4000 的 `ItemDBs` 是玩家数据（134 行 vs 新号 1 行）才换成官方那 134 行，
另加一条行形状断言（我们的 1 行与官方 134 行的键集/键序相同）。

---

## §5 WARN 逐条解释（共 3 条，全部是「合法但不常见」）

`spec_check` 的判定：FAIL 才不通过，WARN 是「合法但需注意」。三条逐条说清：

### WARN-1 `[长度越界] 1005 TutorialIds  数组长度 0 不在观测范围 [21,21]`

* **spec 里是什么**：`len_min=len_max=21`，因为官方只有 **1 条**观测（那是个 32 级号）。
  这只是「观测到的范围」，不是协议约束；`arrays_observed=1`。
* **为什么是 0**：新号一条教程都没播过。`initial_state_rules.q7_tutorials`（confidence **high**）
  明确 `initial.TutorialIds = []`。
* **什么情况会变成问题**：如果上机后客户端卡在教程那一步（不进大厅），说明它期望非空进度 ——
  那时改 `simple_payload.SIMPLE_TUTORIAL_IDS`（或 `gen_simple.py --tutorial-ids 1,2,...`）重新 apply 即可，
  不用改任何结构。
* **怎么消掉**：灌入真实的每账号进度（未来接 DB 时自然消掉）。

### WARN-2 `[空数组首见] 1005 TutorialIds  官方样本中未出现空数组`

* **spec 里是什么**：`empty_observations=0` → 官方 1 条样本里没见过空数组。
* **为什么仍合法**：`[]` 是「进度为空」**唯一**能表达的形状 —— 没有别的写法能表示「一个教程都没播」。
  协议里也没有「省略该键」这条路：`TutorialIds` 是 `always=true` 必填键，省略就是 **FAIL（缺键）**。
  所以空数组是这里唯一合法解。
* **怎么消掉**：同 WARN-1。

### WARN-3 `[长度越界] 4000 ItemDBs  数组长度 1 不在观测范围 [134,134]`

* **spec 里是什么**：官方那 134 条是**玩过的号**的道具（`len_min=len_max=134`，`empty_observations=0`）。
* **为什么是 1**：新号只有 `DefaultParcelExcelTable` 那一行（加速券 × 5）。规则表
  `server_apply_skeleton.ItemDBs` 也只有 1 行；`q3_initial_items` 的证据链是「全表只有 1 行 ParcelType=4」。
* **为什么不能发 0**：发空 = 背包空 = 这条协议等于没做。**这是本任务的验收红线**，已写进补丁自检。
* **什么情况会变成问题**：客户端若按「道具格」渲染并期望某种占位，可能需要补更多行 ——
  但那属于运营数据（哪些道具该给新号），不是结构问题。给多少行都能 PASS（spec 只 WARN）。

> 补充：`4000.ExpiryItemDBs = []` 与 `26000.ContentSaveDB = null` **没有**产生 WARN，
> 因为 spec 里 `ExpiryItemDBs.empty_observations=1`（官方就是空）、`ContentSaveDB` 是 `type=null, nullable=true`（官方就是 null）。
> `conform 记账` 三条全 0，说明也没有「靠丢键过校验」的隐藏项。

---

## §6 补丁：三个单元 / 独立开关 / 26 项自检

### 6.1 挂在哪（3 个插入点，锚点唯一，不唯一就拒改）

| 单元 | 位置 | 作用 |
|---|---|---|
| `PAYLOAD` | `if __name__ == '__main__':` 之前 | 把 `deploy/simple_payload.py` **逐字节原样**内嵌（不抄第二份） |
| `HOOK-G` | `_generic_protocol_response()` 里，`if num == 90004:` 之前 | 主路径：现在的 `min+base` 兜底就长在这里（7 个假键 `MissionProgressDBs` / `StaticOpenConditions` …） |
| `HOOK-D` | `_bridge()` 的 path D，`if proto_int:` 之前 | 那条路会回 `{"Protocol":N}` 单键（`cn_nick.build_min_response`），先接管 |

两个 hook 都包 `try/except`，异常只写 `rec['simple_err']` 然后**原路返回** —— 本补丁自身出问题
不会把别的协议带崩。`HOOK-G` 取 `frag` 用 `locals().get('frag')`，因为线上 bridge 与仓库副本不是同一版（见 §7 R2）。

### 6.2 为什么两个 hook 都要

`_bridge()` 里有两处会「回答」未知协议：

* 名字不在 `NAME_TABLE` → 直接 `_generic_protocol_response()`（HOOK-G 在这条路尽头）；
* 名字在表里 → 走到 path D，若 `rec['req_Hash']` 有值就 `cn_nick.build_min_response(proto_int)` = **只有 `{"Protocol":N}` 一个键**。

`rec['req_Hash']` 只在 `exp = decrypt+*` 的 path A 里被设置，所以**两条路都要挂**。
（顺带解释计划书 §0 的怪现象：日志里既出现过 `min`，也出现过 `min+base` —— 就是这两条路的区别。）

### 6.3 独立开关（运行时）

```
/www/wwwroot/bapatch/tools/cn_1005.txt    内容 "1" = 开，"0"/缺失 = 关
/www/wwwroot/bapatch/tools/cn_4000.txt
/www/wwwroot/bapatch/tools/cn_26000.txt
```

查找顺序：`bridge 所在目录` → `/www/wwwroot/bapatch/tools` → `/www/wwwroot/bapatch`
（放哪个都行，bridge 目录优先）。**缺失 = 关**（fail-safe：忘了建文件不会意外接管）。

另外两个可选文件（不建就走默认）：

```
cn_simple_account.txt   账号号兜底（SESSION.account_id 拿不到时用）
cn_simple_ticks.txt     utc(默认) | local
```

关掉一个不影响另外两个 —— 自检里有专门一条：把 `cn_4000.txt` 写 `0`，
`simple_switch_on(4000)=False` 而 `simple_switch_on(1005)=True`。

### 6.4 自检 26 项（`--verify`，本地沙箱副本实测，全绿）

```
PASS  python 语法检查 compile()
PASS  PAYLOAD 标记成对、各 1 处（BEGIN 1 / END 1）
PASS  HOOK-D 标记成对、各 1 处（BEGIN 1 / END 1）
PASS  HOOK-G 标记成对、各 1 处（BEGIN 1 / END 1）
PASS  PAYLOAD 内嵌副本 == deploy/simple_payload.py 逐字节（sha256 871a78b7e049c8e9 / 871a78b7e049c8e9）
PASS  PAYLOAD 标记里记的 sha256 与真源一致（871a78b7e049c8e9）
PASS  HOOK-G 落在 _generic_protocol_response() 内（def@22592 < hook@23401 < 下一函数@26850）
PASS  HOOK-D 落在 path D 的 `if proto_int:` 之前（hook@46039 < anchor@46505）
PASS  HOOK-G 落在 `if num == 90004:` 之前
PASS  PAYLOAD 落在 `if __name__ == '__main__':` 之前
PASS  内嵌 PAYLOAD 可 exec
PASS  开关文件缺失 -> 判定「关」（fail-safe，不会意外接管）
PASS  三个开关=1 -> 全部「开」
PASS  只关 cn_4000.txt -> 1005 仍开、4000 关（三个开关互相独立）
PASS  simple_route(1005): 200 / 外层 protocol=Account_GetTutorial / inner.RequestId==外层 requestid=True / 顶层 6 键
PASS  1005 TutorialIds == []（新号进度为空）
PASS  simple_route(4000): 200 / 外层 protocol=Item_List / inner.RequestId==外层 requestid=True / 顶层 7 键
PASS  4000 ItemDBs = 1 行加速券（Type=4 / UniqueId=2 / StackCount=5 / 5 键，非空）
PASS  simple_route(26000): 200 / 外层 protocol=ContentSave_Get / inner.RequestId==外层 requestid=True / 顶层 8 键
PASS  26000 HasValidData=false + ContentSaveDB/EventContentChangeDB 均为 null
PASS  三个开关全关 -> 全部返回 None（交回原有兜底，行为完全回到打补丁前）
PASS  开关全开也不会接管别的协议（3 / 8000 / 90004 / 24000 / 1017 -> None）
PASS  1005 回显客户端 MxToken/AccountServerId（官方行为），且 gen_kind='simple-1005'
PASS  无请求片段时 MxToken 由账号派生（64 字符 base64）、账号回落到 10015354380
PASS  bridge 载荷 == gen_simple 的 spec_conform 结果（键序/键数/类型全等）
INFO  1005   cn_1005.txt '1'            -> ON
INFO  4000   cn_4000.txt '1'            -> ON
INFO  26000  cn_26000.txt '1'            -> ON
自检: 全绿
```

第 25 条是关键：bridge 里那份 dict 与 `gen_simple` 经 `specgen.conform` 后的 dict **逐字节相同**，
所以「本地验收通过的文件」就是「线上真正会发出去的包」。

### 6.5 幂等 / 回滚（实测）

本地演练用的是**副本**（`deploy/_sandbox/account_auth_probe.py`，从 `_bridge_ref` 复制），`_bridge_ref` 本身没被碰过：

```
原始副本 sha256 = d4cc743664eca8fc819108ea55243d54685e425168a2f73e73c6dada7795703e  (1,125 行 / 46,568 B)

apply  #1 → 1,503 行 / 61,055 B（+357 payload / +10 HOOK-D / +11 HOOK-G）  语法 PASS，verify 全绿
apply  #2 → 1,503 行 / 61,055 B，逐块「替换已有块（旧 N 行 → 新 N 行，幂等）」，字节数不变
--rollback --only HOOK-G → 只摘 HOOK-G（11 行），PAYLOAD / HOOK-D 两块仍在（重新 apply 可补回）
--rollback（全量）  → 1,125 行 / 46,568 B
                    → sha256 = d4cc743664eca8fc819108ea55243d54685e425168a2f73e73c6dada7795703e
                      与原始副本 **逐字节相同**（`逐字节相同 = True`）
--rollback（再来一次）→「什么都没改（三块本来就不在）」，幂等
```

---

## §7 风险与未验证项（上机先看这几条）

### R1 ★ 如果线上 `cn_bridge_exp = decrypt+*`，本补丁**不会**生效

`_bridge()` 的 path A 在 `exp.startswith('decrypt+')` 时会把客户端请求**代理给 shittim**
（`post_gateway`）并直接返回它的响应，根本走不到 `_generic_protocol_response`。
我们**故意没动 path A** —— 那个开关的语义就是「让 shittim 回答」，去改它等于废掉这条实验通道。

```bash
cat /www/wwwroot/bapatch/cn_bridge_exp.txt      # 必须**不以** decrypt+ 开头（空 / plain 都行）
```
`report\83-服务端当前状态快照.md` 记的是 `decrypt+plain+http200` —— 若仍是这个值，
**三个协议的包仍会来自 shittim**，日志里不会出现 `gen_kind=simple-*`。

### R2 ★ 线上 bridge ≠ 仓库副本，锚点可能对不上

`report\83` 记线上 `account_auth_probe.py = 45,470 B`，仓库 `_bridge_ref` 是 `46,568 B`（1,098 B 差）。
所以：

* **必须先 `--dry-run`**（在服务器上、对线上文件），看三个锚点是否都命中；
* 命中不了就 **abort、不写一个字节**（`锚点不唯一/找不到 → 拒绝动这个文件`），不会打出半截补丁；
* 即使锚点命中，`HOOK-G` 也已用 `locals().get('frag')` 兜住「局部变量名不同」这种版本差异。

### R3 `ServerTimeTicks` 取 UTC 还是本地时间

官方实测 = **UTC**（`639304002559071160 → 2026-11-16T04:30:55.9Z`），所以默认 UTC。
但 bridge 里**老分支**（`_generic` 的 min+base、90004）用的是 `datetime.now()` 本地时间，
两者会差 8 小时。本补丁只改这三个协议，没有统一时钟——如果上机后发现时钟类 UI 异常，
`echo local > /www/wwwroot/bapatch/tools/cn_simple_ticks.txt` 切过去对比即可。

### R4 `ServerId` 号段是本项目约定，不是官方自增号

我们发 `1001535438020001`（16 位），官方是 `24xxxxxx`（8 位）。spec 只要求 `int`，
客户端按它做唯一键，量级无影响；且与 1017 的角色/编队 ServerId 用同一公式（`obj_id`），跨协议自洽。
**未上机验证过**（D 线同样未验证）。

### R5 三个 spec 的置信度都是 `low`

`observations=1` —— 每个协议官方只抓到过一条。字段级结论（键集/键序/类型）可信，
但「可选键」和「长度范围」随时可能不完整。`spec_check` 的 WARN 就是这个原因。

### R6 `IsLocked` 被丢弃是**故意**的

见 §1.2。若哪天客户端对道具锁状态有依赖，得先确认 4000 的 ItemDB 到底有没有这个字段
（现有 109 条官方响应里 4000 只有 5 键）。

### R7 `TutorialIds = []` 没上机验证过

这是本补丁最可能「数据对、行为不对」的一处 —— 客户端会不会因为进度为空而**重新走一遍教程**，
只有上机能回答。要观察：

* 进大厅后是否弹教程/引导；
* 若卡住，把 `simple_payload.py` 的 `SIMPLE_TUTORIAL_IDS` 改成非空（或 `--tutorial-ids`）重新 apply，结构不用动。

---

## §8 部署 / 回滚 / 观测

### 8.1 上线（把 3 个文件传上去，然后在服务器上跑）

```bash
# 0) 传（deploy 里三个 .py 就够，TEST_SIMPLE.md 是文档）
scp work/ba/server/deploy/{simple_payload.py,gen_simple.py,patch_simple.py} \
    root@HOST:/www/wwwroot/bapatch/deploy_simple/

# 1) 先用线上真实文件干跑（必须：线上副本与仓库不同，见 R2）
python3 /www/wwwroot/bapatch/deploy_simple/patch_simple.py --dry-run
#   期望看到三行：PAYLOAD / HOOK-D / HOOK-G 各「插入 N 行」+「语法检查: PASS」

# 2) 打补丁 + 开三个开关（自动备份 account_auth_probe.py.simple.bak.<TS>）
python3 /www/wwwroot/bapatch/deploy_simple/patch_simple.py --apply --switches 1

# 3) 自检 26 项（必须全绿再重启）
python3 /www/wwwroot/bapatch/deploy_simple/patch_simple.py --verify

# 4) 重启 bridge（本机无 systemd unit，历史上是 pkill + nohup，见 report/61）
pkill -f account_auth_probe.py
cd /www/wwwroot/bapatch/tools && nohup python3 account_auth_probe.py \
    > /www/wwwroot/bapatch/logs/api_probe.out 2>&1 &
ss -ltnp | grep 9097        # 确认起来了
```

### 8.2 只改一个协议（隔离故障）

```bash
# 关掉 4000，1005/26000 继续生效
echo 0 > /www/wwwroot/bapatch/tools/cn_4000.txt
# 重新打开
echo 1 > /www/wwwroot/bapatch/tools/cn_4000.txt
```
开关是**每次请求读文件**，不用重启 bridge、不用重新打补丁。

### 8.3 回滚

```bash
# A. 摘掉三块（幂等，其它改动都保留）
python3 /www/wwwroot/bapatch/deploy_simple/patch_simple.py --rollback

# B. 直接还原备份（最保险）
cp -a /www/wwwroot/bapatch/tools/account_auth_probe.py.simple.bak.<TS> \
      /www/wwwroot/bapatch/tools/account_auth_probe.py

# C. 只摘掉某一块（其余保留，可再用 --apply 补回）
python3 .../patch_simple.py --rollback --only HOOK-G
```
回滚后同样要重启 bridge。

### 8.4 上机后怎么确认真的生效了

```bash
# 三个协议各自的生成标记（期望 gen_kind = simple-<协议号>）
grep -E '"gen_kind": *"simple-' /www/wwwroot/bapatch/logs/api_all_requests.log | tail -5

# 1005：期望 simple_keys=6, simple_tutorial_ids=0, enc_body_len≈556
grep 'protocol=1005' /www/wwwroot/bapatch/logs/api_all_requests.log | tail -3

# 4000：期望 simple_item_rows=1（**不是 0** —— 0 就是背包空了）
grep 'protocol=4000' /www/wwwroot/bapatch/logs/api_all_requests.log | tail -3

# 26000：期望 simple_keys=8, enc_body_len=640
grep 'protocol=26000' /www/wwwroot/bapatch/logs/api_all_requests.log | tail -3

# 补丁自身有没有出错（期望**空**）
grep simple_err /www/wwwroot/bapatch/logs/api_all_requests.log | tail

# 还在走老兜底？说明开关没开 / exp 是 decrypt+*（R1）
grep -E '"(gen_kind|fallback)": *"(min\+base|min-envelope|simple-off)' \
     /www/wwwroot/bapatch/logs/api_all_requests.log | tail
```

日志里每条 `rec` 会多出这些键：`gen_kind=simple-<N>` / `fallback=simple-envelope` /
`simple_proto` / `simple_name` / `simple_account_id` / `simple_keys` /
`simple_item_rows` / `simple_tutorial_ids` / `simple_ticks` / `simple_err`（只在出错时出现）
以及原有的 `enc_requestid` / `enc_plain_len` / `enc_body_len`。
