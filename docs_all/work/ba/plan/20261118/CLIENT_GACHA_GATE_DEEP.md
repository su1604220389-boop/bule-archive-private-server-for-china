# 招募按钮点不动 —— 客户端侧证据（深挖）

> 只读取证。未改客户端、未改服务端、未重启、未下载。
> 证据：`global-metadata.dat`（解混淆副本 `md_deob.bin`）+ `ba_ptrs.bin` + `libil2cpp.so` 反汇编 + `NetworkProtocol.cs`。
> 标注：**【已证实】**= 有 typeIdx/偏移/地址/反汇编原文；**【推测】**= 未闭环；**【找不到】**= 明确没拿到。

---

## 0. 一句话结论（本轮最重要的发现）

**【已证实】客户端的"能不能抽"判定**不看服务端的 `ShopRecruits`，而看客户端本地 Excel**：
`UIGacha.IsCanBuyGacha()`（明文，`0x09FB86CC`）第一句就是
`IsShopRecruitOpen(targetExcel, id, CurrentTime)`（`0x0EACBD14`），**返回 false 就直接跳过整个购买分支**。

**⇒ 这就是为什么服务端怎么改 `ShopRecruits` 都没用 —— 那根本不是这个按钮的输入。**

---

## 1. `ShopBuyGacha3Request` 字段清单（与你的问题 1）

**【已证实】客户端 2 个字段，与服务端逐字段一致，无多余字段、无类型冲突。**

```
客户端  type[11544]  MX.NetworkProtocol  ShopBuyGacha3Request  fields=2
    <FreeRecruitId>k__BackingField   typeIdx=50531   (long)
    <Cost>k__BackingField            typeIdx=55361   (对象 — 对应服务端 ParcelCost?)

服务端  NetworkProtocol.cs:6614
    public class ShopBuyGacha3Request : ShopBuyGacha2Request {
        public override Protocol Protocol { get => Protocol.Shop_BuyGacha3; }
        public long FreeRecruitId { get; set; }
        public ParcelCost? Cost { get; set; }
    }
```
**⇒ 完全对齐（2 对 2，long 对 long，ParcelCost 对 55361）。**

顺带把同族的也核了（全部对齐）：

| 类型 | 客户端字段 | 服务端字段 | 判定 |
|---|---|---|---|
| `ShopBuyGachaRequest` type[11539] | `GoodsId`(50531 long), `ShopUniqueId`(50531 long) | 同名同类型（:6583） | ✅ 一致 |
| `ShopBuyGacha2Request` type[11541] | **fields=0**（全继承） | `: ShopBuyGachaRequest` 且无新字段（:6597） | ✅ 一致 |
| `ShopBuyGachaResponse` type[11540] | `ConsumeResultDB`(41482), `ParcelResultDB`(55384) | 同名（:6590） | ✅ 一致 |
| `ShopBuyGacha2Response` type[11543] | `UpdateTime`,`GemBonusRemain`,`GemPaidRemain`,`ConsumedItems`,`GachaResults`,`AcquiredItems`,`GoldRemain`（7） | 同名 7 个（:6602） | ✅ 一致 |
| `ShopBuyGacha3Response` type[11545] | `FreeRecruitHistoryDB`(59699), `PickupFirstGetHistoryDBs`(22592) | 同名 2 个（:6621） | ✅ 一致 |
| `ShopPickupSelectionGachaSetRequest` type[11568] | `ShopRecruitID`(50531), `PickupCharacterSelection`(10683) | — | （未在服务端找到同名，可能是 CN 特有） |
| `ShopPickupSelectionGachaSetResponse` type[11569] | **fields=0** | — | 空响应 |

**⇒ 结论：DTO 层没有任何"客户端多字段/类型不符"的问题，服务端回包不会因此对不上。**

---

## 2. `ShopGachaRecruitListResponse` 完整字段清单（问题 2）

**【已证实】客户端 2 个字段，与服务端一致。**

```
客户端  type[11553]  MX.NetworkProtocol  fields=2
    <ShopRecruits>k__BackingField              typeIdx=22823   (List<ShopRecruitDB>)   偏移 +0x50
    <ShopFreeRecruitHistoryDBs>k__BackingField typeIdx=22811   (List<ShopFreeRecruitHistoryDB>)

服务端  NetworkProtocol.cs:6676
    public class ShopGachaRecruitListResponse : ResponsePacket {
        public List<ShopRecruitDB>? ShopRecruits { get; set; }
        public List<ShopFreeRecruitHistoryDB>? ShopFreeRecruitHistoryDBs { get; set; }
    }
```
**⇒ 没有第三个字段，客户端没有隐藏字段。**

元素类型也核了：
```
ShopRecruitDB type[12143] fields=4: Id(50531 long), SalesStartDate/SalesEndDate/UpdateDate(42727 DateTime)
ShopFreeRecruitHistoryDB type[12139] fields=3: UniqueId(50531), RecruitCount(50495 int), LastUpdateDate(42727)
```

---

## 3. 招募界面类与"可用性判定"方法（问题 3）

**【已证实】关键判定方法全部在 `UIGacha` 里，且 `IsCanBuyGacha` 是明文。**

### 3.1 最可疑 top5（按相关性排序）

| # | 方法 | mdef | vaddr | 状态 | 为什么可疑 |
|---|---|---|---|---|---|
| 1 | **`UIGacha.IsCanBuyGacha`** | 49518 | **`0x09FB86CC`** | **PLAIN** | 名字即"能不能买"，是购买前最后一道闸 |
| 2 | `UIGacha.CheckActiveTicketGacha` | 49495 | `0x09FB7B80` | PLAIN | 判断"当期是否有可用招募券池" |
| 3 | `UIGacha.IsOpenEventThreeStarGacha` | 49497 | — | — | "活动三星池是否开放" |
| 4 | `UIBasicGachaButton.SetGachaCost` | 49244 | `0x0A8CADF4` | PLAIN | 设置按钮上的消耗显示（1,000 就是它） |
| 5 | `UIBasicGachaButton.SetTicketTenUseCheckAndSetting` | 49245 | `0x0A8CBD54` | PLAIN | "10 连是否需要票"的勾选与设置 |

其余相关（名字已够用，未逐个反汇编）：
```
UIGacha: CheckDuplicateThreeStarTab(49496), SetGachaTab(49494), SetData(49521), SetNotice(49522)
UIFreeGachaDisplay.IsGachaFreeAndSetData(49267) @0x0A8CB450 PLAIN
UILobbyGachaTag: CheckFreeGacha(42319), CheckThreeStarGachaAvailability(42321), UpdateTagFlags(42320)
UIGachaPopupRetry.IsOneTicketTenUse(39514)
UIRecruitShopInfo: OpenRecruitShop(49332), SetGachaCeilingData(49331)
UIBasicGachaButton.SetData(49243)
```

### 3.2 ★ `IsCanBuyGacha` 的实际判定链（反汇编原文）

```asm
0x09FB891C  bl  get_targetExcel            ; 取 UIGacha.targetExcel（卡池 Excel 行）
0x09FB892C  bl  get_Id                     ; 取该行的 Id
0x09FB8958  bl  get_CurrentTime            ; 取当前时间
0x09FB8990  bl  IsShopRecruitOpen          ; ★★★ 第一道闸
0x09FB8994  tbz w0, #0, #0x9FB8A38         ; 返回 false → 直接跳走（不进购买分支）
0x09FB89A4  bl  get_freeRecruitId          ; 过了才看"免费招募 id"是否为空
0x09FB89B0  b.eq #0x09FB8B30               ; 空 → 另一分支
0x09FB8A00  bl  get_CurrentTime            ; 再取时间（免费池判定）
```

**⇒ `IsCanBuyGacha` 的输入是 `targetExcel` + `Id` + `CurrentTime`，与 `ShopRecruits` 完全无关。**

### 3.3 ★ `IsShopRecruitOpen` @`0x0EACBD14` 的内部结构（反汇编原文）

```asm
0x0EACBDB4  ldr  x0, [x21, #0x48]      ; this+0x48 = 一张表（按 id 查 Excel 行）
0x0EACBDD0  bl   helper                ; Dictionary.TryGetValue(id, out excel)
0x0EACBDD4  tbz  w0, #0, #0xEACBDE8    ; ★ 查不到 → 走另一分支
0x0EACBDD8  ldr  x10, [sp, #0x18]      ; out excel
0x0EACBDDC  cbz  x10, #0xEACBEC4       ; null → 返回 false
0x0EACBDE0  ldrb w8, [x10, #0x1c]      ; ★ excel + 0x1C 是一个 bool
0x0EACBDE4  cbz  w8, #0xEACBE04        ; false → 走另一分支
```

**【已证实】** 结构：`[表].TryGetValue(id)` → 命中则读 `excel+0x1C` 的 **bool**。
**【找不到】** 那个 bool 的**字段名与语义**（`ShopRecruitExcel` 的字段名在 FlatData 生成类里，本机只有
`Schale\FlatData\ShopRecruitExcel.cs` 的 C# 版本可参考，但**没有该 Excel 的实际数据行**来验证是哪一个列）。

> 可参考的服务端同名类：`work\ba\srv_src\Schale\Excel\ShopRecruitExcelExt.cs` 里用到
> `InfoCharacterId` / `SalePeriodFrom` / `SalePeriodTo` / `CategoryType`；
> **`excel+0x1C` 的 bool 很可能是"是否开催/是否可购买"一类标记，但这是【推测】。**

### 3.4 这个链条对你意味着什么

**客户端判定顺序（已证实）**：
```
点「招募10次」
  → UIGacha.IsCanBuyGacha()
      → IsShopRecruitOpen(targetExcel, Id, Now)   ← ① 本地 Excel 行是否可开催
          → 查不到 id 或 excel+0x1C==false ⇒ 返回 false ⇒ 不发任何请求
      → freeRecruitId 分支（免费池）
      → …
```
**服务端的 `ShopRecruits` 只影响"列表里显示哪些卡池"，不影响 `IsCanBuyGacha` 的闸门。**
**⇒ 要让客户端发请求，必须让"客户端本地 Excel 的 `ShopRecruitExcel` 里那个 id 这一行"满足 `IsShopRecruitOpen` 的条件。**

---

## 4. 字符串表：招募相关 key / 文案（问题 4）

### 4.1 metadata 里的标识符（**【已证实】**，`md_deob.bin` 字符串堆，前缀扫描，共 662 条唯一命中）

与招募直接相关的原文（含偏移）：

```
0x000F4FD5  LocalizeKey                      ← ★ "No LocalizeKey" 的来源就是这个前缀字面量
0x00112780  RecruitId              0x001127A4  ShopRecruitId
0x00114753  Gacha                  0x00114753  GachaInfo
0x0011F6CD  GachaDB                0x0011F6E0  GachaProgress
0x0011F717  GachaProgresses        0x0011F7A8  Gachable
0x0011F7B5  GachableCount          0x0011F7CC  GachaCount
0x0011F862  GachaNullOrEmpty       ← ★ 名字直指"空"
0x0011F8CD  GachaGroupIdCount
0x0013472C  GachaInfoObject        0x00134746  ShopRecruit
0x001347B2  RecruitSelectionShop   0x00134846  RecruitShop
0x0013489C  GachaSnapshot         0x001348F8  GachaRemainCount
0x0013493C  GachaStart            0x00134970  GachaChange
0x00134A0C  GachaCost             0x00134BAF  GachaAvailableParcels
0x00135530  ShopRecruitBuyStudentNetworkTask
0x00135146  ShopBuyGacha3NetworkTask
0x00139DF8  GachaGoodsId           0x00139DE3  GachaTicket
0x00143418  GachaTutorialCompletionCheck
0x00143624  GachaResultStartConditionID
0x00188D37  GachaUI                0x00188D56  GachaItemDisplay
0x0018C6B3  GachaShopUniqueId      0x0018C64C  GachaShopInfo
```

### 4.2 本地化表里的招募文案（**【已证实】**，`work\ba\data\ExcelDB.db` → `LocalizeDBSchema`，18,456 行）

招募相关命中 40+ 行，关键原文（含占位符）：

| rowid | 原文 |
|---|---|
| 3193 | `免费次数` |
| 3513 | `是否继续进行1次招募` |
| 3514 | `招募1次` |
| 3515 | `招募10次` |
| 3516 | `是否继续进行10次招募` |
| 3517 | `是否使用[c][007eff]{0}[-][/c]个青辉石购买[c][007eff]{1}[-][/c]信用积分\n并进行免费招募` |
| 3525 | `招募成员` |
| **768** | **`招募所需的招募券不足`** |
| 1030 | `招募{0}名成员` |
| 3145 | `需招募{0}的学员` |
| 3596 | `是否进行免费新手冲刺招募` |
| **3263** | **`开放期间 : 请参考官方社群公告`** |
| **3264** | **`距离开放剩余{0}天{1}小时`** |
| **3265** | **`距离开放剩余{0}小时{1}分`** |
| 3302 | `离{0}剩余{1}:{2}:{3}` |
| 3521 / 3522 / 3595 | `距离结束剩余[c][50caff]{0}[-][/c]` / `距离过期剩余[c][50caff]{0}[-][/c]` |

**【已证实】** `LocalizeErrorDBSchema`（429 行）里**没有招募相关的错误行**（17 条命中全是编队/等级等无关文案）。
**⇒ 招募被拦时不弹错误框、只表现为"按钮无响应"，与现象一致。**

**【已证实】** 没有「无法招募」「此卡池不在开放期间」这类**硬拦截文案**——
说明卡池不在期是**显示倒计时**（`距离开放剩余…`），不是报错。

---

## 5. 结论与建议（按证据强度排序）

| # | 结论 | 强度 | 可执行动作 |
|---|---|---|---|
| 1 | 客户端购买闸门是 `UIGacha.IsCanBuyGacha` → `IsShopRecruitOpen(targetExcel, Id, Now)`，与 `ShopRecruits` 无关 | **已证实**（反汇编） | 不要再调 `ShopRecruits` 的内容 |
| 2 | `IsShopRecruitOpen` 用"id → Excel 行"查表，命中后看 `excel+0x1C` 的 bool | **已证实**（反汇编） | 需要确认那个 bool 对应 Excel 哪一列 |
| 3 | 三个 DTO（Gacha3Req / RecruitListResp / 同族）与服务端**完全对齐** | **已证实**（逐字段） | 不用改 DTO |
| 4 | `excel+0x1C` bool 的语义 | **找不到** | 需要 `ShopRecruitExcel` 的**实际数据行**（`ExcelDB.db` 里应有 `ShopRecruitDBSchema` 表，下一轮可直接查） |
| 5 | `targetExcel` 取自 `UIGacha.targetExcel`，其赋值点在 `UIGacha.SetData` | **推测** | 下一轮可反汇编 `SetData`(mdef 49521) 确认 id 从哪来 |

**最短下一步（一条 SQL，零风险）**：
查 `work\ba\data\ExcelDB.db` 的 `ShopRecruitDBSchema` 表，看里面**有哪些 id**、以及
**是否存在一列对应"可开催/开催中"的 bool（第 28 字节位附近）**——这能把 `excel+0x1C` 直接钉死。

---

## 6. 本轮新增脚本

`report\_tmp\meta\s36_gacha_dto.py`（DTO 字段 + UI 方法名导出）
