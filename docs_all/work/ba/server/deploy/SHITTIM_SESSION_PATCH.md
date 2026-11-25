# Shittim 会话铸造幂等化补丁 —— `[BAPATCH-SESSION-REUSE v1]`

> 变更范围：`Shittim-Server/Services/SessionKeyService.cs` **一个文件、一处插入、12 行（有效逻辑 5 行）**。
> `Schale` 子项目零改动。产物只有一个 DLL：`Shittim-Server.dll`。
> 本文所有数字均为本机实测；**没有任何 ssh/scp/上传动作**，上线步骤留给人工执行（第 8 节）。

---

## 0. 结论摘要（数字总表）

| 项 | 基线（未打补丁） | 打完补丁 |
|---|---|---|
| `SessionKeyService.cs` | **7,606 B**<br>`377e8a1aff868f913c205b016659ca9b0620f6a9813c2639507e63134d9b9560` | **8,245 B**<br>`40517d883da97964fe73f2365f747faf4d16ff0fe0c488f3ab5736c25b2336b9` |
| `Shittim-Server.dll` | **2,669,568 B**<br>`73e487c813bb2c9e7ba86e731a3f527090e6ee569f4dd6b9158b2658ccf93cff` | **2,669,568 B**<br>`01f5b906159d81b883f86c03df599bcd7936a26ef7db72c62e75d079946a4a18` |
| `Schale.dll` | **5,392,384 B**<br>`73965be6d62b1f9ddfecff765e8aa6195682229c1f1fe201dcfb90acf183cf38` | **5,392,384 B**<br>`73965be6d62b1f9ddfecff765e8aa6195682229c1f1fe201dcfb90acf183cf38`（**未变**） |
| 编译 | 0 错误 / 255 警告（增量）· 265（全量） | 0 错误 / 255 警告（增量）· 265（全量） |
| 回滚后重编 | — | **精确回到** `73e487c8…`（可重复构建成立） |

⚠️ **一处与任务书预期的偏差，必须如实说明**：补丁后 `Shittim-Server.dll` 的**字节数恰好仍是 2,669,568 B，与基线相同**，但 **sha256 不同**（`01f5b906…` vs `73e487c8…`）。
原因：.NET 程序集按 section/文件对齐（512 B 粒度）排布，新增的 IL（约百余字节）连同方法头填充落在既有对齐空隙内，PE 各 section 的 RVA 与总长度不变。
**判定补丁生效的依据是 sha256 变化，不是文件长度**。若上线后要核验，请比 sha256，不要比字节数。

---

## 1. 问题与根因

线上实测：

- Shittim 侧 `Session expired or invalid` 出现 **86 次**；
- 桥在 **170 次**请求里重铸了 **48 次**会话。

根因（`SessionKeyService.cs`，基线源码行号）：

```csharp
private readonly ConcurrentDictionary<long, ActiveSession> _activeSessions;   // L14：一个账号只能有一个会话
...
_activeSessions.AddOrUpdate(account.ServerId, session, (_, _) => session);    // L104：每次铸会话都覆盖旧 token
...
if (!_activeSessions.TryGetValue(sessionKey.AccountServerId, out var session)) // L152
    throw new UnauthorizedAccessException("Session expired or invalid");      // L153
```

即：`_activeSessions` 以 `account.ServerId` 为键、值是**单个** `ActiveSession`。
`GenerateSession` 每被调用一次就 `AddOrUpdate` 换掉值 ⇒ **旧 token 当场作废**。
桥/客户端随后的在途请求带着旧 token 回来，就会在 `GetAuthenticatedUser` 被判：

- 键还在、token 已换 → L155-156 `Session token mismatch`；
- 键被 `PurgeExpiredSessions` 清掉（或 sidecar `Config/sessions.json` 缺失、重启后没加载回来）→ L152-153 `Session expired or invalid`（线上这 86 次属于这条）。

两种表现都来自同一个模型：**“一账号一会话” + “每次重铸就覆盖”**。

`GenerateSession` 的三个调用点（`AccountHandler.cs` L96 `Account_CheckNexon`、L247 `Account_Create`、L907）**都没有传 `customToken`**，所以每次重连/建号都会重铸并作废旧 token。

---

## 2. 补丁内容（唯一一处）

插入点：`GenerateSession` 方法体内，`if (account == null) return null;` **之后**、`var tokenGuid = ...` **之前**。

```csharp
            // [BAPATCH-SESSION-REUSE v1] 同一账号已有有效会话时复用其 token，
            // 避免桥/客户端反复重铸导致在途请求被判 Session expired or invalid。
            if (string.IsNullOrEmpty(customToken) && _activeSessions.TryGetValue(account.ServerId, out var _reuseExisting))
            {
                _reuseExisting.LastActivity = DateTime.UtcNow;
                PersistSessions();
                return new SessionKey
                {
                    AccountServerId = account.ServerId,
                    MxToken = _reuseExisting.Token.ToString()
                };
            }
```

语义：

1. **`customToken` 为空且该账号有会话** → 复用旧 token，刷新 `LastActivity`，落盘，直接返回；**不生成新 Guid、不覆盖 `_activeSessions`**。
2. **`customToken` 显式给出（非空）** → 条件短路，落到原逻辑，按旧语义新建会话（**原语义完整保留**）。
3. 方法其余部分、以及 `ValidateRequest` / `GetAuthenticatedUser` / `RevokeSession` / `PurgeExpiredSessions` / `LoadPersistedSessions` / `PersistSessions` **一字未动**。
4. `RevokeSession` 仍能真正踢人（`TryRemove`），`PurgeExpiredSessions` 仍按 `LastActivity` 过期；复用分支刷新了 `LastActivity`，所以“活跃账号不会被误清”。

补丁后 `_activeSessions` 依然只有一个会话条目/账号（不新增结构），只是**不再每次换 token**。

---

## 3. 完整 diff

`--dry-run` 实测输出（未写盘）：

```diff
--- Shittim-Server/Services/SessionKeyService.cs (baseline, 377e8a1aff86)
+++ Shittim-Server/Services/SessionKeyService.cs (patched, 40517d883da9)
@@ -89,6 +89,19 @@
             if (account == null)
                 return null;
 
+            // [BAPATCH-SESSION-REUSE v1] 同一账号已有有效会话时复用其 token，
+            // 避免桥/客户端反复重铸导致在途请求被判 Session expired or invalid。
+            if (string.IsNullOrEmpty(customToken) && _activeSessions.TryGetValue(account.ServerId, out var _reuseExisting))
+            {
+                _reuseExisting.LastActivity = DateTime.UtcNow;
+                PersistSessions();
+                return new SessionKey
+                {
+                    AccountServerId = account.ServerId,
+                    MxToken = _reuseExisting.Token.ToString()
+                };
+            }
+
             var tokenGuid = string.IsNullOrEmpty(customToken) 
                 ? Guid.NewGuid() 
                 : Guid.Parse(customToken);
```

文件属性：原文件 **LF 换行、无 BOM、UTF-8、末尾有换行**；补丁写入后**保持不变**（7,606 → 8,245 B，+639 B，纯插入，无其他行被改）。

补丁后的方法体（带行号，实测截取，见 `_shittim_session/patched_GenerateSession.txt`）：

```csharp
  77 | public async Task<SessionKey?> GenerateSession(long publisherAccountId, string? customToken = null)
  78 |         {
  79 |             await using var db = await _dbFactory.CreateDbContextAsync();
  80 |             
  81 |             var account = await db.Accounts
  82 |                 .FirstOrDefaultAsync(a => a.PublisherAccountId == publisherAccountId);
  83 | 
  84 |             // Account selected in the Control Center wins over the publisher mapping, ...
  85 |             var selectedId = Config.Instance.ServerConfiguration.SelectedAccountId;
  86 |             if (selectedId > 0)
  87 |                 account = await db.Accounts.FirstOrDefaultAsync(a => a.ServerId == selectedId) ?? account;
  88 | 
  89 |             if (account == null)
  90 |                 return null;
  91 | 
  92 |             // [BAPATCH-SESSION-REUSE v1] 同一账号已有有效会话时复用其 token，
  93 |             // 避免桥/客户端反复重铸导致在途请求被判 Session expired or invalid。
  94 |             if (string.IsNullOrEmpty(customToken) && _activeSessions.TryGetValue(account.ServerId, out var _reuseExisting))
  95 |             {
  96 |                 _reuseExisting.LastActivity = DateTime.UtcNow;
  97 |                 PersistSessions();
  98 |                 return new SessionKey
  99 |                 {
 100 |                     AccountServerId = account.ServerId,
 101 |                     MxToken = _reuseExisting.Token.ToString()
 102 |                 };
 103 |             }
 104 | 
 105 |             var tokenGuid = string.IsNullOrEmpty(customToken) 
 106 |                 ? Guid.NewGuid() 
 107 |                 : Guid.Parse(customToken);
 108 | 
 109 |             var session = new ActiveSession
 110 |             {
 111 |                 UserId = account.ServerId,
 112 |                 Token = tokenGuid,
 113 |                 CreatedAt = DateTime.UtcNow,
 114 |                 LastActivity = DateTime.UtcNow
 115 |             };
 116 | 
 117 |             _activeSessions.AddOrUpdate(account.ServerId, session, (_, _) => session);   // 保留原逻辑
 118 |             PersistSessions();
 119 | 
 120 |             return new SessionKey
 121 |             {
 122 |                 AccountServerId = account.ServerId,
 123 |                 MxToken = tokenGuid.ToString()
 124 |             };
 125 |         }
```

---

## 4. 编译验证

命令（本机，纯本地）：

```powershell
& 'C:\Program Files\dotnet\dotnet.exe' build `
    'work\ba\srv_src\Shittim-Server\Shittim-Server.csproj' -c Release --nologo
```

实测输出（补丁后，`_shittim_session/build_patched.log` 末尾）：

```
  Schale -> ...\srv_src\Schale\bin\Release\net10.0\Schale.dll
  Shittim-Server -> ...\srv_src\Shittim-Server\bin\Release\net10.0\Shittim-Server.dll
已成功生成。
    255 个警告
    0 个错误

已用时间 00:00:03.14
```

| 编译 | 结果 | 警告 | 耗时 |
|---|---|---|---|
| 基线（原样） | 0 错误 | 255（增量）/ 265（全量 `--no-incremental`） | 01.04 s（无改动未重编）/ 04.06 s |
| 打补丁后 | **0 错误** | **255 / 265** | 03.14 s / 03.80 s |
| 回滚后重编 | 0 错误 | 255 / 265 | 02.21 s / 03.70 s |

**同一构建模式下，补丁前后的警告数量和集合完全一致**（增量 255 = 255，全量 265 = 265）⇒ 补丁没有引入任何新警告。
额外那 10 条只是构建模式差异：全量重编会重新编译 `Schale` 子项目并重复报告它自己的 24 条既有警告
（增量模式下 Schale 未重编，Schale 项目标记的警告为 0 条；日志实测：增量 8 行 Schale 相关 / 全量 28 行）。

255 个警告全部是既有类别，与本次补丁无关：
`CS8632`(nullable 注释) / `NU1903`(AutoMapper 15.1.3 安全公告，既有) / `EF1002` / `CS0649` / `CS7022` / `SYSLIB0057` / `CS0168` / `CS4014` / `CS0219`。
补丁也没有 `_reuseExisting` 相关的未使用/未赋值提示。

环境：SDK 10.0.301（`global.json` 要求 10.0.100，`rollForward: latestFeature`），`TargetFramework=net10.0`，`Directory.Build.props` 版本 `2026.8.8`。

---

## 5. 产物指纹（新 / 旧 DLL）

| 文件 | 基线 | 补丁后 |
|---|---|---|
| `Shittim-Server.dll` | 2,669,568 B<br>`73e487c813bb2c9e7ba86e731a3f527090e6ee569f4dd6b9158b2658ccf93cff` | 2,669,568 B<br>`01f5b906159d81b883f86c03df599bcd7936a26ef7db72c62e75d079946a4a18` |
| `Schale.dll` | 5,392,384 B<br>`73965be6d62b1f9ddfecff765e8aa6195682229c1f1fe201dcfb90acf183cf38` | 5,392,384 B<br>`73965be6d62b1f9ddfecff765e8aa6195682229c1f1fe201dcfb90acf183cf38` |

**`Schale.dll` 的 sha256 与任务书给出的基线值逐字符一致 ⇒ 完全没变**，不需要（也不应该）上传。

补丁后的 DLL 副本已留档（可直接用于上线）：

```
work\ba\server\deploy\_shittim_session\Shittim-Server.patched.01f5b906159d.dll
2,669,568 B  sha256=01f5b906159d81b883f86c03df599bcd7936a26ef7db72c62e75d079946a4a18
```

该留档 DLL 与“补丁源码全量重编（`--no-incremental`）”的产物**逐字节相同**（实测 `artifact matches rebuilt patched DLL: True`）
⇒ 补丁构建同样是确定性的，交付的 DLL 与源码严格对应。

---

## 6. 行为验证 —— 静态验证 + 路径推演（**不是**运行时验证）

> **明确声明**：本 agent 没有启动 Shittim-Server，没有连服务器，没有发一个真实协议请求。
> 下面全部是**静态校验 + 控制流推演**。真正的运行时验证只能上线后看日志（`Session expired or invalid` 次数应归零）。

### 6.1 五条静态断言逐条结果（`--verify` 实跑，补丁态）

`patch_shittim_session.py --verify` 用「去注释副本 + 大括号配对」把 `GenerateSession` 方法体切出来，再按位置/正则判定（属结构断言，非完整 C# AST）：

| # | 断言 | 结果 | 证据（方法体内偏移） |
|---|---|---|---|
| ① | 复用分支在 `account == null` 之后 | **PASS** | `null-check@601 < reuse@795 < var tokenGuid@1235` |
| ② | `customToken` 非空时不走复用 | **PASS** | 条件以 `string.IsNullOrEmpty(customToken) &&` 开头，且位于 `if (` 之后 |
| ③ | 复用分支返回的 `MxToken` 取自 `_reuseExisting.Token` | **PASS** | `MxToken = _reuseExisting.Token.ToString()` |
| ④ | `LastActivity` 被更新 | **PASS** | `_reuseExisting.LastActivity = DateTime.UtcNow;` |
| ⑤ | `PersistSessions()` 被调用 | **PASS** | 复用分支区间内含 `PersistSessions();`（全文件调用点 2 → 3 处） |

配套检查（同一次 `--verify`）：

```
[OK ] sha256 属于已知状态            (PATCHED / 8245 B)
[OK ] 锚点 'if (account == null) return null;' 唯一   (1 个)
[OK ] 标记 [BAPATCH-SESSION-REUSE v1] 残留            (1 个（预期 1）)
[OK ] AddOrUpdate 行存在且唯一（原逻辑未被动过）      (1 个)
[OK ] PersistSessions() 调用点                        (3 处（预期 3）)
[OK ] GenerateSession 方法体可定位
[OK ] GenerateSession 方法体大括号平衡                ({=5 }=5)
[OK ] 插入块缩进与所在方法体一致                      (12 空格（期望 12）)
result : PASS
```

缩进断言是**动态取的**：把插入块首行缩进与同方法体内 `_activeSessions.AddOrUpdate(...)` 行的缩进比对，必须都等于 12 空格。

### 6.2 “两次连续 `GenerateSession(同一 publisherId)` 现在会返回同一个 `MxToken`” 的依据

按补丁后的源码路径逐行推演（**不带 `customToken`，`account` 非空**，`_activeSessions` 键 = `account.ServerId`）：

**第 1 次调用（该账号无会话）**

| 步骤 | 代码 | 结果 |
|---|---|---|
| 查账号 | L81-87 | `account != null` |
| 复用分支 | L94 `TryGetValue(account.ServerId, ...)` | **false**（无条目）⇒ 不进分支 |
| 铸 token | L105-107 `Guid.NewGuid()` | `T` |
| 建档 | L109-115 `new ActiveSession { Token = T }` | — |
| 覆盖 | L117 `AddOrUpdate(ServerId, session, ...)` | `_activeSessions[ServerId] = {Token=T}` |
| 返回 | L120-124 | `MxToken = T` |

**第 2 次调用（同一 `publisherId`，`account` 同一个 `ServerId`）**

| 步骤 | 代码 | 结果 |
|---|---|---|
| 查账号 | L81-87 | 同一个 `account.ServerId` |
| 复用分支 | L94 `IsNullOrEmpty(null)==true` && `TryGetValue(ServerId)` | **true**（条目在） |
| 走分支 | L96 `LastActivity = UtcNow` → L97 `PersistSessions()` | 刷新 + 落盘 |
| 返回 | L98-102 `MxToken = _reuseExisting.Token.ToString()` | `= T`（同一个 Guid） |
| 不执行 | L105-124 | **不再 `Guid.NewGuid()`、不再 `AddOrUpdate`** |

⇒ 两次返回的 `MxToken` **字符串完全相同**；`_activeSessions[ServerId].Token` 也没被替换，所以第 1 次发出去的 token 在若干次重铸之后**依然有效** —— 这正是要消掉的 86 次 `Session expired or invalid` 的成因。

（`customToken` 非空时 L94 第一个条件为 false，直接落到 L105-124 的旧逻辑：用 `Guid.Parse(customToken)` 建档并 `AddOrUpdate` 覆盖 —— 旧语义保留，已在 6.3 场景 3 验证。）

### 6.3 控制流等价复刻（纯 Python，逐句照抄 C# 分支）

`_shittim_session/reuse_sim.py` 把 `GenerateSession` / `ValidateRequest` 的控制流按行翻译成 Python，在**同一个进程**里分别跑 `reuse=False`（基线）和 `reuse=True`（补丁）两种实现。实跑结果（`reuse_sim.log`）：

```
[场景 1] 基线逻辑：同一 publisherId 连续两次铸会话
  [OK ] 第一次铸会话后 token 可用
  [OK ] 重铸后旧 token 被作废（bug 复现，期望不可用）        (Session token mismatch)
  [OK ] 两次 MxToken 不同（这就是 bug）                   454ccd28 vs 6149eede
  [OK ] 会话被清掉后 -> 线上那条 'Session expired or invalid'  (Session expired or invalid)

[场景 2] 打完补丁：同一 publisherId 连续两次铸会话
  [OK ] 第二次铸会话后旧 token 仍可用                       (OK)
  [OK ] 两次 MxToken 相同                                  accbff90 == accbff90
  [OK ] 第三次仍然相同（幂等）
  [OK ] 复用路径没有生成新 Guid                            Guid.NewGuid() 调用 1 次（后两次走复用 0 次）
  [OK ] 复用路径刷新 LastActivity
  [OK ] 复用路径调用 PersistSessions()
  [OK ] _activeSessions 里该账号仍只有 1 个会话

[场景 3] customToken 非空：仍按旧逻辑新建（原语义不变）
  [OK ] customToken 被原样采用
  [OK ] customToken 覆盖了旧会话（旧 token 现在失效）
  [OK ] customToken 路径不生成新 Guid（走 Guid.Parse 原值）

[场景 4] 不同 publisherId 各拿各的 token（未串号）
  [OK ] 两个账号 token 不同
  [OK ] 各自重复铸会话保持各自 token
result : PASS
```

**边界**：这是算法/控制流等价验证，**不是** `Shittim-Server.dll` 的运行时验证；它不能证明编译产物在真实服务里的行为，只能证明“这段逻辑改对了”。

### 6.4 运行时验证怎么做（上线后）

1. `grep -c 'Session expired or invalid' /root/srv_run.log` —— 补丁前窗口内 86 次，补丁后同口径应接近 0；
2. 重铸频次（170 次请求里 48 次）应显著下降，不再每几次请求就换一次 token；
3. 若仍出问题，表现会是 `Session token mismatch`（而不是 expired），说明有别的路径在重建会话（例如 `customToken` 被显式传入）。

---

## 7. 可重复构建（两个方向都实测）

**回滚方向**：

```
rollback  → SessionKeyService.cs sha256 = 377e8a1a… (7,606 B, 精确回到基线)
dotnet build -c Release → Shittim-Server.dll
         → 2,669,568 B, sha256 = 73e487c813bb2c9e7ba86e731a3f527090e6ee569f4dd6b9158b2658ccf93cff
```

与最初（未做任何改动时）的 DLL **逐字节相同**。

**补丁方向**（全量重编，排除增量缓存干扰）：

```
apply     → SessionKeyService.cs sha256 = 40517d88… (8,245 B)
dotnet build -c Release --no-incremental → Shittim-Server.dll
         → 2,669,568 B, sha256 = 01f5b906159d81b883f86c03df599bcd7936a26ef7db72c62e75d079946a4a18
         → 与留档副本逐字节相同
```

两个方向都是确定性的 ⇒ 这台机器上的 Release 构建可复现，源码 ↔ DLL 的对应关系可信（也是“本地源码与线上那份同源”的旁证）。

---

## 8. 上线步骤（人工执行；本 agent 未联网、未上传任何东西）

线上布局（取自仓库内 `work/ba/run_srv.sh`）：

```
程序目录 : /www/wwwroot/ba_srv/Shittim-Server.dll
运行时   : /root/dotnet10/dotnet Shittim-Server.dll
日志     : /root/srv_run.log（run_srv.sh）或 /root/s5.log（deploy.sh）
会话侧车 : /www/wwwroot/ba_srv/Config/sessions.json   ← 不要删
```

1. **备份线上原 DLL**（先算 sha 留证）

   ```bash
   cd /www/wwwroot/ba_srv
   sha256sum Shittim-Server.dll            # 存证；若 = 73e487c8… 说明线上那份与本地基线逐字节一致
   cp -a Shittim-Server.dll Shittim-Server.dll.orig.$(date +%Y%m%d-%H%M%S)
   ```

2. **只上传一个文件**：`Shittim-Server.dll`（本地产物见第 5 节；路径
   `work\ba\server\deploy\_shittim_session\Shittim-Server.patched.01f5b906159d.dll`）。
   **不要上传 `Schale.dll`**，它没变（`73965be6…`）；也不要整目录覆盖。

   ```bash
   # 示例模板（用户名/端口按实际填；本 agent 没有执行）
   scp -P <PORT> ./Shittim-Server.patched.01f5b906159d.dll <USER>@<HOST>:/www/wwwroot/ba_srv/Shittim-Server.dll
   ```

3. **校验落地的 DLL**

   ```bash
   cd /www/wwwroot/ba_srv
   sha256sum Shittim-Server.dll    # 必须 = 01f5b906159d81b883f86c03df599bcd7936a26ef7db72c62e75d079946a4a18
   stat -c '%s' Shittim-Server.dll # 2,669,568
   sha256sum Schale.dll            # 必须仍 = 73965be6…（未变）
   ```

4. **重启进程**（`pkill` 后按原命令拉起；`Config/sessions.json` 会被 `LoadPersistedSessions` 读回，
   已登录客户端的 token 不会因为重启而失效）

   ```bash
   pkill -9 -f Shittim-Server.dll; sleep 2
   cd /www/wwwroot/ba_srv
   export DOTNET_ROOT=/root/dotnet10 DOTNET_GCHeapHardLimit=0x20000000 DOTNET_gcServer=0
   setsid /root/dotnet10/dotnet Shittim-Server.dll > /root/srv_run.log 2>&1 < /dev/null &
   sleep 50; ss -tln | grep -E ':5000|:5100'; tail -6 /root/srv_run.log | cut -c1-130
   ```

5. **观察**（见 6.4）：`Session expired or invalid` 应停止增长；`Account_CheckNexon` 反复重连不再把
   正在跑请求的 token 打掉。

6. **出问题立刻回滚**（第 9 节 A 方案，30 秒）。

---

## 9. 回滚步骤

### A. 换回原 DLL（最快，推荐）

```bash
cd /www/wwwroot/ba_srv
ls -1t Shittim-Server.dll.orig.* | head -1                 # 第 8.1 步的备份
cp -a "$(ls -1t Shittim-Server.dll.orig.* | head -1)" Shittim-Server.dll
sha256sum Shittim-Server.dll                               # 必须 = 73e487c8…
pkill -9 -f Shittim-Server.dll; sleep 2
export DOTNET_ROOT=/root/dotnet10 DOTNET_GCHeapHardLimit=0x20000000 DOTNET_gcServer=0
setsid /root/dotnet10/dotnet Shittim-Server.dll > /root/srv_run.log 2>&1 < /dev/null &
```

### B. 源码回滚 + 重编（本地，已验证可精确回到基线）

```powershell
# 1) 源码回滚（默认用脚本自动生成的备份；--rollback 幂等）
python work\ba\server\deploy\patch_shittim_session.py --rollback
python work\ba\server\deploy\patch_shittim_session.py --verify     # state: BASELINE, result: PASS

# 2) 重编，sha 必须回到 73e487c8…
& 'C:\Program Files\dotnet\dotnet.exe' build `
    'work\ba\srv_src\Shittim-Server\Shittim-Server.csproj' -c Release --nologo
```

第 7 节已实测：回滚后重编得到的 `Shittim-Server.dll` = **2,669,568 B / `73e487c8…`**，与原始基线逐字节相同。

### C. 手工回滚（不想用脚本时）

删除 `SessionKeyService.cs` 中从 `// [BAPATCH-SESSION-REUSE v1]` 那一行开始、到紧随其后的
`            }`（复用分支右花括号）为止的 **12 行**，保留原本那一个空行，文件应回到
**7,606 B / `377e8a1aff868f913c205b016659ca9b0620f6a9813c2639507e63134d9b9560`**。

### D. 其它可用的还原源

- 脚本自动备份（现有两个，内容相同，都是 7,606 B 基线）：
  `work\ba\srv_src\Shittim-Server\Services\SessionKeyService.cs.bapseb.bak.20261117-025029`
  `work\ba\srv_src\Shittim-Server\Services\SessionKeyService.cs.bapseb.bak.20261117-025255`
- 完整未改动副本：`work\ba\srv_src_orig\`（含 `SessionKeyService.cs`，与 `srv_src` 逐文件一致）
- 原始源码包：`work\ba\srv_src\shittim_src_20261117-024413.tgz`

---

## 10. 脚本用法与幂等性

```powershell
python work\ba\server\deploy\patch_shittim_session.py --verify           # 只读：sha + 锚点 + 5 条结构断言
python work\ba\server\deploy\patch_shittim_session.py --dry-run          # 打印 unified diff，不写盘
python work\ba\server\deploy\patch_shittim_session.py --apply            # 备份 -> 原子写 -> 打印新 sha
python work\ba\server\deploy\patch_shittim_session.py --rollback         # 备份还原 -> 校验 sha 回到基线
python work\ba\server\deploy\patch_shittim_session.py --src <SRC_ROOT>   # 默认自动定位 work\ba\srv_src
python work\ba\server\deploy\patch_shittim_session.py --verify --expect-sha <hex>
```

- **状态机**：`BASELINE`（按基线 sha）/ `PATCHED`（按补丁 sha + 标记 1 个）/ 其它 → 一律**拒绝写入**，不猜。
- **幂等**：重复 `--apply` 不再备份、不写文件，sha 恒为 `40517d88…`；基线态 `--rollback` 是 no-op。
- **安全检查**：写前验证（a）生成结果的 sha 必须等于写死的 `PATCHED_SHA256`，（b）5 条结构断言全过，
  （c）备份写入后回读校验 sha —— 任一失败即中止，不落盘。
- **备份命名**：`<源文件名>.bapseb.bak.<YYYYmmdd-HHMMSS>`，回滚后保留（不删，便于审计）。
- **无备份也能回滚**：`--rollback` 找不到有效备份时按“精确删除标记块”反补丁，并同样校验 sha 回到基线。

---

## 11. 证据文件

都在 `work\ba\server\deploy\_shittim_session\`（原样日志，未编辑）：

| 文件 | 内容 |
|---|---|
| `hashes.txt` | 所有 sha256 / 字节数 / 编译统计汇总 |
| `verify_baseline.log` | 基线态 `--verify`（state: BASELINE, PASS） |
| `dryrun.log` | `--dry-run` 的完整 diff |
| `apply.log` / `apply_again_idempotent.log` | 第一次 `--apply`（备份+写入）与第二次（no-op） |
| `verify_patched.log` | 补丁态 `--verify`：5 条断言逐条 PASS |
| `patched_GenerateSession.txt` | 补丁后 `GenerateSession` 方法体（带源码行号） |
| `build_patched.log` | 补丁后 Release 编译（0 错误 / 255 警告，增量） |
| `build_patched_full_rebuild.log` | 补丁后全量重编（0 错误 / 265 警告，复现 `01f5b906…`） |
| `build_baseline_incremental.log` / `build_baseline_noincremental.log` | 基线态两次编译（说明可重复构建） |
| `build_baseline_full_rebuild.log` | 回滚后最后一次全量重编（265 警告 / 0 错误，回到 `73e487c8…`） |
| `reuse_sim.py` / `reuse_sim.log` | 控制流等价复刻及其输出（旧 vs 新四场景） |
| `rollback.log` / `rollback_again_idempotent.log` | 回滚（备份还原）与再次回滚（no-op） |
| `build_after_rollback.log` | 回滚后重编（sha 精确回到基线） |
| `verify_final_baseline.log` | 最终态 `--verify`（state: BASELINE, PASS） |
| `source_tree_manifest_cmp.log` | `srv_src` vs `srv_src_orig` 逐文件 sha256 对比（1304 文件全一致） |
| `Shittim-Server.patched.01f5b906159d.dll` | 补丁后的 Release DLL（上传用） |

交付脚本本身：`work\ba\server\deploy\patch_shittim_session.py`
**24,262 B / sha256 `0467390148f45233a78d70618447bb8b2a760fb961d16c9cd1fec42d2a7f5caa`**

---

## 12. 沙箱最终状态（干净）

| 项 | 状态 | sha256 |
|---|---|---|
| `work\ba\srv_src\...\SessionKeyService.cs` | **已回滚到基线**（7,606 B） | `377e8a1aff868f913c205b016659ca9b0620f6a9813c2639507e63134d9b9560` |
| `Shittim-Server.dll`（bin/obj 与 Release） | **已重编回基线**（2,669,568 B） | `73e487c813bb2c9e7ba86e731a3f527090e6ee569f4dd6b9158b2658ccf93cff` |
| `Schale.dll` | 未变 | `73965be6d62b1f9ddfecff765e8aa6195682229c1f1fe201dcfb90acf183cf38` |
| `srv_src` vs `srv_src_orig` | 1304 个源文件（排除 `bin/`、`obj/`）**逐文件 sha256 全一致** | — |

保留物（有意留下的）：

- 源码备份两份（内容相同，均 7,606 B 基线）：
  `SessionKeyService.cs.bapseb.bak.20261117-025029`、`...20261117-025255`；
- 未改动完整副本 `work\ba\srv_src_orig\`（1764 文件 / 248,053,145 B）；
- 证据目录 `work\ba\server\deploy\_shittim_session\`（含补丁后 DLL）。

⇒ **沙箱现在是“源码已回滚 + DLL 已重编回基线”的干净状态，不是打了补丁的状态。**
要复核补丁，再跑一次 `--apply` + `dotnet build` 即可（脚本已验证可重复）。

---

## 13. 诚实声明：做了什么 / 没做什么

**做了**：源码副本、单点插入、编译（Release，0 错误）、sha256/字节数取证、5 条结构断言、
控制流路径推演、控制流 Python 等价复刻、回滚、回滚后重编的字节级一致性验证、源码树逐文件对比。

**没做**（也不会假装做了）：

- ❌ 没有启动 Shittim-Server，没有发任何真实协议请求 ⇒ **没有运行时验证**；
- ❌ 没有 ssh / scp / 上传 / 连服务器；
- ❌ 没有跑 `Shittim-Server.Tests`（`InternalsVisibleTo` 存在，但测试项目不在本次改动范围内；
  且本补丁只改公开方法内部，不影响 internal 契约）；
- ⚠️ `--verify` 的结构断言基于“去注释 + 大括号配对 + 位置/正则”，**不是完整 C# AST 解析**
  （若将来方法里出现内嵌字符串花括号会误判，本方法内没有）。

运行时是否真的把 86 次 `Session expired or invalid` 清零，只能上线后看 `/root/srv_run.log` 的计数。
