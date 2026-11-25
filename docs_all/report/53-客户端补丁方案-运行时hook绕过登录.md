# 53 · 客户端补丁方案：运行时 hook 绕过登录判断

> 日期：2026-11-14
> 目标：`com.RoamingStar.BlueArchive` 3.0.2（versionCode 73）/ Unity 2021.3.56f2 + il2cpp / arm64-v8a
> 环境：KernelSU root，Android 17 / API 37，一加 PLR110
> 本轮**没有碰手机**（无 adb、无 ssh），全部是本地开发 + 脚本 + 手册。
> 结论等级：**[实测]** 本机跑出来的二进制/输出 / **[确证]** 有偏移或字节级证据 / **[推断]** 逻辑外推

---

## 0. 一页结论

### 0.1 先回答"为什么之前 Frida 失败"

`report\DEADENDS.md` 的 D-30~D-35 其实是 **两个互不相干的死因叠在一起**，
而历史记录把它们混成了"Frida 不行"这一条。分开看才解得开：

| # | 死因 | 影响谁 | 能不能解 |
|---|---|---|---|
| **A** | **ACE 的行为/结构检测**：`/proc/self/maps` 里的 agent 映射、线程名 `gum-js-loop`/`pool-frida`、端口 27042、`/proc/self/status` 的 `TracerPid != 0`。dex 里 `frida`/`27042`/`ptrace` **明文 0 命中** ⇒ 它不看字符串，看**结构** | **所有"从进程外注入"的载体**（frida-server、gadget 附加、ptrace 注入） | 部分可解：读取层伪造（§3.2）。但**根本上更好的是换一个不注入的载体** |
| **B** | **`libil2cpp.so` 的 2660 条 `.dynsym` 里，带名的 306 条全是"导入"，`il2cpp_*` 可 dlsym 的 = 0 个** | **所有"按名字拿 il2cpp API"的方案**：`frida-il2cpp-bridge`、AzusaBA 的 `xdl_sym`、`Module.getExportByName` | **已完全解决**：124 个 `il2cpp_*` 的模块内偏移已离线恢复，本报告给出的两个脚本都只用偏移、不用名字 |

历史记录里的三次失败分别死在哪：

| 记录 | 真实死因 | 说明 |
|---|---|---|
| D-30（frida-server / attach / spawn） | **A** | "团队确实 attach 成功过，但没有一份日志证明进程活过 30 秒" —— 这正是 A 的表现 |
| D-31（frida-il2cpp-bridge） | **B**（不是 ACE） | 它内部走 `Module.getExportByName("libil2cpp.so","il2cpp_*")`，导出名被抹了就必然抛 `Unable to find export` |
| D-32（搬 AzusaBA 的 `xdl_sym`） | **B**（不是 ACE） | `xdl_sym` 依赖 `.dynsym` 的 `st_name` 比字符串，全空 ⇒ 全 NULL ⇒ `okHooks = 0/26` |

> **这是本轮最重要的一条纠错**：D-31/D-32 当年被记成"Frida/注入不行"的证据，
> 实际上它们**根本没碰到 ACE**——它们在 ACE 动手之前就已经因为符号表而失败了。
> 反过来，`report\17` 已经证明了 B 可以解（124 个偏移），只是当时没有把它接到"绕过登录"这个目标上。

### 0.2 三个方案的可行性排序（按"能真的把登录推过去"排）

| 排序 | 方案 | 载体 | 存活率 | 装机成本 | 本报告给出的实现 |
|---|---|---|---|---|---|
| **1（推荐）** | **libil2cpp `DT_INIT` 代码洞** | 预置代码，**零注入** | **最高**（A 的四条检测全不成立） | 打包+重启，约 10 分钟 | `work\ba\runtimehook\cave\hook.c` + `mk_hook.py`，**已实测编译通过、blob 2128 B、改动面 2 处** |
| 2 | **KernelSU 模块** | bind-mount 上一项产物 | 同 1 | 同上（模块化、可一键回滚） | `work\ba\runtimehook\kernelsu_module\` 全套 |
| 3 | **Frida（自备偏移，不用 bridge）** | 进程外注入 | **低**（A 会杀） | 推文件+跑命令，3 分钟 | `report\_frida\02_login_hook.js` + `ba_run.py`，**已实测语法通过、偏移实测校验通过** |
| — | Xposed/LSPosed | Java 层 | **不适用** | — | 见 §7.1：本包 Java hook 已废 |
| — | Zygisk | 注入到 app 进程 | 中低 | 中 | 见 §7.2 |

### 0.3 hook 点（这是"绕过登录判断"的实际落点）

卡死机制（`report\48` §3，与全部 6 条现场观测一致）：

```
LoginTask 的协程
  └─ yield return HttpGameSession.WaitForRequest(...)   <WaitForRequest>d__59
       └─ 每帧查 session.IsFinished                    get_IsFinished @ (无符号名)
            └─ 只有 ResponseHandler / NetworkErrorHandler 被调用才置位
                 └─ 回调按响应 protocol 查表，查不到 ⇒ 两个都不调
                      ⇒ IsFinished 永远 false ⇒ 协程永远 yield ⇒ 卡死
```

**最小干预 = 把 `get_IsFinished()` 强制成 true。** 协程立刻往下走，
"响应有没有被认领给会话"这个问题被整体绕过 —— 这才是"绕过登录判断"的正解，
不是去猜服务端该回什么。

四个 hook 点，按干预强度从轻到重：

| # | 方法名（metadata 明文，已逐个确认） | 目标 | 干预 | 风险 |
|---|---|---|---|---|
| H1 | `get_IsFinished` | 0 参 bool | **返回恒 true** | 极低 ← 默认就用这个 |
| H2 | `get_RequestState` | 0 参枚举 | 返回指定值 | 低 |
| H3 | `HandleAccountAuthResponseMessage` | 1 参 | 只打日志（观察是否被调到） | 无 |
| H4 | `OnLoginFinish` | 0 参 | 强制调用（核弹） | **中**（内部假设不满足会 NRE → 进程死），默认**关** |

### 0.4 本轮实际产出的文件（都能直接用）

```
report\_frida\
  00_env_probe.js          环境侦察（只读，30 秒，判 6 件事）
  02_login_hook.js         主 hook 脚本（4 个 hook 点 + 反检测层 + 符号无关定位）
  ba_run.py                PC 侧一键启动器（含判读表）
  gen_offsets.py           偏移再生成器（版本迁移用）【实测：复现 1201/124，与 report/17 完全一致】
  _out\il2cpp_offsets.h    生成的 C 头

work\ba\runtimehook\
  cave\hook.c              DT_INIT 代码洞 hook（freestanding aarch64 C）【实测：编译通过】
  cave\mk_hook.py          构建 + 打补丁【实测：blob 2128 B / 洞 3056 B / 改动面 2 处】
  cave\libil2cpp_hook.bin  【实测】打好的 270,927,056 B 二进制
  kernelsu_module\         KernelSU 模块全套（module.prop / post-fs-data.sh / README）【实测：语法审查】
  pack.ps1                 一键打 zip
```

---

## 1. 前置条件（缺一条就别动手）

| # | 条件 | 判据 | 谁来确认 |
|---|---|---|---|
| P1 | App 已装且是 3.0.2 (73) | `pm path com.RoamingStar.BlueArchive`；`libil2cpp.so` = **270,927,056 B**，sha256 = `5AC1CBE0FB8F730FFD22B93624A70AE9C90B0A1F3F3FBEB18C5D6AF3C73882C3` | 手机侧 |
| P2 | ★ **`extractNativeLibs=true`** | `/data/app/*/*BlueArchive*/lib/arm64/libil2cpp.so` 存在 | 手机侧（见 §6.1） |
| P3 | root 可用 | `su -c id` 有 `uid=0` | 手机侧 |
| P4 | PC 有 WSL + clang（只做方案 1/2 时需要） | `wsl -e bash -lc "which clang ld.lld llvm-objcopy"` | **本机已确认，clang 18.1.3** |
| P5 | PC 有 `frida==16.5.9`（只做方案 3 时需要） | `pip show frida` | PC |
| P6 | 手机上 `frida-server` 版本与 PC 严格一致（只做方案 3） | `frida-ps` 能列出进程 | 手机侧 |

> **P2 是本方案的唯一硬前提。** 如果 `extractNativeLibs=false`，加载器直接从 APK 里的
> `lib/arm64-v8a/libil2cpp.so` 映射，外面那个 lib 目录不参与 ⇒ 方案 1/2 全部无效。
> 详细的判断命令见 `work\ba\runtimehook\kernelsu_module\README.md` §2。

---

## 2. 为什么"强制 IsFinished"是对的解法

先把已经被排除的假设列清楚（避免重复劳动）：

| 假设 | 状态 | 出处 |
|---|---|---|
| 响应必须是加密的 | **已证**（明文六轮全失败；加密复刻后 canary 命中） | `report\50` §C1 |
| 响应体形状（Error/明文/加密/404）是变量 | **已排除**（四变体行为完全一致） | D-44 |
| 缺 `MxToken` / `SessionKey` / `EncryptedUID` | **已排除**（DTO 里根本没这些属性） | `report\47` §0.1 |
| 缺 3 个信封集合（`MissionProgressDBs` 等） | **已排除**（26 键已补，仍静默） | `report\50` §1.1-E6 |
| 服务端要主动推送 | **已排除**（登录链路零推送依赖） | `report\48` §6.2 + `report\42` §3.1 |
| 有 90 秒超时 | **已排除**（HTTP 层已完成，游戏层无超时） | `report\48` §3.4 |
| `requestid` 缺失 | **降权**（已带 GUID，仍静默） | `report\50` §6 |

剩下的是"这一包被认领给谁"（`protocol` 名字 vs token）。**这个问题只能靠动态解决**，
因为 `ParseProtocol` 无函数体、`methodPointer` 取不到（metadata 表头混淆）。

**而"强制 IsFinished"直接跳过这个不确定性**：

- 它不依赖 `protocol` 到底是什么
- 它不依赖服务端响应内容
- 它是**客户端状态机里唯一那个"下一步要不要走"的布尔位**

代价：响应数据可能没被正确填进 session 对象，协程往下走时读到 null。
但**这正是我们想知道的** —— 如果往下走就 NRE，说明认领确实失败；
如果往下走能进 `OnLoginFinish`，登录就通了。无论哪种，**都比"永久静默"信息量大**。

---

## 3. 方案 3（Frida）：修正版设计

> 排在最后不是因为它最差，而是因为它的**存活率**最低（死因 A 未根治）。
> 但它**不需要重启、不需要打包**，所以作为"快速验证 H1 假设"的工具仍然值得先跑一次。

### 3.1 相对历史尝试，改了什么

| 历史做法 | 为什么死 | 本方案 |
|---|---|---|
| `frida-il2cpp-bridge` | 靠导出名（死因 B） | **完全不用**。只用离线恢复的 9 个模块内偏移 |
| `Module.getExportByName("libil2cpp.so", …)` | 导出名被抹 | **一次都不调**。基址从 `Process.enumerateModules()` 拿，地址 = `base + offset` |
| Java 层 `Java.use('MX.Core.Crypto…')` | 那些是 C# 类，不在 ART 里 | **不碰 Java** |
| 只跑脚本，不管反检测 | ACE 四条必中 | 增加**反检测层**（§3.2） |
| 无偏移自校验 | 版本一变就 hook 野指针 | **每次启动校验 B 桩形态 + 跳转目标在模块内**，不过就整体放弃 |

### 3.2 反检测层（`02_login_hook.js` §2）

四条必中项里，三条可以做成**读取侧伪造**：

| ACE 读什么 | 我们的对策 | 关键技巧 |
|---|---|---|
| `/proc/self/status` 的 `TracerPid: <n>` | 把数字位改成 `0` + 空格 | **等长替换**：`TracerPid:\t1234` → `TracerPid:\t0   `。长度一字不差，`atoi` 读到 `0` 就停 |
| `/proc/self/maps` 里的 `frida` / `gum` / `linjector` | 等长改写子串（`frida` → `frxda`） | 同上，行长度不变 ⇒ 任何按行号/偏移解析的一方都不会错位 |
| `/proc/*/task/*/comm` 的 `gum-js-loop` | 等长改写 | 同上 |
| 端口 27042 | 换端口 / 用 gadget（gadget 不监听） | 老办法，有效但只挡一条 |

实现方式：hook libc 的 `open`/`openat` 记下 fd，再 hook `read`/`pread64` 在
**原 buffer 上原地改**，**绝不改返回值、绝不改长度**。

> **诚实标注**：这层能挡"朴素读文件"的实现，挡不住走 binder/系统服务拿同样信息的实现，
> 也挡不住内核/驱动层扫描。**它是缓解，不是根治。** 根治靠方案 1（不注入）。

### 3.3 运行

```powershell
cd report\_frida

# ① 侦察（30 秒，只读，不 hook）
python ba_run.py --host <IP>:<PORT> --script 00_env_probe.js

# ② 只观察（不改任何东西）；点登录后看哪几行出现
python ba_run.py --host <IP>:<PORT> --spawn --mode probe --duration 120

# ③ 观察 20 秒后自动切成"强制 IsFinished"
python ba_run.py --host <IP>:<PORT> --spawn --mode probe --force is_finished --force-after 20
```

### 3.4 判读（四路交叉）

| 日志 | 说明 | 结论 |
|---|---|---|
| `HndAuth enter` 出现 | 响应被派发到 `LoginTask` | **"认领"是通的** ⇒ 卡死点在其后，开 H1 |
| `IsFin enter` 出现 | `WaitForRequest` 真的在等 `IsFinished` | **卡死点确认** ⇒ H1 可解 |
| `OnFin enter` 出现 | 走到 `OnLoginFinish` 了 | 卡死点在 `OnLoginFinish` 之后（补丁/续接内容） |
| 三个都没出现 | 卡在解析/分发之前 | 转 `00_env_probe.js` 的 TLS 路线（钩 `SSL_read` 看明文有没有到达） |

---

## 4. 方案 1（推荐）：libil2cpp `DT_INIT` 代码洞

### 4.1 为什么它绕过了死因 A

ACE 的四条必中检测全部以"存在一个外部进程/外部映射"为前提。
本方案里 **没有外部进程、没有外部 .so、没有新端口、没有 ptrace** ——
它就是 `libil2cpp.so` 自己的一段代码，在库加载时（`DT_INIT`）执行一次。

而 `libil2cpp.so` 已被实测确认**没有哈希钉死**（ACE 钉的是 `libunity.so` 与
`global-metadata.dat`，见 D-01/D-02 的反面结论）。

### 4.2 载体参数（全部实测）

| 项 | 值 | 依据 |
|---|---|---|
| 代码洞起点 | `0x0f2c2410` | RX 段 `p_filesz` 的结束值**正好**是它；加载器按页映射到最后 `0x0f2c3000` |
| 洞容量 | **3056 B**（`0xBF0`） | 同上；原厂该区间实测全零 |
| 原厂 `DT_INIT` | `0x10496434` | 是**真实的 C++ 静态初始化函数**，不是桩。必须**尾调**它 |
| `DT_INIT` 在文件里的位置 | `0x0fa2fc50`（`.dynamic` 里） | 只改低 4 字节 |
| `pthread_create` 的 GOT 槽 | `0x0fbaff00` | `.rela.plt`，`.dynsym` idx 183；**不走 dlsym** |
| `PT_LOAD` 的 `p_vaddr == p_offset` | 成立 | 所以 vaddr 可以直接当文件偏移 |

### 4.3 入口逻辑（`hook.c` 的 `cave_entry`，实测反汇编）

```asm
f2c2410: stp  x29, x30, [sp, #-0x20]!
f2c2414: str  x19, [sp, #0x10]
f2c2418: mov  x0, #-0x64          ; AT_FDCWD
f2c2420: adr  x1, <log path>
f2c2424: mov  w8, #0x38           ; __NR_openat
f2c2428: mov  w2, #0x441          ; O_WRONLY|O_CREAT|O_APPEND
f2c242c: mov  w3, #0x1a4          ; 0644
f2c2430: svc  #0
...
f2c244c: bl   log_h               ; 写一行 "H 0"
...
```

1. **自定位基址**：`base = &cave_entry - 0x0f2c2410`
2. 用 raw syscall 写一行 `H 0`（区分"洞没执行"与"洞执行了但线程没起来"）
3. 从 GOT 槽 `0xfbaff00` 取 `pthread_create`，起 worker
4. **尾调** `base + 0x10496434`（原厂 `DT_INIT`），静态初始化照常执行

### 4.4 worker 逻辑

```
nanosleep(20s)                    ← 等 il2cpp 初始化完（经验值 5~12s，留裕量）
开日志（append）
写 "H 1"
9 个偏移自校验                   ← B 桩形态 + st_size，任一失败 → 写 "! <idx>" + "V <n>" + 放弃
"E" → il2cpp_class_for_each(on_class, &st) → "X"
"N <扫过的类数>"  "K <命中数>"
每个命中： "T <目标索引>" "k <klass>" "m <MethodInfo*>" "p" ×4（MethodInfo[0..3]）
把 get_IsFinished 的 methodPointer → stub_true（mov w0,#1; ret）
写 "q <槽地址>" "F <个数>"
"D"
```

### 4.5 关键设计决策与它们的理由

| 决策 | 为什么 |
|---|---|
| **不在 `hook.c` 里放任何可写全局** | 洞只有 3056 B。第一版把状态放 `.data`，光 64 条命中就 1536 B，**整个 blob 5048 B 塞不下**。改成放 worker 线程栈上（用 `class_for_each` 的 `userData` 传进去），blob 降到 2128 B，**并且连 mprotect 都不需要了**（纯只读代码，没有 W^X 痕迹） |
| **`cave_entry` 强制带 `section(".text.cave_entry")`** | 实测第一版它落在 `0xf2c2418`（`stub_true` 抢了 `0xf2c2410`）。后果：① `DT_INIT` 会跳进 `stub_true`；② 基址自定位偏 8 字节，之后所有 `base+offset` 全是野指针。已在 `mk_hook.py` 里加**构建期断言**（`llvm-nm` 检查 `cave_entry == CAVE_VA`） |
| **改 `MethodInfo->methodPointer`，不改代码页** | ① 目标函数可能落在 `.text` 的"编码块"里（26% 的页在磁盘上不是正常代码，`report\17` §8.3）；② 改数据不需要 i-cache flush；③ 不碰 RX 页，少一个痕迹 |
| **不硬编码 `methodPointer` 在 `MethodInfo` 的第几个字段** | IL2CPP 2021.3 首字段是 `methodPointer`，2022+ 多了 `virtualMethodPointer`。做法：把前 4 个 qword 全打出来，**挑落在模块地址范围内的那个**（`p` 那 4 行就是给这个用的） |
| **用 `il2cpp_class_get_method_from_name` 反查类，不读 `klass->name`** | `klass+0x10` 的偏移在本包上拿不到二进制实证（`report\17` §8.6：`il2cpp_class_get_type` 的真身落在编码块里，反汇编不出来）。而"按方法名问"天然覆盖 iFix 代理类和子类 |
| **AArch64 `B` 指令的 imm26 按 bit25 符号扩展** | 这是个真坑：写成从 bit31 扩展会得到错的目标地址。实测校验：`0x63c3b50` 处 `d8 38 ff 17` → `b 0x6391eb0`，与 `report\17` 的独立反汇编**完全一致** |

### 4.6 构建（已实测跑通）

```powershell
cd C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\runtimehook\cave
python ..\..\..\report\_frida\gen_offsets.py ..\..\bapatch\libil2cpp.bin --out-dir ..\..\..\report\_frida\_out
copy ..\..\..\report\_frida\_out\il2cpp_offsets.h .
python mk_hook.py --src ..\..\bapatch\libil2cpp.bin
```

**本机实际输出**：

```
[*] blob = 2128 字节，洞容量 = 3056 字节（占用 69.6%）
[*] 断言通过：cave_entry == 0xf2c2410（= CAVE_VA）
[+] 代码洞已写入 0xf2c2410，2128 字节
[+] DT_INIT: 0x10496434 -> 0xf2c2410
[+] 已写出 .../libil2cpp_hook.bin (270927056 B)
    verify: DT_INIT = 0xf2c2410  OK
    verify: cave[0:16] = fd 7b be a9 f3 0b 00 f9 60 0c 80 92 1f 20 03 d5  OK
[*] 改动区域（按 4096 B 间隙合并后）:
      0x0f2c2410 - 0x0f2c2c53  (2116 B)
      0x0fa2fc50 - 0x0fa2fc53  (4 B)
    OK：正好两处 —— 代码洞 + DT_INIT，符合设计
```

产物指纹：

| 文件 | sha256 | 大小 |
|---|---|---|
| 原厂 `libil2cpp.bin` | `5AC1CBE0FB8F730FFD22B93624A70AE9C90B0A1F3F3FBEB18C5D6AF3C73882C3` | 270,927,056 |
| **打完补丁 `libil2cpp_hook.bin`** | `4EA00986A057798FFF8BB03F643058622BD3CBD1292C18484A2673D1DB47755E` | 270,927,056 |

### 4.7 入口反汇编（实测，可人工复核）

```
000000000f2c2410 <cave_entry>:                       ; ← 必须是洞的第一个字节
 f2c2410: a9be7bfd      stp  x29, x30, [sp, #-0x20]!
 f2c2414: f9000bf3      str  x19, [sp, #0x10]
 f2c2418: 92800c60      mov  x0, #-0x64               ; AT_FDCWD
 f2c2420: 100037c1      adr  x1, 0xf2c2b18            ; "/data/local/tmp/ba_hook.log"
 f2c2424: 52800708      mov  w8, #0x38                ; __NR_openat
 f2c2428: 52808822      mov  w2, #0x441               ; O_WRONLY|O_CREAT|O_APPEND
 f2c242c: 52803483      mov  w3, #0x1a4                ; 0644
 f2c2430: d4000001      svc  #0
 ...
 f2c244c: 94000020      bl   0xf2c24cc <log_h>
 ...
000000000f2c2xxx <stub_true>:
 f2c2xxx: 52800020      mov  w0, #0x1
 f2c2xxx: d65f03c0      ret
```

---

## 5. 方案 2：KernelSU 模块（把方案 1 做成可一键装卸的形态）

### 5.1 为什么是 bind-mount，不是"直接覆盖文件"

| 做法 | 问题 |
|---|---|
| `cp` 覆盖 `/data/app/.../lib/arm64/libil2cpp.so` | 改坏 owner / SELinux label；App 更新后失效；**无法自动回滚**；文件真的被改了，出问题只能靠备份 |
| **`mount --bind`（本方案）** | 目标文件**一个字节都没被改过**；卸 mount 立刻回原厂；App 更新后重启自动重挂 |

时机选 `post-fs-data`：它在 **zygote 起来之前** 跑，App 进程都是 zygote fork 出来的，
所以 mount 会被之后所有 App 进程继承 —— **不需要先启动 App**。

### 5.2 手机侧操作（另一个 agent 照这个做）

> 本节是**操作手册**，本仓库不执行。全部命令在手机上跑。

```sh
# ── ① 确认前置（P1/P2）────────────────────────────────────────────
su
T=$(ls /data/app/*/*BlueArchive*/lib/arm64/libil2cpp.so 2>/dev/null | head -1)
echo "target=$T"
#   为空 ⇒ extractNativeLibs=false，方案 1/2 不适用，直接转 §3 的 Frida
ls -l "$T"        # 期望 270927056 字节
sha256sum "$T"    # 期望 5AC1CBE0FB8F730FFD22B93624A70AE9C90B0A1F3F3FBEB18C5D6AF3C73882C3

# ── ② 安装模块 ─────────────────────────────────────────────────────
adb push ba_login_hook.zip /data/local/tmp/     # PC 侧
su -c "ksud module install /data/local/tmp/ba_login_hook.zip"
su -c reboot

# ── ③ 验证 bind-mount 生效 ────────────────────────────────────────
su
cat /data/adb/modules/ba_login_hook/hook_apply.log
#   期望：OK: bind-mount 完成，目标前 4 字节 = fd7bbea9（预期 fd7bbea9）

grep libil2cpp /proc/mounts | grep BlueArchive        # 应有 bind 条目
dd if="$T" bs=1 count=4 2>/dev/null | od -An -tx1     # 期望 fd 7b be a9
cat /data/adb/modules/ba_login_hook/orig_sha256.txt   # 应为原厂 sha256

# ── ④ 看 hook 跑没跑起来 ──────────────────────────────────────────
rm -f /data/local/tmp/ba_hook.log
am force-stop com.RoamingStar.BlueArchive
monkey -p com.RoamingStar.BlueArchive -c android.intent.category.LAUNCHER 1
sleep 40                     # hook 里 sleep 20 秒，留裕量
cat /data/local/tmp/ba_hook.log
```

### 5.3 日志判读（决定性判据在这里）

| 看到 | 含义 | 下一步 |
|---|---|---|
| `H 0000000000000000` | **洞入口执行了** —— patch 与 bind-mount 都生效 | 继续 |
| 连 `H` 都没有 | 洞没执行 | 回 §5.2-③ 逐条查（尤其 `dd` 前 4 字节） |
| `H 0000000000000001` | worker 起来了、已睡完 20 秒 | 继续 |
| 有 `H 0` 无 `H 1` | 崩在 `pthread_create`，或 GOT 槽变了 | `readelf -r` 复核 `pthread_create` 的 `r_offset` |
| `! <idx>` + `V …05` | 偏移自校验失败，**主动放弃（没崩）** | 客户端版本变了 → 重跑 `gen_offsets.py` |
| `V 0000000000000000` | 9 个偏移全过 | 继续 |
| `E` … `X` | `class_for_each` 开始/正常返回 | 继续 |
| `N <个数>` | 扫过的类数，正常**几万** | < 1000 ⇒ il2cpp 还没初始化完，`DELAY_SECONDS` 20→30 |
| `K <个数>` | 5 个目标的命中总数 | `K 0` ⇒ 方法名对不上 / metadata 不可读 |
| `q <地址>` | **这个槽被换成返回桩了 —— 强制生效** | ✅ |
| `F <个数>` | 强制成功数，`get_IsFinished` 期望 ≥1 | `F 0` ⇒ 没命中或 MethodInfo 没有代码指针 |
| `D` | 全部完成 | — |

**业务层面的决定性判据（日志之外）**：

| 屏幕现象 | 说明 |
|---|---|
| 出现**昵称输入框** | ✅ 走到 `ShowNicknamePopup`，登录链路真的往前走了 |
| **进入大厅/主界面** | ✅✅ 完全成功 |
| 出现**任意弹窗** | 链路往前走了但撞到下一个错误 —— **这是进展**，截图取文字 |
| 还是"按钮消失 + 不动" | `F 0`（强制没生效）或卡死在更后面 |

服务端侧独立判据：nginx access log 里 `gsqc-api` 是否出现**第二条**业务请求
（三路交叉：conntrack fresh sport + 文件 mtime + logcat，见 D-45）。

### 5.4 回滚（三条，都干净）

```sh
# A. 最轻：只卸 mount，不用重启，立刻生效
su -c "umount $(ls /data/app/*/*BlueArchive*/lib/arm64/libil2cpp.so | head -1)"
su -c "am force-stop com.RoamingStar.BlueArchive"

# B. 禁用模块 + 重启
su -c "touch /data/adb/modules/ba_login_hook/disable"; su -c reboot

# C. 完全删除
su -c "rm -rf /data/adb/modules/ba_login_hook"; su -c reboot
```

> **原厂 `libil2cpp.so` 从头到尾一个字节都没被改过。** 回滚 = 卸 mount，没有"还原文件"这一步。

---

## 6. 最小可执行路径（如果只有一次机会，按这个顺序做）

```
① 手机侧查 P2（extractNativeLibs）
   ├─ lib/arm64/libil2cpp.so 存在 ──────────────→ 走 ②
   └─ 不存在 ──────────────────────────────────→ 走 ④（Frida）

② PC 侧跑 mk_hook.py（已实测可用，约 1 分钟）
   → work\ba\runtimehook\cave\libil2cpp_hook.bin
   → 核对 sha256 = 4EA00986A057798FFF8BB03F643058622BD3CBD1292C18484A2673D1DB47755E

③ 手机侧：包模块 → 装 → 重启 → 看 /data/local/tmp/ba_hook.log
   ├─ 出现 "q <地址>" 和 "F 1" ────────────────→ ✅ 强制生效，点登录看屏幕
   ├─ "V <非0>" ───────────────────────────────→ 版本不符，重跑 gen_offsets.py
   └─ 连 "H 0" 都没有 ─────────────────────────→ bind-mount 没生效，查 §5.2-③

④ Frida 路线（不需要重启）：
   python ba_run.py --spawn --mode probe --duration 120     ← 先确认 hook 点
   python ba_run.py --spawn --mode force --force is_finished ← 再强制
```

**关键点：③ 和 ④ 的判据是同一个 —— `get_IsFinished` 有没有被改成恒 true。**
两种载体只是"把真相告诉客户端"的手段，逻辑完全一致。

---

## 7. 另外两条路为什么不做

### 7.1 Xposed/LSPosed（任务清单里的方案 3）

**本包的 Java 层 hook 已废**，这不是"没试"，是试过并查明原因：

- `report\DEADENDS.md` **D-33**：`XposedHelpers.findAndHookMethod` / `hookAllMethods`
  全部 `NoSuchMethodError`。原因：**App 自带同名 `de.robv.android.xposed.*` 替身类，类加载器遮蔽**。
  `report\17` 的实测里能看到进程内存在 `LUnEw/z/NP/i/NLAT/v/Q/S/XposedBridge` 这类混淆替身。
- 而且我们要 hook 的 `LoginTask` / `HttpGameSession` / `NetworkService` / `MX.Core.Crypto.*`
  **全是 C# 类，活在 il2cpp 元数据里，不是 ART 的 Java 类**。
  `Java.enumerateLoadedClasses` 无论枚举得多全也看不到它们（`report\38` §5A 后果 1）。

> D-33 的教训里有一句是对的：**hook 框架类**（`javax.net.ssl.*`、`android.security.net.config.*`）
> 不受影响，因为它们在 boot classpath。但那与"绕过登录判断"无关。
> 所以 LSPosed 在本任务上**不适用**，不是优先级低。

### 7.2 Zygisk（任务清单里的方案 2 的后半）

技术上可行（`JNI_OnLoad` / `zygisk_module_entry` 里做 inline hook），但不推荐做首选：

| 理由 | 说明 |
|---|---|
| 痕迹面比方案 1 大 | 模块 `.so` 会出现在 app 进程的 `/proc/self/maps` 里 —— **正好是 ACE 的判据之一** |
| KernelSU 本身**不带 Zygisk** | 需要额外装 ZygiskNext，多一个依赖、多一个不稳定面 |
| Zygisk ABI 要对齐 | 需要官方的 `zygisk.hpp` / `api.h`，本机无法编译验证（无 NDK） |
| 没有收益 | 方案 1 已经能做到同样的事，且**一条检测都不碰** |

> 如果将来 P2 变成 `extractNativeLibs=false`（无法 bind-mount）而 Frida 又被杀，
> 那时才值得上 Zygisk。`hook.c` 里的发现/打补丁逻辑**可以原样复用**，
> 只是把入口从 `cave_entry` 换成 `zygisk_module_entry`。

---

## 8. 偏移表（本包的权威值，实测）

来源：`report\_tmp\hookeval\il2cpp_syms.json`（1201 个具名导出，其中 124 个 `il2cpp_*`），
本轮用 `gen_offsets.py` **重新独立复现并逐条校验**：

```
[*] 恢复具名导出 1201 个，其中 il2cpp_* 124 个      ← 与 report/17 完全一致
[*] .text 范围 0x59b8000 - 0x64c1260
    ok  il2cpp_class_for_each                    0x063c3b50  b -> 0x6391eb0
    ok  il2cpp_class_get_methods                 0x063c2ea8  b -> 0x640b084
    ok  il2cpp_class_get_method_from_name        0x063c2eac  b -> 0x640b1e8
    ok  il2cpp_method_get_name                   0x063c37bc  b -> 0x63926a8
    ok  il2cpp_method_get_param_count            0x063c37cc  b -> 0x6392898
    ok  il2cpp_thread_attach                     0x063c38d4  b -> 0x6393608
    ok  il2cpp_class_get_type                    0x063c2eec  b -> 0x640dcb0
    ok  il2cpp_type_get_name_chunked             0x063c3b30  真实函数体 (st_size=16)
    ok  il2cpp_runtime_class_init                0x063c38a0  b -> 0x63afb88
[+] 成功：25 个 API 全部通过 B 桩校验
```

> `0x063c3b50 → b 0x6391eb0` 与 `report/17` §1.2 由**完全不同的方法**（人工反汇编）得出的结论一致，
> 这是一次独立交叉验证。

**hook 目标方法的 metadata 偏移**（`global-metadata.dat` 里是**明文 ASCII**，已逐个确认）：

| 方法名 | get_ 偏移 | 裸名偏移 | 备注 |
|---|---|---|---|
| `get_IsFinished` | `0x21A583` | `IsFinished` @ `0x21A5B3`，`<IsFinished>k__BackingField` @ `0x2271A3` | **注意**：`IsFinished` 另有 `0x226FB4` 一处 ⇒ 可能有**两个类**都有这个属性，脚本必须全处理 |
| `HandleAccountAuthResponseMessage` | `0x13FACF` | — | `LoginTask` 上，1 个参数；另有日志标签 @ `0x40BEDB` |
| `OnLoginFinish` | `0x13FAF0` | — | 0 参；`<OnLoginFinish>g__CompletePatch\|4` @ `0x1404F1` |
| `OnLoginFail` | `0x13FBCD` | — | 0 参 |
| `get_RequestState` | `0x21A47D` | `RequestState` @ `0x21A544` | `HttpGameMessage` |
| `ParseProtocol` | `0x219D1A` | — | 观测用 |
| `LoginState` | `0x13FDD3` | `loginState` @ `0x13FD9B` | 枚举，只有 `Finished`/`Failed` |
| `<WaitForRequest>d__59` | `0x21A802` | `WaitForRequest` @ `0x21A6D6` | 协程状态机 |

---

## 9. 风险清单（诚实标注）

| # | 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|---|
| R1 | `extractNativeLibs=false` | **中** | 方案 1/2 完全不适用 | §1-P2 先查；不满足转 Frida |
| R2 | ACE **持续**轮询而非启动期一次性扫描 | 中 | 方案 1 也可能被杀 | 日志会停在 `H` 之后；此时改走 Frida（它能改检测面） |
| R3 | 客户端更新 → 偏移全变 | 高（长期） | 打印 `V <非0>` 后主动放弃（**不崩**） | 重跑 `gen_offsets.py` + `mk_hook.py` |
| R4 | `get_IsFinished` 属于**两个类**，只强制了一个 | 中 | 不生效 | 脚本会打印全部命中（`T/k/m/p`），按目标索引全部强制 |
| R5 | `IsFinished` 不是卡点（卡在更上游） | 中 | 强制了也没用 | 这正是 `HndAuth`/`IsFin`/`OnFin` 三路日志存在的意义 —— 它们能定位卡点真实位置 |
| R6 | 强制 `OnLoginFinish` 内部 NRE → 进程死 | 中 | 崩溃 | 默认**关**。要开就单独编一版，且只触发一次 |
| R7 | `MethodInfo->methodPointer` 所在页 mprotect 被察觉 | 低 | 未知 | 只短暂 RW→RX，且只动一页 |
| R8 | Frida 的反检测层挡不住 binder/内核层获取的信息 | 高 | Frida 仍被杀 | 这是已知局限；方案 1 才是根治 |
| R9 | 手机上 `frida-server` 版本与 PC 不一致 | 中 | 连不上 | 严格对齐 16.5.9 |

---

## 10. 如果这条路走不通，为什么

诚实地说清楚三种"走不通"的形态，以及各自的判据：

| 形态 | 判据 | 为什么走不通 | 还剩什么 |
|---|---|---|---|
| **P2 不满足**（`extractNativeLibs=false`） | `/data/app/*/*BlueArchive*/lib/arm64/` 不存在 | 加载器从 APK 内直接映射，文件系统层的任何手段都无效。改成 `true` 要重打包重签，直接撞 ACE 的签名面（D-04~D-06 已证：dex 结构变化会让 App 卡启动界面） | Frida（低存活率）；或改服务端让响应被正确认领（`report\50` §5 的 E1/E0 实验） |
| **R2 成立**（ACE 持续轮询） | hook 日志停在 `H 0` 之后，且 Frida 也在 10 秒内被杀 | 说明 ACE 在任何时刻都要求"映射集合 = 原厂"。那么任何"往进程里加东西"的方案（含 gadget/Zygisk）都不成立 | 只能靠**服务端侧**让协议完全正确（把 `protocol` 用 token 回显，`report\48` §9 实验 1）—— 那条路是纯服务端改动，不碰客户端 |
| **R5 成立**（`IsFinished` 不是卡点） | 日志显示 `HndAuth`/`IsFin` **都没出现** | 说明响应在"分发到 LoginTask"之前就被丢了。这时的卡点在上游（`ParseProtocol` / 会话匹配），而 `ParseProtocol` 无函数体、不可静态分析 | 转 `00_env_probe.js` 的 TLS 路线：钩 `SSL_read` 确认明文有没有到达；或直接在服务端做 E1/E0 实验 |

**最重要的一句**：即使方案 1/2 全部失败，**本轮也把"Frida 为什么失败"这个问题彻底答清了**
（死因 A 与死因 B 分离，D-31/D-32 的两条历史结论得到纠正），
并且给出了一个**不注入、不依赖符号名、不依赖 ACE 行为**的客户端补丁载体。
这个载体本身的机制（自定位基址 + 离线偏移 + 按方法名反查类 + 改 `methodPointer`）
与"登录"无关，可以复用到任何"要改某个 C# 方法返回值"的场景。

---

## 11. 文件索引

| 路径 | 作用 | 状态 |
|---|---|---|
| `report\_frida\00_env_probe.js` | 环境侦察（只读） | 语法实测通过 |
| `report\_frida\02_login_hook.js` | 主 hook（Frida 路线） | 语法实测通过；9 个偏移实测校验通过 |
| `report\_frida\ba_run.py` | PC 侧启动器 + 判读表 | — |
| `report\_frida\gen_offsets.py` | 偏移再生成 | **实测：复现 1201/124，25 个 API 全部校验通过** |
| `report\_frida\_out\il2cpp_offsets.h` | 生成的 C 头 | 实测生成 |
| `report\_frida\_out\offsets_js_snippet.txt` | 生成的 JS 片段 | 实测生成 |
| `work\ba\runtimehook\cave\hook.c` | 代码洞 hook 源码 | **实测：clang 18 编译通过** |
| `work\ba\runtimehook\cave\mk_hook.py` | 构建 + 打补丁 + 断言 | **实测：blob 2128 B，改动面 2 处** |
| `work\ba\runtimehook\cave\libil2cpp_hook.bin` | 成品二进制 | **实测生成，sha256 `4EA00986…755E`** |
| `work\ba\runtimehook\kernelsu_module\` | KernelSU 模块全套 + 操作手册 | — |
| `work\ba\runtimehook\pack.ps1` | 一键打 zip | — |
| `report\53-客户端补丁方案-运行时hook绕过登录.md` | 本文件 | — |

---

## 12. 诚实标注

| 结论 | 状态 |
|---|---|
| `il2cpp_*` 可 dlsym 的 = 0 | **确证**（`.dynsym` 2660 条，带名 306 全是导入） |
| 124 个 `il2cpp_*` 偏移可恢复且可用 | **确证**（本轮独立复现，1201/124，B 桩形态全通过） |
| `0x063c3b50 → b 0x6391eb0` | **确证**（两套独立方法得出同一结果） |
| 5 个 hook 目标方法名在 metadata 里是明文 ASCII | **确证**（逐字节扫描） |
| 代码洞 3056 B、`DT_INIT = 0x10496434`、`pthread_create` GOT `0xfbaff00` | **确证**（来自 `report/17` §8.2 的实测，本轮沿用） |
| blob 2128 B 能装进洞、改动面正好 2 处 | **实测**（本机 clang 构建 + 打补丁 + diff） |
| `get_IsFinished` 是真正的卡点 | **强推断**（`report/48` §3，由 `WaitForRequest`/`IsFinished` 双回调结构推出） |
| 强制 `IsFinished = true` 能让登录走通 | **推断**——**未上机验证**。但即使它只让流程"往前走到下一个错"，那也是有价值的诊断 |
| Frida 在本包上的存活率 | **推断为低**：死因 A 只能缓解不能根治 |
| `is_finished` 是否真的被 `WaitForRequest` 每帧检查 | **推断**（无函数体，看不到循环） |
| 两个类都有 `IsFinished` | **推断（中）**——`GetIsFinished` 与 `IsFinished` 在 metadata 里各有 2 处独立出现 |

> **本报告没有一条"上机结果"** —— 因为任务明确要求"不要动手机"。
> 所有实测结论都来自本机二进制分析与编译验证；所有"会不会成功"的判断都是推断，
> 并且每条都给了**用哪一行日志证伪**的判据（§5.3 / §3.4）。
