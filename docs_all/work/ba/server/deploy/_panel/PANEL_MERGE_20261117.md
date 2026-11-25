# 卡密站 × 玩家站 合并 · 施工与验收（2026-11-17 22:0x）

> 用户指令：**「把 PHP 卡密管理站和这种玩家管理站融合到一起，能实现的功能都要实现」**
> 执行：Lead 决策 + 改代码；`srv-ops` 只负责上传/重启/取证；`shittim-analyst` 只读源码出契约。
> 纪律：不碰 nginx（宝塔会重写 .conf）、不碰 WAF、不碰 MITM 证书、不直接写 `shittim.sqlite3`。

---

## 0. 一页结论

**原来以为"面板要新写一套 admin API（装 .NET SDK、写 C#、跨账号发奖做不到）"——全是多余的担心。Shittim 源码里本来就有一套 28 个端点的 `api/admin`，只是我们没用它。**

同时挖出 **4 个会让面板"看起来能用、实际全是错的"的根因 bug**，全部在 C# 侧、全部是几行以内：

| # | 位置 | 症状（如果不管它） | 修法 |
|---|---|---|---|
| 1 | `MailManager.cs` `SendSystemMailWithParcels` / `SendSystemMailMultipleParcels` | **面板发的每一份奖励，客户端都显示 0、领了也等于空** | `ParcelInfo` 补 `Multiplier = BasisPoint.One`、`Probability = BasisPoint.One` |
| 2 | `AdminAuthAttribute.cs` | **`[AdminAuth]` 形同虚设**：反代后 RemoteIp 恒为 127.0.0.1 ⇒ 环回免密钥 ⇒ 公网可打（实测 200 + 真实账号数据） | 配了 key 就**强制**校验，不再因为环回而放行 |
| 3 | `AdminController.GetAccounts` | 面板拿不到 `PublisherAccountId`，**卡密 ↔ 玩家永远是两张皮** | 投影加 `PublisherAccountId / State / VIPLevel / LastConnectTime / CreateDate / UnReadMailCount / CallName` |
| 4 | `AccountState` 全局 | **根本没有封禁概念**：`State` 没有任何一处被读来做门禁，改了客户端毫无反应 | `CheckNexon` + `CheckYostar` 两处加 `Dormant` 门禁；`UpdateAccountRequest` 加 `State` |

**架构定案**：PHP 面板**直连** `127.0.0.1:5000/api/admin/*`（同机环回 + `X-Admin-Key`），写操作全部落到 Shittim 自己的 EF Core。**不新建 Python 中间层，不直写 SQLite。**

---

## 1. 为什么不是"新写一套后端"

`ADMIN_PANEL_SPEC.md §4.1` 当时判定：「GM 命令全部绑定当前控制台账号，**没有 target 入参** ⇒ 给任意玩家发东西做不到」，于是规划了"装 .NET SDK + 新写 admin API"。

源码实测推翻了这条（`_panel/ADMIN_API_CONTRACT.md §6.2`）：

```csharp
// ManagementController.cs:445
var connection = _webService.GetClient(request.Uid, writer);   // Uid 直接就是 AccountServerId
// WebConnection.cs:31
AccountServerId = _accountServerId;                            // 直通，与 account/select 无关
```

⇒ `POST /api/admin/command {Uid, Command}` **自带目标账号**，跨账号操作从一开始就是通的。

**28 个端点分布**（`[Route("api/admin")]` + `[AdminAuth]`，无 `UsePathBase`）：

- `AdminController`（4）：`mail/send`、`currency/set`、`accounts`、`account/{id}/currencies`
- `ManagementController`（24）：`status`、`account/{id}/detail|items|characters|mails`、`account/create|update|delete|select|selected`、`items/give|remove`、`mail/delete`、`command`、`static/items|characters|equipment|currencies`、`meta/parceltypes`、`gacha/config|banners`、`events/seasons|schedule|unlocks|unlock`、`notice`

---

## 2. C# 侧改动（4 处补丁，全部带 `BAPATCH-*` 标记，便于 grep 与回滚）

### 2.1 `BAPATCH-MAILPARCEL` · `Services/MailManager.cs`

`ParcelInfo.MultipliedAmount` 是**计算属性**：`Amount * Multiplier`，而 `Multiplier` 是 `BasisPoint` 结构体，默认 `RawValue=0`。
`SendSystemMailMultipleParcels` 构造包裹时只设了 `Amount`，没设 `Multiplier` ⇒ 客户端算出来的奖励是 0。

上游自己的 `ClanHandler.cs:188` 就是踩了这个坑才写下注释：

> `official's mail carries both at rawValue 10000 (= 1x). left at the struct default they are 0, which the serializer drops as a default and which makes the client's own MultipliedAmount (Amount * Multiplier) render the reward as zero ActionPoint.`

修法（两处，各 3 行）：补 `Multiplier = BasisPoint.One, Probability = BasisPoint.One`，并加 `using Schale.MX.Core.Math;`。

> **这条是整件事的关键**：不修它，「一键批量发奖」会变成「一键批量发空包」，而且**面板侧完全看不出异常**（HTTP 200、邮件也进了邮箱）。

### 2.2 `BAPATCH-ADMINAUTH` · `Controllers/AdminAuthAttribute.cs`

**实测漏洞**（srv-ops 2026-11-17 22:0x，只读）：

```
https://example.com/api/admin/status   → 200
https://example.com/api/admin/accounts → 200 + 真实账号数据
```

成因链：`example.com.conf` 没有 `/api/` 专门转发 ⇒ 落到 `location ^~ / { proxy_pass 127.0.0.1:5000; }`
⇒ Shittim 的 `[AdminAuth]` 判断"环回"（反代后 `RemoteIp` 恒为 127.0.0.1）⇒ 免密钥放行。
`Config.json` 里 `AdminApiKey` 存在但**长度为 0**，所以那条"配了 key 就要 key"的分支根本没生效。

修法：`configuredKey != null` 时**只认 key**，不再回落环回；`configuredKey == null` 时保持原来的"仅环回"语义。
这样**不需要改 nginx**（也就不会被宝塔面板重写掉），只靠代码 + 一个 64 位随机 key 就把洞堵死。

### 2.3 `BAPATCH-ROSTER` · `Controllers/AdminController.cs` `GetAccounts`

原来只 select 5 个字段，且把"有 DevId 的账号"过滤掉（为了藏 Schale AI 助手）。
`DevId` 我们查过：**全工程只有 `AronaAI`/`GameClientHelper` 会写**，玩家账号永远是 NULL ⇒ 那个过滤**没有误伤玩家**，保留。

改动只有一件事：投影补 `PublisherAccountId / CallName / State / VIPLevel / LastConnectTime / CreateDate / UnReadMailCount`。

> **踩到一个 EF 的坑**：`State = a.State.ToString()` 写在 `IQueryable.Select` 里没有 SQL 翻译，运行时会抛。
> 必须 `.ToList()` 物化之后再投影。（`ManagementController.AccountDetail` 之所以能这么写，是因为它前面已经 `FirstOrDefaultAsync` 物化过了。）

### 2.4 `BAPATCH-BAN` · `AccountHandler.cs` × 2 + `ManagementController.UpdateAccountRequest`

`AccountState` 只有 `WaitingSignIn/Normal/Dormant/Comeback/Newbie`，**全工程零处读它做门禁**（其它 `.State ==` 命中全是 EF 的 `EntityState`）。
所以"封号"在这一版里**根本不存在**——改 State 客户端毫无反应。

修法（不新增枚举值，避免动 FlatBuffers 自动生成的 `AccountState.cs`）：
- `CheckNexon` 与 `CheckYostar` **两个登录入口**都在 `GenerateSession` 之前加：
  `if (loginAccount.State == AccountState.Dormant) throw new UnauthorizedAccessException("ACCOUNT_SUSPENDED");`
- `UpdateAccountRequest` 加 `int? State`，落到 `a.State = (AccountState)value`

⇒ `Dormant(2)` 被借用为"封禁"。语义代价：`Dormant` 在原作里是"休眠号"，但这一版**没有任何代码写它**，所以没有冲突。

---

## 3. 面板侧（PHP，在现有卡密站上扩，卡密逻辑一行没动）

线上站点：`https://<SERVER_IP>`（`<SERVER_IP>.conf`，root `/www/wwwroot/ba_cardadmin`，PHP 8.1.35，MySQL 5.7.43，库 `ba_cardadmin`）。

### 3.1 数据分工

```
浏览器 ──HTTPS──> PHP 面板（/www/wwwroot/ba_cardadmin）
                    ├─ MySQL ba_cardadmin          卡密 / 设备 / 管理员 / 审计（现有，逻辑不动）
                    ├─ MySQL 新表 card_players     卡密 ↔ 玩家 绑定（面板自建）
                    ├─ MySQL 新表 panel_ops        玩家域写操作批次（发奖/改货币/封禁/GM）
                    ├─ SQLite accounts.db(只读)     桥接账号镜像：设备号 / 登录次数 / dev_id
                    └─ HTTP 127.0.0.1:5000/api/admin/*  ← 唯一写入通道（Shittim EF Core）
```

`accounts.db` 可读（`/www/wwwroot/bapatch/data/accounts.db`，`www` 有读权限），`/root/shittim.sqlite3` **不可读**（`/root` 是 700），也不需要读。

### 3.2 新增/改动的文件

| 文件 | 作用 |
|---|---|
| `inc/ba.php` | Shittim admin API 客户端：curl/stream 双实现、超时、`X-Admin-Key`、静态数据磁盘缓存、统一错误形状 |
| `inc/players.php` | 玩家域聚合：账号 roster（合并桥接镜像与卡密绑定）、`card_players` / `panel_ops` 自建表、封禁封装 |
| `inc/helpers.php` | **改动**：`nav_items()` 加三组（玩家 / 卡密 / 系统），`page_header()` 支持分组标题 |
| `assets/app.css` | **改动**：追加 `.nav-group` / `.tbl-players` / `.bulkbar` / `.cur-grid` / `.parcel-row` / `.cmd-out` / `.srv-down` |
| `pages/players.php` | 全部玩家、状态/卡密筛选、搜索、批量勾选、批量封禁/解封、批量发奖入口 |
| `pages/player_detail.php` | 资料/货币/角色/邮件/卡密/封禁/GM 命令，一页打尽 |
| `pages/mail.php` | 发奖：单选/多选/全服、发件人、内容、有效期、**多附件混搭**、4 个快捷模板、批次历史 |
| `pages/currency.php` | 批量改货币：设为 / 增加 / 减少，逐人显示 旧值→新值 |
| `pages/items.php` | 发道具（叠加/覆盖）+ 9 个快捷动作（全角色/满级/全装备/五种解锁）+ 静态数据查 Id |
| `pages/console.php` | GM 命令台：多人执行、输出着色、22 条命令参考、最近命令 |
| `pages/dashboard.php` | **改动**：加服务端健康、注册玩家、今日活跃、已绑卡密、封禁数、玩家快捷入口、最近活跃玩家 |
| `pages/settings.php` | **改动**：加「游戏服务端（玩家域）」区：连通状态、Admin Key（脱敏）、桥接账号库、PHP 扩展自检、连接设置表单、清缓存 |

### 3.3 功能对照（用户要的 8 项 + 额外）

| # | 需求 | 落地 | 入口 |
|---|---|---|---|
| 1 | 显示全部用户 | `GET /api/admin/accounts` + 桥接镜像 + 卡密绑定 | 玩家列表 |
| 2 | 按类型筛选 | 状态（正常/封禁/…）+ 只看有卡密 + 关键词（昵称/ServerId/卡密/设备/publisherId） | 玩家列表 |
| 3 | 一键批量发奖励 | 多选 → `POST /api/admin/mail/send`，多附件混搭 | 发奖 / 邮件 |
| 4 | 封号 / 解封 | `POST /account/update {State}` + 登录门禁 | 玩家列表 / 详情 |
| 5 | 改绑定台数 | ⚠️ **未做**（需 `max_devices` + 改 `sync.php` + 改 `sdkcard.py`，见 §6） | — |
| 6 | 查货币 / 角色 | `/account/{id}/detail` + `/currencies` + `/characters` | 玩家详情 |
| 7 | 发补偿 | 同 #3（批次记录进 `panel_ops`，可按 `batch_id` 追溯） | 发奖 / 邮件 |
| 8 | 玩家维度综合平台 | 玩家列表 + 详情 + 发奖 + 货币 + 道具 + GM + 卡密绑定，**与卡密站同一套登录/导航/审计** | 整站 |
| + | 批量改货币 | 设为/增加/减少，逐人回显新旧值 | 货币调整 |
| + | 给道具/装备/角色 | `items/give` + GM 快捷动作 | 道具 / 角色 |
| + | GM 命令台 | `POST /api/admin/command`（Uid=目标） | GM 命令台 |
| + | 删邮件 / 清空邮箱 | `POST /mail/delete` | 玩家详情 |
| + | 静态数据查 Id | `/static/items|characters` | 道具 / 角色 |

### 3.4 附件语义（教训）

- `SendMailRequest.Parcels[].Type` 是**字符串枚举名**（`Enum.Parse<ParcelType>`），`Id` 才是数字
- 青辉石：`{"Type":"Currency","Id":3,"Amount":N}` = 免费石 `GemBonus`；`Id=2` 付费石；`Id=4` 合计（派生）
- `Gem` 是派生值（`Gem = GemBonus + GemPaid`），真写入要落到 `GemBonus`/`GemPaid`；
  `currency/set` 对 `CurrencyType=4` 有内置分支，`ParcelResolver`（GEMGRANT 补丁）对邮件领取有内置分支——两条都安全
- **邮件只是"投递"，不结算**：真正入账发生在玩家在游戏里点领取 → `Mail_Receive` → `ReceiveMail` → `BuildParcel` → `ParcelResolver`

---

## 4. 验收（2026-11-17 22:1x，srv-ops 实测）

| # | 判据 | 结果 |
|---|---|---|
| 1 | 旧 DLL sha = `cd8c5c99…` | ✅ |
| 2 | 新 DLL sha = `adcb1e03bc82b8fcad97a27e2054483f75c0079dd80e799615a76b6b55229377`（2,672,640 B） | ✅ |
| 3 | `AdminApiKey` 长度 64 | ✅ |
| 4 | Shittim 监听 5000/5100/6667 | ✅ 单实例 |
| 5 | 带 key 本机 `GET /api/admin/status` | ✅ 200 |
| 6 | 不带 key 本机 | ✅ **403** + 正确错误体 |
| 7 | **公网 `https://example.com/api/admin/accounts`** | ✅ **403**（裸域同样 403） |
| 8 | `GET /api/admin/accounts` 含 `publisherAccountId`/`state`/`lastConnectTime`/`createDate`/`unReadMailCount` | ✅ |
| 9 | 13 个面板文件 sha256 逐一比对 | ✅ 13/13 |
| 10 | `php -l` 全站 26 个文件 | ✅ 26/26 通过 |
| 11 | MySQL `settings` 三行已写入（key len=64） | ✅ |
| 12 | `sudo -u www curl → /api/admin/status` | ✅ 200 + JSON（php-fpm 视角能拿到数据，面板不会白屏） |
| 13 | `Accounts` 表 State 分布 | ✅ 全部 State=1，无 Dormant，封禁门禁不会误伤 |
| 14 | 面板入口 | ✅ `http://<SERVER_IP>:8081/login.php` → 200 |

**待用户点一次的活体验收（我这层做不到）**：
给 ServerId=2 发 1000 青辉石 → 游戏里领 → `GemBonus` 应 +1000。
这条同时验证 `BAPATCH-MAILPARCEL`（不修的话邮件里会显示 0）。

### 4.1 与原始假设不符的三处（已确认，记录备查）

| 项 | 原以为 | 实测 |
|---|---|---|
| Shittim 配置路径 | `/root/Config.json` | **`/www/wwwroot/ba_srv/Config/Config.json`**（`/root/Config.json` 不存在；里面 `SQLConnectionString` 已是绝对路径 `/root/shittim.sqlite3`） |
| Shittim 启动方式 | `cd /root && dotnet …`（`dotnet` 在 PATH） | **`/root/dotnet10/dotnet /www/wwwroot/ba_srv/Shittim-Server.dll --console --id 2`**（裸 `dotnet` 不在 PATH）；且 `tmux send-keys C-c` 会**销毁整个会话**（窗口里只有这一个进程），重启必须 `kill-session` + `new-session` |
| 面板入口 | `https://<SERVER_IP>` | **`http://<SERVER_IP>:8081`**（vhost `listen 8081`，不监听 443；443 走 SNI 到 MITM 自签证书） |

### 4.2 已知遗留（P2，不影响本轮）

- **P2-1 桥把上游 HTTP 状态码抹平成 200**：经 `gsqc-api` 路径调 `/api/admin/accounts` 返回 `HTTP/2 200` + `content-length: 58` + `{"error":"Admin API requires a valid X-Admin-Key header."}`。**零数据泄露**，但会坑任何靠状态码判断的调用方。
- **P2-2 面板没有 HTTPS 入口**：vhost 只 `listen 8081`。走明文 HTTP，后台密码在链路上是明文。要 HTTPS 就是 nginx 改动，需要另批。
- `nodemodule` 级：`chown -R` 在 `.user.ini` 报 `Operation not permitted`（宝塔锁定该文件，与目标文件无关）。

---

## 5. 回滚

```bash
STAMP=$(cat /root/panel_backup_LATEST.txt)     # 20261117_220711
cp -a /root/panel_backup_$STAMP/Shittim-Server.dll /www/wwwroot/ba_srv/Shittim-Server.dll
cp -a /root/panel_backup_$STAMP/ba_cardadmin /www/wwwroot/
cp -a /root/panel_backup_$STAMP/Config.json /www/wwwroot/ba_srv/Config/Config.json
tmux kill-session -t shittim
tmux new-session -d -s shittim -c /root
tmux send-keys -t shittim "/root/dotnet10/dotnet /www/wwwroot/ba_srv/Shittim-Server.dll --console --id 2" Enter
# 可选：删掉面板新增的两张表（不删也不影响卡密功能）
mysql ... ba_cardadmin -e "DROP TABLE IF EXISTS card_players, panel_ops;"
```

旧 DLL：`cd8c5c99482ec810f047a30f655bfbe04fda5dc267c4b9ea8747a6b735700a9f`
新 DLL：`adcb1e03bc82b8fcad97a27e2054483f75c0079dd80e799615a76b6b55229377`
备份戳：`20261117_220711`（`/root/panel_backup_20261117_220711/{ba_cardadmin, Config.json, Shittim-Server.dll}`）

---

## 6. 没做 / 下一阶段（按风险排序）

| 项 | 为什么没做 | 怎么做 |
|---|---|---|
| **改绑定台数（`max_devices`）+ 公益卡（`kind`）** | 要动**登录路径**：MySQL 加列 → `sync.php` 改导出 → `sdkcard.py` 改台数校验。三处联动，且 `sdkcard.py` 一重启就影响全站登录 | 见 §6.1 |
| 每日登录奖励定义 | `AttendanceExcelT` 是 SQLCipher 加密的 Excel | 需要 ExcelDbSqlCipherKey 或 Custom 覆盖机制 |
| 踢下线 / 实时踢人 | 无踢人路径 | 需要给 Shittim 加连接注册表 |
| 战斗干预 | 无端点 | — |
| 卡密 ↔ 玩家自动对应 | 卡密→publisherId 的派生规则在 SDK 侧（`md5(card)[:8]` 一段），实测 `md5('11111111111')` 算不出桥里的常量 314816420，**规则没钉死**，所以先做手工绑定 | 钉死 sdkcard.py 的 `User.ID` 与桥 `UID` 的真实关系后自动回填 |

### 6.1 `max_devices` 方案（已设计，未执行）

1. `ALTER TABLE cards ADD COLUMN kind VARCHAR(16) NOT NULL DEFAULT 'paid', ADD COLUMN max_devices INT NOT NULL DEFAULT 1;`
   回填：`UPDATE cards SET max_devices = IF(bind_one=1, 1, 0);`（0 = 不限制）
2. `inc/sync.php` `sync_make_payload()`：`cards.json` 每条加 `"kind"`、`"max_devices"`（**只加字段，不改旧字段**，向后兼容）
3. `ba_sdk/sdkcard.py`：绑设备时
   ```python
   maxd = int(rec.get('max_devices') or (1 if rec.get('bind_one') else 0))
   if maxd and len(rec['devices']) >= maxd: -> 400101
   ```
4. 面板 `cards.php` 显示/编辑两个新字段，`players.php` 增加"公益卡"筛选项
5. 验收：把一张卡的 `max_devices` 设 2，用第三台设备登 → 400101

---

## 7. 现场常量

```
服务器            <SERVER_IP>
面板（卡密站）    http://<SERVER_IP>:8081  → /www/wwwroot/ba_cardadmin   （vhost 只 listen 8081）
Shittim admin     http://127.0.0.1:5000/api/admin/*   （X-Admin-Key 必填，64 位）
Shittim 进程      tmux 会话 shittim，cwd=/root
                  /root/dotnet10/dotnet /www/wwwroot/ba_srv/Shittim-Server.dll --console --id 2
Shittim 配置      /www/wwwroot/ba_srv/Config/Config.json   （不是 /root/Config.json）
游戏库            /root/shittim.sqlite3（www 不可读，面板不碰）
卡密库            MySQL ba_cardadmin
桥接账号库        /www/wwwroot/bapatch/data/accounts.db（www 可读）
SDK               /www/wwwroot/ba_sdk/sdkcard.py，监听 127.0.0.1:8080，sha ed2053dc…
cards.json        /www/wwwroot/ba_sdk/cards.json
面板连接配置      MySQL ba_cardadmin.settings: ba_admin_base / ba_admin_key / ba_accounts_db
静态缓存          /www/wwwroot/ba_cardadmin/state/bacache/
```
