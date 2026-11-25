# GameMainConfig（`ServerInfoDataUrl`）接入 `build_noroot_apk.py`

> 工作目录：`work\ba\noroot\`　　日期：2026-11-17
> 解释器：`C:\Users\su\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe`（3.12.14）
> **本轮没有连服务器、没有操作手机、没有修改 `report\_tmp\cn_base.apk`、没有构建 2.12 GB 的完整 APK。**
> 相关文档：`GAMEMAINCONFIG_CN.md`（§3 布局 / §9 预算与方案）、`NOROOT_TLS_RESEARCH.md`（路径 C）、
> `AUDIT_BUILD_NOROOT.md`（P1-1…P1-4）

---

## 0. 一句话结论

`build_noroot_apk.py` 现在**能自己改 `ServerInfoDataUrl` 并产出「指向自己服务器」的包**：
新增 `--gmconfig-url`（便利参数，内部自己算 key8、自己加密、强制等长）和
`--asset-replace NAME=PATH`（通用逃生口），构建后自动从产物 APK 回读解密自检；
顺带修掉审计里 4 条纯代码问题（v1 `.SF` 缺剥离保护、`MANIFEST.MF` 行宽、`--verify-only` 不验 v1、cert/私钥不配对）。

实测要点（全部在下面 §5 有原始输出）：

| 判据 | 结果 |
|---|---|
| `http://` + 19 字符域名 → value 101 字符 | ✅ 等长，**layer1 JSON 545/545，补 0 空格**，密文差 **80 B** |
| 产物仍是 5,212 B、`m_Script` 仍 1,090 B、全部偏移不变 | ✅ 硬断言，不满足直接 `die` |
| 反解 6 字段、其余 5 字段**值与密文 b64 双重逐字节比对** | ✅ |
| 本工具产出与 `_cn_patch.py` 的 `PATCHED_*.bin` | ✅ **逐字节相同**（sha256 `19DE5A15…`） |
| 非法输入（超预算 / 坏结构 / 私钥证书不配对） | ✅ 全部明确拒绝，退出码 1 |
| `v1` 校验器对**官方** `cn_base.apk` | ✅ 41,309 条摘要全对、PKCS#7 验签 OK、`X-Android-APK-Signed: 2, 3` |
| `MANIFEST.MF` 换行与官方 | ✅ 41,309 个 `Name:` 行**逐字节相同** |

---

## 1. 改了什么

### 1.1 文件

| 文件 | 说明 |
|---|---|
| `build_noroot_apk.py` | 主改动，1,245 → **2,510 行**（含并行任务叠加的 P1-6 约 130 行）；当前 sha256 `0CC4E68D…9B9B` |
| `build_noroot_apk.py.orig` | **改动前原文件备份**（sha256 `3C4E3293…B302`，与本轮开始时的文件一致） |
| `build_noroot_apk.py.bak-before-gmconfig` | 同一份的第二个副本（双保险） |
| `GMCONFIG_INTEGRATION.md` | 本文档 |
| `_gmc_crosscheck.py` | 交叉校验：合成 asset vs 真实 asset、本工具产物 vs `_cn_patch.py` 产物 |
| `_gmc_cli_test.py` | CLI 端到端测试（10 组，合成 APK，不碰 2 GB 源包） |
| `_probe_v1fmt.py` / `_probe_p7.py` / `_probe_jarwrap.py` | 只读取证：官方 v1 文件格式、PKCS#7 SignerInfo、`MANIFEST.MF` 换行 |
| `GameMainConfig_http_example.com.bin` | `--gmconfig-selftest` 用真实源包数据算出来的产物（5,212 B，示例域名，**不是**最终域名） |

> ⚠ **并发编辑提醒**：本文件在 2026-11-17 01:07–01:10 期间被**另一个并行任务**同时修改
> （它加了 AUDIT **P1-6** 源包身份校验 `§10b check_source_identity()`、`--force` 参数，
> 并把 `verify_v1()` 的 `X-Android-APK-Signed` 检查升级成"整型集合 + 覆盖 v2/v3"）。
> 两边改动是叠加的、不冲突（我最后跑到的是 2,510 行、`py_compile OK`、`--self-test`/CLI 测试全绿），
> 但**再改这个文件前请先确认没有别的手在写**：本文档描述的是我这部分改动，位于
> `§0b / §3(cert_*) / §9(jar_line,build_v1) / §9.5 / §10 的 [2b][2c][7] / §11(verify_v1,verify_pkcs7) / §12 / §13 / §14`。
> 因为 P1-6 现在会对 `--src` 做包名/版本校验，**用合成小包做测试必须加 `--force`**（`--self-test` 内部已用 `force=True`，
> `_gmc_cli_test.py` 的公共参数里也加了 `--force`）。

### 1.2 代码结构（新增/改动按文件内小节编号）

```
§0b    GameMainConfig 常量（GMC_ENTRY / GMC_SIZE / 0x1004 / 0x1014 / 0x1018 / 6 字段 / 两条 URL 模板）
§3     cert_spki() / cert_pub_n_e() / assert_key_pair()          ← AUDIT P1-4
§9     jar_line() / build_v1()（重写）/ jar_parse()               ← AUDIT P1-1、P1-2
§9.5   GameMainConfig 等长替换（全新）：
         xxhash32 / _MT19937 / gmconfig_create_key / gmconfig_xor      ← 照 CRYPTO_MT.py
         gmconfig_check_layout / gmconfig_read / gmconfig_budget
         gmconfig_budget_msg / gmconfig_value_from_spec
         gmconfig_domain_token / gmconfig_rewrite / gmconfig_selfcheck
§10    do_build()：新增 gmconfig_value / gmconfig_pad / asset_replace 三个参数
         + [2b] GameMainConfig 替换、[2c] 通用 asset 替换、[7] 产物回读自检
§11    parse_pkcs7 / _p7_message_digest / verify_pkcs7 / verify_v1 / _signer_certs
         + verify(require_v1=True, expect_gmconfig=None)          ← AUDIT P1-3
§12    load_key() / gen_keystore()：加配对断言                    ← AUDIT P1-4
§13    self_test()（扩充到 6 组）+ gmconfig_synth() + gmconfig_selftest()
§14    CLI：6 个新参数
```

`create_key` / XOR **完全照 `_extract_cn` 的 `CRYPTO_MT.py` 搬**（xxHash32 → MT19937 →
`Next()=(genrand_int32()>>1)&0x7FFFFFFF` → `create_key=NextBytes(8)`），没有重新发明；
锚点用 `CRYPTO_MT.py` 的自检真值钉死（见 §5.1）。工具仍是**单文件、纯标准库、零依赖**。

---

## 2. 新参数与用法

### 2.1 `--gmconfig-url`（推荐入口）

```powershell
$py="C:\Users\su\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"

# C 路径（最优）：只给域名，默认 http，19 字符
& $py build_noroot_apk.py --src "report\_tmp\cn_base.apk" --out "work\ba\noroot\BA_noroot_v2.apk" `
      --sdk-url https://<卡密服务> `
      --gmconfig-url bapsvr-prods-cn19.com `
      --keystore ba_private.keystore --storepass baserver
```

接受 4 种输入（`gmconfig_value_from_spec()`）：

| 输入 | 解释 | 结果 value |
|---|---|---|
| `bapsvr-prods-cn.com`（纯域名） | 默认 `http`（可用 `--gmconfig-scheme` 改） | `["http://state-api.<d>/api/state","http://stateqc-api.<d>/api/state"]` |
| `http(s)://state-api.<d>/api/state` | 取出 `<d>`，保留条数与路径 | 同上，scheme 取自输入 |
| `https://x/si.json`（任意 URL） | 单元素数组 | `["https://x/si.json"]` |
| `["http://a/api/state"]`（以 `[` 开头） | 原样作为 value | 原样 |

### 2.2 `--gmconfig-value`（直接给完整值）

```powershell
& $py build_noroot_apk.py ... --gmconfig-value '["http://ba.example.com/api/state"]'
```

比原值短时**自动用尾部空格把 layer1 JSON 补满 545 字符**（`GAMEMAINCONFIG_CN.md` §9.3 方案 B，
`json.loads` 允许尾部空白）；不想补就加 `--no-gmconfig-pad`（短值直接拒绝）。

### 2.3 `--gmconfig-scheme http|https`

覆盖协议。例：`--gmconfig-url https://state-api.xxx.com/api/state --gmconfig-scheme http`
= 把现成的 https URL 降成 http 方案（每条省 1 字符）。

### 2.4 `--asset-replace NAME=PATH`（通用逃生口，可多次）

```powershell
& $py build_noroot_apk.py ... `
      --asset-replace "assets/bin/Data/e37c46fea17834108a4756797197d05a=_extract_cn\PATCHED_e37c...bin" `
      --asset-replace "assets/SDKConfigSettings.json=my_sdk.json"
```

- 换 `GameMainConfig` 时会**强制**跑结构校验 + 6 字段自检（不符合就拒绝）；
- 换别的条目按原样写入、重算 CRC/size、重算 v1/v2/v3；
- 与 `--gmconfig-url` 同时指向 `GameMainConfig` 会报冲突。

### 2.5 `--gmconfig-selftest`（不构建 APK，只测替换算法）

```powershell
& $py build_noroot_apk.py --src "report\_tmp\cn_base.apk" --gmconfig-selftest
# 可选：--gmconfig-url <域名或URL> 换测试域名（默认 bapsvr-prods-cn.com）
```

会跑：结构校验 → 反解 6 字段 → 预算计算 → C 路径替换（落盘 `GameMainConfig_http_<域名>.bin`）
→ 方案 A 替换 → 两次非法输入拒绝 → 落盘文件回读复核。

### 2.6 `--verify-only` 变强了

```powershell
& $py build_noroot_apk.py --verify-only BA_noroot_v2.apk
& $py build_noroot_apk.py --verify-only BA_noroot_v2.apk --gmconfig-url bapsvr-prods-cn19.com
```

现在会验：v2/v3（原有）+ **v1**（逐条摘要 / 整份摘要 / PKCS#7 验签 / 72 B 行宽 / `X-Android-APK-Signed`）
+ **v1 与 v2/v3 证书一致性** + **GameMainConfig**（结构、6 字段；给 `--gmconfig-url` 时还会断言 `ServerInfoDataUrl` 等于该值）。

---

## 3. 等长约束是怎么校验的

### 3.1 输入侧（`gmconfig_check_layout`）

对**任何**要写进 `GameMainConfig` 的字节（不管是本工具算的还是 `--asset-replace` 给的）先做硬校验：

| # | 断言 | 失败信息 |
|---|---|---|
| 1 | 文件长度 **= 5,212 B** | `文件 N B，必须是 5212 B（m_Script 固定 1090 B；变长会改 SerializedFile 头部大小字段/文件大小/zip 条目…）` |
| 2 | `0x1000` u32 = 14、`0x1004` = `GameMainConfig` | `0x1000 处 name_len=… / m_Name=…，期望 14 / 'GameMainConfig'` |
| 3 | `0x1014` u32 = **1,090** | `m_Script_len@0x1014 = N，必须是 1090` |
| 4 | `0x1018 + 1090 + 2 == 5212` | `偏移对不上` |
| 5 | `0x1004+14 .. 0x1014` 对齐 padding 全 0 | `对齐 padding 不是全 0` |

### 3.2 改写侧（`gmconfig_rewrite`）

1. 先要求**第一层 JSON 能被原样重建**：`json.dumps(json.loads(plain), separators=(',',':')) == plain`；
   不一致就拒绝（说明布局与文档不符，不能盲改）。
2. 预算检查（见 §4），超了直接 `die` + 完整预算说明。
3. 组装新 JSON（可能补尾部空格）→ UTF-16LE → `XOR cycle8(create_key("GameMainConfig"))`，
   **必须正好 1,090 B**。
4. 只替换 `[0x1018, 0x145A)` 这一段，然后逐条硬校验：

| # | 断言 |
|---|---|
| 6 | 输出长度 `== 5212` |
| 7 | `out[0:0x1018] == asset[0:0x1018]`（头部/长度字段逐字节不变） |
| 8 | `out[0x145A:] == asset[0x145A:]`（尾部 padding 不变） |
| 9 | 回读 `m_Script_len == 1090` |
| 10 | 回读 `ServerInfoDataUrl == 新值` |
| 11 | 其余 5 字段：**值相等** 且 **密文 b64 逐字节相等**（证明只动了这一个值） |

### 3.3 产物侧（`gmconfig_selfcheck`，构建后自动跑）

从**产物 APK** 里 `zipfile.read(GMC_ENTRY)`：

- zip 声明大小与实读大小都必须是 5,212 B；
- 重新解 6 字段，必须 **6/6**；
- `ServerInfoDataUrl` 必须等于本次指定的值；
- 其余 5 字段与**源包**逐字段比对（值 + 密文 b64），不一致直接 `die`（构建失败，不会留下“看着像成功”的包）。

---

## 4. 预算口径与可行组合

### 4.1 结构（真实源包实测）

```
m_Script 固定 1090 B = 545 个 UTF-16 字符（cap）
第一层 JSON 当前正好 545 字符，余量 0
  其中 ServerInfoDataUrl 的 base64 占 272 字符
  其余固定开销 273 字符（另外 5 个字段的 base64 + 引号/逗号/花括号）
⇒ 值的 b64 ≤ 272 字符 ⇒ 值 ≤ 102 字符（精确口径；b64 按 3 B 分组，长度不是严格线性）
  文档 §9.1 的保守口径：545 - 444 = 101 字符（工具两种都打印）
```

### 4.2 实测组合（每条 URL 都是 `state-api.<d>` / `stateqc-api.<d>` + `/api/state`）

| scheme | 域名长 | value 字符 | b64 | layer1 JSON | 结论 |
|---|---|---|---|---|---|
| `http` | **19** | **101** | 272 | **545** | ✅ **恰好占满，补 0 空格**（C 路径，最优） |
| `http` | 18 | 99 | 264 | 537 | ✅ 补 8 个尾部空格 |
| `https` | **18** | **101** | 272 | **545** | ✅ 恰好（方案 A，`GAMEMAINCONFIG_CN.md` §9.2） |
| `https` | 19 | 103 | 276 | 549 | ❌ **超 4 字符，放不下** |
| 任意 | — | ≤ 102 | — | ≤ 545 | ✅ 短的用空格补齐 |
| 单条 URL | — | 4+len(url) ≤ 102 | — | ≤ 545 | ✅ `--gmconfig-value '["http://…"]'` |

公式：`len(value) = 63 + 2×域名长`（http）、`= 65 + 2×域名长`（https）。

> ⚠ **更正任务书里的一条算术**：任务书写「B 路径：https 保持，域名取 19 字符，需要补 1 个空格」。
> 实际 `https + 19 字符域名` 的 value 是 **103 字符**（比 101 多 2），b64 变 276，**JSON 549 > 545，超 4 字符**，
> 补空格救不了（补空格只能救“变短”的方向）。所以 **https 路线域名必须是 18 字符**；
> 想要 19 字符域名只能用 `http`（C 路径）。工具对这两种都给出精确的数字拒绝信息（见 §5.3）。

---

## 5. 自检结果（实际跑了什么、输出了什么）

### 5.1 `--self-test`（离线合成，PASS，退出码 0）

合成一个真实结构的 5,212 B asset（`gmconfig_synth()`），再走完整打包+校验。
关键输出：

```
[*] A. 算法锚点（对照 CRYPTO_MT.py 自检真值）
    [ok]   xxHash32('') = 0x02CC5D05
    [ok]   xxHash32('abc') = 0x32D153FF
    [ok]   create_key('GameMainConfig') = 1b 23 28 06 ad 72 c2 57
[*] B. GameMainConfig 等长替换（合成 5,212 B asset）
    [ok]   预算 cap=545 字符 / 保守上限=101 / 原值=101；精确上限=102
    [ok]   C 路径（http + 19 字符域名）value = 101 字符
    [ok]   产物 5212 B（等长）
    [ok]   无需补空格（JSON 545/545）
    [ok]   0x0..0x1018 头部逐字节不变      [ok] 尾部 padding 不变
    [ok]   反解 ServerInfoDataUrl == 新值  [ok] 其余 5 字段反解后逐字段未变
    [ok]   其余 5 字段密文 b64 逐字节未变
    密文差异 80 B
    [ok]   方案 A（https + 18 字符域名）value = 101 字符 / 补 0 空格 / 密文差异 28 B
    [ok]   方案 B 短值 34 字符 -> 补 180 空格 -> 5212 B
    [ok]   拒绝：短值 + --no-gmconfig-pad
[*] C. 非法输入必须拒绝（预算超限）
    [ok]   拒绝：http + 40 字符域名
    [ok]   拒绝：https + 19 字符域名（value 103 字符）
    [ok]   拒绝：单条 URL 101 字符（value 105）
    [ok]   拒绝：坏 asset（长度 5211）
[*] D. cert/私钥配对校验
    [ok]   配对的 key/cert 通过        [ok]   拒绝：key A + cert B
[*] E. 打包 -> 校验（v1/v2/v3 + GameMainConfig 自检）
[2b] assets/bin/Data/e37c46fea17834108a4756797197d05a: 5212 B -> 5212 B  (等长 OK, 密文差异 80 B, 补 0 空格)
[2b] 预算: cap=545 字符, 固定开销=273, 上限=101(保守)/102(精确), layer1 JSON=545/545
[7] 自检：从产物 APK 回读 GameMainConfig（解密 + 6 字段比对）
    out.apk: 5212 B, m_Script=1090 B, 字段 6/6
      SkipTutorial       = 'False'
      ServerInfoDataUrl  = '["http://state-api.bapsvr-prods-cn.com/api/state", ...]'
      ServerName         = 'prod'      VersionCode = '73'
      PlatformID         = '1'         ChannelID   = '1'
[7] 其余 5 字段与源包逐字节相同：OK（值 + 密文 b64 双重比对）
  v1: 最长行 70 B, 超 72 B 的行 0 个（OK）
  v1: X-Android-APK-Signed = '2, 3'
  v1: 逐条摘要 7 条, 不符 0；SHA-256-Digest-Manifest OK；PKCS#7 验签 OK
  v1 与 v2/v3 证书一致: OK      v1 结论: OK
[*] F. 签名器修复项取证
    [ok]   MANIFEST.MF 最长行 70 B ≤ 72（原实现最长 92 B）
    [ok]   有续行（首字节空格），signapk 风格
    [ok]   .SF 含 X-Android-APK-Signed: 2, 3
    [ok]   META-INF 只有 MANIFEST.MF/CERT.SF/CERT.RSA
    [ok]   产物 APK 回读 ServerInfoDataUrl 正确
[*] self-test PASS
```

### 5.2 `--gmconfig-selftest`（**真实**源包 `cn_base.apk`，只读访问，PASS）

```
[*] 读源包 C:\...\report\_tmp\cn_base.apk
    assets/bin/Data/e37c46fea17834108a4756797197d05a  5212 B
    [ok]   6 个字段全解出
      SkipTutorial       = 'False'
      ServerInfoDataUrl  = '["https://state-api.bluearchive-cn.com/api/state","https://stateqc-api.bluearchive-cn.com/api/state"]'
      ServerName         = 'prod'    VersionCode = '73'    PlatformID = '1'    ChannelID = '1'
    预算：cap=545 字符（m_Script 1090 B），固定开销=273，原值=101，上限=101(保守)/102(精确)
[*] C 路径：http + 19 字符域名 -> value 101 字符
    [ok]   产物 5212 B（等长）
    [ok]   layer1 JSON 545/545，无需补空格
    [ok]   密文差异 80 B（范围 0xF6..0x288）
    [write] ...\GameMainConfig_http_example.com.bin
    [ok]   落盘后反解 == 新值
    [ok]   其余 5 字段逐字段未变 / 密文 b64 未变 / 头部逐字节不变
[*] 方案 A：https + 18 字符域名
    [ok]   value 101 字符，密文差异 28 B
[*] 拒绝测试
    [ok]   拒绝：http + 40 字符域名
    [ok]   拒绝：https + 19 字符域名（value 103）
[*] gmconfig-selftest PASS
```

### 5.3 拒绝时的实际报错（原文）

```
ERROR: ServerInfoDataUrl 放不下：新值 103 字符（UTF-16 代码单元 103）
  预算：m_Script 固定 1090 B = 545 个 UTF-16 字符（cap）
        第一层 JSON 当前 545 字符，余量 0（国服 3.0.2 实测为 0）
        其中本字段 b64 占 272 字符，其余固定开销 273 字符（5 个字段的 b64 + 引号/逗号/花括号）
        值上限：101 字符（保守口径 cap-444）/ 102 字符（精确口径，b64 按 3 B 分组）
        本次值 base64 后 JSON 需 549 字符，超预算 4
  可行办法：① 用 http:// 代替 https://（每条 URL 省 1 字符，C 路径）
            ② 缩短域名（http 最长 19 字符；https 最长 18 字符）
            ③ 只保留一条 URL（["<url>"]，url ≤ 98 字符）
            ④ 用 --gmconfig-value 直接给更短的整串
```

```
ERROR: --key-pem/--cert-pem: 私钥与证书不配对：
  私钥 n = 1024 bit, e = 65537
  证书 n = 1024 bit, e = 65537
  （v2/v3 要求 signer 公钥 == 第一张证书公钥，不配对会被 INSTALL_PARSE_FAILED_NO_CERTIFICATES 一类拒装）
```

### 5.4 `_gmc_cli_test.py`（CLI 端到端，10 组，PASS）

> 合成小包没有真国服清单，**必须带 `--force`** 跳过 P1-6 源包身份校验（脚本的公共参数里已加）。

| # | 场景 | 结果 |
|---|---|---|
| T1 | `--gmconfig-url bapsvr-prods-cn.com` | 退出 0；`5212 -> 5212 B`；无需补空格；产物回读正确 |
| T2 | `--gmconfig-value '["http://ba.example.test/si.json"]'` | 退出 0；补空格；回读 == 该值 |
| T3 | `--asset-replace GMC=<本地 bin>` | 退出 0；结构自检通过；产物条目与本地文件逐字节相同 |
| T4 | `https://state-api.<19 字符>.com/api/state` | **退出 1**，给预算说明 |
| T5 | `--asset-replace GMC=<5,211 B 坏文件>` | **退出 1**，`必须是 5212 B` |
| T6 | `--key-pem A --cert-pem B` | **退出 1**，`不配对` |
| T7 | `--gmconfig-scheme` 覆盖（https 输入→http；18 字符域名+https） | 退出 0，值正确 |
| T8 | `--no-v1` 构建 | 退出 0（v1 校验按 `require_v1` 关闭，不误报） |
| T9 | `--asset-replace assets/SDKConfigSettings.json=…`（普通条目） | 退出 0，条目逐字节相同 |
| T10 | `--verify-only --gmconfig-url <域名>` | 值匹配退出 0；换成别的域名**退出 1** |

### 5.5 交叉验证（`_gmc_crosscheck.py`）

```
[1] synth vs real
    0x1018..0x145A (m_Script) equal: True      ← 合成资产的 m_Script 与真实源包逐字节相同
[2] builder output vs _cn_patch.py PATCHED (scheme A, https 18)
    mine sha 19de5a15fe57bde4   ←→  patched sha 19de5a15fe57bde4
    byte-identical to _cn_patch.py output: True
[3] builder http output: 5212 B，round-trip OK，其余 5 字段未变，密文差异 80 B
```

即：**本工具算出来的 `GameMainConfig` 与上一轮独立脚本 `_cn_patch.py` 的产物逐字节相同** —
两条独立代码路径互证，`create_key` / 二层 XOR / JSON 重排布都没有偏差。

### 5.6 校验器对**官方包**的验证（证明 v1 校验不是“只对自己的产物有效”）

```
[*] 校验 report\_tmp\cn_base.apk (1.98 GB)
  v2: OK    v3: OK    zip 完整性: OK
  v1: MANIFEST.MF 5151677 B, 41309 个 Name 段
  v1: 最长行 70 B, 超 72 B 的行 0 个（OK）
  v1: 逐条摘要 41309 条, 不符 0, 条目缺失 0 OK
  v1: META-INF/BACN.SF SHA-256-Digest-Manifest OK（41309 个逐条段）
  v1: X-Android-APK-Signed = '2, 3'
  v1: META-INF/BACN.RSA 对 .SF 的 PKCS#7 验签 OK
  v1: 签名者证书 SHA-256 = 20E318B9…CAB4CE     （与 v2/v3 一致：OK）
  v1 结论: OK
  __tpinfo 残留: [...5 条...]      ← 退出码 1 的唯一原因（官方包本来就带，本工具会删）
  GameMainConfig: 5212 B, m_Script=1090 B, 字段 6/6
```

### 5.7 `MANIFEST.MF` 换行与官方逐字节比对（`_probe_jarwrap.py`）

```
names checked      : 41309
mismatch           : 0
max line len mine  : 70 (official max = 70 )
RESULT: PASS
```

把官方 41,309 个 `Name:` 属性重新用 `jar_line()` 生成（含 1,254 条换行），**全部逐字节相同**。

---

## 6. 签名器四项修复的前后对比

### P1-1 `.SF` 缺 `X-Android-APK-Signed: 2, 3`

| | 前 | 后 |
|---|---|---|
| 代码 | `build_v1()` 只写 `Signature-Version` / `Created-By` / `SHA-256-Digest-Manifest` | 追加 `X-Android-APK-Signed: 2, 3`（位置与官方 `BACN.SF` 一致：`SHA-256-Digest-Manifest` 之后、空行之前） |
| 旧产物 `BA_noroot_v1.apk` | `v1: X-Android-APK-Signed = None` | — |
| 新产物 | — | `v1: X-Android-APK-Signed = '2, 3'` |
| 官方包对照 | `BACN.SF` 有这一行 | 一行不差 |

### P1-2 `MANIFEST.MF` 有 808 行超过 72 B

| | 前 | 后 |
|---|---|---|
| 代码 | `mf += 'Name: %s\r\nSHA-256-Digest: %s\r\n\r\n'`（不换行） | `jar_line(prefix, value)`：内容 ≤ 70 B/行，续行以单个空格开头（续行正文 ≤ 69 B），UTF-8 安全切分 |
| `BA_noroot_v1.apk`（旧） | 5,147,484 B，**808 行 > 72 B，最长 92 B** | — |
| 新产物 | — | `最长行 70 B，超 72 B 的行 0 个`；与官方 41,309 条 `Name:` 行逐字节相同 |

### P1-3 `--verify-only` 完全不验 v1

| | 前 | 后 |
|---|---|---|
| 代码 | `verify()` 只做 v2/v3 + zip 完整性 + 对齐 + 重名 + tpinfo + NSC | 新增 `verify_v1()`：① 逐条 `SHA-256-Digest`（按条目流式重算）② `.SF` 的 `SHA-256-Digest-Manifest` ③ `.RSA` 的 PKCS#7 RSA 验签（支持 signedAttrs 形式）④ 72 B 行宽 ⑤ `X-Android-APK-Signed` ⑥ v1 证书 == v2/v3 证书 |
| 对旧产物 `BA_noroot_v1.apk` | **exit 0，全绿**（假阳性） | **exit 1**：<br>`v1: 最长行 92 B, 超 72 B 的行 808 个（违反 JAR 规范）`<br>`v1: X-Android-APK-Signed = None ← 缺剥离保护`<br>`v1 结论: FAIL`<br>（逐条摘要 41,304 条 0 不符、PKCS#7 OK — 与审计 §P1-3 的人工复算完全一致） |
| 对官方 `cn_base.apk` | — | `v1 结论: OK`（41,309 条摘要 + PKCS#7 全过） |

### P1-4 cert / 私钥不配对

| | 前 | 后 |
|---|---|---|
| 代码 | `load_key()` 两条路径都直接 `return key, cert`；`do_build()` 只算 `pub = rsa_public_der(key)`，`_verify_signer()` 用块内 `pub` 自验（所以永远发现不了） | 新增 `cert_spki()` / `cert_pub_n_e()` / `assert_key_pair()`；在 `load_key()`（PEM 路径与 PKCS#12 路径）、`do_build()` 开头、`gen_keystore()` 返回前三处断言 `cert 公钥 (n,e) == key (n,e)`，不等直接 `die` |
| 行为 | `--key-pem A --cert-pem B` → 产出一个装不上的包，工具自验全绿 | `ERROR: … 私钥与证书不配对` + 双方 n/e，退出码 1（CLI 测试 T6） |

> 四项改动**互相独立**：`P1-1/P1-2` 只在 `build_v1()`/`jar_line()`，`P1-3` 只在 `verify_v1()`，
> `P1-4` 只在 `assert_key_pair()` 与三处调用点；与 GameMainConfig 那一段（§9.5）没有耦合，可分别回滚。

---

## 7. 没做的 / 需要你确认的

1. **没有构建 2.12 GB 的完整 APK**（按要求）。集成验证用的是：真实 asset（`--gmconfig-selftest`）+
   携带真实结构 asset 的合成小包（`--self-test` / `_gmc_cli_test.py`）。真正出包时用 §2.1 的命令即可。
2. **域名还没定**。当前只能确认长度约束：
   - `http` 路径：域名 **≤ 19 字符**（19 正好占满，无需补空格）；
   - `https` 路径：域名 **≤ 18 字符**；
   - 单条 URL：url ≤ 98 字符。
   请给一个具体域名（例如 19 字符的 `xxxxxxxxxxxxxxxxxxx.com`），我再生成 `BA_noroot_v2.apk`。
3. **`http://` 是否被客户端接受，本轮仍未验证**（`NOROOT_TLS_RESEARCH.md` 路径 C 的唯一死点）——
   需要真机一次 `GET /api/state` 才能钉死。若不接受，退路是 `https` + 18 字符域名（方案 A）+ `--ca` 内置 CA。
4. 审计里**不在本次四项**范围内的：P1-6（源包身份）由**并行任务**接线中（`§10b` + `--force`，
   实测真实源包通过：`package=com.RoamingStar.BlueArchive versionCode=73 versionName=3.0.2
   minSdk=24 targetSdk=33 nsc=0x7F120001`）；P1-5（`resources.arsc` 强制 STORED 硬失败）是否已接、
   §2.1（`.SF` 逐条 `Name:` 段）仍未做——后者 apksig/Android 在整份摘要匹配时不需要，
   本工具产物已验证 41,304 条逐条摘要全对。

---

## 8. 回滚

```powershell
# 全部回滚
Copy-Item build_noroot_apk.py.orig build_noroot_apk.py -Force

# 只回滚签名器四项：删掉 §9 的 jar_line/build_v1 新版、§11 的 verify_v1、§12 的 assert_key_pair，
# 用 .orig 里对应的 4 段替换（其余 GameMainConfig 代码可保留，两者无耦合）
```

新增文件（`_gmc_*.py`、`_probe_*.py`、`GameMainConfig_http_*.bin`、本文档）都是独立文件，删除不影响构建器。
