# 15 · PEM 公钥与 pinning 判读（Q1–Q4）

> 输入：lead 的真机扫描结果 + 本地静态复核（`global-metadata.dat` / `libil2cpp.bin`）。
> 方法：直接读 metadata 字节、`metadata-strings.txt` 行号定位、`.rela.dyn` 全量解析（1,526,842 条）、
> Unity 官方文档（`CertificateHandler.ValidateCertificate`）。
> 标注：**已证**＝有字节/行号/官方文档；**推断**＝静态证据推出但未上机；**证据不足**＝明确写。

---

## 0. 三问三答（先看结论）

| 问题 | 结论 |
|---|---|
| **Q1** 两段 `BEGIN PUBLIC KEY` 是什么？ | **更可能是 (a) 网关握手 RSA 公钥**（客户端用它加密会话材料，服务端需握有对应私钥），**不是证书 pinning 的公钥**。但两者用一个 30 秒的比对就能定死：把可见 modulus 前缀和**官方叶证书的 SPKI** 比一下（§1.4）。 |
| **Q2** `access_denied(49)` 谁发的？ | **应用层**（pinning/自定义校验）发的，不是链不受信。依据是 RFC 语义：链不受信应发 `unknown_ca(48)`，格式问题发 `bad_certificate(42)`；`access_denied(49)` 的定义就是"证书有效但访问控制拒绝"。你们 CA 已装三处仍 49 → 说明拒绝发生在**校验回调**里，不是信任库。 |
| **Q3** 用官方公钥造一张我们能用的证书？ | **你的推理正确，这条路死了**。没有官方私钥 → 过不了 `CertificateVerify`（ECDHE）或拿不到 premaster（RSA kx），两种都握不了手。**唯一例外**：如果 pinning 只是"证书 blob 里包含官方证书"，可以把官方叶证书作为**第二条证书**塞进我们发的链里试一次（§3.3，零 patch，5 分钟）。 |
| **Q4** 拿 methodPointer 最可行的办法 | **全量内存扫描（不是只扫前 16KB）→ dump 明文 metadata → Il2CppDumper**。静态 CodeRegistration 路线我试了：能捞出 34 组代码指针数组（最大 499,123），但**拿不到 name→index 映射**，因为那张 `Type-MethodN` 表不是方法定义序（已证，§4.3）。 |

---

## 1. Q1：两段 PEM 是什么

### 1.1 实际位置与形态（已证）

| 项 | 值 |
|---|---|
| `-----BEGIN PUBLIC KEY-----` | **仅 1 处**，offset `0x178cc65` |
| `-----END PUBLIC KEY-----` | **仅 1 处**，offset `0x178cc23`（在 BEGIN **之前** 0x42 字节） |
| SPKI 头 `MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA` | **仅 1 处**，offset `0x178cc7b` |
| `OQIDAQAB`（RSA 指数 65537 的 DER 尾巴） | **仅 1 处**，offset `0x178cc15` |
| `-----BEGIN CERTIFICATE-----` | **0 处**（metadata / libunity / libil2cpp 全 0） |

实际布局（`0x178cc00` 起）：

```
…MZwsfgZzDNRe8bep2buS\nOQIDAQAB\n-----END PUBLIC KEY-----\n\x00
<二进制（形如 00 00 01 00 … 的计数表 / LZ token）>
-----BEGIN PUBLIC KEY-----\n
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAtgS2BXLKIrI8OFIZi3ge\n
sVQLQq8Epwb0XLSKAmF15r5CT4EF9xaKXOIYho5Iwljdk3FDuhqCwnZL9X
<二进制>
```

**关键观察**：一段 PEM 的**结尾**出现在另一段 PEM 的**开头之前**，且两段都在中间被二进制打断
→ 说明 metadata 的字符串字面量池是**分块/压缩存储**的（这也解释了为什么表结构对不上，见 14 号报告 §2）。
**结论：完整 PEM 无法从磁盘文件直接切出来**（只有 ~140 个 base64 字符可见，RSA-2048 SPKI 需要 ~450）。

### 1.2 邻接字符串（`metadata-strings.txt`，以 PEM 行 L586433 为锚）

紧跟在 PEM 之后的字面量是：

```
Count / Item[] / Keys / Values
Queued,Queued for redirection
DNS Lookup
TCP Connection
Proxy Negotiation
TLS Negotiation
Request Sent
Waiting (TTFB)
Headers
Loading from Cache / Writing to Cache
Response Received
Queued for Dispatch
Finished in
Callback
_placeholder
connect / disconnect / event / error / binaryevent / binaryack
1.0.7
-----BEGIN            ← 注意：带尾空格，是 PEM 解析器的前缀
-----END
BestHTTP.SecureProtocol.Org.BouncyCastle.Pkcs12.IgnoreUselessPassword
```

- 这段邻接是**UnityWebRequest 的计时阶段名**（DNS Lookup / TCP Connection / TLS Negotiation / Waiting TTFB…），
  说明这个字面量池属于**网络栈**，不是 `ServerInfoConnectionGroupData`（那个在 `0x129d13`，隔着 11 MB）。
- 同一段里出现 `-----BEGIN ` / `-----END `（带空格）→ 客户端**自己手写 PEM 解析**（找 BEGIN/END、base64 decode）。

### 1.3 语义线索（已证）

| 字符串 | 计数 | 归属 |
|---|---|---|
| `RsaEncrypt` | 13 | 游戏侧（网关/登录加密） |
| `Handshake` | 50 | 同上 |
| `GetTicket` | 21 | 排队取票（`Queuing_GetTicket` 族） |
| `LoginToServer` | 5 | 登录链路 |
| `FromXmlString` / `RSAParameters` | 1 / 2 | .NET RSA 导入 API |
| `Pinning` | 1 | **假阳性**：`thread_pinning_ref`（Mono 线程字段） |
| `CertificateHash` / `Thumbprint` / `GetPublicKey` | 3 / 1 / 1 | **全是 BouncyCastle / BCL**（`BestHTTP.SecureProtocol…Icao`、`X509FindType`） |

→ **没有任何"游戏自己的证书 pinning"命名证据**；而 `RsaEncrypt`/`Handshake`/`GetTicket` 是实打实的握手层。

### 1.4 决定性判据（30 秒，lead 手上就能做）

可见的 RSA modulus 前缀是：

```
tgS2BXLKIrI8OFIZi3gesVQLQq8Epwb0XLSKAmF15r5CT4EF9xaKXOIYho5Iwljdk3FDuhqCwnZL9X
```

把**官方叶证书**的公钥导出来对比：

```bash
openssl x509 -in official_leaf.pem -pubkey -noout | openssl pkey -pubin -outform DER | base64 -w0
# 看 base64 在固定头 MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA 之后的前 60~90 字符
```

| 比对结果 | 判定 | 后果 |
|---|---|---|
| **一致** | 这是**证书 pinning 的公钥**（官方证书的 SPKI） | 我们必须 patch 校验函数；且**不能**用"同公钥新证书"绕过（§3） |
| **不一致** | 这是**另一把 RSA 公钥**（网关握手 / SDK） | 它与证书无关；接自建网关时需要换掉它或服务端持对应私钥 |

> 文档先验支持"不一致"：`ba-protocol-full.md` §5 记载 Steam 版的 `global-metadata.dat` 里就有
> 「服务端 RSA 公钥，3 个 150 字节块」；国服用 PEM 形态（2 段）是同一机制的另一种编码（**推断**）。

### 1.5 顺带判掉 `0x4068C` 的 `MIIKLEK…`

- offset 263,820（`0x4068C`）落在 metadata 头部之后的**高熵加密区**（该区可打印率 0.37 ≈ 随机），
  且长度 72、无 `-----BEGIN/END`、无 base64 结构 → **随机数据false positive**，不是证书/公钥。可忽略。

---

## 2. Q2：`access_denied(49)` 是谁发的

### 2.1 协议语义（已证，RFC 5246 §7.2.2）

| alert | 含义 | 典型触发 |
|---|---|---|
| `unknown_ca(48)` | 链建不起来 / 根不在信任库 | **CA 没装对、链不全** |
| `bad_certificate(42)` | 证书格式/签名有问题 | 证书损坏 |
| `certificate_unknown(46)` | 其它证书问题 | 通用 |
| **`access_denied(49)`** | **"收到了有效证书，但应用访问控制拒绝"** | **应用层回调/pinning 拒绝** |

你们的实测组合是：**CA 装了三处 + 仍然是 49**。这排除了"链不受信"（那会是 48），
指向**应用层拒绝**：即 `CertificateHandler.ValidateCertificate` 返回 false，或某个自定义 verify 回调拒绝。
（**推断**，但协议语义 + CA 已装这两条一起，基本没有别的解释。）

### 2.2 Unity 侧的证据

Unity 官方文档（`Networking.CertificateHandler.ValidateCertificate`）：

> `protected bool ValidateCertificate(byte[] certificateData)`
> `certificateData`: **Certificate data in PEM or DER format. If certificate data contains multiple certificates, the first one is the leaf certificate.**
> 返回 `true` 接受，`false` 拒绝。

也就是说：
- 只要游戏给 `UnityWebRequest.certificateHandler` 赋了 `CustomCertificateHandler`，**默认校验被替换**，返回值就是最终裁决；
- 拒绝时由 Unity 的 TLS 层（libunity 的 mbedtls/UnityTLS + `CertificateHandlerProxy`）发 fatal alert。
- **具体是 49 还是 46 取决于 Unity 的映射实现**——我没有离线拿到 Unity 源码来证明这一条（**证据不足**）。
  但这不影响结论：49 的语义就是"应用层拒绝"，且 CA 已装仍拒绝，说明不是信任库问题。

### 2.3 还需排除的另一种可能

如果网关请求走的是 **BestHTTP + BouncyCastle**（metadata 里有整套 `BestHTTP.SecureProtocol`），
那 `CertificateHandler` 根本不参与，alert 由 BouncyCastle 的 TLS 栈发出。
**判别方法**：patch 掉 `ValidateCertificate`（或先把服务端换成一张"客户端一定信任"的证书）后看 alert 是否变化；
或者抓 ClientHello 的指纹/套件顺序，和 libunity 的 mbedtls 指纹对比。

---

## 3. Q3：用官方公钥造证书能不能行

### 3.1 你的推理正确（已证）

- X.509 允许"用我们的 CA 私钥给任意 SPKI 签一张证书"——**技术上能签**；
- 但 TLS 握手需要**证明持有该 SPKI 对应的私钥**：
  - ECDHE 套件：服务器要用证书私钥签 `CertificateVerify`（或 ServerKeyExchange）→ 没有官方私钥 → **签不出来**；
  - RSA 密钥交换套件：客户端用证书公钥加密 premaster → 只有官方私钥能解 → **解不开**。
- 所以"官方公钥 + 我们签的证书"**必然在握手阶段失败**，连 pinning 都走不到。**这条路不要想。**

### 3.2 但有一个便宜的"例外"值得试（零 patch，5 分钟）

Unity 文档说 `certificateData` **可能是多张证书、叶证书在前**。如果游戏的 pinning 实现是**朴素包含检查**
（例如把 blob 里的每张证书都 `new X509Certificate2(...)` 后比对指纹，或直接 `bytes.Contains(pinnedCert)`），
那么我们可以：

```
我们发的证书链 = [我们的叶证书(私钥我们有)] + [官方叶证书(公钥部分, 我们只有证书本身)]
```

- TLS 握手只用第一张（我们的叶）→ 我们有私钥 → 握手能成；
- 第二张是"多带的证书"，一般被 TLS 栈忽略，但会**出现在 `certificateData` 里** → 朴素的包含检查可能通过。

**判定**：把官方叶证书 `cat` 到我们 fullchain 的末尾，重跑一次；如果 alert 从 49 变成握手成功 → pinning 是"包含检查"，
直接用这条链即可，**完全不用 patch**。如果仍是 49 → 是 SPKI/指纹比对 → 只能 patch。

### 3.3 顺带说明

如果 §1.4 的比对结果是"PEM == 官方叶证书 SPKI"，那 pinning 键就是官方公钥，**§3.2 的链注入是唯一可能的非补丁绕法**；
如果 PEM 是另一把钥匙（网关握手），那它和证书无关，pinning（如果存在）的键还藏在别处（可能在代码里以 hex/byte[] 形式）。

---

## 4. Q4：拿 methodPointer 的最可行办法

### 4.1 先纠正上一轮的扫描盲区（已证）

你们的扫描是"129 个 ≥4 MB 的 **rw-p** 映射，每个只看**前 16 KB**，只找 `af1bb1fa`"。
三个盲区：

1. **只看前 16 KB**：如果 metadata 在某个堆 arena 里，偏移可能 >16 KB；
2. **只扫 rw-p**：如果是 file-backed 的 `r--p`（mmap 原文件就地解密），会被漏掉；
3. **只找 magic**：如果 header 没被解密（il2cpp 自己解析的是别的结构），magic 永远不出现，但**字符串堆是明文**。

### 4.2 全量扫描命令（推荐，几分钟）

```sh
pid=$(pidof com.RoamingStar.BlueArchive)
busybox awk 'function h2d(h,i,c,v){v=0;for(i=1;i<=length(h);i++){c=tolower(substr(h,i,1));v=v*16+index("0123456789abcdef",c)-1}return v}
{split($1,a,"-");s=h2d(a[1]);e=h2d(a[2]);printf "%.0f %.0f %s\n",s,e-s,$2}' /proc/$pid/maps |
while read s n perm; do
  case "$perm" in rw*|r-*) ;; *) continue;; esac
  sk=$(busybox awk -v s=$s 'BEGIN{printf "%.0f", s/4096}')
  ct=$(busybox awk -v n=$n 'BEGIN{printf "%.0f", n/4096}')
  busybox dd if=/proc/$pid/mem bs=4096 skip=$sk count=$ct 2>/dev/null > /data/local/tmp/seg.bin || continue
  busybox grep -abo $'\xaf\x1b\xb1\xfa' /data/local/tmp/seg.bin | head -1 | while read o _; do
      echo "MAGIC region=$s off=$o size=$n perm=$perm"; done
  busybox grep -abo 'ServerInfoConnectionGroupData' /data/local/tmp/seg.bin | head -1 | while read o _; do
      echo "NAME  region=$s off=$o size=$n perm=$perm"; done
done
```
- `NAME` 命中同样重要：**字符串堆在磁盘上就是明文**，它在内存里一定也在；只要找到它，就能反推 metadata 基址
  （通常 `region_start + off - 0x129d13`），再检查那附近是不是完整缓冲。
- 全量读内存大约 1–3 GB，几分钟；期间游戏不要退出。

### 4.3 静态 `Il2CppCodeRegistration` 路线：能做一半，做不了另一半（已证）

我实际做了：

1. 解析 `.rela.dyn`（**1,526,842 条**，其中 `R_AARCH64_RELATIVE` 指向代码段的有 **903,685** 条）；
2. 按 `r_offset` 连续性还原出**代码指针数组**（文件里这些槽是 0，真实值在重定位 addend 里，所以直接扫 `.data` 是扫不到的）：

| r_offset 起点 | 条数 |
|---|---|
| `0x0f3ccd30` | **499,123** |
| `0x0f2c4a10` | 73,879 |
| `0x0f354f50` | 56,877 |
| `0x0ffa5568` | 21,946 |
| `0x0ffddf98` | 16,002 |

→ **methodPointers 这一类数组本身是能静态拿到的**（不需要 metadata）。

**但是**：name → index 的映射仍然缺。我验证了上一轮那个"`Type-MethodN` 表 = 方法定义序"的猜想：

```
`Type-MethodN` 表共 39,915 条
GameMain 的方法出现在 idx = 3122 / 5415 / 6016 / 12139 / 12827 / 12837 / 12849 / 12865 / 12873 …
```

**同一个类的方法散落在 3122 到 12875 之间** → 该表**不是**方法定义序（更像按名字/哈希排序）。
所以它**不能**当 method index 用。静态路线到这一步就断了：**只有数组，没有"哪个下标是 ValidateCertificate"**。

### 4.4 xref 思路：不可行（已证）

`iFixBaseProxy_ValidateCertificate` 是 **metadata 里的方法名**（`0x1522f2`，XOR-0x66 区），
`libil2cpp.bin` 里对 `CustomCertificateHandler` / `ValidateCertificate` 的字符串引用是 **0**（上一轮已验证）。
代码访问方法名是**通过 metadata 索引**，不是通过 .rodata 里的 C 字符串 → **没有可用的 xref 锚点**。

### 4.5 结论

**最可行 = §4.2 全量内存扫描 → 找到明文 metadata → dump → Il2CppDumper（14 号报告 §3–§5 的流程不变）。**
如果全量扫描既没有 `MAGIC` 也没有 `NAME`，说明 metadata 是**流式解密、内存里没有整块明文**；
这时继续死磕 methodPointer 的性价比很低，应该改打：

- 证书侧：§3.2 的"链里塞官方证书"实验；
- 或 native 侧：找 `CertificateHandlerProxy` / `ValidateCertificateNative` 的调用点（在 libunity，但 libunity 有 hash pin，不能改文件——只能运行时改内存）。

---

## 5. 给 lead 的三个 5 分钟实验（按顺序）

1. **alert 明文**：`openssl s_server -accept 443 -cert fullchain.pem -key k.pem -www -state -msg` 收连接，
   看客户端 alert 的**名字**（`access denied` vs `unknown ca` vs `bad certificate`）。→ 直接回答 Q2 的"谁发的"。
2. **PEM 归属**：把 `official_leaf.pem` 的 SPKI base64 与 `tgS2BXLKIrI8OFIZi3ge…` 对比。→ 直接回答 Q1 的 (a)/(b)。
3. **链注入**：fullchain 末尾追加官方叶证书，重跑握手。→ 若通过，q2/q3/q4 全部不用做。

---

## 6. 附录

### 6.1 关键偏移

| 项 | 值 |
|---|---|
| `-----END PUBLIC KEY-----` | metadata `0x178cc23` |
| `-----BEGIN PUBLIC KEY-----` | metadata `0x178cc65` |
| SPKI 头（`MIIBIjAN…CgKCAQEA`） | `0x178cc7b` |
| 可见 modulus 前缀 | `tgS2BXLKIrI8OFIZi3gesVQLQq8Epwb0XLSKAmF15r5CT4EF9xaKXOIYho5Iwljdk3FDuhqCwnZL9X` |
| `MIIKLEK…`（随机，忽略） | `0x4068C` |
| `ServerInfoConnectionGroupData`（字符串堆锚点） | `0x129d13` |
| `CustomCertificateHandler`（裸名） | `0x1522b3`（XOR-0x66） |
| `<>iFixBaseProxy_ValidateCertificate` | `0x1522f2`（XOR-0x66） |
| `.rela.dyn` | 文件 `0x1a118`，1,526,842 条 |
| 代码指针数组（RELATIVE 还原） | `0xf3ccd30`(499,123) / `0xf2c4a10`(73,879) / `0xf354f50`(56,877) |

### 6.2 复算脚本（`report/_tmp/`）

| 脚本 | 作用 |
|---|---|
| `pem1.py` / `pem2.py` | PEM 位置/截断/邻居 |
| `idxtab.py` / `tbl_cert.py` | `Type-MethodN` 表条数与索引（证明非方法序） |
| `mptab.py` | 直接扫 `.data/.data.rel.ro` 找代码指针数组（0 命中 → 文件里是 0，值在重定位里） |
| `reloc_scan.py` | 解析 `.rela.dyn`，还原代码指针数组 |
