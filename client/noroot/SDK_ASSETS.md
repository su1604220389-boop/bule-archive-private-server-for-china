# SDK_ASSETS · 「魔改登录 SDK」资产全清点与迁移清单

> 产出：`work\ba\noroot\SDK_ASSETS.md`
> 口径：只读核实，不改任何现有文件，不连服务器/手机。每条结论标 `文件:行号`；查不到的写「未找到」。
> 时间基线：仓库快照 2026-11-16；服务器事实取自 `report\09-服务器盘点.md`（11-14 盘点）。

---

## 0. 一句话结论

**「魔改登录 SDK」不是被改过的 native 库，而是三件东西的组合：**

| # | 是什么 | 在哪 |
|---|---|---|
| ① | APK 内 `assets/SDKConfigSettings.json` 顶层 `sdk_url` 从 `https://sdk-api.yostar.cn` 改成我们自己的地址 | APK 内（要打包） |
| ② | 服务端自写的仿悠星 SDK —— `sdkcard.py`（端口 8080），把 `OpenID` 字段当卡密校验，签发 `User.ID` / `User.Token` | 服务器（不打包） |
| ③ | APK 内 SDK 登录界面文案/布局改成「卡密」 | APK 内（要打包） |

卡密数据源 = `/www/wwwroot/ba_sdk/cards.json`，由 PHP 卡密站（MySQL）经 cron 导出（`work\ba\cardadmin_php\inc\sync.php:3,11-16`、`cron\sync_cards.php:3`）。

**`libairisgcore.so` 整库替换、`libtprt` / `libmain` / `libdhook` / LSPosed 那一整套，与卡密登录无关，已废弃，不要搬。**

---

## 1. 资产清单表

### 1.1 必搬（新 APK 打包 / 服务端保持运行）

| 文件 | 是什么 | 改了什么（原值 → 新值） | 现状 | 能否复用 |
|---|---|---|---|---|
| `assets/SDKConfigSettings.json`（APK 内，仓库**无原件**） | 悠星/Airi SDK 的客户端配置，**顶层** `sdk_url` 决定 SDK 打哪个服务器 | `"sdk_url":"https://sdk-api.yostar.cn"` → `"http://127.0.0.1:8080"`。**只改这一个值**，`sdk_pid:"CN-BA"`、`channel:"official"`、`ali.*` 全部保持（原件形态见 `report\_tmp\cl4.txt:3-13`；原值见 `report\54:377`、`report\96:30`、`work\ba\audit\ba-sdk-protocol.md:7`） | **仓库里只有"改法"没有"文件"**：改法写在 `work\ba\bapatch\repack_e31.py:6-7,16-18` | ✅ 改法直接复用；**值必须换**（见 §5 R1） |
| `work\ba\bapatch\sdkcard.py` | 服务端仿制悠星 SDK（卡密门） | 无"原值"——从 0 写的。路由见 `:73,93,118,131,140,143,147`，兜底 `:151` | 仓库副本 5,814 B / md5 `1245D895668EA8198A43657593C5B22E`；**服务器那份是 5,832 B / md5 `0b4205e0…4b9a`（`report\09:211`）→ 与仓库副本不一致，服务器为真** | ⚠️ **不要直接部署仓库副本**，以服务器 `/www/wwwroot/ba_sdk/sdkcard.py` 为准 |
| `work\ba\bapatch\cards.json` | 卡密库（`sdkcard.py` 每次请求 `json.load`） | — | 2 条卡密：`11111111111`（绑 `09a4d0ab0ee93616`）、`22222222222`（未绑）；服务器上有 2 条、键长均 11（`report\09:214`） | ✅ 格式完全复用；内容由 PHP 站生成 |
| `work\ba\bapatch\sdk_resp\*.json`（9 份） | 上游官方 SDK 响应样本 = 我们的响应模板 | 无（取证原件） | `common_config.json` 7,589 B、`user_quick-login.json`/`user_detail.json` 各 787 B、`user_login.json` 76 B、`common_agreement.json` 1,157,396 B、`common_client-code.json` 23,731 B、`common_geo-ip.json` 51 B、`health-game_duration.json` 65 B、`heartbeat_pulse.json` 45 B | ✅ 服务端运行必需（`sdkcard.py:14-15` 直接读其中 2 份；其余硬编码在代码里） |
| `work\ba\bapatch\res_edited\strings.xml` | SDK 登录界面**文案**（编译前的源 XML） | 手机号→卡密：`hint_phone_number`=`请输入卡密`(`:120`)、`hint_phone_code`=`密码`(`:119`)、`illegal_phone`=`卡密不正确`(`:141`)、`illegal_phone_code`=`卡密不正确`(`:142`)、`login_interval`=`请输入 11 位卡密`(`:167`)、`login_other`=`卡密登录`(`:168`)、`login_phone`=`卡密登录`(`:169`)、`phone_number`=`卡密`(`:264`) | 源文件，26,458 B | ✅ 复用；需重新编译进 `resources.arsc` |
| `work\ba\bapatch\res_edited\fragment_default_mobile_code_login.xml` | 卡密输入页布局 | 验证码整行 `layout_phone_code` 加 `visibility="gone"`（`:15`）；`et_phone` 保留 `maxLength="11"` + `inputType="phone"`（`:14`）；隐藏的 `et_phone_code` 预置 `android:text="123456"`、`maxLength="6"`（`:16`） | 源文件，8,962 B | ✅ 复用（注意 11 位上限，见 R9） |
| `work\ba\bapatch\res_edited\fragment_quick_login.xml` | 快捷登录页布局 | `quick_login_layout` 整块 `visibility="gone"`（`:7`，不再显示一键登录）；文案引用 `@string/phone_number`(`:10`) / `@string/login_interval`(`:11`) | 源文件，4,833 B | ✅ 复用 |
| `work\ba\bapatch\res.apk` | 上面 3 个 XML 编译后的成品：完整 `res/` 树 + `resources.arsc`（1,330,948 B） | 相对官方包替换了整个 `res/` 与 `resources.arsc` | 3,145,659 B | ✅ 重打包原料（`repack_e32b/e34/e35.py:4` 引用） |
| `work\ba\add_sdk_loc.py` | 给宝塔 nginx 插 `location /sdk/` | 新增 `location /sdk/ { proxy_pass http://127.0.0.1:8080/; }`（剥前缀） | 脚本 22 行；该 location 已在生产（`report\09:70`） | ✅ 服务端配置，已生效 |
| `work\ba\cardadmin_php\`（整套 PHP） | 卡密管理站：MySQL 为唯一真源，面板只写库 | — | 见 §4 | ✅ 服务端，不打包 |
| `work\ba\cardadmin_php\cron\sync_cards.php` | MySQL → `cards.json` 定时导出（原子替换 + flock） | — | 见 `inc\sync.php:3-16,329-420` | ✅ 服务端，不打包 |

### 1.2 参考/取证件（不打包，出问题时要靠它复盘）

| 文件 | 是什么 | 改动 | 现状 | 复用 |
|---|---|---|---|---|
| `work\ba\bapatch\repack_e31.py` | **「改 sdk_url」的标准脚本**（也是 libunity 证书绕过的第一次尝试） | `SDK_OLD=b'https://sdk-api.yostar.cn'` → `SDK_NEW=b'http://127.0.0.1:8080'`（`:6-7`），实际替换 `:16-18` | 867 B | ✅ **迁移时照抄这个脚本，改一个字面量即可** |
| `work\ba\bapatch\repack_e30.py` | 只打 libunity 证书校验，不动 sdk_url | `0xA53A38`：`f803002a` → `f8031f2a`（`:5,11-12`） | 858 B | 视新包要不要（见 R7） |
| `work\ba\bapatch\repack_e32.py / e32b.py` | e31 + 换 `res/` + `resources.arsc` 对齐 | 同上 + `:20-21,40-59` | 1,944 / 1,941 B | ✅ 打包流程骨架 |
| `work\ba\bapatch\repack_e34.py` | arsc 首条写入 + 证书补丁 + 改 sdk_url + 换 res | `:12-24`（arsc 对齐）、`:27-29`（unity）、`:32-34`（sdk_url） | 1,819 B | ✅ **最干净的「arsc+unity+sdk_url+res」四合一模板** |
| `work\ba\bapatch\repack_e35.py` | e34 + 替换 `libairisgcore.so` | 同上 + `:5,32,45-47` | 1,782 B | ⚠️ 只取前四步，**libairisg 那步丢掉** |
| `work\ba\bapatch\repack_e38.py` | E36 基础 + libil2cpp 尾部填充字节翻转 + 换回原厂 libunity | `PATCH_AT=0x10260000` 单字节 `^0xFF`（`:6,23-28`）；`:50-52` 换原厂 unity | 1,820 B | 「能进主程序」的版本之一（`report\57:328`） |
| `work\ba\bapatch\repack_e40.py / e41.py` | 加 `classes3.dex` 探针 | 不压缩 + 4 字节对齐（`e40:26-35`、`e41:26-29`） | 1,256 / 1,046 B | 探针用，迁移不需要 |
| `work\ba\bapatch\repack_e42.py` | 换回**原厂** `libunity.so`（从设备 `lib` 目录取） | `:5,11-12,30-32` | 1,076 B | ✅ **E42 = 现役"能进主程序 + SDK 卡密登录通过"的包**（`report\01:13`、`work\ba\audit\ba-pitfalls.md:149-151`） |
| `work\ba\bapatch\sdkrelay.py` | 透明中继到真 `sdk-api.yostar.cn`（经 clash 7890），落盘响应样本 | 无改动，纯转发 + 落盘（`:52-82`）；另有 `FORCE_LOGIN` 开关强制 quick-login 失败（`:39-47,66-76`） | 3,510 B | ⚠️ 取证用；**它生成了 `sdk_resp/` 那 9 份样本** |
| `work\ba\bapatch\sdkemu.py` | 假 SDK 端点：记录一切，一律回 `200 {}` | — | 1,327 B | 协议考古用，已过时 |
| `work\ba\bapatch\relay8080.py` | **手机/本机 8080 → 云端 `https://example.com/sdk` 透传**（补前缀由对端 nginx 剥） | `UP='https://example.com/sdk'`（`:6`）；绑 `127.0.0.1:8080`（`:66`） | 2,151 B；`relay.log` 只有 1 条 `POST /common/config -> 200 (7837 B)` | ⚠️ **这是"形态 A"的手机本地中转，新 APK 不需要**（见 §3） |
| `work\ba\bapatch\sdk.log` | 服务端真实请求日志，318 行 | — | 末条 `11:24:39 /heartbeat/pulse`；含 `LOGIN OK 11111111111`（`:67`）、`QUICK OK`（多处） | ✅ **协议字节级的唯一实证来源** |
| `work\ba\bapatch\e0/e1/e2/e0b/a_signed.apk.idsig`（5 份） | 旧改包的 **APK Signature Scheme v4** 签名凭证（APK 本体已删） | — | 各 16,750,059 B；对应 ~2.143 GB 游戏包（`report\57:134,331`） | ⚠️ 只能证明「签过名」，不能当包用 |
| `work\ba\bapatch\cards.json` | 见 1.1 | — | 200 B | ✅ |

### 1.3 明确**不要搬**（与卡密登录无关 / 已废弃）

| 文件 | 是什么 | 为什么不要 |
|---|---|---|
| `work\ba\bapatch\airisg\libairisgcore.so`（10,304 B）+ `gm_airisg.c` | 自写假 `libairisgcore.so`：替换 `com/airi/core/sign/AiriSgClient` 的 3 个 native（`getAAesKey`→`BAPrivateSrvKey1`、`getAAesIv`→`BAPrivateSrvIV12`、`sign`→全 0，`gm_airisg.c:94-98`），并开线程扫 `/proc/self/mem` 把网关域名改写为 `127.0.0.1:9443`（`:12,15-21,33-76`） | ①整库替换 → **SIGBUS**（`report\57:311`、`report\02:135`）、用户已否决（`report\57:306`）；②它服务的是**网关签名**，不是卡密登录；③**我们的 `sdkcard.py` 根本不验 `Sign`**（全文无验签代码），所以假 sign 对卡密登录零收益 |
| `libtprt_patched.so` / `libtprt_patched2.so` | 改 ACE 自毁跳转 | 已废弃且从未上机（`report\57:306`） |
| `libmain_patched.so` / `lib\libmain.so` / `lib\libgm.so` | 改 DT_NEEDED / 重编 libmain / 打点 so | 已废弃，ACE 禁 NEEDED（`report\57:307-310`） |
| `dhook\libdhook*.so`、`lsp\*`、`repack.py`/`repack4-10.py` | LSPosed 模块 + 把模块塞进包 | 需要 root/LSPosed（`report\57:315,325`）；免 root 目标下不成立 |
| `libil2cpp*.bin`、`patch_*.py`（55 个）、`cave\*` | il2cpp 代码洞注入 / 登录绕过 | 与 SDK 卡密登录是**两条不同的路线**（`report\53`）；免 root 版不需要改 il2cpp |
| `sdkemu.py` / `sdkrelay.py` / `sub_server.py` | 假端点 / 中继 / clash 订阅服务器 | 取证或调试用，生产不需要 |
| `probe.bin/.elf/.o`、`dexprobe\*`、`lsp\build13\Probe13.apk` | 探针 | 调试产物 |

---

## 2. 每个候选的定性（逐条回答任务里的 A–E）

| 候选 | 结论 | 证据 |
|---|---|---|
| **A. `assets/SDKConfigSettings.json` 改 `sdk_url`** | ✅ **就是它，是核心** | `repack_e31.py:6-7,16-18`；`report\54:377-382`（原值 + "全项目唯一被证明改了立刻生效的客户端配置"）；`report\96:30` |
| **B. 悠星 SDK native 库（`libairisgcore.so`）被替换** | ⚠️ **做过，但已废弃，且与卡密登录无关** | `work\ba\bapatch\airisg\gm_airisg.c:1`（注释："替换 libairisgcore.so：保留 AiriSgClient 三个 JNI 方法 + 运行时改写网关域名"）；`repack_e35.py:5,32,45-47`；SIGBUS：`report\57:311` |
| **C. APK 里 SDK 资源/文案/布局被改** | ✅ **是，是必要的一环（体验层）** | `res_edited\*` 3 个 XML（见 1.1）；`report\57:313`；打包链 `repack_e32b.py:4,20-21,40-59` |
| **D. 服务端仿制 SDK（`sdkcard.py`，端口 8080）** | ✅ **是，是链路的核心一半** | 全文 `sdkcard.py`；`report\09:207-218` |
| **E. `repack_e*.py` 里定义的改动** | ✅ **e31 是 sdk_url 改动的唯一权威脚本**；e32b/e34/e35 是它的完整继承 | `repack_e31.py:6-7`；`repack_e34.py:12-34` |

---

## 3. ★ 完整链路（文字版）

### 3.1 形态 A —— 旧方案（手机本地中转，**已验证可用**）

```
[APK] assets/SDKConfigSettings.json
        sdk_url = http://127.0.0.1:8080          ← repack_e31.py:7
              │
              ▼  （手机本机回环，明文 HTTP；app 内 cleartext 被接受）
[手机] 127.0.0.1:8080 监听者 = /data/local/tmp/relay.sh
        busybox nc -l -p 8080 -e relay.sh
        relay.sh 读明文请求 → curl 到 https://example.com/sdk<path>（补 /sdk 前缀）
              │                       ↑ report\13:26 (C7)、report\06:58
              ▼
[服务器] 443  nginx  vhost example.com（真证书）
        location /sdk/ { proxy_pass http://127.0.0.1:8080/; }   ← 剥前缀
              │                       ↑ work\ba\add_sdk_loc.py:5-7、report\09:70,213
              ▼
[服务器] 127.0.0.1:8080  sdkcard.py（pm2 名 ba_sdk / systemd 名 ba-sdk.service）
        ├─ /common/config     → 读 sdk_resp/common_config.json，把 4 个官方域名批量替换成 example.com 后返回（sdkcard.py:73-91）
        ├─ /user/login        → OpenID 字段当卡密；查 cards.json；过期/绑满则拒；否则签发 token
        ├─ /user/quick-login  → 用 Authorization.Head.DeviceID 反查已绑卡密，命中即放行，否则 Code 40003「请输入卡密」
        ├─ /user/detail       → 同上反查
        ├─ /common/geo-ip     → {"Prov":"浙江省"}（硬编码）
        ├─ /health-game/duration → Code 110170「用户已成年,不需要计时」
        ├─ /heartbeat/pulse   → {"Delay":3600}
        └─ 其他               → 一律 200 {"Code":200,"Msg":"OK","Data":{}}
              │
              ▼
[服务器] /www/wwwroot/ba_sdk/cards.json   ← 卡密校验的落点
         {"cards":{"<11位卡密>":{"devices":["<DeviceID>"],"expire":0,"bind_one":true}}}
              │
              ▼
[客户端] 拿 Data.User.Token / Data.User.ID
         → C# 层存 yostarUid / yostarToken（report\27:38-42,313）
         → 网关 Queuing_GetAuthTicket 换 AuthTicket = base64("uid/token")（report\27:65）
         → POST /api/gateway 协议号 Account_CheckYostar（report\27:81）
```

### 3.2 形态 B —— **新免 root APK 应该用的**（去掉手机本地中转）

```
[APK] sdk_url = https://example.com/sdk     ← 只改这一个字符串
              │
              ▼ 公网 443，真证书（Let's Encrypt/宝塔，report\10:17）
[服务器] nginx location /sdk/ → 127.0.0.1:8080/  → sdkcard.py → cards.json
```

**形态 B 的判断依据与保留意见（重要）**：

- 支持：`report\09:961` 断言「客户端 5 条登录请求**全部带 `/sdk/` 前缀**，`sdk_url = https://example.com/sdk`」，`report\09:975` 记 SDK 段「✅ 打通 + 卡密校验通过」。
- **但这条推断可疑**：`report\13:26` 明确写 relay.sh 会**补 `/sdk` 前缀**；而最新的改包实测（15:51，`report\_tmp\cl4.txt:3`、`report\_tmp\cl4.sh:4` 的 `BA_E77.apk`）里 `sdk_url` **仍然是 `http://127.0.0.1:8080`**。
- ⇒ 结论：**「客户端直接连 `https://example.com/sdk`」这件事从未被真机验证过**（见 R2）。`/sdk/` 前缀出现在 nginx 日志里，等价地可以由 relay.sh 造出来。
- ⇒ 迁移前必须做一次 10 分钟测试（§5 步骤 T1/T2），二选一。

### 3.3 请求/响应精确形态（字节级）

**统一请求头**（真客户端，`report\96:126-135`，原样）：

```
Authorization: {"Head":{"PID":"CN-BA","Channel":"official","Platform":"android","Lang":"zh",
  "DeviceID":"<16 hex>","Version":"1.16.1","GVersionNo":"73","GBuildNo":"",
  "DeviceModel":"PLR110","RID":"<uuid4>","Time":<unix>,
  "UID":<uint64 数字>,"Token":"<40hex>"},"Sign":"<base64 RSA-2048>"}
gray-tag: ""
User-Agent: okhttp/4.9.2
```

**我们只用到 `Head.DeviceID`**，`Sign` 完全不校验（`sdkcard.py:33-39`）。这是「假 sign 没必要」的直接依据。

| 端点 | 方法 | 请求体 | 我们的响应 | 出处 |
|---|---|---|---|---|
| `/common/config` | POST | `{}` | 7,589 B 官方配置，域名被替换成 `example.com` | `sdkcard.py:73-91`；样本 `sdk_resp\common_config.json` |
| `/user/login` | POST | `{"OpenID":"<卡密>","Secret":"","Token":"123456","Type":"mobile","UserName":""}` | `{"Code":200,"Msg":"OK","Data":<787B 账号资料>}` | 真实请求 `sdk.log:66,223`；官方同形 `report\96:114`、`report\101:161` |
| `/user/quick-login` | POST | `{}` | 命中 → 787 B 资料；未命中 → `{"Code":40003,"Msg":"请输入卡密"}` | `sdkcard.py:118-129` |
| `/user/detail` | POST | `{}` | 787 B 或 `Data:{}` | `sdkcard.py:131-139` |
| `/common/geo-ip` | POST | `{}` | `{"Code":200,"Msg":"OK","Data":{"Prov":"浙江省"}}` | `sdkcard.py:140-142` |
| `/health-game/duration` | POST | `{}` | `{"Code":110170,"Msg":"用户已成年,不需要计时","Data":{}}` | `sdkcard.py:143-145` |
| `/heartbeat/pulse` | POST | `{"PI":""}` | `{"Code":200,"Msg":"OK","Data":{"Delay":3600}}` | `sdkcard.py:147-149`；`sdk.log:13` |
| `/common/client-code` | POST | `{}` | ⚠️ **无专门路由** → 落到兜底 `200 {"Data":{}}` | 客户端确实请求过：`sdk.log:61` |
| `/common/agreement` | POST | — | ⚠️ **无专门路由** → 兜底空 | 样本存在（1.15 MB）但 `sdk.log` 无请求记录 |
| 其他 | 任意 | 任意 | `{"Code":200,"Msg":"OK","Data":{}}` | `sdkcard.py:151` |

**`User.ID` / `User.Token` 怎么来的**（`sdkcard.py:42-48`）：

```python
tok = hashlib.sha256((card + '|' + device).encode()).hexdigest()[:40]   # 40 位小写 hex
tpl['User']['Token'] = tok
tpl['User']['ID']    = int(hashlib.md5(card.encode()).hexdigest()[:8], 16) % 900000000 + 100000000
tpl['Pass']['NickName'] = 'BA' + card[-4:]
```

对照官方（`report\101:165,170,177-181`）：

| 字段 | 官方值 | 我们的值 | 判定 |
|---|---|---|---|
| `User.ID` | `1013178778`（**10 位**） | 9 位（`1e8 ~ 999999999`） | ⚠️ 位数不同，见 R5 |
| `User.Token` | `076b037e8ff4226c972cd8ab18d914f0db517852`（40 位小写 hex） | 40 位小写 hex | ✅ 形态一致 |
| `Pass.ID` | `22420602` | **原样继承模板的 22420602（所有用户相同）** | ⚠️ 见 R6 |
| `Pass.NickName` | `YS1013178778` | `BA<卡密后4位>` | ✅ 客户自定 |
| `Keys[0].NickName` | `177****1532`（真实用户手机号掩码） | **原样继承** | ⚠️ 见 R6 |
| `Identity.RealName` / `IDCard` | `**仙` / `330*********06062*` | **原样继承** | ⚠️ 见 R6 |
| `User.PID` | `CN-BA` | `CN-BA` | ✅ |

**响应体积对表**（`report\100:137-168` 实测：config 7,589 / quick-login 787 / detail 787 / duration 65 / geo-ip 51 / pulse 45 / 根 `/` 44 B）。

⚠️ 但 `relay.log` 记的是 `POST /common/config -> 200 (7837 B)`，**7837 ≠ 7589**。原因【推断，未逐字节验证】：`sdkcard.py:55` 用 `json.dumps(obj, ensure_ascii=False)` 的**默认分隔符**（`, ` / `: `）重新序列化，每个分隔符后多一个空格；而域名替换本身是**变短**的（`sdkcard.py:78-82` 四组替换逐处计数：`static.bluearchive-cn.com` 25→16 ×2、`sdk-api.yostar.cn` 17→16 ×2、`gs-api.bluearchive-cn.com` 25→16 ×2、`www.baidu.com` 13→16 ×1，净 **−35 B**）。⇒ **+248 主要来自重新序列化，不是替换。** 这一点对"客户端是否按字节校验响应"的判断有意义（结论是它不校验）。

---

## 4. PHP 卡密站 ↔ `cards.json` 的关系（回答"是不是通过 cards.json 对接"）

**是，且是单向的「数据库 → 文件」导出。**

```
[管理员] 浏览器 → ba_cardadmin（PHP，宝塔站点 /www/wwwroot/ba_cardadmin/）
                       │ 只写 MySQL，不碰 cards.json
                       ▼
                 MySQL（唯一真源）
                   表：cards(card_key,status,expire_at,bind_one,…) / card_devices / login_logs / audit_logs / settings / admins / sessions / login_attempts
                       │ sql\schema.sql:47-131
                       ▼
                 cron/sync_cards.php（root 或 www，CLI）
                       │ MySQL → cards.json，原子替换（临时文件 + flock + rename）
                       │ inc\sync.php:3-16,329-420
                       ▼
                 /www/wwwroot/ba_sdk/cards.json
                       │
                       ▼
                 sdkcard.py 每次请求 json.load（不做缓存）
```

关键细节：

- **PHP 站本身不响应任何 SDK 端点。** 我逐文件查过 `cardadmin_php\`：只有面板页面 + `inc\sync.php` + `cron\sync_cards.php`，**没有**任何 `/user/login` / `/common/config` / `/user/quick-login` 的 PHP 实现 → 这部分**未找到**，说明 SDK 门确实只有 `sdkcard.py` 一个。
- **`cards.json` 的目标结构写死在 `inc\sync.php:11-12`**：`{"cards":{"<卡密>":{"devices":["<DeviceID>"],"expire":0,"bind_one":true}}}`，注释原文「与 sdkcard.py 完全一致」。
- **反向合并**：`sdkcard.py` 自己在 `/user/login` 绑新设备时会**直接写 `cards.json`**（`sdkcard.py:108-113`，非原子），所以同步前必须先把 json 里新出现的 device 合并回 MySQL（`inc\sync.php:14-16`、`README.md:294-297`）。cron 已实现这一点。
- **孤儿保护**：首次同步若 `cards.json` 里有库里没有的卡密会被拦截，必须先「从 cards.json 导入」（`inc\sync.php:367-375`、`pages\settings.php:159-162`）。
- **`cards_json_path` 与 `sdk_log_path` 是可配置项**，生产值 `scripts\313_run_install.sh:20-21` 写的是 `/www/wwwroot/ba_sdk/cards.json` 和 `/www/wwwroot/ba_sdk/sdk.log`。
- **卡密格式**：`helpers.php:735-755` `gen_card_key($len,$charset,$prefix)`，长度 4–64 可配置，默认字符集 `ABCDEFGHJKLMNPQRSTUVWXYZ23456789`（大写字母+数字，去掉易混 I/O/0/1）。⇒ **11 位是运营选择，不是强约束**（见 R9）。
- **登录日志**：`login_logs.result` 枚举 `ok/reject/expired/device_limit`（`sql\schema.sql:89`），与 `sdkcard.py` 的四种结果一一对应。

---

## 5. ★ 迁移清单：新免 root APK 要动什么

### 5.1 APK 内（必须打包进去）

| # | 动作 | 具体做法 | 出处/模板 |
|---|---|---|---|
| M1 | 改 `assets/SDKConfigSettings.json` 的 `sdk_url` | 把 `"sdk_url": "https://sdk-api.yostar.cn",` 替换成 `"sdk_url": "<T1 或 T2 测出来的地址>",`。**只动这一个 value**；`sdk_pid` / `channel` / `ali.*` 全部保持原样 | `repack_e31.py:6-7,16-18`（注意：原脚本是 `bytes.replace`，改等长或不等长都行，只要 JSON 合法） |
| M2 | 删 `assets/__tpinfo.*`（5 个：`.tsc` / `.tsc.sig` / `.tsd` / `.tsd.sig` / `.tp`） | 不改这 5 个文件，改包后**启动即闪退且无 tombstone** | `work\ba\audit\ba-pitfalls.md:9-11,16`；脚本 `repack_e31.py:23-24` |
| M3 | 换 SDK 登录界面资源 | 用 `res.apk` 里的 `res/` 整树 + `resources.arsc` 覆盖 | `repack_e34.py:42-54`（`res/`）、`:12-24`（arsc 必须**首条 + STORED + 4 字节对齐 + 0xd935 extra pad**） |
| M4 | 判断要不要 libunity 证书补丁 | **E42 用的是原厂 `libunity.so`**（`repack_e42.py:5,11-12,30-32`）——如果新包不需要绕过证书，就不要打 `0xA53A38` 那 4 字节；若要打：`f803002a`→`f8031f2a` | `repack_e30.py:5,11-12` |
| M5 | 重签名 | `apksigner sign --ks ba_private.keystore --ks-pass pass:baserver --ks-key-alias ba --key-pass pass:baserver`。证书实测：`CN=BA, OU=Private, O=BA, L=NA, S=NA, C=CN`，SHA-256 `ABD1FA978928F8BF9B665023B6AB19E27F62C957CC7C959111D646D2ED0E8701`，有效期 2026-11-12 → 2056-11-04（我从 `e0_signed.apk.idsig` 里解出来的） | keystore 用法：`work\ba\bapatch\lsp\build13.sh:32-33`；证书 DN 旁证：`report\57:137` |
| M6 | 不要加 `classes3.dex` / 任何新 so | E40/E41 加的空 dex 只是探针；新 so 会撞 ACE | `repack_e40.py:26-35`；`HISTORY.md:93`「真正杀进程的是改 .so 代码/加新 .so/加新 dex」 |

### 5.2 服务端（**不打包**，保持运行即可）

| # | 项 | 现状 | 要做的事 |
|---|---|---|---|
| S1 | `sdkcard.py` 监听 `127.0.0.1:8080` | **已停**（pm2 `ba_sdk` 在 11-13 21:30:24 被 stop，之后再没起，`report\09:197`；`ss -tln` 无 8080，`report\09:194`） | 起回来。`cd /www/wwwroot/ba_sdk && setsid nohup python3 sdkcard.py &`（`report\09:318-320`），或 `systemctl start ba-sdk`（unit 在 `/etc/systemd/system/ba-sdk.service`，`report\09:545`） |
| S2 | `/www/wwwroot/ba_sdk/cards.json` + `resp/` 9 个 JSON | 在（`report\09:214-215`） | 核对 `resp/` 目录名（服务器用 `resp/`，仓库叫 `sdk_resp/`） |
| S3 | nginx `example.com.conf` 的 `location /sdk/` | 在，且是正确的带尾斜杠 `proxy_pass`（`report\09:70,72`） | 不动 |
| S4 | PHP 卡密站 + MySQL + cron 导出 | 见 §4 | 保证 cron 在跑，且 `cards_json_path` 指向 S2 |
| S5 | `example.com` 的 TLS 证书 | 真证书（`report\10:17`） | 不要在 sdk 路径上用自签（`report\09:76` 记 `ba_mitm` 证书是自签，那是另一条 `*.bluearchive-cn.com` 的线） |
| S6 | 服务端 `sdkcard.py` 版本 | 服务器 5,832 B / md5 `0b4205e0…`；仓库 5,814 B / md5 `1245D895…` | **以服务器为准**，别用仓库副本覆盖 |

### 5.3 交付前必须做的两个测试（10 分钟）

| 编号 | 动作 | 通过判据 | 为什么必须做 |
|---|---|---|---|
| **T1** | 新包 `sdk_url = https://example.com/sdk`，装真机，看服务端 `sdk.log` | 出现 `/common/config` → `/user/quick-login` 或 `/user/login`，且 `dev=<deviceid>` 非空 | 「客户端直连公网 https」**从未验证过**（R2）。若过，**这是最优解**：无需手机本地任何服务 |
| **T2** | T1 挂了，退 `sdk_url = http://example.com/sdk`（80 端口，明文） | 同上 | 明文已被实跑验证可行（`report\10:17`「sdk_url=http://127.0.0.1:8080 裸 http 能用」）；代价是卡密明文过公网 |
| T0 | 先手工验路径：`curl -i -X POST https://example.com/sdk/common/config -H 'Content-Type: application/json' -d '{}'` | 返回 7.5 KB JSON，且域名已是 `example.com` | 把「nginx 前缀 + 反代 + sdkcard」三段与服务一起排除掉 |

### 5.4 顺手该补的两个服务端小洞（不阻塞迁移，但会出体验问题）

1. **`/common/agreement` 补路由** → 直接返回 `sdk_resp/common_agreement.json`（1.15 MB）。现在落到兜底空对象，用户点「用户协议/隐私政策」会是空白页。
2. **`/common/client-code` 补路由** → 返回 `sdk_resp/common_client-code.json`（23,731 B，错误码→文案表）。客户端确实请求过（`sdk.log:61`）；现在返回空表，意味着所有错误码都会退化成默认文案（例如 `101404` 的「网络异常，请重新连接」）。
3. **`/user/login` 的响应体补 `IsNew` / `TaptapProfile`** → 官方 `/user/login` 是 238 B、含 `Data.IsNew:false`（`report\101:165`），我们现在复用的是 787 B 的 detail 模板、**没有 `IsNew`**（`sdkcard.py:42-48` 从 `user_quick-login.json` 出发）。若客户端首登分支读 `IsNew`，`null` 可能被当 `false` 或抛异常 —— 实测未报错，但属未验证。

---

## 6. 风险点（哪些地方依赖了旧环境）

| 编号 | 风险 | 具体 | 出处 |
|---|---|---|---|
| **R1** | **旧包把 `sdk_url` 钉死在 `127.0.0.1:8080`** | 这是**手机本地回环**，新 APK 若原样搬过去，用户手机上必须有进程监听 8080，否则 SDK 立刻 `onFail {"code":101404,"R_MSG":"网络异常?请重新连接"}` | `repack_e31.py:7`；`report\06:18,355`；最新实测包 `BA_E77` 仍是这个值（`report\_tmp\cl4.txt:3`） |
| **R2** | **「客户端直连公网 https」从未验证** | `report\09:961` 断言 `sdk_url=https://example.com/sdk`，但 `report\13:26` 说 `/sdk` 前缀是 relay.sh 补的；两份口径冲突，且更晚的 `cl4` 实测里值还是 127.0.0.1 | `report\09:961` vs `report\13:26` + `report\_tmp\cl4.txt:3` |
| **R3** | **`/sdk` 前缀与 nginx `location /sdk/` 必须严格对齐** | 多一个/少一个斜杠都会 404；根路径 `/common/config` 实测 404，`/sdk/common/config` 才 200 | `report\09:962,967-968` |
| **R4** | **不能指回旧域名** | `sdk-api.yostar.cn` 是官方服务器，改了签名/卡密就失效；`report\09:76` 还记「没有 `sdk-api.yostar.cn` 的 vhost」 | `report\09:76` |
| **R5** | **`User.ID` 位数不符（9 位 vs 官方 10 位）** | 公式 `md5(card)[:8] % 9e8 + 1e8` 上限 999,999,999（9 位），官方 `1013178778` 是 10 位。若客户端或网关对 ID 做位数/范围校验会翻车 | `sdkcard.py:46`；官方值 `report\101:177` |
| **R6** | **模板里包着真实用户 PII，且 `Pass.ID` 全服相同** | `Keys[0].NickName="177****1532"`、`Identity.RealName="**仙"`、`Identity.IDCard="330*********06062*"`、`Pass.ID=22420602` 都是抓包原件，`user_payload()` 只覆盖了 Token/ID/Pass.NickName | `sdkcard.py:42-48`；原件 `sdk_resp\user_quick-login.json`、`report\101:170,179` |
| **R7** | **签名变更 ⇒ 必须卸载重装** | 官方包与我们签名不同；换签名要卸载，会丢 `/data/data` + 11 GB 资源要重新 chown | `HISTORY.md:464`、`work\ba\audit\ba-pitfalls.md:109-122`、`report\30:344` |
| **R8** | **`ba_private.keystore` 实物在仓库里不存在** | 只有 `lsp\build13.sh:32-33` 的调用（alias `ba` / pass `baserver`）。找不到 keystore 就只能新生成一对密钥 → 又是一次签名变更 | 全仓 `*.jks/*.keystore/*.p12` 搜索 **0 命中** |
| **R9** | **卡密长度被 UI 钉在 11 位** | 卡密输入框复用手机号控件：`et_phone` 有 `android:maxLength="11"` + `inputType="phone"`（数字键盘）。而 PHP 端 `gen_card_key` 长度 4–64 任意、默认字符集含**字母** ⇒ 超过 11 位或含字母的卡密在客户端**根本输不进去** | `res_edited\fragment_default_mobile_code_login.xml:14`；`helpers.php:735-755`；现有卡密确实是 11 位纯数字（`cards.json`、`report\09:214`） |
| **R10** | **`__tpinfo` 不删就必闪退** | 改 `assets/` 或任何 so 后启动即闪退，无 tombstone | `work\ba\audit\ba-pitfalls.md:9-11` |
| **R11** | **服务端版本漂移** | 仓库 `sdkcard.py` ≠ 服务器 `sdkcard.py`（5814 vs 5832 B，md5 不同） | 我本地 `Get-FileHash` vs `report\09:211` |
| **R12** | **手机本地中转属"易失"资产** | `/data/local/tmp/relay.sh` + `nc -l -p 8080` 重启即失效（`report\06:84,374`）——这也正是形态 A 必须被淘汰的理由 | `report\06:84,398`；`report\13:96`（P5 未决） |

---

## 7. 未找到 / 待验证

| 项 | 状态 |
|---|---|
| `assets/SDKConfigSettings.json` 的**原始文件本体**（仓库内） | **未找到**。仓库只有它的改法（`repack_e31.py`）与外部引用（`report\54:377`、`report\96:30`、`report\_tmp\cl4.txt:3-13` 的实测全文）。打包时必须从官方 APK 里取 |
| `ba_private.keystore` 实物 | **未找到** |
| `/data/local/tmp/relay.sh` 原文 | **未找到**（只有 `report\06:58` 的描述 + 生成脚本 `report\_tmp\c42.sh:1-35`） |
| `/www/wwwroot/ba_sdk/` 的实机副本 | **未找到**（只有 `report\09:207-218` 的盘点值） |
| `/common/agreement` 的客户端调用记录 | **未找到**（`sdk.log` 318 行内无该路径；样本存在但不知道何时被请求） |
| 官方对 `Sign` 校验失败的客户端表现 | **未找到**（我们服务端从不校验，所以没有观测面） |
| `libairisgcore.so` 原厂文件 | **未找到**（仓库只有自写的假 so；`report\57:311`） |
| 「免 root」路线的正式结论 | 见 `work\ba\noroot\OPTIONS.md`、`HISTORY.md:348-386`（`report\90:264`「免 root 分发不可行」被 `HISTORY.md:386` 判为未验证） |

---

## 8. 出处索引（本文引用到的文件）

| 文件 | 一句话作用 |
|---|---|
| `work\ba\bapatch\repack_e31.py` | **sdk_url 改动的权威脚本**（唯一显式定义 OLD/NEW 字面量的地方） |
| `work\ba\bapatch\repack_e30.py` | libunity 证书补丁（`0xA53A38`） |
| `work\ba\bapatch\repack_e32b.py` / `e34.py` / `e35.py` | arsc 对齐 + res 替换 + sdk_url 的组合模板（e35 多一步 libairisg） |
| `work\ba\bapatch\repack_e38.py` / `e42.py` | 「能进主程序」的两版；e42 用原厂 libunity |
| `work\ba\bapatch\sdkcard.py` | 服务端卡密 SDK（路由、token 生成、卡密校验全在这） |
| `work\ba\bapatch\sdkrelay.py` | 上游中继，生成了 `sdk_resp/` 那 9 份样本 |
| `work\ba\bapatch\relay8080.py` | 形态 A 的 8080→云端中转 |
| `work\ba\bapatch\sdkemu.py` | 假端点记录器 |
| `work\ba\bapatch\sdk_resp\*.json` | 9 份上游响应样本 = 我们的响应模板 |
| `work\ba\bapatch\res_edited\*.xml` | 3 个改过的 SDK 界面源文件（卡密文案 / 隐藏验证码行 / 隐藏快捷登录） |
| `work\ba\bapatch\res.apk` | 上述 3 个 XML 编译后的成品（整树 res/ + resources.arsc） |
| `work\ba\bapatch\airisg\gm_airisg.c` + `libairisgcore.so` | 自写假 airisg so（已废弃） |
| `work\ba\bapatch\sdk.log` | 协议实证日志（318 行） |
| `work\ba\bapatch\cards.json` | 卡密库（2 条） |
| `work\ba\add_sdk_loc.py` | nginx `/sdk/` → `127.0.0.1:8080/` |
| `work\ba\cardadmin_php\inc\sync.php` | MySQL → cards.json 同步引擎 |
| `work\ba\cardadmin_php\cron\sync_cards.php` | 定时导出 |
| `work\ba\cardadmin_php\inc\helpers.php` | `gen_card_key()` 卡密生成规则 |
| `work\ba\cardadmin_php\sql\schema.sql` | 卡密库表结构 |
| `report\09-服务器盘点.md` | 服务器侧现状（路径/端口/进程/pm2/nginx） |
| `report\06-手机基线恢复.md` | 101404 定性 + relay.sh |
| `report\13-总账-2026-11-14凌晨.md` | C7：`sdk_url` 值 + relay.sh 补 `/sdk` 前缀 |
| `report\96-官方服务器探针方案.md` | 官方请求头原文 + `SdkConst.Uri` 端点表 + `/auth/v1` 纠错 |
| `report\101-官方真服抓包分析.md` | 官方 `/user/login` 238B、`/user/detail` 787B 原文 |
| `report\54-客户端补丁方案-本地配置绕过.md` | `SDKConfigSettings.json` 原值与"改了立刻生效" |
| `report\57-既有补丁资产清点.md` | 全资产清点表（§5 各组） |
| `report\04-服务端就绪度.md` | 两种部署形态（本机/云端）互斥于 8080 |
| `work\ba\audit\ba-pitfalls.md` | `__tpinfo` 必须删、E42 配方 |
| `work\ba\noroot\HISTORY.md` / `OPTIONS.md` | 前序免 root 与历史重建（同目录，其他 agent 产出） |
