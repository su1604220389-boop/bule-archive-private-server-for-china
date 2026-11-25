# 39 · metadata 字符串挖掘：`Account_Auth` 解析路径

> 输入（只读，未修改任何二进制）：
> `work\ba\audit\ba-work\x\assets\bin\Data\Managed\Metadata\global-metadata.dat`（38,426,024 B，sha256 `2352cb57…`）
> （`work\ba\bapatch\global-metadata_patched.dat` 只是换过 RSA 公钥，字符串区与本文件逐字节相同，本报告偏移对两者通用）
> 方法：纯离线静态分析 + 自写 Python 解析（脚本全在 `report\_tmp\meta\`）
> 日期：2026-11-14

---

## 0. 结论摘要（三句话）

1. **之前「metadata 里 0 条中文、0 条错误文案」的结论作废**。字面量有一层 **整串 XOR 0x20** 的混淆，
   它把空格变成 `\x00`、下划线变成 `\x7F`，于是 `strings` 只能看到 `pROTOCOL` / `NOT` / `SUPPORTED` 这种碎片，
   任何 `grep -i protocol` 都必然落空。解掉这层后，**`Protocol not supported` 与 `unknown response object` 都能实打实地读出来**。
2. 客户端 `Account_Auth` 响应的落点在 **`LoginTask.HandleAccountAuthResponseMessage`**（`0x0013FACF`），
   失败走 **`ErrorAccountAuth` → `OnLoginFail`**；响应 DTO 是 **`AccountAuthResponseMessage`**（`0x0012ABDF`），
   网络任务类是 **`AccountAuthNetworkTask`**（`0x0012ABFA`）。
3. 响应侧**只需要能解出一种形态**：`HttpGameMessage.DecryptOrReturnOriginal`（`0x0021A4E1`）名字即语义
   —— 解不出来就返回原文。所以「回明文响应」是客户端认可的合法分支；卡点不在加密，而在**解析后没有走到下一个协议**。

---

## 1. 查档

| 档案 | 已覆盖到什么 | 本报告的关系 |
|---|---|---|
| `report\24-state接口schema反推.md` | 已做过 metadata 字符串扫描，结论「中文 0 条、文案在本地化表」，脚本在 `_tmp\meta_re\` | **结论被本报告推翻一半**：它只扫了明文层；XOR 0x20 层没碰 |
| `report\34-国服packet二进制结构分析.md:264-292` | 已定位 `encryptedBase64String/DecodeResponse/DecryptOrReturnOriginal/HandleDecryptionError/IsSpecificErrorJson` 五连 | 本报告**补全了完整方法表**并给出类名 `HttpGameMessage` |
| `report\36-Account_Auth响应字段清单.md` | 服务端 24 字段全清单 | 本报告补**客户端侧** DTO 与失败分支 |
| `report\11-客户端静态逆向-网关与证书.md` §2 | 已指出 metadata「部分 XOR 混淆」、提到 0x66/0xB5 区 | 本报告给出**新的一层 0x20**（之前未识别） |
| `report\15-PEM公钥与pinning判读.md` | PEM 偏移、`CustomCertificateHandler` | 未冲突 |
| `report\02-注入链审计.md` | 指出静态解析 metadata 表不可行 | 本报告**绕开表结构**，用「区域 + 偏移」取证，不需要表头 |

**查档结论：这件事之前做过两次（24 号扫明文、34 号扫网络类），但都没解 XOR 0x20 层，因此都没找到文案。**

---

## 2. 为什么之前全部落空：XOR 0x20 层（本次核心发现）

### 2.1 现象

在 `0x0008E65A` 处，原始字节是：

```
70 52 4F 54 4F 43 4F 4C  00  4E 4F 54  00  53 55 50 50 4F 52 54 45 44
 p  R  O  T  O  C  O  L \0   N  O  T \0   S  U  P  P  O  R  T  E  D
```

整段 `^ 0x20` 之后：

```
50 72 6F 74 6F 63 6F 6C  20  6E 6F 74  20  73 75 70 70 6F 72 74 65 64
 P  r  o  t  o  c  o  l ' '  n  o  t ' '  s  u  p  p  o  r  t  e  d
```

**`Protocol not supported`**

### 2.2 规则

**混淆 = 整串 XOR 0x20（逐字节，不分字母）。** 副作用正是它难被发现的原因：

| 明文字符 | 密文 |
|---|---|
| `A`-`Z` / `a`-`z` | 大小写互换（看起来仍像字母，只是乱） |
| 空格 `0x20` | `0x00`（**字符串在这里被切断**） |
| 下划线 `0x5F` | `0x7F`(DEL)（**同样切断**） |

所以「按可打印 run 扫描 + 关键词 grep」一定漏：
`Protocol not supported` 在文件里是 3 段碎片 `pROTOCOL` / `NOT` / `SUPPORTED`，
`grep -i "protocol not supported"` 永远 0 命中，`grep -i protocol` 也 0 命中（因为大小写被翻了）。

### 2.3 另一层：XOR 0x01 / 0x0E

同区域还能观察到另外两种单字节 key：

| key | 密文 | 明文 | 偏移 |
|---|---|---|---|
| 0x01 | `EHSDBUMX` | `DIRECTLY` | `0x0008E5A3` |
| 0x01 | `B@MMHOF` | `CALLING` | `0x0008E5AC` |
| 0x01 | `qSNQDSUX` | `pROPERTY`（`Property` 的大小写被额外翻过） | `0x0008E55B` |
| 0x0E | `Mo``az` | `Cannot` | `0x00053A91` 一带 |

⇒ **同一文件里至少并存 3 种单字节 key**，且不同区间用不同 key。逐块自动判定见 §7 脚本 `s3_xor.py`。

### 2.4 影响面

* `_tmp\meta_re\s3_cjk.txt` 里那 163 条「CJK 噪声」和 4,298 个 CJK 序列**全部是随机字节碰巧解码**，
  真实中文文案在 XOR 层里（XOR 0x20 把 UTF-8 首字节 `0xE4-0xE9` 打到 `0xC4-0xC9`，3 字节 CJK 结构被破坏）。
  本报告**没有**找到成句中文（见 §8 诚实标注）。
* 之前所有「metadata 里没有 XXX」的否定结论，**只要关键词是英文单词，都需要重新验证**。

---

## 3. P0：可直接 grep 的日志字符串清单

> 说明：下表每一条都给出 **global-metadata.dat 内的真实文件偏移**，可用
> `python -c "d=open(F,'rb').read(); print(d[0x8E65A:0x8E680])"` 或十六进制查看器复核。
> 「原文」列是**解混淆后的明文**；括号里给出文件里的存储形态。

### 3.1 A 级：协议/响应语义直接相关（最值得先 grep）

| # | 明文 | 偏移 | 文件存储形态 | 推测归属 | 置信度（串存在 / 归属） |
|---|---|---|---|---|---|
| 1 | `Protocol not supported` | **`0x0008E65A`** | `pROTOCOL\0NOT\0SUPPORTED`（XOR 0x20） | 网络层协议名分派失败 | **高 / 低-中** ⚠️ 见 3.1.1 |
| 2 | `unknown response object` | **`0x000DFA5A`** | `UNKNOWN\0RESPONSE\0OBJECT`（XOR 0x20） | **响应对象无法映射到已知类型（疑似二进制包解析器）** | **高 / 中** ⚠️ 见 3.1.2 |
| 3 | `POPUP_NETWORK_ERROR_TITLE` | **`0x0008A25A`** | `popup\x7fnetwork\x7ferror\x7ftitle`（XOR 0x20） | 网络错误弹窗的**本地化 key**（不是正文） | **高 / 高**（是 key）；是否进 logcat：低 |
| 4 | `UNSUPPORTED` | **`0x000BBE54`** | XOR 0x0E | 协议/能力不支持 | 中 / 低 |
| 5 | `echelon TryResetSupport fail` | `0x000D169F` | XOR 0x20 | 与登录无关（战斗编队） | 中 / 中（排除用） |

#### 3.1.1 关于 #1 的**反证**（必须读）

`0x8E565`–`0x8E5BD` 紧邻的一串解出来是 `INDEXER` / `PROPERTY` / `CALLING` / `METHODS` / `MESSAGE` 这类
**反射/表达式相关关键字**，而不是网络语义。且 .NET 的 `SocketException` 对
`SocketError.ProtocolNotSupported` 的标准资源文案**正好就是 `Protocol not supported`**。

我做了针对性排除：同一编码下搜 `Connection\0refused` / `Network\0is\0unreachable` /
`Address\0already\0in\0use` / `No\0such\0host\0is\0known` —— **全部 NOT FOUND**，
说明这里没有成组的 SocketException 资源表，但**仍不能排除**它是. NET 框架层某处抛出的单条消息。

⇒ **给 lead 的用法**：这条只当 **"排除法探针"**，不当 **"必定出现的日志"**。
若它在 logcat 里出现，说明走到了「协议名不认识」；不出现**不能**推出任何结论。

#### 3.1.2 关于 #2 的**旁证**（这条更可疑）

`0xDFA5A` 的邻域里有 `UNSIGNED SHORT`（存储为 `UNSIGNEDsHORT` @`0xDFC43`，翻转后 = `UnsignedShort`）
—— 这是**二进制序列化写入器的类型名**。在一个出现 `UnsignedShort` 的区段里出现
`unknown response object`，最自然的解释是：**某个按类型标签分派的二进制读取器读到了不认识的对象**。

⇒ 如果这条成立，那么"客户端认不出我们的响应"可能不只是 JSON 键名问题，
而是**它根本没在按 JSON 解析这个 body**。这一点与 `NetworkService.ParseReceivedString/ParseProtocol/ParsePacketString`
（`0x219D60` / `0x219D1A` / `0x219D28`）三个方法名并列存在的事实并不矛盾 ——
"ParseProtocol" 也可能是**从二进制流里读协议号**，而不是从 JSON 里读 `"protocol"` 键。

**给 logcat 的第一批 grep 命令（大小写不敏感，因为混淆层可能与明文层混排）**：

```bash
adb logcat -v time | grep -iE "Protocol not supported|unknown response object|POPUP_NETWORK_ERROR_TITLE"
```

> ⚠️ **务实提醒**：这三条都只在这条路径真的被打到时才出现。
> 如果客户端是「解析成功但静默停住」，logcat 里**可能一个字符都没有** —— 这与你们观察到的现象一致。
> 本清单的价值是：**排除法**——如果这三条**一条都没出现**，说明客户端连「协议不认识」这一步都没走到，
> 问题更靠前（在 HTTP 响应体解码 / 信封形态），而不是在字段格式。

### 3.2 B 级：框架层错误文案（用于判定「异常被吞」的具体位置）

| 明文 | 偏移 | 来源 | 备注 |
|---|---|---|---|
| `The operation has timed out.` | `0x000A4671` | .NET `WebException` 标准文案 | 若出现 = 请求超时，不是解析失败 |
| `The server returned the filename ({0}) which is not valid.` | `0x000A5F5A` | .NET | 与本任务弱相关 |
| `Object cannot be null.` | `0x00084FBC` | .NET | 空引用被抛出时会带这句 |
| `No valid CRL for distribution point found.` | `0x000836BC` | BouncyCastle | 证书链 CRL 缺失（TLS 已通，应不出现） |
| `Division by zero error` | `0x00062ABC` | Unity | 噪声，列此以排除误判 |

### 3.3 C 级：日志标签（**不是**日志正文，但若客户端用 MX Logger 就会出现在 logcat 前缀里）

MX 框架的日志标签格式是 `{命名空间用-连接}-{类}-{方法}{重载序号}`，metadata 里共 **22,198 条**。与登录链直接相关的：

| 标签 | 偏移 |
|---|---|
| `LoginTask-ErrorAccountAuth0` | `0x0040B850` |
| `LoginTask-RequestAccountAuth0` | `0x0040B86C` |
| `LoginTask-HandleAccountAuthResponseMessage0` | `0x0040BED1` |
| `LoginTask-OnLoginFail0` | `0x0040B99A` |
| `LoginTask-ShowNicknamePopup0` | `0x0040B937` |
| `LoginTask-ErrorAccountCheckYostar0` | `0x0040B6DD` |
| `LoginTask-HandleQueuingGetTicketResponseMessage0` | `0x0040B81F` |
| `Assets-_MX-Program-Scripts-Network-HttpGameMessage-DecryptOrReturnOriginal0` | `0x004975F4` |
| `Assets-_MX-Program-Scripts-Network-HttpGameMessage-get_Protocol0` | 见 34 号报告 §七 |

```bash
adb logcat -v time | grep -E "LoginTask-|HttpGameMessage-|HttpGameSession-"
```

> **诚实标注**：**无法静态证明**这些标签在 release 包里真的会打印。它们是 metadata 里的字符串字面量，
> 语义上像「方法级日志/埋点标签」（同表里 `MX-Logic-*` 4,034 条是同类），但 release 包通常把 logger 关掉。
> 置信度：中低。

---

## 4. P1：`Account_Auth` 响应侧的 C# 结构

### 4.1 三个核心类型（偏移 = 类型名字符串在文件里的位置）

| 类型 | 偏移 | 说明 |
|---|---|---|
| `AccountAuthResponseMessage` | `0x0012ABDF` | 响应 DTO（**不是** `AccountAuthResponse`） |
| `AccountAuthNetworkTask` | `0x0012ABFA` | 网络任务；同簇有 `<ProcessSession>d__1`、`<ProcessSession>b__1_0` |
| `LoginTask` | `0x0013F654` | 登录状态机；`HandleAccountAuthResponseMessage` @`0x0013FACF` |

`AccountAuthNetworkTask` 的协程/回调邻域（同一张方法名表，紧邻 ⇒ 同属一类）：

```
0x0012ABDF  AccountAuthResponseMessage
0x0012ABFA  AccountAuthNetworkTask
0x0012AC0F  <ProcessSession>b__1_0
0x0012AC28  <ProcessSession>d__1
```

### 4.2 客户端 DTO 的字段（以 `get_X` / `set_X` / `<X>k__BackingField` 三件套为准）

| 字段 | getter 偏移 | backing field 偏移 |
|---|---|---|
| `AccountDB` | `0x0022AF71` | `0x0022B288` |
| `CurrentVersion` | `0x0022AE95` | `0x0022B1CC` |
| `TTSCdnUri` | `0x0022AF55` | `0x0022B26D` |
| `OptionDB` | `0x0022B14B` | `0x0022B3F7` |
| `StaticOpenConditions` | `0x002302B5` | `0x002303AD` |
| `ServerNotification` | `0x002301D3` | （见 `all_ascii.tsv`） |
| `MxToken` | `0x00257D93` | `0x00257DAB` |
| `encryptedUID`（小写开头，无 getter） | `0x001B576D` | 另有 `SetEncryptedUID` @`0x001B536E`、UI 标签 `UIPopup_System-SetEncryptedUID0` @`0x003D8945` |
| `AccountId` | `0x0011A4BC` 等多个同名（无法唯一归属） | — |

### 4.3 登录状态机（`LoginTask`）——**这就是「停住」的那台机器**

按文件顺序（`0x0013F654`–`0x0013FD9B`）还原出的成员，**顺序即代码里的声明顺序**：

```
LoginTask
  get_WaitingTicket / set_WaitingTicket
  ErrorQueuingGetTicket                    @0x0013F71B
  HandleQueuingGetTicketResponseMessage    @0x0013F731
  ErrorAccountPassCheck                    @0x0013F757
  ErrorAccountCheckYostar                  @0x0013F793
  AccountAuthStart                         @0x0013F7D3
  ErrorAccountCreate
  ErrorAccountNickname                     @0x0013F81A
  HandleAccountNicknameResponseMessage     @0x0013F82F
  ErrorAccountCallname                     @0x0013F854
  ErrorContentSaveDiscard                  @0x0013F886
  RequestQueuingGetTicket                  @0x0013F8DC
  RequestQueuingGetTicketRetry
  RequestAccountAuth                       @0x0013F942
  StartRequestRelayPackets                 @0x0013F981
  ShowNicknamePopup                        @0x0013F9B7
  IsLoginStarted / IsLoginFinished
  StartLoginWithAccountCheckYostar         @0x0013FA33
  RetryLoginWithAccountCheckYostar
  SetAccountNickname
  HandleAccountAuthResponseMessage         @0x0013FACF   ★
  OnLoginFinish                            @0x0013FAF0
  StartLoginWithAccountPassCheck           @0x0013FB04
  StartLogin                               @0x0013FB38
  ErrorAccountAuth                         @0x0013FB43   ★
  co_RelayPacketsProcess                   @0x0013FBB6
  OnLoginFail                              @0x0013FBCD   ★
  RequestAccountNickname
  LoginState / loginState                  @0x0013FDD3
```

**可推出的登录顺序**（与 `report\27-SDK登录协议调研.md` 的外部情报一致）：

```
Queuing_GetTicket → Account_PassCheck → Account_CheckYostar → Account_Auth
   → [HandleAccountAuthResponseMessage] → Account_Nickname(ShowNicknamePopup) → RelayPackets
```

⇒ 客户端在 `Account_Auth` 之后**本应**紧接着发 `Account_Nickname`（昵称设置）或走 `RelayPackets`。
它没发，说明卡在 `HandleAccountAuthResponseMessage` 内部（解析/取字段/校验），
**还没到 `OnLoginFinish`**（`OnLoginFinish` 之后才是拉数据）。

### 4.4 会话对象不是 `SessionKey`

`SessionKey` 这个词在 metadata 里**完全没有**（`get_SessionKey` / `SessionKey` 均 NOT FOUND）。
客户端侧对应的是 **`SessionDB` @`0x00257DCC`**，字段为：

```
MxToken          @0x00257D93（get_/set_/backing 齐全）
LastConnect      @0x00257DD6
ConnectionTime   @0x00257DF6
```

⇒ **重要**：我们回的 `"SessionKey": {"AccountServerId":2, "MxToken":"…"}` 这个**键名客户端根本不认识**。
Newtonsoft 默认忽略未知键，所以不会报错，但**也不会赋值** ——
`SessionDB.MxToken` 保持 null/空，后续任何需要 token 的协议都会在客户端侧直接失败。
**这是一条比「响应体格式」更值得优先验证的假设**（见 §6.3）。

---

## 5. P2：客户端自己的加密/哈希类（完整方法名清单）

### 5.1 `MX.Core.Services.CryptAES`（`0x00259BA6`–`0x00259C97`）

```
0x00259BA6  CryptAES
0x00259BAF  generateKeyString
0x00259BC1  byteSrc
0x00259BC9  encrypt
0x00259BD1  decrypt
0x00259BD9  toEncryptData
0x00259BE7  EncryptRJ256Api
0x00259BF7  sEncryptedString
0x00259C08  DecryptRJ256Api
0x00259C18  FBENCRYPT_BLOCK_SIZE      ← 32（Rijndael-256 的块长，非 AES 的 16）
0x00259C2D  cRandom
0x00259C35  IVString
0x00259C3E  CryptAESOrigin
0x00259C4D  plainText
0x00259C57  Encrypt
0x00259C5F  cipherText
0x00259C6A  Decrypt
0x00259C76  EncryptStringToBytes_Aes   ← 标准 AES（16 字节块）
0x00259C8F  DecryptStringFromBytes_Aes
```

⇒ 存在**两套并行实现**：`RJ256`（32 字节块，Flash/AS3 `FBEncryptorAES` 血统）与标准 `Aes`。
`FBENCRYPT_BLOCK_SIZE = 32` 是 `RJ256` 那一套的常量，**不是** .NET `Aes` 的块长。这解释了 34 号报告里 `[16][384][32]` 的切分拟合。

### 5.2 `PacketCryptManager`（`0x0025E36E`）——**只有加密方向**

```
0x0025E36E  PacketCryptManager
0x0025E381  requestBytes
0x0025E38E  EncryptRequest          ← 只有 EncryptRequest
0x0025E39D  PROTOCOL_HEAD_RESERVE   ← 34 号报告猜测的常量，实存
0x0025E3B3  _cryptor
0x0025E3BC  _checker
```

**没有 `DecryptResponse` / `Decrypt`。** ⇒ 请求加密与响应解密**不是同一个类**。
响应侧的解密只出现在 `HttpGameMessage.DecodeResponse` → `DecryptOrReturnOriginal`（§6.1）。

### 5.3 `StringCipher` / `XORCryptor` / `Base32` / `ProtocolHashHelper`

```
0x0025E3C5  StringCipher
0x0025E3D2  EncryptString
0x0025E3E0  DecryptString
0x0025E3EE  passphrase
0x0025E3F9  EncryptStringWithPassphrase
0x0025E415  cipherTextWithSalt
0x0025E428  DecryptStringWithPassphrase
0x0025E444  EncryptBytes / 0x0025E451 DecryptBytes
0x0025E45E  EncryptBytesWithPassphrase / 0x0025E491 DecryptBytesWithPassphrase

0x0025E4AC  XORCryptor
0x0025E4B7  ENCRYPTION_KEY        ← 字段名（值不在 metadata，见 §8）
0x0025E4C6  IProofHash
0x0025E4D1  MX.Core.Crypto.ProofToken        ← 命名空间
0x0025E4EB  MD5ProofHash
0x0025E4F8  LeftRotate
0x0025E503  Calculate
0x0025E50F  ProofTokenHelper
0x0025E520  GetHash
0x0025E528  question / 0x0025E531 SolveAsync / 0x0025E53C Solve / 0x0025E569 answer
0x0025E570  ProtocolHashHelper
0x0049691F  MX-Core-Crypto-ProofToken-ProtocolHashHelper-GetHash0   （日志/签名标签）
```

**`Base32` @`0x001552B5`（双向齐全）**：

```
0x001552B5  Base32
0x001552BC  CharToInt
0x001552C6  encoded
0x001552CE  FromBase32String     ← 解码
0x001552DF  padOutput
0x001552E9  ToBase32String       ← 编码
0x001552F8  _digits
0x00155300  _mask
0x00155306  _shift
```

`_digits/_mask/_shift/CharToInt/padOutput` 是标准 RFC 4648 实现的字段组合。

### 5.4 `HybridCryptor`（`0x0025E200` 一带，类名见 `MX-Core-Crypto-HybridCryptor-*` 标签）

```
00025E200  eKeyAndIV
0x0025E20E  LoadPublicKeyFromPem
0x0025E223  EncryptKeyAndIVWithRSA
0x0025E23A  encryptedKey / 0x0025E247 encryptedIV
0x0025E253  signedKey / 0x0025E25D signedIV
0x0025E266  VerifySignatureKeyAndIVWithRSA
0x0025E285  jsonBody
0x0025E28E  EncryptJsonWithRSA
0x0025E2A1  VerifySignatureKeyWithRSA
0x0025E2BB  MD5HashService
0x0025E2CA  ToHexString / ComputeHash / ComputeHashAsString / ComputeDigest / ComputeDigest64 / ComputeHead
0x0025E320  dbUrl / GenerateKey / ExtractDBFileNameFromURL / ExtractReservedWordFileNameFromURL
```

⇒ 这与已知的 `Queuing_GetCryptoKeys` 握手（RSA 包 AES key/IV + 签名）完全对得上，
也解释了 `GameSessionManager`（`0x00219E46` 一带）里的
`SetAesParameters / VerifyAndSetAesParameters / base64AesEncryptedKey / base64RsaSignedKey` 字段。

---

## 6. 定向任务四项（lead 插播）

### 6.1 `DecryptOrReturnOriginal` —— **有**

| 项 | 值 |
|---|---|
| 字符串偏移 | **`0x0021A4E1`** |
| 所属类 | **`HttpGameMessage`** @`0x0021A465`（`HttpMessage` 的子类，`0x0021A830`） |
| 命名空间 | `Assets/_MX/Program/Scripts/Network`（完整路径字面量见 `0x004975F4`） |
| 完整方法链 | `encryptedBase64String`@`0x21A4BC` → `DecodeResponse`@`0x21A4D2` → **`DecryptOrReturnOriginal`**@`0x21A4E1` → `HandleDecryptionError`@`0x21A4F9` → `IsSpecificErrorJson`@`0x21A50F` |

同族类（文件顺序，语义相关）：
`NetworkSender` / `NetworkService`（`ParseProtocol`@`0x219D1A`、`ParsePacketString`@`0x219D28`、`ParseReceivedString`@`0x219D60`、`ShowDefaultNetworkError`@`0x219D3A`）
`Http1Message` / `Http2Message` / `Http2DownloadMessage` / `HttpGameSession` / `GameSessionManager`

⇒ **结论**：响应解码是 `try-decrypt → 失败则用原文`。
**明文响应是客户端明确支持的合法分支**，这与 34 号报告 §六 的推断一致，现在有类名 + 方法名双重证据。

### 6.2 `"protocol"` / `"packet"` 作为 JSON key —— **未找到**

| 搜法 | 结果 |
|---|---|
| 原文层独立单词 `protocol` | **NOT FOUND** |
| XOR 0x20 层独立单词 `protocol` | 仅 `0x0025E39D`（`PROTOCOL_HEAD_RESERVE` 内部子串，非独立串） |
| XOR 0x01 / 0x0E 层 | **NOT FOUND** |
| 带引号 `"protocol"` / `"PROTOCOL"` | **NOT FOUND** |
| 独立单词 `packet` | 仅 `0x00115CF5` —— **邻域是 `Sync_EmblemPacket` / `SyncLogin` / `AttachmentDB`，是局部变量名，不是 JSON key** |

反过来，**属性名**都在：

| 属性 | 偏移 |
|---|---|
| `HttpMessage.<Protocol>k__BackingField` | `0x0021A89B` |
| `NetworkService.ParseProtocol` | `0x00219D1A` |
| `NetworkService.ParsePacketString` | `0x00219D28` |
| `NetworkService.ParseReceivedString` | `0x00219D60` |
| `NetworkService.ShowDefaultNetworkError` | `0x00219D3A` |
| `get_Protocol` | `0x001D7554` |
| `Http1Message.encode`（字段） | `0x0021A33E` |
| `HttpMessage.EncodeRequest` | `0x0021A98D` |

⇒ **判断（中等置信）**：客户端用 Newtonsoft 默认序列化，**JSON key 直接取属性名（PascalCase）**，
所以字符串表里本来就不该出现 `"protocol"` 这个小写字面量。
**这条对 lead 的假设是个反证**：把 `protocol` 的值改成 base32 是对的方向（见 6.3），
但**改 key 的大小写不是** —— key 大概率应该保持/改成 PascalCase 且大小写不是卡点。

> 未能排除的可能：该字面量在**第三种混淆层**（本报告只覆盖 0x00/0x01/0x0E/0x20 四种）。

### 6.3 BASE32 —— **编码/解码都齐全**

| 方向 | 方法 | 偏移 |
|---|---|---|
| 编码 | `Base32.ToBase32String` | `0x001552E9` |
| 解码 | `Base32.FromBase32String` | **`0x001552CE`** |
| 解码辅助 | `Base32.CharToInt` | `0x001552BC` |
| 标签 | `Base32-ToBase32String0/1` | `0x0040C20F` / `0x0040C226` |
| 标签 | `Base32-CharToInt0` | `0x0041CEEE` |
| 标签 | `Base32-FromBase32String0` | `0x0041CF00` |
| 协议哈希 | `ProtocolHashHelper` | `0x0025E570`（`MX.Core.Crypto.ProofToken` 命名空间下） |

⇒ **lead 的假设成立**：客户端**有** base32 解码能力，把 `protocol` 的值改成 base32 是可行的方向（E1 值得做）。

**但必须同时记住三条反证/限定**（诚实标注）：

1. **静态只能证「类存在」，不能证「响应路径调用它」**。没有函数体就没有调用图；
   `Base32` 类紧邻 `NCalcLexer`（`0x0015530D`），说明它是**通用工具类**，也可能是给别处用的。
2. `ProtocolHashHelper` 在 **`MX.Core.Crypto.ProofToken`** 命名空间，和 `ProofTokenHelper`（`GetHash/SolveAsync/Solve` = 工作量证明）挨着，
   **它更像 anti-bot 的 proof-token 哈希，而不是网关协议名哈希**。
   请求里那个 `BASE32(MD5(UTF-16LE(name)))` 的实际生成点，本次**没能定位到具体方法**。
3. 因此 E1 的正确实验形态是：**先只改 `protocol` 的值**（保持明文信封），观察客户端是否推进到下一协议；
   不要同时改 key 大小写，否则两个变量一起动，失败也分辨不出原因。

### 6.4 响应包装类字段 —— **部分存在，且有一处关键缺失**

见 §4.2。要点：

* 存在：`AccountDB` / `CurrentVersion` / `TTSCdnUri` / `OptionDB` / `StaticOpenConditions` / `ServerNotification` / `MxToken` / `encryptedUID`
* **不存在**：`SessionKey`、`get_EncryptedUID`、`AttendanceBookRewards`、`AccountRestrictionsDB`、
  `OptionDB` 之外的 `*RepurchasableMonthly*` / `*AttendanceHistoryDBs*` / `*WeeklyProduct*` 等（全部 NOT FOUND）

⇒ 我们按 `report\36` 的 24 键名逐条抽查，**客户端侧只有 8 条能找到对应属性**；
以下键名在整个 metadata 里（含 4 种 XOR 层）**全部 0 命中**：
`SessionKey`、`AttendanceBookRewards`、`AttendanceHistoryDBs`、`RepurchasableMonthly*`、
`MonthlyProductParcel/Mail`、`BiweeklyProduct*`、`WeeklyProduct*`、`IssueAlertInfos`、
`AccountRestrictionsDB`、`NewlyAddedShopCashIds`、`AccountLimitedFlashSaleDBs`。
（**注意**：0 命中只能说明「客户端不用这个键名」，不能说明「客户端不需要这份数据」——它可能挂在别的类上，
例如 `AttendanceBookReward` 这个**单数**类名确实存在 @`0x002A7A5D`。）

Newtonsoft 会静默忽略不认识的键，所以多发字段本身不会报错。
真正可能致命的是 **`SessionKey`**：客户端没有这个属性，`MxToken` 是 `SessionDB.MxToken`（`0x00257DCC`）的字段。

---

## 7. P3：协议名完整枚举

从 `0x0022D902` 起的 NUL 分隔连续块抽出，**共 431 条**（完整清单：`report\_tmp\meta\protocols.txt`）。
锚点与前后关系可验证：`Common_Cheat` → `System_Version` → `Session_Info` → `NetworkTime_Sync` → `NetworkTime_SyncReply` → … → `Shop_ConfirmTutorialGacha`（末条 @`0x0022FE3C`）。

前 28 条（`Account_*` 全组）：

```
0x0022D902  Common_Cheat
0x0022D90F  System_Version
0x0022D91E  Session_Info
0x0022D92B  NetworkTime_Sync
0x0022D93C  NetworkTime_SyncReply
0x0022D952  Audit_GachaStatistics
0x0022D968  Account_Create
0x0022D977  Account_Nickname
0x0022D988  Account_Auth          ← 我们的卡点
0x0022D995  Account_CurrencySync
0x0022D9AA  Account_SetRepresentCharacterAndComment
0x0022D9CD  Account_GetTutorial
0x0022D9E0  Account_SetTutorial
0x0022D9F3  Account_PassCheck
0x0022DA07  Account_VerifyForYostar
0x0022DA1F  Account_CheckYostar
0x0022DA36  Account_CallName
0x0022DA48  Account_BirthDay
0x0022DA5A  Account_Auth2
0x0022DA6B  Account_LinkReward
0x0022DA80  Account_ReportXignCodeCheater
0x0022DA9F  Account_DismissRepurchasablePopup
0x0022DAC1  Account_InvalidateToken
0x0022DAD9  Account_LoginSync
0x0022DAEC  Account_Reset
0x0022DAFC  Account_RequestBirthdayMail
0x0022DB17  Account_CheckAccountLevelReward
0x0022DB37  Account_ReceiveAccountLevelReward
```

**对卡点的意义**：`Account_Auth` 之后客户端**本应**发的是
`Account_Nickname`（若昵称为空）→ 或直接 `Account_LoginSync`（拉大厅）。
`LoginTask` 里的 `ShowNicknamePopup` / `RequestAccountNickname` 正好对应前者（§4.3）。
**所以「客户端不发第二个请求」= 没走到 `OnLoginFinish`**，问题在 `HandleAccountAuthResponseMessage` 内部。

### 附加：客户端认识的错误码枚举（`WebAPIErrorCode`，229 条）

偏移 `0x0023EF73`（XOR 0x20 层，整段 `^0x20` 后按空格切分）。完整清单：`report\_tmp\meta\errorcodes.txt`。
与我们卡点最相关的：

```
InvalidPacket            InvalidProtocol          InvalidSession
InvalidVersion           InvalidToken             InternalServerError
DBError                  FailedToLockAccount      AccountAuthEmptyDevId
AccountAuthNotCreated    AccountCreateFail        AccountNotFound
AccountNicknameEmptyString
```

⇒ 客户端**有 `InvalidProtocol` / `InvalidPacket` 这两个错误码**。如果我们回的 `protocol` 值认不出，
它**完全有可能**走这个枚举而不是抛异常弹窗 —— 这也解释了「不弹窗、静默停住」。

---

## 8. 诚实标注：哪些是确证的、哪些是猜的

| 结论 | 状态 |
|---|---|
| XOR 0x20 层存在，`Protocol not supported` / `unknown response object` 可在指定偏移字节级验证 | **确证**（直接读文件字节） |
| 这两条文案**归属游戏网络层**（而不是 .NET 框架/序列化库） | **未证实**，各有反证（见 §3.1.1 / §3.1.2）。只当排除法探针用 |
| 文件内并存 XOR 0x01 / 0x0E 层 | **确证**（`EHSDBUMX`→`DIRECTLY`、`Mo``az`→`Cannot`） |
| `DecryptOrReturnOriginal` 属于 `HttpGameMessage`，且与 `DecodeResponse/HandleDecryptionError/IsSpecificErrorJson` 同簇 | **确证**（字符串表邻接 + 完整脚本路径字样） |
| `LoginTask` 的成员清单与登录顺序 | **确证**（同一张方法名表内连续，顺序即声明顺序） |
| 431 条协议名、229 条错误码 | **确证**（NUL/空格分隔连续块，边界可复查） |
| 客户端 JSON key 用属性名（PascalCase） | **推断（中）** —— 依据是「小写字面量 0 命中 + 属性名齐全」，但**没有函数体证据**，且不能排除还有第三种混淆层 |
| `Base32.FromBase32String` 被响应路径调用 | **未证实** —— 只知道类存在且在通用工具区 |
| `ProtocolHashHelper` 就是网关协议名哈希 | **未证实，甚至有反证**（它在 `ProofToken` 命名空间，像 anti-bot PoW） |
| `LoginTask-*` / `MX-*` 标签会进 logcat | **未证实**（release 包可能关日志） |
| metadata 里**没有**成句中文文案 | **本报告确认**：XOR 0x20 会把 UTF-8 中文字节打散，本次未专门做「中文 XOR 还原」；**不能排除**其他 key 下藏着中文 |
| `SessionKey` 这个名字客户端不认识 | **确证**（全文件 0 命中，含 4 种 key 层） |
| `SessionDB.MxToken` 是客户端真正的 token 落点 | **推断（中）** —— 类名 + 字段名齐全，但没证据说明它从响应哪个键赋值 |

---

## 9. 复现命令

```powershell
# 环境：本机 python 无 numpy，需用运行时自带的
$PY = "C:\Users\su\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
cd report\_tmp\meta

# 1) 断言 P0 第一条：0x8E65A 处 ^0x20 得到 "Protocol not supported"
& $PY -c "d=open(r'..\..\..\work\ba\audit\ba-work\x\assets\bin\Data\Managed\Metadata\global-metadata.dat','rb').read(); print(repr(d[0x8E65A:0x8E67A])); print(bytes(b^0x20 for b in d[0x8E65A:0x8E67A]))"

# 2) 全文件 ^0x20 还原隐藏文案
& $PY .\s11_xor20_sentences.py

# 3) 锚点邻域（类/方法名归属）
& $PY .\s2_ctx.py --anchor DecryptOrReturnOriginal --anchor AccountAuthResponseMessage --window 3000

# 4) 协议名完整枚举
& $PY .\s9_protocols.py

# 5) 错误码枚举
& $PY .\s10_enums.py --lo 0x23E800 --hi 0x23F800 --out s10_resultcodes.txt
```

---

## 10. 脚本与产物清单（全部在 `report\_tmp\meta\`）

| 文件 | 作用 |
|---|---|
| `s1_msgscan.py` → `all_ascii.tsv`(518,178) / `sentences.tsv`(6,842) / `fmtstr.tsv`(10) | 带**真实文件偏移**的可打印串扫描（原文层）。这是本次能给出偏移的基础 |
| `s2_ctx.py` → `s2_ctx_*.txt` | 锚点邻域 dump（判断某串属于哪个类） |
| `s3_xor.py` → `keymap.txt` / `metadata.deobf.bin` | 分块自动判定单字节 XOR key（alpha4 + goodspace 双指标，避免 NUL 填充骗分） |
| `s4_cjk_xor.py` → `cjk_key_scores.txt` | 255 key 全扫判「中文是否被隐藏」 |
| `s5_multikey.py` → `multikey_hits.tsv`(4,723) | 多 key 解码 + 关键词命中 |
| `s6_jsonkeys.py` / `s7_standalone.py` | JSON key 存在性判定（带引号/独立单词/多层 key） |
| `s8_region.py` | 区域转储 + 大小写翻转归一化（**最好用的一个**） |
| `s9_protocols.py` → `protocols.txt`(431) | 协议名完整枚举 |
| `s10_enums.py` → `s10_resultcodes.txt` / `errorcodes.txt`(229) | 从翻转层还原 CamelCase 枚举成员 |
| `s11_xor20_sentences.py` → `xor20_sentences.tsv`(1,856) | **解码 XOR 0x20 层还原整句文案**（`Protocol not supported` 就是这样找到的） |

---

## 11. 给 lead 的下一步建议（按性价比）

1. **先做零成本的验证**：把响应里的 `SessionKey` 换成客户端认识的键 ——
   直接试 `MxToken` 平铺、或 `{"SessionDB":{"MxToken":"…"}}`。理由：`SessionKey` 全文件 0 命中（§4.4），
   而 `SessionDB.MxToken` 有完整三件套。**这条比 E1（base32）成本更低、可能性更大**。
2. **E1 只改一个变量**：`protocol` 的值换成 `BASE32(MD5(UTF-16LE("Account_Auth")))`，key 大小写不动（§6.2/§6.3）。
3. **logcat 用 3.1 的三条 grep 做排除法**：全不出现 ⇒ 问题在 HTTP 层而非字段层。
4. 若仍无进展，下一步该做的不是继续猜字段，而是**动态确认 `HandleAccountAuthResponseMessage` 是否被调用**
   （Frida hook 该方法，或用 `il2cpp_class_from_name("AccountAuthResponseMessage")` 是否非空来判断 DTO 是否被反序列化成功）。
