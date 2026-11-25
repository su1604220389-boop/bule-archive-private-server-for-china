# 48 · 登录卡死点：await 结构与推送依赖分析

> 输入（只读）：`work\ba\audit\ba-work\x\assets\bin\Data\Managed\Metadata\global-metadata.dat`（38,426,024 B）
> 方法：纯离线静态分析；四层编码（明文 / XOR 0x20 / 0x01 / 0x0E）全扫
> 脚本：`report\_tmp\meta\s12_ident.py`、`s13_group.py`、`all_ascii.tsv`（带真实偏移）
> 日期：2026-11-14

---

## 0. 一页结论

**卡死点不在 HTTP、不在解析异常，而在「NetworkTask 的完成信号」这一跳。**

```
LoginTask 的某个协程
   └─ 创建 XxxNetworkTask
        └─ yield return HttpGameSession.WaitForRequest(...)      ← <WaitForRequest>d__59 @0x0021A802
             └─ 等待 HttpGameSession.IsFinished == true          ← @0x0021A583
                  └─ 只有 RequestHandler / ResponseHandler 被调用才会置位
                       └─ 而 handler 是按「响应 protocol」查表拿到的
                            └─ 查不到 ⇒ 没人调用任何回调 ⇒ 永不置位 ⇒ 协程永久挂起
```

**为什么"没有异常、没有弹窗"**：查表失败的分支是**返回空**，不是抛异常；
`NetworkErrorHandler` 也依赖"有人发现失败"，而这里连失败都没被感知。
于是 `OnLoginFinish` 不执行、`OnLoginFail` 不执行 —— 正是观测到的第 3/4 条现象。

**`LoginState` 枚举只有两个成员**（`0x0013FDD3`）：`Finished`（`0x13FDDE`）、`Failed`（`0x13FDE7`）。
**没有"进行中"这个状态** —— 所以「卡住」这件事在客户端状态里**根本无处表示**，
UI 只能表现为"按钮文字消失 + 永远不动"。

**我们缺的能力不是推送。** 登录链路对服务端主动推送**零依赖**（§6）。缺的是
**"让客户端把这个响应匹配到 `Account_Auth` 这个待处理会话上"** 的能力。

---

## 1. 查档（避免重复劳动）

| 档案 | 已覆盖 | 本篇关系 |
|---|---|---|
| `report\42-Shittim流程还原-Auth之后.md` | §3.1 服务端**零推送**（源码级四项证据）；§3.3 `Queuing_Ping` 只是健康探针；§3.2 无心跳超时；§5 判定树 | **不重复**。42 号是**服务端**视角，本篇是**客户端**视角 —— 互补 |
| `report\47-HandleAccountAuthResponseMessage拆解.md` | DTO 20 属性、信封 6 字段、无 ResultState | 不重复。47 讲"数据形状"，本篇讲"等待结构" |
| `report\39-...Account_Auth解析路径.md` | LoginTask 成员清单、状态机顺序 | 本篇在其上补**编译器生成名**（协程/局部变量/闭包）的结构证据 |

查档结论：**client 侧的 await/协程结构此前无人做过**，本篇是新的。

---

## 2. 方法学与硬限制（先说清楚，避免把推断当事实）

`global-metadata.dat` **没有函数体**，C# 控制流被编译进 `libil2cpp.so` 的原生代码，
而 `methodPointer` 因表头被混淆（magic `0x12724394` ≠ `0xFAB11BAF`）取不到。
⇒ **本篇不做"控制流还原"这种做不到的事**，只做一件事：

> **用编译器生成的符号名，反推每个方法的"等待形态"。**

依据是 C# 编译器对 `async` / `yield` / 闭包 / 局部函数的**固定命名法**（Roslyn 的规则，跨版本稳定）：

| 符号形态 | 含义 | 对本问题的意义 |
|---|---|---|
| `<Method>d__N` | 该方法被编译成**状态机**（`async` 或 `yield return`） | 有它 ⇒ 该方法**会挂起**，可能永不返回 |
| `<var>5__N` | 该方法的**局部变量**被提升进状态机 | 出现 `networkTask` / `taskQueue` ⇒ 该方法**持有一个网络任务/队列在等** |
| `<Method>b__N_M` | 方法内的 **lambda** | 通常是回调（成功/失败各一个） |
| `<Method>g__Name\|N_M` | 方法内的**局部函数** | 辅助逻辑 |

这些都是**字节级可查的字符串**，不是猜测。

---

## 3. Q1：`HandleAccountAuthResponseMessage` 之后，卡在哪一跳

### 3.1 先给一个确定结论：`HandleAccountAuthResponseMessage` **本身是同步方法**

`0x13F600`–`0x141400` 区间内（LoginTask 的全部编译器生成名，共 **104 条**）
**没有** `<HandleAccountAuthResponseMessage>d__N`。

⇒ 它**不是** `async`、**不是** `yield`，**进去处理完就返回**，本身不会挂起。
⇒ **卡死点不在这里** —— 这与 lead 的观察（不是它抛异常）一致，也把嫌疑推向下游。

### 3.2 真正的等待结构：五条硬证据

| # | 证据（真实偏移） | 含义 |
|---|---|---|
| 1 | `<WaitForRequest>d__59` @`0x0021A802` | `HttpGameSession.WaitForRequest` 是**协程**（`yield`），它是"等一个网络请求完成"的实现 |
| 2 | `get_IsFinished` @`0x0021A583`、`IsFinished` @`0x0021A5B3` | 等待的条件就是 `IsFinished` |
| 3 | `RequestState` @`0x0021A544`、`RetryCount` @`0x0021A551`、`Elapsed`、`TimeOut` @`0x0021A770` | 会话对象带着状态/重试/超时字段 |
| 4 | `<networkTask>5__2` @`0x00140011` | **某个协程把 `networkTask` 提升成了状态机局部变量** ⇒ 该协程在"等这个任务" |
| 5 | `<taskQueue>5__2` @`0x001405EF` + `queueState` @`0x001405C6` + `errorExist` @`0x0014059E` | `LoginTask` 有一套**串行任务队列**（§5） |

`HttpGameSession` 的完整成员（`0x21A5BE`–`0x21A830`，与 47 号互补）：
`get_Session` / `get_IsFinished` / `ResponseHandler` / `NetworkErrorHandler` / `RequestHandler` /
`Elapsed` / `TimeOut` / `isGatewayBypassed` / `SetSessionParameters` / `HandleServerError` /
`BuildErrorMessage` / `Resend` / **`WaitForRequest`** / `httpMessage`。

**关键点：`ResponseHandler` 与 `NetworkErrorHandler` 是两个独立回调。**
如果响应既没被认领为"成功"、也没被识别为"失败"，**两个回调都不会被调用** →
`IsFinished` 永远不置位 → `WaitForRequest` 协程永远 `yield` 下去。

### 3.3 所以"卡死点"的精确表述

> **卡死在 `HttpGameSession.WaitForRequest` 的 `IsFinished` 条件上。**

它不是死锁、不是信号量、不是 `while(!flag)` 空转（那些都会耗 CPU，而且客户端会卡 UI）；
它是**Unity 协程 `yield return` 了一个永远不完成的对象** —— 每帧检查一次，条件永远假。
表现就是：进程正常、CPU 正常、按钮消失（进入 loading/等待态）、零后续请求。

> **这是本轮唯一能同时解释全部 6 条观测的机制。**

### 3.4 为什么 90 秒没有超时？

`HttpGameSession` **有** `TimeOut` @`0x21A770` 字段，`NetworkService` 也有 `TIMEOUT` @`0x21A232`、`get_TIMEOUT` @`0x219E59`。

**逻辑推演（不是证据）**：
1. 若超时检查落在 `WaitForRequest` 的循环里、且每帧执行，90 秒内**必然**会触发 → 会走 `NetworkErrorHandler` → 会弹窗。
2. 我们**没有**看到弹窗 ⇒ 超时检查**要么不在这个循环里**，**要么被更早的分支跳过**。
3. 最自然的解释：超时只作用于 `Http1Message`/`Http2Message` 的 `UnityWebRequest.timeout`（HTTP 层）。
   **我们的 200 已经让 HTTP 层正常完成了**，所以 HTTP 超时根本不会被触发；
   而**游戏层**（等 `IsFinished`）没有任何超时。

⇒ **"回了 200 就再也不会超时"** —— 这解释了为什么是"永久"而不是"90 秒后报错"。

---

## 4. Q2：`RelayPackets` 是什么

### 4.1 它不是协议、不是长连接

| 检查 | 结果 |
|---|---|
| 431 条协议名（`_tmp\meta\protocols.txt`）里含 `Relay` | **0 条** |
| 全文件（raw 层）含 `Relay` 的标识符 | **只有 LoginTask 的 4 条**：`StartRequestRelayPackets`@`0x13F981`、`co_RelayPacketsProcess`@`0x13FBB6`、`<co_RelayPacketsProcess>b__0`@`0x140581`、`b__1`@`0x1405A9`、`d__60`@`0x1405D1` |
| 含 `Notify` 的协议 | `Order_Notify`@`0x22FDA3`、`Battle_Notify`@`0x22FDB0`、`Survey_Notify`@`0x22FDBE`、`Web_Notify`@`0x22FDCC`（都是**客户端主动轮询**的普通协议） |

⇒ **`RelayPackets` 完全是客户端内部概念**，不上线。

### 4.2 它是一个**串行网络任务队列**（强证据）

`co_RelayPacketsProcess` 的状态机局部变量/闭包清单（都在 `0x140581`–`0x1405EF` 这 110 字节内）：

```
0x140581 <co_RelayPacketsProcess>b__0
0x14059E errorExist                     ← 字段：是否已出错
0x1405A9 <co_RelayPacketsProcess>b__1
0x1405C6 queueState                     ← 字段：队列状态
0x1405D1 <co_RelayPacketsProcess>d__60   ← 协程本体
0x1405EF <taskQueue>5__2                ← 协程内的局部变量：队列
```

`taskQueue` + `queueState` + `errorExist` 三件套 = **"取一个任务 → 等它完成 → 出错就停 → 取下一个"** 的典型写法。

**这解释了 `LoginTask` 为什么长得像个调度器**：它下面挂着一堆 `co_*` 协程
（`co_SyncTutorialCompletionIds`@`0x0013F99A` / `<co_SyncTutorialCompletionIds>d__36`@`0x00140387`、
`co_SyncShopListTutorialGacha`@`0x0013FBD9`、
`co_RelayPacketsProcess`@`0x0013FBB6`），它们各自是"发一个请求并等回包"，由队列串起来。

### 4.3 对 lead 的直接结论

> **`RelayPackets` 不需要服务端推送。** 它等的是**自己发出的请求的回包**。
> 所以"服务端只回包、从不推包"**不是**卡死原因 —— 这一点与 42 号 §3.1 的结论一致，
> 现在从客户端侧独立验证了一遍。

---

## 5. Q4：沉默分支枚举（既不 `OnLoginFinish` 也不 `OnLoginFail` 的路径）

`LoginTask` 里能被观测到的"结束"动作只有两个：
`OnLoginFinish`@`0x13FAF0`、`OnLoginFail`@`0x13FBCD`。
`LoginState` 也只有 `Finished`/`Failed` 两个值。

⇒ **任何"协程挂起"都会落在两者之外**，因为挂起不是一次状态转移。以下按可能性排序：

| # | 沉默分支 | 机制 | 证据强度 |
|---|---|---|---|
| **S1** | **`WaitForRequest` 永不完成** | 响应既没被认领也没被判失败，两个回调都不调 | **推断（强）**：`ResponseHandler`/`NetworkErrorHandler` 双回调结构 + `IsFinished` |
| **S2** | **`co_RelayPacketsProcess` 队列停住** | 队列里某个任务永不完成，`queueState` 卡住，`errorExist` 为 false ⇒ 循环不退出也不报错 | 推断（中）：`taskQueue`/`queueState`/`errorExist` 三件套 |
| **S3** | **`AccountAuthStart` 的两个回调都没被调** | `<AccountAuthStart>b__20_0`@`0x13FC31` / `b__20_1`@`0x13FC4B` —— 请求发出时挂的成功/失败回调 | 推断（中）：两个 lambda 的存在是硬证据，哪个是成功哪个是失败不可知 |
| **S4** | **`SkipAccountCallname` 分支** | `<SkipAccountCallname>g__TTSSaveAndRequestAccountAuth\|56_1`@`0x13FD11` —— 局部函数里**先存 TTS 再发 Auth**；若 TTS 存档失败，可能既不前进也不报错 | 推断（弱） |
| **S5** | **`OnLoginFinish` 内部的 `g__CompletePatch` / `g__ContinuedContentProcess`** | `<OnLoginFinish>g__CompletePatch\|4`@`0x1404F0`、`<OnLoginFinish>g__ContinuedContentProcess\|5`@`0x140512` —— 完成后还要做补丁/续接内容；若卡在这里同样静默 | 推断（弱）：但这是**OnLoginFinish 之后**，与"没进 OnLoginFinish"矛盾，列此仅为完整性 |

**排除掉的**：`ErrorAccountAuth`@`0x13FB43`、`ErrorQueuingGetTicket`@`0x13F71B`、
`ErrorAccountCheckYostar`@`0x13F793`、`ErrorAccountCreate`、`ErrorAccountNickname`@`0x13F81A`、
`ErrorAccountCallname`@`0x13F854`、`ErrorContentSaveDiscard`@`0x13F886`
—— 这 7 个 `Error*` 方法**都是显式失败分支，会走 `OnLoginFail` 弹窗**。我们一个都没看到，
**这正是 lead 判断"不是失败、是被卡住"的客户端侧依据**，我完全同意。

---

## 6. Q3 / Q5：Nickname 的触发，以及客户端要不要推送

### 6.1 Nickname：客户端主动发，不是等服务端

| 证据 | 偏移 |
|---|---|
| `ShowNicknamePopup` | `0x0013F9B7` |
| `RequestAccountNickname` | `0x0013FC15` |
| `SetAccountNickname` | `0x0013FA75` |
| `Account_Nickname` 协议 | `0x0022D977` |
| `AccountDB.Nickname`（客户端按此判空） | 见 `report\42` §2.5「仅当 Nickname 为空」 |

⇒ **客户端主动**：`ShowNicknamePopup` 弹框 → 用户输入 → `SetAccountNickname` → `RequestAccountNickname`。
**没有观察到弹框** ⇒ 流程根本没走到 `ShowNicknamePopup`，与我们卡在 Auth 之后一致。

条件字段：`AccountDB.Nickname` 为空（`report\42` §2.5 的 Shittim 侧推断，客户端侧无独立证据）。

### 6.2 推送：登录链路零依赖；客户端确实有 Socket.IO 栈，但只给聊天用

| 检查 | 结果 |
|---|---|
| 客户端 metadata 里的 Socket.IO / 长连接库 | **有**：`LongPollingTransport`@`0x005F5288`、`LongPoll`@`0x005F5DD0`、`KeepAlive`@`0x005F5DD9`、`LongPollDelay`@`0x005F6118`、`heartbeat`@`0x00606733`、`webSocket`@`0x001D84DA` |
| 这些库属于谁 | **BestHTTP 的 SignalR/Socket.IO 实现**（同区全是 `BestHTTP.*` 的 TLS/HTTP2 类） |
| 游戏自己的用例 | **只有 IRC 聊天**：`ircGameObject`@`0x0021A15C`、`IrcJsonMessage`@`0x002591E3`、`ClanChattingNetworkException`@`0x00175089`、`ClanChattingChannelJoin`、`MX-GameLogic-Chat-*` 标签 |
| 登录链路是否用它 | **否**。`LoginTask` 的全部成员里没有任何 IRC/Socket/推送相关名；`RelayPackets` 是内部队列（§4） |

⇒ **Q5 结论：不需要给 bridge 加"主动推送"能力。**
唯一一个"准推送"面是公会聊天（Socket.IO），它发生在进大厅之后，与本卡点无关。

> ⚠️ 但必须记一笔：**`ServerNotification` 是位标志、由客户端请求触发**（42 号 §3.1 已证）。
> 登录完成后的红点/邮件通知，客户端会自己来拉；服务端**不需要**主动敲。

---

## 7. 那么"我们缺哪个能力"—— 一句话

> **缺的不是推送，也不是字段：缺的是"让客户端把这个响应认领给它正在等待的那个会话"。**

机制推演（**推断**，但与本轮所有观测一致）：

```
客户端发出 Account_Auth（AccountAuthStart 里挂上 b__20_0 / b__20_1 两个回调）
  → GameSessionManager.CreateSession 建一个待完成会话（sessionQueue / sessionSet @0x0021A0E1/0x0021A0EE）
  → 收到我们的 200
  → NetworkService.ParseReceivedString(receivedString) @0x00219D60
       → ParseProtocol @0x00219D1A  ← 从响应里取出"这是哪个协议"
       → ParsePacketString @0x00219D28
  → 按 protocol 找到待完成会话 → 调 ResponseHandler → IsFinished = true
      ↑ 如果 ParseProtocol 取出的东西匹配不上任何待完成会话 ⇒ 这一步**静默跳过**
  → LoginTask 的协程永远等不到 IsFinished ⇒ 卡死（不异常、不弹窗、不再发请求）
```

这条链同时解释了 lead 观测到的 6 条现象，而且**不要求"解析抛异常"** ——
与我们没有看到任何错误弹窗完全兼容。

---

## 8. 诚实标注

| 结论 | 状态 |
|---|---|
| `HandleAccountAuthResponseMessage` 是同步方法（无 `d__`） | **确证**（104 条生成名里没有） |
| `LoginState` 只有 `Finished`/`Failed` 两个成员 | **确证**（`0x13FDD3` 后紧跟这两个） |
| `HttpGameSession.WaitForRequest` 是协程，条件为 `IsFinished` | **确证**（`<WaitForRequest>d__59`、`get_IsFinished`） |
| `co_RelayPacketsProcess` 是带 `taskQueue`/`queueState`/`errorExist` 的队列协程 | **确证**（符号名），**语义为推断** |
| `RelayPackets` 不是线上协议 | **确证**（431 条协议名 0 命中） |
| 卡死点在 `WaitForRequest` / `IsFinished` | **推断（强）** —— 无函数体，无法直接看到挂起点 |
| 90 秒无超时的原因是"HTTP 层已完成，游戏层无超时" | **推断** —— `TimeOut` 字段存在，但无法确认它是否在等待循环里被检查 |
| 响应被"静默丢弃"而非"解析异常" | **推断（中强）** —— 与观测最吻合，但 `ParseProtocol` 内部行为不可见 |
| 登录链路不需要服务端推送 | **确证（客户端侧）** + 42 号服务端侧独立互证 |
| IRC/Socket.IO 只用于聊天 | **推断（中）** —— 库存在是确证，用途由命名空间推断 |

---

## 9. 给 lead 的最小实验集

1. **验证 S1（成本最低，一次请求）**：让响应里的 `protocol` 值与**请求里那个 26 字符 base32 值一模一样**
   （即回什么就认什么），而不是 `"Account_Auth"`。若客户端按 protocol 匹配会话，这一改就能让它认领。
   —— 这条把 E1 从"值要算对"降级成"值要回显"，风险小得多。
2. **验证 S1 的对照组**：把同一个 200 的 `protocol` 值改成随机串。
   若两种行为**完全一致**（都卡死），说明客户端确实在按 protocol 匹配，且**匹配失败是静默的** ——
   S1 成立，问题定性闭合。
3. **验证"是否真被卡住"**：logcat 抓 `WAITING_SERVER_RESPONSE` / `RECEIVED_SERVER_RESPONSE`
   （`NetworkService` 8 状态枚举，`0x219DB0`–`0x219E32`）。若停在 WAITING 永不 RECEIVED ⇒ S1 得到旁证。
4. **不要再做**：补 `MxToken`/`SessionKey`（47 号已证客户端无此属性）、等 90 秒看超时（本报告 §3.4 已解释为何不会有超时）。

---

# 附录 A（第 4 轮追加）：REST 路径是否进 `WaitForRequest`？DTO 里有没有 `protocol`？

> 本节回答 lead 的 Q1–Q4。**先说结论：Q2 可以定死，Q1 不能。**

## A.1 Q2 —— `AccountAuthResponse` 里**没有** `Protocol` 字段（可定死）

`0x0022AE81`–`0x0022B5AC` 的 20 个属性（47 号 §3 已逐条列出）：
`CurrentVersion` / `MinimumVersion` / `IsDevelopment` / `BattleValidation` / `UpdateRequired` /
`TTSCdnUri` / `AccountDB` / `RepurchasableMonthlyProductCountDBs` / `MonthlyProductParcel` /
`MonthlyProductMail` / `BiweeklyProductParcel` / `BiweeklyProductMail` / `WeeklyProductParcel` /
`WeeklyProductMail` / `IssueAlertInfos` / `DailyRecordDBs` / `OptionDB` / `AccountLimitedFlashSaleDBs` /
`Desc` / `FunctionClose`

**`Protocol` / `ProtocolName` / `PacketName`：一个都没有。**（区间内 `Protocol` 子串命中 0 次）

### ⚠️ 但这个"没有"**不能**推出「客户端不读 protocol」

因为 protocol 不在 DTO 上，而在**信封/解析层**：

| 证据 | 偏移 | 说明 |
|---|---|---|
| `HttpMessage.<Protocol>k__BackingField` | `0x0021A89B` | 信封基类 `HttpMessage` **有** `Protocol` 属性 |
| `get_Protocol` | `0x001D7554` | 其访问器 |
| `NetworkService.receivedString`（字段） | `0x00219D0B` | 收到的原始字符串 |
| `NetworkService.ParseReceivedString` | `0x00219D60` | 解析入口 |
| `NetworkService.ParseProtocol` | `0x00219D1A` | **专门拆出 protocol** |
| `NetworkService.ParsePacketString` | `0x00219D28` | 专门拆出 packet |

⇒ `ParseReceivedString` → `ParseProtocol` + `ParsePacketString` 这个三件套，
**本身就是"把响应字符串拆成 protocol 和 packet 两段"的实现**。
所以「客户端不读响应里的 protocol」这个说法**是错的**；它读，只是在信封层读，不在 DTO 上读。

> lead 原推论「DTO 没有 Protocol ⇒ protocol 匹配假设错」**不成立**。真正的疑问变成了 §A.2。

## A.2 Q1 —— REST 响应是否进 `WaitForRequest`：**静态不可判定**，且正反各有一条硬证据

### A.2.1 先给不可判定的事实

`global-metadata.dat` 无函数体，`methodPointer` 因表头混淆不可得（48 号 §2）。
**"从 BestHTTP `OnRequestFinished` 正向追到 `HandleAccountAuthResponseMessage`"这件事做不到**，
任何声称做到的说法都是编的。下面只给"类结构层面"的证据。

### A.2.2 反向证据：两套传输在**不同的类**里，解析在**第三个类**里

| 路径 | 类（真实偏移） | 该类自己的成员 |
|---|---|---|
| **Gateway** | **`NetworkSender` @`0x00219C8F`** | `responseHandler`@`219C9D`、`errorHandler`@`219CAD`、`requestHandler`@`219CBA`、**`SendRequestGateway`@`219CC9`**、`IsResendAble`@`219CDC`、`SendRequest`@`219CE9` |
| **API / REST** | **`GameSessionManager` @`0x00219E46`** | `ApiUrl`/`GatewayUrl`/`IsGatewayBypassed`、`sessionQueue`@`21A0E1`、`sessionSet`@`21A0EE`、`RemoveSession`@`219FE6`、**`SendRequestApi`@`0x0021A00C`**、**`CreateSession`@`0x0021A01B`**、`HandleSessionStateChangedMessage`@`21A029`、`PopupAndResend`@`21A08B` |
| **解析** | **`NetworkService` @`0x00219CFC`** | `receivedString`、`ParseProtocol`@`219D1A`、`ParsePacketString`@`219D28`、`ParseReceivedString`@`219D60`、`ShowDefaultNetworkError`@`219D3A` |

⇒ **`SendRequestApi` 与 `ParseProtocol` 不在同一个类里。**
若 REST 路径不调用 `NetworkService.ParseProtocol`，那"按 protocol 匹配会话"对 `/api/account/auth` 就不成立。

### A.2.3 正向证据：API 类自己就管会话

`GameSessionManager` **同时**拥有 `SendRequestApi` 和 `CreateSession` / `RemoveSession` /
`sessionQueue` / `sessionSet` / `HandleSessionStateChangedMessage`。
而等待原语 `WaitForRequest`（`<WaitForRequest>d__59`@`0x0021A802`）与 `IsFinished`@`0x0021A583`
都在 **`HttpGameSession` @`0x0021A5BE`** —— 即 `CreateSession` 造出来的那个对象。

⇒ **推断（中强）**：REST 响应确实会落到一个 `HttpGameSession` 上，`WaitForRequest` 成立。
⇒ **推断（中）**：但"用它来匹配 protocol"这一步未必发生。

### A.2.4 所以 Q1 的诚实答案

> **不能定。**正反各有一条结构性证据，强度都不足以支撑"花掉用户一次点击"。
> 而且——**即使 Q1 答"否"，48 号的"静默卡死"结论仍然成立**，
> 只是机制从「协程永不完成」换成「BestHTTP 回调触发了，但内部静默丢弃」。
> **变的只是解释，不变的是"客户端没有把响应交给 ResponseHandler"这个事实。**

## A.3 Q3 —— 谁决定这条请求"算完成"：候选集，无法唯一确定

从类结构能列出的全部候选（都不是结论）：

| 候选 | 位置 | 说明 |
|---|---|---|
| `IsFinished` | `HttpGameSession` @`0x0021A5B3` | 会话级完成标志（48 号主假设） |
| `RequestState` | `HttpGameSession`/`HttpGameMessage` @`0x0021A544` | 请求状态字段 |
| `IsSuccess` | `Http2DownloadMessage` @`0x0021A421` | BestHTTP 下载消息的成功标志 |
| `get_StatusCode` | `Http1Message` @`0x0021A2EF` | HTTP 状态码 |
| `get_DownloadText` / `get_DownloadData` | `Http1Message` @`0x0021A2FE`/`0x0021A30F` | 响应体 |
| `SessionStateChangedMessage` | `0x0021A55C` | **会话状态变更以"消息"形式广播**；由 `GameSessionManager.HandleSessionStateChangedMessage`@`21A029` 处理 |
| `OnRequestFinished` | `Http2DownloadMessage` @`0x0021A3F2` | BestHTTP 回调入口 |

**观察到的一点（推断，中）**：`SessionStateChangedMessage` 的存在说明完成是**事件驱动**的 →
`IsFinished` 很可能由「收到某条 `SessionStateChangedMessage`」置位，而不是轮询。
若该消息在"响应未被认领"的情况下不发，`IsFinished` 就永不置位 —— 与 48 号假设一致。

## A.4 Q4 —— 客户端发请求时 `protocol` 写的是什么（唯一确凿的一条）

**实测（不是推断）**：`report\36` §7 抓到客户端发来的
`protocol = AHTQLQI65FWJGGGK4KL5AEF57A`（26 字符、base32、`BASE32(MD5(UTF-16LE("Account_Auth")))`），
`encode = True`，`packet = base64([u32 LE 明文长度][gzip(净载荷)])`。

⇒ **客户端写的是 token，不是名字，也不是整数。**（`ToBase32String`@`0x001552E9` 的存在与之相容）

**响应侧读什么**：静态不可知（`ParseProtocol` 无函数体）。
`ParseProtocol` 失败时返回 null / 空串 / 抛异常 / `default` 枚举，**四种都可能，无法区分**。
一个可供参考的观察：`Protocol` 枚举连续块的第一条是 `Common_Cheat`@`0x0022D902`
（它前面是上一个类型的尾巴，不是枚举成员），**若** `Common_Cheat` 恰好是 0，
则"解析失败 → `default(Protocol)` → `Common_Cheat`"就是一条**静默错配**路径。
但**堆顺序 ≠ 枚举值顺序**，这条**无法验证**，仅作假设记录。

## A.5 给 lead 的建议：**先等 srv-ops 的真服抓包**

理由三条：

1. **Q1 我给的证据正反各一条**，强度不足以支撑一次用户点击；盲目改 `protocol` 可能白改一轮
   （lead 的担心是对的）。
2. 抓包**一次性解决** Q4（名字 / token / 整数）、响应是否加密、是否有我们没想到的信封形态。
   这三个问题静态全部不可知。
3. 抓包期间可以并行做**零风险**观测（不消耗点击）：
   logcat 抓 `WAITING_SERVER_RESPONSE`/`RECEIVED_SERVER_RESPONSE`（§9），
   以及 `LoginTask-` / `HttpGameMessage-` 标签（39 号 §3.3）。

**若抓包失败或要等很久**，再退回实验 A，但建议**同时做 A/B 两组**（token 回显 vs 随机串），
一次点击拿两个数据点，而不是一次一个。

---

# 附录 B（第 5 轮追加）：`NetworkService` 成员表、以及 P1/P2/P3 的可答边界

> lead 新证据：真·国服 `Account_Auth` 响应 = **280 字符 base64 → 208 B = 16 + 160 + 32**，不是 JSON。
> 本节先给 lead 点名要的 `NetworkService` 完整成员表，再逐条回答 P1/P2/P3 ——
> **其中 P1 的"键名大小写"和 P2 的"解密失败行为"的决定性部分都不可静态取得，我会明说。**

## B.1 `NetworkService` 完整成员表（lead 点名要的）

类 `NetworkService` @`0x00219CFC`，到下一个类型为止，**全部成员只有 8 条**：

| 偏移 | 成员 | 性质 |
|---|---|---|
| `0x00219D0B` | `receivedString` | 字段（或 `ParseReceivedString` 的参数名）—— 见 B.2 |
| `0x00219D1A` | **`ParseProtocol`** | 方法 |
| `0x00219D28` | **`ParsePacketString`** | 方法 |
| `0x00219D3A` | `ShowDefaultNetworkError` | 方法 |
| `0x00219D52` | `addressFamily` | 字段/局部 |
| `0x00219D60` | **`ParseReceivedString`** | 方法 |
| `0x00219D74` | `<ShowDefaultNetworkError>b__0` | lambda |
| `0x00219D92` | `buttonText` | lambda 捕获的局部变量 |

紧随其后的 **8 个枚举成员**（`WAITING_SERVER_RESPONSE`@`0x219DB0` … `SERVER_NOT_RESPONSE`@`0x219E32`）
属于**另一个独立枚举类型**，不是 `NetworkService` 的成员（上一轮我说"一簇"，此处精确化）。

> **这张表本身就是一条结论**：`NetworkService` 里做"串 → protocol/packet"的只有 3 个方法，
> **没有 `Decode*`、没有 `Decrypt*`、没有 `Json*`**。
> ⇒ 解密不在这个类里，在 `HttpGameMessage`（`DecodeResponse`@`0x21A4D2` / `DecryptOrReturnOriginal`@`0x21A4E1`）。

## B.2 P1 问的「声明类型（参数 / 返回类型）」—— **metadata 里取不到**

必须明确说清，避免又走一次弯路：

* il2cpp 的**方法名**在名字堆里（我们能读到，已给）；
* **参数类型/返回类型**在 `Il2CppMethodDefinition` 的 `returnType` / `parameterStart` 里，
  存的是**整数索引**，要回到 `typeDefinitions` / `typeSpecs` 表去解 ——
  **而这两张表的 offset 在文件头里，本包头被混淆（magic `0x12724394` ≠ `0xFAB11BAF`），解析不了。**
* ⇒ **"给出每个 `Parse*` 的参数类型和返回类型"这件事，静态做不到。** 这是硬限制，不是偷懒。

**能给的替代证据（推断，强）**：
`receivedString`（`0x00219D0B`）+ 方法名 `ParseReceivedString` 组合起来，
说明输入**是一个 string，不是 byte[]** —— 一个 `byte[]` 不会被命名成 `receivedString`。
⇒ **推断（强）：`ParseReceivedString(string)`，即"字节→串"的解码发生在它之前。**

## B.3 "字节 → 串"这条链路只有 5 个环节（全局枚举结果）

全文件（raw 层）`^(Parse|Decode|Decrypt|Encode|Encrypt)[A-Z]` 共 **285 条**，
但落在**网络/加密相关命名空间**里的只有下面这些（其余是 UI 颜色解析、Excel 解析、文本解析等噪声）：

```
网络层（Assets/_MX/Program/Scripts/Network）
  0x0021A4D2  HttpGameMessage.DecodeResponse        ← 入口
  0x0021A4E1  HttpGameMessage.DecryptOrReturnOriginal
  0x00219D60  NetworkService.ParseReceivedString     ← 拆串
  0x00219D1A  NetworkService.ParseProtocol           ← 拆出 protocol
  0x00219D28  NetworkService.ParsePacketString       ← 拆出 packet

加密层（MX.Core.*，可被上面调用）
  0x00259BE7  CryptAES.EncryptRJ256Api        0x00259C08  CryptAES.DecryptRJ256Api
  0x00259C76  CryptAESOrigin.EncryptStringToBytes_Aes   0x00259C8F  CryptAESOrigin.DecryptStringFromBytes_Aes
  0x0025E1CC  HybridCryptor.EncryptTextAES    0x0025E1EA  HybridCryptor.DecryptTextAES
  0x0025E2BB  MD5HashService (+ToHexString/ComputeHash)
  0x0025E36E  PacketCryptManager.EncryptRequest   ← 只有加密方向
  0x0025E3C5  StringCipher（Encrypt/DecryptString、*WithPassphrase）
```

⇒ **整条链一共就这么几个可叫的名字。** 谁调谁拿不到，但"候选集合是封闭的、很小的"这一点本身有价值：
解密只可能是 `DecryptRJ256Api` / `DecryptStringFromBytes_Aes` / `DecryptTextAES` / `StringCipher.DecryptString` 四者之一。

**与 srv-ops 新证据的交叉验证**（本轮**唯一能落地的技术结论**）：

| 观测（208 B = 16 + 160 + 32） | 客户端侧常量/方法 | 是否吻合 |
|---|---|---|
| 头部 16 字节 | **`PacketCryptManager.PROTOCOL_HEAD_RESERVE` @`0x0025E39D`** | ✅ 34 号拟合出的"16 字节头"现在有了**真实字段名**作背板 |
| 密文 160（10×16） | `CryptAESOrigin.DecryptStringFromBytes_Aes`（16 字节块） | ✅ |
| 密文 160（5×32） | `CryptAES.DecryptRJ256Api`（`FBENCRYPT_BLOCK_SIZE`=32 @`0x00259C18`） | ✅ **也吻合** |

⇒ **两条死区间无法用长度区分**（160 同时是 16 和 32 的倍数）。
判别只需一件事：**32 字节尾段是 key 还是 token** —— 若走 `Aes`，布局正好是 `16(IV) + 160(CT) + 32(Key)`，
**自洽**；若走 RJ256，常见布局是 `32 + CT + 32`，与本观测的 16 字节头不符。
**推断（中强）：更像标准 `AES-256-CBC`（key 在尾、IV 在头），而不是 Rijndael-256。**

## B.4 P1 的「键名大小写」——由解析器决定，而解析器**不可静态确定**

| 若解析器是 | 大小写 |
|---|---|
| Newtonsoft（`JsonConvert.DeserializeObject`） | **不敏感**（默认按属性名匹配，忽略大小写差异） |
| 手工 `IndexOf`/`Split`/正则 | **敏感** |

**能给的证据**：本工程**确实**在用 Json.NET，且是游戏自己的代码在用 ——
`ObjectExtensions.DeepCloneByJson` @`0x00259CC5`（游戏侧类，紧邻 `StringServices`/`ConvertService`）。
⇒ **推断（中）：项目整体走 Newtonsoft，网络层大概率也是。若如此，`protocol`/`Protocol` 大小写不敏感，改键名是低价值动作。**

**⚠️ 但这条与现场矛盾**：我们六轮发的就是小写 `{"protocol":...}` 的明文 JSON，
如果客户端真是 Newtonsoft + `DecryptOrReturnOriginal` 返回原文，**那一轮就该成功了**。
它没成功 ⇒ 要么 fallback 没生效、要么在 fallback 之前就断了、要么解析器不是 Newtonsoft。
**⇒ P1 的"改大小写"是低置信度、低价值方向，不建议优先。**

## B.5 P2 分水岭 —— **静态不可知，但现场已经给出答案**

### B.5.1 静态部分：确实不知道

`DecryptOrReturnOriginal`（`0x21A4E1`）与 `HandleDecryptionError`（`0x21A4F9`）**都只是名字**。
名字能说明"存在一个解密失败分支"，**不能说明该分支返回什么**。
`DecodeResponse`（`0x21A4D2`）的返回类型也取不到（同 B.2 原因）。
⇒ **"解密失败后返回原串 / 返回 null / 直接终止"——三种都可能，静态无法区分。不给结论。**

### B.5.2 但现场数据已经把这条路走过了 —— 本轮最重要的一句话

lead 自己列的六轮实验：
`Error envelope` / `真实明文 3740B` / `真实加密 4491B` / `http404 原封不动` → **客户端行为完全一致**。

**如果 `DecryptOrReturnOriginal` 真的会在解密失败时把原串交给下游，那"真实明文 JSON"那一轮就必须前进。**
它没有。

⇒ **推断（强，基于现场而非静态）：明文回退路径在本请求上要么没被走到、要么走到了但下游 `ParseReceivedString` 不认。**
⇒ **项目决策建议：不要把私服押在"明文可绕过加密"上。按 srv-ops 抓到的真实封装（16+CT+32）复刻加密响应，是所有路线里唯一有现场支持的那一条。**

> 这不是猜 —— 这是用 6 轮同形态失败，反证了"明文可行"这个假设。
> P2 的静态答案虽然不可得，但**决策所需的答案现场已经给了**。

## B.6 P3 「名字 vs token」—— 静态不可知，但有一条结构性提示

* 客户端**发**的是 26 字符 base32 token（实测，附录 A.4）。
* 客户端**读**什么，`ParseProtocol` 无函数体，不可知。
* 结构提示：`Protocol` 在客户端是**枚举类型**（`HttpMessage.Protocol` 属性的类型，`<Protocol>k__BackingField`@`0x21A89B`）。
  若 `ParseProtocol` 返回该枚举，则"解析失败"最省事的写法就是 `default(Protocol)`（= 0 号成员）。
  `Protocol` 枚举连续块首条是 `Common_Cheat` @`0x0022D902`，**若**它是 0 号，
  则"填错 protocol → 落到 `Common_Cheat`"就是一条**静默错配**。
  **但堆序 ≠ 值序，此条无法验证，仅登记为假设。**

## B.7 本轮可执行结论（3 条）

1. **P1/P2/P3 的方法体行为全部不可静态取得** —— 这是第三次撞同一堵墙（47 号 §5.1、48 号 §2、本节 B.2）。
   **不要再派静态任务问"某方法内部怎么做"**，除非先解决 metadata 头解密或拿到 `methodPointer`。
2. **静态能推进的是"布局"而非"逻辑"**：`PROTOCOL_HEAD_RESERVE`@`0x25E39D` 与 208 B 的 16 字节头吻合；
   `16(IV)+160(CT)+32(Key)` 更符合 `CryptAESOrigin`（Aes）而非 `CryptAES`（RJ256，通常 `32+CT+32`）。
   **建议 srv-ops 优先按 `AES-256-CBC / PKCS7 / key=尾 32B / iv=头 16B` 试解** —— 当天可验证。
3. **明文路线已有 6 轮反证**，不推荐继续投入。

---

# 附录 C（第 6 轮追加）：208 字节里能不能塞下 16 字节 IV —— **不能**

> lead 现场事实：真服响应 208 B 被解为 `CT(176) + Key(32)`，明文 164 B（148 回读 + 16 头）符合。
> 本节只答**布局**：`PROTOCOL_HEAD_RESERVE` 是 IV 位置，还是"协议头预留"。

## C.1 先给判据的答案

| lead 的判据 | 结论 | 依据 |
|---|---|---|
| A. 若存在 16 的 head reserve **且**有独立 IV 字段 ⇒ 布局可能 `IV(16)+CT(176)+Key(32)=224` | **不成立**（只对了一半） | 独立 IV 字段**有**（C.3）；但 `PROTOCOL_HEAD_RESERVE` **属于请求方向**（C.2），且 `HttpGameMessage` **没有任何 IV/头相关成员**（C.1 表） |
| B. 若 `PROTOCOL_HEAD_RESERVE` 是"协议头预留" ⇒ `CT+Key`，IV 隐含 | **成立（推断，强）** | C.2 的归属证据 |

**算术上也没有余地**：`16 + 176 + 32 = 224 ≠ 208`。
若包里真有 16 字节 IV，总长必然是 224，实测 208 **排除**了"包内 IV"这一种布局。

## C.2 `PROTOCOL_HEAD_RESERVE` 归属 **`PacketCryptManager`（请求方向）**

该类 `@0x0025E36E` 的**全部 6 个成员**：

```
0x0025E36E  PacketCryptManager      ← 类型
0x0025E381  requestBytes            ← 字段：请求字节
0x0025E38E  EncryptRequest          ← 方法：加密请求
0x0025E39D  PROTOCOL_HEAD_RESERVE   ← 常量/字段
0x0025E3B3  _cryptor
0x0025E3BC  _checker
```

**只有 `EncryptRequest`，没有 `DecryptResponse`、没有 `Decrypt`。**
⇒ `PROTOCOL_HEAD_RESERVE` 是**构造请求缓冲时预留的头部长度**，不是响应解密用的 IV 位置。
一个只做加密的类里的 "HEAD_RESERVE" 不可能是响应侧的 IV。

> 这一条同时解释了 34 号报告当年的 `[16][384][32]` 拟合为什么能对上**请求**：
> 那是请求方向的布局，不是响应方向的。

## C.3 IV 的来源全部在**本地/会话侧**，不在包里

| 符号 | 偏移 | 性质 |
|---|---|---|
| `CryptAES.IVString` | `0x00259C35` | **字段**（RJ256 那套存着 IV） |
| `CryptAES.generateKeyString` | `0x00259BAF` | 方法 |
| `CryptAES.cRandom` | `0x00259C2D` | 字段 |
| `MX.Core.Crypto.AesKeyIV` | `0x0025E159` | **Key+IV 的配对容器**（类型） |
| `MX.Core.Crypto.EncryptedKeyIV` | `0x0025E165` | 加密后的 Key+IV 容器 |
| `HybridCryptor.GenerateKeyAndIV` | `0x0025E1F9` | **成对生成 Key 和 IV** |
| `GameSessionManager.aesKey` | `0x00219F54` | 会话字段 |
| `GameSessionManager.aesIV` | `0x00219F5B` | 会话字段 |
| `GameSessionManager.SetAesParameters` | `0x00219F61` | 方法 |
| `GameSessionManager.VerifyAndSetAesParameters` | `0x00219FC2` | 方法 |
| `GameSessionManager.base64AesEncryptedKey` | `0x00219F72` | 字段 |
| `GameSessionManager.base64AesEncryptedIV` | `0x00219F88` | 字段 |
| `GameSessionManager.base64RsaSignedKey` | `0x00219F9D` | 字段 |
| `GameSessionManager.base64RsaSignedIV` | `0x00219FB0` | 字段 |

⇒ **IV 与 Key 在客户端一直被当作"一对"处理**（`AesKeyIV` / `GenerateKeyAndIV` / `encryptedKey`+`encryptedIV`）。
响应包里只带了 Key（尾部 32B），IV 只能来自本地常量或默认值 —— **与 lead 的判断一致**。

## C.4 `HttpGameMessage` 全部符号（15 条）—— **没有任何 Key/IV/Head/Reserve/Block/Offset 成员**

```
0x0021A465  HttpGameMessage            ← 类型
0x0021A475  get_URL
0x0021A47D  get_RequestState
0x0021A48E  get_RetryCount
0x0021A49D  get_message
0x0021A4A9  IncreaseRetryCount
0x0021A4BC  encryptedBase64String      ← 字段：待解的 base64 串
0x0021A4D2  DecodeResponse
0x0021A4E1  DecryptOrReturnOriginal
0x0021A4F9  HandleDecryptionError
0x0021A50F  IsSpecificErrorJson
0x0021A523  hostURL
0x0021A52B  <message>k__BackingField
0x0021A544  RequestState
0x0021A551  RetryCount
```

**这是本节最硬的证据**：如果响应解密需要从包里切一段 IV，这个类里必然出现
`iv` / `head` / `offset` / `reserve` / `block` 之类的字段或局部变量名 —— **一个都没有**。
它只有一个 `encryptedBase64String`（整串）和一步 `DecodeResponse`。
⇒ 解密所需的一切（含 IV）都**不来自这个类的成员**，即不来自包的解析结果。

## C.5 lead 点名要的常量名清单

| 常量 | 偏移 | 备注 |
|---|---|---|
| `PROTOCOL_HEAD_RESERVE` | `0x0025E39D` | **请求方向**（C.2） |
| `FBENCRYPT_BLOCK_SIZE` | `0x00259C18` | `CryptAES`（RJ256）的块长 |
| `IVString` | `0x00259C35` | `CryptAES` 的 IV 字段 |
| `PaddingMode` | **NOT FOUND**（精确名） | — |
| `Pkcs7` | **NOT FOUND**（精确名） | — |
| `RijndaelManaged` | **NOT FOUND**（精确名） | ⇒ `CryptAES` **不是**用 .NET 的 `RijndaelManaged`，是 FBEncryptor 风格自实现（`FBENCRYPT_` 前缀即证据） |
| `CipherMode` | `0x005FCB3E` | ⚠️ **在 BestHTTP/TLS 区（0x5Fxxxx）**，是第三方库符号，**不能用来解释游戏布局** |
| `AesCryptoServiceProvider` | `0x0071C6E3` | ⚠️ 同上，System.Security 区 |
| `KeySize` / `BlockSize` | `0x0060D02F` / `0x0060C954` | ⚠️ 同上，TLS 区 |

> 提醒：`CipherMode`/`BlockSize` 这几个"看起来对"的名字全都在第三方 TLS 库里，
> 拿它们推游戏加密布局会得出错误结论。游戏自己的加密只用 `CryptAES` / `CryptAESOrigin` / `StringCipher` / `HybridCryptor` 四个类。

## C.6 关于「`aesKey` 恒为 null、`SetAesParameters` 从未被调用」

* **字段确实存在**（`aesKey`@`0x219F54`、`aesIV`@`0x219F5B`，见 C.3）。
* 但"恒为 null / 从未调用"是**运行期结论**，**静态无法验证**（无 xref，见 47 号 §6）。
  C.3 只能证明"存在这条设置路径"，不能证明它是否被走过。
* **不过布局推论不依赖它**：无论 `aesIV` 是否被赋值，`208 = 176 + 32` 都已排除包内 IV；
  而 32B key 只能来自包尾（CT 长度 176 是 16 的整数倍，说明密钥不是从 CT 里切出来的）。
  ⇒ 「客户端响应密钥完全取自包内尾部 32B」与布局自洽（**推断，强**）。

## C.7 一条方法论提醒（工具盲区，值得记进 DEADENDS 之外的"方法"栏）

`aesIV` 只有 **5 个字符**，**不在** `all_ascii.tsv` 里 —— 因为 39 号的扫描器设了 `len >= 6`。
同类短名（`iv`、`key`、`aesIV`、`iv2`、`ct`）**全部被漏掉**。
⇒ 以后专门找 IV / key / 长度类短符号时，必须用 `len >= 3` 重扫（本轮 C.3 的 `aesIV` 就是这样才找到的）。
这条不影响 47/48 已给的结论（那些都是长名），但会影响"某字段存不存在"的判断，属于**假阴性风险**。

---

# 附录 D（第 7 轮追加）：IV 常量 `JOSYdf8ys97uhFYS` 已定位 —— **确实硬编码在客户端**

> lead 给的实测：两份不同真实响应（不同 IP、不同随机 key）反推出的 IV 完全一致 =
> `JOSYdf8ys97uhFYS`。本节回答"这个常量在不在客户端里"。

## D.1 结论：**在，而且在 `global-metadata.dat` 里有两处**

两处**都不是明文**，而是被单字节 XOR 藏起来的 —— 这就是直接 `grep` / `strings` 会 0 命中的原因。

| # | 文件偏移 | XOR key | 该处原始 16 字节 | ^ key 后 |
|---|---|---|---|---|
| 1 | **`0x0007AA13`** | **`0xE9`** | `a3 a6 ba b0 8d 8f d1 90 9a d0 de 9c 81 af b0 ba` | `JOSYdf8ys97uhFYS` |
| 2 | **`0x012D172C`** | **`0x66`** | `2c 29 35 3f 02 00 5e 1f 15 5f 51 13 0e 20 3f 35` | `JOSYdf8ys97uhFYS` |

复现（纯 Python，不依赖 grep/strings）：

```python
d = open('global-metadata.dat','rb').read()
print(bytes(b ^ 0xE9 for b in d[0x0007AA13:0x0007AA13+16]))   # b'JOSYdf8ys97uhFYS'
print(bytes(b ^ 0x66 for b in d[0x012D172C:0x012D172C+16]))   # b'JOSYdf8ys97uhFYS'
```

> ⚠️ **方法论要点**：这个常量用 `0x00/0x01/0x0E/0x20` 四把钥匙都搜不到。
> 我把 **0x00..0xFF 全部 256 个 key** 都试了一遍才捞出来，实际 key 是 `0xE9` 与 `0x66`。
> 其中 `0x66` 正是 `report\11` §2 早已标记的"XOR 0x66 区"。
> ⇒ **逐字面量的 XOR key 是随机/不统一的，不能靠猜，必须全 key 扫。**

## D.2 `libil2cpp.bin`：**没有**（四种变体 + 256 个 key 全扫过）

| 文件 | 明文 | XOR 0x20 | UTF-16LE | UTF-16LE^0x20 | 256-key 全扫 |
|---|---|---|---|---|---|
| `global-metadata.dat` | ❌ | ❌ | ❌ | ❌ | ✅ **命中 2 处**（D.1） |
| `libil2cpp.bin`（270,927,056 B） | ❌ | ❌ | ❌ | ❌ | ❌ **全 NOT FOUND** |
| `libunity.bin` | ❌ | — | — | — | — |

⇒ **常量在托管侧（metadata 的字符串字面量），不在任何原生 `.so`。**

**关于"是否落在只读数据段"**：**这条不适用** —— 它不在 ELF 里。
（为排除误判，我仍解析了 `libil2cpp.bin` 的 ELF 结构：`is64=True, le=True, shoff=0x1025FE90, shnum=25, phnum=14`，
只是 256 个 key 下都没有命中，所以没有段归属可报。）
`global-metadata.dat` 是**资源文件**（非 ELF、无 section 概念）；运行期它作为 il2cpp 的 metadata blob 被加载，字面量从里面取。

## D.3 ±64 字节邻域（lead 的第 3 问）：**没有第二组 IV**

**hit 1（`0x7AA13`，key=`0xE9`）**，±64B 解码后只有这些可打印串：

```
0007A9DB  len=28  (-()1(f'4!3+#(2f2?6#fa(,+YB7            ← 前一个用其他 key 混淆的字面量
0007AA08  len=44  BESVPWWRTS=JOSYdf8ys97uhFYSz`|fw}si}utnaiplm
```

* `BESVPWWRTS=` 是**前一个字面量的尾部**（以 base64 的 `=` 结尾）；
* `JOSYdf8ys97uhFYS` 是**独立的一个 16 字符字面量**；
* 其后 `` z`|fw}si}utnaiplm `` 含反引号/竖线/波浪号 ⇒ 那是**另一个 key 混淆的字面量**，不是 IV 的延续。

⇒ **这一处只有 IV 本身，没有备用 / 多语言 IV。**

**hit 2（`0x12D172C`，key=`0x66`）**，±64B 解码后是**一整条连续可打印串**：

```
012D172A  len=66  @ JOSYdf8ys97uhFYSXuseoGqqmIpqu45KlNU6PXwMQmlyJI1+x50T+dDdZGAg=0O+
```

* 前 16 字符 = IV；
* 紧随其后 **48 字符 `XuseoGqqmIpqu45KlNU6PXwMQmlyJI1+x50T+dDdZGAg=` 是 base64 形态**（以 `=` 结尾）。
  **推断（弱）**：可能是与 IV 配对的"默认 key / 预置加密块"，即 `<IV><base64(payload)>` 形式的字面量。
  **无证据**说明它与网关响应有关，登记待查，不作结论。

## D.4 对 lead 的闭环意义

| 问题 | 答案 |
|---|---|
| IV 是否硬编码在客户端 | **是**（metadata 两处：`0x7AA13` / `0x12D172C`） |
| 是否与包内容有关 | **无关** —— 它是**字面量常量**，不是从包里切出来的（与附录 C 的算术排除互相独立、互相印证） |
| 我们造的包客户端能否解开 | **能**：`AES-256-CBC(key = 包尾 32 B, IV = "JOSYdf8ys97uhFYS", PKCS7)` |
| 响应是否需要签名/HMAC | **不需要** —— `_checker` 只在请求方向的 `PacketCryptManager` 里；`HttpGameMessage` 无校验器（附录 C.1/C.2） |

⇒ **最后一处"可能失败"的变量已消除**：IV 固定、key 在包内、响应无签名校验。
三条合起来说明这套封装是**约定**而非**安全边界**。

## D.5 置信度与残留风险

| 项 | 置信度 | 说明 |
|---|---|---|
| 常量存在于 metadata 的这两个偏移 | **确证** | 字节级可复现（D.1 三行代码） |
| 它就是网关响应解密用的 IV | **高（推断）** | 名字能对上的只有 `CryptAES.IVString`@`0x259C35`；且 lead 实测两端一致 |
| 不在 libil2cpp | **确证（限定）** | 256 个**单字节** key 全扫；**不能排除多字节/流式混淆**（本包目前只观察到单字节 key） |
| hit2 后面那 48 字符 base64 的用途 | **未定** | 仅登记 |
