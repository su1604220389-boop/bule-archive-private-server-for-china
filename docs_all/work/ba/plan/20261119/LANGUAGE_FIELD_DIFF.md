# 语言/区域字段对照：我方 vs 官方（假设验证）

- 时间：2026-11-19 01:45（Asia/Shanghai）｜ 执行：srv-ops（**只读**，未改服务器任何文件、未重启、未部署）
- 目的：验证「招募界面本地化全部失败，是因为服务端发错了语言/区域字段」这一假设

## 一句话结论

**我方与官方都**不发**任何语言/区域字段**（`LoginSync` 里零命中、`Account_Auth` 里零命中、`GameSettings` 里没有语言项、服务端 `Language` 枚举根本没有 CN 槽）——
**该假设不成立**：不存在"我们发错了值"这回事，因为双方都没发。

---

## 1. `LoginSync`（1017/1019）递归扫描：语言/区域/设置类键

搜索模式（大小写不敏感）：
`language | lang | locale | localize | localise | region | country | timezone | time_zone | gamesetting | accountsetting | setting`

| 端 | 命中数 | 结果 |
|---|---|---|
| **我方**（`work\ba\data\_tmp\our_loginsync_inner_20261119.json`，728 KB，32 顶层键） | **0** | **无任何命中** |
| **官方**（`report\_tmp\official_decoded_201\02_1017_api_account_loginsync.response.json`，35 顶层键） | **0** | **无任何命中** |

⇒ **官方 LoginSync 响应里也完全没有语言/区域字段**，所以"我们少发/错发语言"这条被排除。

## 2. 顶层 & 其它接口

| 接口 | 我方 | 官方 |
|---|---|---|
| `LoginSync` 顶层 | 32 键：`Protocol, CafeGetInfoResponse, …（无 SessionKey/RequestId/FriendCount）` | 35 键：`Protocol, **SessionKey**, ServerTimeTicks, ServerNotification, **RequestId**, …` |
| `LoginSync.SessionKey` | **`null`**（键不存在） | `{"AccountServerId":10015354380,"MxToken":"Vji5A/Cy6X…"}` |
| `Account_Auth(1002)` 响应 | 顶层 20 键（`Protocol, CurrentVersion, TTSCdnUri, AccountDB, OptionDB, …`）；**语言/设置类命中 = 0** | 官方抓包同样无语言字段 |
| `/api/state`（nginx 静态） | `{"Servers":["https://example.com/api/"],"CallbackUrl":…,"CustomerServiceUrl":"","AddressablesCatalogUrlRoots":[…],"ResourceVersion":"202611051844","TableVersion":"202611051826","MediaVersion":"202611051836","PatchVersion":"202609291539","State":1,"Msg":"","IsOpenPreDownload":true}` ← **无语言字段** | `{"Servers":[…],"State":1,"Msg":"…"}` ← **也无语言字段** |

**客户端请求头（我方实收，桥记录 01:41:13）**
```
APP-VER=3.0.2, CHANNEL-ID=1, PLATFORM-ID=1, RESOURCE-VER=202611051844, TABLE-VER=202611051826,
User-Agent=BestHTTP/2 v2.4.0, Content-Type=multipart/form-data; boundary=BestHTTP_HTTPMultiPartForm_BC53E060
```
**官方 1002 请求明文（抓包）**
```json
{"Protocol":1002,"DevId":"1013178778","OSVersion":"Android OS 17 / API-37 (CP2A.260605.016/B.aa44f1_1b9f17a_1b7f6b9)",
 "DeviceUniqueId":"6b186f8aaed811b9e997c025917dc35c","DeviceModel":"OnePlus PLR110",
 "DeviceSystemMemorySize":15104,"Token":"076b037e8ff4226c972cd8ab18d914f0db517852",
 "SdkPid":"CN-BA","SubChannel":"","ResUrl":"https://static.bluearchive-cn.com/prodm39","Hash":4303557230593}
```
我方 Auth 请求的字段集（桥解析出的 `req_keys`）：
```
['DevId','DeviceModel','DeviceSystemMemorySize','DeviceUniqueId','Hash','OSVersion','Protocol','ResUrl','SdkPid','SubChannel','Token']
```
⇒ **两侧请求字段集合一致，且都不含任何语言字段。**

## 3. `GameSettings` 与 `Language` 枚举

**我方数据库 `Accounts.GameSettings`（逐账号原值）**
```
ServerId=1: {"BypassTeamDeployment":false,"EnableArenaTracker":false,"EnableMultiFloorRaid":false,
             "ForceDateTime":false,"BypassCafeSummon":false,"MultiSweepPresetDBs":[],
             "ForceDateTimeOffset":"2026-11-17T20:34:21.573+08:00","CurrentDateTime":"2026-11-17T20:34:21.573+08:00"}
ServerId=2: 同上（时间不同）
ServerId=4: 同上（时间不同）
```
**`AccountGameSettingDB` 类定义（`Schale\Data\GameModel\ServerModel\AccountGameSettingDB.cs`）**
```csharp
public class AccountGameSettingDB
{
    public bool BypassTeamDeployment { get; set; } = false;
    public bool EnableArenaTracker { get; set; } = false;
    public bool EnableMultiFloorRaid { get; set; } = false;
    public bool ForceDateTime { get; set; } = false;
    public bool BypassCafeSummon { get; set; } = false;
    public List<MultiSweepPresetDB> MultiSweepPresetDBs { get; set; } = [];
    public DateTimeOffset ForceDateTimeOffset { get; set; } = DateTimeOffset.Now;
    public DateTimeOffset CurrentDateTime { get; set; } = DateTimeOffset.Now;
    // ServerDateTimeTicks() / ServerDateTime() / ServerDateTimeOffset()
}
```
⇒ **`GameSettings` 里没有任何语言/区域字段**，全是开关与时间。

**`Language` 枚举（`Schale\MX\FlatData\FlatData.cs:137`）**
```csharp
public enum Language
{
    Kr,   // 0
    Jp,   // 1
    Th,   // 2
    Tw,   // 3
    En    // 4
}
```
⇒ **枚举里没有 Cn/China 槽**；而且它只被 `MailDB.LocalizedSender/LocalizedComment`、
`ClanHandler`（公会签到邮件）、`AttendanceService`（签到邮件）用来生成"多语言邮件文案字典"，
**从未通过任何协议的响应字段下发**（LoginSync / Auth 里都搜不到）。

## 4. 结论与下一步

| 假设 | 结论 |
|---|---|
| 我方发了错误的语言/区域值 | **否** —— 我方一个语言字段都没有 |
| 官方有该字段，我方漏发 | **否** —— 官方 LoginSync / Auth / state 里同样没有 |
| `GameSettings` 里藏着语言枚举 | **否** —— 类定义只有 6 个 bool/list + 2 个时间 |
| 服务端 `Language` 枚举能解释 CN 客户端取错槽 | **不能** —— 枚举无 Cn 槽，且不下发；它只影响邮件文案 |

**⇒ 招募界面的 `No LocalizeKey` 不是"服务端语言字段发错"造成的。**
依照你给的背景（客户端按语言槽索引取 `LocalizeGachaShopDBSchema.Bytes`），
语言槽大概率由**客户端自身**（系统语言 / 打包配置 / `PLATFORM-ID`+`CHANNEL-ID` 解释结果）决定，
服务端没有可调的入口——除非存在别的协议专门下发语言（本次未在 LoginSync/Auth/state 中发现，后续可继续扫其它协议的响应）。

## 5. 附带发现（与本假设无关，但值得记）

- 我方 `LoginSync` 顶层缺 `SessionKey` / `RequestId` / `FriendCount` 三个整键（前两者官方有值）。
- 我方 `LoginSync.SessionKey` 为 **null**（官方是真实对象）；Auth 响应里有 `AccountDB` 无 `SessionKey` 键差异已在上一份 `LOGINSYNC_ENVELOPE_DIFF.md` 记录。
- 官方 `/api/state` 与 我方 `/api/state` 字段差异较大（我方多了 `CallbackUrl / AddressablesCatalogUrlRoots / ResourceVersion / TableVersion / MediaVersion / PatchVersion / IsOpenPreDownload`），但**两侧都没有语言字段**，故不是本假设的解。

**只读取证结束：未改动任何服务器文件、未重启、未部署。**
