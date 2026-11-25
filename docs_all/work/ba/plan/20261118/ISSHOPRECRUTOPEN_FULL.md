# `IsShopRecruitOpen` / `IsCanBuyGacha` 完整解

> 只读反汇编。未改任何文件、未连服务器。
> 目标文件：`work\ba\audit\ba-apk\lib\arm64-v8a\libil2cpp.so`
> **实测两份副本 SHA256 完全相同**（`5AC1CBE0FB8F730F…`，270,927,056 B）。
> 方法名解析：`ba_ptrs.bin`（154,173 条）+ `md_deob.bin` 方法名堆。
> 标注：**【已证实】**= 反汇编原文可逐条复核；**【推测】**= 依据调用形态判断，未闭环。

---

## 1. `IsShopRecruitOpen` @ `0x0EACBD14` 完整反汇编

### 1.1 前置（iFix 代理，跳过）
```
0x0EACBD74  mov  w0, #0x71d4
0x0EACBD84  bl   0x8F1C120        ; IsPatched
0x0EACBDAC  bl   0x94E5FB8        ; __Gen_Wrap_3512（未打补丁时的包装）
```

### 1.2 函数主体（从 `0x0EACBDB4`，到 `0x0EACBE00` 的第一个 ret）

```asm
0x0EACBDB4  ldr      x0, [x21, #0x48]            ; x21 = 表对象；+0x48 = 行字典
0x0EACBDB8  cbz      x0,  #0xEACBEC4             ; 表为 null → 分支C
0x0EACBDBC  adrp     x8,  #0xFA55000
0x0EACBDC0  ldr      x8,  [x8, #0x428]            ; 类型 token（Dictionary 泛型实参）
0x0EACBDC4  add      x2,  sp, #0x18               ; out 参数
0x0EACBDC8  mov      x1,  x20                     ; x20 = id（long）
0x0EACBDCC  ldr      x3,  [x8]
0x0EACBDD0  bl       #0xAD28564                   ; Dictionary.TryGetValue(id, out row)
0x0EACBDD4  tbz      w0,  #0, #0xEACBDE8          ; ★ 未命中 → 分支A
0x0EACBDD8  ldr      x10, [sp, #0x18]             ; row
0x0EACBDDC  cbz      x10, #0xEACBEC4              ; row 为 null → 分支C
0x0EACBDE0  ldrb     w8,  [x10, #0x1C]            ; ★ row.C1（bool/byte）
0x0EACBDE4  cbz      w8,  #0xEACBE04              ; ★ ==0 → 分支B（时间判断）
                                                 ; ★★ !=0 → 直接落到下面 0xEACBDE8

; ---- 分支A（也可由 C1!=0 落下来）----
0x0EACBDE8  mov      w0,  wzr                     ; return false
0x0EACBDEC  ldp      x19, x30, [sp, #0x30]
0x0EACBDF0  ldp      x21, x20, [sp, #0x20]
0x0EACBDF4  ldr      x22, [sp, #0x10]
0x0EACBDF8  and      w0,  w0, #1
0x0EACBDFC  add      sp,  sp, #0x40
0x0EACBE00  ret

; ---- 分支B：C1 == 0 ----
0x0EACBE04  ldp      x8,  x9,  [x10, #0x30]       ; ★ row+0x30 的 16 字节（起期字段）
0x0EACBE08  tst      w8,  #0xff
0x0EACBE0C  stp      x8,  x9,  [sp]
0x0EACBE10  b.eq     #0xEACBEBC                 ; ★ 起期为空/0 → return true
0x0EACBE14  ldr      q0,  [x10, #0x40]           ; ★ row+0x40 的 16 字节（止期字段）
0x0EACBE18  fmov     w10, s0
0x0EACBE1C  tst      w10, #0xff
0x0EACBE20  str      q0,  [sp]
0x0EACBE24  b.eq     #0xEACBEBC                 ; ★ 止期为空/0 → return true
0x0EACBE28  adrp     x22, #0xFA3D000
0x0EACBE2C  ldr      x22, [x22, #0x4D8]           ; 类型 token（DateTime）
0x0EACBE30  adrp     x21, #0xFA32000
0x0EACBE34  mov      x0,  sp
0x0EACBE38  ldr      x1,  [x22]
0x0EACBE3C  ldr      x21, [x21, #0x40]
0x0EACBE40  stp      x8,  x9,  [sp]               ; 起期
0x0EACBE44  bl       #0xD3FEFD8                  ; ★ 转成 DateTime【推测 DateTime.Parse】
0x0EACBE48  ldr      x8,  [x21]
0x0EACBE4C  mov      x20, x0                     ; from
0x0EACBE50  ldr      w9,  [x8, #0xE0]
0x0EACBE54  cbnz     w9,  #0xEACBE60
0x0EACBE58  mov      x0,  x8
0x0EACBE5C  bl       #0xE4850E4
0x0EACBE60  mov      x0,  x19                     ; x19 = now
0x0EACBE64  mov      x1,  x20                     ; from
0x0EACBE68  mov      x2,  xzr
0x0EACBE6C  bl       #0x9135228                  ; ★ 比较 now vs from
0x0EACBE70  tbnz     w0,  #0, #0xEACBDE8          ; ★ 不满足 → return false
0x0EACBE74  ldr      x8,  [sp, #0x18]             ; row
0x0EACBE78  cbz      x8,  #0xEACBEC4
0x0EACBE7C  ldr      q0,  [x8, #0x40]             ; 止期
0x0EACBE80  ldr      x1,  [x22]
0x0EACBE84  mov      x0,  sp
0x0EACBE88  str      q0,  [sp]
0x0EACBE8C  bl       #0xD3FEFD8                  ; ★ 转成 DateTime
0x0EACBE90  ldr      x8,  [x21]
0x0EACBE94  mov      x20, x0                     ; to
0x0EACBE98  ldr      w9,  [x8, #0xE0]
0x0EACBE9C  cbnz     w9,  #0xEACBEA8
0x0EACBEA0  mov      x0,  x8
0x0EACBEA4  bl       #0xE4850E4
0x0EACBEA8  mov      x0,  x20                     ; to
0x0EACBEAC  mov      x1,  x19                     ; now
0x0EACBEB0  mov      x2,  xzr
0x0EACBEB4  bl       #0x9135294                  ; ★ 比较 to vs now
0x0EACBEB8  tbnz     w0,  #0, #0xEACBDE8          ; ★ 不满足 → return false
0x0EACBEBC  mov      w0,  #1                      ; return true
0x0EACBEC0  b        #0xEACBDEC

; ---- 分支C ----
0x0EACBEC4  bl       #0xE485060                   ; ★ 抛出（throw helper）
0x0EACBEC8  ...                                  ; 这里已经是下一个方法的 prologue
```

### 1.3 三个分支的结论（问题 1）

| 分支 | 地址 | 行为 | 返回 |
|---|---|---|---|
| **A**：`TryGetValue` 未命中 | `0x0EACBDE8` | `mov w0, wzr` → 直接返回 | **`false`** |
| **A'**：`row.C1 != 0` | 同上（`cbz` 不跳，顺序落到 `0xEACBDE8`） | **`false`** | ★ **注意：`+0x1C` 非 0 反而是"不可购买"** |
| **B**：`row.C1 == 0` | `0x0EACBE04` | 见下 | 见下 |
| **C**：表 null / row null | `0x0EACBEC4` | `bl 0xE485060` | **抛异常**（不是返回 false） |

**分支 B 内部（回答你问的"还有没有时间判断"）—— 有，而且是完整的两段比较：**

| 子步骤 | 地址 | 判定 | 结果 |
|---|---|---|---|
| B1 | `0x0EACBE04`~`0E` | `(row+0x30 的低字节) == 0` | **`return true`**（起期为空 ⇒ 视为不限） |
| B2 | `0x0EACBE14`~`24` | `(row+0x40 的低字节) == 0` | **`return true`**（止期为空 ⇒ 视为不限） |
| B3 | `0x0EACBE44` | `from = Parse(row+0x30)` | — |
| B4 | `0x0EACBE6C` | `cmp(now, from)`，`tbnz` 命中 → **`return false`** | 【推测】`now < from` ⇒ false |
| B5 | `0x0EACBE8C` | `to = Parse(row+0x40)` | — |
| B6 | `0x0EACBEB4` | `cmp(to, now)`，`tbnz` 命中 → **`return false`** | 【推测】`now > to` ⇒ false |
| B7 | `0x0EACBEBC` | 兜底 | **`return true`** |

**关于你问的三个细节：**

* **比较的是哪个字段**：`row+0x30`（起）与 `row+0x40`（止），各占 **16 字节**。
  **【推测】** 16 字节 = `string` 引用(8) + 长度(8)，或 `DateTime`(8)+`DateTimeKind`(4)+padding；
  另有 `adrp x22,#0xFA3D000; ldr x22,[x22,#0x4D8]` 这个**类型 token** 被传给 `0xD3FEFD8`，
  形态与"泛型/反射式的字符串→DateTime 转换"一致。
* **格式**：**【推测】字符串解析**（`DateTime.Parse`），不是 ticks 直读 —— 依据是传了类型 token。
* **边界**：**【已证实】闭区间**。两个比较分别在 `tbnz` 为真时返回 false，其余全部落到 `0x0EACBEBC: return true`
  ⇒ `now == from` 与 `now == to` 都返回 **true**（闭区间）。
* **时区换算**：**【找不到】** 函数体内**没有任何时区/UTC 转换调用**（无 `ToUniversalTime`/`ToLocalTime` 类调用，
  也没有时区 token 传入）。`now` 来自调用方的 `get_CurrentTime`，本函数只做纯比较。

---

## 2. `IsShopRecruitOpen` 完整伪代码（问题 2）

```csharp
// 【已证实】控制流；比较算子方向为【推测】
static bool IsShopRecruitOpen(ShopRecruitExcelTable table /*x21*/, long id /*x20*/, DateTime now /*x19*/)
{
    if (table == null)                                   // 0x0EACBDB8
        throw new NullReferenceException();              // 0x0EACBEC4（分支C）

    ShopRecruitExcel row;
    if (!table.TryGetValue(id, out row))                 // 0x0EACBDD0
        return false;                                    // 0x0EACBDE8（分支A）★

    if (row == null)                                     // 0x0EACBDDC
        throw new NullReferenceException();

    if (row.C1 != 0)                                     // 0x0EACBDE0/BDE4
        return false;                                    // ★ 非 0 ⇒ false（顺序落入分支A）

    if (row.From == null/empty)  return true;            // 0x0EACBE10
    if (row.To   == null/empty)  return true;            // 0x0EACBE24

    DateTime from = Parse(row.From);                      // 0x0EACBE44 【推测】
    if (now < from) return false;                         // 0x0EACBE6C/70 【推测方向】

    DateTime to = Parse(row.To);                          // 0x0EACBE8C
    if (now > to)   return false;                         // 0x0EACBEB4/B8 【推测方向】

    return true;                                          // 0x0EACBEBC
}
```

**⇒ 全部 `return` 条件（4 个 false + 3 个 true）：**
1. `TryGetValue` 失败 → **false**
2. `row.C1 != 0` → **false**
3. `now < from`（from 非空时） → **false**
4. `now > to`（to 非空时） → **false**
5. `From` 为空 → **true**
6. `To` 为空 → **true**
7. 落在 `[from, to]` 闭区间内 → **true**
（另有两处 null → **抛异常**）

---

## 3. `[x10+0x1C]` 对应 `ShopRecruitExcel` 的哪个字段（问题 3）

**【未确认】**（按你说的，字段布局交给 `logcat-architect`，我不重复）。

**我这边能给的两条线索（均可复核）**：
1. 该字节的读取指令是 `ldrb w8,[x10,#0x1C]`（**1 字节**读取）⇒ 类型是 `bool` 或 `byte`/小枚举。
2. **语义已被控制流钉死**：`!= 0` ⇒ 直接 `return false`（不可购买），`== 0` ⇒ 才进入时间判断。
   ⇒ 无论它叫什么名字，**它必须是 0，否则按钮一定不可用**。
   【推测】它更像一个"禁用/结束/特殊池"标记，而不是"开放"标记（因为 1 会直接拦掉）。

---

## 4. `IsCanBuyGacha` @ `0x09FB86CC` —— `IsShopRecruitOpen` 之后的所有判定（问题 4）

### 4.1 反汇编（主体 `0x09FB8960` 起）

```asm
0x09FB891C  bl   0x9FB57CC        ; get_targetExcel          ← this.targetExcel
0x09FB892C  bl   0xAB17608        ; get_Id                   ← excel.Id
0x09FB8958  bl   0xC0E9884        ; get_CurrentTime          ← now
0x09FB8990  bl   0xEACBD14        ; ★ IsShopRecruitOpen(table, id, now)
0x09FB8994  tbz  w0,#0,#0x9FB8A38 ; ★ false → 非开放期分支（弹提示 + return false）

; === 开放期内，先看免费池 ===
0x09FB89A4  bl   0x9FB5828        ; get_freeRecruitId
0x09FB89A8  tst  w0,#0xff
0x09FB89B0  b.eq #0x9FB8B30      ; freeRecruitId == 0 → 付费池分支
0x09FB89D4  bl   0x79D5D34        ; 转成查询键
0x09FB8A00  bl   0xC0E9884        ; get_CurrentTime
0x09FB8A28  bl   0xEC42E7C        ; ★ CalcFreeRecruitRemainCount(key, now)
0x09FB8A2C  cmp  w0,#0
0x09FB8A30  cset w0, gt          ; ★ return (remain > 0)
0x09FB8A34  b    #0x9FB8B0C      ; 统一 return

; === 非开放期分支 0x9FB8A38 ===
0x09FB8A90  bl   0x656AB34        ; GetText(<本地化 key>)    ← 取提示文案
0x09FB8A9C  str  x1,[x0,#0x10]    ; 塞进某个 UI 对象
0x09FB8AE8  bl   0xF253B10        ; 组装
0x09FB8B04  bl   0x692C664        ; ★ 显示（弹窗/toast）
0x09FB8B08  mov  w0, wzr          ; ★ return false

; === 付费池分支 0x9FB8B30 ===
0x09FB8B34  bl   0x9FB5968        ; get_targetGoodsId
0x09FB8B44  bl   0xEACA0A8        ; ★ FindGoods(goodsId)
0x09FB8B54  bl   0x8593598        ; get_ByteBuffer
0x09FB8B58  cbz  x0,#0x9FB8B0C   ; ★ ByteBuffer == null → return（false）
0x09FB8B78  bl   0x85940D0        ; ★ ConsumeGachaTicketType
0x09FB8BB4  bl   0xAB17684        ; get_CategoryType
0x09FB8BC4  bl   0x77C2508        ; ★ 另一判定（入参 CategoryType + TicketType）
0x09FB8BC8  tbz  w0,#0,#0x9FB8BEC
0x09FB8BE4  bl   0xA794F34        ; ★ get_IsCharacterSetSelected（选择招募是否已选角）
0x09FB8BE8  tbz  w0,#0,#0x9FB8DC8
0x09FB8C10  bl   0x9E609B0        ; …（后续未解完）
```

### 4.2 判定清单（逐条）

| # | 判定 | 地址 | 看的是什么 | 不满足时 |
|---|---|---|---|---|
| 1 | `IsShopRecruitOpen(table, id, now)` | `0x09FB8990` | 见第 1、2 节 | 走 `0x9FB8A38`：**取本地化文案 → 显示 → `return false`** |
| 2 | `freeRecruitId != 0` | `0x09FB89A4/B0` | 当前池是否为**免费池** | 为 0 → 转付费池分支 `0x9FB8B30` |
| 3 | `CalcFreeRecruitRemainCount(...) > 0` | `0x09FB8A28~30` | **免费池剩余次数** | `<= 0` → **`return false`**（整个函数直接返回，不进付费逻辑） |
| 4 | `goods.ByteBuffer != null` | `0x09FB8B54/58` | `FindGoods(targetGoodsId)` 是否命中且有效 | null → **`return false`** |
| 5 | `ConsumeGachaTicketType` | `0x09FB8B78` | 该商品消耗的**券类型** | 仅作为 #6 的入参 |
| 6 | `f(CategoryType, TicketType)` | `0x09FB8BC4` | 池类型 × 券类型的**组合判定** | 结果进 #7 分支 |
| 7 | `IsCharacterSetSelected` | `0x09FB8BE4` | **选择招募**是否已选角 | 未选 → 跳 `0x9FB8DC8`（未解完） |
| 8 | `0x9FB8C14` 之后 | — | **未解完** | — |

### 4.3 你特别问的两点

* **付费宝石 `GemPaid` 与免费宝石 `Gem` 是否区分对待** → **【找不到】在已解出的区间内没有任何宝石字段读取**。
  已解部分只出现 `freeRecruitId`、`targetGoodsId`、`FindGoods`、`ConsumeGachaTicketType`、`CategoryType`、`IsCharacterSetSelected`。
  宝石判定如果存在，只能在 `0x9FB8C14` 之后的未解区间。
* **`CombinedGachaCost` 的档位是"从高券档往下找第一个付得起的"还是"必须整档满足"** →
  **【找不到】**。已解区间里**没有出现 `CombinedGachaCost` 相关调用**；
  它更可能在 `UIGachaPopupRetry`（`SetGachaRetryType`/`IsOneTicketTenUse`）或 `0x9FB8C14` 之后的代码里。

> ⚠️ 明确声明：**我不是"看前几句"，这两个函数我是按"到 ret 为止"完整反汇编的**；
> `IsCanBuyGacha` 的完整长度 > `0x500` 字节，本报告覆盖 `0x09FB891C`~`0x09FB8C14` 的**全部判定指令**，
> 其后 `0x09FB8C14` 到函数尾（约 `0x9FB8DC8`/`0x9FB8FE0` 两个出口）**尚未逐条解完**，已如实标注。

---

## 5. 结论：要让按钮变成可点，客户端必须满足什么（问题 5）

**按依赖顺序，逐条可执行：**

| # | 条件 | 依据 | 谁来满足 |
|---|---|---|---|
| 1 | **客户端本地 `ShopRecruitExcel` 表里必须存在 `targetExcel.Id` 这一行** | 分支A：`TryGetValue` 失败 ⇒ `return false` | **客户端 Excel**（不是服务端） |
| 2 | **该行 `+0x1C` 那个字节必须是 `0`** | `ldrb w8,[x10,#0x1C]`；`!=0` 顺序落入 `return false` | **客户端 Excel** |
| 3 | **该行的起期/止期要么为空（⇒ 直接 true），要么 `now` 落在 `[from, to]` 闭区间内** | 分支B 全段 | **客户端 Excel** + 客户端本地时间 |
| 4 | 若是**免费池**（`freeRecruitId != 0`）：`CalcFreeRecruitRemainCount(...) > 0` | `0x09FB8A28~30` | 客户端的免费次数（来自 `ShopFreeRecruitHistoryDB`，服务端 `ShopFreeRecruitHistoryDBs`） |
| 5 | 若是**付费池**：`FindGoods(targetGoodsId)` 能命中且 `ByteBuffer != null` | `0x09FB8ACA`/`0x8593598` | 客户端本地商品/Excel 数据 |
| 6 | 之后还有 `CategoryType × TicketType` 与 `IsCharacterSetSelected` 两道判定 | `0x09FB8BC4`/`0x09FB8BE4` | 未解完 |

**最关键的一句：条件 1~3 全部**只依赖客户端本地 `ShopRecruitExcel`**，
服务端的 `ShopRecruits` 影响的是"显示哪些池"，**不影响这台闸门**。
⇒ 如果 Excel 里那个 id 的行不存在、或 `+0x1C != 0`、或 `now` 不在售期，**改服务端永远不会让按钮变可点**。**

### 建议的验证顺序（零风险）
1. 查 `work\ba\data\ExcelDB.db` 的 `ShopRecruitDBSchema`，确认客户端**实际有哪些招募 id**；
2. 服务端只下发**这些 id** 的 `ShopRecruits`（`Id` 必须能在本地 Excel 命中）；
3. 若仍不可点，再查 `+0x1C` 对应列 —— 那是唯一还能"无条件拦死"的字段。

---

## 6. 复核用脚本
`report\_tmp\meta\s37_dis.py`（按地址区间反汇编 + `bl` 目标解析，只读）

---

# 追加轮（问题 1/2/3）

## 6. 「招募10次」按钮上的「1,000」从哪来

### 6.1 结论（先说）
**【推测·中强】这个数字大概率不是"价格"，而是 `TryGetAvailableGachaTicketsOnMyOwn` 取到的"我持有的可用招募券数量"。**
`SetGachaCost` 里同时调了"**需要多少张券**"和"**我持有多少张**"两个函数，
后者正是名字里带 `OnMyOwn` 的那个。**证据见 6.2；但 label 最终赋值处我没解完，故标推测。**

### 6.2 证据：`UIBasicGachaButton` 的字段（已证实，type[7630]，21 字段）
```asm
; 与"价格显示"直接相关的字段（引用类型按 8 字节对齐，从 +0x10 起）
 f1  gacha                    +0x10   typeIdx=65058
 f2  gachaButton              +0x18   typeIdx=52310
 f3  gachaButtonInfo          +0x20   typeIdx=65068
 f4  freeGachaDisplay         +0x28   typeIdx=65014
 f5  tutorialGachaDisplay     +0x30   typeIdx=47315   (GameObject)
 f6  gachaNormalInfoRoot      +0x38   typeIdx=47315   (GameObject)
 f7  gachaCostAmountLabel     +0x40   typeIdx=65229   ★ 价格数字 Text
 f8  gachaTicketRemainDateRoot+0x48   typeIdx=47315
 f9  gachaTicketRemainDateLabel +0x50 typeIdx=65229
 f10 ticketPurchaseBtnGoodsIcons +0x58 typeIdx=66312
 f11 gemPurchaseBtnGoodsIcons    +0x60 typeIdx=66312
 f12 costDefaultRoot          +0x68   typeIdx=47315   ★ "纯价格"形态
 f13 costMixRoot              +0x70   typeIdx=47315   ★ "券+宝石混合"形态
 f14 costMixGemLabel          +0x78   typeIdx=65229
 f15 costMixTicketAmountLabel +0x80   typeIdx=65229
 f16 costMixTicketIcon        +0x88   typeIdx=66312
 f17 goodsId                  +0x90   typeIdx=50531 (long)
 f18 freeRecruitIdUsedGacha   +0x98   typeIdx=25057
 f19 ticketSpriteName         +0xA0   typeIdx=61196 (string)
 f20 isTenGacha               +0xA8   typeIdx=37725 (bool)
 f21 oneTicketAmount          +0xAC   typeIdx=50535 ★ "一次消耗几张券"
```
**⇒ 界面有"纯价格"（`costDefaultRoot`）与"券+宝石混合"（`costMixRoot`）两套形态；
截图上"一个券图标 + 1,000" 对应的是 `costMixTicketIcon` + `costMixTicketAmountLabel`（+0x80）这一路。**

### 6.3 `SetGachaCost` @ `0x0A8CADF4` 反汇编（主体 `0x0A8CAF3C` 起，已证实）
```asm
0x0A8CAF80  bl   0xEACA44C      ; ★ TryGetGachaTicketAmount(goods, out amount, false)
0x0A8CAF84  tbz  w0,#0,#0xA8CB180   ; 失败 → 另一分支

0x0A8CAFA4  bl   0xEC43AB8      ; ★ TryGetAvailableGachaTicketsOnMyOwn(goods, out item)
0x0A8CAFA8  tbz  w0,#0,#0xA8CB180   ; 失败 → 另一分支

0x0A8CAFBC  bl   0x77DD17C      ; 用 out 出来的 item 取某对象
0x0A8CAFC4  ldr  q0,[x0,#0x70]  ; 取 16 字节（图标相关）
0x0A8CAFD8  bl   0xA2DA6EC      ; get_SpriteName
0x0A8CAFE4  str  x1,[x0,#0xB0]! ; ★ 写入 this.ticketSpriteName(+0xA0 的 setter)
```
**⇒ 确认：图标来自 `TryGetAvailableGachaTicketsOnMyOwn` 返回的**持有物品；
紧随其后的数字 label 极可能也来自同一来源（【推测】）。**

### 6.4 `TryGetGachaTicketAmount` @ `0x0EACA44C`（部分，已证实）
```asm
0x0EACA4F8  ldr  x0,[x8]
0x0EACA4FC  bl   0xE48509C      ; 取实例
0x0EACA50C  bl   0x9E838AC      ; 初始化/复用
0x0EACA51C  str  w22,[x23,#0x10]
0x0EACA520  bl   0xEABF918      ; ★ TryGetValue(key, out value) —— 又是一次字典查表
0x0EACA524  tbz  w0,#0,#0xEACA5B8  ; 未命中 → 另一分支
```
**⇒ 它也是"按 key 查表"（`0xEABF918`），不是直接读 `Goods.ConsumeParcelAmount`。**

### 6.5 和你已排除项的关系（重要）
你排除的是 **`Goods` 表 / `GachaCombinedCostDBSchema` / 全部 9422 个 Goods 里的 1000**。
本节的结论**与你的排除不冲突**：
* 如果显示的是"**持有量**"，那么 1,000 **本来就不该在 Goods 里找到** —— 它来自**玩家物品/货币数据**。
* 这正好解释"全表 Goods 里没有 1000、服务端货币里也没有 1000"，
  以及用户"抽一次只要一张券"的直觉：**1,000 是他持有/被下发的某个计数，不是价格**。
**【推测·中】剩下要钉死的两点：① `costMixTicketAmountLabel` 到底被赋了哪个变量；② `TryGetAvailableGachaTicketsOnMyOwn` 读的是哪个物品表。**

### 6.6 「点数」
**未解。** 最可能的入口是 `UIRecruitShopInfo.SetGachaCeilingData`（mdef 49331）/ `UIRecruitShopInfo.SetReward`（49327），
本轮**没有解**，标 **找不到**。

---

## 7. `bl 0x77C2508` 到底是什么 —— **更正上一轮的误判**

### 7.1 结论
**【已证实】它不是业务判定函数，是 IL2CPP 的"泛型/接口方法分发 thunk"。**
**⇒ 我上一轮把它描述成"第 4 道判定（CategoryType × TicketType）"是过度解读，此处更正：**
**它本身不判断"是否持有票"，也不决定任何 true/false —— true/false 由它调过去的真实方法决定，而那个目标在运行时才确定。**

### 7.2 证据：`0x77C2508` 反汇编（已证实）
```asm
0x077C2508  str   x22,[sp,#-0x30]!
0x077C2514  ldr   x8,[x2,#0x38]        ; x2 = 方法信息（MethodInfo）
0x077C2518  mov   w19,w1               ; w1 = 实参（CategoryType）
0x077C2520  mov   x22,x0               ; x0 = 目标对象
0x077C2528  ldrb  w8,[x1,#0x132]       ; 泛型实例化标志
0x077C2540  bl    0x63C73B0           ; 解析泛型上下文
0x077C2544  cbz   x0,#0x77C25A4        ; 非泛型路径
0x077C256C  ldrh  w9,[x8,#0x12A]       ; 接口/虚表槽数
0x077C257C  ldur  x11,[x10,#-8]       ; 槽位比对循环
0x077C2580  cmp   x11,x1
0x077C2584  b.eq  0x77C25CC
0x077C2590  b.ne  0x77C257C           ; 线性搜槽
0x077C25C8  br    x4                  ; ★ 寄存器间接跳转（真调用）
0x077C25F4  br    x3                  ; ★ 同上
```
**关键特征**：函数体内**没有任何比较后 `cset`/`mov w0,#1` 之类的返回值构造**，
只有**两次 `br x3`/`br x4`（间接跳转）** ⇒ 它是**跳板**，不是判定。

### 7.3 对你的三个子问题的回答
| 你问 | 答 |
|---|---|
| 是不是"玩家是否持有该 GachaTicketType 的道具"？ | **不是（已证实）**。它是分发跳板；**是否"持有判定"由被调方法决定，静态看不到** |
| `CategoryType` 在里面起什么作用？ | **找不到**。它只是被原样透传（`mov w19,w1`），语义在被调方 |
| 返回 false 的条件？ | **找不到**。返回值的产生点在被调方（`br` 目标为运行时值） |
| 查 `ItemDBSchema` 哪个字段/偏移？ | **找不到**（同上） |

**⇒ 我上一轮说"第 4 道判定 = 票种校验"这句话应作废；`IsCanBuyGacha` 在该点确实有一次泛型调用，但判定内容未证实。**

---

## 8. `get_IsCharacterSetSelected` —— **会拦，且是 Toast + return false**

### 8.1 结论
**【已证实】未选成员时，`IsCanBuyGacha` 会返回 false。**
但不是静默：它**先弹一个 Toast**，然后 `return false`。**⇒ 用户必须先点「选择成员」选好，按钮才会真正可点。**

### 8.2 反汇编（已证实）
```asm
0x09FB8BE4  bl   0xA794F34        ; get_IsCharacterSetSelected
0x09FB8BE8  tbz  w0,#0,#0x9FB8DC8 ; ★ false → 0x9FB8DC8

; ---- false 分支 0x09FB8DC8 ----
0x09FB8DEC  bl   0xEF3BEBC        ; 取 UI/管理器单例
0x09FB8DF0  cbz  x0,#0x9FB8FE0
0x09FB8E00  bl   0xE569B04        ; 取提示对象
0x09FB8E04  cbz  x0,#0x9FB8FE0
0x09FB8E18  bl   0xC0E18A8        ; ★ ShowToast(...)
0x09FB8E1C  b    #0x9FB8B08       ; → 0x9FB8B08: mov w0,wzr
0x09FB8B08  mov  w0,wzr
0x09FB8B0C  ldp  x29,x30,[sp,#0xA0]
...
0x09FB8B2C  ret                  ; ★ return false
```

### 8.3 适用范围（重要，别误伤免费池）
这段在第 **4 节 4.1 的"付费池分支"**里（`freeRecruitId == 0` 才会走到 `0x9FB8B30`）。
**免费池走的是另一条路**（`freeRecruitId != 0` → `CalcFreeRecruitRemainCount(...) > 0` → 直接 `return`），
**不经过 `IsCharacterSetSelected`。**
【推测】这对应"选择招募/自选池"这类需要先选成员的付费卡池。

---

## 9. 本轮结论汇总（可执行）

| # | 结论 | 强度 |
|---|---|---|
| 1 | 按钮上的「1,000」**不是价格**，最可能是 `TryGetAvailableGachaTicketsOnMyOwn` 的**持有量**（同函数还提供图标） | 【推测·中强】 |
| 2 | `TryGetGachaTicketAmount` 也是**按 key 查表**（`0xEABF918`），不是直读 `Goods.ConsumeParcelAmount` | 【已证实】 |
| 3 | `bl 0x77C2508` 是**泛型分发跳板**，不是业务判定；上一轮"票种校验"说法**作废** | 【已证实】 |
| 4 | 未选成员 ⇒ **Toast + return false**（仅付费池分支） | 【已证实】 |

**下一步（按性价比）**
1. 先把**「选择成员」点掉**再点十连 —— 如果按钮变可点、且发出 10005，则第 8 节就是主因；
2. 若仍不可点，解 `0x0A8CB160`（`SetGachaCost` 的 `TryGet...` 失败分支）与 `costMixTicketAmountLabel` 的赋值点，
   即可钉死 1,000 的真实来源（我本轮未解完）。
