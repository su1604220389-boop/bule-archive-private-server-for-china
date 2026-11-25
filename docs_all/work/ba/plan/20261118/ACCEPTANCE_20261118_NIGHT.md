# 2026-11-18 夜间批次 · 验收清单

> 适用：私服运营方（用户本人）
> 前置：所有改动已部署，备份齐全。任何一步失败都能单独回滚。

---

## 0. 本轮改了什么（一页看懂）

| # | 变更 | 影响面 |
|---|---|---|
| 1 | **卡密 = 独立账号**（SDK+桥+Shittim 三层打通） | 每张卡一个存档 |
| 2 | **公益卡 / 付费卡** 概念落地（`cards.kind`） | 付费卡跟卡、公益卡跟设备 |
| 3 | **封禁管理页**（账号 / 卡密 / 设备 三维独立） | 面板新页面 |
| 4 | **限时封禁**（1h / 1d / 7d / 30d / 自定义，到期自动解封） | 读侧判定，不依赖定时任务 |
| 5 | **登录界面改版**（美化 + 游客/卡密双入口） | APK |
| 6 | **客户端放开卡密输入校验** | APK（原来只收 11 位纯数字） |
| 7 | **封禁文案弹窗**（服务端下发起止时间） | APK |

---

## 1. 装机（第一步，最重要）

```bash
adb install -r "C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\apk_patch\out\BlueArchive_cardlogin_v1.apk"
```

**验收：冷启动能过标题、到登录页。**
这一步过了 ⇒ 改资源没有触发 ACE 保护，后面基本安全。

**失败（闪退 / 卡标题 / 白屏）→ 立刻回滚：**
```bash
adb install -r -d "C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\apk_patch\backup\BA_noroot_prod_20261118_v1.apk"
```

---

## 2. 登录界面

- [ ] 是新样式（圆角输入框、浅灰底、更大的按钮）
- [ ] 输入框上方有「游客登录 / 卡密登录」两个选项
- [ ] 点「游客登录」→ 提示变「请输入公益卡密」
- [ ] 点「卡密登录」→ 提示变「请输入付费卡密」

> 注：这两个选项**不影响发送内容**，服务端靠 `cards.kind` 自己判断。纯 UI。

---

## 3. 卡密长度放开

用运维提供的 **16 位带字母测试卡** 登录。

- [ ] 能输入字母（键盘不是纯数字）
- [ ] 能输满 16 位不被截断
- [ ] 能提交并成功进游戏

> 旧包：`^1\d{10}$` + maxLength 11 + 数字键盘 ⇒ **16 位卡根本输不进去**。
> 新包：`^.{1,64}$` + maxLength 64 + 文本键盘。

---

## 4. 卡密 = 独立账号（回归验证）

- [ ] 用卡A（`11111111111`）登录 → 进原账号（`10000000000`，数据完好）
- [ ] 用卡B（`12222222222`）登录 → 进另一个账号（Shittim `ServerId=4`）
- [ ] 两份存档互不干扰

---

## 5. 封禁（三项独立，互不联动）

面板 → 侧边栏 → **封禁管理**

### 5.1 账号封禁（限时）
- [ ] 时长选「2 分钟」，封禁卡B
- [ ] 用卡B 登录 → 客户端弹窗：「**封号时间 YYYY-MM-DD HH:MM 至 YYYY-MM-DD HH:MM，请联系客服**」
- [ ] 等 2 分钟后再登 → 能进去（自动解封）
- [ ] 面板上该玩家状态回到「正常」

### 5.2 永久封禁
- [ ] 时长选「永久」，封禁某测试号
- [ ] 登录 → 弹窗：「**封禁，请联系客服**」
- [ ] 手动解封 → 能进

### 5.3 卡密封禁
- [ ] 禁用某张卡 → 用该卡登录 → 「卡密不正确」类提示
- [ ] 启用 → 能进

### 5.4 设备封禁
- [ ] 封禁自己手机的设备号 → 重开 APP → 「设备已被限制」
- [ ] **验完立刻解封**，否则自己也进不去

> ⚠️ 三个维度**各自独立**：封账号不会连带禁卡密，反之亦然。

---

## 6. 删除账号（**不可逆，最后做，先在测试号上做**）

- [ ] 展开「删除账号…」→ 必须手输昵称或 ServerId 才能提交
- [ ] 提交后再弹一次确认
- [ ] 确认后：Shittim 侧存档清空、桥侧 `accounts.db` 对应行删除
- [ ] 该卡密**仍然存在**（删号不动卡密）

**删完必须验证一件事**：用同一张卡再登录一次，看是「重建新号」还是「登不进去」。
- 重建新号 = 正常
- 登不进去 = **有问题，立刻回报**（`UserAccounts` 残留会导致永久锁死）

---

## 7. 回滚速查

| 范围 | 命令 |
|---|---|
| APK | `adb install -r -d work\ba\apk_patch\backup\BA_noroot_prod_20261118_v1.apk` |
| 关多账号特性 | `rm /www/wwwroot/bapatch/cn_multiacct.txt` |
| 关会话 TTL | `echo 0 > /www/wwwroot/bapatch/cn_session_ttl.txt` |
| 关限时封禁 | `export BA_BANEXP=0`（重启 SDK 生效） |
| 全部服务端文件 | 各备份目录见 `CARD_IDENTITY_FIX_PLAN.md` §5 |

**备份目录（按时间顺序）**
```
/root/CARDID_DEPLOY_20261118_033943            第一刀（已回滚，留档）
/root/CARDID_DEPLOY2_20261118_035837           多账号 + MySQL dump
/root/CARDID_DEPLOY3_20261118_041441           .user.ini + accounts.db
/root/CARDID_DEPLOY4_SIDWB_20261118_041626     sid 回写
/root/CARDID_DEPLOY5_CARDTYPE_20261118_042717  卡型 UI
/root/CARDID_DEPLOY6_BAN_20261118_044930       设备黑名单 + 会话 TTL
/root/CARDID_DEPLOY7_BANPAGE_20261118_045453   封禁页
/root/CARDID_DEPLOY8_BANEXP_20261118_185150    限时封禁
```

---

## 8. 当前线上指纹

```
桥     account_auth_probe.py  18a3b3b9  191,670 B
       account_service.py     0c057b90  108,730 B   （注：桥目录下）
SDK    sdkcard.py             df13e78f   27,239 B
       ban_message.py         5f344a93    6,378 B
面板   inc/bans.php           e0d94299   73,663 B
       pages/bans.php         9c34e9c1   54,341 B
       inc/helpers.php        2208eced   27,688 B
       inc/sync.php           81042da0   29,150 B
       .user.ini              88 B（open_basedir 含 bapatch）
MySQL  cards 14 列（kind / max_devices / last_used_at）
SQLite accounts.db：accounts 表 + shittim_server_id 列 + bans 表
开关   cn_multiacct.txt = 1 ｜ cn_session_ttl.txt 不存在（默认 120s）
Shittim DLL  f54739aa（未改动）
APK    BlueArchive_cardlogin_v1.apk  d621b329  2,133,476,336 B
```

---

## 10. 冻结状态（2026-11-18 20:1x 起）

用户要求「不要改，我去后台改」⇒ 服务端全部冻结，只读待命。

### 冻结时的现场

```
bans 表          1 行：kind=account target=854071516 until=NULL（永久）reason=真机弹窗验证
cn_banreply.txt  = 1（桥侧封禁包开关，已开）
桥 9097          pid 2748344 / md5 215feddd（含 banreply，能发官方 1025 包）
SDK 8080         pid 2743184 / md5 df13e78f（**SDK 层仍会拦账号** ⇒ 玩家看到「未知错误」）
Shittim          ServerId=4 / publisher 854071516 / State=1
APK              手机上是 v2_layoutonly（可用）；v3 已作废
```

⇒ 卡B 处于**双重封禁**：SDK 拦 + 桥拦。复原：

```bash
sqlite3 /www/wwwroot/bapatch/data/accounts.db "DELETE FROM bans WHERE target='854071516';"
rm -f /www/wwwroot/bapatch/cn_banreply.txt
```

### 已构建但**未部署**的产物

| 产物 | 路径 | 用途 |
|---|---|---|
| 卡密格式改 11 位数字 | `work\ba\server\deploy\_build_cardformat\` | 面板建卡规则 + 输入校验 + 列表红标 |
| SDK 去账号封禁拦截 | `work\ba\server\deploy\_build_sdkaccount\`（构建中） | 让账号封禁只在游戏层拦 |
| v4 登录器 | `work\ba\apk_patch\out\v4_login.apk`（构建中） | 去验证码 + 文案改「输入卡密」+ 美化 |

### 本轮确定下来的两条硬事实

1. **dex 一个字节都不能改**：v2（只换 `res/Q9.xml`）真机可启动；v3（同样布局 + dex 里 6 个字节）**0.5 秒闪退**。
   ⇒ 客户端正则 `^1\d{10}$` 改不了 ⇒ **卡密必须是 1 开头的 11 位数字**。
2. **官方封禁弹窗走 `Protocol.Error` + `ErrorCode=1025` + `BanReason`**，客户端本地文案为
   「账号已被禁止使用，/ 如有任何问题请咨询客服！/ 封禁周期至：<BanReason>」。
   ⇒ 不需要改客户端；但**必须让玩家先过 SDK 层**，否则看到的只是「未知错误」。

### 一份"官方封禁"的完整正确链路（结论）

```
面板封禁（选时长）
  → 写 bans 表（永久：until=NULL；限时：until=epoch）
  → SDK 层【只拦卡密/设备，不拦账号】
  → 玩家过了 SDK，进游戏握手
  → 桥发现账号在封禁中 → 回 {Protocol:-1, ErrorCode:1025, BanReason:"永久" 或 "X 至 Y"}
  → 客户端弹官方提示
  → 到期后桥读侧判定放行（不依赖定时任务）
```


## 9. 已知未验证项（记录于 04:3x，其中第 1、2 条已在 20:0x 由真机证伪/证实，见 §10）

1. **改 `res/*.xml` 后整机跑通** —— 离线无法验证，只能真机冷启动确认（第 1 步）
2. `classes.dex` 从 DEFLATE 变 STORED（+5.5 MB）—— 基线本身已有 STORED 条目且跑通，判断低风险
3. `/user/detail` 是否也该拦封禁 —— 上次测试用的是未绑定卡片的伪造设备号，**结论不成立**，需用真实设备号补测
4. `getChildAt(2)` 在真机布局上的命中 —— 取不到只会静默不显示按钮，不会崩
