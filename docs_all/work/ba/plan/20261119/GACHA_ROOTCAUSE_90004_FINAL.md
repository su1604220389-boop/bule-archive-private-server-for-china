# 招募界面长期损坏 —— 根因结案：协议 90004 `Management_Data` 运营数据缺失

- 结案时间：**2026-11-19 02:15（真机验收通过，招募界面完全正常）**
- 问题现象：招募面板标题 / 说明 / 点数说明 / 底部按钮全显示红色 `[FF0000]No LocalizeKey`，页签显示 `DUMMY`，十连按钮点击后毫无反应（连本地提示都没有）
- 文档性质：归档结案文档。只记录结论、证据与后续运维口径，**不含代码改动建议**；本次作业未联网、未碰服务器、未修改任何已有文件
- 数据基准：官方 90004 抓包（`report\_tmp\official_decoded_201\06_90004_api_management_data.response.json`，抓包批次记为 2026-11-18）；当前档期截止 **2026-11-26 13:59:59**（见 §4）

---

## 0. 一句话结论

招募界面坏掉**不是卡池数据问题、不是客户端 / 表 / APK / 语言问题**，而是桥把协议 **90004 `Management_Data`** 写成了一个错误的硬编码桩：**没有 `Data` 外壳**、9 个业务键被平铺到信封层、且 `GachaProbabilityDisplay` / `Banners` / `Notices` / `Events` 全空或类型错 —— 客户端因此拿不到**公告 / 横幅 / 概率公示页**这一层运营数据，招募面板退回到「查不到文案」的静态兜底串；把官方原样的 `Data` 以纯数据方式补上后，界面 100% 恢复。**所以换期时唯一需要替换的就是 `90004_ops.json` 这一个数据文件。**

---

## 1. 根因

### 1.1 症状与结案判定

| 症状 | 修复前 | 修复后（02:15 真机） | 证据 |
|---|---|---|---|
| 面板标题 / 说明 / 点数说明 / 底部按钮 | 红色 `[FF0000]No LocalizeKey` | 正常中文文案 | 真机验收（2026-11-19 02:15）；`D90004_DEPLOY.md` |
| 页签 | `DUMMY` | 正常页签名 | 同上 |
| 十连按钮 | 点击无任何反应，**连本地提示都没有** | 可点、可抽 | 同上 |
| 「注意事项」 | 打不开 / 空白 | 能打开 | 同上 |
| 90004 响应体 | 2,092 B（结构错、内容空） | **14,016 B** | `D90004_DEPLOY.md` §5 |

### 1.2 病灶：`account_auth_probe.py` 里 `if num == 90004:` 的硬编码桩

改动前该分支共 **23 行 / 16 个引号键 / 无 `Data` 外壳**（`D90004_DEPLOY.md` §3 preflight 原文：`has Data=False`）。官方 9 个业务键全在 `Data` 内部，我方却把它们平铺到了信封层：

| 层面 | 官方（10/10 抓包一致） | 我方桩 | 判定 |
|---|---|---|---|
| 顶层键 | **6 个**：`Protocol` / `SessionKey` / `ServerTimeTicks` / `ServerNotification` / `RequestId` / `Data` | 16 个键平铺 | ❌ 形态错 |
| `Data` 外壳 | 存在，9 键 | **不存在** | ❌ 核心病灶 |
| `GachaProbabilityDisplay` | **12 条对象数组**，每条 `{GachaProbabilityDisplayId, Url, LinkedLobbyBannerId, GachaDisplayTag}`，URL 指向 `notice.bluearchive-cn.com/static/gacha/*.html` | `false` | ❌ 类型错 + 内容全空 |
| `GachaPeriodDisplay` | **`null`** | `false` | ❌ 类型错 |
| `RaidPeriodDisplay` | **`null`** | `false` | ❌ 类型错 |
| `GuidePopup` | **`[]`** | `{}` | ❌ 类型错 |
| `Banners` | **7 条**（首条 `BannerId=103869`） | 空 | ❌ 内容全空 |
| `Notices` | **6 条**（首条 `NoticeId=103865`「家具互动更新」） | 空 | ❌ 内容全空 |
| `Events` | **14 条**（含 **5 条「限时招募」**） | 空 | ❌ 内容全空 |
| `Issues` | `[]` | `[]` | ✅ |
| 漏发键 | — | 漏 `SessionKey` / `RequestId` / `Survey` | ❌ |
| 多发键 | 官方从不发 | `ContentLock` / `StaticOpenConditions` / `MissionProgressDBs` / `EventMissionProgressDBDict` / `BattlePassMissionProgressDBDict` | ❌ |

**证据**：`MANAGEMENT_DATA_90004.md`（官方 10 份 90004 明文逐字段比对，只有 `Banners[*].CreateTime` 每次不同，结构与条数 10/10 稳定）；`work\ba\server\deploy\_p90004\90004_ops.json`（修复后实际安装的数据文件，9 键：6 / 14 / 0 / 7 / 12 / 0 / null / null / null）；`D90004_DEPLOY.md` §5（31 项检查逐条 PASS）。

一句话概括这次错误：**不是「值写小了」，是「结构写错了 + 内容写空了」。**（`MANAGEMENT_DATA_90004.md` §0）

### 1.3 为什么这份数据会决定整个招募面板

客户端侧最直接的因果印证来自用户的实际观察，这条比任何静态分析都硬：

> 玩官服时进游戏会弹一个公告，比如「某某限时招募开启」；改成私服之后这个公告就不弹了。

也就是说：**招募界面依赖的是这一份「运营公告 / 横幅 / 概率公示数据」，不是卡池清单。** 90004 正是这份运营数据的唯一来源——请求侧没有任何运营参数（`06_90004_api_management_data.request.json` 只有 `Protocol/Resendable/Hash/IsTest/SessionKey/AccountId/OSType`），服务端必须自己给出全部内容（`MANAGEMENT_DATA_90004.md` §1 证据 D 后的一段）。

链条可以概括为：

```
90004 的 Data 缺失/形状错
  → 客户端拿不到 Notices(公告) / Banners(横幅) / Events(限时招募条) / GachaProbabilityDisplay(概率公示页)
  → 招募面板各子部件没有可绑定的展示数据
  → 回落到「No LocalizeKey」静态兜底串 + `DUMMY` 占位页签 + 十连按钮无有效池可绑定（所以连本地提示都不出）
```

排查史里的第 1～4 条（§3）正是把这根链条的**其他候选上游**逐个排除掉的：卡池行一致、客户端 DTO 一致、客户端表全新——那么剩下的唯一变量就是这层运营数据。

**证据等级说明**：因果已由「补数据 → 界面恢复」的单变量验证钉死（§2）；但「面板内部具体哪个控件读哪个字段」的代码级细节**没有逐帧验证**（release 包不写 Unity 日志，见 §3 第 10 条），因此上面第三行是实证推断而非反汇编结论。

### 1.4 为什么这个 bug 会「长期」存在

仓库里**早就有正确实现**：`dto90004.py`（2026-11-16 05:21，8,891 B）逐条记录了官方 9 键形状和这 4 处类型错，`patch_90004.py` 负责把它内联进桥，`deploy_all.py` 也把它登记进了补丁链（L142-147）。**但当时所有在跑的桥快照里这个补丁都不见了**，线上桥里留着的仍是那 16 键平铺桩。所以这不是「不知道正确答案」，而是「正确答案没进生产」。

**证据**：`MANAGEMENT_DATA_90004.md` §4；`D90004_DEPLOY.md` §1（改前线上 `account_auth_probe.py` 222,539 B / `md5 da07749d…` / `sha256 fd6ba5d8…`，`_ba_state/90004_ops.json` **不存在**）。

---

## 2. 修复过程

**修复方式：纯数据 + 一个桥补丁。不改协议号、不改信封、不动卡池、不动 APK。**

| 项 | 内容 | 证据 |
|---|---|---|
| 补丁器 | `work\ba\server\deploy\patch_90004.py`（配 `dto90004.py`，把官方形状内联进 90004 分支） | `D90004_PATCH_PREP.md`、`D90004_DEPLOY.md` §2 |
| 数据来源 | 官方抓包 `report\_tmp\official_decoded_201\06_90004_api_management_data.response.json` 的 `inner.Data` **原样抽出** | `MANAGEMENT_DATA_90004.md` §1 |
| 安装位置 | `/www/wwwroot/bapatch/_ba_state/90004_ops.json` | `D90004_DEPLOY.md` §2 |
| 数据体积 / 校验 | **10,883 B**，sha256 `938ae90855b5fa5fa11342854f2e0f28e7130b466c303621151685efc06107fb` ✅ 现场复核一致 | 本次复核 `_p90004\90004_ops.json`；`D90004_DEPLOY.md` §2 |
| 字节变化 | 90004 响应 **2,092 B → 14,016 B**（官方同批 14,124 B，差异仅来自 `SessionKey` 空值与时间戳） | `D90004_DEPLOY.md` §5 |
| 验证 | **31/31 PASS**（6 顶层键 / 键序 / 9 个 Data 键 / 条数 6-14-0-7-12-0 / 3 个 null / 无旧 16 键残留），FAIL=0，唯一 WARN 是未登录时 `SessionKey` 为空 | `D90004_DEPLOY.md` §5 |
| 回归 | `Account_Auth(1002)` 200 无 ErrorCode；`LoginSync(1019)` 586,907 B / `ShopRecruits` 仍 **529 条**；`Mail_Check(7001)` 200；SELFCHECK PASS | `D90004_DEPLOY.md` §6 |
| 未触碰 | nginx / 数据库 / `Shittim-Server.dll` / `Data/*.json`（卡池仍 529 条）/ `ClientItemIds.txt` | `D90004_DEPLOY.md` §9 |
| 回滚 | `/root/D90004_20261119_021229/ROLLBACK.sh`（还原桥；改前无 ops，故回滚会删掉 `_ba_state/90004_ops.json` 并重启） | `D90004_DEPLOY.md` §8 |

**时间线（2026-11-19）**

| 时刻 | 动作 | 依据 |
|---|---|---|
| 02:04 | 备份线上桥 | `_p90004\account_auth_probe.py.bak.90004.20261119-020421` |
| 02:08 | 打补丁 + verify + ast 检查 | 同目录 `_v222486` 备份；`patch_90004.py --verify PASS` |
| 02:12 | 覆盖线上桥、重启、跑 31 项验证 | 备份目录 `D90004_20261119_021229`；`9097_UP 1,033 ms` |
| **02:15** | **真机进入招募界面，验收通过** | 用户真机验收（本文件 §6 为准） |

**运维注意**：新分支在**读不到 ops 文件**时会退回「列表全空 + 3 个 null」的**合法新形状**——不会崩、不会报错，但界面会**原样坏回去**。这正是「文件还在不在」必须在验收里单独确认的原因（`D90004_DEPLOY.md` §10）。

---

## 3. 排查史（已证伪清单，别重复）

这张表是本次最省时间的资产：**下面 12 个方向已经用实验或数据排除，再查是浪费**。

| # | 方向 | 一句话结论 | 证据文件 |
|---|---|---|---|
| 1 | 我们下发的卡池数据是不是和官方不一样 | **逐字段差 0**，卡池数据本身完全一致，排除 | `OUR_VS_OFFICIAL_SHOPRECRUITS.md` |
| 2 | 页签数量是不是由 `ShopRecruits` 条数驱动 | 单变量实验：529 条 → 1 条，**页签反而多一个** ⇒ 页签不由 `ShopRecruits` 驱动 | `BANNER1_DEPLOY.md` |
| 3 | 回空数组能不能强制服务端不下发 | 不能。回 `[]` 会**回落到服务端 Excel 的 714 条日服卡池** | `BANNER0_DEPLOY.md` |
| 4 | 客户端招募 DTO 是不是缺字段 | 客户端 `ShopRecruitDB` 只有 4 个字段，我方**一个不缺**；招募 DTO 里**没有任何本地化字段** | `CLIENT_SHOPRECRUIT_DTO_VS_OURS.md` |
| 5 | 是不是语言 / 区域字段没发 | 我方没发，**官方也没发**，两侧一致，排除 | `LANGUAGE_FIELD_DIFF.md` |
| 6 | `ServerNotification: 8` 是不是错误码 | 是 `HasUnreadMail` **全局红点**，不是错误码；官方只在邮件协议上带 | `PICKSEL_FIX.md` §5 |
| 7 | 是不是响应壳（信封）不齐 | 已做：每条回 `SessionKey`、`ServerNotification` 收窄——**做了但没修好招募** | `ENVELOPE1_DEPLOY.md`、`ENVELOPE_ALIGN.md` |
| 8 | 是不是客户端表旧 / 没下成 | 手机 `ExcelDB.db` **全新且正确**：160,534,528 B / `824ce3a8…`，2026-11-19 01:00；`catalog_Remote.json` 也是当天新下 ⇒ 排除 | `work\ba\phone\ADB_WIRELESS_20261119.md`、`CATALOG_RE_DOWNLOAD_CHECK.md` |
| 9 | 是不是缺 Localize bundle | 客户端 `AssetBundles` 里**没有任何 Localize bundle** ⇒ 11-17 那份「缺 Localize bundle」的判断**作废** | `work\ba\server\deploy\_blackout\srv\CATALOG_VERSION_20261117.md` |
| 10 | 抓 logcat 看客户端报错 | 这条路走不通：release 包不写 Unity 日志，**58 MB 全量里游戏进程命中 0 行** | `RECRUIT_LOG_FORENSICS_20261119_0124.md` |
| 11 | 库里有没有 GachaShop 主表 / 两套 id 的映射表 | 全库 **398 张表**里没有 GachaShop 主表、没有两套 id 的映射表；`ShopRecruit` 的 532 个 id **100%** 被 `LocalizeGachaShop` 覆盖 | `ALL_GACHA_TABLES_SCAN.md` |
| 12 | 是不是 APK 被人动过 / 表被换 | APK 是干净的：`resources.arsc` sha256 `cd8943ae…`，**41,301/41,307** 条目与官方一致，只改了登录 SDK / 服务器地址 | `APK_TABLE_INTEGRITY.md` |

补充：`NOLOCALIZEKEY_ORIGIN.md` / `NOLOCALIZEKEY_XREF.md` / `LOCALIZE_KEY_DIFF.md` 三份把「`No LocalizeKey` 这个字符串从哪来、查的哪张表、key 是什么」钉到了方法级（`UIGachaInfo.SetData` → `ShopData::GetGachaTitleNameString` → `localizeGachaShopDic`，key = `ShopRecruitExcel::get_Id()`）。这些**不是错的方向**，但它们是「症状解释」而不是「根因」——真正的缺口在 90004，见 `MANAGEMENT_DATA_90004.md` §0。

---

## 4. 下一个问题：换期怎么同步

当前 90004 数据是 **2026-11-18 官方抓包**，档期到 **2026-11-26 13:59:59**（`Notices` / `Events` / `GachaProbabilityDisplay` 相关条目 `EndDate`，见 `_p90004\90004_ops.json`）。档期一过，**招募界面很可能再次变回坏的状态**：客户端拿到的是新池子，而 `Data` 里对应的公告 / 横幅 / 公示页还是旧的、甚至对不上。

### 4.1 哪些东西会随期变化、各自的数据来源在哪

| 数据 | 是什么 | 存在哪 | 随期变化？ | 谁更新 |
|---|---|---|---|---|
| 卡池本体行 `ShopRecruit` / `LocalizeGachaShop` | 池子本身 + 中文标题 / 说明文案 | **客户端的 ExcelDB**（客户端从官方 CDN 下载，跟随官方表版本） | 是（跟官方表版本走） | **官方**，客户端自动同步；我们不需要动 |
| 运营数据：公告 / 横幅 / 概率公示页 / 活动条 | `Notices` / `Banners` / `Events` / `GachaProbabilityDisplay` / `GuidePopup` / `GachaPeriodDisplay` / `RaidPeriodDisplay` / `Survey` | **`/www/wwwroot/bapatch/_ba_state/90004_ops.json`** | 是（档期驱动，整份换） | **我们自己的数据文件**，手工换 |
| 卡池清单 `ShopRecruits`（**529 条**） | 招募界面能看到的池子列表 | 桥的 `Data/*.json` → 1019 登录响应 | 否（与官方历史全量一致） | 基本不动 |

**这就是为什么「卡池对得上」不等于「界面正常」**：卡池行在客户端，界面文案与入口图在 90004。两者靠 `LinkedLobbyBannerId` 之类的 join 键对齐（7 条 `Banners` 里有 5 条的 `LinkedLobbyBannerId`（5004670/5004680/5004690/5004700/5004710）直接出现在 12 条 `GachaProbabilityDisplay` 条目里，见 `_p90004\90004_ops.json`）——**换期时对不上的就是这层 join**。

### 4.2 换期要更新的到底是什么

**核心只有一件事：替换 `_ba_state/90004_ops.json` + 重启桥。纯数据，不改代码、不改协议、不动卡池。**

- 不需要重打补丁：`patch_90004.py` 已经把「读 ops 文件、拼 `Data`」的逻辑写进桥里了（`D90004_DEPLOY.md` §2、§10）
- 不需要动客户端：卡池行由客户端自己从官方 CDN 同步（§4.1）
- 不需要动 `ShopRecruits`：529 条与官方历史全量一致
- 重启是「确保新文件被加载」的最稳妥口径；成本极低，顺带还能清掉残留实例

### 4.3 换期数据的三个获取途径 + 取舍

| 途径 | 能拿到什么 | 成本 | 风险 | 适用 |
|---|---|---|---|---|
| **(a) 官方抓包** | 最准：真实的公告 `NoticeId`/`Url`/`Title`/`DisplayOrder`、真实 banner 图 CDN 与 `LinkedLobbyBannerId`、真实公示页 URL | **需要官方账号，或一份覆盖新档期的 HAR**（本次来源即 201 entries / 10 次 90004 的抓包，`MANAGEMENT_DATA_90004.md` §1） | 几乎无（结构可直接照抄，只要抓包落在新档期内） | 首选。有账号 / 有 HAR 就走这条 |
| **(b) 用客户端表生成** | `LocalizeGachaShop` 里有中文标题/说明文案，`ShopRecruit` 里有开闭档期，可离线拼出 `Events` / `Banners` / `GachaProbabilityDisplay` 的**骨架** | 零账号成本，可脚本化（本次不做，仅列为方向） | **join 键风险**：`LinkedLobbyBannerId` 必须和客户端对得上；`GachaProbabilityDisplayId` 在官方 12 条里**恒为 2**（不是池子 id），无法从表里推；`Url` 必须指向真实存在的静态公示页，编不出来。**必须真机验证** | 没有抓包时的主力方案 |
| **(c) 手写一版占位** | 几条公告 / banner / 公示页凑出一个「看起来非空」的 `Data` | 最快 | 最容易又被客户端判成「查不到」：条数、键名、类型任一不符就退化；写少了等于没修 | 池子极少、临时救急 |

**推荐顺序：`(a) > (b) > (c)`。**

- **(a) 优先**：这次能结案，靠的就是「原样抄官方」——`inner.Data` 一个字段不改地抽出来（§2）。官方数据自带正确的 join 键和真实 URL，风险最低，也最不容易在换期后二次踩坑。
- **(b) 次选**：文案和档期都能从客户端表里拿到（`LocalizeGachaShop` 有中文、`ShopRecruit` 有档期，§3 第 11 条已验证 `532` 个 id 100% 被覆盖），所以**内容**不缺；缺的是 `LinkedLobbyBannerId` / 公示页 URL 这类**服务端侧 join 与静态资源**，只能靠真机验证补齐。适合「有表、没账号」的常态。
- **(c) 兜底**：只适合池子少、并且愿意承担「改完还是坏」的概率。它不解决 join 问题，只是把空数组换成假数组。

> 一个必须知道的事实：`GachaProbabilityDisplay` 的 12 条 URL 都在 `notice.bluearchive-cn.com/static/gacha/*.html`，是公网静态页。只要那些页面还在，玩家点「注意事项」就能打开；若哪天 404，就得自己镜像同样的静态页并把 `Url` 换掉（此为推断，未实测）。

---

## 5. 换期操作清单（给运维，5 步）

> 前提：新数据文件已按 §4.3 的 (a) 或 (b) 准备好，9 键齐全、键名与官方一致。

| 步 | 动作 | 具体做法 | 通过标准 |
|---|---|---|---|
| 1 | **备份现有数据** | 把 `/www/wwwroot/bapatch/_ba_state/90004_ops.json` 复制为 `90004_ops.json.bak.<日期_时刻>`（保留旧档期，出问题第一时间换回） | 备份文件存在且体积为 10,883 B 量级 |
| 2 | **放新文件** | 上传覆盖 `/www/wwwroot/bapatch/_ba_state/90004_ops.json`，权限 644、属主 root | 线上文件 sha256 与本地新文件一致 |
| 3 | **校验 JSON 与条数** | `cd /www/wwwroot/bapatch/_ba_state` 后用 `python3 -c` 读一遍该文件，打印 9 个键的类型与条数 | JSON 可解析；`Notices/Events/Issues/Banners/GachaProbabilityDisplay/GuidePopup` 为数组、`GachaPeriodDisplay/RaidPeriodDisplay/Survey` 为 `null`；条数符合新档期预期（旧基线是 6/14/0/7/12/0） |
| 4 | **重启桥** | `cd /www/wwwroot/bapatch/tools` → 停旧进程 → `umask 007 && setsid nohup python3 account_auth_probe.py &` → 轮询 9097 端口 | 9097 起来、实例数 = 1、启动日志无异常 |
| 5 | **打一次 90004 验收** | 对 `http://127.0.0.1:9097/api/management/data` 发一次请求并解码 | HTTP 200；`Data` 9 键齐全；`Banners` / `Events` / `GachaProbabilityDisplay` 条数与新文件一致；体积回到 13～15 KB 量级（不是 2 KB） |

**出事怎么退**：把第 1 步的 `.bak` 换回去 → 重做第 4、5 步。若连桥也动过，用 `/root/D90004_20261119_021229/ROLLBACK.sh`（`D90004_DEPLOY.md` §8）。

**时机**：务必在 **2026-11-26 13:59:59** 之前完成，别等过期后再补——过期后客户端拿到新池子、`Data` 还是旧档期，界面会先坏一段时间。

---

## 6. 验收标准

### 6.1 真机（人眼，唯一权威）

| # | 检查项 | 通过标准 |
|---|---|---|
| 1 | 进入招募界面 | 能正常进入，不卡加载 |
| 2 | 页签 | **无 `DUMMY`**，显示正常页签名 |
| 3 | 面板文案 | **无红色 `No LocalizeKey`**（标题 / 说明 / 点数说明 / 底部按钮四处都要看） |
| 4 | 十连按钮 | **可点**，点击有反馈（能抽 / 有明确提示），不再是「点了毫无反应」 |
| 5 | 「注意事项」 | **能打开**，内容非空白 |

### 6.2 服务端（机器可核对，先于真机跑）

| # | 检查项 | 通过标准 | 依据 |
|---|---|---|---|
| 1 | 90004 HTTP | 200，体积 13～15 KB（旧坏态 2,092 B） | `D90004_DEPLOY.md` §5 |
| 2 | 顶层键 | 6 个且键序固定：`Protocol → SessionKey → ServerTimeTicks → ServerNotification → RequestId → Data` | 同上 |
| 3 | `Data` 键 | 9 个，键序固定：`Notices → Events → Issues → Banners → GachaProbabilityDisplay → GuidePopup → GachaPeriodDisplay → RaidPeriodDisplay → Survey` | 同上 |
| 4 | 类型 | `Banners/Notices/Events/Issues/GachaProbabilityDisplay/GuidePopup` = 数组；`GachaPeriodDisplay/RaidPeriodDisplay/Survey` = `null` | 同上 |
| 5 | 条数 | 与换期数据文件一致（旧基线 6/14/0/7/12/0） | 同上 |
| 6 | 无残留 | 无 `ContentLock` / `StaticOpenConditions` / `MissionProgressDBs` / `EventMissionProgressDBDict` / `BattlePassMissionProgressDBDict` | 同上 |
| 7 | 登录回归 | `Account_Auth(1002)` 200 无 ErrorCode；`LoginSync(1019)` 正常且 `ShopRecruits` = **529 条**；`Mail_Check(7001)` 200 | `D90004_DEPLOY.md` §6 |

**判定口径**：6.2 全过 + 6.1 全过 = 换期成功。只过 6.2 不过 6.1，说明 `Data` 结构对了但内容与客户端 join 不上，回 §4.3(b) 补 join 键。

---

## 7. 未解事项与边界（写清楚，免得下个人重查）

1. **客户端代码级机制未逐帧验证**：面板哪个控件读 `Data` 的哪个字段，没做到指令级（release 包不写 Unity 日志，§3 第 10 条）。因果由「补数据即恢复」确认，不是由反汇编确认。
2. **`GachaProbabilityDisplayId` 恒为 2**（官方 12 条全一样），含义未知；它是分组 id 还是版本号没有证据，换期时照抄即可、别试图推导。
3. **`LinkedLobbyBannerId` 的取值空间未知**：官方出现过 5004670/5004680/5004690/5004700/5004710/10838 这类值，也出现过 8000004/7000000/90000000/99999999/10000000（疑似特殊池/自选池）。哪些是必填、哪些可省，只能用真机逐档验证。
4. **官方是否会在非档期日调整 `Data` 结构未知**：本次 10 份抓包结构 10/10 稳定，但只覆盖同一批抓包里的 10 次调用（约 4 分钟窗口，`Banners[*].CreateTime` = `2026-11-16T04:30:55`，`MANAGEMENT_DATA_90004.md` §1 证据 D）。若哪天官方加键/改类型，照抄抓包仍是最稳的做法。
5. **回空数据的后果已实测**：`[]` 不会让服务端不下发，而是回落到服务端 Excel 的 714 条日服卡池（§3 第 3 条）——换期做实验时别再用这条当「关闭开关」。

---

## 8. 本次新增 / 相关的文档清单

### 8.1 本次新增

| 文件 | 位置 | 作用 |
|---|---|---|
| **`GACHA_ROOTCAUSE_90004_FINAL.md`**（本文件） | `work\ba\plan\20261119\` | 根因结案 + 已证伪清单 + 换期同步方案 + 运维清单 + 验收标准 |

### 8.2 根因与修复（直接证据）

| 文件 | 位置 | 关键内容 |
|---|---|---|
| `MANAGEMENT_DATA_90004.md` | `work\ba\plan\20261119\` | 官方 10 份 90004 明文 vs 我方桩的逐字段比对；§4 记录「补丁存在但没进生产」 |
| `D90004_DEPLOY.md` | `work\ba\plan\20261119\` | 部署记录：改前基线、31/31 验证、2,092→14,016 B、回滚 |
| `D90004_PATCH_PREP.md` | `work\ba\plan\20261119\` | 补丁准备与预检（23 行 / 16 键 / `has Data=False`） |
| `NOLOCALIZEKEY_ORIGIN.md` | `work\ba\plan\20261119\` | `No LocalizeKey` 字符串来源与调用链 |
| `NOLOCALIZEKEY_XREF.md` | `work\ba\plan\20261119\` | `UIGachaInfo.SetData → GetGachaTitleNameString → localizeGachaShopDic` 的方法级定位 |
| `LOCALIZE_KEY_DIFF.md` | `work\ba\plan\20261119\` | 本地化 key 全集差异 |
| `90004_ops.json`（10,883 B / `938ae908…`） | `work\ba\server\deploy\_p90004\` | 实际安装的运营数据（本地副本，线上在 `_ba_state/`） |
| `06_90004_api_management_data.response.json` | `report\_tmp\official_decoded_201\` | 官方抓包原始明文，换期照抄的模板 |

### 8.3 已证伪方向（§3 的证据文件）

| 文件 | 对应 §3 条目 |
|---|---|
| `OUR_VS_OFFICIAL_SHOPRECRUITS.md` | 1 |
| `BANNER1_DEPLOY.md` | 2 |
| `BANNER0_DEPLOY.md` | 3 |
| `CLIENT_SHOPRECRUIT_DTO_VS_OURS.md` | 4 |
| `LANGUAGE_FIELD_DIFF.md` | 5 |
| `PICKSEL_FIX.md`（§5） | 6 |
| `ENVELOPE1_DEPLOY.md` / `ENVELOPE_ALIGN.md` | 7 |
| `work\ba\phone\ADB_WIRELESS_20261119.md` / `CATALOG_RE_DOWNLOAD_CHECK.md` | 8 |
| `work\ba\server\deploy\_blackout\srv\CATALOG_VERSION_20261117.md` | 9 |
| `RECRUIT_LOG_FORENSICS_20261119_0124.md` | 10 |
| `ALL_GACHA_TABLES_SCAN.md` | 11 |
| `APK_TABLE_INTEGRITY.md` | 12 |

### 8.4 背景资料（供换期时参考）

`GACHA_INVESTIGATION_20261119.md`、`OPEN_BANNERS_NOW.md`、`OFFICIAL_PICKSEL_PROTOCOL.md`、`PICKSEL_LIVE_TRACE.md`、`SHOPLIST_NRE_FIX.md`、`SHOPLIST_CATEGORY38_ANALYSIS.md`、`GACHA_CANDIDATE_LIST_V2.md`、`EXTERNAL_RESEARCH_GACHA_UI.md`、`LOGINSYNC_ENVELOPE_DIFF.md`、`OFFICIAL_SHOPLIST_SHOPRECRUITS_CHECK.md`（均在 `work\ba\plan\20261119\`）。
