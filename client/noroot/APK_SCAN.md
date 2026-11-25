# APK 硬编码服务器地址扫描（BA 国服）

> 目标：弄清 APK 里到底有哪些服务器地址是硬编码的、在哪，从而判断**改包能不能把服务器换掉**（无 root 方案的前置判断）。
> 全部素材只读；本文件与同目录脚本只写在 `work\ba\noroot\`。
> 复算脚本：`scan_needles.py`（明文/UTF-16 多记号 + ELF section 归属）、`xor_scan.py`（任意单字节/周期 XOR 键）、`extract_urls.py`（URL 提取）、`meta_band.py` / `meta_band2.py`（混淆字面量带枚举）。

## 0. 结论先行

| 问题 | 答案 |
|---|---|
| APK 里有 `bluearchive-cn` / `state-api` / `gsqc-api` / `gs-api` / `yostar.cn` / `xuliehaochaxu` 明文吗 | **没有。本次扫描 31 个文件（22 个 .so、2 个 dex、`global-metadata.dat`、`resources.arsc`、`AndroidManifest.xml`、`aa/settings.json`、2 个 apk 容器）全部 0 命中** |
| 有没有被 XOR 混淆起来的域名 | **有，12 条 URL 全部解出**：10 条与游戏相关（state×3、账号×2、备案、日服帮助页、兑换码、日服支付、TapTap 商店页），2 条无关（Unity 文档模板、百度）；**0 条是 RPC 网关**（§2.1） |
| 客户端自己决定的服务器地址有哪些 | ①`state` 入口（唯一硬编码的是**测试环境** `http://test-ba.yostar.net:5210/api/state`）②`account.yostar.cn`（账号）③`cdkey.yo-star.com`（兑换码）④`payment.yostar.co.jp` / `bluearchive.jp`（日服）⑤`www.taptap.cn/app/316964`、`beian.miit.gov.cn` |
| 服务器给的地址有哪些 | **RPC 基址 + 全部资源 CDN**（`ServerInfoConnectionGroupData` 的 `ApiUrls`/`ApiUrl`/`AssetBundlesUrlRoots`/`AddressablesCatalogUrlRoot`… 全部来自 state 响应）→ **改包改不了** |
| 改包能不能把服务器换掉 | **不能**（就"改域名"这条路而言）。能改的只有"state 请求发到哪"，而生产 state 域名**不在本地这份 APK 里**（§5）。真正可用的无 root 落点是**服务端返回的 state 响应**，不需要改包 |

> **与同目录其它报告的交叉验证**：`SDK_ASSETS.md` 给出 `assets/SDKConfigSettings.json` 的原值 `"sdk_url":"https://sdk-api.yostar.cn"`（权威来源 `work\ba\bapatch\repack_e31.py:6` 的 `SDK_OLD = b'https://sdk-api.yostar.cn'` + `:17` 的 `assert SDK_OLD in cfg`）；`_dd4-integrity.md` 给出 ACE 完整性校验的**定点对象**（`libunity.so`、`libtprt.so` 被钉死；`libil2cpp.so` 不在其列；`assets/__tpinfo.*` 5 个清单文件删掉即整段跳过校验）。本文 §4 的静态发现与这两份不冲突，可互补：他们给"实测事实"，本文给"代码路径与能力边界"。

## 1. 明文扫描（第一层：`grep -a`）

方法：`scan_needles.py` 按 16 MiB 分块 + 重叠，同时搜 ASCII 与 **UTF-16LE**；每个命中给 `offset / section / ±100 B 上下文`。计数为**出现次数**（不是 `grep -c` 的行数——二进制文件里 `-c` 恒为 1，会误导）。

| 文件 | 字节数 | `bluearchive-cn`…6 条目标记号 | `https://` | `http://` | `yostar` |
|---|---|---|---|---|---|
| `global-metadata.dat` | 38,426,024 | **0** | 90 | 30 | 3（`yostarUid`/`yostarToken`/`yostarTexture`，标识符名，非域名） |
| `libil2cpp.so` | 270,927,056 | **0** | 4 | 20 | 0 |
| `libunity.so` | 20,950,552 | **0** | 3 | 1 | 0 |
| `libtprt.so`（ACE） | 1,692,296 | **0** | 1 | 0 | 0 |
| `classes.dex` | 9,327,708 | **0** | 35 | 9 | 6（`yostarsdk.db` 等本地库名） |
| `classes2.dex` | 10,158,904 | **0** | 63 | 14 | 1 |
| `resources.arsc` | 1,156,308 | **0** | 2 | 0 | 0 |
| `AndroidManifest.xml` | 50,552 | **0** | 0 | 1（UTF-16LE） | 0 |
| 其余 21 个 so | 合计 23,805,312 | **0** | 29 | 5 | 0 |

所有 `https://` 明文命中的性质（逐条已核）：

- `libil2cpp.so`：`https://` 4 条（`0x037C8A0C` / `0x037CC556` / `0x037CC7A1` / `0x037CF6B4`）+ `http://` 20 条（`0x037BCEE3`–`0x037CFF71`），**全部在 `.rodata`**（该 so 的 `p_vaddr == p_offset`，故文件偏移=虚拟地址），形态是**被截断的 XML 命名空间前缀**（`http://www.w3.org/…`、`http://schemas.microsoft.com/…`），不是完整 URL。
- `libunity.so`：`https://curl.se/docs/alt-svc.html`、`…/http-cookies.html`（libcurl 帮助字符串）。
- `libtprt.so`：`https://android.googlesource.com/toolchain/llvm-project`（`.comment` 段里的 clang 版本串，`0x0019CA0F`）。
- `libmain.so` / `libsigner.so`：同上，`clang version` 的 `.comment`。
- `resources.arsc`：`https://github.com/journeyapps/zxing-android-embedded`、`https://journeyapps.com/`（zxing 的 legal 文案资源）。
- `AndroidManifest.xml`：`http://schemas.android.com/apk/res/android`（命名空间常量）。
- `classes.dex`/`classes2.dex`：支付宝（`mclient.alipay.com`、`mobilegw.alipay.com`、`loggw-exsdk.alipay.com`）、微博、QQ/QQ互联、Adjust（`app.adjust.com`/`.io`、`ssrv.adjust.*`）、巨量引擎（`analytics.oceanengine.com`）、中国移动认证（`cmpassport.com`、`id6.me`、`nisportal.10010.com:9001`）、TapSDK/心动（`tapsdk.api.xdrnd.cn/.com`、`accounts.xdrnd.cn`、`tapsdk.tapapis.cn`、`gid.tapapis.com`）、`play.google.com`、`baidu.com`。**零条游戏服务器**。

> ⚠️ 陷阱记录：`grep -c` 在二进制上返回的是**行数**（无换行 ⇒ 恒 1）。本文所有计数来自 `scan_needles.py` 的逐次 `bytes.find`。

## 2. 混淆扫描（第二层：任意 XOR 键）—— 这一步才是决定性的

`global-metadata.dat` 的**字面量区是逐条独立 XOR 的**（同一份文件里不同字符串用不同键）。所以 `grep -a` 的"0 命中"**不能**证明"没有硬编码"，必须解混淆。

方法：`xor_scan.py` 用 `b":://"` 做锚点、以**相邻字节 XOR 差**（`d[i]^d[i-1]`，键会被消掉）一次遍历覆盖**全部 256 个单字节键**，命中处反推键并解码窗口。另用跨步 delta 指纹对长域名做**周期 ≤8 的重复 keystream** 检测。

### 2.1 解出的全部游戏相关字面量（12 条，精确偏移）

| # | 解出的串 | 文件:偏移 | XOR 键 | 性质 |
|---|---|---|---|---|
| 1–3 | `http://test-ba.yostar.net:5210/api/state` ×3 | `global-metadata.dat` `0x000C172B` / `0x000C1756` / `0x000C1781` | `0xB5` | **测试环境** state 入口，是**一个 130 字节 JSON 数组**（`0x000C1729`，仅 1 份副本，3 个元素全同）——即"默认连接组" |
| 4 | `https://account.yostar.cn/cn-ba/collect` | `0x000D3DB9` | `0x25` | 国服账号 |
| 5 | `https://account.yostar.cn/cn-ba/shared_list` | `0x000D3DE0` | `0xFC` | 国服账号（分享列表） |
| 6 | `https://beian.miit.gov.cn/FZZ` | `0x000D3E0B` | `0x97` | 工信部备案链接 |
| 7 | `https://bluearchive.jp/help?data=` | `0x000D3E25` | `0xB9` | 日服帮助页 |
| 8 | `https://cdkey.yo-star.com/api/coupon/use` | `0x000D3E46` | `0x5A` | **兑换码 API**（唯一 `yo-star.com`） |
| 9 | `https://docs.unity3d.com/Packages/` | `0x000D3E6E` | `0x72` | Unity 文档（`string.Format` 模板） |
| 10 | `https://payment.yostar.co.jp/product?id=cq3p6brhl8o5o06udbk0` | `0x000D3EA7` | `0x3B` | 日服支付 |
| 11 | `https://www.baidu.com/rnnji` | `0x000D3EE3` | `0xFF` | 百度（更新/检查用） |
| 12 | `https://www.taptap.cn/app/316964` | `0x000D3EF9` | `0xE5` | TapTap 商店页 |

同带上限内另有 `ws://ws-api-dx.xfyun.cn/v2/tts`（`0x000E1034`, key `0xA8`）与 `wss://tts-api.xfyun.cn/v2/tts`（`0x000E1055`, key `0x49`）——讯飞语音，与游戏服务器无关。

**负结果（同样精确）**：`bluearchive-cn` / `state-api` / `gsqc-api` / `gs-api` / `yostar.cn` / `xuliehaochaxu`

| 搜索方式 | metadata | libil2cpp | libunity | classes.dex | classes2.dex |
|---|---|---|---|---|---|
| ASCII 明文 | 0 | 0 | 0 | 0 | 0 |
| UTF-16LE | 0 | 0 | 0 | 0 | 0 |
| **全部 256 个单字节 XOR 键**（键无关 delta 法，精确） | **0** | **0** | **0** | **0** | **0** |
| 周期 P=2..3 重复 keystream（`bluearchive` L=11 / `state-api` L=9 / `xuliehaochaxu` L=13 / `yostar.cn` L=9） | 0 | 0 | 0 | 0 | 0 |

> `bluearchive-cn`(L=14) / `gsqc-api`(L=8) / `gs-api`(L=6) 另做单字节单测：5 个文件各 **0 命中**。
> `gsqc`(L=4) 单测在统计上无意义（约束不足，误报率 1/256 起），故只用 `gsqc-api` 的完整形态判定——**0 命中**。
>
> 周期扫描的可检测上限：针长 L 时 P ≤ L/3 才有统计意义（否则约束不足）。因此"周期 ≥4 的 keystream 藏着 `state-api`"在方法上仍**未被证伪**；但（a）含 `://` 的生产域名已被单字节全键覆盖；（b）同文件里实测的 12 条字面量**全部是单字节键**——混淆实现就是单字节，没有理由对某一条改用周期键；（c）`libil2cpp.so` 的 `.rodata` 里也能解出同一族混淆器处理过的片段（`0x037D23A5` 用键 `0xC9` 解出 `http://www.w3.org/shortcut`），说明混淆器不只用在 metadata 上——而即便如此，单字节全键扫描下 `bluearchive`/`state-api` 在 `libil2cpp.so` 仍是 0。

## 3. 分类：哪些地址是"客户端自己决定的"，哪些是"服务器给的"

### 3.1 类结构（来自 `global-metadata.dat` 名字堆，行号为 `out/metadata-strings.txt`）

```
28999: ServerInfoConnectionGroupData      ← DTO：ApiUrls / ApiUrl / AddressablesCatalogUrlRoot(s)
                                              / AssetBundlesUrlRoots / BundlesCatalogUrls / BundlesHashUrls
                                              / AddressCatalogUrls / AddressHashUrls / ResourceVersion
                                              / TableVersion / MediaVersion / PatchVersion
                                              + Init / InitResPaths / ResetApiUrl / get_ApiUrl / apiIndex
29090: apiIndex                          ← "当前用第几条"
29118: ServerInfoDataRepository          ← 取服务器信息的仓储
29125: get_StateServerUrl                 ← ① state 入口（属性）
29126: DownloadServerInfoDataHttp2        ← ② 下载 state 响应（HTTP/2）
29127: GetApiServerInfo  (b__0..b__3)     ← ③ 从响应里挑 API 服务器（4 个 lambda ⇒ 多候选/多分支）
29128: GetGameServerInfo                  ← ④ 挑游戏（gateway）服务器
29134: StateServerUrl                     ← 同名字段
29135: StateServerResponse                ← 响应类型
29136: Servers                            ← 响应里的候选服务器数组（**唯一一处 `Servers` token**）
```

另有 `2921xx` 区的 `RequestGameServerInfo.<Update>b__14_0`（`0x001D8FD5` 上下文）与 `yostarUid` / `yostarToken` / `RequestQueuingGetTicket` / `enterTicket` / `serverSeed`，构成"登录 → 取票 → 进 gateway"的链路。

### 3.2 结论：**"Servers 来自 state 响应"成立，且 RPC 基址不是硬编码**

- `StateServerResponse` 里**只有一个** `Servers` 字段，紧跟 `StateServerUrl`——与你给的逻辑一致。
- 客户端里与 RPC 基址有关的**唯一**字面量是 `["http://test-ba.yostar.net:5210/api/state" ×3]`，它是 `GetDefaultConnectionGroup` 用的**默认/测试**连接组（JSON 数组、3 个相同元素、`http://`）。
- **fallback 逻辑存在，但 fallback 的值是测试环境**：`GameMain.GetDefaultConnectionGroup`（`0x0041c579` / XOR-0x66 形态 `0x001546f0`）→ 默认组 → 失败再走 `StateServerUrl`。也就是说"硬编码默认值"确实有，但它指向 `test-ba.yostar.net:5210`，**不是生产网关**。
- `ResetApiUrl` + `apiIndex` ⇒ 客户端会在候选间轮换/重试；`ApiUrls`（复数）就是 state 给的候选列表。
- 资源 CDN 也**全部**在 `ServerInfoConnectionGroupData` 里（`AssetBundlesUrlRoots`/`AddressablesCatalogUrlRoot`/`TableUrlRoots`/`PatchUrlRoots`…）⇒ **CDN 地址同样改包改不了**。

### 3.3 与"资源 CDN"相关的本地配置（已核）

`work\ba\audit\ba-work\x\assets\aa\settings.json`（3,161 B）只含 **Addressables 本地目录定义**，全部指向 `{UnityEngine.Application.persistentDataPath}/catalog_Remote.hash`，**没有任何 host/URL**。⇒ CDN 根地址不在这里。

## 4. 签名校验点（ACE）

### 4.1 Java 侧（`jadx/sources`，可读的确定性证据）

| 发现 | 位置 | 含义 |
|---|---|---|
| `System.loadLibrary("tprt")` **全 APK 仅 1 处** | `com/ace/gshell/AceApplication.java:31`（静态块） | libtprt 的唯一加载者 |
| `initialize(packageName, filesDir, nativeLibraryDir, **sourceDir**, splitSourceDirs)` | `AceApplication.java:28,62` | **把 APK 路径（`applicationInfo.sourceDir`）与 split APK 路径整包交给 native** ⇒ "算 APK 哈希/验签"在能力上完全成立 |
| `attachBaseContextShell()` 在 `attachBaseContext` 里调用 | `AceApplication.java:41-44` | 早于任何业务代码；`initialize != 0` 就抛异常（但被 `catch` 吞掉，`65-66`） |
| 3 个 **exported** service：`com.ace.gshell.GP6Service` / `GP7Service` / `GP7Worker`，`onStartCommand` 读 `intent.getStringExtra("ioctl")` → `gp6ioctl/gp7ioctl` | `AndroidManifest.xml:197-222`；`GP7Service.java:18-21` | **第二条进程的命令通道**（gshell 守护/自检），外部也可拉起 |
| **Java 层 0 处** `getPackageInfo` / `GET_SIGNATURES` / `GET_SIGNING_CERTIFICATES` / `.signatures` | 全 `jadx/sources` 全文检索 | 验签**不在 Java 层**；若存在，只在 native |
| `<application android:name="com.tech.core.TechApplication" android:extractNativeLibs="true" android:usesCleartextTraffic="true">` | `AndroidManifest.xml:182-188` | 见 §6（`usesCleartextTraffic=true` 对无 root 方案极关键） |

### 4.2 native 侧（`libtprt.so`，1,692,296 B，sha256 `47064882…`）

| 项 | 结果 |
|---|---|
| 可打印串 | **`strings -n 5` = 2,095 条；`-n 6` = 1,146 条** —— 对 1.69 MB 的库是**极低**，说明字符串被加密（样例垃圾串 `/TLV<x\hAdII}MH_x}Hm`、`` /z`RiK%y ``） |
| `signature` / `Signature` / `getPackageInfo` / `MessageDigest` / `sha256` / `digest` / `integrity` / `cert` / `X509` / `PackageManager` / `checkSignatures` / `crc32` / `dl_iterate_phdr` / `/proc/self/maps` / `frida` / `xposed` | **全部 0 命中**（但**字符串加密 ⇒ 0 命中不构成"没有"的证明**） |
| `ptrace` | 1 命中（导入表亦有 `ptrace@LIBC`） |
| `com.excean.gspace` | 1 命中 —— **模拟器/多开沙箱检测**的包名黑名单项 |
| 导出符号 | `JNI_OnLoad`、`tp_syscall_imp`、`unwind_xx_info_query`、`unwind_xx_ioctl`、`g_tprt_ori_array`、`g_tprt_pfn_array` —— 两个 `g_*_array` 是**inline hook 的原函数/跳板表**，`unwind_xx_*` 是**栈回溯**钩子 |
| 导入符号（154 条） | 检测/对抗面：`ptrace`、`prctl`、`syscall`、`mprotect`、`mmap`、`madvise`、`fork`/`execv`/`waitpid`/`kill`、`dlopen`/`dlsym`/`dladdr`、`open`/`stat`/`readlink`、`opendir`/`readdir`；通信面：`socket`/`connect`/`bind`/`listen`/`accept`/`send`/`recv`/`getaddrinfo` |

**ACE 到底校验什么——可确证的与不可确证的：**

| 校验对象 | 证据强度 | 结论 |
|---|---|---|
| **APK 文件本体（签名/哈希）** | **强（能力）/ 工作区内已有实测（行为）** | ACE 在 `initialize()` 里**拿到了 APK 路径**且发生在 `attachBaseContext`。本项目实测结论（见 `_dd4-integrity.md` §0）：**ACE 的完整性校验是"定点"的，不是"整包签名"的**——已验证被钉死的对象只有 `libunity.so`（改 4 字节 → `SIGBUS`）与 `libtprt.so`；**`libil2cpp.so` 明确不在其列**；`assets/__tpinfo.*` 那 5 个自身完整性清单文件**删掉即整段跳过校验**。另：E30→E44 十余版重打包、`apksigner` 真换签名装机后可运行 ⇒ **未观测到"仅因签名变化被杀"** |
| **so 磁盘哈希** | **强** | 同上：`libunity.so`/`libtprt.so` 定点钉死；`libil2cpp.so` 不钉 |
| dex 哈希 | 未找到 | 0 证据（本文静态侧；Java 层也 0 处验签调用） |
| `global-metadata.dat` | **未知** | 无证据（前情报告 30 号亦标注"未知，需实测"） |
| root / frida / xposed / 模拟器 | **中** | `ptrace`/`prctl` 导入 + `com.excean.gspace` 字样；无 `frida`/`xposed` 明文（串加密） |

> **缺口（必须标注）**：`com.tech.core.TechApplication` 是 manifest 指定的 Application，但 **jadx 没有产出它的源码**（类描述符存在于 `classes2.dex 0x2D364A`：`Lcom/tech/core/TechApplication;`）。它是否 `extends AceApplication`、是否在 `onCreate` 里再做一轮校验，**本次未能反编译**（见 §7 待办）。

## 5. `assets/` 配置清单（第 3 问）

**本地素材里 `assets/` 只有 2 个文件**（`work\ba\audit\ba-work\x\assets\`）：`aa/settings.json`（3,161 B，§3.3，无 URL）与 `bin/Data/Managed/Metadata/global-metadata.dat`。**`assets/SDKConfigSettings.json` 原件不在仓库**——`slim.apk`（7,950,751 B）只有 4 个条目（`resources.arsc` + 2 个 dex + manifest），`dexonly.apk` 只有 2 个，都不含 assets。

但它的**内容已被工作区记录钉死**：`zip_listing.txt` **第 29066 行**证明条目存在；`work\ba\bapatch\repack_e31.py:6` 定义了 `SDK_OLD = b'https://sdk-api.yostar.cn'`，`:17` 断言 `assert SDK_OLD in cfg`（`cfg = zin.read('assets/SDKConfigSettings.json')`）⇒ **顶层 `sdk_url` 的原值 = `https://sdk-api.yostar.cn`**（26 字节）。详见同目录 `SDK_ASSETS.md`。

其 **schema 可从 dex 精确还原**（`com/airi/common/model/params/SDKConfigSettings.java`，321 行）：

```
SDKConfigSettings
├─ sdk_url : String          ← ★ Yostar/Airi SDK 后端基址（最可能藏生产域名的字段）
├─ channel : String
├─ android { cs_enable:int, cs_url:String, qq_appid, udata_oeappid,
│            weibo_appid, weibo_callback, weixin_appid }
└─ ali { internet_detection {
        internet_url : String,
        log     { endpoint, project, logstore, access_key_id, access_key_secret },
        init    { endpoint, project, secret_key, access_key_id, access_key_secret },
        auto_url{ http[], ping[], tcpping[], mtr[], dns[] }   ← 网络诊断目标列表（也是域名！）
   } }
```

`zip_listing.txt` 里其余配置类条目（均未在本地，供后续取用）：
`assets/bin/Data/ScriptingAssemblies.json`、`assets/bin/Data/RuntimeInitializeOnLoads.json`、`assets/aa/catalog.json`、`assets/grs_sdk_server_config.json`、`assets/grs_sdk_global_route_config_opendevicesdk.json`、`assets/grs_sdk_global_route_config_opensdkService.json`、`assets/com.tencent.open.config.json`、`assets/supplierconfig.json`。

**判定**：

| 配置 | 里面有服务器地址吗 | 改它能不能指向我们 | 需要重签 APK 吗 |
|---|---|---|---|
| `assets/SDKConfigSettings.json` | **有**：`sdk_url = https://sdk-api.yostar.cn`（已确证，见上）+ `ali.internet_detection.auto_url.*` | 能改**账号/SDK/诊断**目标；**RPC 网关仍不经过它** | **需要**（`extractNativeLibs=true` 只影响 `.so`，`assets/` 仍是压缩 zip 条目） |
| `assets/aa/settings.json` | **没有**（全 `persistentDataPath`） | 无意义 | 需要 |
| `assets/bin/Data/*.json` | 未在本地，未测 | 未知 | 需要 |
| `global-metadata.dat` | 有 6 条游戏相关（§2.1） | 只能改 state 入口/账号/兑换码 | 需要 |

## 6. 对"无 root 换服务器"的直接含义

1. **`android:usesCleartextTraffic="true"`**（`AndroidManifest.xml:187`）+ 默认连接组是 **`http://`** ⇒ 客户端**接受明文 HTTP**。这意味着无 root 方案**不需要装 CA、不需要 TLS**，服务端用 http 即可。
2. 生产 state 域名不在本地 APK 里 ⇒ **改包改不到生产入口**；但 state 响应里的 `Servers` 完全由服务端决定 ⇒ **只要能让客户端把 state 请求送到我们一次，后面所有地址（RPC + CDN）都由我们下发，永久生效**（这正是私服该走的路线，且**不需要改包**）。
3. 因此"改包"对无 root 方案的价值不在"换域名"，而在：①改 `state` 入口（若最终定位到生产域名，且它恰好在可改配置里）；②关掉 `CustomCertificateHandler`（若将来改走 https）。
4. ACE 在 `attachBaseContext` 阶段就拿到 APK 路径 ⇒ **重签名 APK 有被检出的理论风险**；而 `libil2cpp.so` 未被磁盘哈希钉死（前情实测）⇒ 若必须改，优先"改 `assets` 里的 metadata / 配置 + 重签"而不是"改 so"。

## 7. 未找到 / 待办（诚实标注）

| 项 | 状态 |
|---|---|
| `bluearchive-cn` / `state-api` / `gsqc-api` / `gs-api` / `yostar.cn` / `xuliehaochaxu` 明文 | **未找到（0 命中，31 个文件）** |
| 生产 state 域名（任意单字节 XOR / 周期 ≤3） | **未找到** |
| `assets/SDKConfigSettings.json` | 原件不在仓库，但**值已确证**：`sdk_url = https://sdk-api.yostar.cn`（`repack_e31.py:6,17`）→ 不是缺口 |
| `assets/bin/Data/`（`globalgamemanagers` / `level0` / `sharedassets*.assets`） | **未在本地素材里**；序列化字段仍可能藏 URL（前情报告 11 的模型 M2）⇒ **剩余唯一的信息缺口** |
| `com.tech.core.TechApplication` 的反编译 | **未完成**（类描述符在 `classes2.dex 0x2D364A`，jadx 未产出源码） |
| ACE 是否校验 APK 签名 / `global-metadata.dat` | 静态侧**未证实**；工作区实测侧（`_dd4-integrity.md`）：校验**定点**（libunity/libtprt 钉死，libil2cpp 不钉，`__tpinfo.*` 可跳过），**未观测到"仅因重签被杀"** |

**下一步（按性价比）**：

```powershell
# 1) 唯一剩下的信息缺口：Unity 序列化资源。从原 APK 取出后跑本目录的两个扫描器
#    assets/bin/Data/globalgamemanagers, level0, sharedassets*.assets
python work\ba\noroot\scan_needles.py --out work\ba\noroot\_scan_data <上述文件>
python work\ba\noroot\xor_scan.py url <上述文件> --out work\ba\noroot\_xor_url_data.txt
# 2) 反编译 TechApplication（ACE 的 Application 入口，判断它是否 extends AceApplication）
baksmali d <classes2.dex> -o <out>   # 或 jadx --single-class com.tech.core.TechApplication
# 3) 验证"state 响应决定 RPC 基址"的最后一跳：抓一次官方 state 响应，
#    把 Servers 换成我们的地址，看客户端是否直接连过来（这一步不需要任何改包）
```

## 8. 附：本次全部产物

| 路径 | 内容 |
|---|---|
| `work\ba\noroot\APK_SCAN.md` | 本文件 |
| `work\ba\noroot\scan_needles.py` | 明文/UTF-16 多记号扫描（ELF section 归属 + ±100 B 上下文） |
| `work\ba\noroot\xor_scan.py` | 键无关 XOR 扫描（URL 全键枚举 / 周期 ≤8 delta 指纹） |
| `work\ba\noroot\extract_urls.py` | 从二进制抽完整 URL 与域名片段 |
| `work\ba\noroot\meta_band.py` / `meta_band2.py` | test-ba 副本精确定位 + 混淆字面量带严格域名枚举 |
| `work\ba\noroot\_scan_small.txt` / `_scan_big.txt` | 明文扫描的逐条命中（含偏移/section/上下文） |
| `work\ba\noroot\_xor_url_metadata.txt` / `_xor_url_others.txt` | XOR 扫描结果（按 键+URL 聚合） |
| `work\ba\noroot\_tprt_strings.txt` | libtprt.so 全部可打印串（2,095 行） |
