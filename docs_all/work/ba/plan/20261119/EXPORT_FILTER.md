# BA 私服 · 道具出口过滤（BAPATCH-EXPORTFILTER v1）

- 时间：2026-11-19
- 触发事故：2026-11-19 00:22，`Items.UniqueId=90070000` 被下发 → 客户端解析 `/api/item/list` 失败 → 登录死循环
- 改动文件（服务端源码 5 个，其中 2 个新增）：
  - 新增 `Shittim-Server/Services/ClientItemFilter.cs`
  - 新增 `Shittim-Server/Resources/ClientItemIds.txt`（生成物，1803 条）
  - 改 `Shittim-Server/Core/HandlerManager.cs`（出口钩子，`Dispatch` 由表达式体改为 async 方法）
  - 改 `Shittim-Server/CLI/GameServer.cs`（启动时预热白名单，1 行调用）
  - 改 `Shittim-Server/Shittim-Server.csproj`（把白名单复制进发布目录）
- 工具/测试（3 个新增）：`work/ba/scripts/gen_client_item_ids.py`、`work/ba/scripts/test_client_item_filter.py`、`work/ba/scripts/exportfilter_selftest/`
- 构建产物：`_build_exportfilter/Shittim-Server.dll`，sha256 `63ca8f34694f65420c5dff4ec0822192386407162c9ca38d2b326c65d434789f`，**2,687,488 字节**
- 部署状态：**未部署**（见 §11）

---

## 0. 一句话结论

在**响应离开 handler、进入网关序列化之前**（`HandlerManager.Dispatch`）加了一道出口过滤：凡是 `ItemDB.UniqueId` 不在「国服客户端 `ItemDBSchema` 全集」里的道具，一律从响应对象里摘掉。数据库一行没删、表没改、别人代码没重排；合法道具的响应逐字节不变。

---

## 1. 根因回顾

### 1.1 两起事故，同一个根因

| # | 时间 | 现象 | 根因 |
|---|---|---|---|
| 1 | 2026-11-17 | 服务端下发 23 个客户端表里没有的**角色 id** → 登录「服务端处理错误」 | 服务端角色表 ⊃ 客户端角色表 |
| 2 | 2026-11-19 00:22 | 背包里一行 `Items.UniqueId=90070000` → 客户端 `ItemDBSchema` 查不到 → 解析 `/api/item/list` 失败 → 登录死循环 + 「同步账号信息时发生错误」 | 服务端道具表 ⊃ 客户端道具表 |

第 1 起的修法是 `BAPATCH-CLIENTROSTER v1`（`Services/ExcelTableService.cs` 的 `GetTable<T>()` 里做表级过滤 + `Resources/ClientUnsupportedCharacters.txt` 运行时可扩）。本次沿用它的两个设计取舍：**名单外置成文本文件（改文件不用重编译）**、**拦在下发/读取的单一咽喉点而不是逐个调用方打补丁**。

### 1.2 为什么「服务端表里有」不等于「客户端认得」

- 服务端：`/www/wwwroot/ba_srv/Resources/Dumped/ExcelDB.db`，**311,083,008 B**，日服表。
- 客户端：`work/ba/data/ExcelDB.db`，**160,534,528 B**，md5 `824ce3a8bee2bb5ae36ada1ac95048f1`，与官方 `TableManifest` 里 `ExcelDB.db` 的 Size/Crc 逐位一致。
- 客户端 `ItemDBSchema` 共 **1803** 个 id（`CREATE TABLE ItemDBSchema ('Id' INTEGER, 'Bytes' Blob)`），事故里的 `90070000` **不在**这 1803 个里（本次已重新逐 id 核对，见 §7）。

服务端表比客户端表大，这个差集里既有「客户端还没更新到的新道具」，也有「只在日服/活动池存在、国服永远不会有」的 id。**服务端自己无法从表结构上区分这两类**，所以必须拿客户端那份表来当白名单。

### 1.3 为什么「删掉那一行」不是修法

删行确实能让登录恢复（00:22 就是这么救的），但：

1. 它丢数据——玩家真金白银抽到的东西被抹了，没有任何记录；
2. 它不可持续——每次抽到/发到这类 id 都要人工删一次；
3. 它把问题从「下发」挪到了「存储」，而存储本身不伤害任何人（客户端根本看不到库里的行）。

本次改动**只影响下发**：`90070000` 那一行仍然在 `Items` 表里，只是不再出现在任何响应里；等客户端更新、`ItemDBSchema` 收录了这个 id，重新生成白名单即可自动恢复，不需要补偿、不需要恢复备份。

---

## 2. 设计

### 2.1 只做出口过滤（egress-only）

```
handler 返回 ResponsePacket
        │
        ▼
HandlerManager.Dispatch ──► ClientItemFilter.FilterResponse(response, accountId)   ← 唯一改动点
        │
        ▼
GatewayController: JsonConvert.SerializeObject(rsp) → 加密 → 客户端
```

过滤发生在「handler 已经跑完、`ParcelResultDB` 已经拼好、但 JSON 还没生成」的那一刻。此时：

- **数据库已经写完**（`ParcelResolver.FinalizeUpdates` 里 `SaveChangesAsync` 早就提交了），所以删不删只影响这份内存里的响应对象；
- **还没有任何字节被序列化**，所以过滤是「改对象」，不是「改 JSON 字符串」，不需要处理转义/顺序/编码；
- **所有协议共用这一个出口**（`GatewayController`、`PublicApiController`、Dev `ApiController` 都走 `HandlerManager.Dispatch`）。

### 2.2 为什么钩在这里，而不是 145 处赋值点

`grep "ParcelResultDB =" Shittim-Server` 有 **145 处**赋值，分布在 40+ 个 handler / manager 里；协议程序集里带 `ParcelResultDB` 字段的响应 DTO 有 **168 个**。再加上 `ItemListResponse`、`CommonCheatResponse.ItemDBs`、`ShopBuyGacha2Response.ConsumedItems`、`CharacterFavorGrowthResponse.ConsumeStackableItemDBResult` 这些各自独立的道具列表——逐个赋值点补过滤，**名单一定会漏、一定会过期**，而且每加一个新玩法就多一个漏点。

放在出口，等价于一句话：**「只要这个对象要变成发给客户端的 JSON，它里面的 ItemDB 就会被检查」**，与是哪个 handler、哪条玩法、以后新加的代码无关。

否决的两种替代方案：

| 方案 | 否决理由 |
|---|---|
| 在 `db.GetAccountItems()` 源头过滤 | ①只覆盖「读账号背包」这一条路，抽卡/邮件/任务奖励拼出来的 `ParcelResultDB` 全漏；②GM 面板、导出命令也从同一处读，源头过滤会让面板看不见这些行，等于「软删除」，正是 §1.3 要避免的 |
| 在 `ExcelTableService.GetTable<ItemExcelT>()` 做表级过滤（照抄 CLIENTROSTER） | 服务端道具表被 `!give`、商店、制造等**发放**路径共用；在表上删行会让「客户端不认」变成「服务端也发不出来」，而且 `ExcelTableService` 的角色过滤是已上线的另一件事，不该混进去 |

### 2.3 白名单从哪来

`work/ba/scripts/gen_client_item_ids.py` 从**客户端那份** `ExcelDB.db` 的 `ItemDBSchema.Id` 读出全部 id，排序后写到
`Shittim-Server/Resources/ClientItemIds.txt`（与 `ClientUnsupportedCharacters.txt` 同目录、同风格：一行一个 id，`#` 注释，空行忽略）。

### 2.4 匹配的是 `UniqueId`，不是 `ServerId`

`Items` 表里两个 id 很容易混：

- `ServerId`：这一行的行号（客户端用它来 `Item_Sell` / `Item_Lock`，纯服务端概念）；
- `UniqueId`：道具在 `ItemExcel`/`ItemDBSchema` 里的 id（客户端拿它查表）。

客户端炸在「查不到 excel 行」，所以白名单比对的是 **`ItemDB.UniqueId`**。`ServerId` 从不参与判断。

---

## 3. 过滤点清单（文件 + 行号）

**唯一的过滤调用点：**

| 文件:行 | 内容 |
|---|---|
| `Shittim-Server/Core/HandlerManager.cs:22-26` | `Dispatch` 改为 `async`，在 `InvokeHandler` 返回后调用 `ClientItemFilter.FilterResponse(response, request.AccountId)`（**调用在 :25**） |

**过滤器内部（`Shittim-Server/Services/ClientItemFilter.cs`）：**

| 行 | 内容 |
|---|---|
| `:53` / `:59` / `:65` | `IsEnabled` / `AllowedCount` / `Warmup` |
| `:68` | `IsAllowed(long uniqueId)` |
| `:76` | `Filter(IEnumerable<ItemDB>)`（窄接口，返回同一个 List 实例） |
| `:97` | `FilterInPlace(List<ItemDB>)` —— 原地 `RemoveAll`，保留存活项相对顺序 |
| `:112` | `FilterInPlace(Dictionary<long, ItemDB>)` —— 原地 `Remove`，等于 `ParcelResultDB.ItemDBs` |
| `:141` | `FilterResponse(ResponsePacket?, accountId)` —— 出口入口，异常全部吞掉（过滤器不能把请求搞挂） |
| `:158` | `VisitResponse` —— 递归子响应（`Account_LoginSync` 的 `ItemListResponse` 在下一层），深度上限 4 |
| `:178` | `ApplyItemMembers` —— 对任一对象应用三类成员：`List<ItemDB>` / `Dictionary<long, ItemDB>` / 单个 `ItemDB` |
| `:232` / `:264` | `LoadUncached` / `ResolveListPath` |

**它盖住的生产赋值点（举例，非全部）：**

| 文件:行 | 赋值 | 说明 |
|---|---|---|
| `Core/NetworkProtocol/Handlers/AccountHandler.cs:519-523` | `response.ItemListResponse = new ItemListResponse { ItemDBs = ... }` | `Account_LoginSync` 子包（BAPATCH-LOGINSYNC-ITEM v1 加的） |
| `Core/NetworkProtocol/Handlers/ItemHandler.cs:41-42` | `response.ItemDBs` / `response.ExpiryItemDBs` | `Item_List`（protocol 4000） |
| `Services/ParcelResolver.cs:248` | `ParcelResult.ItemDBs.Add(...)`（已有行改数量） | 所有走 parcel 的奖励路径 |
| `Services/ParcelResolver.cs:544` | `ParcelResult.ItemDBs.Add(...)`（新行） | 同上，`FinalizeUpdates` |
| `Services/ConsumeHandler.cs:230` | `ConsumeResultData.ParcelResult.ItemDBs.TryAdd(...)` | 消耗返还 |
| `Core/NetworkProtocol/Handlers/CraftHandler.cs:611, :678` | `new ParcelResultDB { ItemDBs = ... }` | 制造票据 |
| `Core/NetworkProtocol/Handlers/ShopHandler.cs:296, :944` | `response.ParcelResultDB = new ParcelResultDB` | 抽卡/商店 |
| `Core/NetworkProtocol/Handlers/ItemHandler.cs:141-147` | `ParcelResultDB { ItemDBs = itemDB }` | `Item_AutoSynth` |

这些点本身**一行没改**；`ApplyItemMembers` 是按**属性类型**认的，所以还自动覆盖了没人提到的：

- `ItemListResponse.ItemDBs` / `.ExpiryItemDBs`（`List<ItemDB>`）
- 168 个响应 DTO 的 `ParcelResultDB.ItemDBs`（`Dictionary<long, ItemDB>`）
- `CommonCheatResponse.ItemDBs`（`List<ItemDB>`）
- `ShopBuyGacha2Response.ConsumedItems` / `ShopBeforehandGachaPickResponse.AcquiredItems`（`List<ItemDB>`）
- `CharacterFavorGrowthResponse.ConsumeStackableItemDBResult`（`List<ItemDB>`）
- 单个 `ItemDB` 字段：`ItemLockResponse.ItemDB`、`ItemConsumeResponse.UsedItemDB`、`ItemBulkConsumeResponse.UsedItemDB`、`ItemSelectTicketResponse.UsedItemDB`、`CraftCompleteProcessResponse.TicketItemDB`（`CraftHandler.cs:329` / `:411`）等（命中时置 `null`，理由见 §8）

---

## 4. 加载与降级策略

### 4.1 路径

```
<AppContext.BaseDirectory>/Resources/ClientItemIds.txt
```

即 **DLL 旁边的 `Resources` 目录**，与 `ExcelTableService.ResourceDir`（`Resources/ClientUnsupportedCharacters.txt` 所在处）是同一个目录。
可用环境变量 `SHITTIM_CLIENT_ITEM_IDS` 覆盖整个文件路径（与 `SHITTIM_EXCELDB_SQLCIPHER_KEY` 同一套覆盖思路，方便灰度/对比）。

启动时 `CLI/GameServer.cs:85` 调一次 `ClientItemFilter.Warmup()`：文件有问题，启动日志里就能看到，而不是等第一个玩家登录才报。

### 4.2 解析规则（与 `ClientUnsupportedCharacters.txt` 一致）

- `Trim()` 后：空行跳过、`#` 开头跳过、其余按 `long`（固定 InvariantCulture）解析；
- 解析失败的行只计数、不报错、不中断（文件尾多一行脏数据不会让过滤失效）；
- 结果是 `HashSet<long>`，`Contains` O(1)；
- 全程 `lock` + `Volatile` 保证只加载一次，多线程并发安全。

### 4.3 降级：**fail-open**

| 情况 | 行为 | 日志 |
|---|---|---|
| 文件不存在 | 过滤**关闭**，全部道具照发 | `WARN: export filter disabled: file missing (<path>); every item id is forwarded unfiltered` |
| 文件里没有一条 id | 过滤**关闭**，全部照发 | `WARN: export filter disabled: file has no ids (<path>); ...` |
| 读文件抛异常 | 过滤**关闭**，全部照发 | `WARN: export filter disabled: could not read the client item allowlist (...); ...` |
| 遍历响应时抛异常 | 该次响应按已处理的部分返回，**不 500** | `WARN: export filter threw while scanning <Type> (...)`，每进程只打一次 |

fail-open 是刻意的：名单文件是人为维护的，**名单坏掉导致的后果不能比事故本身更严重**。如果名单缺失就全滤，玩家会瞬间看到空背包——那是比「多一件道具」更糟的故障。宁可退化成「不过滤」（回到今天之前的行为），也要保证游戏能进。

### 4.4 命中日志与限流

```
[ClientItemFilter] WARN: withheld ItemDB UniqueId=90070000 (account 4) from ItemListResponse.ItemDBs:
not in the CN client's ItemDBSchema (ClientItemIds.txt); the row stays in the database and is only kept
out of responses. Further drops of this id are not logged this process.
```

- 带 **accountId + uniqueId + 来源属性名**；
- **同一 id 每进程只打一次**（`ConcurrentDictionary<long, byte>`），否则一个脏存档会在每次登录、每次 `Item_List`、每次领奖里各刷一条；
- 限流是「按 id」而不是「按行数」：同一个 id 出现在 5 个响应里只打 1 条，5 个不同坏 id 各打 1 条。

---

## 5. 「正常路径逐字节不变」论证

### 5.1 论证

设白名单集合 `A`（= 客户端 `ItemDBSchema.Id` 全集，1803 个），响应里的道具集合 `I`。

1. **数学上**：过滤只做一件事——`I := I \ (¬A)`。当 `I ⊆ A` 时，`I \ (¬A) = I`，集合不变。
2. **代码上**：`FilterInPlace` 走的是 `List<T>.RemoveAll(predicate)`，谓词对 `A` 内元素恒 `false`；0 个元素被删时，`List` 的 `_size`、`_items` 数组内容、元素相对顺序、对象引用全都不变。`Dictionary` 版本同理（`rejected == null` 时直接 `return false`，一次 `Remove` 都不执行）。
3. **序列化上**：过滤发生在序列化之前，且不新建对象、不重排、不补字段。属性值没变 → `JsonConvert.SerializeObject` 输出字节没变。
4. **数据上**：任何 `SaveChangesAsync` 都发生在 handler 内部、过滤之前；过滤只碰响应对象，不碰 `DbContext` 里跟踪的实体，所以数据库内容不变。
5. **前提成立**：账号 4 的 53 个 id、账号 2 的 32 个 id 全部 ∈ `A`（§7 实测，一个都没被滤）。

### 5.2 实测（不是推断）

C# 自测里对**同一个账号的同一批 53 件道具**构造两份 `ItemListResponse`：

```
baseline  = 53 件合法道具            → JSON_B
withBad   = 54 件（baseline + 90070000，插在第 27 位） → FilterResponse → JSON_A
断言 JSON_A == JSON_B                                  ✅ PASS
```

`Account_LoginSync` 的 `ItemListResponse` 子树做同样的对比，同样通过。也就是说「往正常背包里硬塞一行坏数据，过滤后得到的 JSON 与从没塞过完全一致」——比「53 件过滤后还是 53 件」更强。

### 5.3 线上两套真实存档

| 账号 | 道具数 | 全部在白名单 | 被滤掉 |
|---|---|---|---|
| 4（= ServerId 4） | 53 | ✅ | 0 |
| 2 | 32 | ✅ | 0 |

---

## 6. 编译

```
cd "C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\srv_src"
& 'C:\Program Files\dotnet\dotnet.exe' publish Shittim-Server\Shittim-Server.csproj -c Release -o _build_exportfilter --nologo
```

**成功**（0 error；告警全部是本次之前就有的 `CS8632`/`EF1002`/`NU1903`，`ClientItemFilter.cs` 自身 0 告警）。

| 产物 | 字节 | sha256 |
|---|---|---|
| `_build_exportfilter/Shittim-Server.dll` | **2,687,488** | `63ca8f34694f65420c5dff4ec0822192386407162c9ca38d2b326c65d434789f` |
| `_build_exportfilter/Schale.dll` | 5,392,896 | `b06f46090f9d8eb8657e51401b789178d9090ad5a5a6d6d1faaa791dad429858` ✅ 与要求一致 |
| `_build_exportfilter/Resources/ClientItemIds.txt` | **12,659** | `48af0fd945fbd2dfaca0afa022b9cafb7095514bfd578b85a09dca17bbeb5ac6`（**1803** 条） |

**与基线的关系**：线上基线 `e90867e2b6c75efdb07ff3bc7ea53fb597e3904a588fbab0fb2212f1c50e632b`（2,680,320 B）在本机源码树里有逐位相同的产物 `_build_shoplistnre/Shittim-Server.dll`，说明本树就是基线的源码树。本次只在其上新增/改动 §0 列出的 5 个文件，DLL 增长 **+7,168 字节**（一个新类 + 一个钩子 + 一处启动调用）。

---

## 7. 自测（真跑，输出可复现）

```
python work\ba\scripts\test_client_item_filter.py
→ TOTAL 34/34 checks passed
```

（最后一次完整运行的原始输出留在 `work/ba/scripts/_test_exportfilter.last.txt`。）

分四层，全部实际执行：

### 第 1 层：白名单文件（13 项）

- 1803 条、严格升序、无重复；
- 与客户端 `ItemDBSchema` 的 id **集合完全相等**（不是「包含」，是「相等」）；
- `90070000` 不在其中；
- 无 BOM、纯 LF、结尾恰好一个换行；
- 文件头含条目数与重生成命令（`--check` 也能跑）。

### 第 2 层：生成可复现（4 项）

- `gen_client_item_ids.py --check` → 现有文件是最新的（exit 0）；
- 连续两次生成 → 两个文件逐字节相同；
- 新生成的文件与仓库里的文件逐字节相同。
  （文件头的「生成时间」取的是**源库 mtime** 而不是当前时钟，所以重跑不会因为时间变了而不一致。）

### 第 3 层：编译后的 C# 过滤器（19 + 5 + 5 项断言）

自测工程 `work/ba/scripts/exportfilter_selftest/` 编译的是**服务端那份 `ClientItemFilter.cs` 源文件本身**（`<Compile Include=...>` 链接，不是复制），引用发布产物的 `Schale.dll`，所以跑的是要上线的那份逻辑。

| 断言 | 结果 |
|---|---|
| 过滤已启用 / 白名单 1803 条 | ✅ |
| 白名单里随机 200 个 id → 全部通过 | ✅ |
| `90070000` → 被拒 | ✅ |
| 账号 4 的 53 个 id → 全部通过 | ✅ |
| 账号 2 的 32 个 id → 全部通过 | ✅ |
| `Item_List`：54 件 → 53 件、顺序不变、序列化前/后逐字节相同 | ✅ |
| `Account_LoginSync` 子 `ItemListResponse`：54 → 53、逐字节相同 | ✅ |
| `ParcelResultDB.ItemDBs`：坏行删除、好行保留 | ✅ |
| 嵌套子响应（深度 2）也能滤到 | ✅ |
| 过滤两次是幂等的 | ✅ |
| 缺文件 → 过滤关闭，54 件全放行，WARN 含 `export filter disabled: file missing` | ✅ |
| 空文件 → 过滤关闭，WARN 含 `export filter disabled: file has no ids` | ✅ |
| 命中日志：`90070000` 在多次响应里只打 **1** 条 WARN，且带 `account 4` | ✅ |

### 第 4 层：发布产物（5 项）

- `Shittim-Server.dll` 里能找到 `ClientItemFilter` 类型名与 `ClientItemIds.txt` 字符串（UTF-16LE 常量）；
- `Schale.dll` sha256 仍是 `b06f4609...`；
- 发布目录里带着 `Resources/ClientItemIds.txt`，与源码树里那份逐字节相同。

---

## 8. 边界：这次**没做**的事

1. **不删任何数据库行**。`Items` 里那行 `90070000` 还在，只是不发。删行=丢数据，且客户端更新后无法自动恢复。
2. **不动 `GachaRecruitBanners.cn.json`、`ShopManager.cs` 现有逻辑、`ExcelTableService` 的角色过滤**。本次没有一行改动落在这三处。
3. **不滤 `ParcelInfo` / `DisplaySequence` / `ParcelForMission`**。这些是 `{Type, Id}` 的奖励展示项，不是 `ItemDB` 行；两起事故的崩溃点都是「客户端拿 Id 查 `ItemDBSchema` 拿不到」的 **ItemDB 反序列化**，而奖励展示条目的容错路径不同。改它们会改变「本次获得」弹窗的内容，属于另一件事；真需要时，在 `ApplyItemMembers` 里加一条 `ParcelType.Item` 的谓词即可（同一个白名单）。
4. **单个 `ItemDB` 字段（`ItemLockResponse.ItemDB` 等）命中时置 `null`**。这类字段永远是「客户端自己刚请求过的那件道具」的回显，正常客户端不可能命中；置空是兜底，避免把解析不了的 id 回给客户端。若真命中，日志会明确写出属性名。
5. **`AccountDataCommand` 的导入/导出 JSON 不经过滤**。那是运维命令读写本地文件，不是发给客户端的报文。
6. **客户端更新后要重跑生成脚本**。新客户端 `ItemDBSchema` 变大 → 白名单变大 → 新道具自动可发；这是**唯一的运维动作**（改文件不用重编译，但要把文件放到服务器 `Resources/` 下）。

---

## 9. 部署步骤（**未执行**，留给有权限的人）

> 本任务明令禁止部署/SSH/连 <SERVER_IP>/改数据库 nginx 桥。以下仅是步骤记录。

1. 备份现场：`cp -a /www/wwwroot/ba_srv/Shittim-Server.dll /root/panel_backup_<STAMP>/`
2. 传 `_build_exportfilter/Shittim-Server.dll` → `/www/wwwroot/ba_srv/Shittim-Server.dll`
3. 传 `_build_exportfilter/Resources/ClientItemIds.txt` → `/www/wwwroot/ba_srv/Resources/ClientItemIds.txt`
4. 重启：`tmux kill-session -t shittim` → 重新 `dotnet Shittim-Server.dll --console --id 2`
5. 看启动日志应出现：`[ClientItemFilter] loaded 1803 client item id(s) from .../Resources/ClientItemIds.txt; item export filter is ON`
6. 用出事的账号登录，确认不再弹「同步账号信息时发生错误」；`grep "withheld ItemDB UniqueId=90070000"` 日志应有且仅有 1 条
7. `Schale.dll` 不用换（哈希未变）

---

## 10. 回滚

- **软回滚（不换 DLL）**：把 `Resources/ClientItemIds.txt` 改名或清空 → 下次启动/首次请求时过滤自动关闭，行为回到今天之前，日志有 WARN。
- **硬回滚**：把备份的 `Shittim-Server.dll` 拷回去重启。白名单文件留着无害（旧 DLL 不读它）。
- **数据侧无需回滚**：本次没有任何数据库写入。

---

## 11. 未部署声明

**本次交付未部署、未 SSH、未连接 <SERVER_IP>、未改动任何线上数据库 / nginx / 网桥。**
所有验证均在本机离线完成：只读 `work/ba/data/ExcelDB.db`、发布到本地 `_build_exportfilter/`、在本机跑测试工程。

---

## 附录 A：复现命令

```powershell
# 1) 重新生成白名单（幂等，重跑逐字节相同）
python work\ba\scripts\gen_client_item_ids.py
python work\ba\scripts\gen_client_item_ids.py --check    # 只校验，不写

# 2) 编译
cd work\ba\srv_src
& 'C:\Program Files\dotnet\dotnet.exe' publish Shittim-Server\Shittim-Server.csproj -c Release -o _build_exportfilter --nologo

# 3) 自测（34 项，含编译并驱动真实 ClientItemFilter.cs）
cd ..\..\..
python work\ba\scripts\test_client_item_filter.py

# 4) 只想单独跑 C# 那部分
& 'work\ba\scripts\exportfilter_selftest\bin\Release\net10.0\exportfilter_selftest.exe' enabled
$env:SHITTIM_CLIENT_ITEM_IDS='C:\tmp\missing.txt'
& 'work\ba\scripts\exportfilter_selftest\bin\Release\net10.0\exportfilter_selftest.exe' disabled
```
