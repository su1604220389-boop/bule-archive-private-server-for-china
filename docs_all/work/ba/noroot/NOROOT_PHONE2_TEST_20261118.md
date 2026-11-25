# 免 root 客户端 · 第二台手机（PYB110）装机与测试台账

> 起草 2026-11-18 00:10（Asia/Shanghai）
> 状态：**装机进行中**，等待首次启动验证
> 本文只记录**实测**；推断一律标注「推断·未证实」。

---

## 0. TL;DR

| 项 | 值 |
|---|---|
| 目标机 | PYB110（OnePlus）· **无 root** · Android 17 / SDK 37 · arm64-v8a · /data 剩 583 G |
| ADB | 无线调试配对成功 → serial `192.168.0.6:42933` |
| 装机包 | `work\ba\noroot\BA_noroot_prod_20261118_v1.apk` |
| 大小 | **2,127,971,177 B** |
| sha256 | `5F8B79DD930B8D1420B5B686CBC978142B751EEA47C4B090BA308482A0F2F5C6` |
| 客户端指向 | 游戏 `https://example.com/api/state` · SDK `https://example.com/sdk` |
| TLS | **不需要装任何证书** —— 该域名有真实 Let's Encrypt 证书，公网侧 `ssl_verify_result=0` |
| 唯一未证实 | 客户端是把 `sdk_url` 当**前缀拼接**还是**主机基址+绝对路径 resolve**（决定 `/sdk` 前缀该不该留） |

---

## 1. 这台机器与第一台的关键差异

| 维度 | 第一台（现役，root） | 第二台（本机，无 root） |
|---|---|---|
| root | KernelSU，`su` 可用 | **无**（`/system/bin/su` 等均不存在，`id` = uid 2000 shell） |
| 网络改写 | iptables DNAT + `/system/etc/hosts` | **不能用**，只能改 APK 内部的 URL |
| 证书 | 系统 CA + MITM 拦 `*.bluearchive-cn.com` | **不需要**（走我们自己的域名 + 真实证书） |
| 装机方式 | 已装官方包 | 官方包 → **必须先卸载**（签名不同） |

---

## 2. 手机侧实测基线（2026-11-18 00:00）

```
ro.product.model / name = PYB110
ro.product.brand        = OnePlus
ro.build.fingerprint    = OnePlus/PYB110/OP64E1L1:17/CP2A.260605.016/C.3601857-f47121-f4775e:user/release-keys
ro.build.version.release= 17        ro.build.version.sdk = 37
ro.build.version.security_patch = 2026-11-01
ro.build.type           = user      ro.debuggable = 0
ro.product.cpu.abilist  = arm64-v8a
df /data                = 931G 总 / 348G 用 / **583G 可用**
```

### 2.1 ADB 配对（一次成功）

```
adb pair 192.168.0.6:40565 970963
→ Successfully paired to 192.168.0.6:40565 [guid=adb-3B169V012KT00000-pEOafQ]
```

配对端口 ≠ 连接端口。`adb mdns` 在本机不可用（`ERROR: mdns daemon unavailable`），
限速扫 30000–50000 命中 `42933 / 46888 / 49897`，只有 **42933** 连通：

```
adb connect 192.168.0.6:42933   → connected
adb devices -l → 192.168.0.6:42933  device  product:PYB110 model:PYB110
```

### 2.2 装机前那台机上的东西

```
com.RoamingStar.BlueArchive  3.0.2 / versionCode 73   ← 官方包
  base.apk = 2,126,400,085 B     ← 与官方源包 cn_base.apk **完全一致**
  签名     = 46a91e98 / oplus Fingerprint 20E318B9…CAB4CE   ← **不是**我们的证书
  我们的证书 sha256 = 94:FA:99:7B:…:9E:BC                     ← 两者不同
  /sdcard/Android/data/<pkg> = 4.6 G（AssetBundles / MediaPatch / TableBundles / il2cpp）
  **没有 ClientSaveData 目录** ⇒ 无本地存档，卸载不丢进度
```

⇒ 同包名不同签名，`install -r` 必 `INSTALL_FAILED_UPDATE_INCOMPATIBLE`，只能先卸载。

---

## 3. 服务端路由实测（免 root 路线的可行性依据）

`srv-ops` 只读盘点 + Lead 公网侧两次 curl：

```
nginx vhost: /www/server/panel/vhost/nginx/example.com.conf
  listen 80;                                  ← 明文入口
  listen 127.0.0.1:8443 ssl;                  ← SNI 分流后（真实证书在这一侧）
  server_name example.com example.com;
  location = /api/state  → root noroot_payloads; rewrite ^ /state1.json break;
  location = /           → return 200 "ok"
  location ^~ /          → proxy_pass http://127.0.0.1:5000;   ← Shittim
  location /sdk/         → proxy_pass http://127.0.0.1:8080/;  ← sdkcard.py（剥 /sdk 前缀）

监听: 0.0.0.0:80 443 8081(卡密面板) / 5000,5100,6667(dotnet) / 127.0.0.1:8080(SDK) / 127.0.0.1:9097(桥)
```

Lead 公网侧实测（各 1 次，间隔 3 s，未触发 WAF）：

```
https://example.com/            → 200   ssl_verify_result=0   ip=<SERVER_IP>:443
https://example.com/api/state   → {"Servers":["https://example.com/api/"],"State":1,"Msg":""}
```

**结论**：证书是真实的公共 CA 签发（`ssl_verify_result=0`，本机没装任何自定义 CA），
⇒ 无 root 客户端**直接走 https 即可**，不需要 `src="user"`、不需要装证书、不需要 MITM。

> 更正一条旧说法：ca-researcher 之前报的「证书 2026-12-12 到期、只剩 25 天」**已作废**——
> 现在这张是 Let's Encrypt，`notAfter 2027-02-15`，可 ACME 自动续期。

---

## 4. APK 构建

```
python work\ba\noroot\build_noroot_apk.py \
  --src report\_tmp\cn_base.apk \
  --out work\ba\noroot\BA_noroot_prod_20261118_v1.apk \
  --sdk-url      https://example.com/sdk \
  --gmconfig-url https://example.com/api/state \
  --keystore work\ba\noroot\ba_private.keystore --storepass baserver --alias ba
→ exit 0，44.7 s
```

### 4.1 包内配置

```
sdk_url            = https://example.com/sdk          （原厂 https://sdk-api.yostar.cn）
ServerInfoDataUrl  = https://example.com/api/state
package            = com.RoamingStar.BlueArchive           （未改，ACE 钉包名）
versionCode 73 / versionName 3.0.2 / minSdk 24 / targetSdk 33   （aapt2 独立复核）
```

### 4.2 变化清单（41,312 → 41,307 条目）

```
+ META-INF/CERT.SF            156 B
+ META-INF/CERT.RSA         1,208 B
- assets/__tpinfo.tp            12 B      ← ACE 完整性清单，5 件全删是**必须**的（不删必闪退）
- assets/__tpinfo.tsc      485,268 B
- assets/__tpinfo.tsc.sig      256 B
- assets/__tpinfo.tsd        1,668 B
- assets/__tpinfo.tsd.sig      256 B
- META-INF/BACN.SF        5,151,804 B      ← 原厂 v1 签名文件，整组剔除重签
- META-INF/BACN.RSA           1,064 B
~ assets/SDKConfigSettings.json  2,840 → 2,843
~ assets/bin/Data/…GameMainConfig 5,212 → 5,212
~ res/Dk.xml                   264 → 560    ← 加 system+user trust-anchors（本路线其实用不到）
~ META-INF/MANIFEST.MF   5,151,677 → 5,151,246
不变 41,301 条
```

### 4.3 自检结论（`--verify-only` exit 0）

```
v2 OK / v3 OK / v1 OK（最长行 70 B，超 72 B 的行 0 个，X-Android-APK-Signed='2, 3'，PKCS#7 验签 OK）
zip 完整性 OK / __tpinfo 残留 无 / resources.arsc 第 1 条 STORED / package 名正确
```

⇒ `INSTALL_PARSE_FAILED_NO_CERTIFICATES` 风险不存在，v1 不需要关。

### 4.4 可复现性

同参数重跑与本轮产物**逐字节相同**（sha256 一致）。

---

## 5. 首启后要验证的三件事（按顺序）

| # | 期望 | 判据 | 失败时看哪里 |
|---|---|---|---|
| 1 | 客户端打 `https://example.com/api/state` 拿到 `Servers` | nginx 访问日志出现该请求且 200 | srv-ops 访问日志 |
| 2 | 游戏 API 打到 `/api/gateway` 等，Shittim 有响应 | 日志 & Shittim stdout | Shittim stdout（tmux `shittim`） |
| 3 | SDK 登录打到 `/sdk/common/config` | 路径**带** `/sdk` 前缀 | 见 §6 |

---

## 6. 唯一未证实的风险：`sdk_url` 的拼接模型

两种情况无法用历史观测区分（因为历史上所有 `sdk_url` 都**没有路径**，两种模型结果相同）：

```
模型 A（拼接）：sdk_url + "/common/config"
  → https://example.com/sdk/common/config → nginx 剥 /sdk → sdkcard /common/config ✅
模型 B（resolve）：把 sdk_url 当主机基址，绝对路径覆盖
  → https://example.com/common/config → location ^~ / → Shittim:5000 → 404 ❌
```

当前选择 `.../sdk` 是**弱占优**：模型 A 下正确；模型 B 下裸主机同样错，所以它不是猜。

**判别方法**：首启后看 nginx 日志第一跳是 `/sdk/common/config` 还是 `/common/config`。
若出现 `/common/config` → 证明是模型 B，**不需要重新构建 APK**。

### 6.1 兜底片段已备好（**未应用**）

srv-ops 实测：Shittim(5000) 对 `/common/*`、`/user/*`、`/heartbeat/*`、`/order/*` **全部 404**
⇒ 这些前缀**没有被 Shittim 占用，转发给 8080 是安全的**。

```nginx
# BAPATCH-SDKFALLBACK v1  —— 仅当客户端丢掉 /sdk 前缀时才需要
location = /common/config { proxy_pass http://127.0.0.1:8080; }   # 精确匹配，优先级高于 ^~ /
location ^~ /common/      { proxy_pass http://127.0.0.1:8080; }
location ^~ /user/        { proxy_pass http://127.0.0.1:8080; }
location ^~ /heartbeat/   { proxy_pass http://127.0.0.1:8080; }
location ^~ /order/       { proxy_pass http://127.0.0.1:8080; }
# BAPATCH-SDKFALLBACK v1 END
```

要点（都是实测/官方规则，不是推断）：
- `proxy_pass` **不能带结尾斜杠**，否则 URI 被剥前缀（`/user/login` → `/login`）⇒ 404
- 位置：第一个 server 块内，`location ^~ /`（conf:100）之前或 `/sdk/`（conf:160）之后
- nginx 匹配顺序：`=` 精确 → 最长前缀（`^~` 只跳过正则，不改变最长优先）→ 正则 → 回落。
  所以 `= /common/config` 不会被 `^~ /` 吃掉；`^~ /user/`(7 字符) 长于 `^~ /`(1 字符)
- 改法：**宝塔面板 → 网站 → example.com → 设置 → 配置文件** 保存（不要 SSH 手改 .conf，面板会覆盖）
- 回滚：删掉 `BAPATCH-SDKFALLBACK v1` 到 `v1 END` 整段

---

## 7. 装机（**已完成 · 2026-11-18 00:13:24**）

```
① Get-FileHash sha256 = 5F8B79DD…F2F5C6            MATCH=True
② uninstall com.RoamingStar.BlueArchive             → Success（2.3 s）
   /sdcard/Android/data/<pkg> → No such file（4.6 G 随卸载删除，已批准）
③ install -r BA_noroot_prod_20261118_v1.apk         → Success（**427 s ≈ 7.1 分钟**）
   过程形态：前 ~5 分钟 /data 几乎不动（+392 KB/60s），最后 ~45 s 猛增 332 MB 后 Success
   全程无 Ctrl-C、无断连、无 INSTALL_FAILED_*，Android 17/SDK37 上未触发 DEPRECATED_SDK_VERSION
④ dumpsys：versionCode=73 / versionName=3.0.2 / minSdk24 / targetSdk33 / lastUpdateTime=2026-11-18 00:13:24
   base.apk = 2,127,971,177 B（与产物逐字节同长）
   signatures 46a91e98（官方）→ **f507b81f**（我们的）
⑤ 游戏由**用户自己**点开（Lead 与 phone-ops 都不 am start）
```

取证已就位：手机侧全量 `logcat`（30 min，>34 MB 已写入），服务端按需抓访问日志/SDK 日志/Shittim stdout。

**代价（已由用户批准）**：那台机上的 4.6 G 官方资源会随卸载消失，首启需重新下载。
曾尝试用 `mv` 保住这 4.6 G，失败——`files/il2cpp` 是 `drwxr-s--- u0_a460`，无 root 下 shell 读不了，
`mv` 在 `il2cpp` 子树报 `Permission denied` 后中止（原目录未受损，半截备份 37 M 已清）。

---

## 8. 回滚

```
# 恢复到官方包：卸载我们的包 → 从应用商店重装 3.0.2
adb -s 192.168.0.6:42933 uninstall com.RoamingStar.BlueArchive
# 服务端：本轮**没有改任何服务端配置**，无需回滚
# APK：删掉 work\ba\noroot\BA_noroot_prod_20261118_v1.apk 即可，源包 cn_base.apk 未动
```

---

## 9. 反作弊（ACE）相关事实（决定"哪些能改"）

摘自 `NOROOT_BUILD.md` §4 / `_dd4-integrity.md`，本轮实测复核过关键几条：

```
ACE 钉死：libunity.so、libtprt.so、libairisgcore.so、加载布局（不许新增 .so / 改 DT_NEEDED / 加 dex）、**包名**
ACE 不钉：libil2cpp.so、res/*、resources.arsc、assets/*.json、**不校验本地签名**（3 次重签实测跑起来了）
必须删：assets/__tpinfo.{tp,tsc,tsc.sig,tsd,tsd.sig} 5 件 —— 清单不在就不校验
别多删：assets/__tpcfinfo.tsa、__tpsinfo.t.p.sin、tpginf.dat
```

⇒ 本轮的改动集（`assets/*.json` + `assets/bin/Data/*` + `res/Dk.xml` + 重签）**完全落在"不钉"一侧**，
且**没有改包名**——这是刻意选的，因为 ACE 钉包名。

若启动后 8~10 s 被 ACE 杀（闪退）：先卸载重装一次（干净状态）；
**不要** `pm clear`——`_dd4-integrity.md` 记录 `files/data/app` 被清会导致永久卡启动。

---

## 10. 首次启动失败 → 修复（2026-11-18 00:21）

### 10.1 现象

用户点开游戏 → 弹窗：

```
标题  提示
正文  404：很抱歉，初始化资源失败，请重试。如果仍然无法解决，请您重启手机，再打开游戏试试。
按钮  网络检测 / 重试        背景  NEXON GAMES / YOSTAR 启动画面
```

### 10.2 定性：**这个弹窗是 AiriSDK 给的，不是游戏**

```
弹窗窗口      com.RoamingStar.BlueArchive/com.airi.official.core.base.BackgroundAct   ← AiriSDK 的 Activity
游戏本体      TechSDKUnityPlayerActivity 已被压到下层（mLastPausedActivity）⇒ Unity 还没开始
资源目录      /sdcard/Android/data/<pkg> 只有 37 M，无 AssetBundles/TableBundles/catalog_Remote
```
⇒ 游戏资源管线**根本没启动**（它排在 SDK 登录之后），所以「初始化资源」指 **SDK 自己的配置资源**。

服务器访问日志实锤（00:14:57–00:15:28）：

```
127.0.0.1 - - [18/Nov/2026:00:14:57 +0800] "POST /common/config HTTP/2.0" 404 0 "-" "okhttp/4.9.2"
… 共 12 次，全部 404
```

### 10.3 根因：**客户端把 `sdk_url` 的路径丢了**

```
我们填的   sdk_url = https://example.com/sdk
客户端打   POST https://example.com/common/config        ← /sdk 前缀被丢
nginx      /common/config 不匹配 /sdk/ ⇒ 落进 location ^~ / → Shittim:5000 → 404
```

⇒ `sdk_url` 的**路径分量无效**（客户端把它当主机基址 + 绝对路径 resolve）。
所以「改 APK 里的 `sdk_url` 加路径」这条路**走不通**，必须服务端路由。

> 为什么以前不需要：现役 root 手机的 SDK 仍指向官方 `sdk-api.yostar.cn`，**从不问我们服务器要 `/common/config`**。
> 这条路由是随「SDK 指向自己」第一次出现的需求，不是服务端坏了。

### 10.4 修复：nginx 加 5 条 location（**不含 Shittim 改动**）

```nginx
# BAPATCH-SDKFALLBACK v1
location = /common/config { access_by_lua_block { } proxy_pass http://127.0.0.1:8080; }
location ^~ /common/      { access_by_lua_block { } proxy_pass http://127.0.0.1:8080; }
location ^~ /user/        { access_by_lua_block { } proxy_pass http://127.0.0.1:8080; }
location ^~ /heartbeat/   { access_by_lua_block { } proxy_pass http://127.0.0.1:8080; }
location ^~ /order/       { access_by_lua_block { } proxy_pass http://127.0.0.1:8080; }
# BAPATCH-SDKFALLBACK v1 END
```

- `proxy_pass` **不带结尾 `/`**（带了会剥前缀）
- **`access_by_lua_block { }` 空块 = 这 5 个前缀跳过 WAF**（沿用现有 `/sdk/` location 的写法）
  ⚠ 原因：free_waf 处理 `/common/config` 时自身抛 Lua 异常
  `init.lua:1656: attempt to compare nil with number`（`url_rule_ex` → `run_btwaf`）→ 500。
  空块是唯一**不修改 WAF 本体**的绕过方式；副作用是这 5 个前缀不再过 WAF（与 `/sdk/` 一致）——**用户已被明确告知**
- 位置：第一个 server 块，`location /sdk/` 之后；`nginx -T` 924 → 931 行

### 10.5 备份与回滚

```
备份目录  /root/nginx_backup_20261118_002008/
  example.com.conf              改前原件 sha256 e873f22b86f81bdcdc38c068155ac9f31c5aee3a9ba8297a5255188b79ee2c05
  nginx_T.before                     改前全量生效配置（924 行）
改后 sha256  dc3e351a26e3b0a1b732698b4edfebb7fd36f493a093f3b2bd3b9ac74300e5a0
```

回滚（一条）：
```bash
cp -a /root/nginx_backup_20261118_002008/example.com.conf /www/server/panel/vhost/nginx/example.com.conf && nginx -t && nginx -s reload
```

### 10.6 改后验证

```
nginx -t  → syntax ok / test successful
nginx -s reload → 平滑重载，Shittim 未重启
POST /common/config    → 200  7,838 B      ← 关键
POST /user/quick-login → 200  53 B  {"Code":40003,"Msg":"请输入卡密"}
GET  /api/state        → 200  64 B
GET  /api/gateway      → 200
```

---

## 11. 第二关：`/api/state` 载荷缺资源地址（2026-11-18 00:28）

### 11.1 现象
SDK 那关过了之后，游戏进到**标题画面**，但：

```
无任何加载指示（用户："左下角一般会有加载标志"）
/sdcard/Android/data/<pkg> 仍 37 M；20 分钟内 0 个新文件 ⇒ 完全没发起资源拉取
```

服务器日志（00:22–00:23，这台手机，UA 可区分）：

```
00:22:05  POST /common/config       200  4,871   okhttp/4.9.2
00:22:05  POST /common/client-code  200  38      okhttp/4.9.2
00:22:08  GET  /api/state           200  64      UnityPlayer/2021.3.56f2 (UnityWebRequest)
00:23:06  POST /common/config       200  4,871
00:23:07  GET  /api/health          200  15
00:23:08  GET  /api/state           200  64      UnityPlayer
```

⇒ **连接完全正常（全 200、无 444）**，问题在**响应内容**。

### 11.2 根因：state 载荷少了「资源在哪」

```
我们返回   {"Servers":["https://example.com/api/"],"State":1,"Msg":""}   64 B
官方返回   + AddressablesCatalogUrlRoots(3× static*.bluearchive-cn.com/prodm39)
           + ResourceVersion / TableVersion / MediaVersion / PatchVersion
           + CallbackUrl / IsOpenPreDownload                                   676 B
```

客户端拿不到 `AddressablesCatalogUrlRoots` ⇒ 不知道去哪下 ⇒ 静默停在标题、不报错、不下载。

**为什么现役 root 手机没事**：它本地已有 4.6 G 资源，从不问服务器要地址。

**这是回归，不是一直如此**：`state2.json`(676 B) 一直存在，但挂在**第二个 server 块**
（`listen 127.0.0.1:8443 ssl` + `server_name example.com`）上，而该块与第一个块
（`:9` 已声明 www、`:4` 已 listen 8443）冲突 ⇒ nginx 启动时直接 `conflicting server name ... ignored`
⇒ **state2.json 对所有入口都不可达**。访问日志旁证：11-17 出现过 `200 676 B`，18 号 00 点起全是 64 B。

### 11.3 修复：只替换 `state1.json` 一个文件

```
路径   /www/wwwroot/bapatch/noroot_payloads/state1.json
改前   64 B   sha256 2a150b40cc1dde80bf5929d60dff5367a8f2bedc96709b213a29e71d21a582bd
改后   720 B  sha256 8b3ba6bf59646f404281068338866d4ead38d7a483030a8472243712f14c1086
内容   state2 的 10 个字段逐字段原样搬运 + 新增 "Servers":["https://example.com/api/"]
```

- **用 python 从 state2.json 复制字段**，不手打；应用前 assert：Servers 正确、state2 的每个 key 都存在且逐字段相等、State==1、roots 3 条且都以 `https://static` 开头
- 属主/权限沿用原值（`root:root 644`）
- **静态文件即时生效，没有 reload nginx**

### 11.4 备份与回滚

```
备份目录  /root/payload_backup_20261118_002833/
  state1.json.before（64 B / sha 2a150b40…）
  state2.json.before（676 B，未改，仅备份）
  SHA256.before（含属主/权限）
```

回滚（一条）：
```bash
cp -a /root/payload_backup_20261118_002833/state1.json.before /www/wwwroot/bapatch/noroot_payloads/state1.json && sha256sum /www/wwwroot/bapatch/noroot_payloads/state1.json
```

### 11.5 验证 + 回归

```
GET /api/state  → 200  720 B   body 含 AddressablesCatalogUrlRoots   ✅
GET /api/gateway → 200                                              ✅ 未回归
POST /common/config → 200                                           ✅ 未回归（5 条兜底仍在 conf:171-175）
无 444
```

### 11.6 关于带宽（用户问）

资源地址是 `static*.bluearchive-cn.com` ⇒ **官方 CDN**。这台无 root 机没有 DNS 劫持/MITM，
公网解析到官方 CDN 真实 IP，**直连**。我们 3 Mbps 只跑 `/common/config`(4.8 KB)、`/api/*`(KB 级)。
服务端侧 `tcp/ba_sni.conf` 的 SNI 分流对 `static*` 是 **stream 层直通真 CDN**（那是给 root 机用的路径），
本机不经过。

---

## 13. 第三～四关：卡密登录成功 → 卡在 `/api/account/auth`（2026-11-18 00:33–00:36）

### 13.1 第三关：卡密登录 —— ✅ 通过

登录框是 **AiriSDK 自己的 Activity**（`com.airi.official.core.base.BackgroundAct`），不是游戏画的。
它连的是**我们的** `sdkcard.py`（`POST /common/config → 200 / 4,871 B`）。

**界面文字是原厂的**，因为本次构建**没有打「文案改造」补丁**：

```
SDK_ASSETS.md:35   work\ba\bapatch\res_edited\strings.xml
  hint_phone_number = 请输入卡密      ← 旧版 E42 打过这个补丁
  hint_phone_code   = 密码
  illegal_phone     = 卡密不正确
  + res/layout/fragment_default_mobile_code_login.xml
```

⇒ 「请输入手机号」那一栏**就是卡密栏**（服务端只读 `OpenID`）。

实测登录：

```
00:33:19  POST /sdk/user/send-sms    200  38 B   （我们没实现，走兜底假 200，无所谓）
00:33:46  POST /sdk/user/login       200  847 B
          BODY {"OpenID":"11111111111","Secret":"","Token":"111111","Type":"mobile","UserName":""}
          → LOGIN OK 11111111111  dev=ce8ffeb7d08cfb36
cards.json: "11111111111".devices = ["09a4d0ab0ee93616", "ce8ffeb7d08cfb36"]   ← 新机已绑定
```

`sdkcard.py` 的关键实现（据此确定操作方式）：

```
:322  key = str(j.get('OpenID') or '').strip()      ← 只读 OpenID 这一个字段
:323-339 只有 卡不存在 / 过期 / 已绑定 三种拒绝，**没有验证码校验分支**
:375  其它任何 path → {"Code":200,"Msg":"OK","Data":{}}   ← 假成功兜底
:345  quick-login 判定：dev 必须在某张卡的 devices 里，否则 :352 返回「请输入卡密」
```

⇒ **操作方式**：卡密 `11111111111` 填进「手机号」框，验证码随便填（`111` 即可），**不要点「发送」**。

### 13.2 第四关：`/api/account/auth` 打到空处 —— ❌ 曾是断点

```
00:33:47  POST /api/account/auth  200  184 B  UA BestHTTP/2 v2.4.0
          落在 /www/wwwlogs/example.com.log
```

对照两条 vhost 的 `/api/` 分流：

| | `ba_mitm.conf`（现役 root 机） | `example.com.conf`（新机） |
|---|---|---|
| `/api/` 其余 | `location ^~ /api/ → 127.0.0.1:9097`（桥） | `location ^~ / → 127.0.0.1:5000`（Shittim 直连） |

```
Shittim(5000) 对 POST /api/account/auth → 200 / 184 B 空壳（无此路由）
桥(9097)      对 POST /api/account/auth → 200 / 3,456 B **正常 CN 加密信封**（本地实测）
```

⇒ 客户端拿到空壳 → 认为登录完成 → 停在标题轮播（Unity 前台、GPU 98–100%、资源停在 453 M、不报错）。

### 13.3 修复：只加一条精确路径

```nginx
    # BAPATCH-AUTHPROXY v1
    location = /api/account/auth {
        access_by_lua_block { }
        proxy_pass http://127.0.0.1:9097;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header Connection "";
    }
    # BAPATCH-AUTHPROXY v1 END
```

- **刻意不加 `location ^~ /api/`** —— 那会把 `/api/gateway` 也带走，而 `/api/gateway → 5000`
  是 00:18 那次完整登录（15+ 协议全 200）验证过的通路，属于「不能动的能用的东西」
- `access_by_lua_block { }` 跳过 WAF（与 `/sdk/`、SDKFALLBACK 一致，避免 free_waf 的 Lua 500）
- 行号：conf:177–187；`nginx -T` 931 → 942 行；`location ^~ /api/` 出现次数 = 0（未误加）

### 13.4 备份与回滚

```
备份  /root/nginx_backup_20261118_003605/（原件 + SHA256.before + nginx_T.before 931 行）
改前  dc3e351a26e3b0a1b732698b4edfebb7fd36f493a093f3b2bd3b9ac74300e5a0
改后  d19eec29b0f80ab53a982392f99de355c3c0f1a117288090d9f1b0a94a65a649
```

```bash
cp -a /root/nginx_backup_20261118_003605/example.com.conf /www/server/panel/vhost/nginx/example.com.conf && nginx -t && nginx -s reload
```

### 13.5 验证（含一个假阴性）

```
第一次 00:36:11  account/auth → 404/0     ← reload 过渡窗口，旧 worker 仍在处理，**不是配置问题**
第二次 00:36:27  account/auth → 200 / 3,456 B  ✅（与直连 9097 完全一致）
                 gateway      → 200
                 state        → 200 / 720 B
                 common/config→ 200 / 7,838 B
```

---

## 15. 第四关：`/api/*` 整层要走桥（2026-11-18 00:42–00:44）

### 15.1 客户端有两层 HTTP API，只有一层走了桥

```
/api/account/auth  /api/academy/getinfo  …   ← 桥（9097）的业务 API（UA BestHTTP/2）
/api/gateway                                 ← Shittim 网关（multipart + protocol 令牌）
```

- `ba_mitm.conf`（现役 root 机）：`location ^~ /api/ → 127.0.0.1:9097` ⇒ **整层进桥**，所以一次就进
- `example.com.conf`（新机）：只加了 `= /api/account/auth` 一条 ⇒ 第一步通、第二步 `academy/getinfo` 掉回 5000 回 184 B 空壳

实测（00:42:06，新机这一次）：

```
POST /api/account/auth     200  2,706 B   ← 桥信封（之前是 184 B 空壳）
POST /api/academy/getinfo  200    184 B   ← 又掉了
之后：无 Account_LoginSync
```

### 15.2 修复：`^~ /api/` 整层 → 9097（照抄 root 机的已验证配置）

```nginx
    # BAPATCH-APIPROXY v1
    location ^~ /api/ {
        access_by_lua_block { }
        proxy_pass http://127.0.0.1:9097;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header Connection "";
    }
    # BAPATCH-APIPROXY v1 END
```

前置确认（桥源码）：`GATEWAY = 'http://127.0.0.1:5000/api/gateway'`（:165，桥内部会调网关）；
未知路径走 `fallback='forward-known-other'` 转发 5000（:2341）。⇒ 整层进桥不会断网关。

`= /api/state`（静态 720 B）与 `= /api/health` **保持精确匹配不动** —— 精确优先，不会被 `^~ /api/` 吃掉。

### 15.3 备份与回滚

```
备份  /root/nginx_backup_20261118_004318/
改前  d19eec29b0f80ab53a982392f99de355c3c0f1a117288090d9f1b0a94a65a649
改后  651119deab58a5bfaf158706ea23ebf7270657d152bb7eeb13b281bc28d98540
```

```bash
cp -a /root/nginx_backup_20261118_004318/example.com.conf /www/server/panel/vhost/nginx/example.com.conf && nginx -t && nginx -s reload
```

验证：`state` 200/720 · `account/auth` 200/3,456 · `academy/getinfo` 已进桥（日志 `fallback=forward-known-other`）· `gateway` 已进桥 · `common/config` 200

---

## 16. **新发现的隐患：存在第二份 SDK 配置，我们从来没改过**

`assets/bin/Data/129346de773e72d2ec581682f32d43da` 是一个 **Unity TextAsset，名字就叫 `SDKConfigSettings`**，
内嵌一份与 `assets/SDKConfigSettings.json` **逐字节相同的 2,840 B JSON**（偏移 `0x01033`，长度前缀 `18 0b 00 00` = 2840）。

```
我们改了        assets/SDKConfigSettings.json      → https://example.com/sdk   ✅
没改的           上述 TextAsset 里那份              → https://sdk-api.yostar.cn     ❌
```

⇒ 如果 il2cpp/C# 侧读的是 TextAsset，那么 `--sdk-url` 只改了 **Java/okhttp** 那一半。
**待验证**：C# 到底读哪个（需在真机上确认是否有发往 `sdk-api.yostar.cn` 的请求）。
**改它的风险（中）**：新 JSON 2,843 B，比原 2,840 B 多 3 B，属**变长改动**，要同步改长度字段与后续偏移。

另两条同时被排除：

```
gsqc-api 在 APK 里 **零命中** ⇒ 不是客户端硬编码；root 机那个 Host 来自当时 state1.json 的 Servers 值
第二跳（gsqc）响应 **不含 Servers** ⇒ 不会覆盖第一跳；域名入口只有 Servers[0]
```

### 16.1 证据：C# 侧读的是 TextAsset

`global-metadata.dat` @ `0x000C32CC`（全文唯一一处带 `.json` 的字符串）：

```
[TechSDK]: Assets/TechSDK/BrandAssets/Resources/SDKConfigSettings.json is not exits
```

`libil2cpp.so` / `libunity.so` 均 **0 命中**。这是 Unity `Resources.Load<TextAsset>("SDKConfigSettings")`
的典型写法 ⇒ **C# 读烤进 `assets/bin/Data` 的那份**，松散 json 归 Java/okhttp（AiriSDK）。

### 16.2 容器结构（`assets/bin/Data/129346de…`，6,964 B）

```
0x1C    u32 BE = 6964          ← 文件大小字段
0x1008  [u32 17] "SDKConfigSettings" [pad 3]
0x1018  u32 LE = 2840          ← 长度前缀
0x101C  ... 2840 B JSON ...    正好结束于 EOF(0x1B34)
```

- 文本是**文件中最后一个对象**，后面没有东西会连锁位移
- 但文件头有"等于文件大小"的 u32，**变长必须同步改它**，而该容器不是标准 SerializedFile 头
  ⇒ **变长不可控**
- `--asset-replace` 本身能吃变长（只重算 CRC/size），风险全在 Unity 侧

### 16.3 零结构风险的等长方案

```
"https://sdk-api.yostar.cn"   25 字符
→ "https://example.com"  24 字符 + JSON 尾部补 1 个空格 ⇒ 整段仍 2840 B
```

长度前缀、文件头大小、对齐**一律不动**，纯就地覆盖。
不带 `/sdk` 正好：C# 会打 `https://example.com/common/config`，
而 nginx 已有 `= /common/config → 127.0.0.1:8080`（SDKFALLBACK v1 第一条）⇒ 现成可用。

### 16.4 同一份 JSON 里的官方域名（按需再动）

```
http[0]/mtr[0]  https://static.bluearchive-cn.com/checkhealth.html   50 字符 ×2
http[1]/mtr[1]  https://sdk-api.yostar.cn                            25 字符 ×2（+sdk_url 共 3 次）
http[2]/mtr[2]  https://gs-api.bluearchive-cn.com/api/health          44 字符 ×2
cs_url          https://customer.yostar.net/                          28 字符 ×3
```
- 逐串等长做不到（44→35、50→41）；**只能"总量等长"**：整体变短后用尾部空格补回 2840
- 两个计划：`sdk-only`（补 1 空格）/ `both`（补 39 空格）
- 脚本已写好**未执行**：`work\ba\noroot\_patch_textasset_sdkconfig.py`（311 行，默认 dry-run，
  断言：容器 6964 / JSON 偏移 0x101C / 长度前缀 0x1018=2840 / 止于 EOF / 与 loose json 逐字节相同 /
  替换次数精确匹配 / 补丁后仍 2840 / 字段集合不变 / 容器头尾字节未变）
- 已修隐患：`sdk-api.yostar.cn` 在 JSON 里出现 **3 次**，不能用一个串统一替换（会误伤 http[1]/mtr[1]）

**决策**：先只上 `sdk-only`，且**等主链验证完再决定是否重打包**（重打包 = 卸载重装 = 丢 453 MB 资源与设备绑定）。

---

## 18. 第五关：登录成功（2026-11-18 约 00:5x）✅

用户确认：**登录成功，客户端开始直连官方 CDN 下载 10+ GB 资源。**

把 `location ^~ /api/ → 9097` 上线后，链路终于通了。**整条链的最终形态：**

```
① SDK 配置      https://example.com/common/config   → nginx = /common/config → 8080   ✅
② 资源地址      https://example.com/api/state       → 静态 state1.json（720 B，含
                  AddressablesCatalogUrlRoots = 官方 static*.bluearchive-cn.com/prodm39）     ✅
③ 卡密登录      /sdk/user/login（OpenID = 卡密）→ sdkcard.py 200；设备写入 cards.json       ✅
④ 账号认证      /api/account/auth → 桥 9097（2,706 B 信封）                               ✅
⑤ 业务 API      /api/academy/getinfo 等 → 桥 9097（必须整层放行，精确放行不够）             ✅
⑥ 网关协议      /api/gateway → 桥 → 转发 5000（multipart + protocol 令牌）                ✅
⑦ 资源下载      https://static*.bluearchive-cn.com/prodm39 → **官方 CDN 直连**，不占我们带宽 ✅
```

### 18.1 为什么必须整层放行（关键教训）

```
/api/account/auth   → 桥       ✅ 单独精确放行就够了
/api/academy/getinfo → 桥      ❌ 精确放行不够！这是第二条业务路由
```

客户端的「账号层 API」是**一组**（BestHTTP/2 发的），不是一条。
只有像 `ba_mitm.conf` 那样 `location ^~ /api/ → 9097` **整层进桥**才能全通；
桥内部对 `/api/gateway` 会转发 5000（`GATEWAY = http://127.0.0.1:5000/api/gateway`，:165），
对未知路径走 `fallback='forward-known-other'`（:2341）。

### 18.2 免 root 路线相对于 MITM 路线的优势（实测）

```
资源         直连官方 CDN，实测 ≈ 3 MB/s（服务器上限 0.375 MB/s ⇒ 反证没走我们）
我们带宽占用 一整个登录会话 ≈ 几百 KB（/common/config 7.8 KB + /api/* 若干 KB + state 720 B）
证书         不需要装任何 CA（example.com 有真实 Let's Encrypt 证书）
DNS          不需要改（用我们自己的域名，公网解析即可）
```

### 18.3 遗留（下次打包再处理，不影响当前使用）

- `assets/bin/Data/129346de…` 的 Unity TextAsset 里 `sdk_url` 仍指向 `sdk-api.yostar.cn`
  （C# 侧读它，Java/okhttp 读松散 json）。等长补丁脚本已备好未执行，详见 §16
- 登录框文案仍是官方的「请输入手机号 / 请输入验证码」，实际填卡密 + 任意验证码

---

## 19. 待办

- [ ] 装机 + 首启（用户操作）
- [ ] 用 nginx 日志判定 §6 的模型 A/B
- [ ] 首启资源重新下载完成后的实际耗时
- [ ] 登录 → 角色选择 → 进入大厅（验证上一轮 234 角色修复在真机上也成立）
- [ ] 把「免 root 首次安装流程」整理成给用户的一页说明
