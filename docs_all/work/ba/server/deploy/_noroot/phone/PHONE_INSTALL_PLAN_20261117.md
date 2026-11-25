# 腾空间 + 装 v2 完整执行方案（**方案稿，未执行任何删除/卸载/安装**）

> 作者：phone-ops（本目录独占）
> 时间：2026-11-17 20:37–20:45 (+08:00)
> 对象：`BA_noroot_v2.apk` 2,127,971,177 B / sha256 `682A9EA2…A2EC`
> 现状：`/data` 空闲 **1.0–1.1 GB**（218 G 总量，100% 已用）

---

## 一、一句话结论

> **可回收 ≈ 3.5 G（清垃圾，不动游戏数据）+ 卸载官方包再腾 ≈ 2.0 G（apk）+ 11.1 G（外部数据）**
> **但卸载必然会删掉 `/data/data/<pkg>` 和 `/sdcard/Android/data/<pkg>` 两处 —— 这一条有本机实证（见 §2）。**
> **不想删数据的话，唯一可行路线是「改包名并行安装」，但需要 ca-researcher 重出包（约 30 分钟+）。**
> **`pm install` 通道已实测可用（不是被 binder 挡）**，且 `adb install --streaming` 也实测走通。

---

## 二、① 清点可回收空间（逐项 + 证据）

### A. `/data/local/tmp` 里的 libil2cpp 家族（**13 个文件，每个 270,927,056 B，实测 sha256 如下**）

| # | 文件 | sha256 | 判定 |
|---|---|---|---|
| 1 | `libil2cpp.before_ce.so` | `6e2edf5a3784c4c9f8aadccbf38764be24ca5961dfc88d4d07c8f12adbf751c1` | 与 2/4/12 **完全相同**，冗余 |
| 2 | `il2cpp_orig.so` | `6e2edf5a…751c1` | **同上**（同一个原厂件） |
| 3 | **`libil2cpp.factory.so`** | **`5ac1cbe0fb8f730ffd22b93624a70ae9c90b0a1f3f3fbeb18c5d6af3c73882c3`** | ★ **= 现役 APK 里的原厂 libil2cpp.so（唯一要留的原厂基准）** |
| 4 | `libil2cpp.baseline.so` | `6e2edf5a…751c1` | 冗余（同 1） |
| 5 | `libil2cpp_hook_v2.so` | `aa833eaa44666c7aaf441d8e7261de12dcc03c9462e03058c3051635fd604a4f` | 实验 hook（已废弃，曾崩） |
| 6 | `libil2cpp_hook_v3.so` | `329c3d857fa899f348b4882a24dac18a8e7519ce8b4c1020737ff581904b1e7c` | 实验 hook（已废弃，曾崩） |
| 7 | `libil2cpp_hook_v2data.so` | `28669d115cdece8d541888c79bd226a39374978cca6ee945908224dba909ab1c` | 实验 hook 附属 |
| 8 | **`libil2cpp_ce.bin`** | **`dabe3cba3f1c1fde3c04693133383c8c0b9600cc0de81ac0ea5cef504be1c3ba`** | ★ **CE 补丁版（我们唯一验证过的补丁产物，建议留）** |
| 9 | `libil2cpp_hook.so` | `11cefd6d5b89536ad588af581c7d19b85e03212a3f01319de4ed872745147b6f` | 实验 hook v1（曾崩） |
| 10 | `libil2cpp_probe.so` | `16fd1eba7e1f7e846e4bd292c3e88a0b3cf8bdd6d8aab2d941424b24ef1dce4a` | 实验探针 |
| 11 | `orig_inst.so` | `6e2edf5a…751c1` | 冗余（同 1） |
| 12 | `libil2cpp.orig_001113.so` | `a473ba16ba5baf0bbf29c48d894d6d6afcb98eb024be2ff9fea18772bea8d61f` | 11-13 旧原厂（与现役不同版本） |

**汇总：13 个文件 × 270,927,056 B = 3.52 GB**
**建议删除：第 1/2/4/11（4 份重复的 `6e2edf5a`，保留 0 份其实也行，但为稳妥留 0）、5/6/7/9/10/12（实验件）⇒ 共 10 个 ≈ 2.71 GB**
**建议保留 2 个（541.8 MB）**：
```
libil2cpp.factory.so   sha256 5ac1cbe0fb8f730ffd22b93624a70ae9c90b0a1f3f3fbeb18c5d6af3c73882c3   ← 现役原厂基准
libil2cpp_ce.bin       sha256 dabe3cba3f1c1fde3c04693133383c8c0b9600cc0de81ac0ea5cef504be1c3ba   ← 我们验证过的 CE 补丁
```
**删了会不会影响现有客户端/取证？**
- **不影响正在跑的官方客户端**：现役 lib 在 `/data/app/…/lib/arm64/libil2cpp.so`（sha `5ac1cbe0…`），与 `/data/local/tmp` 的副本无关。
- **不影响取证**：前几轮 logcat/栈/截图的产物都在 PC。
- **唯一损失**：以后要复现那几次 hook 崩溃（v1/v2/v3）会少原件 —— 但 PC 上 `report\_tmp` 里没有这些大文件，**如果你要保留审计价值，建议先把 `libil2cpp_hook_v3.so` pull 到 PC 再删**（一条 `adb pull`，270 MB）。

### B. 其他临时件（**合计 ≈ 466 MB**）
| 文件 | 大小 | 删了影响？ |
|---|---|---|
| `/data/local/tmp/ffmpeg` | 134 MB | 手机侧转码工具，**我们在 PC 上有 ffmpeg**，可删 |
| `/data/local/tmp/catalog.json` | 81 MB | 11-14 抓的目录缓存，PC 上 `work\ba\data\catalog_Remote.json` 有同源，可删 |
| `/data/local/tmp/frida-server` + `.fs1`（同一文件的副本） | 59 + 59 MB | frida 已不用（现在走 debuggerd/simpleperf），可删两个 |
| `/data/local/tmp/t50m.bin` | 50 MB | 我 11-16 的测速残留，可删 |
| `/data/local/tmp/rec60.mp4` | 45 MB | 黑屏录屏，**PC 已存 `report\_tmp\blackout2\rec60.mp4`**，可删 |
| `/data/local/tmp/global-metadata.dat` | 38 MB | 与数据目录里的重复，可删 |

### C. `/sdcard/Download` 旧件（**合计 ≈ 650 MB**，属历史/用户产物，**必须你或用户点头**）
```
patch.so                     270,927,056   11-13 19:47   （另一份 libil2cpp 副本）
iOS14Sim_P4_v4.0.apk          99,762,161   10-17 23:45   （跟 BA 无关，用户的）
mihomo                        64,007,896   11-13 02:44   （代理内核，可能还在用！）
url_region.bin                50,331,648   11-13 04:37   （抓包中间件）
meta_region.bin               20,971,520   11-13 04:36
u3.bin / u2.bin               20,951,040 / 20,500,480   11-13 04:46/04:47
tmp_tb1.zip                   19,124,224   11-13 04:25
BA_BASE.apk.idsig 等 3 个      各 16,754,155
```
**回收口径：删 `patch.so` + `url_region.bin` + `meta_region.bin` + `u2/u3.bin` + `tmp_tb1.zip` + 3 个 `.idsig` ≈ 442 MB（保留 `mihomo` 和用户的 apk）**

### ★ 可回收合计
| 项 | 大小 | 风险 |
|---|---|---|
| A. 10 个冗余 libil2cpp | **2.71 G** | 低（保留 2 个关键件） |
| B. 临时件 | **466 M** | 低 |
| C. Download 旧件 | **442 M** | 中（需批准，保留 mihomo） |
| **合计** | **≈ 3.6 G** | |

---

## 三、② 装 v2 必须先卸载官方包 —— 会不会删数据？**会，两处都删**

### 3.1 结论 + 本机实证
```
⇒ `pm uninstall <pkg>` 会删除：
   ① /data/data/com.RoamingStar.BlueArchive          （应用私有数据）
   ② /sdcard/Android/data/com.RoamingStar.BlueArchive（外部数据，Android 11+ 由系统一并删）
```
**本机实证（不是推测）**：2026-11-16 02:58 用户卸载并重装官方包后，我 03:07 立刻检查：
```
/data/media/0/Android/data/com.RoamingStar.BlueArchive  → 只剩 **22 个文件 / 53.6 MB**
   （il2cpp/*、GlobalConfig.json、LocalConfig.json、DeviceOption、PopupMessageWatchedOnce —— 全是新包首次启动自生成的）
   ⇒ 之前的 **11.1 GB / 36,538 个文件全部消失**
```
这就是"卸载会删外部数据"的直接证据。

**`pm uninstall -k` 只保留 `/data/data`（私有），外部 `/sdcard/Android/data` 仍然会被删。** 不解决问题。

### 3.2 恢复路径（10 分钟内回到"能玩"状态）
**我们的 `BA_backup` 是完整可用的：31 块 / 11,923,240,960 B (11.10 GB) / 36,538 个文件，逐文件 sha256 已在 2026-11-16 校验 36,538/36,538 全一致。**

恢复步骤（HTTP 推回，实测 15–18 MB/s ⇒ 11.1 GB ≈ **11–13 分钟**，略超 10 分钟，若走局域网 nc 反向通道约 8-10 分钟）：
```bash
# 0) 起 PC 侧下载服务（我们做过，PID 独立存活）
python BA_backup\uploader.py                                    # 监听 8901

# 1) 手机上逐块拉取并解包（tar 内路径相对 files/）
su -c 'D=/data/media/0/Android/data/com.RoamingStar.BlueArchive/files; mkdir -p $D'
for c in BA_files_block1 BA_files_block2_tablebundles BA_files_block3_misc \
         ab_c0 ab_c1 ab_c2 ab_c3 ab_c4 ab_c5 ab_c6 ab_c7 ab_c8 ab_c9 ab_c10 ab_c11 ab_c12 ab_c13 ab_c14 ab_c15 \
         mpcatalog_c0 mpcafe_c0 mpscen_c0 mpscen_c1 mpvideo_c0 mpvideo_c1 mpuis_c0 mpuis_c1 mpbgm_c0 mpvocjp_c0 mpvoc_c0 mpvoc_c1; do
  curl -sS http://192.168.0.2:8901/file/$c.tar | tar -xf - -C $D
done

# 2) 属主与目录权限（uid 会随安装变，取实际值）
su -c 'chown -R $(dumpsys package com.RoamingStar.BlueArchive | grep -m1 userId= | tr -dc 0-9):ext_data_rw $D'
su -c 'find $D -type d -exec chmod 2771 {} \;'

# 3) 校验（必须 36,538 条全一致）
su -c "cd $D && find . -type f -exec sha256sum {} +" > phone_sha.txt
# 与 BA_backup\*.sha 合并比对（我们 11-16 做过一次，36,538/36,538 全过）
```
**回滚到"能玩官方包"最快路径**（不恢复数据也基本能玩，进度在服务端）：
```bash
adb install --streaming -r -d C:\Users\su\Desktop\大肥鱼项目\BAServer\report\_tmp\cn_base.apk
```
⇒ 官方包 2,126,400,085 B / sha256 `dd30a285b58508252df09a503b025850a27a73c89f1162454bee55a60d7f83bb`（**PC 已有，已验证与手机上现役包一致**）。
装回后首次启动会自动重建 22 个基础文件、按需重新下载资源。

### 3.3 有没有办法不卸载就装？——**能，但要重建包（评估）**

| 方案 | 可行性 | 代价 | 结论 |
|---|---|---|---|
| **① 改包名并行安装**（把 v2 的 `package` 改成 `com.RoamingStar.BlueArchive2`，保留原包） | **技术上可行**（我们 11-14 做过一次：用 MT 把官方包改成 `com.RoamingStar.BlueArchiv2`，成功装上并跑过） | 需要 ca-researcher 用同一套流程重签 v2（**改 `AndroidManifest.xml` 里的 package + 相关的 authorities/权限名**，26 处字符串要同步改；约 30–60 分钟） | **最省事、零数据损失**，但**v2 可能需要按新包名重新验证 sdk_url/ACE** |
| ② 双开/应用分身（OPPO 自带） | 大概率不行（分身走同一签名+系统白名单，且分身数据独立） | 试错成本低 | 只能当兜底尝试 |
| ③ `pm install -r` 直接覆盖 | **不行**（签名不同 ⇒ `INSTALL_FAILED_UPDATE_INCOMPATIBLE`） | — | 排除 |
| ④ `pm install -r -d`（允许降级） | **不行**（-d 只解决版本号，不解决签名） | — | 排除 |

> **我的建议**：如果目标只是"验证 v2 能不能走我们的 SDK"，**改包名并行安装是最优解**（不删 11.1 G、不破坏现役官方包、可随时卸载 v2 回原状）。
> 代价是要 ca-researcher 重出一次包。**你定。**

---

## 四、③ `pm install` 的 binder 问题 —— **实测：没有被挡，通道可用**

### 4.1 三条无副作用探测（全部实测，未改动任何东西）
```
① pm uninstall com.does.not.exist.probe
   → Failure [DELETE_FAILED_INTERNAL_ERROR]
   ⇒ 不是 "Failed transaction (2147483646)"，说明 **pm 的 binder 通道在 su 域正常**

② pm install-create -S 1
   → Success: created install session [1594213081]
   ⇒ **install session 通道正常**
   pm install-abandon 1594213081
   → Success（已清理，无残留）

③ adb install --streaming -r fake_probe.apk（200 字节伪 APK）
   → Performing Streamed Install
   → Failure [INSTALL_PARSE_FAILED_NOT_APK: Failed to parse /data/app/vmdl717010215.tmp/base.apk]
   ⇒ **流式上传 → 会话 → 解包校验 全链路走通**，只在解析阶段按预期失败
   （普通 `adb install -r` 也走到同一处，说明两条路都可用）
```
**⇒ 之前"大概率被 binder 挡"的担心，在本机实测不成立。**
（历史上 `settings`/`input`/`pm list` 确实报过 `Failed transaction`，但 `pm install/uninstall` 这条路是通的。）

### 4.2 推荐命令（按优先级）
```bash
# 首选：流式安装，PC 直推，不占手机中转空间（省 2 GB！）
adb -s 192.168.0.5:5555 install --streaming -r "…\_noroot\apk\BA_noroot_v2.apk"
#   期望：Success；若返回 INSTALL_FAILED_UPDATE_INCOMPATIBLE ⇒ 说明没卸干净，回 §3 先 uninstall

# 备选 1：先推后装（要 2 GB 手机空间，空间紧张时不建议）
adb -s 192.168.0.5:5555 push BA_noroot_v2.apk /data/local/tmp/ba_v2.apk
adb -s 192.168.0.5:5555 shell "su -c 'pm install -r /data/local/tmp/ba_v2.apk'"

# 备选 2：会话三段式（手工版流式）
adb -s 192.168.0.5:5555 shell "pm install-create -r -S 2127971177"
adb -s 192.168.0.5:5555 shell "pm install-write -S 2127971177 <sessionId> base.apk -"
#   （把 apk 从 stdin 灌进去，用 adb exec-out 或 --streaming 替代）
adb -s 192.168.0.5:5555 shell "pm install-commit <sessionId>"
```

### 4.3 失败时的回退命令
| 症状 | 回退 |
|---|---|
| `INSTALL_FAILED_UPDATE_INCOMPATIBLE` | `adb shell pm uninstall com.RoamingStar.BlueArchive` → 再装 |
| `INSTALL_FAILED_INSUFFICIENT_STORAGE` | 回 §四按 ④ 重算空间，继续腾 |
| `Failed transaction (2147483646)`（万一出现） | 改用 `adb install --streaming`（本次已实测可用） |
| 安装后启动即崩 / 卡标题 | 立刻 `adb shell pm uninstall com.RoamingStar.BlueArchive` + `adb install --streaming -r -d …\cn_base.apk` 回官方包 |
| 签名/对齐错误 `INSTALL_PARSE_FAILED_*` | 说明 APK 自身有问题 → 回 ca-researcher 重出包 |

---

## 五、④ 空间需求重算（两条路线）

### 路线 1：卸载官方包（删数据）—— **空间非常充裕**
```
现在空闲                              ≈ 1.05 G
+ 清 A（10 个冗余 libil2cpp）           + 2.71 G   → 3.76 G
+ 清 B（临时件）                        + 0.47 G   → 4.23 G
+ 清 C（Download 旧件，需批准）          + 0.44 G   → 4.67 G
+ 卸载官方包：/data/app 里的 apk+libs    + ≈ 2.0 G → 6.67 G
+ 卸载同时删掉外部数据                    + 11.1 G  → **≈ 17.8 G**
⇒ **装 1.98 GB 的 v2 + 首次启动解包/资源展开，绰绰有余**
   （即使不删外部数据，6.67 G 也 > 6 G 的安全线）
```
⚠️ 但注意：**卸载后如果要恢复那 11.1 GB 数据，需要 11.1 G 空间**；17.8 G 够，但恢复完只剩 ~6.7 G。

### 路线 2：改包名并行安装（不删数据）—— **空间刚好够，但很紧**
```
现在空闲                              ≈ 1.05 G
+ 清 A + B + C                         + 3.62 G  → **≈ 4.67 G**
需要：v2 apk 1.98 G（流式安装时系统仍需在 /data/app 解包 ≈ 2.0 G）
⇒ 峰值需求 ≈ 4.0–4.2 G  **< 4.67 G，勉强够，但没有余量**
⇒ 建议再删 `libil2cpp.factory.so`+`libil2cpp_ce.bin`（541 M，可先 pull 到 PC 再删）→ 5.2 G，就比较安全
```
**⇒ 路线 2 在"清 A+B+C"后可行（余量 ~0.5 G，偏紧）；路线 1 余量巨大。**

---

## 六、我的建议（等你拍板，不动手）

```
优先级 1（推荐）：路线 2「改包名并行安装」
  优点：不删 11.1 G 数据、不动现役官方包、失败零成本
  代价：等 ca-researcher 重出包（30-60 min）
  前提：先清 A+B（3.18 G，不用清 Download），可用 ≈ 4.2 G

优先级 2：路线 1「卸载官方包 → 装 v2」
  优点：立刻能做，空间极充裕
  代价：删掉 11.1 G 数据（可从 BA_backup 恢复，11-13 分钟）；数据恢复前游戏需要重新下载资源
  前提：你批准"可删数据"，并接受恢复窗口

优先级 3：先只做「清理 A+B」（安全、可逆、不删任何唯一件）
  腾出 3.18 G → 空闲 ≈ 4.2 G，为两条路线都做好准备
```

---

## 七、本轮边界
```
✅ 只读：ls / du / sha256sum / pm install-create+abandon（空会话）/ pm uninstall 不存在的包 / adb install 伪 APK（解析失败）
❌ 没有删除任何文件、没有卸载任何包、没有安装任何包、没有 pull/push 大文件
```
