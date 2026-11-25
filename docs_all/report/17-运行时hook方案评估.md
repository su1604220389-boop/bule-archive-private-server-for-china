# 17 · 运行时 hook 方案评估（目标：让 `CertificateHandler.ValidateCertificate` 返回 true）

> 对象：国服 `com.RoamingStar.BlueArchive`，Unity 2021.3.56f2 + il2cpp，KernelSU root，Android 17 / sdk 37
> 本文所有地址来自**实测**：`work\ba\bapatch\libil2cpp.bin`（270,927,056 B，本机现役那份）
> 工具与解出的表：`report\_tmp\hookeval\`（`recover_final.py`、`il2cpp_syms.json`）
> 结论标注：**实测** = 我在本机二进制上跑出来的；**推断** = 逻辑外推；**既有** = 引团队已归档结论

---

## 0. 结论（8 行）

1. **A（Frida + frida-il2cpp-bridge）不可行，而且不是被 ACE 挡住的**——`frida-il2cpp-bridge` 自己也是靠 `Module.getExportByName("libil2cpp.so", "il2cpp_*")` 拿 API 的，而这批导出名**已被抹掉**（实测）。ACE 只是第二重死因。
2. **B 有戏，但原样照抄必死**：AzusaBA 的 `getaddr()` 走 `xdl_sym`，在本 so 上会**全返回 NULL**（源码证据见 §2）。它那 26 个 hook 在国服跑不起来。
3. **但我把补偿方案做出来了**：从 `.gnu.hash` + `.dynstr` 反推出被抹名的导出，**恢复 1201 个符号，其中 124 个 `il2cpp_*` 带确切地址**（实测，0 歧义）。
4. 这些 `il2cpp_*` 在 `.text` 尾部是一张 **4 字节 `b <real>` 跳转桩表**（`st_size=4`，已逐字节验证），**可以直接当函数调用**。
5. 关键 API 齐全到足以**完全不碰 metadata**：`il2cpp_class_for_each`（遍历所有类）+ `il2cpp_class_get_methods` + `il2cpp_method_get_name` → 按方法名找到 `ValidateCertificate`，再 `Dobby`/原地跳转 hook 它的 `methodPointer`。
6. **推荐 B2**：沿用你们已验证「不触发 ACE」的 **libil2cpp 代码洞 + `DT_INIT`** 载体，运行时解析 + 运行时打 4 字节跳转，**不新增 .so、不改 APK 签名、不动 libunity**。
7. 预估成功率：**B2 ≈ 60~70%**（卡点在 §5-Step0 的 5 分钟判读：如果拒证发生在托管层之前，hook 托管方法就是空转）。
8. 预估工作量：**0.5 人日**（符号表已解好，代码洞框架已有），失败可完整回滚。

---

## 1. 先把三个前提钉死（都是我在你那份 `libil2cpp.bin` 上实测的）

### 1.1 `il2cpp_*` 导出确实是 0 —— 但你测到的是「结果」，不是「原因」

| 指标 | 实测值 | 位置/方法 |
|---|---|---|
| `.dynsym` 条目数 | 2660 | `elfsym.py` |
| 其中 `.gnu.hash` 覆盖（= 导出） | **2352** | `recover_final.py` |
| `st_name` 可用（能 dlsym 到）的 | **306**（绝大多数是导入；少数是 STL/il2cpp 内部的**定义**符号，如 `_ZNSt6__ndk1…`） | 同上 |
| `il2cpp_*` 可被 `dlsym` 找到 | **0** ✅ 你的结论对 | 同上 |

**原因**：导出符号的 `st_name`（名字在 `.dynstr` 里的偏移）被清零/写成越界值，`st_value` 的存储字节序也被改过。
`.dynstr`（110,505 B）和 `.gnu.hash`（0x3E00 B）**都是完整的** —— 所以 dlsym 死光，但信息还在。

> 这和 `00-下一步总方案.md` §2.5「ACE 把 libil2cpp 的导入函数换成了自己的转发表」是同一类手法的另一面：**导入**用转发表、**导出**抹名字。

### 1.2 我把名字捞回来了：1201 个，其中 124 个 `il2cpp_*`

做法（可复现，脚本见附录 A）：
1. 遍历 `.gnu.hash` 的 bucket→chain，取出每个符号索引的 GNU hash（`chain & ~1`）；
2. 枚举 `.dynstr` 里所有字符串，算 GNU hash，做 hash → 名字的反查；
3. `st_value` 用 **`int.from_bytes(8B, 'big') >> 8`** 解码（这个布局是变异过的，标准解析器会得到一堆 `0x8024…` 垃圾）；
4. 校验：解出来的 1721 个 `FUNC` 符号 **1721/1721 全部落在 `.text`（0x59b8000 + 0xb09260）内**，才能信。

**关键 API 地址表（模块内偏移；运行时地址 = 模块基址 + 该值）**：

| 名称 | vaddr | 形态 |
|---|---|---|
| `il2cpp_class_for_each` | `0x063c3b50` | 4 B `b 0x6391eb0` |
| `il2cpp_class_get_methods` | `0x063c2ea8` | 4 B 跳转桩 |
| `il2cpp_class_get_method_from_name` | `0x063c2eac` | 4 B 跳转桩（→ `0x640b1e8`） |
| `il2cpp_method_get_name` | `0x063c37bc` | 4 B 跳转桩 |
| `il2cpp_method_get_param_count` | `0x063c37cc` | 4 B 跳转桩 |
| `il2cpp_method_get_return_type` | `0x063c37b0` | 4 B 跳转桩 |
| `il2cpp_class_get_parent` | `0x063c2eb8` | 4 B 跳转桩 |
| `il2cpp_class_is_subclass_of` | `0x063c2e70` | 8 B |
| `il2cpp_domain_get_assemblies` | `0x063c348c` | **真实函数**（40 B） |
| `il2cpp_domain_assembly_open` | `0x063c3484` | 8 B |
| `il2cpp_image_get_name` | `0x063c3ab4` | 4 B 跳转桩 |
| `il2cpp_get_corlib` | `0x063c2e14` | 4 B 跳转桩 |
| `il2cpp_thread_attach` | `0x063c38d4` | 4 B 跳转桩 |
| `il2cpp_gc_foreach_heap` | `0x063c36ac` | **真实函数**（40 B） |
| `il2cpp_object_get_virtual_method` | `0x063c3850` | 4 B 跳转桩 |
| `il2cpp_object_new` / `il2cpp_string_new` | `0x063c3854` / `0x063c38b8` | 32 B / 4 B |
| `il2cpp_type_get_type` / `il2cpp_type_get_class_or_element_class` | `0x063c3930` / `0x063c3934` | 4 B |
| `il2cpp_class_get_interfaces` / `il2cpp_class_is_abstract` | `0x063c2e98` / `0x063c2ed8` | 4 B |

**按名字没恢复出来的**（`.dynstr` 里有名字、但 hash 链被改坏，无法定位）：`il2cpp_domain_get`、`il2cpp_class_from_name`、`il2cpp_assembly_get_image`、`il2cpp_image_get_class`、`il2cpp_class_get_name`、`il2cpp_class_get_namespace`、`il2cpp_object_get_class`、`il2cpp_runtime_invoke`、`il2cpp_gchandle_new`。
→ **不需要它们**：§5-Step4 给的链路只用上表里有的 API（这是我们能绕开 metadata 的全部原因）。

### 1.3 这些跳转桩可以当普通函数用

```
0x063c2e14: 97 2c ff 17   →  b 0x638e080     (il2cpp_get_corlib 的真身)
0x063c2ea8: 77 20 01 14   →  b 0x640b0c4     (il2cpp_class_get_methods 的真身)
0x063c2eac: cf 20 01 14   →  b 0x640b1e8     (il2cpp_class_get_method_from_name 的真身)
0x063c3b50: d8 38 ff 17   →  b 0x6391eb0     (il2cpp_class_for_each 的真身)
```
（注意：相邻的两条桩**不一定**指向同一实现，同一实现也可能被多条桩引用——所以自校验要校验「桩跳到的地址」，不要只校验「桩本身在不在」。）
`b` 是**尾跳**，寄存器/栈完全不变 → **等价于直接调用真函数**。

> 反过来这也解释了「为什么 `.dynsym` 里名字全没了，游戏还能跑」：进程内模块之间的调用走 `.rela.plt`/重定位，**按索引**，不需要名字。

---

## 2. Q3 的确定答案：AzusaBA 的 `getaddr()` 在国服必然全失败

源码链路（`report\_tmp\azusa\src_utf8\app\src\main\jni\`）：

```
il2cpp-api-functions.cpp:18-25   #define DO_API(r,n,p) { n = (r(*) p) xdl_sym(handle, #n, nullptr); if(!n) LOGW("api not found %s", #n); }
il2cpp-api-functions.cpp:273-278 il2cpp_api_init(): handle = xdl_open("libil2cpp.so", 0); 然后 200+ 个 DO_API(...)
il2cpp-api-functions.cpp:874-878 getaddr(): if (!il2cpp_domain_get || !il2cpp_thread_attach || ...) { LOGE(...); return nullptr; }
main.cpp:1539-1546               init_my_hook(): while (il2cpp_domain_get != nullptr) break; 等 getaddr 探测 → 120×500ms = 60s 后 LOGE + return
```

推演（**确定，不是猜测**）：
1. `xdl_sym` 依赖 `.dynsym` 的 `st_name`（xdl 自己实现 GNU/SysV hash 查找，最终都要读 `st_name` 比字符串）→ 本 so 全部为空 → 返回 NULL；
2. `il2cpp_domain_get` 为 NULL → `il2cpp_api_init()` 打 200 多条 `api not found`，但**不中断**；
3. `getaddr()` 在 875 行判空 → 直接 `return nullptr`；
4. `init_my_hook()` 在 1540 行等的就是 `il2cpp_domain_get != nullptr`（或探针 `getaddr` 成功），**永远等不到** → 60 秒后 `return`；
5. 结果：`okHooks = 0 / 26`，UI 仍然挂得起来（ImGui 那条链不走 il2cpp），但**一个功能都没有**。

**所以**：
- 「AzusaBA 在国服 3.0.2 上跑通 26 个 hook」这个说法，**至少在国服上不可能成立**。它的 `AZUSA_GAME_VERSION "3.0.2"` 是作者自述，`main.cpp:160-161`。
- 最可能的真相：作者在国际服（导出完整）验证了功能，国服只做了「不崩」级别的适配（包名/路径/日志，见 `main.cpp:53-57`、`1705-1727`）。
- **对 B 的结论**：**原样照搬 = 100% 失败**。但只要把「符号解析层」从 `xdl_sym` 换成 §1.2 的地址表，B 立刻成立。

---

## 3. 方案对比表

| # | 方案 | 成功率 | 工作量 | 被 ACE 杀的风险 | 硬依赖 |
|---|---|---|---|---|---|
| **A1** | Frida + `frida-il2cpp-bridge` | **< 10%** | 0.1 人日 | **极高**（必中项 4 条：frida-agent 映射 / `gum-js-loop` 线程名 / 27042 / TracerPid） | ①Frida 能活 ②**库能拿到 `il2cpp_*` 导出**（实测：拿不到） |
| **A2** | Frida + 手写 Interceptor（自备偏移） | **20~30%** | 0.3 人日 | 极高（同上） | Frida 能活 ≥ 一次握手的时长 |
| **B1** | LSPosed 模块 + `xdl` + Dobby（AzusaBA 原样） | **~0%** | 1 人日 | 低 | ❌ 符号解析全 NULL（§2） |
| **B2** ⭐ | **libil2cpp 代码洞 + `DT_INIT` 载体 + 地址表 + 原地 4 B 跳转** | **60~70%** | **0.5 人日** | **低**（libil2cpp 无 hash pin，既有结论） | 无（不需要 Frida / 不需要 LSPosed / 不改 APK 签名） |
| **B3** | LSPosed 模块 + 地址表 + Dobby | 50~60% | 1.5 人日 | 中（模块 so 在 maps 明文可见） | LSPosed 可用、国服 Java hook 已废（只当跳板） |
| **C1** | 修正版内存明文扫描（只做验证） | — | 0.1 人日 | 无 | 无 |
| **C2** | 原生 TLS 校验点（libunity 内 `SSL_*`/`mbedtls_*`） | 40% | 1 人日 | **高**（`01 §4.1` F7：libunity 4 B 补丁 → ACE `SIGBUS status=7`） | 需要先证明 ACE 不读内存页 |
| **C3** | 系统/用户 CA、`networkSecurityConfig` | **已证伪** | — | 无 | Unity 用自己的信任库（`13:C14`、`06:267-274`） |

> **推荐 B2**。理由不是「它最强」，而是「它是唯一一条**同时**满足：不改 APK、不引入被 ACE 盯上的模块、不依赖任何被抹掉的导出、并且载体你们已经验证过不触发 ACE」的路。

---

## 4. Q2：Frida 在 ACE 下的存活率（诚实答案：没有可靠做法）

### 4.1 已知检测面（`work\ba\audit\anticheat-full.md`、`01-现状与已试方向.md`）

| 检测项 | 依据 | 对 Frida 是否命中 |
|---|---|---|
| `TracerPid`（`/proc/self/status`） | Turing `Virgo.java:57`；中国移动 `gatewayauth/utils/a.java:19`（`line.startsWith("TracerPid")`） | **必中**——Frida 的 attach 就是 ptrace |
| `/proc/self/maps` 里的注入痕迹 | 数美 `l1111l111111Il.java:528` 读 maps 并只保留 `/data/app/` 行 | **必中**（frida-agent 落在匿名可执行段或 `/data/local/tmp`） |
| 线程名 `gum-js-loop` / `pool-frida` | `anti-detection.md §3` | **必中**（除非改 gum 源码重编） |
| 端口 27042 | 同上 | 只在 frida-server 场景命中；gadget 可避 |
| `dladdr`/模块枚举 | `libtprt.so` 导入 `dlopen/dlclose/dlsym/dladdr`（`anticheat-full.md:77`） | 中（能反查到 agent 属于哪个模块） |

dex 里 `frida`/`27042`/`ptrace` **明文命中 0**（`01:241`）——说明它们**不靠字符串匹配**，靠行为/结构检测。这对 Frida 是最坏情况。

### 4.2 本机的实测后果

- 现象：`exit-info reason=2 status=7` = **SIGBUS**，ACE 主动杀（`00-下一步总方案.md`、`13-总账`）。
- 团队已有 `run_frida.py` / `run_spawn.py` / `hook_pfn.js`（hook 53 个 libtprt 函数）——说明**确实 attach 成功过**，但仓库里**没有任何一份日志证明进程在 ACE 全功能开启下活过 30 秒**。
- 我的判断：**能活到「脚本加载完 + 抓几帧」，但活不到一次完整的 UnityWebRequest 握手**（游戏启动后 8~10 s 才进 ACE 主检测窗口，而 TLS 握手发生在 gate 连上之后）。所以「用 Frida 抓到 ValidateCertificate 被调用」这条路，理论可行、实测概率低。

### 4.3 那些「加固做法」的真实效果

| 做法 | 效果 | 备注 |
|---|---|---|
| frida-server 改名 | **无效** | 检测不看文件名，看 maps 段属性 + TracerPid |
| 换端口（非 27042） | **有效（只挡一条）** | 但 gadget 模式本来就不监听 |
| `spawn -f --no-pause` | **部分有效** | 越早注入越容易在 ACE 初始化前埋好；代价是 ACE 初始化时的检测更狠 |
| gadget 注入到别的进程再 ptrace 游戏 | **反向恶化** | 目标进程 `TracerPid` 直接指向你的进程 → 必中 |
| `/proc/maps` 隐藏（`Anti/MemoryHide.h` 那套） | **作者实测崩** | `main.cpp:1526-1528`：多线程 mremap 替换执行页 → SIGSEGV |
| 自编 gum（改线程名 + 自定义 allocator 段名） | 未验证 | 工程量大，且 `ptrace` 那条仍然中 |

**结论：Frida 只能当「一次性侦察工具」用**（例如验证 `CertificateHandler` 到底有没有被调用），**不能当交付载体**。

### 4.4 一条仍然值得做的 5 分钟 Frida 侦察（可选）

目的不是 hook，是**取证**：确认 native 层是否真的把证书交给了托管层。

```bash
# 手机侧（已有 frida-server 的前提下）
adb forward tcp:27042 tcp:27042
# PC 侧（一次性，30 秒内结束战斗）
frida -H 127.0.0.1:27042 -f com.RoamingStar.BlueArchive --no-pause \
      -l report\_tmp\hookeval\probe_cert.js
```

`probe_cert.js` 只做三件事：`Interceptor.attach` 到 `libil2cpp` 的 `il2cpp_class_get_method_from_name`（地址 `base+0x063c2eac`）打日志；把 `il2cpp_method_get_name`（`base+0x063c37bc`）的返回值打印出来；统计有没有出现过 `ValidateCertificate` 这个名字被查询。**不 hook 不写内存**，把痕迹压到最低。

---

## 5. 推荐方案 B2 的落地步骤（命令级）

> 前提：**载体沿用你们已有的「libil2cpp 代码洞 + `DT_INIT`」工作流**（`work\ba\bapatch\cave\*.S` + `patch_*.py`，`00-下一步总方案.md` 已记「已证不触发 ACE」）。
> 下面每一步都可以单独回滚，回滚 = 把原版 `libil2cpp.so` 塞回去（`libil2cpp.bin` 就是原版备份）。

### Step 0（5 分钟，必须先做）：判定「拒证到底发生在哪一层」

这一步不做，后面全可能白干——**`CertificateHandler` 只可能被调用在「TLS 握手成功之后」或「native 校验回调里」；如果客户端在握手阶段就 abort，托管方法根本不会进**。

```powershell
# PC 侧，用我们给 gsqc-api 签的那张证书起一个会打印 alert 的服务端
openssl s_server -accept 443 -cert .\fullchain.pem -key .\k.pem -www -state -msg -tlsextdebug
```

| `s_server` 打印 | 含义 | 走哪条 |
|---|---|---|
| `sslv3 alert unknown ca` | 客户端不认我们的 CA（自带信任库 / pinning） | **继续 Step 1~5**（hook 托管层可能无效 → 先看 Step 1 结果） |
| `sslv3 alert certificate unknown` / `access denied` | 通用拒绝，可能是托管回调返回 false | **Step 1~5，成功率最高** |
| `sslv3 alert bad certificate` | 证书本身不合规（链不全 / SAN 错 / 时间） | **先修证书**，不要 hook |
| 客户端没连过来 | DNAT 没生效 | 先修重定向 |

同时抓一次 logcat 看有没有 C# 栈：
```bash
adb logcat -c; adb logcat | findstr /i "Exception CertificateHandler UnityWebRequest SSL ssl"
```

### Step 1（10 分钟，第二次判定）：metadata 到底有没有明文（**修正你们上次的扫描**）

你们上次扫的是 `CustomCertificateHandler`。**这个探针本身有风险**：Unity 里没有这个公开类，真实类型名是 `UnityEngine.Networking.CertificateHandler`，具体子类在游戏自己的程序集里、名字未知。我在本机 `libil2cpp.bin` 上实测（`report\_tmp\hookeval\cnt.py`）：

| 字符串 | 在 `libil2cpp.bin` 里的次数 |
|---|---|
| `CustomCertificateHandler` | **0** |
| `CertificateHandler` | **3** |
| `UnityEngine.Networking` | **45** |
| `CertificateHandler::`（`类型::方法` 形态） | 2 |
| `ValidateCertificate` | **0** |

两个结论：
- `ValidateCertificate` = 0 是**正常的**（方法名在 metadata 里，不在 .so 里；而 `.rodata` 里那 2 处 `CertificateHandler::` 是 il2cpp 运行时错误消息用的签名串，恰好没有 `ValidateCertificate`）。**所以「.so 里搜不到」不能用来判断方法不存在。**
- 用 `CustomCertificateHandler` 当**内存**探针同样危险：如果游戏里那个子类叫别的名字（如 `BiliCertHandler`），你扫什么都 0 命中，而这不是「metadata 没明文」的证据。

**修正后的探针（只读）**：先扫 **短串**，再扫 metadata magic。

```sh
pid=$(pidof com.RoamingStar.BlueArchive); echo "pid=$pid"
# 1) 先扫短串，别扫长串
busybox grep -abo 'CertificateHandler' /proc/$pid/mem 2>/dev/null | head
# 2) 更靠谱：扫 metadata 的 magic（明文 / 密文两种都认）
busybox awk 'function h2d(h, i,c,v){v=0;for(i=1;i<=length(h);i++){c=tolower(substr(h,i,1));v=v*16+index("0123456789abcdef",c)-1}return v}
{split($1,a,"-");s=h2d(a[1]);e=h2d(a[2]);n=e-s; if(n>1000000) printf "%.0f %.0f %s\n", s, n, $2}' /proc/$pid/maps |
while read s n perm; do
  h=$(busybox dd if=/proc/$pid/mem bs=1 skip=$s count=64 2>/dev/null | busybox od -An -tx1 | tr -d ' \n')
  case "$h" in *af1bb1fa*) echo "HIT-PLAINTEXT start=$s size=$n $perm";; *94437212*) echo "HIT-CIPHER  start=$s size=$n $perm";; esac
done
```

**更决定性的一招（不用扫内存）**：既然 il2cpp 自己显然能按名字查方法（游戏在跑），那 metadata 一定可读——**只是不一定在同一个大块里**。所以：

> **判定标准：如果 Step 5 的 `il2cpp_method_get_name` 能打印出正常字符串，就说明 metadata 可用；否则它返回乱码。**

### Step 2（1 分钟）：拿符号表

```powershell
cd C:\Users\su\Desktop\大肥鱼项目\BAServer\report\_tmp\hookeval
python recover_final.py C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\bapatch\libil2cpp.bin il2cpp_syms.json
# 输出：total named exports recovered: 1201 / il2cpp_* recovered: 124
# il2cpp_syms.json 里是 {名字: {addr, size, shndx, bind, type}}
```

**客户端每次更新都要重跑这条**（地址会变，但脚本不变）。生成后把需要的那十几个 `(名字, addr)` 直接写成 C 常量表。

### Step 3（在代码洞里）：运行时自校验，避免版本漂移静默失效

```c
// 每个固定偏移都做一次「形态校验」，对不上就整体放弃（绝不硬跑）
static bool verify_thunk(uintptr_t base, uint32_t off, uintptr_t expect_target) {
    uint32_t w = *(volatile uint32_t*)(base + off);
    if ((w >> 26) != 0x05) return false;            // 必须是 B
    int32_t imm = (int32_t)(w & 0x03FFFFFF);
    if (imm & 0x02000000) imm |= 0xF0000000;        // 符号扩展
    return (uintptr_t)(base + off + (int64_t)imm * 4) == base + expect_target;
}
// 例：il2cpp_class_get_method_from_name 必须在 base+0x063c2eac，且 b 到 base+0x640b1e8
```

### Step 4（核心）：**不碰 metadata**，按方法名找到 `ValidateCertificate`

只用 §1.2 里**已确认**的 4 个 API：`il2cpp_class_for_each`、`il2cpp_class_get_methods`、`il2cpp_method_get_name`、`il2cpp_method_get_param_count`。

```c
typedef void (*ForEachFn)(void* klass, void* user);
typedef const void* (*GetMethods)(void* klass, void** iter);
typedef const char* (*GetName)(const void* m);
typedef int (*GetParamCount)(const void* m);

struct Hit { void* klass; const void* method; };

static void on_class(void* klass, void* user) {
    struct Hit* out = (struct Hit*)user;
    void* it = NULL;
    const void* m;
    while ((m = GET_METHODS(klass, &it)) != NULL) {
        const char* n = GET_NAME(m);
        if (n && strcmp(n, "ValidateCertificate") == 0) {
            // 只认 bool ValidateCertificate(byte[])：1 个参数
            if (GET_PARAM_COUNT(m) == 1) { out->klass = klass; out->method = m; return; }
        }
    }
}

// 调用：只遍历一次，全量扫所有类（数万级，毫秒量级）
struct Hit hit = {0};
CLASS_FOR_EACH(on_class, &hit);
```

**为什么这能行、而 `il2cpp_class_from_name` 不行**：`class_for_each` 把 `Il2CppClass*` 直接喂给我们，不需要我们先知道 image/assembly；方法名由 il2cpp 自己去 metadata 里读（它能读，我们不用能读）。

**结果处理**：
- 命中 **0 个** → 该类在本版本里没被编译进来 / Step 0 判定错了 → 停，别改内存；
- 命中 **1 个** → 直接用；
- 命中 **>1 个**（iFix 代理、CriWare、游戏自绘 handler 都可能重名）→ 全部记下来，**每个 `methodPointer` 都 hook**（返回 true 对所有重载都是无害的）；
- 若存在 `<>iFixBaseProxy_ValidateCertificate`（热更框架的代理），它也会以「方法名 = `ValidateCertificate`」或「名字里含 `iFixBaseProxy`」的形式出现在枚举里 → 用 `strstr(n, "iFixBaseProxy")` 额外收一遍。

**兜底链（当 `class_for_each` 也排不出方法名 = metadata 真的不可读）**：
```
il2cpp_get_corlib()            → Il2CppImage*
il2cpp_domain_assembly_open()  → UnityEngine.UnityWebRequestModule.dll 的 Il2CppAssembly*
读 assembly->image（Il2CppAssembly 首字段）
il2cpp_image_get_name() 校验名字
→ 之后必须 struct-walk Il2CppImage 取 types[]（版本敏感，只当最后手段）
```

### Step 5（打补丁）：`MethodInfo->methodPointer` 改 4 字节跳转

```c
// IL2CPP 2021 的 MethodInfo 首字段就是 methodPointer
void* target = *(void**)((uintptr_t)hit.method + 0);   // → 真函数入口

// 1) 在代码洞（我们自己的可执行页 / libil2cpp 已 patch 的 cave）里放返回值桩
//    mov w0, #1 ; ret   →  20 00 80 52 C0 03 5F D6
// 2) 把目标入口改成 4 字节 b <stub>
uint32_t branch = 0x14000000u | (uint32_t)(((int64_t)((uintptr_t)stub - (uintptr_t)target)) >> 2 & 0x03FFFFFF);
mprotect(target_page, 4096, PROT_READ|PROT_WRITE|PROT_EXEC);
*(uint32_t*)target = branch;
__builtin___clear_cache((char*)target, (char*)target + 4);
mprotect(target_page, 4096, PROT_READ|PROT_EXEC);
```

要点：
- **不要用 Dobby**（要额外静态库/重定位）。这个方法我们要的是「整体替换」不是「包装」，**一条 `mov w0,#1; ret` 就够**，不需要 trampoline、不需要保存寄存器。
- 目标代码在 **libil2cpp** 里 → 落在「无 hash pin」的安全区（既有结论）；**不要**动 `libunity`（F7 前科：`SIGBUS status=7`）。
- `mprotect` 用你们 `Tools/Syscalls.h` 那套直接 `svc 0` 的封装，别走 libc（ACE 包了 libc）。

### Step 6（验证）

```bash
# 1) 客户端侧：确认没有 0.3 s 自杀循环、没有 SIGBUS
adb logcat -c; adb shell am start -n com.RoamingStar.BlueArchive/.MainActivity
adb logcat | findstr /i "tombstone SIGBUS FATAL azusa"
# 2) 服务端侧：看 access log 是否出现了「握手成功 + 业务 POST」
tail -f /var/log/nginx/access.log | findstr gsqc-api
# 3) 最硬证据：s_server 那边不再打印 alert，而是走到 HTTP
```

### Step 7（回滚）

```powershell
# 一条命令回到原厂
Copy-Item work\ba\bapatch\libil2cpp.bin <APK解包目录>\lib\arm64-v8a\libil2cpp.so -Force
# 重新对齐/签名后装回；或直接用你们已有的原版备份镜像
```
> 提醒（既有坑，`ba-pitfalls.md:138`）：签名前确认 ≥2.1 GB 空闲，否则 `apksigner` 会半截输出。

---

## 6. Q4：另外三条路的评估

### 6.1 特征码找 `il2cpp_class_from_name`（**已不需要，但留作兜底**）

- 可行性：高。`il2cpp_class_from_name` 的真身在 `.text` 里，形态稳定（遍历 image 的 type 表 + `strcmp(namespace/name)`）。
- 但**我们现在有更好的**：`class_for_each` + `get_methods` + `method_get_name` 完全绕开它。
- 只在一种情况下需要它：`il2cpp_method_get_name` 返回乱码（metadata 不可读）。

### 6.2 用 `libtprt.so` 的 `g_tprt_pfn_array` / `g_tprt_ori_array`（**实测确认导出，但对 il2cpp 无帮助**）

实测（`report\_tmp\hookeval\tprt_exports.py`）：

| 符号 | vaddr | size | 项数 | 含义 |
|---|---|---|---|---|
| `g_tprt_pfn_array` | `0x1a3210` | 424 | **53 个指针** | ACE 的 **wrapper 表**（它自己的函数） |
| `g_tprt_ori_array` | `0x1a4b48` | 160 | **20 个指针** | 对应的 **原始 libc 函数** |
| `JNI_OnLoad` | `0x2641c` | 1476 | — | ACE 入口 |
| `tp_syscall_imp` | `0x146be0` | 48 | — | ACE 的 syscall 实现 |

**能干什么**：`g_tprt_ori_array[i]` 是**未经 ACE 插桩的原始 libc 函数**。我们将来做 `connect` 改写时：
- 我们的 hook 里要调真 `connect` → **用 `ori[i]`，不要 `dlsym(RTLD_NEXT)`**（后者可能拿到 ACE 的 wrapper，造成递归/被记录）；
- 但**这跟 il2cpp 一点关系都没有**——它解决不了符号表问题。
- 副作用警告：53/20 这两个数字不对称，说明 pfn 表里有 33 个不是 libc 包装（可能是 ACE 内部函数）→ **必须先在真机上 dump 一遍再逐个配对**（你们已有 `dump_tprt.js`，直接跑）。

### 6.3 iFix 代理 `<>iFixBaseProxy_ValidateCertificate`

- 我在 `libil2cpp.so` 里搜 `iFix` / `iFixBaseProxy` = **0 命中**（方法名本来就在 metadata，不在 .so，所以这个结果**不能证明它不存在**）。
- 但 Step 4 的枚举法**天然覆盖它**：代理方法如果存在，就会以「方法名含 `ValidateCertificate`」或「类名含 `iFixBaseProxy`」出现在 `class_for_each` 的遍历里。
- **必须做的一件事**：枚举结果**全部打印出来（类指针 + 方法指针 + 名字）**，再决定 hook 哪几个。不要只 hook 第一个命中的——iFix 的代理就是为「让 hook 失效」而生的。

---

## 7. 风险清单

| # | 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|---|
| R1 | 拒证发生在**托管层之前**（native TLS 回调直接 abort） | 中 | **hook 完全空转** | Step 0 的 `s_server` 判读 + logcat C# 栈 |
| R2 | 方法名枚举为空（metadata 不可读） | 低 | 方案退化到 struct-walk | Step 5 兜底链；或改用 `il2cpp_image_get_name` 定位 |
| R3 | 目标是 **abstract 方法**，`methodPointer` 为 NULL | 中 | 补丁打在空地址 | 枚举时过滤 `methodPointer != NULL`；抽象方法要取子类的 override（`class_for_each` 会同时给出子类） |
| R4 | 客户端更新 → 偏移全变 | 高（长期） | 静默失效 | Step 3 的形态自校验（必须实现，不要省） |
| R5 | 代码洞本身被 ACE 校验（libil2cpp 无 hash pin 是既有结论，但仍是黑盒） | 低 | SIGBUS | 用你们已验的 cave 流程；先只放「打日志」的最小代码验一轮 |
| R6 | 签名重打包被 ACE 的 `sourceDir` 完整性面抓到 | 中 | 启动即杀 | 既有对策：删 `assets/__tpinfo.*`（`ba-pitfalls.md:9-11`）；只做原地补丁 |
| R7 | 补丁把 `mprotect` 页恢复错（原本是 `r-x` 但有相邻页） | 低 | 游戏随机崩 | 按页边界算；记录原始 prot 再还原 |

---

## 8. 工作量（按「能跑起来」计）

| 阶段 | 内容 | 人日 |
|---|---|---|
| P0 | Step 0 判读（alert + logcat） | 0.05 |
| P1 | Step 2 跑符号表 + 生成常量头 | 0.05（脚本已给） |
| P2 | 代码洞骨架（复用 `cave/*.S`）+ Step 3 自校验 | 0.1 |
| P3 | Step 4 枚举 + 日志（**先只看不写**） | 0.1 |
| P4 | Step 5 打补丁 + 实机验证 | 0.1 |
| P5 | 失败分支（R1/R3）补偿 | 0.1~0.3 |
| **合计** | | **0.5 人日**（顺利）～ **0.8**（含补偿） |

---

## 附录 A：工具与产物

| 文件 | 用途 |
|---|---|
| `report\_tmp\hookeval\elfsym.py` | ELF64 动态符号表探针（判断某个 .so 到底导不导出什么） |
| `report\_tmp\hookeval\gnuhash_recover.py` | 第一版 GNU hash 反查（地址解码是错的，**仅作对照**） |
| `report\_tmp\hookeval\recover_final.py` | **正式版**：正确解码 `st_value`（`BE(8B)>>8`）+ 反查名字，输出 JSON |
| `report\_tmp\hookeval\il2cpp_syms.json` | 1201 个恢复符号（含 124 个 `il2cpp_*` 及地址/大小） |
| `report\_tmp\hookeval\tprt_exports.py` | `libtprt.so` 导出清单（两个数组 + `JNI_OnLoad`） |
| `report\_tmp\hookeval\loadchk.py` | PT_LOAD `vaddr==offset` 校验 + 跳转桩目标解码 |

## 附录 B：复用资产索引（来自 AzusaBA 5.2.5，见 05 号报告）

| 要什么 | 用哪份 |
|---|---|
| 绕 bionic 命名空间拿 .so 句柄 | `AzusaBA/app/src/main/jni/il2cppApi/xdl/`（8 文件） |
| 直接 `svc 0` 的 syscall 封装（绕 libc） | `jni/Tools/Syscalls.h:64-252` |
| `mprotect` + 写 + `clear_cache` 的现成函数 | `jni/Tools/PtrHook.cpp:10-40` |
| 指针槽改写（vtbl/GOT/函数指针数组） | `jni/Tools/PtrHook.cpp:51-66` |
| 崩溃二分（safe flag / hook 位掩码） | `jni/main.cpp:1705-1736` |
| 进程内日志落盘（三路径回落） | `java/HookLoad.java:163-198`、`jni/main.cpp:38-64` |

## 附录 C：一句话回答你的三个问题

1. **A 还是 B**：都不行——A 死在「库也要导出」+「Frida 必被 ACE 抓」，B 原样死在 `xdl_sym`。**能行的只有 B'（B 的载体 + 我解出来的地址表）**。
2. **Frida 存活率**：没有可靠做法；已知必中项 4 条，`ptrace`/`TracerPid` 那条绕不过。只能当一次性侦察。
3. **`getaddr()` 怎么拿 `MethodInfo*` 的**：它拿不到。源码就是 `xdl_sym`（`il2cpp-api-functions.cpp:18-25`），在本 so 上全 NULL。**它没在国服跑通过；而我们可以，因为符号是我们离线解出来的，不靠 dlsym。**

---

# §8 探针存档 + 完整版设计（2026-11-14 追加）

> 背景变更：lead 实测「客户端发 TLS 时**不带 SNI**」→ 命中 `0.default` 默认证书块，
> 我们准备的 `CN=*.bluearchive-cn.com` 一次都没被看到。证书问题可能因此在服务端一行 `default_server` 就消失。
> 本节**只做存档与设计**，不部署、不动 `libil2cpp`、不碰手机。

## 8.1 存档清单

| 项 | 值 |
|---|---|
| **`libil2cpp_probe.bin` sha256** | `16FD1EBA7E1F7E846E4BD292C3E88A0B3CF8BDD6D8AAB2D941424B24EF1DCE4A` |
| 尺寸 | 270,927,056 B（与原厂 `libil2cpp.bin` 完全一致） |
| 改动面 | 仅 2 处：`0xf2c2410–0xf2c25d3`（452 B 探针）+ `.dynamic` 里 `DT_INIT` 的低 4 字节 |
| 源 / 脚本 / 文档 | `work/ba/bapatch/probe.S`、`mkprobe.py`、`PROBE_README.md` |
| 构建链 | WSL `clang --target=aarch64-linux-android26` + `ld.lld -Ttext=0xf2c2410` + `llvm-objcopy` |
| 复现 | `python mkprobe.py`（脚本会断言洞区全 0 才写） |

## 8.2 四条硬情报（本轮实测，可直接引用）

1. **代码洞容量 = 3056 B（0xBF0）**，起点 `0xf2c2410`。
   依据：RX 段 `p_filesz` 的结束值**正好**是 `0xf2c2410`（`0x59b8000 + 0x990a410`），而加载器按**页**映射，
   最后一页到 `0xf2c3000`，所以 `[0xf2c2410, 0xf2c3000)` 都落在 RX 页内、可执行。
   （lead 记的「1112 B 已被 g20 旧桩占用」是另一个 build；原厂 `libil2cpp.bin` 这段**全零**，实测。）
2. **`il2cpp_class_for_each` 回调签名 = `void (*)(Il2CppClass* klass, void* userData)`，有二进制实证**：
   反汇编真身 `0x6391eb0` → `+0x10 MOV x19,x1`（存 userData）、`+0x14 MOV x20,x0`（存 callback）、
   `+0x40 MOV x0,x22`（klass）、`+0x58 MOV x1,x19`、`+0x5c BLR x20`。
3. **`pthread_create` 不在 1201 个「定义符号」里**，但在 **306 个保留名字的导入**里（`.dynsym` idx=183，`shndx=0`），
   对应 `.rela.plt` 的 GOT 槽 **`0x0fbaff00`**。
   同一张表还拿到：`open@0xfbafa58`、`write@0xfbaf968`、`close@0xfbafa70`、`nanosleep@0xfbaff48`、`usleep@0xfbaffe8`。
   用法：`ldr x9,=<got>; add x9,base,x9; ldr x9,[x9]; blr x9`。
4. **原厂 `DT_INIT` = `0x10496434`，是一个真实的 C++ 静态初始化函数，不是跳洞的桩**：
   开头是 `stp x29,x30,[sp,#-16]! / mov x29,sp / bl 0x10496094 / …`。
   把 `DT_INIT` 指向洞里的是 **g20 那个 build**（`libil2cpp_patched.bin`：`DT_INIT=0xf2c2410`，洞里是 `f3 53 b6 a9 …`）。
   ⇒ 从原厂构建时必须**自己改 `DT_INIT`**，并在洞尾 `br 0x10496434` 尾调原厂初始化（本探针即如此，顺带清掉了坏掉的 g20 旧桩）。

## 8.3 ★ 新发现：`.text` 有 26% 的页在磁盘上不是可执行代码

这条直接影响 Pass 2 的落地方式，必须先说。

**实测**（`report\_tmp\hookeval\encmap.py`，结果另存 `work/ba/bapatch/encrypted_pages.txt`）：

| 指标 | 值 |
|---|---|
| `.text` 页数（4 KB） | 2825 |
| 「0 个 `RET` + 可打印字符 <60% + 0 字节 <30%」的页 | **739 页 = 26.2%**，合计 2956 KB |
| 分布形态 | **周期性**：每 64 KB 里约 12 KB 是这种块（`0x59ba000-0x59bd000`、`0x59ca000-0x59cd000`、`0x59da000…`） |
| 具体样本 | 跳转桩 `0x63c2eac`（`il2cpp_class_get_method_from_name`）指向的 `0x640b1e8` 落在 `0x640a000-0x640e000` 块内，`llvm-objdump` 整段输出 `<unknown>` |
| 对照（均正常反汇编） | `0x6391eb0`（`class_for_each` 真身）、`0x63c2e14~0x63c3b5x`（整张跳转桩表）、`0xf2c2410`（我们的洞） |

**是什么**：字节分布极不均匀（某块内 `0xc9` 出现 1794 次、`0xca` 832 次），**不是**高熵密文，
也不是指针表（8 字节落在模块地址范围内的 = 0/2048）。
**最可能的解释（推断，未证）**：ACE 把**部分函数体**搬进编码块、加载时还原，同时保留明文的 `b <target>` 跳转桩。
这与「导出名被抹、`st_value` 改字节序、桩却完好」是同一套手法的三个面。

**三个影响：**

1. ✅ **不影响「按地址调用 API」**：游戏能跑 ⇒ 这些块运行时一定被还原；我们只要地址（来自 `.dynsym`，不受影响）。
2. ✅ **不影响探针**：探针在洞里（g20 build 已实证「洞里的代码能在真机执行」），只调 API，不解析这些块。
3. ⚠️ **直接影响 Pass 2**：原计划「拿到 `methodPointer` → 算文件偏移 → 离线改成 `mov w0,#1; ret`」。
   若目标函数体落在这类块里，**文件级补丁会被 ACE 的还原步骤改掉**，必须改成：
   - 先查 `encrypted_pages.txt` 判断 `methodPointer` 落在哪；
   - **明文页** → 文件级补丁可行（原方案）；
   - **编码块** → **改数据不改代码**：把 `MethodInfo::methodPointer` 指向洞里我们自己的桩（`MethodInfo` 在 data 段，不在这些块里）。

## 8.4 完整版设计（`probe2_full.S`，已写、已语法编译通过、**未构建上机包**）

**核心决策：不读类名，改用 API 直接问「这个类有没有 `ValidateCertificate` 方法」。**

```c
// 回调（每个类调一次）
void cb(Il2CppClass* klass, void* ctx) {
    ctx->scanned++;
    if (ctx->hits >= 8) return;
    MethodInfo* m = il2cpp_class_get_method_from_name(klass, "ValidateCertificate", 1);
    if (m) { ctx->klass[ctx->hits] = klass; ctx->method[ctx->hits] = m; ctx->hits++; }
}
```

为什么比「读 `klass->name` 再 strcmp」好：

| | 读类名 `klass+0x10` | 用 `get_method_from_name` |
|---|---|---|
| 依赖结构体偏移 | **是**（错一字节即 SIGSEGV） | 否 |
| 依赖类名猜测 | 是（`CustomCertificateHandler` 可能压根不是这个名字） | 否 |
| 覆盖 iFix 代理类 | 否 | **是**（谁有这个方法就抓谁） |
| 依赖 metadata 解密方式 | 是 | 否（解压在 il2cpp 内部完成） |

**代价**：每类做一次方法名线性扫描（约 3 万类 × 几十方法），毫秒~秒级，在独立线程里可接受；命中上限 8 个。

## 8.5 完整版的 log 格式（提前定好判读）

每行 = 1 个标签字符 + 空格 + **固定 16 位小写十六进制** + `\n`（共 18 字节，零歧义，`awk '{print $2}'` 直接取）。

```
START              # 6 字节，无空格，DT_INIT 里写（沿用 Pass 1 形态）
AZ2                # 版本魔数
B 0000000e00000000 # 模块基址
E                  # 开始枚举
X                  # 枚举正常返回
N 0000000000007a3c # 扫过的 Il2CppClass 个数
H 0000000000000002 # 命中数
K 0000000e4a1b2c30 # 命中类 Il2CppClass*
M 0000000e4a1b2d80 # 命中方法 MethodInfo*
Q 0000000e064b1e40 # MethodInfo+0x00  ← 这四个 Q 用来在线判 methodPointer 偏移
Q 0000000000000000 # MethodInfo+0x08
Q 0000000e4a1b2c30 # MethodInfo+0x10
Q 0000000e4a1b2e10 # MethodInfo+0x18
K …/M …/Q …        # 第二个命中（最多 8 组）
D                  # 完成
```

判读表：

| 现象 | 结论 | 动作 |
|---|---|---|
| 连 `AZ2` 都没有 | 洞没执行 / `DT_INIT` 没指对 | 查 patch 是否写进对的文件、`DT_INIT` 值 |
| 有 `AZ2`/`B`，无 `E` 之后 | 崩在 `class_for_each` | 复核桩地址；改调真身 `0x6391eb0` |
| 有 `X` 但 `N` 很小（<1000） | 枚举到的是初始化早期的类表 | 把 15 s 延迟加到 25~30 s |
| 有 `X`，`H 0` | **没有任何类有 `ValidateCertificate`** | 这条链路不走托管校验 → 转向 native TLS 层 |
| `H≥1` | 拿到目标 | 看 4 个 `Q`：落在 `libil2cpp` 地址范围（base ~ base+0x1024b4f8）的那个 = `methodPointer`；再查它在不在 `encrypted_pages.txt` 的区间 → 决定「文件补丁」还是「改数据」 |

**`Q` 四行的作用**：`MethodInfo` 在 2021.3 与 2022+ 之间有 `methodPointer` / `virtualMethodPointer` 谁在前的差异。
**我们不需要赌**——把前 4 个 qword 打出来，落在 `libil2cpp` 地址范围内的那个就是代码指针。零风险的在线判读法。

## 8.6 关于「`klass->name` 偏移从哪反推」的答复（风险条目）

**诚实的答案：目前无法给出可信的二进制实证，所以完整版不用它。**

- 常规布局是 `Il2CppClass { image@0x00; gc_desc@0x08; name@0x10; namespaze@0x18; byval_arg@0x20; … }`，
  `il2cpp_class_get_type()` 应等价于 `&klass->byval_arg`（即 `add x0,x0,#0x20; ret`）。
  理论上可反汇编它的真身取证，看到 `#0x20` 即反推出 `byval_arg@0x20` → `name@0x10`。
- **但这条路本轮断了**：`il2cpp_class_get_type` 的桩（`0x063c2eec`）指向 `0x640dcb0`，
  **正落在 8.3 说的编码块里**，`llvm-objdump` 输出 `<unknown>`，看不到 `#0x20`。
- 退一步做模式扫描（`ldr x0,[x0,#0x10]; ret`）也没用：全 `.text` 有 **389 处**命中，无法定位。
- 结论：**不要读 `klass+0x10`**。真要类名，用 `il2cpp_class_get_type` + `il2cpp_type_get_name_chunked`
  （两个 API 都在恢复表里：`0x063c2eec` / `0x063c3b30`），而不是读结构体。

## 8.7 闸门（顺序已按 lead 的决定调整）

```
① 服务端加 default_server（解决无 SNI）→ 重打一轮          ← 现在在这里
② 过了 → 证书问题消失，本次 hook 全案搁置（存档保留）
③ 没过 → 上 probe（Pass 1 最小版）→ 三行 log 判定
④ 探针通 → 上 probe2_full（完整版）→ 拿到 MethodInfo*
⑤ 查 encrypted_pages.txt → 决定「文件补丁」还是「改 methodPointer」
```
