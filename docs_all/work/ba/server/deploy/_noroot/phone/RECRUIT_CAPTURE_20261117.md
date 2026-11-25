# 招募界面现场取证（RECRUIT_CAPTURE_20261117）

> 作者：phone-ops（本目录独占）
> 时间：2026-11-17 20:57:03 与 20:57:06（两张，间隔 3 秒）
> 设备：PLR110 / adb 192.168.0.5:5555 / 游戏进程 **pid 15844**（取证时**运行中**）
> 性质：**只读**。未点屏幕、未杀进程、未清缓存、未重启游戏、未改任何文件。

---

## 一、截图（两张）

```
work\ba\server\deploy\_noroot\phone\captures\recruit1_20261117_205703.png   1,971,202 B   sha256 aed97da8c46cceae11e87d885991ea292ed0def66ea1a857ef48a228b29671a5
work\ba\server\deploy\_noroot\phone\captures\recruit2_20261117_205703.png   1,226,983 B   sha256 eb5067f05ce4677c469738f0d90112d3e74059c1b9160adf8bc2a3e201417e40
均 2800×1272
```

**两张的差异**：左侧卡池立绘在动（第一张是「日和（泳装）」立绘，第二张是**白色漩涡状的过场/加载动画**），
右侧信息面板**完全一致**。⇒ 界面不是静态卡死，是**能切换/有动画**的；缺的只是**文案**。

---

## 二、★ 图里所有文字的原样抄录（这条最重要）

### 顶部栏
```
← 返回
招募成员  [?]
⚡ 64/24    🎫 50,000    💎 1,800
⚙（设置）  🏠（主页）
```

### 卡池缩略图（3 个）
```
[咕噜噜老师图标] DUMMY
[咕噜噜老师图标] DUMMY
[咕噜噜老师图标] DUMMY        ← 三个卡池全部是 "DUMMY"
（最右侧还有一个被裁切的第 4 个缩略图；另有 ☰ 列表按钮）
```

### 右侧信息面板（**核心问题区**）
```
2026/11/12 14:00~2026/11/26 13:59截止        ← 日期是**正常**的
**No LocalizeKey**                            ← 大标题（约 36px 加粗黑字）
**No LocalizeKey**                            ← 副标题第 1 行
**No LocalizeKey**                            ← 副标题第 2 行
（中间一大片空白，无立绘、无说明文字）
```
### 右下角
```
💌（招募券图标，角标 10）   1,000
                          招募10次
```

### 底部按钮
```
[点数图标] 点数   **No LocalizeKey**   **No LocalizeKey**（红底白字，第二个按钮）   选择成员
```

### 左下
```
★★★ 阿里乌斯战术小队
日和（泳装）
配音 中原麻衣/降温
概率信息   成员信息   注意事项
```
（这是左侧卡池的立绘信息，**文字正常**）

---

## 三、占位文字逐条判定

| 位置 | 原文 | 判定 |
|---|---|---|
| 3 个卡池缩略图 | **`DUMMY`** | 卡池**名称**没有真数据 → 服务端/表格给的是占位卡池 |
| 面板大标题 | **`No LocalizeKey`** | **本地化表缺 key**（客户端找不到 `LocalizeText` 条目，直接回显这个字符串） |
| 面板副标题 2 行 | **`No LocalizeKey`** | 同上 |
| 底部按钮 1 | **`No LocalizeKey`** | 同上 |
| 底部按钮 2（红） | **`No LocalizeKey`** | 同上 |
| 日期 | `2026/11/12 14:00~2026/11/26 13:59截止` | **正常**（说明 banner 数据是有的） |
| 价格 | `1,000` / `招募10次` | **正常** |
| 角色信息 | `日和（泳装）` / `阿里乌斯战术小队` / `配音 中原麻衣/降温` | **正常**（说明角色表格正常） |
| 底部固定按钮 | `概率信息` / `成员信息` / `注意事项` / `选择成员` / `点数` | **正常**（UI 骨架的静态文案正常） |

**⇒ 结论：不是"整体文案缺失"，而是「卡池 banner 相关的 LocalizeKey 找不到」——
角色名/日期/价格/按钮骨架都正常，只有**卡池标题、副标题、两个底部按钮**回显 `No LocalizeKey`，且卡池名是 `DUMMY`。**

---

## 四、logcat 命中情况 —— **游戏进程自己 0 行**

```
命令：logcat -d -b all -v threadtime -t 3000  → 3,196 行
按 PID 15844 过滤：**0 行**（release 包不打 Unity/业务日志，与历次观察一致）
```
关键词命中（`Excel|ExcelDB|Localize|TextTable|TableBundle|AssetBundle|Addressable|Failed|NotFound|Missing|placeholder|Gacha|Recruit|Pickup|DUMMY`）：
```
全部是**系统噪音**，与本游戏无关，例如：
  11-17 20:57:02.242  7659  7659 E oiface  : sched_setaffinity failed
  11-17 20:57:03.873  3864  5824 W FastPrintWriter: java.io.IOException: write failed: EPIPE
  11-17 20:57:04.759  8777 22149 W ModernMediaScanner: Failed to visit /data/local/tmp/recruit1.png: AccessDeniedException
  11-17 20:57:05.443  2760 17623 W ResourceManagerMetrics: notifyClientStopped: Start Config is missing!
  11-17 20:57:05.460  2159  2218 W vendor.qti.media.c2@1.0-service: [c2.qti.hevc.decoder] … query failed
```
**⇒ logcat 对本案无价值**（Unity release 包静默），真正的证据在**截图**和**资源文件**里。

---

## 五、客户端版本 + 资源目录（顺带确认）

```
versionName=3.0.2    versionCode=73 (minSdk 24 / targetSdk 33)
```
数据目录 `/sdcard/Android/data/com.RoamingStar.BlueArchive/files/`（mtime 20:53–20:54，**刚刚被写过**）：
```
AssetBundles/     2026-11-16 03:46
TableBundles/     2026-11-16 03:09   6,232 个文件（文件名是 hash，无 localize 字样）
ClientSaveData/   2026-11-17 20:54
catalog_Remote.json  2026-11-13 03:22   81,410,257 B
catalog_Remote.hash  2026-11-17 20:53   内容 = 831a1ba7bd9b4cecf1834e6c74154aed
manifest.db / manifest_backup.db  2026-11-17 20:53   各 12,677,120 B
2071278565329732703  2026-11-17 20:53
```

### ★★ 两个关键配置文件（可能是根因）

**`LocalizeConfig.txt`（164 B，原文）**
```
Env=dev
IsLocalize=false
ResUrls=https://static.bluearchive-cn.com/prodm39;https://static-qc.bluearchive-cn.com/prodm39;https://static-hs.bluearchive-cn.com/prodm39
```
**`LocalConfig.json` / `GlobalConfig.json` 的 StringTable（原文片段）**
```json
{"StringTable":{"Language":"**Kr**","LastLoginName":"10000000001","LastServer":"", ...}}
```
```json
（GlobalConfig.json 同样：{"StringTable":{"Language":"Kr","LastLoginName":"","LastServer":"", ...}}）
```

### ★ 我的判断（推断·中高，非观测）
```
① **`"Language":"Kr"`** —— 客户端当前语言被设成了**韩语**。
   本地化表若没有 Kr 的对应条目（或我们的服务端只发了 Cn/Jp 的文本表），
   查表就会回落到 **`No LocalizeKey`** 这个硬编码兜底串。
② **`IsLocalize=false`** —— 本地化开关是关的，进一步说明"不走本地化表"的路径。
③ 卡池名显示 **`DUMMY`** —— 这是**卡池数据本身**就是占位（服务端 banner 表没给真名），
   和 ① 是两件事：DUMMY 是数据层，No LocalizeKey 是文本层。
```
**⇒ 最小验证动作（我没做，等你批准）：把 `GlobalConfig.json` / `LocalConfig.json` 里的
`"Language":"Kr"` 改成 `"Cn"`（或该客户端支持的值），重启客户端再看招募页。
只需要改 1 个字段、有 backup 可回滚，风险低。**

### 另一个可疑点
```
catalog_Remote.json 是 **2026-11-13** 的旧文件（81.4 MB），而 catalog_Remote.hash 今天 20:53 被刷新成 831a1ba7…
⇒ 目录清单可能"hash 是新的、内容是旧的"，如果服务端换了 catalog 而本地没真正落新 json，
   部分 bundle（含 banner 文本）就会加载到旧/缺的版本。
```
（这条是【推断·中】，要证实得比对服务端 catalog 的 hash 与本地 json 的实际内容。）

---

## 六、边界
```
✅ 只读：screencap / logcat -d / ls / cat / grep / find / dumpsys
❌ 没点屏幕、没杀进程、没清缓存、没重启游戏、没改任何文件、没起 8080
```

---

# §catalog Localize 条目（2026-11-17 21:10–21:16，**纯只读**）

> 方法：`head -c` / `bytes.count` / `find`（在 proot 的 python3 里对 81 MB 文件做 O(n) 字节扫描，不用正则——正则在这台机器的单行大 JSON 上会跑飞，我用 `[A-Za-z0-9_\-./]*[Ll]ocali` 那次把 python 跑成 4 分钟 CPU 未返回，已 kill 掉自己的进程，改用 `bytes.count`，1 秒完成）
> 全程：**没有写、没有删、没有改、没有重启、没有 pull 大文件、没有点屏幕**

## ① catalog 头部前 4 KB（原文节选，`head -c 4096`）

```json
{"m_LocatorId":"AddressablesMainContentCatalog","m_InstanceProviderData":{"m_Id":"UnityEngine.ResourceManagement.ResourceProviders.InstanceProvider","m_ObjectType":{"m_AssemblyName":"Unity.ResourceManager, Version=0.0.0.0, Culture=neutral, PublicKeyToken=null","m_ClassName":"UnityEngine.ResourceManagement.ResourceProviders.InstanceProvider"},"m_Data":""},"m_SceneProviderData":{...},"m_ResourceProviderData":[{"m_Id":"...AssetBundleProvider"},{...BundledAssetProvider},{...BundledAssetProvider}],"m_ProviderIds":["...AssetBundleProvider","...BundledAssetProvider"],"m_InternalIds":["{PlatformUtils.AddressableLoadPath}/academy-_mxload-prefabs-2026-06-04_assets_all_2136914256.bundle","{PlatformUtils.AddressableLoadPath}/akari_original_skill_frag-_mxload-timelines-2026-06-04_assets_all_1674639180.bundle","{PlatformUtils.AddressableLoadPath}/arms-_mxload-prefabs-2026-06-04_assets_all_322129807.bundle","{PlatformUtils.AddressableLoadPath}/assets-_mx-3dobject-airi_original_icecream-_mxdependency-materials-2026-06-04_assets_all_1003847428.bundle", ...（后续数千条同样格式）}
```
**关键字段**：
```
m_LocatorId = "AddressablesMainContentCatalog"      （出现 1 次）
m_InternalIds                                       （出现 1 次，后面是几千条 bundle 路径）
m_BucketDataFromJson = 0                             （**0 次**，说明这不是标准的 addressables JSON catalog 的完整形态）
末尾（tail 300）= ..."MXUnderCover.UCGameResource+HighlightMaterialInfo"},{"...DitherMaterialInfo"}],"m_InternalIdPrefixes":[]}
```

## ② `Localize` 相关 token —— **0 条（彻底没有）**

```
$ grep -o 'Localize[^"]*' catalog_Remote.json | sort -u | head -40
（该命令在手机 busybox 上跑不完，改用等价且快的字节扫描）
```
```
catalog bytes: 81,410,257
  Localize  = 0
  localize  = 0
  Locali    = 0
  locali    = 0
  LOCALI    = 0
```
**⇒ catalog 里**一个** `Localize` 字样都没有**，既没有 `LocalizeGachaShopExcel`，也没有任何 localize bundle 条目。**

## ③ 旁证：catalog 里别的 token 都在，只有 Localize 缺
```
  Gacha = 1047      ← 有（示例：Assets/_MX/AddressableAsset/Audio/SFX_UI/SFX_Gacha/UI_Gacha_Normal_01.wav）
  gacha = 67
  Shop  = 919
  Table = 306
  Excel = 0         ← Excel 也是 0
  bundle = 24164    ← 两万四千多条 bundle 路径
  m_InternalIds = 1
  m_LocatorId = 1
  m_BucketDataFromJson = 0
```
**⇒ 不是文件截断/损坏——`Gacha`/`Shop`/`Table` 都在，24,164 条 bundle 路径都在；
偏偏 `Localize` 与 `Excel` 是 0。这正说明"catalog 是 11-13 那一版，缺后来才加的 Localize/Excel 条目"。**

## ④ manifest.db 里有没有 —— **也没有**

```
$ grep -a -c 'bundle' manifest.db      → 14725
（头部：SQLite format 3，标准 sqlite 文件）
manifest bytes: 12,677,120
  manifest Localize     = 0
  manifest localize     = 0
  manifest Gacha        = 0
  manifest TableBundles = 0
  manifest bundle       = 50273
```
**⇒ manifest.db 里有 50,273 处 `bundle` 记录，但 `Localize` / `Gacha` / `TableBundles` 全是 0**
（说明 manifest.db 只记 bundle 文件名/哈希，不含业务表名，属正常；**不能拿它判断 Localize 缺失**）。

---

## 结论（可直接给 srv-ops / ca-researcher）

```
1. 客户端本地 catalog_Remote.json（11-13 版，81,410,257 B）里 **完全没有 Localize 条目**
   ⇒ 客户端查 LocalizeGachaShopExcel 这类文本键时，Addressables 找不到对应 bundle
   ⇒ 回落成硬编码兜底串 **`No LocalizeKey`** —— 与截图完全吻合
2. 同一份 catalog 里 `Gacha`(1047) / `Shop`(919) / `Table`(306) / `bundle`(24,164) 都在，
   **只有 Localize 与 Excel 是 0** ⇒ 不是文件坏，是"这一版 catalog 生成时就没有这两类"
3. 所以修复方向成立：**只需要补 Localize（和 Excel）那一两个 bundle，
   再把 catalog 里对应条目补上**，不需要重下 11 GB、也不需要重下全部 81 MB（除非服务端只能整包给）
4. ⚠️ 但有一个前提问题：**catalog 是客户端从真实 CDN 下的**（你已确认），
   如果我们只在本机替换 catalog，客户端下次启动可能又按 CDN 的版本覆盖回去；
   要长期生效，得让 `AddressablesCatalogUrlRoots` 指向我们自己能控的地方
```

## 边界
```
✅ 只读：head -c / bytes.count / bytes.find / grep -a / od / ps / ls
❌ 没写、没删、没改、没重启、没 pull 81 MB、没点屏幕
（唯一一次"动作"是 kill 掉我自己跑飞的 python 扫描进程 —— 它已经烧了 4 分钟 CPU，
  不是你或用户的进程；如果你认为这也不该做，我下次改为先报你）
```
