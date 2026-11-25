# KernelSU 模块：BA 登录 Hook（libil2cpp DT_INIT 代码洞）

> 本模块把**预先打好补丁的 `libil2cpp.so`** bind-mount 到已安装 App 的 lib 目录。
> 补丁内容：在 libil2cpp 的代码洞里放一段自定位的 hook，加载时起一个线程，
> 20 秒后把 `get_IsFinished()` 的 `methodPointer` 换成 `mov w0,#1; ret`，
> 于是 `HttpGameSession.WaitForRequest` 的那个 `yield` 立刻满足，登录链路继续往下走。
>
> **不装 Frida、不起进程、不监听端口、不 ptrace、不改 APK 签名。**
> 卸载或禁用模块 + 重启 = 完全还原（App 目录里那个文件一个字节都没被改过）。

---

## 0. 为什么是这个载体（先说清楚，免得重复踩坑）

历史上 Frida 试过十几次，全部被 ACE 主动杀（`SIGBUS`，`ApplicationExitInfo reason=2 status=7`）。
四项**必中**检测，每一条 Frida 都躲不掉（`report/DEADENDS.md` D-30）：

| 检测面 | Frida 为什么必中 |
|---|---|
| `/proc/self/maps` 里 `frida-agent` 的映射行 | agent 是独立 .so，必然出现在 maps |
| 线程名 `gum-js-loop` / `pool-frida` | gum 自己起线程，名字写死 |
| 端口 27042 | frida-server 监听 |
| `/proc/self/status` 的 `TracerPid != 0` | attach 本质就是 ptrace |

本模块这条路**四条全不成立**：它就是 libil2cpp 自己的一段代码，没有任何"外部"。

而 `libil2cpp.so` 已被实测确认**没有哈希钉死**（ACE 钉的是 `libunity.so` 与
`global-metadata.dat`，见 `report/DEADENDS.md` D-01/D-02 的反面结论）。

> 同时也说明为什么 `frida-il2cpp-bridge` 在本包上无论如何都跑不起来：
> 它靠 `Module.getExportByName("libil2cpp.so", "il2cpp_*")`，而本包
> `.dynsym` 2660 条里带名的 306 条**全是导入**，`il2cpp_*` 可 dlsym 的 **0 个**
> （`report/38-Frida部署清单.md` §5A 实测，`report/DEADENDS.md` D-31/D-32）。
> 我们用的是**离线恢复的模块内偏移**，不靠名字。

---

## 1. 前置条件（逐条确认，缺一条就别往下走）

| # | 条件 | 怎么确认 |
|---|---|---|
| 1 | **KernelSU** 已装且 root 正常 | `su -c id` → 有 `uid=0` |
| 2 | **Android 版本任意**（不必是 17） | — |
| 3 | App 已安装：`com.RoamingStar.BlueArchive` | `pm path com.RoamingStar.BlueArchive` |
| 4 | ABI 是 **arm64-v8a** | `ls /data/app/*/*BlueArchive*/lib/` 应有 `arm64` |
| 5 | ★ **`extractNativeLibs=true`** | 见 §2 —— **这是本方案的唯一硬前提** |
| 6 | `libil2cpp.so` 大小 **270,927,056 字节** | `ls -l /data/app/*/*BlueArchive*/lib/arm64/libil2cpp.so` |

---

## 2. ★ 硬前提：`extractNativeLibs` 必须是 true

两种情况的区别：

```
extractNativeLibs = true   →  so 被解压到 /data/app/<pkg>-<rand>/lib/arm64/
                              加载器从这里 mmap  → 替换/bind-mount 这个文件有效  ✅
extractNativeLibs = false  →  加载器直接从 APK 里的 lib/arm64-v8a/ 映射
                              外面那个 lib 目录根本不存在或不参与  → 本方案无效  ❌
```

**怎么查**（手机侧，root）：

```sh
APK=$(pm path com.RoamingStar.BlueArchive | sed 's/package://')
# 1) 这个目录存不存在？存在就大概率是 true
ls -l /data/app/*/*BlueArchive*/lib/arm64/libil2cpp.so

# 2) 更权威：看 manifest 里的 flag
su -c "aapt2 dump xmltree --file AndroidManifest.xml '$APK'" 2>/dev/null \
  | grep -i extractNativeLibs
#    有 extractNativeLibs(0x...)=true   →  ✅
#    有 extractNativeLibs(0x...)=false  →  ❌ 本方案不适用，改走 §8 的备选
#    没有这一行                          →  AndroidManifest 默认值取决于
#                                          minSdkVersion：>=23 时默认 false
```

如果结果是 **false**，有两条出路：
1. 用 `report/_frida/` 那套 Frida 方案（成功率低，且 ACE 会杀）；
2. 把 APK 解包、`extractNativeLibs` 改 true、换 so、重签 —— **但这会撞 ACE 的签名面**（`report/DEADENDS.md` D-04 ~ D-06），**不推荐**。

> 补充判据（更简单）：直接看 `/data/app/*/*BlueArchive*/lib/arm64/` 里有没有 `libil2cpp.so`。
> 有 = 大概率可行；没有 = 一定不行。

---

## 3. 在 PC 上生成补丁后的 `libil2cpp.so`

> ⚠️ 需要 **WSL + clang**（`--target=aarch64-linux-android26`）。
> 本机 `C:\msys64` 的 as/gcc 是 x86 的，编不了 aarch64 —— 这是历史上第一版失败的原因。
>
> 检查：`wsl -e bash -lc "which clang ld.lld llvm-objcopy"`

```powershell
cd C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\runtimehook\cave

# ① 准备偏移头（首次 / 客户端更新后必须做）
python ..\..\..\report\_frida\gen_offsets.py ^
       ..\..\bapatch\libil2cpp.bin --out-dir ..\..\..\report\_frida\_out
copy ..\..\..\report\_frida\_out\il2cpp_offsets.h .

# ② 构建 + 打补丁
python mk_hook.py --src ..\..\bapatch\libil2cpp.bin

# 期望输出：
#   [*] blob = 2128 字节，洞容量 = 3056 字节（占用 69.6%）
#   [*] 断言通过：cave_entry == 0xf2c2410（= CAVE_VA）
#   [+] DT_INIT: 0x10496434 -> 0xf2c2410
#   [*] 改动区域（按 4096 B 间隙合并后）:
#         0x0f2c2410 - 0x0f2c2c53  (2116 B)
#         0x0fa2fc50 - 0x0fa2fc53  (4 B)
#       OK：正好两处 —— 代码洞 + DT_INIT，符合设计
```

产出的 `libil2cpp_hook.bin`：

| 项 | 值（本机实测） |
|---|---|
| 大小 | 270,927,056 B（与原厂一致） |
| sha256 | `4EA00986A057798FFF8BB03F643058622BD3CBD1292C18484A2673D1DB47755E` |
| 原厂 sha256 | `5AC1CBE0FB8F730FFD22B93624A70AE9C90B0A1F3F3FBEB18C5D6AF3C73882C3` |
| 改动面 | 仅 2 处：`0x0f2c2410–0x0f2c2c53`（代码洞）+ `0x0fa2fc50`（DT_INIT 低 4 字节） |

> 客户端更新后偏移一定会变。**不要忘了重跑 gen_offsets.py**，
> 否则 hook 里的自校验会打印 `! <索引>` + `V 5` 然后主动放弃（不会崩，这是设计好的保险）。

---

## 4. 打包成 KernelSU 模块

```powershell
cd C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\runtimehook
.\pack.ps1
# 产出：ba_login_hook.zip（约 90 MB，因为里面有 270 MB 的 so 压缩后）
```

`pack.ps1` 做的事：把 `kernelsu_module/` 打成 zip，并把 `cave/libil2cpp_hook.bin`
改名成 `libil2cpp.so` 放进模块根目录。

也可以手工：

```powershell
Copy-Item cave\libil2cpp_hook.bin kernelsu_module\libil2cpp.so
Compress-Archive -Path kernelsu_module\* -DestinationPath ba_login_hook.zip -Force
```

---

## 5. 手机侧操作（另一个 agent 照这个做）

> **本仓库不执行任何手机操作。以下命令由执行方在手机上手动跑。**

### 5.1 安装

```sh
# 把 ba_login_hook.zip 推到手机
adb push ba_login_hook.zip /data/local/tmp/

# 用 KernelSU 管理器 App 安装（推荐，别用命令行，避免签名/权限问题）
#   KernelSU → 模块 → 从本地安装 → 选 /data/local/tmp/ba_login_hook.zip

# 或者命令行（KernelSU 自带 ksud）
su -c "ksud module install /data/local/tmp/ba_login_hook.zip"

# 重启（post-fs-data 只在开机时跑）
su -c reboot
```

### 5.2 验证 bind-mount 生效了

```sh
su
# ① 看 post-fs-data 自己的日志
cat /data/adb/modules/ba_login_hook/hook_apply.log
#   期望看到： "OK: bind-mount 完成，目标前 4 字节 = fd7bbea9（预期 fd7bbea9）"

# ② 看 mount 表里有没有我们的 bind
grep libil2cpp /proc/mounts | grep BlueArchive
#   期望：/data/app/.../lib/arm64/libil2cpp.so /data/app/.../lib/arm64/libil2cpp.so
#         (bind 的目标和源会显示成同一路径)

# ③ 确认读到的确实是我们的 blob（前 4 字节 = fd 7b be a9 = stp x29,x30,[sp,#-0x20]!）
T=$(ls /data/app/*/*BlueArchive*/lib/arm64/libil2cpp.so | head -1)
dd if="$T" bs=1 count=4 2>/dev/null | od -An -tx1
#   期望： fd 7b be a9

# ④ 原厂文件没被动过（sha256 应该和记录一致）
cat /data/adb/modules/ba_login_hook/orig_sha256.txt
#   期望： 5AC1CBE0FB8F730FFD22B93624A70AE9C90B0A1F3F3FBEB18C5D6AF3C73882C3
```

### 5.3 看 hook 有没有真的跑起来（这才是决定性判据）

```sh
su
rm -f /data/local/tmp/ba_hook.log        # 清旧日志
am force-stop com.RoamingStar.BlueArchive
monkey -p com.RoamingStar.BlueArchive -c android.intent.category.LAUNCHER 1

# 等 40 秒（hook 里 sleep 20 秒，再留裕量）
sleep 40
cat /data/local/tmp/ba_hook.log
```

**日志格式**：每行 = 1 个标签字符 + 空格 + 16 位小写十六进制（或十进制索引）+ 换行。

### 5.4 判读表（按出现顺序）

| 行 | 含义 | 下一步 |
|---|---|---|
| `H 0000000000000000` | **洞入口执行了**。DT_INIT patch 成功、代码在真机跑起来了 | 继续往下看 |
| *（连 `H` 都没有）* | 洞没执行 —— patch 没生效 / bind-mount 没生效 / App 没加载这个 so | 回 §5.2 逐条查 |
| `H 0000000000000001` | worker 线程起来了，且已经睡了 20 秒 | 继续 |
| *（有 `H 0` 无 `H 1`）* | 崩在 `pthread_create`，或 GOT 槽 `0xfbaff00` 不对 | 见 §7 排错 |
| `! <索引>` + `V 00000000000000NN` | 第 N 个偏移自校验失败，**主动放弃**（没崩，这是保险） | 客户端版本变了 → 重跑 `gen_offsets.py` |
| `V 0000000000000000` | 9 个偏移全部通过自校验 | 继续 |
| `E` … `X` | `il2cpp_class_for_each` 开始/正常返回 | 继续 |
| `N <个数>` | 扫过的 Il2CppClass 数。正常应是**几万** | 若 < 1000，说明 il2cpp 还没初始化完 → 把 `DELAY_SECONDS` 从 20 改到 30 |
| `K <个数>` | 5 个目标方法的命中总数 | `K 0` ⇒ 方法名对不上或 metadata 不可读 |
| `T/<k>/<m>/p×4` | 每个命中的目标索引、Il2CppClass*、MethodInfo*、MethodInfo 前 4 个 qword | 看 `p` 那 4 行：落在 libil2cpp 地址范围的那个就是 `methodPointer` |
| `q <地址>` | **这个槽被改成返回桩了** —— 强制生效 | **这就是成功的标志** |
| `F <个数>` | 强制成功个数。`get_IsFinished` 期望 ≥1 | `F 0` ⇒ 没找到 `get_IsFinished` 或它的 MethodInfo 没有代码指针 |
| `D` | 全部完成 | — |

### 5.5 决定性的业务判据（日志之外）

hook 成功之后，**屏幕**上应该出现变化（不再"按钮文字消失 + 永远不动"）：

| 现象 | 说明 |
|---|---|
| 出现昵称输入框 | ✅ 走到 `ShowNicknamePopup` 了，登录链路真的往前走了 |
| 进入大厅/主界面 | ✅✅ 完全成功 |
| 出现弹窗（任意） | 链路往前走了，但撞到了下一个错误 —— **这是进展**，把弹窗文字截下来 |
| 还是"按钮消失 + 不动" | `IsFinished` 强制没生效（`F 0`），或卡死在更后面 |

服务端侧的独立判据：nginx access log 里 `gsqc-api` 是否出现**第二条**业务请求
（`report/DEADENDS.md` D-45 的三路交叉法：conntrack fresh sport + 文件 mtime + logcat）。

---

## 6. 回滚

三条，任选其一，都是干净的：

```sh
# A. 最轻：只卸 mount（不用重启，立刻生效）
su -c "umount \$(ls /data/app/*/*BlueArchive*/lib/arm64/libil2cpp.so | head -1)"
su -c "am force-stop com.RoamingStar.BlueArchive"

# B. 禁用模块 + 重启（KernelSU 管理器的开关，或命令行）
su -c "touch /data/adb/modules/ba_login_hook/disable"
su -c reboot

# C. 完全删除
su -c "rm -rf /data/adb/modules/ba_login_hook"
su -c reboot
```

> **原厂 `libil2cpp.so` 从头到尾一个字节都没被改过**（我们只用 bind-mount 覆盖了它的视图）。
> 所以"回滚"就是卸掉 mount，没有"还原文件"这一步，也不会因为回滚不当而损坏 App。

卸载后记得清日志：
```sh
su -c "rm -f /data/local/tmp/ba_hook.log"
```

---

## 7. 排错

| 症状 | 最可能的原因 | 怎么办 |
|---|---|---|
| 连 `H 0` 都没有 | ① bind-mount 没生效 ② `extractNativeLibs=false` ③ App 根本没加载这个 lib | 按 §5.2 逐条查；尤其确认 `dd` 读到的前 4 字节是 `fd 7b be a9` |
| 有 `H 0` 无 `H 1` | `pthread_create` 拿不到（GOT 槽 `0xfbaff00` 变了） | 用 `readelf -r libil2cpp.so \| grep pthread_create` 复核 `r_offset`，改 `hook.c` 的 `GOT_PTHREAD_CREATE` |
| `N` 很小（< 1000） | 枚举发生在 il2cpp 初始化早期 | 把 `hook.c` 的 `DELAY_SECONDS` 从 20 改成 30，重编 |
| `K 0` | 5 个目标方法一个都没命中 | ① 方法名大小写：`il2cpp_class_get_method_from_name` **区分大小写**，别改 `get_IsFinished` 的写法 ② metadata 不可读（罕见） |
| `F 0` 但 `K > 0` | 命中的 `MethodInfo` 里找不到落在模块内的 qword（可能是 abstract 方法） | 看 `p` 那 4 行；若 4 个全不是 libil2cpp 地址，说明命中的是接口/抽象声明而非实现 |
| 加了 hook 之后 App **秒退**（`SIGBUS`） | ① 洞写的位置不对（改了不该改的字节）② `libil2cpp.so` 大小/版本不对 | 核对 sha256；用 `mk_hook.py` 的"改动区域 应为 2 处"断言复核 |
| 加了 hook 之后 App 卡在启动画面 | `DT_INIT` 尾调原厂初始化失败 | 确认 `ORIG_DT_INIT = 0x10496434` 与你的版本一致（不是就先修） |
| 一切正常但登录还是不动 | `IsFinished` 不是卡点（卡在更上游） | 转 `report/_frida/00_env_probe.js` 的 TLS 路线做观测 |

---

## 8. 备选载体（本模块不适用时）

| 载体 | 前提 | 评价 |
|---|---|---|
| **直接 `cp` 覆盖**（不用模块） | `extractNativeLibs=true` + root | `report/../PROBE_README.md` §3 就是这么做的。缺点：App 更新后失效、属性可能被改坏、要每次手动做。**但它是验证阶段最快的** |
| **Frida** | root + 能接受被 ACE 杀 | 见 `report/_frida/`。成功率低，但**不需要重启、不需要打包、改配置只需改 JS** |
| **Zygisk 模块** | KernelSU + ZygiskNext | 能做成 `JNI_OnLoad` 里 inline hook，但模块 so 会在 `maps` 里可见（ACE 的判据之一）；且 Zygisk ABI 需要官方 header。**只有在 `extractNativeLibs=false` 且 Frida 也不行时才考虑** |
| **LSPosed** | LSPosed | 本包 Java 层 hook 已废：App 自带 `de.robv.android.xposed.*` 替身类遮蔽（`report/DEADENDS.md` D-33）。**不能用于改游戏逻辑** |

---

## 9. 已知风险（诚实列出）

| # | 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|---|
| R1 | ACE 校验 libil2cpp 的**内存**（不是磁盘） | 低 | 进程被杀 | 既有结论是 libil2cpp 无哈希钉死；若被杀，日志会停在 `H` 之后，此时改走 Frida |
| R2 | hook 里的延迟撞上 ACE 主检测窗口（启动后 8~10 s） | 中 | 线程还没跑就被杀 | 把 `DELAY_SECONDS` 调到 20 已避开；若仍被杀，说明 ACE 是**持续**轮询而不是启动期一次性扫描 |
| R3 | `extractNativeLibs=false` | 中 | 整个方案不适用 | §2 已给判据，先查再动手 |
| R4 | 客户端更新后偏移全变 | 高（长期） | hook 打印 `V 5` 后主动放弃（**不会崩**） | 重跑 `gen_offsets.py` + `mk_hook.py` |
| R5 | `MethodInfo` 所在的页被 mprotect 成 RW 时被 ACE 察觉 | 低 | 未知 | 我们只短暂 RW→RX，且只动一页 |
| R6 | `OnLoginFinish` 内部假设协程已填好字段 ⇒ NRE ⇒ 进程退出 | 中（本模块默认**不开**这个） | 崩溃 | `hook.c` 只强制 `get_IsFinished`，不碰 `OnLoginFinish`。要开的话另编一版 |

---

## 10. 文件清单

| 文件 | 作用 |
|---|---|
| `module.prop` | 模块描述 |
| `customize.sh` | 安装时执行（权限、指纹提示） |
| `post-fs-data.sh` | **核心**：bind-mount 补丁后的 so（zygote 之前，全局生效） |
| `uninstall.sh` | 卸载时 umount |
| `libil2cpp.so` | 补丁后的二进制（由 `cave/mk_hook.py` 产出，需手动放入） |
| `hook_apply.log` | post-fs-data 的日志（运行后生成） |
| `orig_sha256.txt` | 原厂文件指纹（运行后生成） |
| `../cave/hook.c` | hook 源码（freestanding aarch64 C） |
| `../cave/mk_hook.py` | 构建 + 打补丁 |
| `../cave/il2cpp_offsets.h` | 偏移表（由 `gen_offsets.py` 生成） |
