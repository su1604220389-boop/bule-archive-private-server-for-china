# `build_noroot_apk.py` 审查报告

> 审查对象：`work\ba\noroot\build_noroot_apk.py`（按 `read`/LF 计数为 1,245 行；任务说明写 1,246，差异来自末尾换行计数口径）
> 目标包：`report\_tmp\cn_base.apk`（2,126,400,085 B / 41,312 entries）
> 实跑产物：`work\ba\noroot\BA_noroot_v1.apk`（2,127,962,985 B / 41,307 entries）
> 日期：2026-11-16
> 审查方式：**静态读码 + 对已存在文件/产物的只读测量 + 独立复算**。
> **没有执行 `build_noroot_apk.py`，没有生成 APK，没有修改任何现有文件**；本文件是唯一新建文件。

---

## 0. 结论摘要

| 问题 | 结论 |
|---|---|
| 有没有会直接导致“装不上 / 卡启动”的硬 bug | **主链上没有找到**。v2/v3 内容摘要、v2/v3 结构、RSA 签名、证书、zip 布局、AXML 都有独立证据；见 §3 |
| 能不能直接当“可分发成品” | **不能**。v1 字段不完整、`--verify-only` 不验 v1、cert/key 与源包身份未校验、GameMainConfig 未接入、没有对**本工具产物**跑过 apksigner 或真机 |
| 最关键的代码缺陷 | ① v1 `.SF` 缺 `X-Android-APK-Signed: 2, 3`；② v1 `MANIFEST.MF` 808 行超过 72 B；③ `--verify-only` 完全不验 v1；④ cert/私钥不配对校验；⑤ `resources.arsc` 的 STORED 未被强制 |
| 最关键的文档错误 | **原包其实有完整的 v2/v3 APK Signing Block**，不是 v1-only；误判来源是 `_probe/probe3_sigmin.py:65-70` 只在文件尾 64 B 找 magic |
| 最关键的缺失能力 | **GameMainConfig / `ServerInfoDataUrl` 没有接进构建流程**；当前工具只能改 `sdk_url`，改不到真正的 state 入口 |

### 0.1 先纠一条已确证的基线事实：`cn_base.apk` 有 v2/v3 签名块

这一条不在任务给的 5 条“已知设计结论”里，但它出现在 `NOROOT_BUILD.md`（§1.2 / §7 / §8）并影响了后续措辞，而且我有**硬证据**，所以必须纠正。

对 `report\_tmp\cn_base.apk` 的只读测量：

| 检查 | 结果 |
|---|---|
| EOCD | `entries=41,312 / cd_size=4,074,047 / cd_offset=2,122,326,016 / comment=0` |
| `cd_offset-16` 起 16 B | **`APK Sig Block 42`** |
| `cd_offset-24` 起的 u64 | `4,088`（块大小）；块起始 = `2,122,321,920`，块头 u64 也是 `4,088` |
| 块内 ID-value pairs | `0x7109871a`（v2，1,334 B）、`0xf05368c0`（v3，1,334 B）、`0x881155ff`（13 B）、`0x42726577`（verity padding，1,335 B） |
| v2 内容摘要 | `36205dd9…`；按“EOCD 的 CD 偏移写成签名块起始”的约定复算，**与块内摘要完全相等**（按原始 EOCD 字节复算则不相等） |
| v3 `minSdkVersion / maxSdkVersion` | `24 / 2147483647`，signedData 里和 signer 里**两处一致** |
| `META-INF/BACN.SF` | 含 **`X-Android-APK-Signed: 2, 3`**（说明签名时确实同时启用了 v2/v3） |

**误判来源已定位：** `_probe/probe3_sigmin.py:65-70` 只读了文件**最后 64 字节**（`f.seek(-64, 2)`）并在其中找 `APK Sig Block 42`。但该 magic 位于 **CD 之前 16 B**，而源包 CD 有 4,074,047 B，magic 距文件尾约 4 MB，所以必然返回 `False`。`NOROOT_BUILD.md:18 / :69 / :77 / :424 / :463` 的“原包没有 APK Signing Block / 只有 v1”就是这条探针的假阴性。

**这条纠错对工具的影响：**
- 本工具是**重建 zip**（只从 CD 读 entries），不复制旧签名块，所以“输入有没有旧块”**不影响**它的重打包路径。
- 但文档里“原包只有 v1”的措辞要改；并且**官方 `.SF` 有 `X-Android-APK-Signed` 而本工具没有**，这正是 §1.1 要修的东西。
- 官方源包反而是比 `Probe13.apk` 更强的**摘要约定参照物**（官方包本身 v2 摘要也符合“pre-block CD offset”）。

### 0.2 审查边界

- 没有执行 `build_noroot_apk.py`。下面的行号、调用链都是静态阅读得到的；数字来自对 `cn_base.apk` / `BA_noroot_v1.apk` / `Probe13.apk` 的只读测量与**独立 Python 复算**，不是本工具 `--verify-only` 的输出。
- 没有 `java` / `apksigner` / `zipalign`。本机只有 `aapt2.exe` 和 `openssl`；`aapt2 dump xmltree` / `dump badging` 是**实际运行过**的（只读），`apksigner verify` **没有跑过**。
- 没有真机；`E30/E38/E42` 的装机记录属于旧的 `zipalign + apksigner` 管线，不等于本工具产物的实测。
- 审查期间同目录出现了 `NOROOT_TLS_RESEARCH.md`（mtime 06:59，**不是本审查创建**，应是并行任务的静态分析）。它与任务基准 #3（“NSC 只管 Java 栈、CA 无净收益”）**结论相反**；本审查不裁决，只在 §2.13 把它作为“跨文档冲突”列出，并说明它对 `--ca`/NSC 价值判断的影响。

---

## 1. 必须修的 bug

> 先给结论：**没有找到会让当前产物直接装不上的 P0**。下面 P1 是“会留下真实风险 / 某些受支持路径下会真失败 / 签名器不合规”的问题，P2 是健壮性或易踩坑问题。每条都标了“是否阻断当前默认路径”。

### P1-1 v1 `CERT.SF` 缺 `X-Android-APK-Signed: 2, 3`

**位置：** `build_noroot_apk.py:764-767`（`build_v1()` 里构造 `.SF`）。

**现状：** 生成的 `.SF` 主体只有 3 行（且只有整份清单摘要）：

```
Signature-Version: 1.0
Created-By: BA-noroot-builder
SHA-256-Digest-Manifest: <base64>
```

**证据：**
- 官方 `META-INF/BACN.SF` 主体含 `X-Android-APK-Signed: 2, 3`。
- 真 apksigner 签的 `Probe13.apk` 的 `META-INF/BA.SF` 也含 `X-Android-APK-Signed: 2, 3`。
- apksig（Gradle 缓存 `apksig-8.6.1.jar`）的 `com.android.apksig.ApkVerifier$Issue` 里有 `JAR_SIG_NO_APK_SIG_STRIP_PROTECTION`，就是“APK 有 v2/v3 但 .SF 没有声明 X-Android-APK-Signed”的对应 issue。

**症状：**
- apksig 里有专门的 `JAR_SIG_NO_APK_SIG_STRIP_PROTECTION` issue；在默认 minSdk 24、APK 同时有 v2/v3 的 verify 场景下，预计会命中（是 warning 还是 error 需实跑确认）。如果它按 error 处理，则 `apksigner verify` 不干净。
- 更实质的是：v1 签名没有声明“本包还应有 v2/v3”，v1-only 客户端无法利用这个头阻止别人把 v2/v3 块剥掉后仍通过 v1 校验。

**影响：** **不阻断 Android 7+ 安装**（minSdk 24，安装时优先 v2/v3；v1 只在回退时用），但属于 v1 签名器**不完整**，必须补齐。

**修法：** 在 `.SF` 主体增加 `X-Android-APK-Signed: 2, 3\r\n`（放在 `SHA-256-Digest-Manifest` 之后、空行之前），然后重新做 `pkcs7_signed_data(key, cert, sf)`；`sf` 字节变了，`.RSA` 和 v2/v3 内容摘要都会重算（现有流程本来就会）。如果以后支持 `--no-v1`，这个头就不该写。

### P1-2 v1 `MANIFEST.MF` 有 808 行超过 JAR 规范的 72 字节

**位置：** `build_noroot_apk.py:760-762`：

```python
mf += 'Name: %s\r\nSHA-256-Digest: %s\r\n\r\n' % (
    name, base64.b64encode(dg).decode())
```

**现状：**
- 输出 `BA_noroot_v1.apk` 的 `MANIFEST.MF` **5,147,484 B**，共 **41,304 个 `Name:` section**。
- **808 行长度 > 72 B，最长 92 B**（例如 `assets/audio/voc_jp/...shirokoridingsuit_battle_tacticalaction_1.ogg`，86 字符 + `Name: ` = 92 B）。
- 官方 `cn_base.apk` 的 `MANIFEST.MF` 采用 signapk 的换行：**最长 70 B，0 行 > 72**，共有 **1,254 条续行**（续行以单个空格开头）；例如
  `Name: META-INF/androidx.lifecycle_lifecycle-viewmodel-savedstate.versi` + ` on`。
- `.SF` 的 `SHA-256-Digest-Manifest` 行是 70 B，没问题；`SHA-256-Digest:` 行是 60 B，也没问题。**问题只在 `Name:` 行。**

**症状：**
- 严格按 JAR 规范（每行 ≤ 72 B）的解析器/工具会拒绝或截断。
- 但 Android 的 `java.util.jar.Manifest` 和 apksig 的 `ManifestParser` 都是**宽松的**：`ManifestParser.class` 里没有 `MAX_LINE_LENGTH` 字段（只有 `ManifestWriter` 有），所以 `apksigner verify` **大概率不会因此报错**；Android 7+ 又优先走 v2，v1 只是冗余。
- 因此这不是当前安装的硬阻断，但它是**规范级缺陷**，且一旦有人把 minSdk 降到 24 以下或 v2/v3 被剥掉，就会暴露。

**影响：** 不阻断当前 Android 7+ 安装；**必须修**，否则不能称 v1 签名为合规。

**修法：** 按 signapk 的格式写 70 B 行（`Name:` 先写 `Name: ` + 前 64 B 左右，剩余部分放续行，续行首字节为空格），所有属性行统一走 `write_manifest_line()`；然后重新计算 `mfb` 的摘要（`build_v1` 现有 `whole` 会自动覆盖）。注意：`SHA-256-Digest` 的 base64 是 44 B，`SHA-256-Digest: ` 16 B，共 60 B，不需要换行；只需保证所有行都 ≤ 70/72 B。

### P1-3 `--verify-only` 完全不验证 v1

**位置：** `build_noroot_apk.py:918-1022`（`verify()`）。它做了：

- 找 EOCD / APK Signing Block；
- 复算 v2/v3 内容摘要（`ChunkHasher`）；
- 用块内公钥验 v2/v3 的 RSA 签名（`_verify_signer()`）；
- `zipfile.testzip()`；
- STORED 4 字节对齐；
- 重名检查；
- `__tpinfo` 残留；
- 解析 `res/Dk.xml` 并打印。

它**没有**：读 `META-INF/MANIFEST.MF`、`CERT.SF`、`CERT.RSA`，没有逐条验 `SHA-256-Digest`，没有验 `SHA-256-Digest-Manifest`，没有验 PKCS#7。

**症状：**
- v1 签名坏了（例如以后有人改了 `v1_items` 的收集顺序、漏掉某个替换条目、或者 `.SF`/`.RSA` 写错），`--verify-only` 仍然会打印 `v2: OK / v3: OK` 并返回 0。
- 文档 §5.1 的“必须看到”清单里也没有 v1 项；§5.0 的 v1 结论是**人工抽查 6 条**，不是工具行为。

**本次实测（只读复算）：** 我独立对 `BA_noroot_v1.apk` 的 **41,304 个 manifest section 全量**（41,259 个非 `META-INF` + 45 个 `META-INF` 普通文件，排除 3 个签名文件）重算 SHA-256，**0 个不匹配**；`.SF` 的 `SHA-256-Digest-Manifest` 与 `MANIFEST.MF` 实际摘要**一致**。也就是说**当前 v1 内容是对的**，只是工具本身不检查。

**影响：** 不会让当前包失败；但会让“校验全绿”失去对 v1 的保证，属于**假阳性风险**，必须修。

**修法：** 在 `verify()` 里加：
1. 解析 `MANIFEST.MF` 的每个 `Name:` section，按条目名流式计算 SHA-256，与 `SHA-256-Digest` 比对；
2. 计算 `MANIFEST.MF` 全字节的 SHA-256，与 `CERT.SF` 的 `SHA-256-Digest-Manifest` 比对；
3. 用 `cert` 的公钥验证 `CERT.RSA` 的 PKCS#7（可以复用 `rsa_verify_sha256`）；
4. （可选）检查 `X-Android-APK-Signed` 是否存在。

### P1-4 没有校验“证书公钥 == 私钥公钥”

**位置：**
- `load_key()`：`build_noroot_apk.py:1113-1149`，PKCS#12 路径把 `key` 和 `cert` 分别取出后直接返回，没有比较；
- `--key-pem/--cert-pem` 路径：`1114-1122`，直接从两个文件各读一个，没有比较；
- `do_build()`：`806` 处 `pub = rsa_public_der(key)`，`cert` 原样用于 v2/v3 和 PKCS#7；
- `_verify_signer()`：`1030-1063` 用块内 `pub` 验签，**不读 cert**，所以自验永远发现不了这种不匹配。

**症状：**
- 用户如果传了不配对的 `--key-pem A --cert-pem B`（或一个含多把 key/多张证书的 PKCS#12），工具会生成：
  - v2/v3 块：`pub` 来自 A，`cert` 是 B；
  - v1：`.RSA` 用 A 签 `.SF`，但证书是 B。
- 工具自验：RSA 签名用 A 的公钥能过 ⇒ 打印 OK。
- Android 安装：v2/v3 验签时要求“签名者公钥 == 第一张证书的公钥”，不匹配 ⇒ 直接拒装（`INSTALL_PARSE_FAILED_NO_CERTIFICATES` 一类）；v1 也会失败。
- 默认路径 `ba_private.keystore` 是 `gen_keystore` 同时生成 key/cert 的，**当前产物没有这个问题**（我核对过：输出块内证书 DER == `ba_private.cert.pem` 的 DER；块内 `pub` == 该证书的 SPKI；见附录 A）。

**影响：** 当前默认路径不触发；但 `--key-pem/--cert-pem` 是文档明确支持的替代路径，**这条路径上会真装不上**。

**修法：** 在 `load_key` 返回前（或 `do_build` 开头）解析证书 SPKI，与 `rsa_public_der(key)` 逐字节比较；不一致直接 `die`。这也顺带能抓住 PKCS#12 多 alias 时“取了第一把 key + 第一张 cert 但不是一对”的情况。

### P1-5 `resources.arsc` 只被“移到第 1 条”，没有被强制 STORED

**位置：**
- `build_noroot_apk.py:846-851`：`order.remove('resources.arsc'); order.insert(0, ...)`，只改顺序；
- `861-871`：对未替换条目，`zw.add(name, e['method'], ...)` 原样复制方法；
- 日志 `850-851` 无条件写“STORED + 4 字节对齐”，但代码没有检查/强制 `e['method'] == 0`；
- `verify()` `1008-1010` 只打印 `resources.arsc: 第 N 条, STORED=...`，即使不是第 1 条或不是 STORED，也不影响 `ok`。

**症状：**
- 本包源 `resources.arsc` 确实是 STORED（只读实测：`compress_type=0`，data offset `2,116,622,724`，`%4==0`），所以**当前产物是正确的**。
- 如果将来换一个把 `resources.arsc` 压成 DEFLATE 的源包（或有人改了输入），工具会原样把 DEFLATE 的 arsc 写进去，仍然打印“STORED + 4 字节对齐”，而 Android 11+ 对 `resources.arsc` 有“未压缩 + 4 字节对齐”的硬要求 ⇒ 安装/资源加载失败；`verify()` 也不会拦（它跳过非 STORED 条目）。

**影响：** 当前输入不触发；属于**换源包就会炸**的潜在 P0。

**修法：**
1. 在 `do_build` 里 `if src.by_name['resources.arsc']['method'] != 0: die(...)`，或者解压后以 STORED 重新写（并重算 CRC/大小）；
2. 在 `verify()` 里把“`resources.arsc` 是第 1 条且 STORED”作为**硬失败**，不是只打印。

### P1-6 源包身份未校验，`MIN_SDK` 硬编码

**位置：** `build_noroot_apk.py:48-58` 定义了：
`PKG_NAME` / `APK_VERSION_NAME` / `APK_VERSION_CODE` / `MIN_SDK` / `TARGET_SDK` / `NSC_RES_ID`，
但实际被使用的只有 `MIN_SDK`（`898` 行传给 `build_v3_signer`）；`PKG_NAME`、`APK_VERSION_CODE`、`APK_VERSION_NAME`、`TARGET_SDK`、`NSC_RES_ID` **完全没有被引用**（grep 可验证）。

**症状：**
- 传错 `--src`（例如国际服包、旧版本、别的游戏）时，工具照样重打包 + 重签，不会报错；产出的包可能包名/版本都不对。
- v3 的 `minSdkVersion` 固定 24；如果源包实际 minSdk 不是 24，v3 signer 的 minSdk 与 APK 不一致（对当前包恰好是 24，没问题）。

**影响：** 不会让**正确的**源包失败；属于“用错输入时没有保护”。当前 `cn_base.apk` 的 aapt2 badging 是 `com.RoamingStar.BlueArchive / 73 / 3.0.2 / minSdk 24 / targetSdk 33`，与常量一致。

**修法：** 在 `do_build` 开头用现有的 `axml_parse` 解析 `AndroidManifest.xml`，校验 `package`、`versionCode`、`uses-sdk` 的 min/target；v3 的 minSdk 用源包值（或显式断言 `== MIN_SDK`）。这也会把 `PKG_NAME` 等常量变成“活的”。

### P2-1 2^31 超限检查在“写完 2.1 GB 之后”

**位置：** `build_noroot_apk.py:890-891`：

```python
if entries_size + len(cd) + 4096 > MAX32:
    die('输出将超过 2^31-1，需要 Zip64，本工具不支持', 2)
```

**症状：**
- 此时 `tmp` 已经写了完整的 2.1 GB；`die` 之后不会删除 `tmp`，也不关闭 `src.f`。失败一次会留一个 2 GB 的 `.tmp`。
- `4096` 是经验余量：当前 v2+v3 块是 2,900 B，够；但如果证书更大（多证书/更长 DN），余量不是精确值。

**影响：** 只是失败路径的磁盘/清理问题，不影响成功路径。当前产物 2,127,962,985 B，距 2^31-1 还有 ~19.5 MB，安全。

**修法：** 先按 key/cert 长度算出 v2/v3 块的精确大小（或先构造 block），再在写第一个字节前判断；失败时 `os.unlink(tmp)`。

### P2-2 `--ca` 与 `--ca-mode user/system` 的静默改写

**位置：** `build_noroot_apk.py:812-816`：

```python
if ca_mode not in ('both', 'bundled'):
    log('[!] 给了 --ca 但 --ca-mode=%s，按 both 处理' % ca_mode)
    ca_mode = 'both'
```

**症状：** 用户传 `--ca ca.crt --ca-mode system`，本意是“只要系统 CA + 内置 CA”，实际会被改成 `both`，于是 NSC 里多一个 **`src="user"`**。多一个信任源通常不是安装问题，但和用户意图不符；如果用户不知道，会以为 `user` 没被信任。

**影响：** 语义问题，不阻断。**修法：** 直接 `die` 要求显式 `--ca-mode both/bundled`，或保留但把日志改成显式警告。

### P2-3 `patch_sdk_url` 的严格 UTF-8 与“只改顶层 key”

**位置：** `build_noroot_apk.py:773-782`。

**症状：**
- `data.decode('utf-8')` 是严格模式；当前 `assets/SDKConfigSettings.json` 是合法 UTF-8（我实测：2,840 B，中文 `plist` 字段是 UTF-8，`json.loads` 通过），所以当前没问题。但将来这个 asset 如果是 GBK/BOM/带非法字节，会抛未捕获的 `UnicodeDecodeError`，不是友好的 `die`。
- 正则只匹配 **顶层键** `"sdk_url"`；同一份 JSON 的 `ali.internet_detection.auto_url.http/mtr` 里还有 **`https://sdk-api.yostar.cn`**（我实测有 3 条），这些不会被改。如果 SDK 的网络诊断也用这些地址，改完 `sdk_url` 后仍会访问官方地址。这不是构建 bug，但属于“改 sdk_url”的能力边界。
- 只做 `json.loads(out).get('sdk_url') != new` 回读；如果 `new` 含非法 JSON 字符会 `die`，OK。

**修法：** `try/except UnicodeDecodeError` 转成 `die`；如果需要“全量指向自有服务”，把 `auto_url` 也纳入替换（或明确写进文档“只改顶层”）。

### P2-4 `--keypass` / `--alias` 解析了但没用

**位置：** `build_noroot_apk.py:1203-1204` 解析 `--keypass` / `--alias`；`load_key()` `1128-1147` 用 `openssl pkcs12 -nodes` 取“第一个私钥 + 第一张证书”，**不按 alias 选**。

**症状：** 如果 PKCS#12 里有多个 alias，可能取到不是用户以为的那一对；`--keypass` 完全没参与。默认 `ba_private.keystore` 只有一个 alias，没问题。

**修法：** 用 `-name <alias>` 取指定条目，或明确只支持单条目的 PKCS#12 并在多条目时 `die`。

---

## 2. 可疑但不能确定的

下面这些**不是已证实的失败**，但要么依赖未验证的假设，要么在特定条件下会出问题。按“需要什么证据”列出。

### 2.1 `.SF` 没有逐条 `Name:` 摘要

- 官方 `BACN.SF` 有 **41,309** 个 `Name:` section；`Probe13.apk` 的 `BA.SF` 有 **5** 个；本工具生成的 `CERT.SF` **只有 128 B，0 个**，只有 `SHA-256-Digest-Manifest`。
- JAR 规范允许“整份 MANIFEST 摘要”这种优化；Android 的 `JarVerifier` 和 apksig 的 `V1SchemeVerifier` 都有 `SHA-256-Digest-Manifest` 路径（apksig 里对应 `JAR_SIG_NO_MANIFEST_DIGEST_IN_SIG_FILE` 是“缺整份摘要”的 issue，本工具不触发）。
- 但 apksig 的 `Issue` 里还有 `JAR_SIG_NO_ZIP_ENTRY_DIGEST_IN_SIG_FILE`：如果它在“有整份摘要”时也会对每个条目发 issue，`apksigner verify` 可能产生大量警告（不影响 exit code 的话）。
- **需要证据：** 在装好 JRE/apksigner 的机器上对 `BA_noroot_v1.apk` 跑 `apksigner verify -v`，看 v1 的 issue 列表。如果出现 `NO_ZIP_ENTRY_DIGEST_IN_SIG_FILE`，就按 signapk 的方式补逐条 section（每个 section 的摘要是该 section 的原始字节，不是条目内容）。

### 2.2 没有 verity padding，CD 偏移不是 4096 对齐

- 官方块的 `0x42726577` 是 apksigner 加的 verity padding，块总长 4,096，CD 偏移 4096 对齐；本工具块 2,900 B，CD 偏移 `2,123,829,032`（不保证 4096 对齐）。
- Android 安装和 `apksigner verify` 都**不要求**这个 padding；它是 apksigner 为 fs-verity/对齐加的。没有证据表明缺失会导致安装失败。
- **需要证据：** `apksigner verify` + 真机安装；如果都过，就把它当“与 apksigner 字节风格不同”而不是 bug。

### 2.3 `raw` 对齐用“裸 0”不是合法 extra 序列

- `ZipWriter._extra()`（`670-678`）在 `align_mode='raw'` 下返回 `b'\x00' * pad`，`pad ∈ {0,1,2,3}`。ZIP 的 extra field 形式上是 `(u16 id, u16 size, data)*`，裸 0 不构成合法记录。
- 但源包本身就是这个风格（我实测 41,312 条的 extra 长度分布 `{0:11152, 1:10061, 2:10147, 3:9952}`，内容全是 0；官方包的 arsc/Dk/E5 的 extra 也是 0/1 个 0），说明 Android/aapt2/apksigner 都不解析 extra 内容，只按长度跳过。
- **需要证据：** 如果某个校验器（例如某些发行渠道的扫描器）严格解析 extra，可能报 malformed。当前没有观察到。

### 2.4 4 字节对齐只对 `extractNativeLibs=true` 成立

- 源 manifest 的 `<application android:extractNativeLibs="true">`（`NOROOT_BUILD.md:430`，且 `lib/arm64-v8a/libil2cpp.so` 在源包里其实是 DEFLATE，实测 `compress_type=8`）。因此“`.so` 不需要 4 KB/16 KB 页对齐”的结论成立。
- 如果将来源包的 `extractNativeLibs` 变成 `false`，未压缩的 `.so` 必须按页对齐（4 KB；Android 15+ 16 KB），而本工具只做 4 字节对齐 ⇒ `dlopen` 会因 `mmap` 偏移不对齐失败。工具没有检查这个 flag。
- **需要证据：** 当前包是 true，无需动作；但建议在 `do_build` 里读 manifest 的 `extractNativeLibs`，若为 false 则 `die` 或加 `--align-page`。

### 2.5 `apksigner verify` 从未对**本工具产物**跑过

- `NOROOT_BUILD.md:345-347` 的“真 apksigner 样本交叉验”是拿 `Probe13.apk`（apksigner 签的**输入**）去验**本工具的校验器**；这证明“本工具能读懂 apksigner 的格式”，**不证明“本工具写出的格式 apksigner 能接受”**。
- 本机没有 `java` / `apksigner`；我也没有跑（任务要求不执行工具、不生成 APK）。所以 `apksigner verify` 的结论只能是“结构/数学上应该过”。
- 我做了等价强度的独立复算：v2/v3 内容摘要约定在**官方源包**和 Probe13 上都能复现；本工具产物的 v2/v3 块结构、v3 min/max、RSA 签名、块内证书/公钥全部自洽（附录 A）。
- **需要证据：** 有 JRE 的机器上 `apksigner verify -v BA_noroot_v1.apk`，重点看 v1 issue 和 `Verified using v1/v2/v3` 三行。

### 2.6 NSC 的运行时行为没有实测

- `aapt2 dump xmltree` 确认结构是 `network-security-config → base-config → trust-anchors → certificates(src="system") / certificates(src="user")`；`aapt2 dump badging` 确认包名/版本/min/target 不变。
- `system` 与 `user` 的并集、`base-config` 里 `trust-anchors` **整体取代**平台默认集、`src` 用无命名空间字符串，这些是 `NOROOT_BUILD.md:151-170` 逐字核对 AOSP `XmlConfigSource` 得出的**源码级结论**，不是本机实测。
- **需要证据：** 真机冷启动后抓 `logcat` 的 `Curl error 60` / `UnityTls error code: 7`；以及装用户 CA 后 Java 栈是否真的不再报证书错误。这属于产品验证，不是构建器 bug。

### 2.7 `__tpinfo` 删除的充分性

- 源包确实只有 5 个 `tpinfo` 文件（`assets/__tpinfo.{tp,tsc,tsc.sig,tsd,tsd.sig}`），工具精确删了这 5 个；`__tpcfinfo.tsa`、`__tpsinfo.t.p.sin`、`tpginf.dat` 保留；工具没有“扫描其他完整性文件”的能力。
- 我扫了源包条目名：`acinfo`、`integrity`、`checksum`、`verify` 均 0 命中，`.sig` 只有那 2 个；工作区已有的二进制扫描输出（`_scan_big.txt` / `_scan_small.txt` / `_tprt_strings.txt`）里也没有 `tpinfo`/`__tpsinfo`/`__tpcfinfo`/`tpginf` 的额外引用。但这只是**条目名 + 已有扫描的静态名单**；“删掉这 5 个 ⇒ ACE 整段跳过”是旧版 E 系列的经验，**没有在本 3.0.2 包上真机验证**。
- **需要证据：** 真机启动 45 s+ / 进大厅；如果闪退，先按 `NOROOT_BUILD.md` §4 #12 清 ACE 记账再复测。

### 2.8 `--align-mode d935` 没有在 2 GB 包上实测

- 代码 `676-678` 的格式是 `u16 0xD935 | u16(2+pad) | u16 4 | pad×0`，与 signapk 一致；`pad` 的计算也对。
- 但默认 `raw` 与源包一致，`d935` 只是“给只认 signapk 布局的校验器”备用；历史 E32/E34 用过 `0xd935` 能进主程序，但那是旧管线。
- **需要证据：** 如果确实要用 `d935`，跑一次 `aapt2`/真机；否则保持默认 `raw`。

### 2.9 `res/E5.ogg` 内置 CA 的副作用

- `--ca --ca-mode both/bundled` 会把唯一的 raw 资源 `res/E5.ogg`（6,401 B，zxing 提示音）替换成 CA DER，并把 NSC 的 `src` 指向 `0x7F0E0000`。
- 如果游戏/扫码库在扫码时 `MediaPlayer` 播这个 raw，可能抛异常（是否被捕获未知）；`NOROOT_BUILD.md:258` 只说“变哑”。
- 默认 `--ca-mode user` 不触发；文档也建议默认不开。**需要证据：** 如果要用这个模式，测一次扫码/提示音路径。

### 2.10 `cleartextTrafficPermitted=true` 被保留

- 原包 `res/Dk.xml` 就是 `cleartextTrafficPermitted="true"`；工具原样保留。这不是 bug，但意味着改后的 NSC **仍然允许全局明文 HTTP**。如果目标环境只走 HTTPS，可以改成 false；如果依赖 http 网关，就保持 true。**需要产品决策，不是代码 bug。**

### 2.11 `sdk_url` 只改顶层，`auto_url` 仍指官方

- 见 P2-3。`assets/SDKConfigSettings.json` 里 `ali.internet_detection.auto_url.http/mtr` 仍有 `https://sdk-api.yostar.cn`（以及 `static.bluearchive-cn.com` / `gs-api.bluearchive-cn.com`）；这些是 SDK 的网络诊断目标，不一定是登录主路径。**需要证据：** 改完 `sdk_url` 后抓 SDK 请求，确认是否还有官方诊断请求；如果有且不希望有，扩展替换范围。

### 2.12 签名变了 ⇒ 必须卸载重装

- `NOROOT_BUILD.md` §4 #10 已写；当前工具没有在包里写任何“版本/签名提示”，也没法避免 `INSTALL_FAILED_UPDATE_INCOMPATIBLE`。
- 这不是 bug；发版说明必须写清楚“先卸载旧包（含官方包），再装”；`versionCode` 仍是 73，不能靠覆盖升级。

### 2.13 跨文档冲突：NSC 到底管不管 `/api/state`（未决，直接影响 `--ca` 的价值）

- **任务给的基准 #3 + `NOROOT_BUILD.md` §2.2**：NSC 只作用于 Java/Conscrypt；`/api/state` 走 native libcurl + UnityTLS，`/api/account/auth` 走 BestHTTP，读 `AndroidCAStore` ⇒ 把 CA 打进 APK **没有净收益**。
- **`NOROOT_TLS_RESEARCH.md`（06:59，非本审查创建）给出相反结论**：
  - `libunity.so` 里有一整块 JNI 反射字符串表：`javax/net/ssl/TrustManagerFactory`、`getDefaultAlgorithm`、`getInstance`、`getTrustManagers`、`init(KeyStore)`、`X509TrustManager`、`checkServerTrusted`、`getAcceptedIssuers`；
  - `AndroidCAStore` / `cacert` / `trusted_ca` / `TrustedCertificateStore` 在 `libunity.so` 里 **0 命中**；
  - `libil2cpp.so` 里没有 TLS 校验代码；BestHTTP 自带 BouncyCastle（`ICertificateVerifyer` / `NotifyServerCertificate`），也不经 Java 信任管理者；
  - ⇒ 它**推断**：`/api/state` 的 mbedTLS 信任根来自 Java `TrustManagerFactory.getAcceptedIssuers()`，`targetSdk=33` 时这个值由 app 的 `res/Dk.xml` 裁决 ⇒ **NSC 就是 `/api/state` 的开关**；用户库默认被过滤，改 NSC 才有用。
  - 因此它把 B1（NSC + 用户 CA）、B2（NSC + 内置 CA）列为可行路径，并把 C（改 `GameMainConfig` 为 `http://`）排在更前；并明确说 B/C **都必须改 GameMainConfig**。
- 两边都是**静态证据 + 推断**，没有真机实测；本审查**不裁决**，但这对本工具的**价值判断**有影响：
  - 若 TLS 文档成立：`--ca` 的“内置 CA”是**零人工**路径，不是“无净收益”；NSC 补丁是主杠杆；而 GameMainConfig 未接入（§4.1）就是 B/C 两条路都卡住的同一处。
  - 若旧结论成立：NSC 只影响 Java 栈，`--ca` 主要是给 Java SDK 流量兜底。
- **需要证据**：按 `NOROOT_TLS_RESEARCH.md` §6 的 E0/E1/E2 真机判据（冷启后 `Curl error 60` / `UnityTls error code: 7` 是否消失、`GET /api/state` 是否 200）钉死。
- 两个**不是矛盾**的差异：① 该文档的 NSC 产物是 **552 B**，本工具是 **560 B**，两者都是合法 AXML（`aapt2` 能读），差异只是字符串池/属性布局/保留哪些属性；② 该文档的 B2 方案要“新增 `res/raw` + 改 `resources.arsc`”，而本工具的 `--ca-mode both/bundled` **复用既有 `res/E5.ogg`（`0x7F0E0000`）、不碰 arsc**——这是本工具的净优势，代价是覆盖 zxing 提示音。
- **对构建器的影响**：无论哪边成立，构建器本身的实现（NSC 结构、CA 槽位、签名、zip）都不变；变的只是“要不要默认开 `--ca`”和“GameMainConfig 的优先级”，所以本报告 §1/§3 的结论不受这条冲突影响。

---

## 3. 设计上正确的部分（明确列出来，避免后续有人瞎改）

### 3.1 `resources.arsc` 不需要重编译（本方案的根本）

- 源包 `android:networkSecurityConfig` 的值是 `TYPE_REFERENCE 0x7F120001`（属性 res-id `0x01010527`）；arsc 对该 ID 只存字符串 `"res/Dk.xml"`。
- 工具只替换同名 zip 条目 `res/Dk.xml`，**不碰 arsc、不碰 manifest、不新增资源 ID**。这是正确的；不要为了“改 XML”去重编译 arsc。
- 注意：本工具**没有**强制 arsc 为 STORED（见 P1-5）；当前源包 arsc 是 STORED，所以产物正确。

### 3.2 AXML 写入器

- `StringPool`（`400-428`）：UTF-8 flag `0x100`、`stringsStart=28+4*count`、每个字符串写 UTF-16 长度 + UTF-8 长度、结尾 4 字节对齐；`aapt2` 能解析。
- `Axml.start/end`（`431-456`）：START 节点 36 B + 20 B/属性，`attributeStart=20`、`attributeSize=20`、`Res_value` 为 `u16 size=8 + u8 res0 + u8 type + u32 data`；END 节点 24 B；空 `RES_XML_RESOURCE_MAP`（`0x0180`, size 8）；`aapt2 dump xmltree` 验证通过。
- `src="system"` / `src="user"` 写成 `TYPE_STRING`（`0x03`），`raw` 和 `data` 都是字符串池索引；`aapt2` 打印 `src="system" (Raw: "system")` / `src="user" (Raw: "user")`。这是对的。
- 资源引用模式（`--ca-mode both/bundled`）写 `TYPE_REFERENCE`（`0x01`），`data=0x7F0E0000`，`raw=0xFFFFFFFF`；与 AOSP `ResourceCertificateSource` 的读取方式一致。
- `base-config` 的 `cleartextTrafficPermitted` 保持 `TYPE_INT_BOOLEAN` + `true`，与源包一致。
- **不要**把 `res/Dk.xml` 改名成 `res/xml/http.xml`：arsc 里存的是 `res/Dk.xml`。

### 3.3 NSC 语义

- `base-config` 里写了 `<trust-anchors>` 就**整体取代**平台默认信任集；工具强制先写 `system`，再写 `user`，所以公开 HTTPS 不会挂。这是对的；不要改成“只写 user”。
- `system` 与 `user` 两个 `<certificates>` 的 anchor 集合是并集（`addAll`）。
- `src` 是无命名空间属性（`ns=0xFFFFFFFF`），与 AOSP `getAttributeResourceValue(null, "src", -1)` / `getAttributeValue(null, "src")` 的读取方式一致。

### 3.4 v2/v3 签名：核心约定是对的（最重要，别“修”错）

- `ChunkHasher`（`618-651`）：每 1 MiB 一块，`SHA256(0xA5 || u32le(len) || chunk)`；最终 `SHA256(0x5A || u32le(块数) || 各块摘要)`；跨 3 段（`[0, block_start)`、CD、EOCD）**每段独立分块**。我用同一算法对：
  - **官方 `cn_base.apk`** 的 v2 摘要；
  - `Probe13.apk`（真 apksigner 签）的 v2 摘要；
  - 本工具产物 `BA_noroot_v1.apk` 的 v2/v3 摘要；
  全部复算成功（见附录 A）。
- **EOCD 的 CD 偏移字段在算摘要时必须写成“签名块起始”**（`do_build` 的 `entries_size`），而不是最终文件里 CD 的实际偏移（`entries_size + len(block)`）。这不是笔误：官方包和 Probe13 都按这个约定通过；如果谁把它“修正”成原始 EOCD 字节，v2/v3 会立刻失效。
- 顺序：工具先写完全部 aligned entries、再算 v2/v3 摘要、再在 `entries_size` 插块、最后写 CD/EOCD ⇒ **v2 签名在 align 之后**，顺序正确（没有“先签名再对齐”的经典错误）。
- 签名块插入位置：所有 entries 之后、Central Directory 之前；EOCD 在块之后；`build_block` 的 `sz = len(body) + 8 + 16`、前后两个 u64 + `APK Sig Block 42` 都正确。
- v2 signer 结构：`lp(sd) + lp(sg) + lp(pub)`，`sd = lp(digests) + lp(certs) + lp(attrs)`；v3 signer 在 `sd` 里和 signer 里都带裸 `u32 minSDK / maxSDK`；`24 / 0x7FFFFFFF` 与官方一致；v3 无 `proof-of-rotation` 对“单 signer、新 key”是合法的。
- RSA：`0x0103`（RSASSA-PKCS1-v1_5 + SHA-256），2048-bit；我独立用块内公钥复算 v2/v3 签名，**都通过**。
- 块内证书：与 `ba_private.cert.pem` 的 DER **完全一致**；块内 `pub` 与该证书的 SPKI **完全一致**（见附录 A）。默认路径下 Android 的“签名者公钥 == 第一张证书公钥”检查会过。
- **不要**为了“和 apksigner 字节完全一样”去加 verity padding/改块大小；当前结构已经能通过摘要/签名/证书检查。

### 3.5 v1 签名

- 内容摘要：`v1sink` 在写 zip 时对流式解压后的数据算 SHA-256（STORED 直接算、DEFLATE 用 `zlib.decompressobj(-15)`）；我用独立脚本对 **41,304 个 section** 全量复核，**0 不匹配**。
- `CERT.SF` 的 `SHA-256-Digest-Manifest` 对整份 `MANIFEST.MF` 计算；我复核**一致**。
- `CERT.RSA` 是 detached PKCS#7 SignedData；`openssl smime -verify` 在文档里已通过；结构上 `issuerAndSerialNumber`、`digestAlgorithm`、`signatureAlgorithm` 都对。
- 旧签名文件 `META-INF/{BACN.SF,BACN.RSA,MANIFEST.MF}` 被 `OLD_SIG_RE`（`69-74`）+ `do_build`（`841-845`）整组剔除；输出里只剩 `META-INF/{MANIFEST.MF,CERT.SF,CERT.RSA}`，无重名。
- 排序：JAR 规范**不要求** MANIFEST section 排序；原包 signapk 输出的是字典序，本工具按 zip 写入序（`resources.arsc` 先，其余保持源顺序）。Android/apksig 都按条目名查 section，**顺序不同不是 bug**；只是和 signapk 逐字节 diff 会看到差异。
- 行宽：`SHA-256-Digest:` 行 60 B、`SHA-256-Digest-Manifest:` 行 70 B，均不需要续行；本工具把这两类行写对了，**只有 808 个 `Name:` 行超 72 B**（P1-2）。
- 新 `MANIFEST.MF` **不**列 3 个签名文件、**列**了 45 个 `META-INF` 普通文件（和原包 signapk 行为一致）；条目数 `41,304 = 41,259 非 META-INF + 45 META-INF`。
- 缺的是 §1.1 的 strip-protection 头和 §1.2 的 72 B 换行；**内容摘要本身没有问题**。

### 3.6 ZIP 重打包

- `SrcZip`（`565-612`）用 `zipfile` 读 CD，按 `header_offset` 读本地头，按 `csize` 流式搬运压缩流；对 DEFLATE 只解压用于 v1 摘要，不重压。
- 输出 41,307 条；`resources.arsc` 第 1 条、STORED、`data_offset=44`（`%4==0`）。
- 我逐条对比了所有被复制条目的 `(compress_type, CRC, compress_size, file_size)`：**0 差异**；`resources.arsc`、`AndroidManifest.xml`、`classes.dex`、`libil2cpp.so`、`assets/SDKConfigSettings.json`、`GameMainConfig` 与源包 **逐字节相同**。
- `.so`：源包 24 个 `lib/arm64-v8a/*.so` **全部是 DEFLATE**（`NOROOT_TLS_RESEARCH.md` §0 也测到；我实测 `libil2cpp.so` 是 `compress_type=8`），工具原样复制。因为 manifest 是 `extractNativeLibs="true"`，安装时会解压，**不需要 STORED/页对齐**；这是当前包的正确前提（若改成 false 见 §2.4）。
- STORED 条目全部 4 字节对齐（实测 40,702 条 STORED，0 条错位）；本地 extra 长度分布 0~3，与源包同风格。
- 条目无重名（`verify()` 也查）；输出 2,127,962,985 B < 2^31-1，不需要 Zip64；`eocd()` 的 entries/CD size/CD offset 都正确。
- **注意：** 这是“当前源包 + 当前开关”的正确性；P1-5（arsc STORED）和 2.4（页对齐）是换源包/改 manifest 时的边界。

### 3.7 条目清单

- 删：`assets/__tpinfo.{tp,tsc,tsc.sig,tsd,tsd.sig}` 恰好 5 个；源包里也只有这 5 个 `tpinfo`，`.sig` 也只有这 2 个。
- 保留：`assets/__tpcfinfo.tsa`、`assets/__tpsinfo.t.p.sin`、`assets/tpginf.dat`、45 个 `META-INF` 普通文件、`META-INF/com.android.games.engine.build_fingerprint`。
- 不碰：`libil2cpp.so`、`libunity.so`、`libtprt.so`、`libairisgcore.so`、`classes.dex`/`classes2.dex`、包名、加载布局；没有新增 `.so`/`.dex`。这正好避开 `NOROOT_BUILD.md` §4 #9 的 ACE 红线。
- 这些与 `_dd4-integrity.md` 的“删 5 件 ⇒ 跳过自身完整性”一致；但“是否真的跳过”仍要真机验证（见 2.7）。

### 3.8 `assets/SDKConfigSettings.json`

- 该条目是 STORED，2,840 B；工具用正则只替换顶层 `"sdk_url"` 的值，保留其余字节；`json.loads` 回读校验。
- 当前文件是合法 UTF-8（中文 `plist` 字段是 UTF-8，不是 GBK）；`sdk_url` 只出现 1 次顶层键。
- 未传 `--sdk-url` 时完全不改；`BA_noroot_v1.apk` 里仍是 `https://sdk-api.yostar.cn`，与文档“样本”说明一致。

### 3.9 可安装性元数据

- `AndroidManifest.xml` 逐字节不变；`aapt2 dump badging` 实测：
  `package: name='com.RoamingStar.BlueArchive' versionCode='73' versionName='3.0.2'`，`minSdkVersion:'24'`，`targetSdkVersion:'33'`。
- `resources.arsc` 逐字节不变；`res/Dk.xml` 只换内容，长度 264 → 560；arsc 路径字符串不变。
- 因此“包名/版本/min/target/资源 ID 不变”这条是**代码 + 实测**都成立的。

### 3.10 密钥/证书生成

- `rsa_generate()` 用 `secrets`，2048-bit，CRT 参数齐全；`rsa_private_pem` 是 PKCS#1；`build_self_signed_cert` 是合法的 v3 自签证书（`basicConstraints cA=TRUE`，2000–2049）；`openssl x509` 能读，指纹 `94:FA:99:7B:…` 与文档一致。
- `pkcs7_signed_data` 的 `issuerAndSerialNumber` 用的是证书真实的 issuer/serial；OK。
- 默认 `ba_private.keystore` 是 PKCS#12（`load_key` 用 openssl 读；JKS 会明确 `die`）。

---

## 4. 缺失的能力

### 4.1 GameMainConfig / `ServerInfoDataUrl` 没有接进流程（最重要）

- 国服 3.0.2 的 state 入口在 `assets/bin/Data/e37c46fea17834108a4756797197d05a`（5,212 B，`GameMainConfig`），`ServerInfoDataUrl` 的值是：
  `["https://state-api.bluearchive-cn.com/api/state","https://stateqc-api.bluearchive-cn.com/api/state"]`
  （`GAMEMAINCONFIG_CN.md` §6/§8，`_extract_cn/` 有解密产物和 `PATCHED_*.bin`）。
- `build_noroot_apk.py` **完全不碰**这个条目（grep 无 `GameMain`/`bin/Data`/`e37c`）；它只能改 `assets/SDKConfigSettings.json` 的 `sdk_url`，而 `sdk_url` 只影响 SDK/账号段，**不影响 state dispatcher**。
- `_cn_patch.py` 已经能产出 `PATCHED_e37c…bin`（方案 A，28 B 密文差异；方案 B，短值 + 空格补齐），但**没有 `--gmconfig` / `--asset` 之类的入口**把它注入构建。`BA_noroot_v1.apk` 里这个 asset 与源包**逐字节相同**（我核对过）。
- 结论：**现在这个工具做不出“把客户端指到我们 state 服务器”的包**；它只是“重打包 + 重签 + 换 SDK 域名 + 删 tpinfo + 改 NSC”的框架。这是产品级缺口，不是构建 bug。
- `NOROOT_TLS_RESEARCH.md`（并行任务）也把“改 GameMainConfig”列为 B/C 两条 TLS 路径的**共同前置**（免 root 下没有 DNS 控制权），所以这个缺口不是可选项，是 server-switch 的必经点。

### 4.2 通用 asset 替换

- 目前只有 3 个硬编码替换点：`res/Dk.xml`、`assets/SDKConfigSettings.json`、`res/E5.ogg`（可选 CA）。
- 没有“把某个 zip 条目替换成指定文件”的通用参数；因此无法接 GameMainConfig、`global-metadata.dat`、`assets/bin/Data/*`、`assets/aa/*` 等；也**不能改 `libil2cpp.so`**（那需要 so patch/重编译/代码洞，且属于 ACE 红线，当前工具刻意不碰）。
- 建议加 `--replace NAME=PATH`（可多次），自动重算 CRC/大小、重算 v1/v2/v3；这是把 4.1 接进来的最小改动。

### 4.3 v1 校验

- `--verify-only` 不验 v1（P1-3）；需要补 manifest/.SF/.RSA 三条。

### 4.4 cert/key 与源包身份校验

- 不校验证书公钥 == 私钥公钥（P1-4）；不校验源包 package/version/minSdk（P1-6）。
- 建议把这两条做成 `do_build` 开头的硬断言。

### 4.5 外部工具门禁 + 真机

- 工具没有调用 `apksigner` / `zipalign` / `aapt2`（本机也没有 Java）；`--verify-only` 是自研校验器。
- 没有真机安装/启动验证；`E30/E38/E42` 是旧管线，不是本工具产物。
- 建议：在 CI/开发机上加 `apksigner verify -v`、`aapt2 dump badging`、一次真机 45 s 启动 + `logcat` 证书判据。

### 4.6 APK Signature Scheme v4 / 增量安装

- 不生成 `.idsig`；`adb install` 普通方式不需要；如果要用 `adb install --incremental` 或某些分发渠道，需要 `apksigner` 的 v4 输出。当前不是必须。

### 4.7 Zip64

- 工具显式不支持，>2^31-1 直接 `die`；当前 2.128 GB 不需要。如果未来包体再涨 ~19 MB 就触发；需要提前规划（Zip64 会改变对齐/签名块处理）。

### 4.8 页对齐 / `extractNativeLibs=false`

- 只做 4 字节对齐；当前 `extractNativeLibs=true` 所以 `.so` 会被解压安装，不需要页对齐。没有 `--align-page`；如果 manifest 改成 false，需要 4 KB/16 KB 对齐。

### 4.9 其他

- `--keypass` / `--alias` 未使用（P2-4）。
- `--ca` 与 `--ca-mode` 的静默改写（P2-2）。
- `patch_sdk_url` 只改顶层（P2-3）。
- `--no-v1` / `--no-arsc-first` / `--align-mode none` 能产出非标准包，但没有“这会降低可安装性”的显式警告。
- `verify()` 不检查 `X-Android-APK-Signed` / per-entry `.SF` / `resources.arsc` 的 STORED（P1-1/P1-3/P1-5）。
- 没有在 `BA_noroot_v1.apk` 上打 `--sdk-url`；发布前必须重跑。

---

## 5. 一行结论

**结构/数学上它能产出可安装的 v1+v2+v3 APK**（v2/v3 摘要约定与官方包、Probe13 逐项吻合；v1 41,304 条摘要和 `.SF` 摘要全对；aapt2 通过；关键条目逐字节不变），**但它还不是可直接分发的成品**：v1 缺 `X-Android-APK-Signed` 和 72 B 换行、`--verify-only` 不验 v1、cert/key 与源包身份未校验，而且**真正的 state 入口 GameMainConfig 根本没接进流程**；`BA_noroot_v1.apk` 本身仍是官方 `sdk_url` + 官方 state，只能算流水线样本。

> 附注：NSC 是否被 `/api/state` 采纳存在跨文档冲突（任务基准 #3 vs 同目录 `NOROOT_TLS_RESEARCH.md`，见 §2.13）。这不改变构建器的任何正确性结论，但会改变 `--ca` 和 GameMainConfig 的优先级；上真机前不要按任何一边下最终结论。

---

## 附录 A：本次只读复算的关键数字（可复现）

### A.1 官方源包 `report\_tmp\cn_base.apk`

```
size = 2,126,400,085
EOCD: entries=41,312  cd_size=4,074,047  cd_offset=2,122,326,016  comment=0
cd_offset-16 : "APK Sig Block 42"
cd_offset-24 : u64 = 4,088   (block start = 2,122,321,920, header u64 = 4,088)
pairs: 0x7109871a=1,334B  0xf05368c0=1,334B  0x881155ff=13B  0x42726577=1,335B
v2 digest stored = 36205dd9f9c029f9facb77e63850be3855f4e293f33cacbd21d2e31a35121442
v2 digest with pre-block EOCD cdoff = 同值（True）
v3 min/max (sd) = (24, 2147483647) ; (signer) = (24, 2147483647)
META-INF/BACN.SF: "X-Android-APK-Signed: 2, 3"
```

### A.2 输出包 `work\ba\noroot\BA_noroot_v1.apk`

```
size = 2,127,962,985
entries = 41,307
first entry = resources.arsc, header_offset=0, compress_type=0, data_off=44 (%4=0)
res/Dk.xml: 560 B, STORED
META-INF/MANIFEST.MF: 5,147,484 B, STORED, 41,304 sections, max line 92, 808 lines > 72
META-INF/CERT.SF: 128 B, 无 X-Android-APK-Signed
META-INF/CERT.RSA: 1,208 B
signing block: @2,123,826,124, size=2,900, pairs v2=1,418B / v3=1,434B
final EOCD: cdoff=2,123,829,032
v2/v3 content digest stored = d6c7ab095f1e503632eed022d35ce306f748b4dcecea557d9a139951cbfa7673
用 pre-block EOCD cdoff 复算 = 同值（True）；用原始 EOCD 复算 = False（符合 apksigner 约定）
v3 min/max: sd=(24,2147483647), signer=(24,2147483647)
v2/v3 RSA-2048/SHA-256 用块内公钥复算：True / True
block cert DER == ba_private.cert.pem 的 DER（776 B）
block pub (294 B) == 该证书的 SPKI（openssl x509 -pubkey）
v1: 41,304 sections 全量 SHA-256 复核 0 不匹配；.SF 的 SHA-256-Digest-Manifest 一致
zip: 所有被复制条目的 (method,CRC,csize,usize) 与源包 0 差异；STORED 4-byte 错位 0
关键条目 (arsc/manifest/classes.dex/libil2cpp/SDKConfig/GameMainConfig) 与源包逐字节相同
```

### A.3 `aapt2`（实际运行，只读）

```
aapt2 dump xmltree --file res/Dk.xml BA_noroot_v1.apk
E: network-security-config
  E: base-config
    A: cleartextTrafficPermitted=true
      E: trust-anchors
        E: certificates  A: src="system" (Raw: "system")
        E: certificates  A: src="user" (Raw: "user")

aapt2 dump badging BA_noroot_v1.apk
package: name='com.RoamingStar.BlueArchive' versionCode='73' versionName='3.0.2'
minSdkVersion:'24'
targetSdkVersion:'33'
```

### A.4 apksig（从 Gradle 缓存 `apksig-8.6.1.jar` 的 class 常量池读到的 issue 名）

- `JAR_SIG_NO_APK_SIG_STRIP_PROTECTION`
- `JAR_SIG_NO_ZIP_ENTRY_DIGEST_IN_SIG_FILE`
- `JAR_SIG_NO_MANIFEST_DIGEST_IN_SIG_FILE`
- `ManifestWriter` 有 `MAX_LINE_LENGTH`；`ManifestParser` 没有该字段（仅 `readLine`/`mBufferedLine`/continuation 处理），这支持“解析器对长行宽松”的判断。

### A.5 没有执行 / 没有验证

- **没有执行** `build_noroot_apk.py`（没有生成任何 APK，没有跑 `--self-test` / `--verify-only`）。
- **没有** `java` / `apksigner` / `zipalign`；没有对 `BA_noroot_v1.apk` 跑 `apksigner verify`。
- **没有**真机/模拟器；没有验证 NSC、`__tpinfo` 删除、`res/E5.ogg` CA 的运行时行为。
- 本报告的所有“通过”都是**只读测量 + 独立 Python 复算 + aapt2**；不是本工具自验器的输出。

---

## 附录 B：审查时特别确认过的“不要改”的点

1. **不要**把 v2/v3 摘要改成“用最终 EOCD 的 CD 偏移”。当前 `do_build` 用 `entries_size`（签名块起始）是对的；官方包和 Probe13 都这样。
2. **不要**把 `res/Dk.xml` 改名或删除 arsc 路径字符串。
3. **不要**在 `base-config/trust-anchors` 里只写 `user`；必须同时写 `system`。
4. **不要**把 `res/E5.ogg` 的 CA 模式设成默认：它会覆盖 zxing 提示音，并把我们的根 CA 随包分发。**但也不要**把它当成“必然无用”：NSC 是否被 `/api/state` 采纳目前有两份文档冲突（见 §2.13），在真机判据出来前，默认关只是保守选择。
5. **不要**为了让 zip “更标准”而把 STORED 条目改成 DEFLATE 或加 4096 页对齐；当前 `extractNativeLibs=true` 下 4 字节对齐就够，改了反而可能触发别的假设。
6. **不要**删 `__tpcfinfo.tsa` / `__tpsinfo.t.p.sin` / `tpginf.dat`；文档明确说没验证过，保持原样。
7. **不要**把 `libil2cpp.so`/`libunity.so`/`libtprt.so`/`libairisgcore.so` 或 `classes*.dex` 加进替换表；当前工具没碰它们，这是对的。
8. **不要**在 `--verify-only` 里只看到 `v2: OK / v3: OK` 就认为 v1 也没问题；v1 目前是人工复核的，工具不验。
