# 招募界面不可用 —— 方案（未改任何代码）

日期：2026-11-19 00:1x
状态：**方案阶段，等你拍板**

---

## 0. 一句话

按你说的思路（**服务端的数据/枚举比国服客户端新，客户端解析不了**），这和当初「发全部角色导致登录报服务端处理错误」是**同一类问题**。
现成的解法就是 `BAPATCH-CLIENTROSTER v1`：**不动表，在服务端"读表"这一层把客户端解析不了的行滤掉**，名单放运行时文本文件，换表不用重编译。

---

## 1. 同类问题的判据对照

| | 发全部角色（2026-11-17） | 招募界面（现在） |
|---|---|---|
| 现象 | 登录报「服务端处理错误」 | 界面能开，卡池数据全是 `No LocalizeKey`，按钮点不动 |
| 判据 | 服务端发了 23 个**客户端表里解析不了**的角色 id | 服务端发的卡池里，**有 5 个 `GachaBannerPath` 为空**（客户端渲染不出图/名） |
| 定性 | 含坏 id > 0 就崩，= 0 就进，**一个例外都没有** | 待用同样方法验证 |
| 解法 | `ExcelTableService.GetTable<T>()` 读表层过滤 + `Resources/ClientUnsupportedCharacters.txt` | 同款（见 §4 方案 A） |

### 区别（必须说清楚，不夸大）
- 角色那次是**硬崩**（登录失败）；卡池这次是**软降级**（界面变成占位数据，按钮不响应）。**不是同一个症状，可能是同一类成因。**
- 卡池这次**还没有拿到"剔除后就好了"的证据**，所以方案里第一步是**单变量验证**，不是直接改。

---

## 2. 借鉴的现成解法（原文位置）

`work\ba\server\deploy\_panel\LOGIN_SYNC_ERROR_DIAG_20261117.md` §4「修复（两层保险）」：

```csharp
// Shittim-Server/Services/ExcelTableService.cs，标记 BAPATCH-CLIENTROSTER v1
private static readonly long[] DefaultClientUnsupportedCharacters = [ ...23 个 id... ];

// GetTable<T>() 里：缓存填充后过滤一次，过滤结果写回缓存；bypassCache 也走过滤
if (bypassCache || clientRosterFiltered.TryAdd(type, 0))
{
    var rosterFiltered = DropClientUnsupportedCharacters(unpacked);
    if (!ReferenceEquals(rosterFiltered, unpacked)) { caches[type] = rosterFiltered; unpacked = rosterFiltered; }
}
```

**为什么有效（当时写的理由，同样适用于卡池）**：
`!giveall` / `!give` / 邮件 / 卡池 / 商店 / 活动奖励**全部走 `ParcelResolver` 查同一张表** ⇒ 一处过滤全链路生效。
**运行时后门**：`Resources/ClientUnsupportedCharacters.txt`，一行一个 id，`#` 注释，客户端更新后改文件即可，**不用重编译**。

---

## 3. 实测数据（只读算出来的，可复现）

脚本：`work\ba\scripts\plan_banner_funnel.py`
输入：客户端表 `work\ba\data\ExcelDB.db`（160,534,528 B，md5 `824ce3a8bee2bb5ae36ada1ac95048f1`，
与官方 `TableManifest` 里 `ExcelDB.db` 的 `Size/Crc` **逐位一致**）；服务端下发清单
`work\ba\srv_src\Shittim-Server\Data\GachaRecruitBanners.cn.json`（529 条）。

| 筛选 | 数量 | 说明 |
|---|---|---|
| 服务端下发卡池 id | 529 | 官方 CN 抓包原样 |
| 在客户端表 `ShopRecruitDBSchema` 里存在 | **529（全部命中）** | 差集为 0 |
| 其中当前档期开放（now=2026-11-18 23:00） | **10** | |
| 且有 `GachaBannerPath`（有卡池图） | 开放 10 个里 **5** | 全局 150 |
| 且有 `LocalizeGachaShop` 行 | **529（全部命中）** | |
| **完全干净：开放 + 有图 + 有本地化** | **5 个** | 见下表 |

### 5 个干净的卡池

| Id | DisplayOrder | CategoryType | 图 | 档期 |
|---|---|---|---|---|
| `5004660` | 60 | 6 | `Event_Banner_50001` | 2026-11-12 14:00 ~ 2026-11-26 13:59:59 |
| `7000001` | 1 | 23 | `Event_Banner_70001` | 2025-08-14 14:00 ~ 2099-12-31 |
| `8000004` | 2 | 23 | `Event_Banner_80000` | 2026-09-24 14:00 ~ 2027-06-10 |
| `90000000` | 100 | 35 | `Event_Banner_50002` | 2026-07-16 10:00 ~ 2099-12-31 |
| `99999999` | 4 | 22 | `Event_Banner_60000` | 2024-08-01 14:00 ~ 2099-12-31 |

### 有问题的 5 个（开放但**没有卡池图**）

`5004670 / 5004680 / 5004690 / 5004700 / 5004710` —— `GachaBannerPath` 为空字符串。
**用户截图里那个「美咲（泳装）」池子就是它们之一**（`InfoCharacterId=[20049]`），
页签才会显示 `DUMMY`。

---

## 4. 方案（三选一，都不改 `ExcelDB.db`）

### 方案 A（推荐，和 CLIENTROSTER 同款）：在服务端过滤 `ShopRecruit`
在服务端把「客户端渲染不出来的卡池行」在**读表这一层**剔掉：
- 判据（三选一或组合）：`GachaBannerPath` 为空 / 档期已过 / 客户端表里没有
- 名单来源：运行时文件 `Resources/ClientUnsupportedBanners.txt`（一行一个 id，`#` 注释）
- **不重编译**：换名单只改文件
- 影响面：`ShopRecruits` 下发、`GachaRecruitList`、以及任何按这张表枚举的地方（和 CLIENTROSTER 一样一处生效）

**风险**：这是 C# 代码改动 → 要重编译 + 部署新 DLL（有回滚脚本）。

### 方案 B（最轻，先做这个验证）：只改数据文件 `GachaRecruitBanners.cn.json`
把下发清单收敛成 §3 那 5 个干净 id（或先只留 1 个做单变量实验）。
- **不动代码、不动表、不动 DLL**，重启即生效
- 立刻能回答一个关键问题：**页签到底是不是由我们下发的 `ShopRecruits` 决定的**
  - 若页签变成 5 个（或 1 个）且标题正常 → 我们控制得住，按方案 A 收口即可
  - 若页签照旧 3 个 → 页签来自客户端本地表，方案 A/B 都无效，需要换思路

### 方案 C（折中）：服务端把「没有卡的池子」映射到「有卡的池子」
下发时把 `5004670..5004710` 这些空图 id 替换成 `5004660` 这类干净 id。
**不推荐**：会让玩家看到与实际不同的卡池内容，语义混乱。

---

## 5. 建议执行顺序

1. **先做方案 B 的最小实验**：下发清单只留 `7000001`（新手冲刺Ⅱ，有图有本地化，档期到 2099）。
   - 预期：只剩 1 个页签，标题「新手冲刺Ⅱ」，按钮能点
   - 若成 ⇒ 说明我们控制得住页签，再按方案 A 正式收口
   - 若败 ⇒ 页签来自客户端本地表，回滚，换思路（下一步查 `UIGacha` 的页签构建逻辑）
2. 通过后再做方案 A（读表过滤 + 运行时名单）
3. 全程单变量、每次备份 + 回滚脚本

---

## 6. 需要你拍板的点

1. **先跑方案 B 的单变量实验吗**（只下发 1 个卡池，几分钟可回滚）？
2. 最终形态你要哪种：
   - (a) 只保留「有图有本地化且开放中」的卡池（干净，但池子少）
   - (b) 保留全部，只把没图的踢掉（`5004670` 那一族不要）
   - (c) 其它
3. 方案 A 要改 C# 重编 DLL，你接受吗？还是先用方案 B 的数据文件顶着？

---

## 7. 附：本次排查中已经排除的（别再回头查）

| 假设 | 结论 |
|---|---|
| 客户端表过期 | 排除：客户端表 md5 `824ce3a8…` = 官方 `TableManifest` 里 `ExcelDB.db` 的 `Crc`，逐位一致 |
| 服务端没发卡池 | 排除：LoginSync 里 `ShopRecruits` 529 条 |
| id 客户端没有 | 排除：529/529 全部命中客户端表 |
| 本地化缺失 | 排除：`LocalizeGachaShop` 对 529 条**全部命中**；`5004670` 的标题实际是「限时招募！」、说明「美咲（泳装）（3★）招募概率提升！」 |
| `IsLegacy` 闸门 | 排除：532 行全部为 0，闸门放行 |
| 券数量/货币不足 | 排除：用户实测——即使没券、宝石不够，按钮也应正常显示（是显示问题不是余额问题）；且各种发放通道都正常 |
| `PickupSelectionGacha` 不保存选择 | **已修**（`/root/PICKSEL_20261118_230108/`），但不是本次根因 |
| 桥把 `Item_List` 换成固定桩 | **已修**（`/root/BRIDGE_ITEMLIST_20261118_235716/`），验收 620 B→2,988 B / 30 件，与库一致；用户实测道具能领到 ⇒ 通道正常 |

---

## 8. 仍然解释不了的一点（必须留档）

客户端表里 `LocalizeGachaShop[5004670]` **有完整中文文本**，且该 id 在我们下发的 529 里，
但界面上标题/说明显示 `No LocalizeKey`。
⇒ **客户端查的很可能不是 `GachaShopId = 卡池 id`**，而是 `ShopRecruit` 行里另一个字段（如 `GoodsDevName`
或某个 localize id），那个字段在我们下发的数据里是空/0。

**待验证**：`ShopRecruitExcel` 12 个字段里没有 localize id 字段（`logcat-architect` 已解出字段表），
所以键只可能来自 `LocalizeGachaShop` 自身或 `Goods`。下一步需要解 `UIGacha` 取标题的那一处调用。
