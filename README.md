# BA 自研补丁交付包 · 20261120 · **终极合并 + 统一脱敏 + 文件名脱敏版**

> ## ✅ 本包已脱敏
>
> 包内**全部文本文件**的口令、密钥、令牌、设备指纹、真实域名、公网 IP、证书路径、邮箱/手机号，已统一替换为 `<REDACTED_*>` / `<SERVER_IP>` / `<CERT_PATH>` / `example.com` 占位符：**293 个文件 / 1,938 处**，逐条台账见包根 **`REDACTION.md`**（不含任何原值）。
> **二进制一律未动**（77 个：dll / pyc / png / zip / pem / db…），换行风格（LF/CRLF）与编码（UTF-8 无 BOM）保持原样；**文件名也已脱敏**——第二轮（2026-11-21）把 **23** 条路径里带真实域名/真实 IP 的文件名与目录名改成 `example.com` / `server_ip`（只改名字、不动字节内容，逐条见 `REDACTION.md` 末节「§ 文件名脱敏」）。
> 例外与残留说明见 §6；若你在包内发现**任何 `<REDACTED_*>` 之外的可疑真实凭据，请立即反馈**。

> ## ⚠️ 上游服务端本身的硬伤：公网部署前必须自行加固
>
> 本包配套的上游开源服务端（`Shittim-Server`）**没有 token 校验 / 没有请求大小上限 / 管理 API 没有权限分级**：
> 
> | 缺陷 | 后果 | 最低加固 |
> |---|---|---|
> | **无 token 校验**：`/api/*` 会话只靠请求体里的 `SessionKey`，服务端不验来源、不验签名 | 拿到一个 token 就能冒充任意账号；直接打 5000 端口甚至不需要 token | 5000/5100 **只监听 `127.0.0.1`**，对外只留 nginx → 桥 |
> | **无请求大小上限** | 超大 body 直接吃内存/磁盘，可被用来压垮进程 | nginx `client_max_body_size` + `limit_req`（部署文档 §8.3 有现成配置） |
> | **管理 API 无权限分级** | `AdminApiKey` 一旦泄露 = 全部 GM 能力；且只有一个 key、无角色、无审计分级 | 管理 API 在公网 vhost 上 **404**，只走 `127.0.0.1`；key 32+ 随机字符并定期轮换 |
> 
> 完整加固清单见 **`DEPLOY_一键部署.md` §8**；本文 §5 与 `DEPLOY_一键部署.md` 的每一步都带验收命令。

> **本目录只有一个交付物：`BA_自研补丁_20261120.zip`。**
> 上游源码（原 `服务端源码\`、`客户端相关\`）按用户要求**已从本交付目录删除**，不再随包交付；
> 源目录 `C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\` **一个字节都没有改动**（本次只做只读复制 + 只改包内副本）。
> 包内：桥与 90004 补丁脚本、自研编译的服务端 DLL 与自有配置、面板 PHP、客户端补丁脚本与 smali、自有文档、线上综合管理站 `panel_full/` 整站快照，外加 **2026-11-21 新并入的 `server_config/`（线上服务端配置快照）、`bridge_tools/`（桥工作目录快照）、`DEPLOY_一键部署.md` 与 `REDACTION.md`**。

---

## 0. 目录现状

```
C:\Users\su\Desktop\BA_交付_20261120\
├─ BA_自研补丁_20261120.zip      10,908,159 B   ← 唯一交付物
├─ MANIFEST_ZIP.txt              139,728 B   ← zip 内 MANIFEST.txt 的包外同文本副本（逐字节相同）
└─ README.md                             本文件
```

---

## 1. 交付物：zip 本体

| 项 | 值 |
|---|---|
| 路径 | `C:\Users\su\Desktop\BA_交付_20261120\BA_自研补丁_20261120.zip` |
| 包内根 | `MANIFEST.txt` `REDACTION.md` `DEPLOY_一键部署.md` + `bridge/ client/ docs/ docs_all/ panel/ panel_full/ server/ server_config/ bridge_tools/` |
| 大小 | **10,908,159 B**（10.40 MiB；其中纯压缩数据流 10,710,219 B，压缩率 30.99%） |
| **sha256** | **`3fa74d736ed035b05b053df3b62b86344fd5674acb8aa76cd2e7a6c557ac0d89`** |
| 条目数 | **1,174**（1,173 个文件 + 根目录 `MANIFEST.txt`） |
| 解压后合计 | 34,556,769 B（32.96 MiB）= 清单内 34,417,041 B + `MANIFEST.txt` 139,728 B |
| `MANIFEST_ZIP.txt` | 139,728 B，sha256 `0c994c3770593fa7dada23f8ad57fa613c1b0fa5cdc1544a38a0a99e67d68a36`，与 zip 内 `MANIFEST.txt` **逐字节相同** |
| 打包方式 | .NET `ZipArchive`（条目名一律正斜杠 `/`，**未用** `Compress-Archive`） |

> ※ zip 根目录**没有**放 `README.md`：本文件只在包外。包内根目录的三个说明文件是 `MANIFEST.txt` / `REDACTION.md` / `DEPLOY_一键部署.md`。

### 1.1 本次新增了什么（2026-11-21 最终合并）

| 新增内容 | 来源 | 文件数 | 字节 | 说明 |
|---|---|---:|---:|---|
| `server_config/` | `work\ba\srv_live\SRVCFG_20261120\` | **149** | **1,601,417** | nginx 98 + systemd 3 + bapatch_root 33 + ba_sdk 14 + 快照 `SHA256SUMS.txt` 1 |
| `bridge_tools/` | `work\ba\srv_live\SRVCFG_20261120\bapatch\` | **183** | **7,526,265** | `tools/` 182 + `_ba_state/` 1 |
| `DEPLOY_一键部署.md` | `work\ba\plan\20261120\` | 1 | 66,547 | 放在**包根**，仍是部署口径的权威文档 |
| `REDACTION.md` | 本次生成 | 1 | 138,004 | 脱敏台账（逐文件 / 逐行 / 占位符），**不含原值**；末节追加「§ 文件名脱敏」 |

**`server_config/` 明细**（保留快照的相对结构；本轮把其中 **18 个文件 + 2 个目录**里带真实域名/IP 的名字改掉，见 `REDACTION.md` 末节）：

| 子目录 | 文件数 | 字节 | 内容 |
|---|---:|---:|---|
| `server_config/nginx/nginx_conf` | 38 | 38,960 | nginx 主配置树（`nginx.conf` + `conf.d`/`enable-php-*`/`mime.types` 等，含 `.default` 与历史变体） |
| `server_config/nginx/vhost` | 60 | 118,008 | 站点 vhost（`nginx/` 下站点配置 + `tcp/ba_sni.conf` + `extension/` + `well-known/`） |
| `server_config/systemd` | 3 | 1,745 | `ba-bridge.service` / `ba-sdk.service` / `ba-shittim.service` |
| `server_config/bapatch_root` | 33 | 159,995 | `/www/wwwroot/bapatch/` 根级：27 个 `cn_*.txt` 开关 + `gen24000.py` / `patch_24000_v3.py` / `patch_requestid.py` + `NOTES-gateway.md` / `README_CA_LOCK.txt` |
| `server_config/ba_sdk` | 14 | 1,242,020 | 卡密 SDK 站点：`resp/` 10 份响应快照 + `sdkcard.py` / `ban_message.py` / `check_order_probe.py` / `pay.json` |
| `server_config/SHA256SUMS.txt` | 1 | 40,689 | 快照自带的线上清单原件（原样保留） |

### 1.2 统一脱敏（本次核心动作）

| 项 | 值 |
|---|---|
| 处理范围 | 包内**文本文件** 1,096 个（`.php .py .sh .json .js .css .html .ini .conf .service .md .txt .sql .user.ini` + 无扩展名的纯文本 nginx 片段） |
| 跳过 | **二进制 77 个**（红线：绝不 redact 二进制） |
| 改动文件 | **293** 个 |
| 替换处数 | **1,938** 处 / 1,736 行 |
| 台账 | 包根 `REDACTION.md`（138,004 B，逐条列出 文件 / 行号 / 占位符，**无一个原值**） |
| 文件名脱敏（第二轮） | **23** 条路径改名（21 个文件 + 2 个目录）：真实域名 → `example.com`、真实公网 IP → `server_ip`；只改名字、不动字节内容 |

| 类别 | 占位符 | 文件数 | 处数 |
|---|---|---:|---:|
| 数据库口令/用户 | `<REDACTED_DB_CREDENTIAL>` | 9 | 10 |
| 应用密钥 | `<REDACTED_SECRET>` | 1 | 1 |
| 令牌/会话 | `<REDACTED_TOKEN>` | 110 | 341 |
| 设备指纹 | `<REDACTED_DEVID>` | 8 | 27 |
| 邮箱/手机号 | `<REDACTED_CONTACT>` | 9 | 23 |
| 公网 IP | `<SERVER_IP>` | 74 | 281 |
| 证书路径 | `<CERT_PATH>` | 42 | 128 |
| 真实域名 | `example.com` | 116 | 1127 |
| **合计** | — | **293**（去重） | **1,938** |

> 合规校验（本次实测）：脱敏后逐文件复核 **JSON 全部仍可解析、Python 全部仍可编译、括号/引号计数逐文件不变**（翻转数 = 0）；二进制改动 **0** 个。详见 `REDACTION.md` §2–§3。
>
> **文件名也已脱敏**：第二轮（2026-11-21）只改名字、不动内容，把 **23** 条带真实域名/IP 的路径改为 `example.com` / `server_ip`（同目录撞名加 `-2`/`-3`），并同步改写 `REDACTION.md` 路径列、`server_config/SHA256SUMS.txt`、`GameMainConfig_http_*.bin` 的文件名引用；条目名复扫 **0 命中**。

### 1.3 包内关键产物速查

| 包内路径 | 字节 | sha256 | 说明 |
|---|---:|---|---|
| `server/Shittim-Server.dll` | 2,727,424 | `c013f4427ad01d44c00cc63af3de817b800638fcd8ec0ee55de41126aed106aa` | 与出包时线上 `/www/wwwroot/ba_srv/Shittim-Server.dll` 一致（二进制，未改） |
| `server/Schale.dll` | 5,392,896 | `b06f46090f9d8eb8657e51401b789178d9090ad5a5a6d6d1faaa791dad429858` | DTO 库（二进制，未改） |
| `server/Data/GachaRecruitBanners.cn.json` | 40,739 | `3ac8385d77a2921932eedf934de83178f61a6c8c30b588c3ca64718f0c423c77` | `"Id"` 计数 **529** 条 |
| `server/Services/ClientItemFilter.cs` | 15,601 | `b14d2a228657ba6f561dd482090f981371bcd50b751e60f341cf922ff823cd50` | 自研过滤逻辑源码单件 |
| `bridge/account_auth_probe.py` | 228,784 | `9060ed7c68a9ea26e0cdf848e3f5505d706fd6a5580729141f3ccb613c8002e8` | 线上真身（脱敏后） |
| `bridge/patch_90004.py` | 30,946 | `c94bae46d6d052945b16446e4f5a35a9cdaf8e3dae896200ece6be5dca4589cf` | 90004 打补丁 |
| `bridge/verify_90004.py` | 27,308 | `84d685bb58453ab72e8fe7193b6c73e3e6bfe0407b2096c10bb202e699feb869` | 90004 校验（`RESULT: PASS` 判据） |
| `bridge_tools/tools/account_auth_probe.py` | 228,784 | `9060ed7c68a9ea26e0cdf848e3f5505d706fd6a5580729141f3ccb613c8002e8` | 桥工具目录里的同一份脚本（脱敏后） |
| `bridge_tools/_ba_state/90004_ops.json` | 10,883 | `938ae90855b5fa5fa11342854f2e0f28e7130b466c303621151685efc06107fb` | 90004 运营数据 |
| `server_config/bapatch_root/patch_24000_v3.py` | 60,456 | `0dd983084c5a1f494e2f622e5d1edb15b305d0548416185c6ef5cec35a2aae7e` | 24000 补丁 v3 |
| `server_config/bapatch_root/patch_requestid.py` | 57,287 | `a1fbffe9a8991834d0a74e452da403de1f312cd87e2abdd79a2dbb580dd9be3c` | RequestId 补丁 |
| `server_config/ba_sdk/sdkcard.py` | 33,454 | `2f7d32b18e865dfe6d61d4ff52c8f7bbef47e2775cce9932605858305cc39fb2` | 卡密 SDK 主程序 |
| `server_config/ba_sdk/pay.json` | 47 | `4461167078cef3a9766f6728a22a5496ea22bcf974ea34b6d2aa31ad9c398a54` | 支付开关（`2/2/3000` = 关） |
| `server_config/systemd/ba-bridge.service` | 479 | `410e27a5d288318f55a892707b92b96d3dd9d22648ae1b2f3b2efab1e45dc287` | 桥的 systemd 单元 |
| `server_config/systemd/ba-sdk.service` | 449 | `10ecdf08522a810b6f8074dc5e1ef9371972da40a20c29915cc8a5b1d03d2035` | SDK 站点 systemd 单元 |
| `server_config/systemd/ba-shittim.service` | 817 | `d1f6eb93854b18bd6d0ca17c8b500c0f0d10cb235d118005d3ebf459ae2a7bb3` | 服务端 systemd 单元 |
| `server_config/nginx/vhost/nginx/ba_mitm.conf` | 4,352 | `a590c1f183badc4e16da62ce4803cef2ada1c93e6df1be80ef8b4783205b3b85` | 主导流 vhost（域名/证书路径已换成占位符） |
| `panel_full/ba_cardadmin/config.php` | 1,088 | `5ddb2a841d7cce6e1d9fa0f659403d1d065d7ebeba7a0d19b858825674154df1` | 管理站配置（**DB 口令与 `APP_SECRET` 已脱敏**） |
| `panel_full/ba_cardadmin/inc/ba.php` | 17,298 | `752f1637bdb86787b1600cc04e506cd3e25b5a161806ff012439fdddded55771` | 面板 ↔ 服务端桥接（`BA_ADMIN_KEY` 读取侧） |
| `panel_full/ba_cardadmin/installed.lock` | 293 | `06dee44818de25442787761a33d1fd9511ccccc4bd9a5fa084c12da209c5c7c5` | “已安装”标记，缺它站点会走未安装引导 |
| `DEPLOY_一键部署.md` | 66,547 | `730c9573d2c294569e17189d0bc4e4d97eae6fcffe6004ac3ec332aa44f1e6ed` | 部署权威文档（§0/§5 已按脱敏口径改） |
| `REDACTION.md` | 138,004 | `c0d1cbda237fa041d7b9171cd2402a4826031e5af882606ab5f6e24f8f081f4e` | 脱敏台账（含末节「§ 文件名脱敏」） |
| `MANIFEST.txt` | 139,728 | `0c994c3770593fa7dada23f8ad57fa613c1b0fa5cdc1544a38a0a99e67d68a36` | 逐文件清单（本文件 §3 的资料来源） |

---

## 2. 内部结构树（目录 / 文件数 / 解压后字节）

```
BA_自研补丁_20261120.zip/   1,174 个文件 / 34,556,769 B（10,908,159 B 压缩包）
├─ bridge/                    17 个文件       857,155 B  桥 / 90004 补丁与校验脚本、systemd 说明（含 `_history/` 两份旧副本）
│  └─ _history/                2 个文件       396,164 B  两份旧副本（未删）
├─ bridge_tools/             183 个文件     7,526,265 B  **本次新增** · 桥工作目录整体快照：`tools/`（182 个脚本与历史变体）+ `_ba_state/`
│  ├─ _ba_state/               1 个文件        10,883 B  90004 运营数据
│  └─ tools/                 182 个文件     7,515,382 B  桥工具脚本（182 个，含历史变体与子目录）
├─ client/                   308 个文件     4,333,351 B  客户端补丁：smali、资源、构建脚本
│  ├─ apk_patch/             134 个文件     1,233,370 B  APK 补丁工作区（基线清单、成品脚本）
│  └─ noroot/                174 个文件     3,099,981 B  免 root 构建（含签名材料，注意保管）
├─ docs/                      18 个文件       364,694 B  精选文档（根因/部署/回滚/交接），平铺
├─ docs_all/                 423 个文件    10,371,851 B  全部文档全集（`docs/` 的超集，保留源树相对路径）
│  ├─ kit/                     5 个文件        77,992 B  工具包说明（logcat / state / probe）
│  ├─ report/                114 个文件     3,855,482 B  报告
│  ├─ scripts/                 3 个文件        14,457 B  脚本说明
│  └─ work/                  298 个文件     6,249,237 B  工作区文档
├─ panel/                      6 个文件       125,888 B  管理面板 PHP（精选改动文件）
│  ├─ inc/                     3 个文件        61,783 B  面板 include
│  ├─ pages/                   2 个文件        48,298 B  面板页面
│  └─ variant_p0rates/         1 个文件        15,807 B  p0rates 变体（仅对照）
├─ panel_full/                54 个文件       760,710 B  线上综合管理站整站只读快照（可还原整站）
│  └─ ba_cardadmin/           54 个文件       760,710 B  53 站点文件 + `SHA256SUMS.txt`
├─ server/                    13 个文件     8,271,284 B  已编译服务端 DLL（线上同款）
│  ├─ Data/                    3 个文件        41,531 B  抽卡配置（529 横幅 / 4 组概率）
│  ├─ Resources/               7 个文件        93,832 B  7 份客户端 id 白名单
│  └─ Services/                1 个文件        15,601 B  ClientItemFilter.cs 源码单件
├─ server_config/            149 个文件     1,601,292 B  **本次新增** · 线上服务端配置快照：nginx 主配置 + vhost、systemd 三单元、bapatch 根级脚本/开关、ba_sdk 站点、快照自身 `SHA256SUMS.txt`
│  ├─ ba_sdk/                 14 个文件     1,242,020 B  卡密 SDK 站点（`resp/` 10 份响应快照 + 4 个根级文件）
│  ├─ bapatch_root/           33 个文件       159,995 B  `/www/wwwroot/bapatch/` 根级：27 个 `cn_*.txt` 开关 + 3 个补丁脚本 + 说明
│  ├─ nginx/                  98 个文件       156,848 B  nginx 配置快照（`nginx_conf/` 主配置 + `vhost/nginx/` 站点配置）
│  └─ systemd/                 3 个文件         1,745 B  `ba-bridge` / `ba-sdk` / `ba-shittim` 三个 unit
├─ DEPLOY_一键部署.md              1 个文件        66,547 B
├─ MANIFEST.txt                1 个文件       139,728 B
└─ REDACTION.md                1 个文件       138,004 B
```

> `MANIFEST.txt` 是 zip 自带的清单，**不在它自己的 1,173 行清单里**；清单内 1,173 个文件合计 34,417,041 B。

---

## 3. 清单表（按目录：相对路径 + 字节 + sha256）

> 数据来源：zip 内 `MANIFEST.txt`；包外同文本副本为 `MANIFEST_ZIP.txt`（139,728 B）。
> **1,173 行**全部可在 `MANIFEST_ZIP.txt` 里逐条复核；此处按目录铺开 `docs_all/` 以外的全部 750 行（`docs_all/` 的 423 行会撑爆本文件，见 §3 末行汇总）。

### `（根目录）` — 2 文件 / 204,168 B

| 相对路径（zip 内） | 字节 | sha256 |
|---|---:|---|
| `DEPLOY_一键部署.md` | 66,547 | `730c9573d2c294569e17189d0bc4e4d97eae6fcffe6004ac3ec332aa44f1e6ed` |
| `REDACTION.md` | 138,004 | `c0d1cbda237fa041d7b9171cd2402a4826031e5af882606ab5f6e24f8f081f4e` |

### `bridge/` — 15 文件 / 460,991 B

| 相对路径（zip 内） | 字节 | sha256 |
|---|---:|---|
| `bridge/90004_ops.json` | 10,883 | `938ae90855b5fa5fa11342854f2e0f28e7130b466c303621151685efc06107fb` |
| `bridge/90004_patch.branch.diff` | 2,348 | `1d5dc7a3b84be614fffffe81001ad7e9054c322a16a777800e52b81a63cbad2c` |
| `bridge/90004_patch.full.diff` | 9,103 | `7dcf28063d9078d10c454cf8f2199ac75c8610fa2fcaab72dba75f50f5229d79` |
| `bridge/account_auth_probe.py` | 228,784 | `9060ed7c68a9ea26e0cdf848e3f5505d706fd6a5580729141f3ccb613c8002e8` |
| `bridge/BRIDGE_SYSTEMD.md` | 7,689 | `272ae6833c8a9e6252e17123fe8ab8e704ed325a464deef466e342368c18b9c5` |
| `bridge/check_patch_90004.py` | 6,350 | `bebff1db04dd13b89842421da6ce9a453be6835576b5a79f95607f5af63027ec` |
| `bridge/deploy_all.py` | 64,334 | `923a2168747a06313333682d7fd2c66f7c93f09bc5b2d3be3f23e53fbb4dfa4f` |
| `bridge/DEPLOY_PLAN.md` | 36,882 | `25a33687a2ff326b5802b36e4b8570abe839f2b45416d614d4d2b3a6d1f813cf` |
| `bridge/dto90004.py` | 8,891 | `bfd07f765709e9d2c30f5acab10b33021e61676e4f0d98eb1dff56a8fd6fe654` |
| `bridge/expected_90004.json` | 11,408 | `a2d0fee9dcfb0e56cbdb09c063ce70757c15ac2df2102c2ab7542af4ab104e65` |
| `bridge/make_ops_90004.py` | 6,394 | `a90fbfa8b14002213108d45867ba6b6638ed81bf2160685b0164cd67393efca6` |
| `bridge/patch_90004.py` | 30,946 | `c94bae46d6d052945b16446e4f5a35a9cdaf8e3dae896200ece6be5dca4589cf` |
| `bridge/preflight_90004.py` | 4,500 | `a6a9f3277717a42ea614ed1fa25a9d36b846e9e7a750dd80b588a9cff60239e3` |
| `bridge/selftest_90004.py` | 5,171 | `3dc25d5255b384560e8b8e2c692749758468ef6bfc09046b81d4805b7db656ce` |
| `bridge/verify_90004.py` | 27,308 | `84d685bb58453ab72e8fe7193b6c73e3e6bfe0407b2096c10bb202e699feb869` |

### `bridge/_history/` — 2 文件 / 396,164 B

| 相对路径（zip 内） | 字节 | sha256 |
|---|---:|---|
| `bridge/_history/account_auth_probe.p90004-16d4efcb.py` | 167,433 | `81af743aea9420b4d1ac67948b0a223898e025a55c404d71bb8b10b43e73287a` |
| `bridge/_history/account_auth_probe.v222486-6756a5de.py` | 228,731 | `26462e99035f36b75b4361e847397bc35f3430f82ce2345d0a5e7046e76d18db` |

### `bridge_tools/_ba_state/` — 1 文件 / 10,883 B

| 相对路径（zip 内） | 字节 | sha256 |
|---|---:|---|
| `bridge_tools/_ba_state/90004_ops.json` | 10,883 | `938ae90855b5fa5fa11342854f2e0f28e7130b466c303621151685efc06107fb` |

### `bridge_tools/tools/` — 178 文件 / 7,500,361 B

| 相对路径（zip 内） | 字节 | sha256 |
|---|---:|---|
| `bridge_tools/tools/8000_catalog.json` | 144,429 | `4b43b8314d2a0ac5a3ffa68f4e7d732ce7c2446788626d116232c96a1071c24c` |
| `bridge_tools/tools/_p3_replay.py` | 12,541 | `65946b813d8d46c1866a4dde8ef0bdb8ee42023cc2c80f10a604538599100556` |
| `bridge_tools/tools/_relay2_replay.py` | 41,039 | `30e43a5e627fc6896efb40766b8a1f86741942523348271ae0bd7fed89a4c6d1` |
| `bridge_tools/tools/_relay_replay.py` | 38,134 | `ce55d10ef4b20313c242a8dd692dd47df9c091d99a8e6464d9171baff0b2aff2` |
| `bridge_tools/tools/_relayfix2_replay.py` | 27,505 | `815322126e605070b1e0ce26b8d2ce158cc171777e3e80ff7f8989077e0b97f4` |
| `bridge_tools/tools/_relayfix_replay.py` | 23,778 | `81fcd583b52c0640d16debe642ae953737ead8b591682cce6f4dc5c264c0c12c` |
| `bridge_tools/tools/account_auth_probe.py` | 228,784 | `9060ed7c68a9ea26e0cdf848e3f5505d706fd6a5580729141f3ccb613c8002e8` |
| `bridge_tools/tools/account_auth_probe.py.ab27.1794604815` | 35,353 | `75c637854bd02cba41bdf3fbd70bf86916430f7132b68471a89e853e90136591` |
| `bridge_tools/tools/account_auth_probe.py.bak.20261116-063006` | 73,413 | `a19ece08d3ba9897fa8d990108f86e7f1b3dc202bb91993cf7dde0ad6f75a97c` |
| `bridge_tools/tools/account_auth_probe.py.bak.20261116_060707` | 53,994 | `56307054852ccf21692f2af9fd9b8ea15578900c9738994535042451bb6d9a00` |
| `bridge_tools/tools/account_auth_probe.py.batch1.bak.20261117_202722` | 152,773 | `5835053f28e4781ece003968c871126400724e3fea1a78404fe4c51c998721db` |
| `bridge_tools/tools/account_auth_probe.py.billingblock.bak.200735` | 148,515 | `f316006b47440445521edb5280e7c6b4dd5ab82257f5e438934d455b2e395035` |
| `bridge_tools/tools/account_auth_probe.py.bridgev5.1794595958` | 3,860 | `be72c71091e250e3148d2ba2df598e15ee4fecc70b80705d2556486c74412891` |
| `bridge_tools/tools/account_auth_probe.py.canary.1794599376` | 20,073 | `f6e00cdfe294fb2ecce5256cc5216833812b9fc29033eaefc6529b691b5c1041` |
| `bridge_tools/tools/account_auth_probe.py.canarypos.1794600510` | 23,436 | `65fe0dbc5f0e58ddcc65241686a270ef047065173a2d51d300c8ac9bdf76a44c` |
| `bridge_tools/tools/account_auth_probe.py.cnresp.1794598994` | 17,455 | `568abe351104313eee2a73de27422fc685530a7b7f97fb3f63060b62c354f141` |
| `bridge_tools/tools/account_auth_probe.py.cnresp.1794599022` | 17,455 | `568abe351104313eee2a73de27422fc685530a7b7f97fb3f63060b62c354f141` |
| `bridge_tools/tools/account_auth_probe.py.e0.1794601768` | 29,026 | `a26748b7e7bdb10145a2e76c023f076362e8e06087fbdfdd168dde9483fb94c5` |
| `bridge_tools/tools/account_auth_probe.py.e1.1794603011` | 31,081 | `23f44667e668823a3c75cb88b600b9e7db4aab37aa78c206996d14e7b9004180` |
| `bridge_tools/tools/account_auth_probe.py.e2.1794603124` | 32,066 | `2f0539920afca817b08cc746642214ee4a0a791b9f2faf4e395c59ef394be018` |
| `bridge_tools/tools/account_auth_probe.py.e3.1794603141` | 33,087 | `9c4ae0691e60a88f2b8830c61820ecd208788f6b697b83d659da25fb29f61127` |
| `bridge_tools/tools/account_auth_probe.py.e4.1794603502` | 34,039 | `440a9c768ab52b5b87a8eed8e3d585962d4025463aa7504bb4c3efa7edde6e20` |
| `bridge_tools/tools/account_auth_probe.py.encb64.1794600835` | 23,582 | `7b99f05d5e89f4cce4fe533812404079c3863951120ef4727d02fbc90cbc8bdc` |
| `bridge_tools/tools/account_auth_probe.py.encresp.1794596619` | 12,866 | `825b3ae358b4f2c71c729c258be8eb5c3eaadff9c483aa56b251cb89aadf65d4` |
| `bridge_tools/tools/account_auth_probe.py.encresp1.1794597149` | 16,765 | `9a4ec6551ce349e26c62563756fdbf587d1cd315619f64bb0bfc2ca8d3b87c50` |
| `bridge_tools/tools/account_auth_probe.py.exp_rs0.1794596415` | 11,829 | `51ba2e7676a7edb2419a77137b37da1908ade79a4aab355b12a9e1e36a01a0f7` |
| `bridge_tools/tools/account_auth_probe.py.experror.1794596553` | 12,260 | `97552ac392e8d38f3ed207bf047cd29aaef7fe06c6a6945671d39967e9966aba` |
| `bridge_tools/tools/account_auth_probe.py.fieldpatch.1794599230` | 18,819 | `e629a494ff89dbff4853558e09b02fe0cea8807583bb165e4c26cc520b442326` |
| `bridge_tools/tools/account_auth_probe.py.fix2.pre.20261117-024747` | 136,862 | `199498b506942375b4b0259f8e35c52353b7785a565cc17dfadc6e384c94f378` |
| `bridge_tools/tools/account_auth_probe.py.fix2pre.183713` | 146,224 | `6b8883f603b18fe4a9185c789ff7d3161b04c3058fdc8592850299ffff4c1388` |
| `bridge_tools/tools/account_auth_probe.py.fix3pre.183916` | 146,259 | `b301eddfcfcc43a119c01fd693361078b4896f8f6a1b425465338d6ffb468cd3` |
| `bridge_tools/tools/account_auth_probe.py.fix5bpre.185539` | 146,479 | `4e572579be97cb65c92523b2e8abf2fb20afe28abfbaa41f6c80f838f12cf5fd` |
| `bridge_tools/tools/account_auth_probe.py.fix5bpreb.185600` | 146,479 | `4e572579be97cb65c92523b2e8abf2fb20afe28abfbaa41f6c80f838f12cf5fd` |
| `bridge_tools/tools/account_auth_probe.py.fix5pre.185409` | 146,479 | `4e572579be97cb65c92523b2e8abf2fb20afe28abfbaa41f6c80f838f12cf5fd` |
| `bridge_tools/tools/account_auth_probe.py.fix6pre.190003` | 146,479 | `4e572579be97cb65c92523b2e8abf2fb20afe28abfbaa41f6c80f838f12cf5fd` |
| `bridge_tools/tools/account_auth_probe.py.fourkeys.1794599499` | 20,976 | `d8f51de8081a41dd73d36927619a7418b973f2bc312cb287d895aca039c17717` |
| `bridge_tools/tools/account_auth_probe.py.hash.1794599435` | 20,457 | `abbe54b94bc44851f1eb80174332e387e94b8c45af66ec9426e0fa861b5bf3fb` |
| `bridge_tools/tools/account_auth_probe.py.http200.1794599073` | 18,746 | `b82fec473091338786385a92409c3b3ef918a1dd2b350877964982c29a7e0205` |
| `bridge_tools/tools/account_auth_probe.py.innermin.1794600929` | 25,646 | `73c6f9ef9450326718f69bc5f8a42a6c64bfccc36afd0a8aa1edbfff59814635` |
| `bridge_tools/tools/account_auth_probe.py.namefix.pre.20261117-183500` | 141,034 | `d76079e8a9c201981166f1668d73ec0b7cfb0c1725735cd45340a8adcf394697` |
| `bridge_tools/tools/account_auth_probe.py.p3.bak.20261117-012355` | 90,553 | `8620bcf7b960ac68ea0127ceecfc0f79217cb602f89c994fe05802b6f7d72e7e` |
| `bridge_tools/tools/account_auth_probe.py.p3.pre.20261117-012349` | 90,553 | `8620bcf7b960ac68ea0127ceecfc0f79217cb602f89c994fe05802b6f7d72e7e` |
| `bridge_tools/tools/account_auth_probe.py.plainmode.1794595746` | 3,042 | `3a6cfe0fac372a03eb3cf5315fc91096cfc24620d839778346ec1f3c74798957` |
| `bridge_tools/tools/account_auth_probe.py.pre_1017.20261116_062952` | 73,413 | `a19ece08d3ba9897fa8d990108f86e7f1b3dc202bb91993cf7dde0ad6f75a97c` |
| `bridge_tools/tools/account_auth_probe.py.pre_24000soc.1794640032` | 46,725 | `69b74e022d1ff77beca9d50fa97b495e781e97a200230072a0ef6fce141fc086` |
| `bridge_tools/tools/account_auth_probe.py.pre_24000soc.1794640045` | 46,725 | `69b74e022d1ff77beca9d50fa97b495e781e97a200230072a0ef6fce141fc086` |
| `bridge_tools/tools/account_auth_probe.py.pre_24000ticks.1794639691` | 46,536 | `a3125c20be91c93ae2e7469b79cd9344243d6ad192acb8b991052026f4ccd337` |
| `bridge_tools/tools/account_auth_probe.py.pre_24v3.20261116_060707` | 53,994 | `56307054852ccf21692f2af9fd9b8ea15578900c9738994535042451bb6d9a00` |
| `bridge_tools/tools/account_auth_probe.py.pre_90004.1794638663` | 45,438 | `e746b4a657fdba11d246f80a74e9c38e3eeff127587f6c8ae89c97d1852665eb` |
| `bridge_tools/tools/account_auth_probe.py.pre_academy.1794607217` | 43,056 | `b04c19ea87b1c7f5ffea73b1f0342eb43c6d1aca4e4aaaed4244e3e8ac30d0da` |
| `bridge_tools/tools/account_auth_probe.py.pre_academy_e1.1794641307` | 49,973 | `e552625c28622a3e2bab29fa0a16812b1d06d96b775efd9d0e667d50ecc326f9` |
| `bridge_tools/tools/account_auth_probe.py.pre_academy_e2.1794641892` | 50,694 | `949133ae4421df603e77b89e514d07e2d8eda8f60ab0d359c22bd4202fc77352` |
| `bridge_tools/tools/account_auth_probe.py.pre_academy_e2.1794641898` | 50,694 | `949133ae4421df603e77b89e514d07e2d8eda8f60ab0d359c22bd4202fc77352` |
| `bridge_tools/tools/account_auth_probe.py.pre_accountsvc.1794640744` | 46,758 | `517b9503947e28667a94d20210c5b4e9ee23ae3bfcc7609afb5735253371c540` |
| `bridge_tools/tools/account_auth_probe.py.pre_acctdb.1794638325` | 45,438 | `e746b4a657fdba11d246f80a74e9c38e3eeff127587f6c8ae89c97d1852665eb` |
| `bridge_tools/tools/account_auth_probe.py.pre_callname.1794605967` | 38,656 | `a811ec0d65f99c2c6940638dfd4d7d6f0ad2c59c763546316bd9884c2aea4d61` |
| `bridge_tools/tools/account_auth_probe.py.pre_callname.1794605980` | 38,656 | `a811ec0d65f99c2c6940638dfd4d7d6f0ad2c59c763546316bd9884c2aea4d61` |
| `bridge_tools/tools/account_auth_probe.py.pre_directenv.1794605546` | 37,774 | `7ffec77e5ecd773bec53c88ce677d3d0bedff0f35ec3eb20f22ea3f0fb5dd187` |
| `bridge_tools/tools/account_auth_probe.py.pre_generic.1794606300` | 40,215 | `97d243b87f04bf99b5231899bc187d8d700e897a2f594dc0ade46443248ed99c` |
| `bridge_tools/tools/account_auth_probe.py.pre_knownother.1794606631` | 42,243 | `e23866aa525fa700ced989bb3ed258003a6e86d49e009fcd8842c92e1ce3a705` |
| `bridge_tools/tools/account_auth_probe.py.pre_L0.1794608299` | 44,809 | `e7ed3ff54543c557eaff4df9f9f6c2f3ec83a95faed0b6844ddafea791d63693` |
| `bridge_tools/tools/account_auth_probe.py.pre_nick.1794605244` | 36,601 | `1c9359e692406090b9e5f153029b261fd17d627b4d1a6940b82e677289c9cc6b` |
| `bridge_tools/tools/account_auth_probe.py.pre_P00.1794608590` | 45,413 | `6c8ca008902874c1c42d4c4b2412e9a53d3570b1f1cc167981379cc96a7f993e` |
| `bridge_tools/tools/account_auth_probe.py.pre_plusfix.1794606925` | 42,472 | `d2657350b307b12b861b6166975d8dad244048d730faf5b3d2c01ab25b8cc222` |
| `bridge_tools/tools/account_auth_probe.py.pre_sessionkey.1794607675` | 44,809 | `e7ed3ff54543c557eaff4df9f9f6c2f3ec83a95faed0b6844ddafea791d63693` |
| `bridge_tools/tools/account_auth_probe.py.pre_simple.20261116_070018` | 76,066 | `9d0ecc7848eb033957c2e67051cb86a2efb8afd9bf0263d4f2c3d7bc065a31e7` |
| `bridge_tools/tools/account_auth_probe.py.pre_sk2.1794607966` | 44,809 | `e7ed3ff54543c557eaff4df9f9f6c2f3ec83a95faed0b6844ddafea791d63693` |
| `bridge_tools/tools/account_auth_probe.py.pre_stateapi.1794641269` | 49,973 | `e552625c28622a3e2bab29fa0a16812b1d06d96b775efd9d0e667d50ecc326f9` |
| `bridge_tools/tools/account_auth_probe.py.pre_wire_acctsvc.1794640825` | 46,758 | `517b9503947e28667a94d20210c5b4e9ee23ae3bfcc7609afb5735253371c540` |
| `bridge_tools/tools/account_auth_probe.py.probemode.1794600882` | 25,080 | `7187928fc6b163f7e5b3a45c04fff5e29a2ac94326104960e4a6ab65e2f3b71b` |
| `bridge_tools/tools/account_auth_probe.py.pwrap.1794600031` | 22,830 | `aeef663a5ae15386ce92c3667773b76f208a3bcdf2c95f670318fc12ed2141b3` |
| `bridge_tools/tools/account_auth_probe.py.r01.1794601878` | 30,071 | `b2d6d07e46f6ec4c1d2cbcad1ef0321924cfed52fc9f8d9c0a74ffd6ba1e4fec` |
| `bridge_tools/tools/account_auth_probe.py.realcap.1794601220` | 28,393 | `cdbe39107b708f044a986bea173ab88447399171eff3c8eb3fe56c89cf1b3ca2` |
| `bridge_tools/tools/account_auth_probe.py.relay.bak.20261117-015320` | 103,868 | `c67871a26926675e3c534cfd6972924b4bea73bda582f685de5aac3374301b07` |
| `bridge_tools/tools/account_auth_probe.py.relay.pre.20261117-015314` | 103,868 | `c67871a26926675e3c534cfd6972924b4bea73bda582f685de5aac3374301b07` |
| `bridge_tools/tools/account_auth_probe.py.relay1017.bak.201445` | 150,544 | `3b8011e21901efce21b91926dc03659d9c8261c6011e744a149ecefa9f8ae3cd` |
| `bridge_tools/tools/account_auth_probe.py.relay2.bak.20261117-020650` | 115,879 | `f75690d66c0c037bedaa125a1d52b3c785c571be04ff71bfbe93c6426611b7e2` |
| `bridge_tools/tools/account_auth_probe.py.relay2.pre.20261117-020644` | 115,879 | `f75690d66c0c037bedaa125a1d52b3c785c571be04ff71bfbe93c6426611b7e2` |
| `bridge_tools/tools/account_auth_probe.py.reqid.1794601181` | 27,354 | `ce109dec54eb9fe6e018a4cb28a19ff0ade964029b2a1924c389642797b6863d` |
| `bridge_tools/tools/account_auth_probe.py.respstub.1794596657` | 13,811 | `e37135ad9ce40f3f2dd6ece9b238448cc09af982a1cc97336ad7d23595b8be6a` |
| `bridge_tools/tools/account_auth_probe.py.rlf.bak.20261117-023404` | 128,277 | `0e853831d3342f50c0d428b940614bdcb16e73370f5a106371f5f3bf8c66ceab` |
| `bridge_tools/tools/account_auth_probe.py.rlf2.bak.20261117-024752` | 136,862 | `199498b506942375b4b0259f8e35c52353b7785a565cc17dfadc6e384c94f378` |
| `bridge_tools/tools/account_auth_probe.py.rlfix.pre.20261117-023359` | 128,277 | `0e853831d3342f50c0d428b940614bdcb16e73370f5a106371f5f3bf8c66ceab` |
| `bridge_tools/tools/account_auth_probe.py.rs1.1794596480` | 12,221 | `e812e09112ba202e465224ecec77ade3f0d7f9e83549b6d199ebe2d5ffcb33e2` |
| `bridge_tools/tools/account_auth_probe.py.simple.bak.20261116-070018` | 76,066 | `9d0ecc7848eb033957c2e67051cb86a2efb8afd9bf0263d4f2c3d7bc065a31e7` |
| `bridge_tools/tools/account_auth_probe.py.spec26.1794601009` | 26,657 | `a033f002e1f76f6dd2ec5ebec2b78442bd71cb250f4b88a12f185a0f9e081266` |
| `bridge_tools/tools/account_auth_probe.py.status.1794597469` | 16,832 | `0e12f002018f8c9eb8bd638b9290c62e8fa8840ee13aab8df1b543722ef7afba` |
| `bridge_tools/tools/account_auth_probe.py.ten.1794599687` | 22,585 | `0c4ef832263d4632374b01bf353d3ec50d9090d8befa28c43ba7f0ee29d1a47a` |
| `bridge_tools/tools/account_auth_probe.py.types.1794599717` | 22,828 | `451fade92a1aa3096c8650596ec8c32fdc5f3884570caa4575fc41e5c00c9381` |
| `bridge_tools/tools/account_auth_probe.py.v1.1794594998` | 1,579 | `c337fb720164c44a2ebf9710d0de300840c56f0189933d97581fb0c9ee6efa88` |
| `bridge_tools/tools/account_auth_probe.py.v2.1794595331` | 2,633 | `6987cac56bffd6b6aad642799480fcc6ad18b6609d614f6532cd16d4042d9be7` |
| `bridge_tools/tools/account_auth_probe.py.v5.1794596872` | 15,321 | `7aafb3ae67d52f49664a1db39efe2ac6ad5bdf2b78dc33c654e23a8af3bfb46b` |
| `bridge_tools/tools/account_auth_probe.py.WORKING_a_proto_int.1794605023` | 36,601 | `1c9359e692406090b9e5f153029b261fd17d627b4d1a6940b82e677289c9cc6b` |
| `bridge_tools/tools/account_auth_probe.py.WORKING_a_proto_int.1794605032` | 36,601 | `1c9359e692406090b9e5f153029b261fd17d627b4d1a6940b82e677289c9cc6b` |
| `bridge_tools/tools/account_auth_probe.py.WORKING_plus_emptyfallback.1794605244` | 36,601 | `1c9359e692406090b9e5f153029b261fd17d627b4d1a6940b82e677289c9cc6b` |
| `bridge_tools/tools/account_service.py` | 108,745 | `7e2b3c13baffee31fb535383b7d8d0e22ff2b51ea4a22b808165b14493482ff5` |
| `bridge_tools/tools/account_template.json` | 12,187 | `d9d47416facea8cf719b3181293856539dd30b1a5e72ebc598068e65667fcb3d` |
| `bridge_tools/tools/aes_pure.py` | 7,615 | `713dd2aa345fa7f8978c882bed59683a22476d3dc18183622e21164ade9ef5bc` |
| `bridge_tools/tools/cn_1005.txt` | 2 | `4355a46b19d348dc2f57c046f8ef63d4538ebb936000f3c9ee954a27460dd865` |
| `bridge_tools/tools/cn_26000.txt` | 2 | `4355a46b19d348dc2f57c046f8ef63d4538ebb936000f3c9ee954a27460dd865` |
| `bridge_tools/tools/cn_4000.txt` | 1 | `5feceb66ffc86f38d952786c6d696c79c2dbc239dd4e91b46729d73a27fb57e9` |
| `bridge_tools/tools/cn_bridge.py` | 10,318 | `a4500c0d6922177c9a985e3b794abe4893ed1e28d4c0eb82624bf41abc9bb760` |
| `bridge_tools/tools/cn_cipher.py` | 6,443 | `9ed3d1806a70b2b319a51e1ba71677955b1877ff560dfa63dcf8bde0aed1be04` |
| `bridge_tools/tools/cn_inner.py` | 4,305 | `2828f1e9733e5132f33eb85e30244d6be59e5446726768194e447031181eada2` |
| `bridge_tools/tools/cn_inner.py.WORKING.1794605023` | 4,305 | `2828f1e9733e5132f33eb85e30244d6be59e5446726768194e447031181eada2` |
| `bridge_tools/tools/cn_inner.py.WORKING.1794605032` | 4,305 | `2828f1e9733e5132f33eb85e30244d6be59e5446726768194e447031181eada2` |
| `bridge_tools/tools/cn_inner27.py` | 5,342 | `7793882d40231f588045862ee8b80f3c1f89e3202d2fda1d7f345150f3257208` |
| `bridge_tools/tools/cn_inner27.py.bak.20261117-182233` | 5,395 | `d9d3e807aa4324384647ffbc20525a8cb8bdde9c75520e4d85d0c0165b0155d9` |
| `bridge_tools/tools/cn_inner27.py.pre_accountsvc.1794640744` | 5,395 | `d9d3e807aa4324384647ffbc20525a8cb8bdde9c75520e4d85d0c0165b0155d9` |
| `bridge_tools/tools/cn_inner27.py.pre_acctdb.1794638325` | 4,438 | `91ae30f7cffae376935fc018e528a6ca392f6bc2dbf3187ebaf9836a762db45d` |
| `bridge_tools/tools/cn_inner27.py.pre_P00.1794608590` | 4,420 | `df28a496a0746fdfcea77f12bf2570a0d650017cfcc9ee6527cd6219b69336db` |
| `bridge_tools/tools/cn_inner27.py.pre_sessionkey.1794607675` | 3,638 | `5ab723d628d1d822ab7e99b6cf9cb751ef47598e78e48cbc71e0e1488ed5588b` |
| `bridge_tools/tools/cn_inner27.py.pre_sk2.1794607966` | 3,638 | `5ab723d628d1d822ab7e99b6cf9cb751ef47598e78e48cbc71e0e1488ed5588b` |
| `bridge_tools/tools/cn_inner27.py.WORKING.1794605023` | 3,638 | `5ab723d628d1d822ab7e99b6cf9cb751ef47598e78e48cbc71e0e1488ed5588b` |
| `bridge_tools/tools/cn_inner27.py.WORKING.1794605032` | 3,638 | `5ab723d628d1d822ab7e99b6cf9cb751ef47598e78e48cbc71e0e1488ed5588b` |
| `bridge_tools/tools/cn_iv_derive.py` | 2,455 | `569729cc3af50a695323f94b6a6a91736fe0d20fd10c33539e6cf823b5cd58dd` |
| `bridge_tools/tools/cn_nick.py` | 2,433 | `4c3466afdec21f5fe0a23169d517dff4ab26a5bcbf0733363625bc65955583b1` |
| `bridge_tools/tools/cn_nick.py.pre_accountsvc.1794640744` | 2,433 | `4c3466afdec21f5fe0a23169d517dff4ab26a5bcbf0733363625bc65955583b1` |
| `bridge_tools/tools/cn_nick.py.pre_callname.1794605967` | 2,225 | `85fb1aed0d27a483afe51caeb049b7f55b6e5cbc180c34760f1faf0d74824599` |
| `bridge_tools/tools/cn_nick.py.pre_callname.1794605980` | 2,433 | `4c3466afdec21f5fe0a23169d517dff4ab26a5bcbf0733363625bc65955583b1` |
| `bridge_tools/tools/cn_real_capture.py` | 6,430 | `4d104e05a1c6b8d780682662deecda2d4bb7958eeb91a5c90d120f4d7ae6ee78` |
| `bridge_tools/tools/cn_resp_crack.py` | 4,023 | `ff443787bb5e5e1e4819657470ce2c2dcd6d6ec301503c7100ddbca24e5a3d40` |
| `bridge_tools/tools/cn_state_real.py` | 2,549 | `fa8a5ecdcadf7a3466ed92a806811a1b6d7238ccd1f3e0490d36c7325826dfd3` |
| `bridge_tools/tools/cn_wire.py` | 9,778 | `f2dc6ce1e29cf7b5128a6a4ccdf5f923038ecc5e2a73b77ac17b0c19ed5c1441` |
| `bridge_tools/tools/cn_wire.py.bak.20261116_053957` | 6,368 | `3a5cb4be537c866e95b4f01d61bc032efeda9809d23288043ed2d1f0c661269a` |
| `bridge_tools/tools/cn_wire.py.bak.20261116_053957.meta.json` | 739 | `6da30c402d2920d20c9dd09cc00d6ba5e86bcdde88d8a992f66a4cfb6ea30b82` |
| `bridge_tools/tools/cn_wire.py.e3.1794603141` | 5,494 | `51b3e674ab9fa26aa8c79511fbac3c6af79d6220255afde29a8c44d1902b508f` |
| `bridge_tools/tools/cn_wire.py.pre_accountsvc.1794640744` | 6,368 | `3a5cb4be537c866e95b4f01d61bc032efeda9809d23288043ed2d1f0c661269a` |
| `bridge_tools/tools/cn_wire.py.pre_rid.20261116_053957` | 6,368 | `3a5cb4be537c866e95b4f01d61bc032efeda9809d23288043ed2d1f0c661269a` |
| `bridge_tools/tools/cn_wire.py.WORKING.1794605023` | 6,368 | `3a5cb4be537c866e95b4f01d61bc032efeda9809d23288043ed2d1f0c661269a` |
| `bridge_tools/tools/cn_wire.py.WORKING.1794605032` | 6,368 | `3a5cb4be537c866e95b4f01d61bc032efeda9809d23288043ed2d1f0c661269a` |
| `bridge_tools/tools/dto90004.py` | 8,891 | `bfd07f765709e9d2c30f5acab10b33021e61676e4f0d98eb1dff56a8fd6fe654` |
| `bridge_tools/tools/fix2_remove_1005.py` | 1,511 | `d29b0d43fe8ebaef784725e3b1f4b388ed843e976c1219f87639ec694e50f116` |
| `bridge_tools/tools/fix3_envelope.py` | 2,077 | `7dd0dd6d175eb498621dabaf400629d4f8874e7a71e4cb38ea861ccce75cb9fc` |
| `bridge_tools/tools/fix5_login_sync.py` | 2,376 | `86d664080995681ffdd575f43e77bb4c8fb80143b00707ed36ad4c2b81e17ba6` |
| `bridge_tools/tools/fix5b_protonum.py` | 5,777 | `3e3397f9161b9834c16a2fa9e28dbc90b858ed01a84fcc8fc0df60e0cc3d7584` |
| `bridge_tools/tools/fix6_nametoken.py` | 3,869 | `4d03ae76bcb2a965c08dc563f66fc3656261206058926a402d0e4bc279276bd8` |
| `bridge_tools/tools/fix_1017_relay.py` | 4,324 | `f43a2acec14e8460fc75f3383c9862098c35f279a38c1a73c82f4652e265c738` |
| `bridge_tools/tools/fix_1017_relay2.py` | 1,851 | `ea40e10cf4d5150f4d6758c18a74816f66ade3a169332909ece0123ea4ebaf7f` |
| `bridge_tools/tools/fix_1017_timeout.py` | 1,588 | `9a3dc0752bb5bdf8865dd0834670e28867f6f34d680d6a6c396844eea2cc531b` |
| `bridge_tools/tools/fix_batch1.py` | 6,576 | `851b248e4802c384b12ebe15d89530f3eac148715e8754f5e5480976859d3381` |
| `bridge_tools/tools/fix_billing_block.py` | 3,672 | `e4c5d189729ffb1e5deb387510a1464398eadfff788e53a18a5dad10fdbb8ba8` |
| `bridge_tools/tools/fix_dedup_relaypath.py` | 3,445 | `66e3de0f149ce4e94ab758fd1897389254b31b4ef36fb629008a894eb352ca4b` |
| `bridge_tools/tools/fix_name_unknown.py` | 7,317 | `83cf598b245e5bd681cde6fab1a4c168d791cbe283ca101af052c8fefde8f773` |
| `bridge_tools/tools/gate.sh` | 913 | `100bfd2457c5ba8cffb77a9cd91f5ce0a26f99c89dce0fc6674722a9bbcf889e` |
| `bridge_tools/tools/gen1017.py` | 62,723 | `abd9d9465969365890e7e9b8825f77fa7a4407719371006a2fe7cafdf9818d0c` |
| `bridge_tools/tools/gen3.py` | 4,099 | `55a6cd57abed48645c958b11ebac0cbd0aa43f67846f4a738e2c8d1e9008f073` |
| `bridge_tools/tools/gen8000.py` | 43,589 | `9432e4ee1b5e1ba527516638d467181f074145845bd844889acabdd46c867598` |
| `bridge_tools/tools/gen8000.py.pre_flatpath.20261116_064112` | 41,437 | `3159d3d515c0080cfed6a103efe366d0e84938482cad23c64e8c8b57e2c7e3fb` |
| `bridge_tools/tools/gen90004.py` | 4,415 | `67128f8d541315d9e1fc467571ecf4f054d71d16f420d1410095e90affba1492` |
| `bridge_tools/tools/gen90004.py.pre_flatpath.20261116_064112` | 4,140 | `c1ca45ca8feba2625f9511b36db3fdf0191a00df2c97b810e061fc615d2dc236` |
| `bridge_tools/tools/gen_common.py` | 17,773 | `1998eb226194ec3893e1fc4b8e035a8d64fa6c583302ca147b0f15b13d577d92` |
| `bridge_tools/tools/gen_common.py.pre_flatpath.20261116_064112` | 15,910 | `847c5f268cc899ed1d07b43adee2c482483469e46215e29fe6a97b6949e4fbf7` |
| `bridge_tools/tools/gen_simple.py` | 17,315 | `93461a082c043af5b6f9d7d4377b91bf64f48af75b12b3b08ff7cd75c8b3d8a1` |
| `bridge_tools/tools/gen_simple.py.pre_flatpath.20261116_064112` | 15,227 | `57e3a524e9a1716adfa8e76edf3e57966cf9c911ab3948a4ec3f8e3eca46f286` |
| `bridge_tools/tools/gwstate_probe.py` | 1,619 | `f3033fdf788d3388bc664fe5c2875b34133fd8b3dbf5f482e1fb3c22fc4c7ad6` |
| `bridge_tools/tools/initial_state_rules.json` | 42,889 | `81e3790e094142fb7a1cc5fd0d533c7a801e2b5c731911aa2629e7ed855d4cb3` |
| `bridge_tools/tools/official_auth_probe.py` | 9,385 | `34b5b4cdceee8c67a28f0839f2a347da4ad117f647d905abdd1cd48566635e7d` |
| `bridge_tools/tools/official_probe2.py` | 6,582 | `5729269f64e19327c9fe28b7f2f1f641ea207c029319a0b607b97d5c06720396` |
| `bridge_tools/tools/official_replay.py` | 3,431 | `8816f1c61a07311823026ebdb0960828bbf4cc3e1a02c3dc8bbbf38c20d2f9df` |
| `bridge_tools/tools/official_spec.json` | 958,494 | `028430a07f173211dbe69018d1201cd007f4838b136d6210f81195957f9afb1b` |
| `bridge_tools/tools/patch_1017.py` | 32,071 | `b5eb6d971e15d50110d82f5dbd672158c07fd50d89bf1a2ffa3a5b26317dcca4` |
| `bridge_tools/tools/patch_3.py` | 63,822 | `26a3b944fc976ff7b8f3317b2cc715b9126662615c0f259b6c5ad4f00cd197cb` |
| `bridge_tools/tools/patch_8000.py` | 42,964 | `045c28d9f4b5846971fa15e07bd3869b4c49a11970af59b0faafe3a096b86d15` |
| `bridge_tools/tools/patch_90004.py` | 30,946 | `c94bae46d6d052945b16446e4f5a35a9cdaf8e3dae896200ece6be5dca4589cf` |
| `bridge_tools/tools/patch_relay.py` | 54,362 | `bfe8ccdd265b1767d9a35e50536c3a4d104c1b480d8a5ba0bd9094e22e41500d` |
| `bridge_tools/tools/patch_relay2.py` | 67,807 | `926a391a42ebd115cb4b1a4d060dd616cd19f42d5a00ddaba2828fedc7943d40` |
| `bridge_tools/tools/patch_relay_fix.py` | 44,031 | `71e6fa3f85ec5059e13ce5ac66b42e2125d6de86480080bf250006c1fa22ad30` |
| `bridge_tools/tools/patch_relay_fix2.py` | 43,479 | `a6eca6a468a7673d27acc88306fd1b95bfeec6253f9280eb9ce849041d089ca2` |
| `bridge_tools/tools/patch_simple.py` | 26,608 | `032e94dde3ea7d2e4a4024fea82649ee0c01975598290610d8a5428f8b29d283` |
| `bridge_tools/tools/protocol_names.txt` | 2,434 | `c6981dced6126156e0cd5ffc3112d0de0cf4657e41bc559859a02e6e4aea78c6` |
| `bridge_tools/tools/schema_sqlite.sql` | 8,766 | `73553712244d6beaee4e0648513770c3f9338b4f34819dc9f8a2a25d7c565748` |
| `bridge_tools/tools/set_gw_dto.py` | 4,397 | `18c4c17a147cc6d90c38e6aede2e7c0c89b8ed4bd4d8ccd7d444687ce0ec93f6` |
| `bridge_tools/tools/shittim_name_tokens.json` | 27,598 | `28ebf45914bfbe13693a57b83e90da1296866540338180fc6b48df19413a0b35` |
| `bridge_tools/tools/shittim_protocol_map.json` | 15,956 | `46cac9aa1544fbf226387a0b18f4a8e09ac03e89182d35139ce8677094e2fb26` |
| `bridge_tools/tools/simple_payload.py` | 13,099 | `871a78b7e049c8e95056013a3327ba90fb53b7c7a66552d66cec2b4ca31619a1` |
| `bridge_tools/tools/spec_check.py` | 14,969 | `72884060dbd4c3e35a452c63530fbb55915f5de89eea9987118280d5cbd58957` |
| `bridge_tools/tools/specgen.py` | 22,794 | `a268f4a1c01994e7520e2cd138dcf2a5f1b885e6e6e1a1c00d70348b82fa173c` |

### `bridge_tools/tools/dto_extra/` — 2 文件 / 13,238 B

| 相对路径（zip 内） | 字节 | sha256 |
|---|---:|---|
| `bridge_tools/tools/dto_extra/proto3_networktime.json` | 5,536 | `a2402fca24d9919346d5babf015319a7e8bb1eed8da3d228ddee3c97fcb67070` |
| `bridge_tools/tools/dto_extra/proto90004_management.json` | 7,702 | `ea86d0d81f1a90628bb01d561b48d26b7121040008b0db17e87ddad8e7850f53` |

### `bridge_tools/tools/official_decoded_201/` — 2 文件 / 1,783 B

| 相对路径（zip 内） | 字节 | sha256 |
|---|---:|---|
| `bridge_tools/tools/official_decoded_201/04_3_api_networktime_sync.request.json` | 797 | `3f08e3b97774280ac6742f2bfdf4a0e8aa7771fa38762655ad3295032bbf1452` |
| `bridge_tools/tools/official_decoded_201/04_3_api_networktime_sync.response.json` | 986 | `59bdde67b452012a8e9ebea1529b568c36fde9cfcf3d9797734dceca5c31a2f0` |

### `client/apk_patch/` — 2 文件 / 39,172 B

| 相对路径（zip 内） | 字节 | sha256 |
|---|---:|---|
| `client/apk_patch/BASELINE_MANIFEST.json` | 3,281 | `00a45e14b2409fb20a0ce16b65538dce9819a2c683b8b17b72cebdfcaf15c8f7` |
| `client/apk_patch/STEP1_REPORT.md` | 35,891 | `c7bbbf39eacaca8ad852fcfe8f9b45b32938a706935d675089cfc3f510a9f0d3` |

### `client/apk_patch/patched/` — 4 文件 / 115,419 B

| 相对路径（zip 内） | 字节 | sha256 |
|---|---:|---|
| `client/apk_patch/patched/CommonUtil.smali` | 31,612 | `edcb7741639ce84fb50409250c64b4eb0971ec1f786d34dadeaead723864c187` |
| `client/apk_patch/patched/DefaultMobileLoginFragment.smali` | 58,970 | `c505729dde6f64476c4862e67a8bb9316dc9584a425a5c725222f271092a55d1` |
| `client/apk_patch/patched/extend_edit_login_layout.xml` | 9,707 | `b2491abe8ed9f1f84c1385a3708e649ac2a308dcc6aae3e93f52f8773203c65f` |
| `client/apk_patch/patched/HttpCallBack.smali` | 15,130 | `cc9db7e86c512fac4e1028ee99588d8f7efc123f5b2572072e95af1e73d28e9e` |

### `client/apk_patch/scripts/` — 45 文件 / 101,433 B

| 相对路径（zip 内） | 字节 | sha256 |
|---|---:|---|
| `client/apk_patch/scripts/compare0.sh` | 2,680 | `277c617a42df3128552390e08ec494c8675608f7ffee02193efcc26a5cbfd94f` |
| `client/apk_patch/scripts/dump_smali.sh` | 1,211 | `7281035cfc13286f9585dc06c80b3b3069ac8755058423067f09d05d8b5f03b9` |
| `client/apk_patch/scripts/exp_layout.sh` | 3,381 | `edfca11cd5aa290aa5fb64affb6f3a763cff446140270cc0977732b9a9563eac` |
| `client/apk_patch/scripts/install.log` | 18,668 | `186d9047bc99844859529fe80bcbf4461356fb30eb42bbedc7e9469f712975dc` |
| `client/apk_patch/scripts/install.sh` | 1,090 | `483216f8e33f1529a09ab75ab789a349b7820e3f4ba81cc9cac5a1d97b1d1036` |
| `client/apk_patch/scripts/install2.sh` | 1,262 | `dc48976ab3fa139f1a784e66ef92ee48a4e7554214e8f1c2aa806b19b3707c1f` |
| `client/apk_patch/scripts/inventory.py` | 2,105 | `f2a250521cfe2ea6306c9a7f9956136603bcfb3a3a6e254e2a8eb3122f0a7210` |
| `client/apk_patch/scripts/make_slim.py` | 1,720 | `2ba7dae8eac934f30e10f2636da3a9a6c20d89105da4496a104f553ed7d78700` |
| `client/apk_patch/scripts/manifest.py` | 2,545 | `b69ef60fc274a2fdc7ee4057cf5d0ae41a078b977e8f217c15a236ac743cb990` |
| `client/apk_patch/scripts/peek.py` | 389 | `911d2d6929ec528a38e386daba8fcf604cfeb439b2b167707788788e59a84cee` |
| `client/apk_patch/scripts/probe.sh` | 1,345 | `37d6d3f23b36880c7eeb0de07d64b5c9559ea0a6bee6f9f83d260c28acae7214` |
| `client/apk_patch/scripts/probe_smali.sh` | 2,393 | `cf5eb0a1570ddfed9cdb27c2fe58bd310ded29b02f31b2ef93d22ccf2dbf5da1` |
| `client/apk_patch/scripts/rebuild0.sh` | 1,002 | `1a4671d7671f89e13bd94b733e4a7fbeee433a8309615536777a6c53e8048194` |
| `client/apk_patch/scripts/roundtrip.log` | 3,126 | `0b4ce8243027ddfaccaaeb12e7651f7a7fef40de5308b8948fc1db0b3672efca` |
| `client/apk_patch/scripts/roundtrip.sh` | 1,036 | `2e8c2e5ddd5ec955beba43ccb999852148c3517e11a37b1df6b12fe0027832ae` |
| `client/apk_patch/scripts/s2_align.py` | 1,055 | `d6d6c2fca50922f40b0908a44a9ea3e4dffca55b8b1a3a162e54cb5c7d96c94c` |
| `client/apk_patch/scripts/s2_apkcheck.sh` | 1,891 | `d38dc7be7928756124f30f98c91726e25b79432d755fec2325b579b9948ff254` |
| `client/apk_patch/scripts/s2_collect.sh` | 1,083 | `38f5a4e191d6b1683ed5129849436ea61d3e1f0362519ce9cd0deb50a9683a53` |
| `client/apk_patch/scripts/s2_delta.py` | 1,760 | `0c04f8b91b0a74643ef4963f81add2d59438b9234b5a2c382970305dca4c8b16` |
| `client/apk_patch/scripts/s2_delta2.py` | 1,449 | `79dbc200a5d2684fa675aa664a0a4d80d9d06526a14eb6db6333ed862f8f11b6` |
| `client/apk_patch/scripts/s2_dump_res.sh` | 1,529 | `7328573e45543ba479b1f70dc5887c1680e9da3d7d3b753359d4aeb935bc328f` |
| `client/apk_patch/scripts/s2_dump_res2.sh` | 1,205 | `86f019ea64a28f8b7bbe776ef0189e5b989b16108a6a0b4223cfb1e2df442821` |
| `client/apk_patch/scripts/s2_dump_res3.sh` | 559 | `709d6b394b0b46fa312372f99997ec8003d469808ce80077a85001b2344074c5` |
| `client/apk_patch/scripts/s2_dump_smali1.sh` | 827 | `5acdbc6f81cacdd2cc915b555207df5bd4f2d972cbada9b5c2c3a022b9a5ddfe` |
| `client/apk_patch/scripts/s2_dump_smali2.sh` | 984 | `51d35c507f1dbd56166f7afad085d9306ca1b414bda5b5be6d333e89d52508ee` |
| `client/apk_patch/scripts/s2_dump_smali3.sh` | 679 | `ebda1e2611e5b0c9a722225eadfa487cffc7201b8907889627ffefe391a9f8c7` |
| `client/apk_patch/scripts/s2_dump_smali4.sh` | 1,286 | `cb322ab51d6abc0a1cdeca9fd858e30797acace6ef987f4b95c42e4bceed2b64` |
| `client/apk_patch/scripts/s2_dump_smali5.sh` | 1,041 | `4e6a9794a83a5458cc7616bca00c6e955577b43de664ab84fc281970daf12879` |
| `client/apk_patch/scripts/s2_dump_smali6.sh` | 412 | `de332529ec43e81d54608fb158b190274def1c4bad41ffe361590477e6dac5ab` |
| `client/apk_patch/scripts/s2_final.sh` | 2,525 | `1e653e0ecc2e3d02a47480e0efce6d88af4ec200e5025e837265b73c70c89b4e` |
| `client/apk_patch/scripts/s2_inspect_build.py` | 593 | `c92442346bb2679ae4c0ad708d55b322b54eb1d92a68e400ed7829cdc341250f` |
| `client/apk_patch/scripts/s2_patch.py` | 18,748 | `bf2499ff24437f1169c668cb015591760e5c65296e7747c930181a8f3f53b4fe` |
| `client/apk_patch/scripts/s2_patch.sh` | 124 | `116e3f100c4026e9e8957de64811bd2d917fd8cddd43bc9e8ead4e7ab8f80e5a` |
| `client/apk_patch/scripts/s2_reqcheck.sh` | 1,272 | `4a076e085c2675be8d2a99387a7e2577f79a5e120c8f6751710f1997fe93fd72` |
| `client/apk_patch/scripts/s2_roundtrip.sh` | 1,817 | `ac4900d629481b39bbcaa552218dbaf1bd93c50ea2ac0775d4e2f658648aa510` |
| `client/apk_patch/scripts/s2_rt_classify.sh` | 2,098 | `84033ce58e2ef1b21cfe974378e2f17ed6c68a90bb4902d0cbc7dce1010920ec` |
| `client/apk_patch/scripts/s2_rt_detail.sh` | 863 | `3d9b34f527302a02c331e2f5b7a7d26b93a86a48a39e82fac4f89ccbb91b7608` |
| `client/apk_patch/scripts/s2_v1check.sh` | 1,600 | `18a5d0bc53e41426532f4bdf4b003cfd2e0cbc33c88b3573d59c80f9a6ef1dfd` |
| `client/apk_patch/scripts/s2_verify_axml.sh` | 1,944 | `4c20bd4c15681adfc69dfce2038e32c6ab2c21e85f3f9b58708e22608d95f7b5` |
| `client/apk_patch/scripts/s2_verify_dex.py` | 3,008 | `7e99464ac3dea8c5dd7f66eeba376dee9de500a63314ecce9c3bef3bcd065935` |
| `client/apk_patch/scripts/s2_verify_dex.sh` | 397 | `aaba23b024b6f21941a067c159ebe089c21611cad12998dee67257b2f4dabbbe` |
| `client/apk_patch/scripts/s2_write_mode.py` | 420 | `edf4e8de8e7738bc8a8d0b89aef0c9b085d4fc080785cc4665086011206c21b1` |
| `client/apk_patch/scripts/s2_write_mode2.py` | 658 | `f5a0f93c5488306d40825dd45b2e95f8528242235e5005dc59e3c7aef8dac689` |
| `client/apk_patch/scripts/s2_zipdiff.py` | 4,236 | `d1e5981d74f33c7af805103a72320574c1093e7873c8dbd9016418cf81b30d27` |
| `client/apk_patch/scripts/verify_axml.py` | 1,417 | `af42aaab9295929e86fb3d153662bc6642598aa95abb65dd2ccb7f22cd041016` |

### `client/apk_patch/v2v3/` — 29 文件 / 266,021 B

| 相对路径（zip 内） | 字节 | sha256 |
|---|---:|---|
| `client/apk_patch/v2v3/aapt_diff.txt` | 5,846 | `a171b94f4944f6e1fcfee3124057d71da02470463e60a59ead13f3095fd6349f` |
| `client/apk_patch/v2v3/aapt_dump_new.txt` | 16,317 | `7fa437b1dfeedfda0fc660343e9975de53e4757922b15fd0f84f17ba669f62a5` |
| `client/apk_patch/v2v3/aapt_dump_new_norm.txt` | 16,292 | `4d33378cfd54559e910a4853e952d887a2fdf5788f6aa4a18ab795e0f7292f93` |
| `client/apk_patch/v2v3/aapt_dump_orig.txt` | 14,026 | `2b0d9eb803b16f8e1f479b60a714f2d17ef5560cf378e2ff8ec46107962444fd` |
| `client/apk_patch/v2v3/aapt_dump_orig_norm.txt` | 13,980 | `5511155a41ae000a50fdd6ae45c55cafcf2d4388f55431babaf70b7cbd4b89eb` |
| `client/apk_patch/v2v3/aapt_new.txt` | 16,317 | `7fa437b1dfeedfda0fc660343e9975de53e4757922b15fd0f84f17ba669f62a5` |
| `client/apk_patch/v2v3/aapt_orig.txt` | 16,317 | `7fa437b1dfeedfda0fc660343e9975de53e4757922b15fd0f84f17ba669f62a5` |
| `client/apk_patch/v2v3/axml_dump.py` | 8,981 | `ce86b9ade41292d979d5492b1100495cf5b70e7d756596b6dcb5e9e1cdb9341f` |
| `client/apk_patch/v2v3/baseline_sha.txt` | 122 | `6d7e2fb2ebace4938db8eeeb87034e2af7aa84f8e661721fa6ddc6d101e7c7e1` |
| `client/apk_patch/v2v3/cmp_axml.py` | 2,966 | `0469d3469fd09bd6f00a5dd327646d316ce1f7f09ad9abedbf78f56fdb76adfa` |
| `client/apk_patch/v2v3/dex_probe.py` | 2,268 | `fa2f0721e77643ef377d31c98176a292971fa8a551e313f8d445611788108c80` |
| `client/apk_patch/v2v3/final_check.py` | 3,747 | `d5d3740f29b5ff3bcfc9a531502ccbc8a075af25962d2a6d84fc0f529ff22918` |
| `client/apk_patch/v2v3/layout_xml.diff` | 7,757 | `23baa3b6cfcff751c5868babc101cf49f77a8c60e138aeab9c97efb1c7ed7e62` |
| `client/apk_patch/v2v3/make_layout.py` | 7,128 | `88ece85c9b3179496e3e846934114b9d2affa105164081681e18bae95b45fdef` |
| `client/apk_patch/v2v3/make_report.py` | 21,412 | `d95075b6e02345f811c9638dc73a88da66709e151e62e70477e4f653f46c7c1e` |
| `client/apk_patch/v2v3/own_diff.txt` | 8,833 | `184f1eeccdd1ac34ce88b0230c0f8c59ca34fc8ae834484062b8dd65466c7680` |
| `client/apk_patch/v2v3/own_dump_new.txt` | 24,083 | `8b168f446311a0d9eefe5a95dc0f6bf784479535549afb8a6fa8a0b36fdfb30f` |
| `client/apk_patch/v2v3/own_dump_orig.txt` | 20,830 | `ab23b57070d49f6623b18cf5d53a7494ec32c0c7d9d27fcf20bf7dad6349cb1d` |
| `client/apk_patch/v2v3/patch_dex.py` | 5,355 | `a95f43b01be0d40cd6f157bb609c8698875c4ac776f38a3be6bb68b230ba93b6` |
| `client/apk_patch/v2v3/res_Q9_new.axml` | 8,284 | `8907d9b258c918c057046ff267d86f1128a13153ece8e32bcfec9ec70a67559c` |
| `client/apk_patch/v2v3/res_Q9_orig.axml` | 7,292 | `cc12543bbb5b977ebc229dfae334d9f10f9514b02f71b25d8e61b72d9a043dfd` |
| `client/apk_patch/v2v3/root_order.py` | 2,213 | `197e12c297794535d07450b09fef55e7b90e3990129115eb42d86ba7b2987533` |
| `client/apk_patch/v2v3/selftest.py` | 9,113 | `5d747c63c9ecdecc273d2afbcad82019e2221586d6d48aa73fd3a4086e4d1dd2` |
| `client/apk_patch/v2v3/selftest_console.txt` | 7,495 | `482431c32009e9f598604d94789d9d31968c5ad9e675fd481df68e555d021316` |
| `client/apk_patch/v2v3/selftest_out.txt` | 7,381 | `fe6d8ba08b4ca27d6e34d452011ac796233d0869fab993ed94729a4cfc489ba8` |
| `client/apk_patch/v2v3/smali_diff.txt` | 387 | `8890db14521a501c1cf2c4930888d7e38a967919e0211376e9cacb5c277cc4d2` |
| `client/apk_patch/v2v3/smali_proof.py` | 2,592 | `2700f0f3f269e5a952ceb00678c04122a1243cc4545a5b83494810e05d02131e` |
| `client/apk_patch/v2v3/tmp_q9.axml` | 8,284 | `8907d9b258c918c057046ff267d86f1128a13153ece8e32bcfec9ec70a67559c` |
| `client/apk_patch/v2v3/zipdiff_v2v3.json` | 403 | `979f4a6ccb5cf5474c13a8350fea02cb85c85dfda75ab2fe9fa8b4c57ee7bc4a` |

### `client/apk_patch/v4/` — 24 文件 / 306,090 B

| 相对路径（zip 内） | 字节 | sha256 |
|---|---:|---|
| `client/apk_patch/v4/aapt_xmltree_v4.txt` | 32,684 | `dc6cd3660ffb43ee90a01e17c59d4ed5ce731d26623453a8db5529b59822dd72` |
| `client/apk_patch/v4/build_report_v4.py` | 22,588 | `7d1f567383e73e589c57cf861eb7eff410fde73df8a4fd31cac178525ef92cc4` |
| `client/apk_patch/v4/layout_xml.diff` | 23,214 | `a4eca63fe1c4ef61a23c17845e033a43d812c3f85f400fb1812aa4c89c6029ce` |
| `client/apk_patch/v4/make_layout_v4.py` | 11,483 | `b50b95bf15c194992c14e5e66b00af0ba36a39d3eff1e187dc2c87b5ad6bb36d` |
| `client/apk_patch/v4/preview.py` | 8,183 | `e0e34cccd7934eade17534c57348246549f7c32f4b7eaf617bba34854b8352d6` |
| `client/apk_patch/v4/preview_v4.png` | 87,288 | `47cd05803149bb404e8defcde452b020687339bf59a691b7dd4e3924cc47e101` |
| `client/apk_patch/v4/probe_container.sh` | 523 | `3d8328a78ef2220c3dac418c7624c39857f2a7be84b3eb1dbfda7ec7536c4b6d` |
| `client/apk_patch/v4/probe_container_out.txt` | 776 | `e8953165ac016aed6cb61ebaaac88de51282b7ffb0b44c2ee3862e6391609057` |
| `client/apk_patch/v4/probe_hideall.txt` | 5,418 | `93d20aad7e4722dd8cfbe2700a5f7f94b2ebd6e3b468c1b76427904598554c88` |
| `client/apk_patch/v4/probe_vis.sh` | 560 | `0a31fb41eeb39a18df8cd8ec89f3c1c147bdf2ffd50f771fcdf37fec5992526f` |
| `client/apk_patch/v4/probe_vis.txt` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `client/apk_patch/v4/probe_vis2.sh` | 216 | `4c1917f2d291c9c266ed28f3541a1aeb9968041359b233d88041fbcb12ecfac8` |
| `client/apk_patch/v4/probe_vis2_out.txt` | 5,638 | `9eabb5996a17919eb266e755cb4d9d5e288550cded210ea1a68abe267e91dc3d` |
| `client/apk_patch/v4/probe_vis3.sh` | 297 | `3e067094e19b13b911ba0117d70a209e7eacb833f976963270f0f101f858dd44` |
| `client/apk_patch/v4/probe_vis3_out.txt` | 12,708 | `c7e294969c35da11ac9c0cca719f3874485341ab90e6d597a689f0c8072428c4` |
| `client/apk_patch/v4/probe_vis4.sh` | 244 | `20ef1333b1f25db1fe0552857ac5438f41f56930af387370b1cf7ca3a2c36971` |
| `client/apk_patch/v4/probe_vis4_out.txt` | 4,410 | `0ca7fb6edab4c5bc4df4174ca3e02f79b3b38772707372086b4d6ae438c912cb` |
| `client/apk_patch/v4/probe_vis_out.txt` | 6,162 | `50db6e1a4f432a12535e0d86ce601c3dddcb3a6bab1f32c79e8eaecb16a6c36b` |
| `client/apk_patch/v4/res_Q9_v4.axml` | 8,208 | `f614865a97955515e41e2248af0b6004f7eefdea3d2fbd0897285d226cb189b3` |
| `client/apk_patch/v4/selftest_console.txt` | 11,506 | `69c80214adc7b66dfcbe25db65ffeed7bf62417fd3c0921716481f2340366813` |
| `client/apk_patch/v4/selftest_v4.py` | 10,122 | `4af2c33dd71d47b0c23c8736124b5311d7e5ad2582340a59dddb7a40b9d1023b` |
| `client/apk_patch/v4/selftest_v4_out.txt` | 5,891 | `e2ccf45c524ab4423993b9f6f5c6d5ed33d32e001ac450c4c42f5470f2f12cda` |
| `client/apk_patch/v4/v4_axml_dump.txt` | 47,780 | `ebbc2e36d53d4d6a86a12b7ab0ae2c9daa481a4c3b4d140d47df7174139de4ed` |
| `client/apk_patch/v4/zipdiff_v4.json` | 191 | `4bc2583163fd2c0d50d0b5063a87852f3cab5ab6b3d4dbc3b2c43c490b071b24` |

### `client/apk_patch/v4/smali_probe/` — 12 文件 / 85,984 B

| 相对路径（zip 内） | 字节 | sha256 |
|---|---:|---|
| `client/apk_patch/v4/smali_probe/v4_p10.txt` | 992 | `61edf837f1edb29dc1440f3303fd1ff8d7d54aa802d27efbf9932151ba230d0b` |
| `client/apk_patch/v4/smali_probe/v4_p11.txt` | 842 | `c5092e022f46f79460fe9ef251a7ecbb6dda89f42a2cbf31d04bfd94bf7e2d17` |
| `client/apk_patch/v4/smali_probe/v4_p12.txt` | 984 | `743a06b7eafc7819a2fddee0a7c0b437146d171ebad811e7044ae68c3fc03450` |
| `client/apk_patch/v4/smali_probe/v4_p13.txt` | 812 | `f1627bdea9e3320a89dfb951032b3bfa76909464f61cf5b1efb81833b9329a89` |
| `client/apk_patch/v4/smali_probe/v4_p14.txt` | 592 | `83dd556111c33a4e0a5e63e4dd55f1ec9514e644cad1a809addfdf10ace202f5` |
| `client/apk_patch/v4/smali_probe/v4_p8.txt` | 128 | `70a73d12030880e83f1d743f79262f607b4d188b66c832ba0cb788bca22ae72d` |
| `client/apk_patch/v4/smali_probe/v4_p9.txt` | 12,836 | `9081a952c6873d077696604bdd688bb8048417f305c3b9466d8c6c42c70cdf48` |
| `client/apk_patch/v4/smali_probe/v4_probe1.txt` | 4,190 | `2309fbc12065de9e12da294c17fd909c817caa6985a56a969e0fcdea487af9a9` |
| `client/apk_patch/v4/smali_probe/v4_probe2.txt` | 2,934 | `f9af4b92903dee84319e72ff8b97fbd089408a3f3e26b1a3d25feced7f55f8f3` |
| `client/apk_patch/v4/smali_probe/v4_probe3.txt` | 4,316 | `7e3dbe4a301d318a710e22d6ea65689e5d647a175648efcb478e5c34c8a81f2a` |
| `client/apk_patch/v4/smali_probe/v4_probe5.txt` | 48,732 | `a6c1befc1ac6b3c443f1014670e8794d5c65ec2d9ef795997b4ad1178ff66ff8` |
| `client/apk_patch/v4/smali_probe/v4_probe7.txt` | 8,626 | `57e0e6c2dbba07e0542e2f088f29574db65eb6904f798c9cde8f724e33363777` |

### `client/apk_patch/v5/` — 18 文件 / 319,251 B

| 相对路径（zip 内） | 字节 | sha256 |
|---|---:|---|
| `client/apk_patch/v5/badging_v4.txt` | 8,653 | `b690d5c71fa105045e2850669b5b8dba25548a2e4db0aa171b994839066105b7` |
| `client/apk_patch/v5/badging_v5.txt` | 8,653 | `b690d5c71fa105045e2850669b5b8dba25548a2e4db0aa171b994839066105b7` |
| `client/apk_patch/v5/build_report_v5.py` | 24,457 | `d412c4930044b78281488ecc1000c01b093b0c12b9b584cf1ae998b354842371` |
| `client/apk_patch/v5/ev_index_safety.sh` | 1,913 | `44502263432d3206d7e0040bbb7337aca68351a2bcfb0b6503cde6cadf7e34c3` |
| `client/apk_patch/v5/ev_index_safety.txt` | 5,133 | `74f7ad6ec62b73d83fc3c70ca085515d80e799ecfa4458e96ac25d2a8de79c3e` |
| `client/apk_patch/v5/ev_xmltree.sh` | 1,096 | `b60ec4f5eeca3b5f35a3eedbc8e0d8c5821b0afc1ad0d13c6b963ef881520ecc` |
| `client/apk_patch/v5/ev_xmltree.txt` | 2,938 | `5f23fee6f3fa8175752cd622fe055b0dc8b9826f91457f133051bcf8c0cc6bfd` |
| `client/apk_patch/v5/make_layout_v5.py` | 8,990 | `59ec24b4fb7e3b916c7bf882ae70da5f4fbb7b2c41e10140d143f4d255fe8e6f` |
| `client/apk_patch/v5/preview_v5.png` | 157,358 | `d399dda20f3f8ebcca2a09adc24b499cff72d0facc43b5e93bbe098929246d82` |
| `client/apk_patch/v5/preview_v5.py` | 11,997 | `c2f8b4c43a340bdfa6244472f5e09ce087c0fd8aaaf3a9e623dba4166a4e5c1d` |
| `client/apk_patch/v5/res_Q9_v5.axml` | 9,060 | `e8096feacfdc5411c4ed65fce2bd75188ecd8dbb6db4dd92d48f551e52437918` |
| `client/apk_patch/v5/selftest_console.txt` | 9,654 | `87acc08a89bbbff786fa46db0472c214e734b5ce107d43b1bb7e64cc62a63151` |
| `client/apk_patch/v5/SELFTEST_v5.md` | 52,560 | `3958ffce9f103b1b2f29028850fc9b914de1361423b9ab4ba5c83be16ae850e9` |
| `client/apk_patch/v5/selftest_v5.py` | 9,875 | `a3d9fadee994b098e5f3ae0c0472c31dc8756cfc43a2b22407292d19b6be124b` |
| `client/apk_patch/v5/selftest_v5_out.txt` | 4,936 | `9917b12afca4f032578dbf76c6e7368b9e2da8d146f214d020ea83614417a27c` |
| `client/apk_patch/v5/sig_v4.txt` | 888 | `7775578894bf9cf68a8956aa903a43c7f3fd328ea6911e259dad11f768db8cae` |
| `client/apk_patch/v5/sig_v5.txt` | 888 | `7775578894bf9cf68a8956aa903a43c7f3fd328ea6911e259dad11f768db8cae` |
| `client/apk_patch/v5/zipdiff_v5.json` | 202 | `34692d79b080f14569661737da8e8d94206e7f1ed361d8b76c99b150a1b33106` |

### `client/noroot/` — 130 文件 / 2,822,048 B

| 相对路径（zip 内） | 字节 | sha256 |
|---|---:|---|
| `client/noroot/24000_DIFF.md` | 21,873 | `87327899c25c64f40156c3706f0edb971c684d0086132f874da1c9e8044bebc1` |
| `client/noroot/_axml_out.txt` | 27,892 | `93d58c5d1dc1790efbc96b803b92afa7c89ea55252184ad140a742e7cba7884d` |
| `client/noroot/_axml_res_apk.txt` | 27,346 | `cd88e720caf30d69922d93a9924591f9217549bfb8e65545486b31b5d51d66da` |
| `client/noroot/_cdn_ctx.py` | 1,404 | `003077e9d8f1ebd8c4f89d2ba1d50c5c407ec96f5d2ed8c7e9088165be904ae1` |
| `client/noroot/_cdn_fullapk.out.txt` | 2,640 | `498246ec3309e358b7838f0cdc6b996ca692b3323a6dd3a8729d3070bc09d7b6` |
| `client/noroot/_cdn_fullapk.py` | 1,836 | `1d2d87d2f86b545a3952bbf2ed1da6a4404478bb30476834699418bc369e29ae` |
| `client/noroot/_cdn_har_cross.py` | 1,480 | `9ef0d9fc2f803a0b1a00f0f3ba4cb6a8b1c7e3383f2bc81f2367681060ccf9e1` |
| `client/noroot/_cdn_scan_aa.out.txt` | 7,392 | `1486cefde71ae01396e0eb3e9ce3b2f7850bf6a256fd6d95e43fb07bbf1d6090` |
| `client/noroot/_cdn_scan_aa.py` | 2,340 | `153cfa7dbf70c9e3fea20965c068b19a5a39dead9c27be3f95d5a719c559341f` |
| `client/noroot/_cdn_scan_apk.out.txt` | 8,614 | `395a42ff08a5097dd7f9fea9a32a4f158e7a89f046c2127cd3d60be9912d6cd7` |
| `client/noroot/_cdn_scan_apk.py` | 2,899 | `46d46b58f548bc0ded7a6a1c956d6c7b94a411b8eb3e7f71ff82d130764fe366` |
| `client/noroot/_cdn_scan_catalog_ctx.out.txt` | 1,204 | `cd55bbe930e66373261d9a44c01f5ec4743f5c534e495951f2bd1d5ca917a678` |
| `client/noroot/_cdn_scan_catalog_ctx.py` | 1,466 | `60621349cbbc9f9e23f2f7d6f2d90bee6e231148596bba7d6ef77b3a8c8de253` |
| `client/noroot/_cdn_scan_meta.py` | 3,302 | `8a7f4867824d3c03a1bfa85bd86a01676647cb91ee3717a5edfeda06b9495168` |
| `client/noroot/_cdn_xor256.py` | 1,892 | `f0474bc0fefeb9c0d4ba89c29e4187185e91d68dd7abaee7c413d59ba429d06d` |
| `client/noroot/_cluster_resurls.txt` | 6,672 | `be9d3ba56de1a3ea0aea07993e8dd8c2d7c19994b9761ee230ccb8e8cb9a932e` |
| `client/noroot/_cn_crack.py` | 3,754 | `4b90e1bbbe2a0ca6739d8de5292a1f222e2c35c12515f1d01cd1733be29883de` |
| `client/noroot/_cn_crack2.py` | 2,844 | `f1148a833adbca2e5dfc607bc81ca9d6fca5bde1789d89e0528e18c360d3d5e8` |
| `client/noroot/_cn_crack3.py` | 5,127 | `4eb020f619e26b8d261fc00939f2074c6f314e2f06970fff05b6e0a82c9da099` |
| `client/noroot/_cn_final.py` | 5,179 | `a7c6a0dea2e9b762e531233b029fc1c0e284e4cfb1249b5eeeefbf3d578e5bcd` |
| `client/noroot/_cn_guess.py` | 5,764 | `dcb541ce9d2a3fcdfe5097481cae447ca4efce716e0a8a485153e63a6ebadab5` |
| `client/noroot/_cn_layer2.py` | 3,135 | `592d6a9f48c3b5e0a05a186c1d02c5349421ced638046a3e6f84ff5ce871c756` |
| `client/noroot/_cn_one.py` | 4,750 | `137fddb86615e9e37d06377acf21b20efdfa8caf645b72d28910e0a118646992` |
| `client/noroot/_cn_parity.py` | 3,286 | `7694e09d51bfeb0bc3489e47e4ba4bc3774ad4fc742e03228c57ced8a80cc42a` |
| `client/noroot/_cn_patch.py` | 8,449 | `e39d84632234882fdf5593ccd24e5168a1a1c8383ea028e5d9956b6a06810854` |
| `client/noroot/_cn_scan_lib.py` | 2,175 | `02d6608a21d28f5337f4881a96fc3ded09a19e70236d6f0325de3ebe95e7525a` |
| `client/noroot/_cn_scan_sanity.py` | 1,710 | `de12fe97405ab7977042e1dcf8ccec8722f0dad7689a00a1cd626b75b6302fa2` |
| `client/noroot/_cn_schema.py` | 3,187 | `d66afd027248279e05ef2276710ec81000613e676ad3c8456cf2e4b2e49028c8` |
| `client/noroot/_cn_verify.py` | 2,676 | `69cbc19f1aae31d7d4a3c2bb1226fa5aab8917bc1f03ac008a3d18194a92bd56` |
| `client/noroot/_cn_words.py` | 4,825 | `dd6dcb68a143f9dd5f9f86a0b3c776b4b573ebfdbc3b152da45bbef52b4e5d31` |
| `client/noroot/_ctx_129346de.txt` | 7,060 | `95b3bda6947c770fa1806adfa00943afb0395465b004e88feb9c472190bba2c5` |
| `client/noroot/_ctx_gmd_addressables.txt` | 7,698 | `0a892544ff997dbcc172f7d3df396a6f937d399e23073e410252c28d5d0ac3ce` |
| `client/noroot/_ctx_gmd_resurl.txt` | 7,912 | `7d078a3e64a226967531e9795fc9c55a38a960f273e5a17c8372c55f94d6cad6` |
| `client/noroot/_ctx_platformutils.txt` | 6,132 | `a6ee64b200072a16fb0dbdc21ad1256de6f176de1a9a9c9fa0eafe63f535cc98` |
| `client/noroot/_ctx_serverinfo.txt` | 11,198 | `daec6e3dc62441827e9a7742e4112ec1c615ab4832fa8fc810ae85318eece58d` |
| `client/noroot/_dbg_all.py` | 2,129 | `4179c42c37449674573713c8137c459b3dc01342887926d0a1a64a6d17ea6fa3` |
| `client/noroot/_dbg_chunks.py` | 319 | `3ed10d359e8f71268f8f61f580bbed8957370891d9995d697100a4231f0e0c35` |
| `client/noroot/_dbg_mt.py` | 1,404 | `9d38914d6f38c0d72a39bf278fbc05c1395493a765976fee83d3cd1c2728b982` |
| `client/noroot/_dd1-P2-repack.md` | 38,032 | `c1197dc919b5f02d3986b58aa478365ac0e9664f4dff9955189c9f6c853dbfe9` |
| `client/noroot/_dd2-P9-plaintext.md` | 38,327 | `d53dcb3162d00252a4f2c94fe834edc49634c92eef496c86c1d964aaff59b21d` |
| `client/noroot/_dd2_axml.py` | 4,471 | `c74f2ffa2dc404338dbe3aaa2366d3f7dc337d4d6312639ce1e17d9d8e7afee1` |
| `client/noroot/_dd3-P4-userCA.md` | 62,572 | `02c21dd6cf495eb1ce4360e87aa331f9e86963efc964d275ad36435448cbe1d8` |
| `client/noroot/_dd4-integrity.md` | 65,480 | `f95cd61c659d958c06ba5ccd0ca89755d2a8cee1402c68ef2d7ae4f61408956b` |
| `client/noroot/_dump_axml.py` | 5,720 | `7e251fd70b051ead8e44c5c2681cad24dede2686977985f7c57db9913ea16ad3` |
| `client/noroot/_gmc_cli_test.py` | 9,216 | `5832e3d13a1cc9d78e12f2352bcc92da26c1be1456b139fe71e588397437ee2b` |
| `client/noroot/_gmc_crosscheck.py` | 2,537 | `e61eaad9bb163be344e7740e070ffb8e88267ce7c641584a74a0108e782dc574` |
| `client/noroot/_har_cross.out.txt` | 4,802 | `3c5e5ed6d88dcab9c8f8a107eea9592f32e8e1071c6ea8817810876538440d31` |
| `client/noroot/_har_versions.txt` | 4,658 | `c548bb636d50854bbf81a0252aa9795d98e336c934f83c300ebd69ffe326ea40` |
| `client/noroot/_lead_negtest.py` | 4,559 | `65c9c6bbcd585374fa4bf35b6fe1f8eaadda18e0f0c1599d0adbfc3a6934e259` |
| `client/noroot/_namecluster.py` | 2,510 | `8ccbd81fa4316230a4aa033e6da3c9067497a7634dba0a3f827fd6e25b4518e7` |
| `client/noroot/_patch_textasset_sdkconfig.py` | 12,180 | `854e6ec43fe70ddcdfbdf1fc9acc46bb293bdcea417f4a2650e9b2a05a9961dc` |
| `client/noroot/_patchdemo.py` | 1,905 | `079ed5edebf8a1c240bc697b3414ec5fa75816d711de56fed275e91c1a9bebf2` |
| `client/noroot/_probe2.py` | 2,094 | `16d41c6446e957d8a87b2d534ac926f65fc0691c55f1cbc6b900e8284810fc79` |
| `client/noroot/_probe3.py` | 2,849 | `73f511222e1a3201469b1938ac7fd90adf25b3a33a309e0b7ed4c87c46561ba2` |
| `client/noroot/_probe_jarwrap.py` | 1,498 | `896656cf7dc2b645f51ccef6f1343822fb2ea373b67eba26c3d4c3499770a9bf` |
| `client/noroot/_probe_p7.py` | 1,148 | `fee72e1ed276e393398eb5dae1ac3f6618a23835c8092bf245463eb77beace28` |
| `client/noroot/_probe_payload.py` | 2,516 | `2438f49966c550b79f4ccad3cb0df3acd71bf2cf5377ec9269e7fff1401df24c` |
| `client/noroot/_probe_v1fmt.py` | 1,954 | `79888a6a86a99dc4fbda1c091218c03e5d561c52a83744d2a9d411b6f9d9393c` |
| `client/noroot/_res_apk_manifest.bin` | 50,220 | `d1c5dbce5328980cf508915b46f4dc34adadc61203a0527598f859c7abf72ce6` |
| `client/noroot/_res_xml_http.bin` | 264 | `f4861a2727f78aa4a30a4dc82308b1ec645dcce1ed7ab8aa05e806684b4dbee7` |
| `client/noroot/_sanity_il2cpp.txt` | 1,096 | `e7f096cab2511a7336144e51f12cc3d8e2825bf67154204a4e5f097d9cb28ed3` |
| `client/noroot/_scan_big.json` | 543,693 | `32d35ec0402694a5b629f6f2f36e344950329f5157593bebef098dc06311704c` |
| `client/noroot/_scan_big.txt` | 256,991 | `c21c0b63a63011aabb97947790304ae9aa46efc0f7c7b062da53d1cde4005feb` |
| `client/noroot/_scan_gmd_extra.txt` | 2,622 | `a8c5520646de6e4576c0687958daa0c3a1a9b0486de22b1d4722a7542c2fa73d` |
| `client/noroot/_scan_gmd_literals.txt` | 1,512 | `c2a9667462879a0d8b7f7ffff2700b1b5be72ff52304bea5ad4034cdac6dbf6e` |
| `client/noroot/_scan_il2cpp.txt` | 1,138 | `4296186a9c60b06ca4e9bfaec99d1fa0f445c23b7fb58e7fc8b87dbc98b5e549` |
| `client/noroot/_scan_il2cpp_resurl.txt` | 830 | `57248c06717808c0425e68c8a17a8597d48d55713c6bc5731887bcad6fcbc790` |
| `client/noroot/_scan_meta_gmd.txt` | 1,484 | `9963fbc7615665fe5b19f1041ff6036708f6210beacacd5014dfe3bb6c1be519` |
| `client/noroot/_scan_small.json` | 5,184 | `7157d193a7b5f68a046c71ce0fa665ebf681e84a410d7a000af519ee4f5152e2` |
| `client/noroot/_scan_small.txt` | 4,414 | `d09c7fb4bb8dc10b8f00d747617db1e847cd90ada2f28d7a95dd71b55772da73` |
| `client/noroot/_schema_bruteforce.py` | 2,104 | `dcbc2d8fc8ba66b8424ca4c78054468e08ac5993d5b6f0085729da59b5325fdc` |
| `client/noroot/_signfix_evidence.py` | 2,041 | `f8a42c7af9e44cbf81d3318b821933e2d1eaf6ba63342805af80f21a1fd37089` |
| `client/noroot/_signfix_live.py` | 2,155 | `6bf15d0f0ae6915eddd2828be2cd61fbd88427291904249f72e83f48fd5b6637` |
| `client/noroot/_signfix_probe.py` | 4,424 | `6de8182b09ab6da4095fc93b6336f4ea3805abc764b79b9cc528de017a39ee19` |
| `client/noroot/_signfix_probe2.py` | 2,442 | `e94970aab8daf8d2f96252d93a91d7090981ef83eeffb8722f18e25cb3c49680` |
| `client/noroot/_signfix_probe3.py` | 4,818 | `33ec9e75b1683a660eff514d55f133e897d46ec82b304d4de4ddfbc068dd4452` |
| `client/noroot/_signfix_test.py` | 26,855 | `f4c559d2af5dec9227ddc5ff4f422af7d773f3dd7b4bf8ef1aa467df431ff5e8` |
| `client/noroot/_snapshot_build_0103.py` | 77,997 | `5585809663f791f766e8bcc244a27f99cb362481fc254e53fd1bd9e87849bafc` |
| `client/noroot/_snapshot_build_0105.py` | 95,582 | `fcea819580deb315fe544cdddae0dc0e99fab5df1e23d7417ba6dba4430a38c8` |
| `client/noroot/_snapshot_build_0107.py` | 97,105 | `ed7ffd4016929ab37962161f8c95d3db05f8f1439c7e7964af6412d5decc877c` |
| `client/noroot/_snapshot_build_0116.py` | 109,041 | `b17a4fbeb053da65eb3f0d77031d9a2376637220e974445886c62db2c15705a7` |
| `client/noroot/_snapshot_build_20261117_2040_pre-rename.py` | 109,041 | `b17a4fbeb053da65eb3f0d77031d9a2376637220e974445886c62db2c15705a7` |
| `client/noroot/_snapshot_build_good_0112.py` | 108,496 | `0ffbd5bb881c3e2d6ea72af51fca6006af0d4e0298ade246563ab1b32044d7a3` |
| `client/noroot/_targets.txt` | 2,030 | `5b5ecb03af081dd94de8445575b9cbaff08c2b574a88355cf8a2f5a5144969a6` |
| `client/noroot/_tprt_strings.txt` | 19,063 | `2506d1dfd351276cd8b033863eb50d03db261303c7098554731c44df9b0cb8ae` |
| `client/noroot/_urls_meta.txt` | 12,894 | `b4d25df581cee7705aa83d813b6943d58f170bd80ea34e08fcc174b793d7adae` |
| `client/noroot/_xor256_gmd.txt` | 2,182 | `5aabe92d52062370416fe8ae7ffc3b288ac603b6505d14a6ce3f192117454ff5` |
| `client/noroot/_xor256_resurls.txt` | 2,310 | `69f960bcf8898589ab30f7d9ccd3aacccaa5f5b1cfd6f8aa37e8127ddaa45505` |
| `client/noroot/_xor_url_metadata.txt` | 20,793 | `ed4319eeaab839557f0459983f90e5ca02b9c0ca205cb69eb2dfdc82141dbda3` |
| `client/noroot/_xor_url_others.txt` | 12,736 | `4513ab95d6263bec001d54fd9e801ccafdfae7c9cec25e8dc62b290c10e4a8d0` |
| `client/noroot/_xt_needle_bluearchive.txt` | 230 | `7bbecd0270031578b7721a0528d600e1bfed8abe44082c572927902a1f1652ee` |
| `client/noroot/_xt_needle_example_com.txt` | 232 | `bb630243261af9b29cc7b24d612a98a48267d6cdfc63e0ef763cf6d3397391d6` |
| `client/noroot/ACCOUNTINFO_LEVEL_MAPPING_20261118.md` | 9,897 | `a64ae1794bbec38af5073b683534699f75ab1df9e7664017b7b6526570413c20` |
| `client/noroot/APK_SCAN.md` | 23,133 | `e1300f4beac199125b5c5eacad656f5382640df3f04c2b2e37cb38afc7bb969a` |
| `client/noroot/AUDIT_BUILD_NOROOT.md` | 47,408 | `b07df9e5b7d191de115098a6e0c50cb2c8145e7b8d940b424147430e886142e7` |
| `client/noroot/ba_private.cert.pem` | 1,126 | `1a99218ce58676c6d20ea7eb9228a25bdbc32832261d2841422e29dfaedbf2ca` |
| `client/noroot/ba_private.key.pem` | 1,698 | `c9cae27ffc6ec327a4109afa07cc5eaa5102a53fb1e0fcabda757c5829f3e9c6` |
| `client/noroot/ba_private.keystore` | 2,568 | `1e7669b1b87a27b50f1340c1103954250e2dd61709aaeb92a5261b27c99d4963` |
| `client/noroot/build_noroot_apk.py` | 115,375 | `c9f0c8600739d26293665175a23e18518472a077add9c3c0aa0a11c4fa90e1f5` |
| `client/noroot/CRYPTO_MT.py` | 6,666 | `e1f127fbc6b5c98bfdfbbfb3417d7d482ac4b7ccacd8d0d95e38d23a7bc59b41` |
| `client/noroot/extract_urls.py` | 2,951 | `f73c5d8f6677ecec92c0950f48edccaf83bfc5f938b2fc971eb079cf91e5e04f` |
| `client/noroot/find_gamemainconfig.py` | 13,671 | `599f92006f93fc7dff6e8df3be3f25bc4c892b51c7bdb2bb0d980561a8a50db0` |
| `client/noroot/FREEZE_FORENSICS_20261118.md` | 7,413 | `9f2c1e399fb5a5a4e76781186b34793b93865a6ec91a5bac5c68491d278b00a3` |
| `client/noroot/GAMEMAINCONFIG.md` | 14,851 | `fbf594c99d6b124592e4362fb6e549008aed3f09e8c5279a60a7c95237a7d1da` |
| `client/noroot/GAMEMAINCONFIG_CN.md` | 22,549 | `68ca7d0a688e271e65c7da8e3cc5d83e4712653d9d9d0043985c6f9136671665` |
| `client/noroot/GameMainConfig_http_example.com.bin` | 5,212 | `3c190b6527c838e42cc38d796f3440794dc4f54a660d080a1d6141cda9f1fe6e` |
| `client/noroot/GameMainConfig_http_example.com-2.bin` | 5,212 | `d4c3ebf965aa492ba6bedd12e244ccef93a3da9d6e6c4773f9f8fb1fa15ba48b` |
| `client/noroot/GMCONFIG_INTEGRATION.md` | 25,321 | `ce6c8da924d849330fdec27379db2f898c714867cc984af8c87d28ba5d61c21b` |
| `client/noroot/HISTORY.md` | 57,376 | `9f3a6c3fdb14abd6eafe27eb338d29527b0d59b20d04bb609d872e2bbe7e7044` |
| `client/noroot/IDCARD_FORENSICS_20261118.md` | 9,317 | `faa76b30a939c93b34e2604c4f01da007a039f47b8dcd15dd411332048da73ec` |
| `client/noroot/IDCARD_NAME_FIELD_20261118.md` | 9,447 | `3ed2619d57e84c7b75a55dfd661df89f673c9b0b74c1765c049c43bfa8d310c2` |
| `client/noroot/LEAD_VERIFY_SIGNER.md` | 5,222 | `16468e6f8ab7beb089482ab9562e4f5f6e9a2026f5537b57756a84ed6072675d` |
| `client/noroot/meta_band.py` | 2,016 | `1d58a5ab368b127c915c79d98533e629f829cf8d8590e5e9a9d54c136cca565d` |
| `client/noroot/meta_band2.py` | 1,195 | `22328c70cb05011cb32b4855f706e095b6e5e87324eee5db81c3e542374c60e2` |
| `client/noroot/NOROOT_BUILD.md` | 35,457 | `d955c9bd9040f5b95ac3157610ee8784267ac870d2d6d94a40df4a742ecafe9f` |
| `client/noroot/NOROOT_PHONE2_TEST_20261118.md` | 33,106 | `790ea541a8241c9cf25be7995dd57900ed281e583b3ff961ba612bc5abe90e94` |
| `client/noroot/NOROOT_PROD_BUILD_PLAN_20261117.md` | 32,052 | `4cff24b05cf0f2211cdec47a2daf420c2cba069488a8076a5164357490fc5fc5` |
| `client/noroot/NOROOT_TLS_RESEARCH.md` | 42,010 | `17727c3725c0545246dcbc7d7468b81e6d0296ee750e21edb5c010cca8607fb5` |
| `client/noroot/OPTIONS.md` | 61,829 | `cd4fc46e7e440921428dc5c86e083e7b240b2b48e063b36482e39786de4b39eb` |
| `client/noroot/p4_proxy.py` | 15,466 | `a0271e657ed3d36c2b675c78cc8d13c1bd5798f31d52ec6d23de2b6193f6f74c` |
| `client/noroot/phone2_ADB_20261118_0000.md` | 5,706 | `c1c7005b31fa957af45ba31c0a9cff47c0b50b9cc7ade2fca49c4f23791e8675` |
| `client/noroot/phone2_INSTALL_20261118_0013.md` | 2,863 | `9626d8a6eaa71fac4b37443ff66aaa5a8bdb5b8d82db48c06f4fcc142f6ed3c4` |
| `client/noroot/phone2_PREINSTALL_20261118_0004.md` | 3,617 | `06da4c97d4c6261b827d2c61a3859b8580d02651b50e3ecf227868d7686b91b8` |
| `client/noroot/RESOURCE_CDN_SOURCE.md` | 32,951 | `d9581f2f12d89addcabb823e1898d3d0c083ef3feffc2db2623344d1a2224604` |
| `client/noroot/scan_needles.py` | 8,978 | `e01a3ba061153a1a75358a42df473617ffc590c6dc2ddccf1e2a8195d5f577f2` |
| `client/noroot/SDK_ASSETS.md` | 34,132 | `bd043480b9ac54a6c9173eafb6d8533831e64d17a0d209ac39f282d38fd74605` |
| `client/noroot/SIGNER_FIXES.md` | 21,246 | `0770b6b6452461b95fe1abbc0f31674d1cc669487aa08deb0a5501b1ab85e2d4` |
| `client/noroot/SYNC_RESOURCE_ERROR_20261118.md` | 9,712 | `c721c64c3eb6318fb6743576767908f8932886c20bf509134b9a6ed3522097d0` |
| `client/noroot/USERINFO_POPUP_20261118.md` | 11,110 | `6bc48111f663a2966ce17ecd9dadcb9f853c2c7f6a24815c7589e04d11b1798f` |
| `client/noroot/xor_scan.py` | 8,177 | `e19d38d238012583455ebc5e220d42f058ff296e95d107543cc3551dbf1b4868` |

### `client/noroot/_extract/` — 3 文件 / 9,479 B

| 相对路径（zip 内） | 字节 | sha256 |
|---|---:|---|
| `client/noroot/_extract/GameMainConfig_assets_bin_Data_61376b4dc1d7943a1a6556439d2df761.bin` | 4,616 | `2820800c31150025d6d80a9e56ee20922ba375f59c2fe742ae7d94924bc917b7` |
| `client/noroot/_extract/GameMainConfig_assets_bin_Data_61376b4dc1d7943a1a6556439d2df761.json` | 247 | `9a888c707c30fe608f43fa6728eb171aa7d949bca03e58f52a95254e84466138` |
| `client/noroot/_extract/GameMainConfig_assets_bin_Data_61376b4dc1d7943a1a6556439d2df761.PATCHDEMO.bin` | 4,616 | `70b3effbcd4578474bba1a92d1693b603a7324ad5f24af6b09876fc20c24071c` |

### `client/noroot/_extract_cn/` — 5 文件 / 16,437 B

| 相对路径（zip 内） | 字节 | sha256 |
|---|---:|---|
| `client/noroot/_extract_cn/CN_GameMainConfig_plain.json` | 256 | `8fa3fc5745075cb0441360ab7aad2df707b88cfd71b1389004bedf2e0ba7151c` |
| `client/noroot/_extract_cn/GameMainConfig_assets_bin_Data_e37c46fea17834108a4756797197d05a.bin` | 5,212 | `b027eded4ed0aea597688f321c60df65e334f2e5c435954f6b8726d93d5759dc` |
| `client/noroot/_extract_cn/GameMainConfig_assets_bin_Data_e37c46fea17834108a4756797197d05a.json` | 545 | `bc2ca52ce220cdd4de8e585067f86f8d51aebd871b950ca693c95acc3b368fe1` |
| `client/noroot/_extract_cn/PATCHED_e37c46fea17834108a4756797197d05a.bin` | 5,212 | `19de5a15fe57bde4123d16357bf5b2d3f340e2e8210ca99db961348ff7ddfd2c` |
| `client/noroot/_extract_cn/PATCHED_SHORT_e37c46fea17834108a4756797197d05a.bin` | 5,212 | `c25b87820f67d26f244f719c51617b184b81db570051a8bc4f61a5c2b17d3ee9` |

### `client/noroot/_kit/BA_probe_kit_v1/` — 1 文件 / 8,707 B

| 相对路径（zip 内） | 字节 | sha256 |
|---|---:|---|
| `client/noroot/_kit/BA_probe_kit_v1/README.md` | 8,707 | `873dd0f29d7dec95c32cc8e1831255fccd65472e19c2ee25bc5a73252833fdd5` |

### `client/noroot/_kit/BA_probe_kit_v1/pc/` — 3 文件 / 18,813 B

| 相对路径（zip 内） | 字节 | sha256 |
|---|---:|---|
| `client/noroot/_kit/BA_probe_kit_v1/pc/make_certs.ps1` | 3,743 | `f92956ed9c97b2956db6dfaec26a1a9ac7221f90a460eeec779d9aeb74a30258` |
| `client/noroot/_kit/BA_probe_kit_v1/pc/run.ps1` | 2,941 | `bb40968e3e58b38d92dd5c044448af66ec3c502ff0f52839b16f6918dfeea388` |
| `client/noroot/_kit/BA_probe_kit_v1/pc/state_gw.py` | 12,129 | `878891b7c4673641c0feebf79cb2727afa52201126027fdb4dc480b24ef50c62` |

### `client/noroot/_kit/BA_probe_kit_v1/phone/` — 3 文件 / 10,162 B

| 相对路径（zip 内） | 字节 | sha256 |
|---|---:|---|
| `client/noroot/_kit/BA_probe_kit_v1/phone/00_collect.sh` | 5,212 | `40d90bc0af81a19650cd3004858515e2b3cbcb1b7c82823c577f10a0e4d96451` |
| `client/noroot/_kit/BA_probe_kit_v1/phone/01_fix_got_slot.sh` | 3,569 | `002352bb37c804f68202e8fe1cfaab583a7a2e5881c5b2092d7cd6956ec1db90` |
| `client/noroot/_kit/BA_probe_kit_v1/phone/02_net_watch.sh` | 1,381 | `25ceebddc6b6e990b95ce72d8f477bff0faeb388835a9a70954af235946d9653` |

### `client/noroot/_probe/` — 4 文件 / 16,936 B

| 相对路径（zip 内） | 字节 | sha256 |
|---|---:|---|
| `client/noroot/_probe/_nsc_orig.bin` | 264 | `f4861a2727f78aa4a30a4dc82308b1ec645dcce1ed7ab8aa05e806684b4dbee7` |
| `client/noroot/_probe/axml_arsc_probe.py` | 10,590 | `5ac8db549d56823921831c3bb15ed4de8b8300453517fa6d2aa88ae27eee9419` |
| `client/noroot/_probe/probe2_resources.py` | 3,478 | `c558e7856b0279af4779e28231ae35b23258d7d8ac7366c139e43b9801cbd265` |
| `client/noroot/_probe/probe3_sigmin.py` | 2,604 | `47fa249ff181023dbc87fe3939ace22a490c6f1eaf7861ad7269f06ce33c095f` |

### `client/noroot/diff24000/` — 25 文件 / 197,399 B

| 相对路径（zip 内） | 字节 | sha256 |
|---|---:|---|
| `client/noroot/diff24000/diff24000.py` | 11,559 | `c0f068cfd1e7074d311f8a4aeaefc93dd41bace88ab819c59a04267236c36d75` |
| `client/noroot/diff24000/diff_A_official_vs_ours.csv` | 8,255 | `c5d709837fbdbb292867ae6528795f7f9c539256621e4526015326e2380bc60b` |
| `client/noroot/diff24000/diff_C2_replay_exact.csv` | 40,373 | `199aa40314069c89e8e4a2ae05832df6b04ad4301ca13a86dc54093ba5309485` |
| `client/noroot/diff24000/diff_C_replay.csv` | 10,038 | `3bc2ab512efb205ced51dbd8c6cfd0cf6926ca65dcb853de5de1cd1bc16cf6b1` |
| `client/noroot/diff24000/diff_D_degraded.csv` | 8,225 | `9a9056d1f8f99876b500fcbbe275832381dc40448ec13ed3bfe0c2d12c0af158` |
| `client/noroot/diff24000/gen_report.py` | 27,915 | `16f3ebbcf95edc0603584fe2894e1a535b081cec94d57717565b119cf3d315d5` |
| `client/noroot/diff24000/log_A.txt` | 15,366 | `b489080cb3f8924aa3fac80327af11adc8ff05d95384db0d2730a467b6f16209` |
| `client/noroot/diff24000/log_C.txt` | 15,348 | `6207f4afa756f1192a094938217373bc9b027e74b8a2ed25449318bfb4707599` |
| `client/noroot/diff24000/log_C2.txt` | 108 | `055b02a253fc2bd6fbf971c274cb2c4d0300a05a0bd95b7c927625aedc91ddfc` |
| `client/noroot/diff24000/log_D.txt` | 15,306 | `f86e9febf3242fb7a55bd0ecb4fd9ff03c6ba95f1fc14c2de34410f794151c50` |
| `client/noroot/diff24000/log_replay.txt` | 1,188 | `80efae4d7d4eb7c2c37226b6b57ef39bffcaf02f87a1fd7f47c794b0e510513d` |
| `client/noroot/diff24000/make_degraded.py` | 568 | `9b389e9b334a1454c0527432c1ddb2b1d92713fbd104947e7f0e24a32bc2edb2` |
| `client/noroot/diff24000/make_replay.py` | 4,426 | `a0a6420b3dfb1fc85af512b2bb80c990a68f58cd35b224fe56e61639fae95008` |
| `client/noroot/diff24000/official_replay.json` | 2,155 | `7d59e9911dfe8310cb13b00f1309a05c61bb54c09150bf2b304cd82a5c21a9a5` |
| `client/noroot/diff24000/official_replay_exact.json` | 11,638 | `cf7a9e94b06aacd40a4a6c9c85c0364cfa8b18acdbf67a79e2eea4a082902cac` |
| `client/noroot/diff24000/official_replay_exact.plain.txt` | 13,128 | `b4f85ff7ef627ce4de085655c7363e220ba65d273f4e2684f03825c9853bdc0d` |
| `client/noroot/diff24000/our_degraded_account0.json` | 1,399 | `2d3d60715d297b3581553ade2ed74f8b1d0ccac833075cd337fce507d647a9ba` |
| `client/noroot/diff24000/our_min.json` | 1,429 | `151f3ec7ac71fa3f44ef34f02cca6f721b15cd4e2087f68e059a5dda0a4b2a94` |
| `client/noroot/diff24000/probe_envelope.py` | 1,268 | `673e318731402f6170fd3227e1c0f44f3393586939d91bb2fec1505faf354bc8` |
| `client/noroot/diff24000/probe_ls.py` | 947 | `e8ad0825d642be25345e2b3ede4a762af686fbb2dd9703a7b89861e256aa42d3` |
| `client/noroot/diff24000/probe_official.py` | 1,765 | `b882f35d7cc3899b8774b6c93fa7137e41da4f64b92b1f075d41003b9d3e8340` |
| `client/noroot/diff24000/probe_samples.py` | 1,441 | `9555294d88182772d276ce74553acb1808de9f5102bf3c124862bf3d6279d711` |
| `client/noroot/diff24000/probe_seq.py` | 780 | `38e66aa4803efe4950cbc9f0912f1fe2a83cb60bb1c6599f4f00ba380ddd32ef` |
| `client/noroot/diff24000/probe_time.py` | 1,532 | `58ce69c90da12a15f07eab97481fd174e12abdc799dd8bc94d7f95049b27deb0` |
| `client/noroot/diff24000/probe_wire.py` | 1,242 | `696902814bc428448b62f691505d453532df46ff3a6d713f5f4937e83018443b` |

### `docs/` — 18 文件 / 364,694 B

| 相对路径（zip 内） | 字节 | sha256 |
|---|---:|---|
| `docs/CLIENT_ID_WHITELISTS.md` | 18,998 | `b8915b80a78e773256ea8312a455af92ddfb6295a9c7f6f85c73c82fbe12c5b0` |
| `docs/D90004_DEPLOY.md` | 8,346 | `b69271e4bffb0095692e8d43e8d3e5a1bd3bbb03da111f338921e603a3f3720b` |
| `docs/D90004_PATCH_PREP.md` | 26,723 | `c9cc5fd70006b25d6ef3d8ea9a6ac4985a327b7979edf7f3c942ba6c1822f8ba` |
| `docs/EXPORTFILTER_DEPLOY.md` | 4,625 | `c06971719120c88851872097b5893e3a3c59fceffdf1f791f27425f7421f2e78` |
| `docs/GACHA_CLEAN5_DEPLOY.md` | 5,951 | `4b5a946895c3d988aaa751573ccd64b59c26d8a996a0eff36221d33b815e2fc5` |
| `docs/GACHA_CLEAN5_INCIDENT.md` | 4,579 | `5534d3a5fc85b3ea4a02713c984b4cd7f0de4d2161c86a6ab3cef4e19a5a650b` |
| `docs/GACHA_ROOTCAUSE_90004_FINAL.md` | 24,467 | `72e9178cc5cfbd000994dccf65ccac4960ae5dc32c01dea0292b1d54ec03a5c4` |
| `docs/GMLOBBY_DEPLOY.md` | 5,477 | `5a9fafc2c3e9c0acc79970b4696ffbcba03d385230b7b86336d59955092f1b96` |
| `docs/HANDOVER_20261119.md` | 46,061 | `732cb1ead853590ea840e1186f44f5bf01eb0084afdae2ecb29216b6ab8812cb` |
| `docs/MANAGEMENT_DATA_90004.md` | 44,778 | `ff7b63dbe75487f5657b8439243fb743d27e2af121670ad73ab54ad71989531f` |
| `docs/P0_CSHARP_IMPL.md` | 77,690 | `f97d26a48963b10e9173633283fd8033934296b39bad5f54928b48a01e0acb4c` |
| `docs/P0_GACHA_RATES_PLAN.md` | 38,427 | `6530ff6450f087584ad9c195e8fffbde657397e75b3cce7b1e7a84a3b423017a` |
| `docs/P0_PANEL_IMPL.md` | 24,793 | `52df7d63be9d11abbc5618518077f295a146c0c99d61933d7c4026ef1f65bdeb` |
| `docs/P0_PRE_BACKUP.md` | 8,886 | `5c026ed0fb1d7fc5ffaa337ce8339d74a4f9720a3c7575d3b6ecdee795286792` |
| `docs/P0PANEL_DEPLOY.md` | 5,312 | `f76bf421c9369a261cdbddefd164aeb811074dfe927c09bdebde783ba82d54b0` |
| `docs/P0RATES_DEPLOY.md` | 7,697 | `c0df173242b3577cc8e8ed9de5aa28a83f6184ea21f0bf999ce4c6b50d3c1e25` |
| `docs/SERVER_RESTART_OOM.md` | 7,846 | `a3b54978250bd033ab8ead9b4680e17fc172a6ab3295f2de1409471ba04310bc` |
| `docs/SWAP_1G.md` | 4,038 | `f7c99b303456c120ec9fa5c16df7cb2af638564873d6fe6e2cbac050323faa9c` |

### `panel/inc/` — 3 文件 / 61,783 B

| 相对路径（zip 内） | 字节 | sha256 |
|---|---:|---|
| `panel/inc/gacha.php` | 17,073 | `1152ff4c5f16372f7cec78a3b458d45dd0e4ed2781b4f396d6634d2f1e3a4e94` |
| `panel/inc/gm_lobby.php` | 15,579 | `7623fe9889eac4c26e1d8b45eaad7a21049f45c158288f7247b06cbdb74ec268` |
| `panel/inc/helpers.php` | 29,131 | `0bd35a74fed7c932bf232f1fb0bf49efd738448e6bd122c1c9830539a4d4a371` |

### `panel/pages/` — 2 文件 / 48,298 B

| 相对路径（zip 内） | 字节 | sha256 |
|---|---:|---|
| `panel/pages/gacha_rates.php` | 24,050 | `105f151cd539322f26ffaa54d32a250c084b82d99536516249f3318d36e1bfdd` |
| `panel/pages/items.php` | 24,248 | `25f7e2b3d29fec83fcc5abf57b121c2c733e491dd958d712f9693f4767dc0c26` |

### `panel/variant_p0rates/pages/` — 1 文件 / 15,807 B

| 相对路径（zip 内） | 字节 | sha256 |
|---|---:|---|
| `panel/variant_p0rates/pages/items.php` | 15,807 | `9ff1f66bf5e4213bdaf24cb8fcbf76bc6cca3561383c71a0e56f227d0edc1b97` |

### `panel_full/ba_cardadmin/` — 14 文件 / 52,107 B

| 相对路径（zip 内） | 字节 | sha256 |
|---|---:|---|
| `panel_full/ba_cardadmin/.htaccess` | 1 | `36a9e7f1c95b82ffb99743e0c5c4ce95d83c9a430aac59f84ef3cbfab6145068` |
| `panel_full/ba_cardadmin/.user.ini` | 88 | `353f2699f4fb9bfe1eccf2e2db80a94962d8d1633dfa504f0289010eb2929968` |
| `panel_full/ba_cardadmin/.user.ini.bak.1794777086` | 45 | `9287f265a2439df160d77f4fb2685894d35659fbd0ed3367be6be76cf4ea77e2` |
| `panel_full/ba_cardadmin/404.html` | 138 | `301bd9f16f94feedfae7a946a14bac38cb73c43efe6117bc5586835af03d7d6f` |
| `panel_full/ba_cardadmin/config.php` | 1,088 | `5ddb2a841d7cce6e1d9fa0f659403d1d065d7ebeba7a0d19b858825674154df1` |
| `panel_full/ba_cardadmin/config.php.example` | 2,733 | `e133bfe2d74bea857c8ba499d19423e405dfd589c3d16ce6df8e9229d46a11b5` |
| `panel_full/ba_cardadmin/index.html` | 917 | `3b319a1e7740a5e3a99f2b9dd8fcf137f0f32773eb44100b012db3196cc6ae5c` |
| `panel_full/ba_cardadmin/index.php` | 396 | `7c3edff633fc7e23c72456b8461617052d3281aec1fa8d6b8c8f21ad295f08e6` |
| `panel_full/ba_cardadmin/installed.lock` | 293 | `06dee44818de25442787761a33d1fd9511ccccc4bd9a5fa084c12da209c5c7c5` |
| `panel_full/ba_cardadmin/login.php` | 4,315 | `eeca7cd0063dba7b99c73655c44faa54c43a6fd9c37fee2a48cb0de22edc98fc` |
| `panel_full/ba_cardadmin/logout.php` | 230 | `0661c73ec444e86798d01480bd3beca74bb6a02c5a5d02e88b785379b21b9bd5` |
| `panel_full/ba_cardadmin/nginx.conf.example` | 2,735 | `10026df7835dab280cd2f5e9229aeee089a6139d5658f601f5fee628928968f9` |
| `panel_full/ba_cardadmin/README.md` | 25,592 | `1f5c537f7f54385e6ed8634fbe6b0e03f1429b8e084df1f98069681155630d1c` |
| `panel_full/ba_cardadmin/SHA256SUMS.txt` | 13,536 | `bd66c28788396bcc24514d19a1ff40ba431a287020bc91dbde40f1722c1ee6ca` |

### `panel_full/ba_cardadmin/assets/` — 2 文件 / 28,220 B

| 相对路径（zip 内） | 字节 | sha256 |
|---|---:|---|
| `panel_full/ba_cardadmin/assets/app.css` | 18,146 | `acdbc8a19304508494b8f654cbcc3be2c635f5558dc2ac712b90f42827c51990` |
| `panel_full/ba_cardadmin/assets/app.js` | 10,074 | `341bce89b83e42e3d6b6e5b59ae23f2db41223e500783f0abdc0397da8306b0b` |

### `panel_full/ba_cardadmin/cron/` — 2 文件 / 4,896 B

| 相对路径（zip 内） | 字节 | sha256 |
|---|---:|---|
| `panel_full/ba_cardadmin/cron/.htaccess` | 218 | `2b25242e978e65aa1ec224b783643f863ac30ae0b51e45d42b8781b7d84e83bd` |
| `panel_full/ba_cardadmin/cron/sync_cards.php` | 4,678 | `4113ba8f46a394677d49b8056e30c10ffb7358a7137dbd61105b893516900f9d` |

### `panel_full/ba_cardadmin/inc/` — 10 文件 / 283,868 B

| 相对路径（zip 内） | 字节 | sha256 |
|---|---:|---|
| `panel_full/ba_cardadmin/inc/.htaccess` | 218 | `2b25242e978e65aa1ec224b783643f863ac30ae0b51e45d42b8781b7d84e83bd` |
| `panel_full/ba_cardadmin/inc/auth.php` | 19,244 | `020e5fe87a2ceec8d3e7d69e91e0845b05ff97eb7f2225cf6a0281343c81f76d` |
| `panel_full/ba_cardadmin/inc/ba.php` | 17,298 | `752f1637bdb86787b1600cc04e506cd3e25b5a161806ff012439fdddded55771` |
| `panel_full/ba_cardadmin/inc/bans.php` | 107,659 | `b99d93f812911ad70cf24bdf0e90c6ecd8dc3e2003690a061c453c07b1426649` |
| `panel_full/ba_cardadmin/inc/db.php` | 4,309 | `a9fa260d6aea7197fedf907392247f07d60ec77ec24cc4a43bf8dc5a4de6b409` |
| `panel_full/ba_cardadmin/inc/gacha.php` | 17,073 | `1152ff4c5f16372f7cec78a3b458d45dd0e4ed2781b4f396d6634d2f1e3a4e94` |
| `panel_full/ba_cardadmin/inc/gm_lobby.php` | 15,579 | `7623fe9889eac4c26e1d8b45eaad7a21049f45c158288f7247b06cbdb74ec268` |
| `panel_full/ba_cardadmin/inc/helpers.php` | 29,131 | `0bd35a74fed7c932bf232f1fb0bf49efd738448e6bd122c1c9830539a4d4a371` |
| `panel_full/ba_cardadmin/inc/players.php` | 26,097 | `cac1c3d005dcd5d242b9c2acbd475a74a81eac6a541b73073ee7058100be55de` |
| `panel_full/ba_cardadmin/inc/sync.php` | 47,260 | `a439ad8b6f5e759c5bbf399c4e66010ebbda4121fca4fd622277606c86cbbc89` |

### `panel_full/ba_cardadmin/pages/` — 17 文件 / 314,303 B

| 相对路径（zip 内） | 字节 | sha256 |
|---|---:|---|
| `panel_full/ba_cardadmin/pages/admins.php` | 12,359 | `a76e16ac3b880389cda1a5e920c3467e5327140b9a1d36f21c96481d95790622` |
| `panel_full/ba_cardadmin/pages/audit.php` | 4,982 | `505a554baea561bcca2ba0e204611e21700544bc86f4a1de7e1068b840a181bf` |
| `panel_full/ba_cardadmin/pages/bans.php` | 60,571 | `9783d0ef38e60ec1425a2a084a313c6ab16f8d8a45a4d99cf694358ba5b80dfd` |
| `panel_full/ba_cardadmin/pages/cards.php` | 28,295 | `91603c45f3a6ca09b2e70e8b51450e1788436fd4dd3d8ee19d9275b50f97bbc7` |
| `panel_full/ba_cardadmin/pages/cards_export.php` | 6,102 | `2e272e161b52cf06787a00ce32048261c11c1348842f7ccfc132051057fca49f` |
| `panel_full/ba_cardadmin/pages/cards_import.php` | 13,366 | `33e84d4576c41c1ef3e418d59dd011dd295fb8c78cdeca7d979f078cfb3df53f` |
| `panel_full/ba_cardadmin/pages/cards_new.php` | 16,776 | `234f27ee95c7e6edcaaa80998f1e2c3b3a00a2e92ab6216e2d9bdcf93ec86b0b` |
| `panel_full/ba_cardadmin/pages/console.php` | 11,012 | `f66a5f8c43c416be25a135464bba95c9476cde12cdb9f91b6ac2b157f6eb5512` |
| `panel_full/ba_cardadmin/pages/currency.php` | 9,383 | `c744bd90b4eaa1e613c61f05e48b4e5222b752c9403f3a6e0a3008fdbf8d588e` |
| `panel_full/ba_cardadmin/pages/dashboard.php` | 14,535 | `f2ac179034671aa26fa543427712b85654cfe02ef41a9489795cb17b130f44ae` |
| `panel_full/ba_cardadmin/pages/gacha_rates.php` | 24,050 | `105f151cd539322f26ffaa54d32a250c084b82d99536516249f3318d36e1bfdd` |
| `panel_full/ba_cardadmin/pages/items.php` | 24,248 | `25f7e2b3d29fec83fcc5abf57b121c2c733e491dd958d712f9693f4767dc0c26` |
| `panel_full/ba_cardadmin/pages/logs.php` | 14,173 | `8b428faad36bdf51e8ef29aaabfc00ddd38c4bf83d5f8ceb4822158875df3389` |
| `panel_full/ba_cardadmin/pages/mail.php` | 17,396 | `2a64aba4025bb5eba104a2497d245c6b27b35bbd85c3b06ad834d3345889b3fc` |
| `panel_full/ba_cardadmin/pages/player_detail.php` | 21,344 | `d7ddf270b73340299c3d382d8c6d3e69909064e199c8fac0df2bf6be804730fb` |
| `panel_full/ba_cardadmin/pages/players.php` | 13,469 | `b4a340f8dc1858cbb16f099cb134c11a0dd15425d80541a3375786b4be89ea63` |
| `panel_full/ba_cardadmin/pages/settings.php` | 22,242 | `23409a84343e4ad9f093b33c70fa97dfbb1dbcbc3cb1f1ae4bb4181536d225ab` |

### `panel_full/ba_cardadmin/sql/` — 2 文件 / 7,997 B

| 相对路径（zip 内） | 字节 | sha256 |
|---|---:|---|
| `panel_full/ba_cardadmin/sql/.htaccess` | 218 | `2b25242e978e65aa1ec224b783643f863ac30ae0b51e45d42b8781b7d84e83bd` |
| `panel_full/ba_cardadmin/sql/schema.sql` | 7,779 | `e4f6cc6843be90cda0c724d38a98a9b07419eb1b34c6b060b76e37e879c73cd8` |

### `panel_full/ba_cardadmin/state/` — 4 文件 / 1,682 B

| 相对路径（zip 内） | 字节 | sha256 |
|---|---:|---|
| `panel_full/ba_cardadmin/state/.htaccess` | 218 | `2b25242e978e65aa1ec224b783643f863ac30ae0b51e45d42b8781b7d84e83bd` |
| `panel_full/ba_cardadmin/state/cards.backup.json` | 1,350 | `c51427753702fa5a62edb575751190947eb4a1c032712c6796893c35ec0af4de` |
| `panel_full/ba_cardadmin/state/otok_c981db91fc4f347a1f62eafa.json` | 57 | `1deea7a48506330b5576d2ecce5eb50c355c592835b94c4918c97bb68deea0b4` |
| `panel_full/ba_cardadmin/state/otok_feeac26639a499856325130e.json` | 57 | `c450e6eaf8c8e966eac4547d444531618cd0db1eaddc736af7aac84303a584de` |

### `panel_full/ba_cardadmin/state/bacache/` — 3 文件 / 67,637 B

| 相对路径（zip 内） | 字节 | sha256 |
|---|---:|---|
| `panel_full/ba_cardadmin/state/bacache/static_chars_e1cf5e7eb4b4eecdd8e506495dde0b94.json` | 22,652 | `0b8745577446d2741ce9f143b5fe08a981a6cb628f35638dac5512914058b2d6` |
| `panel_full/ba_cardadmin/state/bacache/static_currencies.json` | 1,038 | `8770e9763ea141f4e444d9a90a0a22068783f3d74a9d4878db0894351ec04ef4` |
| `panel_full/ba_cardadmin/state/bacache/static_items_87f332e93cfb9af6a1b7011ec4a48c79.json` | 43,947 | `dbfc6812bf2d54774e9c9615e169b3c0f3d9b7e1a512f05e7818df351dc8f88f` |

### `server/` — 2 文件 / 8,120,320 B

| 相对路径（zip 内） | 字节 | sha256 |
|---|---:|---|
| `server/Schale.dll` | 5,392,896 | `b06f46090f9d8eb8657e51401b789178d9090ad5a5a6d6d1faaa791dad429858` |
| `server/Shittim-Server.dll` | 2,727,424 | `c013f4427ad01d44c00cc63af3de817b800638fcd8ec0ee55de41126aed106aa` |

### `server/Data/` — 3 文件 / 41,531 B

| 相对路径（zip 内） | 字节 | sha256 |
|---|---:|---|
| `server/Data/gacha_rates.defaults.json` | 312 | `59bbf27d738daa74f0693e53f8074ecefd469bdbaf5b5282aadf4d1d9e9b2aad` |
| `server/Data/GachaRecruitBanners.cn.clean5.json` | 480 | `ed3a3d867517f90b4cac97cfc4d39045bed38f8c36fa80ac280324708da54834` |
| `server/Data/GachaRecruitBanners.cn.json` | 40,739 | `3ac8385d77a2921932eedf934de83178f61a6c8c30b588c3ca64718f0c423c77` |

### `server/Resources/` — 7 文件 / 93,832 B

| 相对路径（zip 内） | 字节 | sha256 |
|---|---:|---|
| `server/Resources/ClientCharacterIds.txt` | 63,304 | `80e87e4cae88b97821a4bf54a264849056fdfd06090365fe495c57f18e2eb745` |
| `server/Resources/ClientEmblemIds.txt` | 8,474 | `7a95df573c27443b2380adfcd75344c57c45f5f28da96a57c324525c0c6d0757` |
| `server/Resources/ClientEquipmentIds.txt` | 1,073 | `fe60518503bb9558e0b35414afb27a83438acfdbd39a6e785d587098f88f18ff` |
| `server/Resources/ClientFurnitureIds.txt` | 5,240 | `625b58a22e0eeec7ae6aca9519af4f2219a25529341fc3a1410285cb1c0aade6` |
| `server/Resources/ClientItemIds.txt` | 12,659 | `48af0fd945fbd2dfaca0afa022b9cafb7095514bfd578b85a09dca17bbeb5ac6` |
| `server/Resources/ClientMemoryLobbyIds.txt` | 1,558 | `d1b12814c91e7fe17475a534ebbce3e1ed4cff8b3bdad56dc763ef915dc9b13e` |
| `server/Resources/ClientWeaponIds.txt` | 1,524 | `9ecf356ec853b334f548421f64e425dfcfdd2da51282e0599f87e181d823ec6e` |

### `server/Services/` — 1 文件 / 15,601 B

| 相对路径（zip 内） | 字节 | sha256 |
|---|---:|---|
| `server/Services/ClientItemFilter.cs` | 15,601 | `b14d2a228657ba6f561dd482090f981371bcd50b751e60f341cf922ff823cd50` |

### `server_config/` — 1 文件 / 40,684 B

| 相对路径（zip 内） | 字节 | sha256 |
|---|---:|---|
| `server_config/SHA256SUMS.txt` | 40,684 | `f30bf8cfb891039505b5eff51abd005e9ee473addf98b422b8b19e99af7942fd` |

### `server_config/ba_sdk/` — 4 文件 / 43,693 B

| 相对路径（zip 内） | 字节 | sha256 |
|---|---:|---|
| `server_config/ba_sdk/ban_message.py` | 6,378 | `4f29f42a96b50dc02b25fa94b7bdec00edfd013f717090cea2b69504488f5f88` |
| `server_config/ba_sdk/check_order_probe.py` | 3,814 | `23198d63ed6e22cd224d46001a040fbb577d7c677f779ab18c8c6e54c43e132c` |
| `server_config/ba_sdk/pay.json` | 47 | `4461167078cef3a9766f6728a22a5496ea22bcf974ea34b6d2aa31ad9c398a54` |
| `server_config/ba_sdk/sdkcard.py` | 33,454 | `2f7d32b18e865dfe6d61d4ff52c8f7bbef47e2775cce9932605858305cc39fb2` |

### `server_config/ba_sdk/resp/` — 10 文件 / 1,198,327 B

| 相对路径（zip 内） | 字节 | sha256 |
|---|---:|---|
| `server_config/ba_sdk/resp/common_agreement.json` | 1,157,371 | `f3faa548813f2927b9b0284d026bc806a9b867fcd3ca05fa2faaa3e824bcbe22` |
| `server_config/ba_sdk/resp/common_client-code.json` | 23,731 | `76be839a81e6e61430428d08647f8d30c455865c1aaacf0df6bfdbae114e8376` |
| `server_config/ba_sdk/resp/common_config.json` | 7,873 | `ca6c98dff20def8f3b6929348ff505124f775b6a0a305aebf0837551c37289ee` |
| `server_config/ba_sdk/resp/common_config.json.bak.20261117-203121` | 7,589 | `ee713d8abfe9d5d66a55e75490edbeb0c036539b104876c552d36062ec3264a2` |
| `server_config/ba_sdk/resp/common_geo-ip.json` | 51 | `4a2f55a6616baf7cfc7191a1da0387b1e6f0807ce56b0a5d56f57dac633a2b14` |
| `server_config/ba_sdk/resp/health-game_duration.json` | 65 | `fdf760ca6e4280a335f27bf086b6bd54af3b447d1949a8bd8d5002be5956a16b` |
| `server_config/ba_sdk/resp/heartbeat_pulse.json` | 45 | `5ae8658d7694699afca9736dc7bc1fe9f7e52cf6a78f26d35ed7794ce6a08a04` |
| `server_config/ba_sdk/resp/user_detail.json` | 763 | `80baa1dc5d4c5769e72c144b1b6ba133ae3d7b52ac1831fdb7301d80c50357a0` |
| `server_config/ba_sdk/resp/user_login.json` | 76 | `cd573dd14b432083bfe1bd5dbef2062fa4fecd523af1a1258a7a6891aed04972` |
| `server_config/ba_sdk/resp/user_quick-login.json` | 763 | `80baa1dc5d4c5769e72c144b1b6ba133ae3d7b52ac1831fdb7301d80c50357a0` |

### `server_config/bapatch_root/` — 33 文件 / 159,995 B

| 相对路径（zip 内） | 字节 | sha256 |
|---|---:|---|
| `server_config/bapatch_root/cn_1017_relay.txt` | 1 | `6b86b273ff34fce19d6b804eff5a3f5747ada4eaa22f1d49c01e52ddb7875b4b` |
| `server_config/bapatch_root/cn_3.txt` | 2 | `4355a46b19d348dc2f57c046f8ef63d4538ebb936000f3c9ee954a27460dd865` |
| `server_config/bapatch_root/cn_account_svc.txt` | 2 | `4355a46b19d348dc2f57c046f8ef63d4538ebb936000f3c9ee954a27460dd865` |
| `server_config/bapatch_root/cn_banreply.txt` | 1 | `6b86b273ff34fce19d6b804eff5a3f5747ada4eaa22f1d49c01e52ddb7875b4b` |
| `server_config/bapatch_root/cn_billing_block.txt` | 1 | `6b86b273ff34fce19d6b804eff5a3f5747ada4eaa22f1d49c01e52ddb7875b4b` |
| `server_config/bapatch_root/cn_bridge_exp.txt` | 22 | `8ccf60b2fb962a42f4872f4d2c67b2805167d6a8b534bb1195c80b4f8721e251` |
| `server_config/bapatch_root/cn_bridge_exp.txt.bak.1794598994` | 22 | `d64a76ebc8d341032e026d9e14f842a3e8cc39a1d88e152a5d532b65df6223de` |
| `server_config/bapatch_root/cn_bridge_mode.txt` | 7 | `062ad4dc6d69b881c197df69db5ed14214ae62614f63c2e2dc370aec2d2c18de` |
| `server_config/bapatch_root/cn_canary.txt` | 3 | `b6ac5bc39377e44ee783dff946f6703a994f5eb31a438e69dc0735b40060d2e8` |
| `server_config/bapatch_root/cn_dedup.txt` | 1 | `6b86b273ff34fce19d6b804eff5a3f5747ada4eaa22f1d49c01e52ddb7875b4b` |
| `server_config/bapatch_root/cn_dedup_window.txt` | 3 | `bdc5d8a48c23897906b09a9a3680bd2e9c8b3121edbda36f949800f0959c8d55` |
| `server_config/bapatch_root/cn_devid.txt` | 1 | `6b86b273ff34fce19d6b804eff5a3f5747ada4eaa22f1d49c01e52ddb7875b4b` |
| `server_config/bapatch_root/cn_field_patch.txt` | 3 | `b6ac5bc39377e44ee783dff946f6703a994f5eb31a438e69dc0735b40060d2e8` |
| `server_config/bapatch_root/cn_flatten_keys.txt` | 3 | `b6ac5bc39377e44ee783dff946f6703a994f5eb31a438e69dc0735b40060d2e8` |
| `server_config/bapatch_root/cn_hash_mode.txt` | 4 | `b470b84cf0cd3189e10615bffea7d5cbd9f61134ba1c2cfd513ddd45b776a5f6` |
| `server_config/bapatch_root/cn_inner_min.txt` | 4 | `b470b84cf0cd3189e10615bffea7d5cbd9f61134ba1c2cfd513ddd45b776a5f6` |
| `server_config/bapatch_root/cn_inner_src.txt` | 7 | `d61e8fcaca4358dde6ad919ca93271bbd7727e0dad74dcc2b6799ccb39bd96cc` |
| `server_config/bapatch_root/cn_multiacct.txt` | 2 | `4355a46b19d348dc2f57c046f8ef63d4538ebb936000f3c9ee954a27460dd865` |
| `server_config/bapatch_root/cn_nametoken.txt` | 1 | `6b86b273ff34fce19d6b804eff5a3f5747ada4eaa22f1d49c01e52ddb7875b4b` |
| `server_config/bapatch_root/cn_packet_wrap.txt` | 9 | `69737ddd15ff3466f05671e94560bc122af50f7812b37ff63dba31eb315d9759` |
| `server_config/bapatch_root/cn_proto_val.txt` | 5 | `f80b1fa820d95a87cf48f78eb6c298b427fda46207f7b52eaff6fb8ab1590c64` |
| `server_config/bapatch_root/cn_protonum_remap.txt` | 1 | `5feceb66ffc86f38d952786c6d696c79c2dbc239dd4e91b46729d73a27fb57e9` |
| `server_config/bapatch_root/cn_relay.txt` | 4 | `b470b84cf0cd3189e10615bffea7d5cbd9f61134ba1c2cfd513ddd45b776a5f6` |
| `server_config/bapatch_root/cn_relay_known.txt` | 2 | `4355a46b19d348dc2f57c046f8ef63d4538ebb936000f3c9ee954a27460dd865` |
| `server_config/bapatch_root/cn_relay_unknown.txt` | 2 | `4355a46b19d348dc2f57c046f8ef63d4538ebb936000f3c9ee954a27460dd865` |
| `server_config/bapatch_root/cn_requestid_mode.txt` | 7 | `87c1b129fbadd7b6e9abc0a9ef7695436d767aece042bec198a97e949fcbe14c` |
| `server_config/bapatch_root/cn_resp_format.txt` | 12 | `ee2f106b92d31855407f5402ecf98acff5d6a53b888347c98b30275f5adaa801` |
| `server_config/bapatch_root/cn_wrap_mode.txt` | 12 | `39f08eda60264646e1ec7435ab6f1d2ad666505f900d0f84529a3c15755742ef` |
| `server_config/bapatch_root/gen24000.py` | 34,015 | `0f38d266a26d4b2c3dacc66d7db00e8127a20edc3d7e01710307b0454e61be3c` |
| `server_config/bapatch_root/NOTES-gateway.md` | 5,628 | `c37656c72c0bd0f56e9fbc7a47370ba22373c3c038ece4a986bef76cb812406d` |
| `server_config/bapatch_root/patch_24000_v3.py` | 60,456 | `0dd983084c5a1f494e2f622e5d1edb15b305d0548416185c6ef5cec35a2aae7e` |
| `server_config/bapatch_root/patch_requestid.py` | 57,287 | `a1fbffe9a8991834d0a74e452da403de1f312cd87e2abdd79a2dbb580dd9be3c` |
| `server_config/bapatch_root/README_CA_LOCK.txt` | 2,465 | `5cf488c31e331419034973dac70eb5d20e701add2e32a7f98e5cbb45fbc42032` |

### `server_config/nginx/nginx_conf/conf/` — 38 文件 / 38,960 B

| 相对路径（zip 内） | 字节 | sha256 |
|---|---:|---|
| `server_config/nginx/nginx_conf/conf/enable-php-00.conf` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `server_config/nginx/nginx_conf/conf/enable-php-52.conf` | 214 | `407f229accfa7bc3c8b89f8ed03c8c26c533a96ddb969613a95ac44af08faf88` |
| `server_config/nginx/nginx_conf/conf/enable-php-53.conf` | 214 | `0a3e30a49c1e34dafcaecfc4779b9886d415c8f1ffc6779ee0b706fc1f03815f` |
| `server_config/nginx/nginx_conf/conf/enable-php-54.conf` | 214 | `a9ec2a400e1c1998868a1f605b5e9f0fcb1cddf3c42d6a655652a5ec695b4559` |
| `server_config/nginx/nginx_conf/conf/enable-php-55.conf` | 214 | `a0c01a0f1fc66139dbe7f0a319cd01d13c72dd1cee6da244c7b260c3cea38e1b` |
| `server_config/nginx/nginx_conf/conf/enable-php-56.conf` | 214 | `c29b8349a3fdc002818e50366fdeeacf27ff06119d0497e143a2dfa8075817de` |
| `server_config/nginx/nginx_conf/conf/enable-php-70.conf` | 214 | `5f84bf9b6eceed02272a3e6f21f4f2b18e881814cd94c589d85578294ea1278a` |
| `server_config/nginx/nginx_conf/conf/enable-php-71.conf` | 214 | `f44282425d7342c02a8f74982d9351d5cc7a7f41664104275b466dd62d64478b` |
| `server_config/nginx/nginx_conf/conf/enable-php-72.conf` | 214 | `7bd43c149c963cda411a0d5247a755cc41f9bb86566c6a18681dc4b875203950` |
| `server_config/nginx/nginx_conf/conf/enable-php-73.conf` | 214 | `5bc2267017f56269bb790e11940bdafd273f93cb54ec4a6e40090b86d496d9b5` |
| `server_config/nginx/nginx_conf/conf/enable-php-74.conf` | 214 | `033779f9e6e557d20fcd5342b3ecbbf2514e3f47d199115e150a0ec829fdd133` |
| `server_config/nginx/nginx_conf/conf/enable-php-75.conf` | 214 | `94276ff2460e694774c50078d9360ef3d053ac69bb356db9874cde73a2b1e9f8` |
| `server_config/nginx/nginx_conf/conf/enable-php-80.conf` | 214 | `bbb1a24518abc096152293363f338ee8738d372134038134f6c4716f24fbff91` |
| `server_config/nginx/nginx_conf/conf/enable-php-81.conf` | 214 | `3de2802e7c8254808d4f0951bdb715684da62f26b040b2f4c4069811b6461bfe` |
| `server_config/nginx/nginx_conf/conf/enable-php-82.conf` | 214 | `e8b44ab82d950822ba8df70f2c706ccc49d5f98444c10707b4ed56c7308f2485` |
| `server_config/nginx/nginx_conf/conf/enable-php-83.conf` | 214 | `2ce07f36af7e3f7c0290b7dcdf440cddf9d00f1dbd860c0013f7d2234ea9ab36` |
| `server_config/nginx/nginx_conf/conf/enable-php-84.conf` | 214 | `2add54d6e6d530501e3e24b0f61f9cb40d51a5eb5effaac5895b881449e7a598` |
| `server_config/nginx/nginx_conf/conf/enable-php-85.conf` | 214 | `44f99d2949628cd8ce056aa60acc99f1828728bbfe00a6006c11af037fec78ae` |
| `server_config/nginx/nginx_conf/conf/enable-php.conf` | 214 | `2add54d6e6d530501e3e24b0f61f9cb40d51a5eb5effaac5895b881449e7a598` |
| `server_config/nginx/nginx_conf/conf/fastcgi.conf` | 1,118 | `6deeb10b0fc8cfe670b7d4373d5d9319ef5a82d7f77ace047bed0575cd2cf260` |
| `server_config/nginx/nginx_conf/conf/fastcgi.conf.default` | 1,077 | `b2c3d480a58f61f3a7dc61850b461e892e36f236317765a4f2f6d558c928fa57` |
| `server_config/nginx/nginx_conf/conf/fastcgi_params` | 1,007 | `f37852d0113de30fa6bfc3d9b180ef99383c06739530dd482a8538503afd5a58` |
| `server_config/nginx/nginx_conf/conf/fastcgi_params.default` | 1,007 | `f37852d0113de30fa6bfc3d9b180ef99383c06739530dd482a8538503afd5a58` |
| `server_config/nginx/nginx_conf/conf/koi-utf` | 2,837 | `b5f8a6d411db5e5d11d151d50cd1e962444732593adec0e1ef0a8c6eebec63ee` |
| `server_config/nginx/nginx_conf/conf/koi-win` | 2,223 | `de518a9eafe86c8bc705e296d0ef26135835b46bdc0de01d1d50a630fa5d341e` |
| `server_config/nginx/nginx_conf/conf/luawaf.conf` | 175 | `74ded59e0da9863274edc77a5fa2713f228e5d0fa8652f00135f087fc66ff7da` |
| `server_config/nginx/nginx_conf/conf/mime.types` | 5,349 | `6f95d1d7d75e3c072907d845622a69d23110d1266c16ff122b3109b8b21f3ae9` |
| `server_config/nginx/nginx_conf/conf/mime.types.default` | 5,349 | `6f95d1d7d75e3c072907d845622a69d23110d1266c16ff122b3109b8b21f3ae9` |
| `server_config/nginx/nginx_conf/conf/nginx.conf` | 2,709 | `ad0e7c63028a00db7c01bc5bb83e1e2c6cfb7a414acc641fddf0fac1c02ea281` |
| `server_config/nginx/nginx_conf/conf/nginx.conf.default` | 2,630 | `28924d8c868aedb98e996bd4af1e3c4342d532e59f0ed7bd0e406905e0fb2fa0` |
| `server_config/nginx/nginx_conf/conf/nginx.conf.snilog.1794593540` | 2,680 | `32aee21b577e10e16e5d1d7428734ca0e679f9701ccead2e9ae5f66c0dc4b597` |
| `server_config/nginx/nginx_conf/conf/pathinfo.conf` | 289 | `49e9a46da3a83cbf73ada0ea9b7e449cb01956f74578eb8f4f8ec95d07f40847` |
| `server_config/nginx/nginx_conf/conf/proxy.conf` | 447 | `11de08fc939ce9aa163b20600f55cbaf98112340a01caf19520055aa7ea9dbed` |
| `server_config/nginx/nginx_conf/conf/scgi_params` | 636 | `f27b2027c571ccafcfb0fbb3f54d7aeee11a984e3a0f5a1fdf14629030fc9011` |
| `server_config/nginx/nginx_conf/conf/scgi_params.default` | 636 | `f27b2027c571ccafcfb0fbb3f54d7aeee11a984e3a0f5a1fdf14629030fc9011` |
| `server_config/nginx/nginx_conf/conf/uwsgi_params` | 664 | `015cb581c2eb84b1a1ac9b575521d5881f791f632bfa62f34b26ba97d70c0d4f` |
| `server_config/nginx/nginx_conf/conf/uwsgi_params.default` | 664 | `015cb581c2eb84b1a1ac9b575521d5881f791f632bfa62f34b26ba97d70c0d4f` |
| `server_config/nginx/nginx_conf/conf/win-utf` | 3,611 | `0f221e54163907249b5397cb7357a4a9c946907ed4839c262dd09d8c9f9ca185` |

### `server_config/nginx/vhost/nginx/` — 43 文件 / 107,799 B

| 相对路径（zip 内） | 字节 | sha256 |
|---|---:|---|
| `server_config/nginx/vhost/nginx/0.ba_raw_format.conf` | 374 | `1d05341e2434cc3ed21c4faebf9469a8bca6fc82e417276502b1357bbc548a38` |
| `server_config/nginx/vhost/nginx/0.ba_raw_format.conf.bak.1794591791` | 254 | `97901d7e8be30ddcd9b599f8291f09cf2dddfcba0ecd75aa98c24a3e463b7caa` |
| `server_config/nginx/vhost/nginx/0.default.conf` | 571 | `5ad8dd42ffeaf255c9b52a94ef7951e1155c5365a623671bbdfc79a9f5726b93` |
| `server_config/nginx/vhost/nginx/0.fastcgi_cache.conf` | 287 | `1db1d19ab113df6707d98f551e1d5e8daade8c4ff2825c39fed7879ee0613035` |
| `server_config/nginx/vhost/nginx/0.site_total_log_format.conf` | 2,051 | `2685cbcd4f59511196c2f556c20abfd628aeaa53b5e5347fed8329caeaaf5f47` |
| `server_config/nginx/vhost/nginx/0.websocket.conf` | 77 | `077ddca6aa9735f243819b2305e14f5b22fdaabaa446c974717effb2ad7e7fa9` |
| `server_config/nginx/vhost/nginx/server_ip.conf` | 3,012 | `9deaf0c469e4d1bdf2e96c1b56a83610e99834cd3530865fde710bb8420b8ede` |
| `server_config/nginx/vhost/nginx/server_ip.conf.bak.1794776999` | 2,564 | `a87a68de080939b23685a41be05c010201f83b0f0be30b7024290f7dbc8a8643` |
| `server_config/nginx/vhost/nginx/ai_example_tech.conf` | 1,759 | `72d63966f4a15da90f594a92f3e472127ede4f126788d952e5209249e1c982c3` |
| `server_config/nginx/vhost/nginx/ba_mitm.conf` | 4,352 | `a590c1f183badc4e16da62ce4803cef2ada1c93e6df1be80ef8b4783205b3b85` |
| `server_config/nginx/vhost/nginx/ba_mitm.conf.acctprobe.1794594965` | 3,797 | `9e4d5e725a5a82e82ba6ae2a3166a9391f49512309a8090ed4bdd5e77711b752` |
| `server_config/nginx/vhost/nginx/ba_mitm.conf.allapi.1794595331` | 4,119 | `849a637578da983c136e60e49234ccf49c54b4db9fc3bfcbf482ac1cebe2cde4` |
| `server_config/nginx/vhost/nginx/ba_mitm.conf.bak.1794587752` | 735 | `74806681164f1b306432f05beafc6f173455c4b5fd66ab52b2f96e3fbc95ee00` |
| `server_config/nginx/vhost/nginx/ba_mitm.conf.bak.1794588172` | 1,139 | `af65ee47a9ca5658f9c3e5c125e3e3447dfa726a9c11a1dafb8885f9d19c4810` |
| `server_config/nginx/vhost/nginx/ba_mitm.conf.bak.1794588447` | 1,184 | `864eae8c6b840214514f7975750c3e56435bf57b7ecdeb8aabdbefd0be9a3340` |
| `server_config/nginx/vhost/nginx/ba_mitm.conf.bak.1794588578` | 1,183 | `6137f75fe6b130ccc0026831983fd0bc29cea4b216bb38b7e2a31a03805f3386` |
| `server_config/nginx/vhost/nginx/ba_mitm.conf.bak.1794589195` | 1,183 | `6137f75fe6b130ccc0026831983fd0bc29cea4b216bb38b7e2a31a03805f3386` |
| `server_config/nginx/vhost/nginx/ba_mitm.conf.bak.1794589430` | 1,230 | `8fda290877659628f620900d784b41dc44bb6051a69d026a5b205f2fcb29b147` |
| `server_config/nginx/vhost/nginx/ba_mitm.conf.bak.1794589822` | 1,230 | `8fda290877659628f620900d784b41dc44bb6051a69d026a5b205f2fcb29b147` |
| `server_config/nginx/vhost/nginx/ba_mitm.conf.bak.1794590024` | 1,230 | `8fda290877659628f620900d784b41dc44bb6051a69d026a5b205f2fcb29b147` |
| `server_config/nginx/vhost/nginx/ba_mitm.conf.bak.1794590654` | 1,230 | `8fda290877659628f620900d784b41dc44bb6051a69d026a5b205f2fcb29b147` |
| `server_config/nginx/vhost/nginx/ba_mitm.conf.bak.1794590779` | 1,230 | `8fda290877659628f620900d784b41dc44bb6051a69d026a5b205f2fcb29b147` |
| `server_config/nginx/vhost/nginx/ba_mitm.conf.bak.1794591654` | 1,246 | `99c89f38f1e5c9e369e2644b71cb16781cbba79dca2104b2fb9add534a65815b` |
| `server_config/nginx/vhost/nginx/ba_mitm.conf.bak.20261116_055204` | 4,180 | `d44527c7b8c8041faa46da1d060290b4996158ef0225511f795637e3d6d402b4` |
| `server_config/nginx/vhost/nginx/ba_mitm.conf.bak.ca2` | 1,245 | `fab572b5a4d8d749ea070a1b37d3a80cb46dee016b6cb0ce02db300eafd491de` |
| `server_config/nginx/vhost/nginx/ba_mitm.conf.bak.http_servers` | 1,245 | `fab572b5a4d8d749ea070a1b37d3a80cb46dee016b6cb0ce02db300eafd491de` |
| `server_config/nginx/vhost/nginx/ba_mitm.conf.dto1.1794592420` | 3,742 | `9d6c782d1eb6ebbfa1f0a8ff94a2d299f120e881743efc399a70c5d2da6ec85e` |
| `server_config/nginx/vhost/nginx/ba_mitm.conf.gwlog.1794593571` | 3,755 | `b6df86390074216975e3016a9f668ab9883f80615e4d8d0e186f68c56fdc8225` |
| `server_config/nginx/vhost/nginx/ba_mitm.conf.hdrprobe.1794594221` | 3,810 | `9348fd08f8fa44a0196c1ebceceda68da5b6cc670e02f52747820cf37ae87212` |
| `server_config/nginx/vhost/nginx/ba_mitm.conf.probe1.1794591887` | 1,246 | `99c89f38f1e5c9e369e2644b71cb16781cbba79dca2104b2fb9add534a65815b` |
| `server_config/nginx/vhost/nginx/ba_mitm.conf.staticmitm.1794602100` | 4,180 | `d44527c7b8c8041faa46da1d060290b4996158ef0225511f795637e3d6d402b4` |
| `server_config/nginx/vhost/nginx/ba_mitm.conf.struct1.1794592094` | 1,264 | `87b1f0b1f0bf1715da74b4db61f6d66bcf138d9f43ba5c67449bced9b4818895` |
| `server_config/nginx/vhost/nginx/free_waf.conf` | 280 | `c0ed6e0acd5019f193169467ac7f1e9798eab6d087259e2f6fd117ca24de8355` |
| `server_config/nginx/vhost/nginx/phpfpm_status.conf` | 1,835 | `7bd66aa93d217d6f1f07190ed77de5d3cf4d13e44a72d537fc16bded44789e2a` |
| `server_config/nginx/vhost/nginx/waf2monitor_data.conf` | 169 | `1361b7ab989c7d539e318269a574b9a944d044fe178296d4731e4990d8a4035d` |
| `server_config/nginx/vhost/nginx/example.com.conf` | 7,233 | `ee01b5042d44e584f7684c5c6800f024ed99a0456fbc14012e2d87bd659d1a04` |
| `server_config/nginx/vhost/nginx/example.com.conf.bak` | 4,422 | `fd1bd7d29e2be87b2e775659f3f4bd81221a3cd0040deaf24aec398e4c132262` |
| `server_config/nginx/vhost/nginx/example.com.conf.bak.1794587866` | 5,186 | `e70a7378ab4d133d1db709598b63d22c0c042b925597e902cdf92112f2e67b0c` |
| `server_config/nginx/vhost/nginx/example.com.conf.bak.1794588172` | 5,590 | `5d54a749ab31e60a36d05eb3028617bc5b59a3bd6f9368985c166b2a98b8ea79` |
| `server_config/nginx/vhost/nginx/example.com.conf.bak.1794588447` | 5,588 | `ddac4d2b0669ecff74384ae0256547cabad7cae3c73498c84e1f6485a8ff663a` |
| `server_config/nginx/vhost/nginx/example.com.conf.bak.20261117-020244` | 5,600 | `45420d85f8106099bc950590f076a31e4f30dfd37d696359d2d0a29f03db7dca` |
| `server_config/nginx/vhost/nginx/example.com.conf.probe1.1794591887` | 5,587 | `b42deed9b8587138e7a521a309579c106cee8d5f272c081cf06f4219c413c2d0` |
| `server_config/nginx/vhost/nginx/example.com.conf.sync1.1794592879` | 5,605 | `890176f7a8d42789cedaf07e86c6ad9d8b10fb4ba7191e467d21e38629525b63` |

### `server_config/nginx/vhost/nginx/extension/server_ip/` — 1 文件 / 88 B

| 相对路径（zip 内） | 字节 | sha256 |
|---|---:|---|
| `server_config/nginx/vhost/nginx/extension/server_ip/site_total.conf` | 88 | `b05ae1e47b4e552765c804ea012d642411f0a5977522923629fb90c6250973fb` |

### `server_config/nginx/vhost/nginx/extension/example_tech/` — 1 文件 / 88 B

| 相对路径（zip 内） | 字节 | sha256 |
|---|---:|---|
| `server_config/nginx/vhost/nginx/extension/example_tech/site_total.conf` | 88 | `4e048bd212679b449eb7b2aef6863e757fd8f87d711baacd5bfc59a4c9d751d2` |

### `server_config/nginx/vhost/nginx/extension/example.com/` — 1 文件 / 88 B

| 相对路径（zip 内） | 字节 | sha256 |
|---|---:|---|
| `server_config/nginx/vhost/nginx/extension/example.com/site_total.conf` | 88 | `98556f208fb0063887573095ee01e03e0c2cbeaf6335dd07bdb7abe19790e91f` |

### `server_config/nginx/vhost/nginx/tcp/` — 4 文件 / 5,617 B

| 相对路径（zip 内） | 字节 | sha256 |
|---|---:|---|
| `server_config/nginx/vhost/nginx/tcp/ba_sni.conf` | 1,653 | `bc2876274bbdf02e29660dc93e408edf7621dcd3438cce29dc63768aa130ec8a` |
| `server_config/nginx/vhost/nginx/tcp/ba_sni.conf.bak.1794776148` | 1,397 | `d7bf99be2c40fc52069ca53a28527cd5e7b31c480ae952781a7ec0a234b85e53` |
| `server_config/nginx/vhost/nginx/tcp/ba_sni.conf.staticmitm.1794602100` | 1,397 | `d7bf99be2c40fc52069ca53a28527cd5e7b31c480ae952781a7ec0a234b85e53` |
| `server_config/nginx/vhost/nginx/tcp/ba_sni.conf.staticpass.1794594637` | 1,170 | `8a114f43462905d80b14a38c688d3cb1282ec646c434e58a74082878178dee13` |

### `server_config/nginx/vhost/nginx/well-known/` — 10 文件 / 4,208 B

| 相对路径（zip 内） | 字节 | sha256 |
|---|---:|---|
| `server_config/nginx/vhost/nginx/well-known/server_ip.conf` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `server_config/nginx/vhost/nginx/well-known/example_tech.conf` | 1,052 | `060d926803d7385bb9a664f83295d1e74b16adfe144a70417f19de0301d7c0b1` |
| `server_config/nginx/vhost/nginx/well-known/saiche.conf` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `server_config/nginx/vhost/nginx/well-known/example.com-3.conf` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `server_config/nginx/vhost/nginx/well-known/example.com.conf` | 1,052 | `060d926803d7385bb9a664f83295d1e74b16adfe144a70417f19de0301d7c0b1` |
| `server_config/nginx/vhost/nginx/well-known/example.com_1027.conf` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `server_config/nginx/vhost/nginx/well-known/example.com_65454.conf` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `server_config/nginx/vhost/nginx/well-known/example.com_80.conf` | 1,052 | `060d926803d7385bb9a664f83295d1e74b16adfe144a70417f19de0301d7c0b1` |
| `server_config/nginx/vhost/nginx/well-known/example.com_88.conf` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `server_config/nginx/vhost/nginx/well-known/example.com-2.conf` | 1,052 | `060d926803d7385bb9a664f83295d1e74b16adfe144a70417f19de0301d7c0b1` |

### `server_config/systemd/` — 3 文件 / 1,745 B

| 相对路径（zip 内） | 字节 | sha256 |
|---|---:|---|
| `server_config/systemd/ba-bridge.service` | 479 | `410e27a5d288318f55a892707b92b96d3dd9d22648ae1b2f3b2efab1e45dc287` |
| `server_config/systemd/ba-sdk.service` | 449 | `10ecdf08522a810b6f8074dc5e1ef9371972da40a20c29915cc8a5b1d03d2035` |
| `server_config/systemd/ba-shittim.service` | 817 | `d1f6eb93854b18bd6d0ca17c8b500c0f0d10cb235d118005d3ebf459ae2a7bb3` |

### `docs_all/` — 423 文件 / 10,371,908 B（全部文档全集，逐条明细见 `MANIFEST_ZIP.txt` §3 之外的对应行）

---

## 4. 包里没有的东西，以及为什么

| 缺失项 | 规模 | 原因 |
|---|---:|---|
| **上游服务端源码**（原 `服务端源码\`，1,324 文件） | 11,922,062 B（11.37 MiB） | **用户明确要求不带**；2026-11-20 已从本交付目录删除，源目录未动 |
| **上游客户端相关**（原 `客户端相关\`，324 文件） | 6,609,709 B（6.30 MiB） | 同上（用户要求只留自研内容） |
| **成品 APK**（`apk_patch\out\` 5 个 APK） | 10,660,372,241 B（9.93 GiB） | 太大；单个最大 `BlueArchive_cardlogin_v1.apk` 2,133,476,336 B |
| 构建产物 `srv_src\_build_*\`（20 个目录） | 1,379,477,381 B（1.29 GiB） | `dotnet build` 可重建 |
| 解压目录 `apk_patch\decode\`（17,710 文件） | 167,598,935 B（159.8 MiB） | 体积超限，且可由原版 APK 重新解出 |
| `libil2cpp.so`（`noroot\_tmp\`） | 270,927,056 B（258.4 MiB） | 大二进制，无补丁价值 |
| `audit\ba-apk\lib\` 24 个 .so（含 `libunity.so` 20,950,552 B） | 317,375,216 B（302.7 MiB） | 同上 |
| `server\deploy\_noroot\`（26 文件） | 4,262,928,771 B（3.97 GiB） | APK / 日志搬运区 |
| `apk_patch\backup\` + `noroot\BA_noroot*_v1.apk`（3 个 2 GB 级 APK） | 2,127,971,177 B ×2 + 2,127,962,985 B | 2 GB 级成品 |
| 原 `MANIFEST_服务端源码.txt` / `MANIFEST_客户端相关.txt` | 152,894 B / 33,448 B | 描述的就是上面被删的上游内容，2026-11-20 一并删除 |
| `.git` | — | 源树全树就没有 `.git`（0 命中） |
| `*.pdb`、`*.deps.json`、`TestResults\`、`.vs\`、`__pycache__\` | — | 按打包规则排除 |
| panel_full 的 `state/precsrf_*.json`（67 个） | 3,819 B | 运行期一次性预登录 CSRF 票据（登录即生成、用后即弃），含令牌，无还原价值；详见 §6 |

---

## 5. 怎么用

### 5.1 先解压

```powershell
$dst = 'C:\Users\su\Desktop\BA_自研补丁_20261120'
Expand-Archive -LiteralPath 'C:\Users\su\Desktop\BA_交付_20261120\BA_自研补丁_20261120.zip' -DestinationPath $dst -Force
Get-ChildItem -LiteralPath $dst
```
Linux 侧等价：`unzip BA_自研补丁_20261120.zip -d /tmp/ba_self`。

### 5.2 DLL 放哪

| zip 内 | 线上位置 |
|---|---|
| `server/Shittim-Server.dll` | `/www/wwwroot/ba_srv/Shittim-Server.dll` |
| `server/Schale.dll` | `/www/wwwroot/ba_srv/Schale.dll` |

覆盖后重启服务端进程 `ba-shittim`（OOM 注意事项见 `docs/SERVER_RESTART_OOM.md`、`docs/SWAP_1G.md`）。
`Shittim-Server.dll` 的 sha256 = `c013f442…`，与 2026-11-20 线上一致。

> **本包已不带服务端源码**，新机器上无法从源码重建 DLL，只能部署这份已编译产物；要改源码请回 `work\ba\`（源目录）。

### 5.3 桥怎么起

| zip 内 | 线上位置 |
|---|---|
| `bridge/account_auth_probe.py` | `/www/wwwroot/bapatch/tools/account_auth_probe.py` |
| `bridge/90004_ops.json` | `/www/wwwroot/bapatch/_ba_state/90004_ops.json` |

```bash
systemctl restart ba-bridge
systemctl status ba-bridge --no-pager
ss -lntp | grep :9097
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:9097/   # 期望 200
```

- 单元文件全文在 `bridge/BRIDGE_SYSTEMD.md`（`WorkingDirectory=/www/wwwroot/bapatch/tools`、`Restart=always`、端口 9097）。
- 日志：`/www/wwwroot/bapatch/logs/bridge_stdout.log`。
- 首次安装：`systemctl daemon-reload && systemctl enable --now ba-bridge`。
- **包内 `bridge/account_auth_probe.py` 已是线上真身（228,775 B / `15758f0e…`），可直接覆盖；`bridge/_history/` 两份旧副本只作留存，不要上传。**

### 5.4 面板文件放哪

站点根：`/www/wwwroot/ba_cardadmin`

| zip 内 | 放到 |
|---|---|
| `panel/inc/gacha.php` | `inc/gacha.php` |
| `panel/pages/gacha_rates.php` | `pages/gacha_rates.php` |
| `panel/inc/gm_lobby.php` | `inc/gm_lobby.php` |
| `panel/pages/items.php` | `pages/items.php`（24,248 B，11-19 23:39 的 gm_lobby 版） |
| `panel/inc/helpers.php` | `inc/helpers.php`（与 p0rates 版逐字节相同，sha256 `0bd35a74…`，**无独立 diff**） |
| `panel/variant_p0rates/pages/items.php` | 早期变体（15,807 B / 11-19 02:37），**仅作对照，不要直接上线** |

改完先 `php -l` 过一遍，再刷新面板；`inc/gm_lobby.php` 与 `pages/items.php` 是 11-19 23:43 那次上线的一对。

**要还原整站**：把 `panel_full/ba_cardadmin/` 整个目录放到 `/www/wwwroot/ba_cardadmin/`（PHP 站点根），确认 `config.php` 里的 DB 口令 / APP_SECRET 与目标库一致、根目录有 `installed.lock`（`inc/db.php` 据此判断 `CARDADMIN_INSTALLED`，缺了会走未安装引导），并给 `state/` 写权限；`state/` 只带 7 个非票据状态文件，登录票据会在首次登录时自动重新生成，不需要 `precsrf_*` 历史票据。

### 5.5 补丁脚本怎么跑

全部在解压目录里执行：

**90004（服务端运营数据）**

```powershell
python bridge\verify_90004.py          # 打 http://127.0.0.1:9097/api/management/data 校验
python bridge\patch_90004.py --verify  # 校验已打补丁的桥脚本
```

判定线：31 项检查、FAIL=0（唯一 WARN 是 `SessionKey` 为空，属预期）。
配套：`bridge\preflight_90004.py`（预检）、`bridge\selftest_90004.py`（自检）、`bridge\check_patch_90004.py`、`bridge\make_ops_90004.py`、`bridge\deploy_all.py`（编排）。

**客户端（APK）**
- 构建/补丁脚本：`client/apk_patch/scripts/`（45 个文件：.py/.sh/.log）
- 免 root 构建：`client/noroot/build_noroot_apk.py`
- 直接上的 smali / layout：`client/apk_patch/patched/`（3 个 .smali + 1 个 layout xml）
- 布局试验与自检：`client/apk_patch/v4/`、`client/apk_patch/v5/`（含 `res_Q9_v5.axml`、`SELFTEST_v5.md`）
- 2 GB 成品 APK **没有带**（见第 4 节），用这些脚本 + 原版 APK 自行重打。
- 签名材料 `client/noroot/ba_private.keystore` / `ba_private.key.pem` / `ba_private.cert.pem` **注意保管，不要外传**。

---

### 5.6 `server_config/` 与 `bridge_tools/` 怎么用（本次新增）

两者都是**线上快照的参考件**，不是"复制过去就能跑"：所有口令/域名/IP/证书路径已换成占位符，落盘前照 `REDACTION.md` 逐条替换。

| 快照目录 | 对应线上位置 | 用法 |
|---|---|---|
| `server_config/nginx/nginx_conf/` | `/www/server/nginx/conf/` | **对照**你机器上的 nginx 主配置，只抄 `include`/`log_format`/`limit_req_zone` 等行；**别整目录覆盖** |
| `server_config/nginx/vhost/nginx/` | `/www/server/panel/vhost/nginx/` | 站点 vhost 参考（`ba_mitm.conf` 是主导流、`tcp/ba_sni.conf` 是 SNI 分流）；按 `DEPLOY_一键部署.md` §3.6 逐条改 |
| `server_config/systemd/` | `/etc/systemd/system/` | 三个 unit 的**字段参考**；`User`/`WorkingDirectory`/`ExecStart`/日志目录必须按你的路径改（§3.3） |
| `server_config/bapatch_root/` | `/www/wwwroot/bapatch/` 根级 | 27 个 `cn_*.txt` 是**行为开关**（`bridge`/`forward`、`0`/`1`…），先原样拷过去，再按 §3.4 与 §7 第 1 条核对 |
| `server_config/ba_sdk/` | `/www/wwwroot/ba_sdk/` | `resp/` 是官方响应快照，`sdkcard.py` 是 SDK 主程序；检测地址要改成你的（§3.7） |
| `bridge_tools/tools/` | `/www/wwwroot/bapatch/tools/` | **整目录拷**（182 个文件）；带时间戳的 `.bak.*` / `.pre_*` 是历史变体，运行时不会用到，留着只为对照 |
| `bridge_tools/_ba_state/` | `/www/wwwroot/bapatch/_ba_state/` | `90004_ops.json` 运营数据；先跑 `verify_90004.py` 确认结构再打补丁 |

```bash
# 拷完先做三件事（都在服务器上，且不联网）
cd /www/wwwroot/bapatch/tools && python3 verify_90004.py     # 期望 RESULT: PASS
grep -rl '<REDACTED_\|<SERVER_IP>\|<CERT_PATH>' /www/wwwroot/bapatch /www/wwwroot/ba_sdk /www/server/panel/vhost/nginx  # 有输出 = 还有占位符没替换
systemctl daemon-reload && systemctl restart ba-bridge ba-sdk ba-shittim
```


---

## 6. 已知缺口（如实记录）

> ### ✅ 第一条（已解决）：zip 里的桥**已替换为线上真身**
>
> - 2026-11-20 23:50 从线上拉取 `/www/wwwroot/bapatch/tools/account_auth_probe.py`：**228,775 B**，sha256 **`15758f0e…`**（md5 `891178d6…`，与 `bridge/BRIDGE_SYSTEMD.md` §5 记录一致）。
> - 该真身已写入包内 `bridge/account_auth_probe.py`；**本次统一脱敏后为 228,784 B**（`9060ed7c…`），差异**仅为**脱敏替换掉的令牌/域名/IP 等字面值，逻辑代码未动。
> - 原两份旧副本**保留未删**，移入 `bridge/_history/` 并按「版本 + hash」改名：`account_auth_probe.p90004-16d4efcb.py`（167,430 B / `16d4efcb…`）、`account_auth_probe.v222486-6756a5de.py`（228,722 B / `6756a5de…`）；本次同样按脱敏规则改写（+4 B / +8 B）。
> - 本次只改桌面压缩包内部：服务器一字节未动，`work\ba\` 源目录只读拉取、未写入。

| 目标 | 状态 | 处理与证据 |
|---|---|---|
| `work\ba\server\deploy\_ba_state\` 目录 | **未找到** | 全 `work\ba` 树递归搜索 `*_ba_state*`，0 命中。它是**线上路径** `/www/wwwroot/bapatch/_ba_state/`；本地对应物是 `_p90004\90004_ops.json`（sha256 `938ae908…`，与 `D90004_DEPLOY.md` 记录的 90004 运营数据 hash 一致），已收进 zip 的 `bridge/90004_ops.json` |
| 线上桥脚本的字节级副本 | **已解决** | 2026-11-20 23:50 拉取线上真身（228,775 B / `15758f0e…`），已替换包内 `bridge/account_auth_probe.py`；两份旧副本移入 `bridge/_history/` 保留 |
| `inc\helpers.php` 的独立改动说明 / diff | **未找到** | 没有单独的 diff 文档；`gm_lobby` 与 `p0rates` 两份 helpers.php 逐字节相同（sha256 `0bd35a74…`），说明本次改动集中在 `inc/gacha.php`、`pages/gacha_rates.php`、`inc/gm_lobby.php`、`pages/items.php` |
| `patch_90004.py` 在 `_p90004\` 下 | 不在该目录 | 实际在 `server\deploy\patch_90004.py`，已收进 `bridge/patch_90004.py`（sha256 `c94bae46…`，与 `D90004_DEPLOY.md` 记录一致） |
| `dto90004.py` | 找到 | `server\deploy\dto90004.py` → `bridge/dto90004.py` |
| `90004_ops.json` / `expected_90004.json` / `verify_90004.py` | 找到 | 均在 `_p90004\`，已收进 `bridge/` |
| 6 份 id 白名单 + `ClientItemIds.txt` | 找到 | 7 个文件全在 `Shittim-Server\Resources\`，现收在 zip 的 `server/Resources/` |
| 线上版 `Shittim-Server.dll`（`c013f442…`） | 找到 | `_build_p0rates\Shittim-Server.dll`，sha256 与 `c013f442…` 完全一致 |
| `GachaRecruitBanners.cn.json`（529 条） | 找到 | 40,739 B，`"Id"` 计数 529 |
| `panel_full/` 里的 `state/precsrf_*.json`（67 个） | **刻意排除** | 该次线上拉取快照共 120 文件，其中 `state/precsrf_*.json` **67 个 / 3,819 B**（每个 57 B）是**运行期一次性预登录 CSRF 票据**（登录时生成、登出/过期即弃，内容为带 token 的一次性票据），对还原站点无价值，且多一份令牌就多一分外泄面，故**不进包**。**口径说明**：交接要求里写的是 74 个，实测 `state/` 目录共 **74 个条目** = 67 个 precsrf + 3 个 bacache + `cards.backup.json` + 2 个 `otok_*.json` + `.htaccess`；precsrf 本体是 **67 个**，本文件按实测数记录 |
| 包内的**文件名**曾带出包域名/IP | **第二轮已改名（2026-11-21）** | 第一轮按红线只改内容、不改名；第二轮把 **23** 条（21 文件 + 2 目录）改成 `example.com` / `server_ip`，撞名加 `-2`/`-3`，并同步更新包内引用。**注意**：改名后这些 vhost 文件名不再与线上逐字一致，核对线上时请按 `REDACTION.md` 末节的改名清单反查。`MANIFEST.txt`／`REDACTION.md` 的路径列现在只剩 `example.com` / `server_ip` |
| `client/noroot/ba_private.keystore` 等签名材料 | **二进制，未做文本脱敏** | 红线：绝不 redact 二进制（改了会坏签名）。该文件是出包环境的签名私钥，**部署时必须用 `--gen-keystore` 生成你自己的**，否则别人能签同名包冒充你 |

---

---

## 7. 变更记录（2026-11-20 精简 + 历次重打包，可核对）

| 动作 | 对象 | 文件数 | 字节 |
|---|---|---:|---:|
| 删除 | `BA_交付_20261120\服务端源码\` | 1,324 | 11,922,062 |
| 删除 | `BA_交付_20261120\客户端相关\` | 324 | 6,609,709 |
| 删除 | `MANIFEST_服务端源码.txt` | 1 | 152,894 |
| 删除 | `MANIFEST_客户端相关.txt` | 1 | 33,448 |
| **合计删除** | — | **1,650** | **18,718,113** |
| 改名 | `我们写的补丁与成品.zip` → `BA_自研补丁_20261120.zip` | — | 4,197,452（改名时 sha256 前后一致） |
| 包内替换 | `bridge/account_auth_probe.py` ← 线上真身 | — | 167,430 → 228,775（sha256 `16d4efcb…` → `15758f0e…`） |
| 包内移动 | 两份旧副本 → `bridge/_history/`（改名带版本 + hash） | 2 | 396,152（字节未变，仅改路径与文件名） |
| 重打包 | `BA_自研补丁_20261120.zip` | 363 条目 | 4,197,452 → 4,262,879（sha256 `27DA7CB5…` → `5A25A07D…`） |
| 重写 | `README.md`（本文件） | — | — |
| 重写 | `MANIFEST_ZIP.txt` | 1 | 39,269 → 40,008（换成重打包后的全量清单：362 行逐条重算 sha256，与 zip 内 `MANIFEST.txt` 逐字节相同） |
| 未动 | 源目录 `C:\Users\su\Desktop\大肥鱼项目\BAServer\work\ba\` | 0 写入 | 0 |
| **包内新增** | `docs_all/` ← `BAServer\` 全部 `.md`（只读复制，保留原相对路径，含中文名未改） | **423** | **10,377,893** |
| **重打包** | `BA_自研补丁_20261120.zip` | **786 条目** | 4,262,879 → **8,442,935**（sha256 `5A25A07D…` → `6CF45959…`） |
| **重写** | `MANIFEST_ZIP.txt` | 1 | 40,008 → **93,274**（785 行全量重算：字节 + sha256，与 zip 内 `MANIFEST.txt` 逐字节相同） |
| **重写** | `README.md`（本文件） | — | 新增 §1.2 与 §3 `docs_all/` 汇总；更新大小 / sha256 / 条目数 / 解压后合计 / 结构树 |
| 未动 | `docs/` 18 份精选文档 | 0 改动 | 364,747（逐份 sha256 与上一版完全一致） |
| 未动 | 上一版 344 份非文档文件（`bridge/` `client/` `server/` `panel/`） | 0 改动 | 13,588,668（逐份 sha256 与上一版完全一致） |
| 未动 | `BAServer\work\ba\` 下任何 `.md` 内容 | 0 写入 | 0（只读复制 + 只读哈希；无改名/无编辑/无移动） |
| **包内新增** | `panel_full/ba_cardadmin/` ← 线上整站只读快照（保留目录结构，未改名） | **54** | **760,707** |
| **重打包** | `BA_自研补丁_20261120.zip` | **840 条目** | 8,442,935 → **8,679,789**（sha256 `6CF45959…` → `63D9E5B2…`） |
| **重写** | `MANIFEST_ZIP.txt` | 1 | 93,274 → **99,914**（839 行全量重算：字节 + sha256，与 zip 内 `MANIFEST.txt` 逐字节相同） |
| **重写** | `README.md`（本文件） | — | 新增顶部凭据警告 + `panel_full/` 章节；更新大小 / sha256 / 条目数 / 解压后合计 / 结构树 / 自检 |
| 未动 | `bridge/` `client/` `docs/` `docs_all/` `panel/` `server/` 785 份 | 0 改动 | 24,331,308（逐份 sha256 与上一版完全一致） |
| 未动 | 服务器 | 0 次 ssh / 0 次 scp / 0 重启 / 0 部署 | 本次全在本地打包 |

| **包内新增** | `server_config/` ← 线上服务端配置快照（nginx / systemd / bapatch 根级 / ba_sdk / 快照 `SHA256SUMS.txt`），保留相对结构、当轮未改名（第二轮另行改名 18 文件 + 2 目录） | **149** | **1,601,417** |
| **包内新增** | `bridge_tools/` ← 桥工作目录快照（`tools/` 182 + `_ba_state/` 1），未改名 | **183** | **7,526,265** |
| **包内新增** | `DEPLOY_一键部署.md`（包根）、`REDACTION.md`（包根，脱敏台账） | **2** | **199,336** |
| **统一脱敏** | 包内文本文件统一替换真实凭据/域名/IP/证书路径/设备指纹/联系方式 | **293** | **1,938 处 / 1,736 行**（二进制 0 改动） |
| **重打包** | `BA_自研补丁_20261120.zip`（.NET `ZipArchive`，正斜杠，不用 `Compress-Archive`） | **1,174 条目** | 8,679,789 → **10,906,727**（sha256 `63D9E5B2…8EB75` → `6F2996C1…`） |
| **重写** | `MANIFEST_ZIP.txt` | 1 | 99,914 → **140,057**（1,173 行全量重算：字节 + sha256，与 zip 内 `MANIFEST.txt` 逐字节相同） |
| **重写** | `README.md`（本文件） | — | 顶部警告改为"已脱敏 + 上游加固"；新增 `server_config/` `bridge_tools/` `REDACTION.md` `DEPLOY_一键部署.md` 章节；全部数字重算 |
| **校验** | 解压到**全新空目录**按清单逐条比对 | 1,174 | **1,173/1,173 字节 + sha256 全部通过**，缺失 0、多余 0；残留扫描：真实域名/IP/证书路径 **0 命中** |
| **文件名脱敏**（第二轮） | 路径里带真实域名/IP 的文件名与目录名 → `example.com` / `server_ip` | **23**（21 文件 + 2 目录） | 只改名、不动字节内容；撞名加 `-2`/`-3`；逐条见 `REDACTION.md` 末节 |
| **引用同步** | `REDACTION.md` 路径列 10 处 + `server_config/SHA256SUMS.txt` 2 处 + `GameMainConfig_http_*.bin` 文件名引用 4 文件 / 5 处（`docs_all/` 副本另 3 文件 / 4 处） | 8 | 引用旧名的文本一并更新，包里不留悬空路径 |
| **重打包**（第二轮） | `BA_自研补丁_20261120.zip`（.NET `ZipArchive`，正斜杠，不用 `Compress-Archive`） | **1,174 条目** | 10,906,727 → **10,908,159**（sha256 `6F2996C1…` → `51E24C09…`） |
| **重写**（第二轮） | `MANIFEST_ZIP.txt` / `MANIFEST.txt` | 1 | 140,057 → **139,728**（1,173 行全量重算；与 zip 内 `MANIFEST.txt` 逐字节相同） |
| 未动 | 服务器 | 0 | 0 次 ssh / 0 次 scp / 0 重启 / 0 部署（本任务纯本地） |
| 未动 | 源目录 `work\ba\`（含 `SRVCFG_20261120\`、`plan\20261120\`） | 0 写入 | 只读复制 + 只读哈希；包内副本才被改写 |

删除前逐个打印并校验：4 个目标全部 `FullName` 位于 `C:\Users\su\Desktop\BA_交付_20261120\` 之下、且均非 junction / reparse point（全目录 reparse 计数 = 0），才执行 `Remove-Item`。

**`docs_all/` 扫描时按排除规则跳过的 21 份 `.md`**（全部落在 `_build_*` 构建目录下；其余排除目录 `apk_patch\decode`、`audit\ba-apk\jadx`、`audit\ba-apk\out`、`node_modules`、`.git`、`bin`、`obj`、`packages` 在本树内 0 命中）：

```
work\ba\server\deploy\_build_banexp\CHECK.md
work\ba\server\deploy\_build_banpage\CHECK.md
work\ba\server\deploy\_build_banreply\NOTES.md
work\ba\server\deploy\_build_banreply\VERIFY.md
work\ba\server\deploy\_build_banreply2\NOTES.md
work\ba\server\deploy\_build_banreply2\VERIFY.md
work\ba\server\deploy\_build_cardformat\CHECK.md
work\ba\server\deploy\_build_cardformat\PATCH_SPEC.md
work\ba\server\deploy\_build_cardtype2\CHECK.md
work\ba\server\deploy\_build_cardtype2\_work\audit_tables.md
work\ba\server\deploy\_build_devban\NOTES.md
work\ba\server\deploy\_build_gatefix\NOTES.md
work\ba\server\deploy\_build_gatefix\VERIFY.md
work\ba\server\deploy\_build_multiacct\SITES.md
work\ba\server\deploy\_build_multiacct\VERIFY.md
work\ba\server\deploy\_build_purgefix\CHECK.md
work\ba\server\deploy\_build_purgefix\NOTES.md
work\ba\server\deploy\_build_sdkaccount\NOTES.md
work\ba\server\deploy\_build_sdkaccount\VERIFY.md
work\ba\server\deploy\_build_sidwb\NOTES.md
work\ba\server\deploy\_build_ttl\NOTES.md
```

> 扫描口径：`BAServer\` 递归 `*.md` 共 **445** 份；排除 21 份 → 收进 `docs_all/` **423** 份 / 10,377,893 B。路径重复检查：423 个相对路径按大小写不敏感比对，**0 组重复**。

---

## 8. 自检

- 重打包后 zip sha256：`3FA74D736ED035B05B053DF3B62B86344FD5674ACB8AA76CD2E7A6C557AC0D89`（**10,908,159 B**；上一版 `6F2996C1…` / 10,906,727 B，再上一版 `63D9E5B2…8EB75` / 8,679,789 B）。
- zip 中央目录条目数 **1,174**，解压后合计 **34,556,769 B** = 1,173 行清单 34,417,041 B + `MANIFEST.txt` 139,728 B，账对得上（纯压缩数据流 10,710,219 B，压缩率 30.99%）。
- 逐文件复核：新 zip 已解压到**全新空目录**，按 `MANIFEST.txt` 的 **1,173** 行逐条比对「字节 + sha256」→ **1,173/1,173 全部通过**，缺失 0、多余 0（解压出的 1,174 个文件中，唯一不在清单里的就是 `MANIFEST.txt` 自身）。
- `MANIFEST_ZIP.txt` 与 zip 内 `MANIFEST.txt` 逐字节相同（sha256 同为 `0c994c3770593fa7dada23f8ad57fa613c1b0fa5cdc1544a38a0a99e67d68a36`）。
- 脱敏复核：包内文本文件再跑一遍**同一套规则** → 待改文件 **0**；`grep -r '<REDACTED_'` 命中 **> 0**；真实域名 / 公网 IP / 自建 CA 证书路径 **0 命中**。
- 文件名复核（第二轮）：改完再扫一遍**条目名**（文件 + 目录，含正斜杠路径的每一段）→ 真实域名 **0**、真实 IP **0**（`example.com` / `server_ip` 除外）；另有 3 条正则误命中（`server/Data/<数据集>.<区服标记>.json` 2 条、`0.<名称>_total_log_format.conf` 1 条）确认不是域名，保持原名。
- 语法复核：脱敏前后逐文件比对 —— JSON 可解析性翻转 **0**、Python 可编译性翻转 **0**、括号/引号计数变化 **0**；二进制文件改动 **0**。
- 自查命令（PowerShell 5.1 必须显式 `-Encoding UTF8`，否则按 ANSI 解码会乱码）：

```powershell
$z='C:\Users\su\Desktop\BA_交付_20261120\BA_自研补丁_20261120.zip'
(Get-FileHash $z -Algorithm SHA256).Hash    # 应等于 3FA74D736ED035B05B053DF3B62B86344FD5674ACB8AA76CD2E7A6C557AC0D89
$d='C:\Users\su\Desktop\BA_自研补丁_20261120'; Remove-Item $d -Recurse -Force -ErrorAction Ignore
Expand-Archive -LiteralPath $z -DestinationPath $d
Get-Content MANIFEST_ZIP.txt -Encoding UTF8 | Where-Object {$_ -notlike '#*' -and $_.Trim() -ne ''} | ForEach-Object {
  $p=$_.Split("`t"); $f=Join-Path $d $p[0].Replace('/','\')
  $ok = ((Get-Item $f).Length -eq [int64]$p[1]) -and ((Get-FileHash $f -Algorithm SHA256).Hash.ToLower() -eq $p[2])
  if(-not $ok){ Write-Host "FAIL $($p[0])" }
}   # 无输出 = 1,173/1,173 全过
```
