# Frida 部署清单（给用户执行）

> 目的：给 `com.RoamingStar.BlueArchive` 挂 Frida，hook 掉「客户端拿到 200 响应之后做了什么判断」。
> 本文档**只描述步骤**，不代替你执行。所有命令都由你在设备/PC 上手动跑。
> 生成时间：2026-11-14 03:1x

---

## 0. 先想清楚：这一步的风险与收益

**收益**：目前唯一的黑盒是「客户端读完 `/api/account/auth` 的 200 响应后，为什么不动」。
Frida 能直接看到它的判断分支，比我们在服务端猜快一个数量级。

**风险**：
- 碧蓝档案国服带 **ACE（AntiCheatExpert）+ 腾讯 ACE**，对 Frida 有主动检测
- 检测命中通常表现为：**闪退 / 弹「检测到异常环境」/ 静默掉线**，一般不会封号（私服单机账号），但会打断实验
- 需要 root（你有 KSU），**不需要改 APK**（这点很重要，不动包体就不会破坏签名校验）

**建议**：先在**能接受的代价**下试；一崩就按第 7 节清理，回到现在的状态。

---

## 1. 要下的文件

| 项 | 值 |
|---|---|
| 组件 | **frida-server**（不是 frida-tools） |
| 架构 | `arm64`（aarch64） |
| 版本 | **与 PC 侧 `frida` 工具版本严格一致**，建议统一用 **16.5.9**（目前稳定、对 Android 14/15 兼容好） |
| 文件名 | `frida-server-16.5.9-android-arm64.xz` |
| 官方 release | `https://github.com/frida/frida/releases/tag/16.5.9` |
| 完整直链 | `https://github.com/frida/frida/releases/download/16.5.9/frida-server-16.5.9-android-arm64.xz` |

**PC 侧同步装**（版本必须一致，否则协议不匹配）：
```bash
pip install frida==16.5.9 frida-tools==12.4.5
```

> 如果下载慢，把 `.xz` 先下到 PC，再用 `adb push` 传过去，不要指望设备端 curl 拉 20 MB。

---

## 2. 放到哪、给什么权限

```bash
# PC 侧
xz -d frida-server-16.5.9-android-arm64.xz
adb push frida-server-16.5.9-android-arm64 /data/local/tmp/frida-server
# 或者：adb push 到 /sdcard/Download/ 再在设备上 mv

# 设备侧（需要 root shell）
su
chown root:root /data/local/tmp/frida-server
chmod 755 /data/local/tmp/frida-server
ls -lZ /data/local/tmp/frida-server     # 记下 SELinux 上下文，一般是 u:object_r:shell_data_file:s0
```

**为什么放 `/data/local/tmp`**：这是 Android 唯一稳定可执行的公共目录，且 ACE 对它的扫描优先级低于 `/data/adb/` 和 `/system`。

---

## 3. 怎么起

```bash
su
# 清掉可能残留的旧进程
pkill -f frida-server

# 起（后台、静默）
/data/local/tmp/frida-server -l 0.0.0.0:27042 >/dev/null 2>&1 &
```

**KernelSU 下的注意点**：
- **优先不要 `setenforce 0`**。KSU 的 root 域（`u:r:su:s0`）通常足以执行，且保持 Enforcing 不会额外触发 ACE 的「SELinux 被关」检测。
- 如果启动报 `Permission denied` 或 `exec format error`：
  ```bash
  getenforce                      # 看当前状态
  setenforce 0                    # 临时关（重启即恢复，不要写进开机脚本）
  /data/local/tmp/frida-server -l 0.0.0.0:27042 &
  ```
- 如果 KSU 有「SUSFS / umount 模块」，**不要**把 frida-server 加到挂载隐藏列表里 —— 那反而会让 ACE 的 `stat` 与 `open` 结果不一致，更容易被抓。

**验证它起来了**（设备侧）：
```bash
ps -A | grep frida-server
netstat -tlnp 2>/dev/null | grep 27042    # 或 ss -tlnp
```

---

## 4. PC 侧怎么连

**方式 A：网络连接（推荐，USB 被 ACE 占用时也能用）**
```bash
# 设备与 PC 同一局域网，设备 IP 假设 192.168.1.50
frida-ps -H 192.168.1.50:27042
```
如果连不上，先在设备上确认监听：`/data/local/tmp/frida-server -l 0.0.0.0:27042`（**必须是 `0.0.0.0`，不是 `127.0.0.1`**）。

**方式 B：USB + adb（最稳，不受 WiFi 影响）**
```bash
adb forward tcp:27042 tcp:27042
frida-ps -H 127.0.0.1:27042
# 或直接用 USB 模式
frida-ps -U
```

> **注意**：`frida -U` 需要 adb 设备在线，且 `frida-server` 以 root 起。
> 如果 `frida-ps -U` 报 `unable to find process`，多半是没 root 起，或 SELinux 拦了 —— 回第 3 节。

**注入脚本**：
```bash
frida -H 192.168.1.50:27042 -f com.RoamingStar.BlueArchive -l hook.js --no-pause
```
> `-f` 是**冷启动挂载**（在进程起来前注入，能抓到最早的初始化）。
> 但 ACE 对"被 attach 的启动"更敏感，**先用 `-n com.RoamingStar.BlueArchive` 挂到已经在跑的进程**试探，稳了再改 `-f`。

---

## 5. 要 hook 什么（我们的设计）

### 第一优先（直接对应"客户端怎么处理响应"）
```javascript
// 候选 1：解密，或者返回原文 —— 名字说明它同时处理"加密体"和"明文体"
Java.perform(function () {
  var cls = Java.use('MX.Core.Crypto.PacketCryptManager');   // 类名待确认，先用 enumerate
  // ...
});
```

**因为类名不一定准确，实际做法是先枚举再定位**：
```javascript
Java.perform(function () {
  Java.enumerateLoadedClasses({
    onMatch: function (name) {
      if (/Crypt|Decrypt|HttpGameSession|Protocol/i.test(name)) console.log(name);
    },
    onComplete: function () {}
  });
});
```
把输出贴回来，我们按真实类名写 hook。

### 第二优先
| 目标 | 为什么 |
|---|---|
| `DecryptOrReturnOriginal` | 名字直白：**解密，或者返回原文**。hook 它能看到「我们回的明文有没有被它接手」 |
| `IsSpecificErrorJson` | 「先当 JSON 解析再说」——hook 它能看到**它是否解析了我们的 body** |
| `HttpGameSession.DecodeResponse` / `WaitForRequest` | 响应进入业务层的第一站 |
| `PacketCryptManager.EncryptRequest` | 反向：确认请求加密参数（key/iv 生成位置） |
| 协议分发（按 protocol 号找 handler） | 能看出它**有没有走到分发**，还是更早就停了 |

### 第三优先
| 目标 | 为什么 |
|---|---|
| `CryptAES.DecryptRJ256Api` | 名字里有 RJ256（可能是 AES-256 CBC 的客户端封装） |
| 网络层（BestHTTP 回调） | 确认**响应体字节数**和**状态码**被读到的位置 |

**最重要的两个观察点**：
1. **`IsSpecificErrorJson` / `DecryptOrReturnOriginal` 有没有被调用** → 决定"它到底读不读 body"
2. **调用之后去了哪** → 决定"读到了但卡在哪个分支"

---

## 5A. ★ 先判死一件事：il2cpp 到底能不能 hook（已实测，结论是「不能按常规套路」）

我在本机对 `work/ba/audit/ba-apk/lib/arm64-v8a/libil2cpp.so`（270,927,056 字节）做了 ELF 结构分析，实测结果：

```
.dynsym 条目总数 = 2660
其中有名字的     = 306
其中 UNDEFINED    = 306（全部是「导入」）
其中 DEFINED      = 0        ← 没有任何导出符号带名字
il2cpp_* 导出符号 = 0        ← 一个都没有
```

**306 个具名导入**里，与网络相关的只有这些：
```
socket  connect  send  sendmsg  sendfile  recvfrom  recvmsg  read  write  poll  select
dlopen  dlsym  dl_iterate_phdr
```
**没有任何 `SSL_*` / `EVP_*` / `AES_*` / `curl_*` 导入。**
同时 `.symtab`（完整符号表）不存在，只有 `.dynsym`。

### ⇒ 三个直接后果

1. **`Java.enumerateLoadedClasses` 一定看不到 `MX.Core.Crypto.*`**
   那些是 **C# 类**，活在 il2cpp 的元数据里，不是 ART 的 Java 类。Java 层枚举再全也没用。

2. **`Module.findExportByName("libil2cpp.so", "il2cpp_class_from_name")` 一定返回 null**
   因为 `.dynsym` 的导出符号被整个抹掉了（名字清零 / 只留导入）。
   ⇒ **`frida-il2cpp-bridge` 这类"靠导出符号找入口"的工具，在本包上开箱即用是行不通的。**

3. **TLS 与加密都不在导入表里**
   说明 TLS/AES 是**进程内自带实现**，或者是**运行时 `dlopen` 加载的独立 .so**（`dlopen/dlsym` 都在导入表里）。
   ⇒ **真正好打的位置不是 il2cpp，而是运行时加载的 TLS 库。**

### ⇒ 所以第一枪改为「网络层钩子」，不碰 il2cpp

这反而是**更好的选择**，因为我们要回答的问题本来就只有一个：
> **客户端到底有没有把我们那份 200 响应读进内存？**

把 `SSL_read`（或等价的 TLS 解密函数）钩住，**服务端返回的明文 body 会原样经过它** —— 有没有被调用、被调用几次、参数字节数是多少，一眼就能看见。
而且这类符号来自**运行时加载的独立 .so**（不是被 strip 的 libil2cpp），`findExportByName` 是能命中的。

---

## 5B. 零风险侦察脚本（第一次就只做这件事，不 hook 任何东西）

### 脚本 `recon.js`（只观察，不改变任何行为）

```javascript
// recon.js —— 只枚举，不 hook。目标是回答三个问题：
//   1) 有哪些模块被加载（找 TLS 库）
//   2) 哪些模块导出了 SSL_read / mbedtls_ssl_read / curl_easy_perform
//   3) il2cpp 导出是否真的为空（确认我们的静态分析）

setTimeout(function () {
  console.log('=== loaded modules ===');
  Process.enumerateModules().forEach(function (m) {
    console.log('  ' + m.name + '  base=' + m.base + '  size=' + m.size);
  });

  console.log('=== TLS / crypto exports probe ===');
  var mods = Process.enumerateModules().map(function (m) { return m.name; });
  var wanted = ['SSL_read', 'SSL_write', 'mbedtls_ssl_read', 'mbedtls_ssl_write',
                'curl_easy_perform', 'curl_easy_setopt', 'EVP_DecryptUpdate'];
  mods.forEach(function (name) {
    try {
      var mod = Process.findModuleByName(name);
      if (!mod) return;
      wanted.forEach(function (sym) {
        var p = mod.findExportByName(sym);
        if (p) console.log('  HIT  ' + name + '!' + sym + ' -> ' + p);
      });
    } catch (e) {}
  });

  console.log('=== il2cpp export probe (expect empty) ===');
  var il = Process.findModuleByName('libil2cpp.so');
  if (!il) {
    console.log('  libil2cpp.so NOT loaded');
  } else {
    console.log('  libil2cpp.so base=' + il.base + ' size=' + il.size);
    ['il2cpp_init', 'il2cpp_domain_get', 'il2cpp_class_from_name',
     'il2cpp_resolve_icall'].forEach(function (s) {
      console.log('  ' + s + ' -> ' + il.findExportByName(s));
    });
  }

  console.log('=== native threads (frida footprint check) ===');
  Process.enumerateThreads().forEach(function (t) {
    console.log('  tid=' + t.id + ' state=' + t.state);
  });
}, 0);
```

**怎么跑**（挂到已经在跑的进程，不用 `-f`，痕迹更小）：
```bash
frida -H <设备IP>:<端口> -n com.RoamingStar.BlueArchive -l recon.js --no-pause
```

### 怎么判断「侦察成功」

| 观察 | 含义 | 下一步 |
|---|---|---|
| 打印出 20+ 个模块名 | ✅ Frida 可用、进程可见 | 继续看下面 |
| 出现 `SSL_read` 或 `mbedtls_ssl_read` 的 HIT | ✅ **找到 TLS 层** | 直接写 hook，那是决定性证据 |
| 一个 TLS 符号都没有 | 说明 TLS 在 `libunity.so` 内部静态链接 | 改用 `recv`/`recvmsg` 钩子（只能看密文长度，信息量低） |
| `il2cpp_*` 全是 `null` | ✅ 与静态分析一致 | **放弃 il2cpp 路线**，别再试 frida-il2cpp-bridge |
| 一条都没打印出来 | ❌ Frida 没连上 / 被拦 | 先解决连接问题，别往下走 |

### 如果 `Java.enumerateLoadedClasses` 拿不到、`il2cpp_*` 又是空，还有哪条路

| 方案 | 可行性 | 说明 |
|---|---|---|
| **A. 钩 TLS 库的 `SSL_read`** | **高** | 前提是侦察脚本能找到它；这是**首选** |
| B. 钩 `recv`/`recvmsg`（libc） | 高（但信息量低） | 只能看**密文**字节数和时序；能证明"有数据到达"，但不能看内容 |
| C. 在 `.text` 里按字符串引用找 il2cpp 函数 | 中 | 需要 IDA/Ghidra 交叉引用；工作量大，且版本更新即失效 |
| D. `dl_iterate_phdr` 拿 `.dynamic` 里的 `DT_SYMTAB` 手工解析 | 低 | 导出名为空，解析出来也没名字 |
| E. 换思路：hook `libcurl`（UnityWebRequest 用） | 中 | 侦察脚本会告诉我们有没有 `curl_easy_perform` 导出 |

**结论：第一枪打 TLS，不打 il2cpp。** 侦察脚本跑一次就能知道这条路通不通，成本 3 分钟。

---

## 5C. 不用 Frida 的备选：改 `libil2cpp.so` 的 `DT_INIT`（已做过类似东西）

如果 Frida 因为「推 20 MB 文件 / ACE 检测」不可行，还有一条**不装任何东西、只换一个 .so** 的路。

**依据（本项目已有资产）**：
```
work/ba/bapatch/probe.S              4616 B
work/ba/bapatch/probe2_full.S        9537 B     ← 完整的 DT_INIT cave 探针
work/ba/bapatch/libil2cpp_probe.bin  270,927,056 B  ← 已打过补丁的 so
```
做法是：在 `libil2cpp.so` 里找一段 **456 字节的代码洞（cave）**，把探针 shellcode 写进去，
再把 `DT_INIT` 指向这段 cave —— **只改 4 个字节（DT_INIT 的 d_ptr）**，其余文件原样。

**为什么这条路对 ACE 更安全**：
- `libil2cpp.so` **没有被 ACE 哈希钉死**（我们之前已验证：ACE 只钉 `libunity.so` 和 `global-metadata.dat`）
- 不引入任何外部文件、不占端口、进程名干净、`/proc/self/maps` 里看不到 `frida-agent`

**探针里能做什么（对应 Frida 的 TLS 方案）**：
1. 在 `DT_INIT` 里调用 `dl_iterate_phdr` 遍历已加载模块，按名字找 TLS 库（`libssl.so` / `libmbedtls.so` / 其它）
2. 用 `dlsym`（或直接解析该模块的 `.dynsym`）拿到 `SSL_read` 地址
3. `mprotect(PAGE_EXEC)` 后把自己那段改成 inline hook（保存原始前 4 条指令，跳到 trampoline）
4. hook 里只做两件事：**把 `(返回值=字节数)` 和 `(缓冲区前 64 字节)` 写到 `__android_log_print`**
5. 完事后原函数照常执行，行为不变

**代价与风险**：
- 需要重新签名 APK（`broken` 顺序：改 so → 重打包 → 签名 → 安装），一次约 10 分钟
- 探针崩溃会让游戏直接起不来 —— 但换回原 so 就恢复，**可回滚**
- 只能在**能改包**的前提下用；如果用户不接受重装，这条路就不通

**结论：留作 Frida 不通时的 Plan B，现在不做。**

---

## 5D. `recon.js` 已写好（可直接跑）

文件：`report/_frida/recon.js`

**两种模式都支持**：
```bash
# 首选：attach 已运行进程（spawn 在 KSU 上有已知坑）
frida -H <设备IP>:<端口> -n com.RoamingStar.BlueArchive -l recon.js --no-pause

# 备选：spawn 冷启动（脚本内部会轮询等 libil2cpp.so 映射出来，最多 15 秒）
frida -H <设备IP>:<端口> -f com.RoamingStar.BlueArchive -l recon.js --no-pause
```

**脚本做什么（只枚举，不 hook）**：
1. 打印 Frida 版本 / 架构 / pid
2. `Process.enumerateModules()` 全量列出（名字 + base + size + path）
3. 对**每个模块**探这些导出：
   `SSL_read / SSL_write / SSL_get_error / SSL_pending / mbedtls_ssl_read / mbedtls_ssl_write / EVP_DecryptUpdate / EVP_EncryptUpdate / EVP_CipherInit_ex / curl_easy_perform / curl_easy_setopt / recv / recvmsg / recvfrom / send / sendmsg / read / write`
4. 对 `libil2cpp.so` 探 `il2cpp_init / il2cpp_domain_get / il2cpp_class_from_name / il2cpp_resolve_icall / il2cpp_thread_attach`（**预期全 null**）
5. 打印线程数（顺带看 Frida 自身痕迹规模）

**兼容性处理**：`Module.findExportByName` 与对象 API（`Process.findModuleByName(m).findExportByName(s)`）两条路都试，Frida 12~17 都能跑。

**看输出下结论**：
| 输出 | 结论 |
|---|---|
| 出现 `SSL_read` 或 `mbedtls_ssl_read` 的 `HIT` | ✅ 找到 TLS 层 → 直接写 hook，能拿到明文 body |
| 只有 `recv`/`recvmsg` 的 `HIT`，没有 TLS 符号 | TLS 静态链在 `libunity.so` 里 → 只能看密文长度 |
| `IL2 il2cpp_* = null` 全部 | ✅ 与静态分析一致 → 彻底放弃 il2cpp 路线 |
| 一条都没打印 | Frida 没连上（回第 3、4 节排查） |

---

## 6. ACE 检测风险（已知特征与规避程度）

| 检测手段 | 是否会被抓 | 我们能做的 |
|---|---|---|
| `/proc/self/maps` 里出现 `frida-agent` / `gum-js-loop` / `gmain` | **高** | 用 `frida-server` 改名（如 `fs`），或用 `magisk-frida-hide` 类模块；**无法完全消除** |
| 默认端口 **27042** 被扫 | **高** | 换端口：`-l 0.0.0.0:39471` |
| `/proc/<pid>/status` 里 `TracerPid != 0` | **高**（若用 `-f` 注入更明显） | 用 `-n` attach 已运行进程，减少早期痕迹 |
| 检测 `frida-server` 进程名 | **中** | 重命名二进制文件 |
| 检测 `Xposed` / `Magisk` 痕迹 | **中** | 与本步无关，但你设备上若有这些模块，ACE 也会算进去 |
| 检测线程名（`gum-js-loop`） | **高** | 无干净解法，只能靠模块隐藏 |
| 检测 `/data/local/tmp` 下可执行文件 | **中** | 换个不显眼的目录名（但注意 SELinux 上下文） |

**结论：Frida 在这款游戏上"能活多久"是概率问题，不是配置问题。**
建议做法：**一次只挂 3–5 分钟**，抓到日志就撤，不长期常驻。

**一崩就停**：如果游戏启动即闪退或弹异常，说明被检测到，立刻按第 7 节清理，改走别的路（比如继续在服务端做正交实验）。

---

## 7. 回滚（彻底清理）

```bash
# 1) 停进程
su -c "pkill -f frida-server"

# 2) 删文件
su -c "rm -f /data/local/tmp/frida-server"

# 3) 如果改过 SELinux
su -c "setenforce 1"
getenforce          # 应显示 Enforcing

# 4) 清 adb 端口转发（PC 侧）
adb forward --remove tcp:27042

# 5) 卸载 PC 侧工具（可选）
pip uninstall frida frida-tools

# 6) 确认干净
ps -A | grep -i frida          # 应无输出
ls /data/local/tmp/            # 不应有 frida-server
```

**重启设备**是最彻底的收尾（会把 `setenforce 0` 等临时状态全部还原）。

---

## 8. 执行前需要用户确认的三件事

1. **设备能不能 root shell**（KSU 已装，确认 `su` 能正常提权）
2. **能否接受"游戏可能闪退/弹异常"这个代价**（大概率可恢复，只需重启 + 清理）
3. **能不能拿到 PC 与设备的连通方式**（USB adb 或同局域网）

三条都 OK 再动手；任何一条不行，我们就继续在服务端做实验，不依赖 Frida。

---

## 9. 附：一次最小试探流程（推荐首次就这么做）

```bash
# 设备
su
cp /sdcard/Download/frida-server /data/local/tmp/fs        # 改名，降低进程名命中率
chmod 755 /data/local/tmp/fs
/data/local/tmp/fs -l 0.0.0.0:39471 &                     # 换端口

# PC
frida-ps -H <设备IP>:39471                                 # 只要能列出进程就算成功
frida -H <设备IP>:39471 -n com.RoamingStar.BlueArchive -l enum.js --no-pause
```
`enum.js` 只用 `Java.enumerateLoadedClasses` 打印含 `Crypt|Decrypt|Session|Protocol` 的类名，
**不做任何 hook** —— 这一步零风险，先确认「能不能连上、能不能枚举」。
拿到类名清单后再写真正的 hook。
