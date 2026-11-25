# 服务端全面安全审计 · 合并报告

> 2026-11-18 00:53 · 四路只读审计合并
> **全程只读：未改任何代码、任何配置、未重启任何服务**
> 四份原始报告：
> - `AUDIT_SHITTIM_CORE_20261118.md`（Shittim C# 核心）
> - `AUDIT_PROTO_LAYER_20261118.md`（协议/传输层）
> - `AUDIT_PY_SERVICES_20261118.md`（Python 桥 + SDK）
> - `AUDIT_PHP_PANEL_20261118.md`（PHP 卡密站/面板）

---

## 0. 一句话总评

**代码质量不差，缺的是「一层入口校验」。**

四个审计员各自独立地撞在同一件事上：

```
token 从未校验 · 请求体无大小上限 · 解压无上限 · 无速率限制
无重放保护 · 无权限分级 · 日志明文记录凭证
```

这不是 37 个互不相关的 bug，而是**同一层缺失**在四处显形：
客户端信任链只到「知道一个 ID」为止，服务端没有任何环节验证「你是谁」。

PHP 面板相反 —— 代码层（PDO 预处理、CSRF、htmlspecialchars、会话轮换、登录限速）
做得**相当规范**，问题全在**部署与运维面**（明文 HTTP、display_errors、AdminKey 回显）。

---

## 1. 统计

| 来源 | 高危 | 中危 | 低危 | 已做对 |
|---|---|---|---|---|
| A · Shittim C# 核心 | 5 | 7 | 2 | 6 |
| B · 协议/传输层 | 7 | 7 | 3 | 3 |
| C · Python 服务 | 6 | 2 | 1 | 4 |
| D · PHP 面板 | 2 | 6 | 5 | 7 |
| **合计** | **20** | **22** | **11** | **20** |

---

## 2. 按主题合并

### 主题 1 · 身份与凭证（**最核心，跨两份报告重复出现**）

| # | 严重度 | 位置 | 缺什么 | 证实 |
|---|---|---|---|---|
| 1 | 高危 | `AccountHandler.cs:58-63,90-94` | **token 从不校验**：票据只取 `parts[0]` 当 publisherId，token 只被覆盖写入 `NpToken` 从不比对 ⇒ 知道 publisherId 即可登录该账号 | 已证实 |
| 2 | 高危 | `sdkcard.py:44-46` | `User.Token = sha256(card\|dev)[:40]` 签发后**全仓无校验**，纯装饰 | 已证实 |
| 3 | 高危 | `account_service.py:511-528` | 桥的 `identify()` 直接取请求体 `DevId` ⇒ 写上别人的 DevId 即可冒充该号拿 session | 已证实 |
| 4 | 高危 | `sdkcard.py:33-38,332-336` | 设备号取自请求头 `Authorization.Head.DeviceID`，**可任意伪造** ⇒ `bind_one` 形同虚设 | 已证实 |
| 5 | 高危 | `sdkcard.py:322-339` | 卡密**无速率限制、无失败计数** ⇒ 可无限爆破（11 位手机号形态） | 已证实 |
| 6 | 中危 | `SessionKeyService.cs:160-174` | 会话只查存在 + token 一致，**不检查过期** | 已证实 |
| 7 | 中危 | `SessionKeyService.cs:84-87` | `SelectedAccountId>0` 时任何身份都映射到同一账号（越权） | 已证实 |
| 8 | 低危 | `SessionKeyService.cs:109,115` | 会话只绑 `ServerId`，不绑设备/IP | 已证实 |
| 9 | 高危 | 全仓 | **无 nonce / 去重表** ⇒ 同一 packet 原样重放会重复执行（奖励类协议危险） | 推断（强） |
| 10 | 高危 | `GatewayController:262-263` | 会话不绑定连接/IP，可并发多点复用 | 推断（强） |

**合起来意味着**：现在是「知道一个 ID = 拥有那个身份」。补 token 校验是这一组的公共解。

### 主题 2 · 管理接口与权限

| # | 严重度 | 位置 | 缺什么 | 证实 |
|---|---|---|---|---|
| 11 | 高危 | `ManagementController.cs:431-466` | `command` 端点 = **任意 GM 命令 + 任意 Uid**，含读服务器文件的 `accountdata load` | 已证实 |
| 12 | 高危 | `AdminAuthAttribute.cs:20-43` | **无权限分级**：一把 key 或环回 = 全权（改钱/删号/跑命令），没有只读管理员 | 已证实 |
| 13 | 高危 | `AdminAuthAttribute.cs:31-32` | **环回免密钥** ⇒ 同机任意进程（含被挂马的服务）都是超管 | 已证实 |
| 14 | 高危 | `EchelonManager.cs:14-23` | `Echelon_Save` 直接 `mapper.Map` 落库，不校验角色归属/槽位数，可提交他人 `ServerId` | 已证实（无校验） |
| 15 | 中危 | `pages/admins.php:5-6` | 无角色体系，任何管理员可管理其他管理员 = 超管 | 已证实 |
| 16 | 中危 | `pages/settings.php:390` | Shittim `AdminApiKey` **明文回显**在 input value | 已证实 |
| 17 | 中危 | `console.php:147`、`mail.php:308` | GM 命令、全服邮件、批量货币、发道具**全部无二次确认** | 已证实 |
| 18 | 中危 | `settings.php:65-79 → sync.php:417` | `cards_json_path` 无白名单，可覆盖面板自身文件（open_basedir 内） | 已证实 |

### 主题 3 · 输入校验与 DoS（**协议层整片缺失**）

| # | 严重度 | 位置 | 缺什么 | 证实 |
|---|---|---|---|---|
| 19 | 高危 | `account_auth_probe.py:1206-1207` | `Content-Length` 任意大直接 `rfile.read(n)` 进内存，无上限 | 已证实 |
| 20 | 高危 | `cn_cipher.py:54` | `gzip.decompress()` 无输出上限，1 KB → 数 GB 可打爆进程 | 已证实 |
| 21 | 高危 | `GatewayController.cs:457-463` | `GZipStream.CopyTo` 全量展开无上限，且 3 种解包变体各解一次 | 已证实 |
| 22 | 中危 | `GameServer.cs:89` + 全仓 grep 0 命中 | 无 `MaxRequestBodySize` / `RequestSizeLimit` / `RateLimiter`，仅靠 Kestrel 默认 30 MB | 已证实 |
| 23 | 中危 | `AccountHandler.cs:58-63` | 票据解析无 `parts.Length` / `TryParse` 防护，畸形票据 ⇒ 500 | 已证实 |
| 24 | 中危 | `AccountHandler.cs:962-966` | `Account_Reset` 拼表名无 `IsPlainSqlIdentifier`（删号那处有，它漏了） | 已证实 |
| 25 | 中危 | `AccountHandler.cs:271`、`AdminController.cs:86`、`ManagementController.cs:306` | 昵称无长度/字符校验；货币/道具数量无范围校验（可负、可超大） | 已证实 |
| 26 | 中危 | `GatewayController.cs:122-128` | 反序列化无 `MaxDepth`，全工程无请求体大小限制 | 推断 |
| 27 | 中危 | `cn_cipher.py:70-74` | PKCS7 不校验，填充非法时原样返回数据 | 已证实 |
| 28 | 中危 | `cn_cipher.py:82-88` + `GatewayController.cs:370` | **无 MAC/AEAD**；C# 读了 crc 但全文件从不校验 | 已证实 |
| 29 | 中危 | `account_auth_probe.py:1222-1224` | 畸形包 ⇒ 500 + `repr(e)` 异常原文（含路径/解析位置） | 已证实 |
| 30 | 中危 | `account_auth_probe.py:1206 vs 1215` | Content-Length 非数字时异常发生在 try 之外 ⇒ 连接被掐断，连 500 都没有 | 已证实 |
| 31 | 中危 | `account_auth_probe.py:1407` | 未知 token **静默降级**成 `Account_LoginSync` 继续处理 | 已证实 |
| 32 | 中危 | 桥 `:149-162,394` + acct_svc | 14 个文件驱动开关；`cn_billing_block` 注释明写 `1=拦 / 0/缺失=放行(fail-open)` | 已证实 |
| 33 | 低危 | 桥 `:1637/2166/2340` | 未知 `/api/*` 走 `_forward` 原样转 5000 | 已证实 |

**⚠ 设计层面的一条**（不是 bug，但必须知道）：

```
KEY32 明文附在包尾 ⇒ 任何拿到包的人既能解密、也能伪造
服务端完全接受这种"自带钥匙"的包
⇒ 加密只防旁观、不防伪造。客户端就这么发的，但服务端没有为此加任何补偿控制
```

### 主题 4 · 信息泄露

| # | 严重度 | 位置 | 缺什么 | 证实 |
|---|---|---|---|---|
| 34 | 高危 | 桥 `:1211/1213` + 真实日志 | 明文记录完整请求头、body 前 1 KB、`req_key`/`req_iv`/`req_frag_head`（**真实日志里就有 MxToken 明文**） | 已证实 |
| 35 | 高危 | `sdkcard.py:289,326,338` | 卡密明文 + 请求体前 500 B 落 `sdk.log`（实测含 `{"OpenID":"11111111111"}`） | 已证实 |
| 36 | 高危 | live `php.ini:508` | `display_errors=On`，warning/异常会把绝对路径/SQL 打到浏览器 | 已证实 |
| 37 | 高危 | live `<SERVER_IP>.conf:3` | **8081 明文 HTTP、无 TLS**，口令/会话/AdminKey 可被中间人读 | 已证实 |
| 38 | 中危 | `GatewayController:199,275` | Debug 日志打完整请求/响应明文（含 `SessionKey`） | 已证实 |
| 39 | 中危 | `login.php:50-53` | 登录失败回显 PDO 异常原文 | 已证实 |
| 40 | 低危 | `inc/auth.php:243-250` | 会话 token 明文入库 | 已证实 |

### 主题 5 · 数据完整性与可用性

| # | 严重度 | 位置 | 缺什么 | 证实 |
|---|---|---|---|---|
| 41 | 高危 | `sdkcard.py:23-30,336` | `cards.json` **无锁读-改-写 + 非原子 `json.dump`** ⇒ 并发丢 devices；磁盘满/被杀留半截 JSON ⇒ **全部卡密失效** | 已证实 |
| 42 | 中危 | `mail.php:134`、`currency.php:109` | 发奖/改货币只写 `panel_ops`，**不写 `audit_logs`**，审计页看不到 | 已证实 |
| 43 | 低危 | live `logs/sync.log` | 权限 **666 世界可写**，仅靠 nginx `deny /logs/` 兜底 | 已证实 |
| 44 | 低危 | 本地 `install.php` | 线上已删、本地仍在，误传回即重装/接管 | 已证实 |
| 45 | 低危 | `cards.php:15-26`、`cards_export.php:14` | 明文卡密查看/导出走 GET，无 CSRF | 已证实 |
| 46 | 低危 | `inc/auth.php:288-294` | 登录页 CSRF token 存 cookie 而非会话 | 已证实 |

---

## 3. 已做对的部分（20 项，不能只报坏消息）

### Shittim C#
```
固定时间比较 key（AdminAuthAttribute.cs:60-62）
28 个 admin action 类级全覆盖，无 AllowAnonymous
删号 SQL 有表名白名单 + 参数化（ManagementController.cs:196-198,222）
购买数量有上下界（ShopHandler.cs:522-527）
会话 token 用 Guid.NewGuid，不可预测
Newtonsoft 未启用 TypeNameHandling ⇒ 无 $type 反序列化 RCE
```

**重要否决项**：扫了全部 **501 个 `[ProtocolHandler]`**，只有 13 个没调 `GetAuthenticatedUser`，
人工核对**全部是登录前协议** ⇒ **不存在"漏鉴权导致越权读数据"**。

### 协议层
```
ReadExact 有截断校验（GatewayController:450-452）
DecodeGatewayPayload 有最小长度校验（:367-379）
未知协议走 Error 信封而非抛异常（:424）
JSON 未知字段容忍、缺失走 DTO 默认值
```

### Python 服务
```
SQL 全参数化（%s 只拼代码常量列名）
WAL + busy_timeout=5000 + BEGIN IMMEDIATE 显式事务
session 签发用 uuid4 + TTL + revoked + max_active_sessions
文件路径全为常量，无外部输入进路径（无穿越）
```

### PHP 面板
```
全站 PDO 预处理、EMULATE_PREPARES=false，grep 拼接注入 0 命中
所有 POST 统一 require_post_csrf() + hash_equals
统一 e()=htmlspecialchars(ENT_QUOTES)，无裸 echo 超全局
登录即换新随机 token、HttpOnly+SameSite=Strict、过期/禁用即时失效
登录限速 5 次/10 分钟 + 失败固定 0.3s 延迟
Shittim 库只读打开，不直写游戏库
nginx 对 config/inc/cron/sql/state/logs 全 deny + autoindex off
本地 27/27 个文件与线上 sha256 逐字节一致（部署无漂移）
```

---

## 4. 按"修一条能挡住最多"排序的建议（**未执行，待确认**）

> 原则：用户红线是「不要动能用的东西」。以下按 **投入产出比** 排，不是按严重度排。

| 优先级 | 要补的一件事 | 一次能挡住 | 改动面 |
|---|---|---|---|
| **P1** | `Account_Auth` 里**校验 token**（`NpToken` 与票据里的 token 比对） | 上面主题 1 的 1/2/3/4 全部（冒充、伪造 DevId、白嫖 session） | 1 个文件、几行 |
| **P2** | 两处入口加**请求体 + 解压上限** | gzip 炸弹、内存耗尽（主题 3 的 19/20/21） | 2 个文件、常量 |
| **P3** | `AdminAuth` 加**权限分级**（只读/运维/超管），去掉环回免密钥 | GM 命令任意执行、改钱删号（主题 2 的 11/12/13） | 1 个属性类 |
| **P4** | 日志**脱敏**（token / 卡密 / req_key / MxToken / body） | 主题 4 的 34/35/38 | 3 处打印点 |
| **P5** | 关 `display_errors` + 8081 上 TLS | 主题 4 的 36/37（面板口令与 AdminKey 明文过网） | php.ini + 站点证书 |

**为什么不建议现在动**：这五条每条都会碰"正在跑的代码"。当前免 root 登录刚跑通 10 分钟，
资源还在下 10+ GB。**建议等资源下完、你确认客户端稳定之后再逐条改，每条一备份一验证。**

---

## 5. 明确声明

```
四份审计全部只读：未改任何 .cs / .py / .php / .conf / php.ini
未编译、未重启任何服务、未动数据库（只有 SELECT）、未碰手机
未执行任何 curl 对公网页面
```
