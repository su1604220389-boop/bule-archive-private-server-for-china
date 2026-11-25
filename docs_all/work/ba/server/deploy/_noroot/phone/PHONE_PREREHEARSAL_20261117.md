# 装机空跑预演报告（PHONE_PREREHEARSAL_20261117）

> 执行：phone-ops（本目录独占）
> 时间：2026-11-17 20:31–20:35 (+08:00)
> 性质：**只读预演。未 push、未 pull 大文件、未装、未卸、未改任何东西。**
> 被测产物：`BA_noroot_v2.apk` = 2,127,971,177 B / sha256 `682A9EA2…A2EC`（文件已在 `_noroot\apk\`，2,127,971,177 B 已核对）
> 检查单：`_noroot\apk\PHONE_INSTALL_CHECKLIST_20261117.md`（203 行，已通读）

---

# ★ 结论先说

**现在不能装。有 1 个硬阻塞：`/data` 只剩 1.0–1.1 GB（100% 已用），而装机至少要 6 GB 空闲。**
其余各项（通道、基线哈希、备份落点规划、检查单可执行性）都通过或有可绕过的小问题。

---

## ① 通道 —— **通**

```
$ adb devices -l
192.168.0.5:5555   device product:PLR110 model:PLR110 device:OP6117L1 transport_id:3

$ adb shell getprop ro.product.model / ro.build.version.release
PLR110 / 17

$ adb shell pm path com.RoamingStar.BlueArchive
package:/data/app/~~2xgRssuvhsk2wBPdAcLoAg==/com.RoamingStar.BlueArchive-HO-giOdeRyKWibiIJsCg_A==/base.apk
```
- adb 版本 PC 侧 1.0.41 / 33.0.0-8141338（**支持 `--streaming`**，检查单 §3.4 方式二可用）
- root 可用：`adb shell su -c id` → `uid=0(root) … u:r:ksu:s0`
- 18080 root shell 作为备用通道同时在线
- ⚠️ 今天 adbd 已自行掉线两次；掉线后用 18080 执行 `setprop ctl.start adbd` 即可（`/data/misc/adb/adb_keys` 已含本机公钥，无需用户点确认）

---

## ② 现役 base.apk 基线（回滚判据）—— **已记录**

```
路径：/data/app/~~2xgRssuvhsk2wBPdAcLoAg==/com.RoamingStar.BlueArchive-HO-giOdeRyKWibiIJsCg_A==/base.apk
大小：2,126,400,085 B
时间：2026-11-16 02:58:44

sha256 = dd30a285b58508252df09a503b025850a27a73c89f1162454bee55a60d7f83bb
```
**对照 v2 期望值 `682a9ea20dd9c9ec955454acd937e2a8c002f13ec7b6b1307112b3c61d4ea2ec`：**
**⇒ 两者不同（符合预期：现在装的是原厂包）。**
**⇒ 装机后必须变成 `682a9ea2…`；这条是唯一判据（检查单 §4.0 的说法正确，不能用 libil2cpp.so 判断）。**

补充旁证（装机前）：现役 `libil2cpp.so` = `5ac1cbe0…`（factory 原厂），与 v2 "未改任何 .so" 的说法一致。

---

## ③ 空间 —— **硬阻塞**

```
$ adb shell df -h /data
/dev/block/dm-50   218G   217G   **1.1G**   100%
```
**可用仅 1.0–1.1 GB，而检查单要求 ≥6 GB。**

### 空间去哪了（实测占用）
| 位置 | 大小 | 说明 |
|---|---|---|
| `/data/local/tmp` | **5.0 G** | 主要是 12 个 `libil2cpp*.so`/`il2cpp_orig.so`/`orig_inst.so`（每个 270,927,056 B ⇒ **合计 2.8 G**）+ ffmpeg 134 M + catalog.json 81 M + frida-server 59 M + `.fs1` 59 M + t50m.bin 50 M + rec60.mp4 45 M + global-metadata.dat 38 M（**这些合计 449 M**）|
| `/data/media/0/Android/data/com.RoamingStar.BlueArchive` | 11.1 G | 游戏数据（**不能删**）|
| `/sdcard/Download` | **8.6 G** | patch.so 270 M、iOS14Sim 99 M、mihomo 64 M、url_region.bin 50 M、meta_region 21 M、u3/u2.bin 各 20 M、tmp_tb1.zip 19 M、多个 `*.apk.idsig` 各 16.7 M … |

### 可回收清单（**需要你点头我才会删**）
| 方案 | 可回收 | 风险 |
|---|---|---|
| **A. 删我自己的 10 个冗余 libil2cpp 副本**（保留 `libil2cpp.factory.so` + `libil2cpp_ce.bin` 两个即可） | **≈ 2.4 G** | 低（都是我 11-13/11-14 的实验副本，原厂件在 APK 里随时可再取） |
| **B. 删临时件**：ffmpeg(134M)、catalog.json(81M)、frida-server+`.fs1`(118M)、t50m.bin(50M)、rec60.mp4(45M)、global-metadata.dat(38M) | **≈ 466 M** | 低（都是调试遗留；frida-server 若还要用就先留） |
| **C. 清 `/sdcard/Download` 里的旧 APK/中间件**（patch.so 270M、iOS14Sim 99M、mihomo 64M、url_region/meta_region/u2/u3/tmp_tb1 ≈ 131M、若干 .idsig ≈ 84M） | **≈ 650 M** | 中（属用户/历史产物，**必须你或用户同意**） |
| **D. 先把游戏数据（11.1 G）搬去 PC 再清空** | 11 G+ | 高（要重新导入，且我们已有 `BA_backup` 31 块完整备份 + sha256 清单，可行性中等） |

**A+B 合计 ≈ 2.9 G ⇒ 装完系统后可用 ~4 G，仍不够 6 G。**
**A+B+C 合计 ≈ 3.5 G ⇒ 可用 ~4.6 G，仍偏紧。**
**要真正满足 6 G，必须动 D（搬走游戏数据）或者用户自己清其它大目录。**
> 现实建议：**装机其实只需要 ~4 GB**（push 2.0 G 的 apk + 安装时解包 ~2.0 G）；
> 6 GB 是保守值。**如果按 4 GB 口径**，A+B+C 就够；**按 6 GB 口径不够**。这条请你定口径。

---

## ④ 备份落点 —— **都能落地，但都受同一个磁盘限制**

| # | 备份对象 | 体积 | 落点 | 够不够 |
|---|---|---|---|---|
| ① | 现役 base.apk | 2.13 G | **不落手机**，PC 已有 `report\_tmp\cn_base.apk`（2,126,400,085 B，sha256 `dd30a285…` 已核对一致） | ✅ 无需占手机空间 |
| ② | `/data/data/…` 整包 tar | 需实测（app 私有目录，含 webview 缓存） | `/data/local/tmp/` 或 PC | ⚠️ 空间不足时先 pull 到 PC |
| ③ | `/sdcard/Android/data/…/files` | **11.1 G** | 已在 PC：`BA_backup\` 31 块 11.10 GB + `MANIFEST.txt` + 逐文件 sha256（2026-11-16 完成并校验 36,538/36,538 全一致） | ✅ **无需再备份一次** |
| ④ | PRoot `/root/bapatch`（sdkcard.py / cards.json / sdk_resp/） | 小（sdk_resp 里 common_agreement.json 1.1 M、client-code 23 K 等，合计 < 2 M） | PC `_noroot\phone\backup\` | ✅ 空间无压力（pull 到 PC） |
| ⑤ | shared_prefs 账号相关 | < 100 K | PC `_noroot\phone\backup\` | ✅ |

**⇒ ②③ 是唯一有体积压力的两项。**
- **③ 已被现有 `BA_backup` 完整覆盖**（31 块 / 11.10 GB / 36,538 文件 / 逐文件 sha256 全一致），**建议不再重复打包**，直接复用；省 11 G。
- **② 建议按"先 pull 到 PC"处理**（app 私有目录通常几十~几百 MB；先量体积再决定）。
> ⚠️ 检查单 §2 第 ④ 条写的是 `cp -a …/files /sdcard/ba_files_bak` —— **在 11.1 G 数据 + 仅 1.1 G 空闲的情况下必然失败**，这是我标出的第一处执行风险。

---

## ⑤ 检查单通读 —— 已读 203 行，标出 6 处风险

| # | 位置 | 问题 | 建议 |
|---|---|---|---|
| **1** | §2 ④ `cp -a files /sdcard/ba_files_bak` | 需要 11.1 G，当前只剩 1.1 G，**必然失败** | 跳过；直接复用 `BA_backup\` 的 31 块备份 |
| **2** | §3.1 `adb push BA_noroot_v2.apk /data/local/tmp/ba_v2.apk` | push 本身就要 2.0 G，**当前空间不够，会 push 到一半写满** | 先腾空间再 push；push 后必须 `sha256sum` 校验 |
| **3** | §3.2 `adb uninstall` → 若失败改用 `pm uninstall` | 我们这台设备用 **root 域 su** 时 `pm`/`settings`/`input` 常报 `Failed transaction (2147483646)`（历史实测多次）→ **`su -c pm uninstall` 很可能失败** | 优先用 **shell 域**：`adb shell pm uninstall com.RoamingStar.BlueArchive`（不加 su）；失败再试 `su -c` |
| **4** | §3.4 `su -c 'pm install -r …'` | 同上，ksu 域 binder 可能被挡 | 优先 `adb install --streaming -r <本地 apk>`（PC 直推，不占手机中转盘、还省 2 G 空间）——**这同时解决风险 2** |
| **5** | §4.0 `unzip -l base.apk \| grep -c tpinfo` | 手机上有 `/system/bin/unzip`（存在），但 `su -c 'cd /data/app/*/…   && unzip -l base.apk'` 里的通配符在 su 环境中展开可能失败 | 改成 `su -c 'unzip -l $(ls /data/app/*/com.RoamingStar.BlueArchive*/base.apk)'`，或干脆在 PC 上对本地 v2 apk 做同样的 `unzip -l \| grep -c tpinfo` |
| **6** | §5 `adb logcat -d > ba_v2_logcat.txt` 之后 `grep Curl error…` | 经验：release 包 Unity 日志基本是空的（前几轮 12,105 行全量 logcat 里 0 条 AssetBundle/Exception），**这里大概率 grep 不到东西** | 保留该步，但别把"grep 为空"当成"没问题"；真正的判据仍是 §4.1 的 A–F 与服务器 `sdk.log` |

**另外 3 处只是提示，不算风险：**
- 检查单 §1 的 P0-5「手机通道」现已 **✅（我这轮确认）**；P0-6「游戏没在跑」：**现在 `pidof` 为空 ✅**
- 检查单说「手机端 8080 不用起」——**与我 ① 的结论一致**（v2 的 sdk_url 指公网 `example.com`，服务器 nginx → 服务器本地 8080），**手机端确实不需要 PRoot/8080**
- 检查单说「不能用 libil2cpp.so 判断」——**正确**，v2 未改 .so

---

## ⑥ 我预测最可能失败的两步（按概率排序）

1. **空间（必然发生）**：不腾出空间，`adb push` 会写到一半报 `No space left on device`，APK 变成截断文件。
   → 缓解：用 `adb install --streaming`（PC 直推、不在手机落中转文件），可把需求从 ~4 G 降到 ~2.2 G（安装时仍需解包空间）。
2. **`su -c pm …` 被 binder 挡**（本设备历史高频）。
   → 缓解：一律优先 shell 域：`adb shell pm uninstall` / `adb install --streaming`。

---

## ⑦ 一句结论

> **现在不能装。唯一硬阻塞是 `/data` 只剩 1.0–1.1 GB（要求 ≥6 GB，按紧口径也需 ≥4 GB）。**
> **通道 ✅、基线 sha256 已记录 `dd30a285…`、备份落点 ✅（③ 复用 BA_backup、④⑤ pull 到 PC）、检查单 6 处风险已标注。**
> **给我一句"允许清理 A+B+C"（≈3.5 G）或"允许动游戏数据（D）"，我就先腾空间再报一次空闲值，然后等你的 `pm install` 指令。**

---

## 边界
```
✅ 本轮只读：adb devices / getprop / pm path / df / du / ls / sha256sum / 读检查单
❌ 没有 push、没有 pull 大文件、没有 pm install / uninstall、没有改任何文件
```
