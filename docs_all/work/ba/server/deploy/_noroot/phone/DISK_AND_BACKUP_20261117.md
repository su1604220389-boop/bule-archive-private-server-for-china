# 磁盘与备份核对（DISK_AND_BACKUP_20261117）

> 作者：phone-ops（本目录独占）
> 时间：2026-11-17 20:47–20:55 (+08:00)
> 性质：**全部只读，未删除任何东西**

---

## ★ 最重要的一条（先看）

**那 11.1 GB 资源备份不在手机上，在电脑上。**
手机全盘 `find / -maxdepth 4 -type d -name 'BA_backup*'` → **零结果**；`find /data /sdcard -name '*.tar' -size +1G` → **零结果**。
**备份就是 `C:\Users\su\Desktop\大肥鱼项目\BA_backup\`：31 个 tar / 11,923,240,960 B (11.104 GB) / 34 个 `.sha` / `MANIFEST.txt` / `tars.sha256` / `verify_result.json`。**

**⇒ 所以"删手机上的数据腾空间"这条路是**通的** —— 手机上不存在第二份副本，删掉就是净腾出 11.1 G。**
（Lead 说"电脑上没有"，这与我这边不符：**我在 PC 上就在 `C:\...\BA_backup\` 里，31 块、11.104 GB、校验齐全**，见 §3。）

---

## ① `BA_backup` 在哪

```
$ adb shell su -c "find / -maxdepth 4 -type d -name 'BA_backup*' 2>/dev/null"
（无输出）

$ adb shell su -c "find /data /sdcard -maxdepth 4 -name '*.tar' -size +1G"
（无输出）
```
**⇒ 手机上没有任何 BA 备份副本。**

PC 侧（实测）：
```
路径：C:\Users\su\Desktop\大肥鱼项目\BA_backup\
tar 块数：**31**
合计：**11,923,240,960 B = 11.104 GB**
```

---

## ② 分区关系：`/data` 与 `/sdcard` **是同一个分区**

```
$ adb shell df -h /data /storage/emulated/0
/dev/block/dm-50   218G   217G   1.1G   100%   /data/local/tmp/sys-ca-copy   ← /data
/dev/fuse          218G   217G   1.1G   100%   /mnt/installer/0/emulated     ← /sdcard 视图

$ adb shell df -k /data | tail -1
/dev/block/dm-50   228531260   227294720   1105468   100%   /data

$ adb shell mount | grep -E ' /data | /mnt/pass_through/0/emulated '
/dev/block/dm-50 on /data type f2fs (...)
/dev/block/dm-50 on /mnt/pass_through/0/emulated type f2fs (...)   ← 同一块设备
```
**⇒ `/sdcard`（`/storage/emulated/0`）是 `/data` 上的 FUSE 视图，同一块 f2fs（dm-50），共享同一个空间池。**
**⇒ 在 `/sdcard` 上做备份不会腾出空间；但我们的备份在 PC，不受此限制。**

⚠️ 顺带纠正我上一份方案里的一处含糊：`/data/local/tmp` 也在同一分区 ⇒ 清临时件、删 libil2cpp 副本，**能真的腾空间**（这点是对的）。

---

## ③ 31 块是不是真完整 —— **完整，且有校验**

```
$ ls C:\...\BA_backup\*.tar | wc -l
31

总大小：11,923,240,960 B（11.104 GB）

校验文件：
  ✅ MANIFEST.txt        7,540 B   ← 31 行块记录 + 合计 + 恢复说明
  ✅ tars.sha256         2,490 B   ← 31 条"每块 tar 的 sha256"
  ✅ verify_result.json  4,012 B   ← 机器可读的逐块校验结果
  ✅ *.sha               34 个     ← 每块内逐文件 sha256（共 36,536 条）
```
**抽查 2 块的 tar 头（确认不是空文件/截断）**：
```
BA_files_block1.tar   size=157,901,312   首成员='manifest.db'             magic='ustar'  ✅
ab_c15.tar            size=282,555,392   首成员='AssetBundles/timelin…'   magic='ustar'  ✅
```
**tars.sha256 前 3 条（可用于比对）**：
```
f3bbd3b7b177076717d26c5a52eb37bbf6e9d6d74c766f79fe5465785cc0145b  BA_files_block1.tar
3cf865c4e5428d05500c6977fe179f505829d4f0621251b60726c42f2075061b  BA_files_block2_tablebundles.tar
bfeb96425cadf24c84ba0ca608dc804581e5d247ad55d68ffda5c16fc0a57070  BA_files_block3_misc.tar
```
**结论**：**31 块 / 11.104 GB / 有校验（每块 tar 的 sha256 + 每块内逐文件 sha256 + MANIFEST + verify_result.json）/ 抽查头部正常 ⇒ 可确认完整**。
（2026-11-16 恢复时实测："一致 36,536 / 不一致 0 / 缺失 0"，另有 2 个 Catalog 文件单独核验一致 ⇒ 36,538/36,538。）

---

## ④ 那 11.1 G 具体是什么 —— **99.9% 是可重下的资源，账号数据只有 9.8 MB**

### 4.1 `/data/data/com.RoamingStar.BlueArchive`（私有目录）—— **合计 9.8 M / 245 个文件**
```
  216.0K  shared_prefs        ← ★ 账号/登录态（不可重下）
   95.5K  databases           ← ★ 本地库（建议备份）
    4.0M  no_backup           ← ACE 记账(ace_shell_di.dat 22 B)、ano_tmp、Adjust、UdataSdk
    2.8M  files
    2.4M  cache               ← 可重下/可丢
  301.5K  app_webview         ← 内置网页缓存，可丢
  3.5K ×4 app_DUHOME / app_databases / app_textures / code_cache
   11.5K  app_[THEMIS]
```
**★ 不可重下的账号相关文件（shared_prefs 全清单，共 9 个）**：
```
0a978976f84781d9c6f77a49c397e572.xml    220 B   19:59
ALITX_LOGGER_DATA.xml                   221 B   11-16 03:59
AUTH_APP_INFO.xml                     2,299 B   18:17   ← 登录态
AUTH_UT_DATA.xml                      1,895 B   11-16 03:59
Alvin2.xml                              130 B   20:00
AwOriginVisitLoggerPrefs.xml             404 B   20:00
ContextData.xml                          176 B   20:00
Push_Page_Config.xml                     287 B   20:01
TapSdkCore_SP.xml                        155 B   11-16 03:06
```
**⇒ 这一整个目录（9.8 M，245 文件）才是"删了就永久丢"的东西；打一个 tar 只有 ~5 MB。**

### 4.2 `/sdcard/Android/data/com.RoamingStar.BlueArchive` —— **11.1 G**
```
11.1G  files/                 ← ★ 全部是资源：AssetBundles / MediaPatch / TableBundles / il2cpp / 各种 catalog
995.5K cache/                 ← 可丢
```
`files/` 里面的构成（11-16 恢复时的实测）：
```
AssetBundles 6.50 G / 24,161 文件
MediaPatch   4.00 G /  6,041 文件
TableBundles 0.44 G /  6,233 文件
其余（catalog_Remote.* / il2cpp / manifest*.db / 存档小文件）≈ 0.16 G
其中的 ClientSaveData/ 是**本地存档**（52 个 .save，含 10015354380* 24 个）—— 体积小但严格说"删了会丢"
```
**分类判定**：
| 内容 | 大小 | 删了能重下吗 | 处置 |
|---|---|---|---|
| `AssetBundles` / `MediaPatch` / `TableBundles` / `catalog_Remote.*` / `manifest*.db` / `il2cpp` | **≈ 11.0 G** | **能**（客户端启动后从 CDN 重新下载） | **可删**（想快点可以之后用 BA_backup 恢复） |
| `files/ClientSaveData/*.save`（52 个） | 几百 KB | 部分能（服务端有进度；本地设置类会重置） | 建议并入小 tar 一起备份 |
| `/data/data/…` 整个私有目录 | 9.8 M | 部分能（登录态/ACE 记账不能） | **必须备份**（tar 后 ~5 MB） |

**⇒ 结论：11.1 G 里真正"删了就永久丢"的只有几百 KB 的存档 + 9.8 M 私有目录。**

---

## ⑤ 可回收项逐项清单（含"要留哪个"）

### A. `/data/local/tmp` 的 libil2cpp 家族（**13 个 × 270,927,056 B = 3.52 G**）
| 路径 | sha256 | 处置 |
|---|---|---|
| `/data/local/tmp/libil2cpp.before_ce.so` | `6e2edf5a…751c1` | **删**（4 份重复之一） |
| `/data/local/tmp/il2cpp_orig.so` | `6e2edf5a…751c1` | **删**（重复） |
| `/data/local/tmp/libil2cpp.baseline.so` | `6e2edf5a…751c1` | **删**（重复） |
| `/data/local/tmp/orig_inst.so` | `6e2edf5a…751c1` | **删**（重复） |
| **`/data/local/tmp/libil2cpp.factory.so`** | **`5ac1cbe0fb8f730ffd22b93624a70ae9c90b0a1f3f3fbeb18c5d6af3c73882c3`** | **留**（= 现役 APK 里的原厂 lib） |
| **`/data/local/tmp/libil2cpp_ce.bin`** | **`dabe3cba3f1c1fde3c04693133383c8c0b9600cc0de81ac0ea5cef504be1c3ba`** | **留**（我们验证过的 CE 补丁） |
| `/data/local/tmp/libil2cpp_hook_v2.so` | `aa833eaa…4a4f` | **删**（曾崩） |
| `/data/local/tmp/libil2cpp_hook_v3.so` | `329c3d85…1e7c` | **删**（曾崩；如需审计先 `adb pull` 270 M 到 PC） |
| `/data/local/tmp/libil2cpp_hook_v2data.so` | `28669d11…9ab1c` | **删** |
| `/data/local/tmp/libil2cpp_hook.so` | `11cefd6d…b6f` | **删**（v1，曾崩） |
| `/data/local/tmp/libil2cpp_probe.so` | `16fd1eba…ce4a` | **删**（探针） |
| `/data/local/tmp/libil2cpp.orig_001113.so` | `a473ba16…d61f` | **删**（11-13 旧版本，非现役） |

**删 11 个 = 2,980,197,616 B ≈ 2.78 G；留 2 个 = 541,854,112 B ≈ 0.50 G**
**影响评估**：现役客户端用的是 `/data/app/…/lib/arm64/libil2cpp.so`（sha `5ac1cbe0…`，与 factory 副本相同）⇒ **删这些副本不影响运行、不影响取证**（取证产物都在 PC）。

### B. 其他临时件（**466 M**）
```
/data/local/tmp/ffmpeg                 134,312,680   ← PC 有 ffmpeg，删
/data/local/tmp/catalog.json            81,313,204   ← PC 有同源，删
/data/local/tmp/frida-server            59,175,728   ← 已不用（改 debuggerd/simpleperf），删
/data/local/tmp/.fs1                    59,175,728   ← 上面那个的副本，删
/data/local/tmp/t50m.bin                52,428,800   ← 11-16 测速残留，删
/data/local/tmp/rec60.mp4               45,486,780   ← PC 已存 report\_tmp\blackout2\rec60.mp4，删
/data/local/tmp/global-metadata.dat     38,426,024   ← 与数据目录重复，删
```
**影响**：全部为零（PC 有替代或已废弃）。

### C. `/sdcard/Download` 旧件（**≈442 M，需你/用户批准**）
```
/sdcard/Download/patch.so             270,927,056   ← 又一份 lib 副本，删
/sdcard/Download/url_region.bin        50,331,648
/sdcard/Download/meta_region.bin       20,971,520
/sdcard/Download/u3.bin                20,951,040
/sdcard/Download/u2.bin                20,500,480
/sdcard/Download/tmp_tb1.zip           19,124,224
/sdcard/Download/BA_BASE.apk.idsig     16,754,155
/sdcard/Download/BA_E28.apk.idsig      16,754,155
/sdcard/Download/BA_E32.apk.idsig      16,754,155
—— 保留：mihomo 64,007,896（代理内核，可能还在用）、iOS14Sim_P4_v4.0.apk 99,762,161（用户的）
```
**影响**：这些都是抓包/打补丁时代的中间件，删了不影响现役客户端；但属历史产物，**要你点头**。

### ★ 可回收合计
```
A 删 11 个 libil2cpp    2.78 G
B 临时件                0.466 G
C Download（需批准）    0.442 G
──────────────────────────────
合计                    **≈ 3.69 G**
```

---

## ⑥ 空间测算

### 现状
```
/data: 总 228,531,260 KB (218 G)，已用 227,294,720 KB，**可用 1,105,468 KB ≈ 1.05 G**（100%）
```

### 删后预计空闲
| 动作 | 累计可用 |
|---|---|
| 现状 | **1.05 G** |
| + 清 A（11 个副本） | 3.83 G |
| + 清 B（临时件） | **4.30 G** |
| + 清 C（Download，需批准） | **4.74 G** |
| + 卸载官方包（/data/app 里的 apk+解包 libs） | **≈ 6.7 G** |
| + 卸载同时删掉外部数据 11.1 G | **≈ 17.8 G** |

### 够不够装 1.98 G 的 v2？
```
只清 A+B（4.30 G 可用）：
   v2 apk 1.98 G + 系统在 /data/app 解包后的 lib/oat ≈ 2.0 G ⇒ 峰值 ≈ 4.0 G
   **勉强够（余量 ~0.3 G），但没有任何缓冲** —— 官方包还在，数据也还在
清 A+B+C（4.74 G）：
   峰值 4.0 G ⇒ 余量 ~0.7 G，**可行**
卸载官方包后（≥6.7 G）：
   余量 ≥2.7 G，**很安全**
```

---

## ⑦ 一句话结论 + 建议动作

> **备份在 PC（`C:\...\BA_backup\`，31 块 / 11.104 GB / 校验齐全），手机上没有第二份 ⇒ 删手机数据是净腾空间。**
> **`/data` 与 `/sdcard` 同一分区（dm-50），但在 sdcard 上放备份这条路我们没走、也不需要。**
> **11.1 G 里 99.9% 是可重下的资源；真正"删了就丢"的只有 `/data/data/…` 的 9.8 M（含 AUTH_APP_INFO.xml 登录态）+ `ClientSaveData` 几百 KB。**

**建议顺序（等你点头，我不动手）**：
```
第 0 步（零风险，建议先做）：把 /data/data/… 整包 + ClientSaveData 打成一个小 tar（≈5-8 MB）pull 到 PC
                 —— 这样"删了就永久丢"的东西就先落到 PC 了，之后怎么腾空间都不怕
第 1 步：清 A（2.78 G）+ B（0.47 G） → 可用 ≈ 4.30 G（不删任何唯一件）
第 2 步：视路线决定
   · 走"改包名并行安装"：需 4.74 G（再清 C），余量偏紧但可行
   · 走"卸载官方包装 v2"：直接可用 ≈6.7 G（不删数据）或 ≈17.8 G（连数据一起删）
```

---

## 边界
```
✅ 只读：find / df / mount / du / ls / sha256sum（PC 侧）/ tar 头抽查（只读 512 字节）
❌ 没有删除任何文件、没有卸载、没有安装、没有改任何东西
```
