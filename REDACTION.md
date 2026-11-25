# REDACTION.md · BA 自研补丁交付包（20261120）· 统一脱敏逐条清单

> 本文件是**脱敏台账**：逐文件、逐行列出「哪个字段被换成了哪个占位符」。
> **本文件不含任何原值**——连原值的前几位、长度区间、特征都不写；只有占位符、行号与字段名。
>
> **文件名**：第一轮只改内容、不改名；**第二轮（2026-11-21）已把 23 条含真实域名/真实 IP（含 1 条域名品牌词）的文件名与目录名改为 `example.com` / `server_ip`**（只改名字，不动字节内容），见文末「§ 文件名脱敏」。本文件第 4 节的路径列**已是新名字**。

| 项 | 值 |
|---|---|
| 生效包 | `BA_自研补丁_20261120.zip`（包根即本文件所在目录） |
| 脱敏对象 | 包内**文本文件**（`.php .py .sh .json .js .css .html .ini .conf .service .md .txt .sql .user.ini` 及无扩展名的纯文本 nginx 片段） |
| 扫描文本文件 | **1096** 个 |
| 跳过（二进制，未打开写入） | **77** 个：`*.dll *.pyc *.png *.jpg *.ico *.woff* *.ttf *.zip *.dat *.db *.pem *.key *.crt` 等 |
| 实际改动文件 | **293** 个 |
| 替换总处数 | **1938** 处 |
| 替换总行数 | **1736** 行（下表行数） |
| 保留项 | 换行符（LF/CRLF）、编码（UTF-8 无 BOM）、文件权限位；文件名：第一轮未改，第二轮（2026-11-21）按文末「§ 文件名脱敏」改名 22 条 |

## 1. 汇总表（按占位符类别）

| 类别 | 占位符 | 改动文件数 | 替换处数 |
|---|---|---:|---:|
| 数据库口令/用户 | `<REDACTED_DB_CREDENTIAL>` | 9 | 10 |
| 应用密钥 | `<REDACTED_SECRET>` | 1 | 1 |
| 令牌/会话 | `<REDACTED_TOKEN>` | 110 | 341 |
| 设备指纹 | `<REDACTED_DEVID>` | 8 | 27 |
| 邮箱/手机号 | `<REDACTED_CONTACT>` | 9 | 23 |
| 公网 IP | `<SERVER_IP>` | 74 | 281 |
| 证书路径 | `<CERT_PATH>` | 42 | 128 |
| 真实域名 | `example.com` | 116 | 1127 |
| **合计** | — | **293**（文件去重） | **1938** |

## 2. 替换规则口径（据此可复核）

| 类别 | 命中什么 | 换成什么 |
|---|---|---|
| 数据库口令/用户 | `DB_PASS` / `DB_PASSWORD` / `DB_USER` / `MYSQL_*` / `password` / `passwd` / `pwd` 的**字面量值**（`define(...)`、`k = '…'`、`k: "…"`、`k=…`） | `<REDACTED_DB_CREDENTIAL>` |
| 应用密钥 | `APP_SECRET` / `AdminApiKey` / `BA_ADMIN_KEY` / `SECRET` / `APIKEY` / `SDK_KEY` / `SIGN_KEY` / `APPKEY` / 全大写 `*_KEY` 的字面量值 | `<REDACTED_SECRET>` |
| 令牌/会话 | `token` / `MxToken` / `access_token` / `refresh_token` / `session_key` / `sessionid` 的字面量值 | `<REDACTED_TOKEN>` |
| 设备指纹 | `DeviceUniqueId` / `device_unique_id` / `devid` / `dev_id` / `device_id` 的字面量值 | `<REDACTED_DEVID>` |
| 真实域名 | 本项目出包域名本身，以及其 `www.` 前缀形式（大小写不敏感） | `example.com` |
| 公网 IP | 出包服务器的公网地址 | `<SERVER_IP>` |
| 证书路径 | 出包环境自建 CA 目录（`ca` + 数字命名的若干子目录）下的整条路径字符串，以及宝塔面板站点证书目录下的整条路径字符串 | `<CERT_PATH>` |
| 邮箱/手机号 | 形态合法的邮箱地址、11 位大陆手机号（整词匹配） | `<REDACTED_CONTACT>` |

**判定细则（避免误伤）**：值已经是 `<…>` 占位符 / `CHANGE_ME` 类模板串 / 纯数字 / 布尔 / `null` / PHP 变量 / 函数调用 / 表达式 / 文件路径的，**一律不动**；手机号要求两侧非字母数字（不误伤 sha256、十六进制转储）；邮箱要求域名首字符为字母且 TLD 合法（不误伤 `systemd-zram-setup@zram0.service` 这类 unit 名与资源包用户名 `xxx@3.0`）。

**文档树（`docs/`、`docs_all/`、全部 `*.md`）只做「真实域名 / 公网 IP / 证书路径 / 邮箱 / 手机号」五类替换**，其余内容（本来就写成占位符的段落）**保持不动**。

## 3. 明确**没有**处理的东西（防止误以为漏做）

| 对象 | 原因 |
|---|---|
| 全部二进制文件（`.dll .pyc .png .jpg .ico .woff* .ttf .zip .dat .db .pem .key .crt .keystore` 等 **77** 个） | 按红线：**绝不 redact 二进制**（改了会坏签名/坏文件）。其中 `client/noroot/ba_private.keystore` 是签名私钥，部署时**必须换成你自己生成的** |
| 文件名与目录名 | **第一轮不改名**（红线）；**第二轮（2026-11-21）已改名 22 条**（20 文件 + 2 目录）：真实域名 → `example.com`、真实公网 IP → `server_ip`，撞名加 `-2`/`-3`，清单见文末「§ 文件名脱敏」。因此本文件第 4 节的路径列里**已经看不到真实域名/IP**；这些文件的内容替换仍按本节口径 |
| 第三方 / 官方公开数据 | 例如游戏内公告正文里的官方客服邮箱、抓包记录里的对端 IP、DNS 与 X.509 OID 中的点分数字、Unity 资源包里的许可串——非本项目凭据 |
| `SHA256SUMS.txt` 的哈希列 | 只替换其中的路径字符串；哈希值逐字节未动（哈希列不可能与替换值相撞） |

> ⚠️ 若你在包内发现**任何 `<REDACTED_*>` 之外的可疑真实凭据**（口令、密钥、令牌、域名、公网 IP、手机号、邮箱），请**立即反馈**，不要直接拿去部署。

## 4. 逐条清单（按文件分组）

格式：`文件相对路径` → 表格「行号 | 字段 | 该行被替换成的占位符」。同一行替换了多个位置时 `计数` 列给出处数。

### `MANIFEST.txt` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 325 | `server_name/host` | `example.com` | 1 |

### `bridge/_history/account_auth_probe.p90004-16d4efcb.py` — 8 处 / 7 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 318 | `mxtoken,session_key` | `<REDACTED_TOKEN>` | 2 |
| 319 | `devid` | `<REDACTED_DEVID>` | 1 |
| 319 | `token` | `<REDACTED_TOKEN>` | 1 |
| 365 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 1034 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 1097 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 2233 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge/_history/account_auth_probe.v222486-6756a5de.py` — 11 处 / 10 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 351 | `DevId` | `<REDACTED_DEVID>` | 1 |
| 448 | `DevId` | `<REDACTED_DEVID>` | 1 |
| 455 | `DevId` | `<REDACTED_DEVID>` | 1 |
| 518 | `mxtoken,session_key` | `<REDACTED_TOKEN>` | 2 |
| 519 | `devid` | `<REDACTED_DEVID>` | 1 |
| 519 | `token` | `<REDACTED_TOKEN>` | 1 |
| 566 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 1245 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 1308 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 3598 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge/account_auth_probe.py` — 11 处 / 10 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 351 | `DevId` | `<REDACTED_DEVID>` | 1 |
| 448 | `DevId` | `<REDACTED_DEVID>` | 1 |
| 455 | `DevId` | `<REDACTED_DEVID>` | 1 |
| 518 | `mxtoken,session_key` | `<REDACTED_TOKEN>` | 2 |
| 519 | `devid` | `<REDACTED_DEVID>` | 1 |
| 519 | `token` | `<REDACTED_TOKEN>` | 1 |
| 566 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 1245 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 1308 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 3598 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/_relayfix2_replay.py` — 2 处 / 2 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 20 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 72 | `MxToken` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py` — 11 处 / 10 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 351 | `DevId` | `<REDACTED_DEVID>` | 1 |
| 448 | `DevId` | `<REDACTED_DEVID>` | 1 |
| 455 | `DevId` | `<REDACTED_DEVID>` | 1 |
| 518 | `mxtoken,session_key` | `<REDACTED_TOKEN>` | 2 |
| 519 | `devid` | `<REDACTED_DEVID>` | 1 |
| 519 | `token` | `<REDACTED_TOKEN>` | 1 |
| 566 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 1245 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 1308 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 3598 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.WORKING_a_proto_int.1794605023` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 62 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 248 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 311 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 681 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.WORKING_a_proto_int.1794605032` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 62 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 248 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 311 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 681 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.WORKING_plus_emptyfallback.1794605244` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 62 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 248 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 311 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 681 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.ab27.1794604815` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 61 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 247 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 310 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 658 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.bak.20261116-063006` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 165 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 360 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 423 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 1472 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.bak.20261116_060707` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 165 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 360 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 423 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 940 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.batch1.bak.20261117_202722` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 165 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 629 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 692 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 1820 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.billingblock.bak.200735` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 165 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 543 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 606 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 1734 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.bridgev5.1794595958` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 18 | `MxToken` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.canary.1794599376` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 49 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.canarypos.1794600510` — 2 处 / 2 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 54 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 229 | `MxToken` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.cnresp.1794598994` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 47 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.cnresp.1794599022` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 47 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.e0.1794601768` — 3 处 / 3 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 61 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 247 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 310 | `MxToken` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.e1.1794603011` — 3 处 / 3 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 61 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 247 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 310 | `MxToken` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.e2.1794603124` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 61 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 247 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 310 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 598 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.e3.1794603141` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 61 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 247 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 310 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 617 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.e4.1794603502` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 61 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 247 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 310 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 634 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.encb64.1794600835` — 2 处 / 2 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 54 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 229 | `MxToken` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.encresp.1794596619` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 23 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.encresp1.1794597149` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 47 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.exp_rs0.1794596415` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 22 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.experror.1794596553` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 23 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.fieldpatch.1794599230` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 48 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.fix2.pre.20261117-024747` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 165 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 360 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 423 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 1551 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.fix2pre.183713` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 165 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 485 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 548 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 1676 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.fix3pre.183916` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 165 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 485 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 548 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 1676 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.fix5bpre.185539` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 165 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 485 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 548 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 1676 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.fix5bpreb.185600` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 165 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 485 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 548 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 1676 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.fix5pre.185409` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 165 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 485 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 548 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 1676 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.fix6pre.190003` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 165 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 485 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 548 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 1676 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.fourkeys.1794599499` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 51 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.hash.1794599435` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 50 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.http200.1794599073` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 48 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.innermin.1794600929` — 2 处 / 2 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 56 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 240 | `MxToken` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.namefix.pre.20261117-183500` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 165 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 360 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 423 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 1551 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.p3.bak.20261117-012355` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 165 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 360 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 423 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 1540 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.p3.pre.20261117-012349` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 165 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 360 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 423 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 1540 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.pre_1017.20261116_062952` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 165 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 360 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 423 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 1472 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.pre_24000soc.1794640032` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 63 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 258 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 321 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 825 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.pre_24000soc.1794640045` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 63 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 258 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 321 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 825 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.pre_24000ticks.1794639691` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 63 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 258 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 321 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 822 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.pre_24v3.20261116_060707` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 165 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 360 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 423 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 940 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.pre_90004.1794638663` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 63 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 258 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 321 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 799 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.pre_L0.1794608299` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 63 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 258 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 321 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 785 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.pre_P00.1794608590` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 63 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 258 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 321 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 798 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.pre_academy.1794607217` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 63 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 258 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 321 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 752 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.pre_academy_e1.1794641307` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 165 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 360 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 423 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 928 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.pre_academy_e2.1794641892` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 165 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 360 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 423 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 940 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.pre_academy_e2.1794641898` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 165 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 360 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 423 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 940 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.pre_accountsvc.1794640744` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 63 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 258 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 321 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 825 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.pre_acctdb.1794638325` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 63 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 258 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 321 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 799 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.pre_callname.1794605967` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 63 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 249 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 312 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 699 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.pre_callname.1794605980` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 63 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 249 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 312 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 699 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.pre_directenv.1794605546` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 63 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 249 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 312 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 682 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.pre_generic.1794606300` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 63 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 258 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 321 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 708 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.pre_knownother.1794606631` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 63 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 258 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 321 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 742 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.pre_nick.1794605244` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 62 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 248 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 311 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 681 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.pre_plusfix.1794606925` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 63 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 258 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 321 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 743 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.pre_sessionkey.1794607675` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 63 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 258 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 321 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 785 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.pre_simple.20261116_070018` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 165 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 360 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 423 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 1529 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.pre_sk2.1794607966` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 63 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 258 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 321 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 785 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.pre_stateapi.1794641269` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 165 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 360 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 423 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 928 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.pre_wire_acctsvc.1794640825` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 63 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 258 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 321 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 825 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.probemode.1794600882` — 2 处 / 2 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 56 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 240 | `MxToken` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.pwrap.1794600031` — 2 处 / 2 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 53 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 218 | `MxToken` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.r01.1794601878` — 3 处 / 3 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 61 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 247 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 310 | `MxToken` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.realcap.1794601220` — 3 处 / 3 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 61 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 247 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 310 | `MxToken` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.relay.bak.20261117-015320` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 165 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 360 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 423 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 1551 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.relay.pre.20261117-015314` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 165 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 360 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 423 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 1551 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.relay1017.bak.201445` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 165 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 590 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 653 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 1781 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.relay2.bak.20261117-020650` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 165 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 360 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 423 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 1551 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.relay2.pre.20261117-020644` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 165 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 360 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 423 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 1551 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.reqid.1794601181` — 3 处 / 3 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 59 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 220 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 283 | `MxToken` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.respstub.1794596657` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 24 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.rlf.bak.20261117-023404` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 165 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 360 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 423 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 1551 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.rlf2.bak.20261117-024752` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 165 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 360 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 423 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 1551 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.rlfix.pre.20261117-023359` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 165 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 360 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 423 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 1551 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.rs1.1794596480` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 23 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.simple.bak.20261116-070018` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 165 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 360 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 423 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 1529 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.spec26.1794601009` — 3 处 / 3 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 57 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 208 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 271 | `MxToken` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.status.1794597469` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 47 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.ten.1794599687` — 2 处 / 2 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 53 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 212 | `MxToken` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.types.1794599717` — 2 处 / 2 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 53 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 218 | `MxToken` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_auth_probe.py.v5.1794596872` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 24 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/account_service.py` — 13 处 / 12 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 83 | `DevId` | `<REDACTED_DEVID>` | 1 |
| 835 | `DevId,devId` | `<REDACTED_DEVID>` | 2 |
| 836 | `DeviceUniqueId` | `<REDACTED_DEVID>` | 1 |
| 837 | `Token` | `<REDACTED_TOKEN>` | 1 |
| 1680 | `DeviceUniqueId` | `<REDACTED_DEVID>` | 1 |
| 1682 | `Token` | `<REDACTED_TOKEN>` | 1 |
| 1737 | `DeviceUniqueId` | `<REDACTED_DEVID>` | 1 |
| 1895 | `dev_id` | `<REDACTED_DEVID>` | 1 |
| 1906 | `dev_id` | `<REDACTED_DEVID>` | 1 |
| 1926 | `dev_id` | `<REDACTED_DEVID>` | 1 |
| 1932 | `dev_id` | `<REDACTED_DEVID>` | 1 |
| 2038 | `device_unique_id` | `<REDACTED_DEVID>` | 1 |

### `bridge_tools/tools/account_template.json` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 54 | `DevId` | `<REDACTED_DEVID>` | 1 |

### `bridge_tools/tools/dto_extra/proto3_networktime.json` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 43 | `MxToken` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/dto_extra/proto90004_management.json` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 42 | `MxToken` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/gen1017.py` — 3 处 / 3 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 58 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 206 | `mxtoken` | `<REDACTED_TOKEN>` | 1 |
| 1280 | `MxToken` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/official_auth_probe.py` — 2 处 / 2 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 31 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 32 | `DEVICE_UNIQUE_ID` | `<REDACTED_DEVID>` | 1 |

### `bridge_tools/tools/official_decoded_201/04_3_api_networktime_sync.request.json` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 21 | `MxToken` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/official_decoded_201/04_3_api_networktime_sync.response.json` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 14 | `MxToken` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/official_probe2.py` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 33 | `DeviceUniqueId` | `<REDACTED_DEVID>` | 1 |

### `bridge_tools/tools/patch_3.py` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 1105 | `mxtoken` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/patch_relay.py` — 5 处 / 5 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 727 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 734 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 743 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 752 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 758 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/patch_relay2.py` — 10 处 / 10 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 852 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 862 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 870 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 880 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 890 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 900 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 908 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 913 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 919 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |
| 924 | `TOKEN` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/patch_relay_fix.py` — 3 处 / 3 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 596 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 688 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 701 | `MxToken` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/patch_relay_fix2.py` — 2 处 / 2 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 537 | `MxToken` | `<REDACTED_TOKEN>` | 1 |
| 538 | `MxToken` | `<REDACTED_TOKEN>` | 1 |

### `bridge_tools/tools/patch_simple.py` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 461 | `mxtoken` | `<REDACTED_TOKEN>` | 1 |

### `client/apk_patch/STEP1_REPORT.md` — 3 处 / 3 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 74 | `server_name/host` | `example.com` | 1 |
| 212 | `server_name/host` | `example.com` | 1 |
| 505 | `server_name/host` | `example.com` | 1 |

### `client/apk_patch/v5/SELFTEST_v5.md` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 631 | `server_name/host` | `example.com` | 1 |

### `client/noroot/HISTORY.md` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 215 | `server_name/host` | `example.com` | 1 |

### `client/noroot/NOROOT_PHONE2_TEST_20261118.md` — 38 处 / 32 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 18 | `server_name/host` | `example.com` | 2 |
| 83 | `server_name/host` | `example.com` | 1 |
| 86 | `server_name/host` | `example.com` | 2 |
| 98 | `server_name/host` | `example.com` | 1 |
| 98 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 99 | `server_name/host` | `example.com` | 2 |
| 116 | `server_name/host` | `example.com` | 1 |
| 117 | `server_name/host` | `example.com` | 1 |
| 125 | `server_name/host` | `example.com` | 1 |
| 126 | `server_name/host` | `example.com` | 1 |
| 169 | `server_name/host` | `example.com` | 1 |
| 181 | `server_name/host` | `example.com` | 1 |
| 183 | `server_name/host` | `example.com` | 1 |
| 211 | `server_name/host` | `example.com` | 1 |
| 300 | `server_name/host` | `example.com` | 1 |
| 301 | `server_name/host` | `example.com` | 1 |
| 334 | `server_name/host` | `example.com` | 1 |
| 341 | `server_name/host` | `example.com` | 2 |
| 383 | `server_name/host` | `example.com` | 1 |
| 394 | `server_name/host` | `example.com` | 1 |
| 404 | `server_name/host` | `example.com` | 1 |
| 487 | `server_name/host` | `example.com` | 1 |
| 492 | `server_name/host` | `example.com` | 1 |
| 533 | `server_name/host` | `example.com` | 2 |
| 558 | `server_name/host` | `example.com` | 1 |
| 598 | `server_name/host` | `example.com` | 2 |
| 611 | `server_name/host` | `example.com` | 1 |
| 655 | `server_name/host` | `example.com` | 1 |
| 659 | `server_name/host` | `example.com` | 1 |
| 688 | `server_name/host` | `example.com` | 1 |
| 689 | `server_name/host` | `example.com` | 1 |
| 715 | `server_name/host` | `example.com` | 1 |

### `client/noroot/NOROOT_PROD_BUILD_PLAN_20261117.md` — 44 处 / 32 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 146 | `server_name/host` | `example.com` | 1 |
| 149 | `server_name/host` | `example.com` | 1 |
| 154 | `server_name/host` | `example.com` | 2 |
| 167 | `server_name/host` | `example.com` | 3 |
| 173 | `server_name/host` | `example.com` | 1 |
| 196 | `server_name/host` | `example.com` | 4 |
| 199 | `server_name/host` | `example.com` | 1 |
| 199 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 200 | `server_name/host` | `example.com` | 1 |
| 200 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 201 | `server_name/host` | `example.com` | 1 |
| 202 | `server_name/host` | `example.com` | 1 |
| 221 | `server_name/host` | `example.com` | 1 |
| 313 | `server_name/host` | `example.com` | 1 |
| 324 | `server_name/host` | `example.com` | 2 |
| 326 | `server_name/host` | `example.com` | 1 |
| 334 | `server_name/host` | `example.com` | 1 |
| 343 | `server_name/host` | `example.com` | 1 |
| 423 | `server_name/host` | `example.com` | 1 |
| 424 | `server_name/host` | `example.com` | 1 |
| 436 | `server_name/host` | `example.com` | 2 |
| 437 | `server_name/host` | `example.com` | 4 |
| 437 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 449 | `server_name/host` | `example.com` | 1 |
| 468 | `server_name/host` | `example.com` | 1 |
| 478 | `server_name/host` | `example.com` | 1 |
| 479 | `server_name/host` | `example.com` | 1 |
| 480 | `server_name/host` | `example.com` | 1 |
| 495 | `server_name/host` | `example.com` | 1 |
| 504 | `server_name/host` | `example.com` | 2 |
| 507 | `server_name/host` | `example.com` | 1 |
| 508 | `server_name/host` | `example.com` | 1 |

### `client/noroot/OPTIONS.md` — 14 处 / 14 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 134 | `server_name/host` | `example.com` | 1 |
| 136 | `server_name/host` | `example.com` | 1 |
| 144 | `server_name/host` | `example.com` | 1 |
| 241 | `server_name/host` | `example.com` | 1 |
| 242 | `server_name/host` | `example.com` | 1 |
| 246 | `server_name/host` | `example.com` | 1 |
| 375 | `server_name/host` | `example.com` | 1 |
| 377 | `server_name/host` | `example.com` | 1 |
| 411 | `server_name/host` | `example.com` | 1 |
| 420 | `server_name/host` | `example.com` | 1 |
| 486 | `server_name/host` | `example.com` | 1 |
| 536 | `server_name/host` | `example.com` | 1 |
| 542 | `server_name/host` | `example.com` | 1 |
| 547 | `server_name/host` | `example.com` | 1 |

### `client/noroot/RESOURCE_CDN_SOURCE.md` — 4 处 / 3 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 377 | `server_name/host` | `example.com` | 2 |
| 378 | `server_name/host` | `example.com` | 1 |
| 384 | `server_name/host` | `example.com` | 1 |

### `client/noroot/SDK_ASSETS.md` — 16 处 / 14 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 57 | `server_name/host` | `example.com` | 2 |
| 99 | `server_name/host` | `example.com` | 1 |
| 102 | `server_name/host` | `example.com` | 1 |
| 107 | `server_name/host` | `example.com` | 1 |
| 130 | `server_name/host` | `example.com` | 1 |
| 138 | `server_name/host` | `example.com` | 1 |
| 140 | `server_name/host` | `example.com` | 1 |
| 160 | `server_name/host` | `example.com` | 1 |
| 251 | `server_name/host` | `example.com` | 1 |
| 253 | `server_name/host` | `example.com` | 1 |
| 260 | `server_name/host` | `example.com` | 1 |
| 261 | `server_name/host` | `example.com` | 1 |
| 262 | `server_name/host` | `example.com` | 2 |
| 277 | `server_name/host` | `example.com` | 1 |

### `client/noroot/_dd2-P9-plaintext.md` — 21 处 / 21 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 16 | `server_name/host` | `example.com` | 1 |
| 20 | `server_name/host` | `example.com` | 1 |
| 31 | `server_name/host` | `example.com` | 1 |
| 40 | `server_name/host` | `example.com` | 1 |
| 44 | `server_name/host` | `example.com` | 1 |
| 44 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 45 | `server_name/host` | `example.com` | 1 |
| 45 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 61 | `server_name/host` | `example.com` | 1 |
| 63 | `server_name/host` | `example.com` | 1 |
| 75 | `server_name/host` | `example.com` | 1 |
| 76 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 110 | `server_name/host` | `example.com` | 1 |
| 114 | `server_name/host` | `example.com` | 1 |
| 346 | `server_name/host` | `example.com` | 1 |
| 417 | `server_name/host` | `example.com` | 1 |
| 418 | `server_name/host` | `example.com` | 1 |
| 420 | `server_name/host` | `example.com` | 1 |
| 429 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 435 | `server_name/host` | `example.com` | 1 |
| 437 | `server_name/host` | `example.com` | 1 |

### `client/noroot/_patch_textasset_sdkconfig.py` — 2 处 / 2 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 74 | `server_name/host` | `example.com` | 1 |
| 75 | `server_name/host` | `example.com` | 1 |

### `client/noroot/_scan_big.json` — 5 处 / 5 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 428 | `email` | `<REDACTED_CONTACT>` | 1 |
| 439 | `email` | `<REDACTED_CONTACT>` | 1 |
| 450 | `email` | `<REDACTED_CONTACT>` | 1 |
| 1363 | `email` | `<REDACTED_CONTACT>` | 1 |
| 2265 | `mobile` | `<REDACTED_CONTACT>` | 1 |

### `client/noroot/_scan_big.txt` — 5 处 / 5 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 134 | `email` | `<REDACTED_CONTACT>` | 1 |
| 137 | `email` | `<REDACTED_CONTACT>` | 1 |
| 140 | `email` | `<REDACTED_CONTACT>` | 1 |
| 389 | `email` | `<REDACTED_CONTACT>` | 1 |
| 641 | `mobile` | `<REDACTED_CONTACT>` | 1 |

### `client/noroot/_snapshot_build_0103.py` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 1806 | `password` | `<REDACTED_DB_CREDENTIAL>` | 1 |

### `client/noroot/_snapshot_build_0105.py` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 1885 | `password` | `<REDACTED_DB_CREDENTIAL>` | 1 |

### `client/noroot/_snapshot_build_0107.py` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 1915 | `password` | `<REDACTED_DB_CREDENTIAL>` | 1 |

### `client/noroot/_snapshot_build_0116.py` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 2151 | `password` | `<REDACTED_DB_CREDENTIAL>` | 1 |

### `client/noroot/_snapshot_build_20261117_2040_pre-rename.py` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 2151 | `password` | `<REDACTED_DB_CREDENTIAL>` | 1 |

### `client/noroot/_snapshot_build_good_0112.py` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 2140 | `password` | `<REDACTED_DB_CREDENTIAL>` | 1 |

### `client/noroot/_urls_meta.txt` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 3 | `email` | `<REDACTED_CONTACT>` | 1 |

### `client/noroot/build_noroot_apk.py` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 2242 | `password` | `<REDACTED_DB_CREDENTIAL>` | 1 |

### `client/noroot/diff24000/diff24000.py` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 47 | `MxToken` | `<REDACTED_TOKEN>` | 1 |

### `client/noroot/diff24000/official_replay_exact.json` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 1 | `MxToken` | `<REDACTED_TOKEN>` | 1 |

### `client/noroot/diff24000/our_degraded_account0.json` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 5 | `MxToken` | `<REDACTED_TOKEN>` | 1 |

### `client/noroot/diff24000/our_min.json` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 5 | `MxToken` | `<REDACTED_TOKEN>` | 1 |

### `docs/D90004_PATCH_PREP.md` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 372 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 386 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 387 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 393 | `server_name/a-record` | `<SERVER_IP>` | 1 |

### `docs/EXPORTFILTER_DEPLOY.md` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 4 | `server_name/a-record` | `<SERVER_IP>` | 1 |

### `docs/GACHA_CLEAN5_DEPLOY.md` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 4 | `server_name/a-record` | `<SERVER_IP>` | 1 |

### `docs/HANDOVER_20261119.md` — 3 处 / 3 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 38 | `server_name/host` | `example.com` | 1 |
| 116 | `server_name/host` | `example.com` | 1 |
| 356 | `server_name/a-record` | `<SERVER_IP>` | 1 |

### `docs/P0PANEL_DEPLOY.md` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 123 | `server_name/a-record` | `<SERVER_IP>` | 1 |

### `docs/P0_GACHA_RATES_PLAN.md` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 288 | `server_name/a-record` | `<SERVER_IP>` | 1 |

### `docs/P0_PRE_BACKUP.md` — 2 处 / 2 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 94 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 100 | `server_name/a-record` | `<SERVER_IP>` | 1 |

### `docs/SERVER_RESTART_OOM.md` — 2 处 / 2 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 128 | `server_name/host` | `example.com` | 1 |
| 129 | `server_name/host` | `example.com` | 1 |

### `docs_all/SELFTEST_v4.md` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 991 | `server_name/host` | `example.com` | 1 |

### `docs_all/report/02-注入链审计.md` — 10 处 / 10 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 71 | `server_name/host` | `example.com` | 1 |
| 97 | `server_name/host` | `example.com` | 1 |
| 144 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 191 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 192 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 193 | `server_name/host` | `example.com` | 1 |
| 196 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 278 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 314 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 336 | `server_name/a-record` | `<SERVER_IP>` | 1 |

### `docs_all/report/04-服务端就绪度.md` — 12 处 / 12 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 42 | `server_name/host` | `example.com` | 1 |
| 71 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 72 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 75 | `server_name/host` | `example.com` | 1 |
| 103 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 105 | `server_name/host` | `example.com` | 1 |
| 106 | `server_name/host` | `example.com` | 1 |
| 110 | `server_name/host` | `example.com` | 1 |
| 114 | `server_name/host` | `example.com` | 1 |
| 129 | `server_name/host` | `example.com` | 1 |
| 137 | `server_name/host` | `example.com` | 1 |
| 289 | `server_name/host` | `example.com` | 1 |

### `docs_all/report/06-手机基线恢复.md` — 31 处 / 28 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 16 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 58 | `server_name/host` | `example.com` | 1 |
| 78 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 179 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 206 | `server_name/host` | `example.com` | 1 |
| 212 | `server_name/host` | `example.com` | 1 |
| 215 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 241 | `server_name/host` | `example.com` | 1 |
| 241 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 245 | `server_name/host` | `example.com` | 1 |
| 249 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 261 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 275 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 292 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 400 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 410 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 536 | `server_name/a-record` | `<SERVER_IP>` | 2 |
| 538 | `server_name/a-record` | `<SERVER_IP>` | 2 |
| 543 | `server_name/a-record` | `<SERVER_IP>` | 2 |
| 544 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 546 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 579 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 651 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 659 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 704 | `server_name/host` | `example.com` | 1 |
| 709 | `server_name/host` | `example.com` | 1 |
| 725 | `server_name/host` | `example.com` | 1 |
| 743 | `server_name/a-record` | `<SERVER_IP>` | 1 |

### `docs_all/report/09-服务器盘点.md` — 90 处 / 76 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 1 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 36 | `server_name/host` | `example.com` | 1 |
| 70 | `server_name/host` | `example.com` | 3 |
| 82 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 83 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 84 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 84 | `server_name/host` | `example.com` | 2 |
| 213 | `server_name/host` | `example.com` | 1 |
| 260 | `server_name/host` | `example.com` | 1 |
| 305 | `server_name/host` | `example.com` | 1 |
| 356 | `server_name/host` | `example.com` | 1 |
| 358 | `server_name/host` | `example.com` | 1 |
| 361 | `server_name/host` | `example.com` | 1 |
| 362 | `server_name/host` | `example.com` | 1 |
| 419 | `server_name/host` | `example.com` | 1 |
| 420 | `server_name/host` | `example.com` | 1 |
| 421 | `server_name/host` | `example.com` | 1 |
| 428 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 429 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 430 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 431 | `server_name/host` | `example.com` | 1 |
| 431 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 583 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 583 | `server_name/host` | `example.com` | 3 |
| 584 | `server_name/host` | `example.com` | 1 |
| 591 | `server_name/host` | `example.com` | 2 |
| 592 | `server_name/host` | `example.com` | 1 |
| 599 | `server_name/host` | `example.com` | 2 |
| 601 | `server_name/host` | `example.com` | 1 |
| 603 | `server_name/host` | `example.com` | 1 |
| 644 | `server_name/host` | `example.com` | 1 |
| 646 | `server_name/host` | `example.com` | 1 |
| 649 | `server_name/host` | `example.com` | 1 |
| 652 | `server_name/host` | `example.com` | 1 |
| 655 | `server_name/host` | `example.com` | 2 |
| 672 | `server_name/host` | `example.com` | 1 |
| 673 | `server_name/host` | `example.com` | 1 |
| 674 | `server_name/host` | `example.com` | 1 |
| 675 | `server_name/host` | `example.com` | 1 |
| 676 | `server_name/host` | `example.com` | 1 |
| 679 | `server_name/host` | `example.com` | 1 |
| 688 | `server_name/host` | `example.com` | 1 |
| 696 | `server_name/host` | `example.com` | 2 |
| 708 | `server_name/host` | `example.com` | 3 |
| 709 | `server_name/host` | `example.com` | 1 |
| 711 | `server_name/host` | `example.com` | 1 |
| 712 | `server_name/host` | `example.com` | 1 |
| 728 | `server_name/host` | `example.com` | 1 |
| 729 | `server_name/host` | `example.com` | 1 |
| 733 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 735 | `server_name/host` | `example.com` | 1 |
| 736 | `server_name/host` | `example.com` | 1 |
| 767 | `server_name/host` | `example.com` | 1 |
| 776 | `server_name/host` | `example.com` | 1 |
| 778 | `server_name/host` | `example.com` | 1 |
| 779 | `server_name/host` | `example.com` | 2 |
| 795 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 800 | `server_name/host` | `example.com` | 1 |
| 838 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 839 | `server_name/host` | `example.com` | 1 |
| 860 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 860 | `server_name/host` | `example.com` | 1 |
| 861 | `server_name/host` | `example.com` | 2 |
| 863 | `server_name/host` | `example.com` | 1 |
| 877 | `server_name/host` | `example.com` | 2 |
| 882 | `server_name/host` | `example.com` | 1 |
| 892 | `server_name/host` | `example.com` | 1 |
| 895 | `server_name/host` | `example.com` | 1 |
| 898 | `server_name/host` | `example.com` | 1 |
| 913 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 917 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 929 | `server_name/host` | `example.com` | 1 |
| 961 | `server_name/host` | `example.com` | 1 |
| 965 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 981 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 1005 | `server_name/host` | `example.com` | 1 |

### `docs_all/report/10-网关重定向-已试清单与有效缺口.md` — 8 处 / 8 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 17 | `server_name/host` | `example.com` | 1 |
| 18 | `server_name/host` | `example.com` | 1 |
| 19 | `server_name/host` | `example.com` | 1 |
| 45 | `server_name/host` | `example.com` | 1 |
| 46 | `server_name/host` | `example.com` | 1 |
| 131 | `server_name/host` | `example.com` | 1 |
| 163 | `server_name/host` | `example.com` | 1 |
| 169 | `server_name/host` | `example.com` | 1 |

### `docs_all/report/100-新har取证-为何无登录.md` — 2 处 / 2 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 550 | `server_name/host` | `example.com` | 1 |
| 602 | `server_name/host` | `example.com` | 1 |

### `docs_all/report/101-官方真服抓包分析.md` — 2 处 / 2 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 62 | `server_name/host` | `example.com` | 1 |
| 161 | `mobile` | `<REDACTED_CONTACT>` | 1 |

### `docs_all/report/102-最终修复方案.md` — 2 处 / 2 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 83 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 90 | `server_name/a-record` | `<SERVER_IP>` | 1 |

### `docs_all/report/13-总账-2026-11-14凌晨.md` — 18 处 / 15 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 26 | `server_name/host` | `example.com` | 1 |
| 28 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 34 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 49 | `server_name/host` | `example.com` | 1 |
| 55 | `server_name/host` | `example.com` | 2 |
| 57 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 58 | `server_name/host` | `example.com` | 1 |
| 58 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 60 | `server_name/host` | `example.com` | 2 |
| 62 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 63 | `server_name/host` | `example.com` | 1 |
| 94 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 97 | `server_name/host` | `example.com` | 1 |
| 163 | `server_name/host` | `example.com` | 1 |
| 186 | `server_name/host` | `example.com` | 2 |

### `docs_all/report/14-运行期dump与证书补丁方案.md` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 375 | `server_name/host` | `example.com` | 1 |

### `docs_all/report/19-网关攻坚-当前状态.md` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 17 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 18 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 32 | `server_name/host` | `example.com` | 1 |
| 55 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |

### `docs_all/report/21-手机侧执行记录.md` — 68 处 / 55 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 21 | `server_name/a-record` | `<SERVER_IP>` | 2 |
| 156 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 157 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 158 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 159 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 165 | `server_name/a-record` | `<SERVER_IP>` | 2 |
| 258 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 260 | `server_name/host` | `example.com` | 1 |
| 288 | `server_name/a-record` | `<SERVER_IP>` | 3 |
| 300 | `server_name/a-record` | `<SERVER_IP>` | 2 |
| 314 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 322 | `server_name/host` | `example.com` | 1 |
| 322 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 334 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 335 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 337 | `server_name/a-record` | `<SERVER_IP>` | 2 |
| 408 | `server_name/host` | `example.com` | 1 |
| 409 | `server_name/host` | `example.com` | 1 |
| 412 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 516 | `server_name/host` | `example.com` | 1 |
| 518 | `server_name/host` | `example.com` | 1 |
| 518 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 570 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 580 | `server_name/host` | `example.com` | 4 |
| 588 | `server_name/host` | `example.com` | 1 |
| 589 | `server_name/host` | `example.com` | 1 |
| 590 | `server_name/host` | `example.com` | 1 |
| 623 | `server_name/host` | `example.com` | 1 |
| 624 | `server_name/host` | `example.com` | 1 |
| 625 | `server_name/host` | `example.com` | 1 |
| 641 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 662 | `server_name/host` | `example.com` | 4 |
| 688 | `server_name/host` | `example.com` | 1 |
| 695 | `server_name/host` | `example.com` | 1 |
| 697 | `server_name/host` | `example.com` | 1 |
| 697 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 712 | `server_name/host` | `example.com` | 1 |
| 757 | `server_name/host` | `example.com` | 1 |
| 757 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 797 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 813 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 847 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 884 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 886 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 915 | `server_name/a-record` | `<SERVER_IP>` | 2 |
| 949 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 997 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 1060 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 1189 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 1216 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 1294 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 1295 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 1420 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 1527 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 1589 | `server_name/a-record` | `<SERVER_IP>` | 1 |

### `docs_all/report/22-服务端取证记录.md` — 28 处 / 20 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 4 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 17 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 31 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 36 | `server_name/host` | `example.com` | 2 |
| 44 | `server_name/host` | `example.com` | 1 |
| 82 | `server_name/host` | `example.com` | 1 |
| 165 | `server_name/host` | `example.com` | 1 |
| 166 | `server_name/host` | `example.com` | 3 |
| 171 | `server_name/host` | `example.com` | 1 |
| 198 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 200 | `server_name/host` | `example.com` | 1 |
| 209 | `server_name/host` | `example.com` | 4 |
| 211 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 267 | `server_name/host` | `example.com` | 1 |
| 269 | `server_name/host` | `example.com` | 1 |
| 271 | `server_name/host` | `example.com` | 1 |
| 272 | `server_name/host` | `example.com` | 2 |
| 354 | `server_name/host` | `example.com` | 1 |
| 364 | `server_name/host` | `example.com` | 2 |
| 385 | `server_name/host` | `example.com` | 1 |

### `docs_all/report/22-真实上游接口取证.md` — 54 处 / 49 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 7 | `server_name/host` | `example.com` | 1 |
| 7 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 47 | `server_name/host` | `example.com` | 1 |
| 51 | `server_name/host` | `example.com` | 1 |
| 51 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 52 | `server_name/host` | `example.com` | 2 |
| 67 | `server_name/host` | `example.com` | 2 |
| 68 | `server_name/host` | `example.com` | 1 |
| 69 | `server_name/host` | `example.com` | 1 |
| 85 | `server_name/host` | `example.com` | 1 |
| 86 | `server_name/host` | `example.com` | 1 |
| 87 | `server_name/host` | `example.com` | 1 |
| 96 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 200 | `server_name/host` | `example.com` | 1 |
| 210 | `server_name/host` | `example.com` | 1 |
| 255 | `server_name/host` | `example.com` | 1 |
| 255 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 361 | `server_name/host` | `example.com` | 1 |
| 365 | `server_name/host` | `example.com` | 3 |
| 376 | `server_name/host` | `example.com` | 1 |
| 378 | `server_name/host` | `example.com` | 1 |
| 387 | `server_name/host` | `example.com` | 1 |
| 403 | `server_name/host` | `example.com` | 1 |
| 403 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 414 | `server_name/host` | `example.com` | 1 |
| 414 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 442 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 468 | `server_name/host` | `example.com` | 1 |
| 492 | `server_name/host` | `example.com` | 1 |
| 510 | `server_name/host` | `example.com` | 1 |
| 632 | `server_name/host` | `example.com` | 1 |
| 633 | `server_name/host` | `example.com` | 1 |
| 640 | `server_name/host` | `example.com` | 1 |
| 654 | `server_name/host` | `example.com` | 1 |
| 655 | `server_name/host` | `example.com` | 1 |
| 669 | `server_name/host` | `example.com` | 1 |
| 670 | `server_name/host` | `example.com` | 1 |
| 873 | `server_name/host` | `example.com` | 1 |
| 876 | `server_name/host` | `example.com` | 1 |
| 881 | `server_name/host` | `example.com` | 2 |
| 1364 | `server_name/host` | `example.com` | 1 |
| 1365 | `server_name/host` | `example.com` | 1 |
| 1368 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 1378 | `server_name/host` | `example.com` | 1 |
| 1388 | `server_name/host` | `example.com` | 1 |
| 1513 | `server_name/host` | `example.com` | 1 |
| 2024 | `server_name/host` | `example.com` | 1 |
| 2025 | `server_name/host` | `example.com` | 1 |
| 2028 | `server_name/a-record` | `<SERVER_IP>` | 1 |

### `docs_all/report/23-主线改判-TLS已通应用层卡点.md` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 31 | `server_name/host` | `example.com` | 1 |
| 57 | `server_name/host` | `example.com` | 1 |
| 71 | `server_name/host` | `example.com` | 1 |
| 72 | `server_name/host` | `example.com` | 1 |

### `docs_all/report/23-手动关闭宝塔WAF操作指引.md` — 3 处 / 3 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 5 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 20 | `server_name/host` | `example.com` | 1 |
| 20 | `server_name/a-record` | `<SERVER_IP>` | 1 |

### `docs_all/report/24-state接口schema反推.md` — 2 处 / 2 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 303 | `server_name/host` | `example.com` | 1 |
| 311 | `server_name/host` | `example.com` | 1 |

### `docs_all/report/25-根因定案-状态接口schema错误.md` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 61 | `server_name/host` | `example.com` | 1 |
| 61 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 76 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 88 | `server_name/host` | `example.com` | 1 |

### `docs_all/report/26-进度-NRE已修-卡点后移.md` — 9 处 / 6 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 30 | `server_name/host` | `example.com` | 1 |
| 30 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 39 | `server_name/host` | `example.com` | 4 |
| 51 | `server_name/host` | `example.com` | 1 |
| 52 | `server_name/host` | `example.com` | 1 |
| 53 | `server_name/host` | `example.com` | 1 |

### `docs_all/report/27-SDK登录协议调研.md` — 2 处 / 2 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 148 | `server_name/host` | `example.com` | 1 |
| 333 | `server_name/host` | `example.com` | 1 |

### `docs_all/report/28-Shittim网关协议源码核对.md` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 849 | `server_name/host` | `example.com` | 1 |

### `docs_all/report/29-进度-网关未调用与判据纪律.md` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 12 | `server_name/host` | `example.com` | 1 |

### `docs_all/report/54-客户端补丁方案-本地配置绕过.md` — 10 处 / 8 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 243 | `server_name/host` | `example.com` | 1 |
| 452 | `server_name/host` | `example.com` | 1 |
| 461 | `server_name/host` | `example.com` | 1 |
| 468 | `server_name/host` | `example.com` | 1 |
| 480 | `server_name/host` | `example.com` | 3 |
| 570 | `server_name/host` | `example.com` | 1 |
| 571 | `server_name/host` | `example.com` | 1 |
| 615 | `server_name/host` | `example.com` | 1 |

### `docs_all/report/57-既有补丁资产清点.md` — 2 处 / 2 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 108 | `server_name/host` | `example.com` | 1 |
| 109 | `server_name/host` | `example.com` | 1 |

### `docs_all/report/74-63秒空窗期取证.md` — 2 处 / 2 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 3 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 205 | `server_name/a-record` | `<SERVER_IP>` | 1 |

### `docs_all/report/84-手机侧观察时间线.md` — 2 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 154 | `server_name/a-record` | `<SERVER_IP>` | 2 |

### `docs_all/report/90-项目总纲-可交接版.md` — 3 处 / 3 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 33 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 34 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 37 | `server_name/a-record` | `<SERVER_IP>` | 1 |

### `docs_all/report/95-真服抓包与对照方案.md` — 7 处 / 6 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 101 | `server_name/host` | `example.com` | 1 |
| 297 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 299 | `server_name/host` | `example.com` | 2 |
| 322 | `server_name/host` | `example.com` | 1 |
| 347 | `server_name/host` | `example.com` | 1 |
| 390 | `server_name/host` | `example.com` | 1 |

### `docs_all/report/99-baba_har取证.md` — 97 处 / 71 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 40 | `server_name/host` | `example.com` | 1 |
| 40 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 64 | `server_name/host` | `example.com` | 3 |
| 65 | `server_name/host` | `example.com` | 3 |
| 69 | `server_name/host` | `example.com` | 1 |
| 73 | `server_name/host` | `example.com` | 1 |
| 73 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 135 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 139 | `server_name/host` | `example.com` | 2 |
| 140 | `server_name/host` | `example.com` | 2 |
| 141 | `server_name/host` | `example.com` | 2 |
| 142 | `server_name/host` | `example.com` | 2 |
| 143 | `server_name/host` | `example.com` | 2 |
| 144 | `server_name/host` | `example.com` | 2 |
| 145 | `server_name/host` | `example.com` | 2 |
| 146 | `server_name/host` | `example.com` | 2 |
| 147 | `server_name/host` | `example.com` | 2 |
| 148 | `server_name/host` | `example.com` | 2 |
| 149 | `server_name/host` | `example.com` | 2 |
| 150 | `server_name/host` | `example.com` | 2 |
| 152 | `server_name/host` | `example.com` | 2 |
| 162 | `server_name/host` | `example.com` | 1 |
| 163 | `server_name/host` | `example.com` | 1 |
| 164 | `server_name/host` | `example.com` | 1 |
| 165 | `server_name/host` | `example.com` | 1 |
| 193 | `server_name/host` | `example.com` | 1 |
| 193 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 194 | `server_name/host` | `example.com` | 1 |
| 194 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 195 | `server_name/host` | `example.com` | 1 |
| 195 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 197 | `server_name/host` | `example.com` | 1 |
| 197 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 201 | `server_name/host` | `example.com` | 1 |
| 201 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 203 | `server_name/host` | `example.com` | 1 |
| 203 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 218 | `server_name/host` | `example.com` | 1 |
| 218 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 219 | `server_name/host` | `example.com` | 1 |
| 219 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 221 | `server_name/host` | `example.com` | 1 |
| 221 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 222 | `server_name/host` | `example.com` | 1 |
| 222 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 223 | `server_name/host` | `example.com` | 1 |
| 223 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 224 | `server_name/host` | `example.com` | 1 |
| 224 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 280 | `server_name/host` | `example.com` | 1 |
| 280 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 356 | `server_name/host` | `example.com` | 1 |
| 356 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 377 | `server_name/host` | `example.com` | 1 |
| 421 | `server_name/host` | `example.com` | 2 |
| 422 | `server_name/host` | `example.com` | 2 |
| 423 | `server_name/host` | `example.com` | 2 |
| 424 | `server_name/host` | `example.com` | 2 |
| 425 | `server_name/host` | `example.com` | 2 |
| 441 | `server_name/host` | `example.com` | 1 |
| 455 | `server_name/host` | `example.com` | 1 |
| 472 | `server_name/host` | `example.com` | 1 |
| 472 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 495 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 539 | `server_name/host` | `example.com` | 1 |
| 555 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 559 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 607 | `server_name/host` | `example.com` | 1 |
| 613 | `server_name/host` | `example.com` | 3 |
| 614 | `server_name/host` | `example.com` | 3 |
| 619 | `server_name/host` | `example.com` | 1 |

### `docs_all/report/DEADENDS.md` — 8 处 / 7 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 90 | `server_name/host` | `example.com` | 1 |
| 98 | `server_name/host` | `example.com` | 1 |
| 493 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 494 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 509 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 527 | `server_name/host` | `example.com` | 1 |
| 528 | `server_name/host` | `example.com` | 2 |

### `docs_all/report/INDEX.md` — 20 处 / 17 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 16 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 38 | `server_name/host` | `example.com` | 1 |
| 61 | `server_name/host` | `example.com` | 1 |
| 68 | `server_name/host` | `example.com` | 1 |
| 81 | `server_name/host` | `example.com` | 2 |
| 82 | `server_name/host` | `example.com` | 1 |
| 186 | `server_name/host` | `example.com` | 2 |
| 287 | `server_name/host` | `example.com` | 1 |
| 394 | `server_name/a-record` | `<SERVER_IP>` | 2 |
| 401 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 423 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 440 | `server_name/host` | `example.com` | 1 |
| 442 | `server_name/host` | `example.com` | 1 |
| 443 | `server_name/host` | `example.com` | 1 |
| 517 | `server_name/host` | `example.com` | 1 |
| 517 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 528 | `server_name/host` | `example.com` | 1 |

### `docs_all/report/_tmp/_baba_deep_out.md` — 62 处 / 50 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 21 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 73 | `server_name/host` | `example.com` | 1 |
| 73 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 160 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 175 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 179 | `server_name/host` | `example.com` | 2 |
| 180 | `server_name/host` | `example.com` | 2 |
| 181 | `server_name/host` | `example.com` | 2 |
| 182 | `server_name/host` | `example.com` | 2 |
| 183 | `server_name/host` | `example.com` | 2 |
| 184 | `server_name/host` | `example.com` | 2 |
| 185 | `server_name/host` | `example.com` | 2 |
| 186 | `server_name/host` | `example.com` | 2 |
| 187 | `server_name/host` | `example.com` | 2 |
| 188 | `server_name/host` | `example.com` | 2 |
| 189 | `server_name/host` | `example.com` | 2 |
| 190 | `server_name/host` | `example.com` | 2 |
| 200 | `server_name/host` | `example.com` | 1 |
| 201 | `server_name/host` | `example.com` | 1 |
| 202 | `server_name/host` | `example.com` | 1 |
| 204 | `server_name/host` | `example.com` | 1 |
| 208 | `server_name/host` | `example.com` | 1 |
| 210 | `server_name/host` | `example.com` | 1 |
| 225 | `server_name/host` | `example.com` | 1 |
| 226 | `server_name/host` | `example.com` | 1 |
| 228 | `server_name/host` | `example.com` | 1 |
| 229 | `server_name/host` | `example.com` | 1 |
| 230 | `server_name/host` | `example.com` | 1 |
| 231 | `server_name/host` | `example.com` | 1 |
| 256 | `server_name/host` | `example.com` | 1 |
| 257 | `server_name/host` | `example.com` | 1 |
| 259 | `server_name/host` | `example.com` | 1 |
| 260 | `server_name/host` | `example.com` | 1 |
| 261 | `server_name/host` | `example.com` | 1 |
| 262 | `server_name/host` | `example.com` | 1 |
| 288 | `server_name/host` | `example.com` | 1 |
| 289 | `server_name/host` | `example.com` | 1 |
| 290 | `server_name/host` | `example.com` | 1 |
| 291 | `server_name/host` | `example.com` | 1 |
| 292 | `server_name/host` | `example.com` | 1 |
| 305 | `server_name/host` | `example.com` | 1 |
| 306 | `server_name/host` | `example.com` | 1 |
| 307 | `server_name/host` | `example.com` | 1 |
| 309 | `server_name/host` | `example.com` | 1 |
| 312 | `server_name/host` | `example.com` | 1 |
| 331 | `server_name/host` | `example.com` | 1 |
| 332 | `server_name/host` | `example.com` | 1 |
| 333 | `server_name/host` | `example.com` | 1 |
| 334 | `server_name/host` | `example.com` | 1 |
| 336 | `server_name/host` | `example.com` | 1 |

### `docs_all/report/_tmp/server_deploy_selfcheck_20261116.md` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 4 | `server_name/a-record` | `<SERVER_IP>` | 1 |

### `docs_all/report/evidence/22/report_template.md` — 38 处 / 34 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 7 | `server_name/host` | `example.com` | 1 |
| 7 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 47 | `server_name/host` | `example.com` | 1 |
| 51 | `server_name/host` | `example.com` | 1 |
| 51 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 52 | `server_name/host` | `example.com` | 2 |
| 67 | `server_name/host` | `example.com` | 2 |
| 68 | `server_name/host` | `example.com` | 1 |
| 69 | `server_name/host` | `example.com` | 1 |
| 85 | `server_name/host` | `example.com` | 1 |
| 86 | `server_name/host` | `example.com` | 1 |
| 87 | `server_name/host` | `example.com` | 1 |
| 96 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 200 | `server_name/host` | `example.com` | 1 |
| 210 | `server_name/host` | `example.com` | 1 |
| 255 | `server_name/host` | `example.com` | 1 |
| 255 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 361 | `server_name/host` | `example.com` | 1 |
| 365 | `server_name/host` | `example.com` | 3 |
| 376 | `server_name/host` | `example.com` | 1 |
| 378 | `server_name/host` | `example.com` | 1 |
| 387 | `server_name/host` | `example.com` | 1 |
| 403 | `server_name/host` | `example.com` | 1 |
| 403 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 414 | `server_name/host` | `example.com` | 1 |
| 414 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 442 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 468 | `server_name/host` | `example.com` | 1 |
| 492 | `server_name/host` | `example.com` | 1 |
| 510 | `server_name/host` | `example.com` | 1 |
| 599 | `server_name/host` | `example.com` | 1 |
| 600 | `server_name/host` | `example.com` | 1 |
| 613 | `server_name/host` | `example.com` | 1 |
| 614 | `server_name/host` | `example.com` | 1 |

### `docs_all/scripts/NOTES-gateway.md` — 2 处 / 2 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 58 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 61 | `server_name/a-record` | `<SERVER_IP>` | 1 |

### `docs_all/scripts/sni-passthrough/MIGRATION.md` — 9 处 / 7 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 22 | `server_name/host` | `example.com` | 1 |
| 23 | `server_name/host` | `example.com` | 1 |
| 24 | `server_name/host` | `example.com` | 1 |
| 36 | `server_name/host` | `example.com` | 2 |
| 42 | `server_name/host` | `example.com` | 1 |
| 63 | `server_name/host` | `example.com` | 2 |
| 72 | `server_name/host` | `example.com` | 1 |

### `docs_all/scripts/sni-passthrough/RISKS.md` — 4 处 / 2 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 9 | `server_name/host` | `example.com` | 1 |
| 13 | `server_name/host` | `example.com` | 3 |

### `docs_all/work/ba/apk_patch/STEP1_REPORT.md` — 3 处 / 3 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 74 | `server_name/host` | `example.com` | 1 |
| 212 | `server_name/host` | `example.com` | 1 |
| 505 | `server_name/host` | `example.com` | 1 |

### `docs_all/work/ba/apk_patch/v5/SELFTEST_v5.md` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 631 | `server_name/host` | `example.com` | 1 |

### `docs_all/work/ba/cfg/README-推送操作手册.md` — 5 处 / 5 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 31 | `server_name/host` | `example.com` | 1 |
| 47 | `server_name/host` | `example.com` | 1 |
| 48 | `server_name/host` | `example.com` | 1 |
| 50 | `server_name/host` | `example.com` | 1 |
| 81 | `server_name/host` | `example.com` | 1 |

### `docs_all/work/ba/noroot/HISTORY.md` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 215 | `server_name/host` | `example.com` | 1 |

### `docs_all/work/ba/noroot/NOROOT_PHONE2_TEST_20261118.md` — 38 处 / 32 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 18 | `server_name/host` | `example.com` | 2 |
| 83 | `server_name/host` | `example.com` | 1 |
| 86 | `server_name/host` | `example.com` | 2 |
| 98 | `server_name/host` | `example.com` | 1 |
| 98 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 99 | `server_name/host` | `example.com` | 2 |
| 116 | `server_name/host` | `example.com` | 1 |
| 117 | `server_name/host` | `example.com` | 1 |
| 125 | `server_name/host` | `example.com` | 1 |
| 126 | `server_name/host` | `example.com` | 1 |
| 169 | `server_name/host` | `example.com` | 1 |
| 181 | `server_name/host` | `example.com` | 1 |
| 183 | `server_name/host` | `example.com` | 1 |
| 211 | `server_name/host` | `example.com` | 1 |
| 300 | `server_name/host` | `example.com` | 1 |
| 301 | `server_name/host` | `example.com` | 1 |
| 334 | `server_name/host` | `example.com` | 1 |
| 341 | `server_name/host` | `example.com` | 2 |
| 383 | `server_name/host` | `example.com` | 1 |
| 394 | `server_name/host` | `example.com` | 1 |
| 404 | `server_name/host` | `example.com` | 1 |
| 487 | `server_name/host` | `example.com` | 1 |
| 492 | `server_name/host` | `example.com` | 1 |
| 533 | `server_name/host` | `example.com` | 2 |
| 558 | `server_name/host` | `example.com` | 1 |
| 598 | `server_name/host` | `example.com` | 2 |
| 611 | `server_name/host` | `example.com` | 1 |
| 655 | `server_name/host` | `example.com` | 1 |
| 659 | `server_name/host` | `example.com` | 1 |
| 688 | `server_name/host` | `example.com` | 1 |
| 689 | `server_name/host` | `example.com` | 1 |
| 715 | `server_name/host` | `example.com` | 1 |

### `docs_all/work/ba/noroot/NOROOT_PROD_BUILD_PLAN_20261117.md` — 44 处 / 32 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 146 | `server_name/host` | `example.com` | 1 |
| 149 | `server_name/host` | `example.com` | 1 |
| 154 | `server_name/host` | `example.com` | 2 |
| 167 | `server_name/host` | `example.com` | 3 |
| 173 | `server_name/host` | `example.com` | 1 |
| 196 | `server_name/host` | `example.com` | 4 |
| 199 | `server_name/host` | `example.com` | 1 |
| 199 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 200 | `server_name/host` | `example.com` | 1 |
| 200 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 201 | `server_name/host` | `example.com` | 1 |
| 202 | `server_name/host` | `example.com` | 1 |
| 221 | `server_name/host` | `example.com` | 1 |
| 313 | `server_name/host` | `example.com` | 1 |
| 324 | `server_name/host` | `example.com` | 2 |
| 326 | `server_name/host` | `example.com` | 1 |
| 334 | `server_name/host` | `example.com` | 1 |
| 343 | `server_name/host` | `example.com` | 1 |
| 423 | `server_name/host` | `example.com` | 1 |
| 424 | `server_name/host` | `example.com` | 1 |
| 436 | `server_name/host` | `example.com` | 2 |
| 437 | `server_name/host` | `example.com` | 4 |
| 437 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 449 | `server_name/host` | `example.com` | 1 |
| 468 | `server_name/host` | `example.com` | 1 |
| 478 | `server_name/host` | `example.com` | 1 |
| 479 | `server_name/host` | `example.com` | 1 |
| 480 | `server_name/host` | `example.com` | 1 |
| 495 | `server_name/host` | `example.com` | 1 |
| 504 | `server_name/host` | `example.com` | 2 |
| 507 | `server_name/host` | `example.com` | 1 |
| 508 | `server_name/host` | `example.com` | 1 |

### `docs_all/work/ba/noroot/OPTIONS.md` — 14 处 / 14 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 134 | `server_name/host` | `example.com` | 1 |
| 136 | `server_name/host` | `example.com` | 1 |
| 144 | `server_name/host` | `example.com` | 1 |
| 241 | `server_name/host` | `example.com` | 1 |
| 242 | `server_name/host` | `example.com` | 1 |
| 246 | `server_name/host` | `example.com` | 1 |
| 375 | `server_name/host` | `example.com` | 1 |
| 377 | `server_name/host` | `example.com` | 1 |
| 411 | `server_name/host` | `example.com` | 1 |
| 420 | `server_name/host` | `example.com` | 1 |
| 486 | `server_name/host` | `example.com` | 1 |
| 536 | `server_name/host` | `example.com` | 1 |
| 542 | `server_name/host` | `example.com` | 1 |
| 547 | `server_name/host` | `example.com` | 1 |

### `docs_all/work/ba/noroot/RESOURCE_CDN_SOURCE.md` — 4 处 / 3 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 377 | `server_name/host` | `example.com` | 2 |
| 378 | `server_name/host` | `example.com` | 1 |
| 384 | `server_name/host` | `example.com` | 1 |

### `docs_all/work/ba/noroot/SDK_ASSETS.md` — 16 处 / 14 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 57 | `server_name/host` | `example.com` | 2 |
| 99 | `server_name/host` | `example.com` | 1 |
| 102 | `server_name/host` | `example.com` | 1 |
| 107 | `server_name/host` | `example.com` | 1 |
| 130 | `server_name/host` | `example.com` | 1 |
| 138 | `server_name/host` | `example.com` | 1 |
| 140 | `server_name/host` | `example.com` | 1 |
| 160 | `server_name/host` | `example.com` | 1 |
| 251 | `server_name/host` | `example.com` | 1 |
| 253 | `server_name/host` | `example.com` | 1 |
| 260 | `server_name/host` | `example.com` | 1 |
| 261 | `server_name/host` | `example.com` | 1 |
| 262 | `server_name/host` | `example.com` | 2 |
| 277 | `server_name/host` | `example.com` | 1 |

### `docs_all/work/ba/noroot/_dd2-P9-plaintext.md` — 21 处 / 21 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 16 | `server_name/host` | `example.com` | 1 |
| 20 | `server_name/host` | `example.com` | 1 |
| 31 | `server_name/host` | `example.com` | 1 |
| 40 | `server_name/host` | `example.com` | 1 |
| 44 | `server_name/host` | `example.com` | 1 |
| 44 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 45 | `server_name/host` | `example.com` | 1 |
| 45 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 61 | `server_name/host` | `example.com` | 1 |
| 63 | `server_name/host` | `example.com` | 1 |
| 75 | `server_name/host` | `example.com` | 1 |
| 76 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 110 | `server_name/host` | `example.com` | 1 |
| 114 | `server_name/host` | `example.com` | 1 |
| 346 | `server_name/host` | `example.com` | 1 |
| 417 | `server_name/host` | `example.com` | 1 |
| 418 | `server_name/host` | `example.com` | 1 |
| 420 | `server_name/host` | `example.com` | 1 |
| 429 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 435 | `server_name/host` | `example.com` | 1 |
| 437 | `server_name/host` | `example.com` | 1 |

### `docs_all/work/ba/plan/20261118/CARD_IDENTITY_FIX_PLAN.md` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 96 | `server_name/host` | `example.com` | 1 |

### `docs_all/work/ba/plan/20261118/DEVICE_ID_CLEANUP.md` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 19 | `mobile` | `<REDACTED_CONTACT>` | 1 |

### `docs_all/work/ba/plan/20261118/GACHA_ROOTCAUSE_ITEMLIST_STUB.md` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 5 | `server_name/host` | `example.com` | 1 |

### `docs_all/work/ba/plan/20261118/ITEMLIST_RELAY_FIX.md` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 4 | `server_name/a-record` | `<SERVER_IP>` | 1 |

### `docs_all/work/ba/plan/20261118/SRV_CARD_IDENTITY_EVIDENCE.md` — 5 处 / 5 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 128 | `server_name/host` | `example.com` | 1 |
| 175 | `server_name/host` | `example.com` | 1 |
| 214 | `server_name/host` | `example.com` | 1 |
| 252 | `server_name/host` | `example.com` | 1 |
| 254 | `server_name/host` | `example.com` | 1 |

### `docs_all/work/ba/plan/20261119/APK_TABLE_INTEGRITY.md` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 162 | `server_name/host` | `example.com` | 1 |

### `docs_all/work/ba/plan/20261119/CATALOG_RE_DOWNLOAD_CHECK.md` — 15 处 / 15 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 28 | `server_name/host` | `example.com` | 1 |
| 29 | `server_name/host` | `example.com` | 1 |
| 33 | `server_name/host` | `example.com` | 1 |
| 36 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 43 | `server_name/host` | `example.com` | 1 |
| 44 | `server_name/host` | `example.com` | 1 |
| 45 | `server_name/host` | `example.com` | 1 |
| 46 | `server_name/host` | `example.com` | 1 |
| 47 | `server_name/host` | `example.com` | 1 |
| 48 | `server_name/host` | `example.com` | 1 |
| 49 | `server_name/host` | `example.com` | 1 |
| 50 | `server_name/host` | `example.com` | 1 |
| 51 | `server_name/host` | `example.com` | 1 |
| 52 | `server_name/host` | `example.com` | 1 |
| 85 | `server_name/host` | `example.com` | 1 |

### `docs_all/work/ba/plan/20261119/D90004_PATCH_PREP.md` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 372 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 386 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 387 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 393 | `server_name/a-record` | `<SERVER_IP>` | 1 |

### `docs_all/work/ba/plan/20261119/EDITABLE_DATA_INVENTORY.md` — 3 处 / 3 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 4 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 112 | `server_name/host` | `example.com` | 1 |
| 162 | `server_name/a-record` | `<SERVER_IP>` | 1 |

### `docs_all/work/ba/plan/20261119/EXPORTFILTER_DEPLOY.md` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 4 | `server_name/a-record` | `<SERVER_IP>` | 1 |

### `docs_all/work/ba/plan/20261119/EXPORT_FILTER.md` — 2 处 / 2 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 313 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 335 | `server_name/a-record` | `<SERVER_IP>` | 1 |

### `docs_all/work/ba/plan/20261119/GACHA_CLEAN5_DEPLOY.md` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 4 | `server_name/a-record` | `<SERVER_IP>` | 1 |

### `docs_all/work/ba/plan/20261119/GACHA_INVESTIGATION_20261119.md` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 4 | `server_name/a-record` | `<SERVER_IP>` | 1 |

### `docs_all/work/ba/plan/20261119/HANDOVER_20261119.md` — 3 处 / 3 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 38 | `server_name/host` | `example.com` | 1 |
| 116 | `server_name/host` | `example.com` | 1 |
| 356 | `server_name/a-record` | `<SERVER_IP>` | 1 |

### `docs_all/work/ba/plan/20261119/ITEMLIST_RELAY_V2.md` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 4 | `server_name/a-record` | `<SERVER_IP>` | 1 |

### `docs_all/work/ba/plan/20261119/LANGUAGE_FIELD_DIFF.md` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 32 | `server_name/host` | `example.com` | 1 |

### `docs_all/work/ba/plan/20261119/P0PANEL_DEPLOY.md` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 123 | `server_name/a-record` | `<SERVER_IP>` | 1 |

### `docs_all/work/ba/plan/20261119/P0_GACHA_RATES_PLAN.md` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 288 | `server_name/a-record` | `<SERVER_IP>` | 1 |

### `docs_all/work/ba/plan/20261119/P0_PRE_BACKUP.md` — 2 处 / 2 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 94 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 100 | `server_name/a-record` | `<SERVER_IP>` | 1 |

### `docs_all/work/ba/plan/20261119/RECRUIT_LOG_FORENSICS_20261119_0124.md` — 2 处 / 2 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 5 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 13 | `server_name/host` | `example.com` | 1 |

### `docs_all/work/ba/plan/20261119/SHOPLIST_NRE_DEPLOY.md` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 4 | `server_name/a-record` | `<SERVER_IP>` | 1 |

### `docs_all/work/ba/plan/20261119/SHOPLIST_NRE_FIX.md` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 225 | `server_name/a-record` | `<SERVER_IP>` | 1 |

### `docs_all/work/ba/plan/20261120/SERVER_RESTART_OOM.md` — 2 处 / 2 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 128 | `server_name/host` | `example.com` | 1 |
| 129 | `server_name/host` | `example.com` | 1 |

### `docs_all/work/ba/server/deploy/ADMIN_PANEL_SPEC.md` — 2 处 / 2 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 50 | `server_name/host` | `example.com` | 1 |
| 99 | `server_name/host` | `example.com` | 1 |

### `docs_all/work/ba/server/deploy/HANDOFF_20261117.md` — 2 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 125 | `server_name/host` | `example.com` | 2 |

### `docs_all/work/ba/server/deploy/MILESTONE_20261117_BLACKOUT_FIXED.md` — 7 处 / 5 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 51 | `server_name/host` | `example.com` | 3 |
| 83 | `server_name/host` | `example.com` | 1 |
| 96 | `server_name/host` | `example.com` | 1 |
| 97 | `server_name/host` | `example.com` | 1 |
| 98 | `server_name/host` | `example.com` | 1 |

### `docs_all/work/ba/server/deploy/PROGRESS_20261116_1017.md` — 2 处 / 2 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 10 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 49 | `server_name/a-record` | `<SERVER_IP>` | 1 |

### `docs_all/work/ba/server/deploy/TONIGHT_MASTER_20261117.md` — 4 处 / 3 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 114 | `server_name/host` | `example.com` | 2 |
| 138 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 144 | `server_name/host` | `example.com` | 1 |

### `docs_all/work/ba/server/deploy/_audit/AUDIT_PHP_PANEL_20261118.md` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 3 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 29 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 238 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 322 | `server_name/a-record` | `<SERVER_IP>` | 1 |

### `docs_all/work/ba/server/deploy/_audit/FIX_PHP_20261118_0101.md` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 236 | `server_name/a-record` | `<SERVER_IP>` | 1 |

### `docs_all/work/ba/server/deploy/_audit/MERGED_AUDIT_20261118.md` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 111 | `server_name/a-record` | `<SERVER_IP>` | 1 |

### `docs_all/work/ba/server/deploy/_blackout/phone/PHONE_BLACKOUT2_20261117.md` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 123 | `server_name/a-record` | `<SERVER_IP>` | 1 |

### `docs_all/work/ba/server/deploy/_blackout/srv/ADMINAPI_FORENSICS_20261117.md` — 22 处 / 18 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 11 | `server_name/host` | `example.com` | 1 |
| 13 | `server_name/host` | `example.com` | 1 |
| 20 | `server_name/host` | `example.com` | 1 |
| 21 | `server_name/host` | `example.com` | 1 |
| 25 | `server_name/host` | `example.com` | 1 |
| 105 | `server_name/host` | `example.com` | 1 |
| 106 | `server_name/host` | `example.com` | 1 |
| 107 | `server_name/host` | `example.com` | 1 |
| 109 | `server_name/host` | `example.com` | 1 |
| 316 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 317 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 320 | `server_name/host` | `example.com` | 1 |
| 320 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 323 | `server_name/host` | `example.com` | 4 |
| 327 | `server_name/a-record` | `<SERVER_IP>` | 2 |
| 343 | `server_name/host` | `example.com` | 1 |
| 343 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 344 | `server_name/a-record` | `<SERVER_IP>` | 1 |

### `docs_all/work/ba/server/deploy/_blackout/srv/ASSET_404_20261117.md` — 5 处 / 5 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 18 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 52 | `server_name/host` | `example.com` | 1 |
| 52 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 116 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 119 | `server_name/a-record` | `<SERVER_IP>` | 1 |

### `docs_all/work/ba/server/deploy/_blackout/srv/CERT_CHANGE_20261117.md` — 24 处 / 18 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 12 | `server_name/host` | `example.com` | 1 |
| 14 | `server_name/host` | `example.com` | 1 |
| 21 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 22 | `server_name/host` | `example.com` | 2 |
| 23 | `server_name/host` | `example.com` | 2 |
| 28 | `server_name/host` | `example.com` | 1 |
| 33 | `server_name/host` | `example.com` | 1 |
| 43 | `server_name/host` | `example.com` | 3 |
| 44 | `server_name/host` | `example.com` | 2 |
| 48 | `server_name/host` | `example.com` | 1 |
| 65 | `server_name/host` | `example.com` | 1 |
| 66 | `server_name/host` | `example.com` | 1 |
| 67 | `server_name/host` | `example.com` | 1 |
| 69 | `server_name/host` | `example.com` | 1 |
| 77 | `server_name/host` | `example.com` | 1 |
| 93 | `server_name/host` | `example.com` | 1 |
| 94 | `server_name/host` | `example.com` | 1 |
| 98 | `server_name/host` | `example.com` | 2 |

### `docs_all/work/ba/server/deploy/_blackout/srv/CERT_REGRESSION_20261117.md` — 31 处 / 22 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 11 | `server_name/host` | `example.com` | 2 |
| 19 | `server_name/host` | `example.com` | 1 |
| 20 | `server_name/host` | `example.com` | 1 |
| 21 | `server_name/host` | `example.com` | 1 |
| 27 | `server_name/host` | `example.com` | 2 |
| 45 | `server_name/host` | `example.com` | 1 |
| 46 | `server_name/host` | `example.com` | 2 |
| 52 | `server_name/host` | `example.com` | 1 |
| 55 | `server_name/host` | `example.com` | 1 |
| 59 | `server_name/host` | `example.com` | 3 |
| 60 | `server_name/host` | `example.com` | 2 |
| 67 | `server_name/host` | `example.com` | 1 |
| 77 | `server_name/host` | `example.com` | 1 |
| 78 | `server_name/host` | `example.com` | 1 |
| 84 | `server_name/host` | `example.com` | 1 |
| 86 | `server_name/host` | `example.com` | 1 |
| 95 | `server_name/host` | `example.com` | 3 |
| 96 | `server_name/host` | `example.com` | 1 |
| 97 | `server_name/host` | `example.com` | 2 |
| 104 | `server_name/host` | `example.com` | 1 |
| 136 | `server_name/host` | `example.com` | 1 |
| 147 | `server_name/host` | `example.com` | 1 |

### `docs_all/work/ba/server/deploy/_blackout/srv/DISK_20261117.md` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 69 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 70 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 72 | `server_name/host` | `example.com` | 1 |
| 74 | `server_name/host` | `example.com` | 1 |

### `docs_all/work/ba/server/deploy/_blackout/srv/PANEL_DEPLOY_20261117.md` — 11 处 / 11 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 106 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 107 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 109 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 110 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 111 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 112 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 114 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 117 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 146 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 177 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 215 | `server_name/a-record` | `<SERVER_IP>` | 1 |

### `docs_all/work/ba/server/deploy/_blackout/srv/SRV_FINDINGS_20261117.md` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 69 | `server_name/a-record` | `<SERVER_IP>` | 1 |

### `docs_all/work/ba/server/deploy/_blackout/srv/STATE_CATALOG_20261117.md` — 2 处 / 2 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 30 | `server_name/host` | `example.com` | 1 |
| 101 | `server_name/host` | `example.com` | 1 |

### `docs_all/work/ba/server/deploy/_blackout/srv/STATE_FIX_20261117.md` — 7 处 / 7 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 12 | `server_name/host` | `example.com` | 1 |
| 22 | `server_name/host` | `example.com` | 1 |
| 32 | `server_name/host` | `example.com` | 1 |
| 48 | `server_name/host` | `example.com` | 1 |
| 49 | `server_name/host` | `example.com` | 1 |
| 103 | `server_name/host` | `example.com` | 1 |
| 104 | `server_name/host` | `example.com` | 1 |

### `docs_all/work/ba/server/deploy/_card/CHAIN_AUDIT_20261117.md` — 9 处 / 9 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 267 | `server_name/host` | `example.com` | 1 |
| 542 | `server_name/host` | `example.com` | 1 |
| 570 | `server_name/host` | `example.com` | 1 |
| 676 | `server_name/host` | `example.com` | 1 |
| 681 | `server_name/host` | `example.com` | 1 |
| 784 | `server_name/host` | `example.com` | 1 |
| 790 | `server_name/host` | `example.com` | 1 |
| 884 | `server_name/host` | `example.com` | 1 |
| 886 | `server_name/host` | `example.com` | 1 |

### `docs_all/work/ba/server/deploy/_noroot/NOROOT_AUDIT_20261117.md` — 32 处 / 30 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 14 | `server_name/host` | `example.com` | 1 |
| 49 | `server_name/host` | `example.com` | 1 |
| 62 | `server_name/host` | `example.com` | 1 |
| 64 | `server_name/host` | `example.com` | 1 |
| 104 | `server_name/host` | `example.com` | 1 |
| 107 | `server_name/host` | `example.com` | 1 |
| 111 | `server_name/host` | `example.com` | 1 |
| 112 | `server_name/host` | `example.com` | 1 |
| 136 | `server_name/host` | `example.com` | 1 |
| 137 | `server_name/host` | `example.com` | 1 |
| 138 | `server_name/host` | `example.com` | 2 |
| 147 | `server_name/host` | `example.com` | 1 |
| 164 | `server_name/host` | `example.com` | 1 |
| 165 | `server_name/host` | `example.com` | 1 |
| 171 | `server_name/host` | `example.com` | 1 |
| 173 | `server_name/host` | `example.com` | 1 |
| 174 | `server_name/host` | `example.com` | 1 |
| 175 | `server_name/host` | `example.com` | 1 |
| 179 | `server_name/host` | `example.com` | 1 |
| 182 | `server_name/host` | `example.com` | 1 |
| 212 | `server_name/host` | `example.com` | 1 |
| 215 | `server_name/host` | `example.com` | 1 |
| 216 | `server_name/host` | `example.com` | 1 |
| 217 | `server_name/host` | `example.com` | 1 |
| 218 | `server_name/host` | `example.com` | 1 |
| 258 | `server_name/host` | `example.com` | 1 |
| 275 | `server_name/host` | `example.com` | 1 |
| 285 | `server_name/host` | `example.com` | 1 |
| 290 | `server_name/host` | `example.com` | 2 |
| 316 | `server_name/host` | `example.com` | 1 |

### `docs_all/work/ba/server/deploy/_noroot/PHONE8080_20261117.md` — 18 处 / 17 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 13 | `server_name/host` | `example.com` | 1 |
| 61 | `server_name/host` | `example.com` | 1 |
| 65 | `server_name/host` | `example.com` | 1 |
| 74 | `server_name/host` | `example.com` | 1 |
| 96 | `server_name/host` | `example.com` | 1 |
| 97 | `server_name/host` | `example.com` | 1 |
| 98 | `server_name/host` | `example.com` | 1 |
| 99 | `server_name/host` | `example.com` | 1 |
| 153 | `server_name/host` | `example.com` | 1 |
| 155 | `server_name/host` | `example.com` | 2 |
| 178 | `server_name/host` | `example.com` | 1 |
| 182 | `server_name/host` | `example.com` | 1 |
| 241 | `server_name/host` | `example.com` | 1 |
| 242 | `server_name/host` | `example.com` | 1 |
| 243 | `server_name/host` | `example.com` | 1 |
| 244 | `server_name/host` | `example.com` | 1 |
| 291 | `server_name/host` | `example.com` | 1 |

### `docs_all/work/ba/server/deploy/_noroot/SRV_HTTP_ENTRY_AUDIT_20261117.md` — 15 处 / 13 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 8 | `server_name/host` | `example.com` | 1 |
| 10 | `server_name/host` | `example.com` | 1 |
| 17 | `server_name/host` | `example.com` | 2 |
| 18 | `server_name/host` | `example.com` | 1 |
| 27 | `server_name/host` | `example.com` | 1 |
| 33 | `server_name/host` | `example.com` | 2 |
| 49 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 54 | `server_name/host` | `example.com` | 1 |
| 66 | `server_name/host` | `example.com` | 1 |
| 76 | `server_name/host` | `example.com` | 1 |
| 81 | `server_name/host` | `example.com` | 1 |
| 133 | `server_name/host` | `example.com` | 1 |
| 211 | `server_name/host` | `example.com` | 1 |

### `docs_all/work/ba/server/deploy/_noroot/SRV_NOROOT_CLIENT_WATCH_20261118.md` — 8 处 / 8 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 7 | `server_name/host` | `example.com` | 1 |
| 8 | `server_name/host` | `example.com` | 1 |
| 16 | `server_name/host` | `example.com` | 1 |
| 17 | `server_name/host` | `example.com` | 1 |
| 20 | `server_name/host` | `example.com` | 1 |
| 38 | `server_name/host` | `example.com` | 1 |
| 64 | `server_name/host` | `example.com` | 1 |
| 65 | `server_name/host` | `example.com` | 1 |

### `docs_all/work/ba/server/deploy/_noroot/apk/NOROOT_BUILD_PLAN_20261117.md` — 46 处 / 38 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 13 | `server_name/host` | `example.com` | 3 |
| 14 | `server_name/host` | `example.com` | 1 |
| 15 | `server_name/host` | `example.com` | 1 |
| 25 | `server_name/host` | `example.com` | 1 |
| 26 | `server_name/host` | `example.com` | 5 |
| 36 | `server_name/host` | `example.com` | 1 |
| 36 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 37 | `server_name/host` | `example.com` | 1 |
| 37 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 38 | `server_name/host` | `example.com` | 1 |
| 39 | `server_name/host` | `example.com` | 1 |
| 44 | `server_name/host` | `example.com` | 1 |
| 45 | `server_name/host` | `example.com` | 1 |
| 56 | `server_name/host` | `example.com` | 1 |
| 57 | `server_name/host` | `example.com` | 1 |
| 94 | `server_name/host` | `example.com` | 1 |
| 123 | `server_name/host` | `example.com` | 1 |
| 126 | `server_name/host` | `example.com` | 1 |
| 127 | `server_name/host` | `example.com` | 1 |
| 128 | `server_name/host` | `example.com` | 1 |
| 139 | `server_name/host` | `example.com` | 1 |
| 145 | `server_name/host` | `example.com` | 1 |
| 146 | `server_name/host` | `example.com` | 1 |
| 147 | `server_name/host` | `example.com` | 1 |
| 148 | `server_name/host` | `example.com` | 1 |
| 149 | `server_name/host` | `example.com` | 1 |
| 159 | `server_name/host` | `example.com` | 1 |
| 161 | `server_name/host` | `example.com` | 1 |
| 165 | `server_name/host` | `example.com` | 1 |
| 182 | `server_name/host` | `example.com` | 1 |
| 183 | `server_name/host` | `example.com` | 2 |
| 187 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 204 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 208 | `server_name/host` | `example.com` | 2 |
| 211 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 217 | `server_name/host` | `example.com` | 1 |
| 327 | `server_name/host` | `example.com` | 1 |
| 342 | `server_name/host` | `example.com` | 1 |

### `docs_all/work/ba/server/deploy/_noroot/apk/NOROOT_V2B_PARALLEL_20261117.md` — 12 处 / 12 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 25 | `server_name/host` | `example.com` | 1 |
| 31 | `server_name/host` | `example.com` | 1 |
| 46 | `server_name/host` | `example.com` | 1 |
| 52 | `server_name/host` | `example.com` | 1 |
| 53 | `server_name/host` | `example.com` | 1 |
| 59 | `server_name/host` | `example.com` | 1 |
| 60 | `server_name/host` | `example.com` | 1 |
| 76 | `server_name/host` | `example.com` | 1 |
| 77 | `server_name/host` | `example.com` | 1 |
| 81 | `server_name/host` | `example.com` | 1 |
| 82 | `server_name/host` | `example.com` | 1 |
| 156 | `server_name/host` | `example.com` | 1 |

### `docs_all/work/ba/server/deploy/_noroot/apk/NOROOT_V2_RELEASE_20261117.md` — 34 处 / 26 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 12 | `server_name/host` | `example.com` | 2 |
| 16 | `server_name/host` | `example.com` | 4 |
| 29 | `server_name/host` | `example.com` | 1 |
| 30 | `server_name/host` | `example.com` | 1 |
| 51 | `server_name/host` | `example.com` | 1 |
| 51 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 52 | `server_name/host` | `example.com` | 1 |
| 52 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 53 | `server_name/host` | `example.com` | 1 |
| 54 | `server_name/host` | `example.com` | 1 |
| 55 | `server_name/host` | `example.com` | 2 |
| 62 | `server_name/host` | `example.com` | 1 |
| 135 | `server_name/host` | `example.com` | 1 |
| 142 | `server_name/host` | `example.com` | 1 |
| 152 | `server_name/host` | `example.com` | 1 |
| 184 | `server_name/host` | `example.com` | 1 |
| 188 | `server_name/host` | `example.com` | 1 |
| 214 | `server_name/host` | `example.com` | 3 |
| 217 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 225 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 229 | `server_name/host` | `example.com` | 2 |
| 271 | `server_name/host` | `example.com` | 1 |
| 277 | `server_name/host` | `example.com` | 1 |
| 278 | `server_name/host` | `example.com` | 1 |
| 279 | `server_name/host` | `example.com` | 1 |
| 300 | `server_name/host` | `example.com` | 1 |

### `docs_all/work/ba/server/deploy/_noroot/apk/PHONE_INSTALL_CHECKLIST_20261117.md` — 6 处 / 6 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 15 | `server_name/host` | `example.com` | 1 |
| 25 | `server_name/host` | `example.com` | 1 |
| 26 | `server_name/host` | `example.com` | 1 |
| 27 | `server_name/host` | `example.com` | 1 |
| 137 | `server_name/host` | `example.com` | 1 |
| 192 | `server_name/host` | `example.com` | 1 |

### `docs_all/work/ba/server/deploy/_noroot/phone/PHONE_8080_AND_TEST_20261117.md` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 32 | `server_name/host` | `example.com` | 1 |

### `docs_all/work/ba/server/deploy/_noroot/phone/PHONE_PREREHEARSAL_20261117.md` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 115 | `server_name/host` | `example.com` | 1 |

### `docs_all/work/ba/server/deploy/_ops1017/REPORT_APPLY_1017.md` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 3 | `server_name/a-record` | `<SERVER_IP>` | 1 |

### `docs_all/work/ba/server/deploy/_panel/PANEL_MERGE_20261117.md` — 11 处 / 9 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 68 | `server_name/host` | `example.com` | 1 |
| 69 | `server_name/host` | `example.com` | 1 |
| 72 | `server_name/host` | `example.com` | 1 |
| 105 | `server_name/a-record` | `<SERVER_IP>` | 2 |
| 175 | `server_name/host` | `example.com` | 1 |
| 182 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 194 | `server_name/a-record` | `<SERVER_IP>` | 2 |
| 252 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 253 | `server_name/a-record` | `<SERVER_IP>` | 1 |

### `panel_full/ba_cardadmin/SHA256SUMS.txt` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 4 | `server_name/a-record` | `<SERVER_IP>` | 1 |

### `panel_full/ba_cardadmin/config.php` — 3 处 / 3 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 14 | `DB_USER` | `<REDACTED_DB_CREDENTIAL>` | 1 |
| 15 | `DB_PASS` | `<REDACTED_DB_CREDENTIAL>` | 1 |
| 18 | `APP_SECRET` | `<REDACTED_SECRET>` | 1 |

### `panel_full/ba_cardadmin/config.php.example` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 31 | `DB_USER` | `<REDACTED_DB_CREDENTIAL>` | 1 |

### `panel_full/ba_cardadmin/inc/players.php` — 2 处 / 2 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 576 | `mobile` | `<REDACTED_CONTACT>` | 1 |
| 585 | `mobile` | `<REDACTED_CONTACT>` | 1 |

### `panel_full/ba_cardadmin/pages/cards_import.php` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 274 | `mobile` | `<REDACTED_CONTACT>` | 1 |

### `panel_full/ba_cardadmin/state/cards.backup.json` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 33 | `mobile` | `<REDACTED_CONTACT>` | 1 |

### `server_config/SHA256SUMS.txt` — 19 处 / 19 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 4 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 289 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 290 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 315 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 317 | `server_name/host` | `example.com` | 1 |
| 325 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 329 | `server_name/host` | `example.com` | 1 |
| 330 | `server_name/host` | `example.com` | 1 |
| 331 | `server_name/host` | `example.com` | 1 |
| 332 | `server_name/host` | `example.com` | 1 |
| 333 | `server_name/host` | `example.com` | 1 |
| 335 | `server_name/host` | `example.com` | 1 |
| 336 | `server_name/host` | `example.com` | 1 |
| 337 | `server_name/host` | `example.com` | 1 |
| 338 | `server_name/host` | `example.com` | 1 |
| 339 | `server_name/host` | `example.com` | 1 |
| 340 | `server_name/host` | `example.com` | 1 |
| 341 | `server_name/host` | `example.com` | 1 |
| 342 | `server_name/host` | `example.com` | 1 |

### `server_config/ba_sdk/resp/common_agreement.json` — 6 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 1 | `email` | `<REDACTED_CONTACT>` | 6 |

### `server_config/ba_sdk/resp/user_detail.json` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 1 | `Token` | `<REDACTED_TOKEN>` | 1 |

### `server_config/ba_sdk/resp/user_quick-login.json` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 1 | `Token` | `<REDACTED_TOKEN>` | 1 |

### `server_config/ba_sdk/sdkcard.py` — 4 处 / 4 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 794 | `server_name/host` | `example.com` | 1 |
| 795 | `server_name/host` | `example.com` | 1 |
| 796 | `server_name/host` | `example.com` | 1 |
| 797 | `server_name/host` | `example.com` | 1 |

### `server_config/bapatch_root/NOTES-gateway.md` — 2 处 / 2 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 58 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 61 | `server_name/a-record` | `<SERVER_IP>` | 1 |

### `server_config/bapatch_root/README_CA_LOCK.txt` — 5 处 / 5 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 9 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 19 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 32 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 33 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 49 | `server_name/host` | `example.com` | 1 |

### `server_config/bapatch_root/patch_24000_v3.py` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 140 | `mxtoken` | `<REDACTED_TOKEN>` | 1 |

### `server_config/nginx/vhost/nginx/0.default.conf` — 2 处 / 2 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 11 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 12 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |

### `server_config/nginx/vhost/nginx/server_ip.conf` — 6 处 / 6 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 4 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 9 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 11 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 38 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 75 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 76 | `server_name/a-record` | `<SERVER_IP>` | 1 |

### `server_config/nginx/vhost/nginx/server_ip.conf.bak.1794776999` — 6 处 / 6 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 4 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 9 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 11 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 27 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 64 | `server_name/a-record` | `<SERVER_IP>` | 1 |
| 65 | `server_name/a-record` | `<SERVER_IP>` | 1 |

### `server_config/nginx/vhost/nginx/ai_example_tech.conf` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 4 | `server_name/a-record` | `<SERVER_IP>` | 1 |

### `server_config/nginx/vhost/nginx/ba_mitm.conf` — 7 处 / 7 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 4 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 17 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 18 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 53 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 54 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 107 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 108 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |

### `server_config/nginx/vhost/nginx/ba_mitm.conf.acctprobe.1794594965` — 7 处 / 7 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 4 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 17 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 18 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 53 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 54 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 91 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 92 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |

### `server_config/nginx/vhost/nginx/ba_mitm.conf.allapi.1794595331` — 7 处 / 7 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 4 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 17 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 18 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 53 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 54 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 100 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 101 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |

### `server_config/nginx/vhost/nginx/ba_mitm.conf.bak.1794587752` — 2 处 / 2 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 5 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 6 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |

### `server_config/nginx/vhost/nginx/ba_mitm.conf.bak.1794588172` — 2 处 / 2 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 5 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 6 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |

### `server_config/nginx/vhost/nginx/ba_mitm.conf.bak.1794588447` — 3 处 / 3 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 5 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 6 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 26 | `server_name/host` | `example.com` | 1 |

### `server_config/nginx/vhost/nginx/ba_mitm.conf.bak.1794588578` — 3 处 / 3 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 5 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 6 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 26 | `server_name/host` | `example.com` | 1 |

### `server_config/nginx/vhost/nginx/ba_mitm.conf.bak.1794589195` — 3 处 / 3 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 5 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 6 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 26 | `server_name/host` | `example.com` | 1 |

### `server_config/nginx/vhost/nginx/ba_mitm.conf.bak.1794589430` — 3 处 / 3 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 5 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 6 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 27 | `server_name/host` | `example.com` | 1 |

### `server_config/nginx/vhost/nginx/ba_mitm.conf.bak.1794589822` — 3 处 / 3 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 5 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 6 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 27 | `server_name/host` | `example.com` | 1 |

### `server_config/nginx/vhost/nginx/ba_mitm.conf.bak.1794590024` — 3 处 / 3 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 5 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 6 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 27 | `server_name/host` | `example.com` | 1 |

### `server_config/nginx/vhost/nginx/ba_mitm.conf.bak.1794590654` — 3 处 / 3 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 5 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 6 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 27 | `server_name/host` | `example.com` | 1 |

### `server_config/nginx/vhost/nginx/ba_mitm.conf.bak.1794590779` — 3 处 / 3 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 5 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 6 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 27 | `server_name/host` | `example.com` | 1 |

### `server_config/nginx/vhost/nginx/ba_mitm.conf.bak.1794591654` — 3 处 / 3 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 5 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 6 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 27 | `server_name/host` | `example.com` | 1 |

### `server_config/nginx/vhost/nginx/ba_mitm.conf.bak.20261116_055204` — 7 处 / 7 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 4 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 17 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 18 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 53 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 54 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 101 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 102 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |

### `server_config/nginx/vhost/nginx/ba_mitm.conf.bak.ca2` — 3 处 / 3 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 5 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 6 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 27 | `server_name/host` | `example.com` | 1 |

### `server_config/nginx/vhost/nginx/ba_mitm.conf.bak.http_servers` — 3 处 / 3 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 5 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 6 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 27 | `server_name/host` | `example.com` | 1 |

### `server_config/nginx/vhost/nginx/ba_mitm.conf.dto1.1794592420` — 7 处 / 7 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 4 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 16 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 17 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 52 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 53 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 87 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 88 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |

### `server_config/nginx/vhost/nginx/ba_mitm.conf.gwlog.1794593571` — 7 处 / 7 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 4 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 17 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 18 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 53 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 54 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 89 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 90 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |

### `server_config/nginx/vhost/nginx/ba_mitm.conf.hdrprobe.1794594221` — 7 处 / 7 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 4 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 17 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 18 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 53 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 54 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 90 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 91 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |

### `server_config/nginx/vhost/nginx/ba_mitm.conf.probe1.1794591887` — 3 处 / 3 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 5 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 6 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 27 | `server_name/host` | `example.com` | 1 |

### `server_config/nginx/vhost/nginx/ba_mitm.conf.staticmitm.1794602100` — 7 处 / 7 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 4 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 17 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 18 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 53 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 54 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 101 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 102 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |

### `server_config/nginx/vhost/nginx/ba_mitm.conf.struct1.1794592094` — 3 处 / 3 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 5 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 6 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 27 | `server_name/host` | `example.com` | 1 |

### `server_config/nginx/vhost/nginx/tcp/ba_sni.conf` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 3 | `server_name/host` | `example.com` | 1 |

### `server_config/nginx/vhost/nginx/tcp/ba_sni.conf.bak.1794776148` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 3 | `server_name/host` | `example.com` | 1 |

### `server_config/nginx/vhost/nginx/tcp/ba_sni.conf.staticmitm.1794602100` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 3 | `server_name/host` | `example.com` | 1 |

### `server_config/nginx/vhost/nginx/tcp/ba_sni.conf.staticpass.1794594637` — 1 处 / 1 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 3 | `server_name/host` | `example.com` | 1 |

### `server_config/nginx/vhost/nginx/example.com.conf` — 15 处 / 14 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 1 | `server_name/host` | `example.com` | 1 |
| 9 | `server_name/host` | `example.com` | 2 |
| 11 | `server_name/host` | `example.com` | 1 |
| 12 | `server_name/host` | `example.com` | 1 |
| 16 | `server_name/host` | `example.com` | 1 |
| 21 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 22 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 154 | `server_name/host` | `example.com` | 1 |
| 155 | `server_name/host` | `example.com` | 1 |
| 197 | `server_name/host` | `example.com` | 1 |
| 199 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 200 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 204 | `server_name/host` | `example.com` | 1 |
| 205 | `server_name/host` | `example.com` | 1 |

### `server_config/nginx/vhost/nginx/example.com.conf.bak` — 9 处 / 9 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 1 | `server_name/host` | `example.com` | 1 |
| 9 | `server_name/host` | `example.com` | 1 |
| 11 | `server_name/host` | `example.com` | 1 |
| 12 | `server_name/host` | `example.com` | 1 |
| 16 | `server_name/host` | `example.com` | 1 |
| 21 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 22 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 132 | `server_name/host` | `example.com` | 1 |
| 133 | `server_name/host` | `example.com` | 1 |

### `server_config/nginx/vhost/nginx/example.com.conf.bak.1794587866` — 9 处 / 9 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 1 | `server_name/host` | `example.com` | 1 |
| 9 | `server_name/host` | `example.com` | 1 |
| 11 | `server_name/host` | `example.com` | 1 |
| 12 | `server_name/host` | `example.com` | 1 |
| 16 | `server_name/host` | `example.com` | 1 |
| 21 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 22 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 146 | `server_name/host` | `example.com` | 1 |
| 147 | `server_name/host` | `example.com` | 1 |

### `server_config/nginx/vhost/nginx/example.com.conf.bak.1794588172` — 9 处 / 9 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 1 | `server_name/host` | `example.com` | 1 |
| 9 | `server_name/host` | `example.com` | 1 |
| 11 | `server_name/host` | `example.com` | 1 |
| 12 | `server_name/host` | `example.com` | 1 |
| 16 | `server_name/host` | `example.com` | 1 |
| 21 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 22 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 153 | `server_name/host` | `example.com` | 1 |
| 154 | `server_name/host` | `example.com` | 1 |

### `server_config/nginx/vhost/nginx/example.com.conf.bak.1794588447` — 10 处 / 10 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 1 | `server_name/host` | `example.com` | 1 |
| 9 | `server_name/host` | `example.com` | 1 |
| 11 | `server_name/host` | `example.com` | 1 |
| 12 | `server_name/host` | `example.com` | 1 |
| 16 | `server_name/host` | `example.com` | 1 |
| 21 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 22 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 85 | `server_name/host` | `example.com` | 1 |
| 153 | `server_name/host` | `example.com` | 1 |
| 154 | `server_name/host` | `example.com` | 1 |

### `server_config/nginx/vhost/nginx/example.com.conf.bak.20261117-020244` — 9 处 / 9 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 1 | `server_name/host` | `example.com` | 1 |
| 9 | `server_name/host` | `example.com` | 1 |
| 11 | `server_name/host` | `example.com` | 1 |
| 12 | `server_name/host` | `example.com` | 1 |
| 16 | `server_name/host` | `example.com` | 1 |
| 21 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 22 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 153 | `server_name/host` | `example.com` | 1 |
| 154 | `server_name/host` | `example.com` | 1 |

### `server_config/nginx/vhost/nginx/example.com.conf.probe1.1794591887` — 10 处 / 10 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 1 | `server_name/host` | `example.com` | 1 |
| 9 | `server_name/host` | `example.com` | 1 |
| 11 | `server_name/host` | `example.com` | 1 |
| 12 | `server_name/host` | `example.com` | 1 |
| 16 | `server_name/host` | `example.com` | 1 |
| 21 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 22 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 85 | `server_name/host` | `example.com` | 1 |
| 153 | `server_name/host` | `example.com` | 1 |
| 154 | `server_name/host` | `example.com` | 1 |

### `server_config/nginx/vhost/nginx/example.com.conf.sync1.1794592879` — 10 处 / 10 行

| 行号 | 字段 | 占位符 | 计数 |
|---:|---|---|---:|
| 1 | `server_name/host` | `example.com` | 1 |
| 9 | `server_name/host` | `example.com` | 1 |
| 11 | `server_name/host` | `example.com` | 1 |
| 12 | `server_name/host` | `example.com` | 1 |
| 16 | `server_name/host` | `example.com` | 1 |
| 21 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 22 | `ssl_certificate/ssl_certificate_key` | `<CERT_PATH>` | 1 |
| 85 | `server_name/host` | `example.com` | 1 |
| 153 | `server_name/host` | `example.com` | 1 |
| 154 | `server_name/host` | `example.com` | 1 |

---

## § 文件名脱敏

> 第一轮（本文件 §1–§4）只改**内容**、不改名；这一轮（2026-11-21）只改**名字**、不动任何文件的字节内容，
> 目的是把**路径**上仍然带着的真实域名 / 真实公网 IP 去掉——路径会跟着日志、截图、`MANIFEST.txt`、压缩包预览一起外流。

| 项 | 值 |
|---|---|
| 改名条目 | **23** 条 = **21 个文件** + **2 个目录**（其中 1 个文件的旧名里是域名**品牌词**、无 TLD，同样遮罩） |
| 域名规则 | 真实域名 → `example.com`（保留其余部分与扩展名，例如 `***.cn.conf.bak` → `example.com.conf.bak`） |
| IP 规则 | 真实公网 IP → `server_ip`（例如 `***.conf` → `server_ip.conf`） |
| 撞名 | 同一目录改名后重名时加 `-2` / `-3`（基名优先给非空文件）；本包实际撞名 2 组：`well-known/` 3 条 → `example.com.conf` / `-2` / `-3`，`client/noroot/` 2 条 → `GameMainConfig_http_example.com.bin` / `-2` |
| 内容影响 | 二进制 **0** 改动；文本文件只改「引用改名」的那几处，外加下面一行「顺带修复」的 21 + 8 处，其余字节不动 |
| 顺带修复（上轮漏扫） | 域名残留 **21** 处（转义正则 `***\.cn` 20 处 + 纯文本域名 1 处）→ `example.com`；vhost 里按域名起的 `proxy_cache_path` zone 名 **8** 处 → `example_com_cache`。这些是上轮「只扫裸域名、扫不到 `***\.cn` 转义写法」留下的，本轮一并清掉 |
| 包内引用同步 | `REDACTION.md` 路径列 **10** 处；`server_config/SHA256SUMS.txt` **2** 处；`GameMainConfig_http_*.bin` 文件名引用 **4 文件 / 5 处**（`docs_all/` 内 3 份副本另 **4** 处） |
| 改完后 | 条目名里真实域名 **0**、真实 IP **0**（`example.com` / `server_ip` 除外） |
| 有意不改（正则误命中） | `server/Data/<数据集>.<区服标记>.json`（区服/语言标记，不是域名）、`0.<名称>_total_log_format.conf`（nginx 日志格式名，不是域名）、以及 `example_tech` 一类已遮罩名 |

**改名清单（旧名一律遮罩：域名 → `***.cn` / `***.com`，IP → `*.*.*.*`；同目录内 3 条遮罩后相同的 `well-known/*.cn.conf` 按新名列一一对应）**

| # | 目录 | 旧名（遮罩） | 新名 |
|---:|---|---|---|
| 1 | `client/noroot` | `GameMainConfig_http_***.com.bin` | `GameMainConfig_http_example.com.bin` |
| 2 | `client/noroot` | `GameMainConfig_http_***.cn.bin` | `GameMainConfig_http_example.com-2.bin` |
| 3 | `server_config/nginx/vhost/nginx` | `*.*.*.*.conf` | `server_ip.conf` |
| 4 | `server_config/nginx/vhost/nginx` | `*.*.*.*.conf.bak.1794776999` | `server_ip.conf.bak.1794776999` |
| 5 | `server_config/nginx/vhost/nginx/extension` | `*.*.*.*` | `server_ip` |
| 6 | `server_config/nginx/vhost/nginx/extension` | `***.cn` | `example.com` |
| 7 | `server_config/nginx/vhost/nginx/well-known` | `*.*.*.*.conf` | `server_ip.conf` |
| 8 | `server_config/nginx/vhost/nginx/well-known` | `***.cn.conf` | `example.com-3.conf` |
| 9 | `server_config/nginx/vhost/nginx/well-known` | `***.cn.conf` | `example.com.conf` |
| 10 | `server_config/nginx/vhost/nginx/well-known` | `***.cn_1027.conf` | `example.com_1027.conf` |
| 11 | `server_config/nginx/vhost/nginx/well-known` | `***.cn_65454.conf` | `example.com_65454.conf` |
| 12 | `server_config/nginx/vhost/nginx/well-known` | `***.cn_80.conf` | `example.com_80.conf` |
| 13 | `server_config/nginx/vhost/nginx/well-known` | `***.cn_88.conf` | `example.com_88.conf` |
| 14 | `server_config/nginx/vhost/nginx/well-known` | `***.cn.conf` | `example.com-2.conf` |
| 15 | `server_config/nginx/vhost/nginx` | `***.cn.conf` | `example.com.conf` |
| 16 | `server_config/nginx/vhost/nginx` | `***.cn.conf.bak` | `example.com.conf.bak` |
| 17 | `server_config/nginx/vhost/nginx` | `***.cn.conf.bak.1794587866` | `example.com.conf.bak.1794587866` |
| 18 | `server_config/nginx/vhost/nginx` | `***.cn.conf.bak.1794588172` | `example.com.conf.bak.1794588172` |
| 19 | `server_config/nginx/vhost/nginx` | `***.cn.conf.bak.1794588447` | `example.com.conf.bak.1794588447` |
| 20 | `server_config/nginx/vhost/nginx` | `***.cn.conf.bak.20261117-020244` | `example.com.conf.bak.20261117-020244` |
| 21 | `server_config/nginx/vhost/nginx` | `***.cn.conf.probe1.1794591887` | `example.com.conf.probe1.1794591887` |
| 22 | `server_config/nginx/vhost/nginx` | `***.cn.conf.sync1.1794592879` | `example.com.conf.sync1.1794592879` |
| 23 | `client/noroot` | `_xt_needle_***.txt` | `_xt_needle_example_com.txt` |

> 其中 #23 的原名不含 TLD，只是域名品牌词；按「真实域名 → `example.com`」同一口径笼统遮罩成 `example_com`，避免从文件名反推域名。

**改名后自检**：把包解到全新空目录，逐条按 `MANIFEST.txt` 比「字节 + sha256」全过；条目名再扫一遍，
真实域名 / 真实 IP **0 命中**（`example.com`、`server_ip` 除外）。
