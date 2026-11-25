# 14 · 运行期 dump metadata → 定位 ValidateCertificate → 离线补丁 libil2cpp

> 前提（你给的实测）：客户端连 `gsqc-api:443`，DNAT 到我们服务器后
> `ClientHello → ServerHello+证书(1343B) → 客户端 30 字节 alert → FIN`；CA 已装三处仍被拒。
> 本文只给**可执行流程**，每条结论标注 **已证 / 推断**。
> 关键背景（上一轮已证）：`global-metadata.dat` 磁盘态被部分 XOR 混淆（magic `0x12724394`、无 `0xFAB11BAF`）；
> libil2cpp **无 hash pin**（可原位替换）；libil2cpp 的 `.dynsym` 里 `il2cpp_*` 导出 **0** 个。

---

## 0. 结论（先看这 6 行）

1. **30 字节 alert 说明 TLS 已经走到证书/密钥阶段**：明文 alert 只有 7 字节（5 头 + 2），
   30 字节只能是**加密 alert**（TLS1.2 AES-GCM 约 31、TLS1.3 约 24，随套件浮动）→ 客户端是在收到 ServerHello/证书后
   才拒绝的，**不是版本/ALPN/SNI 层面的失败**（**推断**，从长度量级推；确切原因用 §1 的 openssl 读）。
2. **dump 大概率可行，但必须先确认内存里的 header 是明文**：il2cpp 的 `MetadataLoader::LoadMetadataFile`
   在现代版本是 `open/read→malloc(长度)→读入`，**不是 mmap**（**推断**，libil2cpp 里只有一处 `global-metadata.dat` 字符串，
   即按路径读文件）。所以预期内存里是一块 **~38.4 MB 的匿名 rw-p 映射**，首 4 字节 `AF 1B B1 FA`。
   若保护壳改成 mmap+就地解密，则会在 maps 里出现 `global-metadata.dat` 的 file-backed 映射。
3. **第一步（只读，一条命令，见 §2）**：扫 `/proc/$pid/maps` 里所有映射的前 64 字节，找 `af1bb1fa`（已解密）
   或 `94437212`（仍是密文）。输出 `HIT-DECRYPTED` 才能 dump。
4. **建议先花 5 分钟做 §1 的 alert 判读**：用 `openssl s_server` 收同一个连接，它会打印客户端 alert 的
   **明文原因**（`unknown ca` / `bad certificate` / `certificate unknown`）。不同原因对应完全不同的修法，
   不做这一步可能白 patch 一轮。
5. **定位 `ValidateCertificate` 的标准路径**：Il2CppDumper v6.7.46（Windows 自包含包，**无需装 .NET**）→ `dump.cs`
   里直接有 `// RVA: … Offset: …`；本 so 的 `p_vaddr == p_offset`，**Offset 就是文件偏移**。
6. **补丁**：`20 00 80 52 C0 03 5F D6`（`mov w0,#1; ret`，**已核对**）。但必须先排除 **iFix 代理**
   （metadata 里有 `<>iFixBaseProxy_ValidateCertificate`）——热更框架可能让原方法体变成空壳，
   这时要**同时 patch 代理**或改 patch 代理。

**工作量预估**：判定 10 分钟；dump+传输 20 分钟；Il2CppDumper 10 分钟；
定位+补丁 20 分钟；上机验证 20 分钟。**顺利 1.5 小时，含失败重试半天。**

---

## 1. 第 0 步（强烈建议）：先把 alert 的原因读出来（5 分钟，零补丁）

客户端发的是**加密 alert**，但**我们自己有服务器私钥**——用 `openssl s_server` 收同一条连接，
它会把客户端 alert 解密并打印原因。PC 上有 msys2 的 openssl（`where openssl` 确认）。

```powershell
# PC 侧（把 DNAT 指到这台 PC 的 443；证书用我们给 gsqc-api 签的那张）
openssl s_server -accept 443 -cert .\fullchain.pem -key .\k.pem -www -state -msg
# 手机侧照旧启动游戏，等它连过来
```

判读（关键）：

| s_server 打印 | 含义 | 下一步 |
|---|---|---|
| `sslv3 alert unknown ca` / `alert unknown ca` | 客户端**不认我们的 CA**（系统库没被用 / 用了自带 CA / pinning） | 走本文 patch 路线 |
| `alert bad certificate` | 证书本身不合规（链不全 / SAN 不匹配 / 时间） | **先修证书**，不用 patch |
| `alert certificate unknown` | 通用拒绝（多见于 pinning / 自定义校验） | 走 patch 路线 |
| `alert handshake failure` | 算法/版本不匹配（不是证书） | 先查 TLS 版本/套件 |
| 客户端根本没连过来 | DNAT 没生效 | 先修 DNAT |

> 如果这里是 `bad certificate`，那 1343 B 的证书很可能是**只发了叶子、没发中间证书**，或者 SAN 里没有
> `gsqc-api.bluearchive-cn.com`。这两种都属于"证书配置问题"，装 CA 也救不了，patch 也救不了。

---

## 2. 第 1 步：运行期判定（一条只读命令）

### 2.1 命令（整段粘进 root shell；只读，不改任何东西）

```sh
pid=$(pidof com.RoamingStar.BlueArchive); echo "pid=$pid"
busybox awk '
function h2d(h,  i,c,v){v=0; for(i=1;i<=length(h);i++){c=tolower(substr(h,i,1)); v=v*16+index("0123456789abcdef",c)-1} return v}
{ split($1,a,"-"); s=h2d(a[1]); e=h2d(a[2]);
  printf "%.0f %.0f %s %s\n", s, e-s, $2, ($6==""?"[anon]":$6) }
' /proc/$pid/maps | while read s n perm name; do
  h=$(busybox dd if=/proc/$pid/mem bs=1 skip=$s count=64 2>/dev/null | busybox od -An -tx1 | tr -d ' \n')
  [ -z "$h" ] && continue
  head=$(echo "$h" | busybox cut -c1-8)
  case "$h" in
    *af1bb1fa*) echo "HIT-DECRYPTED start=$s size=$n perm=$perm $name head=$head";;
    *94437212*) echo "HIT-ENCRYPTED start=$s size=$n perm=$perm $name head=$head";;
  esac
done
```

> 说明：
> - `h2d` 用 awk 的 double 做十六进制转换，48 位地址在 2^53 内**精确**；
> - 每个映射只读 64 字节，`dd` 用 lseek 直接定位，全进程通常 1000～1500 个映射，**十几秒跑完**；
> - **为什么读 64 字节而不是 4**：如果 metadata 是 `malloc` 分配的，bionic 的 dlmalloc 会在映射头部留
>   8/16 字节 chunk header，**mapping_start 不等于 buffer_start**，magic 会出现在 +8/+16 处；
>   所以要在前 64 字节里搜，而不是只看偏移 0。

### 2.2 输出怎么读

| 输出 | 结论 | 下一步 |
|---|---|---|
| `HIT-DECRYPTED start=… size=38428672 … [anon]` | **内存里是明文**（size = 38,428,672 = 38426024 向上取整到 4 KB） | 直接按 §3 dump |
| `HIT-DECRYPTED … global-metadata.dat` | 内存里是明文，且是**file-backed mmap**（保护壳就地解密） | 同样按 §3 dump（skip 用该映射起点） |
| 只有 `HIT-ENCRYPTED`（`94437212`） | 该处是原文件映射；**明文副本在别处**（多半是匿名堆，可能不是 38.4 MB 整块） | 先跑 §2.3 的"放宽扫描" |
| 两种都没有 | 内存里没有明文整块（可能是按需解密/已释放） | **dump 无意义**，转 §6 方案 C/D 或 hook read |

### 2.3 补充：两种情况下的兜底扫描

**(a) 明文副本不是整块 38.4 MB**（保护壳把 metadata 拆开/只留表）：

```sh
pid=$(pidof com.RoamingStar.BlueArchive)
busybox awk 'function h2d(h, i,c,v){v=0;for(i=1;i<=length(h);i++){c=tolower(substr(h,i,1));v=v*16+index("0123456789abcdef",c)-1}return v}
{split($1,a,"-");s=h2d(a[1]);e=h2d(a[2]);n=e-s; if($2 ~ /^rw/ && n>1000000) printf "%.0f %.0f\n", s, n}' /proc/$pid/maps |
while read s n; do
  sk=$(busybox awk -v s=$s 'BEGIN{printf "%.0f", s/4096}')
  ct=$(busybox awk -v n=$n 'BEGIN{printf "%.0f", n/4096}')
  busybox dd if=/proc/$pid/mem bs=4096 skip=$sk count=$ct 2>/dev/null \
    | busybox grep -abo $'\xaf\x1b\xb1\xfa' | head -1 | while read off rest; do
        echo "MAGIC in region start=$s off=$off"; done
done
```
（这条会读几百 MB，慢；只在 2.2 只有 ENCRYPTED 时用。注意 `$((…))` 在这里**不能**用来算 48 位地址——
Android 的 mksh 在某些版本上按 32 位处理，统一用 awk 算。）

**(b) 保护壳把解密后的文件落盘**（ACE 有 `files/data/app` 解包目录，很可能就在这里）：

```sh
find /data/data/com.RoamingStar.BlueArchive /data/user/0/com.RoamingStar.BlueArchive \
     -type f -size +30000000c -size -50000000c 2>/dev/null | while read f; do
  m=$(busybox head -c 8 "$f" | busybox od -An -tx1 | tr -d ' \n'); echo "$m $f"
done
# 期望看到 af1bb1fa… 的那一行；如果是 94437212… 就是原加密文件
```

---

## 3. 第 2 步：dump（设备侧 + 传回 PC）

### 3.1 设备侧（以 §2 得到的 `start=… size=…` 为准）

```sh
pid=$(pidof com.RoamingStar.BlueArchive)
S=<HIT 行的 start>          # 十进制
N=<HIT 行的 size>           # 十进制，通常 38428672
skip=$(busybox awk -v s=$S 'BEGIN{printf "%.0f", s/4096}')
cnt=$(busybox awk -v n=$N 'BEGIN{printf "%.0f", n/4096}')

kill -STOP $pid                                   # 冻结，避免撕裂/中途 unmap
busybox dd if=/proc/$pid/mem of=/data/local/tmp/md.bin bs=4096 skip=$skip count=$cnt
kill -CONT $pid

ls -l /data/local/tmp/md.bin
busybox md5sum /data/local/tmp/md.bin
busybox od -An -tx1 -N16 /data/local/tmp/md.bin   # 期望 af 1b b1 fa 1d 00 00 00 …
```

**坑**（root 读 `/proc/pid/mem`）：

- 读**未映射**地址会返回 `EIO`；我们是按映射起点读整段，不会踩空。若中途报 EIO，说明目标进程在 dump 期间改过映射
  → `kill -STOP` 后再 dump。
- 读 `r-xp` 页也需要 `CAP_SYS_PTRACE`；KernelSU 的 `u:r:ksu:s0` 一般可以。若报 `Permission denied`，
  先用 `dd … count=1` 做单页试验。
- `bs=4096` 是关键：`bs=1` 会退化成 3800 万次小读写，几十分钟都跑不完。

### 3.2 传回 PC（三条路，按可用性排序）

**路 A（有 adb，最稳）**：
```powershell
adb exec-out su -c "cat /data/local/tmp/md.bin" > md.bin
```
adb 是二进制安全的；PC 侧 `certutil -hashfile md.bin MD5` 与手机 `md5sum` 对比。

**路 B（没有 adb，复用现有 `nc -e sh` 通道）**：
```sh
# 手机：先压缩（38 MB 明文一般压到 8–12 MB）
busybox gzip -1 -c /data/local/tmp/md.bin > /data/local/tmp/md.gz
busybox md5sum /data/local/tmp/md.gz
```
```powershell
# PC：把一条"打印 base64"的命令发进那个 shell 通道，收回 stdout
"busybox base64 /data/local/tmp/md.gz" | nc <手机IP> 18080 > md.b64
```
```powershell
# PC：解码 + 解压 + 校验
python -c "import base64,gzip,sys; d=base64.b64decode(open('md.b64','rb').read()); open('md.gz','wb').write(d)"
python -c "import gzip; open('md.bin','wb').write(gzip.open('md.gz','rb').read())"
```
> 为什么要 base64：`nc -e sh` 走的是 shell 的 stdout，二进制会被 shell 层破坏（并且可能被 CRLF/控制字符干扰）；
> base64 是最稳的。13 MB 的 base64 走 LAN 大约 1–2 分钟。

**路 C（手机主动推）**：手机 `busybox nc <PC_IP> 9000 < /data/local/tmp/md.gz`，PC `ncat -l 9000 > md.gz`。
只有 PC 能被手机访问时才用（防火墙/网段常见坑）。

### 3.3 校验（必须做）

| 检查 | 期望 |
|---|---|
| 文件大小 | 38,428,672（=38426024 向上取整 4 KB）；若用 `dd count` 截断，应为 38,426,024 或整页 |
| 前 4 字节 | `af 1b b1 fa` |
| 偏移 4 的 int32 | `29`（Unity 2021.3 的预期；也可能是 27/28/31，见 §4.2） |
| md5 | 手机 `md5sum` 与 PC 一致 |
| 字符堆抽样 | 偏移 0x129d13 附近应是 `ServerInfoConnectionGroupData`（明文） |

> 若前 4 字节仍是 `94 43 72 12` → **dump 无意义**：说明我们拿到的是磁盘加密态，不是 il2cpp 解析用的明文。
> 直接跳到 §6。

**PC 侧先切齐**（dump 的是整段映射，buffer 可能从 +8/+16 开始）：

```powershell
python -c "d=open('md.bin','rb').read(); i=d.find(bytes.fromhex('af1bb1fa')); assert 0<=i<4096, i; open('md_clean.bin','wb').write(d[i:]); print('magic at',hex(i),'size',len(d)-i)"
```
切完的 `md_clean.bin` 长度应 **≥ 38,426,024**（多出来的尾部是页对齐填充，Il2CppDumper 不介意）。

---

## 4. 第 3 步：定位 `ValidateCertificate`

### 4.1 拿 Il2CppDumper

PC 上目前**没有** Il2CppDumper（`work/ba/bapatch/` 只有我们自己的脚本）。用官方自包含 Windows 包，
**不需要装 .NET**：

```
https://github.com/Perfare/Il2CppDumper/releases/download/v6.7.46/Il2CppDumper-win-v6.7.46.zip   (11 MB, self-contained)
```

（PC 上已有 .NET 8；也兼容 `Il2CppDumper-net7-win-v6.7.46.zip`。）

```powershell
# 解压后
.\Il2CppDumper.exe work\ba\bapatch\libil2cpp.bin md.bin out\
```

> 输入用 `libil2cpp.bin` 即可（与设备上的 `libil2cpp.so` 同文件，sha256 `5ac1cbe0…`）。
> 输出：`dump.cs`、`script.json`、`il2cpp.h`、`stringliteral.json`、`DummyDll/`。

### 4.2 il2cpp 版本怎么确定（不要猜）

1. **dump 出来的 metadata 头里就有**：偏移 4 的 int32。
   ```powershell
   python -c "import struct;d=open('md.bin','rb').read(64);print(hex(struct.unpack_from('<I',d,0)[0]), struct.unpack_from('<i',d,4)[0])"
   ```
   预期：`0xfab11baf 29`。Unity 2021.3.x → metadata **v29**（**推断**，2021.2 是 27.x、2022.3 是 31）。
2. Il2CppDumper 会按这个 version 自动选结构体；若它报 `Unsupported metadata version`，把 27/28/29/31 逐个试
   （`Il2CppDumper` 只在 header 上判断，改一下副本的第 4 字节即可做 A/B）。
3. 交叉验证：`libil2cpp.bin` 里 `global-metadata.dat` 字符串只有 **1 处**（loader 读文件的路径），
   说明它就是标准 `MetadataLoader`，不会有自定义 header 变体。

### 4.3 拿到地址

**方式 1：`dump.cs` 直接读注释**（Il2CppDumper 会给每个方法算好 RVA/Offset）

```powershell
Select-String -Path out\dump.cs -Pattern 'class CustomCertificateHandler' -Context 0,40
```
期望看到类似：

```csharp
public class CustomCertificateHandler : CertificateHandler
{
    // RVA: 0x0XXXXXXX Offset: 0x0XXXXXXX VA: 0x0XXXXXXX
    protected override bool ValidateCertificate(byte[] certificateData) { }
}
```
- **`Offset:` 就是文件偏移**（本 so 的 LOAD 段 `p_vaddr == p_offset`，见 §5.2 的验证）。
- 同时找 `<>iFixBaseProxy_ValidateCertificate` 是否存在同名方法（**大概率存在**，见 §5.3）。

**方式 2：`script.json`**（更适合脚本处理）

```powershell
python -c "import json;d=json.load(open(r'out\script.json',encoding='utf-8'));[print(m) for m in d['ScriptMethod'] if 'ValidateCertificate' in m['Name']]"
```
输出形如 `{'Address': 12345678, 'Name': 'CustomCertificateHandler$$ValidateCertificate', 'Signature': '...', 'TypeSignature': '...'}`，
`Address` 即 RVA。

### 4.4 版本/地址的交叉校验（强烈建议）

在补丁前，先把 `Offset` 处的 16 字节打出来，确认是**函数序言**而不是数据：

```powershell
python -c "d=open(r'work\ba\bapatch\libil2cpp.bin','rb').read();o=0xXXXXXXX;print(d[o:o+16].hex())"
```
期望以 `fd 7b bf a9`（`stp x29,x30,[sp,#-N]!`）或 `ff 43 0X d1`（`sub sp,sp,#N`）开头。
若是一堆 0 或 ASCII → Offset 算错了，改用 RVA 手工映射（§5.2）。

---

## 5. 第 4 步：补丁

### 5.1 机器码（已核对）

```
mov w0, #1   ->  0x52800020  ->  LE 字节 20 00 80 52
ret          ->  0xD65F03C0  ->  LE 字节 C0 03 5F D6
```
`ValidateCertificate` 返回 `bool`（IL2CPP 用 w0 低 8 位），`w0=1` 即 true。**8 字节**。

### 5.2 文件偏移公式

```
file_offset = RVA - 所在 LOAD 段.p_vaddr + 段.p_offset
```
本 so 的所有 LOAD 都满足 `p_vaddr == p_offset`（例如 `0x59b8000` 段、`il2cpp` 段 `0x64c1260`），
所以对 `il2cpp` 段（`0x64c1260 + 0x8dfedac`，148.9 MB）内的地址：

```
file_offset = RVA        # 直接用
```
`dump.cs` 里 Il2CppDumper 已经算好的 `Offset` 更省事，二者应当相等（可互相验证）。

### 5.3 必查风险：iFix 代理

metadata 里明确有 **`<>iFixBaseProxy_ValidateCertificate`**（`0x1522f2`，XOR-0x66 区）。iFix 类热更框架的常规做法是：

- 原方法体被改成一句"调代理"，真正逻辑在代理里（代理再分发到热更 DLL 或原实现）；
- 或者代理只是转发到原实现。

**处理**：`dump.cs` 里搜 `CustomCertificateHandler`，把 **两个方法都列出来**，然后：

1. 先 patch **`<>iFixBaseProxy_ValidateCertificate`**（如果它是返回 bool 的同类方法）；
2. 再 patch 原始 `ValidateCertificate`；
3. 若两者签名不同（代理可能返回 object/void），只 patch 原方法，靠"代理最终回落到原方法"生效。

> 判定方法：patch 后仍被拒 → 说明热点在代理或另一条 TLS 栈；把代理也 patch 再试。

### 5.4 补丁脚本（PC，纯标准库）

```python
# patch_cert.py  py -3 patch_cert.py libil2cpp.bin libil2cpp_cert.bin 0x<Offset>
import sys, struct
src, dst, off = sys.argv[1], sys.argv[2], int(sys.argv[3], 0)
d = bytearray(open(src, 'rb').read())
print('before:', d[off:off+8].hex())
assert d[off:off+8] != bytes.fromhex('20008052c0035fd6'), 'already patched?'
# 强校验：必须是函数序言（stp x29,x30 / sub sp）
first = struct.unpack_from('<I', d, off)[0]
assert (first & 0xFFC07FFF) in (0xA9807BFD, 0xA9BF7BFD) or (first & 0xFF8003FF) == 0xD10003FF, hex(first)
d[off:off+8] = bytes.fromhex('20008052c0035fd6')
open(dst, 'wb').write(d)
print('after :', d[off:off+8].hex())
```
（`0xA9807BFD` = `stp x29,x30,[sp,#-0x..]!`；`0xA9BF7BFD` = `stp x29,x30,[sp,#-0x10]!`；`0xD10003FF` = `sub sp,sp,#imm`。宁可误杀也不要写错位置。）

### 5.5 替换到设备

```sh
# 1) 备份（第一次做先备份到 /data/local/tmp）
cp /data/app/~~*/com.RoamingStar.BlueArchive-*/lib/arm64/libil2cpp.so /data/local/tmp/libil2cpp.orig.so
# 2) 覆盖（cp 保持 inode/context；mv 会换 inode）
cp /data/local/tmp/libil2cpp_cert.so <上面那个路径>
# 3) 校验
md5sum <路径> /data/local/tmp/libil2cpp_cert.so
# 4) force-stop + 冷启动
am force-stop com.RoamingStar.BlueArchive
```
> 上一轮已实测：`libil2cpp.so` 原位替换可正常启动、无 ACE hash pin。

### 5.6 验证

1. 再抓一次 pcap：若握手完成、出现 HTTP 请求 → 成功。
2. 若仍 30 字节 alert → 见 §6。
3. 回滚：`cp /data/local/tmp/libil2cpp.orig.so <路径>`。

### 5.7 关于"methodPointer 会不会被缓存/内联"

| 疑问 | 判定 |
|---|---|
| `MethodInfo->methodPointer` 缓存 | **不影响**：我们改的是**代码字节**，不是 `methodPointers[]` 表；指针指向的地址没变 |
| vtable 缓存 | **不影响**：virtual 调用取的是函数地址，内容改了照样生效 |
| IL2CPP 内联 | **低风险**：`ValidateCertificate` 是 virtual override，被 **libunity 原生**通过 vtable 回调（`CertificateHandlerProxy`），跨模块不可能内联。但游戏 C# 内部 `new CustomCertificateHandler().ValidateCertificate(...)` 的直接调用**可能**被内联 → 判定：用 Ghidra 在 `libil2cpp.bin` 里对该函数地址做 xref 统计（>2 处引用就有内联副本风险），或直接实测 |
| 多处 handler | 如果游戏给不同请求装了不同 handler，要逐个 patch（`dump.cs` 搜所有 `: CertificateHandler` 的子类） |

---

## 6. 失败分支与替代方案

### 6.1 如果 dump 不可行（§2 只有 ENCRYPTED，或 §3.3 头部不对）

说明保护壳没有把明文 metadata 留在内存的连续区。此时：

- **B（改 `get_ApiUrl` 返回 http）**：难度**更高**，不建议先做。原因：`get_ApiUrl` 返回的是 `Il2CppString*`，
  不能像 bool 那样一条 `mov w0,#1` 解决——需要构造/劫持一个字符串对象（game 里已有 `example.com` 之类字面量可借用，
  但仍要找到它的 `Il2CppString` 指针，或在代码洞里 `il2cpp_string_new`——而 **libil2cpp 不导出任何 `il2cpp_*`**，
  调不到）。所以 B 的前置比 A 多两步。
- **C（connect GOT + 80 端口）**：**单独不可行**——TLS 仍在，只是换了个地址；必须与 "scheme 改 http" 同时成立。
- **D（test-ba 明文环境）**：**基本已被你的设备证据否定**——`files/LocalizeConfig.txt` 里已经是 `Env=dev`
  （`audit/api-probe.md:15`），而客户端仍然连 `gsqc-api`。所以 `Env=dev` **不是**切 test 环境的开关。
  可以花 5 分钟做一次排除：把 `Env` 改成 `prod`/`test` 各启动一次，抓包看目标主机有没有变化；大概率不变。

### 6.2 如果 patch 完仍被拒（说明校验不在托管层）

三种可能，按概率排：

1. **Unity 用自带 CA bundle（mbedtls）而不是系统库**：libunity 里 mbedtls 字符串 107 条、`cacert` 0 条，
   但仍有 `X509TrustManager`/`checkServerTrusted` 的 JNI 路径（**已证**存在，不确定是否启用）。
   → 这种情况下托管 `ValidateCertificate` 可能根本没被调用（没有装 handler 时 Unity 走原生校验）。
   **判定**：`dump.cs` 里看 `CustomCertificateHandler` 是否被赋值给 `UnityWebRequest.certificateHandler`
   （需要 xref，dump.cs 看不到；用 Ghidra 或直接看 patch 后行为）。
2. **BestHTTP/BouncyCastle 第二条 TLS 栈**：metadata 里有 `BestHTTP.SecureProtocol` 整套 X509 类。
   若网关请求走 BestHTTP，证书校验在**托管 BouncyCastle** 里，patch Unity 的 CertificateHandler 无效。
   → 这时目标变成 BouncyCastle 的 `ValidateCertificateRequest`/`ServerCertificateValidationCallback`。
3. **真 pinning**（比对 SPKI/公钥哈希）：patch 点仍是校验函数，但要找到比对的常量。

### 6.3 还是不行时的最终替代

- 让客户端**不说 TLS**：需要同时满足"URL 是 http" + "连接指向我们"。两者都要能改到 `get_ApiUrl`/连接层，
  回到 §6.1-B 的难度。
- 或者**放弃 443/证书**，把游戏流量整体降到明文：`Hosts`/`LocalizeConfig` 已被证伪，不可行。

---

## 7. 速查表

| 项 | 值 |
|---|---|
| metadata 明文 magic | `AF 1B B1 FA`（LE 前 4 字节） |
| metadata 磁盘态 magic | `94 43 72 12` |
| 预期内存 size | `38,428,672`（=0x24A6000，38426024 向上取整） |
| metadata 版本字段 | offset 4，int32，预期 29 |
| 目标方法 | `CustomCertificateHandler.ValidateCertificate(byte[])` → bool |
| iFix 代理 | `<>iFixBaseProxy_ValidateCertificate`（metadata `0x1522f2`） |
| 补丁字节 | `20 00 80 52 C0 03 5F D6` |
| 替换目标 | `/data/app/~~*/com.RoamingStar.BlueArchive-*/lib/arm64/libil2cpp.so` |
| 备份 | `/data/local/tmp/libil2cpp.orig.so` |
| Il2CppDumper | v6.7.46 `Il2CppDumper-win-v6.7.46.zip`（self-contained） |

### 7.1 常见报错对照

| 现象 | 原因 | 处理 |
|---|---|---|
| `dd: /proc/PID/mem: I/O error` | 读到未映射地址 / 目标中途 unmap | `kill -STOP` 后重试；确认 skip 是映射起点 |
| `dd: Permission denied` | SELinux 拒绝 ptrace | `id` 确认 `u:r:ksu:s0`；先单页试读；必要时 `setenforce 0`（仅调试） |
| Il2CppDumper `Unsupported metadata version` | 版本判断失败 | 按 header int32 改副本第 4 字节试 27/28/29/31 |
| dump.cs 里没有 `CustomCertificateHandler` | 类被 strip / 在别的 assembly | 搜 `ValidateCertificate` 全部命中；或搜 `CertificateHandler` 子类 |
| 函数序言校验失败 | Offset 不是函数入口 | 用 `script.json` 的 Address，或按 §5.2 手工换算 |
| patch 后启动崩溃 | 写错位置/写了数据区 | 恢复备份；用 `Offset` 重新校验序言 |
| patch 后仍 alert | 校验不在托管层 / iFix 代理 | 见 §6.2 |

---

## 8. 结论（一句话版）

**dump 大概率可行**（il2cpp 读文件到 malloc，不 mmap；内存里应是 38.4 MB 匿名块 + `AF1BB1FA` 头），
**第一步**跑 §2.1 那条只读扫描；拿到 `HIT-DECRYPTED` 后按 §3 dump、§4 用 Il2CppDumper 定位、
§5 打 `mov w0,#1; ret`。
**但先做 §1 的 alert 判读**——如果是 `bad certificate`（链/ SAN 问题），上面这一切都不用做。
