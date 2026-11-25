# 41 — `Account_Auth` 字段级排查（纯离线）

> 时间：2026-11-14 03:36–04:05
> 角色：协议字段分析员。**未连手机、未连服务器、未发任何请求。**
> 一手证据：`report\36`（24 字段与值）、`report\_tmp\mx_crypto\account_auth_full.json`（请求明文）、
> `work\ba\...\Metadata\global-metadata.dat`（38,426,024 B，本次新做的定向字段扫描）、`report\21`（四轮客户端实测）
> 结论等级标注：**[实测]** = 本次亲自读出/算出；**[推断]** = 有依据但未证实；**[猜测]** = 仅列候选

> **03:45 版**：lead 通报了新证据（`/log` 零命中、客户端从未发 `Queuing_*`、`/api/account/auth` 用 BestHTTP + 404/200 差异），
> 结论已按新证据重排：**传输/格式层优先，字段层降为第二层**（见 §0.6、§9）。§1–§7 的字段工作仍然有效。

---

## 0. 查档记录（先说看了什么）

| 文件 | 用途 | 关键结论 |
|---|---|---|
| `report\25` | 上一次 schema 卡点的**定案方法** | 根因靠「改一个字段 → 弹窗像素差 0 px」证死；判据是**逐像素 + 单变量** |
| `report\24` | 同一方法在 `/api/state` 上的执行 | 用 metadata 字符串表 + `k__BackingField` 探针反推 DTO，**这套方法我这次照搬到 `AccountAuthResponse`** |
| `report\31` | 真实国服 `/api/state` 676 B | `AddressablesCatalogUrlRoots` 三条线路；四版本号；`State:1` 正常；`Servers` 两条 `/api/` |
| `report\32` `33` `34` `35` | 国服信封四联 | 信封 `[iv16][ct][key32]` + `[u32 len][gzip]`；`protocol`=BASE32(MD5(UTF-16LE))；**响应方向从未抓到过真样本** |
| `report\36` | 24 字段与实测值 | **本报告 §1 的「我们给的值」全部取自这里，无一处自造** |
| `report\21` | 手机侧 37 轮 | 四变体行为记录、`4491 B 加密体`、无 Unity 日志、无第二条协议 |
| `report\27` `28` | SDK 登录链 / Shittim 源码 | `Account_CheckYostar`（Yostar 系走这条）；响应外层是 camelCase `{protocol,packet}` |
| `report\38` | Frida 清单 | il2cpp 常规 hook 已被判「不能按常规套路」，第一枪改网络层钩子 |

**查档：无记录** 的部分 → `report\` 下 39 份里**没有任何一份抓到过国服网关的响应样本**（`report\32 §8.3`、`report\35 §6.2` 都明确写了「响应方向完全没分析」）。这是本报告全部结论的天花板。

---

## 0.5 三条判据纪律（比字段更重要，先看）

1. **「四种响应体行为完全一致」这句话本身是坏的判据。**
   `report\21` 明确记着：**404 → 弹「服务器处理请求失败」**（`now1.png`/`aa_3.png`，btn_px=58439），
   **200 → 无弹窗、无第二条协议**。这两件事在「弹窗」这一维上是**相反**的。
   把 404 也算进「行为一致」，等于把「HTTP 层报错」和「应用层静默」混成一个观测，后面所有归因都会失真。
   **建议从现在起只记两个数：`btn_px`（弹窗）+ fresh sport 数（后续协议）。**
2. **「无第二条协议」只证明客户端没发新连接，不证明它没解析我们的 body。**
   `report\21 §37.4` 的 fresh sport 判据是可靠的；但它只覆盖「发请求」这一种后续动作。客户端完全可能解析成功、然后卡在一个不出网的状态机上。
3. **`report\21 §37.5` 的「加密响应 4491 B」这条实验，算术上不成立**（见 §6）。
   在没搞清楚那 4491 字节到底是什么之前，**「响应是否加密不影响行为」这个结论不能成立**——它可能只是第二次喂了个非法包。

---

## 0.6 结论重排（03:45 新证据进来之后）

> 来源：lead 转发的服务端日志三行 + 两条排除（`/log` 端点零命中；客户端从未发过 `Queuing_*`）。
> **本节优先级高于 §1–§3。下面 §1–§3 的字段工作仍然有效，但它现在是「第二层」，不是「第一层」。**

### 三行日志改变的问题性质

```
03:23:16  GET  /api/state        → state-api   200  116B  ua=UnityPlayer(UnityWebRequest)
03:23:17  GET  /api/state        → gsqc-api    200  676B  ua=UnityPlayer(UnityWebRequest)
03:27:37  POST /api/account/auth → gsqc-api    404 1269B  ua=BestHTTP/2 v2.4.0   ← 唯一一次网关交互
```

三个「变了」：
1. 路径是 `/api/account/auth`，**不是** `/api/gateway`；
2. HTTP 栈是 **BestHTTP/2**，**不是** UnityWebRequest/libcurl；
3. 编码是 `multipart/form-data`（boundary `BestHTTP_HTTPMultiPartForm_*`）。

### 由此得到的两条硬结论（证据见 §9）

| # | 结论 | 等级 |
|---|---|---|
| 1 | **客户端没有「编码响应」的代码路径**——全文件 `EncryptResponse`/`EncodeResponse`/`DecryptResponse` 0 命中，只有 `DecodeResponse`/`DecryptOrReturnOriginal`。且响应解密要用的 `aesKey/aesIV` 只能由从未发生的 `Queuing_*` 换钥获得 ⇒ **任何加密响应都解不开**。⇒ 回明文 JSON 的方向是对的，「响应必须加密」这条**可以撤掉** | 实测 |
| 2 | `/api/account/auth` **不是「登录专用服务」，是 `ApiUrl + SendRequestApi` 这条 REST 传输上 `Account_Auth` 的路由**（客户端同时存在 `GatewayUrl + SendRequestGateway` 与开关 `IsGatewayBypassed`）。⇒ 我们 bridge 的**协议层假设没错，传输层假设错了** | 实测 |

### 因此排查顺序改成

```
第一层：200 之后 body 到底有没有被消费 / 被谁消费（§9.C 的 L5 毒化探针）
   ↓ 若 body 被消费
第二层：外层形状（protocol 值形态、大小写、Encode、是否两段式文本）（§9.C 的 L1/L2/L6）
   ↓ 若外层也对
第三层：字段值与缺失字段（§1–§3）
```

**注意**：`report\36 §6` 记着「3740 B 明文 gzip 后 = **1269 字节**」，而 404 那枪的 body 正好是 **1269 B**
⇒ 那枪极可能是「同一份 3740 JSON + 404 状态码」，**弹窗来自状态码而非 body**。
这反过来说明：**body 原样下发这条路是通的**，卡点只在 200 之后。

---

## 1. 逐字段合法性表

### 1.1 先给一张「国服到底认不认这些键」的总表

**本次从 `global-metadata.dat` 直读到的国服 `AccountAuthResponse` 属性簇 [实测]**
（偏移 `0x22ae75`–`0x22b5xx`，属性序列物理相邻，前后邻居分别是 `AccountAuthRequest` 与 `AccountAuth2Request`）：

```
CurrentVersion, MinimumVersion, IsDevelopment, BattleValidation, UpdateRequired,
TTSCdnUri, AccountDB, RepurchasableMonthlyProductCountDBs, MonthlyProductParcel,
MonthlyProductMail, BiweeklyProductParcel, BiweeklyProductMail,
WeeklyProductParcel, WeeklyProductMail, IssueAlertInfos, DailyRecordDBs,
OptionDB, AccountLimitedFlashSaleDBs, Desc, FunctionClose
```

**国服 `ResponsePacket` 基类属性簇 [实测]**（`0x2302b9` 起，紧跟在 `ResponsePacket` 之后）：

```
ServerTimeTicks, ServerNotification,
MissionProgressDBs, EventMissionProgressDBDict, BattlePassMissionProgressDBDict,
StaticOpenConditions
```

**据此把 24 个键分类：**

| 分类 | 键 | 数量 |
|---|---|---|
| A. 国服 DTO 直接有 | `CurrentVersion` `TTSCdnUri` `AccountDB` `OptionDB` `RepurchasableMonthlyProductCountDBs` `MonthlyProductParcel` `MonthlyProductMail` `BiweeklyProductParcel` `BiweeklyProductMail` `WeeklyProductParcel` `WeeklyProductMail` `IssueAlertInfos` `AccountLimitedFlashSaleDBs` | **13** |
| B. 国服基类有 | `ServerTimeTicks` `ServerNotification` `StaticOpenConditions` | **3** |
| C. 国服**没有**（整份 metadata 里 0 命中或不在此簇） | `SessionKey` `EncryptedUID` `AccountRestrictionsDB` `AttendanceBookRewards` `AttendanceHistoryDBs` `NewlyAddedShopCashIds` `AccountId` | **7** |
| D. 协议包头层 | `Protocol` | 1 |

**C 类 7 个键的实证：**

| 键 | 全 metadata 命中数 | 备注 |
|---|---|---|
| `SessionKey` | **0** [实测] | 国服只有 `SessionDB`（含 `LastConnect`/`ConnectionTime`，是游戏内 DB 实体），不是会话凭据 |
| `AccountRestrictionsDB` | **0** [实测] | —— |
| `AttendanceBookRewards` | **0** 精确命中 [实测] | `AttendanceBook` 有 7 处，但都是 `AttendanceBookUniqueId`/`DayByBookUniqueId` 这种独立签到协议字段 |
| `NewlyAddedShopCashIds` | **0** [实测] | —— |
| `EncryptedUID` | 2 [实测] | 两处都不是 DTO：`UIPopup_System.encryptedUID` 字段 + `SetEncryptedUID` 方法（用于错误弹窗的登出） |
| `AccountId` | 73 [实测] | 但 `get_AccountId` 只有 1 处且在非网络区；**不在 `AccountAuthResponse` 簇内** |
| `AttendanceHistoryDBs` | 未逐字命中 [推断] | 与 `AttendanceBookRewards` 同类 |

> **这不是「值非法」，是「键根本不存在」。** 对 Newtonsoft 默认设置，未知键被忽略——所以 C 类 7 个键大概率**无害但也无用**；
> 反过来说，我们这份 3740 B 里**约 1/3 的字节是国服客户端读都不读的**。这直接影响「换更小的响应体做差分」的实验设计。

---

### 1.2 顶层 24 字段逐条

> 「值」列全部来自 `report\36`；「来源」= 该值在 `report\36` 里的形成方式。

| # | 字段 | 我们给的值（样本） | 值来源 | 国服语境下是否可能非法 | 如果非法会怎样 |
|---|---|---|---|---|---|
| 1 | `Protocol` | `1002` | Shittim 枚举 `Protocol.Account_Auth` | **中**：请求侧 `protocol` 表单字段是 **base32 token**（`report\35`），不是名字也不是数字；响应里却给 int | 若客户端按名字/token 比对 → 判为未知协议 → **静默丢弃**（最符合现象） |
| 2 | `CurrentVersion` | `446690` | `ServerConfiguration.AuthCurrentVersion`，**国际服口径** | **中**：国服 3.0.2 versionCode=73，446690 是国际服版本号 | 若参与版本比较 → 走 `ClientUpdateRequire` 分支（国服错误码枚举里确有此项 [实测]）→ 可能静默等更新 |
| 3 | `TTSCdnUri` | `https://ba.dn.nexoncdn.co.kr/tts/version2/` | Shittim **硬编码** | **高（值）／低（因果）**：Nexon 国际 CDN，国服不可达 | 若被读 → 起 TTS 下载 → DNS/连接卡住。但 `report\21 §37.4` 当轮 DNS 只有 `openlog` ×2，**没有任何 nexoncdn 解析** ⇒ 客户端没走到这一步 |
| 4 | `AccountDB` | dict(9) | Shittim 账号实体 | **中**：见 §1.3，国服 `AccountDB` 字段更多 | 缺键 → 反序列化为 null/default → 可能在处理链里被解引用 |
| 5 | `AccountId` | `2` | Shittim `AccountDB.ServerId` 的复制 | **中高**：不在国服 DTO 簇内 | 被忽略；**若国服会话靠它**，则拿不到身份 |
| 6 | `SessionKey` | `{AccountServerId:2, MxToken:"0404e715-..."}` | Shittim 会话 | **高**：`SessionKey` 在国服 metadata **0 命中** | 被忽略 → 客户端无会话 → **下一条请求构造不出来**（不明说、不弹窗） |
| 7 | `EncryptedUID` | `FUQPRE2OHCSXGOQRNGJQOAOCD4`（26 字符 base32） | Shittim 生成 | **高**：国服无此 DTO 属性 | 被忽略；不影响登录 |
| 8 | `ServerNotification` | `8` | Shittim 基线位（8=HasUnreadMail） | **低**：国服基类确有该属性，8 合法 | 红点错误，不影响 |
| 9 | `ServerTimeTicks` | `639302220170000000` | Shittim `DateTime.Now.Ticks` | **低**：我换算 = **2026-11-14 03:00:17**，与机器时钟一致 [实测] | 若为 0 → 客户端时间偏移算错；本次不是 0 |
| 10 | `OptionDB` | `{}` | Shittim | **低**：国服簇内只有 `set_OptionDB`（无 getter） | 空对象最安全 |
| 11 | `AccountRestrictionsDB` | `{}` | Shittim | **高（无此键）** | 被忽略 |
| 12 | `StaticOpenConditions` | dict(55)，全 `0` | Shittim 静态解锁表 | **中**：键名是国际服内容枚举；**类型（dict vs list）未证** | 若国服是 `List<...>` → **整个响应反序列化失败**（最危险的单点） |
| 13 | `AttendanceBookRewards` | list(1)，含 10 天 `ParcelInfo` | Shittim 当日签到簿 | **高（无此键）** | 被忽略；且国服签到走独立协议 `Attendance_Reward`（`get_AttendanceBookUniqueId` [实测]） |
| 14 | `AttendanceHistoryDBs` | `[]` | Shittim | **高（无此键）** | 被忽略 |
| 15–21 | `RepurchasableMonthlyProductCountDBs` / `MonthlyProductParcel` / `MonthlyProductMail` / `BiweeklyProductParcel` / `BiweeklyProductMail` / `WeeklyProductParcel` / `WeeklyProductMail` | 全 `[]` | Shittim | **低**：7 个键在国服簇内全部存在 | 空数组 vs 缺键：C# 为 null 时 `foreach` 会 NRE（但 200 轮无 Unity 异常，见 §2） |
| 22 | `IssueAlertInfos` | `[]` | Shittim | **低**：簇内存在 | 同上 |
| 23 | `AccountLimitedFlashSaleDBs` | `[]` | Shittim | **低**：簇内存在 | 同上 |
| 24 | `NewlyAddedShopCashIds` | `[]` | Shittim | **高（无此键）** | 被忽略 |

---

### 1.3 `AccountDB` 9 个子字段

| 子字段 | 我们给的值 | 国服是否有 | 风险 |
|---|---|---|---|
| `ServerId` | `2` | 有（`AccountServerId` 体系） | 低 |
| `Nickname` | `""` | 有 | **中**：空昵称会触发 `ShowNicknamePopup`；但**弹窗没出现**，说明流程没走到 |
| `State` | `1` | 有（国服有 `IsStateMatch` [实测]） | 低（1=正常） |
| `Level` | `1` | 有 | 低 |
| `RepresentCharacterServerId` | `9` | 有 | 低（角色不存在时可能查表失败，但通常在进大厅时才用） |
| `LastConnectTime` | `2026-11-14T02:51:54` | 有 | 低（ISO 无时区，.NET 可解析） |
| `PublisherAccountId` | `314816420` | 有 | 低（= 我们 SDK 的 uid，对得上） |
| `RetentionDays` | `0` | 有 | 低 |
| `CreateDate` | `2026-11-14T02:51:54` | 有 | 低 |

**国服 `AccountDB` 同区段还出现、而我们完全没发的字段 [实测，归属待二次确认]**：
`LobbyMode`、`MemoryLobbyUniqueId`、`CallNameUpdateTime`、`UnReadMailCount`、`LastReturningDate`、
以及三条审核限制 `NicknameRestriction` / `CommentRestriction` / `CallnameRestriction`。

其中 **`CallNameUpdateTime` 最值得注意**：国服有独立的 `Account_CallName` 协议和 `ShowCallnamePopup`
（`report\21` 的 `LoginTask` 字符串里 `SetAccountCallname` / `SkipAccountCallname` / `ShowCallnamePopup` 全在 [实测]）。
如果登录链在 `HandleAccountAuthResponseMessage` 之后就查 `AccountDB.CallNameUpdateTime`，**null 会直接把协程打断**。

### 1.4 `SessionKey` 内部 2 个键

| 子字段 | 我们给的值 | 国服 | 风险 |
|---|---|---|---|
| `AccountServerId` | `2` | 概念存在 | —— |
| `MxToken` | `0404e715-ec34-4808-b1b1-580aefafc3af`（GUID 字符串） | 国服**有 `MxToken` 属性**（`get_MxToken/set_MxToken/<MxToken>k__BackingField`，偏移 `0x257d97`），但它挂在游戏内 DB 实体上，**不在 `AccountAuthResponse` 簇内** | **中高**：字段名对得上、位置对不上 |

---

## 2. 最可疑字段 Top 3

> **03:45 后降级**：本节现在是「第二层」。若 §9.C 的 L5 毒化探针证明 body 根本没被反序列化，这三条全部作废。先做 L5。

> 排序依据：**与「200 无弹窗 + 无第二条协议 + logcat 无 Unity 异常」这一组现象的一致性**，不是「看起来奇怪」。

### Top 1 — `StaticOpenConditions` 的**类型**（不是值）

**为什么可疑**
- 它在国服 `ResponsePacket` **基类**上（`0x2302b9` [实测]），意味着**每个响应**都会被反序列化这一项。
- 我们发的是一张 **55 键的 `Dictionary<string,int>`**，键名全部来自 Shittim（国际服内容枚举）。
- 国服的内容锁枚举集合已经变了（`report\24` 证明国服把 `/api/state` 拆成了两个 DTO），所以国服这边**完全可能是 `List<StaticOpenConditionDB>` 而不是 dict**。
- 如果是 list 而收到 `{...}`：Newtonsoft 抛 `JsonSerializationException`，**整个 `AccountAuthResponseMessage` 反序列化失败**。这个异常发生在 `NetworkService.ParseReceivedString` 里，属于**被 catch 的**异常——`report\21 §34.1` 已实测「02:54–02:59 窗口 Unity 日志 0 行」，即**catch 住的异常不会进 logcat**。
- 这一条能同时解释：为什么四种响应体都没反应（都带同一个非法 `StaticOpenConditions`）、为什么不弹窗（不是 HTTP 错误）、为什么没有下一条协议（任务对象根本没构造出来）。

**怎么验证（离线即可，先做）**
1. 在 metadata 里找 `StaticOpenConditions` 的**元素类型**：搜 `Academy`/`Arena`/`Cafe` 这些枚举名是否构成一个 enum 类型（`report\24` 的方法：看它们是否成簇出现且前面有类型名）。若找不到 enum 而找到 `...DB` 类型 → 倾向 list。
2. 若仍是 dict：把 55 键削减为 `{}`（空字典）做一次对照——如果 `{}` 也不报错，说明类型不是 dict 就是可空引用，风险降低。

**期望看到什么**
- 若国服是 list：**整体置 `[]` 后客户端行为应当突变**（出现弹窗或第二条协议）。
- 若 dict 而键名非法：置 `{}` 后行为不变，但把 `Academy` 等键改成国服枚举里真实存在的名字后可能突变。

---

### Top 2 — `SessionKey`：国服根本没有这个键（`SessionKey` 全文 0 命中）

**为什么可疑**
- `report\36` 把 `SessionKey` 写成「后续所有请求的凭据」，这是**国际服**的语义。
- 国服 metadata 里 `SessionKey` **一次都没出现**；出现的是 `SessionDB`（游戏 DB）、`SessionId`/`SessionState`/`SessionHash`（战斗会话）、`YostarUID`/`EnterTicket`/`Cookie`（Yostar 认证链）。
- 国服的登录字符串表里有一整条 `RequestQueuingGetTicket → RequestAccountCheckYostar → RequestAccountAuth → RequestAccountCreate` 的状态机（`LoginTask`，偏移 `0x13fad5` 区 [实测]），**并且 `AccountCheckYostarResponse` 在国服只有 `ResultState` / `ResultMessag` 两个字段**（`0x22cb8e` [实测]）——连 `EnterTicket`/`Cookie` 都不在这个响应里。
- ⇒ 国服的「会话」到底放在哪个字段，我们现在**不知道**。给一个国服不认识的 `SessionKey`，等于没给。

**怎么验证**
- 离线：在 metadata 里枚举所有 `*Token` / `*Key` / `*Session*` 属性，逐个对到 20 个 DTO 属性上（我这次只做了 `Session*` 与 `Encrypted*` 两类，见 §7）。
- 在线（省事）：**先把 `SessionKey` 换成/补上几个候选名**（`SessionDB`、`SessionKey` 保留、`MxToken` 提到顶层）做 A/B，看第二条协议是否出现。这条**与 Top 1 可以合并成一次实验**。

**期望看到什么**
- 若会话字段名是唯一障碍：补对名字后，客户端会**立刻**发出下一条协议（大概率是 `Queuing_GetTicket` 或 `Account_LoginSync`），fresh sport 数从 1 变 2。

---

### Top 3 — 我们**整份响应都缺**国服基类的三个集合字段

**为什么可疑**
- 国服 `ResponsePacket` 基类有 6 个属性，我们只发了 3 个（`ServerTimeTicks` / `ServerNotification` / `StaticOpenConditions`）。
- **完全没发的三个：`MissionProgressDBs`、`EventMissionProgressDBDict`、`BattlePassMissionProgressDBDict`** [实测]。
- Shittim 的 `ServerResponsePacket` 里根本没有这三个属性（它对齐的是更早的国际服版本），所以**不管怎么改 24 个字段，这三个永远是 null**。
- 如果国服的通用响应处理链（`AbstractNetworkTask` → `SessionTask` → `HandleMessage`）在**每个响应**上都会扫一遍 `MissionProgressDBs`（发任务进度 toast——`SessionTask` 里确实有 `showMissionToast` [实测]），null 会 NRE；NRE 若被 catch，就是「静默」。
- 关键旁证：`report\21` 的 `LoginTask` 里有一整串 `co_SyncTutorialCompletionIds`、`co_SyncShopListTutorialGacha`、`CheckBeforehandGachaProceeding` ——**登录刚结束就有一批「同步型」子流程**，它们正是最可能消费这些 `*ProgressDBs` 的地方。

**怎么验证**
- 一次性把三个都补成空集合（`[]` / `{}` / `{}`），其余一字不动，看行为是否变化。
- 与 Top 1/Top 2 的实验可以**放在同一轮**（它们都是「补字段」，不冲突），但**判定要分开**：若一起变，用下一轮做单变量回退。

**期望看到什么**
- 行为突变（弹窗出现 / 第二条协议出现 / `E/Unity` 出现异常）⇒ 命中。
- 完全不变 ⇒ 这三条不是瓶颈，回到 Top 1（类型）与 §4（信封层）。

---

## 3. 缺失字段候选清单

### 3.1 一手：国服 metadata 里**有**、但我们没发（可直接抄）

| # | 字段 | 所在层 | 证据 | 备注 |
|---|---|---|---|---|
| 1 | `MissionProgressDBs` | `ResponsePacket` 基类 | `0x2302b9` 簇 [实测] | 集合，建议 `[]` |
| 2 | `EventMissionProgressDBDict` | 同上 | 同上 | 字典，建议 `{}` |
| 3 | `BattlePassMissionProgressDBDict` | 同上 | 同上 | 字典，建议 `{}` |
| 4 | `MinimumVersion` | `AccountAuthResponse` | `0x22ae75` 簇 [实测] | 0 时可省略（Shittim 也省） |
| 5 | `IsDevelopment` | 同上 | 同上 | false 时可省 |
| 6 | `BattleValidation` | 同上 | 同上 | false 时可省 |
| 7 | `UpdateRequired` | 同上 | 同上 | false 时可省 |
| 8 | `DailyRecordDBs` | 同上 | 同上 | **Shittim 也省**（源码注释），但国服 DTO 有 → 建议 `[]` |
| 9 | `Desc` | 同上 | `get_Desc/set_Desc` [实测] | 类型未知（疑似 string），`""` 最安全 |
| 10 | `FunctionClose` | 同上 | `get_FunctionClose/set_FunctionClose` [实测] | 类型未知（bool？list？）→ **这是最该先搞清类型的** |
| 11 | `AccountDB.CallNameUpdateTime` | `AccountDB` | `0x24d35a` 簇 [实测，归属待确认] | 若被解引用，null = NRE |
| 12 | `AccountDB.UnReadMailCount` | 同上 | 同上 | 红点用 |
| 13 | `AccountDB.LobbyMode` / `MemoryLobbyUniqueId` / `LastReturningDate` | 同上 | 同上 | 进大厅才用 |

> 第 9/10 条（`Desc` / `FunctionClose`）**是纯国服/新版字段，Shittim 侧没有对应物**，我们怎么改配置文件都补不出来——必须在桥里手写。

### 3.2 二手：Shittim 主动省略的（`report\36 §1` 已列）

`accountBanByNexonDBs`、`DailyRecordDBs`、值为 false 的 `IsArenaAnonymous`、`MinimumVersion`(=0)、
`IsDevelopment`/`BattleValidation`/`UpdateRequired`(false)。—— **这批可以继续省**。

### 3.3 国服特有但**不像**是 `Account_Auth` 响应字段的（列出来是为了排除）

本次在 metadata 里顺带命中的国服/中国区专属符号 [实测]：

```
SDKUtil.GetSubChannelId        SensitiveManager / SensitiveCheckType
OnlyCN / OnlyCNAZ09 / OnlyCNAZ09Sign / REGMATCH_CN 系列
BirthDayLimit / CheckBirthDay  AccountBirthDayRequest / AccountBirthDayResponse
YostarUID / EnterTicket / Cookie / YostarServerNotSuccessStatusCode / YostarCheckFail
AccountAuthEmptyDevId / AccountCreateNoDevId / AccountCreateDuplicatedDevId
```

**判断**：实名/防沉迷/敏感词/生日这套走的是**独立协议**（`Account_BirthDay`）和**本地 `SensitiveManager`**，
不在 `Account_Auth` 的 20 个属性里。⇒ **H2 里「国服可能多要渠道/实名/防沉迷字段」这条，我判为不成立**（至少在 `Account_Auth` 这一层）。
渠道信息（`SubChannel`、`SdkPid`）是**请求**方向带的，不是响应方向。

### 3.4 一条反常，必须记下来

我们抓到的请求明文 11 个键里，`DevId` / `Token` / `SdkPid` **在整份 metadata 里都不是 C# 属性**
（`DevId` 只有 4 次命中，全在错误码枚举里：`AccountAuthEmptyDevId` 等；`SdkPid` **0 命中**，`SDKPID` 1 命中）。
只有 `Hash` 是真属性（`<Hash>k__BackingField`）。

⇒ **国服 `/api/account/auth` 的请求体不是纯 C# `AccountAuthRequest`，而是「C# 基类字段 + SDK 层塞进来的键」的混合体**
（`com.tech.sdk.TechSDK` / Airi SDK 那一层，见 `report\27`）。
那么**响应方向是否也被 SDK 层先过一道手**，现在完全没有证据。这是 H2 的一个变种：**也许要的不是「更多字段」，而是「另一套 DTO」**。

---

## 4. 非 Response 层信令检查清单（按可验证性排序）

> 排序 = 「一次实验能不能给出二值结论」× 「改动成本」。**03:45 后：本表已并入 §9.B/§9.C，此处保留作索引。**

| # | 检查项 | 为什么国服可能卡在这 | 怎么验（单变量） | 成本 | 判据 |
|---|---|---|---|---|---|
| 1 | **响应外层 `protocol` 的值形态**：名字 `"Account_Auth"` vs base32 token `"AHTQLQI65FWJGGGK4KL5AEF57A"` | 请求侧 `protocol` 就是 token（`report\35`）；客户端大概率拿响应 `protocol` 与请求 token 比对 | 同一份 packet，只改外层 `protocol` 值 | 极低 | 出现弹窗或 fresh sport=2 |
| 2 | **外层键名大小写**：`{"protocol","packet"}` vs `{"Protocol","Packet"}` | Shittim 用 camelCase（`serverPacketSettings`，`report\28 §2.5`），但那是**国际服**；国服 `BasePacket` 是 C# PascalCase | 同上，只改大小写 | 极低 | 同上 |
| 3 | **是否要 `encode` 字段**（`"encode":false` / `true`） | 请求侧有这个表单字段；响应里我们从来没给过 | 加一个 `"encode":false` | 极低 | 同上 |
| 4 | **`packet` 是「JSON 字符串」还是「base64 加密串」** | 客户端有 `DecryptOrReturnOriginal`（先解密、失败返原文）；但也有 `encryptedBase64String` 变量名 [实测] | 同一 JSON，两种 `packet` 编码各一次 | 低 | 同上 |
| 5 | **`Content-Type`**：`application/json` vs `text/plain` vs `octet-stream` | 客户端可能按 Content-Type 决定走不走 base64/解密分支 | 只改头 | 极低 | 同上 |
| 6 | **HTTP 状态码 + body 的组合矩阵**（200/204/400/404 × JSON/空） | 404 弹窗、200 不弹，说明状态码进了不同分支；**204 和 400 还没试过** | 4×2 矩阵，每格一轮 | 中 | 二值 |
| 7 | **响应头 `Date`** | 客户端可能用 HTTP `Date` 校时；nginx 默认给，但被我们 proxy 时可能被改写 | 打印实际下发的 `Date`，与 `ServerTimeTicks` 比对 | 低 | 客户端时间是否跳 |
| 8 | **分块 vs Content-Length** | `report\21 §34.2` 已测：chunked / gzip 均正常 | —— | 已完成 | **排除** |
| 9 | **gzip 编码** | 同上，`--compressed` 实测 200 + 172 B 明文 | —— | 已完成 | **排除** |
| 10 | **HTTP/2 vs HTTP/1.1** | 国服有 `DownloadServerInfoDataHttp2`、`Http2Message` 类 [实测] | 看客户端实际 ALPN；若它强制 h2，我们回 h1.1 可能被丢 | 中 | 连接层 |
| 11 | **302 / `Location`** | 没证据，但成本低 | 回一次 302 到同 host | 低 | 二值 |
| 12 | **同连接复用** | auth 用 fresh 连接后立刻 TIME_WAIT（`report\21 §32.3`）；若客户端要求后续请求复用同连接，而我们 `Connection: close`，它会重连（但它没发请求，所以不成立） | —— | 推测 | **低优先** |
| 13 | **另一个域名的请求是否要先完成** | `report\21 §37.4`：三轮 DNS 只有 `openlog`；`gs-inter:4000`、`static-qc`、`static-hs` **全程 0 次** | 已观测 | —— | **无证据，降级** |

**结论**：第 8/9/13 条已经被实测排除，别再查。真正没试过、且成本极低的是 **1/2/3/5**——它们共享同一份 packet，可以做成一次矩阵（已并入 §9.C 的 L1/L2）。

---

## 5. 一锤定音实验设计（P41-1）

> **已被 §9.C 取代/合并**：本节的 B 轮 = §9.C 的 L5，C 轮 = §9.C 的 L2。保留此节是为了记录设计演进，执行请用 §9.C。

### 5.1 核心思路：先证明「body 到底有没有被解析」

不要先改值——先**故意把 body 弄坏**。如果「坏 body」和「好 body」的行为**逐像素一致**，
那就证明客户端根本没读到 `packet` 里的 JSON，H1/H2 全部作废，直接转 H3。
这是 `report\25` 那套「改一个变量 → 逐像素比对」方法的直接复用。

### 5.2 三轮

| 轮 | 改动（**只改这一处**） | 观测 |
|---|---|---|
| **A（基线）** | 不动：`{"protocol":"Account_Auth","packet":"<3740 B JSON 字符串>"}` | `btn_px`、fresh sport 数、`E/Unity` 行数 |
| **B（毒化）** | 只把 `packet` 的**内容**换成非法 JSON：`"packet":"{\"AccountDB\":"`（外层结构一字不动） | 同上 |
| **C（形状）** | 只把**外层**换成 PascalCase + `Encode`：`{"Protocol":"AHTQLQI65FWJGGGK4KL5AEF57A","Packet":"<同一份合法 JSON>","Encode":false}` | 同上 |

判定表：

| A vs B | A vs C | 结论 | 下一步 |
|---|---|---|---|
| 相同 | 相同 | **body 从未被解析** → 卡在信封层 | 转 §4 的 1/2/3/4/5 矩阵；H1/H2 全部暂停 |
| 相同 | 不同 | 外层形状是关键 | 在 C 的方向上继续做 2×2（大小写 × token/名字） |
| **不同** | 相同 | **body 确实被解析**，问题在字段 | 进 5.3 的字段二分 |
| 不同 | 不同 | 两个坑同时存在 | 先修信封，再修字段 |

### 5.3 若判定「body 被解析」：字段二分（最多 3 轮）

| 轮 | 替换内容 | 若行为突变说明 |
|---|---|---|
| D | 把 C 类 7 个「国服不存在的键」**全删**（响应体缩到 ~2.6 KB） | 之前某个未知键触发了 `MissingMemberHandling.Error` 之类 |
| E | 保留 D，**补上 §3.1 的 10 个缺失字段** | 缺字段是主因 |
| F | 保留 E，把 `StaticOpenConditions` 从 dict(55) **改成 `[]`** | Top 1 命中：类型不符 |

### 5.4 为什么这个实验「一锤定音」

- **B 轮是零假设检验**：它不需要知道国服要什么字段，只需要知道「客户端有没有读我们的字节」。这一个二值事实，能把现在混在一起的两大类假设一次性劈开。
- 每轮只改一个变量，观测用已建好的 `btn_px` 像素判据（`report\21 §36.6`）+ fresh sport 计数。
- 全部改动都在**我们自己的响应构造函数**里，不碰客户端、不碰 Shittim 源码、不需要重编译。

---

## 6. 附：`4491` 字节那条实验的算术矛盾（建议复查）

`report\21 §37.5` 原文：

> 加密响应（encresp1：**4452 B 明文 / 4491 B 加密体**）与明文响应在客户端侧表现完全一致

按 `report\35` 已证死的信封格式 `"[u32 长度][gzip([iv:16][ct][key:32])]" → base64 → 塞进 packet`，
我用 Python 实测算了各尺寸下的应有长度 [实测]：

| 明文 | 内层 = 16 + pad + 32 | gzip 后 | +4 | base64 | 外层 JSON 总长 |
|---|---|---|---|---|---|
| 3740 B | 3792 | 3815 | 3819 | **5092** | **5131** |
| 4452 B | 4512 | 4535 | 4539 | **6052** | **6091** |

再反过来解 `body = 4491`：

```
4491 - 39(外壳) = 4452(packet 字符) → 原始 3339 B → gzip 3335 B → 内层 ≈ 3320 B
→ ct = 3320 - 48 = 3272 B，3272 % 16 = 8   ← 不是 16 的整数倍，PKCS7 不可能
```

**结论**：4491 字节**在任何一种解释下都不是 `cn_cipher.wrap_packet()` 的合法输出**（差 8 字节对齐）。所以：

- 要么 encresp1 用的根本是另一套布局（那它就不是「加密响应」的正确实现，这轮实验无效）；
- 要么 4491 这个数字记错了（可能是 HTTP body 长度、也可能是 gzip 后长度）。

**在这一点澄清之前，`report\21 §37.5` 的「响应是否加密不是卡点」这句话应当撤回**——它现在是一条**未成立的证据**，而它恰好会误导我们放弃 H3。

> 建议：把 encresp1 的**实际响应字节**（或至少它的 packet 字段前 32 字节 + 总长）找回来，离线跑一遍 `cn_cipher.unwrap_packet()`。三秒钟就能判定它是不是合法信封。

---

## 7. 没做 / 读不到（诚实标注）

| 项 | 状态 | 原因 |
|---|---|---|
| `AccountAuthResponse` 各属性的**类型**（string/list/dict/bool） | **未取得** | `global-metadata.dat` 头部 magic = `0x12724394` ≠ `0xFAB11BAF`，`typeIndex` 表读不到（`report\24 §3` 已独立复现）。本报告只能给「物理相邻的属性名序列」 |
| `StaticOpenConditions` 是 dict 还是 list | **未定** | 同上；只给了「怎么判」的方法 |
| `Desc` / `FunctionClose` 的类型 | **未定** | 同上 |
| 国服「会话凭据」到底叫什么 | **未定** | `SessionKey` 0 命中；`SessionDB` 是游戏 DB。需要枚举所有 `*Token/*Key` 属性逐个对 |
| 国服网关的**真实响应样本** | **不存在** | 全项目 39 份报告里 0 份抓到过（`report\32 §8.3`） |
| 请求体 `DevId/Token/SdkPid` 的来源 | **推断为 SDK 层** | 三者都不是 metadata 里的 C# 属性；`SdkPid` 0 命中 |
| `AccountAuthResponseMessage` 自身字段 | **空** | metadata 里该类名后面直接跟 `AccountAuthNetworkTask`，无自有字段 → 推断它继承 DTO |

### 可以交给别的 agent 的两件事（避免重复劳动）

1. **给 `ll2cpp-analyst`**：只要确认 `AccountAuthResponse` 的 `StaticOpenConditions` / `FunctionClose` / `Desc` 三个属性的**类型**即可——这直接决定 Top 1 成不成立。方法：解 il2cpp 的 `Il2CppTypeDefinition.fieldStart`（需要先绕过 metadata 头加密）。
2. **给 Frida 线（`report\38`）**：`HttpGameMessage.DecodeResponse` 的返回值 + `NetworkService.ParseReceivedString` 的入参，一次 attach 就能替代 §9.C 的 L0/L5 两枪（能直接看到「客户端拿到的 body 是什么、解析成功没有」）。

---

## 8. 给 lead 的三句话（03:45 后已按新证据重排）

1. **先别再猜字段了**：客户端**没有任何「编码响应」的代码**（`EncryptResponse`/`EncodeResponse`/`DecryptResponse` 全 0 命中），而解密要用的 `aesKey/aesIV` 只能由从未发生的 `Queuing_*` 换钥拿到 ⇒ **加密响应这条线可以整条撤掉**，明文 JSON 是对的方向。
2. **`/api/account/auth` 不是登录专用服务**，是 `ApiUrl + SendRequestApi` 这条 REST 传输上 `Account_Auth` 的路由（客户端同时有 `GatewayUrl + SendRequestGateway` + `IsGatewayBypassed` 开关）⇒ 我们错的是**传输层假设**，不是协议名。**下一个必炸的坑**：如果国服全程走 REST，第二条协议会是 `/api/<group>/<name>`，nginx 现在很可能没兜。
3. **今晚只做一件事：§9.C 的 L5 毒化探针**（`packet` 里塞 `{"CurrentVersion":"P41-CANARY"}`）。它回答「body 有没有被解析」这个二值问题，比再试十种字段值都值钱。

---

## 9. 响应格式专章（A / B / C，03:45 新增）

> 本节回答 lead 收缩后的唯一核心问题：**`POST /api/account/auth` 的 200 响应体，客户端期待什么格式？**

### 9.A 加解密是否双向对称 → **不对称：客户端只有「解码响应」，没有「编码响应」**

**实测（`global-metadata.dat`，均为全文件精确串搜索）**

| 符号 | 命中 | 含义 |
|---|---|---|
| `PacketCryptManager.EncryptRequest` | 1（`0x25e38e`） | **请求**方向的唯一加密入口 |
| `HttpGameMessage.DecodeResponse` | 2（`0x21a4d2`） | **响应**解码入口 |
| `DecryptOrReturnOriginal` | 2（`0x21a4e1`） | 解不开就返回原文 |
| `HandleDecryptionError` / `IsSpecificErrorJson` | 2 / 2 | 解密失败分支 + 「是不是某个特定错误 JSON」 |
| `encryptedBase64String` | 1（`0x21a4bc`） | `DecodeResponse` 里的局部变量名 |
| **`EncryptResponse`** | **0** | —— |
| **`EncodeResponse`** | **0** | —— |
| **`DecryptResponse`** | **0** | —— |
| **`MakeResponse`** | **0** | —— |

⇒ **客户端侧不存在「如何生成一个加密响应」的任何代码符号**，只有「如何解码一个响应」。

**第二层证据（更硬）：它没有钥匙。**
- 响应解密器 `CryptAES.DecryptRJ256Api`（`0x259bf7`）用的 key/iv 来自 `GameSessionManager.aesKey` / `aesIV`，而这两个字段只能由 `SetAesParameters` / `VerifyAndSetAesParameters` 写入；
- 该写入的唯一来源是 `Queuing_GetAuthTicket` / `Queuing_GetCryptoKeys` 的 RSA 换钥（`report\27 §四`、`report\28 §3.2`）；
- **客户端从未发出任何 `Queuing_*` 请求**（lead 新证据）⇒ `aesKey == null`；
- ⇒ 任何我们发过去的加密响应，它**必然解不开**，只能落到 `DecryptOrReturnOriginal` 的「返回原文」分支。

**结论 A**：响应方向**不需要加密**；`report\34 §六` 的推断（`DecryptOrReturnOriginal` ⇒ 可回明文）**成立**。
`report\21 §37.5`「加密响应也无效」那条实验，既算术不成立（§6），方向上也不再重要——**它不是卡点**。

---

### 9.B `/api/account/auth` 与 `/api/gateway` 的关系

**实测：客户端有两套并列传输，且带一个旁路开关**（同一属性簇，`0x219cc9`–`0x21a27a`）：

```
ApiUrl        + NetworkService/SendRequestApi
GatewayUrl    + NetworkSender.SendRequestGateway
IsGatewayBypassed (get/set)          ← 旁路开关
```

旁边还有一整套**会话级 AES 参数**：`aesKey` / `aesIV` / `SetAesParameters` / `base64AesEncryptedKey` /
`base64AesEncryptedIV` / `base64RsaSignedKey` / `base64RsaSignedIV` / `VerifyAndSetAesParameters`
—— 这套正是国际服 `Queuing_GetCryptoKeys` 握手用的；**国服这条链没走，所以它是空的**。

**关键推论**

| # | 推论 | 依据 |
|---|---|---|
| 1 | `ApiUrl` 来自 `state-api` 的 `Servers`（`https://gsqc-api.../api/`），客户端拼成 `{ApiUrl}account/auth` | `report\31 §三` 的真实 161 B `Servers` |
| 2 | **`/api/account/auth` = `Account_Auth` 在 REST 传输下的路由**，不是独立的登录服务 | 两套传输并存 + `IsGatewayBypassed` |
| 3 | 全文件 `"gateway"` 字面量 **0 命中**、`"account/auth"` **0 命中** ⇒ 路径是运行时拼的，不是写死的两个端点 | 实测 |
| 4 | 我们 bridge 的**协议层**处理（解包 → `{"Protocol":"Account_Auth"}` → Shittim）**没错**；错的是**传输层**按 `/api/gateway` + `.mx` 的语义去理解它 | —— |
| 5 | **下一个必炸的坑**：若国服全程走 REST，后续协议会是 `/api/account/nickname`、`/api/queuing/ticket`、`/api/account/loginSync` 之类；nginx 必须把 `/api/*` 全兜到 bridge，否则第二条请求会 404（而 404 会弹窗） | 推论，**建议立刻核对 nginx location 表** |

**第三条旁证：同一个 App 里跑着多套 HTTP 栈，U/A 可区分**

| 请求 | U/A | 对应 metadata 类 |
|---|---|---|
| `GET /api/state` | `UnityPlayer/2021.3.56f2 (UnityWebRequest/1.0, libcurl/8.10.1-DEV)` | `Http2Message` / `Http2DownloadMessage` |
| `POST /api/account/auth` | `BestHTTP/2 v2.4.0` | `Http1Message`（带 `encode` 字段、`get_WebRequest`/`get_StatusCode`/`get_DownloadText`） |

⇒ **登录这一枪走的是 `Http1Message`(BestHTTP) 分支，它的响应解码路径与 `/api/state` 不是同一段代码**，不能拿 state 的成功经验外推。
metadata 里 `BestHTTP` 有 **135** 处命中（插件被编进包里），`HTTPRequest` 5 处。

**关于候选 4（protobuf / msgpack）：基本可排除** [实测]
`MessagePack` **0** 命中、`ProtoBuf`/`Protobuf` **0** 命中；而 `JsonConvert` 7、`JObject` 6、`FromJson` 5、
`NetworkService.ParseReceivedString` / `ParseProtocol` / `ParsePacketString` 全在。
⇒ 响应体是**字符串 JSON**，不是二进制序列化格式。

**关于候选 5（两段式纯文本，03:52 新增）——建议顺手加一枪**
`get_Packet` / `set_Packet` 在国服 metadata **0 命中**，`ServerResponsePacket` 也 **0 命中**；
而响应解析入口叫 `NetworkService.ParseProtocol` + `ParsePacketString`（+ `receivedString` 字段）。
如果客户端是把 `DownloadText` **按两段切开**（协议段 + packet 段），而不是 `JObject["protocol"]`/`["packet"]`，
那么任何 `{...}` 形式的 body 都**永远不会被解析**——这与「四种 body 行为完全一致」高度吻合。
【推断，未验证】两段的分隔符未知，候选：`\n`、`:`、`|`、或者前 26 字符就是 base32 token。
成本极低：L6 打一发 `<26 字符 token>\n<3740 B JSON>` 即可。

**关于候选 2（另一种新封装）：目前没有任何独立证据**，只可能藏在 `Http1Message.encode` 这个字段的语义里——见 9.C 的 L2。

---

### 9.C 判别实验（一次冷启动，7 枪）

#### 设计要点

1. **404 → 弹窗来自状态码分支**（`HandleServerError` / `ShowDefaultNetworkError`），**与 body 无关**。所以「状态码」只能当**对照组**，不能当 body 格式的探针。
2. 200 下客户端对失败**可能是静默的**（`report\21 §34.1`：该窗口 `E/Unity` 0 行），所以必须自带一个**「只要被解析就必然炸」的毒化包**，否则分不清「解析失败」与「根本没解析」。
3. 每枪**只改一个变量**，三信号同时记录：`btn_px`（弹窗像素，`report\21 §36.6` 的判据）/ fresh sport 数 / `E/Unity` 行数。

#### 七枪

| 枪 | HTTP | 响应体（除注明外都是 `application/json`） | 验证哪个候选 |
|---|---|---|---|
| **L0** | 200 | `{"protocol":"Account_Auth","packet":"<3740 B JSON 字符串>"}`（现状） | 基线 |
| **L1** | 200 | 仅改 `protocol` 值 → 请求里那个 base32 token `AHTQLQI65FWJGGGK4KL5AEF57A` | 外层值形态 |
| **L2** | 200 | 仅改外层 → `{"Protocol":"Account_Auth","Packet":"<同一份>","Encode":false}` | 大小写 + Encode 语义 |
| **L3** | 200 | 裸二进制 mx，`Content-Type: application/octet-stream`：`[u32 crc][i32 conv][u8 0][u8 0][u32 len][gzip(JSON)]` | 候选 1（mx 封装） |
| **L4** | 200 | `packet = base64([u32][gzip([iv16][ct][key32])])`，**key 直接用客户端这次请求包里那把**（别新生成） | 「响应复用请求信封/密钥」 |
| **L5** | 200 | **毒化**：`{"protocol":"Account_Auth","packet":"{\"CurrentVersion\":\"P41-CANARY\"}"}` | **body 到底有没有被反序列化** |
| **L6** | 200 | `Content-Type: text/plain`，body = `AHTQLQI65FWJGGGK4KL5AEF57A` + `\n` + `<3740 B JSON>`（两段式，候选 5） | 响应是否根本不是 JSON 对象 |

> L3 的 `crc` / `conv` 可以直接填 0（Shittim 的 `DecodeGatewayPayload` 对 0 容忍，`report\32 §1.2`）。
> L4 复用客户端 key 的理由：客户端在本次请求里把 key 明文附在包尾，若服务端沿用同一把，客户端**无需额外钥匙**就能解——这是唯一一个「不需要 Queuing 换钥也能成立」的加密方案（**推断，未验证**）。

#### 判读矩阵

| 观测 | 结论 | 下一步 |
|---|---|---|
| **L5 有反应**（弹窗 / 新请求 / `E/Unity`） | **body 确实被反序列化** | 转 §1–§3 字段清单（缺 3 个基类集合 + `Desc`/`FunctionClose`/`DailyRecordDBs`；`SessionKey` 0 命中） |
| L5 无反应，L1/L2/L3/L4/L6 任一有反应 | 外层形状/封装错 | 用命中的那枪继续二分（大小写 × token/名字 × Encode × 两段式） |
| **七枪全无反应** | **body 从未被消费** | 停掉字段排查 → 转传输层：`Content-Length`/chunked/gzip/`Connection`/`Date`；并查「它是不是根本不在这个连接上等响应」 |

#### 今晚可以先跑的「零成本三枪」（不改 bridge，只改 nginx 返回体）

| 枪 | 响应 | 若与 L0 完全一致说明 |
|---|---|---|
| Z1 | `200` + **空 body**（`Content-Length: 0`） | 空 body 与 3740 B 无差别 ⇒ body 不参与决策 |
| Z2 | `200` + `{}` | 同上 |
| Z3 | `200` + 非 JSON 文本 `P41` | 同上 |

三枪全静默 ⇒ **直接跳到传输层**，省掉整轮字段实验。

---

### 9.D 对 §5（P41-1）的修订

原 §5 的 B 轮（毒化 body）与本节 L5 **是同一个实验**，以本节为准；原 §5 的 C 轮（外层大小写）并入 L2。原 §5 的 A 轮基线保留。

---

## 10. 复跑检查（本次分析用到的命令，零外部依赖）

```python
# 1) 国服 AccountAuthResponse 属性簇（20 个）
import re
d = open(r"work\ba\...\Metadata\global-metadata.dat", "rb").read()
i = d.find(b"get_TTSCdnUri")
print(d[i-100:i+1200].decode("latin-1"))

# 2) 关键符号命中数（用于 §9.A 的对称性判定）
for t in [b"EncryptResponse", b"EncodeResponse", b"DecryptResponse", b"DecodeResponse",
          b"DecryptOrReturnOriginal", b"get_Packet", b"SessionKey", b"AccountRestrictionsDB",
          b"AttendanceBookRewards", b"MessagePack", b"ProtoBuf"]:
    print(t, len(re.findall(re.escape(t), d)))

# 3) 4491 的算术矛盾（纯 gzip/base64，无外部依赖）
import gzip, os
n, inner = 3740, 16 + ((3740 + 15)//16)*16 + 32
print(len(gzip.compress(os.urandom(inner)))*4//3)   # ≈ 5092
```

