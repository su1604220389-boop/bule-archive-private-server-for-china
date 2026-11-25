# 能否拿到手机端 logcat —— 可行性核查（2026-11-19 01:25）

> 执行：phone-ops
> 时间：2026-11-19 01:25–01:31 (+08:00)
> 性质：**只读核查**。没有改 APK / 没有重打包 / 没有动游戏文件 / 没有清数据 / 没有装模块 / 没有启动或点击游戏。

---

## 结论（先说）

**❌ 现在拿不到 logcat。** 原因只有一个：**没有任何设备对 adb 可见**。

```
adb devices -l →  List of devices attached  （空，一台都没有）
USB     ：当前插着的设备里 **没有** Android ADB Interface / 便携设备(WPD)；
          PnP 里能查到历史记录 `PHK110`、`一加 Ace 2`、`ADB Interface`，但状态都是 **Unknown（= 设备不在场）**
无线    ：192.168.0.5 / 192.168.0.6 都能 ping 通，但 **:5555 均关闭**
          `adb mdns services` → 空（Windows 侧 mDNS 未发现 `_adb-tls-connect._tcp`）
```

---

## 1) adb 路径与版本

```
C:\WINDOWS\system32\adb.exe        5,977,600 B   ← PATH 里的就是它（Get-Command adb 解析到它）
Android Debug Bridge version 1.0.41
Version 33.0.0-8141338

C:\Users\su\AppData\Local\Android\Sdk\platform-tools\adb.exe   **不存在**（本机没装 Android Studio 的 platform-tools）
```
（已执行 `adb kill-server` / `adb start-server` 重启服务，仍无设备）

## 2) 设备状态

| 检查项 | 结果 |
|---|---|
| `adb devices -l` | **空** |
| USB 当前在场设备 | 只有键鼠/读卡器/U 盘/罗技/AURA LED 等，**无 Android ADB Interface、无 WPD 便携设备** |
| PnP 历史记录 | `PHK110`、`一加 Ace 2`（WPD，**Unknown**）、`Android ADB Interface`（**Unknown**）、`Android Bootloader Interface`（**Unknown**） |
| 无线 192.168.0.6 | ping ✅ / `:5555` ❌ / `:18080` ❌ |
| 无线 192.168.0.5 | ping ✅ / `:5555` ❌（`:18080` TCP 可连但**不回数据**，busybox tcpsvd 已挂，取不到 shell） |
| `adb mdns services` | 空 |
| 本机网段 | `192.168.0.2`（以太网），与手机同段 |

**是否 root**：**无法判定**（设备连不上，`adb shell id` 跑不了）。历史实测该机为**无 root**（`which su` → NO_SU_FOUND，`/system/bin/su` 等不存在，`ro.debuggable=0`）。

## 3) 是否无线可连

**当前不可连**。要走无线调试，必须**在手机上主动点「使用配对码配对设备」**，把那一刻显示的 **配对端口 + 6 位配对码** 给出来；没有这两个值，`adb pair` 无法进行（这一步不能猜、不能试）。

## 4) 实际抓到的日志

**没有抓到任何日志**（一个字节都没抓，因为无设备）。

## 5) 关键词命中摘录

**无**（无日志可 grep）。关键词清单已备好，一旦有日志立刻跑：
```
LocalizeKey | Localize | Gacha | Recruit | ShopRecruit | Excel | ExcelDB | TableManifest |
NullReference | Exception | missing | not found
```

---

## 6) 下一步：需要用户在手机上做的（二选一，都只需几步）

### 方案 A：USB（最省事，推荐）
```
1. 用数据线把手机连到这台电脑（USB 口）
2. 手机上弹出的「USB 用途」选 **传输文件 / MTP**（不要选"仅充电"）
3. 设置 → 关于手机 → 连点「版本号」7 次（若开发者选项已开可跳过）
4. 设置 → 系统 → 开发者选项 → 打开 **USB 调试**
5. 手机上弹出「允许 USB 调试吗？」→ 勾选「一律允许」→ **允许**
6. 告诉我一声，我这边 `adb devices` 就能看到
```

### 方案 B：无线调试（不用线，但要配对码）
```
1. 设置 → 系统 → 开发者选项 → **无线调试** → 打开
2. 点「**使用配对码配对设备**」，屏幕会显示：**IP:端口** 和 **6 位配对码**
3. 把这三个值发我：**配对端口**、**配对码**（IP 一般是 192.168.0.6）
4. 我执行 `adb pair`，配对成功后 `adb devices` 里会出现设备
```

### 如果两个方案都不方便：抓 Bug report（次优，但**能拿到系统+应用日志**）
```
1. 设置 → 系统 → 开发者选项 → **生成错误报告（Bug report）** → 选「互动式报告」或「完整报告」
2. 等它生成（约 1–3 分钟），完成后手机会提示分享
3. 把 zip 发回来（几百 MB，里面含 logcat 全量 + dumpsys）
4. ⚠️ 生成过程中**不要去动游戏进程**（不要切后台、不要清数据、不要强杀）
```

---

## 7) 拿到 logcat 后我会怎么做（已备好，不用改任何东西）

```
① adb -s <serial> logcat -c
② adb -s <serial> logcat -d -v time -b all > <本地>\logcat_full_<HHmmss>.txt      # 先抓当前缓冲区
③ adb -s <serial> logcat -d -s Unity:V CRASH:V AndroidRuntime:E DEBUG:V > <本地>\logcat_unity.txt
④ 在两个文件里 grep 上面的关键词，命中行 ±30 行上下文
⑤ 落盘目录：work\ba\phone\logs\（Windows 本地，不写手机）
```
**预期**：这台机历史实测**release 包几乎不打 Unity 日志**（多次抓全量 50–106 MB 里游戏进程 0 条），
所以 `LocalizeKey` 这类字符串**大概率不在 logcat 里**。若确认如此（⑤ 全空），结论就是：
**客户端日志拿不到 → 必须换 Bug report（含 dumpsys）或换 `-s` 之外的证据（抓包/内存扫描）**。
我不会在拿到日志之前预设结论。

---

## 附：本次执行过的命令（全部只读/无副作用）

```
Get-Command adb ; adb version
Test-Path C:\Users\su\AppData\Local\Android\Sdk\platform-tools\adb.exe
adb kill-server ; adb start-server ; adb devices -l ; adb mdns services
Test-Connection 192.168.0.5 / 192.168.0.6 (ping)
Test-NetConnection 192.168.0.5:5555 / 192.168.0.6:5555
Get-PnpDevice (-PresentOnly) 过滤 USB / AndroidUsbDeviceClass / WPD
Get-NetIPAddress (查本机网段)
```
**没有对手机做任何写操作**（也无从做，设备未连接）。
