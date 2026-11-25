# 10015（`ShopPickupSelectionGachaSet`）回显修复 —— **停手报告**

> 结论先行：**按你的红线要求，我停在第一步没有动代码、没有构建。**
> 原因：`ShopPickupSelectionGachaSetResponse` 在**服务端与客户端两侧都没有任何字段**，你说过"如果响应 DTO 根本没有这两个字段（需要新增字段），先别自己加 —— 停下来把 DTO 定义贴给我"。下面是 DTO 定义与相关取证。

---

## 1. DTO 定义（原文）

### 1.1 服务端 `Schale\MX\NetworkProtocol\NetworkProtocol.cs:6787-6791`

```csharp
public class ShopPickupSelectionGachaSetResponse : ResponsePacket
{
    public override Protocol Protocol { get => Protocol.Shop_PickupSelectionGachaSet; }
}
```
**只有 `Protocol`，没有 `ShopRecruitID`，没有 `PickupCharacterSelection`。**

### 1.2 对照：Get（10014）的响应 —— 有字段

```csharp
// NetworkProtocol.cs:6774-6778
public class ShopPickupSelectionGachaGetResponse : ResponsePacket
{
    public override Protocol Protocol { get => Protocol.Shop_PickupSelectionGachaGet; }
    public Dictionary<long, long>? PickupCharacterSelection { get; set; }   // ← 只有 Get 有
}
```

### 1.3 请求侧（两个字段都在请求里）

```csharp
// NetworkProtocol.cs:6780-6785
public class ShopPickupSelectionGachaSetRequest : RequestPacket
{
    public override Protocol Protocol { get => Protocol.Shop_PickupSelectionGachaSet; }
    public long ShopRecruitID { get; set; }                       // 注意大写 D
    public Dictionary<long, long>? PickupCharacterSelection { get; set; }
}
// NetworkProtocol.cs:6768-6772 （Get 请求）
public class ShopPickupSelectionGachaGetRequest : RequestPacket
{
    public override Protocol Protocol { get => Protocol.Shop_PickupSelectionGachaGet; }
    public long ShopRecruitId { get; set; }                       // 注意小写 d
}
```

### 1.4 **客户端 DTO（`work\ba\proto\dto_schema_full_v2.json`）—— 决定性证据**

```
ShopPickupSelectionGachaSetResponse   fields = 0     ← 客户端也没有任何字段
ShopPickupSelectionGachaGetResponse   fields = 1     (PickupCharacterSelection: Dictionary<long,long>)
```

**⇒ 客户端根本没有地方接收这两个字段。** 即使我们给 Set 响应加上 `ShopRecruitID` / `PickupCharacterSelection`，客户端反序列化时**会直接忽略未知键**（Newtonsoft 默认行为），行为不会有任何变化 —— **这条修法在原理上不可能生效**。

---

## 2. 存储逻辑核查（你的第 2 点）：**是对的，不用改**

```csharp
// ShopHandler.cs:432-433  存储容器
private static readonly ConcurrentDictionary<(long AccountId, long ShopRecruitId), Dictionary<long, long>> _pickupSelections = new();

// ShopHandler.cs:443-448  Get：按 (账号, 池) 读回
response.PickupCharacterSelection =
    _pickupSelections.TryGetValue((account.ServerId, request.ShopRecruitId), out var saved) && saved.Count > 0
        ? new Dictionary<long, long>(saved)
        : new Dictionary<long, long>();

// ShopHandler.cs:459-463  Set：按 (账号, 池) 写入
if (request.PickupCharacterSelection is { Count: > 0 })
{
    _pickupSelections[(account.ServerId, request.ShopRecruitID)] =
        new Dictionary<long, long>(request.PickupCharacterSelection);
}
```
- `Dictionary<long,long>` 与客户端 `{"1":10014}`（字符串 key）→ Newtonsoft 会解析成 `long` key，形状一致；
- **Set 存、Get 读，键一致（都是 `ShopRecruitId` 侧的值），逻辑成立。**
- 唯一瑕疵：`ShopRecruitID`（Set）与 `ShopRecruitId`（Get）属性名大小写不同 —— Newtonsoft **默认大小写不敏感**，绑定没问题；但这是我们代码风格问题，不影响功能。

---

## 3. 那 39 次重试更可能是什么？（证据分级）

| # | 假设 | 证据 |
|---|---|---|
| **H1** | 客户端 Set 成功后**要靠 Get(10014) 回读**才知道"已设置"，而它**没有发 Get**（日志里只有 39 次 Set）⇒ 它以为没保存 | **【推测】** 需要确认那 39 次之间是否夹着 10014 |
| **H2** | 客户端发了 Get，但带的 `ShopRecruitId` 与服务端存的 key 不一致（例如发 0）⇒ 我们返回空 map ⇒ 客户端判"未保存" | **【推测】** 同上，需要 10014 的请求体 |
| **H3** | 客户端本地 `IsCharacterSetSelected` 依赖 Get 返回的 **map 内容**而不仅是"非空"（例如要求 `key` 是 pickup index、value 是 characterId），我们原样存回，理论上一致 | **【推测】** |
| **H4** | 与**回显无关**：客户端在 39 次重试后放弃是它自己的重试策略（我们每次都 200 且结构完整） | **【已证实·现象】**（线上报文确实 200 且 JSON 合法） |

**⇒ 单靠"给 Set 加回显"修不了**（客户端 DTO 0 字段，见 §1.4）。

---

## 4. 建议的下一步（都不需要新增 DTO 字段）

1. **先把证据补齐（只读）**：从 00:48 那次日志里抽出 10015 前后 5 秒的所有协议号，确认：
   - 有没有 `10014`？它带的 `ShopRecruitId` 是多少？
   - 有没有 `10016`？
2. **如果确认 H2（Get 带 0 或带错 id）**：服务端可以做**容错读**（仍然 0 个新 DTO 字段）：
   ```csharp
   // ShopHandler.cs Get 里，ShopRecruitId 为 0 时回退到"该账号最近一次 Set 的选择"
   var key = request.ShopRecruitId;
   if (key == 0 && _pickupSelections.Keys.Any(k => k.AccountId == account.ServerId))
       key = _pickupSelections.Keys.Last(k => k.AccountId == account.ServerId).ShopRecruitId;
   ```
   —— 这条是**纯服务端、零 DTO 改动**，可作为下一个单变量实验。
3. **如果要给 Set 加字段**：必须**同时**确认客户端 DTO 里有对应字段（现在字段数 0）——否则只是往空气里发数据。若你仍要加（为将来客户端版本兼容），最小形态是：
   ```csharp
   public class ShopPickupSelectionGachaSetResponse : ResponsePacket
   {
       public override Protocol Protocol { get => Protocol.Shop_PickupSelectionGachaSet; }
       public long ShopRecruitID { get; set; }
       public Dictionary<long, long>? PickupCharacterSelection { get; set; }
   }
   ```
   **但我没有做这个改动**（等你的决定）。
4. 你要的那行 INFO 日志（同样**未加**），建议形态：
   ```csharp
   _logger.LogInformation("[PICKUP] set account={Account} recruit={Recruit} count={Count}", account.ServerId, request.ShopRecruitID, request.PickupCharacterSelection?.Count ?? 0);
   ```
   注意：`ShopHandler` 目前**没有注入 `ILogger`**（构造函数只有 `ISessionKeyService`/`ShopManager`/`IMapper` 等，见 `ShopHandler.cs` 顶部），加日志需要顺手补一个构造参数——这属于"改构造"，按你的红线我先不做。

---

## 5. 本次动作记录

| 项 | 状态 |
|---|---|
| 改 .cs | **无** |
| 备份 | 无需（未改） |
| 构建 | **未执行**（未产生 `_build_picksel2`） |
| 产物 sha256 | 不适用 |
| 部署 | 无 |

---

## 5. `ServerNotification = 8` 是什么（追加，2026-11-19）

### 5.1 类型与语义

```csharp
// Schale\MX\NetworkProtocol\Packet.cs:50   —— ResponsePacket 基类字段
public ServerNotificationFlag ServerNotification { get; set; } = ServerNotificationFlag.None;
```
```csharp
// Schale\MX\NetworkProtocol\ProtocolData.cs:521-540
public enum ServerNotificationFlag : int
{
    None                              = 0,
    NewMailArrived                    = 4,
    HasUnreadMail                     = 8,        // ★ 8 = 有未领取邮件
    NewToastDetected                  = 16,
    CanReceiveArenaDailyReward        = 32,
    CanReceiveRaidReward              = 64,
    ServerMaintenance                 = 256,
    CannotReceiveMail                 = 512,
    InventoryFullRewardMail           = 1024,
    CanReceiveClanAttendanceReward    = 2048,
    HasClanApplicant                  = 4096,
    HasFriendRequest                  = 8192,
    CheckConquest                     = 16384,
    CanReceiveEliminateRaidReward     = 32768,
    CanReceiveMultiFloorRaidReward    = 65536,
    CanReceiveProductDailyRecordReward= 131072,
    HasUnreadSemiPermanentMail        = 262144,
}
```

**⇒ `8` = `HasUnreadMail`，是"有未领取邮件"的红点位，不是错误码。**

### 5.2 谁把它设成 8 —— **不是 ShopHandler，是网关统一叠的**

```csharp
// GatewayController.cs:236   —— 进入 handler 之前先算一次
var notification = await ReadServerNotificationAsync(payload, protocol);
// :268-269   —— 出站前 OR 上去（设计上就是"叠加"，不是覆盖）
rsp.ServerNotification |= notification;
// :336-353
if (await db.GetAccountMailbox(accountServerId, now).AnyAsync())
    return forced | ServerNotificationFlag.HasUnreadMail;      // ← 就是这行给出 8
```
`ShopHandler.cs` 全文 grep `ServerNotification` ⇒ **0 命中**（10015 的响应体里没有任何一处设置它）。
**官方行为一致**（本文件 `GatewayController.cs:327-329` 的注释）：
> `The official server stamps ServerNotification on every in-session response; the baseline computed here is HasUnreadMail (8) whenever unclaimed mail exists ... In a capture whose account had unread mail from login to logout every response carried ServerNotification=8 except ProofToken_RequestQuestion / NetworkTime_Sync / ProofToken_Submit / Account_GetTutorial.`

⇒ **10015 回 `8` 与官方完全一致，不是异常。**

### 5.3 其它"保存类"协议一般填什么

全工程只有 6 处 handler 主动设它（其余一律保持 `None=0`，再由网关叠加邮箱基线）：

| handler | 位置 | 设的值 | 说明 |
|---|---|---|---|
| `Attendance_Receive` | `AttendanceHandler.cs:52` | `|= NewMailArrived (4)` | 发奖进邮箱 ⇒ 4（+基线 8 = 12） |
| `MailHandler`（领取） | `MailHandler.cs:48` | `|= NewMailArrived (4)` | 同上 |
| `ClanHandler.Lobby` | `ClanHandler.cs:134` | `|= NewMailArrived (4)` | 同上 |
| `ClanHandler.Check` | `ClanHandler.cs:149` | `= CanReceiveClanAttendanceReward (2048)` | 覆盖式（+基线 = 2056） |
| `CafeHandler` | `CafeHandler.cs:287-289` | `HasUnreadMail` 或 `None` | 手工对齐基线 |
| `ContentSweepHandler` | `ContentSweepHandler.cs:327` | 同上 | 同上 |
| **其余所有 handler（含 10015）** | — | **从不设置 ⇒ 0**，最终只带基线 | — |

**⇒ "保存类"协议（设置/选择/昵称/编队）默认就是不设置（=0），最终带什么完全取决于邮箱基线。10015 带 8 属于这一类，正常。**

### 5.4 客户端会不会靠这个字段判断"操作有没有生效"？

**判断：不会。** 依据（全部来自代码事实）：
1. `8` 是**账号级邮箱红点**，在**几乎每条** in-session 响应上都会出现（`:329` 注释用的是 "every response carried ServerNotification=8"）；
2. 10015 的 `8` 与"设置成功/失败"没有任何代码路径上的联系（`ShopHandler` 从不设它，网关只看邮箱）；
3. 若客户端真用它判断，那它在此前**每一条**响应上都会得到同样的 8 —— 包括明显成功的 `Shop_List`/`LoginSync`，无法区分。

**⇒ 把 10015 的响应改写成 `ServerNotification = 0` 不会有帮助，反而会与官方行为不符**（官方在有未读邮件时同样带 8）。**不建议做这一行改动。**

### 5.5 那 39 次重试只剩一个方向

客户端在这场交互里**唯一能读的自定义数据 = 空**（`ShopPickupSelectionGachaSetResponse` 两侧 0 字段，见 §1.4），而 `ServerNotification` 是全局邮箱位、无法区分成功失败。
⇒ 客户端要么在等**它自己期望的某个后续动作**（例如 Get 回读），要么是它本地状态机 bug。**服务端在这个协议上没有可改的抓手**（除非新增 DTO 字段，且客户端也不认 —— 见 §1.4）。

**下一步取证（只读）**：确认 39 次 Set 之间/之后是否有 **10014 Get**，以及 `Mail_Check` 之外是否出现过任何能让红点消失的操作。若确实 0 次 Get，则这条要转 il2cpp-analyst 看客户端状态机。
