# 34 — 国服 packet（432 字节）二进制结构分析

> 分析对象：`POST /api/account/auth` multipart 中 `packet` 字段，经 `base64 → [u32 432][gzip] → gunzip` 得到的 **432 字节**
> 样本：`report\_tmp\packet_bin\cn_packet_432.bin`，sha256 `c8171a5db96552af7e0f98da80c39f13cc8cd817e5adeb73aa6613183f7efd5b`

---

## 一页结论

| 问题 | 结论 | 置信度 |
|---|---|---|
| **是不是结构化二进制（FlatBuffers / Protobuf / MessagePack / TLV）？** | **不是。** 四种格式全部实测排除 | **高（实测）** |
| **是不是加密/混淆？** | **是。** 400 字节段熵 7.4262 bits/byte，字节分布近乎均匀 | **高（实测）** |
| **是不是整段加密？** | **不是。** 末尾 **32 字节是明文 ASCII base64**，概率上不可能是密文巧合 | **高（实测）** |
| **最可能的布局** | **`[16 字节头][384 字节密文][32 字节 base64 token]`**，其中 384 = 12 × 32 | **中高（数值吻合，未经代码验证）** |
| **加密算法** | **Rijndael / AES，BlockSize = 256 bit（32 字节块）** —— 由客户端类名 `EncryptRJ256Api` / `FBENCRYPT_BLOCK_SIZE` 判定 | **中高（字符串证据）** |
| **加密密钥** | **尚未取得。** 客户端有 `generateKeyString` / `ENCRYPTION_KEY` / `StringCipher.passphrase`，无前置握手 ⇒ 密钥必须硬编码 | **已定位到类，未取到值** |
| **响应方向是否也加密？** | **很可能不需要。** 客户端有 `DecryptOrReturnOriginal`，会先当明文 JSON 试 | **中（类名推断，值得立即实测）** |

---

## 二、格式排除的实测过程

### 2.1 FlatBuffers —— 排除

```
offset 0  u32 LE root = 3385871913   （远超 432，非法）
offset 4  u32 LE = 807243770
offset 8  u32 LE = 897125354
```
FlatBuffers 的 root offset 必须 `< 缓冲区长度`。四个候选位置（0/4/8/12）**没有一个**落在合法范围。
无合法 vtable 前置 soffset。

⇒ **不是 FlatBuffers。**
（顺带说明：`libil2cpp.so` 里确实有 `FlatBuffers.dll` 字符串，metadata 里也有大量 `Finish*Buffer` / `GetRootAs*` 方法名，但那些是 **Excel 表数据** 的 generated class，与网络包无关。）

### 2.2 Protobuf —— 排除

严格 varint 走查（wire type 0/1/2/5，遇到 3/4 立即失败）：

```
FAILED: illegal wiretype 3 at 10
```

第 10 字节就出现非法 wire type，且没有任何字段能连续走完。

⇒ **不是 Protobuf。**

### 2.3 MessagePack —— 排除

```
首字节 = 0x29
fixmap?  False (0x80-0x8f)
fixarray? False (0x90-0x9f)
fixstr?  False (0xa0-0xbf)
```
0x29 不在 MessagePack 任何合法类型标记范围内。

⇒ **不是 MessagePack。**

### 2.4 压缩格式 —— 排除

对 432 字节全体与 400 字节段分别尝试 `zlib` / `raw-deflate` / `gzip` / `lzma` / `bz2`：**全部抛异常**。

⇒ 外层已经是 gzip 解压后的结果，内部**没有第二层标准压缩**。

### 2.5 熵与字节分布 —— 判定为加密

```
熵：
  全体 432          7.4270 bits/byte
  前 400（head）    7.4262 bits/byte
  前 128            6.5917 bits/byte
  末 32（tail）     4.2386 bits/byte

随机性统计（400 字节 head）：
  零字节数        2        （随机期望 1.6）
  不同字节值      199      （随机期望 ~205）
  16 字节块       25 个，**25 个全不重复**
  最高频字节      0xe5 出现 6 次（随机期望 1.56）

可打印字符占比    37.2%
```

熵 7.43、零字节数接近随机期望、最高频字节仅 6 次 —— 这是**密码学伪随机输出**的典型特征，不是任何序列化格式的自然产物。

**补充对照**：`protocol` 字段 = `AHTQLQI65FWJGGGK4KL5AEF57A`，是合法 base32 字符集（`A-Z2-7`），补 6 个 `=` 后 base32 解码得 **16 字节** `01e705c11ee96c9318cae297d010bdf8`。16 字节恰为一个 AES 块 —— 与「加密后的协议标识」一致。
**已实测排除**：该 16 字节不等于 `MD5/SHA1/SHA256("Account_Auth")` 等 21 个候选名 × 4 种哈希的任一截断，也不是这些名字的 XOR 密钥流（keystream 全随机，无重复模式）。

---

## 三、★ 关键结构：末尾 32 字节是明文

### 3.1 定位

从末尾向前扫描连续可打印 ASCII，得到**恰好 32 字节**、一直延续到文件最后一字节：

```
offset 400..431 (32 B)
ASCII : MjRlMmQ1MmNiZDg0Mzc2MjBjZTgwOTI3
```

### 3.2 解码

```
base64decode → "24e2d52cbd8437620ce80927"    （24 个 ASCII 十六进制字符）
```

### 3.3 为什么这是决定性证据

一个 32 字节的随机序列恰好全部落在 base64 字母表（64/256 个字符）内的概率是：

```
(64/256)^32 = 2^-64 ≈ 5.4e-20
```

**不可能是密文巧合。** 所以这 32 字节一定是**未加密的明文字段**。

⇒ `packet` 的 432 字节**不是整段加密**，而是 **「加密段 + 明文字段」的拼接**。

### 3.4 该 token 的上下文

```
offset 384..399 : 63 67 b7 38 7c f9 c8 66 41 09 4c ee 9c 85 73 3f   （密文尾部，随机）
offset 400..431 : 4d 6a 52 6c 4d 6d 51 31 4d 6d 4e 69 5a 44 67 30 ... （ASCII）
```

token 之前**没有长度前缀**（`0x20`=32 或 `0x18`=24 均未出现在 384..400 区间）。
token 的**原始值（`24e2d5...`）与 base64 形式在 head 中均 0 命中** —— 说明它不是 head 的摘要（已实测 `md5`/`sha256` 各种组合，无一匹配）。

**性质推测**：符合客户端类 `MX.Core.Crypto.ProtocolHashHelper` / `ProofTokenHelper` 的形态 —— 一个**明文附加的协议证明/校验 token**，不参与加密。标注为**推断**。

---

## 四、★ 客户端加密类已定位（这是本次最大的收获）

在 `global-metadata.dat`（38,426,024 B，头部加密但字符串区明文）里搜到完整的加密类簇。**以下全部是字符串实测，位置为文件偏移。**

### 4.1 `MX.Core.Crypto.PacketCryptManager` @ `0x25e36e`

```
000025e36e  PacketCryptManager
000025e381  requestBytes
000025e38e  EncryptRequest
000025e39d  PROTOCOL_HEAD_RESERVE      ← 包头部保留字段
000025e3b3  _cryptor
000025e3bc  _checker
```

⇒ **包加密的总入口**。`PROTOCOL_HEAD_RESERVE` 直接印证「包 = 头部 + 加密体」这种分段结构。

### 4.2 `MX.Core.Services.CryptAES` @ `0x259ba6` —— **算法在这里**

```
0000259ba6  CryptAES
0000259baf  generateKeyString
0000259bc1  byteSrc
0000259bc9  encrypt
0000259bd1  decrypt
0000259bd9  toEncryptData
0000259be7  EncryptRJ256Api
0000259bf7  sEncryptedString
0000259c08  DecryptRJ256Api
0000259c18  FBENCRYPT_BLOCK_SIZE      ← 关键
0000259c2d  cRandom
0000259c35  IVString
0000259c3e  CryptAESOrigin
0000259c4d  plainText
0000259c57  Encrypt
0000259c5f  cipherText
0000259c6a  Decrypt
0000259c72  _iv
0000259c76  EncryptStringToBytes_Aes
0000259c8f  DecryptStringFromBytes_Aes
```

**`RJ256` = Rijndael-256；`FBENCRYPT_BLOCK_SIZE` 是这套代码的标志性常量名。**

`FBENCRYPT_*` 前缀来自广为流传的 **FBEncryptorAES** C# 片段（韩国游戏圈常见），其固定参数为：

```
算法     : Rijndael
KeySize  : 256 bit
BlockSize: 256 bit   ← 即 FBENCRYPT_BLOCK_SIZE = 32 字节（不是标准 AES 的 16！）
Mode     : CBC
Padding  : Zeros
Key      : UTF8(keyString) 右补 0x00 到 32 字节
IV       : 通常为全 0，或由 IVString / cRandom 生成
```

⇒ **这套算法的密文长度必须是 32 的整数倍**（不是 16）。这一条是本次最有判别力的约束。

### 4.3 `MX.Core.Crypto.XORCryptor` + `ENCRYPTION_KEY` @ `0x25e4ac / 0x25e4b7`

```
000025e4ac  XORCryptor
000025e4b7  ENCRYPTION_KEY
```

⇒ 代码里**还有一条 XOR 加解密路径**（`PacketCryptManager._cryptor` 很可能就是它）。
**但已实测排除**：对 400 字节段做 key 长度 1..64 的重复 XOR，可打印率最高仅 **0.373**，没有一处出现 JSON/结构化特征。

### 4.4 `StringCipher` @ `0x25e3c5` —— 带 salt / passphrase 的对称加密

```
EncryptString / DecryptString
passphrase
EncryptStringWithPassphrase / DecryptStringWithPassphrase
cipherTextWithSalt / cipherTextWithSaltBytes
EncryptBytes / DecryptBytes
EncryptBytesWithPassphrase / DecryptBytesWithPassphrase
```

⇒ 这是常见的「`Rfc2898DeriveBytes` + AES + salt 前置」实现，**salt 会明文前置在密文里**。这条如果被用到，同样会造成「密文段首部是明文随机串」的形态。

### 4.5 其它相关类

```
MX.Core.Crypto.ProofToken / MD5ProofHash / ProofTokenHelper   （工作量证明/校验 token）
ProtocolHashHelper
MD5HashService: ToHexString / ComputeHash / ComputeHashAsString / ComputeDigest / ComputeDigest64 / ComputeHead
ProtocolHandler / RequestPacket / ResponsePacket / ParsePacket
MX.Core.Services.CryptAES（已列全）
Assets._MX.Program.Scripts.Network.{GameSessionManager, HttpGameSession, HttpGameMessage, NetworkSender, NetworkService}
```
以及 `MX.Core.Services.XXHashService`（`CalculateHash` / `CalculateHash64` / `Hash64`）。

---

## 五、★ 布局推断：`[16][384][32]`

依据两条硬约束联立：

1. **末尾 32 字节是明文**（§3，概率上已证）
2. **FBEncryptorAES 的密文长度必须是 32 的整数倍**（§4.2）

对 432 − 32 = **400** 字节做切分穷举：

| 头部切掉 | 剩余长度 | `% 32` | 32 字节块数 |
|---|---|---|---|
| 0 | 400 | **16** ❌ | 12.5 |
| **16** | **384** | **0** ✅ | **12** |
| 32 | 368 | 16 ❌ | 11.5 |

**唯一能让密文段 32 字节对齐的切法是 head = 16 字节。**

```
[   0 ..  16)  16 B   协议头保留（PROTOCOL_HEAD_RESERVE），内容 294ed0c9fa8f1d30ea0b79357e91071a
[  16 .. 400) 384 B   Rijndael-256 密文（12 × 32 字节块）
[ 400 .. 432)  32 B   明文 ASCII base64 token = base64("24e2d52cbd8437620ce80927")
```

**旁证**：
- head[16:400] 按 32 字节切成 12 块，**12 块全不重复**（符合 CBC/伪随机，排除 ECB 的结构性重复）
- 该 16 字节头部**不等于** token 或密文的 `md5` / `sha256[:16]`（已逐个实测）
- 若按标准 AES（16 字节块）切，head=0 时 400 也能对齐，但那样 `FBENCRYPT_BLOCK_SIZE=32` 就无法解释；**两条约束同时成立的只有 `[16][384][32]`**

> 置信度：**中高**。数值拟合很干净，但未经反编译验证 `PROTOCOL_HEAD_RESERVE` 的实际取值（可能不是 16）。

---

## 六、★★ 最有价值的一条：响应方向可能**不需要加密**

`MX.Core.Crypto` 之外，`HttpGameSession` 的响应解码路径（@ `0x21a4d2` 一带）是：

```
000021a4bc  encryptedBase64String
000021a4d2  DecodeResponse
000021a4e1  DecryptOrReturnOriginal      ← 关键
000021a4f9  HandleDecryptionError
000021a50f  IsSpecificErrorJson
```

**`DecryptOrReturnOriginal`** —— 方法名直译就是「解密，或者返回原文」。

它的语义只能是两种之一：

- **A**：先尝试解密，解不出来就返回原始字符串
- **B**：先判断是不是该解密的形态，不是就原样返回

**无论哪种，都意味着客户端能接受「未加密的响应体」作为一个合法分支。**

而 `IsSpecificErrorJson` 说明客户端还会**检查响应是不是某个特定的错误 JSON**——它必须先能把响应当 JSON 解析，才谈得上"检查"。这进一步支持「响应可以是明文 JSON」。

**⇒ 这意味着服务端可能根本不需要加密响应，直接回明文 JSON 即可。**

这一条与我们已知的 Shittim 行为完全吻合：Shittim 的 `WireDump` 里就有 `aes=False` 分支，并在 `aes=False` 时直接返回明文 JSON 信封：
```json
{"protocol":"Error","packet":"{\"Protocol\":-1,\"ErrorCode\":500,...}"}
```

**这是当前投入产出比最高的一枪：先不管请求怎么加密，直接把明文 JSON 响应喂回去，看客户端 `DecryptOrReturnOriginal` 是否照单全收。**

---

## 七、还没解决的问题（诚实标注）

| 问题 | 状态 |
|---|---|
| **加密密钥的具体值** | **没拿到。** 类名/方法名已定位（`generateKeyString` / `ENCRYPTION_KEY` / `passphrase`），但这些都是**字段/方法名**，值在 il2cpp 的 `.text` 或 metadata 的已加密头部里，本任务范围（纯离线、不反编译）取不到 |
| **`PROTOCOL_HEAD_RESERVE` 的实际数值** | 推断为 16（数值拟合），未经代码验证 |
| **head[0:16] 的含义** | 未知。不是 token/密文的 md5 或 sha256 前 16 字节；可能是校验/版本/计数器 |
| **`encode: True` 的精确语义** | 客户端 `HttpMessage.EncodeRequest` 字段存在，但具体是「是否加密」还是「是否 gzip」未确定 |
| **`protocol` 字段（base32 → 16 字节）如何生成** | 不是 21 个候选协议名的常见哈希；可能是带密钥的摘要或 AES-ECB 单块 |
| **是否真的用到 `CryptAES`（而非 `XORCryptor`）** | `CryptAES` 在 `global-metadata.dat` 里存在，且 `HttpGameMessage` 的调用串里出现 `MX-Core-Services-CryptAES-DecryptRJ256Api0` / `MX-Core-Services-CryptAES-decrypt0`，**说明它在网络路径上被调用** —— 这条支持 AES 路线 |

**一条特别有力的旁证**（来自 `0x3d910e` 的方法签名串表）：
```
MX-Core-Services-CryptAES-DecryptRJ256Api0
MX-Core-Services-CryptAES-decrypt0
Assets-_MX-Program-Scripts-Network-HttpGameMessage-get_Protocol0
Assets-_MX-Program-Scripts-Network-HttpGameSession-Send0
```
`CryptAES.DecryptRJ256Api` 和 `HttpGameMessage.get_Protocol` **并列出现在同一段方法签名表里** ⇒ **网络响应解密确实走 `CryptAES`**，不是 XOR。

---

## 八、给主 agent 的可执行建议（按性价比排序）

### ① 【立刻做，成本最低】先用**明文 JSON** 回一次响应
客户端有 `DecryptOrReturnOriginal`，Shittim 有 `aes=False` 分支。把 `/api/gateway` 的成功响应直接以明文 JSON 回给客户端，看它是否接受。
- 如果接受 ⇒ **响应方向完全不用加密**，问题瞬间少一半
- 如果不接受（报解密错）⇒ 至少确认了响应必须加密，再把力气投到密钥上

**这一步不需要破解任何密钥。**

### ② 【中等成本】如果请求方向必须解密，从 `FBEncryptorAES` 的标准实现 + 候选密钥字符串暴力试
`FBEncryptorAES` 的参数是**固定公开**的（Rijndael / 256-bit key / **256-bit block** / CBC / Zeros padding / key = UTF8 字符串右补 0 到 32 字节）。**唯一未知的是那个 key 字符串。**

因此可以写一个**离线爆破器**：
```
输入：432 字节样本
候选：从 global-metadata.dat / libil2cpp.so 抽出的所有 ASCII 字符串
      （长度 1..32，尤其关注出现频次低、不像普通单词的串）
流程：对每个候选 key 串，UTF8 编码后右补 0 到 32 字节
      → Rijndael-256-CBC 解密 head[16:400]
      → 判定：结果是否以 '{' 开头 / 是否为合法 UTF-8 JSON / 是否含 "Protocol"
判据：明文 JSON 是极强的自证 —— 试对了不可能看错
```
**这个爆破的搜索空间是「客户端里所有短字符串」，完全可枚举。** 这是把「逆向」变成「穷举」的关键一步。

### ③ 【如果 ② 失败】反编译 `MX.Core.Services.CryptAES.generateKeyString` 与 `PacketCryptManager.EncryptRequest`
注意障碍：**ACE 加密了 `libil2cpp.so` 约 26.2% 的 `.text` 页**（磁盘上非明文），但 **73.8% 的页是明文**。这两个方法有可能落在明文页里。
另外 `global-metadata.dat` 的**头部加密**导致 `fieldDefaultValues` / `typeDefinitions` 无法解析，所以**读不到字符串常量的偏移表**——但字符串区本身明文，可以按内容搜。

### ④ 【工具已就绪】解出来后怎么接
`srv-ops` 已验证：`Config/gateway_aes_sessions.json` 可手工注入 Key/IV，Shittim 启动时加载并当作「历史会话密钥」。
⇒ **一旦拿到 key/iv，写进这个文件，Shittim 就能自己解密国服的包，`.mx` 只做「gzip + XOR(0xD9)」的原样搬运。**

---

## 九、本次全部中间产物

| 文件 | 内容 |
|---|---|
| `report\_tmp\packet_bin\cn_packet_432.bin` | 432 字节原始样本 |
| `report\_tmp\packet_bin\dump1.py` | hex dump + 可打印串提取 |
| `report\_tmp\packet_bin\ana3.py` | 熵 / 零字节 / 16B 块重复 / XOR 扫描 / 压缩尝试 |
| `report\_tmp\packet_bin\fmt1.py` | Protobuf 走查 / FlatBuffers root / MessagePack 首字节 |
| `report\_tmp\packet_bin\proto2.py` | `protocol` 的哈希/XOR 密钥流检验 |
| `report\_tmp\packet_bin\find2.py` / `find3.py` | 客户端二进制字符串检索 |
| `report\_tmp\packet_bin\ctx2.py` / `ctx3.py` / `ctx4.py` | 加密类簇的字符串上下文 dump |
| `report\_tmp\packet_bin\layout.py` | 32 字节块切分假设检验 |
| `report\_tmp\packet_bin\hash2.py` | head[0:16] 与 token/密文的哈希比对 |
