# § 邮件接口容量实测（GM「一键发放全部记忆大厅」可行性）

- 时间：2026-11-19 23:36–23:40（Asia/Shanghai）｜ 执行：srv-ops
- 通道：`POST /api/admin/mail/send`（`X-Admin-Key`）
- 测试账号：**`AccountServerId = 4`**（Nickname `222`，PublisherAccountId `854071516`）
- 允许的写操作范围：仅向该测试账号发信；**未改数据库、未改代码、未重启任何服务**

## 一句话结论

**一封邮件可以挂下全部 258 个记忆大厅包裹（一次成功）**；实测到 **1000 个包裹 / 51 KB 请求体仍是 200**，
没有看到包裹数上限。`Parcels[].Type` **必须用字符串 `"MemoryLobby"`**（数字 `8` 会被 400 拒绝）。

---

## 1. 测试账号确认

```
ServerId  Nickname  PublisherAccountId  Level  State
1         Schale                        90     1
4         222       854071516           90     1     ← 本测试使用的账号
11                  314816420           90     1
12                  719052711           90     1
```

## 2. Mails 表结构（实际 schema）

```sql
CREATE TABLE IF NOT EXISTS "Mails" (
    "ServerId" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    "AccountServerId" INTEGER NOT NULL,
    "Type" INTEGER NOT NULL,
    "UniqueId" INTEGER NOT NULL,
    "Sender" TEXT NOT NULL,
    "Comment" TEXT NOT NULL,
    "LocalizedSender" TEXT NOT NULL,
    "LocalizedComment" TEXT NOT NULL,
    "SendDate" TEXT NOT NULL,
    "ReceiptDate" TEXT NULL,
    "ExpireDate" TEXT NULL,
    "ParcelInfos" TEXT NULL,
    "RemainParcelInfos" TEXT NULL,
    "IsRefresher" INTEGER NOT NULL
);
CREATE INDEX "IX_Mails_AccountServerId" ON "Mails" ("AccountServerId");
```
（列名是 `ServerId`，不是 `Id`；包裹存在 `ParcelInfos` 的 JSON 字符串里。）

## 3. 逐步实测（每步均为实际响应原文）

发信前 `Mails` 行数 = **21**。

### A) 1 个包裹，`Type="MemoryLobby"`（字符串）
```
请求体 161 B ｜ HTTP 200
响应 = {"success":true,"message":"Mail sent successfully"}
```
落库：`ServerId=128`，`ParcelInfos` 128 B：
```json
[{"Key":{"Type":8,"Id":13010},"Amount":1,"Multiplier":{"rawValue":10000},"MultipliedAmount":1,"Probability":{"rawValue":10000}}]
```

### B) 1 个包裹，`Type=8`（数字）
```
请求体 146 B ｜ HTTP **400**
响应 = {"type":"https://tools.ietf.org/html/rfc9110#section-15.5.1",
        "title":"One or more validation errors occurred.","status":400,
        "errors":{"$.Parcels[0].Type":["The JSON value could not be converted to System.String.
                  Path: $.Parcels[0].Type | LineNumber: 0 | BytePositionInLine: 117."]},
        "traceId":"00-96dd18cb2624edca377c87054e403f5e-512369bfa5f27f13-00"}
```
⇒ **`Type` 的类型是 `System.String`（字符串枚举名）**；服务端内部再转成数字 `8` 存库。

### C) 60 个包裹（`Type="MemoryLobby"`）
```
请求体 3,155 B ｜ HTTP 200
响应 = {"success":true,"message":"Mail sent successfully"}
```
落库：`ServerId=129`，60 个包裹，ParcelInfos 7,621 B。

### D) **258 个包裹（全量大厅，onerequest）**
```
请求体 13,264 B ｜ HTTP 200
响应 = {"success":true,"message":"Mail sent successfully"}
```
落库：`ServerId=130`，**258 个包裹**，ParcelInfos 32,777 B。

### E) 500 个包裹（重复 id，仅测容量）
```
请求体 25,629 B ｜ HTTP 200
响应 = {"success":true,"message":"Mail sent successfully"}
```

### F) 1000 个包裹（重复 id，仅测容量）
```
请求体 51,150 B ｜ HTTP 200
响应 = {"success":true,"message":"Mail sent successfully"}
```
⇒ **包裹数上限在本测试范围内未触到**（1000 个仍成功）；请求体 51 KB 远低于 Kestrel 默认 30 MB 限制。
（真实产品只需要 258 个，一封就够。）

## 4. `Type` 写法结论

| 写法 | 结果 |
|---|---|
| `"Type": "MemoryLobby"`（字符串） | **200 成功**，落库 `Key.Type = 8` |
| `"Type": 8`（数字） | **400** —— `The JSON value could not be converted to System.String` |

**⇒ 必须用字符串枚举名**（`MemoryLobby`）。面板 `mail.php` 里既有的 `parcels[{"type":"Item","id":…}]` 也是同一风格。

## 5. 落库正确性核对（5 封测试邮件）

```
Id=128  测试：记忆大厅 A 单个-字符串Type        包裹=1     唯一Id=1   KeyType={8}  Amount集合={1}
Id=129  测试：记忆大厅 C 60个                 包裹=60    唯一Id=60  KeyType={8}  Amount集合={1}
Id=130  测试：记忆大厅 D 258个                包裹=258   唯一Id=258 KeyType={8}  Amount集合={1}  ← 唯一 Id 集合与 258 清单完全一致
Id=131  测试：记忆大厅 F 500个(重复id 容量测试)   包裹=500   唯一Id=258 KeyType={8}  Amount集合={1}
Id=132  测试：记忆大厅 G 1000个(重复id 容量测试)  包裹=1000  唯一Id=258 KeyType={8}  Amount集合={1}
```
- 每封 `Sender=GM`、`Comment` 见上表、`SendDate` 为发送时刻，`ReceiptDate`/`ExpireDate` 为 NULL，`RemainParcelInfos=[]`。
- `ParcelInfos` 是合法 JSON 数组，元素结构 `{"Key":{"Type":8,"Id":<大厅id>},"Amount":1,"Multiplier":…,"MultipliedAmount":1,"Probability":…}`。
- **Id 全部是真实客户端大厅 id**（10000–10098 / 10100–10136 / 13000–13014 / 16000–16019 / 20000–20056 / 23000–23008 / 26000–26015 + 5 个特殊 id），`Amount=1`。

## 6. 测试产生的邮件（供用户删/领）

| ServerId | Comment | 包裹数 | 说明 |
|---|---|---|---|
| **128** | 测试：记忆大厅 A 单个-字符串Type | 1 | 单包裹验证 |
| **129** | 测试：记忆大厅 C 60个 | 60 | 中等批量 |
| **130** | 测试：记忆大厅 D 258个 | **258** | **全量，可作为正式功能形态** |
| **131** | 测试：记忆大厅 F 500个(重复id 容量测试) | 500（重复 258 个 id） | 仅容量测试，建议删除 |
| **132** | 测试：记忆大厅 G 1000个(重复id 容量测试) | 1000（重复 258 个 id） | 仅容量测试，建议删除 |

> 全部发给 `AccountServerId=4`，未领取（`ReceiptDate` 为空）。建议保留 130（或删除后由 GM 按钮重发），删除 131/132。

## 7. 对「一键发放全部记忆大厅」的实现建议（实测支撑）

1. **一封邮件即可**：258 个 `{"Type":"MemoryLobby","Id":<id>,"Amount":1}` 一次性 POST，13 KB 请求体，200。
2. `Type` 用字符串 `"MemoryLobby"`；`Amount` 用 1。
3. 面板侧无需分批；若将来大厅数量大增（>1000）再考虑分封。
4. 建议 GM 按钮带 `Comment` 模板（如 `记忆大厅全量发放`）+ 二次确认，避免误发。

---
**本次仅执行 `POST /api/admin/mail/send`（5 次，全部发往 AccountServerId=4）；未改数据库、未改代码、未重启服务。**
