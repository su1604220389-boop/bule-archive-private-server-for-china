# 国服 `ExcelDB.db` 全量 Gacha / Recruit / Shop / Localize 表扫描

> **只读**。全程 `sqlite3.connect('file:...?mode=ro&immutable=1', uri=True)` + `PRAGMA query_only=1`，未写库、未改任何已有文件。

| 项 | 值 |
|---|---|
| 库文件 | `work\\ba\\data\\ExcelDB.db` |
| 字节数 | 160,534,528 |
| md5 | `824ce3a8bee2bb5ae36ada1ac95048f1`（脚本内自校验） |
| 表总数 | 398 |
| 名字含 Gacha | 14 |
| 名字含 Localize | 7 |
| 命中关键字表数 | 37 |
| 脚本 | `work\\ba\\scripts\\q_all_gacha_tables.py` |

## 1. 关键字命中表全清单（表名 / 行数 / 列名 / 每列类型）

筛选关键字：`Gacha` `Recruit` `Shop` `Localize` `Text` `Msg`（不区分大小写）。共 **37** 张。

| 表名 | 行数 | 列数 | 列名:类型 | 分类 |
|---|---|---|---|---|
| `BattlePassFlavorTextDBSchema` | 45 | 2 | `GroupId`:INTEGER<br>`Bytes`:BLOB |  |
| `EventContentBoxGachaManageDBSchema` | 204 | 2 | `EventContentId`:INTEGER<br>`Bytes`:BLOB | Gacha |
| `EventContentBoxGachaShopDBSchema` | 2478 | 2 | `EventContentId`:INTEGER<br>`Bytes`:BLOB | Gacha |
| `EventContentCardShopDBSchema` | 835 | 4 | `EventContentId`:INTEGER<br>`Id`:INTEGER<br>`CardGroupId`:INTEGER<br>`Bytes`:BLOB |  |
| `EventContentCardShopModifyDBSchema` | 13 | 2 | `EventContentId`:INTEGER<br>`Bytes`:BLOB |  |
| `EventContentFortuneGachaDBSchema` | 154 | 2 | `FortuneGachaGroupId`:INTEGER<br>`Bytes`:BLOB | Gacha |
| `EventContentFortuneGachaModifyDBSchema` | 9 | 2 | `EventContentId`:INTEGER<br>`Bytes`:BLOB | Gacha |
| `EventContentFortuneGachaShopDBSchema` | 188 | 2 | `EventContentId`:INTEGER<br>`Bytes`:BLOB | Gacha |
| `EventContentShopDBSchema` | 3874 | 2 | `Id`:INTEGER<br>`Bytes`:BLOB |  |
| `EventContentShopInfoDBSchema` | 276 | 3 | `EventContentId`:INTEGER<br>`CategoryType`:NUMERIC<br>`Bytes`:BLOB |  |
| `EventContentShopRefreshDBSchema` | 0 | 2 | `Id`:INTEGER<br>`Bytes`:BLOB |  |
| `GachaCombinedCostDBSchema` | 24 | 2 | `GroupId`:INTEGER<br>`Bytes`:BLOB | Gacha |
| `GachaCraftNodeDBSchema` | 141 | 2 | `ID`:INTEGER<br>`Bytes`:BLOB | Gacha |
| `GachaCraftNodeGroupDBSchema` | 291 | 2 | `NodeId`:INTEGER<br>`Bytes`:BLOB | Gacha |
| `GachaCraftOpenTagDBSchema` | 3 | 2 | `NodeTier`:NUMERIC<br>`Bytes`:BLOB | Gacha |
| `GachaElementDBSchema` | 14922 | 3 | `ID`:INTEGER<br>`GachaGroupID`:INTEGER<br>`Bytes`:BLOB | Gacha |
| `GachaElementRecursiveDBSchema` | 669 | 3 | `ID`:INTEGER<br>`GachaGroupID`:INTEGER<br>`Bytes`:BLOB | Gacha |
| `GachaGroupDBSchema` | 1556 | 2 | `ID`:INTEGER<br>`Bytes`:BLOB | Gacha |
| `GachaSelectPickupGroupDBSchema` | 98 | 2 | `Id`:INTEGER<br>`Bytes`:BLOB | Gacha |
| `LocalizeCharProfileChangeDBSchema` | 4 | 2 | `CharacterId`:INTEGER<br>`Bytes`:BLOB | Localize |
| `LocalizeCharProfileDBSchema` | 264 | 2 | `CharacterId`:INTEGER<br>`Bytes`:BLOB | Localize |
| `LocalizeDBSchema` | 18456 | 2 | `Key`:INTEGER<br>`Bytes`:BLOB | Localize |
| `LocalizeErrorDBSchema` | 429 | 2 | `Key`:INTEGER<br>`Bytes`:BLOB | Localize |
| `LocalizeEtcDBSchema` | 5379 | 2 | `Key`:INTEGER<br>`Bytes`:BLOB | Localize |
| `LocalizeGachaShopDBSchema` | 1235 | 2 | `GachaShopId`:INTEGER<br>`Bytes`:BLOB | Gacha/Localize |
| `LocalizeSkillDBSchema` | 14155 | 2 | `Key`:INTEGER<br>`Bytes`:BLOB | Localize |
| `ShopCashDBSchema` | 656 | 2 | `Id`:INTEGER<br>`Bytes`:BLOB |  |
| `ShopCashScenarioResourceInfoDBSchema` | 504 | 3 | `ScenarioResrouceInfoId`:INTEGER<br>`ShopCashId`:INTEGER<br>`Bytes`:BLOB |  |
| `ShopDBSchema` | 7908 | 3 | `Id`:INTEGER<br>`CategoryType`:NUMERIC<br>`Bytes`:BLOB |  |
| `ShopFilterClassifiedDBSchema` | 1453 | 2 | `GoodsId`:INTEGER<br>`Bytes`:BLOB |  |
| `ShopFreeRecruitDBSchema` | 8 | 2 | `Id`:INTEGER<br>`Bytes`:BLOB | Recruit |
| `ShopFreeRecruitPeriodDBSchema` | 67 | 2 | `ShopFreeRecruitId`:INTEGER<br>`Bytes`:BLOB | Recruit |
| `ShopInfoDBSchema` | 18 | 2 | `CategoryType`:NUMERIC<br>`Bytes`:BLOB |  |
| `ShopRecruitDBSchema` | 532 | 2 | `Id`:INTEGER<br>`Bytes`:BLOB | Recruit |
| `ShopRefreshDBSchema` | 430 | 3 | `Id`:INTEGER<br>`CategoryType`:NUMERIC<br>`Bytes`:BLOB |  |
| `ShopTabGroupDBSchema` | 10 | 2 | `ShopGroupType`:NUMERIC<br>`Bytes`:BLOB |  |
| `SkillSelectExTooltipDBSchema` | 6 | 2 | `GroupId`:INTEGER<br>`Bytes`:BLOB |  |

所有表结构完全统一：**一个（或几个）INTEGER 主键列 + 一个 `Bytes` BLOB 列**，`Bytes` 里是 FlatBuffers table。没有任何表把字段拆成独立 SQL 列——所以文本/数值全部要解 blob。

## 2. 名字含 `Gacha` 的表逐张分析

共 **14** 张。主键列取第一个非 `Bytes` 列。

### 2.1 汇总（行数 / 主键 / 取值分布 / id 段）

| 表名 | 行数 | 主键列 | min | max | 5位段<br>(10000~99999) | 5M段<br>(5000000~5999999) | 9位段<br>(1e8~9.99e8) | 位数分布 |
|---|---|---|---|---|---|---|---|---|
| `EventContentBoxGachaManageDBSchema` | 204 | `EventContentId` | 802 | 70,003 | 115 | 0 | 0 | {3位:89, 5位:115} |
| `EventContentBoxGachaShopDBSchema` | 2478 | `EventContentId` | 802 | 70,003 | 1,357 | 0 | 0 | {3位:1121, 5位:1357} |
| `EventContentFortuneGachaDBSchema` | 154 | `FortuneGachaGroupId` | 1 | 166 | 0 | 0 | 0 | {1位:9, 2位:78, 3位:67} |
| `EventContentFortuneGachaModifyDBSchema` | 9 | `EventContentId` | 809 | 10,832 | 3 | 0 | 0 | {3位:6, 5位:3} |
| `EventContentFortuneGachaShopDBSchema` | 188 | `EventContentId` | 809 | 10,832 | 69 | 0 | 0 | {3位:119, 5位:69} |
| `GachaCombinedCostDBSchema` | 24 | `GroupId` | 101 | 90,101 | 12 | 0 | 0 | {3位:12, 5位:12} |
| `GachaCraftNodeDBSchema` | 141 | `ID` | 0 | 3,110 | 0 | 0 | 0 | {1位:10, 2位:56, 3位:52, 4位:23} |
| `GachaCraftNodeGroupDBSchema` | 291 | `NodeId` | 1 | 3,110 | 0 | 0 | 0 | {1位:60, 2位:116, 3位:61, 4位:54} |
| `GachaCraftOpenTagDBSchema` | 3 | `NodeTier` | 0 | 2 | 0 | 0 | 0 | {1位:3} |
| `GachaElementDBSchema` | 14922 | `ID` | 1 | 90,001,030,000 | 1,432 | 0 | 72 | {1位:9, 2位:78, 3位:790, 4位:8487, 5位:1432, 6位:96, 7位:724, 8位:459, 9位:72, 10位:2443, 11位:332} |
| `GachaElementRecursiveDBSchema` | 669 | `ID` | 1 | 9,908 | 0 | 0 | 0 | {1位:9, 2位:40, 4位:620} |
| `GachaGroupDBSchema` | 1556 | `ID` | 1 | 90,010,031 | 101 | 0 | 0 | {1位:1, 2位:30, 3位:43, 4位:79, 5位:101, 6位:1246, 7位:24, 8位:32} |
| `GachaSelectPickupGroupDBSchema` | 98 | `Id` | 1 | 201,009 | 0 | 0 | 0 | {1位:9, 2位:67, 6位:22} |
| `LocalizeGachaShopDBSchema` | 1235 | `GachaShopId` | 1 | 99,999,999 | 695 | 472 | 0 | {1位:3, 5位:695, 6位:7, 7位:523, 8位:7} |

**读法**：`5位段` 命中说明这张表里混着 legacy 的 5 位 id；`5M段` 命中说明有 500 万级别的 id；`9位段` 命中说明存在 9 位 id。

### 2.2 逐张明细：前 30 个主键值 + 前 10 行 blob 字符串

字符串抽取办法（两路都不依赖固定偏移；1 为主，2 为兜底）：

1. **vtable 驱动**（默认走这条）：读根 table 的 `i32 soffset` 回指 vtable，`vtable=[u16 vtable_len][u16 table_len][u16 field_offset[N]]`，逐行拿到**该行自己的**字段绝对位置，再按 `[u32 len][utf8][0x00]` 取串。结果干净，不含长度前缀残渣；
2. **UTF-8 游程扫描**（兜底）：直接扫连续可打印 UTF-8 游程，完全不需要任何偏移。1 解析失败或解出为空时用它，FlatBuffers 省略默认值导致 vtable 逐行截断也不会漏。

> 因为**没有**用固定偏移，所以不会重演「`0x10~0x2b` 其实是 vtable」那种错位。两路对同一行会得到不同粒度的结果——下表同时给出两路的串数，便于对照。

实测每行的 `vtable_len / table_len` 都不一样（FlatBuffers 省略默认值 + vtable 截断），下面 2.3 会给出证据。

#### `EventContentBoxGachaManageDBSchema` — 204 行，主键 `EventContentId`

- 取值域：`min=802`，`max=70,003`，distinct=28
- 5 位段 `10000~99999`：**115** 行；5M 段 `5000000~5999999`：**0** 行；9 位段：**0** 行
- 位数分布：{3位:89, 5位:115}
- 前 30 个**不同**取值（升序，共 28 个不同值）：`[802, 804, 809, 814, 816, 819, 831, 834, 837, 839, 844, 10802, 10804, 10809, 10814, 10816, 10819, 10834, 10837, 10839, 60000, 60001, 60005, 60011, 60014, 70000, 70001, 70003]`
- 注意：该列有重复（204 行 / 28 个不同值），按 rowid 顺序取前 30 行会全是同一个值，故用去重升序展示。
- 前 10 行 `(vtable_len, table_len, 字段数)` 组合：`(10, 28, 3), (12, 32, 4)`

| # | 主键值 | blob长 | vlen | tlen | vtable串数 | 游程串数 | 前 8 个字符串 |
|---|---|---|---|---|---|---|---|
| 0 | 802 | 48 | 10 | 28 | 0 | 0 | *(无可打印字符串)* |
| 1 | 802 | 48 | 10 | 28 | 0 | 0 | *(无可打印字符串)* |
| 2 | 802 | 48 | 10 | 28 | 0 | 0 | *(无可打印字符串)* |
| 3 | 802 | 48 | 10 | 28 | 0 | 0 | *(无可打印字符串)* |
| 4 | 802 | 48 | 10 | 28 | 0 | 0 | *(无可打印字符串)* |
| 5 | 802 | 48 | 10 | 28 | 0 | 0 | *(无可打印字符串)* |
| 6 | 802 | 48 | 12 | 32 | 0 | 0 | *(无可打印字符串)* |
| 7 | 804 | 48 | 10 | 28 | 0 | 0 | *(无可打印字符串)* |
| 8 | 804 | 48 | 10 | 28 | 0 | 0 | *(无可打印字符串)* |
| 9 | 804 | 48 | 10 | 28 | 0 | 0 | *(无可打印字符串)* |

#### `EventContentBoxGachaShopDBSchema` — 2,478 行，主键 `EventContentId`

- 取值域：`min=802`，`max=70,003`，distinct=28
- 5 位段 `10000~99999`：**1,357** 行；5M 段 `5000000~5999999`：**0** 行；9 位段：**0** 行
- 位数分布：{3位:1121, 5位:1357}
- 前 30 个**不同**取值（升序，共 28 个不同值）：`[802, 804, 809, 814, 816, 819, 831, 834, 837, 839, 844, 10802, 10804, 10809, 10814, 10816, 10819, 10834, 10837, 10839, 60000, 60001, 60005, 60011, 60014, 70000, 70001, 70003]`
- 注意：该列有重复（2,478 行 / 28 个不同值），按 rowid 顺序取前 30 行会全是同一个值，故用去重升序展示。
- 前 10 行 `(vtable_len, table_len, 字段数)` 组合：`(20, 56, 7), (20, 56, 6)`

| # | 主键值 | blob长 | vlen | tlen | vtable串数 | 游程串数 | 前 8 个字符串 |
|---|---|---|---|---|---|---|---|
| 0 | 802 | 96 | 20 | 56 | 0 | 0 | *(无可打印字符串)* |
| 1 | 802 | 96 | 20 | 56 | 0 | 0 | *(无可打印字符串)* |
| 2 | 802 | 96 | 20 | 56 | 0 | 0 | *(无可打印字符串)* |
| 3 | 802 | 96 | 20 | 56 | 0 | 0 | *(无可打印字符串)* |
| 4 | 802 | 96 | 20 | 56 | 0 | 0 | *(无可打印字符串)* |
| 5 | 802 | 96 | 20 | 56 | 0 | 0 | *(无可打印字符串)* |
| 6 | 802 | 96 | 20 | 56 | 0 | 0 | *(无可打印字符串)* |
| 7 | 802 | 96 | 20 | 56 | 0 | 0 | *(无可打印字符串)* |
| 8 | 802 | 96 | 20 | 56 | 0 | 0 | *(无可打印字符串)* |
| 9 | 802 | 96 | 20 | 56 | 0 | 0 | *(无可打印字符串)* |

#### `EventContentFortuneGachaDBSchema` — 154 行，主键 `FortuneGachaGroupId`

- 取值域：`min=1`，`max=166`，distinct=154
- 5 位段 `10000~99999`：**0** 行；5M 段 `5000000~5999999`：**0** 行；9 位段：**0** 行
- 位数分布：{1位:9, 2位:78, 3位:67}
- 前 30 个**不同**取值（升序，共 154 个不同值）：`[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 30, 31, 32, 33, 34, 35]`
- 前 10 行 `(vtable_len, table_len, 字段数)` 组合：`(12, 20, 4)`

| # | 主键值 | blob长 | vlen | tlen | vtable串数 | 游程串数 | 前 8 个字符串 |
|---|---|---|---|---|---|---|---|
| 0 | 1 | 116 | 12 | 20 | 1 | 1 | `uis/01_common/27_eventcontent/omikujiimg/img_o…` |
| 1 | 2 | 116 | 12 | 20 | 1 | 1 | `uis/01_common/27_eventcontent/omikujiimg/img_o…` |
| 2 | 3 | 116 | 12 | 20 | 1 | 1 | `uis/01_common/27_eventcontent/omikujiimg/img_o…` |
| 3 | 4 | 116 | 12 | 20 | 2 | 1 | `uis/01_common/27_eventcontent/omikujiimg/img_o…`<br>`uis/01_common/27_eventcontent/omikujiimg/img_o…` |
| 4 | 5 | 116 | 12 | 20 | 1 | 1 | `uis/01_common/27_eventcontent/omikujiimg/img_o…` |
| 5 | 6 | 116 | 12 | 20 | 1 | 1 | `uis/01_common/27_eventcontent/omikujiimg/img_o…` |
| 6 | 7 | 116 | 12 | 20 | 1 | 2 | `uis/01_common/27_eventcontent/omikujiimg/img_o…` |
| 7 | 8 | 116 | 12 | 20 | 1 | 1 | `uis/01_common/27_eventcontent/omikujiimg/img_o…` |
| 8 | 9 | 116 | 12 | 20 | 1 | 1 | `uis/01_common/27_eventcontent/omikujiimg/img_o…` |
| 9 | 10 | 116 | 12 | 20 | 1 | 1 | `uis/01_common/27_eventcontent/omikujiimg/img_o…` |

#### `EventContentFortuneGachaModifyDBSchema` — 9 行，主键 `EventContentId`

- 取值域：`min=809`，`max=10,832`，distinct=9
- 5 位段 `10000~99999`：**3** 行；5M 段 `5000000~5999999`：**0** 行；9 位段：**0** 行
- 位数分布：{3位:6, 5位:3}
- 前 30 个**不同**取值（升序，共 9 个不同值）：`[809, 820, 832, 845, 851, 853, 10809, 10820, 10832]`
- 前 10 行 `(vtable_len, table_len, 字段数)` 组合：`(18, 32, 7)`

| # | 主键值 | blob长 | vlen | tlen | vtable串数 | 游程串数 | 前 8 个字符串 |
|---|---|---|---|---|---|---|---|
| 0 | 809 | 264 | 18 | 32 | 4 | 4 | `uieventfortunegachashop_809`<br>`UIs/01_Common/27_EventContent/OmikujiImg/Img_O…`<br>`UIs/01_Common/27_EventContent/OmikujiImg/Img_O…`<br>`UIEventFortuneGachaShop_Title_809` |
| 1 | 820 | 272 | 18 | 32 | 4 | 4 | `uieventfortunegachashop_809`<br>`UIs/01_Common/27_EventContent/OmikujiImg/Img_O…`<br>`UIs/01_Common/27_EventContent/OmikujiImg/Img_O…`<br>`UIEventFortuneGachaShop_Title_820` |
| 2 | 832 | 288 | 18 | 32 | 4 | 4 | `UIEventFortuneGachaShop_832`<br>`UIs/01_Common/27_EventContent/OmikujiImg/832/I…`<br>`UIs/01_Common/27_EventContent/OmikujiImg/832/I…`<br>`UIEventFortuneGachaShop_Title_832` |
| 3 | 845 | 216 | 18 | 32 | 3 | 3 | `UIEventFortuneGachaShop_845`<br>`UIs/01_Common/27_EventContent/OmikujiImg/845/I…`<br>`UIEventFortuneGachaShop_Title_845` |
| 4 | 851 | 216 | 18 | 32 | 3 | 3 | `UIEventFortuneGachaShop_851`<br>`UIs/01_Common/27_EventContent/OmikujiImg/851/I…`<br>`UIEventFortuneGachaShop_Title_851` |
| 5 | 853 | 216 | 18 | 32 | 3 | 3 | `UIEventFortuneGachaShop_853`<br>`UIs/01_Common/27_EventContent/OmikujiImg/853/I…`<br>`UIEventFortuneGachaShop_Title_853` |
| 6 | 10809 | 264 | 18 | 32 | 4 | 4 | `uieventfortunegachashop_809`<br>`UIs/01_Common/27_EventContent/OmikujiImg/Img_O…`<br>`UIs/01_Common/27_EventContent/OmikujiImg/Img_O…`<br>`UIEventFortuneGachaShop_Title_809` |
| 7 | 10820 | 272 | 18 | 32 | 4 | 4 | `uieventfortunegachashop_809`<br>`UIs/01_Common/27_EventContent/OmikujiImg/Img_O…`<br>`UIs/01_Common/27_EventContent/OmikujiImg/Img_O…`<br>`UIEventFortuneGachaShop_Title_820` |
| 8 | 10832 | 288 | 18 | 32 | 4 | 4 | `UIEventFortuneGachaShop_832`<br>`UIs/01_Common/27_EventContent/OmikujiImg/832/I…`<br>`UIs/01_Common/27_EventContent/OmikujiImg/832/I…`<br>`UIEventFortuneGachaShop_Title_832` |

#### `EventContentFortuneGachaShopDBSchema` — 188 行，主键 `EventContentId`

- 取值域：`min=809`，`max=10,832`，distinct=9
- 5 位段 `10000~99999`：**69** 行；5M 段 `5000000~5999999`：**0** 行；9 位段：**0** 行
- 位数分布：{3位:119, 5位:69}
- 前 30 个**不同**取值（升序，共 9 个不同值）：`[809, 820, 832, 845, 851, 853, 10809, 10820, 10832]`
- 注意：该列有重复（188 行 / 9 个不同值），按 rowid 顺序取前 30 行会全是同一个值，故用去重升序展示。
- 前 10 行 `(vtable_len, table_len, 字段数)` 组合：`(28, 56, 9), (28, 64, 10)`

| # | 主键值 | blob长 | vlen | tlen | vtable串数 | 游程串数 | 前 8 个字符串 |
|---|---|---|---|---|---|---|---|
| 0 | 809 | 128 | 28 | 56 | 1 | 0 | `\n` |
| 1 | 809 | 128 | 28 | 56 | 1 | 0 | `\n` |
| 2 | 809 | 128 | 28 | 56 | 1 | 0 | `\n` |
| 3 | 809 | 128 | 28 | 56 | 1 | 0 | `\n` |
| 4 | 809 | 176 | 28 | 64 | 0 | 0 | *(无可打印字符串)* |
| 5 | 809 | 176 | 28 | 64 | 0 | 0 | *(无可打印字符串)* |
| 6 | 809 | 176 | 28 | 64 | 0 | 0 | *(无可打印字符串)* |
| 7 | 809 | 176 | 28 | 64 | 0 | 0 | *(无可打印字符串)* |
| 8 | 809 | 176 | 28 | 64 | 0 | 0 | *(无可打印字符串)* |
| 9 | 809 | 176 | 28 | 64 | 0 | 0 | *(无可打印字符串)* |

#### `GachaCombinedCostDBSchema` — 24 行，主键 `GroupId`

- 取值域：`min=101`，`max=90,101`，distinct=2
- 5 位段 `10000~99999`：**12** 行；5M 段 `5000000~5999999`：**0** 行；9 位段：**0** 行
- 位数分布：{3位:12, 5位:12}
- 前 30 个**不同**取值（升序，共 2 个不同值）：`[101, 90101]`
- 注意：该列有重复（24 行 / 2 个不同值），按 rowid 顺序取前 30 行会全是同一个值，故用去重升序展示。
- 前 10 行 `(vtable_len, table_len, 字段数)` 组合：`(12, 36, 4), (18, 60, 7)`

| # | 主键值 | blob长 | vlen | tlen | vtable串数 | 游程串数 | 前 8 个字符串 |
|---|---|---|---|---|---|---|---|
| 0 | 101 | 56 | 12 | 36 | 0 | 0 | *(无可打印字符串)* |
| 1 | 101 | 56 | 12 | 36 | 0 | 0 | *(无可打印字符串)* |
| 2 | 101 | 88 | 18 | 60 | 0 | 0 | *(无可打印字符串)* |
| 3 | 101 | 88 | 18 | 60 | 0 | 0 | *(无可打印字符串)* |
| 4 | 101 | 88 | 18 | 60 | 0 | 0 | *(无可打印字符串)* |
| 5 | 101 | 88 | 18 | 60 | 0 | 0 | *(无可打印字符串)* |
| 6 | 101 | 88 | 18 | 60 | 0 | 0 | *(无可打印字符串)* |
| 7 | 101 | 88 | 18 | 60 | 0 | 0 | *(无可打印字符串)* |
| 8 | 101 | 88 | 18 | 60 | 0 | 0 | *(无可打印字符串)* |
| 9 | 101 | 88 | 18 | 60 | 0 | 0 | *(无可打印字符串)* |

#### `GachaCraftNodeDBSchema` — 141 行，主键 `ID`

- 取值域：`min=0`，`max=3,110`，distinct=141
- 5 位段 `10000~99999`：**0** 行；5M 段 `5000000~5999999`：**0** 行；9 位段：**0** 行
- 位数分布：{1位:10, 2位:56, 3位:52, 4位:23}
- 前 30 个**不同**取值（升序，共 141 个不同值）：`[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29]`
- 前 10 行 `(vtable_len, table_len, 字段数)` 组合：`(16, 12, 2), (18, 56, 7)`

| # | 主键值 | blob长 | vlen | tlen | vtable串数 | 游程串数 | 前 8 个字符串 |
|---|---|---|---|---|---|---|---|
| 0 | 0 | 84 | 16 | 12 | 1 | 1 | `UIs/01_Common/19_CraftDuration/CraftNode_Base` |
| 1 | 1 | 136 | 18 | 56 | 1 | 1 | `UIs/01_Common/19_CraftDuration/CraftNode_Rairt…` |
| 2 | 2 | 136 | 18 | 56 | 1 | 1 | `UIs/01_Common/19_CraftDuration/CraftNode_Rairt…` |
| 3 | 3 | 136 | 18 | 56 | 1 | 1 | `UIs/01_Common/19_CraftDuration/CraftNode_Rairt…` |
| 4 | 4 | 136 | 18 | 56 | 1 | 2 | `UIs/01_Common/19_CraftDuration/CraftNode_Rairt…` |
| 5 | 5 | 136 | 18 | 56 | 1 | 1 | `UIs/01_Common/19_CraftDuration/CraftNode_Item` |
| 6 | 6 | 136 | 18 | 56 | 1 | 1 | `UIs/01_Common/19_CraftDuration/CraftNode_Item` |
| 7 | 7 | 136 | 18 | 56 | 1 | 1 | `UIs/01_Common/19_CraftDuration/CraftNode_Item` |
| 8 | 8 | 136 | 18 | 56 | 1 | 1 | `UIs/01_Common/19_CraftDuration/CraftNode_Item` |
| 9 | 9 | 136 | 18 | 56 | 1 | 1 | `UIs/01_Common/19_CraftDuration/CraftNode_Item` |

#### `GachaCraftNodeGroupDBSchema` — 291 行，主键 `NodeId`

- 取值域：`min=1`，`max=3,110`，distinct=144
- 5 位段 `10000~99999`：**0** 行；5M 段 `5000000~5999999`：**0** 行；9 位段：**0** 行
- 位数分布：{1位:60, 2位:116, 3位:61, 4位:54}
- 前 30 个**不同**取值（升序，共 144 个不同值）：`[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30]`
- 注意：该列有重复（291 行 / 144 个不同值），按 rowid 顺序取前 30 行会全是同一个值，故用去重升序展示。
- 前 10 行 `(vtable_len, table_len, 字段数)` 组合：`(10, 28, 3)`

| # | 主键值 | blob长 | vlen | tlen | vtable串数 | 游程串数 | 前 8 个字符串 |
|---|---|---|---|---|---|---|---|
| 0 | 1 | 48 | 10 | 28 | 0 | 0 | *(无可打印字符串)* |
| 1 | 1 | 48 | 10 | 28 | 0 | 0 | *(无可打印字符串)* |
| 2 | 1 | 48 | 10 | 28 | 0 | 0 | *(无可打印字符串)* |
| 3 | 1 | 48 | 10 | 28 | 0 | 0 | *(无可打印字符串)* |
| 4 | 1 | 48 | 10 | 28 | 0 | 0 | *(无可打印字符串)* |
| 5 | 2 | 48 | 10 | 28 | 0 | 0 | *(无可打印字符串)* |
| 6 | 2 | 48 | 10 | 28 | 0 | 0 | *(无可打印字符串)* |
| 7 | 2 | 48 | 10 | 28 | 0 | 0 | *(无可打印字符串)* |
| 8 | 2 | 48 | 10 | 28 | 0 | 0 | *(无可打印字符串)* |
| 9 | 2 | 48 | 10 | 28 | 0 | 0 | *(无可打印字符串)* |

#### `GachaCraftOpenTagDBSchema` — 3 行，主键 `NodeTier`

- 取值域：`min=0`，`max=2`，distinct=3
- 5 位段 `10000~99999`：**0** 行；5M 段 `5000000~5999999`：**0** 行；9 位段：**0** 行
- 位数分布：{1位:3}
- 前 30 个**不同**取值（升序，共 3 个不同值）：`[0, 1, 2]`
- 前 10 行 `(vtable_len, table_len, 字段数)` 组合：`(8, 8, 1), (8, 12, 2)`

| # | 主键值 | blob长 | vlen | tlen | vtable串数 | 游程串数 | 前 8 个字符串 |
|---|---|---|---|---|---|---|---|
| 0 | 0 | 28 | 8 | 8 | 0 | 0 | *(无可打印字符串)* |
| 1 | 1 | 48 | 8 | 12 | 0 | 0 | *(无可打印字符串)* |
| 2 | 2 | 76 | 8 | 12 | 0 | 0 | *(无可打印字符串)* |

#### `GachaElementDBSchema` — 14,922 行，主键 `ID`

- 取值域：`min=1`，`max=90,001,030,000`，distinct=14,922
- 5 位段 `10000~99999`：**1,432** 行；5M 段 `5000000~5999999`：**0** 行；9 位段：**72** 行
- 位数分布：{1位:9, 2位:78, 3位:790, 4位:8487, 5位:1432, 6位:96, 7位:724, 8位:459, 9位:72, 10位:2443, 11位:332}
- 前 30 个**不同**取值（升序，共 14,922 个不同值）：`[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30]`
- 附加 id 列 `GachaGroupID`：min=11 max=90,010,031，5位段=550 5M段=0 9位段=0
- 前 10 行 `(vtable_len, table_len, 字段数)` 组合：`(22, 56, 9)`

| # | 主键值 | blob长 | vlen | tlen | vtable串数 | 游程串数 | 前 8 个字符串 |
|---|---|---|---|---|---|---|---|
| 0 | 1 | 88 | 22 | 56 | 0 | 0 | *(无可打印字符串)* |
| 1 | 2 | 88 | 22 | 56 | 0 | 0 | *(无可打印字符串)* |
| 2 | 3 | 88 | 22 | 56 | 0 | 0 | *(无可打印字符串)* |
| 3 | 4 | 88 | 22 | 56 | 0 | 0 | *(无可打印字符串)* |
| 4 | 5 | 88 | 22 | 56 | 0 | 0 | *(无可打印字符串)* |
| 5 | 6 | 88 | 22 | 56 | 0 | 0 | *(无可打印字符串)* |
| 6 | 7 | 88 | 22 | 56 | 0 | 0 | *(无可打印字符串)* |
| 7 | 8 | 88 | 22 | 56 | 0 | 0 | *(无可打印字符串)* |
| 8 | 9 | 88 | 22 | 56 | 0 | 0 | *(无可打印字符串)* |
| 9 | 10 | 88 | 22 | 56 | 0 | 0 | *(无可打印字符串)* |

#### `GachaElementRecursiveDBSchema` — 669 行，主键 `ID`

- 取值域：`min=1`，`max=9,908`，distinct=669
- 5 位段 `10000~99999`：**0** 行；5M 段 `5000000~5999999`：**0** 行；9 位段：**0** 行
- 位数分布：{1位:9, 2位:40, 4位:620}
- 前 30 个**不同**取值（升序，共 669 个不同值）：`[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30]`
- 附加 id 列 `GachaGroupID`：min=1 max=9,000,099，5位段=0 5M段=0 9位段=0
- 前 10 行 `(vtable_len, table_len, 字段数)` 组合：`(20, 52, 7)`

| # | 主键值 | blob长 | vlen | tlen | vtable串数 | 游程串数 | 前 8 个字符串 |
|---|---|---|---|---|---|---|---|
| 0 | 1 | 80 | 20 | 52 | 0 | 0 | *(无可打印字符串)* |
| 1 | 2 | 80 | 20 | 52 | 0 | 0 | *(无可打印字符串)* |
| 2 | 3 | 80 | 20 | 52 | 0 | 0 | *(无可打印字符串)* |
| 3 | 4 | 80 | 20 | 52 | 0 | 0 | *(无可打印字符串)* |
| 4 | 5 | 80 | 20 | 52 | 0 | 0 | *(无可打印字符串)* |
| 5 | 6 | 80 | 20 | 52 | 0 | 0 | *(无可打印字符串)* |
| 6 | 7 | 80 | 20 | 52 | 0 | 0 | *(无可打印字符串)* |
| 7 | 8 | 80 | 20 | 52 | 0 | 0 | *(无可打印字符串)* |
| 8 | 9 | 80 | 20 | 52 | 0 | 0 | *(无可打印字符串)* |
| 9 | 10 | 80 | 20 | 52 | 0 | 0 | *(无可打印字符串)* |

#### `GachaGroupDBSchema` — 1,556 行，主键 `ID`

- 取值域：`min=1`，`max=90,010,031`，distinct=1,556
- 5 位段 `10000~99999`：**101** 行；5M 段 `5000000~5999999`：**0** 行；9 位段：**0** 行
- 位数分布：{1位:1, 2位:30, 3位:43, 4位:79, 5位:101, 6位:1246, 7位:24, 8位:32}
- 前 30 个**不同**取值（升序，共 1,556 个不同值）：`[1, 10, 11, 12, 13, 20, 30, 31, 32, 33, 50, 51, 52, 53, 59, 60, 61, 62, 63, 69, 70, 71, 72, 73, 79, 80, 81, 82, 83, 89]`
- 前 10 行 `(vtable_len, table_len, 字段数)` 组合：`(12, 28, 4), (12, 24, 4), (12, 24, 3), (12, 20, 3)`

| # | 主键值 | blob长 | vlen | tlen | vtable串数 | 游程串数 | 前 8 个字符串 |
|---|---|---|---|---|---|---|---|
| 0 | 1 | 64 | 12 | 28 | 1 | 2 | `제조 가챠` |
| 1 | 10 | 64 | 12 | 24 | 1 | 2 | `튜토리얼 가챠` |
| 2 | 11 | 72 | 12 | 24 | 1 | 2 | `튜토리얼 가챠 R` |
| 3 | 12 | 72 | 12 | 24 | 2 | 3 | `튜토리얼 가챠 SR`<br>`튜토리얼 가챠 SR` |
| 4 | 13 | 72 | 12 | 24 | 1 | 3 | `튜토리얼 가챠 SSR` |
| 5 | 30 | 72 | 12 | 24 | 1 | 3 | `튜토리얼 선별 가챠` |
| 6 | 31 | 80 | 12 | 24 | 1 | 3 | `튜토리얼 선별 가챠 R` |
| 7 | 32 | 80 | 12 | 24 | 1 | 4 | `튜토리얼 선별 가챠 SR` |
| 8 | 33 | 80 | 12 | 24 | 1 | 4 | `튜토리얼 선별 가챠 SSR` |
| 9 | 20 | 96 | 12 | 20 | 1 | 5 | `레거시 시즌용 더미 학생모집(스즈미)` |

#### `GachaSelectPickupGroupDBSchema` — 98 行，主键 `Id`

- 取值域：`min=1`，`max=201,009`，distinct=98
- 5 位段 `10000~99999`：**0** 行；5M 段 `5000000~5999999`：**0** 行；9 位段：**0** 行
- 位数分布：{1位:9, 2位:67, 6位:22}
- 前 30 个**不同**取值（升序，共 98 个不同值）：`[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30]`
- 前 10 行 `(vtable_len, table_len, 字段数)` 组合：`(10, 28, 3)`

| # | 主键值 | blob长 | vlen | tlen | vtable串数 | 游程串数 | 前 8 个字符串 |
|---|---|---|---|---|---|---|---|
| 0 | 1 | 48 | 10 | 28 | 0 | 0 | *(无可打印字符串)* |
| 1 | 2 | 48 | 10 | 28 | 0 | 0 | *(无可打印字符串)* |
| 2 | 3 | 48 | 10 | 28 | 0 | 0 | *(无可打印字符串)* |
| 3 | 4 | 48 | 10 | 28 | 0 | 0 | *(无可打印字符串)* |
| 4 | 5 | 48 | 10 | 28 | 0 | 0 | *(无可打印字符串)* |
| 5 | 6 | 48 | 10 | 28 | 0 | 0 | *(无可打印字符串)* |
| 6 | 7 | 48 | 10 | 28 | 0 | 0 | *(无可打印字符串)* |
| 7 | 8 | 48 | 10 | 28 | 0 | 0 | *(无可打印字符串)* |
| 8 | 9 | 48 | 10 | 28 | 0 | 0 | *(无可打印字符串)* |
| 9 | 10 | 48 | 10 | 28 | 0 | 0 | *(无可打印字符串)* |

#### `LocalizeGachaShopDBSchema` — 1,235 行，主键 `GachaShopId`

- 取值域：`min=1`，`max=99,999,999`，distinct=1,235
- 5 位段 `10000~99999`：**695** 行；5M 段 `5000000~5999999`：**472** 行；9 位段：**0** 行
- 位数分布：{1位:3, 5位:695, 6位:7, 7位:523, 8位:7}
- 前 30 个**不同**取值（升序，共 1,235 个不同值）：`[1, 2, 3, 50000, 50001, 50002, 50003, 50004, 50005, 50010, 50011, 50012, 50013, 50014, 50015, 50020, 50021, 50022, 50023, 50024, 50025, 50030, 50031, 50032, 50033, 50040, 50041, 50042, 50043, 50044]`
- 前 10 行 `(vtable_len, table_len, 字段数)` 组合：`(24, 48, 10), (24, 52, 10)`

| # | 主键值 | blob长 | vlen | tlen | vtable串数 | 游程串数 | 前 8 个字符串 |
|---|---|---|---|---|---|---|---|
| 0 | 1 | 528 | 24 | 48 | 8 | 23 | `限时招募`<br>`픽업 모집`<br>`限时招募！`<br>`픽업 모집!`<br>`来招募更多个性迥异的成员吧！`<br>`다양한 학생들을 모집하세요!`<br>`选择招募10次，必定获得1名2★以上成员！\n※若出现已拥有的成员则会转换为神名精髓与该成员…`<br>`10회 모집 시, ★2 이상 학생 1명 확정!\n※ 이미 모집한 학생은 엘리그마로 …` |
| 1 | 2 | 528 | 24 | 48 | 8 | 23 | `长期招募`<br>`상시 모집`<br>`长期招募`<br>`상시 모집`<br>`来招募更多个性迥异的成员吧！`<br>`다양한 학생들을 모집하세요!`<br>`选择招募10次，必定获得1名2★以上成员！\n※若出现已拥有的成员则会转换为神名精髓与该成员…`<br>`10회 모집 시, ★2 이상 학생 1명 확정!\n※ 이미 모집한 학생은 엘리그마로 …` |
| 2 | 3 | 536 | 24 | 48 | 8 | 23 | `长期招募`<br>`튜토리얼 모집`<br>`长期招募`<br>`튜토리얼 모집`<br>`来招募更多个性迥异的成员吧！`<br>`다양한 학생들을 모집하세요!`<br>`选择招募10次，必定获得1名2★以上成员！\n※若出现已拥有的成员则会转换为神名精髓与该成员…`<br>`10회 모집 시, ★2 이상 학생 1명 확정!\n※ 이미 모집한 학생은 엘리그마로 …` |
| 3 | 50000 | 528 | 24 | 48 | 8 | 23 | `长期招募`<br>`상시 모집`<br>`长期招募`<br>`상시 모집`<br>`来招募更多个性迥异的成员吧！`<br>`다양한 학생들을 모집하세요!`<br>`选择招募10次，必定获得1名2★以上成员！\n※若出现已拥有的成员则会转换为神名精髓与该成员…`<br>`10회 모집 시, ★2 이상 학생 1명 확정!\n※ 이미 모집한 학생은 엘리그마로 …` |
| 4 | 50001 | 528 | 24 | 52 | 8 | 26 | `限时招募`<br>`픽업 모집`<br>`限时招募！`<br>`픽업 모집!`<br>`切里诺（3★）招募概率提升！`<br>`체리노(★3 ) 출현 확률 UP!`<br>`选择招募10次，必定获得1名2★以上成员！\n※若出现已拥有的成员则会转换为神名精髓与该成员…`<br>`10회 모집 시, ★2 이상 학생 1명 확정!\n※ 이미 모집한 학생은 엘리그마로 …` |
| 5 | 50002 | 528 | 24 | 48 | 8 | 23 | `长期招募`<br>`상시 모집`<br>`长期招募`<br>`상시 모집`<br>`来招募更多个性迥异的成员吧！`<br>`다양한 학생들을 모집하세요!`<br>`选择招募10次，必定获得1名2★以上成员！\n※若出现已拥有的成员则会转换为神名精髓与该成员…`<br>`10회 모집 시, ★2 이상 학생 1명 확정!\n※ 이미 모집한 학생은 엘리그마로 …` |
| 6 | 50003 | 544 | 24 | 48 | 8 | 27 | `长期招募`<br>`픽업 모집`<br>`长期招募`<br>`픽업 모집!`<br>`来招募更多个性迥异的成员吧！`<br>`시로코(★3 ) / 호시노(★3 ) 출현 확률 UP!`<br>`选择招募10次，必定获得1名2★以上成员！\n※若出现已拥有的成员则会转换为神名精髓与该成员…`<br>`10회 모집 시, ★2 이상 학생 1명 확정!\n※ 이미 모집한 학생은 엘리그마로 …` |
| 7 | 50004 | 544 | 24 | 52 | 8 | 26 | `限时招募`<br>`상시 모집`<br>`限时招募！`<br>`상시 모집`<br>`白子（3★）/星野（3★）招募概率提升！`<br>`다양한 학생들을 모집하세요!`<br>`选择招募10次，必定获得1名2★以上成员！\n※若出现已拥有的成员则会转换为神名精髓与该成员…`<br>`10회 모집 시, ★2 이상 학생 1명 확정!\n※ 이미 모집한 학생은 엘리그마로 …` |
| 8 | 50005 | 520 | 24 | 48 | 8 | 26 | `限时招募`<br>`픽업 모집`<br>`限时招募！`<br>`픽업 모집!`<br>`真白（3★）招募概率提升！`<br>`마시로(★3 ) 출현 확률 UP!`<br>`选择招募10次，必定获得1名2★以上成员！\n※若出现已拥有的成员则会转换为神名精髓与该成员…`<br>`10회 모집 시, ★2 이상 학생 1명 확정!\n※ 이미 모집한 학생은 엘리그마로 …` |
| 9 | 50010 | 528 | 24 | 48 | 8 | 23 | `长期招募`<br>`상시 모집`<br>`长期招募`<br>`상시 모집`<br>`来招募更多个性迥异的成员吧！`<br>`다양한 학생들을 모집하세요!`<br>`选择招募10次，必定获得1名2★以上成员！\n※若出现已拥有的成员则会转换为神名精髓与该成员…`<br>`10회 모집 시, ★2 이상 학생 1명 확정!\n※ 이미 모집한 학생은 엘리그마로 …` |

### 2.3 证据：同一张表内 vtable 长度逐行不同

| 表 | 不同布局组合数 | 最常见的 (vtable_len / table_len / 字段数) |
|---|---|---|
| `EventContentBoxGachaManageDBSchema` | 2 | vl=10/tl=28/f=3×176, vl=12/tl=32/f=4×28 |
| `EventContentBoxGachaShopDBSchema` | 2 | vl=20/tl=56/f=6×2274, vl=20/tl=56/f=7×204 |
| `EventContentFortuneGachaDBSchema` | 1 | vl=12/tl=20/f=4×154 |
| `EventContentFortuneGachaModifyDBSchema` | 1 | vl=18/tl=32/f=7×9 |
| `EventContentFortuneGachaShopDBSchema` | 3 | vl=28/tl=64/f=10×124, vl=28/tl=68/f=11×40, vl=28/tl=56/f=9×24 |
| `GachaCombinedCostDBSchema` | 3 | vl=18/tl=60/f=7×18, vl=12/tl=36/f=4×4, vl=18/tl=44/f=5×2 |
| `GachaCraftNodeDBSchema` | 5 | vl=18/tl=56/f=7×68, vl=18/tl=52/f=7×56, vl=16/tl=48/f=6×14, vl=16/tl=44/f=6×2, vl=16/tl=12/f=2×1 |
| `GachaCraftNodeGroupDBSchema` | 1 | vl=10/tl=28/f=3×291 |
| `GachaCraftOpenTagDBSchema` | 2 | vl=8/tl=12/f=2×2, vl=8/tl=8/f=1×1 |
| `GachaElementDBSchema` | 2 | vl=22/tl=56/f=9×10291, vl=22/tl=52/f=8×4631 |
| `GachaElementRecursiveDBSchema` | 1 | vl=20/tl=52/f=7×669 |
| `GachaGroupDBSchema` | 4 | vl=12/tl=20/f=3×725, vl=12/tl=24/f=3×716, vl=12/tl=28/f=4×58, vl=12/tl=24/f=4×57 |
| `GachaSelectPickupGroupDBSchema` | 1 | vl=10/tl=28/f=3×98 |
| `LocalizeGachaShopDBSchema` | 2 | vl=24/tl=48/f=10×748, vl=24/tl=52/f=10×487 |

结论：**同一列 blob 内字段位置逐行浮动**，任何固定偏移解析都会错位。本脚本的「vtable 驱动 + UTF-8 游程扫描」两条路都不依赖固定偏移。

## 3a. 存不存在一张「GachaShop」类的表？

按「表名含 `GachaShop`」精确筛选：**3** 张 -> `EventContentBoxGachaShopDBSchema`, `EventContentFortuneGachaShopDBSchema`, `LocalizeGachaShopDBSchema`

其中 `2` 张是**活动子系统**表（`EventContent*GachaShop*`），另外 1 张是本地化表 `LocalizeGachaShopDBSchema`。**没有任何一张以「招募商店」为主语义的主表。**

对照候选名逐个核对：

| 候选表名 | 是否存在 | 行数 |
|---|---|---|
| `GachaShopDBSchema` | **不存在** | — |
| `GachaDBSchema` | **不存在** | — |
| `ShopGachaDBSchema` | **不存在** | — |
| `GachaShopExcel` | **不存在** | — |
| `ShopRecruitDBSchema` | **存在** | 532 |
| `LocalizeGachaShopDBSchema` | **存在** | 1235 |

> **结论：客户端 ExcelDB 里没有 `GachaShopDBSchema` / `GachaDBSchema` / `ShopGachaDBSchema` 这样的「招募商店主表」。** 名字里带 `GachaShop` 的只有**两张活动子系统表**（`EventContentBoxGachaShop` / `EventContentFortuneGachaShop`，主键 `EventContentId`）**加一张本地化表** `LocalizeGachaShopDBSchema`（主键 `GachaShopId`）。

### 3a.1 两张 `*GachaShop*` 表的实际内容

| 表 | 行数 | 主键 | min | max | 5位段 | 5M段 | 9位段 | 位数 |
|---|---|---|---|---|---|---|---|---|
| `EventContentBoxGachaShopDBSchema` | 2478 | `EventContentId` | 802 | 70,003 | 1357 | 0 | 0 | {3位:1121, 5位:1357} |
| `EventContentFortuneGachaShopDBSchema` | 188 | `EventContentId` | 809 | 10,832 | 69 | 0 | 0 | {3位:119, 5位:69} |
| `LocalizeGachaShopDBSchema` | 1235 | `GachaShopId` | 1 | 99,999,999 | 695 | 472 | 0 | {1位:3, 5位:695, 6位:7, 7位:523, 8位:7} |

### 3a.2 这些表的 blob 里有没有出现 `ShopRecruit.Id` / `GachaShopId`？

做法：对每行按 vtable 取每个字段的位置，**同时**按 u32 和 i64 读值（不猜宽度，避免对齐 padding 干扰），看是否**精确命中**已知 id 集合。用「精确集合命中」而不是「区间命中」，可以排除结构字节造成的假阳性。

同时用**命中率**判定：真外键的命中率应接近 100%；个位数命中属于数值撞车（例如 `EventContentId` 的 5 位值天然落在 50000~99999 里，与 legacy gacha shop id 撞车）。为避免这种撞车，下面的 `GachaShopId(≥1e6)` 只统计 7/8 位的现行 id。

| 表 | 行数 | 命中 ShopRecruit.Id<br>(≥1e6) 行/率 | 命中 GachaShopId<br>(≥1e6) 行/率 | 命中 5位legacy 行/率 | 命中字段<br>(ShopRecruit) |
|---|---|---|---|---|---|
| `EventContentBoxGachaShopDBSchema` | 2478 | 0 (0.0%) | 0 (0.0%) | 237 (9.6%) | — |
| `EventContentFortuneGachaShopDBSchema` | 188 | 0 (0.0%) | 0 (0.0%) | 0 (0.0%) | — |
| `LocalizeGachaShopDBSchema` | 1235 | 529 (42.8%) | 530 (42.9%) | 695 (56.3%) | {0: 1058} |
| `GachaGroupDBSchema` | 1556 | 2 (0.1%) | 2 (0.1%) | 10 (0.6%) | {0: 4} |
| `GachaElementDBSchema` | 14922 | 2 (0.0%) | 2 (0.0%) | 101 (0.7%) | {1: 2, 5: 1, 6: 1} |
| `GachaCombinedCostDBSchema` | 24 | 0 (0.0%) | 0 (0.0%) | 12 (50.0%) | — |
| `GachaSelectPickupGroupDBSchema` | 98 | 38 (38.8%) | 38 (38.8%) | 0 (0.0%) | {1: 76} |

**读法**：`命中 ShopRecruit.Id (≥1e6)` 为 **0** 就说明这张表里**没有任何一个字段**引用 `ShopRecruit.Id`——它不是 `ShopRecruit` 的维表。真外键的命中率应接近 100%（对照：`LocalizeGachaShopDBSchema` 的 `f0` 就是它自己的`GachaShopId`，所以那一行是**自引用**，率 42.9% 只反映 id 段构成，不是外键关系）。其余表最高只有 9.6%，且命中的是 `EventContentId` / `GroupId` 这类 5 位活动 id 落在 50000~99999 区间内的**数值撞车**，不是引用。

## 3b. 有没有哪张表里同时出现 5M 段 id 和 5 位 legacy id？

两套集合：

- `A` = `ShopRecruit.Id` 中 **≥1e6** 的值（去掉 1/2/3 这种小值噪声）→ 529 个
- `B` = `LocalizeGachaShop.GachaShopId` 落在 **50000~99999** 的值 → 695 个（min=50,000，max=90,203）

A 与 B 的交集：**0**（一个 ≥1e6，一个 5 位，天然不相交）。所以「映射」只能表现为**同一行里同时出现 A 的一个值和 B 的一个值**。

**SQL 列级扫描**（所有 398 张表的全部 id 列，值域层面的两段共存）：

| 表 | 列 | 行数 | 命中最 A<br>(ShopRecruit.Id) | 命中最 B<br>(5位legacy) |
|---|---|---|---|---|
| `GachaElementDBSchema` | `GachaGroupID` | 14922 | 1 | 101 |
| `GachaGroupDBSchema` | `ID` | 1556 | 2 | 10 |
| `GoodsDBSchema` | `Id` | 9422 | 1 | 46 |
| `ItemDBSchema` | `Id` | 1803 | 4 | 29 |
| `LocalizeGachaShopDBSchema` | `GachaShopId` | 1235 | 529 | 695 |
| `ScenarioScriptDBSchema` | `GroupId` | 362158 | 1 | 1058 |

**行级扫描**（同一行 blob 内同时出现 A 的一个值和 B 的一个值）：

| 表 | 行数 | 同行共存行数 | 共存率 | 不同 A / 不同 B | 判定 | 样例 (5M id ↔ 5位id) |
|---|---|---|---|---|---|---|
| `CharacterStatDBSchema` | 7242 | 11 | 0.15% | 9 / 17 | 巧合（共存率 0.2%、不同 A=9 个 / 不同 B=17 个，不构成映射） | `10000000` ↔ `50000`（行主键=7304600） |
| `CharacterVoiceDBSchema` | 9493 | 6 | 0.06% | 6 / 3 | 巧合（共存率 0.1%、不同 A=6 个 / 不同 B=3 个，不构成映射） | `9000101` ↔ `90001`（行主键=90001） |
| `MiniGameRhythmDBSchema` | 20 | 5 | 25.00% | 2 / 1 | 巧合（共存率 25.0%、不同 A=2 个 / 不同 B=1 个，不构成映射） | `5000000` ↔ `50000`（行主键=8040102） |

> **判为巧合，不存在映射表。** 真实的两套 id 映射表应当满足「共存率接近 100% 且覆盖多个不同 id」；这几张表都远达不到，且表义与招募无关（角色属性 / 角色语音 / 音游谱面）。命中的值都是 `5000000`、`10000000`、`90001` 这种取整数或本表自身的分组 id，属于数值撞车。

### 3b.1 唯一同时持有两套 id 的表：`LocalizeGachaShopDBSchema`

它是**一张表、一个主键列、两段 id 分行共存**，而不是「一行两列」的映射表：

| id 段 | 行数 |
|---|---|
| 5M段 | 472 |
| 5位legacy | 695 |
| 其它 | 68 |

- `LocalizeGachaShop` 有、`ShopRecruit` 没有的 id：**703** 个，其中 5 位 legacy **695** 个
- `LocalizeGachaShop` 的 5 位段样例：`[50000, 50001, 50002, 50003, 50004, 50005, 50010, 50011, 50012, 50013, 50014, 50015, 50020, 50021, 50022, 50023, 50024, 50025, 50030, 50031, 50032, 50033, 50040, 50041]`
- `ShopRecruit.Id` 的前 24 个：`[1, 2, 3, 5000000, 5000010, 5000020, 5000030, 5000040, 5000050, 5000060, 5000070, 5000080, 5000090, 5000100, 5000110, 5000120, 5000130, 5000140, 5000150, 5000160, 5000170, 5000180, 5000190, 5000200]`

**变换假设检验**（5 位 ↔ 7 位 是否有算术关系）：

| 变换 | 命中率 | 判定 |
|---|---|---|
| ShopRecruit.Id // 100 | 315/532 | 低（大量 id 挤到同一 5 位值，属巧合） |
| ShopRecruit.Id // 1000 | 1/532 | 低（大量 id 挤到同一 5 位值，属巧合） |
| ShopRecruit.Id // 10 | 0/532 | 低（大量 id 挤到同一 5 位值，属巧合） |
| 5位 legacy × 100 | 34/695 | 不成比例 |
| 5位 legacy × 1000 | 1/695 | 不成比例 |

> 结论：两套 id **没有可导出的算术映射**。5 位段是 legacy 历史 id（对应 `LocalizeGachaShop` 里 320 行仍是韩文的未翻译行），7 位/5M 段是现行 id。客户端不可能靠「算」把一套换成另一套——它要么直接用表里的 key，要么根本走的是另一条本地化路径（见 3c）。

## 3c. `Localize*` 类表：行数 / Key 类型 / 随机 20 行 / 含招募类字眼的行

名字含 `Localize` 的表共 **7** 张。

| 表 | 行数 | Key 列 | SQL 类型 | Key 语义 | distinct | min | max | vlen/tlen/字段数 |
|---|---|---|---|---|---|---|---|---|
| `LocalizeCharProfileChangeDBSchema` | 4 | `CharacterId` | `INTEGER` | 整数哈希 (u32) | 4 | 10,005 | 10,135 | 10/28/3 |
| `LocalizeCharProfileDBSchema` | 264 | `CharacterId` | `INTEGER` | 整数哈希 (u32) | 264 | 10,000 | 101,350,001 | 82/164/38 |
| `LocalizeDBSchema` | 18456 | `Key` | `INTEGER` | 整数哈希 (u32) | 18454 | 252,101 | 4,294,866,583 | 10/16/3 |
| `LocalizeErrorDBSchema` | 429 | `Key` | `INTEGER` | 整数哈希 (u32) | 429 | 14,749,936 | 4,284,073,730 | 12/20/4 |
| `LocalizeEtcDBSchema` | 5379 | `Key` | `INTEGER` | 整数哈希 (u32) | 5379 | 347,234 | 4,294,611,526 | 14/24/5 |
| `LocalizeGachaShopDBSchema` | 1235 | `GachaShopId` | `INTEGER` | 整数哈希 (u32) | 1235 | 1 | 99,999,999 | 24/48/10 |
| `LocalizeSkillDBSchema` | 14155 | `Key` | `INTEGER` | 整数哈希 (u32) | 14155 | 42,154 | 4,294,829,182 | 18/32/7 |

> **所有 `Localize*` 表的 `Key` 都是 `INTEGER` 的 u32 哈希**（不是字符串 key）。取满 8 位十六进制、distinct 数 ≈ 行数，说明是散列键。

### 3c.1 各语言/文本槽位的实际填充（国服是精简 schema）

国服 `ExcelDB.db` 的 Localize 表**不是**国际服的 6 语言 schema，槽位少很多。用前 600 行统计每个槽位的主体文字脚本：

| 表 | 槽位 | 样本行 | 中文(Han) | 韩文(Hangul) | 拉丁 | 空串 | 非字符串 |
|---|---|---|---|---|---|---|---|
| `LocalizeCharProfileChangeDBSchema` | f1 | 4 | 0 | 0 | 0 | 0 | 4 |
| `LocalizeCharProfileChangeDBSchema` | f2 | 4 | 0 | 0 | 0 | 0 | 4 |
| `LocalizeCharProfileDBSchema` | f1 | 200 | 182 | 0 | 9 | 0 | 9 |
| `LocalizeCharProfileDBSchema` | f2 | 200 | 0 | 0 | 0 | 0 | 200 |
| `LocalizeCharProfileDBSchema` | f3 | 200 | 194 | 0 | 0 | 0 | 6 |
| `LocalizeCharProfileDBSchema` | f4 | 200 | 0 | 0 | 0 | 0 | 200 |
| `LocalizeCharProfileDBSchema` | f5 | 200 | 194 | 0 | 0 | 0 | 6 |
| `LocalizeCharProfileDBSchema` | f6 | 200 | 0 | 0 | 0 | 0 | 200 |
| `LocalizeCharProfileDBSchema` | f7 | 200 | 194 | 0 | 0 | 0 | 6 |
| `LocalizeCharProfileDBSchema` | f8 | 200 | 0 | 0 | 0 | 0 | 200 |
| `LocalizeCharProfileDBSchema` | f9 | 200 | 0 | 0 | 0 | 0 | 200 |
| `LocalizeCharProfileDBSchema` | f10 | 200 | 0 | 0 | 0 | 0 | 200 |
| `LocalizeCharProfileDBSchema` | f11 | 200 | 0 | 0 | 0 | 0 | 200 |
| `LocalizeCharProfileDBSchema` | f12 | 200 | 0 | 0 | 0 | 0 | 200 |
| `LocalizeCharProfileDBSchema` | f14 | 200 | 193 | 0 | 0 | 0 | 7 |
| `LocalizeCharProfileDBSchema` | f15 | 200 | 0 | 0 | 0 | 0 | 200 |
| `LocalizeCharProfileDBSchema` | f16 | 200 | 5 | 0 | 189 | 0 | 6 |
| `LocalizeCharProfileDBSchema` | f17 | 200 | 0 | 0 | 0 | 0 | 200 |
| `LocalizeCharProfileDBSchema` | f18 | 200 | 0 | 0 | 194 | 0 | 6 |
| `LocalizeCharProfileDBSchema` | f19 | 200 | 61 | 0 | 133 | 0 | 6 |
| `LocalizeCharProfileDBSchema` | f20 | 200 | 0 | 0 | 0 | 0 | 200 |
| `LocalizeCharProfileDBSchema` | f21 | 200 | 1 | 0 | 193 | 0 | 6 |
| `LocalizeCharProfileDBSchema` | f22 | 200 | 0 | 0 | 0 | 0 | 200 |
| `LocalizeCharProfileDBSchema` | f23 | 200 | 4 | 0 | 190 | 0 | 6 |
| `LocalizeCharProfileDBSchema` | f24 | 200 | 0 | 0 | 0 | 0 | 200 |
| `LocalizeCharProfileDBSchema` | f25 | 200 | 1 | 0 | 193 | 0 | 6 |
| `LocalizeCharProfileDBSchema` | f26 | 200 | 0 | 0 | 0 | 0 | 200 |
| `LocalizeCharProfileDBSchema` | f27 | 200 | 184 | 0 | 10 | 0 | 6 |
| `LocalizeCharProfileDBSchema` | f28 | 200 | 0 | 0 | 0 | 0 | 200 |
| `LocalizeCharProfileDBSchema` | f29 | 200 | 190 | 0 | 4 | 0 | 6 |
| `LocalizeCharProfileDBSchema` | f30 | 200 | 0 | 0 | 0 | 0 | 200 |
| `LocalizeCharProfileDBSchema` | f31 | 200 | 168 | 0 | 26 | 0 | 6 |
| `LocalizeCharProfileDBSchema` | f32 | 200 | 194 | 0 | 0 | 0 | 6 |
| `LocalizeCharProfileDBSchema` | f33 | 200 | 0 | 0 | 0 | 0 | 200 |
| `LocalizeCharProfileDBSchema` | f34 | 200 | 0 | 0 | 0 | 0 | 200 |
| `LocalizeCharProfileDBSchema` | f35 | 200 | 194 | 0 | 0 | 0 | 6 |
| `LocalizeCharProfileDBSchema` | f36 | 200 | 0 | 0 | 0 | 0 | 200 |
| `LocalizeCharProfileDBSchema` | f37 | 200 | 141 | 0 | 2 | 0 | 57 |
| `LocalizeCharProfileDBSchema` | f38 | 200 | 0 | 0 | 0 | 0 | 200 |
| `LocalizeDBSchema` | f1 | 200 | 183 | 0 | 17 | 0 | 0 |
| `LocalizeDBSchema` | f2 | 200 | 0 | 0 | 0 | 0 | 200 |
| `LocalizeErrorDBSchema` | f1 | 200 | 0 | 0 | 0 | 0 | 200 |
| `LocalizeErrorDBSchema` | f2 | 200 | 199 | 0 | 0 | 0 | 1 |
| `LocalizeErrorDBSchema` | f3 | 200 | 0 | 0 | 0 | 0 | 200 |
| `LocalizeEtcDBSchema` | f1 | 200 | 198 | 1 | 1 | 0 | 0 |
| `LocalizeEtcDBSchema` | f2 | 200 | 196 | 0 | 4 | 0 | 0 |
| `LocalizeEtcDBSchema` | f3 | 200 | 0 | 0 | 0 | 0 | 200 |
| `LocalizeEtcDBSchema` | f4 | 200 | 0 | 0 | 0 | 0 | 200 |
| `LocalizeGachaShopDBSchema` | f1 | 200 | 200 | 0 | 0 | 0 | 0 |
| `LocalizeGachaShopDBSchema` | f2 | 200 | 0 | 200 | 0 | 0 | 0 |
| `LocalizeGachaShopDBSchema` | f3 | 200 | 200 | 0 | 0 | 0 | 0 |
| `LocalizeGachaShopDBSchema` | f4 | 200 | 0 | 200 | 0 | 0 | 0 |
| `LocalizeGachaShopDBSchema` | f5 | 200 | 200 | 0 | 0 | 0 | 0 |
| `LocalizeGachaShopDBSchema` | f6 | 200 | 0 | 115 | 85 | 0 | 0 |
| `LocalizeGachaShopDBSchema` | f7 | 200 | 200 | 0 | 0 | 0 | 0 |
| `LocalizeGachaShopDBSchema` | f8 | 200 | 0 | 200 | 0 | 0 | 0 |
| `LocalizeGachaShopDBSchema` | f9 | 200 | 0 | 0 | 0 | 0 | 200 |
| `LocalizeSkillDBSchema` | f1 | 200 | 199 | 1 | 0 | 0 | 0 |
| `LocalizeSkillDBSchema` | f2 | 200 | 0 | 0 | 200 | 0 | 0 |
| `LocalizeSkillDBSchema` | f3 | 200 | 0 | 0 | 0 | 0 | 200 |
| `LocalizeSkillDBSchema` | f4 | 200 | 0 | 0 | 0 | 0 | 200 |
| `LocalizeSkillDBSchema` | f5 | 200 | 0 | 0 | 0 | 0 | 200 |
| `LocalizeSkillDBSchema` | f6 | 200 | 0 | 0 | 0 | 0 | 200 |

**读法**：国服 `LocalizeDBSchema` 只有 3 个字段（`Key` + 1 个文本 + 1 个空槽），`LocalizeEtcDBSchema` 5 个字段，`LocalizeGachaShopDBSchema` 10 个字段。`LocalizeGachaShop` 里 f1/f3/f5/f7 是中文槽、f2/f4/f6/f8 是韩文原串槽——即 **(中文, 韩文) 成对**布局。

### 3c.2 随机 20 行：`Key` + 解出的文本

用固定种子 `random.Random(20261119)` 抽样，可复现。

#### `LocalizeCharProfileChangeDBSchema`（4 行，Key=`CharacterId`）

| Key (dec) | Key (hex) | 解出的文本 |
|---|---|---|
| 10135 | 0x00002797 | *(空)* |
| 10099 | 0x00002773 | *(空)* |
| 10005 | 0x00002715 | *(空)* |
| 10098 | 0x00002772 | *(空)* |

#### `LocalizeCharProfileDBSchema`（264 行，Key=`CharacterId`）

| Key (dec) | Key (hex) | 解出的文本 |
|---|---|---|
| 20022 | 0x00004E36 | f1=祈愿平安无事<br>f3=爱清风香<br>f5=爱清<br>f7=风香<br>f14=第2年<br>f16=16岁<br>f18=4/30<br>f19=4月30日<br>f21=159cm<br>f23=7peach<br>f25=7peach<br>f27=菲鲁兹·蓝/宋媛媛<br>f29=烹饪、做便当<br>f31=供餐部自卫枪械A型<br>f32=风香经常携带的冲锋枪。\n\n在新年到来之际，风香希望不会用到它，\n但总是事与愿违……<br>f35=为迎接新年而穿上和服的风香。\n\n她希望今年能够风平浪静，但不知道所处的环境是否能让她得偿所愿。<br>f37=老师，跨年荞麦面吃过了吗？\n希望我和老师今年都能万事如意。 |
| 10118 | 0x00002786 | f1=普快特快火爆狂飙~！！<br>f3=橘望<br>f5=橘<br>f7=望<br>f14=第1年<br>f16=15岁<br>f18=6/14<br>f19=6月14日<br>f21=147cm<br>f23=CHILD<br>f25=CHILD<br>f27=星谷美绪/名前<br>f29=刷新最快纪录<br>f31=Dead girl switch<br>f32=望专用的手枪。\n\n虽然很少使用，却随时保养到位，能及时排除掉妨碍列车行驶的各种因素。<br>f35=海兰德铁道学院中央管制中心的干部。\n\n性格开朗活泼，不拘小节，因此也常常和双胞胎姐姐光一起，制造出各种事故。虽然她大…<br>f37=噗哈哈！是不是等很久了？ |
| 16015 | 0x00003E8F | f1=……已经没问题了。<br>f3=栗村爱理<br>f5=栗村<br>f7=爱理<br>f14=第1年<br>f16=15岁<br>f18=1/30<br>f19=1月30日<br>f21=160cm<br>f23=Mx2J<br>f25=Mx2J<br>f27=杉村千佳子/张宇琦<br>f29=探访甜品店、参加茶会<br>f31=甜爽风味<br>f32=爱理十分珍惜的冲锋枪。\n\n与平常无异的装饰，提醒着爱理那些自己也会无意忽略的回忆。<br>f35=甜点部的成员，也是火速结成的乐队【Sugar Rush】的队长。\n\n她想要改变平凡的自己，于是带着大家参加了乐队活动… |
| 10015 | 0x0000271F | f1=我是千禧年游戏开发部的爱丽丝<br>f3=天童爱丽丝<br>f5=天童<br>f7=爱丽丝<br>f14=第1年<br>f16=？？岁<br>f18=3/25<br>f19=3月25日<br>f21=152cm<br>f23=DoReMi<br>f25=DoReMi<br>f27=田中美海/四白<br>f29=游戏（RPG）<br>f31=光之剑：超新星<br>f32=工程部转让给爱丽丝的巨型电磁炮。\n\n重量和输出极为惊人，是普通女生携带起来都会非常困难的程度。<br>f35=千禧年游戏开发部的成员。\n\n在废墟发现的来历不明的少女，无法查到包括年龄在内的所有情报。\n一直跟着桃和绿打游戏的她…<br>f37=我一直在等待着你的呼唤。 |
| 20025 | 0x00004E39 | f1=新的一年祝您万寿无疆<br>f3=伊草春香<br>f5=伊草<br>f7=春香<br>f14=第1年<br>f16=15岁<br>f18=5/13<br>f19=5月13日<br>f21=157cm<br>f23=DoReMi<br>f25=DoReMi<br>f27=石飞惠里花/刘可慧<br>f29=培育杂草<br>f31=驱散者<br>f32=春香用来驱逐“害虫之类的东西”时用的霰弹枪。\n\n当然，也可以拿来处理真正的害虫。<br>f35=迎接新年的便利屋68的普通社员。\n\n因为能和重要的人一起迎接新年，开心得不知所措。为了配合大家，还穿上了平时不会穿的…<br>f37=今年我也会……\n拼命努力的！！ |
| 10008 | 0x00002718 | f1=啊~？开什么玩笑？！<br>f3=美甘妮露<br>f5=美甘<br>f7=妮露<br>f14=第3年<br>f16=17岁<br>f18=8/17<br>f19=8月17日<br>f21=146cm<br>f23=Mx2J<br>f25=Mx2J<br>f27=小清水亚美/\n拉面二娇<br>f29=胜利<br>f31=双龙<br>f32=妮露使用的两挺冲锋枪。\n\n都刻着华丽精美的金黄色龙纹。<br>f35=千禧年科技的特工组织——“C&C”的部长。\n\n乍一看只是个在女仆装外面套了件刺绣夹克的小太妹，其实是千禧年任务执行能…<br>f37=做好准备了吗，我可不会手下留情！ |
| 10035 | 0x00002733 | f1=办事中，勿扰。<br>f3=古关忧<br>f5=古关<br>f7=忧<br>f14=第3年<br>f16=17岁<br>f18=4/23<br>f19=4月23日<br>f21=165cm<br>f23=CHILD<br>f25=CHILD<br>f27=后藤沙绪里/\n蒜蓉汪汪<br>f29=读书、管理书籍、研究古书<br>f31=声音抑制器<br>f32=忧对周围的噪音忍无可忍时就会掏出这把消音步枪。\n\n枪如其名，可以迅速让周围安静下来。<br>f35=崔尼蒂图书管理部的部长。\n\n极度热爱书，甚至会说出比起人还是更喜欢书这样的话，尤其偏爱充斥着岁月感的古书古籍。平时都…<br>f37=请，请保持安静…… |
| 26009 | 0x00006599 | f1=403 Forbidden<br>f3=花冈柚子<br>f5=花冈<br>f7=柚子<br>f14=第1年<br>f16=16岁<br>f18=8/12<br>f19=8月12日<br>f21=150cm<br>f23=YutokaMizu<br>f25=YutokaMizu<br>f27=寺泽百花/宅会<br>f29=制作游戏<br>f31=喵喵冲击<br>f32=柚子的榴弹发射器。\n\n不论在哪里，哪怕躲藏在纸箱中，柚子的榴弹也能喷出火焰。<br>f35=被误认为C&C成员而穿上女仆装的千禧年游戏开发部部长。\n\n虽然穿上了新衣服，但柚子内向的性格却没有改变。不过多亏了这… |
| 13004 | 0x000032CC | f1=希望大家度过愉快的一天<br>f3=十六夜野宫<br>f5=十六夜<br>f7=野宫<br>f14=第2年<br>f16=16岁<br>f18=9/1<br>f19=9月1日<br>f21=160cm<br>f23=9ml<br>f25=9ml<br>f27=三浦千幸/幽舞越山<br>f29=购物<br>f31=迷你No.5<br>f32=野宫使用的机枪。\n\n名字虽然叫“迷你No.5”，但它的重量非同一般。<br>f35=阿拜多斯对策委员会的成员。\n\n她心思细腻性格温柔，因此能让其他我行我素的对策委员会成员团结在身边，是所有人的精神支柱…<br>f37=终于轮到我出场了！ |
| 16018 | 0x00003E92 | f1=퐁당퐁당 헬멧단, 대 모집 중!<br>f3=코마카제 라브<br>f5=코마카제<br>f7=라브<br>f14=중퇴<br>f16=16세<br>f18=5/6<br>f19=5월 6일<br>f21=161cm<br>f23=CHILD<br>f25=CHILD<br>f27=鈴木日菜<br>f29=헬멧 닦기, 자판기 아래 뒤지기<br>f31=핀치 히터<br>f32=라브의 산탄총.\n\n야구배트처럼 휘두르기도 하고 오래되어 낡았지만 세심하게 정비되어 있다.<br>f35=퐁당퐁당 헬멧단의 대장.\n\n부하들에게 신뢰받는 리더로, 이것저것 시도해보기는 하지만 운이 좋지는 않은 모… |
| 10134 | 0x00002796 | f1=안녕하세요. 텐도 아리스입니다.<br>f3=텐도 아리스<br>f5=텐도<br>f7=아리스<br>f14=1학년<br>f16=??세<br>f18=3/25<br>f19=3월 25일<br>f21=152cm<br>f23=kokosando<br>f25=kokosando<br>f27=田中美海<br>f29=게임(RPG)<br>f31=빛의 검 : 슈퍼노바 for 아비 에슈흐<br>f32=특제 프레임에 맞춰 경량화, 연발 사격에 특화 개조된 에너지 라이플.\n\n전설의 검과 만나, 용사의 모험은…<br>f35=밀레니엄 학원 게임개발부 소속의 부원.\n\n말투가 조금 특이하고, 게임을 좋아할 뿐인 평범한 소녀. 하지만…<br>f37=아리스, 더 많은 세상을 보고 싶습니다! |
| 10082 | 0x00002762 | f1=此刻正青春！<br>f3=不破莲华<br>f5=不破<br>f7=莲华<br>f14=第2年<br>f16=16岁<br>f18=7/23<br>f19=7月23日<br>f21=157cm<br>f23=Mx2J<br>f25=Mx2J<br>f27=小市真琴/井琉<br>f29=阅读轻小说、锻炼<br>f31=百花缭乱制式步枪——青春的火焰<br>f32=莲华珍爱并经常使用的步枪。\n\n这把步枪是百花缭乱的制式步枪，被莲华按照自己的喜好进行了改造和装饰。莲华说，每当她冲锋…<br>f35=百鬼夜行学院百花缭乱纠纷调解委员会的突击队长。\n\n她充满正义感和责任感。虽然非常关爱后辈，但是在教育她们时绝不会手下…<br>f37=我的青春故事从遇到老师的这一刻就开始了！\n嗯，就这么定了！ |
| 10073 | 0x00002759 | f1=出差中<br>f3=古关忧<br>f5=古关<br>f7=忧<br>f14=第3年<br>f16=17岁<br>f18=4/23<br>f19=4月23日<br>f21=165cm<br>f23=CHILD<br>f25=CHILD<br>f27=后藤沙绪里/\n蒜蓉汪汪<br>f29=读书、管理书籍、研究古书<br>f31=声音抑制器<br>f32=难得和忧一起外出的狙击步枪。\n\n虽然在安静的无人岛上，但却意外地有很多能派上用场的地方。<br>f35=崔尼蒂图书管理部部长。因为和姐妹会做了交易，不得不来孤岛上调查遗迹。\n\n虽然不喜欢外出等需要消耗体力的活动，但因为对…<br>f37=哈啊，哈啊……呃……\n为什么要遭这种罪…… |
| 26008 | 0x00006598 | f1=百夜堂连锁店好评营业中！<br>f3=河和静子<br>f5=河和<br>f7=静子<br>f14=第2年<br>f16=16岁<br>f18=7/7<br>f19=7月7日<br>f21=153cm<br>f23=whoisshe<br>f25=whoisshe<br>f27=森永千才/幽若乃<br>f29=可爱地接客、看板娘拳<br>f31=樱花砰砰<br>f32=静子在夏日海边使用的泵动式霰弹枪。\n\n枪身依然散发着百夜堂特产馅蜜的香味，而现在正是让这种香味名扬四海之时！<br>f35=在夏天也想要一展拳脚的百鬼夜行庆典运营管理部部长。\n\n为了让百夜堂的连锁店遍布基沃托斯，部长的热情今天也在熊熊燃烧。… |
| 19005 | 0x00004A3D | *(空)* |
| 16003 | 0x00003E83 | f1=愿今天也是平安的一天<br>f3=守月铃美<br>f5=守月<br>f7=铃美<br>f14=第2年<br>f16=16岁<br>f18=8/31<br>f19=8月31日<br>f21=162cm<br>f23=Empew<br>f25=Empew<br>f27=社本悠/小瑾<br>f29=巡逻、散步<br>f31=安全守卫者<br>f32=铃美的突击步枪。\n\n对总是独自巡逻的铃美而言，这是她十分珍视的伙伴。<br>f35=保护崔尼蒂安全的自警团成员。\n\n因为崔尼蒂的学员频繁被其他人袭击，为阻止这种情况，她自愿进行街头巡逻。\n充满正义感… |
| 10052 | 0x00002744 | f1=基沃托斯的忧郁<br>f3=生盐诺亚<br>f5=生盐<br>f7=诺亚<br>f14=第2年<br>f16=16岁<br>f18=4/13<br>f19=4月13日<br>f21=161cm<br>f23=Hwansang<br>f25=DoReMi<br>f27=铃代纱弓/陈雨<br>f29=读书、背诵<br>f31=秘书的裁断<br>f32=诺亚使用的带有转换套件的手枪。\n\n将枪托展开抵在肩上，就能像冲锋枪一样快速连射压制敌人。<br>f35=千禧年科技学院的理事会【研讨会】的秘书。\n\n主要工作是记录研讨会的决定与会议内容，还负责为千禧年学员研发的产品进行专…<br>f37=和我一起去探访，\n合理与理性的世界吧？ |
| 10049 | 0x00002741 | f1=甜点部成员<br>f3=杏山和纱<br>f5=杏山<br>f7=和纱<br>f14=第1年<br>f16=15岁<br>f18=8/5<br>f19=8月5日<br>f21=155cm<br>f23=mimo<br>f25=Mx2J<br>f27=夏吉优子/星狸<br>f29=“普通地”吃甜点<br>f31=马比诺吉昂<br>f32=和纱用了很久的重机枪。\n\n只要向她打听名字的由来，就能看见和纱慌张地岔开话题的样子。<br>f35=甜点部的一员，性格悠闲。\n\n不太爱表现自己，总是安静地跟在其他成员的身后。虽然为经常被卷入各种事件而头疼，但她自己也…<br>f37=啊，老师。\n居然在这里遇见了。 |
| 10127 | 0x0000278F | f1=교칙을 지킵시다…….<br>f3=사쿠라이 미요<br>f5=사쿠라이<br>f7=미요<br>f14=2학년<br>f16=16세<br>f18=8/24<br>f19=8월 24일<br>f21=155cm<br>f23=Paruru<br>f25=Paruru<br>f27=花岩香奈<br>f29=타자기 수집<br>f31=키보토스 타이프라이터<br>f32=미요가 늘 가지고 다니는, 하지만 성격상 거의 사용하지 않는 소총.\n\n탄흔이라는 텍스트를 새기는 수단………<br>f35=와일드헌트 예술학원 소속의 여고생.\n\n비공인 불법 밀수 동아리 특수교역부의 부장. 목표는 특수교역부의 폐…<br>f37=저도…… 로맨스 소설의 작가가 될 수 있을까요? |
| 29003 | 0x0000714B | *(空)* |

#### `LocalizeDBSchema`（18,456 行，Key=`Key`）

| Key (dec) | Key (hex) | 解出的文本 |
|---|---|---|
| 793570909 | 0x2F4CEE5D | f1=被占领的31号别馆入口 |
| 1311772992 | 0x4E301140 | f1=우리의 것인 증오 |
| 2285653641 | 0x883C4E89 | f1=和纱突然带着【熔岩巧克力蛋糕】来到了沙勒。原来是她吃不了太烫的食物，于是想把蛋糕送给老师。老师捉弄和纱说她是“猫舌”，但… |
| 369102891 | 0x1600102B | f1=#传统市场 #商业街 #邻里公园 #休息 |
| 301281684 | 0x11F53194 | f1=颤栗沙滩 |
| 3728269709 | 0xDE38E18D | f1=取消 |
| 1559446809 | 0x5CF34519 | f1=伊吹的手提包。里面有手机、哨子、枪支、前辈们准备的纸巾，和漂亮的花瓣等东西。 |
| 322868110 | 0x133E938E | f1=漫步街头的怪谈 1 |
| 1666805558 | 0x63596F36 | f1=确认战况，变更应对方式。 |
| 3637715107 | 0xD8D320A3 | f1=辛苦啦～ |
| 889965409 | 0x350BCB61 | f1=自我介绍 |
| 194188632 | 0x0B931558 | f1=若有导弹漏掉，度假村的体力将减少。 |
| 3838238985 | 0xE4C6E109 | f1=修行部的怪人们 2 |
| 4125302622 | 0xF5E31F5E | f1=情人节翌日 |
| 2795819680 | 0xA6A4D2A0 | f1=最终篇解锁！ |
| 3796207934 | 0xE245893E | f1=阻止温泉开发部 |
| 200151146 | 0x0BEE106A | f1=常盘台中学 |
| 1101015470 | 0x41A029AE | f1=完成第{0}章！ |
| 2077929059 | 0x7BDAAE63 | f1=回忆收藏 |
| 2115087290 | 0x7E11ABBA | f1=冲突 2 |

#### `LocalizeErrorDBSchema`（429 行，Key=`Key`）

| Key (dec) | Key (hex) | 解出的文本 |
|---|---|---|
| 950826558 | 0x38AC763E | f2=该账号名不存在。 |
| 3199174171 | 0xBEAF861B | f2=没有道具。 |
| 2402602733 | 0x8F34CEED | f2=道具持有量不足。 |
| 269254824 | 0x100C80A8 | f2=无法离开小组。 |
| 1877159664 | 0x6FE32EF0 | f2=奖励信息无效。 |
| 1400807002 | 0x537E9E5A | f2=邮件发送失败。 |
| 1747331783 | 0x68262AC7 | f2=购买1件商品后即可进行更新。 |
| 1892580245 | 0x70CE7B95 | f2=无法获取已购买的订单信息。 |
| 928524933 | 0x37582A85 | f2=将账号与验证码绑定时失败。 |
| 989987378 | 0x3B020232 | f2=网络连接错误，请重试。\n点击返回大厅。 |
| 2911926680 | 0xAD907998 | f2=无法重复兑换此礼包码内容。 |
| 1146450388 | 0x445571D4 | f2=战斗通行证已结束。 |
| 1854458240 | 0x6E88C980 | f2=更新剧情数据时发生错误。\n将返回标题画面。 |
| 2689814996 | 0xA05351D4 | f2=无效的关卡。 |
| 337993265 | 0x14255E31 | f2=输入的好友码不存在。 |
| 2172607841 | 0x817F5D61 | f2=未成功保存通关信息。 |
| 3518848085 | 0xD1BD5C55 | f2=没有装备。 |
| 1443275327 | 0x5606A23F | f2=安全模组初始化失败，需要重新启动应用。 |
| 4098579131 | 0xF44B5ABB | f2=总力战挑战券不足。 |
| 1542776967 | 0x5BF4E887 | f2=因尚未通关总力战，无法领取排名奖励。 |

#### `LocalizeEtcDBSchema`（5,379 行，Key=`Key`）

| Key (dec) | Key (hex) | 解出的文本 |
|---|---|---|
| 671884566 | 0x280C2516 | f1=十字架颈链设计图<br>f2=可制造装备的设计图。 |
| 1388660830 | 0x52C5485E | f1=额外伤害、命中值减少<br>f2=敌人攻击时会造成额外伤害。\n敌人的命中值减少。 |
| 1865596274 | 0x6F32BD72 | f1=千禧年技能升级礼包1<br>f2=(X) |
| 136683551 | 0x0825A01F | f1=伊织的记忆大厅<br>f2=可以用伊织的回忆装饰大厅。 |
| 2382060588 | 0x8DFB5C2C | f1=吉<br>f2=抽到这张签的人的运势，如同老树开花，过往的烦恼将一扫而空，从现在起会有各种好事降临……会发生各种快乐事情的话，希望安稳的… |
| 782040502 | 0x2E9CFDB6 | f1=花凛的记忆大厅<br>f2=可以用花凛的回忆装饰大厅。 |
| 3773800588 | 0xE0EFA08C | f1=神秘古物选择券组合包 A<br>f2=可获得选择的神秘古物的商品\n青辉石 X 400 （付费 400 个）\n※组合包的详细内容物请参考下列商品内容。 |
| 1486727254 | 0x589DA856 | f1=蒲公英<br>f2=可以生成古董礼物。 |
| 2470282935 | 0x933D86B7 | f1=6面骰<br>f2=点数为1到6的骰子。 |
| 3922903517 | 0xE9D2C1DD | f1=妮露（邦妮）<br>f2=可招募该学员。 |
| 1188251464 | 0x46D34748 | f1=改良型切莲巧<br>f2=由巴绘制了可爱插图的改良型切莲巧。味道跟原本的切莲巧几乎没有区别。 |
| 1889860996 | 0x70A4FD84 | f1=修复材料保管装置<br>f2=(X) |
| 2459684995 | 0x929BD083 | f1=活动积分<br>f2=每次完成活动时获取的积分。积分越多，就可以获得更多的奖励。 |
| 3299392513 | 0xC4A8BC01 | f1=回转者·粉<br>f2=(X) |
| 95106171 | 0x05AB347B | f1=春叶原车站<br>f2=如同春叶原大门的车站。车站中央出口无论何时都能看到角色的身影，周围的电子屏幕也总是播放着与角色相关的广告，形成了一股独特… |
| 1496854870 | 0x59383156 | f1=完整的伏尼契手稿<br>f2=完整状态的伏尼契手稿。用于各种制造和强化。 |
| 3741867899 | 0xDF085F7B | f1=正义实现部<br>f2=(X) |
| 3655403000 | 0xD9E105F8 | f1=购物中心聚光灯<br>f2=能展现商品的最好一面的聚光灯。摆在下面的商品总是销售一空。 |
| 1979335525 | 0x75FA4365 | f1=纪念品店卡牌<br>f2=狂猎美术馆纪念品商店贩卖的扑克牌。精致度高到让人舍不得用于游戏。 |
| 2034547690 | 0x7944BBEA | f1=莽撞的街头魑魅<br>f2=(X) |

#### `LocalizeGachaShopDBSchema`（1,235 行，Key=`GachaShopId`）

| Key (dec) | Key (hex) | 解出的文本 |
|---|---|---|
| 5003570 | 0x004C5932 | f1=长期招募<br>f3=长期招募<br>f5=来招募更多个性迥异的成员吧！<br>f7=选择招募10次，必定获得1名2★以上成员！\n※若出现已拥有的成员则会转换为神名精髓与该成员的神名文字。<br>f9=2026/04/09 14:00~2026/04/16  13:59截止 |
| 9000102 | 0x008954A6 | f1=三星必得学院招募<br>f3=3★必得招募（B组学院）<br>f5=来招募更多个性迥异的成员吧！<br>f7=选择招募10次，必定获得1名3★成员！\n※该招募中只会出现崔尼蒂，红冬，阿拜多斯，瓦尔基丽的学员。\n※若出现已拥有的…<br>f9=2025/07/31 14:00~2025/08/28  13:59截止 |
| 5001640 | 0x004C51A8 | f1=限时招募<br>f3=限时招募！<br>f5=时（邦妮）（3★）招募概率提升！<br>f7=选择招募10次，必定获得1名2★以上成员！\n※若出现已拥有的成员则会转换为神名精髓与该成员的神名文字。<br>f9=2025/01/23 14:00~2025/02/06  13:59截止 |
| 5003240 | 0x004C57E8 | f1=限时招募<br>f3=限时招募！<br>f5=真里奈（3★）招募概率提升！<br>f7=选择招募10次，必定获得1名2★以上成员！\n※若出现已拥有的成员则会转换为神名精髓与该成员的神名文字。<br>f9=2026/01/22 14:00~2026/01/29  9:59截止 |
| 5002960 | 0x004C56D0 | f1=长期招募<br>f3=长期招募<br>f5=来招募更多个性迥异的成员吧！<br>f7=选择招募10次，必定获得1名2★以上成员！\n※若出现已拥有的成员则会转换为神名精髓与该成员的神名文字。<br>f9=2025/12/04 14:00~2025/12/11  13:59截止 |
| 5001350 | 0x004C5086 | f1=限时招募<br>f3=限时招募！<br>f5=千寻（3★）招募概率提升！<br>f7=选择招募10次，必定获得1名2★以上成员！\n※若出现已拥有的成员则会转换为神名精髓与该成员的神名文字。<br>f9=2024/10/24 14:00~2024/11/07  13:59截止 |
| 50810 | 0x0000C67A | f1=상시<br>f2=상시<br>f3=상시 모집<br>f4=상시 모집<br>f5=다양한 학생들을 모집하세요!<br>f6=다양한 학생들을 모집하세요!<br>f7=10회 모집 시, ★2 이상 학생 1명 확정!\n※ 이미 모집한 학생은 엘리그마와 해당 학생의 엘레프로 변환…<br>f8=10회 모집 시, ★2 이상 학생 1명 확정!\n※ 이미 모집한 학생은 엘리그마와 해당 학생의 엘레프로 변환… |
| 5002120 | 0x004C5388 | f1=限时招募<br>f3=限时招募！<br>f5=切里诺（3★）招募概率提升！<br>f7=选择招募10次，必定获得1名2★以上成员！\n※若出现已拥有的成员则会转换为神名精髓与该成员的神名文字。<br>f9=2025/05/10 14:00~2025/05/24  13:59截止 |
| 5002750 | 0x004C55FE | f1=限定限时1<br>f3=限定限时招募 1<br>f5=【限定】和纱（乐队）（3★）招募概率提升！\n还可招募【限定】好美（乐队）（3★）！<br>f7=选择招募10次，必定获得1名2★以上成员！\n※若出现已拥有的成员则会转换为神名精髓与该成员的神名文字。<br>f9=2025/10/02 14:00~2025/10/16  13:59截止 |
| 5002800 | 0x004C5630 | f1=限时招募<br>f3=限时招募！<br>f5=夏（3★）/玛丽（2★）招募概率提升！<br>f7=选择招募10次，必定获得1名2★以上成员！\n※若出现已拥有的成员则会转换为神名精髓与该成员的神名文字。<br>f9=2025/10/16 14:00~2025/10/23  13:59截止 |
| 50946 | 0x0000C702 | f1=픽업 모집<br>f2=픽업 모집<br>f3=픽업 모집!<br>f4=픽업 모집!<br>f5=★3 아리스(메이드) 출현 확률 UP!<br>f6=★3 아리스(메이드) 출현 확률 UP!<br>f7=10회 모집 시, ★2 이상 학생 1명 확정!\n※ 이미 모집한 학생은 엘리그마와 해당 학생의 엘레프로 변환…<br>f8=10회 모집 시, ★2 이상 학생 1명 확정!\n※ 이미 모집한 학생은 엘리그마와 해당 학생의 엘레프로 변환… |
| 5004640 | 0x004C5D60 | f1=限时招募<br>f3=限时招募！<br>f5=艾利（3★）招募概率提升！<br>f7=选择招募10次，必定获得1名2★以上成员！\n※若出现已拥有的成员则会转换为神名精髓与该成员的神名文字。<br>f9=2026/10/29 14:00~2026/11/12  13:59截止 |
| 63002 | 0x0000F61A | f1=3★必得（神秘）<br>f2=★3 확정 (신비)<br>f3=3★成员必得招募（神秘类型）<br>f4=★3 학생 확정 모집 (신비 타입)<br>f5=来招募更多个性迥异的成员吧！<br>f6=다양한 학생들을 모집하세요!<br>f7=选择招募10次，必定获得1名3★成员！※本次招募只会获得神秘类型的成员。\n※若出现已拥有的成员则会转换为神名精髓与该成…<br>f8=10회 모집 시, ★3 학생 1명 이상 확정!\n※ 해당 모집에서는 신비 타입의 학생만을 획득합니다.\n※ … |
| 60006 | 0x0000EA66 | f1=3★必得<br>f2=★3 확정<br>f3=3★必得招募！<br>f4=★3 확정 모집!<br>f5=来招募更多个性迥异的成员吧！<br>f6=다양한 학생들을 모집하세요!<br>f7=10회 모집 시, ★3 학생 1명 이상 확정!\n※ 이미 모집한 학생은 엘리그마와 해당 학생의 엘레프로 변환…<br>f8=10회 모집 시, ★3 학생 1명 이상 확정!\n※ 이미 모집한 학생은 엘리그마와 해당 학생의 엘레프로 변환… |
| 5001290 | 0x004C504A | f1=限时招募<br>f3=限定限时招募 1<br>f5=【限定】妮露（邦妮）（3★）招募概率提升！\n还可招募【限定】花凛（邦妮）（3★）！<br>f7=选择招募10次，必定获得1名2★以上成员！\n※若出现已拥有的成员则会转换为神名精髓与该成员的神名文字。<br>f9=2024/10/17 14:00~2024/10/24  13:59截止 |
| 5003500 | 0x004C58EC | f1=长期招募<br>f3=长期招募<br>f5=来招募更多个性迥异的成员吧！<br>f7=选择招募10次，必定获得1名2★以上成员！\n※若出现已拥有的成员则会转换为神名精髓与该成员的神名文字。<br>f9=2026/03/12 14:00~2026/03/26  13:59截止 |
| 50694 | 0x0000C606 | f1=한정 픽업1<br>f2=한정 픽업1<br>f3=한정 픽업 모집1<br>f4=한정 픽업 모집1<br>f5=「한정」★3 아루(새해) 출현 확률 UP!\n「한정」★3 무츠키(새해)도 모집가능!<br>f6=「한정」★3 아루(새해) 출현 확률 UP!\n「한정」★3 무츠키(새해)도 모집가능!<br>f7=10회 모집 시, ★2 이상 학생 1명 확정!\n※ 이미 모집한 학생은 엘리그마와 해당 학생의 엘레프로 변환…<br>f8=10회 모집 시, ★2 이상 학생 1명 확정!\n※ 이미 모집한 학생은 엘리그마와 해당 학생의 엘레프로 변환… |
| 50699 | 0x0000C60B | f1=픽업 모집<br>f2=픽업 모집<br>f3=픽업 모집!<br>f4=픽업 모집!<br>f5=★3 아리스(메이드) 출현 확률 UP!<br>f6=★3 아리스(메이드) 출현 확률 UP!<br>f7=10회 모집 시, ★2 이상 학생 1명 확정!\n※ 이미 모집한 학생은 엘리그마와 해당 학생의 엘레프로 변환…<br>f8=10회 모집 시, ★2 이상 학생 1명 확정!\n※ 이미 모집한 학생은 엘리그마와 해당 학생의 엘레프로 변환… |
| 5001030 | 0x004C4F46 | f1=限时招募<br>f3=限时招募！<br>f5=心奈（3★）招募概率提升！<br>f7=选择招募10次，必定获得1名2★以上成员！\n※若出现已拥有的成员则会转换为神名精髓与该成员的神名文字。<br>f9=2024/08/15 14:00~2024/08/22  13:59截止 |
| 80000 | 0x00013880 | f1=3★自选<br>f2=★3 선택<br>f3=3★成员自选<br>f4=★3 선택 모집!<br>f5=购买3★成员自选券后，可以选择成员进行招募。<br>f6=★3 학생 선택권을 구매한 후 학생을 선택하세요.<br>f7=购买后将获得1张10次招募券和1张3★成员自选券。\n该商品每个帐号只能购买1次。\n※选择要招募的成员后，可以获得神名…<br>f8=구매 시 10회 모집 티켓 1장과 ★3 학생 선택권 1장을 획득합니다.\n계정당 1회 한정으로 구매가 가능한… |

#### `LocalizeSkillDBSchema`（14,155 行，Key=`Key`）

| Key (dec) | Key (hex) | 解出的文本 |
|---|---|---|
| 3269220166 | 0xC2DC5746 | f1=装扮+<br>f2=攻击力增加[c][007eff]437[-][/c]/\n额外增加[c][007eff]19.6%[-][/c]攻击力 |
| 210745987 | 0x0C8FBA83 | f1=享受此刻<br>f2=攻击力增加[c][007eff]18.9%[-][/c] |
| 3469273690 | 0xCEC8EA5A | f1=毕竟我是头脑派<br>f2=每当食蜂操祈的必杀技能使目标陷入混乱时，防御力与闪避值增加[c][007eff]32.9%[-][/c]（持续[c][0… |
| 1928882204 | 0x72F8681C | f1=特制狙击子弹<br>f2=装弹后，暴击伤害增加[c][007eff]32.2%[-][/c]（持续[c][007eff]13秒[-][/c]） |
| 3807459679 | 0xE2F1395F | f1=芝士巧克力汉堡~<br>f2=获得治疗力[c][007eff]320%[-][/c]的恢复/\n攻击速度增加[c][007eff]38.4%[-][/… |
| 3726643657 | 0xDE2011C9 | *(空)* |
| 584144632 | 0x22D156F8 | f1=卑鄙恶徒！<br>f2=如各回转者在搭乘回转 FX Mk.0之前受到了群控状态影响，受到的伤害会增加[c][007eff]40%[-][/c]（… |
| 1259338152 | 0x4B0FF9A8 | f1=不可以色色！死刑！<br>f2=攻击时对中型目标造成攻击力[c][007eff]19.8%[-][/c]的额外伤害 |
| 3214942622 | 0xBFA0219E | f1=小心谨慎的观察<br>f2=赋予1名敌人弱点把握状态（持续[c][007eff]10秒[-][/c]）/\n处于弱点把握状态的敌人被攻击时，受到美游… |
| 4060804343 | 0xF20AF4F7 | f1=我带了便当哦<br>f2=每[c][007eff]45秒[-][/c]，除自身外体力最低的1名我方成员获得治疗力[c][007eff]24%[-]… |
| 3982399176 | 0xED5E96C8 | f1=指挥交通+<br>f2=暴击值增加[c][007eff]135[-][/c]/\n额外增加[c][007eff]18.9%[-][/c]群体控制… |
| 2233464249 | 0x851FF5B9 | f1=更换护甲<br>f2=每[c][007eff]40秒[-][/c]装备防弹护板，使受到的伤害减少[c][007eff]21.6%[-][/c]… |
| 3398768236 | 0xCA95166C | f1=깎아볼까?<br>f2=공격력 [c][007eff]18.9%[-][/c] 증가 |
| 1986895717 | 0x766D9F65 | f1=可丽饼的香甜滋味+<br>f2=暴击伤害增加[c][007eff]3800[-][/c]/\n额外增加[c][007eff]26.6%[-][/c]暴击… |
| 1671723555 | 0x63A47A23 | f1=경영 철학+<br>f2=이로운 효과 유지력 [c][007eff]1700[-][/c] 증가/\n추가로 군중제어 강화력 [c][007e… |
| 950168729 | 0x38A26C99 | f1=玩得开心一点吧！<br>f2=攻击力增加[c][007eff]23.8%[-][/c] |
| 1292389568 | 0x4D084CC0 | f1=追星者+<br>f2=增益效果持续力增加[c][007eff]1600[-][/c]/\n额外增加[c][007eff]22.4%[-][/c… |
| 1593180463 | 0x5EF6012F | f1=瞄准，砰！+<br>f2=普通攻击时有[c][007eff]20%[-][/c]概率对1名敌人造成攻击力[c][007eff]582%[-][/c… |
| 2927689284 | 0xAE80FE44 | f1=一发必中<br>f2=命中值增加[c][007eff]22.4%[-][/c] |
| 2726425013 | 0xA281F1B5 | f1=排毒效果<br>f2=攻击力增加[c][007eff]14.7%[-][/c] |

### 3c.3 解出的文本里含 `招募` / `限时` / `概率提升` 的行

这是**最关键的一节**：如果某张 Localize 表里能按 u32 key 直接查到招募文案，那客户端真正在用的取词路径就是它，而不是 `LocalizeGachaShop`。

| 表 | 行数 | 含「招募」 | 含「限时」 | 含「概率提升」 | 命中合计 |
|---|---|---|---|---|---|
| `LocalizeCharProfileChangeDBSchema` | 4 | 0 | 0 | 0 | 0 |
| `LocalizeCharProfileDBSchema` | 264 | 4 | 0 | 0 | 4 |
| `LocalizeDBSchema` | 18456 | 69 | 7 | 3 | 76 |
| `LocalizeErrorDBSchema` | 429 | 4 | 0 | 0 | 4 |
| `LocalizeEtcDBSchema` | 5379 | 379 | 7 | 0 | 379 |
| `LocalizeGachaShopDBSchema` | 1235 | 800 | 468 | 486 | 800 |
| `LocalizeSkillDBSchema` | 14155 | 0 | 0 | 0 | 0 |

#### `LocalizeCharProfileDBSchema` — 命中 4 行

- 含「**概率提升**」：**0** 行
- 含「**限时**」：**0** 行
- 含「**招募**」：**4** 行

| Key (dec) | Key (hex) | 解出的文本 |
|---|---|---|
| 10010 | 0x0000271A | 正在招募骑行伙伴……（1/5） ｜ 砂狼白子 ｜ 砂狼 ｜ 白子 ｜ 第2年 ｜ 16岁 ｜ 5/16 ｜ 5月16日 ｜ 156cm ｜ Hwansang ｜ 小仓唯/安雪璃 ｜ 慢跑、体能… |
| 13012 | 0x000032D4 | 瓦尔基丽，正在招募学员！ ｜ 中务桐乃 ｜ 中务 ｜ 桐乃 ｜ 第1年 ｜ 15岁 ｜ 10/22 ｜ 10月22日 ｜ 161cm ｜ 日下雲 ｜ DoReMi ｜ 中岛优衣/Kiyo ｜ … |
| 10100 | 0x00002774 | 正在招募骑行伙伴……（2/5） ｜ 砂狼白子 ｜ 砂狼 ｜ 白子 ｜ 第3年 ｜ 17岁 ｜ 5/16 ｜ 5月16日 ｜ 165cm ｜ Doremsan2j ｜ 小仓唯/安雪璃 ｜ 慢跑、… |
| 20040 | 0x00004E48 | 长期招募受试者/咨询可联系万魔殿 ｜ 京极皋月 ｜ 京极 ｜ 皋月 ｜ 第3年 ｜ 17岁 ｜ 4/10 ｜ 4月10日 ｜ 172cm ｜ 本田roaro ｜ Mx2J ｜ 樱井浩美/阮从青… |

#### `LocalizeDBSchema` — 命中 76 行

- 含「**概率提升**」：**3** 行
- 含「**限时**」：**7** 行
- 含「**招募**」：**69** 行

| Key (dec) | Key (hex) | 解出的文本 |
|---|---|---|
| 1116313095 | 0x42899607 | 在回忆招募中，可通过首次奖励，额外获得设置为概率提升对象的成员的100个神名文字。\n（此首次奖励仅可在招募期间获取1次。获得奖励后，即使更改概率提升对象，也无法获得该对象的100个神名文字。… |
| 1921419360 | 0x72868860 | 在返场招募中，可通过首次奖励，额外获得设置为概率提升对象的成员的100个神名文字。\n（此首次奖励仅可在招募期间获取1次。获得奖励后，即使更改概率提升对象，也无法获得该对象的100个神名文字。… |
| 2657231644 | 0x9E62231C | 请选择招募概率提升的成员。\n [c][83888d]※ 招募概率提升对象随时可更改。[-][/c] |
| 4239658919 | 0xFCB40FA7 | 请注意，当活动道具的持有数量达到上限时，将无法解锁故事关卡！ |
| 221132467 | 0x0D2E36B3 | 请注意，当活动道具的持有数量达到上限时，将无法解锁故事关卡！ |
| 68024019 | 0x040DF6D3 | 完成{0}个以上活动限时任务 |
| 2576257965 | 0x998E93AD | 请注意，当活动道具持有数达到上限时，将无法解锁故事关卡！ |
| 2703648967 | 0xA12668C7 | 限时 |
| 912036346 | 0x365C91FA | 限时 |
| 3347409239 | 0xC7856957 | 限时道具 |
| 3350689640 | 0xC7B77768 | 招募鹤城（泳装） |
| 2948624965 | 0xAFC07245 | 招募所需的招募券不足。 |
| 4260571357 | 0xFDF328DD | 招募{0}名成员 |
| 1094443306 | 0x413BE12A | 需招募{0}的学员 |
| 3869178747 | 0xE69EFB7B | 是否继续进行1次招募？ |
| 801127309 | 0x2FC03B8D | 招募1次 |
| 3304805147 | 0xC4FB531B | 招募10次 |
| 2054950412 | 0x7A7C0E0C | 是否继续进行10次招募？ |
| 2701998922 | 0xA10D3B4A | 是否使用[c][007eff]{0}[-][/c]个青辉石购买[c][007eff]{1}[-][/c]信用积分\n并进行免费招募？ |
| 1328175739 | 0x4F2A5A7B | 招募成员 |
| 4025703718 | 0xEFF35D26 | 是否进行免费新手冲刺招募？ |
| 2936228350 | 0xAF0349FE | 进行招募 |
| 2601022598 | 0x9B087486 | 招募券不足。 |
| 1608891127 | 0x5FE5BAF7 | 成员招募已解锁。 |

#### `LocalizeErrorDBSchema` — 命中 4 行

- 含「**概率提升**」：**0** 行
- 含「**限时**」：**0** 行
- 含「**招募**」：**4** 行

| Key (dec) | Key (hex) | 解出的文本 |
|---|---|---|
| 2856326245 | 0xAA401465 | 招募已过期。\n将返回标题画面。 |
| 658573648 | 0x27410950 | 购买已结算完成，但还未进行招募。\n请在以下时间内进行招募\n（不会产生重复购买） |
| 1864642385 | 0x6F242F51 | 结算已正常完成，但尚未完成招募，\n请再次在招募界面进行招募\n（不会产生反复购买） |
| 2100477460 | 0x7D32BE14 | 未持有3★成员自选券。\n购买自选券后，可选择成员招募。 |

#### `LocalizeEtcDBSchema` — 命中 379 行

- 含「**概率提升**」：**0** 行
- 含「**限时**」：**7** 行
- 含「**招募**」：**379** 行

| Key (dec) | Key (hex) | 解出的文本 |
|---|---|---|
| 3308377822 | 0xC531D6DE | 招募点数 ｜ 限时招募期间，每次进行招募时，都可以获得招募点数。招募点数可以用来换取指定成员。\n※招募期间结束后，积分将自动转换为拱心石碎片。 |
| 1892033319 | 0x70C62327 | 3★自选招募礼包 ｜ 为老师提供的3★自选招募礼包\n可获得限时10次招募券 x 1\n3★成员自选券 x 1 |
| 1784624863 | 0x6A5F36DF | 限时招募 ｜ (X) |
| 2311404574 | 0x89C53C1E | 限时招募 ｜ (X) |
| 3777441543 | 0xE1272F07 | 【庆典限定】 \n限时10次招募券礼包 ｜ 为老师提供的限时10次招募券礼包。\n※礼包详细内容物请参考下方商品内容。 |
| 3998643710 | 0xEE5675FE | 3★自选招募礼包 Ⅱ ｜ 为老师提供的3★自选招募礼包 Ⅱ\n可获得限时10次招募券 x 1\n3★成员自选券 Ⅱ x 1 |
| 3189911802 | 0xBE2230FA | 【庆典限定】\n限时招募补给礼包 ｜ 为老师提供的限时招募补给礼包。\n※礼包详细内容物请参考下方商品内容。 |
| 798331298 | 0x2F9591A2 | 爱露 ｜ 可招募该学员。 |
| 3807268382 | 0xE2EE4E1E | 艾米 ｜ 可招募该学员。 |
| 3851447835 | 0xE5906E1B | 晴奈 ｜ 可招募该学员。 |
| 1027332683 | 0x3D3BDA4B | 日富美 ｜ 可招募该学员。 |
| 2114399124 | 0x7E072B94 | 日奈 ｜ 可招募该学员。 |
| 215481915 | 0x0CD7FE3B | 星野 ｜ 可招募该学员。 |
| 3611252335 | 0xD73F566F | 伊织 ｜ 可招募该学员。 |
| 1325494637 | 0x4F01716D | 真纪 ｜ 可招募该学员。 |
| 1314551102 | 0x4E5A753E | 妮露 ｜ 可招募该学员。 |
| 1847578592 | 0x6E1FCFE0 | 泉 ｜ 可招募该学员。 |
| 3174751282 | 0xBD3ADC32 | 白子 ｜ 可招募该学员。 |
| 4197576983 | 0xFA31F117 | 瞬 ｜ 可招募该学员。 |
| 956113705 | 0x38FD2329 | 堇 ｜ 可招募该学员。 |
| 2482304262 | 0x93F4F506 | 鹤城 ｜ 可招募该学员。 |
| 4051524296 | 0xF17D5AC8 | 泉奈 ｜ 可招募该学员。 |
| 2875023856 | 0xAB5D61F0 | 爱丽丝 ｜ 可招募该学员。 |
| 2658574978 | 0x9E76A282 | 绿 ｜ 可招募该学员。 |

#### `LocalizeGachaShopDBSchema` — 命中 800 行

- 含「**概率提升**」：**486** 行
- 含「**限时**」：**468** 行
- 含「**招募**」：**800** 行

| Key (dec) | Key (hex) | 解出的文本 |
|---|---|---|
| 50001 | 0x0000C351 | 限时招募 ｜ 픽업 모집 ｜ 限时招募！ ｜ 픽업 모집! ｜ 切里诺（3★）招募概率提升！ ｜ 체리노(★3 ) 출현 확률 UP! ｜ 选择招募10次，必定获得1名2★以上成员！\n※若出… |
| 50004 | 0x0000C354 | 限时招募 ｜ 상시 모집 ｜ 限时招募！ ｜ 白子（3★）/星野（3★）招募概率提升！ ｜ 다양한 학생들을 모집하세요! ｜ 选择招募10次，必定获得1名2★以上成员！\n※若出现已拥有的成… |
| 50005 | 0x0000C355 | 限时招募 ｜ 픽업 모집 ｜ 限时招募！ ｜ 픽업 모집! ｜ 真白（3★）招募概率提升！ ｜ 마시로(★3 ) 출현 확률 UP! ｜ 选择招募10次，必定获得1名2★以上成员！\n※若出现… |
| 50011 | 0x0000C35B | 限时招募 ｜ 픽업 모집 ｜ 限时招募！ ｜ 픽업 모집! ｜ 泉奈（3★）/静子（2★）招募概率提升！ ｜ 이즈나(★3 ) / 시즈코(★2) 출현 확률 UP! ｜ 选择招募10次，必定… |
| 50013 | 0x0000C35D | 限时招募 ｜ 픽업 모집 ｜ 限时招募！ ｜ 픽업 모집! ｜ 晴奈（3★）招募概率提升！ ｜ 하루나(★3 ) 출현 확률 UP! ｜ 选择招募10次，必定获得1名2★以上成员！\n※若出现… |
| 50015 | 0x0000C35F | 限时招募 ｜ 픽업 모집 ｜ 限时招募！ ｜ 픽업 모집! ｜ 爱露（3★）招募概率提升！ ｜ 아루(★3 ) 출현 확률 UP! ｜ 选择招募10次，必定获得1名2★以上成员！\n※若出现已… |
| 50021 | 0x0000C365 | 限时招募 ｜ 픽업 모집 ｜ 限时招募！ ｜ 픽업 모집! ｜ 爱丽丝（3★）招募概率提升！ ｜ 아리스(★3 ) 출현 확률 UP! ｜ 选择招募10次，必定获得1名2★以上成员！\n※若出… |
| 50023 | 0x0000C367 | 限时招募 ｜ 픽업 모집 ｜ 限时招募！ ｜ 픽업 모집! ｜ 绿（3★）/桃（2★）招募概率提升！ ｜ 미도리(★3 ) / 모모이(★2) 출현 확률 UP! ｜ 选择招募10次，必定获得… |
| 50025 | 0x0000C369 | 限时招募 ｜ 픽업 모집 ｜ 限时招募！ ｜ 픽업 모집! ｜ 花凛（3★）招募概率提升！ ｜ 카린(★3 ) 출현 확률 UP! ｜ 选择招募10次，必定获得1名2★以上成员！\n※若出现已… |
| 50031 | 0x0000C36F | 限时招募 ｜ 픽업 모집 ｜ 限时招募！ ｜ 픽업 모집! ｜ 切里诺（3★）招募概率提升！ ｜ 체리노(★3 ) 출현 확률 UP! ｜ 选择招募10次，必定获得1名2★以上成员！\n※若出… |
| 50033 | 0x0000C371 | 限时招募 ｜ 픽업 모집 ｜ 限时招募！ ｜ 픽업 모집! ｜ 柚子（3★）招募概率提升！ ｜ 유즈(★3 ) 출현 확률 UP! ｜ 选择招募10次，必定获得1名2★以上成员！\n※若出现已… |
| 50041 | 0x0000C379 | 限时招募 ｜ 픽업 모집 ｜ 限时招募！ ｜ 픽업 모집! ｜ 梓（3★）/花子（2★）招募概率提升！ ｜ 아즈사(★3 ) / 하나코(★2) 출현 확률 UP! ｜ 选择招募10次，必定获… |
| 50043 | 0x0000C37B | 限时招募 ｜ 픽업 모집 ｜ 限时招募！ ｜ 픽업 모집! ｜ 小春（3★）招募概率提升！ ｜ 코하루(★3 ) 출현 확률 UP! ｜ 选择招募10次，必定获得1名2★以上成员！\n※若出现… |
| 50045 | 0x0000C37D | 限时招募 ｜ 픽업 모집 ｜ 限时招募！ ｜ 픽업 모집! ｜ 日富美（3★）招募概率提升！ ｜ 히후미(★3 ) 출현 확률 UP! ｜ 选择招募10次，必定获得1名2★以上成员！\n※若出… |
| 50051 | 0x0000C383 | 限定限时1 ｜ 한정 픽업1 ｜ 限定限时招募1 ｜ 한정 픽업 모집1 ｜ 「限定」3★梓（泳装）招募概率提升！\n可招募「限定」3★真白（泳装）！ ｜ 「한정」★3 아즈사(수영복) 출현… |
| 50053 | 0x0000C385 | 限定限时2 ｜ 한정 픽업2 ｜ 限定限时招募2 ｜ 한정 픽업 모집2 ｜ 「限定」3★真白（泳装）招募概率提升！\n可招募「限定」3★梓（泳装）！ ｜ 「한정」★3 마시로(수영복) 출현… |
| 50055 | 0x0000C387 | 限时 ｜ 픽업 ｜ 限时招募！ ｜ 상시 모집 ｜ 3★日富美（泳装）招募概率提升！ ｜ ★3 히후미(수영복) 출현 확률 UP! ｜ 选择招募10次，必定获得1名2★以上成员！\n※若出现… |
| 50061 | 0x0000C38D | 限定限时1 ｜ 한정 픽업1 ｜ 限定限时招募1 ｜ 한정 픽업 모집1 ｜ 「限定」3★日奈（泳装）招募概率提升！可招募「限定」3★伊织（泳装）！ ｜ 「한정」★3 히나(수영복) 출현 확… |
| 50063 | 0x0000C38F | 限定限时2 ｜ 한정 픽업2 ｜ 限定限时招募2 ｜ 한정 픽업 모집2 ｜ 「限定」3★伊织（泳装）招募概率提升！可招募「限定」3★日奈（泳装）！ ｜ 「한정」★3 이오리(수영복) 출현 … |
| 50065 | 0x0000C391 | 限时 ｜ 픽업 ｜ 限时招募！ ｜ 픽업 모집! ｜ 3★白子（骑手装）招募概率提升！ ｜ ★3 시로코(라이딩) 출현 확률 UP! ｜ 选择招募10次，必定获得1名2★以上成员！\n※若出… |
| 50071 | 0x0000C397 | 限时 ｜ 픽업 ｜ 限时招募！ ｜ 픽업 모집! ｜ 3★瞬（儿童）/2★桐乃招募概率提升！ ｜ ★3 슌(어린이) / ★2 키리노 출현 확률 UP! ｜ 选择招募10次，必定获得1名2★… |
| 50073 | 0x0000C399 | 限时 ｜ 픽업 ｜ 限时招募！ ｜ 픽업 모집! ｜ 3★纱绫（便装）招募概率提升！ ｜ ★3 사야(사복) 출현 확률 UP! ｜ 选择招募10次，必定获得1名2★以上成员！\n※若出现已拥… |
| 50075 | 0x0000C39B | 限时 ｜ 픽업 ｜ 限时招募！ ｜ 픽업 모집! ｜ 3★响招募概率提升！ ｜ ★3 히비키 출현 확률 UP! ｜ 选择招募10次，必定获得1名2★以上成员！\n※若出现已拥有的成员则会转换… |
| 50081 | 0x0000C3A1 | 限定限时1 ｜ 한정 픽업1 ｜ 限定限时招募1 ｜ 한정 픽업 모집1 ｜ 「限定」3★妮露（兔女郎）招募概率提升！还可招募「限定」3★花凛（兔女郎）！ ｜ 「한정」★3 네루(바니걸) 출… |

### 3c.4 全库 398 张表扫「概率提升」

为了确认没有漏掉非 `Localize*` 的表，对全库所有表的所有 blob 做一次「概率提升」全文扫描：

| 表 | 行数 | 含「概率提升」行数 | 样例 |
|---|---|---|---|
| `LocalizeDBSchema` | 18456 | 3 | key=1116313095 :: `在回忆招募中，可通过首次奖励，额外获得设置为概率提升对象的成员的100个神名文字。\n（此首次奖励仅可在招募期间获取1次…` |
| `LocalizeGachaShopDBSchema` | 1235 | 486 | key=50001 :: `切里诺（3★）招募概率提升！` |

## 4. `LocalizeDBSchema`（18,456 行）中含「招募」的行

- 总行数：**18,456**
- `Key` 类型：**INTEGER（u32 哈希）**，SQL 声明 `INTEGER`
- 解出的 Bytes 文本中含「**招募**」：**69** 行
- 其中含「限时」：**0** 行；含「概率提升」：**3** 行

### 4.1 前 20 个 Key（十进制 + 十六进制）

| # | Key (dec) | Key (hex) | 解出的文本 |
|---|---|---|---|
| 1 | 3350689640 | 0xC7B77768 | `招募鹤城（泳装）` |
| 2 | 2948624965 | 0xAFC07245 | `招募所需的招募券不足。` |
| 3 | 4260571357 | 0xFDF328DD | `招募{0}名成员` |
| 4 | 1094443306 | 0x413BE12A | `需招募{0}的学员` |
| 5 | 3869178747 | 0xE69EFB7B | `是否继续进行1次招募？` |
| 6 | 801127309 | 0x2FC03B8D | `招募1次` |
| 7 | 3304805147 | 0xC4FB531B | `招募10次` |
| 8 | 2054950412 | 0x7A7C0E0C | `是否继续进行10次招募？` |
| 9 | 2701998922 | 0xA10D3B4A | `是否使用[c][007eff]{0}[-][/c]个青辉石购买[c][007eff]{1}[-][/c]信用积分\n并进行免费招募？` |
| 10 | 1328175739 | 0x4F2A5A7B | `招募成员` |
| 11 | 4025703718 | 0xEFF35D26 | `是否进行免费新手冲刺招募？` |
| 12 | 2936228350 | 0xAF0349FE | `进行招募` |
| 13 | 2601022598 | 0x9B087486 | `招募券不足。` |
| 14 | 1608891127 | 0x5FE5BAF7 | `成员招募已解锁。` |
| 15 | 934587045 | 0x37B4AAA5 | `是否进行免费招募？` |
| 16 | 669517005 | 0x27E804CD | `※招募时会扣除免费招募次数。\n确认要进行招募吗？` |
| 17 | 3200072333 | 0xBEBD3A8D | `是否消耗招募点数兑换成员的神名文字？\n与招募时同样，可一同获得神名精髓。` |
| 18 | 146583635 | 0x08BCB053 | `是否使用招募点数引进成员？` |
| 19 | 3728930963 | 0xDE42F893 | `是否使用[c][007eff]{0}[-][/c]个青辉石\n购买[c][007eff]{1}[-][/c]信用积分并进行免费招募？\n\n※将先消…` |
| 20 | 983141534 | 0x3A998C9E | `是否确认使用招募券进行招募？` |

其余 49 个 Key（dec）：

`1067839772, 244706337, 1044741424, 2347174371, 629477422, 2685570776, 1220804414, 3582865496, 388315304, 1116313095, 2138928635, 1921419360, 2082372957, 2842760158, 3261751147, 1823356902, 1486240455, 1691085705, 1426707718, 2882077702, 134805102, 3465373326, 1795423173, 2028330816, 1511779096, 1587939129, 375373556, 658356544, 3810093652, 276877161, 3050907365, 4113333893, 3546888697, 114926777, 3635571512, 2657231644, 1427585166, 3041996303, 3200324682, 2036144236, 3165972437, 2035595238, 3620068402, 2728835360, 459655702, 2006714802, 418489335, 1162679472, 2717163105`

### 4.2 含「概率提升」的 Key（这几条最接近招募页真正的说明文案）

| Key (dec) | Key (hex) | 解出的文本 |
|---|---|---|
| 1116313095 | 0x42899607 | `在回忆招募中，可通过首次奖励，额外获得设置为概率提升对象的成员的100个神名文字。\n（此首次奖励仅可在招募期间获取1次。获得奖励后，即使更改概率提升对象，也无法获得该对象的100个神名文字。）` |
| 1921419360 | 0x72868860 | `在返场招募中，可通过首次奖励，额外获得设置为概率提升对象的成员的100个神名文字。\n（此首次奖励仅可在招募期间获取1次。获得奖励后，即使更改概率提升对象，也无法获得该对象的100个神名文字。）` |
| 2657231644 | 0x9E62231C | `请选择招募概率提升的成员。\n [c][83888d]※ 招募概率提升对象随时可更改。[-][/c]` |

## 5. 结论

### a) 有没有「GachaShop」类的表？

- **没有** `GachaShopDBSchema` / `GachaDBSchema` / `ShopGachaDBSchema`。名字带 `GachaShop` 的共 **3** 张：其中 2 张是活动子系统表（`EventContentBoxGachaShopDBSchema` 2,478 行 / `EventContentFortuneGachaShopDBSchema` 188 行，主键都是 `EventContentId`），另 1 张是本地化表 `LocalizeGachaShopDBSchema`（1,235 行，主键 `GachaShopId`）。
- 全库 **398** 张表里，**只有 `LocalizeGachaShopDBSchema`**（1,235 行）以 `GachaShopId` 为主键。
- `ShopRecruit.Id`（532 行）**100% 被 `LocalizeGachaShop.GachaShopId` 覆盖**（532/532，反向差集 703 个）——`ShopRecruit` 是 `LocalizeGachaShop` 的**子集**，不存在「需要另一张 GachaShop 表去补齐映射」的缺口。
- 两张活动 `*GachaShop*` 表的 blob 里，**命中 `ShopRecruit.Id`(≥1e6) 的行数为 0**，它们不是 `ShopRecruit` 的维表（见 3a.2）。

### b) 有没有同时出现 5M 段和 5 位 legacy id 的映射表？

- **没有。** 有 3 张表出现「同行共存」，但共存率、不同 id 数都不构成映射（最多是取整数撞车），且都是角色属性 / 角色语音 / 音游谱面这类与招募无关的表：`CharacterStatDBSchema`, `CharacterVoiceDBSchema`, `MiniGameRhythmDBSchema`。
- 唯一「同时持有两套 id」的表是 `LocalizeGachaShopDBSchema`，但那是**同一列分行共存**：5 位 legacy 695 行 + 现行 7 位 530 行，不是「一行两列」的映射。
- 两套 id 之间**没有算术可导出的映射**（×100 / ÷100 / ÷1000 全部不成比例）：5 位段是 legacy 历史 id，7 位/5M 段是现行 id。

### c) Localize* 表里有没有招募文案？

- `Localize` 表共 **7** 张，`Key` 全部是 **u32 整数哈希**（不是字符串）。
- `LocalizeDBSchema`（18,456 行）：含「招募」**69** 行、含「概率提升」**3** 行
- `LocalizeEtcDBSchema`（5,379 行）：含「招募」**379** 行、含「概率提升」**0** 行
- `LocalizeGachaShopDBSchema`（1,235 行）：含「招募」**800** 行、含「概率提升」**486** 行

- **`LocalizeDBSchema` 里有 69 行含「招募」、3 行含「概率提升」** —— 这是客户端招募 UI 文案真正能查到的位置。第一条 `概率提升` 的 Key = **`1116313095`**（`0x42899607`）。

---

*由 `work\ba\scripts\q_all_gacha_tables.py` 生成；只读扫描，表 398 张，关键字命中 37 张，Gacha 表 14 张，Localize 表 7 张。*
