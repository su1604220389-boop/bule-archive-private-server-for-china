# APK 表完整性核对（本地只读）

> 只读作业：未联网、未连服务器、未重打包、未修改任何 APK 或已有文件。
> 唯一新增的正式文件就是本报告；中间产物只落在 `work\ba\data\_tmp\apk_exceldb\`（3 个 JSON，没有解压任何 APK）。
> 时间：2026-11-19 01:5x（Asia/Shanghai）　解释器：`...\primary-runtime\dependencies\python\python.exe`
> 方法：`zipfile` 只读中央目录（不解压整包）+ `hashlib` 流式全文件哈希 + `sqlite3` 只读查询。

---

## 0. 直接回答（先给结论）

**我们重打包的 APK 里没有 `ExcelDB.db` —— 一个 `.db` 都没有。** 于是"md5 是否等于官方 `824ce3a8…`"这个问题不成立：包里不存在这个文件，也就没有可比的 md5。

**官方原版 APK 里同样没有。** 这不是重打包弄丢的，是**设计如此**：

| 证据 | 内容 |
|---|---|
| 全条目名单 | 重打包包 41,307 条 / 官方包 41,312 条，`.db`、`.sqlite`、`StreamingAssets`、`Excel*` 命中数 **均为 0** |
| 表清单自述 | `work\ba\data\TableCatalog.json` → `"ExcelDB.db": {"Size": 160534528, "Crc": "824ce3a8bee2bb5ae36ada1ac95048f1", "isInbuild": false}` ← **`isInbuild: false` = 明确声明"不进包"** |
| 体积上限 | 两个包里除 `libil2cpp.so`(270,927,056) 外最大条目是 `assets/aa/catalog.json`(81,313,204)，`assets/bin/Data/` 最大只有 17,753,380 —— **160 MB 的表在物理上塞不进任何条目** |

**⇒ 原假设"重打包带进了和官方不一致的表版本"在 APK 层被证伪。** 表既不在我们的包里，也不在官方包里；它只能来自**首次启动时的下载**（见 §8 的源码证据）。

其余关键值（逐条见下文）：

- `resources.arsc` sha256 = **`cd8943ae979fd434a6c1fee67e8129bba1bc4a452e1937d7d7e6052079eecb86`**，**与历史常量一致 ✅**（官方 + 9 个互异成品构建逐个核过，见 §6）
- 我们的生产包 vs 官方包：**41,301 个条目内容完全相同**（size + CRC 双等，含 `resources.arsc`、`assets/aa/*`），真正有差异的只有 **2 新增 / 7 删除 / 4 修改**（见 §5）
- 本地"客户端表基准"两份副本（`data\ExcelDB.db`、`srv_live\…\tools\ExcelDB.db`）**都是 160,534,528 B / md5 `824ce3a8bee2bb5ae36ada1ac95048f1` ✅**

---

## 1. 找到的重打包 APK（成品 / 准成品，≥ 2 GB）

搜索范围：`C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\` 全树（含 `apk_patch`、`noroot`、`server\deploy\_noroot\apk`、`dist`/`output` 类目录），并扩大到整个 `BAServer` 找 ≥100 MB 的包。

| # | 路径（相对 `work\ba\`） | 大小(字节) | 修改时间 | md5 | sha256 |
|---|---|---|---|---|---|
| 1 | `noroot\BA_noroot_prod_20261118_v1.apk` ★生产 | 2,127,971,177 | 2026-11-18 00:04:40 | `f888d4bdd048d0853e840a6dba204f3c` | `5f8b79dd930b8d1420b5b686cbc978142b751eea47c4b090ba308482a0f2f5c6` |
| 2 | `apk_patch\backup\BA_noroot_prod_20261118_v1.apk` | 2,127,971,177 | 2026-11-18 00:04:40 | 同上 | 同上（同一件制品，字节相同） |
| 3 | `server\deploy\_noroot\apk\BA_noroot_v2.apk` | 2,127,971,177 | 2026-11-17 20:40:48 | 同上 | 同上（部署件 = 生产件） |
| 4 | `server\deploy\_noroot\apk\BA_noroot_v2b_parallel.apk` | 2,127,971,233 | 2026-11-17 20:41:37 | `69a04ee27ec4d85ab5c3a0bf3fbcdb24` | `58d2ea89974fea3ffdc0ba9d7569f70ae08a0b4b0756c3083f49096eedd6dafc` |
| 5 | `noroot\BA_noroot_v1.apk` | 2,127,962,985 | 2026-11-16 06:23:38 | `67c6692c727bfa92166011a8d9db95a6` | `449229ba173c103829a1d454f60e6e0ef40d36c73a79df6df7cc29f661de541d` |
| 6 | `apk_patch\out\v2_layoutonly.apk` | 2,127,972,169 | 2026-11-18 19:40:52 | `8b5e2292d19d49dd0e045d185bdd0225` | `562d528a951eaeb15ae3165ece4a7ceb91849bb21ef54c895c6f217f9a676d64` |
| 7 | `apk_patch\out\v3_dexpatch.apk` | 2,133,473,392 | 2026-11-18 19:41:40 | `0df449fd3f585d266cd9041b4eeeaa7a` | `6e5dcfb0317db175cec1be0719fad8271f6cae9abb5f3da84b571a36f6d2de25` |
| 8 | `apk_patch\out\v4_login.apk` | 2,127,972,093 | 2026-11-18 20:14:10 | `69dd05f06844d99008c301c109824056` | `6490fcfc772f4dc6dd1773e7999a491775a646b08675591204b18212ee94eddb` |
| 9 | `apk_patch\out\v5_login.apk` | 2,127,972,945 | 2026-11-18 20:23:37 | `5e05d82ff127f07e4459340bd662ef8f` | `7ae11fd0bb31108dabf616662eb8f5314002b9882e29188007c25bced0303db7` |
| 10 | `apk_patch\out\BlueArchive_cardlogin_v1.apk` | 2,133,476,336 | 2026-11-18 19:05:47 | `5dd4050c35d4c552e184835b02c2f51b` | `d621b3296767a60c208668f1291d662a05ddba1e1fda794cda5021a724a209fe` |

**要点**：`prod_v1` / `deploy v2` / `backup` 三份 sha256 完全相同 ⇒ 线上部署的就是 `apk_patch\backup` 那一份，没有第二套。

### 1.1 小体积中间件（不是成品包，仅存档）

| 路径（相对 `work\ba\`） | 大小 | 修改时间 | 条目数 | sha256 |
|---|---|---|---|---|
| `apk_patch\slim\slim.apk` | 15,828,657 | 2026-11-18 18:50:42 | 878 | `9285e7a8f0dd737632b5a188aa9b9b01572bafe7b648c6a10f45a6a1171a47ef` |
| `audit\ba-apk\slim.apk` | 7,950,751 | 2026-11-11 08:14:10 | 4 | `80f125b3f142cfac4f421ed77b9d1b16c58f107dc583d23e75ed6d3428162f34` |
| `audit\ba-work\x\dexonly.apk` | 7,680,376 | 2026-11-11 08:14:38 | 2 | `1fa59c5ca8678ed7b19d18f01a9eb59a9d268596098796da5c2b8fd74e9af626` |
| `bapatch\res.apk` | 3,145,659 | 2026-11-12 22:05:14 | 1,646 | `1300dba5a5f5efb3c4492e5601624bf587bf8603598006a1dade70aed27efcad` |
| `bapatch\lsp\build13\Probe13.apk` | 21,078 | 2026-11-13 01:28:24 | 8 | `313135869049aa00127002a2a7a635b2d436574319cdc36d4e8115fc2ae000d6` |
| `noroot\_neg_content.apk` | 21,078 | 2026-11-17 01:15:10 | 非 zip（负样本） | `c722ab1837f1d110df677b50e4f229e74588de7b54b9ec77b4f8fc79b14537fc` |
| `noroot\_neg_sigblock.apk` | 21,078 | 2026-11-17 01:15:10 | 8 | `5a5dc6e90483c28f20573ccebf8f87b1c722716349906b24c6e2fb65d7b34ea0` |
| `bapatch\lsp\build13\base.apk` | 13,334 | 2026-11-13 01:28:22 | 5 | `08b287883256859a4f2303ebdbbcf833f5bc8a1f29c998046f534c0a5a67c070` |
| `apk_patch\v2v3\wrap_new.apk` | 2,255 | 2026-11-18 19:43:41 | 1 | `41eaabfbaff0d1e6eadc6abed15d60661329ba301d2a371f43051ec52d17ed9` |
| `bapatch\lsp\build13\aligned.apk` | 1,986 | 2026-11-12 22:40:30 | 3 | `9b58ec75f21bc2a763851ac316716c60e949894877aa2e7b2cf0898e6524ad2a` |
| `apk_patch\v2v3\wrap_orig.apk` | 1,980 | 2026-11-18 19:43:41 | 1 | `f1d223ac001b39e8c8112dc35024586b4ad3f92c3447c3778ad609f0839337c2` |

这些里面也**没有任何 `.db`**（逐个开包核过）。

---

## 2. 官方原版 APK（对照基准）

| 项 | 值 |
|---|---|
| 路径 | `C:\Users\su\Desktop\大肥鱼项目\BAServer\report\_tmp\cn_base.apk` |
| 大小 | **2,126,400,085** 字节（2,027.9 MiB） |
| 修改时间 | 2026-11-16 06:11:50 |
| md5 | `54de1ed6ff555b10f08ca54b35576964` |
| sha256 | `dd30a285b58508252df09a503b025850a27a73c89f1162454bee55a60d7f83bb` |
| 条目数 | 41,312 |

**身份三重印证（它确实是官方国服原包，不是二手产物）**：

1. `report\_tmp\apk1.txt` 记录的真机 `pm path` 结果：
   `APK=/data/app/~~2xgRssuvhsk2wBPdAcLoAg==/com.RoamingStar.BlueArchive-HO-giOdeRyKWibiIJsCg_A==/base.apk`，`SIZE=2126400085` ← **与本文件大小逐字节相同**
2. `report\_tmp\apk3.txt` 记录的真机 `sha256sum`：
   `dd30a285b58508252df09a503b025850a27a73c89f1162454bee55a60d7f83bb` ← **与本文件 sha256 完全相同**
3. 包内 `AndroidManifest.xml`：`package=com.RoamingStar.BlueArchive`、`versionName=3.0.2`（与真机 `pm dump` 记录一致）

---

## 3. 资源清单核对（问题 3）

| APK | 条目数 | `resources.arsc` | `resources.arsc` sha256 | `assets/bin/Data/` 条目 | 任一 `ExcelDB.db`? | 任一 `.db`/`.sqlite`? | `StreamingAssets`? |
|---|---|---|---|---|---|---|---|
| 官方 `cn_base.apk` | 41,312 | 有，1,156,308 B | `cd8943ae…9eecb86` | 565 | **否** | **否** | **否** |
| prod v1（=v2=backup） | 41,307 | 有，1,156,308 B | `cd8943ae…9eecb86` | 565 | **否** | **否** | **否** |
| v2b_parallel | 41,307 | 有，1,156,308 B | `cd8943ae…9eecb86` | 565 | 否 | 否 | 否 |
| noroot v1 | 41,307 | 有，1,156,308 B | `cd8943ae…9eecb86` | 565 | 否 | 否 | 否 |
| v2_layoutonly / v3_dexpatch / v4_login / v5_login / cardlogin_v1 | 41,307 | 有，1,156,308 B | `cd8943ae…9eecb86` | 565 | 否 | 否 | 否 |

补充核查：

- `assets/bin/Data/` 结构完整：`globalgamemanagers`、`globalgamemanagers.assets.split0..5`、`level0/1`、`sharedassets0.assets.split0..36`、`Resources/unity_builtin_extra`、`Managed/Metadata/global-metadata.dat`(38,426,024)、`ScriptingAssemblies.json` 等 —— 与官方逐条一致（565 对 565，仅 1 个文件内容不同，见 §5）。
- `assets/aa/`（Addressables，BA 的远程资源目录）逐条一致：
  `assets/aa/catalog.json`(81,313,204, CRC `63ca83fb`)、`assets/aa/settings.json`(3,161, CRC `9f7ac49d`)、`assets/aa/AddressablesLink/link.xml`(202,355, CRC `ecb64bca`) —— **CRC 全等 ⇒ 内容全等**。
- **`assets/aa/catalog.json` 里搜不到 `ExcelDB` / `Excel` / `TableBundles` / `LocalizeGachaShop` / `MasterData`（命中数均为 0）** ⇒ 表不在 Addressables 目录里，更说明表是走独立下载通道（`/Preload/TableBundles/`）。

---

## 4. `ExcelDB.db` 提取与比对（问题 4）

### 4.1 APK 内：不适用

两个包里**不存在** `ExcelDB.db`（也不存在 `assets/ExcelDB.db`、`assets/**/ExcelDB.db`、`StreamingAssets/ExcelDB.db`）。
⇒ **本轮没有从任何 APK 中提取出 `ExcelDB.db`**，`work\ba\data\_tmp\apk_exceldb\` 下只有 3 个证据 JSON，没有 db 文件。

体积上的排除性证明（防止"改名藏起来"的可能）：

| APK | 最大条目 | 第二大 | >100 MB 的条目 | `assets/bin/Data/` 最大单文件 |
|---|---|---|---|---|
| 官方 | 270,927,056 `lib/arm64-v8a/libil2cpp.so` | 81,313,204 `assets/aa/catalog.json` | 1 个 | 17,753,380 |
| 我们的包 | 同上 | 同上 | 1 个 | 17,753,380 |

`ExcelDB.db` 是 160,534,528 B；就算压缩到 ~40 MB，也必然在"第二大条目"位置冒头 —— 而那个位置被 81 MB 的 catalog.json 占着，其下直接掉到 17.8 MB。**没有任何条目容得下它。**

### 4.2 本地"客户端表基准"比对（顺手核了，作为对照锚点）

| 文件 | 大小 | md5 | sha256 | 与官方基准 |
|---|---|---|---|---|
| `work\ba\data\ExcelDB.db` | 160,534,528 | `824ce3a8bee2bb5ae36ada1ac95048f1` | `c49096aa6fdafee3c7bb4d5293039e1dafe1521c09c033bd25566aefae2cc5a9` | **一致 ✅** |
| `work\ba\srv_live\20261118_0059\bapatch\tools\ExcelDB.db` | 160,534,528 | `824ce3a8bee2bb5ae36ada1ac95048f1` | 同上 | **一致 ✅** |

`sqlite_master`（只读打开，`data\ExcelDB.db`，共 398 张表）：

```
LocalizeGachaShopDBSchema   cols=(GachaShopId, Bytes)   rows=1235
LocalizeDBSchema            cols=(Key, Bytes)           rows=18456
ShopRecruitDBSchema         cols=(Id, Bytes)            rows=532
```

⇒ `LocalizeGachaShopDBSchema` **存在且 1,235 行**，与既有报告（`NOLOCALIZEKEY_ORIGIN.md` 第三轮）完全吻合。**本地这份表没有任何"版本被换掉"的迹象。**

---

## 5. 差异面：我们的生产包 vs 官方原版（问题 5）

比对口径：`filename` → (`uncompressed size`, `CRC32`) 全量双等比较。

| 类别 | 数量 | 明细 |
|---|---|---|
| **内容完全相同** | **41,301** | 含 `resources.arsc`、`assets/aa/*`、`assets/bin/Data/` 564/565 个文件、`classes.dex`、`classes2.dex`、全部 `lib/*.so`、`assets/audio/*`(39,755) |
| **新增** | **2** | `META-INF/CERT.RSA`(1,208) / `META-INF/CERT.SF`(156) ← 我们的重签名 |
| **删除** | **7** | `META-INF/BACN.RSA` / `META-INF/BACN.SF`(5,151,804) ← 官方签名；`assets/__tpinfo.tp`(12) / `assets/__tpinfo.tsc`(485,268) / `assets/__tpinfo.tsc.sig`(256) / `assets/__tpinfo.tsd`(1,668) / `assets/__tpinfo.tsd.sig`(256) ← 腾讯加固的资源索引（合计 487,460 B） |
| **修改** | **4** | 见下表 |

### 5.1 四个被修改的条目（逐个说明）

| 条目 | 官方 → 我们 | 性质 | 与表有关? |
|---|---|---|---|
| `META-INF/MANIFEST.MF` | 5,151,677 → 5,151,246（deflate → **stored**） | 重签产生的 v1 摘要清单，必然变 | 否 |
| `assets/SDKConfigSettings.json` | 2,840 → 2,843 | **免 root 登录补丁**：`"sdk_url"` 由 `https://sdk-api.yostar.cn` 改为 `https://example.com/sdk`（全文仅此 1 行差异） | 否 |
| `res/Dk.xml` | 264 → 560 | `network-security-config`：官方只有 `<trust-anchors><certificates src="system"/>`；我们**新增了 `src="user"`** ⇒ 允许用户 CA（MITM 抓包用）。这是预期内的改动 | 否 |
| `assets/bin/Data/e37c46fea17834108a4756797197d05a` | 5,212 → 5,212（内容不同） | **唯一被改动的 Unity 序列化资产**，详见 §7 | **可能是**（唯一嫌疑） |

### 5.2 包体积变化可完整对账（+1,516,030 压缩字节）

```
MANIFEST.MF  deflate→stored        +3,561,654
e37c46fea…   813→5,212 (deflate→stored)  +4,399
res/Dk.xml                          +296
SDKConfigSettings.json                +3
新增 CERT.RSA+CERT.SF             +1,208+156
删除 BACN.RSA/BACN.SF/__tpinfo.*  -2,051,686
────────────────────────────────────────────
合计                              +1,516,030  = 实测 (2,120,361,297 - 2,118,845,267) ✅
```
未压缩总量：我们 2,456,256,687 vs 官方 2,461,895,783（−5,639,096，来自删掉的 tpinfo+官方签名）。
⇒ **包里"变大"完全是重新压缩 + 重签名造成的，不涉及资源内容替换。**

---

## 6. `resources.arsc`（问题 6）

| 项 | 值 |
|---|---|
| **实际 sha256** | **`cd8943ae979fd434a6c1fee67e8129bba1bc4a452e1937d7d7e6052079eecb86`** |
| 与历史常量 `cd8943ae…9eecb86` | **完全相等 ✅** |
| 大小 | 1,156,308 B（两边相同） |
| CRC32 | 932,256,075（两边相同） |
| 覆盖验证 | 官方 + **全部 9 个互异的重打包成品**（noroot v1 / v2 / prod v1 / v2b_parallel / v2_layoutonly / v3_dexpatch / v4_login / v5_login / cardlogin_v1）+ 2 个 `slim` 中间件，逐个开包核过，**无一例外** 都等于该常量 |

⇒ **"`resources.arsc` 必须保持不变"这条要求成立**，且本次核查的所有成品包都满足。

> 唯一例外是 `bapatch\res.apk`（3,145,659 B，1,646 条目）——它是早期的**纯资源探针包**，arsc 为 `fcc61134146ea393eb1304d5cb91f13d336c798675f03c1560a5a175a26627ee`（1,330,948 B，aapt 重建产物）。它没有进入任何成品链路，**不代表交付包**。

---

## 7. 唯一未解释项：`assets/bin/Data/e37c46fea…`

这是全部 41,307 个条目里，**除签名/配置/网络安全策略之外，唯一内容发生变化的资源**，所以单独展开。

| 项 | 官方 | 我们 |
|---|---|---|
| 大小 | 5,212 | 5,212（同尺寸，原地改） |
| sha256 | `b027eded4ed0aea597688f321c60df65e334f2e5c435954f6b8726d93d5759dc` | `4d922f2d4bf5ab0c4aa0bee54c35c01654b73a56ad9134f15f5617d4fc312eca` |
| md5 | `0b3a5328ebc5e8cc342e4f7f78f35bed` | `ca1521a9ac037fca872d7d6e398cbf7f` |
| 明文串 | `2021.3.56f2`（Unity 版本）、`GameMainConfig`（资产名） | 同 |

差异定位：

```
差异字节数 : 376 / 5212
差异区段   : 0x1124 .. 0x1458 （约 821 B，即 ~102 条 × 8 字节的记录区）
记录形态    : 8 字节一条，形如 XX 72 YY 57 ZZ 23 06（第2/4/6/8 字节在两边都是 0x72/0x57/0x23/0x06，
              只有第1/3/5/7 字节不同 ⇒ 像一串 64 bit 哈希/ID 的集合）
去重计数    : 官方该区段 95 个互异 8 字节记录；我们只有 61 个  ⇒ 我们这边"多条记录塌缩成了相同值"
```

**判定**：
- 【确证】它是一个名为 `GameMainConfig` 的 Unity 序列化资产，被重打包流程重写/重排过。
- 【确证】它 **不是** 表文件（5,212 B），装不下 `LocalizeGachaShop` 的任何实质内容。
- 【未完成】它内部这 102 条 8 字节记录**具体是什么**（资源清单哈希？脚本/程序集 GUID 表？版本号数组？）—— 只读静态条件下无法定名，需要拿 `libil2cpp.so` 里 `GameMainConfig` 的类型定义反查字段名，或在真机上观察该资产的读取点。
- 【风险提示】"我们这边多条记录塌缩成同一个值"是**不正常的**，它更像是某个重写步骤用同一默认值覆盖了一组条目。**如果这组 8 字节值里恰有"资源/表版本"条目，就会正好造成"版本对不上"的现象。这是当前唯一还需要钉死的地方。**

---

## 8. 交叉线索：表到底从哪来（源码证据，非 APK 证据）

> 以下均为对 `work\ba\srv_src\Shittim-Server` 源码的只读引用，用来解释 §0 的结论，**不构成 APK 层证据**。

1. **设计上不进包**：`work\ba\data\TableCatalog.json` → `"ExcelDB.db" … "isInbuild": false`（16 张表，`isInbuild=true` 的数量为 **0**）。
2. **客户端表位置（在设备上，不在 APK 里）**：
   `srv_src\Shittim-Server\Services\ClientExcelBannerPatchService.cs:181`
   `const string relative = @"BlueArchive_Data\StreamingAssets\PUB\Resource\Preload\TableBundles\ExcelDB.db";`
   （`EventScheduleService.cs:268` 同一路径）
3. **表是"下载"来的**：
   `srv_src\Shittim-Server\Services\ResourceService.cs:45-51`
   `baseUrl = Config.Instance.ServerConfiguration.CdnBaseUrl;` + `"/Preload/TableBundles/ExcelDB.db"`、`"/Preload/TableBundles/Excel.zip"`
4. **★ 最关键的旁证** —— `srv_src\Shittim-Server\Services\ClientItemFilter.cs:13-15`：
   > "The server runs the JP excel table (`/www/wwwroot/ba_srv/Resources/Dumped/ExcelDB.db`, **311,083,008 B**) and the installed client runs the CN one (**160,534,528 B, md5 824ce3a8bee2bb5ae36ada1ac95048f1**). The server table is a SUPERSET…"

   ⇒ **服务端跑的是 311 MB 的日服表，客户端跑的是 160 MB 的国服表**，两者是**不同的 build**（`ExcelTableService.cs:203` 亦有同义注释："The server's ExcelDB and the installed client's TableBundles are NOT the same build")。
5. 本地两份 160 MB 表副本（`data\` 与 `srv_live\…`）**都是 824ce3a8（国服，正确）**；311 MB 的日服表在本机磁盘上**不存在**（全盘 `ExcelDB.db` 仅上面两个命中），它应该在远端 `/www/wwwroot/ba_srv/Resources/Dumped/` 上。

---

## 9. 结论

1. **重打包 APK 不含 `ExcelDB.db`，官方也不含；该表是首次启动时按 `/Preload/TableBundles/ExcelDB.db` 下载到 `BlueArchive_Data\StreamingAssets\PUB\Resource\Preload\TableBundles\` 的。**
2. 因此"重打包把表版本带错"**不是本问题的机制**：包里根本没有表，也就无从"带错"。`No LocalizeKey` 若源于表不一致，问题只可能出在**下载侧 / 服务端侧**，不在 APK 侧。
3. **APK 层的完整性是好的**：41,301/41,307 条目与官方逐字节一致；`resources.arsc` sha256 = `cd8943ae…9eecb86` ✅ 全部构建都满足；`assets/aa/catalog.json` 与官方 CRC 相同（远程资源目录没被动过）。
4. 真正需要继续查的两处，按性价比排序：
   - **a）** 核对**线上服务器** `/www/wwwroot/ba_srv/Resources/Dumped/ExcelDB.db` 的实际大小/sha256：若它是 **311,083,008 B（日服）**，而客户端 `StreamingAssets` 里是 **160,534,528 B @ `824ce3a8`（国服）**，则"表版本不一致"是**确凿的、且发生在服务端与客户端之间**，与 APK 无关。
   - **b）** 把真机上 `...\StreamingAssets\PUB\Resource\Preload\TableBundles\ExcelDB.db` 的实际大小/md5 取回来，和 `824ce3a8` 比 —— 这一步能一次性判定"客户端手里的表到底是不是 824ce3a8"。
5. 唯一 APK 侧遗留疑点：`assets/bin/Data/e37c46fea…` 的 376 字节（102 条 8 字节记录里有 34 条塌缩为重复值），需进一步反查 `GameMainConfig` 的字段定义。

---

## 附录 A：复现命令（全部只读）

```powershell
$py='C:\Users\su\AppData\Local\Programs\DeepSeek Harness\resources\runtime\primary-runtime\dependencies\python\python.exe'

# 1) 列出 APK 条目（不解压）+ 找 db/Excel
@'
import zipfile,sys
z=zipfile.ZipFile(sys.argv[1]); n=z.namelist()
print(len(n),"entries")
print([x for x in n if x.lower().endswith((".db",".sqlite")) or "excel" in x.lower()])
'@ | & $py -X utf8 - "C:\...\BA_noroot_prod_20261118_v1.apk"

# 2) resources.arsc 单独哈希（不落盘）
#    z.read("resources.arsc") -> hashlib.sha256()

# 3) 条目级差异（size+CRC）
#    见 work\ba\data\_tmp\apk_exceldb\_apk_matrix.json
```

## 附录 B：本次产生的文件

| 文件 | 性质 |
|---|---|
| `work\ba\plan\20261119\APK_TABLE_INTEGRITY.md` | **本报告（唯一正式新增文件）** |
| `work\ba\data\_tmp\apk_exceldb\_apk_hashes.json` | 11 条 ≥2 GB 记录（官方原包 1 + 重打包文件 10）的全文件 md5/sha256/大小/mtime |
| `work\ba\data\_tmp\apk_exceldb\_apk_matrix.json` | 13 个包的 arsc 哈希、条目数、增/删/改清单 |
| `work\ba\data\_tmp\apk_exceldb\_apk_small.json` | 11 个小体积中间件的哈希与条目数 |

**未做**：未解压任何 APK；未修改/重打包任何 APK；未写任何 db 文件；未联网；未连接服务器。
