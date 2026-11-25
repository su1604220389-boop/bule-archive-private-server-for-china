# CLIENT_ID_WHITELISTS — 一键发放类客户端 id 白名单导出报告

生成时间：2026-11-19 23:35 (本地) ／ 模式：**纯本地只读导出**（未联网、未接触服务器、未修改任何已有文件）
数据源：`work/ba/data/ExcelDB.db` ／ 输出目录：`work/ba/srv_src/Shittim-Server/Resources/`

---

## 0. TL;DR

| # | 类别 | 表名 | **id 数** | min | max | 文件 |
|---|---|---|---|---|---|---|
| 1 | 记忆大厅 | `MemoryLobbyDBSchema` | **258** | 10000 | 2300501 | `ClientMemoryLobbyIds.txt` |
| 2 | 家具 | `FurnitureDBSchema` | **876** | 1 | 1000000 | `ClientFurnitureIds.txt` |
| 3 | 角色 | `CharacterDBSchema` | **7223** | 10000 | 838060812 | `ClientCharacterIds.txt` |
| 4 | 装备 | `EquipmentDBSchema` | **191** | 1 | 109009 | `ClientEquipmentIds.txt` |
| 5 | 专武 | `CharacterWeaponDBSchema` | **254** | 10000 | 26015 | `ClientWeaponIds.txt` |
| 6 | 徽章 | `EmblemDBSchema` | **1065** | 1 | 900000003 | `ClientEmblemIds.txt` |

合计 6 类、**9867** 个 id。**没有任何一类是「未找到」**；6 张表全部在 `sqlite_master` 中精确命中，无一张是拿相似表硬凑的（见 §3 的排除记录）。
记忆大厅与角色 id 交集 = **234 / 258**（不是全同，见 §5，历史结论只对 90.7% 成立）。

---

## 1. 范围与红线执行情况

- 只读打开数据库；**只新建** 6 个数据文件 + 本报告；没有新建任何脚本文件（生成逻辑用 `python -` 从 stdin 内联执行）。
- 未触碰 `ClientItemIds.txt`（md5 与 mtime 均未变，见 §8）。
- 未触碰服务器、未联网。

---

## 2. 数据源与只读证明

| 项 | 值 |
|---|---|
| 路径 | `C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\data\ExcelDB.db` |
| 大小 | 160,534,528 B（与任务书一致） |
| **md5（导出前）** | `824ce3a8bee2bb5ae36ada1ac95048f1` ✅ |
| **md5（导出后复核）** | `824ce3a8bee2bb5ae36ada1ac95048f1` ✅ 未改动 |
| sha256 | `c49096aa6fdafee3c7bb4d5293039e1dafe1521c09c033bd25566aefae2cc5a9` |
| mtime | 2026-11-14T06:22:59.7532067+08:00（未被本次操作触碰） |
| 打开方式 | `sqlite3.connect("file:...?mode=ro&immutable=1", uri=True)` + `PRAGMA query_only=1` |

**独立的来源同一性证明**：`Resources/ClientItemIds.txt` 头部（2026-11-19 00:42 由 `scripts/gen_client_item_ids.py` 生成、已上线的产物）记录的
`source size: 160534528 B` / `source md5: 824ce3a8…` / `source sha256: c49096aa6fdafee3c7bb4d5293039e1dafe1521c09c033bd25566aefae2cc5a9`
与本次实测**三项全部一致**，即本次读取的确是被既有导出管线认定的同一份客户端侧 Excel 表。

---

## 3. 表发现过程（不是猜的）

`SELECT type,name FROM sqlite_master WHERE type IN ('table','view')` → **398 个对象，全部是 `table`，无 view**。
表名命名规律确认：一律 `<Name>DBSchema`，**不存在 `CharacterExcel` 之类的 `Excel` 后缀变体**（角色表只有 `CharacterDBSchema`）。

按关键词检索命中（行数取自 `COUNT(*)`，`PRAGMA table_info` 取列名）：

| 关键词 | 命中表 | 行数 | 列 | 采纳 |
|---|---|---|---|---|
| MemoryLobby | `MemoryLobbyDBSchema` | 258 | `Id, Bytes` | ✅ |
| Furniture | `FurnitureDBSchema` | 876 | `Id, Bytes` | ✅ **家具本体** |
| Furniture | `FurnitureGroupDBSchema` | 23 | `Id, Bytes` | ❌ 家具分组（id 100–122 连续），不是家具 |
| Furniture | `FurnitureTemplateDBSchema` | 21 | `FurnitureTemplateId, Bytes` | ❌ 咖啡厅模板，主键是模板号不是家具号 |
| Furniture | `FurnitureTemplateElementDBSchema` | 1538 | `FurnitureTemplateId, Bytes` | ❌ 模板元素，同上 |
| Character | `CharacterDBSchema` | 7223 | `Id, ProductionStep, MainCombatStyleId, Bytes` | ✅ **角色本体** |
| Equipment | `EquipmentDBSchema` | 191 | `Id, Bytes` | ✅ **装备本体** |
| Equipment | `EquipmentLevelDBSchema` | 70 | （无 Id） | ❌ 强化等级系数 |
| Equipment | `EquipmentStatDBSchema` | 191 | `EquipmentId, …, Bytes` | ❌ 数值表，与 `EquipmentDBSchema` 同 191 行，是其展开 |
| Weapon | `CharacterWeaponDBSchema` | 254 | `Id, Bytes` | ✅ **专武本体** |
| Weapon | `CharacterWeaponExpBonusDBSchema` | 11 | （无 Id） | ❌ 经验加成 |
| Weapon | `CharacterWeaponLevelDBSchema` | 70 | （无 Id） | ❌ 专武等级表 |
| Emblem | `EmblemDBSchema` | 1065 | `Id, Bytes` | ✅ **徽章本体** |

**身份佐证**（直接读首行的 `Bytes` blob 里抽可打印字符串，确认这张表装的就是那个东西，不是同名近似表）：

| 表 | 首行 id | blob 内字符串 |
|---|---|---|
| `MemoryLobbyDBSchema` | 10000 | `UIs/01_Common/08_Lobbyillust/Lobbyillust_Icon_Aru_01`, `LobbyAru` |
| `FurnitureDBSchema` | 1 | `Cafe/my_defaultroom_tile`, `UIs/…/16_CafeItem/My_Defaultroom_Tile` |
| `CharacterDBSchema` | 10000 | `aru`, `Aru_default`, `2099-12-31 03:59:59`（有效期限） |
| `EquipmentDBSchema` | 1 | `UIs/01_Common/02_Equipment/Equipment_Icon_Exp_0` |
| `CharacterWeaponDBSchema` | 10000 | `Passive01`, `UIs/01_Common/04_Weapon/Weapon_Icon_10000` |
| `EmblemDBSchema` | 1 | `UIs/01_Common/43_Emblem/Emblem_BG_Default` |

---

## 4. 逐类导出结果

### 4.1 `ClientMemoryLobbyIds.txt` — `MemoryLobbyDBSchema`.`Id`

| 指标 | 值 |
|---|---|
| 源表行数 | 258（与任务书「已知 258 行」一致 ✅） |
| 导出 id 数 / 去重后 | 258 / 258 |
| 重复 | 无（0） |
| min / max | 10000 / 2300501 |
| 0 或负数 | 无（0 个） |
| 严格升序 | 是 |
| 字节数 / 行数 | **1558** / **258** |
| UTF-8 无 BOM / LF / 结尾换行 | ✅ / ✅（文件内无 `\r`）/ ✅ |
| sha256 | `d1b12814c91e7fe17475a534ebbce3e1ed4cff8b3bdad56dc763ef915dc9b13e` |

### 4.2 `ClientFurnitureIds.txt` — `FurnitureDBSchema`.`Id`

| 指标 | 值 |
|---|---|
| 源表行数 | 876 |
| 导出 id 数 / 去重后 | 876 / 876 |
| 重复 | 无（0） |
| min / max | 1 / 1000000 |
| 0 或负数 | 无（0 个） |
| 严格升序 | 是 |
| 字节数 / 行数 | **5240** / **876** |
| sha256 | `625b58a22e0eeec7ae6aca9519af4f2219a25529341fc3a1410285cb1c0aade6` |

id 段分布（用于判断是否拿错表）：`1–11`：11 个（默认房间 11 件套）／`1xxx–9xxx`：184／`10xxx–99xxx`：472／`100xxx–999xxx`：208／`≥1000000`：1。
最大号 1000000 = `Cafe/my_etc_martdisplay`（真实家具，不是哨兵值）；`301302` = `Cafe/my_trophycabinet_set102_platinum`（奖杯柜），模式自洽。

### 4.3 `ClientCharacterIds.txt` — `CharacterDBSchema`.`Id`

| 指标 | 值 |
|---|---|
| 源表行数 | 7223 |
| 导出 id 数 / 去重后 | 7223 / 7223 |
| 重复 | 无（0） |
| min / max | 10000 / 838060812 |
| 0 或负数 | 无（0 个） |
| 严格升序 | 是 |
| 字节数 / 行数 | **63304** / **7223** |
| sha256 | `80e87e4cae88b97821a4bf54a264849056fdfd06090365fe495c57f18e2eb745` |

**⚠ 这个文件是「客户端能解析的全部角色行」，不等于「可玩角色」。** 7223 行里只有 **257** 行落在可玩 5 位段：

| 段 | 数量 |
|---|---|
| 可玩 `10000–26015` | **257** |
| 5 位其它 `26016–99999`（如 29000, 30000） | 51 |
| 7 位（如 `7000001`） | 3649 |
| 8 位 | 396 |
| 9 位及以上（如 `838060812`） | 2870 |

`ProductionStep` 分布：`3`×7169、`0`×40、`2`×10、`1`×4 —— 无法靠该列区分「可玩 / NPC·敌人」，可靠判据是可玩 id 区段本身。
→ **一键发放角色时，白名单只负责「客户端认不认」；要发谁还得再叠一层「可玩角色」过滤**（建议 `10000 ≤ Id ≤ 26015`，257 个；若要「角色+其专武都齐」，则是 §4.5 的 254 个专武 id 所对应的角色）。把 7223 个 id 全发出去会把 NPC/敌人/9 位杂项塞进玩家账号。

### 4.4 `ClientEquipmentIds.txt` — `EquipmentDBSchema`.`Id`

| 指标 | 值 |
|---|---|
| 源表行数 | 191 |
| 导出 id 数 / 去重后 | 191 / 191 |
| 重复 | 无（0） |
| min / max | 1 / 109009 |
| 0 或负数 | 无（0 个） |
| 严格升序 | 是 |
| 字节数 / 行数 | **1073** / **191** |
| sha256 | `fe60518503bb9558e0b35414afb27a83438acfdbd39a6e785d587098f88f18ff` |

段分布：`<100`：20／`1000–9999`：90／`10000–99999`：0／`≥100000`：81。与 `EquipmentStatDBSchema` 行数（191）严格对上。

### 4.5 `ClientWeaponIds.txt` — `CharacterWeaponDBSchema`.`Id`

| 指标 | 值 |
|---|---|
| 源表行数 | 254 |
| 导出 id 数 / 去重后 | 254 / 254 |
| 重复 | 无（0） |
| min / max | 10000 / 26015 |
| 0 或负数 | 无（0 个） |
| 严格升序 | 是 |
| 字节数 / 行数 | **1524** / **254** |
| sha256 | `9ecf356ec853b334f548421f64e425dfcfdd2da51282e0599f87e181d823ec6e` |

专武 id 与角色 id **同号**（专武就是「该角色的专属武器」）：254 个里有 **235** 个能在 `CharacterDBSchema` 找到同号角色；剩下 19 个（`10127–10136`、`16018`、`16019`、`20050–20056`）在角色表里没有对应行 —— 见 §5.3 的解释，**不要据此判定白名单有错**。

### 4.6 `ClientEmblemIds.txt` — `EmblemDBSchema`.`Id`

| 指标 | 值 |
|---|---|
| 源表行数 | 1065 |
| 导出 id 数 / 去重后 | 1065 / 1065 |
| 重复 | 无（0） |
| min / max | 1 / 900000003 |
| 0 或负数 | 无（0 个） |
| 严格升序 | 是 |
| 字节数 / 行数 | **8474** / **1065** |
| sha256 | `7a95df573c27443b2380adfcd75344c57c45f5f28da96a57c324525c0c6d0757` |

大号段抽查确认是真实徽章而非脏行：`900000000` = `Emblem_Icon_HoshinoMidAutumn`、`900000001` = `Emblem_Icon_Concert1`、`900000002` = `Emblem_Icon_WebMiniGameMidAutumn`、`900000003` = `Emblem_Icon_ProductBundleMonthly`、`190000160` = `Emblem_BG_SpecialOperation_1_1_1`、`9000000` = `Emblem_BG_Etc_001`。

---

## 5. 记忆大厅 × 角色 交叉验证

### 5.1 历史 id 段逐段核对（全部吻合，零差异）

| 历史段 | 应有点数 | 实有点数 | 缺失 | 段外多出 |
|---|---|---|---|---|
| `10000–10098` | 99 | **99** | 无 | 无 |
| `10100–10136` | 37 | **37** | 无 | 无 |
| `13000–13014` | 15 | **15** | 无 | 无 |
| `16000–16019` | 20 | **20** | 无 | 无 |
| `20000–20056` | 57 | **57** | 无 | 无 |
| `23000–23008` | 9 | **9** | 无 | 无 |
| `26000–26015` | 16 | **16** | 无 | 无 |
| 7 位 `1000501 / 1001001 / 1300401 / 1300801 / 2300501` | 5 | **5（全部命中）** | 无 | 无 |
| **合计** | **258** | **258** | **0** | **0** |

`MemoryLobbyDBSchema` 的全部 id **恰好**等于上述 7 段 ∪ 5 个 7 位 id，**没有任何段外 id**（`set(lobby) - covered = ∅`）。
注意段边界本身是对的：`10098→10100`、`10136→13000` 之间的空洞是**真实空洞**（历史文档记录的就是分段并集，不是一段连续区间）。

### 5.2 与 `CharacterDBSchema` 的交集 = **234**（历史结论「同号」只成立 90.7%）

- 大厅 id 集合：258
- 角色 id 集合：7223
- **交集：234**
- 只在记忆大厅、不在角色表：**24 个**

```
10127 10128 10129 10130 10131 10132 10133 10134 10135 10136
16018 16019
20050 20051 20052 20053 20054 20055 20056
1000501 1001001 1300401 1300801 2300501
```

这 24 个不是脏数据 —— 上一节已逐段核过它们都在历史段内。原因是 `CharacterDBSchema` 的可玩段在**这几处比大厅表短**：角色表 `10126→13000` 断（少 `10127–10136`）、`16017→19000` 断（少 `16018/16019`）、`20049→23000` 断（少 `20050–20056`）。

### 5.3 为什么「同号」会在 24 个上失效（blob 命名直接给出答案）

| id | blob 内名字 | 说明 |
|---|---|---|
| `10127` | `LobbyCH0317` / `Lobbyillust_Icon_CH0317_01` | **按 `CH0xxx` 角色槽命名的独立大厅**，其 id 不指向可玩角色 |
| `10128` | `LobbyCH0318` | 同上 |
| `10129` | `LobbyCH0325` | 同上 |
| `10130` | `LobbyCH0309` | 同上 |
| `10131` | `LobbyCH0229` | 同上 |
| `10132` | `LobbyCH0297` | 同上 |
| `1000501` | `LobbyHoshino_multi`（`Hoshino_02` 立绘） | **7 位 id = 角色号×100+01 的「多形态」大厅**：10005→1000501 |
| `1001001` | `LobbyShiroko_multi` | 10010→1001001 |
| `1300401` | `LobbyNonomi_multi` | 13004→1300401 |
| `1300801` | `LobbySerika_multi` | 13008→1300801 |
| `2300501` | `LobbyAyane_multi` | 23005→2300501 |

**结论（对用法有直接影响）：**

1. 「大厅 id 与角色 id 同号」**只对 234 个成立**，不能反过来用「角色表有 = 大厅表有」或「大厅表有 = 角色表有」去互相推导 —— 会各错 24 个。
2. 7 位大厅 id 是**编码规则**（`角色号×100 + 01`），不是笔误、也不是 6 位 id 多了个 0。
3. 因此 `ClientMemoryLobbyIds.txt` 必须**独立以 `MemoryLobbyDBSchema` 为准**发放；`ClientCharacterIds.txt` 也必须独立以 `CharacterDBSchema` 为准。两份文件不可互相派生。
4. 反过来看，`ClientWeaponIds.txt` 也有同样现象（19 个专武 id 没有同号角色行），说明**这一批「角色派生表比角色表长」是这批表的固有特征**，不是导出漏行。

---

## 6. 管线自校验：用已批准产物反证抽取方法

既有 `Resources/ClientItemIds.txt`（2026-11-19 00:42 生成，已投入生产过滤）就是从**同一个库的 `ItemDBSchema.Id`** 导出的。
我用本次这套完全相同的抽取代码重跑 `ItemDBSchema`，与线上文件的 1803 个数字行逐个比对：

```
mine=1803  file=1803  identical=True  symmetric_difference=[]
```

→ 抽取方法、`Id` 列选取、排序规则、写文件格式这一整条链路，已被一个**已上线的既有产物**证明等价。上述 6 个文件的数值因此可直接采信。

---

## 7. 文件格式与兼容性

- 编码 **UTF-8 无 BOM**（首字节非 `EF BB BF`，实测 `bom=False`）；内容为 ASCII 十进制数字，等价于纯 ASCII。
- 行尾 **LF**（实测文件内 `\r` 计数为 0）；**结尾有且仅有一个换行**（`trailing_nl=True`）。
- 每行恰好一个十进制 id，**严格升序**，无空行、无表头、无重复 —— 按任务书「纯数字」要求。
- **与同目录既有 `ClientItemIds.txt` 的格式差异（须知）**：那个文件带 28 行 `#` 注释头（含 source md5/sha256、entries、复现命令），本次 6 个文件按任务书要求**不带任何注释行**。
  兼容性已核对：服务端加载器 `srv_src/Shittim-Server/Services/ClientItemFilter.cs:247` 只接受 `long.TryParse` 成功的行、其余行静默跳过，
  因此「纯数字无头」与「带 `#` 头」两种文件**同一个加载器都能读**（纯数字是它的严格子集，不存在被注释行解析失败的风险）。
  若之后要沿用 `ClientItemIds.txt` 的风格补 `#` 头，请连同加载器一起改，不要只改文件。
- 全部 6 个文件均为**新建**：写入前逐一断言文件不存在（`assert not os.path.exists(...)`），不存在覆盖既有文件的情况。

---

## 8. 自检结果

| 检查项 | 期望 | 实测 | 结论 |
|---|---|---|---|
| `ExcelDB.db` md5（导出前） | `824ce3a8bee2bb5ae36ada1ac95048f1` | `824ce3a8bee2bb5ae36ada1ac95048f1` | ✅ |
| `ExcelDB.db` md5（导出后复核） | 同上 | `824ce3a8bee2bb5ae36ada1ac95048f1` | ✅ **未被改动** |
| `ExcelDB.db` 大小 | 160,534,528 B | 160,534,528 B | ✅ |
| `data\` 下 `-wal` / `-shm` | 不得产生 | `[]`（空） | ✅ **无残留** |
| `ClientItemIds.txt` md5 | 不得变化 | `20ba364daf219792d574c9f2f18c78f5`（前=后） | ✅ **一个字节都没动** |
| `ClientItemIds.txt` mtime | 不得变化 | 2026-11-19 00:42:14（仍为原值） | ✅ |
| 新建文件数 | 6 数据 + 1 报告 | 6 + 1 | ✅ |
| 新建脚本文件 | 不得有 | 0（全部 `python -` 内联执行） | ✅ |
| 每个文件 无BOM/LF/结尾换行/纯数字/升序 | 全部为真 | 6/6 全部为真 | ✅ |

---

## 9. 交付清单（可直接落地的数值）

| 文件 | 绝对路径 | 字节数 | 行数 | id 数 | sha256 |
|---|---|---|---|---|---|
| `ClientMemoryLobbyIds.txt` | `…\Shittim-Server\Resources\ClientMemoryLobbyIds.txt` | 1558 | 258 | 258 | `d1b12814c91e7fe17475a534ebbce3e1ed4cff8b3bdad56dc763ef915dc9b13e` |
| `ClientFurnitureIds.txt` | 同上目录 | 5240 | 876 | 876 | `625b58a22e0eeec7ae6aca9519af4f2219a25529341fc3a1410285cb1c0aade6` |
| `ClientCharacterIds.txt` | 同上目录 | 63304 | 7223 | 7223 | `80e87e4cae88b97821a4bf54a264849056fdfd06090365fe495c57f18e2eb745` |
| `ClientEquipmentIds.txt` | 同上目录 | 1073 | 191 | 191 | `fe60518503bb9558e0b35414afb27a83438acfdbd39a6e785d587098f88f18ff` |
| `ClientWeaponIds.txt` | 同上目录 | 1524 | 254 | 254 | `9ecf356ec853b334f548421f64e425dfcfdd2da51282e0599f87e181d823ec6e` |
| `ClientEmblemIds.txt` | 同上目录 | 8474 | 1065 | 1065 | `7a95df573c27443b2380adfcd75344c57c45f5f28da96a57c324525c0c6d0757` |

（「行数」= LF 个数 = id 行数，因每行恰一个 id 且结尾有换行，两者恒等。所有文件 mtime = 2026-11-19 23:35:46 本地。）

---

## 10. 复现方式（不改任何已有文件，可随时重跑核对）

```powershell
# 只读打开 + 导出 + 自检，全部内联，不落脚本文件
$env:PYTHONIOENCODING="utf-8"
@'
import sqlite3, hashlib, os
DB  = r"C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\data\ExcelDB.db"
RES = r"C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\srv_src\Shittim-Server\Resources"
SPECS = [("ClientMemoryLobbyIds.txt","MemoryLobbyDBSchema"),
         ("ClientFurnitureIds.txt","FurnitureDBSchema"),
         ("ClientCharacterIds.txt","CharacterDBSchema"),
         ("ClientEquipmentIds.txt","EquipmentDBSchema"),
         ("ClientWeaponIds.txt","CharacterWeaponDBSchema"),
         ("ClientEmblemIds.txt","EmblemDBSchema")]
con = sqlite3.connect("file:%s?mode=ro&immutable=1" % DB.replace("\\","/"), uri=True)
con.execute("PRAGMA query_only=1")
for fn, tbl in SPECS:
    ids = sorted({r[0] for r in con.execute('SELECT "Id" FROM "%s"' % tbl)})
    data = "".join("%d\n" % i for i in ids).encode("ascii")
    have = hashlib.sha256(data).hexdigest()
    cur  = hashlib.sha256(open(os.path.join(RES,fn),"rb").read()).hexdigest()
    print("%-28s n=%-5d bytes=%-6d sha256=%s  MATCH=%s" % (fn, len(ids), len(data), have[:16], have==cur))
con.close()
'@ | python -
```

预期全部输出 `MATCH=True`（即 6 个文件与库内容零漂移）。

---

## 11. 给后续实现的三条要点

1. **白名单只回答「客户端认不认这个 id」，不回答「该不该发」**。与 `ClientItemIds.txt` 同一语义：服务器行的存在性与下发与否解耦，发送前过滤、库里不删行。
2. **角色必须二次过滤**。`ClientCharacterIds.txt` 的 7223 个 id 含 NPC/敌人/9 位杂项；「一键发放全角色」应以 `10000 ≤ Id ≤ 26015`（257 个）为界，或直接用 `ClientWeaponIds.txt` 的 254 个专武 id 反查角色。
3. **四张「派生表」不要互相推导**：大厅表比角色表多 24 个 id、专武表比角色表多 19 个 id，各自独立按本文件发放，否则会确定性漏发这批新内容。
