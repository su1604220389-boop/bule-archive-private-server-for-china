# 独立复核报告（红队）

- 复核对象：`work\ba\proto\official_spec.json`（958 347 B）、`work\ba\proto\initial_state_rules.json`（41 319 B）
- 复核角色：独立第三方；**未修改任何现有文件**，未连服务器/手机
- 复核时间：2026-11-16
- 结论先行：**产出 1 的结构事实 100% 复现（1 处表示法缺陷）；产出 2 的核心数值全部复现（3 处证据/表述错误）**

---

## 1. 复核方法（全部为重写实现，不 import 被复核脚本）

| 复核项 | 我的方法 | 与被复核实现的差异 |
|---|---|---|
| spec 结构 | 自写 `review/rv_spec.py`：对 109 个 `*.response.json` 做**扁平路径聚合**（`$` / `a.b` / `a[]` / `a{}`），每路径统计类型多重集、null 次数、object 实例数、子键出现次数、键序、数组长度、全数字键实例数 | 对方用 `Node` 递归累加器 + `build()` 生成树；我用「路径 → 计数器」单遍扫描，再从 spec 树反向逐节点取数核对。数据结构、遍历方向、类型判定都不同 |
| spec 校验 | 自写 `review/rv_nullable.py` 复核 nullable/optional 证据强度；另**重跑** `spec_check.py --all` 复现其 109/109 结论 | 结论复现，但指出该校验与被校验数据同源（循环论证），不能单独作为正确性证据 |
| FlatBuffers | 自写 `review/rv_fb.py`：按规范手写 root uoffset → table → i32 soffset → vtable → slot 偏移；`soffset` 按**有符号**；每 slot 独立判 string/table/vector/scalar，再做整表多数投票 | 不 import `dump_table.py` / `fbparse.py`；额外直接打印每个 slot 的 u32/i32/f32/**i64** 四视图与原始 hex，用于人工对账 |
| ExcelDB | 直接 `sqlite3` 只读 `file:...?mode=ro`，`SELECT` 事实 | 不复用 `dump_table.py` 的 SQL 层 |
| 官方响应对照 | 直接 `json.load` 顶层键，不做 spec 驱动 | — |
| 特殊行形状 | 用自写解析器直接解 `ShopRecruitDBSchema` 的 1/2/3/5000000 行 BLOB | 对方用 `dump_table.py` |

覆盖量：**109 条响应 / 38 个协议 / 2 346 个 spec 节点 / 1 767 条字段出现性判定 / 6 张规则表全部行 / 5 张 ExcelDB 表 / 4 条官方响应**。

---

## 2. 产出 1：`official_spec.json` 逐条判定

### 2.1 总量与全局结论

| # | 声称 | 我的独立计算 | 一致? | 差异 |
|---|---|---|---|---|
| S1 | 响应 109 条 | `*.response.json` = **109** | ✅ | — |
| S2 | 协议 38 个 | `Protocol` 去重 = **38** | ✅ | — |
| S3 | spec 节点 2 346 / 结构字段 2 093 | 我用独立遍历 spec 树重数 = **2 346 / 2 093** | ✅ | — |
| S4 | map 56 / array 159 / mixed 0 | 重数 = **56（48×int_str + 8×str_slot）/ 159 / 0** | ✅ | — |
| S5 | 玩家数据节点 1 382 / 标量 1 054 / values_vary 430 | 重数 = **1 382 / 1 054 / 430** | ✅ | — |
| S6 | 观测次数分布 1:25 / 2:4 / ≥3:9 | 重数 = **25 / 4 / 9** | ✅ | — |
| S7 | `spec_check.py --all` = 109/109 PASS | 重跑 = **文件 109，PASS 109，FAIL 0，协议 38，WARN 1 878** | ✅ | WARN 全部是「可选键缺失」，无一条 FAIL |

### 2.2 逐节点重新推算（核心）

用 109 条原始 JSON 重算后，与 spec 逐节点比对：

| 判定维度 | 比对数 | 不一致 |
|---|---|---|
| 节点级 `type`（含 int/float→number、null、object、array、map） | 2 258 | **0** |
| `nullable`（是否观测到过 null） | 2 258 | **0** |
| `of`（object 实例数） | 全 object 节点 | **0** |
| `seen` / `parent_instances` / `always` | 1 767 | **0** |
| `fields` 键集合（多键/缺键） | 全 object 节点 | **0** |
| 键序（`top_key_order` + `fields` 顺序） | 38 + 全 object 节点 | **0** |
| `key_count_min/max`（object 与 map） | 全 object/map | **0** |
| `map<int_str>` 键全为数字串 | 48 个 map 节点 | **0**（全部实例键都是 `"1".."29"` 这类数字串） |
| `map<str_slot>` | 8 个 map 节点 | 0 反例；见 §4 说明 |
| 数组 `len_min/len_max/empty_observations/arrays_observed` | 159 个 array | **0** |

> 风险点「把多次观测中值不同误当类型不同」：**未发生**。所有节点跨观测的 JSON 类型集合都收敛为单一类型或 int/float→`number`；`mixed_nodes=0` 成立。
> 风险点「把 `map<int,X>` 当成 array」：**未发生**。159 个 array 节点在原始 JSON 里都是真数组；48 个 `map<int_str>` 节点在所有实例里键全部是纯数字串。

节点账目可对齐：2 346 = **2 258**（逐节点直接比对）+ **42**（从未非空、元素形状无观测的数组 items）+ **8**（`map<str_slot>` 的值节点，改为聚合比对）+ **38**（协议根节点，单独核对 `of`/键序）。

### 2.3 五个高风险点（专项）

| # | 待验结论 | 我的独立计算 | 判定 |
|---|---|---|---|
| H1 | `StaticOpenConditions` 在 109 条里 0 次出现 | 对 109 个文件做全文子串扫描：**0 个文件命中**（相关字段在 1002 里叫 `OpenConditions`，另一个名字） | ✅ 成立 |
| H2 | 5 个基础字段 109/109 | `Protocol / SessionKey / ServerTimeTicks / ServerNotification / RequestId` 各 **109/109** 文件存在 | ✅ 成立 |
| H3 | 学院官方 9 条、缺 14 和 18 | **两个** 24000 响应（`01_`、`96_`）都是 **9** 条，ID = `[1,7,11,12,13,15,16,17,19]`；`AcademyLocationDBSchema` = **11** 条 `[1,7,11,12,13,14,15,16,17,18,19]` → 缺的正是 **14、18** | ✅ 成立（且两份响应数据完全一致） |
| H4 | 初始角色 4 个、ID 为 13010/16003/13003/26000 | `DefaultCharacterExcel` 根向量 **4 行**，slot0 = `[13010, 16003, 13003, 26000]`（顺序即表中顺序）；`ConstCommon.TutorialCharacterDefaultCount`(第 64 个 Add*) = **4** | ✅ 成立 |
| H5 | ShopRecruits 529 / DB 532 / 排除 {1,2,3} | 1017 `ShopRecruits` = **529**（529 个不同 Id，5 000 000–99 999 999）；`ShopRecruitDBSchema` = **532** 行、532 个不同主键；`set(DB)-set(官方)` = **`[1,2,3]`**，`set(官方)-set(DB)` = **`[]`** | ✅ 成立 |

补充独立证据（H5 的「为什么排除」）：用自写解析器直解 3 行 BLOB ——
`Id=1/2/3` 的 **f10 全部 ABSENT**、`f15=f16=79999/19999`、`f9=[5000]/[5000]/[5001]`；
普通 banner `Id=5000000` 的 `f10=5000000`（自身）、`f15=f16=1900000`。与声称的结构差异完全一致。

### 2.4 发现的问题（产出 1）

**E1（唯一实质缺陷，中等）**：42 个数组的 `items.type` 被写成 `"null"`，应为 `"unknown"`。

- 位置：`official_spec.json` 中 `items: {"type": "null", "nullable": false}` 的 42 个数组节点，例如
  `1002.AttendanceBookRewards`、`1002.IssueAlertInfos`、`1002.DailyRecordDBs`、
  `1017.CharacterListResponse.WeaponDBs`、`1017.ContentSweepMultiSweepPresetListResponse.MultiSweepPresetDBs[].ParcelIds`……
- 我的计算：这 42 个数组在 109 条里 `len_max == 0`（从未观测到非空），元素形状确实未知；但 spec 自己 `_meta.legend` 写的是「`unknown`: 只观测到空数组/空对象，元素形状未知」，`_build_array()` 里也有 `type="unknown"` 分支 —— 该分支永远走不到，因为 `Node.merge()` 对空数组也会 `self.items = Node()`。
- 后果：`spec_check.py` 只要遇到这 42 个路径**出现一个元素**，就会报 `FAIL 类型不符: spec=null`。当前的 109/109 PASS 是因为这些数组恰好都是空的，属于**被掩盖的错误**。
- 正确值：`{"type": "unknown", "nullable": false, "note": "never observed a non-empty array"}`。

其余无发现。`109/109 PASS` 本身可复现，但它是「同一批数据既建 spec 又验 spec」的循环论证；真正有信息量的是 §2.2 我用不同实现重算后 **0 处不一致**。

---

## 3. 产出 2：`initial_state_rules.json` 逐条判定

### 3.1 事实表

| # | 声称 | 我的独立计算 | 一致? | 差异 |
|---|---|---|---|---|
| I1 | ExcelDB 398 表 / 707 896 行 / 153 MB | `sqlite_master` 表 **398**、行合计 **707 896**、文件 **153.10 MB** | ✅ | — |
| I2 | 398 表里无 Default/Initial/Start/Newbie 类表 | 模糊匹配只有 `MinigameCCGStartDeck*DBSchema`、`Tutorial*`（是同名子串，不是初始规则表） | ✅ | — |
| I3 | Excel.zip 77 个 `*.bytes` | **77**（含 5 张 `default*` + `constcommon`） | ✅ | — |
| I4 | 6 张规则表尺寸/行数 | 312 B/4 行、112 B/1 行、744 B/25 行、392 B/11 行、176 B/1 行、1 720 B/**191 slot** | ✅ | — |
| I5 | 初始角色 4 个及其星级 | slot0=[13010,16003,13003,26000]；StarGrade slot6=[2,1,2,1]；Level(slot2)=1；FavorRank(slot5)=1；4 个技能 slot(7–10)+Leader(slot11)=1；Exp/FavorExp(**slot3/4**) 4 行均缺省=0 | ✅ | — |
| I6 | 官方侧这 4 人仍在、星级不变 | 1017 `CharacterDBs` 46 条中 4 人齐全，StarGrade **2/1/2/1**，技能等级全 1 | ✅ | — |
| I7 | 初始道具 `ItemId=2 ×5` | `DefaultParcelExcel` 第 8 行 `type=4, id=2, amount=5` | ✅（规则表值） | 证据论证错，见 E3 |
| I8 | 货币 19 行（type=2） | 25 行按 type 分组 = **19 / 1 / 5**（Currency/Item/Emblem） | ✅ | — |
| I9 | 19 行金额 | 逐行核对：1:10000, 3:600, 5:24, 6:3, 7:5, 8:3, 17:3, **18:缺省**, 19:40, 20:40, 21:40, 22:6, 23:6, 24:1, 25:1, 26:1, 27:1, **28:缺省, 29:缺省** | ✅ | 表述错，见 E2/E4 |
| I10 | 未发放的 10 种 = 2,4,9–16 | 19 个 ParcelId 之外的 Id 正是 `{2,4,9,10,11,12,13,14,15,16}` | ✅ | — |
| I11 | 官方 CurrencyDict 29 键且 0 值也在 | 1017 = **29** 键（"1".."29"），其中值为 0 的 **12** 个：`2,6,9,10,11,12,13,14,15,16,28,29` | ✅（数据）/ ❌（"19+10"口径，见 E4） | 需改口径 |
| I12 | 11 项精确命中 | 8:3、17:3、19:40、20:40、21:40、22:6、23:6、24:1、25:1、26:1、27:1 —— **全部命中**；7→4、6→0 也命中 | ✅ | 见 E7 |
| I13 | 初始编队 1 条 | `DefaultEchelonExcel` **1 行**：slot0=1、Leader(slot1)=13010、MainId(slot2)=**int64 向量 [13010,16003,13003]**、SupportId(slot3)=[26000] | ✅ | — |
| I14 | 官方 8 条编队不是初始值 | 1017 = 8 条，类型 `[1#1,2#1,3#1,4#1,6#1,11#1,1#2,1#3]`，与声称完全一致 | ✅ | — |
| I15 | 咖啡厅 2 个、Rank 1、11 件家具 | `CafeInfoDBSchema`=2；1017 `CafeDBs`=2，CafeId=2 的 `CafeRank=1`、家具 UniqueId **恰好 [1..11]**、`LastSummonDate=0001-01-01`；CafeId=1 为 Rank3+14 件 | ✅ | — |
| I16 | 11 件家具的位置/坐标 | 逐行核对 `FurnitureId 1..11`、`Location`、`PositionX/Y`、`Rotation=270.0`（5 号）全部一致；float32 位模式与声称的 8.5/3.0/7.5/9.5/4.5/1.5/270.0/0.5/6.5 一一对应 | ✅ | — |
| I17 | 学院 Rank/Exp 初值 Rank=1/Exp=0 | `AcademyLocationDBSchema` 11 行 slot8 **恒为 1**；表中无 per-location 经验字段 → 推断 Exp=0 | ✅（推断合理） | — |
| I18 | 官方 9 条、缺 14/18 | 见 H3 | ✅ | — |
| I19 | 序章不进 history | `ScenarioHistoryDBs`=191，min=11010，11000/11002 **均不在**；group=21，collection=0 | ✅ | — |
| I20 | TutorialIds 是进度 | 1005 返回 21 条 `[1-14,16,17,19,21,22,23,27]`，与声称逐项一致 | ✅ | — |
| I21 | 提示 `AcademyLocationRankSum=1` 与 24000 的和 14 矛盾 | 实测 Rank 和 = 2+1+1+2+1+1+2+2+2 = **14**；1017 该字段 = **1** | ✅ 矛盾成立 | 解释错，见 E5 |
| I22 | 商店 529/532/排除{1,2,3} | 见 H5；起始年份分布 2023:39 / 2024:131 / 2025:176 / 2026:183 也**逐项命中** | ✅ | — |
| I23 | 特殊行缺 f10、f15/f16=79999/19999 | 自写解析器复核通过 | ✅ | — |
| I24 | MemoryLobby / Emblem / 头像卡 | 1017 `MemoryLobbyDBs`=[{Type 8, UniqueId 13010}]；Emblem 14 条全 Type 20、前 5 个 UniqueId 1..5；`AccountAttachmentDB.EmblemUniqueId=1`；`IdCardDefaultCharacterId=13003`/`BgId=1` | ✅ | — |

**对 `dump_table.py` 本身的独立验证**（它不是可信基准，必须验）：`review/rv_cmp_dump.py` 用它自己的 `decode_bytes_file()` 解 6 张表，再和我自写的 FlatBuffers 解析器逐行逐 slot 对值 —— **351 个 slot 值，0 处差异**（含 4 行 × 12 字段的 `DefaultCharacter`、25 行的 `DefaultParcel`、11 行含 float32 的 `DefaultFurniture`、`DefaultEchelon` 的 `vector<int64> [13010,16003,13003]`）。
只有 ConstCommon 的 **4 个 slot（f1/f45/f47/f48）** 两个解析器分类不同（它读标量、我读向量）；其中 f45 的标量读法 `=3` 与 `BeforehandGachaShopId` 语义吻合，说明它的「整表投票 + 字符串区间重叠校验」比我的判据更稳 —— **该工具在这 6 张表上的输出可信**。

### 3.2 发现的问题（产出 2）

**E2（事实错误，小）**：`q4.initial.note_amount_zero` 说「**1/18/28/29 这 4 行** 没有 ParcelAmount 字段（table size 只有 16 字节）」。
- 实测：只有 **3 行** 是 16 字节表 → ParcelId **18、28、29**；ParcelId **1** 的表是 24 字节，`ParcelAmount=10000`。
- 证据：25 行 table size 分布 = **20 行 × 24 B、2 行 × 30 B、3 行 × 16 B**；16 B 的 3 行正是 ParcelId 18/28/29；`Id=1` 行是 24 B 且 f2=10000。
- 正确表述：「**18/28/29** 这 3 行显式 0；ParcelId 1 是 10000」。
- 影响：`granted` 映射本身是对的（1:10000、18/28/29:0），只有说明文字错。

**E3（证据错误，中）**：`q3.evidence` 第 4 条说「`03_4000_api_item_list.response.json` 与 1017 内嵌的 `ItemListResponse` 都是 null … 该号已把 5 张加速券消耗完」。
- 实测：`03_4000` **根本没有 `ItemListResponse` 这个键**；它的顶层是 `ItemDBs` + `ExpiryItemDBs`，`ItemDBs` **134 条**，其中 `{"Type":4,"UniqueId":2,"StackCount":10}` —— 该号手上有 **10 张**加速券，不是 0。
- 只有 1017 内嵌的 `ItemListResponse` 是 null（键存在、值 null）。
- 影响：结论「初始道具 = ItemId 2 ×5」来自规则表，仍然成立；但「用官方 null 反证已消耗完」这条论据不成立，且事实上与抓包相反。

**E4（口径错误，小）**：任务转述的「初始货币 19 种有值 + 10 种为 0」与数据不符。
- 正确分解：**19 行** ParcelType=2 中，**16 行非零**、**3 行显式 0**（18/28/29）；**10 个 Id 完全不发放**（2/4/9–16）；合计 29。
- 官方账号最终 0 值货币是 **12 个**（含已花光的 6），不是 10 个。
- JSON 里的 `granted`/`zero_by_default` 两个映射本身正确，只是「19 种有值」这句概括错。

**E5（表述错误，中）**：`q8.evidence` 用「1017 内嵌的这些子响应大多是默认值模板」来解释 `AcademyLocationRankSum=1`。
- 实测：**信封**（`Protocol:0 / SessionKey 空 / ServerTimeTicks:0`）确实是默认值，但**同一批子响应的 payload 是真实账号数据** —— `AccountCurrencySyncResponse.CurrencyDict` 1 号 = 28 242 189、3/4 号 = 5 438，`CharacterDBs` 46 条带等级，`CafeDBs` Rank 3。所以「子响应是默认值模板」不成立，只有信封是。
- 影响：「`AcademyLocationRankSum` 不可信、别用」的结论仍成立（它与 24000 的 Rank 和 14 确实冲突），但原因说错了；这属于**未解释的矛盾**，应改写成「该字段与 24000 冲突，语义未知，勿用」。

**E6（置信度偏高，小）**：`q2` 把 `FavoriteCharacter` 判为「只有 13003 = true」。
- `DefaultCharacterExcel` 该行 slot1 的原始 u32 = **257 = 0x0101**（两个相邻字节都是 1），更像「两个 1 字节 bool 字段连排」，不能确定 4 字节里哪一个是 FavoriteCharacter。
- 官方 1017 里 4 个角色的 `IsFavorite` **全部为 false**（含 13003），与该推断冲突。
- 建议：`initial.FavoriteCharacter` 直接标「未确定」，不要给 `{13003: true}`。

**E7（遗漏，小）**：`q4.evidence` 说「剩下的 1/3/5/18 是该号后来赚的」。
- 实测 `CurrencyDict["4"] = 5438`，而 4 也不在发放表里 → 后赚的应是 **1/3/4/5/18**（5 个）。

---

## 4. 无法独立验证的项（诚实列出）

1. **字段名 ↔ slot 的语义映射**。我核对了 `metadata-strings.txt` 里 `Add*` 的实际顺序（DefaultCharacter 12 个 Add* 与声称逐字一致；ConstCommon 191 个 Add*，`PrologueScenarioID01/02` 恰为第 60/61、`TutorialCharacterDefaultCount` 恰为第 64），且 191 个 Add* 与 191 个 slot 数量吻合 —— 但「slot1 = FavoriteCharacter」这类**语义**仍需官方 `.fbs` 或 C# 侧代码才能坐实。
2. **`DefaultCharacterExcel` 是否真在「建号时执行」**。静态表 + `TutorialCharacterDefaultCount=4` + 账号侧 4 人仍在，是三重旁证，不是运行时证据（未连服务器/手机）。
3. **学院为什么是 9 条、14/18 为什么缺**。被复核方自己标「未找到」，我也未找到；两个候选解释都无法从数据闭合。
4. **8 个 `map<str_slot>` 究竟是 protobuf map 还是结构体**。JSON 层不可区分。我测到键集合是稀疏/可变的（`SkillCount` 10 个实例出现 3 种键集；`SkillLevelTable` 12 个实例出现 2 种），**倾向** map，但不能证明。
5. **`ParcelType` 枚举值**（4=Item、20=Emblem、2=Currency）。来自外部情报 + 旁证（14 个 Emblem 全 Type 20、CurrencyDict 29 键 = 29 行），本仓数据无法单独证明。
6. **`is_player_data` 分类**。纯键名启发式（`*DB/*DBs/*ServerId`），没有 ground truth 可比对。
7. **新号是否必须写全 29 个 `CurrencyDict` 键**。1017 是「玩过的号」的形态；规则表只给 19 行。「值为 0 的键也在」是观察，不是规则。
8. **`DefaultMailExcel` 的字段语义**（被复核方已标「未完全解出」）。我独立解出同样的 8 个 slot（f0=1、f1=2701768717、f2=13、f3/f4 日期字符串、f5/f6/f7=[2]/[3]/[1200]），但字段名对不上，无法验证。
9. **spec 的 `nullable=true` 是否有过度声明**。69 个节点观测到过 null，其中 33 个只观测到 1 次；这 33 个的分母都 < 10，无法区分「真可空」与「样本内恰好为空」。**没有**出现「大量观测里只 1 次 null 就标可空」的情况（0 例）。
10. **spec 是否漏掉了 38 个协议之外的真实结构**。超出本次 109 条样本的证据范围。

---

## 5. 复现方式

| 脚本 | 作用 | 关键输出 |
|---|---|---|
| `review/rv_spec.py` | 独立路径聚合 + 逐节点比对 | `rv_spec_out.json`（0 mismatch；42 个 items=null） |
| `review/rv_nullable.py` | nullable / optional 证据强度 | 69 个 null 节点、33 个单次 null、25 个 always=false |
| `review/rv_warn.py` | 复现 spec_check 的 WARN 构成 | 1 878 条全部为「可选键缺失」 |
| `review/rv_fb.py` | 自写 FlatBuffers 解析器（含多数投票） | 6 张 default* 表的逐 slot 值 |
| `review/rv_cmp_dump.py` | 交叉验证 `dump_table.py` 的输出 | 351 个 slot 值 0 差异；4 个 slot 分类分歧 |
| `review/rv_state.py` | ExcelDB SQL + 官方响应事实 | `rv_state_out.json` |
| `review/rv_shop.py` / `rv_shoprow.py` | 商店 Id 差值 + 特殊行 BLOB | 差集 `[1,2,3]`；f10/f15/f16 形状 |
| `review/rv_academy.py` | 学院表 11 行原始 slot | slot8 恒 1；Id 列表 |

原始输出：`_rv_spec_stdout.txt`、`rv_spec_out.json`、`rv_state_out.json`、`_spec_check_result.json`。

---

## 6. 汇总（≤50 行）

1. 复核量：**2 份产出 / 109 条响应 / 38 个协议 / 2 346 个 spec 节点 / 1 767 条字段出现性 / 6 张规则表 / 5 张 ExcelDB 表 / 4 条官方响应**。
2. 用**重写实现**复核（路径聚合 vs 递归累加；自写 FlatBuffers 解析 vs dump_table.py；裸 SQL vs 其封装）。
3. 产出 1 结构事实：**type/nullable/of/seen/parent_instances/always/键集合/键序/数组长度 全部 0 不一致**。
4. 高风险点 1：`StaticOpenConditions` 109 条中 **0** 次 ✅。
5. 高风险点 2：5 个基础字段 **109/109** ✅。
6. 高风险点 3：学院官方 **9**、DB **11**、缺 **14/18** ✅（两份 24000 一致）。
7. 高风险点 4：初始角色 **4** 个 = 13010/16003/13003/26000 ✅，星级 2/1/2/1 ✅。
8. 高风险点 5：ShopRecruits **529** / DB **532** / 差集 **{1,2,3}** ✅。
9. `spec_check --all` 复现：**109/109 PASS**，WARN 1 878 条（全是可选键缺失，无 FAIL）✅。
10. 发现错误 **7 处**：实质数据错误 **0**，表示法缺陷 **1**，证据/表述错误 **5**，置信度问题 **1**。
11. **E1**：spec 里 **42 个数组**的 `items.type="null"`，应为 `"unknown"` —— 这 42 个路径只要将来出现一个元素，`spec_check` 必然 FAIL（当前因全空而未暴露）。
12. **E2**：`q4` 说「1/18/28/29 共 4 行没有 ParcelAmount」→ 实际只有 **18/28/29** 三行；**1 = 10000**。
13. **E3**：`q3` 说「4000 的 ItemListResponse 是 null、5 张加速券已消耗完」→ 4000 **无此键**，有顶层 `ItemDBs` **134 条**，其中 `UniqueId=2, StackCount=10`。
14. **E4**：「19 种有值 + 10 种为 0」→ 实为 **16 非零 + 3 显式零 + 10 未发放**；官方账号 0 值货币是 **12** 个。
15. **E5**：「1017 内嵌子响应是默认值模板」不成立（同批数据含 28 242 189 信用点、46 角色、CafeRank 3）；`AcademyLocationRankSum=1` 与 24000 的 14 冲突**仍未解释**。
16. **E6**：`FavoriteCharacter` 只凭 `0x0101` 判 13003=true，与官方 `IsFavorite=false` 冲突，应标未确定。
17. **E7**：「后来赚的」漏了货币 **4 = 5438**。
18. §3.1 的 24 条事实（I1–I24）中，除 E2/E3/E4/E5 涉及的 4 条外全部逐项复现、数值精确一致，含 11 项「精确命中」的货币值。
19. 无法独立验证 **10 项**，主要是字段名语义、`map<str_slot>` 真伪、学院 14/18 原因、`is_player_data` 分类、邮件字段语义。
20. 建议：产出 1 修 E1（一行代码：`items` 为 None 时显式写 `unknown`）；产出 2 修 E2/E3/E5/E6/E7 的文字与置信度，数据本身不用动。
