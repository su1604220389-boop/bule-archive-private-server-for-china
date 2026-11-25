# `ShopRecruitExcel` 字段布局与 `[excel+0x1C]` 定位

> 日期：2026-11-18 23:05（+08:00）
> 只读：未改客户端/服务端/仓库任何文件（本文与分析脚本除外）。
> 目标：`IsShopRecruitOpen` @`0x0EACBD14` 中 `ldrb w8,[x10,#0x1C]` 那个字节到底是哪个字段。
> 标注：**【已证实】**=字节级可复核；**【推测】**=由证据推出、未闭环。

---

## 0. 一句话结论

**`[excel+0x1C]` = `ShopRecruitExcelData.IsLegacy`（bool，第 3 个字段）。**
它**不是**某个 8 字节字段的高半部分：类 `ShopRecruitExcelData` 直接继承 `System.Object`（无基类实例字段），对象头 16 字节，`Id(long)` 在 `0x10`、`CategoryType(enum int)` 在 `0x18`、`IsLegacy(bool)` 正好落在 **`0x1C`**。
并且 **ExcelDB 全部 532 行的 IsLegacy 都是 0**（flatbuffer 里该列根本不存在 → 默认 false）⇒ `[+0x1C]` 对所有客户端行都是 0 ⇒ **这道闸门是"放行"状态**，不是当前 10 连无请求的拦点。

---

## 1. 数据来源与方法

客户端 `global-metadata.dat`（38,426,024 B，sha256 `2352CB57…47E6`）**头部被加密**：文件开头没有 `AF 1B B1 FA`，按标准头解析得到乱值；但字符串区是明文（`ShopRecruitExcelData`、`IsShopRecruitOpen`、`<IsLegacy>k__BackingField` 都能直接搜到）。

因此改用工作区里已有的**明文同版本** metadata（GM 包，v31）：

| 文件 | 大小 | sha256 | 头 |
|---|---|---|---|
| `work/ba/noroot/_extract/gm-global-metadata.dat` | 33,351,780 | `86DB0A21…54` | `AF 1B B1 FA` / version **31** |

表定位（v31 header 解出后按 `nameIndex` 反查验证）：
- strings：offset `994,800`，size `4,431,008`
- fields（`Il2CppFieldDefinition`，12 B：nameIndex/typeIndex/token）：offset `24,019,416`，count **144,037**
- typeDefinitions（本版本 88 B/条）：offset `27,587,864`，count **36,220**

**一致性验证**（防止表偏移猜错）：
- `ShopRecruitExcelData` = typeDef **#15782**，ns `MX.Data`，`fieldStart=69228`；
- 下一个类型 `ShopRefreshExcelData` 的 `fieldStart=69240` ⇒ 本类 **fieldCount=12**；
- 字段区 69228..69239 的名字全部是 `<X>k__BackingField`，与 flatbuffer 列顺序一一对应；
- `System.Object` 的 `fieldStart=-1`（无字段）、`System.String` 的 `fieldStart` 指向 `_stringLength/_firstChar` —— 语义正确。

**基类**：`ShopRecruitExcelData` 的 parentTypeIndex=54420 → 解析为 typeDef **#23825 `System.Object`** ⇒ **没有基类实例字段**，偏移从 `0x10` 起算（对象头 2×8）。

> 注意：metadata 里另有一个 `ShopRecruitExcel`（ns `MX.Data.Excel`，typeDef #19315），它是 flatbuffer 包装器（首字段 `__p`，Table），不是 `TryGetValue` 返回的运行时行对象；本结论针对 **`ShopRecruitExcelData`**（MX.Data）。

---

## 2. 字段表（按 fieldStart 顺序，即 C# 声明顺序）

| # | 字段 | typeIndex | 类型（推断） | 大小 | 偏移 |
|---|---|---|---|---|---|
| 1 | `Id` | 49637 | long | 8 | **0x10** |
| 2 | `CategoryType` | 59347 | enum（int32 底层） | 4 | **0x18** |
| 3 | `IsLegacy` | 36800 | **bool** | 1 | **0x1C** ★ |
| — | padding | — | — | 3 | 0x1D–0x1F |
| 4 | `OneGachaGoodsId` | 49637 | long | 8 | 0x20 |
| 5 | `TenGachaGoodsId` | 49637 | long | 8 | 0x28 |
| 6 | `SalePeriodFrom` | 24507 | 16 字节时间结构（`Nullable<DateTime>` 形态） | 16 | **0x30** |
| 7 | `SalePeriodTo` | 24507 | 同上 | 16 | **0x40** |
| 8 | `IsNewbie` | 36800 | **bool** | 1 | 0x50 |
| 9 | `IsOverrideSalePeriod` | 36800 | **bool** | 1 | 0x51 |
| — | padding | — | — | 6 | 0x52–0x57 |
| 10 | `DirectPayInvisibleTokenId` | 49637 | long | 8 | 0x58 |
| 11 | `SelectAbleGachaGroupId` | 49637 | long | 8 | 0x60 |
| 12 | `SalePeriodDayParameter` | 49637 | long | 8 | 0x68 |

对象实例大小 = **0x70**。

**本类的全部 bool 字段**：`IsLegacy`(0x1C)、`IsNewbie`(0x50)、`IsOverrideSalePeriod`(0x51)。`+0x1C` 只可能是 `IsLegacy`。

---

## 3. 与反汇编的交叉验证（决定性）

`ISSHOPRECRUTOPEN_FULL.md` 的原文（`0x0EACBDE0` 起）：

```asm
0x0EACBDE0  ldrb  w8, [x10, #0x1C]     ; ★ C1
0x0EACBDE4  cbz   w8, #0xEACBE04       ; C1==0 → 分支B（时间判断）
0x0EACBDE8  mov   w0, wzr              ; C1!=0 → return false
...
0x0EACBE04  ldp   x8, x9, [x10, #0x30] ; 起期 16 字节
0x0EACBE14  ldr   q0,    [x10, #0x40]  ; 止期 16 字节
```

- `0x30`/`0x40` 各读 **16 字节**、且两段是独立结构 ⇒ 对应上表的 `SalePeriodFrom@0x30`、`SalePeriodTo@0x40`（16 字节时间结构）。
- 这与"按声明顺序布局 + 16 字节对象头"算出的偏移**完全吻合**；如果字段按大小重排（8 字节优先），`SalePeriodFrom` 会落在 0x20 而不是 0x30，`IsLegacy` 也不会在 0x1C。⇒ **布局就是声明顺序**，`+0x1C = IsLegacy` 成立。

**【已证实】** `[excel+0x1C]` 是 `IsLegacy`；读取宽度 1 字节，语义为"==0 才继续进入售期判断；!=0 直接不可购买"。

---

## 4. flatbuffer / ExcelDB 交叉验证

`ShopRecruitDBSchema` 的 `Bytes` 是单行 flatbuffer，字段顺序与 C# 声明一致（`Id`=4、`CategoryType`=6、`IsLegacy`=8、`OneGachaGoodsId`=10、`TenGachaGoodsId`=12、`SalePeriodFrom`=30、`SalePeriodTo`=32、`IsNewbie`=44 …）。

用 lead 给的已知行验证解析器（`Id=5004670`）：

```
{'Id': 5004670, 'CategoryType': 5, 'OneGachaGoodsId': 5004671, 'TenGachaGoodsId': 5004672,
 'DisplayTag': 1, 'DisplayOrder': 10, 'SalePeriodVisible': 1,
 'SalePeriodFrom': '2026-11-12 14:00:00', 'SalePeriodTo': '2026-11-26 13:59:59'}
```

与 lead 提供的已知值**逐项一致** ⇒ 解析器与列顺序可信。

**关键统计（全部 532 行）**：
- flatbuffer 字段槽 **8（IsLegacy）出现次数 = 0**（532 行全部省略，flatbuffer 默认 false/0）；
- 因此 `ShopRecruitExcelData.IsLegacy = 0`，`[excel+0x1C] = 0`，`IsShopRecruitOpen` **不会在 C1 处返回 false**，而是进入 `0xEACBE04` 的售期判断。

补充：截图页签「新手冲刺」对应的客户端行 `Id=7000000` 的 `SalePeriodTo = 2025-08-14 13:59:59`（已过期）⇒ 即使 id 命中，也会在 B5 的时间比较返回 false。**10 连无请求的主因在"id 不在客户端表 / 行已过售期"，不在 `+0x1C`。**

---

## 5. 不确定性与边界（不编）

1. **typeIndex 的具体类型名没有解出**：本 metadata 的 `Il2CppType` 数组不在 header 的常规表里（尝试按 8/12/16 字节步长定位未命中），所以 `49637/24507/36800/59347` 的**类型名**是按 flatbuffer 列语义 + 反汇编宽度推断的（long / 16 字节时间结构 / bool / enum int）。
   - 但**大小**被反汇编偏移钉死（`0x30`、`0x40` 各 16 字节；`0x1C` 1 字节），偏移结论不依赖类型名。
2. **明文 metadata 来自 GM 包**（33,351,780 B）而非零售包（38,426,024 B，头部加密）。两者版本同为 v31、类/字段名/顺序一致；若零售包字段布局有差异，需要先解密其头部再复核。**【推测：一致】**
3. `SalePeriodFrom/To` 的精确类型（`Nullable<DateTime>` 还是自定义 16 字节结构）**【推测】**；`IsShopRecruitOpen` 里 `0xEACBE44` 的调用是 Parse 还是 `get_Value` 未闭环（不影响 +0x1C）。

---

## 6. 对"10 连不发请求"的直接含义

- `+0x1C`（IsLegacy）在**所有**客户端行都是 0 ⇒ 这道闸门**没有拦**；
- 真正拦的是：① `TryGetValue` 查不到 id（服务端下发 9e7 段 id vs 客户端 5e6 段表，交集仅 {1,2}）；② 命中行的 `SalePeriodTo` 已过（如 7000000 → 2025-08-14）。
- 要让按钮变可点：**服务端下发的 id 必须存在于客户端 `ShopRecruitDBSchema` 且售期覆盖当前时间**；改 `IsLegacy` 无效（本来就是 0）。

---

## 7. 复现

- 解析脚本：`%TEMP%\td_probe.py` / `f_dump.py` / `fb_rows.py`（临时，未入库）
- 关键偏移：strings `994800`、fields `24019416`（12 B/条）、typeDefs `27587864`（88 B/条）
- 类型定位：`ShopRecruitExcelData` typeDef #15782，fieldStart 69228，fieldCount 12（下一类 fieldStart 69240）
