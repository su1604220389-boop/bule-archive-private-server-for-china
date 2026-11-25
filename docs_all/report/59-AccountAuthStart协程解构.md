# 59 · `AccountAuthStart` 协程解构 —— 登录链路明文/密文边界与调用图

> 输入（只读）：`work\ba\audit\ba-work\x\lib\arm64-v8a\libil2cpp.so`（270,927,056 B）
> 复用上一个 agent 的产物：`report\_tmp\patch\` 下的 `md_deob.bin`、`ba_ptrs.bin`、`md_parse.py`
>
> **勘误（lead 裁定）**：`report\55` 报的 `HandleAccountAuthResponseMessage = 0x008A3440` 是**转录错**
> —— 把 `40 34 a8 08` 里的 `a8` 写成了 `8a`。真值 **`0x08A83440`**；`0x008A3440` 处是
> `03 04 00 00 00 00 00 00`，**纯数据不是代码**。本报告与 `report\51` 的地址正确。
> 新增脚本：`report\_tmp\meta\s16_env.py`（ELF 映射）、`s17_probe.py`（代码可解码率）、
> `s18_resolve.py`/`s19_focus.py`（类型/方法解析）、`s20_pagemap.py`（页图）、
> `s21_callgraph.py`（反汇编+符号反查）、`s22_xref.py`（全 section 分支目标扫描）
> 日期：2026-11-14

---

## §0 一句话结论 + 明文/密文边界表

> **客户端卡在 `co_RelayPacketsProcess` 的 yield #1（`NetworkTaskManager.Request` 迭代器永不结束）；
> 成败判决在明文区，`HandleAccountAuthResponseMessage` / `ErrorAccountAuth` 零调用点。
> 根因疑为响应反序列化静默失败。**
>
> 次结论：`IsLoginFinished` = `return (loginState == 2)`，但它**零个直接调用点**（极可能被内联）⇒ 改它无效，已否证。

| 方法 | vaddr | 判读 | 依据 |
|---|---|---|---|
| `LoginTask.AccountAuthStart` | `0x08A8078C` | **明文** | `ff 03 01 d1` = `sub sp,sp,#0x40`；页内 `ret`×9 |
| `LoginTask.IsLoginFinished`(getter) | `0x08A823F0` | **明文** | `f3 7b bf a9` = `stp x19,x30,[sp,#-16]!` |
| `LoginTask.StartRequestRelayPackets` | `0x08A80BA4` | **明文** | `f4 0f 1e f8` = `str x20,[sp,#-0x20]!` |
| `LoginTask.co_RelayPacketsProcess` | `0x08A82014` | **明文** | 同上 |
| **`<co_RelayPacketsProcess>d__60.MoveNext`** | **`0x08A88E4C`** | **明文** | `sub sp,sp,#0x60`；页内 `ret`×8 |
| `HandleAccountAuthResponseMessage` | `0x08A83440` | **密文** | capstone 解码 0/16 字；页内 `ret`=0 |
| `OnLoginFinish` | `0x08A836C0` | **密文** | 同上，`ret`=0 |
| `ErrorAccountAuth` | `0x08A842BC` | **密文** | 同上，`ret`=0 |
| `OnLoginFail` | `0x08A8489C` | **密文** | 同上，`ret`=0 |
| `AccountAuthNetworkTask.*` | `0x08294BD0`+ | **密文** | `ret`=0 |
| `<ProcessSession>d__1.MoveNext` | `0x08295B14` | **密文** | `ret`=0 |
| `<WaitForRequest>d__59.MoveNext` | `0x06E14468` | **密文** | `ret`=0 |

> 判据：对每个地址取所在 4KB 页，统计 ARM64 `ret`(`C0 03 5F D6`) 出现次数。真实代码页恒 ≥1（本文件明文代码页平均 9~10 条）。密文页恒为 0。
> 这与 lead 的独立实测**完全一致**（同一批地址、同样判读）——两条独立路径互证。

---

## §1 `IsLoginFinished` —— 反编译完成，但判定为死路（零调用点 / 内联）

> **本节结论（正式否证）**：`get_IsLoginFinished` 的实现已完整反编译，但它在本文件里
> **没有任何直接调用点**，极可能被 IL2CPP 内联 ⇒ **改它大概率无效，建议放弃这条路线**。
> 否证也是成果：它把"要不要为这个 patch 花一次设备点击"这个问题一次性地关掉了。

### 1.1 反汇编（`0x08A823F0`，明文）

```asm
0x08A823F0  stp   x19, x30, [sp, #-0x10]!
0x08A823F4  mov   x19, x0                       ; x19 = this (LoginTask)
0x08A823F8  mov   w0, #0x819B                   ; iFix token
0x08A823FC  mov   x1, xzr
0x08A82400  bl    #0x08F1C120                   ; -> IsPatched(mdef=154168)
0x08A82404  tbz   w0, #0, #0x08A82428          ; 未打补丁 -> 走原体
0x08A82408  mov   w0, #0x819B
0x08A8240C  mov   x1, xzr
0x08A82410  bl    #0x08F1C0A4                   ; -> GetPatch(mdef=154167)
0x08A82414  cbz   x0, #0x08A8243C
0x08A82418  mov   x1, x19
0x08A8241C  mov   x2, xzr
0x08A82420  ldp   x19, x30, [sp], #0x10
0x08A82424  b     #0x09406484                   ; -> __Gen_Wrap_4(mdef=138195)  尾调用
0x08A82428  ldr   w8, [x19, #0x10]              ; ★ this.loginState
0x08A8242C  cmp   w8, #2
0x08A82430  cset  w0, eq                        ; return (loginState == 2)
0x08A82434  ldp   x19, x30, [sp], #0x10
0x08A82438  ret
```

### 1.2 逐条回答 lead 的 5 问

**① 真实签名**：`bool get_IsLoginFinished()`，**返回 bool 不是枚举**，实现是 `loginState == 2`。
`loginState` 位于 `LoginTask` 实例偏移 **`0x10`**（4 字节，`ldr w8` 读取）。

**② `<A>` / `<B>` / `<C>` 反查结果**（用 `ba_ptrs.bin` 的 154,173 个方法指针反查）：

| 符号 | vaddr | 反查结果 |
|---|---|---|
| `<A>` | `0x08F1C120` | **`IsPatched`**，mdef **154168** |
| `<B>` | `0x08F1C0A4` | **`GetPatch`**，mdef **154167** |
| `<C>` | `0x09406484` | **`__Gen_Wrap_4`**，mdef **138195**（`b` 尾调用） |

⇒ 这是 **iFix 热更代理**（本工程 metadata 里本来就有一整套 `<>iFixBaseProxy_*` 符号）：
`if (IsPatched(token)) return GetPatch(token).Invoke(this); else 走原体`。
`0x819B` = **iFix 的 per-method token**（不是 type token；我试过按类型索引解出的是无关的 `<>c__DisplayClass114_0`，说明它属于 iFix 自己的表）。

**③ `movz w0,#imm16`**：立即数 = **`0x819B` = 33179**。同上，是 iFix token。

**④ 改成 `mov w0,#1; ret` 的语义**：恒返回 `true` = **"登录已完成"**，**不会**被判成"失败"（失败是 `loginState==3`，与这个 getter 无关）。
⇒ 语义上安全，不会反转。

**⑤ 谁在调它 —— ★ 这是本轮最重要的负面结论**

我对**整个 il2cpp section（148 MB，3700 万个 32 位字）**做了 BL/B 全量扫描
（`word & 0xFC000000 == 0x94000000` / `0x14000000`，`target = pc + sext(imm26)<<2`）：

```
调用 0x08A823F0 (IsLoginFinished)  → 无 BL/B 调用点
```

同一次扫描**正确**找到了其它两条链（见 §2），所以扫描器本身有效。

⇒ **结论（推断，强）：`get_IsLoginFinished` 没有任何直接调用点。**
最可能的解释是 IL2CPP 把它**内联**了（`ldr w8,[this,#0x10]; cmp w8,#2` 只有两条指令，极容易被内联到调用处）。
因此**在 `0x08A823F0` 上打 `mov w0,#1; ret`，很可能不会被任何代码执行到**。

> **建议：先不要为这个 patch 花掉设备上的一次点击。**
> 若要验证内联假设，最省的判据是：搜索全 section 里所有 `ldr w8,[Xn,#0x10]; cmp w8,#2` 相邻指令对
> （一条 `0x...F9400?08` + 紧随的 `7100081F`），命中数 = 内联点数量。这条我可以随时补。

### 1.3 `LoginState` 枚举真值（从 metadata 读出，非推断）

`LoginState` = type[3133]，`fieldStart=10991`，`field_count=5`：

| 字段 | 说明 |
|---|---|
| `value__` | 枚举底层字段 |
| **`Ready`** | **= 0** |
| **`Progress`** | **= 1** |
| **`Finished`** | **= 2** |
| **`Failed`** | **= 3** |

（值由 C# 枚举默认序列化规则推出：声明顺序即 0,1,2,3；且代码里 `cmp w8,#2` 与 `Finished` 对应，
与 metadata 的声明顺序 `Ready→Progress→Finished→Failed` 完全吻合 —— 双向印证。）

> 这也修正了我 48 号里的说法：`LoginState` **不是两个成员**，是**四个**。
> 48 号只看到 `Finished`/`Failed` 是因为当时扫的是 metadata 的**字符串堆片段**，而枚举成员名在字段表里。
> **48 号 §3 关于"没有进行中状态"的推论因此作废** —— 客户端是有 `Progress` 态的。

---

## §2 `AccountAuthStart` 调用图（任务 B）

### 2.1 结构：iFix dispatcher + 原体

`AccountAuthStart` @`0x08A8078C` 的前 0x80 字节是**和 `IsLoginFinished` 同款的 iFix 派发器**
（token = `0x816A`，`IsPatched` 判完不成立就跳 **`0x08A80880`**）。
⇒ **`0x08A80880` 才是 `AccountAuthStart` 的原体**。

### 2.2 原体里的关键调用（全 section 分支扫描结果）

```
BL @0x08A80A28  (AccountAuthStart + 0x29C)  →  0x08A80BA4 = StartRequestRelayPackets
```

`StartRequestRelayPackets` @`0x08A80BA4` 内部：

```
BL @0x08A80C40  (StartRequestRelayPackets + 0x9C)  →  0x08A82014 = co_RelayPacketsProcess
```

⇒ **调用图（确证，两个 BL 都是直接调用）**：

```
AccountAuthStart                    @0x08A8078C  （原体 0x08A80880）
  └─ BL 0x08A80A28 ──> StartRequestRelayPackets   @0x08A80BA4
        └─ BL 0x08A80C40 ──> co_RelayPacketsProcess @0x08A82014   （返回 IEnumerator，交给 StartCoroutine）
              └─ MoveNext @0x08A88E4C      ← 明文，可反汇编、可改
```

**这条链的意义**：`Account_Auth` 请求发出后，客户端立刻启动了**中继包队列协程**。
也就是说「Auth 之后干什么」不是等一个回调，而是**进入队列协程**。
这与 48 号的判断方向一致，但把落点从"未知"收紧到了 **`co_RelayPacketsProcess.MoveNext`**。

### 2.3 `co_RelayPacketsProcess.MoveNext` @`0x08A88E4C` 的结构（明文）

* 入口：大段静态初始化（`bl 0x63C72AC` × 30 余次），随后 `mov w8,#1; strb` 置初始化标志。
* 状态分发：`ldr w8,[x19,#0x10]`（`<>1__state`）→ `cmp w8,#4` → `b.hi` 到结束分支；
  然后是**字节跳转表**：`adrp x9,#0x2737000; add x9,x9,#0x949; ldrb w11,[x9,x8]; br`。
  ⇒ **5 态状态机（0..4）**。
* **3 个 `yield return` 点**（`str x0,[x19,#0x18]!` 写入 `<>2__current`，随后 `mov w0,#1` 返回）：

| yield | 地址 |
|---|---|
| #1 | `0x08A894F8` |
| #2 | `0x08A89574` |
| #3 | `0x08A89628` |

* **正常结束**：`0x08A8965C  ret`（`mov w0,wzr` → 返回 false）。
* **异常出口**：`0x08A89660  bl #0x63C73D0` —— 这是 il2cpp 的空引用抛出辅助函数；
  函数体里大量 `cbz x0, #0x08A89660` 都跳到它。
  ⇒ **这个协程里任何一个被解引用的对象为 null，都会抛 NRE 并让协程直接死掉**（Unity 日志关闭 ⇒ 完全静默）。

### 2.4 ★ 协程里有**显式调用 `OnLoginFail`** 的失败出口

```asm
0x08A89514  ldr   x8, [x19, #0x20]      ; 捕获字段（大概率是 LoginTask 引用）
0x08A89518  cbz   x8, #0x08A89660       ; null -> 抛 NRE
0x08A8951C  ldrb  w8, [x8, #0x10]       ; ★ 一个 **byte** 标志
0x08A89520  cbz   w8, #0x08A8958C       ; 标志 == 0 -> 跳到别处
0x08A89524  cbz   x20, #0x08A89660
0x08A89528  mov   x0, x20
0x08A8952C  bl    #0x08A8489C          ; ★★ OnLoginFail（mdef 20282）
0x08A89530  mov   w0, wzr
0x08A89534  b     #0x08A89644          ; return false，协程结束
```

**意义**：`OnLoginFail` 确实由这个协程调用，**条件是那个 byte 标志非 0**。
我们六轮都没看到弹窗 ⇒ 该标志一直为 0 ⇒ 协程走的是另一条路（继续 / 挂起 / 抛 NRE）。
**这条把"没调 OnLoginFail"从推断变成了可观测的结构事实。**

> 注：`ldrb` 读的是 1 字节，而 `loginState` 是 4 字节枚举 ⇒ **这个标志不是 `loginState`**。
> 与 LoginTask 已知字段名对照，最可能是 `errorExist`（metadata 里有这个字段名，`0x14059E`）。

---

## §3 密文块全局地图（任务 C）

方法：对 il2cpp section（`[0x064C1260, 0x0F2C000C)`，36,350 个 4KB 页）逐页统计 `ret` 次数。

```
pages total = 36350
含 >=1 条 ret = 28076  (77.2%)   ← 明文代码页
无 ret        =  8274  (22.8%)   ← 数据页 + 密文页
连续无-ret 段 = 2587 段，合计 32.32 MB（占 section 22.8%）
其中 >=4 页（16 KB）的段 = 583 段
```

**结论：密文不是"只有登录这一块"，而是全文散着很多块。**
（但 22.8% 的"无 ret"里混着大量**真实数据页**——il2cpp section 末尾有 metadata 指针表、
方法指针数组（`methodPointers` @`0x0FED01C0` 就在 section 内）、字符串池等，它们本来就没有 `ret`。
所以 22.8% 是**上界**，不是密文占比。）

**对齐特征**：所有块起止都落在 `...260` 相位上（因为 section 起点 `0x64C1260`），
即**与 4KB 页对齐**、而非与 16 字节对齐。这与 lead 观察到的"~6.4 KB 一块"在粒度上一致
（6.4 KB ≈ 1.6 页，说明**密文块边界不是页边界**，而是落在页内的某个偏移）。

**登录响应链的那一块**：`~0x08A82FF0`（最后一个合法 `b`）到 `0x08A8489C` 之后，约 6.4 KB。
它在我的页图里表现为 `0x08A83000`、`0x08A84000` 两页无 `ret`，而 `0x08A82000`、`0x08A7E000`–`0x08A7F000` 满 `ret`。

完整区间表：`report\_tmp\meta\cipher_blocks.txt`（2587 行，含每段的起止/页数/对齐标志）。

---

## §4 密文密码学尝试与结论（任务 D）

### 4.1 已排除

* **固定 4 字节 XOR**：lead 已试；我这里独立复核——四个密文函数的首字
  （`0x59CA769C` / `0x39CA765D` / `0x63D6CA28` / `0x63C9CA3A`）互不相同，
  而它们的**明文首指令极可能相同**（都是 `stp x29,x30,[sp,#-16]!` = `A9BF7BFD`）。
  同明文 → 不同密文 ⇒ **ECB 也被排除**（ECB 下相同首块必得相同密文）。

### 4.2 可以确定的结构线索

四个首字里 **第 3 字节恒为 `0xCA`**（`9C 76 **CA** 59` / `5D 76 **CA** 39` / `28 **CA** D6 63` / `3A **CA** C9 63`）。
若明文首字相同，则说明**keystream 的第 3 字节恒定** —— 这更像
**"每 16 字节块一个固定 key 位置"** 的块密码（CBC/CTR），而不是长流密码。
（样本只有 4 个，**置信度低**，仅登记为线索。）

### 4.3 结论

**没有突破。** 我没有找到可用的密钥/算法。
但可以给出一条**判别实验设计**（成本低、结论硬）：

> 找两个**首 16 字节明文必然相同**的方法（例如两个都是 `stp x29,x30,[sp,#-16]!` + `mov x19,x0` 开头的小 getter），
> 比较它们的密文首块：
> * 相同 ⇒ **ECB**（可直接按块查表爆破）
> * 不同 ⇒ CBC/CTR（需要 IV/计数器，静态难破）
>
> 目前手上 4 个样本首块都不同，但**无法确证**它们明文首块相同，所以还不能下结论。

---

## §5 `file_offset == vaddr`（任务 Q4）

`elf` 解析结果：

```
PT_LOAD (第 2 段)：p_offset = 0x059B8000, p_vaddr = 0x059B8000, p_filesz = 0x0990A410, flags=5(RX)
                 覆盖 vaddr [0x059B8000, 0x0F2C2410)
il2cpp section ：addr = 0x064C1260, off = 0x064C1260, size = 0x08DFEDAC
                 → 完全落在该 PT_LOAD 内，且 vaddr - offset = 0
```

⇒ **`file_offset = vaddr`（delta = 0），不需要任何换算。**

| 方法 | vaddr | **file_offset** |
|---|---|---|
| `AccountAuthStart` | `0x08A8078C` | `0x08A8078C` |
| `StartRequestRelayPackets` | `0x08A80BA4` | `0x08A80BA4` |
| `co_RelayPacketsProcess` | `0x08A82014` | `0x08A82014` |
| `<co_RelayPacketsProcess>d__60.MoveNext` | `0x08A88E4C` | `0x08A88E4C` |
| `IsLoginFinished` | `0x08A823F0` | `0x08A823F0` |
| `HandleAccountAuthResponseMessage` | `0x08A83440` | `0x08A83440`（密文） |
| `OnLoginFinish` | `0x08A836C0` | `0x08A836C0`（密文） |
| `ErrorAccountAuth` | `0x08A842BC` | `0x08A842BC`（密文） |
| `OnLoginFail` | `0x08A8489C` | `0x08A8489C`（密文） |

> 注意：**vaddr == 文件偏移只在 il2cpp 这个 PT_LOAD 内成立**。
> 第 5~8 个 PT_LOAD（`0x1024C000` 起）有 `vaddr - offset = 0x248000` 等非零差值，
> 若将来要改 `.rodata`/`.data` 里的东西，必须按各自的 PHDR 换算。

---

## §6 诚实标注

| 结论 | 状态 |
|---|---|
| 12 个目标地址的明文/密文判读（§0 表） | **确证**（`ret` 密度 + capstone 解码率，两种独立判据） |
| `get_IsLoginFinished` == `(loginState == 2)` | **确证**（反汇编直读） |
| `LoginState = {Ready=0, Progress=1, Finished=2, Failed=3}` | **确证**（metadata 字段表，与反汇编 `cmp #2` 互证） |
| `<A>/<B>/<C>` = `IsPatched`/`GetPatch`/`__Gen_Wrap_4` | **确证**（方法指针表反查） |
| `AccountAuthStart → StartRequestRelayPackets → co_RelayPacketsProcess` | **确证**（两处直接 BL，全 section 扫描） |
| `IsLoginFinished` 零直接调用点 ⇒ 被内联 | **推断（强）** —— 扫描器有效（同次扫到了其它链），但无法证明内联，只能说"无直接 BL/B 调用" |
| 协程里 `[x8+0x10]` 那个 byte 标志是 `errorExist` | **推断（中）** —— 靠字段名与类型宽度（1 字节）匹配，无直接证据 |
| 密文段"边界不与页对齐" | **推断（中）** —— 由 lead 的 6.4 KB 观测 + 我的页图推出 |
| §4 的密码学线索 | **未突破，置信度低**，仅为假设 |

---

## §7 对 lead 的建议（按性价比）

1. **不要先改 `IsLoginFinished`** —— 零调用点，极可能白改。
2. **改盯 `co_RelayPacketsProcess.MoveNext`**（`0x08A88E4C`，明文）：
   它有 3 个 yield + 1 个 `OnLoginFail` 出口 + 大量 NRE 抛出点。
   **下一步我可以给出三个 yield 各自返回的对象类型**（继续反汇编 `0x08A894xx`/`0x08A8955x`/`0x08A8961x` 前后各 30 条并反查符号）。
3. **一条便宜的判据**：既然协程有 `cbz x0 → 抛 NRE` 的密集模式，
   可以把 `0x08A89660`（`bl 0x63C73D0`）当作**"协程死因探针"**：
   若能把这条改成 `mov w0,wzr; b 0x08A89644`（跳过抛出、按结束处理），
   协程就会静默结束而不是抛异常 —— 这能区分"协程是抛异常死的"还是"卡在 yield 上"。
   **这是我在明文档里看到的最有诊断价值的一处可改点。**

---

# §8 第 8 轮追加：三个 yield 的对象、调用点、字段布局（问题 1/2/4/3）

## 8.1 问题 1 —— 三个 `yield` 分别等什么（**已定案：都不等服务端推送**）

对每个 `str x0,[x19,#0x18]!` 向前回溯，`x0` 的来源与类型如下（`bl` 目标已用方法指针表反查）：

| # | yield 地址 | `x0` 的来源调用 | 反查结果 | 语义 |
|---|---|---|---|---|
| **1** | `0x08A894F8` | `bl #0x07393564` | **`NetworkTaskManager.Request`**（mdef **65586**，declaringType = `NetworkTaskManager` type[9920]） | **发起并等待一次网络请求**（四个实参：`x0=任务对象, x1=taskQueue, x2=?, x3=null`） |
| **2** | `0x08A89574` | `bl #0x08A84A10` → `bl #0x0E6FD4F4` | `LoginTask.co_SyncShopListTutorialGacha`（mdef **20283**）→ **`StartCoroutine`**（il2cpp 辅助函数，无方法名） | `yield return StartCoroutine(co_SyncShopListTutorialGacha(...))` |
| **3** | `0x08A89628` | `bl #0x08A820BC` → `bl #0x0E6FD4F4` | `LoginTask.co_SyncTutorialCompletionIds`（mdef **20257**）→ **`StartCoroutine`** | `yield return StartCoroutine(co_SyncTutorialCompletionIds(...))` |

**⇒ 结论（确证）**：

1. **没有任何一个 yield 在等"服务端主动推送的一帧"。**
   三个 yield 依次是：**一个网络请求**、**一个客户端自发的同步协程**、**另一个客户端自发的同步协程**。
   **"回去补服务端推送能力"这条方向可以关闭。**
2. **谁能让它继续**：Unity 协程调度器。`yield return IEnumerator` 会被 Unity 当作**嵌套协程**每帧
   `MoveNext()` 一次；`yield #1` 返回的是 `NetworkTaskManager.Request(...)` 的迭代器，
   所以**继续的条件完全取决于那个迭代器什么时候返回 false**。
   （代码里紧跟 `str x0,[x19,#0x18]!` 的 `mov x1,x0; mov x0,x19; bl 0x63C7260` 就是
   il2cpp 存放嵌套枚举器的辅助函数，与"嵌套协程"语义一致。）
3. **卡死点因此收敛为一句话**：`co_RelayPacketsProcess` 卡在 `yield #1`，
   即 `NetworkTaskManager.Request(...)` 这个迭代器永远不结束。

### 8.1.1 `NetworkTaskManager` 的可读部分（`type[9920]`，15 个方法）

| mdef | 方法 | vaddr | 状态 |
|---|---|---|---|
| 65575 | `Start` | `0x0739E204` | 明文 |
| 65576 | `OnDestroy` | `0x0739E3AC` | 明文 |
| 65577 | `Init` | `0x0739E24C` | 明文 |
| 65578 | **`HandleTaskFinishedMessage`** | `0x0739E6B8` | **明文** |
| 65579 | `WaitOneFrameRequest` | `0x00000000` | **指针为空** |
| 65580 | `co_WaitOneFrame` | `0x0739E7F4` | 明文 |
| 65581 | `CreateTask` | `0x00000000` | **指针为空** |
| 65582 | `RequestCommon` | `0x00000000` | **指针为空** |
| 65583 | `RequestCommonAsync` | `0x00000000` | **指针为空** |
| 65584 | `ScheduleTask` | `0x00000000` | **指针为空** |
| 65585 | `TryAddComponent` | `0x00000000` | **指针为空** |
| **65586** | **`Request`** | `0x07393564` | **密文** |
| 65587 | `CoRequest` | `0x0739E8CC` | 明文（迭代器工厂） |
| 65588 | `.ctor` | `0x0739E9C8` | 明文 |
| 65589 | `<>iFixBaseProxy_OnDestroy` | `0x0739EA34` | 明文 |

**注意**：`WaitOneFrameRequest` / `CreateTask` / `RequestCommon` / `RequestCommonAsync` /
`ScheduleTask` / `TryAddComponent` 这 6 个方法的**方法指针是 0**。
这通常意味着它们是**泛型方法**或**被裁剪未实例化**——不能靠地址直接调用它们。

**已完成的部分**：`CoRequest` 反汇编显示它是**迭代器工厂**（`new` 一个对象、置 `<>1__state=0`、
把参数写进 `+0x20`/`+0x28` 字段后返回），说明 `Request` 家族走的是
"建任务对象 → 建迭代器 → 由 Unity 驱动"的模型，与 §8.1 的结论自洽。

## 8.2 问题 2 —— 三个 handler 的调用点（BL 全量扫描 + 指针值扫描）

| 方法 | vaddr | BL/B 调用点 | 作为 8 字节指针出现 |
|---|---|---|---|
| **`OnLoginFinish`** | `0x08A836C0` | **1 处：`0x08A8938C`**（在 `co_RelayPacketsProcess.MoveNext` 里，明文） | `0x1DF0110` |
| **`OnLoginFail`** | `0x08A8489C` | **1 处：`0x08A8952C`**（同一个协程，明文） | `0x1DF01E8` |
| `HandleAccountAuthResponseMessage` | `0x08A83440` | **0 处** | `0x1DF00F8` |
| `ErrorAccountAuth` | `0x08A842BC` | **0 处** | `0x1DF0158` |

### 8.2.1 ★ 最重要的重构：成功/失败的决定根本不在 `HandleAccountAuthResponseMessage` 里

`OnLoginFinish` 和 `OnLoginFail` 的**唯一调用点都在明文的 relay 协程**里，紧挨着：

```asm
; 成功路径
0x08A89380  bl  #0x0B1E38DC   ; -> UIManager.set_IsFirstEnterLobbyAfterLogin(true)
0x08A89388  mov x0, x20
0x08A8938C  bl  #0x08A836C0   ; -> LoginTask.OnLoginFinish
0x08A89390  b   #0x08A89530   ; -> mov w0,wzr; b 0x08A89644  (return false，协程正常结束)

; 失败路径
0x08A8951C  ldrb w8,[x8,#0x10]  ; 见 §8.3
0x08A89520  cbz  w8, 0x08A8958C
0x08A8952C  bl   #0x08A8489C    ; -> LoginTask.OnLoginFail
```

⇒ **`co_RelayPacketsProcess.MoveNext` 本身就是"登录成功/失败"的判决处**，
而且它在**明文区**、可反汇编、可改。
`HandleAccountAuthResponseMessage` 零 BL 调用点，说明它是**委托/回调/密文区调用**——
但**它是不是被调用，已经不影响这个判决结构**。

### 8.2.2 关于那组"恰好各出现一次的指针"

6 个方法地址（含 `AccountAuthStart`、`IsLoginFinished`）都各自在
`0x1DEFE10`–`0x1DF01E8` 区间内**恰好出现一次**（8 字节小端指针），且**顺序与 mdef 一致**。
但**间距与 mdef 不成 1:1**（`AccountAuthStart`(20241) 与 `IsLoginFinished`(20264) 差 23 个 mdef，
地址差 `0x228`=552 字节=69 个槽），所以**这不是主 `methodPointers` 数组**（那个在 `0x0FED01C0`）。
其身份**未确定**（可能是反射/热更用的方法指针镜像表），**不作为任何结论的依据**，仅登记。

## 8.3 问题 4 —— `+0x10` 那个 byte 根本不是 `loginState`（矛盾已消解）

### 8.3.1 `LoginTask` 的字段布局（metadata 字段表，确证）

`LoginTask` = type[3156]，`fieldStart=10989`，**`field_count=2`**（只有两个字段）：

| 字段 | 类型索引 | 推断偏移 | 依据 |
|---|---|---|---|
| `loginState` | 77543（`LoginState` 枚举） | **`0x10`** | il2cpp 对象头 0x10 字节；`get_IsLoginFinished` 里 `ldr w8,[x19,#0x10]` 直读 |
| `<WaitingTicket>k__BackingField` | 61196（引用类型） | **`0x18`** | int 占 4 字节 + 4 字节对齐填充后放下一个引用 |

### 8.3.2 `<co_RelayPacketsProcess>d__60` 的字段布局（6 个字段，确证）

| # | 字段 | 推断偏移 | 反汇编印证 |
|---|---|---|---|
| 0 | `<>1__state` | `0x10` | `str w9,[x19,#0x10]` @`0x08A8903C` |
| 1 | `<>2__current` | `0x18` | `str x0,[x19,#0x18]!`（三处 yield） |
| 2 | **`<>8__1`**（闭包/显示类） | **`0x20`** | `ldr x8,[x19,#0x20]` @`0x08A89514` |
| 3 | `<>8__2`（闭包/显示类） | `0x28` | — |
| 4 | **`<>4__this`**（= `LoginTask`） | **`0x30`** | `ldr x20,[x19,#0x30]` @`0x08A8901C` |
| 5 | `<taskQueue>5__2` | `0x38` | `str x22,[x21,#0x38]!` 区 |

### 8.3.3 结论

```asm
0x08A89514  ldr  x8, [x19, #0x20]   ; x8 = <>8__1  ← **闭包对象，不是 LoginTask**
0x08A8951C  ldrb w8, [x8, #0x10]    ; 读的是闭包里被捕获的一个 bool 局部变量
```

* `x19` 是**状态机**，不是 `LoginTask`；`[x19+0x20]` = `<>8__1`（编译器生成的显示类/闭包）。
* 那个 `ldrb` 读的是**闭包里捕获的 bool**（C# 里 `bool` 捕获后放在显示类里），
  与 `LoginTask+0x10` 的 `loginState`（4 字节枚举）**完全无关**。
* `LoginTask` 本体是通过 `<>4__this`（`[x19+0x30]`）取的，代码里 `mov x0,x20; bl OnLoginFail`
  的 `x20` 正是 `0x08A8901C ldr x20,[x19,#0x30]` 装进来的 ⇒ **x20 = LoginTask，自洽**。

⇒ **lead 指出的"Finished(2) 会被 ldrb 判成失败"的矛盾不存在** —— 两者读的不是同一个对象。
`+0x10` 在 `LoginTask` 上确实是 `loginState`（word），但在那个闭包上是一个捕获 bool（byte）。

## 8.4 问题 3 —— `AccountAuthStart` 是不是协程？谁在等响应？

* **不是协程**：`AccountAuthStart` 是普通方法，`ptrs` 里它的地址就是函数入口；
  类型表里**没有** `<AccountAuthStart>d__N` 这个嵌套类型（我把 35,105 个类型名全扫过，`AccountAuthStart` 子串 0 命中）。
  它同步执行完就 `ret`。
* **发起请求的是谁**：链路是
  `AccountAuthStart` → `StartRequestRelayPackets` → `StartCoroutine(co_RelayPacketsProcess)`
  → 协程里 `yield return NetworkTaskManager.Request(...)`。
  ⇒ **真正发请求的函数是 `NetworkTaskManager.Request`**（mdef 65586），
  **不是** `GameSessionManager.SendRequestApi`。
  （`Request` 本体是密文，无法确认它内部是否最终走到 `SendRequestApi`；
  但 `SendRequestApi` 出现在 `GameSessionManager` 类型里，而这里是 `NetworkTaskManager` 的独立任务管道——
  `LoginTask → NetworkTaskManager → (CreateTask/ScheduleTask/RequestCommon) → … → GameSessionManager → BestHTTP`
  这条**是推断，不是证据**。）
* **"等 auth 响应"由谁做**：不是 dispatcher，而是 **`yield #1` 的嵌套协程**
  （`NetworkTaskManager.Request` 返回的迭代器）。它结束 ⇒ 协程恢复 ⇒ 才轮到成功/失败判决。

---

## §8.5 第 8 轮后的优先级重排（给 lead）

| 优先级 | 事项 | 理由 |
|---|---|---|
| **1** | **反编译 `NetworkTaskManager.Request` 的迭代器**（`<Request>d__NN.MoveNext`） | 这是 §8.1 定下的唯一卡点。方法是密文，但它的**迭代器类型**可能在明文区，值得先查类型表定位再判明文/密文 |
| **2** | 若 `Request` 迭代器也全密文 ⇒ **只能运行时观测** | 静态到此为止 |
| 3 | `HandleTaskFinishedMessage`（`0x0739E6B8`，明文） | 任务完成走的是"消息"，这是完成信号的入口；可读出它检查哪些条件 |
| — | ~~`IsLoginFinished` 补丁~~ | **已否证**，零调用点 |
| — | ~~服务端主动推送~~ | **已否证**，三个 yield 无一是等推送 |

---

# §9 第 9 轮追加：`AccountAuthResponse` 精确字段表 + 一处**自我更正**

## 9.1 ★ 更正：我此前报的"客户端没有这些字段"是**假阴性**

在 47 号 §8 与 48 号 §4，我给出过"客户端**完全没有** `AttendanceBookRewards` /
`EncryptedUID` / `AccountRestrictionsDB` / `NewlyAddedShopCashIds`，四层全扫 0 命中"的结论。

**这个结论是错的。** 用正确解混淆后的 `md_deob.bin` 重读，这四个字段**都存在**，
就在 `AccountAuthResponse` 的字段表里（第 8、17、18、24 位）。

**错误原因（方法学教训，必须记下）**：
`global-metadata.dat` 的字符串堆有两层混淆：
1. 头 0x100 字节 XOR `0x66666666`；
2. **周期律**：`file_offset % 0x10000 ∈ [0x1000, 0x5000)` 的 16 KB 整块 XOR **`0x66`**。

我历次"多层 key 搜索"用的是 `{0x00, 0x20, 0x01, 0x0E}`（见 `s12_ident.py` 的 `LAYERS`），
**从来没有试过 `0x66`**。落在那 16 KB 周期块里的字段名因此对我完全不可见。
⇒ **凡是"某名字 0 命中"的结论，都必须先用 `md_deob.bin`（或加上 0x66 周期层）复核一次。**

## 9.2 `AccountAuthResponse` 完整字段表（确证）

* 类型：`MX.NetworkProtocol.AccountAuthResponse`，**type[10689]**
* `fieldStart = 48722`，**`field_count = 27`**（不是 47 号说的 20）
* 字段名全部是 `<X>k__BackingField` 形式 ⇒ 27 个都是 **auto-property 的 backing field**，即 27 个属性

| # | 字段 | typeIndex | 推断类型 |
|---|---|---|---|
| 1 | `CurrentVersion` | 50531 | long |
| 2 | `MinimumVersion` | 50531 | long |
| 3 | `IsDevelopment` | 37725 | bool |
| 4 | `BattleValidation` | 37725 | bool |
| 5 | `UpdateRequired` | 37725 | bool |
| 6 | `TTSCdnUri` | 61196 | string |
| 7 | `AccountDB` | 35066 | `AccountDB` |
| 8 | **`AttendanceBookRewards`** | 16346 | 集合 |
| 9 | **`AttendanceHistoryDBs`** | 16349 | 集合 |
| 10 | `RepurchasableMonthlyProductCountDBs` | 17028 | 集合 |
| 11 | `MonthlyProductParcel` | 16993 | 集合 |
| 12 | `MonthlyProductMail` | 16993 | 集合 |
| 13 | `BiweeklyProductParcel` | 16993 | 集合 |
| 14 | `BiweeklyProductMail` | 16993 | 集合 |
| 15 | `WeeklyProductParcel` | 16993 | 集合 |
| 16 | `WeeklyProductMail` | 16993 | 集合 |
| 17 | **`EncryptedUID`** | 61196 | string |
| 18 | **`AccountRestrictionsDB`** | 35136 | 对象 |
| 19 | `IssueAlertInfos` | 16826 | 集合 |
| 20 | `DailyRecordDBs` | 21742 | 集合 |
| 21 | `OptionDB` | 55122 | 对象/字典 |
| 22 | `IsArenaAnonymous` | 37725 | bool |
| 23 | `AccountLimitedFlashSaleDBs` | 21284 | 集合 |
| 24 | **`NewlyAddedShopCashIds`** | 22246 | 集合 |
| 25 | `IsNew` | 37725 | bool |
| 26 | `Desc` | 61196 | string |
| 27 | `FunctionClose` | 47095 | 对象/枚举 |

### 9.2.1 关于"偏移"与"类型名"的两条硬限制

* **偏移拿不到**：`Il2CppFieldDefinition` 只有 `{nameIndex, typeIndex, token}`（12 字节，与 field stride 12 吻合），
  **没有 offset**。字段偏移来自代码生成模块里的 `FieldOffsets` 表（在 libil2cpp 数据段），不在 metadata。
  ⇒ 本报告只能给**声明顺序**，给不了偏移。
* **类型名只能推断**：`typeIndex` 指向 metadata 的 `Il2CppType` 表。我在 header 的 35 个 `(offset,size)` 对里
  尝试用 `types[77543].data == 3133`（`LoginTask.loginState → LoginState`）做自校验定位该表，**12/16/24 字节三种步长都失败**，
  所以**没有解析出类型名字面量**。上表"推断类型"列是按 **typeIndex 聚类**推的（同一 typeIndex 在不同字段上反复出现 →
  该 typeIndex 是同一类型）。置信度：**中**。若要精确，需要另找 `Il2CppType` 表位置。

## 9.3 与 `report\49` 的 20 个属性逐条对照

| 49 号的字段 | 在 `AccountAuthResponse` 27 字段里？ |
|---|---|
| CurrentVersion / TTSCdnUri / AccountDB / OptionDB | ✅ 1 / 6 / 7 / 21 |
| EncryptedUID / AccountRestrictionsDB / AttendanceBookRewards / AttendanceHistoryDBs | ✅ 17 / 18 / 8 / 9 |
| RepurchasableMonthlyProductCountDBs + 6 个 Product{ Parcel, Mail } | ✅ 10–16 |
| IssueAlertInfos / AccountLimitedFlashSaleDBs / NewlyAddedShopCashIds | ✅ 19 / 23 / 24 |
| `Protocol` | ❌ 不在本类（在 `HttpMessage`，信封层） |
| `SessionKey` | ❌ **全库仍 0 命中**（这一点此前结论不变） |
| `AccountId` / `ServerNotification` / `ServerTimeTicks` / `StaticOpenConditions` | ❌ 不在本类 —— 都在信封基类 `ResponsePacket`（type[?]，`0x23019C` 一带） |

**客户端期望、我们没发的 9 个**：`MinimumVersion`、`IsDevelopment`、`BattleValidation`、`UpdateRequired`、
`DailyRecordDBs`、`IsArenaAnonymous`、`IsNew`、`Desc`、`FunctionClose`。

## 9.4 反序列化器与容忍度（3.2）

**库里同时存在两套 JSON 栈**（均在解混淆后的字符串堆里 0 命中以外的位置）：

| 名字 | 解混淆后偏移 |
|---|---|
| `Newtonsoft` | `0x002146CA` |
| `JsonConvert` | `0x006F72C2` |
| `JsonSerializer` | `0x006F8102` |
| `JsonSerializerSettings` | `0x006F8783` |
| **`MissingMemberHandling`** | `0x006F768B` |
| `JsonUtility`（Unity） | `0x007B32D9` |
| `System.Text.Json` | **NOT FOUND** |

**关键推断（中）**：`MissingMemberHandling` 这个**枚举类型名**出现在 metadata 里，
说明代码里**显式用过**这个开关（默认值是 `Ignore`）。

⇒ **`_probe` 这类多余键大概率不会导致反序列化失败**（除非被显式设成 `Error`）。
⇒ **真正会抛异常的是"类型不匹配"**：`string`↔`int`、`DateTime` 格式、字典键转枚举失败。
⇒ 因此 §9.5 的 `AccountAuthRequest` 字段表（客户端序列化约定）比"猜响应格式"更有价值。

## 9.5 `AccountAuthRequest` 字段表（3.3，客户端发出的那份，对照用）

`MX.NetworkProtocol.AccountAuthRequest`，type[10688]，`fieldStart=48706`，**16 个字段**：

```
 1 Version              2 DevId                3 IMEI                 4 AccessIP
 5 MarketId             6 UserType             7 AdvertisementId      8 OSType
 9 OSVersion           10 DeviceUniqueId      11 DeviceModel         12 DeviceSystemMemorySize
13 Token               14 SdkPid              15 SubChannel          16 ResUrl
```

**命名风格**：`PascalCase`、全部 backing field ⇒ **属性名即 JSON 键**（Newtonsoft 默认按属性名序列化）。
这与 `report\49` 里"客户端请求 `protocol` 用小写"不冲突 —— 那个是 **HTTP 表单字段名**，不是 DTO 属性。

**⇒ 响应 JSON 的键应该是 PascalCase**（`CurrentVersion` / `AccountDB` / …），
小写 `currentVersion` 在 Newtonsoft 默认设置下**也能匹配**（大小写不敏感），所以这不是风险点。

## 9.6 本轮结论的置信度

| 结论 | 状态 |
|---|---|
| `AccountAuthResponse` 有 27 个属性、字段名与顺序如上 | **确证**（字段表直读） |
| 我此前"4 个字段不存在"的说法是假阴性 | **确证**（同一个字段表里就在） |
| 字段类型（string/bool/long/int/DateTime/集合） | **推断（中）** —— typeIndex 聚类，未解析出字面类型名 |
| 字段偏移 | **取不到**（metadata 无 FieldOffsets） |
| 客户端用 Newtonsoft、且代码里出现过 `MissingMemberHandling` | **确证**（字符串存在） |
| "多余键会导致失败" | **不成立的可能性更大**（默认 Ignore），但**不能排除**代码设了 `Error` |

---

# §10 第 10 轮追加：成败判据的那条纽带（`cmp w8,#5`）

## 10.1 失败标志的写入点（确证）

lead 要的"把响应和成败判决连起来的唯一纽带"，在 `co_RelayPacketsProcess.MoveNext` 里找到了：

```asm
0x08A892AC  ldr  w8, [x8, #0x10]    ; x8 = [x19+0x28] = <>8__2（第二个闭包）的 int 字段
0x08A892B0  cmp  w8, #5
0x08A892B4  b.ne #0x08A89394        ; != 5 → 非失败路径
0x08A892B8  ldr  x8, [x19, #0x20]   ; x8 = <>8__1（装失败标志的闭包）
0x08A892BC  cbz  x8, #0x08A89660    ; null → 抛 NRE
0x08A892C0  mov  w9, #1
0x08A892C4  strb w9, [x8, #0x10]    ; ★ 失败标志 = 1（唯一写入点）
0x08A892C8  b    #0x08A8951C        ; → 失败判决 → bl OnLoginFail
```

⇒ **成败判据是一句话：请求结果里那个 int 是否等于 5。**
`== 5` → 置失败标志 → `OnLoginFail`；`!= 5` → 走另一条路（最终落到 `OnLoginFinish` 那一支）。

## 10.2 那个 int 可能是什么（推断，中）

`<>8__2` 是闭包对象，`+0x10` 是一个 int —— 最可能来自 `NetworkTaskManager.Request` 的结果状态。

**候选映射**：`NetworkService` 那组网络状态枚举有 8 个成员：

```
0 WAITING_SERVER_RESPONSE      4 SUCCESS
1 RECEIVED_SERVER_RESPONSE     5 CLIENT_NETWORK_NOT_REACHABLE
2 FILE_NOT_FOUND               6 SERVER_RESPONSE_ERROR
3 FAILED                       7 SERVER_NOT_RESPONSE
```

（顺序按 `0x219DB0`–`0x219E32` 在名字堆里的出现顺序，**不是**枚举值顺序）

若按 0 基编号，**5 = `CLIENT_NETWORK_NOT_REACHABLE`**。
⇒ 语义上：**只有 `SUCCESS`(4) 才算成功，5 被判为失败**。
⇒ 但我们的响应很可能让状态**停留在 0（`WAITING_SERVER_RESPONSE`）** ——
既不是 5、也不是 4，于是**判决永不发生，协程卡在 yield #1**。
这与全部现场观测（无弹窗 / 无第二次请求 / 无崩溃 / 无限等待）完全吻合。

> ⚠️ **这个枚举映射未经证实**（名字堆顺序 ≠ 枚举值顺序，而且我拿不到 `Il2CppType`/枚举常量表）。
> 它只是"最自洽的解释"，**不是结论**。

## 10.3 完整的因果链（当前最佳解释）

```
我们回 200 + CN 信封 + AccountAuthResponse JSON
  → NetworkTaskManager.Request<AccountAuthResponse> 反序列化
     → （若类型不匹配：Newtonsoft 抛异常 → 被 catch 吞掉，日志关闭 ⇒ 静默）
  → Task 永远不 Complete
     → 状态停留 WAITING_SERVER_RESPONSE(0)
  → co_RelayPacketsProcess 卡在 yield #1，永不恢复
     → 既不调 OnLoginFail（因为没到 cmp w8,#5 那条路）
     → 也不调 OnLoginFinish
  → 永久静默：无弹窗、无第二次请求、无崩溃
```

**这条链能同时解释 lead 列出的全部 4 条现象。** 但它仍是**推断**：
`NetworkTaskManager.Request` 的方法体与迭代器都在密文，看不到 `Task.Complete` 的写入点。

## 10.4 可以立刻做的两件零成本实验

1. **补齐 9 个"客户端有、我们没发"的字段**（默认值），并把 `AccountDB.LastConnectTime` / `CreateDate`
   保持 ISO 字符串（客户端那边是 `DateTime`）——这是唯一能排除"类型不匹配"的一发。
2. **验证 `cmp w8,#5` 那个 int 的来源**：如果 srv-ops 能在响应里加一个字段让客户端把状态置成 4，
   就能验证 10.2 的映射。但**该字段名未知**，所以这条目前只能靠运行时。

---

# §11 第 11 轮追加：`Equals` 全解 → "回显 protocol 认领会话"被证伪

## 11.1 定位与明文/密文（用 `ba_ptrs.bin`，不是字符串偏移）

| 类型 | 方法 | vaddr | 状态 |
|---|---|---|---|
| `HttpGameMessage`(type[9977]) | `Equals` | `0x06E12AF0` | **明文 1.00** |
| | `Equals(object)` | `0x06E12C58` | **明文 1.00** |
| | `GetHashCode` | `0x06E12CDC` | **明文 1.00** |
| | `op_Equality` | `0x06E12DE4` | **明文 1.00** |
| | `op_Inequality` | `0x06E12BD0` | **明文 1.00** |
| `HttpGameSession`(type[9981]) | `Equals` | `0x06E13E38` | **密文 0.00** |
| | `GetHashCode` | `0x06E13F9C` | **密文 0.00** |
| | `op_Equality` | `0x06E13FE4` | **密文 0.00** |
| `Http1Message`(type[9972]) | `Equals` | `0x06E0F37C` | **明文 1.00** |
| | `GetHashCode` | `0x06E0F500` | **明文 1.00** |

## 11.2 反汇编结论（明文，确证）

```asm
; op_Equality @0x06E12DE4
0x06E12E2C  cmp  x20, x19          ; ReferenceEquals(a,b)
0x06E12E30  b.eq 0x6e12e54         ;  -> return true
0x06E12E34  cbz  x20, ...          ; a==null -> return false
0x06E12E38  cbz  x19, ...          ; b==null -> return false
0x06E12E50  b    #0x6E12C58        ; 尾调用 Equals(object)
```

```asm
; Equals(HttpGameMessage other) @0x06E12AF0
0x06E12B58  cbz  x20, 0x6e12b98    ; other == null
0x06E12B64  ... ldrb w11,[x9,#0x12c]; ldrb w10,[x8,#0x12c]; cmp     ; is-a 类型检查
0x06E12B98  mov  x0, x20
0x06E12BA0  bl   op_Inequality(x20, null)   ; 只是空守卫
0x06E12BB8  b    #0x06E12C58                ; 尾调用 Equals(object)
```

```asm
; GetHashCode @0x06E12CDC
0x06E12D54  ldr  x0, [x19, #0x10]   ; ★ this.<message>（字符串）
0x06E12D5C  ldr  x8, [x0]           ; vtable
0x06E12D64  ldp  x9, x1, [x8, #0x158]
0x06E12D6C  blr  x9                 ; 虚调用该对象的 GetHashCode
```

**⇒ `HttpGameMessage` 的相等与哈希，全部作用在「包裹的那个字符串」上，完全没有碰 `Protocol`。**

## 11.3 为什么这是必然的：字段表

| 类型 | 字段数 | 字段 |
|---|---|---|
| `HttpGameMessage` | **2** | `<message>k__BackingField`、`disposed` |
| `Http1Message` | **2** | `<WebRequest>k__BackingField`、`disposed` |
| `HttpMessage`（基类） | 8 | `<Protocol>`、`<URL>`、`<MethodType>`、`<Parameter>`、`<BinaryData>`、`<RetryCount>`、`<EncodeRequest>`、`<BundleVersion>` |
| `HttpGameSession` | **19** | `id`、`httpMessage`、`<ResponseHandler>`、`<NetworkErrorHandler>`、`<RequestHandler>`、`state`、`<SessionId>`、`<Elapsed>`、`<TimeOut>`、`url`、`timeOut`、`requestPacket`、`bundleVersion`、`aesKey`、`aesIV`、`aesEncryptedKey`、`aesEncryptedIV`、`<IsGatewayBypassed>`、`retryCount` |

⇒ **两条通道的消息对象结构完全相同（都是 2 个字段、都不带 id）**，
说明"按消息对象/协议号认领会话"这条路在**两条通道上都不成立**。

## 11.4 `SessionId` 的来源：**静态不可判（正式结论）**

对 `HttpGameSession` 的 7 个 setter 做全 section BL/B 扫描：

| setter | vaddr | 自身可解率 | 直接调用点 |
|---|---|---|---|
| `set_SessionId` | `0x06E1339C` | 0.08 | **0** |
| `set_State` | `0x06E13274` | 0.00 | **0** |
| `set_ResponseHandler` | `0x06E1324C` | 0.00 | **0** |
| `set_NetworkErrorHandler` | `0x06E1325C` | 0.00 | **0** |
| `set_RequestHandler` | `0x06E1326C` | 0.00 | **0** |
| `set_Elapsed` | `0x06E133AC` | 0.08 | **0** |
| `set_TimeOut` | `0x06E133BC` | 0.08 | **0** |

⇒ 这些 setter 本身在密文区，调用方（`GameSessionManager.CreateSession` 等）也在密文区。
**`SessionId` 到底是 `Guid.NewGuid()` 自生成、还是从响应字段/header 取，静态无法回答。**
**这条路线到此为止，必须转运行时。**

## 11.5 `Guid` 存在性

`System.Guid` 精确串 **NOT FOUND**（正常——il2cpp 名字堆把命名空间与类型名分开存）；
但 `Guid`、`NewGuid`、`TryParse`、`GuidAttribute` 都在。
⇒ **客户端有 `Guid` 类型**，所以真服响应里那个 `"requestid":"94c7a6ee-…"` **有可能是客户端解析的**，
不能以"客户端没有 Guid"为由否掉。

## 11.6 `requestPacket` 的类型

`HttpGameSession` 第 13 个字段 `requestPacket`。
**类型名解析失败**：`Il2CppType` 表用 `types[77543].data==3133` 自校验，12/16/24 三种步长均未命中。
**推断（中）**：协议 DTO（`BasePacket`/`RequestPacket`/`ResponsePacket` 三个类型在 metadata 里确实存在）。

---

# §12 第 12 轮追加：用**反向搜索法**重验所有"字符串 0 命中"的否定结论

## 12.1 方法（lead 裁定，必须照做）

metadata 的字符串是**逐串一个随机单字节 XOR key**（实测到
`0x66 / 0x7F / 0x83 / 0x8B / 0x8C / 0x8F / 0xBD / 0x4E / 0xE9` 等多种）。
⇒ **「先统一解一层再 grep」必然产生假阴性**。
正确姿势：**拿候选明文，用 256 个 key 逐个加密，去原始 metadata 里搜**。
脚本：`report\_tmp\meta\s27_revsearch.py`（numpy 的 delta 技巧，一次扫完 256 key，38 MB 几十秒）。

## 12.2 复验结果（**多条旧结论被推翻**）

| 候选串 | 旧结论 | 复验结果 | 偏移 / key |
|---|---|---|---|
| **`requestid`** | 47 号：NOT FOUND | **存在** | `0x000DAB85` / `0x7F` |
| **`LocalizeConfig`** | 多处：NOT FOUND | **存在** | `0x000393F2` / `0x8B` |
| `ResUrls` | 41 号：NOT FOUND | **存在**（2 处） | `0x00091F1F` / `0x83`、`0x00091F26` / `0xBA` |
| `IsLocalize` | 同上 | **存在** | `0x000792F6` / `0x8C` |
| `GameMainConfig` | — | **存在** | `0x0006FEF5` / `0x8F` |
| `ServerInfoDataUrl` | — | **存在** | `0x00095EC7` / `0xBD` |
| `NpSN` | — | **存在** | `0x007DC7DB` / `0x4E` |
| **`NpToken`** | — | **确实不存在**（256 key 全试） | — |
| `AttendanceBookRewards` | 47/48 号：NOT FOUND | **存在**（4 处） | `0x00113A8B` / `0x66` |
| `SessionKey` | 47/48 号：NOT FOUND | **存在**（8 处） | `0x00104F31` / `0x66` |
| `AttendanceHistoryDBs` / `AccountRestrictionsDB` / `NewlyAddedShopCashIds` | 47/48 号：NOT FOUND | **存在**（字段表直读 + md_deob） | §9.2 |

## 12.3 三处对自己结论的正式更正

1. **`SessionKey` 存在**（`0x00104F31` / key `0x66`）。47/48 号那句
   "`SessionKey` 全库 0 命中，客户端没有这个属性"**作废**。
   ⚠️ **但要防止过度解读**：这个 `SessionKey` 出现在 `InteractiveWorldRaidCharacter`(type[323])、
   `InteractiveWorldRaidDesignLevel`、`MinigameInputHandler`、`EffectPlayer`、`SkillTimelinePlayer` 等类型上
   —— 是**玩法层**的"会话键"（关卡/小游戏里的会话），**与网关的登录会话 key 无关**。
   正确的结论是：**字符串存在，但不在 `AccountAuthResponse` 的 27 个字段里**，也不在认证链路上。
2. **`AttendanceBookRewards` 等 4 个字段存在**（§9.1 已述）。
3. **`requestid` 存在**（`0x000DAB85`）⇒ 客户端**确实有这个字面量**，
   "真服响应的 requestid 只是服务端跟踪号、客户端不读"这个猜测**不能成立**，
   **回显 requestid 是一条重新打开的方向**。

## 12.4 `NpToken` —— 唯一经得起 256 key 全扫的否定

`NpToken` 在 256 个单字节 key 下**全部 0 命中**（本方法的能力上限是"单字节 XOR"；
多字节/逐字符 keystream 仍可能藏着它）。这是本次复验里**唯一保住**的否定结论。

## 12.5 给后续所有人的告诫

> **凡"某字符串 0 命中"的结论，只要搜索时没有覆盖 256 个单字节 key，就一律不可信。**
> 本报告 §9 / §12 里被推翻的那 6~7 条，全部是同一个错误造成的。
> 正确工具：`report\_tmp\meta\s27_revsearch.py`（反向搜索）。

---

# §13 第 13 轮追加：昵称 / 呼叫名 / 登录同步 协议表

> 用户正卡在「请告知您的姓名」——即 `Account_Auth` 之后客户端认为账号无昵称。
> 本节给出这条链路上所有协议的**整数号 + 客户端 DTO 完整字段表**。

## 13.1 协议号（来源：本地 Shittim `ProtocolData.cs`，与客户端 DTO 类型名双向对上）

| 协议名 | 整数号 | Request 字段 | Response 字段 |
|---|---|---|---|
| **`Account_Nickname`** | **1001** | **`Nickname`（string）** | **`AccountDB`** |
| `Account_CallName` | **1010** | **`CallName`（string）** | **`AccountDB`** |
| `Account_LoginSync` | **1019** | **`SyncProtocols`（协议列表）、`SkillCutInOption`（string）** | **31 个**（§13.3） |
| `Character_List` | 2000 | — | — |
| `Equipment_List` | 3000 | — | — |
| `Item_List` | 4000 | — | — |
| `Echelon_List` | 5000 | — | — |
| `MemoryLobby_List` | 12000 | — | — |
| `Cafe_Get` | 20000 | — | — |
| `Attachment_Get` | 46000 | — | — |

客户端 DTO 类型（`MX.NetworkProtocol`，metadata 类型表直读，非字符串偏移）：

| 类型 | type index | field_count |
|---|---|---|
| `AccountNicknameRequest` | 10694 | **1**（`Nickname`） |
| `AccountNicknameResponse` | 10695 | **1**（`AccountDB`） |
| `AccountCallNameRequest` | 10696 | **1**（`CallName`） |
| `AccountCallNameResponse` | 10697 | **1**（`AccountDB`） |
| `AccountLoginSyncRequest` | 10716 | **2**（`SyncProtocols`、`SkillCutInOption`） |
| `AccountLoginSyncResponse` | 10717 | **31** |

> **Request/Response 都只有 1 个业务字段**。`Protocol` / `ServerTimeTicks` 等在
> 基类 `RequestPacket` / `ResponsePacket` 上 —— **body 里不要重复发**。

## 13.2 ★ 只做 `Account_Nickname` 会再卡一次

`LoginTask` 里存在 `SkipAccountCallname`（mdef **20277**），且客户端有
`UITitleCallNamePopup`、`UIPopup_Input_Callname`、`co_PlayCallName` ——
说明昵称之后还有**一步"呼叫名"弹窗**。

Shittim `AccountHandler.cs:253-263` 的做法是把两步合一：

```csharp
[ProtocolHandler(Protocol.Account_Nickname)]
account.Nickname = request.Nickname;
account.CallName = request.Nickname;                                   // ★
account.CallNameUpdateTime = account.GameSettings.CurrentDateTime.Date; // ★
```

`AccountDB` 的字段表里确实有 `Nickname`(第 2)、`CallName`(第 3)、`CallNameUpdateTime`(第 14，**DateTime**)。

⇒ **回 `AccountNicknameResponse` 时，`AccountDB` 必须同时填**
`Nickname` / `CallName`（= 昵称）/ `CallNameUpdateTime`（= 今天），客户端才会跳过呼叫名弹窗。
**这是防止第二次卡住的关键。**

## 13.3 `AccountLoginSyncResponse` 31 个字段（声明顺序）

```
 1 Responses                              17 ScenarioListResponse
 2 CafeGetInfoResponse                    18 ShopGachaRecruitListResponse
 3 AccountCurrencySyncResponse            19 TimeAttackDungeonLoginResponse
 4 CharacterListResponse                  20 BillingPurchaseListByYostarResponse
 5 EquipmentItemListResponse              21 EventContentPermanentListResponse
 6 CharacterGearListResponse              22 AttachmentGetResponse
 7 ItemListResponse                       23 AttachmentEmblemListResponse
 8 EchelonListResponse                    24 ContentSweepMultiSweepPresetListResponse
 9 MemoryLobbyListResponse                25 StickerListResponse
10 CampaignListResponse                   26 MultiFloorRaidSyncResponse
11 ArenaLoginResponse                     27 MultiFloorRaidLoginResponse
12 RaidLoginResponse                      28 FriendCount (long)
13 EliminateRaidLoginResponse             29 FriendCode (string)
14 CraftInfoListResponse                  30 PickupFirstGetHistoryDBs
15 ClanLoginResponse                      31 AccountLevelRewardIds
16 MomotalkOutlineResponse
```

`AccountLoginSyncRequest.SyncProtocols`（typeIndex 22624）是**客户端点名要哪几种子响应**。
⇒ **按它回，不要全发**：全发 = N 份大数据，且任一子 DTO 结构错就整包炸。

## 13.4 两个 sync 协程用的协议 —— **Shittim 里没有，是国服独有**

`co_SyncShopListTutorialGacha`(mdef 20283)、`co_SyncTutorialCompletionIds`(mdef 20257) 使用的协议：

| 协议名 | 整数号 | 说明 |
|---|---|---|
| `Shop_ListTutorialGacha` | **未知** | 客户端协议名表**最后 4 条**就是这一组 |
| `Shop_BuyTutorialGacha` | **未知** | Shittim `ProtocolData.cs` 里 grep `TutorialGacha` **0 命中** |
| `Shop_SaveTutorialGacha` | **未知** | ⇒ 国服特供 |
| `Shop_ConfirmTutorialGacha` | **未知** | 取号只能靠抓客户端请求 / 反编译（方法体大概率密文） |

DTO 字段表（metadata 直读）：

| Request | 字段 | Response | 字段 |
|---|---|---|---|
| `ShopListTutorialGachaRequest` | **0 个（空）** | `ShopListTutorialGachaResponse` | `MaxTimes`(int)、`LastTimes`(int)、`LastResults`(list)、`SaveTimes`(int)、`SaveResults`(list)、`ConfirmTimes`(int) |
| `ShopBuyTutorialGachaRequest` | **0 个（空）** | `ShopBuyTutorialGachaResponse` | `GachaTimes`(int)、`GachaResults`(list)、`AcquiredItems`(list) |
| `ShopSaveTutorialGachaRequest` | **0 个（空）** | `ShopSaveTutorialGachaResponse` | `SaveTimes`(int)、`SaveResults`(list) |
| `ShopConfirmTutorialGachaRequest` | `GachaTimes`(int) | `ShopConfirmTutorialGachaResponse` | `UpdateTime`(**DateTime**)、`GachaResults`(list)、`AcquiredItems`(list) |

**⇒ 工程建议**：在这 4 个号码拿到之前，
**bridge 对未知协议应回"空但合法"的 `ResponsePacket`（同号 + 只有 `Protocol` 字段），不要 404、不要不回**。
这是目前唯一能防止"昵称过了又卡在教程抽卡"的办法。

## 13.5 置信度

| 结论 | 状态 |
|---|---|
| `Account_Nickname=1001`、`Account_CallName=1010`、`Account_LoginSync=1019` | **确证**（Shittim 源码 + 客户端类型名） |
| 各 DTO 的字段名与个数 | **确证**（metadata 字段表） |
| 字段类型（string/int/DateTime/list） | **推断（中）**（typeIndex 聚类，同 §9.2 的限制） |
| 昵称必须顺带写 `CallName`/`CallNameUpdateTime` | **推断（强）**（Shittim 源码做法 + 客户端有 `SkipAccountCallname`） |
| 4 个 `Shop_*TutorialGacha` 的整数号 | **未知** |
