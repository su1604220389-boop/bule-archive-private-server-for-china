# BAN_AND_DELETE_STUDY — 封禁为何不生效 + 删除账号能力调研

- 调研时间：2026-11-18（只读，未连服务器、未改任何代码/配置）
- 调研对象：`work\ba\cardadmin_php\`（面板）、`account_auth_probe.py`（桥，9097）、`work\ba\srv_src\`（Shittim 源码与本地构建产物）
- 结论等级：**代码级已证实** = 有 `文件:行号` 可复现；**需服务器侧验证** = 必须跑命令才能定论（这类我明确标注，并给出命令）

## 读的是哪个版本（很重要，封禁结论依赖它）

| 组件 | 我读的文件 | 依据 |
|---|---|---|
| 桥 | `work\ba\server\deploy\_build_multiacct\account_auth_probe.py`（177059 B，2026-11-18 03:51） | 任务书说的 `ensure_session()` 在 **:1921**，只有这个构建对得上 |
| 桥（更新构建） | `work\ba\server\deploy\_build_sidwb\account_auth_probe.py`（180227 B，04:09） | `ensure_session()` 在 :1991，缓存判定逻辑完全相同（缓存返回 :1953，`created` 赋值 :1970） |
| 桥（现网快照） | `work\ba\srv_live\20261118_022226\_patched\account_auth_probe.py`（164514 B，02:45） | `ensure_session()` :1633，`SESSION.created` 赋值 :1658，同样无 TTL |
| Shittim 源码 | `work\ba\srv_src\Shittim-Server\`、`work\ba\srv_src\Schale\` | 源码树 |
| Shittim 产物 | 本地 4 个 DLL（见 §1 表 D 行） | 二进制串扫描 |
| 面板 | `work\ba\cardadmin_php\` | 当前工作副本 |
| 桥账号库 | `work\ba\srv_live\20261118_0059\bapatch\data\accounts.db`（143 KB，现网拷贝） | 我用 `mode=ro` 只读打开，见 §4.3 |

---

## 0. 摘要（先给结论）

1. **封禁失效最可能的 2 个原因**
   - **①（最可能）桥把 `Account_CheckNexon`(1014) 用进程内缓存回复了，根本没打到 Shittim 的守卫。** 缓存命中就直接返回 `session_key`（`account_auth_probe.py:1896-1898`），而 `sess.created` **只写不读**（唯一两处：`:1078` 初始化、`:1914` 赋值），`_SESS_BUCKETS` 从不淘汰（`:1314-1321`），**没有任何 TTL**。1014 由 `ensure_session` 合成回包（`:2667-2672`）。⇒ 只要桥进程不重启，被封账号每次「重新登录」拿到的还是旧 SessionKey，`AccountHandler.cs:104-112` 的 `ACCOUNT_SUSPENDED` 永远不会被执行。面板提示的「下次登录生效」（`pages/players.php:58`）是错的，实际是「下次桥重启生效」。
   - **② 运行中的 DLL 可能不含该守卫（源码有 ≠ 编译进去）。** 本地 4 个构建产物里，两个 `2026-11-17` 的 DLL（Debug 构建、`_shittim_session` 补丁版）**不含** `ACCOUNT_SUSPENDED` 字符串，只有 `2026-11-17 23:04` 的 Release 与 `2026-11-18 02:56` 的 `_build_idcard3` 含。见 §1-D。
2. **会话有没有 TTL**：**桥侧没有**（`created` 死字段，零处读取，全量 grep 只 2 命中）；**Shittim 侧有** `SessionTtlMinutes = 10080`（7 天，`ServerConfig.cs:71`），在 `SessionKeyService.cs:176-182` 生效，但它只按「空闲时长」过期，管不到桥的缓存。⇒ 一个活跃玩家可以无限期绕过封禁。
3. **Admin API 有没有删除端点**：**有，而且是早就有的** —— `POST /api/admin/account/delete`（`ManagementController.cs:203-246`），`DeleteAccountRequest`/`DeleteAccount` 在本地 4 个 DLL 的元数据里**全部存在**。面板从未调用过（`inc/ba.php` 无对应函数、`pages/*.php` 无入口）。⇒ 不需要「新增端点」，需要的是「面板接上 + 桥/MySQL 配套 + 想清楚代价」。
4. **删除账号最小改动面一句话**：Shittim 侧**零改动**（端点已在，动态扫描 `AccountServerId` 级联删 44 张子表 + `Accounts` + `UserAccounts`）；真正要动的是面板（`inc/ba.php` 加一个 `ba_account_delete()`、`pages/players.php` 加一个 action）+ 桥账号库（`DELETE FROM accounts WHERE publisher_account_id=?`，靠 `sessions`/`account_blobs` 的 `ON DELETE CASCADE`）+ MySQL `card_players` 解绑 + **重启桥**（否则内存会话桶还在）。
5. **报告路径**：`work\ba\plan\20261118\BAN_AND_DELETE_STUDY.md`

---

## 1. 封禁失效的全部可能路径（按可疑度排序）

### 1.1 主表

| # | 可疑度 | 路径 | 代码级证据（文件:行号） | 若为真的修法方向 |
|---|---|---|---|---|
| **A** | ★★★★★ | **桥会话缓存绕过**：1014 被桥合成回包，Shittim 的 `ACCOUNT_SUSPENDED` 守卫根本没机会执行 | `account_auth_probe.py:1896-1898`（`if sess.session_key is not None: ... return`，**先于**任何网络调用）<br>`:1914`（`sess.created = int(time.time())` 唯一赋值）<br>无任何读取：全量 `\.created` 只有 `:1078`、`:1914` 两处<br>`:1098`/`:1314-1321`（桶只增不减）<br>`:2667-2672`（1014 由 `ensure_session` 合成）<br>`:2594-2595`（注释自认：1014 只由 ensure_session 内部调用） | ① 给 `Session` 加 `ttl` 判定：`if sess.session_key and (time.time()-sess.created) < SESS_TTL: return ...`，超龄就重打 1014（一行级改动，风险最低）<br>② 或在桥侧加「封禁名单」文件：命中就 500/拒绝，和 `cn_bridge_force_reauth.txt` 同一套路<br>③ 停止合成 1014，改为透传（代价大，见 C 行） |
| **B** | ★★★★☆ | **运行中的 DLL 不含 BAPATCH-BAN**（部署漂移） | 见 §1.2 二进制扫描表：`bin\Debug`（11-17 02:45）与 `_shittim_session\*.patched.dll`（11-17 02:50）**无** `ACCOUNT_SUSPENDED`；`bin\Release`（11-17 23:04）与 `_build_idcard3`（11-18 02:56）**有** | 换 DLL 到含守卫的构建 + 重启；或确认 `_build_idcard3` 就是现网包 |
| **C** | ★★★★☆ | **1014 走「合成」而不是「透传」**，桥是登录链路上的一层认证旁路（A 的另一种表述，但决定修法） | `:2643-2646`（path A：解密真实请求后 `post_gateway(req_json)`，这条路**会**触发守卫）<br>`:2665-2672`（path B：`fallback='synthetic'` 时用缓存合成 1014）<br>`:810-818` `_raw_exp()`/`exp_flag()`：`/www/wwwroot/bapatch/cn_bridge_exp.txt` **不存在或为空 ⇒ exp=''** ⇒ `want_decrypt=False`（`:2613`）⇒ **必走 path B** | 确认 `cn_bridge_exp.txt` 内容。若为空/无 `decrypt+` 前缀，则任何封禁都不生效；要么改走 path A（风险高），要么按 A 行方案在桥侧加 TTL/黑名单 |
| **D** | ★★★☆☆ | **`SelectedAccountId` 重定向**：写的那行 ≠ 查的那行 | `SessionKeyService.cs:84-87`（`if (selectedId > 0) account = 按 ServerId 取选中号，覆盖 publisher 映射`）<br>`AccountHandler.cs:109`（守卫查的是 **票据里的 publisher**）<br>`ServerConfig.cs:48`（默认 0） | 若现网 `SelectedAccountId != 0`：封「实际在玩的那个号」永远不会被检查。修法：把守卫移到 `GenerateSession` 之后，或对「查到的账号」和「将要发的账号」**各查一次 State** |
| **E** | ★★★☆☆ | **已在线会话不受影响 + `Account_Auth`/所有协议都不看 State** | `SessionKeyService.cs:160-191`（`GetAuthenticatedUser` 只校验 token，**完全不读 `State`**，仅 `:187-190` 按 `ServerId` 取行）<br>`AccountHandler.cs:125-175`（`Auth` 无任何 State 判断）<br>`SessionKeyService.cs:92-103`（SESSION-REUSE：同账号复用旧 token，不重铸） | 封禁要「立即生效」必须在 `GetAuthenticatedUser` 里加一行 `if (account.State == Dormant) throw`。这是**唯一能踢掉在线玩家**的位置 |
| **F** | ★★☆☆☆ | **重复行 / 孤行导致守卫查错行**：`PublisherAccountId` 重复或为 NULL | `AccountHandler.cs:65-66,109`（两条都是 `PublisherAccountId == publisherId` 的 `FirstOrDefault`，**无 ORDER BY**）<br>`AccountDB.cs:146`（`long? PublisherAccountId`，可空）<br>`AccountHandler.cs:68-89`（`UserAccounts` 有行但 `Accounts` 没行时**不会补建**） | 服务器查重：`SELECT PublisherAccountId,COUNT(*) FROM Accounts GROUP BY 1 HAVING COUNT(*)>1;` 有重复行就先清理，并给 `PublisherAccountId` 加唯一索引 |
| **G** | ★★☆☆☆ | **面板以为写成功但没落库**（Admin Key / base / 端口错位 / 静默 4xx） | `inc/ba.php:368-382`（`ba_account_update`：只放 `ServerId/State/...`，`:381` POST `/api/admin/account/update`）<br>`inc/ba.php:49-51`（base 默认 `http://127.0.0.1:5000`）<br>`ManagementController.cs:174`（找不到行就 `NotFound`）<br>`pages/players.php:45-52`（失败会累加 `$fails` 并 flash） | 一条命令定论：封完立刻 `sqlite3 -readonly ... "select State from Accounts where ServerId=4"`。若仍是 1 ⇒ 问题在 G，不在 A-E |
| **H** | ★☆☆☆☆ | **桥账号库 `state` 与 Shittim `State` 是两套，桥不读自己那份** | `schema_sqlite.sql:66`（`state INTEGER NOT NULL DEFAULT 1`）<br>桥对 `_svc()` 的调用只有 3 处：`:199`（写昵称）、`:1206`、`:1236`（解析身份）—— **没有一处读 `accounts.state`** | 别把希望寄托在桥库的 `state` 上；它现在是装饰列 |

> 已排除（有证据，不必再查）：
> - **不是「5000 / 5100 两个实例两套库」**：`ServerConfig.cs:11-13` 是同一进程的两个监听口，`run_srv.sh` / `deploy.sh` 只 `cd /www/wwwroot/ba_srv` 起**一个** `dotnet Shittim-Server.dll`；桥固定打 `http://127.0.0.1:5000/api/gateway`（`account_auth_probe.py:257`）。
> - **不是「登录时把 State 覆盖回 Normal」**：全仓 `.State =` 只有两处写点 —— `ManagementController.cs:182`（面板）和 `AccountDataCommand.cs:71`（GM 手动 `!accountdata load` 导入存档时才会覆盖）。CheckNexon / Auth / LoginSync 都不写 `State`。
> - **不是「枚举值不一致」**：`AccountState.cs:8-15` = `WaitingSignIn 0 / Normal 1 / Dormant 2 / Comeback 3 / Newbie 4`，与面板 `inc/players.php:393-402`（`2 => Dormant`）和 `ManagementController.cs:161` 注释完全一致。
> - **不是「State 列没被 EF 映射」**：`SchaleDataContext.cs:117` 只对 `ServerId` 设了 `ValueGeneratedOnAdd`，`State` 是普通列（`AccountDB.cs:147`），无 `HasConversion` / `Ignore`。

### 1.2 D 行（B 行）证据：本地 DLL 二进制扫描

扫描方法：读全部字节，同时按 ASCII（元数据 `#Strings` 堆）与 UTF-16LE（用户字符串 `#US` 堆）匹配。`ACCOUNT_SUSPENDED` 是 `throw new UnauthorizedAccessException("...")` 的字面量，只出现在 UTF-16 堆 —— 所以**用普通 `strings` 是搜不到的**，这是上一个排查者容易踩的坑。

| DLL | 大小 | mtime | `ACCOUNT_SUSPENDED`(utf16) | `DeleteAccount`(ascii) | `SessionTtlMinutes` |
|---|---|---|---|---|---|
| `...\bin\Release\net10.0\Shittim-Server.dll` | 2 674 688 | 2026-11-17 23:04 | **1** | 4 | 3 |
| `work\ba\_build_idcard3\Shittim-Server.dll` | 2 676 736 | 2026-11-18 02:56 | **1** | 4 | 3 |
| `...\bin\Debug\net10.0\Shittim-Server.dll` | 2 958 848 | 2026-11-17 02:45 | **0** | 4 | 3 |
| `...\deploy\_shittim_session\Shittim-Server.patched.01f5b906159d.dll` | 2 669 568 | 2026-11-17 02:50 | **0** | 4 | 3 |

⇒ 结论：**守卫是 11-17 23:04 之后才编译进去的**；`DeleteAccount` 端点则从 11-17 02:45 就有（说明「删除」是上游自带能力，BAPATCH-BAN 是后加的）。

### 1.3 每条路径的验证方法（服务器侧，全部只读）

> 下面命令都在 `/www/wwwroot` 下执行，**不写库、不改配置**。`SHITTIM_DLL` / `SQLITE` 请按实际路径替换（默认按 `run_srv.sh` 的 `cd /www/wwwroot/ba_srv` 推断）。

| 验证哪条 | 命令 | 判定 |
|---|---|---|
| 0. 先确认「面板到底写没写进去」（一条测完整条链） | 面板点封禁 → 立刻执行：<br>`sqlite3 -readonly /www/wwwroot/ba_srv/shittim.sqlite3 "select ServerId,PublisherAccountId,State from Accounts where ServerId=4;"` | 仍是 `1` ⇒ 走 G 行；变成 `2` ⇒ 写库正常，问题在下游（A/B/C/D） |
| A / C：桥有没有真的打 1014 | `grep -c '"session_source": "cache"' /www/wwwroot/bapatch/logs/api_all_requests.log`<br>`grep '"acct_pub": 854071516' /www/wwwroot/bapatch/logs/api_all_requests.log \| tail -3` | `session_source=cache` 占绝对多数 ⇒ **A 成立**（封禁永远不生效）；全是 `fresh` ⇒ A 不成立 |
| A：缓存有没有 TTL（行为验证） | `ls -l /www/wwwroot/bapatch/cn_bridge_force_reauth.txt`（不存在就先 `touch` 一个，**一次性**，桥读完会自己删，见 `:1032-1040`）→ 让该玩家重登 → 看是否被拒 | 建了 force 文件后**才**被拒 ⇒ 100% 是缓存问题（A）。这是最干净的判定实验 |
| B：现网 DLL 有没有守卫 | `strings -e l /www/wwwroot/ba_srv/Shittim-Server.dll \| grep -c ACCOUNT_SUSPENDED`（**必须 `-e l`**）<br>`strings -a /www/wwwroot/ba_srv/Shittim-Server.dll \| grep -c account/delete`<br>`sha256sum /www/wwwroot/ba_srv/Shittim-Server.dll`＋比对构建包 | `0` ⇒ **B 成立**，换 DLL 并重启；`1` ⇒ 守卫在，继续查 A/C/D |
| C：1014 走哪条路 | `cat /www/wwwroot/bapatch/cn_bridge_exp.txt`（不存在 = 空）<br>启动横幅里也有：`grep -m1 'listening on 127.0.0.1:9097' /www/wwwroot/bapatch/*.log /root/*.log`（`:4299` 会打印 `exp=`） | 空 / 不含 `decrypt+` ⇒ 走 path B（合成），封禁必然失效 |
| C：桥开了哪些旁路 | `cat /www/wwwroot/bapatch/cn_multiacct.txt`<br>`cat /www/wwwroot/bapatch/cn_account_svc.txt`（缺文件 = **开**，`:51-54`） | 多账号关 ⇒ 所有玩家共用老号 `314816420`（`:260`），封个体号没意义 |
| D：有没有账号重定向 | `curl -s -H "X-Admin-Key: $KEY" http://127.0.0.1:5000/api/admin/account/selected` | `selectedAccountId != 0` ⇒ **D 成立**，所有登录都被改写成那个号 |
| F：有没有重复行 | `sqlite3 -readonly /www/wwwroot/ba_srv/shittim.sqlite3 "select PublisherAccountId,count(*) c from Accounts group by 1 having c>1;"`<br>`sqlite3 -readonly ... "select ServerId,State from Accounts where PublisherAccountId=854071516;"` | 有重复/多行 ⇒ **F 成立**，面板封的可能不是守卫查的那行 |
| H：桥库 state 是否参与判定 | `grep -n "accounts.state\|acct.state\|\.state ==" /www/wwwroot/bapatch/tools/account_auth_probe.py` | 无命中 ⇒ 桥库 `state` 是死列，别指望它 |
| 收尾：重启桥 | 只改内存态，不需要动库：重启 `account_auth_probe.py`（9097） | 重启后封禁立刻生效 ⇒ 反证 A |

---

## 2. 会话缓存到底有没有 TTL（结论 + 行号）

**结论：桥侧没有 TTL；Shittim 侧有，但管不住桥。**

### 2.1 桥侧：`created` 是死字段

`Session` 只有 3 个字段，`created` 初始化在 `:1078`：

```
1073: class Session(object):
1074:     def __init__(self):
1075:         self.lock = threading.Lock()
1076:         self.session_key = None
1077:         self.account_id = None
1078:         self.created = 0
```

`_ensure_session_locked` 的缓存判定（`:1890-1898`）：

```
1890:     with sess.lock:
1891:         if want_force_reauth():          # ← 唯一能主动失效的开关（文件触发）
1892:             rec['force_reauth'] = True
1893:             sess.session_key = None
1894:             sess.account_id = None
1895:             clear_force()
1896:         if sess.session_key is not None:
1897:             rec['session_source'] = 'cache'
1898:             return sess.session_key, sess.account_id     # ← 直接返回，绝不打 1014
```

`created` 的唯一赋值在 `:1914`（**成功拿到 SessionKey 之后**）：

```
1912:         sess.session_key = obj['SessionKey']
1913:         sess.account_id = obj.get('AccountId') or obj['SessionKey'].get('AccountServerId')
1914:         sess.created = int(time.time())
```

**全量 grep `\.created` 的结果（`_build_multiacct` / `_build_sidwb` / `_patched` 三个版本都查了）：**

| 文件 | 命中 |
|---|---|
| `_build_multiacct/account_auth_probe.py` | `L1078: self.created = 0`、`L1914: sess.created = int(time.time())` —— **仅 2 处，0 处读取** |
| `_build_sidwb/account_auth_probe.py` | `L1078`、`L1970` —— 同样 0 处读取 |
| `_patched/account_auth_probe.py`（现网快照） | `L1075: self.created = 0`、`L1658: SESSION.created = int(time.time())` —— 0 处读取 |

同一文件里唯一的「时间比较」是 `:706` 的 `if (time.time() - ts) > dedup_window():`，那是**订单去重窗口**，与会话无关。

`_SESS_BUCKETS`（`:1098`）只被 `.get` / `[key] =` 操作（`:1314-1321`），**没有任何清理/淘汰/过期分支** ⇒ 桶与进程同寿。

### 2.2 Shittim 侧：有 TTL，但语义是「空闲」

`ServerConfig.cs:69-71`：

```
69:         // Idle session lifetime in minutes. A session untouched for longer is treated as missing. 0 disables the check,
71:         public int SessionTtlMinutes { get; set; } = 10080;      // 7 天
```

生效点 `SessionKeyService.cs:171-183`（`GetAuthenticatedUser`）：`session.LastActivity < UtcNow - ttl` 才过期；每次请求都会刷新 `LastActivity`（`:152`、`:185`）。⇒ **只要玩家还在玩，这个 TTL 永远不会触发**。

另外 `:92-103` 的 `BAPATCH-SESSION-REUSE v1` 保证同一账号重铸时复用旧 token，进一步延长了会话寿命。

### 2.3 因此的实际时序（这才是用户看到的现象）

```
玩家点登录
  → 客户端发 1014 CheckNexon
  → 桥 _bridge(): name == 'Account_CheckNexon' → path B (:2667)
  → ensure_session (:1921) → _ensure_session_locked (:1884)
      → sess.session_key 非空? ──是──→ 返回缓存 (:1896-1898)   ❌ Shittim 完全没被访问
      → 否 → post_gateway(1014) → Shittim AccountHandler.CheckNexon
                                    → :104-112 State==Dormant → throw ACCOUNT_SUSPENDED  ✅
  → 桥把缓存 sk 包成 1014 回包 (:2671-2672) → 客户端认为登录成功
  → 之后的 Auth/LoginSync 全走缓存 sk → SessionKeyService.GetAuthenticatedUser 不看 State ✅ 继续玩
```

⇒ **封禁只在「桥进程生命周期内该 publisher 第一次登录」或「桥重启后」或「`cn_bridge_force_reauth.txt` 被 touch」时生效。** 面板文案「下次登录生效」（`pages/players.php:58`、`pages/player_detail.php:36`）在架构上就是错的。

---

## 3. 面板封禁的完整调用链（含 Admin API 的定位字段）

### 3.1 链

| 步 | 位置 | 行为 |
|---|---|---|
| 1 | `pages/players.php:31` | `if ($action === 'ban' \|\| $action === 'unban')` |
| 2 | `pages/players.php:42-43` | 先 `ba_account_detail($sid)` 记旧 `state`（审计用） |
| 3 | `pages/players.php:44` | `player_set_ban($sid, $ban)` |
| 4 | `inc/players.php:420-427` | `player_set_ban()` → `ba_account_update($serverId, ['State' => $ban ? 2 : 1])`（**状态值 2=封 / 1=解**） |
| 5 | `inc/ba.php:368-382` | `ba_account_update()`：`$body = ['ServerId'=>int]`（:370）+ 白名单字段（:371-380，`State` 走 `(int)` 分支 :376-379）→ `ba_post('/api/admin/account/update', $body)`（:381） |
| 6 | `inc/ba.php:80-159` | `ba_http()`：加 `X-Admin-Key`（:89-91），JSON POST（:103-108），超时 8s（:56） |
| 7 | `ManagementController.cs:167-191` | `[HttpPost("account/update")] UpdateAccount` |
| 8 | `ManagementController.cs:173` | **定位字段 = `ServerId`**：`db.Accounts.FirstOrDefaultAsync(x => x.ServerId == request.ServerId)` |
| 9 | `ManagementController.cs:182` | `a.State = (AccountState)request.State.Value;` 然后 `SaveChangesAsync()`（:184） |
| 10 | SQLite | `sqlite3 shittim.sqlite3`，`Accounts` 表 `State` 列（`SchaleDataContext.cs:117` 只对 `ServerId` 特判，`State` 普通映射） |
| 11 | 登录侧读取 | `AccountHandler.cs:62` 从 `EnterTicket` base64 里切出 `publisherId`；`:109` `db.Accounts.FirstOrDefaultAsync(a => a.PublisherAccountId == publisherId)`；`:110-111` `State == Dormant` ⇒ `throw ACCOUNT_SUSPENDED` |

### 3.2 关于「ServerId ↔ PublisherAccountId 不一致」这个前提

任务书的假设是：**面板按 `ServerId` 写、Shittim 按 `PublisherAccountId` 查，所以可能不是同一行**。

**代码结论：这个推理不成立（至少在正常路径下）。** 理由：

1. `ServerId` 与 `PublisherAccountId` 是**同一行的两列**（`AccountDB.cs:140-147`），不是两套 id。写 `ServerId=4` 的 `State`，读 `PublisherAccountId=854071516` 的那行，只要 `ServerId=4` 这一行的 `PublisherAccountId` 真的是 `854071516`，就是同一行、同一个 `State`。
2. 面板的 `$sid` **确实来自 Shittim**：`inc/players.php:280` `$sid = (int)$a['serverId']`，`$a` 来自 `/api/admin/accounts`（`:234`），该端点返回 `a.ServerId`（`AdminController.cs:120`）。所以面板手上的 `sid` 就是 Shittim 的 `ServerId`，不存在「面板拿桥的 id 去写 Shittim」。
3. 桥侧 `accounts.db` 的 `server_id` 是**另一个号段**（`10000000000+`，见 §4.3 实测），面板只在 `bridge_id` 字段里展示它（`inc/players.php:307`），**从不拿它去做写操作**。

**但「不是同一行」仍然有 3 条真实通道**，这才是要查的：

| 通道 | 机制 | 证据 |
|---|---|---|
| 通道 1：**重定向** | 守卫查票据里的 publisher（`AccountHandler.cs:109`），`GenerateSession` 却可能换成 `SelectedAccountId` 那一行（`SessionKeyService.cs:84-87`）⇒ 玩家实际在玩 A 行，封的是 B 行（或反之） | `ServerConfig.cs:48`、`SessionKeyService.cs:84-87` |
| 通道 2：**重复行** | 同一 `PublisherAccountId` 有多行时，`FirstOrDefault` 无 `ORDER BY`（`AccountHandler.cs:109`）取哪行不确定；面板列出所有行，管理员封的可能不是被取中的那行 | `AccountHandler.cs:65,109`、`AccountDB.cs:146`（可空） |
| 通道 3：**身份解析失败退化** | `acct_pub_for()` 解析不到 publisher 时返回 `None`（`:1251-1291`），`ensure_session` 退化成基线：用**老号** `ENTER_TICKET`（`:1937-1939`、`:260-262` UID=`314816420`）⇒ 这个玩家的请求全部记到公共号上，封他自己的号毫无作用 | `:1937-1939`、`:1282-1291`、`:1148-1154` |

---

## 4. 删除账号：现有能力 / 最小改动面 / 数据影响 / 软删 vs 硬删

### 4.1 ManagementController 端点全清单（`work\ba\srv_src\Shittim-Server\Controllers\ManagementController.cs`）

路由前缀 `[Route("api/admin")]`（:25），整形 `[AdminAuth]`（:26）。

| 行 | 方法 | 路由 | 作用 |
|---|---|---|---|
| 51 | GET | `status` | 服务状态/版本/账号数/uptime |
| 75 | GET | `account/{serverId}/detail` | 账号详情（含 `State` 字符串、货币、计数） |
| 114 | POST | `account/create` | 新建账号（合成 publisherId + 初始化全套数据） |
| 167 | POST | `account/update` | 改昵称/呼号/备注/等级/经验/VIP/**State** |
| **203** | **POST** | **`account/delete`** | **删除账号（级联删子表 + Accounts + UserAccounts）** |
| 248 | GET | `account/selected` | 读「登录落到哪个号」 |
| 257 | POST | `account/select` | 设「登录落到哪个号」（下一次 1014 生效） |
| 272 | GET | `account/{serverId}/items` | 道具列表 |
| 298 | POST | `items/give` | 发道具（可 SetExact） |
| 335 | POST | `items/remove` | 删道具 |
| 352 | GET | `account/{serverId}/characters` | 角色列表 |
| 375 | GET | `account/{serverId}/mails` | 邮件列表 |
| 408 | POST | `mail/delete` | 删邮件/清空 |
| 436 | POST | `command` | 执行 GM 命令 |
| 479 | GET | `static/items` | 静态道具表 |
| 505 | GET | `static/characters` | 静态角色表 |
| 532 | GET | `static/equipment` | 静态装备表 |
| 557 | GET | `static/currencies` | 货币 id→名 |
| 566 | GET | `meta/parceltypes` | 包裹类型 |
| 584/620 | GET/POST | `gacha/config` | 卡池配置读/写 |
| 645 | GET | `gacha/banners` | 卡池 banner |
| 669 | GET | `events/seasons` | 活动赛季 |
| 732/753 | GET/POST | `notice` | 公告读/写 |
| 770/846 | GET/POST | `events/schedule` | 活动排期读/写 |
| 860 | GET | `events/{eventContentId}/unlocks` | 活动解锁状态 |
| 934 | POST | `events/unlock` | 解锁活动 |

另有 `AdminController.cs`（老端点，面板实际在用）：`POST mail/send`（:31）、`POST currency/set`（:62）、`GET accounts`（:102）、`GET account/{serverId}/currencies`（:144）。

**⇒ 明确回答：有删除账号的端点，`POST /api/admin/account/delete`，body `{"ServerId":N}`（`DeleteAccountRequest`，:201）。** 而且它编译进了本地全部 4 个 DLL（`DeleteAccount` 元数据命中 4 次）。

面板侧目前**完全没有**删除能力：`inc/ba.php` 的函数止于 `ba_account_create`（:410-416），无 `ba_account_delete`；`pages/players.php` 的 POST 分支只有 `ban/unban/bind_card/unbind_card`（:31/:63/:77）；`pages/player_detail.php` 只有 `ban/unban/cur_set`（:28/:41）。全仓 grep `account/delete|delete_account|删除账` 无命中（仅 `admins.php:200`、`cards.php:528` 是删管理员/删卡密）。

### 4.2 最小改动面（结论：Shittim 侧零改动）

现有 `DeleteAccount` 的实现（`:203-246`）值得先看清楚，它设计得比预期好：

```
209-210  先确认 Accounts 有行，否则 404
213-218  从 sqlite_master + pragma_table_info 动态找出「所有带 AccountServerId 列的表」
220-227  逐表 DELETE FROM "t" WHERE AccountServerId = {0}
229-230  DELETE FROM "Accounts" WHERE ServerId = {0}
231-232  DELETE FROM "UserAccounts" WHERE Uid = {0}
234-238  若删的正是 SelectedAccountId，置 0 并 Config.Save()
```

- **不需要新增端点。** 要做的只是面板接上（1 个 PHP 函数 + 1 个 action + 1 个确认框）。
- **子表覆盖度**：`SchaleDataContext.cs:126-177` 声明了 44 个 `HasMany(... AccountServerId ...)` 关系；动态扫描按「列名存在」而不是按 EF 关系，所以即使某张表没进关系列表（如 `AccountTutorial`、`SkipHistory*`）也会被删。我另外核了 GameModel 里的键列命名：`AccountServerId` 出现 64 次，另有 5 处 `AccountId`（`CafeDB.cs:20`、`AccountAttachmentDB.cs:18`、`TimeAttackDungeonRoomDB.cs:19` 等）**全是 `get => AccountServerId` 的别名属性**，不是独立列 ⇒ 不会漏表。
- **三处真实缺口**（这才是「最小改动面」）：

| 缺口 | 证据 | 后果 | 最小修法 |
|---|---|---|---|
| ① `UserAccounts` 按 `Uid` 删，而 `Uid` 可能没回填/不等于 `ServerId` | `:231-232`；`UserAccounts.cs:7-13`（PK 是 `Id`，`Uid` 是普通列，**没有外键**）；回填点在 `AccountHandler.cs:86`、`ManagementController.cs:138` | 残留 `UserAccounts` 行 ⇒ 该 publisher 下次登录走 `else` 分支（`AccountHandler.cs:90-102`）**不会补建 Accounts**，`loginAccount==null` 跳过守卫，`GenerateSession` 返回 `null`（`SessionKeyService.cs:89-90`）⇒ **该玩家永久登录失败**，只能手工清库 | 改成 `DELETE FROM UserAccounts WHERE Uid=@sid OR NpSN=(SELECT PublisherAccountId FROM Accounts WHERE ServerId=@sid)`（先取 publisher 再删） |
| ② 不撤销内存会话 | `SessionKeyService.cs:193-197` 有 `RevokeSession` 但 `DeleteAccount` 没调 | 客户端旧 token 仍在 `_activeSessions`（且被 `sessions.json` 持久化，`:32-33,60-75`），下一次请求在 `:187-190` 抛 `User not found`（客户端显示笼统错误），直到进程重启 | 删完调一次 `RevokeSession(serverId)` |
| ③ 完全不碰桥与 MySQL | 见 §4.3 / §4.4 | 桥的 `accounts` 行还在 ⇒ `acct_pub_for` 仍能解析出 publisher；MySQL `card_players` 仍指向已删除的 `server_id` | 面板/运维脚本补两步（见下） |

### 4.3 桥侧 `accounts.db` 要同步删什么（用现网拷贝实测）

数据来自 `work\ba\srv_live\20261118_0059\bapatch\data\accounts.db`（只读打开）：

```
TABLES: account_blobs, accounts, id_alloc, protocol_log, schema_meta, sessions
accounts        rows=3     server_id 10000000000..10000000002
account_blobs   rows=63    PK (server_id, kind)
sessions        rows=118   PK mx_token, FK server_id -> accounts.server_id ON DELETE CASCADE
protocol_log    rows=0
```

`accounts` 表结构（`schema_sqlite.sql:58-96`，与实测列完全一致）：

| 列 | 说明 |
|---|---|
| `server_id` INTEGER **PK** | 账号主键，`CHECK (server_id >= 10000000000)`（:87）⇒ **号段与 Shittim 的 `ServerId` 完全不同** |
| `publisher_account_id` INTEGER NOT NULL DEFAULT 0 | **唯一能对上 Shittim `Accounts.PublisherAccountId` 的列**（有索引 `idx_accounts_publisher_account_id`，:94） |
| `dev_id` TEXT NOT NULL | 主身份键，**唯一索引** `uk_accounts_dev_id`（:92） |
| `device_unique_id` / `sdk_token` | 辅助 |
| `state` INTEGER DEFAULT 1 | **桥不读它**（见 §1 H 行） |
| `nickname/call_name/level/exp/...` | 与 AccountDB 同名字段 |
| `next_entity_id` | 本账号实体 id 发号游标 |

关联表：

| 表 | 主键 | 外键 | 删账号时怎么办 |
|---|---|---|---|
| `sessions` | `mx_token` | `server_id → accounts.server_id ON DELETE CASCADE`（:112） | 级联自动删（**前提：连接上 `PRAGMA foreign_keys=ON`**，见 `schema_sqlite.sql:24-27` 警告：SQLite 默认关） |
| `account_blobs` | `(server_id, kind)` | 同上（:130） | 级联自动删（同前提） |
| `protocol_log` | `id`（rowid） | 无 | 建议保留（审计），或按 `server_id` 删 |

**正确的删除语句（按 publisher 删，不是按 server_id 删）：**

```sql
PRAGMA foreign_keys = ON;                      -- 必须，否则 sessions/account_blobs 变孤儿
BEGIN;
DELETE FROM accounts WHERE publisher_account_id = 854071516;
-- 校验：
SELECT COUNT(*) FROM accounts        WHERE publisher_account_id = 854071516;  -- 期望 0
SELECT COUNT(*) FROM sessions s LEFT JOIN accounts a USING(server_id) WHERE a.server_id IS NULL; -- 期望 0
SELECT COUNT(*) FROM account_blobs b LEFT JOIN accounts a USING(server_id) WHERE a.server_id IS NULL; -- 期望 0
COMMIT;
```

> ⚠️ 桥的 `_SESS_BUCKETS` 是**进程内**的（`:1098`），删库不会清它 ⇒ **删完必须重启桥**，否则内存里那份 `session_key` 还能继续用。

### 4.4 删除账号会连带毁掉什么（运营风险，必读）

| # | 毁掉/破坏的东西 | 证据 | 说明 |
|---|---|---|---|
| 1 | **全部存档**：44 张子表 + 货币 + 角色 + 好感 + 咖啡厅 + 剧情 + 活动进度 + 邮件 + 卡池保底 | `SchaleDataContext.cs:126-177`、`ManagementController.cs:213-227` | 不可逆，无备份就没救 |
| 2 | **卡密绑定变悬空**：MySQL `card_players.server_id` 指向已不存在的号 | `inc/players.php:100-113`（DDL，`UNIQUE KEY uk_card_players_card(card_id)`）、`:189-209`（绑定） | 更麻烦的是 `UNIQUE(card_id)`：**这张卡永远绑不到新号**，除非先 `player_unbind_card()`。玩家付过钱的卡等于废掉 |
| 3 | **删了会「自动重生」**：硬删 ≠ 拒之门外 | `AccountHandler.cs:68-89`（`user == null` ⇒ 新建 `UserAccounts` + `AccountDBServer`，`State` 由 ctor 置 `Normal`，`AccountDB.cs:120-123`） | 玩家下次登录会拿到一个**全新的空号（新 ServerId）**；卡密仍绑在旧号上 ⇒ 「删号」在用户眼里等于「清档重来」，不是「封号」 |
| 4 | **`UserAccounts` 残行导致永久登录失败** | `:231-232` + `AccountHandler.cs:90-102` + `SessionKeyService.cs:89-90` | 见 §4.2 缺口①，这是硬删最容易踩的坑 |
| 5 | **`ServerId` 会不会被复用** | `AccountDB.cs:140-141`（`[Key]`）+ `SchaleDataContext.cs:117`（`ValueGeneratedOnAdd`）+ `SchemaReconciler.cs:7-9`（只管建表/加列，不管删列） | EF Core 对 SQLite 的自增主键通常生成 `INTEGER PRIMARY KEY AUTOINCREMENT` ⇒ **号不复用**（`sqlite_sequence` 兜着）。但这取决于建表时实际的 DDL，**必须验证**：`sqlite3 -readonly /www/wwwroot/ba_srv/shittim.sqlite3 ".schema Accounts"`，看有没有 `AUTOINCREMENT`。**没有 `AUTOINCREMENT` 就会复用 max+1** ⇒ 新玩家接管旧 `ServerId`，`card_players` 里那条旧绑定会「复活」到这个新玩家身上（最坏情况：别人的卡绑到新人） |
| 6 | **内存会话残留** | `SessionKeyService.cs:14,32-33,187-190` | 客户端拿旧 token 一直报错到重启 |
| 7 | **桥侧身份仍可解析** | `account_service.py:1196`（`get_account_by_dev_id`）、桥 `:1206` | 只要桥库那行在，`enter_ticket(pub)` 照样能发出该 publisher 的票 ⇒ 又回到 §4.4-3 的「重生」 |
| 8 | **审计断链** | `pages/players.php:53`（`audit_log`）、`inc/players.php:137-160`（`panel_ops`） | 日志只剩 `server#N` 这个号，账号本体没了 ⇒ 玩家申诉时无法举证、无法恢复 |
| 9 | **若删的是被选中的号**：`SelectedAccountId` 被清 0 | `ManagementController.cs:234-238` | 这个处理是对的，但会让所有登录回落到 publisher 映射 —— 需要提前告知运营 |

### 4.5 软删除 vs 硬删除

| | 软删除（复用现有封禁通道：`State=Dormant` + 列表隐藏 + 解绑卡密） | 硬删除（`POST /api/admin/account/delete` + 桥/MySQL 联动） |
|---|---|---|
| 利 1 | **一行 UPDATE，零级联风险**，不会误删 44 张子表 | 真正的数据消失，符合「彻底注销/合规删除」诉求 |
| 利 2 | **可逆**：存档、卡密、审计链都还在，误封可一键解封 | 释放库体积（该账号全部 blob/子表行） |
| 利 3 | 与现有守卫天然一致：`AccountHandler.cs:104-112` 就是按 `Dormant` 判的，不用改服务端 | 能根治脏数据（重复行/孤行）时才有意义 |
| 弊 1 | 列表会越来越多「墓碑号」，需要「隐藏已封禁」筛选 | 不可逆，且**删完下次登录会自动重生新号**（§4.4-3）—— 体验上等于清档，不是封禁 |
| 弊 2 | 若守卫没生效（本报告 §1 的 A/B/C/D），软删和现在一样**看着封了其实没封** | 必须同时改 3 个存储（Shittim / 桥 sqlite / MySQL），漏一个就出悬空引用 |
| 弊 3 | 卡密仍被占着（`UNIQUE(card_id)`），要额外一步解绑 | `UserAccounts` 按 `Uid` 删不干净时会**永久锁死该 publisher 的登录**（§4.2 缺口①） |

**建议（明确表态）：**

1. **「删除」这个按钮先别做。** 现状已经有封禁通道，而封禁失效的根因是桥缓存 / DLL 构建（§1），**不是缺删除功能**。先按 §1.3 的命令把 A/B/C/D 排掉，让 `Dormant` 真的生效 —— 这比新增删除功能收益高一个数量级。
2. 如果产品一定要「删除玩家」，**实现成软删除**：`State=Dormant` + `Comment` 打标记（或新列 `DeletedAt`）+ 面板默认过滤 + 自动调 `player_unbind_card()` 释放卡密 + 桥侧 `revoke_all_sessions(publisher)`（`account_service.py:779`）。**不要 `DELETE` 行**，因为硬删会被 `AccountHandler.cs:68-89` 的自动建号逻辑变成「清档重生」，且踩 §4.4-3/4 两个坑。
3. 只有在「要彻底抹掉某人的数据（合规/纠纷）」时才走硬删，且必须按这个顺序：**先封禁踢下线 → 备份 shittim.sqlite3 + accounts.db → 调 `/account/delete` → 删桥 `accounts` 行（按 publisher）→ 解绑/作废卡密 → 重启桥 → 验证无孤儿行**。

---

## 5. 我不确定的地方（直说，不编）

1. **现网跑的到底是哪个 DLL 构建**。我只能证明「本地 4 个产物里 2 个没有守卫」，无法证明服务器上 `/www/wwwroot/ba_srv/Shittim-Server.dll` 是哪一份。⇒ 必须 `strings -e l ... | grep -c ACCOUNT_SUSPENDED`（§1.3-B）。
2. **`/www/wwwroot/bapatch/cn_bridge_exp.txt` 的内容**。它决定 1014 走 path A（透传，守卫会触发）还是 path B（合成，守卫被绕过）。工作区里没有这个文件的副本（我 glob 过 `**/cn_bridge_exp*.txt`，无命中）。若为空 ⇒ 我给的「桥缓存是主因」就是**唯一主因**；若含 `decrypt+` ⇒ 主因要改成 B（DLL）或 D（重定向）。
3. **`SelectedAccountId` 现网取值**。默认 0（`ServerConfig.cs:48`），但这是「控制中心」会改的运行时值，存在 `Config` 文件里，工作区没有现网 `Config`（`work\ba\cfg` 只有两个 Localize 文本 + README）。⇒ `GET /api/admin/account/selected`。
4. **`UserAccounts.Uid` 的历史数据是否等于 `ServerId`**。这决定硬删会不会留下「永久登不进」的孤行（§4.4-4）。⇒ `sqlite3 -readonly ... "select Id,Uid,NpSN from UserAccounts;"`，找 `Uid <= 0` 或 `Uid NOT IN (select ServerId from Accounts)` 的行。
5. **`Accounts` 的 DDL 里有没有 `AUTOINCREMENT`**，即 `ServerId` 删后会不会被复用（§4.4-5）。⇒ `.schema Accounts`。
6. **桥账号库与 Shittim 的 id 空间如何在 token 层面打通**。`account_auth_probe.py:3740` 的注释明确写「桥账号服务把 `SessionKey.AccountServerId` 改成 `10000000001`，客户端回传它」，但 Shittim 的 `_activeSessions` 是按 `ServerId`（小号段）建的（`SessionKeyService.cs:111,148,165`），我无法从代码上解释这个映射在哪一层完成；`SessionKeyService.cs` 与 `.bapseb.bak` 的 diff 只显示增加了 SESSION-REUSE 和 SESSIONTTL，没有 id 映射。⇒ 需要日志验证：`grep -o '"rl_session_old_sid": [0-9]*' /www/wwwroot/bapatch/logs/api_all_requests.log | sort -u | head`。这一条不影响封禁结论，但会影响「删除后如何彻底断掉该玩家的会话」的实现细节。
7. **`/api/admin/account/delete` 在现网是否真的可调用**（`AdminAuth` 通过、路由未被前置反代拦掉）。代码和二进制都在，但我没连服务器。⇒ `curl -s -o /dev/null -w '%{http_code}\n' -X POST -H "X-Admin-Key: $KEY" -H 'Content-Type: application/json' -d '{"ServerId":0}' http://127.0.0.1:5000/api/admin/account/delete`，期望 `404 {"error":"Account not found"}`（而不是 401/405）—— 这条只读、无副作用，`ServerId:0` 必然 404。
8. **面板缓存层**：`inc/ba.php:186-222` 有磁盘缓存（`static_*` / `parcel_types`，TTL 1800-3600s），但玩家列表 `ba_accounts()`（`:232-235`）**不走缓存**，所以「面板显示已封禁」是实时真值 —— 如果面板显示 `Dormant` 而游戏照玩，那几乎可以锁定 §1 的 A/B/C/D 之一，而不是面板读到了旧数据。这一点我有信心，但把它列出来是为了说明「面板显示」这个信号的可信度。

---

### 附：本次调研的只读证据来源（可复核）

```
work\ba\cardadmin_php\inc\ba.php                        (368-382, 80-159, 186-222, 49-51)
work\ba\cardadmin_php\inc\players.php                   (100-113, 137-160, 189-209, 230-341, 393-427)
work\ba\cardadmin_php\pages\players.php                 (19-61, 58, 223, 269-274)
work\ba\cardadmin_php\pages\player_detail.php           (28-39)
work\ba\server\deploy\_build_multiacct\account_auth_probe.py  (257-263, 810-818, 1028-1040, 1073-1081, 1098,
                                                         1142-1154, 1251-1324, 1884-1948, 2594-2595,
                                                         2613-2672, 3658-3700, 3740, 4298-4300)
work\ba\server\deploy\_build_sidwb\account_auth_probe.py      (1953, 1970, 1991)
work\ba\srv_live\20261118_022226\_patched\account_auth_probe.py (1633, 1658)
work\ba\server\account_service.py                       (716-740, 754-772, 1153, 1196, 1240)
work\ba\server\schema_sqlite.sql                        (24-27, 58-96, 101-116, 121-131)
work\ba\srv_src\Shittim-Server\Core\NetworkProtocol\Handlers\AccountHandler.cs  (52-124, 125-175, 900-959)
work\ba\srv_src\Shittim-Server\Controllers\ManagementController.cs             (25-26, 152-191, 201-246)
work\ba\srv_src\Shittim-Server\Controllers\AdminController.cs                  (102-142)
work\ba\srv_src\Shittim-Server\Services\SessionKeyService.cs                   (32-33, 77-125, 127-158, 160-191, 193-215)
work\ba\srv_src\Shittim-Server\Configuration\ConfigType\ServerConfig.cs        (11-13, 46, 48, 68-71)
work\ba\srv_src\Shittim-Server\Commands\AccountDataCommand.cs                  (70-74)
work\ba\srv_src\Schale\FlatData\AccountState.cs                                (8-15)
work\ba\srv_src\Schale\Data\GameModel\UserModel\AccountDB.cs                   (120-123, 140-147)
work\ba\srv_src\Schale\Data\Models\UserAccount.cs                              (7-13)
work\ba\srv_src\Schale\Data\SchaleDataContext.cs                               (112-178)
work\ba\srv_src\Schale\Data\SchemaReconciler.cs                                (7-9, 61)
DLL 扫描：bin\Release(11-17 23:04) / _build_idcard3(11-18 02:56) / bin\Debug(11-17 02:45)
          / _shittim_session\*.patched.dll(11-17 02:50)
accounts.db 实测：work\ba\srv_live\20261118_0059\bapatch\data\accounts.db（只读，3 账号 / 118 会话 / 63 blob）
```
