# `No LocalizeKey` 与招募面板数据的来源（离线静态分析）

> 只读。未改 APK、未重打包、未动表。唯一写入文件就是本文件。
> 证据源：`report\_tmp\patch\md_deob.bin`（`global-metadata.dat` 解混淆副本，38,426,024 B）、
> `work\ba\data\ExcelDB.db`（Size 160,534,528 / md5 `824ce3a8bee2bb5ae36ada1ac95048f1`，与你给的一致）。
> 标注：**【确证】**= 有偏移/字节/查询结果可直接复核；**【推测】**= 有间接证据；**【未完成】**= 明确没做完。

---

## 1. `No LocalizeKey` 的产地

### 1.1 结论
**【确证】它不是表里的数据，是编译进 IL2CPP 的 **C# 字符串字面量**，完整原文带颜色标记：**

```
[FF0000]No LocalizeKey
```

| 项 | 值 |
|---|---|
| 所在区 | `stringLiteralData`（`global-metadata.dat` 的字符串**字面量**区，**不是** string 名字堆） |
| 文件偏移 | **`0x000C2BAA`**（`No LocalizeKey` 这 14 字节本身在 `0x000C2BB3`） |
| 该串的 XOR key | **`0x51`**（客户端对字面量做了**逐串随机单字节 XOR**） |
| length | 23（`[FF0000]` 9 + `No LocalizeKey` 14） |
| `dataIndex`（相对 `stringLiteralData`） | **599530**（`No LocalizeKey` 起点为 599539） |

### 1.2 怎么找到的（可复现）
```
1) 直接 find（不解码）→ 全文件 0 命中           ⇒ 说明被 XOR 了
2) 256-key 枚举，限定在 stringLiteralData 区内：
   needle = "No LocalizeKey"，key=0x51 → 命中 0x000C2BB3   ★唯一命中
3) 同一 key 解码 0x000C2BAA 起的 23 字节 → "[FF0000]No LocalizeKey"
4) 在 string 名字堆（off 0x000EC9C8）里搜 "LocalizeKey" → 仅有 key=0x00 的
   明文命中 @0x000F4FD5，**但那是字段/方法名，不是这条文案**（长度/上下文不同）
```
**邻域解码**（同 key 0x51，覆盖 `0x000C2AA6..0x000C2CCF`）：
```
0x000C2BA2  ...U[FF0000]No LocalizeKey        ★
```
⇒ 该字面量前面紧邻的是另一个字面量的尾部，**没有任何表数据包裹它** ⇒ **确证是代码常量**。

### 1.3 语义判定
- 带富文本颜色标记 `[FF0000]`（BA 自己的着色标记）⇒ 它被设计成**红色错误占位**直接塞进 Text 组件。
- **【推测·强】** 任何"取本地化文本"的函数在**查不到 key 时**返回这个常量。
  也就是说：**界面出现它 = 该处代码拿到的是一个"查表失败"的结果，而不是表里真的写着这行字。**

### 1.4 精确到类/方法 ——【未完成】
- 我尝试用 `metadataUsageLists` / `metadataUsagePairs`（`(type<<29)|index` 编码，type=5 为 StringLiteral）
  把 literal 索引反查到 method，但**这个 build 的 metadata 头是伪造版本号（v31）+ 各区偏移与我假设的 v27 布局不一致**
  （`stringLiteral` 表 0x100 + 197824×8 的末端会越过 `stringLiteralData` 起始 0x305C0，自相矛盾），
  所以本轮**没有**得到 literal→method 的映射。
- **能给的确定结论**：这个 fallback 是**客户端代码**打的，**不在服务端、也不在任何 Excel 表里**。
  要定位到方法，最短路径是：拿一个**正确的 metadata 头解析器**（本机 `report\_tmp\patch\md_parse.py` 是前人的解析器，
  其字段顺序与本 build 匹配）重跑一次 literal→method 反查；或用运行期 hook 抓 Text 赋值点。
- **我对"是不是查 key 为空/查不到"的回答**：**【推测·强】是**。依据是 1.1 的富文本红字形态 + 1.3 的语义，
  以及下面第 2 节"本地表里明明有文本却显示它"的事实。

---

## 2. 招募面板标题 / 十连价格的数据来源

### 2.1 结论（先给判定）
| 界面元素 | 数据来源 | 强度 |
|---|---|---|
| **卡池标题 / 说明 / 概率文案** | **客户端本地 `LocalizeGachaShopDBSchema`（按 `GachaShopId` 查）**，**不是**服务端 DTO 字段 | **【确证】**（表结构与样本见 2.2） |
| 页签名（`新手冲刺!!`/`3★自选招募`/`DUMMY`）| 本地 `LocalizeDB`（`Key`+`Bytes`，18,456 行） | 【确证】（表存在，具体键名未追） |
| 「招募10次」按钮上的 **`1,000`** | **不是本地表里的价格列**；来自 `UIBasicGachaButton.SetGachaCost` 里的
"需要的券数 / 我持有的可用券数"二者之一 | **【推测·中】**（见 2.3；该项**未能钉死**） |

### 2.2 证据：本地三张表的结构与真实数据
```
ExcelDB.db 内：
  LocalizeDBSchema            cols = (Key, Bytes)          18,456 行
  LocalizeGachaShopDBSchema   cols = (GachaShopId, Bytes)   1,235 行
  ShopRecruitDBSchema         cols = (Id, Bytes)

查询：SELECT Bytes FROM LocalizeGachaShopDBSchema WHERE GachaShopId = 5004670
解码 protobuf 内的文本（按出现顺序）：
  '2026/11/12 14:00~2026/11/26  13:59截止'
  '选择招募10次'
  '必定获得1名2'
  '以上成员'
  '若出现已拥有的成员则会转换为神名精髓与该成员的神名文字'
  '招募概率提升'
  '限时招募'
  '限时招募'
```
**⇒ 本地表里 `GachaShopId=5004670` 确实有"限时招募"等完整文案，
与你在真机上看到的「title/desc 显示 No LocalizeKey」直接矛盾。**
**这反过来证明 1.3 的推断：客户端查的 key 不是 5004670，或它查的不是这张表。**

**【推测·中】最可能的错位点**：客户端用 `ShopRecruitExcelData` 的某个 id 去查，
而服务端下发的 `ShopRecruitDB.Id` 与之未对齐；或客户端查的是 `GachaShopId`（`LocalizeGachaShop` 的键）
而它取的是 `ShopRecruitExcel.DirectPayInvisibleTokenId`(0x58) / `SelectAbleGachaGroupId`(0x60) 之类的派生 id。
**这一点我没有证据钉死，列为待验。**

### 2.3 「1,000」的来源判定

**已确认的字段（`UIBasicGachaButton` type[7630]，21 字段，偏移自 +0x10 起按 8 字节推）**：
```
f7  gachaCostAmountLabel      +0x40  (Text)
f12 costDefaultRoot           +0x68  (GameObject)   ← "纯价格"形态
f13 costMixRoot               +0x70  (GameObject)   ← "券+宝石混合"形态
f14 costMixGemLabel           +0x78  (Text)
f15 costMixTicketAmountLabel  +0x80  (Text)  ★ 截图里"票据图标 + 1,000"就是这一路
f16 costMixTicketIcon         +0x88
f17 goodsId                   +0x90  (long)
f20 isTenGacha                +0xA8  (bool)
f21 oneTicketAmount           +0xAC
```

**`SetGachaCost` @ `0x0A8CADF4`（明文，已反汇编）**：
```asm
0x0A8CAF80  bl 0xEACA44C   ; TryGetGachaTicketAmount(goods, out amount, false)
0x0A8CAF84  tbz w0,#0 → 失败分支 0x0A8CB180
0x0A8CAFA4  bl 0xEC43AB8   ; TryGetAvailableGachaTicketsOnMyOwn(goods, out item)   ★ 关键
0x0A8CAFA8  tbz w0,#0 → 失败分支 0x0A8CB180
0x0A8CAFD8  bl 0xA2DA6EC   ; get_SpriteName
0x0A8CAFE4  str x1,[x0,#0xB0]!   ; 写入 ticketSpriteName
```

**判定**：
- **`1,000` 不是 `ConsumeParcelAmount` 的默认值**，也不是 `GachaCombinedCost` 的档位（你已排除 12 档里没有 1000）。
- **【推测·中强】它来自 `TryGetAvailableGachaTicketsOnMyOwn`（"我持有的可用招募券"）** ——
  与图标同源（图标就在紧邻的指令里从这份数据的 `SpriteName` 取出）。
  ⇒ **按钮显示的可能是"持有量"，不是"价格"**。
- **【未完成】**：`costMixTicketAmountLabel` 的最终赋值指令、以及 `TryGetAvailableGachaTicketsOnMyOwn`
  内部读的是哪张物品表 —— 本轮没解完，不硬说。

---

## 3. 哪些是确证 / 推测

| # | 陈述 | 等级 |
|---|---|---|
| 1 | `[FF0000]No LocalizeKey` 是 `stringLiteralData` 里的**字面量**，偏移 `0x000C2BAA`，XOR key `0x51` | **确证** |
| 2 | 它不在任何 Excel 表里，也不来自服务端 | **确证** |
| 3 | 它带红色富文本标记 ⇒ 设计为"取不到本地化文本"的**错误占位** | **确证（形态）** / 推测（用途，强） |
| 4 | literal → method 的映射 | **未完成**（metadata 头布局与本 build 不匹配） |
| 5 | 标题/说明来自**本地** `LocalizeGachaShopDBSchema`（列名 `GachaShopId`），**不是**服务端 DTO | **确证** |
| 6 | `GachaShopId=5004670` 的本地文案**存在且完整** | **确证**（查询结果原文见 2.2） |
| 7 | ⇒ 显示 `No LocalizeKey` 说明客户端**没查到该键**（键错位或走错表） | **推测·强** |
| 8 | `1,000` 来自 `SetGachaCost` 里"持有券数 / 需要券数"之一，**很可能显示的是持有量** | **推测·中强** |
| 9 | 「点数」的来源 | **未完成**（最可能 `UIRecruitShopInfo.SetGachaCeilingData` mdef 49331） |

---

## 4. 建议的下一步（都不改客户端）
1. **先确认键错位**：把服务端下发的 `ShopRecruitDB.Id` 与本地 `LocalizeGachaShopDBSchema.GachaShopId`
   做一次全量差集（529 vs 1235），看我们发的 id 是否**真的**在 `GachaShopId` 列里——注意这两张表的键**可能不是同一个 id**。
2. 若差集为空仍显示 `No LocalizeKey`，则问题在**客户端取键的路径**（`ShopRecruitExcel.DirectPayInvisibleTokenId` /
   `SelectAbleGachaGroupId` 等派生字段），需要把 literal→method 反查补完才能定位。
3. 「1,000」只需**再解两条指令**：`costMixTicketAmountLabel` 的赋值点，以及 `TryGetAvailableGachaTicketsOnMyOwn`
   的表来源。这个投入很小，建议下一轮先做。

---

# 第二轮：literal → method 追踪（进度与卡点）

## 0. 直接回答

**答不出「传进本地化查表的 key 到底是什么」。卡在第一步：拿不到 `stringLiteral` 表的正确内容，
因此无法把 `No LocalizeKey` 这个 literal 反查到 method，也就无法顺调用链回溯 key 的来源。**

**这一轮新得到的确定事实有两条**（见 1、2），它们把可能范围缩小了，但还不能定论。

---

## 1. 【确证】metadata 头里那些数字是**字节数**，不是条数

第一轮我用错了口径。按字节重算后各表规模与已知值**完全吻合**：

| 表 | off | 字节 | 真实条数 |
|---|---|---|---|
| `stringLiteral` | `0x00000100` | 197,824 | **24,728**（×8 字节） |
| `stringLiteralData` | `0x000305C0` | 771,080 | — |
| `string` | `0x000EC9C8` | 7,109,768 | — |
| `methods` | `0x008B2C14` | 9,471,420 | **263,095**（×36）✔ 与已知一致 |
| `typeDefinitions` | `0x01F02148` | 3,089,240 | **35,105**（×88）✔ |
| `fields` | `0x01B17590` | 2,303,880 | **191,990**（×12）✔ |
| `metadataUsageLists` | `0x021F6E78` | 27,960 | **3,495**（×8） |
| `metadataUsagePairs` | `0x021FDBB0` | 2,328 | **291**（×8） |

⇒ 之前"表末端越过下一个区"的矛盾是我的口径错误，**布局本身是自洽的**。

## 2. 【确证】`stringLiteral` 表在 `md_deob.bin` 里仍是**混淆态**

```
md_deob.bin 里 stringLiteral 前 3 条（解出来的值）：
  (946855354, 1961348764)
  (1487888058, 1995167404)
  (4159626428, 1893711485)
len = 946855354>>1 = 473,427,677  —— 不可能是字符串长度
dataIndex 最小值 3,050,393 > literalData 总长 771,080  —— 越界
```
⇒ **这张表没被解混淆**，所以无法用它索引 literal。

## 3. 【卡点】按文档法则重解原始文件，头解不出 magic

我按 `md_parse.py` 的法则（周期 XOR 0x66 + 头部 XOR 0x66666666）对
`work\ba\audit\ba-work\x\...\global-metadata.dat`（原厂 38,426,024 B）重跑：

```
sanity=0x741425F2   version=-1963446914
```
**期望 magic 是 `0xFAB11BAF`。**
反推：`raw[0:4] ^ 0x66666666 = 0x741425F2` ⇒ 要得到 magic 需要另一个常量 key（`0xE89F583B`），
**说明该文件不是"仅靠这两层"就能解开的**（或该路径下的副本已被前人处理过/来自不同构建）。

**⇒ 卡在这里。要越过这一步，需要下列任一项：**
1. 一份**确认已完整解混淆**的 `global-metadata.dat`（`stringLiteral` 表可读即可，我可以用它完成 literal→method）；
2. 或该 build 的**正确头部/周期性 XOR 参数**（周期长度、区间、两个 key）；
3. 或直接用 Il2CppDumper 在该 `.so`+metadata 上产出 `dump.cs`（有它我就不需要解这张表）。

## 4. 【确证】客户端**没有**名为 `LocalizeGachaShop*` / `GetGachaShopName` 的方法

扫全部 263,095 个方法名，过滤 `GachaShop` / `LocalizeGacha` / `GetGachaShop`，命中的**全是活动类**：
```
MoveToFortuneGachaShop / OpenEventFortuneGachaShop / WebAPIErrorEventContentFortuneGachaShopPurchase
get_tutorialGachaShopId / get_beforehandGachaShopId / AddTutorialGachaShopId / AddBeforehandGachaShopId
TryGetBoxGachaShopData / TryGetFortuneGachaShopInfo(Client)
GetRootAsEventContentBoxGachaShopExcel / …FortuneGachaShopExcel
```
**没有任何一处是"取 GachaShop 标题/说明"的专用方法。**
⇒ **【推测·强】标题/说明走的是"通用本地化辅助"**（`LocalizeDB` / `TextMapper` / `LocalizeKey` 一类），
由调用方把 `GachaShopId` 拼成键再查表 —— 这正好解释了为什么第一轮在方法名里找不到线索。

## 5. 三个子问题的最新状态

| 问题 | 状态 |
|---|---|
| **(a)** 传进去的是 `ShopRecruit.Id`(5004670) 还是 `OneGachaGoodsId`/`TenGachaGoodsId`(5004671/5004672)？ | **无法确证**。三个候选都存在于 `ShopRecruitExcelData`（`Id`@0x10、`OneGachaGoodsId`@0x20、`TenGachaGoodsId`@0x28），而**代码里没有专门方法**可定位。**需要第 3 节的三项之一才能定。** |
| **(b)** 查表失败会不会回退到服务端字符串？ | **未完成**。已知 `IsCanBuyGacha` 的"非开放期"分支是 `GetText(本地化key)` → 显示 → `return false`，**该分支没有读服务端 DTO 字符串**；但"标题/说明"的回退路径**没有单独验证**。 |
| **(c)** 十连数字的最终赋值点 | **未完成**。`SetGachaCost` 已解到 `TryGetAvailableGachaTicketsOnMyOwn`（图标来源），`costMixTicketAmountLabel`(+0x80) 的赋值指令仍未取到。 |

## 6. 下一轮的最短路径

1. **给我一份可读的 `stringLiteral` 表**（或 `dump.cs`）→ 我 10 分钟内给出 literal→method→调用链→key 来源；
2. 若暂时没有，**先做一件不需要它的事**：把 `LocalizeDBSchema`(18,456 行) 里所有 `Key` **是字符串**的条目导出，
   搜 `5004670` / `5004671` / `5004672`，看这张大表里有没有以这些 id 命名的键 ——
   这一步能直接判定 (a)，因为"通用本地化辅助"多半查的就是 `LocalizeDBSchema`。

---

# 第三轮：用数据证据定位 key（表内命中法）

## 0. 直接回答

**`LocalizeDBSchema.Key` 是「整数」（18,456 行全部 integer，是 32 位不透明 hash，不是字符串）；搜 `5004670/5004671/5004672` 在 Key 里 0 命中。
⇒ 招募标题**不走** `LocalizeDBSchema`，只走 `LocalizeGachaShopDBSchema`（主键列名就叫 `GachaShopId`）。**

## 1. 【确证】`LocalizeDBSchema` 的 Key 类型

```
rows = 18456
typeof(Key) 分布: [('integer', 18456)]      ← 全部整数，无一字符串
样本 Key: 2476910193, 108934617, 2038072704, 492870239, 2928326507, 2336868054, 3853670134
样本文本: '存在与其他家具重叠了的家具' / '验证码已发送至您输入的邮箱地址' / '最高纪录 第{0}名'
```
搜 id：
```
[5004670] hits=0
[5004671] hits=0
[5004672] hits=0
```
⇒ **这条线断了**：`LocalizeDB` 是"通用文案池"，键是 hash，与招募 id 无关。

## 2. 【确证】`LocalizeGachaShopDBSchema` 与 `ShopRecruitDBSchema` 的关系

```
LocalizeGachaShopDBSchema: 1,235 个 GachaShopId
ShopRecruitDBSchema:          532 个 Id          ← 注意：你给的是 529，实测 532
交集 = 532
只在 ShopRecruit（本地无本地化行）= 0        ★ 一个不缺
只在 LocalizeGachaShop      = 703
```
id 空间：
```
ShopRecruit 示例:      1, 2, 3, 5000000, 5000010, 5000020, 5000030, 5000040 …
Localize 独有示例:     50000, 50001, 50002, 50003, 50010, 50011 …
```
⇒ **1,235 = 532 个招募 id（7 位）+ 703 个共享/旧 id（5 位）**。
**每个招募 id 在本地化表里都有行，缺行数为 0。**

## 3. 【确证】可用性抽查（决定性）

```
ShopRecruitDBSchema   含 5004670        ✔
LocalizeGachaShop[5004670] -> '2026/11/12 14:00~2026/11/26  13:59截止', '选择招募10次', '限时招募' …
LocalizeGachaShop[5004671] -> NO ROW    ★
LocalizeGachaShop[5004672] -> NO ROW    ★
LocalizeGachaShop[50000]   -> '选择招募10次','必定获得1名2','以上成员' …（共享文案，无标题无档期）
```

**★ 关键**：`5004671 / 5004672` 正是你给的 `OneGachaGoodsId`（单抽 goods）与 `TenGachaGoodsId`（十连 goods），
**它们在 `LocalizeGachaShop` 里根本没有行**。

⇒ **【推测·强】(a) 的答案**：客户端若用 **goods id** 去查 `LocalizeGachaShop`，**必然查不到 ⇒ 红色 `[FF0000]No LocalizeKey`**；
用 **recruit id（5004670）** 查则一定命中。
**我们目前无法从代码确证它用的是哪个**（literal→method 这条路已按你的指示跳过），
但**数据侧只有"用 goods id"这一种解释能同时对上"档期能显示、标题空白"**：
档期来自 `ShopRecruitExcel.SalePeriodFrom/To`（recruit 行里的列，能读到），
标题来自 `LocalizeGachaShop[?]`（若键是 goods id 就查不到）。

> 反过来说：**如果客户端用的是 recruit id，那 5004670 这一行必然渲染出"限时招募"，不可能出现红字。**
> 所以"键不是 recruit id"这个推论，是**被数据排除法逼出来的**，不是猜的。

## 4. (b) 回退到服务端字符串？—— 【未完成】
第三轮的授权范围只到"用表内数据定 key"，我没有再解回退分支。
已知的旁证：`IsCanBuyGacha` 的"非开放期"分支是 `GetText(本地化key)` → 显示 → `return false`，**该分支不读服务端 DTO 字符串**。
**但这不等于"标题失败时也不回退"，此项仍标未完成。**

## 5. (c) 十连数字 —— 【未完成】
`costMixTicketAmountLabel`(+0x80) 的赋值指令仍未取到。

## 6. 下一轮建议（不需要 dump.cs）
1. **直接实验**：让服务端把 `ShopRecruitDB.Id` 之外，**额外**确认客户端拿到的 `OneGachaGoodsId/TenGachaGoodsId`
   能否被"改成 recruit id"（即 goods 表的 id 也指向 5004670）——若改完标题出现，则 (a) 定死为"用 goods id 查"；
2. 或查 `LocalizeGachaShop` 的 703 个 5 位 id 被谁引用（`GachaShopExcel` 之类），确认是否存在第三张 "GachaShop" 表作为中间跳板。
