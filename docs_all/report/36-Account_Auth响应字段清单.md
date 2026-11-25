# `Account_Auth` 响应字段清单（协议 1002）

> 来源：`Shittim-Server` 实测响应（2026-11-14 02:51:56 首抓）+ 源码 `class AccountAuthResponse`
> 抓取位置：`/www/wwwroot/ba_srv/logs/wire-2026-11-14.txt`（WireDump 明文）
> 客户端：BA 国服 3.0.2（versionCode 73），`APP-VER: 3.0.2`
> 服务端：Shittim-Server，账号 `PublisherAccountId = 314816420`，`AccountServerId = 2`

---

## 0. 三个先记住的坑

1. **响应里没有 `ResultState`，也没有 `ErrorCode`** —— 源码 `class AccountAuthResponse` 全文没有这两个字段，
   `AccountHandler` 也从未给它们赋值。这是**正确的**，不是缺失 bug。
   （对比：`AccountCheckNexonResponse` 有 `ResultState`，`AccountHandler.cs:99` 设 =1）
2. **`ServerNotification: 8` 是正常值** = `HasUnreadMail`（有未读邮件）。
   `GatewayController.cs:324/350` 说明：官方在**每个 in-session 响应**上都会盖这个基线位。
3. **`AccountDB.Nickname` 是空串属正常态**。昵称由独立协议 `Account_Nickname`（1001）设置，
   握手阶段不会带昵称。

---

## 1. 顶层键（24 个，按字母序）

| # | 键 | 类型 | 实测值 | 备注 |
|---|---|---|---|---|
| 1 | `Protocol` | int | `1002` | `Account_Auth` 的协议号 |
| 2 | `CurrentVersion` | int | `446690` | 来自 `ServerConfiguration.AuthCurrentVersion`，**可配置** |
| 3 | `TTSCdnUri` | str | `https://ba.dn.nexoncdn.co.kr/tts/version2/` | 硬编码 |
| 4 | `AccountDB` | dict(9) | 见第 2 节 | 账号主体数据 |
| 5 | `AccountId` | int | `2` | 同 `AccountDB.ServerId` |
| 6 | `SessionKey` | dict(2) | 见第 3 节 | 后续所有请求的凭据 |
| 7 | `EncryptedUID` | str | `FUQPRE2OHCSXGOQRNGJQOAOCD4` | 26 字符 base32，官方为「不透明的 26 字符 base32」 |
| 8 | `ServerNotification` | int | `8` | 位标志；8 = `HasUnreadMail` |
| 9 | `ServerTimeTicks` | int | `639302220170000000` | .NET `DateTime.Ticks`（100ns 精度） |
| 10 | `OptionDB` | dict(0) | `{}` | 官方恒为 `{}` |
| 11 | `AccountRestrictionsDB` | dict(0) | `{}` | 空对象，非 null |
| 12 | `StaticOpenConditions` | dict(55) | 全 0 | 见第 4 节 |
| 13 | `AttendanceBookRewards` | list(1) | 见第 5 节 | 当日可领签到簿；全部领完后为 `[]` |
| 14 | `AttendanceHistoryDBs` | list(0) | `[]` | 账号的完整签到历史 |
| 15 | `RepurchasableMonthlyProductCountDBs` | list(0) | `[]` | |
| 16 | `MonthlyProductParcel` | list(0) | `[]` | |
| 17 | `MonthlyProductMail` | list(0) | `[]` | |
| 18 | `BiweeklyProductParcel` | list(0) | `[]` | |
| 19 | `BiweeklyProductMail` | list(0) | `[]` | |
| 20 | `WeeklyProductParcel` | list(0) | `[]` | |
| 21 | `WeeklyProductMail` | list(0) | `[]` | |
| 22 | `IssueAlertInfos` | list(0) | `[]` | |
| 23 | `AccountLimitedFlashSaleDBs` | list(0) | `[]` | 官方**总是**发出（空时为 `[]`） |
| 24 | `NewlyAddedShopCashIds` | list(0) | `[]` | 官方**总是**发出（空时为 `[]`） |

**官方会省略、而 Shittim 也会省略的字段**（源码注释明确）：
`accountBanByNexonDBs`、`DailyRecordDBs`、值为 `false` 的 `IsArenaAnonymous`、`MinimumVersion`（=0 时省略）、
`IsDevelopment`/`BattleValidation`/`UpdateRequired`（均为 false 时省略）。

---

## 2. `AccountDB`（9 个键）

| 键 | 类型 | 实测值 | 备注 |
|---|---|---|---|
| `ServerId` | int | `2` | = `AccountServerId` |
| `Nickname` | str | `""` | 空串正常，由 `Account_Nickname`(1001) 设置 |
| `State` | int | `1` | 账号状态，1 = 正常 |
| `Level` | int | `1` | 账号等级 |
| `RepresentCharacterServerId` | int | `9` | 代表角色 |
| `LastConnectTime` | str | `2026-11-14T02:51:54` | ISO 字符串，**无时区偏移**，整秒精度 |
| `PublisherAccountId` | int | `314816420` | 平台账号 id（= 我们 SDK 的 uid） |
| `RetentionDays` | int | `0` | |
| `CreateDate` | str | `2026-11-14T02:51:54` | 同上格式 |

---

## 3. `SessionKey`（2 个键）

| 键 | 类型 | 实测值 | 备注 |
|---|---|---|---|
| `AccountServerId` | int | `2` | |
| `MxToken` | str | `0404e715-ec34-4808-b1b1-580aefafc3af` | **GUID 字符串形态**（不是 base64！每次 CheckNexon 重新生成） |

后续所有需要鉴权的协议都要带这个对象；服务端 `GetAuthenticatedUser(db, SessionKey)` 会校验它。

---

## 4. `StaticOpenConditions`（55 个键，实测全 0）

```
Academy, Arena, Billing, Cafe, Cafe_2, Cafe_Invite, Cafe_Invite_2, Campaign, Clan, Craft,
Echelon, EliminateRaid, Equip, EventContent, EventMiniGame_1, EventPermanent, EventStage_1,
EventStage_2, Gacha, GuideMission, Item, LobbyIllust, Main_L_1_2, Main_L_1_3, Main_L_1_4,
Main_L_1_5, MiniGameCCG, MiniGameDefense, MinigameDreamMaker, Mission, Mulligan, MultiFloorRaid,
None, Raid, Schedule, SchoolDungeon, ShiftingCraft, Shop, Shop_Gem, Story, Story_Replay,
Story_Sub, StrategySkip, Student, Tactic_Skip, Tactic_Speed, Talk, TimeAttackDungeon,
Unit_Growth_LevelUp, Unit_Growth_Skill, Unit_Growth_Transcendence, WeekDungeon, WeekDungeon_Chase,
__Deprecated_WeekDungeon_Blood, __Deprecated_WeekDungeon_FindGift
```
值全为 `0`（= 已解锁/无限制）。注意其中两个带 `__Deprecated_` 前缀的历史键**仍然要发**。

---

## 5. `AttendanceBookRewards[0]`（当日签到簿完整定义）

| 键 | 类型 | 实测值 |
|---|---|---|
| `UniqueId` | int | `1` |
| `Title` | str | `ATTENDANCEBOOK_NORMAL` |
| `TitleImagePath` | str | `Uis/01_Common/33_Attendance/ImageFont_Attend_1` |
| `TargetGroup` | int | `1` |
| `BookSize` | int | `10` |
| `StartDate` | str | `2020-11-01T00:00:00` |
| `StartableEndDate` | str | `2099-12-31T04:00:00` |
| `EndDate` | str | `2099-12-31T04:00:00` |
| `MailType` | int | `1` |
| `DailyRewardIcons` | dict(10) | `{"1":"", ... ,"10":""}` |
| `DailyRewards` | dict(10) | 每天一个 `ParcelInfo[]`，元素形如： |

```json
{"Key":{"Type":2,"Id":1},"Amount":20000,
 "Multiplier":{"rawValue":10000},"Probability":{"rawValue":10000}}
```
（`Type`：2 = 货币类，4 = 道具类；`rawValue` 是定点数 ×10000 的表示）

---

## 6. 一次真实响应的体量

| 项 | 值 |
|---|---|
| 明文 JSON 长度 | **3740 字节**（无 `ResultState` 时） |
| nginx gzip 压缩后 | **1269 字节**（客户端 `Accept-Encoding: gzip`） |
| 顶层键数 | 24 |
| 最深嵌套 | `AttendanceBookRewards[0].DailyRewards["1"][0].Multiplier.rawValue` |

---

## 7. 与请求方向的对应关系（实测）

```
客户端 → POST /api/account/auth
  multipart: protocol = BASE32(MD5(UTF-16LE("Account_Auth"))) = AHTQLQI65FWJGGGK4KL5AEF57A
             encode   = True
             packet   = base64([u32 LE 明文长度][gzip(净载荷)])

服务端 → 200 application/json
  {"protocol":"Account_Auth","packet":"<上面这份 24 键 JSON 的字符串形式>"}
```
`protocol` 的反查公式已逐字符验证：
`BASE32(MD5(UTF-16LE("Account_Auth"))) = AHTQLQI65FWJGGGK4KL5AEF57A`

---

## 8. 已知的对外依赖（后续协议会用到这里的字段）

| 字段 | 会被谁用 |
|---|---|
| `SessionKey` | 所有 in-session 协议 |
| `AccountDB.ServerId` / `AccountId` | 绝大多数业务协议 |
| `CurrentVersion` | 客户端版本判定（服务端不做校验） |
| `StaticOpenConditions` | 客户端本地内容锁判定 |
| `ServerNotification` | 客户端红点/推送位 |
