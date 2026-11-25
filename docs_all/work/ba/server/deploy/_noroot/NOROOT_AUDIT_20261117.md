# 无 root 客户端审计（NOROOT_AUDIT_20261117）

> 作者：ca-researcher（`_noroot\` 目录独占写入；本轮**只读**，未构建、未改任何文件）
> 时间：2026-11-17 20:14–21:05 (+08:00)
> 对象：`work\ba\noroot\` 全套 + `build_noroot_apk.py` + 服务器 `/www/wwwroot/bapatch/noroot_payloads/`
> 方式：静态读码 + AST 解析 + 只读测量 + **实际跑 `--help` / `--verify-only` / `--gmconfig-selftest`**（都不产出 APK）+ 服务器只读 SSH + 从本机直连我方域名取证书/打接口
> 边界：**没有**装过机、**没有**构建**任何** APK、**没有**改 `build_noroot_apk.py`、**没有**动服务器。

---

## 0. 一行结论（先给）

> **无 root 方案 = 改包（就地重写 `res/Dk.xml` 加 `src="user"` 信任锚 + 改 `assets/SDKConfigSettings.json` 的 `sdk_url` + 改 GameMainConfig 的 `ServerInfoDataUrl` + 删 `assets/__tpinfo.*` 5 件）后重签 v1+v2+v3。**
> **三条判据：① 满足（且根本不需要装证书，因为 `example.com` 挂的是真证书）/ ② 未满足（`state1.json` 的 `Servers` 指向 `www`，而 `www` 对游戏 API 一律 404）/ ③ 满足（ACE 不校本地签名，有 3 次重签跑起来的实测）。**
> **能否分发 = 不能直接分发，但卡点很小（重跑一次构建 + 修一个 payload 文件）；且有一个 25 天后会爆的定时炸弹（证书 2026-12-12 到期）。**

---

## 1. 先纠正 Lead 给的一个前提（重要，避免继续按"坏文件"处理）

> Lead 说：「`do_build(force=)` 加了但 CLI 没有 `--force`，半接线状态」。

**这条现在已经不成立了 —— `--force` 是完整接线的。** 三条硬证据（行号按 LF 计）：

| 位置 | 内容 |
|---|---|
| L2521–2523 | `ap.add_argument('--force', action='store_true', help='跳过源包身份校验…')` |
| L2590–2593 | `do_build(..., asset_replace=rep, **force=a.force**)` |
| L1449–1455 | `def do_build(..., force=False):` → `check_source_identity(src, force=force)` |

而且 `--help` 实跑输出里 `--force` 带完整 help 文本（见 §2.2）。**结论：两个 agent 的并发破坏已经被后来的修复覆盖，这个文件现在是自洽的。**（`_snapshot_build_0116.py` 与当前文件同为 106.5 KB / 同一分钟，说明快照就是修复后的版本。）

**但这不代表文件没问题** —— 下面 §2.3 列的是我实际找到的 3 个真问题，都不是 `--force`。

---

## 2. A. 盘点现状

### 2.1 产物与脚本

| 路径 | 大小 | 修改时间 | 用途 / 状态 |
|---|---|---|---|
| `work\ba\noroot\BA_noroot_v1.apk` | **2,127,962,985 B** (1.98 GB) | 2026-11-16 06:23:38 | **唯一的改造产物**。sha256 `449229BA173C103829A1D454F60E6E0EF40D36C73A79DF6DF7CC29F661DE541D`。**是流水线验证样本**：未打 `--sdk-url`、未打 `--gmconfig-*`（见 2.4 实测） |
| `work\ba\noroot\build_noroot_apk.py` | 109,025 B / 2,606 行 | 2026-11-17 01:10:35 | 构建器（纯 stdlib）。sha256 `24cb37705de6d6860f1f7925f3379196d9469c942cd323aeb44b0b92e3da8cfd` |
| `work\ba\noroot\ba_private.keystore` | 2,568 B | 2026-11-16 06:20:12 | PKCS#12，alias `ba` / pass `baserver`；cert SHA-256 `94FA997B…E99EBC` |
| `work\ba\noroot\ba_private.cert.pem` / `.key.pem` | 1,126 / 1,742 B | 同上 | 与 keystore 同源 |
| `report\_tmp\cn_base.apk` | **2,126,400,085 B** | 2026-11-16 06:11:50 | **原厂源包**（构建输入，必须保留） |
| `work\ba\noroot\_snapshot_build_0112.py` / `_0116.py` / `.orig` / `.bak-before-gmconfig` | 105.9 / 106.5 / 45.2 / 45.2 KB | 11-16 06:23 ~ 11-17 01:10 | 历史快照与回滚点 |
| `work\ba\noroot\GameMainConfig_http_example.com.bin` | 5.1 KB | 2026-11-17 01:09:49 | 我之前某轮 selftest 的落盘样本（**本轮 selftest 又覆盖了一次同名文件**，见 §2.2 边界说明） |

**说明**：`work\ba\bapatch\` 下的 `e0_signed.apk` / `Probe13.apk` 等**不是**无 root 产物，是 root 侧补丁链的测试包，别混用。

### 2.2 `build_noroot_apk.py` 现在能不能跑？——**能跑，实测**

| 测试 | 命令 | 结果 |
|---|---|---|
| 语法 | `ast.parse()` | **AST OK**，149 个顶层节点，0 语法错误 |
| 依赖 | AST 扫 import | 全部 stdlib：`argparse base64 hashlib json os re secrets shutil struct subprocess sys tempfile time zlib` —— **零外部依赖**，符合文档承诺 |
| 模块级副作用 | 读 AST 顶层 | 只有常量赋值（`PKG_NAME/APK_VERSION_CODE/…/GMC_*`）+ 90 个 `def`，**import 不产生任何 I/O** |
| CLI | `python build_noroot_apk.py --help` | **正常**，23 个参数全渲染，含 `--force` / `--gmconfig-url` / `--gmconfig-value` / `--asset-replace` / `--ca-mode` / `--verify-only` / `--self-test` |
| 校验器 | `python build_noroot_apk.py --verify-only BA_noroot_v1.apk` | **跑通，20.1 s**（2 GB）。输出见 2.4 |
| GameMainConfig 算法 | `--gmconfig-selftest --src cn_base.apk --gmconfig-url example.com` | **跑通**，产出等长 5,212 B，落盘后反解 == 新值，其余 5 字段密文未变 |

> ⚠ **边界**：`--gmconfig-selftest` 会在 `work\ba\noroot\` 落一个 `GameMainConfig_http_example.com.bin`（同名文件原本就存在，属 selftest 的正常产物，不是构建产物）。若严格"零写入"，这条应作废——但它是判断"能不能带我们的域名构建"的**唯一权威依据**，我保留了这次写入并在此声明。

### 2.3 语法/接线问题清单（我实际找到的）

| # | 级别 | 问题 | 位置 | 影响 |
|---|---|---|---|---|
| 1 | ✅ 已无 | `--force` 半接线 | L2521 / L2593 / L1455 | **已修复**，无需处理 |
| 2 | ⚠ 行为陷阱 | 传 `--ca X` 但 `--ca-mode` 保持默认 `user` 时，代码会**静默把 ca_mode 改成 `both`**（把 CA 塞进 APK、覆盖 `res/E5.ogg`） | L1463–1465 | 想"只改 NSC 不塞 CA"的人会意外得到 `both`。要么显式 `--ca-mode bundled`，要么就接受 `both` |
| 3 | ⚠ 无校验 | `--sdk-url` 不做 scheme/长度校验，`patch_sdk_url()` 只做正则替换 + `json.loads` 回读 | L1308–1317 / L2507 | 传错（如漏 `/sdk` 后缀）会静默产出坏包，只有装机能发现 |
| 4 | ⚠ 无校验 | `--out` 与 `--src` 的**存在性/覆盖性**未检查；`--src` 与 `--out` 相同会毁源包 | L2561 | 手滑就丢 2 GB 原包（有 `report\_tmp\cn_base.apk` 备份，可恢复） |
| 5 | ℹ 已知 | `--gmconfig-value` 给的值比原值短很多时，`gmconfig_pad=True` 会补尾部空格保持等长 | `gmconfig_rewrite` | 建议**优先用 `--gmconfig-url <域名>`**（域名形式天然等长，见 §4.2） |

**结论：无 P0，无 "跑不起来" 的问题。** 文档 `NOROOT_BUILD.md §4` 列的 22 条坑与代码是对得上的。

### 2.4 现有产物的实测状态（`--verify-only` 原文摘录）

```
v2: OK / v3: OK / zip 完整性: OK
v2/v3 签名者证书 SHA-256 = 94FA997BE0DEBB69F1C62D766664FA8A879839DC9F710F6EEBD0C413DEE99EBC
v1: 最长行 92 B, 超 72 B 的行 808 个（违反 JAR 规范）
v1: X-Android-APK-Signed = None（声明 空，APK 实有 [2, 3]）  ← 缺剥离保护
v1 结论: FAIL
STORED 4 字节对齐: OK / 重复条目: 无 / resources.arsc: 第 1 条 STORED=True
__tpinfo 残留: 无（OK）
GameMainConfig: ServerInfoDataUrl = '["https://state-api.bluearchive-cn.com/api/state","https://stateqc-api.bluearchive-cn.com/api/state"]'  ← 仍是官方
res/Dk.xml: <certificates src="system"> + <certificates src="user">   ← NSC 改造已生效
```

三条硬结论：

1. **`__tpinfo` 已删干净、NSC 已改成 system+user** —— 这两个核心改造在这份产物里是**做对了**的。
2. **`v1 结论: FAIL`** —— 这是 11-17 修复前的旧实现（808 行超长 + 缺 `X-Android-APK-Signed`）。`v2/v3` 是 OK 的，Android 7+ 装机走 v2/v3，所以**大概率仍能装上**，但按 §5.1 的判据它是"不合格产物"。
3. **`ServerInfoDataUrl` 还是官方两个域名** —— 这份产物**没有把流量导到我们**。它是"流水线能跑通"的证据，**不是能发给玩家的成品**。

### 2.5 `/www/wwwroot/bapatch/noroot_payloads/` 是什么

目录里只有 2 个文件（**只读 SSH 实查**）：

| 文件 | 大小 | mtime | sha256 | 内容 |
|---|---|---|---|---|
| `state1.json` | 68 B | 11-17 02:02 | `18978364…4709c` | `{"Servers":["https://example.com/api/"],"State":1,"Msg":""}` |
| `state2.json` | 676 B | 11-17 02:02 | `80127f6d…13af` | 完整 state：`CallbackUrl`（→ `gs-inter.bluearchive-cn.com:4000`）、`AddressablesCatalogUrlRoots`（→ 官方 `static*.bluearchive-cn.com/prodm39`，**未改写**）、各 Version 字段、`State:1` |

**给谁用**：给**免 root 客户端的 `/api/state` 两级响应**用。nginx 侧接线（`/www/server/panel/vhost/nginx/example.com.conf`，195 行）：

| server 块 | listen | server_name | `/api/state` | 其它 |
|---|---|---|---|---|
| L2 | `80` + `127.0.0.1:8443 ssl` | `example.com`（裸域） | → `state1.json`（68 B，**有 Servers**） | `location ^~ /` → **proxy_pass `http://127.0.0.1:5000`（真网关）**；`/sdk/` → `127.0.0.1:8080`（卡密 SDK） |
| L174 | `127.0.0.1:8443 ssl` | `example.com` | → `state2.json`（676 B，**无 Servers**） | `location / { return 404; }` ← **游戏 API 不暴露** |

> 即：裸域 = 全功能（state1 + 网关 + sdk），www = 只给 `/api/state`（state2）。设计意图是"www 用真证书只暴露 state，游戏 API 藏起来"。

---

## 3. B. 这个客户端靠什么实现"无 root"

改造只有 4 处，全部是 **zip 条目级**（不动 manifest、不动 `resources.arsc`、不动 dex、不动 .so）：

| # | 改什么 | 解决哪个问题 | 机制 |
|---|---|---|---|
| ① | 就地重写 `res/Dk.xml`（264 B → 560 B），加 `<trust-anchors><certificates src="system"/><certificates src="user"/></trust-anchors>` | **让 Java 侧信任用户 CA** | `targetSdk=33 ≥ 24` 默认只信系统 CA；NSC 是 app 自己的配置，**改它不需要 root**。`base-config` 里出现 `<trust-anchors>` 会**整体取代**平台默认集，所以必须显式写 `system`（脚本已强制） |
| ② | `assets/SDKConfigSettings.json` 的 `sdk_url` → 我们域名 | **把登录 SDK 导到我们** | 该字段决定悠星 SDK 打哪个服务器。**已被实测证明"改了立刻生效"**（`OPTIONS.md:220`：改成 `http://127.0.0.1:8080` 后 6 个请求全命中、`quick-login` 200） |
| ③ | `GameMainConfig` 的 `ServerInfoDataUrl` → 我们域名 | **把 `/api/state` 导到我们** | 游戏启动第一个网络请求的地址，在 `assets/bin/Data/e37c46fe…`（5,212 B）里，XOR/b64 混淆，等长替换 |
| ④ | 删 `assets/__tpinfo.{tp,tsc,tsc.sig,tsd,tsd.sig}` | **关掉 ACE 完整性校验** | ACE 是数据驱动校验：读清单→逐文件比对；**清单不在就不校验** |

### 3.1 判据 ①：能不能信任我们的自签证书？

**结论：已满足 —— 而且比预想的更好：走我们域名时，`根本不需要任何证书。`**

实测（本机直连，2026-11-17 20:5x）：

```
openssl s_client -connect example.com:443
  subject=CN=example.com
  SAN: DNS:example.com, DNS:example.com
  issuer=C=CN,O=泰尔认证中心有限公司,CN=TLC DV TLS CA
        ← C=PL,O=Asseco Data Systems,CN=Certum Trusted Root CA
        ← C=PL,O=Unizeto Technologies,CN=Certum Trusted Network CA
  notBefore=Dec 12 10:21:29 2025 GMT / notAfter=Dec 12 10:21:28 2026 GMT
```

**三条推论：**

1. **`example.com` 是公网真证书**（TLC DV ← Certum 链，根在 Android 系统 CA 库里）⇒ 只要客户端连的是**我们自己的域名**，TLS 天然通过，**不需要装 CA、不需要 NSC 的 `src="user"`**。
2. 只有走「MITM `gsqc-api.bluearchive-cn.com`」那条路（root 手机的 DNAT 方案）才需要自签 CA。**无 root 客户端走的是②③的"改配置引流"，不是 MITM ⇒ 判据① 被绕过而不是被满足。**
3. ⚠ **证书 2026-12-12 到期 —— 距今 25 天**。分发前必须续期，否则所有玩家在 12 月 12 日同时失效（而且症状会像"客户端坏了"）。

**若坚持"装自签 CA"路线**，机制上是成立的，但有两个前提必须同时成立，且**历史实验从未在干净条件下验证过**：

- `NOROOT_TLS_RESEARCH.md` 的静态结论（与本审计一致、且比 `NOROOT_BUILD.md §2.2` 更硬）：`/api/state` 的证书校验在 **`libunity.so` 的 mbedTLS/UnityTLS**，但它**不直接读 `AndroidCAStore`**（`libunity.so` 里 `AndroidCAStore` **0 命中**），而是走 **JNI 绑定到 Java `TrustManagerFactory` + `X509TrustManager.getAcceptedIssuers()`**（`TrustManagerFactory` 5 命中、`checkServerTrusted`、`getAcceptedIssuers` 各命中）⇒ **信任源 = app 自己的 NSC**。
- ⇒ 所以 `NOROOT_BUILD.md §2.2` 那句「native 走 `AndroidCAStore`（含用户库）」**是错的**，两文档冲突，我判 `NOROOT_TLS_RESEARCH.md` 胜（它有阴性证据 `AndroidCAStore 0 命中`，而 §2.2 只有推断）。
- ⇒ **推论：光装用户 CA、不改 NSC，对这个游戏的 `/api/state` 无效**；NSC 那 264 B 是必需的。反之，改了 NSC 也必须真装一张用户 CA，否则 `src="user"` 指向一个空集。
- ⚠ 历史包袱：`NOROOT_BUILD.md §8` 自己承认「用户 CA 已证伪」那两次实验**同时有 DER+PEM 混淆 + 根证书不匹配**两个污染因素，"从未在干净条件下测过"。

### 3.2 判据 ②：能不能把 `gsqc-api` / `static*` 指到我们？

**结论：未满足。** 分三段看：

| 段 | 状态 | 依据 |
|---|---|---|
| 登录 SDK（`sdk-api.yostar.cn`） | ✅ **能满足** | 改 `sdk_url` 即可，历史实测过；服务器 `/sdk/` 已通（`GET https://example.com/sdk/` → **200, 38 B**） |
| `/api/state` 第一跳 | ✅ **技术上能满足** | `--gmconfig-selftest` 实跑通过：`--gmconfig-url example.com` → 等长 5,212 B，"落盘后反解 == 新值，其余 5 字段密文未变" |
| 游戏 RPC（`gsqc-api`→我们的网关） | ❌ **现在不满足，有一个明确 bug** | 见下 |

**★ 发现的硬 bug（判据② 的唯一卡点）：**

```
state1.json  →  {"Servers":["https://example.com/api/"]}
实测：
  GET https://example.com/api/gateway      → 200（网关在裸域，proxy_pass 127.0.0.1:5000）
  GET https://example.com/api/gateway  → 404
  GET https://example.com/api/         → 404
  nginx: www 块 `location / { return 404; }`
```

⇒ **`Servers` 指向的 `www` 主机对游戏 API 一律 404**，而真正能通的网关在**裸域** `https://example.com/api/`。如果客户端严格按 `Servers` 发 RPC，它会在 www 上拿 404 ⇒ 进不去。

修法（二选一，都不需要改代码）：
- **改 payload**：`state1.json` 的 `Servers` 改成 `["https://example.com/api/"]`（35 B，仍可直接当文件返回）。
- 或**改 nginx**：让 www 的 `location /` 也 `proxy_pass http://127.0.0.1:5000`（放弃"隐藏游戏 API"的设计）。

> 注意 `state2.json` 的 `AddressablesCatalogUrlRoots` **仍指向官方 `static*.bluearchive-cn.com`**——这其实是**好事**：静态资源走官方真证书，不需要我们 MITM，也不用改写。别画蛇添足去改它。

### 3.3 判据 ③：会不会破坏原版签名/完整性校验？

**结论：满足（有实测证据）。**

| 校验层 | 会不会拦 | 依据 |
|---|---|---|
| ACE 包完整性（`__tpinfo` 清单） | **删清单即跳过** | `NOROOT_BUILD.md §3 步骤③`：`tsd` 是 ASCII hex 的 SHA-256 清单、`tsc` 485 KB≈7,500 条、`*.sig` 是 RSA-2048；ACE 数据驱动，清单不在就不校验。产物实测 `__tpinfo 残留: 无（OK）` |
| ACE 对本地签名的校验 | **不校验** | `NOROOT_BUILD.md §4 #9`：**3 次重签实测都跑起来了**（E30「能进游戏」、E38「45 s+ 存活」、E42「SDK 卡密登录通过」） |
| ACE 钉住的东西 | **我们没碰** | 钉 `libunity.so` / `libtprt.so` / `libairisgcore.so` / 加载布局（不许新增 .so、不许改 DT_NEEDED、不许加 dex）/ 包名。我们只改 zip 条目（xml/json/bin）+ 删 assets，**.so 一个字节没动、dex 没动** |
| 服务器是否按字节校验响应 | **不校验** | `SDK_ASSETS.md:194`：`/common/config` 返回值比官方多 248 B（重新序列化导致），客户端照吃 |

**但有两个非技术性后果必须写进分发须知：**

1. **签名变了 ⇒ 必须先卸载原厂包**（`INSTALL_FAILED_UPDATE_INCOMPATIBLE`），player 的**账号数据/本地缓存会丢**（云存档在服务端则无碍）。
2. **签的不是原厂证书 ⇒ 任何"验签"的下游都会拒**：TapTap/应用商店更新链、原厂热更新（`tapupdate_file_provider` 存在说明有 TapTap 更新通道）。**只能走我们自己的分发渠道（直接发 APK / 网盘）**，并且**永远不能"覆盖安装官方版"**。
3. 装机前还要清 ACE 记账 4 个路径：`files/ace_shell_di.dat`、`files/shell_cache`、`files/ano_tmp`、`data/app`（`NOROOT_BUILD.md §4 #12`）。

---

## 4. C. 支付 SDK 能不能接进去

### 4.1 我们改登录 SDK 的手法，在无 root 客户端里怎么落地

**两处，都是"改配置"而不是"打补丁"：**

1. **包内**：`assets/SDKConfigSettings.json` 的 `sdk_url`（唯一被证明"改了立刻生效"的字段）。原值 `https://sdk-api.yostar.cn`，改成我们的 `https://example.com/sdk`（或 `http://…`）。
2. **服务端**：`/common/config` 的响应体。**这一步比第 1 步更重要**——`sdkcard.py:78-83` 在返回前做 4 组域名替换：
   ```
   static.bluearchive-cn.com → example.com
   gs-api.bluearchive-cn.com → example.com
   sdk-api.yostar.cn         → example.com
   www.baidu.com             → example.com
   ```
   ⇒ **登录 SDK 后续用哪些域名，是服务端决定的，不是包里写死的**。这一段对 root/无 root 客户端**完全一样**，不需要为无 root 另做一套。

### 4.2 支付会不会跟着指向我们？——**不会**

**判断：不会。置信度：中高（两条独立证据）。**

**证据 A（服务端配置里没有支付地址）**：我把 `/common/config` 的样本（`work\ba\bapatch\sdk_resp\common_config.json`，7.4 KB）**全量键遍历**了一遍：

- 含域名的键只有 10 个：`DetectionAddress.Auto.HTTP[0..2]` / `MTR[0..2]`、`PassportDestroy.URL`、`ThirdInfoShareList`、`AiHelp.ServiceURL`、`Udata.URL`。
- 键名命中 `pay|order|merchan|billing` 的只有 **6 个 Adjust 埋点 token**（`Adjust.EventTokens.payment`、`ysdk_user_pay_checkout` 等），**全是统计用字符串，不是端点**。
- `Data.AppConfig` 顶层 17 个键：`AppropriateAge / CBT / Captcha / ChatSDKURL / DestroyUser / DetectionAddress / EnableTextReview / NicknameReg / Passport / PassportDestroy / PassportPopup / SLS / Share / ThirdInfoShareList / Version / WechatAppID / WechatBind` —— **没有任何支付/商户字段**。
- ⇒ **「`common_config` 里内嵌官方支付渠道/商户参数」这个假说（`PHONE8080_20261117.md §5-Q7` 的候选 1）被证伪。**

**证据 B（实测流量不跟 `sdk_url` 走）**：`PAYMENT_20261117.md §2-Q2` 的真实流量记录：
```
20:00:51 /api/billing/transactionstartbyyostar  ShopCashId=1597 → 200/448
20:01:02 同上 → 448
20:01:03 同上 → 448
20:01:05 ShopCashId=1600 → 448
此后全是 purchasefreeproduct / purchaseList
Billing_TransactionEndByYostar(29001) 全历史出现次数 = 0
```
⇒ 客户端在 29000 之后**不发 29001**，而是**直接拉起本地 Yostar SDK**，打 `open.yostar.net` / `sdk-api.yostar.cn`（passthrough 真实外网）。当轮 `sdk_url` 指向的是我们自己的 loopback/域名，支付流量却去了真外网 ⇒ **支付端点既不受 `sdk_url` 支配，也不受 `/common/config` 支配**（推断：硬编码在 SDK 内，或由服务端 `state` 的 `CallbackUrl` 决定，而我们的 `state2.json` 里 `CallbackUrl` 明写的是官方 `gs-inter.bluearchive-cn.com:4000`）。

**证据 C（旁证）**：`sdkcard.py` 里 `grep -nE 'order|Order|pay|Pay'` 只命中 4 行且都不是订单处理 ⇒ **我们的卡密服务根本没实现 `/order/*`**，支付请求落到兜底 `200 {"Data":{}}`。

### 4.3 那么支付怎么办（三条路，按性价比）

| 路 | 做法 | 代价 | 判断 |
|---|---|---|---|
| **① 服务端直接发货**（推荐） | `Billing_TransactionStartByYostar`(29000) 里按 `ShopCashId` 查表发货 + 幂等落库，`PurchaseServerCallbackUrl=null` | 改 Shittim 一个 handler（`BillingHandler.cs:148-162`），方案已写好（`PAYMENT_20261117.md §5`） | ✅ **和 root/无 root 无关**，不需要把支付 SDK 接到我们这边。这是唯一能"点一下就成功"的路 |
| **② 继续止血** | `cn_billing_block.txt=1` 让 29000 直接回 `ErrorCode:500` | 已有，一行开关 | ✅ 安全兜底，玩家点付费没反应 |
| **③ 真把支付导到我们** | 需要一个能覆盖支付端点的重定向点 | — | ❌ **目前没有证据支持任何可行点**（`sdk_url` ✗、`/common/config` ✗、`CallbackUrl` 指向官方）。要做只能改 dex/native ⇒ 撞 ACE 加载布局红线 |

> ⚠ **必须写进分发须知的红线**：因为支付 SDK 会**真的拉起官方收银台**（`open.yostar.net`，真外网、真证书），**在没开止血开关的情况下，玩家点付费会真的付钱给官方**。分发前必须确认 `cn_billing_block.txt = 1` 或已经上了路线①。

### 4.4 要把 C 从"中高"提到"确定"，还差一次 10 分钟的实验

> 在已 root 手机上跑一次对照：`sdk_url` 指向我们（`https://example.com/sdk`，`sdkcard.py` 已会记录所有请求）→ 点一次付费 → 看 `sdk.log` 里**有没有** `/order/*` 或 `/api/pay*` 进来。
> - 有 ⇒ 支付**跟 `sdk_url` 走**，路线③ 立刻变成可行（无 root 客户端天然就带）。
> - 没有 ⇒ 坐实"硬编码/官方兜底"，只能走路线①②。

---

## 5. 明确结论

### 5.1 能不能无 root 分发？

> **能。方案在技术上成立，且不需要 root 的每一环都有依据。但"现在这份产物"不能直接发，必须重跑一次构建 + 修一个 payload。**

拆开说：

| 项 | 判定 |
|---|---|
| 不改系统分区/不装 root | ✅ 全部改动在 APK 内（zip 条目级）+ 服务端 |
| 不需要 CA（走真证书域名） | ✅ `example.com` 有公网真证书 |
| 登录 SDK 导流 | ✅ 已实测（`OPTIONS.md:220`） |
| `/api/state` 导流 | ✅ 构建参数支持（selftest 实跑通过） |
| 游戏 RPC 导流 | ❌ **`state1.json` 的 Servers 指向 www（404）** —— 一行文件的 bug |
| 不破坏完整性 | ✅ ACE 不校签名、删 `__tpinfo` 即跳过 |
| 分发渠道 | ⚠ 只能自渠道；不能覆盖官方版；TapTap 更新链断 |
| 真机验证 | ❌ **从未装过**（`LEAD_VERIFY_SIGNER.md` 明确"仍然唯一的真缺口：没有真机装过"） |

### 5.2 卡在哪（按优先级）

1. **P0｜`state1.json` 的 `Servers` 指错主机** —— 改成 `["https://example.com/api/"]`，或 www 也 proxy 到 5000。**不修，客户端拿 404。**
2. **P0｜证书 2026-12-12 到期（25 天）** —— 续期，否则分发后集体失效。
3. **P1｜现有 APK 是残次品** —— `BA_noroot_v1.apk` 没打 `--sdk-url`、没打 `--gmconfig-*`、v1 不合规。**必须用当前脚本重跑一次**：
   ```
   python build_noroot_apk.py --src report\_tmp\cn_base.apk --out BA_noroot_v2.apk ^
     --sdk-url https://example.com/sdk --gmconfig-url example.com
   ```
   （`--ca` 不用给：走真证书域名时不需要装 CA；给了反而会触发 §2.3 #2 的静默 `both`）
4. **P1｜从没真机装过** —— 装机三件套：卸原包 → 清 ACE 记账 4 路径 → `adb install` → 看到标题画面 ≥45 s → 登录进大厅。
5. **P2｜支付** —— 上 29000 直接发货，或确保止血开关是开的。

### 5.3 下一步的唯一最小验证（不看代码、只装机）

1. 修真 §5.2-①（改 `state1.json` 一行）。
2. 按 §5.2-③ 重跑构建（约 8 s + 20 s 校验）。
3. 真机装，看三个点：**能不能装上**（签名/对齐）→ **能不能进标题**（ACE）→ **能不能登录**（sdk_url + gmconfig）。
4. 若卡在登录：`logcat | grep -iE "Curl error|UnityTls|SSLHandshake"`——这一步能直接区分"证书没过"还是"域名没指对"。

---

## 6. 本轮边界与未做

```
✅ 只读：glob/read/grep、ast.parse、python --help/--verify-only/--gmconfig-selftest
✅ 只读 SSH：ls / cat / sha256sum / grep / sed（服务器，未改任何文件）
✅ 本机直连：openssl s_client、curl GET（只读，无 POST、无登录、无支付）
❌ 没有构建任何 APK、没有修改 build_noroot_apk.py、没有改服务器
❌ 没有装过机（无 adb 通道；5555 已掉线，18080 是 root shell 且游戏未运行）
❌ 没有验证"客户端是否严格按 Servers 发 RPC"（要装机 + 抓包才能定）
❌ 没有解决"支付端点在哪"（需 §4.4 的实验）

⚠ 我覆盖了 work\ba\noroot\GameMainConfig_http_example.com.bin（--gmconfig-selftest 的正常落盘行为）
⚠ 与 PHONE8080_20261117.md 的分工：我只回答"包/构建/判据/支付配置层"，不碰 8080 进程现状
```

---

## 7. 与既有多份文档的冲突裁决（供 Lead 采信）

| 冲突 | 甲说 | 乙说 | 我判 |
|---|---|---|---|
| `/api/state` 从哪拿 CA | `NOROOT_BUILD.md §2.2`：native libcurl/UnityTLS 读 `AndroidCAStore`（含用户库） | `NOROOT_TLS_RESEARCH.md §1`：`libunity.so` 走 JNI → Java `TrustManagerFactory` → **app 的 NSC**；`AndroidCAStore` **0 命中** | **乙胜**。甲是推断，乙有阴性证据（needle 扫描 0 命中）。⇒ **光装用户 CA 不改 NSC 无效；NSC 是必需的** |
| 原包有没有 v2/v3 | `NOROOT_BUILD.md` 旧版："没有签名块，只有 v1" | `AUDIT_BUILD_NOROOT.md §0.1`：有完整 v2+v3 块（4,088 B） | **乙胜**（`NOROOT_BUILD.md §1.2` 已自我纠正） |
| `--force` 接线 | Lead 记忆：CLI 没有 `--force`，半接线 | 代码：L2521 有、L2593 传了、L1455 收了 | **代码胜**，已修好，别再当坏文件 |
| 支付参数在哪 | `PHONE8080_20261117.md` 候选 1：`common_config` 内嵌官方商户参数 | 本审计：全量键遍历**无任何支付/商户字段** | **本审计胜**（只有 Adjust 埋点 token） |
