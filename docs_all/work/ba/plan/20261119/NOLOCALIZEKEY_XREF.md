# `[FF0000]No LocalizeKey` 的调用点定位与 key 来源（离线只读静态分析）

> 只读分析。未改 APK、未重打包、未动服务端、未改任何既有文件；本轮**只新增**：
> `work\ba\scripts\xref_nolocalizekey.py`、`work\ba\scripts\md_bridge.py`、`work\ba\scripts\q_localize_slots.py`、
> 以及本报告。
> 标注：**【确证】**= 有地址/字节/指令/查询结果可直接复核；**【推测】**= 有间接证据；**【未完成】**= 明确没做完。

---

## 0. 一句话结论

**任务指定的「字符串 xref」路线在本 build 上结构性不可行**：`[FF0000]No LocalizeKey`
**根本不在 `libil2cpp.so` 里**（明文 / 任意单字节 XOR 全长扫描均 0 命中，见 §1），
因为 IL2CPP 的 C# 字符串字面量只存在于 `global-metadata.dat`。

**改走 metadata↔code 桥（前人 `ba_ptrs.bin`）后，我拿到了完整调用链【确证】：**

```
UIGachaInfo.SetData                         @0x0A8CF08C   (mdef 49273)  ← 招募面板
  └ ShopRecruitExcel::get_Id()              @0x0AB17608   (mdef 128831) ← key 的来源字段
  └ ShopData::GetGachaTitleNameString(int)  @0x0EAC90D4   (mdef 108284) ← 真正“拼/查”的地方
  └ ShopData::GetGachaSubTitleString(int)   @0x0EAC92E0   (mdef 108285)
  └ ShopData::GetGachaDescriptionString(int)@0x0EAC94EC   (mdef 108286)
       └ 用该 int 去查字典 localizeGachaShopDic（LocalizeGachaShopDB，键=GachaShopId）
       └ 读 TitleNameKr(语言0) / TitleNameJp(语言1)
       └ 查不到 / 语言∉{0,1} / 该列 IsNullOrEmpty → 返回一个**静态字面量常量**
```

即：**面板传给查表的 key 就是 `ShopRecruit.Id`**（不是别的字段算出来的），
**查的表是 `LocalizeGachaShopDB`，其主键是 `GachaShopId`** —— 两侧是不同的 id 空间，
这是本轮唯一被代码直接证实的不匹配点（**与任务给的「key 不是 ShopRecruit.Id」前提相反**，见 §5.2）。

另有一条**新手专属分支**用的是**纯常量字符串 key**（不经任何字段），见 §4.2 ——
如果出问题的是「新手冲刺!!」那个卡池，那走的就是这条分支，和任务前提才对得上。

---

## 1. `.so` 里到底有没有这个字面量：**没有**（确证，这是本轮最重要的负结果）

### 1.1 ELF 段布局（先 dump 头，不整读文件）

```
py work\ba\scripts\xref_nolocalizekey.py layout <libil2cpp.so>
```

```
size : 270927056 (0x102604D0)     ELF64 / little-endian / EM_AARCH64(183) / ET_DYN
phoff=0x40 phnum=14   shoff=0x1025FE90 shnum=25

--- Section Headers（关键项）---
name                   type  addr(va)       offset         size
.rodata                1     0x00263E2C0    0x00263E2C0    0x119D699   ( 18.4 MB)
.text                  1     0x0059B8000    0x0059B8000    0x0B09260   ( 11.6 MB, 运行时/引擎代码)
il2cpp                 1     0x0064C1260    0x0064C1260    0x8DFEDAC   (148.8 MB, IL2CPP 生成代码)
.data.rel.ro           1     0x00F2C4000    0x00F2C4000    0x076BA78
.got                   1     0x00FA2FD18    0x00FA2FD18    0x017F948
.data                  1     0x00FBB4000    0x00FBB4000    0x06974F8
```

- 注意：真正的 IL2CPP 方法代码在**名为 `il2cpp` 的段**（0x64C1260 起，148 MB），不是 `.text`。
  只扫 `.text` 会漏掉 92% 的代码。
- PT_LOAD#2（off 0x59B8000 / va 0x59B8000 / filesz 0x990A410）覆盖 0x59B8000–0xF2C8410，
  **该区间内 文件偏移 == 虚拟地址**，所以下文地址既当 VA 也当 file offset 用。

### 1.2 三种搜法 + 256 键全扫，**全部 0 命中**

```
py ...\xref_nolocalizekey.py find  <so> --text "[FF0000]No LocalizeKey"      → hits=0
py ...\xref_nolocalizekey.py find  <so> --text "No LocalizeKey" --xor 0x51   → hits=0（含 utf16le 变体）
py ...\xref_nolocalizekey.py sweep <so> --text "No LocalizeKey"              → total_hits=0  (keys 0x00..0xFF)
py ...\xref_nolocalizekey.py sweep <so> --text "[FF0000]No LocalizeKey"      → total_hits=0  (keys 0x00..0xFF)
```

`sweep` 是对 256 个单字节 XOR key 各做一次全长扫描（明文 `0x00` 也算在内），
覆盖全部 PT_LOAD 的**文件字节**（270,927,056 B 全扫）。

### 1.3 结论与推论

- **【确证】`libil2cpp.so` 里不存在该字面量**：明文没有，被任意单字节 XOR 混淆的形态也没有。
  所以「在 `.rodata`（或 `.text`/`il2cpp`）里找到该串 → ADRP+ADD 反查」这条路**从第一步就无输入**。
- **【确证】原因**：Unity IL2CPP 把所有 C# 字符串字面量放在 **`global-metadata.dat` 的
  `stringLiteralData`** 区，`.so` 里只留「取第 N 号字面量」的代码，不含字节本身。
  `xref_nolocalizekey.py` 里的 ADRP+ADD / ADRP+LDR / ADR / 8 字节指针池扫描器**已经写好并可用**
  （`xref --va 0x...`），但对这个串**没有可指向的目标地址**，所以本轮命中数必然是 0。
- **等价替代**：这个字面量在运行时的「地址」其实是**一个静态槽**：
  代码里成对出现 `adrp x8,#0xFB12000 / ldr x8,[x8,#0x380] / ldr x1,[x8]`，
  即 `x1 = *(*(0x0FB12380))`。`0x0FB12380` 在 `.got` 里。这也解释了为什么静态搜不到明文。

> 交付要求里的「所有 xref 命中」：**0 条**（有 §1.2 的四条命令可复核）。
> 下面 §3 给出**等价的、有意义的 xref**：调用点的真实地址与指令字节。

---

## 2. 绕开字符串的替代路线（我实际用的）

### 2.1 前人产物：metadata ↔ 代码地址 的桥

`report\_tmp\patch\` 里已有：

| 文件 | 内容 |
|---|---|
| `md_deob.bin` (38,426,024 B) | `global-metadata.dat` 解混淆副本 |
| `ba_ptrs.bin` (154,173×8 B) | **方法指针表**：由 `.rela.dyn` 的 `R_AARCH64_RELATIVE(1027)` 重定位还原，`methodPointers[mdef] = 代码地址` |

我用 `ig5`/Ghidra 之外的方式（自己写解析 + capstone）复用了它：
`work\ba\scripts\md_bridge.py` 提供
`hdr / litstat / lit / blobkey / type / types / ms / mdef / va / litref / callers`。

**校验【确证】**：`work\ba\audit\ba-work\x\lib\arm64-v8a\libil2cpp.so` 与
`work\ba\audit\ba-apk\lib\arm64-v8a\libil2cpp.so` **MD5 完全相同**
（`D513F8F973B129368DDEC89491A8A9DA`，270,927,056 B），所以这张表对本 `.so` 有效。

### 2.2 一个有用的新发现：metadata 头的 count 是**字节数**

```
py work\ba\scripts\md_bridge.py hdr
```
```
stringLiteral      0x00000100   0x000304C0 (197824)
stringLiteralData  0x000305C0   0x000BC408 (771080)
string             0x000EC9C8   0x006C7C88 (7109768)
...
contiguity: literal end=0x305C0  literalData start=0x305C0  literalData end=0xEC9C8  string start=0xEC9C8
```

- 0x100 + 0x304C0 = 0x305C0（正好等于 `stringLiteralData` 起点）；0x305C0 + 0xBC408 = 0xEC9C8（正好等于 `string` 起点）。
  **首尾相接、完全自洽** ⇒ 这个头不是"伪造"，而是**把 count 写成了字节数**。
  于是 `stringLiteral` 表 = **[0x100, 0x305C0) 共 24,728 条 × 8B**，`stringLiteralData` = 771,080 B。
- 这也纠正了 `NOLOCALIZEKEY_ORIGIN.md` 里「197824 条 × 8B 会越界」的误判（那是把字节数当条数了）。
  `dataIndex=599530 < 771080` **没有越界**，反而正好落在区内（0x305C0+599530 = 0xC2BAA ✅ 与给定事实吻合）。

### 2.3 但 `stringLiteral` 表条目本身仍是混淆态 ——**【确证】且【未完成】**

```
py work\ba\scripts\md_bridge.py litstat
```
```
entries=24728  plausible=0  implausible=24728
first 8 raw entries (index: len, dataIndex):
  0  1876675492  1959714884
  1  1485508696  1994913964
  ...
```

按 `{u32 length, u32 dataIndex}` 解，**24,728 条没有一条是合法值**（length 全是 10 位数）。
原始 `global-metadata.dat` 同位置字节是 `DC BB 09 5E FA A8 81 12 ...`，
`md_deob.bin` 是 `BA DD 6F 38 ...`（差 `0x66666666`，即页/头 XOR 已去，但表另有混淆）。

⇒ **拿不到「这条字面量的 literal index」**，所以 `litref --index N` 那条路（按立即数找代码）本轮走不通。
**这一条我没有绕过去，明确记【未完成】。** 但它不再必要：用 §2.1 的桥可以直接按**方法名 + 地址**定位。

> 附带结论【确证】：`[FF0000]No LocalizeKey` 的内容在 `stringLiteralData` 里是**逐串随机单字节 XOR**。
> 我对字面量区按 4 KB 页做「单一 key 可打印率」扫描，前 24 页最优 key 各不相同
> （0x9D/0xEF/0x20/0xEF/0xBE/… 得分仅 0.42–0.75），**不存在页级统一 key**
> ⇒ 想批量解密整块字面量区必须先拿到「每串的 key」，本轮做不到。

---

## 3. 真正的调用链（确证，逐指令）

### 3.1 面板：`UIGachaInfo.SetData` —— 招募界面标题/副标题/说明的三个赋值点

`UIGachaInfo`（type idx 7635）字段：
`freeRemainCountLabel, freeRemainCountObj, periodScaleObject, periodLabel, gachaTitleLabel,
gachaSubitleLabel, gachaDescriptionLabel, pickupFirstGetRootTransform, pickupFirstGetLabel, excel`

`SetData` @ **0x0A8CF08C**（mdef 49273）。函数尾部的三段是**决定性证据**：

```
; ---- 标题 ----
0x0A8CF9E8  ldr  x22,[x19,#0x38]        ; 761e40f9  x22 = gachaSubitleLabel? (见下注)
0x0A8CF9FC  bl   0x06FB352C             ; cc8e1b97  取 ShopData 单例
0x0A8CFA0C  bl   0x0AB17608             ; ff1e0994  MX.Data.Excel.ShopRecruitExcel::get_Id()   ★ key 来源
0x0A8CFA14  mov  x1,x0                  ; e10300aa
0x0A8CFA20  bl   0x0EAC90D4             ; ade50795  MX.Data.ShopData::GetGachaTitleNameString(id)
0x0A8CFA34  bl   0x0E63717C             ; d29df594  UILabel::set_text(this+0x38, ret)

; ---- 副标题 ----
0x0A8CFA50  bl   0x0AB17608             ; ee1e0994  ShopRecruitExcel::get_Id()                  ★
0x0A8CFA64  bl   0x0EAC92E0             ; 1fe60795  ShopData::GetGachaSubTitleString(id)
0x0A8CFA78  bl   0x0E63717C             ; c19df594  UILabel::set_text(this+0x40, ret)

; ---- 说明 ----
0x0A8CFA94  bl   0x0AB17608             ; dd1e0994  ShopRecruitExcel::get_Id()                  ★
0x0A8CFAA8  bl   0x0EAC94EC             ; 91e60795  ShopData::GetGachaDescriptionString(id)
0x0A8CFABC  bl   0x0E63717C             ; b09df594  UILabel::set_text(this+0x48, ret)
```

- 目标方法名是**直接解析出来的**（不是猜的）：
  `get_Id`=mdef 128831 @0x0AB17608；`GetGachaTitleNameString`=mdef 108284 @0x0EAC90D4；
  `GetGachaSubTitleString`=mdef 108285 @0x0EAC92E0；`GetGachaDescriptionString`=mdef 108286 @0x0EAC94EC；
  `UILabel::set_text`=mdef 2157 @0x0E63717C。
- **【确证】key 的来源字段 = `MX.Data.Excel.ShopRecruitExcel::get_Id`**，三处调用点分别是
  0x0A8CFA0C / 0x0A8CFA4C / 0x0A8CFA94，取到的 int 直接作为 x1 传下去，**中间没有任何字符串拼接**。
- 注：字段基址 0x10 起算，`+0x38/+0x40/+0x48` 依次对应 gachaSubitleLabel / gachaDescriptionLabel / 下一字段；
  `+0x30`（gachaTitleLabel 候选）在**新手分支**里被赋值（§4.2）。字段→偏移的严格对应关系记为**【推测·强】**
  （metadata 未给出字段偏移，是按字段声明顺序 + 8 字节对齐推的）。

### 3.2 key 怎么被"查"：`ShopData.GetGachaTitleNameString` 逐指令

```
0x0EAC9184  ldr  x0,[x20,#0x120]        ; 809240f9  x0 = this.localizeGachaShopDic  ★ 被查的字典
0x0EAC9198  mov  x1,x19                 ; e10313aa  x1 = 入参 id
0x0EAC91A4  bl   0x0A4497EC             ; 9201e696  Dictionary<int,LocalizeGachaShopExcel>.TryGetValue(id, out v)
0x0EAC91A8  tbz  w0,#0,#0x0EAC927C      ; a0060036  ★ 查不到 → 直接跳 fallback
0x0EAC91E4  cmp  w0,#1                  ; 1f040071  ┐ 语言判定
0x0EAC91E8  b.eq 0x0EAC924C             ; 20030054  ├ 1 → 日文分支
0x0EAC91EC  cbnz w0,#0x0EAC927C         ; 80040035  ┘ 非 0 非 1 → 直接 fallback ★
; 语言 0（韩/中文列）分支：
0x0EAC9210  bl   0x0BCA4874             ; 996d4797  LocalizeGachaShopExcel::get_TitleNameKr()
0x0EAC9218  bl   0x089D732C             ; 45387c96  String.IsNullOrEmpty()   （判空：null 或 [x0+0x10]==0）
0x0EAC921C  tbnz w0,#0,#0x0EAC927C      ; 00030037  ★ 空 → fallback
; 语言 1 分支：
0x0EAC926C  bl   0x0BCA4978             ; c36d4797  LocalizeGachaShopExcel::get_TitleNameJp()
; ---- fallback（三个 Get* 函数共用同一形态）----
0x0EAC927C  ldr  x8,[x23]               ; e80240f9  x23 = 全局 0x0FA2FE60(.got) → 取静态对象
0x0EAC9280  ldr  x8,[x8,#0xb8]          ; 085d40f9  → 该对象 +0xB8 的静态槽
0x0EAC9284  ldr  x0,[x8]                ; 000140f9  → 取出字符串（这就是红字返回值）
0x0EAC9288  ... epilogue / ret
```

- `SubTitle` / `Description` 两个函数是同一模板（0x0EAC941C `get_SubTitleKr`、0x0EAC9478 `get_SubTitleJp`；
  0x0EAC94xx 对应 `get_GachaDescriptionKr/Jp`），标志位 `0x1027 6DE0/6DE1/6DE2` 分别是三者的"已初始化"字节。
- **【确证】`IsNullOrEmpty`**：`0x089D732C`：`cbz x0`→空；`ldr w8,[x0,#0x10]`→C# string 的 length 字段；`cbz`→空。
- **【确证】`localizeGachaShopDic` 是 `ShopData` 的字段**（字段表 field=68306）。
  字段偏移 `+0x120` 与名字的对应是**【推测·强】**（依据：紧跟其后调用链只读 `LocalizeGachaShopExcel` 的属性，
  且该类型里只有这一个 `Dictionary<..., LocalizeGachaShopExcel>`）。
- **【确证】fallback 返回的是一个静态字符串槽**，不是拼接结果、不是表数据。

### 3.3 调用者清单（BL 反查，全代码段 160 MB 扫描）

```
py work\ba\scripts\md_bridge.py callers --va 0x0EAC90D4
callers=1
  0x0A8CFA20  in mdef=49273 UIGachaInfo::SetData
```

**【确证】`GetGachaTitleNameString` 全局只有一个调用者**，就是招募面板。
（所以「谁在拼这个 key」的答案是唯一的，不会误伤别的界面。）

---

## 4. key 到底由什么算出来

### 4.1 主路径（普通卡池）【确证】

```
key = ShopRecruit.Id（int，取自 ShopRecruitDBSchema/ShopRecruitExcel 的 Id 字段）
表  = LocalizeGachaShopDB（FlatBuffer：GachaShopId, TabNameKr/Jp, TitleNameKr/Jp,
      SubTitleKr/Jp, GachaDescriptionKr/Jp, GachaPeriodCN）
```
- 面板**直接把 `ShopRecruit.Id` 当 `GachaShopId` 用**，中间没有 +偏移、没有拼字符串、没有再取别的字段。
- 表结构由 `MX.Data.Excel.LocalizeGachaShopExcel`（39 方法）与
  `MX.Data.Excel.LocalizeGachaShopDBSchema`（GachaShopId）确认。

### 4.2 新手分支（`CategoryType==23 && IsNewbie`）——**这里的 key 是纯常量**【确证】

`SetData` 前半段（0x0A8CF2A4 起）：

```
0x0A8CF2A4  bl 0x0AB17684               ; MX.Data.Excel.ShopRecruitExcel::get_CategoryType()
0x0A8CF2A8  cmp w0,#0x17                ; 1f5c0071   ← 23
0x0A8CF2AC  b.ne 0x0A8CF5C0             ; a1180054  不是 23 → 走普通路径
0x0A8CF2B8  bl 0x0AB1843C               ; ShopRecruitExcel::get_IsNewbie()
0x0A8CF2BC  tbz  w0,#0,#0x0A8CF5C0      ; 20180036  false → 普通路径
; ---- 新手路径 ----
0x0A8CF2DC  bl 0x06FB352C               ; 取 LocalizeData 单例
0x0A8CF2E4  adrp x8,#0xFB12000 / ldr x8,[x8,#0x380] / 0x0A8CF2F8 ldr x1,[x8]   ; x1 = 常量字面量 ★
0x0A8CF300  bl 0x0656AB34               ; MX.Data.LocalizeData::GetText(this, 常量key, null, null)
```

- **【确证】这条分支里 key 是一个编译期字符串字面量常量**，不由任何字段计算 🡒
  如果红字出现在「新手冲刺!!」卡池上，那么**任务前提「key 不是 `ShopRecruit.Id`」就是对的**，
  因为这条分支压根不碰 `ShopRecruit.Id`。
- `MX.Data.LocalizeData::GetText(string)` @0x0656AB34 的实现：
  先 `bl 0x0D2599B4` = `MX.Core.Services.XXHashService::CalculateHash(key)`，
  再转调 `GetText(hash, default)` ——【确证】**本地化表是按 `XXHash(key)` 索引的**。
- 而 `GetText(hash,default)` @0x0656AA90 **本身不含任何 fallback 字面量**：
  `TryGetText` 命中就返回，未命中且 `default==null` 就走到 0x0656AB20 的异常/空处理。
  ⇒ **【确证】红字 `[FF0000]No LocalizeKey` 不是 `LocalizeData.GetText` 打出来的。**

### 4.3 所以红字最可能来自 §3.2 的 `GetGacha*` fallback 【推测·强】

- 依据 1：该 fallback 返回的是**静态字符串槽** `[[0x0FA2FE60]+0xB8]`，形态与「取一个字面量常量」一致。
- 依据 2：`[FF0000]No LocalizeKey` 是客户端里唯一带 `[FF0000]` 的"错误占位"字面量（前人已确证其存在）。
- **未做**：无法证明该槽就是 `[FF0000]No LocalizeKey`（字面量内容整体加密，§2.3）。
  要钉死只需动态侧看一眼该地址里的 string 内容。

---

## 5. 数据侧核对（确证）与前提差异

```
py work\ba\scripts\q_localize_slots.py
```
```
LocalizeGachaShopDBSchema rows=1235  id range 1..99999999
ShopRecruit ids=532  range 1..99999999
ShopRecruit ids that exist as LocalizeGachaShopDBSchema.GachaShopId: 532/532

按 ShopRecruit.Id 命中的行（前 40 个）槽位统计：
  TabNameKr 40, TitleNameKr 40, SubTitleKr 40, GachaDescriptionKr 40   ← 中文字符串齐全
  TabNameJp  3, TitleNameJp  3, SubTitleJp  3, GachaDescriptionJp  3   ← 只有 3 行是合法字符串
  GachaPeriodCN 37
明细：id=5000010  TitleNameKr='限时招募！'  SubTitleKr='白子（3★）招募概率提升！'
```

### 5.1 事实
- **【确证】** 532 个 `ShopRecruit.Id` **全部**能在 `LocalizeGachaShopDBSchema.GachaShopId` 里命中。
- **【确证】** 这些行的**中文文本存放在 `*Kr` 槽位**（`TitleNameKr='限时招募！'`），
  `*Jp` 槽位在绝大多数行里**不是合法字符串**（解析退化成整数）⇒ JP 列基本是空的/坏的。
- ⇒ 因此**「key 错」不是唯一解释**：只要运行时语言判定不是 0，或者读到的是 JP 列，就会 **100% 落到 fallback**。

### 5.2 与任务前提的差异（必须指出）
| 任务前提 | 代码实测 | 判定 |
|---|---|---|
| 「查表用的 key 不是 `ShopRecruit.Id`」 | 主路径**就是** `ShopRecruitExcel.get_Id()`（三处 BL 直接印证） | **前提与主路径不符** |
| 「数据侧不缺」 | 行不缺 ✔，但**中文只在 Kr 列、JP 列空** | 部分成立 |
| 「Tab 能显示，标题/说明不能」 | Tab 走 `ShopData.GetGachaTabString`，与 Title **同构**（同样有语言判定 `cmp w0,#1` + `IsNullOrEmpty` + 同一 fallback） | 说明差异来自**数据列**或**不同卡池走了不同分支**，不是"key 拼错" |

### 5.3 两种可区分的成因（给下一步）
1. **新手分支**（`CategoryType==23 && IsNewbie`）→ 用的是**常量字面量 key**（§4.2）。
   若出问题的是新手池，则修法是改这个常量 key / 补 `Localize` 表的对应条目。
2. **普通分支** → 用 `ShopRecruit.Id` 查 `GachaShopId`，读 `TitleNameKr`（语言 0）。
   若出问题的是普通池，则红字来自「语言判定非 0」或「该行 Kr 列为空」。
   **一分钟可验证**：把 §3.2 的 0x0EAC91E4（`cmp w0,#1`）处的 w0 打出来 —— 
   w0==0 → 查数据 Kr 列；w0==1 → 撞上空的 JP 列；w0∉{0,1} → 语言枚举根本没有中文分支。

---

## 6. 确证 / 推测 清单

**【确证】**
1. `libil2cpp.so` 内**不存在** `[FF0000]No LocalizeKey`（明文 + 256 键 XOR 全扫 = 0 命中）→ 字符串 xref 不可行。
2. metadata 头 count 为字节数；`stringLiteral`=0x100+0x304C0、`stringLiteralData`=0x305C0+0xBC408，首尾严丝合缝。
3. 招募面板 = `UIGachaInfo.SetData` @0x0A8CF08C；标题/副标题/说明分别由
   `GetGachaTitleNameString`/`GetGachaSubTitleString`/`GetGachaDescriptionString` 产生。
4. 主路径 key = `ShopRecruitExcel.get_Id()`（0x0AB17608），三处 BL：0x0A8CFA0C / 0x0A8CFA4C / 0x0A8CFA94。
5. `GetGachaTitleNameString` **全局唯一调用者**就是该面板。
6. 查表动作为 `Dictionary.TryGetValue(id)` → 读 `LocalizeGachaShopExcel.TitleNameKr/Jp` → `IsNullOrEmpty` → fallback。
7. 语言判定为 `0→Kr, 1→Jp, 其它→fallback`。
8. 新手分支用**常量字面量 key** 调 `LocalizeData.GetText`，且该 GetText 按 `XXHash(key)` 索引、自身不含红字常量。
9. 数据侧：532/532 命中；中文在 Kr 列；JP 列基本非字符串。

**【推测·强】**
1. fallback 返回的静态槽 `[[0x0FA2FE60]+0xB8]` 就是 `[FF0000]No LocalizeKey`（内容被加密，无法静态证明）。
2. `ShopData` 字段 `+0x120 == localizeGachaShopDic`；`UIGachaInfo` 字段 `+0x38/+0x40/+0x48` 的对应关系。

**【未完成】**
1. `stringLiteral` 条目表仍是混淆态（24728 条全不可读）⇒ 拿不到 literal index，`litref` 路线未走通。
2. 字面量区不存在页级统一 XOR key，整块解密未完成。
3. 0x0E486524（语言取值的实现）所在页反汇编失败（疑似被加密的代码页），只取其调用点契约。

---

## 7. 复现命令（全部只读）

```powershell
$py = "C:\Users\su\AppData\Local\Programs\DeepSeek Harness\resources\runtime\primary-runtime\dependencies\python\python.exe"
$so = "C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\audit\ba-apk\lib\arm64-v8a\libil2cpp.so"
$S  = "C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\scripts"

& $py $S\xref_nolocalizekey.py layout $so
& $py $S\xref_nolocalizekey.py sweep  $so --text "No LocalizeKey"
& $py $S\md_bridge.py hdr
& $py $S\md_bridge.py litstat
& $py $S\md_bridge.py type  MX.Data.Excel.LocalizeGachaShopExcel
& $py $S\md_bridge.py mdef  49273 --n 1024      # UIGachaInfo.SetData
& $py $S\md_bridge.py mdef  108284              # GetGachaTitleNameString
& $py $S\md_bridge.py callers --va 0x0EAC90D4
& $py $S\q_localize_slots.py
```

## 8. 局限

- 全部为**静态只读**结论；运行时的语言枚举值、`[[0x0FA2FE60]+0xB8]` 的真实字符串内容、
  以及"哪几个 gacha 真的红了"都需要动态侧一眼才能钉死。
- `ba_ptrs.bin` 中有大量 0（未解析的方法），对**非方法起点**的地址做"最近向下"归属会给出错误方法名；
  本报告引用的每个地址都是**方法起点**（有 mdef 编号），可信。
- 有少量代码页（如 0x0E486000 附近）反汇编失败，属疑似加密页，未展开。
