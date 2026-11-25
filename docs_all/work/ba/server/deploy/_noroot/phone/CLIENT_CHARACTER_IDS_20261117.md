# 客户端本地 Excel / Addressables 资源盘点 + 客户端认识的**角色 Id**（2026-11-17 22:37–22:45，**只读**）

> 作者：phone-ops（本目录独占）
> 手机：PLR110 / adb 5555（掉线后我用 18080 重新拉起，adbd pid=14808）
> 性质：**只读**（ls / find / du / head / grep）；**没写手机、没 pull 大文件、没动配置、没 kill 游戏**
> 全程未在手机上产生新文件

---

## ★ 最重要的结论（先看这个）

**客户端认识的角色 Id 已经拿到了，而且不用再碰手机 —— 手机上的 `TableBundles` 里就有一份 `ExcelDB.db`，PC 上 11-14 就已经拉过一份（160,534,528 B，sha256 前 16 位 `C49096AA6FDAFEE3`），我直接对它做了只读 SQL 查询：**

```
CharacterDBSchema              **7,223 行**   Id 范围 **10000 – 838060812**（含皮肤/变体）
CharacterAcademyTagsDBSchema   **253 行**     Id 范围 10000 – 26015   ← ★ 与 giveall 的 253 完全吻合
（两张表 Id 都从 10000 起，10000/100 = base 100）
```
**⇒ 客户端"认识"的角色表就是这 253 个（10000–26015 段），已导出成两个纯文本文件（见文末）。**
**⇒ 如果服务端 giveall 发的 253 个角色 Id 落在这 253 个之内，客户端理论上应认识；若超出 26015 或落在缺口里，就会触发"遇到不认识的角色就中止"。**

---

## 1) 数据目录（第 1 步实测）

```
/sdcard/Android/data/com.RoamingStar.BlueArchive/
  drwxrws--- cache      1,015.5 K
  drwxrws--x files      **11.1 G**

/data/data/com.RoamingStar.BlueArchive/            （私有目录，总 9.8 M / 245 文件）
  app_DUHOME / app_[THEMIS] / app_databases / app_textures / app_webview
  cache / code_cache / databases / files / no_backup / shared_prefs
```
`files/` 顶层（14 个子项）：`AssetBundles/`、`TableBundles/`、`MediaPatch/`、`ClientSaveData/`、`catalog_Remote.json|zip|hash`、`manifest.db`、`manifest_backup.db`、`LocalizeConfig.txt`、`GlobalConfig.json`、`LocalConfig.json`、`Hosts`、`il2cpp/` …
（无 Addressables 专用缓存目录；Unity 的 bundle 直接落在 `AssetBundles/`）

## 2) 目录树要点

```
files/AssetBundles/            24,161 个 .bundle  + Catalog/{BundlePackingInfo.json 4,784,849 B, BundlePackingInfo.hash 9 B}
files/TableBundles/            **6,233 个文件 / 435.3 M**  + Catalog/{TableCatalog.json 2,580,787 B, TableCatalog.hash 10 B}
files/MediaPatch/              4.0 G（audio/video/uis/scenario/cafe/Catalog）
```
**⇒ 没有任何目录名含 addressable / aa**

## 3) ★ 关键发现：Excel 资源**不是** Addressables bundle，而是 `TableBundles` 里的 hash 命名文件

```
TableCatalog.json 第一条（原文）：
  "ExcelDB.db": {
    "Name": "ExcelDB.db",
    "Size": 160534528,
    "Crc": "824ce3a8bee2bb5ae36ada1ac95048f1",
    "isInbuild": false,
    "isChanged": false,
    "IsPrologue": true,
    "IsSplitDownload": false,
    "Includes": null
  }
```
**手机上实际存在的对应文件**：
```
/sdcard/Android/data/com.RoamingStar.BlueArchive/files/TableBundles/
    6993339912994747134_824ce3a8bee2bb5ae36ada1ac95048f1     **160,534,528 B    11-13 03:23**
```
**⇒ 文件名规则 = `<某数字Id>_<Crc>`；`ExcelDB.db` 就是这一份 160.5 MB 的 SQLite。**

**按文件名搜索 `excel|character|catalog|localize|table` 的命中结果：**
```
真正的 Excel 类：只有上面那 1 个（hash 命名，不含 "excel" 字样，所以字符串搜索搜不到）
含 character 的：全部是 AssetBundles 里的**角色动画/贴图** bundle（例：
   assets-_mx-characters-ch0181-_mxdependency-animationclips-2026-06-04_assets_all_3094334170.bundle
   uis-01_common-01_character-_mxload-textures-…bundle、cafe-characteranimation-ch0274-…bundle 等）
含 catalog 的：catalog_Remote.json/zip/hash、AssetBundles/Catalog/*、TableBundles/Catalog/*
含 localize 的：只有 LocalizeConfig.txt（164 B）
```
**⇒ `catalog_Remote.json`（81.4 MB）里 `Excel` 与 `Localize` 计数都是 0（上一轮已实测），
但 Excel 数据其实是走 `TableBundles` 这条独立通道下发的，不走 Addressables catalog —— 两者不矛盾。**

## 4) Addressables catalog（`catalog_Remote.json`）

```
表头：{"m_LocatorId":"AddressablesMainContentCatalog", … "m_InternalIds":["{PlatformUtils.AddressableLoadPath}/xxx.bundle", …]}
计数（上一轮实测）：bundle=24164、Gacha=1047、Shop=919、Table=306、**Excel=0、Localize=0**
```
**⇒ catalog 里确实没有 Excel / Localize 这两个 cluster；Excel 通过 TableBundles 走，Localize 缺失是真缺。**

---

## 5) 客户端认识的角色 Id（从 ExcelDB.db 只读查询得到）

### 5.1 `CharacterAcademyTagsDBSchema` —— **253 行**（与 giveall 的 253 完全吻合）
```
Id 范围：10000 – 26015
前 30 个：10000,10001,10002,10003,10004,10005,10006,10007,10008,10009,10010,10011,10012,10013,10014,10015,10016,10017,10018,10019,10020,10021,10022,10023,10024,10025,10026,10027,10028,10029
后 10 个：26006,26007,26008,26009,26010,26011,26012,26013,26014,26015
```
**完整 253 个已导出：`client_character_ids_AcademyTags253.txt`（1,771 B）**

### 5.2 `CharacterDBSchema` —— **7,223 行**（含皮肤/变体/敌人）
```
Id 范围：10000 – 838060812
base(Id/100) 去重后 1,176 个
其中 <30000 的 base：100,101,130,160,190,200,230,260,290,300,360,390,400,490,590
```
**完整 7,223 个已导出：`client_character_ids_CharacterDBSchema.txt`（70,527 B）**

### 5.3 其他相关表（供参考）
```
CharacterLevelDBSchema   列 = [Level, Bytes]（不含 CharacterId）
CharacterAIDBSchema                 70 行
CharacterDialogDBSchema             11,784 行
CharacterDialogEventDBSchema        7,629 行
CharacterDialogSubtitleDBSchema     5,501 行
CharacterIllustCoordinateDBSchema      254 行
CharacterGearDBSchema                  104 行
```
（ExcelDB.db 共 **398 张表**）

---

## 6) 判断（实测 / 推断 分开）

**实测**
```
1. 客户端本地**有** Excel 数据：TableBundles/6993339912994747134_824ce3a8… = ExcelDB.db 160,534,528 B
2. 客户端**没有** Addressables 形式的 Excel/Localize cluster（catalog 里两者计数 0）
3. 客户端认识的"角色"集合：CharacterAcademyTagsDBSchema **253 个（10000–26015）**；
   CharacterDBSchema 7,223 个（含皮肤，Id 到 838060812）
4. 已导出两个 id 清单文件（PC 上，未写手机）
```

**推断（标注强度）**
```
· 【中高】giveall 的 253 个角色如果就是从 CharacterAcademyTagsDBSchema 这类表枚举出来的，
  那它们**应该**都在客户端认识范围内（10000–26015），"不认识的角色 id"这个假设**可能不成立**
· 【中】真正可能炸的是**其它表**：giveall 同时发了「满级/全装备/5 种解锁/通行证」，
  这些会写入 CharacterLevelDBSchema / CharacterGearDBSchema / CharacterPotentialDBSchema 等，
  如果服务端按**自己的 Excel** 发了客户端这张表里**没有的行**（比如 CharacterDBSchema 里不存在的 Id），
  客户端反序列化时会 IndexOutOfRange / null —— 这才是"中止加载"的更合理触发点
· 【不确定】没有客户端日志能证明具体是哪个字段炸的（本机 release 包不打日志）
```

**⇒ 建议下一步（不需要手机）**：把服务端这次 `LoginSync` 实际下发的角色 Id / 装备 Id 集合，
与这两个文件做**差集**：
- `client_character_ids_AcademyTags253.txt`（253 个"正式角色"）
- `client_character_ids_CharacterDBSchema.txt`（7,223 个含皮肤）
**差集为空的表不会炸；差集非空的那张表就是嫌疑人。**

---

## 产物（PC，均在 `_noroot\phone\`）
```
client_character_ids_AcademyTags253.txt          1,771 B    （253 行）
client_character_ids_CharacterDBSchema.txt      70,527 B    （7,223 行）
本文件：CLIENT_CHARACTER_IDS_20261117.md
```

## 边界
```
✅ 只读：ls / find / du / head / grep / sqlite3(mode=ro)
❌ 没写手机、没 pull 大文件、没动配置、没 kill 游戏、没 force-stop
❌ 没清那 3.6 G（按你要求保持原样）
（唯一"操作"：adb 5555 掉线后我用 18080 执行 setprop ctl.start adbd 重新拉起，属通道维护）
```
