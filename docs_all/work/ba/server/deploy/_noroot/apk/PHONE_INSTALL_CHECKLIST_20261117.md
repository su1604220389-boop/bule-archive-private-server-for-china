# v2 装机前检查单（交 phone-ops 执行）

> 出单人：ca-researcher　　执行人：phone-ops　　时间：2026-11-17 20:55 (+08:00)
> 被测产物：`work\ba\server\deploy\_noroot\apk\BA_noroot_v2.apk`
> **2,127,971,177 B　sha256 `5F8B79DD930B8D1420B5B686CBC978142B751EEA47C4B090BA308482A0F2F5C6`**
> 包名 `com.RoamingStar.BlueArchive`／versionCode 73／UID 10576
> 目的：让手机**第一次真正跑我们改过的客户端**（当前装的是原厂包，`sdk_url` 还是官方，所以卡密/假支付全都没生效）。

---

## ⚠ 三条最容易搞错的（先看）

| # | 误解 | 事实 |
|---|---|---|
| 1 | "装完要手动起手机端 8080" | **不用。** v2 的 `sdk_url` 是 `https://example.com/sdk`（公网），由**服务器** nginx → 服务器 `127.0.0.1:8080`。手机端**不需要任何 PRoot/8080**。起手机 8080 是旧形态 A/B 的事，对 v2 无效也无害 |
| 2 | "用 `libil2cpp.so` 哈希判断装的是不是 v2" | **判不出来。** v2 **没有改任何 .so**，`libil2cpp.so` 与原厂逐字节相同。用 `base.apk` 的 sha256 判断（§4.0） |
| 3 | "点付费没反应就说明没事" | **v2 之前**（现在是原厂包）点付费会**直接进官方收银台、真扣钱**。测试全程必须确认 `cn_billing_block.txt=1`（已实测=1）。点之前先看一眼 |

---

## 1. 开测前置（P0，缺一条就别开始）

| # | 条件 | 怎么确认 | 当前 |
|---|---|---|---|
| **P0-1** | 线上 `state1.json` 已换成裸域版（64 B） | `curl -s https://example.com/api/state \| sha256sum` → **必须是 `2a150b40cc1dde80bf5929d60dff5367a8f2bedc96709b213a29e71d21a582bd`** | ✅ **已上线（20:30，我执行，带备份）** |
| **P0-2** | 网关可达 | `curl -s -o /dev/null -w '%{http_code}' https://example.com/api/gateway` → `200` | ✅ 实测 200 |
| **P0-3** | 服务器卡密 SDK 可达 | `curl -s -o /dev/null -w '%{http_code} %{size_download}' -X POST -H 'Content-Type: application/json' -d '{}' https://example.com/sdk/common/config` → `200 7837` | ✅ 实测 200/7837 |
| **P0-4** | 止血开关=开 | 服务器 `cat /www/wwwroot/bapatch/cn_billing_block.txt` → `1` | ✅ 实测 `1` |
| **P0-5** | 手机通道可用 | adb 或 18080 root shell | ⚠ 5555 掉过线，需 phone-ops 确认 |
| **P0-6** | 游戏当前没在跑 | `pidof com.RoamingStar.BlueArchive` → 空 | 需确认 |
| **P0-7** | APK 已传到手机 | §3.1 | — |

> **P0-1 没做就装机 ⇒ 客户端拿 `Servers` 去 www 会 404 ⇒ 会被误判成"包坏了"。** 这是本轮最容易白跑一次的坑。

---

## 2. 装之前备份什么（5 项，都要）

```bash
# ① 记录当前已装版本（回滚判据）
adb shell dumpsys package com.RoamingStar.BlueArchive > bak_pkg.txt

# ② 记录当前 base.apk 的哈希（证明"装之前是原厂"）
adb shell "su -c 'ls -l /data/app/*/com.RoamingStar.BlueArchive*/base.apk'"
adb shell "su -c 'sha256sum /data/app/*/com.RoamingStar.BlueArchive*/base.apk'" > bak_baseapk.sha256
#   原厂 base.apk 的 sha 应与 report\_tmp\cn_base.apk 不同（安装时会重算/对齐），记下来即可

# ③ 备份 ACE 记账 3 文件（删了才能干净启动）
adb shell "su -c 'D=/data/data/com.RoamingStar.BlueArchive/files; tar czf /sdcard/ba_ace_bak.tgz -C \$D ace_shell_di.dat shell_cache ano_tmp 2>/dev/null; ls -l /sdcard/ba_ace_bak.tgz'"

# ④ 备份游戏配置（Hosts 等）
adb shell "su -c 'cp -a /sdcard/Android/data/com.RoamingStar.BlueArchive/files /sdcard/ba_files_bak 2>/dev/null; du -sh /sdcard/ba_files_bak'"

# ⑤ 记录服务端基线（在服务器上跑，或让 srv-ops 贴给你）
#   sha256sum /www/wwwroot/bapatch/noroot_payloads/state1.json   → 期望 2a150b40…a582bd
#   cat /www/wwwroot/bapatch/cn_billing_block.txt                → 期望 1
```

> 玩家进度在服务端（Shittim），本地清了不心疼；但 **ACE 记账不清会污染新包**，所以 ③ 是必须的。

---

## 3. 安装

### 3.1 传包（2 GB，别用 `adb install` 直接推）

```bash
# 先确认本地包身份（Windows 侧）
certutil -hashfile BA_noroot_v2.apk SHA256
# 期望 5f8b79dd930b8d1420b5b686cbc978142b751eea47c4b090ba308482a0f2f5c6

# 推到手机（约 1-3 分钟，视 USB/WiFi 而定）
adb push BA_noroot_v2.apk /data/local/tmp/ba_v2.apk

# 手机上校验（必须一致，否则传输截断）
adb shell "su -c 'sha256sum /data/local/tmp/ba_v2.apk'"
```

### 3.2 卸原包

```bash
adb uninstall com.RoamingStar.BlueArchive
# 若报 DELETE_FAILED_INTERNAL_ERROR，改用：
adb shell "su -c 'pm uninstall com.RoamingStar.BlueArchive'"
adb shell "su -c 'pm uninstall -k com.RoamingStar.BlueArchive'"   # -k 保留数据（本场景不需要）
```
> 签名不同，**不卸必失败** `INSTALL_FAILED_UPDATE_INCOMPATIBLE`。

### 3.3 清 ACE 记账

```bash
adb shell "su -c 'D=/data/data/com.RoamingStar.BlueArchive/files; rm -f \$D/ace_shell_di.dat \$D/shell_cache; rm -rf \$D/ano_tmp; ls -l \$D | head'"
```

### 3.4 安装

```bash
# 方式一（推荐）：pm install，走 root 域，2 GB 不超时
adb shell "su -c 'pm install -r /data/local/tmp/ba_v2.apk'"
# 期望：Success

# 方式二（备用）：adb install --streaming（adb 1.0.41+）
adb install --streaming -r BA_noroot_v2.apk
```
> ⚠ 若 `pm install` 报 `Failed transaction (2147483646)`（`u:r:ksu:s0` 下 binder 被挡），改用方式二（走 `shell` 域）。

### 3.5 启动

```bash
adb shell monkey -p com.RoamingStar.BlueArchive -c android.intent.category.LAUNCHER 1
```

---

## 4. 装完怎么验证

### 4.0 先证明"装的确实是 v2"（30 秒，最有说服力）

```bash
adb shell "su -c 'sha256sum /data/app/*/com.RoamingStar.BlueArchive*/base.apk'"
# 期望 = 5f8b79dd930b8d1420b5b686cbc978142b751eea47c4b090ba308482a0f2f5c6
```
**不要用 `libil2cpp.so` 判断** —— v2 没改任何 .so，哈希与原厂相同。

再补一条"改造是否生效"的旁证：
```bash
adb shell "su -c 'cd /data/app/*/com.RoamingStar.BlueArchive*/ && /data/adb/ksu/bin/busybox unzip -l base.apk | grep -c tpinfo'"
# 期望 0（原厂是 5）
```

### 4.1 验收标准（A–F 六条，全过才算成功）

| # | 判据 | 怎么判 | 失败含义 |
|---|---|---|---|
| **A** | 装得上 | `pm install` → `Success`；`dumpsys package` 里 `versionCode=73` | 签名/对齐/zip 结构 |
| **B** | 能进标题 ≥45 s 不闪退 | 目视 + `pidof` 持续存在 | ACE 完整性（`__tpinfo` 没删净）/ 签名校验 |
| **C** | **SDK 真的走了我们** | 服务器 `sdk.log` 出现该设备的 `/user/quick-login` 或 `/user/login`；手机侧 `curl -s -o /dev/null -w '%{http_code}' https://example.com/sdk/` → `200` | 登录失败 = `sdk_url`/网络/证书 |
| **D** | 能登录进大厅 | 出现大厅 UI；服务端 `sdk.log` 有 `QUICK OK` | 卡密/账号 |
| **E** | 能打关卡 | 进关卡→打完结算；网关日志出现 `Campaign_*` | `Servers`/网关（state1 的 bug） |
| **F** | **付费按钮拉不起真支付**（安全） | 点付费 → **不应出现**官方收银台/优星网络二维码；应报错或无反应 | 出现了 = 止血开关没开 ⇒ **立刻停测** |

> **C 是这次测试的核心目的**：现在手机跑原厂包，`sdk.log` 里根本不会有新记录。C 一过，就证明"卡密那套开始生效了"，假支付才有验证的前提。

### 4.2 快照留证（给 Lead）

```bash
adb shell "su -c 'sha256sum /data/app/*/com.RoamingStar.BlueArchive*/base.apk'" > evidence_baseapk.sha256
adb logcat -d > evidence_logcat.txt
# 服务器侧（srv-ops 配合）：
#   grep -a 'quick-login\|QUICK OK' /<sdk.log 路径> | tail -20
```

---

## 5. 失败怎么定位（把这份抓给我 / 给 Lead）

```bash
adb logcat -c
adb shell monkey -p com.RoamingStar.BlueArchive -c android.intent.category.LAUNCHER 1
sleep 25 && adb logcat -d > ba_v2_logcat.txt
grep -iE "Curl error|UnityTls|SSLHandshake|certificate|Trust anchor|INSTALL_FAILED|airisg|SIGBUS" ba_v2_logcat.txt | head -40
```

| 症状 | 指向 | 下一步 |
|---|---|---|
| `Curl error 60` / `UnityTls error code: 7` | TLS 没过 | 但我们用真证书 ⇒ 说明**没连到我们的域名**（查 `ServerInfoDataUrl` 是否真生效） |
| `Trust anchor for certification path not found` | 同上 | 同上 |
| 登录 404 / 协议错 | `Servers` 指向 www（P0-1 没做） | 先让 srv-ops 换 state1.json |
| 卡标题画面 | ACE 完整性 | 确认 `__tpinfo` 已 0 条；清 ACE 记账重试 |
| 启动即崩、无 logcat | 被 ACE 钉住的 .so 被动过 | 不可能（v2 未改 .so）；先怀疑传输截断（§3.1 哈希） |
| `INSTALL_FAILED_UPDATE_INCOMPATIBLE` | 没卸原包 | §3.2 |
| `pm install` 报 `Failed transaction` | ksu 域被挡 | 改用 `adb install --streaming` |

---

## 6. 回滚（3 步）

```bash
# ① 卸 v2
adb shell "su -c 'pm uninstall com.RoamingStar.BlueArchive'"

# ② 装回原厂包（report\_tmp\cn_base.apk，2,126,400,085 B）
adb push cn_base.apk /data/local/tmp/cn_base.apk
adb shell "su -c 'pm install -r /data/local/tmp/cn_base.apk'"

# ③ 还原 ACE 记账（可选，一般不需要）
adb shell "su -c 'D=/data/data/com.RoamingStar.BlueArchive/files; tar xzf /sdcard/ba_ace_bak.tgz -C \$D'"
```

服务端回滚（srv-ops）：
```bash
printf '%s' '{"Servers":["https://example.com/api/"],"State":1,"Msg":""}' \
  > /www/wwwroot/bapatch/noroot_payloads/state1.json
```

---

## 7. 一句话交接

> 装之前先跑一遍 §1 的 P0-1/P0-3/P0-4 三条 curl，**三条都对了再卸包**；
> 装完先跑 §4.0 一条 `sha256sum base.apk` 确认装的是 v2（别看 `.so`），
> 再看 §4.1 的 C（服务器 `sdk.log` 有没有新记录）—— 那是这次测试唯一真正的目的。
> **手机端 8080 不用起；付费按钮点之前先确认 `cn_billing_block.txt=1`。**
