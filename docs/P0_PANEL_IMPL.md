# P0 管理站「抽卡概率」页面实现报告

- 日期：2026-11-19
- 任务：在现有 PHP 管理站新增「抽卡概率」页面（读取 / 编辑 / 分组恢复 / 全部恢复）
- 范围：**只写本地工作副本里的 PHP 文件**；未部署、未 SSH、未改服务器、未改快照目录。

---

## 1. 工作副本与红线遵守

| 项目 | 路径 |
|---|---|
| 源快照（只读基线） | `C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\srv_live\P0_SNAPSHOT_20261119_023658\panel\` |
| 工作副本（所有改动） | `C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\panel_work\p0rates\` |
| 站点根（部署目标） | `/www/wwwroot/ba_cardadmin` |

已用递归 SHA256 对比确认：工作副本相对快照**只有**以下差异：

- 新增 `inc/gacha.php`
- 新增 `pages/gacha_rates.php`
- 修改 `inc/helpers.php`（只多一行导航）
- 其余 89 个原文件字节完全一致（原快照共 90 个文件，其中 `inc/helpers.php` 修改，另 89 个未变；含 `config.php`，未动数据库密码/配置）

遵守的红线：

- 未部署、未 SSH、未连接线上服务器。
- 未改快照目录。
- 页面/封装层**不直接读写**服务端的 `gacha_rates.json` / `gacha_config.json`，全部走 `/api/admin/gacha/rates*`。
- 未重启任何服务，未改 nginx / php-fpm / MySQL。
- 未引入新依赖、框架、Composer 包。

### 1.1 关于 `inc/ba.php` 的复用（任务要求先确认）

现有 `inc/ba.php` **已经有**完整封装，不需要另造一套：

- `ba_http($method, $path, $body, $opts)`：底层请求，负责拼 `base`、加 `X-Admin-Key`、POST JSON、超时、解码。
- `ba_get($path, $query, $opts)` / `ba_post($path, $body, $opts)`：便捷包装。
- Key 来源：`config.php` 的 `BA_ADMIN_BASE` / `BA_ADMIN_KEY`，读不到再回落到 `settings` 表的 `ba_admin_base` / `ba_admin_key`。
- 本页新增的 `inc/gacha.php` 只调用 `ba_get()` / `ba_post()`，**没有新写 curl / stream_context**。

---

## 2. 交付文件清单（相对站点根）

| # | 文件（相对站点根） | 类型 | 行数 | 字节数 | SHA-256 |
|---|---|---|---:|---:|---|
| 1 | `inc/gacha.php` | 新增 | 472 | 17,073 | `1152ff4c5f16372f7cec78a3b458d45dd0e4ed2781b4f396d6634d2f1e3a4e94` |
| 2 | `pages/gacha_rates.php` | 新增 | 564 | 24,050 | `105f151cd539322f26ffaa54d32a250c084b82d99536516249f3318d36e1bfdd` |
| 3 | `inc/helpers.php` | 修改（+1 行） | 975 | 29,131 | `0bd35a74fed7c932bf232f1fb0bf49efd738448e6bd122c1c9830539a4d4a371` |

修改前 `inc/helpers.php`（快照）对照：

- 974 行，SHA-256 `4440c2c9845e0a97c411cbbc5a564fa97b025eea935b855235ebc05e7ba6c87e`

说明：

- `inc/gacha.php`：API 封装 + 分类/字段定义 + 校验 + 百分比/分段计算 + 审计文案工具（无输出、无文件操作）。
- `pages/gacha_rates.php`：页面（状态、表格、保存、分组恢复、全部恢复、失败兜底、前端实时换算）。
- `inc/helpers.php`：只在 `nav_items()` 里加了一行「抽卡概率」。

---

## 3. `inc/helpers.php` 的具体改动

只改 `nav_items()`，放在「玩家」分组、「GM 命令台」之后：

```diff
@@ -872,6 +872,7 @@ function nav_items()
         'mail'       => array('发奖 / 邮件', 'pages/mail.php'),
         'currency'   => array('货币调整', 'pages/currency.php'),
         'items'      => array('道具 / 角色', 'pages/items.php'),
         'console'    => array('GM 命令台', 'pages/console.php'),
+        'gacha'      => array('抽卡概率', 'pages/gacha_rates.php'),
 
         /* 卡密域：现有能力，逻辑不动 */
         '__g_card' => array('卡密', null),
```

没有改任何函数签名、常量、CSS、JS、SQL。

---

## 4. 页面功能与区域（截图级别说明）

以下按 1400px 宽、面板现有 `assets/app.css` 渲染描述；本地用临时 harness + Edge headless 渲染了 `custom / default / legacy / fail` 四种状态核对过。

### 4.1 左侧导航

- 「玩家」分组里，在「GM 命令台」下方新增 **「抽卡概率」**（`pages/gacha_rates.php`）。
- 进入页面后该项高亮（`nav-on`），URL 为 `/pages/gacha_rates.php`（文件即页面，无路由）。

### 4.2 顶部：旧配置接管警告（条件显示）

当 API 返回 `legacyOverrideActive: true` 时，页面最顶部、标题栏正下方出现**整宽红色警告条**：

> **警告：旧的 gacha_config.json 正在接管抽卡概率，本页改动不会生效。**
> 服务端检测到 `…/gacha_config.json` 里的 `custom_rates` 非空，抽卡会先走这个旧分支，`/api/admin/gacha/rates` 写入的数值会被绕过。
> 处理办法：让运维确认后清掉该文件的 `custom_rates`（或删除 / 改名 `gacha_config.json`），再刷新本页。本页不会去修改它。

同时在「当前状态」卡右上角出现红色标签 **「旧 gacha_config.json 生效中」**，状态表里「旧 gacha_config.json」一行显示 **「正在接管」** + 服务端给的路径。

### 4.3 「当前状态」卡

右上角标签（三种之一）：

- `默认值`（绿色）：`isDefault: true`
- `已自定义`（黄色）：`isDefault: false`
- `读取失败`（红色）：GET 失败

右侧同时显示 `读取 N ms`。表内四行：

| 行 | 显示内容 |
|---|---|
| 当前状态 | `默认值`（与 defaults 完全一致）或 `已自定义`（当前生效值被覆盖） |
| 最后修改时间 | 本地时间（如 `2026-11-19 10:30:41`）+ 小字 `UTC 原值 2026-11-19T02:30:41.0000000Z`；无记录显示 `—` |
| 版本 / 配置文件 | `v1` + 服务端 `filePath` + 覆盖文件状态（无覆盖文件 / 已生效 / 存在但校验失败 / 未知） |
| 旧 gacha_config.json | `未检测到`（绿）或 `正在接管`（红）+ 路径 |

如果 GET 返回了 `warnings[]`，在表下方追加黄色「服务端提示」条；如果 `lastError` 非空，追加红色「服务端上次读取配置时的错误」条。这两项在契约最小字段之外，按可选处理，没有也不会报错。

### 4.4 「读取当前概率失败」卡（条件显示）

GET 失败（超时 / 非 200 / `ok:false` / 返回不是 JSON）时：

- 「当前状态」卡只显示一行红字：`当前状态未知：读取 API 失败（<错误原文>）`。
- 下方红色 `srv-down` 框：`读取不到抽卡概率：<错误原文>`；下一行 `请求：<URL> · HTTP <status> · <ms> ms`。
- 说明文字：本页只通过该 API 读写、读不到就不显示当前值、不会允许保存/恢复；提示检查服务端与 `X-Admin-Key`。
- 「重新读取」按钮（刷新本页）。
- `<details>` 折叠块 **「原始响应体（点击展开）」**，里面用深色 `<pre class="code">` 显示原始响应（JSON 会 pretty-print；非 JSON/HTML 原样；空响应显示 `(空响应体)`）。
- 表格与保存/恢复按钮**不渲染**，避免把 0 当成真实概率误保存。

### 4.5 「数值怎么读（务必先看）」卡

固定显示任务要求的三段语义（原文，带少量 `<b>` / `<code>` 排版）：

> 这里的「总出彩阈值」是**阈值**，不是相加后的概率。当前判定逻辑是：随机数（0–999）小于 `upSsrRate` 出 UP 3★；否则小于 `ssrThreshold` 出其它 3★。
>
> 所以 **UP 实际出率 = upSsrRate/10 %**，**其它 3★ 实际出率 = (ssrThreshold − upSsrRate)/10 %**，**总出率 = ssrThreshold/10 %**。
>
> 例：`upSsrRate=7, ssrThreshold=23` → UP 0.7% + 其它 1.6% = **总 2.3%**。

下方灰字补充（按已核对的 `ShopManager` 判定顺序）：

- Fes 池在 UP 段之后还有 `fesSsrRate` 段：默认 `7 / 9 / 44` → UP 0.7% + Fes 专属 0.2% + 其它 3.5% = 总 4.4%。
- `srRate` 同样是**绝对阈值**，2★ 区间是 `[ssrThreshold, srRate)`，所以 185 并不等于「2★ 占 18.5%」。
- 表里的「换算」只是 ‰ ÷ 10 的单位换算，实际占比看右侧「实际出率（只读）」。

### 4.6 「各分类阈值」卡（核心表格）

标题：**各分类阈值（单位 ‰，0–1000）**；右上角提示「保存 = 整份提交四个分类；未改的字段按当前值提交」。

七列表头：

1. 分类
2. 总出彩阈值 `ssrThreshold`（副标题：总 3★ 上限，含 UP / Fes 段）
3. UP 出率 `upSsrRate`（UP 3★ 上限）
4. Fes 专属 `fesSsrRate`（仅 Fes 行可填）
5. 2★ 率 `srRate`（2★ 上限，绝对阈值）
6. 实际出率（只读）
7. 操作

四行数据（分类中文名 + 英文枚举 + 说明）：

| 行 | 分类显示 | 可编辑字段 |
|---|---|---|
| 1 | 常驻（常驻池 · NormalGacha） | `ssrThreshold`、`srRate`；UP / Fes 列显示 `—` |
| 2 | Pickup（UP 池 · PickupGacha 及未单列的分类） | `upSsrRate`、`ssrThreshold`、`srRate`；Fes 列 `—` |
| 3 | 限定（限定池 · LimitedGacha） | 同 Pickup |
| 4 | Fes（Fes 池 · FesGacha） | `upSsrRate`、`fesSsrRate`、`ssrThreshold`、`srRate` |

每个可编辑单元格：

- 数字输入框：`min=0 max=1000 step=1 required inputmode=numeric`，当前值来自 GET 的 `rates`。
- 输入框下方只读小字：`换算 <b>2.3%</b> · 默认 23（2.3%）`。
- 输入变化时前端实时重算「换算」和右侧「实际出率」，不提交、不发请求。

「实际出率（只读）」列（按服务端判定顺序推导，前端/后端同一套逻辑）：

- 常驻：`总 3★ 3%` + `2★ 15.5% · 1★ 81.5%`
- Pickup / 限定：`总 3★ 2.3%（UP 0.7% + 其它 1.6%）` + `2★ 16.2% · 1★ 81.5%`
- Fes：`总 3★ 4.4%（UP 0.7% + Fes 0.2% + 其它 3.5%）` + `2★ 14.1% · 1★ 81.5%`

「操作」列：每行一个 **「恢复本组默认」** 按钮（`btn btn-sm`），点击弹浏览器 `confirm()`：

> 把「Pickup」整组恢复为默认值？该组所有字段都会被重置，保存后立即生效。

表格底部（同一张卡）：

- 蓝色 **「保存（整份提交）」** 按钮。
- 灰字：`保存成功后立即生效，无需重启服务端；服务端会先备份上一份配置。`
- 若旧 `gacha_config.json` 接管中，额外黄字：`注意：旧 gacha_config.json 正在接管，保存会写入 gacha_rates.json，但清理旧文件前不会改变实际抽卡。`

实现细节：

- **一个保存表单**（`id="gacha-save-form"`）位于表格之后；表格里的输入用 HTML5 `form="gacha-save-form"` 关联，因此不会出现嵌套 form。
- 每个分组的恢复按钮各自是一个独立 POST 小表单（在单元格内），带 `_csrf`、`action=reset_group`、`scope=<分组>`。
- 保存时整份提交 `rates[Normal][...] / rates[Pickup][...] / rates[Limited][...] / rates[Fes][...]`；常驻不会提交 UP / Fes 字段（服务端会 400）。

### 4.7 「整体恢复」卡

- 说明：会把常驻 / Pickup / 限定 / Fes 四个分类全部恢复为服务端出厂 defaults，并清掉覆盖文件里的自定义值，立即生效。
- 黄色 **「恢复全部默认」** 按钮。
- 表单带 `_csrf`、`action_token_field('gacha-reset-all')`、`action=reset_all`、`confirm_all=1`。
- `onsubmit` 弹浏览器 `confirm()`：`确定把四个分类全部恢复为出厂默认值吗？当前所有自定义值都会被覆盖。`
- 服务端再校验一次性令牌（`action_token_check`）和 `confirm_all=1`，成功后写审计日志。
- 灰字说明：`会二次确认（浏览器 confirm + 服务端一次性令牌），并写入审计日志。`

### 4.8 页面底部

沿用面板现有 `page_footer()`：MySQL ⇄ cards.json 同步说明 + 退出登录等，未改动。

---

## 5. 数据读写与校验

### 5.1 调用的 API（全部经 `inc/ba.php`，带 `X-Admin-Key`）

| 动作 | 请求 | 封装函数 |
|---|---|---|
| 读 | `GET /api/admin/gacha/rates` | `gacha_rates_fetch()` → `ba_get()` |
| 保存 | `POST /api/admin/gacha/rates`，body `{"rates":{...}}` | `gacha_rates_save($rates)` → `ba_post()` |
| 恢复单组 | `POST /api/admin/gacha/rates/reset`，body `{"scope":"Pickup"}` | `gacha_rates_reset($scope)` → `ba_post()` |
| 恢复全部 | `POST /api/admin/gacha/rates/reset`，body `{"scope":"all"}` | `gacha_rates_reset('all')` → `ba_post()` |

`gacha_rates_unpack()` 统一处理：

- HTTP 非 2xx：直接用 `ba_http` 的 error（如 `HTTP 502`、`连接服务端失败：...`）。
- HTTP 2xx 但 `ok:false`：取 `error` 原文。
- 2xx 且 `ok:true`：校验 `rates` 含四个分类且每个分类的字段齐全（缺任何一项都当错误，**绝不补 0**，防止保存时把缺的组清零）。
- 附带读取 `defaults / isDefault / version / updatedAt / legacyOverrideActive / legacyOverridePath / warnings / lastError / filePath / overrideFileExists / overrideFileValid / backupFile / changed`；缺失字段按可选处理，兼容任务给出的最小契约。

### 5.2 服务端校验 + 前端校验

服务端（`gacha_rates_validate()`，保存前执行）：

| 规则 | 错误示例（flash 原文） |
|---|---|
| 缺少分类/字段 | `保存失败：「Fes」缺少「2★ 率」(srRate) 字段` |
| 非整数 / 负数 / 小数 / 空白 | `保存失败：「Pickup · UP 出率」必须是不带小数点的整数（0–1000），收到 “abc”` |
| 超出 0..1000 | `保存失败：「常驻 · 总出彩阈值」必须在 0–1000 之间（收到 1001）` |
| `ssrThreshold < upSsrRate` | `保存失败：「Pickup」的总出彩阈值（23）必须 ≥ UP 出率（30）` |
| `ssrThreshold < fesSsrRate` | `保存失败：「Fes」的总出彩阈值（44）必须 ≥ Fes 专属（45）` |

前端：

- `type=number min=0 max=1000 step=1 required`，浏览器先挡非法值。
- 提交时再检查 `ssrThreshold >= upSsrRate`、`ssrThreshold >= fesSsrRate`，不满足 `alert` 并阻止提交；**服务端仍会再校验一次，以服务端为准**。

### 5.3 百分比的算法（页面显示用）

- 单位换算：`value / 10`，例如 `23 → 2.3%`、`185 → 18.5%`、`30 → 3%`；0 显示 `0%`，1000 显示 `100%`。
- 实际出率按判定顺序推导（与 `ShopManager` 一致，已核对源码）：
  - UP 段：`[0, upSsrRate)`
  - Fes 段：`[upSsrRate, fesSsrRate)`（仅 Fes 池）
  - 其它 3★ 段：`[max(upSsrRate, fesSsrRate), ssrThreshold)`
  - 2★ 段：`[ssrThreshold, srRate)`
  - 1★ 段：`[max(srRate, ssrThreshold), 1000)`
- 所有段宽都做 `max(0, ...)`，异常配置（如 `fesSsrRate < upSsrRate`）不会显示负数。

---

## 6. 审计日志（每次保存 / 恢复都写）

动作名：

- `gacha.rates.save` — 保存
- `gacha.rates.reset` — 恢复单个分组
- `gacha.rates.reset_all` — 恢复全部

示例（实际写入 `audit_logs.target` / `detail`）：

1) 保存（服务端返回 `changed` 时优先用服务端的 diff）：

```text
action: gacha.rates.save
target: 抽卡概率
detail: 变更：常驻 总出彩阈值(ssrThreshold) 30→35；Pickup UP 出率(upSsrRate) 7→9；
        备份=gacha_rates.backup.20261119_024000.json；isDefault=0
```

2) 服务端没有返回 `changed`（或兼容最小契约）时：保存前先 GET 一次当前值，自己算 diff，仍写「分类 字段 旧→新」。

3) 恢复单个分组：

```text
action: gacha.rates.reset
target: 抽卡概率 · Pickup 恢复默认
detail: 旧值→新值：Pickup 总出彩阈值(ssrThreshold) 30→23；Pickup UP 出率(upSsrRate) 9→7；
        备份=gacha_rates.backup.20261119_024100.json
```

4) 恢复全部：

```text
action: gacha.rates.reset_all
target: 抽卡概率 · 全部分类恢复默认
detail: 二次确认=前端 confirm + 服务端一次性令牌；旧值→新值：常驻 总出彩阈值(ssrThreshold) 35→30；
        Pickup 总出彩阈值(ssrThreshold) 30→23；...；备份=gacha_rates.backup.20261119_024200.json
```

失败也会记一条（`失败：<服务端 error 原文>`），便于排查「谁在什么时候点了但没成功」。

---

## 7. 本地验证结果

### 7.1 `php -l`（全部通过）

本地使用便携 PHP **8.2.35 (NTS, VC++ 2019 x64)**（与线上 README 记录的 8.2.31 同系列）：

```text
$ php -v
PHP 8.2.35 (cli) (built: Oct 26 2026 09:48:31) (NTS Visual C++ 2019 x64)

$ php -l inc/gacha.php
No syntax errors detected in C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\panel_work\p0rates\inc\gacha.php

$ php -l pages/gacha_rates.php
No syntax errors detected in C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\panel_work\p0rates\pages\gacha_rates.php

$ php -l inc/helpers.php
No syntax errors detected in C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\panel_work\p0rates\inc\helpers.php
```

### 7.2 纯逻辑自测（临时脚本，不在交付物里）

对 `inc/gacha.php` 跑了 **53 条断言**，全部通过，覆盖：

- 分组/字段顺序与标签
- `‰ → %`：0 / 7 / 23 / 30 / 185 / 1000
- 默认值规范化（与服务端 `Data/gacha_rates.defaults.json` 一致）
- 分段推导：Pickup `7/23/185 → 0.7% + 1.6% = 2.3%`，2★ 16.2%，1★ 81.5%；Fes `7/9/44/185 → 0.7% + 0.2% + 3.5% = 4.4%`；Normal `30/185 → 3%`
- 校验：缺字段、非整数、负数、1001、`ssr < up`、`ssr < fes`、字段是数组、`rates` 整体缺失
- diff 文案 / `changed` 中文化 / `describe`
- `unpack`：200 正常、400 `ok:false`、502 HTML、2xx `ok:false`、200 缺 `rates`、缺分类、缺字段

### 7.3 本地 mock API 集成测试

用 PHP 内置服务器在 `127.0.0.1:5000` 起了一个 mock（只在本机临时跑，已关闭），真实调用 `inc/gacha.php`：

- GET：校验 `rates/defaults/isDefault/legacyOverrideActive/legacyOverridePath/warnings/version/status`
- POST 保存：校验 URL `/api/admin/gacha/rates`、`X-Admin-Key: test-key-123`、body 形状 `{"rates":{...}}`、整数不是字符串、响应 `changed/backupFile/isDefault`
- POST 400：校验 `ok:false`、HTTP 400、`error` 原文原样带回、`raw_text` 是 JSON
- POST reset：单组 `{"scope":"Pickup"}`、全部 `{"scope":"all"}`、返回值与 mock 状态
- 逐条检查 mock 收到的 6 个请求：每条都带 `X-Admin-Key`（本组共 **45 条断言**，全部通过）
- 关掉 mock 后 GET：`ok:false`、`status:0`、`error:"连接服务端失败（...）"`、`raw_text:""`（页面会显示错误 + `(空响应体)` 折叠块）

全部通过。

### 7.4 渲染 / HTML / JS 检查（本地）

- 用临时 harness 加载**真实的** `pages/gacha_rates.php` 模板（只替换 bootstrap 的 require/`gacha_rates_fetch()`，模板本体不改），用 PHP 内置服务器 + 面板原 `assets/app.css` 渲染 `custom / default / legacy / fail` 四种状态：
  - 四种状态都 `HTTP 200`，输出中没有 `Fatal error / Warning / Notice / Deprecated`。
- DOM 结构检查（PHP DOMDocument）：
  - 6 个 `<form>`，**0 个嵌套 form**
  - 4 行 `data-gacha-row`，每行输入数 `2 / 3 / 3 / 4`，各 1 个「恢复本组默认」按钮
  - 12 个输入都通过 `form="gacha-save-form"` 关联到保存表单，且 `name` 都是 `rates[...]`
  - 6 个表单全部带 `_csrf`；整体恢复表单带 `_atoken`
- 页面内联 JS：
  - `node --check` 语法通过
  - 用最小 DOM shim 跑函数逻辑，验证 `pct / bands / sync / 提交前阈值检查`：Normal、Pickup、Fes、`up=0` 的 Fes、越界 1200、非法 `up > ssr` 的 alert 文案，全部通过
- Edge headless 截图（1400px 宽）核对布局；四种状态的实际截图见本地临时文件，未放进仓库。

---

## 8. 部署步骤（给 srv-ops）

### 8.1 传文件

站点根：`/www/wwwroot/ba_cardadmin`

从工作副本上传 **3 个文件**：

```text
inc/gacha.php            -> /www/wwwroot/ba_cardadmin/inc/gacha.php        (新增)
pages/gacha_rates.php    -> /www/wwwroot/ba_cardadmin/pages/gacha_rates.php (新增)
inc/helpers.php          -> /www/wwwroot/ba_cardadmin/inc/helpers.php       (覆盖，先备份)
```

建议命令（在服务器上由 srv-ops 执行，路径按实际账号）：

```bash
cd /www/wwwroot/ba_cardadmin
cp -a inc/helpers.php inc/helpers.php.bak.$(date +%Y%m%d_%H%M%S)
# 上传/覆盖上面三个文件
chown www:www inc/gacha.php pages/gacha_rates.php inc/helpers.php
chmod 644 inc/gacha.php pages/gacha_rates.php inc/helpers.php
```

不要动 `config.php`、`sql/`、`cron/`，不需要执行任何 SQL。

### 8.2 语法检查（服务器上）

```bash
php -l /www/wwwroot/ba_cardadmin/inc/gacha.php
php -l /www/wwwroot/ba_cardadmin/pages/gacha_rates.php
php -l /www/wwwroot/ba_cardadmin/inc/helpers.php
```

### 8.3 是否要 reload php-fpm

- 本次是纯 PHP 文件新增/覆盖，**通常不需要 reload**。
- 先确认 opcache 是否按时间戳失效：

```bash
php -i | grep -E 'opcache.enable|opcache.validate_timestamps|opcache.revalidate_freq'
```

- 若 `opcache.validate_timestamps=0`（或 `revalidate_freq` 很大），再 reload 对应 PHP-FPM（宝塔通常是 `php-fpm-82`）：

```bash
systemctl reload php-fpm-82    # 或 /etc/init.d/php-fpm-82 reload
```

- 不需要重启 C# 服务端、MySQL、nginx。抽卡概率是服务端读文件热加载的（P0RATES 已有实现），本页改动不触碰服务端。

### 8.4 部署后验证清单

1. 浏览器登录管理站，左侧「玩家」组应出现 **「抽卡概率」**，点进去标题是 **「抽卡概率设置」**。
2. 页面应显示当前状态（默认值 / 已自定义）、最后修改时间、版本、配置文件路径。
3. 对照服务端（srv-ops 在服务器上执行，面板不替代）：

```bash
KEY='<Config.json 里的 AdminApiKey>'
curl -s -H "X-Admin-Key: $KEY" http://127.0.0.1:5000/api/admin/gacha/rates | head -c 800
```

  面板上显示的四个分类数值应与该 JSON 的 `rates` 一致。
4. **保存**：把常驻 `ssrThreshold` 从 30 改成 31 → 保存 → 应看到绿色 flash「已保存，立即生效（1 项变更）」，刷新后状态变「已自定义」、最后修改时间更新。
5. **恢复本组**：点 Pickup 的「恢复本组默认」→ 确认 → flash「已把「Pickup」恢复为默认值，立即生效」。
6. **恢复全部**：点「恢复全部默认」→ 浏览器 confirm → 再确认 → flash「已恢复全部默认值，立即生效」。
7. **审计**：打开「审计日志」，筛选 `gacha.rates`，应看到每次保存/恢复一条，detail 含「分类 字段 旧→新」和备份文件名。
8. **旧配置警告**：若服务器上 `gacha_config.json` 含非空 `custom_rates`，页面顶部应出现红色警告；这是预期行为，需运维清理旧文件后才会消失。
9. **失败兜底**（建议在测试环境做，不要改生产设置）：把系统设置里的服务端地址临时改错，刷新页面应看到红色错误条 + 可展开的原始响应，表格不显示、不能保存；改回后「重新读取」恢复。

### 8.5 回滚

```bash
cd /www/wwwroot/ba_cardadmin
mv inc/gacha.php inc/gacha.php.disabled          # 或删除
mv pages/gacha_rates.php pages/gacha_rates.php.disabled
cp -a inc/helpers.php.bak.<时间戳> inc/helpers.php
```

- 无数据库变更，无需回滚 SQL。
- 如果已经通过本页改过概率：服务端每次写入都会在 `Data/` 下留 `gacha_rates.backup.*.json`（保留最近 10 份），可由 srv-ops 恢复；或直接在页面上「恢复全部默认」。

---

## 9. 已知限制 / 注意事项

1. **旧 `gacha_config.json` 不归本页管**：任务要求「不要写文件」，所以本页只检测并警告，不会删除/修改它。清理必须由运维在服务端做。
2. **`legacyOverrideActive: true` 时保存仍会写 `gacha_rates.json`**：数值会落盘，但旧文件清理前不生效；页面在保存按钮旁用黄字明确提示了这一点。
3. **2★ 的语义**：`srRate` 也是绝对阈值，不是「2★ 占比」。页面已用灰字说明，并按判定顺序显示真实的 2★ / 1★ 区间占比；如果只按 ‰÷10 读会误解。
4. **POST 失败的错误展示**：flash 中显示服务端 `error` 原文，并附最多 300 字符的原始响应；GET 失败才显示完整原始响应（折叠）。这是为了不把大段响应塞进 `sessions.flash`。
5. **兼容性**：页面使用 HTML5 `form="..."` 关联输入、`<details>`、`confirm()`，现代浏览器（Chrome/Edge/Firefox/Safari 近版本）均支持；面板现有环境满足。
6. **本地环境没有线上 MySQL/C# 服务端**：本轮没有做「真实数据库 + 真实 C# 服务」的端到端点击，只做了 PHP 语法、纯逻辑、真实 HTTP 封装对 mock API、真实模板渲染 + 浏览器截图；上线后按 §8.4 做一次保存/恢复/审计的冒烟即可。
7. **无新表、无新设置项、无新依赖**：`settings` / `audit_logs` / `sessions` 都复用现有表；导航项是 `nav_items()` 里的一行。
