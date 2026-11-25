# BA 国服（com.RoamingStar.BlueArchive）端点清单 / API 矩阵 / 风控阈值（只读）

> WS=`/data/user/0/com.ai.assistance.operit/files/workspace/9dc0fd0c-7cad-4366-8d0b-bad7165d8587`
> 输入：现成产物 `audit/ba-apk/out/{metadata-strings.txt,strings/*.txt}`、`audit/ba-apk/jadx/sources`（3255 java）、
> 设备上已安装客户端的**运行期数据**（只读：`/sdcard/Android/data/com.RoamingStar.BlueArchive/files/{Hosts,LocalConfig.json,LocalizeConfig.txt,TableBundles/*}`）。
> 未解包 APK、未启动/未改游戏、未读账号存档/Cookies/HTTPCache；`LocalConfig` 里的账号字段未抄录。客户端版本：patch `3_0_2/3_0_3`、资源 `prodm39`。
> 每条结论带证据；取不到的一律写「未取到」。

## 1 端点清单

### 1.1 业务端点（唯一硬证据：客户端自己落盘的 Hosts / LocalizeConfig）

```
$F=…/files/Hosts（89 B，序列化字典）→ 主机名 `gsqc-api.bluearchive-cn.com` + `'https://gsqc-api.bluearchive-cn.com:443'`（前缀 0x01/长度是序列化字节）
$F=…/files/LocalizeConfig.txt → Env=dev; IsLocalize=false;
   ResUrls=https://static.bluearchive-cn.com/prodm39;https://static-qc.bluearchive-cn.com/prodm39;https://static-hs.bluearchive-cn.com/prodm39
$F=…/files/GlobalConfig.json → PathGameData=/_MXTableData/Resources/BytesData/（主数据根）
```

| 类别 | 主机 | 证据 | 说明 |
|---|---|---|---|
| API | `https://gsqc-api.bluearchive-cn.com:443` | `files/Hosts` | 游戏唯一 API 主机；`ApiUrl/GatewayUrl` 由 `ServerInfoConnectionGroupData` 提供（metadata:135740） |
| 资源 CDN ×3 | `static{,-qc,-hs}.bluearchive-cn.com/prodm39` | `files/LocalizeConfig.txt` | 三分区（主/qc/hs）热更资源；`TableBundles` 由此下载 |
| 主数据 | 同 CDN `/_MXTableData/Resources/BytesData/` | `GlobalConfig.json` + `TableBundles/` 实存 | **6,232 个**表包（435 MB）被下载到外部 files 目录 |

### 1.2 三边 http(s):// 去重结果（证明「业务 URL 不在静态代码里」）

| 源 | 去重 URL 数 | 其中业务 URL | 说明 |
|---|---|---|---|
| `jadx/sources`（3255 java） | 38 | **0** | 12 条是 XML 命名空间/SAX feature；其余全是 SDK：alipay×5、adjust×6、oceanengine×1、cmpassport×1、wosms/wostore×2、i139×1、189×1、aliyun dypns×1 |
| `metadata-strings.txt`（768,396 行） | 80 | **0** | 27 kybernetik + 21 unity3d + 17 esotericsoftware + github/w3/nuget/newtonsoft，全是三方库文档链接 |
| `strings/libil2cpp.so.txt`（77,730 行） | 20 | **0** | 全部是压缩块里混入的 HTML/JS 噪声（`www.years`、`px;`…），非真实 URL |

**结论**：业务主机/路径**不以字符串形式编译进 dex / so / global-metadata**；唯一来源是运行期 `Hosts` 落盘 + 服务端下发。`/api`、`/api/`、`/v1/`、`/v2/`、`/gateway` 作为行首字面量在三个源中均为 **0 命中**（`/api/` 全表 28 次出现全部属于 Animancer 文档 URL）。

## 2 API 路径矩阵（实际是「消息级 RPC」，不是 REST 路径表）

证据链：`metadata` 里同时存在 `NetworkTaskManager-Request/CoRequest`、`GameSessionManager-SendRequestGateway`、`GatewayUrl/IsGatewayBypassed`、`HttpGameSession-Init`、`Http2Message`，且 REST 路径字面量为 0 → 客户端走 **Http2 网关 + 消息类型分发**，路径层不暴露在静态产物里。

| 关键词 | NetworkTask 数 | Request/Response 类型数 | 代表消息（metadata 原名） |
|---|---|---|---|
| （总） | **341** | **1493** | `AccountLoginSyncNetworkTask` … |
| gateway | 0（非 Task 命名） | 0 | `SendRequestGateway` / `get_GatewayUrl` / `IsGatewayBypassed`（metadata:69645,69670,69677） |
| account | 17 | 60 | `AccountAuthNetworkTask`、`AccountBirthDayNetworkTask` |
| login | 2 | 27 | `AccountLoginSyncNetworkTask`、`AccountLoginSyncNoPartNetworkTask` |
| battle | 28 | 73 | `ArenaEnterBattleNetworkTask`、`BattlePassGetInfoNetworkTask` |
| raid | 34 | 104 | `EliminateRaid{Create,Enter,End}BattleNetworkTask`（`MultiFloorRaid` 仅有 Request/Response，无 NetworkTask） |
| gacha | 14 | 42 | `EventContentBoxGachaShop{List,Purchase,Refresh}NetworkTask` |
| notice | **0** | 1 | `OnNoticeResponse` + `SessionTask-NotificationFlag`（通知走推送/标志位，不走 NetworkTask） |
| version | 1 | 2 | `SystemVersionNetworkTask` / `SystemVersionRequest/Response` |
| shop | 28 | 76 | `EventContentCardShopPurchaseAllNetworkTask` |
| mail | 6 | 18 | `AccountRequestBirthdayMailNetworkTask` |
| mission | 8 | 32 | `MissionListNetworkTask` |
| arena | 11 | 40 | `ArenaLoginNetworkTask`、`ArenaEnterBattlePart1/2…` |

若要拿到真实 HTTP 路径，只能在设备侧抓包（tcpdump/HttpToolkit）或 dump `NetworkTask` 的 `url` 字段；纯静态**没有**。

## 3 风控阈值表（重点；客户端主数据 `ConstCombatExcel` 实际数值）

取数：客户端下载表 `TableBundles/16300795542385574620_608d0dfcc14694f5df3d0f6c9dc4c170`（1,890,100 B，sha256 `fc243061…29cc1`）→ 内部条目 `constcombatexceltable.bytes`（1032 B）。
本地副本 `audit/ba-work/_probe/constcombat.bytes`（sha256 `53d7a12d…8a1b4b`）；自写 FlatBuffers 解析（root@212，vtable@30，89 槽）。
**类型判定**：同表里 `obstacleColliderHeightJumpable=0x3E99999A=0.3f`、`aimIKMin/Max=±60.0f`、`excessiveTouchCheckTime=1.0f` 证明存在真 float 槽；`defenceConst 10000/6000/3000`、`critical 4000/6000` 与 1.0/0.6/0.3、0.4/0.6 强吻合 → int 槽为 **÷10000 定点**（下表「解码」列，标「推断」的即此换算）。

| 字段 | 原始值（int/float） | 解码 | 证据（表槽号；metadata 行） | 性质 |
|---|---|---|---|---|
| `AllowedMaxTimeScale` | 20000 int | **2.0**（推断 ÷10000） | slot56；60875/60751 | 客户端主数据，非编译常量 |
| `MinimumClearTime` | 10 | 10（原始 int，秒） | slot52；60871/60743 | 同上 |
| `ArenaMinimumClearTime` | 4 | 4 | slot59；60878/60757 | 同上 |
| `MinimumClearLevelGap` | 40 | 40 | slot53；60872/60745 | 同上 |
| `CheckCheaterMaxUseCostNonArena` | 200 | 200 | slot54；60873/60747 | 同上 |
| `CheckCheaterMaxUseCostArena` | 230 | 230 | slot55；60874/60749 | 同上 |
| `CheckCheaterMaxUseCostMultiFloorRaid` | 200 | 200 | slot82；60901/60807 | 同上 |
| `ExcessiveTouchCheckTime` | **1.0f** | 1.0 秒 | slot83；60902/60809 | 同上（真 float） |
| `ExcessiveTouchCheckCount` | 10 | 10 次 | slot84；60903/60811 | 同上 |
| `NormalTimeScale` | 13000 | 1.3 | slot44；60863 | 同上 |
| `FastTimeScale` | 17000 | 1.7 | slot45；60864 | 同上 |
| `BulletTimeScale` | 2000 | 0.2 | slot46；60865 | 同上 |
| `SlowTimeScale` | 10000 | 1.0 | slot49；60868 | 同上 |
| `TimeLimitAlarm` | 10000 | 10000 ms=10 s | slot18；60838 | 同上 |
| `CrowdControlFactor` | 100 | 100（或 0.01 定点，未定） | slot25；60845 | 同上 |
| `MoveCorrectionSkipRatio` | 1500 | 0.15（推断） | slot86；60905 | 同上 |
| `EchelonMaxCommonCost` / `EchelonInitCommonCost` | 10 / **absent** | 10 / 缺省 | slot19/20；60839/60840 | 同上 |
| `EnemyRegenCost` / `ChampionRegenCost` / `PlayerRegenCostDelay` | 10000 / 10000 / 2000 | 10 s / 10 s / 2 s（ms 推断） | slot22/23/24；60842/60843/60844 | 同上 |
| `defenceConstA/B/C/D` | 10000/10000/6000/absent | 1.0/1.0/0.6/缺省 | slot28-31；60848 | 同上 |
| `accuracyConstA/B/C/D` | 10000/10000/3000/absent | 1.0/1.0/0.3/缺省 | slot32-35；60852 | 同上 |
| `criticalConstA/B/C/D` | 4000/4000/6000/absent | 0.4/0.4/0.6/缺省 | slot36-39；60856 | 同上 |
| `WorldRaidAutoSyncTermSecond` / `BossHpDecreaseTerm` | 30 / 3 | 30 s / 3 s | slot64/65；60883/60884 | 同上 |
| `RaidRankingJumpMinimumWaitingTime` | 2000 | 2000 ms | slot67；60886 | 同上 |
| `ObstacleColliderHeightJumpable/NotJumpable` | 0.3f / 1.0f | 0.3 / 1.0 | slot87/88；60906 | 同上 |

**归属定论**：这些值来自**客户端下载的主数据表**（首启 15:51 落到 `TableBundles/`，路径由 `GlobalConfig` 指定，`BundlePackingInfo.json` 提供清单），**不是** libil2cpp 编译常量；改本地表只改本地判定。
**服务端是否用同值二次校验：未验证**（静态无绑定证据；`AccountReportXignCodeCheaterRequest/Response` 只证明有上报通道）。
**未取到**：`ConstCombatExcel` 的 schema（字段类型表）；表中「零点几」是否为 ÷10000 只能由同表 float 槽+常量吻合度推断。

## 4 只读探测（实际 5 个 HTTP 请求，仅 GET/HEAD，间隔 ≥1 s，403/429 即停）

| # | 时间(UTC*) | 方法 | URL | 状态码 | 备注 |
|---|---|---|---|---|---|
| 1 | 10:20:10 | HEAD | `https://gsqc-api.bluearchive-cn.com/` | **404** | `Server: TencentEdgeOne`，`Content-Type: text/plain`，`Content-Length: 18` |
| 2 | 10:20:12 | HEAD | `https://static.bluearchive-cn.com/prodm39/` | **404** | CDN 根不列目录；未 403/429 |
| 3 | 10:20:14 | HEAD | `https://static-qc.bluearchive-cn.com/prodm39/` | **404** | 同上（qc 分区） |
| 4 | 10:20:16 | HEAD | `https://static-hs.bluearchive-cn.com/prodm39/` | **404** | 同上（hs 分区） |
| 5 | 10:20:26 | HEAD | `https://gsqc-api.bluearchive-cn.com/`（`--http2`） | **404** | 实际协商回 **HTTP/1.1**；`EO-Cache-Status: MISS`；TLS `CN=*.bluearchive-cn.com`，issuer RapidSSL TLS RSA CA G1，有效期 2026-09-04→2027-03-11 |

\* 探测机 `date` 与响应 `Date` 头同为 10:20（GMT），故按 UTC 记。

**未做业务请求的原因**：静态三边均无 REST 路径字面量（§2），任何 `/api/...` 都是猜测；按「有证据才打」原则，本轮只验证主机存活与协议面，**0 个业务 POST、0 个带凭证请求**。全部 404 说明主机/CDN 在服务且根路径无目录列举；未出现 403/429，未触发停止条件。DNS：`gsqc-api` → `*.eo.dnse0.com`（39.173.157.74 / 39.174.179.5 / 112.13.210.86，EdgeOne）；`static` → `opencdnv6.jomodns.com` + `*.a.bdydns.com`。

## 5 结论与风险

1. 业务 API 只有 **1 个网关主机** `gsqc-api.bluearchive-cn.com:443`，消息级接口 **341 个 NetworkTask / 1493 个 Request-Response 类型**；REST 路径静态不可得。
2. 风控阈值全部落在 `ConstCombatExcel`（89 槽），本次已解出真实数值：清关时长 10 s / 竞技场 4 s、时间缩放上限 2.0、作弊消耗阈值 200/230/200、触点检测 1 s/10 次。
3. 这些是**客户端主数据**，服务端是否同阈值二次判定未知；把它当「可安全修改的本地开关」是错误假设。
4. 未验证项：schema 类型、服务端校验、CDN 三分区差异、`/api` 路径真实形态（需抓包）。
