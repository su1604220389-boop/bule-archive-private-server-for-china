# GACHA_ROOTCAUSE_DEEP — 招募链路取证（只读）

> 时间 2026-11-18 22:4x | **未改代码 / 未部署 / 未重启 / 未改库**
> 工具：`work\ba\plan\20261118\decode_shoprecruit.py`（FlatBuffer 手工解码，532/532 全部解出、`Id` 与行键 **零不一致**）
> 解码结果：`work\ba\plan\20261118\_shoprecruit_dump.json`

---

## 0. 结论速览（先给结论，证据在后）

```
A  本机 Excel 的 532 行全部解出：3 条 legacy(1,2,3) + 529 条 Id>=5e6 —— 与官方 529 条**条数完全一致**。
   截图里那个卡池（截止 2026/12/16 03:59:59、新手冲刺）**不在任何一行**；
   最匹配的是 **7000001**（CategoryType=23、IsNewbie=true、档期 2025-08-14 → 2099-12-31、TenGachaGoodsId=100101）。
   ⇒ 截图的 2026/12/16 是**客户端按"账号创建后 N 天"自己算出来的**，不是 Excel 里的档期。

B  ShopRecruitDB 只有 4 个字段，**足以**表达"卡池在售窗口"；免费次数在 ShopFreeRecruitHistoryDB（官方也是 []）。
   但我们下发的 JSON **省略了 UpdateDate**（官方样本每条都显式带 "0001-01-01T00:00:00"）——这是真实差异，需评估。

C  客户端"点招募10次不发请求"最可能不是"服务端没下发"，而是**客户端页签来自它自己的 Excel，与我们下发的 id 集合对不上**
   （"DUMMY" 页签 + 三行 "No LocalizeKey" 都指向客户端数据/本地化本身是残缺的）。
   当前证据不足以 100% 定论，下一版必须先做客户端侧取证，见 §3.3。
```

---

## 1. A · 卡池表解码

### 1.1 方法（可复现）
`ShopRecruitDBSchema` 是 `Id + Bytes`，`Bytes` 是 FlatBuffer 裸根表。按 `Schale\FlatData\ShopRecruitExcel.cs` 的
`__offset(4/6/8/…)` 手工解 vtable：

```python
pos = u32(buf,0); vt = pos - i32(buf,pos)
voff = 4 + 2*slot                      # slot 从 0 开始
field = 0 if voff >= u16(buf,vt) else u16(buf,vt+voff)
```
532 行全部解出，**0 个异常、0 个 Id 与主键不一致**。

### 1.2 全表统计（`_shoprecruit_dump.json`）

| 维度 | 值 |
|---|---|
| 行数 | 532 |
| Id 分布 | `<5e6`: 3（1,2,3）；`5e6~1e7`: 523；`1e7~9e7`: 4；`9e7~1e8`: 2 |
| CategoryType | 5:260 / 6:113 / 19:83 / 22:49 / 24:16 / 23:7 / 11:2 / 32:1 / 35:1 |
| DisplayTag | 0:377 / 1:83 / 3:45 / 6:16 / 7:5 / 8:4 / 5:2 |

### 1.3 关键行

| Id | Cat | IsNewbie | IsSelect | 档期 | TenGachaGoodsId | 备注 |
|---|---|---|---|---|---|---|
| 7000000 | 23 | **true** | false | 2024-02-08 → 2025-08-14 | 100100 | 新手冲刺（旧） |
| **7000001** | 23 | **true** | false | 2025-08-14 → **2099-12-31** | 100101 | **新手冲刺（当前）** |
| 8000004 | 23 | false | **true** | 2026-09-24 → 2027-06-10 | 0 | 3★自选招募 |
| 90000000 | 35 | false | false | 2026-07-16 → 2099-12-31 | 900001 | RecruitCoinId=79000 / SelectShopId=19000 |
| 5004660~5004710 | 5/6 | false | false | 2026-11-12 → **2026-11-26** | … | 当前在售的常规池 |
| 99999999 | 22 | false | false | 2024-08-01 → 2099-12-31 | 99999999 | |

### 1.4 「截图里那个卡池是哪个 Id」

- **没有**任何一行 `SalePeriodTo = 2026-12-16`（全表检索，0 命中）。
- 页签写着「账号创建后 ~ 2026/12/16 03:59:59 截止」⇒ 这是**客户端按账号创建时间计算的相对档期**，
  对应的是 **`IsNewbie=true` 的 7000001**（TenGachaGoodsId=100101，价格 1,000；封面 ミナ/南）。
  创建时间若为 2026-11-18，+28 天 = **2026-12-16** —— 与截图日期吻合。
- **它出现在官方 529 条里吗？** 是（`7000001 >= 5000000`）。
- **出现在本服 Excel 里吗？** 是（同一条）。

> 也就是说：**"服务端没下发这个卡池"这个解释不成立** —— 7000001 在线上 v4 的 `GachaRecruitBanners.cn.json` 里（我已核对：529 条，含 7000001、90000000）。

### 1.5 线上实际下发内容（只读核对了部署文件）

```
/www/wwwroot/ba_srv/Data/GachaRecruitBanners.cn.json
  count = 529   size = 40739   mtime = 2026-11-18 22:24
  id min/max = 5000000 / 99999999
  含 7000001: True   含 90000000: True   含 5000000: True   To=2026-12-16 的条数: 0
```

### 1.6 一个必须点出的不一致

`work\ba\srv_live\20261118_2210\wire-2026-11-18.txt.gz` 里 LoginSync 的 `ShopRecruits` 是
`{"Id":90050002,...}` 这一套（**90050xxx**，且**没有 UpdateDate 键**），不是 529 官方号段。
⇒ **这份 22:10 的抓包早于 22:24 的 v4 部署**，不能用来判断 v4 的效果。下一轮取证必须用 v4 之后的抓包。

---

## 2. B · 免费招募表与 `ShopRecruitDB` 四字段

### 2.1 三张表的关系（schema 来自 `Schale\FlatData\*.cs`）

`ShopFreeRecruitExcel`（表 `ShopFreeRecruitDBSchema`，**8 行**）：
```
Id / FreeRecruitPeriodFrom / FreeRecruitPeriodTo / FreeRecruitType /
FreeRecruitDecorationImagePath / TenRecruitCountOnly / ShopRecruitId[]   ← 注意是"一组卡池"
```
`ShopFreeRecruitPeriodExcel`（表 `ShopFreeRecruitPeriodDBSchema`，**67 行**）：
```
ShopFreeRecruitId / ShopFreeRecruitIntervalId / IntervalDate / FreeRecruitCount
```
语义：**免费招募活动**（例如新手/活动期免费十连）→ 通过 `ShopRecruitId[]` 关联到若干 `ShopRecruitDB.Id`；
`Period` 表把活动拆成若干"周期"，每周期给 `FreeRecruitCount` 次免费。
客户端用 `ShopFreeRecruitHistoryDB(UniqueId/RecruitCount/LastUpdateDate)` 记录**已用掉的免费次数**，
`UniqueId` 对应上面的 `ShopFreeRecruit.Id`。

**是否必须按卡池有行？** 官方 1017 样本里 `ShopFreeRecruitHistoryDBs = []`，说明**没抽过就是空数组**，
客户端能正常渲染"免费招募"按钮（次数从 Excel 的 Period/Count 推）。⇒ **不需要预置行**。

### 2.2 `ShopRecruitDB` 四个字段够不够

```
Id / SalesStartDate / SalesEndDate / UpdateDate
```
- 「开放中」判定只需 **Id + Start/End**，够用（官方也是只给这四个）。
- `UpdateDate` 在官方样本里 **每条都显式是 `0001-01-01T00:00:00`**。
- 我们线上 JSON 里 **整条省略了 `UpdateDate`**（抓包实证：`{"Id":90050002,"SalesStartDate":...,"SalesEndDate":...}`）。
  C# 反序列化时缺失 → `default(DateTime)` = `0001-01-01`，**值等价**；
  但**字段缺席**在客户端如果是"必须存在才认为记录有效"的实现里会有风险。**强度：弱推测**，建议下一版显式写 `UpdateDate`（零成本对齐官方）。

---

## 3. C · 「点招募10次不发请求」原因排序

### 3.1 已排除（有证据）
| 项 | 依据 |
|---|---|
| 协议号不一致 | 客户端 map 与服务端 enum 全对上：10006/10001/10005/10008/10009、10014-10016 |
| 客户端不问招募列表 | 11-18 日志里 **没有任何 10006**；招募页数据来自 LoginSync 内嵌 —— 与官方行为一致 |
| 服务端没下发 7000001 | v4 的 529 条里**有** 7000001 |
| Shop_List 差异 | 官方 `ShopInfos` 只有 `Category 38` 一个，与我们一致 |

### 3.2 排序（按证据强度）

**① 强推测：客户端页签来自它自己的 Excel，与我们的 id 集合不同 → 购买被闸在 UI 层**
- 证据 a：`DUMMY` 页签。我们 532 行里 **没有任何 banner 叫 DUMMY**（`GoodsDevName` 里 0 命中），说明这个页签是**客户端侧**的占位数据。
- 证据 b：正文三行 `No LocalizeKey` + 底栏「点数 / No LocalizeKey / 选择成员」—— 客户端本地化键缺失，属**客户端数据残缺**的特征，不是服务端字段缺失。
- 证据 c：客户端 11-17 发过 `Shop_PickupSelectionGachaSet` 且 `ShopRecruitID=90000000`（我们表里有 90000000，说明部分 id 是共用的）。
- 解释力：页面用客户端 Excel 渲染（标题/封面/价格/档期全部正常），但"是否可抽"取决于服务端 `ShopRecruits` 与客户端卡池 id 的**交集**；若客户端显示的 banner id 不在服务端列表里，按钮就禁用。
  ⚠️ 但目前**没有客户端侧证据**证明"哪个 id 被判定为不可用"。

**② 中推测：档期不一致**
- 客户端显示 2026/12/16（自算），我们下发 7000001 的 `SalesEndDate = 2099-12-31`。若客户端做"服务端档期必须在客户端档期内"这类校验，可能判定异常。**无直接证据**。

**③ 弱推测：招募点数货币解析失败**
- 90000000 的 `RecruitCoinId=79000`；若 `ItemList`/物品名解析不到 → 底栏「点数」旁显示 `No LocalizeKey`。但"点数"本身显示正常，故证据弱。

**④ 已排除：服务端列表为空/协议错/Shop_List 差异**（见 3.1）。

### 3.3 下一版该改哪一处 —— **先取证，别改**

**目前无法定论**（缺客户端侧证据）。必须先拿到：
```
① v4 部署之后的一次真机抓包（wire 日志 + nginx），确认 LoginSync 里 ShopRecruits 是 529 条且带 UpdateDate；
② 点「招募10次」时的**客户端行为**：是否有请求发出（抓 tcp 全量，不只看 /api/shop/*），
   —— 注意 CN 客户端所有协议都走 /api/gateway，**只看 /api/shop/* 会漏**；
③ 客户端 Excel：从 APK 解出它的 shoprecruitexceltable（或 persistent 下的 ExcelDB），
   比对它的 banner id 集合 与 我们的 529 集合的**交集**——这是验证 ① 的唯一硬证据。
```
**取证后若 ① 成立，改法是**：`ShopRecruits` 改为"客户端 Excel 的 id 集合"（或两者的并集），
而不是我们自己的 `ExcelDB.db`/官方 529；这需要先拿到客户端 Excel 数据。

**若 ② 成立，改法是**：把下发档期改为客户端 Excel 的档期（或放宽为 2099），并显式写 `UpdateDate`。

---

## 4. 证据索引

| 证据 | 位置 |
|---|---|
| 532 行 FlatBuffer 解码 | `work\ba\plan\20261118\decode_shoprecruit.py` → `_shoprecruit_dump.json`（本次生成，532/532 成功） |
| ShopRecruitExcel schema | `work\ba\srv_src\Schale\FlatData\ShopRecruitExcel.cs:23-96` |
| ShopFreeRecruit schema | `work\ba\srv_src\Schale\FlatData\ShopFreeRecruitExcel.cs`、`ShopFreeRecruitPeriodExcel.cs` |
| ShopRecruitDB 四字段 | `work\ba\srv_src\Schale\...\DBModel.cs:2273-2278` |
| 官方 529 条 | `report\_tmp\official_decoded_201\02_1017_api_account_loginsync.response.json` |
| 官方 Shop_List 仅 Cat38 | `report\_tmp\official_decoded_201\86_10002_api_shop_list.response.json` |
| 线上 v4 下发文件 | `/www/wwwroot/ba_srv/Data/GachaRecruitBanners.cn.json`（529 / 22:24） |
| 线上 Excel 表 | `work\ba\data\ExcelDB.db` → `ShopRecruitDBSchema` 532 / `ShopFreeRecruitDBSchema` 8 / `ShopFreeRecruitPeriodDBSchema` 67 |
| 11-18 抓包（v4 之前） | `work\ba\srv_live\20261118_2210\wire-2026-11-18.txt.gz`（ShopRecruits=90050002 号段、无 UpdateDate） |
| 11-17 抓包（10015=90000000） | `/www/wwwroot/ba_srv/logs/wire-2026-11-17.txt`（Lead 已核） |
