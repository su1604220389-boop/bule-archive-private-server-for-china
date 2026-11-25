# 客户端卡池表取证（APK / TableBundles → ShopRecruitExcel）

> 日期：2026-11-18 22:40（+08:00）
> 只读：未改客户端/服务端/数据库/配置；只在 `%TEMP%` 与 `work/ba/plan/20261118/` 写分析产物。
> 结论标记：**【已证实】** = 直接读到的字节/集合；**【推测】** = 由证据推出的解释。

---

## 0. 一句话结论

**客户端里没有第三套卡池表。** APK 与设备 `TableBundles` 都不含 `ShopRecruitExcel`；客户端唯一的卡池数据容器是**下载来的 `ExcelDB.db`**（`ShopRecruitDBSchema`，532 行 = 官方 529 + `{1,2,3}`）。真正对不上的是**服务端 717 行的 id 段**（`90050002~900900000`）与客户端 id 段（`5000000~99999999`）：交集只有 `{1,2}`。图里的 `DUMMY` 不在这张表里，也不在任何客户端数据/二进制字符串里。

---

## 1. 方法（为什么不是 UnityPy）

| 事实 | 证据 |
|---|---|
| `TableBundles/` 下 6231 个文件全部是 **ZIP**（`PK\x03\x04`），不是 UnityFS | 首个文件 hex `50 4b 03 04 14 00 ...`，解压得单个 `.bytes` |
| 每个 zip 里是**场景/地形** `.bytes`（`sb_01_*`、`*_p01_d`、`*_nodelayer`、`raid_*`） | 抽样 12 个 zip，entry 名全部为 scene 名 |
| 6231 个 zip 共 12931 个唯一 entry；**没有任何** `shoprecruit` / `localizegacha` | 全量扫描 entry 名（脚本见 §7） |
| APK（2,133,476,336 B，41,307 entry）**没有任何** table/excel/bundle 资产；`assets/` 只有音频/Addressables | zip 名单过滤 `table|excel|bundle` → 0 命中 |
| `TableBundles/Catalog/TableCatalog.json` 指向 `Table.ExcelDB.db`（160,534,528 B，`isInbuild=false`）与 18 个 `TablePatchPack_*`（全部 GroundGrid/NodeLayer/Stage） | 目录内 JSON；**没有 Excel 行补丁包** |

⇒ 所以无需 UnityPy（它在 msys python 无 pip；`py -3.12` 有 pip，但本轮用不到）。表数据是**裸 flatbuffer**，直接按 `ShopRecruitExcel` 字段顺序解析即可。

---

## 2. 客户端卡池表在哪、长什么样

容器：`work/ba/data/ExcelDB.db`（sha256 `c49096aa…c5a9`，与服务器 `/www/wwwroot/bapatch/tools/ExcelDB.db` **完全一致**）。
该 DB 每张表是 `(Id, Bytes)`，`Bytes` 是**单行 flatbuffer**。

**`ShopRecruitDBSchema`：532 行**（= 官方 529 + `Id=1,2,3` 三条特殊行）
- id 分布：`1,2,3` + `5000000…99999999`（523 个 7 位 + 6 个 8 位）
- 字段（按 `Schale/FlatData/ShopRecruitExcel.cs` 顺序）：`Id, CategoryType, IsLegacy, OneGachaGoodsId, TenGachaGoodsId, GoodsDevName, DisplayTag, DisplayOrder, GachaBannerPath, VideoId[], LinkedRobbyBannerId, InfoCharacterId[], SalePeriodVisible, SalePeriodFrom, SalePeriodTo, …`
- 样例：`5000000 → Event_Banner_50000`、`7000000 → Event_Banner_70000`、`3 → Event_Banner_3`
- 目前仍在期（含 2099 永久）：10 条 `[5004660, 5004670, 5004680, 5004690, 5004700, 5004710, 7000001, 8000004, 90000000, 99999999]`
- 全表最晚 `SalePeriodTo = 2099-12-31 03:59:59`（仅 3 条），其余到 2025-08 左右

---

## 3. 三方对比（核心表）

| 集合 | 行数 | id 段 | 与客户端交集 |
|---|---|---|---|
| **客户端** `ExcelDB.ShopRecruitDBSchema` | **532** | `{1,2,3} ∪ 5000000…99999999` | — |
| 官方抓包 `_official_shoprecruit_ids.json` | 529 | `5000000…99999999` | **529（客户端 ⊇ 官方，客户端多 1,2,3）** |
| 服务端 `/api/admin/gacha/banners` | **717** | `1 … 900900000`（主体 `90050002~9009xxxxx`） | **仅 2 个：{1, 2}** |

- 官方 ∩ 服务端 = **0**
- 服务端 717 中 **715 个 id 客户端表里根本没有**
- 服务端 id 减 90,000,000 后：**502 个**能在客户端 `LocalizeGachaShopDBSchema` 找到（说明 9e7 是"JP id 偏移"），但只有 **1 个**能在客户端 `ShopRecruitDBSchema` 找到 → **卡池表本身没做这个偏移映射**

⇒ **【已证实】** 客户端卡池表与官方 529 完全一致；服务端 717 是另一套（JP 编号）。

---

## 4. DUMMY 排查（穷举）

| 位置 | 结果 |
|---|---|
| `ShopRecruitDBSchema` 532 行 blob | 无 `DUMMY` |
| `LocalizeGachaShopDBSchema` 1235 行 blob | 无 `DUMMY`（有「新手冲刺招募」等） |
| `LocalizeEtcDBSchema` 5379 行 blob | 无 `DUMMY` |
| 服务端 717 响应 JSON | 无 `DUMMY` |
| 服务端 `/www/wwwroot/bapatch` 数据（json/bytes/db/txt） | 无 `DUMMY` |
| 客户端 `global-metadata.dat`（38,426,024 B） | 仅 `ShopFilterDUMMY_3..7`（商店筛选枚举），无独立 `DUMMY` |
| APK `resources.arsc`、`assets/*.json/*.txt`、`libil2cpp.so` | 无 `DUMMY`（`libunity.so` 只有 Android `TYPE_DUMMY`） |

⇒ **【已证实】** `DUMMY` 不是卡池表/本地化表里的行。
⇒ **【推测】** 它是客户端对「服务端下发的 gacha id 在本机 `LocalizeGachaShop` 里找不到」时的兜底文案（717 条里 215 条按 9e7 偏移也对不上本地化）；兜底字符串可能来自服务端下发的 localize 或运行时拼接，静态包里没找到字面量。

---

## 5. 截图页签对应

| 项 | 值 | 证据 |
|---|---|---|
| 页签文案 | 「新手冲刺招募」/`StartDash`（截图「新手冲刺!!」） | `LocalizeGachaShopDBSchema[GachaShopId=70000]` blob 字符串 |
| 客户端卡池行 | **`Id = 7000000`**，`GachaBannerPath=uis/00_images/banner/Event_Banner_70000`，`2024-02-08 14:00:00 ~ 2025-08-14 13:59:59` | `ShopRecruitDBSchema` 解码 |
| 服务端行 | **`id = 90070000`**，`isNewbie=true`，banner `Event_Banner_70000` | `/api/admin/gacha/banners` |
| 关系 | `90070000 - 90,000,000 = 70000`；`70000` 是**本地化 id**，不是 `ShopRecruit.Id`（后者是 `7000000`） | 集合统计 |

⇒ **【已证实】** 截图页签 ↔ 客户端 `ShopRecruit.Id=7000000` ↔ 服务端 `90070000`。
⇒ **【推测】** 客户端用服务端 id 直接查 `ShopRecruit` 时命中不了（集合证明），`IsCanBuyGacha` 返回 false → 10 连不发请求；页签仍显示是走了本地化/缓存。

---

## 6. 结论（可直接用于定位 bug）

1. **【已证实】** APK 与设备 `TableBundles` 均不含卡池表；客户端卡池唯一来源是 `ExcelDB.db`（532 行，官方 529 + 1/2/3）。
2. **【已证实】** 服务端 717 行的 id 段与客户端表**几乎不相交**（交集 {1,2}）；官方抓包与客户端**完全一致**。
3. **【已证实】** `DUMMY` 不在任何客户端表/本地化/二进制字符串里；截图页签是「新手冲刺」，对应客户端 `7000000`、服务端 `90070000`。
4. **【推测】** 10 连无请求 = 客户端本地 `ShopRecruit` 查不到服务端下发的 id（+/或该行 `SalePeriodTo=2025-08-14` 已过期）→ `IsCanBuyGacha` false。

**修复方向（不在本次改动范围）**：让服务端下发的 gacha id 与客户端 `ShopRecruit.Id` 对齐（把 JP `90000000+id` 映射到 CN `id×100`/客户端 id 段），或让客户端把服务端 717 行合并进本地表。**DUMMY 页签会随 id 对齐自动消失**（本地化按偏移能命中 502/717）。

---

## 7. 复现脚本 / 产物

- 扫描 TableBundles entry 名：`%TEMP%\dump_entries.py`（输出 `%TEMP%\tb_entries.json`，12935 条）
- 解码客户端行：`work/ba/srv_live/20261118_2210/decode_shoprecruit_full.py` → `shoprecruit_full.json`（532 行）
- 服务端 717 行快照：`%TEMP%\server_banners.json`（只读 API 拉取，脚本 base64 走 ssh）
- 对比脚本：`%TEMP%\sets.py`、`%TEMP%\mapping.py`（本次生成，未入库）

## 8. 未决 / 需要 lead 定

1. 客户端**运行时**的 `ExcelDB.db` 是否被整包更新过（备份里没有 `ExcelDB.db`；`TableCatalog` 也没有 Excel 行补丁包）——若要 100% 确证，需要在手机上取 `files/ExcelDB.db` 做 sha 对比。
2. `DUMMY` 的兜底字符串来源仍未找到（静态包穷举为空），建议下一轮抓 `Shop_GachaRecruitList` 响应原文 + 客户端 `LocalizeGachaShop` 查询日志确认。
