# C# 会话幂等化补丁 —— 记录与证据

完成时间：2026-11-17 02:44 ~ 02:57。作者：Lead（下发 + 验证），执行：一次性 subagent + `srv-ops`。

---

## 为什么改

Shittim 侧 `Session expired or invalid` 累计出现 **86 次**，受害者覆盖 `Scenario_Skip`、`Mission_List`、`Account_SetTutorial`、`Toast_List`、`MiniGame_MissionList`、`Event_RewardIncrease` 等一大片协议。

文案分布实测：
```
Session expired or invalid    86 次   ← 就是这个
Session token mismatch         1 次
Session key is required        0 次
```

根因（`SessionKeyService.cs`）：
- `:14` `_activeSessions` 是 `ConcurrentDictionary<long, ActiveSession>` —— **一个账号只能有一个会话**
- `:104` `AddOrUpdate(account.ServerId, session, (_, _) => session)` —— **每铸一次就把旧的作废**
- `:152-153` 在途请求拿旧 token 去查 → 查不到 → `Session expired or invalid`

而桥在 170 次请求里重铸了 **48 次**（`session_source: fresh 48 / cache 122`）。

`Scenario_Skip` 崩在这里 ⇒ 教程卡在第 3 步 ⇒ 客户端再也不发超过 `[1,2]` 的教程进度 ⇒ 用户看到"过完了却要重头来"。

---

## 改了什么

`Shittim-Server/Services/SessionKeyService.cs` 的 `GenerateSession`，在 `account == null` 检查之后插入 12 行：

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

**没有动** `ValidateRequest` / `GetAuthenticatedUser` / `RevokeSession` / `PurgeExpiredSessions`。
`customToken` 显式给定时仍走旧逻辑（新建）。

---

## 文件身份

| 项 | 字节 | sha256 |
|---|---|---|
| 补丁脚本 `patch_shittim_session.py` | 24,262 | `0467390148f45233a78d70618447bb8b2a760fb961d16c9cd1fec42d2a7f5caa` |
| 说明 `SHITTIM_SESSION_PATCH.md` | 28,542 | `f179d6f401aa3ccaef34ef173e7d29677268430df3dfedd01d949b47b8d6e4c3` |
| 源码 基线 `SessionKeyService.cs` | 7,606 | `377e8a1aff868f913c205b016659ca9b0620f6a9813c2639507e63134d9b9560` |
| 源码 补丁态 | 8,245 | `40517d883da97964fe73f2365f747faf4d16ff0fe0c488f3ab5736c25b2336b9` |
| **DLL 补丁态** | 2,669,568 | **`01f5b906159d81b883f86c03df599bcd7936a26ef7db72c62e75d079946a4a18`** |
| DLL 本地回滚重编 | 2,669,568 | `73e487c813bb2c9e7ba86e731a3f527090e6ee569f4dd6b9158b2658ccf93cff` |
| DLL 服务器原始 | 2,669,568 | `2a97a92281aab287ebf246d6dab9108feee914123539bb6d03ad12bb276aaeac` |
| `Schale.dll`（未变） | 5,392,384 | `269c009a630c3668fd27af6c8a8b4acab3658f33027c5d140ebd9dabcf1ca2fa` |

⚠️ **三个 DLL 字节数完全相同、sha256 各不相同。判断新旧必须用 sha256，绝不能用字节数。**

原因：新增 IL 落在 PE 对齐填充内，section 长度不变；而本地重编与服务器原件之间的差异来自 .NET 非确定性构建（嵌入源路径 / MVID）。

---

## 构建可重复性（已验证）

```
本地 Release 编译补丁态   → 2,669,568 B / 01f5b906…   （与交付方独立编译结果一致）
源码 --rollback 后重编     → 2,669,568 B / 73e487c8…   （精确等于我的基线）
--no-incremental 全量重编  → 同上，精确
```
⇒ **我们的构建是确定可重复的**，"我编出来的 DLL"不是黑盒。

---

## 上线记录

```
备份  /www/wwwroot/ba_srv/Shittim-Server.dll.orig.20261117-025444   （2a97a922…，回滚源）
替换  /www/wwwroot/ba_srv/Shittim-Server.dll → 01f5b906…
重启  systemctl stop/start ba-shittim（tmux + --console --id 2 的写法保持不变）
结果  active；5000 / 5100 / 6667 全 LISTEN；Schale.dll 未动；sessions.json 未删未改
```

启动日志里的 `Failed to fetch version from PureAPK` / `SSL connection could not be established` 是**外网版本查询失败**（被我们自己的 SNI 劫持挡住），回落缓存后正常启动，**每次重启都有，与本次替换无关**。

---

## 效果验证（直接测补丁本身，不靠客户端）

连续三次 `Account_CheckNexon(1014)`：

```
round 1: MxToken=06389347-5ce5-420c-9299-7a10a5325548   397 ms   ← 首次，走完整路径
round 2: MxToken=06389347-5ce5-420c-9299-7a10a5325548    16 ms   ← 复用快路径
round 3: MxToken=06389347-5ce5-420c-9299-7a10a5325548    10 ms

distinct tokens = 1      idempotent = True
```

`sessions.json` 探针前后对照：
```
BEFORE  UserId=2 Token=06389347-…   CreatedAt 18:40:51Z   LastActivity 18:40:51Z
AFTER   UserId=2 Token=06389347-…   CreatedAt 18:40:51Z   LastActivity 18:56:04Z   ← 只有这一个字段变
```

Shittim pane：**`Session expired or invalid` 计数 = 0**。

⇒ 补丁确实被加载且生效。

---

## 回滚

```bash
systemctl stop ba-shittim
cp -a /www/wwwroot/ba_srv/Shittim-Server.dll.orig.20261117-025444 /www/wwwroot/ba_srv/Shittim-Server.dll
sha256sum /www/wwwroot/ba_srv/Shittim-Server.dll      # 必须回到 2a97a922…
systemctl start ba-shittim
```

源码侧回滚：`python3 patch_shittim_session.py --rollback`（已验证精确回到 `377e8a1a…`）+ 重编。

---

## 还没验证的部分（诚实标注）

- **没有跑真客户端**。上面的验证只证明"会话不再互踢"，**不证明教程能过第 3 步**。
- 即使会话修好，`Scenario_Skip` 是否真的不再抛异常、教程是否能推进，**必须等真客户端登录才能确认**。
- 记忆大厅那条链（桃信 → `ParcelType.MemoryLobby` → `MemoryLobbies`）**仍然是空的**，是独立的第三件事。
