# 37 — 国服网关 AES 离线破解（432 字节内层）

> 目标：`POST /api/account/auth`（Host `gsqc-api.bluearchive-cn.com`）`packet` 字段解包后的 432 字节
> 样本 A：sha256 `9846b394b4ff120b32de0b66587286cb3e7c3c3931fcf36c86eb317a953ae68e`
> 样本 B：sha256 `c8171a5db96552af7e0f98da80c39f13cc8cd817e5adeb73aa6613183f7efd5b`（本机 `sample_432.bin`）
> 约束：纯离线、只用标准库 + `aes_pure.py`、未改手机/未联网抓包

---

## 0. 一句话结论

**没中。**

在本机可枚举的范围内（**590,858 条客户端字符串 × 15 类 KDF × 16 种布局/模式 = 约 1.5 亿次块级判据**，外加
**4,690 万个「裸字节窗口密钥」试验**），**没有任何一个候选能让 432 字节内层解出 JSON 或已知明文**
（`314816420` / `61de1d1b…` / `"Protocol"` / `"DevId"` 全部一次都没出现）。

**但本次把一个关键问题钉死了：块大小是 16 字节，不是 32 字节。**
依据是 FBEncryptor 原始头文件（`FBENCRYPT_BLOCK_SIZE = kCCBlockSizeAES128 = 16`），
`RJ256` 指的是 **256 位密钥（AES-256）**，不是 256 位块。**报告 34 的「FBEncryptor = 32 字节块」是错的。**

同时把「432 字节到底是什么」从推断升级为**长度上唯一自洽的布局**：

```
[0 .. 16)     16 B   随机 IV（每包不同，实测 A/B 第 0 字节即不同）
[16 .. 400)  384 B   AES-256-CBC 密文 = 24 × 16 B
[400 .. 432)  32 B   明文 ASCII：base64(24 个十六进制字符 = 12 字节)
```

---

## 1. 本轮新增的实测结论

### 1.1 protocol 字段（复算一致）

```
base32( MD5( UTF-16LE("Account_Auth") ) ) 去 '=' 填充
= AHTQLQI65FWJGGGK4KL5AEF57A   ✓ 与抓包完全一致
```

顺带：`base32` 解码回来是 16 字节 `01e705c11ee96c9318cae297d010bdf8`，
**不是**报告 32 里说的「19 字节」——那次是按 base64 解错的。

### 1.2 尾部 32 字节

```
样本 B：base64decode("MjRlMmQ1MmNiZDg0Mzc2MjBjZTgwOTI3") = "24e2d52cbd8437620ce80927"
样本 A：base64decode("Y2M4YjI2YzNmY2YzZjFiNThkZWYwMTM0") = "cc8b26c3fcf3f1b58def0134"
```

两串都是 **24 个 ASCII 十六进制字符 = 12 字节 = 96 bit**。
32 字节内容全部落在 base64 字母表内的概率是 2^-64，所以这 32 字节**一定是明文**，不是密文巧合。

它不是 head / ct 的 MD5、SHA1、SHA256（hex 前 24 / 后 24 / base64 前 32 全试过，0 命中），
也不是当前时间戳（前 4 字节按 BE/LE 解都落在 1989/1993 年），
目前只能定性为「每包不同的 96 bit 随机/派生 token」。

### 1.3 明文长度的独立佐证

`report\_tmp\mx_crypto\plaintext_account_auth.json`（探针构造的请求体片段）长 **373 字节**。

```
373  --PKCS7-->  384   ✓  正好等于 [16:400) 的 384 字节
```

而如果 JSON 里再带 `"Protocol":1002`（16 字节），总长 389 → 要补到 400 字节，
那就得是 `[CT 400][token 32]`（无 IV）——但那样**首块明文完全固定**，
A/B 两份样本的第 0 个密文字节就不该不同。实测第 0 字节就不同 ⇒ **必须有随机 IV** ⇒ 明文 ≤ 384。
**两条独立证据同时收敛到 `[IV16][CT384][token32]`。**

### 1.4 `Hash` 字段自证协议号

```
4303557230595 = (1002 << 32) | 0x0C000003
```

1002 = `Account_Auth`。这与 SDK 的 `Hash = (protocol << 32) | counter` 构造完全一致，
说明明文里一定含 `"Hash":4303557230595`（22 字节已知明文），协议号也确认是 1002。

---

## 2. ★ 块大小判定：16 字节（推翻报告 34）

报告 34 断言「FBEncryptorAES 的 BlockSize = 256 bit、密文必须是 32 的倍数」。**这个断言是错的。**

FBEncryptor 原始头文件（`dev5tec/FBEncryptor/FBEncryptorAES.h`，iOS 上被大量 C# 项目移植的那份，
见 [github.com/dev5tec/FBEncryptor](https://github.com/dev5tec/FBEncryptor/blob/master/FBEncryptorAES.h)）：

```c
#define FBENCRYPT_ALGORITHM     kCCAlgorithmAES128
#define FBENCRYPT_BLOCK_SIZE    kCCBlockSizeAES128     // = 16 字节
#define FBENCRYPT_KEY_SIZE      kCCKeySizeAES256       // = 32 字节
```

- `FBENCRYPT_BLOCK_SIZE` = **16**，CBC + PKCS7 + 16 字节 IV
- `RJ256` / `KeySize = 256` 说的是**密钥长度**，不是块长
- 真正 32 字节块的是另一份 StackOverflow 的 `RijndaelManaged{BlockSize=256}` 片段，
  它和 `FBENCRYPT_BLOCK_SIZE` 这个常量名不是一套东西；报告 34 把两者混在了一起

**长度上也支持 16：**

| 假设 | 密文段 | 是否 32 对齐 | 是否有 32B IV 位置 |
|---|---|---|---|
| 16B 块 + `[IV16][CT384][tok32]` | 384 | 12×32 ✅ | IV=16 ✅ 自洽 |
| 32B 块 + `[head16][CT384][tok32]` | 384 | 12×32 ✅ | **IV 必须 32B，16B 头放不下** ❌ |

32 字节块要成立，必须假设「16 字节头是 salt、IV 是代码里写死的常量」。
但 IV 固定就意味着**首块密文固定**；A/B 首字节不同 ⇒ 要么 IV 随机（那 16 字节头必须正好是 IV ⇒ 块只能是 16），
要么明文首块不同（而明文首块 `{"DevId":"314816420"` 对同一账号是固定的）。
**⇒ 16 字节块是唯一不需要额外假设的解释。**

此外仍按 32 字节块（自写 Rijndael Nb=8，已用 FIPS-197 Nb=4 向量校验 + Nb=8 往返自测）
把 590,858 条 × 5 类 KDF 全跑了一遍：**0 命中**，反向印证。

---

## 3. 试过的组合矩阵（全部 0 命中）

### 3.1 字符串字典（590,858 条）

来源：`global-metadata.dat`(36.6 MB) + `libil2cpp.bin`(258 MB) 的全部可打印串（4–64 字符、不含空格）。
覆盖 `CryptAES` / `PacketCryptManager` / `StringCipher` / `XORCryptor` / `AESKeyHolder` / `BlueArchive` / `Yostar` / `MX` 等全部关键词串。

| # | KDF | 布局 / 模式 | 块级试验 | 耗时 | 结果 |
|---|---|---|---|---|---|
| 1 | UTF8 补零→16/24/32、MD5、SHA256、MD5-hex、SHA1[:16]、base64 解码 | cbc，ct 起点 0/16/32，IV=head/0 | ~31 M | 47.6 s | **0** |
| 2 | PBKDF2-HMAC-SHA1，1000 轮，salt=body[0:16] | cbc，ct 起点 0/16/32/48/64 | ~7 M | 48.8 s | **0** |
| 3 | PBKDF2-HMAC-SHA1，1000 轮，salt=body[0:32] | 同上 | ~7 M | 49.8 s | **0** |
| 4 | PBKDF2-HMAC-SHA256，1000 轮，salt=body[0:16] | 同上 | ~7 M | 50.2 s | **0** |
| 5 | PBKDF2-HMAC-SHA1，1 轮（=HMAC 直出） | 同上 | ~7 M | 50.6 s | **0** |
| 6 | Rijndael-**256**（32B 块）：补零 32/24、SHA256、MD5-hex、SHA256-hex | `[head16][ct384]`，IV=0 | 3 M | 50.9 s | **0** |
| 7 | 8 类 KDF（含 hex 解码 / UTF-16LE / SHA256-hex） | cbc **block0 + block1**、ECB、CFB、OFB、CTR | ~71 M | 162.2 s | **0** |
| 8 | 截断 32/16、UTF-16LE 补零/截断、SHA256-hex、MD5-hex 大写 | cbc，3 种 ct 起点 | ~18 M | 50.0 s | **0** |
| 9 | RC4（raw/MD5/SHA256/SHA1/MD5-hex）、重复 XOR | 流密码，ct 起点 0/16/32 | ~9 M | 见 §3.2 | 粗筛噪声，严格复核见 §3.2 |

**布局覆盖清单**（每个 KDF 都在这些上跑）：

```
iv = body[0:16] / body[16:32] / 全零 / body[32:48]
ct 段 = [0:400) [16:400) [32:400) [48:400) [64:400)
模式 = CBC(PKCS7 校验) / ECB / CFB-128 / OFB / CTR
```

### 3.2 RC4 / XOR

- 590,858 × 5 类密钥流（raw / MD5 / SHA256 / SHA1 / MD5-hex）× 3 个 ct 起点，
  宽松 block0 粗筛出 **779 条低置信命中**，抽查全是随机噪声。
- 随后做**严格复核**：全 400 字节解密 + 必须出现已知明文，**590,858 条 × 5 类 × 3 起点，21.7 秒，0 命中**。
- 报告 34 已排除过「单字节 XOR 0xD9」；本轮额外排除了「字符串/MD5/SHA256 作重复 XOR 密钥流」。

### 3.3 裸字节窗口（覆盖「key 是 C# byte[] 常量」的情况）

这是本轮唯一的新思路：**如果 key 是 `new byte[]{...}`，它不会以字符串出现，但一定是文件里连续的一段字节。**
于是把目标文件的**每一个 4 字节对齐窗口**当作裸 AES key 直接试（16B 和 32B 两种），
每个窗口试 3 种布局（ct 起点 0/16/32），命中后再全量解密复核。

| 目标 | 窗口数 | 粗筛命中 | 全量复核 | 耗时 |
|---|---|---|---|---|
| `global-metadata.dat` 全文件，32B 窗口 | 9,606,506 | 30 | **0** | 121.9 s |
| `global-metadata.dat` 全文件，16B 窗口 | 9,606,506 | 33 | **0** | 91.4 s |
| `libil2cpp.bin` 只读段 `.rodata`（0–94 MB），32B | 23,507,349 | 59 | **0** | 298.9 s |
| `libil2cpp.bin` 可写段 `.data`（24 MB），32B | 4,234,302 | 4 | **0** | 54.5 s |

粗筛命中率与随机期望一致（`p0` 全可打印 ≈ 1e-6），全部经全量解密 + 已知明文判定为假阳性。

### 3.4 上下文派生密钥（369 个）

用协议哈希、`protocol` base32 串、uid、token、DeviceUniqueId、域名、包名、
以及它们的 MD5/SHA256/拼接/PBKDF2 组合直接当 key：**0**。

---

## 4. 为什么「没中」是可信的（工具没坏）

**阳性对照**（`selftest_crack.py` / `selftest2.py`）：
用 `SHA256("TestKey_CN")` 造一个 432 字节样本（`[IV16][CT384][token32]`，JSON 373 字节），
爆破器在 **0.2 秒**内命中，并完整还原出含 uid 与 token 的 JSON。

**判据强度**：
- block0 判据 = `p0[0]=='{' 且 16 字节里 ≥14 可打印`，随机命中率 ~1e-7
- 全量复核 = 必须出现 40 字节 token / 9 字节 uid / `"Protocol"` / `"DevId"` 之一
- 试对了不可能看错；本次所有粗筛命中都已全量复核，无一通过

**样本一致性**：A 只给了前 32 字节 + 末 36 字符，B 是完整 432 字节；
本轮全部爆破以 B 为主，A 用于结构差分（首字节不同 ⇒ IV 随机）。

---

## 5. 覆盖边界（没做到的，诚实标注）

**已经排除的**：

1. key 是客户端里任何可打印字符串，经 UTF8 补零/截断、MD5、SHA256、SHA1、MD5/SHA256-hex、base64/hex 解码、UTF-16LE、PBKDF2（1/1000 轮，SHA1/SHA256，16/32 字节 salt）派生
2. key 是 `global-metadata.dat` / `libil2cpp.bin` 里任何 4 字节对齐的连续 16/32 字节（裸 byte[]）
3. 32 字节块（Rijndael-256）
4. 流模式（CFB/OFB/CTR）与 ECB
5. RC4 / 重复 XOR 密钥流

**还没排除的**（也就是下一步该打的点）：

1. **key 是运行时生成的**：`CryptAES.generateKeyString` / `cRandom` / `IVString` 这组名字强烈暗示
   「用固定 seed 的 `System.Random` + 字符表（`CryptAESOrigin`?）现场生成 keyString」。
   若是这样，静态字符串里永远找不到它——必须动态取或反编译 `generateKeyString`。
2. **key 由 3 段拼接**：`AESKeyHolder.part1 / part2 / part3`。
   若三段各自是独立字面量/字节数组且中间隔着其它数据，任何「单串字典」都不会命中。
   需要按文件顺序做「相邻 run 拼接」或直接读 `.cctor`。
3. **key 是 `.text` 里的立即数 / 栈上拼出来的**（ACE 加密了约 26% 的 `.text`）。
4. **key 在手机运行期落盘的文件里**（安装后写入，不在 APK/metadata 内）。

---

## 6. 下一步建议（按性价比）

### ① 动态取 key（最快、最确定，1 小时内可完成）

在已 root 的模拟器/手机上，对 `libil2cpp.so` 里 `MX.Core.Services.CryptAES.EncryptRJ256Api`
或 `generateKeyString` 下 hook，打印入参 `keyString` / `key` / `iv`。

- 项目已有 LDPlayer（`C:\leidian`）与手机接管链路（报告 08）
- 只需要跑一次登录，打印一次 key 即可，**不需要长期挂 Frida**
- 风险点见报告 18（ACE/XIGNCODE 与 Frida 共存），建议用「一次性 attach → dump → 立刻 detach」

### ② 静态读 `.cctor`（不碰手机，但要先解决两件事）

1. `global-metadata.dat` 头部被加密：magic 实测 `94 43 72 12`（不是 `0xFAB11BAF`），
   所以拿不到 `stringLiteralData` / `fieldAndParameterDefaultValueData` 的区段偏移
2. `libil2cpp.bin` 的 `.text` 有约 26% 页在磁盘上是 ACE 加密的

可行路线：
- 用内存里**已解密的 metadata**（从 `/proc/<pid>/maps` + `/proc/<pid>/mem` dump）做 Il2CppDumper，
  拿到 `CryptAES` 各方法的 RVA 和方法 token 表；
- 或者先脱 ACE（报告 11/17 有工具链评估），再跑 Il2CppDumper + Ghidra。

### ③ 若坚持纯离线：把「三段拼接」纳入搜索

- 按**文件物理顺序**重新抽 run（不要按字典序），对相邻 run 做 `p1+p2`、`p1+p2+p3` 拼接
- 再叠加本报告 §3.1 的 KDF 矩阵
- 这条的前提是「key 被拆成多段且各段相邻」，概率中等，成本约 1 小时

### ④ 绕过（如果目标只是「跑通登录」而不是「完整还原请求」）

报告 34 在 metadata 里实测到 `DecryptOrReturnOriginal` 这个方法名（旁证还有开源 SDK `core/client.py` 的
`if packet.lstrip().startswith(("{","[")) -> 直接当明文`），**响应方向很可能可以回明文 JSON**（未实测）。
请求方向即使解不开，只要服务端不需要请求体里的字段（uid/token 我们本来就知道），
**登录链路可以先跑通**，把解密留作后续。

---

## 7. 本轮产物

全部在 `report\_tmp\mx_crypto\`：

| 文件 | 说明 |
|---|---|
| `crack_core.py` | 核心：布局/KDF/判据 + 自写 Rijndael（Nb=4 对 FIPS-197 向量自测通过） |
| `run_pass.py` | 并行字典爆破器（`--family fast/pbkdf2:.../rij/trunc`） |
| `crack2.py` | 第二轮：CBC block0/block1 + ECB/CFB/OFB/CTR + hex/UTF-16 KDF |
| `scan_windows.py` | **裸字节窗口扫描器**（把文件里每个对齐窗口当 AES key） |
| `verify_any.py` | 对粗筛命中做全量解密复核 |
| `selftest_crack.py` / `selftest2.py` | **阳性对照**：造样本 → 爆破器必须命中 |
| `rc4_strict.py` | RC4 / XOR 严格复核（全量解密 + 已知明文判定） |
| `t1_probe.py` / `t2c_literals.py` | 结构、token、metadata 字面量形态取证 |
| `p1_run.log` / `batch2.log` / `t5b.log` / `winmd*.log` / `wso_*.log` | 每一轮的完整日志（含速度、耗时、命中数） |

---

## 8. 复现命令

```powershell
$py="C:\Users\su\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
cd "C:\Users\su\Desktop\大肥鱼项目\BAServer\report\_tmp\mx_crypto"

# 阳性对照（必须先 PASS）
& $py -X utf8 selftest_crack.py

# 主字典（~50s）
& $py -X utf8 run_pass.py --tag p1 --family fast --workers 26

# 裸窗口扫描（示例：metadata 32B）
& $py -X utf8 scan_windows.py --file <global-metadata.dat> --klen 32 --step 4 --workers 26 --tag win32
& $py -X utf8 verify_any.py <global-metadata.dat> 32 hits_win32.jsonl
```
