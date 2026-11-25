# SCHEMA_V2_DESIGN —— 多用户私服「账号 → 实体」关系化数据层设计

> 配套 DDL：[schema_v2.sql](schema_v2.sql)（80 表 / 496 列 / 22 索引）
> 现有数据层（只读，本设计一个字节都没改）：[schema_sqlite.sql](schema_sqlite.sql)、[account_service.py](account_service.py)、[schema_mysql.sql](schema_mysql.sql)
> 证据来源：[02_1017_api_account_loginsync.response.json](../../../report/_tmp/official_decoded_201/02_1017_api_account_loginsync.response.json) 等 201 条官方明文；静态表 [ExcelDB.db](../../data/ExcelDB.db)（398 张表）

---

## 0. 摘要（先给数字）

| 项 | v1（现状） | v2（本设计） |
|---|---|---|
| 表 | 6 | **80**（新增，v1 的 6 张一张未动） |
| 列 | 53 | **496** |
| 索引 | 10（显式） | **22**（新增段；v1 的 10 条一条没动） |
| 归属键 | `server_id` | `server_id`（全表贯穿，可级联删号） |
| 能承载的协议对象 | 21 个 JSON blob（`account_blobs`） | 26 个 1017 子回包 + 4 个独立协议，全部落到显式列 |

**三条硬事实（都是实测，不是估算）：**

1. **单账号**（本抓包账号：Lv58 / 主线 16 章 / 46 角色）：**3 555 行**，净增 **333 KB**。
2. **100 账号**（同一份数据复刻 100 次）：**356 080 行**，**33.33 MB**，平均 **341.3 KB/账号**。
3. **满进度单账号**（按各表实测字节/行外推 + ExcelDB 行数上界）：**约 12 370 行 / 约 1 062 KB ≈ 1.04 MB**；100 个满进度账号 **≈ 104 MB**。

**隔离性已用 SQL 验证过**（见 §11.3）：B 账号引用 A 账号的角色/装备 → `FOREIGN KEY constraint failed`；`DELETE FROM accounts` → 72 张账号表 0 行残留，共享表与其它账号不受影响。

---

## 1. 输入与证据

### 1.1 抓到的协议

`02_1017_api_account_loginsync.response.json` 的 `inner` 有 **35 个键**：

- **5 个信封字段**：`Protocol` / `SessionKey{AccountServerId,MxToken}` / `ServerTimeTicks` / `ServerNotification` / `RequestId`
- **26 个具名子回包**：`CafeGetInfoResponse` … `MultiFloorRaidLoginResponse`
- **4 个裸字段**：`FriendCount`、`FriendCode`、`PickupFirstGetHistoryDBs`、`AccountLevelRewardIds`

总计 5 + 26 + 4 = 35，与实测键数一致。

### 1.2 独立协议

| 协议 | 文件 | 谁用 |
|---|---|---|
| 24000 `Academy_GetInfo` | `01_24000_api_academy_getinfo.response.json` | `academy_states` / `academy_locations` / `academy_zone_visits` / `academy_zone_schedules` |
| 4000 `Item_List` | `03_4000_api_item_list.response.json` | `items` |
| 5000 `Echelon_List` | `47_5000_api_echelon_list.response.json` | `echelons` / `echelon_slots` / `echelon_combat_styles` |
| 20001 `Cafe_Ack` | `87_20001_api_cafe_ack.response.json` | `cafes` / `cafe_productions` / `cafe_production_parcels` / `cafe_visits` |
| 8000 / 8006 / 35003 任务 | 各自 response | `mission_progress` / `mission_history` / `guide_mission_seasons` |
| 10002 `Shop_List` | `86_10002_api_shop_list.response.json` | `shop_infos` / `shop_products` / `shop_eligma_histories` |
| 7000 / 7003 邮件 | `25_7000`、`24_7003` | `mails` / `mail_parcels` |
| 90004 `Management_Data` | `06_90004` | `management_notices` / `management_banners` / `management_gacha_displays`（**共享**） |
| 1005 `Account_GetTutorial` | `07_1005` | `account_tutorials` |
| 36001 红点 | `16_36001` | `event_content_unlock_cgs` |

### 1.3 校验方式

不是"写完就交"，而是：

1. 把官方抓包按 §1.1 的映射**整包灌进** v1+v2 建出来的真库（`%TEMP%/v2bench_*.sqlite3`）；
2. 全程 `PRAGMA foreign_keys = ON`，让每一条外键/主键/CHECK 实际执行一次；
3. `dbstat` 逐表统计页数 → §7 的容量数字；
4. 另有 6 条破坏性测试（跨账号引用、重复实体 id、CHECK 违约、删号级联）→ §11.3。

灌库过程中**真的报错了 5 次**，每次都是一个设计缺陷，已修（见 §11.1）：`cafe_db_id` 派生关系、`GachaProbabilityDisplayId` 不是唯一键、`mission_history` 重复存储、`mission_progress` 缺 `is_complete`、复合外键 `ON DELETE SET NULL` 撞 `NOT NULL`。

---

## 2. 设计原则

### 2.1 R1 —— 只新增，不动老表

`schema_v2.sql` 里没有一条 `ALTER` / `DROP`，也没往 v1 的 `schema_meta` 写东西（v2 用独立的 `schema_v2_meta`）。所以：

- `account_service.py` 不改一行也能继续跑（selftest 20/20 不受影响）；
- 回滚 = 删掉 v2 的 80 张表（§6.6），或直接还原备份文件。

### 2.2 R2 —— 从属关系：一个卡密 = 一个账号 = 一个 `server_id`

```
accounts(server_id)                     ← v1，钉死不动的唯一身份表
   ├── account_progress / account_settings / account_currencies(29 行) / entity_id_alloc
   ├── characters ── character_potentials / character_equipment_slots
   │              └─ echelon_slots / gears / weapons / costumes / clan_assist_slots
   ├── equipment / items / furniture(→cafes)
   ├── echelons ── echelon_slots / echelon_combat_styles
   ├── cafes ── cafe_productions / cafe_production_parcels / cafe_visits
   ├── academy_states / academy_locations / academy_zone_visits / academy_zone_schedules
   ├── scenarios / campaigns / missions / momotalk / emblems / stickers / memory_lobbies
   ├── arena / raid / eliminate_raid / multi_floor_raid / time_attack
   ├── shop_* / billing_* / event_content_* / craft_* / mails
   └── clan_members(→clans 共享)
```

落地数字：

| 类别 | 数量 |
|---|---|
| v2 表总数 | 80 |
| 带 `server_id` 列 | **72** |
| 直接 `FOREIGN KEY (server_id) REFERENCES accounts` | **61** |
| 经父表间接从属（父表主键含 `server_id`） | **11** |
| 无 `server_id` 的共享表 | **8** |

那 11 张"孙子表"是：`character_potentials`、`character_equipment_slots`、`echelon_slots`、`echelon_combat_styles`、`cafe_productions`、`cafe_production_parcels`、`cafe_visits`、`mail_parcels`、`multi_sweep_preset_stages`、`multi_sweep_preset_parcels`、`craft_nodes`。它们的外键指向父表的 `(server_id, …)` 复合主键，父表再指向 `accounts` —— 传递保证"不属于这个账号的实体不可能被你写出来"，同时级联链最短。§11.3 的删号测试证明这条链是通的（0 行残留）。

**为什么有 8 张共享表**：见 §9.2。它们承载的是"全服同一份"的目录/配置，按账号复制 100 份只会得到 100 份可能不一致的副本。

### 2.3 R3 —— 不拿 JSON blob 糊

结构化字段一律显式列。只有两类真的该用 JSON：

| 表.列 | 为什么只能是 JSON |
|---|---|
| `mission_progress.progress_json` | `ProgressParameters` 是 `Dictionary<long,long>`，键是"第几个完成条件"（实测键 `0`..`5`），**不是实体**、没有可枚举的列语义 |
| `craft_nodes.leaf_node_ids_json` | `LeafNodeIds: List<long>` 变长、无独立语义 |

另有 **2 个 `passthrough_json` 列**，仅当协议对象里存在"客户端只读、服务端从不查询/计算"的字段时才用：

| 表 | 装什么 | 为什么 |
|---|---|---|
| `cafes` | `CurrencyDict_Obsolete` / `UpdateTimeDict_Obsolete` | DTO 里有、wire 上根本不出现、官方已废弃 |
| `memory_lobbies` | `ParcelInfos` | 抓包里恒为 `null`，没有列语义 |

### 2.4 可变状态 vs 静态引用

| | 落库 | 例子 |
|---|---|---|
| **可变状态**（玩家能改） | ✅ | 等级、经验、星级、装备绑定、编队、剧情进度、任务进度、币、货币时间戳、舒适度、排名、商店购买计数 |
| **静态引用**（ExcelDB 定义） | ❌ 不落库，响应时现查 | 角色属性/技能数值、装备属性、家具舒适度、卡池概率、关卡消耗、任务条件、商店价格 |
| **"当时快照"** | ✅ 落库 | `cafe_productions.comfort_value`（结算用，家具改了不能改历史产量）、`clans.clan_president_nickname`（游戏侧不同步，1:1 还原官方行为） |
| **随机结果** | ✅ 落库 | `craft_nodes.node_random_seed` / `result_id` |

判断依据的完整版在 §9.1。

### 2.5 实体 id 模型（实测推出来的，不是拍的）

抓包里同一个账号的 `ServerId` 落在**两个互不相交的带**：

| 带 | 实测范围 | 表 |
|---|---|---|
| 角色 | 3 002 866 … 3 135 930（46 个） | `characters` + `gears/weapons/costumes`（绑角色） |
| 道具类 | 24 345 539 … 28 344 578 | `items`（134）/ `equipment`（84）/ `furniture`（27） |

三张道具表的 id 交集 **= 0**，角色带与道具带交集 **= 0**。所以 v2 用 `entity_id_alloc(server_id, band, next_id)` 两条带各一个游标，取代 v1 的单个 `accounts.next_entity_id`（一个游标喂不了两个带）。

主键统一为 `(server_id, entity_id)`，即 **entity_id 只在账号内唯一**。好处：抓包里那种 7 位数 id 不会被跨账号污染；坏处：跨账号引用必须带 `server_id` —— 而这正好是隔离性的来源（§11.3 测试 [1][2]）。

`CafeDBId` 不是发号器产物，是**派生值**：

```
100153543801 = 10015354380 * 10 + 1     (cafe_id = 1)
100153543802 = 10015354380 * 10 + 2     (cafe_id = 2)
```

DDL 用 `CHECK (cafe_db_id = server_id * 10 + cafe_id)` 把这个关系钉死。代价见 §6.5：复制账号数据必须重算 `cafe_db_id`。

### 2.6 时间与零值归一化（两条铁律）

| wire 上 | 落库 | 依据 |
|---|---|---|
| `'0001-01-01T00:00:00'`、`'0001-01-01T14:00:00'`、`'0001-01-01T00:00:00Z'` | `NULL` | Go 零时间。**必须按前缀 `substr(ts,1,10)='0001-01-01'` 判断**，因为时区 +8 小时后是 `0001-01-01T14:00:00`（实测 `ArenaPlayerInfoDB.DailyRewardActiveTime` 就是 `0001-01-01T14:00:00`），按字符串全等匹配会漏 |
| 实体引用 `0` | 删除该行 或 `NULL` | `CharacterDB.EquipmentServerIds` 实测 138 槽里 108 个是 `0`（空槽）；`CafeVisitCharacterDBs[*].ServerId` 恒 `0`；`FurnitureDB.CafeDBId=0` 表示未摆放。存 0 会让外键立刻炸 |

第三条（灌库时踩的）：**wire JSON 有 `omitempty`，字段会整块消失**。实测：

| 对象 | 缺失的字段 | 缺失行数 |
|---|---|---|
| `CampaignStageHistoryDB` | `TacticClearCountWithRankSRecord`（值 0） | 81 / 90 |
| `CampaignStageHistoryDB` | `Star1Flag` / `Star2Flag` / `Star3Flag`（值 false） | 6 / 90 |
| `EquipmentDB` | `Level` / `Tier` / `BoundCharacterServerId`（值 0） | 54 / 84 |
| `FurnitureDB` | `Rotation`（值 0） | 25 / 27 |
| `MissionProgressDB` | `Complete`（值 false） | 883 / 1240 |

所以：**每一列都必须有 `DEFAULT`，写库一律 `dict.get(键, 默认值)`，绝不 `d[键]`**。

---

## 3. 表总览

完整的分组清单见 §4；这里只给"按段统计"。

| 段 | 表数 | 行数（单账号，实测） |
|---|---|---|
| 0 全局共享 + 元信息 | 7 | 575（含 7 行 `schema_v2_meta`） |
| 1 账号级 | 6 | 55 |
| 2 角色 | 6 | 214 |
| 3 道具/装备/家具 | 3 | 245 |
| 4 编队 | 3 | 97 |
| 5 剧情/战役 | 5 | 314 |
| 6 任务 | 3 | 2 380 |
| 7 咖啡厅 | 4 | 14 |
| 8 学院 | 4 | 148 |
| 9 收集品 | 4 | 36 |
| 10 MomoTalk | 2 | 2 |
| 11 战斗赛季 | 7 | 3 |
| 12 商店/卡池/氪金 | 10 | 8 |
| 13 活动/扫荡/制造 | 11 | 33 |
| 14 邮件 | 2 | 4 |
| 15 公会 | 3 | 2 |
| **v2 合计** | **80** | **4 130** |
| v1（`accounts` 1 + `id_alloc` 1 + `schema_meta` 3） | 6 | 5 |
| **全库** | **86** | **4 135** |

> 其中 3 554 行属于账号（带 `server_id`），576 行属于共享表（`shop_recruits` 529 + `management_*` 39 + `schema_v2_meta` 7 + `clans` 1）。

---

## 4. 分表详解

字段级的逐列说明写在 `schema_v2.sql` 的列注释里（496 列每一列都有），本节给：**用途 / 协议来源 / 关键列 / 行数**。

### 4.1 第 0 段 · 全局共享 + 元信息（无 `server_id` 的共 8 张；`clans` 的业务叙述在第 15 段，这里一并列出便于对账）

| 表 | 协议来源 | 用途 | 关键列 | 实测行 | 满进度行 |
|---|---|---|---|---|---|
| `schema_v2_meta` | — | 结构版本与统计锚点 | `k`/`v`（含 `tables_v2=80`、`columns_v2=496`、`indexes_v2=22`） | 7 | 7 |
| `global_config` | 1002 `auth` / 1017 `functionClose` | 全服开关与常量 | `k`/`v` | 0 | ~20 |
| `management_notices` | 90004 `Data.Notices(6)`/`Events(14)`/`Issues(0)` | 公告/活动公告 | `notice_id`+`notice_kind` 复合主键 | 20 | 40 |
| `management_banners` | 90004 `Data.Banners(7)` | BANNER | `banner_id`、`linked_lobby_banner_id`、`banner_display_type`（实测 910101） | 7 | 20 |
| `management_gacha_displays` | 90004 `Data.GachaProbabilityDisplay(12)` | 概率公示 | **复合主键 `(display_id, linked_lobby_banner_id)`** | 12 | 20 |
| `global_toasts` | 16000 `ToastDBs` | 全服 Toast | `unique_id`、`toast_id` | 0 | 10 |
| `shop_recruits` | 1017 `ShopGachaRecruitListResponse.ShopRecruits(529)` | 卡池目录 | `shop_recruit_id`、档期 | 529 | 529 |
| `clans` | 1017 `ClanLoginResponse.AccountClanDB` | 公会本体 | `clan_db_id`、会长快照、`clan_manager_count`（wire 有、DTO 没有） | 1 | 50 |

> `management_gacha_displays` 的复合主键不是洁癖：12 条记录的 `GachaProbabilityDisplayId` **全是 2**，只拿它当主键会让后 11 条互相覆盖（灌库时实测报 `UNIQUE constraint failed`）。

### 4.2 第 1 段 · 账号级（6 张）

| 表 | 协议来源 | 用途 | 关键列 | 实测行 |
|---|---|---|---|---|
| `account_progress` | 1017 的散落标量 | 账号级进度游标单例 | `current_scenario_id`（`CampaignListResponse`）、`daily_sudden_mission_id`（8000）、`academy_location_rank_sum`、`multi_floor_raid_last_cleared_difficulty`、`has_content_save`（26000） | 1 |
| `account_currencies` | `AccountCurrencySyncResponse.AccountCurrencyDB` | 一个币种一行 | `currency_type`、`amount`、`update_time`、`expires_at` | 29 |
| `account_settings` | 1017 顶层 `FriendCount`/`FriendCode` + 模板 `option`/`restrictions` | 好友码、匿名、改名限制 | `friend_code`（partial unique）、`*_restricted` | 1 |
| `account_tutorials` | 1005 `TutorialIds` | 已完成的新手引导 | `tutorial_id` | 21 |
| `account_level_rewards` | 1017 顶层 `AccountLevelRewardIds` | 已领的等级奖励档 | `reward_id` | 1 |
| `entity_id_alloc` | — | 实体 id 发号器（两带） | `band`∈{`character`,`parcel`}、`next_id` | 2 |

**`academy_location_rank_sum` 为什么不从 `academy_locations` 推导**（实测反例）：

```
AcademyLocationDBs 9 行：rank = [2,1,1,2,1,1,2,2,2]  →  Σrank = 14，Σ(rank-1) = 5
AccountCurrencyDB.AcademyLocationRankSum = 1
```

三个数互不相等，说明它是独立的计数（本院另有用途），**必须单独落库**。这条同时是 §9.1 判据的反例：不是"能推就算出来"。

**为什么币种不用 JSON**：扣款是 `UPDATE ... SET amount = amount - ? WHERE amount >= ?` 的条件原子写。JSON 只能"读到内存 → 改 → 写回"，多开器同时领两份奖必然超发。29 个币种是有限枚举（`ExcelDB.CurrencyDBSchema` 正好 29 行），完全适合做行。

### 4.3 第 2 段 · 角色（6 张）

| 表 | 协议来源 | 用途 | 关键列 | 实测行 | 满进度 |
|---|---|---|---|---|---|
| `characters` | `CharacterListResponse.CharacterDBs(46)` | 一个角色实例一行 | `entity_id`(=ServerId)、`unique_id`、`star_grade`、`level`、`exp`、`favor_rank`、5 个技能等级、`is_new/is_locked/is_favorite` | 46 | 200 |
| `character_potentials` | `CharacterDB.PotentialStats` | 潜能 3 位各一行 | `stat_index`(1..3)、`stat_level` | 138 | 600 |
| `character_equipment_slots` | `CharacterDB.EquipmentServerIds` | 角色穿了哪件装备 | `slot_index`(0..2)、`equipment_entity_id` | 30 | 600 |
| `gears` | `CharacterGearListResponse.GearDBs` | 专属装备 | `level`、`tier`、`slot_index`、`bound_character_entity_id` | 0 | 200 |
| `weapons` | `CharacterListResponse.WeaponDBs` | 专武（无 ServerId） | 主键 `(server_id, unique_id)` | 0 | 200 |
| `costumes` | 模板 `characters.costumes` | 皮肤 | `bound_character_entity_id` | 0 | 60 |

**装备槽为什么要独立表**：`EquipmentServerIds` 实测 46×3 = 138 槽，其中 **108 槽是 `0`（空槽）**，剩下 30 个非零 id **全部**能在 `EquipmentDBs` 里找到。所以：

- 空槽 = **不建行**（不是存 NULL、更不是存 0）；
- 装备与角色的绑定**只在这张表**，`equipment` 表里不放 `bound_character`，避免两处描述同一事实；
- 反过来，`EquipmentDB` 在 wire 上**确实带** `BoundCharacterServerId`、但只在被穿着的那 30 条里出现（54/84 条缺失）—— 这是出包时的派生字段，从本表反查即可。

### 4.4 第 3 段 · 道具/装备/家具（3 张）

| 表 | 协议来源 | 用途 | 关键列 | 实测行 | 满进度 |
|---|---|---|---|---|---|
| `items` | 4000 `ItemDBs(134)` + `ExpiryItemDBs(0)` | 道具堆叠 | `unique_id`、`stack_count`、`expires_at`（NULL=永久） | 134 | 300 |
| `equipment` | `EquipmentItemListResponse.EquipmentDBs(84)` | 装备实例 | `stack_count`（有 78 的强化素材）、`level`、`tier`、`is_locked` | 84 | 400 |
| `furniture` | `CafeGetInfoResponse.FurnitureDBs(27)` | 家具实例 + 摆放 | `cafe_db_id`（NULL=仓库）、`position_x/y`（REAL）、`location`、`item_deploy_sequence` | 27 | 300 |

**`ItemDBs` 和 `ExpiryItemDBs` 合并**：`ItemDB` 本来就是 `{ServerId, UniqueId, StackCount, Expires}`，`Expires` 非空即"限时道具"，没有第二套字段可存。1040 → 1 张表。

**顶层 `FurnitureDBs(27)` 到底是哪 27 件**（实测）：

```
27 = cafe1 摆放的 14 件 + cafe2 摆放的 11 件 + CafeDBId=0（未摆放）的 2 件
     c1∩c2 = 0，父子集互不重叠
```

所以顶层不是"另一批家具"，而是**并集 + 未摆放**。一张表 + 可空 `cafe_db_id` 就够了，不需要"仓库表 / 摆放表"两张。

### 4.5 第 4 段 · 编队（3 张）

| 表 | 协议来源 | 用途 | 关键列 | 实测行 | 满进度 |
|---|---|---|---|---|---|
| `echelons` | `EchelonListResponse.EchelonDBs(8)` / 5000 | 编队头 | 主键 `(server_id, echelon_type, echelon_number, extension_type)`、`leader_entity_id`、`using_flag` | 8 | 12 |
| `echelon_slots` | `MainSlotServerIds`/`SupportSlotServerIds`/`SkillCardMulliganCharacterIds` | 第几位的角色 | `slot_kind`∈{`main`,`support`,`mulligan`}、`slot_index`、`character_entity_id` | 41 | 72 |
| `echelon_combat_styles` | `EchelonDB.CombatStyleIndex` | 每位的战斗风格 | `slot_index`(0..5)、`combat_style_index` | 48 | 72 |

实测形状：8 支编队 = `type 1 ×3`（第 1/2/3 队）、`2/3/4/6/11` 各 1 支；每支 `main` 4 个、`support` 2 个、`mulligan` 3 个、`combat_style` 6 个。41 = 30 main + 11 非零 support（其余 5 个 support 是 0 → 不建行）+ 0 非零 mulligan。

**`echelon_slots` 里的 `mulligan` 为什么和 main/support 同一张表**：三者都是"某个下标 → 某个角色"的定长数组，用 `slot_kind` 区分即可，拆三张表等于把同一件事写三遍。

**`combat_style` 为什么不塞进 slots**：`CombatStyleIndex[6]` 是按 **main 位**（不是按角色）索引的，空位也允许有值 —— 而 slots 里空位不建行。语义不同，必须分开。

### 4.6 第 5 段 · 剧情/战役（5 张）

| 表 | 协议来源 | 用途 | 关键列 | 实测行 | 满进度 |
|---|---|---|---|---|---|
| `scenario_histories` | `ScenarioListResponse.ScenarioHistoryDBs(191)` | 已看过的剧情节点 | `scenario_unique_id`、`clear_datetime` | 191 | 1 500 |
| `scenario_group_histories` | `ScenarioGroupHistoryDBs(21)` | 已通关的剧情组 | `scenario_type`、`event_content_id`、`is_return`、`is_permanent` | 21 | 120 |
| `scenario_collections` | `ScenarioCollectionDBs(0)` | 剧情收集品 | `group_id`、`unique_id`、`receive_date` | 0 | 200 |
| `campaign_stage_histories` | `CampaignListResponse.StageHistoryDBs(90)` / 6000 | 每关三星状态 | 14 列：`star1/2/3_flag`、`clear_turn_record`、`today_play_count`、`today_purchase_play_count_hard_stage`、`first_clear_reward_receive`、`star_reward_receive` | 90 | 407 |
| `campaign_chapter_clear_rewards` | `CampaignChapterClearRewardHistoryDBs(12)` | 章节通关奖励领取 | 主键 `(server_id, chapter_unique_id, reward_type)` | 12 | 40 |

实测 90 关覆盖第 101..116 章（9/6/8/5/5/6/5/5/6/5/5/6/5/5/6/3）。`ScenarioGroupHistoryDB` 的 wire 有 7 键（含 `IsPermanent`），DTO 只有 5 键 → **以 wire 为准，两列都存**。

### 4.7 第 6 段 · 任务（3 张）

| 表 | 协议来源 | 用途 | 关键列 | 实测行 | 满进度 |
|---|---|---|---|---|---|
| `mission_progress` | 8000 `ProgressDBs(1240)` + 8006 `MissionProgressDBs(733)` + 35003 `ProgressDBs(18)` | 任务进度 | `mission_kind`∈{`mission`,`guide`,`minigame`,`event`,`battlepass`}、`category`、`start_date`、`is_complete`、`progress_json` | **1 991** | 3 000 |
| `mission_history` | 8000 `MissionHistoryUniqueIds` / `ClearedOriginalMissionIds` | 已完成任务 | `mission_unique_id`、`complete_time`、`is_expired` | 372 | 2 000 |
| `guide_mission_seasons` | 8006 `GuideMissionSeasonDBs(17)` | 向导任务赛季 | `season_id`、`login_count`、`is_final_mission_complete` | 17 | 20 |

**三个协议共用一张表**：8000 / 8006 / 35003 的任务进度对象**字段完全一致**（`AccountServerId / MissionUniqueId / Category / StartDate / ProgressParameters`），只差来源。用 `mission_kind` 区分，不抄三张。

**`mission_history` 只存一份**（重要实测）：8000 的 `MissionHistoryUniqueIds`（372 条）和 `ClearedOriginalMissionIds`（372 条）**集合相同、顺序也相同**：

```
history == cleared  →  True；h−c = 0；c−h = 0；两个列表逐元素相等
```

它们是同一批 id 的两个回包字段，不是两种状态。最初设计成带 `source_list` 判别列、主键三列，灌库后发现会把同一份数据写两遍（744 行 vs 372 行，100 账号白占 2.4 MB）→ 改成一张表，出包时两个数组都从它取（按 `mission_unique_id` 升序，与实测顺序一致）。

**`idx_mission_progress_cat` 为什么被删**：实测 100 账号库上该索引占 **5 388 KB（全库 13%）**，而它服务的"按 category 取某类任务"本来就能用主键前缀 `(server_id, mission_kind)` 扫到该账号全部 1 240 行。加它只增写放大。

### 4.8 第 7 段 · 咖啡厅（4 张）

| 表 | 协议来源 | 用途 | 关键列 | 实测行 | 满进度 |
|---|---|---|---|---|---|
| `cafes` | `CafeGetInfoResponse.CafeDBs(2)` / 20001 `CafeDB` | 一个厅一行 | `cafe_db_id`（CHECK 派生）、`cafe_rank`、`last_summon_date`、`production_applied_time`、`passthrough_json` | 2 | 2 |
| `cafe_productions` | `CafeDB.ProductionDB` | 产量结算 | `comfort_value`（快照）、`applied_date` | 2 | 2 |
| `cafe_production_parcels` | `ProductionDB.ProductionParcelInfos` | 待领产量明细 | `parcel_type`、`parcel_id`、`amount` | 3 | 6 |
| `cafe_visits` | `CafeDB.CafeVisitCharacterDBs` | 来访学生 | `character_unique_id`（dict 键）、`character_entity_id`（可空）、`last_interact_time` | 7 | 14 |

**`CafeVisitCharacterDBs` 类型实测与 DTO 不符**：DTO 写 `List<VisitingCharacterDB>`，wire 上是 **dict**，键 = `UniqueId`（`{"10044": {...}, "10064": {...}}`），且每条 `ServerId` 恒 `0` —— 来访学生不是玩家的角色实例。所以：`character_unique_id` 是有效键，`character_entity_id` 落 `NULL`（不能存 0，会撞外键）。

**`comfort_value` 明明能从家具算出来，为什么还要落库**：它是**结算时刻的快照**。玩家摆完家具把产量领了、然后再撤掉家具，历史产量不能跟着变。这是 §9.1 判据 3 的正面例子。

### 4.9 第 8 段 · 学院（4 张）

| 表 | 协议来源 | 用途 | 关键列 | 实测行 | 满进度 |
|---|---|---|---|---|---|
| `academy_states` | 24000 `AcademyDB.LastUpdate` | 学院单例 | `last_update` | 1 | 1 |
| `academy_locations` | 24000 `AcademyLocationDBs(9)` | 设施等级/经验 | `location_id`、`rank`、`exp` | 9 | 11 |
| `academy_zone_visits` | `AcademyDB.ZoneVisitCharacterDBs` | 每个 zone 的来访学生 | `zone_id`（dict 键）、`visit_index`、`character_unique_id`、`last_interact_time` | 138 | 200 |
| `academy_zone_schedules` | `AcademyDB.ZoneScheduleGroupRecords` | zone 日程 | `zone_id`、`schedule_unique_id` | 0 | 40 |

实测 71 个 zone 键（1、10..17、20..26、30..37、40..47、50..57、70..77、80..87、90..97、110..117），其中 70 个非空，合计 138 条来访；设施 11 个里开了 9 个。

`ZoneScheduleGroupRecords` DTO 类型是 `Dictionary<long, List<long>>`，抓包为**空字典** → 语义未验证（§10）。

### 4.10 第 9 段 · 收集品（4 张）

| 表 | 协议来源 | 用途 | 关键列 | 实测行 | 满进度 |
|---|---|---|---|---|---|
| `memory_lobbies` | `MemoryLobbyListResponse.MemoryLobbyDBs(1)` | 记忆大厅 | `memory_lobby_unique_id`、`lobby_type`、`passthrough_json` | 1 | 8 |
| `stickers` | `StickerListResponse.StickerBookDB` | 贴纸（未用 20 / 已用 0） | `sticker_unique_id`、`is_used` | 20 | 100 |
| `emblem_histories` | `AttachmentEmblemListResponse.EmblemDBs(14)` | 纹章获得记录 | `emblem_unique_id`、`emblem_type`（实测恒 20）、`receive_date` | 14 | 60 |
| `account_attachments` | `AttachmentGetResponse.AccountAttachmentDB` | 当前佩戴的纹章 | `emblem_unique_id` | 1 | 1 |

`UnusedStickerDBs` / `UsedStickerDBs` 是同一件东西的两种状态 → 一列 `is_used`，不拆两张表。

### 4.11 第 10 段 · MomoTalk（2 张）

| 表 | 协议来源 | 用途 | 关键列 | 实测行 | 满进度 |
|---|---|---|---|---|---|
| `momotalk_outlines` | `MomoTalkOutLineResponse.MomoTalkOutLineDBs(1)` | 每个学生的会话头 | `character_unique_id`、`character_entity_id`、`latest_message_group_id`、`chosen_message_id` | 1 | 120 |
| `momotalk_favor_schedules` | `FavorScheduleRecords` | 已看的羁绊剧情 | `character_unique_id`、`schedule_unique_id` | 1 | 400 |

### 4.12 第 11 段 · 战斗赛季（7 张）

| 表 | 协议来源 | 用途 | 关键列 | 实测行 | 满进度 |
|---|---|---|---|---|---|
| `arena_players` | `ArenaLoginResponse.ArenaPlayerInfoDB` (+22016) | 竞技场单例 | `current_rank`、`season_record`、`all_time_record`、三个 CD 时间、`echelon_setting_time` | 1 | 1 |
| `raid_states` | `RaidLoginResponse` | 总力战（`SeasonType=1`） | `can_receive_ranking_reward`、`last_settled_ranking/tier` | 1 | 1 |
| `eliminate_raid_states` | `EliminateRaidLoginResponse`（`SeasonType=2`） | 大决战 | 同上 | 1 | 1 |
| `eliminate_raid_received_rewards` | `ReceiveLimitedRewardIds` | 已领限定奖励 | `reward_id` | 0 | 30 |
| `eliminate_raid_sweep_points` | `SweepPointByRaidUniqueId` | 每 boss 扫荡点 | `raid_unique_id`、`sweep_point` | 0 | 20 |
| `multi_floor_raids` | `MultiFloorRaidDBs`(null) | 多楼层总力战 | `season_id`、`cleared_difficulty`、`clear_battle_frame` | 0 | 3 |
| `time_attack_rooms` | `TimeAttackDungeonLoginResponse.PreviousRoom`(null) | 限时战斗房 | `season_id`、`room_id`、`is_practice` | 0 | 2 |

竞技场对手（`OpponentUserDBs`）**不落库**：它是别的账号的投影，响应时按排名区间从其它账号 join 出来（§9.4）。

### 4.13 第 12 段 · 商店/卡池/氪金（10 张）

| 表 | 协议来源 | 用途 | 关键列 | 实测行 | 满进度 |
|---|---|---|---|---|---|
| `shop_infos` | 10002 `ShopInfos(1)` | 一个货架一行 | 主键 `(server_id, category, event_content_id)`、`manual_refresh_count`、`next_auto_refresh_date` | 1 | 12 |
| `shop_products` | `ShopInfoDB.ShopProductList(2)` | 商品购买状态 | `purchase_count`、`purchase_count_limit`、`sold_out`（wire 有 / DTO 没有） | 2 | 200 |
| `shop_recruit_states` | 卡池的账号级差异 | 只存与目录不同的行 | `update_date` | 0 | 30 |
| `shop_free_recruit_histories` | `ShopFreeRecruitHistoryDBs(0)` | 免费十连计数 | `recruit_count` | 0 | 5 |
| `shop_eligma_histories` | 10002 `ShopEligmaHistoryDBs(0)` | 神明文字兑换计数 | `character_unique_id`、`purchase_count` | 0 | 20 |
| `pickup_first_get_histories` | 1017 顶层 `PickupFirstGetHistoryDBs(1)` | 首次获得 UP 记录 | `shop_recruit_id`、`log_date` | 1 | 30 |
| `billing_counts` | `BillingPurchaseListByYostarResponse.CountList(4)` | 商品限购计数 | `shop_cash_id`、`purchase_count`、`manual_reset_date` | 4 | 12 |
| `billing_orders` | `OrderList(0)` | 渠道订单 | `purchase_order_id`、`status_code` | 0 | 20 |
| `billing_monthly_products` | `MonthlyProductList(0)` | 月卡 | `product_id`、`reward_end_date` | 0 | 3 |
| `billing_blocked_products` | 模板 `billing.blockedProducts` | 禁售窗口 | `cash_product_id`、`begin/end_date` | 0 | 3 |

**529 条卡池为什么拆成"共享目录 + 账号差异"**：

- `ShopRecruitDBSchema` 是 532 行静态表，529 条就是它的子集，`Id`/档期都是静态数据；
- 抓包里 **529/529** 条 `UpdateDate` 全部是 `0001-01-01T00:00:00`（零值）→ **没有任何账号级差异可存**；
- 若按账号复制：100 账号 = 52 900 行纯重复，而且一旦目录更新就要改 100 份。

所以目录进 `shop_recruits`（共享，529 行），账号真有的差异进 `shop_recruit_states`（带 `server_id`，抓包里 0 行，这是**正常**的）。

### 4.14 第 13 段 · 活动/扫荡/制造（8 张）

| 表 | 协议来源 | 用途 | 关键列 | 实测行 | 满进度 |
|---|---|---|---|---|---|
| `event_content_permanents` | `EventContentPermanentListResponse.PermanentDBs(22)` | 常驻化活动 | `event_content_id`、`is_stage_all_clear`、`is_received_character_reward` | 22 | 60 |
| `event_content_changes` | 26000 `EventContentChangeDB` | 活动内兑换/改造计数 | `use_amount`、`change_count`、`change_flag` | 0 | 40 |
| `event_content_unlock_cgs` | 36001 `EventContentUnlockCGDBs` | 已解锁 CG | `event_content_id`、`cg_id` | 0 | 200 |
| `event_content_collections` | `EventContentCollectionDB` | 活动收集品 | `group_id`、`unique_id` | 0 | 200 |
| `multi_sweep_presets` | `MultiSweepPresetDBs(1)` | 多倍扫荡预设 | `preset_id`、`preset_name` | 1 | 3 |
| `multi_sweep_preset_stages` | `PresetId.StageIds(10)` | 预设关卡序列 | `slot_index`、`stage_unique_id` | 10 | 30 |
| `multi_sweep_preset_parcels` | `PresetId.ParcelIds(0)` | 预设道具 | `parcel_type`、`parcel_id` | 0 | 10 |
| `craft_slots` / `craft_nodes` / `craft_shifting_slots` / `craft_preset_slots` | `CraftInfoListResponse.*`(均 0) | 制造台/节点/转换/预设 | 见 DDL | 0 | 3/18/2/3 |

> 制造段实测全空（`CraftInfos`/`ShiftingCraftInfos`/`PresetSlotDBs` 都是 `[]`），表结构按 `dto_schema_full_v2.json` 的 `CraftInfoDB`/`CraftNodeDB`/`ShiftingCraftInfoDB`/`CraftPresetSlotDB` 建，**未经真实数据验证**。

### 4.15 第 14 段 · 邮件（2 张）

| 表 | 协议来源 | 用途 | 关键列 | 实测行 | 满进度 |
|---|---|---|---|---|---|
| `mails` | 7000 `MailDBs(2)` / 7003 | 邮件 | `mail_uid`(=MailDB.ServerId)、`sender`/`comment`（本地化 key）、`receipt_date`、`expire_date`、`is_semi_permanent` | 2 | 30 |
| `mail_parcels` | `ParcelInfos` + `RemainParcelInfos` | 附件/剩余 | `parcel_role`∈{`parcel`,`remain`}、`amount`、`multiplier`、`probability` | 2 | 45 |

**`MailDB.AccountServerId` 恒为 0，不存**：邮件是"发给账号"的遗留语义，归属列用我们自己的 `server_id`。这是 §9.1"常量回显不存"的典型。

### 4.16 第 15 段 · 公会（3 张）

| 表 | 协议来源 | 用途 | 关键列 | 实测行 | 满进度 |
|---|---|---|---|---|---|
| `clans` | `AccountClanDB` | 公会本体（**共享**） | `clan_db_id`、会长快照、`clan_manager_count` | 1 | 50 |
| `clan_members` | `AccountClanMemberDB` | **我的**公会关系 | `server_id` 主键（一账号最多一行）、`attendance_count`、`clan_social_grade`、`join_date` | 1 | 1 |
| `clan_assist_slots` | `ClanAssistSlotDBs(0)` | 我出借的助战 | `echelon_type`、`slot_number`、`character_entity_id` | 0 | 3 |

**公会为什么是共享表而不算破坏隔离**：50 个人共享同一个公会本体，这是业务事实，不是数据串号。隔离保证落在 `clan_members`：主键就是 `server_id`，一个账号只能有一行公会关系；任何写入前必须校验 `server_id` 属于当前会话。

**刻意不存的 4 个字段**：`AccountClanMemberDB.AccountLevel` / `AccountNickName` / `RepresentCharacterUniqueId` / `RepresentCharacterCostumeId` —— 都能从 `accounts` 和 `characters` join 出来。存副本必然出现"改了昵称公会列表还是旧名"。

---

## 5. 协议 → 表 映射矩阵

### 5.1 1017 的 26 个具名子回包

| # | 子回包 | 里的数据 | 落到 |
|---|---|---|---|
| 1 | `CafeGetInfoResponse` | `CafeDBs(2)` + `FurnitureDBs(27)` | `cafes` / `cafe_productions` / `cafe_production_parcels` / `cafe_visits` / `furniture` |
| 2 | `AccountCurrencySyncResponse` | `AccountCurrencyDB` + `ExpiredCurrency` | `account_currencies`（29 行）+ `account_progress.academy_location_rank_sum` |
| 3 | `CharacterListResponse` | `CharacterDBs(46)` + `TSSCharacterDBs(0)` + `WeaponDBs(0)` | `characters` + `character_potentials` + `character_equipment_slots` + `weapons` |
| 4 | `EquipmentItemListResponse` | `EquipmentDBs(84)` | `equipment` |
| 5 | `CharacterGearListResponse` | `GearDBs(0)` | `gears` |
| 6 | `ItemListResponse` | `null`（1017 里不带头；4000 才有 134 条） | `items` |
| 7 | `EchelonListResponse` | `EchelonDBs(8)` | `echelons` + `echelon_slots` + `echelon_combat_styles` |
| 8 | `MemoryLobbyListResponse` | `MemoryLobbyDBs(1)` | `memory_lobbies` |
| 9 | `CampaignListResponse` | `ChapterClearRewardHistoryDBs(12)` + `StageHistoryDBs(90)` + `CurrentScenarioId` | `campaign_chapter_clear_rewards` + `campaign_stage_histories` + `account_progress` |
| 10 | `ArenaLoginResponse` | `ArenaPlayerInfoDB` | `arena_players` |
| 11 | `RaidLoginResponse` | 4 标量 | `raid_states` |
| 12 | `CraftInfoListResponse` | 3 个空列表 | `craft_slots` / `craft_nodes` / `craft_shifting_slots` / `craft_preset_slots` |
| 13 | `ClanLoginResponse` | `AccountClanDB` + `AccountClanMemberDB` + `ClanAssistSlotDBs(0)` | `clans` / `clan_members` / `clan_assist_slots` |
| 14 | `MomoTalkOutLineResponse` | `MomoTalkOutLineDBs(1)` + `FavorScheduleRecords` | `momotalk_outlines` + `momotalk_favor_schedules` |
| 15 | `ScenarioListResponse` | `ScenarioHistoryDBs(191)` + `ScenarioGroupHistoryDBs(21)` + `ScenarioCollectionDBs(0)` | `scenario_histories` / `scenario_group_histories` / `scenario_collections` |
| 16 | `ShopGachaRecruitListResponse` | `ShopRecruits(529)` + `ShopFreeRecruitHistoryDBs(0)` | `shop_recruits`（共享）+ `shop_free_recruit_histories` |
| 17 | `TimeAttackDungeonLoginResponse` | `PreviousRoom=null` | `time_attack_rooms` |
| 18 | `BillingPurchaseListByYostarResponse` | `CountList(4)` + `OrderList(0)` + `MonthlyProductList(0)` | `billing_counts` / `billing_orders` / `billing_monthly_products` |
| 19 | `EventContentPermanentListResponse` | `PermanentDBs(22)` | `event_content_permanents` |
| 20 | `AttachmentEmblemListResponse` | `EmblemDBs(14)` | `emblem_histories` |
| 21 | `AttachmentGetResponse` | `AccountAttachmentDB` | `account_attachments` |
| 22 | `ContentSweepMultiSweepPresetListResponse` | `MultiSweepPresetDBs(1)` | `multi_sweep_presets` + `_stages` + `_parcels` |
| 23 | `EliminateRaidLoginResponse` | 6 标量 + 2 集合 | `eliminate_raid_states` / `_received_rewards` / `_sweep_points` |
| 24 | `StickerListResponse` | `StickerBookDB` | `stickers` + `account_attachments` |
| 25 | `MultiFloorRaidSyncResponse` | `MultiFloorRaidDBs=null` | `multi_floor_raids` |
| 26 | `MultiFloorRaidLoginResponse` | `LastClearedDifficulty` | `account_progress.multi_floor_raid_last_cleared_difficulty` |

**4 个裸字段**：`FriendCount`/`FriendCode` → `account_settings`；`PickupFirstGetHistoryDBs` → `pickup_first_get_histories`；`AccountLevelRewardIds` → `account_level_rewards`。

### 5.2 独立协议

| 协议 | 顶层键 | 落表 |
|---|---|---|
| 24000 `Academy_GetInfo` | `AcademyDB` / `AcademyLocationDBs` | `academy_states` / `academy_locations` / `academy_zone_visits` / `academy_zone_schedules` |
| 4000 `Item_List` | `ItemDBs` / `ExpiryItemDBs` | `items` |
| 5000 `Echelon_List` | `EchelonDBs` | `echelons` / `echelon_slots` / `echelon_combat_styles` |
| 20001 `Cafe_Ack` | `CafeDB` | `cafes` / `cafe_productions` / `cafe_production_parcels` / `cafe_visits` |
| 90004 `Management_Data` | `Data.*` | `management_notices` / `management_banners` / `management_gacha_displays`（共享） |
| 8000 / 8006 / 35003 | `ProgressDBs` / `MissionProgressDBs` / `HistoryDBs` | `mission_progress` / `mission_history` / `guide_mission_seasons` |
| 10002 `Shop_List` | `ShopInfos` / `ShopEligmaHistoryDBs` | `shop_infos` / `shop_products` / `shop_eligma_histories` |
| 7000 / 7003 | `MailDBs` | `mails` / `mail_parcels` |
| 1005 `Account_GetTutorial` | `TutorialIds` | `account_tutorials` |
| 36001 红点 | `Reddots` / `EventContentUnlockCGDBs` | `event_content_unlock_cgs` |

---

## 6. 迁移方案

### 6.1 关系怎么建立：不需要新增任何列

v1 的 `accounts.server_id` 就是本设计的全表外键目标 —— **同一个值、同一张表、同一个语义**（`SessionKey.AccountServerId`）。所以：

```
accounts.server_id  ==  characters.server_id  ==  ...  ==  mails.server_id
```

- 不给 `accounts` 加列（R1）；
- 新账号的 `server_id` 继续由 `id_alloc('server_id')` 发（起始 10 000 000 000，`CHECK (server_id >= 10000000000)` 兜底）；
- 删号只需 `DELETE FROM accounts WHERE server_id = ?`，72 张账号表靠外键链自动清空（实测 0 行残留）。

### 6.2 新账号要额外插的 9 张"必备单例表"

v1 的 `bootstrap_state()` 建了 41 个状态块的 JSON；v2 要把其中"单例行"显式建出来，否则下一次响应会因为 join 不到而缺字段：

| 表 | 至少的行数 | 内容 |
|---|---|---|
| `account_progress` | 1 | 全 0 |
| `account_settings` | 1 | 生成 `friend_code`（7 位小写字母数字，抓包 `slmv4wc`） |
| `account_currencies` | 29 | 按 `CurrencyDBSchema` 的 29 个币种各一行，`amount=0` |
| `entity_id_alloc` | 2 | `character` / `parcel` 两条游标 |
| `academy_states` | 1 | `last_update = now` |
| `arena_players` | 1 | `current_season_id` = 当前赛季 |
| `raid_states` | 1 | `season_type` = 当前 |
| `eliminate_raid_states` | 1 | 同上 |
| `account_attachments` | 1 | `emblem_unique_id = 0` |

`cafes`（2 行）+ `cafe_productions`（2 行）要按 `cafe_db_id = server_id*10 + cafe_id` 建；`academy_locations` 的 11 行可以懒创建（缺行 = rank 0）。

### 6.3 老数据：`account_blobs` → v2 表

v1 有 **21 个 blob kind**（`account_service.BLOB_LAYOUT`）。逐个映射：

| blob kind | 里面的键 | 写到 v2 |
|---|---|---|
| `option` | `option`/`restrictions`/`functionClose` | `account_settings`（前两个）+ `global_config`（`functionClose`） |
| `auth` | `auth` | `global_config` |
| `characters` | `characters`/`tssCharacters`/`weapons`/`costumes` | `characters` + `character_potentials` + `character_equipment_slots` + `weapons` + `costumes`（`tssCharacters` 无表，§10） |
| `equipment` | `equipments`/`gears` | `equipment` / `gears` |
| `items` | `items`/`expiryItems` | `items`（合并，靠 `expires_at` 区分） |
| `echelons` | `echelons`/`arenaEchelon` | `echelons` + `echelon_slots` + `echelon_combat_styles` |
| `memory_lobby` | `memoryLobby` | `memory_lobbies` |
| `emblems` | `emblems` | `emblem_histories` + `account_attachments` |
| `currency` | `currencies`/`expiredCurrency`/`accountCurrency` | `account_currencies` + `account_progress` |
| `cafe` | `cafe` | `cafes`/`cafe_productions`/`cafe_production_parcels`/`cafe_visits`/`furniture` |
| `arena` | `arena` | `arena_players` |
| `raid` | `raid`/`eliminateRaid` | `raid_states` + `eliminate_raid_*` |
| `clan` | `clan` | `clans` + `clan_members` |
| `momo_talk` | `momotalks` | `momotalk_outlines` + `momotalk_favor_schedules` |
| `scenario` | `scenarios` | `scenario_histories`/`scenario_group_histories`/`scenario_collections` |
| `campaign` | `campaign` | `campaign_stage_histories`/`campaign_chapter_clear_rewards` |
| `craft` | `craft` | `craft_slots`/`craft_nodes`/`craft_shifting_slots`/`craft_preset_slots` |
| `billing` | `billing` | `billing_counts`/`billing_orders`/`billing_monthly_products`/`billing_blocked_products` |
| `event` | `eventContent`/`shop`/`contentSweep`/`multiFloorRaid`/`timeAttack` | `event_content_*`/`shop_*`/`multi_sweep_*`/`multi_floor_raids`/`time_attack_rooms` |
| `social` | `attachment`/`stickerBook`/`settings` | `account_attachments`/`stickers`/`account_settings` |
| `progress` | `missionProgress`/`eventMissionProgress`/`battlePassMissionProgress` | `mission_progress`（`mission_kind` 区分）+ `mission_history` |

### 6.4 迁移步骤（可执行顺序）

```sql
-- ① 备份（文件级，必须做）
--    sqlite3 ba_accounts.sqlite3 ".backup ba_accounts.bak.sqlite3"

-- ② 建 v2（纯增量，不碰 v1）
.read schema_v2.sql

-- ③ 关外键做批量灌数据（否则中间态会因引用未就绪而失败）
PRAGMA foreign_keys = OFF;

-- ④ 按 server_id 逐账号搬运（每账号一个事务）。
--    批次顺序：accounts → characters → equipment → character_equipment_slots
--             → items/furniture → echelons/echelon_slots → cafes/cafe_* → 其余

-- ⑤ 收尾：重建共享表（见下）
-- ⑥ 开回外键并全库体检
PRAGMA foreign_keys = ON;
PRAGMA foreign_key_check;        -- 必须返回 0 行
PRAGMA integrity_check;          -- 必须返回 'ok'
```

**共享表怎么填**（只填一次，不给每个账号填）：

```sql
-- 529 条卡池目录：从 ExcelDB 的 ShopRecruitDBSchema 生成
INSERT OR REPLACE INTO shop_recruits
    (shop_recruit_id, sales_start_date, sales_end_date, update_date, synced_at)
SELECT Id, NULL, NULL, NULL, datetime('now') FROM excel.ShopRecruitDBSchema;
-- 90004 的三张配置表：把上一份管理数据 JSON 拆表灌入（一次性，之后随运营更新）
```

### 6.5 迁移的三个硬约束（都是从实测踩出来的）

| # | 约束 | 原因 |
|---|---|---|
| M1 | **`cafe_db_id` 必须按 `server_id*10 + cafe_id` 重算**，并同步改 `furniture.cafe_db_id` / `cafe_productions` / `cafe_production_parcels` / `cafe_visits` 的引用 | `cafes` 上有 `CHECK (cafe_db_id = server_id*10 + cafe_id)`。直接复制另一账号的行会 CHECK 失败（灌库时实测报 `CHECK constraint failed`） |
| M2 | **写入顺序**：`characters` → `equipment` → `character_equipment_slots`；`cafes` → `furniture` | 子表外键要求父行已存在（灌库时实测报 `FOREIGN KEY constraint failed`） |
| M3 | **零值归一化**：`'0001-01-01*'` → `NULL`；实体引用 `0` → 不建行 / `NULL` | 见 §2.6；不归一化会被 `CHECK` 和外键同时拒绝 |

### 6.6 老账号 `server_id = 10000000000` 怎么处理

**先说实测事实**：

- 全仓 `Glob **/*.sqlite3` / `**/*.db` 只有 `report/_tmp/manifest_pc.db` 和 `work/ba/data/ExcelDB.db` 两个 —— **未找到任何持久化的账号库文件**；
- `10000000000` 这个值只出现在 `account_service.py` 的 `--selftest` 断言（第 1327/1366/1403/1415/1417/1418/1471/1472 行）与文件头注释里，自检用的是临时库；
- 也就是说：**这一"老账号"目前只存在于自检脚本里，不构成真实数据迁移。**

**如果线上确实有这个库**，处理规则：

| 场景 | 处理 |
|---|---|
| 它是开发/自检账号 | 保留为普通账号（卡密体系里发一张测试卡密给它），按 §6.4 正常迁移即可 —— 它在 v2 里和其它账号**没有任何结构差异**，不需要特例分支 |
| 它的 `nickname='老师'`、`call_name` 是默认值 | 无需迁移动作；`account_settings.friend_code` 若为空串，`uk_account_settings_friend_code` 是 **partial unique index（`WHERE friend_code <> ''`）**，空串不参与唯一性，不会撞 |
| 它没有 v2 单例行 | 按 §6.2 补 9 张单例表的行（老库一定是这个状态，必须补） |

**唯一必须人工处理的一处**：`accounts.next_entity_id` 是**单游标**，v2 要拆成两条带：

```sql
-- 角色带游标 = max(现有角色 ServerId) + 1，取不到就退回 next_entity_id
INSERT INTO entity_id_alloc (server_id, band, next_id)
SELECT a.server_id, 'character',
       COALESCE((SELECT MAX(entity_id) + 1 FROM characters c WHERE c.server_id = a.server_id),
                a.next_entity_id)
FROM accounts a
WHERE NOT EXISTS (SELECT 1 FROM entity_id_alloc x
                  WHERE x.server_id = a.server_id AND x.band = 'character');

-- 道具带游标 = max(道具/装备/家具 ServerId) + 1
INSERT INTO entity_id_alloc (server_id, band, next_id)
SELECT a.server_id, 'parcel',
       COALESCE((SELECT MAX(v) + 1 FROM (
                   SELECT entity_id AS v FROM items     WHERE server_id = a.server_id UNION ALL
                   SELECT entity_id      FROM equipment WHERE server_id = a.server_id UNION ALL
                   SELECT entity_id      FROM furniture WHERE server_id = a.server_id)), 24345500)
FROM accounts a
WHERE NOT EXISTS (SELECT 1 FROM entity_id_alloc x
                  WHERE x.server_id = a.server_id AND x.band = 'parcel');
```

### 6.7 回滚

v1 的表一个字节没动，所以回滚是纯减法：

```sql
-- 立刻回到 v1（只删 v2 的东西）
PRAGMA foreign_keys = ON;
DROP TABLE IF EXISTS mail_parcels, mails, craft_preset_slots, craft_shifting_slots, craft_nodes,
  craft_slots, multi_sweep_preset_parcels, multi_sweep_preset_stages, multi_sweep_presets,
  event_content_collections, event_content_unlock_cgs, event_content_changes,
  event_content_permanents, billing_blocked_products, billing_monthly_products, billing_orders,
  billing_counts, pickup_first_get_histories, shop_eligma_histories, shop_free_recruit_histories,
  shop_recruit_states, shop_recruits, shop_products, shop_infos, time_attack_rooms, multi_floor_raids,
  eliminate_raid_sweep_points, eliminate_raid_received_rewards, eliminate_raid_states, raid_states,
  arena_players, momotalk_favor_schedules, momotalk_outlines, account_attachments, emblem_histories,
  stickers, memory_lobbies, academy_zone_schedules, academy_zone_visits, academy_locations,
  academy_states, cafe_visits, cafe_production_parcels, cafe_productions, cafes, furniture,
  campaign_chapter_clear_rewards, campaign_stage_histories, scenario_collections,
  scenario_group_histories, scenario_histories, echelon_combat_styles, echelon_slots, echelons,
  guide_mission_seasons, mission_history, mission_progress, costumes, weapons, gears,
  character_equipment_slots, character_potentials, characters, equipment, items, clan_assist_slots,
  clan_members, clans, global_toasts, management_gacha_displays, management_banners,
  management_notices, global_config, entity_id_alloc, account_level_rewards, account_tutorials,
  account_settings, account_currencies, account_progress, schema_v2_meta;
```

---

## 7. 容量估算（实测，非估算）

### 7.1 三个基准数字

| 场景 | 行数 | 库大小 | 说明 |
|---|---|---|---|
| **空库**（v1+v2 骨架，0 行） | 0 | **848 KB**（212 页） | 191 个 B-tree 对象（86 表 + 32 显式索引 + 73 自动索引）的根页 + `sqlite_schema`，是纯骨架开销 |
| **1 个中等进度账号**（Lv58 / 16 章 / 46 角色） | 4 135（账号 3 555 + 共享 580） | **1 168 KB** | 骨架 848 KB 占了大头 |
| **100 个中等进度账号** | 356 080 | **33.33 MB**（8 533 页） | 平均 **341.3 KB/账号** |

推算：`(33.33 MB − 848 KB) ÷ 100 = 332.8 KB/账号`，与单账号净增 348 KB − 共享 15.2 KB ≈ 333 KB 吻合。

**结论：骨架 848 KB 是一次性成本，第 2 个账号起每账号约 333 KB。**

### 7.2 单账号内部构成（100 账号库的 `dbstat` 逐表字节，表 + 该表全部索引）

| 排名 | 表（含其索引） | 100 账号占用 | 占比 |
|---|---|---|---|
| 1 | `mission_progress`（表 16 164 + 主键 5 828） | **21 992 KB = 21.5 MB** | **64.43%** |
| 2 | `scenario_histories`（表 764 + 主键 372 + 时间索引 816） | 1 952 KB | 5.72% |
| 3 | `mission_history`（表 712 + 主键 744） | 1 456 KB | 4.27% |
| 4 | `items`（表 600 + 主键 288 + 2 索引 484） | 1 372 KB | 4.02% |
| 5 | `campaign_stage_histories` | 1 212 KB | 3.55% |
| 6 | `equipment` | 916 KB | 2.68% |
| 7 | `academy_zone_visits` | 832 KB | 2.44% |
| 8 | `characters` | 620 KB | 1.82% |
| 9 | `character_potentials` | 576 KB | 1.69% |
| 10 | `furniture` | 356 KB | 1.04% |
| 11 | `echelon_slots` | 328 KB | 0.96% |
| 12 | `character_equipment_slots` | 212 KB | 0.62% |
| | 其余 75 张合计 | 2 308 KB | 6.76% |

任务段（`mission_progress` + `mission_history`）= 23 448 KB = **占全库 68.7%** —— 因为一个账号有 1 991 条任务进度，而且每条带两个 23 字符的 ISO 时间戳（`start_date` + `updated_at` ≈ 46 B/行）。`idx_mission_progress_cat` 原本还要再占 5 388 KB（13%），已在 §8.3 说明为何删掉。

### 7.3 满进度单账号估算

方法：`字节/行` 用 §7.2 的实测值（表 + 全部索引），乘以该表"满进度行数"（上限取 `ExcelDB` 对应表的行数，中值取本抓包实测 × 系数）。

| 类别 | 实测行 | 满进度行 | 满进度 KB |
|---|---|---|---|
| 角色（`characters` + potentials + slots + gears/weapons/costumes） | 214 | 1 860 | 123.8 |
| 道具/装备/家具 | 245 | 1 000 | 113.9 |
| 编队（3 表） | 97 | 156 | 9.7 |
| 剧情/战役（5 表） | 314 | 2 267 | 232.3 |
| 任务（3 表） | 2 380 | 5 020 | 410.8 |
| 咖啡厅（4 表） | 14 | 24 | 2.0 |
| 学院（4 表） | 148 | 252 | 15.5 |
| 收集品（4 表） | 36 | 169 | 11.4 |
| MomoTalk（2 表） | 2 | 520 | 51.2 |
| 战斗赛季（7 表） | 3 | 58 | 3.8 |
| 商店/氪金（10 表） | 8 | 335 | 33.7 |
| 活动/制造（11 表） | 33 | 569 | 36.0 |
| 邮件（2 表） | 4 | 75 | 13.8 |
| 公会（3 表） | 2 | 4 | 0.4 |
| 账号级（7 表） | 55 | 61 | 4.2 |
| **合计** | **3 555** | **12 370** | **1 062.5** |

**满进度账号 ≈ 1.04 MB。**

### 7.4 100 账号

| 场景 | 100 账号 |
|---|---|
| 全部中等进度（实测复刻） | **33.33 MB** |
| 全部满进度（估算） | **≈ 104 MB**（100 × 1.04 MB + 848 KB 骨架） |
| 混合（10 满 + 90 中） | ≈ 41 MB |
| 每个账号再算 30% 增长余量（WAL、碎片、历史） | 建议按 **140 MB** 规划磁盘 |

**100 个账号在 SQLite 上完全没问题**（单文件 140 MB，`WAL` 下多读一写够用）。若要做到 1 000 账号，任务段会到 1.4 GB —— 那时该考虑的不是换库，而是 §8.3 的两条压缩手段。

---

## 8. 索引与查询路径

### 8.1 主路径：靠主键，不额外建索引

所有账号表的主键都以 `server_id` 打头，主键索引本身就是一棵 `(server_id, …)` 有序 B 树。所以"取某账号的全部 X"已经被主键覆盖 —— **80 张表里只有 18 张额外建了索引（共 22 条）**。

### 8.2 额外索引的三类来源

| 类别 | 索引 | 服务什么查询 |
|---|---|---|
| 按静态表 id 反查 | `idx_characters_unique`、`idx_equipment_unique`、`idx_furniture_unique`、`uk_items_slot` | "我有没有这个学生/这件装备/这个道具" |
| 按时间窗 | `idx_mails_unread`、`idx_mails_expire`、`management_*_window`、`shop_recruits_window`、`idx_scenario_histories_time`、`idx_items_expires` | 未读邮件、过期清理、活动档期 |
| 按跨表引用反查 | `idx_ces_equipment`（装备被谁穿）、`idx_gears_bound`、`idx_echelon_slots_char`、`idx_clan_members_clan`、`idx_academy_zone_visits_char`、`idx_campaign_stage_chapter`、`idx_shop_products_shelf`、`idx_furniture_placed`、`uk_account_settings_friend_code`、`idx_global_config_updated_at` | 换装前置校验、按章节列关卡、按货架列商品 |

### 8.3 一条被实测否掉的设计

`idx_mission_progress_cat (server_id, mission_kind, category)` 原本打算加，实测在 100 账号库上占 **5 388 KB（13%）**，而它服务的查询（"取某类任务"）用主键前缀 `(server_id, mission_kind)` 就能扫到该账号全部 1 240 行 —— 索引纯属写放大。**已删**，DDL 里保留注释说明原因。

如果要继续压任务段体积（它占 68%），两条路（**本次不做**，只记录）：

1. `mission_progress.start_date` 从 ISO TEXT（23 B）改 INTEGER epoch 秒（4–5 B）：每账号省约 40 KB，代价是出包层要格式化；
2. 已完成且超过 N 天的任务进度归档到 `mission_progress_archive`，热表只留未完成。

两条都会改变"出包时直接读表"的简单性，和 v1 的 ISO-TEXT 约定冲突，所以留作后续优化。

---

## 9. 明确不需要落库的东西

### 9.1 判断依据（五条判据）

**落地（必须存）** 当且仅当满足任一条：

1. **玩家行为改变了它** —— 等级、经验、星级、技能等级、装备绑定、编队、剧情进度、任务进度、币、购买计数；
2. **它是时间点或游标** —— `LastUpdate`、`StartDate`、`NextAutoRefreshDate`、`ProductionAppliedTime`；
3. **它是"当时快照"，事后不可重建** —— `cafe_productions.comfort_value`、`clans.clan_president_nickname`；
4. **它是随机结果** —— `craft_nodes.node_random_seed` / `result_id`；
5. **官方回显与本地 ExcelDB 版本可能不一致** —— `shop_products.price` / `display_order` / `purchase_count_limit`（以线上为准，本地表只是兜底）。

**不落库** 当且仅当满足任一条：

1. **值只来自 ExcelDB 静态表，服务端从不写入** —— 见 §9.2；
2. **值是该行类型的常量回显** —— 见 §9.3；
3. **值可由已有列 join / 聚合得出，且允许每次响应现算** —— 见 §9.4。

> 注意判据 3 **不是**"能推导就不存"：`comfort_value` 能推导但必须存（判据 3 优先）；`AcademyLocationRankSum` 看似能推导（实测推不出来，§4.2）也必须存。所以判据要先判"是不是快照 / 是不是真能推"。

### 9.2 纯 ExcelDB 静态查询（响应时现查，一列都不存）

| 数据 | ExcelDB 表（行数） | 出现在哪个协议字段 |
|---|---|---|
| 角色基础属性、成长曲线 | `CharacterDBSchema`(7 223)、`CharacterStatDBSchema`、`CharacterLevelDBSchema`、`CharacterStatsDetailDBSchema`(10) | 客户端本地算，服务端只给 `Level`/`StarGrade` |
| 技能数值、EX 倍率 | `SkillDBSchema`、`SkillAdditionalTooltipDBSchema` | 同上 |
| 装备属性、强化曲线 | `EquipmentDBSchema`(191)、`EquipmentStatDBSchema`(191)、`EquipmentLevelDBSchema` | 只存 `level`/`tier` |
| 专武等级/星级曲线 | `CharacterWeaponDBSchema`、`CharacterWeaponLevelDBSchema` | 只存 `level`/`star_grade` |
| 家具舒适度、模板 | `FurnitureDBSchema`(876)、`FurnitureTemplateDBSchema` | `cafe_productions.comfort_value` 由服务端算完**存快照** |
| 卡池概率与内容 | `GachaElementDBSchema`、`GachaGroupDBSchema`、`PickupFirstGetBonusDBSchema` | 抽卡时现查 |
| 关卡消耗/掉落 | `CampaignStageDBSchema`(407)、`CampaignStageRewardDBSchema`、`WeekDungeonRewardDBSchema` | 只存 `star*_flag`/`today_play_count` |
| 任务条件与奖励 | `MissionDBSchema`(3 444)、`GuideMissionDBSchema`(923) | 只存 `progress_json`/`is_complete` |
| 商店价格与商品 | `ShopDBSchema`(7 908)、`ShopInfoDBSchema`、`ShopRecruitDBSchema`(532) | 见 §9.1 判据 5：`shop_products.price` **存了**，因为以线上回显为准 |
| 关卡/剧情脚本（36 万行） | `ScenarioScriptDBSchema`(362 158 行) | 客户端资源，服务端只回 `scenario_unique_id` |
| 本地化文本 | `LocalizeDBSchema`、`LocalizeEtcDBSchema` | `mails.sender`/`comment` 存的是 **key**（`UI_MAILBOX_POST_SENDER_ARONA`），文本由客户端查 |
| 账号等级经验表 | `AccountLevelDBSchema`(90)、`AccountLevelRewardDBSchema`(6) | 只存 `account_level_rewards.reward_id` |
| 学院设施定义 | `AcademyLocationDBSchema`(11)、`AcademyLocationRankDBSchema` | 只存 `rank`/`exp` |
| 竞技场赛季/分组 | `ArenaSeasonDBSchema`、`ArenaLevelSectionDBSchema`、`ArenaMapDBSchema` | 只存 `current_rank` 等 |
| 总力战 boss / 奖励 | `RaidStageDBSchema`、`RaidStageRewardDBSchema`、`EliminateRaidStageDBSchema` | 不存 |

判断依据：这些表在 `ExcelDB.db` 里是 **398 张只读表 / 160 MB**，改它们等于改游戏版本；玩家状态只引用它们的 `Id`，不复制内容。**在 DDL 里它们只以 `INTEGER unique_id` 的形式出现，且刻意不建跨库外键** —— SQLite 不支持跨库 FK，而且 ExcelDB 是只读参考数据（版本一变，外键就会"合法地"失效）。

### 9.3 常量回显（不存）

| 字段 | 实测值 | 为什么不存 |
|---|---|---|
| `CharacterDB.Type` | 46/46 = `1` | `ParcelType.Character`，出包时按表类型填死 |
| `EquipmentDB.Type` | 84/84 = `3` | `ParcelType.Equipment` |
| `ItemDB.Type` | 134/134 = `4` | `ParcelType.Item` |
| `FurnitureDB.Type` | 27/27 = `13` | `ParcelType.Furniture` |
| `MailDB.AccountServerId` | 2/2 = `0` | 遗留语义，归属用我们自己的 `server_id` |
| `EmblemDB.Type` | 14/14 = `20` | 存了（升级版本可能要按它区分来源），但它是常量 |
| `CafeVisitCharacterDB.ServerId` | 7/7 = `0` | 来访学生不是玩家实例 → 落 NULL |
| `ShopRecruits[*].UpdateDate` | 529/529 零值 | 无账号差异 → 目录进共享表 |
| `CafeDB.CurrencyDict_Obsolete` / `UpdateTimeDict_Obsolete` | wire 上不出现 | 官方已废弃 → `passthrough_json` |
| `MemoryLobbyDB.ParcelInfos` | `null` | 无语义 → `passthrough_json` |

### 9.4 可 join / 聚合得出（不存副本）

| 字段 | 从哪来 |
|---|---|
| `AccountClanMemberDB.AccountLevel` / `AccountNickName` | `accounts.level` / `accounts.nickname` |
| `AccountClanMemberDB.RepresentCharacterUniqueId` / `CostumeId` | `accounts.represent_character_server_id` → `characters.unique_id` |
| `ArenaUserDB`（对手的 `NickName`/`Level`/`TeamSettingDB`/`AttachmentDB`） | 由排名区间从**其他账号**的行 join 出来，一列都不复制 |
| `DetailedAccountInfoDB.CharacterCount` / `FriendCount` / `ClanName` | `COUNT(*) FROM characters` / `account_settings.friend_count` / `clans.clan_name` |
| `FriendDB.ComfortValue` | `cafe_productions.comfort_value` |
| `StickerBookDB.AccountId` / `AccountAttachmentDB.AccountId` / `AcademyDB.AccountId` / `CafeDB.AccountId` | 就是 `server_id` 本身 |
| `CharacterDB.EquipmentServerIds` 的反向 `EquipmentDB.BoundCharacterServerId` | `character_equipment_slots` 反查（wire 上只在被穿着的 30 条里出现） |

---

## 10. 未建模 / 未找到

诚实清单。这些**故意没有**建表，或者建了但**语义未经真实数据验证**：

| 项 | 状态 | 说明 |
|---|---|---|
| `TSSCharacterDBs` | **未建模** | 抓包 0 行，`dto_schema_full_v2.json` 里也没有 `TSSCharacterDB` 定义 → **未找到**字段表。抓到非空样本再建 |
| `ScenarioCollectionDBs` / `CraftInfos` / `CraftNodes` / `EventContentCollectionDB` / `Billing OrderList` 等 | **建了表，0 行验证** | 结构取自 `dto_schema_full_v2.json`，没有真实数据跑过，字段名/类型可能有偏差 |
| `AcademyDB.ZoneScheduleGroupRecords` | **建了表，语义未验证** | DTO 是 `Dictionary<long, List<long>>`，抓包 `{}`。按"zone_id → 已完成 schedule"建模；若实际是 "schedule_group_id → …"，改列名即可，主键结构不变 |
| `CampaignStrategyObjectHistories` | **未建模** | 模板 `campaign.strategyObjectHistories` 有，但 1017/6000 都没抓到 → 无字段依据 |
| `ShopProducts` 的 `SoldOut` | 已建列 | wire 有、DTO 没有 → 以 wire 为准 |
| `EventContentPermanentDB.IsReceivedCharacterReward` | 已建列 | DTO 有、wire 省略（0 值） |
| `PlayerGroupId` / 赛季分组算法 | 只存值 | `player_group_id=322` 怎么分配没有依据，暂按存值处理 |
| `EncryptedUID` / `TTSCdnUri` 等 auth 字段 | 进 `global_config` | 不建列，键值对存 |
| `protocol_log` / `sessions` | **v1 保留** | 本设计不碰 |
| `account_blobs` | **v1 保留但不写** | 迁移完成后可留作回滚依据；不建议双写（会出现两份真相） |

---

## 11. 不变量、巡检与风险

### 11.1 灌库时暴露并已修的 5 个设计缺陷

| # | 报错 | 根因 | 修法 |
|---|---|---|---|
| 1 | `CHECK constraint failed: cafe_db_id = server_id*10+cafe_id` | 复刻账号时直接复制了别的账号的 `CafeDBId` | 保留 CHECK（是正确的领域不变量），写进迁移约束 M1：复制必须重算 |
| 2 | `UNIQUE constraint failed: management_gacha_displays.display_id` | `GachaProbabilityDisplayId` 12 行**全是 2**，不是唯一键 | 主键改为 `(display_id, linked_lobby_banner_id)` |
| 3 | `IntegrityError: FOREIGN KEY constraint failed`（在 `character_equipment_slots`） | 灌库顺序错了：先插了槽、后插装备 | 写进迁移约束 M2：`characters → equipment → slots` |
| 4 | `table arena_players has 12 columns but 11 values` | 列数统计漏了一个 | 已按 PRAGMA 实际列数对齐 |
| 5 | `NOT NULL constraint failed: furniture.server_id`（删号时） | `ON DELETE SET NULL` 加在**含 NOT NULL `server_id`** 的复合外键上，SET NULL 会连 `server_id` 一起置空 | 5 处改为应用层不变量 + 巡检 SQL（`furniture.cafe_db_id`、`gears/weapons/costumes/momotalk_outlines.*_character_entity_id`）；2 处改为 `ON DELETE CASCADE`（`cafe_visits`、`academy_zone_visits`，它们是可丢弃的链接行） |

第 5 条尤其值得记：SQLite 的复合外键 + `SET NULL` 是个陷阱，**只要外键包含一个 `NOT NULL` 列，`SET NULL` 必然在删除时炸**。

### 11.2 应用层不变量（无法用 DDL 表达，用巡检 SQL 守）

```sql
-- ① 家具只能摆在"本账号"的咖啡厅里（外键因 SET NULL 限制被移除，见 §11.1-5）
SELECT 'furniture' AS t, f.server_id, f.entity_id, f.cafe_db_id
FROM furniture f
WHERE f.cafe_db_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cafes c
                  WHERE c.server_id = f.server_id AND c.cafe_db_id = f.cafe_db_id);

-- ② 装备/专武/皮肤/会话指向的角色必须属于同一账号
SELECT 'gears' t, g.server_id, g.entity_id, g.bound_character_entity_id AS ref FROM gears g
 WHERE g.bound_character_entity_id IS NOT NULL
   AND NOT EXISTS (SELECT 1 FROM characters c
                   WHERE c.server_id = g.server_id AND c.entity_id = g.bound_character_entity_id)
UNION ALL
SELECT 'weapons', w.server_id, w.unique_id, w.bound_character_entity_id FROM weapons w
 WHERE w.bound_character_entity_id IS NOT NULL
   AND NOT EXISTS (SELECT 1 FROM characters c
                   WHERE c.server_id = w.server_id AND c.entity_id = w.bound_character_entity_id)
UNION ALL
SELECT 'costumes', s.server_id, s.unique_id, s.bound_character_entity_id FROM costumes s
 WHERE s.bound_character_entity_id IS NOT NULL
   AND NOT EXISTS (SELECT 1 FROM characters c
                   WHERE c.server_id = s.server_id AND c.entity_id = s.bound_character_entity_id)
UNION ALL
SELECT 'momotalk_outlines', m.server_id, m.character_unique_id, m.character_entity_id
  FROM momotalk_outlines m
 WHERE m.character_entity_id IS NOT NULL
   AND NOT EXISTS (SELECT 1 FROM characters c
                   WHERE c.server_id = m.server_id AND c.entity_id = m.character_entity_id);

-- ③ 零值归一化巡检：不该出现 0001-01-01 时间戳
SELECT 'campaign_stage_histories' t, COUNT(*) n FROM campaign_stage_histories
 WHERE substr(last_play,1,10) = '0001-01-01'
UNION ALL SELECT 'arena_players', COUNT(*) FROM arena_players
 WHERE substr(daily_reward_active_time,1,10) = '0001-01-01';

-- ④ 已领奖但没记录 / 记录与状态矛盾（每条对应一个业务不变量）
SELECT 'mail_parcels' t, COUNT(*) n FROM mails m
 WHERE m.receipt_date IS NOT NULL
   AND EXISTS (SELECT 1 FROM mail_parcels p WHERE p.server_id=m.server_id AND p.mail_uid=m.mail_uid);

-- ⑤ 空槽占位不该存在（归一化漏了就会被抓出来）
SELECT 'character_equipment_slots_zero' t, COUNT(*) n FROM character_equipment_slots WHERE equipment_entity_id = 0
UNION ALL SELECT 'echelon_slots_zero', COUNT(*) FROM echelon_slots WHERE character_entity_id = 0
UNION ALL SELECT 'cafe_visits_zero', COUNT(*) FROM cafe_visits WHERE character_entity_id = 0;
```

### 11.3 隔离性测试（已跑过，全绿）

| # | 测试 | 期望 | 实测结果 |
|---|---|---|---|
| 1 | B 账号插入 `echelon_slots` 引用 A 的角色 | 拒绝 | ✓ `FOREIGN KEY constraint failed` |
| 2 | B 账号插入 `character_equipment_slots` 引用 A 的装备 | 拒绝 | ✓ `FOREIGN KEY constraint failed` |
| 3 | B 用与 A **相同**的 `entity_id` 建自己的角色 | 允许 | ✓ 通过（`entity_id` 只在账号内唯一） |
| 4 | 同一账号重复 `entity_id` | 拒绝 | ✓ `UNIQUE constraint failed: characters.server_id, characters.entity_id` |
| 5 | `cafes` 写入错误的派生 `cafe_db_id` | 拒绝 | ✓ `CHECK constraint failed` |
| 6 | `DELETE FROM accounts WHERE server_id=10000000000` | 该账号 0 残留；共享表与 B 账号完好 | ✓ 残留 `0` 行；`shop_recruits=529`、`management_notices=20` 仍在；B 的 `characters=1` 仍在 |

第 3 条与第 6 条一起说明：**"每个卡密一份独立数据"是结构保证，不是代码约定**。

### 11.4 剩余风险

| 风险 | 影响 | 缓解 |
|---|---|---|
| 任务段占 68% 体积 | 满进度账号 1 MB，1 000 账号会到 GB 级 | §8.3 的两条压缩手段（本次不做） |
| `cafe_db_id` 派生 + CHECK | 复制/迁移账号必须重算（M1） | 已在迁移约束里钉死 + 巡检 SQL |
| 5 处应用层不变量无 DDL 约束 | 写错不会立刻报错 | §11.2 巡检 SQL，建议挂到每日定时任务 |
| 空表结构只有 DTO 依据 | 真实数据可能对不上（`craft_*`、`gears`、`weapons`、`costumes`、`event_content_collections`…） | 抓到非空样本后跑一次灌库回归（就是本设计 §1.3 的方法） |
| `tssCharacters` 完全无依据 | 若客户端真的依赖，会缺字段 | 抓包 0 行 + DTO 无定义 → 暂按不返回处理 |
| ExcelDB 版本漂移 | 静态表行数变化会让"满进度上限"变化 | 容量按 §7.4 的 140 MB 规划，留 30% 余量 |
| v1 `account_blobs` 与 v2 双写 | 两份真相会分叉 | **不要双写**：迁移完成后 `account_blobs` 只读保留 |

---

## 12. 自检清单

| 检查 | 结果 |
|---|---|
| v2 表数 / 列数 / 索引数 | 80 / 496 / 22（`sqlite_master` + `PRAGMA table_info` 实测） |
| v1 是否被改动 | 未改动（`schema_v2.sql` 无 `ALTER`/`DROP`，不写 v1 的 `schema_meta`） |
| DDL 能否在空库一次跑通 | 能（`executescript` 无错误） |
| 每条外键是否实际被触发过 | 是（灌 100 账号 + 6 条破坏性测试，全程 `PRAGMA foreign_keys=ON`） |
| `PRAGMA foreign_key_check` | 0 行 |
| 删号是否 0 残留 | 是（72 张账号表全空，共享表不动） |
| 跨账号引用是否被拒 | 是 |
| 单账号行数 / 大小 | 3 555 行 / 333 KB（净增） |
| 100 账号行数 / 大小 | 356 080 行 / 33.33 MB |
| 满进度单账号 | ≈ 12 370 行 / 1.04 MB |
| 空库骨架 | 848 KB |
| 未找到 / 未验证项 | 已列在 §10，共 5 类 |
