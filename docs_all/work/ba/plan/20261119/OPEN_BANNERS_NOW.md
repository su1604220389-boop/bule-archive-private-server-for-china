# OPEN_BANNERS_NOW — 国服客户端表「此刻处于开放期」的招募卡池

- **时刻基准**：`2026-11-19 01:40:00`（北京时间 UTC+8，表内 `SalePeriodFrom/To` 是无时区字符串，按字面比较）
- **数据源**：`C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\data\ExcelDB.db`（只读打开，`mode=ro`）
- **脚本**：`work\ba\scripts\q_open_banners_now.py`（本文件由脚本自动生成，可复跑）

## 结论

此刻 **10 个** `ShopRecruit` 行落在档期内；**5 个有卡面图**（`GachaBannerPath` 非空）、**10 个有本地化**（`LocalizeGachaShop` 有对应行）。

| Id | CategoryType | DisplayOrder | 卡面图 | 本地化 | 本地化段数 | 一句话 |
|---|---|---|---|---|---|---|
| `7000001` | 23(DirectPayGacha_DontUseGlobal) | 1 | ✅ | ✅ | 4 | 新手冲刺招募Ⅱ｜来招募更多个性迥异的成员吧！ |
| `8000004` | 23(DirectPayGacha_DontUseGlobal) | 2 | ✅ | ✅ | 5 | 3★自选招募｜购买3★成员自选券后，可以选择成员进行招募。 |
| `99999999` | 22(TicketGacha) | 4 | ✅ | ✅ | 5 | 3★必得招募！｜来招募更多个性迥异的成员吧！ |
| `5004670` | 5(PickupGacha) | 10 | ❌ | ✅ | 5 | 限时招募！｜美咲（泳装）（3★）招募概率提升！ |
| `5004680` | 19(LimitedGacha) | 20 | ❌ | ✅ | 5 | 限定限时招募 1｜【限定】纱织（泳装）（3★）招募概率提升！ / 还可招募【限定】日和（泳装）（3★）！ |
| `5004690` | 19(LimitedGacha) | 30 | ❌ | ✅ | 5 | 限定限时招募 2｜【限定】日和（泳装）（3★）招募概率提升！ / 还可招募【限定】纱织（泳装）（3★）！ |
| `5004700` | 5(PickupGacha) | 40 | ❌ | ✅ | 5 | 限时招募！｜白子（泳装）（3★）招募概率提升！ |
| `5004710` | 5(PickupGacha) | 50 | ❌ | ✅ | 5 | 限时招募！｜野宫（泳装）（3★）招募概率提升！ |
| `5004660` | 6(NormalGacha) | 60 | ✅ | ✅ | 5 | 长期招募｜来招募更多个性迥异的成员吧！ |
| `90000000` | 35(SelectPickupGacha) | 100 | ✅ | ✅ | 5 | 档案招募！｜招募概率提升！ |

## 1. 判据：客户端自己怎么筛「开放期」

`work\ba\srv_src\Schale\Excel\ShopRecruitExcelExt.cs:19-25`：

```csharp
public static List<ShopRecruitExcelT> GetTimelinedShopRecruit(
    this List<ShopRecruitExcelT> recruits, DateTime dateTime)
{
    var filtered = recruits.Where(r => 
        DateTime.Parse(r.SalePeriodFrom) <= dateTime && 
        DateTime.Parse(r.SalePeriodTo) >= dateTime);
    return filtered.ToList();
}
```

即：**闭区间** `SalePeriodFrom <= now <= SalePeriodTo`，没有额外闸门。

补充（同表文件实测）：

- `IsLegacy`：全表 532 行 **全为 false**（字段号 f2 在所有 vtable 里都不存在 = 默认值），闸门放行。
- `SalePeriodVisible`：全表 532 行全为 true。
- `SalePeriodFrom/To` 都为空的行共 3 个（`Id=1, 2, 3`），不在 `GetTimelinedShopRecruit` 里，由 `GetNonSaleShopRecruit` 单独取，属**常驻无档期**，本报告不计入「开放期」。
- 档期字符串无法解析的行数：0。

## 2. 布局勘误（任务给的偏移不能用，已实测替换）

任务给的 `Id`@0x10、`SalePeriodFrom`@0x30(16B DateTime?) 那套在这批 blob 上**不成立**：

- `Bytes` 是 **FlatBuffers table**：`0x00` root uoffset → table，table 头部 i32 soffset 回指 vtable，vtable 里 `u16 × N` 是字段相对 table 的偏移，**为 0 表示该字段取默认值并整条省略**。
- 因此**同一张表里字段的绝对偏移逐行不同**（`Id=1` 的 table 长 96B，`Id=5004670` 长 104B），任何固定偏移都会读错。
- `SalePeriodFrom/To` 不是 16 字节 `DateTime?`，是 **string**：`2026-11-12 14:00:00` / `2026-11-26 13:59:59`（无 ticks 编码）。

权威字段号取自仓库内的 FlatBuffers 生成类 `srv_src\Schale\FlatData\ShopRecruitExcel.cs`（字段号 = `(__offset(N) - 4) / 2`）：

| 字段号 | 名字 | 类型 |
|---|---|---|
| f0 | `Id` | long |
| f1 | `CategoryType` | enum ShopCategoryType |
| f2 | `IsLegacy` | bool |
| f3 | `OneGachaGoodsId` | long |
| f4 | `TenGachaGoodsId` | long |
| f5 | `GoodsDevName` | string |
| f6 | `DisplayTag` | enum GachaDisplayTag |
| f7 | `DisplayOrder` | long |
| f8 | `GachaBannerPath` | string |
| f9 | `VideoId` | vector<long> |
| f10 | `LinkedRobbyBannerId` | long |
| f11 | `InfoCharacterId` | vector<long> |
| f12 | `SalePeriodVisible` | bool |
| f13 | `SalePeriodFrom` | string |
| f14 | `SalePeriodTo` | string |
| f15 | `RecruitCoinId` | long |
| f16 | `RecruitSellectionShopId` | long |
| f20 | `IsNewbie` | bool |
| f21 | `IsSelectRecruit` | bool |
| f22 | `DirectPayInvisibleTokenId` | long |
| f25 | `SelectAbleGachaGroupId` | long |
| f26 | `MaxSelectCharacterNum` | long |

## 3. 自校验（脚本每次运行都跑）

| 检查项 | 实测 | 结论 |
|---|---|---|
| ShopRecruit f0 == Id 列 | 532/532 | ✅ PASS |
| LocalizeGachaShop f0 == GachaShopId 列 | 1235/1235 | ✅ PASS |
| ShopRecruit[5004670] 档期解出 2026-11-12 14:00 ~ 2026-11-26 13:59 | 2026-11-12 14:00:00 ~ 2026-11-26 13:59:59 | ✅ PASS |
| LocalizeGachaShop[5004670] 含『限时招募』 | 是 | ✅ PASS |
| LocalizeGachaShop[5004670] 含『2026/11/12 14:00~2026/11/26  13:59截止』 | 是 | ✅ PASS |
| LocalizeGachaShop[5004670] 含『美咲（泳装）（3★）招募概率提升』 | 是 | ✅ PASS |

## 4. 表 1 —— 本刻处于开放期的卡池完整表

| Id | OneGachaGoodsId | TenGachaGoodsId | CategoryType | IsLegacy | IsNewbie | from | to | 覆盖本刻 |
|---|---|---|---|---|---|---|---|---|
| `7000001` | 0 | 100101 | 23(DirectPayGacha_DontUseGlobal) | False | True | 2025-08-14 14:00:00 | 2099-12-31 03:59:59 | ✅ |
| `8000004` | 0 | 0 | 23(DirectPayGacha_DontUseGlobal) | False | False | 2026-09-24 14:00:00 | 2027-06-10 13:59:59 | ✅ |
| `99999999` | 0 | 99999999 | 22(TicketGacha) | False | False | 2024-08-01 14:00:00 | 2099-12-31 03:59:59 | ✅ |
| `5004670` | 5004671 | 5004672 | 5(PickupGacha) | False | False | 2026-11-12 14:00:00 | 2026-11-26 13:59:59 | ✅ |
| `5004680` | 5004681 | 5004682 | 19(LimitedGacha) | False | False | 2026-11-12 14:00:00 | 2026-11-26 13:59:59 | ✅ |
| `5004690` | 5004691 | 5004692 | 19(LimitedGacha) | False | False | 2026-11-12 14:00:00 | 2026-11-26 13:59:59 | ✅ |
| `5004700` | 5004701 | 5004702 | 5(PickupGacha) | False | False | 2026-11-12 14:00:00 | 2026-11-26 13:59:59 | ✅ |
| `5004710` | 5004711 | 5004712 | 5(PickupGacha) | False | False | 2026-11-12 14:00:00 | 2026-11-26 13:59:59 | ✅ |
| `5004660` | 5004661 | 5004662 | 6(NormalGacha) | False | False | 2026-11-12 14:00:00 | 2026-11-26 13:59:59 | ✅ |
| `90000000` | 900000 | 900001 | 35(SelectPickupGacha) | False | False | 2026-07-16 10:00:00 | 2099-12-31 03:59:59 | ✅ |

按 DisplayOrder 排序；`CategoryType` 名称取自 `FlatData\ShopCategoryType.cs`。

附带其它已解出的相关列：

| Id | DisplayTag | DisplayOrder | SalePeriodVisible | InfoCharacterId | VideoId | RecruitCoinId | DirectPayInvisibleTokenId |
|---|---|---|---|---|---|---|---|
| `7000001` | New | 1 | True | - | [5102] | 0 | 11000001 |
| `8000004` | SelectRecruit | 2 | True | - | [5202] | 0 | 12000003 |
| `99999999` | ThreeStar | 4 | True | - | [5300] | 0 | 0 |
| `5004670` | Limited | 10 | True | [20049] | [6180] | 1901120 | 0 |
| `5004680` | Limited | 20 | True | [10101] | [6142] | 1901120 | 0 |
| `5004690` | None | 30 | True | - | [6143] | 1901120 | 0 |
| `5004700` | None | 40 | True | [20027] | [6102] | 1901120 | 0 |
| `5004710` | None | 50 | True | - | [6060] | 1901120 | 0 |
| `5004660` | None | 60 | True | - | [5002] | 1901120 | 0 |
| `90000000` | None | 100 | True | - | [9000] | 79000 | 0 |

### 4.1 档期边界

- 最近一次关池：`2026-11-26 13:59:59`，距今 **7 天 12 小时 19 分**。
- 本刻开放的 10 行分布在 5 个档期区间：`2024-08-01 14:00:00 ~ 2099-12-31 03:59:59`（1 行）；`2025-08-14 14:00:00 ~ 2099-12-31 03:59:59`（1 行）；`2026-07-16 10:00:00 ~ 2099-12-31 03:59:59`（1 行）；`2026-09-24 14:00:00 ~ 2027-06-10 13:59:59`（1 行）；`2026-11-12 14:00:00 ~ 2026-11-26 13:59:59`（6 行）。
- 尚未开始的行：0 个（下一个起点 `-`）；最近 14 天内刚关池的行：3 个。

## 5. 表 2 —— 卡面图 / 本地化

### 5.1 卡面图（`ShopRecruit.GachaBannerPath`，f8）

> **先纠正前提**：这本 `ExcelDB.db` 里**没有** `GachaBannerDBSchema` 之类独立 banner 表（含 `Banner` 字样的表只有 `EventContentArchiveBannerOffsetDBSchema`，且与卡池无关）。卡面图路径就是 `ShopRecruit` 自己的 f8 `GachaBannerPath`，全表 151/532 行非空。

`ShopRecruit` 与 banner 相关的候选表（这本库里一共有 398 张表）：`GachaCombinedCostDBSchema`、`GachaCraftNodeDBSchema`、`GachaCraftNodeGroupDBSchema`、`GachaCraftOpenTagDBSchema`、`GachaElementDBSchema`、`GachaElementRecursiveDBSchema`、`GachaGroupDBSchema`、`GachaSelectPickupGroupDBSchema`、`LocalizeGachaShopDBSchema`、`ShopDBSchema`、`ShopFreeRecruitDBSchema`、`ShopFreeRecruitPeriodDBSchema`、`ShopRecruitDBSchema`、`ShopTabGroupDBSchema`。

| Id | 三种 key 是否有 ShopRecruit 条目 | GachaBannerPath | 有卡面图 |
|---|---|---|---|
| `7000001` | 7000001(Id):有、100101(Ten):无 | `uis/00_images/banner/Event_Banner_70001` | ✅ |
| `8000004` | 8000004(Id):有 | `uis/00_images/banner/Event_Banner_80000` | ✅ |
| `99999999` | 99999999(Id/Ten):有 | `uis/00_images/banner/Event_Banner_60000` | ✅ |
| `5004670` | 5004670(Id):有、5004671(One):无、5004672(Ten):无 | `(空)` | ❌ |
| `5004680` | 5004680(Id):有、5004681(One):无、5004682(Ten):无 | `(空)` | ❌ |
| `5004690` | 5004690(Id):有、5004691(One):无、5004692(Ten):无 | `(空)` | ❌ |
| `5004700` | 5004700(Id):有、5004701(One):无、5004702(Ten):无 | `(空)` | ❌ |
| `5004710` | 5004710(Id):有、5004711(One):无、5004712(Ten):无 | `(空)` | ❌ |
| `5004660` | 5004660(Id):有、5004661(One):无、5004662(Ten):无 | `uis/00_images/banner/Event_Banner_50001` | ✅ |
| `90000000` | 90000000(Id):有、900000(One):无、900001(Ten):无 | `uis/00_images/banner/Event_Banner_50002` | ✅ |

（`OneGachaGoodsId`/`TenGachaGoodsId` 为 `0` 的行表示该字段未设置 —— 本次开放的 `7000001`/`8000004`/`99999999` 就是这种，它们不靠 goods id 单抽/十连，靠直购或票券。）

任务点名的三个 key `5004670 / 5004671 / 5004672`：

| key | 在 ShopRecruit 里 | 在 LocalizeGachaShop 里 | 说明 |
|---|---|---|---|
| `5004670` | ✅ | ✅ | ShopRecruit.Id 本身，`GachaBannerPath`='' |
| `5004671` | ❌ | ❌ | = 该行 `OneGachaGoodsId`（单抽 goods） |
| `5004672` | ❌ | ❌ | = 该行 `TenGachaGoodsId`（十连 goods） |

⇒ 卡面图只挂在 **`ShopRecruit.Id`** 这一把 key 上；`OneGachaGoodsId`/`TenGachaGoodsId` 是 `GoodsDB` 的 goods id（查 `GoodsDBSchema` 能对上），在 ShopRecruit / LocalizeGachaShop 里基本查不到行 —— 唯一例外是 `90000000` 的 `One=900000`，它恰好撞上另一张卡池的本地化行（8 段，内容不是这一张），属于**假命中**，不能当 key 用。

### 5.2 本地化（`LocalizeGachaShop`，key = `GachaShopId`）

| Id | 三种 key 命中 | 本地化段数 |
|---|---|---|
| `7000001` | 7000001(Id):有、100101(Ten):无 | 4 |
| `8000004` | 8000004(Id):有 | 5 |
| `99999999` | 99999999(Id/Ten):有 | 5 |
| `5004670` | 5004670(Id):有、5004671(One):无、5004672(Ten):无 | 5 |
| `5004680` | 5004680(Id):有、5004681(One):无、5004682(Ten):无 | 5 |
| `5004690` | 5004690(Id):有、5004691(One):无、5004692(Ten):无 | 5 |
| `5004700` | 5004700(Id):有、5004701(One):无、5004702(Ten):无 | 5 |
| `5004710` | 5004710(Id):有、5004711(One):无、5004712(Ten):无 | 5 |
| `5004660` | 5004660(Id):有、5004661(One):无、5004662(Ten):无 | 5 |
| `90000000` | 90000000(Id):有、900000(One):有、900001(Ten):无 | 5 |

段数分布（全表 1235 行）：4 段 × 5 行、5 段 × 529 行、8 段 × 701 行。

### 5.3 全部串段（逐条贴出）

槽号即字段号；国服这版是 CN/KR 交错，**奇数槽 f1/f3/f5/f7/f9 = 中文**、偶数槽 f2/f4/f6/f8 = 韩文。

#### `7000001` — 4 段

| 槽 | 推断字段 | 文本 |
|---|---|---|
| f1 | `TabNameCn` | 新手冲刺Ⅱ |
| f3 | `TitleNameCn` | 新手冲刺招募Ⅱ |
| f5 | `SubTitleCn` | 来招募更多个性迥异的成员吧！ |
| f7 | `GachaDescriptionCn` | 选择招募10次，必定获得1名3★成员！<br>※若出现已拥有的成员则会转换为神名精髓与该成员的神名文字。<br>※请注意，新手冲刺招募是有时间限制的招募。 |

#### `8000004` — 5 段

| 槽 | 推断字段 | 文本 |
|---|---|---|
| f1 | `TabNameCn` | 3★自选 |
| f3 | `TitleNameCn` | 3★自选招募 |
| f5 | `SubTitleCn` | 购买3★成员自选券后，可以选择成员进行招募。 |
| f7 | `GachaDescriptionCn` | 购买后将获得1张10次招募券和1张3★成员自选券。<br>该商品每个帐号只能购买1次。<br>※选择已拥有的成员后，可以获得神名精髓与该成员的神名文字。<br>可选择的成员名单可以在选择成员的菜单上确认。<br>购买的自选券的有效期是可购买时间结束一周后的下午14:00点前。 |
| f9 | `PeriodTextCn / 其它Cn槽` | 2026/09/24 14:00~2027/06/10  13:59截止 |

#### `99999999` — 5 段

| 槽 | 推断字段 | 文本 |
|---|---|---|
| f1 | `TabNameCn` | 3★必得 |
| f3 | `TitleNameCn` | 3★必得招募！ |
| f5 | `SubTitleCn` | 来招募更多个性迥异的成员吧！ |
| f7 | `GachaDescriptionCn` | 选择招募10次，必定获得1名3★成员！<br>※若出现已拥有的成员则会转换为神名精髓与该成员的神名文字。 |
| f9 | `PeriodTextCn / 其它Cn槽` | 2026/11/12 14:00~2026/11/26  13:59截止 |

#### `5004670` — 5 段

| 槽 | 推断字段 | 文本 |
|---|---|---|
| f1 | `TabNameCn` | 限时招募 |
| f3 | `TitleNameCn` | 限时招募！ |
| f5 | `SubTitleCn` | 美咲（泳装）（3★）招募概率提升！ |
| f7 | `GachaDescriptionCn` | 选择招募10次，必定获得1名2★以上成员！<br>※若出现已拥有的成员则会转换为神名精髓与该成员的神名文字。 |
| f9 | `PeriodTextCn / 其它Cn槽` | 2026/11/12 14:00~2026/11/26  13:59截止 |

#### `5004680` — 5 段

| 槽 | 推断字段 | 文本 |
|---|---|---|
| f1 | `TabNameCn` | 限定限时1 |
| f3 | `TitleNameCn` | 限定限时招募 1 |
| f5 | `SubTitleCn` | 【限定】纱织（泳装）（3★）招募概率提升！<br>还可招募【限定】日和（泳装）（3★）！ |
| f7 | `GachaDescriptionCn` | 选择招募10次，必定获得1名2★以上成员！<br>※若出现已拥有的成员则会转换为神名精髓与该成员的神名文字。 |
| f9 | `PeriodTextCn / 其它Cn槽` | 2026/11/12 14:00~2026/11/26  13:59截止 |

#### `5004690` — 5 段

| 槽 | 推断字段 | 文本 |
|---|---|---|
| f1 | `TabNameCn` | 限定限时2 |
| f3 | `TitleNameCn` | 限定限时招募 2 |
| f5 | `SubTitleCn` | 【限定】日和（泳装）（3★）招募概率提升！<br>还可招募【限定】纱织（泳装）（3★）！ |
| f7 | `GachaDescriptionCn` | 选择招募10次，必定获得1名2★以上成员！<br>※若出现已拥有的成员则会转换为神名精髓与该成员的神名文字。 |
| f9 | `PeriodTextCn / 其它Cn槽` | 2026/11/12 14:00~2026/11/26  13:59截止 |

#### `5004700` — 5 段

| 槽 | 推断字段 | 文本 |
|---|---|---|
| f1 | `TabNameCn` | 限时招募 |
| f3 | `TitleNameCn` | 限时招募！ |
| f5 | `SubTitleCn` | 白子（泳装）（3★）招募概率提升！ |
| f7 | `GachaDescriptionCn` | 选择招募10次，必定获得1名2★以上成员！<br>※若出现已拥有的成员则会转换为神名精髓与该成员的神名文字。 |
| f9 | `PeriodTextCn / 其它Cn槽` | 2026/11/12 14:00~2026/11/26  13:59截止 |

#### `5004710` — 5 段

| 槽 | 推断字段 | 文本 |
|---|---|---|
| f1 | `TabNameCn` | 限时招募 |
| f3 | `TitleNameCn` | 限时招募！ |
| f5 | `SubTitleCn` | 野宫（泳装）（3★）招募概率提升！ |
| f7 | `GachaDescriptionCn` | 选择招募10次，必定获得1名2★以上成员！<br>※若出现已拥有的成员则会转换为神名精髓与该成员的神名文字。 |
| f9 | `PeriodTextCn / 其它Cn槽` | 2026/11/12 14:00~2026/11/26  13:59截止 |

#### `5004660` — 5 段

| 槽 | 推断字段 | 文本 |
|---|---|---|
| f1 | `TabNameCn` | 长期招募 |
| f3 | `TitleNameCn` | 长期招募 |
| f5 | `SubTitleCn` | 来招募更多个性迥异的成员吧！ |
| f7 | `GachaDescriptionCn` | 选择招募10次，必定获得1名2★以上成员！<br>※若出现已拥有的成员则会转换为神名精髓与该成员的神名文字。 |
| f9 | `PeriodTextCn / 其它Cn槽` | 2026/11/12 14:00~2026/11/26  13:59截止 |

#### `90000000` — 5 段

| 槽 | 推断字段 | 文本 |
|---|---|---|
| f1 | `TabNameCn` | 档案招募！ |
| f3 | `TitleNameCn` | 档案招募！ |
| f5 | `SubTitleCn` | 招募概率提升！ |
| f7 | `GachaDescriptionCn` | 选择招募10次，必定获得1名2★以上成员！<br>※若出现已拥有的成员则会转换为神名精髓与该成员的神名文字。 |
| f9 | `PeriodTextCn / 其它Cn槽` | 2026/07/16 10:00~本期结束时间将另行通知 |

## 6. `LocalizeGachaShop`（1235）与 `ShopRecruit`（532）互相差集

| 集合 | 数量 | 最小 | 最大 |
|---|---|---|---|
| 交集 | 532 | — | — |
| **ShopRecruit 有 / Localize 无** | **0** | - | - |
| **Localize 有 / ShopRecruit 无** | **703** | 50000 | 70000000 |

⇒ **`ShopRecruit.Id` 是 `LocalizeGachaShop.GachaShopId` 的子集，一个都不缺**（rec-only = 0）；反过来 Localize 多出 703 行。

### 6.1 前缀 / 量级分布

| 量级桶 | Localize 全部 1235 | ShopRecruit 全部 532 | Loc-only 703 |
|---|---|---|---|
| <1e3 | 3 | 3 | 0 |
| 1e4-1e5 | 695 | 0 | 695 |
| 1e5-1e6 | 7 | 0 | 7 |
| 1e6-1e7 | 523 | 523 | 0 |
| 1e7-1e8 | 7 | 6 | 1 |

前 3 位前缀（只列 loc-only 里出现的）：

| 前缀 | Loc-only 行数 | Localize 全量 | ShopRecruit 全量 |
|---|---|---|---|
| `506` | 78 | 78 | 0 |
| `508` | 72 | 72 | 0 |
| `503` | 71 | 71 | 0 |
| `501` | 68 | 68 | 0 |
| `504` | 67 | 67 | 0 |
| `505` | 66 | 66 | 0 |
| `502` | 62 | 62 | 0 |
| `507` | 62 | 62 | 0 |
| `500` | 55 | 527 | 472 |
| `509` | 38 | 38 | 0 |
| `600` | 8 | 40 | 32 |
| `800` | 5 | 10 | 5 |
| `900` | 5 | 18 | 13 |
| `100` | 4 | 8 | 4 |
| `611` | 4 | 4 | 0 |
| `621` | 4 | 4 | 0 |
| `631` | 4 | 4 | 0 |
| `641` | 4 | 4 | 0 |
| `699` | 4 | 4 | 0 |
| `700` | 4 | 6 | 2 |
| `901` | 4 | 4 | 0 |
| `902` | 4 | 4 | 0 |
| `610` | 3 | 3 | 0 |
| `620` | 3 | 3 | 0 |
| `630` | 3 | 3 | 0 |
| `801` | 1 | 1 | 0 |

按 10 万位切段（loc-only）：100000: 4、700000: 1、800000: 1、900000: 1、70000000: 1。

**规律**：

1. `ShopRecruit`（532 行）的 id 只占 3 个量级段，全部被 Localize 覆盖 → 招募表是**后加的子集**，本地化表承载着更早的批次。
2. loc-only 的 703 行里 **695 行是 5 位 id（50000–99999）**，是韩服/早期「限时招募」文本批次的残留；`5004670` 这种 7 位 `5004xxx` 才是国服这一轮在用的号段。
3. 另有一批 loc-only 的"整万"占位 id：`50000`、`60000`、`70000`、`80000`、`90000`、`100000`、`700000`、`800000`、`900000`、`70000000` —— 看不出与任何 ShopRecruit 对应。

## 7. 附注

1. **5 个真·卡池一个卡面图都没有**：`5004670 / 5004680 / 5004690 / 5004700 / 5004710`（PickupGacha / LimitedGacha）的 `GachaBannerPath` 全是空串；有图的 5 个是 `5004660`(NormalGacha)、`7000001`(新手)、`8000004`(3★自选)、`90000000`(档案招募)、`99999999`(3★必得)。
2. `5004660`（CategoryType=6 NormalGacha）的本地化文本却是「**长期招募**」，但档期写着 `2026-11-12 14:00 ~ 2026-11-26 13:59` —— 文本与档期自相矛盾（模板串没换），客户端会显示「长期招募」+ 一个明确截止时间。
3. `7000001`（IsNewbie=True）只有 **4 段**本地化，缺 f9 档期串（其 `SalePeriodTo` 是 `2099-12-31 03:59:59`，本就没有截止文案）。
4. `IsNewbie=True` 只有 2 行（`7000000`、`7000001`）；`IsSelectRecruit=True` 有 5 行（`8000000..8000004`）；全表 `IsLegacy` 恒 false，`SalePeriodVisible` 恒 true。
5. 本报告只读：SQLite 以 `mode=ro` 打开，未执行任何写操作。
