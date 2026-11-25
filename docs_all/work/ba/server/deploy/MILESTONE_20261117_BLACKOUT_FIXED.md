# 里程碑：黑屏根治 + 两套数据源合并（2026-11-17 21:00 用户确认"完全正常"）

## 用户确认

> 「完全正常，令人惊喜，我现在开始测试其他功能，这次做的非常好」

四个验证项全部通过：**登录正常 / 青辉石正确 / 大厅背景回来 / 返回不再黑屏 30 秒**。

---

## 最终生效的改动链（今晚从 19:00 到 21:00）

### 1. 1017 转发 —— 两套数据源合并（**根因修复**）
```
改前：1002 身份（桥接编造） + 1017 数据（gen1017 用 spec26 模板编造 122,968 B） + 其它协议（转发 Shittim）
改后：1002 身份（桥接）     + 1017 数据（转发 Shittim 真实库 168,130 B） + 其它协议（转发 Shittim）
```
- 开关：`/www/wwwroot/bapatch/cn_1017_relay.txt = 1`（`echo 0` 秒回滚，无需重启）
- 验证：`relay2_used=True / relay2_protocol=1019 / relay2_err='' / relay2_fallthrough=''`
- LoginSync 首跑需 9,720 ms（Shittim 冷启动，Cafe 查询占 2,103 ms）⇒ `relay2_timeout` 单独放宽到 45 s

**它治好的症状**：
- 青辉石显示 600（模板值）却在领奖后跳到 7000+（Shittim 真值）—— 两套真相源
- 大厅背景为空、记忆大厅消失
- 从任意界面返回大厅卡 30 秒黑屏

### 2. LoginSync 六项缺陷修复（批次 2，Shittim 源码 + 重建）
```
Shittim-Server.dll  59cf008196f19aadca7bd1502c113b3e53e88e3fd21b6201517f62efcc35dc06
Schale.dll          c20095f50e06068a544611ee068bf2fdbdc7f60dd09c81c7ca9da97498a7ddf7
备份                Shittim-Server.dll.pre-batch2.20261117_203256 / Schale.dll.pre-batch2.…
```
1. `MemoryLobbyDB.AccountServerId` 补上（官方每条必带，缺了客户端按账号过滤会得 0）
2. `BillingPurchaseListByNexonResponse` → `BillingPurchaseListByYostarResponse`（**不同词**，客户端按名取）
3. `MomotalkOutlineResponse` → `MomoTalkOutLineResponse`（大小写）
4. 删掉官方没有的 `StaticOpenConditions`
5. M1：移植上游 `ExcelTableService.IsTableComplete<T>()`
6. M2：`AccountHandler.cs:377` 的幽灵角色清理包进守卫

### 3. 桥接批次 1（三合一）
```
account_auth_probe.py  ade3917c… → **8d43dca2ca530e5c20c2fa6c52ead5f1e9c666ed3f5fadf9c8160481ca43d3b1**
备份                   account_auth_probe.py.batch1.bak.20261117_202722
```
- **DevId 接线 3 行**（`rec['req_DevId']` 是死代码，从无写入点）→ `account_service` 真的分流，验证时新建了账号 `10000000002`
- `90011 Shop_ListTutorialGacha` 加进 `RL2_HANDLED`（之前被转发给 Shittim 每调必报错）
- `29001` 订单去重（同单第二次 283 ms → 3 ms，响应逐字节相同）

### 4. 证书更换（用户操作，20:49）
```
example.com   Let's Encrypt YR2   SAN = example.com + example.com
                   notAfter 2027-02-15（90 天）
MITM 证书（*.bluearchive-cn.com）**未动**，仍是 BA Test Root CA，notAfter 2029-02-15
```

---

## 今晚被撤销的错误结论（9 条，留档防重犯）

| # | 错误说法 | 为什么错 |
|---|---|---|
| 1 | 34 次重复领奖导致数据库重复行 | 精确统计 29 次 / 29 章节 / 29 行，1:1:1 |
| 2 | 19:31:53 的 TLS 连接是嫌疑现场 | `session_time=73.487` 单位是**秒**，是 keep-alive 存活时长 |
| 3 | 缺 29 个官方 LoginSync 字段 | 35 vs 35，0 结构性差异 |
| 4 | `RepresentCharacterServerId=1100001` 指向不存在角色 | 那是桥接自造 AccountDB 的值；改库无效，根在身份系统 |
| 5 | 客户端 1017 vs Shittim 1019 编号错位 | 1017 来自桥接桩代码写死的数字，token 反查就是 1019 |
| 6 | 必须改名 `BillingPurchaseListByNexonResponse` | 后来复核：**确实该改**（以官方 HAR 序列化键名为准） |
| 7 | 支付会随 `sdk_url` 改包指向我们 | `/common/config` 零支付字段，支付流量不跟 `sdk_url` 走 |
| 8 | `build_noroot_apk.py` 是半接线坏文件 | `--force` 已接好，工具链实测能跑 |
| 9 | 黑屏是客户端引擎卡死 | 手机是原厂包 + 服务端零错误，方向错 |

---

## 已知未修（用户测试时会遇到，别浪费时间）

| 现象 | 根因 | 状态 |
|---|---|---|
| **付费礼包会真扣钱** | 客户端是原厂包，SDK 直连优星 | 已用 `cn_billing_block=1` 拦 29000；**仍需装改过 SDK 的客户端才能做"假支付"** |
| 免费礼包可无限重复领 | `BillingHandler.cs:215-270` 无幂等检查 | 未改（私服要爽，可保留，但要知道） |
| `Mission_GuideMissionSeasonList` 只回 156 字符（官方 160 KB） | GuideMission 未实现 | 未做 |
| MomoTalk 空 | `MomoTalkOutLines` 0 行 | 未做 |
| 咖啡厅 / 日程 / 制造 / 活动一览 上锁 | 内容解锁门槛（等级/剧情） | 未做 |
| `example.com` 返回 state1 而非 state2 | `.conf:9` 的 `server_name` 被注入 `www.`，`:177` 的块被 ignored | 只影响 www 分档，与游戏无关；修法=宝塔面板删那半截 |
| LoginSync 首跑 5–10 秒 | Shittim 冷启动（Cafe 查询 2.1 s） | 有加速方案，未做 |
| 24 个子响应缺 4 个信封字段 | 官方每个子响应都带 `SessionKey/ServerTimeTicks/ServerNotification/RequestId` | 未做（需确认基类属性可写） |

---

## 性能与稳定性红线（不变）

```
禁止改：ba_sni.conf / WAF / 现有 MITM 证书
允许改但必须：备份 + sha256 + 一行回滚 + 独立开关
宝塔面板操作优先于手改 .conf（宝塔是"定点改写"，只碰 server_name / ssl_certificate*）
每次面板操作后必跑三跳：
  https://example.com/api/state          → 200
  https://example.com/api/gateway        → 200（空 body 会 400，正常）
  https://example.com/sdk/common/config  → 200 / 7,838 B
```

## 备份状态（已落盘，手机可随便折腾）

```
work\ba\backup\BA_backup\        11.104 GB / 31 块 / 6,315 文件（资源，唯一物理副本）
work\ba\backup\account_state\    9.50 MiB / 390 条目（账号态，含 AUTH_APP_INFO + 52 个 .save）
report\_tmp\cn_base.apk          原厂 APK 1.98 GB
_noroot\apk\BA_noroot_v2.apk     sha256 5F8B79DD…（v2，改过 sdk_url）
_noroot\apk\BA_noroot_v2b.apk    sha256 58D2EA89…（v2b，另加改包名，包名 …Archive2）
旧位置 大肥鱼项目\BA_backup  → 已删除，改为指向工作区的目录联接（0 字节，旧路径仍可用）
```
