# PROBE README —— Pass 1 最小探针（libil2cpp_probe.bin）

> 目的：**只验三件事**，二进制判定，不做任何修改。
> 1. `il2cpp_class_for_each` 的地址（`0x063c3b50`，从被抹名的符号表反推）对不对
> 2. 回调调用约定对不对
> 3. `DT_INIT` 里能不能起线程、延迟后能不能调 il2cpp API

---

## 0. 成品与构建

| 文件 | 说明 |
|---|---|
| `probe.S` | 探针源码（aarch64 汇编，456 字节 blob） |
| `mkprobe.py` | 编译 + 写洞 + 改 `DT_INIT`，一条龙 |
| `probe.bin` / `probe.o` / `probe.elf` | 中间产物 |
| **`libil2cpp_probe.bin`** | **成品，270,927,056 B，可直接上机** |

构建（已在本机跑通，clang 在 WSL 里）：

```powershell
cd C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\bapatch
python mkprobe.py                        # 从 libil2cpp.bin（原厂）构建
python mkprobe.py --src libil2cpp_patched.bin --out x.bin   # 换源
```

> 依赖：WSL 里的 `clang` / `ld.lld` / `llvm-objcopy`。
> 本机 `C:\msys64` 的 `as`/`gcc` 是 **x86** 的，不能编 aarch64 —— 这是第一版失败的原因。

构建输出（实测）：

```
[*] blob size = 456, head = fd 7b bc a9 fd 03 00 91 f3 53 01 a9 f5 13 00 f9
[+] blob written at 0xf2c2410, 456 bytes (cave capacity 3056)
[+] DT_INIT: 0x10496434 -> 0xf2c2410
[+] wrote libil2cpp_probe.bin (270927056 bytes)
```

**全文 diff 只有两处**（已实测）：

| 区域 | 字节数 | 内容 |
|---|---|---|
| `0xf2c2410 – 0xf2c25d3` | 452 | 探针代码 + 字面量池 |
| `0xfa2fc50 – 0xfa2fc53` | 4 | `.dynamic` 里 `DT_INIT` 的值（低 4 字节） |

---

## 1. 这一版到底做了什么

```
DT_INIT（加载线程，必须立刻返回）
  ├─ openat(AT_FDCWD, probe.log, O_WRONLY|O_CREAT|O_APPEND, 0644)
  ├─ write("START\n")
  ├─ pthread_create(&tid, NULL, worker, base)   ← 唯一一处 libc 依赖（走 libil2cpp 自己的 GOT 槽）
  ├─ close()
  └─ br 0x10496434                              ← 尾调**原厂 DT_INIT**，静态初始化照常执行

worker 线程
  ├─ nanosleep(15s)
  ├─ openat(append)
  ├─ write("BEFORE_ENUM\n")
  ├─ bl  base+0x063c3b50   (il2cpp_class_for_each, 回调 = 立即 ret)
  ├─ write("END\n")
  └─ close() ; ret
```

日志文件：`/data/data/com.RoamingStar.BlueArchive/files/probe.log`

---

## 2. 七个技术点的答复

| # | 问题 | 答复 |
|---|---|---|
| 1 | `pthread_create` 在不在 1201 个符号里？ | **不在**（1201 个是 `gnu.hash` 里的**定义**符号）。但它在 **306 个保留名字的导入**里（`.dynsym` idx=183，`shndx=0`），所以我走 **libil2cpp 自己的 `.rela.plt` GOT 槽 `0x0fbaff00`**：`ldr x9,=0xfbaff00; add x9,x19,x9; ldr x9,[x9]; blr x9`。不需要 `clone`、不需要 dlsym。 |
| 2 | 延迟怎么做？ | **raw syscall `nanosleep`**（`x8=101`），不碰 libc。`usleep` 也在导入表里（idx 219），但没必要。 |
| 3 | 写日志怎么做？ | **raw syscall**：`openat(56)` / `write(64)` / `close(57)`。libc 的 `open`/`write`/`close`/`fopen`/`fwrite` 都在导入表（idx 72/55/66/140/145），但 ACE 包了 libc，能不用就不用。 |
| 4 | 洞容量 | **`0xf2c2410` 起共 3056 字节（0xBF0）**。依据：RX 段的 `p_filesz` 结束值**正好**是 `0xf2c2410`，而加载器按页映射，页尾到 `0xf2c3000` 都在这张 RX 页里，所以 `[0xf2c2410, 0xf2c3000)` 映射+可执行。这版只用了 456 B。 |
| 5 | `DT_INIT` 怎么改 | ⚠️ **你的前提要修正**：`libil2cpp.bin`（原厂）的 `DT_INIT = 0x10496434`，那是一个**真实的 C++ 静态初始化函数**（`stp x29,x30,[sp,#-16]!; mov x29,sp; bl 0x10496094; ...`），**不是跳洞的桩**。真正把 DT_INIT 指向洞里的是 `libil2cpp_patched.bin`（g20 那版：`DT_INIT=0xf2c2410`，洞里是旧桩 `f3 53 b6 a9 …`）。所以我这版**从原厂 `libil2cpp.bin` 构建**：把 `DT_INIT` 改成 `0xf2c2410`，洞里 `br` 回 `0x10496434`（尾调原厂初始化）。**顺带把坏掉的 g20 旧桩彻底清掉了**。 |
| 6 | `adr` 用局部标签 | 已遵守：所有 `adrp/adr` 只引用 `.Lpath` / `.Ls_*` / `.Lthread` / `.Lcb` 这类 **`.L` 局部标签**，没有任何 `.globl` 符号参与取址。（`probe_entry` 是 `.globl`，只作 `adrp` 的基准点，同目标文件内解析。） |
| 7 | 回调签名权威依据 | 反汇编 `il2cpp_class_for_each` 真身 `0x6391eb0`：<br>`+0x10 MOV x19,x1`（保存 userData）<br>`+0x14 MOV x20,x0`（保存 callback）<br>`+0x40 MOV x0,x22`（klass）<br>`+0x58 MOV x1,x19`（userData）<br>`+0x5c BLR x20`<br>⇒ **`void (*)(Il2CppClass *klass, void *userData)`，x0=klass，x1=userData** —— 与 Unity `il2cpp-api.h` 声明一致，且是二进制实证。 |

---

## 3. 上机步骤

```sh
# ① 备份原厂（必须）
adb shell "su -c 'cp /data/app/*/com.RoamingStar.BlueArchive*/lib/arm64/libil2cpp.so /data/local/tmp/libil2cpp.baseline.so'"

# ② 推探针并原子替换
adb push work/ba/bapatch/libil2cpp_probe.bin /data/local/tmp/libil2cpp.so
adb shell "su -c 'cp /data/local/tmp/libil2cpp.so /data/app/*/com.RoamingStar.BlueArchive*/lib/arm64/libil2cpp.so'"
adb shell "su -c 'chown -R system:system /data/app/*/com.RoamingStar.BlueArchive*/lib/arm64/libil2cpp.so'"
adb shell "su -c 'chmod 644 /data/app/*/com.RoamingStar.BlueArchive*/lib/arm64/libil2cpp.so'"
# 注意：/data/app 是 dm-verity 之外的可写目录，不要碰 /system
# 若包路径带随机后缀，先 `adb shell pm path com.RoamingStar.BlueArchive` 确认

# ③ 清日志、启动、等 60 秒
adb shell "su -c 'rm -f /data/data/com.RoamingStar.BlueArchive/files/probe.log'"
adb shell monkey -p com.RoamingStar.BlueArchive -c android.intent.category.LAUNCHER 1
sleep 60

# ④ 读日志
adb shell "su -c 'cat /data/data/com.RoamingStar.BlueArchive/files/probe.log'"
adb shell "su -c 'ls -l /data/data/com.RoamingStar.BlueArchive/files/probe.log'"
```

> 若 `files/` 不可写（SELinux），日志会写到失败 —— 那也是一种信息（`START` 都没有 ⇒ 连 open 都失败 ⇒ 换路径 `/data/local/tmp/probe.log`，改 `probe.S` 里 `.Lpath` 后重编）。

---

## 4. 怎么读 log（三种失败形态）

| log 内容 | 结论 | 下一步 |
|---|---|---|
| 文件不存在 | `DT_INIT` 没执行到 / 洞没被映射 | 检查 patch 是否写进对了文件（`adb shell md5sum`）；检查 `DT_INIT` 值 |
| 只有 `START` | 崩在 `pthread_create` 或线程入口 | GOT 槽 `0xfbaff00` 可能不对 → 用 `readelf -r` 复核 `.rela.plt` 里 `pthread_create` 的 `r_offset` |
| `START` + `BEFORE_ENUM`，无 `END` | **崩在 `il2cpp_class_for_each`** = 地址或调用约定错 | 先用 §2#7 的方式复核桩；再试 `base+0x6391eb0`（绕过桩直接调真身） |
| `START` + `BEFORE_ENUM` + `END` | **探针成功**：地址、调用约定、线程上下文全对 | 进 Pass 2：回调里做枚举 |

> 若出现 `START`+`BEFORE_ENUM` 后游戏直接退出但没有 tombstone —— 优先怀疑回调签名，而不是地址（地址错通常立刻 SIGSEGV，有 tombstone）。

---

## 5. 回滚

```sh
adb shell "su -c 'cp /data/local/tmp/libil2cpp.baseline.so /data/app/*/com.RoamingStar.BlueArchive*/lib/arm64/libil2cpp.so'"
adb shell "su -c 'chown system:system .../libil2cpp.so; chmod 644 .../libil2cpp.so'"
```

---

## 6. 已知边界

- 本探针**不修改任何游戏状态**，只有一个 `open/write/close` 日志文件和一个 `nanosleep`。
- 15 秒延迟是**经验值**：Unity 把 il2cpp 初始化放在 `UnityPlayer` 起来之后，通常 5~12 秒；若 `BEFORE_ENUM` 出现但 `END` 没有，且 tombstone 里的 PC 落在 `libil2cpp` 的 il2cpp 数据区，可能是初始化还没完 → 把 `probe.S` 里的 `mov x0,#15` 改成 25~30 再编。
- `il2cpp_class_for_each` 在 il2cpp 里是**全局类遍历**，几万次回调；本版回调是 `ret`，开销可忽略。
