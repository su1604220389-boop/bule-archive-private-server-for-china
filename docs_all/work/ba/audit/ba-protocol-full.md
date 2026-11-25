# Blue Archive 网络协议（移植自 Shittim-Server，供国服私服用）

> 来源：`https://github.com/Neoexm/Shittim-Server`（463 star，C#/.NET 10，Steam 版私服，已可玩）
> 本地克隆：`/root/bapatch/shittim`（26 MB，1520 文件）
> 用途：我们做国服 Android 私服时，协议层直接从这里移植，不必从零逆向。

---

## 一、信封结构（单入口）

```
POST /api/gateway
Content-Type: application/json

请求体（信封）:
{ "Protocol": "<协议名>", "Packet": "<业务JSON字符串>" }

响应体（信封，服务端用 ServerResponsePacket）:
{ "Protocol": "<协议名>", "Packet": "<业务JSON字符串>" }
```

- 全部业务走**一个** endpoint，靠 `Protocol` 字段区分
- `Packet` 是**字符串**（内部再 JSON 序列化一次）
- 可选压缩/加密（见第四节）

## 二、请求 / 响应基类（`Packet.cs`）

```csharp
// 会话
public class SessionKey {
    public long   AccountServerId { get; set; }
    public required string MxToken { get; set; }
}

// 所有包
public abstract class BasePacket {
    public SessionKey? SessionKey { get; set; }
    public abstract Protocol Protocol { get; }
    public long AccountId => SessionKey?.AccountServerId ?? 0;   // 有 SessionKey 时才输出
}

// 请求额外字段
public abstract class RequestPacket : BasePacket {
    public int  ClientUpTime { get; set; }
    public bool Resendable  { get; set; } = true;
    public long Hash        { get; set; }   // CreateHash(): counter | ((int)protocol << 32)
    public bool IsTest      { get; set; }
    public DateTime? ModifiedServerTime__DebugOnly { get; set; }
}

// 响应额外字段
public abstract class ResponsePacket : BasePacket {
    public long ServerTimeTicks { get; set; }   // 整秒精度
    public ServerNotificationFlag ServerNotification { get; set; }
}
```

**要点**：`SessionKey` 只在特定协议（`Account_CheckNexon` / `Account_Auth` / `ProofToken_*`）出现；
序列化用 `DefaultValueHandling.Ignore`，所以值为 0 的字段会被丢掉 —— **私服端必须同样处理**，否则客户端解析器会炸。

## 三、协议号（1147 个，`ProtocolData.cs`）

关键节点（Steam 版数值，**国服需逐项核对**）：

| 协议号 | 名称 | 用途 |
|---|---|---|
| 1 | `System_Version` | 版本校验 |
| 2 | `Session_Info` | 会话信息 |
| 3 / 4 | `NetworkTime_Sync` / `_SyncReply` | 时间同步 |
| 1000 | `Account_Create` | 建号 |
| 1002 | `Account_Auth` | 登录认证 |
| 1003 | `Account_CurrencySync` | 货币同步 |
| 1005 / 1006 | `Account_GetTutorial` / `SetTutorial` | 新手教程 |
| 1007 | `Account_PassCheck` | 通过校验 |
| 1008 / 1009 | `Account_VerifyForYostar` / `CheckYostar` | 悠星渠道 |
| 1012 | `Account_Auth2` | 第二段认证 |
| **1014** | **`Account_CheckNexon`** | **RSA 握手（第一个包）** |
| -9999 | `Common_Cheat` | 作弊标记 |
| -1 | `Error` | 错误 |

> 文档 `protocol.md` 里写的 "50001" 是 **gateway 层协议号**，不是 `Protocol` 枚举里的业务号，别混。

## 四、加密（`Core/GatewaySessionCrypto.cs` + `Crypto/`）

```
第一次交换: Account_CheckNexon
  → RSA。服务端私钥 Config/GatewayPrivateKey.pem
  → 客户端内置的公钥必须被 patch 成服务端的公钥

握手之后: 会话 AES
  → AES-CBC + session IV（见 crypto 目录的 commit: "gateway response aes is cbc with the session iv"）
  → 但该客户端实测 session key 常为 null → 响应直接明文
```

**客户端私钥缺失的表现**（对排错很有用）：客户端卡在 "Unpacking game resources"，不报任何密钥错误。

## 五、客户端 patch 清单（`client-patching.md` 摘要）

Steam 版服务端启动时会自动改这些（**我们的 APK 路线可对应处理**）：

| Patcher | 文件 | 改动 |
|---|---|---|
| **Metadata** | `global-metadata.dat` | **服务端 RSA 公钥，3 个 150 字节块** + region label |
| Gamescale IAS | `gamescale.core.dll` | 登录 endpoint |
| Inface config | inface 配置文件 | endpoint 配置 |
| Steam offline | `GameAssembly.dll` | 让客户端在 Steam 离线时也能拿票 |
| Banners | `ExcelDB.db` | 招募 banner 行 |
| Region label | `global-metadata.dat` | 标题页地区名 |
| Store URL | 商店查询表 | 指向私服，让商城货币校验返回"无路可走" |

**region label 机制**（重要）：标题页地区名**不走网络**，是 `global-metadata.dat` 里 `ServerRegion` 枚举成员的**名字**。
三处必须拼写一致：枚举名、独立字符串、服务端的 connection group 名 —— 否则 `Queuing_GetTicket` 返回空 gateway URL，客户端卡加载页。

## 六、序列化坑（Newtonsoft，三个自定义 converter）

1. **日期**：ISO 字符串，**无时区偏移、整秒精度**（`2026-07-27T04:12:50`）。唯一的小数值是 `DateTime.MaxValue` = `9999-12-31T23:59:59.9999999`
2. **整数值的 float**：**不写小数点**
3. **向量**：必须始终带 x/y/z —— 网关默认会丢掉 0 分量，而客户端反序列化在**无 try/catch** 的方法里抛异常，直接整条响应静默失败

## 七、Handler 组织（66 个文件）

`Shittim-Server/Core/NetworkProtocol/Handlers/*.cs`，每个类用 `[ProtocolHandler(Protocol.Xxx)]` 标注方法：

```csharp
[ProtocolHandler(Protocol.NetworkTime_Sync)]
public async Task<NetworkTimeSyncResponse> Sync(SchaleDataContext db, NetworkTimeSyncRequest request, NetworkTimeSyncResponse response)
```

覆盖：Account / Campaign / Character / Gacha / Item / Craft / Mission / Raid / WorldRaid / Arena / Cafe / Clan / Friend / Mail / MomoTalk / Scenario / Shop / Billing / MiniGame(5种) / EventContent(5种) / ProofToken / Queuing …

**未实现的协议返回 500**，客户端显示"无法处理的请求"；handler 内异常也一样，只能看服务端日志区分。

## 八、国服移植注意

| 项 | 说明 |
|---|---|
| **协议号** | Steam 版是 1014 = `CheckNexon`；国服 3.0.2 可能不同，需用客户端 `MX-` 明文串核对 |
| **认证链** | 国服走 `Account_Auth` → `LoginToServer`，Yostar/Nexon 渠道不同 |
| **RSA 公钥** | 国服在 `global-metadata.dat` 里，位置需重新定位（不是 3×150 字节的固定偏移） |
| **AES** | 客户端有 `AiriSgClient.getAAesKey/getAAesIv`，说明国服 key 来自 native，不是纯 metadata |
| **gateway endpoint** | 国服由 `/api/state` 下发，不是硬编码 |

## 九、对我们（改 APK 路线）的直接价值

1. **不用逆向响应结构了** —— 1147 个请求/响应类在这份代码里全有字段定义
2. **协议号表**可直接对照客户端 `MX-` 字符串验证国服数值
3. **序列化规则**（日期/浮点/向量）是客户端解析器的硬约束，照抄即可
4. **信封格式**（Protocol + Packet 字符串）已实证可用
5. 服务端可以用 PHP 重写（低并发场景），但**字段名/嵌套/默认值行为必须完全一致**
