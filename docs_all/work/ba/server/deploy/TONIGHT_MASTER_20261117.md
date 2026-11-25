# BA 私服 · 2026-11-17 夜 主线索引（Lead 汇总）

> 用途：上下文丢失后靠这份恢复。细节在各自 agent 的报告里，这里只留**结论 + 状态 + 谁负责**。

---

## 一、今晚最重要的五条结论

### 1. 手机上是**原厂客户端**，SDK 直连优星
```
libil2cpp.so sha256 = 原厂值（11-16 02:58 商店重装覆盖了改过的包）
游戏 API  *.bluearchive-cn.com  → 我们的服务器（靠 DNS + 系统 CA MITM）
SDK 登录/支付 sdk-api.yostar.cn → **官方优星**（没走我们）
```
⇒ **付费礼包扫码出来是「优星网络」**，因为客户端压根没走我们。
⇒ 卡密那套现在**完全没在工作**（登录用的是真实优星 SDK 账号）。
⇒ 改过 `sdk_url` 的客户端是**另一个构建**，当前没在手机上跑。

### 2. SDK = AiriSDK `com.airi.core` v1.16.1，登录与支付**共用唯一 `sdk_url`**
- 配置：`assets/SDKConfigSettings.json`，顶层只有 `sdk_url`/`channel`/`android`/`ali`
- 支付页 URL 由服务端 `/order/create` 响应下发（`Order{PayState,DeliveryState}` 才是成功判据）
- `/common/config` 里**零个商户号/收银台地址**（只有 6 个 Adjust 埋点 token 名字里带 pay）
- 未改写的官方域名：`udata-api.open.yostar.net`（埋点）、`customer.yostar.net`、`account.yostar.cn`

### 3. 假支付链完整可行（但必须先装改过 SDK 的客户端）
```
① 29000 → 我们回自己造的 PurchaseOrderId
② 客户端调 SDK /order/create → 我们回 Order{PayState=成功, DeliveryState=已发货}
③ SDK paySuccess() → BillingCashShopTask.purchasedCallback → OnPurchaseResponded()
④ 客户端发 29001，body={EndType, PurchaseOrderId}，**EndType.Success=1**
⑤ Shittim 发 ParcelResult / MailDB → 到账（走邮件）
```
- **订单号由我们掌控**（`PurchaseOrderId` 是 29000 响应下发的，客户端原样回显）
- `ProductId` 是客户端从本地 Excel 选的 ⇒ **`/order/create` 不用校验它**，发货用 `ShopCashId`
- 唯一缺：`PayState`/`DeliveryState` 具体取值（拿不到，**用枚举试，不花钱**）

### 4. 两套数据源打架 = 黑屏/货币乱跳的根
```
改前：1002 身份（桥接编造） + 1017 数据（桥接模板编造 122,968B） + 其它（转发 Shittim）
改后：1002 身份（桥接）     + 1017 数据（转发 Shittim 168,130B） + 其它（转发 Shittim）
```
- 开关：`/www/wwwroot/bapatch/cn_1017_relay.txt`（`1`=转发 / `echo 0` 秒回滚）
- 已验证：`relay2_used=True / relay2_protocol=1019 / relay2_err=''`，Shittim 侧 200
- **用户尚未重登验证** ← 今晚唯一的待验证项

### 4.5 重要前提（用户 2026-11-17 20:30 亲口补充）

> 「当时为了方便测试，我手机上的客户端没有改，然后后端是专门为我这个官方的 token 做了一个专门的通过的，就是特例放行」

⇒ 这意味着三件事：
1. **手机客户端完全没改**，SDK 登录用的是用户**真实的官方优星账号**，拿到的是真实官方 token；
2. **后端对这一个 token 做了硬编码特例放行**，所以能进；
3. **"多玩家"到现在为止一次都没被测过**——只有用户一个人在跑，而且走的是旁路。
   `account_service` 的 `fallback to hardcoded` 日志（"没有稳定身份键就拒绝建号"）正是因为这个：真实 token 不是我们签的，没有 DevId 链路。

⇒ **特例放行要保留作为开发旁路，但绝不能进正式环境**。正式环境必须换成卡密签发的 token（HMAC 方案见 `_multiplayer\`）。

### 5. 多玩家：`account_service.py` **本来就是完整多账号服务**
```
server_id 从 10_000_000_000 起、get_or_create_account:513、issue_session_key:677、
resolve_session:707、实体 id 分带、21 个初始 blob
```
⇒ **缺的是接线，不是重写**。3 处缺口：
1. 桥接硬编码 `UID/TOKEN/ENTER_TICKET`（`account_auth_probe.py:164-166`）
2. token → dev_id 没接线
3. `BAPATCH-MU` 只有概念没有实现
⇒ 开关三档：`0` 现状 / `1` 灰度（legacy+签名都收）/ `2` 严格

---

## 二、被撤销的错误结论（别重犯）

| # | 错误说法 | 为什么错 |
|---|---|---|
| 1 | 34 次重复领奖导致重复行 | 精确统计是 29 次 / 29 章节 / 29 行，1:1:1 |
| 2 | 19:31:53 的 TLS 连接是嫌疑现场 | `session_time=73.487` 单位是**秒**，是 keep-alive 存活时长 |
| 3 | 缺 29 个官方 LoginSync 字段 | 35 vs 35，0 结构性差异 |
| 4 | `RepresentCharacterServerId=1100001` 指向不存在角色 | 那是桥接自造 AccountDB 里的值；改库没用，根在桥接身份系统 |
| 5 | 客户端 1017 vs Shittim 1019 编号错位 | 1017 来自桥接桩代码 L1579 写死的数字，token 反查就是 1019 |
| 6 | 必须改名 `BillingPurchaseListByNexonResponse` | 客户端 DTO 本来就叫这个名字，与上游一致 |
| 7 | 支付会随 `sdk_url` 改包指向我们 | `/common/config` 零支付字段，且支付流量不跟 `sdk_url` 走 |
| 8 | `build_noroot_apk.py` 是半接线坏文件 | `--force` 已接好线，工具链实测能跑 |
| 9 | 黑屏是客户端引擎卡死 | 手机是原厂包 + 服务端零错误，方向错 |

---

## 三、任务分派表（agent 独占范围）

| Agent | 独占写入范围 | 任务 |
|---|---|---|
| **srv-ops** | 桥接 `account_auth_probe.py` + Shittim 源码/DLL + `_blackout\srv\` | 1017 验证 / order 探测补丁 / 29001 幂等 / 上游删角色守卫移植 |
| **logcat-architect** | `sdkcard.py`（云端+手机）+ `_card\` | order 三端点 / `pay.json` / `allow_pay` 开关 / Udata 关闭 |
| **ca-researcher** | `build_noroot_apk.py` + `_noroot\apk\` | 重跑构建 / `state1.json` 修 www / 证书续期计划 / 真机测试清单 |
| **phone-ops** | 手机一切操作 + `_noroot\phone\` | 8080 启动方式 / 真机安装 / 黑屏取证 |
| **il2cpp-analyst** | `_sdk\` | 29000→29001 触发链 / PayState 取值 / order 契约 |
| **proto-analyst** | `_blackout\proto\` | 7 个未解析协议 / LoginSync 字段语义 / 大厅背景为空专项 |
| **shittim-analyst** | `_multiplayer\` | token 真校验 / 账号分流 / 卡密表加列 / 面板玩家维度数据方案 |

**红线（谁都不许碰）**：`ba_sni.conf`、任何 nginx 配置、WAF、别人的目录。

---

## 四、待办清单（按优先级）

### P0 · 今晚
- [ ] **用户重登验证 1017**（黑屏是否消失 / 青辉石是否统一 / 登录耗时）

### P1 · 支付安全
- [x] 29000 拦截止血（`cn_billing_block=1`）
- [ ] 用户确认「付费礼包拉不起支付页」
- [ ] `allow_pay` 开关默认 `0`，进分发须知

### P2 · 装改过的客户端（假支付的前提）
- [ ] 重跑 `build_noroot_apk.py`（`--sdk-url https://example.com/sdk --gmconfig-url example.com`，**不给 `--ca`**）
- [ ] 修 `state1.json` 的 `www.` 前缀
- [ ] 8080 SDK 服务要做成**一键启动**（现在纯手动，分发出去没人会起）
- [ ] 真机安装验收

### P3 · 协议与数据
- [ ] 29001 幂等（桥侧 15 分钟去重先上，Shittim 订单表后做）
- [ ] 上游删角色守卫移植（`IsTableComplete<CharacterExcelT>()`）—— **在那之前不要动任何 Excel 表**
- [ ] 7 个未解析 token 定性

### P4 · 多玩家 + 管理面板
- [ ] token 真校验（HMAC-SHA256 `BA2.<payload>.<sig>`）
- [ ] 账号分流接线（3 处）
- [ ] 卡密表加 `kind` / `max_devices` + **改 `sync.php:186-227`**（光改 json 会被每分钟冲掉）
- [ ] 管理面板补 8 项：全部用户列表 / 按类型筛选 / 一键批量发奖 / 封号解封 / 改绑定台数 / 查货币角色 / 发补偿 / 玩家维度综合平台

### P5 · 定时炸弹
- [ ] **证书 2026-12-12 到期（25 天）** —— 建议 11-28 前完成续期

---

## 五、关键路径常量

```
服务器            <SERVER_IP>
桥接              127.0.0.1:9097（pid 变动频繁，看 srv-ops 报告）
Shittim           5000/5100/6667，DB /www/wwwroot/ba_srv/shittim.sqlite3
认证库            /www/wwwroot/bapatch/data/accounts.db
SDK 服务          /www/wwwroot/ba_sdk/sdkcard.py（pm2 ba_sdk）
卡密站            /www/wwwroot/ba_cardadmin（PHP8.2 + MySQL ba_cardadmin）
域名              example.com（证书至 2026-12-12）
开关目录          /www/wwwroot/bapatch/cn_*.txt
```

## 六、环境阶段
**纯测试环境、单人测试**：重启服务可直接做，不必请示。
用户明说「进入正式环境」之后，**任何重启/破坏性操作必须先问**。
