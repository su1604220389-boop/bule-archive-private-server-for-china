# BA 私服 · 官方 109 条 RPC（38 协议）实现盘点

- 审计对象：`work/ba/server/` 与 `work/ba/server/_bridge_ref/`、`work/ba/server/prototype/_scratch/`、`work/ba/proto/build_response.py`
- 方式：只读。用 Python 直接 import `response_factory` / `protocol_router`，把 38 条协议逐条喂给 `route()`、`build_with_stats()`，并带 `proto/account_state.seeded.json` 当账号状态跑了一遍（不联网、不写任何文件）。
- 结论口径（先看这四条）：
  1. **没有任何一条协议写了业务逻辑**（发奖、扣费、改状态、列表内容）。全仓没有 `handle_<协议>` / `build_<协议>_response` 之类的逐协议函数（详见第 4 节）。
  2. **通用层（router + factory）能给出 35/38 条的结构合法响应**；剩下 3 条（`3` / `8006` / `36001`）连 Response DTO 都没有。
  3. 真正的“手写”只有 4 处，都在 `account_auth_probe.py` 里：`1002`（响应体构造器）、`1017/1019`、`24000`、`90004`。
  4. **注意版本差异**：`_bridge_ref/account_auth_probe.py`（1125 行）是旧副本；`report/_tmp/sandbox292/account_auth_probe.py`（1290 行）多了一个 `292_24000_official` managed block（408-577 行），把 `24000` 换成了**官方抓包模板驱动**的实现（`work/ba/proto/academy_24000_official.json`，71 个 `ZoneVisitCharacterDBs` 键 / 9 条 `AcademyLocationDBs`），由 `scripts/292_24000_official.py` 注入部署。第 1 节 `24000` 行按**新版**记级别，并同时标出旧版位置。

缩写约定（下文“位置”列都用这个）：
- `probe:` = `work/ba/server/_bridge_ref/account_auth_probe.py`
- `router:` = `work/ba/server/protocol_router.py`
- `factory:` = `work/ba/server/response_factory.py`
- `svc:` = `work/ba/server/account_service.py`

---

## 第 1 节：逐协议实现状态表

> 「实现级别」按题目定义取四档之一。注意：`通用兜底` 指“结构能出、值靠 schema 默认 + 状态绑定”，不含任何业务语义。

| 协议号 | 协议名 | 手写实现？ | 位置（文件:行号 + 函数名） | 实现级别 | 备注 |
|---|---|---|---|---|---|
| 3 | NetworkTime_Sync | 否 | `probe:643-716 _generic_protocol_response`（else 分支 703-714）；`router:444 route()` 侧无 DTO | 通用兜底 | `protocol_map.json` 里 `id=null`、`resp=null`、`req=NetworkTimeSyncRequest`；schema 709 个类型里没有 `NetworkTimeSyncResponse`（连近似名都没有）。router 侧返回 Error 信封，只有 bridge 能靠 `Hash>>32` 回 7 键最小包 |
| 1002 | Account_Auth | **是** | `probe:1033-1051 _bridge` path B；响应体构造器 `_bridge_ref/cn_inner27.py:41-128 build()`，在 `probe:737-758` 使用 | **完整手写** | 注意：默认（`exp=''`）`_bridge:1033` 是把 `{"Protocol":"Account_Auth","SessionKey":sk}` POST 到 `127.0.0.1:5000/api/gateway`，再把官方回包重新封包 → 默认路径其实是“只转发”。`cn_inner27.build()` 只在 `cn_wrap_mode=a_proto_int/b_proto_str` 时用，给 27 个声明字段 + 22 字段 AccountDB（Nickname/EncryptedUID 为常量） |
| 1005 | Account_GetTutorial | 否 | `router:444` + `factory:961` → `AccountGetTutorialResponse`（8 键） | 通用兜底 | 名字在 `probe:70-84 BUILTIN_NAMES` 里 → bridge 走 `probe:1103` 的“认得但没专属分支”，回 `_generic_protocol_response` 的 7 键最小包（703-714）；只有 path A 解过密（有 `req_Hash`）时才会回 `cn_nick.build_min_response` 的 `{"Protocol":1005}`。另：`official_probe.py:94` 把 1005 记成 `Account_BirthDay`，与 protocol_map / 抓包口径冲突，那张表不可信 |
| 1017 | Account_LoginSync | **是（桩）** | `probe:696-702 _generic_protocol_response`（`num in (1019,1017)`） | 桩/空包 | 只出 `{Protocol, ServerTimeTicks, ServerNotification, 4 个空集合, Responses:[], SkillCutInOption:""}`。国服实发 **1019**、protocol_map 是 1017（无别名注册，`router:78 ID_ALIASES={}`）。通用层 `AccountLoginSyncResponse` 有 37 键，但 `Responses` 恒空（`factory:208 NEVER_EMIT` 排除；实测 `len(Responses)==0`）→ 客户端拿不到任何同步内容 |
| 4000 | Item_List | 否 | `router:444` + `factory:961` → `ItemListResponse`（9 键） | 通用兜底 | `ItemDBs`/`ExpiryItemDBs` 由 `factory:157-180 LIST_BINDINGS['ItemDB']→items` 绑定；实测注入 1 条 items 后 `ItemDBs` 有 1 条（按字段名逐键绑定，名字不符的键被丢） |
| 5000 | Echelon_List | 否 | `router:444` + `factory:961` → `EchelonListResponse`（9 键） | 通用兜底 | `EchelonDBs ← state.echelons`（`LIST_BINDINGS['EchelonDB']`）；`ArenaEchelonDB` 是 object 类型，未绑定时出全默认对象 |
| 5001 | Echelon_Save | 否 | `router:444` + `factory:961` → `EchelonSaveResponse`（8 键） | 通用兜底 | `protocol_map.resp=null`，靠 `proto/protocol_extras.json` 恢复（`router:324 dto_for` extras 分支）；route 会带一条 warning |
| 6000 | Campaign_List | 否 | `router:444` + `factory:961` → `CampaignListResponse`（10 键） | 通用兜底 | 3 个历史列表里只有 `StageHistoryDBs ← CampaignStageHistoryDB`、`StrategyObjecthistoryDBs ← StrategyObjectHistoryDB` 有绑定；`CampaignChapterClearRewardHistoryDBs` 没有绑定 → 恒 `[]` |
| 6020 | Campaign_EnterMainStageStrategySkip | 否 | `router:444` + `factory:961` → `CampaignEnterMainStageStrategySkipResponse`（8 键） | 通用兜底 | DTO 自有字段只有 1 个，但基类链展开后 8 键 |
| 6021 | Campaign_MainStageStrategySkipResult | 否 | `router:444` + `factory:961` → `CampaignMainStageStrategySkipResultResponse`（13 键） | 通用兜底 | 带 state 跑时 bound=163、非空叶子 111；同为结构级，没有发奖/结算逻辑 |
| 7000 | Mail_List | 否 | `router:444` + `factory:961` → `MailListResponse`（9 键） | 通用兜底 | **硬伤**：`LIST_BINDINGS` 里没有 `MailDB` → `MailDBs` 恒 `[]`、`Count` 恒 0。要出邮件必须新写绑定或手写 |
| 7001 | Mail_Check | 否 | `router:444` + `factory:961` → `MailCheckResponse`（8 键） | 通用兜底 | 无 mail 状态可绑（state 里没有 mail 列表） |
| 7003 | Mail_ListSemiPermanent | 否 | `router:444` + `factory:961` → `MailListSemiPermanentResponse`（9 键） | 通用兜底 | 同 7000 |
| 8000 | Mission_List | 否 | `router:444` + `factory:961` → `MissionListResponse`（11 键） | 通用兜底 | `protocol_map.resp=null`，靠 extras 恢复；`MissionProgressDBs ← state.missionProgress`（`LIST_BINDINGS['MissionProgressDB']`），实测注入后能出条目 |
| 8002 | Mission_MultipleReward | 否 | `router:444` + `factory:961` → `MissionMultipleRewardResponse`（9 键） | 通用兜底 | 领奖语义完全没有（不改状态、不校验） |
| 8006 | Mission_GuideMissionSeasonList | 否 | 无 DTO：`router:444` → `router:429 _error_spec` | 通用兜底 | **router 侧 Error 信封**（`protocol_map`: `resp=null`、`dto_match="none/none"`；extras 没有；schema 无同名 DTO）。bridge 侧靠 `probe:703-714` 回最小包，外层 protocol 值是 `'Unknown'` |
| 10002 | Shop_List | 否 | `router:444` + `factory:961` → `ShopListResponse`（9 键） | 通用兜底 | `LIST_BINDINGS` 里没有 `ShopInfoDB`/`ShopEligmaHistoryDB` → `ShopInfos` 恒 `[]`（state 里 shop 有 2 条也填不进去） |
| 15002 | OpenCondition_EventList | 否 | `router:444` + `factory:961` → `OpenConditionEventListResponse`（9 键） | 通用兜底 | — |
| 16000 | Toast_List | 否 | `router:444` + `factory:961` → `ToastListResponse`（8 键） | 通用兜底 | — |
| 20001 | Cafe_Ack | 否 | `router:444` + `factory:961` → `CafeAckResponse`（8 键） | 通用兜底 | `CafeDB ← state.cafe.cafes[0]`（`OBJECT_BINDINGS`），实测 bound=18 |
| 20013 | Cafe_ReceiveCurrency | 否 | `router:444` + `factory:961` → `CafeReceiveCurrencyResponse`（10 键） | 通用兜底 | 收币语义没有；bound=134（绑定生效） |
| 22000 | Arena_EnterLobby | 否 | `router:444` + `factory:961` → `ArenaEnterLobbyResponse`（12 键） | 通用兜底 | `ArenaPlayerInfoDB ← state.arena.playerInfo`，bound=11 |
| 22004 | Arena_EnterBattle | 否 | `router:444` + `factory:961` → `ArenaEnterBattleResponse`（13 键） | 通用兜底 | bound=368，但有 warning：`Battle.StageTopographyChanged` 的类型 `EventHandler` 不在 schema → 出 `{}` |
| 22008 | Arena_CumulativeTimeReward | 否 | `router:444` + `factory:961` → `ArenaCumulativeTimeRewardResponse`（10 键） | 通用兜底 | — |
| 22009 | Arena_DailyReward | 否 | `router:444` + `factory:961` → `ArenaDailyRewardResponse`（9 键） | 通用兜底 | 领奖语义没有 |
| 22016 | Arena_SyncEchelonSettingTime | 否 | `router:444` + `factory:961` → `ArenaSyncEchelonSettingTimeResponse`（8 键） | 通用兜底 | — |
| 24000 | Academy_GetInfo | **是** | 新版：`report/_tmp/sandbox292/account_auth_probe.py:408-577`（managed block）+ `:856-860`（分支），`_academy_24000_build:456-554`；旧版：`probe:685-695`；通用层 `AcademyGetInfoResponse`（9 键） | **完整手写** | 新版按官方抓包模板 `academy_24000_official.json` 渲染（71 个 ZoneVisitCharacterDBs 键、9 条 AcademyLocationDBs，只有 SessionKey/ServerTimeTicks/RequestId/AccountId 是动态的；`LastUpdate` 固定 `2026-11-16T04:00:06.479`）；模板缺失时退化成 7 键最小体。**旧副本 `_bridge_ref` 里仍是 9 键桩**：`AcademyDB{LastUpdate, ZoneVisitCharacterDBs:[], ZoneScheduleGroupRecords:{}}` + `AcademyLocationDBs: []`。通用层不带 academy 状态（`account_state.seeded.json` 里没有 `academy` 键） |
| 25003 | Event_RewardIncrease | 否 | `router:444` + `factory:961` → `EventRewardIncreaseResponse`（8 键） | 通用兜底 | — |
| 26000 | ContentSave_Get | 否 | `router:444` + `factory:961` → `ContentSaveGetResponse`（10 键） | 通用兜底 | `ContentSweepPresetDB` 有 object 绑定 |
| 28000 | Clan_Lobby | 否 | `router:444` + `factory:961` → `ClanLobbyResponse`（12 键） | 通用兜底 | `ClanDB`/`ClanMemberDB` 有绑定，bound=19 |
| 28019 | Clan_Check | 否 | `router:444` + `factory:961` → `ClanCheckResponse`（7 键） | 通用兜底 | — |
| 29002 | Billing_PurchaseListByYostar | 否 | `router:444` + `factory:961` → `BillingPurchaseListByYostarResponse`（13 键） | 通用兜底 | 计费/订单语义没有 |
| 30041 | EventContent_PermanentList | 否 | `router:444` + `factory:961` → `EventContentPermanentListResponse`（8 键） | 通用兜底 | — |
| 35003 | MiniGame_MissionList | 否 | `router:444` + `factory:961` → `MiniGameMissionListResponse`（10 键） | 通用兜底 | — |
| 36001 | Notification_EventContentReddotCheck | 否 | 无 DTO：`router:444` → `router:429 _error_spec` | 通用兜底 | **router 侧 Error 信封**（`resp=null`、`dto_match="none/none"`、extras 无、schema 无同名 DTO；只有 `NotificationLobbyCheckResponse`，语义不同，不做猜测映射）。bridge 侧最小包，外层 protocol 值是 `'Unknown'` |
| 43010 | Friend_Check | 否 | `router:444` + `factory:961` → `FriendCheckResponse`（7 键） | 通用兜底 | — |
| 90004 | Management_Data | **是（桩）** | `probe:662-684 _generic_protocol_response`（`num == 90004`）；通用层 `ManagementDataResponse`（8 键） | 桩/空包 | bridge 分支给 16 键结构（`ServerTimeTicks` 真值、`StaticOpenConditions` 真 55 键、`Notices/Events/Issues/Banners` 全 `[]`）；通用层 8 键，且 `Data` 下 9 个字段类型未知（`EventHandler` 系）→ 出 `{}`/`false` |
| 90009 | Clan_Chat_Records | 否 | `router:444` + `factory:961` → `ClanChatRecordsResponse`（8 键） | 通用兜底 | 聊天记录没有数据源绑定 |

**按级别统计**：完整手写 2（`1002`、`24000`*）· 桩/空包 2（`1017`、`90004`）· 通用兜底 34 · 无 0。
（*`24000` 的完整实现只在 `report/_tmp/sandbox292/account_auth_probe.py` 这份新版副本里；审计目标 `_bridge_ref` 副本里它仍是 9 键桩。）
**按“router/factory 能否生成”统计**：能生成 35/38；不能生成 3 条（`3`、`8006`、`36001`，都是 schema 里没有 Response DTO）。

---

## 第 2 节：通用层结论

### 2.1 `response_factory.py` 能不能对任意 DTO 生成结构合法的响应？

**能——但“任意”的前提是这个名字在 `dto_schema_full_v2.json` 里。** 证据（函数 + 行号）：

1. `factory:222 load_schema()` + `factory:58-61 SCHEMA_CANDIDATES`：schema 唯一来源是 `work/ba/proto/dto_schema_full_v2.json`（2.37 MB），`_meta.counts = {types:709, respDtos:455, responseRoots:457, supportTypes:252}`。
2. `factory:470 base_chain()` / `factory:498 effective_fields()`：不是按 DTO 手写字段，而是沿 `baseChain` 逐层取 `fields`（`BasePacket` / `ResponsePacket` 被跳过，由 `factory:742 _emit_object` 单独补根字段）。
3. `factory:742 _emit_object()` → `factory:839 _value_for()` → `factory:871 _default_for()`：每个字段独立判定 `values` → `hooks` → 状态绑定（`factory:140 OBJECT_BINDINGS` / `157 LIST_BINDINGS` / `183 DICT_BINDINGS` / `191 SCALAR_BINDINGS`）→ 类型默认值；类型不认识就 `factory:384 unknown_default()` 走 `factory:124-131 UNKNOWN_NAME_RULES` 按字段名猜。
4. 入口 `factory:961 build_with_stats()` / `factory:1015 build()`。实测：`protocol_map.json` 里 **14 个没有任何协议 `resp` 指向的 `*Response` DTO**（如 `ContentSweepResponse` 12 键、`EliminateRaidRankingRewardResponse` 9 键）也能 `build()` 出来且 `json_roundtrip_ok=True` → 生成能力确实只取决于 schema 里有没有这个 DTO，与协议号无关。
5. 反向验证：`build_with_stats('TotallyNotADtoResponse', 1234, {})` → 返回 `{}` + warning `DTO 不在 schema`（`factory:969-971`）。

**局限（必须记住）**：
- 只有结构，没有业务语义：`factory` 文件头自己写着“结构完整 ≠ 客户端会接受”（`factory:37-40`）。
- 值只有三种来源：常量默认、`account_state` 绑定、`context['values']`/`hooks` 注值；**没有任何一条协议的发奖/扣费/状态机**。
- 状态绑定是“**类型名 → 状态路径**”的表（`factory:134-135` 注释），不是“协议 → 响应”；表里没有的类型（如 `MailDB`、`ShopInfoDB`）永远填不进数据。
- 全库仍有 264 个字段类型推不出来，靠字段名启发式（`factory:120-131`），`22004` 实测就踩到一个（`EventHandler` → `{}`）。

### 2.2 `protocol_router.py` 的 `route()`：全量路由，无白名单

- `router:444 route(request_ctx)` 六步：① 协议号（`router:257 resolve_protocol_id`，`Hash>>32` / `protocol_id`）→ ② 协议名（`router:275 resolve_name`，base32 token 反查）→ ③ path 交叉校验（`router:302 name_for_path`，只警告）→ ④ 全解不出来 → Error（`router:500-503`）→ ⑤ 查 Response DTO（`router:324 dto_for`：`protocol_map.resp` → `protocol_extras.json` → 按 id 反查）→ ⑥ 交工厂（`router:522-524` 调 `_rf.build_with_stats(dto, pid, fctx)`）。
- **没有 per-protocol 特判表。** 全文按协议号/协议名分支的地方只有：`router:70-76` 的注释（讲 1019/1017 偏移）、`router:711/726` 的自检（`90004`、`24000` 对 `Account_Auth` 冲突样例）。`router:78 ID_ALIASES = {}` 是空表，官方偏移靠 `router:81 set_id_aliases()` 显式注册——**默认什么都不纠正**。
- 未知/已知协议分别怎么走：
  - 未知（无 id 又无 name）→ `router:500-503` Error 信封，`payload = {Protocol:-1, ErrorCode:500, ServerTimeTicks}`（`router:429 _error_spec` + `factory:1027 build_error_packet`）。
  - 已知但 `resp=null` 且 extras 也没有 → `router:514-516` Error 信封（实测 `8006`、`36001`）。
  - 已知但 DTO 不在 schema → `router:517-520` Error 信封。
  - 工厂返回空体 → `router:525-528` Error 信封。
  - 正常 → `ResponseSpec`（`router:356`），`envelope_name = 协议名`。
  - 任何异常 → `router:539-542` 兜底成 Error，永不抛给 bridge。
- 硬编码白名单原文（就这一处，且是空的）：
  ```python
  router:78   ID_ALIASES = {}
  router:81   def set_id_aliases(mapping, replace=False):   # 显式入口，谁有证据谁填
  ```
  `response_factory` 侧另有一张“按协议号”的表，但那是**会话回显白名单**，不是响应构造分支：
  ```python
  factory:105-113
  SESSION_KEY_ECHO_PROTOCOLS = frozenset((
      1000,    # Account_Create
      1002,    # Account_Auth
      1009,    # Account_CheckYostar
      1012,    # Account_Auth2
      1014,    # Account_CheckNexon（国服没有这条，留位）
      37000,   # ProofToken_RequestQuestion
      37001,   # ProofToken_Submit
  ))
  ```

### 2.3 `coverage()` 的实现与分母

- `router:623 coverage(context=None, aggregate=True, collect_failures=40)`：`for row in iter_protocols(): route(...)` 逐条真跑，统计 `total / with_resp / ok / fail / error_envelope / by_source / by_reason / json_roundtrip_bad / unknown_fields_total`。
- `router:596 iter_protocols(with_resp_only=False, include_extras=True)`：遍历 **`protocol_map.json` 的 501 条**（+ `protocol_extras.json` 的 13 条里不重名的）。
- **分母不是 schema 的 709 个 DTO**，是 `protocol_map` 的 501 条。实测本轮：`total=501, with_resp=444, ok=457, fail=44, by_source={'template':457}`，失败原因分布 `B(protocol_map.resp=null 且 extras 没恢复)=38`、`A(协议无数字 id)=6`。与 `test_router.output.txt` 里“457/501 = 91.2%”“444/444 = 100%”一致。

### 2.4 一句话结论

**通用层算“已经有实现”——是“能应答”意义上的实现，不是“协议已实现”意义上的实现。**
38 条里 35 条能拿到结构合法、JSON 往返 OK、且能挂上真实账号状态的响应（`source='account'`），但其中 31 条只是 schema 默认值 + 状态绑定，`Responses`/`MailDBs`/`ShopInfos` 这类真正决定客户端行为的列表要么恒空、要么没有绑定；`3`/`8006`/`36001` 连 DTO 都没有，router 只会回 Error 信封。

---

## 第 3 节：`account_auth_probe.py::_bridge` 的分支清单

`_bridge` 本体 `probe:942-1109`（`_handle:524` 在 `mode != 'forward'` 时调用它）。**下表行号均指 `_bridge_ref` 副本**；新版 `report/_tmp/sandbox292/account_auth_probe.py` 的分支结构与之一致（`_bridge` 在 1107 起、四个名字分支在 1192/1198/1218/1236），只多出 408-577 的 `24000` managed block。它**不按协议号分支，先按“名字查不查得到”分流**；`NAME_TABLE` 来自 `probe:105 load_names()` = `probe:70-84 BUILTIN_NAMES`（43 条）+ 部署机上的 `/www/wwwroot/bapatch/tools/protocol_names.txt`（本机不存在）+ `probe:96-102 EXTRA_TOKENS`（5 个 base32 token）。

### 3.1 `_bridge` 内的分流点（按出现顺序）

| # | 行范围 | 判据 | 干了什么 |
|---|---|---|---|
| 1 | 943-955 | — | `parse_cn_multipart` 取 `protocol` / `packet`；取不到再按 urlencoded form 解析（`+` 先转 `%2B` 保护 base64） |
| 2 | 956-960 | `NAME_TABLE` / `EXTRA_TOKENS` 命中 | `name = NAME_TABLE.get(proto_str) or EXTRA_TOKENS.get(proto_str)`；结果写 `rec['protocol_name']` |
| 3 | 962-968 | `exp == 'experror'` | 直接回 Error 信封 `{"protocol":"Error","packet":"{Protocol:-1,ErrorCode:500,ServerTimeTicks}"}`，不碰官方 |
| 4 | 970-977 | `name is None`（**未知协议**） | 先 `_generic_protocol_response(proto_str, packet_b64, rec)`；返回 `None`（解不开包 / 没有 Hash）就 `_forward(body)` → **只转发**到 `127.0.0.1:5000`（`probe:58 TARGET_BASE`），`rec['fallback']='forward-unknown-protocol'` |
| 5 | 979-1025 | `exp.startswith('decrypt+')` 且 `packet_b64` | **path A**：`cn_cipher.decode_packet` 解真请求 → 取 `Token/Hash` → `ensure_session` → 缺 `SessionKey` 就注入 → `post_gateway(req_json)`（`probe:368`，POST `/api/gateway`）→ `unwrap_gateway_response` → 再按 `cn_resp_format()` 分发：`cn_envelope` → `_cn_envelope`（1020）、`encresp1/2/3` → `_json_encrypted`（1021-1022）、否则 `_json_ok`（1023）。**这条就是“转发官方 + 重新封包”** |
| 6 | 1027-1032 | `name == 'Account_CheckNexon'`（1014） | 本地构造 `{Protocol:1014, ResultState:1, SessionKey:sk, AccountId:aid}`（`_json_ok`），不碰官方 |
| 7 | 1033-1051 | `name in ('Account_Auth','Account_Auth2')`（**1002 / 1012**） | `ensure_session` → `post_gateway({"Protocol":"Account_Auth","SessionKey":sk})` → 官方回包按 `cn_resp_format()` 走 `_cn_envelope` 或 `_json_ok`；`exp=resultstate0/1` 还能改写 `ResultState`（1049-1050）。**默认路径=转发官方**，不是本地构造 |
| 8 | 1053-1068 | `name == 'Account_CallName'`（**1010**） | 解请求取 `"CallName":"…"` → `cn_nick.build_callname_response(call, nickname='111', protocol=1010)` → `_cn_send_envelope`。**本地构造** |
| 9 | 1070-1087 | `name in ('Account_Nickname','Account_CallName')`（**1001**，1010 已在上一条返回） | 解请求取 `"Nickname":"…"` → `cn_nick.build_nickname_response(nick, protocol=1001)` → `_cn_send_envelope`。**本地构造** |
| 10 | 1089-1102 | `rec['req_Hash'] >> 32` 得到协议号（只在 path A 解密过才有） | **path D**：`cn_nick.build_min_response(proto_int)` = `{"Protocol": pid}`，走 `_cn_send_envelope(name or 'Account_Nickname')`，`rec['fallback']='min-envelope'` |
| 11 | 1103-1106 | 已命中名字但上面都没管 | `_generic_protocol_response(..., name=name)` → `rec['known_other_upgraded']=True`（“认得的其它协议”升级成最小/半结构化包） |
| 12 | 1107-1109 | 以上都不成立 | `_forward(body)` → **只转发**官方，`rec['fallback']='forward-known-other'` |

### 3.2 `_generic_protocol_response`（`probe:643-716`）内的按协议号分支

被 #4 / #11 调用。它先 `_cn_decode_any`（`probe:618-641`，`cn_cipher` 解不开就用 `[u32][gzip][iv|ct|key]` 兜底），再用正则从明文里抠 `"Hash": N` → `num = N >> 32`（`probe:650-659`）；`num is None` 直接 `return None`（`probe:660-661`）。

| 行范围 | 判据 | 生成物 |
|---|---|---|
| 662-684 | `num == 90004` | **Management_Data**：16 键对象（`ServerTimeTicks` 真值、`StaticOpenConditions` 取 `cn_inner.STATIC_OPEN_CONDITIONS` 55 键、`Notices/Events/Issues/Banners` 空、`GachaProbabilityDisplay/ContentLock/GachaPeriodDisplay/RaidPeriodDisplay=False`、`GuidePopup={}`），`rec['gen_kind']='management-90004'` |
| 685-695 | `num == 24000` | **Academy_GetInfo**（`_bridge_ref` 旧版）：9 键，`AcademyDB{LastUpdate:"2026-11-14T00:00:00", ZoneVisitCharacterDBs:[], ZoneScheduleGroupRecords:{}}`、`AcademyLocationDBs:[]`，`rec['gen_kind']='academy-24000'`。**新版 `report/_tmp/sandbox292/account_auth_probe.py:856-860` 已改成 `_academy_24000_build(frag, rec)` 官方模板渲染** |
| 696-702 | `num in (1019, 1017)` | **Account_LoginSync**：`{Protocol:num, ServerTimeTicks:0, ServerNotification:0, 4 个空集合, Responses:[], SkillCutInOption:""}`，`rec['gen_kind']='loginsync-%d'` |
| 703-714 | 其它任何 num | **最小泛型包**：`{Protocol:num, ServerTimeTicks:真值, ServerNotification:0, MissionProgressDBs:[], EventMissionProgressDBDict:{}, BattlePassMissionProgressDBDict:{}, StaticOpenConditions:[]}`，`rec['gen_kind']='min+base'` |
| 715-716 | 全部 | `rec['fallback']='generic-envelope'` → `_cn_send_envelope(name or 'Unknown', obj, rec)`（`probe:718-733`：`cn_wire.wrap_response` 出加密体，`Content-Type: text/plain`） |

> 注意 703-714 那一档的 `StaticOpenConditions` 是 `[]`（列表）而不是 55 键字典 —— 与 90004 分支不一致，可能被客户端当类型错处理，记一笔待验证。

### 3.3 `_cn_enc_b64`（`probe:735-915`）里与具体协议绑定的模式

`_bridge` 的 #7 在 `cn_resp_format() == 'cn_envelope'` 时会进 `_cn_envelope`（`probe:577-616`）→ `_cn_enc_b64`。这里**把协议名写死成 `Account_Auth`** 的模式有：

| 行范围 | `cn_wrap_mode()` | 干什么 |
|---|---|---|
| 737-758 | `a_proto_int` / `b_proto_str` | `pv = 1002` 或 `'Account_Auth'` → `cn_inner27.build(pv)`（27 字段 + 22 字段 AccountDB）→ `cn_wire.wrap_response('Account_Auth', …)`。**这是 1002 唯一的本地响应体构造路径** |
| 759-782 | `e4_strict_dto` | `cn_inner.build()` 去掉 `Protocol`/`_probe`，只留 DTO 真成员 |
| 783-799 | `e3_bare_dto` | `cn_inner.build()` 裸 JSON，`cn_wire.wrap_raw` |
| 800-818 | `e2_nickname` | `AccountDB.Nickname='Sensei'` 后封包 |
| 819-837 | `e1_token` | 协议值换成硬编码 token `AHTQLQI65FWJGGGK4KL5AEF57A` |
| 838-856 | `r01_update` | `UpdateRequired=True` |
| 857-873 | `e0_proto_swap` | 读真抓包 `resp_1.body` 解出 inner，用新 requestid 重封 |
| 874-884 | `real_captured` | 原样回放真抓包字节 |
| 885-888 | `cn_enc_b64_probe` | 探测包 `{Protocol:-1, Reason:"ZZPROBEREASON", ErrorCode:1018}`，协议名 `Error` |
| 889-899 | `cn_inner_src()=='spec26'` 否则 `shittim` | inner 取 `cn_inner.build()` 或调用方给的 `inner_obj`；`apply_min_inner` 削字段 |
| 900-915 | 默认 | `cn_wire.wrap_response(proto_name, inner, rid)` 出加密体 |

**一句话**：`_bridge` 里“真正本地构造响应体”的只有 `1001` / `1010` / `1014` / `1017`(1019) / `24000` / `90004` + `1002` 的实验性构造；其余全部是“转发官方”或“最小泛型包”。**38 条里只有 1002 / 1017 / 24000 / 90004 在 `_bridge` 里有名字/号级别的专属分支**；其中只有 `24000` 在新版副本里升级成了官方模板渲染（真实数据），其余三个仍是“固定值/空列表”。

---

## 第 4 节：未找到

1. **未找到任何逐协议处理函数。** 全仓 `*.py` 搜 `def handle_` 只有 4 处，全都不是游戏 RPC 实现：
   - `work/ba/server/example_auth_flow.py:308 handle_auth()`、`:442 handle_followup()`、`:476 handle_rename()` —— 演示脚本，按 `protocol` 参数透传给 `ProtoLayer.render`（`:146`）/ `FactoryLayer.render`（`:202`），本身不构造任何协议字段；
   - `work/ba/bapatch/sdkrelay.py:38 handle_one()` —— SDK 中继，不是游戏 RPC。
2. **未找到 `handle_<协议名>` / `build_<协议名>_response` / `resp_<协议名>` 形式的函数**（除 `cn_nick.build_nickname_response` / `build_callname_response` 这条 1001/1010 专用）。
3. **`account_service.py`（1853 行）里没有任何协议处理函数。** 它全文没有 `handle_` / `build_*Response` / `resp_*`；只有账号/会话/状态块服务：`identify:501`、`get_or_create_account:546`、`issue_session_key:716`、`resolve_session:746`、`load_blob:790`、`save_blob:810`、`build_account_db_for:886`、`build_state_for:942`、`bootstrap_state:979`、`log_protocol:1205`。`log_protocol` 只写日志表，不构造响应。
4. **未找到 `fetch_handler`、`rows_guard`、`_handle_campaign_6020` 这三个名字**（全仓 `*.py` 0 命中）。如果别处有“108 个 fetch_handler / campaign 6020 已手写”的说法，在本仓不成立。
5. **未找到 `official_probe.py` / `passthrough_capture.py` 里的逐协议响应构造。** 两者都是探测/抓包/加解密工具：`official_probe.py:87-96` 只有一张 8 条的 `PROTOCOLS`（name→id→path，**发请求**用的探针表，其中 `Account_LoginSync=1019`、`Account_BirthDay=1005` 与 protocol_map 口径不一致）、`cmd_walk:1033` 只发固定 1019 请求体；`passthrough_capture.py` 全文是 AES/解密/上游转发（`build_upstream_request:917`、`upstream_exchange:1024`），没有响应体构造。
6. **`prototype/_scratch/` 下没有协议实现。** 该目录有 6 个 `.py`（`probe_datasrc.py`、`probe_db.py`、`probe_db2.py`、`probe_format.py`、`probe_official.py`、`probe_zones.py`）+ 输出 txt + `zones.txt` + `_1017_schema.txt`，全部是数据源/DB/格式探测，无响应构造。
7. **未找到 `3` / `8006` / `36001` 的 Response DTO**（`dto_schema_full_v2.json` 里连近似名都没有；`8006`、`36001` 连 `req` 也是 null，`dto_match="none/none"`）。
8. **未找到 `NetworkTime_Sync` 的协议号**：`protocol_map.json` 里 `id=null`（任务给的 `3` 只能从抓包 `Hash>>32` 得到），且 `resp=null`。
9. **未找到 `MailDB` / `ShopInfoDB`（及 `ShopEligmaHistoryDB`）的状态绑定**：`factory:157-180 LIST_BINDINGS` 里没有 → `7000 Mail_List` 的 `MailDBs`、`10002 Shop_List` 的 `ShopInfos` 永远为空，**这两条必须新写绑定或手写响应**。
10. **未找到 `/www/wwwroot/bapatch/tools/protocol_names.txt`**（`probe:57 NAMES_FILE`）：全仓无此文件，所以 bridge 的协议名表运行时只有 43 条 `BUILTIN_NAMES` + 5 个 `EXTRA_TOKENS`；38 条里只有 `NetworkTime_Sync`、`Account_Auth`、`Account_GetTutorial`、`Shop_List`、`Mission_List`、`Mail_List`、`Account_LoginSync`(token) 能被认出来，其余 31 条走“未知协议”分支。
11. **未找到 `cn_cipher.py` / `cn_inner.py` 于 `_bridge_ref/` 内**：`probe:35-40` 从 `/www/wwwroot/bapatch/tools` 导入，本仓只有 `cn_wire.py`、`cn_nick.py`、`cn_inner27.py`（`cn_cipher.py` 在 `report/_tmp/mx_crypto/`、`cn_inner.py` 在 `scripts/`）→ **本机无法直接跑通 bridge 全链路**，只能做静态审计。
12. **未找到“协议实现”类文档**：`work/ba/proto/`、`report/` 里未见逐协议的实现清单（只有 schema 生成/覆盖率报告）。
13. **未找到第二个 managed block**：全仓只有 `report/_tmp/sandbox292/account_auth_probe.py:408-577` 这一个 `292_24000_official` 块（由 `scripts/292_24000_official.py` 注入、模板 `work/ba/proto/academy_24000_official.json`）——即目前只有 `24000` 走过“官方模板注入”这条路；`90004` / `1017` 在新旧两版里都是同一段固定值代码。
14. **未找到 `account_state.seeded.json` 里的 academy 数据**（42 个顶层键里没有 `academy`）→ 通用层的 `AcademyGetInfoResponse` 即使跑起来也不会有学院数据，`24000` 只能靠那份官方模板文件。

---

## 附：本轮证据的可复现片段

（只读；结果就是第 1 节表格里的 `keys/bound/source`）

```python
import sys; sys.path.insert(0, r'work/ba/server')
import response_factory as rf, protocol_router as R
state = __import__('json').load(open(r'work/ba/proto/account_state.seeded.json', encoding='utf-8'))
for pid, name in [(1002,'Account_Auth'), (4000,'Item_List'), (90004,'Management_Data')]:
    spec = R.route({'protocol_id': pid, 'protocol_name': name, 'state': state,
                    'identity': {'account_server_id': 10000000001}})
    print(pid, name, spec.dto_name, len(spec.payload), spec.source, spec.is_error)
```

关键实测数字：`protocol_map` 501 条 · schema 709 类型 / 457 responseRoots · `coverage()` = 457 ok / 44 error（38 B + 6 A）· 38 条里 35 条 route 成功、3 条 Error。
