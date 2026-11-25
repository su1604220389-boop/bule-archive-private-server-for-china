# 91 — `libil2cpp_hook` 写权限 bug 修复（v2）

- 日期：2026-11-14
- 输入基线：`work\ba\bapatch\libil2cpp.bin`，270,927,056 B，sha256 `5AC1CBE0FB8F730FFD22B93624A70AE9C90B0A1F3F3FBEB18C5D6AF3C73882C3`
- 修复对象：`work\ba\runtimehook\libil2cpp_hook.bin`（v1），sha256 `11CEFD6D5B89536AD588AF581C7D19B85E03212A3F01319DE4ED872745147B6F`
- 新成品：`work\ba\runtimehook\libil2cpp_hook_v2.bin`，270,927,056 B，sha256 `AA833EAA44666C7AAF441D8E7261DE12DCC03C9462E03058C3051635FD604A4F`
- 约束：全程本地只读/写产物；未连接手机、未连接服务器、未改动 `libtprt.so`。

---

## §0 一句话结论

**v1 并不是“没给洞页 mprotect”**——v1 的 `cave_main` 第一件事就是 `mprotect(洞页, RWX)`，而且一手日志证明它成功过；崩的原因是**洞页在 DT_INIT 之后又被别的代码改回了 RX**，而触发器的快速路径仍然直接写洞页上的 `g_tick`。

v2 的修法不是再 mprotect 一次，而是**把可写状态整体迁出洞页**：

- 匿名 `mmap` 一页 RW（无 X），所有持久状态（`skip/tick/orig/argc/base/fd/t0/…`）放里面；
- 洞页 `.data` 只留一个 8 字节指针 `g_state`，在 DT_INIT 的 mprotect 窗口里写一次；
- 发布后立即把洞页改回 RX；此后洞页对我们是纯只读；
- 触发器快速路径先读 `g_state`：为 0 就只回放，**零写入**；非 0 时 `tick++` 写匿名页，不写洞页。

---

## §1 崩溃根因（地址复算 + 一手证据链）

### 1.1 tombstone 的三条线

```
F/libc: Fatal signal 11 (SIGSEGV), code 2 (SEGV_ACCERR), fault addr 0x72cdd3cf08 (write)
  esr: 0x9200004f (Data Abort Exception 0x24)
  #00 pc 0x0f2c243c  libil2cpp.so
```

- `esr = 0x9200004F`
  - EC = `0x24`：Data Abort from lower EL
  - DFSC = `0x0F`：Permission fault, level 3
  - WnR = 1：write
  - ⇒ **写权限错**，不是野指针、不是未映射。
- `#00 pc = 0x0F2C243C`：这是 libil2cpp 的**文件内偏移/链接 VA**，运行时地址 = base + 0x0F2C243C。
- `fault addr = 0x72CDD3CF08`。

### 1.2 用 probe.log 复算

v1 的 `probe.log`（142 B，正好两行 71 B）：

```
B0 00000072bea7a000 000000000000007c 000000000f2c2410 00000072cdd3c000
C0 000000063c3b50 000000063c2ea8 0000000010496434 0000000000000000
```

`B0` 的四个字段（v1 `logic.c` 的 `log4('B', 0, base, fd, CAVE_VA, page)`）：

| 字段 | 值 | 含义 |
|---|---|---|
| 1 | `0x72BEA7A000` | libil2cpp 运行时 base |
| 2 | `0x7C` | 日志 fd |
| 3 | `0x0F2C2410` | 洞的链接 VA |
| 4 | `0x72CDD3C000` | 洞所在 4KB 页的运行时地址 |

复算：

```
cave_runtime = base + CAVE_VA
             = 0x72BEA7A000 + 0x0F2C2410
             = 0x72CDD3C410

page         = align_down(cave_runtime, 0x1000)
             = 0x72CDD3C000          ← 与 B0 第 4 字段一致

cave_off_in_page = 0x0F2C2410 - 0x0F2C2000 = 0x410

fault_addr   = 0x72CDD3CF08
             = page + 0xF08
             = cave_runtime + (0xF08 - 0x410)
             = cave_runtime + 0xAF8
             = base + 0x0F2C2F08
```

而 v1 的符号表（`_v1_src/hook.elf`）：

```
0f2c2f08 4 t g_tick
0f2c2f1c 4 t g_skip
0f2c2f58 16 t g_argc
0f2c2f68 32 t g_orig
```

⇒ **fault addr 正好是 v1 的 `g_tick`**：

```
g_tick_VA       = 0x0F2C2F08
g_tick_cave_off = 0x0F2C2F08 - 0x0F2C2410 = 0xAF8
g_tick_page_off = 0x0F2C2F08 - 0x0F2C2000 = 0xF08
```

### 1.3 精确到指令

v1 `hook.S` 的触发器快速路径（`_v1_src/hook.S:62-69`）：

```asm
trig_entry:
    adrp    x16, g_skip
    ldr     w16, [x16, :lo12:g_skip]
    cbnz    w16, .Ltrig_replay
    adrp    x16, g_tick
    ldr     w17, [x16, :lo12:g_tick]
    add     w17, w17, #1
    str     w17, [x16, :lo12:g_tick]   ← 崩溃指令
```

v1 成品的反汇编（`_v1_cave.dis`，洞内偏移 0x14 起）：

```asm
f2c2424  adrp x16, 0xf2c2000
f2c2428  ldr  w16, [x16, #0xf1c]      ; g_skip
f2c242c  cbnz w16, 0xf2c2494
f2c2430  adrp x16, 0xf2c2000
f2c2434  ldr  w17, [x16, #0xf08]      ; g_tick
f2c2438  add  w17, w17, #1
f2c243c  str  w17, [x16, #0xf08]      ; ← tombstone 的 pc
f2c2440  tst  w17, #0xff
f2c2444  b.ne 0xf2c2494
```

- `pc = 0x0F2C243C` = 洞首 `0x0F2C2410` + **0x2C**。
- 存的目标 = `x16 + 0xF08`，`x16 = 0xF2C2000`（运行时 = base + 0xF2C2000）。
- 目标 = `base + 0xF2C2F08` = **g_tick** = 洞内 **0xAF8**。
- tombstone 的 fault addr / pc / esr 与这条 `str` **逐项对齐**。

### 1.4 关键反证：mprotect 其实成功过

这是本次修复最重要的判断，也是为什么不能按“方案 A 字面”再补一次 mprotect。

v1 的 `cave_main` 反汇编（`_v1_cave.dis`）：

```asm
f2c297c  sub  sp, sp, #0x30
f2c2984  adr  x10, 0xf2c297c        ; &cave_main
f2c2994  and  x0, x10, #~0xfff      ; 洞页
f2c2998  mov  w8, #0xe2             ; 226 = mprotect
f2c299c  mov  w1, #0x1000           ; 4096
f2c29a0  mov  w2, #0x7              ; RWX
f2c29a4  svc  #0
f2c29a8  ...
f2c29b4  tbnz x0, #0x3f, 0xf2c2a04  ; rc < 0 → 失败分支
...
(f2c2a3c  log4f 'B')
f2c2a8c  str  wzr, [x8, #0xf1c]     ; g_skip = 0（武装触发器）
```

B0 这一行只在 **`mprotect` 返回 >= 0 的成功分支**里写；而且 B0 之前还写了 `g.base/g.fd/g.t0`、B0 之后又写了 `g_skip=0`，这些都在洞页上。日志里 B0/C0 都在，说明：

1. `mprotect(洞页, RWX)` **确实返回了 0**；
2. 洞页在 DT_INIT 期间**确实可写**；
3. 崩溃发生在这之后，说明洞页在某个时刻**又被改回了 RX**。

**同一个 base 证明是同一次进程**：`B0` 第 1 字段 `0x72BEA7A000` 与 tombstone 的 base 完全相同；ASLR 下两次独立启动几乎不可能给出同一个 libil2cpp base。因此 B0/C0 与 tombstone 是同一次运行，不能解释成“上次成功、这次失败”。

**为什么之后会变成 RX（推断，非一手证明）**：

- 解析 `libil2cpp.so` 的 dynsym：它**没有导入 `mprotect`**（只有 `mmap` / `pthread_create` / `dlopen`）。所以把洞页改回 RX 的**不是 libil2cpp 自己的导入**。
- `libunity.so` 和 `libtprt.so` 的 dynsym **都导入了 `mprotect`**；`libtprt.so` 是 ACE 的保护库，嫌疑最大。
- 原厂 `DT_INIT`（`0x10496434`）本身是标准构造器链（`__libc_init` 风格），没有直接 `mprotect`；但它会调用 ACE/Unity 的静态构造器，构造器完全可能对 `.text` 段做一次“收尾段保护”。
- 时间上也吻合：B0/C0 在尾调原厂 DT_INIT **之前**写出；崩溃发生在引擎起来后 `UnityPlayer K0.handleMessage` 的第一次触发器调用。中间正好隔着 DT_INIT 的构造器和 il2cpp 初始化。

> 结论：**v1 的 mprotect 是“一次性的、会被后续代码覆盖的”**。在 cave 开头再 mprotect 一次，等于重复 v1 已经做过的事；下一次被改回 RX 后，触发器仍然会崩。

### 1.5 为什么 v1 的日志停在 B0/C0

- 142 B = 两条 71 B 的行，只有 B0/C0；
- 没有 `S`（开始扫描）、没有 `R`（扫描结束）、没有 `A/Y/Z`（detour 命中）；
- 触发器快速路径在 `tick++` 就崩了，**根本没进慢路径**，所以 `cave_on_trigger` 一行都没跑。

这与“页在 DT_INIT 后被改回 RX、第一次触发器写 `g_tick` 就 SEGV_ACCERR”完全一致。

---

## §2 找到的具体写操作

### 2.1 v1 所有落在洞页上的可写状态

v1 的 `logic.c`（`_v1_src/logic.c:61-64,119`）把状态放在洞页的 `.data` 里：

```c
u32 g_skip = 1;                 // 0x0F2C2F1C
u32 g_tick = 1;                 // 0x0F2C2F08
u64 g_orig[4] = {1,1,1,1};      // 0x0F2C2F68
static u32 g_argc[4] = {0};     // 0x0F2C2F58
static struct st g = {...};     // 编译器把字段拆在 0x0F2C2F10..0x0F2C2F50
```

从 v1 成品的 `str/stp` 归纳（只列非栈目标）：

| 写者 | 指令/字段 | 目标 VA | 洞内偏移 | 页内偏移 | 触发时机 |
|---|---|---|---|---|---|
| `trig_entry` 快速路径 | `str w17,[x16,#0xf08]`（`g_tick++`） | `0x0F2C2F08` | `0xAF8` | `0xF08` | **每次触发器调用**（崩溃点） |
| `trig_entry` 快速路径 | 读 `g_skip`（不写） | `0x0F2C2F1C` | `0xB0C` | `0xF1C` | 每次 |
| `cave_main` | `g_skip=0` | `0x0F2C2F1C` | `0xB0C` | `0xF1C` | DT_INIT |
| `cave_main` | `g.base/g.fd/g.t0/...` | `0x0F2C2F10..0x0F2C2F50` | `0xB00..0xB40` | `0xF10..0xF50` | DT_INIT |
| `install` | `g_orig[t]=orig` | `0x0F2C2F68` 起 | `0xB58` 起 | `0xF58` 起 | 扫描命中 |
| `install` | `g_argc[t]=n` | `0x0F2C2F58` 起 | `0xB48` 起 | `0xF48` 起 | 扫描命中 |
| `cave_on_trigger` | `g.done/g.skip/g.attempts/g.in` | `0x0F2C2F10..0x0F2C2F50` | `0xB00..0xB40` | `0xF10..0xF50` | 慢路径 |
| `on_class`/`scan` | `g.nclass/g.nmeth/g.found` | `0x0F2C2F38..0x0F2C2F54` | `0xB28..0xB44` | `0xF28..0xF44` | 扫描 |

**崩溃的是第一行**：`g_tick++`。它之所以最先崩，是因为它是**快速路径上唯一的洞页写**，每次触发器调用都会执行；其他洞页写只在 DT_INIT/扫描期发生，而进程在第一次触发器调用就已经崩了。

### 2.2 源码行

- v1 `cave/hook.S`（备份 `_v1_src/hook.S`）第 62–69 行：

```asm
trig_entry:
    adrp    x16, g_skip
    ldr     w16, [x16, :lo12:g_skip]
    cbnz    w16, .Ltrig_replay
    adrp    x16, g_tick
    ldr     w17, [x16, :lo12:g_tick]
    add     w17, w17, #1
    str     w17, [x16, :lo12:g_tick]
```

- v1 `cave/logic.c` 第 62 行：`u32 g_tick = 1;`

### 2.3 目标地址计算（与 tombstone 对照）

```
x16        = base + 0x0F2C2000        (adrp 页基址)
target     = x16 + 0xF08
           = base + 0x0F2C2F08
           = 0x72BEA7A000 + 0x0F2C2F08
           = 0x72CDD3CF08              ← fault addr 完全一致
pc         = base + 0x0F2C243C
           = 0x72CDD3C43C              ← 同页，页内 0x43C
cave_off   = 0x0F2C2F08 - 0x0F2C2410 = 0xAF8
page_off   = 0x0F2C2F08 - 0x0F2C2000 = 0xF08
```

**没有“未找到”的情况**：写操作、源码、反汇编、目标地址、fault addr 五者对上了。

---

## §3 采用的修法：B+（状态迁出洞页），以及为什么不选 A/C

### 3.1 方案 A 的现状：v1 已经做了

方案 A 说“在洞的最开头加一次 mprotect”。v1 的 `cave_main` 第一条实用指令就是：

```asm
f2c2994 and  x0, x10, #~0xfff
f2c2998 mov  w8, #226
f2c299c mov  w1, #4096
f2c29a0 mov  w2, #7
f2c29a4 svc  #0
f2c29b4 tbnz x0, #0x3f, ...fail
```

而且 B0 证明它返回 0、洞页当时可写。**所以按 A 字面再加一次，不会阻止后面的 RX 回写；下一轮仍会在同一条 `str` 上崩。**

如果采用“每次写之前都 mprotect”的变体：

- 触发器快速路径每次调用都要一次 `mprotect` syscall（触发器是 BL 直方图第一名、413,726 个调用点），开销不可接受；
- 即使只在慢路径 mprotect，扫描期间 ACE 仍可能在另一个线程把页改回 RX，存在竞态。

所以 A 不足以作为最终修法。

### 3.2 B+ 的设计（本版采用）

**核心：洞页在发布后不再承担任何可写状态。**

1. `cave_main` 仍然先 `mprotect(洞页, RWX)`——但只为了写一个 8 字节指针 `g_state`。
2. 用 raw `mmap(0, 4096, PROT_READ|PROT_WRITE, MAP_PRIVATE|MAP_ANONYMOUS, -1, 0)` 拿一页匿名 RW（**无 X**）。
3. 把 v1 的 `struct st` 整体搬进这页；`g_skip/g_tick/g_orig/g_argc` 变成该页的字段。
4. 初始化完成后 `dmb ish; g_state = 状态页`；再写 B0/C0；最后 `mprotect(洞页, RX)`。
5. 触发器快速路径：
   - `x16 = g_state`；`cbz` → 只回放（**零写入**）；
   - 否则 `skip = [x16+0x3C]`，非 0 → 只回放；
   - `tick = [x16+0x40]++`，写的是**匿名 RW 页**，不是洞页；
   - 1/256 次进慢路径。
6. 扫描期的临时状态仍然通过 `il2cpp_class_for_each` 的第二个参数（`userData`）传给回调——这是 v1 已经用过、成功的手法，保留。
7. 失败安全：
   - `mprotect` 失败 → `g_state` 保持 0，触发器永远只回放；
   - `mmap` 失败 → 同样不发布；
   - 日志里分别有 M1/M2 记录，游戏不会因为我们的代码崩。

**状态页布局**（`logic.c` 与 `hook.S` 共享，编译器 `_Static_assert` 兜底）：

```c
struct st {
    u64 orig[4];      // 0x00  asm 直接索引：ldr x16,[x16,x19,lsl#3]
    u64 base;         // 0x20
    u64 t0;           // 0x28
    u64 page;         // 0x30  （诊断保留，未使用）
    i32 fd;           // 0x38
    u32 skip;         // 0x3C  asm ST_SKIP = 60
    u32 tick;         // 0x40  asm ST_TICK = 64
    u32 attempts;     // 0x44
    u32 done;         // 0x48
    u32 nclass;       // 0x4C
    u32 nmeth;        // 0x50
    u32 found;        // 0x54
    u32 in;           // 0x58
    u32 argc[4];      // 0x5C
};                    // sizeof = 112
```

`logic.c` 里的断言：

```c
_Static_assert(sizeof(struct st) == 112, "state size changed");
_Static_assert(__builtin_offsetof(struct st, orig) == 0x00, "ST_ORIG != 0");
_Static_assert(__builtin_offsetof(struct st, skip) == 0x3C, "ST_SKIP != 60");
_Static_assert(__builtin_offsetof(struct st, tick) == 0x40, "ST_TICK != 64");
```

### 3.3 为什么不是“纯栈”

`skip/tick/orig/argc/base/fd/t0` 必须跨 413,726 个调用点、跨线程长期存在；`orig[4]` 还要被任意线程的 detour 读到。栈活不过一次调用，不能放这些。

扫描期的临时状态（`nclass/nmeth/found/argc`）确实可以放栈上，而且 v1/v2 都已经通过 `for_each` 的 `userData` 传了；但**持久状态**必须有一个进程内稳定的可写页。匿名 `mmap` 页是最干净的选择：

- 不属于任何 `.so`，不会被 ELF 段保护 / RELRO 波及；
- 权限是 `rw-`，不是 `rwx`，不会触发 W^X / execmem；
- 地址由内核分配，和 libil2cpp 的映射完全解耦。

### 3.4 洞页大小 / 是否跨页

- 洞首 `0x0F2C2410`，页内偏移 `0x410`；
- v2 blob `0xB90` = 2960 B；
- 结束 = `0x410 + 0xB90 = 0xFA0 < 0x1000`；
- **正好不跨页**，容量 3056 B，余量 96 B。

### 3.5 顺手修掉的 4 个问题（前两个会在下一阶段变成新崩溃）

这些不是本次 tombstone 的直接原因，但都在 v1 里真实存在；v2 一并处理，避免下一阶段换一个地方崩。

#### (a) `PROT_RW = 6` 是错的

v1 `logic.c`：

```c
#define PROT_RWX 7
#define PROT_RW  6      // ← 6 = PROT_WRITE|PROT_EXEC，不是 READ|WRITE
#define PROT_RX  5
```

`PROT_READ=1, PROT_WRITE=2, PROT_EXEC=4`。`6` 是 **W|X**，没有 R。

v1 `install()` 在写完 `MethodInfo.methodPointer` 后 `sys_mprotect(page, 0x1000, PROT_RW)`，把 MethodInfo 页改成 **W|X（不可读）**；紧接着的 `Q0` 日志要读 `*(u64*)(mi+0/8/16)`，`param_count` 也可能读 MethodInfo —— **读就会 SIGSEGV**。即使 `g_tick` 修好，v1 走到 install 也会在这里崩。

v2 改成：

```c
#define PROT_READ  1
#define PROT_WRITE 2
#define PROT_EXEC  4
#define PROT_RW   (PROT_READ | PROT_WRITE)   // 3
#define PROT_RX   (PROT_READ | PROT_EXEC)    // 5
#define PROT_RWX  (PROT_READ | PROT_WRITE | PROT_EXEC) // 7
```

#### (b) MethodInfo 是数据，不需要 RWX

v1 `install()` 用 `mprotect(page, RWX)` 改 MethodInfo 页。MethodInfo 槽是**数据**，只需要写权限；加 X 既多一个 W^X 特征，也可能被 SELinux 的 `execmod/execmem` 拒绝。v2 改成 `mprotect(page, RW)`（3），失败时打 `!` 并跳过，不写槽。

#### (c) `.got` 在洞外；v2 用 hidden 彻底消掉

v1 的 `extern void hit0_entry(void); ...` 没有 `hidden`，链接器生成了一个 `.got`：

```
v1 hook.elf .got @ 0xf2c2f88:
  00252c0f 00000000  08252c0f 00000000
  10252c0f 00000000  18252c0f 00000000
```

但要注意：**反汇编显示 v1 的 `&hitN_entry` 已经被链接器松弛成 `adr` 直接取址**，`.got` 是未被引用的死段：

```asm
f2c2cd0  adr x8, 0xf2c2510      ; hit2_entry
f2c2cdc  adr x8, 0xf2c2500      ; hit0_entry
f2c2ce8  adr x8, 0xf2c2518      ; hit3_entry
f2c2cec  stur x8, [x10, #-8]    ; 写 MethodInfo 槽
```

所以 v1 **不会**因为 GOT 读到 0 而崩；但这个 `.got` 落在 `0xF2C2F88`——正好是 v1 `.cave` 的终点之外、洞页之内。它不会被 `build.py` 拷进成品（成品那里是 0），属于“洞外还有一段链接器数据”的隐患。v2 给 4 个 extern 加了 `__attribute__((visibility("hidden")))`，最终 `hook.elf` 里**没有 `.got` 段**，代码全部自包含在 `.cave` 内。

#### (d) x18 是 Android/AArch64 的 platform register

v2 初版快速路径曾用 `x18` 存 `tick`；`x18` 在 Android 上是 shadow call stack pointer / platform register，ABI 规定不能当通用暂存。已改回 `x17`（`ldr w17,[x16,#ST_TICK]`），并在 `hook.S` 注释里写明。静态反汇编里除 `#0x18` 立即数外，**没有任何 x18 寄存器引用**。

---

## §4 重建与自检结果

### 4.1 构建命令与结果

```bash
python work/ba/runtimehook/build.py
```

构建器会：

1. 校验输入 sha256 == `5AC1CBE0…`（原厂）；
2. 校验 RX 段 `p_filesz` 终点 == `0x0F2C2410`；
3. 校验 `DT_INIT == 0x10496434`；
4. WSL clang/ld.lld 编译 `cave/hook.S + cave/logic.c`，链接到 `0x0F2C2410`；
5. 校验零重定位、零未定义符号、blob ≤ 3056；
6. 写洞、DT_INIT、触发器 16 字节；
7. 全文件 diff，任何计划外改动直接退出；
8. 输出 sha256 和大小。

本次输出：

```
BLOD_SIZE=2960
blob 大小 = 2960 B（容量 3056 B，余量 96 B）
✔ 零重定位、零未定义符号
改动了 2624 字节，全部落在计划内（计划外 0 处）
大小   : 270927056 B (期望 270927056)
sha256 : AA833EAA44666C7AAF441D8E7261DE12DCC03C9462E03058C3051635FD604A4F
```

### 4.2 全文件 diff 表

```text
文件偏移      长度   原始                    新                      说明
0xf2c2410    2960   0000000000000000…       1f2003d5e0ffff10…       代码洞
0xfa2fc50    8      3464491000000000        10242c0f00000000        DT_INIT → 0xf2c2410
0x63c77fc    16     f37bbfa9f30300aa…       d07704f010921091…       触发器 16B 跳板
```

- **计划外改动 0 处**。
- 为什么“改动了 2624 B”小于“洞 2960 B”：原厂洞页尾部大量字节是 0/填充，新 blob 里也有大量相同的 0/NOP；只有真正变化的 2624 B 计数。所有变化都在 3 个计划区间内。

v1 → v2 的 diff（`tools/verify_v2.py`）：

```text
0x0f2c2418 .. 0x0f2c24c0   136 B   洞内
0x0f2c24e8 .. 0x0f2c2f97  2515 B   洞内
合计 2651 B，全部在洞内
```

也就是说：**v1 与 v2 的差异只在洞内**，DT_INIT 和触发器跳板的字节两版相同（都指向同一个洞首/`trig_entry`）。

### 4.3 mprotect / mmap / M1 机器码

v2 `cave_main`（`0xF2C2978`）的实际反汇编：

```asm
f2c2984  adr  x23, cave_main          ; 洞页来源
f2c2998  bl   0xf2c2ef8               ; OUTLINED_FUNCTION_2: mov w8,#226; mov w1,#0x1000; ret
f2c29a0  mov  x19, x0                 ; base
f2c29a4  and  x0, x23, #~0xfff         ; x0 = 洞页基址（页对齐）
f2c29a8  mov  w2, #7                  ; PROT_READ|PROT_WRITE|PROT_EXEC
f2c29ac  svc  #0                      ; mprotect(page, 4096, 7)
f2c29b0  mov  x21, x0                 ; rc
...
f2c29f4  bl   log4f                   ; M1 <rc> <page> 0 0
```

> 说明：clang 为了省字节，把 `x8=226 / x1=0x1000` 抽成了 `OUTLINED_FUNCTION_2`（3 条指令的 helper，`ret` 返回），所以不是一条连续的 5 指令序列；语义上调用点仍是 **`x0=page, x1=4096, x2=7, x8=226, svc #0`**。helper 在 `0xF2C2EF8`：

```asm
f2c2ef8  mov w8, #0xe2     ; 226
f2c2efc  mov w1, #0x1000   ; 4096
f2c2f00  ret
```

M1 的参数（`0xF2C29D0` 起）：

```asm
f2c29d0  and  x4, x23, #~0xfff   ; page
f2c29d4  mov  w1, #0x4d          ; 'M'
f2c29d8  mov  w2, #1             ; idx 1
f2c29dc  mov  x3, x21            ; rc
f2c29e0  mov  x5, xzr
f2c29e4  mov  x6, xzr
f2c29f4  bl   log4f              ; x0 = fd
```

实际日志行格式（4 字段，后两个恒 0）：

```
M1 <mprotect返回值> <洞页地址> 0000000000000000 0000000000000000
M2 <mmap返回值/地址> 0000000000000000 0000000000000000 0000000000000000
```

> 为了把洞塞进 3056 B，v2 删掉了单独的 `log2f`（它要 148 B），M1/M2 复用 `log4f`，所以多两个 0 字段。判读只看前两个字段。

mmap：

```asm
f2c29fc  mov  x0, xzr
f2c2a00  mov  w8, #0xde     ; 222 = mmap
f2c2a04  mov  w1, #0x1000   ; 4096
f2c2a08  mov  w2, #3        ; PROT_READ|PROT_WRITE（不是 6！）
f2c2a0c  mov  w3, #0x22     ; MAP_PRIVATE|MAP_ANONYMOUS
f2c2a10  mov  x4, #-1
f2c2a14  mov  x5, xzr
f2c2a18  svc  #0
...
f2c2a3c  bl   log4f          ; M2
```

状态初始化 / 发布 / 恢复 RX：

```asm
f2c2a44  mov  x8, xzr
f2c2a48  mov  w9, #1
f2c2a4c  cmp  x8, #0x20
f2c2a50  b.eq 0xf2c2a60
f2c2a54  str  x9, [x21, x8]      ; orig[0..3] = 1
f2c2a58  add  x8, x8, #8
f2c2a5c  b    0xf2c2a4c
f2c2a64  str  x19, [x21, #0x20]  ; base
f2c2a6c  stp  w20, w9, [x21, #0x38] ; fd, skip=1
...
f2c2a94  dmb  ish
f2c2a98  str  x21, [x8, #0xf98]  ; g_state = 状态页  ← 洞页唯一写
...
f2c2b20  tbnz w20, #0x1f, ...    ; fd < 0 不武装
f2c2b24  str  wzr, [x21, #0x3c]  ; skip = 0，武装触发器
f2c2b28  and  x0, x23, #~0xfff
f2c2b2c  bl   0xf2c2ef8          ; x8=226, x1=0x1000
f2c2b30  mov  w2, #5             ; PROT_READ|PROT_EXEC
f2c2b34  svc  #0                 ; 洞页改回 RX
f2c2b38  add  x8, x19, x22       ; base + ORIG_DT_INIT
f2c2b3c  blr  x8                 ; 尾调原厂 DT_INIT
```

### 4.4 触发器快速路径（v2）

`0xF2C2424`（洞内偏移 0x14）：

```asm
f2c2424  adrp x16, 0xf2c2000
f2c2428  ldr  x16, [x16, #0xf98]   ; x16 = g_state
f2c242c  cbz  x16, 0xf2c2498       ; 未发布 → 只回放，零写入
f2c2430  ldr  w17, [x16, #0x3c]    ; skip
f2c2434  cbnz w17, 0xf2c2498       ; 已完成/未就绪 → 只回放
f2c2438  ldr  w17, [x16, #0x40]    ; tick
f2c243c  add  w17, w17, #1
f2c2440  str  w17, [x16, #0x40]    ; ← 写匿名 RW 页，不是洞页
f2c2444  tst  w17, #0xff
f2c2448  b.ne 0xf2c2498            ; 1/256 进慢路径
```

与 v1 的对照：

| | v1 | v2 |
|---|---|---|
| 状态指针 | 无 | `g_state`（洞页 `.data`，8 B） |
| `tick` 写目标 | `base + 0xF2C2F08`（洞页，`0xAF8`） | `[g_state + 0x40]`（匿名页） |
| 崩溃 pc | `0x0F2C243C`（`str`） | `0x0F2C2440` 的 `str` 目标是匿名页；`0x0F2C243C` 是 `add`，不会 fault |
| x18 | 未用 | 未用（用 x17） |

### 4.5 写指令静态审计

从 `_v2_cave_final.dis` 里逐条看所有 `str/stp/strb/strh`，按目标分类：

| 类别 | 代表指令 | 目标 | 是否安全 |
|---|---|---|---|
| 触发器快速路径 | `str w17,[x16,#0x40]`（`0xF2C2440`） | `g_state+0x40`，匿名 RW 页 | ✅ 不写洞页 |
| 触发器慢路径保存现场 | `stp x0,x1,[sp]` … `str x9,[sp,#0x58]` | 栈 | ✅ |
| `hit_common` 保存现场 | `stp x0,x1,[sp]` … `str x10,[sp,#0x60]` | 栈 | ✅ |
| `cave_main` 发布指针 | `str x21,[x8,#0xf98]`（`0xF2C2A98` / `0xF2C2AFC`） | 洞页 `g_state`（`0xF2C2F98`） | ✅ **在 mprotect RWX 窗口内，且是洞页唯一写** |
| `cave_main` 状态初始化 | `str x9,[x21,x8]`、`str x19,[x21,#0x20]`、`stp w20,w9,[x21,#0x38]`、`str x8,[x21,#0x28]`、`str w9,[x21,#0x48]`、`str wzr,[x21,#0x3c]` | 匿名状态页 | ✅ |
| `cave_on_trigger` | `str w8,[x19,#0x48/0x3c/0x58]`、`str w8,[x19,#0x44]` | 匿名状态页（x19=`g_state`） | ✅ |
| `on_class` | `str w8,[x1,#0x4c]`、`str w8,[x20,#0x50]`、`str x28,[x20,w26,uxtw#3]`、`str w8,[x20,#0x54]`、`str w8,[x24,#0x5c]` | 匿名状态页（x20/x1=`st`） | ✅ |
| `install` 改 MethodInfo | `stur x8,[x10,#-8]`（`0xF2C2D80`） | `MethodInfo` 数据页（RELRO） | ✅ 先 `mprotect(page, RW)`；失败走 `!` 分支不写 |
| 日志缓冲 | `strb w?,[x24,x8]`、`str w?,[x0,#0x68]`、`strb w?,[x11,x12]` | 栈上的 `struct lb` | ✅ |
| `flushf` 写 fd | `svc #0`（write） | 日志 fd | ✅ |

**结论：v2 洞页上只有 `g_state` 这一处 8 字节写（编译器在时钟成功/失败两条路径各生成一条 `str`，逻辑上是同一处），位于 mprotect 窗口内；除此之外没有任何 `str/stp` 以洞页为基址。** 这正是“洞页即使被 ACE 改回 RX 也不会再崩”的静态依据。

> 注：`MethodInfo` 槽的写在 `mprotect` 之后，但 `slot` 是数据页，不是洞页；失败时 `install` 直接 `return`，不会写。`m` 的 `!` 日志会记录 `rc/slot/mi`。

### 4.6 `.data` / `.bss` / `.got` / 段

`llvm-size -A cave/logic.o`：

```
.text                2404
.data                   8     ← 只有 g_state
.rodata.str1.1         72
.rodata                76
.comment               40
```

`llvm-readelf -S cave/hook.elf`：

```
[1] .cave  PROGBITS  0x0f2c2410  0x2410  size 0xb90
（没有 .got）
```

- `g_state`：`0x0F2C2F98`，size 8，初值 8 个 0；
- `.cave` 结束于 `0x0F2C2FA0`，页尾还剩 `0x60 = 96 B`；
- `g_state` 之后到页尾的 96 B 在成品里全 0；
- 没有 `.bss`（`-fno-zero-initialized-in-bss` 下零初始化也进 `.data`；这里只有 `g_state`）。

**“洞里的 `.data/.bss` 完全为空”没有做到 100%**：还剩 `g_state` 这 8 B。原因是运行期 mmap 的地址必须发布到某个可读位置；如果强行做到 0，只能用固定地址 mmap（可能和已有映射冲突）或借 libil2cpp 的 RW 段/`.bss`（会写别人的数据页）。8 B 的“只写一次、之后只读”的指针是这里最小的代价；它不在快速路径上，也没有运行期写入。

### 4.7 触发器跳板 / 回放槽复核

触发器 `0x63C77FC` 的 16 B：

```
d07704f0  adrp x16, page_delta +36603
10921091  add  x16, x16, #0x424
00021fd6  br   x16
1f2003d5  nop
```

解出目标 `0xF2C2424` = `trig_entry`；全程 PC 相对，基址无关。

回放槽 `0xF2C2498`（10 字）：

```
a9bf7bf3  stp x19,x30,[sp,#-16]!   ; 原函数第 1 条
aa0003f3  mov x19,x0               ; 第 2 条
58000090  ldr x16,#16              ; 越界 BL 跳板
d63f0200  blr x16
14000004  b +16
d503201f  nop
0640aa3c  .quad 0x640aa3c          ; 原 BL 目标
00000000
b940da60  ldr w0,[x19,#0xd8]       ; 第 4 条
1400000b  b replay_end
```

- 第 3 条原指令是 `BL 0x640AA3C`，超出 ±128MB，用 `ldr x16,#16; blr x16` 跳板；
- 字面量 `0x0640AA3C` 已由 build.py 复核；
- 回放后跳到 `replay_end`，再 `br` 回 `0x63C780C`（原函数 +16）。

### 4.8 静态自检的边界

- 以上全部是**本地静态**结论；没有上机，M1/M2 的真实返回值、状态页地址、触发器是否被调用，都要等下一轮日志。
- 唯一的一手运行证据是 v1 的 tombstone + probe.log；v2 没有运行证据。
- 状态页地址在编译期未知；静态只能确认“写的是 `[g_state+0x40]`”，不能确认 `g_state` 一定非 0。M2 会打印它。

---

## §5 上机步骤（给 Lead 转手机侧）+ 判读表

### 5.1 替换步骤（沿用 v1 的安装路径）

> 以下命令是给手机侧执行的；本代理未连接手机。`LIB_PATH` 用你们现有的 libil2cpp.so 路径（v1 能跑通的那条路径），`BACKUP` 放同目录或 `/data/local/tmp`。

1. **PC 侧校验**
   ```bash
   sha256sum libil2cpp_hook_v2.bin
   # 必须是 AA833EAA44666C7AAF441D8E7261DE12DCC03C9462E03058C3051635FD604A4F
   ```

2. **强制停止游戏**（覆盖正在映射的 .so 会 ETXTBSY）
   ```bash
   adb shell am force-stop com.RoamingStar.BlueArchive
   ```

3. **备份当前 libil2cpp.so**
   ```bash
   adb shell su -c "cp -a $LIB_PATH ${BACKUP:-/data/local/tmp}/libil2cpp.so.v1.bak"
   adb shell su -c "ls -lZ $LIB_PATH"
   ```
   记下原文件的 owner/mode/SELinux context。

4. **清空 probe.log**（v1 的 openat 是 `O_APPEND`，不清会混着旧行）
   ```bash
   adb shell su -c "rm -f /data/data/com.RoamingStar.BlueArchive/files/probe.log"
   ```

5. **原地覆盖**（用 `cat >` 覆盖 inode，保留 SELinux label/权限；不要用 `cp` 新建文件）
   ```bash
   adb push libil2cpp_hook_v2.bin /data/local/tmp/libil2cpp.so
   adb shell su -c "cat /data/local/tmp/libil2cpp.so > $LIB_PATH"
   adb shell su -c "chmod 644 $LIB_PATH"
   adb shell su -c "ls -lZ $LIB_PATH"     # 与第 3 步对比
   ```

6. **启动、等待、取日志**
   ```bash
   adb shell am start -n com.RoamingStar.BlueArchive/...   # 用你们的启动方式
   sleep 15
   adb shell su -c "cat /data/data/com.RoamingStar.BlueArchive/files/probe.log"
   ```

7. 如果 15 秒内没有 `S/R`，再等 10 秒取一次；触发器在每次托管方法进入时都会走，正常几秒内就会到 1/256 慢路径。

> 不要动 `libtprt.so`；不要把 v2 和 v1 混装；不要改 APK 签名。

### 5.2 判读表

先看日志的**最后一段**（清空后应该从 M1 开始；下面的地址是 v1 的示例，本轮实际地址以 M2/B0 为准）：

```
M1 <mprotect返回值> <洞页地址> 0000000000000000 0000000000000000
M2 <mmap返回值/地址> 0000000000000000 0000000000000000 0000000000000000
B0 <base> <fd> 000000000f2c2410 <洞页运行时地址>
C0 <for_each> <get_methods> <orig_init> 0000000000000000
```

| 日志/现象 | 含义 | 下一步 |
|---|---|---|
| 文件不存在 / 没有 M1 | 洞没执行：装错文件、DT_INIT 没改、或 log 目录不可写 | 校验 sha256；`ls -lZ $LIB_PATH`；确认 v2 的 `DT_INIT` 是 `0x0F2C2410` |
| 只有旧的 B0/C0，没有新 M1 | 日志没清 / 新进程没跑 | 清 log 后重启；看时间戳 |
| `M1 0000000000000000 00000072cdd3c000 …` | mprotect 成功，页地址正确 | 继续看 M2 |
| `M1 fffffffffffffff3 …`（-13 EACCES） | mprotect 被 ACE/SELinux 拒绝 | `g_state` 不会发布，触发器只回放，**游戏应仍能启动**；下一轮走静态补丁或换可写页 |
| `M1 ffffffffffffffea …`（-22 EINVAL） | 页地址/长度不合法（页大小/对齐） | 确认设备是 4KB 页；若是 16KB 页，洞布局/容量要重算 |
| `M1 0000000000000000 …` + `M2 fffffffffffffff4 …`（-12 ENOMEM） | mmap 失败 | `g_state` 不发布，游戏安全；检查进程 VA 限额/ACE 是否拦 mmap |
| `M1 0 …` + `M2 fffffffffffffff3 …` | mmap 被 EACCES | 同上；状态页拿不到，不武装 |
| `M1 0` + `M2 0000007f…` + `B0 …` | **状态页已发布、触发器已武装** | 等 8–10 秒看 `S/R` |
| 新崩溃 pc `0xF2C2A98` / `0xF2C2AFC`，fault = 洞页 + `0xF98` | 洞页在“发布 `g_state`”之前又被改回 RX（初始化窗口内） | 在 `g_state` 存储前再加一次 mprotect；或把发布改成固定地址页 |
| `B0` 后 20 秒没有 `S` | 触发器没被调用，或 `skip` 没武装 | 看 B0 的 base/fd/page；看 C0；下一轮查触发器入口是否被 ACE 覆盖 |
| 有 `S`/`R`，`R` 的命中位图 = 0 | 扫描跑了，但 4 个方法名没匹配到 | 不是崩溃；看 `R` 的类数/方法数；看 `Q0` |
| 出现 `P0` | `HandleAccountAuthResponseMessage` 已装 detour | 等 `A0` |
| 出现 `A0` / `Y0` / `Z0` | detour 真的被调用了；`Y0` 是字符串参数，`Z0` 是响应对象字段 | 这就是要的观测数据 |
| `!0 <rc> <slot> <mi> 0` | MethodInfo 页 mprotect 失败，detour 没装 | 游戏应不崩；下一轮查 RELRO/权限 |
| 新崩溃 pc 仍是 `0x0F2C243C`，fault 仍是 `page+0xF08` | **装的还是 v1**（v2 这个 pc 是 `add`，不会写 fault） | 校验 sha256 / 覆盖是否成功 |
| 新崩溃 pc `0x0F2C2440`，fault = `M2+0x40` | 状态页坏了（地址不对/被 unmap） | 看 M2 地址；下一轮把状态页换到固定可写页 |
| 新崩溃 pc 在 `0x0F2C2D80` 附近，fault = MethodInfo slot | MethodInfo 数据页写不进去（RELRO/被改回） | 走 §6.1 |
| 新崩溃在 `on_class`（`0x0F2C2B58..0x0F2C2E24`） | il2cpp API/ABI 或偏移不对 | 走 §6.3 |
| 启动即崩、连 M1 都没有 | DT_INIT 跳到了坏地址 / 洞没映射 | 回滚 v1/原厂；检查洞首 16 B 和 DT_INIT |

### 5.3 与 v1 判读表的差别

- v1 的 `B0` 没有 mprotect 返回值，只能靠“有没有 B0”间接判断；v2 新增 **M1** 直接给出 rc。
- v1 失败时写 `Z1 mprotect_fail`；v2 为了省 96 B 洞容量删掉了 Z1/Z2 横幅，**M1/M2 的负 errno 就是失败证据**。
- v1 的 `B0` 第 4 字段是洞页；v2 的 `B0` 第 4 字段仍是洞页，但 **M2 第 1 字段才是状态页**。不要把 M2 的地址当成洞页。

---

## §6 如果这次还崩，下一个怀疑点

按可能性排序：

### 6.1 `install()` 写 MethodInfo 数据页（下一个最可能）

- 位置：`cave/logic.c:246` 起，`*slot = &hitN_entry`；反汇编 `stur x8,[x10,#-8]` @ `0x0F2C2D80`。
- 这是 RELRO 数据页（`PT_GNU_RELRO [0xF2C4000, 0xFBB4000)`），v2 已经改成 `mprotect(page, RW)`（3），失败会打 `!` 并跳过。
- 如果仍崩：
  - 看 `!` 行：`rc` 是负几？`slot` 落在哪个页？
  - 读 `/proc/self/maps` 确认该页原始权限；如果 mprotect 返回 0 但写仍 SEGV，说明有人在 mprotect 之后又把页改回只读（ACE/Unity）。
  - 备选：`open("/proc/self/mem", O_RDWR)` + `pwrite` 写槽（绕 mprotect）；或写前再 mprotect 一次 + `dmb`；或改用 `il2cpp_class_get_method_from_name` 的 `methodPointer` 以外的手段（例如只观测不改）。
- 注意：v1 的 `PROT_RW=6`（W|X）已经在 v2 修成 3；如果看到 `Q0` 读 `mi` 崩，那是 v1 的旧问题，不是 v2。

### 6.2 回放序列 / 触发器页被 ACE 加密或覆盖

- 现象：`M1/M2/B0` 都正常，但第一次触发器调用后崩在 `0x640AA3C`、`0x63C780C` 或返回路径；或者 `S` 永远不出现。
- v1 从未走到回放（在 `g_tick` 就崩了），所以**回放序列没有运行证据**；它只是按文件字节重放。
- 已核对 `work/ba/bapatch/encrypted_pages.txt`：
  - 触发器本身 `0x63C77FC` **不在**加密页列表（0x63C4000-0x63C8000 未被标记）；
  - 但回放里 BL 的目标 `0x640AA3C` 落在 `0x640A000-0x640E000`（被标记为疑似 ACE 加密段）。
  - 这个 BL 是原函数自己的调用，游戏运行到触发器时 ACE 必须已经把该页解密；如果崩在 `0x640AA3C`，才说明该页没解密/被重新加密，而不是我们的回放序列写错。
- 备选：
  - 在慢路径里打印触发器运行期前 4 字（`0x63C77FC`），与回放序列比对；
  - 或换一个不在加密页的触发器（BL 直方图 rank 2/3）。
- 本次 tombstone 的 pc 已经在 `trig_entry` 里，说明触发器入口 stub 至少执行了；这降低了“入口被加密覆盖”的概率。

### 6.3 il2cpp API 偏移 / ABI

- 现象：`S` 出现，`R` 没出现，崩在 `on_class`（`0x0F2C2B58..0x0F2C2E24`）。
- 检查 `C0` 的三个常量：`for_each=0x63C3B50`、`get_methods=0x63C2EA8`、`orig_init=0x10496434`。
- `il2cpp_class_for_each` / `get_methods` 的签名：v1 假设 `void (*)(void* klass, void* userData)`、`void* (*)(void*, void**)`；如果这个包是 B 桩（4 字节 `B` 到真实函数），调用约定不变；如果是别的桩形态，需要重定位。
- 备选：先用 `il2cpp_class_get_method_from_name`（本包导出表里的偏移需要重新核实；v1 的 `OFF_METHOD_NAME = 0x63C37BC` 是 `method_get_name`，不是这个 API）只查目标类，减少枚举面；或把扫描的 `get_methods` 上限从 8192 降到 256 做二分。

### 6.4 `probe_str` 的野指针

- 现象：`A0` 已经打出，随后崩在 `cave_on_hit` / `probe_str`（`0x0F2C2890` 附近）。
- `probe_str` 先检查 `p` 的范围/对齐、`*(u64*)p` 落在 `[base, base+MOD_MAX)`，再读 `length`；但 `args[1]` 只有在 `argc>=1` 时才碰。
- 如果 `Q0` 的 `argc` 是 8（因为 `param_count` 返回异常），会误碰 `x1`；下一轮可以只对 `tag==0` 且 `argc==1` 才 probe `x1`，或把 `probe_str` 的 `length` 上限降到 256。

### 6.5 洞页被 unmap/remap（不是 mprotect）

- 现象：连 `g_state` 的读都崩，pc 在 `trig_entry` 的 `ldr x16,[x16,#0xf98]`（`0x0F2C2428`），fault 在洞页 `0xF98`。
- 这比“改回 RX”更狠；如果发生，说明有人重新映射了 RX 段。下一轮把 `g_state` 的发布改成“固定地址状态页”（`mmap(MAP_FIXED_NOREPLACE)`）或用 libil2cpp 的 RW 段空槽，避免从洞页读指针。
- 但本次一手证据是 `SEGV_ACCERR`（权限），不是 `SEGV_MAPERR`（未映射），所以这个概率低于 6.1/6.2。

### 6.6 状态页本身被 ACE 扫到

- 匿名 `rw-` 页不属于任何 .so，通常不会出现在段保护扫描里；但如果 ACE 枚举 `/proc/self/maps` 的匿名可写页并做完整性检查，可能起疑。
- 现象：M1/M2/B0 正常，过一段时间才崩，且 pc 不在我们的写指令上。
- 备选：把状态页改成“借 libil2cpp 的 `.bss` 空槽”（需要先确认空槽）或 `mmap` 后 `mprotect(PROT_READ)`、只在写时临时 RW（会增加 syscall）。

### 6.7 一句话排查顺序

1. 先看 **M1**：mprotect 成没成？
2. 再看 **M2**：状态页拿到没有？地址是不是 `0x7...` 的匿名页？
3. 再看 **B0/C0**：发布/武装有没有走到？
4. 再看 **S/R**：慢路径有没有跑？`R` 的类数/方法数对不对？
5. 最后看 **P/Q/A**：detour 装没装、命中参数是什么？
6. 如果新崩溃的 pc/fault 仍是 v1 的 `0x0F2C243C` / `page+0xF08`，**先怀疑文件没换成功**，不要怀疑修法。

---

## 附录 A 产物与证据

| 文件 | 说明 |
|---|---|
| `work\ba\runtimehook\libil2cpp_hook_v2.bin` | 新成品，270,927,056 B，sha256 `AA833EAA…604A4F` |
| `work\ba\runtimehook\libil2cpp_hook.bin` | v1，未改动，sha256 `11CEFD6D…147B6F` |
| `work\ba\runtimehook\cave\hook.S` | v2 汇编 |
| `work\ba\runtimehook\cave\logic.c` | v2 C |
| `work\ba\runtimehook\build.py` | 构建器（默认输出改为 `_v2.bin`；符号检查改为 `g_state`） |
| `work\ba\runtimehook\_v1_src\` | v1 的 `hook.S/logic.c/build.py/cave.ld/hook.bin/hook.elf` 备份 |
| `work\ba\runtimehook\tools\verify_v2.py` | 独立静态复核脚本 |
| `report\evidence\91\v2_cave_final.dis` | v2 成品洞区反汇编 |
| `report\evidence\91\v1_cave.dis` | v1 成品洞区反汇编（崩溃指令） |
| `report\evidence\91\verify_v2.txt` | 复核输出 |
| `report\evidence\91\build_v2.log` | 构建日志 |
| `report\evidence\91\v1_probe.log.txt` | 用户提供的一手 probe.log 转录 |

### 复现

```bash
cd work/ba/runtimehook
python build.py                     # 需要 WSL: clang / ld.lld / llvm-objcopy
python tools/verify_v2.py           # 只读复核
```

### 回滚

- 恢复 v1：`libil2cpp_hook.bin`（sha `11CEFD6D…`）。
- 恢复原厂：`work\ba\bapatch\libil2cpp.bin`（sha `5AC1CBE0…`）。
- 源码回滚：`_v1_src/` 覆盖回 `cave/` 即可重新构建 v1。
- 手机侧：把备份的 `libil2cpp.so.v1.bak` 用 `cat >` 覆盖回 `$LIB_PATH`，清 `probe.log`，重启。

---

## 附录 B 关键数字速查

```
v2 sha256        AA833EAA44666C7AAF441D8E7261DE12DCC03C9462E03058C3051635FD604A4F
v2 size          270,927,056
cave VA          0x0F2C2410
cave page        0x0F2C2000
cave off in page 0x410
cave blob        0xB90 = 2960 B
cave end         0x0F2C2FA0
page end         0x0F2C3000
margin           0x60 = 96 B
g_state          0x0F2C2F98 (cave off 0xB88, page off 0xF98), size 8
trig_entry       0x0F2C2424 (cave off 0x14)
cave_main        0x0F2C2978 (cave off 0x568)
replay_slot      0x0F2C2498 / replay_end 0x0F2C24E8
trigger stub     0x63C77FC -> 0x0F2C2424
DT_INIT value    0x0FA2FC50 -> 0x0F2C2410
v1 g_tick        0x0F2C2F08 (cave off 0xAF8, page off 0xF08)
v1 g_skip        0x0F2C2F1C
v1 g_argc        0x0F2C2F58
v1 g_orig        0x0F2C2F68
```

## 附录 C 未做到 / 未验证

- 没有上机，M1/M2 的真实值、状态页真实地址、触发器调用频率都未验证。
- 没有抓到“谁把洞页改回 RX”的运行期证据；只能从 dynsym/时序推断（`libunity`/`libtprt` 有 `mprotect`，`libil2cpp` 没有）。
- 没有尝试 16KB 页设备；本包 tombstone 的页地址是 4KB 对齐，按 4KB 页处理。
- 没有改 `libtprt.so`，没有碰签名/APK。
