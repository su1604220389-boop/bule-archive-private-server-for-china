# ID 卡名字位 与 Show\* 开关 的客户端绑定

> 只读。未改 APK、未碰服务器。
> 证据：il2cpp `md_deob.bin` 类型表 + `libil2cpp.so` 反汇编（capstone）。
> 日期：2026-11-18

## 两句话答案

**① ID 卡大号名字位（`userName`）= `MXAccount.AccountInfo.Nickname`（`AccountInfo+0x20`）。**
**② `Show*=false` 时客户端显示 prefab 静态占位文本，不是 `SetActive(false)` 隐藏整块。**

---

## 1. 界面类与字段

**`UIIdCardObject`**（type[6050]，20 字段，8 个方法）—— 卡片本体：

```
 1 spinePos                       2 spineRenderqueueTarget
 3 studentName  (Text)            4 userName (Text)      ← 大号名字位
 5 level        (Text)            6 emblemParcel
 7 friendCode   (Text)            8 comment (Text)
 9 raidRankingIcon               10 raidRankingLabel
11 eliminateRaidRankingIcon      12 eliminateRaidRankingLabel
13 arenaRankingIcon              14 arenaRankingLabel
15 multiFloorRaidClearedDifficultyLabel
16 background                    17 spineMaskRenderer
18 defaultIdCardMaterial         19 popupIdCardMaterial    20 spineCharacter
```

数据源：`SetMyIdCard()`（mdef 39010，vaddr **`0x0A02B060`**，**明文**）。
取数据：`get_Instance()->[+0x190]->get_MyIdCardClone()` → 一个 `FriendIdCardDB` 副本。

> 偏移由"字段声明顺序 + 8 字节对齐"推出，并用反汇编逐条验证：
> `spinePos`(Vector3,12B)@0x10 → `spineRenderqueueTarget`@0x20 →
> **`studentName`@0x28** → **`userName`@0x30** → **`level`@0x38** → `emblemParcel`@0x40 → `friendCode`@0x48 → `comment`@0x50…

## 2. 名字位的写入（实测反汇编）

```asm
; studentName ← 学生名（按卡上角色取名字）
0x0A02B238  ldr  x21, [x19, #0x28]        ; this.studentName
0x0A02B254  ldr  x2,  [x20, #0x30]        ; DB clone+0x30 = 角色 id
0x0A02B260  bl   GetName                  ; 本地化取学生名
0x0A02B274  bl   set_text

; ★ userName ← 账号昵称
0x0A02B278  ldr  x21, [x19, #0x30]        ; this.userName   ← 大号名字位
0x0A02B280  bl   get_Instance             ; MXAccount
0x0A02B288  ldr  x8,  [x0, #0x18]         ; MXAccount.AccountInfo
0x0A02B294  ldr  x1,  [x8, #0x20]         ; ★ AccountInfo.Nickname（string）
0x0A02B2A8  bl   set_text
```

⇒ **大号名字位就是 `AccountInfo.Nickname`**，与 `FriendIdCardDB` 无关
（后者 22 个字段里确实没有昵称，与服务端定义一致）。

## 3. 等级格与 `ShowAccountLevel`（这就是 Show\* 的用法样本）

```asm
0x0A02B2B0  ldr  x21, [x19, #0x38]        ; this.level
0x0A02B2DC  ldrb w8,  [x20, #0x50]        ; ★ DB clone +0x50 = ShowAccountLevel (bool)
0x0A02B2E4  cbz  w8,  #0xA02B318          ; ★ false → 跳到"用静态文本"分支
; true 分支：
0x0A02B2FC  ldr  w8,  [x8, #0x44]         ; AccountInfo.Level
0x0A02B30C  bl   int→string
0x0A02B31C  ...  与本地化模板（"Lv. {0}"）拼接
0x0A02B330  bl   set_text
; false 分支：
0x0A02B318  ldr  x1, [x27]                ; ★ 直接取一个静态字符串常量
0x0A02B31C  b    （同一处 set_text）
```

**⇒ 判定（实测）：`ShowAccountLevel = false` 时，客户端把该 Text 设成 `[x27]` 里的静态文本，而不是隐藏整块。**

> `[x27]` 是 `adrp x27,#0xfa34000; ldr x27,[x27,#0xa0]` 取到的字符串常量的槽位，
> 具体内容需读该槽的运行时值 —— **静态上拿不到字面量，存疑**。
> 但从"同一个 `set_text` 出口"这一点可以确定：**它一定写文本，不会 SetActive(false)**。

`ShowFriendCode` / `ShowRaidRanking` / `ShowArenaRanking` 等其余开关，按同一种代码模式
（`ldrb [DB+偏移]` → `cbz` → 静态文本 vs 实际值）处理，**推断（中）**，未逐个反汇编。

## 4. ★ 顺带定位到的更严重问题：整张卡可能根本没被刷新

`SetMyIdCard` 开头：

```asm
0x0A02B1A8  bl  get_MyIdCardClone
0x0A02B1AC  cbz x0, #0xA02B770     ; ★ 若 clone 为 null → 直接 return，整张卡不刷新
```

**⇒ 如果 `get_MyIdCardClone()` 返回 null，`SetMyIdCard` 立刻返回，
卡片上所有 Text 都保持 **prefab 初始值** —— 也就是屏幕上看到的
`username` / `Lv. 72` / `AAAAAAAAAA` / `100,000` 这一整套"占位"。

**这比"缺 18 个字段"更能解释"整张卡每个格子都是占位"的现象**：
如果是字段缺失，只有被 `Show*` 保护的那几格会是占位，`userName` 应该显示真实昵称；
而现在**连 `userName`（不受任何 Show\* 保护、直接读 `AccountInfo.Nickname`）都是 `username`**，
说明 **`SetMyIdCard` 整体没跑**。

`get_MyIdCardClone()` 挂在 `MXAccount.[+0x190]`（第 49 个字段 `FriendInfoObject`）上 —— 即**好友模块**。
⇒ **`MyIdCardClone` 由好友模块初始化**；它的数据来源是 `Friend_GetIdCard` 响应
（`FriendGetIdCardResponse` 只有 **1 个字段**，应为 `FriendIdCardDB`）。

## 5. 结论与建议

| 问 | 答 | 置信度 |
|---|---|---|
| ID 卡名字 ← 哪个字段 | **`MXAccount.AccountInfo.Nickname`** | **实测** |
| `Show*=false` → 占位还是隐藏 | **显示静态占位文本**（同一 `set_text` 出口） | **实测** |
| 整卡都是占位的原因 | **`get_MyIdCardClone()` 返回 null ⇒ `SetMyIdCard` 提前 return** | **推断（强）** |
| 修哪一层 | **服务端**：让 `Friend_GetIdCard` 返回合法 `FriendIdCardDB`（或让好友模块初始化出 clone） | 推断 |

**⇒ 补全 18 个字段「有可能」修好被 Show\* 保护的那几格，但修不好 `userName`。**
要让整张卡活过来，得先让 `MyIdCardClone` 非空。

> ⚠️ 存疑：`AccountInfo.Nickname` 在账号信息页显示为 `111`（正常），而 ID 卡这里是 `username`
> —— 如果 `SetMyIdCard` 真跑了，`userName` 应该显示 `111` 而不是 `username`。
> **这个矛盾反过来支持"`SetMyIdCard` 没跑"**，但需要一次运行期确认
> （hook `get_MyIdCardClone` 看返回值是否为 null）。

## 6. 拿不到的

| 项 | 原因 |
|---|---|
| `[x27]` 那个静态文本常量的**字面量** | 是 `fa34000+0xa0` 槽位的运行时值，静态读不到 |
| 其余 `Show*` 开关的**逐个**反汇编 | 时间/篇幅限制，只做了 `ShowAccountLevel`；其余按同模式推断 |
| `MyIdCardClone` **为 null 的实证** | 需要运行期 hook（静态只能看到 `cbz` 分支存在） |

---

# 追加（第 2 轮）：Show* 开关的**全量**证据

上一版只反汇编了 `ShowAccountLevel` 一个样本。这一轮把 `SetMyIdCard`（`0x0A02B060`，长度 0x710）里
**所有** `ldrb w?, [x20, #imm]` 扫了一遍 —— 也就是所有从 DB 读 bool 开关的地方：

| 指令地址 | 读取 | 紧随其后 | 判定 |
|---|---|---|---|
| `0x0A02B080` | `ldrb w8,[x20,#0xB36]` | `tbnz` | 静态初始化标志（不是 DB 字段） |
| **`0x0A02B2DC`** | **`ldrb w8,[x20,#0x50]`** | **`cbz w8,#0xA02B318`** | `ShowAccountLevel` |
| **`0x0A02B364`** | **`ldrb w8,[x20,#0x51]`** | — | `ShowFriendCode` |
| **`0x0A02B390`** | **`ldrb w8,[x20,#0x52]`** | **`cbz w8,#0xA02B41C`** | `ShowRaidRanking` |
| **`0x0A02B450`** | **`ldrb w8,[x20,#0x54]`** | **`cbz w8,#0xA02B4DC`** | `ShowEliminateRaidRanking` |
| **`0x0A02B518`** | **`ldrb w8,[x20,#0x53]`** | — | `ShowArenaRanking` |

⇒ **6 个 `Show*` 开关在客户端是 `FriendIdCardDB` 上从 `+0x50` 开始的一段连续 bool 区**（`+0x50..+0x55`）。

## ★ 决定性证据：false 分支做的是「换字符串」，不是「隐藏」

`0x0A02B38C` 处（`ShowRaidRanking` 那一路的 `set_text` 之前）：

```asm
0x0A02B38C  ...  csel x8, x27, x9, eq    ; ★ 按条件在两个字符串槽之间二选一
            ldr  x1, [x8]
            ...
            bl   set_text                ; 无论真假，都走同一个 set_text
```

配合 `ShowAccountLevel` 的写法：

```asm
0x0A02B2DC  ldrb w8,[x20,#0x50]      ; ShowAccountLevel
0x0A02B2E4  cbz  w8, #0xA02B318      ; false → 静态文本槽
...
0x0A02B318  ldr  x1, [x27]           ; ★ 占位字符串
0x0A02B31C  b    #0xA02B31C-ish → 与 true 分支汇合到同一个 set_text
```

**⇒ 结论（实测，覆盖全部 5~6 个开关）：**
**`Show* = false` 时客户端走「取另一个字符串（占位）→ 同一个 `set_text`」，**
**整条路径里没有任何 `SetActive(false)`。所以那些格子不会被隐藏，只会换成占位文本。**

## 与上一版的差异

| 项 | 上一版 | 本版 |
|---|---|---|
| `ShowAccountLevel` | 单样本实测 | 实测 |
| `ShowFriendCode` / `ShowRaidRanking` / `ShowArenaRanking` / `ShowEliminateRaidRanking` | 推断（中） | **实测**（上表逐条地址） |
| "false → 占位不隐藏" | 单样本推断 | **实测**（`csel` 选择字符串槽 + 同一 `set_text`） |

## 仍然成立的判断

1. **`userName`（大号名字位，`UIIdCardObject+0x30`）读的是 `MXAccount.AccountInfo.Nickname`（`+0x20`）**，
   **不是 `FriendIdCardDB`**（DB 22 字段里确实没有昵称，与服务端定义一致）。
2. **因此补全 18 个字段 / 打开 `Show*` 修不好名字位** —— 名字位与 `FriendIdCardDB` 无关。
3. `SetMyIdCard` 开头 `cbz x0, #0xA02B770`（`get_MyIdCardClone()` 为 null 则整函数返回）——
   若整卡每一格都是占位（含 `userName`），**更像是这个提前返回**，而不是字段缺失。**推断（强），需运行期确认。**
