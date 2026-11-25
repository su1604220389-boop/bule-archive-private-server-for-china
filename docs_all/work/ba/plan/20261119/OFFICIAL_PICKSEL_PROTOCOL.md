# 官方抓包里 10014 / 10015 到底怎么回 —— 只读取证报告

- 取证时间：2026-11-19 01:5x
- 方式：**纯本地只读**。未联网、未连服务器、未改动任何已有文件；本报告是本轮唯一新建文件。
- 数据源（全部只读）：
  1. `report/_tmp/official_decoded_201/`（Reqable HAR `official201.har` 解码，`_summary.json` 记 `n_entries=201`、`game_api=109`、`error_entries=0`）
  2. `work/ba/proto/dto_schema_full_v2.json`（2,370,325 B，99,944 行）
  3. `work/ba/srv_src/Schale/MX/NetworkProtocol/{NetworkProtocol.cs, Packet.cs, ProtocolData.cs}`
  4. `work/ba/srv_src/Shittim-Server/Controllers/Api/GatewayController.cs`、`Core/NetworkProtocol/Handlers/ShopHandler.cs`
  5. 旁证（父 agent 已产出，仅引用不修改）：`PICKSEL_LIVE_TRACE.md`

---

## 0. 一句话结论

**官方抓包里没有 10014，也没有 10015。** 整个 Shop 家族在这份抓包里只出现过 **10002 `Shop_List` 一条**，
gacha 段（10001/10003/10006/10008/10014/10015/10016）**一条都没有**。
所以「官方怎么回 10015」在这份材料里**无法直接观测**。

但抓包给出了等价的替代证据：官方对「响应体没有任何自有字段」的协议，回的是一个**严格的 5 字段信封**
（17 个实例，见 §5）。那个形状里**确认没有任何回显字段**，`PickupCharacterSelection` 一定不在其中 ——
这与 DTO 只有 `Protocol` 的结论**互相印证**，所以「加回显」这条路可以**彻底判死**，不是"应该无效"而是"字段根本不存在"。

同时**推翻了本项目源码里一条错误注释**：`GatewayController.cs:264` 声称官方只对 4 个握手协议回显 `SessionKey`。
实测这份抓包 **109/109 条响应全部带 `SessionKey`**，包括最普通的 `Clan_Check` / `Friend_Check`。

---

## 1. 官方抓包里有没有 10014 / 10015？

### 结论：**没有。两个都没有。** 逐条可复核。

抓包 227 个文件（109 对 request/response + 9 个非 API 文件）。解析全部 109 条响应的
`inner.Protocol` 与 109 条请求的 `json.Protocol`，得到**去重后 38 个协议号**，全量清单：

```
3      1002   1005   1017   4000   5000   5001   6000   6020   6021
7000   7001   7003   8000   8002   8006   10002  15002  16000  20001
20013  22000  22004  22008  22009  22016  24000  25003  26000  28000
28019  29002  30041  35003  36001  43010  90004  90009
```

**判定表：**

| 协议号 | 协议名 | 抓包内 |
|---|---|---|
| 10002 | `Shop_List` | ✅ 有（1 对） |
| 10001 `Shop_BuyGacha` / 10003 `Shop_Refresh` / 10006 `Shop_GachaRecruitList` / 10008 `Shop_BuyGacha3` | — | ❌ 无 |
| 10010 `Shop_BeforehandGachaGet` … 10013 `Shop_BeforehandGachaPick` | — | ❌ 无 |
| **10014** | **`Shop_PickupSelectionGachaGet`** | ❌ **无** |
| **10015** | **`Shop_PickupSelectionGachaSet`** | ❌ **无** |
| 10016 | `Shop_PickupSelectionGachaBuy` | ❌ 无 |

**补充证据（排除"数字串巧合"）**：直接字符串搜 `10014` / `10015` 确实有命中，但**全部是巧合**，逐条核对为：
- `"AccountServerId": 10015354380` / `"AccountId": 10015354380`（**账号 id** 恰好以 10015 开头）
- `96_24000_api_academy_getinfo.response.json:684: "UniqueId": 10015`、`:94` 里有 `"UniqueId": 10014`
  —— 这是**角色 UniqueId**（学园拜访角色），不是协议号
- 其余命中都是 `10002`/`20001` 等协议号自身的长串，以及 `100153543801` 这类 Cafe DB id

也就是说：**没有任何一条报文的 `Protocol` 字段等于 10014 或 10015。**

### 1.1 为什么抓不到（这决定了后续该怎么补证据）

`_summary.json` 显示这份 HAR 是 **Reqable 抓的一次真实会话**（201 entries，0 错误）。
实际出现的 Shop 报文只有 `Shop_List`（cat 38），配合 `Campaign_List`、`Arena_*`、`Cafe_*`、`Mail_*` 等。
**这次会话从来没有打开过「选择成员」/抽卡界面**，所以 gacha 段协议一条都不会出现。
→ 这是**采样盲区，不是"官方不实现"**。

**要拿到 10014/10015 的官方形状，只能**：在官方环境下打开一个**真正开着「选择成员」pickup 卡池**的号，
进入该卡池并点一次选择，重新抓 HAR。用国服号 + 当前开放卡池是唯一途径；本次材料无法替代。

---

## 2. 四个 DTO 的完整定义

**先纠正一个前提**：任务里列的 4 个 DTO，`dto_schema_full_v2.json` 里**只有 3 个**——
两个 `*Request` **在 schema 里根本不存在**。全 schema 中 key 含 `Pickup` 的**仅 4 个**：

```
PickupFirstGetHistoryDB
ShopPickupSelectionGachaBuyResponse
ShopPickupSelectionGachaGetResponse
ShopPickupSelectionGachaSetResponse
```

按 `protocol ∈ {10013..10016}` 全量筛（证明不是名字写错）：

```
ShopBeforehandGachaPickResponse      10013  Shop_BeforehandGachaPick        ownFields=2
ShopPickupSelectionGachaGetResponse  10014  Shop_PickupSelectionGachaGet   ownFields=1
ShopPickupSelectionGachaSetResponse  10015  Shop_PickupSelectionGachaSet   ownFields=0
ShopPickupSelectionGachaBuyResponse  10016  Shop_PickupSelectionGachaBuy   ownFields=0
```

对比：别的协议的 `*Request` 在 schema 里是有的（如 `AcademyGetInfoRequest`），
所以 **`ShopPickupSelectionGachaGetRequest` / `...SetRequest` 的缺失是真实的缺失**（客户端 metadata 侧未收录），
不是我的检索漏了。

### 2.1 `ShopPickupSelectionGachaGetResponse`（protocol 10014）

`schema` 原文（第 92407–92555 行），自有字段**只有 1 个**：

```json
"ShopPickupSelectionGachaGetResponse": {
  "base": "ResponsePacket",
  "baseChain": ["BasePacket", "ResponsePacket"],
  "envelope": { "Protocol": 10014 },
  "fieldCount": 1,
  "fields": [
    {
      "conf": "high",
      "kind": "dict",
      "name": "PickupCharacterSelection",
      "src": "vote(17,1.00)",
      "ti": 10683,
      "type": "Dictionary<long,long>"
    }
  ],
  "namespace": "MX.NetworkProtocol",
  "protocol": 10014,
  "protocolName": "Shop_PickupSelectionGachaGet",
  "referenced": ["Dictionary"],
  "segment": 10,
  "tdIndex": 11567,
  "wireFieldCount": 10
}
```

`wireFields` 里 `PickupCharacterSelection` 是 `"source": "own"`（自有），**与同名继承字段并存**：
它在 `wireFields` 中出现在 `StaticOpenConditions` 之后，`"source": "own"`。

### 2.2 `ShopPickupSelectionGachaSetResponse`（protocol 10015）—— 关键

`schema` 原文（第 92557–92575 + `wireFields`）：

```json
"ShopPickupSelectionGachaSetResponse": {
  "base": "ResponsePacket",
  "baseChain": ["BasePacket", "ResponsePacket"],
  "envelope": { "Protocol": 10015 },
  "fieldCount": 0,
  "fields": [],
  "namespace": "MX.NetworkProtocol",
  "protocol": 10015,
  "protocolName": "Shop_PickupSelectionGachaSet",
  "referenced": [],
  "segment": 10,
  "tdIndex": 11569,
  "wireFieldCount": 9
}
```

⇒ **`fieldCount = 0`，`fields = []`。自有字段一个都没有。** 任务描述的这个前提**成立**。
与 10014 的 `wireFieldCount=10` 相比正好少 1 —— 少的那个就是 `PickupCharacterSelection`。

`wireFields` 的 9 个全部是 `"inherited": true`：
`Protocol`、`SessionKey`、`OSType`、`ServerTimeTicks`、`ServerNotification`、
`MissionProgressDBs`、`EventMissionProgressDBDict`、`BattlePassMissionProgressDBDict`、`StaticOpenConditions`
（后 4 个在 request 里不出现，响应侧按默认 `Ignore` 省略）。

### 2.3 两个 Request —— schema 里没有，只能看服务端 C# 定义

`work/ba/srv_src/Schale/MX/NetworkProtocol/NetworkProtocol.cs:6768-6790`（原文）：

```csharp
public class ShopPickupSelectionGachaGetRequest : RequestPacket
{
    public override Protocol Protocol { get => Protocol.Shop_PickupSelectionGachaGet; }
    public long ShopRecruitId { get; set; }
}

public class ShopPickupSelectionGachaGetResponse : ResponsePacket
{
    public override Protocol Protocol { get => Protocol.Shop_PickupSelectionGachaGet; }
    public Dictionary<long, long>? PickupCharacterSelection { get; set; }
}

public class ShopPickupSelectionGachaSetRequest : RequestPacket
{
    public override Protocol Protocol { get => Protocol.Shop_PickupSelectionGachaSet; }
    public long ShopRecruitID { get; set; }                      // 注意：大写 ID
    public Dictionary<long, long>? PickupCharacterSelection { get; set; }
}

public class ShopPickupSelectionGachaSetResponse : ResponsePacket
{
    public override Protocol Protocol { get => Protocol.Shop_PickupSelectionGachaSet; }
    // 空 —— 无任何自有字段
}
```

**可空性**：两个 `PickupCharacterSelection` 都是 `Dictionary<long, long>?`（**可空**）。
`ShopRecruitId` / `ShopRecruitID` 是 `long`（值类型，不可空）。
⚠️ 注意 Get 用 `ShopRecruitId`、Set 用 `ShopRecruitID`，**大小写不一致**。JSON.NET 反序列化默认大小写不敏感，
所以线上两条都能绑上；但这是隐患，见 §6 建议。

### 2.4 `PickupCharacterSelection` 的类型 / key 语义

- **类型：确定是 `Dictionary<long,long>`**，不是 `Dictionary<int,int>`、不是 `List<long>`、不是 `List<xxxDB>`。
  三处独立佐证：schema `"type": "Dictionary<long,long>"` / `"ti": 10683` / `"referenced": ["Dictionary"]`；
  C# `Dictionary<long, long>?`；schema 中该字段 `"kind": "dict"`。
- **JSON 形状**：JSON 对象的 key **必然是字符串**（`long` 键序列化成数字字符串）。
  所以线上一定是 `{"<数字字符串>": <数字>}`，例如 `{"1":10014}`。
- **key / value 语义**：**key = 槽位序号（从 1 开始），value = 角色 UniqueId**。
  依据（本地实测 + 官方旁证）：
  1. 客户端实发载荷是 `{"1":10014}`、`{"1":20009}`（`PICKSEL_LIVE_TRACE.md` §3/§6.2），
     一个槽位只放一个角色，key 取 1 而不是角色 id，说明 key 是**位置/槽位**。
  2. `10014` 和 `20009` **确实是角色 UniqueId** —— 它们在官方抓包
     `01_24000_api_academy_getinfo.response.json` / `96_...` 里以 `"UniqueId": 10014` / `"UniqueId": 20009`
     的形式出现（学园拜访角色）。⇒ **value = 角色 id** 有官方侧硬证据。
  3. `Dictionary<long,long>` 而非 `List<long>` 说明客户端要按 key 做**随机访问**（读第 N 槽选了谁），
     这与「槽位 → 角色」的模型一致；若 key 是角色 id，字典就没有存在意义（直接 List 即可）。
  ⚠️ 诚实边界：**没有官方 10014 响应可以验证这个语义**，"槽位序号"是从客户端载荷 + 类型形状**推断**的，
  不是官方抓包直接观测。§5.3 说明为什么这个推断足够可靠。

### 2.5 其它名字带 `Pickup` 的 DTO

```
PickupFirstGetHistoryDB            （普通 DB 模型，非协议根）
  fields: ShopRecruitId (long), LogDate (DateTime)
```

官方抓包里**唯一**出现的 pickup 数据就是它 —— 在账号同步 `02_1017_api_account_loginsync.response.json`，
真实形状（原样）：

```json
"PickupFirstGetHistoryDBs": [{"ShopRecruitId": 5004170, "LogDate": "2026-08-10T13:52:19.949"}]
```

⇒ 官方 `ShopRecruitId` 用的是**真实卡池 id（5004170 这种 7 位数字）**，
而本项目线上探测到客户端上传的是 **`90000000`**（哨兵档期）。这条差异独立于 10015，但对
§6 的排查有参考价值：`90000000` 在客户端本地 FlatData 里大概率没有对应 `ShopRecruitExcel` 行。

`ShopPickupSelectionGachaBuy`（10016）继承 `ShopBuyGacha3Response`，
其 `PickupFirstGetHistoryDBs`（`List<PickupFirstGetHistoryDB>`）是**继承来的**，与 `PickupCharacterSelection` 无关。

---

## 3. grep `PickupCharacterSelection` / `PickupSelection`

### 结论：**官方抓包里 0 命中。任何大小写都 0。**

对 `report/_tmp/official_decoded_201/` 下全部 227 个文件做**大小写不敏感**全文本搜索
（正则 `pickupselection|pickupcharacterselection`）与 JSON 结构级搜索（遍历所有 key）：

```
=== raw string PickupSelection / PickupCharacterSelection (case-insens) ===
（空）
=== JSON key 级：所有含 'pickup' 的 key ===
  仅 1 个：PickupFirstGetHistoryDBs
  仅 1 个文件：02_1017_api_account_loginsync.response.json
```

命中的**全部内容**就是 §2.5 那句：

```
02_1017_api_account_loginsync.response.json
  "PickupFirstGetHistoryDBs": [{"ShopRecruitId": 5004170, "LogDate": "2026-08-10T13:52:19.949"}]
```

`PickupSelection` / `PickupCharacterSelection` **连一个字符都没出现**。
（`ShopPickupSelectionGacha` 前缀自然也是 0 —— 因为连 10014/10015 报文都不存在。）

---

## 4. grep `ServerNotification` —— 全量取值分布

### 4.1 distinct 值 + 出现次数（分母 = 109 条响应）

```
值      出现次数
0       87
3       2
4       1
8       10
1024    1
2048    8
------------
合计 109，distinct = 6
```

补充：**`ServerNotification` 字段本身 109/109 条响应都存在**，值为 0 时也照样显式输出（不是省略）。

### 4.2 按协议拆开看（这是最有信息量的一张表）

| 值 | 协议号 | 协议名 | 次数 |
|---|---|---|---|
| **0** | 3/1002/1005/1017/4000/5000/5001/6000/6020/6021/7003/8000/8006/10002/15002/16000/20001/22000/22008/22009/22016/24000/25003/26000/29002/30041/35003/36001×10/43010×8/90004×10/90009×2 | 绝大多数 | **87** |
| **8** | 7000 `Mail_List` ×1 ｜ 7001 `Mail_Check` ×9 | **只有邮件协议** | **10** |
| **2048** | 28019 `Clan_Check` ×8 | 只有公会签到 | 8 |
| **1024** | 20013 `Cafe_ReceiveCurrency` ×1 | 只有咖啡馆领币 | 1 |
| **4** | 28000 `Clan_Lobby` ×1 | 只有公会大厅 | 1 |
| **3** | 8002 `Mission_MultipleReward` ×1 ｜ 22004 `Arena_EnterBattle` ×1 | 任务倍率 / 竞技场进战 | 2 |

### 4.3 这个字段是什么（本地源码给出枚举值表）

`work/ba/srv_src/Schale/MX/NetworkProtocol/ProtocolData.cs:521-540`（原文）：

```csharp
public enum ServerNotificationFlag : int
{
    None = 0,
    NewMailArrived = 4,
    HasUnreadMail = 8,
    NewToastDetected = 16,
    CanReceiveArenaDailyReward = 32,
    CanReceiveRaidReward = 64,
    ServerMaintenance = 256,
    CannotReceiveMail = 512,
    InventoryFullRewardMail = 1024,
    CanReceiveClanAttendanceReward = 2048,
    HasClanApplicant = 4096,
    HasFriendRequest = 8192,
    CheckConquest = 16384,
    CanReceiveEliminateRaidReward = 32768,
    CanReceiveMultiFloorRaidReward = 65536,
    CanReceiveProductDailyRecordReward = 131072,
    HasUnreadSemiPermanentMail = 262144,
}
```

⇒ **`8 = HasUnreadMail`（有未读邮件）**。
DTO 侧类型也印证：`dto_schema_full_v2.json` 里 `ServerNotification` 的 `"type": "ServerNotificationFlag"`、
`"kind": "enum"`（schema 中 `ServerNotificationFlag` 这个 DTO 自身 `fieldCount=0`，值表未收录，
所以**值表来源是本地 C# 源码，不是官方 metadata** —— 但下面 4.4 的实测吻合度极高，可以采信）。

### 4.4 「有没有出现过 8」→ **出现过，10 次，但只在邮件协议上**

这是本题的重点，必须说清楚：

- **8 确实在官方抓包里出现了 10 次** ⇒ **`ServerNotification=8` 本身不是非法值/毒值**，
  "客户端看到 8 就崩"这种假设不成立。
- 但这 10 次**全部**落在 `Mail_Check`(7001, 9 次) 与 `Mail_List`(7000, 1 次) 上。
  ⇒ 在这份抓包里，官方**不是**把 `HasUnreadMail` 当作"每个响应都盖一遍的全局基线"，
  而是**只在邮件语义相关的协议上盖这个位**。
  同一时刻的 `Shop_List`(10002)、`Account_LoginSync`(1017)、`Mail_ListSemiPermanent`(7003)、
  `Clan_Check`(28019) 等等都是 0 或各自的位。
- 枚举值表交叉验证，全部自洽：
  `28019 Clan_Check → 2048 = CanReceiveClanAttendanceReward` ✅
  `20013 Cafe_ReceiveCurrency → 1024 = InventoryFullRewardMail` ✅
  `28000 Clan_Lobby → 4 = NewMailArrived` ✅
  `7000/7001 → 8 = HasUnreadMail` ✅
  ⇒ 值表可信。
- ⚠️ 遗留异常：**`3` 里的 bit 0/1 在本地枚举表中没有命名**（`3 = 1|2`）。它出现在
  `8002 Mission_MultipleReward` 与 `22004 Arena_EnterBattle`，说明本地这份枚举表**不完整**
  （至少缺 `1`、`2` 两个低位）。这不影响 `8` 的结论。

---

## 5. 官方对「零自有字段响应」到底回什么（本题最有价值的替代证据）

抓包里没有 10015，但抓包里有 17 条**响应体只有信封、没有任何协议自有字段**的响应
（`Clan_Check` 28019 ×8、`Friend_Check` 43010 ×8、`Mail_ListSemiPermanent` 7003 ×1）。
这正是 10015 的等价形态 —— 10015 的自有字段数就是 0。

### 5.1 官方「最裸 ACK」的完整明文（逐字节，原样）

```json
{"protocol":"Friend_Check","packet":"{\"Protocol\":43010,\"SessionKey\":{\"AccountServerId\":10015354380,\"MxToken\":\"Vji5A/Cy6X2enQZKeYgrjxAC8MoRDOCT2Tb1SW13PcZTq2cnyCPPdd81pGbzYBKA\"},\"ServerTimeTicks\":639304002588409455,\"ServerNotification\":0,\"RequestId\":\"8a897674-e64a-4b50-a6ae-d0f3311a8f16\"}","requestid":"8a897674-e64a-4b50-a6ae-d0f3311a8f16"}
```

解包后的 packet 本体：

```json
{"Protocol":43010,
 "SessionKey":{"AccountServerId":10015354380,"MxToken":"Vji5A/Cy6X2enQZKeYgrjxAC8MoRDOCT2Tb1SW13PcZTq2cnyCPPdd81pGbzYBKA"},
 "ServerTimeTicks":639304002588409455,
 "ServerNotification":0,
 "RequestId":"8a897674-e64a-4b50-a6ae-d0f3311a8f16"}
```

`Clan_Check` 版本同形，只是值不同：

```json
{"Protocol":28019,
 "SessionKey":{"AccountServerId":10015354380,"MxToken":"Vji5A/Cy6X2enQZKeYgrjxAC8MoRDOCT2Tb1SW13PcZTq2cnyCPPdd81pGbzYBKA"},
 "ServerTimeTicks":639304004547664628,
 "ServerNotification":2048,
 "RequestId":"aae212f1-536f-4536-baf8-837d34ba6551"}
```

### 5.2 信封的严格统计（109 条响应全量）

| 字段 | 出现次数 | 说明 |
|---|---|---|
| `Protocol` | **109/109** | |
| `ServerTimeTicks` | **109/109** | 官方值为秒级截断（末尾 `0000000` 或近乎） |
| `ServerNotification` | **109/109** | 值为 0 也显式输出 |
| `RequestId` | **109/109** | 36 字符小写带连字符 GUID |
| `SessionKey` | **109/109** | `{AccountServerId, MxToken}`，**每条都回显** |
| `AccountId` | **0/109** | **官方响应里一次都没出现** |

⇒ 官方零字段响应的形状 = **恰好这 5 个字段，一个不多、一个不少**。

### 5.3 由此得到三条硬结论

**(1) 「加回显」彻底不可行 —— 不是"可能无效"，是字段不存在。**
官方最裸 ACK 里没有任何协议自有字段；10015 的 DTO 自有字段数为 0。
客户端对这个响应的反序列化目标类型里**没有** `PickupCharacterSelection` 这个属性，
塞进去只会被当作未知 JSON 属性忽略（JSON.NET 默认 `MissingMemberHandling.Ignore`）。
⇒ **`ShopPickupSelectionGachaSetResponse` 无论官方还是我方，都不可能携带选择内容。**
这也顺带证明了 `PICKSEL_LIVE_TRACE.md §7` 提的"最小修法方向（响应补 PickupCharacterSelection）"
**不可能生效** —— 那条建议应当作废。

**(2) 我方的 3 字段 ACK 与官方 5 字段 ACK 的差异是 `SessionKey` + `RequestId`。**
我方线上实际回的是：

```json
{"protocol":"Shop_PickupSelectionGachaSet","packet":"{\"Protocol\":10015,\"ServerTimeTicks\":639306495160000000,\"ServerNotification\":8}"}
```

差的正是这两个。`RequestId` 全项目 C# 源码里**一次都没实现**（`grep RequestId *.cs` → 0 命中），
而其它协议（Mail_Check / Clan_Check / Shop_List …）同样没有 `RequestId` 却工作正常 ⇒
**`RequestId` 基本可以排除**为直接病因。
`SessionKey` 则是被 `GatewayController.ShouldEchoSessionKey()` 的白名单挡掉的，见下条。

**(3) 项目源码里有一条与官方抓包冲突的注释，必须记下来。**

`GatewayController.cs:264` 原文：

> `// Official responses echo SessionKey plus the derived top-level AccountId ONLY on the account/security handshake protocols; every other response omits both. Handlers that mint a new session (CheckNexon/Create) set SessionKey themselves.`

`GatewayController.cs:320-325` 原文：

> `// Protocols whose responses officially carry SessionKey/AccountId, from live captures: Account_CheckNexon, Account_Auth, ProofToken_RequestQuestion, ProofToken_Submit.`
> `private static bool ShouldEchoSessionKey(Protocol protocol) => protocol is Protocol.Account_Auth or Protocol.Account_Auth2 or Protocol.ProofToken_RequestQuestion or Protocol.ProofToken_Submit;`

**这份抓包（109 条）与此注释直接冲突**：`SessionKey` 是 **109/109 全带**，
`AccountId` 是 **0/109 全不带**。也就是说：
- 「只对握手协议回显 SessionKey」→ **错**；普通 `Clan_Check` / `Friend_Check` / `Shop_List` 全都有。
- 「AccountId 也一起回显」→ **错**；官方响应 `AccountId` 出现 0 次
  （`BasePacket.AccountId` 派生属性在 `SessionKey != null` 时会算出非 0 值并**被序列化出来**，
  这与官方不一致 —— 属于潜在多余字段，但目前看客户端不介意）。

由于我方 `SessionKey` 在**所有非握手响应**上都缺失，而其它协议客户端能用，
所以**单凭 `SessionKey` 缺失不能解释 39 次重试**。但它是 10015 ACK 与官方 ACK 之间**唯一实质形状差异**，
且改动极小、零风险，值得作为第一个 A/B 实验去排除。见 §6。

---

## 6. 关于「39 次重试」—— 本报告能证实什么、不能证实什么

**必须诚实说明：这份抓包无法解释 39 次重试，因为它压根没有 10014/10015 的官方样本可比。**

以下是基于本轮证据的**推断**（明确标记为推断，非观测）：

### 6.1 已被证据**排除**的方向

| 假设 | 判定 | 证据 |
|---|---|---|
| 响应缺 `PickupCharacterSelection` 回显 | ❌ **排除** | 双方 DTO 均无此字段（§2.2 / §5.3(1)），塞了也被忽略 |
| 响应缺 `ShopRecruitID` 回显 | ❌ **排除** | 同上，DTO 无此字段 |
| `ServerNotification=8` 是非法值导致客户端崩 | ❌ **排除** | 官方抓包里 8 出现 10 次（§4.1） |
| 响应缺 `RequestId` | 🟡 **基本排除** | 全项目 C# 从未实现 `RequestId`，其它协议同缺却正常（§5.3(2)） |
| 服务端 500 / 异常 / 超时 | ❌ **排除** | `PICKSEL_LIVE_TRACE.md`：39 次全 200、0 异常、0 非 200 |

### 6.2 仍然**存活**的候选（按可疑度排序，附可证伪的检验方法）

1. **`SessionKey` 未回显**（唯一实质形状差异，改动最小）
   - 依据：官方 109/109 带；我方 ACK 3 字段不带；`ShouldEchoSessionKey` 白名单不含 10015。
   - 检验：把 10015（或全部业务响应）加入回显，看重试是否消失。**零风险、可秒回滚。**
   - 反证提醒：其它协议同样缺 `SessionKey` 却正常 ⇒ 单这一条**可能不够**。

2. **`ServerNotification=8` 出现在非邮件协议上**（我方 `ReadServerNotificationAsync` 的全局基线策略）
   - 依据：官方抓包里 8 **只**出现在 `Mail_Check`/`Mail_List`（§4.2）；我方却在 10015 上盖了 8。
   - 若客户端在收到 `HasUnreadMail` 后触发邮件/红点重同步，与「选择成员」的完成条件相互干扰，
     理论上可能把一个"已成功"的 Set 变成"未完成"。此为本轮**最值得实测**的行为差异。
   - 检验：让 10015 回 `ServerNotification: 0`，观察重试次数。

3. **`ShopRecruitID = 90000000` 在客户端本地 FlatData 中不存在**
   - 依据：官方 `PickupFirstGetHistoryDB` 里的 `ShopRecruitId` 是真实 7 位卡池 id（`5004170`）；
     我方客户端上传恒为哨兵值 `90000000`（`PICKSEL_LIVE_TRACE.md` §3/§6.2）。
   - 若客户端在 Set 成功后要做「按 ShopRecruitExcel 查这个池子」的本地校验，查不到就可能不结束 loading。
   - 检验：给「选择成员」配一个**真实 id 的卡池**（对齐官方 id 段），再看是否还重试。
     注意：这需要改数据/配置，超出本轮只读范围。

4. **客户端 `Hash` / `Resendable` 重发机制**（机制性解释，非可修 bug）
   - 依据：客户端请求恒带 `"Resendable":true` 与 `Hash`；39 次发送间隔 100–200ms，
     并在重试前重新铸会话（`Account_CheckNexon` 3 次）。形态上像**客户端对"未确认"请求的自动重发**。
   - 含义：它是在等一个"我认这个响应"的信号，而这个信号**不可能**是 DTO 里的字段（§5.3(1)）。
   - 检验：拿到官方 10014/10015 真报文，逐字段 diff。

### 6.3 判定

- **「加回显」这条路已死**，且不是"可能不行"——DTO 层就没有这个字段，代码里现有那套
  `_pickupSelections` 回显（`ShopHandler.cs:426-466`）对 10015 **永远无效**（对 10014 Get 仍然有效且必要）。
- **39 次重试的真实原因，本轮材料无法定论。** 唯一能定论的方式是拿到官方 10014/10015 的真实报文（§1.1）。
- 在此之前，§6.2 的 #1 / #2 是**零风险、可立刻 A/B** 的两项；#3 需要改配置。

---

## 7. 复核用命令（只读，可复制重跑）

```powershell
# 1) 协议号全量清单 + 10014/10015 是否出现 + ServerNotification 分布
python - <<'PY'
import json,glob,os,collections
d=r"C:\Users\su\Desktop\大肥鱼项目\BAServer\report\_tmp\official_decoded_201"
protos=collections.Counter(); notifs=collections.Counter(); sk=0; n=0
for f in glob.glob(os.path.join(d,"*.json")):
    o=json.load(open(f,encoding="utf-8"))
    m=o.get("meta") or {}
    p=m.get("protocol")
    if p is None and isinstance(o.get("json"),dict): p=o["json"].get("Protocol")
    if p is not None: protos[p]+=1
    i=o.get("inner")
    if isinstance(i,dict) and "Protocol" in i:
        n+=1; notifs[i.get("ServerNotification")]+=1
        if "SessionKey" in i: sk+=1
print("distinct protocols:",sorted(protos)); print("10014 in?",10014 in protos,"| 10015 in?",10015 in protos)
print("responses:",n,"with SessionKey:",sk); print("ServerNotification:",dict(notifs))
PY

# 2) 抓包内 grep（大小写不敏感）
Get-ChildItem "C:\...\official_decoded_201" -File |
  Select-String -Pattern 'pickupselection' -CaseSensitive:$false   # → 0 命中

# 3) DTO 定义
python -c "import json;o=json.load(open(r'C:\...\dto_schema_full_v2.json',encoding='utf-8'));print({k:(v.get('protocol'),v.get('fieldCount'),[f['name']+':'+f['type'] for f in v.get('fields',[])]) for k,v in o.items() if 'Pickup' in k})"
```

---

## 8. 附：本轮所有事实的清单（便于引用）

| # | 事实 | 来源 |
|---|---|---|
| F1 | 官方抓包 109 条 game_api 响应，**38 个 distinct 协议号**，**无 10014 / 无 10015** | `official_decoded_201` |
| F2 | 抓包内 Shop 家族只有 `10002 Shop_List`；gacha 段 10001–10016 一条都没有 | 同上 |
| F3 | 抓包里 `PickupSelection` / `PickupCharacterSelection` **0 命中**（大小写不敏感） | 同上 |
| F4 | 抓包里唯一 pickup 数据：`PickupFirstGetHistoryDBs:[{"ShopRecruitId":5004170,"LogDate":"2026-08-10T13:52:19.949"}]`（在 1017 LoginSync） | 同上 |
| F5 | `ServerNotification` distinct = `{0:87, 3:2, 4:1, 8:10, 1024:1, 2048:8}`，109/109 显式输出 | 同上 |
| F6 | `8 = HasUnreadMail`，**官方出现在 10 次**，**只在 7000 Mail_List / 7001 Mail_Check** | 抓包 + `ProtocolData.cs:521-540` |
| F7 | 官方响应信封恒为 5 字段 `Protocol/SessionKey/ServerTimeTicks/ServerNotification/RequestId`，`AccountId` **0/109** | 抓包统计 |
| F8 | 官方「零自有字段」ACK 的 17 个实例形状 = 上述 5 字段，无任何回显 | `Clan_Check`/`Friend_Check`/`Mail_ListSemiPermanent` |
| F9 | `ShopPickupSelectionGachaSetResponse` 自有字段 **0**；`GetResponse` 自有字段 **1** = `PickupCharacterSelection: Dictionary<long,long>` | `dto_schema_full_v2.json:92407-92575` |
| F10 | schema 中**不存在** `ShopPickupSelectionGacha{Get,Set}Request`；仅在 C# `NetworkProtocol.cs:6768-6790` 有定义 | 双源核对 |
| F11 | `PickupCharacterSelection` = `Dictionary<long,long>?`（可空）；GetRequest 用 `ShopRecruitId`、SetRequest 用 `ShopRecruitID`（大小写不一致） | `NetworkProtocol.cs` |
| F12 | `10014`/`20009` 在官方抓包中确实是**角色 UniqueId**（学园拜访角色） | `01_24000_api_academy_getinfo.response.json` |
| F13 | `GatewayController.cs:264/320-325` 的「只对握手协议回显 SessionKey」与 F7 冲突（实测 109/109 全带） | 源码 vs 抓包 |
| F14 | 全项目 C# 源码 `RequestId` **0 实现** | `grep RequestId *.cs` |
