# 51 · 客户端补丁方案：在 `libil2cpp.so` 里绕过登录（强制成功）

> 目标：`com.RoamingStar.BlueArchive` 3.0.2 (versionCode 73) / Unity 2021.3.56f2 / il2cpp / arm64-v8a
> 目标文件：`work\ba\audit\ba-apk\lib\arm64-v8a\libil2cpp.so`（270,927,056 B，
> sha256 `5ac1cbe0fb8f730ffd22b93624a70ae9c90b0a1f3f3fbeb18c5d6af3c73882c3`，
> 与 `work\ba\audit\ba-work\x\lib\arm64-v8a\libil2cpp.so` 逐字节相同）
> 方法：纯离线静态分析。**没有碰手机，没有碰服务器。**
> 日期：2026-11-14

---

## 0. 一页结论

**1. 你给的那批偏移（`LoginTask@0x0013F654`、`OnLoginFinish@0x13FAF0`、`IsFinished@0x0021A583` 等）
全部是 `global-metadata.dat` 的字符串堆偏移，不是 `libil2cpp.so` 的代码地址。**
字节级铁证：`0x13FDDE` = `"Finished"`（8 字符 + 1 长度字节），`0x13FDE7` 恰好 = `0x13FDDE + 9` = `"Failed"`。
所以"按地址找 OnLoginFinish"这条路在起点上是空转的 —— 真正的代码地址本轮才第一次拿到。

**2. metadata 可以完整解析。** report/24、47、48 反复写的"表头混淆、`methodPointer` 不可得"是错的。
去混淆规律见 §2，解完后 30 个段的偏移首尾严丝合缝、三张表的条数
（35,105 类型 / 263,095 方法 / 191,990 字段）与各自的 `count` 字段精确相等。

**3. 已把"方法名 → 真实代码地址"打通**（全项目第一次）：
`Il2CppCodeGenModule(BlueArchive.dll)` @`0x0F90E080`，
`methodPointerCount = 154173`，`methodPointers = 0x0FED01C0`，
151,085 个非空项**全部**落在代码段 `[0x064C1260, 0x0F2C000C)` 内。

**4. `OnLoginFinish` 全库只有一个调用点**：`0x08A8938C`，
位于 `<co_RelayPacketsProcess>d__60.MoveNext`（mdef 20384，`0x08A88E4C`）里。
`OnLoginFail` 也只有一个调用点：`0x08A8952C`，在同一个函数里。→ 这就是登录的"最终闸门"。

**5. 但 `OnLoginFinish` 本体落在 ACE 加密页 `[0x08A83000, 0x08A87000)` 里，离线改不了。**
于是补丁一律走"**明文页 4 字节分支 + RX 段尾部代码洞**"，不碰加密页。

### 推荐的补丁

| 变体 | 改哪里 | 改什么 | 置信度 |
|---|---|---|---|
| **C（首选）** | `RequestAccountAuth` @`0x08A80458` | `b 0x0F2C2410`（代码洞） | **改动确定生效**（明文页、字节可验）；**能否进大厅：中（~50%）** |
| **E（叠加，低风险）** | `<co_RelayPacketsProcess>d__60.MoveNext+0x6E0` @`0x08A8952C` | `bl OnLoginFail` → `bl OnLoginFinish` | **改动确定安全**；只在走到失败分支时生效（低收益） |
| B（更粗） | `HandleAccountCheckYostarResponseMessage` @`0x08A806C8` | `b 0x0F2C2410` | 中偏低（跳过的状态更多） |
| A（下游） | `AccountAuthStart` @`0x08A8078C` | `b 0x0F2C2410` | 中偏低（**该函数在 auth 成功之后才被调到，卡在 auth 前就不会触发**） |
| Q（诊断） | `IsLoginFinished` @`0x08A823F0` | `mov w0,#1 ; ret` | 确定安全、确定无副作用，**但不推进流程** |

代码洞（`0x0F2C2410`，28 字节，RX 段尾部全零填充）：

```asm
stp  x19, x30, [sp, #-0x10]!
mov  x19, x0
bl   0x08A836C0            ; OnLoginFinish(this)
mov  w8, #2
str  w8, [x19, #0x10]      ; this.loginState = LoginState.Finished
ldp  x19, x30, [sp], #0x10
ret
```

脚本：`work\ba\bapatch\patch_login_bypass.py`（已跑通 patch → verify → rollback 全流程，
回滚后的 sha256 与原始文件逐字节相同）。

---

## 1. 先纠正四条前提（会直接影响后续所有人的动作）

### 1.1 `@0x0013F654` 系列是 metadata 字符串堆偏移

| 引用 | 实际是什么 | 证据 |
|---|---|---|
| `LoginTask@0x0013F654` | metadata 字符串堆里 `"LoginTask\0"` 的位置（堆基址 0x0EC9C8，相对 0x52C8C） | 直接读 `global-metadata.dat[0x13F654..]` 得 `LoginTask` |
| `LoginState@0x0013FDD3` | 同上，`"LoginState"` | 其后紧跟 `Finished`(0x13FDDE) 与 `Failed`(0x13FDE7)，间隔正好 9 = 1+8 字符 |
| `OnLoginFinish@0x13FAF0` | 同上，`"OnLoginFinish"` | — |
| `IsFinished@0x0021A583` | 同上，`"get_IsFinished"` | — |

⇒ **任何"把 0x0013xxxx 当函数地址去反汇编"的动作都必然读空。**（本轮之前所有相关推断都建立在这个误解上。）

### 1.2 `LoginState` 有 **4** 个成员，不是 2 个

`LoginState`（type idx **3133**，field 段 `10991..10996`）：

```
10991  value__
10992  Ready      = 0
10993  Progress   = 1
10994  Finished   = 2
10995  Failed     = 3
```

反汇编独立确认（这才是硬证据）：

```asm
IsLoginStarted  @0x08A823A0 : ldr w8,[x19,#0x10] ; cmp w8,#1 ; cset w0,eq
IsLoginFinished @0x08A823F0 : ldr w8,[x19,#0x10] ; cmp w8,#2 ; cset w0,eq
```

⇒ `LoginTask.loginState` 是 `this+0x10` 的 int32，**Finished == 2**。
（report/48 §0 说"只有 Finished/Failed 两个成员"是漏读，因为它只看了 0x13FDD3 之后的两条字符串。）

### 1.3 `HttpGameSession` **没有** `IsFinished` 成员

`HttpGameSession`（type idx 9981）全部 34 个字段与 36 个方法已列出，`IsFinished` 不在其中。
真正的主人：

| 方法 | mdef | 所属类型 | 地址 |
|---|---|---|---|
| `get_IsFinished` | 65973 | **`SessionStateChangedMessage`** | `0x06E131A8`（加密页） |
| `WaitForRequest` | 66007 | `HttpGameSession` | `0x06E13594`（加密页） |
| `get_State / set_State` | 65981/65982 | `HttpGameSession` | `0x06E13158 / 0x06E13274`（加密页） |

⇒ 任务里的**优先级 2（改 `WaitForRequest` 的 `IsFinished` 判定）不可行**：两个候选函数都在加密页，
而且 report/48 的"协程在等 IsFinished"这条推断本身归属就错了。

### 1.4 "改 `methodPointers` 指向代码洞"这条兜底方案，对**直接调用**无效

il2cpp 生成的 C++ 对非虚方法调用是**直接 `bl <函数绝对地址>`**（本轮实测：`OnLoginFinish` 的唯一
调用点就是 `bl #0x8a836c0`）。改 `methodPointers` 只影响
**委托 / 虚调用 / `il2cpp_runtime_invoke` / 反射**这一侧。
⇒ report/17:503 的"目标落在编码块内时改 `MethodInfo::methodPointer`"**只在被调用方是通过方法指针调用的前提下成立**。
本方案因此选择"改调用方入口 / 改调用点"，不依赖这条假设。

---

## 2. `global-metadata.dat` 去混淆（可复现）

文件：`work\ba\audit\ba-work\x\assets\bin\Data\Managed\Metadata\global-metadata.dat`（38,426,024 B）

### 2.1 两层编码

| 层 | 范围 | 规则 |
|---|---|---|
| L1 头部 | `[0x000, 0x100)` | 每 4 字节 `XOR 0x66666666` |
| L2 全文件 | 每个 64 KB 周期 | 块内偏移 `[0x1000, 0x5000)` 的 **16 KB 全部 `XOR 0x66`**，其余原样 |

L2 的判据（整文件 4 KB 分块统计，与内容无关）：

```
(off mod 0x10000)/0x1000 = 1..4  → 0x66 字节密度 0.30
其余 slot                        → 0.003
```

> 这就是 report/11 记的"存在 key=0x00 与 key=0x66 两类区段"的真相：
> 不是"区段"，是**全局周期律**。同理，`global-metadata.dat` 里那些"每串独立 XOR key"的字面量
> （如 IV `JOSYdf8ys97uhFYS` 的 0xE9 / 0x66）是**第三层、只作用于字面量数据区**，与表结构无关。

### 2.2 解完之后的表（自洽性验证）

| 表 | 偏移 | 字节数 | 步长 | 条数 | 校验 |
|---|---|---|---|---|---|
| stringLiteral | 0x000100 | 197,824 | 8 | 24,728 | — |
| stringLiteralData | 0x0305C0 | 771,080 | — | — | — |
| string（名字堆） | 0x0EC9C8 | 7,109,768 | — | — | — |
| methods | 0x8B2C14 | 9,471,420 | **36** | **263,095** | `sum(method_count)` = 263,095 ✅ |
| fields | 0x1B17590 | 2,303,880 | **12** | **191,990** | `sum(field_count)` = 191,990 ✅ |
| typeDefinitions | 0x1F02148 | 3,089,240 | **88** | **35,105** | — |
| images | 0x21F44A0 | 4,120 | **40** | 103 | 名字全可读（`BlueArchive.dll` … `__Generated`） |

`stringOffset = stringLiteralDataOffset + stringLiteralDataCount` 等 30 条相邻段全部首尾相接
（仅 2 处 4 字节对齐填充）。**这不可能靠巧合成立。**

`magic` 与 `version` 解完仍是 `0x741425F2 / 0x8AF82D7E`——那是**故意留的假值**（挡 Il2CppDumper 的第一步），
但后续字段全是真的。若想喂 Il2CppDumper，把 magic 改 `0xFAB11BAF`、version 按
`typeDef=0x58 / method=0x24 / field=0x0C / image=0x28` 试 27 / 29 / 31 即可（本方案不需要，未做）。

脚本：`report\_tmp\patch\md_head.py`、`md_types2.py`、`md_pages.py`、`md_66map.py`、`md_law.py`、`md_parse.py`、
`md_methods.py`、`md_m2.py`、`md_lookup.py`；产物 `report\_tmp\patch\md_deob.bin`（去混淆后的 38 MB 全文）。

---

## 3. 方法名 → 代码地址（本项目的关键基础设施）

### 3.1 `Il2CppCodeGenModule` 定位

`libil2cpp.so` 段落（readelf 级别，`shoff=0x1025FE90`）：

| 段 | vaddr | 大小 |
|---|---|---|
| `.text` | `0x059B8000` | 11,571,808 |
| `il2cpp`（游戏代码主体） | `0x064C1260` | 148,906,412 |
| `.plt` | `0x0F2C0010` | 9,216 |
| `.data.rel.ro` | `0x0F2C4000` | 7,780,472 |
| `.got` | `0x0FA2FD18` | 1,569,096 |

`BlueArchive.dll` 的 codegen module（由 `codeGenModules[]` 数组里唯一一个"名字指针为 NULL"的
槽位 `0x0FC10F00` 反查到）：

```
module struct          @0x0F90E080
+0x00 moduleName       = 0x02651D93（指针非空但该字符串不在文件里，这就是它躲过第一轮枚举的原因）
+0x08 methodPointerCount = 154173
+0x10 methodPointers   = 0x0FED01C0
```

**索引关系：`methodPointers[mdef]`（mdef = metadata 方法索引）**，两条独立验证：

1. `methodPointerCount = 154173` **精确等于** image 0（`BlueArchive.dll`）的 methodDef 区间 `[0, 154173)`；
2. 数组项与 mdef 单调同增（151,085 个非空项里 90% 的相邻项递增），且 151,085 项**全部**落在
   `[0x064C1260, 0x0F2C000C)` 之内。

地址取值方式：`.rela.dyn`（1,526,842 项）里 `r_offset` 落在该数组内的
`R_AARCH64_RELATIVE(1027)` 项，其 `addend` 就是代码地址（运行时由 linker 写入 `base+addend`）。

产物：`report\_tmp\patch\ba_ptrs.bin`（154,173 × u64，全量地址表，可直接复用）。

### 3.2 登录相关函数地址表（**这是本轮最重要的产出**）

| 方法 | mdef | 地址(vaddr) | 所在页 |
|---|---|---|---|
| `LoginTask.CheckContinueCampaign` …（略） | — | — | — |
| `LoginTask.get_WaitingTicket` | 20231 | `0x08A7F04C` | 明文 |
| `LoginTask.Initialize` | 20233 | `0x08A7F05C` | 明文 |
| `LoginTask.ErrorQueuingGetTicket` | 20235 | `0x08A7FAF0` | 明文 |
| `LoginTask.HandleQueuingGetTicketResponseMessage` | 20236 | `0x08A7FD6C` | 明文 |
| `LoginTask.ErrorAccountPassCheck` | 20237 | `0x08A802C4` | 明文 |
| `LoginTask.HandleAccountPassCheckResponseMessage` | 20238 | `0x08A80394` | 明文 |
| `LoginTask.ErrorAccountCheckYostar` | 20239 | `0x08A805F8` | 明文 |
| **`LoginTask.HandleAccountCheckYostarResponseMessage`** | 20240 | **`0x08A806C8`** | 明文 |
| **`LoginTask.AccountAuthStart`** | 20241 | **`0x08A8078C`** | 明文 |
| `LoginTask.StartRequestRelayPackets` | 20256 | `0x08A80BA4` | 明文 |
| `LoginTask.IsLoginStarted` | 20263 | `0x08A823A0` | 明文 |
| **`LoginTask.IsLoginFinished`** | 20264 | **`0x08A823F0`** | 明文 |
| `LoginTask.StartLoginWithAccountCheckYostar` | 20265 | `0x08A82440` | 明文 |
| `LoginTask.StartLogin` | 20275 | `0x08A8258C` | 明文 |
| **`LoginTask.HandleAccountAuthResponseMessage`** | 20272 | **`0x08A83440`** | **加密** |
| **`LoginTask.OnLoginFinish`** | 20273 | **`0x08A836C0`** | **加密** |
| **`LoginTask.ErrorAccountAuth`** | 20276 | **`0x08A842BC`** | **加密** |
| **`LoginTask.OnLoginFail`** | 20282 | **`0x08A8489C`** | **加密** |
| `LoginTask.co_RelayPacketsProcess`（迭代器工厂） | 20281 | `0x08A82014` | 明文 |
| **`<co_RelayPacketsProcess>d__60.MoveNext`** | 20384 | **`0x08A88E4C`** | 明文 |
| `HttpGameSession.WaitForRequest` | 66007 | `0x06E13594` | 加密 |
| `HttpGameSession.get_State` | 65981 | `0x06E13158` | 加密 |
| `SessionStateChangedMessage.get_IsFinished` | 65973 | `0x06E131A8` | 加密 |

完整 72 条 `LoginTask` 方法地址：`report\_tmp\patch\logintask_addrs.json`。

---

## 4. 代码页加密分布（决定了"哪些补丁点能做"）

`libil2cpp.so` 里 `.text + il2cpp` 共 39,177 个 4 KB 页，其中 **13,383 页（34.2%）在磁盘上不是可执行代码**
（ACE 编码块，加载时由 `libtprt` 还原）。判据（与内容无关、可复算）：

```
页内 0xC0035FD6(ret) 计数 = 0
且"每个 4 字节字最高字节 ≥ 0x80"的比例从正常代码的 ~85% 掉到 18~42%
```

登录这一簇的加密块是 **`[0x08A83000, 0x08A87000)`（4 页 = 16 KB）**，它一口气吃掉了：

* `HandleAccountAuthResponseMessage`（0x08A83440）
* **`OnLoginFinish`（0x08A836C0）**
* `ErrorAccountAuth`（0x08A842BC）
* **`OnLoginFail`（0x08A8489C）**
* `StartLoginWithAccountPassCheck` / `SkipAccountCallname` / `onCreateStateEnd` /
  `HandleAccountCallnameResponseMessage` / `co_SyncShopListTutorialGacha` / `.ctor` / 全部 `b__` lambda

⇒ **任务里的优先级 1、3 都不能用"原地改函数体"实现**（改出来的字节在加载时会被 ACE 覆盖）。
**优先级 1 改用"改调用侧"实现**（下面 §5），优先级 3 直接作废。

---

## 5. 关键发现：`OnLoginFinish` / `OnLoginFail` 的唯一调用点

全库 67,731,764 个 4 字节字做 `bl` 目标统计（numpy 全量扫描）：

| 目标 | 直接调用点 |
|---|---|
| `OnLoginFinish` `0x08A836C0` | **只有 1 处：`0x08A8938C`** |
| `OnLoginFail` `0x08A8489C` | **只有 1 处：`0x08A8952C`** |
| `RequestAccountAuth` `0x08A80458` | 2 处：`0x08A80448`（`HandleAccountPassCheckResponseMessage` 尾）、`0x08A8077C`（`HandleAccountCheckYostarResponseMessage` 尾） |
| `AccountAuthStart` `0x08A8078C` | **0 处**（只能通过委托/方法指针调到） |
| `HandleAccountCheckYostarResponseMessage` `0x08A806C8` | **0 处**（同上，网络回调表） |
| `IsLoginFinished` `0x08A823F0` | 0 处（UI 侧经方法指针调用） |

两个调用点都落在 `<co_RelayPacketsProcess>d__60.MoveNext`（`0x08A88E4C`）里，形态是：

```asm
; 成功出口（+0x540）
08A89384  cbz  x20, 0x8A89660
08A89388  mov  x0, x20
08A8938C  bl   #0x8A836C0        ; OnLoginFinish
08A89390  b    #0x8A89530

; 失败出口（+0x6E0）
08A89514  ldr  x8, [x19, #0x20]  ; <>8__1（闭包：errorExist / queueState）
08A8951C  ldrb w8, [x8, #0x10]   ; if (errorExist == 0) ...
08A89520  cbz  w8,  #0x8A8958C
08A89524  cbz  x20, 0x8A89660
08A89528  mov  x0, x20
08A8952C  bl   #0x8A8489C        ; OnLoginFail
```

这条链同时**证伪了 report/48 的 S2 假设措辞**：`co_RelayPacketsProcess` 确实是"串行任务队列"，
但它不是"卡住就静默"——它的两个出口**都**在同一个 `MoveNext` 里，而且都调用了结局函数。
真正的"静默"只可能发生在它 `yield` 出去之后再也没被恢复（即队列里某个 task 永不完成）。

---

## 5.5 一个必须先说清的坑：这些函数是 **IFix 桩**，不是完整函数体

本轮最容易被后来人读错的发现：**本包启用了 IFix 热更框架**（image 表里有 `IFix.Core.dll`，
且 `HttpGameSession` 等类里有编译器生成的 `<>iFixBaseProxy_Equals` 方法）。

IFix 会把每个被纳入热更范围的方法的**入口改写成"懒初始化 + 尾调 `ILFixDynamicMethodWrapper`"**：

```asm
; RequestAccountAuth 的桩 @0x08A80458
08A80458  str x24,[sp,#-0x40]! ...      ; 保存寄存器
08A804BC  mov w0,#0x80cb                ; 类初始化 token
08A804C4  bl  0x8F1C120                 ; IL2CPP_RUNTIME_CLASS_INIT 检查
08A804F4  b   0x09406304                ; 尾调 __Gen_Wrap_2  ← 真正的分发点
08A804F8  ...                           ; ← 原始方法体（明文，紧跟在桩后面）
```

验证（**返回类型逐一吻合**，这是"我认对了函数"的最强证据）：

| 桩入口 | 尾调目标 | 目标签名 | 对应 metadata 里该方法的 `retType` |
|---|---|---|---|
| `RequestAccountAuth` `0x08A80458` | `ILFixDynamicMethodWrapper.__Gen_Wrap_2` (mdef 138193, `0x09406304`) | `void` | `System.Void` ✅ |
| `AccountAuthStart` `0x08A8078C` | 同上 `__Gen_Wrap_2` | `void` | `System.Void` ✅ |
| `HandleAccountCheckYostarResponseMessage` `0x08A806C8` | `__Gen_Wrap_18` (mdef 138209, `0x09406FC8`) | `bool` | `bool` ✅ |

**对补丁的影响（三条）**：

1. **桩入口就是所有直接 `bl` 的落点** ⇒ 在桩入口打 `b` 一定能截到（本方案的 C/B/A 都打在桩入口，正确）。
2. **原始函数体在桩后面、仍在明文页**（`RequestAccountAuth` 体 @`0x08A804F8`、`AccountAuthStart` 体 @`0x08A80880`）
   —— 本轮 6.3/6.4 里"它调了 `ShowNicknamePopup` / `StartRequestRelayPackets`"的判断，读的正是这些原始函数体。
3. **`__Gen_Wrap_*` 本身在 ACE 加密页**（`0x09406304`、`0x09406FC8` 均为加密页），所以"改转发点"不可行；
   要改只能在桩入口改 —— 也就是本方案的做法。

> 这条同时解释了一个此前没人注意的事实：`libil2cpp.so` 里同一条"方法"有**两份代码**
> （桩 + 原始体），体积因此偏大；凡是"按 `ret` 扫函数边界"的做法都会在这里出错。

---


> 下面所有"before"字节都是从**原始文件**读出来的（脚本里做 expected-byte 校验，不符即拒绝写盘）。

### 6.1 变体 C（**首选**）：`RequestAccountAuth` 入口 → 代码洞

* 地址：`0x08A80458`（明文页），mdef 20253，签名 `void RequestAccountAuth(...)`（`retType = System.Void`）
* 为什么选它：它是**唯一被直接调用、且确定在 Account_Auth 这条路上**的函数
  （`HandleAccountCheckYostarResponseMessage` 的成功尾分支 `0x08A80778..0x08A80784` 就是
  `mov x0,x19 ; bl RequestAccountAuth ; mov w0,#1`）。
  客户端**确实发出了** `POST /api/account/auth`，所以它**确定被执行过**。

汇编原文（前 4 条）：

```asm
08A80458  str  x24, [sp, #-0x40]!     ; f8 0f 1c f8
08A8045C  stp  x23, x30, [sp, #0x10]  ; f7 5b 01 a9
08A80460  stp  x21, x20, [sp, #0x20]  ; f5 53 02 a9
08A80464  stp  x19, x30, [sp, #0x30]  ; f3 7b 03 a9
```

| | 字节 |
|---|---|
| before | `f8 0f 1c f8 f7 5b 01 a9 f5 53 02 a9 f3 7b 03 a9` |
| after  | `9a 0c 00 14`（= `b 0x08A836C0`，仅覆盖第 1 条） |

副作用：
* 跳过 Account_Auth 应答 → Nickname 弹窗 → RelayPackets 三段；`OnLoginFinish` 会在
  `HandleAccountCheckYostarResponseMessage` 的返回路径上**同步**执行。
* `x0` 进入时是 `LoginTask*`（实例方法），正是 `OnLoginFinish` 需要的东西。
* 原函数后续 4 条 prologue 不再执行（我们直接改写了入口，栈帧由代码洞自己建/拆），**不会栈失衡**。
* 若 `OnLoginFinish` 依赖 auth 应答里的 `AccountDB/OptionDB` 等对象 → 可能 NRE。
  **这是本方案唯一的实质风险点**，见 §10。

**置信度：改动确定生效（字节级 + 明文页 + 无 hash pin）；能否进大厅：中（~50%）。**

### 6.2 变体 E（叠加，低风险）：把状态机唯一的失败出口改成成功出口

* 地址：`0x08A8952C`（明文页），在 `MoveNext` 内，`+0x6E0`

| | 字节 |
|---|---|
| before | `dc ec ff 97`（`bl 0x08A8489C` = `OnLoginFail`） |
| after  | `65 e8 ff 97`（`bl 0x08A836C0` = `OnLoginFinish`） |

副作用：只把"失败结局"换成"成功结局"。`OnLoginFinish` 与 `OnLoginFail` 都是 `(this)` 单参、
均返回 `void`，寄存器合同一致；`x20` 就是 `LoginTask*`（`mov x0,x20` 已在上一句）。
**不会崩**，但如果协程根本没走到这个分支（大概率），它**也不会被触发**。

**置信度：改动确定安全（高）；功效低（只兜住"走到失败出口"的情形）。**

### 6.3 变体 B（更粗）：`HandleAccountCheckYostarResponseMessage` 入口 → 代码洞

* 地址：`0x08A806C8`（明文页），mdef 20240

汇编原文：

```asm
08A806C8  stp  x21, x20, [sp, #-0x20]!   ; f5 53 be a9
08A806CC  stp  x19, x30, [sp, #0x10]     ; f3 7b 01 a9
08A806D0  adrp x21, #0x10256000          ; b5 be 03 d0
08A806D4  ldrb w8, [x21, #0xc19]         ; a8 66 70 39
```

| | 字节 |
|---|---|
| before | `f5 53 be a9 f3 7b 01 a9 b5 be 03 d0 a8 66 70 39` |
| after  | `fe 0b 00 14`（= `b 0x08A836C0`） |

副作用：比 C 更早（连 Auth 请求都不发）。`x0 = LoginTask*`、`x1 = AccountCheckYostarResponseMessage*`；
`OnLoginFinish` 只用 x0，多余参数无害。
跳过的状态更多（Auth 应答、昵称、RelayPackets 全不执行），**NRE 概率高于 C**。

**置信度：改动确定生效；能否进大厅：中偏低（~35%）。**

### 6.4 变体 A（下游）：`AccountAuthStart` 入口 → 代码洞

* 地址：`0x08A8078C`（明文页），mdef 20241

汇编原文：

```asm
08A8078C  sub  sp, sp, #0x40            ; ff 03 01 d1
08A80790  str  x22, [sp, #0x10]         ; f6 0b 00 f9
08A80794  stp  x21, x20, [sp, #0x20]    ; f5 53 02 a9
08A80798  stp  x19, x30, [sp, #0x30]    ; f3 7b 03 a9
```

| | 字节 |
|---|---|
| before | `ff 03 01 d1 f6 0b 00 f9 f5 53 02 a9 f3 7b 03 a9` |
| after  | `cd 0b 00 14`（= `b 0x08A836C0`） |

⚠️ **重要判读**：`AccountAuthStart` 体内依次调用了 `ShowNicknamePopup`（`0x08A809C0 → 0x08A80A84`）
和 `StartRequestRelayPackets`（`0x08A80A28 → 0x08A80BA4`）——
也就是说它是 **auth 成功之后**那段流程的入口（名字有误导性），
**大概率由 `HandleAccountAuthResponseMessage`（加密块）里的委托调到**。
若客户端就卡在"不会走到 HandleAccountAuthResponseMessage"，**本补丁不会触发**。

**置信度：改动确定生效；触发概率存疑（这也是把它排在 C 之后的原因）。**

### 6.5 变体 Q（诊断，无害）：`IsLoginFinished` 恒返回 true

* 地址：`0x08A823F0`（明文页），mdef 20264

```asm
08A823F0  stp  x19, x30, [sp, #-0x10]!  ; f3 7b bf a9
08A823F4  mov  x19, x0                  ; f3 03 00 aa
```

| | 字节 |
|---|---|
| before | `f3 7b bf a9 f3 03 00 aa` |
| after  | `20 00 80 52 c0 03 5f d6`（`mov w0,#1 ; ret`） |

副作用：只影响"查询登录是否完成"的调用方（UI/流程判定），**不会推进任何网络/状态机**。
适合作为"确认补丁有没有被加载"的探针（打上它之后，若某处 UI 行为变化，说明 so 真的被换了）。

**置信度：改动确定安全（高）；对登录成功无帮助（低）。**

### 6.6 代码洞（变体 A/B/C 共用）

* 地址 `0x0F2C2410`，位于 `.plt`（止于 `0x0F2C2410`）与 `.data.rel.ro`（起于 `0x0F2C4000`）之间的
  **全零填充**，落在 `PT_LOAD (flags=5 = R+X)` 段 `[0x059B8000, 0x0F2C8410)` 内 ⇒ 可执行、可离线写。
  可用长度 `0x0F2C2410..0x0F2C3000` = 3056 B（本项目 report/17 曾在此放过 1111 B 探针，实测可用）。

原始：28 × `00`；补丁后（28 B）：

```asm
0F2C2410  stp  x19, x30, [sp, #-0x10]!   ; f3 7b bf a9
0F2C2414  mov  x19, x0                   ; f3 03 00 aa
0F2C2418  bl   #0x08A836C0               ; aa 04 5f 96
0F2C241C  mov  w8, #2                    ; 48 00 80 52
0F2C2420  str  w8, [x19, #0x10]          ; 68 12 00 b9
0F2C2424  ldp  x19, x30, [sp], #0x10     ; f3 7b c1 a8
0F2C2428  ret                            ; c0 03 5f d6
```

设计要点：
1. **先调 `OnLoginFinish`，后强写 `loginState = 2`**。反过来的话，若 `OnLoginFinish` 开头有
   `if (IsLoginFinished()) return;` 之类的短路，就会被我们抢先设成 Finished 而整段跳过。
2. 用 `x19` 保存 `this`，因为 `bl` 会破坏 caller-saved 寄存器。
3. 结尾 `ret` 直接返回到"调用 `AccountAuthStart`/`RequestAccountAuth`/handler 的那一层"，
   相当于一次**尾调用语义的替换**，不破坏任何栈帧。

---

## 7. 补丁脚本

`work\ba\bapatch\patch_login_bypass.py`（Python 3，无第三方依赖）

```powershell
# 看站点表（地址/前后字节/汇编）
python work\ba\bapatch\patch_login_bypass.py --list

# 打首选补丁（C）
python work\ba\bapatch\patch_login_bypass.py -i libil2cpp.so -o libil2cpp_patched.so -v C

# 叠加 E（推荐组合 CE）
python work\ba\bapatch\patch_login_bypass.py -i libil2cpp.so -o libil2cpp_patched.so -v CE

# 校验文件是否处于该补丁态
python work\ba\bapatch\patch_login_bypass.py -i libil2cpp_patched.so --verify -v C

# 回滚（逐字节还原 + 打印 sha256）
python work\ba\bapatch\patch_login_bypass.py -i libil2cpp_patched.so -o restored.so --rollback -v C
```

内建保护：
* `sha256` 与 `270,927,056` 尺寸双重校验（不符会提示，需 `--force`）；
* 每个站点 **expected-original-byte** 校验，不是原文就拒绝写；
* 代码洞必须**全零**（被别的探针占用会拒绝）；
* `--rollback` 用同一张表还原，**实测回滚后 sha256 = `5ac1cbe0…`，与原始文件逐字节相同**。

本轮实测的产物 sha256：

| 变体 | sha256 |
|---|---|
| A | `b25315100f8a13f10bf376f1f00101c482f7280bd836a5b76c2a668f0ea93600` |
| CE | `dabe3cba3f1c1fde3c04693133383c8c0b9600cc0de81ac0ea5cef504be1c3ba` |

> 这两条 sha256 是"对**原厂** libil2cpp.so 施加该变体"的确定性结果，可当第二个校验锚点。

---

## 8. 装机与验证（**本报告不执行，交给手机侧 agent**）

前提（已有结论，不要重验）：`libil2cpp.so` **无磁盘哈希钉死**，原位替换可用
（`report/01:128`、`ba-pitfalls:171`，E38/E63 两条独立证据）；`assets/__tpinfo.*` 5 个文件必须先删。

建议流程：
1. 备份 `/data/app/.../lib/arm64-v8a/libil2cpp.so`（先 `sha256sum` 存证）；
2. 用**流式**写回（`dd` / `cp` 到一个新 inode 再 `mv`），**绝不要 `cat >`**（`O_TRUNC` → 0 字节 → `dlopen` 自杀循环，见 `report/07`）；
3. `kill -9` + 手动点图标冷启（不要连续 monkey）；
4. 判据（一次只认一个变量）：
   * 是否还发 `POST /api/account/auth`（打 C 就不应该再发了）；
   * `logcat` 有无 `NullReferenceException` / `E/Unity`；
   * 画面是否出现**昵称弹窗 / 标题页消失 / loading**（这是"真的进了 OnLoginFinish"的第一信号）；
   * `conntrack` fresh sport 增量是否 > 1（进了 OnLoginFinish 之后客户端会去拉 RelayPackets 里的协议）。
5. 不行就按 §7 回滚，先恢复基线再谈下一轮。

若变体 C 出现 `NullReferenceException`：说明 `OnLoginFinish` 依赖 auth 之后的 DB 对象。
下一步按优先级：
* **C+**：把代码洞改成"先调 `HandleAccountAuthResponseMessage`（`0x08A83440`）再调 `OnLoginFinish`"，
  但前者的参数是 `AccountAuthResponseMessage*`，我们手上没有实例 → 需要另找入口（见 §9）。
* **B'**：改 `HandleAccountPassCheckResponseMessage`（`0x08A80394`，明文）为入口，
  让流程在 PassCheck 之后直接跳 `OnLoginFinish`（比 CheckYostar 更早、状态更少，通常更糟）。
* **放弃"跳结局"路线**，转去修"队列卡住"的真因（见 §9）。

---

## 9. 现在能立刻推进的两件事（下一轮，成本都很低）

1. **把 `LoginTask`/`NetworkService` 的整条调用链 dump 出来**（现在有地址表，全部可做）：
   在明文页里做 `bl` 目标统计已经跑通（§5 的表就是这么来的）。可以直接回答
   "`HandleAccountAuthResponseMessage` 到底被谁调"、"`WaitForRequest` 的 MoveNext 在哪 `yield`"。
   其中 `<WaitForRequest>d__59.MoveNext` 的地址也在 `ba_ptrs.bin` 里，**本轮没查它的明文状态**，
   下轮第一步就该查（若它在明文页，"修等待"这条路重新打开）。
2. **`OnLoginFinish` 到底需要什么状态**——它本体在加密页，静态看不到。
   但可以做"**参数级旁证**"：紧邻它的几个编译器生成子函数在明文页，例如
   `<>c__DisplayClass52_0.<OnLoginFinish>g__CompletePatch|4` @`0x08A88964`（mdef 20373），
   其体内 `bl 0x08A84AD0`（`CheckBeforehandGachaProceeding`）等调用都可读，
   能反推它依赖哪些全局对象。这比继续猜便宜得多。

---

## 10. 诚实标注（置信度 / 未证 / 风险）

| 结论 | 置信度 | 依据 |
|---|---|---|
| 任务里给的 `0x13xxxx` 是 metadata 字符串偏移，不是代码地址 | **确证** | 字节级（`Finished` 9 字节 → `Failed` 恰好相邻） |
| metadata 可完整解析（L1=头部 0x66666666，L2=每 64KB 的 [0x1000,0x5000) XOR 0x66） | **确证** | 30 段首尾相接 + 三张表 count 精确相等 |
| `methodPointers[mdef]` 索引关系成立 | **确证（强）** | count=154173 与 image 区间精确相等 + 90% 单调 + 全部落在代码段 |
| `loginState` 在 `this+0x10`、`Finished==2` | **确证** | 两处 `cmp` 反汇编 |
| `LoginState` 有 4 个成员 | **确证** | 字段表 `Ready/Progress/Finished/Failed` |
| `OnLoginFinish` 唯一调用点 `0x08A8938C` | **确证** | 全量 67.7M 字 `bl` 扫描 |
| `OnLoginFinish` 在 ACE 加密页、不能离线原地改 | **确证** | 页内 0 条 `ret`、字首字节分布 85%→36% |
| `AccountAuthStart` 是 auth **之后**的入口（而非 auth 之前） | **中高（推断）** | 它调 `ShowNicknamePopup` + `StartRequestRelayPackets`；且全库 0 个直接调用点 |
| 变体 C 会被执行到 | **高** | `RequestAccountAuth` 有 2 个直接调用点，且客户端确实发了 `Account_Auth` |
| 变体 C 能让客户端进大厅 | **中（~50%，未验证）** | 结构上成立；未知 `OnLoginFinish` 对 auth 后状态的依赖 |
| 变体 E 安全 | **高** | 同签名 `(this)→void` 的等价替换 |
| 变体 E 有功效 | **低** | 只有走到失败出口才触发 |
| `WaitForRequest` 是卡点 | **已被削弱** | report/48 的 `IsFinished` 归属错了（属于 `SessionStateChangedMessage`）；且两个候选都在加密页 |
| 本补丁不触发 ACE / 不违反改包边界 | **高（沿用既有结论）** | `report/01:128`、`ba-pitfalls:171`（libil2cpp 无 hash pin）+ 本轮只动明文页与全零填充 |

---

## 附录 A · 本轮新增脚本与产物

| 文件 | 作用 |
|---|---|
| `report\_tmp\patch\md_law.py` | 证明 metadata 的 L2 周期律（按 `off mod 0x10000` 统计 0x66 密度） |
| `report\_tmp\patch\md_parse.py` | 去混淆 + 解析头部，验证 30 段首尾相接与表尺寸 |
| `report\_tmp\patch\md_m2.py` | 方法表字段语义（`parameterStart`=0x08000000|row、token、flags/slot/pc 打包） |
| `report\_tmp\patch\md_lookup.py` | 按类型名查成员/字段/方法索引 |
| `report\_tmp\patch\build_ptrs.py` → `ba_ptrs.bin` | **154,173 条 mdef→代码地址** 全量表 |
| `report\_tmp\patch\build_codemap.py` → `codepage_bits.bin` | 39,177 页的"明文/加密"位图 |
| `report\_tmp\patch\tool.py` | 通用工具：`type <名字>` / `mdef <号>` / `va <地址>` 反汇编，自动标 `plaintext` |
| `report\_tmp\patch\md_deob.bin` | 去混淆后的 metadata（38 MB，可直接二次分析） |
| `work\ba\bapatch\patch_login_bypass.py` | **补丁脚本（交付物）** |

## 附录 B · 与本项目既有结论的冲突修正

| 旧结论（出处） | 本轮修正 |
|---|---|
| metadata 表头混淆、`methodPointer` 不可得（`report/24:245`、`report/47:189`、`report/48:52`） | **错**。头部只是 XOR 0x66666666；另有文件级 16KB/64KB 周期 XOR。表完全可解析 |
| `LoginState` 只有 `Finished`/`Failed`（`report/48:28`） | **错**。4 个成员，Finished=2 |
| `HttpGameSession.IsFinished`（`report/48:20`、任务书） | **归属错**。`get_IsFinished` 属于 `SessionStateChangedMessage`（mdef 65973） |
| `WaitForRequest` 是卡点（`report/48` 主假设） | **降级**：两个候选（`0x06E13594`/`0x06E131A8`）都在 ACE 加密页，静态不可改；且"等 IsFinished"的归属已错 |
| 目标落在加密块时改 `MethodInfo::methodPointer`（`report/17:503`） | **只对间接调用成立**。直接调用是 `bl 绝对地址`，改指针无效 |
| 改 libil2cpp 只能碰明文页（`report/17:484`） | **仍成立**，本轮量化：34.2% 页加密，登录簇的加密块是 `[0x08A83000,0x08A87000)` |
