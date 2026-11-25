# 外部调研：BA 私服「招募/抽卡界面全红 No LocalizeKey」有没有人踩过同一个坑

- 调研时间：2026-11-19（Asia/Shanghai）
- 调研对象：`com.RoamingStar.BlueArchive` 3.0.2（国服，Unity IL2CPP）+ Shittim-Server 派生私服
- 调研方式：纯联网检索 + 公开源码阅读；**未连接任何服务器，未改动任何本地代码/数据**
- 交付物：本文件（唯一写入物）

---

## 0. 一句话结论

**没有找到直接答案。** 公开互联网上不存在「BA 私服招募界面 No LocalizeKey / DUMMY 页签 / 恒显 1,000」这个具体坑的现成分析、issue、帖子或文档。

但找到 **4 条真正有价值的线索** + **5 条推论级证据**，其中三条足以改变排查方向：

1. 招募界面（banner 列表）在官方实现里**是客户端用本地 `ExcelDB.db` 自己拼的，服务端从不下发**——参考实现里 10006 只回「免费十连历史」，`LoginSync` 里 `ShopGachaRecruitListResponse` 只塞一个空数组，`ShopRecruits` 字段压根不填。
2. `LocalizeGachaShop` 的**真实 schema**（flatc 从客户端 IL2CPP metadata 生成）是 `GachaShopId` + **4 个语义字段 × 5 种语言**，不是「5 组（中,韩）配对」；且**存的是字符串本身，不是 LocalizeKey**。
3. 客户端的**本地化表是按 key 的哈希存行**的；`No LocalizeKey` 是「hash 查不到」的通用兜底——**2026-09-23 日服紧急维护时官方客户端自己就在弹窗上显示过 `No LocalizeKey`**（日文社区一手截图转述），说明它跟招募系统没有绑定关系。
4. `ShopRecruitExcel` 在客户端侧**字段漂移过**（官方往表中间插过两个字段），参考实现因此放弃了按固定偏移 UnPack，改用「按客户端真实 slot 对齐」读取。

> 明确区分：第 1–4 条有源码/文档/社区原文支撑（见 §3）；§4 是我从 schema 推出来的判断，**不是外部来源给出的答案**，请当作待验证假设。

---

## 1. 检索覆盖与负面结果（先说没有）

### 1.1 GitHub 全站 issue/PR 检索（`api.github.com/search/issues`，逐个查询串实跑）

| 查询串 | 命中 | 判定 |
| --- | --- | --- |
| `"LocalizeGachaShop"` | **0** | 无人提过 |
| `"ShopRecruits"` | **0** | 无人提过 |
| `"No LocalizeKey" bluearchive` | **0** | 无人提过 |
| `"LocalizeKey" "blue archive"` | **0** | 无人提过 |
| `"LocalizeGachaShop" OR "GachaShopId"` | **0** | 无人提过 |
| `"costMixTicket"` | **0** | 无人提过（你给的符号名在全网 issue 里 0 命中） |
| `"RecruitPoint" bluearchive shop` | **0** | 无关 |
| `"No LocalizeKey"`（不限 BA） | 23 | **全部无关**：BTD-Mod-Helper、home-assistant 前端、pysnmp、consulo、paranext 等，都是同名 API 的巧合 |

### 1.2 参考实现仓库内检索（`Neoexm/Shittim-Server`，commit `5f3910e`，全仓 1631 个文件）

| 检索 | 命中 | 判定 |
| --- | --- | --- |
| `gacha`（issue/PR） | 1 → PR #33 | 无关（momotalk/shop/event 修复，正文只提 box gacha 索引） |
| `recruit`（issue/PR） | 1 → PR #37 | 无关（账号导入） |
| `banner`（issue/PR） | 1 → issue #13「Is there a way to rerun a past event?」 | 弱相关（谈活动复刻，不谈 UI 文案） |
| `LocalizeGachaShop`（全代码） | 21 处，**全部在 `Schale/FlatData/LocalizeGachaShopExcel.cs` 这个 flatc 生成文件内部**；`Schale/FlatData/` 之外 **0 处引用** | 高价值（见 §3-L4） |
| `ShopRecruits` | 2 处（`NetworkProtocol.cs` 定义、`Loaddata.cs`） | 高价值（见 §3-L2） |

### 1.3 其它代码检索通道（都失败，如实记录）

| 通道 | 结果 |
| --- | --- |
| GitHub Code Search API (`/search/code`) | 需登录鉴权，未授权，**不可用** |
| `grep.app` API | HTTP 429（限流），多次重试均失败 |
| `searchcode.com` API | HTTP 404（服务已停） |
| `platform_search`(github) | 连续 4 次返回空 → 该引擎不可用 |

### 1.4 中文社区

| 目标 | 结果 |
| --- | --- |
| 百度（`BAIDU_API_KEY` 未配置 → 回落 exa） | 只返回官网公告、GameKee 卡池攻略、BannerHistory 排期，**无一条私服相关** |
| 知乎（`ZHIHU_API_KEY` 未配置） | 同上，回落 exa，**无相关** |
| B 站（`platform_search` bilibili） | 工具层 `fetch failed`，未取得结果 |
| 贴吧 / NGA | 未被任何启用引擎索引到相关内容；直接站内检索不可用 |
| 关键词跑过的查询 | 「蔚蓝档案 私服 招募 卡池 不显示」「蔚蓝档案 私服 抽卡界面 空白」「No LocalizeKey 蔚蓝档案」「蔚蓝档案 国服 服务端 模拟器 开源」「gitee 蔚蓝档案 服务端 私服」 |

### 1.5 日文 / 英文 / 韩文

| 查询 | 结果 |
| --- | --- |
| `ブルアカ 私設サーバー ガチャ 表示 されない 募集` | 全部是官方故障/攻略站，**无私服内容**（唯一例外见 §3-L5） |
| `blue archive private server gacha banner not showing localization` | 无相关 |
| `"No LocalizeKey" 蔚蓝档案 / ブルアカ` | **命中**（见 §3-L5），但语境是官方维护事故，不是私服 |
| 韩文（NamuWiki / arca 系） | 仅检索到 2025 年官服被黑事件条目，与本题无关 |

### 1.6 「其他 BA 服务端项目」盘点（都看过，均无相关 issue）

`Neoexm/Shittim-Server`（472★，C#，参考实现，见 §3）、`torikushiii/BlueArchiveAPI`（Shittim 上游，issue 仅 #6「Hello」#8「Help」两条灌水）、`BlueArchiveCN/Anti-Harmony`（已归档，反和谐资源仓）、`asfu222/BlueArchiveLocalizationTools`、`asfu222/BACNLocalizationResources`（国服本地化资源打包）、`delayboy/BlueArchive-Translator`（Steam 端简中汉化，见 §3-L6）。

> **国服（`com.RoamingStar.BlueArchive` / 3.0.2 / RoamingStar）在公开互联网上没有任何服务端、协议、数据表文档。** 这是本次调研最大的结构性空白：国服版本号、表结构、Language 枚举都只有你手上那份客户端能回答。

---

## 2. 「直接答案」判定

我把「直接答案」定义为满足任一条：

- (a) 有人描述过完全相同的症状（招募页内文全红 `No LocalizeKey` + DUMMY 页签 + 恒显 1,000）并给出成因；
- (b) 有人明确写过「招募界面的标题/说明不查 `LocalizeGachaShop`，查的是 X 表」；
- (c) 有人给过「私服让招募界面正常还需要下发/修改什么」的清单。

**三条全部为 0 命中。** §1 的检索覆盖了「如果存在一定在这里」的位置：Shittim-Server 全部 issue/PR + 全部 20 篇 docs + 全仓符号引用、GitHub 全站 issue 搜索、GitHub 组织级仓库盘点、中/日/英三语社区。

---

## 3. 相关线索（按价值排序，每条：来源 + 原文摘录 + 可信度 + 对我们的意义）

### L1 ★★★★★ 招募列表是客户端本地拼的，服务端从不下发

来源：`Shittim-Server/Services/ClientExcelBannerPatchService.cs` L9–L12
<https://github.com/Neoexm/Shittim-Server/blob/5f3910ea44a8798c213ea12a3e85f182194f92c6/Shittim-Server/Services/ClientExcelBannerPatchService.cs#L9-L12>

原文（逐字，含注释符）：

```csharp
    // The "View All Recruitments" list is built client-side from the client's encrypted ExcelDB.db; the server never serves it.
    // Active recruitment rows with an empty GachaBannerPath draw as a blank but still selectable banner, and the empty slot pushes the real ones into a gap.
```

同文件 L12 之后紧接着说明该文件的存在意义：它启动时打开客户端的 `ExcelDB.db`，把空的 `GachaBannerPath` 用「Id 前缀最长的近亲 banner」补上。

- **可信度：高。** 这是可运行参考实现里的一手注释 + 一手代码，且与同仓 docs 互相印证（L3b）。作者是 Steam/国际服私服维护者，踩过的坑比你多。
- **对我们的意义（最重要的一条）：** 如果招募列表/页签是客户端本地渲染的，那么「页签名部分变 DUMMY」「内文全红」这两件事**在服务端侧根本没有可下发的数据能修**——它们只能来自客户端 `ExcelDB.db` 里的行内容，或客户端对某张表的查询路径。这与「`ShopRecruits` 逐字段与官方一致却仍然坏」**完全自洽**：因为那个字段本来就不驱动这个界面。
- 注意边界：L1 讲的是 **Steam/国际服** 版本的实现。国服 3.0.2 是否也这样，需要你自己验证（但你们的抓包已经显示 10006 从不被请求，方向一致）。

### L2 ★★★★★ 参考实现里 10006 只回「免费十连历史」，`ShopRecruits` 字段是空的

来源 a：`Shittim-Server/Core/NetworkProtocol/Handlers/ShopHandler.cs` L42–L61
<https://github.com/Neoexm/Shittim-Server/blob/5f3910ea44a8798c213ea12a3e85f182194f92c6/Shittim-Server/Core/NetworkProtocol/Handlers/ShopHandler.cs#L42-L61>

```csharp
    [ProtocolHandler(Protocol.Shop_GachaRecruitList)]
    public async Task<ShopGachaRecruitListResponse> GachaRecruitList(
        SchaleDataContext db,
        ShopGachaRecruitListRequest request,
        ShopGachaRecruitListResponse response)
    {
        var account = await _sessionService.GetAuthenticatedUser(db, request.SessionKey);

        var recruitHistories = db.GetAccountRecruitHistory(account.ServerId).ToList();
        response.ShopFreeRecruitHistoryDBs = recruitHistories
            .Select(h => new ShopFreeRecruitHistoryDB
            {
                UniqueId = h.UniqueId,
                RecruitCount = h.RecruitCount,
                LastUpdateDate = h.LastUpdateDate
            })
            .ToList();

        return response;
    }
```

来源 b：`Shittim-Server/Core/NetworkProtocol/Handlers/AccountHandler.cs` L520–L523（LoginSync 内嵌子包）
<https://github.com/Neoexm/Shittim-Server/blob/5f3910ea44a8798c213ea12a3e85f182194f92c6/Shittim-Server/Core/NetworkProtocol/Handlers/AccountHandler.cs#L520-L523>

```csharp
        response.ShopGachaRecruitListResponse = new ShopGachaRecruitListResponse
        {
            ShopFreeRecruitHistoryDBs = []
        };
```

来源 c：`Schale/MX/NetworkProtocol/NetworkProtocol.cs` L6676–L6684（协议定义本身，可见 `ShopRecruits` 是可选字段）
<https://github.com/Neoexm/Shittim-Server/blob/5f3910ea44a8798c213ea12a3e85f182194f92c6/Schale/MX/NetworkProtocol/NetworkProtocol.cs#L6676-L6684>

```csharp
    public class ShopGachaRecruitListRequest : RequestPacket
    {
        public override Protocol Protocol { get => Protocol.Shop_GachaRecruitList; }
    }
    public class ShopGachaRecruitListResponse : ResponsePacket
    {
        public override Protocol Protocol { get => Protocol.Shop_GachaRecruitList; }
        public List<ShopRecruitDB>? ShopRecruits { get; set; }
```

`ShopRecruitDB` 字段（同文件 L1849/L1856/L2273 附近）只有 `ShopRecruitId` 一类键，**没有**任何标题/说明/价格文本。

- **可信度：高。** 协议类 + handler + LoginSync 三处一致。
- **对我们的意义：** 一个「招募界面完全正常」的私服实现，**在 10006 和 LoginSync 里都没有下发 `ShopRecruits`**。也就是说：
  - `ShopRecruits` 大概率只承载「购买次数/免费十连状态」这类**状态**，不承载**文案**；
  - 你们「529 条逐字段与官方一致」虽然是好工程，但它**证明不了、也不可能是**这个界面文案的来源；
  - 反过来说：如果你现在往 `ShopRecruits` 里塞了东西而官方抓包里本来是空/不同步的，有可能反而是「多给了」——值得拿你们的 LoginSync 原始包跟官方包在**这个子包是否存在、是否为空**这一层再核一遍（不是逐字段核，是核「该不该有」）。

### L3 ★★★★★ 客户端本地化表按 key 的哈希存行；文案类东西根本不走网络

来源 a：`docs/docs/server/client-patching.md`（参考实现官方文档）
<https://github.com/Neoexm/Shittim-Server/blob/5f3910ea44a8798c213ea12a3e85f182194f92c6/docs/docs/server/client-patching.md>

原文（逐字）：

> The same mechanism covers every other client-local string: rows in the client's localization table are keyed by a hash of the localization key, so patching a row is how you change any UI string that never crosses the wire.

同一文档里 banner 相关两段（逐字）：

> | Banners | the client's `ExcelDB.db` | recruitment banner rows |

> Both are re-applied on every server start, because a client update replaces `ExcelDB.db` and takes them with it.
>
> The client reads that database when it launches, so both need a game relaunch, not just a server restart.

- **可信度：高。** 官方仓库文档，且给出了可操作的补丁机制。
- **对我们的意义：**
  1. 「客户端本地字符串 = 按 key 的哈希查行」——这直接给 `No LocalizeKey` 定了性质：**hash 查不到 → 兜底常量**。这是「查表失败」，不是「表缺行」的同义词，更不是「服务端少发字段」。
  2. 「banner 是靠改客户端 `ExcelDB.db` 的行来做的」——参考实现**从来不用服务端协议去改招募界面**。你们现在的做法（对齐服务端 `ShopRecruits`）在这条线索下方向是偏的。
  3. 「客户端只在启动时读这个库，改完必须重启游戏，不是重启服务端」——如果你们之前改过客户端表，注意这条。

### L4 ★★★★★ `LocalizeGachaShop` 的真实 schema：4 个语义字段 × 5 种语言，且全仓无人消费

来源：`Schale/FlatData/LocalizeGachaShopExcel.cs`（flatc 从客户端 `global-metadata.dat` 生成，21 个字段 / vtable slot 0–20）
<https://github.com/Neoexm/Shittim-Server/blob/5f3910ea44a8798c213ea12a3e85f182194f92c6/Schale/FlatData/LocalizeGachaShopExcel.cs>

原文（逐字，属性声明顺序即 slot 顺序）：

```csharp
  public long GachaShopId { get ... }
  public string TabNameKr { ... }
  public string TabNameJp { ... }
  public string TabNameTh { ... }
  public string TabNameTw { ... }
  public string TabNameEn { ... }
  public string TitleNameKr { ... }
  public string TitleNameJp { ... }
  public string TitleNameTh { ... }
  public string TitleNameTw { ... }
  public string TitleNameEn { ... }
  public string SubTitleKr { ... }
  public string SubTitleJp { ... }
  public string SubTitleTh { ... }
  public string SubTitleTw { ... }
  public string SubTitleEn { ... }
  public string GachaDescriptionKr { ... }
  public string GachaDescriptionJp { ... }
  public string GachaDescriptionTh { ... }
  public string GachaDescriptionTw { ... }
  public string GachaDescriptionEn { ... }
```

建表语句里的 slot 编号（可作为「字段顺序」的硬证据）：

```csharp
  public static void AddGachaShopId(FlatBufferBuilder builder, long gachaShopId) { builder.AddLong(0, gachaShopId, 0); }
  public static void AddTabNameKr(...) { builder.AddOffset(1, ...); }
  public static void AddTabNameJp(...) { builder.AddOffset(2, ...); }
  public static void AddTabNameTh(...) { builder.AddOffset(3, ...); }
  public static void AddTabNameTw(...) { builder.AddOffset(4, ...); }
  public static void AddTabNameEn(...) { builder.AddOffset(5, ...); }
  ... TitleName* = slot 6..10, SubTitle* = slot 11..15, GachaDescription* = slot 16..20
```

- **可信度：高（结构层面）。** 这是编译器生成的代码，不是人写的注释；字段名和 slot 号来自客户端 metadata，不是猜的。
- **对我们的意义（直接回答你列的问题 2）：**
  - **不存在「5 组（中文,韩文）配对」。** 真实结构是 **4 个语义字段 × 5 个语言槽位 = 20 个字符串** + 1 个 `GachaShopId`。
  - 语义顺序（也就是你说的「槽位是干什么的」）：
    | 语义 | 字段 | slot |
    | --- | --- | --- |
    | 页签名 | `TabName*` | 1–5 |
    | 标题 | `TitleName*` | 6–10 |
    | 副标题 | `SubTitle*` | 11–15 |
    | 招募说明 | `GachaDescription*` | 16–20 |
  - 语言槽位顺序固定为 **Kr, Jp, Th, Tw, En**（注意：**没有 Cn**，且 **Tw 在 En 前**）。国服客户端如果是 6 语言（含 Cn）或顺序不同，**整表的字符串会被按错位读**——但错位读的结果是「读到别的语言的正常文案」或乱码，**不会**是 `No LocalizeKey`。这条恰好可以用来排除某些假设。
  - 你在表里看到的「5 段文案」很可能就是把这 4 组里某一组的 5 个语言槽位当成了「5 组」；建议按上表重新对齐一次列义。
  - **该表在参考实现全仓 0 处被服务端读取**（我跑过 `grep`，`Schale/FlatData/` 外 0 命中）。→ 服务端**不可能**通过它影响界面；只有客户端读它。

### L5 ★★★★ 官方客户端自己也会显示 `No LocalizeKey`（2026-09-23 日服紧急维护）

这是本次调研唯一一条「同一个报错串、真实场景、有原文」的线索，但语境是官方维护事故，**不是私服**。

来源 a：日文博客「ブルアカで「No LocalizeKey」と表示される原因と対処法を解説」
<https://smhradio-hp.com/4320.html>

原文（搜索结果摘要逐字；该页正文为 JS 渲染，我多次抓取只拿到标题，**以下是摘要原文，非我改写**）：

> ブルアカを起動したときに「No LocalizeKey」という見慣れない文字が表示されると、アプリが壊れたのではないか、自分のスマホだけで問題が起きているのではないかと不安になりやすいところです。ただし、同じタイミングで多くの利用者がログインできなくなり、運営側で緊急メンテナンスが行われている場合は、端末を何度も操作して直そうとするより、まず運営からのお知らせを確認することが大切です。

来源 b：推特趋势聚合「緊急メンテナンス｜トレログ」（2026-09-23，收录当日推文原文）
<https://trends-log.com/2c84a281782938478>

原文（逐字，多条）：

> これtexttex………のしたに緊急メンテナンスって書いてあったわ

> 緊急メンテナンス中の文字の位置調整の確認用の仮テキストのtext...そのままなんかな 一応緊急メンテで終了未定っていう内容自体は読めるし

> 実際の緊急メンテナンスのお知らせ（緊急メンテナンス、日時、お知らせ、OK）とポップアップメッセージのフォーマット（texttext... 、No LocalizeKey、OK）が重なっているんじゃないかと考えています チェックをつけると真ん中のOKが押せるようになるんですよ（？）

> 通知のダミーテキストが緊急メンテナンスの上に来てるのもなんなんだろうね

背景（同一页面）：2026-09-23 20:35 起日服紧急维护（艾莉娜武器强化素材 bug），登录时的公告弹窗出现排版错乱——占位文本 `texttext...` 与 `No LocalizeKey` 同时出现，真正的「緊急メンテナンス」文字被压在下面。

- **可信度：中—高。** 一手是玩家截图（推文，图片未取），转述页是趋势聚合站（二手）。但多条独立推文 + 一个 SEO 博客都在描述同一现象，且时间/原因可对上官方维护。
- **对我们的意义：**
  1. `No LocalizeKey` **是客户端全局通用兜底**，任何「该有本地化文本但没取到」的位置都会显示它——弹窗正文会、招募页内文也会。它**不是招募系统专属**，也不代表表坏了。
  2. 官方环境下的成因是**服务端下发的公告缺少/错配了本地化内容**，客户端只能兜底。映射到你们：招募页内文走的很可能也是「服务端/配置给出一个 key 或标识 → 客户端按 hash 查本地化 → 查不到 → 兜底」。**这条把「10006/ShopRecruits 字段值不对」这个假设进一步削弱，把「客户端拿到的 key/标识与本地表对不上」这个假设抬高。**
  3. 顺带一个可用事实：**占位文本（`texttext...`、`No LocalizeKey`）会与真实内容同时渲染、互相压字**——说明客户端在「取不到文本」时是**保留原占位**而不是清空。所以你们看到的红色 `[FF0000]No LocalizeKey` 是「该槽位取不到」的稳定表现，不是随机渲染错误。

### L6 ★★★ 中文社区一手材料：官方客户端只有 Kr/Jp/Th/Tw/En，简中挂 Tw 分支

来源：`delayboy/BlueArchive-Translator`（Steam 端简中汉化，README 中文，2026-11-16 更新）
<https://github.com/delayboy/BlueArchive-Translator>

原文（逐字）：

> Steam 版《蔚蓝档案》客户端原生仅支持 `Kr / Jp / Th / Tw / En` 五种语言（见 `dump.cs` 中 `Language` 枚举），**没有简体中文（Cn）**

> 游戏将简中渲染挂在 `Language.Tw` 分支，字形使用 `NotoSansTC-Medium/Bold.otf`，因此简体字会以繁体字形显示（生硬、缺字）。

同 README 还给出与本问题直接相关的加密链（逐字）：

> | FlatBuffer `.bytes` XOR | `MT19937(xxh32(name))` | FlatBuffer 类名（公开） | 否，公开字符串即可 |

- **可信度：中—高。** 国人逆向项目，README 有具体函数地址、密钥派生表、bundle 名，细节密度高（不是水贴）；但**对国服不适用**（它讲的是 Steam 国际服 5 语言版）。
- **对我们的意义：**
  - 佐证 L4 的「5 个语言槽 = Kr/Jp/Th/Tw/En」不是巧合，是客户端 `Language` 枚举的固定顺序。
  - **国服客户端的 `Language` 枚举几乎肯定多一个 `Cn`**（甚至顺序不同）。这意味着：**任何按「5 语言固定槽位」写死的服务端代码/表读取逻辑，在国服上都会错位**。这条对你们「表逐位一致却仍不对」是一个可能解释：**表对了，但读表的列索引/语言索引假设错了**。
  - 该仓库还提供了国服方向的可复用工具链（`asfu222/BlueArchiveLocalizationTools` 明确支持 `jp, gl, cn` 三服解包/封包；见 <https://github.com/asfu222/BlueArchiveLocalizationTools>）。

### L7 ★★★ 运营性线索：机器上通常有三份 `ExcelDB.db`，必须一致

来源：`docs/docs/server/excel-data.md`
<https://github.com/Neoexm/Shittim-Server/blob/5f3910ea44a8798c213ea12a3e85f182194f92c6/docs/docs/server/excel-data.md>

原文（逐字）：

> There are normally three copies of `ExcelDB.db` on a machine, and they have to agree:

> | `Resources/Dumped/ExcelDB.db` | what the server reads |
> | `Resources/Downloaded/ExcelDB.db` | what the resource loader restores from |
> | `BlueArchive_Data/StreamingAssets/PUB/Resource/Preload/TableBundles/ExcelDB.db` | what the client reads |

> A change written to fewer than all three drifts back the next time one is copied over another.

- **可信度：高。**
- **对我们的意义：** 你验证的是「客户端本地表与官方 `TableManifest` 逐位一致（160,534,528 B / md5 `824ce3a8…`）」。请确认这个 md5 是**客户端实际读取的那一份**（`…/Preload/TableBundles/ExcelDB.db`），而不是 `Resources/Dumped/` 里的服务端副本。三份里任何一份被改过（比如被某个 patcher 洗过），都会表现为「客户端数据看起来对、行为不对」。

### L8 ★★★ `ShopRecruitExcel` 在客户端侧漂移过——客户端往表中间插过两个字段

来源：`Shittim-Server/Services/ClientExcelBannerPatchService.cs` L65–L67
<https://github.com/Neoexm/Shittim-Server/blob/5f3910ea44a8798c213ea12a3e85f182194f92c6/Shittim-Server/Services/ClientExcelBannerPatchService.cs#L65-L67>

原文（逐字）：

```csharp
            // ShopRecruitExcel has drifted - the client inserted two fields mid-table since the models were generated - so a straight UnPack walks a later field's offset into the middle of another one and throws.
            var slots = ClientExcelSchema.RowSlots(typeof(ShopRecruitExcelT), "ShopRecruitExcel");
```

配套文档 `excel-data.md` 原文（逐字）：

> Field order in the client's schema moves between versions, and a table read at the wrong offsets decodes into plausible-looking nonsense rather than failing.

- **可信度：高。** 作者是踩了这个坑之后写的补丁服务。
- **对我们的意义：** 「按类定义顺序 UnPack」在 BA 表上是**不可靠的**，会「解出看似合理其实是别的字段的值」——这恰好能解释「十连按钮恒显示 `1,000`」这种**看起来像正确数字、其实取错字段**的症状。你们如果自己写了解表脚本验证 `LocalizeGachaShop`/`ShopRecruit`，务必按客户端真实 slot 读，而不是按 flatc 类顺序。

### L9 ★★ 「商店类 UI 名字走 `LocalizeEtc`」是这个游戏里真实存在的另一种取文案方式

来源：`Schale/FlatData/ShopExcel.cs` 与 `Schale/FlatData/LocalizeEtcExcel.cs`
<https://github.com/Neoexm/Shittim-Server/blob/5f3910ea44a8798c213ea12a3e85f182194f92c6/Schale/FlatData/ShopExcel.cs>
<https://github.com/Neoexm/Shittim-Server/blob/5f3910ea44a8798c213ea12a3e85f182194f92c6/Schale/FlatData/LocalizeEtcExcel.cs>

原文（逐字）：

```csharp
// ShopExcelT
  public long Id { get; set; }
  public uint LocalizeEtcId { get; set; }
  public Schale.FlatData.ShopCategoryType CategoryType { get; set; }
```

```csharp
// LocalizeEtcExcelT
  public uint Key { get; set; }
  public string NameKr { get; set; }
  public string DescriptionKr { get; set; }
  ... NameJp/DescriptionJp, NameTh/DescriptionTh, NameTw/DescriptionTw, NameEn/DescriptionEn
```

同类「纯 key + 5 语言」表还有 `LocalizeExcelT`（`Key` + `Kr/Jp/Th/Tw/En` 单列）与 `LocalizeCodeInBuildExcelT`（同构）。

- **可信度：高（schema 层面）。**
- **对我们的意义：** 你问「标题/说明会不会查别的表」——**结构上存在这条路径**：`ShopExcel.LocalizeEtcId` → `LocalizeEtc.Key`。若招募页内文复用商店的取文案逻辑，那么内文来自 `LocalizeEtc`（按 `Key`），而**不是** `LocalizeGachaShop`。这与 L1/L5 拼在一起，构成一个自洽假设：**页签名走 `LocalizeGachaShop.TabName`（本地字面量，所以能显示），内文走 `LocalizeEtc`/`LocalizeExcel`（按 key 的 hash 查行，查不到 → `No LocalizeKey`）**。
- 注意：**这一步是结构证据，不是有人明确说过「招募内文查 LocalizeEtc」。** 见 §4。

### L10 ★★ 无关但值得记录的相邻事实（避免你们重复踩）

- `GachaCombinedCostExcel`（`GroupId/Priority/ConsumeGachaTicketType(+Amount)/ConsumeParcelType/Id/Amount`）与 `GoodsExcel`（`ConsumeParcelType/Id/Amount`、`ConsumeGachaTicketType/Amount`、`CombinedGachaCostId`）是**本地表**里「一次抽卡要花多少」的定义处；`ShopRecruitExcel` 里只有 `OneGachaGoodsId` / `TenGachaGoodsId` / `RecruitCoinId` 这些**外键**，没有价格数字。→ 按钮上的 `1,000` 只可能来自本地 `GoodsExcel`/`GachaCombinedCostExcel`（或客户端拿错字段，见 L8），**不可能来自 `ShopRecruits` 下发值**。可信度：高（schema 事实）。
- `ShopTabGroupExcel`（`Id/ShopGroupType/DisplayOrder/ShopCategoryTypes[]`）与 `ShopInfoExcel`（`CategoryType/CostParcelType[]/GoodsId[]/IsShopVisible/DisplayOrder/…`）没有任何名字文本字段——**页签名不在这些表里**，只能来自 `LocalizeGachaShop.TabName*` 或本地化表。可信度：高（schema 事实）。
- 参考实现 docs 提到 `TableCatalog.bytes` 里有 Size/CRC 校验（见 L6 引用的汉化项目 README：`TableCatalog.bytes` 中 Size/CRC + bundle 整体 CRC）。**改客户端表会被完整性校验打到**，这是「改客户端」路线的主要成本。可信度：中—高。

---

## 4. 我从上面这些事实推出来的判断（**不是外部来源的答案，请当假设验证**）

> 这一节没有任何外部来源支撑「结论」本身，只有 §3 的 schema/文档做前提。请按假设对待。

**H1（最强）｜内文 `No LocalizeKey` 与 `LocalizeGachaShop` 缺行无关。**
`LocalizeGachaShop` 存的是**字符串本身**（L4），不是 key；`No LocalizeKey` 是**按 key 的 hash 查不到**的兜底（L3/L5）。两者机制不同。→ 你在 `LocalizeGachaShop` 里「532 个 id 全部有行、5 段文案齐全」这件事，**在逻辑上无法**修掉内文的红字。
**一分钟判别法**：dump 一行 `LocalizeGachaShop` 的 `TitleNameTw`（或国服对应列），看它是**中文句子**还是 `GachaShop_Title_1001` 这种标识符。
- 是句子 → H1 成立，去查 `LocalizeExcel`/`LocalizeEtc`（按 key）。
- 是标识符 → 那么该列是 key，必须在 `LocalizeExcel`/`LocalizeEtc` 里按 hash 找到对应行；找不到就是你们看到的红字。

**H2｜页签 `DUMMY` 是表里的字面文本，不是渲染失败。**
「部分页签正常、部分是 DUMMY」这种**混合状态**最自然的解释是：那些行在表里的 `TabName*` 字面就是 `DUMMY`（官方表里给占位/未启用卡池留的 dummy 行）。而客户端把「本地表里所有可见 banner 行」都列成页签（L1），于是占位行也被列了出来。
→ 若成立：应能把「显示 DUMMY 的页签」与「`LocalizeGachaShop`/`ShopRecruit` 里某个占位标记（如 `GoodsDevName` 含 DUMMY、`IsLegacy=true`、`SalePeriodFrom/To` 为空、`DisplayTag=None`）一一对上。这是一次纯本地表的 join 验证，成本很低。

**H3｜恒显 `1,000` 是「取错字段」或「取到默认值」，而不是钱包没读对。**
钱包余额与按钮价是两条路径（L10：价格在 `GoodsExcel.ConsumeParcelAmount` / `GachaCombinedCostExcel`）。「111 万青辉石仍显示 1,000」说明客户端读到的不是「应付金额」而是某个**常量/占位/错位字段**（L8 的 field drift 正好会产生这种「看起来合理的数字」）。
→ 建议在客户端侧确认 `1,000` 是否等于某张表里某个**与十连无关**的字段值（例如 `GachaElementExcel.Prob`、`ConsumeGachaTicketTypeAmount`、某个 `DisplayOrder×1000`）。

**H4｜国服多语言槽位可能是错位来源，但错位不会产生 `No LocalizeKey`。**
L6 说明官方 5 语言枚举是 Kr/Jp/Th/Tw/En，国服大概率多 `Cn`。槽位错位的结果是「读到另一种语言」或乱码，**不是**兜底常量。→ 所以「槽位错位」可以解释「文案语言不对」，**不能**解释你现在的症状；不要把它当主因。

---

## 5. 明确没找到的东西（不要在这上面再花时间搜了）

1. 没有任何人写过「招募界面的标题/说明不查 `LocalizeGachaShop`，查的是 X 表」——**零命中**。§4-H1 是我从 schema 推的。
2. 没有任何人公开过 `LocalizeGachaShop` 的「5 组语义」说明（除 flatc 生成代码本身，即 L4）。
3. 没有任何私服/单机/离线版的 `No LocalizeKey` 成因贴（中文、日文、英文、韩文均无）。
4. 没有任何「私服让招募界面正常还需要下发什么」的清单或教程——连 Shittim-Server 的 docs 都没写招募界面，只在 `control-center/gacha.md` 写了掉率与 banner 只读展示（原文：`Banners are defined in the game's Excel data, so the only way to change one is to edit that data`）。
5. 国服 `com.RoamingStar.BlueArchive` 3.0.2 **无任何公开资料**（无协议文档、无表结构、无服务端）。
6. 没有任何关于 `costMixTicketAmountLabel` / `SetGachaCost` 的公开资料——这两个符号全网（issue 检索 + 代码索引可达范围内）**0 命中**，只存在于你们自己的客户端逆向产物里。

---

## 6. 建议的下一步（按性价比排序，全部是本地/离线动作）

1. **验证 H1（10 分钟，最高优先）**：dump 一行 `LocalizeGachaShop`，判断列里是文案还是 key。这一步决定后面所有方向。
2. **验证 H2（20 分钟）**：把「显示 DUMMY 的页签 id」与 `ShopRecruit`/`LocalizeGachaShop` 里带占位标记的行 join 一次。
3. **核对三份 `ExcelDB.db`（5 分钟）**：确认 md5 `824ce3a8…` 那份是客户端真正读的那份（L7）。
4. **重新审视 `ShopRecruits` 的「该不该有」**：参考实现的正常私服**不发**这个字段（L2）。先确认官方包里该子包是「不存在 / 空数组 / 有 529 条」，再决定要不要继续对齐它。
5. **如果最终确认必须改客户端表**：参考实现的做法是启动时写 `ExcelDB.db` 的行（L1/L3），并且要处理 `TableCatalog.bytes` 的 Size/CRC（L10 末条）。这比对齐协议更接近「有人已经走通的路」。

---

## 7. 检索式留档（便于日后复查/换引擎重跑）

```
GitHub issues:
  "LocalizeGachaShop"                                  -> 0
  "ShopRecruits"                                       -> 0
  "No LocalizeKey" bluearchive                         -> 0
  "LocalizeKey" "blue archive"                         -> 0
  "LocalizeGachaShop" OR "GachaShopId"                 -> 0
  "costMixTicket"                                      -> 0
  repo:Neoexm/Shittim-Server gacha|recruit|banner|shop -> 4 条，全无关
中文:
  蔚蓝档案 私服 招募 卡池 不显示 / 私服 抽卡界面 空白 / No LocalizeKey 蔚蓝档案
  蔚蓝档案 国服 服务端 模拟器 开源 / gitee 蔚蓝档案 服务端 私服
日文:
  ブルアカ 私設サーバー ガチャ 表示 されない 募集
  "No LocalizeKey" ブルアカ            -> 命中官方维护事故（L5）
英文:
  blue archive private server gacha banner not showing localization
```

---

## 8. 引用清单

**一手源码/文档（参考实现，commit `5f3910ea44a8798c213ea12a3e85f182194f92c6`）**

1. <https://github.com/Neoexm/Shittim-Server> — Blue Archive Private Server For Steam（C#，472★）
2. <https://github.com/Neoexm/Shittim-Server/blob/5f3910ea44a8798c213ea12a3e85f182194f92c6/Shittim-Server/Services/ClientExcelBannerPatchService.cs#L9-L12> — L1
3. <https://github.com/Neoexm/Shittim-Server/blob/5f3910ea44a8798c213ea12a3e85f182194f92c6/Shittim-Server/Core/NetworkProtocol/Handlers/ShopHandler.cs#L42-L61> — L2
4. <https://github.com/Neoexm/Shittim-Server/blob/5f3910ea44a8798c213ea12a3e85f182194f92c6/Shittim-Server/Core/NetworkProtocol/Handlers/AccountHandler.cs#L520-L523> — L2
5. <https://github.com/Neoexm/Shittim-Server/blob/5f3910ea44a8798c213ea12a3e85f182194f92c6/Schale/MX/NetworkProtocol/NetworkProtocol.cs#L6676-L6684> — L2
6. <https://github.com/Neoexm/Shittim-Server/blob/5f3910ea44a8798c213ea12a3e85f182194f92c6/Schale/FlatData/LocalizeGachaShopExcel.cs> — L4
7. <https://github.com/Neoexm/Shittim-Server/blob/5f3910ea44a8798c213ea12a3e85f182194f92c6/Schale/FlatData/ShopRecruitExcel.cs> — 33 字段，无任何文案字段
8. <https://github.com/Neoexm/Shittim-Server/blob/5f3910ea44a8798c213ea12a3e85f182194f92c6/Schale/FlatData/ShopExcel.cs> — `LocalizeEtcId`，L9
9. <https://github.com/Neoexm/Shittim-Server/blob/5f3910ea44a8798c213ea12a3e85f182194f92c6/Schale/FlatData/LocalizeEtcExcel.cs> — L9
10. <https://github.com/Neoexm/Shittim-Server/blob/5f3910ea44a8798c213ea12a3e85f182194f92c6/Schale/FlatData/GoodsExcel.cs> — L10
11. <https://github.com/Neoexm/Shittim-Server/blob/5f3910ea44a8798c213ea12a3e85f182194f92c6/docs/docs/server/client-patching.md> — L3
12. <https://github.com/Neoexm/Shittim-Server/blob/5f3910ea44a8798c213ea12a3e85f182194f92c6/docs/docs/server/excel-data.md> — L7/L8
13. <https://github.com/Neoexm/Shittim-Server/blob/5f3910ea44a8798c213ea12a3e85f182194f92c6/docs/docs/control-center/gacha.md> — 「banner 只能改客户端 Excel 数据」

**社区 / 第三方**

14. <https://smhradio-hp.com/4320.html> — 日文：「No LocalizeKey」原因与对策（仅取到摘要，正文 JS 渲染未能抓取）— L5
15. <https://trends-log.com/2c84a281782938478> — 2026-09-23 日服紧急维护推文聚合，含 `No LocalizeKey` 一手转述 — L5
16. <https://github.com/delayboy/BlueArchive-Translator> — Steam 端简中汉化，5 语言枚举 / 表加密链 / 完整性校验 — L6/L10
17. <https://github.com/asfu222/BlueArchiveLocalizationTools> — 支持 jp/gl/**cn** 三服 Excel 解包/封包
18. <https://github.com/asfu222/BACNLocalizationResources> — 国服本地化资源打包（README 指向）
19. <https://github.com/torikushiii/BlueArchiveAPI> — Shittim 上游（issue 无相关内容）

**负面证据（可复核）**

20. <https://api.github.com/search/issues?q=%22LocalizeGachaShop%22>
21. <https://api.github.com/search/issues?q=%22ShopRecruits%22>
22. <https://api.github.com/search/issues?q=%22No+LocalizeKey%22+bluearchive>
23. <https://api.github.com/search/issues?q=%22costMixTicket%22>

---

## 9. 本次调研做不到的事（工具/额度限制，如实记录）

- 百度、知乎：本会话未配置 `BAIDU_API_KEY` / `ZHIHU_API_KEY`，这两个中文主入口**实际未检索**（所有「中文结果」都是 exa 代跑）。
- Tavily：当日免 key 额度耗尽（HTTP 429）。
- Perplexity：未配置 key。
- B 站 `platform_search`：工具层 `fetch failed`。
- grep.app（HTTP 429）、searchcode（HTTP 404）、GitHub Code Search（需鉴权）：**公开代码全文检索全部不可用**，因此「全网有没有别人的 BA 服务端代码里出现过 `LocalizeGachaShop`」这一点我**没有能力下结论**，只能确认「issue/PR 层面 0 命中」。
- Shittim-Server Discord 社群（<https://discord.gg/GANwPn9xX6>，仓库主页挂着）：**不可索引**，最可能藏着真正的答案。若你能进，直接问「recruit UI shows No LocalizeKey, is the banner list client-side?」比任何检索都有效。
