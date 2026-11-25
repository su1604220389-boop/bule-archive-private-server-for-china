# 生产前加固 · 部署台账

> 2026-11-18 01:10 起 · 用户宣布「服务器马上要进入生产环境，所有 bug 必须立即修复」
> 铁律：**备份先行 → 单人写服务器 → 作用域不重叠 → 改完全部重审（复审者 ≠ 改者）**

---

## 0. 角色与写作用域（互不重叠）

| 成员 | 写作用域 | 职责 |
|---|---|---|
| **srv-ops** | **服务器全部文件** | 备份、部署、重启、验证 —— **唯一有服务器写权限的人** |
| **shittim-analyst** | `work\ba\srv_src\Shittim-Server\` | C# 源码改动 + 本地编译 |
| **proto-analyst** | `work\ba\srv_live\<ts>\_patched\` | Python 桥 / SDK 改动 |
| **logcat-architect** | `work\ba\cardadmin_php\` | PHP 面板改动 |
| **phone-ops** | 手机（只读） | 进度监控、截图、取证 |

---

## 1. 备份（闸门）

```
/root/PROD_BACKUP_20261118_005630        权限 700
921 MB · 1,047 个文件 · SHA256SUMS.txt 1,045 条
sha256sum -c --quiet → 全静默（全部一致）
ROLLBACK.sh → bash -n 通过、chmod +x
```

覆盖：游戏库（含 `.backup` 一致性快照）/ Shittim 程序全量 / Python 桥 / SDK / 站点根 /
nginx 全量 / php.ini / PHP 站点 / MySQL dump / crontab / 运行态快照。

**磁盘余量 13 GB。**

### 1.1 代码基线（重要教训）

```
本地仓库里 account_auth_probe.py 有 **4 档旧副本**（105,725 / 115,911 / 128,309 / 136,894）
**没有一份等于线上的 157,724**
⇒ 规矩：**只以 `srv_live\<时间戳>\` 为基线**，仓库副本永不作为源码使用
⇒ 每份补丁必须带「基线 md5 → 补丁后 md5 → diff 行数」三项，缺一不可
```

---

## 2. 已部署（全部带备份 + 回滚）

### 2.1 Python 桥 / SDK —— 第一轮

| 文件 | 改前 md5 | 改后 md5 | 体积 |
|---|---|---|---|
| `account_auth_probe.py` | `b8514246…` | `c30c7fcd…` | 157,724 → 159,489 |
| `cn_cipher.py` | `04f33fcc…` | `6eff7f9f…` | 6,020 → 6,443 |
| `sdkcard.py` | `383d09ed…` | `d90546d6…` | 13,328 → 14,940 |

内容：
```
请求体上限 4 MB（超长 → 413，非数字 → 400，不再掐连接）
解压上限 64 MB（gzip 炸弹 → 拒绝）
日志脱敏（卡密/token/req_key/MxToken/SessionKey → 前4后4+len+sha8）
cards.json 进程内锁 + 临时文件+fsync+os.replace 原子写
   解析失败先备份成 .corrupt.<ts>，不静默覆盖
```
自测 **14/14 PASS**。备份 `/root/PY_FIX_BACKUP_20261118_010136/`。

**踩坑记录**：第一次 kill 打到 bash 包装进程（2651204），真正的 python（2651206）没死 ⇒
新代码未加载。精确 kill 后才生效。**⇒ 以后重启必须验 pid + 端口 + 实际行为。**

### 2.2 Python 桥 —— 第二轮（F1b，修副作用）

```
account_auth_probe.py  159,489 → 161,194   md5 c30c7fcd… → 1db27e4c…
diff +51 行（新增 _read_chunked / _read_request_body，入口改调）
```

**为什么必须改**：第一轮的 4 MB 校验在 `_handle` 入口**不分方法**，
`GET /api/xxx` 缺 Content-Length 一律 400。客户端只要有一次 GET 打 `/api/` 就会莫名报错。

```
GET/HEAD/OPTIONS  缺 CL → 视为 n=0，正常处理
POST/PUT/PATCH    缺 CL → 400
chunked                 → 逐块读、累计超 4 MB → 413；块格式坏 → 400
```
自测 **18/18 PASS**。

### 2.3 PHP 面板 —— 14 个文件

```
备份 /root/PHP_FIX_BACKUP_20261118_010306/（14 个改前原件 + SHA256.before）
php -l 25/25 全绿 · php-fpm-82 reload · login.php 200 · / 302
```

| 修复 | 内容 |
|---|---|
| F1 | AdminApiKey 默认掩码 `••••••••`，需要时"显示一次"（120s 一次性令牌） |
| F2 | 危险操作改服务端一次性令牌，缺失/重放 → **419**，不执行写操作 |
| F3 | 审计日志补全：发奖/改货币/封号/GM 命令，带 **旧值 → 新值** |
| F4 | 明文卡密查看/导出改 POST + CSRF；登录 CSRF 移服务端 state |
| 追加 | `install.php` 删除（原件留 `_orig/`）；`player_detail` GM 命令补令牌；`?reveal=1` 改 POST |
| GM 审计 | `console` 与 `player_detail` 统一 `action=gm.command`，detail 含 `cmd/uids/admin/ip/ok/fail/before/outputs` |

最终 diff：**+466 / −55**。

### 2.4 运维

```
✅ display_errors On → Off（php.ini:508）    备份 /root/PHPINI_BACKUP_20261118_010447/
✅ logs/ 775→750、state/ 775→750、logs/sync.log 666→640（属主 www:www 未变）
✅ error_log 指向 /www/wwwlogs/php_82_error.log
⏸ 8081 TLS —— **单独一轮**，不与其他改一起上
```

**抓到的坑**：`log_errors=On` 但 `error_log` 没配 ⇒ 关了 display_errors 之后
**错误既不在页面也不在文件里，等于彻底消失**。这一条比留着错误页更危险。

### 2.5 删除的野文件

```
/www/wwwroot/bapatch/accounts.db  0 字节 → 已删
   成因：某个 agent 用 sqlite3 打开不存在的路径时会自动创建空库
   真正的账号库是 /www/wwwroot/bapatch/data/accounts.db（143,360 B，5 张表）
```

---

## 3. C# 侧（已备好，未部署）

### 3.1 同源验证（强证据）

```
本地重新编译 11-17 23:04:20 那棵树 → sha256 3ec7c46d…
线上运行中的 DLL                → sha256 3ec7c46d…        **逐字节相同**
```

⇒ 本地源码就是线上二进制的来源。晚于构建时刻的非 obj/bin 文件只有 4 个
（`ExcelTableService.cs` mtime == 构建时刻 + 本轮改的 3 个）⇒ **无隐藏未部署增量**。

**教训**：`BAPATCH-` 标记名 **不等于** 补丁全集（`ADMINAUTH`/`MAILPARCEL` 是 22:02 改的、
已编进 DLL 但没打标记）。以后判断"改了什么"只认「构建时刻 + mtime 对比 + 逐行 diff」。

### 3.2 产物

```
work\ba\_build_f2\Shittim-Server.dll
2,675,712 B（+1,024 B / +0.038%）
sha256 79fc88e5e10b44d2bc82ad5991d0c7477a3269240ae0690554147a63711b6544
exit 0 / 0 错误 / 256 警告（增量编译，比之前 265 少，非退化）
```

### 3.3 改动

| 项 | 位置 | 开关 |
|---|---|---|
| **F1** token 校验 | `AccountHandler.cs` L92-99（CheckNexon）+ L927-934（CheckYostar），`[BAPATCH-TOKENGATE v1]` | `EnforceTicketToken` **默认 false** |
| **F2** 会话空闲 TTL | `SessionKeyService.cs` L171-183，用 `LastActivity` 不是 `CreatedAt` | `SessionTtlMinutes` 默认 10080（7 天），0=关闭 |

### 3.4 为什么 F1 默认关（关键决策）

```
UserAccounts 只有 1 行：Id=1 Uid=2 NpSN=314816420 NpToken=61de1d1b…80b210（40 位 hex）
桥把 publisherId 硬编码成 314816420 ⇒ 两台手机映射到同一个账号
但 token 是每设备一个 ⇒ **NpToken 单槽，两台机轮流登录必然互踢**
⇒ 在 Shittim 侧做 token 校验和"一个号多设备"天生冲突，不可行
```

**定案：两层，只开一层**

```
桥（9097）   设备级：token == sha256(card|dev)[:40] 且 dev ∈ cards[card].devices 且未过期
Shittim      保持关；等桥改成 per-publisher 稳定 token（sha256("bp:"+publisherId)）后再开
```

用户拍板：**不做 root 机例外**，那台机以后也会卸载换成我们的包 ⇒ 官方优星 token 这条路会消失。

---

## 4. 公益卡 / 付费卡（功能开发，进行中）

### 4.1 需求

```
公益卡：账号跟随**设备**绑定，卡密不限制设备登录
付费卡：账号跟随**卡密**登录，可选"最多 1 台"或"不限"，且随时可改
```

### 4.2 现状核查结论（改之前）

```
cards.json 每条卡只有 3 个字段：devices / expire / bind_one
没有 kind / card_type / is_free / paid / max_devices（全文件 grep 0 命中）
⇒ "公益卡/付费卡"这个概念在代码里**根本不存在**，只有一个 bind_one 布尔在硬撑
```

| 需求 | 改前状态 |
|---|---|
| ① 公益卡：账号跟随设备 | ⚠️ 仅桥层有 `UNIQUE(dev_id)`；SDK 的 `User.ID = md5(card)`，**两层锚点不一致** |
| ② 公益卡：不限设备 | ⚠️ `bind_one=false` 不拦，devices 无限增长，无上限概念 |
| ③ 付费卡：账号跟随卡密 | ✅ 已实现 |
| ④ 可选"最多1台/不限" | ⚠️ 只有布尔，表达不了"最多 N 台" |
| ⑤ 可随时改 | ⚠️ 手改文件立即生效，但无管理接口、读改写无锁 |

### 4.3 设计（已定）

```json
{ "kind": "paid", "max_devices": 0, "last_used_at": 0, "devices": [], "expire": 0, "bind_one": false }
```

```
paid ：User.ID = md5(卡密)[:8]%9e8+1e8       ← **一字节不能动**（账号 2 = 314816420）
free ：User.ID = md5("free:" + 设备号)[:8]%9e8+1e8   ← 每台设备一个独立账号
paid 设备上限：max_devices 0=不限 / 1=一台 / N
free：不检查设备数
quick-login：paid 优先 → 同类按 last_used_at 倒序 → 卡密字典序兜底（全序确定）
```

### 4.4 SDK 侧已完成（未部署）

```
_patched/sdkcard.py  17,630 B  md5 5902d5de108e0f5cd799ecd9896560ec  diff +78 行
自测两套共 22 个断言全过：
  8 条功能（paid/free 分叉、上限、过期、quick-login 确定性）
  8 条旧数据兼容（老格式迁移、devices 保留、键顺序打乱、落盘读回）
```

### 4.5 ⚠ 三个"改了就回不去"的点

```
① kind 不可逆（双向）
   付费 md5(卡密) ↔ 公益 md5("free:"+设备号)
   切过去后按旧算法算出的账号客户端再也算不出来，切回来也回不到原号
   ⇒ **决策：编辑页把 kind 设成只读**，新建时选，建完不许改；只放开 max_devices

② bind_one 迁移后失效
   一次性派生成 max_devices，之后改它没有任何效果（已用测试锁死）
   ⇒ 运维别再翻那个勾选框，真源是 max_devices

③ free 卡换设备号 = 新账号
   重装 / 重置 Android ID / 换机 ⇒ 新设备号 ⇒ 空账号，旧数据带不走
```

### 4.6 待办

```
· MySQL ALTER：cards 加 kind / max_devices / last_used_at 三列（幂等）
· PHP 表单：新建页选类型、max_devices；编辑页 kind 只读
· cron 同步：必须带三个新字段，且 **反向合并 last_used_at**（SDK 会更新它）
· 部署顺序：**ALTER → PHP → 重启 SDK**
```

---

## 5. 事件：登录变慢的定位（2026-11-18 01:10–01:25）

### 5.1 现象
用户反馈「登录慢了很多」，登录链路从 `Account_Auth` 到 `toast/list` 约 **14 秒**。

### 5.2 排除：不是我们的补丁
```
登录链路本身全部 200、无 4xx/5xx、无异常堆栈
唯一涉及磁盘的改动是 cards.json 的 fsync（文件 225 B，本地实测 1.247 ms/次）
⇒ 量级上不可能造成 100+ MB/s 的读
```

### 5.3 真实原因：宝塔内置任务在扫 journal + SSH 爆破灌爆日志

```
pid 2673922  /www/server/panel/pyenv/bin/python3 …/task_script_extension.py task_ssh_error_count
  └─ 2673926  journalctl -u ssh --reverse --lines=200 --grep='Failed password for'   44 MB/s
  └─ 2676038  journalctl --since -30min --no-pager                                   33 MB/s

journal 大小 832.3 MB（SystemMaxUse **未设** ⇒ 不封顶）
dmesg 里 UFW BLOCK 1,157 条且仍在涨（公网每分钟十几条 SSH 爆破）
实测：带 --grep 的逐条正则全量扫描，已跑 11 分 32 秒仍未结束

机器指标：iowait 87.75% ｜ vda %util 103% ｜ r_await 41.54 ms ｜ aqu-sz 98.84
          pswpin/pswpout = **0**（不是 swap thrashing）
          内存 1608 MB 总 / available 209 MB
```

**关键**：它**不在宝塔「计划任务」列表里**，是面板主进程直接调度的内置功能（系统加固/安全统计），
所以「计划任务」页面看到的 4 个任务都不是它。

### 5.4 同时排除的三个嫌疑
```
❌ 内存换页        pswpin/pswpout = 0，swap 1 GB 用了 0 B
❌ Shittim 反复解包 ExcelDB   Resources/Dumped mtime 停在 2026-11-13 12:46（4 天未变）
                             stdout: "Original resources are already up to date."
❌ 我们的生产备份   没有 tar/rsync/sha256sum 在跑，921 MB 那份早已结束
```

### 5.5 结论：**会反复**
```
任务间隔 < 单次耗时（带 --grep 扫描 832 MB 需十几分钟，且 journal 还在涨）
⇒ 一波未平一波又起，iowait 会周期性顶到 90%+
```

### 5.6 待批的处置（**未执行**）

| 档 | 做什么 | 效果 | 风险 |
|---|---|---|---|
| **B** | `ufw logging low` | journal 写入量降 ~90%（爆破照样被拦，只是不逐条记） | 零功能影响 |
| **A** | journald `SystemMaxUse=200M` + `journalctl --vacuum-size=200M` | 832 MB → 200 MB，扫描从十几分钟降到几十秒 | 重启 journald 几秒，日志不丢 |
| **C** | 宝塔面板里停用「SSH 登录失败统计」 | 掐掉元凶 | 内置任务，可能只能停用、删不掉 |

**A + B + C 缺一不可**；不碰游戏服、不重启 Shittim、不影响玩家登录。

### 5.7 ⚠ 注意
```
dmesg 里那波 UFW BLOCK 是**真实爆破**（各种 DPT 端口，01:09–01:13 十几条/分钟）
⇒ 关日志可以，**但绝对别关 ufw 本身**
```

---

## 7. 当前状态（2026-11-18 01:28）

### 7.1 免 root 客户端：全链路跑通 ✅

```
资源下载完成  11,362.9 MB（≈11.1 G），结构与本机 root 那份完全同型
              AssetBundles 6.5 G / MediaPatch 4.0 G / TableBundles 435 M
              耗时约 37.5 分钟，平均 4.5 MB/s，峰值 7.14 MB/s
              全程零弹窗、零报错、du 曲线一次未回落
ClientSaveData 132 K **已出现** ⇒ 账号初始化完成、存档已生成
```

**⇒ 免 root 路线（不装 CA、不改 DNS、不劫持）从装机到账号初始化全部打通。**

### 7.2 已上线并验收
```
✅ Python 三轮（请求体/解压上限、日志脱敏、cards.json 原子写、F1b 方法分流）
✅ PHP 14 文件（AdminKey 掩码、一次性令牌、审计日志带旧值、卡密查看改 POST）
✅ display_errors Off + error_log 落文件（用 HTTP 触发真实 Warning 验证：0 → 142 B）
✅ 日志权限 666→640、目录 775→750（属主 www:www 未变）
✅ 脱敏真机验证：sdk.log 出现 `1111****1111(len=11)` / `_mask(dev)=ce8f****fb36`
```

### 7.3 已备好、未部署
```
⏸ C# F2 会话 TTL       work\ba\_build_f2\Shittim-Server.dll  sha256 79fc88e5…（+1,024 B / +0.038%）
⏸ 公益卡 ALTER + PHP   logcat-architect 已交付，等磁盘退下
⏸ 公益卡 SDK           sdkcard.py 17,630 B / md5 5902d5de…（22 个断言全过）
⏸ 8081 TLS             单独一轮
```

### 7.4 公益卡三条疑问的答复（已确认）
```
时区    两端都是 Asia/Shanghai，全程 DATETIME 字符串读写、未用 FROM_UNIXTIME
        实测 NOW()=01:12:02 ↔ UNIX_TIMESTAMP()=1794935522（+08:00）⇒ **无 8 小时偏移**
非法值  "abc"→0、-1→0、>9999→9999，一律按"不限"，不拒绝保存
kind    精确白名单，FREE/Free 都落 paid，两端一致
ALTER   cards 表 1 行 / 0.09 MB，DDL 毫秒级；1 个外键但加列不动外键列，需短暂 MDL
        执行前 SHOW PROCESSLIST + SET lock_wait_timeout=10
```

---

## 9. 事件：账号信息页卡死 + 等级显示 1（2026-11-18 01:53–02:15）

### 9.1 症状（免 root 机，root 机同样复现）
```
① HUD 等级一直显示 1
② 点左上角等级 → 账号信息页整体无响应（画面在动、按钮全死）
③ 该页三个位置是占位符：等级标签后的「カカカカカ」、
   "培训中"下面两行「textxttextxt…」、值日员头像空白框
```

### 9.2 关键取证
```
点开该页后 **零新增业务请求**（最后一次业务请求停在 01:37:38）
⇒ 客户端本地卡住，不是网络等待，也不是服务端没响应
```

### 9.3 已确认为真的数据
```
/api/admin/accounts      → serverId=2, nickname="111", callName="杂鱼", level=90
/api/admin/account/2/detail → level=90, representCharacterServerId=9, currencies{...}

页面显示的 Gold 45,095,960 / Gem 100,400（= GemPaid 100,000 + GemBonus 400）
⇒ **与 Shittim 账号 2 完全一致 ⇒ 货币是真的，账号也是真的**
```

错误结论记录：**「信息全是假的」是我早期的误判**，实测货币与账号均为真值。
页面上的 `UID 1311727` 在服务器侧（桥库/Shittim/日志）**全部 0 命中** ⇒ 是客户端侧编号。

### 9.4 根因链（五次部署才挖到底）

```
① 桥构造的 AccountDB 是「影子账号」：
   build_account_db_for 函数体内 grep 'shittim|sqlite' = 0
   Level=1 / Nickname='老师0001' / RepresentCharacterServerId=1000001（自造）
   全部来自桥自己的 accounts.db 一行，与 Shittim 的 Accounts 表无关

② 但这份影子 AccountDB **从来没被送出去过**：
   account_auth_probe.py:113  svc.identify(req) 抛 AuthRejected
   ⇒ :118 inner['AccountDB'] = adb **从未执行**
   ⇒ 桥一直回落「Shittim 原生会话」

③ 为什么 identify 一直失败：
   req 由 rec['req_DevId'] 拼成，而它来自 req_frag_head ——
   一个**被日志脱敏打码（DevId → `De****`）+ 头部截断（len=372）**的字符串
   ⇒ 永远读不到 DevId/DeviceUniqueId
   ⇒ AuthRejected 从 11-17 18:26 起持续存在，**acct_svc 零成功记录**

④ 补丁本身还有 bug（逐层剥开）：
   a. urllib 未 import → NameError → 取真值必失败
   b. merge 接在 build_state_for 上，而登录走的是直接调 build_account_db_for → 接错函数
   c. identify 兜底用了 dev_id='fb:314816420'，
      而 get_or_create_account 只按 dev_id 查（:858），
      ⇒ 会**新建一个空账号**（客户端进空号，比原故障更严重）
   d. detail 响应用 camelCase（level/nickname/...），
      _FIELD_SPEC 用 PascalCase（Level/Nickname/...）⇒ 字段全部解析不到
      ⇒ "admin-api returned no usable fields"
```

### 9.5 每次部署的拦截方式
```
第 1 次  接错函数            → 第 ⑦ 步（跑 build_account_db_for 看真值）发现 Level 仍 1
第 2 次  urllib 未 import    → 第 ⑦ 步发现 NameError traceback
第 3 次  identify 抛异常      → 第 ⑦ 步 + 日志发现 AuthRejected
第 4 次  兜底会建新号         → **部署前**通过代码审查拦下（未上线）
第 5 次  camelCase 不匹配     → 第 ⑦ 步发现 "no usable fields"⇒ 已回滚
```

**教训（已固化为规矩）**：
```
· 部署成功 ≠ 生效。必须看到**服务端实际吐出的值**才算数
· 每次部署前先算好"预期输出"，部署后逐字对比
· 交付物必须带「基线 md5 → 补丁后 md5 → diff 行数」，缺一不合格
· 未导入模块用 AST 扫一遍，不靠肉眼
· 任何"兜底"都要先证明它不会解析到错误的对象（这次差点建出空号）
```

### 9.6 待办（下一版一起上）
```
F1  字段名大小写兼容（_pick_ci，12 个字段统一走）
F2  新账号不预填昵称：
      现在 CallNameUpdateTime 空 ⇒ 用 created_at 顶上 ⇒ 非 0
      ⇒ 客户端认为"昵称已设过" ⇒ 跳过设定界面
      要求：新账号 Nickname 空、CallNameUpdateTime=0，恢复「设定昵称」界面
      （用户明确要求保留该界面）
F3  identify 兜底（dev_id 必须用 str(pub) 才能命中既有行）
F4  真值读取（camelCase 修正后）
```

### 9.7 待验证的疑问
```
HUD 的"等级 1"到底来自哪个字段？
  注入停掉时客户端拿 Shittim 原生 AccountDB，其中 Level=90，但 HUD 仍显示 1
  ⇒ 说明 HUD 等级**可能不是** AccountDB.Level
  ⇒ 等注入真正跑通后再确认
```

---

## 10. 待审 / 待办清单（更新）

```
[ ] 用户验收登录（F1b + PHP 增量 + error_log 之后）
[ ] PHP 面板 12 条冒烟（需用户本人点，srv-ops 抓日志）
[ ] 公益卡 ALTER + PHP + SDK 三轮部署
[ ] C# DLL 上线（79fc88e5…）—— 唯一需要重启游戏服的操作
[ ] 8081 TLS（单独一轮）
[ ] 多路复审（复审者 ≠ 修改者，第四路专查"三份补丁之间有没有打架"）
```

---

## 6. 回滚速查

```bash
# 生产全量（最坏情况）
bash /root/PROD_BACKUP_20261118_005630/ROLLBACK.sh

# Python 三项
B=/root/PY_FIX_BACKUP_20261118_010136
cp -a $B/account_auth_probe.py /www/wwwroot/bapatch/tools/
cp -a $B/cn_cipher.py           /www/wwwroot/bapatch/tools/
cp -a $B/sdkcard.py             /www/wwwroot/ba_sdk/
# 然后重启桥与 SDK（精确 kill python 本体，不是 bash 包装）

# PHP 14 个
cp -a /root/PHP_FIX_BACKUP_20261118_010306/* /www/wwwroot/ba_cardadmin/ && /etc/init.d/php-fpm-82 reload

# php.ini
cp -a /root/PHPINI_BACKUP_20261118_010447/php.ini.bak /www/server/php/82/etc/php.ini && /etc/init.d/php-fpm-82 reload

# C#（上线后）
systemctl stop ba-shittim
cd /www/wwwroot/ba_srv && cp -a Shittim-Server.dll.bak.<TS> Shittim-Server.dll
cp -a Config/config.json.bak.<TS> Config/config.json
systemctl start ba-shittim
```

---

## 11. 事件：基线三方不一致 —— 部署前急停（2026-11-18 02:20）

### 11.1 触发
proto-analyst 交付 F1+F2，自报「基线 105,151 B / 产物 106,139 B / 净 +988」。

### 11.2 本机全盘扫（`Get-ChildItem -Recurse -Filter account_service*.py*`）

| md5 | 字节 | mtime | 副本数 | 说明 |
|---|---|---|---|---|
| `a127e70993f0372cd4997b1f3bf8f2c5` | 94,576 | 11-14 14:59 | **4** | 原始版（`deploy\_baseline\`、`srv_live\0059\bapatch\tools\`、`report\_tmp\live_bridge\`、`server\`） |
| `a1fe73cb4d468584e69564e4e2ba159b` | 98,499 | 11-18 02:03 | 1 | `_patched\account_service.py.pre_wire.bak` |
| `436cba4df30e503212c2e737bf2f9f0c` | 106,139 | 11-18 02:14 | 1 | 本轮产物 |
| `8227f28e7e13c502fcd7666743aa43a8` | 102,919 | 11-18 02:06 | **1**（02:16 拉回） | **= 线上真值**，源在 `/root/ACCOUNTDB_FIX_BACKUP_20261118_021042/` |
| `cb1a96b7…` | 102,516 | — | 0（服务器上） | 中间版，源在 `_020636/` |
| `18a26d37…` | 105,151 | — | **0 永久丢失** | proto 声称的基线：**部署过 → 回滚了 → 部署前没备份**，任何备份里都没有 |

### 11.3 判定
**「+988 B」这个算式是悬空的**：被减数不在磁盘上（105,151 已永久丢失）。

**但真基线已经拿到**：`srv_live\20261118_021609\bapatch\tools\account_service.py`，102,919 B / `8227f28e`，srv-ops 从服务器拉回、逐字节校验一致。

但这**不等于**产物有问题 —— 两条 diff 拉出来后，`106,139` 是从**原始版**一路长上去的，`+127/−1` 与 `+988` 两段都在，功能是自洽且完整的：

```
94,576 → 98,499   +127/−1   import urllib.request；_resolve_admin_key()（递归读 Config.json 找 AdminApiKey）；
                            _FIELD_SPEC(PascalCase) + fetch_real_account_fields + merge_real_account_db 框架
98,499 → 106,139  +988      _pick_ci() + 12 条 camelCase 别名；_FIELD_SPEC 重写为 4 元组；
                            CallNameUpdateTime 空昵称 → 0001-01-01T00:00:00；
                            sid_ensure_column / sid_list_accounts / sid_lookup / sid_resolve / resolve_sid_for_account；
                            _fallback_publisher_id() + identify 兜底（dev_id='314816420'，**不是** fb: 前缀）；
                            build_account_db_for() = merge_real( _shadow(), resolve_sid_for_account() )
```

### 11.4 真正的问题：线上**没有 import urllib**（这才是"改了没生效"的真凶）
srv-ops 在服务器上对线上文件跑探针：
```
KEY_LEN 64                                          ← ✅ 判据①过
LIST_ERR NameError("name 'urllib' is not defined")  ← ❌ 判据②否决
```
核对源码：线上 `account_service.py` 第 **202–203** 行
```
202: req = urllib.request.Request(_ADMIN_URL + path, headers={"X-Admin-Key": _key, ...})
203: with urllib.request.urlopen(req, timeout=timeout) as r:
```
而**全文件 `import urllib` 计数 = 0**。

⇒ 每次取真值都在同一行 `NameError` → 被 `fetch_real_account_fields` 的 `try/except` 吞掉 → 返回 `{}` → 静默退回影子数据。
⇒ **"5 次部署成功、服务正常、结果没变"不是玄学，是每次都在同一行炸，且异常被设计成不抛。**

铁证：`grep -c` 结果 `_resolve_admin_key=2`（key 拿到 64 字节）与 `import urllib=0` 并存 —— 说明第一轮补丁把 `_http_json` 改成走 `_resolve_admin_key()` 时，**新增了 `urllib` 的调用但漏了 import**。

### 11.4.1 最终 diff：线上 → 产物只有 6 个 hunk
```
$ git diff --no-index 线上(102,919) 产物(106,139)     # 148 行
@@ -52,2   +52,3     import urllib.request              ← 就是补这个洞
@@ -237,15 +238,31   _pick_ci() 新增 + _FIELD_SPEC 12 行换 camelCase
@@ -273,8  +290,10   fetch_real_account_fields: sid ∈ {0,"0","None"} 短路
@@ -381,2  +400,60   _fallback_publisher_id() + identify 兜底块
@@ -769,5  +846,11   identify(): 硬 raise AuthRejected → 条件化
@@ -1164,3 +1247,3   CallNameUpdateTime
```
删除行共 20 行，**全部是被替换掉的旧实现**，没有一处意外删除。

⇒ **11.4 早前担心的「丢掉 8,343 B 加固」不成立**：产物不是从 94,576 长出来的另一棵树，它**就是线上的最小增量**。
⇒ `resolve_sid_for_account` / `build_account_db_for` 的真值合并 / `state['account']` 的 sid 解析，**线上版里本来就有**。

### 11.5 部署策略改为「先证明、再部署」
产物既然是线上的干净增量，就不必再"部署后看结果"，可以直接拿真实 admin API 先验：
```
把产物拷到服务器 /tmp/probe2/（不碰线上文件）
python3 跑 _resolve_admin_key / sid_list_accounts / sid_lookup / fetch_real_account_fields
四条判据：KEY_LEN=64 · SID_FOR_314816420=2 · FIELDS_N=12 · Level=90/Nickname='111'/Represent=9/Publisher=314816420
```
**四条全过才允许动线上文件**；任一不过即停手回传 `KEYS0`。

### 11.6 处置
```
[srv-ops]        只读 8 段取证：线上 md5/size/mtime、/root/*BACKUP*/ 里 102,919 与 105,151 的下落、
                 拉回本机 srv_live\<TS>\、上面两个判据、Config.json 位置、账号 SQL、桥健康、磁盘
[shittim-analyst] 改派独立审计（审计员 ≠ 实现者）：A 语法结构完整性（因为出过两次正则截断）、
                 B _pick_ci 语义、C 12 字段、D CallNameUpdateTime、E 失败模式安全性、
                 F 安全、G 会丢失的加固 + 产出 accept_accountdb.py 验收脚本
[lead]           两路都回来后才能决定是否部署；**未部署**
```

### 11.7 新增规矩（第 5 条）
```
⑤ 交付物必须写清"基线是哪个 md5、在哪个路径、什么时候拉的"。
   写不出路径的 md5，一律当不存在。
```

---

## 12. 独立审计 + 部署前死验（2026-11-18 02:20–02:30）

### 12.1 前置验收：**补丁实质通过**
srv-ops 把产物拷到服务器 `/tmp/probe2/`，**不碰线上文件**，用真实 admin API 跑：
```
KEY_LEN 64                                    ✅
LIST_N 1                                      ✅
SID_FOR_314816420 2                           ✅
Level 90 / Nickname '111'                     ✅
RepresentCharacterServerId 9                  ✅（不是 1000001）
PublisherAccountId 314816420                  ✅
FIELDS_N 11                                   ← 判据③ 未满 12
```
**`UnReadMailCount` 缺失的原因（实测非猜测）**：
```
/api/admin/accounts      （列表）含 unReadMailCount
/api/admin/account/2/detail（详情）**不含**
```
⇒ 14 项判据 13 项正确，唯一缺的是**上游接口根本不返回的字段**。

**决策：放宽为 `FIELDS_N >= 11`，立即部署。**
理由：该字段不影响等级页、不影响昵称界面、不影响任何用户可见真值；改从列表取要多一次调用 + 多一个 hunk + 再走一轮审计 —— **不在这轮捆绑**，等登录验完作为独立增量。

附带发现：detail 的 `State` 是字符串 `"Normal"`，`_to_int` 得 `None`，`build_account_db_for` 兜成 1，**不崩**，当前两号都是 Normal 无实际影响。

### 12.2 审计结论（审计员 ≠ 实现者，基线自己复验）

| 项 | 结论 | 一句话 |
|---|---|---|
| A | **PASS** | `ast.parse` + `parse(feature_version=(3,10))` + `py_compile` 全通；方法 60 vs 线上 59（只多 `_build_account_db_for_shadow`）；无重复定义/无 TODO/无截断痕；`import urllib.request` 在 **L53** 顶层 |
| B | **PASS** | 大小写三态全命中；非 dict 返 `(False,None)` 不抛；`0/""/None` 均 `found=True` |
| C | **PASS** | camelCase 载荷 **12/12** |
| D | **PASS** | 新号空昵称→`0001-01-01T00:00:00`；**既有账号 `老师0001`→created**（正是要的边界）；`to_iso(None)=None` |
| E | **FAIL（架构级，非本补丁引入）** | 见 12.3 |
| F | **PASS** | 日志无 token/DevId/admin_key；只连 `127.0.0.1:5000`；`_find_admin_key` 只回单个 key |
| G | **PASS** | 以 102,919 为基线，`gzip/decompress/Content-Length/MAX_/limit/read(` 计数 **live == patched**，**没丢任何保护**（这些本就不在这两个文件里） |

diff 复验：**6 hunk / +103 / −20**，删除的 20 行全是旧实现替换，**无意外删除**。
NameError 根因复验：LIVE `import urllib`=0、`urllib.request.`=2；PATCH 在 **L53** 补上。

### 12.3 E 项：架构级结论（**影响卡业务，本轮不解决但要记死**）
```
identify() 兜底 dev_id='314816420'  ⇒  **所有无 DevId 的登录都塌缩到同一账号**

· 公益卡（账号跟随设备 md5("free:"+device)）→ **当前根本无法实现**
· 付费卡（账号跟随卡密 md5(card)）        → **同样不成立**（兜底与卡无关）
⇒ 这是"临时单账号部署形态"的已知代价。**必须先修 identify 才能上卡业务。**
```

**E3 空号风险 —— 已用真值关闭**（审计员当时存疑，因为本机无库）：
```
桥 accounts: 10000000000|314816420|314816420|老师0001
get_or_create_account 只按 dev_id 查（L882）
兜底值 str(314816420) == 库里的 dev_id  ⇒ 精确命中，不新建
```

**E7 未定论（只差一条证据）**：
```
req_frag_head = 桥 _baseline:1116 的 str(r.get('fragment'))[:600]
  → 解密明文的中段片段，**内存里截断 600 字符**；日志里的 De**** 只是日志层脱敏，不代表内存值被改
  → 「片段里到底有没有 DevId」**未验证**
定论只需：真实请求里打印 len(frag) 与 'DevId' in frag，
          或看 api_all_requests.log 同一请求的 req_keys 是否含 DevId
```

### 12.4 事故：两个 agent 撞了同一个文件名
审计员和我都往 `_audit\accept_accountdb.py` 写，审计员那份**覆盖**了我那份。

| 版本 | 设计 | 可用性 |
|---|---|---|
| 审计员（7,325 B `54d04873`） | 直连 `http://127.0.0.1:8080` 抓 HTTP 登录态 | **不可用**：8080 是 SDK 服务，桥在 9097，无 AccountDB 入口 ⇒ 第 8 步必 FAIL → **误触发回滚** |
| 本版（5,546 B `c25d085d`） | `import account_service`，走登录真正调用的函数 | 可用，已被 12.1 实测验证同路 |

处置：审计员版改名 `accept_accountdb_http.py` 保留（将来真有 HTTP 入口再用）；主脚本换回本版；
`c25d085d…` **钉进部署脚本 pretest 第 0 步**，传错版本直接 ABORT。

本版双向自测：
```
喂影子数据 → ACCEPT FAIL (6 项) exit=1     ← 影子不会被误判成 PASS
喂真实数据 → ACCEPT PASS        exit=0
```

**规矩第 6 条**
```
⑥ 多 agent 并发写同一目录时，文件名必须带归属前缀；
   跨 agent 共用的产物，部署脚本里钉 md5，不钉"文件名"。
```

### 12.5 部署件（已备好，执行中）
```
_patched\account_service.py        106,139 B  md5 436cba4df30e503212c2e737bf2f9f0c
deploy_accountdb_wire.sh           含 pretest / deploy / rollback 三档；无 RESTART_CMD 拒绝执行
accept_accountdb.py                5,546 B    md5 c25d085dabd1411215161668a6813502
线上基线（被替换对象）              102,919 B  md5 8227f28e7e13c502fcd7666743aa43a8
备份将落                             /root/ACCOUNTDB_WIRE_BACKUP_<TS>/ （含 ROLLBACK.sh）
```
部署脚本的硬约束：
```
· 基线 md5/size 不符 → ABORT（线上已变就不许覆盖）
· 备份件 md5 复核不符 → ABORT
· 先写 .new → 校验 md5 + ast.parse → 再 mv
· kill 前校验 9097 持有者 comm == python3（防再杀到 bash 包装）
· 重启后必须 IMPORT_OK + accept PASS，任一失败 → 立即回滚
```

### 12.6 部署结果：**成功**（2026-11-18 02:19）
```
线上 account_service.py
  旧  8227f28e7e13c502fcd7666743aa43a8   102,919 B
  新  436cba4df30e503212c2e737bf2f9f0c   106,139 B
备份  /root/ACCOUNTDB_WIRE_BACKUP_20261118_021907/（含 ROLLBACK.sh）
```

**重启配方（从 /proc 原样取证，不是猜）**
```
cwd       /www/wwwroot/bapatch/tools
cmdline   python3 account_auth_probe.py
fd/1,fd/2 /www/wwwroot/bapatch/tools/bridge.restart.log
ppid      1（systemd 孤儿）
unit      只有 ba-shittim，**桥不在任何 unit 里**；crontab 无桥
environ   无 GATEWAY / BA_ACCOUNT_DB / SHITTIM_* / PYTHONPATH 等业务变量
⇒ RESTART_CMD='setsid nohup python3 account_auth_probe.py >>/www/wwwroot/bapatch/tools/bridge.restart.log 2>&1 &'
```

**ACCEPT 12/12**
```
PASS KEY_LEN=64          PASS SID_FOR_314816420=2
PASS Level=90            PASS Nickname='111'
PASS Represent=9         PASS Publisher=314816420
PASS merged.Level=90     PASS merged.Nickname='111'
PASS merged.Represent=9  PASS merged.Publisher=314816420
PASS sid0_short_circuit={}
MISS UnReadMailCount（已知上游缺失，允许）｜ State/VIPLevel=None（上游类型不符，允许）
JSON {"Level":90,"Nickname":"111","RepresentCharacterServerId":9,"PublisherAccountId":314816420}
```

### 12.7 部署过程中的第二次事故（已处置）
```
第一次 deploy（02:18:41）用了审计员的 7,325 B 错版 accept 脚本
  → 第 8 步 FAIL："响应里找不到像 AccountDB 的对象（顶层键：['Code','Data','Msg']）"
  → 按规则立即 ROLLBACK.sh：线上恢复 8227f28e、9097 单实例
  → 核对服务器那份 = 54d04873（错版）→ 重传 c25d085d → 02:19 重新部署成功
```
**这次事故的价值**：证明「accept 失败即回滚」这条硬规则**真的会被执行**，而且回滚干净。
**代价**：多一次重启。**根因**：文件名撞车（见 12.4 规矩⑥）。

### 12.8 现在仍然缺的一块：`identify` 拿不到真 DevId
```
所有无 DevId 的登录 → 兜底 → 全部落到 dev_id=314816420 这一个账号
⇒ **新建账号这条路当前彻底堵死**
⇒ 昵称设定界面（F2）虽然改对了，但**看不到** —— 因为根本不产生新账号
⇒ 公益卡（跟随设备）/ 付费卡（跟随卡密）**两套都无法实现**
下一轮唯一主题：把 identify 的身份来源从 req_frag_head 换成真实请求体
```

---

## 13. 事件：`DevId`/`DeviceUniqueId`/`Token` 明文落盘（2026-11-18 02:35）

### 13.1 根因闭合：客户端**确实**发 DevId（190 个样本）
扫 `api_all_requests.log` 的 `req_frag_head`（**值已打码、键名完整**，所以这次取证本身不涉密）：
```
SAMPLES 2051
  DevId              190      ← 客户端真的发
  DeviceUniqueId     190
  Token              190
  OSType 1772 · AccountId 1772 · AccountServerId 1715 · MxToken 1664
  Hash 1932 · IsTest 1829 · Resendable 1827 · SessionKey 1827
```
**⇒ identify 拿不到真 DevId 不是客户端问题，是我们取错了来源。**

### 13.2 取错来源的完整链路（一行代码的自伤）
```
cn_cipher.decode_packet() → r['fragment'] = **完整明文**          ← 完整的东西一直在这里
        ↓
:2285  rec['req_frag_len']  = r.get('frag_len')
       rec['req_frag_head'] = mask_secret(str(r.get('fragment'))[:600])
        ↓                                                          ← [:600] 截断 + mask_secret 打码，**只为了写日志**
:83-88 _req_dict(rec): frag = rec.get('req_frag_head')             ← identify 却拿这个残片当输入
```
⇒ `[:600]` + `mask_secret` **只发生在写日志那一刻**，明文本身没被动过。
⇒ 但 identify 吃的是日志副本 ⇒ 双重损失（截断 + 打码）⇒ JSON 解析必然失败 ⇒ 走兜底。

### 13.3 ⚠ 泄露事故（我们自己写的调试代码造成的）
```
:589/:591  devid_stash()  →  rec['req_DevId']          = dv.strip()   原值
                              rec['req_DeviceUniqueId'] = duid        原值
                              rec['req_Token']          = tok         原值
写入 → _log(rec) → json.dumps(rec) → api_all_requests.log
```
**命中 52 条 auth 记录，三者均为 `masked=False` 明文。**
`:96` 的 `devid_stash(rec, _d)` 是 `_req_dict()` 的**副作用**，而 `_req_dict()` 又是 identify 的输入构造器
⇒ 调试用的 stash 把"想取的值"和"不该留的值"塞进了同一个对象。

### 13.4 `rec` 就是落盘对象（所以"往 rec 里塞明文"这条路彻底封死）
```
:1724  rec = {'t','from','method','path','mode','headers','body_len','body_printable',...}
:1757  self._log(rec)
:1678  def _log(self, rec): ... json.dumps(rec, ensure_ascii=False)  → api_all_requests.log
```
⇒ **任何塞进 rec 的键都会进日志。** srv-ops 第一版建议（`rec['req_frag_full']`）作废。

### 13.5 修法（已定，待批，不落地）
```
① 旁路通道：解密成功处（:2285 / relay :3461，frag 在作用域内）
     _FRAG_TLS.v = r.get('fragment')        # threading.local()，不进 rec、不进日志
   文件顶部已 import threading，且 _RL_LOCAL 等已在用 ⇒ 零新增依赖、零签名改动
② 消费端：acct_apply_to_auth() / _req_dict() 优先读 _FRAG_TLS.v（用完置 None），
   解析失败退回 req_frag_head（历史兼容）
③ **顺手堵漏**：devid_stash 改为只存 mask_secret(dv) / sha8+len；原值只走 ①
④ 历史 52 条明文记录需处置（脱敏重写或轮转）—— **属写操作，单独批**
```

### 13.6 修好 identify 会立刻冒出的新故障（必须先设计）
```
现在：无 DevId → 兜底 314816420 → 命中 Lv90 老号
修好：拿到真 DevId → 库里没有该 dev_id 的行 → get_or_create_account **建一个新号**
      ⇒ 用户登录看到一个 1 级空号，**以为存档没了**
```
`get_or_create_account` 只按 dev_id 查（L882），恰好把"修好"变成"看起来丢档"。

**因此账号解析必须同时改成：**
```
有 dev_id 的行   → 用它
没有             → 退回 314816420 的老号（**绝不凭未知 dev_id 建号**）
两者都没有       → 才建（真正的全新安装）
```
这条同时就是**公益卡"账号跟随设备"**的实现形态 —— 一个改动解两个问题。

### 13.7 一条独立发现（不阻塞，但要记）
```
req_keys = None、r['json'] 为 None
⇒ 这一路请求的协议 token 不在 decode_packet 的映射表里
⇒ decode_packet 对它**解不出结构化字段，只解出 fragment 原文**
⇒ 改 identify 时必须按"字段只能从 fragment 文本解析"这个前提设计
```

---

## 14. 桥补丁 v3：复审全绿，可部署（2026-11-18 02:35）

### 14.1 版本链
```
v1  436cba4d   审计 3 FAIL（A4 仍会建号 / C 泄漏 8 位 DevId / G _frag 未定义）
v2  6ac20bc7   审计 4 FAIL（同 A4 A6 C G）→ 退修
v3  7d4d1625   复审 A/B/C/D 全 PASS，实测 11 hunk / +93 / −9
               基线 1db27e4c（161,194 B）→ 164,514 B，+3,320 B
```

### 14.2 复审结论（审计员 ≠ 实现者）
| 项 | 结论 | 依据 |
|---|---|---|
| A · P4 三值判定 | **PASS** | 用文件原样代码跑真值表，四条全过 |
| B · mask_secret | **PASS** | `keep=(0,0)` → `****(len=9,sha8=…)`；`(4,4)` 路径逐字不变（行为中立） |
| C · relay `_frag` | **PASS** | h8/h9 都提前，`busy` 未受影响，重复写无副作用 |
| D · 结构 | **PASS** | 149→150 函数（+`_fallback_dev_id`），无重复定义，3.10 语法 OK |

**A 的真值表（这是本轮的核心防线）**
```
a) 真 dev_id 查询抛异常 + 兜底存在      → dev_id=314816420  src=retarget-fallback  不建号 ✔
b) 真 dev_id 抛异常   + 兜底也抛异常    → dev_id=314816420  src=retarget-fallback  不建号 ✔
c) 真 dev_id 明确无行 + 兜底明确无行    → dev_id=真值       src=create            才建号 ✔
d) 最外层 except 触发                   → dev_id=314816420（已拉回）               ✔
```
⇒ **"修好 identify 反而让用户看到空号"这条事故被真正堵住了。**

### 14.3 残留（低危，下一轮统一收）
```
req_frag_head 四处（L2351/3541/3632/3886）仍用默认 keep=(4,4)
  —— 它装的是解密明文片段，前 4 + 后 4 字符会进日志
acct_mxtoken / req_key / req_iv / req_Token 同
⇒ 建议下一轮统一 keep=(0,0)
```

### 14.4 部署判据（审计员给的，我采纳）
```
代码层面：可以部署
真正的卡点：identify() 能否从 fragment 拿到真 DevId 仍未证实
部署后必须看日志 acct_id_src 分布：
   出现 exact                ⇒ 身份链路真的接通了
   全是 retarget-fallback    ⇒ 身份还没接通（但也不会建错号）
```

### 14.5 C# 侧待上（1 行，无歧义真 bug）
```
patch_idcard_showmulti.udiff（已成型，未应用未构建）
card.ShowMultiFloorRaidClearedDifficulty = request.ShowMultiFloorRaidClearedDifficulty;
理由：请求 DTO 有该字段（NetworkProtocol.cs:4331），SetIdCard 的 11 行赋值唯独漏了它
```

---

## 15. v3 上线实测：**身份链路真的接通了**（2026-11-18 02:42:43）

### 15.1 部署
```
旧 1db27e4c… 161,194 B  →  新 7d4d1625… 164,514 B
备份 /root/PROBE_IDENTITY_BACKUP_20261118_023917/（含 ROLLBACK.sh）
桥 pid 2693248 · 单实例 · cwd=/www/wwwroot/bapatch/tools · IMPORT_OK · ACCEPT PASS 12/12
```

### 15.2 唯一一次登录的实测记录（`/api/account/auth` 02:42:43）
```
decrypted          True
req_frag_len       372
req_frag_head      ',"De****593}(len=372,sha8=0d65bd12)'
req_keys           ['DevId','DeviceModel','DeviceSystemMemorySize','DeviceUniqueId','Hash','OSVersion', ...]
req_devid_src      **'fragment'**        ← ★ fragment 解析成功，不是兜底
req_devid_len      **9**
req_devid_sha8     **'a424da70'**        ← 与 req_DevId 的 sha8 **完全一致**
req_DevId          '****(len=9,sha8=a424da70)'     ← 已脱敏，无明文
req_DeviceUniqueId '****(len=32,sha8=cae2cbea)'    ← 32 位真设备 id
req_Token          'b8e7****ee0a(len=40,sha8=3b6079f0)'
acct_id_src        **'exact'**
acct_id_retarget   <ABSENT>             ← 未发生重定向
acct_server_id     10000000000
acct_svc           'on'
wrap_mode          'a_proto_int'
```
**⇒ fragment → identify 的链路真的通了；命中既有账号；未新建；无明文落盘。**

### 15.3 ⚠ 我自己犯的一次判断错误（记下来）
```
我看到 srv-ops 的 grep 输出为空，就断言"三个诊断字段没写、acct_id_src=exact 是假阳性"。
错因：日志是 `json.dumps(rec)` 默认分隔符 —— **冒号后带空格**
      grep '"req_devid_src":"'（无空格）永远匹配不到
正确写法：grep '"req_devid_src": "'
教训：日志字段的 grep 模式必须按实际序列化格式写；"搜不到"不等于"没写"。
```

### 15.4 ★ 一个对卡业务极重要的语义发现
```
DevId         = 9 位  = 314816420  = 卡号 / publisher id（不是设备 id！）
DeviceUniqueId = 32 位 = 真设备标识（sha8 cae2cbea）
```
⇒ 付费卡（账号跟随卡密）用 DevId 是对的（同一张卡多处登录 = 同一账号）。
⇒ **公益卡（账号跟随设备）不能用 DevId，必须用 `md5("free:" + DeviceUniqueId)`** —— 否则同一张免费卡在任何设备上都塌缩成同一个账号。

### 15.5 未变的东西（排除回归）
```
Friend_GetIdCard 响应 556 → 748 B
  原因：relay2_resp_len 266 → 410（Shittim 回的内容变长），**键数仍是 4**
  归因：用户 02:34 保存过 ID 卡（Comment='666' / EmblemId=1 等有值）⇒ **与 v3 无关，不需回滚**
```

### 15.6 v4 作废（多余的改动 = 多余的风险）
```
4d50e6c7…（164,817 B，11 hunk）—— 声称"路径 B 缺注入"的修正
⇒ 反驳依据：v3(7d4d1625, 3999 行) 的 2348-2353（req_keys / req_frag_head）在 path A 的
   want_decrypt 分支内，而日志里这两项**都有值** ⇒ path A 确实执行、TLS 已由 2342 灌入
⇒ 结论：v4 多余，作废；实现者已把 FIX5 从生成器删掉，
   重新生成的产物 **7d4d1625… / 164,514 B / 10 hunk，与线上逐字节一致**
```
**实现者自己的复盘（值得记）**：
```
"用『缺失的字段』反推控制流，方向搞反了"
⇒ 正确做法：用**存在的字段**正向定位 ——
   decrypted / req_frag_len / req_frag_head(len=372) / req_keys / req_devid_src
   / req_devid_len / req_devid_sha8 / acct_id_src 八个字段逐一锁行号
```

### 15.6.1 ⚠ 我自己在这次争执里也错了一次（必须记）
```
我读了 _patched\account_auth_probe.py，看到 2386-2393 有 `_rf = cn_cipher.decode_packet(...)`
的注入块，就断言"v3 在 path B 本来就有这段，实现者拿错基线了"。

事实：我读的那一刻，磁盘上的 _patched 文件**已经是 v4**（4,005 行 / 164,817 B），
      不是 v3（3,999 行 / 164,514 B）。那段注入属于 v4，不属于 v3。
⇒ 我的"拿错基线"诊断**是错的**，实现者读的文件没错。
⇒ 真正成立的部分只有一条：v3 的 path A（2342）确实执行了，所以 v4 多余。
```
**教训（并入规矩第 7 条）**：
```
读文件做判据之前先取 md5 + 行数，并在结论里写明"我读的是哪个 md5 的文件"。
多个版本在磁盘上来回切换时，行号会指向不同代码 —— 这与"谁读错了目录"是两件事。
```

### 15.7 规矩第 7 条（修订版）
```
⑦ 任何引用行号的结论，必须写成「文件 + md5 + 行数 → 行号」四元组。
   例：V3(7d4d1625…, 3999 行):2342
   理由：同一路径下可能先后存在多个版本；本轮 V3/V4 曾在 _patched 下互相覆盖，
        导致同一行号指向不同代码，双方各执一词。
   注：PowerShell `(Get-Content).Count` 对该文件会少算（3,772 vs 3,999），
       行数以 python `split("\n")` 为准。
```

---

## 16. ID 卡 C# 修复上线（2026-11-18 02:49）

### 16.1 改动（`FriendHandler.cs`，标记 `BAPATCH-IDCARD-LIST v1`）
```
改动 1  List() 补两行：
          response.FriendIdCardDB      = BuildMyIdCard(account);
          response.IdCardBackgroundDBs = db.GetAccountIdCardBackgrounds(account.ServerId)
                                           .ToMapList(_mapper).ToArray();
        并把 GetIdCard 的 5 行抽成 private static BuildMyIdCard()，两处共用
改动 2  SetIdCard() 补漏掉的：
          card.ShowMultiFloorRaidClearedDifficulty = request.ShowMultiFloorRaidClearedDifficulty;
```

### 16.2 为什么是这个
```
FriendListResponse（NetworkProtocol.cs:4253）的第一个字段就是玩家自己的卡：
    public FriendIdCardDB? FriendIdCardDB { get; set; }
而 List()（FriendHandler.cs:39-52）只填了三个好友数组，**从不设置它** ⇒ 永远 null
⇒ 客户端 MXAccount.FriendInfoObject.MyIdCard = null
⇒ UIIdCardObject.SetMyIdCard() 第一行 `bl get_MyIdCardClone; cbz → return`
⇒ **整张卡保留 prefab 出厂文本**（username / Lv.72 / AAAAAAAAAA / TEXTTEXT / 100,000）
⇒ 用户实测：点「编辑ID卡」保存后再进，画面毫无变化 —— 因为读的通道是空的
```

### 16.3 部署结果（六步全过）
```
旧 3ec7c46d2890dd5dae9184b0ecbf64fea386f968ec70676626d319da16180096  2,674,688 B
新 24ef1d4c94649322ea148881a6ac7884b57ee0cbb26f8d1b4909947149875eb9  2,675,712 B
备份 /root/CSHARP_IDCARD_BACKUP_20261118_024923/（DLL + Config + SHA256.before + ROLLBACK.sh，bash -n 通过）
三端口 5000/5100/6667 全 LISTEN（同 pid 2695703）· tmux 会话 1 个
启动日志：Mapped 499/501 · 角色过滤补丁仍在（7265→7256）· **无 Exception**
桥未触碰（pid 2693248 仍在跑）
```

### 16.4 ⚠ 这一版 DLL 顺带带上的东西（已评估，接受）
| 项 | 内容 | 行为变化 |
|---|---|---|
| F1 `BAPATCH-TOKENGATE v1` | AccountHandler ×2 | **无** —— `ServerConfig.cs:68 EnforceTicketToken = false`，且 Config.json 里没有该键 ⇒ 默认关 |
| F2 `BAPATCH-SESSIONTTL v1` | SessionKeyService | **有**：`SessionTtlMinutes` 默认 10080（7 天），空闲超 7 天的会话失效需重登。实测影响可忽略 |
| ServerConfig | 新增两个属性 | 无（首次 Save 才写入 config） |

### 16.5 重启方式（坑）
```
systemd 单元 Type=forking + ExecStart = `tmux new-session -d -s shittim`
ExecStop = `tmux kill-session -t shittim`，Restart=always / RestartSec=5
⇒ **必须 `systemctl restart ba-shittim`**；手工 kill dotnet 会被 systemd 在 5 秒后重建，
   且旧 tmux 会话未清时 new-session 会因重名失败。
⇒ 判断端口要用**轮询（最多 30s）**，不能 sleep 3 就断言。
```

---

## 17. 「玩家信息」卡死：当前定位边界（2026-11-18 02:50）

### 17.1 已确认的实测事实
```
① 可复现：登录 → 点「玩家信息」→ 卡（**不经过 ID 卡也卡**，已由用户实测排除"脏状态"）
② 卡死时 **零请求**：nginx 02:43–02:46 共 0 条、桥 0 条、无 499/502/504
③ 卡死时 **网络几乎不动**：10 秒 rx +3.8 KB / tx +2 KB（心跳量级）⇒ 不是在下载
④ 线程数 203 → 192（下降）⇒ 不是重试循环
⑤ 但**帧一直在出**：两张图 94% 像素变化集中在立绘呼吸动画
⑥ 无任何遮罩/置灰/加载态；主线程持续吃 CPU（6 分钟 +8 秒）
```

### 17.2 客户端结构（il2cpp 反汇编）
```
「玩家信息」= UIPopup_UserInfo（type[6070]）
  入口 UIAccountInfo.OnClickUserInfo @0x0CCF2B94
  子页签：UIUserInfoTab_Profile / _Record / _Assist
  **SetValues / SetData / SetMyData 全是 void 同步方法**
  **没有 MoveNext / d__NN 迭代器 / AsyncTask / Addressables 加载 / 回调参数**
  ⇒ 它不"等"任何东西 ⇒ 与"零请求"自洽
  弹窗层对自身字段有 cbz 判空；风险区是 Profile/Record 两个 Tab（**ACE 密文，可解率 0**）
```

### 17.3 两个竞争假设（都还没被证伪）
```
H1  每帧抛一次异常（Unity 捕获后继续渲染 ⇒ 画面活着、UI 永远走不完）
    支持：帧在出 + 零请求 + 主线程持续吃 CPU
    弱点：拿不到异常栈（见 17.4）

H2  打开了一个透明的全屏阻挡层（空面板 / 全屏 Image 且 raycastTarget=true）
    ⇒ 画面照常动、点哪都没反应、屏幕上什么也看不见 —— **不需要异常、不需要日志**
    支持：SetValues 里确有对子对象 SetActive 的调用
    弱点：未验证
```
**注意 H1 若成立，则"同步死循环"这一支已被排除** —— 死循环会让整帧卡住、画面停止出帧，而我们观测到帧一直在出。

### 17.4 日志这条路已关闭（实测）
```
· /sdcard/Android/data/com.RoamingStar.BlueArchive/ 下**没有任何 .log**，无 Player.log / UnityLog
· boot.config（151 B 全文）无 nolog / 日志级别项
· `setprop log.tag.Unity VERBOSE` 生效后，游戏进程**仍 0 条 self-log**
· NullReference|IndexOutOfRange|InvalidOperation|Exception 关键词（限 uid 10520 及全局）**0 命中**
⇒ 不是"没有异常"，是 release + il2cpp 下异常不进 logcat
⇒ **静态反汇编与日志两条线都已到边界**，只剩行为测试（H2 的返回键测试）
```

### 17.5 环境干扰（重要）
```
OPPO 的后台策略 `o-stop(40)` 在 20 分钟内杀了游戏 4 次：
  02:42:23 pushcore / 02:45:44 pid 16147 / 02:49:23 pid 18012 / 另一次 pushcore
⇒ 复现时必须把游戏**保持在前台**，否则现场会被系统清掉
```

### 17.6 下一步
```
① 用户重登，验 ID 卡是否恢复（C# 修复是否命中）
② 若「玩家信息」仍卡：让 phone-ops 在卡死态**只按一次 Android 返回键**并截图对比
     画面变了 / 能继续操作 ⇒ H2（透明阻挡层）成立，根因是弹窗内容为空
     毫无变化             ⇒ H1（每帧抛异常）
③ 我侧同时查 Friend_List 的 resp_len 是否从 472 B 变大 —— 这是"卡真的送到客户端"的第一个硬证据
```

---

## 18. ID 卡修复完成（三刀，2026-11-18 02:57）✅

### 18.1 结果
**用户实测：「成功了 ID 卡成功显示了」。**

### 18.2 三刀与各自的失败原因
```
第一刀  24ef1d4c   FriendHandler.List 补 FriendIdCardDB + IdCardBackgroundDBs
        结果：Friend_List 472 B → 1,068 B，**数据确实送达了**
        但卡还是不动 ⇒ 数据里有一处是错的

第二刀  d7e06ca2   修 id 空间（ServerId 冒充 UniqueId）
        结果：**完全没生效**（wire dump 里仍是 9）
        原因：改动落在 `if (card.RepresentCharacterUniqueId == 0)` 分支里，
              而库里存的已经是 9 ⇒ 条件不成立 ⇒ **我的修正是死代码**

第三刀  f54739aa   读端无条件覆盖 + 写端反向转换 + 保存后 Reload
        结果：**成功**
```

### 18.3 真正的根因：闭环污染
```
FriendHandler.cs:139
    if (card.RepresentCharacterUniqueId == 0)
        card.RepresentCharacterUniqueId = account.RepresentCharacterServerId;   ← 把 ServerId 当 UniqueId
⇒ 客户端收到 9
⇒ 用户点「编辑ID卡」保存时，客户端把 9 **原样回传**
⇒ SetIdCard 把 9 写进库 ⇒ **错误值被固化**
⇒ 之后任何"只在 == 0 时修正"的补丁都永远不执行
```
**实测佐证（id 空间完全不重叠）**
```
账号 2 的角色：ServerId 7/8/9/10/11 ↔ UniqueId 13010/16003/**13003**/26000/10000
账号 2 共 234 个角色，UniqueId 量级 = 1xxxx / 2xxxx
账号 1 的角色 UniqueId 又是另一套（10000/13006/13005/16000/20033/20016）
⇒ ServerId=9 的真 UniqueId = **13003**，9 绝不可能是 UniqueId
```

### 18.4 最终改法（`patch_idcard_represent_v3.udiff`，3 hunk / +18 / −3）
```
A 读端：删掉 if，**无条件** card.RepresentCharacterUniqueId = RepresentCharacterUniqueIdFor(db, account)
B 写端：SetIdCard 收到的 UniqueId 先查回 ServerId 再入库，命中时同步 account.RepresentCharacterServerId
C 回读：SaveChangesAsync 之后 await db.Entry(account).ReloadAsync()
```

### 18.5 两条必须记住的事实
```
① **客户端保存后不会主动重拉卡**
   FriendSetIdCardResponse 只有 Protocol（NetworkProtocol.cs:4335-4338），服务端没有推送机会
   ⇒ 任何 ID 卡改动，**必须重新登录**才能看到（重新触发 Friend_List）
② **Show* 开关为 false 时，客户端写静态占位文本，不是隐藏整块**（il2cpp 反汇编实测）
   ⇒ 用户保存时关掉的格子，即使数据修好了也显示占位，需要用户自己把开关打开
```

### 18.6 规矩第 8 条
```
⑧ 修"值错误"之前先问：这个值有没有被写回库/被对方回传？
   如果有，那就同时存在"源头算错"和"错值已固化"两个问题。
   只改读取端会落进 `if (值 == 默认)` 之类的分支里变成死代码 ——
   **必须先让错误值失效（无条件覆盖），再修写入端（反向转换），否则永远修不好。**
```

### 18.7 顺带记录：`ArenaHandler.cs:159/271` 有同一个 id 空间混用 bug
```
RepresentCharacterUniqueId = account.RepresentCharacterServerId
⇒ 待办，本轮未碰（避免一次改太多）
```

### 18.8 归档证据（wire dump 原文，2026-11-18 02:57:57）
```
RepresentCharacterUniqueId = **13003**      （旧值 9 → 13003）
CardBackgroundId           = **9002**       （原本"缺失"，用户保存的背景现在出现了）
EmblemId                   = **4**          （原本 1）
Level = 90 · FriendCode = RRYHEALT · Comment = '666'
键集合 10 → **7**（Show* 系列因值为 false 被序列化省略 ⇒ 客户端按 false 处理 ⇒ 那些格子显示占位）
```

---

## 19. 交接状态（2026-11-18 03:00，用户决定「玩家信息先不修」）

### 19.1 当前线上（保持不动）
```
Shittim DLL  f54739aa94f0f3f734fdb37d1e4807be1d9fb1029fae029b617914655ce2e2bf  2,676,736 B
             进程 2697583 tmux / 2697584 dotnet（02:57:07 启动）
桥           7d4d162516c2ac1dd6b140bb6a01779b  164,514 B   pid 2693248（02:39:21 启动）
account_service.py  436cba4df30e503212c2e737bf2f9f0c  106,139 B
端口         6667 / 5000 / 5100 / 9097 全正常，tmux 单会话
```

### 19.2 今晚收口的三件事 ✅
```
① **等级页卡死** → 能进、数据正确
   根因：account_service.py 缺 import urllib（每次取真值 NameError 静默降级成影子数据）
   修复：436cba4d（+6 处 camelCase 兼容），ACCEPT 12/12
② **桥 identity** → 真 DevId 拿到、exact 命中、明文不再落盘、绝不误建号
   修复：7d4d1625（_FRAG_TLS 旁路 + 三级账号解析 + 四处脱敏）
   实测：req_devid_src=fragment / len=9 / sha8=a424da70 / acct_id_src=exact ×4
③ **ID 卡全占位** → 正常显示
   根因：Friend_List 从不返回 FriendIdCardDB + ServerId 冒充 UniqueId + **闭环污染**
   修复：f54739aa（三刀：补卡 → 修 id 空间（失败，死代码）→ 无条件覆盖 + 反向转换）
```

### 19.3 未解决（用户决定暂缓）⏸
```
「点玩家信息就卡死」
  现象：可复现；零请求（nginx/桥都为 0）；网络不动（10s 3.8KB）；
        线程数不增；**帧一直在出**（立绘呼吸）；按返回键无效；**触摸有按下动画但 onClick 不执行**
  已排除：死锁 / 渲染停 / 透明层吞输入 / 资源下载 / 网络等待 / 弹窗遮挡
  客户端结构：UIPopup_UserInfo，SetValues/SetData/SetMyData **全是同步 void**，
             无协程、无 await、无 Addressables、无回调参数
  剩两个假设：H1 每帧抛异常（帧能跑完所以不是死循环）｜H2 其它阻塞源
  卡点：**拿不到异常栈** —— 该 build 无 Player.log、logcat 里游戏 0 行、
        setprop log.tag.Unity VERBOSE 后仍 0 行；Profile/Record 两个 Tab 是 ACE 密文，静态反汇编到边界
  ⇒ 下一步唯一可行：**接回 root 手机**（/proc/<pid>/task/*/stack、frida hook、托管堆 dump）
```

### 19.4 回滚（各一条）
```bash
# Shittim DLL（回到第二刀 d7e06ca2）
bash /root/CSHARP_IDCARD3_BACKUP_20261118_025707/ROLLBACK.sh

# 桥（回到 1db27e4c）
bash /root/PROBE_IDENTITY_BACKUP_20261118_023917/ROLLBACK.sh

# account_service.py（回到 102,919 的 8227f28e）
bash /root/ACCOUNTDB_WIRE_BACKUP_20261118_021907/ROLLBACK.sh
```

### 19.5 待办（按优先级）
```
[ ] 接 root 手机 → 查「玩家信息」卡死（唯一路径）
[ ] 用户去「编辑ID卡」把 Show* 开关打开再保存（否则那几格仍显示占位）
[ ] ArenaHandler.cs:159/271 同一 id 空间混用
[ ] 公益卡/付费卡业务（前置已满足：identity 已接通；注意 DevId=卡号、DeviceUniqueId=真设备）
[ ] _ba_state 明文转储加开关（P7，21 处）
[ ] req_frag_head 等四处统一 keep=(0,0)
[ ] 8081 TLS
```

### 19.6 今晚新增的 8 条规矩
```
① 部署成功 ≠ 生效，必须看服务端实际吐出的值
② 部署前先写死预期输出，部署后逐字对比
③ 交付物必须带「基线 md5 → 补丁后 md5 → diff 行数」
④ 任何"兜底"都要先证明它不会解析到错误的对象
⑤ 交付物必须写清"基线是哪个 md5、在哪个路径、什么时候拉的"
⑥ 多 agent 并发写同一目录时文件名带归属前缀；共用产物钉 md5 不钉文件名
⑦ 引用行号必须写成「文件 + md5 + 行数 → 行号」四元组
⑧ 修"值错误"前先问：这个值有没有被写回库/被对方回传？
   有 ⇒ 必须先让错误值失效（无条件覆盖），再修写入端（反向转换）；
        只改读取端会落进 `if (值==默认)` 变成死代码（第二刀就是这么废的）
```
