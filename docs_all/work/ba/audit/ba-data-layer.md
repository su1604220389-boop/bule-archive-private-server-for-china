# 国服 3.0.2 数据层勘察结论（2026-11-13）

## 一、已确认的事实（全部实测，非推断）

| 项 | 结果 |
|---|---|
| 客户端 `files/TableBundles/` | **6231 个文件 / 433 MB** |
| 其中真正的 SQLite 分片 | **仅 4 个**：7.5 MB、8.5 MB、19 MB、160 MB |
| 最大分片（160 MB，`6993339912994747134_824ce3a8bee2bb5ae36ada1ac95048f1`） | **明文 SQLite**（`SQLite format 3`），**398 张表**，全部为 `*DBSchema`（剧情/本地化/语音字幕类） |
| 8.5 MB 分片 | 明文 SQLite，含 `LevelSkillDataDBSchema` **视图**，聚合物理表 `Ground / Manual / NPC / Student / Enemy / Challenge / TimeAttack / TSS / Common` |
| 玩法数据表（`CharacterDBSchema`、`ItemDBSchema` 等） | **不在客户端任何下载资源里**：`TableBundles` 无、`AssetBundles`（9 GB）grep 无命中、APK 解包目录无命中 |
| 结论 | Steam/PC 端的 `ExcelDB.db` 是**全量单文件**；国服 Android 只下发**剧情/本地化子集**，玩法数值表由客户端内置或走别的通道 |

## 二、对私服的影响

- Shittim-Server 的 `ExcelTableService` 强依赖 `ExcelDB.db` 里的 `CharacterDBSchema` / `ShopRecruitDBSchema` / `LocalizeEtcDBSchema` 等表，**缺表会在启动时抛异常**（实测：`CharacterExcelExt.GetCharacter` 抛在 `SchaleAI.InitializeSchale`）。
- 已加临时开关 `SHITTIM_SKIP_EXCEL=1` 可跳过 key 校验，但**跳不过表数据缺失**。

## 三、已产出的可用件

| 文件 | 说明 |
|---|---|
| `/root/bapatch/data/ExcelDB_full.db` | 4 个 SQLite 分片合并结果（13 张表、52 MB），含 `Student/Enemy/Ground` 等技能表 —— **剧情/技能数据可用** |
| `/sdcard/Download/tb/` | 6231 个分片副本（433 MB，可删） |
| `/root/bapatch/merge_excel.py` | 分片合并脚本（可复用） |

## 四、拿到玩法数值表的三条路

1. **PC/Steam 版 ExcelDB.db** —— 全量表，格式与 Shittim 完全一致。需要一份能解密（或明文）的文件；新版已被 SQLCipher，key 每版轮换，需 `Queuing_GetCryptoKeys` 抓包。
2. **老版本 Android 客户端** —— 2024 年的国际服 `TableBundles/ExcelDB.db` 是**明文**（52pojie 实证），可直接喂给 Shittim。
3. **自建转换器** —— 从 `libil2cpp` 的 Excel 类定义 + 客户端表数据反推，工作量大（周级）。

## 五、当前服务端状态

- 编译通过（.NET 10.0.404，需 `DOTNET_GCHeapHardLimit=0x40000000 DOTNET_gcServer=0`）
- 启动流程：`ResourceService.LoadResources` → `ValidateExcelDbKey`（可由 `SHITTIM_SKIP_EXCEL=1` 跳过）→ `SchaleAI.InitializeSchale`（**需要玩法表，当前卡点**）
- 资源缓存：`https://ba.dn.nexoncdn.co.kr/com.nexon.bluearchive/1f7920cff8224a41`（Global Android 1.96.474931）