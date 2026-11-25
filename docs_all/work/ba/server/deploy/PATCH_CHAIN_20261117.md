# 补丁链现状（截至 2026-11-17 03:10）

## 链（自上而下 = 应用顺序）

| 层 | 产物字节 | 产物 sha256 | 开关 |
|---|---|---|---|
| `patch_3` | 103,900 | `563c1942…4ffc5c8` | `cn_3.txt=1` |
| `patch_relay` | 115,911 | `37717680…6e815a07` | `cn_relay_unknown.txt=1` |
| `patch_relay2` | 128,309 | `e5fb03b8…66f5581` | `cn_relay_known.txt=1` |
| `patch_relay_fix` | 136,894 | `60f34664…0e785ee` | 无新开关 |
| `patch_relay_fix2` | **141,066** | `aefb38a8…76642b65` | 无新开关 ← **当前线上** |

**管线红线**
- 应用顺序：`relay → relay2 → relayfix → relayfix2`
- 打完 `fix2` 后**不能再单独重跑前四层的 `--apply`**（会整块覆盖各自的载荷，把后面的修复冲掉）
- 反向卸载**必须先 `patch_relay_fix2.py --rollback`**，再往前一层层卸

## 03:10 前后的实测

- `patch_relay_fix2` 已上线（新 pid 2577633），`--verify` 24/24、`--apply` 自检 32 项**零 FAIL**
- **Shittim 的 DLL 一个字都没动**：`Shittim-Server.dll` 仍是 `2a97a922…` / 2,669,568 B / mtime 2026-11-13
- `sessions.json` 里 `UserId=2` 的 token 又变了一次（`0793ebba…` → `06389347…`）—— **"C# 会话互踢"的现场证据**

---

## 两个已更正的结论（推翻我此前的判断）

### ① `SetTutorial` 没有 bug

```csharp
AccountHandler.cs:691-694   else { tutorial.TutorialIds = request.TutorialIds.ToList(); }   ← 更新分支存在
AccountHandler.cs:696       await db.SaveChangesAsync();                                      ← 在 if/else 之外，两路都落盘
```
语义是**全量覆盖**。所以"只在新建时赋值"的怀疑**不成立，已作废**。

`[1,2]` 的真相：客户端最后一次真的只报了 2 步 —— 因为卡在第 3 步（跳过剧情）过不去。
**"重登要重新过教程"是症状，不是独立的持久化 bug。**

### ② `Scenario_Skip` 抛的是会话异常，不是数据异常

`ScenarioHandler.cs:47-56` 的 `Skip()` 方法体只有 4 行，`:53` 就是 `GetAuthenticatedUser`。

实测文案分布：
```
Session expired or invalid    86 次   ← 就是这个
Session token mismatch         1 次
Session key is required        0 次
```
⇒ 修法方向是"**会话表对不上**"，不是"请求没带 key"。

---

## 会话根因与根治方案

`SessionKeyService.cs:14` 的 `_activeSessions` 是 `ConcurrentDictionary<long, ActiveSession>` —— **一个账号只能有一个会话**。
`:104` 的 `AddOrUpdate` 每铸一次就覆盖旧的，在途请求随即在 `:152-153` 被判 `Session expired or invalid`。
桥那边在 170 次请求里重铸了 **48 次**。

**根治**：`GenerateSession` 改成**幂等** —— 同账号已有有效会话时复用原 token，不新建。改动约 5 行，只碰这一个方法。

---

## 本地编译链（已验证可用）

```
dotnet   C:\Program Files\dotnet\dotnet.exe     SDK 10.0.101 / 10.0.301
源码     work\ba\srv_src\      （Shittim-Server + Schale，从服务器 tar 拉回，双侧 sha256 一致）
```

**Release 构建产物与服务器字节数完全一致**：
```
Shittim-Server.dll  2,669,568 B      Schale.dll  5,392,384 B
```
⇒ **源码同源已确认**。服务器用的是 Release + portable pdb（所以带 .pdb 和行号），不是 Debug（Debug 构建字节数不符）。

**编译命令**（在 `work\ba\srv_src` 下）：
```
dotnet build Shittim-Server\Shittim-Server.csproj -c Release
```
注意：**没有 .sln**，必须直接 build csproj；`Shittim-Server.csproj` 通过 `ProjectReference` 依赖 `..\Schale\Schale.csproj`，所以 `Schale` 目录必须在。

---

## 上线 DLL 的方式

1. 只传 `Shittim-Server.dll` **一个文件**
2. `Schale.dll` 不变（sha 必须仍是 `73965be6d62b1f9ddfecff765e8aa6195682229c1f1fe201dcfb90acf183cf38`）
3. 服务器上先备份原 DLL，回滚 = 换回来
4. 替换后 `systemctl restart ba-shittim`（注意它现在是 tmux 包一层 + `--console --id 2` 的写法）
