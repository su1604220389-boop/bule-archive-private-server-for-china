# 响应壳对齐官方（SessionKey 全量回显 + ServerNotification 收窄）

> 2026-11-19　·　只改代码 + 本地构建，**未部署**
> 唯一改动文件：`Shittim-Server\Controllers\Api\GatewayController.cs`
> 备份：`GatewayController.cs.bak_20261119-015252`（同目录）

---

## 1. 改动 A —— `SessionKey` 全量回显

### 改前
```csharp
// L264-266（旧）
// Official responses echo SessionKey plus the derived top-level AccountId ONLY on the account/security handshake protocols; every other response omits both. Handlers that mint a new session (CheckNexon/Create) set SessionKey themselves.
if (rsp.SessionKey == null && ShouldEchoSessionKey(protocol))
    rsp.SessionKey = payload.SessionKey;
```
```csharp
// L321-325（旧）
private static bool ShouldEchoSessionKey(Protocol protocol) => protocol
    is Protocol.Account_Auth
    or Protocol.Account_Auth2
    or Protocol.ProofToken_RequestQuestion
    or Protocol.ProofToken_Submit;
```

### 改后
```csharp
// L264-270（新）
// BAPATCH-ENVELOPE v1: the official server echoes SessionKey on every single response (109/109 in the
// capture, including Clan_Check and Friend_Check), not just on the handshake protocols. Handlers that
// mint a session (CheckNexon/Create) already set rsp.SessionKey and are left alone; when the request
// carried none we still answer the official shape rather than omitting the field.
if (rsp.SessionKey == null && ShouldEchoSessionKey(protocol))
    rsp.SessionKey = payload.SessionKey
        ?? new SessionKey { AccountServerId = 0, MxToken = string.Empty };
```
```csharp
// L325-327（新）
// BAPATCH-ENVELOPE v1: always true. The whitelist that used to live here contradicted the capture - every
// one of the 109 official responses carried SessionKey. The parameter is kept so the call site reads the same.
private static bool ShouldEchoSessionKey(Protocol protocol) => true;
```

- `AccountServerId` 取的是**请求里已认证会话**的 id（`payload.SessionKey.AccountServerId`），没有就按官方形状回 `{0, ""}`，**不省略字段**。
- 已经自己铸会话的 handler（`Account_CheckNexon`/`Account_Create`）不受影响：它们运行时 `rsp.SessionKey != null`，不进这个分支。

---

## 2. 改动 B —— `ServerNotification.HasUnreadMail` 只在邮件家族上盖

### 改前
```csharp
// L342-353（旧）—— 只要账号有未读邮件就给每条响应盖 8
var forced = ServerNoticeService.Flags;
try
{
    ...
    if (await db.GetAccountMailbox(accountServerId, now).AnyAsync())
        return forced | ServerNotificationFlag.HasUnreadMail;
}
```

### 改后
```csharp
// L354-360（新）
var forced = ServerNoticeService.Flags;

// BAPATCH-ENVELOPE v1: HasUnreadMail is not a per-response baseline. In the official capture only the mail
// family ever reported 8; every other protocol answered 0 even while unread mail was sitting in the box.
// Stamping it on all 109 responses (what this used to do) makes the flag meaningless to the client.
if (!CarriesMailNotification(protocol))
    return forced;
```
```csharp
// L338-345（新增）
// BAPATCH-ENVELOPE v1: the only protocols that may carry HasUnreadMail. Mail_List (7000) and Mail_Check (7001)
// are the two seen with 8 in the capture; the rest of the family is included because it reports the same box.
private static bool CarriesMailNotification(Protocol protocol) => protocol
    is Protocol.Mail_List
    or Protocol.Mail_Check
    or Protocol.Mail_Receive
    or Protocol.Mail_ListSemiPermanent
    or Protocol.Mail_ReceiveSemiPermanent;
```

- 非邮件协议现在直接 `return forced;`（**不再查库**，顺带省一次 DB 查询），运维强制位（`ServerNoticeService.Flags`）仍然保留。
- `Mail_List(7000)` / `Mail_Check(7001)` 仍会得到 `8`，与官方一致；`Mail_Receive` 等家族成员也保留（领完仍有未读时会继续显示，直到下一次非邮件请求不再带 —— 由客户端自己的 Mail_Check 驱动）。

### 未改动（按你的红线）
`ShouldEchoRequestId` 相关逻辑、10015 handler、`_pickupSelections`、任何业务逻辑、任何 DTO —— **一行未动**。

---

## 3. 构建

```powershell
cd C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\srv_src
dotnet build Shittim-Server\Shittim-Server.csproj -c Release -o _build_envelope1 --nologo --no-incremental
```

结果：**0 个错误 / 268 个警告**（警告数与基线同量级，`GatewayController.cs` 无新增警告）。

---

## 4. 产物

| 项 | 值 |
|---|---|
| 目录 | `C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\srv_src\_build_envelope1\` |
| `Shittim-Server.dll` 大小 | **2,688,000 B** |
| `Shittim-Server.dll` sha256 | **`160c3e159956ee8300b57a90af70bc8813cb03ce5aef48d3c36615631cf4bd16`** |

---

## 5. DLL 差异表（对比本次改动前的最近一次构建 `_build_exportfilter`，2026-11-19 00:45）

| DLL | 大小 | 改后 sha256（前 16） | 改前 sha256（前 16） | 结论 |
|---|---|---|---|---|
| **Shittim-Server.dll** | 2,688,000 | **`160c3e159956ee83`** | `63ca8f34694f6542` | **CHANGED（唯一变化）** |
| Schale.dll | 5,392,896 | `b06f46090f9d8eb8` | `b06f46090f9d8eb8` | 未变 |
| Newtonsoft.Json.dll | 712,464 | `22c649f75fce5be7` | `22c649f75fce5be7` | 未变 |
| Microsoft.EntityFrameworkCore.dll | 2,828,600 | `acb89dff050d681f` | `acb89dff050d681f` | 未变 |
| Microsoft.EntityFrameworkCore.Sqlite.dll | 311,608 | `b8c5027b27be2012` | `b8c5027b27be2012` | 未变 |
| Serilog.dll | 128,000 | `db0a4c4a21a1ba09` | `db0a4c4a21a1ba09` | 未变 |
| SQLitePCLRaw.core.dll | 51,200 | `3d2ed8e186f124f9` | `3d2ed8e186f124f9` | 未变 |

**其余全部三方依赖 DLL 逐文件 sha256 比对：无一变化。** 只有 `Shittim-Server.dll` 变了，与"只改了 `GatewayController.cs`"完全吻合。

---

## 6. 风险与回滚

| 风险 | 说明 | 处置 |
|---|---|---|
| **登录前协议也会带 `SessionKey:{0,""}`** | `Queuing_*` / `NetworkTime_Sync` / `ProofToken_*` 这类请求本来**没有** SessionKey，改后会回一个零形状。若客户端把"响应里出现 SessionKey"当作"已认证"，可能影响握手顺序 | 这是本补丁**唯一需要实测确认**的点：上线后先看登录握手（Queuing → CheckNexon → Auth → LoginSync）是否仍正常；异常则把调用点那一行改回 `rsp.SessionKey = payload.SessionKey;`（去掉 `?? new ...` 兜底），**一行回退、不用改别处** |
| 邮件红点不再"全局常亮" | 只有邮件家族带 8；若客户端靠"非邮件响应里的 8"维持红点，可能红点闪断 | 与官方行为一致（官方就是这样），优先信任抓包 |
| 运维强制公告 | `ServerNoticeService.Flags` 仍会在**所有**协议上叠加（`return forced;`），不受影响 | 无 |
| 回滚 | 目录里有 `GatewayController.cs.bak_20261119-015252`，`cp` 回去重编即可 | 一条命令 |

---

## 7. 一句话

**只有 `Shittim-Server.dll` 变了**（`160c3e15…` / 2,688,000 B），其余 DLL 与原构建完全一致；改动集中在 `GatewayController.cs` 的两处：`SessionKey` 全量回显（含零形状兜底）+ `HasUnreadMail` 收窄到邮件家族。
