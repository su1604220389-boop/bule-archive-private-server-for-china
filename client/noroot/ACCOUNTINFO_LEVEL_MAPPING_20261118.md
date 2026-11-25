# 「账号信息」页等级/最大值 字段绑定分析

> 只读。未改 APK、未重打包、未连服务器。
> 证据：`global-metadata.dat`（解混淆副本 `report\_tmp\patch\md_deob.bin`）+ `libil2cpp.so` 反汇编（capstone）+ `ba_ptrs.bin` 方法指针表。
> 日期：2026-11-18

---

## Q1 `AccountDB` 完整字段表（按声明顺序）

类型：**`MX.GameLogic.DBModel.AccountDB`**（type index **11900**），`fieldStart=52676`，**`field_count = 22`**。
全部为 auto-property（第 22 个除外）。

| # | 字段 | 推断类型 | typeIndex | 备注 |
|---|---|---|---|---|
| 1 | `ServerId` | long | 50531 | 账号主键 |
| 2 | `Nickname` | string | 61196 | |
| 3 | `CallName` | string | 61196 | |
| 4 | `DevId` | string | 61196 | |
| 5 | `State` | enum(→int) | 35149 | |
| 6 | `Level` | int | 50495 | |
| 7 | `Exp` | long | 50531 | |
| 8 | `Comment` | string | 61196 | 问候语 |
| 9 | `LobbyMode` | int | 50495 | |
| 10 | `RepresentCharacterServerId` | long | 50531 | |
| 11 | `MemoryLobbyUniqueId` | long | 50531 | |
| 12 | `LastConnectTime` | **DateTime** | 42727 | |
| 13 | `BirthDay` | **DateTime** | 42727 | |
| 14 | `CallNameUpdateTime` | **DateTime** | 42727 | |
| 15 | `PublisherAccountId` | long | 50531 | |
| 16 | `RetentionDays` | int | 25050 | |
| 17 | `VIPLevel` | int | 25050 | |
| 18 | `CreateDate` | **DateTime** | 42727 | |
| 19 | `UnReadMailCount` | int | 25050 | |
| 20 | `LinkRewardDate` | DateTime? | 24859 | |
| 21 | `LastReturningDate` | DateTime? | 24859 | |
| 22 | `Location` | 未知嵌套类型 | 61200 | **唯一一个没有 `k__BackingField` 的字段（普通公共字段）** |

> **重要**：`AccountDB` 里**没有** `MaxExp` / `MaxLevel` / `ExpMax` / `LevelMax` 这类字段。
> **也没有**任何"等级上限"字段。这一点直接决定 Q3 的答案。

**confidence**：字段名/顺序 = **实测**；类型 = **推断（中）**（typeIndex 聚类；`Il2CppType` 表未解开）。

---

## Q2 「等级」绑定的是哪个字段

### 结论：不是 `AccountDB.Level` 直接读，而是读**一个客户端缓存对象的固定偏移 `+0x44`**

`UIAccountInfo`（type[4161]，36 字段，40 方法）里，`RefreshLevelExp()`（mdef 26708，
vaddr **`0x0CCF14CC`**，**明文**）的反汇编：

```asm
0x0CCF1530  ldr  x20, [x19, #0xF8]     ; this.level  ← TextMeshProUGUI
0x0CCF1538  bl   #0x66C2DD0            ; get_Instance()（单例）
0x0CCF1540  ldr  x8,  [x0, #0x18]      ; instance.<data>   ← 账号缓存对象
0x0CCF1548  ldr  w8,  [x8, #0x44]      ; ★ 读 int @ data+0x44
0x0CCF1554  str  w8,  [sp, #0xc]
0x0CCF1558  bl   #0xA753434            ; int → string
0x0CCF156C  bl   #0xE63717C            ; Text.set_text
```

**⇒ `level` Text（`UIAccountInfo+0xF8`）显示的是 `get_Instance()->[+0x18]->[+0x44]` 这个 int。**
**不是** `AccountDB.Level` 的直接属性读取（il2cpp 里没有 `AccountDB.get_Level` 的调用）。

### 字段偏移的自校验（证明上面的映射不是猜的）

`UIAccountInfo` 36 个字段里，`level` 是第 11 个、`exp` 第 12、`expGauge` 第 13、
`normalLevelExp` 第 14、`maxLevelExp` 第 15；`nicknameLabel` 是第 5 个。
反汇编里用到的偏移：`nicknameLabel=+0xC8`、`level=+0xF8`、`exp=+0x100`、
`expGauge=+0x108`、`normalLevelExp=+0x110`、`maxLevelExp=+0x118`。

按"引用类型字段 8 字节对齐、从 0x10 起"推：
`nicknameLabel(5)` → `0xC8`，`callnameEmptyLabel(10)` → `0xF0`，`level(11)` → `0xF8`
⇒ **全部严格吻合**（相邻引用字段差 8）。**这套偏移映射可信。**
（`confidence`：**实测+算术自洽**）

### 关于 `111`

`111` = 服务端的 `Nickname` 值。而 `Nickname` 在 UI 上的文本字段是 **`nicknameLabel`（`+0xC8`）**
—— `RefreshNickname()`（mdef 26706，`0x0CCEF958`，**明文**）：

```asm
0x0CCEF990  ldr  x19, [x19, #0xC8]     ; this.nicknameLabel
0x0CCEF998  bl   #0x66C2DD0            ; get_Instance()
0x0CCEFA0C  ldr  x8,  [x0, #0x18]
0x0CCEF9AC  ldr  x1,  [x8, #0x20]      ; ★ 读 string @ data+0x20
0x0CCEF9BC  b    #0xE63717C            ; set_text
```

**⇒ `nicknameLabel` 显示 `data+0x20`（string）；`level` 显示 `data+0x44`（int）。两者是不同的字段、不同的 Text。**

**⇒ 判定**：`111` 出现在 `nicknameLabel`（昵称）上，`90` 出现在 `level`（等级）上 ——
**两个都是正确的**。截图里"等级 111"的读法**存疑**：按代码，`111` 不可能由 `level` 字段显示。

> **存疑项**：我无法把「屏幕上的位置」映射到「prefab 里的 Text」——
> 那需要 `UIAccountInfo` 的 prefab 结构（本机未解包该 prefab）。
> 但**字段 → 数据源**的映射是确定的，见上表。

---

## Q3 「最大值」绑定的是哪个字段

### 结论：`maxLevelExp` 是一个 **GameObject**（不是 Text），显隐由 `IsMaxLevelExp()` 决定

`RefreshLevelExp` 后半段（`0x0CCF1570` 起，明文）：

```asm
0x0CCF1574  bl   #0x66C2DD0            ; get_Instance()
0x0CCF1584  ...
0x0CCF1590  bl   #0x6AD6058            ; ★ IsMaxLevelExp()  → w0
0x0CCF1598  ldr  x21, [x19, #0x110]    ; normalLevelExp (GameObject)
0x0CCF15B8  bl   #0xE6E2264            ; GameObject.get_activeSelf
0x0CCF15D4  bl   #0xE6FA8B0            ; GameObject.SetActive(0/1)
...
0x0CCF15EC  ldr  x20, [x19, #0x118]    ; ★ maxLevelExp (GameObject)
0x0CCF160C  bl   #0xE6FA8B0            ; SetActive(1)   ← 满级时显示
```

* `normalLevelExp`（`+0x110`）与 `maxLevelExp`（`+0x118`）**类型都是 typeIndex 47315**
  —— 与 `spineParent` / `newEmblemMark` / `newbieTag` / `newbieIcon` 同类型 ⇒ **`UnityEngine.GameObject`**（推断，强）。
* 两者由 `IsMaxLevelExp()` 的结果 **互斥显隐**：满级显示 `maxLevelExp` 块，非满级显示 `normalLevelExp` 块。

### 我们发的 22 键里有没有它？—— **没有，而且不需要**

* `AccountDB` 22 个字段里**没有任何"经验上限/等级上限"字段**（见 Q1）。
* 客户端是用 **`IsMaxLevelExp()`（本地方法，`0x6AD6058`）** 判断的，不依赖服务端下发。

**⇒ 「最大值」后面没有数字 = 正常显示。**
满级时客户端按设计**不显示 `当前/上限` 数字**，只显示"最大值"三个字（这三个字是 prefab 里的静态文本）。
**不是数据缺失，也不是我们少发了字段。**

> 若确认 `Level=90` 就是该版本满级，则这个显示完全正确。
> `confidence`：`IsMaxLevelExp` 控制显隐 = **实测**；"90 是该版本满级" = **推断（中）**（需查 `CharacterLevelExcel`/`AccountLevelExcel` 的最大行）。

---

## Q4 「等级」那一块到底是什么结构

### 判定：**「等级 + 经验条」**，**不可编辑**

* `level`（`+0xF8`，Text）＝ 等级数字
* `exp`（`+0x100`，Text）＝ `GetCurrentExpString()`（`0x6AD610C`）—— 经验文本
* `expGauge`（`+0x108`，Slider/Image）＝ `GetCurrentExpRatio()`（`0x6AD5F74`）→ `set_value`
* `normalLevelExp` / `maxLevelExp`（`+0x110` / `+0x118`，GameObject）＝ 两种经验显示形态互斥切换

**没有任何"编辑"逻辑**：
`UIAccountInfo` 40 个方法里，编辑类只有 `OnEditNickname` / `OnEditComment` / `OnEditCallname`
三个（分别对应昵称、问候语、称呼），**没有 `OnEditLevel`**。

**⇒ 截图里那个铅笔按钮不是编辑等级**。按 `UIAccountInfo` 的字段，铅笔最可能是：
`nicknameButton` / `commentButton` / `callnameButton` / `idCardButton` / `userInfoButton` 之一，
它们的位置在 prefab 里，**我没有 prefab 无法确定是哪一个（存疑）**。

**⇒ 那一块不是"自定义等级/称号"，是标准"等级 + 经验条"。**

---

## Q5 `90` 和 `111` 分别读哪个字段

| 屏幕上的值 | 归属字段（代码层） | 数据源 |
|---|---|---|
| **`90`** | `UIAccountInfo.level`（`+0xF8`） | `get_Instance()->[+0x18]->[+0x44]`（int） |
| **`111`** | `UIAccountInfo.nicknameLabel`（`+0xC8`）**（推断，中）** | `get_Instance()->[+0x18]->[+0x20]`（string） |

**`111` 的来源 = 服务端 `AccountDB.Nickname = "111"`** —— 这一条与 lead 给的真实值完全对上，
反过来证明 `nicknameLabel` 用的就是 `Nickname`（不是 `CallName`）。

> 那 `杂鱼`（CallName）显示在"昵称"位置是另一回事：
> `callnameLabel` 是 `UIAccountInfo` 的第 9 个字段，由 `RefreshCallname()`（mdef 26707）单独赋值。
> **`Nickname` 和 `CallName` 在客户端是两个独立 Text，各显示各的。**

---

## 结论（3 行）

1. **`111` 不是"跑到等级位置上"的** —— 它由 `nicknameLabel`（`UIAccountInfo+0xC8`）显示，
   数据源是 `AccountDB.Nickname`（=111，正确）；等级数字 `90` 由另一个 Text（`+0xF8`）显示，
   数据源是客户端缓存的 `+0x44`。两者是不同的控件，**没有串位**。
2. **「最大值」后面为空是正常显示**：`maxLevelExp` 是 GameObject（不是数字 Text），
   由客户端本地 `IsMaxLevelExp()` 决定显隐；满级时按设计只显示"最大值"三个字。
   **`AccountDB` 22 个字段里没有任何经验上限字段，我们也不需要发。**
3. **那一块 UI 是「等级 + 经验条」，不可编辑**；`UIAccountInfo` 没有任何 `Level` 的编辑方法。

### 存疑 / 缺什么证据

| 项 | 缺什么 |
|---|---|
| 「等级 111」是否真的相邻显示 | 需要 **`UIAccountInfo` 的 prefab**（`assets/` 内）来做屏幕位置 ↔ 字段名映射；本机未解包 |
| 铅笔按钮是哪一个 | 同上（prefab 层级） |
| `90` 是否为该版本满级 | 需查 `AccountLevelExcel` / `CharacterLevelExcel` 的最大行（本机未导出该表数据） |
| 客户端缓存的 `+0x20`/`+0x44` 由谁填充 | 填充代码在 `get_Instance()->[+0x18]` 对应的 Manager 里，**该类未定位/未反编译**（不做假设） |
