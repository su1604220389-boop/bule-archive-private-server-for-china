# v2b 并行安装包（改包名）+ v2 重建（NOROOT_V2B_PARALLEL_20261117）

> 负责人：ca-researcher（独占 `build_noroot_apk.py` + `_noroot\apk\`）
> 时间：2026-11-17 20:36–21:05 (+08:00)
> 状态：**v2b 已构建并验收；v2 因一个引号 bug 一并重建（旧哈希作废，见 §1）**
> 未碰：手机、`_noroot\phone\`、`_card\`、`_blackout\*`、`_multiplayer\`、nginx、`ba_sni.conf`

---

## 0. 一行结论

> **v2b 构建完成：包名=`com.RoamingStar.BlueArchive2`　sha256=`58D2EA89974FEA3FFDC0BA9D7569F70AE08A0B4B0756C3083F49096EEDD6DAFC`　大小=`2,127,971,233 B`；SDKConfig 验证=**对**；并行安装 **可行（不卸载、不碰现役数据），但有一个无法离线判定的风险：ACE 的 `libtprt.so` 里嵌着包名`。**

⚠ **同时必须知道**：上一版 v2 的 `ServerInfoDataUrl` 是**非法 JSON**（PowerShell 吃掉了内层双引号），已修复并重建，**旧 sha256 `682A9EA2…` 作废**。

---

## 1. ★ 先说一件必须更正的事：v2 的旧哈希作废

### 1.1 现象

上一轮我用这条命令构建 v2：

```powershell
--gmconfig-value '["https://example.com/api/state"]'
```

构建成功、`--verify-only` 也 exit 0，但**回读产物发现**：

```
ServerInfoDataUrl = '[https://example.com/api/state]'   len=36   ← 没有内层双引号
json.loads(...)   → Expecting value: line 1 column 2 (char 1)   ← 非法 JSON
```

### 1.2 根因

**Windows PowerShell 5.1 在把参数传给原生 exe 时会静默吃掉内层双引号。**
`--gmconfig-value '["https://…"]'` 到了 `sys.argv` 里就变成 `[https://…]`（少 2 字节，36 而非 38 字符）。

这是"构建成功、签名全绿、自检也过、但客户端解析不了"的**静默故障**——`--verify-only` 只比对"值 == 我传的值"，而传进去的已经是坏值，所以两边一致、判 OK。

### 1.3 修法（两层）

| 层 | 做法 |
|---|---|
| **① 命令行层面** | 改用**整串 URL 形式**：`--gmconfig-url https://example.com/api/state`。脚本内部走 `'["%s"]' % s` 分支**自己补引号**，命令行里一个双引号都不需要 |
| **② 脚本层面（硬护栏）** | 在 `main()` 里对最终值做 `json.loads` + "非空字符串数组"校验，不合法直接 `die()` 并提示用整串 URL 形式。**以后再踩这个坑，构建会当场失败而不是悄悄产出坏包** |

护栏效果验证：

```
--gmconfig-value '["https://example.com/api/state"]'   → 现在会 die（值变成 [https://…] 非法 JSON）
--gmconfig-url  https://example.com/api/state          → 通过，产出 len=38 的合法数组
```

### 1.4 重建后回读（这一条才是真凭据）

```
BA_noroot_v2.apk              len=38  == 期望: True   json: ['https://example.com/api/state']
BA_noroot_v2b_parallel.apk    len=38  == 期望: True   json: ['https://example.com/api/state']
```

> 教训（写进流程）：**凡是"值由命令行传入"的字段，校验必须是"回读产物 + 语义解析"，不能是"产物 == 我传的值"。**

---

## 2. 构建命令（两条，都可复现）

```powershell
cd work\ba\noroot
$src  = C:\Users\su\Desktop\大肥鱼项目\BAServer\report\_tmp\cn_base.apk
$dir  = C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\server\deploy\_noroot\apk

# v2（原包名，用于"卸载官方包"那条路）
python build_noroot_apk.py --src $src --out $dir\BA_noroot_v2.apk `
  --sdk-url https://example.com/sdk `
  --gmconfig-url https://example.com/api/state

# v2b（改包名，用于"并行安装不碰现役数据"）
python build_noroot_apk.py --src $src --out $dir\BA_noroot_v2b_parallel.apk `
  --sdk-url https://example.com/sdk `
  --gmconfig-url https://example.com/api/state `
  --rename-package com.RoamingStar.BlueArchive2
```

**参数全清单**：`--src / --out / --sdk-url / --gmconfig-url`（v2b 另加 `--rename-package`）；其余全默认：`--ca` 不传、`--ca-mode user`、`--v1`、`--arsc-first`、`--align-mode raw`、`--keystore ba_private.keystore`（相对路径 ⇒ 必须在 `work\ba\noroot\` 下跑）、`--force` 未用。

耗时各约 45 s。两次同参数构建**逐字节一致**（v2 已实测）。

---

## 3. v2b 验收结果

### 3.1 产物

| 项 | v2 | v2b |
|---|---|---|
| 路径 | `_noroot\apk\BA_noroot_v2.apk` | `_noroot\apk\BA_noroot_v2b_parallel.apk` |
| 大小 | 2,127,971,177 B | **2,127,971,233 B** |
| sha256 | `5F8B79DD930B8D1420B5B686CBC978142B751EEA47C4B090BA308482A0F2F5C6` | **`58D2EA89974FEA3FFDC0BA9D7569F70AE08A0B4B0756C3083F49096EEDD6DAFC`** |
| 包名 | `com.RoamingStar.BlueArchive` | `com.RoamingStar.BlueArchive2` |
| 条目数 | 41,307 | 41,307 |

### 3.2 `--verify-only` exit 0（两个包都跑了独立复验）

```
v2: OK / v3: OK / zip 完整性: OK
v1: 最长行 70 B, 超 72 B 的行 0 个（OK）
v1: 逐条摘要 41304 条, 不符 0, 缺失 0
v1: X-Android-APK-Signed = '2, 3'
v1 结论: OK
STORED 4 字节对齐: OK / 重复条目: 无 / resources.arsc 第 1 条 STORED
__tpinfo 残留: 无（OK）
GameMainConfig: ServerInfoDataUrl == 期望值: OK
package = 'com.RoamingStar.BlueArchive2'（OK）        ← --expect-package 校验
```

### 3.3 `aapt2 dump badging`（Google 官方工具，v2b）

```
package: name='com.RoamingStar.BlueArchive2' versionCode='73' versionName='3.0.2'
         compileSdkVersion='33'
minSdkVersion:'24'
targetSdkVersion:'33'
application-label:'蔚蓝档案'
```

### 3.4 包名替换的覆盖度（`aapt2 dump xmltree` 实测）

| 检查 | 结果 |
|---|---|
| 清单里**残留旧包名**（`com.RoamingStar.BlueArchive` 且后面不是数字） | **0 处** ✅ |
| 新包名出现次数 | 98 次 |
| 串池替换数 | **27**（27 个串，49 个属性引用） |
| AXML 节点数 | 582 → 582（**不变**） |
| 属性级 diff | 49 个属性变化，**全部**以新包名为前缀，**0 处误伤** |

**改了哪些**（逐类，来自实测映射）：

| 类别 | 处数 | 例子 |
|---|---|---|
| `manifest/@package` | 1 | `com.RoamingStar.BlueArchive2` |
| `provider/@authorities` | 15 | `.fileprovider` / `.airi.fileprovider` / `.adjust-lifecycle-provider` / `.sls_provider` / `.themisLite` / `.unitywebview.fileprovider` / `.huawei.push.provider` / `.jiguang.InitProvider` / `.aaidinitprovider` / `.GDTInitProvider` / `.TapTapKitInitProvider` / `.SDKContentProvider` / `.DataProvider` / `.InitProvider` / `.AGCInitializeProvider` |
| `permission/@name` + `uses-permission/@name` | 5 个权限名 | `.gdt.qq.SEND_PERMISSION` / `.RECEIVE_PERMISSION` / `.permission.JOPERATE_MESSAGE` / `.permission.JPUSH_MESSAGE` / `.permission.PROCESS_PUSH_MSG` / `.permission.PUSH_PROVIDER` / `.permission.PUSH_WRITE_PROVIDER` |
| `provider/@readPermission` `@writePermission` | 4 | 极光推送的读写权限 |
| `receiver/@permission` | 1 | `.permission.PROCESS_PUSH_MSG` |
| `activity/@taskAffinity`、`activity-alias/@taskAffinity` | 2 | `com.RoamingStar.BlueArchive2` |
| `activity-alias/@name` | 2 | `.wxapi.WXEntryActivity` / `.wxapi.WXPayEntryActivity`（**这两个是 alias 名不是类名**，改对微信回调是必需的） |

> **关键安全性判断**：这 27 个串**全部**是"命名空间类"字符串（包名/authority/权限名/alias 名/taskAffinity），**没有一个是需要存在的 Java 类名** —— 所以改名不会造成 `ClassNotFoundException`。这一点是我在改之前用 `axml_parse` 逐属性核对过的（不是猜的）。

### 3.5 其余保持不变

| 检查 | 结果 |
|---|---|
| `assets/SDKConfigSettings.json` 的 `sdk_url` | `https://example.com/sdk` ✅ 逐字符一致 |
| `res/E5.ogg` sha256 | `9bd6f5856d9162d4…` —— **与原包完全相同** ⇒ `--ca` 没生效 ✅ |
| `__tpinfo.*` | 源包 5 个 → 产物 **0** 个 ✅ |
| `res/Dk.xml` | 560 B，含 `<certificates src="system"/>` + `src="user"/>` ✅ |

---

## 4. 并行安装步骤（v2b）

### 4.1 为什么并行安装是"零风险"

| | 官方包 | v2b |
|---|---|---|
| 包名 | `com.RoamingStar.BlueArchive` | `com.RoamingStar.BlueArchive2` |
| 签名 | 原厂 | 我们的（不同） |
| 安装关系 | — | **不同包名 ⇒ 不冲突、无需卸载、不覆盖** |
| 数据目录 | `/data/data/com.RoamingStar.BlueArchive` | `/data/data/…Archive2`（**全新**） |
| 外部数据 | `/sdcard/Android/data/com.RoamingStar.BlueArchive`（11.1 GB） | `…Archive2`（**空**） |
| 卸载 v2b | 不影响 | 只删自己那份 |

⇒ **装 v2b 不需要 `pm uninstall`，现役 11.1 GB 数据和账号完全不动。**

### 4.2 安装

```bash
# 1) 传包（2 GB）
adb push BA_noroot_v2b_parallel.apk /data/local/tmp/ba_v2b.apk
adb shell "su -c 'sha256sum /data/local/tmp/ba_v2b.apk'"
#   期望 58d2ea89974fea3ffdc0ba9d7569f70ae08a0b4b0756c3083f49096eedd6dafc

# 2) 直接装（不要 uninstall 任何东西）
adb shell "su -c 'pm install -r /data/local/tmp/ba_v2b.apk'"
#   期望 Success
#   若报 Failed transaction（ksu 域被挡）→ adb install --streaming -r BA_noroot_v2b_parallel.apk

# 3) 确认两个包并存
adb shell "pm list packages | grep RoamingStar"
#   期望两行：…BlueArchive 和 …BlueArchive2
```

### 4.3 装完怎么区分"我现在跑的是哪个包"

| 判据 | 官方包 | v2b |
|---|---|---|
| 桌面图标 | 原来的 | **新装一个**（可能同名"蔚蓝档案"，看包名分辨） |
| 包名 | `com.RoamingStar.BlueArchive` | `com.RoamingStar.BlueArchive2` |
| **base.apk sha256** | 原厂 | `58d2ea89…d6dafc` |
| `__tpinfo` | 5 个 | 0 个 |

```bash
# 最可靠：分别取两个包的 base.apk 哈希
adb shell "su -c 'for p in com.RoamingStar.BlueArchive com.RoamingStar.BlueArchive2; do echo \$p; sha256sum /data/app/*/\$p*/base.apk; done'"
```

### 4.4 服务端怎么确认"新包真的连上我们了"

```bash
# 服务器侧（srv-ops）：看 sdk.log 有没有新设备的 /user/quick-login 或 QUICK OK
# 这是唯一能证明"不是官方包在跑"的硬证据
```

### 4.5 卸载 v2b（不影响官方包）

```bash
adb shell "su -c 'pm uninstall com.RoamingStar.BlueArchive2'"
# 官方包的 11.1 GB 数据、账号、进度 一律不受影响
```

---

## 5. 用户必须提前知道的 5 件事

### ① 本地数据是全新的（但**服务端进度大概率还在**）

| 层 | 官方包 | v2b | 说明 |
|---|---|---|---|
| 本地 `/data/data/<pkg>` | 有 | **空** | 设置、缓存、prefs 全没 |
| 本地 `/sdcard/Android/data/<pkg>` | 11.1 GB | **空** | 进游戏要**重新下载/解包约 11 GB** |
| **服务端账号** | 有 | **同一套** | 见 ② |

### ② DevId 是从**卡密**派生的，不是设备号 ⇒ 账号不会被当成新的

已有实测结论（`HANDOFF_20261117.md §6`）：

```
DevId = md5(card)[:8] % 9e8 + 1e8        # 卡密 11111111111 → 314816420
```

⇒ **同一张卡密 → 同一个 DevId → 同一个服务端账号**，与包名、设备、Android ID 都无关。
⇒ 因此：**v2b 用同一张卡登录，看到的是同一个存档**（除非卡密换了）。

> 唯一可能变化的是 SDK 侧的 `Authorization.Head.DeviceID`（Android ID / SSAID）。Android 8+ 的 SSAID 按"签名密钥 + 用户"派生，而我们两个包**签名相同**，所以大概率也相同；但个别 ROM 按包名派生 ⇒ 可能被当成一台"新设备"。**影响面**：如果卡密绑定了设备台数上限，可能占用一个新名额。**建议**：测试用一张不限设备的卡。

### ③ 两个包的 Hosts / 缓存互不相干

`/sdcard/Android/data/<pkg>/files/Hosts` 在新包下是空的。`Hosts` 是 `Servers` 的落盘缓存（`08-手机接管与真因.md §2`），空的时候客户端会重新请求 `/api/state` —— 对我们反而是好事（不会用旧缓存）。

### ④ 想省掉 11 GB 重下（可选，有风险）

```bash
# 装完、首次启动【之前】用 root 把旧目录复制过去（失败就让它自己重下）
adb shell "su -c 'cp -a /sdcard/Android/data/com.RoamingStar.BlueArchive/. /sdcard/Android/data/com.RoamingStar.BlueArchive2/'"
```
⚠ 内部若有硬编码包名的路径/配置，可能读到脏数据。**建议先让它自己下**，确认能跑通之后再考虑省流量。

### ⑤ 两个包能同时装，但**不建议同时运行**

ACE（`libtprt.so`）+ 两个实例同时跑可能触发异常；而且两个包会抢同一个服务端账号。**测 v2b 前先把官方包停掉**（`am force-stop` 或从最近任务划掉）。

---

## 6. 残余风险与未知（必须如实说）

### 6.1 ★ 最大未知：ACE 的 `libtprt.so` 里嵌着**原包名**

实测（只读扫描原包）：

```
lib/arm64-v8a/libtprt.so @0x19BA68:
  ...\x00*U*I*N*F*L*T*F*\x00#T#A#P#I#P#O#E#\x00com.RoamingStar.BlueArchive\x00...
```

包名紧挨着一串 `*U*I*N*F*L*T*F*` / `#T#A#P#I#P#O#E#` 这类**编码标记**，看起来像"按包名派生密钥"的痕迹。

**两种可能，无法离线判定**：
- (a) ACE 只把它当默认值/参考，运行时用 `getPackageName()` ⇒ v2b 正常；
- (b) ACE 用它做密钥种子 ⇒ 包名一变，ACE 初始化失败 ⇒ **启动即崩**。

**已知先例**：11-14 曾把包名改成 `com.RoamingStar.BlueArchiv2` 并"装上跑过"（Lead 提供）。**倾向 (a)**，但**不能替代实测**。

**这不是改包能消除的风险** —— 改 `libtprt.so` 就会撞 ACE 的哈希 pin（E35/E36 的 SIGBUS 教训）。

### 6.2 另外 3 处旧包名**故意没改**

| 条目 | 处数 | 内容 | 为什么不改 | 影响面 |
|---|---|---|---|---|
| `classes.dex` | 1 | 字符串常量（挨着 `com.adjust.preinstall`） | 改 dex 会撞 ACE 加载布局（E39–E43 卡启动） | 若某 SDK 用它拼 authority ⇒ 该 SDK 的内部 provider 失配（Adjust 埋点类，不影响游戏主链） |
| `resources.arsc` | 1 | 资源字符串池里的一个值 | 改 arsc 要重排类型/字符串表，风险最高 | 同上，属 SDK 内部 |
| `lib/arm64-v8a/libtprt.so` | 1 | ACE 自己的字符串 | 绝对不动 | 见 6.1 |

### 6.3 结构上已验证、运行时未验证

已验：签名（v1/v2/v3）、zip 结构、对齐、包名、authorities、权限名、NSC、sdk_url、ServerInfoDataUrl、`__tpinfo` 清空、`E5.ogg` 未动。
**未验**：能不能装上、能不能启动、能不能登录、ACE 认不认新包名。**这些只能真机。**

---

## 7. 台账

| 文件 | 动作 | 字节 | sha256 |
|---|---|---|---|
| `_noroot\apk\BA_noroot_v2.apk` | **重建**（旧哈希作废） | 2,127,971,177 | `5F8B79DD…A0F2F5C6` |
| `_noroot\apk\BA_noroot_v2b_parallel.apk` | **新建** | 2,127,971,233 | `58D2EA89…EDD6DAFC` |
| `work\ba\noroot\build_noroot_apk.py` | **改**（+AXML 改名 / +护栏 / +`--expect-package`） | 115,359 | `C19591E51867F7BD5E25FB7B75A7056177AD5714BB290AEA23C1DACA6ACB85A3` |
| `work\ba\noroot\_snapshot_build_20261117_2040_pre-rename.py` | 新建（改前备份） | 109,025 | `24CB3770…DA8CFD` |
| `report\_tmp\cn_base.apk` | 未改动 | 2,126,400,085 | `DD30A285…7F83BB` |

**回滚脚本改动（一行）**：
```powershell
Copy-Item work\ba\noroot\_snapshot_build_20261117_2040_pre-rename.py work\ba\noroot\build_noroot_apk.py -Force
```

### 7.1 脚本新增能力（供其它任务复用）

| 参数/函数 | 作用 |
|---|---|
| `--rename-package NEW_PKG` | 改包名：只重写 `AndroidManifest.xml` 串池（节点块一个字节不动），package/authorities/权限名/alias 名/taskAffinity 一起改 |
| `--expect-package PKG` | 校验产物 package（`--verify-only` 也可用） |
| `axml_rename_package(axml, old, new)` | 上述实现；支持 UTF-16 串池、styleCount=0；重建后自检"节点数不变" |
| `--gmconfig-value` 的 JSON 护栏 | 值不是合法 JSON 字符串数组 → 直接 `die`，防止"引号被吃"重新出现 |

> 副作用：`--gmconfig-value` 现在**不能**再传不带引号的 `[url]`（会 die）。以前的坏用法被彻底堵死。
