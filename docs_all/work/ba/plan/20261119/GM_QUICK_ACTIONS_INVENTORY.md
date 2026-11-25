# GM 快捷功能盘点（只读）· ba_cardadmin

> 盘点时间：2026-11-19 23:30（Asia/Shanghai）
> 方式：**纯只读**。未联网、未登录服务器、未改任何文件。本报告是唯一写入物。
> 主树（新，含 2026-11-19 新增页面）：`work\ba\panel_work\p0rates\`
> 线上快照（90 文件）：`work\ba\srv_live\P0_SNAPSHOT_20261119_023658\panel\`
>
> **两棵树的关系（已核）**：文件级 diff 后，快照 = 主树去掉 2 个文件 + `inc/helpers.php` 小 72 字节。
> 即：主树 **多出** `pages/gacha_rates.php` + `inc/gacha.php`（2026-11-19 新加的抽卡概率页），其余 88 个文件完全同源。
> ⇒ **本文所有结论对线上同样成立**，除「抽卡概率设置」这一页线上还没有。`pages/*.php` 主树 17 个、快照 16 个。

---

## TL;DR（先看这一段）

1. **「GM 快捷功能」（一键类按钮）一共 9 个，全部在 `pages/items.php` 的「快捷动作」卡片里**，是一个 9 键 PHP 数组 `item_quick_actions()` 渲染出来的 9 个 `<button name="quick" value="<key>">`。
2. 「一键解锁任务」的实体是其中第 8 个按钮，文字就叫 **「解锁任务」**，POST `quick=unlock_mission`，最终发 GM 命令 **`unlockall mission`**。
   页面上没有字面叫「一键解锁任务」的按钮——「一键」二字体现在 **scope**（可切「对全服执行」），不在按钮名字里。
3. 这 9 个按钮 **不发邮件、不写库**，一律走 **`POST /api/admin/command`**（GM 命令），`Uid` = 目标玩家 ServerId，**玩家不需要在线**。
4. 面板 → 后端全部收口在 `inc/ba.php`：`ba_get() / ba_post()` → `ba_http()`，目标 `http://127.0.0.1:5000`（可配），鉴权头 `X-Admin-Key: <BA_ADMIN_KEY>`，超时 8s（`ba_command` 单独 30s）。
5. 批量发道具/邮件走 **两条不同的路**：`/api/admin/items/give`（直接进背包）vs `/api/admin/mail/send`（只写邮件行，玩家领取才入账）。参数见 §4。
6. 三件套惯例：**一次性确认令牌**（`action_token_*`，每次 POST 烧掉）替代 confirm 弹窗 + **双层审计**（`panel_ops` + `audit_logs`）+ **就地结果表**（每人一行 ok/err）。新功能照抄 `pages/items.php` 的 `quick` 分支即可。

---

## §1 页面总表（`pages/*.php`，17 个）

| # | 文件 | 页面标题（`page_header` 第 1 参） | 侧栏导航名 | 一句话作用 |
|---|---|---|---|---|
| 1 | `admins.php` | 管理员 | 管理员 | 管理员增删 / 改密码 / 启停（**没有角色体系**，任何管理员都能管别人） |
| 2 | `audit.php` | 审计日志 | 审计日志 | 查 `audit_logs`，按动作 / 操作人 / 关键字筛选分页（只读） |
| 3 | `bans.php` | 封禁管理 | 封禁管理 | 账号 / 卡密 / 设备三个正交维度的封禁 + 限时封禁 + 删号（硬删，二次确认 + 手输昵称） |
| 4 | `cards.php` | 卡密管理 | 卡密管理 | 卡密列表：分页 / 搜索 / 筛选 / 批量操作 / 单卡编辑 / AJAX 取明文 |
| 5 | `cards_export.php` | *（无页面，下载端点）* | — | 导出卡密 txt/csv；强制 POST+CSRF，记审计（会暴露明文） |
| 6 | `cards_import.php` | 批量导入 | 批量导入 | 文本框/文件批量导入卡密（≤2 MB），可统一到期时间 |
| 7 | `cards_new.php` | 新建卡密 | 新建卡密 | 单个新建 + 批量生成（≤5000），生成后可一键复制/导出 |
| 8 | **`console.php`** | **GM 命令台** | GM 命令台 | **任意 GM 命令执行台**：多选玩家 + 命令输入框 → `/api/admin/command`，附命令参考表 + 最近 15 条历史 |
| 9 | `currency.php` | 货币调整 | 货币调整 | 批量改货币，三种模式 set / add / sub（add/sub 先读现值再写绝对值） |
| 10 | `dashboard.php` | 仪表盘 | 仪表盘 | 统计卡 + 玩家快捷入口链接 + 最近 `panel_ops` + 同步状态 +「立即同步」 |
| 11 | `gacha_rates.php` | 抽卡概率设置 | 抽卡概率 | **[主树新增，线上无]** 四个分类的抽卡阈值读写 + 分组恢复默认 + 整体恢复默认 |
| 12 | **`items.php`** | **道具 / 角色** | 道具 / 角色 | **★ 9 个快捷动作 + 发道具 + 自定义 GM 命令批量 + 静态数据查 Id** |
| 13 | `logs.php` | 登录日志 | 登录日志 | 只读解析 `sdk.log` 入库 + 平台自身登录日志，筛选分页 |
| 14 | `mail.php` | 发奖 / 邮件 | 发奖 / 邮件 | 单人/多选/全服发邮件，附件可混搭（货币+道具+角色+记忆大厅…） |
| 15 | `player_detail.php` | 玩家详情 / 玩家详情 · `<昵称>` | *（挂在玩家列表）* | 单玩家：资料 / 货币 / 角色 / 邮件 / 卡密 / 封禁 + **单人 GM 命令框** |
| 16 | `players.php` | 玩家列表 | 玩家列表 | 全部账号列表 + 筛选 + 批量封禁/解封 + 批量发奖跳转 |
| 17 | `settings.php` | 系统设置 | 系统设置 | 同步、从 cards.json 导入、生成默认规则、路径、环境自检 |

**页面之外但属于站点的入口**：`index.php`（未登录跳登录，已登录 `include` dashboard）、`login.php`、`logout.php`、`404.html`、`index.html`。
**路由方式**：无路由框架，**文件名即页面**；侧栏是 `inc/helpers.php: nav_items()` 一个硬编码数组。

---

## §2 GM 快捷功能：逐按钮明细（带后端接口）

### 2.1 权威定义：`item_quick_actions()`（`pages/items.php:19-33`）

```php
/** 一键快捷动作：key => [标题, 命令, 说明] */
function item_quick_actions()
{
    return array(
        'giveall'         => array('发全部角色',  'giveall',                '把全部角色塞进该账号（含未实装的默认星级）'),
        'maxall'          => array('全角色满级',  'max all',                'Lv90 + 满星 + 技能 10/5/10/10 + 好感满'),
        'giveallequip'    => array('发全部装备',  'giveallequip',           '把全部装备塞进背包'),
        'unlock_campaign' => array('解锁主线',    'unlockall campaign',     '主线关卡全部解锁'),
        'unlock_story'    => array('解锁剧情',    'unlockall story',        '剧情全部解锁'),
        'unlock_week'     => array('解锁周常',    'unlockall weekdungeon',  '周常地下城全部解锁'),
        'unlock_school'   => array('解锁学院',    'unlockall schooldungeon','学院地下城全部解锁'),
        'unlock_mission'  => array('解锁任务',    'unlockall mission',      '任务全部解锁'),
        'battlepass'      => array('解锁通行证',  'unlockbattlepass',       '战斗通行证解锁'),
    );
}
```

### 2.2 完整按钮清单（9 个，一个不多一个不少）

表单：`pages/items.php:222-233`，`<form method="post" action="pages/items.php" id="f-quick">`
所有按钮共用：`mode=quick` + `scope=selected|all` + `_csrf` + `_atoken`，按钮自身只贡献 `name="quick" value="<key>"`。

| # | 按钮文字 | POST 字段 | 面板 action 标识 | GM 命令（`Command` 原文） | 后端接口 | 实际效果 |
|---|---|---|---|---|---|---|
| 1 | 发全部角色 | `quick=giveall` | `quick.giveall` | `giveall` | `POST /api/admin/command` | 把全部 234 个可解析角色塞进该账号（含未实装角色的默认星级） |
| 2 | 全角色满级 | `quick=maxall` | `quick.maxall` | `max all` | 同上 | 每人角色 Lv90 + 满星 + 技能 10/5/10/10 + 好感满 |
| 3 | 发全部装备 | `quick=giveallequip` | `quick.giveallequip` | `giveallequip` | 同上 | 全部装备进背包 |
| 4 | 解锁主线 | `quick=unlock_campaign` | `quick.unlock_campaign` | `unlockall campaign` | 同上 | 主线关卡全解锁 |
| 5 | 解锁剧情 | `quick=unlock_story` | `quick.unlock_story` | `unlockall story` | 同上 | 剧情全解锁 |
| 6 | 解锁周常 | `quick=unlock_week` | `quick.unlock_week` | `unlockall weekdungeon` | 同上 | 周常地下城全解锁 |
| 7 | 解锁学院 | `quick=unlock_school` | `quick.unlock_school` | `unlockall schooldungeon` | 同上 | 学院地下城全解锁 |
| 8 | **解锁任务** | `quick=unlock_mission` | `quick.unlock_mission` | **`unlockall mission`** | 同上 | **任务全部解锁**（这就是「一键解锁任务」） |
| 9 | 解锁通行证 | `quick=battlepass` | `quick.battlepass` | `unlockbattlepass` | 同上 | 战斗通行证解锁 |

> 说明列（第 3 个数组元素）只作为按钮 `title=` 悬浮提示，不显示在按钮上。

### 2.3 同一批「准快捷功能」（不是一键按钮，但新功能会与它们并列，一并列出）

| 位置 | 控件 | 性质 | 走哪条接口 |
|---|---|---|---|
| `items.php:265-279`「自定义 GM 命令（批量）」 | 1 个文本框 `name="command"` + 1 个按钮「对选中玩家执行」 | **真正的任意命令入口** | `POST /api/admin/command` |
| `console.php:161-173` | 1 个文本框 `name="command"` + 「执行」按钮 + **6 个预设芯片**：`help` / `max all` / `giveall` / `giveallequip` / `unlockall campaign` / `unlockbattlepass` | 芯片只是 **JS 填入输入框**，不提交 | `POST /api/admin/command` |
| `console.php:137-195` | 多选玩家（`sid[]`）+ 命令 → 执行，每人一行输出 | 主 GM 台 | `POST /api/admin/command` |
| `player_detail.php:404-417` | 单人命令框，`action=command` | 单人版 | `POST /api/admin/command` |
| `mail.php:202-209` | 4 个发奖模板：`💎 青辉石` / `💰 金币` / `⚡ 体力` / `🎁 三件套` | 纯前端填表（改前 3 行附件），不提交 | 最终还是 `POST /api/admin/mail/send` |
| `mail.php` 附件行 | `p_type[]` / `p_id[]`（货币下拉）/ `p_id_num[]`（道具角色数字）/ `p_amount[]` | 混搭附件 | 同上 |
| `players.php:194-203` 批量栏 | 「封禁」/「解封」/「批量发奖 →」 | 前两个真提交，第三个**带选中的人跳到 mail.php** | `pages/players.php` 自身 / `mail.php?sid=2,3` |
| `dashboard.php:174-180` | 5 个入口按钮（玩家列表 / 发奖 / 货币 / 道具角色 / GM 命令台） | 纯链接 | — |

---

## §3 调用链路

### 3.1 封装层：`inc/ba.php`（唯一出口，`ba_get` / `ba_post` 确实在这里）

```
pages/*.php
   └─ ba_command() / ba_mail_send() / ba_item_give() / ba_currency_set() / ba_account_update() …
        └─ ba_post($path, $body)            ← 薄封装
             └─ ba_http('POST', $path, $body, $opts)   ← 唯一真正的 HTTP 客户端
                  └─ curl_init / file_get_contents + stream_context
```

`ba_get($path, $query = [], $opts = [])` —— `$query` 非空时 `http_build_query` 拼到 path 后（`?` 或 `&` 自动判断），然后 `ba_http('GET', …)`。
`ba_post($path, $body = [], $opts = [])` —— 直接 `ba_http('POST', …)`。

**目标 URL**（`ba_cfg()`，`inc/ba.php:24-60`）：

| 项 | 取值顺序 |
|---|---|
| base | 常量 `BA_ADMIN_BASE` → `settings` 表 `ba_admin_base` → 兜底 **`http://127.0.0.1:5000`** |
| path | 形如 `/api/admin/command`，最终 URL = `rtrim(base,'/') . path` |
| key | 常量 `BA_ADMIN_KEY` → `settings` 表 `ba_admin_key` → 空串（空则**不发**鉴权头） |
| timeout | 默认 **8s**；`ba_command()` 单独传 `['timeout'=>30]` |
| cache | `APP_STATE_DIR/bacache`（只给静态数据用） |

**请求头**（`inc/ba.php:88-108`）：

```
Accept: application/json
X-Admin-Key: <BA_ADMIN_KEY>          ← 只有 key 非空时才发
Content-Type: application/json        ← 仅 POST
```

**请求体**：`json_encode($body, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES)`；`$body === null` 时发 `{}`。

**返回约定**（所有函数都不抛异常）：

```php
['ok'=>bool, 'status'=>int, 'data'=>mixed, 'error'=>string, 'ms'=>int, 'url'=>string]
```

失败判定：curl 失败 → `error='连接服务端失败：…'`；`status==0` → `服务端无响应`；`4xx/5xx` 且有 `{"error":"…"}` → 取该 `error`；否则 `HTTP <code>`。

**鉴权补充**：服务端 `[AdminAuth]` 对 **环回地址直接放行**（`127.0.0.1` / `::1`），跨机才必须带 `X-Admin-Key`。所以面板配不配 key 都能跑，`inc/ba.php` 的注释明确说「key 从 `BA_ADMIN_KEY` 读，读不到回落 settings 表」。

### 3.2 有没有「执行任意 GM 命令」的入口 —— **有，而且有两个**

#### 入口 A：`pages/console.php`（多玩家，主入口）

```
POST pages/console.php
  _csrf=<csrf_token>            （csrf_field()）
  _atoken=<32位hex>             （action_token_field('console')，一次性）
  sid[]=7&sid[]=8               （多个目标玩家，AccountServerId）
  command=unlockall mission     （原文）
```

服务端（`console.php:64-121`）：
`require_post_csrf()` → `action_token_check('console')` → 收集 `sid[]` → 空命令拒 → **`ba_validate_command($cmd)` 角色黑名单拦截** → 逐个 `ba_command($sid, $cmd)` → `panel_op_log('console.command', …)` + `audit_log('console.command', …)`（`setaccount` 会先读旧值写进审计）。

后端请求（`inc/ba.php:402-408`）：
```json
POST http://127.0.0.1:5000/api/admin/command
X-Admin-Key: <BA_ADMIN_KEY>
Content-Type: application/json
{"Uid": 7, "Command": "unlockall mission"}
```
响应：`{"success": true, "output": "<命令输出文本>"}`；失败 400 `{"error": "..."}`。
面板把 `data['output']` 原样贴进 `<pre class="cmd-out">`，并显示每人 `ms` 耗时。

**命令解析细节（服务端）**：`Command.Trim().Split(' ')` → 首 token `TrimStart('/','!','.','*').Split('/').Last()` ⇒ `!give` / `/give` / `give` 等价；然后 `CommandFactory.CreateCommand(name, connection, args)`。

#### 入口 B：`pages/player_detail.php`（单人）

```
POST pages/player_detail.php?sid=7
  _csrf=<csrf_token>
  sid=7
  action=command
  command=max all
```
服务端（`player_detail.php:102-124`）：`require_post_csrf()` →（**注意：没有 `action_token_check`，这个入口没有一次性令牌**）→ `ba_validate_command` → `ba_command($sid,$cmd)` → `panel_op_log('command',…)` + `audit_log('player.command',…)` → flash → `302 → ?sid=7&cmd_out=<前4000字>`（PRG）。

#### 入口 C：`items.php`「自定义 GM 命令（批量）」

字段与 console 同构（`mode=command` 而非 `_atoken` 以外的差异）：`_csrf` + `_atoken` + `scope` + `sid[]`（JS 提交前注入）+ `command`。
服务端走 `items.php:116-137`，审计为 `panel_op_log('command.batch', …)`，结果就地渲染（不回跳）。

### 3.3 命令参考（面板自身的白名单表 `console_command_help()`，`console.php:19-45`）

| 命令 | 参数 | 说明 |
|---|---|---|
| `help` | — | 列出全部命令 |
| `give` | `<包裹类型> <id> <数量>` | 发放单个包裹（如 `give Currency 3 1000`） |
| `giveall` | — | 发放全部角色 |
| `giveequip` | `<装备id> [数量]` | 发放装备 |
| `giveallequip` | — | 发放全部装备 |
| `max` | `<all\|角色名>` | 把角色拉满（Lv90/满星/技能/好感） |
| `currency` | `<货币> <数量>` | 改货币（绝对值） |
| `character` | `<...>` | 角色增删 / 改星级 |
| `addeleph` | `<角色id> <数量>` | 加碎片 |
| `inventory` / `listitem` / `checkitem` | — / — / `<id>` | 查背包 / 列道具 / 查某道具 |
| `clearinventory` | — | 清空背包（危险） |
| `mail` | `<类型> <id,...> <数量>` | 发邮件（**支持逗号多 id**） |
| `accountdata` | `list\|load\|export` | 整包存档导入导出 |
| `setaccount` | `<属性> <值>` | 反射设置账号属性 |
| `setseason` | `total\|grand\|drill\|final <id>` | 设置赛季 |
| `setraid` | `<...>` | 总力战参数 |
| `setting` | `trackpvp\|usefinal\|bypassteam\|bypasssummon\|changetime` | 开关类设置 |
| **`unlockall`** | **`campaign\|story\|weekdungeon\|schooldungeon\|battlepass\|mission`** | **批量解锁** |
| `unlockbattlepass` | — | 解锁战斗通行证 |
| `gacha` | `<...>` | 抽卡模拟 |

> ⚠ 这张表是**面板手写的参考**，不是白名单校验。真正执行时只有 `ba_validate_command()` 一道闸（只在命令里出现 `character` 字样时才比对 23 个黑名单角色 id），其余一律原样转发。所以「任意 GM 命令」是**真的任意**。

---

## §4 批量发放道具/邮件的实现

### 4.1 三条路，别混

| 路径 | 页面 | 后端接口 | 语义 | 到账时机 |
|---|---|---|---|---|
| **A. 发道具** | `items.php`「发道具」卡片 | `POST /api/admin/items/give` | 直接改背包行（可 SetExact 覆盖） | **立即**（不改邮件） |
| **B. 发邮件/发奖** | `mail.php` | `POST /api/admin/mail/send` | 只写 `Mails` 行，**不走 ParcelResolver** | **玩家在游戏里点「领取」时** |
| **C. 改货币** | `currency.php` | `POST /api/admin/currency/set` | 写绝对值 | **立即** |

补充：
- **从不直接写 `/root/shittim.sqlite3`**（`inc/ba.php` 头部注释明确写死这条纪律），全部走 `/api/admin/*`，派生字段/JSON 形状由服务端保证。
- 也没有任何页面用 `/api/admin/*` 之外的方式发东西；桥（`sdkcard.py`）只负责账号/卡密，不碰发放。

### 4.2 A 路：发道具参数（`inc/ba.php:384-392`）

```php
ba_item_give($serverId, $uniqueId, $amount, $setExact = false)
  → POST /api/admin/items/give
    {"AccountServerId": 7, "UniqueId": 1001, "Amount": 100, "SetExact": false}
```
- **没有 ParcelType**，只有 `UniqueId`（道具 Excel Id）+ `Amount`。
- `SetExact=false` → 现有数量上叠加；`true` → 覆盖为 `Amount`。
- 批量：`items.php:110-114` 对每个 `sid` 循环调用，**没有批量端点**。

### 4.3 B 路：发邮件参数（`inc/ba.php:333-348`）★ 附件混搭就靠它

```php
ba_mail_send($serverId, $sender, $comment, $parcels, $expireDate = '')
  → POST /api/admin/mail/send
```

请求体（PHP 侧）：
```php
[
  'AccountServerId' => 7,
  'Sender'          => 'Schale',
  'Comment'         => '全记忆大厅补发',
  'Parcels'         => [ ['type'=>'MemoryLobby','id'=>13010,'amount'=>1], ... ],
  'ExpireDate'      => date('c', strtotime($expire)),   // 仅在填了有效期时才带
]
```
- `Parcels` 每项 = **`type`（ParcelType 枚举名字符串）+ `id`（ParcelId，即包裹 id）+ `amount`**。
- 收件人 = `AccountServerId`（= Shittim 的 Account 表 `ServerId`，面板里叫 `sid` / ServerId）。
- 有效期留空 → 不带 `ExpireDate`，服务端默认 7 天。

**完整例子（面板实际会发出的一个请求）**——给玩家 #7 发「幽香记忆大厅 + 1200 免费青辉石」：

```http
POST http://127.0.0.1:5000/api/admin/mail/send
Accept: application/json
X-Admin-Key: <BA_ADMIN_KEY>
Content-Type: application/json

{
  "AccountServerId": 7,
  "Sender": "Schale",
  "Comment": "全记忆大厅补发，请查收。",
  "Parcels": [
    {"type": "MemoryLobby", "id": 13010, "amount": 1},
    {"type": "Currency",    "id": 3,     "amount": 1200}
  ],
  "ExpireDate": "2026-11-26T23:59:00+08:00"
}
```

对应面板上的人工操作路径：`mail.php` → 勾玩家 #7 → 发送者 `Schale` → 内容栏 → 附件第 1 行 `类型=记忆大厅（L2D）` / `ID=13010` / `数量=1`，第 2 行 `类型=货币` / 下拉选 `GemBonus` / `数量=1200` → 点「发送」。

**类型下拉的可用值**（`ba_parcel_presets()`，`inc/ba.php:472-486`）：
`Currency`（货币/青辉石/金币/体力）、`Item`、`Character`、`Equipment`、**`MemoryLobby`（记忆大厅 L2D）**、`FavorExp`、`AccountExp`、`CharacterExp`、`GachaGroup`、`Furniture`。

**货币 id 速查**（`ba_currency_maps()` 硬编码兜底）：`1 Gold` / `2 GemPaid` / `3 GemBonus` / `4 Gem(派生)` / `5 ActionPoint` / `6 AcademyTicket` / `7 ArenaTicket` / `8 RaidTicket` / `18 MasterCoin`。
⚠ 写 `Gem(4)` 等价于「免费石=该值、付费石=0」（`Gem = GemBonus + GemPaid` 是派生值），想加免费石要用 `GemBonus(3)`。

### 4.4 字段大小写的隐含约定（照抄时必须注意）

- 面板**外层**用 PascalCase（`AccountServerId` / `Sender` / `Parcels`），**包裹项**用全小写（`type` / `id` / `amount`），两种写法混在同一份 body 里。
- 服务端 DTO 是 C# 类（`SendMailRequest { AccountServerId, Sender, Comment, Parcels, ExpireDate }`、`ParcelRequest { Type, Id, Amount }`），线上实测能收 —— 说明它走 ASP.NET Core 的 **Web 默认序列化策略**（输出 camelCase + 输入大小写不敏感），这也解释了为什么 `players.php` 读的是 `$a['serverId']`（camelCase）而不是 `ServerId`。`[推断·高]`
- ⇒ 新功能**照 `ba_mail_send()` 的写法即可**，不要一半 PascalCase 一半 camelCase 另起一套。

---

## §5 现有「一键」类功能的 确认 / 审计 / 回显 三件套

### 5.1 逐功能矩阵

| 功能（页面/动作） | 二次确认 | 审计日志 | 结果回显 |
|---|---|---|---|
| **items.php 9 个快捷动作** | ❌ 无 `confirm()`；**✅ 服务端一次性令牌** `action_token_check('items')` | ✅ 双写：`panel_op_log('quick.<key>', ids, {batch,command}, ok,fail, batch)` + `audit_log('player.bulk_op', implode(ids), "<mode> <label> ok=N fail=M")` | ✅ 页面顶部 `section.card.card-result`：`成功 N / 失败 M` tag + `batch <12位>` + 表格每人一行（`#ServerId` + `tag-ok/tag-err` 消息） |
| items.php 发道具 | 同上（同一表单组） | ✅ `panel_op_log('item.give', …, {batch,unique_id,amount,exact})` + `audit_log('player.bulk_op', …)` | ✅ 同上 |
| items.php 自定义命令 | 同上 | ✅ `panel_op_log('command.batch', …, {batch,command})` + `audit_log('player.bulk_op', …)` | ✅ 同上；`output` 截断到 60 字 |
| **console.php 命令台** | ❌ 无 `confirm()`；✅ 一次性令牌 `action_token_check('console')` | ✅ `panel_op_log('console.command', ids, {command, outputs[]})` + `audit_log('console.command', ids, cmd + ' \| before:<sid>:<old>→(cmd)')`（`setaccount` 会先读旧值） | ✅ 每人一行：`#sid` + OK/错误 tag + `ms` 耗时 + `<pre class="cmd-out">` 完整 output |
| player_detail.php 单人命令 | ❌ 无 confirm；❌ **无一次性令牌**（只 `require_post_csrf`） | ✅ `panel_op_log('command', [sid], {command, output})` + `audit_log('player.command', 'server#N', cmd)` | ✅ flash 提示 + PRG 回跳 `?cmd_out=<前4000字>` 渲染 `<pre class="cmd-out">` |
| **mail.php 发奖** | ❌ 无 `confirm()`；✅ 令牌 `action_token_check('mail')` | ✅ 三处：`panel_op_log('mail.send', ids, {batch,sender,comment,expire,parcels})` + `audit_log('mail.send', "邮件批次 <batch> → N 人（成功/失败）", 完整 parcels JSON + 前 80 个 id)` + 页面底部「最近 10 批发奖」表 | ✅ `card-result`：成功/失败 tag + batch + 每人一行（`#sid` / 已投递或错误 / `ms`）+ 末尾提示「玩家点领取才真正到账」 |
| currency.php 批量货币 | ❌ 无 confirm；✅ 令牌 `action_token_check('currency')` | ✅ `panel_op_log('currency.batch', …)` + `audit_log('currency.batch', "货币 X(#n) 模式=… 数量=… 共N人", "batch=… sid:旧值→新值 …")` | ✅ `card-result`：每人 before → after（失败记 `fail`） |
| players.php 批量封禁/解封 | ✅ 前端 `confirm('确认封禁选中账号？…')`（先检查是否勾选） | ✅ `audit_log('player.ban' / 'player.unban', …)`（带旧 State → 新 State） | ✅ flash + PRG |
| bans.php 全封/全解/删号 | ✅ `data-confirm` 属性 + `app.js` 统一 `window.confirm`；删号额外 **手输昵称/ServerId** | ✅ 有 | ✅ flash + PRG |
| gacha_rates.php 恢复全部默认 | ✅✅ **最强**：前端 `confirm()` + **`confirm_all=1` 隐藏域** + 一次性令牌 `action_token_check('gacha-reset-all')`，审计里明写「二次确认=前端 confirm + 服务端一次性令牌」 | ✅ `audit_log('gacha.rates.reset_all', …, "旧值→新值；备份=<file>")` | ✅ flash + PRG（重定向回本页） |
| dashboard 同步 / settings 导入 / logs 清理 / admins 增删 | ✅ 多数有 `confirm()` | ✅ 有 | ✅ flash |

### 5.2 两种「二次确认」机制（新功能二选一或都上）

1. **一次性确认令牌**（防误触，**不是**防攻击）——`inc/auth.php:426-508`
   - `action_token_field($scope)` 渲染 `<input type="hidden" name="_atoken" value="<32位hex>">`
   - 服务端 `action_token_check($scope)`：读 `state/otok_<sha256(session|scope) 前24>.json`，比对 → **无论成败都 `unlink`**（一次性）；失败直接 **HTTP 419** + 中文提示页。
   - TTL 10 分钟；每个 (会话, scope) 同时只有一个有效令牌（多标签页只留最新）。
   - ⚠ **副作用**：`items.php` / `mail.php` / `currency.php` / `console.php` 都是「POST 就地渲染、不重定向」→ 刷新页面会重发 POST，但令牌已烧掉 → 直接吃 419 页。这是当前设计的既有行为，不是 bug。
2. **前端 `confirm()`** —— 用于「看得见的破坏性动作」（封禁、删号、清邮件、恢复默认）。模板见 `gacha_rates.php:385/418`（用 `json_encode(…, JSON_UNESCAPED_UNICODE)` 注入中文，避免引号问题）和 `app.js` 的 `data-confirm` 统一委托。

**当前 9 个快捷动作只有令牌、没有 confirm**。如果新功能（如一次性发 258 个记忆大厅）要更重的确认，**照 `gacha_rates.php` 的 `reset_all` 三件套写**：`confirm()` + 回传 `confirm_all=1` + 服务端校验。

### 5.3 两套日志别混

| 表 | 由谁写 | 内容 | 在哪看 |
|---|---|---|---|
| `panel_ops` | `panel_op_log()`（`inc/players.php:137`） | `batch_id / action / targets(逗号 id) / payload(JSON) / ok_count / fail_count / admin_name / ip / ts` | `console.php`「最近命令」、`mail.php`「最近 10 批发奖」、`dashboard.php`「最近操作」 |
| `audit_logs` | `audit_log()`（`inc/auth.php:570`） | `admin_id / admin_name / action / target / detail(≤4000) / ip / ts` | `audit.php`（可按 action / 操作人筛） |

两个函数都 **`try/catch` 吞异常、不阻断主流程**。

---

## §6 页面布局惯例 & 可复用组件（新功能照抄这套）

### 6.1 一个典型「操作区」的样子

```
page_header('标题', '导航key')                       ← inc/helpers.php:897，含侧栏/顶栏/flash 渲染
  <section class="card">                             ← 白卡片，border+radius+padding
    <div class="card-h">
      <h2>区块标题</h2>
      <div class="card-h-act"> …右侧按钮/计数/tag… </div>   ← flex，h2 占满
    </div>

    <form method="post" action="u('pages/x.php')">   ← 表单永远 POST + 同页
      csrf_field()                                   ← _csrf
      action_token_field('scope')                    ← _atoken（高危动作才要）
      <input type="hidden" name="mode|action" value="…">

      …选择器…                                       ← 见 6.2
      <div class="field"><label>字段名</label><input …></div>
      <div class="actions"><button class="btn btn-primary">执行</button></div>
    </form>
  </section>

  <section class="card card-result">                 ← 结果区（有结果时才渲染，放页面最上）
    <div class="card-h"><h2>执行结果 · <label></h2>
      <div class="card-h-act">
        <span class="tag tag-ok|tag-warn">成功 N / 失败 M</span>
        <code class="small">batch <id></code>
      </div>
    </div>
    <div class="table-wrap"><table class="tbl">
      <thead><tr><th>ServerId</th><th>结果</th></tr></thead>
      <tbody> 每人一行：<a href="player_detail.php?sid=N">#N</a> + <span class="tag tag-ok|tag-err">msg</span> </tbody>
    </table></div>
  </section>
page_footer()                                        ← 收尾 + 引 app.js
```

### 6.2 可复用组件清单（**只用这些，别自己造 class**）

| 用途 | Class / 片段 | 定义位置 | 备注 |
|---|---|---|---|
| 卡片 | `.card` / `.card-h` / `.card-h-act` / `.card-result`（左侧绿边）/ `.card-edit`（左蓝边） | `app.css:129,133,135,136,137` | `.card-h h2 { flex:1 }` 自动占满 |
| 表格 | `.table-wrap` 包 `table.tbl`；`thead th`；`.row-sub` / `.row-off`；`.w-chk` / `.w-act` / `.td-key` | `app.css:140-170` | 永远包 `.table-wrap`（横向滚动 + 手机适配） |
| 键值表 | `table.kv`（`<th>` 左列 + `<td>` 右列） | `app.css:157` | dashboard/settings 用 |
| **表单字段（推荐）** | `.fld` > `span`(标签) + `input` + `em`(灰字提示)；`.fld-wide` / `.fld-check` / `.fld-actions` / `.form-grid` / `.grid2` | `app.css:219-238` | **有完整样式**，settings / gacha_rates / bans 用这套 |
| 表单字段（旧） | `.field` > `label` + input；`.field-row`；`.actions` | **app.css 里没有这三个选择器** | items / mail / console / currency 在用，纯 no-op（靠浏览器默认）→ **新页面请用 `.fld`** |
| 按钮 | `.btn` + `.btn-primary` / `.btn-danger` / `.btn-warn` / `.btn-sm` / `.btn-xs` / `.btn-block` / `.btn-copy` | `app.css:184-208` | |
| 状态标签 | `.tag` + `.tag-ok` / `.tag-err` / `.tag-warn` / `.tag-info` / `.tag-gray` | `app.css:173-181` | 结果表就用这个 |
| 消息条 | `alert_box($msg,'ok'\|'warn'\|'err'\|'info')` → `.alert.alert-*`；服务端不可达用 `.srv-down` | `helpers.php:969` / `app.css:100,384` | flash 走 `flash_set()` + `page_header` 自动渲染 |
| 双列布局 | `.detail-grid`（2 列等比）/ `.cols`（2 列）/ `.quick`（按钮流）/ `.row-gap` / `.actions` | `app.css:358,123,126,57` | items.php 用 `.detail-grid` 并排放「快捷动作 / 发道具」 |
| 玩家多选区 | `<div style="max-height:180px;overflow:auto;border:1px solid var(--line);border-radius:8px;padding:8px">` + `<label class="small"><input type="checkbox" name="sid[]" class="msid">昵称 #id · LvN</label>` + 顶上的 `全选/清空` + `已选 N 人` | `mail.php:225-238`、`items.php:202-213` | 这个内联样式是**约定俗成的手写块**，没有 class |
| 全服开关 | `<label><input type="checkbox" id="scope-all"> 对<b>全服</b>执行</label>` + 各表单里的 `<input type="hidden" name="scope" class="scope-holder" value="selected">`，JS 勾选时批量改成 `all` | `items.php:214-216,345-352` | 服务端 `scope==='all'` → `player_roster()` 全量替换 ids |
| 批量操作栏 | `.bulkbar` + `.bulk-count`（`<span class="bulk-count">已选 0 人</span>`） | `app.css:243,350,355` | cards.php / players.php 用 |
| 命令输出 | `<pre class="cmd-out">` | `app.css:375-382` | console / player_detail 用 |
| 分页 | `.pager` / `.pg` / `.pg-on` / `.pg-gap` / `.pager-info` | `app.css:255-264` | |
| 前端能力 | `window.CA.copyText()` / `window.CA.toast()` / `data-act`+`data-confirm` 行操作 / `data-toggle` 折叠 / `.ca-pick` 全选 | `app.js` | **无框架、无外网请求**，新页面如需交互就写页面内联 IIFE `<script>` |

### 6.3 新页面骨架（照 `gacha_rates.php` 的注释写法）

```php
<?php
/**
 * pages/xxx.php — 一句话
 * 写操作遵循面板惯例：
 *   POST → require_post_csrf() → (action_token_check) → 校验 → 调 API → audit_log() → flash_set() → 302（PRG）
 */
if (!defined('CARDADMIN')) { define('CARDADMIN', true); }
require_once __DIR__ . '/../inc/auth.php';
require_once __DIR__ . '/../inc/ba.php';
require_once __DIR__ . '/../inc/players.php';   // 需要玩家列表/panel_op_log 才引
require_login();
```

并在 `inc/helpers.php: nav_items()` 里加一行才能出现在侧栏（例：`'gacha' => array('抽卡概率', 'pages/gacha_rates.php')`）。

---

## §7 附录 A：为「一键发放全部记忆大厅」的前置事实（本地文档已证，**非本次实测**）

这一节不在盘点要求内，但直接决定新功能怎么写，且全部能在本地只读文件里找到依据：

1. **`ParcelType.MemoryLobby = 8`**，`Amount` **必须 ≥ 1**（0 会被当无效丢弃）。
   来源：`work\ba\server\deploy\_panel\ADMIN_API_CONTRACT.md:178,187`（`ParcelType` 全表 + 坑位说明）、`work\ba\server\deploy\MEMORYLOBBY_GRANT.md:39-47`。
2. **记忆大厅 ID == `MemoryLobbyDBSchema.Id`，与角色 `UniqueId` 同号**（如幽香 `13010`），全表 **258 行**（`10000`…`2300501`，含 7 位 multi 版）。
   来源：`MEMORYLOBBY_GRANT.md:9-33,73-81`；`work\ba\proto\_sub_exceldb.md:65`。
3. **唯一能写「拥有关系」的通道是 `ParcelType.MemoryLobby`**（`ParcelResolver.UpdateMemoryLobby` 按 `(AccountServerId, MemoryLobbyUniqueId)` 幂等插入 `MemoryLobbies`）。改 `Accounts.MemoryLobbyUniqueId` 只改「当前选中」，改不出「拥有」；`MemoryLobbyHandler` 四个 handler 一个都不写 `MemoryLobbies`。
   来源：`MEMORYLOBBY_GRANT.md:62-70`；`work\ba\server\deploy\SHITTIM_ROOT_PLAN.md:992-1010`。
4. ⇒ **面板已有现成载体**：`mail.php` 的附件下拉里已经有 `MemoryLobby`（`ba_parcel_presets()`），`Parcels` 数组天然支持一次塞 N 个包裹。所以「一键发放全部记忆大厅」最贴合现状的实现是：
   **一次 `POST /api/admin/mail/send`，`Parcels` = 258 个 `{"type":"MemoryLobby","id":<lobbyId>,"amount":1}`**，而不是 258 次 `give` 命令（后者是 258×N 次 HTTP，`ba_command` 单次超时 30s，全服会跑爆 PHP 执行时间）。
   另一条可行但更绕的路：GM 命令 `mail 8 <id,id,…> 1`（`mail` 命令支持逗号多 id，见 `console_command_help()`）。
5. 缺口：**面板没有任何「记忆大厅 id 清单」的来源**。现有静态接口只有 `/api/admin/static/items`、`/static/characters`、`/static/equipment`、`/static/currencies`、`/meta/parceltypes` —— 没有 lobby 列表端点。要「全部」就必须自带一份 id 清单（可从本地 `work\ba\data\ExcelDB.db` 的 `MemoryLobbyDBSchema` 导出，258 行）或新增一个服务端静态端点。

---

## §8 附录 B：本次盘点的证据边界 / 待核实

| # | 事项 | 状态 |
|---|---|---|
| 1 | 两棵树同源（仅差 `gacha_rates.php` + `inc/gacha.php` + `helpers.php` 72B） | ✅ 已用文件级 diff 核实 |
| 2 | 9 个快捷动作的命令原文 | ✅ 直接读 `item_quick_actions()` 源码 |
| 3 | `ba_get/ba_post` 是唯一出口、目标 URL / 鉴权头 / 超时 | ✅ 直接读 `inc/ba.php` |
| 4 | 各功能的确认/审计/回显 | ✅ 逐页读 POST 分支 |
| 5 | 服务端 DTO 与面板字段大小写不一致仍能工作 | `[推断·高]`：ASP.NET Core Web 默认序列化（输出 camelCase、输入大小写不敏感）。依据：`players.php` 用 camelCase 读 `/api/admin/accounts`；`ba_mail_send` 用 PascalCase 发且线上在用 |
| 6 | 258 个大厅 id 的具体清单 | 未导出（本次只读盘点，不跑脚本）；来源与抽取方法见附录 A-2/5 |
| 7 | 「一键解锁任务」在客户端里的实际视觉变化 | 未验证（未执行任何命令、未连服务器） |
| 8 | `max all` / `giveall` 在超大账号上的耗时 | 未验证；`ba_command` 单次超时 30s、`ba_http` 默认 8s，全服批量存在超时风险（PHP `max_execution_time` 也会先撞） |
