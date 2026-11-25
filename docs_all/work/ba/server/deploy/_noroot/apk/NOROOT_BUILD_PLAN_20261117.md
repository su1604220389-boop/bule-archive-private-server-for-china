# 无 root 客户端 · 构建与发布计划（NOROOT_BUILD_PLAN_20261117）

> 负责人：ca-researcher（独占 `build_noroot_apk.py` + `_noroot\apk\`）
> 时间：2026-11-17 20:14–20:40 (+08:00)
> 状态：**① 已完成（v2 已产出，全绿）｜② 方案已定，待 srv-ops 执行｜③ 方案已出，待 Lead 点头｜④ 方案已出，待 phone-ops 执行**
> 红线遵守：未碰 `_noroot\phone\` / `_card\` / `_blackout\*` / `_multiplayer\` / 任何 nginx 配置 / `ba_sni.conf`。
> **本轮没有修改 `build_noroot_apk.py` 一个字节**（原因见 §2.1）。

---

## 0. 一行结论

> **构建参数已定 = `--sdk-url https://example.com/sdk` + `--gmconfig-**value** '["https://example.com/api/state"]'`（**不是** Lead 给的 `--gmconfig-url example.com`，那个会生成 NXDOMAIN 子域）；v2 已构建完成、`--verify-only` 独立复验 exit 0、v1/v2/v3 全绿。**
> **state1 修法 = 改成裸域 `["https://example.com/api/"]`（64 B），作为构建产物落到 `_noroot\apk\payloads\state1.json`，由 srv-ops 一行覆盖上线；不改脚本、不加参数。**
> **证书续期 = 同 SAN 集（`example.com` + `www`）从公网 CA 重签，替换 `fullchain.pem`/`privkey.pem` 后 `nginx -s reload`；域名不变、无 pinning、APK 内零证书材料 ⇒ 客户端不用重打包。硬截止 2026-11-28。**

---

## 1. ① 重跑构建 —— 已完成

### 1.1 参数（与 Lead 指令的差异，必须先看）

| 参数 | Lead 给的值 | **我实际用的值** | 为什么改 |
|---|---|---|---|
| `--sdk-url` | `https://example.com/sdk` | **同**（一致） | — |
| `--gmconfig-*` | `--gmconfig-url example.com` | **`--gmconfig-value '["https://example.com/api/state"]'`** | ⚠ **`--gmconfig-url example.com` 会把值展开成 `["http://state-api.example.com/api/state","http://stateqc-api.example.com/api/state"]`，而这两个子域实测 NXDOMAIN**（见 1.2）。照 Lead 的原值构建，客户端第一跳 DNS 就挂 |
| `--ca` | 不给 | **不给**（一致） | 走真证书域名，不需要自签 CA；给了会触发脚本的静默 `ca_mode→both`，覆盖 `res/E5.ogg` 扫码音 |

### 1.2 为什么必须换掉 `--gmconfig-url <裸域名>`

`gmconfig_value_from_spec()`（L1146–1171）的逻辑：**纯域名**会被 `GMC_TMPL_PAIR` 展开成 `state-api.<d>` + `stateqc-api.<d>` 两条。

实测这两条域名**没有解析**：

```
example.com              -> <SERVER_IP>
example.com          -> <SERVER_IP>
state-api.example.com    -> NXDOMAIN
stateqc-api.example.com  -> NXDOMAIN
```

⇒ 若按原参数构建，`ServerInfoDataUrl` 会指向两个**不存在的主机**，客户端连解析都过不了。

**改用整串 URL**：`gmconfig_value_from_spec()` 走"其它 URL"分支（L1171），原样产出一条 `["https://example.com/api/state"]`：
- 主机 `example.com` 有 A 记录 ✅
- 该主机有真证书、SAN 覆盖 ✅
- `/api/state` 在该主机上确有响应（`GET → 200, 68 B`）✅

### 1.3 实际执行命令（可复现）

```powershell
cd work\ba\noroot
python build_noroot_apk.py `
  --src  C:\Users\su\Desktop\大肥鱼项目\BAServer\report\_tmp\cn_base.apk `
  --out  C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\server\deploy\_noroot\apk\BA_noroot_v2.apk `
  --sdk-url https://example.com/sdk `
  --gmconfig-value '["https://example.com/api/state"]'
```
> ⚠ **必须在 `work\ba\noroot\` 下运行**（`--keystore` 默认是相对路径 `ba_private.keystore`）。

耗时 **47.6 s**（含构建 26.4 s + 自检 + 全量校验）。

### 1.4 产物

| 项 | 值 |
|---|---|
| 路径 | `work\ba\server\deploy\_noroot\apk\BA_noroot_v2.apk` |
| 大小 | **2,127,971,177 B**（1.98 GB；源包 2,126,400,085 B，净 +1,571,092 B = 新 v1 清单 + 签名块） |
| sha256 | **`682A9EA20DD9C9EC955454ACD937E2A8C002F13EC7B6B1307112B3C61D4EA2EC`** |
| mtime | 2026-11-17 20:23:26 |
| 签名证书 SHA-256 | `94FA997BE0DEBB69F1C62D766664FA8A879839DC9F710F6EEBD0C413DEE99EBC` |
| 条目数 | 41,307（41,312 − 5 `__tpinfo` − 3 旧 v1 + 3 新 v1） |

### 1.5 校验结果（构建内自检 + 独立二次复验，全部 exit 0）

```
v2: OK   v3: OK   zip 完整性: OK
v1: 最长行 70 B, 超 72 B 的行 0 个（OK）          ← 旧产物是 808 行 / 92 B
v1: 逐条摘要 41304 条, 不符 0, 条目缺失 0 OK
v1: X-Android-APK-Signed = '2, 3'（声明 [2,3]，实有 [2,3]）  ← 旧产物是 None
v1: META-INF/CERT.RSA 对 .SF 的 PKCS#7 验签 OK
v1 结论: OK                                        ← 旧产物是 FAIL
STORED 4 字节对齐: OK / 重复条目: 无 / resources.arsc: 第 1 条 STORED=True
__tpinfo 残留: 无（OK）
GameMainConfig: ServerInfoDataUrl == 期望值: OK
res/Dk.xml: <certificates src="system"> + <certificates src="user">  ✅
```

包内三件关键条目实测：

| 条目 | 大小 | 方法 | 说明 |
|---|---|---|---|
| `res/Dk.xml` | **560 B** | STORED | 264 → 560，NSC 改造生效 |
| `assets/SDKConfigSettings.json` | 2,843 B | STORED | 2,840 → 2,843；`sdk_url = https://example.com/sdk` ✅ |
| `res/E5.ogg` | **6,401 B** | STORED | **与原厂一致 ⇒ `--ca` 确实没生效、扫码音没被换** ✅ |

### 1.6 回滚（一行）

```powershell
Remove-Item work\ba\server\deploy\_noroot\apk\BA_noroot_v2.apk
```
> 权威回滚点是原厂包 `report\_tmp\cn_base.apk`（2,126,400,085 B，sha256 `DD30A285B58508252DF09A503B025850A27A73C89F1162454BEE55A60D7F83BB`）。构建脚本零改动，重跑即可复现。

---

## 2. ② `state1.json` 的一行 bug —— 方案已定

### 2.1 决策：**改 payload 源文件 + 纳入产物目录，不改脚本、不加 `--servers-url` 参数**

理由（写给 Lead 看的取舍）：

| 方案 | 优点 | 缺点 | 结论 |
|---|---|---|---|
| **A. 改 payload 源文件（选中）** | 零风险；`state1.json` 只有 64 B，本质是**数据不是逻辑**；改动面完全隔离在我自己的目录；srv-ops 一行 `cp` 即可上线 | 需要一次人工部署 | ✅ **选它** |
| B. 给脚本加 `--servers-url` | 一条命令同时产出 APK + payload | 要动 2,606 行脚本；这文件**刚被两个 agent 并发改坏过一次**；为 64 B 数据引入构建器回归风险，性价比不成立 | ❌ |

**补充**：真正需要"一致性保证"的地方，我用**校验脚本**解决（§2.4），而不是把 payload 生成塞进构建器——这样构建器的行为与本轮之前**逐字节等价**，`--self-test` / `--verify-only` 的既有结论继续有效。

### 2.2 问题（原文）

```
线上 state1.json（68 B, sha256 18978364c260b254037cdedf7e2f4f2ae28d8dd06b39352e4e48a6ef34f4709c）：
{"Servers":["https://example.com/api/"],"State":1,"Msg":""}

实测（2026-11-17 20:5x）：
  GET https://example.com/api/gateway      → 200   ← 真网关（nginx `location ^~ /` → 127.0.0.1:5000）
  GET https://example.com/api/gateway  → 404   ← nginx www 块 `location / { return 404; }`
  GET https://example.com/api/         → 404
```

⇒ `Servers` 把客户端指向一个**只服务 `/api/state`、其它一律 404** 的主机。客户端拿 404 就进不去。

### 2.3 修正后（已落盘）

```
work\ba\server\deploy\_noroot\apk\payloads\state1.json   64 B  无尾换行  UTF-8 无 BOM
sha256 = 2A150B40CC1DDE80BF5929D60DFF5367A8F2BEDC96709B213A29E71D21A582BD

{"Servers":["https://example.com/api/"],"State":1,"Msg":""}
```

与 APK 侧的闭环（一个域名、一张真证书、零 CA）：

```
APK: ServerInfoDataUrl = ["https://example.com/api/state"]      ← 我构建进 v2 的值
  → https://example.com/api/state    → nginx 裸域块 → state1.json
  → Servers = ["https://example.com/api/"]                      ← 修正后的 payload
  → https://example.com/api/gateway  → 127.0.0.1:5000（Shittim） ✅
  → SDK: https://example.com/sdk/*   → 127.0.0.1:8080（卡密）    ✅
```

### 2.4 部署（交 srv-ops，一行 + 一行验证）

```bash
# 上线（需先把这个 64 B 文件传到服务器，例如 /tmp/state1.json）
install -m 644 -o root -g root /tmp/state1.json /www/wwwroot/bapatch/noroot_payloads/state1.json

# 验证（应看到 64 B / Servers 指向裸域）
curl -s https://example.com/api/state | tee /dev/stderr | sha256sum
# 期望 sha256 = 2a150b40cc1dde80bf5929d60dff5367a8f2bedc96709b213a29e71d21a582bd
curl -s -o /dev/null -w '%{http_code}\n' https://example.com/api/gateway   # 期望 200
```

> **不需要改 nginx、不需要 reload** —— 只是替换 `root` 目录下的静态文件（`root /www/wwwroot/bapatch/noroot_payloads;` 指向它）。
> 回滚一行：`printf '%s' '{"Servers":["https://example.com/api/"],"State":1,"Msg":""}' > /www/wwwroot/bapatch/noroot_payloads/state1.json`

**`state2.json` 不动**（676 B，只在 www 上被访问；其 `AddressablesCatalogUrlRoots` 指向官方 CDN，正好免掉静态资源的 MITM）。

### 2.5 残余不确定性（真机才能定）

- 客户端是否**严格**按 `Servers[0]` 发 RPC（会不会自己拼 `state-api.` 前缀 / 做主机名白名单）——**未知，需真机抓包**。
- 只给**一条** `Servers` 是否够（原厂是 1 条 `gsqc-api`，所以大概率够）。

---

## 3. ③ 证书续期 —— 方案（**不执行**，等 Lead 点头）

### 3.1 现状（实测）

| 项 | 值 |
|---|---|
| subject | `CN=example.com` |
| SAN | `DNS:example.com, DNS:example.com`（**只有这两个**） |
| 签发者 | `C=CN, O=泰尔认证中心有限公司, CN=TLC DV TLS CA` |
| 链 | `TLC DV TLS CA` ← `Certum Trusted Root CA` ← `Certum Trusted Network CA`（服务器发 3 张，含交叉签，兼容性最好） |
| 有效期 | **notBefore 2025-12-12 10:21:29Z ／ notAfter 2026-12-12 10:21:28Z**（365 天 DV） |
| 文件 | `<CERT_PATH>`(6,887 B) + `privkey.pem`(1,703 B)，mtime 2025-11-13 13:30 |
| 自动续期 | 宝塔有 ACME 续期 cron：`python3 /www/server/panel/class/acme_v2.py --renew_v2=1`，但**当前证书是 TLC（第三方 DV），不是 ACME 签的** ⇒ **不能指望这条 cron 自动续上**，必须人工确认 |

### 3.2 要做什么（三选一，推荐 A）

| 方案 | 做法 | 优点 | 风险 |
|---|---|---|---|
| **A. 同 CA 续签（推荐）** | 在泰尔/Certum 渠道对同一 SAN 集续费重签，拿新的 `fullchain.pem`+`privkey.pem` | 链不变、兼容性已验证过 | 要人工下单/续费 |
| B. 换 Let's Encrypt（ACME） | 用宝塔面板给该站点申请 LE 证书，SAN 同上 | 免费、可自动续期、根 `ISRG Root X1` 在所有现代 Android 系统库里 | 换 CA ⇒ 链变；部分老设备/老 ROM 需确认；**仍需验证** |
| C. 自签 | ❌ | — | **绝对不行**：无 root 客户端拿不到这张 CA，会全线失败 |

> **关键结论**：因为客户端**没有 pinning、也没有内嵌 CA**（§3.4 证据），所以 **A 和 B 对客户端都是透明的**——换哪家公网 CA 都能过。

### 3.3 换证书后 nginx 要改哪、要不要重启

| 步骤 | 命令/动作 | 说明 |
|---|---|---|
| 1 | 备份旧证：`cp -a <CERT_PATH> /root/cert_bak_$(date +%s)` | 必须 |
| 2 | 覆盖 `fullchain.pem` / `privkey.pem`（**文件名不变**） | 文件名不变 ⇒ **不需要改任何 nginx 配置** |
| 3 | `nginx -t` | 语法自检，必须 `syntax is ok` |
| 4 | **`nginx -s reload`**（不是 restart） | reload 不断连接；restart 会瞬断所有在线玩家 |
| 5 | 验证：`openssl s_client -connect example.com:443 -servername example.com </dev/null 2>/dev/null \| openssl x509 -noout -dates -ext subjectAltName` | 确认 notAfter 已延后、SAN 仍是两个 |

⚠ **这是红线**：第 2–4 步碰 nginx，属 Lead 点头范围。我只出清单，不执行。
⚠ 若走方案 B（LE），宝塔会**自动改** `ssl_certificate` 指向新路径（可能变成 `<CERT_PATH>` 同一个位置，也可能新建目录）——**换完必须回读 nginx 配置确认路径**，否则 reload 会失败。

### 3.4 无 root 客户端要不要重新打包？——**不用**（三条证据）

1. **APK 内零证书材料**：本版构建**没有传 `--ca`**，实测 `res/E5.ogg` = **6,401 B**（与原厂一致）⇒ 没有任何 CA 被塞进包里。
2. **NSC 里没有 pin、没有资源引用**：`res/Dk.xml` 只有 `<certificates src="system"/>` 与 `src="user"/>` 两个**关键字**，没有 `<pin-set>`、没有 `src="@0x7f0e0000"` ⇒ 不绑定任何具体证书。
3. **域名不变**：本次只换叶子证书，`example.com` / `www` 都不变；`ServerInfoDataUrl`、`sdk_url`、`Servers` 全部不变 ⇒ APK 里没有任何东西需要跟着改。

> ⇒ **证书续期 = 纯服务端动作，v2 包继续用，不需要 v3 重打包。**
> ⚠ 反过来：**如果哪天为了"零配置信任自签 CA"而用 `--ca` 构建，这条就不成立了**——证书一换就得重打包。这也是我坚持不用 `--ca` 的第二个理由。

### 3.5 时间线（建议）

| 日期 | 动作 | 负责 |
|---|---|---|
| **2026-11-24** | 确认续期渠道（A 还是 B）、准备好新证书 | Lead 决策 |
| **2026-11-28** | **硬截止**：新证书已上线并验证 `notAfter` 已延后 | srv-ops 执行 + 我复核 |
| 2026-12-01 | 真机回归一次（确保换证后客户端仍能登录） | phone-ops |
| 2026-12-12 | 旧证到期（**若前面都做了，此日无事发生**） | — |

> 建议在 11-28 前完成，留 14 天缓冲；`notAfter` 到期后症状是"所有玩家同时连不上"，且**看起来像客户端坏了**，排查成本极高。

---

## 4. ④ 真机安装测试方案 —— 交 phone-ops 执行

> 我只出清单并配合；执行与判定由 phone-ops 做。**前置条件没满足就别开测**（见 4.1）。

### 4.1 开测前置（缺一不可）

| # | 条件 | 当前状态 |
|---|---|---|
| P1 | `state1.json` 已按 §2.4 上线（裸域） | ❌ **未上线**（线上仍是 www 的旧版） |
| P2 | 服务器 `:5000` 网关 + `:8080` 卡密 在跑 | 需 srv-ops 确认 |
| P3 | 手机有可用通道（adb 或 18080 root shell） | ⚠ phone-ops 报 5555 已掉线、18080 可用 |
| P4 | 手机上没有正在运行的旧包（避免 ACE 记账污染） | 需确认 `pidof com.RoamingStar.BlueArchive` 为空 |

> **P1 不做就测，必然失败**，且会被误判成"包有问题"。

### 4.2 装之前必须备份/记录

```bash
# ① 记录当前已装版本（回滚要用）
adb shell dumpsys package com.RoamingStar.BlueArchive | grep -E "versionCode|versionName|firstInstallTime|lastUpdateTime" > ver_before.txt

# ② 备份 ACE 记账 4 路径（装新包前要清，先备份才能回滚）
adb shell "su -c 'cd /data/data/com.RoamingStar.BlueArchive 2>/dev/null; tar czf /sdcard/ba_ace_bak.tgz files/ace_shell_di.dat files/shell_cache files/ano_tmp 2>/dev/null'"

# ③ 备份 Hosts 与配置（若存在）
adb shell "su -c 'cp -a /sdcard/Android/data/com.RoamingStar.BlueArchive/files/Hosts /sdcard/Hosts.bak 2>/dev/null'"

# ④ 记录产物身份（写进测试记录，否则无法判断"这次崩的是哪一版"）
sha256sum BA_noroot_v2.apk          # 期望 682a9ea20dd9c9ec955454acd937e2a8c002f13ec7b6b1307112b3c61d4ea2ec

# ⑤ 服务端基线
sha256sum /www/wwwroot/bapatch/noroot_payloads/state1.json   # 期望 2a150b40…a582bd（新版）
```

### 4.3 安装步骤

```bash
# 1) 卸原包（签名不同，不卸必失败 INSTALL_FAILED_UPDATE_INCOMPATIBLE）
adb uninstall com.RoamingStar.BlueArchive

# 2) 清 ACE 记账 4 路径（宿主机 su）
adb shell "su -c 'rm -rf /data/data/com.RoamingStar.BlueArchive/files/ace_shell_di.dat \
                          /data/data/com.RoamingStar.BlueArchive/files/shell_cache \
                          /data/data/com.RoamingStar.BlueArchive/files/ano_tmp'"
adb shell "su -c 'rm -rf /data/app/*/com.RoamingStar.BlueArchive*'"   # ⚠ 可选，风险高，见下

# 3) 安装（2 GB，走 adb install -r 会慢；建议 push 到 /data/local/tmp 再 pm install）
adb push BA_noroot_v2.apk /data/local/tmp/ba_v2.apk
adb shell "su -c 'pm install -r /data/local/tmp/ba_v2.apk'"      # 期望 Success

# 4) 启动
adb shell monkey -p com.RoamingStar.BlueArchive -c android.intent.category.LAUNCHER 1
```

> ⚠ 第 2 步里 `rm -rf /data/app/*/...` 只在"装完仍闪退且确认是 ACE 记账污染"时才做；正常先只删 `files/` 下三个。
> ⚠ `pm install` 在 `u:r:ksu:s0` 下可能被挡（`Failed transaction`），此时改用 `adb install`（走 `shell` 域）。

### 4.4 验收标准（四条，逐条判）

| # | 判据 | 怎么判 | 失败含义 |
|---|---|---|---|
| **A** | **能装上** | `pm install` 返回 `Success`；`dumpsys package` 里 `versionCode=73` | 装不上 = 签名/对齐/zip 结构问题 |
| **B** | **能进标题画面 ≥ 45 s 不闪退** | 目视 + `pidof` 持续存在 | 闪退 = ACE 完整性（`__tpinfo` 没删干净？）/ 签名校验 |
| **C** | **能登录进大厅** | 出现大厅 UI；服务端 `sdk.log` 出现 `/user/quick-login` 或 `/user/login` | 登录失败 = `sdk_url` 指向/证书/卡密 |
| **D** | **能打关卡** | 进关卡、打完一次结算；服务端网关日志有 `Campaign_*` 协议 | 关卡失败 = `Servers`/网关（§2 那个 bug） |
| **E** | **付费按钮拉不起真支付**（安全判据） | 点付费：**不应该**出现官方收银台/优星网络二维码；应报错或无反应 | 拉起了 = `cn_billing_block.txt` 没开 ⇒ **立刻停测**（会真扣钱） |

### 4.5 失败时的分层定位（把 logcat 抓给我）

```bash
adb logcat -c && adb shell monkey -p com.RoamingStar.BlueArchive -c android.intent.category.LAUNCHER 1
sleep 20 && adb logcat -d > ba_v2_logcat.txt
grep -iE "Curl error|UnityTls|SSLHandshake|certificate|Trust anchor|INSTALL_FAILED|ACE|airisg" ba_v2_logcat.txt | head -40
```

| 症状 | 指向 |
|---|---|
| `Curl error 60` / `UnityTls error code: 7` | TLS 没过（证书链）——但我们是真证书，出现即说明**客户端没连到我们的域名** |
| `Trust anchor for certification path not found` | 同上，或 `ServerInfoDataUrl` 没生效 |
| 启动即 SIGBUS / 无 logcat | 动了被 ACE 钉住的 .so（我们没动，几乎不可能） |
| 卡在标题画面 | ACE 完整性 / `__tpinfo` 残留 |
| `404` / 连接成功但协议错 | `Servers` 指向了 www（§2 bug 未修） |

### 4.6 回滚

```bash
# 客户端
adb uninstall com.RoamingStar.BlueArchive
adb install report_tmp_cn_base.apk            # 原厂包（签名不同，先卸再装）
# 若之前备份过 ACE 记账：还原 /sdcard/ba_ace_bak.tgz 到 /data/data/.../

# 服务端
printf '%s' '{"Servers":["https://example.com/api/"],"State":1,"Msg":""}' \
  > /www/wwwroot/bapatch/noroot_payloads/state1.json
```

---

## 5. 台账：本轮改动与哈希

| 文件 | 动作 | 大小 | sha256 |
|---|---|---|---|
| `_noroot\apk\BA_noroot_v2.apk` | **新建（产物）** | 2,127,971,177 B | `682A9EA20DD9C9EC955454ACD937E2A8C002F13EC7B6B1307112B3C61D4EA2EC` |
| `_noroot\apk\payloads\state1.json` | **新建（待上线）** | 64 B | `2A150B40CC1DDE80BF5929D60DFF5367A8F2BEDC96709B213A29E71D21A582BD` |
| `_noroot\apk\build_noroot_apk.py.bak-20261117` | 备份（未改原文件） | 109,025 B | 同基线 `24CB37705DE6D6860F1F7925F3379196D9469C942CD323AEB44B0B92E3DA8CFD` |
| `work\ba\noroot\build_noroot_apk.py` | **未改动** | 109,025 B | `24CB37705DE6D6860F1F7925F3379196D9469C942CD323AEB44B0B92E3DA8CFD` |
| `report\_tmp\cn_base.apk` | 未改动（源包） | 2,126,400,085 B | `DD30A285B58508252DF09A503B025850A27A73C89F1162454BEE55A60D7F83BB` |
| `work\ba\noroot\GameMainConfig_http_example.com.bin` | 被 `--gmconfig-selftest` 重写（正常落盘） | 5.1 KB | — |

---

## 6. 待办 / 阻塞

| # | 事项 | 负责 | 状态 |
|---|---|---|---|
| 1 | `state1.json` 上线（§2.4） | **srv-ops** | ❌ 阻塞 ④ |
| 2 | 真机安装测试（§4） | **phone-ops** | ⏸ 等 #1 |
| 3 | 证书续期渠道决策 + 上线（§3） | **Lead 点头 + srv-ops** | ⏳ 截止 11-28 |
| 4 | 确认 `:5000`/`:8080` 在跑 | srv-ops | ⏳ |
| 5 | 抓包确认客户端严格用 `Servers[0]`（§2.5） | phone-ops | ⏸ 等 #1 |
| 6 | 支付端点实测（`sdk_url` 是否支配支付） | Lead 决策 | ⏳ 与无 root 无关，但影响 C 路线 |
