# 免 root 改包流水线 · 发版可信度核实（NOROOT_PROD_BUILD_PLAN_20261117）

> 执行：ca-researcher　　时间：2026-11-17 23:59 – 2026-11-18 00:35 (+08:00)
> 方式：**只读**。跑了 `--help`、`--verify-only`（只读产物）、zip 中央目录对比、`.so` 字符串扫描、DNS/HTTP 实测、GameMainConfig 解码与逐字节 diff。
> **没有构建任何 APK、没有改 `build_noroot_apk.py` 或任何已有文件、没碰手机/adb/服务端。** 唯一新建：本文件 + `work\ba\noroot\_tmp\`（两个 .so 解包件）。
> 基线：`build_noroot_apk.py` 115,359 B / sha256 `C19591E51867F7BD5E25FB7B75A7056177AD5714BB290AEA23C1DACA6ACB85A3` / 2026-11-17 20:40:21

---

## 0. 结论速览

| # | 问题 | 结论 | 证据强度 |
|---|---|---|---|
| 1 | 流水线能否直接发版 | **工具链可以，现成产物不可以。** `build_noroot_apk.py` 是自洽、可跑、可复现的（v2/v2b 已实测全绿）；但 `BA_noroot_v1.apk` 是**残次样本**（`--verify-only` **exit 1**、`sdk_url` 与 `ServerInfoDataUrl` 都是原厂值） | 已证实 |
| 2 | 必须 http 还是可以 https | **两者都行，且都不需要用户 CA。** 推荐 **https**（证书已是 Let's Encrypt，链到 ISRG Root X1，公网可信） | 机制已证实 / 端到端未实测 |
| 3 | 唯一生产构建命令 | 见 §5（一条，可直接复制） | — |
| 4 | 要拍板的空白 | 6 项，见 §6 | — |
| 5 | 推翻/纠正的旧说法 | 6 条，见 §7（**其中"证书 25 天后到期"已被证伪：证书今天换成了 LE，到 2027-02-15**） | — |

**一句话**：工具能发版，但**发版命令里的 `--gmconfig-url` 必须给整串 URL 形式**，且**两个预制的 `GameMainConfig_*.bin` 一个都不能用**（都指向 NXDOMAIN 域名）。

---

## 1. Q1：`--help` 原文 与 全部 `add_argument`

### 1.1 `python work\ba\noroot\build_noroot_apk.py --help`（`usage` + `options` 原样）

```
usage: build_noroot_apk.py [-h] [--src SRC] [--out OUT] [--sdk-url SDK_URL]
                           [--ca CA] [--ca-mode {user,system,both,bundled}]
                           [--keystore KEYSTORE] [--storepass STOREPASS]
                           [--keypass KEYPASS] [--alias ALIAS]
                           [--key-pem KEY_PEM] [--cert-pem CERT_PEM] [--v1]
                           [--no-v1] [--no-arsc-first]
                           [--align-mode {raw,d935,none}] [--force]
                           [--rename-package NEW_PKG] [--expect-package PKG]
                           [--gmconfig-url URL_OR_DOMAIN]
                           [--gmconfig-value STR]
                           [--gmconfig-scheme {http,https}]
                           [--no-gmconfig-pad] [--asset-replace NAME=PATH]
                           [--gmconfig-selftest] [--gen-keystore PATH]
                           [--verify-only APK] [--self-test]

options:
  -h, --help            show this help message and exit
  --src SRC
  --out OUT
  --sdk-url SDK_URL
  --ca CA
  --ca-mode {user,system,both,bundled}
  --keystore KEYSTORE
  --storepass STOREPASS
  --keypass KEYPASS
  --alias ALIAS
  --key-pem KEY_PEM
  --cert-pem CERT_PEM
  --v1
  --no-v1
  --no-arsc-first
  --align-mode {raw,d935,none}
  --force               跳过源包身份校验（package/versionCode/targetSdk/networkSecurity
                        Config 资源 ID 不符时仍然构建）
  --rename-package NEW_PKG
                        改包名（并行安装用）：只重写 AndroidManifest.xml
                        的串池，package/authorities/权限名/activity-alias 名一起改；不动
                        dex/arsc/.so
  --expect-package PKG  校验产物的 package 是否等于 PKG（--verify-only 也可用）
  --gmconfig-url URL_OR_DOMAIN
                        改 GameMainConfig.ServerInfoDataUrl（等长）。可给域名 bapsvr-
                        prods-cn.com（默认 http，19 字符最优）或 http(s)://state-
                        api.<域名>/api/state 或任意 URL
  --gmconfig-value STR  直接给完整的 ServerInfoDataUrl 值（含 [] 的整串）
  --gmconfig-scheme {http,https}
                        强制协议（默认取自输入；纯域名默认 http）
  --no-gmconfig-pad     新值比原值短时不允许补尾部空格
  --asset-replace NAME=PATH
                        通用替换：zip 内条目名=本地文件（可多次）；若换 GameMainConfig 会强制结构与字段自检
  --gmconfig-selftest   只测 GameMainConfig 替换算法（需 --src），不构建 APK
  --gen-keystore PATH
  --verify-only APK
  --self-test
```

（`epilog` 里还有一段说明：单文件纯标准库、不需要 apktool/aapt2/jarsigner/keytool/zipalign/apksigner；改造 6 步；退出码 `0 成功 / 1 校验失败 / 2 环境不足`。）

### 1.2 全部 `add_argument`（AST 提取，27 个）

| # | 选项 | dest | 默认值 | action | required |
|---|---|---|---|---|---|
| 1 | `--src` | src | 无（None） | store | 否 |
| 2 | `--out` | out | 无（None） | store | 否 |
| 3 | **`--sdk-url`** | sdk_url | 无（None） | store | 否 |
| 4 | `--ca` | ca | 无（None） | store | 否 |
| 5 | `--ca-mode` | ca_mode | **`user`** | store（choices: user/system/both/bundled） | 否 |
| 6 | `--keystore` | keystore | **`ba_private.keystore`**（相对路径） | store | 否 |
| 7 | `--storepass` | storepass | **`baserver`** | store | 否 |
| 8 | `--keypass` | keypass | None | store | 否 |
| 9 | `--alias` | alias | **`ba`** | store | 否 |
| 10 | `--key-pem` | key_pem | 无 | store | 否 |
| 11 | `--cert-pem` | cert_pem | 无 | store | 否 |
| 12 | `--v1` | v1 | **True** | store_true | 否 |
| 13 | `--no-v1` | v1 | （store_false ⇒ True） | store_false | 否 |
| 14 | `--no-arsc-first` | arsc_first | **True** | store_false | 否 |
| 15 | `--align-mode` | align_mode | **`raw`** | store（raw/d935/none） | 否 |
| 16 | `--force` | force | False（store_true） | store_true | 否 |
| 17 | `--rename-package` | rename_package | 无 | store | 否 |
| 18 | `--expect-package` | expect_package | 无 | store | 否 |
| 19 | **`--gmconfig-url`** | gmconfig_url | 无 | store | 否 |
| 20 | **`--gmconfig-value`** | gmconfig_value | 无 | store | 否 |
| 21 | `--gmconfig-scheme` | gmconfig_scheme | 无（取自输入） | store（http/https） | 否 |
| 22 | `--no-gmconfig-pad` | gmconfig_pad | **True** | store_false | 否 |
| 23 | `--asset-replace` | asset_replace | **`[]`** | append | 否 |
| 24 | `--gmconfig-selftest` | gmconfig_selftest | False | store_true | 否 |
| 25 | `--gen-keystore` | gen_keystore | 无 | store | 否 |
| 26 | `--verify-only` | verify_only | 无 | store | 否 |
| 27 | `--self-test` | self_test | False | store_true | 否 |

**没有任何 `required=True`**；`--src/--out` 是运行时检查（`ap.error('需要 --src 与 --out')`，`main()` 内）。

### 1.3 你点名要确认的两个准确参数名

| 用途 | **准确参数名** | dest | 说明 |
|---|---|---|---|
| SDK 域名 | **`--sdk-url`** | `sdk_url` | 单值；写进 `assets/SDKConfigSettings.json` 的 `sdk_url` 字段 |
| GameMainConfig 注入 | **`--gmconfig-url`** / **`--gmconfig-value`** / `--gmconfig-scheme` / `--no-gmconfig-pad` / `--gmconfig-selftest` | 对应 dest | 三者互斥关系：`--gmconfig-url` 与 `--gmconfig-value` **只能给一个**（`main()` 里 `ap.error`）；`--gmconfig-selftest` 只测算法不构建 |

> 另外还有一个"逃生口"：`--asset-replace assets/bin/Data/e37c46fe...=<本地 bin>`，直接塞一个自备的 GameMainConfig（会强制走结构 + 字段自检）。

---

## 2. Q2：GameMainConfig 链路

### 2.1 改的是哪个条目、哪个字段

| 项 | 值 | 出处 |
|---|---|---|
| zip 条目 | **`assets/bin/Data/e37c46fea17834108a4756797197d05a`** | 常量 `GMC_ENTRY`（脚本 L93） |
| 条目大小 | **5,212 B**（源包 / F1 / F2 都是 5,212 B） | 实测 |
| 字段 | **`ServerInfoDataUrl`**（JSON 里第一层的 6 个 key 之一） | 常量 `GMC_URL_FIELD` |
| 6 个字段 | `SkipTutorial` / `ServerInfoDataUrl` / `ServerName` / `VersionCode` / `PlatformID` / `ChannelID` | 常量 `GMC_FIELDS` |
| m_Script 位置 | **`0x1018`，长度 `1090 B`（0x442）**，到 `0x1459` 结束 | 常量 `GMC_SCRIPT_OFF/LEN` |
| 容量 | `cap = 545` 个 UTF-16 字符（= 1090 B） | `gmconfig_budget()` |

改法：字段值在 m_Script 里是一段 **XOR 混淆 + base64** 的串；`gmconfig_rewrite()` 解出第一层 JSON → 替换该字段 → 重新 b64/XOR → **等长写回**，并要求「输出仍 5,212 B / 头部 0x0–0x1017 逐字节不变 / 尾部 padding 不变 / 回读 6 字段」。

### 2.2 `GameMainConfig_http_example.com.bin` **完整逐字段**

```
文件：GameMainConfig_http_example.com.bin
大小：5,212 B     sha256 前 16：d4c3ebf965aa492b
结构：size=5212   m_Script=1090 B   cap=545
字段（6/6 全部解出）：
  SkipTutorial       = 'False'
  ServerInfoDataUrl  = '["http://state-api.example.com/api/state","http://stateqc-api.example.com/api/state"]'
  ServerName         = 'prod'
  VersionCode        = '73'
  PlatformID         = '1'
  ChannelID          = '1'
```

对照另两份：

| 文件 | ServerInfoDataUrl | 长度 |
|---|---|---|
| **原包**（从 `cn_base.apk` 读） | `["https://state-api.bluearchive-cn.com/api/state","https://stateqc-api.bluearchive-cn.com/api/state"]` | 101 |
| `GameMainConfig_http_example.com.bin` | `["http://state-api.bapsvr-prods-cn.com/api/state","http://stateqc-api.bapsvr-prods-cn.com/api/state"]` | 101 |
| `GameMainConfig_http_example.com.bin` | `["http://state-api.example.com/api/state","http://stateqc-api.example.com/api/state"]` | 95 |

> 文件名 → 生成方式的对应关系（**推断**，与值形态一致）：两个 `.bin` 都是 `--gmconfig-url <裸域名>` 的产物 —— 该分支用模板 `GMC_TMPL_PAIR` 展开成 `http://state-api.<域名>` + `http://stateqc-api.<域名>` 两条。

### 2.3 binary diff：改了几个字节、对应哪个字段

**F1 vs F2**（`..._bapsvr-prods-cn.com.bin` vs `..._example.com.bin`）：

```
差异区段：0x1154 .. 0x1458   共 306 B 变化（306 个单字节段，非连续）
m_Script 区间：0x1018 .. 0x1459
头部 0x0000..0x1017 是否变化：False
m_Script 之后（尾部 padding）是否变化：False
```

**原包 vs F2**：`0x110E .. 0x1459` 区间内共 **315 B** 变化，头部与尾部同样**未变**。

两点解释：

1. **差异全部落在 m_Script 内部**（0x1018–0x1459），**头部长度字段、m_Name、尾部 padding 一个字节没动** —— 这正是"等长替换"的定义。
2. **为什么是"306 个单字节散点"而不是连续块**：m_Script 用位置相关的 XOR 密钥流加密（`gmconfig_xor(key8, plain)`），XOR 是按位异或 ⇒ **明文只有哪些字节不同，密文就只有哪些字节不同**，其余位置密文完全相同。所以散点是**正确行为**，不是损坏。

> 也就是说：改动的字节数 ≈ 两个值在"补空格到 545 后的纯文本"里逐位置不同的字符数。**唯一语义变化就是 `ServerInfoDataUrl` 这一个字段，其余 5 个字段与原包逐字节相同**（脚本 `gmconfig_rewrite` 内置了这条回读校验）。

### 2.4 ★ 但这两个 `.bin` **一个都不能用于发版**

| 文件 | 它指向的主机 | DNS 实测（2026-11-17 23:59） |
|---|---|---|
| `..._bapsvr-prods-cn.com.bin` | `state-api.bapsvr-prods-cn.com` / `stateqc-api.bapsvr-prods-cn.com` | **NXDOMAIN**（`bapsvr-prods-cn.com` 本身也 NXDOMAIN） |
| `..._example.com.bin` | `state-api.example.com` / `stateqc-api.example.com` | **NXDOMAIN**（只有 `example.com` 和 `www.` 有 A 记录） |

```
example.com                   -> <SERVER_IP>
example.com               -> <SERVER_IP>
state-api.example.com         -> NXDOMAIN
stateqc-api.example.com       -> NXDOMAIN
bapsvr-prods-cn.com                -> NXDOMAIN
state-api.bapsvr-prods-cn.com      -> NXDOMAIN
```

⇒ **用这两个 `.bin` 里的任何一个构建，客户端第一跳就 DNS 失败。** 生产命令必须走 §5 的整串 URL 形式。

---

## 3. Q3：必须 http 明文，还是 https + user CA 也能行？

### 3.1 直接结论

| 方案 | 是否可行 | 需不需要装 CA | 强度 |
|---|---|---|---|
| **https + 我们域名的公网真证书** | ✅ 可行 | **不需要** | 已证实（证书链 + 端口 + 实测 200） |
| **http 明文** | ✅ 可行 | **不需要** | 已证实（80 端口 200 + 原厂 http 字面量） |
| https + **自签 CA**（MITM `*.bluearchive-cn.com`） | ✅ 机制上可行 | **需要**（用户证书 + NSC `src="user"`） | 机制已证实 / 端到端未实测 |

**推荐 https**：证书已在 2026-11-17 换成 Let's Encrypt（见 §7-①），链完整、公网可信，且与线上 `state1.json` 返回的 `Servers = ["https://example.com/api/"]` 保持一致（**不做协议降级混合**）。

### 3.2 证据 A：游戏本体到底从哪拿信任锚（.so 扫描，逐条原始输出）

解包 `lib/arm64-v8a/libil2cpp.so`（**270,927,056 B**，sha256 前 16 `5ac1cbe0fb8f730f`）与 `lib/arm64-v8a/libunity.so`（**20,950,552 B**，`01568fac74ab1cf5`）到 `work\ba\noroot\_tmp\`，全文件字节扫描：

**libil2cpp.so（270 MB）**

```
needle                                  ascii  utf16  first ascii off
certifi                                     1      0  0x037C570E      ← 其实是 "certificate" 的子串
（AndroidCAStore / /system/etc/security/cacerts / SSL_CTX / X509TrustManager /
  TrustManagerFactory / cacert / BoringSSL / mbedtls / SSL_CTX 全部 0）
```

精确复核：

```
libil2cpp.so:  certificate=1  certifi=1(其中1个是certificate子串)  TrustManager=0
               cacert=0  unitytls=1  mbedtls=0  BoringSSL=0  SSL_CTX=0
```

⇒ **libil2cpp.so 里没有任何 TLS 证书校验代码、没有 trust store 路径、没有 CA 文件加载**。【已证实·负证据】

**libunity.so（21 MB）**

```
needle                                  ascii  utf16  first ascii off
X509TrustManager                            1      0  0x0111B955
checkServerTrusted                          1      0  0x0111B9B4
getAcceptedIssuers                          1      0  0x0111B9C7
TrustManagerFactory                         5      0  0x0111B758
KeyStore                                    1      0  0x0111B8BB
ValidateCertificateNative                   1      0  0x010668CE
CertificateHandlerProxy                     1      0  0x0106658B
（/apex/com.android.conscrypt/cacerts=0   /system/etc/security/cacerts=0
  AndroidCAStore=0   SSLContext=0   PKIX=0   CURL_CA_BUNDLE=0   cainfo=0   capath=0
  unitytls=7   mbedtls=62）
```

`TrustManagerFactory` 的 5 处上下文（原始字节）：

```
0x111B758  ...javax/net/ssl/TrustManagerFactory\x00getAlgorithm\x00getDefaultAlgorithm\x00(Ljava...
0x111B7B0  ...(Ljava/lang/String;)Ljavax/net/ssl/TrustManagerFactory;\x00(Ljava/lang/String;Ljava/lang/String;)
0x111B7FA  ...(Ljava/lang/String;Ljava/lang/String;)Ljavax/net/ssl/TrustManagerFactory;\x00(Ljava/lang/String;Ljava/security/Prov
0x111B84A  ...)Ljavax/net/ssl/TrustManagerFactory;\x00()Ljava/security/Provider;\x00getTrustMan...
0x111B903  ...TrustManagerFactorySpi;Ljava/security/Provider;Ljava/lang/String...
```

⇒ **这些是 JNI 方法签名串**，证明 libunity 通过 JNI 调 `javax.net.ssl.TrustManagerFactory.getDefaultAlgorithm()` → `getInstance(String)` → `getTrustManagers()`，再调 `X509TrustManager.checkServerTrusted()` / `getAcceptedIssuers()`。**没有任何文件路径式的 CA 加载**（`AndroidCAStore`、`cacerts`、`SSL_CTX_load_verify_locations` 全部 0 命中）。【已证实·正证据】

**推论链**：

```
游戏 TLS 栈 = mbedTLS/UnityTLS（libunity 内，mbedtls 出现 62 次）
      ↓ 但证书链校验不是 mbedTLS 自己做，而是
Java TrustManagerFactory（JNI）→ X509TrustManager.checkServerTrusted
      ↓ init(null) 时用平台默认信任库
RootTrustManager（AndroidNSSP）→ SystemCertificateSource → app 自己的 NetworkSecurityConfig
      ↓
res/Dk.xml 的 <trust-anchors> 决定"信谁"
```

⇒ **NSC 里的 `src="user"` 会真正影响游戏的 TLS 信任集**。【机制已证实 / 端到端未实测】

### 3.3 证据 B：`res/Dk.xml` 原包就有 `cleartextTrafficPermitted="true"`

原包 `res/Dk.xml`（264 B）解出来是：

```xml
<network-security-config>
    <base-config cleartextTrafficPermitted="true"/>
</network-security-config>
```

改造后（560 B）保留了这个属性，只加了 trust-anchors：

```xml
<network-security-config>
  <base-config cleartextTrafficPermitted="true">
    <trust-anchors>
      <certificates src="system"/>
      <certificates src="user"/>
    </trust-anchors>
  </base-config>
</network-security-config>
```

**但这里要说清一个容易混淆的点**：`cleartextTrafficPermitted` 是 **Java 栈**（OkHttp / HttpURLConnection / WebView）的策略，由 `NetworkSecurityPolicy` 查询；**native 的 mbedTLS/libcurl 根本不看它**。所以：

- 「http 可行」的真正依据**不是**这条 NSC 属性，而是下面三条：
  1. **服务器 80 端口确实在服务**：`http://example.com/api/state` → **200 / 64 B**（实测）。
  2. **客户端接受 http 形态的 state URL**：原厂 `global-metadata.dat` 里的出厂默认字面量就是 `http://test-ba.yostar.net:5210/api/state`（http，非 https）——这是"同一个 DTO 同一字段接受 http"的强证据（旧侦察 `report\11`:18/156/313）。
  3. 我们控制 `state1.json`，返回什么协议由我们定。
- 【判断：http 可行 — **推断·高**；上面每一条子证据都是已证实，但"整链 http 端到端跑通"没测过】

### 3.4 证据 C：https 这条路现在是最稳的

```
证书：issuer = C=US, O=Let's Encrypt, CN=YR2
      notBefore = Nov 17 11:50:26 2026 GMT
      notAfter  = Feb 15 11:50:25 2027 GMT
      SAN = DNS:example.com, DNS:example.com
链（服务器发 3 张）：
  0 s:CN=example.com        i:Let's Encrypt CN=YR2
  1 s:Let's Encrypt CN=YR2       i:ISRG CN=Root YR
  2 s:ISRG CN=Root YR            i:Internet Security Research Group CN=ISRG Root X1
curl 校验：ssl_verify_result = 0
```

- 链**终止于 `ISRG Root X1`**（交叉签），X1 在 Android 系统信任库里 ⇒ 客户端用 `src="system"` 即可通过，**不需要装任何 CA**。【已证实·强】
- 端口实况：`http://…/api/state` → 200/64 B；`https://…/api/state` → 200/64 B。**两个都活。**
- 线上 `state1.json` 当前返回：`{"Servers":["https://example.com/api/"]}` ⇒ 后续游戏 RPC 走 **https 裸域**。**首跳也走 https 才不会出现"http→https 混合"**。

### 3.5 什么情况下 **才** 需要 user CA

只有当你想 **MITM 官方域名**（`*.bluearchive-cn.com`）时才需要：那时服务器拿不出官方域名的公网证书，只能自签，客户端就必须信任自签 CA。这条路的两个前提缺一不可：

1. `res/Dk.xml` 写 `src="user"`（脚本默认 `--ca-mode user` 就会写 system+user）；
2. 用户把 CA 装成**用户证书**（PEM、文件名 `<subject_hash_old>.0`、或走系统设置安装）。

> 而**走我们自己的域名**（`example.com`）根本不需要 MITM ⇒ **不需要 CA** ⇒ 也不用碰 `--ca`。
> 这也是为什么生产命令里**不给 `--ca`**：给了会把 CA 塞进 `res/E5.ogg`（唯一的 raw 槽），副作用是扫码提示音失效，且换证书后必须重新打包。

---

## 4. Q4：`BA_noroot_v1.apk` 相对 `cn_base.apk` 改了哪些条目

方法：**只读 zip 中央目录**（不"全量解压"）：先比 `(file_size, CRC, compress_type)` 三元组，只有不一致的条目才读出内容算 sha256。

### 4.1 总账

```
cn_base entries = 41,312        BA_noroot_v1 entries = 41,307
新增 2 条 / 删除 7 条 / 内容变化 2 条 / 未变化 41,303 条
41,312 − 7 + 2 = 41,307   ✅ 账平
```

### 4.2 新增（2）

| 条目 | 大小 |
|---|---|
| `META-INF/CERT.SF` | 128 B |
| `META-INF/CERT.RSA` | 1,208 B |

### 4.3 删除（7）

| 条目 | 原大小 | 为什么删 |
|---|---|---|
| `assets/__tpinfo.tp` | 12 B | ACE 完整性清单，**不删必闪退** |
| `assets/__tpinfo.tsc` | 485,268 B | 同上（≈7,500 条 SHA-256 清单） |
| `assets/__tpinfo.tsc.sig` | 256 B | 同上（RSA-2048 签名） |
| `assets/__tpinfo.tsd` | 1,668 B | 同上 |
| `assets/__tpinfo.tsd.sig` | 256 B | 同上 |
| `META-INF/BACN.SF` | 5,151,804 B | 原厂 v1 签名，**不剔除会与新签名重名 ⇒ Android 拒装** |
| `META-INF/BACN.RSA` | 1,064 B | 同上 |

### 4.4 内容变化（2）

| 条目 | 原大小 → 新大小 | sha256 前 16（原 → 新） |
|---|---|---|
| `res/Dk.xml` | 264 → **560** | `f4861a2727f78aa4` → `39cbb25b3559a127` |
| `META-INF/MANIFEST.MF` | 5,151,677 → 5,147,484 | `0fc67eecc4fba3c6` → `73345dee46355c57` |

### 4.5 有没有误改？—— **没有误改，但有"没改"**

- **误改**：0。除上表 9 个条目外，**41,303 条内容（size+CRC+method 三元组）与原包完全一致**。所有 `.so`、`assets/` 全部未动。
- **该改没改**（这就是它不能发版的原因）：

| 条目 | v1 里的实际值 | 应该是 |
|---|---|---|
| `assets/SDKConfigSettings.json` | `sdk_url = 'https://sdk-api.yostar.cn'`（**原厂值**） | 我们的卡密站 |
| `assets/bin/Data/e37c46fe…` | `ServerInfoDataUrl = '["https://state-api.bluearchive-cn.com/api/state","https://stateqc-api.bluearchive-cn.com/api/state"]'`（**原厂值**） | 我们的 state 入口 |

  （这两条不在"变化列表"里，恰恰证明它们与原包**逐字节相同** —— 与 `NOROOT_BUILD.md` 自述"未打 `--sdk-url`，仅作流水线验证样本"一致。）

- **产物本身还不合规**：`--verify-only BA_noroot_v1.apk` → **exit 1**：

```
v2: OK
v3: OK
v1: 最长行 92 B, 超 72 B 的行 808 个（违反 JAR 规范）
v1: X-Android-APK-Signed = None（声明 空，APK 实有 [2, 3]）  ← 缺剥离保护/值不对
v1 结论: FAIL
STORED 4 字节对齐: OK / 重复条目: 无（OK）
resources.arsc: 第 1 条, STORED=True, 4 字节对齐=True
__tpinfo 残留: 无（OK）
```

  ⇒ v1 是 **2026-11-16 06:23** 的旧实现产物，早于 2026-11-17 01:10 的签名修复。**v2/v3 是好的**（Android 7+ 装机走 v2/v3，所以它"大概能装"，但按项目自己的判据它是 FAIL）。**不能当发版基线。**

---

## 5. Q5：唯一一条生产构建命令

在仓库根目录 `C:\Users\su\Desktop\大肥鱼项目\BAServer` 下执行（**PowerShell**）：

```powershell
python work\ba\noroot\build_noroot_apk.py `
  --src report\_tmp\cn_base.apk `
  --out work\ba\noroot\BA_noroot_prod_$(Get-Date -Format yyyyMMdd_HHmm).apk `
  --sdk-url https://example.com/sdk `
  --gmconfig-url https://example.com/api/state `
  --keystore work\ba\noroot\ba_private.keystore --storepass baserver --alias ba
```

（若想把输出名定死，把 `--out` 换成固定文件名，例如 `work\ba\noroot\BA_noroot_prod.apk`。）

### 5.1 逐参数理由

| 参数 | 取值 | 为什么 |
|---|---|---|
| `--src` | `report\_tmp\cn_base.apk` | 官方 3.0.2 / vc73 原包（2,126,400,085 B / 41,312 条）。脚本会硬校验 `package` / `versionCode` / `targetSdk` / `networkSecurityConfig` 资源 ID，**传错包会直接拒建**，所以不需要 `--force` |
| `--out` | 仓库内新文件名 | 不覆盖原包；`${时间戳}` 便于"这次崩的是哪一版"可追溯 |
| `--sdk-url` | `https://example.com/sdk` | ① 该主机 `listen 80` + `127.0.0.1:8443 ssl`，`location /sdk/ → proxy_pass 127.0.0.1:8080`；② 实测 `POST https://example.com/sdk/common/config` → **200 / 7838 B**；③ 用**公网真证书**，Java/okhttp 侧不需要任何 CA；④ 不用 `http://127.0.0.1:8080`，因为那要求每台手机跑本地中转，**无 root 分发就没了** |
| `--gmconfig-url` | `https://example.com/api/state` | ① **必须给整串 URL**：只给裸域名会被展开成 `state-api.<域名>`，而 `state-api.example.com` **NXDOMAIN**；② 裸域 `example.com` 有 A 记录 → `<SERVER_IP>`；③ 该主机 `GET /api/state` 实测 **200 / 64 B**；④ https 与线上 `state1.json` 返回的 `Servers` 同协议，避免混合降级；⑤ 产出值 `["https://example.com/api/state"]`（38 字符），远低于 101 字符上限 |
| `--keystore` | `work\ba\noroot\ba_private.keystore` | 默认值是**相对路径** `ba_private.keystore`，在仓库根跑必须显式给；证书 SHA-256 `94FA997B…E99EBC` |
| `--storepass` / `--alias` | `baserver` / `ba` | 与 keystore 内的值一致（默认值就是它俩，写上是为了显式、可审计） |
| **不给 `--ca`** | — | 走我们域名 + 公网真证书 ⇒ **不需要任何 CA**。给了会：① 把 CA 写进唯一 raw 槽 `res/E5.ogg`（扫码提示音失效）；② 换证书后必须重新打包 |
| **不给 `--rename-package`** | — | 改包名是"并行安装"策略，属要拍板项（§6-①） |
| 其余全默认 | `--ca-mode user` / `--v1` / `--arsc-first` / `--align-mode raw` / `--force` 未用 | 默认值即已验证配置 |

### 5.2 构建后必须紧接着做的两条验收（只读）

```powershell
# ① 签名 + 结构 + 字段 + 包名（exit 0 才算过）
python work\ba\noroot\build_noroot_apk.py --verify-only work\ba\noroot\BA_noroot_prod_<时间戳>.apk `
  --gmconfig-url https://example.com/api/state

# ② 用 Google 官方 aapt2 独立复核包名/版本/SDK（本机无 java，aapt2 是唯一外部尺子）
& "C:\Users\su\.gradle\caches\8.11.1\transforms\bedba16cea642164a45bf9eb6e21088d\transformed\aapt2-8.6.1-11315950-windows\aapt2.exe" `
  dump badging work\ba\noroot\BA_noroot_prod_<时间戳>.apk
```

> 判据：`--verify-only` **exit 0**，且输出含 `v1 结论: OK` / `v2: OK` / `v3: OK` / `__tpinfo 残留: 无（OK）` / `GameMainConfig: ServerInfoDataUrl == 期望值: OK`。
> ⚠ **不要**用 `--gmconfig-value '["…"]'` 的写法：Windows PowerShell 会吃掉参数里的双引号，值会变成 `[https://…]`（非法 JSON）。脚本现在有 JSON 护栏会当场 `die`，但更省事的做法就是用 `--gmconfig-url` 整串 URL。

---

## 6. Q6：必须由 Lead / 用户拍板的空白项（我不填）

| # | 空白项 | 为什么必须你定 | 候选/影响 |
|---|---|---|---|
| **①** | **发版用哪个包名？** 原包名 `com.RoamingStar.BlueArchive` 还是并行包名 `com.RoamingStar.BlueArchive2`？ | 决定用户**要不要卸载官方包**（卸载会连带删 11.1 GB 外部数据），也决定要不要加 `--rename-package` | A原包名：必须卸载官方包，数据要重下；B并行：不碰现役数据，但 ACE 是否认新包名**未验证** |
| **②** | **`--out` 的最终文件名/版本号** | 发版命名与追溯策略，不是技术问题 | 我给的是带时间戳的示例名 |
| **③** | **首个 state 请求走 https 还是 http** | 我推荐 https（证书已换成 LE、链公网可信、与线上 `Servers` 同协议）；若选 http 需确认是否接受"http→https 混合" | https：依赖证书续期（LE 可自动续）；http：不依赖证书，但与后续 `Servers=https` 混合 |
| **④** | **`ServerInfoDataUrl` 用单条还是双条** | 原厂是「主 + qc」两条，我只放一条（`["https://example.com/api/state"]`）。若客户端需要双条做容灾/测速，需要第二条可解析的主机 | 单条：38 字符，余量极大；双条：需第二个可解析主机（当前没有） |
| **⑤** | **要不要为零 padding 去加一条 DNS** | 值短于 101 字符时，`gmconfig_rewrite` 会在**第一层 JSON 尾部**补空格（本次 38 字符 ⇒ 补 **168 个空格**）。JSON 尾部空白对标准解析器无害，但**客户端解析器是否容忍未实测** | 保持现状（接受 168 空格）；或加一条 18/19 字符的 DNS 记录 + 用裸域名形式做到 101 字符零 padding |
| **⑥** | **发布前的最终判据** | 本机**没有 java / apksigner / adb**，我能给的最强离线证据是 `--verify-only`(自研) + `aapt2 dump badging`(Google) + 包内解码。**"能装上 / 能登录 / 能打关卡"只能真机** | 是否接受"离线全绿 + 真机装机"为放行标准 |

---

## 7. 我推翻 / 纠正的旧说法

| # | 旧说法 | 实测/新证据 | 影响 |
|---|---|---|---|
| **①** | **"`example.com` 证书 2026-12-12 到期，只剩 25 天"**（我自己 2026-11-17 20:52 的记录） | **证书已在今天被换成 Let's Encrypt**：`notBefore 2026-11-17 11:50:26Z` / **`notAfter 2027-02-15 11:50:25Z`**，issuer `Let's Encrypt CN=YR2`，链 3 张 → `ISRG Root X1`，`ssl_verify_result=0` | **"25 天定时炸弹"解除**；且 LE 可走宝塔 ACME 自动续期。**这是本轮最重要的更正** |
| **②** | 两个预制的 `GameMainConfig_*.bin` 可作发版素材 | 两者分别指向 `bapsvr-prods-cn.com`（NXDOMAIN）与 `state-api.example.com`（NXDOMAIN）。**一个都不能用** | 生产命令必须用整串 URL 形式现场生成 |
| **③** | `--gmconfig-url <裸域名>` 是"最优写法"（脚本 help 与 `NOROOT_BUILD.md` 都这么写） | 只有当那个域名的 `state-api.` / `stateqc-api.` 子域**存在**时才成立。对当前唯一可用域名 `example.com`，**子域 NXDOMAIN** ⇒ 该写法产出不可用配置 | 必须用 `--gmconfig-url https://<可解析主机>/api/state` |
| **④** | `BA_noroot_v1.apk` 是"流水线验证样本"（文档已说明，但容易被当成准成品） | 我把它量化了：`--verify-only` **exit 1**；`sdk_url` 与 `ServerInfoDataUrl` 均为**原厂值**；41,303 条内容与原包完全一致 | 不能当发版基线，必须重跑 |
| **⑤** | 我之前扫 `certifi` 命中 56 次，像是"内嵌 CA bundle" | **假信号**：`certifi` 是 `certificate` 的子串，56/56 全部落在 `certificate` 里，独立 `certifi` 串 = **0** | 纠正了我自己的 needle 选择；**libunity 里没有 certifi CA bundle** |
| **⑥** | "游戏本体（Unity libcurl / UnityTLS / BoringSSL）读 `AndroidCAStore` 用户库"（`NOROOT_BUILD.md §2.2` 的表述） | `AndroidCAStore` 在 libunity/libil2cpp 里**各 0 命中**；`/system/etc/security/cacerts` 也是 0；真实路径是 **JNI → Java `TrustManagerFactory` → `X509TrustManager`** ⇒ 信任集由 **app 的 NSC** 决定，不是直接读文件系统 | 结论方向不变（`src="user"` 有效），但**机制表述要改**：不是"读 AndroidCAStore 文件"，而是"读 NSC 的 trust-anchors" |

---

## 8. 证据附录（可复现命令）

```powershell
# A. 参数清单
python work\ba\noroot\build_noroot_apk.py --help

# B. GameMainConfig 逐字段 + 两份 .bin 的 diff（0x1154..0x1458，306 B，全在 m_Script 内）
cd work\ba\noroot
python -c "import sys;sys.path.insert(0,'.');import build_noroot_apk as B;print(B.gmconfig_read(open('GameMainConfig_http_example.com.bin','rb').read())['fields'])"

# C. .so trust store 扫描（本文件 §3.2 的原始输出）
python -c "d=open('_tmp/libunity.so','rb').read();print([(n,d.count(n)) for n in (b'AndroidCAStore',b'/system/etc/security/cacerts',b'TrustManagerFactory',b'X509TrustManager',b'checkServerTrusted',b'getAcceptedIssuers')])"

# D. v1 vs cn_base 中央目录对比（§4）
#    见本文件 §4；方法：比 (file_size, CRC, compress_type)，仅差异条目才读内容

# E. 证书链
openssl s_client -connect example.com:443 -servername example.com -showcerts < NUL | openssl x509 -noout -dates -issuer -ext subjectAltName

# F. 线上端点（只读）
curl.exe -s https://example.com/api/state
curl.exe -s -o NUL -w "%{http_code} %{size_download}`n" -X POST -H "Content-Type: application/json" -d "{}" https://example.com/sdk/common/config
```

### 8.1 本轮产生的临时文件（可随时删）

```
work\ba\noroot\_tmp\libil2cpp.so   270,927,056 B  sha256 前16 5ac1cbe0fb8f730f
work\ba\noroot\_tmp\libunity.so     20,950,552 B  sha256 前16 01568fac74ab1cf5
```
（均为源包内原样解包，未修改。）
