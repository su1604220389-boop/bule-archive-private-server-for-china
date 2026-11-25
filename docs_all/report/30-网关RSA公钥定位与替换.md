# 30 — 网关 RSA 公钥定位与等长替换

> 目标：定位 `global-metadata.dat` 里那把用于 `Queuing_GetCryptoKeys` 网关握手的 RSA 公钥 PEM，并做出**等长替换**的补丁工具。
> 结论：**找到了，三段分散存储，总长 451 字节，RSA-2048**。补丁工具已完成并通过自测与生产产物验证。

---

## 0. 一句话摘要（先纠正一个前提）

| 项目 | 上游（国际服）描述 | **国服实测（本文件）** |
|---|---|---|
| 密钥长度 | RSA-4096 | **RSA-2048** |
| PEM 总长 | 799 B（`ChunkLengths = [272, 272, 255]`） | **451 B** |
| 切分 | 3 段 272/272/255 | **3 段 150 / 150 / 151** |
| 位置 | `fieldAndParameterDefaultValueData` 的定长空洞 | 同样形态：三段互不相邻、各自嵌在 int32 表之间 |
| 首段偏移 | 随 build 漂移（439170 整体挪了 `+0x49B0`） | `0x0178CC60`（**不得硬编码**） |
| 中段偏移 | — | `0x012D5F88`（离首段约 **4.7 MB 远**） |
| 末段偏移 | — | `0x0178CBA0`（**在首段之前**，差 0xC0） |

> **所以「我们的必须是 4096 位」这条对国服不成立。** 一份 4096 位的 PEM 规范化后是 **800 字节**，塞不进 451 字节的三个洞——工具会直接拒绝（见 §5.3 实测）。
> 之所以必须同为 2048，是因为洞是定长的：换长度就会移动整个 section 及其后所有偏移。

**关键点：末段（含 `-----END` 的那段）在首段之前**，中段在 4.7 MB 之外。这就是为什么"搜到 PEM 就地替换"这种做法必然失败——文件里根本不存在一段连续完整的 PEM。

---

## 1. 扫描过程与全部命中

在 `global-metadata.dat`（38,426,024 B，sha256 `2352cb57…`）里搜下列记号：

```
-----BEGIN                          hits = 2   (0x0178CC60, 0x017BE433)
-----END                            hits = 2   (0x0178CC1E, 0x017BE43F)
PUBLIC KEY-----                     hits = 2   (0x0178CC27, 0x0178CC6B)
RSA PUBLIC KEY-----                 hits = 0
PRIVATE KEY-----                    hits = 0
CERTIFICATE-----                    hits = 0
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8A    hits = 1   (0x0178CC7B)   ← PKCS#8 SPKI base64 头
MIIBIjANBgkqhkiG9w0BAQEF            hits = 1   (0x0178CC7B)
MIIBCgKCAQEA                        hits = 1   (0x0178CC9B)   ← SPKI 内部 PKCS#1 的 base64 头
MIIBCgKCAgE                         hits = 0
ssh-rsa                             hits = 0
```

第二处 `-----BEGIN`（`0x017BE433`）**是误命中**，上下文为：

```
...84 00 84 00 16 2d 2d 2d 2d 2d 42 45 47 49 4e 20 12 2d 2d 2d 2d 2d 45 4e 44 ...
```

即 `-----BEGIN ` + `\x12` + `-----END ` —— 这是 metadata 字段名区里的**字符串切片**（配合 `BestHTTP.SecureProtocol.Org.BouncyCastle.Pkcs12.IgnoreUselessPassword` 之类），不是 PEM。**排除。**

### 真正的三处

| 记号 | 偏移 | 说明 |
|---|---|---|
| `-----BEGIN PUBLIC KEY-----` | `0x0178CC60` | 首块起点 |
| `-----END PUBLIC KEY-----` | `0x0178CC1E` | 末块里的结束行（**在首块之前**） |
| SPKI base64 头 `MIIBIjAN…` | `0x0178CC7B` | 首块内 |
| 主体中段 `rzb1o8…` | `0x012D5F88` | **相隔 4.7 MB 的中块** |

### 原始十六进制 dump（前后各 ≥64 字节）

**首块 `0x0178CC50..0x0178CD00`**
```
0x0178CC50  04 00 00 00 06 00 00 00 07 00 00 00 00 00 00 00 2d 2d 2d 2d 2d 42 45 47 49 4e 20 50 55 42 4c 49
0x0178CC70  43 20 4b 45 59 2d 2d 2d 2d 2d 0a 4d 49 49 42 49 6a 41 4e 42 67 6b 71 68 6b 69 47 39 77 30 42 41
0x0178CC90  51 45 46 41 41 4f 43 41 51 38 41 4d 49 49 42 43 67 4b 43 41 51 45 41 74 67 53 32 42 58 4c 4b 49
0x0178CCB0  72 49 38 4f 46 49 5a 69 33 67 65 0a 73 56 51 4c 51 71 38 45 70 77 62 30 58 4c 53 4b 41 6d 46 31
0x0178CCD0  35 72 35 43 54 34 45 46 39 78 61 4b 58 4f 49 59 68 6f 35 49 77 6c 6a 64 6b 33 46 44 75 68 71 43
0x0178CCF0  77 6e 5a 4c 39 58 00 00 01 00 00 00 02 00 00 00 03 00 00 00 05 00 00 00 00 00 00 00 00 00 00 00
           ^^^^^^^^^^^^ 结束于 0x0178CCF5，随后 00 00 是填充，0x0178CCF8 起是 int32 表
```

**中块 `0x012D5F60..0x012D6050`**
```
0x012D5F60  00 00 00 00 00 00 80 be 00 00 00 00 00 00 80 3e 00 00 00 00 00 00 00 00 00 00 00 40 00 00 c0 3f
0x012D5F80  00 00 80 3f 00 00 00 00 72 7a 62 31 6f 38 0a 50 50 64 69 34 39 77 6f 5a 67 69 46 76 66 36 68 55
                               ^^^^^^^^^^^^^^^^^^^^ 0x012D5F88 起
0x012D5FA0  35 6b 39 66 48 37 4e 47 43 46 71 39 61 61 64 68 67 75 47 66 4c 4d 74 50 6f 35 79 49 70 2b 61 77
0x012D5FC0  65 6d 61 77 74 53 5a 6b 52 36 72 5a 68 57 61 0a 77 48 30 44 42 68 34 67 72 63 53 61 71 6f 66 5a
0x012D5FE0  59 68 79 54 35 49 53 4f 55 6d 2b 42 63 54 53 31 57 59 67 75 6a 67 63 70 75 44 79 78 45 33 34 45
0x012D6000  6b 55 57 34 50 4e 46 38 65 71 72 65 66 72 75 77 0a 37 59 7a 49 50 41 49 39 6b 39 79 4f 51 00 00
                                                            结束于 0x012D601D，随后 00 00，0x012D6020 起是另一段表
```

**末块 `0x0178CB80..0x0178CC40`**
```
0x0178CB80  00 00 00 00 01 00 00 00 02 00 00 00 03 00 00 00 04 00 00 00 05 00 00 00 00 00 00 00 00 00 00 00
0x0178CBA0  76 75 30 79 4b 6f 62 52 44 31 70 4a 48 4d 34 37 44 4e 2f 57 4d 44 71 52 70 38 2b 6d 6d 49 6d 48
           ^^^^^^^^^^^^^^^^^^^^^^^^ 0x0178CBA0 起
0x0178CBC0  55 62 4c 2b 74 55 6f 65 48 79 45 55 55 2f 48 4d 6b 37 4e 0a 57 53 6d 52 54 48 32 55 58 43 2f 69
0x0178CBE0  6a 49 57 39 79 46 54 78 7a 65 66 33 63 31 4d 2b 6a 32 78 47 34 4f 37 34 7a 74 41 50 38 38 44 4b
0x0178CC00  4d 5a 77 73 66 67 5a 7a 44 4e 52 65 38 62 65 70 32 62 75 53 0a 4f 51 49 44 41 51 41 42 0a 2d 2d
0x0178CC20  2d 2d 2d 45 4e 44 20 50 55 42 4c 49 43 20 4b 45 59 2d 2d 2d 2d 2d 0a 00 02 00 00 00 01 00 00 00
                                                   结束于 0x0178CC37，随后 00，0x0178CC38 起是 int32 表
```

---

## 2. 完整原 PEM（逐字节，`repr()` 标注换行）

三段按 **首 → 中 → 末** 的顺序拼接（`\n` 是真实 `0x0A`，**没有 CR**）：

```python
b'-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAtgS2BXLKIrI8OFIZi3ge\n'
b'sVQLQq8Epwb0XLSKAmF15r5CT4EF9xaKXOIYho5Iwljdk3FDuhqCwnZL9X'          # ← 首块到此为止（0x0178CCF5）
b'rzb1o8\nPPdi49woZgiFvf6hU5k9fH7NGCFq9aadhguGfLMtPo5yIp+awemawtSZkR6rZhWa\n'
b'wH0DBh4grcSaqofZYhyT5ISOUm+BcTS1WYgujgcpuDyxE34EkUW4PNF8eqrefruw\n'
b'7YzIPAI9k9yOQ'                                                      # ← 中块到此为止（0x012D601D）
b'vu0yKobRD1pJHM47DN/WMDqRp8+mmImHUbL+tUoeHyEUU/HMk7N\n'
b'WSmRTH2UXC/ijIW9yFTxzef3c1M+j2xG4O74ztAP88DKMZwsfgZzDNRe8bep2buS\n'
b'OQIDAQAB\n-----END PUBLIC KEY-----\n'                                # ← 末块到此为止（0x0178CC37）
```

规范化（标准 64 字符折行 + 结尾换行）后：

```
-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAtgS2BXLKIrI8OFIZi3ge
sVQLQq8Epwb0XLSKAmF15r5CT4EF9xaKXOIYho5Iwljdk3FDuhqCwnZL9Xrzb1o8
PPdi49woZgiFvf6hU5k9fH7NGCFq9aadhguGfLMtPo5yIp+awemawtSZkR6rZhWa
wH0DBh4grcSaqofZYhyT5ISOUm+BcTS1WYgujgcpuDyxE34EkUW4PNF8eqrefruw
7YzIPAI9k9yOQvu0yKobRD1pJHM47DN/WMDqRp8+mmImHUbL+tUoeHyEUU/HMk7N
WSmRTH2UXC/ijIW9yFTxzef3c1M+j2xG4O74ztAP88DKMZwsfgZzDNRe8bep2buS
OQIDAQAB
-----END PUBLIC KEY-----
```

`openssl pkey -pubin -text -noout` 验证：

```
Public-Key: (2048 bit)
Modulus:
    00:b6:04:b6:05:72:ca:22:b2:3c:38:52:19:8b:78:1e:b1:54:0b:42:af:04:a7:06:f4:5c:b4:8a:02:61:...
```

| 项 | 值 |
|---|---|
| 文件 | `bapatch/metadata_orig_pub.pem` |
| 长度 | **451 B**（LF 换行；若用 CRLF 则是 460 B） |
| sha256 | `cf0297159db93aca7edbc1feaaff0ee71e2bc93b86abd7d2e97b5c0f10d268ea` |
| base64 主体 | **392 字符** |
| SPKI DER | **294 B**，头 `30 82 01 22 …`（外层 SEQUENCE 声明 290，合计 294） |
| 密钥 | **RSA-2048**，`e = 65537` |

---

## 3. 定长约束分析

| 块 | 偏移 | 槽位容量 | 内容构成 | 后面紧跟 |
|---|---|---|---|---|
| **A（首）** | `0x0178CC60` | **150 B** | BEGIN 行 26 + `\n` + base64 123（64 + `\n` + 58） | `00 00` 填充，再后是 int32 表 |
| **M（中）** | `0x012D5F88` | **150 B** | base64 147（`rzb1o8` + `\n` + 64 + `\n` + 64 + `\n` + 13） | `00 00` 填充，再后是另一段表 |
| **C（末）** | `0x0178CBA0` | **151 B** | base64 123 + `\n` + `OQIDAQAB` … 到 END 行 24 + `\n`（共 3 个换行） | `\n` 后 `00`，再后是 int32 表 |
| 合计 | — | **451 B** | = 规范化 PEM 全长的**精确值** | — |

### 为什么换同一长度的 PEM 就绝对安全

- 一把 RSA-2048 的 SPKI DER 恒为 **294 字节**（`30 82 01 22` + 290），base64 恒为 **392 字符**；
- 用固定格式（`-----BEGIN PUBLIC KEY-----` / 64 字符折行 / `-----END PUBLIC KEY-----` / LF）时，PEM 总长恒为 **451 字节**；
- 451 = 150 + 150 + 151，**逐块切点也对得上**（切点落在 base64 主体内的固定位置，与换行无关，因为 base64 解码会忽略空白）；
- 因此替换后**文件大小不变、section 不移动、后续所有偏移不变**。

### 实测对照

```
openssl genrsa 2048 → 规范化 PUBLIC KEY PEM  = 451 B   ✅ 可替换
openssl genrsa 4096 → 规范化 PUBLIC KEY PEM  = 800 B   ❌ 比洞大 349 B，工具拒绝
```

> 顺带印证了上游的数字：国际服那份「799 B、切 272/272/255」，799 ≈ 一把 4096 位 PEM 的长度（少一个尾换行）。**国服就是 2048，别照抄 4096。**

---

## 4. 全项目扫描：这把密钥只存在于 metadata

为避免"只改了一处、另一处还在用旧公钥"，对整个 `work/ba`（3,934 个文件）做了内容扫描：

| 记号 | 命中位置 | 判定 |
|---|---|---|
| `-----BEGIN PUBLIC KEY-----` | `global-metadata.dat @0x0178CC60` | ✅ 目标 |
| 同上 | `libunity.so @0x10DD669`、`libunity.bin` 同偏移 | ❌ **只有 52 字节的格式常量**（`-----BEGIN PUBLIC KEY----- ` + `-----END PUBLIC KEY-----`，中间无主体）——是 PEM 解析/生成代码里的字面量，不是密钥 |
| 同上 | `out/metadata-strings.txt`、`out/strings/libunity.so.txt` | ❌ 之前导出字符串的中间产物 |
| 原密钥模数前 24 字符 `tgS2BXLKIrI8OFIZi3ge` | **仅** `global-metadata.dat @0x0178CCA7` (+ 导出的 txt) | ✅ 唯一 |
| DER 编码的模数（`02 82 01 01 00 b6 04 b6 05 72 ca 22 b2`） | **0 命中** | — |
| SPKI 头 `MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8A` | `classes2.dex @0x308EE3/@0x309075`、`jadx` 里 `com/mobile/auth/l/i.java`、`common_config.json` | ❌ **都是别的密钥**（模数不匹配）——TapTap / 阿里 / 移动认证 SDK 自己的公钥 |

**结论：需要改的只有 `global-metadata.dat` 里这三处。**

> 注：`libunity.so` 在别的场景下被 ACE 做了磁盘哈希钉死（改 4 字节就 SIGBUS），但这里**不需要动它**，所以不构成阻碍。

---

## 5. 补丁工具

### 5.1 文件

`bapatch/patch_metadata_key.py`（18,551 B，纯标准库，Python ≥ 3.8）

```
用法：
  # 只发现布局、不写任何东西
  python patch_metadata_key.py --in global-metadata.dat --dry-run

  # 把原始（拼装好的）公钥导出成 PEM
  python patch_metadata_key.py --in global-metadata.dat --extract-pem orig.pem

  # 打补丁
  python patch_metadata_key.py --in global-metadata.dat \
         --pubkey gateway_pub.pem --out global-metadata_patched.dat \
         --report report.json

  # 复核任意文件（原始或已补丁）
  python patch_metadata_key.py --in global-metadata.dat --verify
```

### 5.2 定位算法（**AOB，绝不使用固定偏移**）

1. **锚定首块**：找 `-----BEGIN PUBLIC KEY-----`，向后吞掉 base64 字母表和换行 → 得到 A 的区间与长度。
2. **锚定末块**：找 `-----END PUBLIC KEY-----`，**向前**吞掉整个 base64 块（含内嵌换行）→ 得到 C 的区间。
3. **用「验证」而不是「猜测」找中块**：枚举全文件所有极大 base64 串（长度 24–4096），对每个候选拼 `A + cand + C`，然后要求：
   - base64 主体长度 ∈ [300, 1200] 且 **是 4 的倍数**；
   - 能 base64 解码；
   - **往返校验**：`base64.b64encode(decoded)` 必须与主体逐字符相同（这一条能排除所有偶然的 base64 拼接）；
   - DER 必须严格是一个合法的 `SubjectPublicKeyInfo`：外层 SEQUENCE 长度与缓冲精确吻合、OID 必须是 `1.2.840.113549.1.1.1`、BIT STRING 无未用位、内部 `RSAPublicKey` 的 modulus/exponent 合法。
   
   本文件里**只有一个候选通过**（`0x012D5F88`，恰好 150 B，RSA-2048）。
4. 三段两两不重叠才继续。

> 因为全程按内容定位、并按密码学结构验证，所以**上游说的「build 439170 整体挪了 +0x49B0」这类偏移漂移不会影响本工具**。

### 5.3 硬断言（任何一条不过就**不写盘**）

| 断言 | 失败时的行为 |
|---|---|
| 替换 PEM 规范化后总长 == 洞总长（451） | 退出码 1，不写，输出「比洞大/小多少」 |
| 替换密钥位数 == 原密钥位数（2048） | 退出码 1，不写 |
| base64 主体长度 == 原主体长度（392） | 退出码 1，不写 |
| 三段互不重叠 | 退出码 1，不写 |
| 输出文件大小 == 输入文件大小 | 退出码 1，不写 |
| **所有差异字节都落在三个洞之内** | 退出码 1，不写 |
| 写完重新定位，抽回的 PEM 必须等于新 PEM | 退出码 1，不写 |
| 写完重新定位，密钥位数必须等于新密钥位数 | 退出码 1，不写 |

### 5.4 自测结果（一次性密钥，非生产）

用 `openssl genrsa 2048` 现生成的一对临时密钥跑完整流程：

```
=== discovered layout (CN build) ===
  piece A (BEGIN + body head) off=0x0178CC60 len=150
  piece M (body middle)       off=0x012D5F88 len=150
  piece C (body tail + END)   off=0x0178CBA0 len=151
  total PEM bytes             451
  key size                    RSA-2048  (e=65537)
  SPKI DER len                294

=== post-write verification ===
  output size      : 38426024  (unchanged: True)
  every differing byte lies inside a hole : True
      A @0x0178CC60 len=150 : 3 differing run(s), first 0x0178CCA7 last 0x0178CCF6
      M @0x012D5F88 len=150 : 7 differing run(s), first 0x012D5F8A last 0x012D601E
      C @0x0178CBA0 len=151 : 4 differing run(s), first 0x0178CBA0 last 0x0178CC17
  total differing bytes    : 335 of 38426024 (0.0009%)
  re-discovered PEM matches new key : True
  re-discovered key size            : RSA-2048
```

再把补丁产物里的公钥抽回来、和私钥派生的公钥比对：

```
extracted sha256 = b9c425540c42df7828da3d5644fb2b3056ea148c51fce7f2cee5a61236a6b193
test key  sha256 = b9c425540c42df7828da3d5644fb2b3056ea148c51fce7f2cee5a61236a6b193
IDENTICAL = True
openssl pkey -pubin -pubcheck -noout  →  Key is valid
Public-Key: (2048 bit)
```

**4096 位拒绝测试：**

```
4096 pub pem raw size = 814
REFUSING to write: replacement is 800 bytes but the holes total 451.
  A different key size / line width would shift every following
  offset in the metadata section. Nothing was written.
output exists? False
```

### 5.5 生产产物（已生成，可直接用）

```
bapatch/metadata_orig_pub.pem                     451 B   cf0297159db93aca7edbc1feaaff0ee71e2bc93b86abd7d2e97b5c0f10d268ea
bapatch/gateway_key/gateway_priv.pem            1,732 B   （服务器用，务必保管）
bapatch/gateway_key/gateway_pub.pem               460 B   （CRLF，工具会自动规范化成 451）
bapatch/global-metadata_patched.dat       38,426,024 B   f0a300084b3dd8c30dc8c493c0da79d04cade7d972841e04a59e42f2855e77ae
bapatch/global-metadata_patched.dat.origbackup 38,426,024 B  2352cb570a4652cc76574b9eb87a2941cf906237ff1f1a80454ab1b5634b47e6  ← 原文件
bapatch/global-metadata_patched.report.json      1,975 B  每段 offset/长度/新旧 sha256 + 全部差异区间
```

本次生产补丁的差异统计：

```
total differing bytes : 337 / 38,426,024  (0.0009%)
piece A @0x0178CC60 len=150 : 5 runs, 0x0178CCA7 .. 0x0178CCF6
piece M @0x012D5F88 len=150 : 4 runs, 0x012D5F88 .. 0x012D601E
piece C @0x0178CBA0 len=151 : 4 runs, 0x0178CBA0 .. 0x0178CC16
```

**跨验证**：从 `global-metadata_patched.dat` 抽出的公钥，与 `gateway_priv.pem` 派生的公钥**规范化后逐字节相同**（451 B / 451 B）。

---

## 6. 风险与失败形态

### 6.1 已知的失败形态（上游描述 + 我们的推断）
- **症状**：卡在「Unpacking game resources」，屏幕无任何提示。
- **机理**：客户端拿改过的公钥去加密 `Queuing_GetCryptoKeys` 握手包，服务端用**旧私钥**解不开 → 握手静默失败。
- ⚠️ **所以「换公钥」和「换服务端私钥」必须成对做。** 只改 metadata 不改服务端，效果就和没改一样（甚至更难查，因为不再报错）。

### 6.2 ACE 会不会因此杀掉？（**未知，必须实测**）
- 已证实：ACE 对 **`libunity.so`** 做磁盘哈希钉死（改 4 字节 → SIGBUS）；对 **`libil2cpp.so`** 未做。
- **`global-metadata.dat` 是否被哈希、被完整性校验：今晚没有证据。**
- 我们的改动只有 337 字节，且**文件大小完全不变**，从"体积/布局"角度看不出破绽；但如果 ACE 对整文件做 CRC/SHA，仍会被抓。
- **实测方法**：装上后看是否一启动就闪退 / 是否报 ACE 相关错误 / 是否能过"Unpacking game resources"。若被杀，回滚就是把 `.origbackup` 覆盖回去（一个 `cp`）。

### 6.3 其它风险
- **换行风格**：如果手工把 PEM 改成了 CRLF（460 B），工具会因长度不符拒绝——这正是设计意图，不是 bug。
- **多版本**：本工具按内容定位，换 build 也能用；但**如果新 build 的密钥变成 4096 位**，洞的长度会变（约 800 B），本工具会自动发现并报告新的洞总长，届时按新值重新生成密钥即可（无需改代码）。
- **双重打包**：如果客户端是从 APK 里的 `assets/bin/Data/Managed/Metadata/global-metadata.dat` 读，那必须**重打包 APK**或做文件级替换；见 §7。

---

## 7. 下一步操作清单（装到手机上）

> ⚠️ 先确认一件事：`global-metadata.dat` 在设备上到底从哪儿读。
> 若 APK 是 `extractNativeLibs=true`（本项目正是），`assets/` 仍是**未解压的 zip 条目**，运行时由 Unity 通过 AssetManager 读取 → **改 `assets/` 里的文件必须重打包 APK 并重签名**。
> 只有在 APK 被解包到 `/data/app/.../` 之后仍有独立文件的情况下，才能直接替换单个文件。

### 路线 A（推荐，最稳）：重打包 APK
1. 用 `apktool d` / `7z` 解包原 APK（保留全部其它条目原样）。
2. 把 `assets/bin/Data/Managed/Metadata/global-metadata.dat` 换成 `bapatch/global-metadata_patched.dat`（**必须保持相同的 zip 存储方式**——如果原来是 STORED 就不要改成 DEFLATED，反之亦然；否则会改变 APK 内偏移，某些校验会挂）。
3. `zipalign -p 4` → `apksigner sign`（v1+v2+v3）。
4. 卸载重装（**不要覆盖安装**，签名变了会失败；且要先备份 `/data/data/com.RoamingStar.BlueArchive`，卡密登录态在里面）。
5. 装完 `restorecon` 不用管（APK 由系统安装器处理 SELinux）。

### 路线 B：文件级替换（仅当运行时确实读独立文件）
```sh
# 以 root 操作，注意必须是"先 cp 到临时位置 + 校验 + 原子 mv"
DST=/data/app/~~xxxx/com.RoamingStar.BlueArchive-xxxx/base.apk   # 不对，APK 里换不了
# 若存在解包目录：
#   /data/app/<pkg>/.../assets/bin/Data/Managed/Metadata/global-metadata.dat
cp /data/local/tmp/global-metadata_patched.dat /data/local/tmp/gm.new
sha256sum /data/local/tmp/gm.new     # 必须 = f0a300084b3dd8c30dc8c493c0da79d04cade7d972841e04a59e42f2855e77ae
chown <uid>:<gid> /data/local/tmp/gm.new
chmod 644 /data/local/tmp/gm.new
restorecon /data/local/tmp/gm.new
mv -f /data/local/tmp/gm.new <目标路径>
```
**绝对不要用 `cat > 目标` 的方式写**——本项目已经被这个坑过一次（写一半中断 → 文件 0 字节 → `dlopen failed: file offset for the library >= file size`）。

### 服务端（必须同步做）
1. 把 `bapatch/gateway_key/gateway_priv.pem` 放到服务器，配置给 `Shittim-Server`（它需要这把私钥解 `Queuing_GetCryptoKeys`）。
2. **私钥不要放进任何 nginx vhost 的 root 目录**（项目规矩：私钥 `600`，不放 web 可达路径）。
3. 服务端的公钥/私钥必须与打进 metadata 的那把**严格配对**——本文 §5.5 的跨验证已经证明当前这对是配的。

### 验证顺序（别跳步）
1. 先只装 metadata，服务端用**配对私钥**跑通 → 看是否还能过「Unpacking game resources」。
2. 若卡在 unpacking → 说明改坏了或有别处也在用旧公钥，先回滚（`cp .origbackup` 回去）。
3. 若能过 unpacking 但握手仍失败 → 查服务端私钥是否真的被加载（对比握手包能否解开）。

### 回滚
```sh
cp bapatch/global-metadata_patched.dat.origbackup <目标路径>
# sha256 必须回到 2352cb570a4652cc76574b9eb87a2941cf906237ff1f1a80454ab1b5634b47e6
```

---

## 8. 诚实标注（本次没做到 / 没做的）

| 项 | 状态 |
|---|---|
| 解出 metadata 头部的加密 | **没做，也没需要**。公钥在**明文区**（字符串/默认值数据），全程不需要解头部。之前 24 号报告说「头部被加密、字符串区明文」——本次完全印证：我们只用了内容搜索，没解析任何 header 字段 |
| 精确说出这三块属于哪个 metadata 区段 | **未证实**。头部加密 → 拿不到 `fieldAndParameterDefaultValueData` 的 offset/size。但形态（定长洞 + 前后夹 int32 表 + 段被切开）与上游描述完全一致，**标注为「与 `fieldAndParameterDefaultValueData` 一致，未直接验证」** |
| ACE 是否校验 `global-metadata.dat` | **未知，需实测**（§6.2） |
| 设备上 metadata 的实际读取路径 | **未验证**（§7 开头的路线选择依赖它） |
| 服务端如何加载这把私钥 | **未做**，只给出了私钥文件与要求 |

---

## 9. 附：全部中间产物

| 路径 | 内容 |
|---|---|
| `bapatch/patch_metadata_key.py` | 补丁工具（交付物） |
| `bapatch/metadata_orig_pub.pem` | 从 metadata 拼回来的**原始**公钥（451 B） |
| `bapatch/gateway_key/gateway_priv.pem` | 生产用 RSA-2048 私钥 |
| `bapatch/gateway_key/gateway_pub.pem` | 对应公钥（CRLF 460 B，工具会规范化） |
| `bapatch/global-metadata_patched.dat` | **已打补丁的 metadata**（38,426,024 B，sha256 `f0a30008…`） |
| `bapatch/global-metadata_patched.dat.origbackup` | 原文件备份（sha256 `2352cb57…`） |
| `bapatch/global-metadata_patched.report.json` | 补丁 JSON 报告 |
| `report/_tmp/meta_pem/s1_scan.py` | 记号扫描 |
| `report/_tmp/meta_pem/s2_dump.py` | 区域 hex dump + base64 长串扫描 |
| `report/_tmp/meta_pem/s3_frag.py` | 片段枚举 |
| `report/_tmp/meta_pem/s4_assemble.py` | 三段拼装 + DER 校验 |
| `report/_tmp/meta_pem/s5_elsewhere.py` | 全项目重复公钥扫描 |
| `report/_tmp/meta_pem/dbg.py` | 定位算法调试 |
| `report/_tmp/meta_pem/test_pub.pem` / `test_priv.pem` | 自测用一次性 2048 密钥 |
| `report/_tmp/meta_pem/test4096_pub.pem` / `test4096_priv.pem` | 拒绝测试用 4096 密钥 |
| `report/_tmp/meta_pem/global-metadata_TEST.dat` | 自测产物（可用 `--verify` 复核） |
