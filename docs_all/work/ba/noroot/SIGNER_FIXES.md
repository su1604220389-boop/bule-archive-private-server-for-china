# 签名器修复记录（`build_noroot_apk.py`）

> 对象：`work\ba\noroot\build_noroot_apk.py`
> 依据：`AUDIT_BUILD_NOROOT.md` §1 的 6 条必修项（P1-1 … P1-6）
> 日期：2026-11-17
> 原则：**不生成 2 GB 包、不连服务器、不动手机、不修改 `report\_tmp\cn_base.apk`**。
> 全部证据来自「微型 APK 全链路」+「对真包/旧产物的只读测量」+「独立重写的校验器」。

---

## 0. 一句话结论

改完之后，这个签名器在**签名层**是完整、可验证、可自洽的（v1 合规 + 剥离保护 + v2/v3 + 逐条/整份/证书三重自校验）；
**它还不能算"可分发"的唯一硬原因是：没有用真 `apksigner` / 真机独立验过一遍**（本机无 JVM，见 §6）。

---

## 1. 修复项一览

| # | 审计项 | 状态 | 代码位置（最终行号） | 一句话 |
|---|---|---|---|---|
| P1-1 | `.SF` 缺 `X-Android-APK-Signed: 2, 3` | ✅ | `build_v1()` 874，写头 893 | 主属性区补上降级保护头，与官方 `BACN.SF` / 真 apksigner 样本一致 |
| P1-2 | MANIFEST 808 行 > 72 B | ✅ | `JAR_MAX_LINE` 113，`jar_line()` 846，`jar_parse()` 898，`build_v1()` 879-891 | 按 signapk 的 **70 B** 折续行；解析器把续行拼回 |
| P1-3 | `--verify-only` 完全不验 v1 | ✅ | `verify_v1()` 1773-1896，`_entry_sha256()` 1752，`_scheme_set()` 1764，调用点 1977-1980 | 逐条摘要 + 整份摘要 + PKCS#7 + 头值 + 残留/重名/覆盖性 |
| P1-4 | cert/私钥不配对 | ✅ | `assert_key_pair()` 437，调用点 1453 / 2172 / 2186 / 2213 | SPKI 的 (n,e) 比对 **+ 签验往返** |
| P1-5 | `resources.arsc` 不强制 STORED | ✅ | `do_build()` 1557-1591、1588；`verify()` 2006-2030 | 构建时强制解压重写为 `method=0`；校验时**硬失败** |
| P1-6 | 源包身份未校验 / `MIN_SDK` 硬编码 | ✅ | `read_manifest_identity()` 1345，`check_source_identity()` 1393，`do_build()` 1455，v3 1625，`--force` 2521 | 包名/版本/targetSdk/NSC 资源 ID 硬校验；v3 minSdk 取自清单 |

**顺手清掉的死代码**：`verify()` 里 `stale = [n for n in names if is_old_signature(n) and False]`（永远为空、从不参与判断）已删除，换成真正的残留检查（在 `verify_v1()` 内）。

### 1.1 协作说明（重要）

本次任务期间，`build_noroot_apk.py` 被**另一个进程并发改写**：我 00:59 读到的是 46,300 B（1,245 行，已备份 `.orig`），
到 01:05 它已被写到 95,566 B，01:09 我接手缺口时 108,480 B；我的改动之后定格在 109,025 B（2,605 行）。
并发期间目录里还出现了不是我写的 `_probe_v1fmt.py` / `_probe_jarwrap.py` / `_probe_p7.py` / `_gmc_cli_test.py`。到我接手缺口时：

- P1-1 / P1-2 / P1-3 的**主体**已经由那次并发写入实现（`jar_line()`、`build_v1(apk_signed=…)`、`verify_v1()`）；
- P1-4 只做了 (n,e) 比对，缺"签验往返"；
- **P1-5、P1-6 完全没做**（`MIN_SDK` 仍硬编码传 v3，`arsc` 仍原样复制压缩方法，`verify()` 里 `stale` 死代码还在）；
- `self_test()` 当时塞的还是 8 字节假 `AndroidManifest.xml`，P1-6 一加就会让自检自己挂掉。

因此本次实际由我落地的改动是：**P1-5、P1-6 全部**、**P1-4 的签验往返**、**P1-3 的加固**（头的"值"校验、残留/重名/覆盖性、流式摘要）、
**`selftest_manifest()` + `--force` CLI + 自检适配**；P1-1/P1-2/P1-3 主体我做的是**独立复核**（见 §2 的逐项证据，其中
"70 B 而不是 72 B"、"41,310 段字节级重排 0 不匹配"、"官方 SF 头的确切 4 行"是本次新证）。
用 `_signfix_test.py` 对 `.orig`（改前）与最终版跑同一套断言，结果见 §4。

---

## 2. 逐项：改了什么、为什么、证据

### P1-1 `.SF` 加 `X-Android-APK-Signed: 2, 3`

**位置**：`build_v1()`（874-895），写头在 893：

```python
if apk_signed:
    sf += jar_line('X-Android-APK-Signed: ', ', '.join(apk_signed))
```

**为什么**：apksig 的 `JAR_SIG_NO_APK_SIG_STRIP_PROTECTION` 对应"APK 有 v2/v3 但 `.SF` 没声明"。
没有这个头，v1-only 客户端无法知道"本包还应有 v2/v3"——把签名块整块剥掉仍能通过 v1 校验。

**实测证据（官方包）**：`report\_tmp\cn_base.apk` 的 `META-INF/BACN.SF` 主属性区前 4 行：

```
Signature-Version: 1.0
Created-By: 1.0 (Android)
SHA-256-Digest-Manifest: D8Z+7MT7o8YeoruOAUKDKjR9GkheZ8S47ZEdcHeZsHo=
X-Android-APK-Signed: 2, 3
```

随后空行、再 `Name: Andr…`。真 apksigner 签的 `bapatch\lsp\build13\Probe13.apk` 的 `META-INF/BA.SF`
同样是 `X-Android-APK-Signed: 2, 3`（该文件 599 B，5 个逐条段）。

**改前 / 改后原始字节**（`_signfix_evidence.py`，同样 2 个条目）：

```
改前 CERT.SF (128 B)                改后 CERT.SF (156 B)
Signature-Version: 1.0              Signature-Version: 1.0
Created-By: BA-noroot-builder       Created-By: BA-noroot-builder
SHA-256-Digest-Manifest: HomJU…=    SHA-256-Digest-Manifest: 6OUYt…=
                                    X-Android-APK-Signed: 2, 3
(空行)                               (空行)
```

**位置断言**（测试 P1）：头必须落在**主属性区**（第一个空行之前），且在 `SHA-256-Digest-Manifest` 之后。
`P1 PASS value='2, 3', in_main_section=True`。

---

### P1-2 `MANIFEST.MF` 按 70 B 折续行

**位置**：`JAR_MAX_LINE = 70`（113）、`jar_line(prefix, value)`（846-873）、`build_v1()`（879-891）、`jar_parse()`（898-926）。

**为什么**：JAR 规范每行 ≤ 72 B（UTF-8，不含 CRLF）。原实现整行写出，真包 41,304 段里 **808 行 > 72 B，最长 92 B**。

**为什么取 70 而不是 72**（本次新证，之前文档只写了"signapk 是 70"但没给机制）：

1. 从 Gradle 缓存的 `apksig-8.6.1.jar` 里抽 `com/android/apksig/internal/jar/ManifestWriter.class`，
   解析常量池 ⇒ **只有一个 Integer 常量 70**（`MAX_LINE_LENGTH`）；`ManifestParser.class` 里没有任何行长常量（所以它读长行是宽松的）。
2. 用"70 B 贪心 + 续行加 1 个空格"把官方 `cn_base.apk` 的 `MANIFEST.MF` **41,310 个 section 全部重排一遍**
   （其中 1,254 段含续行），与原始字节 **逐字节比对：0 个不匹配**。⇒ 70 B + 单空格续行就是 signapk 的确切规则。

**改前 / 改后（同一输入）**：

| | MANIFEST 大小 | 最长行 | >72 B 行数 | 续行数 |
|---|---|---|---|---|
| 改前（`.orig`） | 296 B | **92 B** | 1 | 0 |
| 改后 | 299 B | **70 B** | **0** | 1 |
| 真包 41,304 条 · 旧产物 | 5,147,484 B | **92 B** | **808** | 0 |
| 真包 41,304 条 · 新生成器 | 5,151,246 B | **70 B** | **0** | **1,254** |

（最后一行是拿旧产物 `BA_noroot_v1.apk` 里的 41,304 条 `Name:+摘要` 喂给新 `build_v1()`、在内存里生成的结果；
续行数 1,254 与官方 signapk 的 1,254 条**完全相同**，因为两边的包名长度分布一致。）

**续行拼回（最容易错的地方）**：写了**两个独立解析器**验证——

- `parse_manifest_strict()`：每行 ≤ 72 B、续行必须以 1 个空格开头、属性必须 `key: value`；
- `parse_manifest_liberal()`：模仿 apksig `ManifestParser` / `java.util.jar.Manifest`（CRLF/LF/CR 都吃、不限行长、先按字节拼再 UTF-8 解码）。

两者对同一份新 MANIFEST 的结论一致：条目名逐条还原、`SHA-256-Digest` 逐条还原（含 97+83 字符的超长名、
中文/日文/ümlaut 的 UTF-8 名，且换行点不会切断多字节字符）。
`P2 PASS max=70 over72=0 continuations=3 strict_viol=无`。

---

### P1-3 `--verify-only` 全量验 v1

**位置**：`verify_v1()`（1773-1895），辅助 `_entry_sha256()`（1752，流式）、`_scheme_set()`（1764）、
`verify()` 调用点（1977-1980）。

**做了什么**：

| 检查 | 实现 | 失败即 |
|---|---|---|
| 逐条 `SHA-256-Digest` vs zip 实际内容 | `_entry_sha256()` 流式算（不把大 asset 读进内存），41,304 条全验 | FAIL |
| `SHA-256-Digest-Manifest` vs `MANIFEST.MF` 整体摘要 | `base64(sha256(mf_raw))` | FAIL |
| `X-Android-APK-Signed` **值**是否覆盖实际方案 | `_scheme_set()` + `apk_schemes`（`verify()` 传 v2/v3 实际存在集） | FAIL |
| 行长 ≤72 B | 直接按 CRLF 切行统计 | FAIL |
| `META-INF` 重名条目 | `Counter(names)` | FAIL |
| 残留旧签名 | 只允许 `MANIFEST.MF` + 1 个 `.SF` + 1 个 `.RSA/.DSA/.EC`，其余（含 `BACN.*`、`SIG-*`）报残留 | FAIL |
| 覆盖性（zip 条目没被 MANIFEST 覆盖） | 非 `META-INF` 条目缺摘要 | FAIL |
| PKCS#7 | 用 `.RSA` 里证书公钥验 `.SF`；`.RSA` 证书须与 v2/v3 块证书 SHA-256 相同 | FAIL |

**改前 / 改后（微型包，`_signfix_test.py` P3 系列）**：

| 场景 | 改前 | 改后 |
|---|---|---|
| 正常 v1 签名包 | 无 `verify_v1()`（根本无法验） | `verify_v1()=True` |
| 内容被篡改 | — | `False`（`a.txt 摘要不符`） |
| `.SF` 缺 `X-Android-APK-Signed` | — | `False` |
| 头存在但值写成 `2` | — | `False` |
| `META-INF` 残留 `BACN.SF/BACN.RSA` | — | `False` |
| 有 MANIFEST 未覆盖的条目 | — | `False` |

**真包只读证据**（对旧产物 `BA_noroot_v1.apk` 跑新的 `--verify-only`，2.1 GB 只读；整套 **12.8 s**，文件已在页缓存）：

```
v2: OK
v3: OK
v1: MANIFEST.MF 5147484 B, 41304 个 Name 段
v1: 最长行 92 B, 超 72 B 的行 808 个（违反 JAR 规范）   ← 改前产物自己就会挂在这里
v1: 逐条摘要 41304 条, 不符 0, 条目缺失 0 OK            ← 内容本身是对的（与审计一致）
v1: 未被 MANIFEST 覆盖的条目 0 个
v1: META-INF 签名文件 3 个 [MANIFEST.MF, CERT.SF, CERT.RSA]
v1: META-INF/CERT.SF SHA-256-Digest-Manifest OK（0 个逐条段）
v1: X-Android-APK-Signed = None（声明 空，APK 实有 [2, 3]）  ← 缺剥离保护/值不对
v1: META-INF/CERT.RSA 对 .SF 的 PKCS#7 验签 OK
v1 与 v2/v3 证书一致: OK
v1 结论: FAIL
resources.arsc: 第 1 条, STORED=True, 4 字节对齐=True
```

⇒ 新校验器对**旧产物**返回 1（FAIL），失败点正是 P1-1 和 P1-2 —— 这就是"改前产物不该分发"的机器判据；
而**新产物**（`--self-test` 里那个包）是 `v1 结论: OK`：
```
v1: MANIFEST.MF 769 B, 7 个 Name 段
v1: 最长行 70 B, 超 72 B 的行 0 个（OK）
v1: 逐条摘要 7 条, 不符 0, 条目缺失 0 OK
v1: X-Android-APK-Signed = '2, 3'（声明 [2, 3]，APK 实有 [2, 3]）
v1: META-INF/CERT.RSA 对 .SF 的 PKCS#7 验签 OK
v1 结论: OK
```

> 注：v1 仍然只写"整份 MANIFEST 摘要"，没有逐条 `Name:` 段（apksig 的
> `JAR_SIG_NO_ZIP_ENTRY_DIGEST_IN_SIG_FILE` 只在**整份摘要不可验证**时才发，所以这是合法形态，
> 官方 signapk 两种都写；改成逐条段属可选优化，不阻断安装/校验，本次没动）。

---

### P1-4 cert / 私钥配对自检

**位置**：`assert_key_pair(key, cert, where='')`（437-467）；调用点：
`do_build()` 1453、`gen_keystore()` 2161、`load_key()` 的 `--key-pem/--cert-pem` 路径 2186、PKCS#12 路径 2213。

**为什么**：`--key-pem A --cert-pem B` 时旧实现照建不误：v2/v3 块的 `pub` 来自 A、证书是 B，
工具自验（用块内公钥验签）当然通过，但 Android 安装时要求"签名者公钥 == 第一张证书的公钥" ⇒ 直接拒装。

**改后做两道检查**：
1. 证书 SPKI 的 `(n, e)` 与私钥逐项相同；
2. **用私钥签一段固定数据、用证书里的公钥验签**（本次补的，防"d 与 n/p/q 对不上的坏 PEM"这类即使 1 也过不了的情况）。

**改前 / 改后**：

| 场景 | 改前 | 改后 |
|---|---|---|
| `do_build(src, out, …, keyA, certB)` | 不拒绝，产出 `v2 pub == cert SPKI? **False**` 的包 | `SystemExit(1)`，报错给出两边 n 位长与往返验签结果 |
| 自检里的显式用例 | 无 | `assert_key_pair(key, c2)` 拒绝 |

**真包相关事实**（只读复核，审计 §3.4 的数字复现）：旧产物 `BA_noroot_v1.apk` 的
`v2/v3 签名者证书 SHA-256 = 94FA997B…` 与 `ba_private.cert.pem` 相同，`签名者证书 SPKI 294 B`，
`v1 与 v2/v3 证书一致: OK` ⇒ 默认路径本来就是配对的，本次加的是**防呆**。

---

### P1-5 `resources.arsc` 强制 STORED

**位置**：`do_build()` 1557-1591（判定 + 日志）、1588（写入分支强制 `method=0`）；
`verify()` 2006-2030（**硬失败**）。

**为什么**：Android 11+ 要求 `resources.arsc` 未压缩（且 4 字节对齐）。旧实现只把 arsc 移到第 1 条、
原样复制压缩方法，还无条件打印"STORED + 4 字节对齐"。当前源包恰好是 STORED，所以产物对；
**换一个 DEFLATE 的源包就会装不上，而旧 `verify()` 只会打印、不会失败**。

**改后行为**：
- 构建时若源 arsc `method != 0`：解压后以 `method=0` 重写（重算 CRC/尺寸，v1 摘要按解压内容算），并打印原因；
- 校验时 `STORED=False` 或 `4 字节对齐=False` ⇒ `ok = False`（退出码 1）。

**改前 / 改后（`_signfix_test.py` P5/P5b）**：

| 场景 | 改前 | 改后 |
|---|---|---|
| 源 arsc 是 DEFLATE（method=8） | 输出仍 `method=8` | 输出 `method=0`（`src method=8 -> out method=0, first=resources.arsc`） |
| 一个"签名全对但 arsc 是 DEFLATE"的包 | `verify()=True`（只打印） | `verify()=False`（`if not _stored: ok=False`） |
| 现有产物 `BA_noroot_v1.apk` | `method=0` | `method=0`，`第 1 条, STORED=True, 4 字节对齐=True`（不误伤） |

> 造"签名全对但 arsc 是 DEFLATE"的包的办法：临时把 `ZipWriter.add` 包一层，让 `resources.arsc`
> 以 DEFLATE 写入（CRC/尺寸按压缩后重算，v1/v2/v3 摘要照常由模块自己算），于是签名与内容一致、
> 只有 arsc 的压缩方法违规 —— 这样能单独证明 `verify()` 拦的是"arsc 方法"而不是别的。

---

### P1-6 源包身份校验 + v3 minSdk 取自清单

**位置**：
- `read_manifest_identity(buf)`（1345-1392）：用现成的 `axml_parse` 读 `package` / `versionCode` /
  `versionName` / `uses-sdk.minSdkVersion` / `uses-sdk.targetSdkVersion` / `application.networkSecurityConfig`；
- `check_source_identity(src, force=False)`（1393-1447）：四项硬校验 + `NSC_ENTRY` 存在性；
- `do_build()` 1455：`min_sdk = check_source_identity(src, force=force)`；
- 1625：`build_v3_signer(digest, [cert], pub, key, min_sdk, MAX32)`（不再用 `MIN_SDK` 硬编码）；
- CLI 2521：`--force`；`main()` 把它透传给 `do_build`。

**为什么**：`PKG_NAME/APK_VERSION_CODE/TARGET_SDK/NSC_RES_ID` 原本是死常量，传错 `--src`（国际服/旧版/别的游戏）
照样建包；`MIN_SDK=24` 硬编码会让 v3 的 `minSdkVersion` 与清单不一致（当前恰好都是 24，换包就错）。
`networkSecurityConfig` 资源 ID 不对的话，换 `res/Dk.xml` 是**白换**（arsc 根本没指向它）——这条最隐蔽。

**改前 / 改后（`_signfix_test.py` P6 系列）**：

| 场景 | 改前 | 改后 |
|---|---|---|
| `--src` 的 package 是 `com.example.notbluearchive` | 照建（`SystemExit` 不触发） | `SystemExit(1)`，报 `package = 'com.example…'，期望 'com.RoamingStar.BlueArchive'` |
| 同上 + `force=True` | 无此参数（`TypeError`） | 构建成功（打印 `[!] --force：忽略源包身份不符`） |
| 源清单 `minSdkVersion=21` | v3 `min/max = (24, 2147483647)`（硬编码） | v3 `min/max = (**21**, 2147483647)` |

**真包只读证据**（`_signfix_live.py`，读官方包 50,552 B 的 `AndroidManifest.xml`）：

```
package      = 'com.RoamingStar.BlueArchive'
versionCode  = 73
versionName  = '3.0.2'
minSdk       = 24
targetSdk    = 33
nscResId     = 2131886081  (0x7F120001)
与常量一致: OK
[*] 源包身份: package=com.RoamingStar.BlueArchive versionCode=73 versionName=3.0.2
             minSdk=24 targetSdk=33 nsc=0x7F120001
返回 minSdk = 24
```

⇒ 官方包不 `--force` 直接过；同时 v3 的 minSdk 现在来自清单而非常量。

**自检适配**：`selftest_manifest()`（2249）用模块自己的 `Axml` 生成一个身份正确的
`AndroidManifest.xml`（原来塞的 8 字节假 manifest 会让 P1-6 直接把自检打死）。

---

## 3. 文档纠错（`NOROOT_BUILD.md`）

任务点名的 5 处（行号为**改前**）：

| 原行 | 原文 | 改成 |
|---|---|---|
| 18 | 「v1 + v2 + v3（原包**只有 v1**，没有 APK Sig Block） | 「原包 `cn_base.apk` **本身就带完整的 v1+v2+v3**，见 §1.2；旧版'只有 v1'是探针假阴性」 |
| 67-77 | 「原包**没有 APK Signing Block** … ⇒ 原厂包是 **v1-only**」 | 整节重写为实测表：`cd_offset-16 = APK Sig Block 42`、块 u64 `4,088`、块起始 `2,122,321,920`、四个 ID-value（v2 `0x7109871a` 1,334 B / v3 `0xf05368c0` 1,334 B / `0x881155ff` 13 B / verity `0x42726577` 1,335 B）、v3 min/max `24/2147483647`、`BACN.SF` 有 `X-Android-APK-Signed: 2, 3`；并写清误判根因（`_probe/probe3_sigmin.py:65-70` 只在文件尾 64 B 找 magic，而 magic 在 CD 前 16 B、距文件尾约 4 MB） |
| 424 | 「签名 无 APK Sig Block（v1-only：…）」 | 「签名 v1+v2+v3（不是 v1-only）」+ 块偏移/大小/四个 pair/v3 min-max |
| 463 | 「原包根本没有 APK Signing Block，是 v1-only」 | 「原包本来就有 v2/v3 签名块（§1.2 实测）…本工具不复制旧块，v2/v3 是重新生成的 ⇒ 重打包逻辑不受影响」 |
| （同项说明） | — | 在 §1.2 末尾明确：**工具不复制输入里的旧签名块**（`SrcZip` 读 CD → `ZipWriter` 重写 → `build_block` 现造 v2/v3），旧块在输出里整段丢弃，所以这条纠错**不影响重打包逻辑**，反而让官方包成为 v2 摘要约定的更强参照物 |

---

## 4. 验证方式（可复现）

全部命令都用 DSH 自带 Python（**不是** MSYS2 的）：

```bat
set PY=C:\Users\su\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe

:: 1) 改前基线（0/9）—— 对 .orig 跑同一套断言
%PY% work\ba\noroot\_signfix_test.py --module work\ba\noroot\build_noroot_apk.py.orig --skip-live

:: 2) 改后全量（15/15，含对真包 41,304 条的只读重排）
%PY% work\ba\noroot\_signfix_test.py

:: 3) 模块自检（P1-1/P1-2/P1-4 + GameMainConfig + 打包→校验全链路）
%PY% work\ba\noroot\build_noroot_apk.py --self-test

:: 4) 真包/旧产物只读复核
%PY% work\ba\noroot\_signfix_live.py
%PY% work\ba\noroot\build_noroot_apk.py --verify-only work\ba\noroot\BA_noroot_v1.apk

:: 5) 改前/改后 .SF 与 MANIFEST 原始字节
%PY% work\ba\noroot\_signfix_evidence.py
```

结果矩阵（同一套断言，改前 vs 改后）：

| 断言 | 改前 | 改后 |
|---|---|---|
| P1 `.SF` 有 `X-Android-APK-Signed` 且值正确 | FAIL（`None`） | PASS |
| P2 每行 ≤72 B 且续行能拼回 | FAIL（92 B / 1 行超限） | PASS（70 B / 0 行超限） |
| P3 v1 全量校验（含 5 个负例） | FAIL（无 `verify_v1`） | PASS（正常过、5 个负例全拦） |
| P4 cert/key 不配对拒绝 | FAIL（不拒，`v2 pub != cert SPKI`） | PASS（`SystemExit(1)`） |
| P5 DEFLATE 源 arsc 强制 STORED | FAIL（`method=8`） | PASS（`method=0`） |
| P5b 非 STORED 的包 verify 硬失败 | FAIL（`verify()=True`） | PASS（`False`） |
| P6 包名不符拒绝 / `--force` / v3 minSdk 取自清单 | FAIL ×3 | PASS ×3 |
| **合计** | **0/9** | **15/15** |

外加：`--self-test` PASS（含 `MANIFEST.MF 最长行 70 B ≤ 72`、`有续行`、`.SF 含 X-Android-APK-Signed: 2, 3`、
`v1 结论: OK`）；`--verify-only BA_noroot_v1.apk` 退出码 1（旧产物的 v1 不合格，见 §2 P1-3）。

---

## 5. 没做 / 明确没碰的东西

- **没有**生成 2 GB 产物（`BA_noroot_v1.apk` 仍是旧产物，只被只读打开）。
- **没有**修改 `report\_tmp\cn_base.apk`（只用 `zipfile` 随机读了两处：`AndroidManifest.xml` 50 KB、`META-INF` 三个签名文件）。
- **没有**删除任何既有文件；备份为 `build_noroot_apk.py.orig` / `NOROOT_BUILD.md.orig`。
- 新增的测量/测试脚本都是 `_signfix_*.py` / `_snapshot_*.py`，产物日志 `_*.log`（可随时删）。
  其中：`_signfix_test.py` = 14 项断言测试台（改前/改后通用）；`_signfix_live.py` = 官方包身份 + 旧产物字段只读复核；
  `_signfix_evidence.py` = 改前/改后 `.SF`、`MANIFEST` 原始字节；`_signfix_probe{,2,3}.py` = 一次性测量
  （apksig 常量池、官方行长分布、41,310 段重排比对）；`_snapshot_build_*.py` = 并发写入期间的脚本快照（可用于回滚比对）。
- 未改 v2/v3 的摘要约定、未加 verity padding、未改 zip 对齐方式（审计附录 B 明确"不要改"）。

## 6. 一行结论

**签名层已经完整、可验证**（v1 合规 + `X-Android-APK-Signed` 剥离保护 + v2/v3 + 逐条/整份/证书/PKCS#7 自校验 +
cert-key 与源包身份门槛），**"可分发"还差的唯一硬项是在有 JRE 的机器上用真 `apksigner verify -v --print-certs`
独立验一次本工具的新产物、并做一次真机安装**（本机无 `java`/`apksigner`，只能用自研校验器 + aapt2，属于本机能力的边界，不是签名器的缺陷）。
