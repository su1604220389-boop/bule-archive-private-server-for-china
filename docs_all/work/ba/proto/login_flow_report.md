# BA 国服私服 —— 官方真服完整登录流程状态机（还原报告）

> 数据源：`report/_tmp/official201.har`（sha256 `e4cabb58…b65fd`，201 条 entry）
> 解码后：`report/_tmp/official_decoded_201/`（109 条游戏 RPC 全部解密）
> 抓包窗口：北京时间 **2026-11-16 04:30:38 ~ 04:34:32**（233.98 s）
> 账号：`AccountServerId=10015354380`，昵称 `111`，Lv.32
> 机器可读版：`work/ba/proto/login_flow_state_machine.json`

---

## 0. 结论先行（5 句）

1. **109 条游戏 RPC 全部严格串行**：108 个「收到上一条响应最后一字节 → 发出下一条」的间隔全部 > 0（最小 20 ms），没有任何两条同时在飞。并行只出现在非游戏流量（`checkhealth.html` ×2、`gs-api/api/health` ×2 在同一毫秒重复）。
2. **官方客户端有两条硬链条，可以从抓包里 100% 验证**：
   - `Hash = (Protocol << 32) | counter`，counter 是**会话内全局自增**，本会话 **1..109 连续无缺** → 抓包没有漏条，顺序即真实顺序。
   - **请求 n 的 HTTP 头 `REQUEST-ID` == 响应 n-1 的 `RequestId`**，**108/108 条全部成立**（第 1 条没有该头）。这是整份报告最重要的发现。
3. **`24000 → 1017` 隔 0.130 s 的原因不是任何业务字段，而是 `RequestId`**：
   `91 ms`（24000 的 HTTP 往返）+ `39 ms`（客户端把 17 560 B 响应反序列化 + 拼出下一条请求）= `130 ms`。
   1017 请求体里**没有任何一个值**来自 24000 的响应（25 个 `SyncProtocols` 是客户端常量、`SkillCutInOption` 在 109 条响应里出现 0 次、`SessionKey`/`AccountId` 来自 1002）。客户端只需要 24000 的响应**被成功解析并从信封里取出 `RequestId`**。
4. **我们卡死的原因**：24000 的回包是 `{"Protocol":24000}`（`observed_sequence.json`：`inner_keys=1`、`wrap_mode=direct_envelope`），官方那七件套 `Protocol / SessionKey / ServerTimeTicks / ServerNotification / RequestId / AcademyDB / AcademyLocationDBs` 一个都没有 → 客户端取不到 `RequestId` → 下一条请求的 `REQUEST-ID` 头拼不出来 → 链条停在 24000。
5. **进大厅的最小集合是 23 条 RPC**（seq 1~23，时间 04:30:54.662 → 04:30:59.309，4.647 s），此后 1.843 s 客户端拉 notice/news，**04:31:03.093 大厅可操作（登录后 8.431 s）**。剩下 86 条 `seq 24~109` 全在大厅内，由 UI/刷新组触发，不影响进大厅。

---

## 1. 证据基础与方法（先看这一节，后面所有结论都挂在这里）

### 1.1 Hash 里藏着请求计数器

```
Hash = (Protocol << 32) | counter          counter = 会话内全局自增，从 1 开始
1002  → 4303557230593  = (1002  << 32) | 1
24000 → 103079215104002 = (24000 << 32) | 2
1017  → 4367981740035  = (1017  << 32) | 3
4000  → 17179869184004 = (4000  << 32) | 4
```

109 条的 `counter` 恰好是 **1,2,3,…,109**，严格递增、无重复、无缺口。
**这条结论价值极高**：它证明这份 HAR 没有丢包，并且给出了与时间戳独立的发送顺序。本报告所有「seq」就是这个 counter。

### 1.2 RequestId 链（★ 本报告最关键的证据）

| 请求 | HTTP 头 `REQUEST-ID` | 上一条响应的 `RequestId` | 一致 |
|---|---|---|---|
| seq1 1002 | **（无此头）** | — | — |
| seq2 24000 | `f24daa29-45e0-4ecb-99bc-6d0ed3bd7c4e` | `f24daa29-…`（1002 响应） | ✅ |
| seq3 1017 | `3770c1bc-a631-46fb-a9b6-0421ae2601fe` | `3770c1bc-…`（24000 响应） | ✅ |
| seq4 4000 | `bef95b60-6b60-419a-8844-d81f61ca0e05` | `bef95b60-…`（1017 响应） | ✅ |
| … | … | … | ✅ **108/108** |

含义：**客户端必须先完整解析第 n-1 条响应、从信封里取出 `RequestId`，才拼得出第 n 条请求**。
所以「串行」在这里不是猜测，是可验证的因果：任何一条响应解析失败 / 缺 `RequestId`，链条就在那里断。
`RequestId` 是服务端每条响应新生成的 UUIDv4（24000 的 `3770c1bc…` 与 1017 的 `bef95b60…` 不同，也不等于请求头里的值）。

### 1.3 SessionKey 是纯回显

108/108 条：响应的 `SessionKey` 与请求的 `SessionKey` **逐字节相同**。
`MxToken = Vji5A/Cy6X2enQZKeYgrjxAC8MoRDOCT2Tb1SW13PcZTq2cnyCPPdd81pGbzYBKA`。
`SessionKey` 首次出现在 **1002 的响应**（1002 的请求里没有这个字段）。

### 1.4 响应体与请求体的包装

- 响应体：`{"protocol":"Academy_GetInfo","packet":"<inner JSON 字符串>"}`（外层明文 JSON，`packet` 内是完整信封）。
- 请求体：AES 加密的 `multipart/form-data`，`Content-Length` 就是本报告的「请求B」。
- 客户端头：`APP-VER: 3.0.2`、`PLATFORM-ID: 1`、`CHANNEL-ID: 1`、`RESOURCE-VER: 202611051844`、`TABLE-VER: 202611051826`、`User-Agent: BestHTTP/2 v2.4.0`。

### 1.5 「并行」只有一种情况

109 条游戏 RPC **零并行**。真正的并行只在这里：

| 同毫秒重复 2 次 | 时刻 |
|---|---|
| `static.bluearchive-cn.com/checkhealth.html` | 04:30:42.949 / 42.950；04:30:52.062 ×2 |
| `gs-api.bluearchive-cn.com/api/health` | 04:30:43.556 ×2；04:30:53.096 ×2 |

（其余 SDK/埋点/广告流量与游戏 RPC 互不阻塞，不参与登录判定。）

---

## 2. 阶段总览（12 个阶段：P0~P3 纯 HTTP，P4~P11 是 109 条游戏 RPC）

| 阶段 | 名称 | 时间窗 | RPC# | 协议 | 进入条件 → 退出条件 |
|---|---|---|---|---|---|
| **P0** | 启动自检 | 04:30:38.445 ~ 04:30:43.556 | — |  | 进程启动，反外挂 SDK 初始化完成 → static/checkhealth.html 返回 200（内容 509 B）且 gs-api/api/health 返回 200（2 B） |
| **P1** | 服务器发现 | 04:30:45.180 ~ 04:30:45.398 | — |  | P0 的 health 检查通过 → 拿到 gsqc-api/api/state（676 B）中的网关地址/版本号 |
| **P2** | 资源版本比对 | 04:30:45.979 ~ 04:30:47.118 | — |  | P1 拿到网关 + RESOURCE-VER/TABLE-VER → 3 个 Manifest hash + 2 个 Catalog hash 全部取回并与本地比对完成 |
| **P3** | SDK 登录 | 04:30:48.439 ~ 04:30:53.096 | — |  | P2 版本一致 → sdk-api.yostar.cn/user/quick-login 返回 200（787 B）并取出 Token |
| **P4** | 账号认证 | 04:30:54.662 | 1 | 1002/Account_Auth | P3 拿到 SDK Token；用户点击『开始游戏』 → 1002 响应带回 SessionKey{AccountServerId,MxToken} + AccountDB（非空 Nickname） |
| **P5** | Academy 预取（LoginSync 之前的强制前置） | 04:30:54.980 | 2 | 24000/Academy_GetInfo | P4 的响应被完整解析（拿到 SessionKey） → 24000 响应被完整解析（Protocol/SessionKey/ServerTimeTicks/ServerNotification/RequestId/AcademyDB/AcademyLocationDBs 七件套齐全） |
| **P6** | 登录同步（大 DB 一次性下发） | 04:30:55.110 | 3 | 1017/Account_LoginSync | P5 的响应被完整解析（RequestId 链可用于构造下一个 REQUEST-ID 头） → 1017 响应（246808 B，35 个 DB 段）解析完成 |
| **P7** | 同步后固定链 | 04:30:55.460 ~ 04:30:56.071 | 4~8 | 4000/3/26000/90004/1005 | P6 完成 → 1005 Account_GetTutorial 返回 |
| **P8** | 任务 / 迷你游戏枚举 | 04:30:56.292 ~ 04:30:57.315 | 9~13 | 8000/8006/35003 | P7 完成（尤其 90004 的运营数据） → 35003 MiniGame_MissionList 返回 |
| **P9** | 首屏红点扇入 | 04:30:57.515 ~ 04:30:59.309 | 14~23 | 16000/25003/15002/36001/7001/28019/43010/90004 | P8 完成 → 最后一条 90004 返回（04:30:59.309）；此后 1.843 s 空闲，客户端开始拉notice/news |
| **P10** | 大厅主页 | 04:31:01.246 ~ 04:31:03.093 | 24~26 | 29002/7003/7000 | 大厅主界面渲染（notice/news 拉取完成） → 7000 Mail_List 返回 —— 此时大厅已可操作（登录后 8.431 s） |
| **P11** | 大厅交互与周期刷新 | 04:31:05.134 ~ 04:34:22.916 | 27~109 | 25003/36001/7001/28019/43010/90004/29002/6000/5000/5001/6020/6021/30041/8002/22000/22008/22009/22016/22004/10002/20001/20013/24000/28000/90009 | 大厅可操作 → （会话结束） |

**串行/并行比例：109 条中 109 条串行（100%），0 条并行。**
时间上 P0~P3 占 16.2 s（04:30:38.445 → 04:30:54.662），P4~P10（进大厅）占 8.431 s。

---

## 3. 阶段明细（进入 / 退出 / 失败）


### P0 启动自检

- 时间窗：`04:30:38.445 ~ 04:30:43.556`
- 进入条件：进程启动，反外挂 SDK 初始化完成
- 退出条件：static/checkhealth.html 返回 200（内容 509 B）且 gs-api/api/health 返回 200（2 B）
- 包含 RPC：无（纯 HTTP）
- HTTP 序列：
  - `04:30:38.445 GET down.anticheatexpert.com/gamesafe/mobile/huiwan/android/... -> 404 (492 B)`
  - `04:30:42.722 GET er.ns.aliyuncs.com/policy -> 200 (2044 B)`
  - `04:30:42.728/42.764/46.691/47.683/54.528 etc. aliyun logstores -> 200`
  - `04:30:42.861 POST sdk-api.yostar.cn/common/config -> 200 (7589 B)`
  - `04:30:42.937/42.950 GET sdk-api.yostar.cn/ -> 200 (44 B)`
  - `04:30:42.949 + 42.950 GET static.bluearchive-cn.com/checkhealth.html -> 200 (509 B)  [同一毫秒重复 2 次]`
  - `04:30:43.214 GET openlog.tapapis.cn/status -> 200`
  - `04:30:43.253 POST fp-it.fengkongcloud.com/v3/cloudconf -> 200`
  - `04:30:43.254 POST tapsdk.tapapis.cn/sdk-core/v1/gatekeeper -> 200 (2121 B)`
  - `04:30:43.282 POST dypnsapi-dualstack.aliyuncs.com/ -> 200`
  - `04:30:43.556 GET gs-api.bluearchive-cn.com/api/health -> 200 (2 B)  [同一毫秒重复 2 次]`
- 失败会怎样：checkhealth.html 非 200 / 内容不符 -> 客户端停在标题画面的『维护/更新中』提示；反外挂 404 不影响流程（官方这次也是 404）
- 证据：_timeline.txt 行 5~24；HAR 全 URL

### P1 服务器发现

- 时间窗：`04:30:45.180 ~ 04:30:45.398`
- 进入条件：P0 的 health 检查通过
- 退出条件：拿到 gsqc-api/api/state（676 B）中的网关地址/版本号
- 包含 RPC：无（纯 HTTP）
- HTTP 序列：
  - `04:30:45.180 GET state-api.bluearchive-cn.com/api/state -> 200 (161 B)`
  - `04:30:45.398 GET gsqc-api.bluearchive-cn.com/api/state -> 200 (676 B)`
- 失败会怎样：『无法连接服务器』；state-api 成功但 gsqc-api 失败时客户端不会进入 P2
- 证据：_timeline.txt 行 29、32

### P2 资源版本比对

- 时间窗：`04:30:45.979 ~ 04:30:47.118`
- 进入条件：P1 拿到网关 + RESOURCE-VER/TABLE-VER
- 退出条件：3 个 Manifest hash + 2 个 Catalog hash 全部取回并与本地比对完成
- 包含 RPC：无（纯 HTTP）
- HTTP 序列：
  - `04:30:45.979 GET static.bluearchive-cn.com/prodm39/Manifest/Patch/202609291539/patch_assetmanifest -> 200 (78 B)`
  - `04:30:46.059 GET static.bluearchive-cn.com/prodm39/Manifest/TableBundles/202611051826/TableManifestHash -> 200 (10 B)`
  - `04:30:46.207 GET static.bluearchive-cn.com/prodm39/Manifest/MediaResources/202611051836/MediaManifestHash -> 200 (11 B)`
  - `04:30:46.929 GET static.bluearchive-cn.com/prodm39/AssetBundles/Catalog/202611051844/Android/bundleDownloadInfo.hash -> 200 (9 B)`
  - `04:30:47.118 GET static.bluearchive-cn.com/prodm39/AssetBundles/Catalog/202611051844/Android/catalog_Android.hash -> 200 (32 B)`
- 失败会怎样：hash 不一致 -> 客户端进入下载/更新流程，不会发任何游戏 RPC
- 证据：_timeline.txt 行 33~38；HAR 全 URL。注：任务描述里的『4 个 Manifest/Catalog hash』实际是 3 Manifest + 2 Catalog（共 5 条 GET，其中 1 条是 bundleDownloadInfo.hash）

### P3 SDK 登录

- 时间窗：`04:30:48.439 ~ 04:30:53.096`
- 进入条件：P2 版本一致
- 退出条件：sdk-api.yostar.cn/user/quick-login 返回 200（787 B）并取出 Token
- 包含 RPC：无（纯 HTTP）
- HTTP 序列：
  - `04:30:48.439 POST gid.tapapis.cn/device/v1/query -> 200 (84 B)`
  - `04:30:51.915 POST sdk-api.yostar.cn/user/quick-login -> 200 (787 B)   <-- 真正的登录端点`
  - `04:30:52.008 POST sdk-api.yostar.cn/user/detail -> 200 (787 B)`
  - `04:30:52.062 GET static.bluearchive-cn.com/checkhealth.html -> 200  [同一毫秒重复 2 次]`
  - `04:30:52.152 POST sdk-api.yostar.cn/health-game/duration -> 200`
  - `04:30:52.295 POST sdk-api.yostar.cn/common/geo-ip -> 200`
  - `04:30:52.386 POST sdk-api.yostar.cn/heartbeat/pulse -> 200`
  - `04:30:53.096 GET gs-api.bluearchive-cn.com/api/health -> 200  [同一毫秒重复 2 次]`
- 失败会怎样：拿不到 Token -> 1002 的 Token 字段为空 -> 1002 返回错误码 -> 停在标题画面。注：任务描述写的是 sdk-api/user/login，实测路径是 /user/quick-login（另有 /user/detail）
- 证据：_timeline.txt 行 40~52

### P4 账号认证

- 时间窗：`04:30:54.662`
- 进入条件：P3 拿到 SDK Token；用户点击『开始游戏』
- 退出条件：1002 响应带回 SessionKey{AccountServerId,MxToken} + AccountDB（非空 Nickname）
- 包含 RPC：`1`（共 1 条）：1 1002
- 失败会怎样：返回 ErrorCode -> 「登录失败」弹窗回到标题画面。若 AccountDB.Nickname 为空或 IsNew=true，客户端会额外走 1001 Account_Nickname / 1010 Account_CallName 两条新号 gate（官方抓包里没有这两条）
- 证据：seq 1；本次抓包 IsNew=false、Nickname='111'、CallName=''

### P5 Academy 预取（LoginSync 之前的强制前置）

- 时间窗：`04:30:54.980`
- 进入条件：P4 的响应被完整解析（拿到 SessionKey）
- 退出条件：24000 响应被完整解析（Protocol/SessionKey/ServerTimeTicks/ServerNotification/RequestId/AcademyDB/AcademyLocationDBs 七件套齐全）
- 包含 RPC：`2`（共 1 条）：2 24000
- 失败会怎样：★ 我们当前就卡在这里：客户端不再发任何后续 RPC（含 1017）。官方在这之后的 0.130 s 内必发 1017。约 8 s 后客户端弹「通知 / 同步账户信息时发生错误。将返回标题画面。确认。」并回标题
- 证据：seq 2；observed_sequence.json last_request_before_sync_error

### P6 登录同步（大 DB 一次性下发）

- 时间窗：`04:30:55.110`
- 进入条件：P5 的响应被完整解析（RequestId 链可用于构造下一个 REQUEST-ID 头）
- 退出条件：1017 响应（246808 B，35 个 DB 段）解析完成
- 包含 RPC：`3`（共 1 条）：3 1017
- 失败会怎样：任何一段 DB 结构错 -> 后续 4000/3/26000 链全断；客户端多会直接回标题
- 证据：seq 3；C_1017_response_inventory.json

### P7 同步后固定链

- 时间窗：`04:30:55.460 ~ 04:30:56.071`
- 进入条件：P6 完成
- 退出条件：1005 Account_GetTutorial 返回
- 包含 RPC：`4~8`（共 5 条）：4 4000, 5 3, 6 26000, 7 90004, 8 1005
- 失败会怎样：缺任何一条都会让教学/时间/存档/运营数据缺失，后续任务与大厅红点逻辑不完整
- 证据：seq 4~8

### P8 任务 / 迷你游戏枚举

- 时间窗：`04:30:56.292 ~ 04:30:57.315`
- 进入条件：P7 完成（尤其 90004 的运营数据）
- 退出条件：35003 MiniGame_MissionList 返回
- 包含 RPC：`9~13`（共 5 条）：9 8000, 10 8006, 11 8000, 12 8000, 13 35003
- 失败会怎样：任务/引导赛季/迷你游戏数据缺失 -> 大厅任务面板空白，不阻塞进大厅
- 证据：seq 9~13

### P9 首屏红点扇入

- 时间窗：`04:30:57.515 ~ 04:30:59.309`
- 进入条件：P8 完成
- 退出条件：最后一条 90004 返回（04:30:59.309）；此后 1.843 s 空闲，客户端开始拉notice/news
- 包含 RPC：`14~23`（共 10 条）：14 16000, 15 25003, 16 15002, 17 36001, 18 7001, 19 25003, 20 28019, 21 43010, 22 90004, 23 90004
- 失败会怎样：红点/邮件/公会/好友角标不亮；不阻塞进大厅
- 证据：seq 14~23；随后 04:31:00.783 GET notice.bluearchive-cn.com + 6 条 webcnstatic 新闻图

### P10 大厅主页

- 时间窗：`04:31:01.246 ~ 04:31:03.093`
- 进入条件：大厅主界面渲染（notice/news 拉取完成）
- 退出条件：7000 Mail_List 返回 —— 此时大厅已可操作（登录后 8.431 s）
- 包含 RPC：`24~26`（共 3 条）：24 29002, 25 7003, 26 7000
- 失败会怎样：商店/邮件入口空白，不阻塞操作
- 证据：seq 24~26

### P11 大厅交互与周期刷新

- 时间窗：`04:31:05.134 ~ 04:34:22.916`
- 进入条件：大厅可操作
- 退出条件：（会话结束）
- 包含 RPC：`27~109`（共 83 条）：27 25003, 28 36001, 29 7001, 30 25003, 31 28019, 32 43010, 33 90004, 34 29002, 35 25003, 36 36001, 37 7001, 38 25003, 39 28019, 40 43010, 41 90004, 42 29002, 43 25003, 44 36001, 45 6000, 46 25003, 47 7001, 48 5000, 49 5001, 50 6020, 51 6021, 52 25003, 53 36001, 54 7001, 55 25003, 56 28019, 57 43010, 58 90004, 59 30041, 60 8002, 61 25003, 62 36001, 63 7001, 64 25003, 65 28019, 66 43010, 67 90004, 68 25003, 69 36001, 70 22000, 71 22008, 72 22009, 73 5000, 74 5000, 75 22016, 76 5000, 77 5001, 78 22004, 79 22000, 80 25003, 81 36001, 82 7001, 83 25003, 84 28019, 85 43010, 86 90004, 87 10002, 88 20001, 89 20013, 90 25003, 91 36001, 92 7001, 93 25003, 94 28019, 95 43010, 96 90004, 97 24000, 98 25003, 99 25003, 100 25003, 101 36001, 102 7001, 103 25003, 104 28019, 105 43010, 106 90004, 107 28000, 108 90009, 109 90009
- 失败会怎样：单个功能不可用/弹错；不影响已进入的大厅
- 证据：seq 27~109

---

## 4. 依赖关系图

### 4.1 主链（必有边）

```
[P3 SDK quick-login]
        │ Token=076b037e…
        ▼
seq1 1002 Account_Auth ──响应带回 SessionKey{AccountServerId,MxToken} + AccountDB──┐
        │ RequestId                                                                  │
        ▼                                                                            │
seq2 24000 Academy_GetInfo ◀──(数据依赖：SessionKey / AccountId)─────────────────────┘
        │ RequestId   ★ 我们卡在这一步之后
        ▼
seq3 1017 Account_LoginSync  ← 25 段 DB 一次性下发（246 808 B / 明文 167 287 B）
        │ RequestId
        ▼
seq4 4000 Item_List → seq5 3 NetworkTime_Sync → seq6 26000 ContentSave_Get
        → seq7 90004 Management_Data → seq8 1005 Account_GetTutorial
        ▼
seq9 8000 Mission_List(null) → seq10 8006 → seq11 8000(849) → seq12 8000(10838) → seq13 35003
        ▼
seq14 16000 Toast_List → seq15..23 首屏红点扇入（25003/15002/36001/7001/25003/28019/43010/90004×2）
        │
        ▼ ※ 1.843 s 空闲，拉 notice + 6 张新闻图
seq24 29002 → seq25 7003 → seq26 7000      ← 大厅可操作（登录后 8.431 s）
```

### 4.2 跨阶段数据边（值溯源验证过，共 14 条 `data` 类）

| 目标请求 | 字段 | 值 | 来源（JSON 路径） |
|---|---|---|---|
| seq2 24000 | `SessionKey.*` / `AccountId` | 10015354380 / `Vji5…` | **seq1 1002 响应 `.SessionKey`** |
| seq49 5001 | `EchelonDB.MainSlotServerIds` | 3100950,3043301,… | seq3 1017 `.CharacterListResponse` |
| seq50 6020 | `StageUniqueId` | 1021103 | seq3 1017 `.CampaignListResponse.StageHistoryDBs[11].StageUniqueId`（seq45 6000 响应亦含） |
| seq51 6021 | `Summary.StageId` | 1021103 | 同 6020 + 客户端本地战斗结果 |
| seq78 22004 | `OpponentRank` / `OpponentIndex` | 12909 / 2 | **seq70 22000 响应 `.OpponentUserDBs[2].Rank`** |
| seq88 20001 | `CafeDBId` | 100153543801 | **seq3 1017 `.CafeGetInfoResponse.CafeDBs[0].CafeDBId`** |
| seq108 90009 | `ClanDBId` | 27353 | **seq3 1017 `.ClanLoginResponse.AccountClanDB.ClanDBId`**（seq107 28000 响应亦含） |
| seq109 90009 | `LastChatId` | 321945 | **seq108 90009 响应 `.ChatRecords[0].ChatId`** |
| seq12/13 | `EventContentId` | 10838 | seq7 90004 `.Data.Banners[5].LinkedLobbyBannerId`（候选） |
| seq11 | `EventContentId` | 849 | **未找到**（推断客户端本地表） |
| seq16 15002 | `ConquestEventIds[0]` 等 | 50822 / 821602 | **未找到**（推断客户端本地表 + 本地时间） |
| seq60 8002 | `GuideMissionSeasonId` | 4 | seq10 8006 响应（小整数，证据弱） |

### 4.3 依赖分类统计（109 条）

| 依赖类 | 条数 | 含义 |
|---|---:|---|
| `tick`（大厅刷新组） | 56 | 固定 7 条 `25003→36001→7001→25003→28019→43010→90004`，本会话重复 **9 次**，间隔 1.5~93 s **不规则**，未找到触发它的服务器字段 |
| `serial_only` | 19 | 只依赖上一条响应完成 + RequestId，**无数据依赖** |
| `user`（用户操作） | 19 | 点击界面触发，无服务器数据来源 |
| `data` | 14 | 至少一个参数值只能来自某条先前响应 |
| `external` | 1 | 依赖 SDK 登录（seq1） |

> 串行比 = **109 / 109 = 100%**；其中**真正有数据依赖的只有 14 条**，其余 95 条是「完成依赖」。
> 这个比例正是排查时的关键：**大部分请求不需要你返回任何特定业务数据，只需要你的响应能被解析、并且带 `RequestId`。**

---

## 5. ★ 专项：`24000 → 1017` 的 0.130 s 到底依赖什么

### 5.1 拆解

| 量 | 值 | 来源 |
|---|---|---|
| 24000 发出 | `04:30:54.980` | seq2 |
| 24000 HTTP 往返（`time`） | **91 ms** | HAR `entry.time` |
| 收到响应最后一字节 | `04:30:55.071` | 计算 |
| 客户端解析 + 拼下一条 | **39 ms** | `idle_gap_ms` |
| 1017 发出 | `04:30:55.110` | seq3 |
| 合计 | **130 ms**（= 0.130 s） | ✅ 与题面一致 |

`idle_gap` 与响应体大小正相关，说明它**是反序列化耗时，不是定时器**：

| 响应 | 大小 | idle_gap |
|---|---:|---:|
| 1017 | 246 808 B | 175 ms |
| 8000 | 268 396 B | 114 ms |
| 24000 | 17 560 B | **39 ms** |
| 4000 | 16 088 B | 26 ms |
| 3 | 620 B | 63 ms |

### 5.2 1017 请求体逐字溯源（9 个键，**没有一条来自 24000 的响应**）

| 字段 | 值 | 归因 |
|---|---|---|
| `Protocol` | 1017 | 客户端常量 |
| `SyncProtocols` | 25 个协议号 | **客户端常量**。25 个 id 中 16 个在整份抓包里作为标量值出现 **0 次**；24000 响应里也没有任何协议 id 数组 |
| `SkillCutInOption` | `"OnceADay"` | **本地设置**。109 条响应中出现 **0 次** |
| `Resendable` / `IsTest` / `OSType` | true / false / 2 | 客户端常量（108/109 条请求各只有一种取值） |
| `Hash` | 4367981740035 | `(1017<<32)|3` |
| `SessionKey.{AccountServerId,MxToken}` `AccountId` | 10015354380 / `Vji5…` | **来自 1002 的响应** |

→ **24000 的响应里没有任何值被 1017 引用。这是 SEQUENCING / DISPATCH-completion 依赖，不是数据依赖。**

### 5.3 那个「东西」= `RequestId`

官方 24000 响应（明文，17 560 B 里 decode 出来的 inner）：

```json
{"Protocol":24000,
 "SessionKey":{"AccountServerId":10015354380,"MxToken":"Vji5…"},
 "ServerTimeTicks":639304002548158993,
 "ServerNotification":0,
 "RequestId":"3770c1bc-a631-46fb-a9b6-0421ae2601fe",
 "AcademyDB":{...},"AcademyLocationDBs":[...]}
```

1017 的 HTTP 头 `REQUEST-ID` **就是** `3770c1bc-a631-46fb-a9b6-0421ae2601fe`。
`RequestId` 是**唯一一个「客户端必须从 24000 响应里读出来、否则拼不出下一条请求」的东西**。

### 5.4 候选字段排序（题面点名的 5 个差异）

| 字段 | 判定 | 依据 |
|---|---|---|
| **`RequestId`** | ★ **最可能的门槛** | 108/108 链证明它是下一条请求的必要输入；我们完全没发 |
| `SessionKey` | 必要但不足 | 108/108 纯回显；缺了客户端拿不到会话 |
| `ServerTimeTicks` / `ServerNotification` | 必要字段 | 官方每条响应都带；前者是客户端时钟基准 |
| `AcademyDB.AccountId` | **非门槛** | = `AccountServerId`，客户端已从 `SessionKey` 得知；109 条请求没有一条引用它 |
| `AcademyDB.ZoneVisitCharacterDBs` 的**类型** | 只在反序列化层面致命 | 官方是 `map<string ZoneId, array{UniqueId,ServerId,LastInteractTime}>`（71 个 key）。若我们发成数组 → 解析异常 → 整个响应作废 → 同样断链 |
| `AcademyLocationDBs` | **非门槛** | 官方是 9 元素数组 `{AccountId,LocationId,Rank,Exp}`；无请求引用 `Rank` |

### 5.5 官方 24000 响应的照抄规格（给实现用，全部经脚本核对）

```
Protocol            : 24000                       (int)
SessionKey          : {AccountServerId, MxToken}  逐字回显请求里的值（108/108 已验证）
ServerTimeTicks     : .NET ticks，例 639304002548158993
ServerNotification  : 0
RequestId           : 新 UUIDv4（小写，无大括号）
AcademyDB           : {
  AccountId                : 10015354380                (= AccountServerId)
  LastUpdate               : "2026-11-16T04:00:06.479"   (yyyy-MM-ddTHH:mm:ss.FFFFFFF，无时区；尾零截断，为 0 时省略小数段——见 5.7)
  ZoneVisitCharacterDBs    : { "1": [], "10": [{UniqueId,ServerId,LastInteractTime}…], … }
                             ← **map<string,array>**，官方 **71 个 key**，共 138 个元素
                             107 个不同 UniqueId / 20 个不同 ServerId（其中 28 个非 0）
                             LastInteractTime 全部 = "0001-01-01T00:00:00"
  ZoneScheduleGroupRecords : {}                          ← **空 map，不是数组**
}
AcademyLocationDBs  : [ {AccountId,LocationId,Rank,Exp} × 9 ]   ← **数组**
                      LocationId = [1,7,11,12,13,15,16,17,19]
                      Rank       = [2,1,1,2,1,1,2,2,2]
                      Exp        = [0,0,0,0,0,0,0,0,200]
                      AccountId  = 全部 10015354380
```

官方这 7 个键的 inner JSON 紧凑序列化 = **11 685 B**（线上 17 560 B 是外层 `{"protocol","packet"}` + JSON 转义后的体积）。

⚠️ 我们当前**多发**了官方没有的 4 个键：`MissionProgressDBs` / `EventMissionProgressDBDict` / `BattlePassMissionProgressDBDict` / `StaticOpenConditions`。

### 5.6 判别实验（3 步定位，别一次全上）

1. 24000 只回 `{Protocol, SessionKey(回显), ServerTimeTicks, ServerNotification, RequestId(新 UUID)}`，**不带 AcademyDB** → 若 1017 出现，说明业务负载不是门槛，信封/`RequestId` 是。
2. 仍未出现 → 补 `AcademyDB{AccountId, LastUpdate, ZoneVisitCharacterDBs:{}, ZoneScheduleGroupRecords:{}}`。
3. 仍未出现 → 把 `ZoneVisitCharacterDBs` 换成官方同构（71 个 key，值为数组）。

### 5.7 字节级照抄要点（照这个写才不会解析失败）

| 项 | 规则 | 依据 |
|---|---|---|
| 序列化 | `json.dumps(obj, ensure_ascii=False, separators=(",",":"))`，**保持插入序**；用 `sort_keys` 会破坏字节一致 | 重序列化后恰好 **11 685 B**，与官方 inner 完全一致 |
| `ZoneVisitCharacterDBs` 的 key 顺序 | **字符串字典序**（`"110"` 排在 `"12"` 前面），**不是**数值序 | `sorted(keys)==keys` 为 True；`sorted(keys,key=int)==keys` 为 False |
| `ZoneVisitCharacterDBs` 的值 | 71 个 key 里**只有 `"1"` 是空数组**，其余都有元素；共 138 个元素 | 逐 key 统计 |
| `ServerTimeTicks` | .NET ticks，取值是服务端**本地(UTC+8)墙钟**（`639304002548158993` → `2026-11-16T04:30:54.815899`，比 HTTP 响应开始早 165 ms）；**不是 UTC** | 反解 + 比对 |
| `LastUpdate` | `yyyy-MM-ddTHH:mm:ss.FFFFFFF`，**无时区后缀**（109 条响应里 `Z` / `±hh:mm` 出现 0 次）；小数尾零会被截掉（别的地方出现过 `.03`、`.6`），为 0 时整段省略 | 全量扫描 |
| `RequestId` | 小写 UUID **v4**，36 字符 | 108 条统计 |
| 1002 是唯一的信封例外 | 108/109 条响应前 5 键是 `Protocol,SessionKey,ServerTimeTicks,ServerNotification,RequestId`；**只有 1002** 是 `Protocol,ServerTimeTicks,ServerNotification,RequestId,SessionKey`（SessionKey 排在最后） | 逐文件核对 |

---

## 6. 失败现象对照表（哪一步卡住 → 客户端表现）

| 卡在 | 观测到的客户端表现 | 证据强度 |
|---|---|---|
| P0 checkhealth | 停在标题画面维护/更新提示 | 推断（未实测） |
| P1 state-api | 「无法连接服务器」 | 推断 |
| P2 Manifest hash | 进入下载/更新流程，无任何游戏 RPC | 推断 |
| P3 SDK | 1002 `Token` 为空 → 登录失败弹窗 | 推断 |
| P4 1002 | 登录失败弹窗回标题；若 `IsNew=true`/昵称空，客户端会多走 **1001 Account_Nickname → 1010 Account_CallName**（官方抓包里**没有**这两条） | 部分实测（见 7.2） |
| **P5 24000** | **★ 之后 0 条请求；约 8 s 后弹「通知 / 同步账户信息时发生错误。将返回标题画面。确认。」→ 回标题** | **实测（我方 2026-11-14 会话）** |
| P6 1017 | 任一段 DB 结构错 → 后续固定链全断，回标题 | 推断 |
| P7 4000/3/26000/90004/1005 | 教学/时间/存档/运营数据缺失，任务与红点异常 | 推断 |
| P8 8000/8006/35003 | 任务面板空白，不阻塞进大厅 | 推断 |
| P9 首屏扇入 | 红点/邮件/公会/好友角标不亮 | 推断 |
| P10 29002/7003/7000 | 商店/邮件入口空白 | 推断 |
| P11 大厅内 | 单个功能报错，不影响大厅 | 推断 |

---

## 7. 我们 vs 官方：已经能确认的结构差异

### 7.1 24000 回包（决定性）

| 项 | 官方 | 我们（2026-11-14） |
|---|---|---|
| inner 键数 | 7 | **1** |
| inner JSON | 见 5.3 | `{"Protocol":24000}` |
| `wrap_mode` | 标准信封 | `direct_envelope` / `gen_kind=min` |
| 响应长度 | 17 560 B | **192 B** |

### 7.2 我们的登录链多了两条官方没有的 gate

官方这份抓包里 **1001 / 1010 一次都没出现**，但它们在协议表里是：

- `1001 = Account_Nickname`
- `1010 = Account_CallName`

官方账号 `Nickname="111"`、`CallName=""`、`IsNew=false`。也就是说 **1001/1010 是「新号建号」路径**。
我方链是 `1002 → 1001 → 1010 → 24000`，说明 **我们的 1002 响应让客户端认为这是一个新账号**（`IsNew=true` 或昵称为空）。
→ 建议：1002 响应返回 `IsNew:false` + 非空 `Nickname`，让客户端走与官方一致的既有账号路径，排除「新号分支」这个额外变量。

### 7.3 24000 在大厅里还会被再调一次

seq97（`04:34:11.018`）是 24000 的**第 2 次**调用，紧跟在刷新组走完之后，之后跟了 3 次 `25003`。
→ 服务端 24000 **必须可重复、幂等调用**，不能当一次性 gate。

### 7.4 1017 响应的构造规则（子 agent C 验证）

- 35 个顶层键，**线上 246 808 B / 明文 167 287 B**。
- 25 个 `SyncProtocols` ↔ 25 个被填充的 `*Response` 成员**精确双射**；顺序 = 服务端 DTO 顺序（**不是** `SyncProtocols` 的顺序），照抄观测序。
- 每个被填充成员是完整 `ResponsePacket` 且**外层信封全零**：`{"Protocol":0,"SessionKey":{"AccountServerId":0,"MxToken":""},"ServerTimeTicks":0,"ServerNotification":0,"RequestId":""}`。
- **不要发 `Responses` 数组**（`dto_schema` 里有这个 mid 置信字段，官方明文出现 0 次）。
- **`ItemListResponse` 是存在但为 `null` 的槽**，且 `4000` 是唯一不在 `SyncProtocols` 里的成员协议 → 客户端随后单独发 `Item_List(4000)`。**别顺手把这个槽填上。**
- 21 个协议在整份抓包里**从未被单独调用**，1017 响应是它们登录期的唯一来源：`20000,1003,2000,3000,12000,22001,17018,21000,28001,33000,19000,10006,39006,44000,45000,46000,46001,47000,49000,27002,49004`。
- 注意别混淆：`20001 Cafe_Ack` / `20013` / `22000 Arena_EnterLobby` / `28000 Clan_Lobby` / `10002 Shop_List` 是**不同协议**，不能替代上面那些。
- 仅 4 个仍被单独重拉：`29002`（+6.136 s ×3）、`6000`（+31.520 s）、`5000`（+42.137 s ×4）、`30041`（+124.230 s）。

### 7.5 `SyncProtocols` 可能为空

我方另一会话里客户端发过 `SyncProtocols: []`（`observed_sequence.json`）。**服务端解析 1017 请求时不能假设它一定有 25 项。**

---

### 7.6 根因（服务端代码级，子 agent D 定位）

线上真正跑的是 **bridge 层** `work/ba/server/_bridge_ref/account_auth_probe.py`；
`response_factory.py` / `protocol_router.py` 只被 `example_auth_flow.py` 和 `test_router.py` 引用，**没有接线**。

```
_bridge() 942-977
  └─ 959  name = NAME_TABLE.get(proto_str) or EXTRA_TOKENS.get(proto_str)
          24000 的 token  KKVAEXLS5QIIB36RQW27XRTJGI  → 不在 EXTRA_TOKENS(96-102)
          "Academy_GetInfo"                            → 不在 BUILTIN_NAMES(70-84, 43 个)
  └─ 970-972  rec['unknown_protocol'] = True
  └─ _generic_protocol_response() 的 min 分支
          obj = {"Protocol": num};  rec['gen_kind'] = 'min'      ← 就是那条 192 B 的回包
```

**注意**：仓库里这个 else 分支**已经**升级成 `'min+base'`（7 键），而日志里出现的是 `gen_kind='min'`，文件里也已经没有 `'min'` 这个取值 → **线上部署的 bridge 比仓库 `_bridge_ref` 旧**。线上确切源码：**未找到**（只有日志签名）。
所以「改代码」和「部署」是两件事，必须先确认线上跑的是哪一版。

字段缺口（对照官方 7 键）：

| 字段 | 我方状态 | 根因 |
|---|---|---|
| `RequestId` | 完全没发 | 设计层就**没有建这个字段**（所有 `dto_schema*.json` 里 0 命中，`official_spec.json` 里 153 命中） |
| `SessionKey` | 24000 不发 | `response_factory.SESSION_KEY_ECHO_PROTOCOLS`（105-113，门在 783-795）只白名单 7 个协议 |
| `ServerTimeTicks` / `ServerNotification` | min 包里没有 | 设计层有，但线上走的是 min 分支 |
| `AcademyDB.AccountId` | 缺 | 我方只发 3 个子键 |
| `AcademyDB.ZoneVisitCharacterDBs` | **发成 LIST** | 官方是 `map<string,array>`（71 键） |
| `AcademyDB.ZoneScheduleGroupRecords` | — | 官方是空 map `{}` |
| `AcademyLocationDBs` | 发 `[]` | 官方 9 元素；我方 schema 只有 3 字段（缺 `AccountId`） |

### 7.7 ⚠️ 修复其实已经写好了，但有两处会「改完还是不通」的坑

| 产物 | 路径 | 状态 |
|---|---|---|
| 901 行官方模板 | `work/ba/proto/academy_24000_official.json` | 结构/数值正确，**但有 3 处类型错误**（见下） |
| 模板生成器 | `scripts/291_gen_academy_24000_template.py` | — |
| 部署器（带 `--verify`/`--rollback`） | `scripts/292_24000_official.py` | **是否部署成功：未找到证据** |
| 渲染器 | `report/_tmp/sandbox292/account_auth_probe.py:456-576`（`_academy_24000_build`/`_academy_24000_send`，强制 outer rid == inner RequestId） | 仅 sandbox 验证 |

**坑 1：模板里的占位符是字符串，直接替换会发出错误类型**
`"SessionKey":"__SESSION_KEY__"`（必须是 object）、`"ServerTimeTicks":"__TICKS__"`（必须是 int）、`"AccountId":"__ACCOUNT_ID__"`（必须是 int）。
→ 渲染时必须做**带类型的替换**（json 层替换值，不是字符串拼接），否则客户端解析失败，症状和现在一样。

**坑 2：`gen_academy.py --check` 的断言本身是错的**
它断言 `ZoneVisitCharacterDBs` 是 `list`、`AcademyDB` 的键集合是旧的 3 个、顶层键数 `>= 9`、且必须包含官方根本不发的 4 个 `ResponsePacket` 字段。
→ **一旦你把结构改对，这个自检就会失败**。要么先改 `--check`，要么别拿它当验收标准。

`report/_tmp/sandbox292/account_auth_probe.py` 有 `.bak.20261116_044822`，说明文件今天 04:48 被动过，但**没有部署成功日志**。
→ **第一步应该是确认 `292` 到底有没有部署到 `/www/wwwroot/bapatch`，以及线上 24000 现在返回多少字节**；若已部署却仍卡死，再走 5.6 的三步判别实验。

### 7.8 我方 spec 文件里的类型错误（子 agent B 逐文件核对）

| 文件 | 问题 | 严重度 |
|---|---|---|
| `dto_schema_academy.json` | `AcademyDB.ZoneVisitCharacterDBs` = `kind:"list"`, `type:"unknown"` → **必须是 map/object** | ★★★ 致命 |
| `dto_schema_academy.json` | `AcademyDB` **缺 `AccountId`**（3 字段 vs 官方 4）；`AcademyLocationDB` **缺 `AccountId`**（3 vs 4） | ★★ |
| `dto_schema_academy.json` | `wireFields` 里列了官方 24000 **不发**的 4 个 `ResponsePacket` 字段（`MissionProgressDBs` 等） | ★ |
| `dto_schema_full.json` / `dto_schema_lobby.json` | 同样的 `AccountId` 缺失（像是基类继承没解析） | ★★ |
| `gen_academy.py --check` | 自检断言的是**错误的**形状（见 7.7 坑 2） | ★★★ |
| `type_index_map.json` | `ti 10463/10425/21273/10683` 全部解析成 `null` → 无法校验争议形状，这正是 list/map 搞错的根因 | ★★★ |
| `shittim_types.json` | 没有 `AcademyDB` / `AcademyLocationDB` 的嵌套形状 | ★ |
| **`official_spec.json` → `protocols["24000"]`** | **完全正确**：map、int、71 键、`{}` 标注为恒空、数组长 9 → **以它为类型权威，模板文件只作数值来源** | ✅ 可用 |

顺带纠正 4 条还在文档里流传的错误结论：

- `report/94:192`「24000 应该 9 键（6 基础 + 2 自有）」→ 错，官方 **7 键**。
- `report/76:656`「`Responses:[]` 是元凶」→ 官方明文里**没有** `Responses` 字段。
- `report/97 §A7`「AcademyLocationDB 只有 3 个字段」→ 官方是 **4 个**（含 `AccountId`）。
- `observed_sequence.json:219`「LoginSync=1019；1017=DismissRepurchasablePopup」→ 这条更正是**错的**：`protocol_map.json` 里 `LoginSync=1017`、`DismissRepurchasablePopup=1015`、`1019=RequestBirthdayMail`。若代码按这条更正路由，「24000 之后的下一跳」会被导到错误协议上。

最后：**我方服务端没有 gate 概念**。`protocol_router.route()` 无任何会话前置条件；`account_service` 只有 `resolve_session()->None` 和 `AuthRejected`。
所谓「4 个 gate（1002/1001/1010/24000）」完全是**客户端侧**的执行顺序，服务端并没有拦你。

---

## 8. 未找到 / 未验证（严禁当作结论使用）

- `EventContentId=849`（seq11）在 seq1~10 全部响应中**未找到** —— 推断来自客户端本地 Excel/Table。
- `ConquestEventIds=50822`、`WorldRaidSeasonAndGroupIds={"821":[821602],"823":[823100]}`（seq16）在任何前置响应中**未找到** —— 推断来自本地表 + 本地时间。
- 大厅刷新组的**触发源未找到**：与 `customer.yostar.net/api/open/red_point` 轮询在时间上相邻（±0.7 s），但**没有因果证据**；9 次间隔 1.5~93 s 不规则。
- `SyncProtocols` 的顺序是否有语义：未验证（官方顺序与服务端 DTO 顺序不同）。
- 未请求的槽能否省略：官方 26 个槽全在，未验证省略会怎样。
- 客户端内部如何消费 `AcademyDB` / `AcademyLocationDBs`：**未动态调试验证**。
- `1001/1010` 的判定条件（`IsNew` vs 空昵称）：**未读客户端代码确认**，只是从「官方既有账号不发这两条」推断。
- 「23 条是最小集合」是观测推断：这 23 条官方必然全发且无用户输入，但**能否省掉 P8/P9 仍能进大厅，未做实验证明**。

---

## 9. 复现方式

本目录下的脚本全部只读抓包、只写 `work/ba/proto/_sub/`：

| 脚本 | 作用 | 产物 |
|---|---|---|
| `_sub/extract_timeline.py` | 解析 `_timeline.txt` 201 行 + 关联解码包 | `A_timeline_109.json` |
| `_sub/extract_har_timings.py` | HAR `time`/`timings`/头；UTC→北京 | `A2_har_timings.json` |
| `_sub/verify_requestid_chain.py` | 108/108 RequestId 链 + SessionKey 回显 | `A3_requestid_chain.json` |
| `_sub/extract_field_provenance.py` | 请求信号字段的全局值出现性扫描 | `A4_field_provenance.json` |
| `_sub/extract_path_provenance.py` | 路径级（JSON path）值溯源 | `A5_path_provenance.json` |
| `_sub/build_state_machine.py` | 汇总成状态机 | `login_flow_state_machine.json` |
| `_sub/mk_report.py` | 生成本文件 | `login_flow_report.md` |
| `_sub/B_*`（子 agent B） | 24000 官方响应字段矩阵 / HAR RequestId 链 | `B_*.md/json` |
| `_sub/C_*`（子 agent C） | 1017 请求依赖溯源 + 响应清单 | `C_*.json/md` |
| `_sub/D_*`（子 agent D） | 我方 24000 代码路径现状 | `D_*.md/json` |

---

## 10. 109 条 RPC 完整时序表

列说明：
- `距上条` = **上一条 RPC** 发出 → 本条发出（含上一条的往返）。注意 `_timeline.txt` 原表的 `gap_s` 是「上一条**任意类型** entry」，中间夹了 CONNECT/埋点时会出现 0.001 s 这种假值，这里已按 RPC 重算。
- `idle` = 上一条**响应最后一字节** → 本条发出（≈客户端反序列化耗时，`—` 表示该条无后继）。
- `依赖类`：`data` 有跨请求数据依赖 / `serial_only` 只等上一条完成 / `tick` 大厅刷新组 / `user` 用户操作 / `external` 依赖 SDK 登录。

| # | 时刻 | 距上条 | idle | 协议 | 名称 | HTTP path | 请求B | 响应B | 依赖类 | 触发 / 依赖 |
|---:|---|---:|---:|---:|---|---|---:|---:|---|---|
| 1 | 04:30:54.662 | — | 157 | 1002 | Account_Auth | `/api/account/auth` | 1138 | 5056 | external | 用户点击『开始游戏』；SDK 登录完成后 2.747 s 发出 |
| 2 | 04:30:54.980 | 0.318 | 39 | 24000 | Academy_GetInfo | `/api/academy/getinfo` | 926 | 17560 | data | resp(seq1) 解析完成后 157 ms 立即发出 |
| 3 | 04:30:55.110 | 0.130 | 175 | 1017 | Account_LoginSync | `/api/account/loginsync` | 1182 | 246808 | serial_only | resp(seq2) 解析完成后 39 ms 立即发出（24000 的 RTT 91 ms + 39 ms = 观测到的 0.130 s） |
| 4 | 04:30:55.460 | 0.350 | 26 | 4000 | Item_List | `/api/item/list` | 926 | 16088 | serial_only | resp(seq3) 解析完成后 26 ms |
| 5 | 04:30:55.625 | 0.165 | 63 | 3 | NetworkTime_Sync | `/api/networktime/sync` | 906 | 620 | serial_only | resp(seq4) 解析完成后 63 ms |
| 6 | 04:30:55.773 | 0.148 | 81 | 26000 | ContentSave_Get | `/api/contentsave/get` | 926 | 640 | serial_only | resp(seq5) 解析完成后 81 ms |
| 7 | 04:30:55.940 | 0.167 | 47 | 90004 | Management_Data | `/api/management/data` | 926 | 14124 | serial_only | resp(seq6) 解析完成后 47 ms |
| 8 | 04:30:56.071 | 0.131 | 136 | 1005 | Account_GetTutorial | `/api/account/gettutorial` | 926 | 640 | serial_only | resp(seq7) 解析完成后 136 ms |
| 9 | 04:30:56.292 | 0.221 | 114 | 8000 | Mission_List | `/api/mission/list` | 946 | 268396 | serial_only | resp(seq8) 解析完成后 114 ms；EventContentId=null 表示『全部』 |
| 10 | 04:30:56.632 | 0.340 | 71 | 8006 | Mission_GuideMissionSeasonList | `/api/mission/guidemission` | 926 | 160216 | serial_only | resp(seq9) 解析完成后 71 ms |
| 11 | 04:30:56.839 | 0.207 | 188 | 8000 | Mission_List | `/api/mission/list` | 946 | 8768 | data | resp(seq10) 解析完成后 188 ms |
| 12 | 04:30:57.167 | 0.328 | 20 | 8000 | Mission_List | `/api/mission/list` | 946 | 8216 | data | resp(seq11) 解析完成后 20 ms（全流程最小空闲） |
| 13 | 04:30:57.315 | 0.148 | 66 | 35003 | MiniGame_MissionList | `/api/minigame/missionlist` | 942 | 4480 | data | resp(seq12) 解析完成后 66 ms |
| 14 | 04:30:57.515 | 0.200 | 74 | 16000 | Toast_List | `/api/toast/list` | 926 | 556 | serial_only | resp(seq13) 解析完成后 74 ms |
| 15 | 04:30:57.747 | 0.232 | 82 | 25003 | Event_RewardIncrease | `/api/event/rewardincrease` | 926 | 792 | serial_only | resp(seq14) 解析完成后 82 ms（刷新组第 1 条） |
| 16 | 04:30:57.913 | 0.166 | 87 | 15002 | OpenCondition_EventList | `/api/opencondition/eventl` | 1034 | 600 | data | resp(seq15) 解析完成后 87 ms |
| 17 | 04:30:58.104 | 0.191 | 339 | 36001 | Notification_EventContentReddotCheck | `/api/notification/eventco` | 926 | 1088 | serial_only | resp(seq16) 解析完成后 339 ms |
| 18 | 04:30:58.577 | 0.473 | 35 | 7001 | Mail_Check | `/api/mail/check` | 926 | 556 | serial_only | resp(seq17) 解析完成后 35 ms |
| 19 | 04:30:58.711 | 0.134 | 70 | 25003 | Event_RewardIncrease | `/api/event/rewardincrease` | 926 | 792 | serial_only | resp(seq18) 解析完成后 70 ms |
| 20 | 04:30:58.860 | 0.149 | 62 | 28019 | Clan_Check | `/api/clan/check` | 926 | 536 | serial_only | resp(seq19) 解析完成后 62 ms |
| 21 | 04:30:59.008 | 0.148 | 70 | 43010 | Friend_Check | `/api/friend/check` | 926 | 536 | serial_only | resp(seq20) 解析完成后 70 ms |
| 22 | 04:30:59.161 | 0.153 | 60 | 90004 | Management_Data | `/api/management/data` | 926 | 14124 | serial_only | resp(seq21) 解析完成后 60 ms |
| 23 | 04:30:59.309 | 0.148 | 1843 | 90004 | Management_Data | `/api/management/data` | 926 | 14104 | serial_only | resp(seq22) 解析完成后 60 ms；此后 1.843 s 空闲（大厅首屏渲染） |
| 24 | 04:31:01.246 | 1.937 | 1356 | 29002 | Billing_PurchaseListByYostar | `/api/billing/purchaselist` | 922 | 1280 | user | 首屏 notice/news 拉完后 0.435 s 发出（billing 红点） |
| 25 | 04:31:02.981 | 1.735 | 31 | 7003 | Mail_ListSemiPermanent | `/api/mail/listsemipermane` | 1074 | 556 | serial_only | resp(seq24) 解析完成后 1 ms（同一毫秒） |
| 26 | 04:31:03.093 | 0.112 | 1956 | 7000 | Mail_List | `/api/mail/list` | 1074 | 1600 | serial_only | resp(seq25) 解析完成后 31 ms；7000 与 7003 参数完全相同，仅协议号不同 |
| 27 | 04:31:05.134 | 2.041 | 89 | 25003 | Event_RewardIncrease | `/api/event/rewardincrease` | 926 | 792 | tick | 刷新组 第1/7 条（tick；组序列与 9 次重复见 §4.3） |
| 28 | 04:31:05.316 | 0.182 | 339 | 36001 | Notification_EventContentReddotCheck | `/api/notification/eventco` | 926 | 1088 | tick | 刷新组 第2/7 条（tick；组序列与 9 次重复见 §4.3） |
| 29 | 04:31:05.777 | 0.461 | 24 | 7001 | Mail_Check | `/api/mail/check` | 926 | 556 | tick | 刷新组 第3/7 条（tick；组序列与 9 次重复见 §4.3） |
| 30 | 04:31:05.891 | 0.114 | 63 | 25003 | Event_RewardIncrease | `/api/event/rewardincrease` | 926 | 792 | tick | 刷新组 第1/7 条（tick；组序列与 9 次重复见 §4.3） |
| 31 | 04:31:06.042 | 0.151 | 63 | 28019 | Clan_Check | `/api/clan/check` | 926 | 536 | tick | 刷新组 第5/7 条（tick；组序列与 9 次重复见 §4.3） |
| 32 | 04:31:06.190 | 0.148 | 64 | 43010 | Friend_Check | `/api/friend/check` | 926 | 536 | tick | 刷新组 第6/7 条（tick；组序列与 9 次重复见 §4.3） |
| 33 | 04:31:06.340 | 0.150 | 2196 | 90004 | Management_Data | `/api/management/data` | 926 | 14124 | tick | 刷新组 第7/7 条（tick；组序列与 9 次重复见 §4.3） |
| 34 | 04:31:08.629 | 2.289 | 4102 | 29002 | Billing_PurchaseListByYostar | `/api/billing/purchaselist` | 926 | 1280 | tick | 刷新组 第0/7 条（tick；组序列与 9 次重复见 §4.3） |
| 35 | 04:31:12.824 | 4.195 | 75 | 25003 | Event_RewardIncrease | `/api/event/rewardincrease` | 926 | 792 | tick | 刷新组 第1/7 条（tick；组序列与 9 次重复见 §4.3） |
| 36 | 04:31:12.986 | 0.162 | 365 | 36001 | Notification_EventContentReddotCheck | `/api/notification/eventco` | 926 | 1088 | tick | 刷新组 第2/7 条（tick；组序列与 9 次重复见 §4.3） |
| 37 | 04:31:13.454 | 0.468 | 30 | 7001 | Mail_Check | `/api/mail/check` | 926 | 556 | tick | 刷新组 第3/7 条（tick；组序列与 9 次重复见 §4.3） |
| 38 | 04:31:13.571 | 0.117 | 63 | 25003 | Event_RewardIncrease | `/api/event/rewardincrease` | 926 | 792 | tick | 刷新组 第1/7 条（tick；组序列与 9 次重复见 §4.3） |
| 39 | 04:31:13.723 | 0.152 | 67 | 28019 | Clan_Check | `/api/clan/check` | 926 | 536 | tick | 刷新组 第5/7 条（tick；组序列与 9 次重复见 §4.3） |
| 40 | 04:31:13.873 | 0.150 | 61 | 43010 | Friend_Check | `/api/friend/check` | 926 | 536 | tick | 刷新组 第6/7 条（tick；组序列与 9 次重复见 §4.3） |
| 41 | 04:31:14.069 | 0.196 | 605 | 90004 | Management_Data | `/api/management/data` | 926 | 14124 | tick | 刷新组 第7/7 条（tick；组序列与 9 次重复见 §4.3） |
| 42 | 04:31:14.785 | 0.716 | 8313 | 29002 | Billing_PurchaseListByYostar | `/api/billing/purchaselist` | 926 | 1280 | tick | 刷新组 第0/7 条（tick；组序列与 9 次重复见 §4.3） |
| 43 | 04:31:23.190 | 8.405 | 67 | 25003 | Event_RewardIncrease | `/api/event/rewardincrease` | 926 | 792 | tick | 刷新组 第1/7 条（tick；组序列与 9 次重复见 §4.3） |
| 44 | 04:31:23.350 | 0.160 | 3175 | 36001 | Notification_EventContentReddotCheck | `/api/notification/eventco` | 926 | 1088 | tick | 刷新组 第2/7 条（tick；组序列与 9 次重复见 §4.3） |
| 45 | 04:31:26.630 | 3.280 | 50 | 6000 | Campaign_List | `/api/campaign/list` | 926 | 44672 | user | 用户打开剧情/关卡界面后 3.175 s（选关前的列表请求） |
| 46 | 04:31:26.794 | 0.164 | 9707 | 25003 | Event_RewardIncrease | `/api/event/rewardincrease` | 926 | 792 | tick | 刷新组 第1/7 条（tick；组序列与 9 次重复见 §4.3） |
| 47 | 04:31:36.586 | 9.792 | 563 | 7001 | Mail_Check | `/api/mail/check` | 926 | 556 | tick | 刷新组 第3/7 条（tick；组序列与 9 次重复见 §4.3） |
| 48 | 04:31:37.247 | 0.661 | 253 | 5000 | Echelon_List | `/api/echelon/list` | 926 | 4120 | user | 用户打开编队界面 |
| 49 | 04:31:37.905 | 0.658 | 820 | 5001 | Echelon_Save | `/api/echelon/save` | 1394 | 984 | user | 用户在编队界面保存队伍后 253 ms |
| 50 | 04:31:38.827 | 0.922 | 70270 | 6020 | Campaign_EnterMainStageStrategySkip | `/api/campaign/entermainst` | 990 | 2072 | data | 用户点击『跳过战斗』 |
| 51 | 04:32:49.197 | 70.370 | 6821 | 6021 | Campaign_MainStageStrategySkipResult | `/api/campaign/mainstagest` | 32572 | 10284 | data | 战斗在客户端本地跑完（70.270 s 空闲 = 战斗时长）后发出 |
| 52 | 04:32:56.190 | 6.993 | 74 | 25003 | Event_RewardIncrease | `/api/event/rewardincrease` | 926 | 792 | tick | 刷新组 第1/7 条（tick；组序列与 9 次重复见 §4.3） |
| 53 | 04:32:56.362 | 0.172 | 368 | 36001 | Notification_EventContentReddotCheck | `/api/notification/eventco` | 926 | 1088 | tick | 刷新组 第2/7 条（tick；组序列与 9 次重复见 §4.3） |
| 54 | 04:32:56.842 | 0.480 | 34 | 7001 | Mail_Check | `/api/mail/check` | 926 | 556 | tick | 刷新组 第3/7 条（tick；组序列与 9 次重复见 §4.3） |
| 55 | 04:32:56.967 | 0.125 | 67 | 25003 | Event_RewardIncrease | `/api/event/rewardincrease` | 926 | 792 | tick | 刷新组 第1/7 条（tick；组序列与 9 次重复见 §4.3） |
| 56 | 04:32:57.117 | 0.150 | 60 | 28019 | Clan_Check | `/api/clan/check` | 926 | 536 | tick | 刷新组 第5/7 条（tick；组序列与 9 次重复见 §4.3） |
| 57 | 04:32:57.266 | 0.149 | 72 | 43010 | Friend_Check | `/api/friend/check` | 926 | 536 | tick | 刷新组 第6/7 条（tick；组序列与 9 次重复见 §4.3） |
| 58 | 04:32:57.432 | 0.166 | 1820 | 90004 | Management_Data | `/api/management/data` | 926 | 14124 | tick | 刷新组 第7/7 条（tick；组序列与 9 次重复见 §4.3） |
| 59 | 04:32:59.340 | 1.908 | 4234 | 30041 | EventContent_PermanentList | `/api/eventcontent/permane` | 926 | 2156 | user | 用户打开活动内容界面 |
| 60 | 04:33:03.675 | 4.335 | 2298 | 8002 | Mission_MultipleReward | `/api/mission/multiplerewa` | 1010 | 8320 | data | 用户点击『一键领取』任务奖励 |
| 61 | 04:33:06.123 | 2.448 | 76 | 25003 | Event_RewardIncrease | `/api/event/rewardincrease` | 926 | 792 | tick | 刷新组 第1/7 条（tick；组序列与 9 次重复见 §4.3） |
| 62 | 04:33:06.299 | 0.176 | 366 | 36001 | Notification_EventContentReddotCheck | `/api/notification/eventco` | 926 | 1088 | tick | 刷新组 第2/7 条（tick；组序列与 9 次重复见 §4.3） |
| 63 | 04:33:06.769 | 0.470 | 28 | 7001 | Mail_Check | `/api/mail/check` | 926 | 556 | tick | 刷新组 第3/7 条（tick；组序列与 9 次重复见 §4.3） |
| 64 | 04:33:06.898 | 0.129 | 60 | 25003 | Event_RewardIncrease | `/api/event/rewardincrease` | 926 | 792 | tick | 刷新组 第1/7 条（tick；组序列与 9 次重复见 §4.3） |
| 65 | 04:33:07.049 | 0.151 | 74 | 28019 | Clan_Check | `/api/clan/check` | 926 | 536 | tick | 刷新组 第5/7 条（tick；组序列与 9 次重复见 §4.3） |
| 66 | 04:33:07.214 | 0.165 | 62 | 43010 | Friend_Check | `/api/friend/check` | 926 | 536 | tick | 刷新组 第6/7 条（tick；组序列与 9 次重复见 §4.3） |
| 67 | 04:33:07.363 | 0.149 | 2587 | 90004 | Management_Data | `/api/management/data` | 926 | 14124 | tick | 刷新组 第7/7 条（tick；组序列与 9 次重复见 §4.3） |
| 68 | 04:33:10.041 | 2.678 | 29 | 25003 | Event_RewardIncrease | `/api/event/rewardincrease` | 926 | 792 | tick | 刷新组 第1/7 条（tick；组序列与 9 次重复见 §4.3） |
| 69 | 04:33:10.166 | 0.125 | 2169 | 36001 | Notification_EventContentReddotCheck | `/api/notification/eventco` | 926 | 1088 | tick | 刷新组 第2/7 条（tick；组序列与 9 次重复见 §4.3） |
| 70 | 04:33:12.442 | 2.276 | 2816 | 22000 | Arena_EnterLobby | `/api/arena/enterlobby` | 926 | 9068 | user | 用户打开竞技场 |
| 71 | 04:33:15.394 | 2.952 | 1589 | 22008 | Arena_CumulativeTimeReward | `/api/arena/cumulativetime` | 926 | 3072 | user | 用户点击竞技场累计时长奖励 |
| 72 | 04:33:17.101 | 1.707 | 1356 | 22009 | Arena_DailyReward | `/api/arena/dailyreward` | 926 | 3224 | user | 用户点击竞技场每日奖励 |
| 73 | 04:33:18.562 | 1.461 | 1708 | 5000 | Echelon_List | `/api/echelon/list` | 926 | 4120 | user | 竞技场编队界面列表 |
| 74 | 04:33:20.377 | 1.815 | 902 | 5000 | Echelon_List | `/api/echelon/list` | 926 | 4120 | user | 竞技场编队界面列表（第 2 次） |
| 75 | 04:33:21.382 | 1.005 | 585 | 22016 | Arena_SyncEchelonSettingTime | `/api/arena/syncechelonset` | 922 | 640 | user | 同步竞技场编队设置时间 |
| 76 | 04:33:22.070 | 0.688 | 177 | 5000 | Echelon_List | `/api/echelon/list` | 922 | 4120 | user | 竞技场编队界面列表（第 3 次） |
| 77 | 04:33:22.785 | 0.715 | 631 | 5001 | Echelon_Save | `/api/echelon/save` | 1418 | 1004 | data | 用户在竞技场编队界面保存 |
| 78 | 04:33:23.501 | 0.716 | 22737 | 22004 | Arena_EnterBattle | `/api/arena/enterbattle` | 1010 | 67180 | data | 用户点击第 3 个对手『战斗』 |
| 79 | 04:33:46.722 | 23.221 | 3459 | 22000 | Arena_EnterLobby | `/api/arena/enterlobby` | 926 | 9068 | user | 战斗结算后返回竞技场大厅（22.737 s 空闲 = 战斗+结算） |
| 80 | 04:33:50.283 | 3.561 | 68 | 25003 | Event_RewardIncrease | `/api/event/rewardincrease` | 926 | 792 | tick | 刷新组 第1/7 条（tick；组序列与 9 次重复见 §4.3） |
| 81 | 04:33:50.453 | 0.170 | 400 | 36001 | Notification_EventContentReddotCheck | `/api/notification/eventco` | 926 | 1088 | tick | 刷新组 第2/7 条（tick；组序列与 9 次重复见 §4.3） |
| 82 | 04:33:50.924 | 0.471 | 27 | 7001 | Mail_Check | `/api/mail/check` | 926 | 556 | tick | 刷新组 第3/7 条（tick；组序列与 9 次重复见 §4.3） |
| 83 | 04:33:51.024 | 0.100 | 62 | 25003 | Event_RewardIncrease | `/api/event/rewardincrease` | 926 | 792 | tick | 刷新组 第1/7 条（tick；组序列与 9 次重复见 §4.3） |
| 84 | 04:33:51.222 | 0.198 | 60 | 28019 | Clan_Check | `/api/clan/check` | 926 | 536 | tick | 刷新组 第5/7 条（tick；组序列与 9 次重复见 §4.3） |
| 85 | 04:33:51.655 | 0.433 | 71 | 43010 | Friend_Check | `/api/friend/check` | 926 | 536 | tick | 刷新组 第6/7 条（tick；组序列与 9 次重复见 §4.3） |
| 86 | 04:33:51.803 | 0.148 | 7246 | 90004 | Management_Data | `/api/management/data` | 926 | 14124 | tick | 刷新组 第7/7 条（tick；组序列与 9 次重复见 §4.3） |
| 87 | 04:33:59.137 | 7.334 | 2311 | 10002 | Shop_List | `/api/shop/list` | 946 | 1304 | user | 用户打开商店（CategoryList=[38]） |
| 88 | 04:34:01.533 | 2.396 | 1683 | 20001 | Cafe_Ack | `/api/cafe/ack` | 946 | 5016 | data | 用户打开咖啡厅 |
| 89 | 04:34:03.336 | 1.803 | 6313 | 20013 | Cafe_ReceiveCurrency | `/api/cafe/receivecurrency` | 990 | 11136 | data | 用户点击咖啡厅领取货币 |
| 90 | 04:34:09.740 | 6.404 | 46 | 25003 | Event_RewardIncrease | `/api/event/rewardincrease` | 926 | 792 | tick | 刷新组 第1/7 条（tick；组序列与 9 次重复见 §4.3） |
| 91 | 04:34:09.859 | 0.119 | 356 | 36001 | Notification_EventContentReddotCheck | `/api/notification/eventco` | 926 | 1088 | tick | 刷新组 第2/7 条（tick；组序列与 9 次重复见 §4.3） |
| 92 | 04:34:10.335 | 0.476 | 37 | 7001 | Mail_Check | `/api/mail/check` | 926 | 556 | tick | 刷新组 第3/7 条（tick；组序列与 9 次重复见 §4.3） |
| 93 | 04:34:10.452 | 0.117 | 66 | 25003 | Event_RewardIncrease | `/api/event/rewardincrease` | 926 | 792 | tick | 刷新组 第1/7 条（tick；组序列与 9 次重复见 §4.3） |
| 94 | 04:34:10.584 | 0.132 | 72 | 28019 | Clan_Check | `/api/clan/check` | 926 | 536 | tick | 刷新组 第5/7 条（tick；组序列与 9 次重复见 §4.3） |
| 95 | 04:34:10.717 | 0.133 | 64 | 43010 | Friend_Check | `/api/friend/check` | 922 | 536 | tick | 刷新组 第6/7 条（tick；组序列与 9 次重复见 §4.3） |
| 96 | 04:34:10.849 | 0.132 | 96 | 90004 | Management_Data | `/api/management/data` | 926 | 14124 | tick | 刷新组 第7/7 条（tick；组序列与 9 次重复见 §4.3） |
| 97 | 04:34:11.018 | 0.169 | 146 | 24000 | Academy_GetInfo | `/api/academy/getinfo` | 926 | 17560 | user | 用户打开 Academy 界面（此后紧跟 3 次 25003，seq98~100） |
| 98 | 04:34:11.245 | 0.227 | 603 | 25003 | Event_RewardIncrease | `/api/event/rewardincrease` | 926 | 792 | user | Academy 界面打开后的奖励状态查询（第 1 次） |
| 99 | 04:34:11.911 | 0.666 | 2055 | 25003 | Event_RewardIncrease | `/api/event/rewardincrease` | 926 | 792 | user | Academy 界面奖励状态查询（第 2 次） |
| 100 | 04:34:14.031 | 2.120 | 68 | 25003 | Event_RewardIncrease | `/api/event/rewardincrease` | 926 | 792 | user | Academy 界面奖励状态查询（第 3 次） |
| 101 | 04:34:14.172 | 0.141 | 393 | 36001 | Notification_EventContentReddotCheck | `/api/notification/eventco` | 926 | 1088 | tick | 刷新组 第2/7 条（tick；组序列与 9 次重复见 §4.3） |
| 102 | 04:34:14.644 | 0.472 | 36 | 7001 | Mail_Check | `/api/mail/check` | 926 | 556 | tick | 刷新组 第3/7 条（tick；组序列与 9 次重复见 §4.3） |
| 103 | 04:34:14.810 | 0.166 | 64 | 25003 | Event_RewardIncrease | `/api/event/rewardincrease` | 926 | 792 | tick | 刷新组 第1/7 条（tick；组序列与 9 次重复见 §4.3） |
| 104 | 04:34:14.945 | 0.135 | 66 | 28019 | Clan_Check | `/api/clan/check` | 922 | 536 | tick | 刷新组 第5/7 条（tick；组序列与 9 次重复见 §4.3） |
| 105 | 04:34:15.074 | 0.129 | 63 | 43010 | Friend_Check | `/api/friend/check` | 926 | 536 | tick | 刷新组 第6/7 条（tick；组序列与 9 次重复见 §4.3） |
| 106 | 04:34:15.207 | 0.133 | 1664 | 90004 | Management_Data | `/api/management/data` | 926 | 14124 | tick | 刷新组 第7/7 条（tick；组序列与 9 次重复见 §4.3） |
| 107 | 04:34:16.937 | 1.730 | 954 | 28000 | Clan_Lobby | `/api/clan/lobby` | 926 | 35864 | user | 用户打开公会 |
| 108 | 04:34:18.043 | 1.106 | 4728 | 90009 | Clan_Chat_Records | `/api/clan/chat/records` | 970 | 30316 | data | 用户打开公会聊天 |
| 109 | 04:34:22.916 | 4.873 | — | 90009 | Clan_Chat_Records | `/api/clan/chat/records` | 970 | 556 | data | 公会聊天轮询新消息 |
