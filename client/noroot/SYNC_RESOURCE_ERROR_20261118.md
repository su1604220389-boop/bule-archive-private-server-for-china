# 「同步资源信息」失败文案 —— 出处与封禁弹窗触发层（**已订正**）

> 只读。未执行客户端操作、未改任何代码。
> **本文件第 3、4 节已于 2026-11-18 21:29 被真机实测否证并整段替换。**
> 订正依据：lead 真机实测（封禁窗已打通）+ 本机 `work\ba\data\ExcelDB.db` 只读查询。
> 日期：2026-11-18（订正版）

---

## 第 1 节：字符串出处 —— 结论保留：**它不在 APK / metadata / libil2cpp 里**

> **结论：** 我在客户端代码与资源里找不到这句中文，**这个结论是对的**；但它**不等于"这句话不存在"**
> —— 它在**运行时数据表**里。**我上一轮的失败原因不是编码，而是扫描范围**（见下"教训"）。

### 当时实测的搜索矩阵（保留）

| 目标文件 | 大小 | `同步资源信息时失败` | `同步资源信息` | `资源信息时失败` | `同步资源` | UTF-16LE |
|---|---|---|---|---|---|---|
| `global-metadata.dat`（原始，混淆态） | 38,426,024 | ✗ | ✗ | ✗ | ✗ | ✗ |
| `md_deob.bin`（解混淆副本） | 38,426,024 | ✗ | ✗ | ✗ | ✗ | ✗ |
| `libil2cpp.so` | 270,927,056 | ✗ | ✗ | ✗ | ✗ | ✗ |
| APK 全包（41,307 条目，`zipfile` 流式） | 2,127,971,177 | ✗ | — | — | ✗ | ✗ |

方法：metadata 是**每串随机单字节 XOR** 混淆，故对每个候选串做了 **256 个 key 全枚举**；
APK 用流式逐条目扫描，UTF-8 与 UTF-16LE 各一遍。脚本：`report\_tmp\meta\s30_find_str.py`。

### ★ 教训（写在这里防止再犯）

**真正的原因是我扫错了地方，不是编码问题。**
* 我扫的四个目标是 **代码/元数据/资源包**；而 UI 文案在 **Excel 数据表**里。
* 数据表在本机是 `work\ba\data\ExcelDB.db`（**160,534,528 B 的 SQLite**），**它根本不在 APK 里**，
  所以我那四轮扫描**再怎么扫也不可能命中**。
* 文案的确切存放形态：`LocalizeErrorDBSchema(Key INTEGER, Bytes BLOB)`，
  `Bytes` 是一段 **protobuf**，中文是其中最后一个 length-delimited 字段的 UTF-8 负载。
  **它没有加密、没有 XOR** —— 只要扫 `ExcelDB.db` 就能找到。

**⇒ 以后找 UI 文案的第一步应该是 `ExcelDB.db` 的 `Localize*` 系列表，而不是扫 APK。**

---

## 第 2 节：哪个整数索引它 —— 结论保留"未找到"，但**定位方法已在第 3 节给出**

> **结论：** 客户端里确实**没有** `错误码→文案` 的硬编码查表；这张表在数据库里，
> 名为 **`LocalizeErrorDBSchema`**，通过 `ErrorCode` 数值索引（对齐方法见第 3 节）。

### 实测（`work\ba\data\ExcelDB.db`，只读）

```
tables: LocalizeDBSchema, LocalizeErrorDBSchema, LocalizeEtcDBSchema,
        LocalizeSkillDBSchema, LocalizeCharProfileChangeDBSchema,
        LocalizeGachaShopDBSchema, LocalizeCharProfileDBSchema
LocalizeErrorDBSchema: rows = 429, columns = (Key INTEGER, Bytes BLOB)
```

样本（rowid / Key / 从 Bytes 的 protobuf 里抽出的中文）：
```
rowid=1  Key=3205063001  「未找到该助力者。」
rowid=2  Key=3080068811  「无法处理收到的请求。」
rowid=3  Key=1451459100  「无法处理收到的请求。」
```

---

## 第 3 节：**以下为真机否证** —— `Protocol = -1` 能正常解析

> **结论（真机实测）：`Protocol:-1` 完全可以正常解析。我上一轮"`TypeConversion(-1)` 返回 null
> ⇒ 只能弹通用失败"的推断是错的。真正决定弹什么文案的是 `ErrorCode`。**

### 3.1 我上一轮错在哪

我看了 `ProtocolConverter.TypeConversion`（mdef 75291，`0x0DBCD728`）的 `protocol % 99` 跳表 +
`cmp w8,#98 / b.hi → return 0` 守卫，**只凭 `umull` 的无符号语义就推断 `-1` 会被判越界**。
**真机结果：`Protocol:-1` 正常解析，弹窗正常按 `ErrorCode` 显示。**
⇒ 我的推断错在**对 ARM `msub` 取模与后续分支的语义假设**上，且**没有实测就写成"推断（强）"**。
**教训：涉及"会不会走某个分支"的结论，必须真机验证，不能只靠 ISA 语义推演。**

### 3.2 真机实测的错误码对照（2026-11-18 21:29）

| `ErrorCode` | 枚举名（`ProtocolData.cs`） | 客户端表现 | 结论 |
|---|---|---|---|
| **3** | `InvalidSession`（:654） | 弹 **「无效的会话。」** | ✅ 验证通道：说明 `ErrorCode → LocalizeErrorDBSchema` 的通路是通的 |
| **1025** | `AccountLoginError`（:720） | **本地化表里没有这一行** ⇒ 回落兜底「同步资源信息时…。将返回标题画面。」 | ❌ 证伪：1025 不是封禁码 |
| **27000** | **`AccountBanned`**（**:979**） | 弹 **官方封禁窗「账号已被禁止使用，/ 如有任何问题请咨询客服！/ 封禁周期至：」** | ✅ 成功 |

### 3.3 数据库侧交叉验证（本机只读，实测）

`LocalizeErrorDBSchema` **按枚举顺序存放**，与 `ProtocolData.cs` 逐行对齐：

```
idx=166 rowid=167 Key=2211462200  「无法找到保存信息」            ← ContentSaveDBNotFound = 26000（:977）
idx=167 rowid=168 Key=1749817446  「账号已被禁止使用
                                    \n如有任何问题请咨询客服
                                    \n封禁周期至」                ← AccountBanned = 27000（:979）★
idx=168 rowid=169 Key=600902130   「认证服务器拒绝了请求\n将返回标题画面」
idx=169 rowid=170 Key=2441522708  「访问无效\n将返回标题画面」
idx=170 rowid=171 Key=281872164   「进行中的会话信息已存在」
idx=171 rowid=172 Key=3833806126  「实时服务器发送了使用开发功能的请求」
```

* **rowid 167 = 「无法找到保存信息」 ↔ 26000**，**rowid 168 = 封禁三行 ↔ 27000**，
  与 lead 给的 `row167/row168` 编号**逐行吻合**（编号口径 = **rowid**）。
* rowid 168 之后正好接 `28000 ServerNowLoadingProhibitedWord` 起的成员（`:980` 起 6 个）。
* `ProtocolData.cs` 实测：`ContentSaveDBNotFound = 26000`（**:977**）、**`AccountBanned = 27000`（:979）**、
  `ServerNowLoadingProhibitedWord = 28000`（:980）。

### 3.4 关于「时失败」这五个字的核实修正（重要）

**数据库里的原文不是「…时失败」，而是「…时发生错误」。**

`LocalizeErrorDBSchema` 里所有 429 行做中文抽取后搜索：
```
[时失败]   hits=1   idx=26  Key=928524933  「将账号与验证码绑定时失败」（与此无关）
[同步资源] hits=1   idx=292 Key=3944054940 「同步资源信息时发生错误」+「\n将返回标题画面」
[标题画面] hits=15
```

`idx=292 / rowid=293 / Key=3944054940` 的 `Bytes` 完整文本 run：
```
run: '同步资源信息时发生错误'
run: '\n将返回标题画面'
（该 blob 内不存在「失败」两个字）
```

**⇒ 屏幕上真实渲染的两行是「同步资源信息时发生错误 / 将返回标题画面」。**
「同步资源信息时失败」应是转述时的简写；**弹窗链路本身不受影响**，但落盘请以
`rowid=293 / Key=3944054940` 这条为准。

---

## 第 4 节：**以下为真机否证** —— 触发层是 `ErrorCode`，不是包形状，更不是"回错接口"

> **结论（真机实测）：包形状从头到尾没变过，只换 `ErrorCode` 的数值就决定了弹哪个窗。
> "回错接口 / 包形状不对"全部不成立。**

### 4.1 我上一轮的错误结论（已作废）

| 我当时的说法 | 真机结果 |
|---|---|
| `Protocol=-1` 在 `TypeConversion` 里返回 null ⇒ 解不出 DTO | **否证**：正常解析 |
| 因此 `BanReason` 永远读不到 | **否证**：封禁窗已弹出 |
| "可能把封禁包回给了错误的接口" | **否证**：协议名 `Error` / 值 `-1` 本来就是对的 |

### 4.2 真实链路（真机验证）

```
桥 → outer{ "protocol":"Error", "packet":<inner>, "requestid":... }
      inner{ "Protocol": -1, "ServerTimeTicks": ..., "RequestId": ..., "ErrorCode": <N>, ... }
                                    ↓
        客户端按 inner.Protocol(-1) 选错误 DTO（能解析）
                                    ↓
        按 inner.ErrorCode = N 去查 LocalizeErrorDBSchema
                                    ↓
        ┌ 命中 → 弹该行文案
        └ 未命中（如 1025）→ 回落「<当前阶段>时…」+「将返回标题画面」
```

### 4.3 订正后的"必要且充分条件"

**要让封禁窗弹出，只要 `ErrorCode = 27000 (AccountBanned)`。**
与协议名、包形状、RPC 都无关 —— 这三个变量在成功与失败两次实验里**完全相同**。

### 4.4 仍然成立的一条（来自 metadata，未被否证）

`ErrorPacket`（type[10777]）= `{Reason, ErrorCode}`；`AccountBanErrorPacket`（type[10780]）= `{BanReason}`，
且后者**有 `get_ErrorCode` ⇒ 继承前者**。真机现象表明客户端在 `ErrorCode=27000` 这条路上读的是
**`ErrorPacket.Reason`**，所以日期串必须**同时**挂在 `BanReason` 与 `Reason` 两个字段上
（详见 `work\ba\plan\20261118\BAN_POPUP_SOLVED.md`）。

---

## 摘要（订正后）

1. 「同步资源信息…」这句**不在客户端代码/资源包**里，在 `ExcelDB.db` 的 `LocalizeErrorDBSchema`
   （429 行，`Key`/`Bytes`，`Bytes` 是 protobuf）—— 我当初没扫这个文件，这是**范围错误**，不是编码问题。
2. **`Protocol:-1` 能正常解析**（真机否证我第 3 节的推断）。
3. **`ErrorCode` 决定文案**：`3`→「无效的会话」；`1025`→表里没有→回落兜底；**`27000`→官方封禁窗 ✅**。
4. 包形状/协议名/接口**都不是变量**，唯一变量是 `ErrorCode` 的数值。
