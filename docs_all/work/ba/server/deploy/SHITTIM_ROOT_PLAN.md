# Shittim-Server 接管方案（CN 3.0.2 根因方案）

> 产出：2026-11-17 · 作者：shittim-analyst
> 目标：回答「让 Shittim 真正接管业务与存档、Python 桥退化为信封代理」的可行性问题
> **方法**：GitHub API（`api.github.com`，`Accept: application/vnd.github.raw`）拉源码到本地临时目录再逐份读；`raw.githubusercontent.com` 在本机被 reset，不可用（与 `report\28` 附录 B 一致）
> **核对基准**：`Neoexm/Shittim-Server` **main = `5f3910ea44a8798c213ea12a3e85f182194f92c6`（committer date 2026-08-20T14:33:17Z，msg "fixed db issue"）**
> ★ **这个 sha 与 `report\28` 用的基准完全相同** ⇒ 本地快照 `report\_tmp\shittim\src\` 就是当前 main，下文所有引用本地快照的 `文件:行号` 对 main 有效。
> 证据分级：`[源码实测]` / `[本地数据实测]` / `[团队实测]`（引用既有报告或 `work\ba\server\` 下的既有产物）/ `[未确认]`

---

## 0. 一页结论

| 问题 | 结论 |
|---|---|
| **1. 对外协议** | Shittim **不是** `/api/account/auth` 这种按协议分路径。**全部游戏协议只有一个入口 `POST /api/gateway`**，body 是 `multipart/form-data` + 字段 `mx`（二进制）。内层是**纯 JSON**（Newtonsoft），**不是 flatbuffer**。`Schale/BlueArchive.fbs`（304 KB）只用于 **Excel 表数据**，与网络层无关。加密/压缩只在外层 `mx`（XOR 0xD9 + GZip），且握手可关。 |
| **2. 存档与账号** | EF Core + **SQLite**（可切 SQL Server），71 个 DbSet。建号在 `AccountService.CreateAccount()`，**种子数据全部来自 4 张 Excel 表**（`DefaultParcelExcel` / `DefaultCharacterExcel` / `DefaultEchelonExcel` + cafe/academy/mail）。**教程送的角色不是硬编码**，由 `DefaultCharacterExcel` 决定；我用本地 ExcelDB 解出来是 **优香(13010,★2) / 铃美(16003,★1) / 莲见(13003,★2,纪念大厅指定) / 千夏(26000,★1)** —— 正好解释"卡在早濑优香的记忆大厅"。 |
| **3. CN 能不能接** | **能，而且比预想便宜**：CN 的内层 JSON 与 Shittim 的 `ResponsePacket` **只差 1 个字段 `RequestId`**（另加请求侧 `Hash`↔`RequestId`）。外层信封形态（`protocol/packet/requestid`）与 `mx` 完全不同，必须由代理转换。**Shittim 没有任何 CN/多版本开关**（`[源码实测]`）。 |
| **4. 最小改造** | **推荐 (a) Python 桥做信封翻译**——但执行点要挪到"每个协议都 `POST /api/gateway`"，而不是现在的"自造 JSON"。同时补两个不变量：**回显 `requestid`**、**注入/透传 `SessionKey`**。工作量 ~250–400 行 Python，1 次跑通概率最高。 |
| **5. 最大的坑** | ① ExcelDB 版本（CN 3.0.2 vs Shittim 默认拉国际服 1.93）；② `RequestId` 缺失导致客户端不认包；③ CN 没有 `Hash`→Shittim 的会话校验（`ValidateRequest` 是**死代码**，真正的校验在 handler 里的 `GetAuthenticatedUser`）；④ 抽卡/战斗/竞技场等协议 Shittim 有 handler 但 CN DTO 可能多字段。 |
| **6. 发东西的正规通道** | **有：`Shittim-Server/Commands/` 的 23 条 GM 命令**（`!giveall` / `!max all` / `!currency Gem N` / `!character add …` / `!mail` …）。**只有"控制台"这条路真能执行**；HTTP `POST /dev/api/command` 是 **stub（从未调用 `CommandFactory`）**，千万别用。用户要的"全角色+全90+几百万青辉石"= 三条命令，全走 EF 写库的正常机理。 |
| **7. 数据模型** | EF Core + SQLite，**无 `Migrations/`**，靠启动时 `SchemaReconciler` 反推补列。复杂列（`CurrencyDict`、`FurnitureDBs`、`PotentialStats`…）**一律是 JSON 文本**（`HasJsonConversion` 唯一转换器）。`Characters.UniqueId = CharacterExcel.Id`，而 Echelon/代表角色引用的是 **`ServerId`（自增主键）**——裸 SQL 必踩。 |
| **8. Session 硬阻塞** | 报错 `"Session key required"` = 请求里 `SessionKey` **整个为 null**（不是值错）。**`Account_Auth` 永远不能第一个发**：会话只能由 `Account_CheckNexon(1014)` / `Account_CheckYostar(1009)` 铸（`AccountHandler.cs:96 / :943`）。`BypassAuthentication` 与免会话白名单**都是死代码，开关无效**。 |
| **9. 多玩家** | **Shittim 侧本来就支持多账号**（主键自增 + 会话按账号键 + 种子按 `AccountServerId` 隔离），**一行都不用改**。桥侧三处结构性错误全在桥：硬编码 ticket / 全局单例 session / 没有映射表。**最小改动 = 把硬编码的 uid 换成请求明文里的 `DevId` 当 publisherId**（不必另发号）。⚠ 唯一跨账号的共享结构是 `GatewaySessionCryptoBuilder` 的全局 AES 密钥表（扫全表），走明文 `keyLen=0` 即可永不触发。 |

---

## 1. Shittim 的对外协议长什么样

### 1.1 HTTP 路由：只有一个游戏入口

`[源码实测]` `Shittim-Server/Controllers/Api/GatewayController.cs:100-158`：

```csharp
[ApiController]
[Route("api")]                                   // :101
public class GatewayController : ControllerBase  // :102
...
[HttpGet] [Route("Queuing/Ping")] public IResult Ping() => Results.Ok("Pong");  // :150-152
[HttpGet("gateway")]              public IResult GatewayHealthCheck() => Results.Ok();  // :154-155
[HttpPost("gateway")]             public async Task GatewayRequest()                     // :157-158
```

**⇒ 不是 `/api/account/auth`。** 路径里**没有协议名**：协议名在 `mx` 内层 JSON 的 `Protocol` 字段里（`GatewayController.cs:412-422` `ReadProtocol`，int 或枚举名字符串都认）。

`[源码实测]` 控制器全表（GitHub 文件树），与游戏协议无关的那些：

| 目录 | 控制器 | 用途 |
|---|---|---|
| `Controllers/Api/` | `GatewayController` / `ServerInfoController` | **游戏协议 + 版本/连接组** |
| `Controllers/SDK/` | `IasController` / `ToySDKController` / `GTableInfaceController` / `PublicApiController` / `StampController` / `ConfigNaController` / `ProhibitedWordController` / `OtherController` | **Steam/inface 启动器**的登录、gtable、禁词表 |
| `Controllers/` | `AdminController` / `ManagementController` / `BannerController` / `AddressablesController` / `ModsController` | 控制台 / 资源 / 公告 |
| `Controllers/GM/` `Controllers/Dev/` | 若干 | GM 与开发 |

`[源码实测]` 另有 `GameServer.cs:251 app.MapGet("/health", ...)`。

> ⇒ 对 CN 客户端来说，**除了 `/api/gateway`、`/api/Queuing/Ping`、`/log`（`ServerInfoController.cs:47`）之外的所有 `api/<服务>/<动作>` 路径都不存在**（与 `report\44` §4 的推导一致）。

### 1.2 JSON 还是 flatbuffer？——**网络层是 JSON，flatbuffer 只给 Excel**

| 层 | 格式 | 证据 |
|---|---|---|
| 网络请求内层 | **JSON**（字符串） | `GatewayController.cs:412-422` 从 `JObject` 读 `Protocol`；`:630-656` `TryReadJson` 要求首字符 `{`；`:215` `JsonConvert.DeserializeObject(payloadStr, requestType)` |
| 网络响应内层 | **JSON** | `:268` `JsonConvert.SerializeObject(rsp, jsonSettings)` |
| 网络响应外层 | **JSON** | `:794` `JsonConvert.SerializeObject(packet, serverPacketSettings)`（camelCase） |
| Excel 表 | **FlatBuffers** | `Schale/BlueArchive.fbs`（304,085 B）+ `Schale/FlatData/` **912 个**生成类（文件名形如 `CharacterExcel.cs` / `AccountLevelExcel.cs`…） |

`[源码实测]` 佐证：`Schale/FlatData/DefaultCharacterExcel.cs` 里 `ValidateVersion()` 调用 `FlatBufferConstants.FLATBUFFERS_25_2_10()` —— 这是 **FlatBuffers 25.2.10 生成的 Excel 表读取器**，入口是 `UnPack()`/`UnPackTo()`，跟 HTTP 无关。

⇒ **`.fbs` 用来把 `ExcelDB.db` 里的表反序列化成 `*ExcelT` 对象**，供 `ExcelTableService.GetTable<T>()` 使用（`AccountService.cs:32,40,76` 全是这种调用）。

**⇒ 由此得到本次最重要的可行性判断：CN 客户端的内层是 JSON，Shittim 的内层也是 JSON ⇒ 不存在"flatbuffer 换算"这件事，转换代价 = 0。**

### 1.3 加密 / 压缩层：有，但可以整体旁路

`[源码实测]` `mx` 文件布局（`GatewayController.cs:360-409` `DecodeGatewayPayload`）：

```
0  uint32 crc | 4 int32 typeConversion | 8 uint8 keyLen | 9 uint8 ivLen
10 byte[keyLen] headerKey | byte[ivLen] headerIv | byte[] rawPayload
```
`rawPayload` = `XOR(0xD9)( [u32 声明长度] + gzip(JSON) )`（`:462-493` 三种变体全试，`RequestXorKey = {0xD9}` 在 `:107`）。

**可以关掉 AES**：`[源码实测]` `:514-517`

```csharp
var responseCrypto = (headerKey.Length > 0 && headerIv.Length == 16 && IsValidAesKeyLength(headerKey.Length))
    ? new GatewayCryptoContext(true, headerKey, headerIv)
    : GatewayCryptoContext.None;
```

⇒ **`keyLen=0, ivLen=0` ⇒ 双向明文**。`cn_cipher.py:135-141` 的 `build_mx()` 就是这么造的（`crc=0, conv=0, keyLen=0, ivLen=0`），且 `report\35:116` 记录它被 Shittim 正常处理。
**⇒ 代理侧只需 gzip + XOR 1 字节，不需要 RSA、不需要 AES。**

### 1.4 协议号 → handler：反射 + 特性，无配置文件

`[源码实测]` 三步：

1. **请求/响应类型的注册表**：`Shittim-Server/Core/ProtocolHandlerFactory.cs:30-52` —— 反射扫描 `RequestPacket`/`ResponsePacket` 程序集里所有非抽象子类，`Activator.CreateInstance` 后读 `Protocol` 属性，建立 `Dictionary<Protocol, Type>`。
2. **handler 方法注册表**：`…/ProtocolHandlerFactory.cs:54-67` `RegisterInstance()` —— 扫描带 `[ProtocolHandler(attr)]` 的方法；`Shittim-Server/Core/ProtocolHandlerRegistry.cs:64-104` 是同一逻辑的另一份实现。
3. **装配**：`Shittim-Server/Core/ProtocolHandlerExtensions.cs:23-37` `InitializeProtocolHandlers()` 在 `GameServer.cs:184` 被调用，遍历所有 `ProtocolHandlerBase` 子类逐个 `RegisterHandlerType`。

对外的门面是 `HandlerManager`（**本地快照缺、现已补读**）：

```csharp
// Shittim-Server/Core/HandlerManager.cs:14-19
public bool IsImplemented(Protocol protocol) => _registry.GetHandler(protocol) != null;
public Type? GetRequestType(Protocol protocol) => _registry.GetRequestType(protocol);
public Task<ResponsePacket?> Dispatch(Protocol protocol, RequestPacket request) => _registry.InvokeHandler(protocol, request);
```

⇒ **新增协议 = 加一个 DTO 类（带 `Protocol` 属性）+ 一个 `[ProtocolHandler]` 方法**，不需要改路由、不需要注册表。

### 1.5 ★ 会话校验其实不在网关层（重要，纠正 42 号的一个推断）

`[源码实测]` `SessionKeyService.cs:114-145` 有 `ValidateRequest()`，`_publicProtocols` 白名单（`:17-28`）也在。
**但 `GatewayController` 全文（802 行）没有调用 `ValidateRequest`，`ProtocolHandlerRegistry.InvokeHandler` 也没有**（`ProtocolHandlerRegistry.cs:124-181` 逐行确认）。

⇒ **`ValidateRequest` / `_publicProtocols` / `BypassAuthentication` 在当前 main 上是死代码。**
真正的鉴权发生在**每个 handler 内部**：`_sessionService.GetAuthenticatedUser(db, request.SessionKey)`（如 `AccountHandler.cs:116, 259, 295`），它检查 `_activeSessions` 里的 GUID（`SessionKeyService.cs:147-164`），失败抛 `UnauthorizedAccessException` → 网关转成 `Error` 信封（`GatewayController.cs:287-295`，200 状态码）。

**这对方案的直接影响**：任何 handler 若 `SessionKey` 不对，就会回 Error。CN 客户端如果没带对 `SessionKey`，**逐协议报错而不是统一 401**。⇒ 代理必须保证 SessionKey 正确（见 §3.3）。

---

## 2. 存档与账号

### 2.1 持久化

| 项 | 值 | 证据 |
|---|---|---|
| ORM | **EF Core**，`IDbContextFactory<SchaleDataContext>` | `DBServiceExtensions.cs:13-19` |
| 数据库 | **SQLite**（默认）/ SQL Server（可切） | `DBServiceExtensions.cs:16-24`；`SchaleDataContext.cs:414-416` `UseSqlite("Data Source=schale.sqlite3")`，`:97` `UseSqlServer`，`:411` |
| 连接串来源 | `Config.Instance.ServerConfiguration.SQLProvider` / `SQLConnectionString` | `DBServiceExtensions.cs:13-14`；配置类型见 `report\28` §4.2（`SQLProvider` 默认 `"SQLite3"`） |
| 表数 | **71 个 DbSet** | `SchaleDataContext.cs`（`grep 'public DbSet<'` = 71） |
| 建表 | 无 migrations：`CanConnect()`→`EnsureCreated()`，再 `SchemaReconciler.ReconcileAsync()` 反推补列 | `GameServer.cs:186-206`（`report\28` §4.5 已引） |
| 其它落盘状态 | `Config/sessions.json`（会话）、`Config/gateway_aes_sessions.json`（网关 AES 历史）、`server_notice.json`（维护门/强制通知位） | `SessionKeyService.cs:32-33`、`GatewaySessionCrypto.cs:27`、`ServerNoticeService.cs:13` |

**`server_notice.json`**（本轮新确认）：`[源码实测]` `ServerNoticeService.cs:26-52` 读 `AppDomain.BaseDirectory/../server_notice.json`；`gate_error != 0` 时**除 `Queuing_GetCryptoKeys` 外全部回 Error**（`:65`）。**默认文件不存在 ⇒ 门是关的**（`:31-32`）。⇒ 排查"所有协议都失败"时先看这个文件。

### 2.2 新建账号时种入什么

`[源码实测]` `AccountHandler.cs:52-106`（`CheckNexon`）/ `:899-953`（`CheckYostar`）在账号不存在时：
```csharp
var newAccount = new AccountDBServer(publisherId);
db.Accounts.Add(newAccount);
await db.SaveChangesAsync();
user.Uid = account.ServerId;
await AccountInitializationService.InitializeCompleteAccount(db, account);   // ★ 全部种子在这里
await db.SaveChangesAsync();
```

`[源码实测]` 种子实现 = `Shittim-Server/Services/AccountService.cs` 里的 `AccountInitializationService`：

| 顺序 | 种什么 | 数据来源 | 行号 |
|---|---|---|---|
| 1 | 货币行 `AccountCurrencyDBServer` | 代码 | `:28-30` |
| 2 | **默认资源**（AP/钻/券…） | `DefaultParcelExcel` | `:32-38` |
| 3 | ★ **角色**（含星级/等级/技能） | **`DefaultCharacterExcel`** + `CharacterExcel` 校验 | `:40-74` |
| 4 | ★ **初始编队**（1 队，含 leader/main/support） | `DefaultEchelonExcel` | `:76-100` |
| 5 | 4×5 编队预设 + 4 组预设组 | 代码 | `:102-130` |
| 6 | 咖啡厅 ×2、家具、来访者 | 代码 + `CafeService` | `:180-233` |
| 7 | 课程表（Academy）区域/来访 | `AcademyService` | `:248-254` |
| 8 | ★ **代表角色（大厅/纪念大厅）** | 取 `DefaultCharacterExcel` 里 `FavoriteCharacter==true` 的那个 | `:261-265` |
| 9 | 欢迎邮件 | `DefaultMail` + `LocalizeExcel` | `:329` 附近 |
| 10 | 关卡历史（自动通关若干主线，让功能解锁） | 代码 + `CampaignExcel` | `:349-372` |

### 2.3 ★ 教程送的角色是谁（本轮新解出来的硬证据）

**代码侧**：`[源码实测]` `AccountService.cs:40-54` —— 完全由 `DefaultCharacterExcel` 表驱动，**没有任何硬编码 CharacterId**：

```csharp
var defaultCharacters = excelTableService.GetTable<DefaultCharacterExcelT>();   // :40
var characterExcel = excelTableService.GetTable<CharacterExcelT>()              // :41
    .Where(x => x.IsPlayable && x.IsPlayableCharacter)…;
var newCharacters = defaultCharacters.Select(x => new CharacterDBServer() {
    UniqueId = x.CharacterId, StarGrade = x.StarGrade, Level = x.Level, … });   // :45-71
```

**数据侧**：`[本地数据实测]` 我手工解了本地 `work\ba\data\_excel_unzip\defaultcharacterexceltable.bytes`（**312 B**，FlatBuffers，按 `DefaultCharacterExcel.cs` 的 vtable 布局逐字段读）：

| # | CharacterId | StarGrade | Level | Favorite | 用 `LocalizeCharProfileDBSchema` 解出的角色 |
|---|---|---|---|---|---|
| 1 | **13010** | **2** | 1 | false | **早濑优香**（千禧年科技·研讨会会计） |
| 2 | **16003** | 1 | 1 | false | 铃美（崔尼蒂自警团） |
| 3 | **13003** | **2** | 1 | **true** | 羽川莲见（正义实现部二号） |
| 4 | **26000** | 1 | 1 | false | 千夏（歌赫娜风纪委员会医疗） |

`[本地数据实测]` 名字来源：`ExcelDB.db` 的 `LocalizeCharProfileDBSchema(CharacterId, Bytes)`（flatbuffer blob 里取 UTF-8 串）。
`[本地数据实测]` 表中字段值（1、2）是明文整数 ⇒ **该份 ExcelDB 的字段级加密是关的**（对应 `TableEncryptionService.UseEncryption == false`），Shittim 默认 `UseEncryption=false`（`report\28` §4.2）**能直接吃**。

> **⇒ 对着 lead 的现象核对：优香(13010) 就在这 4 个里，而 `FavoriteCharacter=true` 的是莲见(13003) → 会成为 `RepresentCharacterServerId`（`:261-265`）。**
> 也就是说 CN 客户端在"过完教程进大厅"这一步要读的那套角色/纪念大厅数据，**Shittim 建号时本来就种好了**；我们现在卡住是因为桥自造响应里根本没有 `CharacterDBs`。

### 2.4 教程 / GuideMission 怎么驱动，哪些 state 必须落盘

`[源码实测]` 教程是**两个独立机制**：

1. **TutorialIds（客户端驱动的进度）** —— `AccountHandler.cs:656-670` `Account_GetTutorial`：读 `db.AccountTutorials`，**没有行就回 `Enumerable.Range(1, 27)`（= 1..27 全未完成）**；`Account_SetTutorial`（`:672-698`）把客户端报上来的 `TutorialIds` 整份覆盖写回。
   ⇒ **必须落盘**：`AccountTutorial.AccountServerId + TutorialIds`（模型 `Schale/Data/Models/AccountTutorial.cs`）。
2. **GuideMission（服务端任务进度）** —— `AccountHandler.cs:299` `_missionService.UpdateMissionProgress(db, account, MissionCompleteConditionType.Reset_DailyLogin, 1)`；`MissionHandler` 负责清单/领奖。任务进度存在 `MissionProgressDB`（`Schale/Data/GameModel/ProgressModel/MissionProgressDB.cs`），进 `ResponsePacket.MissionProgressDBs` 下发。
   ⇒ **必须落盘**：`MissionProgresses` / `MissionHistories`。

**`Account_LoginSync`（1019）是大厅数据总闸**：`[源码实测]` `AccountHandler.cs:288-655` 一次性下发
`CafeGetInfo / AccountCurrencySync / CharacterList / EquipmentItemList / CharacterGearList / EchelonList / MemoryLobbyList / CampaignList / ArenaLogin / MultiFloorRaidSync …`
—— 注释 `:307`「咖啡厅由这个 sync 喂，不是 Cafe_Get」、`:445`「官方 LoginSync 没有 ItemList 子包（客户端随后自己拉 Item_List）」。

⇒ **"没有存档/角色/任务空"的三个症状分别对应**：`CharacterDBs`、`MissionProgressDBs`、`AccountTutorial.TutorialIds` 三处都没落盘。Shittim 三处都有。

---

## 3. CN 客户端能不能接 Shittim

### 3.1 关键判断：内层 JSON **同构**，只差 1 个字段

| 层 | CN 3.0.2（团队实测） | Shittim | 差异 |
|---|---|---|---|
| 传输 | `POST /api/account/auth`（按协议分路径）、`multipart` 三文本字段 `protocol`/`encode`/`packet` | `POST /api/gateway`、`multipart` 单字段 `mx`（二进制） | **完全不同** |
| 外层信封 | `{"protocol":"<名字>","packet":"<内层 JSON 转义字符串>","requestid":"<uuid>"}` | `{"protocol":"<名字>","packet":"<内层 JSON 字符串>"}`（`GatewayController.cs:277`、`:794`） | **缺 `requestid`** |
| 内层信封字段 | `Protocol / SessionKey{AccountServerId,MxToken} / ServerTimeTicks / ServerNotification / RequestId` | `Protocol / SessionKey / AccountId / ServerTimeTicks / ServerNotification`（`Packet.cs:14-56`） | **CN 多 `RequestId`；Shittim 多 `AccountId`** |
| 请求侧标识 | `Hash`（= `(protocol<<32)\|counter`，我上一轮已解）+ 外层 `requestid` | `Hash`（`Packet.cs:29`，**声明但从不读**）+ `ClientUpTime`/`Resendable`（同样不读） | 等价物存在 |
| 加密 | AES-256-CBC，密钥明文附在密文尾部 | `mx` 内可无加密（`keyLen=0`） | 代理两层都懂 |
| 内层序列化 | JSON（PascalCase 键） | JSON（PascalCase，`DefaultValueHandling.Ignore`，`GatewayController.cs:122-128`） | **同构** |

`[团队实测]` 证据（`work\ba\server\`）：
- `SCHEMA_V2_DESIGN.md:35`「5 个信封字段：`Protocol` / `SessionKey{AccountServerId,MxToken}` / `ServerTimeTicks` / `ServerNotification` / `RequestId`」
- `prototype\_scratch\probe_ticks.txt:14` 官方 `NetworkTime_Sync` 响应原文：
  ```json
  {"Protocol":3,"SessionKey":{"AccountServerId":10015354380,
   "MxToken":"Vji5A/Cy6X2enQZKeYgrjxAC8MoRDOCT2Tb1SW13PcZTq2cnyCPPdd81pGbzYBKA"},
   "ServerTimeTicks":639304002554622705,"ServerNotification":0,
   "RequestId":"d1d5579c-9c2b-44e6-a496-c66d4ccca10c",
   "ReceiveTick":639304002554622693,"EchoSendTick":639304002554622693}
  ```

**⇒ 三条硬结论：**

1. **量级可控**：内层转换 = "Shittim 的 DTO JSON + 补一个 `RequestId`"。**不是 flatbuffer、不需要重写 DTO。**
2. **CN 确实有 `SessionKey`，而且会回传**（上面 `probe_ticks.txt` 里 `MxToken` 是 64 字符 base64、`AccountServerId` 11 位）⇒ **可以走"服务端发什么、客户端回什么"的透传**，不必让代理硬编码会话。
   > 这条同时**推翻** `report\41:173-175`「`SessionKey` 全文 0 命中」——那是在 XOR 0x20 混淆被发现之前做的字符串搜索，不可信（lead 已通报该混淆）。
   > ⇒ 我在 `report\46` §1.3 / §4.3 基于它的两条结论**论据要换**：结论（代理必须能提供会话）仍成立，但理由是"Shittim 全程要 SessionKey 且 handler 逐个校验"，不是"客户端没有这个字段"。
3. **`RequestId` 是必补项**：官方 109/109 条响应满足 `outer.requestid == inner packet.RequestId`（`work\ba\server\deploy\DEPLOY_PLAN.md:69`、`patch_1017.py:36`）。Shittim **永远不发** `RequestId`（`Packet.cs:45-56` 无此字段）。
   ⇒ 若代理不回显，客户端很可能丢弃该响应（与"按钮 loading 不动、无弹窗、无崩溃"完全一致）。**这是本次改造的第一优先级。**

### 3.2 Shittim 有没有 CN / 多版本协议开关？

`[源码实测]` **没有。** 证据：
- `ServerConfig.cs`（84 行，`report\28` §4.2 已列全）无 region/CN/version-switch 项；
- 全文检索 `Region` 只命中 `ClientRegionLabelPatchService`（改标题界面文字）与 `ServerConfig.RegionDisplayText`（`report\28` §5.4 已核）；
- `GatewayController` 里没有任何 `if (region == …)`；
- 唯一"国服痕"是**协议级**的：`Protocol.Account_CheckYostar`(1009) 有 handler（`AccountHandler.cs:899-953`），注释 `:898` 明说「Yostar build 的对位物，Steam 客户端从不发它」。
- 文件树里带 Yostar/Inface 的只有 4 个文件，全是**PC 启动器**侧（`GTableInfaceController` / `ClientInfaceConfigPatchService`）。

⇒ **要支持 CN，只有两条路：改 Shittim，或在它前面加代理。**

### 3.3 SessionKey 怎么走通（决定成败的细节）

`[源码实测]` Shittim 的会话是**服务端随机 GUID**，存在内存 + `Config/sessions.json`，由 `GenerateSession()` 铸（`SessionKeyService.cs:77-112`），handler 用 `GetAuthenticatedUser()` 校验（`:147-164`，**必须 GUID 字符串逐字相等**，`:155-156`）。

而 CN 官方的 `MxToken` 是 64 字符 base64。两者形态不同，但**客户端只是不透明回传**（`probe_ticks.txt` 证明它会带回来）。

⇒ 三种接法，推荐第 2 种：

| 接法 | 做法 | 风险 |
|---|---|---|
| 1. 透传客户端发来的 `SessionKey` 给 Shittim | 直接转发 | **必然失败**：客户端回传的是"上一响应里的 MxToken"，即 Shittim 自己发的 GUID —— 其实**能对上**，前提是代理第一次就把 Shittim 的 SessionKey 原样交给客户端 ✅ |
| **2. 代理持有会话，逐请求注入** | 代理自己 `Account_CheckNexon` 拿 SessionKey（现有 bridge 已这么做），转发时覆盖 `SessionKey` | 最稳；多账号需按 `DevId` 分桶 |
| 3. 让 Shittim 认 CN 的 token | 改 `SessionKeyService` | 改上游，不考虑 |

> 建议：**先按 1 试（最省代码、语义最像官方）**，失败再退 2。判据：看 Shittim 日志里该请求是 `Success` 还是 `Rejected request with invalid session`（`GatewayController.cs:290`）。

---

## 4. 最小改造路径

### 4.1 四条候选的评估

| 路线 | 内容 | 工作量 | 一次跑通概率 | 风险 |
|---|---|---|---|---|
| **(c) 直接把 CN 客户端指向 Shittim** | 改 ApiUrl → Shittim | 0 | **0 %** | 路径不对（`/api/account/auth` vs `/api/gateway`）、信封不对、`RequestId` 缺失、metadata RSA-2048 不匹配（`report\30`）。**不可行** |
| **(a) Python 桥做信封翻译** | 现有 `cn_wire`/bridge：解 CN 信封 → 组 `{"Protocol":…}` → `POST /api/gateway`（`mx`）→ 拿 Shittim JSON → 补 `RequestId` → 用 CN 信封回 | **~250–400 行** | **高** | 桥依赖 Shittim 存活；错误需二次映射 |
| **(b) 在 Shittim 加 C# 中间件** | 写一个 catch-all controller，把 `/api/<任何>/<任何>` 按 CN 信封解码 → 转内部 dispatch → 编码回 | ~300–500 行 C# + 改路由 | 中 | 改上游（合并冲突）；C# 侧要重写 CN AES/尾密钥解析；`Microsoft.AspNetCore.Routing` catch-all 与现有 `[Route("api")]` 共存要小心 |
| (d) 其它 | 例如把 CN 协议映射成 Shittim 的 SDK/IAS 流 | — | 低 | 完全不同的语义 |

### 4.2 推荐路线（分三段，每段可独立验收）

**总原则：桥不做业务，只做"信封 + 会话 + RequestId"三件事，其余全部交给 Shittim。**

```
CN 客户端
  │ POST /api/<任意>/<任意>   multipart: protocol(base32)/encode/packet(AES, key 在尾部)
  ▼
① 解信封           cn_cipher.decode_packet()                     【已有，report\35 §八】
② 定协议名          base32 → name（b32md5 反查）                  【已有】
③ 会话             取/铸 SessionKey（MxToken + AccountServerId）    【改：按 DevId 分桶】
④ 组 mx            {"Protocol":name, "SessionKey":…, …参数}        【已有 build_mx】
⑤ 转发            POST http://127.0.0.1:5000/api/gateway  (multipart, 字段 mx)
⑥ 收 Shittim 响应   {"protocol":…,"packet":"<JSON>"}                【已有 unwrap】
⑦ ★ 补 RequestId   内层 packet.RequestId ← 本次请求的 requestid
⑧ ★ 回 CN 信封     {"protocol","packet","requestid"}（明文或 AES，见下）
```

**第 ⑦ 步是第一优先级**，理由见 §3.1：官方 109/109 条都是 `outer.requestid == inner.RequestId`。

**第 ⑧ 步的口径**（沿 `report\46` §1.4 的结论）：客户端 metadata 里没有 `EncryptResponse`/`EncodeResponse` 符号 ⇒ **响应可以明文**。但既然团队已实测过 `outer.requestid` 形态，建议**先明文**（与现状一致，单变量），跑通后再考虑加密封装。

**必须同时上的两条不变量**（否则必然静默失败）：
1. `outer.requestid == inner.packet.RequestId`（§3.1）；
2. `SessionKey` 必须是 Shittim 认识的（§3.3）。

### 4.3 为什么不是 (b)

(b) 的唯一优势是"客户端路径原生"，但：
- CN 的 AES 尾密钥逻辑要在 C# 里重写一遍（`[u32 len][gzip([iv16][ct][key32])]`），而 Python 侧**已经能跑**；
- Shittim 现有 `[Route("api")]` + `[HttpPost("gateway")]` 是两段精确路由，加一个 `api/{**rest}` catch-all 会与它抢匹配，需改优先级；
- 改上游 ⇒ 每次 `git pull` 都要重打。

⇒ **(a) 先上；(b) 作为"跑通之后再把桥下沉进 Shittim"的第二阶段**，(a) 的桥正好可以当 (b) 的行为参照（对照测试）。

### 4.4 ExcelDB：决定"像不像官方"的第二个变量

`[源码实测]` Shittim 的表全部来自 `ExcelTableService.GetTable<T>()`（`AccountService.cs:32,40,76`），表本体是 `Resources/Dumped/ExcelDB.db`。
`[源码实测 + DEADENDS D-51]` `UseCustomExcel=true` 会 `ResetDumped()` 删掉整个 `Resources/Dumped` 再拼 CDN URI 崩掉（`ResourceService.cs:151`）⇒ **不能开**。

⇒ 正确做法：**把 CN 客户端那份 `ExcelDB.db`（我们本地有：`work\ba\data\ExcelDB.db`，160,534,528 B，398 张表，明文 SQLite）直接放到 Shittim 的 `Resources/Dumped/ExcelDB.db`**，并设：
```
UseCustomExcel=false            # 否则会删资源
DownloadExcelTables=false
AutoUpdateResources=false
AutoCheckVersion=false / AutoUpdateVersion=false
```
这样建号时 `DefaultCharacterExcel` 读到的就是 **CN 的 13010/16003/13003/26000**，与客户端本地表一致 —— **角色 ID 对不上的问题从根上消失**。

---

## 5. 要警惕的坑（从源码看到的）

| # | 坑 | 证据 | 表现 / 对策 |
|---|---|---|---|
| **P1** | **`RequestId` 缺失** → 客户端不认响应 | Shittim `Packet.cs:45-56` 无此字段；官方 109/109 有（`DEPLOY_PLAN.md:69`） | loading 不动、无弹窗、无第二请求。**必须由代理补** |
| **P2** | **ExcelDB 版本漂移** | Shittim 默认 `ServerInfoUrl` 拉国际服 `439170_Live_*.json`（`report\28` §4.2）；`config/ba_version_cache.json` 是 `1.93.452511` | 角色/关卡 id 与 CN 3.0.2 不符 ⇒ 客户端找不到 excel 行 ⇒ 空白/卡住。**对策：用 CN 的 ExcelDB（§4.4）** |
| **P3** | **`Account_Auth.CurrentVersion` 口径**：`AuthCurrentVersion` 默认 `446690`（`ServerConfig.cs:6` 注释：官方对 1.90.443855 客户端也回 446690） | `AccountHandler.cs:121-122` | CN 客户端是否校验存疑（`[未确认]`）。CN 的 `Account_Auth` 请求里**没有 `Version` 字段**（`report\35:55` 11 键）⇒ 大概率只是展示用 |
| **P4** | **`ServerNotification` 语义**：Shittim 在**每个 in-session 响应**上 OR 上 `HasUnreadMail` 等位（`GatewayController.cs:265-266, 324-331`），且 4 个协议跳过 | 同上 | 若 CN DTO 没有对应位/枚举值不同 ⇒ 未知位可能被忽略（`DEADENDS D-46` 实测"注入未知字段完全没变化"）。**风险低**，但 `8`/`2048` 这类位要按 CN 枚举核对 |
| **P5** | **会话失配**：`GetAuthenticatedUser` 逐字比 GUID | `SessionKeyService.cs:147-164` | 任一请求 SessionKey 不对 ⇒ 该协议回 `Error`（不是 401）⇒ 客户端可能弹「无法处理的请求」。对策见 §3.3 |
| **P6** | **CN 特有协议缺失**：`Account_GetIdCardInformation` 之类**不在 Shittim 枚举**（`report\44` §5.2 已核） | — | 若真被调用，代理只能自造空响应。`[未确认]` 是否真会被调用（`report\41:223` 判实名走独立协议 + 本地 `SensitiveManager`） |
| **P7** | **协议号本身可能错位**：CN 与 Steam 若对同一号语义不同 ⇒ 全盘错 | `[未确认]`；但目前 `Account_Auth=1002`、`NetworkTime_Sync=3` 两个号在 CN 抓包里**与 Shittim 枚举一致**（`report\36`、`probe_ticks.txt`） | 建议把"号→名"当作待验证表，逐个跑 |
| **P8** | **`Queuing_*` 空 `EnterTicket` 扣住客户端** | `QueuingHandler.cs:106-109` 注释「empty EnterTicket is what holds the client on the queue popup」 | 若 CN 走队列，必须回非空票（`report\43` 已有完整规格） |
| **P9** | **`server_notice.json` 维护门** | `ServerNoticeService.cs:65` | 除 `Queuing_GetCryptoKeys` 外全 Error。默认关，但要确认 |
| **P10** | **明文 ExcelDB 字段加密开关** | `DefaultCharacterExcel.cs` 的 `UnPackTo` 里 `TableEncryptionService.UseEncryption` | 本地数据实测字段是明文 ⇒ 与 Shittim 默认（`UseEncryption=false`）一致 ✅（若换成加密表就会读出垃圾） |

---

## 6. 未确认（不要当结论用）

| 项 | 状态 |
|---|---|
| CN 客户端是否**强制**校验 `RequestId`（缺失即丢弃），还是仅用于日志 | **未确认**。仅知官方 109/109 都带；建议做一次 A/B（带/不带）即定 |
| CN 的 `MxToken`（64 字符 base64）是否被 Shittim 接受 | **未确认**，但按 §3.3 接法 1 可零成本验证 |
| `Account_Auth.CurrentVersion` 在 CN 上是否被校验 | **未确认** |
| Shittim 的 `DefaultCharacterExcel` 在本机 ExcelDB 上是否解析出与 §2.3 相同结果 | **已用本地 .bytes 手工验证表结构**；**未在运行中的 Shittim 上验证**（不碰服务器） |
| CN 3.0.2 是否真的会发 `Queuing_*` | **未确认**（lead 正在测） |
| `Controllers/SDK/*` 各控制器的精确路由前缀 | **未逐一核对**（只确认为非游戏协议） |
| Shittim 对"CN 多出来的 DTO 字段"是否容忍 | **推断容忍**（Newtonsoft 忽略未知成员，`DEADENDS D-46` 实测客户端也忽略未知字段），未在服务端验证 |

---

## 7. 落地清单（给实施者，按顺序）

| # | 动作 | 判据 |
|---|---|---|
| 0 | 确认 `server_notice.json` 不存在或 `gate_error=0` | Shittim 日志无 "Maintenance gate is ACTIVE" |
| 1 | 把 CN 的 `ExcelDB.db` 放到 `Resources/Dumped/`，关闭 `UseCustomExcel`/下载/更新 | 启动日志无 `Custom Excel is Enabled`，且建号后 DB 里有 4 个角色行 |
| 2 | 桥改为"每协议都转发 `/api/gateway`"，用 `cn_cipher.build_mx` | Shittim 日志出现 `POST /api/gateway` 且 `-> 200`，wire dump 有明文 |
| 3 | **补 `RequestId`**：内层 = 外层 `requestid` | 客户端出现第二个协议请求（或 `POST /log`） |
| 4 | 会话：先按"透传"试，失败改"代理注入" | Shittim 日志无 `Rejected request with invalid session` |
| 5 | 逐个补 `Queuing_*` / `Account_CheckYostar` 等登录族 | 能进大厅，且角色/任务/教程 ID 都非空 |

---

## 附：本次查阅的关键源码路径（main @ 5f3910e）

| 主题 | 路径 |
|---|---|
| 网关入口/信封 | `Shittim-Server/Controllers/Api/GatewayController.cs` |
| 协议注册 | `Shittim-Server/Core/ProtocolHandlerFactory.cs`、`Core/ProtocolHandlerRegistry.cs`、`Core/ProtocolHandlerExtensions.cs`、`Core/HandlerManager.cs` |
| 建号/种子 | `Shittim-Server/Services/AccountService.cs`（`AccountInitializationService`） |
| 会话 | `Shittim-Server/Services/SessionKeyService.cs` |
| 持久化 | `Shittim-Server/Extensions/DBServiceExtensions.cs`、`Schale/Data/SchaleDataContext.cs` |
| 维护门/通知位 | `Shittim-Server/Services/ServerNoticeService.cs`、`MailNotificationService.cs` |
| Excel 表桥 | `Schale/BlueArchive.fbs`、`Schale/FlatData/*.cs`（912 个）、`Shittim-Server/Services/ExcelTableService.cs` |
| 数据包基类 | `Schale/MX/NetworkProtocol/Packet.cs`、`ProtocolData.cs` |

---

## 6. Shittim 有没有"发东西"的正规通道（追加必答）

**结论先行：有，而且正是用户要的那种"走服务端自己的机理"——它就是 `Shittim-Server/Commands/` 里的 23 条 GM 命令。**
但**唯一真正能执行的是"控制台/游戏内"这条路**；HTTP 的 `/dev/api/command` 是**空壳（stub）**，别指望它。

### 6.1 两个 Electron 前端是什么

| 项目 | 是什么 | 证据 |
|---|---|---|
| `ShittimControlCenter/` | Electron 控制台：`main.js` / `preload.js` / `src/js/pages/*.js`，页面有 **accounts / inventory / mail / config / events / notices / mods / overview / health** | 文件树 `ShittimControlCenter/src/js/pages/` |
| `ShittimRaidConsole/` | 另一个 Electron 小工具（`main.js` / `preload.js` / `src/`），按命名是世界 Raid 控制台 | 文件树 `ShittimRaidConsole/`；**具体功能未逐一核对 `[未确认]`** |

它们连的是 Shittim 的 HTTP 面（`/dev/api`、`/admin`、`/gm/*`），**不是游戏协议面**。

### 6.2 命令系统：23 条 `[CommandHandler]`，反射装配

`[源码实测]` `Shittim-Server/Commands/` 共 **23 个文件**，全部继承 `Command`（`Commands/Command.cs:8-55`）：

| 命令（`[CommandHandler(name, hint, usage)]`） | 作用 | 源码 |
|---|---|---|
| **`!giveall`** | **解锁全部可玩角色** | `GiveAllCommand.cs:9`；执行 `:14`，回包 `:53` "Unlocked {count} characters!" |
| **`!max <all\|角色名>`** | **满级/满星/羁绊/技能**：`Lv90 + MaxStarGrade + Favor 100 + Skills 10/5/10/10 + PotentialStats maxed` | `MaxCommand.cs:9`；主逻辑 `:24`/`:28`；回包原文 `:118` |
| **`!currency <id\|name> <amount>`** | **改任意货币**，含 `Gem`（并对 `GemBonus` 同步） | `CurrencyCommand.cs:9`；`:65-67`；回包 `:81` |
| `!character <add\|show\|…> <id> [barebone\|basic\|ue30\|ue50\|max\|level\|star\|skill\|ps]` | 单角色添加/改属性 | `CharacterCommand.cs:9,20,45` |
| `!give` / `!giveequip` / `!giveallequip` | 发物品/装备 | `GiveCommand.cs` / `GiveEquipCommand.cs` / `GiveAllEquipCommand.cs` |
| `!unlockall` / `!unlockbattlepass` | 解锁内容/通行证 | `UnlockAllCommand.cs` / `UnlockBattlePassCommand.cs` |
| `!mail` | **通过邮件系统发附件**（最"官方"的奖励通道） | `MailCommand.cs` |
| `!item` / `!listitem` / `!checkitem` / `!clearinventory` / `!inventory` | 背包管理 | `ItemCommand.cs`（未读）/ `ListItemCommand.cs` / `CheckItemCommand.cs` / `ClearInventoryCommand.cs` / `InventoryCommand.cs` |
| `!accountdata` / `!setaccount` | 账号数据/切账号 | `AccountDataCommand.cs` / `SetAccountCommand.cs` |
| `!gacha` | 抽卡相关 | `GachaCommand.cs` |
| `!setraid` / `!setseason` / `!setting` / `!eleph` / `!help` | 杂项 | 各同名文件 |

**装配方式**（`[源码实测]`）：`Commands/Command.cs:104-126` `CommandFactory.LoadCommands()` 反射所有带 `[CommandHandler]` 的类，建立 `Dictionary<string, Type>`；`:128-143` `CreateCommand(name, connection, args)` 实例化并 `Validate()`（参数用 `[Argument(position, regex)]` 声明，见 `:57-77`）。

### 6.3 ★ 触发路径：只有两条真的能跑

| 通道 | 是否真能执行 | 证据 |
|---|---|---|
| **控制台（进程 stdin）** | ✅ **是** | `Services/Client/ConsoleCommand.cs:25-26`：`var command = CommandFactory.CreateCommand(commandName, connection, commandArgs); command?.Execute();`；入口 `GameServer.cs:215-225`：`new ConsoleClientConnection(..., id ?? 2)` → `Task.Run(() => ConsoleCommand.ConsoleCommandListener(consoleConnection))` |
| **游戏内聊天（`!` 前缀）** | `[未确认]` | 命令全部通过 `connection.SendChatMessage(...)` 回话（`IClientConnection.cs:16-17`），说明产出面是"聊天/控制台"；**但我没有在 handler 列表里找到把聊天消息路由到 `CommandFactory` 的 handler** ⇒ 是否支持"游戏里打 `!giveall`"，未确认 |
| **HTTP `POST /dev/api/command`** | ❌ **不能（stub）** | `Controllers/GM/CommandController.cs:8-21` 路由是 `[Route("/dev/api")] + [HttpPost][Route("command")]`；**但 `:38` 原文写死**：`commandOutput = $"Command system not yet fully implemented. Command received: {cmdName} with args: ..."` —— **它从头到尾没有调用 `CommandFactory`**，拿到的 `connection` 也从未被使用。⇒ 打这个端点只会回一句"还没实现" |
| **`ShittimControlCenter` 的账号/背包/邮件页** | `[未确认]` | 走的应是 `Controllers/GM/*Controller.cs`（Arena/Character/Command/Common/Raid/Settings）与 `AdminController`，**不是**命令系统；具体端点未逐个读 |

> ⚠ **给 lead 的结论**：**不要用 `/dev/api/command` 给用户发东西**，会得到一个"成功"的假象（返回 `ResponseStatus.Success` + 那句 stub 文案，`CommandController.cs:58`）。**要用控制台**。

### 6.4 用户那个存档，正确的生成方式（三步命令）

```
!giveall                    # 全部可玩角色解锁（GiveAllCommand.cs:9）
!max all                    # 全部 Lv90 / 满星 / Favor 100 / 技能 10-5-10-10（MaxCommand.cs:118）
!currency Gem 3000000       # 青辉石（CurrencyCommand.cs:65-67，Gem 与 GemBonus 同步）
```

三条都是**服务端自己的机理**：走 `Command.Execute()` → EF Core 改实体 → `SaveChanges` 落 SQLite；货币还走 `CurrencyDict`/`UpdateTimeDict` 双字典（`AccountCurrencyDB.cs:22-23`）。**抽卡能正常**是因为抽卡逻辑本身在 `GachaHandler` / `Core/GachaCommand.cs`，与货币同源。

> 控制台绑定的账号：`GameServer.cs:217-223` `new ConsoleClientConnection(..., id ?? 2)` ⇒ **默认作用于 `AccountServerId = 2`**（正好是我们现在那个账号，见 `report\36` §3）。若要多账号，用 `!setaccount` 或控制台启动参数 `id`。

### 6.5 如果都不够用：新账号的正确注入点

`[源码实测]` 若需要"新建账号时就带资源"，**不要在 handler 里塞，也不要写 SQL**，正确注入点是：

**`Shittim-Server/Services/AccountService.cs` 的 `AccountInitializationService.CreateAccount()` / `InitializeCompleteAccount()`（`:20` / `:393`）**——它是唯一的建号种子入口（`AccountHandler.cs:935`、`:987` 都调它）。改这里 = 改"新账号默认给什么"，且天然对所有建号路径生效。

**优先顺序**：① GM 命令（零改码，立即生效）→ ② 改 `DefaultParcelExcel`/`DefaultCharacterExcel` 数据（要重导 ExcelDB）→ ③ 改 `AccountService` 代码（最重，且与上游冲突）。

---

## 7. 数据模型细节（决定能不能安全写入）

### 7.1 持久化 / 迁移

| 项 | 结论 | 证据 |
|---|---|---|
| ORM | **EF Core**，`IDbContextFactory<SchaleDataContext>` | `Extensions/DBServiceExtensions.cs:13-24` |
| 数据库 | **SQLite**（默认）/ SQL Server | `DBServiceExtensions.cs:16-24`；`Schale/Data/SchaleDataContext.cs:414-416` `UseSqlite("Data Source=schale.sqlite3")`，`:97` `UseSqlServer`，`:411` 可配置 |
| `Migrations/` 目录 | **不存在**（仓库树里没有） | GitHub 文件树 1520 个 blob 中无 `Migrations/` |
| 建表 | `CanConnect()` → `EnsureCreated()`；有待迁移则 `Migrate()`；**实际靠 `SchemaReconciler.ReconcileAsync(context)` 从 EF 模型反推表/列并补齐** | `CLI/GameServer.cs:186-206` |
| 惰性加载 | `UseLazyLoadingProxies()` | `DBServiceExtensions.cs:17,22` |

⇒ **没有版本化迁移**。加字段靠"启动时 reconcile"，所以**手工加列也可以被接受**，但**新增实体属性后一定要重启让它 reconcile**。

### 7.2 复杂列：**JSON 字符串，不是 flatbuffer BLOB**

`[源码实测]` `SchaleDataContext.cs:420-458` —— 全项目唯一的列转换器：

```csharp
public static PropertyBuilder<T> HasJsonConversion<T>(this PropertyBuilder<T> propertyBuilder) where T : class?, new()
{
    var converter = new ValueConverter<T, string>(
        v => JsonSerializer.Serialize(v, _options),
        v => string.IsNullOrEmpty(v) ? new T() : JsonSerializer.Deserialize<T>(v, _options) ?? new T());   // :436-440
    ...
    propertyBuilder.HasConversion(converter);                    // :452
    propertyBuilder.Metadata.SetValueComparer(comparer);         // :454
}
```

- 序列化用 `System.Text.Json`，`DefaultIgnoreCondition = WhenWritingNull`（`:422-426`）。
- **空串 `''` 会被当成"空对象"**（`:438` 注释：老行是 `''` 不是 JSON）⇒ 手工写 `''` 是安全的，写 `NULL` 反而不行（列 NOT NULL）。
- 比较器按"序列化后字符串相等"判等（`:446`）⇒ **纯手工改 JSON 时键顺序变了也算"变了"，会触发 UPDATE，无害**。

`[源码实测]` 具体到问题里点名的两列：

| 列 | 类型 | 存成 | 源码 |
|---|---|---|---|
| `AccountCurrencyDB.CurrencyDict` | `Dictionary<CurrencyTypes, long>` | **JSON 文本**（TEXT 列） | `Schale/Data/GameModel/UserModel/AccountCurrencyDB.cs:22` |
| `AccountCurrencyDB.UpdateTimeDict` | `Dictionary<CurrencyTypes, DateTime>` | **JSON 文本** | `:23` |
| `CafeDB.FurnitureDBs` | 集合类型 | **JSON 文本**（同一 `HasJsonConversion`） | `SchaleDataContext.cs:431-457` 唯一转换器 |
| `CharacterDB.EquipmentServerIds` / `PotentialStats` / `EquipmentSlotAndDBIds` | `List<long>` / `Dict<int,int>` / `Dict<int,long>` | **JSON 文本** | `CharacterDB.cs:39-41` |

⚠ **字典的键是 enum**：`System.Text.Json` 把 enum 键写成**数字字符串**（如 `{"2":20000}`），不是名字。手工写 JSON 时必须用数字键，否则 `Deserialize` 失败（`CurrencyTypes` 见 `Schale/MX/.../ProtocolData.cs` 或 `FlatData/CurrencyTypes.cs`）。

### 7.3 `Characters` 表一条记录的必填/关键字段

`[源码实测]` `Schale/Data/GameModel/UserModel/CharacterDB.cs:9-53`：

| 字段 | 类型 | 说明 | 行 |
|---|---|---|---|
| `ServerId` | `long` | **主键**（`[Key]`，自增） | `:24-25` |
| `AccountServerId` | `long` | 所属账号（外键语义，`[JsonIgnore]`） | `:17-18` |
| **`UniqueId`** | `long` | **= `CharacterExcelT.Id`**（不是 ServerId） | `:27`；赋值处 `AccountService.cs:48,53` |
| `StarGrade` | int（默认 1） | 星级 | `:28` |
| `Level` | int（默认 1） | 等级（满级 90） | `:29` |
| `Exp` | long | 经验 | `:30` |
| `FavorRank` | int（默认 1） | 羁绊等级 | `:31` |
| `FavorExp` | long | 羁绊经验 | `:32` |
| `PublicSkillLevel` / `ExSkillLevel` / `PassiveSkillLevel` / `ExtraPassiveSkillLevel` / `LeaderSkillLevel` | int（默认 1） | 五个技能等级 | `:33-37` |
| `IsFavorite` | bool | 代表角色标记 | `:38` |
| `EquipmentServerIds` | `List<long>`（默认 3 个 0） | 装备槽 | `:39` |
| `PotentialStats` | `Dict<int,int>`（默认 1/2/3 → 0） | 潜能 | `:40` |
| `EquipmentSlotAndDBIds` | `Dict<int,long>` | 装备槽→装备 id | `:41` |

**`UniqueId` 对应哪张表哪个字段**：`CharacterExcel` 表的 **`Id`** 列（`AccountService.cs:41-48`：`characterExcel.FirstOrDefault(y => y.Id == x.CharacterId)`，把 `DefaultCharacterExcel.CharacterId` 映射到 `CharacterExcel.Id`）。我们本地实测的 4 个 id（§2.3）就是这套 id 空间。

### 7.4 ★ 派生/顺序字段：裸 SQL 一定会踩的三个

| # | 坑 | 源码 | 后果 |
|---|---|---|---|
| D1 | **`Characters.ServerId` 必须先生成，后面的行才能引用它** | `AccountService.cs:77-83`：Echelon 的 `LeaderServerId`/`MainSlotServerIds`/`SupportSlotServerIds` 全部用 `character.ServerId`（**不是 UniqueId**） | 裸 SQL 若先写 Echelon 会拿到 0 或错 id → 编队空/进战斗崩 |
| D2 | **`AccountDBServer.RepresentCharacterServerId` 也是 `ServerId`** | `AccountService.cs:261-265` `newCharacters.First(...).ServerId` | 同上；写错 = 大厅/记忆大厅取不到角色（正是用户当前症状） |
| D3 | **`AccountCurrencyDB.AccountLevel` 不是从 `AccountDB.Level` 读出来的常量** | `AccountCurrencyDB.cs:20` 字段 + `:56` `UpdateAccountLevel(long level)` 方法 | 只改 `AccountDB.Level` 不改这里 → 账号等级奖励/显示不一致 |
| D4 | 货币 `Gem` 与 `GemBonus` 成对 | `CurrencyCommand.cs:65-67` | 只写 `Gem` 不写 `GemBonus` → 客户端显示/消耗异常（这是 `!currency` 自带的行为，别用 SQL 绕） |
| D5 | 角色 `Exp` 与 `Level` 的解耦 | `MaxCommand.cs` 直接 `Level=90`（`:118` 文案），不重算 Exp | 说明"等级"是权威值、Exp 只是展示 ⇒ 手工写时**以 Level 为准** |

**⇒ 结论：能用 `!giveall` / `!max` / `!currency` 就不要写 SQL。** 只有当"要批量改多个账号"或"要构造历史数据"时才考虑 SQL，且必须按 D1→D2 的顺序（先 Characters，再取 id 回填）。

---

## 8. Session 到底怎么拿（当前唯一硬阻塞）

### 8.1 线上那条报错的逐字解码

```
[ERR] System.UnauthorizedAccessException: Session key required
[WRN] Rejected request with invalid session: Session key required
[INF] Error Response: {"Protocol":-1,"ErrorCode":3,...}
```

| 环节 | 源码 | 含义 |
|---|---|---|
| 抛错点 | `AccountHandler.cs:113-114`：`if (request.SessionKey == null) throw new UnauthorizedAccessException("Session key required");` | **`SessionKey` 整个是 `null`**（不是"值不对"） |
| 捕获点 | `GatewayController.cs:287-295`：`catch (UnauthorizedAccessException)` → `CreateProtocolErrorResponse(ex.Message, WebAPIErrorCode.InvalidSession, …)` | 回 **HTTP 200** + `Error` 信封 |
| `ErrorCode: 3` | `ProtocolData.cs:654` `InvalidSession = 3` | 与日志一致 |

⇒ **诊断结论：那次 `Account_Auth` 请求里根本没有 `SessionKey` 字段。** 不是 token 过期、不是 GUID 不匹配（那两种会抛 `"Session expired or invalid"` / `"Session token mismatch"`，见 `SessionKeyService.cs:152-156`）。

### 8.2 `Auth` 里 session 校验的完整逻辑

`[源码实测]` `AccountHandler.cs:107-157`：

```csharp
[ProtocolHandler(Protocol.Account_Auth)]
public async Task<AccountAuthResponse> Auth(SchaleDataContext db, AccountAuthRequest request, AccountAuthResponse response)
{
    if (request.SessionKey == null)                                   // :113  ← 本次报错在这里
        throw new UnauthorizedAccessException("Session key required"); // :114
    var account = await _sessionService.GetAuthenticatedUser(db, request.SessionKey);  // :116
    await EnsureOpenConditionScenariosCleared(db, account);            // :119
    …
}
```

`GetAuthenticatedUser`（`SessionKeyService.cs:147-164`）三连检：

```csharp
if (sessionKey == null) throw new UnauthorizedAccessException("Session key is required");        // :149-150
if (!_activeSessions.TryGetValue(sessionKey.AccountServerId, out var session))
    throw new UnauthorizedAccessException("Session expired or invalid");                         // :152-153
if (!session.Token.ToString().Equals(sessionKey.MxToken, StringComparison.OrdinalIgnoreCase))
    throw new UnauthorizedAccessException("Session token mismatch");                             // :155-156
```

⇒ **SessionKey 必须同时满足：① 非 null；② `AccountServerId` 在 `_activeSessions` 里；③ `MxToken` 与登记的那张 GUID 逐字相等。**

### 8.3 SessionKey 从哪来？——**只有 5 个协议能铸**

`[源码实测]` 唯一的铸造函数是 `SessionKeyService.GenerateSession(publisherAccountId)`（`:77-112`：查 `Accounts` 表 → 生成 `Guid.NewGuid()` → 写入 `_activeSessions` → **立即持久化**）。

它的调用点（全部在 `AccountHandler.cs`）：

| 协议 | 行 | 是否**要求**先有会话 |
|---|---|---|
| **`Account_CheckNexon`(1014)** | `:96` | ❌ **不要求**（handler 开头不校验 SessionKey） |
| **`Account_CheckYostar`(1009)** | `:943` | ❌ **不要求** |
| `Account_Create`(1000) | `:247` | ✅ 要求（`:240` 先 `GetAuthenticatedUser`） |
| `Account_Auth2`(1012) | `:813-822` | ✅ 要求 |
| `Account_CheckNexon` 已有号时 | `:96`（同上） | ❌ |

⇒ ★ **`Account_Auth`(1002) 永远不可能作为第一个协议成功。** 首登必须先跑 **`Account_CheckNexon`(1014)** 或 **`Account_CheckYostar`(1009)**，拿回 `SessionKey{AccountServerId, MxToken}`，再把它原样放进后续每个请求。

**这正是我们桥接现在必须做的事**：`cn_bridge_v5.py:138-158` 的 `ensure_session()` 就是替客户端跑 `Account_CheckNexon` 并把 `SessionKey` 注入后续请求。**线上报错说明这条注入没生效**（大概率那次请求走的是不带注入的路径，或 `ensure_session` 返回了 `None` 后被忽略）。

> 相关既有结论：`report\28` §3.3 已核实 `CheckYostar`/`CheckNexon` 都在免会话白名单里；`report\46` §3.3 给了三种会话接法。**本轮新增的是：`ValidateRequest` 是死代码（见 8.5），所以白名单实际不起作用，唯一的门是每个 handler 自己的校验。**

### 8.4 `Config/sessions.json` 与 `gateway_aes_sessions.json`

`[源码实测]` **sessions.json**

- 路径：`Path.Combine(AppContext.BaseDirectory, "Config", "sessions.json")`（`SessionKeyService.cs:32-33`）
- 结构：`List<ActiveSession>`（`:49-52` 读、`:67-68` 写），元素是

```csharp
private class ActiveSession            // SessionKeyService.cs:190-196
{
    public required long UserId { get; init; }      // = 账号 ServerId
    public required Guid Token { get; init; }       // = MxToken
    public required DateTime CreatedAt { get; init; }
    public DateTime LastActivity { get; set; }
}
```
- 序列化用 `System.Text.Json` 默认（**PascalCase**），⇒ 150 B 的文件内容形如：
  `[{"UserId":2,"Token":"0404e715-ec34-4808-b1b1-580aefafc3af","CreatedAt":"2026-11-14T02:51:54Z","LastActivity":"..."}]`
  （我们实测过的那张 `MxToken` 正是这个 GUID，见 `report\36` §3）
- 谁写：构造时 `LoadPersistedSessions()`（`:36-41`，静默失败）；每次 `GenerateSession`/`RevokeSession`/`PurgeExpiredSessions` 后 `PersistSessions()`（`:60-75`，写失败只 warning）
- **为什么必须有它**：`:30-31` 注释——纯内存时重启会让客户端的 `MxToken` 失效，表现为 "Abnormal client" / "A request that cannot be processed"

`[源码实测]` **gateway_aes_sessions.json**

- 路径：`Path.Combine(Config.ConfigDirectory, "gateway_aes_sessions.json")`（`GatewaySessionCrypto.cs:27`）
- 结构：`List<PersistedGatewaySession>`，元素 `(Key: base64, Iv: base64, LastUsedTicks: long)`（`:313`；写 `:321-326`，读 `:341-360`）
- 用途：**记住客户端握手时用的 AES key/IV**，用于重启后继续解释客户端在会话加密模式下发来的包（`:24-25` 注释：丢了会卡 "Unpacking game resources"）
- 限额：最多 32 条、30 分钟 TTL（`:20-21`）
- ⇒ 103 B ≈ 一条记录（两个 16/32 字节 base64 + ticks）

**⇒ 对方案的含义：重启服务不会丢会话（已有持久化）；但如果 `sessions.json` 被删/账号重建，客户端手里那张 GUID 立刻失效 ⇒ 客户端必须重新 `CheckNexon`。**

### 8.5 ★ `BypassAuthentication` 到底绕过什么？——**什么也没绕过（死代码）**

`[源码实测]` 这个配置项只在一处被读：`SessionKeyService.cs:122-133`

```csharp
public bool ValidateRequest(RequestPacket request)
{
    if (_publicProtocols.Contains(request.Protocol)) return true;         // :116-117
    if (request.SessionKey == null) return false;                         // :119-120
    if (Config.Instance.ServerConfiguration.BypassAuthentication)         // :122  ← 唯一读点
    { … _activeSessions.TryAdd(...); return true; }                       // :124-132
    …
}
```

**而 `ValidateRequest` 在整份 main 里没有任何调用者**（本地快照与刚拉的 `GatewayController.cs` / `HandlerManager.cs` / `ProtocolHandlerRegistry.cs` 全部确认；`grep 'ValidateRequest'` 只命中 `SessionKeyService.cs:114` 与 `ISessionKeyService.cs:10` 的定义）。

⇒ **`BypassAuthentication: true` 在当前 main 上是无效开关**：它换不来"首登免 session"。同理 `_publicProtocols` 白名单也不起作用（handler 自己的 `GetAuthenticatedUser` 才是唯一的门）。

> 这一条也修正了 `report\28` §3.5 的隐含印象（"白名单让它们能作为登录第一枪"）——**真正让 1014/1009 能当第一枪的是它们 handler 内部不校验 SessionKey**，不是白名单。

### 8.6 有没有"开发/单机模式"让首登免 session？——**没有；但有两个替代**

| 手段 | 效果 | 证据 |
|---|---|---|
| `BypassAuthentication: true` | ❌ **无效**（死代码） | §8.5 |
| `SelectedAccountId` | ✅ 有用但不是免会话：`GenerateSession` 里优先选这个账号（任何身份都登进同一个号） | `SessionKeyService.cs:84-87` |
| **先跑 1014/1009** | ✅ **唯一正解** | §8.3 |
| 手写 `sessions.json` | ⚠ 技术上可行（格式见 8.4），但 `_activeSessions` 只在构造时加载 ⇒ **必须重启进程**才生效；属于"绕"，不建议 | `SessionKeyService.cs:36-41` |

**⇒ 给 lead 的处置建议（按成本排序）**

1. **先确认那次 `Account_Auth` 的请求体里有没有 `SessionKey`**——按 §8.1 的结论，报错是"字段缺失"而不是"值错"。查桥接日志里 `synth_auth` / `session_source` 两个字段（`cn_bridge_v5.py:135-137, 262-263`）。
2. 若缺：把注入补上（`{"Protocol":"Account_Auth","SessionKey":{...}}`），最小改动。
3. 若 `ensure_session()` 返回 `None`：往上查 `Account_CheckNexon` 的响应——它需要 `EnterTicket`（`base64("uid/token")`），而我们 SDK 的 uid/token 是现成的（`report\28` §6.4）。
4. **不要**为了绕这一步去开 `BypassAuthentication`（无效），也不要手改 `sessions.json`（要重启且脆弱）。

---

## 9. 多玩家与身份映射（追加必答）

> 本节回答"A/B/C/D"四问。**结论先说**：**Shittim 侧本来就是多账号架构，一行都不用改**；现在的串号问题 100% 在桥里。

### 9.0 一页结论

| 问 | 答 |
|---|---|
| 每个玩家怎么变成 Shittim 的账号？ | 由 **`EnterTicket` 里的 `publisherId`** 决定，它落到 `UserAccounts.NpSN`（`AccountHandler.cs:65-68`）。**这个 id 由我们提供，Shittim 不校验格式以外的任何东西。** |
| 没见过的新 ticket？ | **自动建号**（`AccountHandler.cs:68-89` / `:915-936`），没有任何准入检查。 |
| 多账号并发支持吗？ | **支持**：会话字典以 `Accounts.ServerId` 为键（`SessionKeyService.cs:14,96-104`），持久化是 `List<ActiveSession>`。 |
| 有没有隐藏单例会串号？ | **有一个真的**：`GatewaySessionCryptoBuilder` 的**全局 AES 密钥候选表**（跨账号扫全表）。其余单例/静态都是无账号状态的。 |
| `SessionKey.AccountServerId` 是 `Accounts.ServerId` 吗？ | **是**（`SessionKeyService.cs:96-111`）。两个玩家的值不同（自增主键）。 |
| 同账号多端？ | **后登录踢前一个**（`AddOrUpdate` 覆盖 token，`:104`）⇒ 前一端下一请求即 `Session token mismatch`。 |
| CN 业务协议字段对得上吗？ | **对得上**：Newtonsoft 默认忽略未知字段、缺失字段落默认值（`GatewayController.cs:215`）。**没有任何版本校验会挡 CN 3.0.2**（全项目 `ClientVersion` 只出现 4 处，且算完就丢弃）。真正的风险是"协议号语义"，不是字段名。 |

### 9.1 A. `EnterTicket` 是怎么被解析成账号的

#### ① 格式约定：`base64( UTF8( "{publisherId}/{token}" ) )`，且第一段必须能 `long.Parse`

`[源码实测]` 两条登录链**同构**：

```csharp
// AccountHandler.cs:58-63   CheckNexon(1014)
var ticketBytes   = Convert.FromBase64String(request.EnterTicket);
var ticketString  = Encoding.UTF8.GetString(ticketBytes);
var parts         = ticketString.Split('/');
var publisherId   = long.Parse(parts[0]);     // ★ 必须纯数字
var token         = parts[1];                 // ★ 只取第一段，token 里不能有 '/'

// AccountHandler.cs:905-910  CheckYostar(1009) —— 逐字相同
```

**这个格式是谁定的？——Shittim 自己两头都按它办，不是我们发明的：**

| 方向 | 位置 | 代码 |
|---|---|---|
| **铸票**（`Queuing_GetTicket`） | `QueuingHandler.cs:61-62` | `Encoding.UTF8.GetBytes($"{request.NpSN}/{request.NpToken}")` → base64 |
| **铸票**（`Queuing_GetAuthTicket`，国服线） | `QueuingHandler.cs:84, 93` | `Encoding.UTF8.GetBytes($"{request.YostarUID}/{request.YostarToken}")` → base64 |
| **铸票**（`ProcessWaitingQueue` 兜底） | `QueuingHandler.cs:107-109` | 同上，`NpSN != 0` 时 |
| **解析** | `AccountHandler.cs:58-63` / `:905-910` | 上引 |

⇒ **桥塞 `base64("UID/TOKEN")` 是完全正确的**，与 Shittim 自己的铸票逻辑逐字节一致。唯一约束：**`publisherId` 必须是十进制数字；`token` 不能含 `/`**。

#### ② 查哪张表哪一列：`UserAccounts.NpSN`

`[源码实测]` `AccountHandler.cs:65-68`（CheckNexon）/ `:912-913`（CheckYostar）：

```csharp
var user = await db.UserAccounts.FirstOrDefaultAsync(u => u.NpSN == publisherId);
```

| 列 | 语义 | 证据 |
|---|---|---|
| `UserAccounts.NpSN` | **= `publisherId`（匹配键）** | `:65-68`；模型 `Schale/Data/Models/UserAccount.cs`（`report\28` §4.4：`Uid` / `NpSN` / `NpToken`） |
| `UserAccounts.NpToken` | **只在不等时覆盖写，不参与匹配** | `:90-94` / `:937-941` |
| `UserAccounts.Uid` | 建号后回填为 `Accounts.ServerId` | `:86` / `:933` |
| `Accounts.PublisherAccountId` | **= `publisherId`**，会话查找用的就是它 | 建号 `:78`/`:925`；查询 `SessionKeyService.cs:81-82` |

> ⚠ **关键设计含义：换 token 不会换号。** 同一个 `publisherId` 带不同 token 登录，只更新 `NpToken`，仍进同一个 `Accounts` 行。
> ⇒ **我们的映射表必须以 `publisherId` 为唯一键**，token 只能当附属信息。

#### ③ 从未见过的 ticket：**自动建号**（无准入检查）

`[源码实测]` `AccountHandler.cs:68-89`（CheckYostar 在 `:915-936`，逻辑相同）：

```csharp
if (user == null)                                     // :68   ← 触发条件
{
    var newUser = new UserAccount { Uid = -1, NpSN = publisherId, NpToken = token };
    db.UserAccounts.Add(newUser);                     // :70-76
    var newAccount = new AccountDBServer(publisherId);
    db.Accounts.Add(newAccount);                      // :78
    await db.SaveChangesAsync();                      // :81   ← 先落盘拿自增 ServerId
    user = await db.UserAccounts.FirstAsync(u => u.NpSN == publisherId);
    var account = await db.Accounts.FirstAsync(a => a.PublisherAccountId == publisherId);
    user.Uid = account.ServerId;                      // :86   ← 回填
    await AccountInitializationService.InitializeCompleteAccount(db, account);   // :87
    await db.SaveChangesAsync();
}
```

⇒ **只要 `publisherId` 是没见过的新数字，Shittim 就自动开一个新号并跑完整初始化**。这就是"多玩家"能成立的根本原因：**不需要预先建号，只需要给每个玩家一个不同的数字 id**。

### 9.2 B. 多账号 / 并发

#### ① `sessions.json` 是 `List<ActiveSession>` ⇒ 多账号**天然支持**

`[源码实测]` `SessionKeyService.cs`：

| 元素 | 位置 | 说明 |
|---|---|---|
| 内存表 | `:14` `ConcurrentDictionary<long, ActiveSession> _activeSessions` | **键 = `Accounts.ServerId`** ⇒ 按账号隔离 |
| 持久化 | `:32-33` `Config/sessions.json`；`:49-52` 读、`:67-68` 写 | `List<ActiveSession>`，**结构性支持多个账号** |
| 元素 | `:190-196` `{ UserId(long), Token(Guid), CreatedAt, LastActivity }` | 一个账号一条 |
| 写入时机 | `:104-105`（GenerateSession）、`:168`（Revoke）、`:183` | 每次变更全量落盘 |

#### ② 单例 / 静态扫描（回答"有没有隐藏单例导致串号"）

`[源码实测]` 全量扫了 DI 注册（`GameServer.cs:92,114-117`）与两个服务的字段：

| 对象 | 生命周期 | 内部状态 | 会串号吗 |
|---|---|---|---|
| `SessionKeyService` | **Singleton**（`GameServer.cs:92` → `SessionKeyService.cs:203`） | `_activeSessions`（按账号键的并发字典）、`_dbFactory`；静态只有 `_publicProtocols`(只读)、`PersistPath`、`_persistLock`(锁) | **不会**（按键隔离） |
| `HandlerManager` | Singleton（`GameServer.cs:115`） | 只读方法注册表 | 不会 |
| `CafeService` / `CustomCharacterService` / `ModCatalogService` | Singleton（`:114,116,117`） | 无账号状态（未逐一读，`[未确认]`） | 不会（推断） |
| `MailNotificationService` | **static class** | `ConcurrentDictionary<long,byte>`，**键 = accountServerId**（`:11-18`） | **不会** |
| `AccountInitializationService` | **static class** | 仅 2 个 static 依赖 `_excelService` / `_parcelHandler`（`AccountService.cs:384-385`），启动时 `Initialize()` 写一次 | 不会 |
| **`GatewaySessionCryptoBuilder`** | **static class** | `static ConcurrentDictionary AesSessions`（`GatewaySessionCrypto.cs:20-22`），**按 AES key/iv 哈希为键，不含账号** | ⚠ **会跨账号**（见下） |

**⚠ 唯一真实的跨账号结构**：`GatewaySessionCryptoBuilder.GetAesCandidates()` 返回 **所有** 存过的密钥（`GatewaySessionCrypto.cs:158-168`），而解密失败时会**逐个尝试全部候选**（`GatewayController.cs:555-578`）。

后果（都不会读到别人的数据，但都会互相干扰）：
1. `TouchAes()` 会刷新**别人**那条 `LastUsedUtc`（`:170-173`）⇒ 该过期的不过期；
2. 上限 32 条（`:20`）⇒ 玩家多了互相挤占，早期会话被挤掉后可能出现"重启后解不开"；
3. 每包多尝试 N 次，N 随玩家数增长。

**⇒ 对我们：桥始终发 `keyLen=0 / ivLen=0`（明文分支），这张表**永远不会被写入**（`:175-179` `RememberAes` 只在握手时被动调用；我们的造包器不握手），风险直接归零。**
（唯一例外：若让桥去转发 `Queuing_GetCryptoKeys`(50001)，就会写表——多玩家前要先把这条排除或按账号分表。）

#### ③ `SessionKey.AccountServerId` = `Accounts.ServerId`，两个玩家一定不同

`[源码实测]` `SessionKeyService.cs:77-111`：

```csharp
var account = await db.Accounts.FirstOrDefaultAsync(a => a.PublisherAccountId == publisherAccountId);  // :81-82
var selectedId = Config.Instance.ServerConfiguration.SelectedAccountId;                                 // :85
if (selectedId > 0) account = await db.Accounts.FirstOrDefaultAsync(a => a.ServerId == selectedId) ?? account;  // :86-87
var session = new ActiveSession { UserId = account.ServerId, Token = tokenGuid, … };                    // :96-102
_activeSessions.AddOrUpdate(account.ServerId, session, (_, _) => session);                              // :104
return new SessionKey { AccountServerId = account.ServerId, MxToken = tokenGuid.ToString() };           // :107-111
```

- 查找键是 **`PublisherAccountId`**（`:81-82`），返回的是 **`ServerId`**（`:107-111`）。
- `Accounts.ServerId` 是自增主键 ⇒ **不同玩家必然不同** ✅
- ⚠ **`SelectedAccountId > 0` 会把所有人强行映射到同一个号**（`:85-87`）⇒ 多玩家必须保持 `SelectedAccountId = 0`（`report\28` §4.2 已列该配置）。

#### ④ 同账号多端：**踢前一个**

`[源码实测]` `:104` `AddOrUpdate(account.ServerId, session, (_, _) => session)` —— 后登录直接**覆盖**该账号的 `ActiveSession`。
于是前一个客户端手里的 `MxToken` 与内存里的新 GUID 不等 ⇒ `GetAuthenticatedUser` 抛 `"Session token mismatch"`（`:155-156`）⇒ 网关回 `Error`/`ErrorCode=3`（`GatewayController.cs:287-295`）。

**⇒ 行为是"后者胜、前者掉线"，不是共存。** 对"多玩家"无影响；对"同一玩家两台设备"会互踢（官方行为如何 `[未确认]`，但 Shittim 就是这样）。

### 9.3 C. 建号与初始数据

#### ① 是不是 `AccountHandler.cs:935` 调的那个？——**是，且只有它**

`[源码实测]` 调用链：

```
AccountHandler.CheckNexon  (:52-106，调用点 :87)
AccountHandler.CheckYostar (:899-953，调用点 :934)
        └─> AccountInitializationService.InitializeCompleteAccount(db, account)   // AccountService.cs:393-399
                └─> AccountService.CreateAccount(context, account, _excelService, _parcelHandler)   // :398
                        └─> 逐表种入（下表）
```

先决条件（`[源码实测]`）：`AccountInitializationService.Initialize(excelService, parcelHandler)` 必须在启动时调用过（`AccountService.cs:387-391`；在 `GameServer.cs:205-206`），否则 `:395-396` 抛 `"AccountInitializationService not initialized"`。

**触发条件**（两个，缺一不可）：
1. `UserAccounts` 里查不到该 `publisherId`（`AccountHandler.cs:68` / `:915`）；
2. **不限于** `user.NpToken` 变化 —— token 变了只更新 token，**不重种**（`:90-94` / `:937-941`）。

#### ② 新建账号时种了哪些表（逐个 `Add` 行号）

`[源码实测]` `Shittim-Server/Services/AccountService.cs`：

| # | 表（DbSet） | 行 | 内容 |
|---|---|---|---|
| 1 | `Currencies` | `:29` | 货币行（`AccountCurrencyDBServer`） |
| 2 | （通过 `ParcelHandler`） | `:32-38` | `DefaultParcelExcel` 里的默认资源 |
| 3 | `Characters` | `:73` | `DefaultCharacterExcel` 的 4 个角色（§2.3） |
| 4 | `Echelons` | `:99` | 1 支编队（`DefaultEchelonExcel`） |
| 5 | `EchelonPresets` | `:120, :152` | 4 组 × 5 个预设 |
| 6 | `EchelonPresetGroups` | `:130, :162` | 4 个预设组 |
| 7 | `Cafes` | `:166-167` | 咖啡厅 1、2 |
| 8 | `Furnitures` | `:205` | 初始家具 |
| 9 | `AcademyLocations` / `Academies` | `:257-258` | 课程表 |
| 10 | `AccountAttachments` | `:275` | 附件/头像框 |
| 11 | `StickerBooks` | `:284` | 贴纸 |
| 12 | `EventContentPermanents` | `:298` | 常驻活动 |
| 13 | `Mails` | `:323` | 欢迎邮件 |
| 14 | `CampaignStageHistories` | `:375` | 已通关主线（自动解锁功能） |
| — | `Accounts` / `UserAccounts` | **不在这里**，由 handler 建（`AccountHandler.cs:70-81` / `:917-928`） | — |
| — | **`AccountTutorials`** | **不在这里**（见 9.4） | — |

每行都带 `AccountServerId = account.ServerId` ⇒ **天然按账号隔离**（构造处如 `:52, :90, :109, :124`）。

### 9.4 教程状态写在哪：**`Account_SetTutorial`(1006)，不是 1005，也不是 Auth**

`[源码实测]`

| 协议 | 行 | 行为 |
|---|---|---|
| `Account_GetTutorial`(1005) | `AccountHandler.cs:656-670` | **只读**：`db.AccountTutorials.FirstOrDefault(...)`；**没有行就回 `Enumerable.Range(1, 27)`**（即 1..27 全未完成） |
| `Account_SetTutorial`(1006) | `:672-698` | **写入**：不存在就 `new AccountTutorial{ AccountServerId, TutorialIds }`，存在就 `tutorial.TutorialIds = request.TutorialIds.ToList()` |
| `Account_Auth`(1002) | `:107-157` | **完全不碰 `AccountTutorials`**（全文无该表引用） |

⇒ **教程进度 100% 由客户端在 1006 上报后落盘**。代理/桥**绝不要**在 Auth 里伪造教程状态；重启后"教程重来"的唯一原因就是 `AccountTutorials` 没写进去。

### 9.5 D. CN 客户端能不能走通全部业务协议

#### ① 字段名：**对得上，而且容错**

`[源码实测]` `GatewayController.cs:215`：

```csharp
var payload = (RequestPacket)JsonConvert.DeserializeObject(payloadStr, requestType)!;
```

Newtonsoft 默认 `MissingMemberHandling.Ignore` ⇒ **客户端多发的字段被忽略、少发的字段落默认值**，**不会因为字段名多寡报错**。

**例子（问题里点名的 `Item_List`）**：`[源码实测]` 请求 DTO **是空类** —— 没有任何字段可言错：

```csharp
// Schale/MX/NetworkProtocol/NetworkProtocol.cs:4465-4468
public class ItemListRequest : RequestPacket
{
    public override Protocol Protocol { get => Protocol.Item_List; }
}
// :4470-4475 响应
public class ItemListResponse : ResponsePacket
{
    public override Protocol Protocol { get => Protocol.Item_List; }
    public List<ItemDB>? ItemDBs { get; set; }
    public List<ItemDB>? ExpiryItemDBs { get; set; }
}
```

⇒ **CN 的 `Item_List` 请求体是什么都无所谓**（哪怕带一堆字段），Shittim 只认 `Protocol`。
有字段的协议才会真读：如 `Item_Sell{ TargetServerIds }`（`:4477-4481`）、`Account_Nickname{ Nickname }`（`:150-154`）—— **这类才需要逐个核对字段名是否一致**。

#### ② 版本/协议号校验：**没有任何一处会挡住 CN 3.0.2**

`[源码实测]` 全项目 `ClientVersion` 只有 4 处：

| 位置 | 用途 |
|---|---|
| `QueuingHandler.cs:48-58` | 解析后**算了个 `majorMinorMismatch` 然后 `_ = majorMinorMismatch;` 丢弃**（`:56-58`，注释明写 "Do not hard-fail queue bootstrap when client and server versions differ"） |
| `NetworkProtocol.cs:5802, 5846, 5867` | 三个队列请求 DTO 的字段声明 |

其余：
- `Account_Auth` 的 `CurrentVersion` 是**下发**（`AccountHandler.cs:121-122` 取 `Config.ServerConfiguration.AuthCurrentVersion`），**不做比较**；
- `GameVersion = 1.90.439170`（`ServerConfig.cs`）只被上面那段**丢弃**的队列比较用到；
- 协议号：`ReadProtocol` **int 或名字都认**（`GatewayController.cs:412-422`），CN 内层是 int ⇒ 直接命中。

⇒ **"版本号不匹配"不是风险来源**（至少在本仓库源码层面）。

#### ③ 真正的风险：**号段语义漂移**，不是字段名

CN 3.0.2 与 Shittim 的 Steam 口径若对同一数字给了不同含义，就会打到错的 handler，且**不会有版本报错**——只会表现为"字段缺失/数据为空"。

目前**实测一致**的只有两个号：
- `Account_Auth = 1002`（`report\36`）
- `NetworkTime_Sync = 3`（`work\ba\server\prototype\_scratch\probe_ticks.txt:14` 的官方 CN 响应）

其余 **`[未确认]`**，必须逐个跑一遍"CN 请求 → Shittim 是否命中预期 handler"。

### 9.6 落地：桥侧最小改动（多玩家）

**核心洞察：不需要"发号系统"，因为 `DevId` 本身就是数字 id。**

`[团队实测]` CN 的 `Account_Auth` 请求明文里有 `"DevId":"314816420"`（`report\35:55`），而它正是我们 SDK 下发的 `User.ID`。
⇒ **直接把每次请求明文里的 `DevId` 当 `publisherId` 用**，就能让不同玩家自动落到不同 `Accounts` 行。**这是"从根上解决"最省的一步，且不动 Shittim 一行。**

要改的三处（全在桥里，与 `report\44`/`report\46` 的分支图对齐）：

| # | 现在 | 改成 | 验收判据 |
|---|---|---|---|
| 1 | `ENTER_TICKET = base64("314816420/61de…")` 硬编码（`cn_bridge_v5.py:21-23`） | 每次请求从明文取 `DevId`/`Token` → `base64(f"{DevId}/{Token}")` | Shittim `Accounts` 行数随不同 `DevId` 增长 |
| 2 | `SESSION` 模块级单例（`:119-126`），`ensure_session()` 无参数（`:128-158`） | `sessions: dict[publisher_id] → SessionKey`，`ensure_session(dev_id, token)` | 并发两个玩家，`sessions.json` 出现两条不同 `UserId` |
| 3 | 转发时不带会话 | 每个请求带上**该玩家自己的** `SessionKey` | Shittim 日志无 `Session token mismatch` |

**映射表（若需要一个持久化的"玩家→账号"台账，只在桥侧建即可）**

```sql
-- 桥侧私有，与 Shittim 的 schale.sqlite3 分开
CREATE TABLE identity (
  dev_id       TEXT PRIMARY KEY,   -- 我们 SDK 的 uid（= DevId）
  publisher_id INTEGER NOT NULL UNIQUE,  -- = long.Parse(dev_id)
  token        TEXT,               -- 最近一次见到的 token（不参与匹配）
  account_server_id INTEGER,       -- 仅缓存，权威值在 Shittim 的 Accounts.ServerId
  created_at   TEXT NOT NULL
);
```

> **为什么键选 `publisherId` 而不是 token**：9.1 已证 `UserAccounts` 只按 `NpSN` 匹配、`NpToken` 不参与 ⇒ token 换号不变，token 做主键会造出重复账号。

**并发安全清单（桥侧）**：`sessions` 用锁或线程安全字典；同一 `publisherId` 的首次登录要串行化（否则两个请求同时走"查不到→建号"会双开）。Shittim 侧由 `SaveChangesAsync` + EF 保证，但**两次并发 `CheckNexon` 仍可能各建一个 `Accounts` 行**（`AccountHandler.cs:68` 的读-建之间没有唯一约束保护，`[未确认]` 是否有 unique index）⇒ 桥必须对 `publisherId` 加互斥。

---

## 10. 桃信（MomoTalk）与记忆大厅解锁

**一句话**：记忆大厅不是标志位，**是 Parcel（奖励）**；唯一写入点在 `ParcelHandler`。而桃信的两张表**只能由客户端的 33002/33004 写**。三张表全 0 ⇒ 这两个协议从未成功打到 Shittim。

### 10.1 协议面（`MomoTalkHandler.cs`，共 244 行）

| 协议 | 号 | 行 | 读/写 | 行为 |
|---|---|---|---|---|
| `MomoTalk_OutLine` | 33000 | `:151-165` | 读 | 回全部 outline + `FavorScheduleRecords`（`:159-162`） |
| `MomoTalk_MessageList` | 33001 | `:39-64` | 读 | 单角色 outline（`:47-53`）+ choices（`:55-61`） |
| **`MomoTalk_Read`** | **33002** | **`:66-149`** | **写** | ★ 首次创建 `MomoTalkOutLines`（`:82-90`）；写/改 `MomoTalkChoices`（`:102-123`）；`:136` 统一 `SaveChanges` |
| `MomoTalk_Reply` | 33003 | `:235-243` | — | **空实现**（注释 `:234`：客户端从不发它） |
| **`MomoTalk_FavorSchedule`** | **33004** | **`:167-232`** | **写 + 发奖** | ★ `ScheduleIds.Add`（`:216`）+ `BuildParcel`（`:219-223`） |

**两张表都是客户端上报驱动**：outline 幂等创建（`:77-92`，且 `:79-80` 要求该 `CharacterDBId` 必须是本账号的角色，否则直接 return 不写）；choice 落库前**用 `AcademyMessangerExcel` 校验** `ChosenMessageId/MessageGroupId/CharacterId/MessageCondition==Answer`（`:94-99`）。
**消息正文不在响应里** —— `docs/docs/modding/momotalk.md:44-46`：「client decides which groups are visible…; the server hands over the rows and tracks what you have read」。

### 10.2 记忆大厅：唯一写入点是 Parcel

`[源码实测]` `ParcelHandler.cs:114-115`：`case ParcelType.MemoryLobby: await parcelResolver.UpdateMemoryLobby(parcel);`
`[源码实测]` `ParcelResolver.UpdateMemoryLobby()`：按 `(AccountServerId, MemoryLobbyUniqueId)` 幂等查重，不存在才 `Context.MemoryLobbies.Add(new MemoryLobbyDBServer{ AccountServerId, MemoryLobbyUniqueId = parcel.Id })`。

`[源码实测]` **`MemoryLobbyHandler.cs` 四个 handler 一个都不写这张表**：`List`(12000) 只读 `:34`；`SetMain`(12001) 只改 `account.MemoryLobbyUniqueId`（`:47`）；`UpdateLobbyMode`(12002) 只改 `LobbyMode`（`:62`）；`Interact`(12003) 空（`:75`）。

| 结构 | 位置 | 语义 |
|---|---|---|
| `MemoryLobbies` 表 | `SchaleDataContext.cs:30`；模型 `MemoryLobbyDB.cs:9-25`（`AccountServerId` / `ServerId`(PK) / `MemoryLobbyUniqueId`） | **拥有集合，一个 id 一行** |
| `Accounts.MemoryLobbyUniqueId` | `AccountDB.cs:153` | **当前选中/展示的那一个**（唯一写入点 `MemoryLobbyHandler.cs:47`） |

**完整链路**：`33002 Read`（建 outline）→ `33004 FavorSchedule`（四道闸：schedule 存在 `:179`；outline 存在 `:183-185`；未领 `:187-188`；`FavorRank` 达标 `:191-193`）→ `ScheduleIds.Add` + `BuildParcel` → 奖励含 `MemoryLobby` 时落表 → `MemoryLobby_List`(12000) 读到。
⚠ `:183-185` 与 `:192-193` 都是 **静默 `return response`**（HTTP 200、正常信封、无错误）⇒ 客户端"点了没反应"。

**数据来源**：`AcademyMessangerExcel`（15,426 行，`CharacterId`+`MessageGroupId`，`MessageCondition ∈ {None,FavorRankUp,AcademySchedule,Answer,Feedback}`）+ `AcademyFavorScheduleExcel`（`ScheduleId→CharacterId/FavorRank/RewardParcelType-Id-Amount`，`MomoTalkHandler.cs:36,179,191,204-214`）。**不需要种进 DB**。

### 10.3 教程那一步：没有特判；`1006` 是"结果"不是"原因"

- 全仓 `MemoryLobby` 写入点只有 `ParcelHandler.cs:114` / `ParcelResolver.UpdateMemoryLobby` ⇒ **没有"首次解锁"特判**。
- 教程自己有协议：`Campaign_EnterTutorialStage`(6017, `CampaignHandler.cs:51`)、`ConfirmTutorialStage`(6015, `:72`)、**`TutorialStageResult`(6018, `:95`)** → `CampaignManager.CampaignTutorialStageResult` **也走 `BuildParcel`** ⇒ 教程关卡结算是一个候选发放点（**是否含 MemoryLobby 取决于 Excel `CampaignStageRewardExcel`，`未确认`**）。
- `Account_SetTutorial`(1006) 只做覆盖写（见 §12），**没有时序语义**。
- 文件树里**没有** `TutorialService` / `GuideMissionService`；教程持久化只有 `AccountTutorials` 一张表。

### 10.4 修法（判断）

| 候选 | 判断 | 理由 |
|---|---|---|
| ① 让 33002/33004 真正打到 Shittim | ✅ **正解** | 唯一会写 outline/choice/ScheduleIds 并触发 Parcel 的入口 |
| ② 种 MomoTalk 表 | ❌ 有害 | 语义是"玩家看到哪/选了啥"，硬种会让客户端跳过对话，且下次 33002 直接覆盖 |
| ③ 改 `Accounts.MemoryLobbyUniqueId` | ❌ 无效 | 它只是"选中"，拥有关系在 `MemoryLobbies` 表 |

### 10.5 未确认

教程关卡奖励是否含 `MemoryLobby`、幽香(13010) 的 favor schedule 奖励是否含 `MemoryLobby`、客户端在第几步发 33002/33004、`GuideMission` handler 在哪 —— **均未确认**（V2/V3 可用本地 `ExcelDB.db` 离线核）。

---

## 11. `Scenario_Skip` 崩溃与教程推进

### 11.1 A. `ScenarioHandler.cs:53` 抛的是**会话异常**，不是空引用/First 无匹配

`[源码实测]` `Skip()` 全文（`ScenarioHandler.cs:47-56`）只有 4 行有效代码：

```csharp
[ProtocolHandler(Protocol.Scenario_Skip)]
public async Task<ScenarioSkipResponse> Skip(
    SchaleDataContext db, ScenarioSkipRequest request, ScenarioSkipResponse response)
{
    var account = await _sessionService.GetAuthenticatedUser(db, request.SessionKey);   // ← :53  ★ 抛点
    return response;                                                                     // :55
}
```

**逐条对照 lead 的四个猜测**：

| 猜测 | 判定 | 依据 |
|---|---|---|
| 空引用？ | ❌ | `:53` 是 `await` 一个方法调用，没有解引用 |
| `First()`/`Single()` 无匹配？ | ❌ | Skip **没有任何 LINQ 查询**，方法体只有一行 |
| 显式 `throw`？ | ❌ | 方法体里没有 `throw` |
| **依赖 DB 数据（`ScenarioGroupHistories` 0 行）？** | ❌ | **Skip 根本不读任何场景表** |
| **✅ 真因：`GetAuthenticatedUser` 抛 `UnauthorizedAccessException`** | ✅ | `SessionKeyService.cs:147-164` 的三个 throw |

`[源码实测]` `GetAuthenticatedUser` 的三个抛出点（`SessionKeyService.cs`）：

```csharp
if (sessionKey == null)              throw new UnauthorizedAccessException("Session key is required");     // :149-150
if (!_activeSessions.TryGetValue(...)) throw new UnauthorizedAccessException("Session expired or invalid"); // :152-153
if (!session.Token.ToString().Equals(...)) throw new UnauthorizedAccessException("Session token mismatch"); // :155-156
```

⇒ **日志里 `System.UnauthorizedAccessException:` 后面那半句就是答案**（三种之一），lead 贴的栈没带文案，请回日志补看。

`[源码实测]` 异常传播链：handler 抛 → `ProtocolHandlerRegistry.cs:176-180` 的 `catch (Exception ex) { _logger.LogError(ex, "Error invoking handler for protocol {Protocol}", …); throw; }`（**这就是你看到的那行 "Error invoking handler for protocol Scenario_Skip"**）→ 网关 `GatewayController.cs:287-295` 捕获 → 回 `Error`/`ErrorCode=3(InvalidSession)`，**HTTP 200**。

**⇒ 与 `ScenarioGroupHistories` = 0 行完全无关。** 那张表是 `Scenario_GroupHistoryUpdate`(19005) 写的（`ScenarioHandler.cs:69-82` → `_scenarioManager.ScenarioGroupHistoryUpdate`），Skip 从不碰它。

### 11.2 A2. `ScenarioSkipRequest` 字段（CN 缺哪个都不影响本次崩溃）

`[源码实测]` `NetworkProtocol.cs:6279-6284`：

```csharp
public class ScenarioSkipRequest : RequestPacket {
    public override Protocol Protocol { get => Protocol.Scenario_Skip; }
    public long ScriptGroupId { get; set; }          // :6282
    public int  SkipPointScriptCount { get; set; }   // :6283
}
```

Skip **一个字段都不读**（方法体就一行）。⇒ 即便 CN 少发/改名，也只会落默认值 0，**不会崩**。

### 11.3 B. 正常流程里谁写 `ScenarioGroupHistories`

| 表 | 写入协议 | 证据 |
|---|---|---|
| `ScenarioGroupHistories` | **`Scenario_GroupHistoryUpdate`(19005)** | `ScenarioHandler.cs:69-82`：`_scenarioManager.ScenarioGroupHistoryUpdate(db, account, request)`，请求字段 `ScenarioGroupUniqueId` + `ScenarioType`（`NetworkProtocol.cs:6266-6271`） |
| `ScenarioHistories` | **`Scenario_Clear`(19007?)** | `ScenarioHandler.cs:84-99`：`_scenarioManager.ScenarioClear(db, account, request)` 返回 `ScenarioHistoryDB`；另 `AccountService.cs:375` 建号时会补一些 `CampaignStageHistories`（不是 Scenario） |
| `Scenario_Skip`(19003) | **什么都不写** | `:55` 直接 return |
| `Scenario_Select`(19004) | **什么都不写** | `:58-67` 同样只验会话 |

⇒ **现象自洽**：`ScenarioHistories` 4 行（来自 `Scenario_Clear`）、`ScenarioGroupHistories` 0 行（**客户端没发 19005**）。

### 11.4 C. 记忆大厅 Parcel 从哪来 / 编号空间

- **发放点**：任何 `BuildParcel` 的地方都可能是——`Scenario_Clear` 的奖励（`:92-96` 有 `ParcelResultDB`）、`Campaign_TutorialStageResult`（`CampaignHandler.cs:95-111`）、`MomoTalk_FavorSchedule`（`:219-223`）、邮件附件、任务奖励。**没有单独的"只发记忆大厅"的协议**。
- **编号空间**：`MemoryLobbyDBServer.MemoryLobbyUniqueId` = **`Parcel.Id`**（`ParcelResolver.UpdateMemoryLobby`），Parcel 由 `ParcelType.MemoryLobby` + id 组成 ⇒ **编号空间是 `MemoryLobbyExcel` 的 id，与 `Characters.UniqueId`（`CharacterExcel.Id`）不是同一套**。`[推断]` 二者数量级相近但不等价，**未确认**是否有交叉约束。
- **"教程专用初始 Parcel 包"**：`[源码实测]` 建号种子用的是 `DefaultParcelExcel`（`AccountService.cs:32-38`）——它是**一张通用表**，是否含 `MemoryLobby` 取决于数据（**未确认**，可用本地 ExcelDB 查 `DefaultParcelExcel` 是否出现 `ParcelType.MemoryLobby`）。

### 11.5 D. 最小修法

**不是 ② 种 `ScenarioGroupHistories`，也不是 ③ 让 19003 不转发。**

✅ **正解 = 修会话注入（与 §8 同一个根因）**：拒绝发生在 `:53`，而 `:53` 只做会话校验 ⇒ 只要让 19003 带上**有效的 `SessionKey`**，它立刻变回"无害的 no-op"（`:55` 直接 return，天然幂等、不写库、不报错）。

**为什么"只有 Skip 崩、1006 不崩"（`[推断]`，机制与 `report\44` 一致）**：桥只对它**接管**的协议注入 `SessionKey`；`Scenario_Skip`(19003) 落在 `_forward` 分支 → 原样转发 → Shittim 收到**没有 `SessionKey`** 的请求 → `:149-150` 抛 `"Session key is required"`。
⇒ **修法就是 §9.6 的"每协议都注入会话"**，不需要给 Scenario 写任何种子数据。

**判据（看完日志即可定案）**：若那 6 次的异常文案是 `"Session key is required"` ⇒ 上述推断成立，改注入即可；若是 `"Session expired or invalid"`/`"Session token mismatch"` ⇒ 是会话被顶掉（同账号多端，`SessionKeyService.cs:104`），改会话复用策略。

---

## 12. `AccountTutorials` 更新语义与持久化

### 12.1 结论先说：**`SetTutorial` 的更新分支存在，不是"只写一次"的 bug**

`[源码实测]` `AccountHandler.cs:672-698` 完整原文：

```csharp
672  [ProtocolHandler(Protocol.Account_SetTutorial)]
673  public async Task<AccountSetTutorialResponse> SetTutorial(
674      SchaleDataContext db,
675      AccountSetTutorialRequest request,
676      AccountSetTutorialResponse response)
677  {
678      var account = await _sessionService.GetAuthenticatedUser(db, request.SessionKey);
679
680      var tutorial = db.AccountTutorials.FirstOrDefault(x => x.AccountServerId == account.ServerId);
681
682      if (tutorial == null)
683      {
684          tutorial = new AccountTutorial
685          {
686              AccountServerId = account.ServerId,
687              TutorialIds = request.TutorialIds.ToList()
688          };
689          db.AccountTutorials.Add(tutorial);
690      }
691      else
692      {
693          tutorial.TutorialIds = request.TutorialIds.ToList();      // ★ 更新赋值在这里
694      }
695
696      await db.SaveChangesAsync();                                  // ★ 两个分支共用
697      return response;
698  }
```

逐条回答 lead 的 5 问：

| # | 问题 | 答案 |
|---|---|---|
| **1** | `if (tutorial == null)` 之后有没有更新赋值？ | **有**：`:691-694` 的 `else` 分支 `tutorial.TutorialIds = request.TutorialIds.ToList();`。⇒ **"行一旦创建就永不更新"的假说不成立** |
| **2** | `SaveChanges()` 在哪个分支？ | **不在分支里，在分支外**（`:696`），**创建与更新都会落盘** |
| **3** | `request.TutorialIds` 是全量还是增量？ | **服务端按全量覆盖处理**（`:693` 直接整份替换，没有 `Union`/`AddRange`）。⇒ **客户端必须每次发完整集合**；若它发增量，库里会**变少** |
| **4** | `GetTutorial`(1005) 读逻辑 | `:664-667`：`var tutorial = db.AccountTutorials.FirstOrDefault(...); response.TutorialIds = tutorial?.TutorialIds ?? Enumerable.Range(1, 27).Select(i => (long)i).ToList();` ⇒ **有行就回行里的值**。库里是 `[1,2]` ⇒ 客户端收到 `{1,2}` ⇒ **从第 3 步继续**（不是从头） |
| **5** | 教程总共有多少个 id？ | 代码里是**硬编码 27**（`:667` `Enumerable.Range(1, 27)`）。这是 Shittim 自己的兜底值；**真实总数在 `Schale/FlatData/TutorialExcel.cs` 对应数据里，`未确认`**（需查 ExcelDB） |

### 12.2 那 `[1,2]` 是怎么来的？——**是客户端最后一次"真的发了 2 步"，不是丢更新**

`[推断，逻辑闭合]` 三条证据交叉：

1. 更新分支存在且 `SaveChanges` 共用（§12.1）⇒ **每次 1006 成功都会覆盖**；
2. 你说 1006 被收到 **8 次**。若客户端曾发过 `[1,2,3…N]`，库里必然是 N 结尾；**现在是 `[1,2]`，说明 8 次里有内容的最后一次，其 `TutorialIds` 只到 2**；
3. 同时 `Scenario_Skip` 崩了 **6 次**（§11）⇒ 客户端在"第 2 步之后、第 3 步途中"反复撞墙。

⇒ **因果顺序应为：1006 推进到 2 → 客户端进入第 3 步（剧情跳过）→ `Scenario_Skip` 因会话无效被拒 → 客户端拿不到成功响应 → 教程卡死 → 之后再没发出超过 2 的 `TutorialIds`。**
**⇒ 持久化没坏；是"教程没走到能上报第 3 步"的地方。** 与"杀掉重登又从头过教程"完全一致：客户端读 `GetTutorial` 得到 `{1,2}`，从第 3 步起——看起来就像"从头"。

### 12.3 一个必须注意的坑：**EF 会把 `List<long>` 存成 JSON 文本，但没有显式转换器**

`[源码实测]` `Schale/Data/Models/AccountTutorial.cs`（全文 13 行）：

```csharp
public class AccountTutorial {
    [Key] public required long AccountServerId { get; set; }
    public List<long> TutorialIds { get; set; } = [];
}
```

`[源码实测]` `SchaleDataContext.cs` 里关于它的**只有两行**：`:16` `DbSet<AccountTutorial> AccountTutorials`、`:114` `Property(x => x.AccountServerId).ValueGeneratedNever()` —— **没有 `HasJsonConversion`**（对比 §7.2 里 `CurrencyDict` 用的是显式 `HasJsonConversion`）。

⇒ 它走的是 **EF Core 的 primitive collection 原生映射**（`List<long>` → JSON TEXT 列），change tracking 由 EF 快照比较负责，`:693` 的赋值**能被检测到**。
**`未确认`**：EF Core 具体版本（`Shittim-Server.csproj` 未读），primitive collection 需要 EF Core 8+。若实际低于 8，这一列会退化成"未映射/值转换器缺失"，那时的表现会是**整列不落盘**——但那与"库里有 `[1,2]`"矛盾，故可排除。

### 12.4 `1006` 与 `19003` 的先后，以及 8 vs 6 能推出什么

- **先后关系**：`[源码实测]` 两者**在服务端完全独立**——`SetTutorial` 只写教程表并 `SaveChanges`（`:696`）；`Scenario_Skip` 只验会话即返回（`ScenarioHandler.cs:55`）。**没有任何代码把二者串起来**，所以"Skip 崩了会不会影响 1006"在**服务端层面：不会**。
- **客户端侧**（`[推断]`）：客户端大概率是"先上报进度(1006) → 再播剧情/跳过(19003)"。Skip 失败后它停在那个等待态 ⇒ **不再发后续 1006**。这解释了 8 次 1006 都停在 `[1,2]`。
- **8 与 6 能否反推进度**：能推出**上界**——教程最多推进到"第 2 步已登记、第 3 步未完成"。**不能**推出"一共几步尝试"（客户端可能重试同一发）。
  ⚠ 注意：8 次 1006 里若有一次发生在重登之后，则它携带的仍是 `[1,2]`（因为客户端从 1005 读到的就是 `[1,2]`）⇒ **重登不会丢进度，只会重复上报同一份**。这与用户"重启后又要从头过"的体感一致。

### 12.5 修法

| 候选 | 判断 |
|---|---|
| 改 `SetTutorial`（补更新赋值） | ❌ **没必要**——赋值已存在（`:693`） |
| 手改 `AccountTutorials` 里的 `TutorialIds` | ⚠ 能"骗过"1005，但客户端的教程分支由剧情推进，**跳过 19003 那一步不会因此消失**，且下次 1006 会覆盖回来 |
| **修 `Scenario_Skip` 的会话（§11.5）** | ✅ **正解**：它是唯一真正挡住第 3 步的东西，且修好后 Skip 是天然幂等的 no-op |
| 让 19003 不转发（落回旧桥） | ❌ 等于放弃这一环，且客户端仍会认为"跳过未成功" |

### 12.6 未确认清单（§12）

| 项 | 状态 |
|---|---|
| 教程 id 的真实总数（Excel） | **未确认**（代码只有硬编码 27） |
| EF Core 具体版本 / primitive collection 是否生效 | **未确认**（未读 `Shittim-Server.csproj`；但库里有 `[1,2]` 反证该列确实落盘） |
| 客户端 1006 发的是全量还是增量 | **推断为全量**（`:693` 整份覆盖 + 库里是 `[1,2]` 两元素 ⇒ 客户端曾发过长度 2 的完整集合） |
| 8 次 1006 各自携带的具体 `TutorialIds` | **未确认**（需要桥日志打印 payload；目前日志只记长度/摘要） |
| `Scenario_Skip` 那 6 次的异常文案（三种会话错误的哪一种） | **未确认**（lead 贴的栈没带 message，**回日志补看即可一秒定案**） |
