# BA 国服 · 免 root 改包方案（可执行版）

> 目标包：`com.RoamingStar.BlueArchive` 3.0.2 (versionCode 73)，minSdk 24 / targetSdk 33。
> 源包实测：`report\_tmp\cn_base.apk` = **2,126,400,085 B / 41,312 entries**。
> 产出工具：`work\ba\noroot\build_noroot_apk.py`（纯 Python 标准库，零外部依赖）。
> 本文所有数字都是对着真包量出来的，不是从旧文档继承的；继承来的说法我都标了出处并复核过。

---

## 0. TL;DR

| 项 | 结论 |
|---|---|
| 推荐方案 | **就地重写 `res/Dk.xml`**（不改 manifest、不改 `resources.arsc`、不新增资源）＋ `src="system"` ＋ `src="user"` |
| 改造步骤数 | **6 步**（其中 1 步可选） |
| 要不要 apktool/aapt2 | **不要**。原包资源是 AndResGuard 扁平混淆 + STORED，直接按字节重写即可 |
| 要不要重编译 resources.arsc | **不要**。这是本方案最关键的一条，见 §2.1 |
| 签名 | v1 + v2 + v3（原包 `cn_base.apk` **本身就带完整的 v1+v2+v3**，见 §1.2；旧版"只有 v1"是探针假阴性） |
| 最大风险 | ① 签名变了 ⇒ 必须卸载重装；② `networkSecurityConfig` **管不到** native libcurl/UnityTLS，证书该装还得装（§2.2） |
| 已跑通 | 2,126,400,085 B 真包 → 1.98 GB 改造包，**7.3 s**，v1/v2/v3 全绿；`aapt2` / `openssl` / 真 apksigner 样本三把外部尺子交叉验证过（§5.0） |

**产物**（都在 `work\ba\noroot\`）：

| 文件 | 说明 |
|---|---|
| `build_noroot_apk.py` | 构建/校验/密钥生成/自检，纯 Python，零依赖 |
| `NOROOT_BUILD.md` | 本文 |
| `BA_noroot_v1.apk` | 实跑产出（1.98 GB，**未打 `--sdk-url`**，仅作流水线验证样本；正式发版请带 `--sdk-url` 重跑） |
| `ba_private.keystore` / `.key.pem` / `.cert.pem` | 新生成的签名密钥（alias `ba` / pass `baserver`），cert SHA-256 `94FA997B…` |
| `_probe/` | 量 `res/Dk.xml`、arsc、manifest 用的一次性探针脚本 |

---

## 1. 现状核实

### 1.1 包体与资源解析链（实测）

```
AndroidManifest.xml            STORED  50,552 B   <application> @0x7D54, 11 attrs
  android:networkSecurityConfig  res_id=0x01010527  dtype=0x01(TYPE_REFERENCE)  data=0x7F120001
resources.arsc                 STORED  1,156,308 B   全局字符串池 6,726 串(UTF-8)
  0x7F120001 → type=0x12(xml) key="http" → 路径字符串 "res/Dk.xml"  (arsc 内偏移 0x6E8D)
res/Dk.xml                     STORED  264 B
```

`res/Dk.xml` 解出来的树（**没有** `<trust-anchors>`，也**没有** `<pin-set>` / `<domain-config>`）：

```xml
<network-security-config>
    <base-config cleartextTrafficPermitted="true"/>      <!-- 264 B，共 3 个字符串，UTF-8 池 -->
</network-security-config>
```

同族资源（全包只有 10 个 `xml`）：

```
0x7f120000 filepaths                            res/oS.xml
0x7f120001 http                                 res/Dk.xml   ← 唯一目标
0x7f120002 sdk_file_provider_paths              res/XP.xml
0x7f120003..007 standalone_badge*               res/T_.xml gx.xml c9.xml E1.xml WC.xml
0x7f120008 tapupdate_file_provider              res/XN.xml
0x7f120009 unitywebview_file_provider_paths     res/pM.xml
```

**`res/raw` 只有一个**：`0x7f0e0000 zxing_beep → res/E5.ogg`（6,401 B）。这在 §2.3 里很关键。

### 1.2 签名现状（实测：原包本来就带 v2+v3，不是 v1-only）

> **2026-11-17 纠正**：本节旧版写"原包没有 APK Signing Block / 只有 v1"，**是错的**。
> `AUDIT_BUILD_NOROOT.md` §0.1 已用硬证据推翻，下面是同一批只读测量。

`report\_tmp\cn_base.apk` 的 EOCD 是 `entries=41,312 / cd_size=4,074,047 / cd_offset=2,122,326,016 / comment=0`，
CD **前面**有完整、合法的 APK Signing Block：

| 检查项 | 实测值 |
|---|---|
| `cd_offset-16` 起的 16 B | **`APK Sig Block 42`** |
| `cd_offset-24` 起的 u64 | `4,088`（块起始 `2,122,321,920`，块头 u64 也是 `4,088`） |
| 块内 ID-value pairs | v2 `0x7109871a` 1,334 B / v3 `0xf05368c0` 1,334 B / `0x881155ff` 13 B / verity padding `0x42726577` 1,335 B |
| v2 内容摘要 | `36205dd9…`；按"EOCD 的 CD 偏移写成签名块起始"的约定复算，与块内摘要**完全相等** |
| v3 `minSdkVersion / maxSdkVersion` | `24 / 2147483647`（signedData 与 signer 两处一致） |
| `META-INF/BACN.SF` | 含 **`X-Android-APK-Signed: 2, 3`** |

⇒ 原厂包是 **v1 + v2 + v3**，不是 v1-only。

**旧结论的误判根因**：`_probe/probe3_sigmin.py:65-70` 只读了文件**最后 64 字节**（`f.seek(-64, 2)`）并在其中找
`APK Sig Block 42`。但该 magic 位于 **CD 之前 16 B**，而源包 CD 有 4,074,047 B，magic 距文件尾约 4 MB ⇒ 必然假阴性。

**对重打包逻辑无影响**：本工具**不复制**输入里的旧签名块，只从 CD 读条目重建 zip
（`SrcZip` 读 CD → `ZipWriter` 重写 → `build_block` 现造 v2/v3 块），旧块在输出里被整段丢弃、v2/v3 是重新生成的。
这条纠正只影响文档措辞；反过来，官方包成了**比 `Probe13.apk` 更强的摘要约定参照物**（见 §5.1）。

原包的 v1 签名文件（会被整组剔除并重签）：

```
META-INF/BACN.SF      含 X-Android-APK-Signed: 2, 3（本工具现在也会写，见 build_v1）
META-INF/BACN.RSA
META-INF/MANIFEST.MF
```

⇒ 我们的产物同样是 v1+v2+v3；minSdk=24 下 Android 7+ 走 v2/v3，v1 作兼容冗余 + 降级保护。

### 1.3 压缩与对齐现状（实测 41,312 条全扫）

```
STORED   40,699 条 / 1,950,057,475 B      DEFLATE  613 条
所有 STORED 条目的本地数据偏移 % 4 == 0    （40,699/40,699）
本地 extra 长度分布：0 B×10,539  1 B×10,061  2 B×10,147  3 B×9,952
```

extra 是 **0~3 个裸 0 字节**——这是 **`zipalign` 的风格**（它不加 extra 头，只补零），不是 `signapk` 的 `0xD935` 记录。所以本工具默认 `--align-mode raw`，产出的包和原厂在字节风格上一致；`--align-mode d935` 是给只认 signapk 布局的校验器用的。

### 1.4 工具现状（本机）

```
python  3.12.11    OK        openssl  3.x (msys64)   OK
java / keytool / apktool / apksigner / zipalign      ❌ 全部没有
aapt2.exe                                            ✅ 在 Gradle 缓存里（原生 exe，不需要 JVM）
   C:\Users\su\.gradle\caches\8.11.1\transforms\bedba16cea642164a45bf9eb6e21088d\
   transformed\aapt2-8.6.1-11315950-windows\aapt2.exe
```

⇒ 所以本方案**不依赖** apktool/aapt2 做改包；`aapt2.exe` 只用来做**改后的独立复核**（§5）。
⇒ `ba_private.keystore` **在仓库里不存在**（全盘搜 `*.keystore/*.jks/*.p12` 为 0），只剩
`work\ba\bapatch\e0_signed.apk.idsig` 等 5 个 v4 idsig（私钥不可从 idsig 还原）。
⇒ 因此脚本会**新生成**一把 RSA-2048 密钥；如需沿用旧签名，必须找回那把 keystore。

---

## 2. `networkSecurityConfig` 三条路的可行性

### 2.1 先拆掉一个错误前提：「改 XML 必须重编译 resources.arsc」

**不需要。** 理由（实测）：

- `android:networkSecurityConfig` 的值是 **`TYPE_REFERENCE` 0x7F120001**，不是路径字符串。
- `resources.arsc` 对这个 ID 只存**一字符串** `"res/Dk.xml"`（全包唯一，arsc 偏移 `0x6E8D`）。
- `AssetManager` 是拿这串字去 **zip 里按名找条目**，arsc **不存 zip 偏移、不存文件长度**。
- 所以：**只要 zip 条目名还是 `res/Dk.xml`，内容换成什么都行**，长度也可以变。

⇒ 全流程 **零 resources.arsc 改动、零 manifest 改动、资源 ID 100% 不变**。
这是本方案能稳的根本：改动面只有「一个 zip 条目 + 5 个条目的删除 + 一个 json」。

### 2.2 关键机制纠正：NSC 只管 Java 栈，管不到 native TLS

这一条会决定「要不要把 CA 打进 APK」，必须先说清：

| TLS 栈 | 用在哪 | 信任谁 | NSC 管不管 |
|---|---|---|---|
| Java / Conscrypt（OkHttp、HttpsURLConnection） | 各家 SDK（腾讯、华为 HMS、Adjust…）、`HttpURLConnection` | `TrustManagerImpl` 读 NSC | **管** |
| UnityTLS + native libcurl | `/api/state`（`UnityPlayer/2021.3.56f2`, `libcurl/8.10.1-DEV`） | `AndroidCAStore`：`/system/etc/security/cacerts` + `/data/misc/user/0/cacerts-added` | **不管** |
| BestHTTP/2（.NET/IL2CPP 侧） | `/api/account/auth` | Mono 的证书链实现，同样落到 `AndroidCAStore` | **不管** |

证据链：旧侦察 `_dd3-P4-userCA.md` 明确写过「NSC 只回答 Java 侧这一个问题，真正卡的 `/api/state` 走 native libcurl + UnityTLS」；
Unity 在 `2021.3.48f1` 的 release note 里写「user installed certificates … wouldn't show up in the trusted_ca list」——
说明 Unity 读的是**用户证书库**，不是 NSC。

**两个推论：**

1. NSC 改造**不是**「让登录通过」的关键，它是「让被代理的 Java SDK 流量不炸」的保险。**两件事都得做**。
2. 「把 CA 打进 APK」**不能**替代装证书 —— 因为 native 那条路根本不看 NSC。**净收益为零**。

### 2.3 三条路对比

| | 路线 A：就地改 `res/Dk.xml` | 路线 B：新增 xml + 改 manifest 指向 | 路线 C：把 CA 打进 APK |
|---|---|---|---|
| 改动面 | 1 个 zip 条目 | 新增 arsc 条目 + 重排 arsc + 改 manifest 属性 | 1 个 zip 条目（复用 raw 槽）+ `src` 用资源引用 |
| 要碰 `resources.arsc` | **否** | **是**（新增 ID 必须重排 string/type 表，风险最高） | 否 |
| 要碰 manifest | 否 | 是（属性值改成新 ID，还要保持按 res-id 升序） | 否 |
| 资源 ID 稳定 | ✅ | ❌ 容易撞 ID | ✅（复用既有 `0x7f0e0000`） |
| 用户侧配置 | 装一次 CA | 装一次 CA | 「零配置」——**但只对 Java 栈成立** |
| 副作用 | 无 | 高 | 覆盖 `res/E5.ogg` ⇒ zxing 扫码提示音变哑 |
| 可行性 | ✅ 已实现并验证 | ⚠️ 可行但没必要，收益为零 | ⚠️ 技术可行，AOSP 支持，但 §2.2 使它**没有净收益** |

**AOSP 依据（逐字核对过源码）：**

`XmlConfigSource.parseCertificatesEntry()` 先看资源引用，再看字面量：

```java
int sourceId = parser.getAttributeResourceValue(null, "src", -1);
String sourceString = parser.getAttributeValue(null, "src");
if (sourceId != -1)              source = new ResourceCertificateSource(sourceId, mContext);
else if ("system".equals(sourceString)) source = SystemCertificateSource.getInstance();
else if ("user".equals(sourceString))   source = UserCertificateSource.getInstance();
else if ("wfa".equals(sourceString))    source = WfaCertificateSource.getInstance();
else throw new ParserException(parser, "Unknown certificates src. Should be one of system|user|@resourceVal");
```

- `src` 是**无命名空间**属性（`null, "src"`），和我们生成的 AXML 用 `ns = -1` 一致。
- `base-config` 里**可以**写 `<trust-anchors>`（`parseConfigEntry` 对 trust-anchors 不设 CONFIG_DOMAIN 限制），但**每个 config 元素最多一个**。
- `system` 与 `user` 同时声明时，anchor 集合是**并集**（`addCertificatesEntryRefs` → `addAll`）。
- ⚠️ **`base-config` 里一旦出现 `<trust-anchors>`，会整体取代平台默认信任集，而不是与它合并**
  （`Builder.getEffectiveCertificatesEntryRefs()` 是 replace-if-present）。所以**必须显式写 `system`**，
  只写 `user` 会让所有公开 HTTPS 全挂。这一点已固化进脚本。

### 2.4 推荐

> **路线 A**：就地重写 `res/Dk.xml` 为
> ```xml
> <network-security-config>
>   <base-config cleartextTrafficPermitted="true">
>     <trust-anchors>
>       <certificates src="system"/>
>       <certificates src="user"/>
>     </trust-anchors>
>   </base-config>
> </network-security-config>
> ```
> 264 B → **560 B**，条目名不变，arsc / manifest / ID 全不动。

**路线 C 仍然实现并保留**（`--ca our_ca.crt --ca-mode both`），用于「用户坚决不装证书、且只关心 Java 侧」的场景；
但**默认关**，因为它会把扫码提示音换掉，且换不来 native 侧的任何好处。

---

## 3. 改造清单（6 步，每步：改什么 / 工具 / 怎么验证）

> 一键完成：`build_noroot_apk.py`（脚本内部按 §3 的顺序做完 ①②③⑤⑥，④可选）。
> 下面写的是它每一步具体在动什么，便于人工复核或换工具重做。

### 步骤 0：准备（一次性）

```bat
:: 0-a 生成签名密钥（本次没有旧 keystore，只能新生成）
python work\ba\noroot\build_noroot_apk.py --gen-keystore work\ba\noroot\ba_private.keystore
::   → ba_private.keystore (PKCS#12, alias=ba, pass=baserver) + ba_private.key.pem + ba_private.cert.pem

:: 0-b 原厂包备份（回滚用，务必做）
copy report\_tmp\cn_base.apk work\ba\noroot\_orig\cn_base.apk
```
验证：`openssl pkcs12 -in ba_private.keystore -nokeys -passin pass:baserver -noout` 不报错。

---

### 步骤 ①：重写 `res/Dk.xml`

| 项 | 内容 |
|---|---|
| 改什么 | zip 条目 `res/Dk.xml`（264 B → 560 B，仍是 STORED） |
| 工具 | `build_noroot_apk.py` 自带的 AXML 写入器（**不需要** aapt2/apktool） |
| 生成的字节 | `RES_XML_TYPE(8)` + `STRING_POOL(UTF-8, 8 串, 176 B)` + **空** `RESOURCE_MAP(8)` + 5×START + 5×END（每个 START = 36 + 20×属性数，END = 24） |
| 关键细节 | 属性记录固定 **20 B**（ns4+name4+raw4+Res_value 8）；`attributeSize=20`；`attributeStart=20`；元素 size = `36 + 20*n`；空 resource map 必须保留（原包也是空的，属性和环境靠**名字**匹配而非 res-id） |
| 验证 | `python build_noroot_apk.py --verify-only <out.apk>`，看它打印出的树是否等于 §2.4 那张；再用 `aapt2 dump xmltree` 复核（§5） |

**不要**把条目改名成 `res/xml/http.xml`——arsc 里存的就是 `res/Dk.xml`，改名等于资源丢失。

---

### 步骤 ②：改 `assets/SDKConfigSettings.json` 的 `sdk_url`

| 项 | 内容 |
|---|---|
| 改什么 | 只替换 `"sdk_url": "<旧值>"` 里的字符串；文件其余字节**逐字节保留**（该条目 STORED，长度可变） |
| 原值 | `https://sdk-api.yostar.cn` |
| 新值 | `--sdk-url` 传入（例：`https://<卡密服务域名>`；尾部**不要**带 `/`，SDK 自己拼 `/api/...`） |
| 工具 | 脚本内正则替换 + `json.loads` 回读校验 |
| 验证 | `python -c "import zipfile,json;print(json.load(open(...)))"` 或直接 `unzip -p out.apk assets/SDKConfigSettings.json` |

> 注意：这一步只改「SDK 打哪个域名」，不含账号/卡密逻辑本身；卡密站点与 `sdkcard.py` 是服务器侧的事。

---

### 步骤 ③：删 `assets/__tpinfo.*` 5 件

| 项 | 内容 |
|---|---|
| 删什么 | `assets/__tpinfo.tp` (12 B) / `__tpinfo.tsc` (485,268 B) / `__tpinfo.tsc.sig` (256 B) / `__tpinfo.tsd` (1,668 B) / `__tpinfo.tsd.sig` (256 B) |
| 为什么 | `tsd` 实测是一串 **ASCII hex 的 SHA-256 清单**（`007f547f537f44 0018000000 5a0da37c` + `af694dbb1851e3330b87a26abf07c5f1d9565b23ead…`），`tsc` 485 KB ≈ 7500 条 SHA-256，`*.sig` 是 RSA-2048 签名。ACE 的完整性校验是**数据驱动**的：读清单 → 逐文件比对；**清单不在就不校验**。删掉即整段跳过 |
| 工具 | 脚本重打包时不写入这 5 条 |
| 验证 | `--verify-only` 会打印 `__tpinfo 残留: 无（OK）` |

> ⚠️ **只删这 5 个**。同目录还有 `assets/__tpcfinfo.tsa` (272 B)、`assets/__tpsinfo.t.p.sin` (67 B)、`assets/tpginf.dat` (8 B)——历史配方里从没删过它们，且删了没被验证过，**保持原样**。

---

### 步骤 ④（可选）：把 CA 打进 APK

| 项 | 内容 |
|---|---|
| 改什么 | ① `res/E5.ogg`（唯一 raw 槽 `0x7f0e0000`，6,401 B）内容 ← 我们的 CA（**DER**，单张）；② `<certificates src="@0x7f0e0000"/>`（`TYPE_REFERENCE`） |
| 工具 | `--ca our_ca.crt --ca-mode both`（脚本自动把 PEM/DER 归一成 DER） |
| 副作用 | zxing 扫码提示音失效（ID 仍然有效，只是内容变成证书） |
| 验证 | `--verify-only` 的树里应出现 `src="@0x7f0e0000"`；`aapt2 dump resources` 能看到 `raw/zxing_beep` 仍在 |
| 建议 | **默认不要开**，理由见 §2.2 |

---

### 步骤 ⑤：重打包并对齐

| 项 | 内容 |
|---|---|
| 改什么 | 整个 zip 重写；`resources.arsc` 提到**第 1 条**；所有 STORED 条目 4 字节对齐 |
| 为什么 arsc 要首条 | 让 arsc 的绝对偏移可预测、且 %4/页对齐；原包不是首条（在 2,116,622,680），但历史配方 + 一致性好，代价为零 |
| 对齐算法 | 对每条 STORED：`pad = (-(pos + 30 + nlen)) % 4`，把 `pad` 个 `0x00` 追加进本地 extra（`--align-mode raw`，与 zipalign 一致）。`--align-mode d935` 则写 signapk 记录：`u16 0xD935 | u16(2+pad) | u16 align(4) | pad×0x00` |
| 压缩 | DECLATE 条目**原样复制压缩流**（不解压不重压）⇒ CRC/尺寸/压缩率完全不变 |
| 顺序 | 其余条目保持原顺序 |
| 上限 | 输出必须 `< 2,147,483,647 B`（超了会触发 Zip64，extra 字段会挤掉对齐），脚本会显式拒绝 |
| 工具 | `build_noroot_apk.py` 自带的 zip 写入器（**不用** zipalign——本机也没有；而且历史记录里 `zipalign` 在这 2 GB 文件上会 `Illegal instruction` 崩） |
| 验证 | `--verify-only` 会打 `STORED 4 字节对齐: OK` 和 `resources.arsc: 第 1 条, STORED=True` |

---

### 步骤 ⑥：重签 v1 + v2 + v3

| 项 | 内容 |
|---|---|
| **先剔除旧签名** | `META-INF/BACN.SF`、`META-INF/BACN.RSA`、`META-INF/MANIFEST.MF` **必须从 zip 里删掉**。不删就会和我们新生成的同名条目**重名**，Android 直接拒装（`aapt2` 报 `Duplicate entries in archive`）。**重写 zip 不会自动丢掉它们——这是我们实测踩到的坑，见 §4 #18** |
| 保留 | `META-INF/com/android/build/gradle/app-metadata.properties`、各 `*.version` —— 这些不是签名文件，保持原样 |
| 改什么 | 生成 `META-INF/MANIFEST.MF` / `CERT.SF` / `CERT.RSA`；并在 CD 前插入 APK Signing Block（v2 `0x7109871a` + v3 `0xf05368c0`） |
| v1 | 逐条目 `SHA-256-Digest`；`CERT.SF` 用整份 MANIFEST.MF 的 `SHA-256-Digest-Manifest` + **`X-Android-APK-Signed: 2, 3`**（v2/v3 剥离保护）；每行按 signapk 的 **70 B** 折续行（续行首字节空格）；`CERT.RSA` = **detached PKCS#7 SignedData**（无 authenticatedAttributes，最简合法形态） |
| v2 | 内容摘要 = 3 段 chunked SHA-256（见下），算法 `0x0103` = RSASSA-PKCS1-v1_5 + SHA-256（确定性，适合构建工具） |
| v3 | 多带一组裸 `uint32 minSDK / maxSDK`（签名值与未签名值必须一致），**minSdk 取自源包清单**（`uses-sdk.minSdkVersion`，当前 24；不再硬编码），maxSdk=0x7FFFFFFF，**只允许一个 signer** |
| 内容摘要（关键） | ① 每 1 MiB 一块：`SHA256(0xA5 ‖ u32le(len) ‖ chunk)`；② 最终：`SHA256(0x5A ‖ u32le(块数) ‖ 各块摘要拼接)`；③ 三段 = `[0, 签名块起始)`、`CD`、`EOCD`（**EOCD 里的 CD 偏移字段要改写成签名块起始偏移**，且不带 comment） |
| 工具 | 脚本自带（**不用** apksigner——本机没有 Java） |
| 验证 | `--verify-only`：`v2: OK` / `v3: OK` **且 `v1 结论: OK`**（逐条摘要 / 整份摘要 / PKCS#7 / 剥离保护 / 残留·重名·覆盖性）。该校验器已对**真 apksigner 签的包**做过交叉验证（见 §5.1） |

---

## 4. 已知坑全表

| # | 坑 | 实情 / 对策 |
|---|---|---|
| 1 | 「改 XML 要重编译 resources.arsc」（E32/E34 教训） | **不需要**。arsc 只存路径字符串；条目名不变即可换内容。见 §2.1 |
| 2 | `0xD935` | 它是 **`signapk`** 的对齐 extra 记录格式：`u16 0xD935 ‖ u16(2+pad) ‖ u16 align ‖ pad×0x00`，共 6+pad 字节。而 **`zipalign` 不加头，只补裸 0 字节**。原包用的是后者（extra 长度 0~3）。两条路脚本都支持 |
| 3 | resources.arsc 必须 STORED + 4 字节对齐 | **构建时强制**：源包里 arsc 若是 DEFLATE，解压后以 `method=0` 重写（重算 CRC/尺寸），且提到第 1 条。**校验时是硬失败**（`resources.arsc: … STORED=False` ⇒ 退出码 1），不再只打印。原包 arsc 本来就是 STORED 且偏移 %4==0，所以当前产物不受影响 |
| 4 | Zip64 悬崖 | 输出必须 < 2,147,483,647 B。原包 2,126,400,085 B，只剩 ~21 MB 余量；脚本超限直接报错退出（2） |
| 5 | `assets/__tpinfo.*` 不删必闪退 | 5 件全删。**别多删** `__tpcfinfo.tsa` / `__tpsinfo.t.p.sin` / `tpginf.dat` |
| 6 | AndResGuard 混淆名 | `0x7f120001` 的路径是 `res/Dk.xml`，**不能**改成 `res/xml/http.xml`。arsc 里根本没有 `res/xml/http.xml` 这个字符串（实测 0 次出现） |
| 7 | `extractNativeLibs=true` | `.so` 安装时会被解包到 `/data/app/.../lib/arm64/`，所以**zip 内 .so 是 STORED 还是 DEFLATE 都无所谓**，也不需要 4 KB/16 KB 页对齐。历史记录里 `zipalign -p` 在这包上直接崩，不必强求 |
| 8 | 旧文档把 E30/E32/E34/E38/E42 当「错误码」 | **它们是实验编号**，且都被记录为**成功**的重打包（E30「能进游戏」、E38「45 s+ 存活」、E42「SDK 卡密登录通过」）。真正炸的是 E35/E36（换/改 libairisgcore、libunity ⇒ SIGBUS 7）、E39–E43（增/改 dex ⇒ 卡启动） |
| 9 | ACE 钉什么 | **钉**：`libunity.so`、`libtprt.so`、`libairisgcore.so`、**加载布局**（不许新增 .so / 改 DT_NEEDED / 加 dex）、包名。**不钉**：`libil2cpp.so`、`res/*`、`resources.arsc`、`assets/*.json`、以及**不校验本地签名**（3 次重签实测跑起来了） |
| 10 | 签名变了 | 与既有测试包签名不同 ⇒ 必须先**卸载**再装（`INSTALL_FAILED_UPDATE_INCOMPATIBLE`）。上一批构建用的证书 SHA-256 是 `ABD1FA97…`（从 `e0_signed.apk.idsig` 解析），本次新签的**不是**它 |
| 11 | `ba_private.keystore` 找不到 | 全盘无此文件，只有 5 个 `.idsig`（v4，私钥不可还原）。脚本自动新生成一套；若要沿用旧签名必须找回原 keystore |
| 12 | 装完仍闪退 | 先清 ACE 记账：`files/ace_shell_di.dat`、`files/shell_cache`、`files/ano_tmp`、`data/app`（任一新包装完后旧包也会被记账污染） |
| 13 | 用户证书装了不生效 | ① 必须 **PEM**（`openssl x509 -in ca.crt -out ca.pem`），文件名 `<subject_hash_old>.0`（`openssl x509 -subject_hash_old -in ca.pem`）；② 服务端证书链的**根**必须就是我们装的那张。旧侦察里「用户 CA 不生效」的两次失败**同时**有 DER 格式 + 根不匹配两个混淆因素，不能当结论 |
| 14 | `targetSdk=33` | API 24+ 且 targetSdk≥24 ⇒ **默认只信系统 CA**，用户 CA 必须靠 NSC 显式声明。这就是步骤 ① 的唯一目的 |
| 15 | `<trust-anchors>` 只写 `user` | 会**整体取代**默认信任集 ⇒ 公开 HTTPS 全挂。必须同时写 `system`（脚本已强制） |
| 16 | NSC 想覆盖 native 流量 | 做不到。见 §2.2。native（libcurl/UnityTLS/BestHTTP）读 `AndroidCAStore`，只认系统库 + 用户库文件 |
| 17 | 服务器 `state` 回 `Servers` 指向 | 这条**不改包**，是服务端行为，与本文无关，但它是整条链路真正把流量引到 `https://<我们的网关>/api/` 的地方 |
| 18 | **旧 v1 签名文件没删 ⇒ zip 重名 ⇒ 装不上** | 原包自带 `META-INF/{BACN.SF,BACN.RSA,MANIFEST.MF}`。重打包若不先剔除，直接写我们的同名条目就会产生**重复条目**；Python 的 `zipfile` 不报错（`namelist()` 里两条并存），但 Android 与 `aapt2` 会拒绝：`Zip: Error adding entry to hash table` / `Duplicate entries in archive`。脚本现在会显式剔除并在 `--verify-only` 里查重 |
| 19 | 只改 zip 内容不改压缩方法 | 613 条 DEFLATE 条目必须**原样复制压缩流**（不重压），否则 CRC/尺寸/压缩率变化，且白白多花时间。脚本按块搬运，只对 6 个被替换/新增的条目重新计算 CRC |
| 20 | **v1 的两个规范字段**（2026-11-17 修） | ① `.SF` 主属性区必须有 `X-Android-APK-Signed: 2, 3`，否则 apksig 报 `JAR_SIG_NO_APK_SIG_STRIP_PROTECTION`，v1-only 客户端也无法察觉"v2/v3 被剥掉"；② `MANIFEST.MF` 每行 ≤ 72 B（signapk 的行长上限是 **70**，续行以 1 个空格开头）。旧实现写成整行，真产物有 **808 行 > 72 B、最长 92 B**；解析时**必须把续行拼回**（先按字节拼、再 UTF-8 解码）。`--verify-only` 对这两条都是硬失败 |
| 21 | **cert 与私钥不配对**（2026-11-17 修） | `--key-pem A --cert-pem B` 会产出"v2/v3 块里 pub 来自 A、证书是 B"的包：工具自验（用块内公钥）能过，**Android 安装必挂**（要求"签名者公钥 == 第一张证书公钥"）。现在 `assert_key_pair()` 在加载/构建时做 SPKI 的 (n,e) 比对 **+ 用私钥签名、用证书公钥验签的往返自检**，不通过直接拒建 |
| 22 | **源包身份**（2026-11-17 修） | `PKG_NAME/APK_VERSION_CODE/TARGET_SDK/NSC_RES_ID` 以前是死常量，传错 `--src` 照建。现在构建前硬校验 `package` / `versionCode` / `targetSdkVersion` / `android:networkSecurityConfig` 资源 ID（**最后一个最隐蔽**：ID 不对，换 `res/Dk.xml` 等于白换），并检查 `NSC_ENTRY` 存在；不符直接拒建，确认无误可加 `--force`。v3 的 `minSdkVersion` 同时改为读清单实际值 |

---

## 5. 验证清单

按顺序做，任一项失败就别装机。

### 5.1 签名与结构（脚本自带，`--verify-only`）

```bat
python work\ba\noroot\build_noroot_apk.py --verify-only work\ba\noroot\BA_noroot_v1.apk
```

必须看到：

```
APK Signing Block: OK @<off> (<n> B)
v2: OK
v3: OK
zip 完整性: OK
v2/v3 签名者证书 SHA-256 = <cert SHA-256>
v1: MANIFEST.MF <n> B, <n> 个 Name 段
v1: 最长行 70 B, 超 72 B 的行 0 个（OK）
v1: 逐条摘要 <n> 条, 不符 0, 条目缺失 0 OK
v1: 未被 MANIFEST 覆盖的条目 0 个
v1: META-INF 签名文件 3 个 [MANIFEST.MF, CERT.SF, CERT.RSA]
v1: META-INF/CERT.SF SHA-256-Digest-Manifest OK（0 个逐条段）
v1: X-Android-APK-Signed = '2, 3'（声明 [2, 3]，APK 实有 [2, 3]）
v1: META-INF/CERT.RSA 对 .SF 的 PKCS#7 验签 OK
v1: 签名者证书 SHA-256 = <cert SHA-256>
v1 与 v2/v3 证书一致: OK
v1 结论: OK
STORED 4 字节对齐: OK
重复条目: 无（OK）
resources.arsc: 第 1 条, STORED=True, 4 字节对齐=True
__tpinfo 残留: 无（OK）
res/Dk.xml 解析：  <network-security-config> … <certificates src="system"> <certificates src="user"> …
```

> **v1 是硬判据，不是装饰**：`最长行 > 72 B`、`逐条摘要不符`、`SHA-256-Digest-Manifest` 不一致、
> `X-Android-APK-Signed` 缺/值不对、`META-INF` 有重名或残留旧签名、有非 `META-INF` 条目没被 MANIFEST 覆盖、
> `resources.arsc` 非 STORED —— 任一条都会让命令返回 **1**。
> 例如拿它去验旧产物 `BA_noroot_v1.apk`（2026-11-16 建的）会明确失败：
> `v1: 最长行 92 B, 超 72 B 的行 808 个` + `X-Android-APK-Signed = None` ⇒ `v1 结论: FAIL`。
> 2.1 GB 包上整套校验实测 **12.8 s**（文件已在页缓存）。

> **这套校验器是可信的**：它能独立验通**真 apksigner 签过的** `work\ba\bapatch\lsp\build13\Probe13.apk`
> （`v2: OK` / `v3: OK`），说明内容摘要算法、v2/v3 结构、RSA PKCS#1 v1.5 验签都与 AOSP 一致。
> 这是它和「自己写自己验」的自嗨实现的关键区别。
> **但注意边界**：它验通的是"别的工具写的东西我能读懂"，**不等于**"我写的东西官方工具能接受"——
> 后者必须有 JRE + `apksigner verify -v` 或真机（本机没有，见 §1.4）。

### 5.2 AXML 独立复核（用 aapt2，不需要 JVM）

```bat
set AAPT2=C:\Users\su\.gradle\caches\8.11.1\transforms\bedba16cea642164a45bf9eb6e21088d\transformed\aapt2-8.6.1-11315950-windows\aapt2.exe
%AAPT2% dump xmltree --file res/Dk.xml work\ba\noroot\BA_noroot_v1.apk
%AAPT2% dump badging work\ba\noroot\BA_noroot_v1.apk | findstr /i "package sdkVersion"
```

期望：`N: network-security-config` → `base-config` → `trust-anchors` → 两个 `certificates`（`src=system` / `src=user`）；
`package: name='com.RoamingStar.BlueArchive' versionCode='73'`，`sdkVersion:'24'`，`targetSdkVersion:'33'`。

### 5.3 包内清单

```bat
python -c "import zipfile;z=zipfile.ZipFile(r'work\ba\noroot\BA_noroot_v1.apk');n=z.namelist();print(len(n));print([x for x in n if 'tpinfo' in x]);print(z.getinfo('res/Dk.xml').file_size, z.getinfo('res/Dk.xml').compress_type);print(z.read('assets/SDKConfigSettings.json')[:60])"
```

期望：`41307` 条、tpinfo 列表为空、`560 0`、`sdk_url` 已是新值（没传 `--sdk-url` 时则仍是原值）。
条目数账：`41312 − 5(__tpinfo) − 3(旧 v1 签名) + 3(新 v1 签名) = 41307`。

### 5.0 本方案自带的实测证据（2026-11-16 跑通）

| 检查 | 工具 | 结果 |
|---|---|---|
| v2/v3 内容摘要 + RSA 验签 | 本脚本 `--verify-only` | `v2: OK` / `v3: OK` |
| **摘要算法是否真和 AOSP 一致** | 拿**真 apksigner 签的** `bapatch\lsp\build13\Probe13.apk` 交叉验 | `v2: OK` / `v3: OK` ⇒ 算法与 apksigner 一致 |
| AXML 结构 | **`aapt2 dump xmltree`**（Google 官方工具） | `E: network-security-config → base-config → trust-anchors → certificates src="system" / src="user"` |
| 包元数据 | `aapt2 dump badging` | `com.RoamingStar.BlueArchive versionCode='73' minSdkVersion:'24' targetSdkVersion:'33'` |
| v1 的 PKCS#7 | **`openssl smime -verify`** | **`Verification successful`** |
| MANIFEST.MF 逐条摘要 | 本脚本 `--verify-only`（2026-11-17 起为**全量**） | 41,304 条 `不符 0 / 缺失 0`；旧产物同时暴露 `808 行 > 72 B` + 缺 `X-Android-APK-Signed` ⇒ `v1 结论: FAIL` |
| v1 换行规则 | 与官方 signapk 输出**字节级对齐** | 用 70 B 规则重排官方 `MANIFEST.MF` 的 41,310 段（含 1,254 条续行）⇒ **0 个不匹配**；apksig `ManifestWriter.class` 常量池里只有 `Integer 70` |
| cert/key 与源包身份 | `--self-test` + 独立测试 | 不配对拒建、包名/版本/targetSdk/NSC 资源 ID 不符拒建、`--force` 可跳过、v3 minSdk 取自清单 |
| 真包整链 | 2,126,400,085 B 输入 → 1.98 GB 输出 | **7.3 s**，全绿 |

> 这三把「外部尺子」（apksigner 签名样本、aapt2、openssl）就是这套工具可信的根据；
> 其中 `aapt2` 还当场抓出了「旧 v1 签名未剔除导致 zip 重名」这个 bug（§4 #18）。

### 5.4 装机（唯一真判据）

1. 卸载旧包（签名不同，必须卸）。
2. 清 ACE 记账 4 个路径。
3. 装 → 启动 → 能看到标题画面 ≥ 45 s 不闪退。
4. 抓 `logcat` 里 `Curl error 60` / `UnityTls error code: 7`：出现即**证书链没通**（装的是 PEM 吗？根对不对？）。
5. 登录到大厅 ⇒ 通过。

### 5.5 证书侧（配合步骤 ①）

```bash
# 手机上（用户证书）
openssl x509 -in our_ca.crt -out our_ca.pem                       # 必须 PEM
openssl x509 -subject_hash_old -in our_ca.pem                     # 得到 <hash>
# 改名成 <hash>.0 后装进「用户证书」（设置 → 安全 → 加密与凭据 → 安装证书 → CA）
```

---

## 6. 回滚

| 层 | 做法 |
|---|---|
| 客户端 | 保留原厂 `report\_tmp\cn_base.apk`（2,126,400,085 B，SHA-256 自行记录）。回滚 = 卸载我们的包 → 装原厂包。原厂包签名不同，同样要先卸 |
| 服务端 | `state` 接口把 `Servers` 指回官方；卡密站点关停即可，客户端无需改动 |
| 证书 | 设置里删掉那张用户 CA（系统会提示「网络可能被监控」消失） |
| 代理 | 关掉 Wi-Fi 代理 / per-app VPN，客户端即直连官方 |
| 构建 | 我们的包不含任何不可逆改动：①③④只是替换/删除 zip 条目，⑤⑥只影响签名；原包逐字节保留即可随时重来 |

> **纪律**：每次装机前记录 `cert SHA-256` 和 `out.apk` 的 SHA-256，否则无法判断「这次闪退是哪一版」。

---

## 7. 附录：本方案依赖的实测数据

```
源包        report\_tmp\cn_base.apk
            2,126,400,085 B / 41,312 entries / EOCD cd_offset=2,122,326,016 cd_size=4,074,047
包名        com.RoamingStar.BlueArchive    versionCode 73   versionName 3.0.2
SDK         minSdk 24   targetSdk 33   compileSdk 33
签名        v1+v2+v3（不是 v1-only，见 §1.2）
            APK Sig Block @2,122,321,920，4,088 B：
            v2 0x7109871a 1,334 B / v3 0xf05368c0 1,334 B（min/max=24/2147483647）
            / 0x881155ff 13 B / verity padding 0x42726577 1,335 B
            v1 = META-INF/BACN.SF（含 X-Android-APK-Signed: 2, 3）+ BACN.RSA + MANIFEST.MF
压缩        STORED 40,699 条（1,950,057,475 B） / DEFLATE 613 条
对齐        所有 STORED 条目 data_off % 4 == 0；本地 extra 长度 ∈ {0,1,2,3}（裸 0 字节）

AndroidManifest.xml   STORED 50,552 B；<application> @0x7D54；11 attrs（按 res-id 升序）
  networkSecurityConfig  res_id 0x01010527  TYPE_REFERENCE  0x7F120001
  extractNativeLibs      0x010104EA  true
  usesCleartextTraffic   0x010104EC  true
<uses-sdk> @0x5720：minSdkVersion 0x0101020C=24，targetSdkVersion 0x01010270=33

resources.arsc         STORED 1,156,308 B；全局字符串池 6,726 串（UTF-8）；1 个 package(0x7f)
  0x7F120001 → type 0x12(xml) key "http" → "res/Dk.xml"（arsc 偏移 0x6E8D，全包唯一）
  type 0x0E(raw) 仅 1 条：0x7F0E0000 key "zxing_beep" → "res/E5.ogg"（6,401 B STORED）

res/Dk.xml             264 B STORED
  RES_XML_TYPE(8) + STRING_POOL(UTF-8, 3 串: base-config / cleartextTrafficPermitted /
  network-security-config) + RESOURCE_MAP(空, 8) + <network-security-config>(36) +
  <base-config cleartextTrafficPermitted=true>(56) + 2×END(24)
  ⇒ 生成后 560 B：pool 8 串 176 B + resmap 8 + START 36/56/36/56/56 + END 5×24

assets/__tpinfo.tp        12 B    ASCII 魔数 3c2d03e0a4fc2000 57c13ce3
assets/__tpinfo.tsc       485,268 B  ≈7500 条 SHA-256 清单
assets/__tpinfo.tsd       1,668 B  ASCII hex SHA-256 清单（≈25 条）
assets/__tpinfo.tsc.sig   256 B    RSA-2048
assets/__tpinfo.tsd.sig   256 B    RSA-2048
（保持原样：__tpcfinfo.tsa 272 B / __tpsinfo.t.p.sin 67 B / tpginf.dat 8 B）

assets/SDKConfigSettings.json  2,840 B STORED；"sdk_url": "https://sdk-api.yostar.cn"
```

---

## 8. 与旧文档不一致的地方（已按实测纠正）

| 旧说法 | 实测 |
|---|---|
| 「改 res xml 必须重编译 resources.arsc」 | 不需要，arsc 只存路径字符串 |
| 「E32/E34 栽过（当错误码）」 | E30…E44 是**实验编号**，其中重打包类全部跑起来了 |
| 「用户 CA 已证伪」 | 那两次实验有 DER+PEM 与根证书不匹配两个混淆因素，**从未在干净条件下测过** |
| 「原包 v2 重签」 | **原包本来就有 v2/v3 签名块**（§1.2 实测：CD 前 16 B = `APK Sig Block 42`，块 4,088 B）。"没有签名块"是 `probe3_sigmin.py` 只在文件尾 64 B 找 magic 造成的假阴性。本工具不复制旧块，v2/v3 是重新生成的 ⇒ 重打包逻辑不受影响 |
| 「res/raw 不存在」 | raw 类型存在 1 条，但被 AndResGuard 扁平化到 `res/E5.ogg`（目录名不可见） |
| 「打 CA 进 APK = 零配置」 | 只对 Java 栈成立；native（login 主路径）完全不看 NSC |
